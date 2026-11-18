// projectAdventure: the ONLY adventure data sent to clients (CONTRACT §3). No stored fog
// bitset or cursors, no battle seeds, no proof ledgers, no hidden POIs. Below hall III
// the projection is locked: no POIs, no horse, boundary fog only.
import {access, fog as fogModule} from './vendor.mjs';
import {CAMPAIGN_ID, SITES, HOME_ID, HORSE_ID, BRIDGE_ID, BOSS_TARGET_ID, BOSS, TASKS, actUnlocked} from './content.mjs';
import {creatureSpec as localCreatureSpec} from './catalog.mjs';
import {stateAt} from './battle.mjs';
import {projectMove, projectHorseMove, positionNow, movePath} from './movement.mjs';
import {roundPoint} from './navgraph.mjs';
import {MIN_HALL_LEVEL_EXPORT, FOG_GRID} from './constants.mjs';
import * as T from './trusted.mjs';
import {clone, sumUnits} from './util.mjs';

function poiMeta(graph) {
  const ids = [HOME_ID, HORSE_ID, BRIDGE_ID, BOSS_TARGET_ID, ...SITES.map(s => s.id)];
  return ids.map(id => { const n = graph.nodes.get(id); return {id, x: n.x, z: n.z}; });
}

function nextTask(campaign, field) {
  switch (campaign.phase) {
    case 'prologue': return {siteId: null, taskId: 'discover_horse'};
    case 'boss_unlocked': return {siteId: BOSS_TARGET_ID, taskId: 'begin_boss'};
    case 'boss_active': return {siteId: BOSS_TARGET_ID, taskId: field.boss.victory ? 'finish_boss' : 'engage_boss'};
    case 'completed': return null;
    default: {
      const acts = actUnlocked(campaign);
      const site = SITES.find(s => acts[s.act - 1] && campaign.sites[s.id].step < 5);
      return site ? {siteId: site.id, taskId: TASKS[campaign.sites[site.id].step]} : null;
    }
  }
}

function busy(ctx) {
  if (T.battleActive(ctx)) return 'battle';
  if (T.escortWalking(ctx)) return 'escort';
  if (ctx.bundle.field.plates) return 'mechanism';
  return null;
}

function guardianView(ctx, site, step) {
  const spec = ctx.ports.creatureSpec(site.guardian.species, site.guardian.level) ?? localCreatureSpec(site.guardian.species, site.guardian.level);
  const record = ctx.bundle.field.guardians[site.id];
  const b = ctx.bundle.field.battle;
  let state = 'alive', hp = spec.hp;
  if (record?.state === 'defeated' || step >= 3) { state = 'defeated'; hp = 0; }
  else if (b?.state === 'active' && b.siteId === site.id) { state = 'engaged'; hp = stateAt(b.timeline, b.hpMax, (ctx.now - b.startedAt) / 1000).hp; }
  return {species: site.guardian.species, level: site.guardian.level, modifier: site.guardian.modifier, name: spec.name,
    state, hp, hpMax: spec.hp, requiredHall: site.guardian.requiredHall, attempts: record?.attempts ?? 0};
}

function captiveState(ctx, siteId, step) {
  if (step >= 5) return 'home';
  if (step < 4) return 'caged';
  const e = ctx.bundle.field.escorts[siteId];
  if (!e) return 'freed';
  return e.state === 'walking' ? 'escorted' : 'home';
}

function nodePoint(ctx, id) {
  const n = ctx.graph.nodes.get(id);
  return {id, ...roundPoint(n)};
}

function siteView(ctx, site, available) {
  const {campaign, mechanisms, field} = ctx.bundle;
  const {step, artifact} = campaign.sites[site.id];
  const discovered = step >= 1;
  const mech = mechanisms[site.id];
  const solved = mech?.solved === true || step >= 2;
  const center = ctx.graph.nodes.get(site.id);
  const targets = {center: nodePoint(ctx, site.id)};
  const mechanism = {kind: site.variation, progress: solved ? 3 : (mech?.progress.length ?? 0), length: 3, solved,
    symbols: discovered ? [...site.puzzle.symbols] : [], lastResult: field.mechanismResults[site.id] ?? null,
    clue: discovered ? site.puzzle.clue : null};
  if (discovered) {
    targets.cage = nodePoint(ctx, site.id + ':cage');
    targets.guardian = nodePoint(ctx, site.id + ':guardian');
    targets.key = nodePoint(ctx, site.artifact.id);
    if (site.variation === 'paired_latch') {
      targets.plate_left = nodePoint(ctx, site.id + ':plate_left');
      targets.plate_right = nodePoint(ctx, site.id + ':plate_right');
      const plates = T.platesStatus(ctx, site.id);
      mechanism.plates = {state: plates.state, readyAt: plates.readyAt ?? null};
    }
    if (site.variation === 'trail_cache') {
      const observed = field.trails[site.id]?.observed ?? [];
      targets.landmarks = site.puzzle.solution.map(symbol => ({...nodePoint(ctx, site.id + ':landmark:' + symbol), symbol, observed: observed.includes(symbol)}));
      mechanism.observed = [...observed];
    }
  }
  return {
    id: site.id, kind: 'site', name: site.name, number: site.number, act: site.act,
    ...roundPoint(center), variation: site.variation, cage: site.cage, cagePose: step >= 4 ? 'open' : 'closed',
    step, available, discovered,
    captives: discovered ? site.captives.map(c => ({id: c.id, name: c.name, role: c.role, visual: c.visual, state: captiveState(ctx, site.id, step)})) : [],
    guardian: guardianView(ctx, site, step),
    artifact: {id: site.artifact.id, name: site.artifact.name, family: site.artifact.family, held: artifact === 1,
      state: step < 2 ? 'hidden' : step < 4 ? 'found' : 'in_socket'},
    mechanism,
    targets,
  };
}

