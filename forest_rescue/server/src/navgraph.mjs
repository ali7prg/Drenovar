// Adventure navigation graph built from delivery/data/world-atlas.json.
//
// * Ways are polylines: the 13 authored routes (samples ≤0.5 apart, y from the samples),
//   a short spur to the home reception, and densified glade spokes to the per-site
//   cage / guardian / artifact (key) spots taken from the atlas site offsets, plus the
//   paired-latch plates and trail-cache landmarks derived from those offsets.
// * Junctions are named targets (CONTRACT §2.2). Dijkstra runs on junctions; a squad
//   that stopped between junctions sits on a fine node "<wayId>#<index>".
// * Validation at build time (fail closed): spacing ≤0.5, bounds [-112,112), dry ground
//   by the atlas river samples except on the approved deck of the new bridge on
//   bridge way (v2 lf_route_bridge, v1 lf_route_10_11), glade points inside their clearing, endpoints
//   match atlas centres. Atlas v2 (server/data/world-atlas.v2.json, art/01 masterplan) is a network:
//   junction landmarks, radial trails and loops; Dijkstra runs on the junctions unchanged.
import {data} from './vendor.mjs';
import {SITES, HOME_ID, HORSE_ID, BRIDGE_ID, BOSS_TARGET_ID} from './content.mjs';
import {sha256Hex, round} from './util.mjs';

export const MAX_SPACING = 0.5;
const EPS = 1e-6;
// The way that crosses the river on the approved deck: atlas v2 'lf_route_bridge' (v1: lf_route_10_11),
// recognised by its 'walk+bridge' traversal so a different atlas keeps working.
const BRIDGE_ROUTE_IDS = ['lf_route_bridge', 'lf_route_10_11'];
const isBridgeRoute = route => BRIDGE_ROUTE_IDS.includes(route.id) || String(route.traversal ?? '').includes('bridge');
export const HOME_OFFSET_Z = 3; // home reception: 3 units south (town side) of the horse origin
const PLATE_OFFSET = 2.6;
// Trail landmarks (glade-local, x mirrored to the artifact side): outside the guardian zone.
const TRAIL_LOCAL = [{x: 1.5, z: -4.5}, {x: 5.0, z: -3.5}, {x: 5.5, z: 0.5}];

const navError = (code, detail) => Object.assign(new Error(code), {code, detail});

function hdist(a, b) {
  return Math.hypot(b.x - a.x, b.z - a.z);
}

function densify(a, b, y) {
  const n = Math.max(1, Math.ceil(hdist(a, b) / MAX_SPACING - 1e-9));
  const out = [];
  for (let i = 0; i <= n; i++) out.push({x: a.x + (b.x - a.x) * i / n, y, z: a.z + (b.z - a.z) * i / n});
  return out;
}

function riverWetAt(river, x, z) {
  const s = river.samples;
  if (z < s[0].z || z > s[s.length - 1].z) return false;
  let i = Math.min(s.length - 2, Math.max(0, Math.floor((z - s[0].z) / (s[1].z - s[0].z))));
  while (i > 0 && s[i].z > z) i--;
  while (i < s.length - 2 && s[i + 1].z < z) i++;
  const a = s[i], b = s[i + 1], t = (z - a.z) / (b.z - a.z || 1);
  const west = a.wetWest + (b.wetWest - a.wetWest) * t, east = a.wetEast + (b.wetEast - a.wetEast) * t;
  return x >= west && x <= east;
}

