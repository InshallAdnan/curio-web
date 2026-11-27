// Curio files + clock — a Cloudflare Worker in front of the R2 bucket "curio-files".
//
// • Files: Curio Web signs short tickets (ES256). This Worker checks them with Curio Web's PUBLIC key
//   (fetched from CURIO_URL/api/files/key), so no secret is shared. Reading supports Range (videos can seek).
// • Clock: every minute (Cron Trigger "* * * * *") it calls TICK_URL — Curio Web's reminder tick — so due Tracker
//   reminders reach the phone. TICK_URL is the one secret; paste it in Settings › Variables and Secrets.
//
// Bindings: BUCKET (R2 bucket curio-files). Variables: CURIO_URL (text), TICK_URL (secret).

let KEY = null, KEY_AT = 0;

async function pubKey(env) {
  if (KEY && Date.now() - KEY_AT < 3600e3) return KEY;
  const r = await fetch(env.CURIO_URL.replace(/\/$/, '') + '/api/files/key', { cf: { cacheTtl: 300 } });
  if (!r.ok) throw new Error('key ' + r.status);
  const jwk = await r.json();
  KEY = await crypto.subtle.importKey('jwk', { kty: 'EC', crv: 'P-256', x: jwk.x, y: jwk.y, ext: true }, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
  KEY_AT = Date.now(); return KEY;
}

function unb64(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '=';
  const b = atob(s), out = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) out[i] = b.charCodeAt(i); return out;
}

async function ok(env, op, key, exp, extra, sig) {
  if (!key || !exp || !sig || Number(exp) < Date.now() / 1000) return false;
  if (!/^[fl]\/[\w.\/-]{4,200}$/.test(key) || key.includes('..')) return false;
  const msg = new TextEncoder().encode(`${op}|${key}|${exp}|${extra}`);
  try { return await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, await pubKey(env), unb64(sig), msg); }
  catch { return false; }
}

const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, HEAD, PUT, POST, OPTIONS',
               'Access-Control-Allow-Headers': 'Content-Type, Range', 'Access-Control-Expose-Headers': 'ETag, Content-Length, Content-Range, Accept-Ranges',
               'Access-Control-Max-Age': '86400' };
const J = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { ...CORS, 'Content-Type': 'application/json' } });

async function handle(req, env) {
  const u = new URL(req.url), q = u.searchParams, p = u.pathname;
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
  if (p === '/health') return J({ ok: true, bucket: !!env.BUCKET, clock: !!env.TICK_URL, curio: env.CURIO_URL || '' });
  const key = q.get('key'), exp = q.get('exp'), sig = q.get('sig'), type = q.get('type') || 'application/octet-stream';

  if (p === '/get' && (req.method === 'GET' || req.method === 'HEAD')) {
    if (!(await ok(env, 'get', key, exp, '', sig))) return J({ error: 'ticket' }, 403);
    const range = req.headers.get('Range');
    const obj = await env.BUCKET.get(key, range ? { range: req.headers } : {});
    if (!obj) return J({ error: 'not found' }, 404);
    const h = new Headers(CORS); obj.writeHttpMetadata(h); h.set('ETag', obj.httpEtag); h.set('Accept-Ranges', 'bytes');
    h.set('Cache-Control', 'private, max-age=21600');
    if (range && obj.range) {
      const off = obj.range.offset ?? 0, len = obj.range.length ?? (obj.size - off);
      h.set('Content-Range', `bytes ${off}-${off + len - 1}/${obj.size}`); h.set('Content-Length', String(len));
      return new Response(req.method === 'HEAD' ? null : obj.body, { status: 206, headers: h });
    }
    h.set('Content-Length', String(obj.size));
    return new Response(req.method === 'HEAD' ? null : obj.body, { headers: h });
  }
  if (p === '/put' && req.method === 'PUT') {
    const max = q.get('max') || '';
    if (!(await ok(env, 'put', key, exp, `${max}|${type}`, sig))) return J({ error: 'ticket' }, 403);
    const n = Number(req.headers.get('Content-Length') || 0);
    if (!n || n > Number(max)) return J({ error: 'size' }, 413);
    const obj = await env.BUCKET.put(key, req.body, { httpMetadata: { contentType: type } });
    return J({ ok: true, size: obj.size, etag: obj.httpEtag });
  }
  if (p.startsWith('/mpu/')) {
    if (!(await ok(env, 'mpu', key, exp, type, sig))) return J({ error: 'ticket' }, 403);
    if (p === '/mpu/create' && req.method === 'POST') {
      const m = await env.BUCKET.createMultipartUpload(key, { httpMetadata: { contentType: type } });
      return J({ upload: m.uploadId });
    }
    const m = env.BUCKET.resumeMultipartUpload(key, q.get('upload') || '');
    if (p === '/mpu/part' && req.method === 'PUT') {
      const part = await m.uploadPart(Number(q.get('part')), req.body);
      return J({ part: part.partNumber, etag: part.etag });
    }
    if (p === '/mpu/complete' && req.method === 'POST') {
      const parts = await req.json();
      const obj = await m.complete(parts.map(x => ({ partNumber: x.part, etag: x.etag })));
      return J({ ok: true, size: obj.size });
    }
  }
  return J({ error: 'not here' }, 404);
}

export default {
  fetch(req, env) { return handle(req, env).catch(e => J({ error: String(e && e.message || e) }, 500)); },
  async scheduled(event, env, ctx) {
    if (env.TICK_URL) ctx.waitUntil(fetch(env.TICK_URL, { headers: { 'User-Agent': 'Curio-Clock' } }).then(r => r.text()).catch(() => null));
  },
};
