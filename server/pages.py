"""Pages (the Notion clone) for Curio Web — the desktop's pages_ui.py / pages_ext.py logic on the shared database.

The web app (public/pages/pages.js — the same build as the desktop) talks to two objects, `curio` and `curioext`,
exactly as it does over Qt's web channel; public/pages/channel.js turns each call into POST /api/pages/rpc.
Every answer is JSON text, like the desktop slots."""
import base64, html, json, re, time, uuid, zipfile, io, mimetypes

import tdb
from tdb import Snapshot

TABLES = ['docs', 'dbs', 'page_meta', 'page_comments']
BOOK = Snapshot('pages', TABLES)
SNAP_EVERY = 600; KEEP = 60
USER = {'name': 'You'}


def _schema(c):
    c.execute('''CREATE TABLE IF NOT EXISTS docs (id TEXT PRIMARY KEY, title TEXT, content TEXT, icon TEXT, cover TEXT, parent TEXT,
                 archived INTEGER DEFAULT 0, published INTEGER DEFAULT 0, created REAL, updated REAL)''')
    cols = {r[1] for r in c.execute('PRAGMA table_info(docs)')}
    for col, kind in (('db', 'TEXT'), ('props', 'TEXT'), ('sort', 'REAL')):
        if col not in cols: c.execute(f'ALTER TABLE docs ADD COLUMN {col} {kind}')
    c.execute('''CREATE TABLE IF NOT EXISTS dbs (id TEXT PRIMARY KEY, title TEXT, icon TEXT, props TEXT, views TEXT, parent TEXT, created REAL, updated REAL)''')
    c.execute('CREATE INDEX IF NOT EXISTS docs_db ON docs(db)')
    c.execute('''CREATE TABLE IF NOT EXISTS page_meta (id TEXT PRIMARY KEY, fav INTEGER DEFAULT 0, fav_order REAL, locked INTEGER DEFAULT 0,
                 font TEXT DEFAULT 'default', small INTEGER DEFAULT 0, toc INTEGER DEFAULT 0, visited REAL)''')
    c.execute('CREATE TABLE IF NOT EXISTS page_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, doc TEXT, text TEXT, ts REAL, done INTEGER DEFAULT 0)')


_CON = [None]


class _Ctx:
    """`with connect() as c:` — the in-memory copy of the running call."""
    def __enter__(self): return _CON[0]
    def __exit__(self, *a): return False


def connect(): return _Ctx()


def run(fn, *a):
    def go(c):
        _schema(c); _CON[0] = c
        try: return fn(*a)
        finally: _CON[0] = None
    return BOOK.run(go)


# ───────────────────────── direct tables (too big to copy: versions, files) ─────────────────────────
_DIRECT_READY = [False]


def direct(stmts):
    r = tdb.remote()
    if not _DIRECT_READY[0]:
        r.run([('''CREATE TABLE IF NOT EXISTS page_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, doc TEXT, title TEXT, icon TEXT,
                    content TEXT, words INTEGER, ts REAL, label TEXT)''', ()),
               ('CREATE INDEX IF NOT EXISTS page_versions_doc ON page_versions(doc, ts)', ()),
               ('CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, name TEXT, mime TEXT, data BLOB, size INTEGER, created REAL)', ()),
               ('CREATE TABLE IF NOT EXISTS published (slug TEXT PRIMARY KEY, doc TEXT, html TEXT, updated REAL)', ())])
        _DIRECT_READY[0] = True
    return r.run(stmts)


# ───────────────────────── pages (pages_ui.py) ─────────────────────────
def _row(r, content=False):
    d = {'id': r['id'], 'title': r['title'] or 'Untitled', 'icon': r['icon'], 'coverImage': r['cover'], 'parentId': r['parent'],
         'isArchived': bool(r['archived']), 'isPublished': bool(r['published']), 'updatedAt': r['updated']}
    if content: d['content'] = r['content']; d['db'] = r['db']
    return d


def list_docs():
    with connect() as c: return [_row(r) for r in c.execute('SELECT * FROM docs WHERE db IS NULL ORDER BY created')]


