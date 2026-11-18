// projectAdventure output validated against CONTRACT §3 at every step of a whole campaign
// (locked, moving, plates, battles, escorts, boss phases, completed) and events against §4.
import test from 'node:test';
import assert from 'node:assert/strict';
import {freshRealm} from './helpers/realm.mjs';
import {Journey, SITES} from './helpers/journey.mjs';
import {checkAdventure, checkMove} from './helpers/contract-schema.mjs';

const EVENT_FIELDS = {
  horse_joined: [], task_completed: ['siteId', 'taskId', 'reward'], reward_escrowed: ['resources'], transfer_rewards: ['resources'],
  fog_revealed: ['cells'], mechanism_progress: ['siteId', 'ok'], battle_report: ['reportId'], cage_opened: ['siteId'],
  escort_arrived: ['siteId'], boss_unlocked: [], boss_started: [], boss_phase: ['phase'], campaign_completed: [], intro_present: [],
};

class CheckedJourney extends Journey {
  async step(label, fn) {
    const result = await super.step(label, fn);
    const s = await this.client.state();
    checkAdventure(s.adventure);
    // cues committed by settle during polling are kept in the projected ring buffer
    this.ring ??= new Map();
    for (const e of s.adventure.recentEvents) this.ring.set(e.seq, e);
    if (result?.adventure) checkAdventure(result.adventure);
    this.validated = (this.validated ?? 0) + 1;
    return result;
  }
}

test('CONTRACT §3 shape holds at every step of a full campaign; §4 events carry their fields', {timeout: 300000}, async () => {
  const {realm, client} = await freshRealm({idPrefix: 'contract'});
  try {
    const locked = await client.state();
    checkAdventure(locked.adventure);
    assert.equal(locked.adventure.access.unlocked, false);
    assert.deepEqual(locked.adventure.pois, []);
    assert.equal(locked.adventure.horse.visible, false);
    await client.hall(2);
    checkAdventure((await client.state()).adventure);
    await client.hall(3);
    await client.army({'ENG-06': 6000});
    const unlocked = checkAdventure((await client.state()).adventure);
    assert.equal(unlocked.intro.offer, true);
    const intro = await client.send(client.intro('start_intro'));
    assert.equal(intro.status, 200);
    assert.ok(intro.body.events.some(e => e.type === 'intro_present'));
    checkAdventure(intro.body.adventure);
    const journey = new CheckedJourney(realm, client);
    await journey.prologue({'ENG-06': 6000});
    // mid-move projection: move + horse lead + live position
    const moving = await client.ok('move', {targetId: 'lf_site_01'});
    checkAdventure(moving.adventure);
    checkMove(moving.adventure.horse.move, 'horse.move');
    assert.ok(moving.adventure.horse.move.arriveAt < moving.adventure.squad.move.arriveAt, 'the horse leads and waits');
    // Commit happens lazily on the next request: a command 2 s into the move settles the first
    // traversal checkpoint and returns its cues (fog_revealed with the new cell indices).
    await client.clock(moving.adventure.squad.move.departAt + 2000);
    const mid = await client.ok('set_auto_refill', {enabled: false});
    checkAdventure(mid.adventure);
    assert.notDeepEqual(mid.adventure.squad.position, moving.adventure.squad.position);
    const fogEvent = mid.events.find(e => e.type === 'fog_revealed');
    assert.ok(fogEvent && fogEvent.cells.length === fogEvent.count && fogEvent.cells.every(i => Number.isSafeInteger(i) && i >= 0 && i < 3136));
    journey.events.push(...mid.events);
    const arrived = await client.advanceTo(moving.adventure.squad.move.arriveAt + 1);
    assert.equal(arrived.adventure.squad.node, 'lf_site_01');
    assert.ok(arrived.adventure.recentEvents.some(e => e.type === 'squad_arrived' && e.targetId === 'lf_site_01'));
    for (const site of SITES) {
      if (site.id === 'lf_site_07') await client.hall(5);
      await journey.completeSite(site.id);
    }
    await journey.step('claim', () => client.ok('claim_rewards'));
    await journey.formAtHome();
    await journey.moveTo('lf_boss_ancient_maw');
    await journey.step('begin_boss', () => client.ok('begin_boss'));
    const fight = await client.ok('engage_boss');
    checkAdventure(fight.adventure);
    assert.equal(fight.adventure.boss.state, 'active');
    const b = fight.adventure.battle;
    const fury = b.timeline.find(e => e.type === 'phase' && e.phase === 'fury');
    const midFight = await client.advanceTo(b.startedAt + Math.ceil(fury.t * 1000) + 10);
    checkAdventure(midFight.adventure);
    assert.equal(midFight.adventure.boss.phase, 'fury');
    assert.ok(midFight.adventure.boss.hp < 78000 && midFight.adventure.battle.outcome === 'pending');
    assert.equal(midFight.adventure.horse.mood, 'alert');
    await client.advanceTo(b.endsAt + 1);
    const done = await journey.step('finish_boss', () => client.ok('finish_boss'));
    checkAdventure(done.adventure);
    assert.equal(done.adventure.boss.state, 'defeated');
    assert.equal(done.adventure.campaign.phase, 'completed');
    assert.ok(journey.validated > 150);
    // §4: every contract event type appeared with its fields, deduplicable by revision+type
    const seen = new Set();
    const ringEvents = [...journey.ring.values()].filter(e => e.type !== 'fog_revealed'); // ring keeps fog as a count only
    for (const e of [...journey.events, ...intro.body.events, ...fight.events, ...ringEvents]) {
      assert.ok(Number.isSafeInteger(e.revision) && Number.isSafeInteger(e.seq), 'revision/seq on ' + e.type);
      if (EVENT_FIELDS[e.type]) {
        for (const k of EVENT_FIELDS[e.type]) assert.ok(Object.hasOwn(e, k), e.type + '.' + k);
        seen.add(e.type);
      }
    }
    for (const type of ['horse_joined', 'task_completed', 'reward_escrowed', 'transfer_rewards', 'fog_revealed', 'mechanism_progress',
      'battle_report', 'cage_opened', 'escort_arrived', 'boss_unlocked', 'boss_started', 'boss_phase', 'campaign_completed', 'intro_present']) {
      assert.ok(seen.has(type), 'event ' + type + ' observed');
    }
  } finally {
    await realm.destroy();
  }
});
