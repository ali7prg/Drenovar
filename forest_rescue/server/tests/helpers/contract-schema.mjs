// Executable form of CONTRACT.md §3 (state.adventure). Throws with a JSON path on mismatch.
// Additive fields (CONTRACT changelog v1.1) are allowed; required fields, enums and types
// are checked strictly, and internal server data must never appear.
const RES = ['food', 'wood', 'stone', 'iron', 'coins'];
export const FORBIDDEN_KEYS = ['exploredBase64', 'cursors', 'seed', 'usedBattleProofs', 'knocks', 'signature', 'serverVerified',
  'battleProof', 'escortProof', 'mechanismProof', 'ownerId', 'graphId', 'serials', 'victory', 'announcedPhase', 'expectedEncounterId'];

function fail(path, msg) {
  throw new Error('CONTRACT §3 violation at ' + path + ': ' + msg);
}
const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const int = (v, path) => { if (!Number.isSafeInteger(v)) fail(path, 'expected integer, got ' + JSON.stringify(v)); };
const num = (v, path) => { if (typeof v !== 'number' || !Number.isFinite(v)) fail(path, 'expected number'); };
const bool = (v, path) => { if (typeof v !== 'boolean') fail(path, 'expected boolean'); };
const str = (v, path) => { if (typeof v !== 'string' || !v) fail(path, 'expected string'); };
const oneOf = (v, list, path) => { if (!list.includes(v)) fail(path, JSON.stringify(v) + ' not in ' + list.join('|')); };
const obj = (v, path, keys = []) => {
  if (!isObj(v)) fail(path, 'expected object');
  for (const k of keys) if (!Object.hasOwn(v, k)) fail(path, 'missing key ' + k);
};
const nullable = (v, path, fn) => { if (v !== null) fn(v, path); };

function bag(v, path) {
  obj(v, path, RES);
  for (const r of RES) { int(v[r], path + '.' + r); if (v[r] < 0) fail(path, 'negative'); }
}
function point(v, path) {
  obj(v, path, ['x', 'y', 'z']);
  num(v.x, path + '.x'); num(v.y, path + '.y'); num(v.z, path + '.z');
}
function units(v, path) {
  obj(v, path);
  for (const [k, n] of Object.entries(v)) { int(n, path + '.' + k); if (n <= 0) fail(path, 'non-positive unit count'); }
}
export function checkMove(v, path) {
  obj(v, path, ['path', 'departAt', 'arriveAt', 'targetId', 'speed']);
  if (!Array.isArray(v.path) || !v.path.length) fail(path + '.path', 'expected non-empty array');
  v.path.forEach((p, i) => point(p, path + '.path[' + i + ']'));
  int(v.departAt, path + '.departAt'); int(v.arriveAt, path + '.arriveAt');
  if (v.arriveAt < v.departAt) fail(path, 'arriveAt < departAt');
  str(v.targetId, path + '.targetId'); num(v.speed, path + '.speed');
  if (v.speed <= 0) fail(path, 'speed must be positive');
}
function site(v, path) {
  obj(v, path, ['variation', 'cage', 'cagePose', 'captives', 'guardian', 'artifact', 'mechanism']);
  oneOf(v.variation, ['trail_cache', 'rune_lock', 'winch_sequence', 'paired_latch'], path + '.variation');
  oneOf(v.cage, ['oak', 'iron', 'root'], path + '.cage');
  oneOf(v.cagePose, ['closed', 'open'], path + '.cagePose');
  if (!Array.isArray(v.captives) || ![0, 3].includes(v.captives.length)) fail(path + '.captives', 'expected 0 (undiscovered) or 3');
  v.captives.forEach((c, i) => {
    const p = path + '.captives[' + i + ']';
    obj(c, p, ['id', 'name', 'role', 'visual', 'state']);
    str(c.id, p + '.id'); str(c.name, p + '.name'); str(c.role, p + '.role'); str(c.visual, p + '.visual');
    oneOf(c.state, ['caged', 'freed', 'escorted', 'home'], p + '.state');
  });
  const g = v.guardian;
  obj(g, path + '.guardian', ['species', 'level', 'modifier', 'state', 'hp', 'hpMax']);
  oneOf(g.species, ['tenerys', 'velkor', 'kamneklyk', 'dragor'], path + '.guardian.species');
  oneOf(g.level, [1, 2, 3], path + '.guardian.level');
  if (g.modifier !== null) str(g.modifier, path + '.guardian.modifier');
  oneOf(g.state, ['alive', 'engaged', 'defeated'], path + '.guardian.state');
  int(g.hp, path + '.guardian.hp'); int(g.hpMax, path + '.guardian.hpMax');
  const a = v.artifact;
  obj(a, path + '.artifact', ['id', 'family', 'state']);
  str(a.id, path + '.artifact.id');
  oneOf(a.family, ['stone_rune', 'bronze_seal', 'amber_crystal', 'bone_key'], path + '.artifact.family');
  oneOf(a.state, ['hidden', 'found', 'in_socket'], path + '.artifact.state');
  const m = v.mechanism;
  obj(m, path + '.mechanism', ['kind', 'progress', 'length', 'solved', 'symbols', 'lastResult']);
  oneOf(m.kind, ['trail_cache', 'rune_lock', 'winch_sequence', 'paired_latch'], path + '.mechanism.kind');
  int(m.progress, path + '.mechanism.progress'); int(m.length, path + '.mechanism.length'); bool(m.solved, path + '.mechanism.solved');
  if (!Array.isArray(m.symbols) || m.symbols.some(s => typeof s !== 'string')) fail(path + '.mechanism.symbols', 'expected string[]');
  oneOf(m.lastResult, ['ok', 'wrong', null], path + '.mechanism.lastResult');
}
const TIMELINE_TYPES = ['attack', 'hit', 'ability', 'death', 'telegraph', 'phase', 'recovery', 'retreat'];
function battle(v, path) {
  obj(v, path, ['reportId', 'siteId', 'encounterId', 'species', 'level', 'startedAt', 'endsAt', 'outcome', 'timeline', 'losses', 'loot']);
  str(v.reportId, path + '.reportId'); str(v.siteId, path + '.siteId'); str(v.encounterId, path + '.encounterId'); str(v.species, path + '.species');
  if (v.level !== null) int(v.level, path + '.level');
  int(v.startedAt, path + '.startedAt'); int(v.endsAt, path + '.endsAt');
  oneOf(v.outcome, ['victory', 'defeat', 'retreat', 'pending'], path + '.outcome');
  if (!Array.isArray(v.timeline)) fail(path + '.timeline', 'expected array');
  v.timeline.forEach((e, i) => {
    const p = path + '.timeline[' + i + ']';
    obj(e, p, ['t', 'type', 'actor']);
    num(e.t, p + '.t'); oneOf(e.type, TIMELINE_TYPES, p + '.type'); oneOf(e.actor, ['guardian', 'squad', 'boss'], p + '.actor');
  });
  obj(v.losses, path + '.losses', ['wounded', 'dead']);
  units(v.losses.wounded, path + '.losses.wounded'); units(v.losses.dead, path + '.losses.dead');
  if (v.loot !== null) obj(v.loot, path + '.loot');
}

