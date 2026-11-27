"""Curio Desktop ⇐ Curio Web. The web is the original; the desktop app copies it when you press "Update from web".

You make a desktop key here (Settings › Connect desktop) and paste it into the desktop app once. The key can only READ:
  GET /api/desktop/status          → how much is here and a change number per part (cheap; the desktop checks it at start)
  GET /api/desktop/pull?part=…     → every row of Finance ('finance'), Pages ('pages') or Tracker ('tracker'), gzip'd JSON
  (pictures come from the existing GET /api/file/<id>)
Only a SHA-256 of each key is kept (table desktop_keys); the key itself is shown once. Revoke it any time."""
import base64, gzip, hashlib, json, re, secrets, time

import tdb, fin, pages, tracker

PREFIX = 'cdk_'
_READY = [False]


def _db(stmts):
    r = tdb.remote()
    if not _READY[0]:
        r.run([('CREATE TABLE IF NOT EXISTS desktop_keys (id TEXT PRIMARY KEY, hash TEXT NOT NULL, name TEXT, created REAL, last_used REAL)', ())])
        _READY[0] = True
    return r.run(stmts)


def _hash(key): return hashlib.sha256(key.encode()).hexdigest()


# ───────────────────────── signed-in side (Settings card) ─────────────────────────
def keys(a=None):
    return _db([('SELECT id, name, created, last_used FROM desktop_keys ORDER BY created DESC', ())])[0].dicts()


def create(a):
    name = (str((a or {}).get('name') or '').strip() or 'Desktop')[:40]
    key = PREFIX + secrets.token_urlsafe(32); kid = secrets.token_hex(6)
    _db([('INSERT INTO desktop_keys (id, hash, name, created, last_used) VALUES (?,?,?,?,NULL)', (kid, _hash(key), name, time.time()))])
    return {'id': kid, 'name': name, 'key': key}                      # the only time the key itself is ever shown


def revoke(a):
    _db([('DELETE FROM desktop_keys WHERE id=?', (str(a['id']),))]); return True


OPS = {'keys': keys, 'create': create, 'revoke': revoke}


def call(op, args):
    if op not in OPS: raise ValueError('unknown op')
    return OPS[op](args or {})


# ───────────────────────── desktop side (key in the Authorization header) ─────────────────────────
def check(env):
    """→ True when the request carries a live desktop key."""
    auth = env.get('HTTP_AUTHORIZATION') or ''
    key = auth[7:].strip() if auth.lower().startswith('bearer ') else ''
    if not key.startswith(PREFIX) or len(key) > 120: return False
    rows = _db([('SELECT id FROM desktop_keys WHERE hash=?', (_hash(key),))])[0].rows
    if not rows: return False
    try: _db([('UPDATE desktop_keys SET last_used=? WHERE id=?', (time.time(), rows[0][0]))])
    except Exception: pass
    return True


def _revs():
    try: res = tdb.remote().run([("SELECT name, rev FROM _rev WHERE name IN ('finance','pages','tracker')", ())])[0].rows
    except Exception: res = []
    out = {'finance': 0, 'pages': 0, 'tracker': 0}; out.update({n: r for n, r in res}); return out


def _dump(con, tables):
    """every row of these tables, as {table: {cols, rows}}; bytes travel as {"$b": base64}"""
    out = {}
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in tables:
        if t not in have: continue
        cur = con.execute(f'SELECT * FROM "{t}"'); cols = [d[0] for d in cur.description]
        out[t] = {'cols': cols, 'rows': [[{'$b': base64.b64encode(bytes(v)).decode()} if isinstance(v, (bytes, bytearray, memoryview)) else v
                                          for v in row] for row in cur.fetchall()]}
    return out


FILE_RE = re.compile(r'/api/file/([\w.-]+)')


