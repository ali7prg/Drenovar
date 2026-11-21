// Hall-III access gate (before receipt replay), entrance corridor, real upgrade completion,
// intro lifecycle and the existing-progress intro migration.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, writeFileSync} from 'node:fs';
import {freshRealm} from './helpers/realm.mjs';
import {campaignFsm} from '../src/vendor.mjs';

const bit = (state, x, z) => {
  const c = Math.floor((x + 112) / 4), r = Math.floor((z + 112) / 4), i = r * 56 + c;
  return !!(Buffer.from(state.adventure.fog.visibleBase64, 'base64')[i >> 3] & (1 << (i & 7)));
};
const ZERO = {food: 0, wood: 0, stone: 0, iron: 0, coins: 0};

test('hall I/II: locked projection, every adventure/intro command refused before receipt replay, saved bytes untouched', async () => {
  const {realm, client, playerId} = await freshRealm({idPrefix: 'locked'});
  try {
    for (const level of [1, 2]) {
      await client.hall(level);
      const s = await client.state();
      assert.equal(s.adventure.access.unlocked, false);
      assert.equal(s.adventure.access.hallLevel, level);
      assert.equal(s.adventure.access.reason, 'FOREST_LOCKED_HALL_LEVEL');
      assert.deepEqual(s.adventure.pois, []);
      assert.equal(s.adventure.horse.visible, false);
      assert.equal(s.adventure.fog.explorationLocked, true);
      assert.equal(s.adventure.intro.offer, false);
      assert.ok(bit(s, 0, 0) && !bit(s, -12, -60), 'town visible, no entrance corridor yet');
      for (const body of [client.adv('form_squad', {units: {'ENG-01': 1}}), client.adv('claim_rewards'), client.adv('set_auto_refill', {enabled: true}), client.intro('start_intro'), client.intro('skip_intro')]) {
        const r = await client.send(body);
        assert.equal(r.status, 403, JSON.stringify(body));
        assert.equal(r.body.error, 'FOREST_LOCKED_HALL_LEVEL');
        assert.equal(r.body.message, 'Приключение откроется на 3-м уровне ратуши.');
      }
    }
    const saved = JSON.parse(readFileSync(realm.dbPath, 'utf8')).players[playerId];
    for (const ns of ['adventures', 'adventureMechanisms', 'adventureFog', 'adventureAccess', 'rewardReservePrefs', 'adventureField']) assert.equal(saved[ns], undefined, ns);
    // A receipt stored while unlocked is NOT replayed once the hall gate is closed.
    await client.hall(3);
    const body = client.adv('form_squad', {units: {'ENG-01': 2}});
    assert.equal((await client.send(body, {key: 'receipt-before-lock-1'})).status, 200);
    await client.hall(2);
    const replay = await client.send(body, {key: 'receipt-before-lock-1'});
    assert.equal(replay.status, 403);
    assert.equal(replay.body.error, 'FOREST_LOCKED_HALL_LEVEL');
    const bytes = JSON.stringify(JSON.parse(readFileSync(realm.dbPath, 'utf8')).players[playerId].adventureField);
    await client.state();
    assert.equal(JSON.stringify(JSON.parse(readFileSync(realm.dbPath, 'utf8')).players[playerId].adventureField), bytes, 'locked polling writes nothing');
  } finally {
    await realm.destroy();
  }
});

