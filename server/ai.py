"""AI for Curio Web — “Sign in with ChatGPT” (your own ChatGPT plan, no API key) and Ask AI chats.

How the sign-in works on the web (OpenAI's ChatGPT plan usage for apps you run yourself):
  1. Settings › AI models › “Continue with ChatGPT” opens OpenAI's sign-in in a new tab. You approve “Curio”.
  2. OpenAI then sends the browser to http://127.0.0.1:1455/auth/callback?code=… — an address on YOUR computer, so
     the tab shows “can't connect” (or, when the desktop app is open, its own page). That is expected: the address bar
     now holds a one-time code. Copy that whole address and paste it into Curio Web; the server finishes the sign-in.
  3. The tokens are kept encrypted in your own database (key: this deployment's secrets), renewed when needed, and only
     used for AI answers on your plan. They cannot read your ChatGPT chats.
Rules of this route: streaming, store=false, no temperature / max_output_tokens, system prompt in `instructions`."""
import base64, hashlib, hmac, json, os, re, secrets, time, uuid, urllib.error, urllib.parse, urllib.request

import auth, tdb

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
APP_NAME = 'Curio'
REDIRECT = 'http://127.0.0.1:1455/auth/callback'
_MARGIN = 120


class AIError(RuntimeError):
    def __init__(self, code, message, status=None):
        super().__init__(message); self.code = code; self.status = status


# ───────────────────────── storage (encrypted rows in your database) ─────────────────────────
_READY = [False]


def _db(stmts):
    r = tdb.remote()
    if not _READY[0]:
        r.run([('CREATE TABLE IF NOT EXISTS ai_store (k TEXT PRIMARY KEY, v TEXT, updated REAL)', ()),
               ('CREATE TABLE IF NOT EXISTS ai_chats (id TEXT PRIMARY KEY, title TEXT, created REAL, updated REAL, msgs TEXT)', ())])
        _READY[0] = True
    return r.run(stmts)


def _keys():
    root = hmac.new(auth._key(), b'curio-ai-vault-v1', hashlib.sha256).digest()
    return hmac.new(root, b'enc', hashlib.sha256).digest(), hmac.new(root, b'mac', hashlib.sha256).digest()


