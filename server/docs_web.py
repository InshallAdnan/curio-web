"""Curio Web — the Tracker's Inspo inside Docs (same as the desktop's docs_link.py, on the web database).

Docs › "Inspo" has two tables: "Goals" (every goal and dream, written by the Tracker — one way, Tracker → Docs) and
"Inspo cards" (a card becomes a row when you press "Convert into page"). Each row is a page for more pictures and text.
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


def _ids(c): return dict(root=M.setting(c, 'inspo_page_root') or '', cdb=M.setting(c, 'inspo_cards_db') or '', gdb=M.setting(c, 'inspo_goals_db') or '')


def _ensure(st):
    """inside PG.run → (root page, cards table, goals table); makes what is missing"""
    root = st['root'] if st['root'] and PG.get_doc(st['root']) else PG.create(None, 'Inspo', None, '✨')
    have = {d['id'] for d in PG.db_list()}
    cdb = st['cdb'] if st['cdb'] in have else PG.db_create(root, {'title': 'Inspo cards', 'icon': '🖼️', 'props': CARD_PROPS, 'views': [
        {'id': _u(), 'name': 'Gallery', 'type': 'gallery', 'cardSize': 'm'}, {'id': _u(), 'name': 'Table', 'type': 'table', 'sorts': [{'prop': 'added', 'dir': 'desc'}]}]})['id']
    gdb = st['gdb'] if st['gdb'] in have else PG.db_create(root, {'title': 'Goals', 'icon': '🎯', 'props': GOAL_PROPS, 'views': [
        {'id': _u(), 'name': 'Table', 'type': 'table', 'sorts': [{'prop': 'added', 'dir': 'desc'}]}, {'id': _u(), 'name': 'Gallery', 'type': 'gallery', 'cardSize': 'm'}]})['id']
    doc = PG.get_doc(root) or {}
    try: cur = json.loads(doc.get('content') or '[]') or []
    except Exception: cur = []
    ids = {b.get('props', {}).get('dbId') for b in cur if isinstance(b, dict) and b.get('type') == 'database'}
    want = [{'type': 'database', 'props': {'dbId': gdb}}, {'type': 'database', 'props': {'dbId': cdb}}]
    if not {cdb, gdb} <= ids:
        head = [] if cur else [{'type': 'paragraph', 'content': 'Made by Tracker › Inspo. Goals come from the Tracker by themselves; a card is added here when you press “Convert into page”.'}]
        PG.update(root, {'content': json.dumps(head + cur + [b for b in want if b['props']['dbId'] not in ids] + ([] if cur else [{'type': 'paragraph'}]))})
    return root, cdb, gdb


def _save_ids(c, root, cdb, gdb):
    for k, v in (('inspo_page_root', root), ('inspo_cards_db', cdb), ('inspo_goals_db', gdb)): M.set_setting(c, k, v)


def _sig(gs): return json.dumps([(g['id'], g['kind'], g['title'], g['why'], g.get('created'), g.get('done_at'), g.get('due'), g.get('page_id')) for g in gs])


def goal_pages(force=False):
    st = tracker.run(lambda c: dict(gs=M.goals(c, 'goal') + M.goals(c, 'dream'), sig=M.setting(c, 'goal_pages_sig'), **_ids(c)))
    if not force and st['sig'] == _sig(st['gs']): return

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
        return dict(root=root, cdb=cdb, gdb=gdb, got=got)
    res = PG.run(go)

    def back(c):
        _save_ids(c, res['root'], res['cdb'], res['gdb'])
        for gid, pid in res['got'].items(): c.execute('UPDATE goals SET page_id=? WHERE id=?', (pid, gid))
        c.commit(); M.set_setting(c, 'goal_pages_sig', _sig(M.goals(c, 'goal') + M.goals(c, 'dream')))
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
        return dict(root=root, cdb=cdb, gdb=gdb, pid=r['id'])
    res = PG.run(go)
    tracker.run(lambda c: (_save_ids(c, res['root'], res['cdb'], res['gdb']), M.update_inspo(c, iid, page_id=res['pid'])))
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
