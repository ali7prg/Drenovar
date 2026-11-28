extends Node3D
## «Лес потерянных» world layer (WORLD_API.md). Created by landscape.gd for the city scene when
## the `forest_rescue_v1` flag is ON; `stage.forest_world` is null otherwise (rollback).
## Owns: outer earthworks, dirt paths, the replaced forest (inner kit re-skin at the original
## positions + new natural outer layout with remapped resource ids), landmarks/arena, fog.

signal world_ready
signal fog_reveal_finished(revision: int)

const ForestFlags = preload("res://src/forest_rescue/world/forest_flags.gd")
const ForestAtlas = preload("res://src/forest_rescue/world/forest_atlas.gd")
const ForestTerrain = preload("res://src/forest_rescue/world/forest_terrain.gd")
const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")
const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const ForestCanopy = preload("res://src/forest_rescue/world/forest_canopy.gd")
const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")
const ForestLandmarks = preload("res://src/forest_rescue/world/forest_landmarks.gd")
const ForestImpostors = preload("res://src/forest_rescue/world/forest_impostors.gd")
const ForestOccluders = preload("res://src/forest_rescue/world/forest_occluders.gd")
const ForestWater = preload("res://src/forest_rescue/world/forest_water.gd")
const ForestQuarry = preload("res://src/forest_rescue/world/forest_quarry.gd")
const GROUND_SHADER = preload("res://src/forest_rescue/world/forest_ground.gdshader")
const PAINTED_INCLUDE := "res://src/forest_rescue/world/forest_painted.gdshaderinc"   # impostor bake signature
const SUN_ROTATION := Vector3(-0.837758, -0.558505, 0.0)   # landscape.gd city sun (-48°, -32°, 0)
const PAINT_LIGHT_DIR := Vector3(-0.6, 0.68, 0.42)            # direction TO the crown light (kit vegetation / rocks)
const QUARRY_KIND := 6                                         # Rules.UNDERSTORY "quarry_rock"
const DEAD_TREE_SCALE := 0.72                                  # oak v1 skeleton ×0.72 ≈ 9.5 m (art/01 S-G)
const DEAD_TREE_STONES := [[-3.4, 1.1, 20.0, 0.34], [3.2, -1.5, 75.0, 0.3], [1.3, 3.1, 140.0, 0.24], [-1.8, -2.9, 250.0, 0.2]]
const QUARRY_LEDGE_SHAPE := Vector3(1.7, 0.8, 1.3)             # ledge slab: wide, low, deep
const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")
const PATH_SHADER = preload("res://src/forest_rescue/world/forest_path.gdshader")
const RIVER_SHADER = preload("res://src/forest_rescue/world/forest_river.gdshader")
const SURFACES := "res://assets/city/premium/surfaces07/"

const API_VERSION := 3
## Known forest away from the squad and the mare stays visible slightly dimmed (plain darkening
## ≤ 9 %, no haze colour, never the town); within SIGHT_RADIUS of the squad / mare / escort the
## revealed ground renders exactly like the base.
const DIM_EXPLORED := 0.09
const SIGHT_RADIUS := 10.0
## Kit v2 meshes keep their authored real-metre size (meta heightM/footprintM); the layout
## carries absolute instance scales. TREE_CROWN = nominal crown radius (m) for clearance QA.
const TREE_CROWN := Rules.CROWN_RADIUS

static var _cache: Dictionary = {}        # shared across city-scene rebuilds (versioned keys)

var stage: Node3D
var data: Dictionary
var atlas: RefCounted
var terrain: RefCounted
var masks: RefCounted
var kit: RefCounted
var layout: Dictionary = {}
var canopy: Node3D
var fog: Node3D
var landmarks: Node3D
var water: Node3D                         # ForestWater (lake, waterfall + pond, marsh pools)
var quarry: Node3D                        # ForestQuarry (pass 4: limestone terraces + timber crane)
var paths: MeshInstance3D
var _actors := Node3D.new()
var _props := Node3D.new()
var ready_for_frame := false
var adventure: Dictionary = {}
var locked := true
var reduced_motion := false
var projection_bits := PackedByteArray()
var displayed_bits := PackedByteArray()
var anchor_bits := PackedByteArray()
var hold_bits := PackedByteArray()
var entrance_released := false
var last_fog_key := ""
var fog_revision := -1
var pinned: Dictionary = {}
var extra_sights: Array = []
var received_at_ms := 0
var server_time_ms := 0.0
var last_cull := {}
var setup_ms := {}
## 1022 lazy attach (landscape.attach_forest_world): the city is already on screen, so setup() keeps the
## rebuilt ground tiles and the river restyle aside and commit_ground() applies them in one frame, right
## before the kit forest replaces the 1021 trees.
var deferred_commit := false
var initial_adventure: Dictionary = {}   # deferred setup: state.adventure as the city was presented
var _pending_tiles: Array = []
var _pending_river := false
var setup_stage := ""                    # entry probe: the setup step running in the current frame
var impostor_signature_parts: Array = [] # entry probe: which signature part differs between editor and pack
var remap: Dictionary = {}               # resource id -> Vector2 (visual position, layout)
var resource_look: Dictionary = {}       # resource id -> [kit variant, absolute scale]
var visual_pos: Dictionary = {}          # resource id -> Vector2 actually rendered (last build)
var mesh_keys: Dictionary = {}
var city_state: Dictionary = {}
var arena_state := "locked"
var site_steps: Dictionary = {}
var impostors: Node
var occluders: Node3D                     # ForestOccluders (whole-tree fade of crowns hiding actors)
var _cull_timer := 0.0
var _sight_timer := 0.0
## Build 1024 «туман отстаёт от коня»: presentation lead of the server's own fog reveal. The server
## reveals cells within 10 m of the squad's COMMITTED path (a checkpoint every 4 units, settled by the
## state reads every 1.2 s, then a 2 s dissolve): on the phone the mare and the squad walked into
## fog that cleared up to ~5 s after them. lead_bits stamps the same discs (cell centre within
## LEAD_RADIUS < the server's 10 m) along the AUTHORITATIVE move path the projection already holds,
## up to a little ahead of the squad and the mare, as they walk — so every lead cell is one the
## server reveals itself when the walk commits it (no knowledge the server does not hand out; the
## projection stays authoritative: displayed = (projection | lead) & ~hold). Never sent anywhere.
const LEAD_RADIUS := 9.0          # 10 m server disc − 1 m (its path samples are ≤ 2 m apart)
const LEAD_AHEAD := 4.0           # metres ahead of the farther of the squad / the mare
const LEAD_STEP := 0.2            # s between lead updates while a move runs
const LEAD_REVEAL_SECONDS := 0.45 # dissolve of a lead cell (the server's own reveal takes 2 s)
const LEAD_KEEP_MS := 12000       # lead cells the projection never confirmed are dropped after this
var lead_bits := PackedByteArray()
var _lead_timer := 0.0
var _lead_move := ""
var _lead_reach := 0.0
var _lead_idle_since := 0
## Per-frame cost probe (QA): usec spent in the last lead update.
var lead_usec := 0


# ============================================================================================
# Construction

