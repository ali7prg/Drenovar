/** Executable atomic snapshot demonstration; NOT an HTTP/D1/auth adapter. */
import {CAMPAIGN_ID,RESOURCES,initialState,loadState,reduceCampaign,validateAction} from './forest-rescue.mjs';
import {assertAdventureAccess,initialIntroState,validateIntroAction,reduceIntro} from './adventure-access.mjs';
import {migrateIntroForExistingCampaign} from './intro-migration.mjs';
const fail=code=>{const e=new Error(code);e.code=code;throw e;};
export function createReferenceSnapshot(playerId,wallet=Object.fromEntries(RESOURCES.map(r=>[r,0]))){
  if(typeof playerId!=='string'||!playerId)fail('INVALID_IDENTITY');
  return {players:[{playerId,campaign:initialState(),intro:initialIntroState(),wallet:structuredClone(wallet)}],receipts:[]};
}
function parseBody(body){
  if(!body||!['adventure','adventure_intro'].includes(body.kind)||body.campaignId!==CAMPAIGN_ID||typeof body.action!=='string')fail('INVALID_COMMAND');
  const {kind,campaignId,action,...rest}=body;
  if(Object.hasOwn(rest,'type'))fail('INVALID_COMMAND');
  return kind==='adventure_intro'?validateIntroAction({type:action,...rest}):validateAction({type:action,...rest});
}
function validateWallet(wallet){
  if(!wallet||Object.keys(wallet).length!==RESOURCES.length||RESOURCES.some(r=>!Number.isSafeInteger(wallet[r])||wallet[r]<0))fail('INVALID_WALLET');
}
export function executeReferenceCommand(snapshot,trustedContext,request){
  const {authenticatedPlayerId,enabled}=trustedContext??{};
  assertAdventureAccess(trustedContext);
  if(!request||typeof request.key!=='string'||!/^[-\w]{8,100}$/.test(request.key))fail('INVALID_KEY');
  const action=parseBody(request.body),signature=JSON.stringify(request.body);
  const next=structuredClone(snapshot),player=next.players.find(p=>p.playerId===authenticatedPlayerId);
  if(!player)fail('UNKNOWN_PLAYER');
  player.campaign=loadState(player.campaign);player.intro=migrateIntroForExistingCampaign(player.intro,player.campaign).state;validateWallet(player.wallet);
  const old=next.receipts.find(r=>r.playerId===authenticatedPlayerId&&r.key===request.key);
  if(old){
    if(old.signature!==signature)fail('IDEMPOTENCY_CONFLICT');
    return {snapshot:next,response:{state:structuredClone(player.campaign),intro:structuredClone(player.intro),wallet:structuredClone(player.wallet),effects:[],duplicate:true}};
  }
  if(enabled!==true)fail('FEATURE_DISABLED');
  // SERVER reads wallet; a caller cannot override it even via a mistaken trusted context.
  const introCommand=request.body.kind==='adventure_intro';
  const result=introCommand?reduceIntro(player.intro,action,trustedContext):reduceCampaign(player.campaign,action,{...trustedContext,wallet:player.wallet});
  for(const effect of result.effects)if(effect.type==='transfer_rewards')for(const r of RESOURCES){
    const value=player.wallet[r]+effect.resources[r];if(!Number.isSafeInteger(value))fail('RESOURCE_OVERFLOW');player.wallet[r]=value;
  }
  if(introCommand)player.intro=result.state;else player.campaign=result.state;
  next.receipts.push({playerId:authenticatedPlayerId,key:request.key,signature});
  return {snapshot:next,response:{state:structuredClone(player.campaign),intro:structuredClone(player.intro),wallet:structuredClone(player.wallet),effects:result.effects,duplicate:false}};
}
