"""Finance inside Ask AI (web): ChatGPT sees the user's Finance book and can record money for him.

• Every message carries a short "book card" (accounts + balances, categories, this month, today) so the AI always knows
  what is in Finance. Money questions also get the details (two months, latest entries, transfers, bills, goals).
• The AI asks for older records with a ```curio {"find": …}``` block — the server looks them up and asks again.
• To record, the AI ends its answer with a ```curio {"actions": [...]}``` block. Nothing is written straight from the AI's
  text: every action is checked here (account / category matched to real ones, amount and date parsed) and shown as a card.
  It is saved when the user taps Save — or at once when he turned on "Save right away" in Settings › AI models.
• Only adds income / expenses / transfers. Never edits or deletes old records."""
import difflib, json, re
from datetime import date, timedelta

import fin
from finance import ledger, reports, currency, subs, goals
from finance.util import this_month, add_months, today, iso

BLOCK = re.compile(r'```\s*curio\s*\n(.*?)```', re.S | re.I)


def _m(v): return f'{(v or 0) / 100:,.0f}'


# ───────────────────────── what the AI sees ─────────────────────────
def book(con):
    accs = [a for a in ledger.accounts(con, True) if not a['archived']]
    if not accs: return ''
    b = currency.base(con); bal = ledger.balances(con); t = today(); m = this_month()
    s = reports.month_summary(con, m)
    spent_today = sum(abs(r['net']) for r in ledger.list_transactions(con, kind='expense', date_from=iso(t), date_to=iso(t)))
    cats = ledger.categories(con)
    lines = [f'Today: {iso(t)} ({t.strftime("%A")}). Main currency: {b}.',
             'Accounts (use these exact names): ' + '; '.join(f'"{a["name"]}" ({a["kind"]}, {a["currency"]}) balance {_m(bal.get(a["id"], 0))}' for a in accs),
             'Expense categories: ' + ', '.join(c['name'] for c in cats if c['kind'] == 'expense'),
             'Income categories: ' + ', '.join(c['name'] for c in cats if c['kind'] == 'income'),
             f'This month ({m}): income {_m(s["income"])}, spent {_m(s["expense"])}. Spent today: {_m(spent_today)}.']
    lim = fin.setting(con, 'spend_limit', '')
    if lim:
        try: lines.append(f'Monthly spending limit: {float(lim):,.0f} {b} (left: {float(lim) - s["expense"] / 100:,.0f}).')
        except ValueError: pass
    due = subs.due_charges(con)
    if due: lines.append(f'Subscription charges due and not posted yet: {len(due)}.')
    return '\n'.join(lines)


def details(con):
    accs = ledger.accounts(con, True)
    if not accs: return ''
    m = this_month(); out = []
    for mm in (m, add_months(m, -1)):
        s = reports.month_summary(con, mm)
        cats = reports.category_breakdown(con, mm, 'expense')[:10]
        out.append(f'{mm}: income {_m(s["income"])}, spent {_m(s["expense"])}. By category: ' + ', '.join(f'{n} {_m(v)}' for n, v in cats))
    out.append('Latest transactions (date time | account | kind | amount | category | title | note):')
    for r in map(dict, ledger.list_transactions(con, limit=40)):
        out.append(f'{r["date"]} {r.get("time") or ""} | {r["account_name"]} | {r["kind"]} | {_m(abs(r["net"]))} {r["currency"]} | {r.get("category_name") or ""} | {(r.get("title") or "")[:50]} | {(r.get("note") or "")[:40]}')
    tfs = [dict(x) for x in ledger.list_transfers(con)[:10]]
    if tfs:
        out.append('Latest transfers (date | from → to | amount | note):')
        for r in tfs:
            out.append(f'{r["date"]} | {r.get("from_name") or r.get("from_account_id")} → {r.get("to_name") or r.get("to_account_id")} | {_m(r.get("amount_out"))} | {(r.get("note") or r.get("title") or "")[:40]}')
    ups = []
    for s in subs.list_subscriptions(con):
        if subs.effective_state(con, s) == 'active':
            n = subs.next_charge(con, s)
            if n: ups.append(f'{s["name"]} {_m(s["cost"])} {s["currency"]} on {iso(n[1])}')
    if ups: out.append('Upcoming subscriptions: ' + '; '.join(sorted(ups, key=lambda x: x[-10:])[:8]))
    gl = goals.list_goals(con)
    if gl: out.append('Goals: ' + '; '.join(f'{g["name"]} {round(goals.progress(g) * 100)}%' for g in gl[:6]))
    return '\n'.join(out)