func setup(owner: Node3D, ground_meshes: Array) -> void:
	var started := Time.get_ticks_usec()
	ForestFog.prepare_noise_async()
	setup_stage = "data"
	stage = owner
	data = owner.data
	name = "ForestWorld"
	_actors.name = "AdventureActors"
	_props.name = "SiteProps"
	add_child(_actors)
	add_child(_props)
	atlas = _cache.get("atlas")
	layout = _cache.get("layout", {})
	masks = _cache.get("masks")
	if atlas == null or layout.is_empty() or masks == null:
		# 1022 (iPhone entry): atlas, layout and static masks (~0.3 s of parsing in one frame on desktop)
		# load on a worker thread; nothing reads them before this await returns.
		var loaded := {}
		var load_data := func() -> void:
			var loaded_atlas: Variant = atlas if atlas != null else ForestAtlas.load_default()
			loaded.atlas = loaded_atlas
			loaded.layout = layout if not layout.is_empty() else _load_layout()
			if masks == null:
				var set := ForestMasks.MaskSet.new(8.0)
				for mask in loaded_atlas.static_masks():
					set.add(mask)
				loaded.masks = set
		var data_task := WorkerThreadPool.add_task(load_data, true, "forest data")
		while not WorkerThreadPool.is_task_completed(data_task):
			await get_tree().process_frame
		WorkerThreadPool.wait_for_task_completion(data_task)
		atlas = loaded.atlas
		layout = loaded.layout
		_cache.atlas = atlas
		_cache.layout = layout
		if loaded.has("masks"):
			masks = loaded.masks
			_cache.masks = masks
	for section in ["resourceRemap", "innerRemap"]:
		for id in layout.get(section, {}):
			var entry: Array = layout[section][id]
			remap[id] = Vector2(float(entry[0]), float(entry[1]))
			if entry.size() >= 5:
				resource_look[id] = [int(entry[3]), float(entry[4])]
	setup_ms.data = (Time.get_ticks_usec() - started) / 1000.0
	await get_tree().process_frame
	setup_stage = "landmarks.plan"
	# Landmarks first: their pads take part in the terrain bake.
	landmarks = ForestLandmarks.new()
	landmarks.name = "Landmarks"
	add_child(landmarks)
	# 1022 (iPhone entry): the placement search is pure array work: a worker thread, not one long frame.
	var plan_task := WorkerThreadPool.add_task(landmarks.plan.bind(atlas, masks, func(x: float, z: float) -> float: return ForestTerrain.base_height(x, z)), true, "forest landmarks plan")
	while not WorkerThreadPool.is_task_completed(plan_task):
		await get_tree().process_frame
	WorkerThreadPool.wait_for_task_completion(plan_task)
	var t := Time.get_ticks_usec()
	var key := "terrain_v%d_%s" % [ForestTerrain.TERRAIN_VERSION, atlas.atlas_id]
	terrain = _cache.get(key)
	if terrain == null:
		await get_tree().process_frame
		setup_stage = "terrain.new"
		terrain = ForestTerrain.new(atlas)
		terrain.extra_pads = landmarks.pads()
		terrain.quarry_center = landmarks.quarry_center()
		terrain.water_bodies = ForestWater.bodies(atlas)
		await get_tree().process_frame
		setup_stage = "terrain.shadows+tiles"
		var shadows := []
		var shadow_task := WorkerThreadPool.add_task(func() -> void: shadows.append(_crown_shadows()), true, "forest crown shadows")
		while not WorkerThreadPool.is_task_completed(shadow_task):
			await get_tree().process_frame
		WorkerThreadPool.wait_for_task_completion(shadow_task)
		terrain.crown_shadows = shadows[0]
		var source_arrays: Array = []
		for part: MeshInstance3D in ground_meshes:
			source_arrays.append(part.mesh.surface_get_arrays(0))
		# 1022 (iPhone entry): the tile scan is pure array work, on a worker thread.
		var tiles_task := WorkerThreadPool.add_task(terrain.read_tiles.bind(source_arrays), true, "forest terrain tiles")
		while not WorkerThreadPool.is_task_completed(tiles_task):
			await get_tree().process_frame
		WorkerThreadPool.wait_for_task_completion(tiles_task)
		await get_tree().process_frame
		# iPhone entry: the bake (pure array work, ~1-4 s) runs on a worker thread while the city keeps
		# animating; nothing reads `terrain` before it is cached below
		setup_stage = "terrain.bake (thread)"
		var bake_task := WorkerThreadPool.add_task(terrain.bake, true, "forest terrain bake")
		while not WorkerThreadPool.is_task_completed(bake_task):
			await get_tree().process_frame
		WorkerThreadPool.wait_for_task_completion(bake_task)
		_cache[key] = terrain
		_cache.tiles = {}
	setup_ms.terrain = (Time.get_ticks_usec() - t) / 1000.0
	t = Time.get_ticks_usec()
	var tiles: Dictionary = _cache.get("tiles", {})
	var slice := Time.get_ticks_usec()
	for part: MeshInstance3D in ground_meshes:
		var tile_key := (part.owner.scene_file_path if part.owner != null else String(part.get_path())) + "/" + String(part.name)
		var rebuilt: Variant = tiles.get(tile_key)
		if rebuilt == null:
			rebuilt = terrain.rebuild_tile(part.mesh)
			tiles[tile_key] = rebuilt if rebuilt != null else false
		if rebuilt is ArrayMesh:
			if deferred_commit:
				_pending_tiles.append([part, rebuilt])
			else:
				part.mesh = rebuilt
				_apply_forest_ground(part)
		if Time.get_ticks_usec() - slice > 4000:
			await get_tree().process_frame
			slice = Time.get_ticks_usec()
	_cache.tiles = tiles
	setup_ms.tiles = (Time.get_ticks_usec() - t) / 1000.0
	t = Time.get_ticks_usec()
	# layout pass 3 (art/01): the kit crowns, bark and rocks are lit from the screen's upper left so they read
	# with a lit top-left and a shaded lower-right; landmarks / props / actors keep the sun-based painted
	# light (their textures carry the painting's own light); the city keeps its sun.
	ForestKit.light_dir = Basis.from_euler(SUN_ROTATION).z.normalized()
	ForestKit.crown_light_dir = PAINT_LIGHT_DIR
	await get_tree().process_frame
	setup_stage = "kit"
	kit = ForestKit.new(data, stage.scenery_material)
	await get_tree().process_frame
	setup_stage = "canopy+paths"
	canopy = ForestCanopy.new()
	canopy.name = "Canopy"
	add_child(canopy)
	occluders = ForestOccluders.new(self, canopy)
	add_child(occluders)
	_build_paths()
	await get_tree().process_frame
	setup_stage = "river+water"
	if deferred_commit:
		_pending_river = true
	else:
		_restyle_river()
	water = ForestWater.new()
	water.name = "Water"
	add_child(water)
	water.build(atlas, func(x: float, z: float) -> float: return terrain.ground_height(x, z), _noise_texture())
	await get_tree().process_frame
	setup_stage = "quarry"
	_build_quarry()
	await get_tree().process_frame
	setup_stage = "impostor meshes"
	impostors = ForestImpostors.new()
	impostors.name = "Impostors"
	add_child(impostors)
	var bake_list: Array = []
	for species in Rules.SPECIES.size():
		for variant in Rules.SPECIES_VARIANTS[species]:
			var mesh := _tree_mesh(species, variant)
			bake_list.append([mesh[2], canopy.meshes[mesh[0]].lods[0]])
		await get_tree().process_frame       # iPhone entry: one species' meshes per frame
	# pass 4: the bare white dead tree is a tree like the others (3D near, impostor far): a KIND_TREE mesh
	# without an impostor is skipped where its cell draws impostors, so it was never seen
	var dead_mesh := _dead_tree_mesh()
	if not dead_mesh.is_empty():
		bake_list.append([dead_mesh[2], canopy.meshes[dead_mesh[0]].lods[0]])
	# export-safe signature (no file listings / mtimes: an exported pack has neither the raw .glb nor
	# modification times): bake keys, the looks, the kit json and painted shader digests; the kit GLB md5s
	# are checked in the editor only (ForestImpostors stores them with the shipped bake)
	var signature := "%s;%s;%s;%s;" % [str(FOLIAGE_LOOK), str(PAINT_LIGHT_DIR), FileAccess.get_md5(ForestKit.KIT_JSON),
		(load(PAINTED_INCLUDE) as ShaderInclude).code.md5_text()]
	impostor_signature_parts = [str(FOLIAGE_LOOK).md5_text(), str(PAINT_LIGHT_DIR), FileAccess.get_md5(ForestKit.KIT_JSON),
		(load(PAINTED_INCLUDE) as ShaderInclude).code.md5_text()]
	for entry in bake_list:
		signature += String(entry[0]) + ";"
	var kit_md5 := {}
	if OS.has_feature("editor"):
		# only where the raw GLBs exist (an editor binary running an exported pack has none)
		for file in ResourceLoader.list_directory(ForestKit.KIT_DIR):
			if file.ends_with(".glb") and FileAccess.file_exists(ForestKit.KIT_DIR + file):
				kit_md5[file] = FileAccess.get_md5(ForestKit.KIT_DIR + file)
	setup_stage = "impostors"
	await impostors.bake(bake_list, SUN_ROTATION, stage.camera.environment, signature, kit_md5)
	setup_stage = "fog"
	canopy.impostors = impostors
	setup_ms.impostors = (Time.get_ticks_usec() - t) / 1000.0
	fog = ForestFog.new()
	fog.name = "Fog"
	add_child(fog)
	var light: Vector3 = -stage.shadow_direction if stage.shadow_direction != Vector3.ZERO else Vector3(0.45, 0.74, 0.5)
	while not ForestFog.noise_ready():
		await get_tree().process_frame
	await get_tree().process_frame
	var fog_ground := func(x: float, z: float) -> float: return terrain.ground_height(x, z)
	# 1022 (iPhone entry): the fog's grid, height map and billows are computed off the main thread.
	var fog_task := WorkerThreadPool.add_task(ForestFog.prepare_build.bind(fog_ground), true, "forest fog prepare")
	while not WorkerThreadPool.is_task_completed(fog_task):
		await get_tree().process_frame
	WorkerThreadPool.wait_for_task_completion(fog_task)
	fog.build(fog_ground, light)
	await get_tree().process_frame
	fog.reveal_finished.connect(func() -> void: fog_reveal_finished.emit(fog_revision))
	fog.target_applied.connect(_on_fog_target_applied)
	landmarks.arena_clear_discs = [[ForestWater.POND_CENTER, ForestWater.POND_RADIUS + 4.5], [ForestWater.FALLS_LIP + ForestWater.FALLS_FACING * 2.0, 4.0]]
	setup_stage = "landmarks.populate"
	await landmarks.populate()
	await get_tree().process_frame
	setup_stage = "fog receivers"
	_register_fog_receivers()
	setup_ms.visuals = (Time.get_ticks_usec() - t) / 1000.0
	await get_tree().process_frame
	setup_stage = "adventure state"
	if deferred_commit:
		# the layer is still hidden: the first fog target (distance fields) is computed off the main thread
		fog.threaded_snap = true
		apply_adventure(initial_adventure)
		while fog.target_pending():
			await get_tree().process_frame
		fog.threaded_snap = false
	else:
		apply_adventure({})
	setup_ms.total = (Time.get_ticks_usec() - started) / 1000.0
	setup_stage = "post-setup (city build / first ticks)"
	set_process(true)
	ready_for_frame = true
	print("ForestWorld: ready ", setup_ms, " kit=", kit.kit_status().missing.size(), " missing kit assets")


## Applies what a deferred setup kept aside (see deferred_commit).
func commit_ground() -> void:
	for entry in _pending_tiles:
		var part: MeshInstance3D = entry[0]
		if is_instance_valid(part):
			part.mesh = entry[1]
			_apply_forest_ground(part)
	_pending_tiles.clear()
	if _pending_river:
		_pending_river = false
		_restyle_river()


## Pass 4 (art/01 quarry): terraces + crane round the quarry pit (ForestQuarry), off trails / glade 05 / mine.
func _build_quarry() -> void:
	if landmarks == null:
		return
	var center: Vector2 = landmarks.quarry_center()
	var mine := Vector2.INF
	for placement in landmarks.placements:
		if placement.id == "lf_env_quarry_mine":
			mine = Vector2(placement.position.x, placement.position.z)
	var site: Dictionary = atlas.site_by_id.get("lf_site_05", {})
	if center == Vector2.INF or mine == Vector2.INF or site.is_empty():
		return
	var glade := Vector2(site.center.x, site.center.z)
	var axis_v := ((mine - glade).normalized() * 0.6 + Vector2(-0.7071, -0.7071) * 0.4).normalized()
	quarry = ForestQuarry.new()
	quarry.name = "Quarry"
	add_child(quarry)
	quarry.build(center, atan2(axis_v.y, axis_v.x), mine, glade, float(site.radius),
		func(x: float, z: float) -> float: return terrain.ground_height(x, z),
		func(x: float, z: float) -> float: return float(atlas.nearest_route(x, z, false).get("distance", 99.0)))


