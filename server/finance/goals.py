"""Purchasing goals. Tick a goal and it moves to the Completed list with the date — nothing to wire."""
from . import ledger, currency
from .db import category_id
from .util import iso, today, parse_date

GOAL_SQL = ("SELECT g.*, g.initial + COALESCE((SELECT SUM(c.amount) FROM goal_contributions c WHERE c.goal_id=g.id), 0) AS saved FROM goals g")


def _now(): return iso(today())


def goal(con, gid): return con.execute(GOAL_SQL + ' WHERE g.id=?', (gid,)).fetchone()


def list_goals(con, completed=False):
    if completed: return con.execute(GOAL_SQL + ' WHERE g.completed=1 ORDER BY g.completed_on DESC, g.id DESC').fetchall()
    return con.execute(GOAL_SQL + ' WHERE g.completed=0 ORDER BY g.sort, g.id').fetchall()


def add_goal(con, name, target, initial=0, due=None, note='', cur=None):
    name = (name or '').strip()
    if not name: raise ValueError('Give the goal a name')
    if target <= 0: raise ValueError('Enter the amount you need')
    if due: parse_date(due)
    c = con.execute('INSERT INTO goals(name, target, initial, currency, due, note, sort, created) VALUES(?,?,?,?,?,?,(SELECT COALESCE(MAX(sort),0)+1 FROM goals),?)',
                    (name, target, initial, cur or currency.base(con), due or None, note, _now()))
    con.commit(); return c.lastrowid


def update_goal(con, gid, name, target, initial=0, due=None, note=''):
    name = (name or '').strip()
    if not name: raise ValueError('Give the goal a name')
    if target <= 0: raise ValueError('Enter the amount you need')
    con.execute('UPDATE goals SET name=?, target=?, initial=?, due=?, note=? WHERE id=?', (name, target, initial, due or None, note, gid)); con.commit()


def delete_goal(con, gid):
    ids = [r[0] for r in con.execute('SELECT transfer_id FROM goal_contributions WHERE goal_id=? AND transfer_id IS NOT NULL', (gid,))]
    con.execute('DELETE FROM goals WHERE id=?', (gid,))                      # contributions go with it; the money transfers stay (they really happened)
    con.commit()


def contributions(con, gid): return con.execute('SELECT * FROM goal_contributions WHERE goal_id=? ORDER BY date DESC, id DESC', (gid,)).fetchall()


def add_contribution(con, gid, date, amount, note='', from_account=None, to_account=None):
    """Put money towards a goal. Give both accounts to also move the money (a real transfer is created); give none to just earmark it."""
    g = goal(con, gid)
    if not g: raise ValueError('Goal not found')
    parse_date(date)
    if amount == 0: raise ValueError('Enter an amount')
    tid = None
    if from_account or to_account:
        if not (from_account and to_account): raise ValueError('To move money, choose both accounts — or choose neither to just note it')
        if amount < 0: raise ValueError('Taking money back cannot move accounts; leave the accounts empty')
        for a in (from_account, to_account):
            if ledger.account(con, a)['currency'] != g['currency']: raise ValueError(f"This goal is in {g['currency']}; use accounts in {g['currency']}")
        tid = ledger.add_transfer(con, date, from_account, to_account, amount, None, 0, f"For goal: {g['name']}" + (f' — {note}' if note else ''))
    c = con.execute('INSERT INTO goal_contributions(goal_id, date, amount, note, transfer_id) VALUES(?,?,?,?,?)', (gid, date, amount, note, tid))
    con.commit(); return c.lastrowid


def delete_contribution(con, cid, keep_transfer=False):
    r = con.execute('SELECT transfer_id FROM goal_contributions WHERE id=?', (cid,)).fetchone()
    con.execute('DELETE FROM goal_contributions WHERE id=?', (cid,))
    if r and r['transfer_id'] and not keep_transfer: con.execute('DELETE FROM transfers WHERE id=?', (r['transfer_id'],))
    con.commit()


def complete_goal(con, gid, on_date=None, expense_account=None, expense_amount=None):
    """Mark as bought. Optionally record the purchase as an expense from an account."""
    g = goal(con, gid)
    on_date = on_date or _now(); parse_date(on_date)
    if expense_account:
        amt = expense_amount if expense_amount else g['target']
        ledger.add_transaction(con, on_date, expense_account, 'expense', amt, 0, g['name'], category_id(con, 'Shopping', 'expense'), 'Bought from a goal', None, 'goal', gid)
    con.execute('UPDATE goals SET completed=1, completed_on=? WHERE id=?', (on_date, gid)); con.commit()


def reopen_goal(con, gid): con.execute('UPDATE goals SET completed=0, completed_on=NULL WHERE id=?', (gid,)); con.commit()


def progress(g): return 0.0 if not g['target'] else max(0.0, min(1.0, g['saved'] / g['target']))


def goal_of_transfer(con, tid):
    r = con.execute('SELECT goal_id FROM goal_contributions WHERE transfer_id=?', (tid,)).fetchone()
    return r[0] if r else None


def link_transfer(con, tid, gid):
    """Tie a transfer to a goal (or untie it with gid=None). The goal then counts the money that was moved."""
    t = con.execute('SELECT date, amount_out, title, note FROM transfers WHERE id=?', (tid,)).fetchone()
    old = con.execute('SELECT id, goal_id FROM goal_contributions WHERE transfer_id=?', (tid,)).fetchone()
    if old and (not gid or old['goal_id'] != gid): con.execute('DELETE FROM goal_contributions WHERE id=?', (old['id'],)); old = None
    if gid and t:
        if old: con.execute('UPDATE goal_contributions SET date=?, amount=? WHERE id=?', (t['date'], t['amount_out'], old['id']))
        else: con.execute('INSERT INTO goal_contributions(goal_id, date, amount, note, transfer_id) VALUES(?,?,?,?,?)', (gid, t['date'], t['amount_out'], t['title'] or t['note'] or '', tid))
    con.commit()
