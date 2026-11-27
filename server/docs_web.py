"""Curio Web — the Tracker's Inspo inside Docs (same as the desktop's docs_link.py, on the web database).

Docs › Curio Database › Inspo › "Goals" (its own page with the table of every goal and dream, written by the Tracker — one way)
and Inspo › "Inspo cards" (its own page; a card becomes a row when you press "Convert into page"). Each row is a page for more pictures and text.
Nothing is deleted: a goal removed from the Tracker keeps its page, marked "Removed"."""
import json, re, uuid
from datetime import date

import myday as M
import pages as PG
import tracker

CARD_PROPS = [{'id': 'title', 'name': 'Name', 'type': 'title'},
              {'id': 'sec', 'name': 'Section', 'type': 'select', 'options': []},
              {'id': 'kind', 'name': 'Kind', 'type': 'select', 'options': [{'id': 'picture', 'name': 'Picture', 'color': 'blue'}, {'id': 'video', 'name': 'Video', 'color': 'purple'},
                                                                         {'id': 'note', 'name': 'Note', 'color': 'yellow'}, {'id': 'link', 'name': 'Link', 'color': 'gray'}]},
              {'id': 'added', 'name': 'Added', 'type': 'date'}, {'id': 'made', 'name': 'Page made', 'type': 'date'}]
GOAL_PROPS = [{'id': 'title', 'name': 'Name', 'type': 'title'},
              {'id': 'type', 'name': 'Type', 'type': 'select', 'options': [{'id': 'goal', 'name': 'Goal', 'color': 'orange'}, {'id': 'dream', 'name': 'Dream', 'color': 'purple'},
                                                                         {'id': 'removed', 'name': 'Removed', 'color': 'gray'}]},
              {'id': 'why', 'name': 'Why', 'type': 'text'}, {'id': 'year', 'name': 'Year', 'type': 'number', 'number': {'format': 'number'}},
              {'id': 'added', 'name': 'Added', 'type': 'date'}, {'id': 'done_on', 'name': 'Achieved', 'type': 'date'}, {'id': 'done', 'name': 'Done', 'type': 'checkbox'}]
IMG = re.compile(r'"type":\s*"image"\s*,\s*"props":\s*\{[^{}]*?"url":\s*"([^"]+)"')


def _u(): return uuid.uuid4().hex[:8]


def _day(ts): return {'start': ts[:10]} if ts else None


EXTRA = {'top': 'curio_db_page', 'gpage': 'inspo_goals_page', 'cpage': 'inspo_cards_page'}
INTRO = 'Made by Tracker › Inspo. Goals come from the Tracker by themselves; a card is added to the Vision Board when you press “Convert into page”.'


def _ids(c):
    d = dict(root=M.setting(c, 'inspo_page_root') or '', cdb=M.setting(c, 'inspo_cards_db') or '', gdb=M.setting(c, 'inspo_goals_db') or '')
    d.update({k: M.setting(c, v) or '' for k, v in EXTRA.items()}); d['v'] = M.setting(c, 'inspo_docs_v') or ''; return d


def _blocks(doc):
    try: return json.loads((doc or {}).get('content') or '[]') or []
    except Exception: return []


def _has(blocks, typ, key, val):
    return any(isinstance(b, dict) and b.get('type') == typ and (b.get('props') or {}).get(key) == val for b in blocks)


