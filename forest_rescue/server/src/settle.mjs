// Lazy settle(now): commits whatever the server clock says has already happened —
// battle results at endsAt (losses applied to the real army, loot, one-time guardian
// defeat), traversal checkpoints with fog reveal through the delivered fog authority
// (its resolveTraversal reads ONLY the committed move record), trail landmark
// observations, arrivals and escort arrivals.
import {fog as fogModule} from './vendor.mjs';
import {HOME_ID} from './content.mjs';
import {creatureSpec as localCreatureSpec} from './catalog.mjs';
import {knockedUntil, splitLosses} from './battle.mjs';
import {movePath, distanceAt, CHECKPOINT_UNITS, committedFogPath} from './movement.mjs';
import {indexAtDistance} from './navgraph.mjs';
import {rng, sumUnits, normalizeUnits, clone} from './util.mjs';

export const SQUAD_ACTOR = 'squad';
export const routeIdOf = move => 'mv' + move.serial;
export const cursorKey = move => JSON.stringify([SQUAD_ACTOR, routeIdOf(move)]);

function fogBits(state) {
  return Buffer.from(state.exploredBase64, 'base64');
}

function newlyRevealed(before, after) {
  const a = fogBits(before), b = fogBits(after), cells = [];
  for (let i = 0; i < b.length; i++) {
    const diff = b[i] & ~a[i];
    if (diff) for (let k = 0; k < 8; k++) if (diff & (1 << k)) cells.push(i * 8 + k);
  }
  return cells;
}

/** Reveal along the committed prefix [0..move.committed] of the squad's move. */
async function revealCommitted(ctx, move) {
  if (move.committed < 1 || !ctx.unlocked) return;
  const graph = ctx.graph, owner = ctx.p.id;
  const authority = fogModule.createFogAuthority({
    resolveTraversal: async ({authenticatedPlayerId, actorId, routeId}) => {
      const current = ctx.bundle.field.squad.move; // committed candidate state only
      if (authenticatedPlayerId !== owner || actorId !== SQUAD_ACTOR || !current || routeIdOf(current) !== routeId) return null;
      return {ownerId: owner, actorId, routeId, sequence: current.committed, committed: true, navigationChecked: true,
        path: committedFogPath(movePath(graph, current), current.committed)};
    },
  });
  const before = ctx.bundle.fog;
  const after = await authority.reveal(before, {actorId: SQUAD_ACTOR, routeId: routeIdOf(move)}, {authenticatedPlayerId: owner, hallLevel: ctx.hall});
  if (after.revision !== before.revision) {
    const cells = newlyRevealed(before, after);
    ctx.bundle.fog = after;
    if (cells.length) ctx.emit('fog_revealed', {cells, count: cells.length});
  }
}

function observeLandmarks(ctx, path, upto) {
  const {field, campaign} = ctx.bundle;
  for (const mark of path.marks) {
    if (mark.i > upto) break;
    const node = ctx.graph.nodes.get(mark.nodeId);
    if (node?.kind !== 'landmark' || campaign.sites[node.siteId].step < 1) continue;
    const trail = field.trails[node.siteId] ??= {observed: []};
    if (!trail.observed.includes(node.symbol)) {
      trail.observed.push(node.symbol);
      ctx.emit('landmark_observed', {siteId: node.siteId, symbol: node.symbol});
    }
  }
}

/** Commit traversal of the current move up to `now` (checkpoint granularity unless forced). */
export async function commitTraversal(ctx, {force = false} = {}) {
  const move = ctx.bundle.field.squad.move;
  if (!move) return;
  const path = movePath(ctx.graph, move);
  const arrived = ctx.now >= move.arriveAt;
  const idx = arrived ? path.points.length - 1 : indexAtDistance(path, distanceAt(move, path, ctx.now));
  if (idx <= move.committed) return;
  if (!arrived && !force && path.cum[idx] - path.cum[move.committed] < CHECKPOINT_UNITS) return;
  move.committed = idx;
  observeLandmarks(ctx, path, idx);
  await revealCommitted(ctx, move);
}