export function buildNavGraph(atlas = data.atlas) {
  const ways = new Map();
  const nodes = new Map();
  const centers = new Map([...atlas.sites, ...atlas.landmarks].map(p => [p.id, p.center]));
  const bridge = atlas.landmarks.find(l => l.id === BRIDGE_ID);
  if (!bridge) throw navError('NAV_BRIDGE_MISSING');
  const nodeIdFor = atlasId => atlasId === 'lf_boss_arena' ? BOSS_TARGET_ID : atlasId;

  function addNode(id, p, meta) {
    const existing = nodes.get(id);
    if (existing) {
      if (Math.abs(existing.x - p.x) > EPS || Math.abs(existing.z - p.z) > EPS) throw navError('NAV_JUNCTION_MISMATCH', {id});
      return existing;
    }
    const node = Object.freeze({id, x: p.x, y: p.y, z: p.z, ...meta});
    nodes.set(id, node);
    return node;
  }
  function addWay(id, kind, points, junctions, extra = {}) {
    if (ways.has(id)) throw navError('NAV_DUPLICATE_WAY', {id});
    ways.set(id, {id, kind, points: points.map(p => Object.freeze({x: p.x, y: p.y, z: p.z})), junctions, ...extra});
  }

  // 1. Authored routes.
  for (const route of atlas.routes) {
    const from = centers.get(route.from), to = centers.get(route.to);
    if (!from || !to) throw navError('NAV_ROUTE_ENDPOINT', {route: route.id});
    const pts = route.samples.map(s => ({x: s.x, y: s.y, z: s.z, deck: false}));
    if (hdist(pts[0], from) > EPS || hdist(pts[pts.length - 1], to) > EPS) throw navError('NAV_ROUTE_ENDPOINT', {route: route.id});
    const junctions = [];
    if (isBridgeRoute(route)) {
      // Approved geometry: the samples ON the bridge axis between the two bank entries
      // (west (77,20) … east (104,20); the atlas road profile there is the 1.1 deck).
      const c = bridge.center;
      const onDeck = p => Math.abs(p.z - c.z) < EPS && p.x >= bridge.west.x - EPS && p.x <= bridge.east.x + EPS;
      for (const p of pts) if (onDeck(p)) { p.y = bridge.structuralHeight; p.deck = true; }
      // Insert the named bridge-centre junction exactly at the authored centre.
      const k = pts.findIndex((p, i) => i > 0 && p.deck && pts[i - 1].deck && pts[i - 1].x <= c.x && p.x >= c.x && Math.abs(p.z - c.z) < EPS);
      if (k < 0) throw navError('NAV_BRIDGE_NOT_ON_ROUTE');
      if (Math.abs(pts[k].x - c.x) < EPS) pts[k].x = c.x;
      else pts.splice(k, 0, {x: c.x, y: bridge.structuralHeight, z: c.z, deck: true});
      const bridgeIndex = pts.findIndex(p => Math.abs(p.x - c.x) < EPS && Math.abs(p.z - c.z) < EPS);
      addNode(BRIDGE_ID, pts[bridgeIndex], {kind: 'bridge'});
      junctions.push({index: bridgeIndex, nodeId: BRIDGE_ID});
    }
    const fromId = nodeIdFor(route.from), toId = nodeIdFor(route.to);
    addNode(fromId, {...pts[0], y: pts[0].y}, {kind: kindOf(fromId)});
    addNode(toId, pts[pts.length - 1], {kind: kindOf(toId)});
    junctions.push({index: 0, nodeId: fromId}, {index: pts.length - 1, nodeId: toId});
    addWay(route.id, 'route', pts, junctions, {deck: pts.map(p => p.deck), bridge: isBridgeRoute(route)});
  }

  // 2. Home reception spur (north approach of the settlement, inside the protected square).
  const horse = centers.get(HORSE_ID);
  const home = {x: horse.x, y: horse.y, z: horse.z + HOME_OFFSET_Z};
  const spur = densify(home, horse, horse.y);
  addNode(HOME_ID, spur[0], {kind: 'home'});
  addWay('lf_spur_home', 'spur', spur, [{index: 0, nodeId: HOME_ID}, {index: spur.length - 1, nodeId: HORSE_ID}]);

  // 3. Glade spokes per site; y = glade pad height (site centre sample).
  for (const site of SITES) {
    const c = nodes.get(site.id);
    if (!c) throw navError('NAV_SITE_NOT_ROUTED', {site: site.id});
    const local = o => ({x: c.x + o.x, y: c.y, z: c.z + o.z});
    const side = Math.sign(site.offsets.artifact.x) || 1;
    const spots = {
      cage: local(site.offsets.cage),
      guardian: local(site.offsets.guardian),
      key: local(site.offsets.artifact),
    };
    const ids = {cage: site.id + ':cage', guardian: site.id + ':guardian', key: site.artifact.id};
    addNode(ids.cage, spots.cage, {kind: 'cage', siteId: site.id});
    addNode(ids.guardian, spots.guardian, {kind: 'guardian', siteId: site.id});
    addNode(ids.key, spots.key, {kind: 'key', siteId: site.id});
    const spoke = (suffix, fromId, fromP, toId, toP) => {
      const pts = densify(fromP, toP, c.y);
      addWay(site.id + '>' + suffix, 'glade', pts, [{index: 0, nodeId: fromId}, {index: pts.length - 1, nodeId: toId}], {siteId: site.id});
    };
    spoke('cage', site.id, c, ids.cage, spots.cage);
    spoke('guardian', site.id, c, ids.guardian, spots.guardian);
    if (site.variation === 'trail_cache') {
      // The cache is reachable ONLY along the authored trail: centre → L1 → L2 → L3 → key.
      let prevId = site.id, prevP = c;
      site.puzzle.solution.forEach((symbol, i) => {
        const p = local({x: TRAIL_LOCAL[i].x * side, z: TRAIL_LOCAL[i].z});
        const id = site.id + ':landmark:' + symbol;
        addNode(id, p, {kind: 'landmark', siteId: site.id, symbol});
        spoke('trail:' + (i + 1), prevId, prevP, id, p);
        prevId = id; prevP = p;
      });
      spoke('trail:4', prevId, prevP, ids.key, spots.key);
    } else {
      spoke('key', site.id, c, ids.key, spots.key);
    }
    if (site.variation === 'paired_latch') {
      const left = {x: spots.key.x, y: c.y, z: spots.key.z - PLATE_OFFSET};
      const right = {x: spots.key.x, y: c.y, z: spots.key.z + PLATE_OFFSET};
      addNode(site.id + ':plate_left', left, {kind: 'plate', siteId: site.id, plate: 'left'});
      addNode(site.id + ':plate_right', right, {kind: 'plate', siteId: site.id, plate: 'right'});
      spoke('plate_left', site.id, c, site.id + ':plate_left', left);
      spoke('plate_right', site.id, c, site.id + ':plate_right', right);
    }
  }

  // 4. Validation.
  for (const way of ways.values()) {
    const pts = way.points;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      if (![p.x, p.y, p.z].every(Number.isFinite) || p.x < -112 || p.x >= 112 || p.z < -112 || p.z >= 112) throw navError('NAV_OUT_OF_BOUNDS', {way: way.id, i});
      if (i > 0 && hdist(pts[i - 1], p) > MAX_SPACING + 1e-9) throw navError('NAV_SPACING', {way: way.id, i});
      const wet = riverWetAt(atlas.river, p.x, p.z);
      if (wet && !(way.bridge && way.deck[i])) throw navError('NAV_WATER_OUTSIDE_BRIDGE', {way: way.id, i});
      if (way.kind === 'glade') {
        const site = nodes.get(way.siteId);
        if (hdist(site, p) > SITES.find(s => s.id === way.siteId).clearingRadius + EPS) throw navError('NAV_OUTSIDE_CLEARING', {way: way.id, i});
      }
    }
    way.junctions.sort((a, b) => a.index - b.index);
    way.cum = [0];
    for (let i = 1; i < pts.length; i++) way.cum.push(way.cum[i - 1] + hdist(pts[i - 1], pts[i]));
    Object.freeze(way.points);
  }

  // 5. Junction adjacency (segments between consecutive junctions of a way).
  const adjacency = new Map([...nodes.keys()].map(id => [id, []]));
  for (const way of ways.values()) {
    for (let k = 0; k + 1 < way.junctions.length; k++) {
      const a = way.junctions[k], b = way.junctions[k + 1];
      const length = way.cum[b.index] - way.cum[a.index];
      adjacency.get(a.nodeId).push({to: b.nodeId, w: way.id, a: a.index, b: b.index, length});
      adjacency.get(b.nodeId).push({to: a.nodeId, w: way.id, a: b.index, b: a.index, length});
    }
  }
  const fingerprint = [...ways.values()].map(w => [w.id, w.points.map(p => [round(p.x, 4), round(p.y, 4), round(p.z, 4)])]);
  const graphId = 'fr-nav-1-' + sha256Hex(JSON.stringify(fingerprint)).slice(0, 16);
  return Object.freeze({graphId, ways, nodes, adjacency});
}

