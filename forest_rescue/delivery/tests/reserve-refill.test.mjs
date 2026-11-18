import test from 'node:test';
import assert from 'node:assert/strict';
import {RESOURCES} from '../code/forest-rescue.mjs';
import {refillAfterVerifiedSpend} from '../code/reserve-refill.mjs';
import {play,owner,bag,allActions} from './fixtures.mjs';
const state=play().state;
const args={authenticatedPlayerId:owner,hallLevel:5,optedIn:true,beforeWallet:bag(2000),afterWallet:{...bag(2000),food:500,wood:1300},capacity:bag(2000)};
test('Opt-in reserve refills after a legitimate spend without changing capacity, price or earned total',()=>{
  const out=refillAfterVerifiedSpend(state,args);
  assert.deepEqual(out.wallet,bag(2000));assert.equal(out.state.escrow.pending.food,state.escrow.pending.food-1500);
  assert.equal(out.state.escrow.pending.wood,state.escrow.pending.wood-700);
  assert.deepEqual(out.state.escrow.earned,state.escrow.earned);
  for(const r of RESOURCES)assert.equal(out.state.escrow.pending[r]+out.state.escrow.claimed[r],state.escrow.earned[r]);
  assert.equal(args.afterWallet.food,500);assert.equal(state.escrow.claimed.food,0);
});
test('Opt-out and polls without spending never drain the reserve',()=>{
  const off=refillAfterVerifiedSpend(state,{...args,optedIn:false});assert.equal(off.changed,false);assert.deepEqual(off.wallet,args.afterWallet);
  const poll=refillAfterVerifiedSpend(state,{...args,afterWallet:args.beforeWallet});assert.equal(poll.changed,false);assert.deepEqual(poll.effects,[]);
});
test('Partial remaining reserve exhausts exactly and leaves other deficits visible',()=>{
  const small=play(allActions.slice(0,1)).state;
  const out=refillAfterVerifiedSpend(small,{...args,beforeWallet:bag(10000),afterWallet:bag(0),capacity:bag(10000)});
  assert.deepEqual(out.wallet,{food:5000,wood:5000,stone:0,iron:0,coins:0});assert.deepEqual(out.state.escrow.pending,bag(0));
});
test('Existing over-cap balance is preserved; refunds and mixed mutations must use another path',()=>{
  const over=refillAfterVerifiedSpend(state,{...args,beforeWallet:bag(3000),afterWallet:{...bag(3000),food:2500}});
  assert.equal(over.wallet.food,2500);assert.equal(over.wallet.wood,3000);assert.equal(over.changed,false);
  assert.throws(()=>refillAfterVerifiedSpend(state,{...args,afterWallet:{...args.afterWallet,coins:2001}}),e=>e.code==='NOT_SPEND_ONLY');
});
test('CAS loser recomputes its legitimate spend then refill against committed reserve',()=>{
  const candidateA=refillAfterVerifiedSpend(state,args),candidateB=refillAfterVerifiedSpend(state,args);
  assert.deepEqual(candidateA.state,candidateB.state);
  // One snapshot wins. A different authorized spend is then applied to its wallet.
  const newBefore=candidateA.wallet,newAfter={...newBefore,food:newBefore.food-1500,wood:newBefore.wood-700};
  const rebased=refillAfterVerifiedSpend(candidateA.state,{...args,beforeWallet:newBefore,afterWallet:newAfter});
  assert.equal(rebased.state.escrow.claimed.food,3000);assert.equal(rebased.state.escrow.claimed.wood,1400);
  assert.deepEqual(rebased.wallet,bag(2000));
});