/** Close a finished/replaced move: its fog cursor is archived (never resolved again). */
export function archiveMoveCursor(ctx, move) {
  const key = cursorKey(move);
  if (Object.hasOwn(ctx.bundle.fog.cursors, key)) {
    const cursors = {...ctx.bundle.fog.cursors};
    delete cursors[key];
    ctx.bundle.fog = {...ctx.bundle.fog, cursors};
  }
}

function completeMove(ctx, move) {
  const field = ctx.bundle.field;
  field.squad.node = move.targetId;
  field.squad.arrival = {targetId: move.targetId, serial: move.serial, at: move.arriveAt};
  field.squad.move = null;
  archiveMoveCursor(ctx, move);
  ctx.emit('squad_arrived', {targetId: move.targetId, at: move.arriveAt});
  if (move.kind === 'escort') {
    const escort = field.escorts[move.escortSiteId];
    if (escort && escort.state === 'walking' && escort.moveSerial === move.serial) {
      escort.state = 'home';
      escort.arrivedAt = move.arriveAt;
      ctx.emit('escort_arrived', {siteId: move.escortSiteId, captiveIds: [...escort.captiveIds]});
    }
  }
}

async function settleMovement(ctx) {
  const move = ctx.bundle.field.squad.move;
  if (!move) return;
  await commitTraversal(ctx);
  if (ctx.now >= move.arriveAt) completeMove(ctx, move);
}

export function rollGuardianLoot(spec, seed) {
  const R = rng((seed ^ 0x5bd1e995) >>> 0);
  const items = {hides: spec.rewards.hides, [spec.item]: spec.rewards.material};
  if (R() < spec.rewards.rareChance) items[spec.rare] = 1;
  return {resources: {food: spec.rewards.food}, items, xp: spec.xp};
}

function subtractUnits(units, knocked) {
  const out = {...units};
  for (const [id, n] of Object.entries(knocked)) out[id] = Math.max(0, (out[id] ?? 0) - n);
  return normalizeUnits(out);
}

/** Finalize the active battle with `outcome` at server time `at` (endsAt or retreat time). */
export function finalizeBattle(ctx, outcome, at) {
  const {field} = ctx.bundle;
  const b = field.battle;
  const elapsed = Math.max(0, (at - b.startedAt) / 1000);
  if (outcome === 'retreat') {
    b.timeline = b.timeline.filter(e => e.t <= elapsed + 1e-9);
    b.timeline.push({t: Math.round(elapsed * 100) / 100, type: 'retreat', actor: 'squad'});
    b.knocks = b.knocks.filter(k => k.t <= elapsed + 1e-9);
    b.endsAt = at;
  }
  const knocked = knockedUntil(b.knocks, outcome === 'retreat' ? elapsed : Infinity);
  const split = splitLosses(knocked, outcome);
  const applied = ctx.ports.applyLosses(ctx.p, split, b);
  field.squad.units = subtractUnits(field.squad.units, knocked);
  let loot = null;
  if (outcome === 'victory') {
    const victory = {reportId: b.reportId, encounterId: b.encounterId, species: b.species, level: b.level, modifier: b.modifier, finalizedAt: at};
    if (b.kind === 'guardian') {
      const g = field.guardians[b.siteId];
      g.state = 'defeated';
      g.victory = victory;
      // Ordinary first-victory loot (a separate line; NOT part of the campaign escrow).
      const spec = ctx.ports.creatureSpec(b.species, b.level) ?? localCreatureSpec(b.species, b.level);
      loot = ctx.ports.applyLoot(ctx.p, rollGuardianLoot(spec, b.seed), b);
    } else {
      field.boss.state = 'defeated';
      field.boss.victory = victory;
      loot = {resources: {}, items: {}, xp: 0, overflow: {}, note: 'new species ancient_maw has no ordinary loot table; the campaign final reward is claimed via finish_boss'};
    }
  }
  b.state = 'finalized';
  b.finalOutcome = outcome;
  b.finalizedAt = at;
  b.losses = applied;
  b.loot = loot;
  ctx.ports.pushReport(ctx.p, battleReportSummary(ctx, b));
  ctx.emit('battle_report', {reportId: b.reportId, siteId: b.siteId, outcome});
  if (b.kind === 'boss' && outcome === 'victory') ctx.emit('boss_defeated', {reportId: b.reportId});
  if (sumUnits(field.squad.units) === 0) {
    // Nobody left standing: the (empty) squad record returns home; progress is untouched.
    field.squad = {units: {}, node: HOME_ID, move: null, arrival: null};
    field.plates = null;
    ctx.emit('squad_returned_home', {reason: 'no_units_left'});
  }
}

