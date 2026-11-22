extends Node3D

const WarriorVisual = preload("res://src/warrior_visual.gd")
var fallen_bodies: Array = []
var combat_view = preload("res://src/combat_presentation.gd").new()
var combat_audio = preload("res://src/combat_audio.gd").new()
var foot_contacts = preload("res://src/foot_contacts.gd").new()
var combat_debug: Node3D
var next_combat_debug_ms := 0

const SURFACES := "res://assets/city/premium/surfaces07/"
const CAMERA_RESPONSE := 22.0
const WORLD_CAMERA_TILT := 0.88
const BATCH_CELL_SIZE := 18.0
const TOWN_DETAIL_ZOOM := 135.0
const TOWN_DETAIL_RADIUS := 58.0
const CANOPY_OVERVIEW_ZOOM := 210.0
const CITY_TREE_CELL_SIZE := 12.0
const ACTOR_CACHE_SECONDS := 10.0
const MAX_HIDDEN_CREATURES := 8
const MAX_HIDDEN_ARMIES := 3
const WATER_SHADER = preload("res://src/water.gdshader")
const BIOME_SHADER = preload("res://src/biome.gdshader")
const MEADOW_SHADER = preload("res://src/meadow.gdshader")
const FOREST_SHADER = preload("res://src/forest.gdshader")
const CityWorks = preload("res://src/city_works.gd")
const CityWalls = preload("res://src/city_walls.gd")
const TownPlan = preload("res://src/town_plan.gd")
const TownGround = preload("res://src/town_ground.gd")
const TOWN_LOTS := "res://assets/city/town_lots.json"
# B18 gate scenes are authored at plot scale; in the city wall they stand larger so
# the carriageway and towers match the height of the ring curtain.
const GATE_SCENE_SCALES := [1.9, 2.0, 2.0, 2.1, 2.2]
const GATE_SCENE_HALF_SPAN := 5.9

static func gate_scene_scale(level: int) -> float:
	if level >= 6:
		return 1.0
	return GATE_SCENE_SCALES[clampi(level, 1, 5) - 1]
var works := CityWorks.new()
# The second worker's crew (workers-v1: a second worker from «Жилой дом» III).
var works2 := CityWorks.new()
var walls := CityWalls.new()
# Yards, streets and their dressing (build 52): see src/town_plan.gd.
var town_plan := TownPlan.new()
var town := TownGround.new()
var town_lots: Dictionary = {}
var town_rebuilds := 0
var forest_materials := {}
var focus_radius := 0.0
var focus_centre := Vector3.ZERO
var focus_core := Vector3.ZERO
var focus_core_radius := 0.0
var fight_positions := {}
# Hunts with battle places: the ground the crowd needs cleared of trees (metres).
var fight_cores := {}
var announced_fights := {}
signal fight_started(army_id: String, position: Vector3)
const Formations = preload("res://src/formations.gd")
# [forest_rescue_v1 hook] versioned world layer flag; OFF = legacy forest (rollback).
const ForestFlags = preload("res://src/forest_rescue/world/forest_flags.gd")
var forest_world: Node3D = null
var forest_attach_state := ""   # "", "attaching", "attached", "failed", "off" (1022 lazy world layer)
var forest_last_city: Dictionary = {}
var forest_last_state: Dictionary = {}
var forest_last_exclusions: Array = []
var city_ground_meshes: Array = []
const GaitTable = preload("res://src/gait_table.gd")
const CombatSlots = preload("res://src/combat_slots.gd")
const MarchLanes = preload("res://src/march_lanes.gd")
# Presentation paths of the marching columns (march_lanes.gd), one plan at a time.
var lanes := MarchLanes.new()
var lane_queue: Array = []
var lane_busy := false
# How far a lane may leave the server's route (m): the world map's soldiers are smaller.
const LANE_CORRIDOR := 8.0
# The main gate scene of the wall (march_lanes: its passage is the way out).
var gate_node: Node3D
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
# Size of a field soldier (march and hunt) on each map. Up to build 1020 both maps
# drew every soldier at 1.15: 2.0-2.2 m on foot, 3.1-3.3 m mounted (measured from
# the GLB models, godot/tools/measure_field_scale.gd). In the city that is larger
# than the same soldiers on the parade ground and at the barracks (1.0). On the
# world map, whose houses are 1.0-1.65 m and trees 3.6-3.9 m tall, a soldier stood
# taller than a house, a rider twice as tall, and a hunting party around a 6.7-8.5 m
# Velkor covered more ground than a whole village.
const FIELD_UNIT_SCALE := 1.0 # city, the same as the parade ground and the barracks
const WORLD_UNIT_SCALE := 0.5 # world map: 0.9-1.0 m on foot, 1.4 m mounted
# A Velkor I 4.0 m tall, a III 5.1 m: a forest giant as tall as the trees (the crowns
# around a world creature fade, creature_clear).
const WORLD_CREATURE_SCALE := 0.6
# The column, the crowd around a creature, the collision boxes of the battle places
# and the run speeds were laid out for soldiers at this scale; they follow the size
# of the soldiers (unit_k) and of the creature (beast_k) on each map.
const LAYOUT_UNIT_SCALE := 1.15
var unit_scale := FIELD_UNIT_SCALE
var unit_k := FIELD_UNIT_SCALE / LAYOUT_UNIT_SCALE
var beast_k := 1.0
# Slowest walk tempo and fastest run tempo; between them feet match exactly.
const WALK_TEMPO := Vector2(0.55, 0.0)
const RUN_TEMPO := Vector2(0.0, 1.6)
# A half-size soldier keeps the server's march speed (3-4 m/s) with quicker steps
# instead of sliding: on the world map the run may play up to this tempo.
const WORLD_RUN_TEMPO := 2.5
var run_tempo_max := RUN_TEMPO.y
const MARCH_LINE := preload("res://src/fx_march.gdshader")
const PLOT_GLOW := preload("res://src/plot_glow.gdshader")
const PLACEMENT_GHOST := preload("res://src/placement_ghost.gdshader")
# Creature bodies at scale 1, measured from the GLB models: half length (the head
# is at +X) and half width. Battle places hug this outline.
const CREATURE_BODY := {"velkor": Vector2(2.51, 1.19), "tenerys": Vector2(2.63, 0.69),
	"kamneklyk": Vector2(2.62, 1.04), "dragor": Vector2(3.15, 1.07)}
# Creature models look along +X; headings (atan2(dx, dz)) look along +Z.
const CREATURE_YAW := -PI * 0.5
# Gap between the melee arc and the creature's body.
const ENGAGE_GAP := 0.8
# Run speed of soldiers going from the column to their battle places (m/s).
const CHARGE_SPEED := 3.6
const CHARGE_MAX_RUN := 8.0
const CHARGE_MAX_RIDE := 11.0
const ROAR_MS := 1600.0
const REGROUP_MS := 1400.0
# Running speeds back to the column after a hunt (m/s) and the longest regroup.
const REGROUP_RUN := 4.5
const REGROUP_RIDE := 7.0
const REGROUP_MAX_MS := 8000.0
# Per-frame budget for refining a hunt's contact places while the column walks.
const ENGAGE_SLICE_USEC := 2500
# A moving target is re-planned only after it has left this radius.
const ENGAGE_REPLAN_M := 3.0
# Tools and tests that read a finished plan right after engage_plan().
var engage_sync := false
# How long the slain creature stays on the field after the army leaves.
const CORPSE_MS := 4500.0
const MELEE_SWING_MS := 1700.0
var data: Dictionary
var map_name := "city"
var world_heights := PackedFloat32Array()
var actors := Node3D.new()
var battle_fx := BattleFx.new()
var creatures := Node3D.new()
var buildings := Node3D.new()
var training := Node3D.new()
var camera := Camera3D.new()
var target := Vector3.ZERO
var zoom := 68.0
var camera_target := Vector3.ZERO
var camera_zoom := 68.0
var world_yaw := 0.0
var camera_yaw := 0.0
var last_cull_target := Vector3.INF
var last_cull_zoom := 0.0
var last_cull_yaw := 0.0
var camera_dirty := false
var last_cull_ms := 0.0
var uploaded_transform_bytes := 0
var models: Dictionary = {}
var trees: Dictionary = {}
var geometries: Dictionary = {}
var army_routes: Dictionary = {}
var place_markers: Array[Dictionary] = []
var empty_plots: Array[Dictionary] = []
var render_batches: Array[Dictionary] = []
var shadow_direction := Vector3.ZERO
var terrain_bounds := AABB()
var route_preview: MeshInstance3D
var scenery := Node3D.new()
var city_ground_detail := Node3D.new()
var scenery_material: StandardMaterial3D
var meadow_material: ShaderMaterial
var meadow_stone: StandardMaterial3D
var city_road_mesh: MeshInstance3D
var city_streets: Array = []
var resource_layer := true
var detail_layer := true
var selectable_trees: Array = []
var standing_tree_cells: Dictionary = {}
var parade := Node3D.new()
var workers := Node3D.new()
var parade_center := Vector3.ZERO
var parade_slots: Array[Dictionary] = []
var army_markers: Array[Dictionary] = []
var creature_markers: Array[Dictionary] = []
var patrol_routes: Dictionary = {}
var effects := Node3D.new()
var march_lines := Node3D.new()
var shaft_mesh: CylinderMesh
var vegetation_rebuilds := 0
var ground_rebuilds := 0
var city_nodes_created := 0
var static_heights: Dictionary = {}
# Trees that survive the exclusion and street filters for the current ground signature.
var eligible_trees: Array = []
var work_sites := {}

func setup(game_data: Dictionary, state: Dictionary, scene_name: String, saved_view: Dictionary) -> void:
	data = game_data
	map_name = scene_name
	name = scene_name.capitalize()
	var is_city := map_name == "city"
	set_field_scale(FIELD_UNIT_SCALE if is_city else WORLD_UNIT_SCALE, 1.0 if is_city else WORLD_CREATURE_SCALE)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#8b9874") if is_city else Color("#8baba7")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d8e5ee") if is_city else Color("#e5eee1")
	env.ambient_light_energy = 0.58 if is_city else 0.65
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.fog_enabled = true
	env.fog_light_color = env.background_color
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_density = 0.72
	env.fog_depth_begin = 160.0 if is_city else 340.0
	env.fog_depth_end = 300.0 if is_city else 610.0
	WarriorVisual.add_reflections(env, env.background_color)
	# Grade: a touch more contrast, calmer saturation (the raw palette read as lime).
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.1
	env.adjustment_saturation = 0.9
	env.adjustment_brightness = 1.0
	camera.environment = env
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -32, 0)
	shadow_direction = -sun.basis.z
	sun.light_color = Color("#ffe4b8") if is_city else Color("#ffefd0")
	sun.light_energy = 1.85
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150 if is_city else 260
	if is_city:
		# One atlas projection covers the orthographic city without repeating casters across splits.
		sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	add_child(sun)
	var ground_material := ShaderMaterial.new()
	ground_material.shader = BIOME_SHADER
	ground_material.set_shader_parameter("settlement", is_city)
	ground_material.set_shader_parameter("grass", load(SURFACES + "grass20-albedo.webp"))
	ground_material.set_shader_parameter("earth", load(SURFACES + "soil-albedo.webp"))
	ground_material.set_shader_parameter("rock", load(data.stoneTexture))
	ground_material.set_shader_parameter("normal_texture", load(SURFACES + "grass20-normal.png"))
	ground_material.set_shader_parameter("roughness_texture", load(SURFACES + "grass20-roughness.png"))
	ground_material.set_shader_parameter("soil_normal", load(SURFACES + "soil-normal.png"))
	ground_material.set_shader_parameter("soil_roughness", load(SURFACES + "soil-roughness.png"))
	ground_material.set_shader_parameter("stone_normal", load(SURFACES + "stone-normal.png"))
	ground_material.set_shader_parameter("stone_roughness", load(SURFACES + "stone-roughness.png"))
	if is_city:
		meadow_material = ShaderMaterial.new()
		meadow_material.shader = MEADOW_SHADER
		meadow_stone = StandardMaterial3D.new()
		meadow_stone.albedo_texture = load(data.stoneTexture)
		meadow_stone.vertex_color_use_as_albedo = true
		meadow_stone.roughness = 0.94
	scenery_material = StandardMaterial3D.new()
	scenery_material.albedo_texture = load(data.environmentTexture)
	scenery_material.vertex_color_use_as_albedo = true
	scenery_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	scenery_material.roughness = 0.95
	scenery_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	scenery_material.alpha_scissor_threshold = 0.36
	scenery_material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var ground_paths: Array = data.cityGround if is_city else data.worldGround
	if not is_city:
		world_heights = Marshalls.base64_to_raw(data.worldHeights).to_float32_array()
	var terrain_slice := Time.get_ticks_usec()
	for path in ground_paths:
		var ground := scene_resource(path).instantiate()
		add_child(ground)
		for mesh in ground.find_children("*", "MeshInstance3D", true, false):
			mesh.material_override = ground_material
			if is_city:
				city_ground_meshes.append(mesh)  # [forest_rescue_v1 hook]
			var bounds: AABB = mesh.transform * mesh.get_aabb()
			terrain_bounds = bounds if not terrain_bounds.has_volume() else terrain_bounds.merge(bounds)
		terrain_slice = await setup_slice(terrain_slice)
	add_child(buildings)
	add_child(actors)
	add_child(creatures)
	add_child(training)
	add_child(scenery)
	add_child(city_ground_detail)
	add_child(parade)
	add_child(workers)
	add_child(effects)
	add_child(march_lines)
	add_child(battle_fx)
	add_child(combat_audio)
	if is_city:
		town.name = "Town"
		add_child(town)
		var lots_table: Variant = JSON.parse_string(FileAccess.get_file_as_string(TOWN_LOTS))
		town_lots = lots_table.get("types", {}) if lots_table is Dictionary else {}
		works.setup(self, data)
		add_child(works)
		works2.setup(self, data)
		works2.name = "CityWorks2"
		add_child(works2)
	add_child(camera)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL if is_city else Camera3D.PROJECTION_PERSPECTIVE
	camera.fov = 43.0
	camera.near = 0.5
	camera.far = 700.0 if is_city else 1100.0
	await yield_frame()
	if is_city:
		zoom = 70.0
		target = Vector3(5, 0, -4)
		build_water()
		# [forest_rescue_v1 hook] 1022: the city opens with the 1021 forest; ForestGame attaches the world
		# layer after the launch (attach_forest_world), only when the server offers the adventure.
		if ForestFlags.eager():
			await _setup_forest_world()
	else:
		fit_world()
		await build_world_scenery()
		await yield_frame()
		await build_towns()
		build_world_water()
		await yield_frame()
		build_world_roads()
	if not saved_view.is_empty():
		target = saved_view.target
		zoom = saved_view.zoom
		world_yaw = saved_view.get("yaw", 0.0)
		resource_layer = saved_view.get("resources", true)
		detail_layer = saved_view.get("details", true)
	if is_city:
		await present_city(state, true)
	else:
		present(state)
	update_camera(0, true)
	get_viewport().size_changed.connect(update_visible_batches)

# Size of the field soldiers and creatures on this map (see FIELD_UNIT_SCALE).
# Tools may compare sizes; armies and creatures already drawn keep theirs until rebuilt.
func set_field_scale(soldier: float, creature: float) -> void:
	unit_scale = soldier
	unit_k = soldier / LAYOUT_UNIT_SCALE
	beast_k = creature
	run_tempo_max = RUN_TEMPO.y if soldier >= FIELD_UNIT_SCALE else WORLD_RUN_TEMPO

func set_active(active: bool) -> void:
	visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	if active:
		camera.make_current()
		if not fx_warmed:
			fx_warmed = true
			fx_warm_frames = 3

# Battle effects, the arrow and the strike cue are first drawn by the first
# blow; drawing them once (invisibly) when the scene opens moves their pipeline
# compilation out of the fight (see BattleFx.warm).
var fx_warmed := false
var fx_warm_frames := 0
var fx_warm_nodes: Array[Node] = []

func warm_effects() -> void:
	battle_fx.warm(camera)
	if fx_warm_nodes.is_empty():
		var at := camera.global_position - camera.global_transform.basis.z * (camera.near + 2.0)
		# Under the stage, not `effects`: present_creatures frees unknown cues there.
		var holder := Node3D.new()
		holder.name = "FxWarmup"
		add_child(holder)
		fx_warm_nodes.append(holder)
		draw_arrow(holder, null, at + camera.global_transform.basis.x * 0.02, 0.5)
		var arrow := holder.get_node("Arrow") as MeshInstance3D
		arrow.global_position = at
		arrow.scale = Vector3.ONE * 0.001
		show_battle_cue("FxWarmupCue", at, Color(1, 1, 1, 0.0), 1.0)
		effects.get_node("FxWarmupCue").reparent(holder)
	if fx_warm_frames == 0:
		for node in fx_warm_nodes:
			if is_instance_valid(node):
				node.queue_free()
		fx_warm_nodes.clear()

func view_state() -> Dictionary:
	return {"target": target, "zoom": zoom, "yaw": world_yaw, "resources": resource_layer, "details": detail_layer}

func fit_world() -> void:
	world_yaw = 0.0
	target = terrain_bounds.get_center()
	target.y = 1.0
	var size := get_viewport().get_visible_rect().size
	var direction := Vector3(0, sin(WORLD_CAMERA_TILT), cos(WORLD_CAMERA_TILT))
	var up := direction.cross(Vector3.RIGHT)
	var tan_y := tan(deg_to_rad(camera.fov) * 0.5) * 0.9
	var tan_x := tan_y * maxf(0.1, size.x / maxf(1.0, size.y))
	zoom = 0
	for corner in range(8):
		var offset := terrain_bounds.get_endpoint(corner) - target
		var depth := maxf(absf(offset.x) / tan_x, absf(offset.dot(up)) / tan_y)
		zoom = maxf(zoom, depth + offset.dot(direction))

func scene_resource(path: String) -> PackedScene:
	if not models.has(path):
		models[path] = load(path)
	return models[path]

# Background loading of troop models. A first-time load() of a troop model
# (about 60-100 ms on a desktop CPU, several times more on a phone, ten types
# in a mixed party) used to run on the main thread when the column appeared.
var model_requests := {}

func request_model(path: String) -> void:
	if path.is_empty() or models.has(path) or model_requests.has(path) or not ResourceLoader.exists(path):
		return
	if ResourceLoader.load_threaded_request(path, "PackedScene") == OK:
		model_requests[path] = true

# True when the model can be instantiated without waiting. Starts loading it
# in the background otherwise.
func model_ready(path: String) -> bool:
	if models.has(path):
		return true
	request_model(path)
	if not model_requests.has(path):
		return true # Not loadable in the background: scene_resource loads it.
	var status := ResourceLoader.load_threaded_get_status(path)
	if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		return false
	model_requests.erase(path)
	if status == ResourceLoader.THREAD_LOAD_LOADED:
		models[path] = ResourceLoader.load_threaded_get(path)
	return true

func prewarm_troops(unit_ids: Array) -> void:
	for id in unit_ids:
		if data.unitModels.has(id):
			request_model(str(data.unitModels[id].field))
	CombatV010.prewarm("troop", unit_ids.filter(func(id): return data.unitModels.has(id)))

func surface(key: String) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_texture = load(SURFACES + key + "-albedo.webp")
	material.normal_enabled = true
	material.normal_texture = load(SURFACES + key + "-normal.png")
	material.roughness_texture = load(SURFACES + key + "-roughness.png")
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material

func point(value: Dictionary) -> Vector3:
	return Vector3(float(value.get("x",0)),float(value.get("y",0)),float(value.get("z",0)))

func array_point(value: Array) -> Vector3:
	return Vector3(float(value[0]),float(value[1]),float(value[2]))

func sample_city(x: float, z: float) -> float:
	var west := -x + 0.16*z + 2.6*sin(z*0.095)
	var north := -z + 0.13*x + 2.8*sin(x*0.078)
	var shelf := 3.8*smoothstep(25,31,west)+2.1*smoothstep(43,49,west)+4.5*smoothstep(25,33,north)+1.7*smoothstep(43,50,north)+2.6*smoothstep(35,43,z+sin(x*0.08)*3)
	var land := 0.45 + shelf*smoothstep(31.5,38,maxf(absf(x),absf(z))) + 0.12*sin(x*0.17)*cos(z*0.14) + 0.16*sin((x+z)*0.08)
	land += 2.0*(1.0-smoothstep(5.5,15,Vector2(x+25,z+7).length()))
	land += 2.5*(1.0-smoothstep(5.5,15,Vector2(x+7,z+27).length()))
	land += 1.1*(1.0-smoothstep(5.5,15,Vector2(x-28,z).length()))
	var center := z+66+8*sin(z*0.068)+3.5*cos(z*0.127+0.3)+9*exp(-pow((z+25)/15,2))
	var distance := absf(x-center)-4.3-0.65*sin(z*0.093+1.4)
	var y := lerpf(-2.85+0.15*sin(z*0.15),land,smoothstep(-0.6,5.2,distance))
	for lot in data.lots:
		var edge := maxf(absf(x-float(lot.x))-float(lot.rx),absf(z-float(lot.z))-float(lot.rz))
		if edge < 1.4:
			y = lerpf(float(lot.get("y",y)),y,smoothstep(0,1.4,edge))
	return y

func path_mesh(strips: Array, material: Material, scale_uv: float) -> MeshInstance3D:
	var mesh := SurfaceTool.new()
	mesh.begin(Mesh.PRIMITIVE_TRIANGLES)
	for quad in strips:
		for i in [0,2,1,2,3,1]:
			var vertex: Vector3 = quad[i]
			mesh.set_uv(Vector2(vertex.x,vertex.z)*scale_uv)
			# Across-strip coordinate: 0 on one bank, 1 on the other (water depth, road edges).
			mesh.set_uv2(Vector2(float(i % 2), 0.0))
			mesh.add_vertex(vertex)
	mesh.generate_normals()
	var instance := MeshInstance3D.new()
	instance.mesh = mesh.commit()
	instance.material_override = material
	add_child(instance)
	return instance

func clear_route() -> void:
	if is_instance_valid(route_preview):
		route_preview.queue_free()
		route_preview = null

func show_route(path: Array) -> void:
	clear_route()
	if path.size() < 2:
		return
	var mesh := ImmediateMesh.new()
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("#edc465")
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLES, material)
	var line := march_points(path)
	for i in range(1, line.size()):
		var a := line[i - 1]
		var b := line[i]
		a.y = (terrain_y(a) if map_name == "world" else sample_city(a.x, a.z)) + 0.35
		b.y = (terrain_y(b) if map_name == "world" else sample_city(b.x, b.z)) + 0.35
		var half_width := Vector3(-(b.z - a.z), 0.0, b.x - a.x).normalized() * 0.36
		for vertex in [a - half_width, a + half_width, b + half_width, a - half_width, b + half_width, b - half_width]:
			mesh.surface_add_vertex(vertex)
	mesh.surface_end()
	route_preview = MeshInstance3D.new()
	route_preview.mesh = mesh
	route_preview.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(route_preview)

func water_material(color: Color) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = WATER_SHADER
	material.set_shader_parameter("water_color", color)
	return material

func build_water() -> void:
	var strips: Array = []
	for i in range(data.water.size()-1):
		var a: Array = data.water[i]
		var b: Array = data.water[i+1]
		strips.append([array_point(a[0]),array_point(a[1]),array_point(b[0]),array_point(b[1])])
	path_mesh(strips, water_material(Color("#42777c")), 0.1)

# Yards and streets for the buildings on their plots (see src/town_plan.gd). Streets
# depend only on where the buildings stand (each yard is sized for the largest of its
# levels), so an upgrade restyles the yard without moving streets or vegetation.
func plan_town(town_buildings: Array, plots: Array, district: Variant) -> void:
	var gates: Array = []
	if walls.visible:
		for road in walls.gate_roads:
			gates.append([road[0], road[1]])
	var obstacles: Array = []
	if district is Dictionary:
		obstacles.append(Rect2(float(district.x) - 15.7, float(district.z) - 12.7, 31.4, 25.4))
	var corners: Array = plots.map(func(p): return Vector2(float(p.x), float(p.z)))
	var key := JSON.stringify([town_buildings, gates.map(func(g): return [g[0].x, g[0].y, g[1].x, g[1].y]),
		obstacles.map(func(r: Rect2): return [r.position.x, r.position.y]), corners.map(func(c: Vector2): return [c.x, c.y])])
	if key == geometries.get("town_signature", ""):
		return
	geometries["town_signature"] = key
	town_plan.plan(town_buildings, town_lots, gates, corners, obstacles, town_ground_ok)
	city_streets = town_plan.street_lines()

func town_ground_ok(x: float, z: float) -> bool:
	if maxf(absf(x), absf(z)) > 58.0 or static_height(x, z) < -0.2:
		return false
	return not walls.visible or walls.inside(x, z, 1.0)

# Inside the town: no wild undergrowth or loose boulders (inside the wall, or near the
# yards before the wall stands).
func in_town(x: float, z: float) -> bool:
	if walls.visible:
		return walls.inside(x, z, -1.0)
	for lot: Dictionary in town_plan.lots:
		if lot.rect.grow(4.0).has_point(Vector2(x, z)):
			return true
	return false

func build_world_water() -> void:
	var plane := PlaneMesh.new()
	plane.size = Vector2(1000, 1000)
	var mesh := MeshInstance3D.new()
	mesh.name = "Water"
	mesh.mesh = plane
	mesh.position.y = 1.13
	var material := water_material(Color("#347e8b"))
	# Distance to the shore (tools: precomputed from worldHeights) drives depth tint and foam.
	material.set_shader_parameter("shore_map", load("res://assets/environment/world-water-distance.png"))
	material.set_shader_parameter("use_shore_map", true)
	# Texel centres sit on the 1.25 m grid points of the heightfield.
	material.set_shader_parameter("height_origin", Vector2(-150.625, -120.625))
	material.set_shader_parameter("height_extent", Vector2(241.0, 193.0) * 1.25)
	mesh.material_override = material
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mesh)

func build_world_roads() -> void:
	var road := surface("path")
	road.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	road.alpha_scissor_threshold = 0.05
	var roads := scene_resource("res://assets/world-roads.glb").instantiate()
	roads.name = "Roads"
	add_child(roads)
	for mesh in roads.find_children("*", "MeshInstance3D", true, false):
		mesh.material_override = road
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

func model_transform(x: float, y: float, z: float, angle: float, scale: float) -> Transform3D:
	return Transform3D(Basis(Vector3.UP,angle).scaled(Vector3.ONE*scale),Vector3(x,y,z))

