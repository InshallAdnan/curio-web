"""Finance for Curio Web — the desktop app's own money rules (server/finance/*), behind one JSON call.

POST /api/fin  {"op": "...", "args": {...}}  →  {"ok": true, "data": ...}  or  {"error": "..."}
Amounts travel as minor units (paisa) when they come from the server, and as text the way you typed them
("12,500" / "1250.50") when they go to it."""
import calendar, csv, io, json, os, sqlite3, tempfile
from datetime import timedelta

from tdb import Snapshot
from finance import ledger, goals, subs, assets as A, reports, currency, db as fdb, backup
from finance.money import parse_amount, to_minor, fmt
from finance.util import this_month, month_label, short_month, add_months, ym, today, iso, month_bounds

TABLES = ['settings', 'accounts', 'categories', 'transactions', 'transfers', 'goals', 'goal_contributions', 'subscriptions', 'sub_periods',
          'sub_charges', 'assets', 'asset_events', 'rates', 'rate_history']
BOOK = Snapshot('finance', TABLES)
CAT_COLORS = ['#2F6FDE', '#D4533B', '#1F7A5C', '#8B5CF6', '#E0A100', '#0E8FA3', '#C2417A', '#6B7280', '#F2602D', '#3CC08C']


# ───────────────────────── the book ─────────────────────────
def _prepare(con):
    """Same start as the desktop's finance.db.connect: a new book gets the tables, categories and base currency."""
    con.execute('PRAGMA foreign_keys = ON')
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone():
        for stmt in [s.strip() for s in fdb.SCHEMA.split(';') if s.strip()]: con.execute(stmt)
        con.executemany('INSERT INTO categories(name, kind) VALUES(?,?)', fdb.DEFAULT_CATEGORIES)
        fdb.set_setting(con, 'base_currency', 'PKR'); fdb.set_setting(con, 'auto_post_subs', '1')
        con.execute('INSERT INTO rates(currency, rate, updated, source) VALUES(?,?,?,?)', ('PKR', 1.0, iso(today()), 'base'))
    tcols = [r[1] for r in con.execute('PRAGMA table_info(transfers)')]
    if 'title' not in tcols: con.execute("ALTER TABLE transfers ADD COLUMN title TEXT NOT NULL DEFAULT ''")
    if 'time' not in tcols: con.execute("ALTER TABLE transfers ADD COLUMN time TEXT NOT NULL DEFAULT ''")
    if 'time' not in [r[1] for r in con.execute('PRAGMA table_info(transactions)')]:
        con.execute("ALTER TABLE transactions ADD COLUMN time TEXT NOT NULL DEFAULT ''")
    con.commit()


def run(fn):
    def go(con):
        _prepare(con); return fn(con)
    return BOOK.run(go)


# ───────────────────────── helpers ─────────────────────────
def M(v, allow_zero=True):
    """typed amount → minor units"""
    if v is None or v == '': return 0
    if isinstance(v, (int, float)) and not isinstance(v, bool): return to_minor(v)
    return parse_amount(str(v))


def I(v): return int(v) if v not in (None, '', 'null') else None


def D(r): return dict(r) if r is not None else None


def L(rows): return [dict(r) for r in rows]


def base(con): return currency.base(con)


def setting(con, k, d=''): return fdb.get_setting(con, k, d)


def meta(con):
    bal = ledger.balances(con)
    return dict(base=base(con), today=iso(today()), month=this_month(),
                accounts=[dict(D(a), balance=bal.get(a['id'], 0)) for a in ledger.accounts(con, True)],
                categories=L(ledger.categories(con)), goals=L(goals.list_goals(con)), kinds=ledger.KINDS, colors=ledger.COLORS,
                currencies=currency.currencies_in_use(con), cat_colors=CAT_COLORS,
                settings={k: setting(con, k, '') for k in ('spend_limit', 'emergency_account', 'emergency_months', 'overview_hidden', 'auto_post_subs')})


