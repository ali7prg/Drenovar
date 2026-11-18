// Receipts, lost responses, concurrent commands, repeated victory/cage, profile isolation and
// the strict allowlist — all over HTTP against the local realm.
import test from 'node:test';
import assert from 'node:assert/strict';
import {adventurer, commitBarrier} from './helpers/setup.mjs';
import {RESOURCES} from './helpers/journey.mjs';

const sum = (a, b) => Object.fromEntries(RESOURCES.map(r => [r, a[r] + b[r]]));

test('lost response: same key + same body replays the current state without effects (also after restart); changed body → 409', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'replay'});
  try {
    await journey.moveTo('lf_site_01');
    const body = client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'});
    const first = await client.send(body, {key: 'lost-response-0001'});
    assert.equal(first.status, 200);
    assert.ok(first.body.events.some(e => e.type === 'task_completed'));
    const escrow = first.body.adventure.escrow;
    const again = await client.send(body, {key: 'lost-response-0001'});
    assert.equal(again.status, 200);
    assert.equal(again.body.replayed, true);
    assert.deepEqual(again.body.events.filter(e => e.type === 'task_completed' || e.type === 'reward_escrowed'), []);
    assert.deepEqual(again.body.adventure.escrow, escrow);
    await realm.restart();
    const afterRestart = await client.send(body, {key: 'lost-response-0001'});
    assert.equal(afterRestart.body.replayed, true);
    assert.deepEqual(afterRestart.body.adventure.escrow, escrow);
    const mismatch = await client.send(client.adv('claim_rewards'), {key: 'lost-response-0001'});
    assert.equal(mismatch.status, 409);
    assert.equal(mismatch.body.error, 'IDEMPOTENCY_BODY_MISMATCH');
    assert.match(mismatch.body.message, /запрос/);
    // A fresh key cannot repeat a paid task: the durable step forbids it.
    const fresh = await client.send(body, {key: 'another-key-0002'});
    assert.equal(fresh.status, 200);
    assert.equal(fresh.body.replayed, false);
    assert.deepEqual(fresh.body.events.filter(e => e.type === 'task_completed'), []);
    assert.deepEqual(fresh.body.adventure.escrow, escrow);
    // requestId (if sent) must equal the Idempotency-Key; missing key is refused.
    assert.equal((await client.send({...body, requestId: 'not-the-same-key'}, {key: 'yet-another-0003'})).body.error, 'BAD_FIELDS');
    assert.equal((await client.send({...body, requestId: 'same-as-header-0004'}, {key: 'same-as-header-0004'})).status, 200);
    const noKey = await client.send(client.adv('claim_rewards'), {key: null});
    assert.equal(noKey.status, 400);
    assert.equal(noKey.body.error, 'BAD_FIELDS');
  } finally {
    await realm.destroy();
  }
});

test('two concurrent claims transfer the free capacity once; a concurrent same-key retry has no second effect', async () => {
  const barrier = commitBarrier();
  const {realm, client, journey} = await adventurer({idPrefix: 'claims', hooks: barrier.hooks});
  try {
    await journey.completeSite('lf_site_01');
    await client.wallet({food: 0, wood: 0, stone: 0, iron: 0, coins: 0});
    const before = (await client.state()).adventure.escrow;
    const cap = 3600; // hall III: 1200 + 3×800
    barrier.armed = true;
    const [a, b] = await Promise.all([client.send(client.adv('claim_rewards')), client.send(client.adv('claim_rewards'))]);
    assert.equal(a.status, 200);
    assert.equal(b.status, 200);
    const t = e => e.body.events.find(x => x.type === 'transfer_rewards').resources;
    const total = sum(t(a), t(b));
    const s = await client.state();
    for (const r of RESOURCES) {
      const expected = Math.min(cap, before.pending[r]);
      assert.equal(total[r], expected, r);
      assert.equal(s.adventure.escrow.claimed[r], expected);
      assert.equal(s.adventure.escrow.pending[r], before.pending[r] - expected);
      assert.equal(s.adventure.escrow.claimed[r] + s.adventure.escrow.pending[r], s.adventure.escrow.earned[r]);
    }
    assert.equal(s.city.progress.wood, Math.min(cap, before.pending.wood));
    assert.equal(s.city.demo.wallet.food, Math.min(cap, before.pending.food));
    assert.ok(realm.store.conflicts >= 1, 'the losing claim was rebased by CAS');
    // Same key fired twice concurrently (retry of an in-flight request).
    await client.wallet({food: 0, wood: 0, stone: 0, iron: 0, coins: 0});
    const mid = (await client.state()).adventure.escrow;
    const body = client.adv('claim_rewards');
    barrier.armed = true;
    const [x, y] = await Promise.all([client.send(body, {key: 'same-claim-key-01'}), client.send(body, {key: 'same-claim-key-01'})]);
    assert.deepEqual([x.status, y.status], [200, 200]);
    assert.equal([x, y].filter(r => r.body.replayed).length, 1);
    const end = (await client.state()).adventure.escrow;
    for (const r of RESOURCES) assert.equal(end.claimed[r] - mid.claimed[r], Math.min(cap, mid.pending[r]));
  } finally {
    await realm.destroy();
  }
});

