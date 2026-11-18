// integration/core-adapter.mjs exercised inside a stand-in core that follows the documented
// v92 CoreGameServer flow: tx → readyPlayer62 (settle) → [adventure gate+receipt+branch]
// → legacy receipt SELECT → legacy branches → putPlayer + INSERT receipt, with snapshot CAS.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createV92Adventure, sanitizeLegacyImport} from '../integration/core-adapter.mjs';
import {hallLevel, balance, capacity} from '../src/city-rules.mjs';
import {creatureSpec} from '../src/catalog.mjs';
import {createLocalPorts, healthyUnits} from '../src/local-ports.mjs';
import {newPlayer} from '../local-realm/starter.mjs';
import {checkAdventure} from './helpers/contract-schema.mjs';

const local = createLocalPorts();
const adventure = createV92Adventure({hallLevel, balance, capacity, creatureSpec, healthyUnits,
  applyLosses: local.applyLosses, applyLoot: local.applyLoot, pushReport: local.pushReport});

class StandInCore {
  constructor() { this.db = {revision: 0, players: {}, commands: {}}; this.now = 1794370000000; }
  async tx(fn) { // hosted.mjs: whole-realm snapshot, UPDATE … WHERE revision=?
    const snap = structuredClone(this.db);
    const out = await fn(snap);
    if (out.abort) return out;
    if (snap.revision !== this.db.revision) throw new Error('CAS');
    snap.revision++;
    this.db = snap;
    return out;
  }
  async readyPlayer62(snap, id) {
    const p = snap.players[id];
    const settled = await adventure.settle(p, this.now); // core.mjs:35 settle hook (after settleKingdom)
    this.settleEvents = settled.events; // surfaced in the command response (also kept in adventure.recentEvents)
    return p;
  }
  publicState(p) {
    return {playerId: p.id, city: p.city, adventure: adventure.publicState(p, this.now)}; // core.mjs:50
  }
  command(b, key, id) {
    return this.tx(async snap => {
      const p = await this.readyPlayer62(snap, id);
      const adv = await adventure.command({p, b, key, now: this.now, selectReceipt: k => snap.commands[id + '|' + k] ?? null});
      if (adv) {
        if (!adv.ok) return {abort: true, status: adv.status, body: adv.body};
        if (adv.receipt) snap.commands[id + '|' + key] = {signature: adv.receipt.signature}; // INSERT INTO commands
        return {status: 200, body: {...this.publicState(p), events: [...this.settleEvents, ...adv.events]}};
      }
      const old = snap.commands[id + '|' + key]; // legacy receipt SELECT (unchanged)
      if (old) return old.signature === JSON.stringify(b) ? {status: 200, body: this.publicState(p)} : {abort: true, status: 409, body: {error: 'legacy-conflict'}};
      if (b.kind === 'legacy_noop') p.city.progress.rev++;
      snap.commands[id + '|' + key] = {signature: JSON.stringify(b)};
      return {status: 200, body: this.publicState(p)};
    });
  }
}

const adv = (action, extra = {}) => ({kind: 'adventure', campaignId: 'forest_rescue_v1', action, ...extra});

test('v92 wiring: gate before receipt replay for adventure kinds only; receipts, replay, mismatch; publicState', async () => {
  const core = new StandInCore();
  const p = newPlayer({id: 'v92-player', login: 'l', now: core.now});
  p.city.military.owned = {'ENG-06': 100};
  core.db.players[p.id] = p;
  const locked = await core.command(adv('form_squad', {units: {'ENG-06': 10}}), 'key-locked-001', p.id);
  assert.deepEqual([locked.status, locked.body.error], [403, 'FOREST_LOCKED_HALL_LEVEL']);
  assert.equal((await core.command({kind: 'legacy_noop'}, 'legacy-key-0001', p.id)).status, 200, 'ordinary commands are not gated');
  core.db.players[p.id].city.buildings[0].level = 3;
  const formed = await core.command(adv('form_squad', {units: {'ENG-06': 10}}), 'key-form-0001', p.id);
  assert.equal(formed.status, 200);
  checkAdventure(formed.body.adventure);
  assert.ok(core.db.commands[p.id + '|key-form-0001']);
  const replay = await core.command(adv('form_squad', {units: {'ENG-06': 10}}), 'key-form-0001', p.id);
  assert.equal(replay.status, 200);
  assert.deepEqual(replay.body.events, []);
  const mismatch = await core.command(adv('claim_rewards'), 'key-form-0001', p.id);
  assert.deepEqual([mismatch.status, mismatch.body.error], [409, 'IDEMPOTENCY_BODY_MISMATCH']);
  const moved = await core.command(adv('move', {targetId: 'lf_horse_origin'}), 'key-move-0001', p.id);
  core.now = moved.body.adventure.squad.move.arriveAt + 1;
  const horse = await core.command(adv('discover_horse'), 'key-horse-001', p.id);
  assert.ok(horse.body.events.some(e => e.type === 'squad_arrived'), 'settle inside readyPlayer committed the arrival');
  assert.ok(horse.body.events.some(e => e.type === 'horse_joined'));
  // the gate runs before the receipt SELECT: a stored receipt is not replayed below hall III
  core.db.players[p.id].city.buildings[0].level = 2;
  const gated = await core.command(adv('discover_horse'), 'key-horse-001', p.id);
  assert.deepEqual([gated.status, gated.body.error], [403, 'FOREST_LOCKED_HALL_LEVEL']);
  assert.equal(core.db.players[p.id].adventures.forest_rescue_v1.phase, 'rescue');
});

test('v92 wiring: legacy import never carries adventure namespaces; auto-refill hook for paid branches', async () => {
  const imported = {city: {progress: {wood: 1}, adventures: {x: 1}}, adventures: {forest_rescue_v1: {phase: 'completed'}}, adventureFog: {}, adventureField: {}, rewardReservePrefs: {}, adventureAccess: {}, adventureMechanisms: {}};
  const clean = sanitizeLegacyImport(imported);
  for (const k of ['adventures', 'adventureFog', 'adventureField', 'rewardReservePrefs', 'adventureAccess', 'adventureMechanisms']) assert.equal(clean[k], undefined);
  assert.equal(clean.city.adventures, undefined);
  assert.equal(imported.adventures.forest_rescue_v1.phase, 'completed', 'input untouched');
  const p = newPlayer({id: 'spender', login: 'l', now: 0});
  p.city.buildings[0].level = 3;
  p.rewardReservePrefs = {forest_rescue_v1: {autoRefill: true}};
  const out = await adventure.afterVerifiedSpend(p, {food: 400, wood: 500, stone: 0, iron: 0, coins: 400}, 0);
  assert.equal(out.changed, false, 'nothing pending yet: no transfer, no write');
  assert.throws(() => createV92Adventure({}), /v92 dependency missing/);
});
