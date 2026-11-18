// Server-timed movement on the adventure graph. Positions are a pure function of the
// persisted move record and server time; arrival is committed lazily by settle(now).
import {TROOPS} from './catalog.mjs';
import {planPath, expandSteps, pointAtDistance, indexAtDistance, refAt, refPosition, simplifyForClient, roundPoint} from './navgraph.mjs';
import {round} from './util.mjs';

export const SPEED_FACTOR = 0.6;      // world units/s per catalog speed point (ENG-09: 4 → 2.4)
export const ESCORT_SPEED = 1.6;      // rescued civilians walk slower than the squad
export const CHECKPOINT_UNITS = 4;    // committed traversal granularity for fog reveal
export const HORSE_LEAD_MS = 1500;    // the horse arrives first and waits for the squad

export function squadSpeed(units) {
  let slowest = Infinity;
  for (const [id, n] of Object.entries(units ?? {})) if (n > 0 && TROOPS[id]) slowest = Math.min(slowest, TROOPS[id].speed);
  return Number.isFinite(slowest) ? round(slowest * SPEED_FACTOR, 3) : 0;
}

const cache = new Map();
export function movePath(graph, move) {
  const key = graph.graphId + '|' + JSON.stringify([move.start, move.steps]);
  let path = cache.get(key);
  if (!path) {
    path = expandSteps(graph, move.steps, move.start);
    cache.set(key, path);
    if (cache.size > 512) cache.delete(cache.keys().next().value);
  }
  return path;
}

export function distanceAt(move, path, now) {
  if (now >= move.arriveAt) return path.length;
  if (now <= move.departAt) return 0;
  return Math.min(path.length, move.speed * (now - move.departAt) / 1000);
}

export function durationMs(length, speed) {
  return speed > 0 ? Math.ceil(length / speed * 1000) : 0;
}

/** Build a new move record; returns null when the target is unreachable. */
export function buildMove(graph, {serial, kind, fromRef, start = null, targetId, now, speed, escortSiteId = null, aheadLoc = null}) {
  let steps;
  if (aheadLoc) {
    // Mid-segment: first reach the next graph point ahead, then follow the plan from there.
    const aheadRef = refAt(graph, graph.ways.get(aheadLoc.w), aheadLoc.i);
    if (aheadRef === targetId || targetId === null) steps = [{w: aheadLoc.w, a: aheadLoc.i, b: aheadLoc.i}];
    else {
      const plan = planPath(graph, aheadRef, targetId);
      if (!plan) return null;
      steps = plan.steps.length ? plan.steps : [{w: aheadLoc.w, a: aheadLoc.i, b: aheadLoc.i}];
    }
    targetId ??= aheadRef;
  } else {
    const plan = planPath(graph, fromRef, targetId);
    if (!plan) return null;
    steps = plan.steps;
  }
  const move = {serial, kind, targetId, start, steps, departAt: now, arriveAt: now, speed, committed: 0, escortSiteId};
  const path = movePath(graph, move);
  move.arriveAt = now + durationMs(path.length, speed);
  return move;
}

/** Current position and the next graph point ahead (for stop / redirect). */
export function anchorAt(graph, move, now) {
  const path = movePath(graph, move);
  const d = distanceAt(move, path, now);
  const position = pointAtDistance(path, d);
  let ahead = indexAtDistance(path, d);
  if (path.cum[ahead] < d - 1e-9 || !path.locs[ahead]) ahead = Math.min(path.points.length - 1, ahead + 1);
  while (!path.locs[ahead] && ahead < path.points.length - 1) ahead++;
  const exact = Math.abs(path.cum[ahead] - d) < 1e-9;
  return {path, d, position, aheadIndex: ahead, aheadLoc: path.locs[ahead], start: exact ? null : position};
}

export function projectMove(graph, move) {
  if (!move) return null;
  const path = movePath(graph, move);
  return {path: simplifyForClient(path), departAt: move.departAt, arriveAt: move.arriveAt, targetId: move.targetId,
    speed: move.speed, kind: move.kind, length: round(path.length, 3)};
}

/** The riderless horse leads along the squad path and arrives HORSE_LEAD_MS earlier. */
export function projectHorseMove(graph, move) {
  if (!move) return null;
  const base = projectMove(graph, move);
  const duration = move.arriveAt - move.departAt;
  const lead = Math.min(HORSE_LEAD_MS, Math.floor(duration * 0.2));
  const arriveAt = move.arriveAt - lead;
  return {...base, arriveAt, speed: arriveAt > move.departAt ? round(base.length / ((arriveAt - move.departAt) / 1000), 3) : base.speed};
}

export function positionNow(graph, field, now) {
  const move = field.squad.move;
  if (move) {
    const path = movePath(graph, move);
    return roundPoint(pointAtDistance(path, distanceAt(move, path, now)));
  }
  const p = refPosition(graph, field.squad.node);
  return p ? roundPoint(p) : null;
}

/** Points of the committed prefix, re-spaced to ≤2 units for the delivered fog module. */
export function committedFogPath(path, upto) {
  const out = [];
  let since = 0;
  for (let i = 0; i <= upto; i++) {
    const p = path.points[i];
    if (i === 0) { out.push({x: p.x, z: p.z}); continue; }
    since += path.cum[i] - path.cum[i - 1];
    if (since >= 1.5 || i === upto) { out.push({x: p.x, z: p.z}); since = 0; }
  }
  return out;
}
