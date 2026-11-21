extends RefCounted
## Runtime view of data/forest_rescue/world/world-atlas.json (copy of the delivery atlas
## `lost_forest_atlas_v1`). Game XZ = atlas XZ, +Y up, north = -Z.

const ATLAS_PATH := "res://data/forest_rescue/world/world-atlas.json"
const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")

const BRIDGE_CENTER := Vector3(90.48200135039062, 1.1, 20.0)
const BRIDGE_LENGTH := 27.0
const BRIDGE_WIDTH := 4.0
const BRIDGE_DECK_Y := 1.1
const ARENA_RADIUS := 15.0
const ARENA_CLEAR_RADIUS := 17.0
const GLADE_RADIUS := 7.0
const GLADE_BLEND := 2.0
const HOME_RECEPTION := Vector2(-7.0, -51.0)
const WATER_LEVEL := -1.35

var raw: Dictionary = {}
var atlas_id := ""
var sites: Array = []            # [{id, name, act, zone, center: Vector3, radius, blend, offsets{}, variant}]
var site_by_id: Dictionary = {}
var routes: Array = []           # [{id, from, to, width, clear, points: PackedVector3Array (x,targetRoadY,z), base: PackedFloat32Array}]
var route_by_id: Dictionary = {}
var zones: Array = []            # [{id, name, center: Vector2, density, mix: Array}]
var reserve_masks: Array = []
var river_z := PackedFloat32Array()
var river_center := PackedFloat32Array()
var river_west := PackedFloat32Array()
var river_east := PackedFloat32Array()
var arena_center := Vector3(75.0, 6.545627597111355, -86.0)
var horse_origin := Vector3(-8.0, 6.783492739619742, -55.0)
var bridge: Dictionary = {}
var fog_spec: Dictionary = {}
var streaming: Dictionary = {}
var entrance_corridor := {"from": Vector2(-8, -55), "to": Vector2(-12, -60), "radius": 3.0, "transitionMs": 1200}
var _segment_grid: Dictionary = {}   # Vector2i -> PackedInt32Array of encoded (route<<16 | segment)
var _server_grid: Dictionary = {}    # same over the authoritative (server) route samples
const SEGMENT_CELL := 8.0

## Visual trails (art/01, art/07): every route is drawn — and kept clear — as a narrow winding
## dirt trail that meanders ≤ MEANDER_AMPLITUDE m around the authoritative route (zero at both
## ends, on the bridge deck ± MEANDER_TAPER and inside the base). `points` are the visual samples
## (terrain, masks, layout, path ribbon), `server_points` the atlas samples = the server's ways.
## visual_of() maps a point of a server move path onto the drawn trail, so actors walk the trail;
## the fog keeps following the server path (reveal radius 10 m ≫ the meander).
const MEANDER_AMPLITUDE := 3.2
const MEANDER_TAPER := 7.0
const MEANDER_WAVES := [[24.0, 0.62], [9.5, 0.26], [43.0, 0.36]]   # [wavelength m, weight]
## Decorative trails (visual only, no server way): the art/01 network linking the base edge,
## glades and landmarks. Polylines of control points (x, z), densified to ≤ 0.5 m and meandered.
const DECOR_TRAILS := {
	"lf_trail_south_gate": [Vector2(6, 56.5), Vector2(10, 66), Vector2(14, 76), Vector2(20, 87)],
	"lf_trail_west_gate": [Vector2(-56.5, 10), Vector2(-66, 7), Vector2(-76, 3), Vector2(-86, 0)],
	"lf_trail_southwest_gate": [Vector2(-38, 56.5), Vector2(-46, 62), Vector2(-54, 67), Vector2(-62, 70)],
	"lf_trail_northwest_gate": [Vector2(-56.5, -26), Vector2(-66, -28), Vector2(-75, -30), Vector2(-84, -32)],
	"lf_trail_standing_stones": [Vector2(-43, -67), Vector2(-48, -73), Vector2(-52, -77)],
	"lf_trail_quarry": [Vector2(-25, 86), Vector2(-28, 93), Vector2(-31, 98)],
	"lf_trail_hunter_shelter": [Vector2(97, -18), Vector2(98, -22)],
	"lf_trail_watchpost": [Vector2(-81, 35), Vector2(-78, 41), Vector2(-76, 44)],
}
const DECOR_CLEAR := 2.2


