"""Assets and depreciation (straight-line, monthly). A repair is just a cost. An upgrade adds to the value and is spread over the time that is left
(optionally extending the life). Depreciation is not cash: it never touches an account balance."""
from fractions import Fraction
from math import floor
from . import ledger, currency
from .db import category_id
from .util import add_months_date, full_months_between, iso, today, parse_date

KINDS = ['Computer', 'Phone', 'Camera / gear', 'Vehicle', 'Furniture', 'Equipment', 'Other']


def _r(x): return int(floor(Fraction(x) + Fraction(1, 2)))


def asset(con, aid): return con.execute('SELECT * FROM assets WHERE id=?', (aid,)).fetchone()


def list_assets(con): return con.execute("SELECT * FROM assets ORDER BY status, purchase_date DESC, id DESC").fetchall()


def events(con, aid): return con.execute('SELECT * FROM asset_events WHERE asset_id=? ORDER BY date, id', (aid,)).fetchall()


# ───────────────────────── the engine ─────────────────────────
def _elapsed(a, d): return max(full_months_between(a['purchase_date'], d), 0)


def _segments(a, evs):
    life, salvage = a['life_months'], Fraction(a['salvage'])
    v = Fraction(a['price']); r = max(v - salvage, 0) / life
    segs = [dict(k0=0, v0=v, r=r, kend=life)]
    for e in sorted((e for e in evs if e['kind'] == 'upgrade'), key=lambda e: (e['date'], e['id'])):
        s = segs[-1]; ke = max(_elapsed(a, e['date']), s['k0'])
        cur = _seg_value(s, ke, salvage)
        remaining = max(s['kend'] - ke, 0) + (e['extend_months'] or 0)
        if remaining <= 0: remaining = 12                       # it was already fully written off: spread the upgrade over a year
        v2 = cur + e['cost']
        segs.append(dict(k0=ke, v0=v2, r=max(v2 - salvage, 0) / remaining, kend=ke + remaining))
    return segs


def _seg_value(s, k, salvage):
    return max(s['v0'] - s['r'] * (min(k, s['kend']) - s['k0']), Fraction(salvage))


def _seg_at(segs, k):
    seg = segs[0]
    for s in segs:
        if s['k0'] <= k: seg = s
    return seg


def schedule(a, evs):
    """month by month: [{k, date, depreciation, book, upgrade}]"""
    segs = _segments(a, evs); salvage = Fraction(a['salvage']); last = max(s['kend'] for s in segs); rows = []
    ups = {}
    for e in evs:
        if e['kind'] == 'upgrade': ups.setdefault(_elapsed(a, e['date']), []).append(e)
    for k in range(1, last + 1):
        sp = _seg_at(segs, k - 1)
        dep = _r(_seg_value(sp, k - 1, salvage)) - _r(_seg_value(sp, k, salvage))
        book = _r(_seg_value(_seg_at(segs, k), k, salvage))
        rows.append(dict(k=k, date=iso(add_months_date(a['purchase_date'], k)), depreciation=dep, book=book, upgrade=sum(e['cost'] for e in ups.get(k, []))))
    return rows


def status(a, evs, as_of=None):
    """where the asset stands today (or `as_of`) → dict"""
    as_of = iso(as_of) if as_of and not isinstance(as_of, str) else (as_of or iso(today()))
    sold = a['status'] == 'sold' and a['sold_date']
    end = a['sold_date'] if sold and as_of >= a['sold_date'] else as_of
    evs = [e for e in evs if e['date'] <= end]
    segs = _segments(a, evs); salvage = Fraction(a['salvage']); k = _elapsed(a, end)
    seg = _seg_at(segs, k)
    book = _r(_seg_value(seg, k, salvage)) if end >= a['purchase_date'] else a['price']
    capital = a['price'] + sum(e['cost'] for e in evs if e['kind'] == 'upgrade')
    repairs = sum(e['cost'] for e in evs if e['kind'] == 'repair')
    active = not sold and k < seg['kend']
    remaining = max(seg['kend'] - k, 0)
    depreciable = max(capital - a['salvage'], 0)
    out = dict(book=book, monthly=_r(seg['r']) if active else 0, accumulated=capital - book, capital=capital, repairs=repairs, total_cost=capital + repairs,
               elapsed=k, remaining=remaining, life_end=iso(add_months_date(a['purchase_date'], seg['kend'])),
               pct=(capital - book) / depreciable if depreciable else 1.0, fully=k >= seg['kend'], sold=bool(sold))
    if sold and a['sold_price'] is not None: out['gain'] = a['sold_price'] - book
    return out


