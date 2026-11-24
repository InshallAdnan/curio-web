"""Calendar for Curio Web — the desktop Calendar's own adapters (calendar_sources.py, unchanged) on the web database.

Finance money (income, expenses, daily total, transfers, upcoming subscriptions) and every Pages database that has a
Date property show on one calendar. Which databases are shown, their colours and the Finance switches are kept in the
Finance settings table (key 'calendar_cfg'), so they follow you to every device."""
import json
from datetime import date, datetime, timedelta

import fin, pages
import calendar_sources as cs
from finance import ledger, db as fdb, money

SOURCES = list(cs.SOURCES)
DEFAULT = {'sources': {s: s != 'daily_total' for s in SOURCES}, 'pages': None}


def _d(s): return date.fromisoformat(str(s)[:10])


def _dt(s): return datetime.fromisoformat(str(s)[:16]) if len(str(s)) > 10 else datetime.fromisoformat(str(s)[:10])


def _cfg(con):
    try: c = json.loads(fdb.get_setting(con, 'calendar_cfg', '') or '{}')
    except ValueError: c = {}
    out = {'sources': dict(DEFAULT['sources']), 'pages': c.get('pages')}
    out['sources'].update(c.get('sources') or {})
    return out


def _save_cfg(con, c): fdb.set_setting(con, 'calendar_cfg', json.dumps(c))


def _jsonable(e):
    e = dict(e)
    for k in ('date', 'start', 'end'):
        v = e.get(k)
        if isinstance(v, (date, datetime)): e[k] = v.isoformat()
    return e


def _calendars(cfg):
    """the Pages databases on the calendar (first visit: every dated database), with their colour and date property"""
    found = cs.page_calendars(); by_id = {c['id']: c for c in found}
    items = cfg.get('pages')
    if items is None: items = [{'db': c['id'], 'prop': c['date_props'][0]['id'], 'color': i % len(cs.PAGE_INKS), 'on': True} for i, c in enumerate(found)]
    cals = []
    for it in items:
        c = by_id.get(it.get('db'))
        if not c: continue
        prop = next((p for p in c['date_props'] if p['id'] == it.get('prop')), c['date_props'][0])
        cals.append(dict(id=c['id'], title=c['title'], icon=c.get('icon'), parent=c.get('parent'), crumb=c.get('crumb', ''), date_props=c['date_props'],
                         prop_id=prop['id'], prop_name=prop['name'], color=it.get('color', 0), on=it.get('on', True), props=c['props']))
    return cals, items


def view(a):
    start, end = _d(a['start']), _d(a['end'])
    def money_part(con):
        cfg = _cfg(con)
        on = [s for s, v in cfg['sources'].items() if v]
        ev = cs.finance_events(con, start, end, on)
        return cfg, [_jsonable(e) for e in ev], fdb.get_setting(con, 'base_currency', 'PKR')
    cfg, fev, base = fin.run(money_part)

    def pages_part():
        cals, items = _calendars(cfg); out = []
        for c in cals:
            if not c['on']: continue
            for e in cs.page_events(c, c['prop_id'], start, end, c['color']):
                e.pop('props', None); out.append(_jsonable(e))
        for c in cals: c.pop('props', None)
        return cals, items, out
    cals, items, pev = pages.run(pages_part)
    if cfg.get('pages') is None and items:                         # first visit: remember the starting set
        cfg['pages'] = items; fin.run(lambda con: _save_cfg(con, cfg))
    try:
        import tracker
        tev = tracker.call('calendar', {'start': start.isoformat(), 'end': end.isoformat()})
        trk = [dict(key=f"area:{b['id']}", name=b['name'], color=b['color']) for b in tracker.call('areas', {})] + \
              [dict(key='checkins', name='Check-ins', color='#0e8fa3'), dict(key='habits', name='Habits', color='#1f9d6b'), dict(key='sleep', name='Sleep', color='#6d5bd0')]
    except Exception: tev, trk = [], []
    return dict(events=fev + pev + tev, calendars=cals, sources=cfg['sources'], labels=SOURCE_LABELS, base=base, inks=cs.PAGE_INKS, colors=cs.PAGE_COLORS, tracker=trk)


SOURCE_LABELS = {'income': 'Income', 'expense': 'Expenses', 'daily_total': 'Daily total', 'transfer': 'Transfers', 'subscription': 'Upcoming subscriptions'}


def _edit_cfg(fn):
    def go(con):
        c = _cfg(con)
        if c.get('pages') is None:
            c['pages'] = pages.run(lambda: _calendars(c)[1])
        fn(c); _save_cfg(con, c); return True
    return fin.run(go)


def set_source(a): return _edit_cfg(lambda c: c['sources'].__setitem__(a['key'], bool(a['on'])))


def set_page(a):
    def f(c):
        for it in c['pages']:
            if it['db'] == a['db']:
                for k in ('on', 'color', 'prop'):
                    if k in a: it[k] = a[k]
    return _edit_cfg(f)