_IMG = re.compile(r'"type":\s*"image"\s*,\s*"props":\s*\{[^{}]*?"url":\s*"([^"]+)"')


def _db(r):
    return {'id': r['id'], 'title': r['title'] or '', 'icon': r['icon'], 'props': json.loads(r['props'] or '[]'),
            'views': json.loads(r['views'] or '[]'), 'parent': r['parent'], 'updatedAt': r['updated']}


def _rowdict(r):
    m = _IMG.search(r['content'] or '')
    return {'id': r['id'], 'title': r['title'] if r['title'] != 'Untitled' else '', 'icon': r['icon'], 'coverImage': r['cover'],
            'props': json.loads(r['props'] or '{}'), 'created': r['created'], 'updated': r['updated'], 'sort': r['sort'],
            'thumb': m.group(1) if m else None}


def db_list():
    with connect() as c:
        return [{'id': r['id'], 'title': r['title'] or '', 'icon': r['icon'], 'props': json.loads(r['props'] or '[]')}
                for r in c.execute('SELECT * FROM dbs ORDER BY created')]


def db_create(parent, payload):
    i = uuid.uuid4().hex[:16]; t = time.time(); p = payload or {}
    with connect() as c:
        c.execute('INSERT INTO dbs (id, title, icon, props, views, parent, created, updated) VALUES (?,?,?,?,?,?,?,?)',
                  (i, p.get('title') or '', p.get('icon'), json.dumps(p.get('props') or []), json.dumps(p.get('views') or []), parent or None, t, t))
        return _db(c.execute('SELECT * FROM dbs WHERE id=?', (i,)).fetchone())


def db_get(i):
    with connect() as c:
        r = c.execute('SELECT * FROM dbs WHERE id=?', (i,)).fetchone()
        if not r: return None
        rows = [_rowdict(x) for x in c.execute('SELECT * FROM docs WHERE db=? ORDER BY COALESCE(sort, created)', (i,))]
        return {'db': _db(r), 'rows': rows}


def db_update(i, payload):
    sets, vals = [], []
    for k in ('title', 'icon', 'props', 'views', 'parent'):
        if k in payload:
            v = payload[k]; sets.append(f'{k}=?'); vals.append(json.dumps(v) if k in ('props', 'views') else v)
    if sets:
        with connect() as c: c.execute(f'UPDATE dbs SET {", ".join(sets)}, updated=? WHERE id=?', (*vals, time.time(), i))


def db_remove(i):
    with connect() as c:
        c.execute('DELETE FROM docs WHERE db=?', (i,)); c.execute('DELETE FROM dbs WHERE id=?', (i,))


