"""Run Curio Web on your own PC:  python dev.py   →  http://localhost:8787
Uses a local SQLite file (.data/curio-web.db) unless TURSO_DATABASE_URL is set; CURIO_DEV_USER skips Google sign-in."""
import os, sys, mimetypes
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api'))
os.environ.setdefault('CURIO_DEV_USER', 'You')
from index import app as api_app  # noqa: E402

PUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')


def app(env, start):
    path = env.get('PATH_INFO', '/')
    if path.startswith('/api/') or path.startswith('/p/'):
        if path.startswith('/p/'): env['QUERY_STRING'] = '__p=' + path.lstrip('/') + ('&' + env['QUERY_STRING'] if env.get('QUERY_STRING') else '')
        return api_app(env, start)
    f = os.path.normpath(os.path.join(PUB, path.lstrip('/')))
    if os.path.isdir(f): f = os.path.join(f, 'index.html')
    if not f.startswith(PUB) or not os.path.isfile(f): start('404 Not Found', [('Content-Type', 'text/plain')]); return [b'not found']
    data = open(f, 'rb').read()
    start('200 OK', [('Content-Type', mimetypes.guess_type(f)[0] or 'application/octet-stream'), ('Content-Length', str(len(data)))])
    return [data]


class Quiet(WSGIRequestHandler):
    def log_message(self, *a): pass


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8787))
    print(f'Curio Web on http://localhost:{port}')
    make_server('127.0.0.1', port, app, handler_class=Quiet).serve_forever()
