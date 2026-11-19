"""Library for Curio Web — the Moodboard (your saved posts, pins and videos) and My Boards.

On the web only small copies are kept: every picture is shrunk in the browser (longest side ~1200 px, JPEG) and a video
keeps one still frame, so a few hundred saves fit easily in the free database. The full files stay on your PC; each
save keeps its link to the original post. Nothing here talks to Instagram / Pinterest / YouTube."""
import hashlib, json, time

import tdb

_READY = [False]
PLATFORMS = ('instagram', 'pinterest', 'youtube', 'facebook', 'behance', 'x', 'web', 'upload')


def _db(stmts, transaction=False):
    r = tdb.remote()
    if not _READY[0]:
        r.run([('''CREATE TABLE IF NOT EXISTS lib_items (platform TEXT NOT NULL, item_id TEXT NOT NULL, url TEXT, category TEXT, title TEXT,
                   caption TEXT, published TEXT, author TEXT, media TEXT, bytes INTEGER DEFAULT 0, added REAL, note TEXT DEFAULT '',
                   PRIMARY KEY(platform, item_id))''', ()),
               ('CREATE INDEX IF NOT EXISTS lib_items_added ON lib_items(added)', ()),
               ('''CREATE TABLE IF NOT EXISTS lib_boards (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent INTEGER, color TEXT,
                   created REAL, pos INTEGER DEFAULT 0)''', ()),
               ('''CREATE TABLE IF NOT EXISTS lib_board_items (board INTEGER NOT NULL, platform TEXT NOT NULL, item_id TEXT NOT NULL, added REAL,
                   PRIMARY KEY(board, platform, item_id))''', ()),
               ('CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, name TEXT, mime TEXT, data BLOB, size INTEGER, created REAL)', ())])
        _READY[0] = True
    return r.run(stmts, transaction=transaction)


def _row(d):
    try: d['media'] = json.loads(d.get('media') or '[]')
    except ValueError: d['media'] = []
    return d


def items(a):
    q = (a.get('q') or '').strip(); plat = a.get('platform') or ''; cat = a.get('category') or ''; board = a.get('board')
    sql = ('SELECT i.platform, i.item_id, i.url, i.category, i.title, i.caption, i.published, i.author, i.media, i.added, i.note '
           'FROM lib_items i')
    args = []
    if board: sql += ' JOIN lib_board_items b ON b.platform=i.platform AND b.item_id=i.item_id AND b.board=?'; args.append(int(board))
    sql += ' WHERE 1=1'
    if plat: sql += ' AND i.platform=?'; args.append(plat)
    if cat: sql += ' AND i.category=?'; args.append(cat)
    if q:
        sql += ' AND (i.title LIKE ? OR i.caption LIKE ? OR i.category LIKE ? OR i.author LIKE ? OR i.note LIKE ?)'; args += [f'%{q}%'] * 5
    sql += ' ORDER BY i.added DESC LIMIT ? OFFSET ?'; args += [min(int(a.get('limit') or 120), 400), int(a.get('offset') or 0)]
    rows = [_row(d) for d in _db([(sql, args)])[0].dicts()]
    return rows


def facets(a=None):
    r = _db([('SELECT platform, COUNT(*) AS n FROM lib_items GROUP BY platform ORDER BY n DESC', ()),
             ("SELECT category, COUNT(*) AS n FROM lib_items WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY n DESC", ()),
             ("SELECT COUNT(*), COALESCE(SUM(bytes),0) FROM lib_items", ()),
             ('SELECT b.id, b.name, b.parent, b.color, b.pos, (SELECT COUNT(*) FROM lib_board_items x WHERE x.board=b.id) AS n FROM lib_boards b ORDER BY b.pos, b.id', ())])
    total, size = r[2].rows[0]
    return {'platforms': r[0].dicts(), 'categories': r[1].dicts(), 'total': total, 'bytes': size, 'boards': r[3].dicts()}


def known(a):
    """which of these (platform, item_id) are already here — the importer skips them"""
    keys = a.get('keys') or []
    if not keys: return []
    out = set()
    for i in range(0, len(keys), 200):
        part = keys[i:i + 200]
        sql = 'SELECT platform, item_id FROM lib_items WHERE ' + ' OR '.join(['(platform=? AND item_id=?)'] * len(part))
        out |= {f'{p}:{k}' for p, k in _db([(sql, [v for pk in part for v in pk])])[0].rows}
    return sorted(out)


def put_file(a):
    """one shrunk picture (base64 JPEG/PNG/WebP) → its id; same bytes → same id"""
    import base64
    raw = base64.b64decode(a['b64'])
    if len(raw) > 3_000_000: raise ValueError('That picture is still bigger than 3 MB after shrinking.')
    fid = 'lib_' + hashlib.sha1(raw).hexdigest()[:20] + {'image/png': '.png', 'image/webp': '.webp'}.get(a.get('mime'), '.jpg')
    _db([('INSERT OR IGNORE INTO files (id, name, mime, data, size, created) VALUES (?,?,?,?,?,?)',
          (fid, (a.get('name') or fid)[:120], a.get('mime') or 'image/jpeg', raw, len(raw), time.time()))])
    return {'id': fid, 'size': len(raw)}


