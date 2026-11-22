// Synthetic, in-memory V6 fixture for the 1022 client QA (qa_net_1022.gd, qa_forest_v6.gd).
// Never opens a production or staging database; it runs the V6 code of a local server
// checkout (DRENOVAR_SERVER_ROOT) against an in-memory SQLite realm.
//
//   DRENOVAR_SERVER_ROOT=../drenovar-server node godot/tools/qa-v6-1022-server.mjs
//
// Environment (fixture only):
//   DRENOVAR_QA_PORT=8799            listen port (127.0.0.1)
//   DRENOVAR_QA_ADVENTURE=1          handleV6Request(..., {adventure:true}) (DRENOVAR_V6_ADVENTURE=true)
//   DRENOVAR_QA_CONDITIONAL=1        conditional state polls (DRENOVAR_V6_CONDITIONAL=true)
//   DRENOVAR_QA_HALL=3               town hall (B01) level of the new settlement
// The Godot client in loopback mode sends no X-Drenovar-Session; the fixture adds a
// fixed synthetic device session to requests without one, so V6 device auth applies.
//
// QA controls (POST, JSON):
//   /qa/requests            log of API requests (no secrets; receipts are hashed)
//   /qa/fault  {kind,count,mode}  next <count> commands of <kind> ('*' = any): mode 'drop'
//                           (committed, then the connection is cut: a lost answer), '503'
//                           (HTML 503 before the server sees it) or 'timeout' (no answer for 15 s)
//   /qa/poll-fault {count,mode}   the same for GET state
//   /test/clock?time=<ms>   move the server clock forward (never backward)
//   /test/hall?level=<n>    set B01 (town hall) to level n
//   /test/army {units}      set the healthy army
import {createServer} from 'node:http';
import {DatabaseSync} from 'node:sqlite';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const source = process.env.DRENOVAR_SERVER_ROOT;
if (!source) throw Error('DRENOVAR_SERVER_ROOT must name a local server checkout');
const moduleAt = file => import(pathToFileURL(resolve(source, file)));
const {sqliteD1} = await moduleAt('v6/sqlite-d1.mjs');
const {handleV6Request, TEST_REALM} = await moduleAt('v6/http.mjs');
const {snapshotStore} = await moduleAt('v6/snapshot-store.mjs');
const {project} = await moduleAt('v6/game.mjs');
const {CONDITIONAL_VERSION} = await moduleAt('v6/conditional.mjs');
const sql = new DatabaseSync(':memory:');
sql.exec('CREATE TABLE game_realm37(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL)');
const db = sqliteD1(sql), store = snapshotStore(db), requests = [];
const port = Number(process.env.DRENOVAR_QA_PORT ?? 8799);
const adventure = process.env.DRENOVAR_QA_ADVENTURE === '1';
const conditional = process.env.DRENOVAR_QA_CONDITIONAL === '1' ? {build: [CONDITIONAL_VERSION, 'qa-1022', adventure].join('|')} : null;
const DEVICE = 'device.' + 'c'.repeat(64);
let offset = 0;
let fault = null, pollFault = null;

async function mutatePlayer(change) {
 const row = await store.load(TEST_REALM);
 if (!row) return false;
 const realm = JSON.parse(row.data);
 for (const entry of realm.repository?.players ?? []) {
  const player = JSON.parse(entry[1].state);
  change(player);
  entry[1].state = JSON.stringify(project(player));
 }
 await store.commit(TEST_REALM, row.revision, JSON.stringify(realm));
 return true;
}

const json = (res, code, value) => res.writeHead(code, {'content-type':'application/json'}).end(JSON.stringify(value));