def _ensure(st):
    """inside PG.run → (Inspo page, cards table, goals table). 10.51: every part has its own page —
    Curio Database › Inspo › Goals (its table) and Inspo cards (its table). Moves an older Inspo (both tables on one page) into this."""
    def page(key, parent, title, icon):
        d = PG.get_doc(st.get(key) or '') if st.get(key) else None
        if not d: st[key] = PG.create(parent, title, None, icon); return st[key]
        if parent and d.get('parentId') != parent: PG.move(st[key], parent)
        return st[key]
    top = page('top', None, 'Curio Database', '🗂️')
    root = page('root', top, 'Inspo', '✨')
    gpage = page('gpage', root, 'Goals', '🎯')
    cpage = page('cpage', root, 'Vision Board', '🖼️')
    if (PG.get_doc(cpage) or {}).get('title') == 'Inspo cards': PG.update(cpage, {'title': 'Vision Board'})      # 10.53: its name
    have = {d['id']: d for d in PG.db_list()}
    cdb = st['cdb'] if st['cdb'] in have else PG.db_create(cpage, {'title': 'Vision Board', 'icon': '🖼️', 'props': CARD_PROPS, 'views': [
        {'id': _u(), 'name': 'Gallery', 'type': 'gallery', 'cardSize': 'm'}, {'id': _u(), 'name': 'Table', 'type': 'table', 'sorts': [{'prop': 'added', 'dir': 'desc'}]}]})['id']
    gdb = st['gdb'] if st['gdb'] in have else PG.db_create(gpage, {'title': 'Goals', 'icon': '🎯', 'props': GOAL_PROPS, 'views': [
        {'id': _u(), 'name': 'Table', 'type': 'table', 'sorts': [{'prop': 'added', 'dir': 'desc'}]}, {'id': _u(), 'name': 'Gallery', 'type': 'gallery', 'cardSize': 'm'}]})['id']
    if ((PG.db_get(cdb) or {}).get('db') or {}).get('title') == 'Inspo cards': PG.db_update(cdb, {'title': 'Vision Board'})
    for dbid, pg in ((cdb, cpage), (gdb, gpage)):
        if (PG.db_get(dbid) or {}).get('db', {}).get('parent') != pg: PG.db_update(dbid, {'parent': pg})
        cur = _blocks(PG.get_doc(pg))
        if not _has(cur, 'database', 'dbId', dbid): PG.update(pg, {'content': json.dumps([{'type': 'database', 'props': {'dbId': dbid}}] + (cur or [{'type': 'paragraph'}]))})
    # Inspo: a line + links to its two pages (the tables no longer sit here)
    cur = _blocks(PG.get_doc(root)); keep = [b for b in cur if not (isinstance(b, dict) and b.get('type') == 'database' and (b.get('props') or {}).get('dbId') in (cdb, gdb))]
    if not any(isinstance(b, dict) and b.get('type') == 'paragraph' and 'Made by Tracker' in json.dumps(b.get('content') or '') for b in keep):
        keep = [{'type': 'paragraph', 'content': INTRO}] + keep
    miss = [pid for pid in (gpage, cpage) if not _has(keep, 'pageLink', 'docId', pid)]
    if miss:
        while keep and isinstance(keep[-1], dict) and keep[-1].get('type') == 'paragraph' and not keep[-1].get('content'): keep.pop()
        keep += [{'type': 'pageLink', 'props': {'docId': pid}} for pid in miss] + [{'type': 'paragraph'}]
    if keep != cur: PG.update(root, {'content': json.dumps(keep)})
    cur = _blocks(PG.get_doc(top))
    if not _has(cur, 'pageLink', 'docId', root):
        head = [] if cur else [{'type': 'paragraph', 'content': 'Everything Curio keeps for you, one page each: Inspo (Goals, Vision Board) — more parts come here later.'}]
        PG.update(top, {'content': json.dumps(head + cur + [{'type': 'pageLink', 'props': {'docId': root}}, {'type': 'paragraph'}])})
    return root, cdb, gdb


def _save_ids(c, root, cdb, gdb, ex=None):
    for k, v in (('inspo_page_root', root), ('inspo_cards_db', cdb), ('inspo_goals_db', gdb)): M.set_setting(c, k, v)
    for k, v in (ex or {}).items():
        if k in EXTRA and v: M.set_setting(c, EXTRA[k], v)


def _sig(gs): return json.dumps([(g['id'], g['kind'], g['title'], g['why'], g.get('created'), g.get('done_at'), g.get('due'), g.get('page_id')) for g in gs])


