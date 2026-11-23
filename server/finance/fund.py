"""Replacement fund: set aside the value your things lose, so the money is there when they need replacing.

One fund account for everything. Each month the depreciation of your things is "due" to the fund.
  due so far   = depreciation of every asset, month by month, from the month the fund started up to this month
  saved so far = every set-aside (a real transfer from an account into the fund account)
  pending      = due so far - saved so far            (missed or paused months show up here, never lost)
  this month   = what is due this month and not yet covered; older pending can be paid at once or spread
Each asset gets a share of what was saved in proportion to what it was due, so every thing shows saved / pending too.
Taking money out of the fund to buy a replacement is an ordinary transfer or expense — it does not make anything pending again."""
from . import ledger, currency
from . import assets as A
from .db import get_setting, set_setting
from .util import iso, today, this_month, add_months

SCHEMA = """CREATE TABLE IF NOT EXISTS fund_moves(
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount > 0), transfer_id INTEGER REFERENCES transfers(id) ON DELETE CASCADE,
  note TEXT, created TEXT)"""


def prepare(con): con.execute(SCHEMA)


def _s(con, k, d=''): return get_setting(con, k, d)


def settings(con):
    return dict(account=int(_s(con, 'fund_account', '0') or 0), source=int(_s(con, 'fund_from', '0') or 0), since=_s(con, 'fund_since', ''),
                paused=_s(con, 'fund_paused', '0') == '1', spread=int(_s(con, 'fund_spread', '0') or 0))


def _to_base(con, m, cur):
    v = currency.to_base(con, m, cur); return v or 0


def _due_by_asset(con, since, upto):
    """{asset id: (name, due in base currency)} for depreciation months since..upto (YYYY-MM, both included)"""
    out = {}
    for a in A.list_assets(con):
        evs = A.events(con, a['id']); end = a['sold_date'] if a['status'] == 'sold' and a['sold_date'] else None
        amt = sum(r['depreciation'] for r in A.schedule(a, evs) if since <= r['date'][:7] <= upto and (end is None or r['date'] <= end))
        if amt: out[a['id']] = (a['name'], _to_base(con, amt, a['currency']))
    return out


def moves(con): return [dict(r) for r in con.execute('SELECT * FROM fund_moves ORDER BY date DESC, id DESC')]


def state(con):
    s = settings(con); m = this_month()
    if not s['account'] or not ledger.account(con, s['account']):
        return dict(on=False, settings=s)
    since = s['since'] or m
    due_all = _due_by_asset(con, since, m)
    due_before = sum(v for _, v in _due_by_asset(con, since, add_months(m, -1)).values()) if since < m else 0
    due = sum(v for _, v in due_all.values())
    mv = moves(con); saved = sum(r['amount'] for r in mv)
    month_saved = sum(r['amount'] for r in mv if r['date'][:7] == m)
    pending = max(due - saved, 0)
    month_due = due - due_before                                # what this month itself adds
    backlog = max(due_before - (saved - month_saved), 0)        # left over from earlier months when this month began (missed or paused)
    left = 1
    if s['spread']:                                             # catch up over N months, counted from when you chose it
        f0 = _s(con, 'fund_spread_from', m) or m; gone = (int(m[:4]) * 12 + int(m[5:7])) - (int(f0[:4]) * 12 + int(f0[5:7]))
        left = max(s['spread'] - gone, 1)
    catchup = min(backlog, -(-backlog // left))
    suggest = 0 if s['paused'] else max(min(month_due + catchup - month_saved, pending), 0)
    per = []
    for aid, (name, d) in sorted(due_all.items(), key=lambda x: -x[1][1]):
        got = min(d, saved * d // due) if due else 0
        per.append(dict(id=aid, name=name, due=d, saved=got, pending=d - got))
    acc = ledger.account(con, s['account'])
    return dict(on=True, settings=s, since=since, account=dict(acc), balance=ledger.balance(con, s['account']),
                due=due, saved=saved, pending=pending, backlog=backlog, month_due=month_due, catchup=catchup, suggest=suggest,
                month_saved=month_saved, per_asset=per, moves=mv[:24])


def setup(con, account, source=None, since=None):
    if not ledger.account(con, account): raise ValueError('Pick the fund account')
    set_setting(con, 'fund_account', account)
    if source: set_setting(con, 'fund_from', source)
    if since is not None or not _s(con, 'fund_since'): set_setting(con, 'fund_since', (since or this_month())[:7])
    con.commit()


def set_aside(con, amount, date=None, source=None, note=''):
    s = settings(con)
    if not s['account']: raise ValueError('Turn on the replacement fund first')
    src = source or s['source']
    if not src: raise ValueError('Pick the account the money comes from')
    if src == s['account']: raise ValueError('The money has to come from another account')
    if amount <= 0: raise ValueError('Enter an amount')
    d = date or iso(today())
    tid = ledger.add_transfer(con, d, src, s['account'], amount, None, 0, note or 'Replacement fund', 'Replacement fund')
    con.execute('INSERT INTO fund_moves(date, amount, transfer_id, note, created) VALUES(?,?,?,?,?)', (d, amount, tid, note, iso(today())))
    if source: set_setting(con, 'fund_from', source)
    con.commit(); return tid


def remove_move(con, mid, keep_transfer=False):
    r = con.execute('SELECT transfer_id FROM fund_moves WHERE id=?', (mid,)).fetchone()
    con.execute('DELETE FROM fund_moves WHERE id=?', (mid,))
    if r and r['transfer_id'] and not keep_transfer: con.execute('DELETE FROM transfers WHERE id=?', (r['transfer_id'],))
    con.commit()


def set_option(con, paused=None, spread=None):
    if paused is not None: set_setting(con, 'fund_paused', '1' if paused else '0')
    if spread is not None: set_setting(con, 'fund_spread', max(int(spread), 0)); set_setting(con, 'fund_spread_from', this_month())
    con.commit()


def turn_off(con):
    """stop the fund (its transfers stay in your accounts)"""
    set_setting(con, 'fund_account', '0'); con.commit()
