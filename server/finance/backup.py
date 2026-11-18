"""Where the data lives, safe backups, and CSV in / out."""
import csv, os, re, sqlite3
from datetime import datetime, date
from . import ledger, currency
from .money import fmt_plain, parse_amount
from .util import iso

APP_DIR = 'Curio'


_DATA_DIR = [None]


def set_data_dir(path): _DATA_DIR[0] = path


def data_dir():
    if _DATA_DIR[0]: return _DATA_DIR[0]
    env = os.environ.get('HISAAB_DATA')
    if env: return env
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), '.local', 'share')
    return os.path.join(base, APP_DIR)


def db_path(): return os.path.join(data_dir(), 'finance.db')


def default_backup_dir(): return os.path.join(data_dir(), 'backups')


def make_backup(con, folder=None, tag=''):
    folder = folder or default_backup_dir(); os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"hisaab-{datetime.now().strftime('%Y%m%d-%H%M%S')}{('-' + tag) if tag else ''}.db")
    dst = sqlite3.connect(path)
    try: con.backup(dst)
    finally: dst.close()
    return path


def list_backups(folder=None):
    folder = folder or default_backup_dir()
    if not os.path.isdir(folder): return []
    return sorted((os.path.join(folder, f) for f in os.listdir(folder) if re.fullmatch(r'hisaab-\d{8}-\d{6}.*\.db', f)), reverse=True)


def auto_backup(con, folder=None, keep=30):
    """One backup per day, the newest `keep` are kept. → path or None"""
    folder = folder or default_backup_dir(); stamp = datetime.now().strftime('%Y%m%d')
    if any(os.path.basename(p).startswith(f'hisaab-{stamp}') for p in list_backups(folder)): return None
    p = make_backup(con, folder)
    for old in list_backups(folder)[keep:]:
        try: os.remove(old)
        except OSError: pass
    return p


def restore(con, path):
    """Replace everything with the backup (a safety copy of the current book is made first)."""
    src = sqlite3.connect(path)
    try:
        names = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'accounts', 'transactions', 'transfers'} <= names or src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('This file is not a Curio backup')
        safety = make_backup(con, tag='before-restore')
        src.backup(con)
    finally: src.close()
    con.execute('PRAGMA foreign_keys = ON'); return safety


# ───────────────────────── CSV ─────────────────────────
def export_csv(con, folder):
    os.makedirs(folder, exist_ok=True)
    p1 = os.path.join(folder, 'transactions.csv'); p2 = os.path.join(folder, 'transfers.csv')
    with open(p1, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['Date', 'Account', 'Currency', 'Type', 'Title', 'Category', 'Amount', 'Fee', 'Note'])
        for t in reversed(ledger.list_transactions(con)):
            w.writerow([t['date'], t['account_name'], t['currency'], t['kind'].title(), t['title'], t['category_name'] or '', fmt_plain(t['amount']), fmt_plain(t['fee']), t['note'] or ''])
    with open(p2, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['Date', 'From', 'To', 'Sent', 'Sent currency', 'Received', 'Received currency', 'Fee', 'Note'])
        for t in reversed(ledger.list_transfers(con)):
            w.writerow([t['date'], t['from_name'], t['to_name'], fmt_plain(t['amount_out']), t['from_cur'], fmt_plain(t['amount_in']), t['to_cur'], fmt_plain(t['fee']), t['note'] or ''])
    return p1, p2


_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y', '%Y/%m/%d', '%d.%m.%Y')
_COLS = {'date': ('date', 'day', 'when'), 'title': ('name', 'title', 'description', 'details', 'item'), 'account': ('account', 'accounts', 'wallet'),
         'amount': ('amount', 'value', 'sum'), 'fee': ('fee', 'fees', 'charges'), 'kind': ('type', 'select', 'kind', 'income/expense'),
         'category': ('category', 'tag'), 'note': ('note', 'notes', 'memo'), 'to': ('to account', 'to', 'to accounts')}


def _date(s):
    s = (s or '').strip().split(' → ')[0].split(' -> ')[0]
    for f in _DATE_FORMATS:
        try: return datetime.strptime(s, f).date().isoformat()
        except ValueError: pass
    raise ValueError(f'unreadable date “{s}”')


def _clean_name(s): return re.sub(r'\s*\(https?://[^)]*\)\s*$', '', (s or '').strip())        # Notion exports relations as “Name (url)”