static func load_default() -> RefCounted:
	var atlas = load("res://src/forest_rescue/world/forest_atlas.gd").new()
	if not atlas.load_from(ATLAS_PATH):
		return null
	return atlas


func load_from(path: String) -> bool:
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		var resource: Variant = load(path) if ResourceLoader.exists(path) else null
		if resource is JSON:
			raw = resource.data
	else:
		var parsed: Variant = JSON.parse_string(text)
		if parsed is Dictionary:
			raw = parsed
	if raw.is_empty():
		push_error("ForestAtlas: cannot read " + path)
		return false
	atlas_id = String(raw.get("id", ""))
	for site in raw.get("sites", []):
		var center := Vector3(float(site.center.x), float(site.center.y), float(site.center.z))
		var entry := {"id": site.id, "name": site.get("name", ""), "act": int(site.get("act", 0)),
			"zone": site.get("zoneId", ""), "center": center, "radius": float(site.get("clearingRadius", GLADE_RADIUS)),
			"blend": float(site.get("padBlend", GLADE_BLEND)), "variant": site.get("variant", "A"),
			"cage": _offset(site.get("cageOffset", {"x": 0, "z": -2})),
			"guardian": _offset(site.get("guardianOffset", {"x": 0, "z": 3})),
			"artifact": _offset(site.get("artifactOffset", {"x": 3.5, "z": -1})),
			"approach": _offset(site.get("escapeApproachOffset", {"x": 0, "z": 7.5}))}
		sites.append(entry)
		site_by_id[entry.id] = entry
	for landmark in raw.get("landmarks", []):
		match String(landmark.get("id", "")):
			"lf_horse_origin":
				horse_origin = Vector3(float(landmark.center.x), float(landmark.center.y), float(landmark.center.z))
			"lf_bridge_crossing":
				bridge = landmark
			"lf_boss_arena":
				arena_center = Vector3(float(landmark.center.x), float(landmark.center.y), float(landmark.center.z))
	for route in raw.get("routes", []):
		var points := PackedVector3Array()
		var base := PackedFloat32Array()
		for sample in route.get("samples", []):
			points.append(Vector3(float(sample.x), float(sample.targetRoadY), float(sample.z)))
			base.append(float(sample.y))
		var bridge_route := String(route.get("traversal", "")).contains("bridge")
		var entry := {"id": route.id, "from": route.get("from", ""), "to": route.get("to", ""),
			"width": float(route.get("width", 2.8)), "clear": float(route.get("clearVegetationRadius", 3.8)),
			"server_points": points, "points": meander(String(route.id), points, bridge_route), "base": base,
			"bridge": bridge_route, "decor": false}
		routes.append(entry)
		route_by_id[entry.id] = entry
	for id in DECOR_TRAILS:
		var controls: Array = DECOR_TRAILS[id]
		var dense := PackedVector3Array()
		for k in range(controls.size() - 1):
			var a: Vector2 = controls[k]
			var b: Vector2 = controls[k + 1]
			var steps := maxi(1, ceili(a.distance_to(b) / 0.5))
			for i in steps:
				var q := a.lerp(b, float(i) / steps)
				dense.append(Vector3(q.x, NAN, q.y))
		var last: Vector2 = controls[-1]
		dense.append(Vector3(last.x, NAN, last.y))
		var decor := {"id": id, "from": "", "to": "", "width": 1.8, "clear": DECOR_CLEAR,
			"server_points": PackedVector3Array(), "points": meander(id, dense, false), "base": PackedFloat32Array(),
			"bridge": false, "decor": true}
		routes.append(decor)
		route_by_id[id] = decor
	for zone in raw.get("zones", []):
		zones.append({"id": zone.id, "name": zone.get("name", ""), "center": Vector2(float(zone.center.x), float(zone.center.z)),
			"density": int(zone.get("ambientTreeCountPerChunk", 64)), "mix": zone.get("treeMix", [])})
	reserve_masks = raw.get("reserveMasks", [])
	var river: Dictionary = raw.get("river", {})
	for sample in river.get("samples", []):
		river_z.append(float(sample.z))
		river_center.append(float(sample.center))
		river_west.append(float(sample.wetWest))
		river_east.append(float(sample.wetEast))
	fog_spec = raw.get("fog", {})
	var corridor: Dictionary = fog_spec.get("entranceCorridor", {})
	if not corridor.is_empty():
		entrance_corridor = {"from": Vector2(float(corridor.from.x), float(corridor.from.z)),
			"to": Vector2(float(corridor.to.x), float(corridor.to.z)), "radius": float(corridor.get("radius", 3)),
			"transitionMs": int(corridor.get("transitionMs", 1200))}
	streaming = raw.get("streaming", {})
	_build_segment_grid()
	return true