# ───────────────────────── views ─────────────────────────
def overview(con, args):
    if setting(con, 'auto_post_subs', '1') == '1' and subs.due_charges(con): subs.post_due(con)
    accs = ledger.accounts(con, True)
    if not accs: return dict(empty=True, meta=meta(con))
    b = base(con); m = this_month(); t = today()
    nw = reports.net_worth(con); ms = reports.month_summary(con, m); last = reports.month_summary(con, add_months(m, -1))
    six = reports.series(con, 7)[:-1]
    avg_i = sum(x['income'] for x in six) / 6; avg_e = sum(x['expense'] for x in six) / 6
    spent = [x['expense'] for x in six if x['expense']]; avg_spent = sum(spent) / len(spent) if spent else 0
    em_months = int(setting(con, 'emergency_months', '6') or 6); em_aid = int(setting(con, 'emergency_account', '0') or 0)
    em = None
    if em_aid and ledger.account(con, em_aid):
        a = ledger.account(con, em_aid); have = ledger.balance(con, em_aid)
        em = dict(account=D(a), have=have, target=avg_spent * em_months, cover=(have / avg_spent if avg_spent else 0))
    kind = args.get('where', 'expense')
    rows = reports.category_breakdown(con, m, kind); cols = {r['name']: r['color'] for r in ledger.categories(con, kind) if r['color']}
    where = [[n, v, cols.get(n) or CAT_COLORS[i % len(CAT_COLORS)]] for i, (n, v) in enumerate(rows)]
    if len(where) > 7: where = where[:6] + [['Other', sum(v for _, v, _ in where[6:]), '#868E96']]
    m0, m1 = month_bounds(m)
    ups = []
    for s in subs.list_subscriptions(con):
        if subs.effective_state(con, s) == 'active':
            n = subs.next_charge(con, s)
            if n: ups.append(dict(name=s['name'], date=iso(n[1]), cost=s['cost'], currency=s['currency']))
    ups.sort(key=lambda x: x['date'])
    al = [a for a in A.list_assets(con) if a['status'] == 'active']
    return dict(
        meta=meta(con), net=nw, month=ms, last=last, avg_income=avg_i, avg_expense=avg_e, avg_spent=avg_spent,
        days_left=calendar.monthrange(t.year, t.month)[1] - t.day + 1,
        flow=[dict(month=x['month'], label=short_month(x['month']), full=month_label(x['month']), income=x['income'], expense=x['expense']) for x in reports.series(con, 12)],
        weekly_income=reports.weekly(con, 'income', 12), weekly_expense=reports.weekly(con, 'expense', 12),
        emergency=em, emergency_months=em_months, where=where, where_kind=kind,
        due=subs.due_charges(con), recent=L(ledger.list_transactions(con, limit=6)),
        goals=[dict(D(g), progress=goals.progress(g)) for g in goals.list_goals(con)[:5]],
        subs_monthly=reports.subscriptions_monthly(con), subs_next=ups[:4],
        depr_month=reports.depreciation_between(con, iso(m0), iso(m1)), depr_year=reports.depreciation_between(con, f'{t.year}-01-01', f'{t.year}-12-31'),
        assets=dict(count=len(al), worth=nw['assets'], monthly=reports.assets_monthly_depreciation(con)))


def transactions(con, args):
    rows = ledger.list_transactions(con, month=args.get('month') or None, account_id=I(args.get('account')), kind=args.get('kind') or None,
                                    category=I(args.get('category')), search=(args.get('search') or '').strip())
    rows = L(rows); b = base(con); inc = exp = 0
    for r in rows:
        v = currency.to_base(con, abs(r['net']), r['currency']) or 0
        if r['kind'] == 'income': inc += v
        else: exp += v
    return dict(rows=rows, income=inc, expense=exp, meta=meta(con))


def transfers(con, args):
    return dict(rows=L(ledger.list_transfers(con, month=args.get('month') or None, account_id=I(args.get('account')), search=(args.get('search') or '').strip())), meta=meta(con))


def accounts(con, args):
    bal = ledger.balances(con); m = this_month(); out = []
    for a in ledger.accounts(con, True):
        r = con.execute("SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount-fee ELSE 0 END),0), COALESCE(SUM(CASE WHEN kind='expense' THEN amount+fee ELSE 0 END),0) "
                        "FROM transactions WHERE account_id=? AND substr(date,1,7)=?", (a['id'], m)).fetchone()
        out.append(dict(D(a), balance=bal.get(a['id'], 0), month_in=r[0], month_out=r[1], active=ledger.has_activity(con, a['id'])))
    return dict(rows=out, meta=meta(con))