func group_placements(transforms: Array, cell_size := BATCH_CELL_SIZE) -> Dictionary:
	var cells := {}
	for placement: Transform3D in transforms:
		var coord := Vector2i(floori(placement.origin.x / cell_size), floori(placement.origin.z / cell_size))
		if not cells.has(coord):
			cells[coord] = []
		cells[coord].append(placement)
	return cells

func batch_model(parent: Node3D, path: String, transforms: Array, appearance: Material = null, layer: Dictionary = {}, grouped: Dictionary = {}) -> void:
	if transforms.is_empty():
		return
	var cells := grouped if not grouped.is_empty() else group_placements(transforms)
	var instance := scene_resource(path).instantiate() as Node3D
	prepare_model_materials(instance)
	parent.add_child(instance)
	var forest := path.contains("/forest60/")
	for part in instance.find_children("*", "MeshInstance3D", true, false):
		if forest:
			appearance = forest_material(part)
		var offset: Transform3D = instance.global_transform.affine_inverse() * part.global_transform
		batch_mesh(parent, part.mesh, offset, cells, transforms.size(),
			appearance if appearance != null else part.material_override, layer)
	instance.free()

func batch_silhouettes(parent: Node3D, spec: Dictionary, cells: Dictionary, count: int, layer: Dictionary) -> void:
	var material := StandardMaterial3D.new()
	material.albedo_texture = load(spec.path)
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	material.alpha_scissor_threshold = 0.24
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * float(spec.size)
	var rotation := Basis(Vector3.RIGHT, -WORLD_CAMERA_TILT)
	var center := Vector3(0.5 - float(spec.anchor[0]), float(spec.anchor[1]) - 0.5, 0.0)
	batch_mesh(parent, quad, Transform3D(rotation, rotation * center * float(spec.size)),
		cells, count, material, layer)

func batch_mesh(parent: Node3D, mesh: Mesh, offset: Transform3D, cells: Dictionary,
		count: int, appearance: Material, layer: Dictionary) -> void:
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.mesh = mesh
	# Capacity grows only as needed. Do not upload space for thousands of invisible instances.
	multi.instance_count = 0
	var all_bounds := AABB()
	var clusters: Array[PackedFloat32Array] = []
	var origins_by_cell := PackedVector3Array()
	var low_by_cell := PackedVector3Array()
	var high_by_cell := PackedVector3Array()
	var mesh_bounds := mesh.get_aabb()
	var silhouette: bool = layer.get("silhouette", false)
	var casts_shadow: bool = layer.is_empty() or not (layer.far or layer.detail or layer.resource)
	for placements: Array in cells.values():
		var bounds := AABB()
		var origins := Vector3.ZERO
		var buffer := PackedFloat32Array()
		buffer.resize(placements.size() * 12)
		for index in range(placements.size()):
			var placement: Transform3D = placements[index]
			origins += placement.origin
			if silhouette:
				placement.basis = Basis.IDENTITY.scaled(Vector3.ONE * placement.basis.x.length())
			var placed := placement * offset
			var box := placed * mesh_bounds
			bounds = box if index == 0 else bounds.merge(box)
			var x := placed.basis.x
			var y := placed.basis.y
			var z := placed.basis.z
			var p := placed.origin
			var slot := index * 12
			buffer[slot] = x.x
			buffer[slot + 1] = y.x
			buffer[slot + 2] = z.x
			buffer[slot + 3] = p.x
			buffer[slot + 4] = x.y
			buffer[slot + 5] = y.y
			buffer[slot + 6] = z.y
			buffer[slot + 7] = p.y
			buffer[slot + 8] = x.z
			buffer[slot + 9] = y.z
			buffer[slot + 10] = z.z
			buffer[slot + 11] = p.z
		all_bounds = bounds if clusters.is_empty() else all_bounds.merge(bounds)
		# Include offscreen casters only for batches that actually cast shadows.
		if casts_shadow:
			var reach := maxf(0.0, bounds.end.y + 6.0) / maxf(0.05, -shadow_direction.y)
			bounds = bounds.merge(AABB(bounds.position + shadow_direction * reach, bounds.size))
		bounds = bounds.grow(4.0 if casts_shadow else 3.0)
		clusters.append(buffer)
		origins_by_cell.append(origins / placements.size())
		low_by_cell.append(bounds.position)
		high_by_cell.append(bounds.end)
	multi.custom_aabb = all_bounds
	multi.visible_instance_count = 0
	var node := MultiMeshInstance3D.new()
	node.multimesh = multi
	node.material_override = appearance
	if not casts_shadow:
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)
	render_batches.append({"node":node, "clusters":clusters, "mask":PackedByteArray(),
		"origins":origins_by_cell, "low":low_by_cell, "high":high_by_cell,
		"total":count, "visible":0, "capacity":0, "layer":layer})

func build_forest(city: Dictionary, exclusions: Array, rebuild_ground := true, staged := false, swap := false) -> void:
	# Trees and stumps depend on felled trees; understory and meadow only on exclusions
	# and streets. A felled tree therefore never rebuilds the ground cover.
	forest_last_city = city  # [forest_rescue_v1 hook] the lazy world layer rebuilds from these
	forest_last_exclusions = exclusions
	# [forest_rescue_v1 hook] 1022: a newly felled tree takes only its own instances out.
	if forest_world != null and not rebuild_ground and is_instance_valid(trees.get("node")) and forest_world.fell_trees(city):
		return
	if forest_world != null:
		forest_world.detach_canopy()  # [forest_rescue_v1 hook] survives the group rebuild
	# [forest_rescue_v1 hook] swap (lazy world layer): the 1021 trees and ground cover stay on screen
	# until the world layer's forest has been built, then go in one frame.
	var replaced: Array = []
	if is_instance_valid(trees.get("node")):
		if swap:
			trees.node.name = "ForestReplaced"
			replaced.append(trees.node)
		else:
			trees.node.free()
	if rebuild_ground:
		for child in city_ground_detail.get_children():
			if swap:
				replaced.append(child)
			else:
				child.free()
	render_batches = render_batches.filter(func(batch): return is_instance_valid(batch.node))
	var group := Node3D.new()
	group.name = "Forest"
	add_child(group)
	trees["node"] = group
	selectable_trees.clear()
	standing_tree_cells.clear()
	# [forest_rescue_v1 hook] the world layer owns every tree (kit species, remapped outer ids).
	# staged (city load): its instance build is sliced across frames; a felled tree rebuilds it at once.
	if forest_world != null:
		forest_world.attach_canopy(group)
		if staged:
			await forest_world.build_city_forest(city, exclusions, true)
		else:
			forest_world.build_city_forest(city, exclusions, false)
		if rebuild_ground:
			build_meadow(exclusions)
		for node in replaced:
			if is_instance_valid(node):
				node.free()
		if not replaced.is_empty():
			render_batches = render_batches.filter(func(batch): return is_instance_valid(batch.node))
			update_visible_batches()
		return
	var felled := {}
	for id in city.get("progress", {}).get("felled", []):
		felled[id] = true
	var batches: Dictionary = {}
	var details: Dictionary = {}
	if rebuild_ground or eligible_trees.is_empty():
		eligible_trees.clear()
		for tree in data.woods:
			if tree.village and not city.get("kingdom") is Dictionary:
				continue
			var at := array_point(tree.p)
			if inside_exclusions(at.x, at.z, exclusions) or on_street(Vector2(at.x, at.z), 1.5) or walls.blocks(at.x, at.z):
				continue
			var detail: int = {"":0, "mid":1, "far":2}.get(tree.lod, 2)
			eligible_trees.append({"tree": tree, "p": at, "cell": Vector2i(floori(at.x / 4.0), floori(at.z / 4.0)),
				"key": "tree" + str(int(tree.variant)) + str(detail), "model": "tree" + str(int(tree.variant)),
				"detail": detail, "transform": model_transform(at.x, at.y, at.z, float(tree.angle), float(tree.scale))})
		if staged:
			await yield_frame()
	for entry: Dictionary in eligible_trees:
		var tree: Dictionary = entry.tree
		var p: Vector3 = entry.p
		selectable_trees.append(tree)
		# A felled tree is cleared away completely (no stump is left in the town).
		if felled.has(tree.id):
			continue
		var cell: Vector2i = entry.cell
		if not standing_tree_cells.has(cell):
			standing_tree_cells[cell] = []
		standing_tree_cells[cell].append(Vector2(p.x, p.z))
		var key: String = entry.key
		if not batches.has(key):
			batches[key] = {"model":entry.model, "best":entry.detail, "placements":[]}
		batches[key].placements.append(entry.transform)
	for key in batches:
		var batch: Dictionary = batches[key]
		var cells := group_placements(batch.placements, CITY_TREE_CELL_SIZE)
		for detail in range(batch.best, 3):
			var model: String = batch.model + ["", "mid", "far"][detail]
			batch_model(group, data.models[model].path, batch.placements, null,
				{"city":true, "far":false, "detail":false, "resource":false,
					"tree_lod":detail, "tree_best":batch.best}, cells)
	for key in details:
		batch_model(group, data.cityDetails[key], details[key], scenery_material,
			{"city":true,"far":true,"detail":true,"resource":false})
	if not rebuild_ground:
		return
	if staged:
		await yield_frame()
	var understory: Dictionary = {}
	for prop in data.cityUnderstory:
		if inside_exclusions(prop.x, prop.z, exclusions) or walls.blocks(prop.x, prop.z) or in_town(prop.x, prop.z):
			continue
		if not understory.has(prop.id):
			understory[prop.id] = []
		understory[prop.id].append(model_transform(prop.x, static_height(prop.x, prop.z), prop.z, prop.angle, prop.scale))
	for key in understory:
		batch_model(city_ground_detail, data.cityDetails[key], understory[key], scenery_material,
			{"city":true,"far":true,"detail":true,"resource":false})
	if staged:
		await yield_frame()
	build_meadow(exclusions)

func build_meadow(exclusions: Array) -> void:
	for kind in data.groundCover:
		var transforms: Array = []
		for item in data.groundCover[kind]:
			if inside_exclusions(item.x, item.z, exclusions) or on_street(Vector2(item.x, item.z), 0.85) or walls.blocks(item.x, item.z):
				continue
			if town_plan.covered(item.x, item.z) or (kind == "rocks" and in_town(item.x, item.z)):
				continue
			var y := static_height(item.x, item.z)
			var scale := float(item.size)
			var angle := float(item.get("angle", item.x * 0.7 + item.z * 0.3))
			if kind == "rocks":
				var basis := Basis.from_euler(Vector3(0.2, angle, 0.1)).scaled_local(Vector3(1.0, 0.55, 0.8) * scale)
				transforms.append(Transform3D(basis, Vector3(item.x, y + scale * 0.3, item.z)))
			else:
				transforms.append(model_transform(item.x, y + 0.025, item.z, angle, scale if kind == "grass" else scale / 0.23))
		var material: Material = meadow_stone if kind == "rocks" else meadow_material
		batch_model(city_ground_detail, data.meadow[kind], transforms, material,
			{"city":true,"far":kind != "rocks","detail":false,"resource":false})

func static_height(x: float, z: float) -> float:
	# sample_city() depends only on immutable game data, so heights of fixed
	# placements can be memoised across vegetation rebuilds.
	var cell := Vector2(x, z)
	var cached: Variant = static_heights.get(cell)
	if cached == null:
		cached = sample_city(x, z)
		static_heights[cell] = cached
	return cached

func on_street(p: Vector2, width: float) -> bool:
	# A street [a, b, half width] keeps clear its own width plus the half of `width`.
	for segment in city_streets:
		var near := Geometry2D.get_closest_point_to_segment(p, segment[0], segment[1])
		var limit: float = float(segment[2]) + width * 0.5 if segment.size() > 2 else width
		if p.distance_squared_to(near) < limit * limit:
			return true
	return false

func inside_exclusions(x: float, z: float, exclusions: Array) -> bool:
	for rect: Rect2 in exclusions:
		if rect.has_point(Vector2(x, z)):
			return true
	return false

const SETUP_SLICE_USEC := 3500
const BACKGROUND_SLICE_USEC := 2000
# While the launch screen covers everything (main.gd), the first scene is built in
# large slices: up to build 1020 it took 3.5 ms per frame, and with the phone's 60 Hz
# a frame lasts 16.7 ms, so about four fifths of the launch was spent waiting.
const LAUNCH_SLICE_USEC := 45000
static var launching := false
# Measurements only (tools/profile_startup.gd --slice=3500): the slices of build 1020.
static var launch_slices := true
# Set while the scene is prepared in the background (the other scene is on
# screen). It returns false while the player is touching or the camera moves, and
# the build waits; cleared when the player asks for this scene, so it finishes at
# full speed.
var background_gate := Callable()

static var launch_slice_start := 0

func yield_frame() -> void:
	# One frame; in a background build, also waits while the player interacts.
	# Under the launch screen a frame is yielded only once a large slice is used up.
	if launching and launch_slices and Time.get_ticks_usec() - launch_slice_start < LAUNCH_SLICE_USEC:
		return
	await get_tree().process_frame
	launch_slice_start = Time.get_ticks_usec()
	while background_gate.is_valid() and not background_gate.call():
		await get_tree().process_frame

func setup_slice(started: int) -> int:
	# Yields to the next frame once the current one has spent its setup budget.
	var budget := BACKGROUND_SLICE_USEC if background_gate.is_valid() else (LAUNCH_SLICE_USEC if launching and launch_slices else SETUP_SLICE_USEC)
	if Time.get_ticks_usec() - started < budget:
		return started
	await get_tree().process_frame
	while background_gate.is_valid() and not background_gate.call():
		await get_tree().process_frame
	return Time.get_ticks_usec()

func build_world_scenery() -> void:
	var batches := {}
	var distant_canopies := {}
	var slice_started := Time.get_ticks_usec()
	var counted := 0
	for item in data.environment:
		counted += 1
		if counted % 256 == 0:
			slice_started = await setup_slice(slice_started)
		if not batches.has(item.id):
			batches[item.id] = []
		batches[item.id].append(model_transform(item.x, item.y, item.z, item.rotation, item.scale))
		var canopy: Variant = data.environmentModels[item.id].canopy
		if canopy is Dictionary and float(canopy.scale) < 0.65:
			var key := "tree" + str(int(canopy.variant))
			if not distant_canopies.has(key):
				distant_canopies[key] = []
			distant_canopies[key].append(model_transform(item.x, item.y, item.z, 0.0, item.scale * canopy.scale))
	for key in distant_canopies:
		var transforms: Array = distant_canopies[key]
		batch_silhouettes(scenery, data.distantModels[key], group_placements(transforms), transforms.size(),
			{"far":true, "tree":true, "detail":false, "resource":false, "silhouette":true, "canopy":true})
		slice_started = await setup_slice(slice_started)
	for id in batches:
		var spec: Dictionary = data.environmentModels[id]
		var transforms: Array = batches[id]
		var cells := group_placements(transforms)
		var has_silhouette: bool = spec.canopy is Dictionary and float(spec.canopy.scale) < 0.65
		# Forest trees carry their own material (foliage atlas); other scenery shares the atlas material.
		var material: Material = null if str(spec.near).contains("/forest60/") else scenery_material
		for far in [false, true]:
			batch_model(scenery, spec.far if far else spec.near, transforms, material,
				{"far":far, "tree":spec.tree, "detail":spec.detail, "resource":spec.resource, "canopy":has_silhouette}, cells)
			slice_started = await setup_slice(slice_started)

func toggle_scenery_layer(resources: bool) -> void:
	if resources:
		resource_layer = not resource_layer
	else:
		detail_layer = not detail_layer
	update_visible_batches()

func update_visible_batches() -> void:
	var started := Time.get_ticks_usec()
	camera_dirty = false
	last_cull_target = camera_target
	last_cull_zoom = camera_zoom
	last_cull_yaw = camera_yaw
	var planes := camera.get_frustum()
	var normals := PackedVector3Array()
	var signs := PackedVector3Array()
	var offsets := PackedFloat32Array()
	for plane in planes:
		normals.append(plane.normal)
		signs.append(Vector3(
			1.0 if plane.normal.x < 0 else 0.0,
			1.0 if plane.normal.y < 0 else 0.0,
			1.0 if plane.normal.z < 0 else 0.0
		))
		offsets.append(plane.d)
	var overhead_canopies := camera_zoom >= CANOPY_OVERVIEW_ZOOM
	var city_near_squared := 27.0 * 27.0 if camera_zoom <= 47.0 else 0.0
	var city_mid_radius := clampf(camera_zoom * 0.52, 31.0, 46.0)
	var city_mid_squared := city_mid_radius * city_mid_radius
	for batch in render_batches:
		var node: MultiMeshInstance3D = batch.node
		var layer: Dictionary = batch.layer
		var near_zoom := false
		var town: bool = layer.get("town", false)
		var silhouette: bool = layer.get("silhouette", false)
		var landscape: bool = not layer.is_empty() and not layer.get("city", false)
		var city_tree_lod: int = layer.get("tree_lod", -1)
		if city_tree_lod == 0 and city_near_squared == 0.0:
			node.hide()
			continue
		if landscape:
			if layer.get("canopy", false) and overhead_canopies != silhouette:
				node.hide()
				continue
			if (layer.detail and (not detail_layer or camera_zoom >= 105.0)) or (layer.resource and not resource_layer):
				node.hide()
				continue
			near_zoom = camera_zoom < (TOWN_DETAIL_ZOOM if town else (90.0 if layer.tree else 80.0))
			if not near_zoom and not layer.far:
				node.hide()
				continue
			if near_zoom and layer.far and not town and not layer.tree:
				node.hide()
				continue
		var mask := PackedByteArray()
		mask.resize(batch.clusters.size())
		var cell_origins: PackedVector3Array = batch.origins
		var low: PackedVector3Array = batch.low
		var high: PackedVector3Array = batch.high
		var buffers: Array[PackedFloat32Array] = batch.clusters
		var visible_count := 0
		var choose_distance: bool = landscape and near_zoom and (town or layer.tree)
		var compare_detail := landscape and not (silhouette and not town)
		var world_radius_squared := TOWN_DETAIL_RADIUS * TOWN_DETAIL_RADIUS if town else 2500.0
		var far: bool = layer.get("far", false)
		var best: int = layer.get("tree_best", 0)
		for i in buffers.size():
			if city_tree_lod >= 0:
				var origin: Vector3 = cell_origins[i]
				var dx := origin.x - camera_target.x
				var dz := origin.z - camera_target.z
				var distance_squared := dx * dx + dz * dz
				var desired := 0 if distance_squared < city_near_squared else (1 if distance_squared < city_mid_squared else 2)
				if city_tree_lod != maxi(desired, best):
					continue
			if compare_detail:
				var near := near_zoom
				if choose_distance:
					var origin: Vector3 = cell_origins[i]
					var x := origin.x - camera_target.x
					var z := origin.z - camera_target.z
					near = x * x + z * z < world_radius_squared
				if near == far:
					continue
			var visible_cluster := true
			var minimum := low[i]
			var extent := high[i] - minimum
			for plane_index in normals.size():
				var nearest := minimum + extent * signs[plane_index]
				if normals[plane_index].dot(nearest) > offsets[plane_index] + 0.0001:
					visible_cluster = false
					break
			if visible_cluster:
				mask[i] = 1
				visible_count += 1
		node.visible = visible_count > 0
		if batch.mask == mask:
			continue
		batch.mask = mask
		var visible_transforms := PackedFloat32Array()
		for i in mask.size():
			if mask[i]:
				visible_transforms.append_array(buffers[i])
		batch.visible = int(visible_transforms.size() / 12.0)
		if not visible_transforms.is_empty():
			if batch.visible > batch.capacity:
				var capacity := maxi(16, int(batch.capacity))
				while capacity < batch.visible:
					capacity *= 2
				batch.capacity = mini(capacity, int(batch.total))
				node.multimesh.instance_count = batch.capacity
			visible_transforms.resize(batch.capacity * 12)
			node.multimesh.buffer = visible_transforms
			uploaded_transform_bytes += visible_transforms.size() * 4
		node.multimesh.visible_instance_count = batch.visible
	last_cull_ms = (Time.get_ticks_usec() - started) / 1000.0
	if forest_world != null:
		forest_world.on_camera_changed()  # [forest_rescue_v1 hook]

func batch_counts() -> Vector2i:
	var counts := Vector2i.ZERO
	for batch in render_batches:
		if batch.node.visible:
			counts.x += int(batch.visible)
		counts.y += int(batch.total)
	return counts

func world_lod_counts() -> Vector3i:
	var counts := Vector3i.ZERO
	for batch in render_batches:
		if not batch.node.visible:
			continue
		var layer: Dictionary = batch.layer
		if layer.get("town", false):
			if layer.get("silhouette", false):
				counts.y += int(batch.visible)
			elif layer.get("town_counter", false):
				counts.x += int(batch.visible)
		elif layer.get("silhouette", false):
			counts.z += int(batch.visible)
	return counts

func build_towns() -> void:
	var group := Node3D.new()
	group.name = "Settlements"
	add_child(group)
	var batches := {"hall":[], "house":[]}
	for site in data.sites:
		for part in site.parts:
			batches[part.key].append(model_transform(float(part.x), float(part.y), float(part.z),
				float(part.rotation), float(part.scale)))
	for key in batches:
		var transforms: Array = batches[key]
		var cells := group_placements(transforms, 6.0)
		var layer := {"town":true, "far":false, "tree":false, "detail":false, "resource":false}
		var first_batch := render_batches.size()
		batch_model(group, data.models[key].path, transforms, null, layer, cells)
		if render_batches.size() > first_batch:
			render_batches[first_batch].layer = layer.merged({"town_counter":true})
		await yield_frame()
		batch_silhouettes(group, data.distantModels[key], cells, transforms.size(),
			layer.merged({"far":true, "silhouette":true}, true))
		await yield_frame()

func add_model(parent: Node3D, model_path: String, transform_value: Transform3D) -> Node3D:
	var instance := scene_resource(model_path).instantiate() as Node3D
	prepare_model_materials(instance)
	instance.transform = transform_value
	parent.add_child(instance)
	return instance

func add_warrior(parent: Node3D, model_path: String, transform_value: Transform3D) -> Node3D:
	var instance := scene_resource(model_path).instantiate() as Node3D
	WarriorVisual.prepare(instance)
	instance.transform = transform_value
	parent.add_child(instance)
	return instance

# Forest meshes share one shader material per atlas (forest.gdshader): same look as
# the imported material, plus the clearing around a visible fight.
func forest_material(part: MeshInstance3D) -> Material:
	var source := part.get_active_material(0) as BaseMaterial3D
	var texture: Texture2D = source.albedo_texture if source != null else null
	var key := texture.resource_path if texture != null else ""
	if forest_materials.has(key):
		return forest_materials[key]
	var material := ShaderMaterial.new()
	material.shader = FOREST_SHADER
	material.set_shader_parameter("albedo_tex", texture)
	material.set_shader_parameter("cutoff", source.alpha_scissor_threshold if source != null else 0.42)
	forest_materials[key] = material
	return material


# `battle_focus` is declared in project.godot [shader_globals].
# Opens (radius > 0) or closes the forest clearing around the fight on screen.
func update_battle_focus(centre: Vector3, wanted: float, delta: float, core := Vector3.ZERO, core_wanted := 0.0) -> void:
	if wanted > 0.0:
		focus_centre = centre
	focus_radius = move_toward(focus_radius, wanted, delta * 30.0)
	RenderingServer.global_shader_parameter_set(&"battle_focus",
		Vector4(focus_centre.x, focus_centre.y, focus_centre.z, focus_radius))
	# The crowd's own ground around a hunted creature (battle_focus_core in forest.gdshader).
	if core_wanted > 0.0:
		focus_core = core
	focus_core_radius = move_toward(focus_core_radius, core_wanted, delta * 30.0)
	RenderingServer.global_shader_parameter_set(&"battle_focus_core",
		Vector4(focus_core.x, focus_core.y, focus_core.z, focus_core_radius))

func prepare_model_materials(instance: Node3D) -> void:
	# Reuse original maps and geometry; preserve normal/ORM values and alpha settings.
	for part: MeshInstance3D in instance.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		for index in part.mesh.get_surface_count():
			var material := part.get_active_material(index)
			if material is BaseMaterial3D:
				material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC

func play_animation(model: Node3D, preferred: String, fallback := "", phase := -1.0, start_fraction := 0.0) -> void:
	clear_additive_hit(model)
	if CreatureVisuals.owns(model):
		# creatures-v2: the semantic state resolves to one exact authored clip (no substring guess).
		var species := CreatureVisuals.species_of(model)
		var exact := CreatureVisuals.clip_name(species, preferred)
		if exact != &"":
			preferred = String(exact)
			fallback = String(CreatureVisuals.clip_name(species, "Idle"))
	if not model.has_meta("animation_players"):
		model.set_meta("animation_players", model.find_children("*", "AnimationPlayer", true, false))
	for animation: AnimationPlayer in model.get_meta("animation_players"):
		var names: PackedStringArray = animation.get_animation_list()
		var selected := ""
		for clip in names:
			if preferred.to_lower() in clip.to_lower():
				selected = clip
				break
			if not fallback.is_empty() and fallback.to_lower() in clip.to_lower():
				selected = clip
		if selected.is_empty():
			continue
		var resource: Animation = animation.get_animation(selected)
		if phase < 0:
			resource.loop_mode = Animation.LOOP_LINEAR
			animation.play(selected, 0.16)
			if start_fraction > 0.0:
				animation.seek(start_fraction * resource.length, true)
		else:
			if animation.assigned_animation != selected:
				animation.play(selected)
			animation.pause()
			animation.seek(clampf(phase, 0.0, 0.999) * resource.length, true)

func clear_additive_hit(model: Node3D) -> void:
	if not model.has_meta("additive_hit"):return
	var last: Dictionary=model.get_meta("additive_hit")
	if is_instance_valid(last.skeleton):
		# An animation may already have replaced this pose. Never undo its value.
		if last.skeleton.get_bone_pose_rotation(last.bone).is_equal_approx(last.applied):
			last.skeleton.set_bone_pose_rotation(last.bone,last.base)
	model.remove_meta("additive_hit")

func additive_hit(model: Node3D, phase: float) -> void:
	clear_additive_hit(model)
	if phase<0.0 or phase>1.0:return
	for skeleton: Skeleton3D in model.find_children("*","Skeleton3D",true,false):
		for bone in skeleton.get_bone_count():
			var name:=skeleton.get_bone_name(bone).to_lower()
			if "spine" in name or "chest" in name:
				var rotation:=skeleton.get_bone_pose_rotation(bone)
				var applied:=rotation*Quaternion(Vector3.RIGHT,sin(phase*PI)*.035*(1.0-phase))
				skeleton.set_bone_pose_rotation(bone,applied)
				model.set_meta("additive_hit",{"skeleton":skeleton,"bone":bone,"base":rotation,"applied":applied})
				return