export function battleReportSummary(ctx, b) {
  const spec = b.kind === 'guardian' ? (ctx.ports.creatureSpec(b.species, b.level) ?? localCreatureSpec(b.species, b.level)) : null;
  const knocked = {};
  for (const bag of [b.losses.wounded, b.losses.dead]) for (const [id, n] of Object.entries(bag)) knocked[id] = (knocked[id] ?? 0) + n;
  return {
    id: b.reportId, kind: 'adventure', campaignId: 'forest_rescue_v1', siteId: b.siteId, encounterId: b.encounterId,
    creature: {name: b.kind === 'boss' ? 'Пращур' : spec.name, species: b.species, level: b.level ?? 0},
    outcome: b.finalOutcome === 'victory' ? 'victory' : 'defeat', adventureOutcome: b.finalOutcome,
    at: b.finalizedAt, startedAt: b.startedAt,
    surviving: subtractUnits(b.units, knocked), wounded: clone(b.losses.wounded), dead: clone(b.losses.dead),
    rewards: b.loot ? {resources: clone(b.loot.resources), items: clone(b.loot.items), xp: b.loot.xp} : {resources: {}, items: {}, xp: 0},
  };
}

function settleBattle(ctx) {
  const b = ctx.bundle.field.battle;
  if (!b || b.state !== 'active') return;
  const elapsed = (Math.min(ctx.now, b.endsAt) - b.startedAt) / 1000;
  if (b.kind === 'boss') {
    // boss_phase cues committed lazily once server time passes the phase change.
    const phases = b.timeline.filter(e => e.type === 'phase' && e.t <= elapsed + 1e-9).map(e => e.phase);
    const seen = phases.indexOf(b.announcedPhase);
    for (const phase of phases.slice(seen + 1)) { b.announcedPhase = phase; ctx.emit('boss_phase', {phase, reportId: b.reportId}); }
  }
  if (ctx.now >= b.endsAt) finalizeBattle(ctx, b.outcome, b.endsAt);
}

/** Reserved squad units never exceed the real healthy army (units are never created). */
export function clampSquad(ctx) {
  const {field} = ctx.bundle;
  if (field.battle?.state === 'active') return;
  const healthy = ctx.ports.healthyUnits(ctx.p);
  const units = {};
  for (const [id, n] of Object.entries(field.squad.units)) units[id] = Math.min(n, healthy[id] ?? 0);
  const next = normalizeUnits(units);
  if (JSON.stringify(next) !== JSON.stringify(field.squad.units)) {
    field.squad.units = next;
    if (sumUnits(next) === 0 && field.squad.node !== HOME_ID && field.squad.move === null) {
      field.squad = {units: {}, node: HOME_ID, move: null, arrival: null};
      field.plates = null;
    }
  }
}

export async function settleBundle(ctx) {
  settleBattle(ctx);
  if (ctx.unlocked) await settleMovement(ctx);
  clampSquad(ctx);
}
