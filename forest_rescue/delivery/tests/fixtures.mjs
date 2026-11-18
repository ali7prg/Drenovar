import {CAMPAIGN_ID,RESOURCES,SITE_IDS,TASKS,BOSS_ID,BOSS_SPECIES,HORSE_ID,guardianSpec,artifactId,captiveIds,initialState,reduceCampaign} from '../code/forest-rescue.mjs';
export const owner='settlement-A';
export const bag=n=>Object.fromEntries(RESOURCES.map(r=>[r,n]));
export const context={authenticatedPlayerId:owner,enabled:true,hallLevel:5,capacity:bag(2000),wallet:bag(0)};
export const envelope=action=>{const {type,...rest}=action;return {kind:'adventure',campaignId:CAMPAIGN_ID,action:type,...rest};};
export function evidence(action,playerId=owner){
  const c={...context,authenticatedPlayerId:playerId};
  const arrival=targetId=>({ownerId:playerId,targetId,serverVerified:true,routeValid:true});
  if(action.type==='discover_horse')c.arrival=arrival(HORSE_ID);
  if(action.type==='begin_boss')c.arrival=arrival(BOSS_ID);
  if(action.type==='attempt_task'){
    const {siteId,taskId}=action;
    if(taskId==='discover')c.arrival=arrival(siteId);
    if(taskId==='recover_artifact'){
      c.arrival=arrival(artifactId(siteId));
      c.mechanismProof={ownerId:playerId,siteId,serverVerified:true,solved:true};
    }
    if(taskId==='unlock_cage')c.arrival=arrival(siteId+':cage');
    if(taskId==='defeat_guardian'){
      c.expectedEncounterId='server-guardian-'+siteId;
      c.battleProof={reportId:'battle-'+siteId,encounterId:c.expectedEncounterId,ownerId:playerId,siteId,serverVerified:true,finalized:true,outcome:'victory',...guardianSpec(siteId)};
    }
    if(taskId==='escort_home')c.escortProof={ownerId:playerId,siteId,serverVerified:true,arrivedHome:true,captiveIds:captiveIds(siteId)};
  }
  if(action.type==='finish_boss'){
    c.expectedEncounterId='server-final-boss';
    c.battleProof={reportId:'battle-final-boss',encounterId:c.expectedEncounterId,ownerId:playerId,siteId:BOSS_ID,serverVerified:true,finalized:true,outcome:'victory',species:BOSS_SPECIES};
  }
  return c;
}
export const allActions=[{type:'discover_horse'},...SITE_IDS.flatMap(siteId=>TASKS.map(taskId=>({type:'attempt_task',siteId,taskId}))),{type:'begin_boss'},{type:'finish_boss'}];
export function play(actions=allActions){let state=initialState();const effects=[];for(const action of actions){const out=reduceCampaign(state,action,evidence(action));state=out.state;effects.push(...out.effects);}return {state,effects};}