func present(state: Dictionary) -> void:
	if map_name == "city":
		present_city(state)
		return
	place_markers.clear()
	empty_plots.clear()
	var occupied := {}
	for player in state.world.cities:
		occupied[player.slot] = true
		place_markers.append({"position":point(player.position)+Vector3(0,4.5,0),"id":player.id,"kind":"settlement","item":player})
	for site in data.sites:
		if not occupied.has(site.slot):
			empty_plots.append({"position":point(site)+Vector3(0,2,0), "kind":"world-plot", "item":site})
	var frame := combat_view.frame(state, float(state.serverTime), map_name)
	present_armies(frame.state, frame.time)

# Every point a city creature stands on or patrols to: the wall stays inside them.
# Defeated creatures keep their place, so the wall does not jump after a hunt.
func creature_lairs(state: Dictionary) -> Array:
	var points: Array = []
	for encounter in state.get("encounters", []):
		var patrol: Array = []
		for step in encounter.get("patrol", []):
			if step is Dictionary:
				patrol.append(Vector2(float(step.get("x", 0)), float(step.get("z", 0))))
		if patrol.size() >= 2:
			# The whole patrol line, sampled every 2 m. The live position lies on it
			# and changes with every poll; using it rebuilt the town signature (and
			# re-planned the wall) on each server answer while a creature walked.
			points.append(patrol[0])
			for i in range(1, patrol.size()):
				var a: Vector2 = patrol[i - 1]
				var b: Vector2 = patrol[i]
				var pieces := maxi(1, ceili(a.distance_to(b) / 2.0))
				for k in range(1, pieces + 1):
					points.append(a.lerp(b, float(k) / pieces))
			continue
		points.append_array(patrol)
		if encounter.get("position") is Dictionary:
			var p: Dictionary = encounter.position
			points.append(Vector2(float(p.get("x", 0)), float(p.get("z", 0))))
	points.sort()
	return points

func present_city(state: Dictionary, staged := false) -> void:
	# staged=true is used only by setup(): the first build yields between phases so
	# no single frame carries the whole settlement. Later updates stay synchronous.
	var city: Dictionary = state.city
	forest_last_state = state  # [forest_rescue_v1 hook] for the lazy world layer
	if forest_world != null:
		forest_world.apply_state_hint(state)  # [forest_rescue_v1 hook]
	var progress: Dictionary = city.get("progress", {})
	var kingdom: Variant = city.get("kingdom")
	var construction: Variant = kingdom if kingdom is Dictionary else city.get("legacyUpgrades")
	var order: Variant = construction.get("order") if construction is Dictionary else null
	var district: Variant = city.military.get("garrison")
	var army: Dictionary = city.military.get("owned", {})
	var lairs := creature_lairs(state)
	var key := JSON.stringify([city.buildings, progress.get("sites", []), progress.get("felled", []),
		progress.get("cleared", []), kingdom.get("clearedPlots", []) if kingdom is Dictionary else [],
		order, district, lairs])
	if key == geometries.get("city_signature",""):
		sync_parade(army, district)
		return
	geometries["city_signature"] = key
	place_markers.clear()
	empty_plots.clear()
	var plots: Array = data.plots.duplicate() if kingdom is Dictionary else data.legacyPlots.duplicate()
	for id in progress.get("sites", []):
		if data.treePlots.has(id):
			plots.append(data.treePlots[id])
	var occupied := {}
	var plot_positions := {}
	var exclusions: Array = []
	# Descriptors of every static city node. Unchanged nodes are reused instead of
	# re-instantiating GLB scenes after each authoritative state update.
	var wanted_buildings: Array = []
	var wanted_workers: Array = []
	if district is Dictionary:
		exclusions.append(Rect2(district.x - 15.7, district.z - 12.7, 31.4, 25.4))
	var hall_level := 1
	var defence_level := 0
	var hall_spot := Vector2(-5.0, -5.0) if kingdom is Dictionary else Vector2.ZERO
	for building in city.buildings:
		var base: String = city_base_type(building.type)
		if base == "ECO-05":
			hall_level = maxi(hall_level, int(building.level))
			for plot in plots:
				if plot.id == building.plotId:
					hall_spot = Vector2(float(plot.x), float(plot.z))
		elif base == "SUP-03":
			defence_level = maxi(defence_level, int(building.level))
	var wall_markers: Array = []
	var town_buildings: Array = []
	for building in city.buildings:
		occupied[building.plotId] = true
		for plot in plots:
			if plot.id != building.plotId:
				continue
			var id: String = data.starterHall if building.type == "ECO-05" and int(building.level) == 1 else data.types.get(building.type,"")
			if id == "":
				break
			var asset: Dictionary = data.models[id]
			var x := float(plot.x)
			var z := float(plot.z)
			var y := sample_city(x,z)
			plot_positions[plot.id] = Vector3(x, y, z)
			exclusions.append(Rect2(x - 7.0, z - 7.0, 14.0, 14.0))
			# "Walls and gate" is the perimeter wall itself: its plate sits on the main
			# gate, the plot keeps only a cleared yard.
			if city_base_type(building.type) == "SUP-03" and walls_shown(hall_level, defence_level):
				wall_markers.append(building)
				break
			# Reworked levels (architecture-v2) are complete scenes per type and level, so they
			# never alter the shared model or overlays used by other levels and types.
			var level_model: Dictionary = level_model_for(building.type, int(building.level))
			if not level_model.is_empty():
				wanted_buildings.append(["model", level_model.path, model_transform(x,y,z,0,float(level_model.get("scale", 1.0)))])
				wanted_workers.append([id, Vector3(x,y,z), level_worker_offset(level_model)])
			else:
				# The scattered level props of 0.5.9 (city-details/<type>-<level>.glb) are
				# replaced by the yard dressing of the town plan, the same for every building.
				var scale := float(asset.scale)*(1+0.055*(int(building.level)-1))
				wanted_buildings.append(["model", asset.path, model_transform(x,y,z,0,scale)])
				wanted_workers.append([id, Vector3(x,y,z)])
			town_buildings.append({"id": building.id, "type": building.type, "level": int(building.level),
				"x": x, "z": z, "hall": city_base_type(building.type) == "ECO-05"})
			place_markers.append({"position":Vector3(x,y+5,z),"id":building.id,"kind":"building","item":building})
			break
	# The wall ring: grows with the town hall, bulges around buildings, sites and
	# the troop base. Only plots inside it are offered for new buildings.
	var obstacles: Array = []
	for id in plot_positions:
		var at: Vector3 = plot_positions[id]
		obstacles.append([Vector2(at.x, at.z), CityWalls.BUILDING_CLEARANCE])
	var order_plot: String = str(order.get("plotId", "")) if order is Dictionary else ""
	for plot in plots:
		if plot.id == order_plot or plot.id.begins_with("site-"):
			obstacles.append([Vector2(float(plot.x), float(plot.z)), CityWalls.BUILDING_CLEARANCE])
	# The main gate of the ring is the "walls and gate" building itself (B18 levels I-V).
	var gate_scene: Dictionary = level_model_for("SUP-03", maxi(1, defence_level))
	walls.custom_main_gate = not gate_scene.is_empty()
	walls.main_gate_span = GATE_SCENE_HALF_SPAN * gate_scene_scale(defence_level)
	walls.plan(hall_spot, hall_level, defence_level, walls_shown(hall_level, defence_level), obstacles, district, sample_city, lairs)
	var gate_signature := ""
	if walls.visible and walls.custom_main_gate:
		var out := walls.main_gate_outward
		var gate_basis := Basis(Vector3.UP, atan2(out.x, out.z)).scaled(Vector3.ONE * gate_scene_scale(defence_level))
		wanted_buildings.append(["model", gate_scene.path, Transform3D(gate_basis, walls.main_gate)])
		gate_signature = node_signature("model", gate_scene.path, Transform3D(gate_basis, walls.main_gate))
	for building in wall_markers:
		place_markers.append({"position": walls.main_gate + Vector3.UP * 7.0, "id": building.id, "kind": "building", "item": building, "wall": true})
	if walls.visible and wall_markers.is_empty():
		place_markers.append({"position": walls.main_gate + Vector3.UP * 7.0, "id": "city-walls", "kind": "wall",
			"item": {"type": "SUP-03", "level": 1, "wall": true}})
	plan_town(town_buildings, plots, district)
	for lot: Dictionary in town_plan.lots:
		exclusions.append(lot.rect)
	for plot in plots:
		if (kingdom is Dictionary and plot.id in kingdom.get("clearedPlots", [])) or plot.id.begins_with("site-"):
			exclusions.append(Rect2(plot.x - 6.7, plot.z - 6.7, 13.4, 13.4))
		if not plot_positions.has(plot.id):
			plot_positions[plot.id] = Vector3(plot.x, sample_city(plot.x, plot.z), plot.z)
		# Scaffolding, builders and the rising building are drawn by CityWorks.
		if not occupied.has(plot.id):
			var x := float(plot.x)
			var z := float(plot.z)
			if kingdom is Dictionary and not walls.inside(x, z, 6.0) and not plot.id.begins_with("site-"):
				continue
			empty_plots.append({"position":Vector3(x, sample_city(x, z), z), "kind":"plot", "item":plot})
	for grove in data.clearings:
		if grove.id in progress.get("cleared", []):
			var half := float(grove.size) * 0.5
			exclusions.append(Rect2(grove.x - half, grove.z - half, grove.size, grove.size))
	sync_city_buildings(wanted_buildings)
	gate_node = null
	for child in buildings.get_children():
		if not gate_signature.is_empty() and child.get_meta("city_signature", "") == gate_signature:
			gate_node = child
	if walls.signature != geometries.get("wall_signature", "") or (walls.visible and not is_instance_valid(walls.node)):
		geometries["wall_signature"] = walls.signature
		walls.build(self)
	works.observe_city(city, plot_positions)
	works2.observe_city(city, plot_positions)
	work_sites = plot_positions
	if staged:
		await yield_frame()
	sync_city_workers(wanted_workers)
	if geometries.get("town_built", "") != geometries.get("town_signature", "") or not is_instance_valid(city_road_mesh):
		geometries["town_built"] = geometries.get("town_signature", "")
		town.build(town_plan, static_height)
		city_road_mesh = town.ground
		town_rebuilds += 1
	var ground_key := JSON.stringify([exclusions.map(func(r: Rect2): return [r.position.x, r.position.y, r.size.x, r.size.y]),
		kingdom is Dictionary, city_streets.map(func(road): return [road[0].x, road[0].y, road[1].x, road[1].y]),
		walls.signature if walls.visible else ""])
	var vegetation_key := JSON.stringify([ground_key, progress.get("felled", [])])
	if vegetation_key != geometries.get("vegetation_signature", ""):
		var rebuild_ground: bool = ground_key != geometries.get("ground_signature", "")
		geometries["vegetation_signature"] = vegetation_key
		geometries["ground_signature"] = ground_key
		if staged:
			await yield_frame()
			await build_forest(city, exclusions, rebuild_ground, true)
		else:
			build_forest(city, exclusions, rebuild_ground)
		vegetation_rebuilds += 1
		if rebuild_ground:
			ground_rebuilds += 1
	sync_parade(army, district)
	update_visible_batches()

func city_base_type(type: String) -> String:
	for definition in data.buildings:
		if definition.id == type:
			return str(definition.get("base", type))
	return type

# The wall stands from town hall II; a built "walls and gate" shows it at once.
func walls_shown(hall_level: int, defence_level: int) -> bool:
	return hall_level >= CityWalls.WALL_FROM_HALL or defence_level > 0

func node_signature(kind: String, path: String, transform_value: Transform3D) -> String:
	return "%s|%s|%s" % [kind, path, var_to_str(transform_value)]

func sync_city_buildings(wanted: Array) -> void:
	var existing := {}
	for child in buildings.get_children():
		var signature: String = child.get_meta("city_signature", "")
		if signature.is_empty() or existing.has(signature):
			child.free()
		else:
			existing[signature] = child
	var kept := {}
	for item in wanted:
		var signature := node_signature(item[0], item[1], item[2])
		if existing.has(signature) and not kept.has(signature):
			kept[signature] = true
			continue
		var node: Node3D
		if item[0] == "detail":
			add_city_detail(buildings, item[1], item[2].origin)
			node = buildings.get_child(buildings.get_child_count() - 1)
			node.transform = item[2]
		else:
			node = add_model(buildings, item[1], item[2])
		node.set_meta("city_signature", signature)
		kept[signature] = true
		city_nodes_created += 1
	for signature in existing:
		if not kept.has(signature):
			existing[signature].free()

func sync_city_workers(wanted: Array) -> void:
	var existing := {}
	for child in workers.get_children():
		var signature: String = child.get_meta("city_signature", "")
		if signature.is_empty() or existing.has(signature):
			child.free()
		else:
			existing[signature] = child
	var kept := {}
	for item in wanted:
		var signature := "%s|%s|%s" % [item[0], var_to_str(item[1]), var_to_str(item[2] if item.size() > 2 else null)]
		if existing.has(signature) and not kept.has(signature):
			kept[signature] = true
			continue
		var before := workers.get_child_count()
		add_worker(item[0], item[1], item[2] if item.size() > 2 else null)
		if workers.get_child_count() > before:
			workers.get_child(workers.get_child_count() - 1).set_meta("city_signature", signature)
			city_nodes_created += 1
		kept[signature] = true
	for signature in existing:
		if not kept.has(signature):
			existing[signature].free()

func level_worker_offset(level_model: Dictionary) -> Variant:
	var w: Variant = level_model.get("worker")
	return Vector3(float(w[0]), float(w[1]), float(w[2])) if w is Array and w.size() == 3 else null

# [scene path, scale] that the city shows for a type at a level (level scene or the
# shared model grown by level), or [] when the type has no model.
func level_visual(type: String, level: int) -> Array:
	if level < 1 or level > 11:
		return []
	var entry := level_model_for(type, level)
	if not entry.is_empty():
		return [entry.path, float(entry.get("scale", 1.0))]
	var id: String = data.starterHall if type == "ECO-05" and level == 1 else data.types.get(type, "")
	if id.is_empty() or not data.models.has(id):
		return []
	return [data.models[id].path, float(data.models[id].scale) * (1 + 0.055 * (level - 1))]

func level_model_for(type: String, level: int) -> Dictionary:
	var levels: Variant = data.get("levelModels", {}).get(type)
	if not levels is Dictionary:
		return {}
	var entry: Variant = levels.get(str(level))
	return entry if entry is Dictionary else {}

func add_worker(building: String, base: Vector3, offset_override: Variant = null) -> void:
	var worker: String = {
		"hall":"Worker_Carrier", "starterHall":"Worker_Carrier", "warehouse":"Worker_Carrier",
		"market27":"Worker_Carrier", "quarry27":"Worker_Carrier", "ironmine27":"Worker_Carrier",
		"farm":"Worker_Farmer", "lumber":"Worker_Lumberjack", "smith":"Worker_Smith"
	}.get(building, "")
	if worker.is_empty():
		return
	var offset := Vector3(3.2 if building == "farm" else (-3.4 if building == "lumber" else 0.0), 0.0, 2.8)
	if building in ["hall", "starterHall"]:
		offset.z = 4.1 if building == "starterHall" else 5.2
	if offset_override is Vector3:
		# reworked levels keep the worker on open ground clear of their new stairs and posts
		offset = offset_override
	var p := ground_point(base + offset)
	var actor := add_model(workers, data.models[worker].path, model_transform(p.x, p.y, p.z, 0.0, 1.25))
	actor.set_meta("base", base + offset)
	actor.set_meta("building", building)
	for player: AnimationPlayer in actor.find_children("*", "AnimationPlayer", true, false):
		var motions := Animation.new()
		for clip in player.get_animation_list():
			if clip == "RESET":
				continue
			var part: Animation = player.get_animation(clip)
			motions.length = maxf(motions.length, part.length)
			for track in range(part.get_track_count()):
				part.copy_track(track, motions)
		if motions.get_track_count() > 0:
			motions.loop_mode = Animation.LOOP_LINEAR
			var library := AnimationLibrary.new()
			library.add_animation("work", motions)
			player.add_animation_library("ambient", library)
			player.play("ambient/work")

func present_workers(time: float) -> void:
	var phase := fposmod(time, 12.0) / 12.0 * TAU
	for actor: Node3D in workers.get_children():
		var p: Vector3 = actor.get_meta("base")
		var kind: String = actor.get_meta("building")
		var on_screen := camera.is_position_in_frustum(p + Vector3.UP)
		actor.visible = on_screen
		actor.process_mode = Node.PROCESS_MODE_INHERIT if on_screen else Node.PROCESS_MODE_DISABLED
		if not on_screen:
			continue
		if kind in ["hall", "starterHall"]:
			p += Vector3(sin(phase) * 1.65, 0.0, cos(phase) * 0.42)
			p = ground_point(p) + Vector3.UP * absf(sin(time * 5.0)) * 0.035
			actor.rotation.y = atan2(cos(phase) * 1.65, -sin(phase) * 0.42)
		else:
			p.y = static_height(p.x, p.z) + (sin(time * 2.0) * 0.025 if kind == "farm" else 0.0)
		actor.position = p

func add_city_detail(parent: Node3D, path: String, p: Vector3) -> void:
	var detail := add_model(parent, path, Transform3D(Basis.IDENTITY, p))
	for mesh in detail.find_children("*", "MeshInstance3D", true, false):
		mesh.material_override = scenery_material

func sync_parade(army: Dictionary, district: Variant) -> void:
	# The parade site depends on building markers and standing trees as well as the army.
	var key := JSON.stringify([army, district, geometries.get("vegetation_signature", ""),
		place_markers.map(func(marker): return [marker.position.x, marker.position.z])])
	if key == geometries.get("parade_signature", ""):
		return
	geometries.parade_signature = key
	for child in parade.get_children():
		child.free()
	parade_slots = Formations.parade_slots(army, data.englishRoster)
	if district is Dictionary:
		parade_center = Vector3(district.x, district.elevation, district.z)
		add_model(parade, data.models.garrison27.path, Transform3D(Basis.IDENTITY, parade_center))
	elif not parade_slots.is_empty():
		var low := Vector2(INF, INF)
		var high := Vector2(-INF, -INF)
		for slot in parade_slots:
			low = low.min(slot.offset)
			high = high.max(slot.offset)
		var center := (low + high) * 0.5
		var best := INF
		for z in range(-42, 43, 2):
			for x in range(-42, 43, 2):
				var candidate := Vector2(x, z)
				var distance := candidate.distance_squared_to(Vector2(0, 8))
				if distance >= best:
					continue
				var size := (high - low) + Vector2(10, 10)
				var rect := Rect2(candidate - size * 0.5, size)
				if place_markers.any(func(marker): return rect.has_point(Vector2(marker.position.x, marker.position.z))):
					continue
				var height := sample_city(x, z)
				if height < 0.0:
					continue
				var clear := true
				for slot in parade_slots:
					var point_2d: Vector2 = candidate + (slot.offset - center) * 0.77
					if absf(sample_city(point_2d.x, point_2d.y) - height) > 1.65:
						clear = false
						break
					if near_standing_tree(point_2d, 3.24 if slot.mounted else 1.44):
						clear = false
					if not clear:
						break
				if clear:
					best = distance
					parade_center = Vector3(x, height, z)
		if best == INF:
			parade_slots.clear()
			return
		for slot in parade_slots:
			slot.offset = (slot.offset - center) * 0.77
	for slot in parade_slots:
		var p := parade_center + Vector3(slot.offset.x, 0.0, slot.offset.y)
		if not district is Dictionary:
			p.y = sample_city(p.x, p.z)
		slot.position = p

func near_standing_tree(p: Vector2, radius_squared: float) -> bool:
	var cell := Vector2i(floori(p.x / 4.0), floori(p.y / 4.0))
	for z in range(-1, 2):
		for x in range(-1, 2):
			for tree: Vector2 in standing_tree_cells.get(cell + Vector2i(x, z), []):
				if p.distance_squared_to(tree) < radius_squared:
					return true
	return false

func present_parade() -> void:
	if parade_slots.is_empty():
		return
	var made := 0
	for i in range(parade_slots.size()):
		var slot := parade_slots[i]
		var existing := parade.get_node_or_null(NodePath("rank" + str(i))) as Node3D
		var visible_rank := camera.is_position_in_frustum(slot.position + Vector3.UP)
		if existing != null:
			existing.visible = visible_rank
			existing.process_mode = Node.PROCESS_MODE_INHERIT if visible_rank else Node.PROCESS_MODE_DISABLED
		elif visible_rank and made < 4 and data.unitModels.has(slot.id):
			var actor := add_warrior(parade, data.unitModels[slot.id].field, Transform3D(Basis.IDENTITY, slot.position))
			actor.name = "rank" + str(i)
			play_animation(actor, "Idle", "", -1.0, fposmod(float(i) * 0.381966, 1.0))
			made += 1

