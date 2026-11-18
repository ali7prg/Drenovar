// Revision CAS: a conflicting commit between read and write forces a retry on the FRESH
// snapshot, recomputing gate, proofs, capacity and wallet; exhaustion → CAS_CONFLICT_RETRY.
import test from 'node:test';
import assert from 'node:assert/strict';
import {adventurer} from './helpers/setup.mjs';

function injector() {
  const inj = {mutate: null, times: 0, hooks: null, fired: 0};
  inj.hooks = {beforeCommit: async ({attempt, store}) => {
    if (!inj.mutate || inj.fired >= inj.times) return;
    inj.fired++;
    const {revision, data} = store.read();
    inj.mutate(data, attempt);
    assert.equal(store.commit(revision, data), true); // "another tab" commits first
  }};
  inj.arm = (mutate, times = 1) => { inj.mutate = mutate; inj.times = times; inj.fired = 0; };
  return inj;
}

test('claim retried after a conflicting spend recomputes the transfer from the fresh wallet', async () => {
  const inj = injector();
  const {realm, client, journey, playerId} = await adventurer({idPrefix: 'cas', hooks: inj.hooks});
  try {
    await journey.completeSite('lf_site_01');
    await client.wallet({food: 0, wood: 0, stone: 0, iron: 0, coins: 0});
    const pending = (await client.state()).adventure.escrow.pending;
    inj.arm(data => { data.players[playerId].city.progress.wood = 3000; data.players[playerId].city.demo.wallet.food = 3500; });
    const conflicts = realm.store.conflicts;
    const r = await client.ok('claim_rewards');
    assert.equal(realm.store.conflicts, conflicts + 1);
    const t = r.events.find(e => e.type === 'transfer_rewards').resources;
    assert.equal(t.wood, 600, 'capacity 3600 − fresh wood 3000');
    assert.equal(t.food, 100);
    assert.equal(r.city.progress.wood, 3600);
    assert.equal(r.adventure.escrow.pending.wood, pending.wood - 600);
  } finally {
    await realm.destroy();
  }
});

test('retry re-applies the hall gate and the durable task step from the fresh snapshot', async () => {
  const inj = injector();
  const {realm, client, journey, playerId} = await adventurer({idPrefix: 'cas2', hooks: inj.hooks});
  try {
    await journey.moveTo('lf_site_01');
    // the other transaction lowers the hall: the retried command must now be refused
    inj.arm(data => { data.players[playerId].city.buildings.find(b => b.type === 'ECO-05').level = 2; });
    const gated = await client.send(client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'}));
    assert.equal(gated.status, 403);
    assert.equal(gated.body.error, 'FOREST_LOCKED_HALL_LEVEL');
    await client.hall(3);
    const before = (await client.state()).adventure.escrow.earned;
    // the other transaction already completed the same task (another key): no second award
    inj.arm(data => {
      const c = data.players[playerId].adventures.forest_rescue_v1;
      c.sites.lf_site_01.step = 1; c.revision++;
      for (const [r, n] of Object.entries({food: 2000, wood: 2000, stone: 1000, iron: 500, coins: 100})) { c.escrow.earned[r] += n; c.escrow.pending[r] += n; }
    });
    const r = await client.ok('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'});
    assert.deepEqual(r.events.filter(e => e.type === 'reward_escrowed'), []);
    assert.equal(r.adventure.escrow.earned.food - before.food, 2000, 'awarded exactly once');
  } finally {
    await realm.destroy();
  }
});

test('persistent conflicts end with CAS_CONFLICT_RETRY and no effect of the losing command', async () => {
  const inj = injector();
  const {realm, client, playerId} = await adventurer({idPrefix: 'cas3', hooks: inj.hooks});
  try {
    const before = (await client.state()).adventure;
    inj.arm(data => { data.players[playerId].items.touch = (data.players[playerId].items.touch ?? 0) + 1; }, 100);
    const r = await client.send(client.adv('set_auto_refill', {enabled: true}));
    assert.equal(r.status, 409);
    assert.equal(r.body.error, 'CAS_CONFLICT_RETRY');
    assert.match(r.body.message, /Повторите/);
    inj.arm(null);
    const after = await client.state();
    assert.equal(after.adventure.autoRefill, before.autoRefill);
    assert.equal(after.items.touch, 8, 'all 8 attempts were rebased on fresh snapshots');
  } finally {
    await realm.destroy();
  }
});