function kindOf(id) {
  if (id === HORSE_ID) return 'horse_origin';
  if (id === BOSS_TARGET_ID) return 'boss_arena';
  if (id === HOME_ID) return 'home';
  return 'site';
}

export function isJunction(graph, ref) {
  return graph.nodes.has(ref);
}

/** Resolve a junction id or fine node "<way>#<index>" to {way, index} / junction. */
export function resolveRef(graph, ref) {
  if (typeof ref !== 'string') return null;
  if (graph.nodes.has(ref)) return {junction: graph.nodes.get(ref)};
  const m = /^(.+)#(\d{1,5})$/.exec(ref);
  if (!m) return null;
  const way = graph.ways.get(m[1]);
  const index = Number(m[2]);
  if (!way || index <= 0 || index >= way.points.length - 1) return null;
  if (way.junctions.some(j => j.index === index)) return null; // junctions have canonical names
  return {way, index};
}

export function refPosition(graph, ref) {
  const r = resolveRef(graph, ref);
  if (!r) return null;
  const p = r.junction ?? r.way.points[r.index];
  return {x: p.x, y: p.y, z: p.z};
}

/** Canonical id of the point at (way,index). */
export function refAt(graph, way, index) {
  const j = way.junctions.find(x => x.index === index);
  return j ? j.nodeId : way.id + '#' + index;
}

