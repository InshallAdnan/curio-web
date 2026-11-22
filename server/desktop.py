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
        names = [n for n in tracker.NAMES if n != 'activity']
        data = tracker.run(lambda c: _dump(c._c, [tracker.PFX + n for n in names]))
        body = {'ok': True, 'part': 'tracker', 'rev': rev['tracker'], 'tables': {k[len(tracker.PFX):]: v for k, v in data.items()}}
    else:
        raise ValueError('part must be finance, pages or tracker')
    return gzip.compress(json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 6)

