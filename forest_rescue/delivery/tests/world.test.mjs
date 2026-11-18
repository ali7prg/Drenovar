import test from'node:test';import assert from'node:assert/strict';
import{createFogState,createFogAuthority,isExplored,exploredCellCount,validateFogState,projectFogForClient,forestUnlocked,MIN_HALL_LEVEL,ENTRANCE_CORRIDOR}from'../code/fog.mjs';
import{allChunks,chunkIdAt,generateScatter,selectChunks,insideMask,SCATTER_COVERAGE}from'../code/world-layout.mjs';
import fs from'node:fs';
const atlas=JSON.parse(fs.readFileSync(new URL('../data/world-atlas.json',import.meta.url)));
const traversal={ownerId:'owner',actorId:'squad1',routeId:'route1',sequence:1,committed:true,navigationChecked:true,path:[{x:-8,z:-54},{x:-10,z:-60},{x:-14,z:-66}]};
const command={actorId:'squad1',routeId:'route1'},auth={authenticatedPlayerId:'owner',hallLevel:3};
const maskProof={maskRevision:'synthetic-test-city:1',coverage:Object.fromEntries(SCATTER_COVERAGE.map(k=>[k,true]))};
test('fog starts with existing base visible, distant forest hidden',()=>{const s=createFogState();assert.equal(isExplored(s,0,0),true);assert.equal(isExplored(s,75,-86),false);assert.equal(exploredCellCount(s),784);assert.equal(validateFogState(JSON.parse(JSON.stringify(s))),true);});
test('committed server traversal reveals persistently and repeat is idempotent',async()=>{const s=createFogState(),f=createFogAuthority({resolveTraversal:async()=>traversal});const next=await f.reveal(s,command,auth);assert.ok(exploredCellCount(next)>exploredCellCount(s));assert.equal(isExplored(next,-14,-66),true);assert.equal(isExplored(s,-14,-66),false);assert.deepEqual(await f.reveal(JSON.parse(JSON.stringify(next)),command,auth),next);});
test('forged coordinate commands, ownership, and uncommitted movement rejected',async()=>{const f=createFogAuthority({resolveTraversal:async()=>traversal});await assert.rejects(f.reveal(createFogState(),{...command,x:75,z:-86},auth),/INVALID_FOG_COMMAND/);await assert.rejects(f.reveal(createFogState(),command,{authenticatedPlayerId:'other',hallLevel:3}),/UNVERIFIED_TRAVERSAL/);const g=createFogAuthority({resolveTraversal:async()=>({...traversal,committed:false})});await assert.rejects(g.reveal(createFogState(),command,auth),/UNVERIFIED_TRAVERSAL/);});
test('version, bad bitset, sparse jumping paths and NaN are rejected',async()=>{assert.throws(()=>validateFogState({...createFogState(),schemaVersion:2}),/UNSUPPORTED/);assert.throws(()=>validateFogState({...createFogState(),exploredBase64:'AAAA'}),/ENCODING/);const f=createFogAuthority({resolveTraversal:async()=>({...traversal,path:[{x:0,z:0},{x:75,z:-86}]})});await assert.rejects(f.reveal(createFogState(),command,auth),/DENSIFIED/);const g=createFogAuthority({resolveTraversal:async()=>({...traversal,path:[{x:NaN,z:0}]})});await assert.rejects(g.reveal(createFogState(),command,auth),/INVALID_TRAVERSAL/);});
test('fog monotonically expands between routes without exposing boss on camera move',async()=>{let t=traversal;const f=createFogAuthority({resolveTraversal:async()=>t});const first=await f.reveal(createFogState(),command,auth);t={...traversal,routeId:'route2',path:[{x:-14,z:-66},{x:-20,z:-66}]};const next=await f.reveal(first,{...command,routeId:'route2'},auth);assert.ok(exploredCellCount(next)>=exploredCellCount(first));assert.equal(isExplored(next,75,-86),false);});
test('chunks cover every authored POI exactly once',()=>{assert.equal(allChunks().length,16);assert.equal(chunkIdAt(-112,-112),'lf_chunk_0_0');assert.equal(chunkIdAt(112,0),null);for(const site of atlas.sites)assert.equal(site.chunkId,chunkIdAt(site.center.x,site.center.z));assert.equal(atlas.sites.length,12);assert.equal(atlas.zones.length,8);});
test('scatter repeats by seed and respects reserved property and road corridor',()=>{const masks=[{type:'box',minX:-112,maxX:-80,minZ:-112,maxZ:-56},{type:'capsule',a:{x:-80,z:-90},b:{x:-56,z:-90},radius:4}];const opts={...maskProof,chunkId:'lf_chunk_0_0',count:40,masks,terrain:()=>({dry:true,y:1,slope:0})};const a=generateScatter(opts),b=generateScatter(opts);assert.deepEqual(a,b);assert.equal(a.placed,40);assert.ok(a.instances.every(p=>masks.every(m=>!insideMask(p,m,1.3*p.scale))));assert.ok(a.instances.every(p=>p.ownership==='ambient'));});
test('no scatter on water, cliffs, or fully reserved chunk',()=>{assert.equal(generateScatter({...maskProof,masks:[],chunkId:'lf_chunk_0_0',count:4,terrain:()=>({dry:false,y:0,slope:0})}).placed,0);assert.equal(generateScatter({...maskProof,masks:[],chunkId:'lf_chunk_0_0',count:4,terrain:()=>({dry:true,y:1,slope:40})}).placed,0);});
test('streaming budgets never evict pinned squad or pause simulation',()=>{const plan=selectChunks({camera:{x:0,z:0},pinnedPoints:[{x:75,z:-86}],isChunkExplored:()=>true});assert.ok(plan.full.includes(chunkIdAt(75,-86)));assert.ok(plan.full.length<=4);assert.ok(plan.proxy.length<=8);assert.equal(new Set([...plan.full,...plan.proxy,...plan.fogOnly,...plan.unloaded]).size,16);const overflow=selectChunks({camera:{x:0,z:0},fullBudget:1,pinnedPoints:[{x:-100,z:-100},{x:100,z:100}]});assert.equal(overflow.overflow,1);assert.equal(overflow.full.length,2);});
test('unknown unpinned chunks use fog only, not full geometry',()=>{const plan=selectChunks({camera:{x:0,z:0},isChunkExplored:()=>false});assert.equal(plan.full.length,0);assert.equal(plan.proxy.length,0);assert.ok(plan.fogOnly.length>0);});
test('atlas path endpoints match linked POIs and boss',()=>{const points=new Map([...atlas.sites,...atlas.landmarks].map(p=>[p.id,p.center]));for(const route of atlas.routes){const a=points.get(route.from),b=points.get(route.to);assert.ok(a&&b);assert.deepEqual(route.controls[0],{x:a.x,z:a.z});assert.deepEqual(route.controls.at(-1),{x:b.x,z:b.z});assert.ok(route.samples.every(p=>[p.x,p.y,p.z,p.targetRoadY].every(Number.isFinite)));}});

