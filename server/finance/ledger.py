"""Accounts, daily transactions (income / expense) and transfers between accounts (including currency exchange)."""
import sqlite3
from . import currency
from .db import category_id
from .util import iso, today, parse_date

KINDS = [('cash', 'Cash'), ('bank', 'Bank'), ('wallet', 'Wallet / mobile money'), ('savings', 'Savings'), ('emergency', 'Emergency fund'), ('other', 'Other')]
COLORS = ['#1F7A5C', '#2F6FDE', '#D4533B', '#8B5CF6', '#E0A100', '#0E8FA3', '#C2417A', '#6B7280']


def _now(): return iso(today())


# ───────────────────────── accounts ─────────────────────────
def accounts(con, include_archived=False):
    q = 'SELECT * FROM accounts' + ('' if include_archived else ' WHERE archived=0') + ' ORDER BY archived, sort, name COLLATE NOCASE'
    return con.execute(q).fetchall()


def account(con, aid): return con.execute('SELECT * FROM accounts WHERE id=?', (aid,)).fetchone()


def add_account(con, name, cur, kind='bank', opening=0, color=None, note=''):
    name = (name or '').strip(); cur = (cur or '').strip().upper()
    if not name: raise ValueError('Give the account a name')
    if not cur: raise ValueError('Choose a currency')
    if con.execute('SELECT 1 FROM accounts WHERE name=? COLLATE NOCASE', (name,)).fetchone(): raise ValueError(f'You already have an account called “{name}”')
    if color is None: color = COLORS[con.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] % len(COLORS)]
    c = con.execute('INSERT INTO accounts(name, currency, kind, opening, color, note, sort, created) VALUES(?,?,?,?,?,?,(SELECT COALESCE(MAX(sort),0)+1 FROM accounts),?)',
                    (name, cur, kind, opening, color, note, _now()))
    con.commit(); return c.lastrowid


def update_account(con, aid, name, kind, opening, color, note=''):
    """The currency of an account that already has activity cannot change."""
    name = (name or '').strip()
    if not name: raise ValueError('Give the account a name')
    if con.execute('SELECT 1 FROM accounts WHERE name=? COLLATE NOCASE AND id<>?', (name, aid)).fetchone(): raise ValueError(f'You already have an account called “{name}”')
    con.execute('UPDATE accounts SET name=?, kind=?, opening=?, color=?, note=? WHERE id=?', (name, kind, opening, color, note, aid)); con.commit()


def set_archived(con, aid, flag): con.execute('UPDATE accounts SET archived=? WHERE id=?', (1 if flag else 0, aid)); con.commit()


def has_activity(con, aid):
    return bool(con.execute('SELECT (SELECT COUNT(*) FROM transactions WHERE account_id=?) + (SELECT COUNT(*) FROM transfers WHERE from_account_id=? OR to_account_id=?)'
                            ' + (SELECT COUNT(*) FROM subscriptions WHERE account_id=?)', (aid, aid, aid, aid)).fetchone()[0])


def delete_account(con, aid):
    if has_activity(con, aid): raise ValueError('This account has entries. Archive it instead (its history stays).')
    con.execute('DELETE FROM accounts WHERE id=?', (aid,)); con.commit()


BALANCE_SQL = """
SELECT a.id AS id, a.opening
 + COALESCE((SELECT SUM(CASE t.kind WHEN 'income' THEN t.amount - t.fee ELSE -(t.amount + t.fee) END) FROM transactions t WHERE t.account_id = a.id), 0)
 + COALESCE((SELECT SUM(f.amount_in) FROM transfers f WHERE f.to_account_id = a.id), 0)
 - COALESCE((SELECT SUM(f.amount_out + f.fee) FROM transfers f WHERE f.from_account_id = a.id), 0) AS balance
FROM accounts a"""


def balances(con): return {r['id']: r['balance'] for r in con.execute(BALANCE_SQL)}


def balance(con, aid): return balances(con).get(aid, 0)


# ───────────────────────── transactions ─────────────────────────
def net_effect(kind, amount, fee): return amount - fee if kind == 'income' else -(amount + fee)


def _check_tx(con, date, account_id, kind, amount, fee):
    if kind not in ('income', 'expense'): raise ValueError('Choose income or expense')
    if amount <= 0: raise ValueError('The amount must be more than zero')
    if fee < 0: raise ValueError('The fee cannot be negative')
    if not account(con, account_id): raise ValueError('Choose an account')
    parse_date(date)


