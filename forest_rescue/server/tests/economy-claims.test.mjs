// Escrow claims into the REAL wallet fields (p.city.progress.wood, p.city.demo.wallet.*):
// partial transfers bounded by free capacity, remainder kept, over-cap balances untouched,
// opt-in auto-refill only after a genuine paid command in the same transaction.
import test from 'node:test';
import assert from 'node:assert/strict';
import {adventurer} from './helpers/setup.mjs';
import {RESOURCES} from './helpers/journey.mjs';
import {createForestRescue, createLocalPorts} from '../src/index.mjs';
import {campaignFsm} from '../src/vendor.mjs';

const wallet = s => ({food: s.city.demo.wallet.food, wood: s.city.progress.wood, stone: s.city.demo.wallet.stone, iron: s.city.demo.wallet.iron, coins: s.city.demo.wallet.coins});

test('full warehouse: claim moves only free capacity, keeps the remainder, never cuts an over-cap balance', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'warehouse'});
  try {
    await journey.completeSite('lf_site_01');
    const cap = 3600; // hall III with the starter buildings: 1200 + 3×800
    await client.wallet({food: 1600, wood: cap, stone: 5000, iron: 0, coins: 3599});
    const before = (await client.state()).adventure.escrow;
    const r = await client.ok('claim_rewards');
    const t = r.events.find(e => e.type === 'transfer_rewards').resources;
    assert.deepEqual(t, {food: 2000, wood: 0, stone: 0, iron: Math.min(cap, before.pending.iron), coins: 1});
    const w = wallet(r);
    assert.deepEqual(w, {food: 3600, wood: 3600, stone: 5000, iron: Math.min(cap, before.pending.iron), coins: 3600});
    for (const res of RESOURCES) {
      assert.equal(r.adventure.escrow.pending[res], before.pending[res] - t[res], 'remainder kept: ' + res);
      assert.equal(r.adventure.escrow.claimed[res] + r.adventure.escrow.pending[res], r.adventure.escrow.earned[res]);
    }
    assert.equal(r.city.demo.wallet.wood, undefined, 'wood is never written to demo.wallet');
    // completely full: a successful zero transfer with an explanation; still allowed while paused
    await client.ok('pause');
    await client.wallet({food: 5000, wood: 9999, stone: 3600, iron: 3600, coins: 3600});
    const full = await client.ok('claim_rewards');
    const ev = full.events.find(e => e.type === 'transfer_rewards');
    assert.deepEqual(ev.resources, {food: 0, wood: 0, stone: 0, iron: 0, coins: 0});
    assert.equal(ev.storageFull, true);
    assert.deepEqual(full.adventure.escrow, r.adventure.escrow);
    assert.deepEqual(wallet(full), {food: 5000, wood: 9999, stone: 3600, iron: 3600, coins: 3600});
  } finally {
    await realm.destroy();
  }
});

test('claim formula at a 2000 capacity (new-city storage) through the module ports', async () => {
  const ports = {...createLocalPorts(), capacity: () => 2000};
  const fr = createForestRescue({ports});
  const p = {id: 'cap-2000', city: {progress: {wood: 1500, xp: 0}, demo: {wallet: {food: 0, stone: 2500, iron: 1999, coins: 0}}, buildings: [{type: 'ECO-05', level: 3}], military: {owned: {}}}, wounded: {}};
  const ctx = {authenticatedPlayerId: p.id, hallLevel: 3, arrival: {ownerId: p.id, targetId: 'lf_horse_origin', serverVerified: true, routeValid: true}};
  p.adventures = {forest_rescue_v1: campaignFsm.reduceCampaign(campaignFsm.initialState(), {type: 'discover_horse'}, ctx).state};
  const out = await fr.command({p, body: {kind: 'adventure', campaignId: 'forest_rescue_v1', action: 'claim_rewards'}, key: 'cap-2000-claim', now: 1, receipts: {find: async () => null}});
  assert.deepEqual(out.events.find(e => e.type === 'transfer_rewards').resources, {food: 2000, wood: 500, stone: 0, iron: 0, coins: 0});
  assert.deepEqual(p.adventures.forest_rescue_v1.escrow.pending, {food: 3000, wood: 4500, stone: 0, iron: 0, coins: 0});
  assert.deepEqual([p.city.demo.wallet.food, p.city.progress.wood, p.city.demo.wallet.stone], [2000, 2000, 2500]);
});

test('auto-refill: off by default; opt-in refills from escrow only after a real paid command; never on polls or below hall III', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'refill'});
  try {
    await journey.completeSite('lf_site_01');
    const hallId = (await client.state()).city.buildings.find(b => b.type === 'ECO-05').id;
    const upgrade = level => client.send({kind: 'kingdom', action: 'upgrade', buildingId: hallId, expectedLevel: level});
    await client.wallet({food: 3600, wood: 3600, stone: 3600, iron: 3600, coins: 3600});
    const e0 = (await client.state()).adventure.escrow;
    const off = await upgrade(3);
    assert.equal(off.status, 200);
    assert.deepEqual(wallet(off.body), {food: 3200, wood: 2900, stone: 3240, iron: 3490, coins: 3520}, 'opted out: plain spend');
    assert.deepEqual(off.body.adventure.escrow, e0);
    await client.advanceTo(off.body.city.kingdom.order.endsAt);
    assert.deepEqual((await client.state()).adventure.escrow, e0, 'polling never refills');
    // opt in (owner-scoped preference), then a real paid upgrade 4→5
    const pref = await client.ok('set_auto_refill', {enabled: true});
    assert.equal(pref.adventure.autoRefill, true);
    const cap = 4400; // hall IV
    await client.wallet({food: cap, wood: cap, stone: cap, iron: cap, coins: cap});
    const on = await upgrade(4);
    assert.equal(on.status, 200);
    const ev = on.body.events.find(e => e.type === 'transfer_rewards' && e.auto === true);
    assert.deepEqual(ev.resources, {food: 600, wood: 1150, stone: 700, iron: 300, coins: 150}, 'exactly the freed space');
    assert.deepEqual(wallet(on.body), {food: cap, wood: cap, stone: cap, iron: cap, coins: cap});
    for (const r of RESOURCES) assert.equal(on.body.adventure.escrow.pending[r], e0.pending[r] - ev.resources[r]);
    assert.equal(on.body.city.kingdom.order.level, 5, 'the purchase itself is unchanged');
    // A replayed (duplicate) purchase refills nothing.
    const dup = await client.send({kind: 'kingdom', action: 'upgrade', buildingId: hallId, expectedLevel: 4}, {key: on.key});
    assert.equal(dup.body.replayed, true);
    assert.deepEqual(dup.body.adventure.escrow, on.body.adventure.escrow);
    // Below hall III the reserve stays locked even though the unrelated spend succeeds.
    await client.advanceTo(on.body.city.kingdom.order.endsAt);
    await client.hall(2);
    await client.wallet({food: 2000, wood: 2000, stone: 2000, iron: 2000, coins: 2000});
    const locked = await upgrade(2);
    assert.equal(locked.status, 200);
    assert.deepEqual(locked.body.events.filter(e => e.type === 'transfer_rewards'), []);
    assert.equal(locked.body.adventure.access.unlocked, false);
    assert.deepEqual(wallet(locked.body), {food: 1770, wood: 1550, stone: 1840, iron: 2000, coins: 1960});
  } finally {
    await realm.destroy();
  }
});