test('scatter refuses unconfirmed masks',()=>{assert.throws(()=>generateScatter({chunkId:'lf_chunk_0_0',count:4,terrain:()=>({dry:true,y:0,slope:0})}),/INCOMPLETE_RESERVE_MASKS/);});

test('malformed or negative reserve mask never silently opens protected terrain',()=>{for(const mask of [{type:'circle',x:0,z:0,radius:-1},{type:'box',minX:NaN,maxX:1,minZ:0,maxZ:1}])assert.throws(()=>generateScatter({...maskProof,masks:[mask],chunkId:'lf_chunk_0_0',count:4,terrain:()=>({dry:true,y:0,slope:0})}),/INVALID_RESERVE_MASK/);});

test('same-login profiles cannot reveal fog for another selected settlement',async()=>{const f=createFogAuthority({resolveTraversal:async({authenticatedPlayerId})=>{assert.equal(authenticatedPlayerId,'settlement-B');return{...traversal,ownerId:'settlement-A'};}});await assert.rejects(f.reveal(createFogState(),command,{authenticatedPlayerId:'settlement-B',sessionUserId:'same-login',hallLevel:3}),/UNVERIFIED_TRAVERSAL/);});

function projectedAt(projection,x,z){const c=Math.floor((x+112)/4),r=Math.floor((z+112)/4),i=r*56+c,b=Buffer.from(projection.visibleTerrainBase64,'base64');return !!(b[i>>3]&(1<<(i&7)));}
test('hall1 hall2 missing invalid and client-forged levels deny exploration before traversal resolution',async()=>{
 let calls=0;const f=createFogAuthority({resolveTraversal:async()=>{calls++;return traversal;}}),s=createFogState();
 for(const hallLevel of [1,2,undefined,null,'3',3.5,NaN,Infinity,-1])await assert.rejects(f.reveal(s,command,{authenticatedPlayerId:'owner',hallLevel}),/FOREST_LOCKED_HALL_LEVEL/);
 await assert.rejects(f.reveal(s,{...command,hallLevel:3},undefined),/AUTH_REQUIRED/);
 await assert.rejects(f.reveal(s,{...command,hallLevel:3},{authenticatedPlayerId:'owner',hallLevel:2}),/FOREST_LOCKED_HALL_LEVEL/);
 await assert.rejects(f.reveal(s,{...command,hallLevel:3},auth),/INVALID_FOG_COMMAND/);
 assert.equal(calls,0);assert.equal(MIN_HALL_LEVEL,3);assert.equal(forestUnlocked(auth),true);
});
test('hall3 reveals via authoritative traversal; upgrading does not expose the entire map',async()=>{
 const f=createFogAuthority({resolveTraversal:async()=>traversal}),s=createFogState();
 const projected=projectFogForClient(s,auth,{pois:[{id:'horse',x:-8,z:-55},{id:'boss',x:75,z:-86}]});
 assert.equal(projected.explorationLocked,false);assert.deepEqual(projected.visiblePoiIds,['horse']);
 assert.equal(projectedAt(projected,-12,-60),true);assert.equal(projectedAt(projected,75,-86),false);
 assert.equal(projected.boundaryFog.entranceTransitionMs,1200);
 const next=await f.reveal(s,command,auth);assert.ok(exploredCellCount(next)>exploredCellCount(s));
});
test('locked projection masks legacy progress and all POIs while preserving town and saved bytes',async()=>{
 const f=createFogAuthority({resolveTraversal:async()=>traversal}),legacy=await f.reveal(createFogState(),command,auth),before=JSON.stringify(legacy);
 assert.equal(isExplored(legacy,-14,-66),true);
 for(const hallLevel of [1,2,undefined,'3']){const locked=projectFogForClient(legacy,{authenticatedPlayerId:'owner',hallLevel},{pois:[{id:'horse',x:-8,z:-55},{id:'legacy',x:-14,z:-66}]});assert.equal(locked.explorationLocked,true);assert.deepEqual(locked.visiblePoiIds,[]);assert.equal(projectedAt(locked,0,0),true);assert.equal(projectedAt(locked,-14,-66),false);assert.equal(locked.boundaryFog.coverage,'entire outer forest');}
 assert.equal(JSON.stringify(legacy),before);
 const unlocked=projectFogForClient(legacy,auth,{pois:[{id:'legacy',x:-14,z:-66}]});assert.equal(projectedAt(unlocked,-14,-66),true);assert.deepEqual(unlocked.visiblePoiIds,['legacy']);assert.equal(JSON.stringify(legacy),before);
});
test('camera and old mask cannot bypass hall gate; unauthenticated projection denied',async()=>{
 const f=createFogAuthority({resolveTraversal:async()=>traversal}),legacy=await f.reveal(createFogState(),command,auth),before=JSON.stringify(legacy);
 await assert.rejects(f.reveal(legacy,command,{authenticatedPlayerId:'owner',hallLevel:2,camera:{x:75,z:-86},exploredBase64:legacy.exploredBase64}),/FOREST_LOCKED_HALL_LEVEL/);
 assert.throws(()=>projectFogForClient(legacy,{hallLevel:3}),/AUTH_REQUIRED/);assert.equal(JSON.stringify(legacy),before);
});

test('protected town property outside the default core stays visible while forest remains locked',()=>{const s=createFogState(),p=projectFogForClient(s,{authenticatedPlayerId:'owner',hallLevel:2},{protectedTownCells:[{x:-58,z:0}],pois:[{id:'hidden-forest',x:-58,z:0}]});assert.equal(projectedAt(p,-58,0),true);assert.equal(projectedAt(p,-70,0),false);assert.deepEqual(p.visiblePoiIds,[]);assert.equal(isExplored(s,-58,0),false);});

test('atlas gate and entrance match shared code constants',()=>{assert.equal(atlas.fog.minimumHallLevel,MIN_HALL_LEVEL);assert.deepEqual(atlas.fog.entranceCorridor,ENTRANCE_CORRIDOR);assert.equal(atlas.fog.projectionFunction,'projectFogForClient');});
