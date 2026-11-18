/** Explicit compatibility policy. Inputs must be loaded from the selected SERVER player. */
import {initialIntroState,loadIntroState,validateIntroState} from './adventure-access.mjs';
import {loadState} from './forest-rescue.mjs';
export function migrateIntroForExistingCampaign(savedIntro,savedCampaign){
  const campaign=loadState(savedCampaign);
  if(savedIntro!==undefined)return {state:loadIntroState(savedIntro),migrated:false,reason:null};
  const state=initialIntroState();
  if(campaign.phase!=='prologue'){
    state.status='acknowledged';state.acknowledgment='existing_progress';state.revision=1;
    validateIntroState(state);return {state,migrated:true,reason:'existing_progress'};
  }
  return {state,migrated:false,reason:null};
}