# ───────────────────────── changes ─────────────────────────
def _check(name, price, date, life, salvage):
    if not (name or '').strip(): raise ValueError('Give the asset a name')
    if price <= 0: raise ValueError('Enter what it cost')
    parse_date(date)
    if life < 1: raise ValueError('How many months will it last? (at least 1)')
    if salvage < 0 or salvage > price: raise ValueError('The resale value cannot be more than the price')


def add_asset(con, name, price, purchase_date, life_months, salvage=0, kind='', note='', cur=None, pay_from=None):
    _check(name, price, purchase_date, life_months, salvage)
    c = con.execute('INSERT INTO assets(name, kind, currency, price, purchase_date, life_months, salvage, note, created) VALUES(?,?,?,?,?,?,?,?,?)',
                    (name.strip(), kind, cur or (ledger.account(con, pay_from)['currency'] if pay_from else currency.base(con)), price, purchase_date, life_months, salvage, note, iso(today())))
    aid = c.lastrowid
    if pay_from: ledger.add_transaction(con, purchase_date, pay_from, 'expense', price, 0, name.strip(), category_id(con, 'Equipment', 'expense'), 'Asset purchase', None, 'asset', aid)
    con.commit(); return aid


def update_asset(con, aid, name, price, purchase_date, life_months, salvage=0, kind='', note=''):
    _check(name, price, purchase_date, life_months, salvage)
    con.execute('UPDATE assets SET name=?, kind=?, price=?, purchase_date=?, life_months=?, salvage=?, note=? WHERE id=?', (name.strip(), kind, price, purchase_date, life_months, salvage, note, aid)); con.commit()


def delete_asset(con, aid):
    con.execute("UPDATE transactions SET source='manual', source_id=NULL WHERE source='asset' AND source_id=?", (aid,))
    con.execute('DELETE FROM assets WHERE id=?', (aid,)); con.commit()


def add_event(con, aid, date, kind, cost, extend_months=0, note='', pay_from=None):
    a = asset(con, aid); parse_date(date)
    if kind not in ('repair', 'upgrade'): raise ValueError('Choose repair or upgrade')
    if cost <= 0: raise ValueError('Enter the cost')
    if date < a['purchase_date']: raise ValueError('This is before the purchase date')
    if kind == 'upgrade' and extend_months < 0: raise ValueError('Extra months cannot be negative')
    tid = None
    if pay_from:
        tid = ledger.add_transaction(con, date, pay_from, 'expense', cost, 0, f"{a['name']} — {kind}", category_id(con, 'Repairs & Maintenance' if kind == 'repair' else 'Equipment', 'expense'),
                                     note, None, 'asset', aid)
    c = con.execute('INSERT INTO asset_events(asset_id, date, kind, cost, extend_months, note, transaction_id) VALUES(?,?,?,?,?,?,?)', (aid, date, kind, cost, extend_months if kind == 'upgrade' else 0, note, tid))
    con.commit(); return c.lastrowid


def delete_event(con, eid, delete_expense=False):
    r = con.execute('SELECT transaction_id FROM asset_events WHERE id=?', (eid,)).fetchone()
    con.execute('DELETE FROM asset_events WHERE id=?', (eid,))
    if r and r['transaction_id'] and delete_expense: con.execute('DELETE FROM transactions WHERE id=?', (r['transaction_id'],))
    con.commit()


def sell_asset(con, aid, date, price, deposit_to=None):
    a = asset(con, aid); parse_date(date)
    if date < a['purchase_date']: raise ValueError('The sale cannot be before the purchase')
    con.execute("UPDATE assets SET status='sold', sold_date=?, sold_price=? WHERE id=?", (date, price, aid))
    if deposit_to and price > 0: ledger.add_transaction(con, date, deposit_to, 'income', price, 0, f"Sold: {a['name']}", category_id(con, 'Other income', 'income'), '', None, 'asset', aid)
    con.commit()


def unsell_asset(con, aid): con.execute("UPDATE assets SET status='active', sold_date=NULL, sold_price=NULL WHERE id=?", (aid,)); con.commit()