export function scanForbidden(value, path = 'adventure') {
  if (Array.isArray(value)) value.forEach((v, i) => scanForbidden(v, path + '[' + i + ']'));
  else if (isObj(value)) for (const [k, v] of Object.entries(value)) {
    if (FORBIDDEN_KEYS.includes(k)) fail(path + '.' + k, 'internal server field leaked');
    scanForbidden(v, path + '.' + k);
  }
}

/** Validate state.adventure against CONTRACT §3; returns the object for chaining. */
export function checkAdventure(a) {
  const P = 'adventure';
  obj(a, P, ['campaignId', 'schemaVersion', 'serverTime', 'access', 'intro', 'fog', 'campaign', 'escrow', 'autoRefill', 'squad', 'horse', 'pois', 'battle', 'escort', 'boss', 'nextTask']);
  if (a.campaignId !== 'forest_rescue_v1') fail(P + '.campaignId', 'wrong id');
  if (a.schemaVersion !== 1) fail(P + '.schemaVersion', 'expected 1');
  int(a.serverTime, P + '.serverTime');
  obj(a.access, P + '.access', ['unlocked', 'hallLevel', 'requiredHall', 'reason']);
  bool(a.access.unlocked, P + '.access.unlocked'); int(a.access.hallLevel, P + '.access.hallLevel');
  if (a.access.requiredHall !== 3) fail(P + '.access.requiredHall', 'expected 3');
  if (a.access.unlocked ? a.access.reason !== null : a.access.reason !== 'FOREST_LOCKED_HALL_LEVEL') fail(P + '.access.reason', 'wrong reason');
  obj(a.intro, P + '.intro', ['status', 'deferred', 'offer']);
  oneOf(a.intro.status, ['pending', 'playing', 'acknowledged'], P + '.intro.status');
  bool(a.intro.deferred, P + '.intro.deferred'); bool(a.intro.offer, P + '.intro.offer');
  const f = a.fog;
  obj(f, P + '.fog', ['explorationLocked', 'columns', 'rows', 'cellSize', 'origin', 'visibleBase64', 'revision', 'entranceCorridor']);
  bool(f.explorationLocked, P + '.fog.explorationLocked');
  if (f.columns !== 56 || f.rows !== 56 || f.cellSize !== 4 || f.origin?.x !== -112 || f.origin?.z !== -112) fail(P + '.fog', 'grid');
  if (typeof f.visibleBase64 !== 'string' || Buffer.from(f.visibleBase64, 'base64').length !== 392) fail(P + '.fog.visibleBase64', 'expected 392-byte base64');
  int(f.revision, P + '.fog.revision');
  obj(f.entranceCorridor, P + '.fog.entranceCorridor', ['from', 'to', 'radius', 'transitionMs']);
  const c = a.campaign;
  obj(c, P + '.campaign', ['phase', 'paused', 'revision', 'horseJoined', 'sites', 'rescuedIds', 'rescuedCount', 'actUnlocked']);
  oneOf(c.phase, ['prologue', 'rescue', 'boss_unlocked', 'boss_active', 'completed'], P + '.campaign.phase');
  bool(c.paused, P + '.campaign.paused'); int(c.revision, P + '.campaign.revision'); bool(c.horseJoined, P + '.campaign.horseJoined');
  if (!Array.isArray(c.sites) || c.sites.length !== 12) fail(P + '.campaign.sites', 'expected 12 sites');
  c.sites.forEach((s, i) => {
    const p = P + '.campaign.sites[' + i + ']';
    obj(s, p, ['id', 'step', 'artifact', 'act', 'available', 'visible']);
    oneOf(s.step, [0, 1, 2, 3, 4, 5], p + '.step'); oneOf(s.artifact, [0, 1], p + '.artifact'); oneOf(s.act, [1, 2, 3, 4], p + '.act');
    bool(s.available, p + '.available'); bool(s.visible, p + '.visible');
  });
  if (!Array.isArray(c.rescuedIds) || c.rescuedIds.length !== c.rescuedCount) fail(P + '.campaign.rescuedIds', 'count mismatch');
  if (!Array.isArray(c.actUnlocked) || c.actUnlocked.length !== 4) fail(P + '.campaign.actUnlocked', 'expected 4 booleans');
  obj(a.escrow, P + '.escrow', ['earned', 'claimed', 'pending']);
  for (const k of ['earned', 'claimed', 'pending']) bag(a.escrow[k], P + '.escrow.' + k);
  for (const r of RES) if (a.escrow.earned[r] !== a.escrow.claimed[r] + a.escrow.pending[r]) fail(P + '.escrow', 'earned != claimed + pending');
  bool(a.autoRefill, P + '.autoRefill');
  const sq = a.squad;
  obj(sq, P + '.squad', ['units', 'members', 'node', 'move', 'busy']);
  units(sq.units, P + '.squad.units'); oneOf(sq.members, [0, 1, 2, 3], P + '.squad.members');
  if (sq.node !== null) str(sq.node, P + '.squad.node');
  nullable(sq.move, P + '.squad.move', checkMove);
  oneOf(sq.busy, [null, 'battle', 'escort', 'mechanism'], P + '.squad.busy');
  const h = a.horse;
  obj(h, P + '.horse', ['visible', 'node', 'mood', 'move']);
  bool(h.visible, P + '.horse.visible'); oneOf(h.mood, ['calm', 'alert', 'waiting'], P + '.horse.mood');
  nullable(h.move, P + '.horse.move', checkMove);
  if (!Array.isArray(a.pois)) fail(P + '.pois', 'expected array');
  a.pois.forEach((poi, i) => {
    const p = P + '.pois[' + i + ']';
    obj(poi, p, ['id', 'kind', 'x', 'y', 'z']);
    str(poi.id, p + '.id'); str(poi.kind, p + '.kind'); num(poi.x, p + '.x'); num(poi.y, p + '.y'); num(poi.z, p + '.z');
    if (poi.kind === 'site') site(poi, p);
  });
  nullable(a.battle, P + '.battle', battle);
  nullable(a.escort, P + '.escort', (e, p) => {
    obj(e, p, ['siteId', 'captiveIds', 'move', 'state']);
    if (!Array.isArray(e.captiveIds) || e.captiveIds.length !== 3) fail(p + '.captiveIds', 'expected exactly 3');
    nullable(e.move, p + '.move', checkMove);
    oneOf(e.state, ['walking', 'home'], p + '.state');
  });
  obj(a.boss, P + '.boss', ['state', 'hp', 'hpMax', 'phase', 'requiredHall']);
  oneOf(a.boss.state, ['locked', 'available', 'active', 'defeated'], P + '.boss.state');
  int(a.boss.hp, P + '.boss.hp'); int(a.boss.hpMax, P + '.boss.hpMax');
  oneOf(a.boss.phase, ['hunt', 'fury', 'last_stand'], P + '.boss.phase');
  if (a.boss.requiredHall !== 5) fail(P + '.boss.requiredHall', 'expected 5');
  nullable(a.nextTask, P + '.nextTask', (t, p) => {
    obj(t, p, ['siteId', 'taskId']);
    oneOf(t.taskId, ['discover', 'recover_artifact', 'defeat_guardian', 'unlock_cage', 'escort_home', 'discover_horse', 'begin_boss', 'engage_boss', 'finish_boss'], p + '.taskId');
  });
  if (!a.access.unlocked) {
    if (a.pois.length || a.horse.visible || !a.fog.explorationLocked) fail(P, 'locked projection must hide POIs/horse and lock exploration');
  }
  scanForbidden(a);
  return a;
}
