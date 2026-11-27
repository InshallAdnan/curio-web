/* Curio Web — stands in for Qt's web channel: the same `curio` and `curioext` objects the desktop gives Pages,
   but every call goes to the server (POST /api/pages/rpc) and comes back as the same JSON text. */
(function () {
  'use strict';
  function signIn() { (window.top || window).location.href = '/api/auth/login?next=' + encodeURIComponent((window.top || window).location.pathname + (window.top || window).location.hash); }
  function post(o, m, a) {
    return fetch('/api/pages/rpc', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify({ o: o, m: m, a: a }) })
      .then(function (r) { if (r.status === 401) { signIn(); return '{"error":"Signing you in…"}'; } return r.text(); })
      .catch(function () { return JSON.stringify({ error: 'No internet connection — your last change was not saved. Try again.' }); });
  }
  function download(name, blob) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function b64blob(b64, type) { var s = atob(b64), u = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); return new Blob([u], { type: type }); }
  function make(o) {
    var signals = {};
    function sig(n) {
      return signals[n] || (signals[n] = { cbs: [], connect: function (f) { this.cbs.push(f); }, disconnect: function (f) { this.cbs = this.cbs.filter(function (x) { return x !== f; }); },
        emit: function () { var a = arguments; this.cbs.slice().forEach(function (f) { f.apply(null, a); }); } });
    }
    var local = {
      fetch_meta_start: function (rid, url, cb) { post(o, 'fetch_meta', [url]).then(function (t) { sig('metaReady').emit(rid, t); }); if (cb) cb('{}'); },
      open: function (url, cb) { if (url) window.open(url, '_blank', 'noopener'); if (cb) cb('{}'); },
      save_file: function (name, text, cb) { download(name, new Blob([text], { type: 'text/plain;charset=utf-8' })); if (cb) cb(JSON.stringify({ path: name })); },
      save_zip: function (name, files, cb) {
        post('curioext', 'make_zip', [name, files]).then(function (t) { var r = JSON.parse(t); if (r.b64) download(r.name, b64blob(r.b64, 'application/zip')); if (cb) cb(JSON.stringify(r.error ? r : { path: r.name })); });
      },
      reveal: function (p, cb) { if (cb) cb('{}'); }
    };
    return new Proxy({}, {
      get: function (_, name) {
        if (name === 'then' || typeof name === 'symbol') return undefined;
        if (name === 'metaReady') return sig('metaReady');
        if ((o === 'curio' && (name === 'fetch_meta_start' || name === 'open')) || (o === 'curioext' && local[name])) return local[name];
        if (o === 'curio' && name === 'upload') return function (fname, dataUrl, replace, cb) {       // 10.52: through R2 when it is on
          window.curioR2On().then(function (on) {
            if (!on || typeof dataUrl !== 'string' || dataUrl.indexOf('data:') !== 0) return post(o, 'upload', [fname, dataUrl, replace]).then(function (t) { if (cb) cb(t); });
            window.curioUpload(dataBlob(dataUrl), fname || 'file').then(function (u) { if (cb) cb(JSON.stringify({ url: u })); })
              .catch(function (e) { if (cb) cb(JSON.stringify({ error: e.message })); });
          });
        };
        return function () {
          var args = Array.prototype.slice.call(arguments), cb = typeof args[args.length - 1] === 'function' ? args.pop() : null;
          post(o, name, args).then(function (t) { if (cb) cb(t); });
        };
      }
    });
  }
  // 10.52: big files go straight to Cloudflare R2 (no 4.5 MB limit); small or when R2 is off, the old way
  function api(op, args) {
    return fetch('/api/files', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: JSON.stringify({ op: op, args: args || {} }) })
      .then(function (r) { return r.json(); }).then(function (j) { if (j.error) throw new Error(j.error); return j.data; });
  }
  var r2on = null;
  window.curioR2On = function () {
    if (r2on) return r2on;
    r2on = api('status').then(function (s) { return !!(s && s.on); }).catch(function () { return false; }); return r2on;
  };
  window.curioUpload = async function (blob, name, onprog) {
    var st = await api('start', { name: name, size: blob.size, mime: blob.type || '' });
    if (st.put) {
      var r = await fetch(st.put, { method: 'PUT', body: blob, headers: { 'Content-Type': st.mime } });
      if (!r.ok) throw new Error('Upload failed (' + r.status + ')');
      if (onprog) onprog(1);
    } else {
      var m = st.mpu, c = await (await fetch(m.create, { method: 'POST' })).json(); if (!c.upload) throw new Error('Upload could not start');
      var parts = [], n = Math.ceil(blob.size / m.part_size);
      for (var i = 0; i < n; i++) {
        var pr = await fetch(m.part + '&upload=' + encodeURIComponent(c.upload) + '&part=' + (i + 1), { method: 'PUT', body: blob.slice(i * m.part_size, (i + 1) * m.part_size) });
        var pj = await pr.json(); if (!pr.ok || !pj.etag) throw new Error('Upload stopped at part ' + (i + 1));
        parts.push({ part: pj.part, etag: pj.etag }); if (onprog) onprog((i + 1) / n);
      }
      var done = await fetch(m.complete + '&upload=' + encodeURIComponent(c.upload), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(parts) });
      if (!done.ok) throw new Error('Upload could not finish');
    }
    var d = await api('done', { id: st.id, name: name, mime: st.mime, size: blob.size });
    return d.url;
  };
  function dataBlob(url) {
    var head = url.split(',')[0], b64 = url.slice(head.length + 1), type = (head.match(/data:([^;]+)/) || [])[1] || 'application/octet-stream';
    return b64blob(b64, type);
  }
  window.qt = { webChannelTransport: {} };
  window.QWebChannel = function (transport, cb) { var self = this; this.objects = { curio: make('curio'), curioext: make('curioext') }; setTimeout(function () { cb(self); }, 0); };
})();
