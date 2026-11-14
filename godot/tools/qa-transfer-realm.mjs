// QA only: an "old server" and a "new server" on 127.0.0.1 for the settlement transfer.
//   node qa-transfer-realm.mjs <drenovar-server checkout>
// Old server (:8420): the ORIGINAL v92 native login (native-session.mjs) and game; the
//   ChatGPT login on the approval page is simulated by /__qa/approve (user chatgpt-ali).
// New server (:8421): the production game Worker (cloudflare_transfer/worker-game.mjs)
//   with DRENOVAR_OLD_SERVER pointing at :8420.
import {createServer} from 'node:http';
import {pathToFileURL} from 'node:url';
import {join, resolve} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
const root = resolve(process.argv[2]);
const {handleGame} = await import(pathToFileURL(join(root, 'DRENOVAR-Server-v92/gameplay37/server/hosted.mjs')));
const {handleNative} = await import(pathToFileURL(join(root, 'DRENOVAR-Server-v92/gameplay37/server/native-session.mjs')));
const worker = (await import(pathToFileURL(join(root, 'cloudflare_transfer/worker-game.mjs')))).default;
const shim = () => {
  const sql = new DatabaseSync(':memory:');
  sql.exec('CREATE TABLE game_realm37(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL)');
  return {sql, db: {prepare(q) { return {bind(...a) { return {
    async first() { return sql.prepare(q).get(...a); },
    async run() { return {meta: {changes: sql.prepare(q).run(...a).changes}}; }}; }}; }}};
};
const oldDb = shim(), newDb = shim();
const OLD = 'http://127.0.0.1:8420', NEW = 'http://127.0.0.1:8421';
const toRequest = async (incoming, origin) => {
  const chunks = []; for await (const c of incoming) chunks.push(c);
  const body = Buffer.concat(chunks);
  const headers = new Headers();
  for (const [k, v] of Object.entries(incoming.headers)) if (typeof v === 'string') headers.set(k, v);
  return new Request(origin + incoming.url, {method: incoming.method, headers, body: ['GET', 'HEAD'].includes(incoming.method) ? undefined : body});
};
const send = async (out, response) => {
  out.writeHead(response.status, Object.fromEntries(response.headers));
  out.end(Buffer.from(await response.arrayBuffer()));
};
// The old settlement of chatgpt-ali: town hall II, soldiers, resources.
await handleGame(new Request(OLD + '/api/session/new', {method: 'POST', body: '{}', headers: {'content-type': 'application/json', origin: OLD}}), oldDb.db,
  {worldEnabled: true, authenticatedUser: 'chatgpt-ali'});
{
  const row = oldDb.sql.prepare("SELECT data FROM game_realm37 WHERE id='development-37'").get();
  const snap = JSON.parse(row.data);
  for (const entry of snap.repository.players) {
    const p = JSON.parse(entry[1].state);
    p.city.buildings.find(b => b.type === 'ECO-05').level = 2;
    p.city.military.owned['ENG-09'] = 110; p.city.military.owned['ENG-01'] = 90;
    p.city.demo.wallet = {...p.city.demo.wallet, food: 1000000, stone: 998900, iron: 997700, coins: 990600};
    p.city.progress.wood = 992300; p.nickname = 'Ali';
    entry[1].state = JSON.stringify(p);
  }
  oldDb.sql.prepare("UPDATE game_realm37 SET data=?, revision=revision+1 WHERE id='development-37'").run(JSON.stringify(snap));
}
createServer(async (incoming, out) => {
  try {
    const url = new URL(incoming.url, OLD);
    if (url.pathname === '/__qa/approve') {
      // The player approves in Safari while signed in to ChatGPT on the old server.
      const challenge = url.searchParams.get('challenge');
      const r = await handleNative(new Request(OLD + '/api/native/approve?challenge=' + challenge, {method: 'POST',
        body: 'code=' + challenge.slice(0, 8), headers: {origin: OLD, 'content-type': 'application/x-www-form-urlencoded', 'oai-authenticated-user-id': 'chatgpt-ali'}}), oldDb.db, handleGame);
      return send(out, r);
    }
    const request = await toRequest(incoming, OLD);
    request.headers.delete('oai-authenticated-user-id');
    if (url.pathname === '/api/native/game/state') console.log('old server: state read for transfer');
    await send(out, await handleNative(request, oldDb.db, handleGame));
  } catch (e) { out.writeHead(500).end(String(e)); }
}).listen(8420, '127.0.0.1');
createServer(async (incoming, out) => {
  try { await send(out, await worker.fetch(await toRequest(incoming, NEW), {DB: newDb.db, DRENOVAR_OLD_SERVER: OLD})); }
  catch (e) { out.writeHead(500).end(String(e)); }
}).listen(8421, '127.0.0.1');
console.log('old server', OLD, 'new server', NEW);
