"""Read-only Finance event adapters used by Curio Calendar."""
from datetime import timedelta
from calendar import monthrange


SOURCES = ('income', 'expense', 'daily_total', 'transfer', 'subscription')


def visible_range(anchor, mode, days=1):
    """Return the inclusive dates shown by a Calendar view; weeks always start Monday."""
    if mode == 'week':
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if mode == 'month':
        start = anchor.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return start, end
    count = max(1, min(9, int(days)))
    return anchor, anchor + timedelta(days=count - 1)


def shift_anchor(anchor, mode, direction, days=1):
    """Move the selected day by the active view's natural interval."""
    if mode == 'month':
        index = anchor.year * 12 + anchor.month - 1 + int(direction)
        year, month = divmod(index, 12)
        month += 1
        return anchor.replace(year=year, month=month, day=min(anchor.day, monthrange(year, month)[1]))
    return anchor + timedelta(days=(7 if mode == 'week' else max(1, min(9, int(days)))) * int(direction))


def overlap_lanes(events):
    """Greedy, deterministic lanes for timed blocks; suitable for paint-only calendar grids."""
    ends, lanes = [], []
    for event in events:
        start, end = event['start_minute'], max(event['start_minute'] + 1, event['end_minute'])
        lane = next((i for i, value in enumerate(ends) if value <= start), None)
        if lane is None:
            lane = len(ends); ends.append(end)
        else: ends[lane] = end
        lanes.append(lane)
    return lanes, max(1, len(ends))


def _event(source, record_id, when, title, amount, currency, color, readonly=False, **extra):
    return dict(id=f'{source}:{record_id}', source=source, record_id=record_id, date=when,
                title=title, amount=int(amount), currency=currency, color=color or '#6B7280',
                readonly=readonly, **extra)


def _upcoming_subscriptions(con, start, end):
    """Project subscription dates without posting or otherwise changing Finance data."""
    from finance import subs
    from finance.util import add_months, clip_day, ym
    out = []
    month = ym(start)
    last = ym(end)
    while month <= last:
        for sub in subs.list_subscriptions(con):
            if month not in subs.schedule(con, sub['id'], month, sub['every_months']):
                continue
            when = clip_day(month, sub['billing_day'])
            if start <= when <= end:
                out.append(_event('subscription', f"{sub['id']}:{month}", when, sub['name'], sub['cost'],
                                  sub['currency'], sub['account_color'] if 'account_color' in sub.keys() else None,
                                  True, subscription_id=sub['id']))
        month = add_months(month, 1)
    return out


def finance_events(con, start, end, enabled=None):
    """Return Finance-backed Calendar events. This function never writes to the Finance book."""
    from finance import currency, ledger, money
    enabled = set(SOURCES if enabled is None else enabled)
    events, net = [], {}
    if enabled & {'income', 'expense', 'daily_total'}:
        for row in ledger.list_transactions(con, date_from=start.isoformat(), date_to=end.isoformat()):
            source = row['kind']
            if source in enabled:
                amount = row['amount'] - row['fee'] if source == 'income' else -(row['amount'] + row['fee'])
                title = row['title'] or row['category_name'] or ('Income' if source == 'income' else 'Expense')
                events.append(_event(source, row['id'], start.fromisoformat(row['date']), title, amount,
                                     row['currency'], row['account_color'], False,
                                     detail=money.fmt(amount, row['currency'], sign=True), transaction_id=row['id']))
            if 'daily_total' in enabled:
                amount = row['amount'] - row['fee'] if row['kind'] == 'income' else -(row['amount'] + row['fee'])
                base_amount = currency.to_base(con, amount, row['currency'])
                if base_amount is not None: net[row['date']] = net.get(row['date'], 0) + base_amount
    if enabled & {'transfer', 'daily_total'}:
        for row in ledger.list_transfers(con):
            when = start.fromisoformat(row['date'])
            if not start <= when <= end: continue
            if 'transfer' in enabled:
                title = f"{row['from_name']} → {row['to_name']}"
                events.append(_event('transfer', row['id'], when, title, row['amount_out'], row['from_cur'],
                                     row['from_color'], False, detail=money.fmt(row['amount_out'], row['from_cur']), transfer_id=row['id']))
            if 'daily_total' in enabled and row['fee']:
                fee = currency.to_base(con, row['fee'], row['from_cur'])
                if fee is not None: net[row['date']] = net.get(row['date'], 0) - fee
    if 'daily_total' in enabled:
        base = currency.base(con)
        for when, amount in net.items():
            events.append(_event('daily_total', when, start.fromisoformat(when), 'Daily total', amount, base,
                                 '#64748B', True, detail=money.fmt(amount, base, sign=True)))
    if 'subscription' in enabled: events.extend(_upcoming_subscriptions(con, start, end))
    return sorted(events, key=lambda e: (e['date'], e['source'], str(e['record_id'])))