func present_creatures(state: Dictionary, server_ms: float, delta: float) -> void:
	refresh_view_planes()
	var rows: Array = state.world.encounters if map_name == "world" else state.get("encounters", [])
	var armies: Array = state.world.armies if map_name == "world" else state.get("armies", [])
	var battles := {}
	# Armies on the way to a creature, and armies leaving a creature they slew.
	var approaches := {}
	var leaving := {}
	for army in armies:
		if army.status == "fighting":
			battles[army.target] = army
		elif army.status == "outbound":
			approaches[army.target] = army
		elif army.status == "returning" and server_ms - float(army.get("returnStartsAt", server_ms)) < CORPSE_MS:
			leaving[army.target] = army
	creature_markers.clear()
	creature_clear.clear()
	var retained := {}
	var known := {}
	var cues := {}
	var created := false
	for encounter in rows:
		var slain: bool = encounter.status == "defeated" or int(encounter.get("hp", 1)) <= 0
		var id: String = encounter.id
		# A creature under attack stays on the field for the whole fight even when the
		# server has already recorded the outcome (status/hp are final at battle start);
		# a slain one lies there a little longer while the army leaves.
		var corpse: bool = slain and leaving.has(id) and not battles.has(id)
		if slain and not battles.has(id) and not corpse:
			continue
		var species := creature_species(encounter)
		if species.is_empty():
			species = "velkor"
		if not data.creatureModels.has(species):
			continue
		var p := point(encounter.position)
		var heading := 0.0
		var moving: bool = encounter.get("behavior", "") == "roaming"
		var ground_speed := 0.0
		var path: Array = encounter.get("patrol", [])
		known[id] = true
		if battles.has(id) or corpse:
			path = []
			moving = false
		if map_name == "world" and encounter.status == "alive" and path.size() >= 2:
			var phase := fposmod(server_ms, 16000.0)
			var fraction := clampf(phase / 4000.0 - 1.0, 0.0, 1.0) if phase < 12000.0 else 4.0 - phase / 4000.0
			var a := point(path[0])
			var b := point(path[1])
			p = a.lerp(b, fraction)
			heading = atan2(b.x - a.x, b.z - a.z) + (PI if phase >= 8000.0 else 0.0)
			moving = (phase >= 4000.0 and phase < 8000.0) or phase >= 12000.0
			ground_speed = Vector2(b.x - a.x, b.z - a.z).length() / 4.0
		elif encounter.status == "alive" and path.size() > 2:
			var route: Dictionary = patrol_routes.get(id, {})
			if route.get("source", []) != path:
				route = route_for(path)
				patrol_routes[id] = route
			var phase := fposmod(maxf(0.0, server_ms - float(encounter.get("spawnedAt", server_ms))), 20000.0)
			var fraction := (phase - 4000.0) / 16000.0
			p = along_route(route, fraction)
			var direction := along_route(route, fraction + 0.02) - p
			heading = atan2(direction.x, direction.z)
			moving = phase >= 4000.0
			ground_speed = float(route.distances[-1]) / 16.0 if not route.distances.is_empty() else 0.0
		p = ground_point(p)
		creature_markers.append({"position":p + Vector3.UP * 2.5, "id":id, "kind":"encounter", "item":encounter})
		# Drawn while its body is inside the camera frustum and nearer than the end
		# of the depth fog (beyond it nothing is visible). A fixed 54/64 m radius
		# around the camera target hid creatures that were still on screen: the
		# phone's wide landscape view reaches ~76 m to the sides at the default zoom.
		var close_enough := sphere_in_view(p + Vector3.UP * 1.5, creature_body(encounter).x + 2.5) \
			and camera.global_position.distance_to(p) < camera.environment.fog_depth_end
		var hunter: Dictionary = battles.get(id, approaches.get(id, leaving.get(id, {})))
		var plan: Dictionary = army_routes.get(hunter.get("id", ""), {}).get("engage", {}) if not hunter.is_empty() else {}
		if approaches.has(id) and not plan.is_empty() and not corpse:
			# Target of a march: a red ring under it, like a marked prey.
			battle_fx.ring(p, float(plan.body.x) + 1.4 * beast_k, Color("#e5483a"))
			if server_ms >= float(plan.get("halt_at", INF)) - 3000.0:
				# Open the canopy before the column arrives, so the charge is seen.
				fight_positions[id] = p
				fight_cores[id] = float(plan.get("clear", 0.0))
		if corpse:
			fight_positions[id] = p
			fight_cores[id] = float(plan.get("clear", 0.0))
		if not close_enough or (map_name == "world" and camera_zoom > 132.0):
			continue
		# World map: a creature is about as tall as the trees there (WORLD_CREATURE_SCALE),
		# so the crowns around it fade like those beside a marching column; it stays in
		# sight and can be tapped. Stamped by the next present_armies.
		if map_name == "world" and not slain:
			creature_clear.append(Vector3(p.x, p.z, creature_body(encounter).x + CREATURE_GLADE_M))
		var actor := creatures.get_node_or_null(NodePath(id)) as Node3D
		if actor == null:
			if created:
				continue
			var variant := clampi(int(encounter.level), 1, 3)
			var model_path := CreatureVisuals.model_path(species, variant, data.creatureModels[species][variant - 1])
			var scene := scene_resource(model_path)
			actor = scene.instantiate() as Node3D
			actor.name = id
			actor.position = p
			actor.rotation.y = heading + CREATURE_YAW
			var actor_k := creature_scale(variant) * beast_k * CreatureVisuals.display_scale(species)
			actor.scale = Vector3.ONE * actor_k
			creatures.add_child(actor)
			CreatureVisuals.install(actor, species, variant, actor_k)
			CombatV010.install(actor, "creature", model_path)
			created = true
		retained[id] = true
		actor.show()
		actor.process_mode = Node.PROCESS_MODE_INHERIT
		actor.set_meta("last_visible_ticks", Time.get_ticks_msec())
		# creatures-v2: LOD1/LOD2 by view distance, with hysteresis from the shown LOD.
		CreatureVisuals.update_lod(actor, camera)
		var clip := "Walk" if moving else "Idle"
		var clip_phase := -1.0
		var turn_rate := 10.0
		# Combat v0.1.0: exact clip and server-derived clip time for this creature.
		var v010 := CombatV010.owns(actor)
		var v010_clip := &""
		var v010_time := -1.0
		var bite := CombatV010.creature_attack_window(actor) if v010 else Vector2(560.0, 430.0)
		# creatures-v2: the special attack (charge, pounce, tusk sweep, shockwave) has its own clip timing.
		var special := CombatV010.creature_attack_window(actor, &"attack_b") if v010 else bite
		var v2 := CreatureVisuals.owns(actor)
		var attack_w := bite
		var motion := Vector2.ZERO
		if approaches.has(id) and not plan.is_empty():
			# The army halts in front of it: the creature turns to face it and roars.
			var halt_at := float(plan.get("halt_at", INF))
			if server_ms >= halt_at - 900.0:
				heading = float(plan.yaw)
				turn_rate = 5.0
				if server_ms >= halt_at and server_ms < halt_at + ROAR_MS:
					clip = "Roar"
					clip_phase = (server_ms - halt_at) / ROAR_MS
			if server_ms >= halt_at and not corpse:
				# The fight has begun on screen before the server's battle arrives
				# (present_armies `engaging`): the crowd swings, the creature fights back
				# at the shield wall and shows its full health.
				var army: Dictionary = approaches[id]
				var route: Dictionary = army_routes.get(army.id, {})
				var elapsed := server_ms - float(army.get("battleAt", army.get("arrivesAt", server_ms)))
				if not announced_fights.has(army.id):
					announced_fights[army.id] = true
					fight_started.emit(str(army.id), p)
				fight_positions[id] = p
				fight_cores[id] = float(plan.get("clear", 0.0))
				if clip != "Roar":
					for feint in route.get("feints", []):
						if elapsed >= float(feint.at) - bite.x and elapsed <= float(feint.at) + bite.y:
							var target: Variant = route.get("member_at", {}).get(str(feint.target))
							if target != null:
								var toward := atan2((target as Vector3).x - p.x, (target as Vector3).z - p.z)
								heading += clampf(angle_difference(heading, toward), -0.75, 0.75)
							turn_rate = 14.0
							clip = "Attack"
							clip_phase = (elapsed - float(feint.at) + 260.0) / 690.0
							if v010:
								v010_clip = &"attack_a"
								v010_time = (elapsed - float(feint.at) + bite.x) / 1000.0
							break
					if clip != "Attack" and v010:
						v010_clip = &"combat_idle"
				var spec: Dictionary = encounter.get("spec", {})
				var title := "%s · %s" % [spec.get("name", species), ["I", "II", "III"][clampi(int(encounter.get("level", 1)), 1, 3) - 1]]
				battle_fx.health(p + Vector3.UP * creature_top(encounter, actor), title, 1.0, 1.0, Color("#d8402c"),
					clampf(camera_zoom / 46.0, 0.6, 2.5) if map_name == "world" else clampf(camera_zoom / 40.0, 0.6, 2.5))
		if battles.has(id):
			var army: Dictionary = battles[id]
			var elapsed := server_ms - float(army.battleAt)
			var route: Dictionary = army_routes.get(army.id, {})
			heading = float(plan.yaw) if not plan.is_empty() else float(route.get("heading", 0.0)) + PI
			var events: Array = army_battle_events(army)
			var hit := -INF
			var attack := -INF
			var charge := false
			var victim := ""
			var striker := ""
			var hit_span := 480.0 if v010 else 420.0
			for reaction in battle_timeline(army, encounter, events).reactions:
				if float(reaction[0]) > elapsed:
					break
				if elapsed - float(reaction[0]) < hit_span:
					hit = float(reaction[0])
					striker = reaction[1]
			for event in events:
				var at := float(event[0]) if event is Array else float(event.at)
				var kind: String = event[1] if event is Array else event.kind
				var w := special if v2 and CreatureVisuals.is_special(kind) else bite
				if kind == "soldier_attack":
					continue
				elif at >= elapsed - w.y and at <= elapsed + w.x and attack == -INF:
					attack = at
					attack_w = w
					charge = CreatureVisuals.is_special(kind) if v2 else kind == "antler_charge"
					victim = "%s:%d" % [event[2], int(event[3])] if event is Array else "%s:%d" % [event.unitId, int(event.index)]
			if attack == -INF:
				# Between its server attacks it swipes at the shield wall (beast_feints).
				for feint in route.get("feints", []):
					if elapsed >= float(feint.at) - bite.x and elapsed <= float(feint.at) + bite.y:
						attack = float(feint.at)
						victim = str(feint.target)
						charge = false
			var fallen_at := present_battle_fx(id, p, encounter, army, elapsed, events)
			fight_cores[id] = float(plan.get("clear", 0.0))
			if fallen_at > -INF and elapsed >= fallen_at:
				attack = -INF
				hit = -INF
				clip = "Death"
				clip_phase = clampf((elapsed - fallen_at) / 1200.0, 0.0, 1.0)
				v010_time = (elapsed - fallen_at) / 1000.0
				# The corpse that follows plays on the same fall (server time of the killing blow).
				actor.set_meta("fell_at", float(army.battleAt) + fallen_at)
			elif attack > -INF:
				# Strike at the soldier the server names, turning toward it within reach.
				var target: Variant = route.get("member_at", {}).get(victim)
				if target != null:
					var toward := atan2((target as Vector3).x - p.x, (target as Vector3).z - p.z)
					heading += clampf(angle_difference(heading, toward), -0.75, 0.75)
				turn_rate = 14.0
				clip = "Alert" if charge and elapsed < attack - 260.0 and not v2 else "Attack"
				clip_phase = (elapsed - attack + 560.0) / 300.0 if clip == "Alert" else (elapsed - attack + 260.0) / 690.0
				if v010:
					# One authored strike from windup to recovery; contact = event.at.
					v010_clip = &"attack_b" if charge else &"attack_a"
					v010_time = (elapsed - attack + attack_w.x) / 1000.0
				if v2:
					# The clip is in place; its manifest says how far the presenter carries the body
					# (charge, pounce): one source of motion, no extra lunge on top.
					motion = CreatureVisuals.motion_at(species, "attack_b" if charge else "attack_a", maxf(0.0, v010_time)) * actor.scale.x
				else:
					var lunge := sin(PI * clampf((elapsed - attack + 210.0) / 590.0, 0.0, 1.0)) * (1.8 if charge else 0.6) * beast_k
					p = ground_point(p + Vector3(sin(heading), 0, cos(heading)) * lunge)
				if charge or elapsed >= attack:
					# The creature's stamp and lunge throw up dust at its feet.
					battle_fx.dust(p, clampf((elapsed - attack + 210.0) / 900.0, 0.0, 1.0), (3.2 if charge else 2.4) * beast_k, float(attack) * 0.001)
				cues[id] = true
				show_battle_cue(id, p, Color("#fcc069") if charge else Color("#e89568"), clip_phase)
			elif hit > -INF:
				clip = "Hit"
				clip_phase = (elapsed - hit) / 420.0
				if v010:
					var shower := strike_shower(route, hit, striker.get_slice(":", 0), int(striker.get_slice(":", 1)))
					v010_clip = CombatV010.creature_hit_clip(actor, route.get("member_at", {}).get(shower), heading)
					v010_time = (elapsed - hit) / 1000.0
				cues[id] = true
				show_battle_cue(id, p, Color("#f3d789"), clip_phase)
			elif elapsed < ROAR_MS and float(plan.get("halt_at", INF)) > float(army.battleAt) - 200.0:
				# No halt before the battle (army met it at once): the roar opens the fight.
				clip = "Roar"
				clip_phase = maxf(0.0, elapsed) / ROAR_MS
		elif corpse:
			# The slain creature lies where it fell, then sinks into the ground.
			var age := server_ms - float(leaving[id].get("returnStartsAt", server_ms))
			if not plan.is_empty():
				heading = float(plan.yaw)
			else:
				heading = actor.rotation.y - CREATURE_YAW
			clip = "Death"
			clip_phase = 1.0
			if v2:
				# creatures-v2: the fall plays on from the killing blow instead of popping to the last frame.
				# A long fight is not stretched (CombatPresentation) and ends on that blow, so the whole fall
				# happens here; a stretched one began it inside the fight (fell_at) and continues seamlessly.
				var ended := float(leaving[id].get("returnStartsAt", server_ms))
				var fell := float(actor.get_meta("fell_at", ended))
				if fell < float(leaving[id].get("battleAt", -INF)):
					fell = ended # a mark from an earlier fight of this actor
				v010_time = maxf(0.0, server_ms - fell) / 1000.0
			p.y -= smoothstep(CORPSE_MS - 2400.0, CORPSE_MS, age) * 2.6 * actor.scale.y
		actor.rotation.y = lerp_angle(actor.rotation.y, heading + CREATURE_YAW, 1.0 - exp(-turn_rate * delta))
		if v2:
			# Smoothed anchor (server position) plus the clip's own controller motion.
			var anchor: Vector3 = actor.get_meta("anchor", actor.position)
			anchor = anchor.lerp(p, 1.0 - exp(-5.0 * delta))
			actor.set_meta("anchor", anchor)
			var yaw := actor.rotation.y - CREATURE_YAW
			var offset := Vector3(sin(yaw), 0, cos(yaw)) * motion.x + Vector3(-cos(yaw), 0, sin(yaw)) * motion.y
			actor.position = ground_point(anchor + offset) if motion != Vector2.ZERO else anchor
		else:
			actor.position = actor.position.lerp(p, 1.0 - exp(-5.0 * delta))
		if v010:
			if v010_clip.is_empty():
				v010_clip = CombatV010.creature_clip(actor, clip)
				if clip == "Idle" and battles.has(id):
					v010_clip = &"combat_idle"
			if clip == "Death" and v010_time < 0.0:
				v010_time = INF # corpse: hold the grounded last frame
			elif clip == "Roar":
				v010_time = clip_phase * ROAR_MS / 1000.0
			var tempo := 1.0
			if v2 and clip == "Walk" and ground_speed > 0.0:
				# Walk tempo follows the patrol's real ground speed: hooves and paws stay planted.
				tempo = clampf(ground_speed / maxf(0.05, CreatureVisuals.clip_speed(species, "Walk") * actor.scale.x), 0.35, 2.5)
			CombatV010.drive(actor, v010_clip, v010_time, tempo)
			if v2:
				# Runes, veins and seams go out over the death clip and stay out on the corpse.
				var death_s := float(CreatureVisuals.clip_row(species, "death").get("length_s", 2.0))
				CreatureVisuals.set_life(actor, 0.0 if clip == "Death" and v010_time >= death_s else (1.0 - clampf(v010_time / death_s, 0.0, 1.0) if clip == "Death" else 1.0))
			actor.set_meta("clip", clip)
		elif clip_phase >= 0.0 or actor.get_meta("clip", "") != clip:
			play_animation(actor, clip, "Idle", clip_phase)
			actor.set_meta("clip", clip)
		# A light contact overlays the spine without restarting Attack. Death has
		# already won the state selection and never receives this additive layer.
		# (Legacy only: v0.1.0 has no verified bone mask for an overlay.)
		if clip=="Attack" and battles.has(id) and not v010:
			var army: Dictionary=battles[id]
			var elapsed:=server_ms-float(army.battleAt)
			var last_hit:=-INF
			for event in army_battle_events(army):
				var row:=event_row(event)
				if row[1]=="soldier_attack" and float(row[0])<=elapsed:last_hit=float(row[0])
			additive_hit(actor,(elapsed-last_hit)/320.0)
	retain_hidden_actors(creatures, known, retained, MAX_HIDDEN_CREATURES)
	# Clear the canopy around the fight closest to the camera centre.
	var focus_wanted := 0.0
	var focus_at := focus_centre
	var core_at := focus_core
	var core_wanted := 0.0
	var best := INF
	for fight_id in fight_positions:
		var at: Vector3 = fight_positions[fight_id]
		var gap := Vector2(at.x - camera_target.x, at.z - camera_target.z).length_squared()
		if gap < best:
			best = gap
			focus_at = at
			core_at = at
			core_wanted = float(fight_cores.get(fight_id, 0.0))
			# The world map's smaller crowd needs a smaller clearing (it still covers
			# the whole crowd and the trees in front of it).
			focus_wanted = 19.0 if map_name == "city" else maxf(12.0 * beast_k, core_wanted + 3.0)
	fight_positions.clear()
	fight_cores.clear()
	if is_instance_valid(placement_plate):
		# Building being placed: open the canopy around it so the ghost and plot show.
		focus_at = placement_position()
		focus_wanted = 15.0
	if focus_wanted > 0.0:
		# Trees between the camera and the fight hide it most: shift the clearing toward the camera.
		var toward := camera.global_position - focus_at
		toward.y = 0.0
		if toward.length_squared() > 0.01:
			focus_at += toward.normalized() * focus_wanted * 0.35
	update_battle_focus(focus_at, focus_wanted, delta, core_at, core_wanted)
	foot_contacts.draw(self,server_ms)
	combat_audio.consume(self)
	battle_fx.finish()
	if "--combat-debug" in OS.get_cmdline_user_args() and Time.get_ticks_msec() >= next_combat_debug_ms:
		if not is_instance_valid(combat_debug):
			combat_debug = load("res://src/combat_debug.gd").new()
			add_child(combat_debug)
		combat_debug.sample(self)
		next_combat_debug_ms = Time.get_ticks_msec() + 250
	for cue in effects.get_children():
		if not cues.has(String(cue.name)):
			cue.queue_free()

const REACTION_GAP_MS := 360.0

# Damage timeline of one battle from the server events: soldier hits with the
# creature's remaining hp, and the creature's strikes on formation members.
var fx_timelines := {}

func battle_timeline(army: Dictionary, encounter: Dictionary, events: Array) -> Dictionary:
	var cached: Dictionary = fx_timelines.get(army.id, {})
	# Same list object and length as last frame (no new poll): no deep comparison.
	if is_same(cached.get("source"), events) and int(cached.get("count", -1)) == events.size():
		return cached
	if not cached.is_empty() and cached.get("source") == events:
		cached.source = events
		cached.count = events.size()
		return cached
	var spec: Dictionary = encounter.get("spec", {})
	var start_hp := float(spec.get("hp", encounter.get("maxHp", encounter.get("hp", 1))))
	var hits: Array = []
	var strikes: Array = []
	# Server order breaks ties: a volley lands on one tick, and an unstable sort would
	# shuffle its blows (the hp they leave would then jump back and forth).
	var order := range(events.size())
	var time_of := func(event) -> float: return float(event[0]) if event is Array else float(event.at)
	order.sort_custom(func(a, b): return time_of.call(events[a]) < time_of.call(events[b]) or \
		(time_of.call(events[a]) == time_of.call(events[b]) and a < b))
	var ordered := order.map(func(index): return events[index])
	var hp := start_hp
	for event in ordered:
		var e := event_row(event)
		if e[1] == "soldier_attack":
			var after: float = float(e[4]) if e.size() > 4 and e[4] != null else hp
			# The blow's own damage when the server names it (a world fight lists only
			# the drawn soldiers, so the hp step between them includes unseen blows).
			var damage: float = float(e[5]) if e.size() > 5 and e[5] != null else maxf(0.0, hp - after)
			# Blows landing on the same server tick (a volley) get a rank, so their
			# numbers pop one after another instead of printing over each other.
			var rank: int = hits[-1][3] + 1 if not hits.is_empty() and float(hits[-1][0]) == float(e[0]) else 0
			hits.append([float(e[0]), damage, after, rank, combat_view.event_id(army,event),str(e[2]),int(e[3])])
			hp = after
		else:
			strikes.append([float(e[0]), "%s:%d" % [e[2], int(e[3])], e[1],float(e[5]) if e.size()>5 and e[5]!=null else 0.0,float(e[4]) if e.size()>4 and e[4]!=null else 1.0,combat_view.event_id(army,event)])
	# The creature's reaction to blows: one reaction starts at a blow and is not
	# restarted by the next blows for REACTION_GAP_MS. Restarting at every blow
	# (a volley lands every 50-300 ms) kept the 0.48 s clip in its first 60-180 ms,
	# 11-42 times per fight: the creature twitched instead of recoiling.
	var reactions: Array = []
	for hit in hits:
		if reactions.is_empty() or float(hit[0]) - float(reactions[-1][0]) >= REACTION_GAP_MS:
			reactions.append([float(hit[0]), "%s:%d" % [hit[5], int(hit[6])]])
	cached = {"source": events, "count": events.size(), "hits": hits, "strikes": strikes, "reactions": reactions, "max": maxf(1.0, start_hp)}
	fx_timelines[army.id] = cached
	return cached

func present_battle_fx(id: String, p: Vector3, encounter: Dictionary, army: Dictionary, elapsed: float, events: Array) -> float:
	var timeline := battle_timeline(army, encounter, events)
	fight_positions[id] = p
	if not announced_fights.has(army.id) and elapsed < 2500.0:
		announced_fights[army.id] = true
		fight_started.emit(str(army.id), p)
	var route: Dictionary = army_routes.get(army.id, {})
	var centre: Vector3 = route.get("position", p)
	var members: Dictionary = route.get("member_at", {})
	var plan: Dictionary = route.get("engage", {})
	if plan.is_empty():
		battle_fx.ring(p.lerp(centre, 0.5), maxf(7.5 * unit_k, p.distance_to(centre) * 0.5 + 6.0 * unit_k), Color("#62e07a"))
	else:
		# The prey's red ring stays under it for the whole fight.
		battle_fx.ring(p, float(plan.body.x) + 1.4 * beast_k, Color("#e5483a"))
	var hp := float(timeline.max)
	var recent := hp
	for hit in timeline.hits:
		var at := float(hit[0])
		if at > elapsed:
			break
		if elapsed - at > 600.0:
			recent = float(hit[2])
		hp = float(hit[2])
		var age := elapsed - at
		if age <= 180.0:
			# From the drawn soldier that shows this blow (it may be lent, see battle_events).
			var attacker: Vector3=members.get(strike_shower(route,float(hit[0]),str(hit[5]),int(hit[6])),centre)
			var direction: Vector3=(attacker-p).normalized()
			var contact:=p+direction*minf(creature_body(encounter).y,attacker.distance_to(p)*.5)
			battle_fx.spark(contact,age/180.0,Color("#9a8060") if creature_species(encounter) in ["dragor","kamneklyk"] else Color("#94745a"),(.70 if str(hit[5]) in ["ENG-01","ENG-06"] else .45)*beast_k,fposmod(at*.013,1.0))
	# Same target and exact authoritative tick only. Final contact remains separate.
	var numbers := {}
	for hit in timeline.hits:
		var age := elapsed-float(hit[0])
		if age < 0.0 or age > 900.0 or float(hit[1]) <= 0.0: continue
		var final := float(hit[2]) <= 0.0
		var key := str(hit[0])+('/final' if final else '/group')
		if not numbers.has(key): numbers[key] = {"damage":0.0,"ids":[],"age":age,"final":final}
		numbers[key].damage += float(hit[1])
		numbers[key].ids.append(hit[4])
	for number in numbers.values():
		var caption := "-%d" % roundi(number.damage)
		if number.ids.size() > 1: caption += " ×%d" % number.ids.size()
		battle_fx.number(p,caption,number.age/900.0,Color("#ffe7a8"),number.final,number.ids,id,number.final)
	for strike in timeline.strikes:
		var age := elapsed - float(strike[0])
		if age < -80.0 or age > 900.0:
			continue
		var target: Vector3 = members.get(strike[1], centre)
		battle_fx.slash(p,target,(age+80.0)/200.0,Color("#a29a85"),(1.2 if strike[2]=="antler_charge" else .8)*beast_k)
		if age>=0.0 and age<=220.0:
			battle_fx.spark(target,age/220.0,Color("#a69b83"),.65*beast_k,fposmod(float(strike[0])*.007,1.0))
		if age>=0.0 and float(strike[3])>0:
			battle_fx.number(target,"-%d"%roundi(strike[3]),age/900.0,Color("#e8aa96"),strike[4]<=0,[strike[5]],id+"/"+str(strike[1]),strike[4]<=0)
	var spec: Dictionary = encounter.get("spec", {})
	var title := "%s · %s" % [spec.get("name", creature_species(encounter)), ["I", "II", "III"][clampi(int(encounter.get("level", 1)), 1, 3) - 1]]
	var height := creature_top(encounter, creatures.get_node_or_null(NodePath(id)) as Node3D)
	var fallen_at := -INF
	if not timeline.hits.is_empty() and float(timeline.hits[-1][2]) <= 0.0:
		fallen_at = float(timeline.hits[-1][0])
	if fallen_at == -INF or elapsed < fallen_at + 900.0:
		battle_fx.health(p + Vector3.UP * height, title, hp / float(timeline.max), recent / float(timeline.max), Color("#d8402c"),
			clampf(camera_zoom / 46.0, 0.6, 2.5) if map_name == "world" else clampf(camera_zoom / 40.0, 0.6, 2.5))
	battle_fx.last_battle_msec = Time.get_ticks_msec()
	battle_fx.last_battle_events = events.size()
	return fallen_at

func show_battle_cue(id: String, p: Vector3, color: Color, phase: float) -> void:
	var cue := effects.get_node_or_null(NodePath(id)) as MeshInstance3D
	if cue == null:
		var ring := TorusMesh.new()
		ring.inner_radius = 0.88
		ring.outer_radius = 1.0
		ring.rings = 24
		ring.ring_segments = 6
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		cue = MeshInstance3D.new()
		cue.name = id
		cue.mesh = ring
		cue.material_override = material
		cue.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		effects.add_child(cue)
	var progress := clampf(phase, 0.0, 1.0)
	cue.position = p + Vector3.UP * 0.14
	cue.scale = Vector3.ONE * (1.1 + 2.2 * progress) * beast_k
	cue.material_override.albedo_color = Color(color, 0.65 * (1.0 - progress))

func terrain_y(p: Vector3) -> float:
	if world_heights.is_empty():
		return p.y
	var field := world_heights
	var x := clampf((p.x + 150.0) / 1.25, 0, 240)
	var z := clampf((p.z + 120.0) / 1.25, 0, 192)
	var ix := mini(floori(x), 239)
	var iz := mini(floori(z), 191)
	var a := iz * 241 + ix
	var b := a + 241
	var dx := x - ix
	var dz := z - iz
	if dx + dz <= 1.0:
		return field[a] + (field[a + 1] - field[a]) * dx + (field[b] - field[a]) * dz
	return field[b + 1] + (field[b] - field[b + 1]) * (1.0 - dx) + (field[a + 1] - field[b + 1]) * (1.0 - dz)

# The points of a march route; in the city a route through the wall goes out of
# the main gate (CityWalls.gate_path).
func march_points(path: Array) -> PackedVector3Array:
	var points := PackedVector3Array()
	for entry in path:
		points.append(point(entry))
	if map_name == "city":
		points = walls.gate_path(points)
	return points

# Same as march_points, as {x, y, z} rows for the small route map of the march window.
func march_path(path: Array) -> Array:
	var rows: Array = []
	for p in march_points(path):
		rows.append({"x": p.x, "y": p.y, "z": p.z})
	return rows

func route_for(path: Array, through_gate := false) -> Dictionary:
	var points := PackedVector3Array()
	var distances := PackedFloat32Array()
	for next in (march_points(path) if through_gate else PackedVector3Array(path.map(point))):
		var total := 0.0
		if not points.is_empty():
			var previous := points[-1]
			total = distances[-1] + Vector2(next.x - previous.x, next.z - previous.z).length()
		points.append(next)
		distances.append(total)
	# Ferry legs of a city route (the server's ferry: one straight step across the
	# river along a line of constant z, longer than a grid step, over water).
	var ferry := PackedByteArray()
	ferry.resize(points.size())
	ferry.fill(0)
	if map_name == "city":
		for i in range(1, points.size()):
			var a := points[i - 1]
			var b := points[i]
			var mid := (a + b) * 0.5
			if absf(a.z - b.z) < 0.01 and absf(a.x - b.x) > 2.01 and sample_city(mid.x, mid.z) < -0.25:
				ferry[i] = 1
	return {"source":path,"points":points,"distances":distances,"ferry":ferry}

# Whether the army at this fraction of its route is on a ferry leg, and how far
# along that leg (0..1); the raft also covers a short stretch at both banks for
# boarding and landing.
# 0 on land, 1 on the raft, in between over FERRY_RAMP_M before boarding and
# after landing. The formation packs onto the raft (RAFT_PACK) and stands on its
# deck; switched in one frame at the bank, rear soldiers jumped ~6 m forward.
const FERRY_RAMP_M := 4.0

func ferry_weight(route: Dictionary, fraction: float) -> float:
	var ferry: PackedByteArray = route.get("ferry", PackedByteArray())
	if not ferry.has(1):
		return 0.0
	var distances: PackedFloat32Array = route.distances
	var travelled := clampf(fraction, 0, 1) * distances[-1]
	var weight := 0.0
	for i in range(1, ferry.size()):
		if ferry[i] != 1:
			continue
		var board := distances[i - 1] - 1.5
		var land := distances[i] + 1.5
		if travelled >= board and travelled <= land:
			return 1.0
		var gap := board - travelled if travelled < board else travelled - land
		weight = maxf(weight, 1.0 - clampf(gap / FERRY_RAMP_M, 0.0, 1.0))
	return smoothstep(0.0, 1.0, weight)

func ferry_at(route: Dictionary, fraction: float) -> float:
	var ferry: PackedByteArray = route.get("ferry", PackedByteArray())
	if not ferry.has(1):
		return -1.0
	var distances: PackedFloat32Array = route.distances
	var travelled := clampf(fraction, 0, 1) * distances[-1]
	for i in range(1, ferry.size()):
		if ferry[i] == 1 and travelled >= distances[i - 1] - 1.5 and travelled <= distances[i] + 1.5:
			return clampf((travelled - distances[i - 1]) / maxf(0.01, distances[i] - distances[i - 1]), 0.0, 1.0)
	return -1.0

