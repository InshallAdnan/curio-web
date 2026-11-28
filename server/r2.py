"""Curio Web — big files on Cloudflare R2 (pictures, videos, Notion files, collections sent online from the desktop).

How it fits together (no passwords or keys are copied anywhere):
  • A small Cloudflare Worker ("curio-files") sits in front of the R2 bucket. It stores and serves files, and every minute it
    calls this server's reminder tick (the "clock" for phone notifications).
  • This server signs short-lived tickets (ES256, the same P-256 code as phone reminders) — "put this file", "read this file".
    The Worker checks each ticket with this server's PUBLIC key (GET /api/files/key), so no secret has to be shared.
  • Every file keeps its usual address /api/file/<id>; for a file on R2 that address answers with a jump (302) to a signed
    Worker link, so old pages, the desktop copy and the phone all keep working.
  • Big files go straight from the browser / desktop to the Worker (Vercel's 4.5 MB limit does not apply); over 90 MB they
    go in 50 MB parts.
The Worker's address is kept in the database (Settings › Where your data lives) or in the R2_WORKER_URL variable."""
import json, os, re, secrets, time, uuid, mimetypes

import push, tdb

PART = 50 * 1024 * 1024          # multipart part size
SINGLE = 90 * 1024 * 1024        # up to this one PUT is enough (Cloudflare's free request limit is 100 MB)
MAX = 5 * 1024 * 1024 * 1024     # one file at most 5 GB
_READY = [False]


def _db(stmts):
    r = tdb.remote()
    if not _READY[0]:
        r.run([('CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, name TEXT, mime TEXT, data BLOB, size INTEGER, created REAL)', ()),
               ('CREATE TABLE IF NOT EXISTS push_store (k TEXT PRIMARY KEY, v TEXT)', ())])
        cols = {row[1] for row in r.run([('PRAGMA table_info(files)', ())])[0].rows}
        if 'r2' not in cols: r.run([('ALTER TABLE files ADD COLUMN r2 TEXT', ())])
        if 'origin' not in cols: r.run([('ALTER TABLE files ADD COLUMN origin TEXT', ())])
        _READY[0] = True
    return r.run(stmts)


# ───────────────────────── settings ─────────────────────────
def _store_get(k):
    rows = _db([('SELECT v FROM push_store WHERE k=?', (k,))])[0].rows
    return rows[0][0] if rows else None


def _store_set(k, v): _db([('INSERT OR REPLACE INTO push_store(k, v) VALUES(?,?)', (k, v))])


def worker_url():
    u = (os.environ.get('R2_WORKER_URL') or _store_get('r2_worker_url') or '').strip().rstrip('/')
    return u


def set_worker_url(u):
    u = (u or '').strip().rstrip('/')
    if u and not re.match(r'^https://[\w.-]+(:\d+)?(/[\w./-]*)?$', u): raise ValueError('That is not a https:// address.')
    _store_set('r2_worker_url', u); return {'url': u}


def on(): return bool(worker_url())


# ───────────────────────── signing (its own P-256 key, kept in the database) ─────────────────────────
def _key():
    v = _store_get('files_key')
    if not v:
        _db([('INSERT OR IGNORE INTO push_store(k, v) VALUES(?,?)', ('files_key', format(secrets.randbelow(push.N - 1) + 1, 'x')))])
        v = _store_get('files_key')
    d = int(v, 16); x, y = push._mul(d)
    return d, x, y


def public_jwk():
    _d, x, y = _key()
    return {'kty': 'EC', 'crv': 'P-256', 'x': push._b64(x.to_bytes(32, 'big')), 'y': push._b64(y.to_bytes(32, 'big')), 'ext': True}


def _ticket(op, key, exp, extra=''):
    d, _x, _y = _key()
    msg = f'{op}|{key}|{exp}|{extra}'.encode()
    return push._b64(push._sign(d, msg))


def _q(**kw):
    from urllib.parse import urlencode
    return urlencode(kw)


