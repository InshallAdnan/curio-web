"""Curio Web — Notion's "Export › Markdown & CSV" (the .zip) becomes Docs pages, the way they were in Notion.

The browser opens the zip, uploads the pictures (and small videos) one by one, then sends the text here:
  pages  {file name: markdown}       one .md per Notion page (database rows too)
  csvs   {file name: csv text}       one per database ("…_all.csv" has every column)
  files  {file name: /api/file/…}    what was uploaded
  skipped [file name …]              too big for Curio Web for now
Everything goes under one new page "Notion import — <date>"; nothing that already exists is changed.

Notion's file names end with a 32-letter id ("My Journal 22-24 b4740e41….csv"). Links between pages use those names, so the
same tree comes back: a page's sub-pages become its sub-pages, a database inside a page becomes a table in that page, and each
row of a database becomes a row page (its properties as columns, its text and pictures inside)."""
import csv, io, json, re, time, uuid
from datetime import datetime
from urllib.parse import unquote

import pages as PG

PAR = r'((?:[^()\s]|\([^()\s]*\))+)'                      # a link target, allowing (1) inside
HEX = re.compile(r'\s+([0-9a-f]{32})(?:_all)?(\.(?:md|csv))$', re.I)
DATE_FMTS = ('%B %d, %Y %I:%M %p', '%B %d, %Y', '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%dT%H:%M')
VIDEO = ('.mp4', '.mov', '.webm', '.m4v', '.mkv')
AUDIO = ('.mp3', '.m4a', '.wav', '.ogg')
COLORS = ['blue', 'green', 'orange', 'purple', 'pink', 'yellow', 'red', 'brown', 'gray']


def _u(): return uuid.uuid4().hex[:8]


def base(name):
    """'Folder/My Page 0a41….md' → ('My Page', '0a41…')"""
    n = name.replace('\\', '/').split('/')[-1]
    m = HEX.search(n)
    if m: return n[:m.start()].strip(), m.group(1).lower()
    return re.sub(r'(_all)?\.(md|csv)$', '', n, flags=re.I).strip(), ''


def parse_date(s):
    s = (s or '').strip()
    if not s: return None
    s1 = re.sub(r'\s*\(.*?\)\s*$', '', s).split(' → ')[0].strip()
    for f in DATE_FMTS:
        try:
            d = datetime.strptime(s1, f)
            return {'start': d.strftime('%Y-%m-%dT%H:%M') if ('%H' in f or '%I' in f) else d.strftime('%Y-%m-%d')}
        except ValueError: continue
    return None


def _epoch(d):
    """Notion writes times in your own time zone (Karachi): read them so, whatever the server's clock zone is"""
    import os
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(os.environ.get('CURIO_TZ', 'Asia/Karachi'))
    try:
        dt = datetime.strptime(d['start'][:16], '%Y-%m-%dT%H:%M') if 'T' in d['start'] else datetime.strptime(d['start'][:10], '%Y-%m-%d')
        return dt.replace(tzinfo=tz).timestamp()
    except Exception: return None


# ───────── markdown → Docs blocks ─────────
INLINE = re.compile(r'(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|__(.+?)__|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)|`([^`]+)`|~~(.+?)~~|\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\))')


def inline(text, links=None):
    """markdown inline text → BlockNote inline content"""
    out, pos = [], 0
    def txt(s, **st):
        if s: out.append({'type': 'text', 'text': s, 'styles': st})
    for m in INLINE.finditer(text or ''):
        txt(text[pos:m.start()])
        if m.group(2): txt(m.group(2), bold=True, italic=True)
        elif m.group(3): txt(m.group(3), bold=True)
        elif m.group(4): txt(m.group(4), bold=True)
        elif m.group(5): txt(m.group(5), italic=True)
        elif m.group(6): txt(m.group(6), italic=True)
        elif m.group(7): txt(m.group(7), code=True)
        elif m.group(8): txt(m.group(8), strike=True)
        elif m.group(9):
            href = m.group(10).strip()
            if links is not None and not re.match(r'^[a-z]+:', href):
                target = links(href)
                if target: href = target
            if re.match(r'^(https?:|mailto:|#)', href): out.append({'type': 'link', 'href': href, 'content': [{'type': 'text', 'text': m.group(9), 'styles': {}}]})
            else: txt(m.group(9))
        pos = m.end()
    txt(text[pos:])
    return out


