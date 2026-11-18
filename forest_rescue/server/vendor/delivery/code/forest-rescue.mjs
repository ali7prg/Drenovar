/** Authored, tested reference domain logic. Not installed in DRENOVAR. */
import {assertAdventureAccess} from './adventure-access.mjs';
export const CAMPAIGN_ID='forest_rescue_v1';
export const SCHEMA_VERSION=1;
export const RESOURCES=Object.freeze(['food','wood','stone','iron','coins']);
export const TASKS=Object.freeze(['discover','recover_artifact','defeat_guardian','unlock_cage','escort_home']);
export const SITE_IDS=Object.freeze(Array.from({length:12},(_,i)=>'lf_site_'+String(i+1).padStart(2,'0')));
export const BOSS_ID='lf_boss_ancient_maw';
export const HORSE_ID='lf_horse_origin';
export const BOSS_SPECIES='ancient_maw';
export const GUARDIANS=Object.freeze([
  ['tenerys',1],['tenerys',1],['tenerys',1],['tenerys',2],['velkor',2],['kamneklyk',2],
  ['tenerys',3],['velkor',3],['kamneklyk',3],['dragor',2],['dragor',3],['dragor',3]
]);
export const TASK_REWARDS=Object.freeze({
  discover:{food:2000,wood:2000,stone:1000,iron:500,coins:100},
  defeat_guardian:{food:10000,wood:8000,stone:5000,iron:2000,coins:500},
  recover_artifact:{food:4000,wood:6000,stone:4000,iron:3000,coins:300},
  unlock_cage:{food:8000,wood:10000,stone:6000,iron:4000,coins:700},
  escort_home:{food:20000,wood:20000,stone:12000,iron:8000,coins:1400}
});
export const PROLOGUE_REWARD=Object.freeze({food:5000,wood:5000,stone:0,iron:0,coins:0});
export const FINAL_REWARD=Object.freeze({food:1000000,wood:1000000,stone:750000,iron:500000,coins:100000});
const phases=['prologue','rescue','boss_unlocked','boss_active','completed'];
const stateKeys=['schemaVersion','campaignId','phase','paused','revision','sites','rescuedIds','usedBattleProofs','escrow'];
const fail=code=>{const error=new Error(code);error.code=code;throw error;};
const zero=()=>Object.fromEntries(RESOURCES.map(r=>[r,0]));
const clone=structuredClone;
function exactKeys(value,keys,code='INVALID_STATE'){
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k)))fail(code);
}
function integer(value){return Number.isSafeInteger(value)&&value>=0;}
function resourceBag(value){exactKeys(value,RESOURCES);if(RESOURCES.some(r=>!integer(value[r])))fail('INVALID_RESOURCE_BAG');}
function add(a,b){for(const r of RESOURCES){const n=a[r]+b[r];if(!integer(n))fail('RESOURCE_OVERFLOW');a[r]=n;}return a;}
export function siteNumber(siteId){const n=SITE_IDS.indexOf(siteId)+1;if(!n)fail('UNKNOWN_SITE');return n;}
export function siteMultiplier(siteId){return Math.ceil(siteNumber(siteId)/3);}
export function guardianSpec(siteId){const n=siteNumber(siteId),[species,level]=GUARDIANS[n-1];return {species,level,modifier:n===12?'ancient_watch':null,requiredHall:[0,1,3,5][level]};}
export function artifactId(siteId){return 'lf_key_'+String(siteNumber(siteId)).padStart(2,'0');}
export function captiveIds(siteId){const n=String(siteNumber(siteId)).padStart(2,'0');return ['a','b','c'].map(s=>'lf_captive_'+n+'_'+s);}
export function taskReward(siteId,taskId){if(!TASKS.includes(taskId))fail('UNKNOWN_TASK');const multiplier=siteMultiplier(siteId);return Object.fromEntries(RESOURCES.map(r=>[r,TASK_REWARDS[taskId][r]*multiplier]));}
export function initialState(){return {schemaVersion:1,campaignId:CAMPAIGN_ID,phase:'prologue',paused:false,revision:0,sites:Object.fromEntries(SITE_IDS.map(id=>[id,{step:0,artifact:0}])),rescuedIds:[],usedBattleProofs:[],escrow:{earned:zero(),claimed:zero(),pending:zero()}};}
function expectedEarned(state){
  const result=zero();
  if(state.phase!=='prologue')add(result,PROLOGUE_REWARD);
  for(const siteId of SITE_IDS)for(let i=0;i<state.sites[siteId].step;i++)add(result,taskReward(siteId,TASKS[i]));
  if(state.phase==='completed')add(result,FINAL_REWARD);
  return result;
}
export function validateState(state){
  exactKeys(state,stateKeys);
  if(state.schemaVersion!==SCHEMA_VERSION)fail('UNSUPPORTED_SCHEMA');
  if(state.campaignId!==CAMPAIGN_ID||!phases.includes(state.phase)||typeof state.paused!=='boolean'||!integer(state.revision))fail('INVALID_STATE');
  exactKeys(state.sites,SITE_IDS);
  for(const siteId of SITE_IDS){
    const site=state.sites[siteId];exactKeys(site,['step','artifact']);
    if(!integer(site.step)||site.step>5||site.artifact!==([2,3].includes(site.step)?1:0))fail('INVALID_SITE_STATE');
    const groupStart=Math.floor((siteNumber(siteId)-1)/3)*3;
    if(site.step>0&&SITE_IDS.slice(0,groupStart).some(id=>state.sites[id]?.step!==5))fail('INVALID_ACT_GATE');
  }
  if(state.phase==='prologue'&&SITE_IDS.some(id=>state.sites[id].step!==0))fail('INVALID_PHASE');
  const allRescued=SITE_IDS.every(id=>state.sites[id].step===5);
  if(['boss_unlocked','boss_active','completed'].includes(state.phase)!==allRescued)fail('INVALID_BOSS_GATE');
  if(state.phase!=='prologue'&&state.revision===0)fail('INVALID_REVISION');
  const expectedRescued=SITE_IDS.filter(id=>state.sites[id].step===5).flatMap(captiveIds);
  if(!Array.isArray(state.rescuedIds)||JSON.stringify(state.rescuedIds)!==JSON.stringify(expectedRescued))fail('INVALID_RESCUE_LEDGER');
  if(!Array.isArray(state.usedBattleProofs))fail('INVALID_PROOF_LEDGER');
  const reportIds=new Set(),proofSites=new Set();
  for(const proof of state.usedBattleProofs){
    exactKeys(proof,['reportId','siteId']);
    if(typeof proof.reportId!=='string'||proof.reportId.length<1||proof.reportId.length>200||reportIds.has(proof.reportId)||proofSites.has(proof.siteId))fail('INVALID_PROOF_LEDGER');
    if(!SITE_IDS.includes(proof.siteId)&&proof.siteId!==BOSS_ID)fail('INVALID_PROOF_LEDGER');
    reportIds.add(proof.reportId);proofSites.add(proof.siteId);
  }
  for(const siteId of SITE_IDS)if(proofSites.has(siteId)!==(state.sites[siteId].step>=3))fail('INVALID_PROOF_LEDGER');
  if(proofSites.has(BOSS_ID)!==(state.phase==='completed'))fail('INVALID_PROOF_LEDGER');
  exactKeys(state.escrow,['earned','claimed','pending']);
  for(const bag of Object.values(state.escrow))resourceBag(bag);
  const expected=expectedEarned(state);
  for(const r of RESOURCES)if(state.escrow.earned[r]!==expected[r]||state.escrow.claimed[r]+state.escrow.pending[r]!==expected[r])fail('INVALID_ESCROW_LEDGER');
  return state;
}
/** Only absent namespace migrates automatically. Corrupt/unknown versions preserve failure. */
export function loadState(saved){return saved===undefined?initialState():clone(validateState(saved));}
export function validateAction(action){
  if(!action||typeof action.type!=='string')fail('INVALID_ACTION');
  const keys={discover_horse:['type'],attempt_task:['type','siteId','taskId'],begin_boss:['type'],finish_boss:['type'],claim_rewards:['type'],pause:['type'],resume:['type']}[action.type];
  if(!Array.isArray(keys))fail('UNKNOWN_ACTION');exactKeys(action,keys,'INVALID_ACTION');
  if(action.type==='attempt_task'){siteNumber(action.siteId);if(!TASKS.includes(action.taskId))fail('UNKNOWN_TASK');}
  return action;
}
function proof(state,context,siteId,expected){
  const p=context.battleProof;
  if(!p||p.ownerId!==context.authenticatedPlayerId||p.siteId!==siteId||p.serverVerified!==true||p.finalized!==true||p.outcome!=='victory'||
    typeof p.reportId!=='string'||!p.reportId||p.reportId.length>200||
    typeof p.encounterId!=='string'||!p.encounterId||p.encounterId!==context.expectedEncounterId||
    p.species!==expected.species||(expected.level!==undefined&&p.level!==expected.level)||
    (expected.modifier!==undefined&&(p.modifier??null)!==expected.modifier))fail('UNVERIFIED_BATTLE');
  if(state.usedBattleProofs.some(v=>v.reportId===p.reportId))fail('BATTLE_PROOF_REUSED');
  state.usedBattleProofs.push({reportId:p.reportId,siteId});
}
function arrived(context,targetId){
  const arrival=context.arrival;
  if(!arrival||arrival.ownerId!==context.authenticatedPlayerId||arrival.targetId!==targetId||arrival.serverVerified!==true||arrival.routeValid!==true)fail('UNVERIFIED_ARRIVAL');
}
function award(state,bag,awardId,effects){add(state.escrow.earned,bag);add(state.escrow.pending,bag);effects.push({type:'reward_escrowed',awardId,resources:clone(bag)});}
/** Context is trusted SERVER state, never copied from a client request. No wall-clock authority. */
export function reduceCampaign(current,action,trustedContext={}){
  validateState(current);validateAction(action);
  const ctx=trustedContext;
  assertAdventureAccess(ctx);
  const state=clone(current),effects=[];
  if(action.type==='pause')state.paused=true;
  else if(action.type==='resume')state.paused=false;
  else if(action.type==='claim_rewards'){
    // A reward claim remains possible while the quest is paused or completed.
    resourceBag(ctx.wallet);resourceBag(ctx.capacity);
    const transfer=zero();
    for(const r of RESOURCES){
      // Existing over-cap funds are preserved. Never clamp or confiscate a wallet.
      transfer[r]=Math.min(state.escrow.pending[r],Math.max(0,ctx.capacity[r]-ctx.wallet[r]));
      state.escrow.pending[r]-=transfer[r];state.escrow.claimed[r]+=transfer[r];
    }
    effects.push({type:'transfer_rewards',resources:transfer});
  }else{
    if(state.paused)fail('CAMPAIGN_PAUSED');
    if(action.type==='discover_horse'){
      if(state.phase==='prologue'){
        arrived(ctx,HORSE_ID);state.phase='rescue';award(state,PROLOGUE_REWARD,CAMPAIGN_ID+':prologue',effects);
        effects.push({type:'horse_joined'});
      }
    }else if(action.type==='attempt_task'){
      if(state.phase==='prologue')fail('HORSE_REQUIRED');
      const site=state.sites[action.siteId],index=TASKS.indexOf(action.taskId);
      if(site.step<index)fail('TASK_ORDER');
      if(site.step===index){
        const groupStart=Math.floor((siteNumber(action.siteId)-1)/3)*3;
        if(SITE_IDS.slice(0,groupStart).some(id=>state.sites[id].step!==5))fail('PREVIOUS_ACT_REQUIRED');
        if(action.taskId==='discover')arrived(ctx,action.siteId);
        if(action.taskId==='defeat_guardian'){
          const spec=guardianSpec(action.siteId);
          if(!Number.isSafeInteger(ctx.hallLevel)||ctx.hallLevel<spec.requiredHall)fail('HALL_REQUIRED');
          proof(state,ctx,action.siteId,spec);
        }
        if(action.taskId==='recover_artifact'){
          arrived(ctx,artifactId(action.siteId));
          const mechanism=ctx.mechanismProof;
          if(!mechanism||mechanism.ownerId!==ctx.authenticatedPlayerId||mechanism.siteId!==action.siteId||mechanism.serverVerified!==true||mechanism.solved!==true)fail('UNVERIFIED_MECHANISM');
        }
        if(action.taskId==='unlock_cage'){
          arrived(ctx,action.siteId+':cage');
          if(site.artifact!==1)fail('ARTIFACT_REQUIRED');
        }
        if(action.taskId==='escort_home'){
          const escort=ctx.escortProof,ids=captiveIds(action.siteId);
          if(!escort||escort.ownerId!==ctx.authenticatedPlayerId||escort.siteId!==action.siteId||escort.serverVerified!==true||escort.arrivedHome!==true||
            !Array.isArray(escort.captiveIds)||new Set(escort.captiveIds).size!==3||!ids.every(id=>escort.captiveIds.includes(id)))fail('UNVERIFIED_ESCORT');
        }
        site.step++;site.artifact=[2,3].includes(site.step)?1:0;
        state.rescuedIds=SITE_IDS.filter(id=>state.sites[id].step===5).flatMap(captiveIds);
        award(state,taskReward(action.siteId,action.taskId),CAMPAIGN_ID+':'+action.siteId+':'+action.taskId,effects);
        effects.push({type:'task_completed',siteId:action.siteId,taskId:action.taskId});
        if(SITE_IDS.every(id=>state.sites[id].step===5)){state.phase='boss_unlocked';effects.push({type:'boss_unlocked'});}
      }
    }else if(action.type==='begin_boss'){
      if(!['boss_unlocked','boss_active','completed'].includes(state.phase))fail('ALL_RESCUES_REQUIRED');
      if(state.phase==='boss_unlocked'){
        if(!Number.isSafeInteger(ctx.hallLevel)||ctx.hallLevel<5)fail('HALL_REQUIRED');
        arrived(ctx,BOSS_ID);state.phase='boss_active';effects.push({type:'boss_started'});
      }
    }else if(action.type==='finish_boss'){
      if(state.phase!=='completed'){
        if(state.phase!=='boss_active')fail('BOSS_NOT_ACTIVE');
        if(ctx.hallLevel<5)fail('HALL_REQUIRED');
        proof(state,ctx,BOSS_ID,{species:BOSS_SPECIES});state.phase='completed';
        award(state,FINAL_REWARD,CAMPAIGN_ID+':final',effects);effects.push({type:'campaign_completed'});
      }
    }
  }
  const changed=JSON.stringify(state)!==JSON.stringify(current);
  if(changed){if(current.revision===Number.MAX_SAFE_INTEGER)fail('REVISION_EXHAUSTED');state.revision++;}
  validateState(state);return {state,effects,changed};
}
export function campaignMaximumReward(){
  const total=add(zero(),PROLOGUE_REWARD);
  for(const siteId of SITE_IDS)for(const taskId of TASKS)add(total,taskReward(siteId,taskId));
  return add(total,FINAL_REWARD);
}
