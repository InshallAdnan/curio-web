"""Subscriptions. A subscription is a list of *periods* (active spans). Pause = close the span; resume = open a new one;
'for a few months' = a span with an end; remove = end it. Charges are created from the periods — never typed by hand."""
from . import ledger
from .db import category_id, get_setting
from .util import add_months, clip_day, iso, today, ym, month_diff, parse_date

STATES = {'active': 'Active', 'paused': 'Paused', 'ended': 'Ended', 'scheduled': 'Starts soon', 'finished': 'Finished'}


def subscription(con, sid): return con.execute('SELECT s.*, a.name AS account_name, a.currency AS currency FROM subscriptions s JOIN accounts a ON a.id=s.account_id WHERE s.id=?', (sid,)).fetchone()


def list_subscriptions(con):
    return con.execute('SELECT s.*, a.name AS account_name, a.currency AS currency, a.color AS account_color FROM subscriptions s JOIN accounts a ON a.id=s.account_id ORDER BY s.name COLLATE NOCASE').fetchall()


def periods(con, sid): return con.execute('SELECT * FROM sub_periods WHERE sub_id=? ORDER BY start_month, id', (sid,)).fetchall()


def charges(con, sid): return con.execute('SELECT * FROM sub_charges WHERE sub_id=? ORDER BY month DESC', (sid,)).fetchall()


def schedule(con, sid, upto, every=None):
    """charge months of a subscription up to (and including) month `upto`"""
    every = every or con.execute('SELECT every_months FROM subscriptions WHERE id=?', (sid,)).fetchone()[0]
    out = set()
    for p in periods(con, sid):
        m = p['start_month']; end = min(p['end_month'] or upto, upto)
        while m <= end: out.add(m); m = add_months(m, every)
    return sorted(out)


def _skip_past(con, sid, cost, every, billing_day, start, end, this_month):
    """Months before this month are NOT charged automatically (they were already paid / recorded by you)."""
    m = start; last = min(end or add_months(this_month, -1), add_months(this_month, -1))
    while m <= last:
        con.execute('INSERT OR IGNORE INTO sub_charges(sub_id, month, due_date, amount, state) VALUES(?,?,?,?,?)', (sid, m, iso(clip_day(m, billing_day)), cost, 'skipped'))
        m = add_months(m, every)


def add_subscription(con, name, cost, account_id, start_month=None, every_months=1, billing_day=1, months=None, category=None, note='', backfill=False, today_=None):
    name = (name or '').strip(); t = today_ or today()
    if not name: raise ValueError('Give the subscription a name')
    if cost <= 0: raise ValueError('Enter the price')
    if not ledger.account(con, account_id): raise ValueError('Choose the account it is paid from')
    start_month = start_month or ym(t); end = add_months(start_month, months - 1) if months else None
    c = con.execute('INSERT INTO subscriptions(name, cost, every_months, billing_day, account_id, category_id, note, status, created) VALUES(?,?,?,?,?,?,?,?,?)',
                    (name, cost, every_months, billing_day, account_id, category, note, 'active', iso(t)))
    sid = c.lastrowid
    con.execute('INSERT INTO sub_periods(sub_id, start_month, end_month) VALUES(?,?,?)', (sid, start_month, end))
    if not backfill: _skip_past(con, sid, cost, every_months, billing_day, start_month, end, ym(t))
    con.commit()
    if get_setting(con, 'auto_post_subs', '1') == '1': post_due(con, t)
    return sid


def update_subscription(con, sid, name, cost, account_id, every_months=1, billing_day=1, category=None, note=''):
    name = (name or '').strip()
    if not name: raise ValueError('Give the subscription a name')
    if cost <= 0: raise ValueError('Enter the price')
    con.execute('UPDATE subscriptions SET name=?, cost=?, account_id=?, every_months=?, billing_day=?, category_id=?, note=? WHERE id=?',
                (name, cost, account_id, every_months, billing_day, category, note, sid)); con.commit()


def pause(con, sid, from_month):
    """Stop charging from `from_month` on."""
    last = add_months(from_month, -1)
    for p in periods(con, sid):
        if p['end_month'] is None or p['end_month'] >= from_month:
            if p['start_month'] > last: con.execute('DELETE FROM sub_periods WHERE id=?', (p['id'],))
            else: con.execute('UPDATE sub_periods SET end_month=? WHERE id=?', (last, p['id']))
    con.execute("UPDATE subscriptions SET status='paused' WHERE id=?", (sid,)); con.commit()


