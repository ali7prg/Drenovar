// Loopback-only network jitter between the native client and playable-server.mjs.
// Reproduces a mobile connection: every answer is held back by a random delay
// (base + lognormal tail, occasional multi-second spikes), and a share of requests
// can fail. Never forwards anywhere but 127.0.0.1.
//   DRENOVAR_JITTER_PORT=8798 DRENOVAR_JITTER_TARGET=8797
//   DRENOVAR_JITTER_BASE_MS=120 DRENOVAR_JITTER_SIGMA=0.9 DRENOVAR_JITTER_SPIKE=0.06
//   DRENOVAR_JITTER_SPIKE_MS=2500 DRENOVAR_JITTER_FAIL=0 DRENOVAR_JITTER_SEED=1
import {createServer, request} from 'node:http';
const env = process.env;
const port = Number(env.DRENOVAR_JITTER_PORT ?? 8798), target = Number(env.DRENOVAR_JITTER_TARGET ?? 8797);
const base = Number(env.DRENOVAR_JITTER_BASE_MS ?? 120), sigma = Number(env.DRENOVAR_JITTER_SIGMA ?? 0.9);
const spike = Number(env.DRENOVAR_JITTER_SPIKE ?? 0.06), spikeMs = Number(env.DRENOVAR_JITTER_SPIKE_MS ?? 2500);
const fail = Number(env.DRENOVAR_JITTER_FAIL ?? 0);
// Jitter starts this long after launch (lets a synthetic test account sign up first).
const startAfter = Number(env.DRENOVAR_JITTER_START_AFTER_MS ?? 0), launched = Date.now();
let seed = Number(env.DRENOVAR_JITTER_SEED ?? 1) >>> 0 || 1;
const rnd = () => { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; return (seed >>> 0) / 4294967296; };
const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-12)) * Math.cos(2 * Math.PI * rnd());
const delay = () => base * Math.exp(sigma * gauss()) + (rnd() < spike ? spikeMs * (0.5 + rnd()) : 0);
const log = [];
createServer((req, res) => {
  const chunks = [];
  req.on('data', c => chunks.push(c));
  req.on('end', () => {
    const active = Date.now() - launched >= startAfter;
    const body = Buffer.concat(chunks), wait = active ? delay() : 0, drop = active && rnd() < fail;
    log.push({path: req.url, at: Date.now(), wait: Math.round(wait), drop});
    if (req.url === '/jitter/log') { res.writeHead(200, {'content-type': 'application/json'}).end(JSON.stringify(log)); return; }
    const up = request({host: '127.0.0.1', port: target, path: req.url, method: req.method, headers: {...req.headers, host: `127.0.0.1:${target}`, ...(req.headers.origin ? {origin: `http://127.0.0.1:${target}`} : {})}}, r => {
      const parts = [];
      r.on('data', c => parts.push(c));
      r.on('end', () => setTimeout(() => {
        if (drop) { res.writeHead(503, {'content-type': 'text/html'}).end('<html>jitter drop</html>'); return; }
        res.writeHead(r.statusCode, r.headers).end(Buffer.concat(parts));
      }, wait));
    });
    up.on('error', e => { res.writeHead(502).end(String(e)); });
    up.end(body);
  });
}).listen(port, '127.0.0.1', () => console.log(`JITTER http://127.0.0.1:${port} -> ${target} base=${base} sigma=${sigma} spike=${spike}x${spikeMs} fail=${fail}`));
