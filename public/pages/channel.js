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
        return function () {
          var args = Array.prototype.slice.call(arguments), cb = typeof args[args.length - 1] === 'function' ? args.pop() : null;
          post(o, name, args).then(function (t) { if (cb) cb(t); });
        };
      }
    });
  }
  window.qt = { webChannelTransport: {} };
  window.QWebChannel = function (transport, cb) { var self = this; this.objects = { curio: make('curio'), curioext: make('curioext') }; setTimeout(function () { cb(self); }, 0); };
})();
