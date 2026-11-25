"""Phone reminders for Curio Web (Web Push, standard library only).

How it works: your phone (Curio Web added to the home screen) gives a "subscription" address. Every minute a free
cron service calls /api/tracker/tick?key=…; when a Tracker reminder is due, the server sends an EMPTY push (no
message inside — that would need encryption the standard library does not have) and the phone's Curio then asks
/api/tracker/inbox what to show. The push is signed with this server's own key (VAPID, ES256 — made here, kept in your
database). Nothing goes to anyone else."""
import base64, hashlib, hmac, json, secrets, time, urllib.error, urllib.parse, urllib.request

import auth, tdb

# ───────────────────────── P-256 (ES256) ─────────────────────────
P = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
A = P - 3
B = 0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
N = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
G = (0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296, 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5)


def _add(p, q):
    if p is None: return q
    if q is None: return p
    if p[0] == q[0] and (p[1] + q[1]) % P == 0: return None
    if p == q: l = (3 * p[0] * p[0] + A) * pow(2 * p[1], -1, P) % P
    else: l = (q[1] - p[1]) * pow(q[0] - p[0], -1, P) % P
    x = (l * l - p[0] - q[0]) % P
    return x, (l * (p[0] - x) - p[1]) % P


def _mul(k, p=G):
    r = None
    while k:
        if k & 1: r = _add(r, p)
        p = _add(p, p); k >>= 1
    return r


def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def _unb64(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _sign(d, msg):
    z = int.from_bytes(hashlib.sha256(msg).digest(), 'big')
    while True:
        k = secrets.randbelow(N - 1) + 1; r = _mul(k)[0] % N
        if not r: continue
        s = pow(k, -1, N) * (z + r * d) % N
        if s: return r.to_bytes(32, 'big') + s.to_bytes(32, 'big')


# ───────────────────────── storage ─────────────────────────
_READY = [False]


def _db(stmts):
    r = tdb.remote()
    if not _READY[0]:
        r.run([('CREATE TABLE IF NOT EXISTS push_subs (endpoint TEXT PRIMARY KEY, sub TEXT, created REAL, last REAL, name TEXT)', ()),
               ('CREATE TABLE IF NOT EXISTS push_inbox (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, title TEXT, body TEXT, tag TEXT, url TEXT, seen INTEGER DEFAULT 0)', ()),
               ('CREATE TABLE IF NOT EXISTS push_store (k TEXT PRIMARY KEY, v TEXT)', ())])
        _READY[0] = True
    return r.run(stmts)


def _keys():
    got = _db([('SELECT v FROM push_store WHERE k=?', ('vapid',))])[0].rows
    if got: d = int(got[0][0], 16)
    else:
        d = secrets.randbelow(N - 1) + 1; _db([('INSERT OR IGNORE INTO push_store(k, v) VALUES(?,?)', ('vapid', format(d, 'x')))])
        d = int(_db([('SELECT v FROM push_store WHERE k=?', ('vapid',))])[0].rows[0][0], 16)
    x, y = _mul(d)
    return d, b'\x04' + x.to_bytes(32, 'big') + y.to_bytes(32, 'big')


def public_key(): return _b64(_keys()[1])


def tick_key():
    """the secret for the cron address (made from this deployment's own secret)"""
    return hmac.new(auth._key(), b'curio-tracker-tick', hashlib.sha256).hexdigest()[:32]


def subscribe(sub, name=''):
    ep = sub.get('endpoint') or ''
    if not ep.startswith('https://'): raise ValueError('That is not a push address.')
    _db([('INSERT OR REPLACE INTO push_subs(endpoint, sub, created, last, name) VALUES(?,?,?,?,?)', (ep, json.dumps(sub), time.time(), None, name[:40]))])
    return True


def unsubscribe(endpoint): _db([('DELETE FROM push_subs WHERE endpoint=?', (endpoint,))]); return True


def subs(): return _db([('SELECT endpoint, name, created, last FROM push_subs ORDER BY created', ())])[0].dicts()


def _send(endpoint, d, pub):
    u = urllib.parse.urlparse(endpoint); aud = f'{u.scheme}://{u.netloc}'
    head = _b64(json.dumps({'typ': 'JWT', 'alg': 'ES256'}).encode()); body = _b64(json.dumps({'aud': aud, 'exp': int(time.time()) + 12 * 3600, 'sub': 'https://curio.app'}).encode())
    jwt = f'{head}.{body}.' + _b64(_sign(d, f'{head}.{body}'.encode()))
    req = urllib.request.Request(endpoint, data=b'', method='POST', headers={'TTL': '3600', 'Urgency': 'high', 'Authorization': f'vapid t={jwt}, k={_b64(pub)}',
                                                                              'Content-Length': '0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status
    except urllib.error.HTTPError as e: return e.code


def notify(items):
    """items: [(title, body, tag, url)] → into the inbox, then one empty push to every phone"""
    if not items: return 0
    now = time.time()
    _db([('INSERT INTO push_inbox(ts, title, body, tag, url) VALUES(?,?,?,?,?)', (now, t[:120], (b or '')[:300], tag, url or '/#/tracker')) for t, b, tag, url in items])
    d, pub = _keys(); sent = 0
    for s in subs():
        st = _send(s['endpoint'], d, pub)
        if st in (404, 410): unsubscribe(s['endpoint'])
        elif 200 <= st < 300: sent += 1; _db([('UPDATE push_subs SET last=? WHERE endpoint=?', (now, s['endpoint']))])
    return sent


def inbox():
    """what the phone should show now (unseen, last 2 hours) — and mark it seen"""
    rows = _db([('SELECT id, title, body, tag, url FROM push_inbox WHERE seen=0 AND ts>? ORDER BY id DESC LIMIT 4', (time.time() - 7200,))])[0].dicts()
    if rows: _db([('UPDATE push_inbox SET seen=1 WHERE id IN (%s)' % ','.join(str(int(r['id'])) for r in rows), ())])
    _db([('DELETE FROM push_inbox WHERE ts<?', (time.time() - 7 * 86400,))])
    return rows


def seen_tick():
    """10.43: remember when the reminder service last called (so Setup can say if it is working)"""
    try: _db([('INSERT OR REPLACE INTO push_store(k, v) VALUES(?,?)', ('last_tick', str(time.time())))])
    except Exception: pass


def status():
    try: v = _db([('SELECT v FROM push_store WHERE k=?', ('last_tick',))])[0].rows
    except Exception: v = []
    last = float(v[0][0]) if v else None
    ss = subs()
    kinds = sorted({('Android / Chrome' if 'fcm.googleapis' in x['endpoint'] else 'iPhone' if 'push.apple' in x['endpoint'] else 'Other') for x in ss})
    return dict(last_tick=last, ago=(time.time() - last) if last else None, phones=len(ss), kinds=kinds)