def row_create(dbid, payload):
    i = uuid.uuid4().hex[:16]; t = time.time(); p = payload or {}
    with connect() as c:
        c.execute('INSERT INTO docs (id, title, content, icon, cover, parent, created, updated, db, props, sort) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                  (i, p.get('title') or '', None, p.get('icon'), None, None, t, t, dbid, json.dumps(p.get('props') or {}), p.get('sort', t)))
        return _rowdict(c.execute('SELECT * FROM docs WHERE id=?', (i,)).fetchone())


def row_update(i, payload):
    with connect() as c:
        r = c.execute('SELECT props FROM docs WHERE id=?', (i,)).fetchone()
        if not r: return
        sets, vals = [], []
        if 'props' in payload:
            props = json.loads(r['props'] or '{}'); props.update(payload['props'] or {})
            sets.append('props=?'); vals.append(json.dumps(props))
        for k, col in (('title', 'title'), ('icon', 'icon'), ('coverImage', 'cover'), ('sort', 'sort'), ('created', 'created')):   # created: imports keep the original date
            if k in payload: sets.append(f'{col}=?'); vals.append(payload[k])
        if sets: c.execute(f'UPDATE docs SET {", ".join(sets)}, updated=? WHERE id=?', (*vals, time.time(), i))


def row_delete(i):
    with connect() as c:
        c.execute('DELETE FROM docs WHERE id=?', (i,))
        for r in c.execute("SELECT id, props FROM docs WHERE db IS NOT NULL AND props LIKE ?", (f'%{i}%',)).fetchall():
            try: props = json.loads(r['props'] or '{}')
            except ValueError: continue
            changed = False
            for k, v in props.items():
                if isinstance(v, list) and i in v: props[k] = [x for x in v if x != i]; changed = True
            if changed: c.execute('UPDATE docs SET props=? WHERE id=?', (json.dumps(props), r['id']))


def get_doc(i):
    with connect() as c:
        r = c.execute('SELECT * FROM docs WHERE id=?', (i,)).fetchone()
        return _row(r, True) if r else None


def create(parent=None, title='Untitled', content=None, icon=None):
    i = uuid.uuid4().hex[:16]; t = time.time()
    with connect() as c:
        c.execute('INSERT INTO docs (id, title, content, icon, cover, parent, created, updated) VALUES (?,?,?,?,?,?,?,?)',
                  (i, title or 'Untitled', content, icon, None, parent or None, t, t))
    return i


def update(i, payload):
    if isinstance(payload, dict) and 'content' in payload:
        try: snapshot(i)
        except Exception: pass
    _update(i, payload)


def _update(i, payload):
    m = {'title': 'title', 'content': 'content', 'icon': 'icon', 'coverImage': 'cover', 'isPublished': 'published', 'parentId': 'parent', 'isArchived': 'archived'}
    sets, vals = [], []
    for k, col in m.items():
        if k in payload:
            v = payload[k]
            if col in ('published', 'archived'): v = 1 if v else 0
            sets.append(f'{col}=?'); vals.append(v)
    if not sets: return
    with connect() as c: c.execute(f'UPDATE docs SET {", ".join(sets)}, updated=? WHERE id=?', (*vals, time.time(), i))


def _tree_all(c, i):
    out = [i]
    for r in c.execute('SELECT id FROM docs WHERE parent=?', (i,)).fetchall(): out += _tree_all(c, r['id'])
    return out


def archive(i, on=True):
    with connect() as c:
        ids = _tree_all(c, i)
        c.executemany('UPDATE docs SET archived=?, updated=? WHERE id=?', [(1 if on else 0, time.time(), x) for x in ids])
        if not on:
            r = c.execute('SELECT parent FROM docs WHERE id=?', (i,)).fetchone()
            if r and r['parent']:
                p = c.execute('SELECT archived FROM docs WHERE id=?', (r['parent'],)).fetchone()
                if p and p['archived']: c.execute('UPDATE docs SET parent=NULL WHERE id=?', (i,))


def remove(i):
    with connect() as c:
        for x in _tree_all(c, i):
            c.execute('DELETE FROM docs WHERE id=?', (x,))
            for d in c.execute('SELECT id FROM dbs WHERE parent=?', (x,)).fetchall():
                c.execute('DELETE FROM docs WHERE db=?', (d['id'],)); c.execute('DELETE FROM dbs WHERE id=?', (d['id'],))


# ───────────────────────── extras (pages_ext.py) ─────────────────────────
def meta_get(i):
    with connect() as c:
        r = c.execute('SELECT * FROM page_meta WHERE id=?', (i,)).fetchone()
        d = dict(r) if r else {'id': i, 'fav': 0, 'locked': 0, 'font': 'default', 'small': 0, 'toc': 0, 'visited': None}
        doc = c.execute('SELECT title, content, updated, created FROM docs WHERE id=?', (i,)).fetchone()
        if doc:
            d['updated'], d['created'] = doc['updated'], doc['created']
            d['words'] = words(doc['content'])
            d['comments'] = c.execute('SELECT COUNT(*) FROM page_comments WHERE doc=? AND done=0', (i,)).fetchone()[0]
    if doc:
        try: d['versions'] = direct([('SELECT COUNT(*) FROM page_versions WHERE doc=?', (i,))])[0].rows[0][0]
        except Exception: d['versions'] = 0
    return d


def meta_set(i, payload):
    allowed = {'fav', 'locked', 'font', 'small', 'toc'}
    vals = {k: v for k, v in (payload or {}).items() if k in allowed}
    if not vals: return meta_get(i)
    if vals.get('font') not in (None, 'default', 'serif', 'mono'): vals['font'] = 'default'
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO page_meta (id) VALUES (?)', (i,))
        if vals.get('fav'): vals['fav_order'] = time.time()
        for k, v in vals.items():
            c.execute(f'UPDATE page_meta SET {k}=? WHERE id=?', (int(v) if isinstance(v, bool) else v, i))
    return meta_get(i)


def visit(i):
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO page_meta (id) VALUES (?)', (i,))
        c.execute('UPDATE page_meta SET visited=? WHERE id=?', (time.time(), i))


def side():
    with connect() as c:
        q = '''SELECT d.id, d.title, d.icon FROM page_meta m JOIN docs d ON d.id=m.id WHERE d.archived=0 AND {} ORDER BY {} LIMIT {}'''
        fav = [dict(r) for r in c.execute(q.format('m.fav=1', 'm.fav_order', 50))]
        rec = [dict(r) for r in c.execute(q.format('m.visited IS NOT NULL', 'm.visited DESC', 6))]
    return {'favorites': fav, 'recents': rec}


def comments(i):
    with connect() as c: return [dict(r) for r in c.execute('SELECT * FROM page_comments WHERE doc=? ORDER BY ts', (i,))]


def comment_add(i, text):
    text = (text or '').strip()[:4000]
    if not text: return comments(i)
    with connect() as c: c.execute('INSERT INTO page_comments (doc, text, ts) VALUES (?,?,?)', (i, text, time.time()))
    return comments(i)


def comment_set(cid, done):
    with connect() as c: c.execute('UPDATE page_comments SET done=? WHERE id=?', (1 if done else 0, cid))


def comment_del(cid):
    with connect() as c: c.execute('DELETE FROM page_comments WHERE id=?', (cid,))


def _text(blocks):
    out = []
    for b in blocks or []:
        if not isinstance(b, dict): continue
        cont = b.get('content')
        if isinstance(cont, str): out.append(cont)
        elif isinstance(cont, list):
            for x in cont:
                if isinstance(x, dict): out.append(x.get('text') or '' if x.get('type') != 'link' else ' '.join(y.get('text', '') for y in x.get('content') or []))
                elif isinstance(x, str): out.append(x)
        elif isinstance(cont, dict) and cont.get('type') == 'tableContent':
            for row in cont.get('rows') or []:
                for cell in row.get('cells') or []:
                    cell = cell.get('content') if isinstance(cell, dict) else cell
                    for x in cell or []:
                        if isinstance(x, dict): out.append(x.get('text') or '')
        out.append(_text(b.get('children')))
    return ' '.join(t for t in out if t)


def words(content):
    try: blocks = json.loads(content or '[]')
    except ValueError: return 0
    return len(re.findall(r'\w+', _text(blocks)))


def snapshot(i, label='', force=False):
    """Keep the page as it is now (called before its text changes) — in page_versions, straight in the database."""
    with connect() as c:
        d = c.execute('SELECT title, icon, content FROM docs WHERE id=?', (i,)).fetchone()
    if not d or not d['content']: return
    last = direct([('SELECT content, ts FROM page_versions WHERE doc=? ORDER BY ts DESC LIMIT 1', (i,))])[0].dicts()
    last = last[0] if last else None
    if last and last['content'] == d['content']: return
    if last and not force and time.time() - last['ts'] < SNAP_EVERY: return
    direct([('INSERT INTO page_versions (doc, title, icon, content, words, ts, label) VALUES (?,?,?,?,?,?,?)',
             (i, d['title'], d['icon'], d['content'], words(d['content']), time.time(), label)),
            ('DELETE FROM page_versions WHERE doc=? AND id NOT IN (SELECT id FROM page_versions WHERE doc=? ORDER BY ts DESC LIMIT ?)', (i, i, KEEP))])


def version_label(vid, label): direct([('UPDATE page_versions SET label=? WHERE id=?', ((label or '')[:120], vid))])


def versions(i): return direct([('SELECT id, title, icon, words, ts, label FROM page_versions WHERE doc=? ORDER BY ts DESC', (i,))])[0].dicts()


def version_get(vid):
    r = direct([('SELECT * FROM page_versions WHERE id=?', (vid,))])[0].dicts()
    return r[0] if r else None


def version_restore(vid):
    v = version_get(vid)
    if not v: raise ValueError('That version is gone.')
    snapshot(v['doc'], 'Before restoring', force=True)
    _update(v['doc'], {'content': v['content'], 'title': v['title'], 'icon': v['icon']})
    return v['doc']


def _tree(c, i):
    out = [i]
    for r in c.execute('SELECT id FROM docs WHERE parent=? AND db IS NULL', (i,)).fetchall(): out += _tree(c, r['id'])
    return out


def duplicate(i):
    t = time.time(); new = lambda: uuid.uuid4().hex[:16]
    with connect() as c:
        pages = _tree(c, i)
        pmap = {p: new() for p in pages}
        dbs = [r for r in c.execute(f'SELECT * FROM dbs WHERE parent IN ({",".join("?" * len(pages))})', pages)]
        dmap = {d['id']: new() for d in dbs}
        rows = []
        for d in dbs: rows += c.execute('SELECT * FROM docs WHERE db=?', (d['id'],)).fetchall()
        rmap = {r['id']: new() for r in rows}

        def remap_text(s):
            if not s: return s
            for old, nw in list(dmap.items()) + list(pmap.items()) + list(rmap.items()): s = s.replace(old, nw)
            return s

        for p in pages:
            r = c.execute('SELECT * FROM docs WHERE id=?', (p,)).fetchone()
            title = r['title'] if p != i else (r['title'] or 'Untitled') + ' (copy)'
            c.execute('INSERT INTO docs (id, title, content, icon, cover, parent, archived, published, created, updated) VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (pmap[p], title, remap_text(r['content']), r['icon'], r['cover'], pmap.get(r['parent'], r['parent']), r['archived'], 0, t, t))
        for d in dbs:
            props = json.loads(d['props'] or '[]')
            for pr in props:
                rel = pr.get('relation') or {}
                if rel.get('db') in dmap: rel['db'] = dmap[rel['db']]
            c.execute('INSERT INTO dbs (id, title, icon, props, views, parent, created, updated) VALUES (?,?,?,?,?,?,?,?)',
                      (dmap[d['id']], d['title'], d['icon'], json.dumps(props), d['views'], pmap.get(d['parent'], d['parent']), t, t))
        for r in rows:
            props = json.loads(r['props'] or '{}')
            for k, v in props.items():
                if isinstance(v, list): props[k] = [rmap.get(x, x) if isinstance(x, str) else x for x in v]
            c.execute('INSERT INTO docs (id, title, content, icon, cover, parent, archived, published, created, updated, db, props, sort) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (rmap[r['id']], r['title'], remap_text(r['content']), r['icon'], r['cover'], None, 0, 0, r['created'], t, dmap[r['db']], json.dumps(props), r['sort']))
        return pmap[i]


def move(i, parent):
    parent = parent or None
    with connect() as c:
        if parent and parent in _tree(c, i): raise ValueError('A page cannot go inside itself.')
        c.execute('UPDATE docs SET parent=?, updated=? WHERE id=?', (parent, time.time(), i))


def targets():
    with connect() as c:
        rows = {r['id']: dict(r) for r in c.execute('SELECT id, title, icon, parent FROM docs WHERE db IS NULL AND archived=0')}
    def path(r, seen=()):
        p = rows.get(r['parent'])
        return (path(p, seen + (r['id'],)) + ' / ' if p and p['id'] not in seen else '') + (r['title'] or 'Untitled')
    return sorted(({'id': r['id'], 'title': r['title'] or 'Untitled', 'icon': r['icon'], 'path': path(r)} for r in rows.values()), key=lambda x: x['path'].lower())


# ───────────────────────── files, link previews, publish ─────────────────────────
def upload(name, data_url, replace):
    head, _, b64 = (data_url or '').partition(',')
    raw = base64.b64decode(b64)
    if len(raw) > 3 * 1024 * 1024: raise ValueError('On the web a picture or file can be at most 3 MB.')
    ext = (re.search(r'\.\w{1,6}$', name or '') or [''])[0].lower() or '.' + ((re.search(r'image/(\w+)', head) or ['', 'bin'])[1])
    fid = uuid.uuid4().hex[:12] + ext
    mime = (re.search(r'data:([^;]+)', head) or [None, None])[1] or mimetypes.guess_type(fid)[0] or 'application/octet-stream'
    stmts = [('INSERT INTO files (id, name, mime, data, size, created) VALUES (?,?,?,?,?,?)', (fid, name or fid, mime, raw, len(raw), time.time()))]
    m = re.search(r'/api/file/([\w.-]+)', replace or '')
    if m: stmts.append(('DELETE FROM files WHERE id=?', (m.group(1),)))
    direct(stmts)
    return {'url': f'/api/file/{fid}'}


def file_get(fid):
    r = direct([('SELECT mime, data FROM files WHERE id=?', (fid,))])[0].rows
    return (r[0][0], r[0][1]) if r else (None, None)


def fetch_meta(url):
    import urllib.request
    from urllib.parse import urljoin
    out = {'url': url, 'title': '', 'description': '', 'image': ''}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=6) as r:
            h = r.read(400000).decode(r.headers.get_content_charset() or 'utf-8', 'replace'); final = r.geturl()
        def meta(*names):
            for n in names:
                m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % re.escape(n), h, re.I) or \
                    re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(n), h, re.I)
                if m: return html.unescape(m.group(1)).strip()
            return ''
        t = re.search(r'<title[^>]*>(.*?)</title>', h, re.I | re.S)
        out['title'] = meta('og:title', 'twitter:title') or (html.unescape(t.group(1)).strip() if t else '') or url
        out['description'] = meta('og:description', 'description', 'twitter:description')[:300]
        img = meta('og:image', 'twitter:image'); out['image'] = urljoin(final, img) if img else ''
    except Exception:
        out['title'] = url
    return out