# A log raft with rails and a pair of sweeps: the ferry that carries a city army
# over the river (no boat model ships with the game, so it is built from primitives).
const FERRY_DECK := -0.9
func make_raft(width: float, length: float) -> Node3D:
	var raft := Node3D.new()
	raft.name = "Ferry"
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("#7a5634")
	wood.roughness = 0.85
	var dark := StandardMaterial3D.new()
	dark.albedo_color = Color("#4f3620")
	dark.roughness = 0.9
	var logs := maxi(4, ceili(width / 0.62))
	var log_mesh := CylinderMesh.new()
	log_mesh.top_radius = 0.31
	log_mesh.bottom_radius = 0.31
	log_mesh.height = length
	log_mesh.radial_segments = 8
	log_mesh.rings = 1
	log_mesh.material = wood
	for k in logs:
		var log := MeshInstance3D.new()
		log.mesh = log_mesh
		log.rotation = Vector3(PI * 0.5, 0.0, 0.0)
		log.position = Vector3(-width * 0.5 + (k + 0.5) * width / logs, -0.32, 0.0)
		raft.add_child(log)
	var beam_mesh := BoxMesh.new()
	beam_mesh.size = Vector3(width + 0.5, 0.16, 0.34)
	beam_mesh.material = dark
	for z in [-length * 0.42, 0.0, length * 0.42]:
		var beam := MeshInstance3D.new()
		beam.mesh = beam_mesh
		beam.position = Vector3(0.0, 0.02, z)
		raft.add_child(beam)
	var rail_mesh := BoxMesh.new()
	rail_mesh.size = Vector3(0.12, 0.12, length * 0.92)
	rail_mesh.material = dark
	var post_mesh := BoxMesh.new()
	post_mesh.size = Vector3(0.14, 0.75, 0.14)
	post_mesh.material = dark
	for side in [-1.0, 1.0]:
		var rail := MeshInstance3D.new()
		rail.mesh = rail_mesh
		rail.position = Vector3(side * (width * 0.5 + 0.1), 0.72, 0.0)
		raft.add_child(rail)
		for z in [-length * 0.44, -length * 0.15, length * 0.15, length * 0.44]:
			var post := MeshInstance3D.new()
			post.mesh = post_mesh
			post.position = Vector3(side * (width * 0.5 + 0.1), 0.37, z)
			raft.add_child(post)
		# Long sweeps over the side, dipping into the water.
		var sweep := MeshInstance3D.new()
		var sweep_mesh := BoxMesh.new()
		sweep_mesh.size = Vector3(3.2, 0.1, 0.22)
		sweep_mesh.material = wood
		sweep.mesh = sweep_mesh
		sweep.position = Vector3(side * (width * 0.5 + 1.3), 0.1, -length * 0.3)
		sweep.rotation = Vector3(0.0, 0.0, side * -0.32)
		raft.add_child(sweep)
	for child in raft.get_children():
		(child as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return raft

func along_route(route: Dictionary, fraction: float) -> Vector3:
	var points: PackedVector3Array = route.points
	var distances: PackedFloat32Array = route.distances
	if points.size() < 2:
		return points[0] if not points.is_empty() else Vector3.ZERO
	var travelled := clampf(fraction, 0, 1) * distances[-1]
	var index := clampi(distances.bsearch(travelled), 1, distances.size() - 1)
	var length := distances[index] - distances[index - 1]
	var weight := (travelled - distances[index - 1]) / length if length > 0.0 else 0.0
	return points[index - 1].lerp(points[index], weight)

func ground_point(p: Vector3) -> Vector3:
	p.y = terrain_y(p) if map_name == "world" else sample_city(p.x, p.z)
	if forest_world != null and maxf(absf(p.x), absf(p.z)) > 56.0:
		p.y = forest_world.height_at(p.x, p.z)  # [forest_rescue_v1 hook] earthworks/bridge
	return p

# Kind of a creature: city creatures carry "species"; the world-map sites (Велькор)
# only name it in spec.id. Without this the world fight had no battle places, no
# charge and no blows: the soldiers just stood beside the creature.
static func creature_species(encounter: Dictionary) -> String:
	var species := str(encounter.get("species", ""))
	if species.is_empty() and encounter.get("spec") is Dictionary:
		species = str(encounter.spec.get("id", ""))
	return species

# One server battle event as [at, kind, unitId, index, hp]. A city battle sends
# objects whose soldier blows carry the creature's hp after the blow as
# "creatureHP" (simulate() in combat.mjs); the world map sends rows already.
static func event_row(event: Variant) -> Array:
	if event is Array:
		return event
	var kind := str(event.get("kind", ""))
	var hp: Variant = event.get("creatureHP", event.get("hp")) if kind == "soldier_attack" else event.get("hp")
	return [float(event.get("at", 0.0)), kind, str(event.get("unitId", "")), int(event.get("index", 0)), hp, event.get("damage")]

# True when two short lists hold the same objects (or equal values). Avoids a
# deep comparison of whole fight timelines on every frame.
static func same_items(a: Variant, b: Array) -> bool:
	if not a is Array or a.size() != b.size():
		return false
	for i in b.size():
		if not is_same(a[i], b[i]) and a[i] != b[i]:
			return false
	return true

# Events of an army's fight. The world map sends only a window around the poll
# (about -1.3 s .. +1.4 s); windows of successive polls are merged per army, so a
# slow answer leaves no gap in the blows and numbers already seen stay known.
func army_battle_events(army: Dictionary) -> Array:
	if army.get("presentation") is Dictionary:
		return army.presentation.get("events", [])
	if army.get("battle") is Dictionary:
		return army.battle.get("events", [])
	var window: Array = army.get("events", [])
	var cache: Dictionary = army_routes.get(str(army.get("id", "")), {})
	if cache.is_empty():
		return window
	var merged: Dictionary = cache.get("merged", {})
	if is_same(cache.get("merged_window_ref"), window) and int(cache.get("merged_window_size", -1)) == window.size() and cache.has("merged_rows"):
		return cache.merged_rows
	cache.merged_window_ref = window
	cache.merged_window_size = window.size()
	if cache.get("merged_window") != window or not cache.has("merged_rows"):
		cache.merged_window = window.duplicate()
		for event in window:
			var e := event_row(event)
			merged["%d|%s|%s|%d" % [roundi(float(e[0])), e[1], e[2], int(e[3])]] = e
		cache.merged = merged
		var rows: Array = merged.values()
		rows.sort_custom(func(a, b): return float(a[0]) < float(b[0]))
		cache.merged_rows = rows
	return cache.merged_rows

# Which drawn soldier shows each server blow (presentation only; HP, numbers and
# the outcome come from the events themselves).
#
# A large party is drawn by up to FIELD_LIMIT representatives, and a hunt puts
# members without a contact place into reserve rows. Build 1018 gave every blow
# of an undrawn or reserve member to a contact member of its type by index
# modulo: one rider in contact received all 44 cavalry blows of a level-3 hunt
# while five riders stood idle, and a soldier can show one swing per ~1.7 s, so
# 1 of 44 cavalry blows and 35-56 % of all blows were drawn.
#
# Now each blow goes to a drawn soldier of its type that is free (its previous
# swing has passed contact by MIN_FOLLOW_MS before this windup starts), in tiers:
#   0: the member itself, then other members in contact (ranged: any place);
#   1: first reserve row (one rank behind the contact arc, within weapon reach);
#   2: second reserve row;
#   3: far reserves (no room within reach): they ride or run in to the creature
#      for the blow and back (time from the distance: 7 m/s mounted, 4.5 m/s on
#      foot, never starting before the blow was known), so their busy window is
#      longer. Build 1018 either left them idle or, when a
#      type had nobody nearer, let them swing at the air 8+ m from the creature.
# Blows nobody is free to show are not drawn (they still change HP/numbers).
# Hits and deaths always stay with their own member. Decisions are remembered in
# `memo` per event, so later polls (more events, merged world windows) never
# move a blow that may already be on screen.
const MIN_FOLLOW_MS: float = CombatV010.MIN_FOLLOW_MS

# The drawn soldier that shows a server blow (decided in battle_events), or the
# blow's own member: sparks and the creature's recoil come from where the swing is.
static func strike_shower(route: Dictionary, at: float, unit: String, index: int) -> String:
	var decided: Variant = route.get("strike_memo", {}).get("%d|%s|%d" % [roundi(at * 10.0), unit, index])
	var shown: String = decided[0] if decided is Array else ""
	return shown if not shown.is_empty() else "%s:%d" % [unit, index]
const RIDE_LEAVE_MS := 250.0
const RIDE_SPEED := 7.0
const RUN_IN_SPEED := 4.5

# True when a blow at `at` (contact, windup `prepare` before it) fits between the
# blows already given to a soldier (sorted contact times) without cutting any
# windup or contact. Usually the new blow is the latest: one comparison.
static func strike_slot_free(times: Array, at: float, prepare: float, follow := MIN_FOLLOW_MS) -> bool:
	if times.is_empty():
		return true
	if at >= float(times[-1]):
		return at - prepare >= float(times[-1]) + follow
	for u in times:
		if not (at - prepare >= float(u) + follow or float(u) - prepare >= at + follow):
			return false
	return true

# Between the server's blows every soldier standing at its battle place keeps
# fighting (presentation only: no number, HP or outcome comes from these swings).
# Up to build 1019 a soldier swung only for a server blow given to it: about one
# swing each in a short hunt, while the crowd stood still around the creature.
# The cadence is a pure function of the member key and the battle clock, so polls,
# rewinds and other devices draw the same swings: one swing (plus the crossbow's
# reload, `recover`) and a rest of 0.2-0.8 s, the phase spread per member; only
# from `from` (the soldier stands at its place), no contact after `until` (the
# creature falls), and never over a server blow this soldier shows: that blow's
# windup, contact and follow-through stay MIN_FOLLOW_MS clear. Returns the contact
# time (battle ms) of the swing whose busy span holds `elapsed`, or -INF.
const AMBIENT_REST_MS := Vector2(200.0, 800.0)

static func ambient_strike(key: String, elapsed: float, from: float, until: float, window: Vector2, recover: float, own: Array) -> float:
	var seed := hash(key)
	var busy := window.x + window.y + recover
	var period := busy + lerpf(AMBIENT_REST_MS.x, AMBIENT_REST_MS.y, float(seed & 1023) / 1023.0)
	var offset := float((seed >> 10) & 1023) / 1023.0 * period
	var start := offset + floorf((elapsed - offset) / period) * period
	if elapsed > start + busy or start < from or start + window.x > until - 120.0:
		return -INF
	for at in own:
		if float(at) - window.x < start + busy + MIN_FOLLOW_MS and start < float(at) + window.y + MIN_FOLLOW_MS:
			return -INF
	return start + window.x

# The creature fights back between its server attacks (presentation only: no
# damage, number or death comes from these). Up to build 1019 a hunt showed just
# the server's one or two creature attacks, and the creature stood still while the
# crowd struck it. Now every 2.4-3.3 s it swipes at one of the foot soldiers in
# front of it (within 80 degrees of its face), who takes the swipe on the raised
# shield. A pure function of the army id, the plan and the battle clock, so every
# poll and device draws the same; none within 2 s of a server creature attack,
# none after the creature falls (`until`), only at soldiers who have a shield clip.
const FEINT_PERIOD_MS := Vector2(2400.0, 3300.0)
const FEINT_FIRST_MS := 2200.0
const FEINT_CLEAR_MS := 2000.0
const BLOCK_WINDOW := Vector2(420.0, 520.0)

func beast_feints(army_id: String, plan: Dictionary, cache: Dictionary, rows: Array, until: float, bite: Vector2, fallen: Dictionary) -> Array:
	var stamp := [rows.size(), until, bite, fallen.size(), plan.get("locked", false), cache.slots.size()]
	if cache.get("feints_stamp") == stamp and cache.get("feints_all") is Array:
		return cache.feints_all
	var beast: Vector3 = plan.beast
	var face: Vector3 = plan.face
	var candidates: Array = []
	for slot in cache.slots:
		var key := "%s:%d" % [slot.id, int(slot.index)]
		if slot.ranged or slot.mounted or fallen.has(key) or not plan.places.has(key) or plan.get("reserves", {}).get(key, false):
			continue
		if slot.id not in ["ENG-01", "ENG-02"]:
			continue # the shield bearers (their models have Shield_Block)
		var place: Vector3 = plan.places[key]
		var to := Vector3(place.x - beast.x, 0.0, place.z - beast.z)
		if to.length_squared() > 0.01 and to.normalized().dot(face) >= cos(deg_to_rad(80.0)):
			candidates.append(key)
	candidates.sort()
	var server: Array = []
	for e in rows:
		var row := event_row(e)
		if row[1] != "soldier_attack":
			server.append(float(row[0]))
	var result: Array = []
	var seed := hash(army_id)
	var period := lerpf(FEINT_PERIOD_MS.x, FEINT_PERIOD_MS.y, float(seed & 1023) / 1023.0)
	if not candidates.is_empty():
		for n in 64:
			var at := FEINT_FIRST_MS + n * period + float(hash("%s#%d" % [army_id, n]) & 1023) / 1023.0 * 0.25 * period
			if at > until - 500.0:
				break
			if server.any(func(t): return absf(t - at) < FEINT_CLEAR_MS):
				continue
			result.append({"at": at, "target": candidates[hash("%s@%d" % [army_id, n]) % candidates.size()]})
	cache.feints_stamp = stamp
	cache.feints_all = result
	return result

# 0 at the reserve place, 1 at the creature: a far reserve comes in for a blow
# with contact at `at` (battle ms) and goes back after it. It sets off `ride_ms`
# before the windup, but never before `known_at`, when the client first had the
# blow; a blow learnt too late is swung from the reserve place instead of jumping.
static func ride_weight(elapsed: float, at: float, prepare: float, ride_ms: float, known_at: float, last_at := NAN) -> float:
	var start := maxf(at - prepare - ride_ms, known_at)
	if start > at - 300.0:
		return 0.0
	var arrived := minf(maxf(at - prepare, start + 300.0), at - 50.0)
	var arrive := smoothstep(start, arrived, elapsed)
	var until := at if is_nan(last_at) else last_at
	var leave := smoothstep(until + RIDE_LEAVE_MS, until + RIDE_LEAVE_MS + ride_ms, elapsed)
	return arrive * (1.0 - leave)

# A far reserve stays at the creature between blows that follow closely (no time
# to go back and come again): the blows form one visit from its first to its last.
static func ride_visits(times: Array, prepare: float, ride_ms: float) -> Array:
	var visits: Array = []
	for at in times:
		if not visits.is_empty() and float(at) - prepare - ride_ms <= float(visits[-1][1]) + RIDE_LEAVE_MS + ride_ms:
			visits[-1][1] = float(at)
		else:
			visits.append([float(at), float(at)])
	return visits

# Where a far reserve meets the creature: its own direction from the creature,
# at the contact gap outside the body outline.
func contact_point(plan: Dictionary, from: Vector3, mounted: bool) -> Vector3:
	var beast: Vector3 = plan.beast
	var out := Vector3(from.x - beast.x, 0.0, from.z - beast.z)
	out = out.normalized() if out.length_squared() > 0.01 else Vector3(plan.face)
	var face: Vector3 = plan.face
	var across := Vector3(face.z, 0.0, -face.x)
	var body: Vector2 = plan.body
	var edge := 1.0 / sqrt(pow(out.dot(face) / body.x, 2) + pow(out.dot(across) / body.y, 2))
	return ground_point(beast + out * (edge + (ENGAGE_GAP + (1.4 if mounted else 0.5)) * unit_k))

func battle_events(army: Dictionary, slots: Array = [], plan: Dictionary = {}, memo: Dictionary = {}, known_at := -INF) -> Dictionary:
	var by_member := {}
	var fallen := {}
	var forced := {}
	var strikers := {}
	var entries: Array = army_battle_events(army)
	var reserve_rows: Dictionary = plan.get("reserve_rows", {})
	var reserves: Dictionary = plan.get("reserves", {})
	var tiers := {}  # unit id -> [tier0 keys, tier1, tier2, tier3]
	var window := {}  # unit id -> Vector2(prepare, follow)
	var drawn := {}
	for slot in slots:
		var key := "%s:%d" % [slot.id, int(slot.index)]
		drawn[key] = true
		if not tiers.has(slot.id):
			tiers[slot.id] = [[], [], [], []]
			window[slot.id] = CombatV010.strike_window(str(slot.id), bool(slot.ranged))
		var row := 0 if slot.ranged or not reserves.get(key, false) else int(reserve_rows.get(key, 4))
		tiers[slot.id][0 if row == 0 else (row if row <= 2 else 3)].append(key)
	var far := {}
	var ride_ms := {}
	var mounted := {}
	for slot in slots:
		mounted["%s:%d" % [slot.id, int(slot.index)]] = bool(slot.get("mounted", false))
	for id in tiers:
		for key in tiers[id][3]:
			far[key] = true
			var place: Variant = plan.get("places", {}).get(key)
			var distance := 6.0
			if place is Vector3 and plan.has("beast"):
				distance = (place as Vector3).distance_to(contact_point(plan, place, mounted[key]))
			ride_ms[key] = clampf(distance / ((RIDE_SPEED if mounted[key] else RUN_IN_SPEED) * unit_k) * 1000.0, 400.0, 1800.0)
			if tiers[id][0].is_empty() and tiers[id][1].is_empty() and tiers[id][2].is_empty():
				forced[key] = true
	# Server order, stable across polls: time, then kind, unit and index.
	var rows: Array = entries.map(func(event): return event_row(event))
	var ordered := true
	for n in range(1, rows.size()):
		if float(rows[n][0]) < float(rows[n - 1][0]):
			ordered = false
			break
	if not ordered:
		rows.sort_custom(func(a, b):
			if float(a[0]) != float(b[0]): return float(a[0]) < float(b[0])
			if str(a[1]) != str(b[1]): return str(a[1]) < str(b[1])
			if str(a[2]) != str(b[2]): return str(a[2]) < str(b[2])
			return int(a[3]) < int(b[3]))
	var assigned := {}  # member key -> contact times of the blows it shows
	var pending: Array = []
	for e in rows:
		var own := "%s:%d" % [e[2], int(e[3])]
		if e[1] != "soldier_attack" or not tiers.has(e[2]):
			if not by_member.has(own): by_member[own] = []
			by_member[own].append(e)
			continue
		var id := "%d|%s|%d" % [roundi(float(e[0]) * 10.0), e[2], int(e[3])]
		if memo.has(id):
			var kept: String = memo[id][0]
			if not kept.is_empty():
				if not by_member.has(kept): by_member[kept] = []
				by_member[kept].append(e)
				if not assigned.has(kept): assigned[kept] = []
				assigned[kept].append(float(e[0]))
				strikers[kept] = true
		else:
			pending.append([id, e, own])
	for item in pending:
		var e: Array = item[1]
		var own: String = item[2]
		var at := float(e[0])
		var span: Vector2 = window[e[2]]
		var chosen := ""
		for tier in 4:
			var keys: Array = tiers[e[2]][tier]
			if keys.is_empty():
				continue
			var order: Array = []
			if tier == 0 and keys.has(own):
				order.append(own)
			var start := int(e[3]) % keys.size()
			for k in keys.size():
				var candidate: String = keys[(start + k) % keys.size()]
				if candidate != own or tier != 0:
					order.append(candidate)
			for candidate in order:
				var free := strike_slot_free(assigned.get(candidate, []), at, span.x)
				if free and tier == 3:
					# Starting a new visit: the rider must be able to arrive before the windup.
					var ride: float = ride_ms.get(candidate, 0.0)
					var times: Array = assigned.get(candidate, [])
					var visiting: bool = not times.is_empty() and at - span.x - ride <= float(times[-1]) + RIDE_LEAVE_MS + ride and at >= float(times[-1])
					free = visiting or at - span.x - ride >= known_at
				if free:
					chosen = candidate
					break
			if not chosen.is_empty():
				break
		memo[item[0]] = [chosen, known_at]
		if chosen.is_empty():
			continue
		if not by_member.has(chosen): by_member[chosen] = []
		by_member[chosen].append(e)
		if not assigned.has(chosen): assigned[chosen] = []
		var times: Array = assigned[chosen]
		times.insert(times.bsearch(at), at)
		strikers[chosen] = true
	for key in by_member:
		var list: Array = by_member[key]
		for n in range(1, list.size()):
			if float(list[n][0]) < float(list[n - 1][0]):
				list.sort_custom(func(a, b): return float(a[0]) < float(b[0]))
				break
	for unit in army.get("fallen", []):
		fallen["%s:%d" % [unit[0], int(unit[1])]] = true
	return {"members":by_member, "fallen":fallen, "forced":forced, "strikers":strikers, "far":far, "windows":window, "ride_ms":ride_ms}

func present_armies(state: Dictionary, server_ms: float) -> void:
	refresh_view_planes()
	battle_fx.begin()
	if fx_warm_frames > 0:
		fx_warm_frames -= 1
		warm_effects()
	for body in fallen_bodies:
		if is_instance_valid(body.node):
			if server_ms >= body.until:
				body.node.queue_free()
			elif CombatV010.owns(body.node):
				CombatV010.drive(body.node, &"death", (server_ms - body.at) / 1000.0)
			else:
				play_animation(body.node, "death", "", (server_ms - body.at) / 1200.0)
	fallen_bodies = fallen_bodies.filter(func(body): return is_instance_valid(body.node) and server_ms < body.until)
	var alive := {}
	var known := {}
	var rows: Array = state.world.armies if map_name == "world" else state.get("armies", [])
	var encounters := {}
	for encounter in (state.world.encounters if map_name == "world" else state.get("encounters", [])):
		encounters[str(encounter.id)] = encounter
	var me := str(state.get("playerId", ""))
	var lines := {}
	army_markers.clear()
	var creation_budget := 6
	# Where soldiers walk outside a fight: the trees there fade (update_march_clearing).
	var walkers := PackedVector2Array()
	# A column mustering while its lane is still being planned (march_lanes.gd).
	var mustering := false
	for army in rows:
		if army.status == "returned":
			continue
		var returning: bool = army.status == "returning"
		var fighting: bool = army.status == "fighting"
		var path: Array = army.get("returnPath", []) if returning else army.get("path", [])
		if path.is_empty():
			continue
		var id: String = army.id
		known[id] = true
		var bag: Dictionary = army.get("returnUnits", army.units) if returning else army.units
		var cache: Dictionary = army_routes.get(id, {})
		army_routes[id] = cache
		if cache.get("source", []) != path:
			cache.merge(route_for(path, true), true)
			cache.source = path
			cache.erase("lane")
		if cache.get("bag", {}) != bag or not cache.has("slots") or cache.get("returning", false) != returning:
			# A recalled march (no battle) turns back where it stands: remember each
			# soldier's place so it walks to its new place in the homeward column
			# instead of appearing there (the rows reverse their order on the way back).
			cache.erase("turn_from")
			cache.erase("turn_ms")
			if returning and not cache.get("returning", false) and army.get("battleAt") == null:
				var walking_actor := actors.get_node_or_null(NodePath(id)) as Node3D
				if walking_actor != null and walking_actor.visible:
					var from := {}
					for unit in walking_actor.get_children():
						if unit is Node3D and unit.name != &"Ferry":
							from[String(unit.name)] = (unit as Node3D).global_position
					cache.turn_from = from
			cache.bag = bag
			cache.returning = returning
			var identity_source: Dictionary = army.duplicate(false)
			if returning and army.get("battle") == null and cache.has("identity_events"):
				identity_source.battle = {"events":cache.identity_events}
			cache.slots = Formations.returning_slots(identity_source, data.englishRoster) if returning else Formations.field_slots(bag, data.englishRoster)
			# The column's rows and files follow the soldiers' size on this map.
			for slot in cache.slots:
				slot.side = float(slot.side) * unit_k
				slot.rear = float(slot.rear) * unit_k
			cache.extent = formation_extent(cache.slots)
			cache.erase("strike_memo")
			cache.erase("regroup_ms")
		if fighting:
			cache.identity_events = army_battle_events(army)
		var timeline: Variant = [army.get("events"), army.get("fallen"), army.get("battle"), army.get("presentation"), army_battle_events(army).size()]
		# A finished short battle can arrive as one packet. Its events are already
		# known while the presentation clock still draws the approach. Rebuild on
		# the phase transition too, even when that packet has not changed.
		var unchanged := same_items(cache.get("timeline"), timeline)
		if unchanged:
			cache.timeline = timeline # keep the newest objects: next frame compares by identity
		if not unchanged or cache.get("events_fighting", false) != fighting:
			cache.timeline = timeline
			cache.events_fighting = fighting
			if not cache.has("strike_memo"):
				cache.strike_memo = {}
			cache.events = battle_events(army, cache.slots, cache.get("engage", {}), cache.strike_memo,
				server_ms - float(army.get("battleAt", server_ms))) if fighting else {"members":{}, "fallen":{}}
		army_routes[id] = cache
		if cache.slots.is_empty():
			continue
		if not is_same(cache.get("lane_source"), cache.source):
			cache.lane_source = cache.source
			request_lane(cache)
		var start := float(army.get("returnStartsAt", server_ms) if returning else army.get("startsAt", server_ms))
		var end := float(army.get("returnsAt", server_ms) if returning else army.get("arrivesAt", server_ms))
		var travelling: bool = army.status == "outbound" or returning
		var duration := maxf(1.0, end - start)
		# Its march lane, once planned: before the column sets off, or while it is out of
		# sight (a hunt that has halted keeps the route its battle places were made on).
		var halted_before: bool = cache.get("engage", {}).get("locked", false) and not returning
		apply_lane(id, cache, server_ms < start or (not cache.get("in_view", false) and not fighting and not halted_before))
		if server_ms < start and not cache.get("lane_job", {}).get("done", true):
			mustering = true
		var fraction := (server_ms - start) / duration if travelling else 1.0
		var total := maxf(0.001, float(cache.distances[-1]))
		var travel := clampf(fraction, 0.0, 1.0) * total
		# Creature hunt: the column halts in front of the creature (never on it) and the
		# soldiers run to battle places around it; after the fight they regroup.
		var encounter: Dictionary = encounters.get(str(army.get("target", "")), {})
		var hunt: bool = not encounter.is_empty() and data.creatureModels.has(creature_species(encounter)) \
			and army.get("worldKind") != "pvp"
		var plan: Dictionary = {}
		if hunt and not returning:
			plan = engage_plan(cache, encounter)
			plan.halt_at = start + duration * float(plan.stop) / total
			travel = minf(travel, float(plan.stop))
			if server_ms >= float(plan.halt_at):
				# The charge has begun: contact places are final from here on.
				plan.locked = true
		elif returning and cache.has("engage") and army.get("battleAt") != null:
			plan = cache.engage
			plan.locked = true
			if cache.get("leave_source") != path:
				cache.leave_source = path
				cache.leave = approach_distance(cache.points, cache.distances, plan.beast, float(plan.front), false)
			travel = float(cache.leave) + clampf(fraction, 0.0, 1.0) * (total - float(cache.leave))
		var p := ground_point(along_route(cache, travel / total))
		# A hunt column halted at the bank stays on its raft through the fight: the
		# ferry state follows the column's place on the route, not the march status
		# (switching it off at the start of the fight dropped soldiers ~4 m).
		var on_route: bool = travelling or (hunt and not returning)
		var crossing := ferry_at(cache, travel / total) if on_route else -1.0
		var packing := ferry_weight(cache, travel / total) if on_route else 0.0
		# The column stays packed on the raft until its last row has landed: up to
		# build 1020 the formation unpacked as soon as the front had landed, and the
		# rear rows stood in the river (the riders on the owner's recording of 1020).
		var docked := -1.0
		if on_route:
			var depth := 0.0
			for slot in cache.slots:
				depth = maxf(depth, float(slot.rear))
			var last_row := (travel - depth * RAFT_PACK) / total
			packing = maxf(packing, ferry_weight(cache, last_row))
			if crossing < 0.0:
				docked = ferry_at(cache, last_row)
		if crossing >= 0.0:
			p.y = maxf(p.y, FERRY_DECK)
		var before := along_route(cache, (travel - 0.8) / total)
		var after := along_route(cache, (travel + 0.8) / total)
		var direction := after - before
		if direction.length_squared() > 0.0001:
			cache.heading = atan2(direction.x, direction.z)
		var heading := float(cache.get("heading", 0.0))
		army_markers.append({"position":p + Vector3.UP * 2.6, "id":id, "kind":"army", "item":army})
		var own: bool = me.is_empty() or str(army.get("owner", me)) == me
		if own and travelling:
			# The route still ahead, as flowing arrows: to the creature or back home.
			var goal := float(plan.stop) if hunt and not returning else total
			update_march_line(id, cache, travel, goal)
			lines[id] = true
		if map_name == "world" and camera_zoom > 132.0:
			cache.in_view = false
			continue
		# Whole formation (and a hunt's battle places), not the anchor point alone.
		var in_view := sphere_in_view(p + Vector3.UP, float(cache.get("extent", 10.0)))
		if not in_view and not plan.is_empty():
			in_view = sphere_in_view(plan.beast + Vector3.UP, battle_reach(plan))
		cache.in_view = in_view
		if not in_view:
			continue
		alive[id] = true
		var actor := actors.get_node_or_null(NodePath(id)) as Node3D
		if actor == null:
			actor = Node3D.new()
			actor.name = id
			actors.add_child(actor)
		actor.show()
		actor.process_mode = Node.PROCESS_MODE_INHERIT
		actor.set_meta("last_visible_ticks", Time.get_ticks_msec())
		actor.position = p
		cache.position = p
		var halted: bool = hunt and not returning and server_ms >= float(plan.halt_at)
		# Halted at the creature while the server has not sent the battle yet (it is
		# simulated at the first answer after the arrival, see CombatPresentation
		# late_starts): the crowd already fights from its places, the server's blows,
		# numbers and HP join when the battle comes. Up to build 1020 the soldiers
		# stood still there for 3.5-6 s.
		var engaging: bool = halted and not fighting
		var melee: bool = fighting or engaging
		if melee:
			cache.member_at = {}
		var walking: bool = travelling and fraction >= 0.0 and fraction < 1.0 and crossing < 0.0 and not halted
		sync_raft(actor, cache, crossing, heading, server_ms, docked, p)
		# Authoritative ground speed of the formation (world units per second).
		var ground_speed := float(cache.distances[-1]) / (duration / 1000.0) if walking and cache.distances.size() > 1 else 0.0
		if returning and not plan.is_empty():
			ground_speed *= (total - float(cache.leave)) / total
		var elapsed := server_ms - float(army.get("battleAt", end))
		var spread := smoothstep(0.0, 700.0, elapsed) if fighting and not hunt else 0.0
		if returning and plan.is_empty() and army.get("battleAt") != null:
			# No battle places known (a fight with a city, or the app opened on the way
			# back): the old ring closes into the column.
			spread = 1.0 - smoothstep(0.0, 700.0, server_ms - start)
		var charge_age := server_ms - float(plan.halt_at) if halted else -INF
		var battle_base := float(army.get("battleAt", end))
		# The crowd keeps fighting until the creature falls (or, in a lost fight, to the end).
		var slain_at := INF
		if hunt and fighting:
			var fx := battle_timeline(army, encounter, army_battle_events(army))
			if not fx.hits.is_empty() and float(fx.hits[-1][2]) <= 0.0:
				slain_at = float(fx.hits[-1][0])
			elif army.get("battleEndsAt") != null:
				slain_at = float(army.battleEndsAt) - battle_base
		var ambient_sparks := 0
		var places: Dictionary = plan.get("places", {})
		var beast: Vector3 = plan.get("beast", p)
		var events: Dictionary = cache.get("events", {"members":{}, "fallen":{}})
		# The creature's own swipes between its server attacks, and who blocks them.
		var feints: Array = []
		if hunt and melee and not plan.is_empty():
			var beast_actor := creatures.get_node_or_null(NodePath(str(encounter.get("id", "")))) as Node3D
			if beast_actor != null:
				var bite := CombatV010.creature_attack_window(beast_actor) if CombatV010.owns(beast_actor) else Vector2(560.0, 430.0)
				feints = beast_feints(id, plan, cache, army_battle_events(army), slain_at, bite, events.get("fallen", {}))
		cache.feints = feints
		var blocks := {}
		for feint in feints:
			if not blocks.has(feint.target): blocks[feint.target] = []
			blocks[feint.target].append(float(feint.at))
		var retained := {}
		for i in range(cache.slots.size()):
			var slot: Dictionary = cache.slots[i]
			var key := "%s:%d" % [slot.id, int(slot.index)]
			var node_name := "%s_%d" % [slot.id, int(slot.index)]
			var unit := actor.get_node_or_null(NodePath(node_name)) as Node3D
			if unit == null:
				# A retired unit id (DRENOVAR-V6-ROSTER-5) has no model: the server converts saves on load.
				if not data.unitModels.has(slot.id):
					continue
				if creation_budget <= 0 or not model_ready(str(data.unitModels[slot.id].field)) \
						or not CombatV010.ready_for("troop", slot.id):
					continue
				unit = add_warrior(actor, data.unitModels[slot.id].field, Transform3D.IDENTITY)
				# Combat v0.1.0 (flag): the library goes onto the fresh player before
				# anything has played on it; this soldier's pose belongs to it for life.
				CombatV010.install(unit, "troop", slot.id)
				unit.name = node_name
				creation_budget -= 1
			retained[node_name] = true
			var pack := lerpf(1.0, RAFT_PACK, packing)
			var side := float(slot.side) * (1.0 + spread * 0.22) * pack
			var rear := (float(slot.rear) + spread * (4.0 if slot.ranged else 2.5) * unit_k) * pack
			if cache.has("lane") and not fighting and packing <= 0.0:
				# The column closes up where its lane passes close to trees, houses, the
				# wall or the water (march_lanes.gd); each row where it walks.
				side *= MarchLanes.squeeze(cache.lane, travel - rear, float(cache.lane_half), float(cache.lane_body))
			# Each row walks the route itself, `rear` metres behind the anchor.
			var row: Array = column_point(cache, travel, side, rear, heading, returning and not plan.is_empty())
			var place: Vector3 = row[0]
			if spread > 0.0:
				var angle: float = TAU * i / cache.slots.size()
				place = place.lerp(p + Vector3(cos(angle), 0.0, sin(angle)) * (7.5 if slot.mounted else 4.8) * unit_k, spread)
			var offset := place - p
			place = ground_point(place)
			if packing > 0.0:
				place.y = lerpf(place.y, p.y, packing)
				# A row over the river stands on the raft's deck.
				if ferry_at(cache, (travel - rear) / total) >= 0.0 and not dry_ground(place):
					place.y = FERRY_DECK
			var facing := atan2(-offset.x, -offset.z) if fighting and not hunt else float(row[1])
			var clip := "walk" if walking else "idle"
			var tempo := 1.0
			if walking:
				var gait := gait_for(slot.id, ground_speed, unit_scale, run_tempo_max)
				clip = gait[0]
				tempo = gait[1]
			# Where this soldier fights the creature, and whether it got there.
			var post: Variant = places.get(key)
			var engaged := false
			var arrived_at := INF # battle ms from which it stands at its place
			if post != null:
				var spot: Vector3 = post
				var approach: Array = plan.get("approaches",{}).get(key,[])
				if returning:
					# Back from the battle place to its place in the homeward column, at a
					# run. The time follows the distance (it was a fixed 1.4 s: up to
					# ~40 m/s). Straight when that stays on dry ground; otherwise back
					# along the checked approach (which ends at the halt point, behind
					# the way home). Chosen once per soldier, so the path never switches.
					var regroup_ms: Dictionary = cache.get("regroup_ms", {})
					cache.regroup_ms = regroup_ms
					if not regroup_ms.has(key):
						var detour := false
						for k in range(1, 10):
							var q := spot.lerp(place, k / 10.0)
							# Water, and (build 1021) the wall, houses and trunks of the march lanes.
							if not dry_ground(q) or (not lanes.signature.is_empty() and lanes.clearance(Vector2(q.x, q.z), 0.3 * unit_k) < 0.2 * unit_k):
								detour = approach.size() > 1
								break
						var first: Array = [spot, place]
						if detour:
							first = approach.duplicate()
							first.reverse()
							first.append(place)
						var length := 0.0
						for n in range(1, first.size()):
							length += (first[n - 1] as Vector3).distance_to(first[n])
						regroup_ms[key] = [clampf(length / ((REGROUP_RIDE if slot.mounted else REGROUP_RUN) * unit_k) * 1000.0, REGROUP_MS, REGROUP_MAX_MS), detour]
					var span: float = regroup_ms[key][0]
					var exit_path: Array = [spot, place]
					if regroup_ms[key][1]:
						exit_path = approach.duplicate()
						exit_path.reverse()
						exit_path.append(place)
					var w := clampf((server_ms - start) / span, 0.0, 1.0)
					if w < 1.0:
						var along := w * w * (3.0 - 2.0 * w)
						var moved: Vector3 = CombatSlots.along(exit_path, along)
						var ahead: Vector3 = CombatSlots.along(exit_path, minf(1.0, along + 0.02))
						if moved.distance_to(ahead) > 0.01:
							facing = atan2(ahead.x - moved.x, ahead.z - moved.z)
						var length := 0.0
						for n in range(1, exit_path.size()):
							length += (exit_path[n - 1] as Vector3).distance_to(exit_path[n])
						var gait := gait_for(slot.id, maxf(1.2 * unit_k, length / (span / 1000.0) * 6.0 * w * (1.0 - w)), unit_scale, run_tempo_max)
						clip = gait[0]
						tempo = gait[1]
						place = moved
				elif charge_age > -INF:
					if approach.size() > 1 and (approach[0] as Vector3).distance_to(place) > 0.05:
						# Continuity: the charge starts where the soldier stands.
						approach = [place] + approach
					var distance := place.distance_to(spot)
					if approach.size()>1:
						distance=0.0
						for n in range(1,approach.size()):distance+=approach[n-1].distance_to(approach[n])
					# At most 2.6 s, but never faster on average than a soldier or a horse
					# can run: a 30 m approach squeezed into 2.6 s slid at ~17 m/s.
					var span := maxf(clampf(distance / (CHARGE_SPEED * unit_k) * 1000.0, 300.0, 2600.0),
						distance / ((CHARGE_MAX_RIDE if slot.mounted else CHARGE_MAX_RUN) * unit_k) * 1000.0)
					var w := clampf(charge_age / span, 0.0, 1.0)
					arrived_at = float(plan.halt_at) + (span if distance > 0.3 else 0.0) - battle_base
					var from := place
					place = CombatSlots.along(approach,w*w*(3.0-2.0*w)) if approach.size()>1 else from.lerp(spot,w*w*(3.0-2.0*w))
					if w < 1.0 and distance > 0.3:
						var next: Vector3=CombatSlots.along(approach,minf(1.0,w*w*(3.0-2.0*w)+0.015)) if approach.size()>1 else spot
						facing = atan2(next.x-place.x,next.z-place.z)
						var gait := gait_for(slot.id, distance / (span / 1000.0) * 6.0*w*(1.0-w), unit_scale, run_tempo_max)
						clip = gait[0]
						tempo = gait[1]
					else:
						engaged = true
						clip = "idle"
						tempo = 1.0
						facing = atan2(beast.x - place.x, beast.z - place.z)
			if returning and cache.has("turn_from") and cache.turn_from.has(node_name):
				var from: Vector3 = cache.turn_from[node_name]
				var turn_ms: Dictionary = cache.get("turn_ms", {})
				cache.turn_ms = turn_ms
				if not turn_ms.has(node_name):
					turn_ms[node_name] = clampf(from.distance_to(place) / ((REGROUP_RIDE if slot.mounted else REGROUP_RUN) * unit_k) * 1000.0, REGROUP_MS, REGROUP_MAX_MS)
				var turn := smoothstep(0.0, float(turn_ms[node_name]), server_ms - start)
				if turn < 1.0:
					var moved := from.lerp(place, turn)
					if from.distance_to(place) > 0.3 and turn < 0.85:
						facing = atan2(place.x - from.x, place.z - from.z)
						var gait := gait_for(slot.id, maxf(1.2 * unit_k, from.distance_to(place) / (float(turn_ms[node_name]) / 1000.0)), unit_scale, run_tempo_max)
						clip = gait[0]
						tempo = gait[1]
					place = moved
			if fighting and post != null and events.get("far", {}).has(key) and not plan.is_empty():
				# A far reserve rides in for each of its blows and back (see battle_events),
				# from wherever it is, also while it is still on its way to its place.
				var prepare_ms: float = (events.windows.get(slot.id, Vector2(490, 510)) as Vector2).x
				var ride_ms: float = events.ride_ms.get(key, 800.0)
				var ride := 0.0
				var leaving := false
				var blows: Array = events.members.get(key, []).filter(func(event): return event[1] == "soldier_attack")
				var learnt_at := {}
				for event in blows:
					var decided: Variant = cache.get("strike_memo", {}).get("%d|%s|%d" % [roundi(float(event[0]) * 10.0), event[2], int(event[3])])
					learnt_at[float(event[0])] = float(decided[1]) if decided is Array else -INF
				for visit in ride_visits(blows.map(func(event): return float(event[0])), prepare_ms, ride_ms):
					var weight := ride_weight(elapsed, visit[0], prepare_ms, ride_ms, learnt_at.get(visit[0], -INF), visit[1])
					if weight > ride:
						ride = weight
						leaving = elapsed > float(visit[1]) + RIDE_LEAVE_MS
				if ride > 0.0:
					var rest := place
					var contact := contact_point(plan, rest, bool(slot.mounted))
					place = rest.lerp(contact, ride)
					if ride < 0.98:
						var gait := gait_for(slot.id, maxf(1.2 * unit_k, rest.distance_to(contact) / (ride_ms / 1000.0) * 1.5), unit_scale, run_tempo_max)
						clip = gait[0]
						tempo = gait[1]
						if leaving and rest.distance_to(contact) > 0.5:
							facing = atan2(rest.x - contact.x, rest.z - contact.z)
					engaged = false # flat while it rides; the support tilt belongs to the reserve place
			if melee:
				cache.member_at[key] = place
			var shown_yaw := smooth_yaw(unit, facing, server_ms)
			unit.transform = model_transform(place.x - p.x, place.y - p.y, place.z - p.z, shown_yaw, unit_scale)
			if engaged and plan.get("supports",{}).has(key):
				unit.basis = support_basis(plan.supports[key], shown_yaw) * unit_scale
			var phase := -1.0
			var strike := -INF
			var last_strike := -INF
			# Authored ranged Attack releases at frame 15/30 (poses.py); its
			# release must precede contact by the existing 260 ms flight interval.
			var prepare := 760.0 if slot.ranged else 490.0
			# Combat v0.1.0: windows come from the library manifest (contact/release).
			var v010 := CombatV010.owns(unit)
			var window := CombatV010.attack_window(unit, prepare)
			prepare = window.x
			var hit_ms := CombatV010.hit_window(unit, 400.0) if v010 else 400.0
			var hit := -INF
			var down: bool = fighting and events.fallen.has(key)
			# Ambient swing (between the server's blows, see ambient_strike) and the
			# crossbow's reload after a shot: contact times in battle ms.
			var ambient := -INF
			var reload_from := -INF
			var recover := CombatV010.recover_ms(unit) if v010 else 0.0
			# A creature's swipe at this soldier (beast_feints): the shield goes up.
			var block := -INF
			if melee and v010 and engaged and blocks.has(key) and CombatV010.has_clip(unit, &"block"):
				for at in blocks[key]:
					if elapsed >= at - BLOCK_WINDOW.x and elapsed <= at + BLOCK_WINDOW.y:
						block = at
			if melee:
				var own_blows: Array = blocks.get(key, []).duplicate()
				for event in events.members.get(key, []):
					var at := float(event[0])
					if event[1] == "soldier_attack":
						own_blows.append(at)
						if at<=elapsed:last_strike=at
						if elapsed >= at - prepare and elapsed <= at + window.y:
							strike = at
					elif at <= elapsed:
						hit = at
						down = down or event[4] == 0
				if v010:
					# Overlapping (lent) strikes: never cut a windup/contact (see pick_strike).
					strike = CombatV010.pick_strike(unit, events.members.get(key, []), elapsed)
					# Every soldier at its place swings from the moment it arrives (a far
					# reserve, out of reach, waits for a blow it rides in for).
					if hunt and engaged and not down and strike == -INF and elapsed - hit >= hit_ms \
							and (slot.ranged or int(plan.get("reserve_rows", {}).get(key, 0)) < 3):
						ambient = ambient_strike(key, elapsed, arrived_at, slain_at, window, recover, own_blows)
						if ambient > -INF and elapsed > ambient + window.y:
							reload_from = ambient + window.y
							ambient = -INF
					if recover > 0.0 and strike == -INF and ambient == -INF and reload_from == -INF \
							and elapsed - last_strike > window.y and elapsed - last_strike < window.y + recover:
						reload_from = last_strike + window.y
				if down:
					clip = "death"
					phase = 1.0 if hit == -INF else (elapsed - hit) / 1200.0
					if not unit.has_meta("death_at"):
						unit.set_meta("death_at", server_ms if hit == -INF else float(army.battleAt) + hit)
						unit.set_meta("death_transform", unit.global_transform)
					unit.global_transform = unit.get_meta("death_transform")
				elif elapsed - hit < hit_ms and strike == -INF:
					clip = "hit"
					phase = (elapsed - hit) / hit_ms
				elif strike > -INF and (slot.ranged or events.get("strikers",{}).has(key)):
					clip = "attack"
					phase = (elapsed - strike + prepare) / 1000.0
					if not slot.ranged and slot.id not in ["ENG-01","ENG-06"]:
						# Weapon sweep timed to the swing's contact frame (event time).
						battle_fx.slash(place, beast if hunt else p,(elapsed-strike+70.0)/170.0,Color("#b7b8ac"),.85 * unit_k)
				elif block > -INF:
					clip = "block"
					phase = (elapsed - block + BLOCK_WINDOW.x) / 1000.0
					# The claw meets the shield: no number, the swipe did no harm.
					battle_fx.slash(beast, place, (elapsed - block + 80.0) / 200.0, Color("#a29a85"), .8 * beast_k)
					if elapsed >= block and elapsed - block <= 200.0:
						battle_fx.spark(place.lerp(beast, 0.15), (elapsed - block) / 200.0, Color("#e4dcc4"), .5 * beast_k, fposmod(block * .007, 1.0))
				elif ambient > -INF:
					clip = "attack"
					phase = (elapsed - ambient + prepare) / 1000.0
					if not slot.ranged:
						if slot.id not in ["ENG-01","ENG-06"]:
							battle_fx.slash(place, beast, (elapsed - ambient + 70.0) / 170.0, Color("#b7b8ac"), .75 * unit_k)
						if elapsed >= ambient and elapsed - ambient <= 160.0 and ambient_sparks < 4:
							# The blow lands on the creature's hide (no number: not a server blow).
							ambient_sparks += 1
							var toward := (place - beast).normalized()
							battle_fx.spark(beast + toward * minf(float(plan.body.y), place.distance_to(beast) * 0.5), (elapsed - ambient) / 160.0,
								Color("#94745a"), .32 * beast_k, fposmod(ambient * .011 + i * .17, 1.0))
				elif army.get("worldKind") == "pvp":
					clip = "attack"
					phase = fposmod(elapsed + i * 125.0, 1000.0) / 1000.0
				elif reload_from > -INF:
					clip = "reload"
					phase = (elapsed - reload_from) / maxf(1.0, recover)
				elif slot.id=="ENG-04" and not v010 and elapsed-last_strike>=240.0 and elapsed-last_strike<2240.0:
					# The authored 2s reload fits between the existing 3.2s attacks:
					# recovery ends +240, next preparation starts +2440.
					clip="reload";phase=(elapsed-last_strike-240.0)/2000.0
			var shown := strike if strike > -INF else ambient
			var clip_time := -1.0
			if v010:
				# Single pose owner: exact clips, server-time driven.
				var named := StringName(clip)
				if clip == "attack":
					if shown > -INF:
						named = CombatV010.attack_clip(key, shown)
						clip_time = CombatV010.attack_time(unit, elapsed, shown)
						unit.set_meta("v010_strike", strike) # the server event this swing shows (QA)
						unit.set_meta("ambient_strike", ambient)
					else:
						# Existing PvP stand-in swing (no individual server events): same
						# staggered cadence, played at the clip's own speed.
						named = &"attack_a"
						clip_time = fposmod(elapsed + i * 125.0, window.x + window.y) / 1000.0
						unit.set_meta("v010_strike", -INF)
				elif clip == "reload":
					clip_time = (elapsed - reload_from) / 1000.0
				elif clip == "block":
					clip_time = (elapsed - block + BLOCK_WINDOW.x) / 1000.0
				elif clip == "death":
					clip_time = INF if hit == -INF else (elapsed - hit) / 1000.0
				elif clip == "hit":
					clip_time = (elapsed - hit) / 1000.0
				CombatV010.drive(unit, named, clip_time, tempo, fposmod(float(i) * 0.381966, 1.0))
				unit.set_meta("clip", clip)
				unit.set_meta("tempo", tempo)
				if clip == "attack" and shown > -INF and engaged and not slot.ranged:
					# The body goes into the blow: a short step (a rider's lunge) toward the
					# creature through the contact and back. Feet stay planted in the clip.
					var lunge := sin(PI * clampf((elapsed - shown + 320.0) / 720.0, 0.0, 1.0))
					var toward := Vector3(beast.x - place.x, 0.0, beast.z - place.z)
					if toward.length_squared() > 0.01:
						unit.position += toward.normalized() * lunge * (0.55 if slot.mounted else 0.24) * unit_k
			elif phase >= 0.0 or unit.get_meta("clip", "") != clip:
				play_animation(unit, data.unitModels[slot.id].drill if clip=="reload" else clip, data.unitModels[slot.id].drill if clip == "attack" else "", phase,
					fposmod(float(i) * 0.381966, 1.0))
				unit.set_meta("clip", clip)
			# Legacy only: the spine overlay has no verified bone mask, so v0.1.0 shows
			# a hit during an active swing by contact FX alone.
			if clip=="attack" and not v010:additive_hit(unit,(elapsed-hit)/320.0)
			if slot.id == "SIEGE-RAM-01":
				# Static authored machine: cosmetic recoil only at an actual server hit.
				unit.rotation.z = PI / 3.0 if down else 0.0
				if strike > -INF and not down:
					unit.position += unit.basis.z.normalized() * (sin(clampf((elapsed - strike + 490.0) / 1000.0, 0.0, 1.0) * PI) * 0.25 * unit_k)
			if unit.get_meta("tempo", 1.0) != tempo:
				unit.set_meta("tempo", tempo)
				for player: AnimationPlayer in unit.get_meta("animation_players", []):
					player.speed_scale = tempo
			var shot := unit.get_node_or_null("Arrow") as MeshInstance3D
			var firing: bool = slot.ranged and clip == "attack" and shown > -INF and elapsed >= shown - 260.0 and elapsed <= shown
			if firing:
				draw_arrow(unit, shot, beast if hunt else p, (elapsed - shown + 260.0) / 260.0, slot.id, "%s/%s/%s" % [id,key,shown])
			elif shot != null:
				shot.hide()
			foot_contacts.sample(self,unit,clip,bool(slot.mounted),server_ms)
			if not fighting and clip != "death":
				walkers.append(Vector2(unit.global_position.x, unit.global_position.z))
		for unit in actor.get_children():
			if not retained.has(String(unit.name)) and unit.name != &"Ferry":
				if unit.has_meta("death_at") and fallen_bodies.size() < Formations.FIELD_LIMIT:
					var death_at := float(unit.get_meta("death_at"))
					unit.reparent(self, true)
					unit.global_transform = unit.get_meta("death_transform")
					fallen_bodies.append({"node":unit, "at":death_at, "until":maxf(server_ms + 1200.0, death_at + 3200.0)})
				else:
					unit.free()
	retain_hidden_actors(actors, known, alive, MAX_HIDDEN_ARMIES)
	update_march_clearing(walkers)
	lanes.slice_usec = MarchLanes.MUSTER_SLICE_USEC if mustering else MarchLanes.SLICE_USEC
	for line in march_lines.get_children():
		if not lines.has(String(line.name)):
			line.free()
	for id in army_routes.keys():
		if not rows.any(func(army): return army.id == id and army.status != "returned"):
			army_routes.erase(id)
			fx_timelines.erase(id)
			announced_fights.erase(id)

# Where an army hunting a creature halts and where each soldier fights: the column
# stops in front of the creature and the whole party closes in on it as one crowd
# (crowd_places: foot and riders mixed in the ring at its body, archers mixed in the
# next ring). Places on water turn around the creature to dry ground. Cached per
# route and bag.
func engage_plan(cache: Dictionary, encounter: Dictionary) -> Dictionary:
	# A patrolling target reports a new position on every poll. Rebuilding the
	# plan for each small step restarted the whole collision search; keep it
	# while the target stays within a few metres of the planned anchor.
	var key := [cache.source, creature_species(encounter), encounter.get("level"), cache.bag]
	var anchor := point(encounter.position)
	if cache.get("engage_key") == key and cache.has("engage"):
		var planned: Vector3 = cache.engage.get("anchor", anchor)
		if cache.engage.get("locked", false) or Vector2(planned.x - anchor.x, planned.z - anchor.z).length() < ENGAGE_REPLAN_M:
			return cache.engage
	if cache.get("engage") is Dictionary:
		# A replaced plan stops refining (its column changed route or party).
		cache.engage.locked = true
	var beast := ground_point(point(encounter.position))
	var body := creature_body(encounter)
	var front := body.x + (ENGAGE_GAP + 1.0) * unit_k
	var stop := approach_distance(cache.points, cache.distances, beast, front, true)
	var halt := along_route(cache, stop / maxf(0.001, float(cache.distances[-1])))
	var face := Vector3(halt.x - beast.x, 0.0, halt.z - beast.z)
	if face.length_squared() < 0.25:
		var first: Vector3 = cache.points[0]
		face = Vector3(first.x - beast.x, 0.0, first.z - beast.z)
	face = face.normalized() if face.length_squared() > 0.0001 else Vector3.BACK
	var side := Vector3(face.z, 0.0, -face.x)
	# PvE's current server solver starts each unit at x=-7-index%5*.6.
	# The front lanes therefore deliver the first melee contacts. On a narrow
	# bank, assigning every legal contact footprint to rear-lane members can
	# leave the actual attackers in reserve for the whole short battle. Prioritise
	# those existing front members when planning positions at march start; their
	# identities, events and validated footprints/approaches remain unchanged.
	var placement_slots: Array = cache.slots.duplicate()
	var placement_order := {}
	for i in placement_slots.size():
		var slot: Dictionary = placement_slots[i]
		placement_order["%s:%d" % [slot.id, int(slot.index)]] = i + (int(slot.index) % 5) * Formations.FIELD_LIMIT if not slot.mounted and not slot.ranged else 1000 + i
	placement_slots.sort_custom(func(a,b): return placement_order["%s:%d" % [a.id,int(a.index)]] < placement_order["%s:%d" % [b.id,int(b.index)]])
	# Where each member stands in the halted column (the charge starts there).
	var heading := route_heading(cache, stop, atan2(-face.x, -face.z))
	var origins := {}
	for slot in placement_slots:
		var at: Vector3 = column_point(cache, stop, float(slot.side), float(slot.rear), heading)[0]
		origins["%s:%d" % [slot.id, int(slot.index)]] = Vector2((at - beast).dot(face), (at - beast).dot(side))
	var places := {}
	var local_places := crowd_places(placement_slots, origins, body, unit_k)
	# The crowd's ground: trees on it are cleared while the fight is on screen
	# (battle_focus_core), so they do not push soldiers out of the crowd. Up to
	# build 1019 their trunks still counted: on the wooded world map riders found
	# no place near the creature and waited 8-15 m away.
	var clear := 0.0
	for slot in placement_slots:
		var member := "%s:%d" % [slot.id, int(slot.index)]
		places[member] = battle_place(beast, face, side, local_places[member])
		clear = maxf(clear, (local_places[member] as Vector2).length() + (2.2 if slot.mounted else 1.0) * unit_k)
	var plan := {"beast": beast, "face": face, "yaw": atan2(face.x, face.z), "body": body, "front": front,
		"stop": stop, "places": places, "anchor": anchor, "clear": clear}
	var solver := CombatSlots.new()
	solver.clear_radius = clear
	solver.set_unit_k(unit_k)
	plan.approaches={};plan.supports={};plan.reserves={};plan.reserve_rows={};plan.slot_solver=solver
	plan.solving=true
	cache.engage_key = key
	cache.engage = plan
	# The arc places above are usable at once. The collision-checked refinement
	# runs in slices while the column walks (engage_sync: whole plan now, for
	# tools and tests). It never blocks a frame for more than the slice.
	solver.slice_usec = 0 if engage_sync else ENGAGE_SLICE_USEC
	refine_engage_plan(plan, solver, placement_slots, cache, stop, heading)
	return plan

# Collision-checked contact places and approaches, member by member (front
# melee first). Members are only rewritten before the charge starts: once the
# column halts, an unfinished member keeps its arc place instead of jumping.
func refine_engage_plan(plan: Dictionary, solver, placement_slots: Array, cache: Dictionary, stop: float, heading: float) -> void:
	await solver.prepare(self,plan.beast,plan.face,plan.body)
	for slot in placement_slots:
		if plan.get("locked", false) or not solver.space.is_valid():
			break
		var member := "%s:%d"%[slot.id,int(slot.index)]
		var origin := ground_point(column_point(cache, stop, float(slot.side), float(slot.rear), heading)[0])
		var result: Dictionary=await solver.choose(member,plan.places[member],origin,bool(slot.mounted))
		if result.is_empty() or plan.get("locked", false):
			break
		plan.places[member]=result.position;plan.approaches[member]=result.path
		plan.supports[member]=result.basis;plan.reserves[member]=result.reserve
		plan.reserve_rows[member]=int(result.get("reserve_row", 4 if result.reserve else 0))
	plan.solving=false
	if not engage_sync:
		solver.release()

# Trees beside marching soldiers fade like those around a fight (forest.gdshader
# march_clear): a small mask around the camera target, r = 1 within MARCH_CLEAR_M of
# each soldier outside a fight (narrower on the world map, whose soldiers are smaller).
# Up to build 1020 a column on its way walked through the trunks and under the
# canopy; together with the march lanes it now walks between the trees and is seen.
# On the world map the creatures get the same glade (creature_clear), and the mask
# covers about the whole screen.
const MARCH_CLEAR_PX := 64
const WORLD_CLEAR_PX := 128
# About a tree's crown: a soldier under a crown is hidden from the camera. On the
# world map (smaller soldiers, smaller trees) half of it.
const MARCH_CLEAR_M := 4.0
# A world creature's glade reaches this far beyond its body: about one and a half
# crowns of the trees there (half-widths 0.6-2.05 m, measured on the models).
const CREATURE_GLADE_M := 3.0
var march_clear_image: Image
var march_clear_texture: ImageTexture
var march_clear_bytes := PackedByteArray()
# World creatures drawn last frame: x, z and the glade radius (m).
var creature_clear := PackedVector3Array()
# The mask's ground square (x0, z0, size m, 1) as given to the shader; 0 when off.
var march_clear_area := Vector4.ZERO
# What the mask was last drawn from when only creatures were in it (they often stand
# still under a still camera: then it is not drawn again).
var march_clear_key := PackedFloat32Array()
# The shader globals are shared by both scenes: whichever stage drew a mask last
# switches it off.
static var march_clear_on := false
static var march_clear_owner := 0

func update_march_clearing(spots: PackedVector2Array) -> void:
	if spots.is_empty() and creature_clear.is_empty():
		march_clear_area = Vector4.ZERO
		if march_clear_on:
			march_clear_on = false
			RenderingServer.global_shader_parameter_set(&"march_clear_area", Vector4.ZERO)
		return
	var px := MARCH_CLEAR_PX if map_name == "city" else WORLD_CLEAR_PX
	var size := clampf(camera_zoom * (1.7 if map_name == "city" else 2.2), 48.0, 260.0)
	var origin := Vector2(camera_target.x, camera_target.z) - Vector2.ONE * size * 0.5
	var per_m := px / size
	var reach := MARCH_CLEAR_M * unit_k / (FIELD_UNIT_SCALE / LAYOUT_UNIT_SCALE)
	# Crowns between a soldier and the camera hide it most: the clearing leans that way.
	var toward := Vector2(camera.global_position.x - camera_target.x, camera.global_position.z - camera_target.z)
	toward = toward.normalized() * 0.35 if toward.length_squared() > 0.01 else Vector2.ZERO
	var key := PackedFloat32Array()
	if spots.is_empty():
		key = PackedFloat32Array([origin.x, origin.y, size, toward.x, toward.y])
		for c in creature_clear:
			key.append(c.x)
			key.append(c.y)
			key.append(c.z)
		if key == march_clear_key and march_clear_on and march_clear_owner == get_instance_id():
			return
	march_clear_key = key
	if march_clear_bytes.size() != px * px:
		march_clear_bytes.resize(px * px)
	march_clear_bytes.fill(0)
	var stamped := PackedVector2Array()
	for q in spots:
		# Rows walk close together: a soldier next to one already cleared adds little.
		var skip := false
		for other in stamped:
			if other.distance_squared_to(q) < reach * reach * 0.16:
				skip = true
				break
		if skip:
			continue
		stamped.append(q)
		stamp_clearing((q + toward * reach - origin) * per_m, reach * per_m, px)
	for c in creature_clear:
		stamp_clearing((Vector2(c.x, c.y) + toward * c.z - origin) * per_m, c.z * per_m, px)
	if march_clear_image == null:
		march_clear_image = Image.create_from_data(px, px, false, Image.FORMAT_L8, march_clear_bytes)
		march_clear_texture = ImageTexture.create_from_image(march_clear_image)
	else:
		march_clear_image.set_data(px, px, false, Image.FORMAT_L8, march_clear_bytes)
		march_clear_texture.update(march_clear_image)
	if not march_clear_on or march_clear_owner != get_instance_id():
		march_clear_owner = get_instance_id()
		RenderingServer.global_shader_parameter_set(&"march_clear", march_clear_texture)
	march_clear_on = true
	march_clear_area = Vector4(origin.x, origin.y, size, 1.0)
	RenderingServer.global_shader_parameter_set(&"march_clear_area", march_clear_area)

# One soft disc of the march mask: full inside 55 % of the radius (pixels).
func stamp_clearing(c: Vector2, radius: float, px: int) -> void:
	var inner := radius * 0.55
	var x0 := maxi(0, floori(c.x - radius))
	var x1 := mini(px, ceili(c.x + radius) + 1)
	var y0 := maxi(0, floori(c.y - radius))
	var y1 := mini(px, ceili(c.y + radius) + 1)
	for y in range(y0, y1):
		var row := y * px
		var dy := y + 0.5 - c.y
		for x in range(x0, x1):
			var dx := x + 0.5 - c.x
			var d := sqrt(dx * dx + dy * dy)
			if d >= radius:
				continue
			var v := int(255.0 * (1.0 - smoothstep(inner, radius, d)))
			if v > march_clear_bytes[row + x]:
				march_clear_bytes[row + x] = v

# Plans the march lane of an army's current route in the background (one at a time;
# a newer route of the same army replaces a waiting one).
func request_lane(cache: Dictionary) -> void:
	var job := {"source": cache.source, "done": false}
	cache.lane_job = job
	var half := 0.0
	for slot in cache.slots:
		half = maxf(half, absf(float(slot.side)))
	cache.lane_body = 0.45 * unit_k
	cache.lane_half = half + float(cache.lane_body)
	lane_queue.append([cache, job])
	if not lane_busy:
		run_lanes()

func run_lanes() -> void:
	lane_busy = true
	while not lane_queue.is_empty():
		var item: Array = lane_queue.pop_front()
		var cache: Dictionary = item[0]
		var job: Dictionary = item[1]
		if not is_same(cache.get("lane_job"), job):
			continue
		var corridor := LANE_CORRIDOR * (1.0 if map_name == "city" else 0.75)
		var started := Time.get_ticks_usec()
		job.lane = await lanes.plan(self, cache.points, cache.get("ferry", PackedByteArray()), float(cache.lane_half), float(cache.lane_body), corridor)
		job.usec = Time.get_ticks_usec() - started
		job.done = true
		if not is_inside_tree():
			break
	lane_busy = false

# Puts a planned lane in place of the route as drawn so far (`now_ok`: the column is
# not yet on its way or not in sight, so nothing on screen jumps).
func apply_lane(id: String, cache: Dictionary, now_ok: bool) -> void:
	var job: Dictionary = cache.get("lane_job", {})
	if not job.get("done", false) or job.get("applied", false):
		return
	if job.get("source") != cache.source:
		job.applied = true
		return
	if not now_ok:
		return
	job.applied = true
	var lane: Dictionary = job.get("lane", {})
	if lane.is_empty():
		return
	var points: PackedVector3Array = lane.points
	var distances := PackedFloat32Array()
	for i in points.size():
		distances.append(0.0 if i == 0 else distances[-1] + Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length())
	cache.points = points
	cache.distances = distances
	cache.ferry = lane.ferry
	cache.lane = lane
	# What was made on the old route: the hunt's plan (not yet halted) and the way off.
	if cache.get("engage") is Dictionary:
		cache.engage.locked = true
		if not cache.get("returning", false):
			cache.erase("engage")
			cache.erase("engage_key")
	cache.erase("leave_source")
	var line := march_lines.get_node_or_null(NodePath(id))
	if line != null:
		line.free()

# Route distance where the route meets a circle of `radius` around `centre`: the
# last crossing inward on the way there, or the first outward on the way back.
static func approach_distance(points: PackedVector3Array, distances: PackedFloat32Array, centre: Vector3, radius: float, inbound: bool) -> float:
	var flat := func(q: Vector3) -> float: return Vector2(q.x - centre.x, q.z - centre.z).length()
	if points.size() < 2:
		return 0.0
	var order := range(points.size() - 1, 0, -1) if inbound else range(1, points.size())
	if inbound and flat.call(points[-1]) >= radius:
		return distances[-1]
	if not inbound and flat.call(points[0]) >= radius:
		return 0.0
	for i in order:
		var a := points[i - 1]
		var b := points[i]
		var outside_a: bool = flat.call(a) >= radius
		var outside_b: bool = flat.call(b) >= radius
		if outside_a == outside_b:
			continue
		# Bisection on the segment for the crossing.
		var low := 0.0
		var high := 1.0
		for step in 18:
			var mid := (low + high) * 0.5
			if (flat.call(a.lerp(b, mid)) >= radius) == outside_a:
				low = mid
			else:
				high = mid
		return distances[i - 1] + (distances[i] - distances[i - 1]) * (low + high) * 0.5
	return 0.0 if inbound else distances[-1]

# The party fights as one crowd around the creature (presentation only).
# Up to build 1019 foot soldiers took 120-degree arcs in front of it, riders its
# rear flanks and archers lines of seven behind the melee: on the phone each troop
# type queued in its own row and the archers shot from the back. Now foot and
# riders share one ring around the whole body, riders spread evenly among the foot;
# melee that does not fit and the archers stand in the next ring, staggered and
# mixed all round, a little irregular. Each member takes the free place of its kind
# nearest to where it stands in the halted column. Returns member -> local
# (x along the creature's face, y to its side); `origins` uses the same axes.
const CROWD_FOOT_M := 1.25
const CROWD_RIDER_M := 2.5
const CROWD_RANGED_M := 1.6
const CROWD_RING_M := 1.4
const CROWD_RIDER_OUT := 1.3
const CROWD_RANGED_OUT := 2.6

static func crowd_places(slots: Array, origins: Dictionary, body: Vector2, k := 1.0) -> Dictionary:
	var foot: Array = []
	var riders: Array = []
	var ranged: Array = []
	for slot in slots:
		var key := "%s:%d" % [slot.id, int(slot.index)]
		if slot.ranged:
			ranged.append(key)
		elif slot.mounted:
			riders.append(key)
		else:
			foot.append(key)
	# Riders spread evenly through the melee sequence (Bresenham).
	var melee_kinds: Array = []
	var total := foot.size() + riders.size()
	for n in total:
		melee_kinds.append("r" if riders.size() > 0 and floori((n + 1) * riders.size() / float(total)) > floori(n * riders.size() / float(total)) else "f")
	var free := {"f": [], "r": [], "a": []}
	# `k`: the soldiers' size on this map (unit_k); the rings shrink with them.
	var a := body.x + (ENGAGE_GAP + 0.35) * k
	var b := body.y + (ENGAGE_GAP + 0.55) * k
	var ring := 0
	var queued := melee_kinds
	while not queued.is_empty() and ring < 4:
		var spacing: Array = queued.map(func(kind): return (CROWD_RIDER_M if kind == "r" else CROWD_FOOT_M) * k)
		var placed: Array = ellipse_ring(a + ring * CROWD_RING_M * k, b + ring * CROWD_RING_M * k, spacing, 0.5 if ring % 2 else 0.0, ring * 17, 0.36 * k)
		for n in placed.size():
			var local: Vector2 = placed[n]
			if queued[n] == "r":
				local += ellipse_normal(a, b, local) * CROWD_RIDER_OUT * k
			free[queued[n]].append(local)
		queued = queued.slice(placed.size())
		ring += 1
	# Archers: one ring beyond the melee, spread round the crowd (the very back of
	# the creature stays a little emptier), alternately a little nearer and farther
	# (no straight lines). More archers than places go a ring further.
	var out := a - body.x + (CROWD_RANGED_OUT + maxi(0, ring - 1) * CROWD_RING_M) * k
	var ranged_ring := 0
	while free.a.size() < ranged.size() and ranged_ring < 4:
		var extra := out + ranged_ring * CROWD_RING_M * k
		var want: Array = []
		want.resize(ranged.size() - free.a.size())
		var around := 2.0 * ellipse_half_length(body.x + extra, body.y + extra)
		want.fill(clampf(0.82 * around / maxf(1.0, want.size()), CROWD_RANGED_M * k, CROWD_RANGED_M * 3.0 * k))
		var placed: Array = ellipse_ring(body.x + extra, body.y + extra, want, 0.5, 101 + ranged_ring * 13, 0.36 * k)
		for n in placed.size():
			var local: Vector2 = placed[n]
			free.a.append(local + ellipse_normal(body.x + extra, body.y + extra, local) * (0.45 if n % 2 else -0.15) * k)
		ranged_ring += 1
	var result := {}
	for group in [[foot, "f"], [riders, "r"], [ranged, "a"]]:
		var spots: Array = free[group[1]]
		for key in group[0]:
			if spots.is_empty():
				break
			var from: Vector2 = origins.get(key, Vector2(a + 6.0 * k, 0.0))
			var best := 0
			for n in range(1, spots.size()):
				if from.distance_squared_to(spots[n]) < from.distance_squared_to(spots[best]):
					best = n
			result[key] = spots[best]
			spots.remove_at(best)
	# Every member must have a place (the refinement reads them all): a party larger
	# than four rings, which the field limit never draws, waits farther out.
	var spare := 0
	for slot in slots:
		var key := "%s:%d" % [slot.id, int(slot.index)]
		if not result.has(key):
			result[key] = Vector2(a + (4.0 + floori(spare / 6.0) * CROWD_RING_M) * k, (spare % 6 - 2.5) * CROWD_RANGED_M * k)
			spare += 1
	return result

# Places around an ellipse (a ahead, b to the side) from its front, alternating
# sides, each `spacing[n]` metres of the outline wide, until the two sides meet at
# the back. `phase` (0..1 of the first spacing) staggers a ring against the one
# inside it; `seed` adds a small fixed irregularity. Returns the places that fit.
static func ellipse_ring(a: float, b: float, spacing: Array, phase: float, seed: int, radial_jitter := 0.36) -> Array:
	var lengths := PackedFloat32Array([0.0])
	var previous := Vector2(a, 0.0)
	for k in range(1, 181):
		var q := Vector2(a * cos(PI * k / 180.0), b * sin(PI * k / 180.0))
		lengths.append(lengths[-1] + q.distance_to(previous))
		previous = q
	var half := lengths[-1]
	var cursor := PackedFloat32Array([phase * float(spacing[0]) if not spacing.is_empty() else 0.0, 0.0])
	var result: Array = []
	for n in spacing.size():
		var width := float(spacing[n])
		var s := n % 2
		if cursor[s] + width > half + 0.001:
			s = 1 - s
			if cursor[s] + width > half + 0.001:
				break
		var along: float = cursor[s] + width * 0.5
		cursor[s] += width
		var jitter := fposmod(sin(float(seed + n) * 12.9898) * 43758.5453, 1.0)
		along = clampf(along + (jitter - 0.5) * 0.24 * width, 0.0, half)
		var k := lengths.bsearch(along)
		k = clampi(k, 1, 180)
		var f := (along - lengths[k - 1]) / maxf(0.0001, lengths[k] - lengths[k - 1])
		var phi := PI * (k - 1 + f) / 180.0
		var q := Vector2(a * cos(phi), b * sin(phi) * (1.0 if s == 0 else -1.0))
		var radial := (fposmod(jitter * 7.31, 1.0) - 0.5) * radial_jitter
		result.append(q + ellipse_normal(a, b, q) * radial)
	return result

static func ellipse_half_length(a: float, b: float) -> float:
	var length := 0.0
	var previous := Vector2(a, 0.0)
	for k in range(1, 91):
		var q := Vector2(a * cos(PI * k / 90.0), b * sin(PI * k / 90.0))
		length += q.distance_to(previous)
		previous = q
	return length

static func ellipse_normal(a: float, b: float, q: Vector2) -> Vector2:
	var n := Vector2(q.x / (a * a), q.y / (b * b))
	return n.normalized() if n.length_squared() > 0.0 else Vector2.RIGHT

func battle_place(beast: Vector3, face: Vector3, side: Vector3, local: Vector2) -> Vector3:
	var offset := face * local.x + side * local.y
	for turn in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8, 9, -9, 10]:
		var turned := offset.rotated(Vector3.UP, turn * deg_to_rad(18.0))
		if dry_ground(beast + turned):
			offset = turned
			break
	return ground_point(beast + offset)

