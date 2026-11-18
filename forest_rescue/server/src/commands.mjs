// Strict allowlist parsing (CONTRACT §2) and execution of adventure / adventure_intro
// actions on the loaded bundle of the selected player. The client never supplies
// success, rewards, wallet, capacity, owner, time, positions, revision or proofs.
import {campaignFsm, access, mechanisms as mech, fog as fogModule} from './vendor.mjs';
import {CAMPAIGN_ID, SITE_IDS, TASKS, HOME_ID, HORSE_ID, BOSS_TARGET_ID, BOSS_ENCOUNTER_ID, BOSS_SPECIES, BOSS, siteDef, guardianEncounterId, actUnlocked} from './content.mjs';
import {TROOPS} from './catalog.mjs';
import {simulateGuardian, simulateBoss} from './battle.mjs';
import {buildMove, anchorAt, squadSpeed, ESCORT_SPEED} from './movement.mjs';
import {refPosition} from './navgraph.mjs';
import {commitTraversal, archiveMoveCursor, finalizeBattle} from './settle.mjs';
import * as T from './trusted.mjs';
import {AdventureError, fail, hallMessage, toAdventureError} from './errors.mjs';
import {isPlainObject, fnv1a, normalizeUnits, sumUnits, clone} from './util.mjs';

export const ADVENTURE_KINDS = Object.freeze(['adventure', 'adventure_intro']);
export const KEY_PATTERN = /^[-\w]{8,128}$/;

const BASE = ['kind', 'campaignId', 'action'];
const OPTIONAL_BASE = ['requestId'];
const SCHEMA = {
  adventure: {
    form_squad: {required: ['units']},
    move: {required: ['targetId']},
    stop: {}, discover_horse: {}, retreat: {}, begin_boss: {}, engage_boss: {}, finish_boss: {},
    claim_rewards: {}, pause: {}, resume: {},
    attempt_task: {required: ['siteId', 'taskId']},
    mechanism_input: {required: ['siteId', 'symbol']},
    occupy_plates: {required: ['siteId']},
    engage_guardian: {required: ['siteId']},
    escort_start: {required: ['siteId']},
    set_auto_refill: {required: ['enabled']},
  },
  adventure_intro: {
    start_intro: {optional: ['reducedMotion']},
    finish_intro: {optional: ['attempt']},
    skip_intro: {}, defer_intro: {},
  },
};

function bad(message, detail) {
  return new AdventureError('BAD_FIELDS', {message, detail});
}

