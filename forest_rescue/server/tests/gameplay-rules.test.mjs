// Server-built trust: arrival, landmarks on the committed path, simultaneous plates, real
// battles (defeat/retreat keep progress), escorts, stop/redirect, pause, squad rules.
import test from 'node:test';
import assert from 'node:assert/strict';
import {adventurer} from './helpers/setup.mjs';

const code = async (p, status, error) => {
  const r = await p;
  assert.equal(r.status, status, JSON.stringify(r.body).slice(0, 300));
  assert.equal(r.body.error, error);
  assert.ok(typeof r.body.message === 'string' && r.body.message.length > 5);
  return r.body;
};

test('order, arrival and proofs: nothing completes without the server records', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'rules'});
  const A = (action, extra) => client.send(client.adv(action, extra));
  try {
    const moving = await client.ok('move', {targetId: 'lf_site_01'});
    await code(A('attempt_task', {siteId: 'lf_site_01', taskId: 'discover'}), 409, 'NOT_ARRIVED');
    await client.advanceTo(moving.adventure.squad.move.arriveAt + 1);
    await code(A('attempt_task', {siteId: 'lf_site_01', taskId: 'unlock_cage'}), 409, 'TASK_OUT_OF_ORDER');
    await code(A('attempt_task', {siteId: 'lf_site_04', taskId: 'discover'}), 409, 'ACT_LOCKED');
    await code(A('begin_boss'), 409, 'BOSS_LOCKED');
    await code(A('engage_boss'), 409, 'BOSS_LOCKED');
    await journey.task('lf_site_01', 'discover');
    // trail cache: a landmark counts only once the committed path has passed it
    await code(A('mechanism_input', {siteId: 'lf_site_01', symbol: 'split_birch'}), 409, 'MECHANISM_NOT_READY');
    await journey.moveTo('lf_site_01:landmark:split_birch');
    await client.ok('mechanism_input', {siteId: 'lf_site_01', symbol: 'split_birch'});
    await code(A('mechanism_input', {siteId: 'lf_site_01', symbol: 'white_moss'}), 409, 'MECHANISM_NOT_READY');
    await journey.moveTo('lf_key_01');
    await code(A('attempt_task', {siteId: 'lf_site_01', taskId: 'recover_artifact'}), 409, 'MECHANISM_NOT_READY');
    const wrong = await client.ok('mechanism_input', {siteId: 'lf_site_01', symbol: 'fallen_trunk'});
    assert.deepEqual(wrong.events.filter(e => e.type === 'mechanism_progress').map(e => e.ok), [false]);
    const poi = wrong.adventure.pois.find(p => p.id === 'lf_site_01');
    assert.deepEqual([poi.mechanism.progress, poi.mechanism.lastResult], [0, 'wrong']);
    assert.equal(wrong.adventure.campaign.sites[0].step, 1, 'a wrong input never costs progress');
    for (const s of ['split_birch', 'white_moss', 'fallen_trunk']) await client.ok('mechanism_input', {siteId: 'lf_site_01', symbol: s});
    await journey.moveTo('lf_site_01');
    await code(A('attempt_task', {siteId: 'lf_site_01', taskId: 'recover_artifact'}), 409, 'NOT_ARRIVED');
    await journey.moveTo('lf_key_01');
    await journey.task('lf_site_01', 'recover_artifact');
    await code(A('attempt_task', {siteId: 'lf_site_01', taskId: 'defeat_guardian'}), 409, 'NO_BATTLE_PROOF');
    await code(A('attempt_task', {siteId: 'lf_site_01', taskId: 'unlock_cage'}), 409, 'TASK_OUT_OF_ORDER');
    await code(A('engage_guardian', {siteId: 'lf_site_02'}), 409, 'TASK_OUT_OF_ORDER');
    await journey.moveTo('lf_horse_origin');
    await code(A('engage_guardian', {siteId: 'lf_site_01'}), 409, 'NOT_ARRIVED');
  } finally {
    await realm.destroy();
  }
});

