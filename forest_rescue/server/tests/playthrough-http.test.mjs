// Full campaign over HTTP against the local realm: prologue, all 12 sites (all 4 mechanism
// kinds), the 3-phase boss and reward claims — restarting the realm from its persisted JSON
// snapshot after EVERY step and asserting the complete public state survived unchanged.
import test from 'node:test';
import assert from 'node:assert/strict';
import {freshRealm} from './helpers/realm.mjs';
import {Journey, SITES, ECONOMY, RESOURCES, bagSum} from './helpers/journey.mjs';

const TOTALS = {food: 2325000, wood: 2385000, stone: 1590000, iron: 1025000, coins: 190000};

test('complete campaign: 12 sites, 4 mechanisms, boss, exact 7,515,000 reward, restart after every step', {timeout: 600000}, async () => {
  const {realm, client} = await freshRealm({idPrefix: 'journey'});
  try {
    const journey = new Journey(realm, client, {restartEachStep: true});
    await client.hall(3);
    await client.army({'ENG-06': 6000});
    const initial = await client.state();
    assert.equal(initial.adventure.access.unlocked, true);
    assert.equal(initial.adventure.campaign.phase, 'prologue');

    await journey.prologue({'ENG-06': 6000});
    let s = await client.state();
    assert.equal(s.adventure.campaign.phase, 'rescue');
    assert.deepEqual(s.adventure.escrow.earned, ECONOMY.prologue);

    const mechanisms = new Set();
    for (const site of SITES) {
      if (site.id === 'lf_site_07') {
        // Level-III guardians keep their hall-V requirement: upgrade the real town hall
        // through the construction order (paid from claimed rewards, completes on settle).
        for (const level of [3, 4]) {
          await journey.step('hall-upgrade:' + level, async () => {
            const st = await client.state();
            const hall = st.city.buildings.find(b => b.type === 'ECO-05');
            assert.equal(hall.level, level);
            const r = await client.send({kind: 'kingdom', action: 'upgrade', buildingId: hall.id, expectedLevel: level});
            assert.equal(r.status, 200, JSON.stringify(r.body));
            const order = r.body.city.kingdom.order;
            assert.equal(order.level, level + 1);
            assert.equal(r.body.adventure.access.hallLevel, level, 'a queued upgrade does not count');
            const done = await client.advanceTo(order.endsAt + 1);
            assert.equal(done.city.buildings.find(b => b.type === 'ECO-05').level, level + 1);
            assert.equal(done.adventure.access.hallLevel, level + 1);
            return r.body;
          });
        }
      }
      await journey.completeSite(site.id);
      mechanisms.add(site.variation);
      s = await client.state();
      const poi = s.adventure.pois.find(p => p.id === site.id);
      assert.equal(poi.step, 5);
      assert.equal(poi.cagePose, 'open');
      assert.ok(poi.captives.every(c => c.state === 'home'));
      assert.equal(poi.guardian.state, 'defeated');
      assert.equal(poi.artifact.state, 'in_socket');
      // Keep the warehouse moving: claim what fits (cap is per resource; remainder stays).
      await journey.step('claim:' + site.id, () => client.ok('claim_rewards'));
    }
    assert.deepEqual([...mechanisms].sort(), ['paired_latch', 'rune_lock', 'trail_cache', 'winch_sequence']);

    s = await client.state();
    assert.equal(s.adventure.campaign.phase, 'boss_unlocked');
    assert.equal(s.adventure.campaign.rescuedCount, 36);
    assert.equal(new Set(s.adventure.campaign.rescuedIds).size, 36);
    assert.equal(s.adventure.boss.state, 'available');

    // Boss: hall V, arrival at the arena, 3 phases, verified final report.
    await journey.formAtHome();
    await journey.moveTo('lf_boss_ancient_maw');
    const begun = await journey.step('begin_boss', () => client.ok('begin_boss'));
    assert.ok(begun.events.some(e => e.type === 'boss_started'));
    const fight = await journey.battle('engage_boss');
    const timeline = fight.adventure.battle.timeline;
    assert.deepEqual([...new Set(timeline.filter(e => e.type === 'phase').map(e => e.phase))], ['hunt', 'fury', 'last_stand']);
    assert.ok(timeline.some(e => e.type === 'telegraph') && timeline.some(e => e.type === 'recovery') && timeline.some(e => e.type === 'death' && e.actor === 'boss'));
    s = await client.state();
    assert.equal(s.adventure.boss.state, 'defeated');
    assert.equal(s.adventure.campaign.phase, 'boss_active');
    const final = await journey.step('finish_boss', () => client.ok('finish_boss'));
    assert.ok(final.events.some(e => e.type === 'campaign_completed'));
    s = final;
    assert.equal(s.adventure.campaign.phase, 'completed');
    assert.equal(s.adventure.nextTask, null);

    // Exactly the guaranteed campaign total — ordinary battle loot is a separate line.
    const earned = s.adventure.escrow.earned;
    assert.deepEqual(earned, TOTALS);
    assert.deepEqual(earned, ECONOMY.totals);
    assert.equal(bagSum(earned), 7515000);
    for (const r of RESOURCES) assert.equal(s.adventure.escrow.claimed[r] + s.adventure.escrow.pending[r], earned[r]);
    const awards = journey.events.filter(e => e.type === 'reward_escrowed');
    assert.equal(awards.length, 62);
    assert.equal(new Set(awards.map(e => e.awardId)).size, 62);
    assert.equal(journey.events.filter(e => e.type === 'task_completed').length, 60);
    const victories = s.reports.filter(r => r.kind === 'adventure' && r.outcome === 'victory');
    assert.equal(victories.length, 13);
    const loot = victories.filter(r => r.siteId !== 'lf_boss_ancient_maw').reduce((n, r) => n + (r.rewards.resources.food ?? 0), 0);
    assert.ok(loot > 0, 'ordinary first-victory loot was credited separately');
    assert.ok(Object.keys(s.items).length > 0, 'ordinary loot items');
    // Losses were applied to the real army like ordinary hunts.
    assert.ok((s.city.military.owned['ENG-06'] ?? 0) < 6000);
    assert.ok(journey.restartChecks > 150, 'restart checks: ' + journey.restartChecks);
    console.log('# playthrough steps', journey.steps, 'restart checks', journey.restartChecks, 'events', journey.events.length,
      'army left', JSON.stringify(s.city.military.owned), 'wounded', JSON.stringify(s.wounded));
  } finally {
    await realm.destroy();
  }
});
