"""Sign-in for Curio Web: Google, and only the address(es) in ALLOWED_EMAIL may come in. No passwords anywhere.

Environment (Vercel › Settings › Environment Variables):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET   the OAuth client (type “Web application”)
  ALLOWED_EMAIL                            your Gmail (several: comma separated)
  AUTH_SECRET                              optional — signs the session cookie (otherwise derived from the two secrets above)
The session is a signed cookie (30 days). Nothing about you is stored anywhere else."""
import base64, hashlib, hmac, json, os, secrets, time, urllib.parse, urllib.request

COOKIE = 'curio_s'; STATE = 'curio_st'; DAYS = 30


def _key():
    k = os.environ.get('AUTH_SECRET') or (os.environ.get('GOOGLE_CLIENT_SECRET', '') + '|' + os.environ.get('TURSO_AUTH_TOKEN', '') + '|curio-web')
    return hashlib.sha256(k.encode()).digest()


def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def _unb64(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def sign(obj):
    body = _b64(json.dumps(obj, separators=(',', ':')).encode())
    return body + '.' + _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())


def unsign(tok):
    try:
        body, sig = tok.split('.', 1)
        if not hmac.compare_digest(sig, _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())): return None
        obj = json.loads(_unb64(body))
        return obj if obj.get('exp', 0) > time.time() else None
    except Exception: return None


def allowed():
    return {e.strip().lower() for e in os.environ.get('ALLOWED_EMAIL', '').split(',') if e.strip()}


def dev_user():
    """Running on your own PC without Google set up: CURIO_DEV_USER=Name signs you in automatically."""
    n = os.environ.get('CURIO_DEV_USER')
    return {'name': n, 'email': 'dev@local'} if n and not os.environ.get('VERCEL') else None


def user(cookies):
    return dev_user() or unsign(cookies.get(COOKIE, '') or '')


def configured(): return bool(os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET') and allowed())


def login_url(origin, nxt='/'):
    st = secrets.token_urlsafe(18)
    q = urllib.parse.urlencode({'client_id': os.environ['GOOGLE_CLIENT_ID'], 'redirect_uri': origin + '/api/auth/callback', 'response_type': 'code',
                                'scope': 'openid email profile', 'state': st, 'prompt': 'select_account', 'access_type': 'online'})
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + q, sign({'st': st, 'next': nxt if nxt.startswith('/') else '/', 'exp': time.time() + 600})


def finish(origin, code, state, state_cookie):
    """→ (session cookie value, next path) or raises ValueError with a message for the person."""
    st = unsign(state_cookie or '')
    if not st or not hmac.compare_digest(st.get('st', ''), state or ''): raise ValueError('The sign-in took too long or came from somewhere else. Please try again.')
    data = urllib.parse.urlencode({'code': code, 'client_id': os.environ['GOOGLE_CLIENT_ID'], 'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
                                   'redirect_uri': origin + '/api/auth/callback', 'grant_type': 'authorization_code'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=data), timeout=15) as r: tok = json.loads(r.read())
    # the ID token came straight from Google over TLS in exchange for our secret, so its contents can be read as they are
    claims = json.loads(_unb64(tok['id_token'].split('.')[1]))
    if claims.get('aud') != os.environ['GOOGLE_CLIENT_ID']: raise ValueError('This sign-in was not meant for Curio.')
    email = (claims.get('email') or '').lower()
    if not claims.get('email_verified') or email not in allowed():
        raise ValueError('This Google account is not allowed into this Curio. Sign in with the account set in ALLOWED_EMAIL.')
    name = (claims.get('given_name') or claims.get('name') or email.split('@')[0]).split()[0]
    return sign({'email': email, 'name': name, 'pic': claims.get('picture', ''), 'exp': time.time() + DAYS * 86400}), st.get('next', '/')