## Soft ground shadows under the crowns (layout pass 3): [x, z, crown radius, crown height] for every
## outer tree of the layout (ambient + remapped resource trees); the terrain bake darkens a blob
## offset away from the painted light.
func _crown_shadows() -> Array:
	var out: Array = []
	if layout.is_empty():
		return out
	var heights := [13.6, 15.0, 12.0, 10.0, 14.0, 13.6]
	for item in layout.get("trees", []):
		var sp := int(item[2])
		out.append([float(item[0]), float(item[1]), Rules.CROWN_RADIUS[sp] * float(item[5]), heights[sp] * float(item[5])])
	var names := {}
	for tree in data.woods:
		names[tree.id] = tree.name
	for id in layout.get("resourceRemap", {}):
		var e: Array = layout.resourceRemap[id]
		var sp: int = Rules.RESOURCE_SPECIES.get(String(names.get(id, "")), Rules.PINE)
		out.append([float(e[0]), float(e[1]), Rules.CROWN_RADIUS[sp] * float(e[4]), heights[sp] * float(e[4])])
	return out


func _load_layout() -> Dictionary:
	var text := FileAccess.get_file_as_string(Rules.LAYOUT_PATH)
	var parsed: Variant = JSON.parse_string(text) if not text.is_empty() else null
	if parsed == null and ResourceLoader.exists(Rules.LAYOUT_PATH):
		var resource: Variant = load(Rules.LAYOUT_PATH)
		parsed = resource.data if resource is JSON else null
	if not parsed is Dictionary or String(parsed.get("layoutId", "")) != Rules.LAYOUT_ID:
		push_error("ForestWorld: missing or unsupported forest layout " + Rules.LAYOUT_PATH)
		return {"trees": [], "understory": [], "innerUnderstory": [], "resourceRemap": {}}
	return parsed


func _build_paths() -> void:
	var vertices := PackedVector3Array()
	var colors := PackedColorArray()
	var normals := PackedVector3Array()
	var indices := PackedInt32Array()
	# art/07: a narrow worn dirt trail (≈ 1.6 m) whose edges are overgrown with grass
	# (forest_path.gdshader), on the meandered visual trail (ForestAtlas).
	for r in atlas.routes.size():
		var decor: bool = atlas.routes[r].get("decor", false)
		var half := 0.7 if decor else 0.8
		var fringe := 0.5 if decor else 0.55
		var points: PackedVector3Array = atlas.routes[r].points
		var on_deck: PackedByteArray = terrain.road_on_deck[r]
		var profile: PackedFloat32Array = terrain.road_profiles[r]
		var run_start := -1
		# the mare's first trail leaves the base at the horse origin (inside ±56): drawn in full
		var entry: bool = atlas.routes[r].from == "lf_horse_origin" or atlas.routes[r].to == "lf_horse_origin"
		for i in points.size():
			var p := points[i]
			var skip := on_deck[i] == 1 or (maxf(absf(p.x), absf(p.z)) < 56.0 and not entry)
			if skip:
				run_start = -1
				continue
			var a := points[maxi(i - 1, 0)]
			var b := points[mini(i + 1, points.size() - 1)]
			var tangent := Vector2(b.x - a.x, b.z - a.z).normalized()
			var side := Vector2(-tangent.y, tangent.x)
			var base := vertices.size()
			for offset in [-(half + fringe), -half, half, half + fringe]:
				var q: Variant = Vector2(p.x, p.z) + side * offset
				var y: float = maxf(profile[i], terrain.ground_height(q.x, q.y)) + 0.06
				vertices.append(Vector3(q.x, y, q.y))
				normals.append(Vector3.UP)
				colors.append(Color(1, 1, 1, 0.0 if absf(offset) > half else 1.0))
			if run_start >= 0:
				var prev := base - 4
				for k in 3:
					indices.append_array(PackedInt32Array([prev + k, base + k, prev + k + 1, prev + k + 1, base + k, base + k + 1]))
			run_start = i
	if vertices.is_empty():
		return
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var material := ShaderMaterial.new()
	material.shader = PATH_SHADER
	material.render_priority = -4
	material.set_shader_parameter("path_albedo", load(SURFACES + "path-albedo.webp"))
	material.set_shader_parameter("path_normal", load(SURFACES + "path-normal.png"))
	material.set_shader_parameter("path_roughness", load(SURFACES + "path-roughness.png"))
	material.set_shader_parameter("noise_tex", ForestFog._noise_texture if ForestFog._noise_texture != null else ImageTexture.create_from_image(ForestFog.make_noise_image(128)))
	paths = MeshInstance3D.new()
	paths.name = "DirtPaths"
	paths.mesh = mesh
	paths.material_override = material
	paths.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(paths)


var _ground_material: ShaderMaterial


## Layout pass 4: forest-touched ground tiles draw with forest_ground.gdshader (the city ground shader's
## code path unchanged inside the base square; painted meadow detail and camp pads on the forest ring).
func _apply_forest_ground(part: MeshInstance3D) -> void:
	var source: Variant = part.material_override
	if not source is ShaderMaterial:
		return
	if _ground_material == null:
		_ground_material = ShaderMaterial.new()
		_ground_material.shader = GROUND_SHADER
		for name in ["grass", "earth", "rock", "normal_texture", "roughness_texture", "soil_normal", "soil_roughness",
				"stone_normal", "stone_roughness", "settlement"]:
			_ground_material.set_shader_parameter(name, (source as ShaderMaterial).get_shader_parameter(name))
		_ground_material.set_shader_parameter("detail_noise", _noise_texture())
		var pads := PackedVector4Array()
		var glades: Array = atlas.sites.duplicate()
		glades.append_array(atlas.extra_glades)
		for glade in glades:
			if pads.size() >= 16:
				break
			pads.append(Vector4(glade.center.x, glade.center.z, ForestTerrain.GLADE_DIRT, fposmod(glade.center.x * 0.37 + glade.center.z * 0.11, TAU)))
		_ground_material.set_shader_parameter("pads", pads)
		_ground_material.set_shader_parameter("pad_count", pads.size())
	part.material_override = _ground_material


func _noise_texture() -> Texture2D:
	return ForestFog._noise_texture if ForestFog._noise_texture != null else ImageTexture.create_from_image(ForestFog.make_noise_image(128))


## The city water strip gets the art/01 river material (world layer only; flag OFF keeps the
## original material). The strip is found by its shader, nothing else in landscape.gd changes.
func _restyle_river() -> void:
	var material := ShaderMaterial.new()
	material.shader = RIVER_SHADER
	material.set_shader_parameter("noise_tex", _noise_texture())
	var deck: Rect2 = atlas.bridge_deck_rect()
	material.set_shader_parameter("bridge_rect", Vector4(deck.position.x, deck.position.y, deck.size.x, deck.size.y))
	for feature in atlas.water_features:
		if feature.id == "lake":
			material.set_shader_parameter("lake_circle", Vector4(feature.center.x, feature.center.y, feature.radius, 1.0))
			material.set_shader_parameter("lake_shape", Vector4(float(feature.minor) / float(feature.radius), cos(float(feature.rot)), sin(float(feature.rot)), 0.0))
	for child in stage.get_children():
		if child is MeshInstance3D and child.material_override is ShaderMaterial:
			var shader: Shader = (child.material_override as ShaderMaterial).shader
			if shader != null and shader.resource_path == "res://src/water.gdshader":
				child.material_override = material
				child.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


# ============================================================================================
# Forest (called by landscape.build_forest when this layer is active)

## landscape.build_forest frees and recreates its "Forest" group; the canopy lives inside it
## (so the existing smoke checks still see forest content) and survives each rebuild.
func detach_canopy() -> void:
	if canopy != null and canopy.get_parent() != null:
		canopy.get_parent().remove_child(canopy)


func attach_canopy(group: Node3D) -> void:
	if canopy == null:
		return
	if canopy.get_parent() != null:
		canopy.get_parent().remove_child(canopy)
	group.add_child(canopy)


## Called from landscape.present(): follows state.adventure (idempotent; absent → locked).
func apply_state_hint(state: Dictionary) -> void:
	if state.get("city") is Dictionary:
		city_state = state.city
	if presentation_active:
		return
	var adv: Variant = state.get("adventure", {})
	var key := JSON.stringify(adv) if adv is Dictionary else "{}"
	if key == _last_hint:
		return
	_last_hint = key
	apply_adventure(adv if adv is Dictionary else {})


var _last_hint := ""
## Story presentation (forest_game.set_presentation): while true, landscape state hints are not applied
## (the presentation projection stays on screen); forest_game re-applies the server state when it ends.
var presentation_active := false


## Registers one kit variant (real-metre mesh, no normalisation). Returns [mesh index, 1.0, key].
func _mesh_for(asset: Dictionary, key: String, kind: int, variant: int, variant_name := "") -> Array:
	if mesh_keys.has(key):
		return mesh_keys[key]
	var variants: Array = asset.variants
	var entry: Dictionary = variants[(maxi(variant, 1) - 1) % variants.size()]
	if not variant_name.is_empty():
		for candidate: Dictionary in variants:
			if String(candidate.get("name", "")) == variant_name:
				entry = candidate
				break
	var index: int = canopy.register_mesh(key, entry.lods, entry.tris, kind, entry.radius, entry.height)
	mesh_keys[key] = [index, 1.0, key]
	return mesh_keys[key]


## Bare white dead tree (art/01 S-G, "built from kit pieces"): the golden oak v1 branch skeleton
## (its bark surface only, every LOD) wearing the birch's white bark material.
func _dead_tree_mesh() -> Array:
	if mesh_keys.has("deadtree"):
		return mesh_keys["deadtree"]
	var oak: Dictionary = kit.tree_asset("lf_env_golden_oak")
	var birch: Dictionary = kit.tree_asset("lf_env_birch")
	if not oak.get("kit", false) or not birch.get("kit", false) or oak.variants.is_empty() or birch.variants.is_empty():
		return []
	var skeleton: Dictionary = oak.variants[0]
	var bark: Material = (birch.variants[0].lods[0] as Mesh).surface_get_material(0)
	var lods: Array = []
	var tris: Array = []
	for lod in 3:
		var source: Mesh = skeleton.lods[lod]
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, source.surface_get_arrays(0))
		mesh.surface_set_material(0, bark)
		lods.append(mesh)
		tris.append(ForestKit.mesh_triangles(mesh))
	var index: int = canopy.register_mesh("deadtree", lods, tris, ForestCanopy.KIND_TREE, 4.5, 9.0)
	mesh_keys["deadtree"] = [index, 1.0, "deadtree"]
	return mesh_keys["deadtree"]


