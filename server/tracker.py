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
         'focus_sessions', 'mood', 'focus_events', 'parked', 'inspo', 'activity', 'nudges', 'goals', 'ai_chat']
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
    return dict(id=h['id'], name=h['name'], why=h['why'], time=h['time'], etime=h.get('etime'), start_day=h['start_day'], days=st['days'], hours=st['hours'], since=st['since'], best=st['best'], beaten=st['beaten'],
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
    return dict(empty=empty, total=s['total'], done=s['done'], timeline=[x for x in tl if x['kind'] not in ('quit', 'focus')], routines=_routines(c), top3=[dict(id=x['id'], title=x['title'], done=bool(x['done_at'])) for x in M.top3(c)],
                sleep=_sleep_row(c, sl[0]) if sl else None, quit=[dict(id=h['id'], name=h['name'], days=M.quit_stats(c, h)['days'], best=M.quit_stats(c, h)['best']) for h in q],
                colors=M.ROUTINE_COLORS, areas=[dict(id=x['id'], name=x['name'], color=x['color']) for x in M.areas(c)])


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
    v = dict(old or {}); v.update({k: t.get(k) for k in ('title', 'area_id', 'day', 'time', 'minutes', 'note', 'remind', 'why') if k in t})
    if 'repeat' in t: v['repeat'] = t['repeat']
    if 'repeat_end' in t: v['repeat_end'] = t['repeat_end']
    v.setdefault('status', 'todo'); v['minutes'] = int(v.get('minutes') or 30); v['remind'] = int(v.get('remind') if v.get('remind') is not None else -1)
    if not (v.get('title') or '').strip(): raise ValueError('Write the task first.')
    return M.save_task(c, v)


def calendar_events(c, a):
    """the same Tracker blocks as the desktop Calendar: dated tasks, check-ins / habits that have a time, nights of sleep (planned ones dashed).
    Focus is switched off for now."""
    s, e = _d(a['start']), _d(a['end'])
    out = [x for x in M.calendar_events(s, e, c) if x.get('mgroup') != 'focus']
    for x in out:
        if x.get('mkind') == 'sleepplan': x['planned'] = True
        if x.get('mkind') == 'habit': x['readonly'] = True
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
    t = _d(a.get('day')) if a.get('day') else M.today(); t = min(t, M.today()); e = t; s = e - timedelta(days=6)
    allh = [h for h in M.habits(c, 'build')]
    rows = M.grid(c, allh, s, e) if allh else []
    by = {r['habit']['id']: r for r in rows}; logs = {r['habit_id']: r['state'] for r in c.execute('SELECT habit_id, state FROM habit_log WHERE day=?', (M.iso(t),))}
    out = {}
    allh = [h for h in allh if any(p['start'] <= M.iso(t) and (not p['end'] or p['end'] >= M.iso(t)) for p in h['periods'])] if a.get('day') else allh
    for h in allh:
        st = M.stats(c, h, 30)
        out.setdefault(h['routine'] or '', []).append(dict(id=h['id'], name=h['name'], time=h['time'], etime=h.get('etime'), due=M.due_on(h, t), state=logs.get(h['id']),
                                                          late=bool(M.due_on(h, t) and not logs.get(h['id']) and M.time_passed(h, t)),
                                                          history=M.period_lines(h) if len(h['periods']) > 1 else [],
                                                          week=[[M.iso(d), x] for d, x in by[h['id']]['cells']], streak=st['streak'], pct=st['pct'],
                                                          routine=h['routine'], area_id=h['area_id'], days=h['days'], remind=h['remind'], why=h.get('why') or ''))
    return dict(day=t, groups=out, order=M.ROUTINES, colors=M.ROUTINE_COLORS, changes=M.habit_changes(c)[:12],
                stopped=[dict(id=h['id'], name=h['name'], routine=h['routine'], last=(h['periods'][-1]['end'] if h['periods'] else None)) for h in M.habits(c, 'build', archived=True)])


def _routines(c):
    """Home's check-in tiles; late = its time is over and it is not ticked yet (shows red until you tick it)"""
    r = M.routines_today(c)
    for items in r.values():
        for x in items: x['late'] = bool(not x.get('done') and M.time_passed(x))
    return r


# ───────────────────────── boards ─────────────────────────
def areas_view(c, a):
    return [dict(id=x['id'], name=x['name'], color=x['color'], **M.area_use(c, x['id'])) for x in M.areas(c)]


def area_save(c, a):
    name = (a.get('name') or '').strip()[:40]
    if not name: raise ValueError('Give the board a name.')
    if a.get('id'): M.update_area(c, int(a['id']), name=name, **({'color': a['color']} if a.get('color') else {})); return int(a['id'])
    return M.add_area(c, name, a.get('color'))


def area_delete(c, a):
    """a board goes; its tasks / check-ins move to the board you picked (nothing of yours is deleted)"""
    M.delete_area(c, int(a['id']), int(a['move_to']) if a.get('move_to') else None); return True


def task_delete(c, a):
    """a repeating task: only this day's copy goes, the repeat goes on"""
    tid = int(a['id']); t = M.task(c, tid)
    if t and t['repeat'] and not t['done_at']: M.ensure_next(c, tid)
    M.delete_task(c, tid); return True


def task_info(c, a):
    t = M.task(c, int(a['id']))
    if not t: return None
    ar = {x['id']: x for x in M.areas(c, True)}; b = ar.get(t['area_id']) or {}
    return dict(id=t['id'], title=t['title'], area_id=t['area_id'], area=b.get('name'), color=b.get('color'), day=t['day'], time=t['time'], minutes=t['minutes'],
                repeat=M.repeat_text(t['repeat']) if t['repeat'] else '', note=t['note'], link=t['link'], done=bool(t['done_at']), done_at=t['done_at'],
                status=t.get('status') or 'todo', areas=[dict(id=x['id'], name=x['name'], color=x['color']) for x in M.areas(c)])


# ───────────────────────── Ask AI about a day (the chat is saved, and the AI reads the earlier chats) ─────────────────────────
AI_SYSTEM = ('You are the user’s kind, honest productivity coach inside their Curio Tracker. Answer in simple Roman Urdu mixed with English, short (max 8 lines), '
             'specific to the data. Breaks and meals are fine. Never moralise. You remember the earlier chat messages given to you: use what the user told you there '
             '(their reasons, preferences, what counts as work for them) and do not ask again. Compare with the last days when it helps. '
             'This is the web: screen time is only recorded on the user’s PC, so a day without screen data is NOT a day of no work — never compare minutes against such days. '
             'Check-ins whose time passed without a tick: mention them kindly with one practical step.')


def ai_day(c, a):
    d = _d(a.get('day'))
    return dict(day=M.iso(d), chat=M.chat_day(c, d), saved=M.chat_count(c))


def ai_ask(c, a):
    import ai
    d = _d(a.get('day')); q = (a.get('question') or '').strip() or 'How did my day go and what one thing should I change tomorrow?'
    plan = '\n'.join(f"{x['time'] or 'any time'} {x['title']} ({'done' if x['done_at'] else 'open'})" for x in M.tasks(c) if x['day'] == M.iso(d))
    goals = ', '.join(g['title'] for g in M.goals(c) if not g['done_at'])
    hs = [h for h in M.habits(c, 'build', on=d) if M.due_on(h, d)]
    logs = {r['habit_id']: r['state'] for r in c.execute('SELECT habit_id, state FROM habit_log WHERE day=?', (M.iso(d),))}
    ck = '\n'.join(f"{(h['time'] or '')[:5]} {h['name']}: {logs.get(h['id']) or ('time passed, not ticked' if M.time_passed(h, d) else 'not yet')}" for h in hs)
    days = '\n'.join(M.day_digest(c, d - timedelta(days=k)) for k in range(7, 0, -1))
    brief = M.setting(c, 'coach_brief') or ''
    ctx = (f"Day asked about: {d:%A %d %B %Y}\nPlan for the day:\n{plan or '-'}\nCheck-ins / habits:\n{ck or '-'}\nGoals: {goals or '-'}\n"
           f"How I want my coach to talk to me: {brief or '-'}\n\nThe 7 days before (to compare):\n{days}")
    hist = []
    for m in M.chat_recent(c, 24):
        role = 'assistant' if m['role'] == 'assistant' else 'user'; txt = (f"[{m['day']}] " if role == 'user' else '') + m['text']
        if hist and hist[-1]['role'] == role: hist[-1]['content'] += '\n' + txt
        else: hist.append({'role': role, 'content': txt})
    while hist and hist[0]['role'] != 'user': hist.pop(0)
    if hist and hist[-1]['role'] == 'user': hist.append({'role': 'assistant', 'content': '(no answer)'})
    M.chat_add(c, d, 'user', q)
    try: txt = ai.respond(hist + [{'role': 'user', 'content': f'{ctx}\n\nQuestion: {q}'}], AI_SYSTEM)
    except Exception as e: raise ValueError(f'The AI did not answer: {e}. Connect ChatGPT in Ask AI › Settings.')
    txt = (txt or '').strip() or 'The AI did not answer.'
    M.chat_add(c, d, 'assistant', txt)
    return ai_day(c, {'day': M.iso(d)})


def ai_clear(c, a):
    M.chat_clear(c, _d(a['day']) if a.get('day') else None); return True


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
    'task_delete': task_delete, 'task_info': task_info,
    'areas': areas_view, 'area_save': area_save, 'area_delete': area_delete,
    'ai_day': ai_day, 'ai_ask': ai_ask, 'ai_clear': ai_clear,
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
                                                   days=list(range(7)), time=a.get('time') or (M.habit(c, int(a['id']))['time'] if a.get('id') else '22:00'),
                                                   etime=a.get('etime') or None, remind=0, start_day=a.get('start_day') or (M.habit(c, int(a['id']))['start_day'] if a.get('id') else M.iso(M.today())))),
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


