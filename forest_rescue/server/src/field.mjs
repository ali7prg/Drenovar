// New server-owned namespace p.adventureField.forest_rescue_v1: movement, plate occupancy,
// battle reports, escorts, trail observations, presentation event ring. It is kept apart
// from the strict delivered campaign schema (p.adventures.forest_rescue_v1).
// Absent → lazily initialised (derived from the validated campaign); present but corrupt
// or of another schemaVersion → explicit error, never a silent reset.
import {CAMPAIGN_ID, SITE_IDS, SITE_BY_ID, HOME_ID} from './content.mjs';
import {TROOPS} from './catalog.mjs';
import {hasExactKeys, isPlainObject, isCount, isTime} from './util.mjs';

export const FIELD_SCHEMA_VERSION = 1;
export const EVENT_RING = 32;
const FIELD_KEYS = ['schemaVersion', 'campaignId', 'graphId', 'revision', 'serials', 'squad', 'plates', 'guardians', 'boss', 'battle', 'escorts', 'trails', 'mechanismResults', 'events'];
const SQUAD_KEYS = ['units', 'node', 'move', 'arrival'];
const MOVE_KEYS = ['serial', 'kind', 'targetId', 'start', 'steps', 'departAt', 'arriveAt', 'speed', 'committed', 'escortSiteId'];
const BATTLE_KEYS = ['reportId', 'kind', 'siteId', 'encounterId', 'species', 'level', 'modifier', 'attempt', 'seed', 'startedAt', 'endsAt', 'units', 'hpMax', 'outcome', 'state', 'finalOutcome', 'finalizedAt', 'timeline', 'knocks', 'losses', 'loot', 'announcedPhase'];

const corrupt = reason => Object.assign(new Error('INVALID_FIELD_STATE'), {code: 'INVALID_FIELD_STATE', reason});
const check = (cond, reason) => { if (!cond) throw corrupt(reason); };

export function initialField(graphId) {
  return {
    schemaVersion: FIELD_SCHEMA_VERSION, campaignId: CAMPAIGN_ID, graphId, revision: 0,
    serials: {move: 0, battle: 0, event: 0},
    squad: {units: {}, node: HOME_ID, move: null, arrival: null},
    plates: null,
    guardians: {},
    boss: {state: 'alive', attempts: 0, victory: null},
    battle: null,
    escorts: {},
    trails: {},
    mechanismResults: {},
    events: [],
  };
}

/**
 * Lazy migration for an ABSENT field namespace of a player whose (validated) campaign
 * already progressed elsewhere: guardians/boss already proven stay defeated; nothing new
 * is granted; the squad starts at home without units.
 */
export function deriveFieldFromCampaign(campaign, graphId) {
  const field = initialField(graphId);
  for (const proof of campaign.usedBattleProofs) {
    // Provenance of these older proofs is the validated campaign ledger itself.
    const victory = {reportId: proof.reportId, encounterId: null, species: null, level: null, modifier: null, finalizedAt: 0};
    if (SITE_BY_ID.has(proof.siteId)) field.guardians[proof.siteId] = {state: 'defeated', attempts: 0, victory};
    else field.boss = {state: 'defeated', attempts: 0, victory};
  }
  return field;
}

function units(value, reason) {
  check(isPlainObject(value) && Object.keys(value).length <= 20, reason);
  for (const [k, n] of Object.entries(value)) check(Object.hasOwn(TROOPS, k) && Number.isSafeInteger(n) && n > 0, reason);
}

function ref(value) {
  return typeof value === 'string' && value.length > 0 && value.length <= 160;
}

function point(p) {
  return hasExactKeys(p, ['x', 'y', 'z']) && [p.x, p.y, p.z].every(Number.isFinite);
}