def _account_id(con, name, base, res):
    acc = con.execute('SELECT id FROM accounts WHERE name=? COLLATE NOCASE', (name,)).fetchone()
    if acc: return acc[0]
    aid = ledger.add_account(con, name, base, 'bank', 0); res['new_accounts'].append(name); return aid


def _import_transfer(con, row, col, d, amt, base, res):
    """Type = Transfer, Account = from, To Account = to. Fee is taken from the sending account on top of Amount."""
    frm = _clean_name(row[col['account']]) if col['account'] else ''; to = _clean_name(row.get(col['to']) or '')
    if not frm or not to: raise ValueError('a transfer needs both Account and To Account')
    if frm.lower() == to.lower(): raise ValueError('a transfer needs two different accounts')
    fee = abs(parse_amount(row[col['fee']])) if col['fee'] and (row.get(col['fee']) or '').strip() else 0
    a, b = _account_id(con, frm, base, res), _account_id(con, to, base, res); amt = abs(amt)
    note = (row.get(col['note']) or '').strip() if col['note'] else ''
    title = (row.get(col['title']) or '').strip() if col['title'] else ''
    if con.execute('SELECT 1 FROM transfers WHERE date=? AND from_account_id=? AND to_account_id=? AND amount_out=? AND fee=?', (d, a, b, amt, fee)).fetchone():
        res['duplicates'] += 1; return
    ledger.add_transfer(con, d, a, b, amt, amt, fee, note, title); res['imported'] += 1


def import_csv(con, path, default_account=None):
    """Bring transactions in from a CSV (Curio's own export, or a spreadsheet / Notion export). → dict(imported, duplicates, errors, new_accounts)"""
    res = dict(imported=0, duplicates=0, errors=[], new_accounts=[])
    with open(path, newline='', encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames: raise ValueError('The file is empty')
        low = {h.strip().lower(): h for h in rd.fieldnames}
        col = {k: next((low[a] for a in names if a in low), None) for k, names in _COLS.items()}
        if not col['date'] or not col['amount']: raise ValueError('The file needs at least a Date and an Amount column')
        if not col['account'] and not default_account: raise ValueError('There is no Account column — choose which account these belong to')
        base = currency.base(con); cats = {}
        for i, row in enumerate(rd, start=2):
            try:
                d = _date(row[col['date']]); raw = row[col['amount']].strip()
                if not raw: continue
                amt = parse_amount(raw)
                kind = (row.get(col['kind']) or '').strip().lower() if col['kind'] else ''
                if kind.startswith('trans') and col['to']:              # a move between two of your accounts
                    _import_transfer(con, row, col, d, amt, base, res); continue
                if kind.startswith(('inc', 'in', '+', 'cr')): kind = 'income'
                elif kind.startswith(('exp', 'out', '-', 'db')): kind = 'expense'
                else: kind = 'expense' if amt < 0 or not kind else kind
                if kind not in ('income', 'expense'): kind = 'expense'
                amt = abs(amt); fee = abs(parse_amount(row[col['fee']])) if col['fee'] and (row.get(col['fee']) or '').strip() else 0
                name = _clean_name(row[col['account']]) if col['account'] else ''
                if name:
                    acc = con.execute('SELECT id FROM accounts WHERE name=? COLLATE NOCASE', (name,)).fetchone()
                    if acc: aid = acc[0]
                    else: aid = ledger.add_account(con, name, base, 'bank', 0); res['new_accounts'].append(name)
                else: aid = default_account
                title = (row.get(col['title']) or '').strip() if col['title'] else ''
                cname = (row.get(col['category']) or '').strip() if col['category'] else ''
                cid = None
                if cname:
                    key = (cname, kind)
                    if key not in cats: cats[key] = ledger.add_category(con, cname, kind)
                    cid = cats[key]
                if con.execute('SELECT 1 FROM transactions WHERE date=? AND account_id=? AND kind=? AND amount=? AND fee=? AND title=?', (d, aid, kind, amt, fee, title)).fetchone():
                    res['duplicates'] += 1; continue
                ledger.add_transaction(con, d, aid, kind, amt, fee, title, cid, (row.get(col['note']) or '').strip() if col['note'] else '', None, 'import'); res['imported'] += 1
            except (ValueError, KeyError) as e:
                res['errors'].append((i, str(e)))
    return res