test('defeat and retreat keep keys, people and rewards; losses hit the real army; a wiped squad returns home', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'defeat', army: {'ENG-01': 5, 'ENG-06': 3000}, prologue: false});
  try {
    await journey.prologue({'ENG-01': 5});
    await journey.completeSite('lf_site_01', {stopBefore: 'engage'});
    const before = await client.state();
    const fight = await client.ok('engage_guardian', {siteId: 'lf_site_01'});
    assert.equal(fight.adventure.squad.busy, 'battle');
    await code(client.send(client.adv('move', {targetId: 'lf_site_01'})), 409, 'SQUAD_BUSY');
    const lost = await client.advanceTo(fight.adventure.battle.endsAt + 1);
    assert.equal(lost.adventure.battle.outcome, 'defeat');
    assert.equal(lost.reports.at(-1).outcome, 'defeat');
    assert.deepEqual(lost.adventure.escrow, before.adventure.escrow);
    assert.deepEqual(lost.adventure.campaign.sites[0], before.adventure.campaign.sites[0], 'key kept, step kept');
    assert.equal(lost.adventure.pois.find(p => p.id === 'lf_site_01').guardian.state, 'alive');
    const dead = lost.adventure.battle.losses.dead['ENG-01'] ?? 0, wounded = lost.adventure.battle.losses.wounded['ENG-01'] ?? 0;
    assert.equal(dead + wounded, 5);
    assert.equal(lost.city.military.owned['ENG-01'] ?? 0, before.city.military.owned['ENG-01'] - dead);
    assert.equal(lost.wounded['ENG-01'] ?? 0, wounded);
    assert.equal(lost.adventure.squad.node, 'lf_home_reception', 'nobody left: the squad record returns home');
    assert.deepEqual(lost.adventure.squad.units, {});
    // Re-form at home with real healthy knights, walk back, retreat mid-fight, then win.
    await code(client.send(client.adv('form_squad', {units: {'ENG-06': 3001}})), 409, 'UNITS_UNAVAILABLE');
    await journey.step('form', () => client.ok('form_squad', {units: {'ENG-06': 3000}}));
    await journey.moveTo('lf_site_01:guardian');
    const second = await client.ok('engage_guardian', {siteId: 'lf_site_01'});
    await client.advance(2000);
    const fled = await client.ok('retreat');
    assert.equal(fled.adventure.battle.outcome, 'retreat');
    assert.equal(fled.adventure.battle.timeline.at(-1).type, 'retreat');
    assert.ok(fled.adventure.battle.endsAt < second.adventure.battle.endsAt);
    assert.equal(fled.adventure.squad.busy, null);
    assert.equal(fled.adventure.pois.find(p => p.id === 'lf_site_01').guardian.state, 'alive');
    await journey.battle('engage_guardian', {siteId: 'lf_site_01'});
    await journey.task('lf_site_01', 'defeat_guardian');
    assert.equal((await client.state()).reports.filter(r => r.siteId === 'lf_site_01').map(r => r.adventureOutcome).join(), 'defeat,retreat,victory');
  } finally {
    await realm.destroy();
  }
});

test('paired latch: needs two members held simultaneously; moving away releases the plates', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'latch', army: {'ENG-06': 3000, 'ENG-01': 1}, prologue: false});
  try {
    await journey.prologue({'ENG-06': 3000});
    for (const id of ['lf_site_01', 'lf_site_02', 'lf_site_03']) await journey.completeSite(id);
    await journey.step('form1', () => client.ok('form_squad', {units: {'ENG-01': 1}}));
    await journey.moveTo('lf_site_04');
    await journey.task('lf_site_04', 'discover');
    await code(client.send(client.adv('occupy_plates', {siteId: 'lf_site_04'})), 409, 'PLATES_NOT_OCCUPIED');
    await code(client.send(client.adv('mechanism_input', {siteId: 'lf_site_04', symbol: 'left_plate'})), 409, 'PLATES_NOT_OCCUPIED');
    await journey.moveTo('lf_home_reception');
    await journey.step('form2', () => client.ok('form_squad', {units: {'ENG-06': 2}}));
    await journey.moveTo('lf_site_04');
    const occ = await client.ok('occupy_plates', {siteId: 'lf_site_04'});
    const plates = occ.adventure.pois.find(p => p.id === 'lf_site_04').mechanism.plates;
    assert.equal(plates.state, 'walking');
    assert.equal(occ.adventure.squad.busy, 'mechanism');
    await code(client.send(client.adv('mechanism_input', {siteId: 'lf_site_04', symbol: 'left_plate'})), 409, 'PLATES_NOT_OCCUPIED');
    await client.advanceTo(plates.readyAt);
    await client.ok('mechanism_input', {siteId: 'lf_site_04', symbol: 'left_plate'});
    await client.ok('mechanism_input', {siteId: 'lf_site_04', symbol: 'right_plate'});
    await journey.moveTo('lf_site_04:guardian'); // walking away releases both plates
    const released = await client.state();
    assert.equal(released.adventure.pois.find(p => p.id === 'lf_site_04').mechanism.plates.state, 'free');
    await code(client.send(client.adv('mechanism_input', {siteId: 'lf_site_04', symbol: 'center_latch'})), 409, 'PLATES_NOT_OCCUPIED');
    const again = await client.ok('occupy_plates', {siteId: 'lf_site_04'});
    await client.advanceTo(again.adventure.pois.find(p => p.id === 'lf_site_04').mechanism.plates.readyAt);
    const solved = await client.ok('mechanism_input', {siteId: 'lf_site_04', symbol: 'center_latch'});
    const m = solved.adventure.pois.find(p => p.id === 'lf_site_04').mechanism;
    assert.deepEqual([m.solved, m.progress], [true, 3]);
    assert.equal(solved.adventure.squad.busy, null, 'plates released after solving');
  } finally {
    await realm.destroy();
  }
});

