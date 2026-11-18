"""The database for Curio Web.

Remote: a Turso (libSQL) database reached over its HTTP API (stdlib only — no native packages on Vercel).
Local: a plain SQLite file, used when TURSO_DATABASE_URL is not set (development and tests).

Two ways to use it:
  • remote().run([(sql, args), ...])          — a few statements in one round trip (big tables like page_versions, files)
  • Snapshot('finance', TABLES).run(fn)       — the whole set of tables is copied into an in-memory SQLite once per
    warm server and reused while nothing changed (a revision number tells). `fn(con)` runs on that copy with the
    desktop app's own code; every statement that changed something is replayed on the real database in ONE
    transaction, guarded by the revision so two tabs can never overwrite each other.
"""
import base64, json, os, sqlite3, threading, urllib.request, urllib.error

WRITE_WORDS = ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP')


# ───────────────────────── values ─────────────────────────
def _arg(v):
    if v is None: return {'type': 'null'}
    if isinstance(v, bool): return {'type': 'integer', 'value': str(int(v))}
    if isinstance(v, int): return {'type': 'integer', 'value': str(v)}
    if isinstance(v, float): return {'type': 'float', 'value': v}
    if isinstance(v, (bytes, bytearray, memoryview)): return {'type': 'blob', 'base64': base64.b64encode(bytes(v)).decode()}
    return {'type': 'text', 'value': str(v)}


def _val(c):
    t = c.get('type')
    if t == 'null': return None
    if t == 'integer': return int(c['value'])
    if t == 'float': return float(c['value'])
    if t == 'blob': return base64.b64decode(c.get('base64') or '')
    return c.get('value')


class Result:
    def __init__(self, cols, rows, last_id=None, changes=0):
        self.cols, self.rows, self.last_id, self.changes = cols, rows, last_id, changes

    def dicts(self): return [dict(zip(self.cols, r)) for r in self.rows]


# ───────────────────────── remote (Turso over HTTP) ─────────────────────────
class TursoError(RuntimeError): pass


class Turso:
    def __init__(self, url, token):
        url = url.strip()
        if url.startswith('libsql://'): url = 'https://' + url[len('libsql://'):]
        self.url = url.rstrip('/'); self.token = token.strip()

    def _post(self, body, base=None):
        req = urllib.request.Request((base or self.url) + '/v2/pipeline', data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=25) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise TursoError(f'database answered {e.code}: {e.read()[:300].decode(errors="replace")}')

    @staticmethod
    def _results(out):
        res = []
        for r in out.get('results', []):
            if r.get('type') == 'error': raise TursoError(r.get('error', {}).get('message', 'database error'))
            resp = r.get('response', {})
            if resp.get('type') != 'execute': continue
            x = resp['result']
            res.append(Result([c.get('name') for c in x.get('cols', [])], [[_val(c) for c in row] for row in x.get('rows', [])],
                              int(x['last_insert_rowid']) if x.get('last_insert_rowid') not in (None, '') else None, x.get('affected_row_count', 0)))
        return res

    def run(self, stmts, transaction=False):
        """[(sql, args)] → [Result]. With transaction=True they all apply or none does."""
        stmts = [(s, a) for s, a in stmts]
        if transaction: stmts = [('BEGIN', ())] + stmts + [('COMMIT', ())]
        reqs = [{'type': 'execute', 'stmt': {'sql': s, 'args': [_arg(v) for v in (a or ())]}} for s, a in stmts] + [{'type': 'close'}]
        res = self._results(self._post({'requests': reqs}))
        return res[1:-1] if transaction else res

    def guarded(self, check_sql, check_args, stmts):
        """BEGIN; run the check (must change exactly one row) — only then the rest; COMMIT. Returns False when the check
        failed (somebody else changed the data first) and nothing was written."""
        first = self._post({'requests': [{'type': 'execute', 'stmt': {'sql': 'PRAGMA foreign_keys = ON'}}, {'type': 'execute', 'stmt': {'sql': 'BEGIN'}},
                                         {'type': 'execute', 'stmt': {'sql': check_sql, 'args': [_arg(v) for v in check_args]}}]})
        baton, base = first.get('baton'), first.get('base_url')
        res = self._results(first)
        if res[2].changes != 1:
            self._post({'baton': baton, 'requests': [{'type': 'execute', 'stmt': {'sql': 'ROLLBACK'}}, {'type': 'close'}]}, base)
            return False
        reqs = [{'type': 'execute', 'stmt': {'sql': s, 'args': [_arg(v) for v in (a or ())]}} for s, a in stmts]
        reqs += [{'type': 'execute', 'stmt': {'sql': 'COMMIT'}}, {'type': 'close'}]
        try: self._results(self._post({'baton': baton, 'requests': reqs}, base))
        except Exception:
            try: self._post({'baton': baton, 'requests': [{'type': 'execute', 'stmt': {'sql': 'ROLLBACK'}}, {'type': 'close'}]}, base)
            except Exception: pass
            raise
        return True