/** Parse the HTTP body into a validated action; unknown/forbidden fields → BAD_FIELDS. */
export function parseCommand(body, key) {
  if (!isPlainObject(body) || !ADVENTURE_KINDS.includes(body.kind)) throw bad(undefined, {reason: 'kind'});
  if (body.campaignId !== CAMPAIGN_ID) throw bad(undefined, {reason: 'campaignId'});
  const spec = typeof body.action === 'string' && Object.hasOwn(SCHEMA[body.kind], body.action) ? SCHEMA[body.kind][body.action] : null;
  if (!spec) throw bad(undefined, {reason: 'action'});
  const allowed = new Set([...BASE, ...OPTIONAL_BASE, ...(spec.required ?? []), ...(spec.optional ?? [])]);
  const extra = Object.keys(body).filter(k => !allowed.has(k));
  if (extra.length) throw bad(undefined, {reason: 'unknown_fields', fields: extra});
  for (const k of spec.required ?? []) if (!Object.hasOwn(body, k)) throw bad(undefined, {reason: 'missing_field', field: k});
  if (Object.hasOwn(body, 'requestId') && (typeof body.requestId !== 'string' || body.requestId !== key)) throw bad(undefined, {reason: 'requestId_must_equal_idempotency_key'});
  const a = {kind: body.kind, action: body.action};
  if (Object.hasOwn(body, 'siteId')) {
    if (!SITE_IDS.includes(body.siteId)) throw bad(undefined, {reason: 'siteId'});
    a.siteId = body.siteId;
  }
  if (Object.hasOwn(body, 'taskId')) {
    if (!TASKS.includes(body.taskId)) throw bad(undefined, {reason: 'taskId'});
    a.taskId = body.taskId;
  }
  if (Object.hasOwn(body, 'symbol')) {
    if (typeof body.symbol !== 'string' || !body.symbol || body.symbol.length > 64) throw bad(undefined, {reason: 'symbol'});
    a.symbol = body.symbol;
  }
  if (Object.hasOwn(body, 'targetId')) {
    if (typeof body.targetId !== 'string' || !body.targetId || body.targetId.length > 128) throw bad(undefined, {reason: 'targetId'});
    a.targetId = body.targetId;
  }
  if (Object.hasOwn(body, 'units')) {
    const u = body.units;
    if (!isPlainObject(u) || !Object.keys(u).length || Object.keys(u).length > 20) throw bad(undefined, {reason: 'units'});
    for (const [id, n] of Object.entries(u)) if (!Object.hasOwn(TROOPS, id) || !Number.isSafeInteger(n) || n < 1 || n > 1e9) throw bad(undefined, {reason: 'units', unitId: id});
    a.units = normalizeUnits(u);
  }
  if (Object.hasOwn(body, 'enabled')) {
    if (typeof body.enabled !== 'boolean') throw bad(undefined, {reason: 'enabled'});
    a.enabled = body.enabled;
  }
  if (Object.hasOwn(body, 'attempt')) {
    if (!Number.isSafeInteger(body.attempt) || body.attempt < 1) throw bad(undefined, {reason: 'attempt'});
    a.attempt = body.attempt;
  }
  if (Object.hasOwn(body, 'reducedMotion')) {
    if (typeof body.reducedMotion !== 'boolean') throw bad(undefined, {reason: 'reducedMotion'});
    a.reducedMotion = body.reducedMotion;
  }
  return a;
}

// ---------------------------------------------------------------------------------------
function reduce(ctx, action, extra = {}, {requiredHall} = {}) {
  const trusted = {...extra, authenticatedPlayerId: ctx.p.id, hallLevel: ctx.hall};
  let out;
  try {
    out = campaignFsm.reduceCampaign(ctx.bundle.campaign, action, trusted);
  } catch (error) {
    throw toAdventureError(error, {requiredHall});
  }
  ctx.bundle.campaign = out.state;
  for (const effect of out.effects) {
    if (effect.type === 'reward_escrowed') ctx.emit('reward_escrowed', {awardId: effect.awardId, resources: effect.resources});
    else if (effect.type === 'task_completed') {
      ctx.emit('task_completed', {siteId: effect.siteId, taskId: effect.taskId, reward: campaignFsm.taskReward(effect.siteId, effect.taskId)});
      if (effect.taskId === 'unlock_cage') ctx.emit('cage_opened', {siteId: effect.siteId});
    } else if (effect.type === 'transfer_rewards') {
      // credited by the caller with the real wallet mapping
    } else ctx.emit(effect.type, {});
  }
  return out;
}

function requireUnpaused(ctx) {
  if (ctx.bundle.campaign.paused) fail('CAMPAIGN_PAUSED');
}

function requireSquad(ctx) {
  if (T.squadUnits(ctx) < 1) fail('SQUAD_EMPTY');
}

function requireNotBusy(ctx) {
  if (T.battleActive(ctx) || T.escortWalking(ctx)) fail('SQUAD_BUSY');
}

function requireStationary(ctx) {
  if (!T.stationary(ctx)) fail('NOT_ARRIVED', {message: 'Отряд ещё в пути. Дождитесь прибытия или остановите отряд.'});
}

function requireGlade(ctx, siteId) {
  requireStationary(ctx);
  if (!T.presentInGlade(ctx, siteId)) fail('NOT_ARRIVED', {message: 'Отряд должен находиться на этой поляне.', detail: {siteId}});
}

