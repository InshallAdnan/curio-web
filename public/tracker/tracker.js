/* Curio Tracker on the web — the same book as the desktop's Tracker: Home, Tasks, Check-ins, Habits, Sleep, NoFap, Nudges, Inspo,
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
  const TABS = [['home', 'Home'], ['tasks', 'Tasks'], ['checkins', 'Check-ins'], ['habits', 'Habits'], ['sleep', 'Sleep'], ['quit', 'NoFap'], ['nudges', 'Nudges'], ['inspo', 'Inspo'], ['phone', 'Setup']];
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
    for (const q of d.quit) mini.append(h('div', { class: 'card' }, h('h3', {}, q.name), h('div', { class: 'row' }, h('div', { class: 'big' }, q.days), h('div', { class: 'muted' }, 'days clean', h('br'), `best ${q.best}`)),
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
    // this week
    const wk = h('div', { class: 'week' }); const today = iso(new Date());
    for (const [day, list] of Object.entries(d.week)) {
      const dd = new Date(day + 'T00:00');
      wk.append(h('div', { class: 'day' + (day === today ? ' today' : '') }, h('div', { class: 'd' }, dd.toLocaleDateString('en-GB', { weekday: 'short' }) + ' ' + dd.getDate()),
        ...list.map(x => h('div', { class: 'chip' + (x.done ? ' x' : ''), style: { '--c': x.color || '#888' }, title: x.title }, x.title))));
    }
    els.push(h('div', { class: 'card' }, h('h3', {}, 'This week'), wk));
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

  // ── Tasks ──
  let AREAS = [];
  V.tasks = async (p) => {
    const d = await api('tasks'); AREAS = d.areas;
    const row = (x, showDay) => h('div', { class: 'item' + (x.done ? ' done' : ''), onclick: () => taskForm(x) }, chk(x.done, x.color, (on) => act('task_done', { id: x.id, on }, on ? 'Done' : 'Opened again')),
      h('div', { class: 't' }, h('b', {}, x.title), h('small', {}, [x.area, showDay && x.day ? dayLab(x.day) : '', x.time ? t12(x.time) + ' – ' + t12(endOf(x)) : '', x.repeat ? '↻ ' + x.repeat : ''].filter(Boolean).join('  ·  '))));
    const els = [h('div', { class: 'row', style: { marginBottom: '10px' } }, h('div', { class: 'grow' }), h('button', { class: 'btn', onclick: boardsForm }, 'Boards'), h('button', { class: 'btn primary', onclick: () => taskForm({ day: iso(new Date()) }) }, '+ Task'))];
    for (const [k, t] of [['overdue', 'Overdue'], ['today', 'Today'], ['upcoming', 'Upcoming'], ['someday', 'No date']]) {
      if (!d[k].length && k !== 'today') continue;
      els.push(h('div', { class: 'card' }, h('h3', {}, t, h('span', { class: 'muted' }, d[k].length || '')), ...(d[k].length ? d[k].map(x => row(x, k !== 'today')) : [h('div', { class: 'empty' }, 'Nothing for today.')])));
    }
    els.push(h('div', { class: 'row', style: { margin: '-4px 0 10px' } }, h('div', { class: 'grow' }), h('button', { class: 'btn sm', onclick: () => repForm() }, '+ Repeating task')));
    if (d.repeating.length) els.push(h('div', { class: 'card' }, h('h3', {}, 'Repeating'), ...d.repeating.map(x => h('div', { class: 'item' }, h('div', { class: 't' }, h('b', {}, x.title), h('small', {}, `${x.rule} · done ${x.done}×` + (x.next ? ' · next ' + dayLab(x.next) : ''))),
      h('span', { class: 'pill', style: { '--c': x.state === 'running' ? 'var(--good)' : x.state === 'ending' ? 'var(--poor)' : 'var(--bad)' } }, x.state),
      x.state === 'running' || x.state === 'ending' ? h('button', { class: 'btn sm', onclick: () => confirm(`Stop “${x.title}”? Its history stays.`) && act('stop_series', { id: x.id }, 'Stopped') }, 'Stop')
        : h('button', { class: 'btn sm', onclick: () => act('restart_series', { id: x.id }, 'Restarted') }, 'Restart')))));
    if (d.done.length) els.push(h('div', { class: 'card' }, h('h3', {}, 'Done lately'), ...d.done.slice(0, 10).map(x => row(x, true))));
    p.replaceChildren(...els);
  };
  // boards: add, rename, delete (its tasks / check-ins move to the board you pick — nothing is deleted)
  async function boardsForm() {
    const list = h('div', {});
    const fill = async () => {
      const bs = await api('areas');
      list.replaceChildren(...bs.map(b => h('div', { class: 'item' }, h('span', { class: 'dotc', style: { '--c': b.color } }),
        h('div', { class: 't' }, h('b', {}, b.name), h('small', {}, `${b.tasks} task${b.tasks === 1 ? '' : 's'} · ${b.habits} check-in / habit${b.habits === 1 ? '' : 's'}`)),
        h('button', { class: 'btn sm soft', onclick: async () => { const n = prompt('New name for the board:', b.name); if (n && n.trim()) { await api('area_save', { id: b.id, name: n }).catch(e => toast(e.message)); AREAS = []; fill(); draw(); } } }, 'Rename'),
        h('button', { class: 'btn sm danger', onclick: () => delBoard(b, bs, fill) }, 'Delete'))),
        h('div', { class: 'row', style: { marginTop: '10px' } }, (() => { const nb = inp('', 'New board name'); const add = h('button', { class: 'btn sm primary', onclick: async () => { if (!nb.value.trim()) return; await api('area_save', { name: nb.value }).catch(e => toast(e.message)); AREAS = []; fill(); draw(); } }, '+ Add');
          return [nb, add]; })()));
    };
    await fill(); sheet('Boards', list, []);
  }
  function delBoard(b, bs, after) {
    const others = bs.filter(x => x.id !== b.id); const n = b.tasks + b.habits;
    const to = h('select', { class: 'inp' }, others.map(x => h('option', { value: x.id }, x.name)), h('option', { value: '' }, 'No board'));
    sheet(`Delete “${b.name}”?`, h('div', {}, n ? h('p', { class: 'muted' }, `It has ${b.tasks} task(s) (done ones too) and ${b.habits} check-in / habit(s). They are not deleted — they move to:`) : h('p', { class: 'muted' }, 'It is empty — nothing else changes.'),
      n ? to : null), [['Delete board', 'danger', async () => { await api('area_delete', { id: b.id, move_to: n ? to.value || null : null }).catch(e => toast(e.message)); toast('Board deleted'); AREAS = []; draw(); }]]);
    void after;
  }
  const rng = (x) => x.time ? t12(x.time) + (x.etime ? ' – ' + t12(x.etime) : '') : '';
  const endOf = (x) => { if (!x.time) return ''; const [a, b] = x.time.split(':').map(Number); const e = a * 60 + b + (x.minutes || 30); return `${pad(Math.floor(e / 60) % 24)}:${pad(e % 60)}`; };
  async function repForm() {
    if (!AREAS.length) AREAS = (await api('tasks')).areas;
    const title = inp('', 'e.g. Hair oiling'); let area = (AREAS[0] || {}).id; let days = [new Date().getDay() === 0 ? 6 : new Date().getDay() - 1];
    const chips = h('div', { class: 'chips' }, AREAS.map(a => { const b = h('button', { class: a.id === area ? 'on' : '', style: { '--c': a.color }, onclick: () => { area = a.id; chips.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === b)); } }, a.name); return b; }));
    const every = h('select', { class: 'inp' }, [['day', 'Every day'], ['weekdays', 'Weekdays'], ['week', 'Every week on…'], ['month', 'Every month']].map(([k, t]) => h('option', { value: k }, t)));
    const dchips = h('div', { class: 'chips' }, DOW.map((t, i) => { const b = h('button', { class: days.includes(i) ? 'on' : '', onclick: () => { days = days.includes(i) ? days.filter(z => z !== i) : [...days, i]; b.classList.toggle('on'); } }, t); return b; }));
    const st = inp('', '', 'time'), en = inp('', '', 'time'), start = inp(iso(new Date()), '', 'date'), end = inp('', '', 'date');
    sheet('New repeating task', h('div', {}, field('Task', title), field('Board', chips), field('Repeat', every), field('On (for “every week”)', dchips), field('Starts', start),
      h('div', { class: 'grid2' }, field('From', st), field('To', en)), field('Ends (empty = keeps repeating)', end)),
      [['Save', 'primary', async () => {
        const k = every.value; const rep = k === 'day' ? { every: 'day', n: 1 } : k === 'weekdays' ? { every: 'week', n: 1, days: [0, 1, 2, 3, 4] } : k === 'week' ? { every: 'week', n: 1, days: days.sort() } : { every: 'month', n: 1 };
        let m = 30; if (st.value && en.value) { const [a, b] = st.value.split(':').map(Number), [c, e] = en.value.split(':').map(Number); m = (c * 60 + e) - (a * 60 + b); if (m <= 0) m += 1440; }
        try { await api('task_save', { task: { title: title.value, area_id: area, day: start.value, time: st.value || null, minutes: m, repeat: rep, repeat_end: end.value || null, remind: st.value ? 10 : -1 } }); toast('Saved'); draw(); }
        catch (e) { toast(e.message); return false; }
      }]]);
  }
  async function taskForm(x) {
    if (!AREAS.length) AREAS = (await api('tasks')).areas;
    const title = inp(x.title, 'What needs doing?'); let area = x.area_id || (AREAS[0] || {}).id;
    const chips = h('div', { class: 'chips' }, AREAS.map(a => { const b = h('button', { class: a.id === area ? 'on' : '', style: { '--c': a.color }, onclick: () => { area = a.id; chips.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === b)); } }, a.name); return b; }));
    const day = inp(x.day || '', '', 'date'), st = inp(x.time || '', '', 'time'), en = inp(x.time ? endOf(x) : '', '', 'time');
    const note = h('textarea', { class: 'inp', rows: 3, placeholder: 'Notes (optional)' }, x.note || '');
    const body = h('div', {}, field('Task', title), field('Board', chips), h('div', { class: 'grid2' }, field('Day', day), h('div', {})),
      h('div', { class: 'grid2' }, field('Starts', st), field('Ends', en)), h('div', { class: 'faint' }, 'Leave the times empty for an all-day task. The length is worked out from start → end.'), field('Notes', note));
    const btns = [['Save', 'primary', async () => {
      let m = x.minutes || 30;
      if (st.value && en.value) { const [a, b] = st.value.split(':').map(Number), [c, e] = en.value.split(':').map(Number); m = (c * 60 + e) - (a * 60 + b); if (m <= 0) m += 1440; }
      try { await api('task_save', { task: { id: x.id, title: title.value, area_id: area, day: day.value || null, time: day.value && st.value ? st.value : null, minutes: m, note: note.value, remind: st.value ? 10 : -1 } }); toast('Saved'); draw(); }
      catch (e) { toast(e.message); return false; }
    }]];
    if (x.id) btns.unshift(['Delete', 'danger', async () => { if (!confirm(x.repeat ? 'Delete this day? It is a repeating task — only this day goes, the repeat goes on.' : 'Delete this task?')) return false; await act('task_delete', { id: x.id }, 'Deleted'); }]);
    if (x.id && x.done_at) body.prepend(h('div', { class: 'pill', style: { '--c': 'var(--good)', marginBottom: '6px' } }, 'Done ✓ ' + t12(x.done_at.slice(11, 16)) + (x.done_at.slice(0, 10) !== x.day ? ' · ' + dayLab(x.done_at.slice(0, 10)) : '')));
    sheet(x.id ? 'Edit task' : 'New task', body, btns); setTimeout(() => title.focus(), 250);
  }

  // ── Check-ins and Habits ──
  async function habitsView(p, routine) {
    const d = await api('checkins'); const els = [];
    const groups = routine ? [...d.order.filter(k => d.groups[k]), ...Object.keys(d.groups).filter(k => k && !d.order.includes(k))] : [''];
    for (const g of groups) {
      const items = d.groups[g] || []; const c = d.colors[g] || 'var(--accent)';
      if (!routine && !items.length) { els.push(h('div', { class: 'card' }, h('div', { class: 'empty' }, 'No habits yet.'), h('button', { class: 'btn primary', onclick: () => habitForm({ routine: '' }, d) }, '+ Habit'))); continue; }
      els.push(h('div', { class: 'card' }, h('h3', { style: { color: c } }, g || 'Habits', h('span', { class: 'sp' }), h('span', { class: 'muted', style: { fontSize: '13px' } }, `${items.filter(x => x.state === 'done').length}/${items.filter(x => x.due).length} today`),
          h('button', { class: 'btn sm', onclick: () => habitForm({ routine: g }, d) }, '+')),
        ...items.map(x => h('div', { class: 'item' + (x.state === 'done' ? ' done' : '') + (x.late ? ' lateit' : ''), onclick: () => habitForm(x, d) }, chk(x.state === 'done', c, (on) => act('habit_log', { id: x.id, state: on ? 'done' : null })),
          h('div', { class: 't' }, h('b', {}, x.name), h('small', {}, [rng(x), x.late ? 'time passed — not done' : '', x.streak ? `${x.streak} day streak` : ''].filter(Boolean).join('  ·  '))),
          h('div', { class: 'dots' }, x.week.map(([day, s]) => h('div', { class: 'dot ' + (s === 'today' && x.late ? 'missed' : s), style: { '--c': c }, title: `${dayLab(day)}: ` + ({ done: 'done', missed: 'missed', skip: 'skipped', today: x.late ? 'time passed — not ticked' : 'not ticked yet', off: 'not planned' }[s] || '') })))))));
    }
    if (d.changes.length) els.push(h('div', { class: 'card' }, h('h3', {}, 'Changes'), ...d.changes.map(x => h('div', { class: 'item' }, h('span', { class: 'pill', style: { '--c': x.color } }, x.what),
      h('div', { class: 't' }, h('b', {}, x.name), h('small', {}, `${dayLab(x.day)} · ${x.detail}`))))));
    if (routine) els.unshift(h('div', { class: 'row', style: { marginBottom: '10px' } }, h('div', { class: 'grow muted' }, 'Tap an item to change or stop it.'), h('button', { class: 'btn primary', onclick: () => habitForm({ routine: 'Morning' }, d) }, '+ Item')));
    const st = (d.stopped || []).filter(x => routine ? x.routine : !x.routine);
    if (st.length) els.push(h('div', { class: 'card' }, h('h3', {}, routine ? 'Removed items' : 'Stopped habits'), ...st.map(x => h('div', { class: 'item' }, h('div', { class: 't' }, h('b', {}, x.name), h('small', {}, x.last ? 'stopped ' + dayLab(x.last) : '')),
      h('button', { class: 'btn sm', onclick: () => act('habit_restart', { id: x.id }, 'Back from today') }, 'Restart')))));
    p.replaceChildren(...els);
  }
  const DOW = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  async function habitForm(x, d) {
    if (!AREAS.length) AREAS = (await api('tasks')).areas;
    const isRt = x.routine !== '' && x.routine != null;
    const name = inp(x.name, isRt ? 'e.g. Fajr, Skincare, Check Gmail' : 'e.g. Read 20 pages');
    const rt = h('select', { class: 'inp' }, [...new Set([...(d.order || []), ...(x.routine ? [x.routine] : [])])].map(r => h('option', { value: r, selected: r === x.routine }, r)));
    let days = (x.days && x.days.length ? x.days : [0, 1, 2, 3, 4, 5, 6]).slice();
    const dchips = h('div', { class: 'chips' }, DOW.map((t, i) => { const b = h('button', { class: days.includes(i) ? 'on' : '', onclick: () => { days = days.includes(i) ? days.filter(z => z !== i) : [...days, i]; b.classList.toggle('on'); } }, t); return b; }));
    const tm = inp(x.time || '', '', 'time'), tme = inp(x.etime || '', '', 'time'); const rem = h('input', { type: 'checkbox', checked: x.id ? (x.remind ?? -1) >= 0 : true });
    let area = x.area_id || (AREAS[0] || {}).id;
    const chips = h('div', { class: 'chips' }, AREAS.map(a => { const b = h('button', { class: a.id === area ? 'on' : '', style: { '--c': a.color }, onclick: () => { area = a.id; chips.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === b)); } }, a.name); return b; }));
    const from = inp(iso(new Date()), '', 'date');
    const body = h('div', {}, field('Name', name), isRt ? field('Check-in', rt) : null, field('Days', dchips), h('div', { class: 'grid2' }, field('Starts', tm), field('Ends (optional)', tme)), h('label', { class: 'item' }, rem, h('span', {}, 'Remind me at the start time (phone and PC)')),
      field('Board', chips), x.id ? field('Changes start on (earlier days keep the old plan and times)', from) : null,
      x.history && x.history.length ? h('div', { class: 'faint', style: { marginTop: '8px' } }, h('b', {}, 'Plan history'), ...x.history.map(l => h('div', {}, l))) : null);
    const btns = [['Save', 'primary', async () => {
      try { await api('habit_save', { habit: { id: x.id, name: name.value, routine: isRt ? rt.value : '', days: days.sort(), time: tm.value || null, etime: tm.value && tme.value ? tme.value : null, remind: rem.checked && tm.value ? 0 : -1, area_id: area, kind: 'build' }, from_day: x.id ? from.value : null }); toast('Saved'); draw(); }
      catch (e) { toast(e.message); return false; }
    }]];
    if (x.id) btns.unshift(['Stop it', 'danger', () => confirm(`Stop “${x.name}” from today? Its history stays.`) ? act('habit_end', { id: x.id }, 'Stopped') : false]);
    sheet(x.id ? 'Edit' : isRt ? 'New check-in item' : 'New habit', body, btns);
  }
  V.checkins = (p) => habitsView(p, true);
  V.habits = (p) => habitsView(p, false);

  // ── Sleep ──
  let SL = { mode: 'week', off: 0 };
  V.sleep = async (p) => {
    const d = await api('sleep', SL);
    const seg = h('div', { class: 'seg' }, [['week', 'Week'], ['month', 'Month'], ['30', '30 days']].map(([k, t]) => h('button', { class: SL.mode === k ? 'on' : '', onclick: () => { SL = { mode: k, off: 0 }; draw(); } }, t)));
    const grid = h('div', { class: 'nights' });
    for (let dt = new Date(d.start + 'T00:00'); dt <= new Date(d.end + 'T00:00'); dt.setDate(dt.getDate() + 1)) {
      const k = iso(dt), r = d.nights[k]; const lab = dt.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
      grid.append(h('div', { class: 'night' + (r ? ' has' : ''), style: r ? { '--c': r.color } : {}, onclick: () => sleepForm(k, r, d) }, h('div', { class: 'faint' }, lab),
        r ? h('div', { class: 'h' }, hm(r.minutes)) : h('div', { class: 'faint' }, 'not logged'), r ? h('div', { class: 'faint' }, `${t12(r.bed.slice(11, 16))} → ${t12(r.wake.slice(11, 16))}`) : null));
    }
    p.replaceChildren(h('div', { class: 'card' }, h('h3', {}, `Every night ${t12(d.bed)} → ${t12(d.wake)}`), h('div', { class: 'muted' }, d.auto ? 'Each night fills in by itself on the desktop. If a night was different, tap it.' : 'Tap a night to log it.'),
      h('div', { class: 'row', style: { marginTop: '10px' } }, h('button', { class: 'btn sm', onclick: () => usualForm(d) }, 'Change usual times'))),
      h('div', { class: 'row', style: { margin: '6px 0 10px' } }, seg, h('div', { class: 'grow' }), h('button', { class: 'btn sm', onclick: () => { SL.off--; draw(); } }, '‹'), h('button', { class: 'btn sm', disabled: SL.off >= 0, onclick: () => { SL.off++; draw(); } }, '›')),
      grid, h('div', { class: 'row faint', style: { marginTop: '10px' } }, h('span', { style: { color: 'var(--good)' } }, '● Good'), h('span', { style: { color: 'var(--poor)' } }, '● Poor'), h('span', { style: { color: 'var(--bad)' } }, '● Bad')));
  };
  function sleepForm(night, r, d) {
    const b = inp(r ? r.bed.slice(11, 16) : d.bed, '', 'time'), w = inp(r ? r.wake.slice(11, 16) : d.wake, '', 'time');
    const btns = [['Save', 'primary', () => act('sleep_save', { night, bed: b.value, wake: w.value, id: r && r.id }, 'Saved')]];
    if (r) btns.unshift(['Delete', 'danger', () => confirm('Delete this night?') ? act('sleep_delete', { id: r.id }, 'Deleted') : false]);
    sheet(`Night of ${dayLab(night)}`, h('div', { class: 'grid2' }, field('In bed', b), field('Woke up', w)), btns);
  }
  function usualForm(d) {
    const b = inp(d.bed, '', 'time'), w = inp(d.wake, '', 'time'), g = inp(d.goal, '', 'number');
    sheet('Usual sleep', h('div', {}, h('div', { class: 'grid2' }, field('In bed', b), field('Up', w)), field('A good night = minutes of sleep', g)),
      [['Save', 'primary', () => act('sleep_usual', { bed: b.value, wake: w.value, goal: g.value }, 'Saved')]]);
  }

  // ── NoFap ──
  V.quit = async (p) => {
    const qs = await api('quit'); const els = [h('div', { class: 'row', style: { marginBottom: '10px' } }, h('div', { class: 'grow' }), h('button', { class: 'btn', onclick: () => quitForm({}) }, '+ Something to quit'))];
    if (!qs.length) els.push(h('div', { class: 'card empty' }, 'Nothing here yet.'));
    for (const q of qs) {
      els.push(h('div', { class: 'card' }, h('h3', {}, q.name, h('span', { class: 'sp' }), h('button', { class: 'btn sm', onclick: () => quitForm(q) }, 'Edit')), h('div', { class: 'row' }, h('div', { class: 'big', style: { fontSize: '46px' } }, q.days), h('div', { class: 'muted' }, `days clean + ${q.hours} h`, h('br'), `best ${q.best} · ${q.beaten} urges beaten · ${q.relapses} slips`)),
        h('div', { class: 'row', style: { marginTop: '10px', flexWrap: 'wrap' } }, h('button', { class: 'btn primary', style: { flex: 1 }, onclick: () => struggle(q.id, q) }, 'I’m struggling'),
          h('button', { class: 'btn', onclick: () => urgeForm(q.id) }, 'Log urge'), h('button', { class: 'btn', onclick: () => slipped(q.id, q.name) }, 'I slipped'))));
      if (q.why) els.push(h('div', { class: 'card' }, h('h3', {}, 'Why I’m doing this'), ...q.why.split('\n').filter(Boolean).map(l => h('div', {}, '•  ' + l))));
      els.push(h('div', { class: 'card' }, h('h3', {}, 'Every streak'), ...q.streaks.map(s => h('div', { class: 'item' }, h('div', { class: 't' }, h('b', {}, `${s.days} days`), h('small', {}, `${s.start.slice(0, 10)} – ${s.current ? 'now' : s.end.slice(0, 10)}`)), s.current ? h('span', { class: 'pill', style: { '--c': 'var(--good)' } }, 'now') : null))));
    }
    p.replaceChildren(...els);
  };
  function quitForm(q) {
    const name = inp(q.name, 'e.g. NoFap, Smoking'); const why = h('textarea', { class: 'inp', rows: 4, placeholder: 'Why you are doing this — one reason per line' }, q.why || '');
    const since = inp(q.id ? String(q.since || '').slice(0, 10) : iso(new Date()), '', 'date');
    sheet(q.id ? 'Edit' : 'Something to quit', h('div', {}, field('Name', name), field('My reasons', why), q.id ? null : field('Clean since', since)),
      [['Save', 'primary', () => act('quit_save', { id: q.id, name: name.value, why: why.value, start_day: q.id ? undefined : since.value }, 'Saved')]]);
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

  // ── Inspo (goals, dreams, notes) ──
  const NOTE = ['#fff1b8', '#ffd8e4', '#d6ecff', '#d9f5e3', '#e9defc', '#ffe3cc'];
  V.inspo = async (p) => {
    const d = await api('inspo'); const yr = new Date().getFullYear();
    p.replaceChildren(h('div', { class: 'card' }, h('h3', {}, 'Goals'), ...d.goals.map(g => h('div', { class: 'item' + (g.done_at ? ' done' : '') }, chk(!!g.done_at, 'var(--good)', (on) => act('goal_done', { id: g.id, on })),
        h('div', { class: 't' }, h('b', {}, g.title), h('small', {}, [g.why, g.due ? 'by ' + g.due : ''].filter(Boolean).join(' · '))))),
      h('button', { class: 'btn sm', style: { marginTop: '8px' }, onclick: () => { const t = inp('', 'Goal'); sheet('New goal', field('Goal', t), [['Save', 'primary', () => act('goal_save', { goal: { kind: 'goal', title: t.value, due: `${yr}-12-31` } }, 'Saved')]]); } }, '+ Goal')),
      d.dreams.length ? h('div', { class: 'card' }, h('h3', {}, 'Raw dreams'), ...d.dreams.map((g, i) => h('div', { class: 'item' }, h('b', {}, `${i + 1}.`), h('div', { class: 't' }, g.title)))) : null,
      h('div', { class: 'card' }, h('h3', {}, 'Notes', h('span', { class: 'sp' }), h('button', { class: 'btn sm', onclick: () => noteForm({}) }, '+ Note')),
        h('div', { class: 'grid2' }, ...d.notes.map(n => h('div', { class: 'note', style: { background: n.color || NOTE[n.id % NOTE.length] }, onclick: () => noteForm(n) }, n.title ? h('b', {}, n.title) : null, h('i', {}, n.text))))));
  };
  function noteForm(n) {
    const t = inp(n.title, 'Title'), x = h('textarea', { class: 'inp', rows: 4, placeholder: 'A line, a quote, a reminder' }, n.text || '');
    sheet(n.id ? 'Edit note' : 'New note', h('div', {}, field('Title', t), field('Text', x)), [['Save', 'primary', () => act('note_save', { id: n.id, title: t.value, text: x.value, color: n.color || '' }, 'Saved')]]);
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
        h('p', { class: 'muted' }, 'On the PC: Tracker › Plan › “Open the data folder” — the file is myday.db. Pick it here. (Your screen record stays on the PC.)'),
        file, h('label', { class: 'item' }, rep, h('span', {}, 'Replace what is on the web')), h('div', { class: 'row' }, go), imp),
      h('div', { class: 'card' }, h('h3', {}, 'Reminders on this phone'), st, h('div', { class: 'row', style: { marginTop: '10px', flexWrap: 'wrap' } }, on, test),
      h('p', { class: 'faint' }, 'First add Curio to your home screen (browser menu › Add to Home screen) and open it from there.')),
      h('div', { class: 'card' }, h('h3', {}, 'The every-minute check (one time setup)'),
        h('p', { class: 'muted' }, 'Reminders go out when this address is opened. A free service opens it every minute for you:'), url,
        h('ol', { class: 'muted' }, h('li', {}, 'Open cron-job.org → Sign up (free) → Create cronjob.'), h('li', {}, 'Title: Curio. URL: paste the address above.'), h('li', {}, 'Execution schedule: Every 1 minute → Create.')),
        h('p', { class: 'faint' }, 'Keep this address private — it only lets someone trigger your reminders, nothing else.')));
  };

  addEventListener('hashchange', () => { const k = location.hash.slice(1); if (k && k !== cur && TABS.some(t => t[0] === k)) { cur = k; nav(); draw(); } });
  nav(); draw();
  document.addEventListener('visibilitychange', () => { if (!document.hidden) draw(); });
})();