## Layout pass 4 (art/01 crown colour, measured with crown_hsv.py): per-species foliage colour (hue
## rotation, saturation) and a lifted AO floor (shaded inner crown never near black). Pines blue-green teal,
## oaks golden olive, the hollow oak golden like the grove instead of orange-red.
const FOLIAGE_LOOK := {
	"lf_env_dark_pine": {"hue_shift": 32.0, "albedo_sat": 2.4, "ao_floor": 0.72, "albedo_gain": 0.44, "albedo_contrast": 0.9},
	"lf_env_golden_oak": {"hue_shift": -8.0, "albedo_sat": 1.0, "ao_floor": 0.6},
	"lf_env_golden_oak_green": {"hue_shift": -10.0, "albedo_sat": 1.05, "ao_floor": 0.6},
	"lf_env_birch": {"hue_shift": -6.0, "albedo_sat": 1.0, "ao_floor": 0.6},
	"lf_env_willow": {"hue_shift": -6.0, "albedo_sat": 1.0, "ao_floor": 0.6},
	"lf_env_hollow_oak": {"hue_shift": 17.0, "albedo_sat": 0.92, "ao_floor": 0.6},
}


func _tree_mesh(species: int, variant: int) -> Array:
	var id: String = Rules.SPECIES[species]
	var variants: Array = Rules.SPECIES_VARIANTS[species]
	var v: int = variant if variants.has(variant) else int(variants[(maxi(variant, 1) - 1) % variants.size()])
	var asset: Dictionary = kit.tree_asset(id)
	if FOLIAGE_LOOK.has(id) and asset.get("kit", false):
		asset = _shaded_asset(asset, "look:" + id, FOLIAGE_LOOK[id], "lf_foliage")
	return _mesh_for(asset, "tree:%s:v%d" % [id, v], ForestCanopy.KIND_TREE, v, "v%d" % v)


func _under_mesh(kind_index: int, variant: int) -> Array:
	var kind: String = Rules.UNDERSTORY[clampi(kind_index, 0, Rules.UNDERSTORY.size() - 1)]
	var spec: Array = Rules.UNDERSTORY_KIT[kind]
	var names: Array = spec[1]
	var variant_name: String = names[(maxi(variant, 1) - 1) % names.size()]
	var canopy_kind := ForestCanopy.KIND_ROCK if kind in Rules.LARGE_UNDERSTORY else ForestCanopy.KIND_UNDER
	var asset: Dictionary = kit.understory_asset(kind, spec[0])
	if kind == "quarry_rock":
		asset = _limestone_asset(asset, "quarry")
	if UNDER_LOOK.has(kind) and asset.get("kit", false) and not OS.get_cmdline_user_args().has("--no-under-look"):
		asset = _shaded_asset(asset, "look:under:" + kind, UNDER_LOOK[kind], "lf_foliage")
	return _mesh_for(asset, "under:%s:%s" % [kind, variant_name], canopy_kind, 1, variant_name)


## Close-zoom bushes (review at zoom 26: the golden brambles read as dark-speckled blobs with black holes):
## interior leaves keep a brightness floor, cards seen edge-on stay filled, a lower cutout closes the holes.
const UNDER_LOOK := {
	"bramble": {"ao_floor": 0.8, "alpha_cut": 0.32, "edge_fade": Vector2(0.0, 0.04), "albedo_gain": 1.05},
}


## Pass 3 (art/01 waterfall): the kit moss rock v1 as dark wet stone (ForestKit painted copy with `wet`).
func _wet_rock_mesh() -> Array:
	var kind := "rock"
	var spec: Array = Rules.UNDERSTORY_KIT[kind]
	var names: Array = spec[1]
	var asset := _shaded_asset(kit.understory_asset(kind, spec[0]), "wet", {"wet": 0.85})
	return _mesh_for(asset, "under:rock_wet:%s" % names[0], ForestCanopy.KIND_ROCK, 1, names[0])


## Pass 2 (art/01 quarry): the quarry ledges, cliffs and boulders are the kit moss rock in a pale
## limestone look (ForestKit painted material copy with `limestone`, cracks and shading kept).
func _limestone_asset(asset: Dictionary, tag: String) -> Dictionary:
	return _shaded_asset(asset, tag, {"limestone": 0.8})


func _shaded_asset(asset: Dictionary, tag: String, params: Dictionary, prefix := "") -> Dictionary:
	var key := "shaded:%s:%s" % [tag, asset.get("id", "")]
	if mesh_keys.has(key):
		return mesh_keys[key]
	var copy := asset.duplicate()
	var variants: Array = []
	var materials := {}
	for entry: Dictionary in asset.get("variants", []):
		var e := entry.duplicate()
		var lods: Array = []
		for lod: Mesh in entry.lods:
			var mesh := ArrayMesh.new()
			for s in lod.get_surface_count():
				mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, lod.surface_get_arrays(s))
				var material: Material = lod.surface_get_material(s)
				if material is ShaderMaterial and (prefix.is_empty() or String(material.resource_name).to_lower().begins_with(prefix)):
					if not materials.has(material):
						var pale := (material as ShaderMaterial).duplicate() as ShaderMaterial
						for name in params:
							pale.set_shader_parameter(name, params[name])
						ForestKit.register_copy(material, pale)
						materials[material] = pale
					material = materials[material]
				mesh.surface_set_material(s, material)
			lods.append(mesh)
		e.lods = lods
		variants.append(e)
	copy.variants = variants
	mesh_keys[key] = copy
	return copy


## Visual position of a resource tree (natural slot from the layout; the original spot when the
## slot is blocked by the player's property). Same point the pick list uses.
func resource_tree_position(id: String) -> Vector3:
	if visual_pos.has(id):
		var v: Vector2 = visual_pos[id]
		return Vector3(v.x, height_at(v.x, v.y), v.y)
	for tree in data.woods:
		if tree.id == id:
			var p := _tree_xz(tree)
			return Vector3(p.x, height_at(p.x, p.y), p.y)
	return Vector3.INF


func _tree_xz(tree: Dictionary) -> Vector2:
	return remap.get(tree.id, Vector2(float(tree.p[0]), float(tree.p[2])))


static func _excluded(p: Vector2, exclusions: Array) -> bool:
	for rect: Rect2 in exclusions:
		if rect.has_point(p):
			return true
	return false


## Trees, stumps and understory of the city map (pickable resource trees keep the legacy rule).
## staged=true (the city load, landscape.build_forest(..., staged)): the instance build yields to the
## next frame whenever the landscape's setup budget is used up (stage.setup_slice: 3.5 ms in game,
## 45 ms under the launch screen, 2 ms in a background build), so no single frame carries the whole
## forest (it was one 2.4 s frame on the desktop software renderer). A newer build cancels an older
## staged one at its next yield. staged=false (a felled tree) stays synchronous.
## 1022: the 1021 town rules apply too: no tree on the wall band / gate roads (stage.walls.blocks),
## no wild understory inside the town (stage.in_town).
var _forest_build_serial := 0
var build_parts: Dictionary = {}

func _city_blocked(p: Vector2, exclusions: Array, street_margin: float) -> bool:
	if _excluded(p, exclusions):
		return true
	if street_margin > 0.0 and stage.on_street(p, street_margin):
		return true
	var walls: Variant = stage.get("walls")
	return walls != null and walls.blocks(p.x, p.y)