function requireHall(ctx, level) {
  if (!Number.isSafeInteger(ctx.hall) || ctx.hall < level) fail('HALL_LEVEL_TOO_LOW', {message: hallMessage(level), detail: {requiredHall: level, hallLevel: ctx.hall}});
}

function releasePlates(ctx) {
  if (ctx.bundle.field.plates) {
    ctx.bundle.field.plates = null;
    ctx.emit('plates_released', {});
  }
}

/** Is a named target known to this player (no leak of hidden POIs)? */
export function targetKnown(ctx, targetId) {
  const node = ctx.graph.nodes.get(targetId);
  if (!node) return false;
  const {campaign} = ctx.bundle;
  const revealed = fogModule.isExplored(ctx.bundle.fog, node.x, node.z);
  const acts = actUnlocked(campaign);
  switch (node.kind) {
    case 'home': case 'horse_origin': return true;
    case 'site': return campaign.sites[node.id].step >= 1 || revealed || acts[siteDef(node.id).act - 1];
    case 'cage': case 'guardian': case 'key': case 'plate': case 'landmark': return campaign.sites[node.siteId].step >= 1;
    case 'bridge': return revealed || acts[3];
    case 'boss_arena': return revealed || ['boss_unlocked', 'boss_active', 'completed'].includes(campaign.phase);
    default: return false;
  }
}

async function startSquadMove(ctx, targetId, {kind = 'walk', speed, escortSiteId = null} = {}) {
  const field = ctx.bundle.field;
  const current = field.squad.move;
  let move;
  if (current) {
    await commitTraversal(ctx, {force: true});
    const anchor = anchorAt(ctx.graph, current, ctx.now);
    move = buildMove(ctx.graph, {serial: field.serials.move + 1, kind, targetId, start: anchor.start, aheadLoc: anchor.aheadLoc, now: ctx.now, speed, escortSiteId});
    if (!move) fail('TARGET_UNKNOWN');
    archiveMoveCursor(ctx, current);
  } else {
    move = buildMove(ctx.graph, {serial: field.serials.move + 1, kind, fromRef: field.squad.node, targetId, now: ctx.now, speed, escortSiteId});
    if (!move) fail('TARGET_UNKNOWN');
  }
  field.serials.move = move.serial;
  field.squad.move = move;
  ctx.emit('move_started', {targetId: move.targetId, kind, departAt: move.departAt, arriveAt: move.arriveAt});
  return move;
}

