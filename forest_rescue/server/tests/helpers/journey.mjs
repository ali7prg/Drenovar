// Scripted playthrough driver over HTTP. Every step can be followed by a full realm restart
// from the persisted snapshot with a deep-equality check of the whole public state.
import assert from 'node:assert/strict';
import {data} from '../../src/vendor.mjs';

export const SITES = data.campaign.sites;
export const ECONOMY = data.economy;
export const RESOURCES = ECONOMY.resources;

export function taskReward(siteId, taskId) {
  const n = Number(siteId.slice(-2));
  const mult = ECONOMY.siteMultiplierByNumber[n - 1];
  return Object.fromEntries(RESOURCES.map(r => [r, ECONOMY.baseTaskRewards[taskId][r] * mult]));
}

export function bagSum(bag) {
  return RESOURCES.reduce((n, r) => n + bag[r], 0);
}

export class Journey {
  constructor(realm, client, {restartEachStep = false} = {}) {
    this.realm = realm;
    this.client = client;
    this.restartEachStep = restartEachStep;
    this.steps = 0;
    this.restartChecks = 0;
    this.events = [];
  }

  async step(label, fn) {
    const result = await fn();
    this.steps++;
    if (result?.events) this.events.push(...result.events.map(e => ({...e, step: label})));
    if (this.restartEachStep) {
      const before = await this.client.state();
      await this.realm.restart();
      const after = await this.client.state();
      assert.deepEqual(after, before, 'state changed across restart after step ' + label);
      this.restartChecks++;
    }
    return result;
  }

  async state() {
    return this.client.state();
  }

  async moveTo(targetId) {
    return this.step('move:' + targetId, async () => {
      const r = await this.client.ok('move', {targetId});
      const move = r.adventure.squad.move;
      if (move) {
        assert.equal(move.targetId, targetId);
        assert.ok(move.arriveAt > move.departAt && move.path.length >= 2);
        // Not there yet: tasks needing arrival are refused until the server commits it.
        await this.client.advanceTo(move.arriveAt + 1);
      }
      const s = await this.client.state();
      assert.equal(s.adventure.squad.node, targetId);
      assert.equal(s.adventure.squad.move, null);
      return r;
    });
  }

  async task(siteId, taskId) {
    return this.step('task:' + siteId + ':' + taskId, async () => {
      const before = (await this.client.state()).adventure.escrow.earned;
      const r = await this.client.ok('attempt_task', {siteId, taskId});
      const done = r.events.find(e => e.type === 'task_completed');
      assert.ok(done, 'task_completed for ' + siteId + ' ' + taskId);
      assert.deepEqual(done.reward, taskReward(siteId, taskId));
      const after = r.adventure.escrow.earned;
      for (const res of RESOURCES) assert.equal(after[res] - before[res], taskReward(siteId, taskId)[res]);
      return r;
    });
  }

  async input(siteId, symbol) {
    return this.step('mech:' + siteId + ':' + symbol, async () => {
      const r = await this.client.ok('mechanism_input', {siteId, symbol});
      const ev = r.events.find(e => e.type === 'mechanism_progress');
      assert.ok(ev && ev.ok === true, 'mechanism progress ok ' + symbol);
      return r;
    });
  }

  async formAtHome() {
    const s = await this.client.state();
    const healthy = s.healthy, reserved = s.adventure.squad.units;
    const units = {};
    for (const [id, n] of Object.entries(healthy)) units[id] = n + (reserved[id] ?? 0);
    for (const [id, n] of Object.entries(reserved)) units[id] ??= n;
    return this.step('form_squad', () => this.client.ok('form_squad', {units}));
  }

  async battle(action, extra) {
    return this.step(action + ':' + (extra?.siteId ?? 'boss'), async () => {
      const r = await this.client.ok(action, extra);
      const b = r.adventure.battle;
      assert.equal(b.outcome, 'pending');
      assert.equal(r.adventure.squad.busy, 'battle');
      assert.ok(b.timeline.length > 3 && b.endsAt > b.startedAt);
      const s = await this.client.advanceTo(b.endsAt + 1);
      assert.equal(s.adventure.battle.reportId, b.reportId);
      assert.equal(s.adventure.battle.outcome, 'victory', 'battle won ' + JSON.stringify(extra));
      assert.ok(s.reports.some(rep => rep.id === b.reportId && rep.outcome === 'victory'));
      return r;
    });
  }

  async prologue(units) {
    await this.step('form_squad', () => this.client.ok('form_squad', {units}));
    await this.moveTo('lf_horse_origin');
    const r = await this.step('discover_horse', () => this.client.ok('discover_horse'));
    assert.ok(r.events.some(e => e.type === 'horse_joined'));
    return r;
  }

  async completeSite(siteId) {
    const site = SITES.find(s => s.id === siteId);
    const key = site.artifact.id, solution = site.artifact.puzzle.solution;
    const s0 = await this.client.state();
    if (s0.adventure.squad.node === 'lf_home_reception') await this.formAtHome();
    await this.moveTo(siteId);
    await this.task(siteId, 'discover');
    if (site.variation === 'trail_cache') {
      await this.moveTo(key); // the only way to the cache passes the three landmarks in order
      for (const symbol of solution) await this.input(siteId, symbol);
    } else if (site.variation === 'paired_latch') {
      const r = await this.step('occupy:' + siteId, () => this.client.ok('occupy_plates', {siteId}));
      const poi = r.adventure.pois.find(p => p.id === siteId);
      await this.client.advanceTo(poi.mechanism.plates.readyAt + 1);
      for (const symbol of solution) await this.input(siteId, symbol);
      await this.moveTo(key);
    } else {
      for (const symbol of solution) await this.input(siteId, symbol);
      await this.moveTo(key);
    }
    await this.task(siteId, 'recover_artifact');
    await this.moveTo(siteId + ':guardian');
    await this.battle('engage_guardian', {siteId});
    await this.task(siteId, 'defeat_guardian');
    await this.moveTo(siteId + ':cage');
    const unlocked = await this.task(siteId, 'unlock_cage');
    assert.ok(unlocked.events.some(e => e.type === 'cage_opened' && e.siteId === siteId));
    await this.step('escort:' + siteId, async () => {
      const r = await this.client.ok('escort_start', {siteId});
      assert.equal(r.adventure.escort.siteId, siteId);
      assert.equal(r.adventure.escort.state, 'walking');
      assert.equal(r.adventure.squad.busy, 'escort');
      assert.deepEqual(r.adventure.escort.captiveIds, site.captives.map(c => c.id));
      const s = await this.client.advanceTo(r.adventure.escort.arriveAt + 1);
      assert.equal(s.adventure.escort.state, 'home');
      assert.equal(s.adventure.squad.node, 'lf_home_reception');
      return r;
    });
    await this.task(siteId, 'escort_home');
  }
}