func build_city_forest(city: Dictionary, exclusions: Array, staged := false) -> void:
	_forest_build_serial += 1
	var serial := _forest_build_serial
	var started := Time.get_ticks_usec()
	var slice := started
	var part := started
	build_parts = {"staged": staged, "frames": 1}
	_built_ok = false
	var previous_stage := setup_stage
	setup_stage = "city forest instances"
	city_state = city
	if occluders != null:
		occluders.clear()
	canopy.clear_instances()
	stage.selectable_trees.clear()
	stage.standing_tree_cells.clear()
	visual_pos.clear()
	var felled := {}
	for id in city.get("progress", {}).get("felled", []):
		felled[id] = true
	var kingdom: bool = city.get("kingdom") is Dictionary
	var stump: Dictionary = kit.stump_asset()
	var stump_mesh: Array = _mesh_for(stump, "stump:resource", ForestCanopy.KIND_STUMP, 1)
	var town_check: bool = stage.has_method("in_town")
	var count := 0
	for tree in data.woods:
		if tree.village and not kingdom:
			continue
		# Pickable set exactly as the legacy forest (decided on the original spot); the visual
		# slot falls back to the original spot when the player's property covers it.
		var original := Vector2(float(tree.p[0]), float(tree.p[2]))
		if _city_blocked(original, exclusions, 1.5):
			continue
		var xz := _tree_xz(tree)
		if xz != original and _city_blocked(xz, exclusions, 1.5):
			xz = original
		visual_pos[tree.id] = xz
		var y := height_at(xz.x, xz.y)
		var entry: Dictionary = tree.duplicate()
		entry.p = [xz.x, y, xz.y]
		stage.selectable_trees.append(entry)
		if felled.has(tree.id):
			# 1021: a felled tree is cleared away completely inside the town; the wild forest keeps a stump.
			if not (town_check and stage.in_town(xz.x, xz.y)):
				canopy.add_instance(stump_mesh[0], Transform3D(Basis(Vector3.UP, float(tree.angle)).scaled(Vector3.ONE * 0.7), Vector3(xz.x, y, xz.y)))
			continue
		var cell := Vector2i(floori(xz.x / 4.0), floori(xz.y / 4.0))
		if not stage.standing_tree_cells.has(cell):
			stage.standing_tree_cells[cell] = []
		stage.standing_tree_cells[cell].append(xz)
		var species: int = Rules.RESOURCE_SPECIES.get(String(tree.name), Rules.PINE)
		var look: Array = resource_look.get(tree.id, [])
		var variant: int = int(look[0]) if look.size() == 2 else Rules.kit_variant_for_legacy(int(tree.variant), Rules.id_hash(tree.id), species)
		var scale: float = float(look[1]) if look.size() == 2 else Rules.resource_scale(species, float(tree.scale))
		if variant >= Rules.GREEN_VARIANT_BASE:
			species = Rules.OAK_GREEN
			variant -= Rules.GREEN_VARIANT_BASE
		var mesh := _tree_mesh(species, variant)
		var transform := Transform3D(Basis(Vector3.UP, float(tree.angle)).scaled(Vector3.ONE * scale), Vector3(xz.x, y - 0.05, xz.y))
		canopy.add_instance(mesh[0], transform)
		_add_impostor(mesh, transform.origin, float(tree.angle), scale)
		count += 1
		if staged and count % 8 == 0:
			var next: int = await stage.setup_slice(slice)
			if next != slice:
				build_parts.frames += 1
				if serial != _forest_build_serial:
					return
			slice = next
	build_parts.resource_ms = (Time.get_ticks_usec() - part) / 1000.0
	part = Time.get_ticks_usec()
	for item in layout.get("trees", []):
		var xz := Vector2(float(item[0]), float(item[1]))
		if _city_blocked(xz, exclusions, 0.0):
			continue
		var mesh := _tree_mesh(int(item[2]), int(item[3]))
		var scale := float(item[5])
		var transform := Transform3D(Basis(Vector3.UP, deg_to_rad(float(item[4]))).scaled(Vector3.ONE * scale),
			Vector3(xz.x, height_at(xz.x, xz.y) - 0.05, xz.y))
		canopy.add_instance(mesh[0], transform)
		_add_impostor(mesh, transform.origin, deg_to_rad(float(item[4])), scale)
		count += 1
		if staged and count % 8 == 0:
			var next: int = await stage.setup_slice(slice)
			if next != slice:
				build_parts.frames += 1
				if serial != _forest_build_serial:
					return
			slice = next
	build_parts.ambient_ms = (Time.get_ticks_usec() - part) / 1000.0
	part = Time.get_ticks_usec()
	for list_name in ["understory", "innerUnderstory"]:
		var inner: bool = list_name == "innerUnderstory"
		for item in layout.get(list_name, []):
			var xz := Vector2(float(item[0]), float(item[1]))
			if _city_blocked(xz, exclusions, 1.7 if inner else 0.0):
				continue
			if inner and town_check and stage.in_town(xz.x, xz.y):
				continue
			var mesh := _under_mesh(int(item[2]), int(item[3]))
			var y := height_at(xz.x, xz.y) + (float(item[6]) if item.size() > 6 else 0.0)
			var shape := Vector3.ONE
			if int(item[2]) == QUARRY_KIND and int(item[3]) == 2:
				shape = QUARRY_LEDGE_SHAPE          # pass 3: terraced limestone ledges (flat lit tops, faces)
			var basis := Basis(Vector3.UP, deg_to_rad(float(item[4]))).scaled(shape * float(item[5]))
			canopy.add_instance(mesh[0], Transform3D(basis, Vector3(xz.x, y - 0.03, xz.y)))
			count += 1
			if staged and count % 16 == 0:
				var next: int = await stage.setup_slice(slice)
				if next != slice:
					build_parts.frames += 1
					if serial != _forest_build_serial:
						return
				slice = next
	build_parts.understory_ms = (Time.get_ticks_usec() - part) / 1000.0
	part = Time.get_ticks_usec()
	# art/01 S-G: the bare pale dead tree (~9.5 m) at its mark (kit oak skeleton with birch bark) with pale
	# limestone stones round it (the bones module stands beside it, ForestLandmarks DEAD_TREE_SET).
	if landmarks != null and landmarks.dead_tree_spot != Vector2.INF:
		var dead := _dead_tree_mesh()
		if not dead.is_empty():
			var spot: Vector2 = landmarks.dead_tree_spot
			var origin := Vector3(spot.x, height_at(spot.x, spot.y) - 0.1, spot.y)
			canopy.add_instance(dead[0], Transform3D(Basis(Vector3.UP, 2.3).scaled(Vector3.ONE * DEAD_TREE_SCALE), origin))
			_add_impostor(dead, origin, 2.3, DEAD_TREE_SCALE)
			var stone := _under_mesh(Rules.UNDERSTORY.find("quarry_rock"), 1)
			for st in DEAD_TREE_STONES:
				var q: Vector2 = spot + Vector2(float(st[0]), float(st[1]))
				canopy.add_instance(stone[0], Transform3D(Basis(Vector3.UP, deg_to_rad(float(st[2]))).scaled(Vector3(1.0, 1.35, 1.0) * float(st[3])),
					Vector3(q.x, height_at(q.x, q.y) - 0.15, q.y)))
	# Waterfall outcrop (atlas v2): kit limestone rocks stacked into the cliff behind the fall; pass 3
	# (art/01): a dark wet rock face behind the white water.
	var rock_mesh := _wet_rock_mesh()
	for rock in ForestWater.outcrop_rocks():
		var basis := Basis(Vector3.UP, float(rock[2])).scaled(rock[3])
		canopy.add_instance(rock_mesh[0], Transform3D(basis, Vector3(rock[0], height_at(rock[0], rock[1]) - 0.2, rock[1])))
	if staged:
		var next: int = await stage.setup_slice(slice)
		if next != slice:
			build_parts.frames += 1
			if serial != _forest_build_serial:
				return
		slice = next
	build_parts.extras_ms = (Time.get_ticks_usec() - part) / 1000.0
	part = Time.get_ticks_usec()
	_refresh_local_anchors()
	if staged:
		# 1023: the anchors, the fog receivers and the fog cull each get a frame of their own
		await stage.yield_frame()
		build_parts.frames += 1
		if serial != _forest_build_serial:
			return
	_register_fog_receivers()
	if staged:
		await stage.yield_frame()
		build_parts.frames += 1
		if serial != _forest_build_serial:
			return
	_apply_fog_cull()
	build_parts.fog_cull_ms = (Time.get_ticks_usec() - part) / 1000.0
	if staged:
		# the first canopy upload (on_camera_changed) gets a frame of its own
		await stage.yield_frame()
		build_parts.frames += 1
		if serial != _forest_build_serial:
			return
	last_cull.build_ms = (Time.get_ticks_usec() - started) / 1000.0
	_built_felled = felled
	_built_ok = true
	setup_stage = previous_stage
	if stage.camera != null and stage.camera.is_inside_tree():
		on_camera_changed()
	call_deferred("_emit_ready_once")


## 1022: the felled set the instance buffers hold; a newly felled tree then only takes its own
## instances out (fell_trees) instead of rebuilding every cell (134 ms -> a few ms per felling).
var _built_felled := {}
var _built_ok := false
var last_fell_ms := 0.0


## Applies newly felled trees to the built city forest: their kit instances and impostors leave
## their cells, a stump stays in the wild forest (none inside the town, as in 1021). Returns false
## when a full build is needed (nothing built yet, or a felled tree came back).
func fell_trees(city: Dictionary) -> bool:
	if not _built_ok or canopy == null or stage == null:
		return false
	var now := {}
	for id in city.get("progress", {}).get("felled", []):
		now[id] = true
	for id in _built_felled:
		if not now.has(id):
			return false
	city_state = city
	var added := {}
	for id in now:
		if not _built_felled.has(id) and visual_pos.has(id):
			added[id] = true
	_built_felled = now
	if added.is_empty():
		return true
	var started := Time.get_ticks_usec()
	var town_check: bool = stage.has_method("in_town")
	var stump_mesh: Array = _mesh_for(kit.stump_asset(), "stump:resource", ForestCanopy.KIND_STUMP, 1)
	for tree in data.woods:
		if not added.has(tree.id):
			continue
		var xz: Vector2 = visual_pos[tree.id]
		canopy.remove_tree_at(xz)
		var cell := Vector2i(floori(xz.x / 4.0), floori(xz.y / 4.0))
		var standing: Array = stage.standing_tree_cells.get(cell, [])
		standing.erase(xz)
		if standing.is_empty():
			stage.standing_tree_cells.erase(cell)
		if not (town_check and stage.in_town(xz.x, xz.y)):
			var y := height_at(xz.x, xz.y)
			canopy.add_instance(stump_mesh[0], Transform3D(Basis(Vector3.UP, float(tree.angle)).scaled(Vector3.ONE * 0.7), Vector3(xz.x, y, xz.y)))
	if occluders != null:
		occluders.clear()
	_refresh_local_anchors()
	_apply_fog_cull()
	last_fell_ms = (Time.get_ticks_usec() - started) / 1000.0
	if stage.camera != null and stage.camera.is_inside_tree():
		on_camera_changed()
	return true


func _register_fog_receivers() -> void:
	if fog == null:
		return
	var list: Array = ForestKit.fog_receivers.duplicate()
	if impostors != null and impostors.material != null:
		list.append(impostors.material)
	fog.set_receivers(list)


func _add_impostor(mesh: Array, origin: Vector3, yaw: float, scale: float) -> void:
	if impostors != null and impostors.has_impostor(mesh[2]):
		var entry: Array = impostors.instance_for(mesh[2], origin, yaw, scale)
		canopy.add_impostor(entry[0], entry[1])


var _ready_emitted := false
func _emit_ready_once() -> void:
	if _ready_emitted:
		return
	_ready_emitted = true
	world_ready.emit()


# ============================================================================================
# Camera / streaming

