#!/usr/bin/env node
// «Лес потерянных» local realm — loopback HTTP server the Godot client can play against:
//   godot --path godot/project -- --server=http://127.0.0.1:8418
// Env: DRENOVAR_FR_PORT (default 8418, 0 = random), DRENOVAR_FR_DB (default <tmpdir>/drenovar-forest-rescue-realm.json),
//      DRENOVAR_FR_BUILD_SECONDS (hall upgrade timer, default 10), DRENOVAR_FR_START_TIME (fixed simulated start clock, ms),
//      DRENOVAR_FR_TEST_ENDPOINTS=0 disables the /test/* helpers.
import {createServer} from 'node:http';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRealm, DEFAULT_LOGIN} from './realm.mjs';
import {AdventureError, toAdventureError} from '../src/errors.mjs';

export const DEFAULT_PORT = 8418;
const BODY_LIMIT = 16384;

function send(out, status, body) {
  if (body === null || body === undefined) { out.writeHead(status).end(); return; }
  const text = JSON.stringify(body);
  out.writeHead(status, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'Content-Length': Buffer.byteLength(text)}).end(text);
}

async function readBody(incoming) {
  const chunks = [];
  let length = 0;
  for await (const data of incoming) {
    length += data.length;
    if (length > BODY_LIMIT) throw Object.assign(new Error('BODY_TOO_LARGE'), {httpStatus: 413, body: {error: 'BODY_TOO_LARGE', message: 'Слишком большой запрос.'}});
    chunks.push(data);
  }
  if (!length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw Object.assign(new Error('BAD_JSON'), {httpStatus: 400, body: {error: 'BAD_FIELDS', message: 'Тело запроса не является JSON.'}});
  }
}

export function createHandler(realm) {
  return async function handle(incoming, out) {
    try {
      const url = new URL(incoming.url, 'http://127.0.0.1');
      const header = name => (typeof incoming.headers[name] === 'string' ? incoming.headers[name] : null);
      const who = {login: header('oai-authenticated-user-id') ?? DEFAULT_LOGIN, selected: header('x-drenovar-player') || null};
      const method = incoming.method;
      let r;
      if (url.pathname === '/api/state' && method === 'GET') r = await realm.getState(who);
      else if (url.pathname === '/api/session/new' && method === 'POST') r = await realm.sessionNew({...who, body: await readBody(incoming)});
      else if (url.pathname === '/api/command' && method === 'POST') r = await realm.command({...who, key: header('idempotency-key'), body: await readBody(incoming)});
      else if (url.pathname.startsWith('/test/') && process.env.DRENOVAR_FR_TEST_ENDPOINTS === '0') r = {status: 404, body: {error: 'NOT_FOUND', message: 'Тестовые адреса отключены.'}};
      else if (url.pathname === '/api/march-preview' && method === 'POST') {
        await readBody(incoming);
        r = {status: 404, body: {error: 'UNSUPPORTED_IN_LOCAL_REALM', message: 'Походы и охота недоступны в локальном мире приключения.'}};
      } else if (url.pathname === '/test/clock' && method === 'POST') {
        r = await realm.testClock({time: url.searchParams.has('time') ? Number(url.searchParams.get('time')) : undefined, mode: url.searchParams.get('mode')});
      } else if (url.pathname === '/test/hall' && method === 'POST') r = await realm.testHall(who, Number(url.searchParams.get('level')));
      else if (url.pathname === '/test/army' && method === 'POST') r = await realm.testArmy(who, await readBody(incoming));
      else if (url.pathname === '/test/wallet' && method === 'POST') r = await realm.testWallet(who, await readBody(incoming));
      else if (url.pathname === '/test/building' && method === 'POST') r = await realm.testBuilding(who, {type: url.searchParams.get('type'), level: Number(url.searchParams.get('level'))});
      else if (url.pathname === '/health' && method === 'GET') r = {status: 200, body: {ok: true, revision: realm.store.revision, serverTime: realm.clock()}};
      else r = {status: 404, body: {error: 'NOT_FOUND', message: 'Неизвестный адрес локального мира.'}};
      send(out, r.status, r.body);
    } catch (error) {
      if (error?.httpStatus) { send(out, error.httpStatus, error.body); return; }
      const e = error instanceof AdventureError ? error : toAdventureError(error);
      if (e.internal) console.error(e.cause ?? e);
      send(out, e.status, e.toBody());
    }
  };
}

export async function startServer({port = Number(process.env.DRENOVAR_FR_PORT ?? DEFAULT_PORT), host = '127.0.0.1',
  dbPath = process.env.DRENOVAR_FR_DB ?? join(tmpdir(), 'drenovar-forest-rescue-realm.json'), quiet = false, ...options} = {}) {
  const startEnv = process.env.DRENOVAR_FR_START_TIME;
  const realm = createRealm({dbPath: resolve(dbPath), startTime: startEnv ? Number(startEnv) : null, ...options});
  const server = createServer(createHandler(realm));
  await new Promise((ok, fail) => { server.once('error', fail); server.listen(port, host, ok); });
  const actual = server.address().port;
  if (!quiet) {
    console.log('Лес потерянных — local realm http://' + host + ':' + actual + ' (db: ' + resolve(dbPath) + ')');
    console.log('LISTENING ' + actual);
  }
  return {server, realm, port: actual, url: 'http://' + host + ':' + actual,
    close: () => new Promise(ok => { server.closeAllConnections?.(); server.close(() => ok()); })};
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const running = await startServer();
  const stop = async () => { await running.close(); process.exit(0); };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
}

