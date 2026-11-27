/* Curio Library on the web — Moodboard (all your saves) and My Boards.
   Pictures are kept small (shrunk here in the browser); the full files stay on your PC. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const h = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'html') e.innerHTML = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat(3)) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const toast = (m) => { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 2600); };
  async function api(op, args = {}) {
    const r = await fetch('/api/lib', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify({ op, args }) });
    if (r.status === 401) { top.location.href = '/api/auth/login'; throw new Error('Signing you in…'); }
    const j = await r.json(); if (j.error) throw new Error(j.error); return j.data;
  }
  const PL = { instagram: ['Instagram', '#e1306c'], pinterest: ['Pinterest', '#e60023'], youtube: ['YouTube', '#ff0000'], facebook: ['Facebook', '#1877f2'],
    behance: ['Behance', '#1769ff'], x: ['X', '#111'], web: ['Web', '#6e6e7a'], upload: ['Uploaded', '#f2602d'] };
  const COLORS = ['#5b5ff6', '#0ea5e9', '#f59e0b', '#e11d48', '#14795a', '#8b5cf6', '#f2602d', '#111827'];
  const fileUrl = (id) => '/api/file/' + encodeURIComponent(id);
  const mb = (b) => (b / 1048576).toFixed(b > 1048576 * 10 ? 0 : 1) + ' MB';

  let MODE = 'moodboard', F = { q: '', platform: '', category: '', board: null }, FACETS = null, ITEMS = [], done = false;
  const app = $('#app');

  function setMode() {
    MODE = location.hash.replace('#', '') === 'boards' ? 'boards' : 'moodboard';
    document.body.classList.toggle('mode-boards', MODE === 'boards');
    if (MODE === 'moodboard') F.board = null;
    draw();
  }

  async function draw() {
    try { FACETS = await api('facets'); } catch (e) { app.replaceChildren(h('div', { class: 'main' }, h('div', { class: 'empty' }, h('h2', {}, 'Could not load'), h('p', {}, e.message)))); return; }
    if (MODE === 'boards' && !F.board && FACETS.boards.length) F.board = FACETS.boards[0].id;
    const side = h('aside', { class: 'boards only-boards' }, h('h4', {}, h('span', {}, 'My Boards'), h('button', { class: 'btn ghost', style: 'height:26px;padding:0 6px', title: 'New board', onclick: newBoard }, '+')),
      FACETS.boards.map(b => h('div', { class: 'bd' + (F.board === b.id ? ' on' : ''), onclick: () => { F.board = b.id; draw(); } }, h('i', { style: `background:${b.color || '#f2602d'}` }), h('span', {}, b.name), h('small', {}, b.n),
        h('button', { class: 'x', title: 'Delete board', onclick: (e) => { e.stopPropagation(); delBoard(b); } }, '×'))),
      FACETS.boards.length ? null : h('p', { class: 'stat', style: 'padding:8px' }, 'No boards yet. Make one, then add saves to it from the Moodboard.'));
    const board = FACETS.boards.find(b => b.id === F.board);
    const title = MODE === 'boards' ? (board ? board.name : 'My Boards') : 'Moodboard';
    const search = h('input', { class: 'search', type: 'search', placeholder: 'Search captions, titles, creators…', value: F.q });
    let tmr; search.addEventListener('input', () => { clearTimeout(tmr); tmr = setTimeout(() => { F.q = search.value.trim(); load(true); }, 250); });
    const chips = h('div', { class: 'chips' }, h('button', { class: 'chip' + (!F.platform ? ' on' : ''), onclick: () => { F.platform = ''; draw(); } }, 'All ', h('small', {}, FACETS.total)),
      FACETS.platforms.map(p => h('button', { class: 'chip' + (F.platform === p.platform ? ' on' : ''), onclick: () => { F.platform = p.platform; draw(); } }, (PL[p.platform] || [p.platform])[0], ' ', h('small', {}, p.n))));
    const cat = h('select', { class: 'inp', onchange: () => { F.category = cat.value; load(true); } }, h('option', { value: '' }, 'All categories'),
      FACETS.categories.map(c => h('option', { value: c.category, selected: c.category === F.category }, `${c.category} (${c.n})`)));
    const grid = h('div', { class: 'grid', id: 'grid' });
    const main = h('div', { class: 'main' },
      h('div', { class: 'head' }, h('h1', {}, title), h('span', { class: 'stat' }, `${FACETS.total} saves on the web · ${mb(FACETS.bytes || 0)}`),
        h('button', { class: 'btn', onclick: addDialog }, '+ Add'), h('button', { class: 'btn primary', onclick: importDialog }, 'Import from desktop')),
      FACETS.total ? h('div', { class: 'tools' }, search, chips, FACETS.categories.length ? cat : null) : null,
      grid, h('div', { class: 'more', id: 'more' }));
    app.replaceChildren(side, main);
    if (!FACETS.total) {
      grid.replaceWith(h('div', { class: 'empty' }, h('div', { class: 'ic' }, '▦'), h('h2', {}, 'Your Moodboard is empty on the web'),
        h('p', { style: 'max-width:520px;margin:6px auto 18px' }, 'Bring a few saves from the desktop app to try it out — choose how many (start with 30–50), and Curio copies small pictures of them here. Your PC files are not touched.'),
        h('div', { class: 'row', style: 'justify-content:center' }, h('button', { class: 'btn primary', onclick: importDialog }, 'Import from desktop'), h('button', { class: 'btn', onclick: addDialog }, '+ Add a picture or link'))));
      return;
    }
    if (MODE === 'boards' && !board) { grid.replaceWith(h('div', { class: 'empty' }, h('h2', {}, 'No boards yet'), h('p', {}, 'Make your first board.'), h('button', { class: 'btn primary', onclick: newBoard }, '+ New board'))); return; }
    load(true);
  }

  async function load(reset) {
    if (reset) { ITEMS = []; done = false; }
    const grid = $('#grid'), more = $('#more'); if (!grid) return;
    const rows = await api('items', { q: F.q, platform: F.platform, category: F.category, board: MODE === 'boards' ? F.board : null, offset: ITEMS.length, limit: 120 });
    if (reset) grid.replaceChildren();
    ITEMS = ITEMS.concat(rows); done = rows.length < 120;
    for (const it of rows) grid.append(tile(it));
    if (!ITEMS.length) grid.replaceChildren(h('div', { class: 'empty', style: 'column-span:all' }, h('p', {}, MODE === 'boards' ? 'Nothing in this board yet — open a save in the Moodboard and tap the board name.' : 'Nothing matches.')));
    more.replaceChildren(done ? '' : h('button', { class: 'btn', onclick: () => load(false) }, 'Show more'));
  }

  const isMov = (f) => /\.(mp4|mov|webm|m4v|mkv)$/i.test(f || '');      // 10.52: a full video (sent online from the desktop, on R2)
  function tile(it) {
    const m = it.media || [], first = m[0];
    const vid = m.some(x => x.kind === 'video');
    const img = first ? (isMov(first.file) ? h('video', { src: fileUrl(first.file) + '#t=0.5', muted: true, playsinline: true, preload: 'metadata', style: 'width:100%;display:block' })
      : h('img', { src: fileUrl(first.file), loading: 'lazy', alt: '', style: first.w && first.h ? `aspect-ratio:${first.w}/${first.h}` : null }))
      : h('div', { class: 'noimg' }, it.title || it.url || 'No picture');
    const p = PL[it.platform] || [it.platform];
    return h('div', { class: 'tile', onclick: () => viewer(it) }, img,
      h('div', { class: 'badges' }, h('span', { class: 'bdg' }, p[0]), vid ? h('span', { class: 'bdg r' }, '▶') : m.length > 1 ? h('span', { class: 'bdg r' }, '1/' + m.length) : null),
      (it.title || it.author) ? h('div', { class: 'cap' }, it.title ? h('b', {}, it.title) : null, h('small', {}, [it.author, it.category].filter(Boolean).join(' · '))) : null);
  }

  // ── viewer ──
  async function viewer(it) {
    let i = 0; const m = it.media || [];
    const imgBox = h('div', { class: 'vmedia' });
    const show = () => {
      const cur = m[i];
      imgBox.replaceChildren(...[cur ? (isMov(cur.file) ? h('video', { src: fileUrl(cur.file), controls: true, playsinline: true, autoplay: true, style: 'max-width:100%;max-height:80vh' })
        : h('img', { src: fileUrl(cur.file), alt: '' })) : h('div', { style: 'color:#aaa;padding:40px' }, 'No picture for this save.'),
        m.length > 1 ? [h('button', { class: 'nav l', onclick: () => { i = (i - 1 + m.length) % m.length; show(); } }, '‹'), h('button', { class: 'nav r', onclick: () => { i = (i + 1) % m.length; show(); } }, '›'),
          h('span', { class: 'count' }, `${i + 1} / ${m.length}`)] : null,
        cur && cur.kind === 'video' && !isMov(cur.file) ? h('span', { class: 'vid' }, '▶ Video — still frame here, the full video is on your PC / original post') : null].flat().filter(Boolean));
    };
    show();
    const note = h('textarea', { placeholder: 'Your note…' }, it.note || '');
    let nt; note.addEventListener('input', () => { clearTimeout(nt); nt = setTimeout(() => api('note', { platform: it.platform, item_id: it.item_id, note: note.value }).then(() => { it.note = note.value; }).catch(e => toast(e.message)), 500); });
    const bwrap = h('div', { class: 'bchips' });
    const drawBoards = async () => {
      const inB = new Set(await api('item_boards', { platform: it.platform, item_id: it.item_id }));
      bwrap.replaceChildren(...FACETS.boards.map(b => h('button', { class: 'bchip' + (inB.has(b.id) ? ' on' : ''), onclick: async () => {
        await api(inB.has(b.id) ? 'board_take' : 'board_add', { board: b.id, platform: it.platform, item_id: it.item_id });
        toast(inB.has(b.id) ? 'Taken out of ' + b.name : 'Added to ' + b.name); drawBoards(); b.n += inB.has(b.id) ? -1 : 1;
      } }, h('i', { style: `background:${b.color}` }), b.name)), h('button', { class: 'bchip', onclick: async () => { await newBoard(); drawBoards(); } }, '+ New board'));
    };
    drawBoards();
    const p = PL[it.platform] || [it.platform];
    const info = h('div', { class: 'vinfo' },
      h('h2', {}, it.title || '(no title)'),
      h('div', { class: 'meta' }, h('span', {}, p[0]), it.author ? h('span', {}, '· ' + it.author) : null, it.category ? h('span', {}, '· ' + it.category) : null, it.published ? h('span', {}, '· ' + String(it.published).slice(0, 10)) : null),
      it.caption ? h('div', { class: 'capt' }, it.caption) : null,
      it.url ? h('a', { class: 'btn', href: it.url, target: '_blank', rel: 'noopener noreferrer' }, 'Open original ↗') : null,
      h('label', {}, 'Boards'), bwrap, h('label', {}, 'Note'), note,
      h('div', { class: 'row', style: 'margin-top:auto;padding-top:8px' }, h('button', { class: 'btn danger', onclick: async () => {
        if (!confirm('Remove this save from Curio Web? (Your PC copy stays.)')) return;
        await api('remove', { platform: it.platform, item_id: it.item_id }); close(); toast('Removed from the web'); draw();
      } }, 'Remove from web')));
    const ov = h('div', { class: 'ov', onclick: (e) => { if (e.target === ov) close(); } }, h('div', { class: 'viewer' }, imgBox, info), h('button', { class: 'close', onclick: () => close() }, '×'));
    const key = (e) => { if (e.key === 'Escape') close(); if (m.length > 1 && e.target.tagName !== 'TEXTAREA') { if (e.key === 'ArrowRight') { i = (i + 1) % m.length; show(); } if (e.key === 'ArrowLeft') { i = (i - 1 + m.length) % m.length; show(); } } };
    function close() { ov.remove(); document.removeEventListener('keydown', key); }
    document.addEventListener('keydown', key); document.body.append(ov);
  }

  // ── boards ──
  async function newBoard() {
    const name = prompt('Board name'); if (!name || !name.trim()) return;
    const id = await api('board_save', { name: name.trim(), color: COLORS[(FACETS.boards.length) % COLORS.length] });
    FACETS.boards.push({ id, name: name.trim(), color: COLORS[(FACETS.boards.length) % COLORS.length], n: 0 });
    if (MODE === 'boards') { F.board = id; draw(); }
    toast('Board made');
  }
  async function delBoard(b) {
    if (!confirm(`Delete the board “${b.name}”? The saves in it stay in your Moodboard.`)) return;
    await api('board_delete', { id: b.id }); if (F.board === b.id) F.board = null; draw();
  }

  // ── pictures: shrink in the browser ──
  function loadImg(blob) {
    return new Promise((ok, bad) => { const u = URL.createObjectURL(blob); const im = new Image(); im.onload = () => { ok([im, u]); }; im.onerror = () => { URL.revokeObjectURL(u); bad(new Error('not a picture')); }; im.src = u; });
  }
  function canvasOut(src, w, h2, max) {
    const s = Math.min(1, max / Math.max(w, h2)); const cw = Math.max(1, Math.round(w * s)), ch = Math.max(1, Math.round(h2 * s));
    const c = document.createElement('canvas'); c.width = cw; c.height = ch; c.getContext('2d').drawImage(src, 0, 0, cw, ch);
    return new Promise(ok => c.toBlob(b => ok([b, cw, ch]), 'image/jpeg', 0.82));
  }
  async function shrinkImage(blob, max = 1200) {
    const [im, u] = await loadImg(blob); try { return await canvasOut(im, im.naturalWidth, im.naturalHeight, max); } finally { URL.revokeObjectURL(u); }
  }
  function videoFrame(blob, max = 1000) {
    return new Promise((ok, bad) => {
      const u = URL.createObjectURL(blob); const v = document.createElement('video'); v.muted = true; v.preload = 'auto'; v.playsInline = true;
      const t = setTimeout(() => { cleanup(); bad(new Error('video timeout')); }, 12000);
      const cleanup = () => { clearTimeout(t); URL.revokeObjectURL(u); v.removeAttribute('src'); v.load(); };
      v.onloadedmetadata = () => { v.currentTime = Math.min(1.2, (v.duration || 2) / 3); };
      v.onseeked = async () => { try { const r = await canvasOut(v, v.videoWidth, v.videoHeight, max); cleanup(); ok(r); } catch (e) { cleanup(); bad(e); } };
      v.onerror = () => { cleanup(); bad(new Error('video cannot be read here')); };
      v.src = u;
    });
  }
  const toB64 = (blob) => new Promise(ok => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1]); r.readAsDataURL(blob); });
  async function upload(blob, name) { return api('put_file', { b64: await toB64(blob), mime: 'image/jpeg', name }); }

  // ── add one save by hand ──
  function addDialog() {
    const files = h('input', { type: 'file', accept: 'image/*,video/*', multiple: true });
    const title = h('input', { class: 'inp', placeholder: 'Title (optional)' });
    const url = h('input', { class: 'inp', placeholder: 'Link to the original (optional) — https://…' });
    const cat = h('input', { class: 'inp', placeholder: 'Category (optional)', list: 'cats' });
    const dl = h('datalist', { id: 'cats' }, (FACETS.categories || []).map(c => h('option', { value: c.category })));
    const go = h('button', { class: 'btn primary', onclick: async () => {
      if (!files.files.length && !url.value.trim()) return toast('Choose a picture or paste a link');
      go.disabled = true;
      try {
        const media = [];
        for (const f of files.files) {
          const [b, w, hh] = f.type.startsWith('video') ? await videoFrame(f) : await shrinkImage(f);
          const r = await upload(b, f.name); media.push({ file: r.id, kind: f.type.startsWith('video') ? 'video' : 'image', w, h: hh });
        }
        let plat = 'upload'; const u = url.value.trim();
        if (/instagram\.com/.test(u)) plat = 'instagram'; else if (/pinterest\./.test(u) || /pin\.it/.test(u)) plat = 'pinterest'; else if (/youtu/.test(u)) plat = 'youtube'; else if (/facebook\.com|fb\.watch/.test(u)) plat = 'facebook'; else if (u) plat = 'web';
        await api('save', { platform: plat, url: u, title: title.value.trim(), category: cat.value.trim(), media });
        close(); toast('Added'); draw();
      } catch (e) { toast(e.message); go.disabled = false; }
    } }, 'Add');
    const { close } = modal(h('div', { class: 'dlg' }, h('h2', {}, 'Add to Moodboard'), h('p', {}, 'Pictures are shrunk to a light copy before they are saved. A video keeps one still frame.'),
      h('label', { class: 'fld' }, h('span', {}, 'Pictures or videos'), files), h('label', { class: 'fld' }, h('span', {}, 'Title'), title),
      h('label', { class: 'fld' }, h('span', {}, 'Link'), url), h('label', { class: 'fld' }, h('span', {}, 'Category'), cat, dl),
      h('div', { class: 'row', style: 'justify-content:flex-end;margin-top:16px' }, h('button', { class: 'btn ghost', onclick: () => close() }, 'Cancel'), go)));
  }
  function modal(box) {
    const ov = h('div', { class: 'ov', onclick: (e) => { if (e.target === ov && !ov._busy) close(); } }, box);
    const key = (e) => { if (e.key === 'Escape' && !ov._busy) close(); };
    function close() { ov.remove(); document.removeEventListener('keydown', key); }
    document.addEventListener('keydown', key); document.body.append(ov); return { close, ov };
  }

  // ── import a few saves from the desktop app ──
  let _sql = null;
  function loadSQL() {
    if (_sql) return _sql;
    _sql = new Promise((ok, bad) => { const s = h('script', { src: '/vendor/sql-wasm.js' }); s.onload = () => window.initSqlJs({ locateFile: f => '/vendor/' + f }).then(ok, bad); s.onerror = () => bad(new Error('Could not load the reader')); document.head.append(s); });
    return _sql;
  }
  const norm = (p) => String(p || '').replace(/\\/g, '/').toLowerCase().split('/').filter(Boolean);
  function importDialog() {
    let DB = null, rows = [], boards = [], boardItems = [];
    const fDb = h('input', { type: 'file', accept: '.sqlite3,.sqlite,.db' });
    const fDir = h('input', { type: 'file', webkitdirectory: true, directory: true, multiple: true });
    const howMany = h('input', { class: 'inp', type: 'number', min: 1, max: 500, value: 40, style: 'width:100px' });
    const plat = h('select', { class: 'inp' }, h('option', { value: '' }, 'All platforms'));
    const catSel = h('select', { class: 'inp' }, h('option', { value: '' }, 'All categories'));
    const withBoards = h('input', { type: 'checkbox', checked: true });
    const info = h('div', { class: 'stat', style: 'margin-top:8px' });
    const bar = h('div', { class: 'bar', style: 'display:none' }, h('i')); const log = h('div', { class: 'log' });
    const say = (t) => { log.textContent += t + '\n'; log.scrollTop = log.scrollHeight; };
    fDb.onchange = async () => {
      if (!fDb.files[0]) return;
      try {
        const SQL = await loadSQL(); DB = new SQL.Database(new Uint8Array(await fDb.files[0].arrayBuffer()));
        const q = (s) => { const r = DB.exec(s); return r.length ? r[0].values.map(v => Object.fromEntries(r[0].columns.map((c, i) => [c, v[i]]))) : []; };
        rows = q("SELECT platform, item_id, url, category, title, caption, published, media, author, updated FROM items WHERE media IS NOT NULL AND media != '[]' ORDER BY updated DESC");
        try { boards = q('SELECT id, name, parent, color, pos FROM boards'); boardItems = q('SELECT board, platform, item_id FROM board_items'); } catch (e) { boards = []; boardItems = []; }
        const by = {}; const cats = {}; for (const r of rows) { by[r.platform] = (by[r.platform] || 0) + 1; if (r.category) cats[r.category] = (cats[r.category] || 0) + 1; }
        plat.replaceChildren(h('option', { value: '' }, `All platforms (${rows.length})`), Object.entries(by).map(([k, n]) => h('option', { value: k }, `${(PL[k] || [k])[0]} (${n})`)));
        catSel.replaceChildren(h('option', { value: '' }, 'All categories'), Object.entries(cats).sort((a, b) => b[1] - a[1]).map(([k, n]) => h('option', { value: k }, `${k} (${n})`)));
        info.textContent = `${rows.length} saves with pictures found · ${boards.length} boards. Newest first.`;
      } catch (e) { info.textContent = 'This does not look like Curio\'s library file: ' + e.message; DB = null; }
    };
    const go = h('button', { class: 'btn primary', onclick: () => run().catch(e => { say('Stopped: ' + e.message); toast(e.message); ov._busy = false; go.disabled = false; }) }, 'Start import');
    async function run() {
      if (!DB) return toast('Choose library_v4.sqlite3 first');
      if (!fDir.files.length) return toast('Choose your Media folder (step 2)');
      log.textContent = ''; say('Checking what is already on the web…');
      const n = Math.max(1, Math.min(500, parseInt(howMany.value, 10) || 40));
      const pick = rows.filter(r => (!plat.value || r.platform === plat.value) && (!catSel.value || r.category === catSel.value));
      const already = new Set(await api('known', { keys: pick.slice(0, n * 3).map(r => [r.platform, String(r.item_id)]) }));
      const todo = pick.filter(r => !already.has(r.platform + ':' + r.item_id)).slice(0, n);
      if (!todo.length) { say('These saves are already on the web.'); return toast('These saves are already on the web'); }
      // index the chosen folder by the last parts of each path
      const idx3 = new Map(), idx2 = new Map();
      for (const f of fDir.files) { const p = norm(f.webkitRelativePath || f.name); idx3.set(p.slice(-3).join('/'), f); idx2.set(p.slice(-2).join('/'), f); }
      go.disabled = true; ov._busy = true; bar.style.display = 'block';
      say(`Importing ${todo.length} saves…`);
      let ok = 0, miss = 0, bytes = 0; const okKeys = new Set();
      for (let k = 0; k < todo.length; k++) {
        const r = todo[k]; let media = [];
        try { media = JSON.parse(r.media || '[]'); } catch (e) { media = []; }
        const out = [];
        for (const m of media.slice(0, 10)) {
          const p = norm(m.path); const f = idx3.get(p.slice(-3).join('/')) || idx2.get(p.slice(-2).join('/'));
          if (!f) continue;
          try {
            const isV = m.kind === 'video' || /^video\//.test(f.type) || /\.(mp4|mov|webm|mkv|m4v)$/i.test(f.name);
            const [b, w, hh] = isV ? await videoFrame(f) : await shrinkImage(f);
            const up = await upload(b, f.name); bytes += up.size; out.push({ file: up.id, kind: isV ? 'video' : 'image', w, h: hh });
          } catch (e) { /* this one file could not be read */ }
        }
        if (!out.length) { miss++; say(`  skipped “${(r.title || r.item_id).slice(0, 50)}” — its files are not in the chosen folder`); }
        else {
          const t = Date.parse(r.updated || '') / 1000;
          await api('save', { platform: r.platform, item_id: String(r.item_id), url: r.url, category: r.category, title: r.title, caption: r.caption, published: r.published, author: r.author, media: out, added: isNaN(t) ? null : t });
          ok++; okKeys.add(r.platform + ':' + r.item_id);
        }
        bar.firstChild.style.width = Math.round((k + 1) / todo.length * 100) + '%';
      }
      if (withBoards.checked && boards.length && okKeys.size) {
        const fx = await api('facets'); const byName = new Map(fx.boards.map(b => [b.name.toLowerCase(), b.id])); const map = new Map();
        for (const b of boards) {
          const used = boardItems.some(x => x.board === b.id && okKeys.has(x.platform + ':' + x.item_id)); if (!used) continue;
          let id = byName.get(String(b.name).toLowerCase()); if (!id) { id = await api('board_save', { name: b.name, color: b.color || '#f2602d' }); byName.set(String(b.name).toLowerCase(), id); }
          map.set(b.id, id);
        }
        let linked = 0;
        for (const x of boardItems) if (map.has(x.board) && okKeys.has(x.platform + ':' + x.item_id)) { await api('board_add', { board: map.get(x.board), platform: x.platform, item_id: String(x.item_id) }); linked++; }
        if (map.size) say(`Boards: ${map.size} (${linked} saves placed in them)`);
      }
      say(`Done ✓ ${ok} saves added (${mb(bytes)})${miss ? ` · ${miss} skipped` : ''}.`);
      ov._busy = false; go.disabled = false; go.textContent = 'Import more'; draw();
    }
    const { ov } = modal(h('div', { class: 'dlg' }, h('h2', {}, 'Import from the desktop app'),
      h('p', {}, 'Try the web Moodboard with a few of your saves. Everything is read here in your browser; only light copies of the pictures go to your database. Nothing on your PC changes.'),
      h('div', { class: 'steps' },
        h('div', { class: 'step' }, h('div', {}, 'Choose ', h('code', {}, 'library_v4.sqlite3'), ' from your Curio data folder (', h('code', {}, 'C:\\AI\\Projects\\curio\\Media'), ').', h('div', { class: 'drop' }, fDb), info)),
        h('div', { class: 'step' }, h('div', {}, 'Choose the folder with the pictures — your ', h('code', {}, 'Media'), ' folder, or just one platform folder inside it (e.g. ', h('code', {}, 'Media\\instagram'), ') to keep it quick. The browser may ask “upload N files?” — it only reads the ones it needs.', h('div', { class: 'drop' }, fDir))),
        h('div', { class: 'step' }, h('div', {}, 'How many (newest first):', h('div', { class: 'row', style: 'margin-top:8px' }, howMany, plat, catSel),
          h('label', { class: 'row', style: 'margin-top:10px;gap:8px;cursor:pointer' }, withBoards, h('span', {}, 'Also bring their My Boards'))))),
      h('div', { class: 'row', style: 'justify-content:flex-end' }, h('button', { class: 'btn ghost', onclick: () => { if (!ov._busy) ov.remove(); } }, 'Close'), go), bar, log));
  }

  window.addEventListener('hashchange', setMode);
  setMode();
})();