def status():
    def f(con):
        n = lambda t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        return {'transactions': n('transactions'), 'transfers': n('transfers'), 'accounts': n('accounts')}
    def p():
        c = pages._CON[0]
        return {'pages': c.execute('SELECT COUNT(*) FROM docs WHERE db IS NULL AND archived=0').fetchone()[0],
                'rows': c.execute('SELECT COUNT(*) FROM docs WHERE db IS NOT NULL AND archived=0').fetchone()[0],
                'databases': c.execute('SELECT COUNT(*) FROM dbs').fetchone()[0],
                'last_edit': c.execute('SELECT MAX(updated) FROM docs').fetchone()[0]}
    counts = fin.run(f); counts.update(pages.run(p))
    try: counts.update({'tracker_' + k: v for k, v in tracker.call('stats', {}).items()})
    except Exception: pass
    return {'ok': True, 'app': 'Curio Web', 'version': 1, 'rev': _revs(), 'counts': counts, 'time': time.time()}


def pull(part):
    rev = _revs()
    if part == 'finance':
        data = fin.run(lambda con: _dump(con, fin.TABLES))
        try: cfg = json.loads(next((r[1] for r in data.get('settings', {}).get('rows', []) if r[0] == 'calendar_cfg'), '') or '{}')
        except (ValueError, IndexError, TypeError): cfg = {}
        body = {'ok': True, 'part': 'finance', 'rev': rev['finance'], 'tables': data, 'calendar_cfg': cfg}
    elif part == 'pages':
        data = pages.run(lambda: _dump(pages._CON[0], pages.TABLES))
        used = set()
        for t in ('docs', 'dbs'):
            for row in data.get(t, {}).get('rows', []):
                for v in row:
                    if isinstance(v, str) and '/api/file/' in v: used.update(FILE_RE.findall(v))
        files = []
        if used:
            ids = sorted(used)
            for i in range(0, len(ids), 80):                        # short IN (…) lists: Turso's expression depth limit
                chunk = ids[i:i + 80]
                files += pages.direct([('SELECT id, name, mime, size FROM files WHERE id IN (%s)' % ','.join('?' * len(chunk)), tuple(chunk))])[0].dicts()
        body = {'ok': True, 'part': 'pages', 'rev': rev['pages'], 'tables': data, 'files': files}
    elif part == 'tracker':
        # the Tracker book, table names as on the desktop (without md_); the screen record (activity) stays on each PC
        names = [n for n in tracker.NAMES if n not in ('activity', 'ai_chat')]    # the PC keeps its own screen record and its own AI chat
        data = tracker.run(lambda c: _dump(c._c, [tracker.PFX + n for n in names]))
        body = {'ok': True, 'part': 'tracker', 'rev': rev['tracker'], 'tables': {k[len(tracker.PFX):]: v for k, v in data.items()}}
    else:
        raise ValueError('part must be finance, pages or tracker')
    try:                                                                # 10.52: the next new ids, so both sides number new rows alike
        names = list(body['tables'].keys()); real = [tracker.PFX + n for n in names] if part == 'tracker' else names
        rows = tdb.remote().run([('SELECT name, seq FROM sqlite_sequence WHERE name IN (%s)' % ','.join('?' * len(real)), tuple(real))])[0].rows if real else []
        body['seq'] = {(n[len(tracker.PFX):] if part == 'tracker' else n): q for n, q in rows}
    except Exception: body['seq'] = {}
    return gzip.compress(json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 6)



# ───────────────────────── 10.52: live sync — the desktop sends its changes (two-way, no button) ─────────────────────────
PUSH_TABLES = {
    'finance': set(fin.TABLES),
    'pages': set(pages.TABLES),
    'tracker': {n for n in tracker.NAMES if n not in ('activity', 'ai_chat')},
}
_STMT = re.compile(r'^\s*(INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO|UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM)\s+"?(\w+)"?', re.I)
LOCAL_FILE = re.compile(r'file:///[^"\'\s)\\]*?/pages/files/([\w.-]+)')


def _clean(part, sql):
    """only plain row changes on this part's own tables; the PC's picture links go back to /api/file/<id>"""
    m = _STMT.match(sql or '')
    if not m or m.group(2).lower() not in {t.lower() for t in PUSH_TABLES[part]}: return None
    if part == 'pages': sql = LOCAL_FILE.sub(lambda x: '/api/file/' + x.group(1), sql)
    if part == 'tracker': sql = tracker.sql(sql)
    return sql


