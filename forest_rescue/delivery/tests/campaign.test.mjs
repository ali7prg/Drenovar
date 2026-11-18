import test from 'node:test';
import assert from 'node:assert/strict';
import {initialState,loadState,validateState,reduceCampaign,campaignMaximumReward,RESOURCES,SITE_IDS,TASKS,BOSS_ID,artifactId,captiveIds} from '../code/forest-rescue.mjs';
import {createReferenceSnapshot,executeReferenceCommand} from '../code/reference-transaction.mjs';
import {owner,bag,context,envelope,evidence,allActions,play} from './fixtures.mjs';
const code=expected=>e=>e.code===expected;
function transact(actions=allActions){let s=createReferenceSnapshot(owner);for(const [i,a]of actions.entries())s=executeReferenceCommand(s,evidence(a),{key:'command-'+String(i).padStart(5,'0'),body:envelope(a)}).snapshot;return s;}

test('Complete 60-task campaign rescues 36 people and awards exact requested resource total',()=>{
  const {state,effects}=play();assert.equal(state.phase,'completed');assert.equal(state.rescuedIds.length,36);
  assert.equal(new Set(state.rescuedIds).size,36);assert.equal(state.usedBattleProofs.length,13);
  assert.deepEqual(state.escrow.earned,{food:2325000,wood:2385000,stone:1590000,iron:1025000,coins:190000});
  assert.deepEqual(state.escrow.earned,campaignMaximumReward());assert.deepEqual(state.escrow.pending,state.escrow.earned);
  assert.deepEqual(state.escrow.claimed,bag(0));
  const awards=effects.filter(e=>e.type==='reward_escrowed');assert.equal(awards.length,62);assert.equal(new Set(awards.map(e=>e.awardId)).size,62);
  assert.equal(effects.filter(e=>e.type==='task_completed').length,60);
});
test('Every save checkpoint round-trips and reaches identical final result',()=>{
  const expected=play().state;let state=initialState();
  for(let i=0;i<=allActions.length;i++){
    let restored=loadState(JSON.parse(JSON.stringify(state)));
    for(const a of allActions.slice(i))restored=reduceCampaign(restored,a,evidence(a)).state;
    assert.deepEqual(restored,expected);
    if(i<allActions.length)state=reduceCampaign(state,allActions[i],evidence(allActions[i])).state;
  }
});
test('Horse, ordered tasks, act gates, and final boss gate are mandatory',()=>{
  const first={type:'attempt_task',siteId:SITE_IDS[0],taskId:'discover'};
  assert.throws(()=>reduceCampaign(initialState(),first,evidence(first)),code('HORSE_REQUIRED'));
  const state=play(allActions.slice(0,1)).state;
  assert.throws(()=>reduceCampaign(state,{...first,taskId:'unlock_cage'},context),code('TASK_ORDER'));
  const late={...first,siteId:SITE_IDS[3]};assert.throws(()=>reduceCampaign(state,late,evidence(late)),code('PREVIOUS_ACT_REQUIRED'));
  assert.throws(()=>reduceCampaign(state,{type:'begin_boss'},evidence({type:'begin_boss'})),code('ALL_RESCUES_REQUIRED'));
  assert.throws(()=>reduceCampaign(state,{type:'finish_boss'},evidence({type:'finish_boss'})),code('BOSS_NOT_ACTIVE'));
});
test('Sites are free-order inside an act; fourth act has reward multiplier not fictional level4',()=>{
  const order=[...SITE_IDS.slice(0,3).reverse(),...SITE_IDS.slice(3)];
  const actions=[allActions[0],...order.flatMap(siteId=>TASKS.map(taskId=>({type:'attempt_task',siteId,taskId}))),{type:'begin_boss'},{type:'finish_boss'}];
  assert.deepEqual(play(actions).state.escrow,play().state.escrow);
  assert.deepEqual(play(actions).state.rescuedIds,play().state.rescuedIds);
  const last=evidence({type:'attempt_task',siteId:SITE_IDS[11],taskId:'defeat_guardian'}).battleProof;
  assert.equal(last.level,3);assert.equal(last.species,'dragor');assert.equal(last.modifier,'ancient_watch');
});
test('Artifact is found before battle but cannot open cage before victory, be spent twice or used elsewhere',()=>{
  let state=play(allActions.slice(0,2)).state;
  const collect={type:'attempt_task',siteId:SITE_IDS[0],taskId:'recover_artifact'};
  state=reduceCampaign(state,collect,evidence(collect)).state;
  assert.equal(state.sites[SITE_IDS[0]].artifact,1);assert.equal(state.usedBattleProofs.length,0);
  assert.throws(()=>reduceCampaign(state,{...collect,taskId:'unlock_cage'},evidence({...collect,taskId:'unlock_cage'})),code('TASK_ORDER'));
  state=play(allActions.slice(0,4)).state;assert.equal(state.sites[SITE_IDS[0]].artifact,1);
  const unlock={type:'attempt_task',siteId:SITE_IDS[0],taskId:'unlock_cage'};
  assert.throws(()=>reduceCampaign(state,unlock,{...evidence(unlock),arrival:{...evidence(unlock).arrival,targetId:SITE_IDS[1]+':cage'}}),code('UNVERIFIED_ARRIVAL'));
  const once=reduceCampaign(state,unlock,evidence(unlock));assert.equal(once.state.sites[SITE_IDS[0]].artifact,0);
  const twice=reduceCampaign(once.state,unlock,context);assert.equal(twice.changed,false);assert.deepEqual(twice.effects,[]);
  const recollect=reduceCampaign(once.state,collect,context);assert.equal(recollect.state.sites[SITE_IDS[0]].artifact,0);assert.deepEqual(recollect.effects,[]);
});
test('Battle proof must be finalized victorious, owner-bound, correctly typed and encounter-bound',()=>{
  const state=play(allActions.slice(0,3)).state,action=allActions[3],ctx=evidence(action);
  for(const patch of [{outcome:'defeat'},{finalized:false},{serverVerified:false},{ownerId:'other'},{siteId:SITE_IDS[1]},{species:'dragor'},{level:3},{encounterId:'unrelated-battle'}]){
    assert.throws(()=>reduceCampaign(state,action,{...ctx,battleProof:{...ctx.battleProof,...patch}}),code('UNVERIFIED_BATTLE'));
  }
  assert.throws(()=>reduceCampaign(state,action,{...ctx,hallLevel:0}),code('HALL_REQUIRED'));
  assert.throws(()=>reduceCampaign(state,action,context),code('UNVERIFIED_BATTLE'));
});
test('Same finalized report cannot authorize another guardian',()=>{
  let state=play(allActions.slice(0,6)).state;
  const discover={type:'attempt_task',siteId:SITE_IDS[1],taskId:'discover'};state=reduceCampaign(state,discover,evidence(discover)).state;
  const collect={...discover,taskId:'recover_artifact'};state=reduceCampaign(state,collect,evidence(collect)).state;
  const battle={...discover,taskId:'defeat_guardian'},ctx=evidence(battle);ctx.battleProof.reportId='battle-'+SITE_IDS[0];
  assert.throws(()=>reduceCampaign(state,battle,ctx),code('BATTLE_PROOF_REUSED'));
});
test('Arrival and escort require server route and all three matching captives',()=>{
  assert.throws(()=>reduceCampaign(initialState(),{type:'discover_horse'},context),code('UNVERIFIED_ARRIVAL'));
  const horse=evidence(allActions[0]);horse.arrival.routeValid=false;
  assert.throws(()=>reduceCampaign(initialState(),allActions[0],horse),code('UNVERIFIED_ARRIVAL'));
  const state=play(allActions.slice(0,5)).state,escort=allActions[5],ctx=evidence(escort);
  for(const patch of [{arrivedHome:false},{serverVerified:false},{captiveIds:captiveIds(SITE_IDS[1])},{captiveIds:[...captiveIds(SITE_IDS[0]).slice(0,2)]},{ownerId:'other'}]){
    assert.throws(()=>reduceCampaign(state,escort,{...ctx,escortProof:{...ctx.escortProof,...patch}}),code('UNVERIFIED_ESCORT'));
  }
});
test('Pause/resume, reload, cancelled presentation and arbitrary wall-clock passage lose no quest progress',()=>{
  const before=play(allActions.slice(0,4)).state;
  const paused=reduceCampaign(before,{type:'pause'},context).state;
  assert.throws(()=>reduceCampaign(paused,allActions[4],evidence(allActions[4])),code('CAMPAIGN_PAUSED'));
  const restored=loadState(JSON.parse(JSON.stringify(paused)));
  const resumed=reduceCampaign(restored,{type:'resume'},context).state;
  assert.deepEqual(resumed.sites,before.sites);assert.deepEqual(resumed.escrow,before.escrow);
  assert.deepEqual(reduceCampaign(resumed,allActions[4],evidence(allActions[4])).state.sites[SITE_IDS[0]],{step:4,artifact:0});
});
test('Partial claims respect each capacity and preserve every unclaimed unit, including over-cap wallets',()=>{
  let state=play(allActions.slice(0,1)).state;
  const ctx={...context,wallet:{food:1900,wood:2500,stone:0,iron:0,coins:0}};
  const claim=reduceCampaign(state,{type:'claim_rewards'},ctx);
  assert.deepEqual(claim.effects[0].resources,{food:100,wood:0,stone:0,iron:0,coins:0});
  assert.equal(claim.state.escrow.pending.food,4900);assert.equal(claim.state.escrow.pending.wood,5000);
  for(const r of RESOURCES)assert.equal(claim.state.escrow.pending[r]+claim.state.escrow.claimed[r],state.escrow.earned[r]);
  const full=reduceCampaign(claim.state,{type:'claim_rewards'},{...context,wallet:bag(2000)});
  assert.equal(full.changed,false);assert.deepEqual(full.effects[0].resources,bag(0));
});
test('Claimed escrow plus wallet changes commit atomically, concurrent claims are safe on rebase',()=>{
  const before=transact(allActions.slice(0,1)),req={key:'claim-concurrent',body:envelope({type:'claim_rewards'})};
  const candidateA=executeReferenceCommand(before,context,req),candidateB=executeReferenceCommand(before,context,req);
  assert.deepEqual(before.players[0].wallet,bag(0));assert.deepEqual(candidateA.snapshot,candidateB.snapshot);
  const committed=candidateA.snapshot;
  const rebased=executeReferenceCommand(committed,context,req);assert.equal(rebased.response.duplicate,true);
  assert.deepEqual(rebased.response.wallet,{food:2000,wood:2000,stone:0,iron:0,coins:0});
  assert.equal(rebased.response.state.escrow.pending.food,3000);
  const secondKey=executeReferenceCommand(committed,context,{...req,key:'claim-second-key'});
  assert.deepEqual(secondKey.response.wallet,rebased.response.wallet);assert.equal(secondKey.response.state.escrow.pending.food,3000);
});
test('Spending then claiming remaining escrow transfers exact remainder without expiring rewards',()=>{
  let snapshot=transact(allActions.slice(0,1));
  for(let i=0;i<3;i++){
    snapshot=executeReferenceCommand(snapshot,context,{key:'claim-batch-'+i,body:envelope({type:'claim_rewards'})}).snapshot;
    if(i<2){snapshot.players[0].wallet.food=0;snapshot.players[0].wallet.wood=0;} // Trusted unrelated spend.
  }
  assert.equal(snapshot.players[0].campaign.escrow.pending.food,0);assert.equal(snapshot.players[0].campaign.escrow.claimed.food,5000);
  assert.equal(snapshot.players[0].wallet.food,1000);
});
test('Retries, receipt eviction and fresh keys cannot repeat task or final reward',()=>{
  let snapshot=transact();const final={key:'fresh-final-key',body:envelope({type:'finish_boss'})};snapshot.receipts=[];
  const result=executeReferenceCommand(snapshot,context,final);assert.deepEqual(result.response.effects,[]);
  assert.deepEqual(result.response.state.escrow.earned,campaignMaximumReward());
  const replay=executeReferenceCommand(result.snapshot,context,final);assert.equal(replay.response.duplicate,true);
  assert.throws(()=>executeReferenceCommand(result.snapshot,context,{...final,body:envelope({type:'claim_rewards'})}),code('IDEMPOTENCY_CONFLICT'));
  const oldTask=executeReferenceCommand(result.snapshot,context,{key:'old-task-new-key',body:envelope(allActions[3])});
  assert.deepEqual(oldTask.response.effects,[]);assert.equal(oldTask.response.state.sites[SITE_IDS[0]].artifact,0);
});
test('Profiles isolate wallets, quest progression and receipt namespaces',()=>{
  let snapshot=createReferenceSnapshot(owner);snapshot.players.push(createReferenceSnapshot('settlement-B').players[0]);
  const req={key:'shared-idempotency-key',body:envelope(allActions[0])};
  snapshot=executeReferenceCommand(snapshot,evidence(allActions[0]),req).snapshot;
  assert.equal(snapshot.players[1].campaign.phase,'prologue');
  snapshot=executeReferenceCommand(snapshot,evidence(allActions[0],'settlement-B'),req).snapshot;
  assert.equal(snapshot.receipts.length,2);assert.deepEqual(snapshot.players[1].wallet,bag(0));
  assert.throws(()=>executeReferenceCommand(snapshot,{...context,authenticatedPlayerId:'unknown'},req),code('UNKNOWN_PLAYER'));
});
test('Malformed requests cannot inject state, reward, victory, owner, wallet or client clock',()=>{
  const snapshot=createReferenceSnapshot(owner);
  for(const extra of [{state:{phase:'completed'}},{reward:999999},{battleProof:{outcome:'victory'}},{evidence:{}},{playerId:'settlement-B'},{wallet:bag(0)},{now:0},{amount:1000},{type:'finish_boss'}]){
    assert.throws(()=>executeReferenceCommand(snapshot,evidence(allActions[0]),{key:'malformed-req',body:{...envelope(allActions[0]),...extra}}));
  }
  assert.throws(()=>executeReferenceCommand(snapshot,{}, {key:'valid-key-1',body:envelope(allActions[0])}),code('UNAUTHENTICATED'));
  assert.throws(()=>executeReferenceCommand(snapshot,evidence(allActions[0]),{key:'x',body:envelope(allActions[0])}),code('INVALID_KEY'));
});
test('Absent save migration is explicit; corrupt, unknown-version or inflated states fail closed',()=>{
  assert.deepEqual(loadState(undefined),initialState());assert.throws(()=>loadState(null));
  for(const version of [0,2])assert.throws(()=>loadState({...initialState(),schemaVersion:version}),code('UNSUPPORTED_SCHEMA'));
  const saved=play(allActions.slice(0,4)).state;
  for(const mutate of [s=>s.sites[SITE_IDS[0]].artifact=2,s=>s.escrow.pending.food++,s=>s.escrow.earned.food++,s=>s.rescuedIds.push('invented'),s=>s.usedBattleProofs=[],s=>s.phase='completed']){
    const damaged=structuredClone(saved);mutate(damaged);assert.throws(()=>validateState(damaged));
  }
});
test('Nonfinite, negative and unsafe-number capacities reject without mutating a snapshot',()=>{
  const before=transact(allActions.slice(0,1)),original=JSON.stringify(before),request={key:'claim-invalid-cap',body:envelope({type:'claim_rewards'})};
  for(const bad of [-1,Infinity,NaN,Number.MAX_SAFE_INTEGER+1,1.5])assert.throws(()=>executeReferenceCommand(before,{...context,capacity:{...bag(2000),food:bad}},request));
  assert.equal(JSON.stringify(before),original);
});
test('New dinosaur victory is distinct from Tenerys and requires hall5 before starting',()=>{
  const unlocked=play(allActions.slice(0,-2)).state;assert.equal(unlocked.phase,'boss_unlocked');
  assert.throws(()=>reduceCampaign(unlocked,{type:'begin_boss'},{...evidence({type:'begin_boss'}),hallLevel:4}),code('HALL_REQUIRED'));
  const active=reduceCampaign(unlocked,{type:'begin_boss'},evidence({type:'begin_boss'})).state;
  for(const hallLevel of [3,4])assert.throws(()=>reduceCampaign(active,{type:'finish_boss'},{...evidence({type:'finish_boss'}),hallLevel}),code('HALL_REQUIRED'));
  const ctx=evidence({type:'finish_boss'});ctx.battleProof.species='tenerys';
  assert.throws(()=>reduceCampaign(active,{type:'finish_boss'},ctx),code('UNVERIFIED_BATTLE'));
  assert.equal(active.rescuedIds.length,36);assert.equal(active.usedBattleProofs.some(p=>p.siteId===BOSS_ID),false);
});
