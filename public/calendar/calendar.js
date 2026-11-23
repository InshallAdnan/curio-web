/* Curio Calendar on the web: Finance money + Pages databases on one calendar (Notion-Calendar-style).
   Drag to move (Pages rows: day and time, bottom edge to resize; Finance: the day), drag on empty time to make an event,
   Ctrl+Z undoes a move. Everything is read from and written to your own database through /api/cal. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const h = (tag, a, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(a || {})) {
      if (v === false || v == null) continue;
      if (k === 'style' && typeof v === 'object') { for (const [sk, sv] of Object.entries(v)) sk.startsWith('--') ? e.style.setProperty(sk, sv) : (e.style[sk] = sv); }
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'html') e.innerHTML = v; else if (k === 'value') e.value = v; else if (k === 'checked') e.checked = !!v;
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat(9)) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const SVG = { left: 'M15 18l-6-6 6-6', right: 'M9 18l6-6-6-6', panelL: 'M4 5h16v14H4zM9 5v14', panelR: 'M4 5h16v14H4zM15 5v14', down: 'M7 10l5 5 5-5', search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4' };
  const ic = (n) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('class', 'i'); const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', SVG[n]); s.append(p); return s; };
  const put = (el, ...k) => el.replaceChildren(...k.flat(9).filter(x => x != null && x !== false));
  const toast = (m) => { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 2400); };
  const dark = () => document.documentElement.dataset.theme === 'dark';

  async function api(path, op, args = {}) {
    let r;
    try { r = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify({ op, args }) }); }
    catch (e) { throw new Error('No internet connection — nothing was changed.'); }
    if (r.status === 401) { (window.top || window).location.href = '/api/auth/login'; throw new Error('Signing you in…'); }
    const j = await r.json(); if (j.error) throw new Error(j.error); return j.data;
  }
  const cal = (op, a) => api('/api/cal', op, a);
  const fin = (op, a) => api('/api/fin', op, a);

  // ── dates (local) ──
  const pad = (n) => String(n).padStart(2, '0');
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const ymdhm = (d) => `${ymd(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const parse = (s) => { s = String(s); return s.length <= 10 ? new Date(s + 'T00:00') : new Date(s.slice(0, 16)); };
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const mondayOf = (d) => addDays(startOfDay(d), -((d.getDay() + 6) % 7));
  const sameDay = (a, b) => ymd(a) === ymd(b);
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const isoWeek = (d) => { const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())); const day = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - day); const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1)); return Math.ceil(((t - y0) / 864e5 + 1) / 7); };
  const ampm = (d) => { let H = d.getHours(), M = d.getMinutes(); const ap = H >= 12 ? 'PM' : 'AM'; H = H % 12 || 12; return M ? `${H}:${pad(M)} ${ap}` : `${H} ${ap}`; };

  // ── state ──
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('curio-cal-' + k)); localStorage.setItem('curio-cal-' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const S = { mode: store('mode') || (innerWidth < 600 ? 'days' : 'week'), days: store('days') || 3, anchor: startOfDay(new Date()), data: null, sel: null, undo: [], left: store('left') !== false, right: store('right') !== false, miniMonth: null, accounts: null };
  const SRC_INK = { income: '#15803d', expense: '#dc2626', daily_total: '#64748b', transfer: '#2563eb', subscription: '#7c3aed' };
  const HOUR = 48;

  function range() {
    if (S.mode === 'month') { const first = new Date(S.anchor.getFullYear(), S.anchor.getMonth(), 1); const s = mondayOf(first); return [s, addDays(s, 41)]; }
    if (S.mode === 'week') { const s = mondayOf(S.anchor); return [s, addDays(s, 6)]; }
    const n = S.mode === 'day' ? 1 : S.days; return [S.anchor, addDays(S.anchor, n - 1)];
  }
  function shift(dir) {
    if (S.mode === 'month') S.anchor = new Date(S.anchor.getFullYear(), S.anchor.getMonth() + dir, Math.min(S.anchor.getDate(), 28));
    else S.anchor = addDays(S.anchor, dir * (S.mode === 'week' ? 7 : S.mode === 'day' ? 1 : S.days));
    load();
  }
  function setMode(m, n) { S.mode = m; if (n) S.days = n; store('mode', m); store('days', S.days); load(); }

  // ── events ──
  function norm(e) {
    const isPage = String(e.source).startsWith('page:'), isMd = e.source === 'myday';     // Tracker: tasks, sleep, focus
    const allDay = !(isPage || isMd) || !!e.all_day;
    const start = (isPage || isMd) ? parse(e.start) : parse(e.date);
    let end = e.end ? parse(e.end) : null;
    if (!end) end = allDay ? start : new Date(start.getTime() + 3600e3);
    const ink = (isPage || isMd) ? e.ink : (SRC_INK[e.source] || '#64748b');
    const bg = dark() ? ink + '33' : (isPage ? e.color : isMd ? ink + '22' : ink + '14');
    const movable = isPage || isMd || ['income', 'expense', 'transfer'].includes(e.source);
    return Object.assign({}, e, { isPage, isMd, allDay, s: start, e: end, ink, bg, movable });
  }
  let EV = [];
  const dayEvents = (d) => EV.filter(e => e.allDay ? (startOfDay(e.s) <= d && d <= startOfDay(e.e)) : sameDay(e.s, d));

  async function load() {
    const [a, b] = range();
    try { S.data = await cal('view', { start: ymd(a), end: ymd(b) }); }
    catch (e) { toast(e.message); return; }
    EV = S.data.events.map(norm).sort((x, y) => x.s - y.s || (x.source === 'daily_total') - (y.source === 'daily_total'));
    if (S.sel && !EV.find(e => e.id === S.sel)) S.sel = null;
    render();
  }

  // ── render ──
  function render() { renderLeft(); renderBar(); renderGrid(); renderRight(); }

  function renderBar() {
    const [a, b] = range(); const bar = $('#bar');
    const title = S.mode === 'month' ? `${MONTHS[S.anchor.getMonth()]} ${S.anchor.getFullYear()}` : (a.getMonth() === b.getMonth() ? `${MONTHS[a.getMonth()]} ${a.getFullYear()}` : `${MONTHS[a.getMonth()].slice(0, 3)} – ${MONTHS[b.getMonth()].slice(0, 3)} ${b.getFullYear()}`);
    const viewName = { day: 'Day', week: 'Week', month: 'Month', days: S.days + ' days' }[S.mode];
    put(bar, 
      h('button', { class: 'ib', title: 'Show / hide calendars  ( [ )', onclick: () => togglePanel('left') }, ic('panelL')),
      h('h1', {}, title), S.mode !== 'month' ? h('span', { class: 'wk' }, 'W' + isoWeek(a)) : null, h('div', { class: 'grow' }),
      h('button', { class: 'pill', onclick: (e) => menu(e.currentTarget, [['Day', 'D or 1', () => setMode('day')], ['Week', 'W or 0', () => setMode('week')], ['Month', 'M', () => setMode('month')], '-',
        ...[2, 3, 4, 5, 7].map(n => [`${n} days`, String(n), () => setMode('days', n)])]) }, viewName, ic('down')),
      h('button', { class: 'pill', title: 'Today  (T)', onclick: () => { S.anchor = startOfDay(new Date()); load(); } }, 'Today'),
      h('div', { class: 'nav' }, h('button', { title: 'Previous  (K / ←)', onclick: () => shift(-1) }, ic('left')), h('button', { title: 'Next  (J / →)', onclick: () => shift(1) }, ic('right'))),
      h('button', { class: 'new', title: 'New event  (N)', onclick: () => newEvent(roundNow(), null, false) }, '+  New'),
      h('button', { class: 'ib', title: 'Show / hide details  ( ] )', onclick: () => togglePanel('right') }, ic('panelR')));
  }
  function togglePanel(w) {
    if (innerWidth < 900 && w === 'left') { $('#left').classList.toggle('open'); return; }
    S[w] = !S[w]; store(w, S[w]); $('#' + w).classList.toggle('hide', !S[w]);
  }
  const roundNow = () => { const d = new Date(); d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0); return d; };

  // left: mini month, Finance, Pages databases
  function renderLeft() {
    const L = $('#left'); L.classList.toggle('hide', !S.left);
    const mm = S.miniMonth || new Date(S.anchor.getFullYear(), S.anchor.getMonth(), 1);
    const [ra, rb] = range(); const first = mondayOf(mm); const today = new Date();
    const rows = [];
    for (let w = 0; w < 6; w++) {
      const d0 = addDays(first, w * 7); const inr = S.mode !== 'month' && d0 <= rb && addDays(d0, 6) >= ra;
      rows.push(h('tr', { class: inr ? 'inrange' : '' }, h('td', { class: 'wk' }, isoWeek(d0)), [...Array(7)].map((_, i) => { const d = addDays(d0, i);
        return h('td', { class: (d.getMonth() !== mm.getMonth() ? 'out ' : '') + (sameDay(d, today) ? 'today' : '') }, h('b', { onclick: () => { S.anchor = d; S.miniMonth = null; load(); } }, d.getDate())); })));
    }
    const mini = h('div', { class: 'mini' }, h('div', { class: 'mh' }, h('span', {}, `${MONTHS[mm.getMonth()]} ${mm.getFullYear()}`),
      h('button', { onclick: () => { S.miniMonth = new Date(mm.getFullYear(), mm.getMonth() - 1, 1); renderLeft(); } }, '‹'),
      h('button', { onclick: () => { S.miniMonth = new Date(mm.getFullYear(), mm.getMonth() + 1, 1); renderLeft(); } }, '›')),
      h('table', {}, h('tr', {}, h('th'), DOW.map(d => h('th', {}, d[0]))), rows));
    const D = S.data || { sources: {}, labels: {}, calendars: [], inks: [] };
    const srcRows = Object.keys(D.labels).map(k => h('div', { class: 'src' + (D.sources[k] ? ' on' : ''), style: { '--c': SRC_INK[k] }, onclick: async () => { await cal('set_source', { key: k, on: !D.sources[k] }).catch(e => toast(e.message)); load(); } },
      h('span', { class: 'box' }), h('span', { class: 'nm' }, D.labels[k])));
    const pageRows = D.calendars.map(c => h('div', { class: 'src' + (c.on ? ' on' : ''), style: { '--c': D.inks[c.color % D.inks.length] }, title: `${c.title} · date: ${c.prop_name}`,
      onclick: async (e) => { if (e.target.closest('.dots')) return; await cal('set_page', { db: c.id, on: !c.on }).catch(x => toast(x.message)); load(); } },
      h('span', { class: 'box' }), h('span', { class: 'nm' }, (c.icon && c.icon.length <= 2 ? c.icon + '  ' : '') + c.title),
      h('button', { class: 'dots', title: 'Options', onclick: (e) => pageMenu(e.currentTarget, c) }, '⋯')));
    put(L, mini, h('div', { class: 'sec' }, h('span', {}, 'Finance')), srcRows,
      h('div', { class: 'sec' }, h('span', {}, 'Pages databases'), h('button', { title: 'Add a Pages database as a calendar', onclick: openPicker }, '+')),
      pageRows.length ? pageRows : h('div', { class: 'hint' }, 'No Pages database here yet.\nClick + to pick one from Pages, or paste\nits link (view menu › Copy link to view).'));
  }
  function pageMenu(at, c) {
    const D = S.data, names = ['Blue', 'Pink', 'Green', 'Yellow', 'Purple', 'Teal', 'Orange', 'Grey'];
    menu(at, [['↗  Open database in Pages', '', () => goPages(c.parent || c.id)],
      ...(c.date_props.length > 1 ? ['-', { lbl: 'Use date property' }, ...c.date_props.map(p => [(p.id === c.prop_id ? '✓ ' : '   ') + p.name, '', async () => { await cal('set_page', { db: c.id, prop: p.id }); load(); }])] : []),
      '-', { lbl: 'Colour' }, ...names.map((n, i) => [(i === c.color ? '✓ ' : '   ') + n, '', async () => { await cal('set_page', { db: c.id, color: i }); load(); }]),
      '-', ['Show only this calendar', '', async () => { await cal('solo', { db: c.id }); load(); }],
      ['Remove from Calendar (keeps the database)', '', async () => { await cal('remove', { db: c.id }); load(); }]]);
    void D;
  }
  function menu(at, items) {
    $$('.menu').forEach(m => m.remove());
    const m = h('div', { class: 'menu' }, items.map(it => it === '-' ? h('hr') : it.lbl ? h('div', { class: 'lbl' }, it.lbl) :
      h('button', { onclick: () => { m.remove(); it[2](); } }, h('span', { style: { flex: '1' } }, it[0]), it[1] ? h('span', { style: { color: 'var(--faint)', fontSize: '11.5px' } }, it[1]) : null)));
    document.body.append(m); const r = at.getBoundingClientRect();
    m.style.left = Math.max(6, Math.min(r.left, innerWidth - m.offsetWidth - 6)) + 'px'; m.style.top = Math.min(r.bottom + 4, innerHeight - m.offsetHeight - 6) + 'px';
    setTimeout(() => document.addEventListener('mousedown', function off(e) { if (!m.contains(e.target)) { m.remove(); document.removeEventListener('mousedown', off); } }), 0);
  }

  // grid
  function chip(e) {
    const total = e.source === 'daily_total';
    const el = h('div', { class: 'chip' + (total ? ' total' : '') + (S.sel === e.id ? ' sel' : ''), style: { '--ink': e.ink, '--bgc': e.bg }, 'data-id': e.id, title: e.title + (e.detail ? '  ' + e.detail : '') },
      e.isPage && e.icon && e.icon.length <= 2 ? h('span', {}, e.icon) : null, h('span', {}, total ? `Net ${e.detail}` : e.title + (e.detail && !e.isPage ? '  ' + e.detail.replace('+', '').replace('−', '−') : '')));
    attachDrag(el, e); return el;
  }
  function renderGrid() {
    const G = $('#grid'); put(G, );
    if (S.mode === 'month') return renderMonth(G);
    const [a, b] = range(); const days = []; for (let d = new Date(a); d <= b; d = addDays(d, 1)) days.push(new Date(d));
    const cols = `56px repeat(${days.length}, minmax(0,1fr))`; const today = new Date();
    G.append(h('div', { class: 'dhead', style: { gridTemplateColumns: cols } }, h('div', { class: 'tz' }, 'GMT+5'),
      days.map(d => h('div', { class: 'd' + (sameDay(d, today) ? ' today' : '') + (d.getDay() % 6 === 0 ? ' wkend' : '') }, DOW[(d.getDay() + 6) % 7], h('b', { onclick: () => { S.anchor = d; setMode('day'); } }, d.getDate())))));
    G.append(h('div', { class: 'allday', style: { gridTemplateColumns: cols } }, h('div', { class: 'lab' }, 'all-day'),
      days.map(d => h('div', { class: 'col', 'data-date': ymd(d), ondblclick: (ev) => { if (ev.target === ev.currentTarget) newEvent(d, null, true); } }, dayEvents(d).filter(e => e.allDay).map(chip)))));
    const sc = h('div', { class: 'scroll' }); G.append(sc);
    const tg = h('div', { class: 'tgrid', style: { gridTemplateColumns: cols, height: 24 * HOUR + 'px' } });
    tg.append(h('div', { class: 'hours' }, [...Array(24)].map((_, i) => h('div', {}, i ? ampm(new Date(2000, 0, 1, i)) : ''))));
    days.forEach(d => {
      const col = h('div', { class: 'tcol' + (d.getDay() % 6 === 0 ? ' wkend' : ''), 'data-date': ymd(d) });
      const d0 = startOfDay(d), d1 = addDays(d0, 1);
      const timed = [...dayEvents(d).filter(e => !e.allDay),                       // + the morning part of a night (or anything) that started yesterday
        ...EV.filter(e => !e.allDay && e.s < d0 && e.e > d0).map(e => Object.assign(Object.create(Object.getPrototypeOf(e)), e, { cont: true }))];
      const lanes = [], ends = []; timed.forEach(e => { let l = ends.findIndex(t => t <= e.s); if (l < 0) { l = ends.length; ends.push(0); } ends[l] = e.e; lanes.push(l); });
      const n = Math.max(1, ends.length);
      timed.forEach((e, i) => {
        const vs = e.cont ? d0 : e.s, ve = e.e > d1 ? d1 : e.e;                   // the part of it that falls on this day
        const top = (vs.getHours() * 60 + vs.getMinutes()) / 60 * HOUR, mins = Math.max(20, (ve - vs) / 6e4);
        const el = h('div', { class: 'ev' + (e.planned ? ' plan' : '') + (S.sel === e.id ? ' sel' : ''), 'data-id': e.id, style: { '--ink': e.ink, '--bgc': e.bg, top: top + 'px', height: Math.max(20, mins / 60 * HOUR - 2) + 'px', left: `calc(${lanes[i] / n * 100}% + 2px)`, width: `calc(${100 / n}% - 4px)` } },
          h('b', {}, (e.icon && e.icon.length <= 2 ? e.icon + ' ' : '') + e.title), h('small', {}, `${ampm(e.s)} – ${ampm(e.e)}`), e.isMd ? h('div', { class: 'rz rzt' }) : null, (e.isPage || e.isMd) ? h('div', { class: 'rz' }) : null);
        if (e.cont) { el.classList.add('cont'); el.querySelector('.rzt') && el.querySelector('.rzt').remove(); el.addEventListener('click', () => select(e.id)); contResize(el, e, d0); }
        else attachDrag(el, e);
        col.append(el);
      });
      if (sameDay(d, today)) col.append(h('div', { class: 'now', style: { top: (today.getHours() * 60 + today.getMinutes()) / 60 * HOUR + 'px' } }));
      col.addEventListener('pointerdown', (ev) => { if (ev.target === col && ev.button === 0) createDrag(ev, col, d); });
      tg.append(col);
    });
    sc.append(tg);
    requestAnimationFrame(() => { sc.scrollTop = S._scroll != null ? S._scroll : 7.5 * HOUR; });
    sc.addEventListener('scroll', () => { S._scroll = sc.scrollTop; });
  }
  function renderMonth(G) {
    const [a] = range(); const today = new Date(), mon = S.anchor.getMonth();
    G.append(h('div', { class: 'mhead' }, DOW.map(d => h('div', {}, d))));
    const grid = h('div', { class: 'month' });
    for (let i = 0; i < 42; i++) {
      const d = addDays(a, i); const evs = dayEvents(d); const max = 4;
      const cell = h('div', { class: 'cell' + (d.getMonth() !== mon ? ' out' : '') + (sameDay(d, today) ? ' today' : '') + (d.getDay() % 6 === 0 ? ' wkend' : ''), 'data-date': ymd(d),
        ondblclick: (ev) => { if (ev.target === ev.currentTarget) newEvent(d, null, true); } },
        h('div', { class: 'n', onclick: () => { S.anchor = d; setMode('day'); } }, d.getDate() === 1 ? `${MONTHS[d.getMonth()].slice(0, 3)} 1` : d.getDate()),
        evs.slice(0, max).map(chip), evs.length > max ? h('div', { class: 'more', onclick: () => { S.anchor = d; setMode('day'); } }, `+${evs.length - max} more`) : null);
      grid.append(cell);
    }
    G.append(grid);
  }

  // ── dragging: move / resize / create ──
  function attachDrag(el, e) {
    el.addEventListener('click', (ev) => { if (el._dragged) { el._dragged = false; return; } ev.stopPropagation(); select(e.id); });
    el.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0 || !e.movable) return;
      ev.stopPropagation();
      const resize = ev.target.classList.contains('rz'), top = ev.target.classList.contains('rzt');
      const sx = ev.clientX, sy = ev.clientY; let moved = false, target = null, ghost = null;
      const timed = !e.allDay && el.classList.contains('ev');
      const onMove = (m) => {
        if (!moved && Math.abs(m.clientX - sx) + Math.abs(m.clientY - sy) < 5) return;
        moved = true; el._dragged = true;
        if (timed) {
          const col = document.elementsFromPoint(m.clientX, m.clientY).find(x => x.classList && x.classList.contains('tcol'));
          if (!col) return;
          const r = col.getBoundingClientRect(); const dur = e.e - e.s;
          let mins = Math.round(((m.clientY - r.top) / HOUR * 60 - (resize ? 0 : ((sy - el.getBoundingClientRect().top) / HOUR * 60))) / 15) * 15;
          if (!ghost) { ghost = el.cloneNode(true); ghost.classList.add('ghost'); el.style.opacity = .35; }
          const day = parse(col.dataset.date);
          if (top) { const start = new Date(day.getTime() + Math.max(0, Math.min(mins, (e.e - day) / 6e4 - 15)) * 6e4); target = { start, end: e.e };
            ghost.style.top = (start - day) / 36e5 * HOUR + 'px'; ghost.style.height = Math.max(20, (e.e - start) / 36e5 * HOUR - 2) + 'px'; if (ghost.parentNode !== el.parentNode) el.parentNode.append(ghost); }
          else if (resize) { const end = new Date(startOfDay(e.s).getTime() + Math.max((e.s - startOfDay(e.s)) / 6e4 + 15, mins) * 6e4); target = { start: e.s, end };
            ghost.style.height = Math.max(20, (end - e.s) / 36e5 * HOUR - 2) + 'px'; if (ghost.parentNode !== el.parentNode) el.parentNode.append(ghost); }
          else { mins = Math.max(0, Math.min(24 * 60 - 15, mins)); const start = new Date(day.getTime() + mins * 6e4); target = { start, end: new Date(start.getTime() + dur) };
            ghost.style.top = mins / 60 * HOUR + 'px'; ghost.style.left = '2px'; ghost.style.width = 'calc(100% - 4px)'; if (ghost.parentNode !== col) col.append(ghost); }
        } else {
          $$('.drop-hl').forEach(x => x.classList.remove('drop-hl'));
          const cell = document.elementsFromPoint(m.clientX, m.clientY).find(x => x.dataset && x.dataset.date && (x.classList.contains('cell') || x.classList.contains('col') || x.classList.contains('tcol')));
          if (!cell) return; cell.classList.add('drop-hl'); el.style.opacity = .4;
          const day = parse(cell.dataset.date), span = startOfDay(e.e) - startOfDay(e.s);
          target = { start: day, end: new Date(day.getTime() + span) };
        }
      };
      const onUp = async () => {
        document.removeEventListener('pointermove', onMove); document.removeEventListener('pointerup', onUp);
        $$('.drop-hl').forEach(x => x.classList.remove('drop-hl')); if (ghost) ghost.remove(); el.style.opacity = '';
        if (!moved || !target) return;
        if (+target.start === +e.s && +target.end === +e.e) return;
        await moveEvent(e, target.start, target.end, true);
      };
      document.addEventListener('pointermove', onMove); document.addEventListener('pointerup', onUp);
    });
  }
  function contResize(el, e, day) {                                            // the morning part of a night: drag its bottom edge to change the wake-up time
    el.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0 || !e.movable || !ev.target.classList.contains('rz')) return;
      ev.stopPropagation(); let end = null; const r = el.parentNode.getBoundingClientRect();
      const onMove = (m) => { const mins = Math.max(15, Math.min(24 * 60, Math.round((m.clientY - r.top) / HOUR * 60 / 15) * 15)); end = new Date(day.getTime() + mins * 6e4);
        el.style.height = Math.max(20, (end - day) / 36e5 * HOUR - 2) + 'px'; };
      const onUp = async () => { document.removeEventListener('pointermove', onMove); document.removeEventListener('pointerup', onUp); if (end && +end !== +e.e) await moveEvent(e, e.s, end, true); };
      document.addEventListener('pointermove', onMove); document.addEventListener('pointerup', onUp);
    });
  }
  async function moveEvent(e, start, end, remember) {
    const allDay = e.allDay;
    const fmt = (d) => allDay ? ymd(d) : ymdhm(d);
    try {
      if (e.isMd) await cal('move', { source: 'myday', kind: e.mkind, id: e.mid, start: fmt(start), end: end && !allDay ? fmt(end) : null, all_day: allDay });
      else await cal('move', { source: e.source, record_id: e.record_id, prop_id: e.prop_id, start: fmt(start), end: e.isPage && end && +end !== +start ? fmt(end) : null, all_day: allDay });
      if (remember) { S.undo.push({ e: Object.assign({}, e, { s: start, e: end }), start: e.s, end: e.e }); toast('Moved · Ctrl+Z to undo'); }
      await load();
    } catch (x) { toast(x.message); load(); }
  }
  function createDrag(ev, col, day) {
    const r = col.getBoundingClientRect(); const m0 = Math.floor((ev.clientY - r.top) / HOUR * 4) * 15; let m1 = m0 + 60;
    const g = h('div', { class: 'slot-ghost', style: { top: m0 / 60 * HOUR + 'px', height: HOUR + 'px' } }); col.append(g);
    const mv = (m) => { m1 = Math.max(m0 + 15, Math.ceil((m.clientY - r.top) / HOUR * 4) * 15); g.style.height = (m1 - m0) / 60 * HOUR + 'px'; };
    const up = () => { document.removeEventListener('pointermove', mv); document.removeEventListener('pointerup', up); g.remove();
      newEvent(new Date(day.getTime() + m0 * 6e4), new Date(day.getTime() + m1 * 6e4), false); };
    document.addEventListener('pointermove', mv); document.addEventListener('pointerup', up);
  }

  // ── details (right) ──
  function select(id) { S.sel = id; $$('.sel').forEach(x => x.classList.remove('sel')); $$(`[data-id="${CSS.escape(id)}"]`).forEach(x => x.classList.add('sel')); renderRight(); }
  async function renderRight() {
    const R = $('#right'); R.classList.toggle('hide', !S.right);
    const e = EV.find(x => x.id === S.sel);
    if (!e) {
      const t = new Date(), list = dayEvents(startOfDay(t));
      put(R, h('div', { class: 'dt-label' }, t.toLocaleDateString('en-GB', { weekday: 'long' })), h('div', { class: 'dt-title' }, t.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })),
        list.length ? list.map(x => h('div', { class: 'chip', style: { '--ink': x.ink, '--bgc': x.bg, marginBottom: '4px' }, onclick: () => select(x.id) }, h('span', {}, x.title + (x.detail && !x.isPage ? '  ' + x.detail : '')))) : h('div', { class: 'short' }, 'Nothing on the calendar today.'),
        h('div', { class: 'dt-label', style: { marginTop: '22px' } }, 'SHORTCUTS'),
        h('div', { class: 'short' }, 'D or 1 · day   W or 0 · week   M · month', h('br'), '2 – 9 · number of days   T · today', h('br'), 'J / K or → / ← · next / previous', h('br'), 'N · new event   Ctrl+Z · undo a move', h('br'), '[ ] · side panels   Esc · close details'),
        h('div', { class: 'short', style: { marginTop: '12px' } }, 'Drag on empty time to make an event. Drag any event — Pages, income, expense or transfer — to another day to move it; drag a Pages event’s bottom edge to change the end time.'));
      return;
    }
    const when = e.allDay ? (sameDay(e.s, e.e) ? e.s.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' }) : `${e.s.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} → ${e.e.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`)
      : `${e.s.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}, ${ampm(e.s)} – ${ampm(e.e)}`;
    const calName = e.isPage ? e.calendar : S.data.labels[e.source];
    const head = [h('div', { class: 'dt-label' }, h('span', { style: { display: 'inline-block', width: '9px', height: '9px', borderRadius: '3px', background: e.ink, marginRight: '6px' } }), calName)];
    if (e.isPage) {
      const inp = h('input', { class: 'dt-edit', value: e.title, onkeydown: (k) => { if (k.key === 'Enter') inp.blur(); },
        onblur: async () => { if (inp.value.trim() !== e.title) { await cal('rename', { record_id: e.record_id, title: inp.value.trim() }).catch(x => toast(x.message)); load(); } } });
      const props = h('div', {}, h('div', { class: 'short' }, '…'));
      put(R, ...head, inp, h('div', { class: 'dt-row' }, h('span', { class: 'k' }, 'When'), h('span', {}, when)), props,
        h('button', { class: 'dt-btn', onclick: () => goPages(e.record_id) }, '↗  Open in Pages'),
        h('button', { class: 'dt-btn danger', onclick: async () => { await cal('clear_date', { record_id: e.record_id, prop_id: e.prop_id }).catch(x => toast(x.message)); S.sel = null; load(); } }, 'Remove from calendar (clear the date)'));
      const rows = await cal('details', { db: e.db_id, record_id: e.record_id, prop_id: e.prop_id }).catch(() => []);
      if (S.sel === e.id) put(props, ...rows.filter(r => r[1]).map(([k, v]) => h('div', { class: 'dt-row' }, h('span', { class: 'k' }, k), h('span', {}, v))));
    } else {
      put(R, ...head, h('div', { class: 'dt-title' }, e.title), h('div', { class: 'big', style: { color: e.ink } }, e.detail || ''), h('div', { class: 'dt-row' }, h('span', { class: 'k' }, 'Date'), h('span', {}, when)),
        h('div', { id: 'findet' }), h('button', { class: 'dt-btn', onclick: () => goTop('finance') }, '↗  Open Finance'));
      if (['income', 'expense', 'transfer'].includes(e.source)) {
        const d = await cal('fin_detail', { source: e.source, record_id: e.record_id }).catch(() => null);
        const box = $('#findet'); if (!d || !box || S.sel !== e.id) return;
        const rows = e.source === 'transfer' ? [['From', d.from_name], ['To', d.to_name], ['Note', d.note]] : [['Account', d.account_name], ['Category', d.category_name], ['Note', d.note]];
        put(box, ...rows.filter(r => r[1]).map(([k, v]) => h('div', { class: 'dt-row' }, h('span', { class: 'k' }, k), h('span', {}, v))));
      }
    }
  }
  const goTop = (to, doc) => { try { window.top.postMessage({ curio: 'go', to, doc }, location.origin); } catch (e) { /* standalone */ } };
  const goPages = (doc) => goTop('pages', doc);

  // ── new event ──
  async function newEvent(start, end, allDay) {
    const cals = (S.data && S.data.calendars || []).filter(c => c.on);
    if (!S.accounts) S.accounts = await fin('meta').then(m => m.accounts.filter(a => !a.archived)).catch(() => []);
    end = end || (allDay ? start : new Date(start.getTime() + 3600e3));
    const t = h('input', { type: 'text', placeholder: 'Event title' });
    const which = h('select', {}, cals.map((c, i) => h('option', { value: 'p' + i }, `${c.icon && c.icon.length <= 2 ? c.icon : '▦'}  ${c.title}   (${c.prop_name})`)),
      h('option', { value: 'fx' }, '💸  Finance — expense'), h('option', { value: 'fi' }, '💰  Finance — income'));
    const ad = h('input', { type: 'checkbox', checked: allDay, style: { width: 'auto' } });
    const a = h('input', {}), b = h('input', {});
    const acc = h('select', {}, S.accounts.map(x => h('option', { value: x.id }, `${x.name} · ${x.currency}`)));
    const amt = h('input', { type: 'text', inputmode: 'decimal', placeholder: 'Amount' });
    const finRow = h('div', { class: 'r' }, acc, amt); const err = h('div', { class: 'err' });
    const sync = () => { const isFin = which.value.startsWith('f'); finRow.style.display = isFin ? 'flex' : 'none'; ad.disabled = isFin;
      const all = isFin || ad.checked; a.type = b.type = all ? 'date' : 'datetime-local'; a.value = all ? ymd(start) : ymdhm(start); b.value = all ? ymd(end) : ymdhm(end); b.disabled = isFin; };
    which.onchange = sync; ad.onchange = () => { start = parse(a.value); end = parse(b.value || a.value); sync(); }; sync();
    if (!cals.length) which.value = 'fx', sync();
    const close = () => { sc.remove(); dl.remove(); };
    const ok = h('button', { class: 'new', onclick: async () => {
      err.textContent = ''; ok.disabled = true;
      try {
        if (which.value.startsWith('f')) {
          if (!S.accounts.length) throw new Error('Add an account in Finance first.');
          await fin('tx_save', { kind: which.value === 'fi' ? 'income' : 'expense', amount: amt.value, title: t.value, account: acc.value, date: a.value.slice(0, 10) });
        } else {
          const c = cals[+which.value.slice(1)]; const all = ad.checked;
          await cal('create', { db: c.id, prop_id: c.prop_id, title: t.value, start: a.value, end: b.value && b.value !== a.value ? b.value : null, all_day: all });
        }
        close(); toast('Added'); load();
      } catch (x) { err.textContent = x.message; ok.disabled = false; } } }, 'Create');
    const sc = h('div', { class: 'scrim', onclick: close });
    const dl = h('div', { class: 'dlg' }, t, which, h('div', { class: 'r' }, a, h('span', {}, '→'), b), h('label', { class: 'r', style: { gap: '6px' } }, ad, 'All day'), finRow, err,
      h('div', { class: 'acts' }, h('button', { class: 'pill', onclick: close }, 'Cancel'), ok));
    document.body.append(sc, dl); t.focus();
    t.addEventListener('keydown', (k) => { if (k.key === 'Enter') ok.click(); if (k.key === 'Escape') close(); });
  }

  // ── Notion-Calendar-style “Add database” picker ──
  async function openPicker() {
    let data = await cal('databases', {}).catch(x => { toast(x.message); return null; }); if (!data) return;
    const q = h('input', { placeholder: 'Add Pages database or paste its link…' });
    const list = h('div', { class: 'list' }); let rows = [], cur = 0, tm;
    const sc = h('div', { class: 'scrim', onclick: () => close() });
    const pk = h('div', { class: 'picker' }, h('div', { class: 'chipws' }, `${(data.me || 'Your')} Pages`), h('div', { class: 'q' }, ic('search'), q), list,
      h('div', { class: 'foot', html: 'Pages databases with a Date property appear here. Not in the list? In Pages open the view menu (▾ next to the view name) › <b>Copy link to view</b> and paste it above.' }));
    const close = () => { sc.remove(); pk.remove(); };
    const fill = () => {
      const t = q.value.trim(), tl = t.toLowerCase(); const shown = new Set(data.shown); put(list, ); rows = [];
      const row = (d) => { const added = shown.has(d.id); const r = h('div', { class: 'row' + (added ? ' added' : ''), title: added ? 'Already on your Calendar — use ⋯ next to it on the left to remove it' : '' },
        h('span', {}, d.icon && d.icon.length <= 2 ? d.icon : '▦'), h('span', { class: 't' }, d.title), h('span', { class: 'c' }, d.crumb ? ' —  ' + d.crumb : ''),
        added ? h('span', { class: 'tag' }, 'Added') : !d.has_date ? h('span', { class: 'tag add' }, 'Add Date property') : null);
        if (!added) { r.onclick = () => pick(d); rows.push([r, d]); } list.append(r); };
      if (data.link) { list.append(h('div', { class: 'head' }, 'From the link')); const d = data.dbs.find(x => x.id === data.link); if (d) row(d); }
      else {
        const match = data.dbs.filter(d => !tl || d.title.toLowerCase().includes(tl) || (d.crumb || '').toLowerCase().includes(tl));
        const dated = match.filter(d => d.has_date);
        dated.filter(d => !shown.has(d.id)).forEach(row); dated.filter(d => shown.has(d.id)).forEach(row);
        const nod = match.filter(d => !d.has_date);
        if (nod.length) { list.append(h('div', { class: 'head' }, 'No Date property yet — click one to give it a Date and show it')); nod.forEach(row); }
        if (!list.children.length) list.append(h('div', { class: 'head' }, t ? `Nothing matches “${t}”` : 'No database found'));
      }
      cur = 0; paint();
    };
    const paint = () => rows.forEach(([r], i) => r.classList.toggle('cur', i === cur));
    const pick = async (d) => { close(); try { await cal('add_db', { db: d.id }); toast(d.has_date ? 'Added to Calendar' : 'Gave it a Date property and added it'); load(); } catch (x) { toast(x.message); } };
    q.addEventListener('input', () => { clearTimeout(tm); const t = q.value.trim();
      if (/documents\/|db=|^[0-9a-f]{16}$/.test(t)) tm = setTimeout(async () => { data = await cal('databases', { link: t }); fill(); }, 200);
      else { data.link = null; fill(); } });
    q.addEventListener('keydown', (k) => {
      if (k.key === 'Escape') close();
      else if (k.key === 'ArrowDown') { cur = Math.min(rows.length - 1, cur + 1); paint(); k.preventDefault(); }
      else if (k.key === 'ArrowUp') { cur = Math.max(0, cur - 1); paint(); k.preventDefault(); }
      else if (k.key === 'Enter' && rows[cur]) pick(rows[cur][1]);
    });
    document.body.append(sc, pk); fill(); q.focus();
  }

  // ── keys ──
  document.addEventListener('keydown', async (k) => {
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || $('.dlg') || $('.picker')) return;
    if ((k.ctrlKey || k.metaKey) && k.key.toLowerCase() === 'z') { const u = S.undo.pop(); if (u) { k.preventDefault(); await moveEvent(u.e, u.start, u.end, false); toast('Undone'); } return; }
    if (k.ctrlKey || k.metaKey || k.altKey) return;
    const K = k.key.toLowerCase();
    if (K === 'd' || K === '1') setMode('day'); else if (K === 'w' || K === '0') setMode('week'); else if (K === 'm') setMode('month');
    else if (/^[2-9]$/.test(K)) setMode('days', +K); else if (K === 't') { S.anchor = startOfDay(new Date()); load(); }
    else if (K === 'j' || K === 'arrowright') shift(1); else if (K === 'k' || K === 'arrowleft') shift(-1);
    else if (K === 'n') newEvent(roundNow(), null, false); else if (K === '[') togglePanel('left'); else if (K === ']') togglePanel('right');
    else if (K === 'escape') { S.sel = null; $$('.sel').forEach(x => x.classList.remove('sel')); renderRight(); }
  });
  setInterval(() => { const n = $('.now'); if (n) { const t = new Date(); n.style.top = (t.getHours() * 60 + t.getMinutes()) / 60 * HOUR + 'px'; } }, 60000);
  window.addEventListener('focus', () => load());                 // changes made in Pages / Finance show up when you come back
  load();
})();