def save(a):
    """add or update one save: {platform, item_id, url, category, title, caption, published, author, media:[{file, kind, w, h, poster}]}"""
    plat = (a.get('platform') or 'upload').lower()
    if plat not in PLATFORMS: plat = 'web'
    iid = str(a.get('item_id') or hashlib.sha1(f'{a.get("url")}{time.time()}'.encode()).hexdigest()[:16])
    media = [m for m in (a.get('media') or []) if isinstance(m, dict) and m.get('file')]
    fids = [m['file'] for m in media]
    size = 0
    if fids:
        size = _db([('SELECT COALESCE(SUM(size),0) FROM files WHERE id IN (%s)' % ','.join('?' * len(fids)), fids)])[0].rows[0][0]
    _db([('''INSERT INTO lib_items (platform, item_id, url, category, title, caption, published, author, media, bytes, added)
             VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(platform, item_id) DO UPDATE SET url=excluded.url, category=excluded.category,
             title=excluded.title, caption=excluded.caption, published=excluded.published, author=excluded.author, media=excluded.media,
             bytes=excluded.bytes''',
          (plat, iid, a.get('url') or '', (a.get('category') or '')[:120], (a.get('title') or '')[:300], (a.get('caption') or '')[:6000],
           a.get('published') or '', (a.get('author') or '')[:120], json.dumps(media), size, float(a.get('added') or time.time())))])
    return {'platform': plat, 'item_id': iid}


def note(a):
    _db([('UPDATE lib_items SET note=? WHERE platform=? AND item_id=?', ((a.get('note') or '')[:4000], a['platform'], a['item_id']))]); return True


def remove(a):
    """removes the save from Curio Web only (your PC copy is not touched); its pictures go when nothing else uses them"""
    rows = _db([('SELECT media FROM lib_items WHERE platform=? AND item_id=?', (a['platform'], a['item_id']))])[0].rows
    if not rows: return True
    fids = [m.get('file') for m in json.loads(rows[0][0] or '[]') if m.get('file')]
    st = [('DELETE FROM lib_items WHERE platform=? AND item_id=?', (a['platform'], a['item_id'])),
          ('DELETE FROM lib_board_items WHERE platform=? AND item_id=?', (a['platform'], a['item_id']))]
    _db(st, transaction=True)
    for f in fids:
        used = _db([('SELECT COUNT(*) FROM lib_items WHERE media LIKE ?', (f'%{f}%',))])[0].rows[0][0]
        if not used: _db([('DELETE FROM files WHERE id=?', (f,))])
    return True


# ── My Boards ──
def board_save(a):
    if a.get('id'):
        _db([('UPDATE lib_boards SET name=?, color=? WHERE id=?', ((a.get('name') or 'Board')[:80], a.get('color') or '#f2602d', int(a['id'])))]); return int(a['id'])
    r = _db([('INSERT INTO lib_boards (name, parent, color, created, pos) VALUES (?,?,?,?,(SELECT COALESCE(MAX(pos),0)+1 FROM lib_boards))',
              ((a.get('name') or 'Board')[:80], a.get('parent'), a.get('color') or '#f2602d', time.time()))])
    return r[0].last_id


def board_delete(a):
    """the board goes; the saves in it stay in the Moodboard"""
    _db([('DELETE FROM lib_board_items WHERE board=?', (int(a['id']),)), ('UPDATE lib_boards SET parent=NULL WHERE parent=?', (int(a['id']),)),
         ('DELETE FROM lib_boards WHERE id=?', (int(a['id']),))], transaction=True); return True


def board_add(a):
    _db([('INSERT OR IGNORE INTO lib_board_items (board, platform, item_id, added) VALUES (?,?,?,?)', (int(a['board']), a['platform'], a['item_id'], time.time()))]); return True


def board_take(a):
    _db([('DELETE FROM lib_board_items WHERE board=? AND platform=? AND item_id=?', (int(a['board']), a['platform'], a['item_id']))]); return True


def item_boards(a):
    return [r[0] for r in _db([('SELECT board FROM lib_board_items WHERE platform=? AND item_id=?', (a['platform'], a['item_id']))])[0].rows]


OPS = {'items': items, 'facets': facets, 'known': known, 'put_file': put_file, 'save': save, 'note': note, 'remove': remove,
       'board_save': board_save, 'board_delete': board_delete, 'board_add': board_add, 'board_take': board_take, 'item_boards': item_boards}


def call(op, args):
    f = OPS.get(op)
    if f is None: raise ValueError(f'Unknown action: {op}')
    return f(args or {})