func _offset(value: Dictionary) -> Vector2:
	return Vector2(float(value.get("x", 0.0)), float(value.get("z", 0.0)))


## Analytic river centre used by the original terrain (landscape.gd sample_city).
static func river_center_analytic(z: float) -> float:
	return z + 66.0 + 8.0 * sin(z * 0.068) + 3.5 * cos(z * 0.127 + 0.3) + 9.0 * exp(-pow((z + 25.0) / 15.0, 2.0))


## {center, west, east} of the wet banks at z (atlas samples, analytic outside ±112).
func river_at(z: float) -> Vector3:
	if river_z.size() < 2 or z < river_z[0] or z > river_z[river_z.size() - 1]:
		var c := river_center_analytic(z)
		var half := 4.3 + 0.65 * sin(z * 0.093 + 1.4) + 0.3
		return Vector3(c, c - half, c + half)
	var t := (z - river_z[0]) / (river_z[1] - river_z[0])
	var i := clampi(floori(t), 0, river_z.size() - 2)
	var f := clampf(t - i, 0.0, 1.0)
	return Vector3(lerpf(river_center[i], river_center[i + 1], f), lerpf(river_west[i], river_west[i + 1], f),
		lerpf(river_east[i], river_east[i + 1], f))


## Signed distance (m) from the wet bank edge: < 0 inside the wet channel.
func river_bank_distance(x: float, z: float) -> float:
	var r := river_at(z)
	if x < r.y:
		return r.y - x
	if x > r.z:
		return x - r.z
	return -minf(x - r.y, r.z - x)


## Lateral meander of a route polyline (see MEANDER_*): deterministic per route id.
func meander(id: String, points: PackedVector3Array, bridge_route: bool) -> PackedVector3Array:
	var n := points.size()
	if n < 3:
		return points.duplicate()
	var along := PackedFloat32Array()
	along.resize(n)
	for i in range(1, n):
		along[i] = along[i - 1] + Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length()
	var total := along[n - 1]
	var deck := bridge_deck_rect().grow(0.6)
	var deck_along: Array = []
	if bridge_route:
		for i in n:
			if deck.has_point(Vector2(points[i].x, points[i].z)):
				deck_along.append(along[i])
	var seed := absi(hash(id))
	var weight_sum := 0.0
	for wave in MEANDER_WAVES:
		weight_sum += float(wave[1])
	var out := points.duplicate()
	for i in n:
		var s := along[i]
		var w := smoothstep(0.0, MEANDER_TAPER, s) * smoothstep(0.0, MEANDER_TAPER, total - s)
		for value: float in deck_along:
			w *= smoothstep(1.0, 1.0 + MEANDER_TAPER, absf(s - value))
		var core := maxf(absf(points[i].x), absf(points[i].z))
		w *= smoothstep(56.0, 62.0, core)
		if w <= 0.0:
			continue
		var offset := 0.0
		for k in MEANDER_WAVES.size():
			var wave: Array = MEANDER_WAVES[k]
			var phase := float((seed >> (k * 5)) % 628) / 100.0
			offset += float(wave[1]) * sin(TAU * s / float(wave[0]) + phase)
		offset *= MEANDER_AMPLITUDE * w / weight_sum
		var a := points[maxi(i - 6, 0)]
		var b := points[mini(i + 6, n - 1)]
		var tangent := Vector2(b.x - a.x, b.z - a.z).normalized()
		var normal := Vector2(-tangent.y, tangent.x)
		out[i] = Vector3(points[i].x + normal.x * offset, points[i].y, points[i].z + normal.y * offset)
	return out