# ───────────────────────── 10.43 (like the desktop): tasks by day, Notes, Inspo ─────────────────────────
def tasks_days(c, a):
    """tasks of the days start..end (done ones stay), the ones with no date, and the boards with how many open tasks"""
    s, e = _d(a.get('start')), _d(a.get('end') or a.get('start')); area = int(a['area']) if a.get('area') else None
    ar = {x['id']: x for x in M.areas(c, True)}; now = M.now()
    def row(x):
        late = False
        if not x['done_at'] and x['day']:
            if x['time']:
                st = datetime.fromisoformat(f"{x['day']}T{x['time']}"); late = st + timedelta(minutes=int(x['minutes'] or 30)) < now
            else: late = x['day'] < M.iso(M.today())
        b = ar.get(x['area_id']) or {}
        return dict(id=x['id'], title=x['title'], area_id=x['area_id'], area=b.get('name'), color=b.get('color'), day=x['day'], time=x['time'], minutes=x['minutes'],
                    note=x['note'], why=x.get('why') or '', remind=x['remind'], done=bool(x['done_at']), done_at=x['done_at'], late=late)
    allt = M.tasks(c)
    rows = [row(x) for x in allt if x['day'] and M.iso(s) <= x['day'] <= M.iso(e) and (area is None or x['area_id'] == area)]
    rows.sort(key=lambda r: (r['day'], r['time'] or '99'))
    nod = [row(x) for x in allt if not x['day'] and not x['done_at'] and (area is None or x['area_id'] == area)]
    cnt = {}
    for x in allt:
        if not x['done_at']: cnt[x['area_id']] = cnt.get(x['area_id'], 0) + 1
    boards = [dict(id=b['id'], name=b['name'], color=b['color'], open=cnt.get(b['id'], 0)) for b in M.areas(c)]
    return dict(rows=rows, nodate=nod, boards=boards, all_open=sum(cnt.values()))