# ───────────────────────── local (SQLite file) ─────────────────────────
class Local:
    """Same interface as Turso, on a file — for running Curio Web on your own PC and for tests."""
    _lock = threading.Lock()

    def __init__(self, path):
        self.path = path; os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _con(self):
        c = sqlite3.connect(self.path, isolation_level=None, timeout=20); return c

    def _exec(self, c, s, a):
        cur = c.execute(s, tuple(a or ()))
        cols = [d[0] for d in cur.description] if cur.description else []
        return Result(cols, [list(r) for r in cur.fetchall()] if cols else [], cur.lastrowid, cur.rowcount if cur.rowcount > 0 else 0)

    def run(self, stmts, transaction=False):
        with self._lock:
            c = self._con()
            try:
                if transaction: c.execute('BEGIN')
                out = [self._exec(c, s, a) for s, a in stmts]
                if transaction: c.execute('COMMIT')
                return out
            except Exception:
                if transaction:
                    try: c.execute('ROLLBACK')
                    except Exception: pass
                raise
            finally: c.close()

    def guarded(self, check_sql, check_args, stmts):
        with self._lock:
            c = self._con()
            try:
                c.execute('PRAGMA foreign_keys = ON'); c.execute('BEGIN')
                if c.execute(check_sql, tuple(check_args)).rowcount != 1: c.execute('ROLLBACK'); return False
                for s, a in stmts: c.execute(s, tuple(a or ()))
                c.execute('COMMIT'); return True
            except Exception:
                try: c.execute('ROLLBACK')
                except Exception: pass
                raise
            finally: c.close()


_REMOTE = None


def remote():
    global _REMOTE
    if _REMOTE is None:
        url = os.environ.get('TURSO_DATABASE_URL') or os.environ.get('LIBSQL_URL') or os.environ.get('TURSO_URL')
        tok = os.environ.get('TURSO_AUTH_TOKEN') or os.environ.get('LIBSQL_AUTH_TOKEN') or os.environ.get('TURSO_TOKEN') or ''
        # no Turso yet: a scratch file (on Vercel only /tmp can be written, and it is wiped often — connect Turso!)
        scratch = os.path.join('/tmp' if os.environ.get('VERCEL') else os.getcwd(), '.data', 'curio-web.db')
        _REMOTE = Turso(url, tok) if url else Local(os.environ.get('CURIO_LOCAL_DB', scratch))
    return _REMOTE


def rows(sql, args=()):
    return remote().run([(sql, args)])[0].dicts()


# ───────────────────────── snapshots ─────────────────────────
class Conflict(Exception): pass