test('higher guardians keep their hall requirement (HALL_LEVEL_TOO_LOW, not a silent lock)', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'hall5'});
  try {
    for (const id of ['lf_site_01', 'lf_site_02', 'lf_site_03', 'lf_site_04', 'lf_site_05', 'lf_site_06']) await journey.completeSite(id);
    await journey.completeSite('lf_site_07', {stopBefore: 'engage'});
    const r = await code(client.send(client.adv('engage_guardian', {siteId: 'lf_site_07'})), 403, 'HALL_LEVEL_TOO_LOW');
    assert.equal(r.detail.requiredHall, 5);
    assert.match(r.message, /ратуша уровня 5/);
    await client.hall(5);
    await journey.battle('engage_guardian', {siteId: 'lf_site_07'});
  } finally {
    await realm.destroy();
  }
});

test('stop at the next graph node, redirect, pause, escort rules, squad reservation', async () => {
  const {realm, client, journey} = await adventurer({idPrefix: 'move', army: {'ENG-06': 3000}});
  try {
    const s0 = await client.state();
    assert.equal(s0.healthy['ENG-06'] ?? 0, 0, 'reserved squad units are not free');
    assert.equal(s0.healthy['ENG-01'], 5, 'starter recruits stay free at home');
    await code(client.send(client.adv('form_squad', {units: {'ENG-01': 1}})), 409, 'SQUAD_BUSY');
    const go = await client.ok('move', {targetId: 'lf_site_03'});
    await client.clock(go.adventure.squad.move.departAt + 3000);
    const stopped = await client.ok('stop');
    const target = stopped.adventure.squad.move.targetId;
    assert.match(target, /^lf_trail_[a-z0-9_]+#\d+$/);
    assert.ok(stopped.adventure.squad.move.arriveAt - stopped.adventure.serverTime < 400, 'stops at the next node (≤0.5 units)');
    const at = await client.advance(1000);
    assert.equal(at.adventure.squad.node, target);
    const redirect = await client.ok('move', {targetId: 'lf_horse_origin'});
    assert.equal(redirect.adventure.squad.move.path[0].x, at.adventure.squad.position.x);
    await client.advanceTo(redirect.adventure.squad.move.arriveAt);
    await client.ok('pause');
    await code(client.send(client.adv('move', {targetId: 'lf_site_01'})), 409, 'CAMPAIGN_PAUSED');
    await client.ok('move', {targetId: 'lf_home_reception'}); // going home is always allowed
    await client.ok('claim_rewards');
    await client.ok('resume');
    await journey.completeSite('lf_site_01', {stopBefore: 'escort'});
    await code(client.send(client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'escort_home'})), 409, 'ESCORT_NOT_ARRIVED');
    const esc = await client.ok('escort_start', {siteId: 'lf_site_01'});
    assert.deepEqual(esc.adventure.pois.find(p => p.id === 'lf_site_01').captives.map(c => c.state), ['escorted', 'escorted', 'escorted']);
    await code(client.send(client.adv('stop')), 409, 'SQUAD_BUSY');
    await code(client.send(client.adv('move', {targetId: 'lf_site_02'})), 409, 'SQUAD_BUSY');
    await code(client.send(client.adv('attempt_task', {siteId: 'lf_site_01', taskId: 'escort_home'})), 409, 'ESCORT_NOT_ARRIVED');
    const twice = await client.ok('escort_start', {siteId: 'lf_site_01'});
    assert.equal(twice.adventure.escort.arriveAt, esc.adventure.escort.arriveAt, 'escort_start is idempotent');
    assert.ok(esc.adventure.escort.move.speed <= 1.6, 'civilians walk slower');
    const home = await client.advanceTo(esc.adventure.escort.arriveAt);
    assert.equal(home.adventure.escort.state, 'home');
    assert.deepEqual(home.adventure.pois.find(p => p.id === 'lf_site_01').captives.map(c => c.state), ['home', 'home', 'home']);
    const done = await client.ok('attempt_task', {siteId: 'lf_site_01', taskId: 'escort_home'});
    assert.deepEqual(done.adventure.campaign.rescuedIds, ['lf_captive_01_a', 'lf_captive_01_b', 'lf_captive_01_c']);
    assert.equal(done.adventure.escort, null);
  } finally {
    await realm.destroy();
  }
});