func on_camera_changed() -> void:
	if canopy == null or stage == null:
		return
	var started := Time.get_ticks_usec()
	var target: Vector3 = stage.camera_target
	var zoom: float = stage.camera_zoom
	var view_radius := maxf(65.0, zoom * 1.35)
	var points: Array = []
	for id in pinned:
		var area: Dictionary = pinned[id]
		var c: Vector3 = area.center
		var r: float = area.radius
		for o in [Vector2.ZERO, Vector2(r, r), Vector2(-r, r), Vector2(r, -r), Vector2(-r, -r)]:
			var q: Vector2 = Vector2(clampf(c.x + o.x, -111.9, 111.9), clampf(c.z + o.y, -111.9, 111.9))
			if not points.has(q):
				points.append(q)
	var selected := ForestMasks.select_chunks(Vector2(target.x, target.z), view_radius, points,
		Callable(self, "chunk_explored"), 4, 8)
	var classes := {}
	for cls in ["full", "proxy", "fogOnly", "unloaded"]:
		for id in selected.get(cls, []):
			classes[id] = cls
	# Budget overflow inside the view (zoomed-out ortho camera sees all 16 chunks): instead of
	# bare ground these chunks draw tree impostors only (2 triangles per tree, no understory).
	for chunk in ForestMasks.all_chunks():
		if classes.get(chunk.id, "") == "unloaded":
			var nearest := Vector2(clampf(target.x, chunk.minX, chunk.maxX), clampf(target.z, chunk.minZ, chunk.maxZ))
			if nearest.distance_to(Vector2(target.x, target.z)) <= view_radius + 20.0:
				classes[chunk.id] = "far"
	var edge_distance := maxf(0.0, 112.0 - maxf(absf(target.x), absf(target.z)))
	classes["edge"] = "fogOnly" if edge_distance <= view_radius + 20.0 else "unloaded"
	canopy.chunk_class = classes
	canopy.update_view(stage.camera, target, zoom)
	last_cull = canopy.last_stats.duplicate()
	if landmarks != null:
		last_cull.landmark_tris = landmarks.update_view(target, zoom, Callable(self, "area_displayed"))
	if water != null:
		water.update_view(Callable(self, "area_displayed"))
		if quarry != null:
			quarry.update_view(Callable(self, "area_displayed"))
	last_cull.select = selected
	last_cull.cull_ms = (Time.get_ticks_usec() - started) / 1000.0


## True when any displayed-clear fog cell lies within `radius` (+ the 3 m blend band) of (x, z).
func area_displayed(x: float, z: float, radius: float) -> bool:
	if displayed_bits.size() != ForestFog.BYTES:
		return true
	var r := radius + 3.0
	var c0 := ForestFog.cell_of(clampf(x - r, -111.9, 111.9), clampf(z - r, -111.9, 111.9))
	var c1 := ForestFog.cell_of(clampf(x + r, -111.9, 111.9), clampf(z + r, -111.9, 111.9))
	if c0.x < 0 or c1.x < 0:
		return false
	for row in range(c0.y, c1.y + 1):
		for column in range(c0.x, c1.x + 1):
			if ForestFog.bit(displayed_bits, column, row):
				return true
	return false


## Fog cull: keep an instance only if it stands on explored ground or inside the 3 m blend band.
const FOG_BAND := 3.0
var fog_cull_stats := {"ms": 0.0, "culled": 0}


func _instance_kept(x: float, z: float) -> bool:
	return fog == null or fog.sdf_at(x, z) >= -FOG_BAND


## Spatial bucketing for the fog cull: a canopy cell whose fog distance samples (3×3, 0.5 m steps) are
## unchanged keeps its previous filtered instances instead of re-testing every one.
func _cell_cull_key(cell: int) -> int:
	if fog == null:
		return 0
	var c: Vector2 = ForestCanopy.cell_center(cell)
	var h := ForestCanopy.CELL * 0.5
	var key := 17
	for dz in [-h, 0.0, h]:
		for dx in [-h, 0.0, h]:
			key = key * 31 + int(round(clampf(fog.sdf_at(c.x + dx, c.y + dz), -40.0, 40.0) * 2.0))
	return key


## Whole 14 m canopy cell kept (1) / culled (-1) / mixed (0), from the SDF at its centre.
func _cell_cull_state(cell: int) -> int:
	if fog == null:
		return 1
	var c: Vector2 = ForestCanopy.cell_center(cell)
	var d: float = fog.sdf_at(c.x, c.y)
	if d >= ForestCanopy.CELL * 0.71 + 1.0:
		return 1
	if d <= -(FOG_BAND + ForestCanopy.CELL * 0.71 + 1.0):
		return -1
	return 0


func _on_fog_target_applied() -> void:
	_apply_fog_cull()
	if canopy != null and stage != null and stage.camera != null:
		on_camera_changed()


func _apply_fog_cull() -> void:
	if canopy == null or fog == null:
		return
	var started := Time.get_ticks_usec()
	canopy.set_cull(Callable(self, "_instance_kept"), Callable(self, "_cell_cull_state"), Callable(self, "_cell_cull_key"))
	fog_cull_stats = {"ms": (Time.get_ticks_usec() - started) / 1000.0, "culled": canopy.culled}


func chunk_explored(id: String) -> bool:
	var parts := id.split("_")
	if parts.size() < 4:
		return false
	var cx := int(parts[2])
	var cz := int(parts[3])
	for row in range(cz * 14, cz * 14 + 14):
		for column in range(cx * 14, cx * 14 + 14):
			if ForestFog.bit(displayed_bits, column, row):
				# The protected town alone does not make an outer chunk "explored".
				var x := -112.0 + column * 4.0 + 2.0
				var z := -112.0 + row * 4.0 + 2.0
				if maxf(absf(x), absf(z)) > 56.0 or (cx in [1, 2] and cz in [1, 2]):
					return true
	return false


func _process(delta: float) -> void:
	_update_occluders(delta)
	_cull_timer -= delta
	if _cull_timer <= 0.0:
		_cull_timer = 0.25
		_cull_fogged_children(_actors)
		_cull_fogged_children(_props)
	_sight_timer -= delta
	if _sight_timer <= 0.0 and not locked:
		_sight_timer = 0.5
		_update_sights()
	_lead_timer -= delta
	if _lead_timer <= 0.0 and not locked:
		_lead_timer = LEAD_STEP
		_update_lead()


## Whole-tree occluder fade: trees whose crown would hide a visible adventure actor or site prop
## from the city camera are drawn faded (forest_occluders.gd). Actors may set the meta
## "occluder_height" (m, default 2.0; props 2.6); "no_canopy_fade" excludes markers/decals.
## Only targets around the camera focus count (ortho view ≈ ±1.1·zoom); from zoom 80 on (overview)
## nothing is faded — the plates mark the units there.
const OCCLUDER_MAX_ZOOM := 80.0


func _update_occluders(delta: float) -> void:
	if occluders == null or stage == null:
		return
	# iPhone hot path: the target list is only gathered when the occluder query is due (every
	# ForestOccluders.UPDATE_SECONDS), into a reused array
	if occluders._timer - delta > 0.0:
		occluders._timer -= delta
		return
	_occluder_targets.clear()
	var zoom: float = stage.camera_zoom
	if zoom <= OCCLUDER_MAX_ZOOM:
		var focus := Vector2(stage.camera_target.x, stage.camera_target.z)
		var reach := zoom * 1.1
		_gather_targets(_actors, 2.0, focus, reach)
		_gather_targets(_props, 2.6, focus, reach)
	occluders.update_targets(_occluder_targets, delta)


var _occluder_targets: Array = []


func _gather_targets(root: Node3D, height: float, focus: Vector2, reach: float) -> void:
	for child in root.get_children():
		if child is Node3D and (child as Node3D).visible and not child.get_meta("no_canopy_fade", false):
			var p: Vector3 = (child as Node3D).global_position
			if Vector2(p.x, p.z).distance_to(focus) <= reach:
				_occluder_targets.append([p, float(child.get_meta("occluder_height", height))])


func _cull_fogged_children(root: Node3D) -> void:
	for child in root.get_children():
		if child is Node3D and not child.get_meta("fog_exempt", false):
			var p: Vector3 = (child as Node3D).global_position
			(child as Node3D).visible = fog_cleared_at(p.x, p.z)


# ============================================================================================
# Adventure state → fog

func apply_adventure(adv: Dictionary) -> void:
	adventure = adv if adv != null else {}
	received_at_ms = Time.get_ticks_msec()
	server_time_ms = float(adventure.get("serverTime", 0.0))
	var access: Dictionary = adventure.get("access", {}) if adventure.get("access") is Dictionary else {}
	locked = adventure.is_empty() or access.get("unlocked", false) != true
	var fog_state: Dictionary = adventure.get("fog", {}) if adventure.get("fog") is Dictionary else {}
	var text: String = String(fog_state.get("visibleBase64", ""))
	var bits := ForestFog.decode_base64(text)
	if bits.is_empty():
		if not text.is_empty():
			push_warning("ForestWorld: invalid fog projection → locked town default (fail closed)")
		bits = ForestFog.default_town_bits()
	_refresh_local_anchors()
	if adventure.is_empty() or (locked and text.is_empty()):
		for i in ForestFog.BYTES:
			bits[i] = bits[i] | anchor_bits[i]
	projection_bits = bits
	fog_revision = int(fog_state.get("revision", fog_revision))
	# Hold the entrance corridor closed until the hall-III intro plays it (or the intro is done).
	var intro: Dictionary = adventure.get("intro", {}) if adventure.get("intro") is Dictionary else {}
	if not locked and not entrance_released and String(intro.get("status", "acknowledged")) != "acknowledged":
		var corridor: Dictionary = atlas.entrance_corridor
		hold_bits = ForestFog.corridor_bits(corridor.from, corridor.to, corridor.radius)
		# 1022: the town square once per call (it was rebuilt for every byte: ~150 ms per state while the
		# intro was pending, on the main thread).
		var town := ForestFog.default_town_bits()
		var shown_now := displayed_bits.size() == ForestFog.BYTES
		for i in ForestFog.BYTES:
			hold_bits[i] = hold_bits[i] & ~town[i] & ~(displayed_bits[i] if shown_now else 0)
	else:
		hold_bits = PackedByteArray()
		if not locked:
			entrance_released = true
	if locked or hold_bits.size() == ForestFog.BYTES:
		lead_bits = PackedByteArray()
	var shown := _shown_bits()
	var key := Marshalls.raw_to_base64(shown) + ("L" if locked else "U")
	if fog != null and key != last_fog_key:
		var first := last_fog_key.is_empty()
		last_fog_key = key
		displayed_bits = shown
		fog.set_dim(0.0 if locked else DIM_EXPLORED)
		fog.set_target(shown, anchor_bits, not first and not reduced_motion)   # → target_applied → cull
	var boss: Dictionary = adventure.get("boss", {}) if adventure.get("boss") is Dictionary else {}
	if boss.has("state"):
		set_boss_arena_state(String(boss.state))
	_update_sights()


