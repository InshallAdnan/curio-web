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
    insta: 'M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM17.5 6.5h.01', pin: 'M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zM12 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
    fb: 'M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z', upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12', out: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  };
  const ic = (n) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '1.8'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', P[n] || ''); s.append(p); return s; };

  // ── what is in the sidebar ──
  const LIVE = { home: 1, pages: 1, finance: 1, calendar: 1, settings: 1 };
  const NAV = [
    [null, [['home', 'Home', 'home'], ['explore', 'Explore', 'explore']]],
    ['Library', [['moodboard', 'Moodboard', 'grid'], ['boards', 'My Boards', 'bookmark'], ['bookmarks', 'Bookmarks', 'globe'], ['insights', 'Insights', 'chart'], ['rediscover', 'Rediscover', 'spark']]],
    ['Media', [['creators', 'Creators', 'users'], ['youtube', 'YouTube', 'play'], ['songs', 'Songs', 'music']]],
    ['AI', [['ask', 'Ask AI · ChatGPT', 'bot'], ['notebooks', 'Notebooks', 'book']]],
    ['Workspace', [['pages', 'Pages', 'page'], ['finance', 'Finance', 'wallet'], ['calendar', 'Calendar', 'cal']]],
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
    return view(k, (v) => { v.classList.add('frame'); v.append(h('iframe', { src, title: TITLE[k] })); });
  }

  function route() {
    const k = (location.hash.match(/^#\/([\w-]+)/) || [])[1] || 'home';
    let v;
    if (k === 'pages') v = frame('pages', '/pages/index.html?theme=' + theme() + '#/documents');
    else if (k === 'finance') v = frame('finance', '/finance/index.html?theme=' + theme());
    else if (k === 'calendar') v = frame('calendar', '/calendar/index.html?theme=' + theme());
    else if (k === 'home') { v = view('home', () => {}); renderHome(v); }
    else if (k === 'settings') { v = view('settings', () => {}); renderSettings(v); }
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
      h('div', { class: 'grid', style: 'grid-template-columns:1fr' }, storageCard(), importCard(), themeCard(), accountCard())));
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
      h('p', { class: 'faint', style: 'margin-top:14px' }, 'ChatGPT (Sign in with ChatGPT) and the other sections are coming next. The desktop app keeps working on its own.'));
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
