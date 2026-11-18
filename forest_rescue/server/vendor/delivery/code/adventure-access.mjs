/** Hall-III access and durable introductory presentation lifecycle; no reward logic. */
export const MIN_HALL_LEVEL=3;
export const ACCESS_CAMPAIGN_ID='forest_rescue_v1';
const fail=code=>{const e=new Error(code);e.code=code;throw e;};
export function isAdventureUnlocked(hallLevel){
  if(!Number.isSafeInteger(hallLevel)||hallLevel<0)fail('INVALID_HALL_LEVEL');
  return hallLevel>=MIN_HALL_LEVEL;
}
export function assertAdventureAccess(trusted){
  if(!trusted||typeof trusted.authenticatedPlayerId!=='string'||!trusted.authenticatedPlayerId)fail('UNAUTHENTICATED');
  if(!isAdventureUnlocked(trusted.hallLevel))fail('HALL_REQUIRED');
}
export function initialIntroState(){return {schemaVersion:1,campaignId:ACCESS_CAMPAIGN_ID,status:'pending',attempts:0,deferred:false,acknowledgment:null,revision:0};}
export function validateIntroState(state){
  const keys=['schemaVersion','campaignId','status','attempts','deferred','acknowledgment','revision'];
  if(!state||Object.keys(state).length!==keys.length||keys.some(k=>!Object.hasOwn(state,k)))fail('INVALID_INTRO_STATE');
  if(state.schemaVersion!==1)fail('UNSUPPORTED_INTRO_SCHEMA');
  if(state.campaignId!==ACCESS_CAMPAIGN_ID||!['pending','playing','acknowledged'].includes(state.status)||
    !Number.isSafeInteger(state.attempts)||state.attempts<0||!Number.isSafeInteger(state.revision)||state.revision<0||typeof state.deferred!=='boolean')fail('INVALID_INTRO_STATE');
  if(state.status==='acknowledged'){
    if(!['finished','skipped','existing_progress'].includes(state.acknowledgment)||state.deferred||(state.acknowledgment==='finished'&&state.attempts===0))fail('INVALID_INTRO_STATE');
  }else if(state.acknowledgment!==null)fail('INVALID_INTRO_STATE');
  if(state.status==='playing'&&(state.attempts===0||state.deferred))fail('INVALID_INTRO_STATE');
  if(state.attempts>state.revision||(state.status==='acknowledged'&&state.revision===0)||(state.deferred&&state.revision===0)||
    (state.status==='pending'&&state.attempts>0&&!state.deferred)||(state.acknowledgment==='existing_progress'&&state.attempts!==0))fail('INVALID_INTRO_STATE');
  return state;
}
export function loadIntroState(saved){return saved===undefined?initialIntroState():structuredClone(validateIntroState(saved));}
function safePresentation(trusted){
  return trusted.cityForeground===true&&trusted.uiReady===true&&trusted.activeCombat===false&&trusted.modalOpen===false&&trusted.loading===false;
}
/** Pure UI projection after authoritative hall/profile reconciliation. Does not start a movie. */
export function projectAdventureAccess(saved,trusted){
  const state=loadIntroState(saved);
  if(!trusted||typeof trusted.authenticatedPlayerId!=='string'||!trusted.authenticatedPlayerId)fail('UNAUTHENTICATED');
  const unlocked=isAdventureUnlocked(trusted.hallLevel),safe=safePresentation(trusted);
  return {unlocked,minimumHall:MIN_HALL_LEVEL,introStatus:state.status,
    autoStartEligible:unlocked&&safe&&state.status==='pending'&&!state.deferred&&state.attempts===0,
    invitationAvailable:unlocked&&state.status!=='acknowledged',
    continueRequired:unlocked&&state.status!=='acknowledged'&&(state.deferred||state.attempts>0),
    canStartNow:unlocked&&safe&&state.status==='pending',
    campaignAccessible:unlocked};
}
function finish(state,before,effects){
  const changed=JSON.stringify(state)!==JSON.stringify(before);
  if(changed){if(before.revision===Number.MAX_SAFE_INTEGER)fail('REVISION_EXHAUSTED');state.revision++;}
  validateIntroState(state);return {state,effects,changed};
}
/** Call on actual new foreground session entry, not on every polling request. */
export function reconcileIntroOnEntry(saved,trusted){
  const before=loadIntroState(saved),state=structuredClone(before);
  if(!trusted||typeof trusted.authenticatedPlayerId!=='string'||!trusted.authenticatedPlayerId)fail('UNAUTHENTICATED');
  if(isAdventureUnlocked(trusted.hallLevel)&&state.status==='playing'){state.status='pending';state.deferred=true;}
  return finish(state,before,[]);
}
export function validateIntroAction(action){
  const keys={start_intro:['type'],finish_intro:['type','attempt'],skip_intro:['type'],defer_intro:['type']}[action?.type];
  if(!Array.isArray(keys)||!action||Object.keys(action).length!==keys.length||keys.some(k=>!Object.hasOwn(action,k)))fail('INVALID_INTRO_ACTION');
  if(action.type==='finish_intro'&&(!Number.isSafeInteger(action.attempt)||action.attempt<1))fail('INVALID_INTRO_ACTION');
  return action;
}
export function reduceIntro(saved,action,trusted){
  const before=loadIntroState(saved);validateIntroAction(action);assertAdventureAccess(trusted);
  const state=structuredClone(before),effects=[];
  if(state.status==='acknowledged')return {state,effects,changed:false};
  if(action.type==='start_intro'){
    if(!safePresentation(trusted))fail('INTRO_NOT_SAFE');
    if(state.status==='pending'){
      if(state.attempts===Number.MAX_SAFE_INTEGER)fail('ATTEMPT_EXHAUSTED');
      state.attempts++;state.status='playing';state.deferred=false;
      effects.push({type:'present_intro',attempt:state.attempts,mode:trusted.reducedMotion===true?'static_cards':'animated'});
    }
  }else if(action.type==='finish_intro'){
    if(state.status!=='playing'||action.attempt!==state.attempts)fail('STALE_INTRO_ATTEMPT');
    state.status='acknowledged';state.acknowledgment='finished';state.deferred=false;
  }else if(action.type==='skip_intro'){
    // Skip is also allowed directly from an invitation; no cinematic is compulsory.
    state.status='acknowledged';state.acknowledgment='skipped';state.deferred=false;
  }else if(action.type==='defer_intro'){
    state.status='pending';state.deferred=true;
  }
  return finish(state,before,effects);
}