def notes_view(c, a):
    tags = M.note_tags(c); cols = M.note_tag_colors(c)
    ns = M.notes(c, a.get('tag') or None, q=a.get('q') or '')
    return dict(tags=[dict(name=t, color=cols[t]) for t in tags], palette=M.STICKY, notes=ns, memory=M.memory_of_day(c))


def notes_save(c, a):
    n = a['note']; old = next((x for x in M.notes(c) if x['id'] == int(n['id'])), {}) if n.get('id') else {}
    v = dict(old); v.update(n)
    if not ((v.get('title') or '').strip() or (v.get('content') or '').strip()): raise ValueError('Write something first.')
    return M.save_note(c, v)


def _spark(c):
    """one thing at a time from your notes, goals and dreams (pictures stay on the PC); a new one every few hours, like the desktop"""
    import time as _t
    pool = [x for x in M.spark_pool(c) if x['spark'] != 'card' or x['kind'] == 'quote']
    hrs = M.spark_hours(c); left = int(hrs * 3600 - (_t.time() % (hrs * 3600)))
    if not pool: return dict(item=None, hours=hrs, left=left)
    pool.sort(key=lambda x: (x['spark'], x['id']))
    import random as _r
    return dict(item=_r.Random(M.spark_slot(c) * 7919 + len(pool)).choice(pool), hours=hrs, left=left)