def end_subscription(con, sid, last_month):
    """Remove it: the last charge is `last_month`; history stays."""
    for p in periods(con, sid):
        if p['end_month'] is None or p['end_month'] > last_month:
            if p['start_month'] > last_month: con.execute('DELETE FROM sub_periods WHERE id=?', (p['id'],))
            else: con.execute('UPDATE sub_periods SET end_month=? WHERE id=?', (last_month, p['id']))
    con.execute("UPDATE subscriptions SET status='ended' WHERE id=?", (sid,)); con.commit()


def resume(con, sid, from_month=None, months=None, today_=None):
    """Restart, or add a new stretch ('for N months')."""
    t = today_ or today(); s = subscription(con, sid); from_month = from_month or ym(t)
    end = add_months(from_month, months - 1) if months else None
    for p in periods(con, sid):                                    # an open span would double-charge
        if p['end_month'] is None or p['end_month'] >= from_month:
            last = add_months(from_month, -1)
            if p['start_month'] > last: con.execute('DELETE FROM sub_periods WHERE id=?', (p['id'],))
            else: con.execute('UPDATE sub_periods SET end_month=? WHERE id=?', (last, p['id']))
    con.execute('INSERT INTO sub_periods(sub_id, start_month, end_month) VALUES(?,?,?)', (sid, from_month, end))
    con.execute("UPDATE subscriptions SET status='active' WHERE id=?", (sid,))
    _skip_past(con, sid, s['cost'], s['every_months'], s['billing_day'], from_month, end, ym(t)); con.commit()
    if get_setting(con, 'auto_post_subs', '1') == '1': post_due(con, t)


def delete_subscription(con, sid):
    con.execute("UPDATE transactions SET source='manual', source_id=NULL WHERE source='subscription' AND source_id=?", (sid,))
    con.execute('DELETE FROM subscriptions WHERE id=?', (sid,)); con.commit()


def effective_state(con, s, today_=None):
    t = ym(today_ or today())
    if s['status'] in ('ended', 'paused'): return s['status']
    ps = periods(con, s['id'])
    if any(p['start_month'] <= t and (p['end_month'] is None or p['end_month'] >= t) for p in ps): return 'active'
    if any(p['start_month'] > t for p in ps): return 'scheduled'
    return 'finished'


def _due_date(s, m): return clip_day(m, s['billing_day'])


def due_charges(con, today_=None):
    """Charges whose date has arrived and that were not posted yet."""
    t = today_ or today(); out = []
    for s in list_subscriptions(con):
        done = {r['month'] for r in con.execute('SELECT month FROM sub_charges WHERE sub_id=?', (s['id'],))}
        for m in schedule(con, s['id'], ym(t), s['every_months']):
            d = _due_date(s, m)
            if m not in done and d <= t: out.append(dict(sub_id=s['id'], name=s['name'], month=m, due_date=iso(d), amount=s['cost'], account_id=s['account_id'], currency=s['currency'], category_id=s['category_id']))
    out.sort(key=lambda r: (r['due_date'], r['name'])); return out


def post_due(con, today_=None):
    """Create the expense for every due charge. Safe to run any number of times."""
    posted = []
    cat_default = category_id(con, 'Subscriptions', 'expense')
    for d in due_charges(con, today_):
        tid = ledger.add_transaction(con, d['due_date'], d['account_id'], 'expense', d['amount'], 0, d['name'], d['category_id'] or cat_default, 'Subscription charge', None, 'subscription', d['sub_id'])
        con.execute("INSERT INTO sub_charges(sub_id, month, due_date, amount, transaction_id, state) VALUES(?,?,?,?,?, 'posted')", (d['sub_id'], d['month'], d['due_date'], d['amount'], tid))
        posted.append(d)
    con.commit(); return posted


def skip_charge(con, sid, month):
    """Do not charge this one month (e.g. a free month)."""
    s = subscription(con, sid)
    con.execute("INSERT INTO sub_charges(sub_id, month, due_date, amount, state) VALUES(?,?,?,?, 'skipped') ON CONFLICT(sub_id, month) DO UPDATE SET state='skipped'",
                (sid, month, iso(_due_date(s, month)), s['cost'])); con.commit()


def next_charge(con, s, today_=None):
    """→ (month, date) of the next charge that has not happened yet, or None"""
    t = today_ or today(); start = ym(t)
    done = {r['month'] for r in con.execute('SELECT month FROM sub_charges WHERE sub_id=?', (s['id'],))}
    for m in schedule(con, s['id'], add_months(start, 26), s['every_months']):
        d = _due_date(s, m)
        if d >= t and m not in done: return m, d
    return None


def monthly_equivalent(s): return int(round(s['cost'] / s['every_months']))


