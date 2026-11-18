/** Optional pure helper, to call INSIDE an already-authorized successful spend transaction. */
import {RESOURCES,validateState,reduceCampaign} from './forest-rescue.mjs';
import {isAdventureUnlocked} from './adventure-access.mjs';
const fail=code=>{const e=new Error(code);e.code=code;throw e;};
function bag(value){if(!value||Object.keys(value).length!==RESOURCES.length||RESOURCES.some(r=>!Number.isSafeInteger(value[r])||value[r]<0))fail('INVALID_RESOURCE_BAG');}
export function refillAfterVerifiedSpend(state,{authenticatedPlayerId,hallLevel,optedIn,beforeWallet,afterWallet,capacity}){
  validateState(state);bag(beforeWallet);bag(afterWallet);bag(capacity);
  if(typeof authenticatedPlayerId!=='string'||!authenticatedPlayerId)fail('UNAUTHENTICATED');
  if(typeof optedIn!=='boolean')fail('INVALID_PREFERENCE');
  const unlocked=isAdventureUnlocked(hallLevel);
  // Compare snapshots immediately before and after the existing validated spend,
  // after production settlement. This is an invariant, NOT authorization by itself.
  if(RESOURCES.some(r=>afterWallet[r]>beforeWallet[r]))fail('NOT_SPEND_ONLY');
  const spent=RESOURCES.some(r=>afterWallet[r]<beforeWallet[r]);
  // A low-level city's unrelated existing spend may succeed, but reserve access stays locked.
  if(!unlocked||!optedIn||!spent)return {state:structuredClone(state),wallet:structuredClone(afterWallet),effects:[],changed:false};
  const result=reduceCampaign(state,{type:'claim_rewards'},{authenticatedPlayerId,hallLevel,wallet:afterWallet,capacity});
  const wallet=structuredClone(afterWallet);
  for(const effect of result.effects)if(effect.type==='transfer_rewards')for(const r of RESOURCES){
    const sum=wallet[r]+effect.resources[r];if(!Number.isSafeInteger(sum))fail('RESOURCE_OVERFLOW');wallet[r]=sum;
  }
  return {...result,wallet};
}