function move(m) {
  check(hasExactKeys(m, MOVE_KEYS), 'move.keys');
  check(isCount(m.serial) && m.serial > 0 && ['walk', 'escort'].includes(m.kind) && ref(m.targetId), 'move.ids');
  check(m.start === null || point(m.start), 'move.start');
  check(Array.isArray(m.steps) && m.steps.length <= 256 && m.steps.every(s => hasExactKeys(s, ['w', 'a', 'b']) && ref(s.w) && isCount(s.a) && isCount(s.b)), 'move.steps');
  check(isTime(m.departAt) && isTime(m.arriveAt) && m.arriveAt >= m.departAt, 'move.time');
  check(Number.isFinite(m.speed) && m.speed > 0 && m.speed < 100 && Number.isSafeInteger(m.committed) && m.committed >= 0, 'move.progress');
  check(m.escortSiteId === null || SITE_BY_ID.has(m.escortSiteId), 'move.escort');
  check((m.kind === 'escort') === (m.escortSiteId !== null), 'move.kind');
}

export const VICTORY_KEYS = ['reportId', 'encounterId', 'species', 'level', 'modifier', 'finalizedAt'];
function victory(v) {
  return v === null || (hasExactKeys(v, VICTORY_KEYS) && typeof v.reportId === 'string' && v.reportId.length > 0 && v.reportId.length <= 200 &&
    (v.encounterId === null || typeof v.encounterId === 'string') && (v.species === null || typeof v.species === 'string') &&
    (v.level === null || Number.isSafeInteger(v.level)) && (v.modifier === null || typeof v.modifier === 'string') && isTime(v.finalizedAt));
}

function lossBag(b) {
  return hasExactKeys(b, ['wounded', 'dead']) && [b.wounded, b.dead].every(x => isPlainObject(x) && Object.values(x).every(n => Number.isSafeInteger(n) && n >= 0));
}

function battle(b) {
  check(hasExactKeys(b, BATTLE_KEYS), 'battle.keys');
  check(typeof b.reportId === 'string' && b.reportId.length > 0 && b.reportId.length <= 200, 'battle.reportId');
  check(['guardian', 'boss'].includes(b.kind) && typeof b.siteId === 'string' && typeof b.encounterId === 'string' && typeof b.species === 'string', 'battle.ids');
  check(b.kind === 'boss' ? b.level === null : Number.isSafeInteger(b.level), 'battle.level');
  check(b.modifier === null || typeof b.modifier === 'string', 'battle.modifier');
  check(isCount(b.attempt) && isCount(b.seed) && isTime(b.startedAt) && isTime(b.endsAt) && b.endsAt >= b.startedAt, 'battle.time');
  units(b.units, 'battle.units');
  check(isCount(b.hpMax) && ['victory', 'defeat'].includes(b.outcome) && ['active', 'finalized'].includes(b.state), 'battle.state');
  check(b.state === 'active' ? b.finalOutcome === null && b.finalizedAt === null && b.losses === null && b.loot === null
    : ['victory', 'defeat', 'retreat'].includes(b.finalOutcome) && isTime(b.finalizedAt) && lossBag(b.losses), 'battle.final');
  check(Array.isArray(b.timeline) && b.timeline.length <= 4000 && b.timeline.every(e => isPlainObject(e) && Number.isFinite(e.t) && e.t >= 0 && typeof e.type === 'string'), 'battle.timeline');
  check(Array.isArray(b.knocks) && b.knocks.length <= 4000 && b.knocks.every(k => hasExactKeys(k, ['t', 'units']) && Number.isFinite(k.t) && isPlainObject(k.units)), 'battle.knocks');
  check(b.loot === null || isPlainObject(b.loot), 'battle.loot');
  check(typeof b.announcedPhase === 'string', 'battle.phase');
}

