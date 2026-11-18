extends Node3D
## Landmarks + boss arena dressing. Assets are picked up automatically when the asset agents
## deliver them (re-checked on every city build); nothing is invented here.
##
## Authored spots (atlas coordinates, documented in WORLD_API.md changelog):
##   lf_env_bridge27m        (90.482, 0, 20) exactly, yaw 0 (long axis X, deck top local 1.1)
##   lf_env_quarry_mine      Ломаный известняк, NW of site 03 — preferred (-93, -88)
##   lf_env_ruined_watchpost Пепельная часовня edge — preferred (-80, -73)
##   lf_env_hunter_shelter   Тёмная хвоя, west of route 04→05 — preferred (-101, -15)
##   lf_env_standing_stones  Древняя роща, east of site 12 — preferred (96, -62)
##   lf_env_camp_props       one per glade, just outside the pad at the freest angle
##   arena modules           centred on the arena (75, -86), entrance toward the boss route
## Preferred spots are validated against route clearances, glades, arena, bridge, core and the
## wet river channel; if blocked, a spiral search (≤ 24 m) finds the nearest valid spot.

const LANDMARK_DIR := "res://assets/forest_rescue/landmarks/"
const ARENA_DIR := "res://assets/forest_rescue/arena/"
const PROPS_JSON := "res://assets/forest_rescue/props/site_props.json"

const SPECS := [
	{"id": "lf_env_quarry_mine", "pos": Vector2(-93, -88), "footprint": 8.0, "face": Vector2(-70, -66)},
	{"id": "lf_env_ruined_watchpost", "pos": Vector2(-80, -73), "footprint": 5.5, "face": Vector2(-67, -63)},
	{"id": "lf_env_hunter_shelter", "pos": Vector2(-101, -15), "footprint": 5.0, "face": Vector2(-85, -15)},
	{"id": "lf_env_standing_stones", "pos": Vector2(96, -62), "footprint": 5.5, "face": Vector2(78, -49)},
]
const CAMP := {"id": "lf_env_camp_props", "footprint": 3.2, "distance": 9.6}

var atlas: RefCounted
var placements: Array = []        # [{id, position: Vector3, yaw, footprint, kind}]
var missing: Dictionary = {}
var loaded: Dictionary = {}
var arena_state := "locked"
var arena_root: Node3D
var site_states: Dictionary = {}


## Computes all placements (static, deterministic). height_fn: Callable(x, z) -> float.
func plan(forest_atlas: RefCounted, masks: RefCounted, height_fn: Callable) -> void:
	atlas = forest_atlas
	placements.clear()
	placements.append({"id": "lf_env_bridge27m", "position": Vector3(atlas.BRIDGE_CENTER.x, 0.0, atlas.BRIDGE_CENTER.z),
		"yaw": 0.0, "footprint": 0.0, "kind": "bridge", "pad": false})
	for spec in SPECS:
		var spot := find_spot(spec.pos, float(spec.footprint), masks)
		var face: Vector2 = spec.face - spot
		placements.append({"id": spec.id, "position": Vector3(spot.x, 0.0, spot.y), "yaw": atan2(face.x, face.y),
			"footprint": spec.footprint, "kind": "landmark", "pad": true})
	for site in atlas.sites:
		var center := Vector2(site.center.x, site.center.z)
		var best_angle := 0.0
		var best_score := -INF
		for k in 24:
			var angle := TAU * k / 24.0
			var p := center + Vector2(cos(angle), sin(angle)) * float(CAMP.distance)
			var score := 0.0
			var hit: Dictionary = atlas.nearest_route(p.x, p.y)
			score += minf(hit.get("distance", 12.0), 12.0)
			# keep away from the approach side (+offset) used by the escort
			var approach: Vector2 = site.approach
			score -= 6.0 * maxf(0.0, Vector2(cos(angle), sin(angle)).dot(approach.normalized()))
			if not valid_spot(p, float(CAMP.footprint), masks, true):
				score -= 100.0
			if score > best_score:
				best_score = score
				best_angle = angle
		var spot := center + Vector2(cos(best_angle), sin(best_angle)) * float(CAMP.distance)
		placements.append({"id": CAMP.id, "position": Vector3(spot.x, 0.0, spot.y), "yaw": atan2(center.x - spot.x, center.y - spot.y),
			"footprint": CAMP.footprint, "kind": "camp", "site": site.id, "pad": true})
	for placement in placements:
		var p: Vector3 = placement.position
		if placement.kind != "bridge":
			placement.position.y = height_fn.call(p.x, p.z)


func valid_spot(p: Vector2, footprint: float, masks: RefCounted, camp := false) -> bool:
	if maxf(absf(p.x), absf(p.y)) < 56.0 + footprint or maxf(absf(p.x), absf(p.y)) > 110.0 - footprint * 0.5:
		return false
	if atlas.river_bank_distance(p.x, p.y) < footprint + 2.0:
		return false
	var hit: Dictionary = atlas.nearest_route(p.x, p.y)
	if not hit.is_empty() and hit.distance < footprint + 1.8:
		return false
	for site in atlas.sites:
		var limit: float = site.radius + (0.8 if camp else 2.0) + footprint
		if p.distance_to(Vector2(site.center.x, site.center.z)) < limit:
			return false
	if p.distance_to(Vector2(atlas.arena_center.x, atlas.arena_center.z)) < atlas.ARENA_CLEAR_RADIUS + footprint + 2.0:
		return false
	if atlas.bridge_deck_rect().grow(footprint + 4.0).has_point(p):
		return false
	return true


