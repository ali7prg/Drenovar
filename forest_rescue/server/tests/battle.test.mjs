// Deterministic seeded battles: guardians and the 3-phase boss with exact attack timings.
import test from 'node:test';
import assert from 'node:assert/strict';
import {simulateGuardian, simulateBoss, splitLosses, knockedUntil, stateAt} from '../src/battle.mjs';
import {creatureSpec} from '../src/catalog.mjs';
import {BOSS} from '../src/content.mjs';
import {data} from '../src/vendor.mjs';

const knocked = r => Object.values(r.totalKnocked).reduce((a, b) => a + b, 0);

test('same inputs → identical report; the seed only jitters details', () => {
  const spec = creatureSpec('tenerys', 2);
  const a = simulateGuardian({units: {'ENG-06': 400}, spec, seed: 42});
  const b = simulateGuardian({units: {'ENG-06': 400}, spec, seed: 42});
  assert.deepEqual(a, b);
  const c = simulateGuardian({units: {'ENG-06': 400}, spec, seed: 43});
  assert.equal(c.outcome, a.outcome);
  assert.notDeepEqual(c.timeline, a.timeline);
});

test('outcome follows the real troop stats: more/better units win, a starter squad loses', () => {
  const spec = creatureSpec('tenerys', 1);
  assert.equal(simulateGuardian({units: {'ENG-09': 5}, spec, seed: 1}).outcome, 'defeat');
  assert.equal(simulateGuardian({units: {'ENG-09': 600}, spec, seed: 1}).outcome, 'victory');
  const recruits = simulateGuardian({units: {'ENG-09': 400}, spec, seed: 7});
  const knights = simulateGuardian({units: {'ENG-06': 120}, spec, seed: 7}); // same power as 400 recruits
  assert.equal(knights.outcome, 'victory');
  assert.ok(knocked(knights) * 200 < knocked(recruits) * 60 * 2, 'stronger stat profile loses less power');
  for (const species of ['tenerys', 'velkor', 'kamneklyk', 'dragor']) for (const level of [1, 2, 3]) {
    const r = simulateGuardian({units: {'ENG-06': 3000}, spec: creatureSpec(species, level), seed: level});
    assert.equal(r.outcome, 'victory', species + level);
    assert.ok(r.timeline.some(e => e.type === 'death' && e.actor === 'guardian'));
    assert.ok(r.timeline.some(e => e.type === 'attack' && e.actor === 'squad'));
    assert.ok(r.timeline.some(e => e.type === 'hit' && e.target === 'guardian'));
    assert.ok(r.timeline.some(e => e.type === 'telegraph') && r.timeline.some(e => e.type === 'ability'));
    assert.ok(r.durationMs >= 5000, 'a guardian cannot be one-shot');
    for (let i = 1; i < r.timeline.length; i++) assert.ok(r.timeline[i].t >= r.timeline[i - 1].t);
  }
});

test('boss: hunt → fury → last_stand with the exact telegraph/active/recovery seconds of campaign.json', () => {
  const r = simulateBoss({units: {'ENG-06': 3000}, boss: BOSS, seed: 99});
  assert.equal(r.outcome, 'victory');
  const phases = r.timeline.filter(e => e.type === 'phase').map(e => e.phase);
  assert.deepEqual(phases, ['hunt', 'fury', 'last_stand']);
  const cfg = data.campaign.boss.attacks;
  const telegraphs = r.timeline.filter(e => e.type === 'telegraph');
  assert.ok(telegraphs.length >= 3);
  for (const tg of telegraphs) {
    const a = cfg[tg.attack];
    assert.equal(tg.telegraphSeconds, a.telegraphSeconds);
    assert.equal(tg.recoverySeconds, a.recoverySeconds);
    const attacks = r.timeline.filter(e => e.type === 'attack' && e.actor === 'boss' && e.attack === tg.attack && e.t >= tg.t && e.t <= tg.t + a.telegraphSeconds + 1.0 + 1e-6);
    if (!attacks.length) continue; // fight ended during this telegraph
    assert.ok(Math.abs(attacks[0].t - (tg.t + a.telegraphSeconds)) < 0.011, tg.attack + ' active starts after its telegraph');
    if (tg.attack === 'stomp_waves') {
      assert.equal(attacks.length, 2);
      assert.ok(Math.abs(attacks[1].t - attacks[0].t - 0.9) < 0.011, 'wave starts 0.9 s apart');
    }
  }
  // every phase shows at least one of its own attacks before it can end
  const byPhase = {};
  for (const tg of telegraphs) (byPhase[tg.phase] ??= []).push(tg.attack);
  for (const p of BOSS.phases) assert.ok(byPhase[p.id]?.every(a => p.attacks.includes(a)), p.id);
  const at = stateAt(r.timeline, r.hpMax, 0);
  assert.deepEqual(at, {hp: 78000, phase: 'hunt'});
  // an under-strength squad loses without an unwarned instant kill
  const weak = simulateBoss({units: {'ENG-09': 50}, boss: BOSS, seed: 3});
  assert.equal(weak.outcome, 'defeat');
  const firstHit = weak.timeline.find(e => e.type === 'hit' && e.actor === 'boss');
  const tg = weak.timeline.find(e => e.type === 'telegraph');
  assert.ok(firstHit.t >= tg.t + 2.4, 'damage only lands after a telegraph');
});

test('losses split wounded/dead deterministically; retreat counts only hits so far', () => {
  assert.deepEqual(splitLosses({'ENG-06': 10, 'ENG-09': 1}, 'victory'), {wounded: {'ENG-06': 6, 'ENG-09': 1}, dead: {'ENG-06': 4}});
  assert.deepEqual(splitLosses({'ENG-06': 10}, 'defeat'), {wounded: {'ENG-06': 4}, dead: {'ENG-06': 6}});
  const r = simulateGuardian({units: {'ENG-09': 900}, spec: creatureSpec('velkor', 2), seed: 5});
  const mid = r.knocks[1].t;
  const partial = knockedUntil(r.knocks, mid);
  assert.ok(Object.values(partial)[0] < Object.values(r.totalKnocked)[0]);
});
