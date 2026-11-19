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
const SUN_ROTATION := Vector3(-0.837758, -0.558505, 0.0)   # landscape.gd city sun (-48°, -32°, 0)
const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")
const PATH_SHADER = preload("res://src/forest_rescue/world/forest_path.gdshader")
const SURFACES := "res://assets/city/premium/surfaces07/"

const API_VERSION := 3
const DIM_EXPLORED := 0.14
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
var remap: Dictionary = {}               # resource id -> Vector2 (visual position, layout)
var resource_look: Dictionary = {}       # resource id -> [kit variant, absolute scale]
var visual_pos: Dictionary = {}          # resource id -> Vector2 actually rendered (last build)
var mesh_keys: Dictionary = {}
var city_state: Dictionary = {}
var arena_state := "locked"
var site_steps: Dictionary = {}
var impostors: Node
var _fade_key := ""
var _fade_timer := 0.0
var _cull_timer := 0.0
var _sight_timer := 0.0


# ============================================================================================
# Construction

func setup(owner: Node3D, ground_meshes: Array) -> void:
	var started := Time.get_ticks_usec()
	stage = owner
	data = owner.data
	name = "ForestWorld"
	_actors.name = "AdventureActors"
	_props.name = "SiteProps"
	add_child(_actors)
	add_child(_props)
	atlas = _cache.get("atlas")
	if atlas == null:
		atlas = ForestAtlas.load_default()
		_cache.atlas = atlas
	layout = _cache.get("layout", {})
	if layout.is_empty():
		layout = _load_layout()
		_cache.layout = layout
	for section in ["resourceRemap", "innerRemap"]:
		for id in layout.get(section, {}):
			var entry: Array = layout[section][id]
			remap[id] = Vector2(float(entry[0]), float(entry[1]))
			if entry.size() >= 5:
				resource_look[id] = [int(entry[3]), float(entry[4])]
	masks = _cache.get("masks")
	if masks == null:
		masks = ForestMasks.MaskSet.new(8.0)
		for mask in atlas.static_masks():
			masks.add(mask)
		_cache.masks = masks
	setup_ms.data = (Time.get_ticks_usec() - started) / 1000.0
	# Landmarks first: their pads take part in the terrain bake.
	landmarks = ForestLandmarks.new()
	landmarks.name = "Landmarks"
	add_child(landmarks)
	landmarks.plan(atlas, masks, func(x: float, z: float) -> float: return ForestTerrain.base_height(x, z))
	var t := Time.get_ticks_usec()
	var key := "terrain_v%d_%s" % [ForestTerrain.TERRAIN_VERSION, atlas.atlas_id]
	terrain = _cache.get(key)
	if terrain == null:
		terrain = ForestTerrain.new(atlas)
		terrain.extra_pads = landmarks.pads()
		var source_meshes: Array = []
		for part: MeshInstance3D in ground_meshes:
			source_meshes.append(part.mesh)
		terrain.read_tiles(source_meshes)
		await get_tree().process_frame
		terrain.bake()
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
			part.mesh = rebuilt
		if Time.get_ticks_usec() - slice > 4000:
			await get_tree().process_frame
			slice = Time.get_ticks_usec()
	_cache.tiles = tiles
	setup_ms.tiles = (Time.get_ticks_usec() - t) / 1000.0
	t = Time.get_ticks_usec()
	ForestKit.light_dir = Basis.from_euler(SUN_ROTATION).z.normalized()
	kit = ForestKit.new(data, stage.scenery_material)
	canopy = ForestCanopy.new()
	canopy.name = "Canopy"
	add_child(canopy)
	_build_paths()
	impostors = ForestImpostors.new()
	impostors.name = "Impostors"
	add_child(impostors)
	var bake_list: Array = []
	for species in Rules.SPECIES.size():
		for variant in Rules.SPECIES_VARIANTS[species]:
			var mesh := _tree_mesh(species, variant)
			bake_list.append([mesh[2], canopy.meshes[mesh[0]].lods[0]])
	var signature := ""
	for file in DirAccess.get_files_at(ForestKit.KIT_DIR):
		if file.ends_with(".glb"):
			signature += "%s:%d;" % [file, FileAccess.get_modified_time(ForestKit.KIT_DIR + file)]
	for entry in bake_list:
		signature += String(entry[0]) + ";"
	await impostors.bake(bake_list, SUN_ROTATION, stage.camera.environment, signature)
	canopy.impostors = impostors
	setup_ms.impostors = (Time.get_ticks_usec() - t) / 1000.0
	fog = ForestFog.new()
	fog.name = "Fog"
	add_child(fog)
	var light: Vector3 = -stage.shadow_direction if stage.shadow_direction != Vector3.ZERO else Vector3(0.45, 0.74, 0.5)
	fog.build(func(x: float, z: float) -> float: return terrain.ground_height(x, z), light)
	fog.reveal_finished.connect(func() -> void: fog_reveal_finished.emit(fog_revision))
	landmarks.populate()
	_register_fog_receivers()
	setup_ms.visuals = (Time.get_ticks_usec() - t) / 1000.0
	apply_adventure({})
	setup_ms.total = (Time.get_ticks_usec() - started) / 1000.0
	set_process(true)
	ready_for_frame = true
	print("ForestWorld: ready ", setup_ms, " kit=", kit.kit_status().missing.size(), " missing kit assets")


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
	var half := 1.45
	var fringe := 0.9
	for r in atlas.routes.size():
		var points: PackedVector3Array = atlas.routes[r].points
		var on_deck: PackedByteArray = terrain.road_on_deck[r]
		var profile: PackedFloat32Array = terrain.road_profiles[r]
		var run_start := -1
		for i in points.size():
			var p := points[i]
			var skip := on_deck[i] == 1 or maxf(absf(p.x), absf(p.z)) < 56.0
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
	var adv: Variant = state.get("adventure", {})
	var key := JSON.stringify(adv) if adv is Dictionary else "{}"
	if key == _last_hint:
		return
	_last_hint = key
	apply_adventure(adv if adv is Dictionary else {})