class Snapshot:
    """A set of tables, copied into memory, kept in step with the real database by a revision number."""

    def __init__(self, name, tables):
        self.name, self.tables = name, list(tables)
        self.con, self.rev = None, None; self.lock = threading.RLock()

    # revision table, shared by every snapshot
    @staticmethod
    def _ensure_rev(r):
        r.run([('CREATE TABLE IF NOT EXISTS _rev (name TEXT PRIMARY KEY, rev INTEGER NOT NULL)', ())])

    def _remote_rev(self, r):
        try: res = r.run([('SELECT rev FROM _rev WHERE name=?', (self.name,))])[0]
        except Exception:
            self._ensure_rev(r); res = r.run([('SELECT rev FROM _rev WHERE name=?', (self.name,))])[0]
        return res.rows[0][0] if res.rows else 0

    def _load(self, r):
        """One round trip: the schema, the AUTOINCREMENT counters and every row of our tables."""
        names = ','.join("'%s'" % t for t in self.tables)
        head = r.run([("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL AND tbl_name IN (%s) ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END" % names, ()),
                       ('SELECT rev FROM _rev WHERE name=?', (self.name,))])
        schema = head[0].dicts(); rev = head[1].rows[0][0] if head[1].rows else 0
        present = [s['name'] for s in schema if s['type'] == 'table']
        stmts = [(f'SELECT * FROM "{t}"', ()) for t in present]
        has_seq = bool(r.run([("SELECT name FROM sqlite_master WHERE name='sqlite_sequence'", ())])[0].rows)
        if has_seq: stmts.append(('SELECT name, seq FROM sqlite_sequence WHERE name IN (%s)' % names, ()))
        data = r.run(stmts) if stmts else []
        con = sqlite3.connect(':memory:', check_same_thread=False); con.row_factory = sqlite3.Row
        for s in schema: con.execute(s['sql'])
        for t, res in zip(present, data):
            if res.rows:
                con.executemany(f'INSERT INTO "{t}" ({",".join(chr(34) + c + chr(34) for c in res.cols)}) VALUES ({",".join("?" * len(res.cols))})', res.rows)
        if has_seq and data:
            seq = data[-1]
            if seq.rows:
                con.execute('CREATE TABLE IF NOT EXISTS _seq_probe (id INTEGER PRIMARY KEY AUTOINCREMENT)')   # makes sqlite_sequence exist
                con.execute('DROP TABLE _seq_probe')
                for n, s in seq.rows:
                    con.execute('DELETE FROM sqlite_sequence WHERE name=?', (n,)); con.execute('INSERT INTO sqlite_sequence (name, seq) VALUES (?,?)', (n, s))
        con.commit(); self.con, self.rev = con, rev

    def _fresh(self, r):
        rev = self._remote_rev(r)
        if self.con is None or rev != self.rev: self._load(r)

    def drop(self): self.con, self.rev = None, None

    def run(self, fn, tries=2):
        """fn(con) on the in-memory copy; its changes go to the real database; returns fn's result."""
        r = remote()
        with self.lock:
            for attempt in range(tries):
                self._fresh(r); con = self.con; log = []
                before = (con.total_changes, con.execute('PRAGMA schema_version').fetchone()[0])
                con.set_trace_callback(log.append)
                try:
                    out = fn(con); con.commit()
                except Exception:
                    self.drop(); raise
                finally:
                    try: con.set_trace_callback(None)
                    except Exception: pass
                after = (con.total_changes, con.execute('PRAGMA schema_version').fetchone()[0])
                writes = [s for s in log if s.lstrip().split(None, 1)[0].upper() in WRITE_WORDS] if after != before else []
                if not writes: return out
                new = self.rev + 1
                if self.rev == 0:                                         # first write ever: make sure our row exists
                    r.run([('INSERT OR IGNORE INTO _rev (name, rev) VALUES (?, 0)', (self.name,))])
                ok = r.guarded('UPDATE _rev SET rev=? WHERE name=? AND rev=?', (new, self.name, self.rev), [(s, ()) for s in writes])
                if ok: self.rev = new; return out
                self.drop()                                               # someone else wrote first: reload and do it again
            raise Conflict('The data changed in another tab — please try again.')

    def read(self, fn):
        return self.run(fn)