def push(a):
    """{part, base, stmts:[sql…]} → written on the web in one go. When the web changed in between (base is old) the
    changes still go in on top (last change wins) and the answer says clean=False, so the desktop takes the web's copy."""
    part = a.get('part')
    if part not in PUSH_TABLES: raise ValueError('part must be finance, pages or tracker')
    raw = a.get('stmts') or []
    if len(raw) > 2000: raise ValueError('too many changes in one go')
    stmts = [(s, ()) for s in (_clean(part, x) for x in raw) if s]
    base = int(a.get('base') or 0); r = tdb.remote()
    tdb.Snapshot._ensure_rev(r); r.run([('INSERT OR IGNORE INTO _rev (name, rev) VALUES (?, 0)', (part,))])
    if not stmts: return {'rev': _revs()[part], 'clean': True, 'n': 0}
    for _ in range(4):
        cur = _revs()[part]
        if r.guarded('UPDATE _rev SET rev=? WHERE name=? AND rev=?', (cur + 1, part, cur), stmts):
            return {'rev': cur + 1, 'clean': cur == base, 'n': len(stmts)}
    raise tdb.Conflict('The web was busy — the desktop will send again in a moment.')


def lib_save(a):
    """the desktop sends one collection item online (its files are already on R2): same row as a web save"""
    import library
    return library.save(a)


def lib_board(a):
    """make sure a board (collection) with this name exists on the web → its id; and put these items in it"""
    import library
    name = str(a.get('name') or '').strip()[:80]
    if not name: raise ValueError('name')
    got = library._db([('SELECT id FROM lib_boards WHERE name=? AND parent IS NULL', (name,))])[0].rows
    bid = got[0][0] if got else library._db([('INSERT INTO lib_boards (name, parent, color, created, pos) VALUES (?,?,?,?,0)', (name, None, a.get('color'), time.time()))])[0].last_id
    items = [(str(x.get('platform')), str(x.get('item_id'))) for x in (a.get('items') or [])][:2000]
    if items: library._db([('INSERT OR IGNORE INTO lib_board_items (board, platform, item_id, added) VALUES (?,?,?,?)', (bid, p, i, time.time())) for p, i in items])
    return {'id': bid}


KEY_OPS = {'push': push, 'lib_save': lib_save, 'lib_board': lib_board}


def key_call(op, args):
    """calls made with the desktop key (POST /api/desktop/do)"""
    import r2
    if op in KEY_OPS: return KEY_OPS[op](args or {})
    if op == 'file_start': return r2.start(args or {})
    if op == 'file_done': return r2.done(args or {}, origin='desktop')
    if op == 'file_has': return r2.has((args or {}).get('ids') or [])
    if op == 'where': return where()
    raise ValueError('unknown op')


def where():
    """10.52: Settings › Where your data lives — every place Curio keeps something online"""
    import os, r2
    db = tdb.remote(); turso = isinstance(db, tdb.Turso)
    host = re.sub(r'^https?://', '', db.url) if turso else 'this computer (test mode)'
    out = {'app': {'name': 'Vercel', 'what': 'The app itself (screens, buttons, the server code)', 'where': os.environ.get('VERCEL_URL') or 'curio-web',
                   'region': os.environ.get('VERCEL_REGION') or 'bom1 (Mumbai)'},
           'database': {'name': 'Turso', 'what': 'All your data: Tasks / Tracker, Docs, Finance, Calendar, Library list, phone reminders',
                        'where': host, 'parts': _revs()},
           'files': {'name': 'Cloudflare R2', 'what': 'Big files: pictures, videos, Notion files, collections sent online',
                     **{k: v for k, v in r2.status().items() if k in ('on', 'worker', 'worker_ok', 'r2_files', 'r2_bytes', 'db_files', 'db_bytes')}},
           'clock': {'name': 'Cloudflare Worker (Cron)', 'what': 'Wakes Curio Web every minute for phone reminders'}}
    try:
        import push
        st = push.status(); out['clock'].update({'last_tick': st.get('last_tick'), 'ago': st.get('ago'), 'phones': st.get('phones'), 'kinds': st.get('kinds')})
    except Exception: pass
    return out
