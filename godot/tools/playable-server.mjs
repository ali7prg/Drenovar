// Synthetic, in-memory native integration fixture. Never opens a production DB.
// DRENOVAR_SERVER_ROOT points to the exact deployed server checkout or candidate.
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
const sql = new DatabaseSync(':memory:');
sql.exec('CREATE TABLE game_realm37(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL)');
const db = sqliteD1(sql), store = snapshotStore(db), requests = [];
const port = Number(process.env.DRENOVAR_QA_PORT ?? 8797);
let offset = 0;
let failedDeploys = Number(process.env.DRENOVAR_QA_FAIL_DEPLOY ?? 0);
createServer(async(req, res) => {
 try {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  const chunks = []; for await (const b of req) chunks.push(b);
  const body = Buffer.concat(chunks);
  if (url.pathname === '/qa/requests') {
   res.writeHead(200, {'content-type':'application/json'}).end(JSON.stringify(requests)); return;
  }
  if (url.pathname === '/qa/clock' && req.method === 'POST') {
   offset = Number(JSON.parse(body).time) - Date.now();
   res.writeHead(200, {'content-type':'application/json'}).end('{}'); return;
  }
  if (!url.pathname.startsWith('/api/')) {res.writeHead(404).end(); return;}
  if (url.pathname.startsWith('/api/qa-status/')) {
   const code=Number(url.pathname.split('/').at(-1));
   res.writeHead(code,{'content-type':code>=500?'text/html':'application/json'}).end(code>=500?'<html>Worker exceeded resource limit</html>':'{}');return;
  }
  const response = await handleV6Request(new Request(url, {
   method:req.method, headers:req.headers,
   ...(!['GET','HEAD'].includes(req.method) ? {body} : {})
  }), db, {clock:() => Date.now() + offset});
  const data = Buffer.from(await response.arrayBuffer());
  if (response.ok && url.pathname.endsWith('/session/new')) {
   const row = await store.load(TEST_REALM), realm = JSON.parse(row.data);
   const entry = realm.repository.players.at(-1), player = JSON.parse(entry[1].state);
   // DRENOVAR_QA_ALL_UNITS=1: every troop type (qa_all_troop_attacks.gd).
   player.v6.healthy = process.env.DRENOVAR_QA_ALL_UNITS==='1'
    ? Object.fromEntries(['ENG-01','ENG-02','ENG-03','ENG-04','ENG-05','ENG-06','ENG-07','ENG-08','ENG-09','ENG-10'].map(k=>[k,60]))
    : {'ENG-03':300, 'ENG-05':300, 'ENG-01':300, 'ENG-02':300};
   player.v6.buildings.find(b => b.type === 'B01').level = 11;
   entry[1].state = JSON.stringify(project(player));
   await store.commit(TEST_REALM, row.revision, JSON.stringify(realm));
  }
  const command = body.length ? JSON.parse(body) : {};
  // Regression controls for delayed previews racing a submitted command.
  // Only this loopback fixture reads these variables.
  const previewDelay=url.pathname.endsWith('/march-preview') ? Number(process.env.DRENOVAR_QA_PREVIEW_DELAY_MS??0) : 0;
  const commandDelay=url.pathname.endsWith('/command') && command.kind==='deploy' ? Number(process.env.DRENOVAR_QA_COMMAND_DELAY_MS??0) : 0;
  if(previewDelay||commandDelay)await new Promise(resolve=>setTimeout(resolve,previewDelay||commandDelay));
  const previewFault=previewDelay>0 && process.env.DRENOVAR_QA_PREVIEW_ERROR==='1';
  // Simulate a response lost AFTER a successful commit. Real retries must use
  // the same receipt and must not create another army. Only this loopback tool.
  const fault=url.pathname.endsWith('/command') && response.ok && command.kind==='deploy' && failedDeploys>0;
  if(fault)failedDeploys--;
  // Never log auth headers/device secrets, even in the synthetic fixture.
  requests.push({path:url.pathname,method:req.method,status:fault||previewFault?503:response.status,at:Date.now()+offset,
   receipt: createHash('sha256').update(req.headers['idempotency-key']??'').digest('hex'),
   ...(command.kind ? {kind:command.kind, units:command.units, encounterId:command.encounterId} : {})});
  if(fault||previewFault)res.writeHead(503,{'content-type':'text/html'}).end('<html>Worker exceeded resource limit</html>');
  else res.writeHead(response.status, Object.fromEntries(response.headers)).end(data);
 } catch(e) {console.error(e.stack); if (!res.headersSent) res.writeHead(500).end(JSON.stringify({error:e.message}));}
}).listen(port, '127.0.0.1', () => console.log(`SYNTHETIC_ONLY http://127.0.0.1:${port} source=${source}`));
