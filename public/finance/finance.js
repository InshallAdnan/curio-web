/* Curio Finance on the web. Every number comes from the server, which runs the desktop app's own money rules
   (balances, transfers, subscriptions, goals, depreciation). Amounts arrive as minor units (paisa). */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const h = (tag, attrs, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === 'html') e.innerHTML = v; else if (k === 'style' && typeof v === 'object') { for (const [sk, sv] of Object.entries(v)) { if (sk.startsWith('--')) e.style.setProperty(sk, sv); else e.style[sk] = sv; } }
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'value') e.value = v; else if (k === 'checked') e.checked = !!v; else e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat(9)) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const SVGNS = 'http://www.w3.org/2000/svg';
  const s = (tag, attrs, ...kids) => { const e = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs || {})) if (v != null) e.setAttribute(k, v); kids.flat().forEach(k => k != null && e.append(k.nodeType ? k : document.createTextNode(k))); return e; };
  const toast = (m) => { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 2600); };

  // ── server ──
  async function api(op, args = {}) {
    let r;
    try { r = await fetch('/api/fin', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify({ op, args }) }); }
    catch (e) { throw new Error('No internet connection — nothing was changed.'); }
    if (r.status === 401) { (window.top || window).location.href = '/api/auth/login'; throw new Error('Signing you in…'); }
    const j = await r.json().catch(() => ({ error: 'The server did not answer properly.' }));
    if (j.error) throw new Error(j.error);
    return j.data;
  }
  let META = null;

  // ── money (same as finance/money.py) ──
  const SYM = { PKR: 'Rs', USD: '$', EUR: '€', GBP: '£', INR: '₹', AED: 'AED', SAR: 'SAR', CAD: 'C$', AUD: 'A$', JPY: '¥' };
  const PLAIN = new Set(['PKR', 'INR', 'JPY']);
  function fmt(m, cur, o = {}) {
    if (m == null) return '—';
    const neg = m < 0; let a = Math.abs(Math.round(m));
    if (o.whole && PLAIN.has(cur)) a = Math.floor((a + 50) / 100) * 100;
    const w = Math.floor(a / 100), c = a % 100;
    const body = (PLAIN.has(cur) && c === 0) ? w.toLocaleString('en-US') : w.toLocaleString('en-US') + '.' + String(c).padStart(2, '0');
    const pre = cur ? (SYM[cur] || cur) : ''; const s2 = pre + (pre.length > 1 ? ' ' : '') + body;
    return neg ? '−' + s2 : (o.sign && m > 0 ? '+' + s2 : s2);
  }
  const plain = (m) => { if (m == null || m === '') return ''; const w = Math.floor(Math.abs(m) / 100), c = Math.abs(m) % 100; return (m < 0 ? '-' : '') + (c ? w + '.' + String(c).padStart(2, '0') : String(w)); };
  const B = () => (META && META.base) || 'PKR';
  const W = (m, cur) => fmt(m, cur || B(), { whole: true });

  // ── dates ──
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const today = () => (META && META.today) || new Date().toISOString().slice(0, 10);
  const thisMonth = () => today().slice(0, 7);
  const addMonths = (m, n) => { let [y, mo] = m.split('-').map(Number); mo += n; y += Math.floor((mo - 1) / 12); mo = ((mo - 1) % 12 + 12) % 12 + 1; return `${y}-${String(mo).padStart(2, '0')}`; };
  const monthLabel = (m) => `${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}`;
  const nice = (d, year = true) => { if (!d) return ''; const dt = new Date(d.slice(0, 10) + 'T00:00'); const t = today();
    if (d.slice(0, 10) === t) return 'Today'; const y = new Date(t + 'T00:00'); y.setDate(y.getDate() - 1); if (dt.getTime() === y.getTime()) return 'Yesterday';
    return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(year && d.slice(0, 4) !== t.slice(0, 4) ? { year: 'numeric' } : {}) }); };
  const t12 = (t) => { if (!t) return ''; let [H, M] = t.split(':').map(Number); const ap = H >= 12 ? 'PM' : 'AM'; H = H % 12 || 12; return `${H}:${String(M).padStart(2, '0')} ${ap}`; };

  // ── icons ──
  const IP = {
    home: 'M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z', list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01', swap: 'M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7',
    wallet: 'M3 7a2 2 0 0 1 2-2h14v4M3 7v10a2 2 0 0 0 2 2h16V9H5a2 2 0 0 1-2-2zM16 14h.01', target: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
    repeat: 'M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3', box: 'M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8', chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
    gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z', plus: 'M12 5v14M5 12h14', more: 'M12 6h.01M12 12h.01M12 18h.01', x: 'M18 6 6 18M6 6l12 12', left: 'M15 18l-6-6 6-6', right: 'M9 18l6-6-6-6',
    trash: 'M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6', cal: 'M4 5h16v16H4zM16 3v4M8 3v4M4 10h16', tag: 'M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 7.5h.01',
  };
  const ic = (n) => s('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.9, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, s('path', { d: IP[n] }));

  // ── small building blocks ──
  const card = (title, extra, ...kids) => h('div', { class: 'card' }, title != null ? h('div', { class: 'ch' }, h('h3', {}, title), h('div', { class: 'x' }, extra)) : null, kids);
  const btn = (text, cls, onclick, icon) => h('button', { class: 'btn ' + (cls || ''), onclick }, icon ? ic(icon) : null, text);
  const bar = (frac, color) => { const b = h('div', { class: 'bar' }, h('i', { style: { width: '0%', background: color || 'var(--accent)' } })); requestAnimationFrame(() => requestAnimationFrame(() => { b.firstChild.style.width = Math.max(0, Math.min(1, frac || 0)) * 100 + '%'; })); return b; };
  const chip = (text, color) => h('span', { class: 'chip ' + (color || '') }, text);
  const dot = (c, size = 10) => h('span', { class: 'dot', style: { background: c, width: size + 'px', height: size + 'px' } });
  const accById = (id) => (META.accounts || []).find(a => a.id === id);
  const catById = (id) => (META.categories || []).find(c => c.id === id);
  const catColor = (c, i = 0) => (c && c.color) || META.cat_colors[(c ? c.id : i) % META.cat_colors.length];
  const kindLabel = (k) => (META.kinds.find(x => x[0] === k) || [k, k])[1];

  function seg(options, value, onchange) {
    const el = h('div', { class: 'seg' });
    options.forEach(([v, t]) => el.append(h('button', { class: v === value ? 'on' : '', onclick: () => { $$('button', el).forEach(b => b.classList.remove('on')); el.children[options.findIndex(o => o[0] === v)].classList.add('on'); onchange(v); } }, t)));
    return el;
  }
  function menu(at, items) {
    $$('.menu').forEach(m => m.remove());
    const m = h('div', { class: 'menu' }, items.map(it => it === '-' ? h('hr') : h('button', { class: it.danger ? 'danger' : '', onclick: () => { m.remove(); it.fn(); } }, it.t)));
    document.body.append(m);
    const r = at.getBoundingClientRect(); const mw = m.offsetWidth, mh = m.offsetHeight;
    m.style.left = Math.max(8, Math.min(r.right - mw, innerWidth - mw - 8)) + 'px'; m.style.top = (r.bottom + mh + 6 > innerHeight ? r.top - mh - 4 : r.bottom + 4) + 'px';
    setTimeout(() => document.addEventListener('mousedown', function off(e) { if (!m.contains(e.target)) { m.remove(); document.removeEventListener('mousedown', off); } }), 0);
  }

  // ── forms in a dialog ──
  function modal(title, body, foot, wide) {
    const sc = h('div', { class: 'scrim' }); const m = h('div', { class: 'modal' + (wide ? ' wide' : '') }, h('div', { class: 'mh' }, h('h2', {}, title), btn('', 'ghost icon', () => close(), 'x')), body, foot);
    sc.append(m); document.body.append(sc);
    const close = () => { sc.remove(); document.removeEventListener('keydown', esc); };
    const esc = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', esc); sc.addEventListener('mousedown', (e) => { if (e.target === sc) close(); });
    return { close, el: m };
  }
  function opts(list, val, blank) {
    return [blank != null ? h('option', { value: '' }, blank) : null, ...list.map(([v, t]) => h('option', { value: v, selected: String(v) === String(val) ? true : false }, t))];
  }
  function field(f, val) {
    let inp;
    if (f.type === 'select') inp = h('select', { class: 'inp', name: f.k }, opts(f.options, val, f.blank));
    else if (f.type === 'textarea') inp = h('textarea', { name: f.k, rows: 3, placeholder: f.ph || '' }, val || '');
    else if (f.type === 'check') return h('div', { class: 'fld check' + (f.half ? ' half' : '') }, h('input', { type: 'checkbox', name: f.k, id: 'f_' + f.k, checked: !!val }), h('label', { for: 'f_' + f.k, style: { color: 'var(--ink)', fontWeight: 500 } }, f.label));
    else if (f.type === 'color') {
      const box = h('div', { class: 'colors' }); let cur = val || '';
      const hid = h('input', { type: 'hidden', name: f.k, value: cur });
      (f.options || META.colors).forEach(c => box.append(h('button', { type: 'button', class: c === cur ? 'on' : '', style: { background: c }, onclick: (e) => { $$('button', box).forEach(b => b.classList.remove('on')); e.currentTarget.classList.add('on'); hid.value = c; } })));
      inp = h('div', {}, box, hid);
    }
    else inp = h('input', { class: 'inp', name: f.k, type: f.type === 'amount' ? 'text' : (f.type || 'text'), inputmode: f.type === 'amount' ? 'decimal' : null, value: val == null ? '' : val, placeholder: f.ph || '', step: f.step || null, min: f.min, max: f.max, autocomplete: 'off' });
    return h('div', { class: 'fld' + (f.half ? ' half' : '') }, h('label', {}, f.label), inp, f.hint ? h('div', { class: 'hint' }, f.hint) : null);
  }
  function form(title, fields, vals, onSave, o = {}) {
    const body = h('form', { class: 'mb', onsubmit: (e) => { e.preventDefault(); save(); } }, fields.filter(Boolean).map(f => f.html ? h('div', { class: 'fld' }, f.html) : field(f, vals[f.k])), h('button', { type: 'submit', style: { display: 'none' } }));
    const err = h('span', { class: 'err' });
    const ok = btn(o.ok || 'Save', 'primary', () => save());
    const foot = h('div', { class: 'mf' }, err, o.extra || null, btn('Cancel', '', () => m.close()), ok);
    const m = modal(title, body, foot, o.wide);
    async function save() {
      const fd = {}; fields.filter(f => f && f.k).forEach(f => { const el = body.elements[f.k]; fd[f.k] = f.type === 'check' ? el.checked : el.value; });
      ok.disabled = true; err.textContent = '';
      try { await onSave(fd); m.close(); }
      catch (e) { err.textContent = e.message; ok.disabled = false; }
    }
    if (o.onBuild) o.onBuild(body, m);
    setTimeout(() => { const f = body.querySelector('input:not([type=hidden]):not([type=checkbox]),select'); if (f && !o.noFocus) f.focus(); }, 30);
    return m;
  }
  const ask = (text, okText = 'Delete', danger = true) => new Promise((ok) => {
    const foot = h('div', { class: 'mf' }, btn('Cancel', '', () => { m.close(); ok(false); }), btn(okText, danger ? 'primary' : 'primary', () => { m.close(); ok(true); }));
    const m = modal('Are you sure?', h('div', { class: 'mb' }, h('p', { class: 'fld', style: { margin: 0 } }, text)), foot);
  });
  async function act(op, args, msg) {
    try { const r = await api(op, args); if (msg) toast(msg); await reload(); return r; }
    catch (e) { toast(e.message); throw e; }
  }

  // ── charts ──
  function cashflow(series) {
    const W0 = 760, H0 = 240, pl = 8, pr = 8, pt = 16, pb = 26;
    const max = Math.max(1, ...series.map(x => Math.max(x.income, x.expense)));
    const n = series.length, gw = (W0 - pl - pr) / n, bw = Math.min(16, gw * .3);
    const y = (v) => pt + (H0 - pt - pb) * (1 - v / max);
    const svg = s('svg', { viewBox: `0 0 ${W0} ${H0}`, role: 'img', 'aria-label': 'Money in and spent per month' });
    for (let i = 0; i <= 3; i++) svg.append(s('line', { x1: pl, x2: W0 - pr, y1: y(max * i / 3), y2: y(max * i / 3), stroke: 'var(--line)', 'stroke-dasharray': i ? '3 4' : null }));
    const spent = series.slice(0, -1).filter(x => x.expense).map(x => x.expense); const avg = spent.length ? spent.reduce((a, b) => a + b, 0) / spent.length : 0;
    const wrap = h('div', { class: 'chart' }); const tip = h('div', { class: 'tip' });
    series.forEach((x, i) => {
      const cx = pl + gw * i + gw / 2, last = i === n - 1, op = last ? 1 : .55;
      const g = s('g', { style: 'cursor:default' });
      g.append(s('rect', { x: pl + gw * i, y: pt, width: gw, height: H0 - pt - pb, fill: 'transparent' }));
      const r1 = s('rect', { x: cx - bw - 1.5, y: y(x.income), width: bw, height: Math.max(0, H0 - pb - y(x.income)), rx: 4, fill: 'var(--income)', opacity: op });
      const r2 = s('rect', { x: cx + 1.5, y: y(x.expense), width: bw, height: Math.max(0, H0 - pb - y(x.expense)), rx: 4, fill: 'var(--expense)', opacity: op });
      [r1, r2].forEach(r => { const hh = +r.getAttribute('height'); r.style.transformOrigin = `0 ${H0 - pb}px`; r.animate([{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], { duration: 500 + i * 30, easing: 'cubic-bezier(.2,.8,.2,1)' }); void hh; });
      g.append(r1, r2, s('text', { x: cx, y: H0 - 8, 'text-anchor': 'middle', 'font-size': 11.5, fill: last ? 'var(--ink)' : 'var(--muted)', 'font-weight': last ? 700 : 500 }, x.label));
      g.addEventListener('mouseenter', () => { tip.innerHTML = `<b>${x.full}</b><br><span style="color:#7ee2b8">In ${W(x.income)}</span> · <span style="color:#ffb3a3">Spent ${W(x.expense)}</span><br>Kept ${fmt(x.income - x.expense, B(), { whole: true, sign: true })}`;
        tip.style.left = (cx / W0 * 100) + '%'; tip.style.top = (y(Math.max(x.income, x.expense)) / H0 * 100) + '%'; tip.classList.add('on'); });
      g.addEventListener('mouseleave', () => tip.classList.remove('on'));
      svg.append(g);
    });
    if (avg) {
      svg.append(s('line', { x1: pl, x2: W0 - pr, y1: y(avg), y2: y(avg), stroke: 'var(--muted)', 'stroke-dasharray': '5 5', opacity: .7 }));
      svg.append(s('text', { x: pl + 2, y: y(avg) - 6, 'font-size': 11, fill: 'var(--muted)' }, 'Average spending ' + W(avg)));
    }
    wrap.append(svg, tip); return wrap;
  }
  function gauge(rate, size = 180) {
    const r = 70, c = Math.PI * r, v = Math.max(0, Math.min(1, rate / .4));
    const col = rate >= .2 ? 'var(--income)' : rate > 0 ? 'var(--warn)' : 'var(--expense)';
    const svg = s('svg', { viewBox: '0 0 180 104', width: size, style: 'max-width:100%' },
      s('path', { d: 'M20 95 A70 70 0 0 1 160 95', fill: 'none', stroke: 'var(--track)', 'stroke-width': 14, 'stroke-linecap': 'round' }));
    const arc = s('path', { d: 'M20 95 A70 70 0 0 1 160 95', fill: 'none', stroke: col, 'stroke-width': 14, 'stroke-linecap': 'round', 'stroke-dasharray': `${c} ${c}`, 'stroke-dashoffset': c });
    svg.append(arc, s('text', { x: 90, y: 82, 'text-anchor': 'middle', 'font-size': 26, 'font-weight': 750, fill: 'var(--ink)' }, Math.round(rate * 100) + '%'),
      s('text', { x: 90, y: 100, 'text-anchor': 'middle', 'font-size': 11, fill: 'var(--muted)' }, 'kept this month'));
    requestAnimationFrame(() => arc.animate([{ strokeDashoffset: c }, { strokeDashoffset: c * (1 - v) }], { duration: 800, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' }));
    return svg;
  }
  function spark(vals, color) {
    const w = 110, hh = 38, mx = Math.max(1, ...vals); const pts = vals.map((v, i) => `${(i / Math.max(1, vals.length - 1)) * w},${hh - 3 - (v / mx) * (hh - 6)}`).join(' ');
    return s('svg', { viewBox: `0 0 ${w} ${hh}`, width: w, height: hh }, s('polyline', { points: pts, fill: 'none', stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
  }
  function segbar(rows) { const tot = rows.reduce((a, r) => a + r[1], 0) || 1; return h('div', { class: 'segbar' }, rows.map(([n, v, c]) => h('i', { style: { width: (v / tot * 100) + '%', background: c }, title: `${n}: ${W(v)}` }))); }

  // ── navigation ──
  const NAV = [['overview', 'Overview', 'home'], ['transactions', 'Transactions', 'list'], ['transfers', 'Transfers', 'swap'], ['accounts', 'Accounts', 'wallet'], ['goals', 'Goals', 'target'],
    ['subscriptions', 'Subscriptions', 'repeat'], ['assets', 'Assets', 'box'], ['reports', 'Reports', 'chart'], ['settings', 'Settings', 'gear']];
  const ST = { month: null, search: '', account: '', kind: '', category: '', where: 'expense', goalFilter: 'all', sel: new Set(), tfMonth: null, repMonth: null, assetSel: null, showArch: false };
  const cur = () => (location.hash.match(/^#(\w+)/) || [])[1] || 'overview';
  function buildNav() {
    $('#nav').replaceChildren(...NAV.map(([k, t, i]) => h('a', { class: 'pillnav' + (k === cur() ? ' on' : ''), href: '#' + k }, ic(i), t)));
  }
  const page = () => $('#page');
  function head(title, sub, ...acts) { return h('div', { class: 'head' }, h('div', {}, h('h1', {}, title), sub ? h('div', { class: 'sub' }, sub) : null), h('div', { class: 'acts' }, acts)); }
  let busy = 0;
  async function reload() {
    const k = cur(), n = ++busy; buildNav();
    if (!page().children.length) page().append(h('div', { class: 'skel' }));
    try {
      const v = VIEWS[k] || VIEWS.overview; const el = await v();
      if (n !== busy) return;
      page().replaceChildren(el);
    } catch (e) { if (n === busy) page().replaceChildren(h('div', { class: 'empty' }, h('h2', {}, 'Something went wrong'), h('p', {}, e.message), btn('Try again', 'primary', reload))); }
  }

  // ── dialogs used everywhere ──
  const accOpts = (all) => META.accounts.filter(a => all || !a.archived).map(a => [a.id, `${a.name} · ${a.currency}`]);
  const catOpts = (kind) => META.categories.filter(c => !kind || c.kind === kind).map(c => [c.id, c.name]);
  function txDialog(t) {
    t = t || { kind: 'expense', date: today(), account_id: (META.accounts.find(a => !a.archived) || {}).id };
    const kindSel = { k: 'kind', label: 'Type', type: 'select', options: [['expense', 'Expense'], ['income', 'Income']], half: true };
    const f = [kindSel, { k: 'amount', label: 'Amount', type: 'amount', ph: '0', half: true },
      { k: 'title', label: 'Title', ph: 'What was it?' },
      { k: 'account', label: 'Account', type: 'select', options: accOpts(!!t.id), half: true },
      { k: 'category', label: 'Category', type: 'select', options: catOpts(t.kind), blank: 'No category', half: true },
      { k: 'date', label: 'Date', type: 'date', half: true }, { k: 'time', label: 'Time (optional)', type: 'time', half: true },
      { k: 'fee', label: 'Fee (optional)', type: 'amount', ph: '0', half: true, hint: 'Bank / wallet charge' }, { k: 'category_name', label: 'or a new category', ph: 'New category name', half: true },
      { k: 'note', label: 'Note', type: 'textarea' }];
    form(t.id ? 'Edit transaction' : 'New transaction', f,
      { kind: t.kind, amount: t.id ? plain(t.amount) : '', title: t.title, account: t.account_id, category: t.category_id, date: t.date, time: t.time, fee: t.fee ? plain(t.fee) : '', note: t.note },
      async (v) => { await api('tx_save', { ...v, id: t.id }); toast(t.id ? 'Saved' : 'Added'); await reload(); },
      { extra: t.id ? btn('Delete', 'ghost danger', async () => { if (await ask('Delete this transaction?')) { $('.scrim') && $('.scrim').remove(); await act('tx_delete', { ids: [t.id] }, 'Deleted'); } }) : null,
        onBuild: (body) => { body.elements.kind.addEventListener('change', () => { const c = body.elements.category; c.replaceChildren(...opts(catOpts(body.elements.kind.value), '', 'No category')); }); } });
  }
  async function editTx(id) { txDialog(await api('tx_get', { id })); }
  function tfDialog(t) {
    t = t || { date: today() };
    const accs = accOpts(!!t.id);
    form(t.id ? 'Edit transfer' : 'Move money', [
      { k: 'title', label: 'Title', ph: 'e.g. Savings for the month' },
      { k: 'from', label: 'From', type: 'select', options: accs, half: true }, { k: 'to', label: 'To', type: 'select', options: accs, half: true },
      { k: 'amount_out', label: 'Amount sent', type: 'amount', half: true }, { k: 'amount_in', label: 'Amount received', type: 'amount', half: true, hint: 'Only for a different currency' },
      { k: 'fee', label: 'Fee', type: 'amount', ph: '0', half: true }, { k: 'goal', label: 'Goal (optional)', type: 'select', options: META.goals.map(g => [g.id, g.name]), blank: 'No goal', half: true },
      { k: 'date', label: 'Date', type: 'date', half: true }, { k: 'time', label: 'Time (optional)', type: 'time', half: true },
      { k: 'note', label: 'Note', type: 'textarea' }],
      { title: t.title, from: t.from_account_id || (accs[0] || [])[0], to: t.to_account_id || (accs[1] || [])[0], amount_out: t.id ? plain(t.amount_out) : '', amount_in: t.id && t.amount_in !== t.amount_out ? plain(t.amount_in) : '',
        fee: t.fee ? plain(t.fee) : '', goal: t.goal || '', date: t.date, time: t.time, note: t.note },
      async (v) => { await api('tf_save', { ...v, id: t.id }); toast(t.id ? 'Saved' : 'Moved'); await reload(); },
      { extra: t.id ? btn('Delete', 'ghost danger', async () => { if (await ask('Delete this transfer?')) { $('.scrim').remove(); await act('tf_delete', { ids: [t.id] }, 'Deleted'); } }) : null });
  }
  function accDialog(a) {
    a = a || { kind: 'bank', currency: B() };
    form(a.id ? 'Edit account' : 'New account', [
      { k: 'name', label: 'Name', ph: 'e.g. Meezan Bank' },
      { k: 'kind', label: 'Kind', type: 'select', options: META.kinds, half: true },
      a.id ? null : { k: 'currency', label: 'Currency', ph: 'PKR', half: true },
      { k: 'opening', label: 'Opening balance', type: 'amount', ph: '0', half: !a.id ? true : false, hint: 'What was in it before you started counting' },
      { k: 'color', label: 'Colour', type: 'color' }, { k: 'note', label: 'Note', type: 'textarea' }],
      { name: a.name, kind: a.kind, currency: a.currency, opening: a.opening ? plain(a.opening) : '', color: a.color || META.colors[META.accounts.length % META.colors.length], note: a.note },
      async (v) => { await api('acc_save', { ...v, id: a.id }); toast('Saved'); await reload(); });
  }
  async function statementDialog(id) {
    const d = await api('statement', { account: id }); const a = d.account;
    const list = h('div', { style: { maxHeight: '60vh', overflow: 'auto' } }, d.rows.length ? d.rows.map(r => h('div', { class: 'li' },
      h('div', { class: 'm' }, h('div', { class: 't' }, r.title || (r.what === 'income' ? 'Income' : r.what === 'expense' ? 'Expense' : 'Transfer')), h('div', { class: 'faint' }, nice(r.date) + ' · ' + r.what.replace('_', ' '))),
      h('div', { class: 'right' }, h('div', { class: r.delta >= 0 ? 'income' : 'expense', style: { fontWeight: 650 } }, fmt(r.delta, a.currency, { sign: true })), h('div', { class: 'faint' }, fmt(r.balance, a.currency)))))
      : h('p', { class: 'muted' }, 'Nothing has happened in this account yet.'));
    modal(a.name, h('div', { class: 'mb', style: { display: 'block' } }, h('div', { class: 'hero', style: { fontSize: '30px' } }, fmt(d.balance, a.currency)), h('div', { class: 'faint', style: { marginBottom: '10px' } }, `${kindLabel(a.kind)} · opening ${fmt(a.opening, a.currency)}`), list),
      h('div', { class: 'mf' }, btn('Edit account', '', () => { $('.scrim').remove(); accDialog(META.accounts.find(x => x.id === id)); }), btn('Close', 'primary', () => $('.scrim').remove())), true);
  }

  // ══════════════ Overview ══════════════
  async function vOverview() {
    const d = await api('overview', { where: ST.where }); META = d.meta;
    const el = h('div', {});
    if (d.empty) {
      el.append(head('Overview', null), card(null, null, h('div', { class: 'empty', style: { padding: '30px 10px' } }, h('h2', {}, 'Welcome to Finance'),
        h('p', {}, 'Your money in one calm place: accounts, daily income and expenses, moving money, goals, subscriptions and the things you own.'),
        h('div', { class: 'row', style: { justifyContent: 'center', marginTop: '16px', flexWrap: 'wrap' } }, btn('Add my first account', 'primary', () => accDialog(), 'plus'),
          h('a', { class: 'btn', href: '/#/settings', target: '_top' }, 'Import from the desktop app')))));
      return el;
    }
    const hidden = new Set((META.settings.overview_hidden || '').split(',').filter(Boolean));
    const ms = d.month, last = d.last, b = B(), lastName = MONTHS[(+thisMonth().slice(5) + 10) % 12];
    el.append(head('Overview', new Date(today() + 'T00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
      btn('Customize', 'ghost', (e) => customize(e.currentTarget, hidden)), btn('Move money', '', () => tfDialog(), 'swap'), btn('New transaction', 'primary', () => txDialog(), 'plus')));
    const delta = (now, before, goodUp) => { if (!before) return chip('No data for ' + lastName); const p = (now - before) / before * 100, up = p >= 0; return chip(`${up ? '▲' : '▼'} ${Math.abs(p).toFixed(0)}% vs ${lastName}`, up === goodUp ? 'green' : 'red'); };
    // balance + recent
    const accs = META.accounts.filter(a => !a.archived); const cols = Math.max(2, Math.min(4, Math.ceil((accs.length + 1) / 2)));
    const wallets = h('div', { class: 'wallets', style: { '--cols': cols } }, accs.map((a, i) => h('button', { class: 'wallet', style: { '--c': a.color || 'var(--accent)' }, title: 'Every movement of this account', onclick: () => statementDialog(a.id) },
      h('div', { class: 'nm' }, a.name), h('div', { class: 'am' }, fmt(a.balance, a.currency, { whole: true })), h('div', { class: 'ft' }, h('span', {}, kindLabel(a.kind)), h('span', {}, a.currency)))),
      h('button', { class: 'addcard', onclick: () => accDialog() }, '+ Add account'));
    wallets.style.setProperty('--cols', cols);
    const balance = card('Balance', [chip(b), btn('All accounts', 'ghost sm', () => location.hash = '#accounts')], h('div', { class: 'hero' }, W(d.net.accounts)),
      d.net.assets ? h('div', { class: 'muted' }, `Net worth with the things you own: ${W(d.net.total)}`) : null, wallets);
    const recent = card('Recent transactions', btn('View all', 'ghost sm', () => location.hash = '#transactions'),
      d.recent.length ? d.recent.map(t => { const name = t.title || t.category_name || (t.kind === 'income' ? 'Income' : 'Expense'); const c = catById(t.category_id);
        return h('div', { class: 'li', style: { cursor: 'pointer' }, onclick: () => editTx(t.id) }, h('div', { class: 'av', style: { background: c && c.color || (t.kind === 'income' ? 'var(--income)' : 'var(--expense)') } }, name[0].toUpperCase()),
          h('div', { class: 'm' }, h('div', { class: 't' }, name), h('div', { class: 'faint' }, nice(t.date) + (t.category_name ? ' · ' + t.category_name : ''))),
          h('div', { class: 'right' }, h('div', { class: t.kind, style: { fontWeight: 700 } }, fmt(t.net, t.currency, { sign: true })), h('div', { class: 'faint' }, t.account_name))); })
        : h('p', { class: 'muted' }, 'No transactions yet — press “New transaction”.'));
    el.append(h('div', { class: 'g ' + (hidden.has('recent') ? '' : 'g2'), style: { marginBottom: '16px' } }, balance, hidden.has('recent') ? null : recent));
    if (d.net.missing.length || ms.missing.length) el.append(h('div', { class: 'banner' }, h('div', { class: 'grow' }, `No exchange rate for ${[...new Set([...d.net.missing, ...ms.missing])].join(', ')} — set it in Settings so totals include those accounts.`), btn('Set rate', 'soft sm', () => location.hash = '#settings')));
    if (d.due.length) el.append(h('div', { class: 'banner' }, h('div', { class: 'grow' }, `${d.due.length} subscription charge${d.due.length > 1 ? 's' : ''} due — ${[...new Set(d.due.map(x => x.name))].join(', ')}`), btn('Add them now', 'soft sm', () => act('sub_post_due', {}, 'Added'))));
    // KPIs
    const limit = +META.settings.spend_limit || 0;
    const kIn = card('Money in', delta(ms.income, last.income, true), h('div', { class: 'big income' }, W(ms.income)),
      h('div', { class: 'muted' }, `Last month ${W(last.income)} · 6-month average ${W(d.avg_income)}`), h('div', { style: { margin: '10px 0 4px' } }, bar(d.avg_income ? ms.income / d.avg_income : 0, 'var(--income)')),
      h('div', { class: 'faint' }, d.avg_income ? 'Bar full = your usual month' : 'Your average appears after a few months'));
    let spendBody;
    if (limit) {
      const used = ms.expense / limit, left = limit - ms.expense, col = used < .7 ? 'var(--income)' : used < 1 ? 'var(--warn)' : 'var(--expense)';
      spendBody = [h('div', { style: { margin: '10px 0 4px' } }, bar(used, col)), h('div', { class: 'muted' }, left >= 0 ? `${W(left)} left of ${W(limit)} · about ${W(Math.floor(left / d.days_left))} a day for ${d.days_left} days` : `Over your limit by ${W(-left)} (limit ${W(limit)})`),
        btn('Change limit', 'ghost sm', setLimit)];
    } else spendBody = [h('div', { class: 'muted' }, `Last month ${W(last.expense)} · 6-month average ${W(d.avg_expense)}`), h('div', { style: { marginTop: '10px' } }, btn('Set a monthly spending limit', 'soft sm', setLimit, 'plus'))];
    const kOut = card('Spent', delta(ms.expense, last.expense, false), h('div', { class: 'big expense' }, W(ms.expense)), spendBody);
    const rate = ms.income > 0 ? ms.net / ms.income : 0;
    const kSave = card('Saved', delta(ms.net, last.net, true), h('div', { class: 'big', style: { color: ms.net >= 0 ? 'var(--income)' : 'var(--expense)' } }, fmt(ms.net, b, { whole: true, sign: true })),
      h('div', { class: 'muted' }, ms.income > 0 ? `You kept ${Math.max(0, rate * 100).toFixed(0)}% of what came in · aim for 20% or more` : 'Income minus spending'),
      h('div', { style: { margin: '10px 0 4px' } }, bar(rate < .2 ? Math.max(0, rate) / .2 : 1, rate >= .2 ? 'var(--income)' : 'var(--warn)')), h('div', { class: 'faint' }, 'Bar full = 20% saved'));
    el.append(h('div', { class: 'g g3 rise', style: { marginBottom: '16px' } }, kIn, kOut, kSave));
    // cash flow · health · emergency
    if (!hidden.has('flow')) {
      const flow = card('Cash flow', null, h('div', { class: 'legend' }, dot('var(--income)', 9), 'Money in', dot('var(--expense)', 9), 'Spent', h('span', { class: 'faint' }, '· last 12 months · hover a month')), cashflow(d.flow));
      const health = card('Financial health', null, h('div', { style: { display: 'flex', justifyContent: 'center' } }, gauge(rate)),
        h('div', { class: 'muted', style: { textAlign: 'center' } }, rate >= .2 ? 'Healthy — you keep a good part of what comes in.' : rate > 0 ? 'Okay — try to keep at least 20% of what comes in.' : 'You spent more than came in this month.'));
      let em;
      if (!d.emergency) em = card('Emergency fund', null, h('p', { class: 'muted', style: { marginTop: 0 } }, `Money kept only for bad days — work stops, illness, the PC breaks. Keep about ${d.emergency_months} months of spending in one account you do not touch.`), btn('Choose the account', 'soft sm', setEmergency, 'plus'));
      else {
        const e = d.emergency, m = d.emergency_months, okc = e.cover >= m ? 'var(--income)' : e.cover >= 3 ? 'var(--warn)' : 'var(--expense)';
        em = card('Emergency fund', btn('Change', 'ghost sm', setEmergency), h('div', { class: 'big', style: { color: okc } }, `${e.cover.toFixed(1)} months covered`), h('div', { style: { margin: '10px 0 6px' } }, bar(e.target ? e.have / e.target : 0, e.cover >= m ? 'var(--income)' : 'var(--warn)')),
          h('div', { class: 'muted' }, e.target ? `${e.account.name}: ${fmt(e.have, e.account.currency, { whole: true })} of ${W(e.target)} (${m} months)` : `${e.account.name}: ${fmt(e.have, e.account.currency, { whole: true })} — your average spending appears after a month or two`),
          e.target && e.have < e.target ? h('div', { class: 'faint' }, `${W(e.target - e.have)} more to reach ${m} months`) : null);
      }
      el.append(h('div', { class: 'g g2', style: { marginBottom: '16px' } }, flow, h('div', { class: 'g' }, health, em)));
    }
    // where · goals · subs · depreciation · assets
    const cards = [];
    if (!hidden.has('where')) {
      const tot = d.where.reduce((a, r) => a + r[1], 0);
      cards.push(card(`${d.where_kind === 'expense' ? 'Spending' : 'Income'} in ${MONTHS[+thisMonth().slice(5) - 1]}`, seg([['expense', 'Spending'], ['income', 'Income']], d.where_kind, (v) => { ST.where = v; reload(); }),
        tot ? [h('div', { class: 'big' }, W(tot)), segbar(d.where), d.where.map(([n, v, c]) => h('div', { class: 'li', style: { padding: '5px 0' } }, dot(c), h('div', { class: 'm' }, n), h('span', { class: 'muted' }, W(v)), h('b', { style: { width: '46px', textAlign: 'right' } }, Math.round(v * 100 / tot) + '%')))]
          : h('p', { class: 'muted' }, 'Nothing yet this month.')));
    }
    if (!hidden.has('goals')) cards.push(card('My goals', btn('All', 'ghost sm', () => location.hash = '#goals'), d.goals.length ? d.goals.map((g, i) => h('div', { class: 'li' },
      h('div', { class: 'av', style: { background: META.cat_colors[i % META.cat_colors.length] } }, g.name[0].toUpperCase()), h('div', { class: 'm' }, h('div', { class: 't' }, g.name), h('div', { class: 'faint' }, `${fmt(g.saved, g.currency, { whole: true })} of ${fmt(g.target, g.currency, { whole: true })}`), h('div', { style: { marginTop: '5px' } }, bar(g.progress))),
      h('b', {}, Math.round(g.progress * 100) + '%'))) : [h('p', { class: 'muted' }, 'No goals yet. Add something you are saving for — a new phone, a camera, a trip.'), btn('Add a goal', 'soft sm', () => goalDialog(), 'plus')]));
    if (!hidden.has('subs')) cards.push(card('Subscriptions', btn('All', 'ghost sm', () => location.hash = '#subscriptions'), d.subs_next.length || d.subs_monthly ? [h('div', { class: 'big', style: { fontSize: '20px' } }, W(d.subs_monthly) + ' a month'),
      d.subs_next.map(x => h('div', { class: 'li' }, h('div', { class: 'm' }, x.name), h('span', { class: 'muted' }, nice(x.date)), h('b', {}, fmt(x.cost, x.currency))))] : h('p', { class: 'muted' }, 'No subscriptions yet.')));
    if (!hidden.has('depr')) {
      const mo = d.depr_month.reduce((a, r) => a + r[1], 0), yr = d.depr_year.reduce((a, r) => a + r[1], 0);
      cards.push(card('Depreciation', null, mo || yr ? [h('div', { class: 'row', style: { gap: '30px' } }, h('div', {}, h('div', { class: 'muted' }, 'This month'), h('div', { class: 'big expense' }, W(mo))), h('div', {}, h('div', { class: 'muted' }, 'This year'), h('div', { class: 'big expense' }, W(yr)))),
        d.depr_year.slice(0, 4).map(([n, v]) => h('div', { class: 'li' }, h('div', { class: 'm' }, n), h('span', { class: 'muted' }, W(v) + ' this year'))), h('div', { class: 'faint' }, 'Value your things lose — set this aside to replace them. It is not taken from any account.')]
        : [h('p', { class: 'muted' }, 'Add the things you own in Assets (PC, camera, phone…) to see how much value they lose each month and year.'), btn('Add an asset', 'soft sm', () => location.hash = '#assets', 'plus')]));
    }
    if (!hidden.has('assets')) cards.push(card('Things you own', btn('All', 'ghost sm', () => location.hash = '#assets'), d.assets.count ? h('div', { class: 'row', style: { gap: '30px', flexWrap: 'wrap' } },
      [['Worth today', W(d.assets.worth)], ['Loses each month', W(d.assets.monthly)], ['Items', d.assets.count]].map(([c, v]) => h('div', {}, h('div', { class: 'muted' }, c), h('div', { class: 'big' }, v)))) : h('p', { class: 'muted' }, 'Add your PC, phone or equipment to see their value and monthly depreciation.')));
    el.append(h('div', { class: 'g gauto rise' }, cards));
    return el;
  }
  function customize(at, hidden) {
    const CARDS = [['flow', 'Cash flow, health and emergency fund'], ['where', 'Where the money went'], ['recent', 'Recent activity'], ['depr', 'Depreciation'], ['subs', 'Subscriptions'], ['goals', 'Goals'], ['assets', 'Things you own']];
    menu(at, CARDS.map(([k, t]) => ({ t: (hidden.has(k) ? '☐  ' : '☑  ') + t, fn: () => { hidden.has(k) ? hidden.delete(k) : hidden.add(k); act('settings_set', { overview_hidden: [...hidden].join(',') }); } })));
  }
  function setLimit() {
    form('Monthly spending limit', [{ k: 'spend_limit', label: `How much can you spend in a month? (${B()}, 0 = no limit)`, type: 'amount' }], { spend_limit: plain(+META.settings.spend_limit || 0) },
      async (v) => { await api('settings_set', v); await reload(); });
  }
  function setEmergency() {
    form('Emergency fund', [{ k: 'emergency_account', label: 'Which account holds your emergency money?', type: 'select', options: accOpts() },
      { k: 'emergency_months', label: 'How many months of spending should it cover?', type: 'number', min: 1, max: 24 }],
      { emergency_account: META.settings.emergency_account, emergency_months: META.settings.emergency_months || 6 }, async (v) => { await api('settings_set', v); await reload(); });
  }

  // ══════════════ Transactions ══════════════
  function monthNav(m, set) {
    return h('div', { class: 'monthnav' }, h('button', { title: 'Previous month', onclick: () => set(addMonths(m || thisMonth(), -1)) }, ic('left')),
      h('span', { title: 'Click: this month / all time', onclick: () => set(m ? '' : thisMonth()) }, m ? monthLabel(m) : 'All time'), h('button', { title: 'Next month', onclick: () => set(addMonths(m || thisMonth(), 1)) }, ic('right')));
  }
  async function vTransactions() {
    if (ST.month === null) ST.month = thisMonth();
    const d = await api('transactions', { month: ST.month, search: ST.search, account: ST.account, kind: ST.kind, category: ST.category }); META = d.meta;
    ST.sel = new Set([...ST.sel].filter(id => d.rows.some(r => r.id === id)));
    const el = h('div', {});
    el.append(head('Transactions', `${d.rows.length} ${d.rows.length === 1 ? 'entry' : 'entries'}`, btn('New transaction', 'primary', () => txDialog(), 'plus')));
    const search = h('input', { class: 'inp', placeholder: 'Search title, note, category, account', value: ST.search, style: { flex: '1', minWidth: '180px' } });
    let tm; search.addEventListener('input', () => { clearTimeout(tm); tm = setTimeout(() => { ST.search = search.value; reload().then(() => { const s2 = $('.toolbar .inp'); if (s2) { s2.focus(); s2.setSelectionRange(s2.value.length, s2.value.length); } }); }, 300); });
    const sel = (val, list, blank, key) => h('select', { class: 'inp', onchange: (e) => { ST[key] = e.target.value; reload(); } }, opts(list, val, blank));
    el.append(h('div', { class: 'toolbar' }, monthNav(ST.month, (m) => { ST.month = m; reload(); }), search, sel(ST.account, accOpts(true), 'All accounts', 'account'),
      sel(ST.kind, [['income', 'Income'], ['expense', 'Expenses']], 'All types', 'kind'), sel(ST.category, catOpts(), 'All categories', 'category')));
    el.append(h('div', { class: 'sum' }, h('span', {}, 'Money in ', h('b', { class: 'income' }, W(d.income))), h('span', {}, 'Spent ', h('b', { class: 'expense' }, W(d.expense))), h('span', {}, 'Net ', h('b', {}, fmt(d.income - d.expense, B(), { whole: true, sign: true })))));
    if (!d.rows.length) { el.append(card(null, null, h('div', { class: 'empty' }, h('h2', {}, 'Nothing here'), h('p', {}, ST.search || ST.account || ST.kind || ST.category ? 'No entry matches these filters.' : 'No transactions in this month yet.')))); return el; }
    const all = h('input', { type: 'checkbox', title: 'Select all', checked: ST.sel.size === d.rows.length, onclick: (e) => { e.stopPropagation(); ST.sel = e.target.checked ? new Set(d.rows.map(r => r.id)) : new Set(); paintSel(); } });
    const tb = h('tbody', {}, d.rows.map(t => {
      const c = catById(t.category_id);
      const ck = h('input', { type: 'checkbox', checked: ST.sel.has(t.id), onclick: (e) => { e.stopPropagation(); e.target.checked ? ST.sel.add(t.id) : ST.sel.delete(t.id); paintSel(); } });
      return h('tr', { 'data-id': t.id, class: ST.sel.has(t.id) ? 'sel' : '', onclick: () => editTx(t.id) },
        h('td', { class: 'ck' }, ck), h('td', { class: 'sm nowrap' }, nice(t.date) + (t.time ? ' · ' + t12(t.time) : '')),
        h('td', { class: 't' }, t.title || (c ? c.name : (t.kind === 'income' ? 'Income' : 'Expense'))), h('td', { class: 'muted', 'data-m': 'hide' }, t.note || ''),
        h('td', { class: 'sm' }, h('span', { class: 'row', style: { gap: '6px' } }, dot(t.account_color || 'var(--muted)', 8), t.account_name)),
        h('td', { class: 'sm' }, c ? h('span', { class: 'catpill' }, dot(catColor(c), 8), c.name) : h('span', { class: 'faint' }, '—')),
        h('td', { class: 'amt right nowrap ' + t.kind, style: { fontWeight: 700 } }, fmt(t.net, t.currency, { sign: true })), h('td', { class: 'right faint', 'data-m': 'hide' }, t.fee ? fmt(t.fee, t.currency) : ''));
    }));
    el.append(h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', { class: 'ck' }, all), h('th', {}, 'Date'), h('th', {}, 'Title'), h('th', {}, 'Note'), h('th', {}, 'Account'), h('th', {}, 'Category'), h('th', { class: 'right' }, 'Amount'), h('th', { class: 'right' }, 'Fee'))), tb));
    function paintSel() {
      $$('tr[data-id]', tb).forEach(tr => { const on = ST.sel.has(+tr.dataset.id); tr.classList.toggle('sel', on); tr.querySelector('input').checked = on; });
      all.checked = ST.sel.size === d.rows.length; $$('.bulk').forEach(b => b.remove());
      if (!ST.sel.size) return;
      const ids = [...ST.sel];
      document.body.append(h('div', { class: 'bulk' }, h('b', { style: { marginRight: '6px' } }, `${ids.length} selected`),
        btn('Date', 'sm', () => form('Change date', [{ k: 'date', label: `New date for ${ids.length} entries`, type: 'date' }], { date: today() }, async (v) => { await api('tx_bulk', { ids, date: v.date }); toast('Changed'); ST.sel.clear(); await reload(); }), 'cal'),
        btn('Category', 'sm', () => form('Change category', [{ k: 'category', label: 'Category', type: 'select', options: catOpts() }], {}, async (v) => { await api('tx_bulk', { ids, category: v.category }); toast('Changed'); ST.sel.clear(); await reload(); }), 'tag'),
        btn('Account', 'sm', () => form('Change account', [{ k: 'account', label: 'Account', type: 'select', options: accOpts() }], {}, async (v) => { await api('tx_bulk', { ids, account: v.account }); toast('Changed'); ST.sel.clear(); await reload(); }), 'wallet'),
        btn('Delete', 'sm danger', async () => { if (await ask(`Delete ${ids.length} transaction${ids.length > 1 ? 's' : ''}?`)) { ST.sel.clear(); $$('.bulk').forEach(b => b.remove()); await act('tx_bulk', { ids, delete: true }, 'Deleted'); } }, 'trash'),
        btn('', 'ghost sm icon', () => { ST.sel.clear(); paintSel(); }, 'x')));
    }
    setTimeout(paintSel, 0);
    return el;
  }

  // ══════════════ Transfers ══════════════
  async function vTransfers() {
    if (ST.tfMonth === null) ST.tfMonth = thisMonth();
    const d = await api('transfers', { month: ST.tfMonth, search: ST.search }); META = d.meta;
    const el = h('div', {}, head('Transfers', 'Money moved between your own accounts', btn('Move money', 'primary', () => tfDialog(), 'swap')),
      h('div', { class: 'toolbar' }, monthNav(ST.tfMonth, (m) => { ST.tfMonth = m; reload(); })));
    if (!d.rows.length) { el.append(card(null, null, h('div', { class: 'empty' }, h('h2', {}, 'No transfers'), h('p', {}, 'Nothing was moved between accounts in this month.')))); return el; }
    const hasNote = d.rows.some(r => r.note && r.note !== r.title);
    el.append(h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, 'Date'), h('th', {}, 'Title'), h('th', {}, 'From → To'), h('th', { class: 'right' }, 'Sent'), h('th', { class: 'right' }, 'Received'), h('th', { class: 'right' }, 'Fee'), hasNote ? h('th', {}, 'Note') : null)),
      h('tbody', {}, d.rows.map(f => h('tr', { onclick: async () => tfDialog(await api('tf_get', { id: f.id })) },
        h('td', { class: 'sm nowrap' }, nice(f.date) + (f.time ? ' · ' + t12(f.time) : '')), h('td', { class: 't' }, f.title || f.note || 'Transfer', f.goal_name ? h('span', { class: 'chip accent', style: { marginLeft: '8px' } }, '🎯 ' + f.goal_name) : null),
        h('td', { class: 'sm' }, h('span', { class: 'row', style: { gap: '6px', flexWrap: 'wrap' } }, dot(f.from_color || 'var(--muted)', 8), f.from_name, '→', dot(f.to_color || 'var(--muted)', 8), f.to_name)),
        h('td', { class: 'amt right nowrap', style: { fontWeight: 700 } }, fmt(f.amount_out, f.from_cur)), h('td', { class: 'right nowrap', 'data-m': f.from_cur === f.to_cur ? 'hide' : null }, fmt(f.amount_in, f.to_cur)),
        h('td', { class: 'right faint', 'data-m': 'hide' }, f.fee ? fmt(f.fee, f.from_cur) : ''), hasNote ? h('td', { class: 'muted', 'data-m': 'hide' }, f.note && f.note !== f.title ? f.note : '') : null)))));
    return el;
  }

  // ══════════════ Accounts ══════════════
  async function vAccounts() {
    const d = await api('accounts'); META = d.meta;
    const rows = d.rows.filter(a => ST.showArch || !a.archived); const arch = d.rows.filter(a => a.archived).length;
    const el = h('div', {}, head('Accounts', 'Where your money sits', arch ? btn(ST.showArch ? 'Hide archived' : `Show archived (${arch})`, 'ghost', () => { ST.showArch = !ST.showArch; reload(); }) : null, btn('New account', 'primary', () => accDialog(), 'plus')));
    if (!rows.length) { el.append(card(null, null, h('div', { class: 'empty' }, h('h2', {}, 'No accounts yet'), h('p', {}, 'Add the places your money sits — bank, cash, wallet.')))); return el; }
    el.append(h('div', { class: 'g gauto rise' }, rows.map(a => {
      const more = btn('', 'ghost sm icon', (e) => { e.stopPropagation(); menu(e.currentTarget, [{ t: 'Every movement', fn: () => statementDialog(a.id) }, { t: 'Edit', fn: () => accDialog(a) },
        { t: a.archived ? 'Bring back' : 'Archive', fn: () => act('acc_archive', { id: a.id, on: !a.archived }, a.archived ? 'Back' : 'Archived') }, '-',
        { t: 'Delete', danger: true, fn: async () => { if (await ask(a.active ? `“${a.name}” has entries. Deleting it deletes them too. Archive it instead?` : `Delete “${a.name}”?`, 'Delete')) act('acc_delete', { id: a.id }, 'Deleted'); } }]); }, 'more');
      return h('div', { class: 'card', style: { cursor: 'pointer', opacity: a.archived ? .6 : 1 }, onclick: () => statementDialog(a.id) },
        h('div', { class: 'row' }, h('div', { class: 'av', style: { background: a.color || 'var(--accent)' } }, a.name[0].toUpperCase()), h('div', { class: 'grow' }, h('div', { style: { fontWeight: 700, fontSize: '16px' } }, a.name), h('div', { class: 'faint' }, `${kindLabel(a.kind)} · ${a.currency}${a.archived ? ' · archived' : ''}`)), more),
        h('div', { class: 'big', style: { margin: '14px 0 8px' } }, fmt(a.balance, a.currency, { whole: true })),
        h('div', { class: 'row', style: { gap: '16px' } }, h('span', { class: 'muted' }, 'This month '), h('span', { class: 'income' }, '+' + fmt(a.month_in, a.currency, { whole: true })), h('span', { class: 'expense' }, '−' + fmt(a.month_out, a.currency, { whole: true }))));
    })));
    return el;
  }

  // ══════════════ Goals ══════════════
  function goalDialog(g) {
    g = g || {};
    form(g.id ? 'Edit goal' : 'New goal', [{ k: 'name', label: 'What are you saving for?', ph: 'e.g. New phone' }, { k: 'target', label: 'Amount needed', type: 'amount', half: true },
      { k: 'initial', label: 'Already saved', type: 'amount', ph: '0', half: true }, { k: 'due', label: 'By when (optional)', type: 'date', half: true },
      g.id ? null : { k: 'currency', label: 'Currency', ph: B(), half: true }, { k: 'note', label: 'Note', type: 'textarea' }],
      { name: g.name, target: g.id ? plain(g.target) : '', initial: g.initial ? plain(g.initial) : '', due: g.due, note: g.note }, async (v) => { await api('goal_save', { ...v, id: g.id }); toast('Saved'); await reload(); });
  }
  function moneyDialog(g) {
    form(`Add money · ${g.name}`, [{ k: 'amount', label: 'Amount', type: 'amount', half: true }, { k: 'date', label: 'Date', type: 'date', half: true },
      { k: 'from', label: 'Move it from (optional)', type: 'select', options: accOpts(), blank: '— just note it —', half: true }, { k: 'to', label: 'to', type: 'select', options: accOpts(), blank: '—', half: true },
      { k: 'note', label: 'Note' }], { date: today() }, async (v) => { await api('goal_add_money', { ...v, id: g.id }); toast('Added'); await reload(); });
  }
  async function goalHistory(g) {
    const d = await api('goal_history', { goal: g.id }); const G = d.goal;
    const body = h('div', { class: 'mb', style: { display: 'block' } }, h('div', { class: 'row', style: { gap: '20px', flexWrap: 'wrap' } }, h('div', {}, h('div', { class: 'muted' }, 'Saved'), h('div', { class: 'big' }, fmt(G.saved, G.currency, { whole: true }))),
      h('div', {}, h('div', { class: 'muted' }, 'Target'), h('div', { class: 'big' }, fmt(G.target, G.currency, { whole: true })))), h('div', { style: { margin: '10px 0 16px' } }, bar(G.progress)),
      h('h3', { style: { margin: '0 0 6px', fontSize: '14px' } }, 'When money was added'),
      d.rows.length ? d.rows.map(c => h('div', { class: 'li' }, h('div', { class: 'm' }, h('div', { class: 't' }, nice(c.date)), h('div', { class: 'faint' }, c.from_name ? `${c.from_name} → ${c.to_name}` : (c.note || 'Noted'))),
        h('b', { class: c.amount >= 0 ? 'income' : 'expense' }, fmt(c.amount, G.currency, { sign: true })), btn('', 'ghost sm icon', async () => { if (await ask('Remove this entry?' + (c.transfer_id ? ' The transfer it made is removed too.' : ''))) { $$('.scrim').forEach(x => x.remove()); await act('goal_del_money', { id: c.id }, 'Removed'); } }, 'trash')))
        : h('p', { class: 'muted' }, G.initial ? `Started with ${fmt(G.initial, G.currency)} already saved.` : 'No money added yet.'));
    modal(G.name, body, h('div', { class: 'mf' }, btn('Add money', 'soft', () => { $('.scrim').remove(); moneyDialog(G); }, 'plus'), btn('Close', 'primary', () => $('.scrim').remove())), true);
  }
  async function vGoals() {
    const d = await api('goals'); META = d.meta;
    const cnt = { open: 0, done: 0, failed: 0 }; d.rows.forEach(g => cnt[g.state]++);
    const shown = d.rows.filter(g => ST.goalFilter === 'all' || g.state === ST.goalFilter);
    const el = h('div', {}, head('Goals', `${cnt.open} in progress · ${cnt.done} completed · ${cnt.failed} failed`, btn('New goal', 'primary', () => goalDialog(), 'plus')),
      h('div', { class: 'toolbar' }, seg([['all', 'All'], ['open', 'In progress'], ['done', 'Completed'], ['failed', 'Failed']], ST.goalFilter, (v) => { ST.goalFilter = v; reload(); })));
    if (!shown.length) { el.append(card(null, null, h('div', { class: 'empty' }, h('h2', {}, 'No goals here'), h('p', {}, 'Add something you are saving for — a camera, a trip, a new PC.')))); return el; }
    el.append(h('div', { class: 'g gauto rise' }, shown.map(g => {
      const st = { done: chip('Completed', 'green'), failed: chip('Failed', 'red'), open: chip('In progress', 'blue') }[g.state];
      const more = btn('', 'ghost sm icon', (e) => { e.stopPropagation(); menu(e.currentTarget, [{ t: 'History', fn: () => goalHistory(g) }, { t: 'Edit', fn: () => goalDialog(g) },
        g.completed ? { t: 'Not completed (reopen)', fn: () => act('goal_reopen', { id: g.id }, 'Reopened') } : { t: 'Mark completed', fn: () => form('Completed — bought it?', [{ k: 'date', label: 'Date', type: 'date', half: true }, { k: 'account', label: 'Record the purchase from (optional)', type: 'select', options: accOpts(), blank: '— don’t record —', half: true }, { k: 'amount', label: 'Price paid (optional)', type: 'amount', ph: plain(g.target) }], { date: today() }, async (v) => { await api('goal_complete', { ...v, id: g.id }); toast('Completed 🎉'); await reload(); }) }, '-',
        { t: 'Delete', danger: true, fn: async () => { if (await ask(`Delete the goal “${g.name}”? Money transfers made for it stay.`)) act('goal_delete', { id: g.id }, 'Deleted'); } }]); }, 'more');
      const pct = Math.round(g.progress * 100);
      return h('div', { class: 'card goal', onclick: () => goalHistory(g) }, h('div', { class: 'row' }, h('div', { class: 'nm grow' }, g.name), st, more),
        h('div', { class: 'big' }, fmt(g.target, g.currency, { whole: true })), bar(g.progress, g.state === 'failed' ? 'var(--expense)' : g.state === 'done' ? 'var(--income)' : 'var(--accent)'),
        h('div', { class: 'row' }, h('span', { class: 'muted grow' }, `${fmt(g.saved, g.currency, { whole: true })} saved · ${pct}%`), g.completed ? h('span', { class: 'faint' }, 'Bought ' + nice(g.completed_on)) : g.due ? h('span', { class: g.state === 'failed' ? 'expense' : 'faint', style: { fontSize: '12.5px' } }, 'By ' + nice(g.due)) : null),
        g.completed ? null : h('div', {}, btn('Add money', 'soft sm', (e) => { e.stopPropagation(); moneyDialog(g); }, 'plus')));
    })));
    return el;
  }

  // ══════════════ Subscriptions ══════════════
  function subDialog(x) {
    x = x || { every_months: 1, billing_day: +today().slice(8, 10) };
    form(x.id ? 'Edit subscription' : 'New subscription', [{ k: 'name', label: 'Name', ph: 'e.g. Spotify' }, { k: 'cost', label: 'Price', type: 'amount', half: true },
      { k: 'account', label: 'Paid from', type: 'select', options: accOpts(), half: true },
      { k: 'every', label: 'Every … months', type: 'number', min: 1, max: 36, half: true }, { k: 'day', label: 'Billing day', type: 'number', min: 1, max: 31, half: true },
      { k: 'category', label: 'Category', type: 'select', options: catOpts('expense'), blank: 'Subscriptions', half: true },
      x.id ? null : { k: 'start', label: 'Starts (month)', type: 'month', half: true }, x.id ? null : { k: 'months', label: 'For how many months (empty = until you stop)', type: 'number', min: 1 },
      x.id ? null : { k: 'backfill', label: 'Also add the past months since it started', type: 'check' }, { k: 'note', label: 'Note', type: 'textarea' }],
      { name: x.name, cost: x.id ? plain(x.cost) : '', account: x.account_id, every: x.every_months, day: x.billing_day, category: x.category_id, start: thisMonth(), note: x.note },
      async (v) => { await api('sub_save', { ...v, id: x.id }); toast('Saved'); await reload(); });
  }
  async function subHistory(x) {
    const d = await api('sub_history', { sub: x.id });
    modal(x.name, h('div', { class: 'mb', style: { display: 'block' } }, h('div', { class: 'muted', style: { marginBottom: '10px' } }, `${fmt(x.cost, x.currency)} every ${x.every_months > 1 ? x.every_months + ' months' : 'month'} on day ${x.billing_day} · ${x.account_name}`),
      d.charges.length ? d.charges.map(c => h('div', { class: 'li' }, h('div', { class: 'm' }, monthLabel(c.month)), c.state === 'posted' ? chip('Paid', 'green') : chip('Skipped'), h('b', {}, fmt(c.amount, x.currency)))) : h('p', { class: 'muted' }, 'No charges yet.')),
      h('div', { class: 'mf' }, btn('Close', 'primary', () => $('.scrim').remove())));
  }
  async function vSubs() {
    const d = await api('subscriptions'); META = d.meta;
    const el = h('div', {}, head('Subscriptions', `${W(d.monthly)} a month for the active ones`, btn('New subscription', 'primary', () => subDialog(), 'plus')));
    if (d.due.length) el.append(h('div', { class: 'banner' }, h('div', { class: 'grow' }, `${d.due.length} charge${d.due.length > 1 ? 's' : ''} due`), btn('Add them now', 'soft sm', () => act('sub_post_due', {}, 'Added'))));
    if (!d.rows.length) { el.append(card(null, null, h('div', { class: 'empty' }, h('h2', {}, 'No subscriptions'), h('p', {}, 'Add what you pay every month — the expense is added on its day.')))); return el; }
    const STC = { active: ['Active', 'green'], paused: ['Paused', 'amber'], ended: ['Ended', ''], scheduled: ['Starts later', 'blue'], finished: ['Finished', ''] };
    el.append(h('div', { class: 'g rise' }, d.rows.map(x => {
      const st = STC[x.state] || [x.state, ''];
      const more = btn('', 'ghost sm icon', (e) => { e.stopPropagation(); menu(e.currentTarget, [{ t: 'History', fn: () => subHistory(x) }, { t: 'Edit', fn: () => subDialog(x) },
        x.next_month ? { t: `Skip ${monthLabel(x.next_month)}`, fn: () => act('sub_skip', { id: x.id, month: x.next_month }, 'Skipped') } : null,
        x.state === 'active' ? { t: 'Pause from this month', fn: () => act('sub_pause', { id: x.id, month: thisMonth() }, 'Paused') } : { t: 'Resume', fn: () => act('sub_resume', { id: x.id }, 'Resumed') },
        x.state !== 'ended' ? { t: 'End (keep history)', fn: () => act('sub_end', { id: x.id, month: addMonths(thisMonth(), -1) }, 'Ended') } : null, '-',
        { t: 'Delete', danger: true, fn: async () => { if (await ask(`Delete “${x.name}”? Its past expenses stay.`)) act('sub_delete', { id: x.id }, 'Deleted'); } }].filter(Boolean)); }, 'more');
      return h('div', { class: 'card row', style: { cursor: 'pointer', padding: '14px 16px' }, onclick: () => subHistory(x) }, h('div', { class: 'av', style: { background: x.account_color || 'var(--accent)' } }, x.name[0].toUpperCase()),
        h('div', { class: 'grow', style: { minWidth: 0 } }, h('div', { style: { fontWeight: 700 } }, x.name), h('div', { class: 'faint' }, `${x.account_name} · every ${x.every_months > 1 ? x.every_months + ' months' : 'month'} on day ${x.billing_day}` + (x.next ? ' · next ' + nice(x.next) : ''))),
        chip(st[0], st[1]), h('b', { class: 'nowrap', style: { minWidth: '90px', textAlign: 'right' } }, fmt(x.cost, x.currency)), more);
    })));
    return el;
  }

  // ══════════════ Assets ══════════════
  function assetDialog(a) {
    a = a || { purchase_date: today(), life_months: 36 };
    form(a.id ? 'Edit asset' : 'New asset', [{ k: 'name', label: 'What is it?', ph: 'e.g. Gaming PC' }, { k: 'kind', label: 'Kind', ph: 'Computer, camera, phone…', half: true },
      { k: 'price', label: 'Price paid', type: 'amount', half: true }, { k: 'date', label: 'Bought on', type: 'date', half: true }, { k: 'life', label: 'Lasts (months)', type: 'number', min: 1, half: true },
      { k: 'salvage', label: 'Resale value at the end', type: 'amount', ph: '0', half: true }, a.id ? null : { k: 'pay_from', label: 'Paid from (adds the expense)', type: 'select', options: accOpts(), blank: '— already recorded —', half: true },
      { k: 'note', label: 'Note', type: 'textarea' }],
      { name: a.name, kind: a.kind, price: a.id ? plain(a.price) : '', date: a.purchase_date, life: a.life_months, salvage: a.salvage ? plain(a.salvage) : '', note: a.note },
      async (v) => { const id = await api('asset_save', { ...v, id: a.id }); ST.assetSel = a.id || id; toast('Saved'); await reload(); });
  }
  async function vAssets() {
    const d = await api('assets'); META = d.meta;
    const el = h('div', {}, head('Assets', `Things you own · they lose ${W(d.monthly)} of value a month`, btn('New asset', 'primary', () => assetDialog(), 'plus')));
    if (!d.rows.length) { el.append(card(null, null, h('div', { class: 'empty' }, h('h2', {}, 'Nothing yet'), h('p', {}, 'Add your PC, camera, phone or equipment to see their value today and the depreciation each month.')))); return el; }
    const a = d.rows.find(x => x.id === ST.assetSel) || d.rows[0]; ST.assetSel = a.id; const st = a.status_info;
    const list = card(null, null, d.rows.map(x => h('div', { class: 'li', style: { cursor: 'pointer', padding: '8px', borderRadius: '10px', background: x.id === a.id ? 'var(--soft)' : '' }, onclick: () => { ST.assetSel = x.id; reload(); } },
      h('div', { class: 'm' }, h('div', { class: 't' }, x.name), h('div', { class: 'faint' }, (x.kind ? x.kind + ' · ' : '') + (x.status === 'sold' ? 'sold' : 'worth ' + fmt(x.status_info.book, x.currency, { whole: true })))))));
    const more = btn('', 'ghost sm icon', (e) => menu(e.currentTarget, [{ t: 'Edit', fn: () => assetDialog(a) },
      a.status === 'sold' ? { t: 'Not sold (undo)', fn: () => act('asset_unsell', { id: a.id }, 'Done') } : { t: 'Sold it', fn: () => form('Sold', [{ k: 'date', label: 'Date', type: 'date', half: true }, { k: 'price', label: 'Sold for', type: 'amount', half: true }, { k: 'deposit_to', label: 'Money went to (optional)', type: 'select', options: accOpts(), blank: '— don’t record —' }], { date: today() }, async (v) => { await api('asset_sell', { ...v, id: a.id }); await reload(); }) },
      '-', { t: 'Delete', danger: true, fn: async () => { if (await ask(`Delete “${a.name}”?`)) act('asset_delete', { id: a.id }, 'Deleted'); } }]), 'more');
    const metric = (c, v, cls) => h('div', {}, h('div', { class: 'muted' }, c), h('div', { class: 'big ' + (cls || ''), style: { fontSize: '21px' } }, v));
    const detail = card(a.name, [a.status === 'sold' ? chip('Sold', 'amber') : st.fully ? chip('Fully depreciated') : chip('In use', 'green'), more],
      h('div', { class: 'g', style: { gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', marginBottom: '14px' } }, metric('Worth today', fmt(st.book, a.currency, { whole: true })),
        metric('Loses each month', fmt(st.monthly, a.currency, { whole: true }), 'expense'), metric('Lost so far', fmt(st.accumulated, a.currency, { whole: true })), metric('Total cost', fmt(st.total_cost, a.currency, { whole: true }))),
      bar(st.pct, 'var(--expense)'), h('div', { class: 'faint', style: { margin: '6px 0 14px' } }, `${Math.round(st.pct * 100)}% used · ${st.remaining} months left · ends ${nice(st.life_end)}` + (st.gain != null ? ` · ${st.gain >= 0 ? 'gain' : 'loss'} on sale ${fmt(st.gain, a.currency, { sign: true })}` : '')),
      h('h3', { style: { fontSize: '14px', margin: '8px 0' } }, 'Year by year'),
      a.years.map(([y, dep, val]) => h('div', { class: 'li', style: { padding: '4px 0' } }, h('div', { class: 'm' }, y), h('span', { class: 'expense' }, '−' + fmt(dep, a.currency, { whole: true })), h('span', { class: 'muted', style: { width: '130px', textAlign: 'right' } }, 'worth ' + fmt(val, a.currency, { whole: true })))),
      h('div', { class: 'row', style: { margin: '14px 0 8px' } }, h('h3', { style: { fontSize: '14px', margin: 0 }, class: 'grow' }, 'Repairs & upgrades'),
        btn('Add', 'soft sm', () => form('Repair or upgrade', [{ k: 'kind', label: 'What', type: 'select', options: [['repair', 'Repair (does not add value)'], ['upgrade', 'Upgrade (adds value)']] }, { k: 'cost', label: 'Cost', type: 'amount', half: true }, { k: 'date', label: 'Date', type: 'date', half: true },
          { k: 'extend', label: 'Upgrade: extra months of life', type: 'number', min: 0, half: true }, { k: 'pay_from', label: 'Paid from (adds the expense)', type: 'select', options: accOpts(), blank: '— don’t record —', half: true }, { k: 'note', label: 'Note' }],
          { date: today(), extend: 0 }, async (v) => { await api('asset_event', { ...v, id: a.id }); await reload(); }), 'plus')),
      a.events.length ? a.events.map(e => h('div', { class: 'li' }, h('div', { class: 'm' }, h('div', { class: 't' }, (e.kind === 'repair' ? '🔧 Repair' : '⬆ Upgrade') + (e.note ? ' — ' + e.note : '')), h('div', { class: 'faint' }, nice(e.date) + (e.extend_months ? ` · +${e.extend_months} months` : ''))),
        h('b', {}, fmt(e.cost, a.currency)), btn('', 'ghost sm icon', async () => { if (await ask('Remove this entry?')) act('asset_event_delete', { id: e.id }, 'Removed'); }, 'trash'))) : h('p', { class: 'muted' }, 'None yet.'));
    el.append(h('div', { class: 'g', style: { gridTemplateColumns: 'minmax(220px,1fr) 2.4fr' } }, list, detail));
    if (innerWidth < 980) el.lastChild.style.gridTemplateColumns = '1fr';
    return el;
  }

  // ══════════════ Reports ══════════════
  async function vReports() {
    if (!ST.repMonth) ST.repMonth = thisMonth();
    const d = await api('reports', { month: ST.repMonth, months: 12 }); META = d.meta;
    const m = d.month; const el = h('div', {}, head('Reports', d.label), h('div', { class: 'toolbar' }, monthNav(ST.repMonth, (x) => { ST.repMonth = x || thisMonth(); reload(); })));
    el.append(h('div', { class: 'g g3 rise', style: { marginBottom: '16px' } }, card('Money in', null, h('div', { class: 'big income' }, W(m.income))), card('Spent', null, h('div', { class: 'big expense' }, W(m.expense))),
      card('Kept', null, h('div', { class: 'big', style: { color: m.net >= 0 ? 'var(--income)' : 'var(--expense)' } }, fmt(m.net, B(), { whole: true, sign: true })), h('div', { class: 'muted' }, m.income > 0 ? Math.round(m.net / m.income * 100) + '% of income' : ''))));
    el.append(card('12 months', h('div', { class: 'legend', style: { margin: 0 } }, dot('var(--income)', 9), 'In', dot('var(--expense)', 9), 'Spent'), cashflow(d.series.map(x => ({ ...x, label: MONTHS[+x.month.slice(5) - 1].slice(0, 3), full: monthLabel(x.month) })))));
    const breakdown = (title, rows, kind) => { const tot = rows.reduce((a, r) => a + r[1], 0); const cols = rows.map(([n, v], i) => [n, v, META.categories.find(c => c.name === n && c.kind === kind)?.color || META.cat_colors[i % META.cat_colors.length]]);
      return card(title, h('b', {}, W(tot)), tot ? [segbar(cols), cols.map(([n, v, c]) => h('div', { class: 'li', style: { padding: '5px 0' } }, dot(c), h('div', { class: 'm' }, n), h('span', { class: 'muted' }, W(v)), h('b', { style: { width: '46px', textAlign: 'right' } }, Math.round(v / tot * 100) + '%')))] : h('p', { class: 'muted' }, 'Nothing in this month.')); };
    el.append(h('div', { class: 'g g2', style: { marginTop: '16px' } }, breakdown('Spending by category', d.expense, 'expense'), breakdown('Income by category', d.income, 'income')));
    el.append(h('div', { class: 'g g3', style: { marginTop: '16px' } }, card('Net worth', null, h('div', { class: 'big' }, W(d.net.total)), h('div', { class: 'muted' }, `Accounts ${W(d.net.accounts)} · things you own ${W(d.net.assets)}`)),
      card('Subscriptions', null, h('div', { class: 'big' }, W(d.subs_monthly)), h('div', { class: 'muted' }, 'a month')), card('Depreciation', null, h('div', { class: 'big expense' }, W(d.depr_monthly)), h('div', { class: 'muted' }, 'a month'))));
    return el;
  }

  // ══════════════ Settings ══════════════
  async function vSettings() {
    const d = await api('settings'); META = d.meta; const s2 = META.settings;
    const el = h('div', {}, head('Finance settings', `${d.counts.accounts} accounts · ${d.counts.transactions} transactions · ${d.counts.transfers} transfers`));
    const rates = card('Money', btn('Set a rate', 'soft sm', () => form('Exchange rate', [{ k: 'currency', label: 'Currency', ph: 'USD', half: true }, { k: 'rate', label: `1 of it = how many ${B()}?`, type: 'text', half: true }], {}, async (v) => { await api('set_rate', v); toast('Saved'); await reload(); }), 'plus'),
      h('div', { class: 'muted', style: { marginBottom: '8px' } }, `Main currency: ${B()} — every total is shown in it.`),
      d.rates.map(r => h('div', { class: 'li' }, h('b', { style: { width: '56px' } }, r.currency), h('div', { class: 'm' }, r.source === 'base' ? 'main currency' : `1 ${r.currency} = ${(+r.rate).toLocaleString('en-US', { maximumFractionDigits: 4 })} ${B()}`), h('span', { class: 'faint' }, r.updated || ''))),
      h('div', { style: { marginTop: '10px' } }, btn('Change main currency', 'ghost sm', () => form('Main currency', [{ k: 'base', label: 'New main currency (needs a rate first)', ph: 'USD' }], {}, async (v) => { await api('settings_set', v); toast('Changed'); await reload(); }))));
    const cats = card('Categories', btn('Add', 'soft sm', () => form('New category', [{ k: 'name', label: 'Name' }, { k: 'kind', label: 'For', type: 'select', options: [['expense', 'Expenses'], ['income', 'Income']] }], { kind: 'expense' }, async (v) => { await api('cat_add', v); await reload(); }), 'plus'),
      ['expense', 'income'].map(k => h('div', {}, h('div', { class: 'faint', style: { margin: '8px 0 4px', fontWeight: 650 } }, k === 'expense' ? 'Expenses' : 'Income'),
        h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '6px' } }, META.categories.filter(c => c.kind === k).map(c => h('span', { class: 'catpill', style: { cursor: 'pointer' }, title: 'Colour / delete',
          onclick: (e) => menu(e.currentTarget, [{ t: 'Change colour', fn: () => form('Colour of ' + c.name, [{ k: 'color', label: 'Colour', type: 'color', options: META.cat_colors }], { color: c.color }, async (v) => { await api('cat_color', { id: c.id, color: v.color }); await reload(); }) },
            { t: 'Delete', danger: true, fn: async () => { if (await ask(`Delete the category “${c.name}”? Entries keep their amounts, without a category.`)) act('cat_delete', { id: c.id }, 'Deleted'); } }]) }, dot(catColor(c), 8), c.name))))));
    const habits = card('Overview', null,
      h('div', { class: 'li' }, h('div', { class: 'm' }, 'Monthly spending limit'), h('b', {}, +s2.spend_limit ? W(+s2.spend_limit) : 'none'), btn('Change', 'ghost sm', setLimit)),
      h('div', { class: 'li' }, h('div', { class: 'm' }, 'Emergency fund'), h('b', {}, s2.emergency_account ? (accById(+s2.emergency_account) || {}).name || '—' : 'not set'), btn('Change', 'ghost sm', setEmergency)),
      h('div', { class: 'li' }, h('div', { class: 'm' }, 'Add subscription charges by themselves on their day'), h('input', { type: 'checkbox', checked: s2.auto_post_subs !== '0', style: { width: '18px', height: '18px', accentColor: 'var(--accent)' }, onchange: (e) => act('settings_set', { auto_post_subs: e.target.checked ? '1' : '0' }, 'Saved') })));
    const csvIn = h('input', { type: 'file', accept: '.csv,text/csv', style: { display: 'none' }, onchange: async (e) => { const f = e.target.files[0]; if (!f) return;
      const text = await f.text(); try { const r = await api('import_csv', { text }); toast(`Imported ${r.imported} · ${r.duplicates} already there` + (r.errors.length ? ` · ${r.errors.length} skipped` : '')); await reload(); } catch (x) { toast(x.message); } e.target.value = ''; } });
    const dl = (name, blob) => { const a = h('a', { href: URL.createObjectURL(blob), download: name }); document.body.append(a); a.click(); setTimeout(() => a.remove(), 500); };
    const data = card('Your data', null, h('p', { class: 'muted', style: { marginTop: 0 } }, 'Bring entries in from a spreadsheet or Notion export, or take everything with you.'),
      h('div', { class: 'row', style: { flexWrap: 'wrap' } }, btn('Import from CSV…', '', () => csvIn.click()), csvIn,
        btn('Download CSV', '', async () => dl('Curio finance.csv', new Blob([await api('export_csv')], { type: 'text/csv' }))),
        btn('Download finance.db (for the desktop app)', '', async () => { const b = await api('export_db'); const s3 = atob(b), u = new Uint8Array(s3.length); for (let i = 0; i < s3.length; i++) u[i] = s3.charCodeAt(i); dl('finance.db', new Blob([u])); })),
      h('div', { class: 'faint', style: { marginTop: '10px' } }, 'The whole desktop file can be brought in once from Curio › Settings › Import.'));
    el.append(h('div', { class: 'g g2 rise' }, h('div', { class: 'g' }, rates, habits), h('div', { class: 'g' }, cats, data)));
    return el;
  }

  const VIEWS = { overview: vOverview, transactions: vTransactions, transfers: vTransfers, accounts: vAccounts, goals: vGoals, subscriptions: vSubs, assets: vAssets, reports: vReports, settings: vSettings };
  window.addEventListener('hashchange', () => { $$('.bulk').forEach(b => b.remove()); ST.search = ''; page().replaceChildren(); reload(); scrollTo(0, 0); });
  document.addEventListener('keydown', (e) => {
    if ($('.scrim') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if (e.key === 'n' && !e.ctrlKey && !e.metaKey) { e.preventDefault(); txDialog(); }
    if (e.key === 'Escape' && ST.sel.size) { ST.sel.clear(); reload(); }
  });
  reload();
})();