def read_url(key, hours=6):
    """a link the Worker accepts for reading (the expiry is rounded to the hour, so the same link repeats and caches)"""
    exp = (int(time.time()) // 3600 + 1 + hours) * 3600
    return f"{worker_url()}/get?{_q(key=key, exp=exp, sig=_ticket('get', key, exp))}"


# ───────────────────────── uploads ─────────────────────────
def _fid(name, mime):
    ext = (re.search(r'\.\w{1,6}$', name or '') or [''])[0].lower() or (mimetypes.guess_extension(mime or '') or '.bin')
    return uuid.uuid4().hex[:12] + ext


def start(a):
    """{name, size, mime} → where and how to send the file. Then call done."""
    if not on(): raise ValueError('Cloud files are not switched on yet (Settings › Where your data lives).')
    name = str(a.get('name') or 'file')[:200]; size = int(a.get('size') or 0); mime = str(a.get('mime') or '') or mimetypes.guess_type(name)[0] or 'application/octet-stream'
    if size <= 0: raise ValueError('That file is empty.')
    if size > MAX: raise ValueError('One file can be at most 5 GB.')
    want = str(a.get('id') or '')                                    # the desktop keeps its own file name (its pages already point to it)
    fid = want if re.fullmatch(r'[\w-]{6,40}\.\w{1,6}', want) and not has([want]) else _fid(name, mime)
    if a.get('lib'): fid = want if re.fullmatch(r'lib_[\w.-]{4,60}', want) else 'lib_' + fid
    key = 'f/' + fid; exp = int(time.time()) + 6 * 3600; w = worker_url()
    out = {'id': fid, 'key': key, 'mime': mime, 'size': size}
    if size <= SINGLE:
        out['put'] = f"{w}/put?{_q(key=key, exp=exp, max=size, type=mime, sig=_ticket('put', key, exp, f'{size}|{mime}'))}"
    else:
        sig = _ticket('mpu', key, exp, mime)
        base = _q(key=key, exp=exp, type=mime, sig=sig)
        out['mpu'] = {'create': f'{w}/mpu/create?{base}', 'part': f'{w}/mpu/part?{base}', 'complete': f'{w}/mpu/complete?{base}', 'part_size': PART}
    return out


def done(a, origin='web'):
    """the file is on R2 → it gets its row (and its /api/file/<id> address)"""
    fid = str(a.get('id') or '')
    if not re.fullmatch(r'[\w.-]{6,40}', fid): raise ValueError('bad file id')
    _db([('INSERT OR REPLACE INTO files (id, name, mime, data, size, created, r2, origin) VALUES (?,?,?,?,?,?,?,?)',
          (fid, str(a.get('name') or fid)[:200], str(a.get('mime') or 'application/octet-stream'), None, int(a.get('size') or 0), time.time(), 'f/' + fid, origin))])
    return {'id': fid, 'url': f'/api/file/{fid}'}


def lookup(fid):
    """→ (mime, data, r2key) for /api/file/<id>"""
    rows = _db([('SELECT mime, data, r2 FROM files WHERE id=?', (fid,))])[0].rows
    return tuple(rows[0]) if rows else (None, None, None)


def has(ids):
    """which of these file ids exist here (the desktop asks before sending pictures of a page)"""
    ids = [i for i in ids if re.fullmatch(r'[\w.-]{4,60}', str(i))][:500]
    if not ids: return []
    return [r[0] for r in _db([('SELECT id FROM files WHERE id IN (%s)' % ','.join('?' * len(ids)), ids)])[0].rows]


def usage():
    r = _db([("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE r2 IS NOT NULL", ()),
             ("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE r2 IS NULL", ())])
    return {'r2_files': r[0].rows[0][0], 'r2_bytes': r[0].rows[0][1], 'db_files': r[1].rows[0][0], 'db_bytes': r[1].rows[0][1]}


def status():
    out = {'on': on(), 'worker': worker_url(), 'from_env': bool(os.environ.get('R2_WORKER_URL'))}
    try: out.update(usage())
    except Exception: pass
    if out['on']:
        try:
            import urllib.request                                # (a name of our own: Cloudflare turns away Python's default)
            with urllib.request.urlopen(urllib.request.Request(worker_url() + '/health', headers={'User-Agent': 'Curio-Web/1.0'}), timeout=8) as r: out['worker_ok'] = json.loads(r.read()).get('ok') is True
        except Exception as e: out['worker_ok'] = False; out['worker_err'] = str(e)[:120]
    return out


# ───────────────────────── a file from a link (Notion import without downloading anything yourself) ─────────────────────────
FROM_HOSTS = ('file.notion.com', 'file.notion.so', 'prod-files-secure.s3.us-west-2.amazonaws.com', 's3.us-west-2.amazonaws.com',
              's3-us-west-2.amazonaws.com', 'secure.notion-static.com')


def from_url(a):
    """{url, name} → this server fetches the file (only from Notion's own file hosts) and puts it on R2. → {id, url, size}"""
    try: return _from_url(a)
    except ValueError: raise
    except Exception as e: raise ValueError(f'Could not copy the file: {str(e)[:200]}')


def _from_url(a):
    import urllib.request
    from urllib.parse import urlparse, unquote
    url = str(a.get('url') or '')
    host = (urlparse(url).hostname or '').lower()
    if urlparse(url).scheme != 'https' or not any(host == h or host.endswith('.' + h) for h in FROM_HOSTS):
        raise ValueError('Only Notion file links can be copied this way.')
    if not on(): raise ValueError('Cloud files are not switched on yet (Settings › Where your data lives).')
    req = urllib.request.Request(url, headers={'User-Agent': 'Curio-Web/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        mime = (r.headers.get('Content-Type') or '').split(';')[0].strip()
        data = r.read(SINGLE + 1)
    if len(data) > SINGLE: raise ValueError('That file is too big to copy from a link (over 90 MB).')
    if not data: raise ValueError('That file is empty.')
    name = str(a.get('name') or '') or unquote(urlparse(url).path.rsplit('/', 1)[-1]) or 'file'
    if not mime or mime == 'application/octet-stream' or mime.startswith('binary/'): mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    st = start({'name': name, 'size': len(data), 'mime': mime})
    put = urllib.request.Request(st['put'], data=data, method='PUT', headers={'Content-Type': st['mime'], 'User-Agent': 'Curio-Web/1.0'})
    with urllib.request.urlopen(put, timeout=90) as r:
        if r.status >= 300: raise ValueError(f'R2 said {r.status}')
    out = done({'id': st['id'], 'name': name, 'mime': st['mime'], 'size': len(data)}, origin='notion')
    out['size'] = len(data); out['mime'] = st['mime']
    return out
