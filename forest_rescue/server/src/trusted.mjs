// Server-built trusted contexts for the delivered reducers. Every proof is derived from
// the committed records of the selected player p (field namespace), never from the body.
import {siteDef, HOME_ID, BOSS_TARGET_ID, BOSS_ENCOUNTER_ID, BOSS_SPECIES, guardianEncounterId} from './content.mjs';
import {resolveRef} from './navgraph.mjs';
import {sumUnits} from './util.mjs';

export function squadUnits(ctx) {
  return sumUnits(ctx.bundle.field.squad.units);
}

export function battleActive(ctx) {
  return ctx.bundle.field.battle?.state === 'active';
}

export function escortWalking(ctx) {
  return Object.entries(ctx.bundle.field.escorts).find(([, e]) => e.state === 'walking') ?? null;
}

/** Site whose glade contains a graph ref (junction or fine node on a glade way), or null. */
export function siteOfRef(graph, ref) {
  const r = resolveRef(graph, ref);
  if (!r) return null;
  if (r.junction) return r.junction.kind === 'site' ? r.junction.id : (r.junction.siteId ?? null);
  return r.way.kind === 'glade' ? r.way.siteId : null;
}

export function stationary(ctx) {
  return ctx.bundle.field.squad.move === null;
}

/** Committed arrival at an exact graph node by a server-planned move. */
export function arrivedAt(ctx, nodeId) {
  const squad = ctx.bundle.field.squad;
  return squad.move === null && squad.node === nodeId && squad.arrival?.targetId === nodeId && sumUnits(squad.units) > 0;
}

/** Squad physically present (stationary, committed) anywhere in the glade of siteId. */
export function presentInGlade(ctx, siteId) {
  const squad = ctx.bundle.field.squad;
  return squad.move === null && sumUnits(squad.units) > 0 && squad.arrival !== null && siteOfRef(ctx.graph, squad.node) === siteId;
}

export function arrivalProof(ctx, targetId) {
  return arrivedAt(ctx, targetId) ? {ownerId: ctx.p.id, targetId, serverVerified: true, routeValid: true} : undefined;
}

export function siteArrivalProof(ctx, siteId) {
  return presentInGlade(ctx, siteId) ? {ownerId: ctx.p.id, targetId: siteId, serverVerified: true, routeValid: true} : undefined;
}

export function mechanismProof(ctx, siteId) {
  return ctx.bundle.mechanisms[siteId]?.solved === true
    ? {ownerId: ctx.p.id, siteId, serverVerified: true, solved: true} : undefined;
}

function proofFromVictory(ctx, siteId, victory) {
  if (!victory || victory.encounterId === null) return undefined;
  return {reportId: victory.reportId, encounterId: victory.encounterId, ownerId: ctx.p.id, siteId,
    species: victory.species, level: victory.level ?? undefined, modifier: victory.modifier,
    serverVerified: true, finalized: true, outcome: 'victory'};
}

export function guardianBattleContext(ctx, siteId) {
  siteDef(siteId);
  return {battleProof: proofFromVictory(ctx, siteId, ctx.bundle.field.guardians[siteId]?.victory), expectedEncounterId: guardianEncounterId(siteId)};
}

export function bossBattleContext(ctx) {
  // species comes from the finalized boss report (must be ancient_maw; the reducer checks).
  const proof = proofFromVictory(ctx, BOSS_TARGET_ID, ctx.bundle.field.boss.victory);
  if (proof && proof.species !== BOSS_SPECIES) return {battleProof: undefined, expectedEncounterId: BOSS_ENCOUNTER_ID};
  return {battleProof: proof, expectedEncounterId: BOSS_ENCOUNTER_ID};
}

export function escortProof(ctx, siteId) {
  const e = ctx.bundle.field.escorts[siteId];
  const expected = siteDef(siteId).captives.map(c => c.id);
  if (!e || e.state !== 'home' || e.arrivedAt === null || !expected.every((id, i) => e.captiveIds[i] === id)) return undefined;
  return {ownerId: ctx.p.id, siteId, captiveIds: [...e.captiveIds], serverVerified: true, arrivedHome: true};
}

/** Simultaneous server-side plate occupancy for the paired latch of siteId at ctx.now. */
export function platesStatus(ctx, siteId) {
  const f = ctx.bundle.field, plates = f.plates;
  if (!plates || plates.siteId !== siteId) return {state: 'free', held: false};
  const intact = f.squad.move === null && f.squad.node === plates.anchor && !battleActive(ctx) && sumUnits(f.squad.units) >= 2;
  if (!intact) return {state: 'free', held: false};
  if (ctx.now < plates.readyAt) return {state: 'walking', held: false, readyAt: plates.readyAt};
  return {state: 'held', held: true, readyAt: plates.readyAt};
}

export function isHome(ref) {
  return ref === HOME_ID;
}