function battleView(ctx) {
  const b = ctx.bundle.field.battle;
  if (!b) return null;
  const active = b.state === 'active';
  const now = stateAt(b.timeline, b.hpMax, (Math.min(ctx.now, b.endsAt) - b.startedAt) / 1000);
  return {
    reportId: b.reportId, kind: b.kind, siteId: b.siteId, encounterId: b.encounterId, species: b.species, level: b.level, modifier: b.modifier,
    startedAt: b.startedAt, endsAt: b.endsAt, outcome: active ? 'pending' : b.finalOutcome, active,
    units: clone(b.units), hp: active ? now.hp : (b.finalOutcome === 'victory' ? 0 : b.hpMax), hpMax: b.hpMax, phase: now.phase,
    timeline: b.timeline,
    losses: b.losses ? clone(b.losses) : {wounded: {}, dead: {}},
    loot: b.loot ? {resources: clone(b.loot.resources), items: clone(b.loot.items), xp: b.loot.xp, overflow: clone(b.loot.overflow ?? {})} : null,
  };
}

function escortView(ctx) {
  const {field} = ctx.bundle;
  const entries = Object.entries(field.escorts);
  if (!entries.length) return null;
  const walking = entries.find(([, e]) => e.state === 'walking');
  const [siteId, e] = walking ?? entries.sort((a, b) => b[1].arrivedAt - a[1].arrivedAt)[0];
  const move = field.squad.move?.kind === 'escort' && field.squad.move.escortSiteId === siteId ? projectMove(ctx.graph, field.squad.move) : null;
  return {siteId, captiveIds: [...e.captiveIds], move, state: e.state, departAt: e.departAt, arriveAt: e.arriveAt, arrivedAt: e.arrivedAt};
}

function bossView(ctx) {
  const {campaign, field} = ctx.bundle;
  const b = field.battle?.kind === 'boss' ? field.battle : null;
  const defeated = campaign.phase === 'completed' || field.boss.state === 'defeated';
  const state = defeated ? 'defeated' : {prologue: 'locked', rescue: 'locked', boss_unlocked: 'available', boss_active: 'active'}[campaign.phase];
  let hp = BOSS.stats.hp, phase = BOSS.phases[0].id;
  if (defeated) { hp = 0; phase = BOSS.phases[BOSS.phases.length - 1].id; }
  else if (b?.state === 'active') {
    const s = stateAt(b.timeline, b.hpMax, (ctx.now - b.startedAt) / 1000);
    hp = s.hp; phase = s.phase ?? phase;
  }
  return {state, hp, hpMax: BOSS.stats.hp, phase, requiredHall: BOSS.requiredHall, attempts: field.boss.attempts, name: BOSS.name};
}

function horseView(ctx, unlocked) {
  const {campaign, field} = ctx.bundle;
  if (!unlocked) return {visible: false, node: null, mood: 'calm', move: null, position: null};
  if (campaign.phase === 'prologue') {
    return {visible: true, node: HORSE_ID, mood: 'waiting', move: null, position: roundPoint(ctx.graph.nodes.get(HORSE_ID)), joined: false};
  }
  const move = field.squad.move;
  const horseMove = projectHorseMove(ctx.graph, move);
  let mood = 'calm';
  if (T.battleActive(ctx)) mood = 'alert';
  else if (horseMove && ctx.now >= horseMove.arriveAt) mood = 'waiting';
  let position;
  if (move) {
    const path = movePath(ctx.graph, move);
    const t = Math.min(1, Math.max(0, (ctx.now - horseMove.departAt) / Math.max(1, horseMove.arriveAt - horseMove.departAt)));
    position = roundPoint(pointAt(path, t * path.length));
  } else position = positionNow(ctx.graph, field, ctx.now);
  return {visible: true, node: field.squad.node, mood, move: horseMove, position, joined: true};
}

function pointAt(path, d) {
  const {points, cum} = path;
  if (d <= 0) return points[0];
  for (let i = 1; i < points.length; i++) if (cum[i] >= d) {
    const t = (d - cum[i - 1]) / (cum[i] - cum[i - 1] || 1), a = points[i - 1], b = points[i];
    return {x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t};
  }
  return points[points.length - 1];
}

export function lockedReason(unlocked) {
  return unlocked ? null : 'FOREST_LOCKED_HALL_LEVEL';
}