def statement(con, args):
    aid = I(args['account']); a = ledger.account(con, aid)
    return dict(account=D(a), rows=list(reversed(ledger.statement(con, aid))), balance=ledger.balance(con, aid))


def goal_state(g):
    if g['completed']: return 'done'
    if g['due'] and g['due'] < iso(today()) and g['saved'] < g['target']: return 'failed'
    return 'open'


def goals_view(con, args):
    gs = [dict(D(g), progress=goals.progress(g), state=goal_state(g)) for g in goals.list_goals(con) + goals.list_goals(con, True)]
    return dict(rows=gs, meta=meta(con))


def goal_history(con, args):
    gid = I(args['goal']); g = goals.goal(con, gid)
    rows = []
    for c in goals.contributions(con, gid):
        d = D(c)
        if c['transfer_id']:
            f = con.execute('SELECT f.*, a.name AS fn, b.name AS tn FROM transfers f JOIN accounts a ON a.id=f.from_account_id JOIN accounts b ON b.id=f.to_account_id WHERE f.id=?', (c['transfer_id'],)).fetchone()
            if f: d['from_name'], d['to_name'] = f['fn'], f['tn']
        rows.append(d)
    return dict(goal=dict(D(g), progress=goals.progress(g), state=goal_state(g)), rows=rows)


def subs_view(con, args):
    out = []
    for s in subs.list_subscriptions(con):
        st = subs.effective_state(con, s); n = subs.next_charge(con, s) if st in ('active', 'scheduled') else None
        out.append(dict(D(s), state=st, next=iso(n[1]) if n else None, next_month=n[0] if n else None, monthly=subs.monthly_equivalent(s),
                        periods=L(subs.periods(con, s['id']))))
    return dict(rows=out, monthly=reports.subscriptions_monthly(con), due=subs.due_charges(con), meta=meta(con))


def sub_history(con, args):
    sid = I(args['sub'])
    return dict(sub=D(subs.subscription(con, sid)), charges=L(subs.charges(con, sid)), periods=L(subs.periods(con, sid)))


def assets_view(con, args):
    out = []
    for a in A.list_assets(con):
        evs = A.events(con, a['id']); st = A.status(a, evs)
        out.append(dict(D(a), status_info=st, events=L(evs), years=reports.depreciation_by_year(con, a)))
    return dict(rows=out, monthly=reports.assets_monthly_depreciation(con), meta=meta(con))


def reports_view(con, args):
    m = args.get('month') or this_month(); n = int(args.get('months') or 12)
    return dict(series=reports.series(con, n, m), month=reports.month_summary(con, m), net=reports.net_worth(con),
                expense=reports.category_breakdown(con, m, 'expense'), income=reports.category_breakdown(con, m, 'income'),
                subs_monthly=reports.subscriptions_monthly(con), depr_monthly=reports.assets_monthly_depreciation(con), label=month_label(m), meta=meta(con))


def settings_view(con, args):
    rates = L(con.execute('SELECT * FROM rates ORDER BY currency'))
    counts = {t: con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('accounts', 'transactions', 'transfers', 'goals', 'subscriptions', 'assets')}
    return dict(rates=rates, counts=counts, meta=meta(con))


# ───────────────────────── changes ─────────────────────────
def tx_save(con, a):
    cat = I(a.get('category'))
    if not cat and (a.get('category_name') or '').strip(): cat = ledger.add_category(con, a['category_name'], a['kind'])
    vals = (a['date'], I(a['account']), a['kind'], M(a['amount']), M(a.get('fee')), a.get('title', ''), cat, a.get('note', ''))
    if a.get('id'): tid = I(a['id']); ledger.update_transaction(con, tid, *vals, attachment=(ledger.transaction(con, tid) or {'attachment': None})['attachment'])
    else: tid = ledger.add_transaction(con, *vals)
    ledger.set_time(con, 'transactions', tid, a.get('time') or '')
    return tid


def tx_bulk(con, a):
    """change many transactions at once: date / category / account; or delete them"""
    ids = [I(x) for x in a.get('ids') or []]
    if a.get('delete'):
        for t in ids: ledger.delete_transaction(con, t)
        return len(ids)
    for t in ids:
        r = ledger.transaction(con, t)
        if not r: continue
        ledger.update_transaction(con, t, a.get('date') or r['date'], I(a['account']) if a.get('account') else r['account_id'], r['kind'], r['amount'], r['fee'], r['title'],
                                  I(a['category']) if a.get('category') else r['category_id'], r['note'], r['attachment'])
    return len(ids)