def add_transaction(con, date, account_id, kind, amount, fee=0, title='', category=None, note='', attachment=None, source='manual', source_id=None):
    _check_tx(con, date, account_id, kind, amount, fee)
    c = con.execute('INSERT INTO transactions(date, account_id, kind, title, amount, fee, category_id, note, attachment, source, source_id, created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (date, account_id, kind, (title or '').strip(), amount, fee, category, note, attachment, source, source_id, _now()))
    con.commit(); return c.lastrowid


def update_transaction(con, tid, date, account_id, kind, amount, fee=0, title='', category=None, note='', attachment=None):
    _check_tx(con, date, account_id, kind, amount, fee)
    con.execute('UPDATE transactions SET date=?, account_id=?, kind=?, title=?, amount=?, fee=?, category_id=?, note=?, attachment=? WHERE id=?',
                (date, account_id, kind, (title or '').strip(), amount, fee, category, note, attachment, tid)); con.commit()


def delete_transaction(con, tid):
    con.execute("UPDATE sub_charges SET state='skipped', transaction_id=NULL WHERE transaction_id=?", (tid,))     # a deleted subscription charge is not re-created
    con.execute('DELETE FROM transactions WHERE id=?', (tid,)); con.commit()


def transaction(con, tid): return con.execute('SELECT * FROM transactions WHERE id=?', (tid,)).fetchone()


def list_transactions(con, month=None, account_id=None, kind=None, category=None, search='', date_from=None, date_to=None, limit=None):
    q = ("SELECT t.*, a.name AS account_name, a.currency AS currency, a.color AS account_color, c.name AS category_name,"
         " CASE t.kind WHEN 'income' THEN t.amount - t.fee ELSE -(t.amount + t.fee) END AS net"
         " FROM transactions t JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id WHERE 1=1")
    p = []
    if month: q += ' AND substr(t.date,1,7)=?'; p.append(month)
    if date_from: q += ' AND t.date>=?'; p.append(date_from)
    if date_to: q += ' AND t.date<=?'; p.append(date_to)
    if account_id: q += ' AND t.account_id=?'; p.append(account_id)
    if kind: q += ' AND t.kind=?'; p.append(kind)
    if category: q += ' AND t.category_id=?'; p.append(category)
    if search:
        q += ' AND (t.title LIKE ? OR t.note LIKE ? OR c.name LIKE ? OR a.name LIKE ?)'; p += [f'%{search}%'] * 4
    q += ' ORDER BY t.date DESC, t.id DESC'
    if limit: q += f' LIMIT {int(limit)}'
    return con.execute(q, p).fetchall()


def categories(con, kind=None):
    if kind: return con.execute('SELECT * FROM categories WHERE kind=? ORDER BY name COLLATE NOCASE', (kind,)).fetchall()
    return con.execute('SELECT * FROM categories ORDER BY kind, name COLLATE NOCASE').fetchall()


def add_category(con, name, kind):
    name = (name or '').strip()
    if not name: raise ValueError('Give the category a name')
    return category_id(con, name, kind)


def delete_category(con, cid): con.execute('DELETE FROM categories WHERE id=?', (cid,)); con.commit()


# ───────────────────────── transfers (also currency exchange) ─────────────────────────
def _check_transfer(con, date, frm, to, out, inn, fee):
    parse_date(date)
    if frm == to: raise ValueError('Choose two different accounts')
    a, b = account(con, frm), account(con, to)
    if not a or not b: raise ValueError('Choose both accounts')
    if out <= 0: raise ValueError('The amount must be more than zero')
    if fee < 0: raise ValueError('The fee cannot be negative')
    if a['currency'] == b['currency']:
        if inn not in (None, 0, out): raise ValueError('Both accounts use the same currency, so the amounts must match')
        inn = out
    else:
        if not inn or inn <= 0: raise ValueError(f"Enter how much arrives in {b['name']} ({b['currency']})")
    return a, b, inn


def _learn_rate(con, a, b, out, inn):
    """An exchange teaches Curio the rate between your currency and the base currency."""
    base = currency.base(con)
    if a['currency'] == b['currency']: return None
    if b['currency'] == base: currency.set_rate(con, a['currency'], inn / out, 'exchange'); return inn / out
    if a['currency'] == base: currency.set_rate(con, b['currency'], out / inn, 'exchange'); return out / inn
    return None


def add_transfer(con, date, frm, to, amount_out, amount_in=None, fee=0, note='', title=''):
    a, b, inn = _check_transfer(con, date, frm, to, amount_out, amount_in, fee)
    rate = inn / amount_out if a['currency'] != b['currency'] else None
    c = con.execute('INSERT INTO transfers(date, from_account_id, to_account_id, amount_out, amount_in, fee, rate, note, created, title) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (date, frm, to, amount_out, inn, fee, rate, note, _now(), (title or '').strip()))
    _learn_rate(con, a, b, amount_out, inn); con.commit(); return c.lastrowid


def update_transfer(con, tid, date, frm, to, amount_out, amount_in=None, fee=0, note='', title=None):
    a, b, inn = _check_transfer(con, date, frm, to, amount_out, amount_in, fee)
    rate = inn / amount_out if a['currency'] != b['currency'] else None
    con.execute('UPDATE transfers SET date=?, from_account_id=?, to_account_id=?, amount_out=?, amount_in=?, fee=?, rate=?, note=? WHERE id=?',
                (date, frm, to, amount_out, inn, fee, rate, note, tid))
    if title is not None: con.execute('UPDATE transfers SET title=? WHERE id=?', ((title or '').strip(), tid))      # None = keep the name it has
    con.commit()


def delete_transfer(con, tid): con.execute('DELETE FROM transfers WHERE id=?', (tid,)); con.commit()


def transfer(con, tid): return con.execute('SELECT * FROM transfers WHERE id=?', (tid,)).fetchone()


def list_transfers(con, month=None, account_id=None, search='', limit=None):
    q = ("SELECT f.*, a.name AS from_name, a.currency AS from_cur, a.color AS from_color, b.name AS to_name, b.currency AS to_cur, b.color AS to_color,"
         " (SELECT g.name FROM goal_contributions gc JOIN goals g ON g.id=gc.goal_id WHERE gc.transfer_id=f.id) AS goal_name"
         " FROM transfers f JOIN accounts a ON a.id=f.from_account_id JOIN accounts b ON b.id=f.to_account_id WHERE 1=1")
    p = []
    if month: q += ' AND substr(f.date,1,7)=?'; p.append(month)
    if account_id: q += ' AND (f.from_account_id=? OR f.to_account_id=?)'; p += [account_id, account_id]
    if search: q += ' AND (f.note LIKE ? OR f.title LIKE ? OR a.name LIKE ? OR b.name LIKE ?)'; p += [f'%{search}%'] * 4
    q += ' ORDER BY f.date DESC, f.id DESC'
    if limit: q += f' LIMIT {int(limit)}'
    return con.execute(q, p).fetchall()


# ───────────────────────── one account's story ─────────────────────────
def statement(con, aid):
    """Every movement of one account, oldest first, with the balance after each → list of dicts."""
    a = account(con, aid); rows = []
    for t in con.execute('SELECT * FROM transactions WHERE account_id=?', (aid,)):
        rows.append(dict(date=t['date'], id=t['id'], what='income' if t['kind'] == 'income' else 'expense', title=t['title'], delta=net_effect(t['kind'], t['amount'], t['fee'])))
    for f in con.execute('SELECT f.*, a.name AS fn, b.name AS tn FROM transfers f JOIN accounts a ON a.id=f.from_account_id JOIN accounts b ON b.id=f.to_account_id '
                         'WHERE from_account_id=? OR to_account_id=?', (aid, aid)):
        if f['to_account_id'] == aid: rows.append(dict(date=f['date'], id=f['id'], what='transfer_in', title=f"from {f['fn']}", delta=f['amount_in']))
        if f['from_account_id'] == aid: rows.append(dict(date=f['date'], id=f['id'], what='transfer_out', title=f"to {f['tn']}", delta=-(f['amount_out'] + f['fee'])))
    rows.sort(key=lambda r: (r['date'], r['what'], r['id']))
    run = a['opening']
    for r in rows: run += r['delta']; r['balance'] = run
    return rows


def set_category_color(con, cid, color):
    """A colour for a category (None = no colour). Used for the dots and chips in lists, charts and the calendar."""
    con.execute('UPDATE categories SET color=? WHERE id=?', (color or None, cid)); con.commit()


def set_time(con, table, rid, time):
    """the optional time of day of a transaction or transfer ('' = none)"""
    if table not in ('transactions', 'transfers'): raise ValueError(table)
    con.execute(f'UPDATE {table} SET time=? WHERE id=?', (time or '', rid)); con.commit()