// ---------------------------------------------------------------------------------------
const ACTIONS = {
  async form_squad(ctx, a) {
    const field = ctx.bundle.field;
    requireNotBusy(ctx);
    if (field.squad.move || (field.squad.node !== HOME_ID && T.squadUnits(ctx) > 0)) {
      fail('SQUAD_BUSY', {message: 'Состав отряда меняется только дома, у северного подхода поселения.'});
    }
    const healthy = ctx.ports.healthyUnits(ctx.p);
    for (const [id, n] of Object.entries(a.units)) {
      if (n > (healthy[id] ?? 0)) fail('UNITS_UNAVAILABLE', {detail: {unitId: id, requested: n, available: healthy[id] ?? 0}});
    }
    field.squad = {units: clone(a.units), node: HOME_ID, move: null, arrival: field.squad.node === HOME_ID ? field.squad.arrival : null};
    ctx.emit('squad_formed', {units: clone(a.units)});
  },

  async move(ctx, a) {
    requireSquad(ctx);
    requireNotBusy(ctx);
    if (ctx.bundle.campaign.paused && a.targetId !== HOME_ID) fail('CAMPAIGN_PAUSED');
    if (!targetKnown(ctx, a.targetId)) fail('TARGET_UNKNOWN');
    const field = ctx.bundle.field;
    if (!field.squad.move && field.squad.node === a.targetId) return; // already there
    releasePlates(ctx);
    await startSquadMove(ctx, a.targetId, {speed: squadSpeed(field.squad.units)});
  },

  async stop(ctx) {
    const field = ctx.bundle.field;
    if (!field.squad.move) return;
    if (field.squad.move.kind === 'escort') fail('SQUAD_BUSY', {message: 'Сопровождение нельзя прервать посреди леса: люди идут домой.'});
    await startSquadMove(ctx, null, {speed: field.squad.move.speed});
  },

  async discover_horse(ctx) {
    reduce(ctx, {type: 'discover_horse'}, {arrival: T.arrivalProof(ctx, HORSE_ID)});
  },

  async attempt_task(ctx, a) {
    const {siteId, taskId} = a;
    const site = siteDef(siteId);
    const extra = {};
    if (taskId === 'discover') extra.arrival = T.siteArrivalProof(ctx, siteId);
    if (taskId === 'recover_artifact') { extra.arrival = T.arrivalProof(ctx, site.artifact.id); extra.mechanismProof = T.mechanismProof(ctx, siteId); }
    if (taskId === 'defeat_guardian') Object.assign(extra, T.guardianBattleContext(ctx, siteId));
    if (taskId === 'unlock_cage') extra.arrival = T.arrivalProof(ctx, siteId + ':cage');
    if (taskId === 'escort_home') extra.escortProof = T.escortProof(ctx, siteId);
    const out = reduce(ctx, {type: 'attempt_task', siteId, taskId}, extra, {requiredHall: site.guardian.requiredHall});
    if (taskId === 'escort_home' && out.state.sites[siteId].step === 5 && ctx.bundle.field.escorts[siteId]?.state === 'home') {
      delete ctx.bundle.field.escorts[siteId];
    }
    if (taskId === 'recover_artifact' && out.changed) ctx.emit('artifact_found', {siteId, artifactId: site.artifact.id});
  },

  async mechanism_input(ctx, a) {
    const site = siteDef(a.siteId);
    requireUnpaused(ctx);
    const step = ctx.bundle.campaign.sites[a.siteId].step;
    let current = ctx.bundle.mechanisms[a.siteId];
    if (!current) {
      try { current = mech.initialMechanism(site.raw); } catch (e) { throw toAdventureError(e); }
    }
    if (current.solved || step >= 2) return; // solved earlier: inputs have no further effect
    const isPlate = site.variation === 'paired_latch' && a.symbol !== site.puzzle.solution[2] && site.puzzle.solution.includes(a.symbol);
    const plates = site.variation === 'paired_latch' ? T.platesStatus(ctx, a.siteId) : null;
    const trusted = {
      authenticatedPlayerId: ctx.p.id, hallLevel: ctx.hall,
      siteDiscovered: step >= 1, siteAccessVerified: T.presentInGlade(ctx, a.siteId) && !T.battleActive(ctx),
      campaignPaused: ctx.bundle.campaign.paused,
    };
    if (site.variation === 'trail_cache') {
      trusted.observedLandmark = ctx.bundle.field.trails[a.siteId]?.observed.includes(a.symbol) ? a.symbol : null;
    }
    if (site.variation === 'paired_latch') {
      trusted.occupancyServerVerified = plates.held;
      trusted.leftOccupied = plates.held;
      trusted.rightOccupied = plates.held;
    }
    if (step >= 1 && !current.solved && trusted.siteAccessVerified && isPlate && !plates.held) fail('PLATES_NOT_OCCUPIED');
    let out;
    try { out = mech.reduceMechanism(current, {symbol: a.symbol}, site.raw, trusted); } catch (e) { throw toAdventureError(e); }
    ctx.bundle.mechanisms[a.siteId] = out.state;
    for (const effect of out.effects) {
      const ok = effect.type !== 'mechanism_reset';
      ctx.bundle.field.mechanismResults[a.siteId] = ok ? 'ok' : 'wrong';
      ctx.emit('mechanism_progress', {siteId: a.siteId, ok, symbol: a.symbol, progress: out.state.progress.length, solved: out.state.solved});
    }
    if (out.state.solved && site.variation === 'paired_latch') releasePlates(ctx);
  },

  async occupy_plates(ctx, a) {
    const site = siteDef(a.siteId);
    if (site.variation !== 'paired_latch') fail('MECHANISM_NOT_READY', {message: 'На этой поляне нет парных площадок.'});
    requireUnpaused(ctx);
    requireNotBusy(ctx);
    const step = ctx.bundle.campaign.sites[a.siteId].step;
    if (step < 1) fail('TASK_OUT_OF_ORDER', {message: 'Сначала обнаружьте это место.'});
    if (ctx.bundle.mechanisms[a.siteId]?.solved || step >= 2) return;
    requireGlade(ctx, a.siteId);
    const field = ctx.bundle.field;
    if (T.squadUnits(ctx) < 2) fail('PLATES_NOT_OCCUPIED', {message: 'Нужно минимум два бойца отряда, чтобы одновременно удерживать обе площадки.'});
    if (field.plates?.siteId === a.siteId && field.plates.anchor === field.squad.node) return;
    const order = Object.keys(field.squad.units).sort();
    const left = order[0], right = field.squad.units[left] >= 2 ? left : order[1];
    const anchorPos = refPosition(ctx.graph, field.squad.node);
    const lp = ctx.graph.nodes.get(a.siteId + ':plate_left'), rp = ctx.graph.nodes.get(a.siteId + ':plate_right');
    const dist = Math.max(Math.hypot(lp.x - anchorPos.x, lp.z - anchorPos.z), Math.hypot(rp.x - anchorPos.x, rp.z - anchorPos.z));
    const speed = squadSpeed(field.squad.units) || 1;
    field.plates = {siteId: a.siteId, anchor: field.squad.node, startedAt: ctx.now, readyAt: ctx.now + Math.ceil(dist / speed * 1000), left, right};
    ctx.emit('plates_occupied', {siteId: a.siteId, readyAt: field.plates.readyAt});
  },

  async engage_guardian(ctx, a) {
    const site = siteDef(a.siteId);
    requireUnpaused(ctx);
    requireSquad(ctx);
    requireNotBusy(ctx);
    const field = ctx.bundle.field, step = ctx.bundle.campaign.sites[a.siteId].step;
    if (!actUnlocked(ctx.bundle.campaign)[site.act - 1]) fail('ACT_LOCKED');
    if (field.guardians[a.siteId]?.state === 'defeated' || step >= 3) fail('GUARDIAN_DEFEATED');
    if (step < 2) fail('TASK_OUT_OF_ORDER', {message: 'Сначала найдите печать этого места: её добывают до боя со стражем.'});
    requireHall(ctx, site.guardian.requiredHall);
    requireGlade(ctx, a.siteId);
    const spec = ctx.ports.creatureSpec(site.guardian.species, site.guardian.level);
    if (!spec) fail('STATE_CORRUPT', {detail: {reason: 'CREATURE_SPEC_MISSING'}});
    releasePlates(ctx);
    const g = field.guardians[a.siteId] ??= {state: 'alive', attempts: 0, victory: null};
    g.attempts++;
    field.serials.battle++;
    const encounterId = guardianEncounterId(a.siteId);
    const seed = fnv1a(ctx.p.id + '|' + encounterId + '|' + g.attempts);
    const sim = simulateGuardian({units: field.squad.units, spec, modifier: site.guardian.modifier, seed});
    field.battle = newBattle(ctx, {kind: 'guardian', siteId: a.siteId, encounterId, species: spec.id, level: spec.level, modifier: site.guardian.modifier, attempt: g.attempts, seed, sim, hpMax: spec.hp});
    ctx.emit('battle_report', {reportId: field.battle.reportId, siteId: a.siteId, outcome: 'pending', endsAt: field.battle.endsAt});
  },

  async retreat(ctx) {
    const b = ctx.bundle.field.battle;
    if (!b || b.state !== 'active') return;
    finalizeBattle(ctx, 'retreat', Math.min(ctx.now, b.endsAt));
  },

  async escort_start(ctx, a) {
    const site = siteDef(a.siteId);
    requireUnpaused(ctx);
    const field = ctx.bundle.field, step = ctx.bundle.campaign.sites[a.siteId].step;
    if (step >= 5 || field.escorts[a.siteId]) return; // already home / already walking
    if (step < 4) fail('TASK_OUT_OF_ORDER', {message: 'Сначала откройте клетку печатью этого места.'});
    requireSquad(ctx);
    requireNotBusy(ctx);
    requireGlade(ctx, a.siteId);
    releasePlates(ctx);
    const move = await startSquadMove(ctx, HOME_ID, {kind: 'escort', speed: Math.min(ESCORT_SPEED, squadSpeed(field.squad.units)), escortSiteId: a.siteId});
    field.escorts[a.siteId] = {captiveIds: site.captives.map(c => c.id), state: 'walking', moveSerial: move.serial, departAt: move.departAt, arriveAt: move.arriveAt, arrivedAt: null};
    ctx.emit('escort_started', {siteId: a.siteId, captiveIds: site.captives.map(c => c.id), arriveAt: move.arriveAt});
  },

  async begin_boss(ctx) {
    const phase = ctx.bundle.campaign.phase;
    if (phase === 'boss_unlocked') {
      requireUnpaused(ctx);
      requireHall(ctx, BOSS.requiredHall);
    }
    reduce(ctx, {type: 'begin_boss'}, {arrival: T.arrivalProof(ctx, BOSS_TARGET_ID)}, {requiredHall: BOSS.requiredHall});
  },

  async engage_boss(ctx) {
    const {campaign, field} = ctx.bundle;
    if (['prologue', 'rescue'].includes(campaign.phase)) fail('BOSS_LOCKED');
    if (campaign.phase === 'boss_unlocked') fail('TASK_OUT_OF_ORDER', {message: 'Сначала войдите в Костяную чашу (begin_boss).'});
    if (campaign.phase === 'completed' || field.boss.state === 'defeated') fail('GUARDIAN_DEFEATED', {message: 'Пращур уже побеждён. Завершите финал, чтобы получить награду.'});
    requireUnpaused(ctx);
    requireHall(ctx, BOSS.requiredHall);
    requireSquad(ctx);
    requireNotBusy(ctx);
    requireStationary(ctx);
    if (!T.arrivedAt(ctx, BOSS_TARGET_ID)) fail('NOT_ARRIVED', {message: 'Отряд должен стоять на арене Костяной чаши.'});
    field.boss.attempts++;
    field.serials.battle++;
    const seed = fnv1a(ctx.p.id + '|' + BOSS_ENCOUNTER_ID + '|' + field.boss.attempts);
    const sim = simulateBoss({units: field.squad.units, boss: BOSS, seed});
    field.battle = newBattle(ctx, {kind: 'boss', siteId: BOSS_TARGET_ID, encounterId: BOSS_ENCOUNTER_ID, species: BOSS_SPECIES, level: null, modifier: null, attempt: field.boss.attempts, seed, sim, hpMax: BOSS.stats.hp});
    field.battle.announcedPhase = BOSS.phases[0].id;
    ctx.emit('battle_report', {reportId: field.battle.reportId, siteId: BOSS_TARGET_ID, outcome: 'pending', endsAt: field.battle.endsAt});
    ctx.emit('boss_phase', {phase: BOSS.phases[0].id, reportId: field.battle.reportId});
  },

  async finish_boss(ctx) {
    if (ctx.bundle.campaign.phase === 'boss_active') requireHall(ctx, BOSS.requiredHall);
    reduce(ctx, {type: 'finish_boss'}, T.bossBattleContext(ctx), {requiredHall: BOSS.requiredHall});
  },

  async claim_rewards(ctx) {
    const capacity = ctx.ports.capacity(ctx.p);
    const wallet = ctx.ports.integerWallet(ctx.p);
    const capBag = Object.fromEntries(Object.keys(wallet).map(r => [r, Math.min(Number.MAX_SAFE_INTEGER, Math.floor(capacity))]));
    const out = reduce(ctx, {type: 'claim_rewards'}, {wallet, capacity: capBag});
    const transfer = out.effects.find(e => e.type === 'transfer_rewards').resources;
    for (const [r, n] of Object.entries(transfer)) ctx.ports.credit(ctx.p, r, n);
    const pending = ctx.bundle.campaign.escrow.pending;
    ctx.emit('transfer_rewards', {resources: transfer, capacity: capBag.food,
      storageFull: Object.values(transfer).every(n => n === 0) && Object.values(pending).some(n => n > 0)});
  },

  async set_auto_refill(ctx, a) {
    ctx.bundle.prefs = {autoRefill: a.enabled};
  },

  async pause(ctx) { reduce(ctx, {type: 'pause'}); },
  async resume(ctx) { reduce(ctx, {type: 'resume'}); },
};

