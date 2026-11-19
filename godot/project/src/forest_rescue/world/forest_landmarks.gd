extends Node3D
## Landmarks + boss arena dressing (landmarks v3 / arena modules). Nothing is invented here:
## every visual is a delivered GLB, picked up automatically (re-checked on every city build).
##
## Landmark GLBs: <id>.glb = LOD0 (+ <id>_cloth_LOD0 morph clip lf_banner_wind, + <id>_base
## painted ground patch), <id>_LOD1.glb / <id>_LOD2.glb (same origin). In the world the `_base`
## nodes are OFF (the terrain/paths provide the ground), cloth clips loop, every surface uses the
## painted kit material with k = 0.35 (meta paintedLightMix), LODs switch by the city zoom.
##
## Spots follow the art/01 masterplan as seen from the city camera (screen angle φ around the
## town, CCW from screen-right) and are validated against route clearances, glades, arena,
## bridge, core and the wet river channel (spiral search ≤ 24 m if blocked):
##   lf_env_bridge27m        (90.482, 0, 20) exactly, yaw 0 (long axis X, deck top local 1.1)
##   lf_env_quarry_mine      art/01 SW quarry (φ≈209°): outside glade 08, portal facing it
##   lf_env_ruined_watchpost art/01 arch ruin at the grove edge (φ≈164°), near glade 06
##   lf_env_hunter_shelter   art/01 east bank shelter (φ≈331°), between glades 11 and 12
##   lf_env_standing_stones  art/01 stone row above the town (φ≈85°), between glades 02 and 03
##   lf_env_camp_props       one per glade (tent + fire next to the cage), freest angle
##   arena (assembled)       centred on (75, -86), yaw 5.4° (gap toward the boss route); whole
##                           LOD files by zoom (<=34 / <=85 / beyond), one resident at a time

const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const LANDMARK_DIR := "res://assets/forest_rescue/landmarks/"
const ARENA_DIR := "res://assets/forest_rescue/arena/"
const LIGHT_MIX := 0.35
const ARENA_YAW_DEG := 5.4

const SPECS := [
	{"id": "lf_env_quarry_mine", "site": "lf_site_08", "out": 15.5, "side": 4.0, "footprint": 6.0, "face_site": true},
	{"id": "lf_env_ruined_watchpost", "pos": Vector2(-74, 47), "footprint": 5.0, "face": Vector2(0, 0)},
	{"id": "lf_env_hunter_shelter", "pos": Vector2(97, -27), "footprint": 4.6, "face": Vector2(90, -20)},
	{"id": "lf_env_standing_stones", "pos": Vector2(-56, -82), "footprint": 4.4, "face": Vector2(-40, -60)},
]
const CAMP := {"id": "lf_env_camp_props", "footprint": 3.4, "distance": 10.2}

var atlas: RefCounted
var placements: Array = []        # [{id, position: Vector3, yaw, footprint, kind}]
var missing: Dictionary = {}
var loaded: Dictionary = {}
var arena_state := "locked"
var arena_root: Node3D
var site_states: Dictionary = {}
var items: Array = []             # [{node, lods: [Node3D×3], players: [[AnimationPlayer]×3], center: Vector2, radius, lod}]
var arena_parts: Array = []       # [MeshInstance3D, Mesh LOD0, Mesh LOD1]
var arena_lod := -1
var tris_by_lod := {}             # placement id -> [tris LOD0, LOD1, LOD2]