class Ctx:
    def __init__(self, files, page_ids, db_ids, skipped):
        self.files, self.page_ids, self.db_ids, self.skipped = files, page_ids, db_ids, set(skipped or [])
        self.used_pages, self.used_dbs = set(), set()

    def file(self, ref):
        n = unquote(ref).replace('\\', '/').split('/')[-1]
        return self.files.get(n) or self.files.get(unquote(ref)), n

    def page_link(self, ref):
        n = unquote(ref).split('/')[-1]
        return '#/documents/' + self.page_ids[n] if n in self.page_ids else None


def md_blocks(md, ctx, skip_title=True, skip_props=0):
    lines = (md or '').replace('\r\n', '\n').split('\n')
    i = 0
    if skip_title and lines and lines[0].startswith('# '): i = 1
    while i < len(lines) and not lines[i].strip(): i += 1
    i += skip_props
    blocks, para = [], []
    stack = []                                                     # (indent, block) for nested lists

    def flush():
        if para:
            text = ' '.join(x.strip() for x in para).strip(); para.clear()
            if text: add({'type': 'paragraph', 'content': inline(text, ctx.page_link)}, 0)

    def add(b, indent):
        b.setdefault('children', [])
        while stack and stack[-1][0] >= indent: stack.pop()
        if indent > 0 and stack: stack[-1][1]['children'].append(b)
        else: blocks.append(b)
        if b['type'] in ('bulletListItem', 'numberedListItem', 'checkListItem', 'toggleListItem'): stack.append((indent, b))
        else: stack.clear()

    while i < len(lines):
        raw = lines[i]; line = raw.rstrip(); s = line.strip(); indent = len(raw.replace('\t', '    ')) - len(raw.replace('\t', '    ').lstrip())
        if not s: flush(); stack.clear(); i += 1; continue
        if s.startswith('```'):
            flush(); lang = s[3:].strip(); code = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'): code.append(lines[i]); i += 1
            add({'type': 'codeBlock', 'props': {'language': lang or 'text'}, 'content': [{'type': 'text', 'text': '\n'.join(code), 'styles': {}}]}, 0); i += 1; continue
        if s.lower().startswith('<aside'):
            flush(); body = []; i += 1
            while i < len(lines) and '</aside>' not in lines[i].lower(): body.append(lines[i]); i += 1
            txt = re.sub(r'<img[^>]*>', '', '\n'.join(body)); txt = re.sub(r'<[^>]+>', '', txt)
            txt = ' '.join(x.strip() for x in txt.split('\n') if x.strip() and x.strip() != '**')
            add({'type': 'callout', 'props': {'emoji': '💡', 'backgroundColor': 'gray'}, 'content': inline(txt, ctx.page_link)}, 0); i += 1; continue
        if re.fullmatch(r'(-{3,}|\*{3,}|_{3,})', s): flush(); add({'type': 'divider'}, 0); i += 1; continue
        m = re.match(r'^(#{1,6})\s+(.*)$', s)
        if m: flush(); add({'type': 'heading', 'props': {'level': min(3, len(m.group(1)))}, 'content': inline(m.group(2), ctx.page_link)}, 0); i += 1; continue
        m = re.fullmatch(r'!\[([^\]]*)\]\(' + PAR + r'\)', s)
        if m:
            flush(); url, name = ctx.file(m.group(2)); low = name.lower()
            if url: add({'type': 'video' if low.endswith(VIDEO) else 'audio' if low.endswith(AUDIO) else 'image', 'props': {'url': url, 'name': name, 'caption': ''}}, 0)
            elif re.match(r'^https?:', m.group(2)): add({'type': 'image', 'props': {'url': m.group(2), 'caption': m.group(1)}}, 0)
            else: add({'type': 'paragraph', 'content': [{'type': 'text', 'text': f'📎 {name} — not imported (too big for Curio Web for now)', 'styles': {'italic': True}}]}, 0)
            i += 1; continue
        m = re.fullmatch(r'\[([^\]]+)\]\(' + PAR + r'\)', s)               # a link alone on its line: a sub-page or a database
        if m and not re.match(r'^[a-z]+:', m.group(2)):
            flush(); n = unquote(m.group(2)).split('/')[-1]
            if n.lower().endswith('.csv'):
                key = re.sub(r'(_all)?\.csv$', '', n, flags=re.I)
                if key in ctx.db_ids: add({'type': 'database', 'props': {'dbId': ctx.db_ids[key]}}, 0); ctx.used_dbs.add(key); i += 1; continue
            elif n in ctx.page_ids:
                add({'type': 'pageLink', 'props': {'docId': ctx.page_ids[n]}}, 0); ctx.used_pages.add(n); i += 1; continue
            else:
                url, nm = ctx.file(m.group(2)); low = nm.lower()
                if url:
                    kind = 'video' if low.endswith(VIDEO) else 'audio' if low.endswith(AUDIO) else 'image' if low.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) else 'file'
                    add({'type': kind, 'props': {'url': url, 'name': nm, **({'caption': ''} if kind != 'file' else {})}}, 0); i += 1; continue
        m = re.match(r'^[-*+]\s+\[([ xX])\]\s+(.*)$', s)
        if m: flush(); add({'type': 'checkListItem', 'props': {'checked': m.group(1).lower() == 'x'}, 'content': inline(m.group(2), ctx.page_link)}, indent); i += 1; continue
        m = re.match(r'^[-*+]\s+(.*)$', s)
        if m: flush(); add({'type': 'bulletListItem', 'content': inline(m.group(1), ctx.page_link)}, indent); i += 1; continue
        m = re.match(r'^\d+[.)]\s+(.*)$', s)
        if m: flush(); add({'type': 'numberedListItem', 'content': inline(m.group(1), ctx.page_link)}, indent); i += 1; continue
        if s.startswith('>'):
            flush(); add({'type': 'quote', 'content': inline(s.lstrip('> ').strip(), ctx.page_link)}, 0); i += 1; continue
        if s.startswith('|') and i + 1 < len(lines) and re.fullmatch(r'\|?\s*:?-{2,}.*', lines[i + 1].strip()):
            flush(); rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                if not re.fullmatch(r'\|?[\s:|-]+\|?', lines[i].strip()):
                    rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            n = max(len(r) for r in rows)
            add({'type': 'table', 'content': {'type': 'tableContent', 'rows': [{'cells': [inline(c, ctx.page_link) for c in r + [''] * (n - len(r))]} for r in rows]}}, 0)
            continue
        if re.fullmatch(r'<[^>]+>', s): i += 1; continue                  # stray html
        para.append(s); i += 1
        if line.endswith('  '): flush()
    flush()
    return blocks or [{'type': 'paragraph'}]