## (projection | lead) & ~hold: the fog the player sees.
func _shown_bits() -> PackedByteArray:
	var shown := projection_bits.duplicate()
	var lead := lead_bits.size() == ForestFog.BYTES and shown.size() == ForestFog.BYTES
	var hold := hold_bits.size() == ForestFog.BYTES and shown.size() == ForestFog.BYTES
	if lead or hold:
		for i in shown.size():
			var v := shown[i]
			if lead:
				v = v | lead_bits[i]
			if hold:
				v = v & ~hold_bits[i]
			shown[i] = v
	return shown


func _presentation_now() -> float:
	if clock_source.is_valid():
		return float(clock_source.call())
	return server_time_ms + float(Time.get_ticks_msec() - received_at_ms)


## Build 1024: stamps the lead discs along the running authoritative move (squad / escort walk) up to
## LEAD_AHEAD past the farther of the squad and the mare; dissolves newly lit cells in
## LEAD_REVEAL_SECONDS. Incremental per move (only the stretch walked since the last update).
func _update_lead() -> void:
	if fog == null or locked or hold_bits.size() == ForestFog.BYTES or projection_bits.size() != ForestFog.BYTES:
		return
	var started := Time.get_ticks_usec()
	var now := _presentation_now()
	var squad: Variant = adventure.get("squad")
	var move: Variant = squad.get("move") if squad is Dictionary else null
	if not (move is Dictionary and (move.get("path", []) as Array).size() >= 2):
		# No walk: drop lead cells once the projection holds them (or after LEAD_KEEP_MS regardless).
		if lead_bits.size() == ForestFog.BYTES:
			if _lead_idle_since == 0:
				_lead_idle_since = Time.get_ticks_msec()
			var covered := true
			for i in ForestFog.BYTES:
				if lead_bits[i] & ~projection_bits[i]:
					covered = false
					break
			if covered or Time.get_ticks_msec() - _lead_idle_since > LEAD_KEEP_MS:
				lead_bits = PackedByteArray()
				_lead_move = ""
				if not covered:
					_push_shown(false)
		lead_usec = Time.get_ticks_usec() - started
		return
	_lead_idle_since = 0
	var key := "%s|%s|%s" % [str(move.get("departAt", 0)), str(move.get("arriveAt", 0)), str(move.get("targetId", ""))]
	if key != _lead_move:
		_lead_move = key
		_lead_reach = 0.0
	var path: Array = move.path
	var reach := _path_travel(move, now)
	var horse: Variant = adventure.get("horse")
	if horse is Dictionary and horse.get("visible", false) and horse.get("move") is Dictionary \
			and str(horse.move.get("departAt", 0)) == str(move.get("departAt", 0)):
		reach = maxf(reach, _path_travel(horse.move, now))
	reach += LEAD_AHEAD
	if reach <= _lead_reach + 0.5:
		lead_usec = Time.get_ticks_usec() - started
		return
	if lead_bits.size() != ForestFog.BYTES:
		lead_bits = PackedByteArray()
		lead_bits.resize(ForestFog.BYTES)
	var before := lead_bits.duplicate()
	var from := maxf(0.0, _lead_reach - 1.0)
	var walked := 0.0
	for i in range(1, path.size()):
		var a := Vector2(float(path[i - 1].x), float(path[i - 1].z))
		var b := Vector2(float(path[i].x), float(path[i].z))
		var length := a.distance_to(b)
		if walked + length >= from and walked <= reach:
			var t0 := clampf((from - walked) / maxf(length, 0.0001), 0.0, 1.0)
			var t1 := clampf((reach - walked) / maxf(length, 0.0001), 0.0, 1.0)
			var steps := maxi(1, ceili((t1 - t0) * length / 2.0))
			for k in steps + 1:
				ForestFog.stamp_disc(lead_bits, a.lerp(b, lerpf(t0, t1, float(k) / steps)), LEAD_RADIUS)
		walked += length
		if walked > reach:
			break
	_lead_reach = reach
	var grows := false
	for i in ForestFog.BYTES:
		if lead_bits[i] & ~before[i] & ~projection_bits[i]:
			grows = true
			break
	if grows:
		_push_shown(true)
	lead_usec = Time.get_ticks_usec() - started


## Distance (m) travelled along a server move's path at `now` (same timing as _move_position).
func _path_travel(move: Dictionary, now: float) -> float:
	var path: Array = move.get("path", [])
	var total := 0.0
	for i in range(1, path.size()):
		total += Vector2(float(path[i].x) - float(path[i - 1].x), float(path[i].z) - float(path[i - 1].z)).length()
	var depart := float(move.get("departAt", now))
	var arrive := float(move.get("arriveAt", now))
	return clampf((now - depart) / maxf(1.0, arrive - depart), 0.0, 1.0) * total


func _push_shown(lead_reveal: bool) -> void:
	var shown := _shown_bits()
	var key := Marshalls.raw_to_base64(shown) + "U"
	if key == last_fog_key:
		return
	last_fog_key = key
	displayed_bits = shown
	fog.set_target(shown, anchor_bits, not reduced_motion, LEAD_REVEAL_SECONDS if lead_reveal else ForestFog.REVEAL_SECONDS)


func _refresh_local_anchors() -> void:
	anchor_bits = ForestFog.default_town_bits()
	if data.is_empty():
		return
	var city: Dictionary = city_state
	if city.is_empty() and stage != null:
		return
	# Property outside the square: prepared tree sites and their buildings, active felling.
	var plots: Dictionary = {}
	for plot in data.get("plots", []) + data.get("legacyPlots", []):
		plots[plot.id] = plot
	var progress: Dictionary = city.get("progress", {})
	for id in progress.get("sites", []):
		var plot: Variant = data.treePlots.get(id)
		if plot is Dictionary:
			plots[plot.id] = plot
			_stamp_property(Vector2(float(plot.x), float(plot.z)), 7.0)
	for building in city.get("buildings", []):
		var plot: Variant = plots.get(building.get("plotId", ""))
		if plot is Dictionary:
			_stamp_property(Vector2(float(plot.x), float(plot.z)), 7.0)
	var job: Variant = progress.get("job")
	if job is Dictionary and job.get("id") is String:
		var p := resource_tree_position(job.id)
		if p != Vector3.INF:
			_stamp_property(Vector2(p.x, p.z), 4.0)


func _stamp_property(p: Vector2, half: float) -> void:
	if maxf(absf(p.x), absf(p.y)) <= 56.0 - half:
		return
	var x := p.x - half
	while x <= p.x + half:
		var z := p.y - half
		while z <= p.y + half:
			var cell := ForestFog.cell_of(x, z)
			ForestFog.set_bit(anchor_bits, cell.x, cell.y)
			z += 2.0
		x += 2.0


## Optional presentation clock (gameplay layer: client.server_now) so the sight circles stay
## on the actors when the clock is driven per frame (fixed-fps movies); real time otherwise.
var clock_source := Callable()


func _update_sights() -> void:
	if fog == null:
		return
	var points: Array = []
	if not locked:
		var now := server_time_ms + float(Time.get_ticks_msec() - received_at_ms)
		if clock_source.is_valid():
			now = float(clock_source.call())
		for actor in ["squad", "horse"]:
			var block: Variant = adventure.get(actor)
			if block is Dictionary and (actor != "horse" or block.get("visible", false)):
				var p := _actor_position(block, now)
				if p != Vector3.INF:
					points.append(Vector4(p.x, p.z, SIGHT_RADIUS, 1.0))
		var escort: Variant = adventure.get("escort")
		if escort is Dictionary and escort.get("move") is Dictionary:
			var p := _move_position(escort.move, now)
			if p != Vector3.INF:
				points.append(Vector4(p.x, p.z, SIGHT_RADIUS, 1.0))
	for extra in extra_sights:
		points.append(extra)
	fog.set_sights(points)


func _actor_position(block: Dictionary, now: float) -> Vector3:
	if block.get("move") is Dictionary:
		var p := _move_position(block.move, now)
		if p != Vector3.INF:
			return p
	var node := String(block.get("node", ""))
	return poi_position(node) if not node.is_empty() else Vector3.INF


func _move_position(move: Dictionary, now: float) -> Vector3:
	var path: Array = move.get("path", [])
	if path.is_empty():
		return Vector3.INF
	var depart := float(move.get("departAt", now))
	var arrive := float(move.get("arriveAt", now))
	var f := clampf((now - depart) / maxf(1.0, arrive - depart), 0.0, 1.0)
	var total := 0.0
	var lengths: Array = [0.0]
	for i in range(1, path.size()):
		total += Vector2(float(path[i].x) - float(path[i - 1].x), float(path[i].z) - float(path[i - 1].z)).length()
		lengths.append(total)
	var travelled := f * total
	for i in range(1, path.size()):
		if travelled <= lengths[i] or i == path.size() - 1:
			var seg: float = maxf(0.0001, lengths[i] - lengths[i - 1])
			var w := clampf((travelled - lengths[i - 1]) / seg, 0.0, 1.0)
			return Vector3(lerpf(float(path[i - 1].x), float(path[i].x), w), 0.0, lerpf(float(path[i - 1].z), float(path[i].z), w))
	return Vector3(float(path[0].x), 0.0, float(path[0].z))


# ============================================================================================
# WORLD_API

func is_locked() -> bool:
	return locked


func height_at(x: float, z: float) -> float:
	return terrain.height_at(x, z) if terrain != null else ForestTerrain.base_height(x, z)