# Land, not river: the city riverbed lies below -0.2, the world sea plane at 1.13.
func dry_ground(q: Vector3) -> bool:
	if map_name == "world":
		return world_heights.is_empty() or terrain_y(q) > 1.3
	return sample_city(q.x, q.z) > -0.2

static func creature_scale(level: Variant) -> float:
	return 1.02 + 0.16 * clampi(int(level), 1, 3)

func creature_body(encounter: Dictionary) -> Vector2:
	var species := creature_species(encounter)
	return CreatureVisuals.body(species, CREATURE_BODY.get(species, Vector2(2.7, 1.0))) * creature_scale(encounter.get("level", 1)) * beast_k

# Height of the health bar above a creature: the creatures-v2 model's own top (it is
# authored in metres and scaled by the display adapter), the 0.5.9 heights otherwise.
func creature_top(encounter: Dictionary, actor: Node3D) -> float:
	var species := creature_species(encounter)
	var level := clampi(int(encounter.get("level", 1)), 1, 3)
	if CreatureVisuals.active(species) and actor != null:
		var top := float(CreatureVisuals.entry(species).get("authored_bounds_m", {}).get("top", 3.0))
		return top * actor.scale.y + 0.35 * beast_k
	return (2.6 + 0.5 * level) * beast_k

