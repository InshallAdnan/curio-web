"""Tracker for Curio Web — the desktop app's own My Day / Tracker rules (server/myday.py, a copy of the desktop file),
on your web database, so the same tasks, check-ins, habits, sleep, NoFap, nudges and goals work from the phone.

POST /api/tracker {"op": "...", "args": {...}} → {"ok": true, "data": ...} or {"error": "..."}
Tables live next to Finance and Pages with a "md_" in front of their names (Finance already has `settings` and `goals`);
the desktop code is unchanged — every SQL it runs gets the prefix on the way in."""
import base64, json, os, re, sqlite3, sys, tempfile, types
from datetime import date, datetime, timedelta
from pathlib import Path

if 'core' not in sys.modules:                                     # myday.py asks for the desktop's data folder; on the web it is not used
    _core = types.ModuleType('core'); _core.ROOT = Path(tempfile.gettempdir()) / 'curio-tracker'; sys.modules['core'] = _core
import myday as M  # noqa: E402
from tdb import Snapshot  # noqa: E402

NAMES = ['settings', 'areas', 'tasks', 'habits', 'habit_periods', 'habit_log', 'quit_events', 'sleep', 'notes', 'quotes', 'sent', 'snoozes',
         'focus_sessions', 'mood', 'focus_events', 'parked', 'inspo', 'activity', 'nudges', 'goals']
PFX = 'md_'
TABLES = [PFX + n for n in NAMES]
BOOK = Snapshot('tracker', TABLES)
_RX = re.compile(r'(\b(?:FROM|JOIN|INTO|UPDATE|TABLE|EXISTS|ON)\s+|table_info\()(%s)\b' % '|'.join(sorted(NAMES, key=len, reverse=True)), re.I)


def sql(s): return _RX.sub(lambda m: m.group(1) + PFX + m.group(2), s)


class Con:
    """the desktop code thinks it talks to its own myday.db; every statement gets md_ table names"""
    def __init__(self, con): self._c = con

    def execute(self, s, a=()): return self._c.execute(sql(s), a)
    def executemany(self, s, a): return self._c.executemany(sql(s), a)
    def executescript(self, s):
        for st in [x.strip() for x in s.split(';') if x.strip()]: self._c.execute(sql(st))
    def commit(self): self._c.commit()
    def close(self): pass
    def __getattr__(self, k): return getattr(self._c, k)


def _prepare(c):
    """the same start as the desktop's myday.connect: tables, new columns, plan periods, first boards"""
    c.executescript(M.SCHEMA)
    M._add_columns(c)
    if c.execute('SELECT 1 FROM habits WHERE id NOT IN (SELECT habit_id FROM habit_periods) LIMIT 1').fetchone():
        c.execute("INSERT INTO habit_periods(habit_id, start, end, days, time, remind, routine) "
                  "SELECT id, COALESCE(start_day, substr(created, 1, 10), date('now','localtime')), CASE WHEN archived=1 THEN COALESCE(start_day, substr(created, 1, 10)) END, "
                  "days, time, remind, COALESCE(routine, '') FROM habits WHERE id NOT IN (SELECT habit_id FROM habit_periods)")
    if not c.execute('SELECT 1 FROM areas LIMIT 1').fetchone(): M._first_areas(c)
    c.commit()


def run(fn):
    def go(con):
        c = Con(con); _prepare(c); return fn(c)
    return BOOK.run(go)