export function validateField(saved) {
  check(isPlainObject(saved), 'root');
  if (saved.schemaVersion !== FIELD_SCHEMA_VERSION) {
    throw Object.assign(new Error('UNSUPPORTED_FIELD_SCHEMA'), {code: 'UNSUPPORTED_FIELD_SCHEMA'});
  }
  check(hasExactKeys(saved, FIELD_KEYS), 'keys');
  check(saved.campaignId === CAMPAIGN_ID && typeof saved.graphId === 'string' && isCount(saved.revision), 'header');
  check(hasExactKeys(saved.serials, ['move', 'battle', 'event']) && Object.values(saved.serials).every(isCount), 'serials');
  check(hasExactKeys(saved.squad, SQUAD_KEYS), 'squad');
  units(saved.squad.units, 'squad.units');
  check(ref(saved.squad.node), 'squad.node');
  if (saved.squad.move !== null) move(saved.squad.move);
  check(saved.squad.arrival === null || (hasExactKeys(saved.squad.arrival, ['targetId', 'serial', 'at']) && ref(saved.squad.arrival.targetId) && isCount(saved.squad.arrival.serial) && isTime(saved.squad.arrival.at)), 'squad.arrival');
  check(saved.plates === null || (hasExactKeys(saved.plates, ['siteId', 'anchor', 'startedAt', 'readyAt', 'left', 'right']) && SITE_BY_ID.get(saved.plates.siteId)?.variation === 'paired_latch' &&
    ref(saved.plates.anchor) && isTime(saved.plates.startedAt) && isTime(saved.plates.readyAt) && Object.hasOwn(TROOPS, saved.plates.left) && Object.hasOwn(TROOPS, saved.plates.right)), 'plates');
  check(isPlainObject(saved.guardians) && Object.keys(saved.guardians).every(id => SITE_IDS.includes(id)), 'guardians');
  for (const g of Object.values(saved.guardians)) {
    check(hasExactKeys(g, ['state', 'attempts', 'victory']) && ['alive', 'defeated'].includes(g.state) && isCount(g.attempts) && victory(g.victory) && (g.state === 'defeated') === (g.victory !== null), 'guardian');
  }
  const boss = saved.boss;
  check(hasExactKeys(boss, ['state', 'attempts', 'victory']) && ['alive', 'defeated'].includes(boss.state) && isCount(boss.attempts) && victory(boss.victory) && (boss.state === 'defeated') === (boss.victory !== null), 'boss');
  if (saved.battle !== null) battle(saved.battle);
  check(isPlainObject(saved.escorts) && Object.keys(saved.escorts).length <= 12, 'escorts');
  for (const [siteId, e] of Object.entries(saved.escorts)) {
    check(SITE_BY_ID.has(siteId) && hasExactKeys(e, ['captiveIds', 'state', 'moveSerial', 'departAt', 'arriveAt', 'arrivedAt']), 'escort.keys');
    const expected = SITE_BY_ID.get(siteId).captives.map(c => c.id);
    check(Array.isArray(e.captiveIds) && e.captiveIds.length === 3 && expected.every((id, i) => e.captiveIds[i] === id), 'escort.captives');
    check(['walking', 'home'].includes(e.state) && isCount(e.moveSerial) && isTime(e.departAt) && isTime(e.arriveAt) && (e.state === 'home' ? isTime(e.arrivedAt) : e.arrivedAt === null), 'escort.state');
  }
  check(isPlainObject(saved.trails), 'trails');
  for (const [siteId, t] of Object.entries(saved.trails)) {
    const site = SITE_BY_ID.get(siteId);
    check(site?.variation === 'trail_cache' && hasExactKeys(t, ['observed']) && Array.isArray(t.observed) && t.observed.length <= 3 &&
      new Set(t.observed).size === t.observed.length && t.observed.every(s => site.puzzle.solution.includes(s)), 'trails.entry');
  }
  check(isPlainObject(saved.mechanismResults) && Object.entries(saved.mechanismResults).every(([id, r]) => SITE_BY_ID.has(id) && ['ok', 'wrong'].includes(r)), 'mechanismResults');
  check(Array.isArray(saved.events) && saved.events.length <= EVENT_RING && saved.events.every(e => isPlainObject(e) && isCount(e.seq) && isCount(e.revision) && typeof e.type === 'string'), 'events');
  return saved;
}