test('double cage open (sequential and concurrent) spends the key and pays once', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'cage'});
  try {
    await journey.completeSite('lf_site_01', {stopBefore: 'unlock_cage'});
    const before = (await client.state()).adventure;
    assert.equal(before.campaign.sites[0].artifact, 1);
    const body = client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'unlock_cage'});
    const [a, b] = await Promise.all([client.send(body), client.send(body)]);
    assert.deepEqual([a.status, b.status], [200, 200]);
    const opened = [...a.body.events, ...b.body.events].filter(e => e.type === 'cage_opened');
    assert.equal(opened.length, 1);
    const third = await client.send(body);
    assert.deepEqual(third.body.events.filter(e => e.type === 'cage_opened' || e.type === 'reward_escrowed'), []);
    const s = await client.state();
    assert.equal(s.adventure.campaign.sites[0].step, 4);
    assert.equal(s.adventure.campaign.sites[0].artifact, 0, 'the key is spent exactly once');
    assert.equal(s.adventure.escrow.earned.food - before.escrow.earned.food, 8000);
    assert.equal(s.adventure.pois.find(p => p.id === 'lf_site_01').artifact.state, 'in_socket');
  } finally {
    await realm.destroy();
  }
});

test('repeated victory: a campaign guardian never respawns; a report cannot pay twice', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'victory'});
  try {
    await journey.completeSite('lf_site_01', {stopBefore: 'unlock_cage'});
    const s = await client.state();
    const reports = s.reports.length;
    await client.raw('POST', '/api/command', {}); // noise: invalid request has no effect
    await journey.moveTo('lf_site_01:guardian');
    const again = await client.send(client.adv('engage_guardian', {siteId: 'lf_site_01'}));
    assert.equal(again.status, 409);
    assert.equal(again.body.error, 'GUARDIAN_DEFEATED');
    const retask = await client.send(client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'defeat_guardian'}));
    assert.equal(retask.status, 200);
    assert.deepEqual(retask.body.events.filter(e => e.type === 'reward_escrowed'), []);
    const after = await client.state();
    assert.deepEqual(after.adventure.escrow, s.adventure.escrow);
    assert.equal(after.reports.length, reports, 'no new battle, no new loot');
    assert.equal(after.adventure.pois.find(p => p.id === 'lf_site_01').guardian.state, 'defeated');
  } finally {
    await realm.destroy();
  }
});

test('second profile of the same account is fully isolated (namespaces, receipts, hall gate)', async () => {
  const {realm, client, journey, playerId} = await adventurer({idPrefix: 'profiles'});
  try {
    await journey.moveTo('lf_site_01');
    const a = await client.send(client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'}), {key: 'shared-key-00000001'});
    assert.equal(a.status, 200);
    const created = await client.raw('POST', '/api/session/new', {body: {additional: true}});
    assert.equal(created.status, 201);
    const other = realm.client({player: created.body.playerId, keyPrefix: 'b'});
    assert.notEqual(created.body.playerId, playerId);
    const b0 = await other.state();
    assert.equal(b0.adventure.access.unlocked, false, 'profile B has its own hall I');
    assert.equal(b0.adventure.campaign.phase, 'prologue');
    assert.deepEqual(b0.adventure.escrow.earned, {food: 0, wood: 0, stone: 0, iron: 0, coins: 0});
    const locked = await other.send(other.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'}), {key: 'shared-key-00000001'});
    assert.equal(locked.status, 403, 'B is gated by its OWN hall, not A’s receipt');
    assert.equal(locked.body.error, 'FOREST_LOCKED_HALL_LEVEL');
    await other.hall(3);
    const bForm = await other.send(other.adv('form_squad', {units: {'ENG-09': 5}}), {key: 'shared-key-00000001'});
    assert.equal(bForm.status, 200);
    assert.equal(bForm.body.replayed, false, 'receipts are per selected settlement');
    const aAfter = await client.state();
    assert.equal(aAfter.adventure.campaign.sites[0].step, 1);
    assert.notEqual(aAfter.adventure.fog.visibleBase64, bForm.body.adventure.fog.visibleBase64);
    assert.deepEqual(bForm.body.adventure.campaign.sites.map(x => x.step), Array(12).fill(0));
    const foreign = realm.client({login: 'someone-else', player: playerId});
    const denied = await foreign.raw('GET', '/api/state');
    assert.equal(denied.status, 403);
    assert.equal(denied.body.error, 'PROFILE_FORBIDDEN');
  } finally {
    await realm.destroy();
  }
});

test('strict allowlist: client-declared success, rewards, wallet, owner, time, positions or proofs are refused without effects', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'allow'});
  try {
    await journey.moveTo('lf_site_01');
    const before = await client.state();
    const base = client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'});
    for (const extra of [{serverVerified: true}, {reward: {food: 1}}, {wallet: {}}, {capacity: 99999}, {ownerId: 'x'}, {playerId: 'x'},
      {now: 1}, {revision: 3}, {state: {phase: 'completed'}}, {battleProof: {outcome: 'victory'}}, {arrival: {}}, {x: 1, z: 2},
      {position: {x: 0}}, {hallLevel: 5}, {success: true}, {type: 'finish_boss'}]) {
      const r = await client.send({...base, ...extra});
      assert.equal(r.status, 400, JSON.stringify(extra));
      assert.equal(r.body.error, 'BAD_FIELDS');
      assert.ok(r.body.message.length > 5);
    }
    for (const body of [{...base, campaignId: 'other'}, {...base, siteId: 'lf_site_99'}, {...base, taskId: 'win'}, client.adv('teleport'),
      client.adv('form_squad', {units: {'ENG-99': 1}}), client.adv('form_squad', {units: {'ENG-06': 0}}), client.adv('set_auto_refill', {enabled: 'yes'}),
      client.intro('finish_intro', {attempt: 0})]) {
      const r = await client.send(body);
      assert.equal(r.status, 400, JSON.stringify(body));
    }
    const after = await client.state();
    assert.deepEqual(after.adventure.escrow, before.adventure.escrow);
    assert.deepEqual(after.adventure.campaign, before.adventure.campaign);
  } finally {
    await realm.destroy();
  }
});
