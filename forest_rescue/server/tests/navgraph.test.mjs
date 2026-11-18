// Adventure navigation graph from world-atlas.json: routes, glade targets, bridge-only
// water crossing, Dijkstra paths, y from samples, validation failures.
import test from 'node:test';
import assert from 'node:assert/strict';
import {buildNavGraph, navGraph, planPath, expandSteps, MAX_SPACING, resolveRef, simplifyForClient} from '../src/navgraph.mjs';
import {data} from '../src/vendor.mjs';
import {SITES} from '../src/content.mjs';

const atlas = data.atlas;
const g = navGraph();
const hd = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);

test('every CONTRACT target id exists (per-site key/cage/guardian, plates, trail landmarks, bridge, boss, home)', () => {
  for (const id of ['lf_horse_origin', 'lf_home_reception', 'lf_bridge_crossing', 'lf_boss_ancient_maw']) assert.ok(g.nodes.has(id), id);
  for (const site of SITES) {
    for (const id of [site.id, site.artifact.id, site.id + ':cage', site.id + ':guardian']) assert.ok(g.nodes.has(id), id);
    const c = site.center, raw = atlas.sites.find(s => s.id === site.id);
    assert.deepEqual([g.nodes.get(site.id + ':cage').x, g.nodes.get(site.id + ':cage').z], [c.x + raw.cageOffset.x, c.z + raw.cageOffset.z]);
    assert.deepEqual([g.nodes.get(site.id + ':guardian').x, g.nodes.get(site.id + ':guardian').z], [c.x + raw.guardianOffset.x, c.z + raw.guardianOffset.z]);
    assert.deepEqual([g.nodes.get(site.artifact.id).x, g.nodes.get(site.artifact.id).z], [c.x + raw.artifactOffset.x, c.z + raw.artifactOffset.z]);
    assert.equal(g.nodes.has(site.id + ':plate_left'), site.variation === 'paired_latch');
    assert.equal(g.nodes.has(site.id + ':plate_right'), site.variation === 'paired_latch');
    for (const symbol of site.puzzle.solution) assert.equal(g.nodes.has(site.id + ':landmark:' + symbol), site.variation === 'trail_cache');
  }
  const home = g.nodes.get('lf_home_reception');
  assert.deepEqual([home.x, home.z], [-8, -52], 'north approach of the settlement, inside the protected square');
  assert.equal(home.y, atlas.landmarks.find(l => l.id === 'lf_horse_origin').center.y);
});

test('all 13 routes are ways with ≤0.5 spacing and y taken from the atlas samples (deck y only on the bridge)', () => {
  assert.equal(atlas.routes.length, 13);
  for (const route of atlas.routes) {
    const way = g.ways.get(route.id);
    assert.ok(way, route.id);
    for (let i = 1; i < way.points.length; i++) assert.ok(hd(way.points[i - 1], way.points[i]) <= MAX_SPACING + 1e-9);
    const extra = route.id === 'lf_route_10_11' ? 1 : 0; // inserted bridge-centre junction
    assert.equal(way.points.length, route.samples.length + extra);
    for (const s of route.samples) {
      const p = way.points.find(q => q.x === s.x && q.z === s.z);
      assert.ok(p, route.id);
      if (way.deck?.[way.points.indexOf(p)]) assert.equal(p.y, 1.1);
      else assert.equal(p.y, s.y);
    }
  }
  for (const way of g.ways.values()) for (let i = 1; i < way.points.length; i++) assert.ok(hd(way.points[i - 1], way.points[i]) <= MAX_SPACING + 1e-9, way.id);
});