def goal_pages(force=False):
    st = tracker.run(lambda c: dict(gs=M.goals(c, 'goal') + M.goals(c, 'dream'), sig=M.setting(c, 'goal_pages_sig'), **_ids(c)))
    if not force and st['sig'] == _sig(st['gs']) and st.get('top') and st.get('v') == '2': return           # 10.51: once more to give Inspo its own pages

    def go():
        root, cdb, gdb = _ensure(st); rows = {r['id']: r for r in PG.db_get(gdb)['rows']}; got = {}
        for g in st['gs']:
            props = {'type': g['kind'], 'why': g['why'] or '', 'year': M.goal_year(g) if g['kind'] == 'goal' else None,
                     'added': _day(g.get('created')), 'done_on': _day(g.get('done_at')), 'done': bool(g.get('done_at'))}
            pid = g.get('page_id') or ''
            if pid and pid in rows: PG.row_update(pid, {'title': g['title'], 'props': props})
            else: pid = PG.row_create(gdb, {'title': g['title'], 'props': props})['id']
            got[g['id']] = pid
        for rid, r in rows.items():
            if rid not in got.values() and (r.get('props') or {}).get('type') != 'removed': PG.row_update(rid, {'props': {'type': 'removed'}})
        return dict(root=root, cdb=cdb, gdb=gdb, got=got, ex={k: st.get(k) for k in EXTRA})
    res = PG.run(go)

    def back(c):
        _save_ids(c, res['root'], res['cdb'], res['gdb'], res['ex'])
        for gid, pid in res['got'].items(): c.execute('UPDATE goals SET page_id=? WHERE id=?', (pid, gid))
        c.commit(); M.set_setting(c, 'goal_pages_sig', _sig(M.goals(c, 'goal') + M.goals(c, 'dream'))); M.set_setting(c, 'inspo_docs_v', '2')
    tracker.run(back)


def card_page(iid):
    st = tracker.run(lambda c: dict(it=next((x for x in M.inspo_items(c) if x['id'] == iid), None), **_ids(c)))
    it = st['it']
    if not it: raise ValueError('That card is gone.')
    if it.get('page_id'):
        ok = PG.run(lambda: bool(PG.get_doc(it['page_id'])))
        if ok: return dict(page_id=it['page_id'])

    def go():
        root, cdb, gdb = _ensure(st)
        d = PG.db_get(cdb)['db']; props = d['props']; p = next((x for x in props if x['id'] == 'sec'), None); sec = it.get('section') or 'My Inspo'; oid = sec
        if p is not None:
            o = next((x for x in p.get('options') or [] if x['name'] == sec), None)
            if o is None:
                cols = ['orange', 'blue', 'green', 'pink', 'purple', 'yellow', 'red', 'gray', 'brown']
                o = {'id': _u(), 'name': sec, 'color': cols[len(p.get('options') or []) % len(cols)]}; p.setdefault('options', []).append(o); PG.db_update(cdb, {'props': props})
            oid = o['id']
        kind = {'image': 'picture', 'media': 'picture', 'video': 'video', 'quote': 'note', 'link': 'link'}.get(it.get('kind'), 'note')
        r = PG.row_create(cdb, {'title': (it.get('title') or f"{sec} · {date.today():%d %b %Y}")[:120],
                                'props': {'sec': oid, 'kind': kind, 'added': _day(it.get('created')), 'made': {'start': date.today().isoformat()}}})
        blocks = ([{'type': 'paragraph', 'content': it['text']}] if it.get('text') else []) + ([{'type': 'paragraph', 'content': it['url']}] if it.get('url') else []) + [{'type': 'paragraph'}]
        PG.update(r['id'], {'content': json.dumps(blocks)})
        return dict(root=root, cdb=cdb, gdb=gdb, pid=r['id'], ex={k: st.get(k) for k in EXTRA})
    res = PG.run(go)
    tracker.run(lambda c: (_save_ids(c, res['root'], res['cdb'], res['gdb'], res['ex']), M.update_inspo(c, iid, page_id=res['pid'])))
    return dict(page_id=res['pid'])


def thumbs(pids):
    """the first picture on each page (a goal's picture on the web)"""
    if not pids: return {}
    def go():
        out = {}
        for pid in pids:
            d = PG.get_doc(pid); m = IMG.search((d or {}).get('content') or '')
            if m and not m.group(1).startswith('file:'): out[pid] = m.group(1)
        return out
    return PG.run(go)
