import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {initialMechanism,reduceMechanism,validateMechanism} from '../code/mechanisms.mjs';
import {reduceCampaign} from '../code/forest-rescue.mjs';
import {play,allActions,evidence} from './fixtures.mjs';
const campaign=JSON.parse(fs.readFileSync(new URL('../data/campaign.json',import.meta.url),'utf8'));
const trusted={authenticatedPlayerId:'settlement-A',hallLevel:3,siteAccessVerified:true,siteDiscovered:true,occupancyServerVerified:true,leftOccupied:true,rightOccupied:true};
test('All twelve authored mechanisms solve, persist and stay solved without repeating effects',()=>{
  for(const site of campaign.sites){
    let state=initialMechanism(site);
    for(const symbol of site.artifact.puzzle.solution){state=reduceMechanism(state,{symbol},site,{...trusted,observedLandmark:symbol}).state;state=JSON.parse(JSON.stringify(state));validateMechanism(state,site);}
    assert.equal(state.solved,true);
    const replay=reduceMechanism(state,{symbol:site.artifact.puzzle.solution[2]},site,trusted);assert.equal(replay.changed,false);assert.deepEqual(replay.effects,[]);
  }
});
test('Wrong rune resets only this mechanism; no rewards or key consumed',()=>{
  const site=campaign.sites[1],solution=site.artifact.puzzle.solution;
  let state=reduceMechanism(initialMechanism(site),{symbol:solution[0]},site,trusted).state;
  const wrong=reduceMechanism(state,{symbol:solution[2]},site,trusted);
  assert.deepEqual(wrong.state.progress,[]);assert.equal(wrong.state.solved,false);assert.equal(wrong.effects[0].type,'mechanism_reset');
  assert.equal('escrow' in wrong.state,false);assert.equal('artifact' in wrong.state,false);
});
test('Trail requires actual server-observed landmark and latch requires simultaneous occupancy',()=>{
  const trail=campaign.sites[0];assert.throws(()=>reduceMechanism(initialMechanism(trail),{symbol:trail.artifact.puzzle.solution[0]},trail,trusted),e=>e.code==='LANDMARK_NOT_REACHED');
  const site=campaign.sites[3],solution=site.artifact.puzzle.solution;let state=initialMechanism(site);
  for(const symbol of solution.slice(0,2))state=reduceMechanism(state,{symbol},site,trusted).state;
  assert.throws(()=>reduceMechanism(state,{symbol:solution[2]},site,{...trusted,rightOccupied:false}),e=>e.code==='PLATES_NOT_SIMULTANEOUS');
  assert.throws(()=>reduceMechanism(state,{symbol:solution[2]},site,{...trusted,occupancyServerVerified:false}),e=>e.code==='PLATES_NOT_SIMULTANEOUS');
});
test('Undiscovered site access spoof and unsolved artifact recovery fail closed',()=>{
  const site=campaign.sites[1],symbol=site.artifact.puzzle.solution[0];
  assert.throws(()=>reduceMechanism(initialMechanism(site),{symbol},site,{...trusted,siteDiscovered:false}),e=>e.code==='MECHANISM_ACCESS_DENIED');
  assert.throws(()=>reduceMechanism(initialMechanism(site),{symbol,solved:true},site,trusted),e=>e.code==='INVALID_MECHANISM_INPUT');
  const state=play(allActions.slice(0,2)).state,action=allActions[2],ctx=evidence(action);delete ctx.mechanismProof;
  assert.throws(()=>reduceCampaign(state,action,ctx),e=>e.code==='UNVERIFIED_MECHANISM');
});