def tf_save(con, a):
    out = M(a['amount_out']); inn = M(a['amount_in']) if a.get('amount_in') not in (None, '') else None
    vals = (a['date'], I(a['from']), I(a['to']), out, inn, M(a.get('fee')))
    if a.get('id'): tid = I(a['id']); ledger.update_transfer(con, tid, *vals, note=a.get('note', ''), title=a.get('title', ''))
    else: tid = ledger.add_transfer(con, *vals, note=a.get('note', ''), title=a.get('title', ''))
    ledger.set_time(con, 'transfers', tid, a.get('time') or '')
    goals.link_transfer(con, tid, I(a.get('goal')))
    return tid


def acc_save(con, a):
    color = a.get('color') or None
    if a.get('id'):
        aid = I(a['id']); ledger.update_account(con, aid, a['name'], a.get('kind', 'bank'), M(a.get('opening')), color, a.get('note', ''))
        return aid
    return ledger.add_account(con, a['name'], a.get('currency') or base(con), a.get('kind', 'bank'), M(a.get('opening')), color, a.get('note', ''))


def goal_save(con, a):
    vals = (a['name'], M(a['target']), M(a.get('initial')), a.get('due') or None, a.get('note', ''))
    if a.get('id'): gid = I(a['id']); goals.update_goal(con, gid, *vals); return gid
    return goals.add_goal(con, *vals, cur=a.get('currency') or None)


def sub_save(con, a):
    if a.get('id'):
        sid = I(a['id']); subs.update_subscription(con, sid, a['name'], M(a['cost']), I(a['account']), int(a.get('every') or 1), int(a.get('day') or 1), I(a.get('category')), a.get('note', ''))
        return sid
    months = int(a['months']) if a.get('months') else None
    return subs.add_subscription(con, a['name'], M(a['cost']), I(a['account']), a.get('start') or None, int(a.get('every') or 1), int(a.get('day') or 1), months,
                                 I(a.get('category')), a.get('note', ''), bool(a.get('backfill')))


def asset_save(con, a):
    vals = (a['name'], M(a['price']), a['date'], int(a['life']), M(a.get('salvage')), a.get('kind', ''), a.get('note', ''))
    if a.get('id'): aid = I(a['id']); A.update_asset(con, aid, *vals); return aid
    return A.add_asset(con, *vals, cur=a.get('currency') or None, pay_from=I(a.get('pay_from')))


def set_settings(con, a):
    for k in ('spend_limit',):
        if k in a: fdb.set_setting(con, k, str(M(a[k])))
    for k in ('emergency_account', 'emergency_months', 'overview_hidden', 'auto_post_subs'):
        if k in a: fdb.set_setting(con, k, str(a[k]))
    if a.get('base'): currency.set_base(con, a['base'])
    return True


def import_csv(con, a):
    fd, path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f: f.write(a.get('text') or '')
    try:
        r = backup.import_csv(con, path, I(a.get('account')))
        con.commit(); r['errors'] = r['errors'][:20]; return r
    finally: os.unlink(path)


def export_db(con, a):
    """the whole book as a finance.db file — open it in the desktop app (Finance › Settings › Restore)"""
    import base64
    fd, path = tempfile.mkstemp(suffix='.db'); os.close(fd)
    try:
        out = sqlite3.connect(path); con.backup(out); out.execute(f'PRAGMA user_version = {fdb.SCHEMA_VERSION}'); out.commit(); out.close()
        return base64.b64encode(open(path, 'rb').read()).decode()
    finally: os.unlink(path)


def export_csv(con, a):
    """every transaction and transfer as one CSV text (the same columns the importer reads)"""
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(['Date', 'Type', 'Title', 'Account', 'To account', 'Category', 'Amount', 'Fee', 'Note'])
    for t in ledger.list_transactions(con):
        w.writerow([t['date'], t['kind'].title(), t['title'], t['account_name'], '', t['category_name'] or '', t['amount'] / 100, t['fee'] / 100, t['note'] or ''])
    for f in ledger.list_transfers(con):
        w.writerow([f['date'], 'Transfer', f['title'], f['from_name'], f['to_name'], '', f['amount_out'] / 100, f['fee'] / 100, f['note'] or ''])
    return buf.getvalue()