export function projectAdventure(ctx) {
  const {campaign, field, fog, intro, prefs} = ctx.bundle;
  const unlocked = ctx.unlocked;
  const hall = Number.isSafeInteger(ctx.hall) ? ctx.hall : 0;
  const auth = {authenticatedPlayerId: ctx.p.id, hallLevel: hall};
  const fogView = fogModule.projectFogForClient(fog, auth, {pois: poiMeta(ctx.graph), protectedTownCells: ctx.ports.protectedTownCells(ctx.p)});
  const visible = new Set(fogView.visiblePoiIds);
  const introView = access.projectAdventureAccess(intro, {...auth, cityForeground: true, uiReady: true, activeCombat: T.battleActive(ctx), modalOpen: false, loading: false});
  const acts = actUnlocked(campaign);
  const sites = SITES.map(s => {
    const {step, artifact} = campaign.sites[s.id];
    return {id: s.id, step, artifact, act: s.act, available: unlocked && acts[s.act - 1], visible: unlocked && (visible.has(s.id) || step >= 1)};
  });
  const pois = [];
  if (unlocked) {
    for (const id of [HOME_ID, HORSE_ID]) pois.push({id, kind: ctx.graph.nodes.get(id).kind, ...roundPoint(ctx.graph.nodes.get(id))});
    for (const s of SITES) if (visible.has(s.id) || campaign.sites[s.id].step >= 1) pois.push(siteView(ctx, s, acts[s.act - 1]));
    if (visible.has(BRIDGE_ID)) pois.push({id: BRIDGE_ID, kind: 'bridge', ...roundPoint(ctx.graph.nodes.get(BRIDGE_ID))});
    if (visible.has(BOSS_TARGET_ID) || ['boss_unlocked', 'boss_active', 'completed'].includes(campaign.phase)) {
      pois.push({id: BOSS_TARGET_ID, kind: 'boss_arena', name: 'Костяная чаша', ...roundPoint(ctx.graph.nodes.get(BOSS_TARGET_ID)), prisoners: 0});
    }
  }
  const squadUnits = clone(field.squad.units);
  return {
    campaignId: CAMPAIGN_ID,
    schemaVersion: 1,
    serverTime: ctx.now,
    revision: field.revision,
    access: {unlocked, hallLevel: hall, requiredHall: MIN_HALL_LEVEL_EXPORT, reason: lockedReason(unlocked)},
    intro: {status: intro.status, deferred: intro.deferred, offer: introView.autoStartEligible, invitation: introView.invitationAvailable,
      continueRequired: introView.continueRequired, attempt: intro.attempts, acknowledgment: intro.acknowledgment},
    fog: {explorationLocked: fogView.explorationLocked, ...FOG_GRID, visibleBase64: fogView.visibleTerrainBase64, revision: fogView.storedFogRevision,
      entranceCorridor: clone(fogModule.ENTRANCE_CORRIDOR), boundaryFog: fogView.boundaryFog},
    campaign: {phase: campaign.phase, paused: campaign.paused, revision: campaign.revision, horseJoined: campaign.phase !== 'prologue',
      sites, rescuedIds: [...campaign.rescuedIds], rescuedCount: campaign.rescuedIds.length, actUnlocked: unlocked ? acts : [false, false, false, false]},
    escrow: clone(campaign.escrow),
    autoRefill: prefs.autoRefill,
    squad: unlocked
      ? {units: squadUnits, members: Math.min(3, sumUnits(squadUnits)), node: field.squad.node, position: positionNow(ctx.graph, field, ctx.now),
        move: projectMove(ctx.graph, field.squad.move), busy: busy(ctx)}
      : {units: squadUnits, members: Math.min(3, sumUnits(squadUnits)), node: null, position: null, move: null, busy: null},
    horse: horseView(ctx, unlocked),
    pois,
    battle: unlocked ? battleView(ctx) : null,
    escort: unlocked ? escortView(ctx) : null,
    boss: unlocked ? bossView(ctx) : {state: 'locked', hp: BOSS.stats.hp, hpMax: BOSS.stats.hp, phase: BOSS.phases[0].id, requiredHall: BOSS.requiredHall, attempts: 0, name: BOSS.name},
    nextTask: unlocked ? nextTask(campaign, field) : null,
    recentEvents: unlocked ? clone(field.events) : [],
  };
}

/** Projection when a namespace cannot be loaded: explicit error, nothing hidden is leaked. */
export function projectError(ctx, error) {
  const hall = Number.isSafeInteger(ctx.hall) ? ctx.hall : 0;
  return {
    campaignId: CAMPAIGN_ID, schemaVersion: 1, serverTime: ctx.now,
    error: error.toBody(),
    access: {unlocked: false, hallLevel: hall, requiredHall: MIN_HALL_LEVEL_EXPORT, reason: error.code},
    pois: [], horse: {visible: false, node: null, mood: 'calm', move: null, position: null},
    fog: {explorationLocked: true, ...FOG_GRID, visibleBase64: null, revision: null, entranceCorridor: clone(fogModule.ENTRANCE_CORRIDOR)},
  };
}

