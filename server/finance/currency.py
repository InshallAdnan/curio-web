"""Currencies: every rate is 'how many BASE-currency units are 1 unit of this currency' (base is PKR by default)."""
from .db import get_setting, set_setting
from .util import iso, today


def base(con): return get_setting(con, 'base_currency', 'PKR')


def rates(con): return {r['currency']: r['rate'] for r in con.execute('SELECT currency, rate FROM rates')}


def rate(con, cur):
    if cur == base(con): return 1.0
    r = con.execute('SELECT rate FROM rates WHERE currency=?', (cur,)).fetchone()
    return r[0] if r else None


def set_rate(con, cur, value, source='manual'):
    if cur == base(con): return
    value = float(value)
    if value <= 0: raise ValueError('The rate must be more than zero')
    con.execute('INSERT INTO rates(currency, rate, updated, source) VALUES(?,?,?,?) ON CONFLICT(currency) DO UPDATE SET rate=excluded.rate, updated=excluded.updated, source=excluded.source',
                (cur, value, iso(today()), source))
    con.execute('INSERT INTO rate_history(date, currency, rate, source) VALUES(?,?,?,?)', (iso(today()), cur, value, source)); con.commit()


def convert(con, minor, frm, to):
    """minor units of `frm` → minor units of `to`; None when a rate is missing"""
    if frm == to or minor == 0: return minor
    a, b = rate(con, frm), rate(con, to)
    if a is None or b is None: return None
    return int(round(minor * a / b))


def to_base(con, minor, cur): return convert(con, minor, cur, base(con))


def set_base(con, new_base):
    """Re-base all rates so they stay correct (e.g. PKR→USD)."""
    new_base = new_base.upper().strip(); old = base(con)
    if new_base == old: return
    nb = rate(con, new_base)
    if nb is None: raise ValueError(f'Set a rate for {new_base} first')
    for r in con.execute('SELECT currency, rate FROM rates').fetchall():
        con.execute('UPDATE rates SET rate=? WHERE currency=?', (r['rate'] / nb, r['currency']))
    con.execute('INSERT OR REPLACE INTO rates(currency, rate, updated, source) VALUES(?,?,?,?)', (new_base, 1.0, iso(today()), 'base'))
    set_setting(con, 'base_currency', new_base)


def currencies_in_use(con):
    out = {base(con)}
    for t, c in (('accounts', 'currency'), ('goals', 'currency'), ('assets', 'currency')):
        out |= {r[0] for r in con.execute(f'SELECT DISTINCT {c} FROM {t}')}
    return sorted(out)


