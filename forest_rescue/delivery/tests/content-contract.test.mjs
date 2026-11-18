import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {CAMPAIGN_ID,SITE_IDS,TASKS,RESOURCES,BOSS_ID,BOSS_SPECIES,HORSE_ID,TASK_REWARDS,PROLOGUE_REWARD,FINAL_REWARD,guardianSpec,siteMultiplier,artifactId,captiveIds,taskReward,campaignMaximumReward,validateState,initialState,validateAction} from '../code/forest-rescue.mjs';
import {allActions,play} from './fixtures.mjs';
const read=relative=>JSON.parse(fs.readFileSync(new URL(relative,import.meta.url),'utf8'));
const campaign=read('../data/campaign.json'),economy=read('../data/economy.json'),ui=read('../data/ui.ru.json');
test('All 12 site definitions match executable task, guardian, captive and artifact contracts',()=>{
  assert.equal(campaign.id,CAMPAIGN_ID);assert.deepEqual(campaign.taskOrder,TASKS);
  assert.equal(campaign.prologue.horseId,HORSE_ID);
  assert.deepEqual(campaign.sites.map(s=>s.id),SITE_IDS);assert.equal(campaign.mainTaskCount,60);
  for(const site of campaign.sites){
    assert.equal(site.rewardMultiplier,siteMultiplier(site.id));assert.deepEqual(site.tasks.map(t=>t.id),TASKS);
    for(const [key,value]of Object.entries(guardianSpec(site.id)))assert.equal(site.guardian[key],value,site.id+':'+key);
    assert.equal(site.artifact.id,artifactId(site.id));assert.equal(site.artifact.boundSiteId,site.id);assert.equal(site.artifact.quantity,1);
    assert.deepEqual(site.captives.map(c=>c.id),captiveIds(site.id));
    for(const [i,task]of site.tasks.entries()){
      assert.equal(task.requiresStep,i);assert.equal(task.nextStep,i+1);assert.deepEqual(task.reward,taskReward(site.id,task.id));
      assert.equal(task.awardId,CAMPAIGN_ID+':'+site.id+':'+task.id);
    }
  }
});
test('Narrative economy matches all executable amounts and has no hidden awards',()=>{
  assert.equal(economy.campaignId,CAMPAIGN_ID);assert.deepEqual(economy.resources,RESOURCES);
  assert.deepEqual(economy.baseTaskRewards,TASK_REWARDS);assert.deepEqual(economy.prologue,PROLOGUE_REWARD);assert.deepEqual(economy.final,FINAL_REWARD);
  assert.deepEqual(economy.totals,campaignMaximumReward());assert.deepEqual(campaign.economyTotals,campaignMaximumReward());
  assert.equal(economy.totalAllResources,Object.values(campaignMaximumReward()).reduce((a,b)=>a+b,0));
  assert.equal(economy.awardCount,62);assert.equal(economy.additionalHiddenCampaignAwards,false);assert.equal(economy.xpAward,0);
  assert.equal(economy.ordinaryFirstCombatLoot,'retained separately under original rules; excluded from guaranteed totals');
  assert.equal(campaign.boss.encounterId,BOSS_ID);assert.equal(campaign.boss.speciesId,BOSS_SPECIES);assert.deepEqual(campaign.boss.reward,FINAL_REWARD);
});
test('Packaged synthetic save fixtures validate and match executed checkpoints',()=>{
  const checkpoints=[['01_prologue',0],['02_key_recovered',3],['03_completed_unclaimed',allActions.length]];
  for(const [name,length]of checkpoints){const state=read('./fixtures/'+name+'.json');validateState(state);assert.deepEqual(state,play(allActions.slice(0,length)).state);}
});
test('Russian UI has correct campaign identity and nonempty plain-text values',()=>{
  assert.equal(ui.campaignId,CAMPAIGN_ID);assert.equal(ui.locale,'ru-RU');assert.equal(ui.plainTextOnly,true);
  assert.ok(Object.keys(ui.strings).length>20);
  for(const [key,value]of Object.entries(ui.strings))assert.ok(typeof value==='string'&&value.trim().length>0,key);
});
test('Final persistence contract matches exact state shape and command allowlist',()=>{
  const contract=read('../data/persistence-contract.json'),state=initialState();
  assert.equal(contract.campaignId,CAMPAIGN_ID);
  assert.deepEqual([...contract.stateKeys].sort(),Object.keys(state).sort());
  assert.deepEqual([...contract.perSiteKeys].sort(),Object.keys(state.sites[SITE_IDS[0]]).sort());
  assert.deepEqual([...contract.escrowKeys].sort(),Object.keys(state.escrow).sort());
  assert.equal(contract.autoRefillDefault,false);
  assert.deepEqual(contract.commands,{discover_horse:[],attempt_task:['siteId','taskId'],begin_boss:[],finish_boss:[],claim_rewards:[],pause:[],resume:[]});
  for(const type of Object.keys(contract.commands)){
    const action=type==='attempt_task'?{type,siteId:SITE_IDS[0],taskId:TASKS[0]}:{type};
    validateAction(action);
    for(const forbidden of contract.clientForbiddenAuthority)assert.throws(()=>validateAction({...action,[forbidden]:true}));
  }
});