# Flowing arrows over the part of the march route still ahead of the army.
func update_march_line(id: String, cache: Dictionary, from_m: float, to_m: float) -> void:
	var line := march_lines.get_node_or_null(NodePath(id)) as MeshInstance3D
	if line != null and line.get_meta("source") != cache.source:
		line.free()
		line = null
	if line == null:
		line = MeshInstance3D.new()
		line.name = id
		line.mesh = march_ribbon(cache.points, cache.distances)
		line.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var material := ShaderMaterial.new()
		material.shader = MARCH_LINE
		material.render_priority = 1
		line.material_override = material
		line.set_meta("source", cache.source)
		march_lines.add_child(line)
	line.visible = to_m - from_m > 1.0
	var material := line.material_override as ShaderMaterial
	material.set_shader_parameter("from_m", from_m)
	material.set_shader_parameter("to_m", to_m)

func march_ribbon(points: PackedVector3Array, distances: PackedFloat32Array) -> ArrayMesh:
	var samples := PackedVector3Array()
	var along := PackedFloat32Array()
	for i in range(1, points.size()):
		var length := distances[i] - distances[i - 1]
		var steps := maxi(1, ceili(length / 1.5))
		for k in steps:
			samples.append(points[i - 1].lerp(points[i], float(k) / steps))
			along.append(distances[i - 1] + length * k / steps)
	if not points.is_empty():
		samples.append(points[-1])
		along.append(distances[-1])
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in range(1, samples.size()):
		var a := samples[j - 1]
		var b := samples[j]
		var across := Vector3(-(b.z - a.z), 0.0, b.x - a.x)
		if across.length_squared() < 0.000001:
			continue
		across = across.normalized() * 0.5
		a.y = line_height(a)
		b.y = line_height(b)
		var corners := [[a - across, along[j - 1], 0.0], [a + across, along[j - 1], 1.0], [b - across, along[j], 0.0], [b + across, along[j], 1.0]]
		for c in [0, 1, 2, 2, 1, 3]:
			tool.set_uv(Vector2(corners[c][1], corners[c][2]))
			tool.add_vertex(corners[c][0])
	return tool.commit()

func line_height(q: Vector3) -> float:
	return (terrain_y(q) if map_name == "world" else maxf(sample_city(q.x, q.z), -1.0)) + 0.3

# On the raft the formation stands closer together.
const RAFT_PACK := 0.62

func sync_raft(actor: Node3D, cache: Dictionary, crossing: float, heading: float, server_ms: float, docked := -1.0, anchor := Vector3.ZERO) -> void:
	var raft := actor.get_node_or_null("Ferry") as Node3D
	if crossing < 0.0 and docked < 0.0:
		if raft != null:
			raft.hide()
		return
	if raft == null:
		var width := 3.0
		var length := 4.0
		for slot in cache.slots:
			width = maxf(width, absf(float(slot.side)) * RAFT_PACK * 2.0 + 2.2)
			length = maxf(length, absf(float(slot.rear)) * RAFT_PACK + 3.4)
		raft = make_raft(minf(width, 14.0), minf(length, 18.0))
		actor.add_child(raft)
	raft.show()
	# Centred on the formation (its slots run backwards from the leader), bobbing gently.
	var depth := 0.0
	for slot in cache.slots:
		depth = maxf(depth, float(slot.rear))
	var back := Vector3(-sin(heading), 0.0, -cos(heading)) * depth * RAFT_PACK * 0.5
	if crossing < 0.0:
		# The front has landed: the raft waits at the far bank, its last rows still on it.
		var ferry: PackedByteArray = cache.ferry
		var points: PackedVector3Array = cache.points
		for i in range(1, ferry.size()):
			if ferry[i] != 1:
				continue
			var a := points[i - 1]
			var b := points[i]
			var along := Vector3(b.x - a.x, 0.0, b.z - a.z).normalized()
			var dock := Vector3(b.x, FERRY_DECK, b.z) - along * (depth * RAFT_PACK * 0.5 + 1.0)
			heading = atan2(along.x, along.z)
			back = dock - anchor
			back.y = FERRY_DECK - anchor.y
			break
	raft.position = back + Vector3.UP * (0.05 * sin(server_ms * 0.0021))
	raft.rotation = Vector3(0.02 * sin(server_ms * 0.0017), heading, 0.015 * sin(server_ms * 0.0013))

