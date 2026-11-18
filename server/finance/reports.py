"""Totals for the Home screen and Reports, all in the base currency."""
from . import ledger, currency, assets as A, subs
from .util import add_months, ym, today, month_bounds


def _conv(con, m, cur, missing):
    v = currency.to_base(con, m, cur)
    if v is None: missing.add(cur); return 0
    return v


def net_worth(con):
    """→ dict(accounts, assets, total, missing=[currencies without a rate])"""
    miss = set(); bal = ledger.balances(con); acc = 0
    for a in ledger.accounts(con): acc += _conv(con, bal.get(a['id'], 0), a['currency'], miss)
    ast = 0
    for a in A.list_assets(con):
        if a['status'] == 'active': ast += _conv(con, A.status(a, A.events(con, a['id']))['book'], a['currency'], miss)
    return dict(accounts=acc, assets=ast, total=acc + ast, missing=sorted(miss))


def month_summary(con, month):
    """income, expense (incl. transfer fees), net — in base currency"""
    miss = set(); inc = exp = 0
    for r in con.execute("SELECT a.currency AS cur, t.kind AS kind, SUM(t.amount) AS amt, SUM(t.fee) AS fee FROM transactions t JOIN accounts a ON a.id=t.account_id WHERE substr(t.date,1,7)=? GROUP BY a.currency, t.kind", (month,)):
        if r['kind'] == 'income': inc += _conv(con, r['amt'] - r['fee'], r['cur'], miss)
        else: exp += _conv(con, r['amt'] + r['fee'], r['cur'], miss)
    for r in con.execute("SELECT a.currency AS cur, SUM(f.fee) AS fee FROM transfers f JOIN accounts a ON a.id=f.from_account_id WHERE substr(f.date,1,7)=? GROUP BY a.currency", (month,)):
        exp += _conv(con, r['fee'] or 0, r['cur'], miss)
    return dict(income=inc, expense=exp, net=inc - exp, missing=sorted(miss))


def series(con, months=6, end=None):
    end = end or ym(today()); out = []
    for i in range(months - 1, -1, -1):
        m = add_months(end, -i); s = month_summary(con, m); out.append(dict(month=m, income=s['income'], expense=s['expense']))
    return out


def category_breakdown(con, month, kind='expense'):
    miss = set(); tot = {}
    for r in con.execute("SELECT COALESCE(c.name, 'No category') AS name, a.currency AS cur, SUM(t.amount) AS amt, SUM(t.fee) AS fee FROM transactions t JOIN accounts a ON a.id=t.account_id "
                         "LEFT JOIN categories c ON c.id=t.category_id WHERE substr(t.date,1,7)=? AND t.kind=? GROUP BY c.name, a.currency", (month, kind)):
        tot[r['name']] = tot.get(r['name'], 0) + _conv(con, r['amt'] + (r['fee'] if kind == 'expense' else -r['fee']), r['cur'], miss)
    if kind == 'expense':
        fees = 0
        for r in con.execute("SELECT a.currency AS cur, SUM(f.fee) AS fee FROM transfers f JOIN accounts a ON a.id=f.from_account_id WHERE substr(f.date,1,7)=? GROUP BY a.currency", (month,)):
            fees += _conv(con, r['fee'] or 0, r['cur'], miss)
        if fees: tot['Transfer fees'] = tot.get('Transfer fees', 0) + fees
    return sorted(([k, v] for k, v in tot.items() if v), key=lambda x: -x[1])


def subscriptions_monthly(con):
    """what the active subscriptions cost per month (base currency)"""
    miss = set(); t = 0
    for s in subs.list_subscriptions(con):
        if subs.effective_state(con, s) == 'active': t += _conv(con, subs.monthly_equivalent(s), s['currency'], miss)
    return t


def assets_monthly_depreciation(con):
    miss = set(); t = 0
    for a in A.list_assets(con):
        if a['status'] == 'active': t += _conv(con, A.status(a, A.events(con, a['id']))['monthly'], a['currency'], miss)
    return t


def depreciation_between(con, d_from, d_to):
    """Depreciation of every asset in a period (both ISO dates included) → [(asset name, amount in base currency)], biggest first.
    Depreciation is not cash: it is the value your things lose, set aside on paper."""
    miss = set(); out = []
    for a in A.list_assets(con):
        evs = A.events(con, a['id']); end = a['sold_date'] if a['status'] == 'sold' and a['sold_date'] else None
        amt = sum(r['depreciation'] for r in A.schedule(a, evs) if d_from <= r['date'] <= d_to and (end is None or r['date'] <= end))
        if amt: out.append((a['name'], _conv(con, amt, a['currency'], miss)))
    return sorted(out, key=lambda x: -x[1])


def depreciation_by_year(con, a):
    """One asset, year by year → [(year, depreciation, value at the end of that year)] in its own currency."""
    rows = A.schedule(a, A.events(con, a['id'])); out = {}
    for r in rows:
        y = r['date'][:4]; d = out.setdefault(y, [0, r['book']]); d[0] += r['depreciation']; d[1] = r['book']
    return [(y, v[0], v[1]) for y, v in sorted(out.items())]


def weekly(con, kind, weeks=12):
    """Income or spending per week for the last `weeks` weeks, oldest first, in the base currency (for the small trend lines)."""
    import datetime as dt
    t = today(); start = t - dt.timedelta(days=t.weekday() + 7 * (weeks - 1)); out = [0] * weeks; miss = set()
    for r in con.execute("SELECT t.date AS d, a.currency AS cur, t.amount AS amt, t.fee AS fee FROM transactions t JOIN accounts a ON a.id=t.account_id "
                         "WHERE t.kind=? AND t.date>=?", (kind, start.isoformat())):
        try: i = (dt.date.fromisoformat(r['d'][:10]) - start).days // 7
        except ValueError: continue
        if 0 <= i < weeks: out[i] += _conv(con, r['amt'] - r['fee'] if kind == 'income' else r['amt'] + r['fee'], r['cur'], miss)
    return out