OPS = {
    # views
    'meta': lambda con, a: meta(con), 'overview': overview, 'transactions': transactions, 'transfers': transfers, 'accounts': accounts,
    'statement': statement, 'goals': goals_view, 'goal_history': goal_history, 'subscriptions': subs_view, 'sub_history': sub_history,
    'assets': assets_view, 'reports': reports_view, 'settings': settings_view,
    # transactions
    'tx_save': tx_save, 'tx_delete': lambda con, a: [ledger.delete_transaction(con, I(x)) for x in a['ids']] and True, 'tx_bulk': tx_bulk,
    'tx_get': lambda con, a: D(ledger.transaction(con, I(a['id']))),
    # transfers
    'tf_save': tf_save, 'tf_delete': lambda con, a: [ledger.delete_transfer(con, I(x)) for x in a['ids']] and True,
    'tf_get': lambda con, a: dict(D(ledger.transfer(con, I(a['id']))), goal=goals.goal_of_transfer(con, I(a['id']))),
    # accounts / categories
    'acc_save': acc_save, 'acc_archive': lambda con, a: ledger.set_archived(con, I(a['id']), bool(a.get('on'))) or True,
    'acc_delete': lambda con, a: ledger.delete_account(con, I(a['id'])) or True,
    'cat_add': lambda con, a: ledger.add_category(con, a['name'], a['kind']), 'cat_delete': lambda con, a: ledger.delete_category(con, I(a['id'])) or True,
    'cat_color': lambda con, a: ledger.set_category_color(con, I(a['id']), a.get('color')) or True,
    # goals
    'goal_save': goal_save, 'goal_delete': lambda con, a: goals.delete_goal(con, I(a['id'])) or True,
    'goal_add_money': lambda con, a: goals.add_contribution(con, I(a['id']), a['date'], M(a['amount']), a.get('note', ''), I(a.get('from')), I(a.get('to'))),
    'goal_del_money': lambda con, a: goals.delete_contribution(con, I(a['id']), bool(a.get('keep_transfer'))) or True,
    'goal_complete': lambda con, a: goals.complete_goal(con, I(a['id']), a.get('date') or None, I(a.get('account')), M(a['amount']) if a.get('amount') else None) or True,
    'goal_reopen': lambda con, a: goals.reopen_goal(con, I(a['id'])) or True,
    # subscriptions
    'sub_save': sub_save, 'sub_delete': lambda con, a: subs.delete_subscription(con, I(a['id'])) or True,
    'sub_pause': lambda con, a: subs.pause(con, I(a['id']), a.get('month') or this_month()) or True,
    'sub_end': lambda con, a: subs.end_subscription(con, I(a['id']), a.get('month') or this_month()) or True,
    'sub_resume': lambda con, a: subs.resume(con, I(a['id']), a.get('month') or None, int(a['months']) if a.get('months') else None) or True,
    'sub_skip': lambda con, a: subs.skip_charge(con, I(a['id']), a['month']) or True,
    'sub_post_due': lambda con, a: len(subs.post_due(con)),
    # assets
    'asset_save': asset_save, 'asset_delete': lambda con, a: A.delete_asset(con, I(a['id'])) or True,
    'asset_event': lambda con, a: A.add_event(con, I(a['id']), a['date'], a['kind'], M(a['cost']), int(a.get('extend') or 0), a.get('note', ''), I(a.get('pay_from'))),
    'asset_event_delete': lambda con, a: A.delete_event(con, I(a['id']), bool(a.get('delete_expense'))) or True,
    'asset_sell': lambda con, a: A.sell_asset(con, I(a['id']), a['date'], M(a.get('price')), I(a.get('deposit_to'))) or True,
    'asset_unsell': lambda con, a: A.unsell_asset(con, I(a['id'])) or True,
    # money & settings
    'set_rate': lambda con, a: currency.set_rate(con, a['currency'].upper().strip(), float(a['rate'])) or True,
    'settings_set': set_settings, 'import_csv': import_csv, 'export_db': export_db, 'export_csv': export_csv,
}


def call(op, args):
    f = OPS.get(op)
    if f is None: raise ValueError(f'Unknown action: {op}')
    return run(lambda con: f(con, args or {}))
