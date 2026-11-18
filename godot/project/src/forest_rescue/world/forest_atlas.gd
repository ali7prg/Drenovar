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
const SEGMENT_CELL := 8.0


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
		var entry := {"id": route.id, "from": route.get("from", ""), "to": route.get("to", ""),
			"width": float(route.get("width", 2.8)), "clear": float(route.get("clearVegetationRadius", 3.8)),
			"points": points, "base": base, "bridge": String(route.get("traversal", "")).contains("bridge")}
		routes.append(entry)
		route_by_id[entry.id] = entry
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


func _build_segment_grid() -> void:
	_segment_grid.clear()
	for route_index in routes.size():
		var points: PackedVector3Array = routes[route_index].points
		for i in range(points.size() - 1):
			var a := Vector2(points[i].x, points[i].z)
			var b := Vector2(points[i + 1].x, points[i + 1].z)
			var reach := 12.0
			for gz in range(floori((minf(a.y, b.y) - reach) / SEGMENT_CELL), floori((maxf(a.y, b.y) + reach) / SEGMENT_CELL) + 1):
				for gx in range(floori((minf(a.x, b.x) - reach) / SEGMENT_CELL), floori((maxf(a.x, b.x) + reach) / SEGMENT_CELL) + 1):
					var key := Vector2i(gx, gz)
					if not _segment_grid.has(key):
						_segment_grid[key] = PackedInt32Array()
					_segment_grid[key].append((route_index << 16) | i)


## Nearest route point within 12 m: {distance, route, segment, t, y (targetRoadY), base_y} or {}.
func nearest_route(x: float, z: float) -> Dictionary:
	var key := Vector2i(floori(x / SEGMENT_CELL), floori(z / SEGMENT_CELL))
	var best := {}
	var best_distance := INF
	var p := Vector2(x, z)
	for code in _segment_grid.get(key, PackedInt32Array()):
		var route_index: int = code >> 16
		var i: int = code & 0xffff
		var points: PackedVector3Array = routes[route_index].points
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