def publish(i, body_html, keep):
    d = get_doc(i) or {}
    slug = (re.sub(r'[^\w-]+', '-', (d.get('title') or 'page').lower()).strip('-')[:60] or 'page') + '-' + i[:6]
    cover = f'<div class="cover" style="background-image:url(\'{html.escape(d["coverImage"])}\')"></div>' if d.get('coverImage') else ''
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(d.get("title") or "Page")}</title><style>
body{{margin:0;font-family:Inter,"Segoe UI",system-ui,sans-serif;color:#1f1f1f;background:#fff}}
.cover{{height:34vh;background:#eee center/cover no-repeat}} main{{max-width:760px;margin:0 auto;padding:40px 24px 120px}}
.icon{{font-size:64px;margin-top:-20px}} h1.t{{font-size:44px;margin:10px 0 24px}} img{{max-width:100%;border-radius:6px}}
blockquote{{border-left:3px solid #ddd;margin:0;padding-left:14px;color:#555}} pre{{background:#f6f6f6;padding:12px;border-radius:6px;overflow:auto}}
table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:6px 10px}} .made{{color:#999;font-size:12px;margin-top:60px}}
@media (prefers-color-scheme:dark){{body{{background:#191919;color:#eee}} .cover{{background-color:#333}}}}
</style></head><body>{cover}<main><div class="icon">{html.escape(d.get("icon") or "")}</div><h1 class="t">{html.escape(d.get("title") or "")}</h1>
{body_html or ""}<div class="made">Made with Curio Pages</div></main></body></html>'''
    direct([('DELETE FROM published WHERE doc=?', (i,)), ('INSERT INTO published (slug, doc, html, updated) VALUES (?,?,?,?)', (slug, i, page, time.time()))])
    return {'path': f'/p/{slug}'}


def published(slug):
    r = direct([('SELECT html FROM published WHERE slug=?', (slug,))])[0].rows
    return r[0][0] if r else None


def unpublish(i): direct([('DELETE FROM published WHERE doc=?', (i,))])


def make_zip(name, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files or []: z.writestr(str(f.get('path') or 'page.md').lstrip('/'), f.get('text') or '')
    return {'name': name if name.endswith('.zip') else name + '.zip', 'b64': base64.b64encode(buf.getvalue()).decode()}


# ───────────────────────── the two channel objects ─────────────────────────
def _calendar_add(dbid):
    raise ValueError('Calendar is coming to Curio Web soon — on the desktop app it works already.')


def _snap_rpc(fn):
    return lambda *a: run(fn, *a)


CURIO = {
    'info': lambda: {'user': USER['name']},
    'list': _snap_rpc(list_docs), 'get': _snap_rpc(get_doc),
    'create': _snap_rpc(lambda parent, title: {'id': create(parent or None, title or 'Untitled')}),
    'update': _snap_rpc(lambda i, payload: update(i, json.loads(payload or '{}')) or {}),
    'archive': _snap_rpc(lambda i, on: archive(i, bool(on)) or {}),
    'remove': _snap_rpc(lambda i: remove(i) or {}),
    'db_list': _snap_rpc(db_list), 'db_create': _snap_rpc(lambda parent, payload: db_create(parent or None, json.loads(payload or '{}'))),
    'db_get': _snap_rpc(db_get), 'db_update': _snap_rpc(lambda i, payload: db_update(i, json.loads(payload or '{}')) or {}),
    'db_remove': _snap_rpc(lambda i: db_remove(i) or {}),
    'row_create': _snap_rpc(lambda dbid, payload: row_create(dbid, json.loads(payload or '{}'))),
    'row_update': _snap_rpc(lambda i, payload: row_update(i, json.loads(payload or '{}')) or {}),
    'row_delete': _snap_rpc(lambda i: row_delete(i) or {}),
    'fetch_meta': fetch_meta, 'upload': upload,
    'publish': _snap_rpc(publish),
    'notion': lambda i, md: (_ for _ in ()).throw(ValueError('Copying to Notion works from the desktop app.')),
}

EXT = {
    'meta': _snap_rpc(meta_get), 'meta_set': _snap_rpc(lambda i, payload: meta_set(i, json.loads(payload or '{}'))),
    'visit': _snap_rpc(lambda i: visit(i) or {}), 'side': _snap_rpc(side),
    'versions': versions, 'version': version_get, 'restore': _snap_rpc(lambda vid: {'id': version_restore(vid)}),
    'snapshot': _snap_rpc(lambda i, label: snapshot(i, label, True) or {}),
    'duplicate': _snap_rpc(lambda i: {'id': duplicate(i)}), 'move': _snap_rpc(lambda i, parent: move(i, parent) or {}),
    'targets': _snap_rpc(targets), 'version_label': lambda vid, label: version_label(vid, label) or {},
    'comments': _snap_rpc(comments), 'comment_add': _snap_rpc(comment_add),
    'comment_set': _snap_rpc(lambda cid, done: comment_set(cid, done) or {}), 'comment_del': _snap_rpc(lambda cid: comment_del(cid) or {}),
    'make_zip': lambda name, files: make_zip(name, json.loads(files or '[]')),
    'calendar_add': _calendar_add,
    'notion_import': lambda payload: __import__('notion_import').build(json.loads(payload or '{}')),
}


def rpc(obj, method, args):
    """→ JSON text, like a desktop slot (errors as {"error": "..."})."""
    table = CURIO if obj == 'curio' else EXT if obj == 'curioext' else None
    f = table.get(method) if table else None
    try:
        if f is None: raise ValueError(f'Pages on the web cannot do “{method}” yet.')
        return json.dumps(f(*args), ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)[:300]})