func ground_point(x: float, z: float) -> Vector3:
	return Vector3(x, height_at(x, z), z)


func site_anchor(site_id: String) -> Dictionary:
	var site: Dictionary = atlas.site_by_id.get(site_id, {})
	if site.is_empty():
		return {}
	var c: Vector3 = site.center
	var at := func(offset: Vector2) -> Vector3: return ground_point(c.x + offset.x, c.z + offset.y)
	var cage: Vector2 = site.cage
	var approach: Vector2 = site.approach
	var artifact: Vector2 = site.artifact
	var side := 2.6 * (1.0 if artifact.x <= 0.0 else -1.0)
	var symbols := {}
	var index := 0
	for angle in [0.35, 1.45, 2.55, 3.65, 4.75, 5.85]:
		var ring: Vector2 = Vector2(cos(angle + c.x * 0.01), sin(angle + c.z * 0.01)) * (site.radius - 1.2)
		symbols["symbol_%d" % index] = at.call(ring)
		index += 1
	var facing := approach - cage
	return {"center": ground_point(c.x, c.z), "cage": at.call(cage), "guardian": at.call(site.guardian),
		"artifact": at.call(artifact), "approach": at.call(approach),
		"plate_left": at.call(cage + Vector2(-side, 2.4)), "plate_right": at.call(cage + Vector2(side, 2.4)),
		"landmarks": symbols, "cage_yaw": atan2(facing.x, facing.y), "radius": site.radius}


func poi_position(target_id: String) -> Vector3:
	if target_id == "lf_horse_origin":
		return ground_point(atlas.horse_origin.x, atlas.horse_origin.z)
	if target_id == "lf_home_reception":
		return ground_point(atlas.HOME_RECEPTION.x, atlas.HOME_RECEPTION.y)
	if target_id == "lf_bridge_crossing":
		return Vector3(atlas.BRIDGE_CENTER.x, atlas.BRIDGE_DECK_Y, atlas.BRIDGE_CENTER.z)
	if target_id == "lf_boss_ancient_maw" or target_id == "lf_boss_arena":
		return ground_point(atlas.arena_center.x, atlas.arena_center.z)
	if target_id.begins_with("lf_key_"):
		var anchor := site_anchor("lf_site_" + target_id.trim_prefix("lf_key_"))
		return anchor.get("artifact", Vector3.INF)
	if atlas.landmark_by_id.has(target_id):        # atlas v2 waypoints: junctions, marks, lf_glade_el
		var node: Dictionary = atlas.landmark_by_id[target_id]
		return ground_point(float(node.center.x), float(node.center.z))
	var parts := target_id.split(":")
	var anchor := site_anchor(parts[0])
	if anchor.is_empty():
		return Vector3.INF
	if parts.size() == 1:
		return anchor.center
	return anchor.get(parts[1], Vector3.INF)


## v3.3: a server move path ({x,y,z} points) as the drawn, meandered trail (densified); actors
## walk this polyline so they stay on the visual trail (same arc-length fraction / timing).
func visual_path(path: Array) -> Array:
	return atlas.visual_path(path) if atlas != null else path


## WORLD_API v3.3 (atlas v2): the drawn trail (terrain-profile heights) from one atlas node to
## another over the trail network (ForestAtlas.trail_legs: shortest, no transit through another
## site's glade). Accepts CONTRACT ids: lf_key_NN / lf_site_NN:* → their glade, lf_boss_ancient_maw
## → the arena, lf_home_reception → the horse origin. Empty when unknown or unreachable.
func trail_path(from_id: String, to_id: String) -> PackedVector3Array:
	var a := atlas_node_of(from_id)
	var b := atlas_node_of(to_id)
	var out := PackedVector3Array()
	if a.is_empty() or b.is_empty():
		return out
	for leg in atlas.trail_legs(a, b):
		var points := route_points(String(atlas.routes[leg[0]].id))
		if not leg[1]:
			points.reverse()
		var start := 1 if not out.is_empty() else 0
		for i in range(start, points.size()):
			out.append(points[i])
	return out


## Atlas node of a CONTRACT target id ("" when it has none).
func atlas_node_of(target_id: String) -> String:
	var base := target_id.get_slice(":", 0).get_slice("#", 0)
	if base.begins_with("lf_key_"):
		base = "lf_site_" + base.trim_prefix("lf_key_")
	match base:
		"lf_boss_ancient_maw":
			base = "lf_boss_arena"
		"lf_home_reception":
			base = "lf_horse_origin"
	if atlas.site_by_id.has(base) or atlas.landmark_by_id.has(base):
		return base
	return ""


## Build 1024: the entrance corridor of the fog (atlas; fog.mjs ENTRANCE_CORRIDOR) {from, to, radius}.
func entrance_corridor_spec() -> Dictionary:
	return atlas.entrance_corridor if atlas != null else {}


## WORLD_API v3.3: the arena's entrance yaw (deg, atlas entranceYawDeg; the gap faces the trail).
func arena_entrance_yaw_deg() -> float:
	return atlas.arena_yaw_deg


func route_points(route_id: String) -> PackedVector3Array:
	var route: Dictionary = atlas.route_by_id.get(route_id, {})
	if route.is_empty():
		return PackedVector3Array()
	var index: int = atlas.routes.find(route)
	var points: PackedVector3Array = route.points.duplicate()
	var profile: PackedFloat32Array = terrain.road_profiles[index]
	for i in points.size():
		points[i].y = profile[i]
	return points


func actors_root() -> Node3D:
	return _actors


func props_root() -> Node3D:
	return _props


func fog_cleared_at(x: float, z: float) -> bool:
	var cell := ForestFog.cell_of(x, z)
	if cell.x < 0:
		return false
	return (ForestFog.bit(projection_bits, cell.x, cell.y) or ForestFog.bit(lead_bits, cell.x, cell.y)) and not ForestFog.bit(hold_bits, cell.x, cell.y)


func play_entrance_reveal(duration_ms: int) -> void:
	if locked:
		push_warning("ForestWorld: entrance reveal ignored while the forest is locked")
		return
	entrance_released = true
	hold_bits = PackedByteArray()
	var shown := projection_bits.duplicate()
	var key := Marshalls.raw_to_base64(shown) + "U"
	last_fog_key = key
	displayed_bits = shown
	fog.set_target(shown, anchor_bits, not reduced_motion, duration_ms / 1000.0)
	_apply_fog_cull()
	if canopy != null and stage != null and stage.camera != null:
		on_camera_changed()


func set_reduced_motion(on: bool) -> void:
	reduced_motion = on
	if fog != null:
		fog.set_reduced_motion(on)


func pin_area(id: String, center: Vector3, radius: float) -> void:
	pinned[id] = {"center": center, "radius": radius}
	on_camera_changed()


func unpin_area(id: String) -> void:
	pinned.erase(id)
	on_camera_changed()


func focus_bounds() -> Rect2:
	return Rect2(-112.0, -112.0, 224.0, 224.0)


func set_boss_arena_state(state: String) -> void:
	if not state in ["locked", "available", "active", "defeated"]:
		return
	arena_state = state
	if landmarks != null:
		landmarks.apply_arena_state(state)


func set_site_post_state(site_id: String, step: int) -> void:
	site_steps[site_id] = step
	if landmarks != null:
		landmarks.apply_site_state(site_id, step)


func perf_snapshot() -> Dictionary:
	var select: Dictionary = last_cull.get("select", {})
	return {"full_chunks": select.get("full", []).size(), "proxy_chunks": select.get("proxy", []).size(),
		"fog_only_chunks": select.get("fogOnly", []).size(), "overflow": select.get("overflow", 0),
		"instances": last_cull.get("instances", 0), "tris_est": last_cull.get("tris_est", 0),
		"lod0": last_cull.get("lod0", 0), "lod1": last_cull.get("lod1", 0), "lod2": last_cull.get("lod2", 0),
		"batches": last_cull.get("batches", 0), "uploads": canopy.uploads if canopy != null else 0,
		"landmark_tris": last_cull.get("landmark_tris", 0), "fog_culled": fog_cull_stats.culled,
		"fog_cull_ms": fog_cull_stats.ms,
		"cull_ms": last_cull.get("cull_ms", 0.0), "build_ms": last_cull.get("build_ms", 0.0),
		"fog_shells": fog.shells.size() if fog != null else 0, "setup_ms": setup_ms.duplicate()}


# ---- additive API (v2, see WORLD_API.md changelog) ----------------------------------------

## Smooth fly-to using the existing city camera interpolation (no new camera mode).
func focus_on(position: Vector3, zoom := -1.0) -> void:
	stage.target = Vector3(clampf(position.x, -112.0, 112.0), position.y, clampf(position.z, -112.0, 112.0))
	if zoom > 0.0:
		stage.zoom = clampf(zoom, 24.0, 120.0)


func focus_site(site_id: String, zoom := 42.0) -> void:
	var anchor := site_anchor(site_id)
	if not anchor.is_empty():
		focus_on(anchor.center, zoom)


func focus_entrance(zoom := 46.0) -> void:
	var c: Dictionary = atlas.entrance_corridor
	var mid: Vector2 = (c.from + c.to) * 0.5
	focus_on(ground_point(mid.x, mid.y), zoom)


## Extra sight circles [Vector4(x, z, radius, strength)] (e.g. a battle the player watches).
func set_sight_points(points: Array) -> void:
	extra_sights = points.duplicate()
	_update_sights()


func kit_status() -> Dictionary:
	var status: Dictionary = kit.kit_status() if kit != null else {}
	status.landmarks_missing = landmarks.missing.duplicate() if landmarks != null else {}
	status.landmarks_loaded = landmarks.loaded.duplicate() if landmarks != null else {}
	return status


func layout_info() -> Dictionary:
	return {"layoutId": layout.get("layoutId", ""), "layoutVersion": layout.get("layoutVersion", 0),
		"seed": layout.get("seed", 0), "remapStats": layout.get("remapStats", {}), "apiVersion": API_VERSION,
		"flag": ForestFlags.FLAG_ID, "flagVersion": ForestFlags.FLAG_VERSION}