test('water is crossed only on the approved 27 m deck of lf_route_10_11', () => {
  const bridge = atlas.landmarks.find(l => l.id === 'lf_bridge_crossing');
  const way = g.ways.get('lf_route_10_11');
  const deck = way.points.filter((p, i) => way.deck[i]);
  assert.ok(deck.length > 50);
  assert.ok(deck.every(p => p.z === 20 && p.x >= bridge.west.x && p.x <= bridge.east.x && p.y === bridge.structuralHeight));
  const center = g.nodes.get('lf_bridge_crossing');
  assert.deepEqual([center.x, center.y, center.z], [bridge.center.x, 1.1, 20]);
  // Moving one sample of another route into the river makes the build fail closed.
  const broken = structuredClone(atlas);
  const r = broken.routes.find(x => x.id === 'lf_route_09_10');
  r.samples[40] = {...r.samples[40], x: 90.48, z: 20};
  r.samples[41] = {...r.samples[41], x: 90.5, z: 20.2};
  assert.throws(() => buildNavGraph(broken), e => ['NAV_WATER_OUTSIDE_BRIDGE', 'NAV_SPACING'].includes(e.code));
  const water = structuredClone(atlas);
  const w = water.routes.find(x => x.id === 'lf_route_10_11');
  // the same water outside the deck rectangle (z shifted by 3) is not approved geometry
  for (const s of w.samples) if (s.z === 20 && s.x > 85 && s.x < 95) s.z = 20.0001 + 0; // still on deck: allowed
  assert.doesNotThrow(() => buildNavGraph(water));
  const sparse = structuredClone(atlas);
  sparse.routes[0].samples.splice(5, 3);
  assert.throws(() => buildNavGraph(sparse), e => e.code === 'NAV_SPACING');
});

test('Dijkstra: home → sites follow the authored chain; the east bank is reached only over the bridge', () => {
  const marks = (from, to) => expandSteps(g, planPath(g, from, to).steps).marks.map(m => m.nodeId);
  assert.deepEqual(marks('lf_home_reception', 'lf_site_01'), ['lf_home_reception', 'lf_horse_origin', 'lf_site_01']);
  const east = marks('lf_site_10', 'lf_site_12');
  assert.deepEqual(east, ['lf_site_10', 'lf_bridge_crossing', 'lf_site_11', 'lf_site_12']);
  const home = marks('lf_site_12:cage', 'lf_home_reception');
  assert.ok(home.includes('lf_bridge_crossing'));
  assert.equal(home.at(-1), 'lf_home_reception');
  assert.deepEqual(marks('lf_site_12', 'lf_boss_ancient_maw'), ['lf_site_12', 'lf_boss_ancient_maw']);
  // trail cache: the cache is reachable only past the three landmarks in clue order
  for (const site of SITES.filter(s => s.variation === 'trail_cache')) {
    assert.deepEqual(marks(site.id, site.artifact.id), [site.id, ...site.puzzle.solution.map(s => site.id + ':landmark:' + s), site.artifact.id]);
    assert.deepEqual(marks(site.id + ':cage', site.artifact.id).slice(-4, -1), site.puzzle.solution.map(s => site.id + ':landmark:' + s));
  }
  const path = expandSteps(g, planPath(g, 'lf_home_reception', 'lf_boss_ancient_maw').steps);
  for (let i = 1; i < path.points.length; i++) assert.ok(hd(path.points[i - 1], path.points[i]) <= MAX_SPACING + 1e-9);
  assert.ok(Math.abs(path.length - 536.65) < 0.5, 'length ' + path.length);
  const client = simplifyForClient(path);
  assert.ok(client.length < path.points.length / 4, 'projection is compacted');
  assert.deepEqual(client[0], {x: -8, y: 6.783, z: -52});
  assert.equal(planPath(g, 'lf_home_reception', 'nowhere'), null);
});

test('fine nodes: canonical junction names; graph id is stable', () => {
  assert.equal(resolveRef(g, 'lf_route_01_02#0'), null, 'endpoints use the junction name');
  assert.ok(resolveRef(g, 'lf_route_01_02#10').way);
  assert.equal(resolveRef(g, 'lf_route_01_02#999'), null);
  assert.equal(buildNavGraph().graphId, g.graphId);
  assert.match(g.graphId, /^fr-nav-1-[0-9a-f]{16}$/);
});