# Turning speed of a soldier: the shown heading follows the wanted one with this
# rate (1/s), on the presentation clock. The wanted heading switches at once at
# the start of a charge, on reaching the battle place and when the army turns
# home; drawn directly, those were turns of up to 180 degrees within one frame.
const TURN_RATE := 12.0

func smooth_yaw(unit: Node3D, wanted: float, server_ms: float) -> float:
	var at := float(unit.get_meta("yaw_at", -INF))
	var yaw := wanted
	if at > -INF and server_ms >= at and server_ms - at < 600.0:
		yaw = lerp_angle(float(unit.get_meta("yaw", wanted)), wanted, 1.0 - exp(-TURN_RATE * (server_ms - at) / 1000.0))
	unit.set_meta("yaw", yaw)
	unit.set_meta("yaw_at", server_ms)
	return yaw

# The planner's ground support (tilt) with the shown heading.
static func support_basis(support: Basis, yaw: float) -> Basis:
	var normal := support.y.normalized()
	var forward := Basis(Vector3.UP, yaw).z.slide(normal).normalized()
	return Basis(normal.cross(forward).normalized(), normal, forward)

# Heading of the route at a distance along it, sampled `window` metres both ways.
func route_heading(cache: Dictionary, travel: float, fallback: float, window := 0.8) -> float:
	var total := maxf(0.001, float(cache.distances[-1]))
	var direction := along_route(cache, (travel + window) / total) - along_route(cache, (travel - window) / total)
	return atan2(direction.x, direction.z) if direction.length_squared() > 0.0001 else fallback

# Where a soldier `rear` metres behind the anchor and `side` metres across walks:
# on the route itself at its own distance, so a column turns at a corner row by
# row. Moving the whole formation rigidly with the anchor's heading swung the rear
# rows around the anchor at every turn of the route (15 m behind the anchor, a
# 90-degree corner moved them ~1.3 m per frame, about 200 m/s). The heading is
# sampled over COLUMN_TURN_M both ways so a row turns over a few metres of
# travel. Returns [position (not grounded), heading]. Behind the start of the
# route, the first leg continues backwards. The battle planner starts each
# approach from this same point at the halt (it used the creature's facing
# instead, so at the start of a charge rear soldiers jumped up to ~6 m).
const COLUMN_TURN_M := 2.5

func column_point(cache: Dictionary, travel: float, side: float, rear: float, fallback: float, from_start := false) -> Array:
	var total := maxf(0.001, float(cache.distances[-1]))
	var at := travel - rear
	if from_start:
		# Leaving a hunt the column forms from the start of the way home; rows
		# beyond it would stand on the far side of the creature.
		at = maxf(at, 0.0)
	var heading := route_heading(cache, maxf(at, 0.0), fallback, COLUMN_TURN_M)
	var base: Vector3
	if at >= 0.0:
		base = along_route(cache, at / total)
	else:
		base = (cache.points[0] as Vector3) - Vector3(sin(heading), 0.0, cos(heading)) * (-at)
	return [base + Vector3(cos(heading), 0.0, -sin(heading)) * side, heading]

static func gait_for(unit_id: String, ground_speed: float, scale := FIELD_UNIT_SCALE, run_max := RUN_TEMPO.y) -> Array:
	# Picks walk or run and the playback tempo at which planted feet travel at the
	# formation's ground speed, so soldiers do not skate along the route. The gait
	# changes at the geometric mean of both strides, which keeps tempo distortion
	# symmetric; only speeds outside the supported range are clamped. A smaller
	# soldier (`scale`, the world map) takes shorter steps, so the same speed needs
	# a quicker tempo, up to `run_max`.
	var stance: Dictionary = GaitTable.STANCE_SPEED.get(unit_id, {})
	var walk := float(stance.get("walk", 0.0)) * scale
	var run := float(stance.get("run", 0.0)) * scale
	var trot := float(stance.get("trot", 0.0)) * scale
	if walk <= 0.0 or ground_speed <= 0.0:
		return ["walk", 1.0]
	if trot > 0.0:
		# New equine cycles have separate contact intervals. The normal 7/8 m/s
		# march uses gallop near 1x; a mixed slow column uses walk or diagonal trot.
		var chosen := "walk" if ground_speed < sqrt(walk*trot) else "trot" if ground_speed < sqrt(trot*run) else "run"
		return [chosen, ground_speed/(float(stance[chosen])*scale)]
	if run <= 0.0 or ground_speed < sqrt(walk * run):
		return ["walk", clampf(ground_speed / walk, WALK_TEMPO.x, INF)]
	return ["run", clampf(ground_speed / run, 0.0, run_max)]

# Visibility of actors that move as a group. A single anchor point decided
# whether a whole army was drawn: when the column's front (or the halt point of a
# hunt) left the screen, every soldier vanished at once although most of them
# were still in view. Now an actor is drawn while any part of its conservative
# bounds is inside the camera frustum; the renderer still culls each soldier.
var view_planes: Array[Plane] = []

# Once per present_* call: the camera has its pose for this frame by then.
func refresh_view_planes() -> void:
	view_planes.assign(camera.get_frustum())

func sphere_in_view(centre: Vector3, radius: float) -> bool:
	for plane in view_planes:
		if plane.distance_to(centre) > radius:
			return false
	return true

# Farthest a soldier of this formation stands from its anchor (slot offsets,
# the fight ring of a battle without places, a rider's length), plus a margin.
static func formation_extent(slots: Array) -> float:
	var extent := 0.0
	for slot in slots:
		extent = maxf(extent, Vector2(float(slot.side) * 1.22, float(slot.rear) + (4.0 if slot.ranged else 2.5)).length())
	return maxf(extent, 7.5) + 3.0

# Radius around the creature that holds every battle place of a hunt.
static func battle_reach(plan: Dictionary) -> float:
	if plan.has("reach"):
		return float(plan.reach)
	var beast: Vector3 = plan.get("beast", Vector3.ZERO)
	var reach := 0.0
	for place: Vector3 in plan.get("places", {}).values():
		reach = maxf(reach, Vector2(place.x - beast.x, place.z - beast.z).length())
	if plan.get("locked", false):
		plan.reach = reach + 3.0
	return reach + 3.0

func retain_hidden_actors(parent: Node3D, known: Dictionary, shown: Dictionary, maximum: int) -> void:
	var hidden: Array[Node] = []
	var now := Time.get_ticks_msec()
	for actor in parent.get_children():
		var id := String(actor.name)
		if shown.has(id):
			continue
		actor.hide()
		actor.process_mode = Node.PROCESS_MODE_DISABLED
		if not known.has(id) or now - int(actor.get_meta("last_visible_ticks", 0)) > ACTOR_CACHE_SECONDS * 1000:
			actor.queue_free()
		else:
			hidden.append(actor)
	if hidden.size() > maximum:
		hidden.sort_custom(func(a, b): return a.get_meta("last_visible_ticks", 0) < b.get_meta("last_visible_ticks", 0))
		for index in hidden.size() - maximum:
			hidden[index].queue_free()

func draw_arrow(unit: Node3D, shaft: MeshInstance3D, destination: Vector3, phase: float, unit_id := "ENG-03", event_id := "") -> void:
	if shaft == null:
		if shaft_mesh == null:
			shaft_mesh = CylinderMesh.new()
			shaft_mesh.top_radius = 0.023
			shaft_mesh.bottom_radius = 0.023
			shaft_mesh.height = 1.0
			shaft_mesh.radial_segments = 5
			var material := StandardMaterial3D.new()
			material.albedo_color = Color("#ffd480")
			material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			shaft_mesh.material = material
		shaft = MeshInstance3D.new()
		shaft.name = "Arrow"
		shaft.mesh = shaft_mesh
		shaft.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		unit.add_child(shaft)
	if shaft.get_meta("event_id", "") != event_id or not shaft.has_meta("origin"):
		var origin := unit.global_position + Vector3.UP * 1.35 * unit_k
		var bone_name := "wrist.L"
		for skeleton: Skeleton3D in unit.find_children("*","Skeleton3D",true,false):
			var bone := skeleton.find_bone(bone_name)
			if bone >= 0:
				origin = (skeleton.global_transform*skeleton.get_bone_global_pose(bone)).origin
				break
		shaft.set_meta("origin",origin)
		shaft.set_meta("event_id",event_id)
	var a: Vector3 = shaft.get_meta("origin")
	var b := destination + Vector3.UP * 1.45 * beast_k
	var tip := a.lerp(b, phase) + Vector3.UP * sin(PI * phase) * 0.6 * unit_k
	var direction := (b-a).normalized()
	var length := (0.42 if unit_id == "ENG-04" else 0.85) * unit_k
	var tail := tip-direction*length
	if direction.length_squared() <= 0.00001:
		shaft.hide()
		return
	var rotation := Basis(Quaternion(Vector3.UP, direction.normalized()))
	shaft.global_transform = Transform3D(rotation.scaled(Vector3.ONE), (tip + tail) * 0.5)
	shaft.scale.y = length / unit.scale.y
	shaft.show()

func present_training(state: Dictionary, server_ms: float) -> void:
	var retained := {}
	var queues: Dictionary = state.city.military.get("queues", {})
	for marker in place_markers:
		if marker.kind != "building":
			continue
		var group: String = data.trainingGroups.get(marker.item.type, "")
		if group not in ["INF-01", "RNG-01", "CAV-01"]:
			continue
		var id: String = marker.id
		var p: Vector3 = marker.position + Vector3(0.2, 0.0, 2.95)
		p.y = sample_city(p.x, p.z)
		if not camera.is_position_in_frustum(p + Vector3.UP):
			continue
		var orders: Array = queues.get(id, [])
		var order: Dictionary = {} if orders.is_empty() else orders[0]
		var active := not order.is_empty() and server_ms >= float(order.startsAt) and server_ms < float(order.endsAt)
		var fallback: String = {"INF-01":"ENG-01", "RNG-01":"ENG-03", "CAV-01":"ENG-06"}[group]
		var unit_id: String = order.get("unitId", fallback) if active else fallback
		if not data.unitModels.has(unit_id):
			unit_id = fallback  # a retired unit id (DRENOVAR-V6-ROSTER-5) from an old answer
		var visual: Dictionary = data.unitModels[unit_id]
		var actor := training.get_node_or_null(NodePath(id)) as Node3D
		if actor != null and actor.get_meta("unit_id") != unit_id:
			actor.free()
			actor = null
		if actor == null:
			actor = add_warrior(training, visual.preview, model_transform(p.x, p.y, p.z, PI, 1.0))
			actor.name = id
			actor.set_meta("unit_id", unit_id)
		var clip: String = visual.drill if active else "Idle"
		if actor.get_meta("clip", "") != clip:
			play_animation(actor, clip)
			actor.set_meta("clip", clip)
		retained[id] = true
	for actor in training.get_children():
		if not retained.has(String(actor.name)):
			actor.queue_free()

func update_camera(delta: float, snap := false) -> void:
	if not snap and camera_target == target and camera_zoom == zoom and camera_yaw == world_yaw:
		if camera_dirty:
			refresh_camera_visibility()
		return
	var weight := 1.0 if snap else 1.0 - exp(-CAMERA_RESPONSE * delta)
	camera_target = camera_target.lerp(target, weight)
	camera_zoom = lerpf(camera_zoom, zoom, weight)
	camera_yaw = lerp_angle(camera_yaw, world_yaw, weight)
	if absf(angle_difference(camera_yaw, world_yaw)) < 0.0001:
		camera_yaw = world_yaw
	if camera_target.distance_squared_to(target) < 0.000001:
		camera_target = target
	if absf(camera_zoom - zoom) < 0.001:
		camera_zoom = zoom
	apply_camera_pose()
	refresh_camera_visibility(snap)

func refresh_camera_visibility(force := false) -> void:
	camera_dirty = false
	if force or camera_target.distance_squared_to(last_cull_target) >= 1.4 * 1.4 \
		or absf(camera_zoom - last_cull_zoom) >= maxf(0.65, camera_zoom * 0.014) \
		or absf(angle_difference(camera_yaw, last_cull_yaw)) >= 0.012:
		update_visible_batches()

func apply_camera_pose() -> void:
	if map_name == "city":
		camera.size = camera_zoom
		camera.position = camera_target + Vector3(75, 83, 75)
		camera.look_at(camera_target, Vector3.UP)
	else:
		var world_target := Vector3(camera_target.x, 1, camera_target.z)
		var direction := Vector3(0, sin(WORLD_CAMERA_TILT), cos(WORLD_CAMERA_TILT)).rotated(Vector3.UP, camera_yaw)
		camera.position = world_target + direction * camera_zoom
		camera.look_at(world_target, Vector3.UP)

func begin_direct_manipulation() -> void:
	# Interrupt a scripted fly-to at its displayed pose, without a jump.
	target = camera_target
	zoom = camera_zoom
	world_yaw = camera_yaw

func commit_direct_manipulation() -> void:
	# Pose is cheap and immediate. Cull/upload at most once in the render-frame loop.
	camera_target = target
	camera_zoom = zoom
	camera_yaw = world_yaw
	apply_camera_pose()
	camera_dirty = true

func ground_at(screen_position: Vector2) -> Vector3:
	var origin := camera.project_ray_origin(screen_position)
	var ray := camera.project_ray_normal(screen_position)
	var height := camera_target.y if map_name == "city" else 1.0
	if absf(ray.y) < 0.001:
		return camera_target
	return origin + ray * ((height - origin.y) / ray.y)

func drag_between(previous: Vector2, current: Vector2) -> void:
	# Projection-aware: works with perspective, orthographic view, rotation and aspect ratio.
	shift_camera_target(ground_at(previous) - ground_at(current))
	commit_direct_manipulation()

func pinch_between(previous: Vector2, current: Vector2, ratio: float) -> void:
	var anchor := ground_at(previous)
	change_zoom(ratio)
	commit_direct_manipulation()
	shift_camera_target(anchor - ground_at(current))
	commit_direct_manipulation()

func pan(delta: Vector2) -> void:
	var size := get_viewport().get_visible_rect().size
	var height := camera_zoom if map_name == "city" else 2 * camera_zoom * tan(deg_to_rad(camera.fov) * 0.5)
	var speed := height / maxf(1, size.y)
	var horizontal := camera.global_basis.x * -delta.x * speed
	var back := camera.global_basis.z
	var along_ground := Vector3(back.x, 0, back.z).normalized()
	var vertical := along_ground * (-delta.y * speed / maxf(0.35, absf(back.y)))
	shift_camera_target(horizontal + vertical)

func change_zoom(amount: float) -> void:
	zoom = clampf(zoom / amount, 15, 500) if map_name == "world" else clampf(zoom / amount, 24, 120)

func zoom_at(amount: float, position: Vector2) -> void:
	var old_zoom := zoom
	change_zoom(amount)
	if old_zoom == zoom:
		return
	var origin := camera.project_ray_origin(position)
	var ray := camera.project_ray_normal(position)
	if absf(ray.y) < 0.001:
		return
	var height := camera_target.y if map_name == "city" else 1.0
	var anchor := origin + ray * ((height - origin.y) / ray.y)
	shift_camera_target((anchor - camera_target) * (1.0 - zoom / old_zoom))

func shift_camera_target(offset: Vector3) -> void:
	target.x = clampf(target.x + offset.x, -147, 147)
	target.z = clampf(target.z + offset.z, -118, 118)

# [forest_rescue_v1 hook] 1022: lazy world layer. Called by ForestGame once the city is interactive and the
# server projects the adventure (QA may call it directly). The layer's scripts load one per frame, its
# setup runs hidden (heavy steps on worker threads, the rest sliced), the rebuilt ground tiles and river
# are committed together, then the kit forest replaces the 1021 trees in a staged swap.
func attach_forest_world(gate := Callable()) -> void:
	if forest_world != null or forest_attach_state != "" or map_name != "city":
		return
	if not ForestFlags.enabled():
		forest_attach_state = "off"   # rollback flag: the 1021 forest stays (asked once, not every frame)
		return
	forest_attach_state = "attaching"
	await ForestFlags.load_staged(ForestFlags.WORLD_LAYER, get_tree(), gate)
	var script: Variant = load(ForestFlags.WORLD_LAYER_SCRIPT)
	if not script is GDScript or not is_inside_tree():
		forest_attach_state = "failed"
		return
	var world: Node3D = script.new()
	world.deferred_commit = true
	world.visible = false
	world.city_state = forest_last_state.get("city", {}) if forest_last_state.get("city") is Dictionary else {}
	var adventure: Variant = forest_last_state.get("adventure")
	world.initial_adventure = adventure if adventure is Dictionary else {}
	add_child(world)
	await world.setup(self, city_ground_meshes)
	if not is_instance_valid(world) or not is_inside_tree():
		forest_attach_state = "failed"
		return
	world.commit_ground()
	forest_world = world
	world.visible = true
	if not forest_last_city.is_empty():
		await build_forest(forest_last_city, forest_last_exclusions, true, true, true)
	if is_instance_valid(forest_world):
		forest_world.apply_state_hint(forest_last_state)
		forest_world.on_camera_changed()
	forest_attach_state = "attached"

# [forest_rescue_v1 hook] World layer for «Лес потерянных» (src/forest_rescue/world/*).
# Loaded only when the flag is ON, so a broken/missing layer can never affect the rollback path.
func _setup_forest_world() -> void:
	if map_name != "city" or not ForestFlags.enabled():
		return
	var script: Variant = load("res://src/forest_rescue/world/forest_world.gd")
	if not script is GDScript:
		push_error("forest_rescue_v1: world layer script missing; legacy forest kept")
		return
	forest_world = script.new()
	add_child(forest_world)
	await forest_world.setup(self, city_ground_meshes)

# --- Building placement (construction mode) ------------------------------------
# A ghost of the chosen building that the player drags across the city with a
# finger; free plots are outlined (green: ready, amber: forest to clear) and the
# ghost snaps to the plot under it. Only visuals live here; main.gd owns input
# and commands.
var placement: Node3D
var placement_ghost: Node3D
var placement_plate: MeshInstance3D
var placement_rings: Array[MeshInstance3D] = []
var placement_overlay: StandardMaterial3D
var placement_lift := 0.0

static func placement_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = color
	material.no_depth_test = false
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material

func show_placement(model_path: String, model_scale: float, plots: Array) -> void:
	clear_placement()
	placement = Node3D.new()
	placement.name = "Placement"
	add_child(placement)
	for plot in plots:
		var ring := MeshInstance3D.new()
		var torus := TorusMesh.new()
		torus.inner_radius = 5.3
		torus.outer_radius = 5.9
		torus.rings = 48
		torus.ring_segments = 6
		ring.mesh = torus
		ring.scale = Vector3(1.0, 0.12, 1.0)
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.material_override = placement_material(Color(0.45, 0.95, 0.55, 0.55) if plot.cleared else Color(1.0, 0.72, 0.3, 0.5))
		ring.position = plot.position + Vector3.UP * 0.25
		placement.add_child(ring)
		placement_rings.append(ring)
	placement_plate = MeshInstance3D.new()
	var plate := PlaneMesh.new()
	plate.size = Vector2(12.4, 12.4)
	placement_plate.mesh = plate
	placement_plate.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	placement_plate.material_override = placement_material(Color(0.4, 0.95, 0.5, 0.32))
	placement.add_child(placement_plate)
	placement_ghost = add_model(placement, model_path, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * model_scale), Vector3.ZERO))
	placement_overlay = placement_material(Color(0.5, 1.0, 0.6, 0.18))
	for part: MeshInstance3D in placement_ghost.find_children("*", "MeshInstance3D", true, false):
		part.material_overlay = placement_overlay

## Placing a new building of the V6 economy (premium UI stage 3, src/v6_build.gd): the free
## plots of its terrain glow warm gold (plot_glow.gdshader on a quad above each plot); the
## ghost and its plate wait hidden until the player taps a plot (move_placement shows them).
## The materials of the placement on glowing plots live as long as the city: a
## StandardMaterial3D's shader is shared per feature set and freed with its last material, so
## new ones on every placement rebuilt two shader variants on the tap (about 15 ms).
var plot_ring_material: ShaderMaterial
var plot_plate_material: StandardMaterial3D
var plot_ghost_material: StandardMaterial3D
## The translucent ghost: one material per surface material of the level scenes (uniforms of
## one shader, placement_ghost.gdshader), kept for the session.
var ghost_template: ShaderMaterial
var ghost_materials := {}

## Creates them ahead of the first placement (the construction strip calls this while open).
func prepare_plot_glow() -> void:
	if plot_ring_material != null:
		return
	plot_ring_material = ShaderMaterial.new()
	plot_ring_material.shader = PLOT_GLOW
	plot_plate_material = placement_material(Color(1.0, 0.82, 0.45, 0.14))
	# The ghost shows through the trees of a forest plot as a faint gold silhouette.
	plot_ghost_material = placement_material(Color(1.0, 0.85, 0.5, 0.1))
	plot_ghost_material.no_depth_test = true
	ghost_template = ShaderMaterial.new()
	ghost_template.shader = PLACEMENT_GHOST
	for material: Material in [plot_ring_material, plot_plate_material, plot_ghost_material, ghost_template]:
		material.get_rid()

func show_plot_glow(model_path: String, model_scale: float, plots: Array) -> void:
	clear_placement()
	prepare_plot_glow()
	placement = Node3D.new()
	placement.name = "Placement"
	add_child(placement)
	var glow := plot_ring_material
	var quad := PlaneMesh.new()
	quad.size = Vector2(15.0, 15.0)
	for plot in plots:
		var ring := MeshInstance3D.new()
		ring.mesh = quad
		ring.material_override = glow
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.position = plot.position + Vector3.UP * 0.35
		placement.add_child(ring)
		placement_rings.append(ring)
	placement_plate = MeshInstance3D.new()
	var plate := PlaneMesh.new()
	plate.size = Vector2(12.4, 12.4)
	placement_plate.mesh = plate
	placement_plate.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	placement_plate.material_override = plot_plate_material
	placement_plate.visible = false
	placement.add_child(placement_plate)
	placement_ghost = Node3D.new()
	placement_ghost.name = "Ghost"
	placement.add_child(placement_ghost)
	placement_overlay = plot_ghost_material
	placement_ghost.visible = false
	if not model_path.is_empty():
		attach_ghost(model_path, model_scale, placement)

## The ghost's scene loads on a worker thread: a first load() of an unbuilt type's level scene
## took 10-40 ms on the main thread, right on the tap of a card. The ghost stays hidden until a
## plot is chosen, so it is almost always there in time.
func attach_ghost(model_path: String, model_scale: float, session: Node3D) -> void:
	while not model_ready(model_path):
		await get_tree().process_frame
		if session != placement or not is_instance_valid(session):
			return
	if session != placement or not is_instance_valid(placement_ghost):
		return
	var model := add_model(placement_ghost, model_path, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * model_scale), Vector3.ZERO))
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if part.mesh != null:
			for index in part.mesh.get_surface_count():
				part.set_surface_override_material(index, ghost_material(part.get_active_material(index)))
		part.material_overlay = placement_overlay

## The translucent ghost version of a level scene's surface material (its colours, see
## placement_ghost.gdshader).
func ghost_material(source: Material) -> ShaderMaterial:
	var key := source.get_rid().get_id() if source != null else 0
	if ghost_materials.has(key):
		return ghost_materials[key]
	var ghost := ShaderMaterial.new()
	ghost.shader = PLACEMENT_GHOST
	if source is BaseMaterial3D:
		var base := source as BaseMaterial3D
		ghost.set_shader_parameter("albedo_texture", base.albedo_texture)
		ghost.set_shader_parameter("use_texture", 1.0 if base.albedo_texture != null else 0.0)
		ghost.set_shader_parameter("albedo_color", base.albedo_color)
		ghost.set_shader_parameter("triplanar", 1.0 if base.uv1_triplanar else 0.0)
		ghost.set_shader_parameter("uv_scale", base.uv1_scale.x)
	else:
		ghost.set_shader_parameter("use_texture", 0.0)
		ghost.set_shader_parameter("albedo_color", Color(0.85, 0.78, 0.66))
	ghost_materials[key] = ghost
	return ghost

## The chosen plot burns brighter than the others.
func highlight_plot_glow(at: Vector3) -> void:
	for ring: MeshInstance3D in placement_rings:
		var chosen := Vector2(ring.position.x, ring.position.z).distance_to(Vector2(at.x, at.z)) < 0.5
		if chosen and ring.material_override.get_meta("chosen", false) == false:
			var bright := ring.material_override.duplicate() as ShaderMaterial
			bright.set_shader_parameter("chosen", 1.0)
			bright.set_meta("chosen", true)
			ring.material_override = bright
		elif not chosen and ring.material_override.get_meta("chosen", false):
			for other: MeshInstance3D in placement_rings:
				if not other.material_override.get_meta("chosen", false):
					ring.material_override = other.material_override
					break

# valid: green plate (buildable); otherwise amber (forest, must be cleared) or red (no plot).
func move_placement(at: Vector3, plate_state: String, lifted: bool) -> void:
	if not is_instance_valid(placement):
		return
	var color := Color(0.4, 0.95, 0.5) if plate_state == "ready" else (Color(1.0, 0.7, 0.28) if plate_state == "forest" else Color(1.0, 0.36, 0.3))
	# The V6 ghost (translucent, in its own colours) keeps its faint gold plate and silhouette.
	if placement_overlay != plot_ghost_material:
		(placement_plate.material_override as StandardMaterial3D).albedo_color = Color(color, 0.34)
		placement_overlay.albedo_color = Color(color.lightened(0.2), 0.2)
	placement_lift = 1.2 if lifted else 0.0
	placement_plate.position = at + Vector3.UP * 0.18
	placement_ghost.position = at + Vector3.UP * placement_lift
	placement_plate.visible = true
	placement_ghost.visible = true

func placement_position() -> Vector3:
	return placement_plate.position - Vector3.UP * 0.18 if is_instance_valid(placement_plate) else Vector3.ZERO

func clear_placement() -> void:
	if is_instance_valid(placement):
		placement.queue_free()
	placement = null
	placement_ghost = null
	placement_plate = null
	placement_rings.clear()

# City-only helpers are constructed with every Landscape, including the world.
# Unparented helpers are not freed by Node's normal child destruction.
func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		for helper in [works, works2, town]:
			if is_instance_valid(helper) and helper.get_parent() == null:
				helper.free()
