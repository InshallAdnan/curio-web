"""My Day — the things that come back and need a nudge: tasks, habits & routines, quitting a bad habit, sleep, quick notes.

One book, one shape (not a dashboard per topic): every task and habit belongs to an *area* (Responsibilities, Self-Improve,
Skill Learn, Health, Deen … add more any time). Pages stays the place for writing; My Day is the place that reminds.

Data: <data>/myday/myday.db (yours) and <data>/myday/demo.db (made-up examples, only to look around — never mixed).
Times are local (your PC's clock). Nothing here talks to the internet."""
import json, random, re, sqlite3, threading
from datetime import date, datetime, timedelta
from pathlib import Path

from core import ROOT

HOME = ROOT / 'myday'
REAL, DEMO = HOME / 'myday.db', HOME / 'demo.db'
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
AREA_COLORS = ['#e0a100', '#2f6fde', '#1f9d6b', '#d6457a', '#0e8fa3', '#8b5cf6', '#f2602d', '#6b7280']
ROUTINES = ['Morning', 'Namaz', 'Day', 'Night']
ROUTINE_COLORS = {'Morning': '#e0a100', 'Namaz': '#0e8fa3', 'Day': '#2f6fde', 'Night': '#6d5bd0'}
STATUSES = [('idea', 'Ideas'), ('todo', 'To do'), ('doing', 'In progress'), ('done', 'Done')]
MOODS = [(1, 'Stressed', '#e5484d'), (2, 'Low', '#f08a5d'), (3, 'Okay', '#e0a100'), (4, 'Good', '#7cc49b'), (5, 'Great', '#1f9d6b')]
SLEEP_TAGS = ['Phone in bed', 'Tea / coffee after 6', 'Late dinner', 'Walked today', 'Read before sleep', 'Stressed']
NOTE_TAGS = ['Daily Life', 'Idea', 'Inspiration', 'Personal', 'Gratification', 'Affirmations', 'Business', 'My Belief']
TRIGGERS = ['Bored', 'Alone', 'Late night', 'Phone in bed', 'Stressed', 'Tired', 'Social media', 'Other']

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS areas(id INTEGER PRIMARY KEY, name TEXT NOT NULL, color TEXT, sort REAL DEFAULT 0, archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL, area_id INTEGER, day TEXT, time TEXT, minutes INTEGER DEFAULT 30,
  repeat TEXT, remind INTEGER DEFAULT -1, note TEXT DEFAULT '', link TEXT DEFAULT '', priority INTEGER DEFAULT 0, done_at TEXT,
  next_id INTEGER, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS habits(id INTEGER PRIMARY KEY, name TEXT NOT NULL, area_id INTEGER, kind TEXT DEFAULT 'build', routine TEXT DEFAULT '',
  days TEXT DEFAULT '[0,1,2,3,4,5,6]', time TEXT, remind INTEGER DEFAULT -1, why TEXT DEFAULT '', start_day TEXT, sort REAL DEFAULT 0,
  archived INTEGER DEFAULT 0, created TEXT);
CREATE TABLE IF NOT EXISTS habit_periods(id INTEGER PRIMARY KEY, habit_id INTEGER NOT NULL, start TEXT NOT NULL, end TEXT,
  days TEXT, time TEXT, remind INTEGER DEFAULT -1, routine TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS habit_log(habit_id INTEGER NOT NULL, day TEXT NOT NULL, state TEXT NOT NULL, ts TEXT, PRIMARY KEY(habit_id, day));
CREATE TABLE IF NOT EXISTS quit_events(id INTEGER PRIMARY KEY, habit_id INTEGER NOT NULL, ts TEXT NOT NULL, kind TEXT NOT NULL,
  trigger TEXT DEFAULT '', helped TEXT DEFAULT '', note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sleep(id INTEGER PRIMARY KEY, bed TEXT NOT NULL, wake TEXT NOT NULL, quality INTEGER DEFAULT 3, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, title TEXT DEFAULT '', content TEXT DEFAULT '', tags TEXT DEFAULT '[]',
  pinned INTEGER DEFAULT 0, archived INTEGER DEFAULT 0, resurface INTEGER DEFAULT 1, created TEXT, last_shown TEXT);
CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY, text TEXT NOT NULL, author TEXT DEFAULT '', archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sent(key TEXT PRIMARY KEY, ts TEXT);
CREATE TABLE IF NOT EXISTS snoozes(key TEXT PRIMARY KEY, until TEXT, title TEXT, body TEXT, kind TEXT, ref INTEGER);
CREATE TABLE IF NOT EXISTS focus_sessions(id INTEGER PRIMARY KEY, task_id INTEGER, title TEXT DEFAULT '', area_id INTEGER, start TEXT NOT NULL, end TEXT NOT NULL,
  minutes INTEGER DEFAULT 0, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS mood(day TEXT PRIMARY KEY, mood INTEGER NOT NULL, ts TEXT, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS focus_events(id INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, task_id INTEGER, run TEXT DEFAULT '',
  app TEXT DEFAULT '', title TEXT DEFAULT '', note TEXT DEFAULT '', seconds INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS parked(id INTEGER PRIMARY KEY, text TEXT NOT NULL, ts TEXT, task_id INTEGER, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS inspo(id INTEGER PRIMARY KEY, section TEXT DEFAULT 'My Inspo', kind TEXT NOT NULL, title TEXT DEFAULT '', text TEXT DEFAULT '',
  path TEXT DEFAULT '', ref TEXT DEFAULT '', url TEXT DEFAULT '', habit_id INTEGER, pinned INTEGER DEFAULT 0, sort REAL DEFAULT 0, created TEXT);
CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY, start TEXT NOT NULL, end TEXT NOT NULL, app TEXT DEFAULT '', title TEXT DEFAULT '',
  cat TEXT DEFAULT '', task_id INTEGER);
CREATE INDEX IF NOT EXISTS activity_start ON activity(start);
CREATE TABLE IF NOT EXISTS nudges(id INTEGER PRIMARY KEY, text TEXT NOT NULL, every INTEGER DEFAULT 45, start TEXT DEFAULT '09:00', end TEXT DEFAULT '23:00',
  days TEXT DEFAULT '[0,1,2,3,4,5,6]', kind TEXT DEFAULT 'timer', active_only INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1, last TEXT);
CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY, kind TEXT DEFAULT 'goal', title TEXT NOT NULL, why TEXT DEFAULT '', due TEXT,
  progress INTEGER DEFAULT 0, done_at TEXT, sort REAL DEFAULT 0, created TEXT);
"""

DEFAULTS = {'morning_time': '08:00', 'memory_time': '21:30', 'notify': '1', 'calendar': '1', 'inspo_boards': '[]', 'sleep_goal': '450', 'bed_goal': '23:00',
            'focus': '', 'focus_break': '45', 'wake_goal': '07:00', 'sleep_auto': '1', 'cal_sleep': '1', 'cal_focus': '1',
            'watch_all': '1', 'night_watch': '1', 'coach_strict': '2', 'coach_ai': '0', 'coach_ai_every': '30', 'plan_end': '23:00', 'drift_min': '15',
            # focus coach (10.23)
            'coach_ask': '15', 'coach_watch': '1', 'coach_bar': '1', 'coach_idle': '8', 'coach_wander': '1', 'coach_wander_every': '45',
            'work_start': '10:00', 'work_end': '19:00', 'inspo_times': '["11:30", "16:30"]',
            'coach_apps': json.dumps(['youtube', 'instagram', 'facebook', 'tiktok', 'netflix', 'whatsapp', 'twitter', 'reddit', 'snapchat', 'x.com', 'daraz', 'cricinfo']),
            'inspo_sections': json.dumps(['My Inspo', 'GOAT', 'Reset', 'Life I want']),
            'plan': json.dumps(['Stand up and leave the room', 'Drink a glass of water, make wudu', 'Walk for 10 minutes — no phone',
                                'Call or text someone', 'Open your Reset board'])}

_LOCK = threading.RLock()


# ───────────────────────── the book ─────────────────────────
def is_demo():
    """10.29: the made-up demo book is gone — Tracker always shows your own data"""
    return False


def set_demo(on):
    import studio_ui
    studio_ui.save_cfg(myday_demo=bool(on))


def path(): return DEMO if is_demo() else REAL


DEMO_ACTIVITY = {('figma', 'Client logo — Figma', 'task'), ('chrome', 'YouTube - Figma auto layout tutorial', 'learning'), ('chrome', 'Instagram', 'distraction'),
                 ('whatsapp', 'WhatsApp', 'distraction'), ('code', 'Curio — Visual Studio Code', 'work'), ('chrome', 'Meta Ads Manager', 'work'),
                 ('chrome', 'YouTube - funny clips', 'distraction')}
LOCAL_KEYS = ('coach_', 'watch_', 'night_watch', 'act_', 'drift_min', 'nudge_ai', 'wander', 'work_start', 'work_end', 'sleep_quiet_until')


def retire_demo():
    """10.29: the demo book goes away. While it was on, the PC's screen record and your coach settings were written into it —
    those (yours, not made-up) move to your own book first. The demo file itself is kept aside in myday/_old (never shown again)."""
    if not DEMO.exists(): return
    with _LOCK:
        if not DEMO.exists(): return
        try:
            r = sqlite3.connect(str(REAL), timeout=20); r.executescript(SCHEMA); _add_columns(r)
            d = sqlite3.connect(str(DEMO), timeout=20); d.row_factory = sqlite3.Row
            have = {(x[0], x[1]) for x in r.execute('SELECT start, app FROM activity')}
            n = 0
            try:
                for x in d.execute('SELECT * FROM activity ORDER BY start'):
                    if (x['app'], x['title'], x['cat']) in DEMO_ACTIVITY and x['task_id'] is None: continue        # the made-up day
                    if (x['start'], x['app']) in have: continue
                    r.execute('INSERT INTO activity(start, end, app, title, cat, task_id) VALUES(?,?,?,?,?,?)', (x['start'], x['end'], x['app'], x['title'], x['cat'], None)); n += 1
            except sqlite3.Error: pass
            mine = {x[0] for x in r.execute('SELECT key FROM settings')}
            try:
                for k, v in d.execute('SELECT key, value FROM settings'):
                    if k.startswith(LOCAL_KEYS) and k not in mine: r.execute('INSERT INTO settings(key, value) VALUES(?,?)', (k, v))
            except sqlite3.Error: pass
            r.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('demo_retired', ?)", (stamp(),))
            r.commit(); r.close(); d.close()
            old = HOME / '_old'; old.mkdir(exist_ok=True)
            DEMO.replace(old / f"demo-removed-{now():%Y%m%d-%H%M%S}.db")
            import logging; logging.info('Tracker: demo removed, %d screen-record rows kept', n)
        except Exception:
            import logging; logging.exception('Tracker: removing the demo')


def connect(p=None):
    p = Path(p or path()); p.parent.mkdir(parents=True, exist_ok=True)
    if p.name == REAL.name and DEMO.exists(): retire_demo()
    new = not p.exists()
    if not new and p.name == REAL.name: _copy_before_upgrade(p)
    c = sqlite3.connect(str(p), timeout=20, check_same_thread=False); c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    _add_columns(c)
    # habits from before plans had periods: one period from the day each habit began
    c.execute("INSERT INTO habit_periods(habit_id, start, end, days, time, remind, routine) "
              "SELECT id, COALESCE(start_day, substr(created, 1, 10), date('now','localtime')), CASE WHEN archived=1 THEN COALESCE(start_day, substr(created, 1, 10)) END, "
              "days, time, remind, COALESCE(routine, '') FROM habits WHERE id NOT IN (SELECT habit_id FROM habit_periods)")
    if new or not c.execute('SELECT 1 FROM areas LIMIT 1').fetchone():
        _first_areas(c)
        if p.name == DEMO.name: seed_demo(c)
    if p.name == DEMO.name:
        try: demo_extras(c); demo_inspo_cards(c); demo_extras3(c); demo_extras4(c)
        except Exception: import logging; logging.exception('demo extras')
    c.commit()
    return c


NEW_COLUMNS = [('tasks', 'status', "TEXT DEFAULT 'todo'"), ('habit_log', 'note', "TEXT DEFAULT ''"),
               ('sleep', 'latency', 'INTEGER DEFAULT 0'), ('sleep', 'tags', "TEXT DEFAULT '[]'"),
               ('focus_sessions', 'run', "TEXT DEFAULT ''"), ('focus_sessions', 'intent', "TEXT DEFAULT ''"), ('focus_sessions', 'rating', 'INTEGER'),
               ('tasks', 'series', 'INTEGER'), ('tasks', 'repeat_end', 'TEXT'), ('tasks', 'snooze_until', 'TEXT'),
               ('sleep', 'auto', 'INTEGER DEFAULT 0'), ('sleep', 'source', "TEXT DEFAULT ''"), ('inspo', 'color', "TEXT DEFAULT ''"), ('nudges', 'brief', "TEXT DEFAULT ''"),
               ('habits', 'etime', 'TEXT'), ('habit_periods', 'etime', 'TEXT')]


def _add_columns(c):
    """10.22+: new fields on old tables (added, never removed — old data stays as it was)"""
    added = set()
    for table, col, kind in NEW_COLUMNS:
        have = {r[1] for r in c.execute(f'PRAGMA table_info({table})')}
        if col not in have: c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {kind}'); added.add((table, col))
    if ('tasks', 'series') in added:                           # 10.25: link the copies of a repeating task into one series
        for r in c.execute('SELECT id, next_id FROM tasks WHERE next_id IS NOT NULL').fetchall(): pass
        nxt = {r[0]: r[1] for r in c.execute('SELECT id, next_id FROM tasks')}
        prev = {v: k for k, v in nxt.items() if v}
        for tid in nxt:
            if tid in prev: continue                             # not the first of its chain
            chain, cur = [], tid
            while cur and cur not in chain: chain.append(cur); cur = nxt.get(cur)
            if len(chain) > 1 or c.execute('SELECT repeat FROM tasks WHERE id=?', (tid,)).fetchone()[0]:
                c.execute(f"UPDATE tasks SET series=? WHERE id IN ({','.join('?' * len(chain))})", [tid] + chain)


def _copy_before_upgrade(p):
    """10.22 adds a few columns to your book; keep one untouched copy of it from before, next to it"""
    keep = p.with_name('myday.before-10.22.db')
    if keep.exists(): return
    try:
        c = sqlite3.connect(str(p)); have = {r[1] for r in c.execute('PRAGMA table_info(tasks)')}
        if have and 'status' not in have:
            b = sqlite3.connect(str(keep)); c.backup(b); b.close()
        c.close()
    except Exception:
        import logging; logging.exception('My Day: copy before upgrade')


def _first_areas(c):
    for i, n in enumerate(['Responsibilities', 'Self-Improve', 'Skill Learn', 'Deen']):
        c.execute('INSERT INTO areas(name, color, sort) VALUES(?,?,?)', (n, AREA_COLORS[i], i))


def now(): return datetime.now()
def today(): return date.today()
def iso(d): return d.isoformat()
def stamp(): return now().isoformat(timespec='seconds')


def setting(c, k):
    r = c.execute('SELECT value FROM settings WHERE key=?', (k,)).fetchone()
    return r[0] if r else DEFAULTS.get(k, '')


def set_setting(c, k, v):
    c.execute('INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)', (k, str(v))); c.commit()


# ───────────────────────── areas ─────────────────────────
def areas(c, all_=False):
    return [dict(r) for r in c.execute('SELECT * FROM areas WHERE archived=0 OR ? ORDER BY sort, id', (1 if all_ else 0,))]


def add_area(c, name, color=None):
    n = c.execute('SELECT COUNT(*) FROM areas').fetchone()[0]
    cur = c.execute('INSERT INTO areas(name, color, sort) VALUES(?,?,?)', (name.strip()[:40], color or AREA_COLORS[n % len(AREA_COLORS)], n))
    c.commit(); return cur.lastrowid


def update_area(c, aid, **kw):
    for k in ('name', 'color', 'archived', 'sort'):
        if k in kw: c.execute(f'UPDATE areas SET {k}=? WHERE id=?', (kw[k], aid))
    c.commit()


# ───────────────────────── tasks ─────────────────────────
def _task(r):
    d = dict(r); d['repeat'] = json.loads(d['repeat']) if d.get('repeat') else None; return d


def tasks(c, area=None, done=None, cancelled=False):
    q, a = 'SELECT * FROM tasks WHERE 1=1', []
    if not cancelled: q += " AND COALESCE(status,'') != 'cancelled'"
    if area: q += ' AND area_id=?'; a.append(area)
    if done is True: q += ' AND done_at IS NOT NULL'
    if done is False: q += ' AND done_at IS NULL'
    q += " ORDER BY day IS NULL, day, time IS NULL, time, priority DESC, id"
    return [_task(r) for r in c.execute(q, a)]


def task(c, tid):
    r = c.execute('SELECT * FROM tasks WHERE id=?', (tid,)).fetchone(); return _task(r) if r else None


def save_task(c, t):
    """insert (no id) or update; t: title, area_id, day, time, minutes, repeat(dict|None), remind, note, link, priority"""
    st = t.get('status') or 'todo'
    if st == 'done': st = 'todo'                                   # done is kept by done_at (complete())
    vals = (t['title'].strip()[:300], t.get('area_id'), t.get('day') or None, t.get('time') or None, int(t.get('minutes') or 30),
            json.dumps(t['repeat']) if t.get('repeat') else None, int(t.get('remind', -1)), t.get('note', ''), t.get('link', ''),
            int(t.get('priority') or 0), st)
    if t.get('id'):
        c.execute('UPDATE tasks SET title=?, area_id=?, day=?, time=?, minutes=?, repeat=?, remind=?, note=?, link=?, priority=?, status=?, updated=? WHERE id=?',
                  vals + (stamp(), t['id'])); tid = t['id']
        if 'repeat_end' in t: c.execute('UPDATE tasks SET repeat_end=? WHERE id=?', (t['repeat_end'] or None, tid))
    else:
        tid = c.execute('INSERT INTO tasks(title, area_id, day, time, minutes, repeat, remind, note, link, priority, status, created, updated) '
                        'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', vals + (stamp(), stamp())).lastrowid
    if 'repeat_end' in t: c.execute('UPDATE tasks SET repeat_end=? WHERE id=?', (t['repeat_end'] or None, tid))
    c.commit(); return tid


def next_day(rule, d):
    """the next date of a repeating task after d"""
    if not rule: return None
    ev, n = rule.get('every', 'day'), max(1, int(rule.get('n', 1)))
    if ev == 'day': return d + timedelta(days=n)
    if ev == 'week':
        days = sorted(set(rule.get('days') or [d.weekday()]))
        for k in range(1, 7 * n + 8):
            x = d + timedelta(days=k)
            if x.weekday() in days and (n == 1 or ((x - d).days // 7) % n == 0 or k < 7): return x
        return d + timedelta(weeks=n)
    if ev == 'month':
        m = d.month - 1 + n; y = d.year + m // 12; m = m % 12 + 1
        import calendar as _c
        return date(y, m, min(d.day, _c.monthrange(y, m)[1]))
    return None


def repeat_text(rule):
    if not rule: return ''
    ev, n = rule.get('every'), int(rule.get('n', 1))
    if ev == 'day': return 'Every day' if n == 1 else f'Every {n} days'
    if ev == 'week':
        days = rule.get('days') or []
        if sorted(days) == [0, 1, 2, 3, 4]: return 'Weekdays'
        return ('Every week' if n == 1 else f'Every {n} weeks') + (' · ' + ' '.join(WEEKDAYS[x] for x in sorted(days)) if days else '')
    if ev == 'month': return 'Every month' if n == 1 else f'Every {n} months'
    return ''


def complete(c, tid, on=True):
    t = task(c, tid)
    if not t: return None
    if on and not t['done_at']:
        c.execute('UPDATE tasks SET done_at=? WHERE id=?', (stamp(), tid))
        sid = t.get('series') or tid
        if t['repeat'] and not t.get('series'): c.execute('UPDATE tasks SET series=? WHERE id=?', (sid, tid))
        if t['repeat'] and not t['next_id']:
            base = date.fromisoformat(t['day']) if t['day'] else today()
            nd = next_day(t['repeat'], max(base, today()) if base < today() else base)
            if nd and (not t.get('repeat_end') or iso(nd) <= t['repeat_end']):
                nt = dict(t); nt.pop('id'); nt['day'] = iso(nd); nt['status'] = 'todo'
                nid = save_task(c, nt); c.execute('UPDATE tasks SET next_id=?, series=? WHERE id=?', (nid, sid, tid))
                c.execute('UPDATE tasks SET series=?, repeat_end=? WHERE id=?', (sid, t.get('repeat_end'), nid))
    elif not on and t['done_at']:
        c.execute('UPDATE tasks SET done_at=NULL WHERE id=?', (tid,))
        if t['next_id']:                                      # the copy made when it was ticked — only if never touched
            n = task(c, t['next_id'])
            if n and not n['done_at'] and n['created'] == n['updated']:
                c.execute('DELETE FROM tasks WHERE id=?', (n['id'],)); c.execute('UPDATE tasks SET next_id=NULL WHERE id=?', (tid,))
    c.commit(); return task(c, tid)


def delete_task(c, tid):
    c.execute('DELETE FROM tasks WHERE id=?', (tid,)); c.commit()


def move_task(c, tid, day, time_=None):
    c.execute('UPDATE tasks SET day=?, time=COALESCE(?, time), updated=? WHERE id=?', (day, time_, stamp(), tid)); c.commit()


def task_buckets(c, area=None):
    """{'overdue','today','upcoming','someday','done'} → lists"""
    t0 = iso(today()); out = {k: [] for k in ('overdue', 'today', 'upcoming', 'someday', 'done')}
    for t in tasks(c, area):
        if t['done_at']: out['done'].append(t); continue
        if not t['day']: out['someday'].append(t)
        elif t['day'] < t0: out['overdue'].append(t)
        elif t['day'] == t0: out['today'].append(t)
        else: out['upcoming'].append(t)
    out['done'].sort(key=lambda t: t['done_at'], reverse=True)
    return out


# ───────────────────────── habits & routines ─────────────────────────
# A habit's plan (which days, what time, reminder, which routine) lives in *periods*: "from … until …".
# Changing the plan closes the old period and opens a new one, so earlier days keep the plan they really had:
# a habit added in November never shows October as missed, and a habit you stopped keeps its history.
PLAN = ('days', 'time', 'etime', 'remind', 'routine')


def _periods(c, hid):
    out = []
    for r in c.execute('SELECT * FROM habit_periods WHERE habit_id=? ORDER BY start, id', (hid,)):
        d = dict(r); d['days'] = json.loads(d['days'] or '[0,1,2,3,4,5,6]'); out.append(d)
    return out


def period_on(h, d):
    """the plan a habit had on day d (None = it did not exist / was stopped then)"""
    k = iso(d)
    for p in reversed(h.get('periods') or []):
        if p['start'] <= k and (not p['end'] or k <= p['end']): return p
    return None


def active_on(h, d): return period_on(h, d) is not None


def due_on(h, d):
    p = period_on(h, d)
    return bool(p) and d.weekday() in (p['days'] or list(range(7)))


def _habit(c, r, on=None):
    d = dict(r); d['periods'] = _periods(c, d['id'])
    p = period_on(d, on or today()) or (d['periods'][-1] if d['periods'] else None)
    if p:
        for k in PLAN: d[k] = p[k]
    else: d['days'] = json.loads(d['days'] or '[]')
    d['first_day'] = d['periods'][0]['start'] if d['periods'] else (d.get('start_day') or iso(today()))
    d['ended'] = bool(d['periods']) and bool(d['periods'][-1]['end'])
    return d


def habits(c, kind=None, routine=None, archived=False, on=None):
    """active habits (a plan covering today) — or, with archived=True, the ones you stopped"""
    q, a = 'SELECT * FROM habits WHERE archived=?', [1 if archived else 0]
    if kind: q += ' AND kind=?'; a.append(kind)
    out = [_habit(c, r, on) for r in c.execute(q + ' ORDER BY sort, id', a)]
    if not archived: out = [h for h in out if active_on(h, on or today()) or not h['periods']]
    if routine is not None: out = [h for h in out if (h['routine'] or '') == routine]
    out.sort(key=lambda h: (h['sort'], h['time'] is None, h['time'] or '', h['id']))
    return out


def habit(c, hid):
    r = c.execute('SELECT * FROM habits WHERE id=?', (hid,)).fetchone(); return _habit(c, r) if r else None


def _plan(h):
    t = h.get('time') or None; et = (h.get('etime') or None) if t else None
    if et and et == t: et = None
    return dict(days=json.dumps(sorted(h.get('days') or list(range(7)))), time=t, etime=et,
                remind=int(h.get('remind', -1)), routine=h.get('routine', '') or '')


def save_habit(c, h, from_day=None):
    """new habit → plan from its start day. Existing habit → name/area/reasons change everywhere, but a changed plan
    starts on `from_day` (default today); the days before keep the old plan."""
    pl = _plan(h)
    if h.get('id'):
        hid = h['id']
        c.execute('UPDATE habits SET name=?, area_id=?, kind=?, why=?, start_day=COALESCE(?, start_day), routine=?, days=?, time=?, etime=?, remind=? WHERE id=?',
                  (h['name'].strip()[:200], h.get('area_id'), h.get('kind', 'build'), h.get('why', ''), h.get('start_day'),
                   pl['routine'], pl['days'], pl['time'], pl['etime'], pl['remind'], hid))
        cur = c.execute('SELECT * FROM habit_periods WHERE habit_id=? AND end IS NULL ORDER BY start DESC LIMIT 1', (hid,)).fetchone()
        eff = iso(from_day or today())
        if cur is None:
            c.execute('INSERT INTO habit_periods(habit_id, start, end, days, time, etime, remind, routine) VALUES(?,?,?,?,?,?,?,?)',
                      (hid, eff, None, pl['days'], pl['time'], pl['etime'], pl['remind'], pl['routine']))
        elif any(str(cur[k]) != str(pl[k]) for k in PLAN):
            if cur['start'] >= eff:                               # the plan only started today (or later): just correct it
                c.execute('UPDATE habit_periods SET days=?, time=?, etime=?, remind=?, routine=? WHERE id=?', (pl['days'], pl['time'], pl['etime'], pl['remind'], pl['routine'], cur['id']))
            else:                                                 # the days before keep their old days / times — history stays as it was
                c.execute('UPDATE habit_periods SET end=? WHERE id=?', (iso(date.fromisoformat(eff) - timedelta(days=1)), cur['id']))
                c.execute('INSERT INTO habit_periods(habit_id, start, end, days, time, etime, remind, routine) VALUES(?,?,?,?,?,?,?,?)',
                          (hid, eff, None, pl['days'], pl['time'], pl['etime'], pl['remind'], pl['routine']))
    else:
        start = h.get('start_day') or iso(today()); n = c.execute('SELECT COUNT(*) FROM habits').fetchone()[0]
        hid = c.execute('INSERT INTO habits(name, area_id, kind, routine, days, time, etime, remind, why, start_day, sort, created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (h['name'].strip()[:200], h.get('area_id'), h.get('kind', 'build'), pl['routine'], pl['days'], pl['time'], pl['etime'], pl['remind'],
                         h.get('why', ''), start, n, stamp())).lastrowid
        c.execute('INSERT INTO habit_periods(habit_id, start, end, days, time, etime, remind, routine) VALUES(?,?,?,?,?,?,?,?)',
                  (hid, start, None, pl['days'], pl['time'], pl['etime'], pl['remind'], pl['routine']))
    c.commit(); return hid


def end_habit(c, hid):
    """stop a habit: it leaves your lists from today (from tomorrow if today is already ticked); its history stays"""
    t = today(); done_today = c.execute("SELECT 1 FROM habit_log WHERE habit_id=? AND day=?", (hid, iso(t))).fetchone()
    last = iso(t if done_today else t - timedelta(days=1))
    for p in c.execute('SELECT * FROM habit_periods WHERE habit_id=? AND end IS NULL', (hid,)).fetchall():
        if p['start'] > last: c.execute('DELETE FROM habit_periods WHERE id=?', (p['id'],))   # a plan that never really started
        else: c.execute('UPDATE habit_periods SET end=? WHERE id=?', (last, p['id']))
    c.execute('UPDATE habits SET archived=1 WHERE id=?', (hid,)); c.commit()


def restart_habit(c, hid):
    h = habit(c, hid)
    if not h: return
    t = iso(today()); last = h['periods'][-1] if h['periods'] else None
    if last and last['end'] and last['end'] >= t: c.execute('UPDATE habit_periods SET end=NULL WHERE id=?', (last['id'],))
    else: c.execute('INSERT INTO habit_periods(habit_id, start, end, days, time, etime, remind, routine) VALUES(?,?,?,?,?,?,?,?)',
                    (hid, t, None, json.dumps(h['days'] or list(range(7))), h['time'], h.get('etime'), h['remind'] if h['remind'] is not None else -1, h['routine'] or ''))
    c.execute('UPDATE habits SET archived=0 WHERE id=?', (hid,)); c.commit()


def archive_habit(c, hid, on=True):
    end_habit(c, hid) if on else restart_habit(c, hid)


def time_range(p):
    """'7:50 AM – 8:10 AM' (or just the start)"""
    if not p or not p.get('time'): return ''
    return _t12(p['time']) + (' – ' + _t12(p['etime']) if p.get('etime') else '')


def span_minutes(p, default=15):
    """how long a check-in / habit block is (start → end, past midnight too)"""
    if not p or not p.get('time') or not p.get('etime'): return default
    a = int(p['time'][:2]) * 60 + int(p['time'][3:5]); b = int(p['etime'][:2]) * 60 + int(p['etime'][3:5])
    return (b - a) % (24 * 60) or default


def plan_text(p, routine=True):
    days = p['days'] or list(range(7))
    d = 'Every day' if len(days) == 7 else 'Weekdays' if sorted(days) == [0, 1, 2, 3, 4] else ' '.join(WEEKDAYS[x] for x in sorted(days))
    return '  ·  '.join(x for x in (d, time_range(p), (p['routine'] + ' routine') if p['routine'] and routine else '') if x)


def _t12(s):
    try: return datetime.strptime(s, '%H:%M').strftime('%I:%M %p').lstrip('0')
    except Exception: return s or ''


def _short(s): d = date.fromisoformat(s); return f'{d.day} {d:%b %Y}'


def period_lines(h):
    """['1 Sep 2026 – 20 Oct 2026: Weekdays · 9:00 PM', 'since 21 Oct 2026: Every day · 9:30 PM']"""
    out = []
    for p in h['periods']:
        when = f"{_short(p['start'])} – {_short(p['end'])}" if p['end'] else f"since {_short(p['start'])}"
        out.append(f'{when}:  {plan_text(p)}')
    return out


def log_map(c, hid, since):
    return {r['day']: r['state'] for r in c.execute('SELECT day, state FROM habit_log WHERE habit_id=? AND day>=?', (hid, iso(since)))}


def set_log(c, hid, d, state, at=None):
    """state: 'done' | 'skip' | None (clear). The clock time is kept only when it is real: ticking today, or a time you typed."""
    if state:
        old = c.execute('SELECT ts, note FROM habit_log WHERE habit_id=? AND day=?', (hid, iso(d))).fetchone()
        ts = (iso(d) + 'T' + at) if at else stamp() if d == today() else iso(d)
        if old and old['ts'] and 'T' in old['ts'] and not at and d != today(): ts = old['ts']      # editing a past day keeps the time it had
        c.execute('INSERT OR REPLACE INTO habit_log(habit_id, day, state, ts, note) VALUES(?,?,?,?,?)', (hid, iso(d), state, ts, (old['note'] if old else '') or ''))
    else: c.execute('DELETE FROM habit_log WHERE habit_id=? AND day=?', (hid, iso(d)))
    c.commit()


def toggle(c, hid, d=None):
    d = d or today(); cur = c.execute('SELECT state FROM habit_log WHERE habit_id=? AND day=?', (hid, iso(d))).fetchone()
    set_log(c, hid, d, None if cur and cur[0] == 'done' else 'done'); return not (cur and cur[0] == 'done')


def stats(c, h, days=30):
    """streak (planned days in a row; a skip or a day off doesn't break it; today counts once done), best, % of the last `days`.
    Only days the habit really existed count — days before it was added or after it was stopped are not 'missed'."""
    t = today(); start = date.fromisoformat(h['first_day'])
    logs = log_map(c, h['id'], t - timedelta(days=400))
    streak, d = 0, t
    while d >= start:
        if not active_on(h, d): break                             # it was stopped then: the streak can't reach past that
        if due_on(h, d):
            s = logs.get(iso(d))
            if s == 'done': streak += 1
            elif s == 'skip' or d == t: pass                      # today not done yet: still counting yesterday's streak
            else: break
        d -= timedelta(days=1)
    best = run = 0; d = max(start, t - timedelta(days=400))
    while d <= t:
        if not active_on(h, d): run = 0
        elif due_on(h, d):
            s = logs.get(iso(d))
            if s == 'done': run += 1; best = max(best, run)
            elif s != 'skip' and d != t: run = 0
        d += timedelta(days=1)
    due = [x for x in (t - timedelta(days=i) for i in range(days)) if due_on(h, x)]
    done = sum(1 for x in due if logs.get(iso(x)) == 'done')
    return {'streak': streak, 'best': best, 'pct': round(100 * done / len(due)) if due else 0, 'done_today': logs.get(iso(t)) == 'done',
            'logs': logs, 'since': h['first_day']}


def routines_today(c):
    """{routine: [habit + done]} for today's planned routine habits (today's plan, not an old one)"""
    t = today(); out = {}
    hs = [h for h in habits(c, 'build') if h['routine'] and due_on(h, t)]
    logs = {x['habit_id']: x['state'] for x in c.execute('SELECT habit_id, state FROM habit_log WHERE day=?', (iso(t),))}
    for r in ROUTINES + sorted({h['routine'] for h in hs} - set(ROUTINES)):
        items = [dict(h, done=logs.get(h['id']) == 'done') for h in hs if h['routine'] == r]
        if items: out[r] = items
    return out


def month_report(c, year, month):
    """what each routine looked like in that month, and how it went: {'routines': {name: [rows]}, 'done', 'due'}.
    A habit counts only for the days it existed in that month (with the plan it had then)."""
    import calendar as _c
    first = date(year, month, 1); last = date(year, month, _c.monthrange(year, month)[1]); upto = min(last, today())
    groups, tot_done, tot_due = {}, 0, 0
    for r in c.execute("SELECT * FROM habits WHERE kind='build' ORDER BY sort, id"):
        h = _habit(c, r, upto)
        ps = [p for p in h['periods'] if p['start'] <= iso(last) and (not p['end'] or p['end'] >= iso(first))]
        if not ps or first > today(): continue
        logs = log_map(c, h['id'], first)
        due = [first + timedelta(days=i) for i in range((upto - first).days + 1)] if upto >= first else []
        due = [d for d in due if due_on(h, d)]
        done = sum(1 for d in due if logs.get(iso(d)) == 'done')
        p_main = period_on(h, upto) or ps[-1]
        notes = []
        if first.isoformat() <= h['first_day'] <= last.isoformat(): notes.append(('Added ' + _short(h['first_day'])[:-5], 'added'))
        if ps[-1]['end'] and ps[-1]['end'] <= iso(last) and not any(p['start'] > ps[-1]['end'] for p in h['periods']):
            notes.append(('Stopped ' + _short(ps[-1]['end'])[:-5], 'stopped'))
        if len(ps) > 1: notes.append(('Plan changed ' + _short(ps[-1]['start'])[:-5], 'changed'))
        row = dict(id=h['id'], name=h['name'], area_id=h['area_id'], plan=plan_text(p_main, False), due=len(due), done=done,
                   pct=round(100 * done / len(due)) if due else 0, notes=notes)
        groups.setdefault(p_main['routine'] or '', []).append(row); tot_done += done; tot_due += len(due)
    return {'routines': groups, 'done': tot_done, 'due': tot_due, 'pct': round(100 * tot_done / tot_due) if tot_due else 0}


# ───────────────────────── quit a habit ─────────────────────────
def quit_stats(c, h):
    t = now(); start = datetime.fromisoformat((h.get('start_day') or iso(today())) + 'T00:00:00')
    ev = [dict(r) for r in c.execute('SELECT * FROM quit_events WHERE habit_id=? ORDER BY ts', (h['id'],))]
    relapses = [datetime.fromisoformat(e['ts']) for e in ev if e['kind'] == 'relapse']
    last = relapses[-1] if relapses else start
    marks = [start] + relapses + [t]
    best = max((marks[i + 1] - marks[i]).days for i in range(len(marks) - 1)) if len(marks) > 1 else 0
    urges = [e for e in ev if e['kind'] == 'urge']
    trig = {}
    for e in urges + [e for e in ev if e['kind'] == 'relapse']:
        if e['trigger']: trig[e['trigger']] = trig.get(e['trigger'], 0) + 1
    week = t - timedelta(days=7)
    return {'days': (t - last).days, 'hours': int((t - last).total_seconds() // 3600) % 24, 'since': last, 'best': best,
            'relapses': len(relapses), 'urges_week': sum(1 for e in urges if datetime.fromisoformat(e['ts']) >= week),
            'beaten': sum(1 for e in urges), 'triggers': sorted(trig.items(), key=lambda x: -x[1]), 'events': ev[::-1]}


def log_quit(c, hid, kind, trigger='', helped='', note='', when=None):
    c.execute('INSERT INTO quit_events(habit_id, ts, kind, trigger, helped, note) VALUES(?,?,?,?,?,?)',
              (hid, (when or now()).isoformat(timespec='seconds'), kind, trigger, helped, note)); c.commit()


# ───────────────────────── sleep ─────────────────────────
def sleeps(c, n=21):
    """newest first; minutes = time asleep (time in bed minus the time it took to fall asleep)"""
    out = []
    for r in c.execute('SELECT * FROM sleep ORDER BY bed DESC LIMIT ?', (n,)):
        d = dict(r); b, w = datetime.fromisoformat(d['bed']), datetime.fromisoformat(d['wake'])
        d['latency'] = int(d.get('latency') or 0)
        try: d['tags'] = json.loads(d.get('tags') or '[]')
        except Exception: d['tags'] = []
        d['in_bed'] = max(0, int((w - b).total_seconds() // 60)); d['minutes'] = max(0, d['in_bed'] - d['latency']); out.append(d)
    return out


def add_sleep(c, bed, wake, quality=3, note='', latency=0, tags=None, sid=None):
    if wake <= bed: wake += timedelta(days=1)
    vals = (bed.isoformat(timespec='minutes'), wake.isoformat(timespec='minutes'), int(quality), note, int(latency or 0), json.dumps(tags or []))
    if sid: c.execute('UPDATE sleep SET bed=?, wake=?, quality=?, note=?, latency=?, tags=? WHERE id=?', vals + (sid,))
    else: c.execute('INSERT INTO sleep(bed, wake, quality, note, latency, tags) VALUES(?,?,?,?,?,?)', vals)
    c.commit()


def delete_sleep(c, sid): c.execute('DELETE FROM sleep WHERE id=?', (sid,)); c.commit()


def hm(minutes): return f'{minutes // 60}h {minutes % 60:02d}m'


def night_of(bed):
    """the evening a night belongs to (gone to bed at 1 AM on Saturday = Friday night)"""
    b = datetime.fromisoformat(bed) if isinstance(bed, str) else bed
    return (b - timedelta(hours=12)).date()


# ───────────────────────── quick notes & memories ─────────────────────────
def notes(c, tag=None, archived=False, q=''):
    rows = [dict(r, tags=json.loads(r['tags'] or '[]')) for r in c.execute('SELECT * FROM notes WHERE archived=? ORDER BY pinned DESC, created DESC', (1 if archived else 0,))]
    if tag: rows = [r for r in rows if tag in r['tags']]
    if q: rows = [r for r in rows if q.lower() in (r['title'] + ' ' + r['content']).lower()]
    return rows


def save_note(c, n):
    vals = (n.get('title', '').strip()[:200], n.get('content', ''), json.dumps(n.get('tags') or []), int(n.get('pinned', 0)), int(n.get('resurface', 1)))
    if n.get('id'): c.execute('UPDATE notes SET title=?, content=?, tags=?, pinned=?, resurface=? WHERE id=?', vals + (n['id'],)); nid = n['id']
    else: nid = c.execute('INSERT INTO notes(title, content, tags, pinned, resurface, created) VALUES(?,?,?,?,?,?)', vals + (stamp(),)).lastrowid
    c.commit(); return nid


def archive_note(c, nid, on=True): c.execute('UPDATE notes SET archived=? WHERE id=?', (1 if on else 0, nid)); c.commit()


def memory_of_day(c):
    """one note to look back at today: same day in an earlier month/year first, else the one not shown the longest"""
    t = today(); rows = [r for r in notes(c) if r['resurface'] and (r['created'] or '')[:10] != iso(t)]      # a memory, not today's note
    if not rows: return None
    same = [r for r in rows if r['created'] and r['created'][5:10] == iso(t)[5:10] and r['created'][:10] != iso(t)]
    if same: return same[0]
    rnd = random.Random(iso(t))                               # same pick all day
    rows.sort(key=lambda r: (r['last_shown'] or '', r['id']))
    return rnd.choice(rows[:max(1, len(rows) // 3)])


def mark_shown(c, nid): c.execute('UPDATE notes SET last_shown=? WHERE id=?', (iso(today()), nid)); c.commit()


# ───────────────────────── inspiration ─────────────────────────
def quotes(c): return [dict(r) for r in c.execute('SELECT * FROM quotes WHERE archived=0 ORDER BY id')]


def add_quote(c, text, author=''):
    c.execute('INSERT INTO quotes(text, author) VALUES(?,?)', (text.strip(), author.strip())); c.commit()


def quote_of_day(c, salt=''):
    q = quotes(c)
    return random.Random(iso(today()) + salt).choice(q) if q else None


# ───────────────────────── today ─────────────────────────
def today_summary(c):
    t0 = iso(today()); b = task_buckets(c)
    hs = [h for h in habits(c, 'build') if due_on(h, today())]
    logs = {x['habit_id']: x['state'] for x in c.execute('SELECT habit_id, state FROM habit_log WHERE day=?', (t0,))}
    done_tasks = sum(1 for t in b['done'] if (t['done_at'] or '')[:10] == t0)
    total = len(b['today']) + len(b['overdue']) + done_tasks + len(hs)
    done = done_tasks + sum(1 for h in hs if logs.get(h['id']) == 'done')
    return {'total': total, 'done': done, 'tasks': b, 'habits': len(hs), 'habits_done': sum(1 for h in hs if logs.get(h['id']) == 'done')}


# ───────────────────────── reminders ─────────────────────────
def due_reminders(c, at=None, window=15):
    """[(key, title, body, kind, ref)] that are due now (within the last `window` minutes) and not sent yet"""
    at = at or now(); t = at.date(); out = []
    lo = at - timedelta(minutes=window)

    def fire(key, when, title, body, kind, ref):
        if lo <= when <= at and not c.execute('SELECT 1 FROM sent WHERE key=?', (key,)).fetchone(): out.append((key, title, body, kind, ref))

    def hhmm(s, d=t):
        try: h, m = map(int, s.split(':')); return datetime(d.year, d.month, d.day, h, m)
        except Exception: return None

    if setting(c, 'notify') != '1': return []
    for r in c.execute('SELECT * FROM snoozes WHERE until<=?', (at.isoformat(timespec='seconds'),)).fetchall():
        out.append((r['key'] + ':snz:' + r['until'], r['title'], r['body'], r['kind'], r['ref'])); c.execute('DELETE FROM snoozes WHERE key=?', (r['key'],))
    c.commit()
    for x in tasks(c, done=False):
        if x['remind'] is None or x['remind'] < 0 or not x['day'] or not x['time']: continue
        w = hhmm(x['time'], date.fromisoformat(x['day']))
        if w: fire(f"task:{x['id']}:{x['day']}", w - timedelta(minutes=x['remind']), x['title'],
                   ('Now' if not x['remind'] else f"In {x['remind']} min") + f" · {x['time']}", 'task', x['id'])
    logs = {x['habit_id'] for x in c.execute("SELECT habit_id FROM habit_log WHERE day=?", (iso(t),))}
    for h in habits(c):
        if h['remind'] is None or h['remind'] < 0 or not h['time'] or not due_on(h, t): continue
        w = hhmm(h['time'])
        if not w: continue
        if h['kind'] == 'quit':
            st = quit_stats(c, h)
            fire(f"quit:{h['id']}:{iso(t)}", w, f"{st['days']} days clean — keep it going",
                 (h['why'].splitlines()[0] if h['why'] else 'This time of day is a risky one. Phone away, lights on.'), 'quit', h['id'])
        elif h['id'] not in logs:
            fire(f"habit:{h['id']}:{iso(t)}", w - timedelta(minutes=h['remind']), h['name'], (h['routine'] + ' routine · ' if h['routine'] else '') + h['time'], 'habit', h['id'])
    m = hhmm(setting(c, 'morning_time'))
    if m:
        s = today_summary(c); q = quote_of_day(c)
        fire(f"morning:{iso(t)}", m, 'Good morning — your day',
             f"{len(s['tasks']['today'])} tasks today, {len(s['tasks']['overdue'])} overdue, {s['habits']} habits" + (f"\n“{q['text']}”" if q else ''), 'morning', None)
    m = hhmm(setting(c, 'memory_time'))
    if m:
        n = memory_of_day(c)
        if n: fire(f"memory:{iso(t)}", m, 'Memory of the day: ' + (n['title'] or 'a note'), (n['content'] or '')[:160], 'memory', n['id'])
    return out


def mark_sent(c, key): c.execute('INSERT OR REPLACE INTO sent(key, ts) VALUES(?,?)', (key, stamp())); c.commit()


def snooze(c, key, title, body, kind, ref, minutes=10):
    until = (now() + timedelta(minutes=minutes)).isoformat(timespec='seconds')
    c.execute('INSERT OR REPLACE INTO snoozes(key, until, title, body, kind, ref) VALUES(?,?,?,?,?,?)', (key.split(':snz:')[0], until, title, body, kind, ref)); c.commit()


# ───────────────────────── calendar (tasks with a date) ─────────────────────────
def calendar_events(start, end):
    """for Curio Calendar: dated tasks, your nights of sleep and focus sessions (routines / namaz / habits are not shown there)"""
    c = connect()
    try:
        out = []
        if setting(c, 'cal_sleep') == '1':
            try: ensure_recent_nights(c)                         # last night from your template (or the PC), even if Tracker was not opened
            except Exception: pass
            for night, b, w in planned_nights(c, start, end):
                out.append(dict(id=f"myday:plan:{iso(night)}", source='myday', record_id=None, date=b.date(), start=b, end=w, all_day=False,
                                title=f"Sleep · plan {hm(int((w - b).total_seconds() // 60))}", color='#6d5bd01a', ink='#6d5bd0', readonly=False, mkind='sleepplan', mid=iso(night),
                                calendar='Tracker · Sleep', detail='every night (your usual times) — drag to change this night'))
            for r in sleeps(c, 400):
                b, w = datetime.fromisoformat(r['bed']), datetime.fromisoformat(r['wake']); d = b.date()
                if start <= d <= end or start <= w.date() <= end:
                    out.append(dict(id=f"myday:sleep:{r['id']}", source='myday', record_id=None, date=d, start=b, end=w, all_day=False,
                                    title=f"Sleep · {hm(r['minutes'])}" + (' (auto)' if r.get('auto') else ''), color='#6d5bd033', ink='#6d5bd0', readonly=False, mkind='sleep', mid=r['id'],
                                    calendar='Tracker · Sleep', detail=''))
        if setting(c, 'cal_focus') == '1':
            for s_ in sessions(c, start, end):
                st, en = datetime.fromisoformat(s_['start']), datetime.fromisoformat(s_['end'])
                out.append(dict(id=f"myday:focus:{s_['id']}", source='myday', record_id=s_['task_id'], date=st.date(), start=st, end=en, all_day=False,
                                title=f"Focus · {s_['title']}", color='#f2602d33', ink='#f2602d', readonly=False, mkind='focus', mid=s_['id'], calendar='Tracker · Focus', detail=''))
        if setting(c, 'calendar') != '1': return out
        ar = {a['id']: a for a in areas(c, True)}
        for t in tasks(c):
            if not t['day']: continue
            d = date.fromisoformat(t['day'])
            if not (start <= d <= end): continue
            a = ar.get(t['area_id']) or {}
            col = a.get('color') or '#6b7280'
            if t['time']:
                h, m = map(int, t['time'].split(':')); s = datetime(d.year, d.month, d.day, h, m)
                e = s + timedelta(minutes=int(t['minutes'] or 30)); allday = False
            else: s, e, allday = datetime(d.year, d.month, d.day), None, True
            out.append(dict(id=f"myday:{t['id']}", source='myday', record_id=t['id'], date=d, start=s, end=e, all_day=allday,
                            title=('✓ ' if t['done_at'] else '') + t['title'], color=col + '33', ink=col, readonly=False, mkind='task', mid=t['id'],
                            calendar='Tracker · ' + (a.get('name') or 'Tasks'), detail=repeat_text(t['repeat'])))
        return out
    finally: c.close()



# ───────────────────────── 10.22: boards (status), history, focus, mood, sleep score ─────────────────────────
def set_status(c, tid, status):
    """move a task between board columns: idea / todo / doing / done"""
    t = task(c, tid)
    if not t: return
    if status == 'done': complete(c, tid, True); return
    if t['done_at']: complete(c, tid, False)
    c.execute('UPDATE tasks SET status=?, updated=? WHERE id=?', (status, stamp(), tid)); c.commit()


def task_status(t): return 'done' if t.get('done_at') else (t.get('status') or 'todo')


def set_log_detail(c, hid, d, at=None, note=None):
    """change the clock time ('HH:MM' or '' to clear) or the note of a day already in the history"""
    r = c.execute('SELECT * FROM habit_log WHERE habit_id=? AND day=?', (hid, iso(d))).fetchone()
    if not r: return
    if at is not None: c.execute('UPDATE habit_log SET ts=? WHERE habit_id=? AND day=?', ((iso(d) + 'T' + at) if at else iso(d), hid, iso(d)))
    if note is not None: c.execute('UPDATE habit_log SET note=? WHERE habit_id=? AND day=?', (note, hid, iso(d)))
    c.commit()


def log_rows(c, hid, start, end):
    """the history of one habit between two days, newest first: day, state ('done'/'skip'/'missed'/'off'), time, note"""
    h = habit(c, hid); out = []
    got = {r['day']: dict(r) for r in c.execute('SELECT * FROM habit_log WHERE habit_id=? AND day BETWEEN ? AND ?', (hid, iso(start), iso(end)))}
    d = min(end, today())
    while d >= start:
        r = got.get(iso(d))
        if r: out.append(dict(day=d, state=r['state'], time=r['ts'][11:16] if r['ts'] and 'T' in r['ts'] else '', note=r.get('note') or ''))
        elif due_on(h, d) and d < today(): out.append(dict(day=d, state='missed', time='', note=''))
        d -= timedelta(days=1)
    return out


def delete_habit(c, hid):
    """remove a habit and its whole history for good (asked for and confirmed in the window first)"""
    for t in ('habit_log', 'habit_periods', 'quit_events'): c.execute(f'DELETE FROM {t} WHERE habit_id=?', (hid,))
    c.execute('DELETE FROM habits WHERE id=?', (hid,)); c.commit()


def grid(c, hs, start, end):
    """history table: for every habit, one state per day — done / skip / missed / off (not planned) / none (did not exist) / later"""
    t = today(); out = []
    for h in hs:
        logs = {r['day']: r['state'] for r in c.execute('SELECT day, state FROM habit_log WHERE habit_id=? AND day BETWEEN ? AND ?', (h['id'], iso(start), iso(end)))}
        cells, done, due = [], 0, 0; d = start
        while d <= end:
            s = logs.get(iso(d))
            if d > t: st = 'later'
            elif not active_on(h, d): st = 'none'
            elif s == 'done': st = 'done'
            elif s == 'skip': st = 'skip'
            elif not due_on(h, d): st = 'off'
            elif d == t: st = 'today'
            else: st = 'missed'
            if st in ('done', 'missed'): due += 1
            if st == 'done': done += 1
            cells.append((d, st)); d += timedelta(days=1)
        out.append(dict(habit=h, cells=cells, done=done, due=due, pct=round(100 * done / due) if due else 0))
    return out


def time_pattern(c, h, days=30):
    """when you really tick it: [(day, minutes after midnight)], the usual time, and how often it was on time (±15 min of the plan)"""
    since = today() - timedelta(days=days); pts = []
    for r in c.execute("SELECT day, ts FROM habit_log WHERE habit_id=? AND state='done' AND day>=? AND ts LIKE '%T%'", (h['id'], iso(since))):
        try: tm = datetime.fromisoformat(r['ts']); pts.append((date.fromisoformat(r['day']), tm.hour * 60 + tm.minute))
        except Exception: pass
    if not pts: return dict(points=[], usual=None, on_time=None, late=None)
    ms = sorted(m for _, m in pts); usual = ms[len(ms) // 2]
    on = late = None
    if h.get('time'):
        pl = int(h['time'][:2]) * 60 + int(h['time'][3:5]); on = round(100 * sum(1 for m in ms if abs(m - pl) <= 15) / len(ms)); late = usual - pl
    return dict(points=sorted(pts), usual=f'{usual // 60:02d}:{usual % 60:02d}', on_time=on, late=late)


def day_scores(c, start, end):
    """{day: (done, planned)} — every dated task and every planned habit / check-in, as it was planned on that day"""
    out = {}; t = today()
    for x in c.execute("SELECT day, done_at FROM tasks WHERE day BETWEEN ? AND ? AND COALESCE(status,'') != 'cancelled'", (iso(start), iso(end))):
        d = date.fromisoformat(x['day']); a, b = out.get(d, (0, 0)); out[d] = (a + (1 if x['done_at'] else 0), b + 1)
    hs = [_habit(c, r) for r in c.execute("SELECT * FROM habits WHERE kind='build'")]
    logs = {}
    for r in c.execute("SELECT habit_id, day, state FROM habit_log WHERE day BETWEEN ? AND ?", (iso(start), iso(end))): logs[(r['habit_id'], r['day'])] = r['state']
    d = start
    while d <= min(end, t):
        for h in hs:
            if not due_on(h, d): continue
            s = logs.get((h['id'], iso(d)))
            if s == 'skip': continue
            a, b = out.get(d, (0, 0)); out[d] = (a + (1 if s == 'done' else 0), b + 1)
        d += timedelta(days=1)
    return out


def month_story(c, year, month):
    """the month in a few plain lines: how much got done, against last month, best and weakest days, what went well / slipped"""
    import calendar as _c
    first = date(year, month, 1); last = date(year, month, _c.monthrange(year, month)[1]); upto = min(last, today())
    sc = day_scores(c, first, last)
    pm = (first - timedelta(days=1)); pfirst = pm.replace(day=1)
    psc = day_scores(c, pfirst, pm)
    pct = lambda m: round(100 * sum(a for a, b in m.values()) / max(1, sum(b for a, b in m.values()))) if m else None
    now_p, prev_p = pct({k: v for k, v in sc.items() if k <= upto}), pct(psc)
    days = [(d, a / b) for d, (a, b) in sc.items() if b and d <= upto]
    best = max(days, key=lambda x: (x[1], x[0])) if days else None
    full = sum(1 for _, v in days if v >= .999)
    wd = {}
    for d, v in days: wd.setdefault(d.weekday(), []).append(v)
    weak = min(wd.items(), key=lambda x: sum(x[1]) / len(x[1])) if len(wd) >= 4 else None
    rep = month_report(c, year, month); rows = [r for g in rep['routines'].values() for r in g if r['due'] >= 3]
    good = sorted(rows, key=lambda r: -r['pct'])[:2]; bad = sorted(rows, key=lambda r: r['pct'])[:2]
    tasks_done = c.execute('SELECT COUNT(*) FROM tasks WHERE substr(done_at,1,10) BETWEEN ? AND ?', (iso(first), iso(last))).fetchone()[0]
    focus = c.execute('SELECT COALESCE(SUM(minutes),0) FROM focus_sessions WHERE substr(start,1,10) BETWEEN ? AND ?', (iso(first), iso(last))).fetchone()[0]
    return dict(scores=sc, pct=now_p, prev=prev_p, best=best, full_days=full, weak_day=(WEEKDAYS[weak[0]], round(100 * sum(weak[1]) / len(weak[1]))) if weak else None,
                good=good, bad=bad, tasks_done=tasks_done, focus=focus, days=len(days))


def up_next(c, limit=6):
    """what is still open today, in time order: [(HH:MM or '', title, kind, id, colour, late?)]"""
    t = today(); nowm = now().strftime('%H:%M'); ar = {a['id']: a for a in areas(c, True)}; out = []
    for x in tasks(c, done=False):
        if x['day'] == iso(t) or (x['day'] and x['day'] < iso(t)):
            out.append((x['time'] or '', x['title'], 'task', x['id'], (ar.get(x['area_id']) or {}).get('color') or '#6b7280', bool(x['day'] < iso(t) or (x['time'] and x['time'] < nowm))))
    logs = {r['habit_id'] for r in c.execute('SELECT habit_id FROM habit_log WHERE day=?', (iso(t),))}
    for h in habits(c, 'build'):
        if due_on(h, t) and h['id'] not in logs and h['time']:
            out.append((h['time'], h['name'], 'habit', h['id'], ROUTINE_COLORS.get(h['routine']) or (ar.get(h['area_id']) or {}).get('color') or '#6b7280', h['time'] < nowm))
    out.sort(key=lambda x: (x[0] == '', x[0]))
    return out[:limit] if limit else out


# focus timer: one at a time; it keeps running while Curio is closed (only its start time is saved)
def focus_state(c):
    try: f = json.loads(setting(c, 'focus') or '{}')
    except Exception: f = {}
    if not f: return None
    run = 0 if f.get('paused') else max(0, int((now() - datetime.fromisoformat(f['start'])).total_seconds()))
    f['elapsed'] = int(f.get('acc', 0)) + run; return f


def _save_seg(c, f, at=None):
    s = datetime.fromisoformat(f['start']); e = max(s, at or now()); mins = int((e - s).total_seconds() // 60)
    if (e - s).total_seconds() >= 60:
        t = task(c, f.get('task_id')) if f.get('task_id') else None
        c.execute('INSERT INTO focus_sessions(task_id, title, area_id, start, end, minutes, run, intent) VALUES(?,?,?,?,?,?,?,?)',
                  (f.get('task_id'), f.get('title', ''), (t or {}).get('area_id', f.get('area_id')), s.isoformat(timespec='seconds'), e.isoformat(timespec='seconds'), mins,
                   f.get('run', ''), f.get('intent', '')))
    return int((e - s).total_seconds())


def focus_start(c, tid=None, title='', planned=None, mode='up', intent=''):
    if focus_state(c): focus_stop(c)
    t = task(c, tid) if tid else None
    if t and not t['done_at'] and t.get('status') != 'doing': c.execute("UPDATE tasks SET status='doing' WHERE id=?", (tid,))
    f = dict(task_id=tid, title=(t or {}).get('title') or title or 'Focus', area_id=(t or {}).get('area_id'), start=stamp(), acc=0, paused=False,
             planned=int(planned or (t or {}).get('minutes') or 25), mode=mode, done_before=tracked(c, tid) if tid else 0,
             run=stamp(), intent=intent or '', asked=stamp(), allow=[])
    set_setting(c, 'focus', json.dumps(f)); log_event(c, 'start', tid, f['run'], note=intent); return f


def focus_update(c, **kw):
    """change something on the running timer (when it last asked, apps allowed for this task …)"""
    f = focus_state(c)
    if not f: return None
    f.update(kw); f.pop('elapsed', None); set_setting(c, 'focus', json.dumps(f)); return focus_state(c)


def focus_pause(c, at=None):
    """pause / resume. `at`: pause as of an earlier moment (you were away since then — that time is not counted)"""
    f = focus_state(c)
    if not f: return
    if f.get('paused'): f.update(paused=False, start=stamp(), asked=stamp())
    else: f['acc'] = int(f.get('acc', 0)) + _save_seg(c, f, at); f['paused'] = True
    f.pop('elapsed', None); set_setting(c, 'focus', json.dumps(f))


def focus_stop(c, done=False, rating=None):
    f = focus_state(c)
    if not f: return
    if not f.get('paused'): _save_seg(c, f)
    if rating: c.execute('UPDATE focus_sessions SET rating=? WHERE run=?', (int(rating), f.get('run', '')))
    log_event(c, 'done' if done else 'stop', f.get('task_id'), f.get('run', ''), seconds=f['elapsed'])
    set_setting(c, 'focus', '')
    if done and f.get('task_id'): complete(c, f['task_id'], True)
    c.commit()


def tracked(c, tid):
    return c.execute('SELECT COALESCE(SUM(minutes),0) FROM focus_sessions WHERE task_id=?', (tid,)).fetchone()[0] if tid else 0


def tracked_map(c): return {r[0]: r[1] for r in c.execute('SELECT task_id, SUM(minutes) FROM focus_sessions WHERE task_id IS NOT NULL GROUP BY task_id')}


def sessions(c, start, end):
    return [dict(r) for r in c.execute('SELECT * FROM focus_sessions WHERE substr(start,1,10) BETWEEN ? AND ? ORDER BY start DESC', (iso(start), iso(end)))]


def add_session(c, tid, start, minutes, sid=None):
    t = task(c, tid) if tid else None; end = start + timedelta(minutes=int(minutes))
    v = (tid, (t or {}).get('title', 'Focus'), (t or {}).get('area_id'), start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds'), int(minutes))
    if sid: c.execute('UPDATE focus_sessions SET task_id=?, title=?, area_id=?, start=?, end=?, minutes=? WHERE id=?', v + (sid,))
    else: c.execute('INSERT INTO focus_sessions(task_id, title, area_id, start, end, minutes) VALUES(?,?,?,?,?,?)', v)
    c.commit()


def delete_session(c, sid): c.execute('DELETE FROM focus_sessions WHERE id=?', (sid,)); c.commit()


# mood
def set_mood(c, d, v, note=''):
    if v: c.execute('INSERT OR REPLACE INTO mood(day, mood, ts, note) VALUES(?,?,?,?)', (iso(d), int(v), stamp(), note))
    else: c.execute('DELETE FROM mood WHERE day=?', (iso(d),))
    c.commit()


def moods(c, n=14):
    since = today() - timedelta(days=n - 1)
    return {date.fromisoformat(r['day']): r['mood'] for r in c.execute('SELECT * FROM mood WHERE day>=?', (iso(since),))}


# sleep score: hours vs your goal (50) + how rested you felt (30) + in bed on time (20)
def sleep_score(c, r):
    goal = int(setting(c, 'sleep_goal') or 450); bg = setting(c, 'bed_goal') or '23:00'
    b = datetime.fromisoformat(r['bed']); n0 = night_of(r['bed'])
    target = datetime(n0.year, n0.month, n0.day, int(bg[:2]), int(bg[3:5]))
    if target.hour < 12: target += timedelta(days=1)
    late = int((b - target).total_seconds() // 60)
    hours = min(1, r['minutes'] / goal); rest = (int(r['quality'] or 3) - 1) / 4; ontime = 1 if late <= 15 else max(0, 1 - (late - 15) / 120)
    return dict(score=round(50 * hours + 30 * rest + 20 * ontime), hours_pct=round(100 * r['minutes'] / goal), late=late, goal=goal)


def sleep_week(c):
    rows = sleeps(c, 7); goal = int(setting(c, 'sleep_goal') or 450)
    if not rows: return None
    avg = sum(r['minutes'] for r in rows) // len(rows)
    debt = sum(r['minutes'] - goal for r in rows)
    sc = [sleep_score(c, r) for r in rows]; beds = [r['in_bed'] and (datetime.fromisoformat(r['bed']).hour * 60 + datetime.fromisoformat(r['bed']).minute + (1440 if datetime.fromisoformat(r['bed']).hour < 12 else 0)) for r in rows]
    mean = sum(beds) / len(beds); spread = round((sum((x - mean) ** 2 for x in beds) / len(beds)) ** .5)
    best = max(rows, key=lambda r: r['minutes'])
    return dict(avg=avg, debt=debt, on_time=sum(1 for s in sc if s['late'] <= 15), nights=len(rows), spread=spread, best=best,
                score=round(sum(s['score'] for s in sc) / len(sc)))


def sleep_factors(c):
    """for each tag: how much longer / shorter you slept on nights with it than without (needs a few nights of each)"""
    rows = sleeps(c, 60); out = []
    for tag in sorted({t for r in rows for t in r['tags']}):
        a = [r['minutes'] for r in rows if tag in r['tags']]; b = [r['minutes'] for r in rows if tag not in r['tags']]
        if len(a) >= 2 and len(b) >= 2: out.append((tag, round(sum(a) / len(a) - sum(b) / len(b)), len(a)))
    return sorted(out, key=lambda x: x[1])


def demo_extras(c):
    """10.22 additions for the demo book only (board columns, focus sessions, mood, sleep details, a Day routine, real tick times).
    Runs once; your own myday.db is never touched by this."""
    if setting(c, 'demo_v') >= '2': return
    set_setting(c, 'demo_v', '1')
    rnd = random.Random(22); t = today(); A = {a['name']: a['id'] for a in areas(c, True)}
    st = {'Notebook organisation': 'idea', 'Blender 3D — donut tutorial': 'idea', 'Watch: video on hair care': 'idea', 'Meta Ads course — module 3': 'doing'}
    for tt in tasks(c):
        if tt['title'] in st: c.execute('UPDATE tasks SET status=? WHERE id=?', (st[tt['title']], tt['id']))
    mins = {'Figma class — auto layout': 45, 'Meta Ads course — module 3': 60, 'Organise hard drive (D:)': 60, 'Grocery shopping': 45, 'Hair oiling': 15}
    for tt in tasks(c):
        if tt['title'] in mins: c.execute('UPDATE tasks SET minutes=? WHERE id=?', (mins[tt['title']], tt['id']))
    for title, area, k, rep in [('Logo revisions for client', 'Responsibilities', 0, None), ('Read: brand strategy chapter', 'Skill Learn', 1, None),
                                 ('Plan next week', 'Self-Improve', 2, None), ('Clean the desk', 'Self-Improve', -2, None)]:
        save_task(c, dict(title=title, area_id=A.get(area), day=iso(t + timedelta(days=k)), time='15:00' if k == 0 else None, minutes=90 if k == 0 else 30))
    for name, tm in [('Plan the day (5 min)', '09:30'), ('Lunch away from the desk', '13:30'), ('Inbox zero', '17:00')]:
        hid = save_habit(c, dict(name=name, area_id=A.get('Self-Improve'), routine='Day', time=tm, remind=-1, days=[0, 1, 2, 3, 4, 5], start_day=iso(t - timedelta(days=25))))
        h = habit(c, hid)
        for k in range(1, 26):
            d = t - timedelta(days=k)
            if due_on(h, d) and rnd.random() < .7: c.execute('INSERT OR REPLACE INTO habit_log(habit_id, day, state, ts) VALUES(?,?,?,?)', (hid, iso(d), 'done', iso(d)))
    for r in c.execute("SELECT l.habit_id, l.day, p.time FROM habit_log l JOIN habit_periods p ON p.habit_id=l.habit_id AND p.start<=l.day AND (p.end IS NULL OR l.day<=p.end) "
                       "WHERE l.state='done' AND l.ts NOT LIKE '%T%'").fetchall():
        base = r['time'] or '20:00'; m = int(base[:2]) * 60 + int(base[3:5]) + int(rnd.gauss(14, 22)); m = max(0, min(23 * 60 + 59, m))
        c.execute('UPDATE habit_log SET ts=? WHERE habit_id=? AND day=?', (f"{r['day']}T{m // 60:02d}:{m % 60:02d}", r['habit_id'], r['day']))
    eff = {'Phone in bed': -40, 'Tea / coffee after 6': -25, 'Late dinner': -20, 'Stressed': -30, 'Walked today': 20, 'Read before sleep': 30}
    for r in c.execute('SELECT id, wake FROM sleep').fetchall():
        tags = [x for x in SLEEP_TAGS if rnd.random() < .3]; w = datetime.fromisoformat(r['wake']) + timedelta(minutes=sum(eff[x] for x in tags))
        c.execute('UPDATE sleep SET latency=?, tags=?, wake=? WHERE id=?', (rnd.choice([5, 10, 15, 20, 30, 40]), json.dumps(tags), w.isoformat(timespec='minutes'), r['id']))
    for k, title, area in [(3, 'Send invoice to client', 'Responsibilities'), (5, 'Figma: components lesson', 'Skill Learn'), (6, 'Car service booking', 'Responsibilities'),
                           (9, 'Meta Ads — module 2', 'Skill Learn'), (11, 'Declutter downloads folder', 'Self-Improve'), (13, 'Buy vitamins', 'Health'),
                           (16, 'Figma: variants lesson', 'Skill Learn'), (19, 'Back up phone photos', 'Self-Improve')]:
        d = t - timedelta(days=k); tid = save_task(c, dict(title=title, area_id=A.get(area), day=iso(d), minutes=45))
        c.execute('UPDATE tasks SET done_at=? WHERE id=?', (datetime(d.year, d.month, d.day, rnd.randint(10, 20), rnd.choice([5, 25, 40])).isoformat(timespec='seconds'), tid))
    for k in range(0, 14):
        if rnd.random() < .85: c.execute('INSERT OR REPLACE INTO mood(day, mood, ts) VALUES(?,?,?)', (iso(t - timedelta(days=k)), rnd.choice([2, 3, 3, 4, 4, 4, 5]), stamp()))
    for k in range(1, 8):
        d = t - timedelta(days=k)
        for _ in range(rnd.randint(1, 3)):
            pool = [x for x in tasks(c) if x['title'] in ('Figma class — auto layout', 'Meta Ads course — module 3', 'Organise hard drive (D:)', 'Hair oiling', 'Grocery shopping')
                    or (x['done_at'] and x['day'] and x['day'] <= iso(d))]
            tt = rnd.choice(pool); s0 = datetime(d.year, d.month, d.day, rnd.randint(10, 21), rnd.choice([0, 15, 30, 45]))
            add_session(c, tt['id'], s0, max(10, int(int(tt['minutes'] or 30) * rnd.uniform(.4, .9))))
    for title, h0, m0, mm in [('Check Lensequee inventory', 11, 0, 20), ('Logo revisions for client', 13, 12, 72), ('Logo revisions for client', 14, 36, 54)]:
        tt = next((x for x in tasks(c) if x['title'] == title), None)
        if tt: add_session(c, tt['id'], datetime(t.year, t.month, t.day, h0, m0), mm)
    set_setting(c, 'demo_v', '2'); c.commit()


def demo_extras3(c):
    """10.25 demo additions: things left half-done (to pick up again) and a day of screen activity"""
    if setting(c, 'demo_v') >= '3': return
    rnd = random.Random(25); t = today(); A = {a['name']: a['id'] for a in areas(c, True)}
    old = (now() - timedelta(days=3)).isoformat(timespec='seconds')
    for tt in tasks(c):
        if tt['title'] == 'Meta Ads course — module 3':
            c.execute('UPDATE tasks SET updated=?, note=? WHERE id=?', (old, '[19 Nov] Stopped at: lesson 4 (lookalike audiences)  Next: finish lesson 4 quiz', tt['id']))
            c.execute('UPDATE focus_sessions SET end=start WHERE task_id=? AND substr(start,1,10) >= ?', (tt['id'], iso(t - timedelta(days=2))))
    tid = save_task(c, dict(title='AI agent room (Hermes bots)', area_id=A.get('Skill Learn'), status='doing', minutes=90,
                            note='[20 Nov] Stopped at: chief bot + folders  Next: set up the marketer bot profile'))
    c.execute('UPDATE tasks SET updated=?, created=? WHERE id=?', ((now() - timedelta(days=2)).isoformat(timespec='seconds'), (now() - timedelta(days=4)).isoformat(timespec='seconds'), tid))
    t0 = datetime(t.year, t.month, t.day, 10, 0); cur = t0
    plan = [('figma', 'Client logo — Figma', 'task', 55), ('chrome', 'YouTube - Figma auto layout tutorial', 'learning', 25), ('chrome', 'Instagram', 'distraction', 18),
            ('whatsapp', 'WhatsApp', 'distraction', 12), ('code', 'Curio — Visual Studio Code', 'work', 40), ('chrome', 'Meta Ads Manager', 'work', 35),
            ('chrome', 'YouTube - funny clips', 'distraction', 22), ('figma', 'Client logo — Figma', 'task', 45)]
    for app, title, cat, m in plan:
        e = cur + timedelta(minutes=m)
        if e > now(): break
        c.execute('INSERT INTO activity(start, end, app, title, cat) VALUES(?,?,?,?,?)', (cur.isoformat(timespec='seconds'), e.isoformat(timespec='seconds'), app, title, cat))
        cur = e + timedelta(minutes=rnd.randint(2, 15))
    set_setting(c, 'demo_v', '3'); c.commit()


# ───────────────────────── 10.23: focus coach — stay on one thing ─────────────────────────
# Ideas from research, built in: say what "done" looks like before you start (implementation intentions); park a stray thought
# instead of following it (a written plan quiets an unfinished goal — Masicampo & Baumeister 2011); a short "where I stopped / next step"
# note when you switch (ready-to-resume plan — Leroy & Glomb 2018); being asked "still on it?" now and then (progress monitoring —
# Harkin et al. 2016). Everything here stays on this PC.
DRIFT_PULLS = ['Phone', 'YouTube', 'Instagram', 'WhatsApp', 'Another task', 'Someone talked to me', 'Felt stuck', 'Tired', 'Hungry', 'Other']


def log_event(c, kind, task_id=None, run='', app='', title='', note='', seconds=0, when=None):
    c.execute('INSERT INTO focus_events(ts, kind, task_id, run, app, title, note, seconds) VALUES(?,?,?,?,?,?,?,?)',
              ((when or now()).isoformat(timespec='seconds'), kind, task_id, run or '', (app or '')[:80], (title or '')[:160], (note or '')[:300], int(seconds or 0)))
    c.commit()


def events(c, start, end, kinds=None):
    q, a = 'SELECT * FROM focus_events WHERE substr(ts,1,10) BETWEEN ? AND ?', [iso(start), iso(end)]
    if kinds: q += ' AND kind IN (%s)' % ','.join('?' * len(kinds)); a += list(kinds)
    return [dict(r) for r in c.execute(q + ' ORDER BY ts', a)]


def park(c, text, task_id=None):
    c.execute('INSERT INTO parked(text, ts, task_id) VALUES(?,?,?)', (text.strip()[:300], stamp(), task_id)); c.commit()
    f = focus_state(c); log_event(c, 'park', (f or {}).get('task_id'), (f or {}).get('run', ''), note=text)


def parked(c, done=False): return [dict(r) for r in c.execute('SELECT * FROM parked WHERE done=? ORDER BY ts DESC', (1 if done else 0,))]


def park_done(c, pid, on=True): c.execute('UPDATE parked SET done=? WHERE id=?', (1 if on else 0, pid)); c.commit()


def park_to_task(c, pid):
    r = c.execute('SELECT * FROM parked WHERE id=?', (pid,)).fetchone()
    if not r: return None
    t = task(c, r['task_id']) if r['task_id'] else None
    tid = save_task(c, dict(title=r['text'], area_id=(t or {}).get('area_id') or (areas(c) or [{}])[0].get('id'), status='idea'))
    park_done(c, pid); return tid


def is_distracting(c, app, title):
    """is this window one of the 'pulls' on your list? → the word that matched, else ''"""
    try: words = [w.strip().lower() for w in json.loads(setting(c, 'coach_apps') or '[]') if w.strip()]
    except Exception: words = []
    hay = f' {app} {title} '.lower()
    return next((w for w in words if w in hay), '')


def focus_report(c, d=None):
    """one day of focus: minutes, sessions, how often you drifted and to what, check-in answers, longest run without drifting"""
    d = d or today(); ss = sessions(c, d, d); ev = events(c, d, d)
    drifts = [e for e in ev if e['kind'] in ('drift', 'nudge_back')]; yes = sum(1 for e in ev if e['kind'] == 'still_yes')
    asked = sum(1 for e in ev if e['kind'] in ('still_yes', 'drift', 'switch'))
    pulls = {}
    for e in drifts: k = e['app'] or e['note'] or 'Other'; pulls[k] = pulls.get(k, 0) + 1
    away = sum(e['seconds'] for e in ev if e['kind'] in ('away', 'nudge_back', 'drift'))
    # the longest stretch of a session with no drift in it
    best = 0
    for s in ss:
        st, en = datetime.fromisoformat(s['start']), datetime.fromisoformat(s['end']); marks = [st]
        marks += [datetime.fromisoformat(e['ts']) for e in drifts if st <= datetime.fromisoformat(e['ts']) <= en] + [en]
        best = max([best] + [int((marks[i + 1] - marks[i]).total_seconds() // 60) for i in range(len(marks) - 1)])
    switches = sum(1 for e in ev if e['kind'] == 'switch')
    rated = [s['rating'] for s in ss if s.get('rating')]
    return dict(minutes=sum(s['minutes'] for s in ss), sessions=len(ss), drifts=len(drifts), pulls=sorted(pulls.items(), key=lambda x: -x[1]),
                on_track=round(100 * yes / asked) if asked else None, asked=asked, longest=best, switches=switches, away=away // 60,
                parked=sum(1 for e in ev if e['kind'] == 'park'), rating=round(sum(rated) / len(rated), 1) if rated else None,
                samples=[e for e in ev if e['kind'] == 'sample'])


def top3(c, d=None):
    try: ids = json.loads(setting(c, 'top3:' + iso(d or today())) or '[]')
    except Exception: ids = []
    return [t for t in (task(c, i) for i in ids) if t]


def set_top3(c, ids, d=None): set_setting(c, 'top3:' + iso(d or today()), json.dumps([int(i) for i in ids][:3]))


def work_hours_now(c, at=None):
    at = at or now(); a, b = setting(c, 'work_start') or '10:00', setting(c, 'work_end') or '19:00'
    return a <= at.strftime('%H:%M') < b


# ───────────────────────── inspo board (pictures, videos, links, quotes — from My Media, pasted or dropped in) ─────────────────────────
INSPO_DIR = HOME / 'inspo'
IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
VID_EXT = {'.mp4', '.mov', '.webm', '.mkv', '.m4v', '.avi'}


def inspo_sections(c):
    try: return json.loads(setting(c, 'inspo_sections') or '[]') or ['My Inspo']
    except Exception: return ['My Inspo']


def inspo_items(c, section=None):
    q, a = 'SELECT * FROM inspo', []
    if section: q += ' WHERE section=?'; a.append(section)
    return [dict(r) for r in c.execute(q + ' ORDER BY pinned DESC, sort DESC, id DESC', a)]


def add_inspo(c, kind, section='My Inspo', title='', text='', path='', ref='', url='', habit_id=None):
    n = c.execute('SELECT COALESCE(MAX(sort),0) FROM inspo').fetchone()[0] + 1
    iid = c.execute('INSERT INTO inspo(section, kind, title, text, path, ref, url, habit_id, sort, created) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (section, kind, title[:200], text, str(path or ''), ref, url, habit_id, n, stamp())).lastrowid
    c.commit(); return iid


def update_inspo(c, iid, **kw):
    for k in ('section', 'title', 'text', 'pinned', 'habit_id', 'path', 'kind', 'sort', 'color'):
        if k in kw: c.execute(f'UPDATE inspo SET {k}=? WHERE id=?', (kw[k], iid))
    c.commit()


def remove_inspo(c, iid):
    """takes the card off the board. A file you dropped in is kept in myday/inspo (nothing is deleted from your PC)."""
    c.execute('DELETE FROM inspo WHERE id=?', (iid,)); c.commit()


def keep_file(src):
    """copy a dropped / chosen file into <data>/myday/inspo so the board keeps working if the original moves"""
    import shutil, uuid
    src = Path(src); INSPO_DIR.mkdir(parents=True, exist_ok=True)
    out = INSPO_DIR / f'{uuid.uuid4().hex[:12]}{src.suffix.lower()}'; shutil.copy2(src, out); return out


def kind_of(path):
    e = Path(str(path)).suffix.lower()
    return 'image' if e in IMG_EXT else 'video' if e in VID_EXT else 'file'


def youtube_id(url):
    import re
    m = re.search(r'(?:youtu\.be/|v=|shorts/|embed/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else ''


def inspo_pick(c, salt=''):
    """one card for today (Today page, reminders, 'I'm struggling') — pinned ones come up more often"""
    items = [i for i in inspo_items(c) if i['kind'] in ('image', 'video', 'media', 'quote', 'link')]
    if not items: return None
    pool = items + [i for i in items if i['pinned']] * 2
    return random.Random(iso(today()) + str(salt)).choice(pool)


def goals(c, kind='goal', done=None):
    q, a = 'SELECT * FROM goals WHERE kind=?', [kind]
    if done is True: q += ' AND done_at IS NOT NULL'
    if done is False: q += ' AND done_at IS NULL'
    return [dict(r) for r in c.execute(q + ' ORDER BY done_at IS NOT NULL, sort, id', a)]


def save_goal(c, g):
    v = (g.get('kind', 'goal'), g['title'].strip()[:200], g.get('why', ''), g.get('due') or None, int(g.get('progress') or 0))
    if g.get('id'): c.execute('UPDATE goals SET kind=?, title=?, why=?, due=?, progress=? WHERE id=?', v + (g['id'],)); gid = g['id']
    else: gid = c.execute('INSERT INTO goals(kind, title, why, due, progress, created) VALUES(?,?,?,?,?,?)', v + (stamp(),)).lastrowid
    c.commit(); return gid


def goal_done(c, gid, on=True): c.execute('UPDATE goals SET done_at=? WHERE id=?', (stamp() if on else None, gid)); c.commit()


def delete_goal(c, gid): c.execute('DELETE FROM goals WHERE id=?', (gid,)); c.commit()


def demo_inspo(c, library_items, first_media):
    """demo only: fill the board with a few of YOUR saves from My Media (just references — nothing is copied or changed)"""
    if setting(c, 'demo_inspo') == '1': return False
    pool = [i for i in library_items if first_media(i)[0]]
    if not pool: return False
    rnd = random.Random(23); secs = inspo_sections(c)
    for k, it in enumerate(rnd.sample(pool, min(18, len(pool)))):
        cap = (it.get('caption') or it.get('title') or it.get('text') or '').strip().split('\n')[0][:90]
        add_inspo(c, 'media', secs[k % len(secs)], cap, '', '', f"{it['platform']}|{it['key']}")
    for r in c.execute('SELECT id FROM inspo').fetchall(): c.execute('UPDATE inspo SET sort=? WHERE id=?', (rnd.random() * 100, r['id']))   # mix quotes and pictures
    set_setting(c, 'demo_inspo', '1'); c.commit(); return True


def demo_inspo_cards(c):
    """demo only: quote cards and goals, like your Notion Inspo page"""
    if setting(c, 'demo_cards') == '1': return
    for sec, title, text in [('Reset', 'Don’t be lazy — do your skincare routine!', ''), ('My Inspo', 'Run, baby, RUN!', 'The obsession with running is really an obsession with the potential for more and more life.'),
                             ('Life I want', 'Be the real man', 'That every eye is on you — not yours on everyone.'), ('Reset', 'Eat healthy most of the time', 'Healthy body, healthy mind.'),
                             ('My Inspo', 'The world is here to be discovered.', 'Just keep swimming…'), ('GOAT', 'Do great work', 'The only way to do great work is to love what you do. — Steve Jobs')]:
        add_inspo(c, 'quote', sec, title, text)
    for title, why, prog, due in [('Launch the brand-colour course', 'Teach what I know, earn while I sleep', 35, '2026-12-31'), ('Run 5 km without stopping', 'Energy for everything else', 60, None),
                                  ('Save for the studio setup', 'A room that makes me want to work', 20, None)]:
        save_goal(c, dict(title=title, why=why, progress=prog, due=due))
    for title in ('Plan for studying abroad', 'Learn Spanish', 'Travel the world — solo'): save_goal(c, dict(kind='dream', title=title))
    set_setting(c, 'demo_cards', '1')

# ───────────────────────── 10.25: repeating series, timeline, pick-up, auto sleep, activity, nudges, day plan ─────────────────────────
def series_list(c):
    """every repeating task as one line: how it repeats, since when, how often done, the next one, and whether it still runs"""
    rows = [dict(r) for r in c.execute('SELECT * FROM tasks WHERE series IS NOT NULL OR repeat IS NOT NULL ORDER BY id')]
    by = {}
    for r in rows: by.setdefault(r['series'] or r['id'], []).append(r)
    ar = {a['id']: a for a in areas(c, True)}; out = []
    for sid, ts in by.items():
        last = ts[-1]; rule = json.loads(last['repeat']) if last['repeat'] else None
        rules = [json.loads(t['repeat']) for t in ts if t['repeat']]
        if not rule and not rules: continue
        open_ = [t for t in ts if not t['done_at'] and (t['status'] or '') != 'cancelled']
        done = [t for t in ts if t['done_at']]
        days = sorted(t['day'] for t in ts if t['day'])
        end = (open_[0].get('repeat_end') if open_ else last.get('repeat_end')) or ''
        if any((t['status'] or '') == 'cancelled' for t in ts) and not open_: state = 'stopped'
        elif open_ and any(t['repeat'] for t in open_): state = 'ending' if end else 'running'
        else: state = 'ended'
        out.append(dict(id=sid, title=last['title'], area=(ar.get(last['area_id']) or {}).get('name', ''), color=(ar.get(last['area_id']) or {}).get('color'),
                        rule=repeat_text(rule or rules[-1]), rule_raw=rule or rules[-1], started=days[0] if days else (ts[0]['created'] or '')[:10],
                        done=len(done), last_done=max((t['done_at'] or '')[:10] for t in done) if done else '', next=open_[0]['day'] if open_ else '',
                        open_id=open_[0]['id'] if open_ else None, end=end, state=state, time=last['time'],
                        stopped=max(((t['updated'] or '')[:10] for t in ts if (t['status'] or '') == 'cancelled'), default='')))
    out.sort(key=lambda x: (x['state'] != 'running', x['title'].lower()))
    return out


def series_history(c, sid):
    return [dict(r) for r in c.execute("SELECT id, day, time, done_at, status FROM tasks WHERE series=? OR id=? ORDER BY day DESC, id DESC", (sid, sid))]


def stop_series(c, sid, end_day=None):
    """stop a repeating task from `end_day` (default today). Days already done stay in the history; a copy waiting after the end is
    taken off your lists (marked stopped — not deleted)."""
    end = iso(end_day or today())
    for t in [dict(r) for r in c.execute("SELECT * FROM tasks WHERE (series=? OR id=?) AND done_at IS NULL AND COALESCE(status,'') != 'cancelled'", (sid, sid))]:
        if t['day'] and t['day'] > end: c.execute("UPDATE tasks SET status='cancelled', repeat_end=?, updated=? WHERE id=?", (end, stamp(), t['id']))
        else: c.execute('UPDATE tasks SET repeat_end=?, updated=? WHERE id=?', (end, stamp(), t['id']))
    c.commit()


def restart_series(c, sid, from_day=None):
    """bring a stopped / ended repeating task back from `from_day` (default today)"""
    ts = series_history(c, sid)
    if not ts: return
    last = task(c, ts[0]['id']); d0 = iso(from_day or today())
    open_ = [t for t in ts if not t['done_at'] and (t['status'] or '') != 'cancelled']
    if open_: c.execute('UPDATE tasks SET repeat_end=NULL WHERE id=?', (open_[0]['id'],)); c.execute("UPDATE tasks SET status='todo' WHERE id=? AND status='cancelled'", (open_[0]['id'],))
    else:
        rule = last['repeat'] or next((json.loads(r['repeat']) for r in c.execute('SELECT repeat FROM tasks WHERE (series=? OR id=?) AND repeat IS NOT NULL ORDER BY id DESC', (sid, sid))), None)
        nt = dict(last, day=d0, repeat=rule, status='todo'); nt.pop('id')
        nid = save_task(c, nt); c.execute('UPDATE tasks SET series=?, repeat_end=NULL WHERE id=?', (sid, nid))
    c.commit()


def set_series_end(c, sid, end_day):
    for r in c.execute("SELECT id FROM tasks WHERE (series=? OR id=?) AND done_at IS NULL AND COALESCE(status,'') != 'cancelled'", (sid, sid)).fetchall():
        c.execute('UPDATE tasks SET repeat_end=? WHERE id=?', (iso(end_day) if end_day else None, r['id']))
    c.commit()


def rel_time(target, at=None):
    """'in 2 h 30 m' / 'in 25 min' / 'in 40 s' / '15 min ago' / 'now'"""
    at = at or now(); s = int((target - at).total_seconds()); a = abs(s)
    if a < 30: return 'now'
    txt = f'{a} s' if a < 60 else f'{a // 60} min' if a < 3600 else f'{a // 3600} h' + (f' {(a % 3600) // 60:02d} m' if (a % 3600) // 60 else '') if a < 86400 * 2 else f'{a // 86400} days'
    return ('in ' + txt) if s > 0 else (txt + ' ago')


def timeline(c, d=None):
    """everything planned (and done) on one day, in time order, each with a type tag — the one place to look (for you and the AI)"""
    d = d or today(); D = iso(d); out = []; ar = {a['id']: a for a in areas(c, True)}; t_now = now()
    logs = {r['habit_id']: dict(r) for r in c.execute('SELECT * FROM habit_log WHERE day=?', (D,))}

    def state_for(when, done, skipped=False):
        if done: return 'done'
        if skipped: return 'skipped'
        if when and when < t_now: return 'missed' if d < today() else 'late'
        return 'upcoming' if d >= today() else 'missed'

    def at(hm):
        try: return datetime(d.year, d.month, d.day, int(hm[:2]), int(hm[3:5]))
        except Exception: return None
    for x in tasks(c):
        if x['day'] != D: continue
        w = at(x['time']) if x['time'] else None; a = ar.get(x['area_id']) or {}
        out.append(dict(time=x['time'] or '', at=w, kind='task', tag=a.get('name') or 'Task', color=a.get('color') or '#6b7280', title=x['title'],
                        state='done' if x['done_at'] else ('late' if (w and w < t_now and d <= today()) or d < today() else 'upcoming'), ref=x['id'],
                        done_at=(x['done_at'] or '')[11:16], minutes=x['minutes']))
    for r in c.execute("SELECT * FROM habits ORDER BY sort, id"):
        h = _habit(c, r, d)
        if not due_on(h, d): continue
        lg = logs.get(h['id']) or {}; w = at(h['time']) if h['time'] else None
        if h['kind'] == 'quit':
            out.append(dict(time=h['time'] or '', at=w, kind='quit', tag='Quit', color='#c2410c', title=f"{h['name']} — risky time", state='info', ref=h['id']))
            continue
        tag = h['routine'] or 'Habit'
        out.append(dict(time=h['time'] or '', at=w, kind='habit', tag=tag, color=ROUTINE_COLORS.get(h['routine']) or (ar.get(h['area_id']) or {}).get('color') or '#2f6fde',
                        title=h['name'], state=state_for(w, lg.get('state') == 'done', lg.get('state') == 'skip'), ref=h['id'],
                        done_at=(lg.get('ts') or '')[11:16] if lg.get('state') == 'done' else ''))
    bg = setting(c, 'bed_goal') or '23:00'; wg = setting(c, 'wake_goal') or '07:00'
    nights = {night_of(r['bed']): r for r in sleeps(c, 40)}
    last = nights.get(d - timedelta(days=1))
    out.append(dict(time=wg, at=at(wg), kind='sleep', tag='Sleep', color='#6d5bd0', title='Wake up' + (f" — slept {hm(last['minutes'])}" if last else ''),
                    state='done' if last else ('upcoming' if d >= today() and (at(wg) or t_now) > t_now else 'info'), ref=last['id'] if last else None,
                    done_at=last['wake'][11:16] if last else ''))
    tonight = nights.get(d); bw = at(bg)
    if bw and int(bg[:2]) < 12: bw += timedelta(days=1)
    out.append(dict(time=bg, at=bw, kind='sleep', tag='Sleep', color='#6d5bd0', title='Bedtime' + (f" — in bed {tonight['bed'][11:16]}" if tonight else ''),
                    state='done' if tonight else ('upcoming' if bw and bw > t_now else 'late' if d == today() else 'missed'), ref=tonight['id'] if tonight else None))
    for s_ in sessions(c, d, d):
        st = datetime.fromisoformat(s_['start'])
        out.append(dict(time=st.strftime('%H:%M'), at=st, kind='focus', tag='Focus', color='#f2602d', title=f"{s_['title']} · {s_['minutes']} min", state='done', ref=s_['task_id']))
    for n in nudges(c):
        if n['kind'] == 'at' and n['enabled'] and d.weekday() in json.loads(n['days'] or '[]'):
            out.append(dict(time=n['start'], at=at(n['start']), kind='nudge', tag='Reminder', color='#0e8fa3', title=n['text'], state='info', ref=n['id']))
    out.sort(key=lambda x: (x['time'] == '', x['time'] or '99', x['kind'] != 'sleep'))
    return out


def last_touch(c, t):
    """when you last really worked on a task: a focus session, a matching window on screen, a change to it"""
    marks = [t.get('updated') or '', t.get('created') or '']
    r = c.execute('SELECT MAX(end) FROM focus_sessions WHERE task_id=?', (t['id'],)).fetchone()[0]
    if r: marks.append(r)
    r = c.execute('SELECT MAX(end) FROM activity WHERE task_id=?', (t['id'],)).fetchone()[0]
    if r: marks.append(r)
    return max(m for m in marks if m) if any(marks) else ''




def snooze_task(c, tid, days=3):
    c.execute('UPDATE tasks SET snooze_until=? WHERE id=?', (iso(today() + timedelta(days=days)), tid)); c.commit()


# auto sleep: last night from your PC (last activity → first activity) or from your usual times
def usual_night(c, night):
    """your every-night template for the night that starts on `night` → (bed, wake)"""
    bg = setting(c, 'sleep_usual_bed') or setting(c, 'bed_goal') or '23:30'; wk = setting(c, 'sleep_usual_wake') or setting(c, 'wake_goal') or '07:00'
    bed = datetime(night.year, night.month, night.day, int(bg[:2]), int(bg[3:5]))
    if bed.hour < 12: bed += timedelta(days=1)
    wake = datetime(night.year, night.month, night.day, int(wk[:2]), int(wk[3:5])) + timedelta(days=1)
    if wake <= bed: wake += timedelta(days=1)
    return bed, wake


def planned_nights(c, start, end, ahead=14):
    """nights from your template that are not written yet (tonight and the coming ones) — shown in the calendar
    so you can see and drag them; each becomes a real night the next morning (or when you move it)"""
    if setting(c, 'sleep_auto') != '1': return []
    t = today(); have = {night_of(r['bed']) for r in sleeps(c, 40)}; out = []
    d = max(start - timedelta(days=1), t - timedelta(days=1))
    while d <= min(end, t + timedelta(days=ahead)):
        if d not in have and setting(c, 'auto_slept:' + iso(d)) != '1':
            b, w = usual_night(c, d)
            if w > now(): out.append((d, b, w))                    # a night whose morning has passed is filled in for real instead
        d += timedelta(days=1)
    return out


def write_planned_night(c, night, bed, wake):
    """a planned night moved in the calendar becomes a real one → its id"""
    if isinstance(night, str): night = date.fromisoformat(night)
    rid = c.execute('INSERT INTO sleep(bed, wake, quality, note, latency, tags, auto, source) VALUES(?,?,?,?,?,?,?,?)',
                    (bed.isoformat(timespec='minutes'), wake.isoformat(timespec='minutes'), 3, '', 0, '[]', 0, 'calendar')).lastrowid
    set_setting(c, 'auto_slept:' + iso(night), '1'); c.commit(); return rid


def ensure_last_night(c, at=None):
    at = at or now()
    if setting(c, 'sleep_auto') != '1': return None
    night = at.date() - timedelta(days=1)
    wg = setting(c, 'wake_goal') or '07:00'
    if at.strftime('%H:%M') < wg: return None                                       # too early to know
    if any(night_of(r['bed']) == night for r in sleeps(c, 5)): return None
    if setting(c, 'auto_slept:' + iso(night)) == '1': return None                     # you deleted the auto night — don't add it again
    lo = datetime(night.year, night.month, night.day, 20, 0); hi = lo + timedelta(hours=15)
    acts = [(datetime.fromisoformat(r['start']), datetime.fromisoformat(r['end'])) for r in
            c.execute('SELECT start, end FROM activity WHERE end >= ? AND start <= ? ORDER BY start', (lo.isoformat(), hi.isoformat()))]
    bed = wake = None; src = 'usual times'
    if acts:
        gaps = [(acts[i][1], acts[i + 1][0]) for i in range(len(acts) - 1) if (acts[i + 1][0] - acts[i][1]).total_seconds() >= 3 * 3600]
        if gaps:
            bed, wake = max(gaps, key=lambda g: g[1] - g[0]); src = 'PC'
    if not bed: bed, wake = usual_night(c, night)
    c.execute('INSERT INTO sleep(bed, wake, quality, note, latency, tags, auto, source) VALUES(?,?,?,?,?,?,?,?)',
              (bed.isoformat(timespec='minutes'), wake.isoformat(timespec='minutes'), 3, '', 0, '[]', 1, src))
    set_setting(c, 'auto_slept:' + iso(night), '1'); c.commit(); return src


# activity: what was on screen (Windows) — merged into spans; private windows are stored without their title
DEFAULT_RULES = {'work': ['figma', 'photoshop', 'illustrator', 'indesign', 'after effects', 'premiere', 'afterfx', 'code', 'cursor', 'notion', 'canva', 'excel',
                          'word', 'powerpoint', 'shopify', 'meta business', 'ads manager', 'google ads', 'gmail', 'outlook', 'slack', 'chatgpt', 'claude',
                          'hermes', 'obsidian', 'curio', 'lightroom', 'blender', 'davinci'],
                 'learning': ['course', 'tutorial', 'lesson', 'udemy', 'coursera', 'skillshare', 'class'],
                 'private': ['bank', 'password', 'wallet', 'easypaisa', 'jazzcash', 'incognito', 'inprivate']}


def act_rules(c):
    try: r = json.loads(setting(c, 'act_rules') or 'null') or {}
    except Exception: r = {}
    out = {k: r.get(k, v) for k, v in DEFAULT_RULES.items()}
    try: out['distraction'] = json.loads(setting(c, 'coach_apps') or '[]')
    except Exception: out['distraction'] = []
    return out




def add_activity(c, start, end, app, title, cat, task_id=None):
    """one sample of what was on screen; joins it to the last span when it is the same window"""
    if cat == 'private': title = ''
    last = c.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 1').fetchone()
    if last and last['app'] == app and last['title'] == title[:200] and (start - datetime.fromisoformat(last['end'])).total_seconds() <= 45:
        c.execute('UPDATE activity SET end=? WHERE id=?', (end.isoformat(timespec='seconds'), last['id']))
    else:
        c.execute('INSERT INTO activity(start, end, app, title, cat, task_id) VALUES(?,?,?,?,?,?)',
                  (start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds'), app[:60], title[:200], cat, task_id))
    c.commit()


def activity_day(c, d=None):
    """where the time went on one day: minutes per category, per program, per task, the main windows, first and last activity"""
    d = d or today(); lo = datetime(d.year, d.month, d.day); hi = lo + timedelta(days=1)
    rows = [dict(r) for r in c.execute('SELECT * FROM activity WHERE end > ? AND start < ? ORDER BY start', (lo.isoformat(), hi.isoformat()))]
    cats, apps, tks, titles = {}, {}, {}, {}
    for r in rows:
        s_ = max(lo, datetime.fromisoformat(r['start'])); e_ = min(hi, datetime.fromisoformat(r['end'])); m = max(0.0, (e_ - s_).total_seconds() / 60)
        cats[r['cat']] = cats.get(r['cat'], 0) + m; apps[r['app'] or '?'] = apps.get(r['app'] or '?', 0) + m
        if r['task_id']: tks[r['task_id']] = tks.get(r['task_id'], 0) + m
        if r['title']: k = (r['app'], r['title'][:90]); titles[k] = titles.get(k, 0) + m
    rnd = lambda dct: {k: round(v) for k, v in sorted(dct.items(), key=lambda x: -x[1]) if v >= 1}
    return dict(total=round(sum(cats.values())), cats=rnd(cats), apps=dict(list(rnd(apps).items())[:12]), tasks=rnd(tks),
                windows=[dict(app=a, title=t, min=round(m)) for (a, t), m in sorted(titles.items(), key=lambda x: -x[1])[:15] if m >= 1],
                first=rows[0]['start'][11:16] if rows else '', last=rows[-1]['end'][11:16] if rows else '', spans=rows)


def activity_since(c, minutes=30):
    lo = (now() - timedelta(minutes=minutes)).isoformat(timespec='seconds')
    return [dict(r) for r in c.execute('SELECT * FROM activity WHERE end >= ? ORDER BY start', (lo,))]


# nudges: small repeating reminders that are not tasks (sit straight, water, "masti ya kaam?")
DEFAULT_NUDGES = [('Sit up straight — shoulders back, screen at eye level', 40, 'timer'), ('Drink a glass of water', 90, 'timer'),
                  ('Masti ho rahi hai ya kaam? Back to your main thing.', 20, 'drift'), ('Look away from the screen for 20 seconds (20-20-20)', 30, 'timer')]


def nudges(c):
    if setting(c, 'nudges_seeded') != '1':
        for text, every, kind in DEFAULT_NUDGES:
            c.execute('INSERT INTO nudges(text, every, kind, start, end) VALUES(?,?,?,?,?)', (text, every, kind, '10:00', '23:30'))
        set_setting(c, 'nudges_seeded', '1')
    return [dict(r) for r in c.execute('SELECT * FROM nudges ORDER BY kind, id')]


def save_nudge(c, n):
    v = (n['text'].strip()[:200], int(n.get('every') or 45), n.get('start') or '10:00', n.get('end') or '23:30', json.dumps(n.get('days') or list(range(7))),
         n.get('kind') or 'timer', 1 if n.get('active_only', 1) else 0, 1 if n.get('enabled', 1) else 0, (n.get('brief') or '').strip()[:2000])
    if n.get('id'): c.execute('UPDATE nudges SET text=?, every=?, start=?, end=?, days=?, kind=?, active_only=?, enabled=?, brief=? WHERE id=?', v + (n['id'],))
    else: c.execute('INSERT INTO nudges(text, every, start, end, days, kind, active_only, enabled, brief) VALUES(?,?,?,?,?,?,?,?,?)', v)
    c.commit()


def delete_nudge(c, nid): c.execute('DELETE FROM nudges WHERE id=?', (nid,)); c.commit()


def due_nudges(c, at=None, active=True):
    """timer nudges whose turn has come (inside their hours, on their days)"""
    at = at or now(); hm_ = at.strftime('%H:%M'); out = []
    for n in nudges(c):
        if not n['enabled'] or n['kind'] not in ('timer', 'at') or at.weekday() not in json.loads(n['days'] or '[]'): continue
        if n['active_only'] and not active: continue
        last = datetime.fromisoformat(n['last']) if n['last'] else None
        if n['kind'] == 'at':                                    # once a day, from its time until 3 hours later
            if n['start'] <= hm_ and (at - at.replace(hour=int(n['start'][:2]), minute=int(n['start'][3:5]))).total_seconds() < 3 * 3600 \
               and (last is None or last.date() != at.date()): out.append(n)
            continue
        if not (n['start'] <= hm_ < n['end']): continue
        if last is None or (at - last).total_seconds() >= n['every'] * 60: out.append(n)
    return out


def nudge_fired(c, nid, at=None): c.execute('UPDATE nudges SET last=? WHERE id=?', ((at or now()).isoformat(timespec='seconds'), nid)); c.commit()


# plan the day: give each open task of today a time (time blocking)
def plan_day(c, d=None, start=None, end=None):
    """fill free time with today's unscheduled tasks (high priority / in progress first). Returns [(task, 'HH:MM')]; nothing is saved."""
    d = d or today(); start = start or max(setting(c, 'work_start') or '10:00', now().strftime('%H:%M') if d == today() else '00:00')
    end = end or setting(c, 'plan_end') or '23:00'
    toM = lambda s: int(s[:2]) * 60 + int(s[3:5])
    busy = []
    for x in tasks(c, done=False):
        if x['day'] == iso(d) and x['time']: busy.append((toM(x['time']), toM(x['time']) + int(x['minutes'] or 30)))
    for h in habits(c, 'build'):
        if due_on(h, d) and h['time']: busy.append((toM(h['time']), toM(h['time']) + 10))
    busy.sort(); cur = ((toM(start) + 14) // 15) * 15; endM = toM(end); out = []
    todo = [x for x in tasks(c, done=False) if (x['day'] == iso(d) or (x['day'] and x['day'] < iso(d))) and not x['time']]
    todo.sort(key=lambda x: (-(x['priority'] or 0), task_status(x) != 'doing', x['day'] or ''))
    for x in todo:
        need = int(x['minutes'] or 30)
        while True:
            clash = next(((a, b) for a, b in busy if a < cur + need and b > cur), None)
            if not clash: break
            cur = ((clash[1] + 14) // 15) * 15
        if cur + need > endM: break
        out.append((x, f'{cur // 60:02d}:{cur % 60:02d}')); busy.append((cur, cur + need)); busy.sort(); cur += need + 10
        cur = ((cur + 14) // 15) * 15
    return out


def apply_plan(c, plan, d=None):
    for x, tm in plan: c.execute('UPDATE tasks SET day=?, time=?, updated=? WHERE id=?', (iso(d or today()), tm, stamp(), x['id']))
    c.commit()

# ───────────────────────── demo book ─────────────────────────
def seed_demo(c):
    """made-up examples so you can look around — only ever written to demo.db"""
    rnd = random.Random(7); t = today(); A = {a['name']: a['id'] for a in areas(c)}
    D = lambda k: iso(t + timedelta(days=k))
    for title, area, day, tm, rep, rem, pr in [
            ('Bring Ammi’s medicines', 'Responsibilities', D(0), '18:30', None, 15, 2),
            ('Grocery shopping', 'Responsibilities', D(1), '17:00', None, 30, 0),
            ('Pay internet bill', 'Responsibilities', D(-1), None, None, -1, 1),
            ('Organise hard drive (D:)', 'Self-Improve', D(0), '21:00', None, 0, 0),
            ('Sleep early tonight', 'Self-Improve', D(0), '23:00', {'every': 'day', 'n': 1}, 0, 1),
            ('Notebook organisation', 'Self-Improve', None, None, None, -1, 0),
            ('Figma class — auto layout', 'Skill Learn', D(0), '20:00', {'every': 'week', 'n': 1, 'days': [0, 2, 4]}, 10, 1),
            ('Meta Ads course — module 3', 'Skill Learn', D(2), '19:30', None, 10, 0),
            ('Blender 3D — donut tutorial', 'Skill Learn', D(4), None, None, -1, 0),
            ('Hair oiling', 'Health', D(0), '22:40', {'every': 'week', 'n': 1, 'days': [1, 4]}, 0, 0),
            ('Watch: video on hair care', 'Health', D(3), None, None, -1, 0),
            ('Jumu’ah — leave office early', 'Deen', iso(t + timedelta(days=(4 - t.weekday()) % 7)), '13:00', {'every': 'week', 'n': 1, 'days': [4]}, 30, 1)]:
        save_task(c, dict(title=title, area_id=A[area], day=day, time=tm, repeat=rep, remind=rem, priority=pr))
    done = save_task(c, dict(title='Check Lensequee inventory', area_id=A['Responsibilities'], day=D(0), time='11:00'))
    c.execute('UPDATE tasks SET done_at=? WHERE id=?', (datetime.combine(t, datetime.min.time()).replace(hour=11, minute=20).isoformat(), done))
    # habits with a history: some began later, one changed its plan, one was stopped
    H = []
    for name, area, routine, tm, rem, days, began in [
            ('Teeth brush', 'Health', 'Morning', '08:00', -1, None, 90), ('20 min breakfast, no phone', 'Health', 'Morning', '08:15', -1, None, 90),
            ('Check Gmail', 'Responsibilities', 'Morning', '09:00', 0, [0, 1, 2, 3, 4, 5], 20), ('Check LinkedIn', 'Responsibilities', 'Morning', '09:10', -1, [0, 1, 2, 3, 4, 5], 20),
            ('Fajr', 'Deen', 'Namaz', '05:20', 0, None, 90), ('Dhuhr', 'Deen', 'Namaz', '12:40', 0, None, 90), ('Asr', 'Deen', 'Namaz', '15:50', 0, None, 90),
            ('Maghrib', 'Deen', 'Namaz', '17:35', 0, None, 90), ('Isha', 'Deen', 'Namaz', '19:00', 0, None, 90),
            ('Night check-in', 'Self-Improve', 'Night', '23:00', 0, None, 90), ('Skincare', 'Health', 'Night', '23:10', -1, None, 45),
            ('Phone out of the bedroom', 'Self-Improve', 'Night', '23:30', 0, None, 30),
            ('Read 20 pages', 'Self-Improve', '', '22:30', 0, [0, 1, 2, 3, 4], 90), ('Drink 8 glasses of water', 'Health', '', None, -1, None, 90),
            ('Walk 20 minutes', 'Health', '', '18:00', 0, [0, 2, 4, 6], 60), ('Gym', 'Health', 'Night', '21:00', 0, [0, 2, 4], 90)]:
        H.append(save_habit(c, dict(name=name, area_id=A[area], routine=routine, time=tm, remind=rem, days=days or list(range(7)),
                                    start_day=iso(t - timedelta(days=began)))))
    read, gym = H[12], H[15]
    save_habit(c, dict(habit(c, read), time='21:30', days=list(range(7))), from_day=t - timedelta(days=30))   # plan changed a month ago
    c.execute('UPDATE habit_periods SET end=? WHERE habit_id=?', (iso(t - timedelta(days=35)), gym)); c.execute('UPDATE habits SET archived=1 WHERE id=?', (gym,))
    rates = [.95, .7, .85, .6, .55, .8, .7, .75, .9, .5, .6, .45, .65, .7, .55, .6]
    for i, hid in enumerate(H):                                # made-up history, only on days each habit really existed
        h = habit(c, hid)
        for k in range(1, 91):
            d = t - timedelta(days=k)
            if not due_on(h, d): continue
            if rnd.random() < rates[i] or (k < 4 and rates[i] > .8): c.execute('INSERT OR REPLACE INTO habit_log(habit_id, day, state, ts) VALUES(?,?,?,?)', (hid, iso(d), 'done', iso(d)))
            elif rnd.random() < .08: c.execute('INSERT OR REPLACE INTO habit_log(habit_id, day, state, ts) VALUES(?,?,?,?)', (hid, iso(d), 'skip', iso(d)))
        if i in (0, 1, 4, 5): c.execute('INSERT OR REPLACE INTO habit_log(habit_id, day, state, ts) VALUES(?,?,?,?)', (hid, iso(t), 'done', iso(t)))
    q = save_habit(c, dict(name='NoFap', area_id=A['Self-Improve'], kind='quit', time='00:15', remind=0, start_day=iso(t - timedelta(days=75)),
                           why='I want to be the man I respect — clear head, real energy, real relationships.\nEvery clean day is proof I can.\n'
                               'It never once made me feel better afterwards.'))
    for k, kind, trig, helped in [(64, 'relapse', 'Late night', ''), (41, 'relapse', 'Phone in bed', ''), (12, 'relapse', 'Bored', ''),
                                  (10, 'urge', 'Late night', 'Went for a walk'), (8, 'urge', 'Alone', 'Called a friend'),
                                  (5, 'urge', 'Phone in bed', 'Phone in the other room'), (2, 'urge', 'Late night', 'Wudu + 2 rakat'),
                                  (1, 'urge', 'Bored', 'Opened my Reset board')]:
        log_quit(c, q, kind, trig, helped, when=now() - timedelta(days=k, hours=rnd.randint(0, 5)))
    for k in range(1, 15):
        d = t - timedelta(days=k); bed = datetime(d.year, d.month, d.day, 23, 0) + timedelta(minutes=rnd.randint(-40, 150))
        add_sleep(c, bed, bed + timedelta(minutes=rnd.randint(300, 470)), rnd.randint(2, 5))
    for title, content, tags, pin, days_ago in [
            ('Today I finished the Curio web version', 'Felt proud. Remember this when things feel slow — one step at a time works.', ['Gratification'], 1, 0),
            ('Idea: course on brand colour systems', 'Short lessons, real client examples, Figma files as downloads.', ['Idea', 'Business'], 0, 3),
            ('Morning with family', 'Breakfast together on Sunday without phones. Do this more often.', ['Daily Life', 'Personal'], 0, 34),
            ('I am disciplined', 'Discipline is choosing what I want most over what I want now.', ['Affirmations', 'My Belief'], 1, 12),
            ('Client said the logo made them cry', 'Best feedback this year. This is why I design.', ['Gratification', 'Business'], 0, 61),
            ('Started running again', '3 km. Legs hurt, mind clear.', ['Daily Life'], 0, 92)]:
        nid = save_note(c, dict(title=title, content=content, tags=tags, pinned=pin))
        c.execute('UPDATE notes SET created=? WHERE id=?', ((now() - timedelta(days=days_ago)).isoformat(timespec='seconds'), nid))
    for text, who in [('Small steps every day beat big plans once a year.', ''), ('Discipline is remembering what you want.', ''),
                      ('Build the system, and the goals take care of themselves.', ''), ('Be the man every eye is on — not the one whose eyes are everywhere.', ''),
                      ('One day, or day one. You decide.', '')]:
        add_quote(c, text, who)
    c.commit()


# ───────────────────────── 10.26: calendar drag / resize, smarter pick-up, activity corrections, sleep list, quit streaks, check-in changes ─────────────────────────
def calendar_move(kind, rid, start, end, all_day=False):
    """an item dragged or resized in Curio Calendar. Returns what it was before (for Ctrl+Z)."""
    c = connect()
    try:
        if kind == 'task':
            t = task(c, rid)
            if not t: return None
            old = ('task', rid, t['day'], t['time'], t['minutes'])
            mins = int((end - start).total_seconds() // 60) if (end and not all_day) else int(t['minutes'] or 30)
            c.execute('UPDATE tasks SET day=?, time=?, minutes=?, updated=? WHERE id=?',
                      (iso(start.date()), None if all_day else start.strftime('%H:%M'), max(5, mins), stamp(), rid))
        elif kind == 'sleep':
            r = c.execute('SELECT bed, wake, auto, source FROM sleep WHERE id=?', (rid,)).fetchone()
            if not r: return None
            old = ('sleep', rid, r['bed'], r['wake'], r['auto'], r['source'])
            end = end or start + (datetime.fromisoformat(r['wake']) - datetime.fromisoformat(r['bed']))
            c.execute("UPDATE sleep SET bed=?, wake=?, auto=0, source='calendar' WHERE id=?", (start.isoformat(timespec='minutes'), end.isoformat(timespec='minutes'), rid))
        elif kind == 'sleepplan':
            end = end or start + timedelta(hours=8)
            new = write_planned_night(c, rid, start, end); old = ('sleepplan', new, str(rid))
        elif kind == 'focus':
            r = c.execute('SELECT start, end, minutes FROM focus_sessions WHERE id=?', (rid,)).fetchone()
            if not r: return None
            old = ('focus', rid, r['start'], r['end'], r['minutes'])
            end = end or start + (datetime.fromisoformat(r['end']) - datetime.fromisoformat(r['start']))
            c.execute('UPDATE focus_sessions SET start=?, end=?, minutes=? WHERE id=?',
                      (start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds'), max(1, int((end - start).total_seconds() // 60)), rid))
        else: return None
        c.commit(); return old
    finally: c.close()


def calendar_restore(old):
    c = connect()
    try:
        k, rid = old[0], old[1]
        if k == 'task': c.execute('UPDATE tasks SET day=?, time=?, minutes=? WHERE id=?', (old[2], old[3], old[4], rid))
        elif k == 'sleep': c.execute('UPDATE sleep SET bed=?, wake=?, auto=?, source=? WHERE id=?', (old[2], old[3], old[4], old[5], rid))
        elif k == 'focus': c.execute('UPDATE focus_sessions SET start=?, end=?, minutes=? WHERE id=?', (old[2], old[3], old[4], rid))
        elif k == 'sleepplan': c.execute('DELETE FROM sleep WHERE id=?', (rid,)); c.execute('DELETE FROM settings WHERE key=?', ('auto_slept:' + old[2],))
        c.commit()
    finally: c.close()


def _words(s): return {w for w in re.findall(r'[a-z0-9]{3,}', (s or '').lower())}


def _alike(a, b):
    A, B = _words(a), _words(b)
    return bool(A) and bool(B) and len(A & B) / min(len(A), len(B)) >= .6


def open_loops(c, min_days=1, limit=4):
    """things you started and then left — only real one-off work: not repeating tasks, not things already planned for today or later,
    not something that is also a daily check-in / habit, not something you keep finishing anyway"""
    t0 = today(); out = []
    regular = [h['name'] for h in habits(c)] + [s['title'] for s in series_list(c) if s['state'] in ('running', 'ending')]
    recent_done = [x['title'] for x in tasks(c, done=True) if (x['done_at'] or '')[:10] >= iso(t0 - timedelta(days=10))]
    for t in tasks(c, done=False):
        if t.get('snooze_until') and t['snooze_until'] > iso(t0): continue
        if t.get('repeat') or t.get('series'): continue
        if t['day'] and t['day'] >= iso(t0): continue
        if any(_alike(t['title'], r) for r in regular + recent_done): continue
        st = task_status(t); worked = tracked(c, t['id'])
        nxt = ''
        for line in reversed((t['note'] or '').splitlines()):
            if 'Next:' in line: nxt = line.split('Next:', 1)[1].strip(); break
        if st != 'doing' and not worked and not nxt: continue
        lt = last_touch(c, t)
        if not lt: continue
        days = (t0 - date.fromisoformat(lt[:10])).days
        if days < min_days: continue
        out.append(dict(task=t, days=days, last=lt[:10], next=nxt, worked=worked))
    out.sort(key=lambda x: (-(x['task']['priority'] or 0), x['days']))
    return out[:limit]


# activity: your own corrections win ("Canva is work", "that was dinner, not a distraction")
ACT_CATS = ['task', 'work', 'learning', 'break', 'distraction', 'other', 'private']


def act_overrides(c):
    try: return json.loads(setting(c, 'act_overrides') or '[]')
    except Exception: return []


def classify(c, app, title, open_tasks=None):
    """→ (category, task_id): your corrections first, then private / a window that matches an open task / a work program /
    distraction / learning / work words / other"""
    if not app and not title: return 'away', None
    hay = f' {app} {title} '.lower(); R = act_rules(c); app_l = f' {(app or "").lower()} '
    for o in act_overrides(c):
        if o.get('match') and o['match'].lower() in hay: return o.get('cat', 'work'), o.get('task_id')
    if any(w and w in hay for w in R['private']): return 'private', None
    for t in (open_tasks if open_tasks is not None else tasks(c, done=False)):
        words = [w for w in re.findall(r'[a-z0-9]{4,}', t['title'].lower()) if w not in ('task', 'with', 'from', 'that', 'this', 'class', 'module')]
        if words and sum(1 for w in words if w in hay) >= max(1, min(2, len(words) // 2)): return 'task', t['id']
    browser = any(b in app_l for b in ('chrome', 'msedge', 'edge', 'firefox', 'brave', 'opera', 'arc', 'vivaldi'))
    if not browser and any(w and w in app_l for w in R['work']): return 'work', None          # Canva showing an "Instagram post" is still work
    if any(w and w in hay for w in R['distraction']):
        if any(w and w in hay for w in R['learning']): return 'learning', None
        return 'distraction', None
    if any(w and w in hay for w in R['learning']): return 'learning', None
    if any(w and w in hay for w in R['work']): return 'work', None
    return 'other', None


def relabel_activity(c, aid, cat, scope='one', task_id=None):
    """correct what a stretch of screen time was. scope: 'one' = just this stretch; 'window' = this window today;
    'always' = this window from now on (and the last 30 days)"""
    r = c.execute('SELECT * FROM activity WHERE id=?', (aid,)).fetchone()
    if not r: return
    if scope == 'one': c.execute('UPDATE activity SET cat=?, task_id=? WHERE id=?', (cat, task_id, aid))
    else:
        lo = r['start'][:10] if scope == 'window' else iso(today() - timedelta(days=30))
        hi = r['start'][:10] if scope == 'window' else iso(today())
        if r['title']: c.execute('UPDATE activity SET cat=?, task_id=? WHERE app=? AND title=? AND substr(start,1,10) BETWEEN ? AND ?', (cat, task_id, r['app'], r['title'], lo, hi))
        else: c.execute('UPDATE activity SET cat=?, task_id=? WHERE app=? AND substr(start,1,10) BETWEEN ? AND ?', (cat, task_id, r['app'], lo, hi))
        if scope == 'always':
            m = (r['title'] or r['app'] or '').strip()[:80]
            if m:
                ov = [o for o in act_overrides(c) if o.get('match', '').lower() != m.lower()] + [dict(match=m, cat=cat, task_id=task_id)]
                set_setting(c, 'act_overrides', json.dumps(ov[-200:]))
    c.commit()


def delete_override(c, match):
    set_setting(c, 'act_overrides', json.dumps([o for o in act_overrides(c) if o.get('match') != match]))


def activity_rows(c, d):
    lo = datetime(d.year, d.month, d.day); hi = lo + timedelta(days=1)
    return [dict(r) for r in c.execute('SELECT * FROM activity WHERE end > ? AND start < ? ORDER BY start', (lo.isoformat(), hi.isoformat()))]


def delete_activity_day(c, d):
    c.execute('DELETE FROM activity WHERE substr(start,1,10)=?', (iso(d),)); c.commit()


APP_NAMES = {'chrome': 'Chrome', 'msedge': 'Edge', 'firefox': 'Firefox', 'code': 'VS Code', 'figma': 'Figma', 'canva': 'Canva', 'whatsapp': 'WhatsApp',
             'photoshop': 'Photoshop', 'illustrator': 'Illustrator', 'afterfx': 'After Effects', 'premiere': 'Premiere Pro', 'notion': 'Notion',
             'obsidian': 'Obsidian', 'explorer': 'File Explorer', 'curio': 'Curio', 'pythonw': 'Curio', 'python': 'Curio', 'excel': 'Excel',
             'winword': 'Word', 'powerpnt': 'PowerPoint', 'slack': 'Slack', 'telegram': 'Telegram', 'spotify': 'Spotify', 'vlc': 'VLC'}


def app_name(a): return APP_NAMES.get((a or '').lower(), (a or '?').replace('_', ' ').title())


# sleep: one simple list (week / month / last 30 days), coloured by how long you slept
def sleep_grade(c, minutes):
    goal = int(setting(c, 'sleep_goal') or 450)
    if minutes >= goal - 30: return 'Good', '#1f9d6b'
    if minutes >= goal - 90: return 'Poor', '#e8833a'
    return 'Bad', '#e5484d'


def sleep_nights(c, start, end):
    """{night date: sleep row} for nights between start and end (a night belongs to the evening it started)"""
    out = {}
    for r in sleeps(c, 400):
        n = night_of(r['bed'])
        if start <= n <= end and n not in out: out[n] = r
    return out


def ensure_recent_nights(c, at=None, back=7):
    """fill in up to a week of missing nights (from the PC or your usual times), never before you turned auto sleep on"""
    at = at or now()
    if setting(c, 'sleep_auto') != '1': return 0
    since = setting(c, 'sleep_auto_since')
    if not since: since = iso(today() - timedelta(days=1)); set_setting(c, 'sleep_auto_since', since)
    have = {night_of(r['bed']) for r in sleeps(c, 30)}; n = 0
    for k in range(back, 1, -1):
        night = today() - timedelta(days=k)
        if iso(night) < since or night in have or setting(c, 'auto_slept:' + iso(night)) == '1': continue
        if ensure_last_night(c, datetime.combine(night + timedelta(days=1), datetime.max.time().replace(microsecond=0))): n += 1
    if ensure_last_night(c, at): n += 1
    return n


# quit: struggling / urges / slips, with every streak kept
def quit_streaks(c, h):
    """every clean run, newest first: dict(start, end, days, current)"""
    start = datetime.fromisoformat((h.get('start_day') or iso(today())) + 'T00:00:00')
    rel = [datetime.fromisoformat(r[0]) for r in c.execute("SELECT ts FROM quit_events WHERE habit_id=? AND kind='relapse' ORDER BY ts", (h['id'],))]
    marks = [start] + rel; out = []
    for i, a in enumerate(marks):
        b = marks[i + 1] if i + 1 < len(marks) else now()
        out.append(dict(start=a, end=b, days=(b - a).days, current=i + 1 == len(marks)))
    return out[::-1]


def quit_month(c, h, year, month):
    lo = f'{year:04d}-{month:02d}-01'; hi = f'{year:04d}-{month:02d}-31T99'
    r = {k: 0 for k in ('urge', 'relapse')}
    for k, n in c.execute('SELECT kind, COUNT(*) FROM quit_events WHERE habit_id=? AND ts BETWEEN ? AND ? GROUP BY kind', (h['id'], lo, hi)): r[k] = n
    return r


# check-ins / habits: what you added, changed, stopped and restarted — and when
def habit_changes(c, kind='build', limit=60):
    out = []
    for r in c.execute('SELECT * FROM habits WHERE kind=?', (kind,)):
        h = _habit(c, r); ps = h['periods']
        for i, p in enumerate(ps):
            if i == 0: out.append(dict(day=p['start'], what='Added', name=h['name'], detail=plan_text(p), color='#1f9d6b', hid=h['id']))
            else:
                prev = ps[i - 1]
                gap = prev['end'] and (date.fromisoformat(p['start']) - date.fromisoformat(prev['end'])).days > 1
                out.append(dict(day=p['start'], what='Restarted' if gap else 'Changed', name=h['name'],
                                detail=(plan_text(prev) + '  →  ' + plan_text(p)) if not gap else plan_text(p), color='#2f6fde', hid=h['id']))
            if p['end'] and (i + 1 == len(ps) or (date.fromisoformat(ps[i + 1]['start']) - date.fromisoformat(p['end'])).days > 1):
                out.append(dict(day=iso(date.fromisoformat(p['end']) + timedelta(days=1)), what='Stopped', name=h['name'], detail=f"ran {_short(p['start'])} – {_short(p['end'])}",
                                color='#e5484d', hid=h['id']))
    out.sort(key=lambda x: x['day'], reverse=True)
    return out[:limit]


def demo_extras4(c):
    """10.26 demo: no Health board (its tasks go to Self-Improve), a few check-ins added / stopped / changed, a slip in the NoFap history"""
    if setting(c, 'demo_v') >= '4': return
    t = today(); A = {a['name']: a['id'] for a in areas(c, True)}
    if A.get('Health') and A.get('Self-Improve'):
        c.execute('UPDATE tasks SET area_id=? WHERE area_id=?', (A['Self-Improve'], A['Health']))
        c.execute('UPDATE habits SET area_id=? WHERE area_id=?', (A['Self-Improve'], A['Health']))
        c.execute('UPDATE areas SET archived=1 WHERE id=?', (A['Health'],))
    si = A.get('Self-Improve')
    g = save_habit(c, dict(name='Read one article (10 min)', area_id=si, routine='Day', time='10:30', remind=-1, start_day=iso(t - timedelta(days=9))))
    for k in range(1, 9):
        if k % 3: c.execute('INSERT OR IGNORE INTO habit_log(habit_id, day, state, ts) VALUES(?,?,?,?)', (g, iso(t - timedelta(days=k)), 'done', iso(t - timedelta(days=k)) + 'T10:40'))
    w = save_habit(c, dict(name='Morning walk', area_id=si, routine='Morning', time='06:45', remind=-1, start_day=iso(t - timedelta(days=60))))
    c.execute('UPDATE habit_periods SET end=? WHERE habit_id=?', (iso(t - timedelta(days=16)), w)); c.execute('UPDATE habits SET archived=1 WHERE id=?', (w,))
    for k in range(17, 58):
        if k % 4: c.execute('INSERT OR IGNORE INTO habit_log(habit_id, day, state, ts) VALUES(?,?,?,?)', (w, iso(t - timedelta(days=k)), 'done', iso(t - timedelta(days=k)) + 'T06:50'))
    set_setting(c, 'demo_v', '4'); c.commit()


def task_events(c, start, end, area=None):
    """dated tasks as calendar blocks (for Tasks › Calendar)"""
    ar = {a['id']: a for a in areas(c, True)}; out = []
    for t in tasks(c, area):
        if not t['day']: continue
        d = date.fromisoformat(t['day'])
        if not (start <= d <= end): continue
        a = ar.get(t['area_id']) or {}; col = a.get('color') or '#6b7280'
        if t['time']:
            h, m = map(int, t['time'].split(':')); s = datetime(d.year, d.month, d.day, h, m); e = s + timedelta(minutes=int(t['minutes'] or 30)); allday = False
        else: s, e, allday = datetime(d.year, d.month, d.day), None, True
        out.append(dict(id=f"myday:{t['id']}", source='myday', record_id=t['id'], date=d, start=s, end=e, all_day=allday, mkind='task', mid=t['id'],
                        title=('✓ ' if t['done_at'] else '') + t['title'], color=col + '33', ink=col, readonly=False, calendar=a.get('name') or 'Tasks',
                        detail=repeat_text(t['repeat'])))
    return out