func find_spot(preferred: Vector2, footprint: float, masks: RefCounted) -> Vector2:
	if valid_spot(preferred, footprint, masks):
		return preferred
	var radius := 1.0
	while radius <= 24.0:
		for k in 24:
			var angle := TAU * k / 24.0
			var p := preferred + Vector2(cos(angle), sin(angle)) * radius
			if valid_spot(p, footprint, masks):
				return p
		radius += 1.0
	return preferred


## Flatten pads for terrain baking: [[Vector2 center, radius, height]].
func pads() -> Array:
	var result: Array = []
	for placement in placements:
		if placement.get("pad", false):
			result.append([Vector2(placement.position.x, placement.position.z), float(placement.footprint), placement.position.y])
	return result


## Instantiates every delivered asset; logs missing ones. Safe to call again (picks up new files).
func populate() -> void:
	for child in get_children():
		child.free()
	missing.clear()
	loaded.clear()
	for placement in placements:
		var path := _find(LANDMARK_DIR, placement.id)
		if path.is_empty():
			path = _find("res://assets/forest_rescue/props/", placement.id)
		if path.is_empty():
			missing[placement.id] = "not delivered (expected %s%s.glb)" % [LANDMARK_DIR, placement.id]
			continue
		var node: Node3D = load(path).instantiate()
		node.name = "%s_%s" % [placement.id, placement.get("site", str(placements.find(placement)))]
		node.position = placement.position
		node.rotation.y = placement.yaw
		add_child(node)
		loaded[placement.id] = path
	_populate_arena()


func _find(directory: String, id: String) -> String:
	for candidate in [directory + id + ".glb", directory + id + ".tscn", directory + id + ".scn"]:
		if ResourceLoader.exists(candidate):
			return candidate
	var dir := DirAccess.open(directory)
	if dir != null:
		for file in dir.get_files():
			if file.begins_with(id) and file.ends_with(".glb"):
				return directory + file
	return ""


func _populate_arena() -> void:
	arena_root = Node3D.new()
	arena_root.name = "BossArena"
	var center: Vector3 = atlas.arena_center
	arena_root.position = Vector3(center.x, center.y - 0.3, center.z)
	add_child(arena_root)
	var whole := _find(ARENA_DIR, "lf_boss_arena")
	if not whole.is_empty():
		var node: Node3D = load(whole).instantiate()
		node.rotation.y = _arena_entrance_yaw()
		arena_root.add_child(node)
		loaded["lf_boss_arena"] = whole
		apply_arena_state(arena_state)
		return
	var dir := DirAccess.open(ARENA_DIR)
	var modules: Array = []
	if dir != null:
		for file in dir.get_files():
			if file.ends_with(".glb"):
				modules.append(ARENA_DIR + file)
	modules.sort()
	if modules.is_empty():
		missing["lf_boss_arena"] = "arena modules not delivered (expected %s*.glb)" % ARENA_DIR
		return
	# Ring layout: cliffs around r≈17 leaving a 50° entrance toward the boss route,
	# fossil cliff opposite the entrance, pillars inside the bowl.
	var entrance := _arena_entrance_yaw()
	var cliffs := modules.filter(func(p): return String(p).get_file().contains("cliff") and not String(p).get_file().contains("fossil"))
	var fossils := modules.filter(func(p): return String(p).get_file().contains("fossil") or String(p).get_file().contains("bone"))
	var pillars := modules.filter(func(p): return String(p).get_file().contains("pillar") or String(p).get_file().contains("rock"))
	var others := modules.filter(func(p): return not (cliffs.has(p) or fossils.has(p) or pillars.has(p)))
	var ring := 10
	for k in ring:
		var angle := entrance + PI / 7.0 + (TAU - 2.0 * PI / 7.0) * k / float(ring - 1)
		var path: String = (fossils[0] if k == ring / 2 and not fossils.is_empty() else (cliffs[k % cliffs.size()] if not cliffs.is_empty() else ""))
		if path.is_empty():
			continue
		var node: Node3D = load(path).instantiate()
		node.position = Vector3(sin(angle), 0.0, cos(angle)) * 17.5
		node.rotation.y = angle + PI
		arena_root.add_child(node)
	for k in pillars.size() * 0 + mini(3, pillars.size()):
		var angle := entrance + PI * (0.55 + 0.45 * k)
		var node: Node3D = load(pillars[k % pillars.size()]).instantiate()
		node.position = Vector3(sin(angle), 0.0, cos(angle)) * 10.5
		arena_root.add_child(node)
	for path in others:
		loaded[String(path).get_file()] = path
	loaded["arena_modules"] = modules
	apply_arena_state(arena_state)


func _arena_entrance_yaw() -> float:
	# Direction from the arena centre toward the boss route's approach (77, -65).
	var c: Vector3 = atlas.arena_center
	return atan2(77.0 - c.x, -65.0 - c.z)


## Visual dressing only. Nodes named state_<locked|available|active|defeated> (any depth) are
## shown for their state; everything else is untouched.
func apply_arena_state(state: String) -> void:
	arena_state = state
	if arena_root == null:
		return
	for node in arena_root.find_children("state_*", "Node3D", true, false):
		(node as Node3D).visible = String(node.name).trim_prefix("state_").begins_with(state)


func apply_site_state(site_id: String, step: int) -> void:
	site_states[site_id] = step
	for node in find_children("*_" + site_id, "Node3D", false, false):
		for part in node.find_children("post_*", "Node3D", true, false):
			(part as Node3D).visible = step >= 5
