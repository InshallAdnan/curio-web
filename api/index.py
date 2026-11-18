"""Curio Web — every /api/* call (and published pages /p/<slug>) lands here. Plain WSGI, Python standard library only."""
import json, os, sys, time, traceback, urllib.parse
from http.cookies import SimpleCookie

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', 'server'), os.path.join(os.getcwd(), 'server')):
    if os.path.isdir(p) and p not in sys.path: sys.path.insert(0, os.path.abspath(p))

os.environ.setdefault('TZ', os.environ.get('CURIO_TZ', 'Asia/Karachi'))      # "today" is your day, not the server's
try: time.tzset()
except AttributeError: pass

import auth, tdb  # noqa: E402

MAX_BODY = 4_400_000


class Req:
    def __init__(self, env):
        self.env = env; self.method = env.get('REQUEST_METHOD', 'GET')
        self.q = {k: v[0] for k, v in urllib.parse.parse_qs(env.get('QUERY_STRING', ''), keep_blank_values=True).items()}
        p = self.q.pop('__p', None)
        self.path = ('/' + p.lstrip('/')) if p is not None else env.get('PATH_INFO', '/')
        if self.path.startswith('/api/'): self.path = self.path[4:]
        c = SimpleCookie(); c.load(env.get('HTTP_COOKIE', '') or '')
        self.cookies = {k: m.value for k, m in c.items()}
        host = env.get('HTTP_X_FORWARDED_HOST') or env.get('HTTP_HOST') or 'localhost'
        proto = env.get('HTTP_X_FORWARDED_PROTO') or ('http' if host.startswith(('localhost', '127.')) else 'https')
        self.origin = f'{proto}://{host}'

    def body(self):
        n = int(self.env.get('CONTENT_LENGTH') or 0)
        if n > MAX_BODY: raise ValueError('That is too big to send in one go.')
        return self.env['wsgi.input'].read(n) if n else b''

    def json(self):
        b = self.body(); return json.loads(b or b'{}')


def _cookie(name, value, max_age, secure):
    return ('Set-Cookie', f'{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax' + ('; Secure' if secure else ''))


def app(env, start):
    r = Req(env); secure = r.origin.startswith('https')
    headers = [('Cache-Control', 'no-store')]

    def send(status, body, ctype='application/json; charset=utf-8', extra=()):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str): body = body.encode('utf-8')
        start(status, headers + [('Content-Type', ctype), ('Content-Length', str(len(body)))] + list(extra))
        return [body]

    def redirect(to, extra=()):
        start('302 Found', headers + [('Location', to), ('Content-Length', '0')] + list(extra)); return [b'']

    try:
        path = r.path.rstrip('/') or '/'
        # ── public ──
        if path == '/health': return send('200 OK', {'ok': True, 'db': 'turso' if isinstance(tdb.remote(), tdb.Turso) else 'local', 'auth': auth.configured()})
        if path.startswith('/file/'):
            import pages
            mime, data = pages.file_get(path[6:])
            if data is None: return send('404 Not Found', {'error': 'not found'})
            start('200 OK', [('Content-Type', mime), ('Content-Length', str(len(data))), ('Cache-Control', 'private, max-age=31536000, immutable')]); return [bytes(data)]
        if path.startswith('/p/'):
            import pages
            h = pages.published(path[3:])
            return send('200 OK', h, 'text/html; charset=utf-8') if h else send('404 Not Found', '<h1>Not published</h1>', 'text/html; charset=utf-8')
        if path == '/auth/login':
            if auth.dev_user() or not auth.configured(): return redirect('/')
            url, st = auth.login_url(r.origin, r.q.get('next', '/'))
            return redirect(url, [_cookie(auth.STATE, st, 600, secure)])
        if path == '/auth/callback':
            if r.q.get('error'): return redirect('/login.html?e=' + urllib.parse.quote('Google sign-in was cancelled.'))
            try: sess, nxt = auth.finish(r.origin, r.q.get('code', ''), r.q.get('state', ''), r.cookies.get(auth.STATE))
            except ValueError as e: return redirect('/login.html?e=' + urllib.parse.quote(str(e)))
            return redirect(nxt, [_cookie(auth.COOKIE, sess, auth.DAYS * 86400, secure), _cookie(auth.STATE, '', 0, secure)])
        if path == '/auth/logout': return redirect('/login.html?out=1', [_cookie(auth.COOKIE, '', 0, secure)])

        # ── signed in only ──
        u = auth.user(r.cookies)
        if path == '/me':
            if not u: return send('401 Unauthorized', {'error': 'signin', 'configured': auth.configured()})
            return send('200 OK', {'name': u.get('name'), 'email': u.get('email'), 'pic': u.get('pic', '')})
        if not u: return send('401 Unauthorized', {'error': 'Please sign in again.', 'signin': True})
        if r.method != 'POST': return send('405 Method Not Allowed', {'error': 'POST only'})
        if env.get('HTTP_X_CURIO') != '1': return send('403 Forbidden', {'error': 'bad request'})        # only Curio's own pages call these

        if path == '/fin':
            import fin
            b = r.json()
            try: return send('200 OK', {'ok': True, 'data': fin.call(b.get('op'), b.get('args') or {})})
            except (ValueError, KeyError, tdb.Conflict) as e: return send('200 OK', {'error': str(e) if not isinstance(e, KeyError) else f'Missing: {e}'})
        if path == '/pages/rpc':
            import pages
            pages.USER['name'] = u.get('name') or 'You'
            b = r.json()
            return send('200 OK', pages.rpc(b.get('o'), b.get('m'), b.get('a') or []), 'application/json; charset=utf-8')
        if path.startswith('/import/'):
            import importer
            return send('200 OK', importer.handle(path[8:], r.json()))
        return send('404 Not Found', {'error': 'not found'})
    except Exception as e:
        traceback.print_exc()
        return send('500 Internal Server Error', {'error': f'{type(e).__name__}: {e}'[:300]})