def _seal(obj):
    ke, km = _keys(); pt = json.dumps(obj, separators=(',', ':')).encode(); nonce = secrets.token_bytes(16)
    stream = b''.join(hmac.new(ke, nonce + i.to_bytes(4, 'big'), hashlib.sha256).digest() for i in range(len(pt) // 32 + 1))
    ct = bytes(a ^ b for a, b in zip(pt, stream))
    return 'v1.' + base64.b64encode(nonce + ct + hmac.new(km, nonce + ct, hashlib.sha256).digest()).decode()


def _open(text):
    try:
        raw = base64.b64decode(text[3:]); nonce, ct, tag = raw[:16], raw[16:-32], raw[-32:]
        ke, km = _keys()
        if not hmac.compare_digest(tag, hmac.new(km, nonce + ct, hashlib.sha256).digest()): return None
        stream = b''.join(hmac.new(ke, nonce + i.to_bytes(4, 'big'), hashlib.sha256).digest() for i in range(len(ct) // 32 + 1))
        return json.loads(bytes(a ^ b for a, b in zip(ct, stream)))
    except Exception: return None


def kv_get(k, secret=False):
    rows = _db([('SELECT v FROM ai_store WHERE k=?', (k,))])[0].rows
    if not rows or rows[0][0] is None: return None
    v = rows[0][0]
    if secret: return _open(v) if str(v).startswith('v1.') else None
    try: return json.loads(v)
    except ValueError: return None


def kv_set(k, v, secret=False):
    if v is None: _db([('DELETE FROM ai_store WHERE k=?', (k,))]); return
    _db([('INSERT INTO ai_store (k, v, updated) VALUES (?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated=excluded.updated',
          (k, _seal(v) if secret else json.dumps(v), time.time()))])


def cfg():
    c = kv_get('ai_cfg') or {}
    return {'provider': c.get('provider') or 'chatgpt', 'chatgpt_model': c.get('chatgpt_model') or '', 'context': c.get('context', True)}


def set_cfg(a):
    c = cfg()
    for k in ('chatgpt_model', 'context', 'provider'):
        if k in a: c[k] = a[k]
    kv_set('ai_cfg', c); return c


def host_id():
    h = kv_get('chatgpt_host')
    if isinstance(h, str) and h.startswith('urn:uuid:'): return h
    h = 'urn:uuid:' + str(uuid.uuid4()); kv_set('chatgpt_host', h); return h


# ───────────────────────── http ─────────────────────────
def _http(method, url, form=None, body=None, token=None, timeout=30):
    data = headers = None
    headers = {'Accept': 'application/json', 'User-Agent': 'Curio-Web'}
    if form is not None: data = urllib.parse.urlencode(form).encode(); headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if body is not None: data = json.dumps(body).encode(); headers['Content-Type'] = 'application/json'
    if token: headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: raw = r.read(); status = r.status
    except urllib.error.HTTPError as e: raw = e.read(); status = e.code
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AIError('network_error', 'Could not reach ChatGPT just now. Try again in a minute.')
    try: j = json.loads(raw or b'{}')
    except ValueError: j = {}
    return status, j


_FRIENDLY = {
    'subscription_sharing_user_not_eligible': 'ChatGPT plan usage is not available for this ChatGPT account. It works with a personal ChatGPT Plus / Pro account.',
    'subscription_sharing_usage_limit_exceeded': 'Your ChatGPT plan limit for Curio is used up for now. ChatGPT › Settings › Usage shows when it resets.',
    'subscription_sharing_usage_unavailable': 'ChatGPT could not check your usage just now. Try again in a minute.',
    'subscription_sharing_invalid_user': 'ChatGPT could not confirm your plan. Sign in again from Settings › AI models.',
    'chatpass_v2_scope_not_authorized': 'ChatGPT did not allow this request. Sign in again and allow “use my ChatGPT plan”.',
    'invalid_client': 'ChatGPT no longer knows this Curio connection. Press “Start over” in Settings › AI models and sign in again.',
    'invalid_grant': 'ChatGPT did not accept the sign-in (the code is used once and expires in a few minutes). Please start again.',
    'invalid_refresh_token': 'Your ChatGPT sign-in can no longer be renewed. Please sign in again.',
    'refresh_token_expired': 'Your ChatGPT sign-in can no longer be renewed. Please sign in again.',
    'refresh_token_reused': 'Your ChatGPT sign-in can no longer be renewed. Please sign in again.',
    'refresh_token_invalidated': 'Your ChatGPT sign-in can no longer be renewed. Please sign in again.',
    'access_denied': 'Sign-in was not completed. You can try again when you are ready.',
    'model_not_found': 'This model is not available on your ChatGPT plan. Pick another one.',
}
_DEAD = {'invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired', 'refresh_token_invalidated', 'refresh_token_reused'}
_STATUS = {401: 'ChatGPT did not accept the saved sign-in. Please sign in again from Settings › AI models.',
           403: 'ChatGPT refused this request (your account, workspace or region may not allow plan usage).',
           429: 'ChatGPT says the limit is reached for now. Check ChatGPT › Settings › Usage, then try again.',
           503: 'ChatGPT is busy right now. Try again in a minute.'}


def _err(data, status=None):
    code = msg = ''
    if isinstance(data, dict):
        e = data.get('error')
        if isinstance(e, dict): code = str(e.get('code') or e.get('type') or ''); msg = str(e.get('message') or '')
        elif isinstance(e, str): code = e; msg = str(data.get('error_description') or '')
        if not code and data.get('code'): code = str(data['code'])
        if not msg and data.get('detail'): msg = str(data['detail'])
    code = code.replace('_v2_', '_')
    text = _FRIENDLY.get(code) or _STATUS.get(status) or (f'ChatGPT error {status or ""}: {msg[:200]}'.strip() if (msg or status) else 'ChatGPT did not answer.')
    return AIError(code or f'http_{status}', text, status)


# ───────────────────────── OpenID + ID token (pure Python RS256) ─────────────────────────
_cache = {}


def _disc():
    d = _cache.get('disc')
    if d and time.time() - d[0] < 3600: return d[1]
    st, j = _http('GET', ISSUER + '/.well-known/openid-configuration', timeout=15)
    if st != 200 or j.get('issuer') != ISSUER: raise AIError('unavailable', 'ChatGPT sign-in could not be reached right now. Try again shortly.')
    for k in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
        if not str(j.get(k, '')).startswith(ISSUER + '/'): raise AIError('unavailable', 'ChatGPT sign-in answered unexpectedly. Try again shortly.')
    _cache['disc'] = (time.time(), j); return j


def _b64d(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _b64e(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


_DIGEST = bytes.fromhex('3031300d060960864801650304020105000420')


def _rs256(msg, sig, n, e):
    k = (n.bit_length() + 7) // 8; t = _DIGEST + hashlib.sha256(msg).digest()
    if len(sig) != k or k < len(t) + 11 or int.from_bytes(sig, 'big') >= n: return False
    em = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
    return hmac.compare_digest(em, b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t)


def _jwk(kid, again=False):
    c = _cache.get('jwks')
    if again or not c or time.time() - c[0] > 3600:
        st, j = _http('GET', _disc()['jwks_uri'], timeout=15)
        if st != 200 or not isinstance(j.get('keys'), list): raise AIError('unavailable', 'ChatGPT keys could not be fetched. Try again shortly.')
        c = (time.time(), [k for k in j['keys'] if isinstance(k, dict) and k.get('kty') == 'RSA']); _cache['jwks'] = c
    keys = c[1]
    if kid: return next((k for k in keys if k.get('kid') == kid), None)
    return keys[0] if len(keys) == 1 else None


def verify_id_token(tok, client_id, nonce=None):
    bad = AIError('invalid_id_token', 'The ChatGPT identity could not be verified. Please sign in again.')
    try:
        h64, p64, s64 = tok.split('.'); head = json.loads(_b64d(h64)); cl = json.loads(_b64d(p64)); sig = _b64d(s64)
    except Exception: raise bad
    if head.get('alg') != 'RS256': raise bad
    key = _jwk(head.get('kid')) or _jwk(head.get('kid'), again=True)
    if not key: raise bad
    if not _rs256(f'{h64}.{p64}'.encode(), sig, int.from_bytes(_b64d(key['n']), 'big'), int.from_bytes(_b64d(key['e']), 'big')): raise bad
    aud = cl.get('aud'); auds = aud if isinstance(aud, list) else [aud]
    if (cl.get('iss') != ISSUER or client_id not in auds or not isinstance(cl.get('exp'), (int, float)) or cl['exp'] + 5 < time.time()
            or not cl.get('sub') or (nonce is not None and cl.get('nonce') != nonce) or (cl.get('azp') is not None and cl['azp'] != client_id)):
        raise bad
    return {'subject': cl['sub'], 'email': cl.get('email') or '', 'name': cl.get('name') or ''}


# ───────────────────────── the ChatGPT connection ─────────────────────────
def _conn(): return kv_get('chatgpt', secret=True)


def _save(c): kv_set('chatgpt', c, secret=True)


def status(a=None):
    c = _conn()
    out = {'state': 'none', 'email': '', 'name': '', 'model': cfg()['chatgpt_model'], 'pending': bool(kv_get('chatgpt_pending', secret=True))}
    if not c or not c.get('client_id'): return out
    signed = bool(c.get('signed_in'))
    out.update(state=('ready' if PLAN_SCOPE in (c.get('scopes') or []) else 'no_plan') if signed else 'signed_out', email=c.get('email', ''), name=c.get('name', ''))
    return out


def start(a=None):
    """Step 1 — the OpenAI sign-in address (opened in a new tab)."""
    prev = _conn() or {}
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    q = {'client_id': prev.get('client_id') or 'dynamic_agent_client', 'response_type': 'code', 'redirect_uri': REDIRECT, 'scope': SCOPES,
         'resource': RESOURCE, 'state': state, 'nonce': nonce, 'code_challenge_method': 'S256',
         'code_challenge': _b64e(hashlib.sha256(verifier.encode()).digest()), 'ext_agent_host_id': host_id()}
    if not prev.get('client_id'): q['agent_name_hint'] = APP_NAME
    if prev.get('email'): q['login_hint'] = prev['email']
    if (a or {}).get('reconsent'): q['prompt'] = 'consent'
    kv_set('chatgpt_pending', {'state': state, 'nonce': nonce, 'verifier': verifier, 'exp': time.time() + 900}, secret=True)
    return {'url': _disc()['authorization_endpoint'] + '?' + urllib.parse.urlencode(q)}


def finish(a):
    """Step 2 — the address the browser landed on (127.0.0.1:1455/auth/callback?code=…), pasted back."""
    text = (a.get('url') or '').strip()
    pend = kv_get('chatgpt_pending', secret=True)
    if not pend or pend.get('exp', 0) < time.time():
        raise AIError('expired', 'That sign-in has expired. Press “Continue with ChatGPT” again.')
    qs = text.split('?', 1)[1] if '?' in text else text
    qs = qs.split('#', 1)[0]
    q = urllib.parse.parse_qs(qs, keep_blank_values=True)
    one = lambda k: q[k][0] if len(q.get(k, [])) == 1 else ''
    if one('error'):
        e = one('error'); raise AIError(e, _FRIENDLY.get(e) or f'ChatGPT did not complete the sign-in ({e[:60]}).')
    if not one('code'): raise AIError('no_code', 'That address has no sign-in code. Copy the whole address from the tab that says 127.0.0.1 after you approved Curio.')
    if not hmac.compare_digest(one('state').encode(), pend['state'].encode()):
        raise AIError('state', 'That address belongs to a different sign-in. Press “Continue with ChatGPT” again and use the newest tab.')
    prev = _conn() or {}
    saved, returned = prev.get('client_id') or '', one('client_id')
    client_id = returned or saved
    if not client_id or client_id == 'dynamic_agent_client' or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', client_id) or (saved and returned and returned != saved):
        raise AIError('registration', 'ChatGPT did not finish registering Curio. Please try again.')
    if not saved: _save({'client_id': client_id, 'scopes': [], 'signed_in': False})
    st, data = _http('POST', _disc()['token_endpoint'], form={'grant_type': 'authorization_code', 'client_id': client_id, 'code': one('code'),
                                                              'code_verifier': pend['verifier'], 'redirect_uri': REDIRECT, 'resource': RESOURCE})
    kv_set('chatgpt_pending', None)
    if st != 200: raise _err(data, st)
    if not isinstance(data.get('id_token'), str): raise AIError('invalid_id_token', 'ChatGPT did not return a verifiable identity. Please try again.')
    ident = verify_id_token(data['id_token'], client_id, nonce=pend['nonce'])
    if prev.get('subject') and ident['subject'] != prev['subject']:
        raise AIError('account_mismatch', 'This is a different ChatGPT account than before. Use the same account, or press “Start over”.')
    conn = {'client_id': client_id, 'email': ident['email'], 'name': ident['name'], 'subject': ident['subject'], 'signed_in': True, **_fields(data)}
    _save(conn); _cache.pop('models', None)
    return status()


def _fields(data, old_scopes=None):
    scope = data.get('scope')
    scopes = scope.split() if isinstance(scope, str) else list(old_scopes or [])
    at = data.get('access_token')
    if not isinstance(at, str) or not at or str(data.get('token_type', '')).lower() != 'bearer':
        raise AIError('invalid_token_response', 'ChatGPT returned incomplete credentials. Please sign in again.')
    return {'scopes': scopes, 'access_token': at, 'refresh_token': data.get('refresh_token') or '', 'expires_at': time.time() + float(data.get('expires_in') or 3600)}


def _lock():
    """one renewal at a time across servers (OpenAI replaces the refresh token on every renewal)"""
    now = time.time()
    r = _db([('INSERT INTO ai_store (k, v, updated) VALUES (?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated=excluded.updated WHERE ai_store.updated < ?',
              ('chatgpt_lock', '1', now, now - 30))])
    return r[0].changes == 1


def _unlock(): _db([('DELETE FROM ai_store WHERE k=?', ('chatgpt_lock',))])


def access_token(force=False):
    for _ in range(20):
        c = _conn()
        if not c or not c.get('client_id'): raise AIError('not_signed_in', 'ChatGPT is not connected yet. Open Settings › AI models and press “Continue with ChatGPT”.')
        if not c.get('signed_in'): raise AIError('reauth', 'You are signed out of ChatGPT. Open Settings › AI models and press “Continue with ChatGPT”.')
        if PLAN_SCOPE not in (c.get('scopes') or []): raise AIError('plan', 'ChatGPT plan usage was not allowed. Sign in again and allow it.')
        if not force and c.get('access_token') and time.time() < float(c.get('expires_at') or 0) - _MARGIN: return c['access_token']
        if not _lock(): time.sleep(0.6); force = False; continue
        try:
            c = _conn()                                   # another server may have renewed it a moment ago
            if not force and c.get('access_token') and time.time() < float(c.get('expires_at') or 0) - _MARGIN: return c['access_token']
            if not c.get('refresh_token'): raise AIError('reauth', 'Your ChatGPT sign-in has ended. Sign in again from Settings › AI models.')
            st, data = _http('POST', _disc()['token_endpoint'], form={'grant_type': 'refresh_token', 'client_id': c['client_id'],
                                                                      'refresh_token': c['refresh_token'], 'resource': RESOURCE})
            if st != 200:
                e = _err(data, st)
                if e.code in _DEAD:
                    _save(dict(c, signed_in=False, access_token='', refresh_token='', expires_at=0))
                    raise AIError('reauth', 'Your ChatGPT sign-in expired or was disconnected in ChatGPT. Sign in again from Settings › AI models.')
                raise e
            f = _fields(data, c.get('scopes'))
            if not f['refresh_token']: f['refresh_token'] = c['refresh_token']
            c.update(f); _save(c)
            return c['access_token']
        finally: _unlock()
    raise AIError('busy', 'ChatGPT sign-in is being renewed. Try again in a moment.')


def logout(a=None):
    c = _conn()
    if c and c.get('refresh_token'):
        ep = _disc().get('revocation_endpoint')
        if ep and ep.startswith(ISSUER + '/'):
            try: _http('POST', ep, form={'token': c['refresh_token'], 'token_type_hint': 'refresh_token', 'client_id': c['client_id']}, timeout=10)
            except AIError: pass
    if c: _save({k: c.get(k) for k in ('client_id', 'email', 'name', 'subject')} | {'signed_in': False, 'scopes': []})
    return status()


def reset(a=None):
    """Start over: forget the sign-in and the registration."""
    try: logout()
    except AIError: pass
    kv_set('chatgpt', None); kv_set('chatgpt_pending', None)
    return status()


def models(a=None):
    m = _cache.get('models')
    if m and time.time() - m[0] < 600: return m[1]
    for attempt in range(2):
        st, j = _http('GET', RESOURCE + '/models', token=access_token(force=attempt == 1))
        if st == 401 and attempt == 0: continue
        if st != 200: raise _err(j, st)
        out = [{'slug': x['slug'], 'name': x.get('display_name') or x['slug']} for x in j.get('models') or []
               if isinstance(x, dict) and x.get('visibility') == 'list' and isinstance(x.get('slug'), str)]
        _cache['models'] = (time.time(), out); return out
    raise AIError('reauth', 'ChatGPT did not accept the saved sign-in. Please sign in again.')


def _stream(body, token, timeout=280):
    req = urllib.request.Request(RESOURCE + '/responses', data=json.dumps(body).encode(), method='POST',
                                 headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': 'text/event-stream', 'User-Agent': 'Curio-Web'})
    try: resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        try: j = json.loads(e.read() or b'{}')
        except ValueError: j = {}
        raise _err(j, e.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AIError('network_error', 'Could not reach ChatGPT. Try again in a minute.')
    deltas, done, final, ok = [], [], {}, False
    with resp:
        for raw in resp:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'): continue
            p = line[5:].strip()
            if not p or p == '[DONE]': continue
            try: ev = json.loads(p)
            except ValueError: continue
            t = ev.get('type')
            if t == 'response.output_text.delta' and isinstance(ev.get('delta'), str): deltas.append(ev['delta'])
            elif t == 'response.output_text.done' and isinstance(ev.get('text'), str): done.append(ev['text'])
            elif t == 'response.failed': raise _err({'error': (ev.get('response') or {}).get('error') or {}})
            elif t == 'error': raise _err(ev if 'error' in ev else {'error': ev})
            elif t == 'response.incomplete': raise AIError('incomplete', 'ChatGPT stopped before finishing. Try again.')
            elif t == 'response.completed': final = ev.get('response') or {}; ok = True; break
    if not ok and not deltas: raise AIError('cut', 'The answer was cut off. Try again.')
    text = ''.join(deltas) or ''.join(done)
    if not text:
        for it in final.get('output') or []:
            for c in (it.get('content') or []) if isinstance(it, dict) else []:
                if isinstance(c, dict) and c.get('type') == 'output_text': text += c.get('text') or ''
    return text, final.get('usage') or {}, final.get('model') or body['model']


def respond(messages, system='', model=None):
    model = (model or '').strip() or cfg()['chatgpt_model'] or (models() or [{}])[0].get('slug')
    if not model: raise AIError('no_models', 'ChatGPT did not list any model for your plan.')
    body = {'model': model, 'input': [{'role': 'assistant' if m['role'] == 'assistant' else 'user', 'content': m['content']} for m in messages],
            'store': False, 'stream': True}
    if system.strip(): body['instructions'] = system.strip()
    force = False
    for attempt in range(2):
        try: return _stream(body, access_token(force=force))
        except AIError as e:
            if e.status == 401 and attempt == 0: force = True; continue
            raise


# ───────────────────────── Ask AI ─────────────────────────
SYSTEM = """You are Curio — a warm, smart assistant inside the user's own Curio app (their Pages notes, Finance book and Calendar).
Talk like a helpful friend and expert. Chat, brainstorm, explain, plan and answer general questions from your own knowledge.
Sometimes you get "From your Curio" notes: matching Pages (numbered [P1], [P2] …) and a Finance summary. Use them when the
question is about the user's notes, plans, money or spending — cite pages like [P1] right after the point they support.
Never invent numbers or what a page says. If the notes do not cover it, say so briefly and help anyway.
Start with the direct answer. Be concrete. Short replies for chit-chat. Use bullets only when there are several points.
Money: use the user's currency as given. Reply in the same language and style the user writes in (Roman Urdu, Urdu, Hindi, English or a mix)."""

_STOP = set('the a an is are was were be to of in on for and or with my me i you it this that what how kya hai hain ka ki ke ko se mein me main mera meri mujhe aur ya bhi tha thi kar karo kaise kitna kitne'.split())
_MONEY = re.compile(r'\b(money|spen[dt]|spending|expense|expenses|income|salary|balance|account|bank|budget|paise|paisa|pesa|kharch|kharcha|amdani|rupe|rs|pkr|usd|\$|saving|savings|goal|subscription|bill|paid|pay|transaction|finance|loan|wallet)\w*', re.I)


def _pages_context(q, n=5):
    import pages
    words = [w for w in re.findall(r'\w+', q.lower()) if len(w) > 2 and w not in _STOP][:8]
    if not words: return []
    def go():
        with pages.connect() as c:
            rows = c.execute('SELECT id, title, content, icon FROM docs WHERE archived=0').fetchall()
        scored = []
        for r in rows:
            title = (r['title'] or '').lower()
            try: body = pages._text(json.loads(r['content'] or '[]'))
            except ValueError: body = ''
            low = body.lower(); s = sum(3 * title.count(w) + min(low.count(w), 5) for w in words)
            if s: scored.append((s, r, body))
        scored.sort(key=lambda x: -x[0])
        return [{'id': r['id'], 'title': r['title'] or 'Untitled', 'icon': r['icon'] or '', 'text': body[:1500]} for _, r, body in scored[:n]]
    return pages.run(go)


def _finance_context():
    import fin
    from finance import ledger, reports, currency
    def go(con):
        accs = ledger.accounts(con, True)
        if not accs: return ''
        from finance.util import this_month, add_months
        b = currency.base(con); bal = ledger.balances(con); m = this_month()
        lines = [f'Currency: {b}. Amounts are in {b} unless shown. Today: {time.strftime("%Y-%m-%d")}.']
        lines.append('Accounts: ' + '; '.join(f'{a["name"]} {bal.get(a["id"], 0) / 100:,.0f} {a["currency"]}' for a in accs if not a['archived']))
        for mm in (m, add_months(m, -1)):
            s = reports.month_summary(con, mm)
            cats = reports.category_breakdown(con, mm, 'expense')[:8]
            lines.append(f'{mm}: income {s["income"] / 100:,.0f}, spent {s["expense"] / 100:,.0f}. Top spending: ' + ', '.join(f'{n} {v / 100:,.0f}' for n, v in cats))
        rec = [dict(r) for r in ledger.list_transactions(con, limit=30)]
        lines.append('Latest transactions (date | account | kind | amount | category | title):')
        for r in rec:
            lines.append(f'{r["date"]} | {r.get("account_name") or ""} | {r["kind"]} | {abs(r["net"]) / 100:,.0f} {r["currency"]} | {r.get("category_name") or ""} | {(r.get("title") or r.get("note") or "")[:60]}')
        return '\n'.join(lines)
    try: return fin.run(go)
    except Exception: return ''


def chats(a=None):
    rows = _db([('SELECT id, title, created, updated FROM ai_chats ORDER BY updated DESC LIMIT 200', ())])[0].dicts()
    return rows


def chat(a):
    rows = _db([('SELECT id, title, created, updated, msgs FROM ai_chats WHERE id=?', (a['id'],))])[0].dicts()
    if not rows: return None
    r = rows[0]; r['msgs'] = json.loads(r['msgs'] or '[]'); return r


def rename(a):
    _db([('UPDATE ai_chats SET title=? WHERE id=?', ((a.get('title') or 'Chat')[:120], a['id']))]); return True


def delete(a):
    _db([('DELETE FROM ai_chats WHERE id=?', (a['id'],))]); return True


def ask(a):
    text = (a.get('text') or '').strip()
    if not text: raise AIError('empty', 'Write a message first.')
    c = cfg()
    cur = chat({'id': a['id']}) if a.get('id') else None
    msgs = (cur or {}).get('msgs') or []
    use_ctx = a.get('context', c['context'])
    found, fctx = [], ''
    if use_ctx:
        try: found = _pages_context(text)
        except Exception: found = []
        if _MONEY.search(text): fctx = _finance_context()
    note = ''
    if found or fctx:
        parts = ['From your Curio (use only if it helps):']
        for i, p in enumerate(found, 1): parts.append(f'[P{i}] {p["icon"]} {p["title"]}\n{p["text"]}')
        if fctx: parts.append('Finance summary:\n' + fctx)
        note = '\n\n'.join(parts)
    hist = [{'role': m['role'], 'content': m['content'][:4000]} for m in msgs[-12:]]
    q = text if not note else f'{text}\n\n---\n{note}'
    answer, usage, model = respond(hist + [{'role': 'user', 'content': q}], SYSTEM, a.get('model') or c['chatgpt_model'])
    now = time.time()
    msgs = msgs + [{'role': 'user', 'content': text, 'ts': now},
                   {'role': 'assistant', 'content': answer, 'ts': time.time(), 'model': model, 'pages': [{'id': p['id'], 'title': p['title'], 'icon': p['icon']} for p in found],
                    'finance': bool(fctx)}]
    cid = (cur or {}).get('id') or a.get('id') or uuid.uuid4().hex[:12]
    title = (cur or {}).get('title') or re.sub(r'\s+', ' ', text)[:60]
    _db([('INSERT INTO ai_chats (id, title, created, updated, msgs) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET msgs=excluded.msgs, updated=excluded.updated',
          (cid, title, (cur or {}).get('created') or now, time.time(), json.dumps(msgs, ensure_ascii=False)))])
    return {'id': cid, 'title': title, 'msg': msgs[-1]}


def settings(a=None):
    return {'cfg': cfg(), 'chatgpt': status()}


OPS = {'settings': settings, 'set_cfg': set_cfg, 'status': status, 'start': start, 'finish': finish, 'logout': logout, 'reset': reset,
       'models': models, 'chats': chats, 'chat': chat, 'rename': rename, 'delete': delete, 'ask': ask}


def call(op, args):
    f = OPS.get(op)
    if f is None: raise ValueError(f'Unknown action: {op}')
    try: return f(args or {})
    except AIError as e: raise ValueError(str(e))
