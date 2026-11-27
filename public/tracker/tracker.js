/* Curio Tracker on the web — the same book as the desktop's Tracker (10.43): Home, Notes, Tasks, Check-ins, Habits, Nudges, Inspo, Sleep, Quit,
   and phone reminders. Everything is one call: POST /api/tracker {op, args}. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const h = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'html') e.innerHTML = v; else if (k === 'style' && typeof v === 'object') { for (const [sk, sv] of Object.entries(v)) { if (sk.startsWith('--')) e.style.setProperty(sk, sv); else e.style[sk] = sv; } }
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const toast = (m) => { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 2400); };
  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify(body) });
    if (r.status === 401) { (window.top || window).location.href = '/api/auth/login?next=/%23/tracker'; throw new Error('Signing you in…'); }
    const j = await r.json(); if (j.error) throw new Error(j.error); return j.data;
  }
  const api = (op, args = {}) => post('/api/tracker', { op, args });
  const act = async (op, args, msg) => { try { await api(op, args); if (msg) toast(msg); draw(); } catch (e) { toast(e.message); } };
  const pad = (n) => String(n).padStart(2, '0');
  const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const t12 = (hm) => { if (!hm) return ''; let [a, b] = hm.split(':').map(Number); const ap = a < 12 ? 'AM' : 'PM'; a = a % 12 || 12; return `${a}:${pad(b)} ${ap}`; };
  const hm = (m) => `${Math.floor(m / 60)}h ${pad(m % 60)}m`;
  const mins = (m) => m < 60 ? `${m} min` : `${Math.floor(m / 60)} h${m % 60 ? ' ' + pad(m % 60) + ' m' : ''}`;
  const rel = (at) => { const d = Math.round((new Date(at) - new Date()) / 60000); if (d < 0) return null; if (d < 1) return 'now'; if (d < 60) return `in ${d} min`; return `in ${Math.floor(d / 60)} h ${pad(d % 60)} m`; };
  const dayLab = (s) => { const d = new Date(s + 'T00:00'); const t = new Date(); t.setHours(0, 0, 0, 0); const k = Math.round((d - t) / 864e5);
    return k === 0 ? 'Today' : k === 1 ? 'Tomorrow' : k === -1 ? 'Yesterday' : d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }); };
  const chk = (on, c, fn) => h('button', { class: 'chk' + (on ? ' on' : ''), style: { '--c': c || 'var(--accent)' }, onclick: (e) => { e.stopPropagation(); fn(!on); }, 'aria-label': on ? 'Done' : 'Not done' });

  // ── a bottom sheet for every form ──
  function sheet(title, body, buttons) {
    const s = $('#sheet'), sc = $('#scrim');
    const close = () => { s.classList.remove('on'); sc.classList.remove('on'); };
    s.replaceChildren(h('h2', {}, title), body, h('div', { class: 'acts' }, ...(buttons || []).map(([t, cls, fn]) => h('button', { class: 'btn ' + (cls || ''), onclick: async () => { if ((await fn()) !== false) close(); } }, t)),
      h('button', { class: 'btn soft', onclick: close }, 'Close')));
    sc.onclick = close; requestAnimationFrame(() => { s.classList.add('on'); sc.classList.add('on'); }); return close;
  }
  const field = (lab, el) => h('div', {}, h('label', { class: 'l' }, lab), el);
  const inp = (v, ph, type = 'text') => h('input', { class: 'inp', type, value: v ?? '', placeholder: ph || '' });

  // ── tabs ──
  // like the desktop 10.42+: Notes and Tasks right after Home; Quit is for anything (smoking, NoFap…)
  const TABS = [['home', 'Home'], ['notes', 'Notes'], ['tasks', 'Tasks'], ['checkins', 'Check-ins'], ['habits', 'Habits'], ['nudges', 'Nudges'], ['inspo', 'Inspo'], ['sleep', 'Sleep'], ['quit', 'Quit'], ['phone', 'Setup']];
  let cur = (location.hash.slice(1) || 'home');
  function nav() { $('#nav').replaceChildren(...TABS.map(([k, t]) => h('button', { class: 'tab' + (k === cur ? ' on' : ''), onclick: () => { $('#sheet').classList.remove('on'); $('#scrim').classList.remove('on'); cur = k; location.hash = k; nav(); draw(); } }, t))); }
  let tick = null;
  async function draw() {
    clearInterval(tick); const p = $('#page');
    try { await (V[cur] || V.home)(p); } catch (e) { p.replaceChildren(h('div', { class: 'card' }, h('b', {}, 'Could not load: '), e.message)); }
  }
  const V = {};

  // ── Home ──
  V.home = async (p) => {
    const d = await api('home'); const hr = new Date().getHours();
    if (d.empty) { p.replaceChildren(h('div', { class: 'card' }, h('h3', {}, 'Your Tracker on the web is empty'),
      h('p', { class: 'muted' }, 'The web is where your Tracker lives from now on; the desktop app copies it with “Update from web”. Bring your desktop data here once — or start fresh.'),
      h('div', { class: 'row', style: { flexWrap: 'wrap' } }, h('button', { class: 'btn primary', onclick: () => { cur = 'phone'; location.hash = 'phone'; nav(); draw(); } }, 'Copy my desktop Tracker here'),
        h('button', { class: 'btn', onclick: () => taskForm({ day: iso(new Date()) }) }, '+ Task'), h('button', { class: 'btn', onclick: () => { cur = 'checkins'; location.hash = 'checkins'; nav(); draw(); } }, '+ Check-in item')))); return; }
    const greet = hr < 5 ? 'LATE NIGHT' : hr < 12 ? 'GOOD MORNING' : hr < 17 ? 'GOOD AFTERNOON' : hr < 21 ? 'GOOD EVENING' : 'GOOD NIGHT';
    const left = d.total - d.done; const nxt = d.timeline.filter(x => x.state === 'upcoming' && x.time);
    const pct = d.total ? Math.round(100 * d.done / d.total) : 0;
    const ring = h('div', { class: 'ring', html: `<svg width="76" height="76" viewBox="0 0 76 76"><circle cx="38" cy="38" r="31" stroke="rgba(255,255,255,.25)" stroke-width="8" fill="none"/><circle cx="38" cy="38" r="31" stroke="#fff" stroke-width="8" fill="none" stroke-linecap="round" stroke-dasharray="${(2 * Math.PI * 31 * pct / 100).toFixed(1)} 999" transform="rotate(-90 38 38)"/><text x="38" y="43" text-anchor="middle" fill="#fff" font-size="16" font-weight="900">${pct}%</text></svg>` });
    const els = [h('div', { class: 'card hero' }, h('div', { class: 'grow' }, h('div', { class: 'g' }, greet), h('div', { class: 't' }, !d.total ? 'Nothing planned yet' : !left ? 'Everything is done today' : `${left} thing${left > 1 ? 's' : ''} left today`),
      nxt.length ? h('div', { class: 'n', html: `Next: <b>${nxt[0].title}</b> at ${t12(nxt[0].time)}` }) : null, d.top3.length ? h('div', { class: 'n', html: `Main thing: <b>${d.top3[0].title}</b>` }) : null), ring)];
    const mini = h('div', { class: 'grid2' });
    if (d.sleep) mini.append(h('div', { class: 'card', onclick: () => { cur = 'sleep'; location.hash = 'sleep'; nav(); draw(); } }, h('h3', {}, 'Sleep', h('span', { class: 'sp' }), h('span', { class: 'pill', style: { '--c': d.sleep.color } }, d.sleep.grade)),
      h('div', { class: 'big', style: { color: d.sleep.color } }, hm(d.sleep.minutes)), h('div', { class: 'muted' }, `${t12(d.sleep.bed.slice(11, 16))} → ${t12(d.sleep.wake.slice(11, 16))}`)));
    for (const q of d.quit) mini.append(h('div', { class: 'card' }, h('h3', {}, q.name), h('div', { class: 'row' }, h('div', { class: 'big' }, q.days), h('div', { class: 'muted' }, 'days without it', h('br'), `best ${q.best}`)),
      h('div', { class: 'row', style: { marginTop: '8px' } }, h('button', { class: 'btn sm primary', onclick: () => struggle(q.id) }, 'I’m struggling'), h('button', { class: 'btn sm', onclick: () => slipped(q.id, q.name) }, 'I slipped'))));
    els.push(mini, h('div', { style: { height: '12px' } }));
    // the day in order
    const box = h('div', { class: 'card dark' }, h('h3', {}, 'Today'));
    const open = d.timeline.filter(x => x.state !== 'done' && x.state !== 'info' && x.kind !== 'focus'); const done = d.timeline.filter(x => x.state === 'done');
    const secs = [['NEXT', open.filter(x => x.time && x.state === 'upcoming')], ['STILL OPEN', open.filter(x => x.time && (x.state === 'late' || x.state === 'missed'))], ['ANY TIME TODAY', open.filter(x => !x.time)]];
    const rels = [];
    for (const [title, rows] of secs) {
      if (!rows.length) continue; box.append(h('div', { class: 'sec' }, title));
      rows.forEach((x, i) => {
        const r = h('span', {}); if (x.at && x.state === 'upcoming') rels.push([r, x.at]); else if (x.state === 'late') r.append(h('span', { class: 'late' }, 'late'));
        box.append(h('div', { class: 'item' + (title === 'NEXT' && i === 0 ? ' hi' : '') }, h('div', { class: 'muted', style: { width: '62px', fontSize: '12.5px' } }, t12(x.time)),
          h('div', { class: 't' }, h('b', {}, x.title), h('small', { style: { color: x.color } }, x.tag)), r,
          (x.kind === 'task' || x.kind === 'habit') ? h('button', { class: 'btn sm', onclick: () => x.kind === 'task' ? act('task_done', { id: x.ref }, 'Done') : act('habit_log', { id: x.ref, state: 'done' }, 'Done') }, 'Done') : null));
      });
    }
    if (done.length) box.append(h('div', { class: 'sec' }, `DONE ${done.length}`), ...done.slice(0, 30).map(x => h('div', { class: 'item done' }, h('div', { class: 'muted', style: { width: '62px', fontSize: '12.5px' } }, t12(x.time)), h('div', { class: 't' }, h('b', {}, x.title)))));
    els.push(box);
    const upd = () => rels.forEach(([e, at]) => { const t = rel(at); e.className = t ? 'rel' : 'late'; e.textContent = t || 'late'; }); upd(); tick = setInterval(upd, 30000);
    // check-ins
    const tiles = h('div', { class: 'tiles' });
    for (const [name, items] of Object.entries(d.routines)) {
      const c = d.colors[name] || 'var(--accent)', n = items.filter(x => x.done).length;
      tiles.append(h('div', { class: 'tile', style: { '--c': c } }, h('h4', {}, name, h('span', {}, `${n}/${items.length}`)),
        ...items.map(x => h('div', { class: 'item' + (x.done ? ' done' : '') + (x.late ? ' lateit' : ''), title: x.late ? 'Time passed — not done yet. Tick it when you have done it.' : '' },
          chk(x.done, c, (on) => act('habit_log', { id: x.id, state: on ? 'done' : null })), h('div', { class: 't' }, h('b', {}, x.name)), h('span', { class: 'faint' }, rng(x))))));
    }
    els.push(tiles);
    els.push(await aiCard(iso(new Date())));
    p.replaceChildren(...els);
  };

  // 🎙 speak instead of typing (the browser turns speech into text; language as on Ask AI)
  function micBtn(input, onDone) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const b = h('button', { class: 'btn mic', title: 'Speak instead of typing — press again to stop and send' }, '🎙');
    if (!SR) { b.onclick = () => toast('Speaking works in Chrome or Edge.'); return b; }
    let rec = null, base = '', fin = '';
    b.onclick = () => {
      if (rec) { rec.stop(); return; }
      rec = new SR(); let lang = 'hi-IN'; try { lang = localStorage.getItem('curio-voice-lang') || 'hi-IN'; } catch (e) { /* default */ }
      rec.lang = lang; rec.interimResults = true; rec.continuous = true; base = input.value ? input.value.trim() + ' ' : ''; fin = '';
      rec.onresult = (e) => { let mid = ''; for (let i = e.resultIndex; i < e.results.length; i++) { const t = e.results[i][0].transcript; if (e.results[i].isFinal) fin += t + ' '; else mid += t; } input.value = (base + fin + mid).trimStart(); };
      rec.onerror = (e) => { if (e.error === 'not-allowed' || e.error === 'service-not-allowed') toast('The browser is blocking the microphone: lock icon next to the address › Microphone › Allow.'); else if (e.error === 'no-speech') toast('No speech heard.'); };
      rec.onend = () => { rec = null; b.classList.remove('on'); b.textContent = '🎙'; if (input.value.trim()) onDone(); };
      try { rec.start(); b.classList.add('on'); b.textContent = '■'; toast('Listening… press ■ when you are done'); } catch (e) { rec = null; toast(e.message); }
    };
    return b;
  }

  // ── Ask AI about a day: the chat is saved, and the AI reads your earlier chats and your last 7 days before it answers ──
  async function aiCard(day) {
    const box = h('div', { class: 'card' });
    const fill = (d) => {
      const q = inp('', d.chat.length ? 'Reply…' : 'e.g. Why did my evening go off track?');
      const go = h('button', { class: 'btn primary', onclick: async () => {
        go.disabled = true; go.textContent = 'Thinking…';
        try { fill(await api('ai_ask', { day, question: q.value })); } catch (e) { toast(e.message); go.disabled = false; go.textContent = 'Ask'; }
      } }, 'Ask');
      q.addEventListener('keydown', (k) => { if (k.key === 'Enter') go.click(); });
      box.replaceChildren(...[h('h3', {}, 'Ask AI about ' + (day === iso(new Date()) ? 'today' : dayLab(day))),
        h('div', { class: 'faint', style: { marginBottom: '8px' } }, 'The chat is saved. The AI reads your earlier chats and your last 7 days before it answers — so tell it things once (e.g. “Canva is work”, “lunch is 1–2 PM”).'),
        ...d.chat.slice(-12).map(m => h('div', { class: 'bub ' + (m.role === 'user' ? 'me' : 'ai') }, m.text, m.role !== 'user' && 'speechSynthesis' in window ? h('button', { class: 'lis', title: 'Listen', onclick: () => {
          if (speechSynthesis.speaking) { speechSynthesis.cancel(); return; } const u = new SpeechSynthesisUtterance(m.text); const v = speechSynthesis.getVoices().find(x => /^en-IN|^hi/i.test(x.lang)); if (v) u.voice = v; speechSynthesis.speak(u); } }, '🔊') : null)),
        h('div', { class: 'row', style: { marginTop: '8px' } }, q, micBtn(q, () => go.click()), go),
        d.saved ? h('div', { class: 'row', style: { marginTop: '8px' } }, h('span', { class: 'faint grow' }, `${d.saved} message${d.saved === 1 ? '' : 's'} saved`),
          d.chat.length ? h('button', { class: 'btn sm soft', onclick: async () => { if (!confirm('Delete this day’s chat with the AI?')) return; await api('ai_clear', { day }); fill(await api('ai_day', { day })); } }, 'Clear this day') : null,
          h('button', { class: 'btn sm soft', onclick: async () => { if (!confirm('Delete every saved chat with the AI? It will not remember them any more.')) return; await api('ai_clear', {}); fill(await api('ai_day', { day })); } }, 'Forget all chats')) : null].filter(Boolean));
    };
    try { fill(await api('ai_day', { day })); } catch (e) { box.replaceChildren(h('h3', {}, 'Ask AI'), h('div', { class: 'muted' }, e.message)); }
    return box;
  }

  // ── Tasks (like the desktop 10.40+: big boards, one date navigator, Day / Week, List / Table; done tasks stay) ──
  let AREAS = [];
  const TK = { area: null, day: iso(new Date()), span: 'day', view: 'list' };
  const addDays = (s, k) => { const d = new Date(s + 'T00:00'); d.setDate(d.getDate() + k); return iso(d); };
  const monOf = (s) => { const d = new Date(s + 'T00:00'); const k = (d.getDay() + 6) % 7; d.setDate(d.getDate() - k); return iso(d); };
  // one navigator for every page: ‹ [pick a day] ›  and Today (orange when you are on another day)
  function dateNav(cur, onPick, opts = {}) {
    const today = iso(new Date()); const max = opts.max || null;
    const pick = h('input', { type: 'date', class: 'inp dpick', value: cur, max: max || undefined, onchange: (e) => e.target.value && onPick(e.target.value) });
    const step = (k) => { let v = addDays(cur, k * (opts.step || 1)); if (max && v > max) v = max; onPick(v); };
    const lab = opts.label || ((cur === today ? 'Today · ' : '') + new Date(cur + 'T00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }));
    return h('div', { class: 'dnav' }, h('button', { class: 'btn sm', onclick: () => step(-1) }, '‹'),
      h('label', { class: 'dlab' }, h('b', {}, lab), ' ▾', pick), h('button', { class: 'btn sm', disabled: !!(max && cur >= max), onclick: () => step(1) }, '›'),
      h('button', { class: 'btn sm' + ((opts.isNow ? !opts.isNow() : cur !== today) ? ' primary' : ' soft'), onclick: () => onPick(today) }, 'Today'));
  }
  const seg = (opts, cur, fn) => h('div', { class: 'seg' }, opts.map(([k, t]) => h('button', { class: cur === k ? 'on' : '', onclick: () => fn(k) }, t)));
  const status = (x) => x.done ? ['Done', 'var(--good)'] : x.late ? ['Not done', 'var(--bad)'] : ['To do', 'var(--muted)'];
  const whenTxt = (x, withDay) => [withDay && x.day ? dayLab(x.day) : '', x.time ? t12(x.time) + ' → ' + t12(endOf(x)) : ''].filter(Boolean).join(' · ');
  V.tasks = async (p) => {
    const start = TK.span === 'week' ? monOf(TK.day) : TK.day, end = TK.span === 'week' ? addDays(start, 6) : TK.day;
    const d = await api('tasks_days', { start, end, area: TK.area }); AREAS = d.boards;
    // the boards
    const bar = h('div', { class: 'boards' }, h('button', { class: 'board' + (TK.area == null ? ' on' : ''), style: { '--c': 'var(--ink)' }, onclick: () => { TK.area = null; draw(); } }, 'All boards', h('span', {}, d.all_open)),
      ...d.boards.map(b => h('button', { class: 'board' + (TK.area === b.id ? ' on' : ''), style: { '--c': b.color }, title: 'Tap again for Rename / Colour / Delete',
        onclick: () => { if (TK.area === b.id) boardMenu(b, d.boards); else { TK.area = b.id; draw(); } },
        oncontextmenu: (e) => { e.preventDefault(); boardMenu(b, d.boards); } }, h('i', {}), b.name, h('span', {}, b.open))),
      h('button', { class: 'board add', onclick: () => newBoard() }, '+ Board'));
    const wlab = TK.span === 'week' ? `${new Date(start + 'T00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} – ${new Date(end + 'T00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}` : null;
    const top = h('div', { class: 'row wrapr', style: { margin: '10px 0' } }, dateNav(TK.day, (v) => { TK.day = v; draw(); }, { step: TK.span === 'week' ? 7 : 1, label: wlab,
      isNow: () => TK.span === 'week' ? monOf(iso(new Date())) === start : TK.day === iso(new Date()) }),
      seg([['day', 'Day'], ['week', 'Week']], TK.span, (k) => { TK.span = k; draw(); }), h('div', { class: 'grow' }),
      seg([['list', 'List'], ['table', 'Table']], TK.view, (k) => { TK.view = k; draw(); }),
      h('button', { class: 'btn primary', onclick: () => taskForm({ day: TK.day, area_id: TK.area }) }, '+ Task'));
    const els = [bar, top];
    const row = (x, withDay) => h('div', { class: 'item' + (x.done ? ' done' : '') + (x.late ? ' lateit' : ''), onclick: () => taskForm(x) },
      chk(x.done, x.color, (on) => act('task_done', { id: x.id, on }, on ? 'Done ✓' : 'Opened again')),
      h('div', { class: 't' }, h('b', {}, x.title), h('small', {}, [x.area, whenTxt(x, withDay)].filter(Boolean).join('  ·  '))));
    if (TK.view === 'table') {
      const rows = d.rows;
      els.push(h('div', { class: 'card tblc' }, h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, 'Status'), h('th', {}, 'Task'), h('th', {}, 'Board'), h('th', {}, 'Date'))),
        h('tbody', {}, ...rows.map(x => { const [st, sc] = status(x); return h('tr', { class: (x.done ? 'done' : '') + (x.late ? ' lateit' : ''), onclick: () => taskForm(x) },
          h('td', {}, h('div', { class: 'row', style: { gap: '8px' } }, chk(x.done, x.color, (on) => act('task_done', { id: x.id, on }, on ? 'Done ✓' : 'Opened again')), h('b', { style: { color: sc, fontSize: '12px' } }, st))),
          h('td', { class: 'tt' }, x.title), h('td', { style: { color: x.color } }, x.area || ''), h('td', { class: 'muted' }, whenTxt(x, true) || dayLab(x.day))); }))),
        rows.length ? null : h('div', { class: 'empty' }, 'Nothing planned in these days.'),
        h('div', { class: 'faint', style: { marginTop: '8px' } }, 'Tap a row to change it · red “Not done” = its time is over and it is not ticked.')));
    } else {
      const days = TK.span === 'week' ? [...Array(7)].map((_, i) => addDays(start, i)) : [TK.day];
      for (const day of days) {
        const list = d.rows.filter(x => x.day === day);
        if (TK.span === 'week' && !list.length) continue;
        els.push(h('div', { class: 'card' }, h('h3', {}, dayLab(day), h('span', { class: 'muted', style: { fontWeight: 600, fontSize: '13px' } }, `${list.filter(x => x.done).length}/${list.length}`), h('span', { class: 'sp' }),
          h('button', { class: 'btn sm', onclick: () => taskForm({ day, area_id: TK.area }) }, '+')), ...(list.length ? list.map(x => row(x, false)) : [h('div', { class: 'empty' }, 'Nothing planned.')])));
      }
      if (TK.span === 'week' && !d.rows.length) els.push(h('div', { class: 'card empty' }, 'Nothing planned this week.'));
      if (d.nodate.length) els.push(h('div', { class: 'card' }, h('h3', {}, 'No date', h('span', { class: 'muted' }, d.nodate.length)), ...d.nodate.map(x => row(x, false))));
    }
    p.replaceChildren(...els);
  };
  // board: rename, colour, delete (its tasks / check-ins move to the board you pick — nothing is deleted)
  const BCOL = ['#e0a100', '#f2602d', '#dc2626', '#d6457a', '#8b5cf6', '#6d5bd0', '#2f6fde', '#0e8fa3', '#1f9d6b', '#65a30d', '#a16207', '#6b7280'];
  function boardMenu(b, all) {
    const name = inp(b.name, 'Board name'); let col = b.color;
    const sw = h('div', { class: 'swatches' }, ...BCOL.map(c => h('button', { class: c === col ? 'on' : '', style: { background: c }, onclick: (e) => { col = c; wheel.value = c; sw.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === e.currentTarget)); } })));
    const wheel = h('input', { type: 'color', value: col, class: 'wheel', oninput: (e) => { col = e.target.value; sw.querySelectorAll('button').forEach(z => z.classList.remove('on')); } });
    sheet(b.name, h('div', {}, field('Name', name), field('Colour (the Calendar uses it too)', h('div', { class: 'row', style: { flexWrap: 'wrap' } }, sw, h('label', { class: 'faint row' }, wheel, 'any colour')))),
      [['Delete board…', 'danger', () => { delBoard(b, all); return false; }],
       ['Save', 'primary', async () => { try { await api('area_save', { id: b.id, name: name.value, color: col }); toast('Saved'); draw(); } catch (e) { toast(e.message); return false; } }]]);
  }
  function newBoard() {
    const name = inp('', 'e.g. Health, Office, Family');
    sheet('New board', field('Name', name), [['Add', 'primary', async () => { try { await api('area_save', { name: name.value, color: BCOL[(AREAS.length + 2) % BCOL.length] }); draw(); } catch (e) { toast(e.message); return false; } }]]);
    setTimeout(() => name.focus(), 250);
  }
  function delBoard(b, bs) {
    const others = bs.filter(x => x.id !== b.id);
    const to = h('select', { class: 'inp' }, others.map(x => h('option', { value: x.id }, x.name)), h('option', { value: '' }, 'No board'));
    sheet(`Delete “${b.name}”?`, h('div', {}, h('p', { class: 'muted' }, 'Its tasks and check-ins are not deleted — they move to:'), to),
      [['Delete board', 'danger', async () => { await api('area_delete', { id: b.id, move_to: to.value || null }).catch(e => toast(e.message)); toast('Board deleted'); if (TK.area === b.id) TK.area = null; draw(); }]]);
  }
  const rng = (x) => x.time ? t12(x.time) + (x.etime ? ' → ' + t12(x.etime) : '') : '';
  const endOf = (x) => { if (!x.time) return ''; const [a, b] = x.time.split(':').map(Number); const e = a * 60 + b + (x.minutes || 30); return `${pad(Math.floor(e / 60) % 24)}:${pad(e % 60)}`; };
  async function taskForm(x) {
    if (!AREAS.length) AREAS = (await api('tasks_days', { start: iso(new Date()) })).boards;
    const title = inp(x.title, 'What needs doing?'); const why = inp(x.why, 'Optional — one line: why it matters'); let area = x.area_id || (AREAS[0] || {}).id;
    const chips = h('div', { class: 'chips' }, AREAS.map(a => { const b = h('button', { class: a.id === area ? 'on' : '', style: { '--c': a.color }, onclick: () => { area = a.id; chips.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === b)); } }, a.name); return b; }));
    const day = inp(x.day || '', '', 'date'), st = inp(x.time || '', '', 'time'), en = inp(x.time ? endOf(x) : '', '', 'time');
    const note = h('textarea', { class: 'inp', rows: 3, placeholder: 'Notes (optional)' }, x.note || '');
    const body = h('div', {}, field('Task', title), field('Why', why), field('Board', chips), field('Day', day),
      h('div', { class: 'grid2' }, field('Starts', st), field('Ends', en)), h('div', { class: 'faint' }, 'Leave the times empty for an all-day task.'), field('Notes', note));
    const btns = [['Save', 'primary', async () => {
      let m = x.minutes || 30;
      if (st.value && en.value) { const [a, b] = st.value.split(':').map(Number), [c, e] = en.value.split(':').map(Number); m = (c * 60 + e) - (a * 60 + b); if (m <= 0) m += 1440; }
      try { await api('task_save', { task: { id: x.id, title: title.value, why: why.value, area_id: area, day: day.value || null, time: day.value && st.value ? st.value : null, minutes: m, note: note.value, remind: st.value ? 10 : -1 } }); toast('Saved'); draw(); }
      catch (e) { toast(e.message); return false; }
    }]];
    if (x.id) btns.unshift(['Delete', 'danger', async () => { if (!confirm('Delete this task?')) return false; await act('task_delete', { id: x.id }, 'Deleted'); }]);
    sheet(x.id ? 'Edit task' : 'New task', body, btns); setTimeout(() => title.focus(), 250);
  }

  // ── Check-ins and Habits (any day: ‹ day ›; green done, red when the time passed) ──
  const HD = { day: iso(new Date()) };
  async function habitsView(p, routine) {
    const d = await api('checkins', { day: HD.day }); const els = [];
    els.push(h('div', { class: 'row wrapr', style: { marginBottom: '10px' } }, dateNav(HD.day, (v) => { HD.day = v; draw(); }, { max: iso(new Date()) }), h('div', { class: 'grow' }),
      h('button', { class: 'btn primary', onclick: () => habitForm(routine ? { routine: 'Morning' } : { routine: '' }, d) }, routine ? '+ Check-in item' : '+ Habit')));
    const groups = routine ? [...d.order.filter(k => d.groups[k]), ...Object.keys(d.groups).filter(k => k && !d.order.includes(k))] : [''];
    for (const g of groups) {
      const items = (d.groups[g] || []).filter(x => x.due); const c = d.colors[g] || 'var(--good)';
      if (!items.length) { if (!routine) els.push(h('div', { class: 'card empty' }, 'No habits on this day.')); continue; }
      els.push(h('div', { class: 'card' }, h('h3', { style: { color: c } }, g || 'Habits', h('span', { class: 'sp' }), h('span', { class: 'muted', style: { fontSize: '13px' } }, `${items.filter(x => x.state === 'done').length} of ${items.length} done`)),
        ...items.map(x => { const late = x.late && x.state !== 'done';
          const pill = x.state === 'done' ? ['done', 'var(--good)'] : x.state === 'skip' ? ['skipped', 'var(--muted)'] : x.state === 'missed' ? ['missed', 'var(--bad)'] : late ? ['not done', 'var(--bad)'] : null;
          return h('div', { class: 'item' + (x.state === 'done' ? ' done' : '') + (late ? ' lateit' : ''), onclick: () => habitForm(x, d) },
            chk(x.state === 'done', c, (on) => act('habit_log', { id: x.id, day: HD.day, state: on ? 'done' : null })),
            h('div', { class: 't' }, h('b', {}, x.name), x.why ? h('small', {}, x.why) : null), pill ? h('span', { class: 'pill', style: { '--c': pill[1] } }, pill[0]) : null,
            h('span', { class: 'faint', style: { minWidth: '66px', textAlign: 'right' } }, rng(x))); })));
    }
    if (d.changes.length) els.push(h('div', { class: 'card' }, h('h3', {}, 'Changes'), h('div', { class: 'faint' }, 'What you added, changed and stopped — and when.'), ...d.changes.slice(0, 8).map(x => h('div', { class: 'item' }, h('span', { class: 'pill', style: { '--c': x.color } }, x.what),
      h('div', { class: 't' }, h('b', {}, x.name), h('small', {}, `${dayLab(x.day)} · ${x.detail}`))))));
    const st = (d.stopped || []).filter(x => routine ? x.routine : !x.routine);
    if (st.length) els.push(h('div', { class: 'card' }, h('h3', {}, routine ? 'Removed items' : 'Stopped habits'), ...st.map(x => h('div', { class: 'item' }, h('div', { class: 't' }, h('b', {}, x.name), h('small', {}, x.last ? 'stopped ' + dayLab(x.last) : '')),
      h('button', { class: 'btn sm', onclick: () => act('habit_restart', { id: x.id }, 'Back from today') }, 'Restart')))));
    p.replaceChildren(...els);
  }
  const DOW = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  async function habitForm(x, d) {
    if (!AREAS.length) AREAS = (await api('tasks_days', { start: iso(new Date()) })).boards;
    const isRt = x.routine !== '' && x.routine != null;
    const name = inp(x.name, isRt ? 'e.g. Fajr, Skincare, Check Gmail' : 'e.g. Read 20 pages'); const why = inp(x.why, 'Optional — one line: why it matters');
    const rt = h('select', { class: 'inp' }, [...new Set([...(d.order || []), ...(x.routine ? [x.routine] : [])])].map(r => h('option', { value: r, selected: r === x.routine }, r)));
    let days = (x.days && x.days.length ? x.days : [0, 1, 2, 3, 4, 5, 6]).slice();
    const dchips = h('div', { class: 'chips' }, DOW.map((t, i) => { const b = h('button', { class: days.includes(i) ? 'on' : '', onclick: () => { days = days.includes(i) ? days.filter(z => z !== i) : [...days, i]; b.classList.toggle('on'); } }, t); return b; }));
    const tm = inp(x.time || '', '', 'time'), tme = inp(x.etime || '', '', 'time'); const rem = h('input', { type: 'checkbox', checked: x.id ? (x.remind ?? -1) >= 0 : true });
    let area = x.area_id || (AREAS[0] || {}).id;
    const chips = h('div', { class: 'chips' }, AREAS.map(a => { const b = h('button', { class: a.id === area ? 'on' : '', style: { '--c': a.color }, onclick: () => { area = a.id; chips.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === b)); } }, a.name); return b; }));
    const from = inp(iso(new Date()), '', 'date');
    const body = h('div', {}, field('Name', name), field('Why', why), isRt ? field('Check-in', rt) : null, field('Days', dchips), h('div', { class: 'grid2' }, field('Starts', tm), field('Ends (optional)', tme)),
      h('label', { class: 'item' }, rem, h('span', {}, 'Remind me at the start time (phone and PC)')), field('Board', chips), x.id ? field('Changes start on (earlier days keep the old plan and times)', from) : null,
      x.history && x.history.length ? h('div', { class: 'faint', style: { marginTop: '8px' } }, h('b', {}, 'Plan history'), ...x.history.map(l => h('div', {}, l))) : null);
    const btns = [['Save', 'primary', async () => {
      try { await api('habit_save', { habit: { id: x.id, name: name.value, why: why.value, routine: isRt ? rt.value : '', days: days.sort(), time: tm.value || null, etime: tm.value && tme.value ? tme.value : null, remind: rem.checked && tm.value ? 0 : -1, area_id: area, kind: 'build' }, from_day: x.id ? from.value : null }); toast('Saved'); draw(); }
      catch (e) { toast(e.message); return false; }
    }]];
    if (x.id) btns.unshift(['Stop it', 'danger', () => confirm(`Stop “${x.name}” from today? Its history stays.`) ? act('habit_end', { id: x.id }, 'Stopped') : false]);
    sheet(x.id ? 'Edit' : isRt ? 'New check-in item' : 'New habit', body, btns);
  }
  V.checkins = (p) => habitsView(p, true);
  V.habits = (p) => habitsView(p, false);

  // ── Sleep (a month, in a calendar) ──
  let SL = { mode: 'month', off: 0 };
  V.sleep = async (p) => {
    const d = await api('sleep', SL);
    const first = new Date(d.start + 'T00:00'); const lead = (first.getDay() + 6) % 7;
    const grid = h('div', { class: 'mcal' }, ...DOW.map(t => h('div', { class: 'mh' }, t)));
    const cell0 = new Date(first); cell0.setDate(cell0.getDate() - lead);
    const last = new Date(d.end + 'T00:00'); const cells = Math.ceil((lead + last.getDate()) / 7) * 7;
    for (let i = 0; i < cells; i++) {
      const dt = new Date(cell0); dt.setDate(cell0.getDate() + i); const k = iso(dt); const inM = dt.getMonth() === first.getMonth(); const r = inM ? d.nights[k] : null;
      grid.append(h('div', { class: 'mc' + (inM ? '' : ' out') + (r ? ' has' : '') + (k === iso(new Date()) ? ' today' : ''), style: r ? { '--c': r.color } : {}, onclick: () => inM && sleepForm(k, r, d) },
        h('div', { class: 'dn' }, dt.getDate()), r ? h('div', { class: 'h' }, hm(r.minutes)) : null));
    }
    const lab = first.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
    p.replaceChildren(h('div', { class: 'card' }, h('h3', {}, `Every night ${t12(d.bed)} → ${t12(d.wake)}`, h('span', { class: 'sp' }), h('button', { class: 'btn sm', onclick: () => usualForm(d) }, 'Change usual times')),
      h('div', { class: 'muted' }, d.auto ? 'Each night fills in by itself. If a night was different, tap it.' : 'Tap a night to log it.')),
      h('div', { class: 'card' }, h('div', { class: 'row', style: { marginBottom: '8px' } }, h('button', { class: 'btn sm', onclick: () => { SL.off--; draw(); } }, '‹'), h('b', { class: 'grow', style: { textAlign: 'center' } }, lab),
        h('button', { class: 'btn sm' + (SL.off ? ' primary' : ' soft'), onclick: () => { SL.off = 0; draw(); } }, 'This month'), h('button', { class: 'btn sm', disabled: SL.off >= 0, onclick: () => { SL.off++; draw(); } }, '›')),
        grid, h('div', { class: 'row faint', style: { marginTop: '10px' } }, h('span', { style: { color: 'var(--good)' } }, '● Good'), h('span', { style: { color: 'var(--poor)' } }, '● Poor'), h('span', { style: { color: 'var(--bad)' } }, '● Bad'))));
  };

  // ── Quit (anything: smoking, NoFap, sugar…) — one simple card each ──
  V.quit = async (p) => {
    const qs = await api('quit');
    const els = [h('div', { class: 'row', style: { marginBottom: '10px' } }, h('div', { class: 'grow muted' }, 'When an urge comes press “I’m struggling”. If it happened, “I slipped” — the count starts again, your history stays.'),
      h('button', { class: 'btn', onclick: () => quitForm({}) }, '+ Something to quit'))];
    if (!qs.length) els.push(h('div', { class: 'card empty' }, 'Nothing here yet.'));
    for (const q of qs) {
      els.push(h('div', { class: 'card' }, h('h3', {}, q.name, h('span', { class: 'sp' }), h('span', { class: 'faint' }, `best ${q.best} · ${q.beaten} urges beaten · ${q.relapses} slips`), h('button', { class: 'btn sm', onclick: () => quitForm(q) }, 'Edit')),
        h('div', { class: 'row' }, h('div', { class: 'big', style: { fontSize: '46px' } }, q.days), h('div', { class: 'muted' }, h('b', {}, `day${q.days === 1 ? '' : 's'} without it`), ` + ${q.hours} h`, h('br'), 'since ' + new Date(q.since).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }))),
        h('div', { class: 'row', style: { marginTop: '10px' } }, h('button', { class: 'btn primary', style: { flex: 2 }, onclick: () => struggle(q.id, q) }, 'I’m struggling'), h('button', { class: 'btn', style: { flex: 1 }, onclick: () => slipped(q.id, q.name) }, 'I slipped')),
        q.why ? h('div', {}, h('div', { class: 'sec' }, 'WHY I’M DOING THIS'), ...q.why.split('\n').filter(Boolean).slice(0, 5).map(l => h('div', {}, '•  ' + l))) : null,
        h('div', { class: 'sec' }, 'LATELY'), ...(q.events.length ? q.events.slice(0, 6).map(x => h('div', { class: 'row', style: { gap: '8px', margin: '3px 0' } },
          h('span', { class: 'pill', style: { '--c': x.kind === 'urge' ? 'var(--good)' : 'var(--bad)' } }, x.kind === 'urge' ? 'Beat an urge' : 'Slipped'),
          h('span', { class: 'faint' }, new Date(x.ts).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) + (x.trigger ? ' · ' + x.trigger : '')))) : [h('div', { class: 'faint' }, 'Nothing yet.')])));
    }
    p.replaceChildren(...els);
  };
  function quitForm(q) {
    const name = inp(q.name, 'e.g. Smoking, NoFap'); const why = h('textarea', { class: 'inp', rows: 4, placeholder: 'Why you are doing this — one reason per line' }, q.why || '');
    const a = inp(q.time || '22:00', '', 'time'), b = inp(q.etime || '', '', 'time');
    const since = inp(q.start_day || iso(new Date()), '', 'date'); since.max = iso(new Date());
    sheet(q.id ? 'Edit' : 'Something to quit', h('div', {}, field('Name', name), h('div', { class: 'grid2' }, field('Risky time — from', a), field('to', b)),
      h('div', { class: 'faint' }, 'When urges usually come. At that time you get a short, kind nudge with your first reason.'), field('My reasons', why),
      field('Stopped on', since), h('div', { class: 'faint' }, 'Your day 1 — the days you stay away are counted from here. A slip starts the count again.')),
      [['Save', 'primary', () => act('quit_save', { id: q.id, name: name.value, why: why.value, time: a.value || null, etime: b.value || null, start_day: since.value }, 'Saved')]]);
  }

  async function struggle(id, q) {
    q = q || (await api('quit')).find(x => x.id === id) || {};
    let left = 600; const clock = h('div', { class: 'timer' }, '10:00');
    const tips = (q.plan && q.plan.length ? q.plan : ['Leave the room or change where you are', 'Put the phone away — in another room', 'Drink water and take a short walk', 'Do something that keeps your mind busy']);
    const body = h('div', {}, h('p', { class: 'muted' }, 'An urge doesn’t mean you have to act on it — it peaks and passes.'), clock, h('div', { class: 'faint', style: { textAlign: 'center' } }, '10-minute urge timer'),
      h('div', { class: 'sec' }, 'TRY ONE NOW'), ...tips.map(t => h('label', { class: 'item' }, h('input', { type: 'checkbox' }), h('span', {}, t))),
      q.why ? h('div', {}, h('div', { class: 'sec' }, 'WHY I’M DOING THIS'), ...q.why.split('\n').filter(Boolean).slice(0, 4).map(l => h('div', {}, '•  ' + l))) : null);
    const iv = setInterval(() => { left = Math.max(0, left - 1); clock.textContent = left ? `${Math.floor(left / 60)}:${pad(left % 60)}` : 'You made it.'; if (!left) clearInterval(iv); }, 1000);
    const close = sheet('You can get through this.', body, [['I got through it', 'primary', async () => { clearInterval(iv); await act('quit_log', { id, kind: 'urge', helped: 'urge timer' }, 'Urge beaten — saved'); }]]);
    $('#scrim').addEventListener('click', () => clearInterval(iv), { once: true }); return close;
  }
  function urgeForm(id) {
    const trig = h('div', { class: 'chips' }, ['Bored', 'Alone', 'Late night', 'Phone in bed', 'Stressed', 'Tired', 'Social media'].map(t => h('button', { onclick: (e) => { trig.querySelectorAll('button').forEach(b => b.classList.remove('on')); e.target.classList.add('on'); } }, t)));
    const help = inp('', 'What helped? (optional)');
    sheet('Urge beaten', h('div', {}, field('What triggered it', trig), field('What helped', help)),
      [['Save', 'primary', () => act('quit_log', { id, kind: 'urge', trigger: (trig.querySelector('.on') || {}).textContent || '', helped: help.value }, 'Saved')]]);
  }
  function slipped(id, name) {
    const now = new Date(); const when = inp(`${iso(now)}T${pad(now.getHours())}:${pad(now.getMinutes())}`, '', 'datetime-local');
    const trig = h('div', { class: 'chips' }, ['Boredom', 'Stress', 'Late night', 'Phone in bed', 'Social media', 'Alone', 'Tired', 'Other'].map(t => h('button', { onclick: (e) => { trig.querySelectorAll('button').forEach(b => b.classList.remove('on')); e.target.classList.add('on'); } }, t)));
    const note = h('textarea', { class: 'inp', rows: 2, placeholder: 'Anything you want to note (optional)' });
    sheet('It’s okay — let’s understand what happened', h('div', {}, h('p', { class: 'muted' }, `${name}: one setback doesn’t erase your progress. Your history is kept; a new streak starts from this time.`), field('When', when), field('What triggered it', trig), field('Note', note)),
      [['Save', 'primary', async () => { await api('quit_log', { id, kind: 'relapse', when: when.value, trigger: (trig.querySelector('.on') || {}).textContent || '', note: note.value });
        sheet('Your next chapter starts now.', h('p', { class: 'muted' }, 'Your previous journey is saved. Your new streak starts from the moment you chose.'), []); draw(); }]]);
  }

  // ── Nudges ──
  V.nudges = async (p) => {
    const ns = await api('nudges');
    const pcOnly = (n) => n.kind === 'drift' || !!n.active_only;
    const row = (n) => h('div', { class: 'item', onclick: () => nudgeForm(n) }, chk(!!n.enabled, 'var(--accent)', (on) => act('nudge_save', { nudge: Object.assign({}, n, { enabled: on ? 1 : 0, days: JSON.parse(n.days || '[]') }) })),
      h('div', { class: 't' }, h('b', {}, n.text), h('small', {}, (n.kind === 'timer' ? `every ${n.every} min · ${t12(n.start)}–${t12(n.end)}` : n.kind === 'drift' ? `by itself, when a distraction is on the PC screen ${n.every}+ min` : `once a day at ${t12(n.start)}`) + (n.brief ? ' · AI brief' : ''))));
    const phone = ns.filter(n => !pcOnly(n)), pc = ns.filter(pcOnly);
    p.replaceChildren(
      h('div', { class: 'card' }, h('h3', {}, 'On your phone (and PC)', h('span', { class: 'sp' }), h('button', { class: 'btn sm primary', onclick: () => nudgeForm({ active_only: 0 }) }, '+ Nudge')),
        h('div', { class: 'faint' }, 'These come as a notification on the phone at their time. Example: “Drink water” every 90 minutes, or “Pay rent” once a day at 10 AM.'),
        ...(phone.length ? phone.map(row) : [h('div', { class: 'muted', style: { padding: '8px 0' } }, 'None yet — add one with + Nudge.')])),
      h('div', { class: 'card' }, h('h3', {}, 'On the PC only', h('span', { class: 'sp' }), h('button', { class: 'btn sm', onclick: () => nudgeForm({ active_only: 1 }) }, '+ PC nudge')),
        h('div', { class: 'faint' }, 'Screen things — look away, sit straight, and the one that comes by itself when a distraction is on screen. They pop up on the PC while you use it (Curio desktop open), never on the phone. You do not have to add these; they are already here.'),
        ...pc.map(row)));
  };
  function nudgeForm(n) {
    const text = inp(n.text, 'e.g. Sit up straight'); const brief = h('textarea', { class: 'inp', rows: 4, placeholder: 'Brief for the AI — what this is for and when / how to remind you' }, n.brief || '');
    const kind = h('select', { class: 'inp' }, [['timer', 'Every few minutes'], ['at', 'Once a day at a time'], ['drift', 'By itself, when a distraction is on the PC screen']].map(([k, t]) => h('option', { value: k, selected: (n.kind || 'timer') === k }, t)));
    const every = inp(n.every || 40, '', 'number'), st = inp(n.start || '10:00', '', 'time'), en = inp(n.end || '23:30', '', 'time');
    const where = h('select', { class: 'inp' }, [[0, 'On my phone too (and on the PC)'], [1, 'On the PC only — while I am using it']].map(([k, t]) => h('option', { value: k, selected: (n.active_only ? 1 : 0) === k }, t)));
    const syncWhere = () => { if (kind.value === 'drift') where.value = '1'; where.disabled = kind.value === 'drift'; }; kind.addEventListener('change', syncWhere); syncWhere();
    const btns = [['Save', 'primary', () => act('nudge_save', { nudge: { id: n.id, text: text.value, brief: brief.value, kind: kind.value, every: +every.value, start: st.value, end: en.value, active_only: +where.value, enabled: n.id ? n.enabled : 1, days: n.days ? JSON.parse(n.days) : [0, 1, 2, 3, 4, 5, 6] } }, 'Saved')]];
    if (n.id) btns.unshift(['Delete', 'danger', () => confirm('Delete this nudge?') ? act('nudge_delete', { id: n.id }, 'Deleted') : false]);
    sheet(n.id ? 'Edit nudge' : 'New nudge', h('div', {}, field('Title', text), field('Brief for the AI', brief), field('When', kind), h('div', { class: 'grid2' }, field('Every (min)', every), h('div', {})),
      h('div', { class: 'grid2' }, field('From', st), field('To', en)), field('Where', where),
      h('div', { class: 'faint' }, 'For “once a day”, From is the time it comes. The brief tells the AI on the PC how to word it and when to be strict.')), btns);
  }

  // ── a Docs page, opened right here (Docs = the Notion-like part; it used to be called Pages) ──
  function openDoc(pid, title) {
    const theme = document.documentElement.dataset.theme || 'light';
    const ov = h('div', { class: 'docov' }, h('div', { class: 'dochead' }, h('b', { class: 'grow' }, title || 'Page'),
        h('button', { class: 'btn sm', onclick: () => { try { window.top.postMessage({ curio: 'openPage', id: pid }, location.origin); } catch (e) { /* same site */ } ov.remove(); } }, 'Open in Docs'),
        h('button', { class: 'btn sm', onclick: () => { ov.remove(); draw(); } }, 'Close')),
      h('iframe', { src: `/pages/index.html?theme=${theme}&embed=1#/documents/${pid}`, title: title || 'Page' }));
    document.body.append(ov);
  }

  // ── Inspo: this year's goals (added / achieved dates, list or pictures), raw dreams (drag up = a goal), Today's spark, note cards ──
  const NOTE = ['#fff1b8', '#ffd8e4', '#d6ecff', '#d9f5e3', '#e9defc', '#ffe3cc'];
  const dt = (s) => s ? new Date(s.length > 10 ? s : s + 'T12:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  const goalYear = (g) => +((g.due || g.created || iso(new Date())).slice(0, 4));
  let IN = { year: new Date().getFullYear(), sec: null };
  V.inspo = async (p) => {
    const d = await api('inspo'); const yr = IN.year;
    const gs = d.goals.filter(g => goalYear(g) === yr);
    const gcard = h('div', { class: 'card', ondragover: (e) => { e.preventDefault(); gcard.classList.add('drop'); }, ondragleave: () => gcard.classList.remove('drop'),
      ondrop: async (e) => { e.preventDefault(); gcard.classList.remove('drop'); const id = +e.dataTransfer.getData('text/curio-dream'); if (id) await act('dream_to_goal', { id }, `It is a ${new Date().getFullYear()} goal now — set today`); } },
      h('h3', {}, `${yr} Goals`, h('span', { class: 'sp' }), seg([['list', 'List'], ['pics', 'Pictures']], d.view, (k) => act('goal_view', { view: k })),
        h('button', { class: 'btn sm', onclick: () => { IN.year--; draw(); } }, '‹'), h('button', { class: 'btn sm', onclick: () => { IN.year++; draw(); } }, '›'),
        h('button', { class: 'btn sm', onclick: () => goalForm({ kind: 'goal' }) }, '+ Goal')));
    if (d.view === 'pics' && gs.length) gcard.append(h('div', { class: 'gtiles' }, ...gs.map(g => h('div', { class: 'gtile' + (g.done_at ? ' done' : '') },
      h('div', { class: 'gpic', style: g.pic ? { backgroundImage: `url("${g.pic}")` } : { background: NOTE[g.id % NOTE.length] }, onclick: () => g.page_id ? openDoc(g.page_id, g.title) : goalForm(g) }, g.pic ? null : (g.title || '?')[0].toUpperCase()),
      h('div', { class: 'row', style: { gap: '6px', marginTop: '6px' } }, chk(!!g.done_at, 'var(--good)', (on) => act('goal_done', { id: g.id, on })), h('b', { class: 'grow', onclick: () => goalForm(g) }, g.title)),
      h('div', { class: 'faint' }, g.done_at ? 'Achieved ' + dt(g.done_at) : 'Added ' + dt(g.created))))));
    else gcard.append(...gs.map(g => h('div', { class: 'item' + (g.done_at ? ' done' : ''), onclick: () => goalForm(g) }, chk(!!g.done_at, 'var(--good)', (on) => act('goal_done', { id: g.id, on })),
      h('div', { class: 't' }, h('b', {}, g.title), g.why ? h('small', {}, g.why.length > 140 ? g.why.slice(0, 137) + '…' : g.why) : null,
        h('div', { class: 'row', style: { gap: '6px', marginTop: '4px', flexWrap: 'wrap' } }, g.created ? h('span', { class: 'pill', style: { '--c': 'var(--muted)' } }, 'Added ' + dt(g.created)) : null,
          g.done_at ? h('span', { class: 'pill', style: { '--c': 'var(--good)' } }, 'Achieved ' + dt(g.done_at)) : null)))));
    if (!gs.length) gcard.append(h('div', { class: 'empty' }, `What do you want to have done by the end of ${yr}? Drag a dream here (or tap → Goal) to start on it.`));
    const dcard = h('div', { class: 'card' }, h('h3', {}, 'Raw dreams', h('span', { class: 'sp' }), h('button', { class: 'btn sm', onclick: () => goalForm({ kind: 'dream' }) }, '+ Dream')),
      ...d.dreams.map((g, i) => h('div', { class: 'item', draggable: 'true', ondragstart: (e) => e.dataTransfer.setData('text/curio-dream', String(g.id)), onclick: () => goalForm(g) },
        h('b', {}, `${i + 1}.`), h('div', { class: 't' }, h('b', {}, g.title), g.why ? h('small', {}, g.why) : null),
        h('button', { class: 'btn sm', title: `Make it a ${new Date().getFullYear()} goal (set today)`, onclick: (e) => { e.stopPropagation(); act('dream_to_goal', { id: g.id }, 'It is a goal now — set today'); } }, '→ Goal'))),
      d.dreams.length ? h('div', { class: 'faint' }, `Drag a dream up into ${yr} Goals (or press → Goal) when you start on it.`) : h('div', { class: 'empty' }, 'Big wishes, no dates. Just what you want and why it matters.'));
    // the board of note cards
    const secs = d.sections; if (IN.sec && !secs.includes(IN.sec)) IN.sec = null;
    const notes = d.notes.filter(n => !IN.sec || n.section === IN.sec);
    const bar = h('div', { class: 'row wrapr', style: { margin: '6px 0 10px' } }, seg([[null, 'All'], ...secs.map(s => [s, s])], IN.sec, (k) => { IN.sec = k; draw(); }),
      IN.sec ? h('button', { class: 'btn sm soft', onclick: () => sectionMenu(IN.sec, secs) }, '⋯') : null, h('div', { class: 'grow' }),
      h('button', { class: 'btn primary sm', onclick: () => noteForm({ section: IN.sec || secs[0] }) }, '+ Quote / note'));
    const board = h('div', { class: 'masonry' }, ...notes.map(n => h('div', { class: 'note', style: { background: n.color || NOTE[n.id % NOTE.length] }, onclick: () => noteForm(n) },
      n.title ? h('b', {}, n.title) : null, n.text ? h('i', {}, n.text) : null,
      h('div', { class: 'nmeta' }, [IN.sec ? '' : n.section, dt(n.created)].filter(Boolean).join(' · '), n.page_id ? h('span', { class: 'pill', style: { '--c': 'var(--accent)' } }, 'Page') : null))));
    p.replaceChildren(h('div', { class: 'faint', style: { marginBottom: '8px' } }, 'Pictures and videos of your board stay on the PC; here you have your goals, dreams and note cards.'),
      h('div', { class: 'ins' }, h('div', {}, gcard, dcard), sparkCard(d.spark)), bar, notes.length ? board : h('div', { class: 'card empty' }, 'No note cards here yet.'));
  };
  function sparkCard(s) {
    const it = s.item; const left = s.left;
    const every = h('select', { class: 'inp sm', onchange: (e) => act('spark_hours', { hours: +e.target.value }) }, [1, 2, 3, 4, 6, 12, 24].map(k => h('option', { value: k, selected: k === s.hours }, k < 24 ? `every ${k} h` : 'once a day')));
    const head = h('div', { class: 'row', style: { gap: '8px', marginBottom: '8px' } }, h('span', { class: 'sec', style: { margin: 0 } }, 'TODAY’S SPARK'),
      h('span', { class: 'faint grow' }, '· new in ' + (left >= 3600 ? `${Math.floor(left / 3600)} h ${Math.floor(left % 3600 / 60)} min` : `${Math.max(1, Math.floor(left / 60))} min`)), every,
      h('button', { class: 'btn sm', onclick: () => act('spark_next', {}) }, 'Next ↻'));
    if (!it) return h('div', { class: 'card spark' }, head, h('div', { class: 'muted' }, 'Add goals, dreams or note cards — one of them shows here and changes every few hours.'));
    const isCard = it.spark === 'card'; const kind = isCard ? it.section : it.spark === 'goal' ? `${goalYear(it)} goal` : 'Dream';
    const line = (isCard ? it.text : it.why) || ''; const short = line.length > 220 ? line.slice(0, 217) + '…' : line;
    return h('div', { class: 'card spark' }, head, h('div', { class: 'sbody' },
      h('div', { class: 'stile', style: { background: NOTE[it.id % NOTE.length] } }, (it.title || '✦')[0].toUpperCase()),
      h('div', { class: 'grow' }, h('span', { class: 'pill', style: { '--c': 'var(--accent)' } }, kind), it.title ? h('div', { class: 'st' }, it.title) : null, short ? h('div', { class: 'sq' }, `“${short}”`) : null,
        it.created ? h('div', { class: 'faint' }, (isCard ? 'Added ' : 'Set on ') + dt(it.created)) : null,
        h('div', { class: 'row', style: { gap: '6px', marginTop: '8px', flexWrap: 'wrap' } }, it.page_id ? h('button', { class: 'btn sm', onclick: () => openDoc(it.page_id, it.title) }, 'Open page') : null,
          h('button', { class: 'btn sm soft', onclick: () => act(isCard ? 'card_spark' : 'goal_save', isCard ? { id: it.id, off: true } : { goal: { id: it.id, no_spark: 1 } }, 'It will not show in Spark') }, 'Don’t show in Spark')))));
  }
  function goalForm(g) {
    const dream = g.kind === 'dream'; const t = inp(g.title, dream ? 'A big wish' : 'e.g. iPhone 16 Pro'), why = inp(g.why, 'Why it matters');
    const added = inp((g.created || iso(new Date())).slice(0, 10), '', 'date'), got = inp((g.done_at || '').slice(0, 10), '', 'date');
    const body = h('div', {}, field(dream ? 'Dream' : 'Goal', t), field('Why it matters', why),
      dream ? null : h('div', { class: 'grid2' }, field('Added on', added), field('Achieved on (empty = not yet)', got)),
      g.id && !dream ? h('div', { class: 'faint', style: { marginTop: '8px' } }, 'Each goal has its own page in Docs › Inspo › Goals — add pictures and notes there.') : null);
    const keep = (old, v) => old && old.slice(0, 10) === v ? old : (v ? v + 'T12:00:00' : null);
    const btns = [['Save', 'primary', async () => {
      const v = { id: g.id, kind: g.kind || 'goal', title: t.value, why: why.value };
      if (!dream) { v.created = keep(g.created, added.value) || g.created; v.done_at = keep(g.done_at, got.value); }
      try { await api('goal_save', { goal: v }); toast('Saved'); draw(); } catch (e) { toast(e.message); return false; }
    }]];
    if (g.id) {
      btns.unshift(['Delete', 'danger', () => confirm(`Delete “${g.title}”? Its page in Docs stays (marked Removed).`) ? act('goal_delete', { id: g.id }, 'Deleted') : false]);
      if (g.page_id) btns.unshift(['Open page', '', () => { openDoc(g.page_id, g.title); }]);
      btns.unshift([g.no_spark ? 'Show in Spark' : 'Don’t show in Spark', 'soft', () => act('goal_save', { goal: { id: g.id, no_spark: g.no_spark ? 0 : 1 } }, 'Saved')]);
      if (dream) btns.unshift(['→ Goal', '', () => act('dream_to_goal', { id: g.id }, 'It is a goal now — set today')]);
    }
    sheet(g.id ? (dream ? 'Dream' : 'Goal') : dream ? 'New dream' : 'New goal', body, btns); setTimeout(() => t.focus(), 250);
  }
  function noteForm(n) {
    const t = inp(n.title, 'Title'), x = h('textarea', { class: 'inp', rows: 4, placeholder: 'A line, a quote, a reminder' }, n.text || '');
    const btns = [['Save', 'primary', () => act('note_save', { id: n.id, section: n.section, title: t.value, text: x.value, color: n.color || '' }, 'Saved')]];
    if (n.id) {
      btns.unshift(['Remove', 'danger', () => confirm('Remove this card from the board?') ? act('note_delete', { id: n.id }, 'Removed') : false]);
      btns.unshift([n.no_spark ? 'Show in Spark' : 'Don’t show in Spark', 'soft', () => act('card_spark', { id: n.id, off: !n.no_spark }, 'Saved')]);
      btns.unshift([n.page_id ? 'Open page' : 'Convert into page', '', async () => { try { const r = await api('card_page', { id: n.id }); openDoc(r.page_id, n.title || n.section); } catch (e) { toast(e.message); return false; } }]);
    }
    sheet(n.id ? 'Card' : 'New card', h('div', {}, field('Title', t), field('Text', x)), btns);
  }
  function sectionMenu(sec, secs) {
    const nm = inp(sec, 'Name'); const others = secs.filter(s => s !== sec);
    const to = h('select', { class: 'inp' }, others.map(s => h('option', { value: s }, s)));
    sheet(`Section “${sec}”`, h('div', {}, field('Rename', nm), others.length ? field('Delete it — its cards move to', to) : null),
      [...(others.length ? [['Delete section', 'danger', () => confirm(`Delete “${sec}”? Its cards are not deleted — they move to “${to.value}”.`) ? act('section_delete', { name: sec, move_to: to.value }, 'Deleted').then(() => { IN.sec = null; }) : false]] : []),
       ['Rename', 'primary', async () => { try { await api('section_rename', { old: sec, new: nm.value }); IN.sec = nm.value.trim(); draw(); } catch (e) { toast(e.message); return false; } }]]);
  }

  // ── Notes: sticky notes, sized by what is on them; your own categories (colour, rename, delete) ──
  const NT = { tag: null, q: '' };
  V.notes = async (p) => {
    const d = await api('notes', { tag: NT.tag, q: NT.q }); const col = Object.fromEntries(d.tags.map(t => [t.name, t.color]));
    if (NT.tag && !col[NT.tag]) NT.tag = null;
    const colorOf = (n) => n.color || (n.tags || []).map(t => col[t]).find(Boolean) || d.palette[0][1];
    const q = inp(NT.q, 'Search notes…'); q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { NT.q = q.value.trim(); draw(); } });
    const chips = h('div', { class: 'tagbar' }, h('button', { class: 'tg' + (NT.tag ? '' : ' on'), onclick: () => { NT.tag = null; draw(); } }, 'All'),
      ...d.tags.map(t => h('button', { class: 'tg' + (NT.tag === t.name ? ' on' : ''), onclick: () => { if (NT.tag === t.name) tagMenu(t, d.palette); else { NT.tag = t.name; draw(); } },
        oncontextmenu: (e) => { e.preventDefault(); tagMenu(t, d.palette); }, title: 'Tap again (or right-click) to rename, colour or delete' }, h('i', { style: { background: t.color } }), t.name)),
      h('button', { class: 'tg add', onclick: async () => { const n = prompt('New category (e.g. Business, Gym, Family):'); if (n && n.trim()) { await api('tag_add', { name: n }).catch(e => toast(e.message)); NT.tag = n.trim(); draw(); } } }, '+ Category'));
    // the first card: a new note
    let picked = NT.tag ? [NT.tag] : [];
    const ti = inp('', 'Title'), tx = h('textarea', { class: 'inp', rows: 3, placeholder: 'Something that hit you, an idea, a win…' });
    const catb = h('button', { class: 'btn sm soft' }); const showCat = () => { catb.textContent = picked.length ? '🏷 ' + picked.join(', ') : '🏷 Category ▾'; }; showCat();
    catb.onclick = () => { const box = h('div', { class: 'chips' }, ...d.tags.map(t => { const b = h('button', { class: picked.includes(t.name) ? 'on' : '', style: { '--c': t.color }, onclick: () => { picked = picked.includes(t.name) ? picked.filter(z => z !== t.name) : [...picked, t.name]; b.classList.toggle('on'); showCat(); } }, t.name); return b; }));
      sheet('Category', box, []); };
    const comp = h('div', { class: 'sticky new' }, h('b', {}, 'New note'), ti, tx, h('div', { class: 'row' }, catb, h('div', { class: 'grow' }),
      h('button', { class: 'btn sm primary', onclick: async () => { if (!ti.value.trim() && !tx.value.trim()) return; try { await api('notes_save', { note: { title: ti.value, content: tx.value, tags: picked } }); draw(); } catch (e) { toast(e.message); } } }, 'Save')));
    const ago = (s) => { if (!s) return ''; const k = Math.floor((new Date() - new Date(s)) / 864e5); return k <= 0 ? 'today' : k === 1 ? 'yesterday' : k < 30 ? `${k} days ago` : dt(s); };
    const tile = (n, mem) => h('div', { class: 'sticky', style: { background: colorOf(n) }, onclick: () => stickyForm(n, d) }, mem ? h('div', { class: 'mem' }, 'MEMORY OF THE DAY') : null,
      n.title ? h('b', {}, n.title) : null, n.content ? h('div', { class: 'tx' }, n.content.length > 700 ? n.content.slice(0, 700) + '…' : n.content) : null,
      h('div', { class: 'foot' }, ...(n.tags || []).slice(0, 3).map(t => h('span', {}, t)), h('div', { class: 'grow' }), n.pinned ? '📌' : null, h('small', {}, ago(n.created))));
    const list = d.notes.filter(n => !(d.memory && n.id === d.memory.id && !NT.tag && !NT.q));
    p.replaceChildren(h('div', { class: 'row wrapr', style: { marginBottom: '10px' } }, chips, h('div', { class: 'grow' }), h('div', { style: { width: '220px' } }, q)),
      h('div', { class: 'masonry' }, comp, d.memory && !NT.tag && !NT.q ? tile(d.memory, true) : null, ...list.map(n => tile(n))),
      ...(d.notes.length ? [] : [h('div', { class: 'empty' }, NT.q ? 'Nothing found.' : 'No notes here yet — write one in the first card.')]));
  };
  function stickyForm(n, d) {
    const t = inp(n.title, 'Title'), x = h('textarea', { class: 'inp', rows: 6 }, n.content || ''); let tags = (n.tags || []).slice(), color = n.color || '';
    const tg = h('div', { class: 'chips' }, ...d.tags.map(c => { const b = h('button', { class: tags.includes(c.name) ? 'on' : '', style: { '--c': c.color }, onclick: () => { tags = tags.includes(c.name) ? tags.filter(z => z !== c.name) : [...tags, c.name]; b.classList.toggle('on'); } }, c.name); return b; }));
    const sw = h('div', { class: 'swatches' }, h('button', { class: color ? '' : 'on', title: 'Same as its category', style: { background: 'linear-gradient(135deg,#fff6b3,#dcecff)' }, onclick: (e) => { color = ''; mark(e); } }),
      ...d.palette.map(([nm, c]) => h('button', { class: color === c ? 'on' : '', title: nm, style: { background: c }, onclick: (e) => { color = c; mark(e); } })));
    function mark(e) { sw.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === e.currentTarget)); }
    const pin = h('input', { type: 'checkbox', checked: !!n.pinned }), res = h('input', { type: 'checkbox', checked: n.resurface !== 0 });
    sheet('Note', h('div', {}, field('Title', t), field('Note', x), field('Category', tg), field('Colour', sw),
      h('label', { class: 'item' }, pin, h('span', {}, 'Pin to the top')), h('label', { class: 'item' }, res, h('span', {}, 'Bring it back to me as a “Memory of the day”'))),
      [['Delete', 'danger', () => confirm('Delete this note for good?') ? act('notes_delete', { id: n.id }, 'Deleted') : false],
       ['Archive', 'soft', () => act('notes_archive', { id: n.id }, 'Archived')],
       ['Save', 'primary', () => act('notes_save', { note: { id: n.id, title: t.value, content: x.value, tags, color, pinned: pin.checked ? 1 : 0, resurface: res.checked ? 1 : 0 } }, 'Saved')]]);
  }
  function tagMenu(t, palette) {
    const nm = inp(t.name, 'Name'); let color = t.color;
    const sw = h('div', { class: 'swatches' }, ...palette.map(([n, c]) => h('button', { class: c === color ? 'on' : '', title: n, style: { background: c }, onclick: (e) => { color = c; sw.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === e.currentTarget)); } })));
    sheet(`Category “${t.name}”`, h('div', {}, field('Name', nm), field('Colour of its notes', sw)),
      [['Delete', 'danger', () => confirm(`Delete “${t.name}”? Its notes stay — they just lose this label.`) ? act('tag_delete', { name: t.name }, 'Deleted').then(() => { NT.tag = null; }) : false],
       ['Save', 'primary', async () => { try { if (nm.value.trim() !== t.name) { await api('tag_rename', { old: t.name, new: nm.value }); NT.tag = nm.value.trim(); }
         await api('tag_color', { name: nm.value.trim() || t.name, color }); draw(); } catch (e) { toast(e.message); return false; } }]]);
  }

  // ── Phone: reminders on this phone ──
  V.phone = async (p) => {
    const st = h('div', { class: 'muted' }, 'Checking…'); const supported = 'serviceWorker' in navigator && 'PushManager' in window;
    const on = h('button', { class: 'btn primary', onclick: enable }, 'Turn on reminders on this phone');
    const test = h('button', { class: 'btn', onclick: async () => { try { const r = await post('/api/tracker/push', { op: 'test' }); toast(r.sent ? 'Sent — it should pop up' : 'No phone is connected yet'); } catch (e) { toast(e.message); } } }, 'Send a test');
    const url = h('code', { style: { display: 'block', wordBreak: 'break-all', padding: '10px', background: 'var(--card2)', borderRadius: '10px', userSelect: 'all' } }, '…');
    post('/api/tracker/push', { op: 'tick_url' }).then(r => url.textContent = r.url).catch(e => url.textContent = e.message);
    async function state() {
      if (!supported) { st.textContent = 'This browser cannot get reminders. On iPhone: Share › Add to Home Screen, then open Curio from the home screen. On Android: use Chrome.'; return; }
      const reg = await navigator.serviceWorker.getRegistration('/'); const sub = reg && await reg.pushManager.getSubscription();
      st.textContent = sub ? 'Reminders are ON on this phone.' : (Notification.permission === 'denied' ? 'Notifications are blocked for Curio — allow them in the browser settings.' : 'Reminders are off on this phone.');
    }
    async function enable() {
      try {
        const perm = await Notification.requestPermission(); if (perm !== 'granted') { toast('Notifications were not allowed'); return; }
        const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' }); await navigator.serviceWorker.ready;
        const { key } = await post('/api/tracker/push', { op: 'key' });
        const raw = Uint8Array.from(atob(key.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((key.length + 3) % 4)), c => c.charCodeAt(0));
        const sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: raw });
        await post('/api/tracker/push', { op: 'subscribe', args: { sub: sub.toJSON(), name: navigator.userAgent.includes('Android') ? 'Android phone' : navigator.userAgent.includes('iPhone') ? 'iPhone' : 'Browser' } });
        toast('Reminders are on'); state();
      } catch (e) { toast(e.message); }
    }
    state();
    // 10.43: is the free reminder service (cron-job.org) really calling Curio every minute?
    const svc = h('div', { class: 'muted' }, 'Checking…');
    post('/api/tracker/push', { op: 'status' }).then(r => {
      const ago = r.ago == null ? null : Math.round(r.ago / 60);
      svc.replaceChildren(h('div', { style: { color: ago != null && ago <= 3 ? 'var(--good)' : 'var(--bad)', fontWeight: 700 } },
        ago == null ? '✗ The reminder service has never called Curio — reminders cannot come yet. Do step 2 below.' : ago <= 3 ? `✓ Working — the reminder service called ${ago <= 1 ? 'just now' : ago + ' min ago'}.` : `✗ Not working — the last call was ${ago < 120 ? ago + ' min' : Math.round(ago / 60) + ' h'} ago. Check the job on cron-job.org.`),
        h('div', { class: 'faint' }, `Phones with reminders on: ${r.phones}` + (r.kinds.length ? ` (${r.kinds.join(', ')})` : '')));
    }).catch(e => { svc.textContent = e.message; });
    const file = h('input', { type: 'file', accept: '.db', class: 'inp' }); const rep = h('input', { type: 'checkbox' }); const imp = h('div', { class: 'muted' });
    const go = h('button', { class: 'btn', onclick: async () => {
      const f = file.files[0]; if (!f) { toast('Pick myday.db first'); return; }
      if (rep.checked && !confirm('Replace everything Tracker has on the web with the desktop copy?')) return;
      go.disabled = true; imp.textContent = 'Copying…';
      try {
        const b64 = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1]); r.onerror = no; r.readAsDataURL(f); });
        const n = await post('/api/tracker/import', { file: b64, replace: rep.checked });
        imp.textContent = `Copied: ${n.tasks || 0} tasks, ${n.habits || 0} check-ins / habits, ${n.habit_log || 0} ticks, ${n.sleep || 0} nights, ${n.quit_events || 0} NoFap events.`; toast('Copied');
      } catch (e) { imp.textContent = e.message; }
      go.disabled = false;
    } }, 'Copy it to the web');
    p.replaceChildren(h('div', { class: 'card' }, h('h3', {}, 'Copy your desktop Tracker here (one time)'),
        h('p', { class: 'muted' }, 'On the PC: Tracker › Review › “Open the data folder” — the file is myday.db. Pick it here. (Your screen record stays on the PC.)'),
        file, h('label', { class: 'item' }, rep, h('span', {}, 'Replace what is on the web')), h('div', { class: 'row' }, go), imp),
      h('div', { class: 'card' }, h('h3', {}, 'Is the reminder service working?'), svc),
      h('div', { class: 'card' }, h('h3', {}, 'Reminders on this phone'), st, h('div', { class: 'row', style: { marginTop: '10px', flexWrap: 'wrap' } }, on, test),
      h('p', { class: 'faint' }, 'First add Curio to your home screen (browser menu › Add to Home screen) and open it from there.')),
      h('div', { class: 'card' }, h('h3', {}, 'The every-minute check (one time setup)'),
        h('p', { class: 'muted' }, 'Reminders go out when this address is opened. Your Cloudflare Worker “curio-files” opens it every minute:'), url,
        h('ol', { class: 'muted' }, h('li', {}, 'Copy the address above.'), h('li', {}, 'Cloudflare › Workers & Pages › curio-files › Settings › Variables and secrets › + Add variable.'),
          h('li', {}, 'Key: TICK_URL · Value: paste the address · tick “Secret” → Add variable and deploy.'), h('li', {}, 'Within a minute this page says ✓ Working. (An older cron-job.org job can then be paused.)')),
        h('p', { class: 'faint' }, 'Keep this address private — it only lets someone trigger your reminders, nothing else.')));
  };

  addEventListener('hashchange', () => { const k = location.hash.slice(1); if (k && k !== cur && TABS.some(t => t[0] === k)) { cur = k; nav(); draw(); } });
  nav(); draw();
  document.addEventListener('visibilitychange', () => { if (!document.hidden) draw(); });
})();