class Heap {
  constructor() { this.items = []; }
  push(item) {
    const a = this.items; a.push(item);
    let i = a.length - 1;
    while (i > 0) { const p = (i - 1) >> 1; if (a[p].d <= a[i].d) break; [a[p], a[i]] = [a[i], a[p]]; i = p; }
  }
  pop() {
    const a = this.items, top = a[0], last = a.pop();
    if (a.length) {
      a[0] = last; let i = 0;
      for (;;) {
        const l = 2 * i + 1, r = l + 1; let m = i;
        if (l < a.length && a[l].d < a[m].d) m = l;
        if (r < a.length && a[r].d < a[m].d) m = r;
        if (m === i) break; [a[m], a[i]] = [a[i], a[m]]; i = m;
      }
    }
    return top;
  }
  get size() { return this.items.length; }
}

/**
 * Dijkstra from a junction or fine node to a junction target.
 * Returns {steps:[{w,a,b}], length} or null when unreachable. Steps traverse way w from
 * index a to index b; consecutive steps share their junction point.
 */
export function planPath(graph, fromRef, targetId) {
  if (!graph.nodes.has(targetId)) return null;
  const from = resolveRef(graph, fromRef);
  if (!from) return null;
  if (from.junction && from.junction.id === targetId) return {steps: [], length: 0};
  const dist = new Map(), prev = new Map(), heap = new Heap();
  if (from.junction) {
    dist.set(from.junction.id, 0); heap.push({id: from.junction.id, d: 0});
  } else {
    const {way, index} = from;
    const before = [...way.junctions].reverse().find(j => j.index < index);
    const after = way.junctions.find(j => j.index > index);
    for (const j of [before, after]) {
      if (!j) continue;
      const d = Math.abs(way.cum[j.index] - way.cum[index]);
      if (d < (dist.get(j.nodeId) ?? Infinity)) {
        dist.set(j.nodeId, d); prev.set(j.nodeId, {from: null, step: {w: way.id, a: index, b: j.index}});
        heap.push({id: j.nodeId, d});
      }
    }
  }
  const done = new Set();
  while (heap.size) {
    const {id, d} = heap.pop();
    if (done.has(id)) continue;
    done.add(id);
    if (id === targetId) break;
    for (const e of graph.adjacency.get(id)) {
      const nd = d + e.length;
      if (nd < (dist.get(e.to) ?? Infinity) - 1e-12) {
        dist.set(e.to, nd); prev.set(e.to, {from: id, step: {w: e.w, a: e.a, b: e.b}});
        heap.push({id: e.to, d: nd});
      }
    }
  }
  if (!dist.has(targetId)) return null;
  const steps = [];
  let cur = targetId;
  while (prev.has(cur)) {
    const p = prev.get(cur);
    steps.push(p.step);
    if (p.from === null) break;
    cur = p.from;
  }
  steps.reverse();
  return {steps, length: dist.get(targetId)};
}

/**
 * Expand steps to points (with y) plus the junction marks passed, in order.
 * `start` (optional) is an exact current position prepended for a mid-segment redirect.
 */