test('hall III opens only the entrance corridor; hidden or unavailable targets are unknown (404, no leak)', async () => {
  const {realm, client} = await freshRealm({idPrefix: 'corridor'});
  try {
    await client.hall(3);
    const s = await client.state();
    assert.equal(s.adventure.access.unlocked, true);
    assert.equal(s.adventure.fog.explorationLocked, false);
    assert.ok(bit(s, -12, -60) && bit(s, -8, -55), 'corridor open');
    assert.ok(!bit(s, -20, -65) && !bit(s, 75, -86) && !bit(s, 90, 20), 'rest of the forest stays fogged');
    assert.deepEqual(s.adventure.pois.map(p => p.id).sort(), ['lf_home_reception', 'lf_horse_origin']);
    assert.equal(s.adventure.horse.visible, true);
    assert.equal(s.adventure.horse.node, 'lf_horse_origin');
    assert.ok(s.adventure.campaign.sites.every(x => !x.available && !x.visible));
    await client.army({'ENG-06': 50});
    await client.ok('form_squad', {units: {'ENG-06': 50}});
    for (const targetId of ['lf_site_01', 'lf_site_04', 'lf_key_01', 'lf_site_01:cage', 'lf_bridge_crossing', 'lf_boss_ancient_maw', 'lf_trail_junction_corridor__junction_stones#10', 'nowhere']) {
      const r = await client.send(client.adv('move', {targetId}));
      assert.equal(r.status, 404, targetId);
      assert.equal(r.body.error, 'TARGET_UNKNOWN');
    }
    assert.equal((await client.send(client.adv('move', {targetId: 'lf_horse_origin'}))).status, 200);
  } finally {
    await realm.destroy();
  }
});

test('a hall upgrade 2→3 unlocks only when the server construction order completes', async () => {
  const {realm, client} = await freshRealm({idPrefix: 'upgrade'});
  try {
    await client.hall(2);
    await client.wallet({food: 1000, wood: 1000, stone: 1000, iron: 1000, coins: 1000});
    const hall = (await client.state()).city.buildings.find(b => b.type === 'ECO-05');
    const order = await client.send({kind: 'kingdom', action: 'upgrade', buildingId: hall.id, expectedLevel: 2});
    assert.equal(order.status, 200, JSON.stringify(order.body));
    const o = order.body.city.kingdom.order;
    assert.equal(o.level, 3);
    assert.equal(order.body.city.demo.wallet.food, 1000 - 230);
    assert.equal(order.body.adventure.access.unlocked, false, 'starting the upgrade does not open the forest');
    assert.equal((await client.send(client.intro('start_intro'))).status, 403);
    const during = await client.advanceTo(o.endsAt - 1);
    assert.equal(during.adventure.access.unlocked, false);
    const after = await client.advanceTo(o.endsAt);
    assert.equal(after.city.buildings.find(b => b.type === 'ECO-05').level, 3);
    assert.equal(after.adventure.access.unlocked, true);
    assert.equal(after.adventure.intro.offer, true, 'first confirmed hall III offers the intro once');
    assert.deepEqual(after.adventure.escrow.earned, ZERO, 'unlocking pays nothing');
  } finally {
    await realm.destroy();
  }
});

