// A loopback-only test adapter for the existing authoritative backend.
import {createServer} from 'node:http';
import {pathToFileURL} from 'node:url';
import {resolve,join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';

const checkout=resolve(process.argv[2]??'../drenovar-web84');
const {handleGame}=await import(pathToFileURL(join(checkout,'gameplay37/server/hosted.mjs')));
const sql=new DatabaseSync(':memory:');
sql.exec('CREATE TABLE game_realm37(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL)');
const db={prepare(query){return {bind(...args){return {
 async first(){return sql.prepare(query).get(...args);},
 async run(){return {meta:{changes:sql.prepare(query).run(...args).changes}};}
};}};}};

const port=Number(process.env.DRENOVAR_TEST_PORT??8417);
const origin='http://127.0.0.1:'+port;
const paths=new Set(['state','command','session/new','march-preview']);
let simulatedTime=null;
let timeoutCityPreview=process.env.DRENOVAR_TEST_CITY_PREVIEW_TIMEOUT==='1';
const battleFixture=process.env.DRENOVAR_TEST_BATTLE_FIXTURE==='1';
// Route QA: Tenerys I stands next to a later building ("Нет безопасного пути к цели" in v92).
// '1': clock frozen with the creature in the blocked cell; 'moving': the clock runs and
// the creature walks its patrol, in and out of the building's clearance.
const blockedCreatureFixture=['1','moving'].includes(process.env.DRENOVAR_TEST_BLOCKED_CREATURE)?process.env.DRENOVAR_TEST_BLOCKED_CREATURE:'';
// Proposed speedup grants (server patch speedups-v2); never on outside this isolated realm.
const speedupGrantsV2=process.env.DRENOVAR_TEST_SPEEDUP_GRANTS==='1';
// Simulated network delay of the hosted server (ms, each way split evenly), for timer QA.
const delayMs=Number(process.env.DRENOVAR_TEST_DELAY_MS??0);
const pause=ms=>ms>0?new Promise(resolve=>setTimeout(resolve,ms)):null;
const server=createServer(async (incoming,out)=>{
 try {
  const url=new URL(incoming.url,origin);
  if(url.pathname==='/test/clock'&&incoming.method==='POST'){
   const time=Number(url.searchParams.get('time'));
   if(!Number.isSafeInteger(time)||time<(simulatedTime??Date.now())){
    out.writeHead(400).end();return;
   }
   simulatedTime=time;
   out.writeHead(204).end();return;
  }
  if(url.origin!==origin || !url.pathname.startsWith('/api/') || !paths.has(url.pathname.slice(5))) {
   out.writeHead(404).end();return;
  }
  const headers=new Headers();
  for(const key of ['content-type','idempotency-key','x-drenovar-player','origin']){
   const value=incoming.headers[key];
   if(typeof value==='string')headers.set(key,value);
  }
  headers.set('oai-authenticated-user-id','native-loopback-tester');
  let body;
  if(incoming.method==='POST'){
   const chunks=[];let length=0;
   for await(const data of incoming){
    length+=data.length;
    if(length>16384){out.writeHead(413).end();return;}
    chunks.push(data);
   }
   body=Buffer.concat(chunks);
  }
  if(timeoutCityPreview&&url.pathname==='/api/march-preview'&&body&&JSON.parse(body).kind==='deploy'){
   timeoutCityPreview=false;
   return;
  }
  await pause(delayMs/2);
  const response=await handleGame(new Request(url,{method:incoming.method,headers,body}),db,{
   worldEnabled:true,isolated:true,realmId:'native-loopback-only',clock:()=>simulatedTime??Date.now(),speedupGrantsV2
  });
  if(battleFixture&&url.pathname==='/api/session/new'&&response.status===201){
   const record=sql.prepare('SELECT data FROM game_realm37 WHERE id=?').get('native-loopback-only');
   const snapshot=JSON.parse(record.data);
   const [id,entry]=snapshot.repository.players[0];
   const player=JSON.parse(entry.state);
   player.city.military.owned={'ENG-03':200};
   player.city.demo.wallet.food=200;
   player.city.buildings=player.city.buildings.filter(building=>building.type!=='RES-04');
   snapshot.repository.players[0]=[id,{...entry,state:JSON.stringify(player)}];
   sql.prepare('UPDATE game_realm37 SET data=?, revision=revision+1 WHERE id=?').run(JSON.stringify(snapshot),'native-loopback-only');
  }
  if(blockedCreatureFixture&&url.pathname==='/api/session/new'&&response.status===201){
   // A building raised next to Tenerys I after it spawned (plot v1-33 at -38,-40),
   // the creature held at (-40,-40) inside the building's 5 m clearance; clock frozen.
   const record=sql.prepare('SELECT data FROM game_realm37 WHERE id=?').get('native-loopback-only');
   const snapshot=JSON.parse(record.data);
   const [id,entry]=snapshot.repository.players[0];
   const player=JSON.parse(entry.state);
   player.city.buildings.push({id:'building-v1-33',type:'ECO-03',plotId:'v1-33',level:1});
   player.city.military.owned={...player.city.military.owned,'ENG-09':20};
   snapshot.repository.players[0]=[id,{...entry,state:JSON.stringify(player)}];
   if(blockedCreatureFixture==='1')simulatedTime=simulatedTime??Date.now();
   const fixtureNow=simulatedTime??Date.now();
   for(const pair of snapshot.repository.encounters){
    const encounter=JSON.parse(pair[1].state);
    if(encounter.owner===id&&encounter.level===1){encounter.spawnedAt=fixtureNow-12000;encounter.position={x:-40,z:-40};pair[1]={...pair[1],state:JSON.stringify(encounter)};}
   }
   sql.prepare('UPDATE game_realm37 SET data=?, revision=revision+1 WHERE id=?').run(JSON.stringify(snapshot),'native-loopback-only');
  }
  const text=await response.text();
  await pause(delayMs/2);
  out.writeHead(response.status,Object.fromEntries(response.headers)).end(text);
 } catch (error) {
  console.error(error);
  if(!out.headersSent)out.writeHead(500,{'Content-Type':'application/json'}).end(JSON.stringify({error:'Local test realm error'}));
 }
});
server.listen(port,'127.0.0.1',()=>console.log(origin));