var _last_hint := ""


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


func _tree_mesh(species: int, variant: int) -> Array:
	var id: String = Rules.SPECIES[species]
	var variants: Array = Rules.SPECIES_VARIANTS[species]
	var v: int = variant if variants.has(variant) else int(variants[(maxi(variant, 1) - 1) % variants.size()])
	return _mesh_for(kit.tree_asset(id), "tree:%s:v%d" % [id, v], ForestCanopy.KIND_TREE, v, "v%d" % v)


func _under_mesh(kind_index: int, variant: int) -> Array:
	var kind: String = Rules.UNDERSTORY[clampi(kind_index, 0, Rules.UNDERSTORY.size() - 1)]
	var spec: Array = Rules.UNDERSTORY_KIT[kind]
	var names: Array = spec[1]
	var variant_name: String = names[(maxi(variant, 1) - 1) % names.size()]
	var canopy_kind := ForestCanopy.KIND_ROCK if kind in Rules.LARGE_UNDERSTORY else ForestCanopy.KIND_UNDER
	return _mesh_for(kit.understory_asset(kind, spec[0]), "under:%s:%s" % [kind, variant_name], canopy_kind, 1, variant_name)


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


func build_city_forest(city: Dictionary, exclusions: Array) -> void:
	var started := Time.get_ticks_usec()
	city_state = city
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
	for tree in data.woods:
		if tree.village and not kingdom:
			continue
		# Pickable set exactly as the legacy forest (decided on the original spot); the visual
		# slot falls back to the original spot when the player's property covers it.
		var original := Vector2(float(tree.p[0]), float(tree.p[2]))
		if _excluded(original, exclusions) or stage.on_street(original, 1.5):
			continue
		var xz := _tree_xz(tree)
		if xz != original and (_excluded(xz, exclusions) or stage.on_street(xz, 1.5)):
			xz = original
		visual_pos[tree.id] = xz
		var y := height_at(xz.x, xz.y)
		var entry: Dictionary = tree.duplicate()
		entry.p = [xz.x, y, xz.y]
		stage.selectable_trees.append(entry)
		if felled.has(tree.id):
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
	for item in layout.get("trees", []):
		var xz := Vector2(float(item[0]), float(item[1]))
		if _excluded(xz, exclusions):
			continue
		var mesh := _tree_mesh(int(item[2]), int(item[3]))
		var scale := float(item[5])
		var transform := Transform3D(Basis(Vector3.UP, deg_to_rad(float(item[4]))).scaled(Vector3.ONE * scale),
			Vector3(xz.x, height_at(xz.x, xz.y) - 0.05, xz.y))
		canopy.add_instance(mesh[0], transform)
		_add_impostor(mesh, transform.origin, deg_to_rad(float(item[4])), scale)
	for list_name in ["understory", "innerUnderstory"]:
		var inner: bool = list_name == "innerUnderstory"
		for item in layout.get(list_name, []):
			var xz := Vector2(float(item[0]), float(item[1]))
			if _excluded(xz, exclusions) or (inner and stage.on_street(xz, 1.7)):
				continue
			var mesh := _under_mesh(int(item[2]), int(item[3]))
			var y := height_at(xz.x, xz.y)
			var basis := Basis(Vector3.UP, deg_to_rad(float(item[4]))).scaled(Vector3.ONE * float(item[5]))
			canopy.add_instance(mesh[0], Transform3D(basis, Vector3(xz.x, y - 0.03, xz.y)))
	_refresh_local_anchors()
	_register_fog_receivers()
	_apply_fog_cull()
	last_cull.build_ms = (Time.get_ticks_usec() - started) / 1000.0
	if stage.camera != null and stage.camera.is_inside_tree():
		on_camera_changed()
	call_deferred("_emit_ready_once")


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