func _build_segment_grid() -> void:
	_segment_grid.clear()
	_server_grid.clear()
	for route_index in routes.size():
		_grid_route(_segment_grid, route_index, routes[route_index].points)
		_grid_route(_server_grid, route_index, routes[route_index].server_points)


func _grid_route(grid: Dictionary, route_index: int, points: PackedVector3Array) -> void:
	for i in range(points.size() - 1):
		var a := Vector2(points[i].x, points[i].z)
		var b := Vector2(points[i + 1].x, points[i + 1].z)
		var reach := 12.0
		for gz in range(floori((minf(a.y, b.y) - reach) / SEGMENT_CELL), floori((maxf(a.y, b.y) + reach) / SEGMENT_CELL) + 1):
			for gx in range(floori((minf(a.x, b.x) - reach) / SEGMENT_CELL), floori((maxf(a.x, b.x) + reach) / SEGMENT_CELL) + 1):
				var key := Vector2i(gx, gz)
				if not grid.has(key):
					grid[key] = PackedInt32Array()
				grid[key].append((route_index << 16) | i)


## The drawn (meandered) trail point for a point of a SERVER move path: a point on a route's
## authoritative polyline (≤ 0.35 m) maps to the same sample interval of the visual trail;
## anything else (glade spokes, home spur) is returned unchanged.
func visual_of(p: Vector3) -> Vector3:
	var hit := _nearest_in(_server_grid, p.x, p.z, true, true)
	if hit.is_empty() or float(hit.distance) > 0.35:
		return p
	var route: Dictionary = routes[hit.route]
	var visual: PackedVector3Array = route.points
	var a := visual[hit.segment]
	var b := visual[hit.segment + 1]
	var q := a.lerp(b, float(hit.t))
	return Vector3(q.x, p.y, q.z)


## A server path (Array of {x,y,z} / Vector3) as the drawn trail: densified (≤ 0.8 m) and mapped.
func visual_path(path: Array) -> Array:
	var out: Array = []
	var previous := Vector3.INF
	for entry in path:
		var p := _point(entry)
		if previous != Vector3.INF:
			var steps := maxi(1, ceili(Vector2(p.x - previous.x, p.z - previous.z).length() / 0.8))
			for i in range(1, steps):
				out.append(visual_of(previous.lerp(p, float(i) / steps)))
		out.append(visual_of(p))
		previous = p
	return out


static func _point(value: Variant) -> Vector3:
	if value is Vector3:
		return value
	if value is Dictionary:
		return Vector3(float(value.get("x", 0)), float(value.get("y", 0)), float(value.get("z", 0)))
	return Vector3.ZERO


## Nearest route point within 12 m: {distance, route, segment, t} or {} (visual trails, incl. the
## decorative ones unless include_decor is false).
func nearest_route(x: float, z: float, include_decor := true) -> Dictionary:
	return _nearest_in(_segment_grid, x, z, include_decor, false)