def prop_lines(md):
    """'Key: value' lines right under the title of a row page → ({key: value}, how many lines)"""
    lines = (md or '').replace('\r\n', '\n').split('\n'); i = 1 if lines and lines[0].startswith('# ') else 0
    while i < len(lines) and not lines[i].strip(): i += 1
    props, n = {}, 0
    while i + n < len(lines):
        m = re.match(r'^([^:\n]{1,40}):\s?(.*)$', lines[i + n])
        if not m or not lines[i + n].strip(): break
        props[m.group(1).strip()] = m.group(2).strip(); n += 1
    return props, n


# ───────── databases ─────────
def guess_props(header, rows):
    out = []
    for j, name in enumerate(header):
        vals = [r[j] for r in rows if j < len(r) and r[j].strip()]
        if j == 0: out.append({'id': 'title', 'name': name or 'Name', 'type': 'title'}); continue
        pid = 'p' + _u()
        low = name.lower()
        if low in ('created time', 'created', 'created date', 'created on'):
            out.append({'id': pid, 'name': name, 'type': 'date', 'date': {'time': True}, '_kind': 'date'}); continue
        if vals and all(parse_date(v) for v in vals):
            out.append({'id': pid, 'name': name, 'type': 'date', '_kind': 'date'}); continue
        if vals and all(v.strip().lower() in ('yes', 'no') for v in vals):
            out.append({'id': pid, 'name': name, 'type': 'checkbox', '_kind': 'check'}); continue
        if vals and all(re.fullmatch(r'-?\d+(\.\d+)?', v.strip()) for v in vals):
            out.append({'id': pid, 'name': name, 'type': 'number', 'number': {'format': 'number'}, '_kind': 'num'}); continue
        parts = [p.strip() for v in vals for p in v.split(',')]
        multi = any(',' in v for v in vals) and len(set(parts)) <= max(12, len(vals) // 2)
        distinct = sorted(set(parts if multi else [v.strip() for v in vals]))
        if vals and (multi or ('select' in low or low in ('type', 'status', 'tags', 'category', 'contain'))) and len(distinct) <= 40 and all(len(x) < 60 for x in distinct):
            opts = [{'id': 'o' + _u(), 'name': d, 'color': COLORS[k % len(COLORS)]} for k, d in enumerate(distinct)]
            out.append({'id': pid, 'name': name, 'type': 'multi_select' if multi else 'select', 'options': opts, '_kind': 'multi' if multi else 'select'}); continue
        out.append({'id': pid, 'name': name, 'type': 'text', '_kind': 'text'})
    return out


def cell(p, v):
    v = (v or '').strip(); k = p.get('_kind')
    if not v: return None
    if k == 'date': return parse_date(v)
    if k == 'check': return v.lower() == 'yes'
    if k == 'num':
        try: return float(v) if '.' in v else int(v)
        except ValueError: return None
    if k == 'select': return next((o['id'] for o in p['options'] if o['name'] == v), None)
    if k == 'multi': return [o['id'] for o in p['options'] if o['name'] in [x.strip() for x in v.split(',')]]
    return v


def read_csv(text):
    text = (text or '').lstrip('﻿')
    rows = list(csv.reader(io.StringIO(text)))
    return (rows[0], rows[1:]) if rows else ([], [])


# ───────── the whole import ─────────
def build(payload):
    pages, csvs = payload.get('pages') or {}, payload.get('csvs') or {}
    files, skipped = payload.get('files') or {}, payload.get('skipped') or []
    stamp = datetime.now().strftime('%d %b %Y, %H:%M')

    def go():
        root = PG.create(payload.get('parent') or None, (payload.get('title') or '').strip()[:120] or f'Notion import — {stamp}', None, payload.get('icon') or '📥')
        # databases: one per Notion table (the "_all" file has every column)
        dbfiles = {}
        for n in csvs:
            key = re.sub(r'(_all)?\.csv$', '', n.split('/')[-1], flags=re.I)
            if n.lower().endswith('_all.csv') or key not in dbfiles: dbfiles[key] = n
        page_ids = {n.split('/')[-1]: uuid.uuid4().hex[:16] for n in pages}
        db_ids = {key: None for key in dbfiles}
        # which page is a row of which database: same title (+ same created date when there is one)
        by_title = {}
        for n, md in pages.items():                                   # 10.53: the page's own title (# …) — file names lose "/" and such
            h1 = next((l[2:].strip() for l in md.splitlines()[:3] if l.startswith('# ')), '') or base(n)[0]
            for t in {h1.strip().lower(), base(n)[0].strip().lower()}: by_title.setdefault(t, []).append(n.split('/')[-1])
        rows_of, taken = {}, set()
        dbs = {}
        for key, n in dbfiles.items():
            header, rows = read_csv(csvs[n])
            if not header: continue
            props = guess_props(header, rows); dbs[key] = (header, rows, props)
            for r in rows:
                if not r: continue
                cands = [c for c in by_title.get((r[0] or 'Untitled').strip().lower(), []) if c not in taken]
                if len(cands) > 1:
                    want = {v.strip() for v in r[1:] if v.strip()}
                    best = max(cands, key=lambda c: len(want & set(prop_lines(pages[[k for k in pages if k.split('/')[-1] == c][0]])[0].values())))
                    cands = [best]
                if cands: taken.add(cands[0]); rows_of.setdefault(key, []).append((r, cands[0]))
                else: rows_of.setdefault(key, []).append((r, None))
        full = {n.split('/')[-1]: n for n in pages}
        # create the databases (parent fixed below)
        for key, (header, rows, props) in dbs.items():
            clean = [{k: v for k, v in p.items() if not k.startswith('_')} for p in props]
            views = [{'id': _u(), 'name': 'Table', 'type': 'table'}, {'id': _u(), 'name': 'List', 'type': 'list'}]
            date_p = next((p for p in props if p.get('_kind') == 'date'), None)
            if date_p: views[0]['sorts'] = [{'prop': date_p['id'], 'dir': 'desc'}]; views.append({'id': _u(), 'name': 'Calendar', 'type': 'calendar', 'dateProp': date_p['id']})
            db_ids[key] = PG.db_create(root, {'title': base(key + '.csv')[0], 'icon': '🗂️', 'props': clean, 'views': views})['id']
        ctx = Ctx(files, {}, db_ids, skipped)
        # rows (+ their pages' text and pictures)
        nrows = 0
        for key, items in rows_of.items():
            header, rows, props = dbs[key]
            for r, fname in items:
                vals = {}
                for j, p in enumerate(props[1:], 1):
                    if j < len(r):
                        v = cell(p, r[j])
                        if v is not None: vals[p['id']] = v
                row = PG.row_create(db_ids[key], {'title': (r[0] or '').strip(), 'props': vals})
                nrows += 1
                if fname: page_ids[fname] = row['id']
                created = next((vals[p['id']] for p in props if p.get('_kind') == 'date' and p['name'].lower().startswith('created') and p['id'] in vals), None)
                if created and _epoch(created):
                    with PG.connect() as c: c.execute('UPDATE docs SET created=?, sort=? WHERE id=?', (_epoch(created), _epoch(created), row['id']))
        ctx.page_ids = page_ids
        rowpages = {f for items in rows_of.values() for _, f in items if f}
        for key, items in rows_of.items():
            for r, fname in items:
                if not fname: continue
                md = pages[full[fname]]; _, n = prop_lines(md)
                blocks = md_blocks(md, ctx, True, n)
                PG._update(page_ids[fname], {'content': json.dumps(blocks)})
        # normal pages: made under the page that links to them (else under the import page)
        parent_of = {}
        for n, md in pages.items():
            me = n.split('/')[-1]
            for ref in [x for x in re.findall(r'\]\(' + PAR + r'\)', md) if x.lower().endswith('.md')]:
                child = unquote(ref).split('/')[-1]
                if child != me and child in page_ids and child not in rowpages and child not in parent_of: parent_of[child] = me
        db_parent = {}
        for n, md in pages.items():
            for ref in [x for x in re.findall(r'\]\(' + PAR + r'\)', md) if x.lower().endswith('.csv')]:
                key = re.sub(r'(_all)?\.csv$', '', unquote(ref).split('/')[-1], flags=re.I)
                if key in db_ids and key not in db_parent: db_parent[key] = n.split('/')[-1]
        def empty(me):                                                # 10.53: an empty "Untitled" page (Notion templates, blank rows' leftovers) is left out
            md = pages[full[me]]; _, k = prop_lines(md)
            body = [l for l in md.splitlines()[1:] if l.strip()][k:]
            return not body and (base(me)[0] or 'Untitled').strip().lower() == 'untitled'
        order, seen = [], set()
        def visit(p):
            if p in seen: return
            seen.add(p)
            if p in parent_of: visit(parent_of[p])
            order.append(p)
        for n in pages:
            me = n.split('/')[-1]
            if me not in rowpages: visit(me)
        npages = 0
        for me in order:
            md = pages[full[me]]; title = base(me)[0] or 'Untitled'
            par = parent_of.get(me); pid = page_ids[par] if par in page_ids else root
            if par in rowpages: pid = page_ids[par]
            with PG.connect() as c:
                c.execute('INSERT INTO docs (id, title, content, icon, cover, parent, created, updated) VALUES (?,?,?,?,?,?,?,?)',
                          (page_ids[me], title, None, None, None, pid, time.time(), time.time()))
            npages += 1
        for me in order:
            PG._update(page_ids[me], {'content': json.dumps(md_blocks(pages[full[me]], ctx, True, 0))})
        for key, pg in db_parent.items():
            if pg in page_ids: PG.db_update(db_ids[key], {'parent': page_ids[pg]})
        # the import page: links to the top pages, and the tables no page showed
        top = [me for me in order if me not in parent_of]
        content = [{'type': 'paragraph', 'content': [{'type': 'text', 'text': f'Imported from Notion on {stamp}: {npages} pages, {len(db_ids)} tables, {nrows} rows.', 'styles': {}}]}]
        content += [{'type': 'pageLink', 'props': {'docId': page_ids[me]}} for me in top]
        content += [{'type': 'database', 'props': {'dbId': db_ids[k]}} for k in db_ids if k not in db_parent]
        if skipped:
            content.append({'type': 'paragraph', 'content': [{'type': 'text', 'text': f'Not imported yet (too big for Curio Web): {", ".join(skipped[:30])}' + (' …' if len(skipped) > 30 else ''), 'styles': {'italic': True}}]})
        PG._update(root, {'content': json.dumps(content)})
        return {'id': root, 'pages': npages, 'tables': len(db_ids), 'rows': nrows, 'skipped': len(skipped)}
    return PG.run(go)