export function expandSteps(graph, steps, start = null) {
  const points = [], marks = [], locs = [];
  if (start) { points.push({x: start.x, y: start.y, z: start.z}); locs.push(null); }
  for (const step of steps) {
    const way = graph.ways.get(step.w);
    if (!way) throw navError('NAV_GRAPH_MISMATCH', {way: step.w});
    const dir = step.b >= step.a ? 1 : -1;
    for (let i = step.a; dir > 0 ? i <= step.b : i >= step.b; i += dir) {
      if (i < 0 || i >= way.points.length) throw navError('NAV_GRAPH_MISMATCH', {way: step.w, i});
      const p = way.points[i];
      const last = points[points.length - 1];
      if (last && Math.abs(last.x - p.x) < EPS && Math.abs(last.z - p.z) < EPS) {
        // shared junction / duplicated start point: keep the graph location of the point
        if (locs[locs.length - 1] === null) locs[locs.length - 1] = {w: way.id, i};
      } else {
        points.push(p);
        locs.push({w: way.id, i});
      }
      const j = way.junctions.find(x => x.index === i);
      if (j && marks[marks.length - 1]?.nodeId !== j.nodeId) marks.push({i: points.length - 1, nodeId: j.nodeId});
    }
  }
  if (points.length > 1 && hdist(points[0], points[1]) > MAX_SPACING + 1e-6) throw navError('NAV_START_NOT_ON_PATH');
  const cum = [0];
  for (let i = 1; i < points.length; i++) cum.push(cum[i - 1] + hdist(points[i - 1], points[i]));
  return {points, marks, locs, cum, length: cum[cum.length - 1] ?? 0};
}

/** Ref of the last point of the expanded steps. */
export function endRef(graph, steps) {
  const last = steps[steps.length - 1];
  return refAt(graph, graph.ways.get(last.w), last.b);
}

export function pointAtDistance(path, d) {
  const {points, cum} = path;
  if (points.length === 1 || d <= 0) return {...points[0]};
  const total = cum[cum.length - 1];
  if (d >= total) return {...points[points.length - 1]};
  let lo = 0, hi = cum.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= d) lo = mid; else hi = mid; }
  const a = points[lo], b = points[hi], seg = cum[hi] - cum[lo], t = seg > 0 ? (d - cum[lo]) / seg : 0;
  return {x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t};
}

export function indexAtDistance(path, d) {
  const {cum} = path;
  let lo = 0, hi = cum.length - 1;
  if (d >= cum[hi]) return hi;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= d + 1e-9) lo = mid; else hi = mid; }
  return lo;
}

/** Ramer–Douglas–Peucker in 3D, keeping junction marks; projection only. */
export function simplifyForClient(path, tolerance = 0.05) {
  const {points, marks} = path;
  if (points.length <= 2) return points.map(roundPoint);
  const keep = new Uint8Array(points.length);
  keep[0] = keep[points.length - 1] = 1;
  for (const m of marks) keep[m.i] = 1;
  const anchors = [];
  for (let i = 0; i < points.length; i++) if (keep[i]) anchors.push(i);
  for (let k = 0; k + 1 < anchors.length; k++) {
    const stack = [[anchors[k], anchors[k + 1]]];
    while (stack.length) {
      const [s, e] = stack.pop();
      let best = -1, bestD = tolerance;
      for (let i = s + 1; i < e; i++) {
        const d = distToSegment3(points[i], points[s], points[e]);
        if (d > bestD) { bestD = d; best = i; }
      }
      if (best >= 0) { keep[best] = 1; stack.push([s, best], [best, e]); }
    }
  }
  const out = [];
  for (let i = 0; i < points.length; i++) if (keep[i]) out.push(roundPoint(points[i]));
  return out;
}

function distToSegment3(p, a, b) {
  const abx = b.x - a.x, aby = b.y - a.y, abz = b.z - a.z;
  const len2 = abx * abx + aby * aby + abz * abz;
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * abx + (p.y - a.y) * aby + (p.z - a.z) * abz) / len2)) : 0;
  return Math.hypot(p.x - a.x - t * abx, p.y - a.y - t * aby, p.z - a.z - t * abz);
}

export function roundPoint(p) {
  return {x: round(p.x), y: round(p.y), z: round(p.z)};
}

let cached = null;
export function navGraph() {
  cached ??= buildNavGraph();
  return cached;
}
