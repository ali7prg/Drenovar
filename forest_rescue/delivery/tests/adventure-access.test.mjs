import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {MIN_HALL_LEVEL,ACCESS_CAMPAIGN_ID,initialIntroState,loadIntroState,projectAdventureAccess,reconcileIntroOnEntry,reduceIntro} from '../code/adventure-access.mjs';
import {CAMPAIGN_ID,initialState,reduceCampaign} from '../code/forest-rescue.mjs';
import {createReferenceSnapshot,executeReferenceCommand} from '../code/reference-transaction.mjs';
import {refillAfterVerifiedSpend} from '../code/reserve-refill.mjs';
import {migrateIntroForExistingCampaign} from '../code/intro-migration.mjs';
import {owner,context,evidence,envelope,play,allActions,bag} from './fixtures.mjs';
const safe={...context,hallLevel:3,cityForeground:true,uiReady:true,activeCombat:false,modalOpen:false,loading:false,reducedMotion:false};
const introBody=action=>{const {type,...rest}=action;return {kind:'adventure_intro',campaignId:CAMPAIGN_ID,action:type,...rest};};
const callIntro=(snapshot,action,key='intro-command-1',ctx=safe)=>executeReferenceCommand(snapshot,ctx,{key,body:introBody(action)});

test('Hall1 and2 block every campaign command despite valid proofs and preserve old progress/funds',()=>{
  assert.equal(MIN_HALL_LEVEL,3);assert.equal(ACCESS_CAMPAIGN_ID,CAMPAIGN_ID);
  const completed=play().state;
  const actions=[{type:'discover_horse'},allActions[1],{type:'begin_boss'},{type:'finish_boss'},{type:'claim_rewards'},{type:'pause'},{type:'resume'}];
  for(const hallLevel of [1,2])for(const action of actions){
    const before=JSON.stringify(completed);
    assert.throws(()=>reduceCampaign(completed,action,{...evidence(action),hallLevel}),e=>e.code==='HALL_REQUIRED');
    assert.equal(JSON.stringify(completed),before);
  }
  let snapshot=createReferenceSnapshot(owner);snapshot.players[0].campaign=completed;
  const before=JSON.stringify(snapshot);
  assert.throws(()=>executeReferenceCommand(snapshot,{...safe,hallLevel:2},{key:'locked-reward-claim',body:envelope({type:'claim_rewards'})}),e=>e.code==='HALL_REQUIRED');
  assert.equal(JSON.stringify(snapshot),before);
});
test('Hall3 unlocks horse and first site; undefined, forged and invalid hall authority fail closed',()=>{
  const horse=reduceCampaign(initialState(),allActions[0],{...evidence(allActions[0]),hallLevel:3});assert.equal(horse.state.phase,'rescue');
  assert.equal(reduceCampaign(horse.state,allActions[1],{...evidence(allActions[1]),hallLevel:3}).state.sites.lf_site_01.step,1);
  for(const hallLevel of [undefined,null,'3',NaN,Infinity,3.5,-1,Number.MAX_SAFE_INTEGER+1]){
    assert.throws(()=>reduceCampaign(initialState(),allActions[0],{...evidence(allActions[0]),hallLevel}),e=>e.code==='INVALID_HALL_LEVEL');
  }
  const snapshot=createReferenceSnapshot(owner);
  assert.throws(()=>executeReferenceCommand(snapshot,safe,{key:'forged-level-claim',body:{...envelope(allActions[0]),hallLevel:99}}),e=>e.code==='INVALID_ACTION');
  assert.throws(()=>executeReferenceCommand(snapshot,{...safe,hallLevel:2},{key:'forged-level-claim',body:{...envelope(allActions[0]),hallLevel:99}}),e=>e.code==='HALL_REQUIRED');
});
test('Locked read projection preserves saved intro bytes; hall3 completion or existing hall5 suggests safe first autoplay',()=>{
  const fresh=initialIntroState(),before=JSON.stringify(fresh);
  for(const hallLevel of [1,2]){
    const view=projectAdventureAccess(fresh,{...safe,hallLevel});assert.equal(view.unlocked,false);assert.equal(view.autoStartEligible,false);assert.equal(view.invitationAvailable,false);
  }
  for(const hallLevel of [3,5]){const view=projectAdventureAccess(fresh,{...safe,hallLevel});assert.equal(view.autoStartEligible,true);assert.equal(view.campaignAccessible,true);}
  assert.equal(JSON.stringify(fresh),before);
});
test('Initial playback waits for safe foreground city, no combat/modal/loading, then starts once',()=>{
  const fresh=initialIntroState();
  for(const patch of [{cityForeground:false},{uiReady:false},{activeCombat:true},{modalOpen:true},{loading:true},{activeCombat:undefined}]){
    const ctx={...safe,...patch};assert.equal(projectAdventureAccess(fresh,ctx).autoStartEligible,false);
    assert.throws(()=>reduceIntro(fresh,{type:'start_intro'},ctx),e=>e.code==='INTRO_NOT_SAFE');
  }
  const start=reduceIntro(fresh,{type:'start_intro'},safe);assert.equal(start.state.status,'playing');assert.equal(start.state.attempts,1);
  assert.deepEqual(start.effects,[{type:'present_intro',attempt:1,mode:'animated'}]);
  const repeat=reduceIntro(start.state,{type:'start_intro'},safe);assert.equal(repeat.changed,false);assert.deepEqual(repeat.effects,[]);
});
test('Finish and skip are durable idempotent server acknowledgments with no campaign awards',()=>{
  for(const skipBeforeStart of [true,false]){
    let snapshot=createReferenceSnapshot(owner),original=JSON.stringify(snapshot.players[0].campaign);
    if(!skipBeforeStart)snapshot=callIntro(snapshot,{type:'start_intro'}).snapshot;
    const action=skipBeforeStart?{type:'skip_intro'}:{type:'finish_intro',attempt:1};
    const result=callIntro(snapshot,action,'intro-ack-key');snapshot=result.snapshot;
    assert.equal(snapshot.players[0].intro.status,'acknowledged');assert.equal(JSON.stringify(snapshot.players[0].campaign),original);assert.deepEqual(snapshot.players[0].wallet,bag(0));
    assert.deepEqual(result.response.effects,[]);
    const retry=callIntro(snapshot,action,'intro-ack-key');assert.equal(retry.response.duplicate,true);assert.deepEqual(retry.response.effects,[]);
    const newer=callIntro(snapshot,action,'intro-ack-new-key');assert.equal(newer.response.intro.acknowledgment,skipBeforeStart?'skipped':'finished');
    const entry=reconcileIntroOnEntry(newer.response.intro,safe);assert.equal(entry.changed,false);assert.equal(projectAdventureAccess(entry.state,safe).autoStartEligible,false);
    assert.deepEqual(callIntro(snapshot,{type:'start_intro'},'no-replay-intro').response.effects,[]);
  }
});
test('Interruption/defer returns a manual invitation and never repeats full autoplay on every login',()=>{
  const playing=reduceIntro(initialIntroState(),{type:'start_intro'},safe).state;
  const interrupted=reconcileIntroOnEntry(JSON.parse(JSON.stringify(playing)),safe);assert.equal(interrupted.state.status,'pending');assert.equal(interrupted.state.deferred,true);
  const view=projectAdventureAccess(interrupted.state,safe);assert.equal(view.autoStartEligible,false);assert.equal(view.continueRequired,true);assert.equal(view.canStartNow,true);
  const entryAgain=reconcileIntroOnEntry(interrupted.state,safe);assert.equal(entryAgain.changed,false);
  assert.throws(()=>reduceIntro(interrupted.state,{type:'finish_intro',attempt:1},safe),e=>e.code==='STALE_INTRO_ATTEMPT');
  const resumed=reduceIntro(interrupted.state,{type:'start_intro'},safe);assert.equal(resumed.state.attempts,2);
  assert.throws(()=>reduceIntro(resumed.state,{type:'finish_intro',attempt:1},safe),e=>e.code==='STALE_INTRO_ATTEMPT');
  const deferred=reduceIntro(initialIntroState(),{type:'defer_intro'},safe);assert.equal(projectAdventureAccess(deferred.state,safe).autoStartEligible,false);
});
test('Reduced motion presents static cards and a lost skip callback never locks real progression',()=>{
  const start=reduceIntro(initialIntroState(),{type:'start_intro'},{...safe,reducedMotion:true});assert.equal(start.effects[0].mode,'static_cards');
  let snapshot=createReferenceSnapshot(owner);snapshot=callIntro(snapshot,{type:'start_intro'}).snapshot;
  // User may progress after a lost presentation callback; intro is never a reward prerequisite.
  const horse=executeReferenceCommand(snapshot,{...evidence(allActions[0]),hallLevel:3},{key:'horse-after-lost-skip',body:envelope(allActions[0])});
  assert.equal(horse.response.state.phase,'rescue');assert.equal(horse.response.intro.status,'playing');
  const skip=callIntro(horse.snapshot,{type:'skip_intro'},'recover-skip-ack');assert.equal(skip.response.intro.status,'acknowledged');assert.deepEqual(skip.response.state.escrow,horse.response.state.escrow);
});
test('Intro profiles and receipt conflicts remain isolated; arbitrary ack flags rejected',()=>{
  let snapshot=createReferenceSnapshot(owner);snapshot.players.push(createReferenceSnapshot('settlement-B').players[0]);
  snapshot=callIntro(snapshot,{type:'skip_intro'}).snapshot;
  assert.equal(snapshot.players[0].intro.status,'acknowledged');assert.equal(snapshot.players[1].intro.status,'pending');
  const other=callIntro(snapshot,{type:'start_intro'},'intro-command-1',{...safe,authenticatedPlayerId:'settlement-B'});assert.equal(other.response.intro.status,'playing');
  assert.throws(()=>callIntro(snapshot,{type:'start_intro'},'intro-command-1'),e=>e.code==='IDEMPOTENCY_CONFLICT');
  for(const extra of [{acknowledged:true},{state:{status:'acknowledged'}},{hallLevel:9},{reward:1000}])assert.throws(()=>callIntro(snapshot,{type:'skip_intro',...extra},'bad-intro-key'));
  assert.throws(()=>callIntro(snapshot,{type:'skip_intro'},'locked-intro-key',{...safe,hallLevel:2}),e=>e.code==='HALL_REQUIRED');
});
test('Intro absent migration is explicit and corrupt/versioned saved acknowledgments are preserved by rejection',()=>{
  assert.deepEqual(loadIntroState(undefined),initialIntroState());
  for(const state of [null,{...initialIntroState(),schemaVersion:2},{...initialIntroState(),status:'acknowledged'},{...initialIntroState(),status:'playing'},{...initialIntroState(),acknowledgment:'finished'}])assert.throws(()=>loadIntroState(state));
});
test('Low-level reserve auto-refill stays locked without undoing unrelated valid spending',()=>{
  const state=play().state;
  const result=refillAfterVerifiedSpend(state,{authenticatedPlayerId:owner,hallLevel:2,optedIn:true,beforeWallet:bag(2000),afterWallet:bag(1000),capacity:bag(2000)});
  assert.equal(result.changed,false);assert.deepEqual(result.state,state);assert.deepEqual(result.wallet,bag(1000));assert.deepEqual(result.effects,[]);
});
test('Existing progressed campaign without intro namespace migrates to acknowledged without replay or rewards',()=>{
  const campaign=play(allActions.slice(0,3)).state,bytes=JSON.stringify(campaign);
  const migration=migrateIntroForExistingCampaign(undefined,campaign);
  assert.equal(migration.migrated,true);assert.equal(migration.state.status,'acknowledged');assert.equal(migration.state.acknowledgment,'existing_progress');
  assert.equal(projectAdventureAccess(migration.state,{...safe,hallLevel:5}).autoStartEligible,false);assert.equal(JSON.stringify(campaign),bytes);
  const fresh=migrateIntroForExistingCampaign(undefined,undefined);assert.equal(fresh.migrated,false);assert.equal(projectAdventureAccess(fresh.state,safe).autoStartEligible,true);
  const explicit=initialIntroState(),kept=migrateIntroForExistingCampaign(explicit,campaign);assert.deepEqual(kept.state,explicit);assert.equal(kept.migrated,false);
  let snapshot=createReferenceSnapshot(owner);snapshot.players[0].campaign=campaign;delete snapshot.players[0].intro;
  const result=callIntro(snapshot,{type:'start_intro'});assert.equal(result.response.intro.acknowledgment,'existing_progress');assert.deepEqual(result.response.effects,[]);assert.equal(JSON.stringify(result.response.state),bytes);
});
test('Persisted command receipts cannot bypass the new hall gate; higher guardian gates stay at hall5',()=>{
  const request={key:'horse-existing-receipt',body:envelope(allActions[0])};
  const committed=executeReferenceCommand(createReferenceSnapshot(owner),{...evidence(allActions[0]),hallLevel:3},request).snapshot;
  assert.throws(()=>executeReferenceCommand(committed,{...evidence(allActions[0]),hallLevel:2},request),e=>e.code==='HALL_REQUIRED');
  // First six sites rescued; site7 discovered and artifact recovered. Guardian III still needs V.
  const beforeBattle=play(allActions.slice(0,33)).state,action=allActions[33];
  assert.equal(action.siteId,'lf_site_07');assert.equal(action.taskId,'defeat_guardian');
  for(const hallLevel of [3,4])assert.throws(()=>reduceCampaign(beforeBattle,action,{...evidence(action),hallLevel}),e=>e.code==='HALL_REQUIRED');
  assert.equal(reduceCampaign(beforeBattle,action,{...evidence(action),hallLevel:5}).state.sites.lf_site_07.step,3);
});
test('Competing intro starts publish only the winning committed effect; CAS rebase does not start another playback',()=>{
  const before=createReferenceSnapshot(owner),a=callIntro(before,{type:'start_intro'},'intro-tab-A'),b=callIntro(before,{type:'start_intro'},'intro-tab-B');
  assert.deepEqual(a.response.effects,b.response.effects);assert.equal(before.players[0].intro.attempts,0);
  // Only A's snapshot/effect is published. B discards its speculative effect and rebases.
  const rebased=callIntro(a.snapshot,{type:'start_intro'},'intro-tab-B');
  assert.deepEqual(rebased.response.effects,[]);assert.equal(rebased.response.intro.attempts,1);
});
test('Authored unlock and intro timeline agree with the executable access contract',()=>{
  const data=JSON.parse(fs.readFileSync(new URL('../data/unlock-intro.json',import.meta.url),'utf8'));
  assert.equal(data.campaignId,CAMPAIGN_ID);assert.equal(data.minimumHallLevel,MIN_HALL_LEVEL);assert.equal(data.requiresCompletedHallUpgrade,true);
  assert.equal(data.unlock.blockCampaignUntilIntroAcknowledged,false);assert.equal(data.unlock.rewardForWatchingOrSkipping,false);assert.equal(data.unlock.skipAllowed,true);
  assert.equal(data.locked.allowQuestCommands,false);assert.equal(data.locked.allowCampaignRewardClaims,false);
  let cursor=0;for(const shot of data.presentation.shots){assert.equal(shot.start,cursor);assert.ok(shot.end>shot.start);assert.ok(Object.hasOwn(data.texts,shot.textKey));cursor=shot.end;}
  assert.equal(cursor,data.presentation.durationSeconds);assert.equal(data.presentation.cameraRestoredAfter,data.presentation.durationSeconds);
});
