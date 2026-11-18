"""One-time move of the desktop data into Curio Web.

The browser opens finance.db / pages.db itself (sql.js) and sends the tables here in small batches, so nothing passes
through anyone else and big files never hit the request size limit. Pictures of Pages (data/pages/files/*) can be sent too.
  begin  {domain, schema:[{type,name,sql}]}  → replaces that part of the web data with empty tables of the desktop's shape
  rows   {table, cols, rows}                 → adds rows
  file   {name, b64, mime}                   → one picture
  end    {domain}                            → links pictures, tells every server to reload"""
import base64, json, mimetypes, re, time

import tdb, fin, pages

DOMAINS = {'finance': (fin.TABLES, fin.BOOK), 'pages': (pages.TABLES, pages.BOOK)}


def _bump(name):
    tdb.remote().run([('CREATE TABLE IF NOT EXISTS _rev (name TEXT PRIMARY KEY, rev INTEGER NOT NULL)', ()),
                      ('INSERT INTO _rev (name, rev) VALUES (?, 1) ON CONFLICT(name) DO UPDATE SET rev = rev + 1', (name,))])


def handle(step, b, only_if_empty=False):
    r = tdb.remote()
    if step == 'begin':
        tables, book = DOMAINS[b['domain']]
        if only_if_empty:
            probe = 'accounts' if b['domain'] == 'finance' else 'docs'
            try: n = r.run([(f'SELECT COUNT(*) FROM "{probe}"', ())])[0].rows[0][0]
            except Exception: n = 0
            if n: return {'error': 'There is already data here — sign in to replace it.'}
        schema = [s for s in b.get('schema') or [] if s.get('sql') and s.get('tbl_name', s.get('name')) in tables]
        if not any(s['type'] == 'table' for s in schema): return {'error': 'This file does not look like a Curio ' + b['domain'] + ' database.'}
        stmts = [('PRAGMA foreign_keys = OFF', ())] + [(f'DROP TABLE IF EXISTS "{t}"', ()) for t in reversed(tables)]
        stmts += [(s['sql'], ()) for s in sorted(schema, key=lambda s: 0 if s['type'] == 'table' else 1)]
        r.run(stmts); book.drop(); _bump(b['domain'])
        return {'ok': True, 'tables': [s['name'] for s in schema if s['type'] == 'table']}
    if step == 'rows':
        t = b['table']
        if not any(t in v[0] for v in DOMAINS.values()): return {'error': 'unknown table ' + t}
        cols = b['cols']; sql = f'INSERT OR REPLACE INTO "{t}" ({",".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({",".join("?" * len(cols))})'
        rows = [[base64.b64decode(v['$b']) if isinstance(v, dict) and '$b' in v else v for v in row] for row in b['rows']]
        r.run([(sql, row) for row in rows], transaction=True)
        return {'ok': True, 'n': len(rows)}
    if step == 'file':
        name = re.sub(r'[^\w.-]', '_', b['name'])[:80]; raw = base64.b64decode(b['b64'])
        pages.direct([('INSERT OR REPLACE INTO files (id, name, mime, data, size, created) VALUES (?,?,?,?,?,?)',
                       (name, b['name'], b.get('mime') or mimetypes.guess_type(name)[0] or 'application/octet-stream', raw, len(raw), time.time()))])
        return {'ok': True}
    if step == 'end':
        if b['domain'] == 'pages':
            # pictures were file:///…/pages/files/<name> on the PC — on the web they are /api/file/<name>
            def fix(c):
                pat = re.compile(r'file:///[^"\')\s]*?/pages/files/([\w.-]+)')
                n = 0
                for row in c.execute("SELECT id, content, cover FROM docs WHERE content LIKE '%/pages/files/%' OR cover LIKE '%/pages/files/%'").fetchall():
                    c.execute('UPDATE docs SET content=?, cover=? WHERE id=?', (pat.sub(r'/api/file/\1', row['content'] or '') or row['content'],
                                                                                pat.sub(r'/api/file/\1', row['cover'] or '') or row['cover'], row['id'])); n += 1
                for row in c.execute("SELECT id, props FROM docs WHERE props LIKE '%/pages/files/%'").fetchall():
                    c.execute('UPDATE docs SET props=? WHERE id=?', (pat.sub(r'/api/file/\1', row['props']), row['id']))
                return n
            n = pages.run(lambda: fix(pages._CON[0]))
            return {'ok': True, 'fixed': n}
        fin.run(lambda con: True)                                    # adds any column the web needs (title / time) and checks it opens
        return {'ok': True}
    return {'error': 'unknown step'}