def solo(a):
    def f(c):
        for it in c['pages']: it['on'] = it['db'] == a['db']
    return _edit_cfg(f)


def remove(a): return _edit_cfg(lambda c: c.__setitem__('pages', [it for it in c['pages'] if it['db'] != a['db']]))


def databases(a):
    """every Pages database for the “Add database” picker: dated ones, and the rest (they can get a Date property)"""
    def go():
        dbs = cs.page_databases()
        for d in dbs: d.pop('props', None); d.pop('views', None)
        link = cs.resolve_db(a.get('link') or '', dbs) if a.get('link') else None
        return dbs, link
    dbs, link = pages.run(go)
    shown = fin.run(lambda con: [it['db'] for it in (_cfg(con).get('pages') or [])])
    return dict(dbs=dbs, shown=shown, link=link)


def add_db(a):
    dbid = a['db']
    def go():
        d = next((x for x in cs.page_databases() if x['id'] == dbid), None)
        if not d: raise ValueError('That database no longer exists.')
        if not d['has_date']: cs.add_date_property(dbid); d = next(x for x in cs.page_databases() if x['id'] == dbid)
        return d['date_props'][0]['id']
    prop = pages.run(go)
    def f(c):
        if any(it['db'] == dbid for it in c['pages']):
            for it in c['pages']:
                if it['db'] == dbid: it['on'] = True
            return
        used = {it.get('color') for it in c['pages']}
        color = next((i for i in range(len(cs.PAGE_INKS)) if i not in used), len(c['pages']) % len(cs.PAGE_INKS))
        c['pages'].append({'db': dbid, 'prop': prop, 'color': color, 'on': True})
    return _edit_cfg(f)


def move(a):
    """an event dragged to another day / time (or resized). Finance: only its date changes."""
    src = a['source']
    if src == 'myday':                                                # Tracker: a task, a night of sleep or a focus session
        import tracker
        return tracker.call('calendar_move', {'kind': a['kind'], 'id': a['id'], 'start': a['start'], 'end': a.get('end'), 'all_day': a.get('all_day')})
    if src.startswith('page:'):
        s = _dt(a['start']); e = _dt(a['end']) if a.get('end') else None
        return pages.run(lambda: cs.set_page_when(a['record_id'], a['prop_id'], s, e, bool(a.get('all_day'))) or True)
    day = str(a['start'])[:10]
    def go(con):
        if src in ('income', 'expense'):
            r = ledger.transaction(con, int(a['record_id']))
            ledger.update_transaction(con, r['id'], day, r['account_id'], r['kind'], r['amount'], r['fee'], r['title'], r['category_id'], r['note'], r['attachment'])
        elif src == 'transfer':
            r = ledger.transfer(con, int(a['record_id']))
            ledger.update_transfer(con, r['id'], day, r['from_account_id'], r['to_account_id'], r['amount_out'], r['amount_in'], r['fee'], r['note'])
        else: raise ValueError('This one cannot be moved.')
        return True
    return fin.run(go)


def create(a):
    s = _dt(a['start']); e = _dt(a['end']) if a.get('end') else None
    return pages.run(lambda: cs.create_page_event(a['db'], a['prop_id'], a.get('title') or 'Untitled', s, e, bool(a.get('all_day'))))


def rename(a): return pages.run(lambda: pages.row_update(a['record_id'], {'title': a.get('title') or ''}) or True)


def clear_date(a): return pages.run(lambda: pages.row_update(a['record_id'], {'props': {a['prop_id']: None}}) or True)


def details(a):
    def go():
        cal = next((c for c in cs.page_calendars() if c['id'] == a['db']), None)
        if not cal: return []
        with pages.connect() as c:
            r = c.execute('SELECT props FROM docs WHERE id=?', (a['record_id'],)).fetchone()
        ev = {'props': json.loads(r['props'] or '{}') if r else {}, 'prop_id': a['prop_id']}
        return [list(x) for x in cs.page_details(ev, cal)]
    return pages.run(go)


def fin_detail(a):
    def go(con):
        src = a['source']
        if src in ('income', 'expense'):
            t = next((r for r in ledger.list_transactions(con) if r['id'] == int(a['record_id'])), None)
            return dict(t) if t else None
        if src == 'transfer':
            f = next((r for r in ledger.list_transfers(con) if r['id'] == int(a['record_id'])), None)
            return dict(f) if f else None
        return None
    return fin.run(go)


OPS = {'view': view, 'set_source': set_source, 'set_page': set_page, 'solo': solo, 'remove': remove, 'databases': databases, 'add_db': add_db,
       'move': move, 'create': create, 'rename': rename, 'clear_date': clear_date, 'details': details, 'fin_detail': fin_detail}


def call(op, args):
    f = OPS.get(op)
    if f is None: raise ValueError(f'Unknown action: {op}')
    return f(args or {})