function newBattle(ctx, {kind, siteId, encounterId, species, level, modifier, attempt, seed, sim, hpMax}) {
  const short = (fnv1a(ctx.p.id + '|' + encounterId).toString(36));
  const reportId = 'frb-' + (kind === 'boss' ? 'boss' : siteId.slice(-2)) + '-a' + attempt + '-' + short;
  return {
    reportId, kind, siteId, encounterId, species, level, modifier, attempt, seed,
    startedAt: ctx.now, endsAt: ctx.now + sim.durationMs, units: clone(ctx.bundle.field.squad.units), hpMax,
    outcome: sim.outcome, state: 'active', finalOutcome: null, finalizedAt: null,
    timeline: sim.timeline, knocks: sim.knocks, losses: null, loot: null, announcedPhase: 'engage',
  };
}

const INTRO_ACTIONS = {
  start_intro(ctx, a) {
    return {type: 'start_intro', trusted: {reducedMotion: a.reducedMotion === true}};
  },
  finish_intro(ctx, a) {
    const intro = ctx.bundle.intro;
    // `attempt` is optional on the wire (CONTRACT changelog v1.1); default = current attempt.
    const attempt = a.attempt ?? (intro.status === 'playing' ? intro.attempts : Math.max(1, intro.attempts));
    return {type: 'finish_intro', attempt};
  },
  skip_intro() { return {type: 'skip_intro'}; },
  defer_intro() { return {type: 'defer_intro'}; },
};

function executeIntro(ctx, a) {
  const spec = INTRO_ACTIONS[a.action](ctx, a);
  const {trusted: presentation = {}, ...action} = spec;
  // The server cannot see UI state: issuing start_intro is the client's statement that it
  // is in a safe city-foreground moment; the server adds what it does know (active battle).
  const trusted = {
    authenticatedPlayerId: ctx.p.id, hallLevel: ctx.hall,
    cityForeground: true, uiReady: true, modalOpen: false, loading: false,
    activeCombat: T.battleActive(ctx), reducedMotion: presentation.reducedMotion === true,
  };
  let out;
  try { out = access.reduceIntro(ctx.bundle.intro, action, trusted); } catch (e) { throw toAdventureError(e); }
  ctx.bundle.intro = out.state;
  for (const effect of out.effects) if (effect.type === 'present_intro') ctx.emit('intro_present', {attempt: effect.attempt, mode: effect.mode});
}

export async function executeCommand(ctx, a) {
  if (a.kind === 'adventure_intro') return executeIntro(ctx, a);
  const handler = ACTIONS[a.action];
  return handler(ctx, a);
}