func _apply_fog_cull() -> void:
	if canopy == null or fog == null:
		return
	var started := Time.get_ticks_usec()
	canopy.set_cull(Callable(self, "_instance_kept"), Callable(self, "_cell_cull_state"))
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
	_fade_timer -= delta
	if _fade_timer <= 0.0:
		_fade_timer = 0.15
		_update_fade_circles()
	_cull_timer -= delta
	if _cull_timer <= 0.0:
		_cull_timer = 0.25
		_cull_fogged_children(_actors)
		_cull_fogged_children(_props)
	_sight_timer -= delta
	if _sight_timer <= 0.0 and not locked:
		_sight_timer = 0.5
		_update_sights()


## Canopy fade around adventure actors and pinned areas (crowns dither away above 1.2 m).
func _update_fade_circles() -> void:
	var circles: Array = []
	for child in _actors.get_children():
		if child is Node3D and (child as Node3D).visible and not child.get_meta("no_canopy_fade", false):
			var p: Vector3 = (child as Node3D).global_position
			circles.append(Vector4(p.x, p.y, p.z, float(child.get_meta("canopy_fade_radius", 6.5))))
	for id in pinned:
		var area: Dictionary = pinned[id]
		var c: Vector3 = area.center
		circles.append(Vector4(c.x, height_at(c.x, c.z), c.z, maxf(4.0, float(area.radius))))
	var key := str(circles)
	if key == _fade_key:
		return
	_fade_key = key
	ForestKit.set_fade_circles(circles, [impostors.material] if impostors != null and impostors.material != null else [])


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
		for i in ForestFog.BYTES:
			hold_bits[i] = hold_bits[i] & ~ForestFog.default_town_bits()[i] & ~(displayed_bits[i] if displayed_bits.size() == ForestFog.BYTES else 0)
	else:
		hold_bits = PackedByteArray()
		if not locked:
			entrance_released = true
	var shown := bits.duplicate()
	if hold_bits.size() == ForestFog.BYTES:
		for i in ForestFog.BYTES:
			shown[i] = shown[i] & ~hold_bits[i]
	var key := Marshalls.raw_to_base64(shown) + ("L" if locked else "U")
	if fog != null and key != last_fog_key:
		var first := last_fog_key.is_empty()
		last_fog_key = key
		displayed_bits = shown
		fog.set_target(shown, anchor_bits, not first and not reduced_motion)
		fog.set_dim(0.0 if locked else DIM_EXPLORED)
		_apply_fog_cull()
		if canopy != null and stage != null and stage.camera != null:
			on_camera_changed()
	var boss: Dictionary = adventure.get("boss", {}) if adventure.get("boss") is Dictionary else {}
	if boss.has("state"):
		set_boss_arena_state(String(boss.state))
	_update_sights()


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


func _update_sights() -> void:
	if fog == null:
		return
	var points: Array = []
	if not locked:
		var now := server_time_ms + float(Time.get_ticks_msec() - received_at_ms)
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
	var parts := target_id.split(":")
	var anchor := site_anchor(parts[0])
	if anchor.is_empty():
		return Vector3.INF
	if parts.size() == 1:
		return anchor.center
	return anchor.get(parts[1], Vector3.INF)


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
	return ForestFog.bit(projection_bits, cell.x, cell.y) and not ForestFog.bit(hold_bits, cell.x, cell.y)


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