# ── Pages databases as calendars (like Notion Calendar shows Notion databases) ───────────────────────────────
PAGE_COLORS = ['#e8f0fe', '#fde7f3', '#e6f6ea', '#fff4d6', '#efe7ff', '#e3f6f7', '#ffe9e1', '#eef0f3']
PAGE_INKS = ['#1a5fd0', '#b5317a', '#1d7a3b', '#9a6a00', '#6b3fd4', '#13797f', '#c2481c', '#4b5563']


def _pages():
    import pages_ui
    return pages_ui


def parse_when(value):
    """Pages date value → (start datetime, end datetime | None, all_day). Accepts 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM' or {start, end}."""
    from datetime import datetime
    if not value: return None
    if isinstance(value, dict): s, e = value.get('start'), value.get('end')
    else: s, e = value, None
    def one(x):
        if not x: return None
        x = str(x)
        try: return datetime.fromisoformat(x[:16] if len(x) > 10 else x[:10])
        except ValueError: return None
    a = one(s)
    if a is None: return None
    b = one(e); all_day = len(str(s)) <= 10
    if b and b < a: b = None
    return a, b, all_day


def _path_of(c, parent):
    """Titles from the top page down to `parent` (a row page steps up through its database)."""
    out, seen, i = [], set(), parent
    while i and i not in seen and len(out) < 12:
        seen.add(i)
        r = c.execute('SELECT title, parent, db FROM docs WHERE id=?', (i,)).fetchone()
        if r: out.append(r['title'] or 'Untitled'); i = r['db'] or r['parent']; continue
        d = c.execute('SELECT title, parent FROM dbs WHERE id=?', (i,)).fetchone()
        if not d: break
        out.append(d['title'] or 'Untitled database'); i = d['parent']
    return out[::-1]


def crumb(path):
    """Notion's short breadcrumb: 'Top / … / Parent'."""
    if not path: return ''
    return ' / '.join(path) if len(path) <= 2 else f'{path[0]} / … / {path[-1]}'


def page_databases():
    """Every Pages database (not in the bin) with its path, date properties and views — dated or not."""
    import json
    pu = _pages(); out = []
    with pu.connect() as c:
        rows = c.execute('SELECT d.id, d.title, d.icon, d.props, d.views, d.parent FROM dbs d LEFT JOIN docs p ON p.id = d.parent '
                         'WHERE p.id IS NULL OR COALESCE(p.archived, 0) = 0 ORDER BY d.created').fetchall()
        for r in rows:
            props = json.loads(r['props'] or '[]')
            dates = [p for p in props if p.get('type') == 'date']
            path = _path_of(c, r['parent']) if r['parent'] else []
            title = r['title'] or (path[-1] if path else '') or 'Untitled database'
            out.append({'id': r['id'], 'title': title, 'icon': r['icon'], 'parent': r['parent'], 'path': path, 'crumb': crumb(path),
                        'views': json.loads(r['views'] or '[]'), 'has_date': bool(dates),
                        'date_props': [{'id': p['id'], 'name': p.get('name') or 'Date', 'time': bool((p.get('date') or {}).get('time'))} for p in dates],
                        'props': props})
    return out


def page_calendars():
    """Every Pages database that has a date property — each one can be a calendar."""
    return [d for d in page_databases() if d['has_date']]


def add_date_property(db_id):
    """Give a database a 'Date' property (with time) so it can show on the Calendar. Nothing else changes."""
    import uuid
    pu = _pages(); d = pu.db_get(db_id)
    if not d: raise ValueError('That database no longer exists.')
    props = d['db']['props']
    if any(p.get('type') == 'date' for p in props): return None
    names = {p.get('name') for p in props}; name = 'Date'; n = 2
    while name in names: name = f'Date {n}'; n += 1
    prop = {'id': uuid.uuid4().hex[:8], 'name': name, 'type': 'date', 'date': {'time': True}}
    props.append(prop); pu.db_update(db_id, {'props': props})
    return prop


def resolve_db(text, dbs=None):
    """A pasted Pages link (Copy link to view / Copy link) or an id → the database it points to, or None."""
    import re
    t = (text or '').strip()
    if not t: return None
    dbs = dbs if dbs is not None else page_databases()
    ids = {d['id'] for d in dbs}
    m = re.search(r'[?&]db=([0-9a-f]{8,32})', t)
    if m and m.group(1) in ids: return m.group(1)
    page = re.search(r'documents/([^/?#\s]+)', t)
    toks = ([page.group(1)] if page else []) + re.findall(r'\b[0-9a-f]{16}\b', t)
    for tok in toks:
        if tok in ids: return tok
        on_page = [d['id'] for d in dbs if d['parent'] == tok]
        if on_page: return on_page[0]
    return None


def _fmt_prop(p, v, rel_titles):
    t = p.get('type')
    if v in (None, '', []): return ''
    if t in ('select', 'status'): return next((o.get('name', '') for o in p.get('options') or [] if o.get('id') == v), '')
    if t.startswith('multi'): return ', '.join(o.get('name', '') for o in p.get('options') or [] if o.get('id') in (v or []))
    if t == 'checkbox': return '✓' if v else '—'
    if t == 'relation': return ', '.join(rel_titles.get(x, '') for x in v if rel_titles.get(x))
    if t == 'date':
        w = parse_when(v)
        if not w: return ''
        a, b, ad = w; f = (lambda d: d.strftime('%d %b %Y')) if ad else (lambda d: d.strftime('%d %b %Y, %I:%M %p'))
        return f(a) + (' → ' + f(b) if b else '')
    if isinstance(v, (dict, list)): return ''
    return str(v)