func _nearest_in(grid: Dictionary, x: float, z: float, include_decor: bool, server: bool) -> Dictionary:
	var key := Vector2i(floori(x / SEGMENT_CELL), floori(z / SEGMENT_CELL))
	var best := {}
	var best_distance := INF
	var p := Vector2(x, z)
	for code in grid.get(key, PackedInt32Array()):
		var route_index: int = code >> 16
		var i: int = code & 0xffff
		if not include_decor and routes[route_index].decor:
			continue
		var points: PackedVector3Array = routes[route_index].server_points if server else routes[route_index].points
		var a := Vector2(points[i].x, points[i].z)
		var d := Vector2(points[i + 1].x, points[i + 1].z) - a
		var length_squared := d.length_squared()
		var t := 0.0 if length_squared == 0.0 else clampf((p - a).dot(d) / length_squared, 0.0, 1.0)
		var distance := p.distance_to(a + d * t)
		if distance < best_distance:
			best_distance = distance
			best = {"distance": distance, "route": route_index, "segment": i, "t": t}
	return best


func route_points_world(route_id: String) -> PackedVector3Array:
	var route: Dictionary = route_by_id.get(route_id, {})
	return route.get("points", PackedVector3Array())


## Soft biome weights: softmin over distances to the 8 authored centres (band ≈ 10 m).
func biome_weights(x: float, z: float, softness := 3.2) -> PackedFloat32Array:
	var weights := PackedFloat32Array()
	weights.resize(zones.size())
	var nearest := INF
	var distances := PackedFloat32Array()
	distances.resize(zones.size())
	for i in zones.size():
		distances[i] = Vector2(x, z).distance_to(zones[i].center)
		nearest = minf(nearest, distances[i])
	var total := 0.0
	for i in zones.size():
		weights[i] = exp(-(distances[i] - nearest) / softness)
		total += weights[i]
	for i in zones.size():
		weights[i] /= total
	return weights


func nearest_biome(x: float, z: float) -> int:
	var best := 0
	var best_distance := INF
	for i in zones.size():
		var d: float = Vector2(x, z).distance_squared_to(zones[i].center)
		if d < best_distance:
			best_distance = d
			best = i
	return best


func bridge_deck_rect() -> Rect2:
	return Rect2(BRIDGE_CENTER.x - BRIDGE_LENGTH * 0.5, BRIDGE_CENTER.z - BRIDGE_WIDTH * 0.5, BRIDGE_LENGTH, BRIDGE_WIDTH)


## Static vegetation exclusion masks (world-layout.mjs format + "kind").
## Player-dependent masks (buildings, plots, sites) are added at runtime by ForestWorld.
func static_masks() -> Array:
	var result: Array = [{"type": "box", "minX": -56.0, "maxX": 56.0, "minZ": -56.0, "maxZ": 56.0, "kind": "core"}]
	for mask in reserve_masks:
		if ForestMasks.valid_mask(mask):
			var copy: Dictionary = mask.duplicate()
			copy.kind = "reserve"
			result.append(copy)
	for site in sites:
		result.append({"type": "circle", "x": site.center.x, "z": site.center.z, "radius": site.radius, "kind": "glade", "id": site.id})
	result.append({"type": "circle", "x": arena_center.x, "z": arena_center.z, "radius": ARENA_CLEAR_RADIUS, "kind": "arena"})
	var deck := bridge_deck_rect()
	result.append({"type": "capsule", "a": {"x": deck.position.x - 3.0, "z": BRIDGE_CENTER.z},
		"b": {"x": deck.end.x + 3.0, "z": BRIDGE_CENTER.z}, "radius": 3.6, "kind": "bridge"})
	for route in routes:
		var points: PackedVector3Array = route.points
		for i in range(points.size() - 1):
			result.append({"type": "capsule", "a": {"x": points[i].x, "z": points[i].z},
				"b": {"x": points[i + 1].x, "z": points[i + 1].z}, "radius": route.clear, "kind": "route", "id": route.id})
	return result