def inspo_view(c, a):
    return dict(goals=M.goals(c, 'goal'), dreams=M.goals(c, 'dream'), notes=[x for x in M.inspo_items(c) if x['kind'] == 'quote'],
                sections=M.inspo_sections(c), spark=_spark(c), view=M.setting(c, 'goal_view') or 'list', year=M.today().year)


def goal_save(c, a):
    g = a['goal']; old = dict(c.execute('SELECT * FROM goals WHERE id=?', (int(g['id']),)).fetchone() or {}) if g.get('id') else {}
    v = dict(old); v.update(g)
    if not (v.get('title') or '').strip(): raise ValueError('Write the goal first.')
    return M.save_goal(c, v)


OPS2 = {
    'tasks_days': tasks_days,
    'notes': notes_view, 'notes_save': notes_save,
    'notes_delete': lambda c, a: M.delete_note(c, int(a['id'])) or True,
    'notes_archive': lambda c, a: M.archive_note(c, int(a['id'])) or True,
    'tag_add': lambda c, a: M.add_note_tag(c, a['name']),
    'tag_rename': lambda c, a: M.rename_note_tag(c, a['old'], a['new']) or (_ for _ in ()).throw(ValueError('That name is already used.')),
    'tag_delete': lambda c, a: M.delete_note_tag(c, a['name']),
    'tag_color': lambda c, a: M.set_note_tag_color(c, a['name'], a['color']) or True,
    'inspo': inspo_view, 'goal_save': goal_save,
    'goal_delete': lambda c, a: M.delete_goal(c, int(a['id'])) or True,
    'dream_to_goal': lambda c, a: M.dream_to_goal(c, int(a['id'])) or True,
    'goal_view': lambda c, a: M.set_setting(c, 'goal_view', 'pics' if a.get('view') == 'pics' else 'list') or True,
    'spark_hours': lambda c, a: M.set_setting(c, 'inspo_spark_hours', str(int(a['hours']))) or True,
    'spark_next': lambda c, a: M.set_setting(c, 'inspo_spark_skip', str(int(M.setting(c, 'inspo_spark_skip') or 0) + 1)) or True,
    'card_spark': lambda c, a: M.update_inspo(c, int(a['id']), no_spark=1 if a.get('off', True) else 0) or True,
    'note_delete': lambda c, a: M.remove_inspo(c, int(a['id'])) or True,
    'section_rename': lambda c, a: M.rename_inspo_section(c, a['old'], a['new']) or (_ for _ in ()).throw(ValueError('That name is already used.')),
    'section_delete': lambda c, a: M.delete_inspo_section(c, a['name'], a['move_to']),
}


GOAL_OPS = {'inspo', 'goal_save', 'goal_done', 'goal_delete', 'dream_to_goal'}


def call(op, args):
    if op == 'card_page':                                               # a note card becomes a page in Docs › Inspo › Inspo cards
        import docs_web; return docs_web.card_page(int(args['id']))
    fn = OPS2.get(op) or OPS.get(op)
    if not fn: raise ValueError(f'Unknown: {op}')
    out = _j(run(lambda c: fn(c, args or {})))
    if op == 'inspo':
        try:
            import docs_web; docs_web.goal_pages(); out = _j(run(lambda c: fn(c, args or {})))
            th = docs_web.thumbs([g.get('page_id') for g in out['goals'] if g.get('page_id')])
            for g in out['goals']: g['pic'] = th.get(g.get('page_id') or '')
        except Exception:
            import logging; logging.exception('docs goals')
        return out
    if op in GOAL_OPS:
        try:
            import docs_web; docs_web.goal_pages()                       # goals are a table in Docs too (each one a page)
        except Exception:
            import logging; logging.exception('docs goals')
    return out


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
    push.seen_tick()
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
