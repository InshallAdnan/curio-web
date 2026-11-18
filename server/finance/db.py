"""The database. One SQLite file. Every rule (balances, transfers, subscriptions, depreciation) lives in code, so nothing has to be wired by hand."""
import os, sqlite3
from .util import iso, today

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE accounts(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, currency TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'bank',
  opening INTEGER NOT NULL DEFAULT 0, color TEXT, note TEXT, archived INTEGER NOT NULL DEFAULT 0, sort INTEGER NOT NULL DEFAULT 0, created TEXT);
CREATE TABLE categories(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('income','expense')), color TEXT, UNIQUE(name, kind));
CREATE TABLE transactions(
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, account_id INTEGER NOT NULL REFERENCES accounts(id),
  kind TEXT NOT NULL CHECK(kind IN ('income','expense')), title TEXT NOT NULL DEFAULT '',
  amount INTEGER NOT NULL CHECK(amount >= 0), fee INTEGER NOT NULL DEFAULT 0 CHECK(fee >= 0),
  category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL, note TEXT, attachment TEXT,
  source TEXT NOT NULL DEFAULT 'manual', source_id INTEGER, created TEXT);
CREATE INDEX tx_date ON transactions(date); CREATE INDEX tx_acc ON transactions(account_id);
CREATE TABLE transfers(
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, from_account_id INTEGER NOT NULL REFERENCES accounts(id), to_account_id INTEGER NOT NULL REFERENCES accounts(id),
  amount_out INTEGER NOT NULL CHECK(amount_out > 0), amount_in INTEGER NOT NULL CHECK(amount_in > 0), fee INTEGER NOT NULL DEFAULT 0 CHECK(fee >= 0),
  rate REAL, note TEXT, created TEXT);
CREATE INDEX tf_date ON transfers(date);
CREATE TABLE goals(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, target INTEGER NOT NULL DEFAULT 0, initial INTEGER NOT NULL DEFAULT 0, currency TEXT NOT NULL,
  due TEXT, note TEXT, completed INTEGER NOT NULL DEFAULT 0, completed_on TEXT, sort INTEGER NOT NULL DEFAULT 0, created TEXT);
CREATE TABLE goal_contributions(
  id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE, date TEXT NOT NULL, amount INTEGER NOT NULL, note TEXT,
  transfer_id INTEGER REFERENCES transfers(id) ON DELETE CASCADE);
CREATE TABLE subscriptions(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, cost INTEGER NOT NULL CHECK(cost >= 0), every_months INTEGER NOT NULL DEFAULT 1 CHECK(every_months >= 1),
  billing_day INTEGER NOT NULL DEFAULT 1, account_id INTEGER NOT NULL REFERENCES accounts(id), category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  note TEXT, status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','ended')), created TEXT);
CREATE TABLE sub_periods(
  id INTEGER PRIMARY KEY, sub_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE, start_month TEXT NOT NULL, end_month TEXT);
CREATE TABLE sub_charges(
  id INTEGER PRIMARY KEY, sub_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE, month TEXT NOT NULL, due_date TEXT NOT NULL,
  amount INTEGER NOT NULL, transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
  state TEXT NOT NULL DEFAULT 'posted' CHECK(state IN ('posted','skipped')), UNIQUE(sub_id, month));
CREATE TABLE assets(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT, currency TEXT NOT NULL, price INTEGER NOT NULL CHECK(price >= 0), purchase_date TEXT NOT NULL,
  life_months INTEGER NOT NULL CHECK(life_months >= 1), salvage INTEGER NOT NULL DEFAULT 0 CHECK(salvage >= 0), note TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','sold')), sold_date TEXT, sold_price INTEGER, created TEXT);
CREATE TABLE asset_events(
  id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE, date TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('repair','upgrade')), cost INTEGER NOT NULL CHECK(cost >= 0), extend_months INTEGER NOT NULL DEFAULT 0, note TEXT,
  transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL);
CREATE TABLE rates(currency TEXT PRIMARY KEY, rate REAL NOT NULL, updated TEXT, source TEXT);
CREATE TABLE rate_history(id INTEGER PRIMARY KEY, date TEXT NOT NULL, currency TEXT NOT NULL, rate REAL NOT NULL, source TEXT);
"""

DEFAULT_CATEGORIES = [
    ('Salary', 'income'), ('Freelance', 'income'), ('Other income', 'income'),
    ('Food', 'expense'), ('Transport', 'expense'), ('Bills', 'expense'), ('Shopping', 'expense'), ('Health', 'expense'),
    ('Education', 'expense'), ('Entertainment', 'expense'), ('Subscriptions', 'expense'), ('Repairs & Maintenance', 'expense'),
    ('Business', 'expense'), ('Other', 'expense')]


def connect(path):
    """Open (or create) the book at `path`."""
    new = path == ':memory:' or not os.path.exists(path)
    if path != ':memory:': os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path, timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    if new or con.execute('PRAGMA user_version').fetchone()[0] == 0:
        con.executescript(SCHEMA)
        con.executemany('INSERT INTO categories(name, kind) VALUES(?,?)', DEFAULT_CATEGORIES)
        set_setting(con, 'base_currency', 'PKR'); set_setting(con, 'auto_post_subs', '1'); set_setting(con, 'theme', 'light')
        con.execute('INSERT INTO rates(currency, rate, updated, source) VALUES(?,?,?,?)', ('PKR', 1.0, iso(today()), 'base'))
        con.execute(f'PRAGMA user_version = {SCHEMA_VERSION}'); con.commit()
    tcols = [r[1] for r in con.execute('PRAGMA table_info(transfers)')]
    if 'title' not in tcols: con.execute("ALTER TABLE transfers ADD COLUMN title TEXT NOT NULL DEFAULT ''")          # transfers got a name of their own
    if 'time' not in tcols: con.execute("ALTER TABLE transfers ADD COLUMN time TEXT NOT NULL DEFAULT ''")            # optional time of day, 'HH:MM'
    if 'time' not in [r[1] for r in con.execute('PRAGMA table_info(transactions)')]:
        con.execute("ALTER TABLE transactions ADD COLUMN time TEXT NOT NULL DEFAULT ''")
    con.commit()
    return con


def get_setting(con, key, default=None):
    r = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return r[0] if r else default


def set_setting(con, key, value):
    con.execute('INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value))); con.commit()


def category_id(con, name, kind):
    r = con.execute('SELECT id FROM categories WHERE name=? AND kind=?', (name, kind)).fetchone()
    if r: return r[0]
    cur = con.execute('INSERT INTO categories(name, kind) VALUES(?,?)', (name, kind)); con.commit(); return cur.lastrowid


def wipe(con):
    """Erase every entry and start a clean book (categories and settings stay)."""
    for t in ('sub_charges', 'sub_periods', 'subscriptions', 'asset_events', 'assets', 'goal_contributions', 'goals', 'transfers', 'transactions', 'accounts', 'rate_history'):
        con.execute(f'DELETE FROM {t}')
    con.execute("DELETE FROM rates WHERE source<>'base'"); con.commit()