PROTOCOL = """
FINANCE — you are connected to the user's Curio Finance book (data under "Finance book" in each message).
• To RECORD money, end your reply with ONE block like this (JSON, no comments):
```curio
{"actions":[{"do":"add_expense","amount":1200,"account":"Meezan","category":"Food","title":"Lunch","date":"2026-11-20","time":"13:30","note":""}]}
```
  do = add_expense | add_income | add_transfer. A transfer uses "from", "to", "amount" (+ "amount_in" only when the two
  accounts have different currencies).
  account / from / to: an account name exactly as in the Accounts list. If the user did not name one, follow the user's own
  rules below, else use the account they used most for that kind of entry in the latest transactions. If you truly cannot
  tell, ask a short question and do not add the block.
  category: reuse an existing category when it fits; make a new short one only if nothing fits.
  title: 2–5 words in the style of the user's recent titles. amount: plain number in that account's currency.
  date: YYYY-MM-DD ("aaj" = today; "kal" about money already spent = yesterday). time: HH:MM only if the user said it.
  Several items in one message → several actions in the same block.
  Above the block, say in one line what you are recording (e.g. "Food · 1,200 PKR · Meezan · today"). Do not claim it is
  already saved — Curio shows a card and saves it.
• To LOOK UP older or specific records first, reply with ONLY this block and nothing else:
```curio
{"find":{"search":"","month":"YYYY-MM","from":"YYYY-MM-DD","to":"YYYY-MM-DD","account":"","category":"","kind":"expense"}}
```
  (leave out what you don't need). You get the matching records back, then answer.
• Use only the numbers you are given — never guess balances or past entries. You cannot edit or delete old records; tell the
  user to do that in Finance."""


# ───────────────────────── parse the AI's blocks ─────────────────────────
def parse(answer):
    """→ (text without the blocks, [actions], find-or-None)"""
    acts, find = [], None
    for raw in BLOCK.findall(answer or ''):
        try: j = json.loads(raw.strip())
        except ValueError:
            try: j = json.loads(re.sub(r',\s*([}\]])', r'\1', raw.strip()))
            except ValueError: continue
        if isinstance(j, dict):
            if isinstance(j.get('find'), dict): find = j['find']
            a = j.get('actions')
            if isinstance(a, dict): a = [a]
            if isinstance(a, list): acts += [x for x in a if isinstance(x, dict)]
            elif j.get('do'): acts.append(j)
        elif isinstance(j, list): acts += [x for x in j if isinstance(x, dict)]
    text = BLOCK.sub('', answer or '').strip()
    return text, acts[:20], find


def _match(name, rows, cutoff=0.72):
    name = (name or '').strip().lower()
    if not name: return None
    by = {r['name'].lower(): r for r in rows}
    if name in by: return by[name]
    part = [r for r in rows if name in r['name'].lower() or r['name'].lower() in name]
    if len(part) == 1: return part[0]
    close = difflib.get_close_matches(name, list(by), n=1, cutoff=cutoff)
    return by[close[0]] if close else None


def _amount(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool): return float(v)
    s = str(v or '').lower().replace(',', '').strip()
    mult = 1
    if re.search(r'\d\s*(k|hazar|hazaar|thousand)\b', s): mult = 1000
    elif re.search(r'\d\s*(lac|lakh|lakh?s)\b', s): mult = 100000
    n = re.search(r'-?\d+(\.\d+)?', s)
    return float(n.group()) * mult if n else 0.0


def _date(v):
    s = str(v or '').strip().lower()
    t = today()
    if s in ('', 'today', 'aaj'): return iso(t)
    if s in ('yesterday', 'kal'): return iso(t - timedelta(days=1))
    try: return date.fromisoformat(s[:10]).isoformat()
    except ValueError: return iso(t)


