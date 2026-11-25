/* Curio Pages — extras (clean-room, written for Curio).
   Adds the page-level tools: header (edited time, favourite, copy link, lock badge), a fuller ⋯ menu
   (search actions, copy link / contents, duplicate, move to, version history, appearance, lock, undo, import, export,
   word count), Favorites + Recents in the sidebar, a table of contents panel, and a quick “Form” to add database rows.
   Talks to pages_ext.py through Qt's web channel ('curioext'); everything stays on this PC. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const h = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (k === 'html') e.innerHTML = v;
      else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ── bridge ──────────────────────────────────────────────────────────────────────────
  let EXT = null, CORE = null;
  const call = (obj, name, ...args) => new Promise((ok, bad) => {
    if (!obj || typeof obj[name] !== 'function') return bad(new Error('Pages is still starting — try again in a moment.'));
    obj[name](...args, r => {
      let v; try { v = JSON.parse(r); } catch { v = r; }
      if (v && v.error) bad(new Error(v.error)); else ok(v);
    });
  });
  const ext = (n, ...a) => call(EXT, n, ...a);
  const core = (n, ...a) => call(CORE, n, ...a);

  const docId = () => (location.hash.match(/#\/documents\/([\w-]+)/) || [])[1] || null;
  const bn = () => window.__bn || null;

  // ── small UI kit ────────────────────────────────────────────────────────────────────
  const css = `
  .cx-btn{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 8px;border-radius:6px;font-size:13px;color:hsl(var(--muted-foreground));background:none;border:0;cursor:pointer;white-space:nowrap}
  .cx-btn:hover{background:hsl(var(--accent));color:hsl(var(--foreground))}
  .cx-btn.on{color:#e3a008}
  .cx-edited{font-size:12px;color:hsl(var(--muted-foreground));margin-right:2px;white-space:nowrap}
  .cx-badge{font-size:11px;padding:2px 8px;border-radius:99px;background:hsl(var(--secondary));color:hsl(var(--muted-foreground))}
  .cx-sep{height:1px;background:hsl(var(--border));margin:4px -4px}
  .cx-item{display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:4px;font-size:13.5px;cursor:pointer;user-select:none;color:hsl(var(--popover-foreground))}
  .cx-item:hover,.cx-item.kb{background:hsl(var(--accent))}
  .cx-item .ic{width:18px;text-align:center;opacity:.75;font-size:14px}
  .cx-item .kbd{margin-left:auto;font-size:11px;color:hsl(var(--muted-foreground))}
  .cx-item .val{margin-left:auto;font-size:12px;color:hsl(var(--muted-foreground))}
  .cx-search{width:100%;box-sizing:border-box;margin:2px 0 4px;padding:6px 8px;font-size:13px;border:1px solid hsl(var(--border));border-radius:6px;background:hsl(var(--background));color:hsl(var(--foreground));outline:none}
  .cx-foot{font-size:11.5px;color:hsl(var(--muted-foreground));padding:6px 8px 4px;line-height:1.5}
  .cx-sw{width:30px;height:17px;border-radius:99px;background:hsl(var(--muted));position:relative;margin-left:auto;transition:.15s;flex:none}
  .cx-sw:after{content:'';position:absolute;left:2px;top:2px;width:13px;height:13px;border-radius:50%;background:#fff;transition:.15s;box-shadow:0 1px 2px #0003}
  .cx-sw.on{background:#2383e2}.cx-sw.on:after{left:15px}
  .cx-fonts{display:flex;gap:6px;padding:4px 6px 8px}
  .cx-font{flex:1;border-radius:6px;padding:6px 0 4px;text-align:center;cursor:pointer;border:1px solid transparent}
  .cx-font:hover{background:hsl(var(--accent))}.cx-font.on{border-color:#2383e2;background:hsl(var(--accent))}
  .cx-font b{display:block;font-size:20px;font-weight:500;color:hsl(var(--foreground))}.cx-font span{font-size:11px;color:hsl(var(--muted-foreground))}
  .cx-overlay{position:fixed;inset:0;background:#0007;z-index:2147483000;display:flex;align-items:flex-start;justify-content:center;padding-top:9vh}
  .cx-modal{background:hsl(var(--popover));color:hsl(var(--popover-foreground));border:1px solid hsl(var(--border));border-radius:10px;box-shadow:0 20px 60px #0005;width:min(560px,92vw);max-height:78vh;display:flex;flex-direction:column;overflow:hidden;font-size:14px}
  .cx-modal.wide{width:min(980px,94vw);height:78vh}
  .cx-mh{display:flex;align-items:center;gap:10px;padding:14px 16px 10px;font-weight:600;font-size:15px}
  .cx-mh .x{margin-left:auto;cursor:pointer;opacity:.6;font-size:18px;font-weight:400}.cx-mh .x:hover{opacity:1}
  .cx-mb{padding:0 16px 14px;overflow:auto;flex:1}
  .cx-mf{display:flex;gap:8px;justify-content:flex-end;padding:10px 16px;border-top:1px solid hsl(var(--border))}
  .cx-primary{background:#2383e2;color:#fff;border:0;border-radius:6px;padding:7px 14px;font-size:13.5px;cursor:pointer}.cx-primary:hover{background:#0f6fcf}
  .cx-ghost{background:none;border:1px solid hsl(var(--border));color:hsl(var(--foreground));border-radius:6px;padding:7px 14px;font-size:13.5px;cursor:pointer}.cx-ghost:hover{background:hsl(var(--accent))}
  .cx-list .cx-item{padding:7px 8px}.cx-list .path{font-size:11.5px;color:hsl(var(--muted-foreground));margin-left:auto;max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .cx-vh{display:flex;gap:0;flex:1;min-height:0}
  .cx-vh .l{width:250px;border-right:1px solid hsl(var(--border));overflow:auto;padding:6px}
  .cx-vh .r{flex:1;overflow:auto;padding:16px 28px;line-height:1.6;font-size:14px}
  .cx-prev h1{font-size:1.7em;margin:.6em 0 .2em}.cx-prev h2{font-size:1.35em;margin:.6em 0 .2em}.cx-prev h3{font-size:1.15em;margin:.5em 0 .2em}
  .cx-prev p{margin:.3em 0}.cx-prev ul,.cx-prev ol{padding-left:1.4em}.cx-prev img{max-width:100%}.cx-prev blockquote{border-left:3px solid hsl(var(--border));margin:0;padding-left:12px}
  .cx-vh .v{padding:8px 10px;border-radius:6px;cursor:pointer;font-size:13px}.cx-vh .v:hover{background:hsl(var(--accent))}.cx-vh .v.on{background:hsl(var(--accent));font-weight:600}
  .cx-vh .v small{display:block;font-weight:400;color:hsl(var(--muted-foreground));font-size:11.5px}
  .cx-field{display:grid;grid-template-columns:150px 1fr;align-items:center;gap:10px;margin:8px 0}
  .cx-field label{font-size:13px;color:hsl(var(--muted-foreground))}
  .cx-field input,.cx-field select,.cx-field textarea{width:100%;box-sizing:border-box;padding:7px 9px;border:1px solid hsl(var(--border));border-radius:6px;background:hsl(var(--background));color:hsl(var(--foreground));font-size:13.5px;font-family:inherit}
  .cx-chips{display:flex;flex-wrap:wrap;gap:6px}.cx-chip{padding:3px 9px;border-radius:5px;font-size:12.5px;cursor:pointer;border:1px solid hsl(var(--border))}.cx-chip.on{background:#2383e2;color:#fff;border-color:#2383e2}
  .cx-side{padding:4px 0 6px}
  .cx-side .t{font-size:11.5px;font-weight:600;color:hsl(var(--muted-foreground));padding:8px 12px 4px;display:flex;align-items:center}
  .cx-side .t span{margin-left:auto;cursor:pointer;opacity:.6;font-weight:400}
  .cx-side .p{display:flex;align-items:center;gap:8px;font-size:13.5px;padding:3px 12px 3px 14px;cursor:pointer;color:hsl(var(--muted-foreground));white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-height:27px}
  .cx-side .p:hover{background:hsl(var(--primary)/.05)}.cx-side .p.on{background:hsl(var(--primary)/.06);color:hsl(var(--foreground))}
  .cx-toc{position:fixed;right:18px;top:120px;width:220px;max-height:60vh;overflow:auto;font-size:12.5px;z-index:50;padding:8px 6px;border-radius:8px}
  .cx-toc:hover{background:hsl(var(--background));box-shadow:0 4px 20px #0002}
  .cx-toc a{display:block;padding:3px 8px;border-radius:4px;color:hsl(var(--muted-foreground));text-decoration:none;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cx-toc a:hover{background:hsl(var(--accent));color:hsl(var(--foreground))}
  .cx-toc .tt{font-weight:600;font-size:11px;color:hsl(var(--muted-foreground));padding:0 8px 4px}
  .cx-lockbar{display:flex;align-items:center;gap:10px;justify-content:center;font-size:12.5px;padding:6px;background:hsl(var(--secondary));color:hsl(var(--muted-foreground))}
  .cx-lockbar button{background:none;border:0;color:#2383e2;cursor:pointer;font-size:12.5px}
  .cx-formbtn{display:inline-flex;align-items:center;height:28px;padding:0 8px;border-radius:5px;font-size:13px;color:hsl(var(--muted-foreground));cursor:pointer;margin-right:2px}
  .cx-formbtn:hover{background:hsl(var(--accent))}
.cx-com{margin:4px 0 14px;padding:8px 0 4px;border-bottom:1px solid hsl(var(--border));font-size:13.5px}
  .cx-ct{font-size:12px;font-weight:600;color:hsl(var(--muted-foreground));margin-bottom:4px}
  .cx-c{display:flex;gap:8px;align-items:flex-start;padding:5px 0}.cx-c small{font-size:11px;color:hsl(var(--muted-foreground))}
  .cx-c.done>div{opacity:.5;text-decoration:line-through}.cx-ck{cursor:pointer;opacity:.6}.cx-cx{cursor:pointer;opacity:0;padding:0 4px}.cx-c:hover .cx-cx{opacity:.6}
  .cx-cin{width:100%;border:0;outline:none;background:none;padding:6px 0;font-size:13.5px;color:hsl(var(--foreground))}
  .cx-rsel{position:absolute;left:-24px;top:50%;margin-top:-8px;width:16px;height:16px;border-radius:4px;border:1.5px solid hsl(var(--muted-foreground)/.6);opacity:0;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;background:hsl(var(--background))}
  [data-row]:hover>.cx-rsel{opacity:.85}
  .cx-bulk{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);display:flex;align-items:center;gap:4px;padding:6px 8px 6px 14px;border-radius:10px;background:hsl(var(--popover));color:hsl(var(--popover-foreground));border:1px solid hsl(var(--border));box-shadow:0 8px 30px #0003;z-index:2147483000;font-size:13px}
  .cx-bulk b{margin-right:8px;color:#2383e2}.cx-bulk button{background:none;border:0;padding:6px 9px;border-radius:6px;cursor:pointer;font-size:13px;color:inherit}.cx-bulk button:hover{background:hsl(var(--accent))}.cx-bulk .danger{color:#e03e3e}
  .cx-pop{position:fixed;z-index:2147483000;background:hsl(var(--popover));border:1px solid hsl(var(--border));border-radius:8px;box-shadow:0 8px 30px #0003;padding:4px;width:240px}
  .cx-toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:#2f2f2f;color:#fff;padding:9px 16px;border-radius:8px;font-size:13.5px;z-index:2147483600;box-shadow:0 6px 20px #0004}
  body.cx-font-serif .bn-editor, body.cx-font-serif .cx-title-font, body.cx-font-serif .text-5xl.font-bold{font-family:Lyon-Text,Georgia,"Times New Roman",serif}
  body.cx-font-mono .bn-editor, body.cx-font-mono .cx-title-font, body.cx-font-mono .text-5xl.font-bold{font-family:"iawriter-mono",Consolas,"Courier New",monospace}
  body.cx-small .bn-editor{font-size:14px}
  body.cx-small .bn-editor .bn-block-content{font-size:14px}
  body.cx-locked .bn-side-menu{display:none!important}
  `;
  document.head.append(h('style', {}, css));

  const toast = (msg) => {
    const t = h('div', { class: 'cx-toast' }, msg); document.body.append(t);
    setTimeout(() => t.remove(), 2200);
  };
  const ago = (ts) => {
    if (!ts) return '';
    const s = Date.now() / 1000 - ts;
    if (s < 50) return 'just now';
    if (s < 3600) return Math.round(s / 60) + 'm ago';
    if (s < 86400) return Math.round(s / 3600) + 'h ago';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
  };
  const when = (ts) => new Date(ts * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });

  function modal(title, body, { wide = false, foot = null, onClose = null } = {}) {
    const close = () => { ov.remove(); document.removeEventListener('keydown', key, true); onClose && onClose(); };
    const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    const box = h('div', { class: 'cx-modal' + (wide ? ' wide' : '') },
      h('div', { class: 'cx-mh' }, title, h('span', { class: 'x', title: 'Close', onclick: close }, '×')),
      body, foot);
    const ov = h('div', { class: 'cx-overlay', onmousedown: (e) => { if (e.target === ov) close(); } }, box);
    document.body.append(ov); document.addEventListener('keydown', key, true);
    return { close, box };
  }

  // reload after something changed outside the editor (sidebar / database need to show it) — waits for pending saves
  const settle = (hash) => setTimeout(() => { if (hash) location.hash = hash; location.reload(); }, 1300);

  // ── page state ──────────────────────────────────────────────────────────────────────
  let META = null, curDoc = null;
  async function loadMeta() {
    const id = docId(); if (!id) { META = null; return; }
    try { META = await ext('meta', id); } catch { META = null; }
    applyAppearance(); renderHead(); renderComments();
  }

  function applyAppearance() {
    const m = META || {};
    document.body.classList.toggle('cx-font-serif', m.font === 'serif');
    document.body.classList.toggle('cx-font-mono', m.font === 'mono');
    document.body.classList.toggle('cx-small', !!m.small);
    document.body.classList.toggle('cx-locked', !!m.locked);
    const ed = bn();
    if (ed) { try { if (ed.isEditable === !!m.locked) ed.isEditable = !m.locked; } catch {} }
    $$('textarea, [contenteditable]').forEach(t => {            // the big title of the page
      if (t.closest('.bn-container')) return;
      if (t.tagName === 'TEXTAREA') { t.classList.add('cx-title-font'); t.readOnly = !!m.locked; }
    });
    renderToc(); renderLockBar();
  }

  function renderLockBar() {
    let bar = $('#cx-lockbar');
    if (!(META && META.locked)) { bar && bar.remove(); return; }
    const nav = navEl(); if (!nav) return;
    if (!bar) {
      bar = h('div', { id: 'cx-lockbar', class: 'cx-lockbar' }, '🔒 This page is locked — editing is off.',
        h('button', { onclick: () => setMeta({ locked: 0 }) }, 'Unlock'));
      nav.after(bar);
    }
  }

  async function setMeta(p) {
    const id = docId(); if (!id) return;
    try { META = await ext('meta_set', id, JSON.stringify(p)); } catch (e) { return toast(e.message); }
    applyAppearance(); renderHead();
    if ('fav' in p) loadSide();
  }

  // ── header ──────────────────────────────────────────────────────────────────────────
  const navEl = () => { const b = $$('nav button').find(x => x.innerText.trim() === 'Publish'); return b ? b.closest('nav') : null; };
  function renderHead() {
    const nav = navEl(); if (!nav) return;
    const pub = $$('button', nav).find(x => x.innerText.trim() === 'Publish'); if (!pub) return;
    let box = $('#cx-head');
    if (!box || box.parentElement !== pub.parentElement) {
      box && box.remove();
      box = h('div', { id: 'cx-head', style: { display: 'flex', alignItems: 'center', gap: '2px' } });
      pub.before(box);
    }
    const m = META || {};
    const sig = [docId(), m.updated && ago(m.updated), m.locked, m.fav, m.comments].join('|');
    if (box.__sig === sig) return; box.__sig = sig;
    box.replaceChildren(
      m.updated ? h('span', { class: 'cx-edited', title: m.updated ? 'Last edited ' + when(m.updated) : '' }, 'Edited ' + ago(m.updated)) : '',
      m.locked ? h('span', { class: 'cx-badge', title: 'Locked' }, '🔒 Locked') : '',
      h('button', { class: 'cx-btn', title: 'Comments', onclick: () => { showComments = !showComments; renderComments(true); } }, '💬' + (m.comments ? ' ' + m.comments : '')),
      h('button', { class: 'cx-btn', title: 'Copy link (Ctrl+Alt+L)', onclick: copyLink }, '🔗'),
      h('button', { class: 'cx-btn' + (m.fav ? ' on' : ''), title: m.fav ? 'Remove from Favorites' : 'Add to Favorites',
        onclick: () => setMeta({ fav: m.fav ? 0 : 1 }).then(() => toast(META && META.fav ? 'Added to Favorites' : 'Removed from Favorites')) }, m.fav ? '★' : '☆'));
  }

  // ── actions ─────────────────────────────────────────────────────────────────────────
  const pageLink = (id = docId()) => location.href.split('#')[0] + '#/documents/' + id;
  async function copyText(t, msg) {
    try { await navigator.clipboard.writeText(t); }
    catch { const a = h('textarea', { style: { position: 'fixed', opacity: 0 } }); a.value = t; document.body.append(a); a.select(); document.execCommand('copy'); a.remove(); }
    toast(msg);
  }
  const copyLink = () => copyText(pageLink(), 'Link copied');
  async function pageMarkdown() {
    const ed = bn(); if (!ed) return '';
    const doc = await core('get', docId()).catch(() => null);
    const md = await ed.blocksToMarkdownLossy(ed.document);
    return (doc && doc.title ? '# ' + doc.title + '\n\n' : '') + md;
  }
  const copyContents = async () => copyText(await pageMarkdown(), 'Page contents copied');

  async function duplicatePage() {
    const id = docId(); if (!id) return;
    try { const r = await ext('duplicate', id); toast('Duplicated'); settle('#/documents/' + r.id); } catch (e) { toast(e.message); }
  }

  async function moveTo() {
    const id = docId(); if (!id) return;
    let all = []; try { all = await ext('targets'); } catch (e) { return toast(e.message); }
    const doc = await core('get', id).catch(() => ({}));
    // pages inside this one can't be the new home
    const inside = new Set([id]); let grew = true;
    const parentOf = {}; all.forEach(p => parentOf[p.id] = null);
    const full = await core('list').catch(() => []);
    full.forEach(p => parentOf[p.id] = p.parentId);
    while (grew) { grew = false; for (const p of full) if (!inside.has(p.id) && inside.has(p.parentId)) { inside.add(p.id); grew = true; } }
    const input = h('input', { class: 'cx-search', placeholder: 'Move page to…' });
    const list = h('div', { class: 'cx-list' });
    const draw = () => {
      const q = input.value.toLowerCase().trim();
      const rows = [{ id: '', title: 'Top level', icon: '🏠', path: 'Not inside another page' }, ...all.filter(p => !inside.has(p.id))]
        .filter(p => !q || p.path.toLowerCase().includes(q) || p.title.toLowerCase().includes(q)).slice(0, 80);
      list.replaceChildren(...rows.map(p => h('div', { class: 'cx-item' + ((doc.parentId || '') === p.id ? ' kb' : ''), onclick: () => go(p) },
        h('span', { class: 'ic' }, p.icon || '📄'), p.title, h('span', { class: 'path' }, p.path))));
    };
    const go = async (p) => {
      try { await ext('move', id, p.id || ''); m.close(); toast('Moved to ' + p.title); settle('#/documents/' + id); } catch (e) { toast(e.message); }
    };
    input.addEventListener('input', draw);
    const m = modal('Move to', h('div', { class: 'cx-mb' }, input, list)); draw(); setTimeout(() => input.focus(), 30);
  }

  async function versionHistory() {
    const id = docId(); if (!id) return;
    try { await ext('snapshot', id, ''); } catch {}
    let vs = []; try { vs = await ext('versions', id); } catch (e) { return toast(e.message); }
    const left = h('div', { class: 'l' }), right = h('div', { class: 'r' }, vs.length ? 'Choose a version on the left.' : 'No earlier versions yet. Curio keeps one whenever the page changes (at most every 10 minutes).');
    let pick = null;
    const name = h('button', { class: 'cx-ghost', disabled: true, onclick: async () => {
      if (!pick) return; const inp = h('input', { class: 'cx-search', placeholder: 'e.g. Before the redesign' });
      const mm = modal('Name this version', h('div', { class: 'cx-mb' }, inp), { foot: h('div', { class: 'cx-mf' }, h('button', { class: 'cx-primary', onclick: async () => {
        try { await ext('version_label', pick, inp.value.trim()); mm.close(); m.close(); versionHistory(); } catch (e) { toast(e.message); } } }, 'Save')) });
      setTimeout(() => inp.focus(), 30);
    } }, 'Name this version');
    const restore = h('button', { class: 'cx-primary', disabled: true, onclick: async () => {
      if (!pick) return;
      try { await ext('restore', pick); m.close(); toast('Version restored'); settle(); } catch (e) { toast(e.message); }
    } }, 'Restore this version');
    const show = async (v, el) => {
      $$('.v', left).forEach(x => x.classList.remove('on')); el.classList.add('on'); pick = v.id; restore.disabled = false; name.disabled = false;
      right.textContent = 'Loading…';
      try {
        const full = await ext('version', v.id); const blocks = JSON.parse(full.content || '[]');
        const ed = bn(); let html = '';
        try { html = ed ? await ed.blocksToHTMLLossy(blocks) : ''; } catch { html = ''; }
        const view = h('div', { class: 'cx-prev' }); view.innerHTML = html.replace(/<script[\s\S]*?<\/script>/gi, '');
        right.replaceChildren(h('div', { style: { fontSize: '26px', fontWeight: 700, marginBottom: '14px' } }, (full.icon || '') + ' ' + (full.title || 'Untitled')),
          html ? view : '(this version has blocks Curio cannot preview here, but it can still be restored)');
      } catch (e) { right.textContent = e.message; }
    };
    vs.forEach(v => {
      const el = h('div', { class: 'v' }, v.label ? '🔖 ' + v.label : when(v.ts), h('small', {}, (v.label ? when(v.ts) + ' · ' : '') + (v.words || 0) + ' words'));
      el.onclick = () => show(v, el); left.append(el);
    });
    const m = modal('Version history', h('div', { class: 'cx-vh' }, left, right), { wide: true, foot: h('div', { class: 'cx-mf' }, name, restore) });
    if (vs[0]) show(vs[0], left.firstChild);
  }

  async function importFile() {
    const inp = h('input', { type: 'file', accept: '.md,.markdown,.txt,.html,.htm,.csv,.tsv', style: { display: 'none' } });
    document.body.append(inp);
    inp.onchange = async () => {
      const f = inp.files[0]; inp.remove(); if (!f) return;
      const text = await f.text();
      if (/\.(csv|tsv)$/i.test(f.name)) return importCSVAsPage({ name: f.name, text });
      const ed = bn(); if (!ed) return toast('Open a page first.');
      let blocks = [];
      try {
        if (/\.html?$/i.test(f.name)) blocks = await ed.tryParseHTMLToBlocks(text);
        else if (/\.txt$/i.test(f.name)) blocks = text.split(/\r?\n\r?\n/).map(p => ({ type: 'paragraph', content: p.replace(/\r?\n/g, ' ') }));
        else blocks = await ed.tryParseMarkdownToBlocks(text);
      } catch (e) { return toast('Could not read that file: ' + e.message); }
      const name = f.name.replace(/\.[^.]+$/, '');
      const body = h('div', { class: 'cx-mb' }, h('p', {}, `“${f.name}” has ${blocks.length} blocks. Where should it go?`));
      const asNew = async () => {
        try {
          const r = await core('create', docId(), name);
          await core('update', r.id, JSON.stringify({ content: JSON.stringify(blocks) }));
          m.close(); toast('Imported as a new page'); settle('#/documents/' + r.id);
        } catch (e) { toast(e.message); }
      };
      const here = () => {
        try { const last = ed.document[ed.document.length - 1]; ed.insertBlocks(blocks, last, 'after'); m.close(); toast('Imported into this page'); }
        catch (e) { toast(e.message); }
      };
      const m = modal('Import', body, { foot: h('div', { class: 'cx-mf' }, h('button', { class: 'cx-ghost', onclick: here }, 'Add to this page'),
        h('button', { class: 'cx-primary', onclick: asNew }, 'New page inside this one')) });
    };
    inp.click();
  }

  async function exportPage(kind) {
    const ed = bn(); if (!ed) return;
    const doc = await core('get', docId()).catch(() => ({}));
    const title = (doc && doc.title) || 'Untitled';
    let text = '', name = title;
    if (kind === 'md') { text = await pageMarkdown(); name += '.md'; }
    else if (kind === 'txt') { text = title + '\n\n' + ($('.bn-editor') ? $('.bn-editor').innerText : ''); name += '.txt'; }
    else {
      const body = await ed.blocksToHTMLLossy(ed.document);
      text = `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title><style>body{font-family:Segoe UI,system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6;color:#222}img{max-width:100%}pre{background:#f5f5f5;padding:12px;border-radius:6px;overflow:auto}blockquote{border-left:3px solid #ccc;margin:0;padding-left:14px;color:#555}</style></head><body><h1>${esc((doc.icon || '') + ' ' + title)}</h1>${body}</body></html>`;
      name += '.html';
    }
    try { const r = await ext('save_file', name, text); if (r.path) { toast('Saved'); } } catch (e) { toast(e.message); }
  }

  // the page, every page inside it and their databases → one zip of Markdown + CSV files
  async function exportTree() {
    const ed = bn(); const root = docId(); if (!ed || !root) return;
    toast('Preparing…');
    try {
      const all = await core('list'); const files = []; const used = new Set();
      const safe = (t) => { let b = (t || 'Untitled').replace(/[\\/:*?"<>|]+/g, '-').slice(0, 80).trim() || 'Untitled', n = b, k = 2; while (used.has(n)) n = b + ' ' + (k++); used.add(n); return n; };
      const walk = async (id, dir) => {
        const d = await core('get', id); if (!d) return;
        let blocks = []; try { blocks = JSON.parse(d.content || '[]'); } catch {}
        const name = safe(d.title);
        let md = '# ' + (d.icon ? d.icon + ' ' : '') + (d.title || 'Untitled') + '\n\n';
        try { md += await ed.blocksToMarkdownLossy(blocks); } catch {}
        files.push({ path: dir + name + '.md', text: md });
        const dbIds = []; const find = (bs) => (bs || []).forEach(b => { if (b && b.type === 'database' && b.props && b.props.dbId) dbIds.push(b.props.dbId); find(b && b.children); }); find(blocks);
        for (const dbid of [...new Set(dbIds)]) { try { const r = await rowsToCSV(dbid); files.push({ path: dir + name + '/' + safe(r.title) + '.csv', text: r.csv }); } catch {} }
        for (const c of all.filter(x => x.parentId === id && !x.isArchived)) await walk(c.id, dir + name + '/');
      };
      await walk(root, '');
      const r = await ext('save_zip', (files[0] ? files[0].path.replace(/\.md$/, '') : 'Pages') + '.zip', JSON.stringify(files));
      if (r.path) toast(`Saved ${files.length} files`);
    } catch (e) { toast(e.message); }
  }

  function undo() { const ed = bn(); try { ed && ed._tiptapEditor.commands.undo(); } catch {} }

  // ── ⋯ menu ──────────────────────────────────────────────────────────────────────────
  function sw(on) { return h('span', { class: 'cx-sw' + (on ? ' on' : '') }); }
  function appearanceItems(menu) {
    const m = META || {};
    const full = (() => { try { return localStorage.getItem('curio-full-' + docId()) === '1'; } catch { return false; } })();
    const fonts = h('div', { class: 'cx-fonts' }, ...[['default', 'Default', 'inherit'], ['serif', 'Serif', 'Georgia,serif'], ['mono', 'Mono', 'Consolas,monospace']]
      .map(([k, label, ff]) => h('div', { class: 'cx-font' + ((m.font || 'default') === k ? ' on' : ''), onclick: () => setMeta({ font: k }).then(() => refreshMenu(menu)) },
        h('b', { style: { fontFamily: ff } }, 'Ag'), h('span', {}, label))));
    const toggle = (ic, label, on, fn) => h('div', { class: 'cx-item', 'data-cx': label, onclick: fn }, h('span', { class: 'ic' }, ic), label, sw(on));
    return [h('div', { class: 'cx-foot', style: { paddingBottom: 0 } }, 'Font style'), fonts,
      toggle('A↓', 'Small text', !!m.small, () => setMeta({ small: m.small ? 0 : 1 }).then(() => refreshMenu(menu))),
      toggle('↔', 'Full width', full, () => {
        try { localStorage.setItem('curio-full-' + docId(), full ? '0' : '1'); } catch {}
        window.dispatchEvent(new Event('curio-full')); refreshMenu(menu);
      }),
      toggle('☰', 'Table of contents', !!m.toc, () => setMeta({ toc: m.toc ? 0 : 1 }).then(() => refreshMenu(menu)))];
  }

  function closeMenus() { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); }

  function ourItems(menu) {
    const m = META || {};
    const item = (ic, label, fn, kbd) => h('div', { class: 'cx-item', 'data-cx': label, onclick: (e) => { e.stopPropagation(); closeMenus(); setTimeout(fn, 60); } },
      h('span', { class: 'ic' }, ic), label, kbd ? h('span', { class: 'kbd' }, kbd) : null);
    let appOpen = menu.__cxApp || false;
    const appRow = h('div', { class: 'cx-item', 'data-cx': 'Appearance & layout', onclick: (e) => { e.stopPropagation(); menu.__cxApp = !appOpen; refreshMenu(menu); } },
      h('span', { class: 'ic' }, 'Aa'), 'Appearance & layout', h('span', { class: 'val' }, appOpen ? '▾' : '›'));
    let moreOpen = menu.__cxMore || false;
    const moreRow = h('div', { class: 'cx-item', 'data-cx': 'Import Export More', onclick: (e) => { e.stopPropagation(); menu.__cxMore = !moreOpen; refreshMenu(menu); } },
      h('span', { class: 'ic' }, '⋯'), 'Import & export', h('span', { class: 'val' }, moreOpen ? '▾' : '›'));
    return [
      item('🔗', 'Copy link', copyLink, 'Ctrl+Alt+L'),
      item('📋', 'Copy page contents', copyContents),
      item('⧉', 'Duplicate', duplicatePage),
      item('↪', 'Move to', moveTo),
      item('🕘', 'Version history', versionHistory),
      h('div', { class: 'cx-sep' }),
      appRow, ...(appOpen ? appearanceItems(menu) : []),
      h('div', { class: 'cx-item', 'data-cx': 'Lock page', onclick: (e) => { e.stopPropagation(); setMeta({ locked: m.locked ? 0 : 1 }).then(() => refreshMenu(menu)); } },
        h('span', { class: 'ic' }, '🔒'), 'Lock page', sw(!!m.locked)),
      item('⤺', 'Undo', undo, 'Ctrl+Z'),
      moreRow, ...(moreOpen ? [
        item('⬇', 'Import (Markdown, text, HTML, CSV)', importFile),
        item('⬆', 'Export as Markdown', () => exportPage('md')),
        item('⬆', 'Export as HTML', () => exportPage('html')),
        item('⬆', 'Export as plain text', () => exportPage('txt')),
        item('🗂', 'Export with sub-pages (zip)', exportTree)] : []),
    ];
  }

  function refreshMenu(menu) {
    const box = menu.querySelector('#cx-menu'); if (!box) return;
    const q = (menu.querySelector('.cx-search') || {}).value || '';
    box.replaceChildren(...ourItems(menu)); filterMenu(menu, q);
  }

  function filterMenu(menu, q) {
    q = q.toLowerCase().trim();
    $$('[role=menuitem], .cx-item', menu).forEach(el => {
      if ((menu.__cxHide || []).includes(el)) { el.style.display = 'none'; return; }
      const t = (el.getAttribute('data-cx') || el.innerText || '').toLowerCase();
      el.style.display = !q || t.includes(q) ? '' : 'none';
    });
  }

  function augmentMenu(menu) {
    if (menu.__cx) return;
    const items = $$('[role=menuitem]', menu);
    if (!items.some(i => i.innerText.trim() === 'Full width')) return;          // only the page ⋯ menu
    menu.__cx = true;
    menu.style.width = '270px'; menu.style.maxHeight = '80vh'; menu.style.overflowY = 'auto';
    const search = h('input', { class: 'cx-search', placeholder: 'Search actions…' });
    search.addEventListener('input', () => filterMenu(menu, search.value));
    search.addEventListener('keydown', e => e.stopPropagation());
    menu.prepend(search);
    // the original “Full width” lives in Appearance now
    items.filter(i => i.innerText.trim() === 'Full width').forEach(i => i.style.display = 'none');
    menu.__cxHide = items.filter(i => i.innerText.trim() === 'Full width');
    const box = h('div', { id: 'cx-menu' }, ...ourItems(menu));
    const first = items.find(i => i.innerText.trim() !== 'Full width') || items[0];
    first.before(box, h('div', { class: 'cx-sep' }));
    const m = META || {};
    menu.append(h('div', { class: 'cx-sep' }), h('div', { class: 'cx-foot' },
      m.words != null ? `${m.words} words` : '', m.updated ? h('br') : '', m.updated ? 'Last edited ' + when(m.updated) : '',
      m.created ? h('br') : '', m.created ? 'Created ' + when(m.created) : ''));
    setTimeout(() => search.focus(), 30);
  }

  // ── comments under the title ───────────────────────────────────────────────────────
  let showComments = false;
  async function renderComments(force) {
    const id = docId(); const title = $('.text-5xl.font-bold');
    let box = $('#cx-comments');
    const want = id && title && (showComments || (META && META.comments));
    if (!want) { box && box.remove(); return; }
    const host = title.parentElement;
    if (!box || box.parentElement !== host) { box && box.remove(); box = h('div', { id: 'cx-comments', class: 'cx-com' }); title.after(box); force = true; }
    if (!force && box.__doc === id) return; box.__doc = id;
    let list = []; try { list = await ext('comments', id); } catch {}
    const input = h('input', { class: 'cx-cin', placeholder: 'Add a comment…' });
    input.addEventListener('keydown', async (e) => {
      e.stopPropagation();
      if (e.key === 'Enter' && input.value.trim()) { await ext('comment_add', id, input.value); input.value = ''; await loadMeta(); renderComments(true); }
    });
    box.replaceChildren(h('div', { class: 'cx-ct' }, 'Comments'),
      ...list.map(c => h('div', { class: 'cx-c' + (c.done ? ' done' : '') },
        h('span', { class: 'cx-ck', title: c.done ? 'Open again' : 'Resolve', onclick: async () => { await ext('comment_set', c.id, !c.done); await loadMeta(); renderComments(true); } }, c.done ? '☑' : '☐'),
        h('div', { style: { flex: 1 } }, h('div', {}, c.text), h('small', {}, when(c.ts))),
        h('span', { class: 'cx-cx', title: 'Delete', onclick: async () => { await ext('comment_del', c.id); await loadMeta(); renderComments(true); } }, '×'))),
      input);
    if (showComments && !list.length) setTimeout(() => input.focus(), 30);
  }

  // ── table of contents ───────────────────────────────────────────────────────────────
  let tocTimer = null;
  function headings(blocks, out = []) {
    for (const b of blocks || []) {
      if (b.type === 'heading' || b.type === 'toggleHeading') {
        const t = (Array.isArray(b.content) ? b.content.map(x => x.text || (x.content || []).map(y => y.text).join('')).join('') : '') || '';
        if (t.trim()) out.push({ id: b.id, level: (b.props && b.props.level) || 1, text: t });
      }
      headings(b.children, out);
    }
    return out;
  }
  function renderToc() {
    let el = $('#cx-toc');
    if (!(META && META.toc) || !docId()) { el && el.remove(); clearInterval(tocTimer); tocTimer = null; return; }
    if (!el) { el = h('div', { id: 'cx-toc', class: 'cx-toc' }); document.body.append(el); }
    const draw = () => {
      const ed = bn(); const hs = ed ? headings(ed.document) : [];
      const sig = JSON.stringify(hs); if (el.__sig === sig) return; el.__sig = sig;
      el.replaceChildren(h('div', { class: 'tt' }, 'On this page'), ...(hs.length ? hs.map(x => h('a', { style: { paddingLeft: (8 + (x.level - 1) * 12) + 'px' },
        onclick: () => { const b = document.querySelector(`[data-id="${x.id}"]`); b && b.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }, x.text))
        : [h('div', { style: { padding: '2px 8px', color: 'hsl(var(--muted-foreground))' } }, 'Add headings to see them here.')]));
    };
    draw(); if (!tocTimer) tocTimer = setInterval(draw, 1500);
  }

  // ── sidebar: Favorites + Recents ────────────────────────────────────────────────────
  let SIDE = { favorites: [], recents: [] };
  async function loadSide() { try { SIDE = await ext('side'); } catch {} renderSide(); }
  function sideAnchor() {
    const aside = $('aside'); if (!aside) return null;
    return $$('[role=button]', aside).find(x => x.innerText.trim() === 'New page') || null;
  }
  function renderSide() {
    const a = sideAnchor(); if (!a) return;
    let box = $('#cx-side');
    if (!box || box.previousElementSibling !== a) { box && box.remove(); box = h('div', { id: 'cx-side', class: 'cx-side' }); a.after(box); }
    const cur = docId();
    const row = (p) => h('div', { class: 'p' + (p.id === cur ? ' on' : ''), title: p.title, onclick: () => { location.hash = '#/documents/' + p.id; } },
      h('span', {}, p.icon || '📄'), h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis' } }, p.title || 'Untitled'));
    const recents = SIDE.recents.filter(p => !SIDE.favorites.some(f => f.id === p.id)).slice(0, 5);
    box.replaceChildren(
      ...(SIDE.favorites.length ? [h('div', { class: 't' }, 'Favorites'), ...SIDE.favorites.map(row)] : []),
      ...(recents.length ? [h('div', { class: 't' }, 'Recents'), ...recents.map(row)] : []),
      (SIDE.favorites.length || recents.length) ? h('div', { class: 't', style: { paddingTop: '10px' } }, 'Pages') : '');
  }

  // ── database helpers ────────────────────────────────────────────────────────────────
  const DBS = () => window.__dbs || null;
  async function dbData(dbid) {                          // the live copy the tables show (falls back to Curio's file)
    const st = DBS() && DBS().store && DBS().store();
    const live = st && st.getState().dbs && st.getState().dbs[dbid];
    if (live && live.db) return live;
    if (st && st.getState().load) { try { await st.getState().load(dbid); const l = st.getState().dbs[dbid]; if (l && l.db) return l; } catch {} }
    return core('db_get', dbid);
  }
  async function addRow(dbid, props, title) {
    if (DBS() && DBS().addRow) return DBS().addRow(dbid, props, title || '');
    const row = await core('row_create', dbid, JSON.stringify({ title: title || '', props }));
    await linkBack(dbid, row.id, props); return row;
  }
  async function setRow(dbid, rowid, patch) {
    if (DBS() && DBS().setRow) return DBS().setRow(dbid, rowid, patch);
    return core('row_update', rowid, JSON.stringify(patch));
  }
  async function delRow(dbid, rowid) {
    if (DBS() && DBS().removeRow) return DBS().removeRow(dbid, rowid);
    return core('row_delete', rowid);
  }
  async function linkBack(dbid, rowid, props) {           // only needed without the live store
    const d = await core('db_get', dbid);
    for (const p of d.db.props) {
      const back = p.type === 'relation' && p.relation && p.relation.reverse; if (!back || !Array.isArray(props[p.id])) continue;
      const other = await core('db_get', p.relation.db).catch(() => null);
      for (const oid of props[p.id]) {
        const o = other && other.rows.find(r => r.id === oid); if (!o) continue;
        const cur = Array.isArray(o.props[back]) ? o.props[back] : [];
        if (!cur.includes(rowid)) await core('row_update', oid, JSON.stringify({ props: { [back]: [...cur, rowid] } }));
      }
    }
  }
  const EDITABLE = new Set(['relation', 'title', 'text', 'number', 'select', 'status', 'multi_select', 'multiselect', 'multi-select', 'date', 'checkbox', 'url', 'email', 'phone']);
  const isMulti = t => /^multi/.test(t);

  // one input for one property; writes into vals[p.id]
  function makeField(p, vals, init) {
    let inp; const t = p.type; const muted = (txt) => h('span', { style: { fontSize: '12px', opacity: .6 } }, txt);
    if (t === 'select' || t === 'status') {
      inp = h('select', {}, h('option', { value: '' }, '—'), ...(p.options || []).map(o => h('option', { value: o.id }, o.name)));
      inp.onchange = () => vals[p.id] = inp.value || null;
      if (init) { inp.value = init; vals[p.id] = init; }
    } else if (isMulti(t) || t === 'relation') {
      const chosen = new Set(Array.isArray(init) ? init : []);
      const chips = (items) => items.map(o => {
        const c = h('span', { class: 'cx-chip' + (chosen.has(o.id) ? ' on' : '') }, o.name);
        c.onclick = () => { chosen.has(o.id) ? chosen.delete(o.id) : chosen.add(o.id); c.classList.toggle('on'); vals[p.id] = [...chosen]; };
        return c;
      });
      inp = h('div', { class: 'cx-chips' });
      if (t === 'relation') {
        inp.append(muted('Loading…'));
        dbData((p.relation || {}).db).then(d => {
          const rows = (d && d.rows) || [];
          inp.replaceChildren(...(rows.length ? chips(rows.slice(0, 200).map(r => ({ id: r.id, name: (r.icon ? r.icon + ' ' : '') + (r.title || 'Untitled') }))) : [muted('Nothing to link yet.')]));
        }).catch(() => inp.replaceChildren('—'));
      } else inp.append(...((p.options || []).length ? chips(p.options) : [muted('No options yet — add them in the database.')]));
    } else if (t === 'checkbox') {
      inp = h('input', { type: 'checkbox', style: { width: 'auto' } }); inp.onchange = () => vals[p.id] = inp.checked;
      if (init != null) { inp.checked = !!init; vals[p.id] = !!init; }
    } else if (t === 'date') {
      inp = h('input', { type: 'date' }); inp.onchange = () => vals[p.id] = inp.value ? { start: inp.value } : null;
    } else if (t === 'number') {
      inp = h('input', { type: 'number', step: 'any' }); inp.oninput = () => vals[p.id] = inp.value === '' ? null : Number(inp.value);
    } else {
      inp = h(t === 'text' ? 'textarea' : 'input', { type: t === 'url' ? 'url' : t === 'email' ? 'email' : t === 'phone' ? 'tel' : 'text', rows: 2 });
      inp.oninput = () => vals[p.id] = inp.value;
    }
    return inp;
  }

  // ── database: quick form ────────────────────────────────────────────────────────────
  async function openForm(dbid) {
    let data; try { data = await dbData(dbid); } catch (e) { return toast(e.message); }
    const db = data.db; const props = (db.props || []).filter(p => EDITABLE.has(p.type)).sort((a, b) => (b.type === 'title') - (a.type === 'title'));
    const vals = {};
    const body = h('div', { class: 'cx-mb' }, h('p', { style: { marginTop: 0, color: 'hsl(var(--muted-foreground))', fontSize: '13px' } },
      'Fill in and press Add — a new row is made in “' + (db.title || 'this database') + '”.'),
      ...props.map(p => h('div', { class: 'cx-field' }, h('label', {}, p.name + (p.type === 'title' ? ' *' : '')), makeField(p, vals))));
    const add = async (again) => {
      const titleProp = props.find(p => p.type === 'title');
      const title = titleProp ? (vals[titleProp.id] || '').trim() : '';
      const rest = {}; for (const [k, v] of Object.entries(vals)) if (!titleProp || k !== titleProp.id) rest[k] = v;
      try {
        await addRow(dbid, rest, title);
        toast('Added to ' + (db.title || 'the database'));
        m.close(); if (again) openForm(dbid); else if (!DBS()) settle();
      } catch (e) { toast(e.message); }
    };
    const m = modal('📝 ' + (db.title || 'New row'), body, { foot: h('div', { class: 'cx-mf' },
      h('button', { class: 'cx-ghost', onclick: () => add(true) }, 'Add & next'), h('button', { class: 'cx-primary', onclick: () => add(false) }, 'Add')) });
    setTimeout(() => { const f = $('input,textarea', body); f && f.focus(); }, 40);
  }

  // ── CSV ─────────────────────────────────────────────────────────────────────────────
  function parseCSV(text) {
    text = text.replace(/^﻿/, ''); const rows = []; let row = [], cell = '', q = false;
    const sep = (text.split('\n')[0].match(/;/g) || []).length > (text.split('\n')[0].match(/,/g) || []).length ? ';' : (text.split('\n')[0].includes('\t') && !text.split('\n')[0].includes(',') ? '\t' : ',');
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (q) { if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += ch; }
      else if (ch === '"') q = true;
      else if (ch === sep) { row.push(cell); cell = ''; }
      else if (ch === '\n' || ch === '\r') { if (ch === '\r' && text[i + 1] === '\n') i++; row.push(cell); rows.push(row); row = []; cell = ''; }
      else cell += ch;
    }
    if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
    return rows.filter(r => r.some(c => c.trim() !== ''));
  }
  const csvCell = v => { v = v == null ? '' : String(v); return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const toCSV = (rows) => '﻿' + rows.map(r => r.map(csvCell).join(',')).join('\r\n');
  const optName = (p, id) => ((p.options || []).find(o => o.id === id) || {}).name || '';

  async function rowsToCSV(dbid, onlyIds) {
    const d = await dbData(dbid); const props = d.db.props || [];
    const relTitles = {};
    for (const p of props) if (p.type === 'relation' && p.relation) {
      try { const o = await dbData(p.relation.db); relTitles[p.id] = Object.fromEntries((o.rows || []).map(r => [r.id, r.title || 'Untitled'])); } catch {}
    }
    const shown = props.filter(p => !['rollup', 'formula'].includes(p.type));
    const out = [shown.map(p => p.name)];
    for (const r of d.rows) {
      if (onlyIds && !onlyIds.has(r.id)) continue;
      out.push(shown.map(p => {
        const v = p.type === 'title' ? r.title : r.props[p.id];
        if (v == null) return '';
        if (p.type === 'select' || p.type === 'status') return optName(p, v);
        if (isMulti(p.type)) return (Array.isArray(v) ? v : []).map(x => optName(p, x)).filter(Boolean).join(', ');
        if (p.type === 'relation') return (Array.isArray(v) ? v : []).map(x => (relTitles[p.id] || {})[x]).filter(Boolean).join(', ');
        if (p.type === 'date') return v.start ? v.start + (v.end ? ' → ' + v.end : '') : '';
        if (p.type === 'checkbox') return v ? 'Yes' : 'No';
        if (typeof v === 'object') return JSON.stringify(v);
        return v;
      }));
    }
    return { csv: toCSV(out), title: d.db.title || 'Database', count: out.length - 1 };
  }
  // what the table shows right now (formulas and rollups included)
  function viewToCSV(dbEl) {
    const head = $$('[data-col]', dbEl).length ? null : null; void head;
    const rows = $$('[data-row]', dbEl);
    if (!rows.length) return null;
    const cols = [...new Set($$('[data-col]', rows[0]).map(c => c.getAttribute('data-col')))];
    const names = cols.map(c => { const hc = $$(`[data-col="${c}"]`, dbEl).find(x => !x.closest('[data-row]')); return hc ? hc.innerText.trim() : c.split('-').pop(); });
    const data = rows.map(r => cols.map(c => { const cell = r.querySelector(`[data-col="${c}"]`); return cell ? cell.innerText.replace(/\bOPEN\b/g, '').replace(/\s*\n\s*/g, ', ').trim() : ''; }));
    return toCSV([names, ...data]);
  }

  async function exportCSV(dbid, dbEl, onlyIds) {
    try {
      let csv, title = 'Database';
      if (!onlyIds && dbEl && $$('[data-row]', dbEl).length) { csv = viewToCSV(dbEl); const d = await dbData(dbid); title = d.db.title || title; }
      else { const r = await rowsToCSV(dbid, onlyIds); csv = r.csv; title = r.title; }
      const r = await ext('save_file', title + '.csv', csv); if (r.path) toast('Saved ' + title + '.csv');
    } catch (e) { toast(e.message); }
  }

  const DATE_RE = /^(\d{4})-(\d{1,2})-(\d{1,2})/;
  function toDate(s) {
    s = String(s).split('→')[0].trim(); if (!s) return null;
    let m = s.match(DATE_RE); if (m) return { start: `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}` };
    m = s.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2,4})/);                // 13/11/2026 (day first, as in Pakistan)
    if (m) { const y = m[3].length === 2 ? '20' + m[3] : m[3]; let d = +m[1], mo = +m[2]; if (mo > 12) [d, mo] = [mo, d]; return { start: `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}` }; }
    const t = new Date(s); return isNaN(t) ? null : { start: t.toISOString().slice(0, 10) };
  }
  const toNum = s => { const n = Number(String(s).replace(/[^\d.\-]/g, '')); return String(s).trim() === '' || isNaN(n) ? null : n; };
  const COLORS = ['gray', 'brown', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'red'];

  async function importCSVInto(dbid, text) {
    const rows = parseCSV(text); if (rows.length < 2) return toast('That file has no rows.');
    const st = DBS();
    let d = await dbData(dbid); let props = d.db.props.slice();
    const head = rows[0].map(x => x.trim());
    const map = head.map((name, i) => {
      let p = props.find(x => x.name.toLowerCase() === name.toLowerCase());
      if (!p && i === 0) p = props.find(x => x.type === 'title');
      return p || null;
    });
    // columns the database doesn't have yet → new text properties
    for (let i = 0; i < head.length; i++) if (!map[i] && head[i]) {
      const np = { id: Math.random().toString(36).slice(2, 10), name: head[i], type: 'text' };
      if (st && st.addProp) st.addProp(dbid, np); else { props.push(np); await core('db_update', dbid, JSON.stringify({ props })); }
      map[i] = np;
    }
    d = await dbData(dbid); props = d.db.props;
    const fresh = (p) => props.find(x => x.id === p.id) || p;
    const relRows = {};
    for (const p of props) if (p.type === 'relation' && p.relation) { try { relRows[p.id] = (await dbData(p.relation.db)).rows || []; } catch { relRows[p.id] = []; } }
    let added = 0;
    for (const r of rows.slice(1)) {
      let title = ''; const pv = {};
      for (let i = 0; i < head.length; i++) {
        const p = map[i] && fresh(map[i]); if (!p) continue; const raw = (r[i] || '').trim(); if (raw === '') continue;
        if (p.type === 'title') { title = raw; continue; }
        if (p.type === 'number') pv[p.id] = toNum(raw);
        else if (p.type === 'date') pv[p.id] = toDate(raw);
        else if (p.type === 'checkbox') pv[p.id] = /^(yes|true|1|✓|✔|x|done|checked)$/i.test(raw);
        else if (p.type === 'select' || p.type === 'status' || isMulti(p.type)) {
          const names = isMulti(p.type) ? raw.split(/\s*,\s*/) : [raw]; const ids = [];
          for (const n of names) {
            let o = (p.options || []).find(x => x.name.toLowerCase() === n.toLowerCase());
            if (!o) {                                                   // a new option, like Notion does on import
              o = { id: Math.random().toString(36).slice(2, 10), name: n, color: COLORS[(p.options || []).length % COLORS.length] };
              p.options = [...(p.options || []), o];
              if (st && st.updateProp) st.updateProp(dbid, p.id, { options: p.options });
              else await core('db_update', dbid, JSON.stringify({ props }));
            }
            ids.push(o.id);
          }
          pv[p.id] = isMulti(p.type) ? ids : ids[0];
        } else if (p.type === 'relation') {
          pv[p.id] = raw.split(/\s*,\s*/).map(n => (relRows[p.id].find(x => (x.title || '').toLowerCase() === n.toLowerCase()) || {}).id).filter(Boolean);
        } else if (['rollup', 'formula', 'created_time', 'last_edited_time', 'files'].includes(p.type)) continue;
        else pv[p.id] = raw;
      }
      await addRow(dbid, pv, title); added++;
    }
    toast(`Imported ${added} row${added === 1 ? '' : 's'}`);
    if (!st) settle();
  }
  function pickFile(accept) {
    return new Promise(ok => {
      const inp = h('input', { type: 'file', accept, style: { display: 'none' } }); document.body.append(inp);
      inp.onchange = async () => { const f = inp.files[0]; inp.remove(); ok(f ? { name: f.name, text: await f.text() } : null); };
      inp.click();
    });
  }
  // a whole CSV as a new page with a database on it (⋯ › Import)
  async function importCSVAsPage(f) {
    const rows = parseCSV(f.text); if (!rows.length) return toast('That file is empty.');
    const head = rows[0].map((x, i) => x.trim() || 'Column ' + (i + 1)); const body = rows.slice(1);
    const kinds = head.map((_, i) => {
      const vals = body.map(r => (r[i] || '').trim()).filter(Boolean);
      if (i === 0 || !vals.length) return 'text';
      if (vals.every(v => toNum(v) !== null && /^[\s\-+]*[\d,.\s]*(pkr|rs\.?|\$|€|%)?\s*$/i.test(v.replace(/^(pkr|rs\.?)\s*/i, '')))) return 'number';
      if (vals.every(v => DATE_RE.test(v) || /^\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}/.test(v))) return 'date';
      if (vals.every(v => /^(yes|no|true|false|✓|✔|x|)$/i.test(v))) return 'checkbox';
      const uniq = new Set(vals); if (uniq.size <= Math.max(3, vals.length / 3) && uniq.size <= 20 && vals.length > 3) return 'select';
      return 'text';
    });
    const props = head.map((n, i) => {
      const p = { id: i === 0 ? 'title' : Math.random().toString(36).slice(2, 10), name: n, type: i === 0 ? 'title' : kinds[i] };
      if (p.type === 'number') p.number = { format: 'comma' };
      if (p.type === 'select') p.options = [...new Set(body.map(r => (r[i] || '').trim()).filter(Boolean))].map((nm, k) => ({ id: Math.random().toString(36).slice(2, 10), name: nm, color: COLORS[k % COLORS.length] }));
      return p;
    });
    const name = f.name.replace(/\.[^.]+$/, '');
    try {
      const pg = await core('create', docId(), name);
      const db = await core('db_create', pg.id, JSON.stringify({ title: name, props, views: [{ id: Math.random().toString(36).slice(2, 10), name: 'Table', type: 'table' }] }));
      let k = 0;
      for (const r of body) {
        const pv = {};
        props.forEach((p, i) => {
          const raw = (r[i] || '').trim(); if (!raw || i === 0) return;
          pv[p.id] = p.type === 'number' ? toNum(raw) : p.type === 'date' ? toDate(raw) : p.type === 'checkbox' ? /^(yes|true|✓|✔|x)$/i.test(raw)
            : p.type === 'select' ? (p.options.find(o => o.name === raw) || {}).id : raw;
        });
        await core('row_create', db.id, JSON.stringify({ title: (r[0] || '').trim(), props: pv, sort: Date.now() / 1000 + (k++) }));
      }
      await core('update', pg.id, JSON.stringify({ content: JSON.stringify([{ type: 'database', props: { dbId: db.id } }, { type: 'paragraph' }]) }));
      toast(`Imported ${body.length} rows`); settle('#/documents/' + pg.id);
    } catch (e) { toast(e.message); }
  }

  // ── database toolbar: Form · CSV ────────────────────────────────────────────────────
  function csvMenu(btn, dbid, dbEl) {
    const old = $('#cx-pop'); if (old) { old.remove(); return; }
    const r = btn.getBoundingClientRect();
    const pop = h('div', { id: 'cx-pop', class: 'cx-pop', 'data-curio-pop': '', style: { left: Math.min(r.left, innerWidth - 250) + 'px', top: (r.bottom + 4) + 'px' } },
      h('div', { class: 'cx-item', onclick: () => { pop.remove(); exportCSV(dbid, dbEl); } }, h('span', { class: 'ic' }, '⬆'), 'Export this view (CSV)'),
      h('div', { class: 'cx-item', onclick: async () => { pop.remove(); const r2 = await rowsToCSV(dbid).catch(e => toast(e.message)); if (r2) { const s2 = await ext('save_file', r2.title + ' (all rows).csv', r2.csv); if (s2.path) toast('Saved'); } } },
        h('span', { class: 'ic' }, '⬆'), 'Export all rows (CSV)'),
      h('div', { class: 'cx-item', onclick: async () => { pop.remove(); const f = await pickFile('.csv,.tsv,.txt'); if (f) importCSVInto(dbid, f.text); } },
        h('span', { class: 'ic' }, '⬇'), 'Import rows from CSV'));
    document.body.append(pop);
    setTimeout(() => document.addEventListener('mousedown', function off(e) { if (!pop.contains(e.target)) { pop.remove(); document.removeEventListener('mousedown', off, true); } }, true), 0);
  }
  // Notion has no CSV / Form buttons on a database's toolbar — CSV lives in the view menu (▾ next to the view name)
  // as “Merge with CSV” / “Export view as CSV”, next to “Copy link to view” and “Manage in Calendar”.
  function augmentDatabases() {
    $$('.cx-formbtn').forEach(b => b.remove());
    augmentRows();
    focusLinkedDb();
  }
  const dbEl = (dbid) => $(`[data-content-type="database"][data-db-id="${dbid}"]`);
  // a view link: <Pages>#/documents/<page>?db=<database>&v=<view> — opens the page and brings that database into view
  const viewLinkOf = (dbid, vid) => {
    const pg = docId();
    return location.href.split('#')[0] + '#/documents/' + pg + '?db=' + dbid + (vid ? '&v=' + vid : '');
  };
  let lastFocus = '';
  function focusLinkedDb() {
    const m = location.hash.match(/[?&]db=([\w-]+)/); if (!m || lastFocus === location.hash) return;
    const el = dbEl(m[1]); if (!el) return;
    lastFocus = location.hash; el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    el.animate([{ boxShadow: '0 0 0 3px hsl(var(--ring) / .45)' }, { boxShadow: '0 0 0 0 transparent' }], { duration: 1400, easing: 'ease-out' });
  }
  window.__cx = {
    viewLink: (dbid, vid) => copyText(viewLinkOf(dbid, vid), 'Link to view copied — paste it in Calendar › + to add this database'),
    csvImport: async (dbid) => { const f = await pickFile('.csv,.tsv,.txt'); if (f) importCSVInto(dbid, f.text); },
    csvExport: (dbid) => exportCSV(dbid, dbEl(dbid)),
    calendar: async (dbid) => {
      try {
        const r = await ext('calendar_add', dbid);
        if (r.prop && DBS()) { try { DBS().addProp(dbid, r.prop); } catch (e) { /* shows after a refresh */ } }
        toast(r.date_added ? 'Added a Date property and opened it in Calendar' : 'Showing this database in Calendar');
      } catch (e) { toast(e.message); }
    },
  };

  // ── selecting rows (click, Shift+click range, drag, Ctrl+A) and changing them together ─
  const SEL = { db: null, ids: new Set(), last: null, dragging: false, dragOn: true };
  const rowEls = (dbid) => $$(`[data-row][data-db="${dbid}"]`);
  function augmentRows() {
    $$('[data-row]').forEach(r => {
      if (r.querySelector(':scope > .cx-rsel')) return;
      const box = h('span', { class: 'cx-rsel', title: 'Select (Shift+click: a range · drag: many)' });
      box.addEventListener('mousedown', (e) => {
        e.preventDefault(); e.stopPropagation();
        const db = r.getAttribute('data-db'), id = r.getAttribute('data-row');
        if (SEL.db !== db) { SEL.ids.clear(); SEL.db = db; }
        if (e.shiftKey && SEL.last) {
          const all = rowEls(db).map(x => x.getAttribute('data-row'));
          const a = all.indexOf(SEL.last), b = all.indexOf(id);
          if (a >= 0 && b >= 0) all.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(x => SEL.ids.add(x));
        } else {
          SEL.dragOn = !SEL.ids.has(id); SEL.dragOn ? SEL.ids.add(id) : SEL.ids.delete(id);
          SEL.dragging = true;
        }
        SEL.last = id; drawSel();
      });
      r.addEventListener('mouseenter', () => {
        if (!SEL.dragging || r.getAttribute('data-db') !== SEL.db) return;
        const id = r.getAttribute('data-row'); SEL.dragOn ? SEL.ids.add(id) : SEL.ids.delete(id); SEL.last = id; drawSel();
      });
      r.append(box);
    });
    drawSel(true);
  }
  document.addEventListener('mouseup', () => { SEL.dragging = false; });
  // Shift+click a checkbox in a table: every row between the last one you ticked and this one gets the same tick
  let lastTick = null;
  document.addEventListener('click', (e) => {
    const cb = e.target.closest && e.target.closest('[data-row] [data-col]');
    if (!cb) return;
    const box = cb.querySelector('input[type=checkbox], span[class*="h-4 w-4"][class*="rounded-[3px]"]');
    if (!box || cb.innerText.trim()) return;                                  // only checkbox cells
    const row = cb.closest('[data-row]'); const db = row.getAttribute('data-db'), rid = row.getAttribute('data-row');
    const col = cb.getAttribute('data-col'); const pid = col.slice(col.indexOf('-') + 1);
    const wasOn = box.tagName === 'INPUT' ? box.checked : /bg-\[#2383e2\]/.test(box.className);  // before this click
    if (e.shiftKey && lastTick && lastTick.db === db && lastTick.col === col) {
      const all = rowEls(db).map(x => x.getAttribute('data-row'));
      const a = all.indexOf(lastTick.rid), b = all.indexOf(rid);
      if (a >= 0 && b >= 0) {
        const want = !wasOn;
        all.slice(Math.min(a, b), Math.max(a, b) + 1).filter(x => x !== rid).forEach(x => setRow(db, x, { props: { [pid]: want } }));
        toast(`${Math.abs(a - b) + 1} rows ${want ? 'ticked' : 'unticked'}`);
      }
    }
    lastTick = { db, col, rid };
  }, true);
  document.addEventListener('keydown', (e) => {
    if (!SEL.ids.size) return;
    if (e.key === 'Escape' && !$('.cx-overlay')) { SEL.ids.clear(); drawSel(); }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A') && !e.target.closest('.bn-editor, input, textarea, [contenteditable="true"]')) {
      e.preventDefault(); rowEls(SEL.db).forEach(x => SEL.ids.add(x.getAttribute('data-row'))); drawSel();
    }
    if ((e.key === 'Delete') && !e.target.closest('.bn-editor, input, textarea, [contenteditable="true"]')) { e.preventDefault(); bulkDelete(); }
  }, true);
  function drawSel(quiet) {
    // forget rows that are gone
    const alive = new Set($$('[data-row]').map(x => x.getAttribute('data-row')));
    for (const id of [...SEL.ids]) if (!alive.has(id)) SEL.ids.delete(id);
    let st = $('#cx-selcss'); if (!st) { st = h('style', { id: 'cx-selcss' }); document.head.append(st); }
    const css2 = [...SEL.ids].map(id => `[data-row="${id}"]{box-shadow:inset 0 0 0 9999px rgba(35,131,226,.14)!important}[data-row="${id}"]>.cx-rsel{opacity:1;background:#2383e2;border-color:#2383e2}[data-row="${id}"]>.cx-rsel:after{content:'✓'}`).join('\n');
    if (st.textContent !== css2) st.textContent = css2;
    let bar = $('#cx-bulk');
    if (!SEL.ids.size) { bar && bar.remove(); return; }
    const n = SEL.ids.size, total = rowEls(SEL.db).length;
    const sig = n + '/' + total; if (bar && bar.__sig === sig) return;
    if (!bar) { bar = h('div', { id: 'cx-bulk', class: 'cx-bulk' }); document.body.append(bar); }
    bar.__sig = sig;
    bar.replaceChildren(h('b', {}, `${n} selected`),
      n < total ? h('button', { onclick: () => { rowEls(SEL.db).forEach(x => SEL.ids.add(x.getAttribute('data-row'))); drawSel(); } }, `Select all ${total}`) : '',
      h('button', { onclick: bulkEdit }, '✎ Edit property'),
      h('button', { onclick: bulkDuplicate }, '⧉ Duplicate'),
      h('button', { onclick: () => exportCSV(SEL.db, null, new Set(SEL.ids)) }, '⬆ CSV'),
      h('button', { class: 'danger', onclick: bulkDelete }, '🗑 Delete'),
      h('button', { title: 'Clear (Esc)', onclick: () => { SEL.ids.clear(); drawSel(); } }, '✕'));
    void quiet;
  }
  async function bulkEdit() {
    const dbid = SEL.db, ids = [...SEL.ids]; const d = await dbData(dbid);
    const props = d.db.props.filter(p => EDITABLE.has(p.type));
    const vals = {}; const sel = h('select', {}, ...props.map(p => h('option', { value: p.id }, p.name)));
    const holder = h('div');
    const draw = () => { for (const k in vals) delete vals[k]; const p = props.find(x => x.id === sel.value); holder.replaceChildren(makeField(p, vals, p.type === 'checkbox' ? true : undefined)); };
    sel.onchange = draw;
    const body = h('div', { class: 'cx-mb' }, h('p', { style: { marginTop: 0, fontSize: '13px', color: 'hsl(var(--muted-foreground))' } }, `Set one property on ${ids.length} row${ids.length === 1 ? '' : 's'}.`),
      h('div', { class: 'cx-field' }, h('label', {}, 'Property'), sel), h('div', { class: 'cx-field' }, h('label', {}, 'Value'), holder));
    draw();
    const m = modal('Edit ' + ids.length + ' rows', body, { foot: h('div', { class: 'cx-mf' }, h('button', { class: 'cx-primary', onclick: async () => {
      const p = props.find(x => x.id === sel.value); const v = p.id in vals ? vals[p.id] : (p.type === 'checkbox' ? false : null);
      try {
        for (const id of ids) await setRow(dbid, id, p.type === 'title' ? { title: v || '' } : { props: { [p.id]: v } });
        m.close(); toast(`Updated ${ids.length} rows`); if (!DBS()) settle();
      } catch (e) { toast(e.message); }
    } }, 'Apply')) });
  }
  async function bulkDuplicate() {
    const dbid = SEL.db; const d = await dbData(dbid);
    const rows = d.rows.filter(r => SEL.ids.has(r.id));
    try { for (const r of rows) await addRow(dbid, JSON.parse(JSON.stringify(r.props || {})), r.title || ''); toast(`Duplicated ${rows.length} rows`); SEL.ids.clear(); drawSel(); if (!DBS()) settle(); }
    catch (e) { toast(e.message); }
  }
  function bulkDelete() {
    const dbid = SEL.db, ids = [...SEL.ids]; if (!ids.length) return;
    const m = modal('Delete ' + ids.length + ' row' + (ids.length === 1 ? '' : 's') + '?', h('div', { class: 'cx-mb' }, 'Each row is a page — its text goes too. This cannot be undone.'),
      { foot: h('div', { class: 'cx-mf' }, h('button', { class: 'cx-ghost', onclick: () => m.close() }, 'Cancel'),
        h('button', { class: 'cx-primary', style: { background: '#e03e3e' }, onclick: async () => {
          try { for (const id of ids) await delRow(dbid, id); m.close(); SEL.ids.clear(); drawSel(); toast(`Deleted ${ids.length} rows`); if (!DBS()) settle(); }
          catch (e) { toast(e.message); }
        } }, 'Delete')) });
  }

  // ── “/turn…” commands (Notion: /turnbullet, /turncallout …) ─────────────────────────
  const TURN = [['text', 'Text', { type: 'paragraph' }], ['h1', 'Heading 1', { type: 'heading', props: { level: 1 } }], ['h2', 'Heading 2', { type: 'heading', props: { level: 2 } }],
    ['h3', 'Heading 3', { type: 'heading', props: { level: 3 } }], ['bullet', 'Bulleted list', { type: 'bulletListItem' }], ['number', 'Numbered list', { type: 'numberedListItem' }],
    ['todo', 'To-do list', { type: 'checkListItem' }], ['toggle', 'Toggle list', { type: 'toggleListItem' }], ['quote', 'Quote', { type: 'quote' }],
    ['callout', 'Callout', { type: 'callout' }], ['code', 'Code', { type: 'codeBlock' }]];
  window.__cxSlash = (ed) => {
    let txt = '';
    try { const b = ed.getTextCursorPosition().block; txt = (Array.isArray(b.content) ? b.content.map(x => x.text || '').join('') : ''); } catch {}
    if (!/\/turn/i.test(txt)) return [];
    const cur = () => ed.getTextCursorPosition().block;
    return [...TURN.map(([k, label, spec]) => ({ title: 'Turn into ' + label, group: 'Turn into', aliases: ['turn' + k, 'turn ' + k, 'turn' + label.toLowerCase().replace(/\s+/g, '')],
      subtext: '/turn' + k, onItemClick: () => { try { ed.updateBlock(cur(), spec); } catch (e) { toast(e.message); } } })),
      { title: 'Turn into page', group: 'Turn into', aliases: ['turnpage', 'turn page'], subtext: '/turnpage — this block and what is inside it become a page',
        onItemClick: async () => {
          const b = cur(); const title = (Array.isArray(b.content) ? b.content.map(x => x.text || '').join('') : '') || 'Untitled';
          try {
            const pg = await core('create', docId(), title);
            await core('update', pg.id, JSON.stringify({ content: JSON.stringify((b.children || []).length ? b.children : [{ type: 'paragraph' }]) }));
            ed.updateBlock(b, { type: 'pageLink', props: { docId: pg.id }, content: undefined, children: [] });
            const ps = DBS() && DBS().pages && DBS().pages(); if (ps && ps.getState().refresh) ps.getState().refresh();
          } catch (e) { toast(e.message); }
        } }];
  };

  // ── 10.43: Docs (was “Pages”) — a small path on top, no “…'s Pages” switcher; embed=1 = a page opened inside the Tracker ──
  const EMBED = /[?&]embed=1\b/.test(location.search);
  (function () {
    const st = document.createElement('style');
    st.textContent = '.cx-crumb{display:flex;align-items:center;gap:4px;font-size:12.5px;color:hsl(var(--muted-foreground));white-space:nowrap;overflow:hidden;min-width:0;flex:0 1 auto;margin-right:6px}' +
      '.cx-crumb a{color:inherit;text-decoration:none;padding:2px 4px;border-radius:4px;overflow:hidden;text-overflow:ellipsis;max-width:180px}.cx-crumb a:hover{background:hsl(var(--accent));color:hsl(var(--foreground))}' +
      '.cx-crumb .sep{opacity:.5;flex:none} .cx-crumb > a:first-child{flex:none;overflow:visible}' +
      (EMBED ? 'aside{display:none!important} aside + div{left:0!important;width:100%!important} .cx-side{display:none!important}' : '');
    document.head.append(st);
  })();
  function hideSwitcher() {
    const aside = $('aside'); if (!aside) return;
    for (const b of $$('[role=button]', aside)) {
      if (b.__cxHid) continue;
      if (/'s Pages\s*$/.test((b.innerText || '').trim())) { b.style.display = 'none'; b.__cxHid = true; }
    }
  }
  let CRUMB = { id: null, list: [] };
  async function loadCrumb(id) {
    const out = []; let cur = await core('get', id).catch(() => null); let n = 0;
    while (cur && n++ < 8) {
      let pid = cur.parentId;
      if (!pid && cur.db) {
        const d = await core('db_get', cur.db).catch(() => null);
        if (d && d.db) { out.unshift({ title: d.db.title || 'Table', id: d.db.parent, db: true }); pid = d.db.parent; }
      }
      if (!pid) break;
      const p = await core('get', pid).catch(() => null); if (!p) break;
      if (!out.length || out[0].db || out[0].id !== p.id) out.unshift({ title: p.title || 'Untitled', id: p.id, icon: p.icon });
      cur = p;
    }
    CRUMB = { id, list: out }; renderCrumb();
  }
  function renderCrumb() {
    let nav = navEl(), pad = false;
    if (!nav) {                                                   // a database row has no top bar: put the path in the empty strip on top
      const a = $('aside'), strip = a && a.nextElementSibling;
      if (!strip || [...strip.children].some(x => x.id !== 'cx-crumb')) return;
      nav = strip; pad = true;
    }
    let el = $('#cx-crumb');
    if (!el || el.parentElement !== nav) { el && el.remove(); el = h('div', { id: 'cx-crumb', class: 'cx-crumb' }); nav.prepend(el); }
    el.style.padding = pad ? '12px 16px' : '';
    const sig = CRUMB.id + '|' + CRUMB.list.map(x => x.title).join('/');
    if (el.__sig === sig) return; el.__sig = sig;
    const kids = [h('a', { href: EMBED ? 'javascript:void 0' : '#/documents' }, 'Docs')];
    for (const x of CRUMB.list) kids.push(h('span', { class: 'sep' }, '/'), x.id ? h('a', { href: '#/documents/' + x.id, title: x.title }, (x.icon ? x.icon + ' ' : '') + x.title) : h('span', {}, x.title));
    kids.push(h('span', { class: 'sep' }, '/'));
    el.replaceChildren(...kids);
  }

  // ── wiring ──────────────────────────────────────────────────────────────────────────
  let lastDoc = null, lastEditor = null, pending = false;
  function tick() {
    pending = false;
    const id = docId();
    if (id !== lastDoc) {
      lastDoc = id; META = null; showComments = false;
      if (id) { ext('visit', id).then(loadSide).catch(() => {}); loadMeta(); loadCrumb(id).catch(() => {}); } else { renderToc(); renderLockBar(); renderHead(); }
    }
    hideSwitcher(); if (id) renderCrumb();
    if (bn() !== lastEditor) { lastEditor = bn(); applyAppearance(); }
    renderHead(); renderComments();
    if (!$('#cx-side') || $('#cx-side').previousElementSibling !== sideAnchor()) renderSide();
    $$('[role=menu]').forEach(augmentMenu);
    augmentDatabases();
  }
  const obs = new MutationObserver(() => { if (!pending) { pending = true; requestAnimationFrame(tick); } });

  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.altKey && (e.key === 'l' || e.key === 'L')) { e.preventDefault(); copyLink(); }
  }, true);
  setInterval(() => { if (docId()) loadMeta(); }, 30000);           // keeps “Edited …” fresh

  function start() {
    const ch = window.__chan;
    if (!ch || !ch.objects) return setTimeout(start, 120);
    EXT = ch.objects.curioext || null; CORE = ch.objects.curio || null;
    if (!EXT) { console.warn('Curio extras: pages_ext is not available'); return; }
    obs.observe(document.body, { childList: true, subtree: true });
    window.addEventListener('hashchange', tick);
    loadSide(); tick();
    window.__curioExt = { ext, core, openForm, versionHistory, moveTo, duplicatePage, importFile, exportPage };
  }
  start();
})();