## Computes all placements (static, deterministic). height_fn: Callable(x, z) -> float.
func plan(forest_atlas: RefCounted, masks: RefCounted, height_fn: Callable) -> void:
	atlas = forest_atlas
	placements.clear()
	placements.append({"id": "lf_env_bridge27m", "position": Vector3(atlas.BRIDGE_CENTER.x, 0.0, atlas.BRIDGE_CENTER.z),
		"yaw": 0.0, "footprint": 0.0, "kind": "bridge", "pad": false})
	for spec in SPECS:
		var preferred: Vector2
		var face: Vector2
		if spec.has("site"):
			var site: Dictionary = atlas.site_by_id[spec.site]
			var c := Vector2(site.center.x, site.center.z)
			var out := c.normalized()
			preferred = c + out * float(spec.out) + Vector2(-out.y, out.x) * float(spec.get("side", 0.0))
			face = c
		else:
			preferred = spec.pos
			face = spec.face
		var spot := find_spot(preferred, float(spec.footprint), masks)
		var dir: Vector2 = face - spot
		placements.append({"id": spec.id, "position": Vector3(spot.x, 0.0, spot.y), "yaw": atan2(dir.x, dir.y),
			"footprint": spec.footprint, "kind": "landmark", "pad": true})
	# art/01: every site has a camp (tarp, fire ring, crates) next to the cage inside its clearing.
	# The camp stands at the clearing edge, as far as possible from the gameplay anchors (cage,
	# guardian, artifact, escort approach) and from the trails, preferring the camera-far side.
	for site in atlas.sites:
		var center := Vector2(site.center.x, site.center.z)
		var anchors: Array = [site.cage, site.guardian, site.artifact, site.approach]
		var best := Vector2.INF
		var best_score := -INF
		for ring in [6.2, 7.4, 8.8]:
			for k in 36:
				var angle := TAU * k / 36.0
				var p: Vector2 = center + Vector2(cos(angle), sin(angle)) * float(ring)
				if not camp_spot_ok(p, float(CAMP.footprint), site):
					continue
				var clearance := INF
				for anchor: Vector2 in anchors:
					clearance = minf(clearance, p.distance_to(center + anchor))
				var hit: Dictionary = atlas.nearest_route(p.x, p.y)
				var trail: float = minf(hit.get("distance", 12.0), 12.0)
				var score: float = minf(clearance, 6.0) * 1.6 + trail - float(ring) * 0.4
				score += 1.5 * Vector2(cos(angle), sin(angle)).dot(Vector2(-0.7071, -0.7071))
				if clearance < 3.6:
					score -= 50.0
				if score > best_score:
					best_score = score
					best = p
		if best == Vector2.INF:
			continue
		placements.append({"id": CAMP.id, "position": Vector3(best.x, 0.0, best.y), "yaw": atan2(center.x - best.x, center.y - best.y),
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
	for placement in placements:
		if placement.kind != "bridge" and Vector2(placement.position.x, placement.position.z).distance_to(p) < float(placement.footprint) + footprint + 1.0:
			return false
	return true


## Camp spot test: inside or at the edge of its own clearing, off trails, other glades, river.
func camp_spot_ok(p: Vector2, footprint: float, own_site: Dictionary) -> bool:
	if maxf(absf(p.x), absf(p.y)) < 56.0 + footprint or maxf(absf(p.x), absf(p.y)) > 110.0 - footprint * 0.5:
		return false
	if atlas.river_bank_distance(p.x, p.y) < footprint + 1.5:
		return false
	var hit: Dictionary = atlas.nearest_route(p.x, p.y)
	if not hit.is_empty() and hit.distance < footprint + 1.6:
		return false
	for site in atlas.sites:
		if site.id != own_site.id and p.distance_to(Vector2(site.center.x, site.center.z)) < site.radius + footprint + 1.0:
			return false
	for placement in placements:
		if placement.kind != "bridge" and Vector2(placement.position.x, placement.position.z).distance_to(p) < float(placement.footprint) + footprint + 1.0:
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


## Centre of the SW quarry pit (art/01): between the mine portal and glade 08 (shared with the
## layout builder). Vector2.INF when the mine has no placement.
func quarry_center() -> Vector2:
	for placement in placements:
		if placement.id == "lf_env_quarry_mine":
			var site: Dictionary = atlas.site_by_id.lf_site_08
			return Vector2(placement.position.x, placement.position.z).lerp(Vector2(site.center.x, site.center.z), 0.45)
	return Vector2.INF


## Flatten pads for terrain baking: [[Vector2 center, radius, height]].
func pads() -> Array:
	var result: Array = []
	for placement in placements:
		if placement.get("pad", false):
			result.append([Vector2(placement.position.x, placement.position.z), float(placement.footprint), placement.position.y])
	return result


## Spots the forest layout keeps free of trunks: [[Vector2 center, radius]].
func clearances() -> Array:
	var result: Array = []
	for placement in placements:
		if placement.kind != "bridge":
			result.append([Vector2(placement.position.x, placement.position.z), float(placement.footprint) + 1.5])
	return result


## Instantiates every delivered asset; logs missing ones. Safe to call again (picks up new files).
func populate() -> void:
	for child in get_children():
		child.free()
	items.clear()
	arena_parts.clear()
	arena_lod = -1
	missing.clear()
	loaded.clear()
	for placement in placements:
		var paths := lod_paths(placement.id)
		if paths[0].is_empty():
			missing[placement.id] = "not delivered (expected %s%s.glb)" % [LANDMARK_DIR, placement.id]
			continue
		var holder := Node3D.new()
		holder.name = "%s_%s" % [placement.id, placement.get("site", str(placements.find(placement)))]
		holder.position = placement.position
		holder.rotation.y = placement.yaw
		add_child(holder)
		var lods: Array = []
		var players: Array = []
		var tris: Array = []
		for lod in 3:
			var path: String = paths[lod] if not paths[lod].is_empty() else paths[maxi(0, lod - 1)]
			var scene: Variant = load(path)
			if not scene is PackedScene:
				missing[placement.id] = "found but not imported yet: " + path
				lods.append(null)
				players.append([])
				tris.append(0)
				continue
			var node: Node3D = scene.instantiate()
			node.name = "LOD%d" % lod
			_prepare(node)
			holder.add_child(node)
			lods.append(node)
			players.append(node.find_children("*", "AnimationPlayer", true, false))
			tris.append(_count_tris(node))
		tris_by_lod[placement.id] = tris
		items.append({"node": holder, "lods": lods, "players": players, "center": Vector2(placement.position.x, placement.position.z),
			"radius": maxf(4.0, float(placement.footprint)) if placement.kind != "bridge" else 17.0, "lod": -1, "id": placement.id,
			"site": placement.get("site", ""), "tris": tris})
		loaded[placement.id] = paths[0]
		_set_lod(items[-1], 1)
	_populate_arena()


## [LOD0, LOD1, LOD2] files of a landmark id ("" when missing).
func lod_paths(id: String) -> Array:
	var result := []
	for suffix in ["", "_LOD1", "_LOD2"]:
		var path: String = LANDMARK_DIR + id + suffix + ".glb"
		result.append(path if ResourceLoader.exists(path) else "")
	return result


func _prepare(node: Node3D) -> void:
	for part in node.find_children("*", "Node3D", true, false):
		if String(part.name).contains("_base"):
			(part as Node3D).visible = false
	ForestKit.paint_scene(node, LIGHT_MIX)
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if String(part.name).contains("_base") else GeometryInstance3D.SHADOW_CASTING_SETTING_ON


static func _visible_tris(node: Node) -> int:
	if node == null or not is_instance_valid(node):
		return 0
	var total := 0
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if part.mesh != null and part.is_visible_in_tree():
			total += ForestKit.mesh_triangles(part.mesh)
	return total


static func _count_tris(node: Node) -> int:
	var total := 0
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null or not part.visible:
			continue
		total += ForestKit.mesh_triangles(part.mesh)
	return total


func _set_lod(item: Dictionary, lod: int) -> void:
	if item.lod == lod:
		return
	item.lod = lod
	for i in 3:
		var node: Node3D = item.lods[i]
		if node == null:
			continue
		var on := i == lod
		node.visible = on
		for player: AnimationPlayer in item.players[i]:
			if on and not player.get_animation_list().is_empty():
				var clip: String = player.get_animation_list()[0]
				player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
				if not player.is_playing():
					player.play(clip)
					player.seek(fposmod(item.center.x * 0.37 + item.center.y * 0.11, 4.5), true)
			elif not on and player.is_playing():
				player.stop()


## LOD by the city zoom and the distance to the camera focus; hidden while under opaque fog.
## visible_fn: Callable(x, z, radius) -> bool (fog-aware). Returns visible triangle estimate.
func update_view(target: Vector3, zoom: float, visible_fn: Callable) -> int:
	var tris := 0
	for item in items:
		var shown: bool = visible_fn.call(item.center.x, item.center.y, item.radius) if visible_fn.is_valid() else true
		item.node.visible = shown
		if not shown:
			continue
		var d: float = item.center.distance_to(Vector2(target.x, target.z))
		var lod := 2
		if zoom <= 50.0 and d <= 30.0:
			lod = 0
		elif zoom <= 96.0 and d <= 64.0:
			lod = 1
		_set_lod(item, lod)
		if d <= zoom * 1.25 + item.radius:      # roughly inside the ortho view
			tris += int(item.tris[lod])
	if arena_root != null:
		var center := Vector2(arena_root.position.x, arena_root.position.z)
		var shown: bool = visible_fn.call(center.x, center.y, 20.0) if visible_fn.is_valid() else true
		arena_root.visible = shown
		if shown:
			var d := center.distance_to(Vector2(target.x, target.z))
			var lod := 0 if zoom <= ARENA_LOD_ZOOM[0] else (1 if zoom <= ARENA_LOD_ZOOM[1] else 2)
			if d > zoom * 1.25 + 40.0:
				lod = 2
			_set_arena_lod(lod)
			arena_visible_fn = visible_fn
			_cull_arena()
			if d <= zoom * 1.25 + 24.0:
				tris += _visible_tris(arena_node)
	return tris


## Arena v2 (art/08 rebuild): three whole files with the same node names,
## lf_boss_arena_assembled{,_lod1,_lod2}.glb (54.8k / 21.2k / 10.1k tris, ~13-14 MB each with
## embedded kit textures). The file for the zoom (LOD0 <= 34, LOD1 <= 85, LOD2 beyond) is
## loaded on a worker thread and swapped in; the previous instance is freed, so only one
## arena file stays resident. Painted kit material like the landmarks.
const ARENA_FILES := ["lf_boss_arena_assembled.glb", "lf_boss_arena_assembled_lod1.glb", "lf_boss_arena_assembled_lod2.glb"]
const ARENA_LOD_ZOOM := [34.0, 85.0]
var arena_node: Node3D
var arena_cull: Array = []        # [[MeshInstance3D, Vector2 xz centre, radius]] of the shown file
var arena_visible_fn := Callable()
var arena_shown_lod := -1
var arena_wanted_lod := -1
var arena_loading := ""
var arena_tris := 0


func _populate_arena() -> void:
	arena_root = Node3D.new()
	arena_root.name = "BossArena"
	var center: Vector3 = atlas.arena_center
	arena_root.position = Vector3(center.x, center.y - 0.3, center.z)
	arena_root.rotation.y = deg_to_rad(ARENA_YAW_DEG)
	add_child(arena_root)
	if not arena_loading.is_empty():
		ResourceLoader.load_threaded_get(arena_loading)   # drain a request of the previous build
	arena_node = null
	arena_shown_lod = -1
	arena_wanted_lod = -1
	arena_loading = ""
	if _arena_path(0).is_empty():
		missing["lf_boss_arena"] = "arena not delivered (expected %s%s)" % [ARENA_DIR, ARENA_FILES[0]]
		return
	loaded["lf_boss_arena"] = _arena_path(0)
	_request_arena_lod(1)


func _arena_path(lod: int) -> String:
	for level in range(lod, -1, -1):
		var path: String = ARENA_DIR + ARENA_FILES[level]
		if ResourceLoader.exists(path):
			return path
	return ""


func _request_arena_lod(lod: int) -> void:
	arena_wanted_lod = lod
	var path := _arena_path(lod)
	if path.is_empty() or (lod == arena_shown_lod and arena_node != null):
		return
	if arena_loading == path:
		return
	if not arena_loading.is_empty():
		# A different file is still on its way: let it land, the poll re-requests the wanted one.
		return
	if ResourceLoader.load_threaded_request(path, "PackedScene") != OK:
		_swap_arena(load(path), lod)
		return
	arena_loading = path


func _process(_delta: float) -> void:
	_poll_arena()


func _poll_arena(blocking := false) -> void:
	if arena_loading.is_empty():
		return
	var status := ResourceLoader.load_threaded_get_status(arena_loading)
	if blocking or status == ResourceLoader.THREAD_LOAD_LOADED:
		var scene: Variant = ResourceLoader.load_threaded_get(arena_loading)
		var lod := ARENA_FILES.find(arena_loading.get_file())
		arena_loading = ""
		_swap_arena(scene, lod)
	elif status == ResourceLoader.THREAD_LOAD_FAILED or status == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
		push_warning("ForestLandmarks: arena LOD failed to load: " + arena_loading)
		arena_loading = ""
	if arena_loading.is_empty() and arena_wanted_lod >= 0 and arena_wanted_lod != arena_shown_lod:
		_request_arena_lod(arena_wanted_lod)


## QA/capture: finish a pending arena load now (a still never shows the previous LOD).
func finish_arena_load() -> void:
	_poll_arena(true)


func _swap_arena(scene: Variant, lod: int) -> void:
	if not scene is PackedScene or arena_root == null:
		return
	var node: Node3D = (scene as PackedScene).instantiate()
	node.name = "LOD%d" % lod
	ForestKit.paint_scene(node, LIGHT_MIX)
	arena_root.add_child(node)
	for player: AnimationPlayer in node.find_children("*", "AnimationPlayer", true, false):
		if not player.get_animation_list().is_empty():
			var clip: String = player.get_animation_list()[0]
			player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
			player.play(clip)
	if arena_node != null and is_instance_valid(arena_node):
		arena_node.free()
	arena_node = node
	arena_shown_lod = lod
	arena_lod = lod
	arena_tris = _count_tris(node)
	# Zero-through-fog: the arena file carries kit trees / rocks on its rim; each part follows
	# the same rule as the kit instances (nothing renders deeper inside unexplored ground than
	# the 3 m blend band, here + the part's own radius), and its painted materials join the fog
	# receivers so the band erodes like the forest around it.
	arena_cull.clear()
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		var box: AABB = part.global_transform * part.get_aabb()
		var c := box.get_center()
		arena_cull.append([part, Vector2(c.x, c.z), maxf(box.size.x, box.size.z) * 0.5])
	var world := get_parent()
	if world != null and world.has_method("_register_fog_receivers"):
		world.call("_register_fog_receivers")
	_cull_arena()
	apply_arena_state(arena_state)


func _cull_arena() -> void:
	if not arena_visible_fn.is_valid():
		return
	for entry in arena_cull:
		var part: MeshInstance3D = entry[0]
		if is_instance_valid(part):
			part.visible = bool(arena_visible_fn.call(entry[1].x, entry[1].y, float(entry[2])))


func _set_arena_lod(lod: int) -> void:
	_request_arena_lod(lod)


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