def resolve(con, a):
    """an AI action → a checked card the user can save (ids filled in, problems listed)"""
    do = str(a.get('do') or a.get('action') or '').lower()
    accs = [dict(x) for x in ledger.accounts(con, False)]
    amt = abs(_amount(a.get('amount')))
    p = {'status': 'pending', 'problem': '', 'date': _date(a.get('date')), 'time': str(a.get('time') or '')[:5],
         'note': str(a.get('note') or '')[:300], 'title': str(a.get('title') or '')[:120], 'amount': amt}
    if do in ('add_transfer', 'transfer'):
        f, t = _match(a.get('from'), accs), _match(a.get('to'), accs)
        p.update(type='transfer', from_id=f and f['id'], from_name=f['name'] if f else str(a.get('from') or ''),
                 to_id=t and t['id'], to_name=t['name'] if t else str(a.get('to') or ''),
                 amount_in=abs(_amount(a.get('amount_in'))) if a.get('amount_in') not in (None, '') else None,
                 currency=f['currency'] if f else currency.base(con))
        if not f or not t: p['problem'] = 'Choose both accounts.'
        elif f['id'] == t['id']: p['problem'] = 'From and To are the same account.'
    else:
        kind = 'income' if do in ('add_income', 'income') or a.get('kind') == 'income' else 'expense'
        acc = _match(a.get('account'), accs)
        if not acc and len(accs) == 1: acc = accs[0]
        cats = [dict(x) for x in ledger.categories(con, kind)]
        cat = _match(a.get('category'), cats, 0.85)
        p.update(type='transaction', kind=kind, account_id=acc and acc['id'], account=acc['name'] if acc else str(a.get('account') or ''),
                 currency=acc['currency'] if acc else currency.base(con), category_id=cat and cat['id'],
                 category=cat['name'] if cat else str(a.get('category') or '').strip()[:60], fee=abs(_amount(a.get('fee'))) if a.get('fee') else 0)
        if not acc: p['problem'] = 'Choose an account.'
    if not amt: p['problem'] = (p['problem'] + ' ' if p['problem'] else '') + 'Amount is missing.'
    return p


def apply(con, p):
    """save one card → its id"""
    if p['type'] == 'transfer':
        if not p.get('from_id') or not p.get('to_id') or p['from_id'] == p['to_id']: raise ValueError('Choose two different accounts.')
        return fin.tf_save(con, {'date': p['date'], 'from': p['from_id'], 'to': p['to_id'], 'amount_out': p['amount'],
                                 'amount_in': p.get('amount_in') or '', 'fee': 0, 'note': p.get('note', ''), 'title': p.get('title', ''), 'time': p.get('time', '')})
    if not p.get('account_id'): raise ValueError('Choose an account.')
    if not p.get('amount'): raise ValueError('Amount is missing.')
    a = {'date': p['date'], 'account': p['account_id'], 'kind': p['kind'], 'amount': p['amount'], 'fee': p.get('fee') or 0,
         'title': p.get('title', ''), 'note': p.get('note', ''), 'time': p.get('time', '')}
    if p.get('category_id'): a['category'] = p['category_id']
    elif (p.get('category') or '').strip(): a['category_name'] = p['category'].strip()
    return fin.tx_save(con, a)


def find(con, f):
    acc = _match(f.get('account'), [dict(x) for x in ledger.accounts(con, True)]) if f.get('account') else None
    kind = f.get('kind') if f.get('kind') in ('income', 'expense') else None
    cat = _match(f.get('category'), [dict(x) for x in ledger.categories(con, kind)], 0.8) if f.get('category') else None
    rows = [dict(r) for r in ledger.list_transactions(con, month=(f.get('month') or None), account_id=acc and acc['id'], kind=kind,
                                                       category=cat and cat['id'], search=str(f.get('search') or '').strip(),
                                                       date_from=f.get('from') or None, date_to=f.get('to') or None)]
    inc = sum(abs(r['net']) for r in rows if r['kind'] == 'income'); exp = sum(abs(r['net']) for r in rows if r['kind'] != 'income')
    out = [f'Found {len(rows)} records (income {_m(inc)}, spent {_m(exp)}). Showing {min(len(rows), 80)}:']
    for r in rows[:80]:
        out.append(f'{r["date"]} | {r["account_name"]} | {r["kind"]} | {_m(abs(r["net"]))} {r["currency"]} | {r.get("category_name") or ""} | {(r.get("title") or "")[:50]} | {(r.get("note") or "")[:40]}')
    return '\n'.join(out)


def meta(con):
    return {'accounts': [{'id': a['id'], 'name': a['name'], 'currency': a['currency']} for a in ledger.accounts(con, False)],
            'categories': [{'id': c['id'], 'name': c['name'], 'kind': c['kind']} for c in ledger.categories(con)], 'today': iso(today())}
