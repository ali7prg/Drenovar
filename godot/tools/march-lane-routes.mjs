// Build 1021: the server's own city routes for the march-lane checks
// (godot/project/tests/march_lanes/owner_city_routes.json, used by qa_march_lanes.gd).
// Input: a city dumped by dump_owner_city.gd (state, the client's wall as a march sends
// it, the creature targets). Output: marchRoute() of the v92 server with the reviewed
// route-approach-v2 patch, from the home square to each creature and to ring targets.
//   cd godot/project && godot --headless --path . -s ../tools/dump_owner_city.gd -- /tmp/city.json
//   node godot/tools/march-lane-routes.mjs /tmp/city.json godot/project/tests/march_lanes/owner_city_routes.json \
//     <path to drenovar-server>/DRENOVAR-Server-v92/gameplay37/server/navigation.mjs
// Node 24. Read-only use of the private server sources; nothing is sent anywhere.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const [input, output, navigation] = process.argv.slice(2);
const {marchRoute, home, routeUsesFerry, distance} = await import(pathToFileURL(navigation).href);
const dump = JSON.parse(fs.readFileSync(input, 'utf8'));
const city = dump.state.city;
const routes = [];
// The creatures of the city, and a ring of other targets around the walls (east bank too).
const targets = [...dump.targets];
for (const [x, z] of [[-44, -44], [44, -40], [40, 44], [-46, 30], [10, -50], [-50, 0], [52, 10]]) targets.push({id: `t${x}_${z}`, x, z});
for (const t of targets) {
  try {
    const path = marchRoute(home, {x: t.x, z: t.z}, city, dump.wall);
    routes.push({target: t.id, to: {x: t.x, z: t.z}, path, ferry: routeUsesFerry(path), length: distance(path)});
  } catch (e) { routes.push({target: t.id, to: {x: t.x, z: t.z}, error: String(e.message ?? e)}); }
}
fs.writeFileSync(output, JSON.stringify({source: 'DRENOVAR-Server-v92 gameplay37/server/navigation.mjs marchRoute (route-approach-v2 applied), Node 24', home, wall: dump.wall, state: dump.state, routes}));
console.log(routes.map(r => `${r.target}: ${r.error ?? (r.path.length + ' pts, ' + r.length.toFixed(1) + ' m, ferry=' + r.ferry)}`).join('\n'));