test('intro lifecycle: start/finish, skip, defer, interrupted playing → deferred on entry, no auto-replay, no rewards', async () => {
  const {realm, client} = await freshRealm({idPrefix: 'intro'});
  try {
    await client.hall(3);
    const start = await client.send(client.intro('start_intro'));
    assert.equal(start.status, 200);
    assert.deepEqual(start.body.events.filter(e => e.type === 'intro_present').map(e => [e.attempt, e.mode]), [[1, 'animated']]);
    assert.equal(start.body.adventure.intro.status, 'playing');
    const twice = await client.send(client.intro('start_intro'));
    assert.deepEqual(twice.body.events.filter(e => e.type === 'intro_present'), [], 'no second presentation');
    const stale = await client.send(client.intro('finish_intro', {attempt: 2}));
    assert.equal(stale.status, 409);
    assert.equal(stale.body.error, 'INTRO_STALE_ATTEMPT');
    const fin = await client.send(client.intro('finish_intro'));
    assert.equal(fin.status, 200);
    assert.equal(fin.body.adventure.intro.status, 'acknowledged');
    assert.equal(fin.body.adventure.intro.acknowledgment, 'finished');
    assert.equal(fin.body.adventure.intro.offer, false);
    const again = await client.send(client.intro('start_intro'));
    assert.deepEqual(again.body.events.filter(e => e.type === 'intro_present'), [], 'acknowledged intro never auto-replays');
    assert.equal((await client.session()).status, 200, 'entry with an existing settlement');
    assert.equal((await client.state()).adventure.intro.status, 'acknowledged');
    assert.deepEqual((await client.state()).adventure.escrow.earned, ZERO);

    // Second settlement: defer → start (reduced motion) → interrupted → new entry → deferred → skip.
    const created = await client.raw('POST', '/api/session/new', {body: {additional: true}});
    const b = realm.client({player: created.body.playerId, keyPrefix: 'b'});
    await b.hall(5);
    const deferred = await b.send(b.intro('defer_intro'));
    assert.deepEqual([deferred.body.adventure.intro.status, deferred.body.adventure.intro.deferred, deferred.body.adventure.intro.offer, deferred.body.adventure.intro.invitation], ['pending', true, false, true]);
    const play = await b.send(b.intro('start_intro', {reducedMotion: true}));
    assert.deepEqual(play.body.events.filter(e => e.type === 'intro_present').map(e => e.mode), ['static_cards']);
    assert.equal(play.body.adventure.intro.status, 'playing');
    const polled = await b.state();
    assert.equal(polled.adventure.intro.status, 'playing', 'polling never reconciles');
    const entry = await b.raw('POST', '/api/session/new', {body: {}});
    assert.equal(entry.status, 200);
    assert.equal(entry.body.playerId, created.body.playerId);
    assert.ok(entry.body.events.some(e => e.type === 'intro_deferred'));
    const resumed = entry.body.adventure.intro;
    assert.deepEqual([resumed.status, resumed.deferred, resumed.offer, resumed.continueRequired], ['pending', true, false, true]);
    const skip = await b.send(b.intro('skip_intro'));
    assert.deepEqual([skip.body.adventure.intro.status, skip.body.adventure.intro.acknowledgment], ['acknowledged', 'skipped']);
    assert.deepEqual(skip.body.adventure.escrow.earned, ZERO);
    assert.equal(skip.body.adventure.campaign.phase, 'prologue', 'intro never replaces discover_horse');
  } finally {
    await realm.destroy();
  }
});

test('existing campaign progress without an intro namespace migrates to acknowledged(existing_progress) without touching progress', async () => {
  const {realm, client, playerId} = await freshRealm({idPrefix: 'legacy'});
  try {
    await realm.stop();
    const db = JSON.parse(readFileSync(realm.dbPath, 'utf8'));
    const ctx = {authenticatedPlayerId: playerId, hallLevel: 3, arrival: {ownerId: playerId, targetId: 'lf_horse_origin', serverVerified: true, routeValid: true}};
    const legacy = campaignFsm.reduceCampaign(campaignFsm.initialState(), {type: 'discover_horse'}, ctx).state;
    db.players[playerId].adventures = {forest_rescue_v1: legacy};
    db.players[playerId].city.buildings[0].level = 3;
    writeFileSync(realm.dbPath, JSON.stringify(db));
    await realm.start();
    const s = await client.state();
    assert.equal(s.adventure.intro.status, 'acknowledged');
    assert.equal(s.adventure.intro.acknowledgment, 'existing_progress');
    assert.equal(s.adventure.intro.offer, false);
    assert.equal(s.adventure.campaign.phase, 'rescue');
    assert.deepEqual(s.adventure.escrow.earned, {food: 5000, wood: 5000, stone: 0, iron: 0, coins: 0});
    assert.equal(s.adventure.squad.node, 'lf_home_reception');
    await client.army({'ENG-06': 10});
    await client.ok('form_squad', {units: {'ENG-06': 10}});
    const saved = JSON.parse(readFileSync(realm.dbPath, 'utf8')).players[playerId];
    assert.equal(saved.adventureAccess.forest_rescue_v1.acknowledgment, 'existing_progress');
    assert.deepEqual(saved.adventures.forest_rescue_v1, legacy, 'campaign bytes unchanged by the migration');
  } finally {
    await realm.destroy();
  }
});