# ───────────────────────── helpers ─────────────────────────
def _j(v):
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, dict): return {k: _j(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [_j(x) for x in v]
    if isinstance(v, sqlite3.Row): return _j(dict(v))
    return v


def _d(s): return date.fromisoformat(str(s)[:10]) if s else M.today()


def _sleep_row(c, r):
    if not r: return None
    g, col = M.sleep_grade(c, r['minutes']); return dict(id=r['id'], bed=r['bed'], wake=r['wake'], minutes=r['minutes'], grade=g, color=col, auto=r.get('auto'),
                                                         night=M.iso(M.night_of(r['bed'])))


def _quit(c, h):
    st = M.quit_stats(c, h)
    return dict(id=h['id'], name=h['name'], why=h['why'], days=st['days'], hours=st['hours'], since=st['since'], best=st['best'], beaten=st['beaten'],
                relapses=st['relapses'], triggers=st['triggers'][:6], events=st['events'][:20],
                streaks=[dict(days=x['days'], start=x['start'], end=x['end'], current=x['current']) for x in M.quit_streaks(c, h)[:12]],
                plan=json.loads(M.setting(c, 'plan') or '[]'))


# ───────────────────────── calls ─────────────────────────
def home(c, a):
    try: M.ensure_recent_nights(c)                                  # a night of sleep from your usual times, when the desktop did not fill it
    except Exception: pass
    t = M.today(); s = M.today_summary(c); ar = {x['id']: x for x in M.areas(c, True)}
    tl = M.timeline(c, t)
    sl = M.sleeps(c, 1); q = M.habits(c, 'quit')
    mon = t - timedelta(days=t.weekday()); days = [mon + timedelta(days=i) for i in range(7)]
    week = {M.iso(d): [] for d in days}
    for x in M.tasks(c):
        if x['day'] in week: week[x['day']].append(dict(id=x['id'], title=x['title'], time=x['time'], done=bool(x['done_at']), color=(ar.get(x['area_id']) or {}).get('color')))
    empty = not c.execute('SELECT 1 FROM tasks LIMIT 1').fetchone() and not c.execute('SELECT 1 FROM habits LIMIT 1').fetchone()
    return dict(empty=empty, total=s['total'], done=s['done'], timeline=[x for x in tl if x['kind'] != 'quit'], routines=M.routines_today(c), top3=[dict(id=x['id'], title=x['title'], done=bool(x['done_at'])) for x in M.top3(c)],
                sleep=_sleep_row(c, sl[0]) if sl else None, quit=[dict(id=h['id'], name=h['name'], days=M.quit_stats(c, h)['days'], best=M.quit_stats(c, h)['best']) for h in q],
                week=week, colors=M.ROUTINE_COLORS, areas=[dict(id=x['id'], name=x['name'], color=x['color']) for x in M.areas(c)])


def tasks(c, a):
    b = M.task_buckets(c, a.get('area')); ar = {x['id']: x for x in M.areas(c, True)}

    def row(x):
        return dict(id=x['id'], title=x['title'], area_id=x['area_id'], area=(ar.get(x['area_id']) or {}).get('name'), color=(ar.get(x['area_id']) or {}).get('color'),
                    day=x['day'], time=x['time'], minutes=x['minutes'], repeat=M.repeat_text(x['repeat']) if x['repeat'] else '', note=x['note'], remind=x['remind'],
                    done=bool(x['done_at']), done_at=x['done_at'])
    return dict(overdue=[row(x) for x in b['overdue']], today=[row(x) for x in b['today']], upcoming=[row(x) for x in b['upcoming']], someday=[row(x) for x in b['someday']],
                done=[row(x) for x in b['done'][:20]], areas=[dict(id=x['id'], name=x['name'], color=x['color']) for x in M.areas(c)],
                repeating=[dict(id=x['id'], title=x['title'], rule=x['rule'], state=x['state'], next=x['next'], done=x['done'], open_id=x['open_id']) for x in M.series_list(c)])


def task_save(c, a):
    t = a['task']; old = M.task(c, int(t['id'])) if t.get('id') else {}
    v = dict(old or {}); v.update({k: t.get(k) for k in ('title', 'area_id', 'day', 'time', 'minutes', 'note', 'remind') if k in t})
    if 'repeat' in t: v['repeat'] = t['repeat']
    if 'repeat_end' in t: v['repeat_end'] = t['repeat_end']
    v.setdefault('status', 'todo'); v['minutes'] = int(v.get('minutes') or 30); v['remind'] = int(v.get('remind') if v.get('remind') is not None else -1)
    if not (v.get('title') or '').strip(): raise ValueError('Write the task first.')
    return M.save_task(c, v)


def calendar_events(c, a):
    s, e = _d(a['start']), _d(a['end']); out = M.task_events(c, s, e)
    try: M.ensure_recent_nights(c)                                  # last night from your every-night times, even if Tracker was not opened
    except Exception: pass
    for night, b, w in M.planned_nights(c, s, e):
        out.append(dict(id=f"myday:plan:{M.iso(night)}", source='myday', date=b.date(), start=b, end=w, all_day=False, mkind='sleepplan', mid=M.iso(night),
                        title=f"Sleep · plan {M.hm(int((w - b).total_seconds() // 60))}", color='#6d5bd01a', ink='#6d5bd0', calendar='Tracker · Sleep', planned=True))
    for r in M.sleeps(c, 400):
        b, w = datetime.fromisoformat(r['bed']), datetime.fromisoformat(r['wake'])
        if s <= b.date() <= e or s <= w.date() <= e:
            out.append(dict(id=f"myday:sleep:{r['id']}", source='myday', date=b.date(), start=b, end=w, all_day=False, mkind='sleep', mid=r['id'],
                            title=f"Sleep · {M.hm(r['minutes'])}", color='#6d5bd033', ink='#6d5bd0', calendar='Tracker · Sleep'))
    for x in M.sessions(c, s, e):
        st, en = datetime.fromisoformat(x['start']), datetime.fromisoformat(x['end'])
        out.append(dict(id=f"myday:focus:{x['id']}", source='myday', date=st.date(), start=st, end=en, all_day=False, mkind='focus', mid=x['id'],
                        title=f"Focus · {x['title']}", color='#f2602d33', ink='#f2602d', calendar='Tracker · Focus'))
    return out


def calendar_move(c, a):
    """a Tracker block dragged / stretched in the calendar"""
    k = a['kind']; st = datetime.fromisoformat(a['start'][:16]); en = datetime.fromisoformat(a['end'][:16]) if a.get('end') else None
    allday = bool(a.get('all_day'))
    if k == 'sleepplan':                                            # a planned night moved → it becomes a real night
        M.write_planned_night(c, str(a['id']), st, en or st + timedelta(hours=8)); return True
    rid = int(a['id'])
    if k == 'task':
        t = M.task(c, rid); mins = int((en - st).total_seconds() // 60) if (en and not allday) else int(t['minutes'] or 30)
        c.execute('UPDATE tasks SET day=?, time=?, minutes=?, updated=? WHERE id=?', (M.iso(st.date()), None if allday else st.strftime('%H:%M'), max(5, mins), M.stamp(), rid))
    elif k == 'sleep':
        r = c.execute('SELECT bed, wake FROM sleep WHERE id=?', (rid,)).fetchone(); en = en or st + (datetime.fromisoformat(r['wake']) - datetime.fromisoformat(r['bed']))
        c.execute("UPDATE sleep SET bed=?, wake=?, auto=0, source='calendar' WHERE id=?", (st.isoformat(timespec='minutes'), en.isoformat(timespec='minutes'), rid))
    elif k == 'focus':
        r = c.execute('SELECT start, end FROM focus_sessions WHERE id=?', (rid,)).fetchone(); en = en or st + (datetime.fromisoformat(r['end']) - datetime.fromisoformat(r['start']))
        c.execute('UPDATE focus_sessions SET start=?, end=?, minutes=? WHERE id=?', (st.isoformat(timespec='seconds'), en.isoformat(timespec='seconds'), max(1, int((en - st).total_seconds() // 60)), rid))
    c.commit(); return True


def checkins(c, a):
    t = M.today(); e = t; s = e - timedelta(days=6)
    allh = [h for h in M.habits(c, 'build')]
    rows = M.grid(c, allh, s, e) if allh else []
    by = {r['habit']['id']: r for r in rows}; logs = {r['habit_id']: r['state'] for r in c.execute('SELECT habit_id, state FROM habit_log WHERE day=?', (M.iso(t),))}
    out = {}
    for h in allh:
        st = M.stats(c, h, 30)
        out.setdefault(h['routine'] or '', []).append(dict(id=h['id'], name=h['name'], time=h['time'], etime=h.get('etime'), due=M.due_on(h, t), state=logs.get(h['id']),
                                                          history=M.period_lines(h) if len(h['periods']) > 1 else [],
                                                          week=[[M.iso(d), x] for d, x in by[h['id']]['cells']], streak=st['streak'], pct=st['pct'],
                                                          routine=h['routine'], area_id=h['area_id'], days=h['days'], remind=h['remind']))
    return dict(groups=out, order=M.ROUTINES, colors=M.ROUTINE_COLORS, changes=M.habit_changes(c)[:12],
                stopped=[dict(id=h['id'], name=h['name'], routine=h['routine'], last=(h['periods'][-1]['end'] if h['periods'] else None)) for h in M.habits(c, 'build', archived=True)])


def habit_save(c, a):
    h = a['habit']; base = M.habit(c, int(h['id'])) if h.get('id') else {}
    v = dict(base or {}); v.update(h); v.setdefault('kind', 'build'); v['remind'] = int(v.get('remind') if v.get('remind') is not None else -1)
    if not (v.get('name') or '').strip(): raise ValueError('Give it a name.')
    return M.save_habit(c, v, _d(a['from_day']) if a.get('from_day') else None)


def sleep_view(c, a):
    try: M.ensure_recent_nights(c)
    except Exception: pass
    mode = a.get('mode', 'week'); off = int(a.get('off') or 0); t0 = M.today()
    if mode == 'month':
        import calendar as _c
        m0 = t0.month - 1 + off; y = t0.year + m0 // 12; mm = m0 % 12 + 1; s = date(y, mm, 1); e = date(y, mm, _c.monthrange(y, mm)[1])
    elif mode == '30': e = t0 - timedelta(days=1) + timedelta(days=30 * off); s = e - timedelta(days=29)
    else: e = t0 - timedelta(days=1) + timedelta(weeks=off); s = e - timedelta(days=6)
    n = M.sleep_nights(c, s, e)
    return dict(start=s, end=e, nights={M.iso(k): _sleep_row(c, v) for k, v in n.items()}, goal=int(M.setting(c, 'sleep_goal') or 450),
                bed=M.setting(c, 'sleep_usual_bed') or M.setting(c, 'bed_goal') or '23:00', wake=M.setting(c, 'sleep_usual_wake') or M.setting(c, 'wake_goal') or '07:00',
                auto=M.setting(c, 'sleep_auto') == '1')


def sleep_save(c, a):
    night = _d(a['night']); bh, bm = map(int, a['bed'].split(':')); wh, wm = map(int, a['wake'].split(':'))
    bed = datetime(night.year, night.month, night.day, bh, bm)
    if bh < 12: bed += timedelta(days=1)
    wake = datetime(bed.year, bed.month, bed.day, wh, wm)
    if wake <= bed: wake += timedelta(days=1)
    sid = int(a['id']) if a.get('id') else None
    M.add_sleep(c, bed, wake, 3, '', 0, [], sid)
    if sid: c.execute("UPDATE sleep SET auto=0, source='' WHERE id=?", (sid,)); c.commit()
    return True


OPS = {
    'home': home, 'tasks': tasks, 'task_save': task_save, 'checkins': checkins, 'habit_save': habit_save, 'sleep': sleep_view, 'sleep_save': sleep_save,
    'calendar': calendar_events, 'calendar_move': calendar_move,
    'timeline': lambda c, a: M.timeline(c, _d(a.get('day'))),
    'task_done': lambda c, a: M.complete(c, int(a['id']), bool(a.get('on', True))),
    'task_delete': lambda c, a: M.delete_task(c, int(a['id'])),
    'task': lambda c, a: M.task(c, int(a['id'])),
    'stop_series': lambda c, a: M.stop_series(c, int(a['id'])),
    'restart_series': lambda c, a: M.restart_series(c, int(a['id'])),
    'habit_log': lambda c, a: M.set_log(c, int(a['id']), _d(a.get('day')), a.get('state')),
    'habit': lambda c, a: M.habit(c, int(a['id'])),
    'habit_end': lambda c, a: M.end_habit(c, int(a['id'])),
    'habit_restart': lambda c, a: M.restart_habit(c, int(a['id'])),
    'sleep_delete': lambda c, a: M.delete_sleep(c, int(a['id'])),
    'sleep_usual': lambda c, a: [M.set_setting(c, k, str(a[v])) for k, v in (('sleep_usual_bed', 'bed'), ('bed_goal', 'bed'), ('sleep_usual_wake', 'wake'), ('wake_goal', 'wake'),
                                                                            ('sleep_goal', 'goal')) if a.get(v) is not None],
    'quit': lambda c, a: [_quit(c, h) for h in M.habits(c, 'quit')],
    'quit_save': lambda c, a: M.save_habit(c, dict(M.habit(c, int(a['id'])) if a.get('id') else {}, kind='quit', name=a['name'], why=a.get('why', ''), routine='',
                                                   days=list(range(7)), time=a.get('time') or '00:15', remind=0, start_day=a.get('start_day') or M.iso(M.today()))),
    'quit_log': lambda c, a: M.log_quit(c, int(a['id']), a['kind'], a.get('trigger', ''), a.get('helped', ''), a.get('note', ''),
                                        datetime.fromisoformat(a['when'][:16]) if a.get('when') else None),
    'nudges': lambda c, a: M.nudges(c),
    'nudge_save': lambda c, a: M.save_nudge(c, a['nudge']),
    'nudge_delete': lambda c, a: M.delete_nudge(c, int(a['id'])),
    'inspo': lambda c, a: dict(goals=M.goals(c, 'goal'), dreams=M.goals(c, 'dream'), notes=[x for x in M.inspo_items(c) if x['kind'] == 'quote'], sections=M.inspo_sections(c)),
    'goal_save': lambda c, a: M.save_goal(c, a['goal']),
    'goal_done': lambda c, a: M.goal_done(c, int(a['id']), bool(a.get('on', True))),
    'note_save': lambda c, a: (M.update_inspo(c, int(a['id']), title=a.get('title', ''), text=a.get('text', ''), color=a.get('color', '')) if a.get('id')
                               else M.add_inspo(c, 'quote', a.get('section') or 'My Inspo', a.get('title', ''), a.get('text', ''))),
    'top3': lambda c, a: M.set_top3(c, [int(x) for x in a.get('ids') or []]),
    'stats': lambda c, a: dict(tasks=c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], habits=c.execute('SELECT COUNT(*) FROM habits').fetchone()[0],
                               sleep=c.execute('SELECT COUNT(*) FROM sleep').fetchone()[0]),
}


def call(op, args):
    fn = OPS.get(op)
    if not fn: raise ValueError(f'Unknown: {op}')
    return _j(run(lambda c: fn(c, args or {})))


# ───────────────────────── one-time copy of the desktop's myday.db ─────────────────────────
def import_db(b64, replace=False):
    raw = base64.b64decode(b64)
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f: f.write(raw); p = f.name
    try:
        src = sqlite3.connect(p); src.row_factory = sqlite3.Row
        have = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'tasks' not in have or 'habits' not in have: raise ValueError('This is not a Tracker (myday.db) file.')
        data = {}
        for n in NAMES:
            if n in have and n != 'activity': data[n] = [dict(r) for r in src.execute(f'SELECT * FROM "{n}"')]
        src.close()
    finally:
        try: os.remove(p)
        except OSError: pass

    def go(c):
        if not replace and c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] + c.execute('SELECT COUNT(*) FROM habits').fetchone()[0]:
            raise ValueError('Tracker on the web already has data. Tick “Replace what is on the web” to copy the desktop data over it.')
        counts = {}
        for n, rows in data.items():
            c.execute(f'DELETE FROM {n}')
            cols = {r[1] for r in c.execute(f'PRAGMA table_info({n})')}
            for r in rows:
                k = [x for x in r if x in cols]
                if k: c.execute(f'INSERT INTO {n}({",".join(k)}) VALUES({",".join("?" * len(k))})', [r[x] for x in k])
            counts[n] = len(rows)
        c.commit(); return counts
    return run(go)


# ───────────────────────── reminders to the phone (the cron service calls tick every minute) ─────────────────────────
def tick():
    import push
    at = M.now(); items = []

    def go(c):
        try: M.ensure_recent_nights(c, at)                          # every night is written from your usual times, the morning after
        except Exception: pass
        for key, title, body, kind, ref in M.due_reminders(c, at, 15):
            M.mark_sent(c, key); items.append((title, body, kind, '/#/tracker'))
        for n in M.due_nudges(c, at, active=False):
            if n['kind'] != 'drift' and not n['active_only']:       # the phone gets only "phone too" nudges; screen ones stay on the PC
                M.nudge_fired(c, n['id'], at); items.append((n['text'], '', 'nudge', '/#/tracker'))
        return len(items)
    run(go)
    return dict(due=len(items), sent=push.notify(items) if items else 0, at=at.isoformat(timespec='seconds'))