createServer(async(req, res) => {
 try {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  const chunks = []; for await (const b of req) chunks.push(b);
  const body = Buffer.concat(chunks);
  const input = body.length ? JSON.parse(body) : {};
  if (url.pathname === '/qa/requests') return json(res, 200, requests);
  if (url.pathname === '/qa/fault') { fault = {kind: input.kind ?? '*', count: Number(input.count ?? 1), mode: input.mode ?? 'drop'}; return json(res, 200, fault); }
  if (url.pathname === '/qa/poll-fault') { pollFault = {count: Number(input.count ?? 1), mode: input.mode ?? '503'}; return json(res, 200, pollFault); }
  if (url.pathname === '/test/clock') {
   const time = Number(url.searchParams.get('time') ?? input.time);
   if (time > Date.now() + offset) offset = time - Date.now();
   return json(res, 200, {now: Date.now() + offset});
  }
  if (url.pathname === '/test/hall') {
   const level = Number(url.searchParams.get('level') ?? input.level);
   return json(res, 200, {ok: await mutatePlayer(p => { p.v6.buildings.find(b => b.type === 'B01').level = level; })});
  }
  if (url.pathname === '/test/army') {
   return json(res, 200, {ok: await mutatePlayer(p => { p.v6.healthy = {...input.units}; })});
  }
  if (!url.pathname.startsWith('/api/')) { res.writeHead(404).end(); return; }
  const headers = {...req.headers};
  if (!headers['x-drenovar-session']) headers['x-drenovar-session'] = DEVICE;
  const command = url.pathname.endsWith('/command') ? input : {};
  const isPoll = req.method === 'GET' && /\/state$/.test(url.pathname);
  const record = {path: url.pathname, method: req.method, at: Date.now() + offset,
   receipt: createHash('sha256').update(req.headers['idempotency-key'] ?? '').digest('hex').slice(0, 16),
   conditional: req.headers['x-drenovar-conditional'] === '1', ifNoneMatch: !!req.headers['if-none-match'],
   economy: req.headers['x-drenovar-economy'] ?? null,
   ...(command.kind ? {kind: command.kind, action: command.action ?? null} : {})};
  requests.push(record);
  // Faults before the server sees the request: 503 page or a hang (client timeout).
  const commandFault = fault && url.pathname.endsWith('/command') && (fault.kind === '*' || fault.kind === command.kind) && fault.count > 0;
  const stateFault = pollFault && isPoll && pollFault.count > 0;
  const early = commandFault && fault.mode !== 'drop' ? fault.mode : stateFault ? pollFault.mode : null;
  if (early) {
   if (commandFault) fault.count--; else pollFault.count--;
   record.status = early === '503' ? 503 : 0; record.fault = early;
   if (early === '503') { res.writeHead(503, {'content-type':'text/html'}).end('<html>Worker exceeded resource limit</html>'); return; }
   if (early === 'drop') { req.socket.destroy(); return; }
   setTimeout(() => req.socket.destroy(), 15000); return;
  }
  const response = await handleV6Request(new Request(url, {
   method: req.method, headers,
   ...(!['GET','HEAD'].includes(req.method) ? {body} : {})
  }), db, {clock: () => Date.now() + offset, adventure, conditional});
  const data = Buffer.from(await response.arrayBuffer());
  if (response.ok && url.pathname.endsWith('/session/new') && response.status === 201) {
   const hall = Number(process.env.DRENOVAR_QA_HALL ?? 3);
   await mutatePlayer(p => {
    p.v6.healthy = {'ENG-01': 40, 'ENG-02': 40, 'ENG-03': 40, 'ENG-04': 20, 'ENG-06': 20};
    p.v6.buildings.find(b => b.type === 'B01').level = hall;
   });
  }
  record.status = response.status;
  record.etag = !!response.headers.get('etag');
  if (commandFault && fault.mode === 'drop') {
   // The command is committed; its answer is lost on the way (a dropped mobile link).
   fault.count--; record.fault = 'drop'; req.socket.destroy(); return;
  }
  const out = Object.fromEntries(response.headers);
  if (response.status === 304) { res.writeHead(304, out); res.end(); return; }
  res.writeHead(response.status, out).end(data);
 } catch(e) { console.error(e.stack); if (!res.headersSent) res.writeHead(500).end(JSON.stringify({error: e.message})); }
}).listen(port, '127.0.0.1', () => console.log(`SYNTHETIC_ONLY http://127.0.0.1:${port} adventure=${adventure} conditional=${!!conditional} source=${source}`));
