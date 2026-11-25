/* Curio Web — the shell: sidebar, sign-in check, Home, Settings (with the one-time import from the desktop app).
   Pages and Finance run in their own frames, kept alive while you move around. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const h = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'html') e.innerHTML = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const toast = (m) => { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 2600); };
  const post = async (url, body) => {
    const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify(body) });
    if (r.status === 401) { signIn(); throw new Error('Signing you in…'); }
    const j = await r.json(); if (j.error) throw new Error(j.error); return j;
  };
  const fin = async (op, args = {}) => (await post('/api/fin', { op, args })).data;
  const ai = async (op, args = {}) => (await post('/api/ai', { op, args })).data;
  const signIn = () => { location.href = '/api/auth/login?next=' + encodeURIComponent(location.pathname + location.hash); };

  // ── icons (simple line icons) ──
  const P = {
    home: 'M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z', explore: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm4 6-2.5 5.5L8 16l2.5-5.5z',
    grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z', bookmark: 'M6 3h12v18l-6-4-6 4z', globe: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM2 12h20M12 2c3 3 3 17 0 20M12 2c-3 3-3 17 0 20',
    chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2', spark: 'M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2zM19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z', users: 'M16 20v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 20v-1a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
    play: 'M2 7a3 3 0 0 1 3-3h14a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3zM10 9l5 3-5 3z', music: 'M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
    bot: 'M12 8V4M8 4h8M5 8h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2zM9 14h.01M15 14h.01', book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5',
    page: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h6', wallet: 'M3 7a2 2 0 0 1 2-2h14v4M3 7v10a2 2 0 0 0 2 2h16V9H5a2 2 0 0 1-2-2zM16 14h.01',
    cal: 'M4 5h16v16H4zM16 3v4M8 3v4M4 10h16', gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    check: 'M20 6 9 17l-5-5',
    insta: 'M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM17.5 6.5h.01', pin: 'M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zM12 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
    fb: 'M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z', upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12', out: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  };
  const ic = (n) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '1.8'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', P[n] || ''); s.append(p); return s; };

  // ── what is in the sidebar ──
  const LIVE = { home: 1, tracker: 1, pages: 1, finance: 1, calendar: 1, settings: 1, ask: 1, moodboard: 1, boards: 1 };
  const NAV = [
    [null, [['home', 'Home', 'home'], ['explore', 'Explore', 'explore']]],
    ['Library', [['moodboard', 'Moodboard', 'grid'], ['boards', 'My Boards', 'bookmark'], ['bookmarks', 'Bookmarks', 'globe'], ['insights', 'Insights', 'chart'], ['rediscover', 'Rediscover', 'spark']]],
    ['Media', [['creators', 'Creators', 'users'], ['youtube', 'YouTube', 'play'], ['songs', 'Songs', 'music']]],
    ['AI', [['ask', 'Ask AI · ChatGPT', 'bot'], ['notebooks', 'Notebooks', 'book']]],
    ['Workspace', [['tracker', 'Tracker', 'check'], ['pages', 'Pages', 'page'], ['finance', 'Finance', 'wallet'], ['calendar', 'Calendar', 'cal']]],
    ['Platforms', [['instagram', 'Instagram', 'insta'], ['pinterest', 'Pinterest', 'pin'], ['ytsync', 'YouTube', 'play'], ['facebook', 'Facebook', 'fb']]],
  ];
  const TITLE = Object.fromEntries(NAV.flatMap(([, items]) => items.map(([k, t]) => [k, t]))); TITLE.settings = 'Settings';
  const ICON = Object.fromEntries(NAV.flatMap(([, items]) => items.map(([k, , i]) => [k, i])));
  let ME = null;

  function buildSide() {
    const side = $('#side'); side.replaceChildren();
    side.append(h('a', { class: 'brand', href: '#/home' }, h('div', { class: 'logo' }, 'C'), h('div', {}, h('b', {}, 'Curio'), h('small', {}, 'Your inspiration library'))));
    for (const [sec, items] of NAV) {
      if (sec) side.append(h('div', { class: 'sec' }, sec));
      for (const [k, t, i] of items) side.append(h('a', { class: 'nav', href: '#/' + k, 'data-k': k }, ic(i), t, LIVE[k] ? null : h('span', { class: 'soon' }, 'Soon')));
    }
    side.append(h('div', { class: 'grow' }));
    side.append(h('a', { class: 'nav', href: '#/settings', 'data-k': 'settings' }, ic('gear'), 'Settings'));
    const me = h('div', { class: 'me' }, ME && ME.pic ? h('img', { src: ME.pic, alt: '', referrerpolicy: 'no-referrer' }) : h('div', { class: 'av' }, ((ME && ME.name) || 'Y')[0].toUpperCase()), h('span', {}, (ME && ME.name) || 'You'),
      h('a', { class: 'btn ghost', href: '/api/auth/logout', title: 'Sign out', style: 'padding:0 8px' }, ic('out')));
    side.append(me);
  }

  // ── views ──
  const views = {};
  function view(k, make) {
    if (!views[k]) { const v = h('section', { class: 'view', 'data-v': k }); $('#main').append(v); views[k] = v; make(v); }
    return views[k];
  }
  const theme = () => document.documentElement.dataset.theme || 'light';
  function frame(k, src) {
    return view(k, (v) => { v.classList.add('frame'); v.append(h('iframe', { src, title: TITLE[k], allow: 'microphone' })); });
  }

  function route() {
    const k = (location.hash.match(/^#\/([\w-]+)/) || [])[1] || 'home';
    let v;
    if (k === 'pages') v = frame('pages', '/pages/index.html?theme=' + theme() + '#/documents');
    else if (k === 'finance') v = frame('finance', '/finance/index.html?theme=' + theme());
    else if (k === 'moodboard') v = frame('moodboard', '/library/index.html?theme=' + theme() + '#moodboard');
    else if (k === 'boards') v = frame('boards', '/library/index.html?theme=' + theme() + '#boards');
    else if (k === 'calendar') v = frame('calendar', '/calendar/index.html?theme=' + theme());
    else if (k === 'tracker') v = frame('tracker', '/tracker/index.html?theme=' + theme());
    else if (k === 'home') { v = view('home', () => {}); renderHome(v); }
    else if (k === 'settings') { v = view('settings', () => {}); renderSettings(v); }
    else if (k === 'ask') v = view('ask', (el) => renderAsk(el));
    else { v = view('soon-' + k, (el) => renderSoon(el, k)); }
    for (const x of Object.values(views)) x.classList.toggle('on', x === v);
    document.querySelectorAll('.nav').forEach(n => n.classList.toggle('on', n.dataset.k === k));
    $('#toptitle').textContent = TITLE[k] || 'Curio'; document.title = (TITLE[k] ? TITLE[k] + ' · ' : '') + 'Curio';
    $('#side').classList.remove('open'); $('#scrim').classList.remove('on');
  }

  function renderSoon(el, k) {
    const ai = k === 'ask' || k === 'notebooks';
    el.append(h('div', { class: 'page fade' }, h('div', { class: 'soonbox' },
      h('div', { class: 'ic' }, ic(ICON[k] || 'spark')), h('h1', {}, TITLE[k]),
      h('p', { class: 'sub', style: 'max-width:520px;margin:8px auto 22px' }, ai
        ? 'ChatGPT is coming to Curio Web with “Sign in with ChatGPT” — the same account you use in the desktop app, no API key. Until then it works in the desktop app.'
        : 'This part of Curio works in the desktop app. On the web it is coming soon — Pages and Finance are already here.'),
      h('div', { class: 'row', style: 'justify-content:center' }, h('a', { class: 'btn primary', href: '#/pages' }, ic('page'), 'Open Pages'), h('a', { class: 'btn', href: '#/finance' }, ic('wallet'), 'Open Finance')))));
  }

  const money = (m, cur) => {
    if (m == null) return '—'; const neg = m < 0; let a = Math.abs(Math.round(m)); a = Math.round(a / 100) * 100;
    const sym = { PKR: 'Rs', USD: '$', EUR: '€', GBP: '£', INR: '₹' }[cur] || cur || '';
    return (neg ? '−' : '') + (sym ? sym + (sym.length > 1 ? ' ' : '') : '') + (a / 100).toLocaleString('en-US', { maximumFractionDigits: 0 });
  };

  async function renderHome(v) {
    const hour = new Date().getHours(), greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    const name = (ME && ME.name) || '';
    v.replaceChildren(h('div', { class: 'page fade' },
      h('div', { class: 'hero' }, h('h2', {}, `${greet}${name ? ', ' + name : ''}`), h('p', {}, new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) + ' · Curio on the web')),
      h('div', { class: 'grid', id: 'homegrid' }, h('div', { class: 'card' }, h('p', {}, 'Loading…')))));
    const grid = $('#homegrid', v);
    const [f, docs] = await Promise.all([fin('overview').catch(e => ({ err: e.message })), pagesList().catch(() => [])]);
    grid.replaceChildren();
    if (f.err) grid.append(h('div', { class: 'card' }, h('h3', {}, 'Finance'), h('p', {}, f.err)));
    else if (f.empty) grid.append(h('div', { class: 'card' }, h('h3', {}, 'Finance'), h('p', {}, 'No accounts yet. Bring your desktop data in, or start fresh.'),
      h('div', { class: 'row', style: 'margin-top:14px' }, h('a', { class: 'btn primary', href: '#/settings' }, ic('upload'), 'Import from desktop'), h('a', { class: 'btn', href: '#/finance' }, 'Open Finance'))));
    else {
      const b = f.meta.base;
      grid.append(h('a', { class: 'card', href: '#/finance', style: 'text-decoration:none' }, h('h3', {}, 'Balance'), h('div', { class: 'big' }, money(f.net.accounts, b)),
        h('p', {}, `${f.meta.accounts.filter(a => !a.archived).length} accounts`)));
      grid.append(h('a', { class: 'card', href: '#/finance', style: 'text-decoration:none' }, h('h3', {}, 'This month'),
        h('div', { class: 'row', style: 'gap:22px;margin-top:6px' },
          h('div', {}, h('div', { class: 'faint' }, 'Money in'), h('div', { class: 'big', style: 'color:var(--income);font-size:22px' }, money(f.month.income, b))),
          h('div', {}, h('div', { class: 'faint' }, 'Spent'), h('div', { class: 'big', style: 'color:var(--expense);font-size:22px' }, money(f.month.expense, b)))),
        f.due.length ? h('p', { style: 'margin-top:8px' }, `${f.due.length} subscription charge(s) due`) : null));
    }
    const recent = docs.filter(d => !d.isArchived).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)).slice(0, 6);
    grid.append(h('div', { class: 'card' }, h('h3', {}, 'Recent pages'),
      recent.length ? h('div', { class: 'links' }, recent.map(d => h('a', { href: '#/pages', onclick: () => openPage(d.id) }, h('span', {}, d.icon || '📄'), d.title || 'Untitled')))
        : h('p', {}, 'No pages yet.'), h('div', { class: 'row', style: 'margin-top:12px' }, h('a', { class: 'btn', href: '#/pages' }, ic('page'), 'Open Pages'))));
  }
  async function pagesList() {
    const r = await fetch('/api/pages/rpc', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify({ o: 'curio', m: 'list', a: [] }) });
    const j = await r.json(); return Array.isArray(j) ? j : [];
  }
  function openPage(id) {
    const v = frame('pages', '/pages/index.html?theme=' + theme() + '#/documents/' + id);
    const f = v.querySelector('iframe'); try { f.contentWindow.location.hash = '#/documents/' + id; } catch (e) { /* first load uses the src */ }
  }

  // ── Settings + import ──
  function renderSettings(v) {
    v.replaceChildren(h('div', { class: 'page fade' }, h('h1', {}, 'Settings'), h('p', { class: 'sub' }, 'Curio on the web — your Pages and Finance, from any device.'),
      h('div', { class: 'grid', style: 'grid-template-columns:1fr' }, aiCard(), storageCard(), desktopCard(), importCard(), themeCard(), accountCard())));
  }
  function storageCard() {
    const st = h('span', { class: 'pill' }, 'checking…');
    fetch('/api/health').then(r => r.json()).then(j => { st.textContent = j.db === 'turso' ? 'Connected' : 'Not connected'; st.className = 'pill ' + (j.db === 'turso' ? 'ok' : 'warn'); }).catch(() => {});
    return h('div', { class: 'card' }, h('div', { class: 'row' }, h('h3', { style: 'margin:0' }, 'Where your data is saved'), st),
      h('p', { style: 'margin-top:8px' }, 'Everything you do here — Pages (pages, databases, rows, comments, version history, pictures), Finance (accounts, transactions, transfers, goals, subscriptions, assets, settings) and Calendar (which calendars are shown, colours) — is saved the moment you make the change, in your own database:'),
      h('div', { class: 'links', style: 'margin-top:10px' },
        h('div', {}, h('b', {}, 'Turso database'), h('span', { class: 'muted' }, ' — SQLite in the cloud, region Mumbai, free plan (5 GB). Connected to your Vercel project “curio-web”.')),
        h('div', {}, h('b', {}, 'Vercel'), h('span', { class: 'muted' }, ' — runs the app; it keeps no data itself.')),
        h('div', {}, h('b', {}, 'Google'), h('span', { class: 'muted' }, ' — only checks it is you when you sign in.'))),
      h('p', { class: 'faint', style: 'margin-top:10px' }, 'Backups: Finance › Settings › Download finance.db (opens in the desktop app) or CSV · Pages › ⋯ › Import & export. The desktop app keeps its own data on your PC, separate from this.'));
  }
  // ── Connect desktop: a read-only key the desktop app uses for "Update from web" ──
  function desktopCard() {
    const dk = async (op, args = {}) => (await post('/api/desktop', { op, args })).data;
    const pill = h('span', { class: 'pill' }, '…');
    const list = h('div', { class: 'links', style: 'margin-top:12px' });
    const fresh = h('div');
    const name = h('input', { class: 'inp', type: 'text', placeholder: 'Name, e.g. Home PC', maxlength: '40', autocomplete: 'off', style: 'flex:1;min-width:160px' });
    const make = h('button', { class: 'btn primary', onclick: async () => {
      make.disabled = true;
      try {
        const k = await dk('create', { name: name.value || 'Desktop' }); name.value = '';
        const box = h('code', { style: 'display:block;padding:10px 12px;border-radius:10px;background:var(--hover, rgba(127,127,127,.12));word-break:break-all;user-select:all;margin-top:8px' }, k.key);
        const copy = h('button', { class: 'btn', onclick: async () => { try { await navigator.clipboard.writeText(k.key); toast('Key copied'); } catch (e) { toast('Select the key and copy it'); } } }, 'Copy key');
        fresh.replaceChildren(h('div', { class: 'card', style: 'margin-top:12px;border-color:var(--accent, #f2602d)' },
          h('b', {}, `Key for “${k.name}”`), box,
          h('div', { class: 'row', style: 'margin-top:10px' }, copy, h('button', { class: 'btn', onclick: () => fresh.replaceChildren() }, 'Done')),
          h('p', { class: 'faint', style: 'margin-top:8px' }, 'Shown only this once. In the desktop app: Settings › Curio Web › paste the key › Save. It can only read your data, never change it.')));
        draw();
      } catch (e) { toast(e.message); }
      make.disabled = false;
    } }, 'Make a desktop key');
    const when = (t) => t ? new Date(t * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'never';
    async function draw() {
      let ks;
      try { ks = await dk('keys'); } catch (e) { list.replaceChildren(h('p', { style: 'color:var(--expense)' }, e.message)); return; }
      pill.textContent = ks.length ? (ks.length === 1 ? '1 desktop' : ks.length + ' desktops') : 'Not connected';
      pill.className = 'pill ' + (ks.length ? 'ok' : 'warn');
      list.replaceChildren(...ks.map(k => h('div', { class: 'row', style: 'justify-content:space-between;gap:10px' },
        h('div', {}, h('b', {}, k.name), h('span', { class: 'muted' }, ` · made ${when(k.created)} · last update ${when(k.last_used)}`)),
        h('button', { class: 'btn', onclick: async () => {
          if (!confirm(`Remove the key “${k.name}”? That desktop can no longer update from the web until you give it a new key.`)) return;
          try { await dk('revoke', { id: k.id }); toast('Key removed'); draw(); } catch (e) { toast(e.message); }
        } }, 'Remove'))));
    }
    draw();
    return h('div', { class: 'card' }, h('div', { class: 'row' }, h('h3', { style: 'margin:0' }, 'Connect desktop'), pill),
      h('p', { style: 'margin-top:8px' }, 'The web is the original. Your desktop app copies Pages, Finance and Calendar from here when you press “Update from web” — it never changes anything here.'),
      h('div', { class: 'row', style: 'margin-top:12px;gap:8px' }, name, make), fresh, list);
  }
  function themeCard() {
    const cur = localStorage.getItem('curio-theme') || 'system';
    const seg = h('div', { class: 'seg' }, ['light', 'dark', 'system'].map(t => h('button', { class: t === cur ? 'on' : '', onclick: () => setTheme(t) }, t[0].toUpperCase() + t.slice(1))));
    return h('div', { class: 'card' }, h('h3', {}, 'Appearance'), h('p', { style: 'margin-bottom:12px' }, 'Light, dark, or follow this device.'), seg);
  }
  function setTheme(t) {
    try { localStorage.setItem('curio-theme', t); } catch (e) { /* private window */ }
    location.reload();
  }
  function accountCard() {
    return h('div', { class: 'card' }, h('h3', {}, 'Account'), h('p', {}, `Signed in as ${ME ? ME.email : ''} with Google. Only this account can open your Curio.`),
      h('div', { class: 'row', style: 'margin-top:12px' }, h('a', { class: 'btn', href: '/api/auth/logout' }, ic('out'), 'Sign out')),
      h('p', { class: 'faint', style: 'margin-top:14px' }, 'The desktop app keeps working on its own, with its own data.'));
  }

  function importCard() {
    const log = h('div', { class: 'faint', style: 'margin-top:10px;white-space:pre-line' });
    const bar = h('div', { class: 'bar', style: 'display:none' }, h('i'));
    const pick = (label, accept, multi) => { const i = h('input', { type: 'file', accept, multiple: multi || false }); return [h('label', { class: 'muted' }, label), i]; };
    const [l1, fFin] = pick('finance.db', '.db,.sqlite'), [l2, fPg] = pick('pages.db', '.db,.sqlite'), [l3, fFiles] = pick('Pictures (optional)', 'image/*,*', true);
    const go = h('button', { class: 'btn primary', onclick: run }, ic('upload'), 'Import');
    async function run() {
      if (!fFin.files[0] && !fPg.files[0]) return toast('Choose finance.db and/or pages.db first');
      if (!confirm('This replaces the Finance and/or Pages data on the web with the files you chose. Your desktop app is not touched. Continue?')) return;
      go.disabled = true; bar.style.display = 'block'; log.textContent = '';
      const say = (t) => { log.textContent += t + '\n'; };
      const prog = (p) => { bar.firstChild.style.width = Math.round(p * 100) + '%'; };
      try {
        const SQL = await loadSQL();
        if (fFin.files[0]) { say('Finance: reading…'); await importDb(SQL, fFin.files[0], 'finance', say, prog); }
        if (fPg.files[0]) { say('Pages: reading…'); await importDb(SQL, fPg.files[0], 'pages', say, prog); }
        if (fFiles.files.length) {
          say(`Pictures: ${fFiles.files.length}…`); let i = 0;
          for (const f of fFiles.files) {
            if (f.size > 3.2e6) { say(`  skipped ${f.name} (bigger than 3 MB)`); continue; }
            await post('/api/import/file', { name: f.name, mime: f.type, b64: await b64(f) }); prog(++i / fFiles.files.length);
          }
        }
        if (fPg.files[0] || fFiles.files.length) await post('/api/import/end', { domain: 'pages' });
        say('Done ✓ — open Finance and Pages.'); prog(1); toast('Imported');
        for (const k of ['pages', 'finance']) if (views[k]) { views[k].remove(); delete views[k]; }
      } catch (e) { say('Stopped: ' + e.message); }
      go.disabled = false;
    }
    return h('div', { class: 'card' }, h('h3', {}, 'Bring your desktop data in (once)'),
      h('p', {}, 'Your files are read here in the browser and sent straight to your own database — nobody else sees them.'),
      h('div', { class: 'steps', style: 'margin:16px 0' },
        h('div', { class: 'step' }, h('div', {}, 'On your PC open your Curio data folder (yours: ', h('code', {}, 'C:\\AI\\Projects\\curio\\Media'), ').')),
        h('div', { class: 'step' }, h('div', {}, 'Finance: ', h('code', {}, 'finance\\finance.db'), '  ·  Pages: ', h('code', {}, 'pages\\pages.db'), '  ·  pictures in ', h('code', {}, 'pages\\files'), ' (select them all).')),
        h('div', { class: 'step' }, h('div', {}, 'Close Curio on the PC first, so the files are complete.'))),
      h('div', { class: 'drop' }, l1, fFin), h('div', { class: 'drop', style: 'margin-top:8px' }, l2, fPg), h('div', { class: 'drop', style: 'margin-top:8px' }, l3, fFiles),
      h('div', { class: 'row', style: 'margin-top:14px' }, go), bar, log);
  }
  let _sql = null;
  function loadSQL() {
    if (_sql) return _sql;
    _sql = new Promise((ok, bad) => {
      const s = h('script', { src: '/vendor/sql-wasm.js' }); s.onload = () => window.initSqlJs({ locateFile: f => '/vendor/' + f }).then(ok, bad); s.onerror = () => bad(new Error('Could not load the reader')); document.head.append(s);
    });
    return _sql;
  }
  const b64 = (file) => new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1]); r.readAsDataURL(file); });
  const bytesB64 = (u8) => { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); };
  const TABLES = {
    finance: ['settings', 'accounts', 'categories', 'transactions', 'transfers', 'goals', 'goal_contributions', 'subscriptions', 'sub_periods', 'sub_charges', 'assets', 'asset_events', 'rates', 'rate_history'],
    pages: ['docs', 'dbs', 'page_meta', 'page_comments'],
  };
  async function importDb(SQL, file, domain, say, prog) {
    const db = new SQL.Database(new Uint8Array(await file.arrayBuffer()));
    const want = TABLES[domain];
    const q = (sql) => { const r = db.exec(sql); return r.length ? r[0] : { columns: [], values: [] }; };
    const sch = q("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'");
    const schema = sch.values.map(r => ({ type: r[0], name: r[1], tbl_name: r[2], sql: r[3] })).filter(s => want.includes(s.tbl_name));
    if (!schema.some(s => s.type === 'table' && s.name === want[1])) throw new Error(`${file.name} is not a Curio ${domain} file.`);
    await post('/api/import/begin', { domain, schema });
    const tables = schema.filter(s => s.type === 'table').map(s => s.name);
    let total = 0, done = 0; const counts = {};
    for (const t of tables) { counts[t] = q(`SELECT COUNT(*) FROM "${t}"`).values[0][0]; total += counts[t]; }
    for (const t of tables) {
      const r = q(`SELECT * FROM "${t}"`); let batch = [], size = 0;
      const flush = async () => { if (!batch.length) return; await post('/api/import/rows', { table: t, cols: r.columns, rows: batch }); done += batch.length; prog(total ? done / total : 1); batch = []; size = 0; };
      for (const row of r.values) {
        const vals = row.map(x => x instanceof Uint8Array ? { $b: bytesB64(x) } : x);
        const len = JSON.stringify(vals).length;
        if (size + len > 900000 || batch.length >= 400) await flush();
        batch.push(vals); size += len;
      }
      await flush(); say(`  ${t}: ${counts[t]}`);
    }
    if (domain === 'finance') await post('/api/import/end', { domain });
    db.close();
  }

  // ── AI models (Settings) ──
  function aiCard() {
    const body = h('div', {}, h('p', {}, 'Loading…'));
    const pill = h('span', { class: 'pill' }, '…');
    const card = h('div', { class: 'card', id: 'aicard' },
      h('div', { class: 'row' }, h('h3', { style: 'margin:0' }, 'AI models'), pill),
      h('p', { style: 'margin-top:6px' }, 'Connect the AI that Ask AI uses. ChatGPT runs on your own ChatGPT Plus / Pro plan — no API key.'), body);
    const draw = async () => {
      let s;
      try { s = await ai('settings'); } catch (e) { body.replaceChildren(h('p', { style: 'margin-top:10px;color:var(--expense)' }, e.message)); return; }
      const c = s.chatgpt, ready = c.state === 'ready';
      pill.textContent = ready ? 'ChatGPT connected' : c.state === 'no_plan' ? 'Plan usage not allowed' : 'Not connected';
      pill.className = 'pill ' + (ready ? 'ok' : 'warn');
      const rowsP = h('div', { class: 'providers' });
      const gpt = h('div', { class: 'prov' + (ready ? ' on' : '') },
        h('div', { class: 'prov-ic gpt' }, ic('bot')),
        h('div', { class: 'prov-t' }, h('b', {}, 'ChatGPT'), h('span', { class: 'muted' }, ready ? `Signed in${c.email ? ' as ' + c.email : ''} · uses your ChatGPT plan` : 'Sign in with ChatGPT — your Plus / Pro plan, no API key')),
        ready ? h('span', { class: 'pill ok' }, 'Active') : null);
      rowsP.append(gpt);
      for (const [n, t] of [['Gemini', 'Free key from Google AI Studio'], ['Claude', 'Anthropic API key'], ['Ollama', 'Runs on your own PC (desktop app only)']])
        rowsP.append(h('div', { class: 'prov dim' }, h('div', { class: 'prov-ic' }, ic('spark')), h('div', { class: 'prov-t' }, h('b', {}, n), h('span', { class: 'muted' }, t)), h('span', { class: 'soon' }, 'Soon')));
      const parts = [rowsP];
      if (ready) {
        const sel = h('select', { class: 'inp', onchange: async () => { await ai('set_cfg', { chatgpt_model: sel.value }); toast('Model saved'); } }, h('option', { value: '' }, 'Default (first on your plan)'));
        ai('models').then(ms => { for (const m of ms) sel.append(h('option', { value: m.slug, selected: m.slug === s.cfg.chatgpt_model }, m.name)); }).catch(e => toast(e.message));
        const ctx = h('input', { type: 'checkbox', checked: s.cfg.context !== false, onchange: async () => { await ai('set_cfg', { context: ctx.checked }); toast('Saved'); } });
        const fon = h('input', { type: 'checkbox', checked: s.cfg.finance !== false, onchange: async () => { await ai('set_cfg', { finance: fon.checked }); toast('Saved'); } });
        const fauto = h('input', { type: 'checkbox', checked: !!s.cfg.fin_auto, onchange: async () => { await ai('set_cfg', { fin_auto: fauto.checked }); toast('Saved'); } });
        const frules = h('textarea', { class: 'inp area', rows: 4, placeholder: 'e.g.  Default account: Meezan Bank. Food, chai, lunch → category Food. Petrol → Fuel from Cash. Titles short in English.' }, s.cfg.fin_rules || '');
        frules.addEventListener('change', async () => { await ai('set_cfg', { fin_rules: frules.value }); toast('Rules saved'); });
        parts.push(h('div', { class: 'form2' },
          h('label', {}, h('span', { class: 'muted' }, 'Model'), sel),
          h('label', { class: 'chk' }, ctx, h('span', {}, 'Let Ask AI look in my Pages when a question is about them')),
          h('label', { class: 'chk' }, fon, h('span', {}, 'Connect Finance — ChatGPT sees my accounts, balances and entries, and can record money for me')),
          h('label', { class: 'chk' }, fauto, h('span', {}, 'Save right away (no Save button) when ChatGPT records something')),
          h('label', {}, h('span', { class: 'muted' }, 'My rules for recording (ChatGPT always follows these)'), frules,
            h('span', { class: 'faint' }, 'Saved when you click outside the box.'))),
          h('div', { class: 'row', style: 'margin-top:14px' },
            h('a', { class: 'btn primary', href: '#/ask' }, ic('bot'), 'Open Ask AI'),
            h('a', { class: 'btn', href: 'https://chatgpt.com/settings/usage', target: '_blank', rel: 'noopener' }, 'See usage in ChatGPT'),
            h('button', { class: 'btn ghost', onclick: async () => { if (!confirm('Disconnect ChatGPT from Curio Web?')) return; await ai('logout'); draw(); } }, 'Disconnect')));
      } else {
        const paste = h('input', { class: 'inp', placeholder: 'http://127.0.0.1:1455/auth/callback?code=…', autocomplete: 'off', spellcheck: 'false' });
        const fin2 = h('button', { class: 'btn primary', onclick: async () => {
          if (!paste.value.trim()) return toast('Paste the address first');
          fin2.disabled = true;
          try { await ai('finish', { url: paste.value }); toast('ChatGPT connected ✓'); draw(); } catch (e) { toast(e.message); fin2.disabled = false; }
        } }, 'Finish');
        const go = h('button', { class: 'btn primary', onclick: async () => {
          const w = window.open('about:blank', '_blank');
          try { const r = await ai('start', c.state === 'no_plan' ? { reconsent: true } : {}); if (w) w.location = r.url; else location.href = r.url; step2.style.display = ''; paste.focus(); }
          catch (e) { if (w) w.close(); toast(e.message); }
        } }, ic('bot'), 'Continue with ChatGPT');
        const step2 = h('div', { class: 'steps', style: (c.pending ? '' : 'display:none;') + 'margin-top:16px' },
          h('div', { class: 'step' }, h('div', {}, 'In the new tab sign in to ChatGPT and approve ', h('b', {}, 'Curio'), '.')),
          h('div', { class: 'step' }, h('div', {}, 'The tab then goes to an address starting with ', h('code', {}, 'http://127.0.0.1:1455'), ' and says it can\'t connect — that is expected. Copy that whole address from the address bar.')),
          h('div', { class: 'step' }, h('div', { style: 'flex:1' }, 'Paste it here:', h('div', { class: 'row', style: 'margin-top:8px;flex-wrap:nowrap' }, paste, fin2))));
        parts.push(h('div', { class: 'row', style: 'margin-top:14px' }, go,
          c.state !== 'none' ? h('button', { class: 'btn ghost', onclick: async () => { if (!confirm('Forget the ChatGPT connection completely and register Curio again?')) return; await ai('reset'); draw(); } }, 'Start over') : null), step2,
          h('p', { class: 'faint', style: 'margin-top:12px' }, 'Needs a personal ChatGPT Plus or Pro account. Your sign-in is kept encrypted in your own database and only used for Ask AI answers on your plan — it cannot read your ChatGPT chats. You can limit or remove Curio any time in ChatGPT › Settings.'));
      }
      body.replaceChildren(...parts);
    };
    draw();
    return card;
  }

  // ── Ask AI ──
  const esc = (t) => String(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function md(t, pagesUsed) {
    const blocks = String(t || '').split(/```/);
    return blocks.map((b, i) => {
      if (i % 2) { const nl = b.indexOf('\n'); return '<pre><code>' + esc(nl > -1 ? b.slice(nl + 1) : b) + '</code></pre>'; }
      let x = esc(b);
      x = x.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>');
      x = x.replace(/\[P(\d+)\]/g, (m, n) => { const p = (pagesUsed || [])[n - 1]; return p ? `<a class="cite" data-doc="${esc(p.id)}" title="${esc(p.title)}">${esc(p.icon || '📄')} ${esc(p.title)}</a>` : m; });
      x = x.replace(/\[(\w[^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      const lines = x.split('\n'); let out = '', list = null;
      for (const ln of lines) {
        const ul = ln.match(/^\s*[-*•]\s+(.*)/), ol = ln.match(/^\s*\d+[.)]\s+(.*)/), hd = ln.match(/^\s*#{1,4}\s+(.*)/);
        const want = ul ? 'ul' : ol ? 'ol' : null;
        if (list && want !== list) { out += `</${list}>`; list = null; }
        if (want) { if (!list) { out += `<${want}>`; list = want; } out += `<li>${(ul || ol)[1]}</li>`; continue; }
        if (hd) { out += `<h4>${hd[1]}</h4>`; continue; }
        out += ln.trim() ? `<p>${ln}</p>` : '';
      }
      if (list) out += `</${list}>`;
      return out;
    }).join('');
  }
  // ── voice: speak instead of typing (the browser turns speech into text), and listen to an answer ──
  const VOICE_LANGS = [['hi-IN', 'Hindi / Urdu (हिंदी)'], ['ur-PK', 'Urdu (اردو)'], ['en-IN', 'English (India)'], ['en-US', 'English (US)']];
  const voiceLang = (v) => { try { if (v) localStorage.setItem('curio-voice-lang', v); return localStorage.getItem('curio-voice-lang') || 'hi-IN'; } catch (e) { return 'hi-IN'; } };
  function micButton(input, onDone) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const b = h('button', { class: 'btn mic', title: 'Speak instead of typing — press again to stop and send (right-click: language)' }, '🎙');
    if (!SR) { b.title = 'Speaking needs Chrome or Edge on this device'; b.onclick = () => toast('Speaking works in Chrome or Edge. In this browser, type instead.'); return b; }
    let rec = null, base = '', final = '', stopped = false;
    const reset = () => { rec = null; b.classList.remove('on'); b.textContent = '🎙'; };
    b.onclick = () => {
      if (rec) { stopped = true; rec.stop(); return; }
      rec = new SR(); rec.lang = voiceLang(); rec.interimResults = true; rec.continuous = true; base = input.value ? input.value.trim() + ' ' : ''; final = ''; stopped = false;
      rec.onresult = (e) => { let mid = ''; for (let i = e.resultIndex; i < e.results.length; i++) { const t = e.results[i][0].transcript; if (e.results[i].isFinal) final += t + ' '; else mid += t; }
        input.value = (base + final + mid).trimStart(); input.dispatchEvent(new Event('input')); };
      rec.onerror = (e) => {
        const m = { 'not-allowed': 'The browser is blocking the microphone. Click the lock icon next to the address › Microphone › Allow, then press 🎙 again.',
          'service-not-allowed': 'The browser is blocking the microphone. Click the lock icon next to the address › Microphone › Allow, then press 🎙 again.',
          'no-speech': 'No speech heard — press 🎙 and speak.', 'audio-capture': 'No microphone was found on this device.', 'network': 'Speech needs the internet — check the connection.' }[e.error];
        if (m) toast(m); stopped = true;
      };
      rec.onend = () => { const was = stopped; reset(); if (input.value.trim() && was !== null) onDone && onDone(); };
      try { rec.start(); b.classList.add('on'); b.textContent = '■'; toast('Listening… press ■ when you are done'); } catch (e) { reset(); toast('The microphone could not start: ' + e.message); }
    };
    b.oncontextmenu = (e) => { e.preventDefault(); const cur = voiceLang(); const pick = prompt('Speaking language:\n' + VOICE_LANGS.map(([k, t], i) => `${i + 1}. ${t}${k === cur ? '  ✓' : ''}`).join('\n') + '\n\nType 1–' + VOICE_LANGS.length, '');
      const i = parseInt(pick, 10) - 1; if (VOICE_LANGS[i]) { voiceLang(VOICE_LANGS[i][0]); toast('Speaking language: ' + VOICE_LANGS[i][1]); } };
    return b;
  }
  function speakButton(getText) {
    if (!('speechSynthesis' in window)) return null;
    const b = h('button', { class: 'btn ghost sm speak', title: 'Listen to this answer' }, '🔊 Listen');
    b.onclick = () => {
      if (speechSynthesis.speaking) { speechSynthesis.cancel(); document.querySelectorAll('.speak.on').forEach(x => { x.classList.remove('on'); x.textContent = '🔊 Listen'; }); if (b._on) { b._on = false; return; } }
      const txt = getText().replace(/[#*_`>|]/g, ' ').replace(/\[P\d+\]/g, ''); const u = new SpeechSynthesisUtterance(txt);
      const vs = speechSynthesis.getVoices(); const hasDeva = /[\u0900-\u097F]/.test(txt), hasArab = /[\u0600-\u06FF]/.test(txt);
      const want = hasDeva ? 'hi' : hasArab ? 'ur' : 'en'; u.voice = vs.find(v => v.lang.toLowerCase().startsWith(want + '-in')) || vs.find(v => v.lang.toLowerCase().startsWith(want)) || null; if (u.voice) u.lang = u.voice.lang;
      u.onend = u.onerror = () => { b._on = false; b.classList.remove('on'); b.textContent = '🔊 Listen'; };
      b._on = true; b.classList.add('on'); b.textContent = '■ Stop'; speechSynthesis.speak(u);
    };
    return b;
  }

  function renderAsk(el) {
    let cur = null, busy = false, status = null;
    const list = h('div', { class: 'chatlist' });
    const log = h('div', { class: 'chatlog' });
    const input = h('textarea', { class: 'chatin', rows: 1, placeholder: 'Ask anything — “is mahine food pe kitna kharch hua?”, “summarise my Ideas page”…' });
    const send = h('button', { class: 'btn primary send', title: 'Send', onclick: () => go() }, '↑');
    const modelTag = h('span', { class: 'faint' });
    const banner = h('div');
    const wrap = h('div', { class: 'ask' },
      h('aside', { class: 'askside' }, h('button', { class: 'btn primary', style: 'width:100%;justify-content:center', onclick: () => open(null) }, '+ New chat'), list),
      h('section', { class: 'askmain' }, banner, log, h('div', { class: 'composer' }, h('div', { class: 'cbox' }, input, micButton(input, () => go()), send), h('div', { class: 'row', style: 'justify-content:space-between;margin-top:6px' }, modelTag,
        h('span', { class: 'faint' }, 'Enter to send · Shift+Enter new line · 🎙 speak (right-click: language)')))));
    el.append(wrap);
    input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px'; });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); go(); } });
    log.addEventListener('click', (e) => { const a = e.target.closest('.cite'); if (a) { openPage(a.dataset.doc); location.hash = '#/pages'; } });

    let FM = null;
    const fmeta = async (fresh) => { if (!FM || fresh) FM = await ai('fin_meta'); return FM; };
    const money = (v, c) => Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 }) + ' ' + (c || '');
    function finCard(m, mi, p, i) {
      const box = h('div', { class: 'fcard ' + (p.type === 'transfer' ? 'tf' : p.kind) + ' ' + p.status });
      const label = p.type === 'transfer' ? 'Transfer' : p.kind === 'income' ? 'Income' : 'Expense';
      const sign = p.type === 'transfer' ? '⇄' : p.kind === 'income' ? '+' : '−';
      const summary = p.type === 'transfer' ? `${p.from_name || '?'} → ${p.to_name || '?'}` : [p.category, p.account].filter(Boolean).join(' · ');
      const draw = async () => {
        const head = h('div', { class: 'fhead' }, h('span', { class: 'fsign' }, sign), h('b', {}, label), h('span', { class: 'famt' }, money(p.amount, p.currency)),
          h('span', { class: 'fstat' }, p.status === 'saved' ? '✓ Saved' : p.status === 'cancelled' ? 'Cancelled' : 'Not saved yet'));
        if (p.status !== 'pending') {
          box.replaceChildren(head, h('div', { class: 'fline' }, [summary, p.title, p.date].filter(Boolean).join(' · '),
            p.status === 'saved' ? h('a', { href: '#/finance', class: 'flink' }, 'Open in Finance') : null));
          return;
        }
        const M = await fmeta().catch(() => ({ accounts: [], categories: [] }));
        const accSel = (val) => h('select', { class: 'inp' }, h('option', { value: '' }, 'Choose account…'), M.accounts.map(a => h('option', { value: a.id, selected: a.id === val }, `${a.name} (${a.currency})`)));
        const amt = h('input', { class: 'inp', inputmode: 'decimal', value: p.amount });
        const date = h('input', { class: 'inp', type: 'date', value: p.date });
        const title = h('input', { class: 'inp', value: p.title || '', placeholder: 'Title' });
        let fields, read;
        if (p.type === 'transfer') {
          const f = accSel(p.from_id), t = accSel(p.to_id);
          fields = [h('label', {}, 'From', f), h('label', {}, 'To', t), h('label', {}, 'Amount', amt), h('label', {}, 'Date', date), h('label', { class: 'wide' }, 'Note', title)];
          read = () => ({ from_id: f.value, to_id: t.value, amount: amt.value, date: date.value, title: title.value });
        } else {
          const acc = accSel(p.account_id);
          const dl = 'fc' + mi + '_' + i;
          const cat = h('input', { class: 'inp', value: p.category || '', list: dl, placeholder: 'Category' });
          const opts = h('datalist', { id: dl }, M.categories.filter(c => c.kind === p.kind).map(c => h('option', { value: c.name })));
          fields = [h('label', {}, 'Amount', amt), h('label', {}, 'Account', acc), h('label', {}, 'Category', cat, opts), h('label', {}, 'Date', date), h('label', { class: 'wide' }, 'Title', title)];
          read = () => { const c = M.categories.find(x => x.kind === p.kind && x.name.toLowerCase() === cat.value.trim().toLowerCase());
            return { amount: amt.value, account_id: acc.value, category: cat.value.trim(), category_id: c ? c.id : '', date: date.value, title: title.value }; };
        }
        const save = h('button', { class: 'btn primary', onclick: async () => {
          save.disabled = true;
          try { const r = await ai('fin_card', { id: cur.id, msg: mi, i, edits: read() }); Object.assign(p, r); m.actions[i] = p; toast('Saved in Finance ✓'); fmeta(true); draw(); }
          catch (e) { toast(e.message); save.disabled = false; }
        } }, 'Save');
        const cancel = h('button', { class: 'btn ghost', onclick: async () => { try { Object.assign(p, await ai('fin_card', { id: cur.id, msg: mi, i, cancel: true })); draw(); } catch (e) { toast(e.message); } } }, 'Cancel');
        box._save = () => save.click();
        box.replaceChildren(...[head, h('div', { class: 'fgrid' }, fields), p.problem ? h('div', { class: 'fprob' }, p.problem) : null, h('div', { class: 'row', style: 'margin-top:10px' }, save, cancel)].filter(Boolean));
      };
      draw();
      return box;
    }
    const bubble = (m, mi) => {
      if (m.role === 'user') return h('div', { class: 'msg me' }, h('div', { class: 'b' }, m.content));
      const used = [];
      for (const p of m.pages || []) used.push(h('a', { class: 'chip', onclick: () => { openPage(p.id); location.hash = '#/pages'; } }, (p.icon || '📄') + ' ' + p.title));
      if (m.finance) used.push(h('a', { class: 'chip', href: '#/finance' }, '💰 Finance'));
      return h('div', { class: 'msg ai' + (m.err ? ' err' : '') }, h('div', { class: 'av' }, ic('bot')), h('div', { class: 'b' }, h('div', { class: 'mdx', html: md(m.content, m.pages) }),
        used.length ? h('div', { class: 'used' }, h('span', { class: 'faint' }, 'Looked at:'), used) : null,
        (m.actions && m.actions.length) ? (() => {
          const cards = m.actions.map((p, i) => finCard(m, mi, p, i));
          const pend = m.actions.filter(p => p.status === 'pending').length;
          return h('div', { class: 'fcards' }, cards, pend > 1 ? h('button', { class: 'btn', onclick: () => cards.forEach(c => c._save && m.actions[cards.indexOf(c)].status === 'pending' && c._save()) }, `Save all ${pend}`) : null);
        })() : null,
        h('div', { class: 'row', style: 'margin-top:6px;gap:8px' }, m.err ? null : speakButton(() => m.content || ''), m.model ? h('span', { class: 'faint' }, m.model) : null)));
    };
    const empty = () => h('div', { class: 'askempty' }, h('div', { class: 'soonbox', style: 'padding:40px 10px' }, h('div', { class: 'ic' }, ic('bot')), h('h1', {}, 'Ask AI'),
      h('p', { class: 'sub', style: 'max-width:480px;margin:8px auto 18px' }, 'Chat with ChatGPT on your own plan. It knows your Finance book — ask about your money, or say “record 1200 lunch” and it adds it.'),
      h('div', { class: 'row', style: 'justify-content:center' }, ['Is mahine maine kis cheez pe sab se zyada kharch kiya?', 'Meri pages me ideas ka summary do', 'Aaj lunch 1200 ka Meezan se kharch hua'].map(t =>
        h('button', { class: 'btn', onclick: () => { input.value = t; go(); } }, t)))));
    async function loadList() {
      let rows = []; try { rows = await ai('chats'); } catch (e) { /* shown on send */ }
      list.replaceChildren(...rows.map(r => h('div', { class: 'chatitem' + (cur && cur.id === r.id ? ' on' : ''), onclick: () => open(r.id) },
        h('span', {}, r.title || 'Chat'),
        h('button', { class: 'x', title: 'Delete chat', onclick: async (e) => { e.stopPropagation(); if (!confirm('Delete this chat?')) return; await ai('delete', { id: r.id }); if (cur && cur.id === r.id) open(null); else loadList(); } }, '×'))));
      if (!rows.length) list.append(h('p', { class: 'faint', style: 'padding:10px' }, 'Your chats are saved here.'));
    }
    async function open(id) {
      cur = id ? await ai('chat', { id }) : null;
      log.replaceChildren(...(cur && cur.msgs.length ? cur.msgs.map((m, i) => bubble(m, i)) : [empty()]));
      log.scrollTop = log.scrollHeight; loadList(); input.focus();
    }
    async function checkStatus() {
      try { status = (await ai('settings')).chatgpt; } catch (e) { status = { state: 'none' }; }
      banner.replaceChildren(status.state === 'ready' ? '' : h('div', { class: 'askwarn' }, h('span', {}, 'ChatGPT is not connected yet.'), h('a', { class: 'btn primary', href: '#/settings', onclick: () => setTimeout(() => { const c = document.getElementById('aicard'); if (c) c.scrollIntoView({ behavior: 'smooth' }); }, 60) }, 'Connect in Settings')));
      modelTag.textContent = status.state === 'ready' ? 'ChatGPT' + (status.model ? ' · ' + status.model : '') + (status.email ? ' · ' + status.email : '') : '';
    }
    async function go() {
      const text = input.value.trim(); if (!text || busy) return;
      busy = true; send.disabled = true; input.value = ''; input.style.height = 'auto';
      if (!cur) { log.replaceChildren(); cur = { id: null, msgs: [] }; }
      log.append(bubble({ role: 'user', content: text }));
      const wait = h('div', { class: 'msg ai' }, h('div', { class: 'av' }, ic('bot')), h('div', { class: 'b' }, h('span', { class: 'dots' }, h('i'), h('i'), h('i'))));
      log.append(wait); log.scrollTop = log.scrollHeight;
      try {
        const r = await ai('ask', { id: cur.id, text });
        cur.id = r.id; cur.msgs = cur.msgs || []; cur.msgs[r.index] = r.msg; wait.replaceWith(bubble(r.msg, r.index)); loadList();
      } catch (e) { wait.replaceWith(bubble({ role: 'assistant', content: e.message, err: true })); input.value = text; if (/connect|sign in/i.test(e.message)) checkStatus(); }
      busy = false; send.disabled = false; log.scrollTop = log.scrollHeight; input.focus();
    }
    checkStatus(); open(null);
    window.addEventListener('hashchange', () => { if (location.hash === '#/ask') checkStatus(); });
  }

  // ── start ──
  async function start() {
    try {
      const r = await fetch('/api/me', { credentials: 'same-origin' });
      if (r.status === 401) { const j = await r.json().catch(() => ({})); location.href = j.configured === false ? '/login.html?setup=1' : '/api/auth/login?next=' + encodeURIComponent(location.pathname + location.hash); return; }
      ME = await r.json();
    } catch (e) { ME = null; }
    buildSide(); route();
    window.addEventListener('hashchange', route);
    $('#menu').onclick = () => { $('#side').classList.add('open'); $('#scrim').classList.add('on'); };
    $('#scrim').onclick = () => { $('#side').classList.remove('open'); $('#scrim').classList.remove('on'); };
    window.addEventListener('message', (e) => {
      if (e.origin !== location.origin || !e.data || e.data.curio !== 'go') return;
      if (e.data.to === 'pages' && e.data.doc) openPage(e.data.doc);
      location.hash = '#/' + e.data.to;
    });
  }
  start();
})();