def page_events(cal, prop_id, start, end, color_index=0):
    """Rows of one Pages database whose date falls in [start, end] (dates)."""
    import json
    from datetime import datetime, timedelta, time as dtime
    pu = _pages(); out = []
    prop = next((p for p in cal['props'] if p.get('id') == prop_id), None)
    if not prop: return out
    bg = PAGE_COLORS[color_index % len(PAGE_COLORS)]; ink = PAGE_INKS[color_index % len(PAGE_INKS)]
    lo = datetime.combine(start, dtime.min); hi = datetime.combine(end, dtime.max)
    with pu.connect() as c:
        rows = c.execute('SELECT id, title, icon, props FROM docs WHERE db=? AND COALESCE(archived, 0)=0', (cal['id'],)).fetchall()
    for r in rows:
        try: props = json.loads(r['props'] or '{}')
        except ValueError: continue
        w = parse_when(props.get(prop_id))
        if not w: continue
        a, b, all_day = w
        if all_day:
            b2 = b or a
            if (b2 + timedelta(days=1)) <= lo or a > hi: continue
        else:
            b2 = b or (a + timedelta(hours=1))
            if b2 <= lo or a > hi: continue
        out.append(dict(id=f"page:{r['id']}", source='page:' + cal['id'], record_id=r['id'], db_id=cal['id'], prop_id=prop_id,
                        date=a.date(), start=a, end=b, all_day=all_day, title=(r['title'] if r['title'] != 'Untitled' else '') or 'Untitled',
                        icon=r['icon'], color=bg, ink=ink, readonly=False, calendar=cal['title'], props=props))
    return out


def page_details(ev, cal):
    """[(name, text)] of the other properties of a Pages row, for the side panel."""
    import json
    rel_titles = {}
    pu = _pages()
    try:
        ids = [x for p in cal['props'] if p.get('type') == 'relation' for x in (ev['props'].get(p['id']) or [])]
        if ids:
            with pu.connect() as c:
                q = ','.join('?' * len(ids))
                rel_titles = {r['id']: r['title'] for r in c.execute(f'SELECT id, title FROM docs WHERE id IN ({q})', ids)}
    except Exception: pass
    out = []
    for p in cal['props']:
        if p.get('type') in ('title', 'formula', 'rollup', 'files') or p.get('id') == ev['prop_id']: continue
        txt = _fmt_prop(p, ev['props'].get(p['id']), rel_titles)
        out.append((p.get('name') or '', txt, p.get('type')))
    return out


def set_page_when(row_id, prop_id, start, end, all_day):
    """Move / resize a Pages row on the calendar (writes the date property only)."""
    def s(d): return d.strftime('%Y-%m-%d') if all_day else d.strftime('%Y-%m-%dT%H:%M')
    val = {'start': s(start)}
    if end and end != start: val['end'] = s(end)
    _pages().row_update(row_id, {'props': {prop_id: val}})


def create_page_event(db_id, prop_id, title, start, end, all_day):
    def s(d): return d.strftime('%Y-%m-%d') if all_day else d.strftime('%Y-%m-%dT%H:%M')
    val = {'start': s(start)}
    if end and end != start: val['end'] = s(end)
    return _pages().row_create(db_id, {'title': title or 'Untitled', 'props': {prop_id: val}})


def ensure_calendar_database():
    """Make a ready 'Calendar' page with a database (Name, Date with time, Type, Notes) when none exists yet."""
    import uuid
    pu = _pages()
    pid = pu.create(None, 'Calendar', None, '📅')
    opt = lambda n, c: {'id': uuid.uuid4().hex[:8], 'name': n, 'color': c}
    props = [{'id': 'title', 'name': 'Name', 'type': 'title'},
             {'id': 'when', 'name': 'Date', 'type': 'date', 'date': {'time': True}},
             {'id': 'type', 'name': 'Type', 'type': 'select', 'options': [opt('Task', 'blue'), opt('Meeting', 'purple'), opt('Personal', 'green'), opt('Reminder', 'orange')]},
             {'id': 'done', 'name': 'Done', 'type': 'checkbox'},
             {'id': 'notes', 'name': 'Notes', 'type': 'text'}]
    vid = uuid.uuid4().hex[:8]
    db = pu.db_create(pid, {'title': 'Calendar', 'icon': '📅', 'props': props,
                            'views': [{'id': vid, 'name': 'Calendar', 'type': 'calendar', 'dateProp': 'when'},
                                      {'id': uuid.uuid4().hex[:8], 'name': 'Table', 'type': 'table'}]})
    import json
    pu.update(pid, {'content': json.dumps([{'type': 'database', 'props': {'dbId': db['id']}}, {'type': 'paragraph'}])})
    return db['id']
