extends Node3D

const WarriorVisual = preload("res://src/warrior_visual.gd")

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
# B18 gate scenes are authored at plot scale; in the city wall they stand larger so
# the carriageway and towers match the height of the ring curtain.
const GATE_SCENE_SCALE := 1.6
const GATE_SCENE_HALF_SPAN := 5.9
var works := CityWorks.new()
var walls := CityWalls.new()
var forest_materials := {}
var focus_radius := 0.0
var focus_centre := Vector3.ZERO
var fight_positions := {}
var announced_fights := {}
signal fight_started(army_id: String, position: Vector3)
const Formations = preload("res://src/formations.gd")
const GaitTable = preload("res://src/gait_table.gd")
const FIELD_UNIT_SCALE := 1.15
# Slowest walk tempo and fastest run tempo; between them feet match exactly.
const WALK_TEMPO := Vector2(0.55, 0.0)
const RUN_TEMPO := Vector2(0.0, 1.6)
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
	add_child(battle_fx)
	if is_city:
		works.setup(self, data)
		add_child(works)
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

func set_active(active: bool) -> void:
	visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	if active:
		camera.make_current()

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
	for i in range(1, path.size()):
		var a := point(path[i - 1])
		var b := point(path[i])
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

func build_city_roads(city: Dictionary, plots: Array) -> void:
	if is_instance_valid(city_road_mesh):
		city_road_mesh.free()
	city_streets.clear()
	var by_id := {}
	for plot in plots:
		by_id[plot.id] = Vector2(plot.x, plot.z)
	var hall: Dictionary = city.buildings[0]
	for building in city.buildings:
		if building.type in ["ECO-05", "ALT-13"]:
			hall = building
			break
	var a: Vector2 = by_id.get(hall.plotId, Vector2.ZERO)
	a.y += 4.0
	for building in city.buildings:
		if building.id == hall.id or not by_id.has(building.plotId):
			continue
		var end: Vector2 = by_id[building.plotId] + Vector2(0.0, 3.5)
		var previous := a
		for i in range(1, 9):
			var t := i / 8.0
			var next := a.lerp(end, t) + sin(t * PI) * Vector2(1.1, 0.7)
			city_streets.append([previous, next])
			previous = next
	# Roads through the wall gates; the main gate is joined to the town hall.
	if walls.visible:
		for i in walls.gate_roads.size():
			var road: Array = walls.gate_roads[i]
			var start: Vector2 = road[0]
			var finish: Vector2 = road[1]
			for k in 6:
				city_streets.append([start.lerp(finish, k / 6.0), start.lerp(finish, (k + 1) / 6.0)])
			if i == 0:
				var previous := a
				for k in range(1, 11):
					var t := k / 10.0
					var next := a.lerp(start, t) + sin(t * PI) * Vector2(1.4, 0.0)
					city_streets.append([previous, next])
					previous = next
	var strips: Array = []
	for road in city_streets:
		var start: Vector2 = road[0]
		var end: Vector2 = road[1]
		var n := (end-start).orthogonal().normalized()*0.7
		var quad: Array = []
		for p in [start+n,start-n,end+n,end-n]:
			quad.append(Vector3(p.x,sample_city(p.x,p.y)+0.065,p.y))
		strips.append(quad)
	if not strips.is_empty():
		city_road_mesh = path_mesh(strips,surface("path"),0.35)

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

func build_forest(city: Dictionary, exclusions: Array, rebuild_ground := true, staged := false) -> void:
	# Trees and stumps depend on felled trees; understory and meadow only on exclusions
	# and streets. A felled tree therefore never rebuilds the ground cover.
	if is_instance_valid(trees.get("node")):
		trees.node.free()
	if rebuild_ground:
		for child in city_ground_detail.get_children():
			child.free()
	render_batches = render_batches.filter(func(batch): return is_instance_valid(batch.node))
	var group := Node3D.new()
	group.name = "Forest"
	add_child(group)
	trees["node"] = group
	selectable_trees.clear()
	standing_tree_cells.clear()
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
		if felled.has(tree.id):
			if not details.has("tree_stump"):
				details.tree_stump = []
			details.tree_stump.append(model_transform(p.x, p.y, p.z, 0.0, 0.7))
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
		if inside_exclusions(prop.x, prop.z, exclusions) or walls.blocks(prop.x, prop.z):
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
	for segment in city_streets:
		var near := Geometry2D.get_closest_point_to_segment(p, segment[0], segment[1])
		if p.distance_squared_to(near) < width * width:
			return true
	return false

func inside_exclusions(x: float, z: float, exclusions: Array) -> bool:
	for rect: Rect2 in exclusions:
		if rect.has_point(Vector2(x, z)):
			return true
	return false

const SETUP_SLICE_USEC := 3500
const BACKGROUND_SLICE_USEC := 2000
# Set while the scene is prepared in the background (the other scene is on
# screen). It returns false while the player is touching or the camera moves, and
# the build waits; cleared when the player asks for this scene, so it finishes at
# full speed.
var background_gate := Callable()

func yield_frame() -> void:
	# One frame; in a background build, also waits while the player interacts.
	await get_tree().process_frame
	while background_gate.is_valid() and not background_gate.call():
		await get_tree().process_frame

func setup_slice(started: int) -> int:
	# Yields to the next frame once the current one has spent its setup budget.
	var budget := BACKGROUND_SLICE_USEC if background_gate.is_valid() else SETUP_SLICE_USEC
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
func update_battle_focus(centre: Vector3, wanted: float, delta: float) -> void:
	if wanted > 0.0:
		focus_centre = centre
	focus_radius = move_toward(focus_radius, wanted, delta * 30.0)
	RenderingServer.global_shader_parameter_set(&"battle_focus",
		Vector4(focus_centre.x, focus_centre.y, focus_centre.z, focus_radius))

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
	present_armies(state, float(state.serverTime))

func present_city(state: Dictionary, staged := false) -> void:
	# staged=true is used only by setup(): the first build yields between phases so
	# no single frame carries the whole settlement. Later updates stay synchronous.
	var city: Dictionary = state.city
	var progress: Dictionary = city.get("progress", {})
	var kingdom: Variant = city.get("kingdom")
	var construction: Variant = kingdom if kingdom is Dictionary else city.get("legacyUpgrades")
	var order: Variant = construction.get("order") if construction is Dictionary else null
	var district: Variant = city.military.get("garrison")
	var army: Dictionary = city.military.get("owned", {})
	var key := JSON.stringify([city.buildings, progress.get("sites", []), progress.get("felled", []),
		progress.get("cleared", []), kingdom.get("clearedPlots", []) if kingdom is Dictionary else [],
		order, district])
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
				var scale := float(asset.scale)*(1+0.055*(int(building.level)-1))
				wanted_buildings.append(["model", asset.path, model_transform(x,y,z,0,scale)])
				wanted_workers.append([id, Vector3(x,y,z)])
				var levels: Dictionary = data.architecture.get(building.type, {})
				var upgrade: String = levels.get(str(int(building.level)), "")
				if not upgrade.is_empty():
					wanted_buildings.append(["detail", upgrade, Transform3D(Basis.IDENTITY, Vector3(x,y,z))])
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
	walls.main_gate_span = GATE_SCENE_HALF_SPAN * GATE_SCENE_SCALE
	walls.plan(hall_spot, hall_level, defence_level, walls_shown(hall_level, defence_level), obstacles, district, sample_city)
	if walls.visible and walls.custom_main_gate:
		var out := walls.main_gate_outward
		var gate_basis := Basis(Vector3.UP, atan2(out.x, out.z)).scaled(Vector3.ONE * GATE_SCENE_SCALE)
		wanted_buildings.append(["model", gate_scene.path, Transform3D(gate_basis, walls.main_gate)])
	for building in wall_markers:
		place_markers.append({"position": walls.main_gate + Vector3.UP * 7.0, "id": building.id, "kind": "building", "item": building, "wall": true})
	if walls.visible and wall_markers.is_empty():
		place_markers.append({"position": walls.main_gate + Vector3.UP * 7.0, "id": "city-walls", "kind": "wall",
			"item": {"type": "SUP-03", "level": 1, "wall": true}})
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
	if walls.signature != geometries.get("wall_signature", "") or (walls.visible and not is_instance_valid(walls.node)):
		geometries["wall_signature"] = walls.signature
		walls.build(self)
	works.observe_city(city, plot_positions)
	work_sites = plot_positions
	if staged:
		await yield_frame()
	sync_city_workers(wanted_workers)
	var road_key := JSON.stringify([city.buildings.map(func(b): return [b.id, b.type, b.plotId]), plots.map(func(p): return [p.id, p.x, p.z]),
		walls.signature if walls.visible else ""])
	if road_key != geometries.get("road_signature", "") or not is_instance_valid(city_road_mesh):
		geometries["road_signature"] = road_key
		build_city_roads(city, plots)
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
		elif visible_rank and made < 4:
			var actor := add_warrior(parade, data.unitModels[slot.id].field, Transform3D(Basis.IDENTITY, slot.position))
			actor.name = "rank" + str(i)
			play_animation(actor, "Idle", "", -1.0, fposmod(float(i) * 0.381966, 1.0))
			made += 1

func present_creatures(state: Dictionary, server_ms: float, delta: float) -> void:
	var rows: Array = state.world.encounters if map_name == "world" else state.get("encounters", [])
	var armies: Array = state.world.armies if map_name == "world" else state.get("armies", [])
	var battles := {}
	for army in armies:
		if army.status == "fighting":
			battles[army.target] = army
	creature_markers.clear()
	var retained := {}
	var known := {}
	var cues := {}
	var created := false
	for encounter in rows:
		# A creature under attack stays on the field for the whole fight even when the
		# server has already recorded the outcome (status/hp are final at battle start).
		if (encounter.status == "defeated" or int(encounter.get("hp", 1)) <= 0) and not battles.has(encounter.id):
			continue
		var species: String = encounter.get("species", "velkor")
		if not data.creatureModels.has(species):
			continue
		var p := point(encounter.position)
		var heading := 0.0
		var moving: bool = encounter.get("behavior", "") == "roaming"
		var path: Array = encounter.get("patrol", [])
		var id: String = encounter.id
		known[id] = true
		if battles.has(id):
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
		p = ground_point(p)
		creature_markers.append({"position":p + Vector3.UP * 2.5, "id":id, "kind":"encounter", "item":encounter})
		var range_limit := 54.0 if map_name == "city" else 64.0
		var close_enough := Vector2(p.x - camera_target.x, p.z - camera_target.z).length_squared() <= range_limit * range_limit
		if not close_enough or (map_name == "world" and camera_zoom > 132.0):
			continue
		var actor := creatures.get_node_or_null(NodePath(id)) as Node3D
		if actor == null:
			if created:
				continue
			var variant := clampi(int(encounter.level), 1, 3)
			var scene := scene_resource(data.creatureModels[species][variant - 1])
			actor = scene.instantiate() as Node3D
			actor.name = id
			actor.position = p
			actor.scale = Vector3.ONE * (1.02 + 0.16 * variant)
			creatures.add_child(actor)
			created = true
		retained[id] = true
		actor.show()
		actor.process_mode = Node.PROCESS_MODE_INHERIT
		actor.set_meta("last_visible_ticks", Time.get_ticks_msec())
		var clip := "Walk" if moving else "Idle"
		var clip_phase := -1.0
		if battles.has(id):
			var army: Dictionary = battles[id]
			var elapsed := server_ms - float(army.battleAt)
			heading = float(army_routes.get(army.id, {}).get("heading", 0.0)) + PI
			var events: Array = army.get("events", [])
			if army.get("battle") is Dictionary:
				events = army.battle.get("events", [])
			var hit := -INF
			var attack := -INF
			var charge := false
			for event in events:
				var at := float(event[0]) if event is Array else float(event.at)
				var kind: String = event[1] if event is Array else event.kind
				if kind == "soldier_attack":
					if at <= elapsed and elapsed - at < 420.0:
						hit = at
				elif at >= elapsed - 430.0 and at <= elapsed + 560.0 and attack == -INF:
					attack = at
					charge = kind == "antler_charge"
			var fallen_at := present_battle_fx(id, p, encounter, army, elapsed, events)
			if fallen_at > -INF and elapsed >= fallen_at:
				attack = -INF
				hit = -INF
				clip = "Death"
				clip_phase = clampf((elapsed - fallen_at) / 1200.0, 0.0, 1.0)
			elif attack > -INF:
				clip = "Alert" if charge and elapsed < attack - 260.0 else "Attack"
				clip_phase = (elapsed - attack + 560.0) / 300.0 if clip == "Alert" else (elapsed - attack + 260.0) / 690.0
				var lunge := sin(PI * clampf((elapsed - attack + 210.0) / 590.0, 0.0, 1.0)) * (1.8 if charge else 0.5)
				p = ground_point(p + Vector3(sin(heading), 0, cos(heading)) * lunge)
				cues[id] = true
				show_battle_cue(id, p, Color("#fcc069") if charge else Color("#e89568"), clip_phase)
			elif hit > -INF:
				clip = "Hit"
				clip_phase = (elapsed - hit) / 420.0
				cues[id] = true
				show_battle_cue(id, p, Color("#f3d789"), clip_phase)
		actor.rotation.y = lerp_angle(actor.rotation.y, heading, 1.0 - exp(-10.0 * delta))
		actor.position = actor.position.lerp(p, 1.0 - exp(-5.0 * delta))
		if clip_phase >= 0.0 or actor.get_meta("clip", "") != clip:
			play_animation(actor, clip, "Idle", clip_phase)
			actor.set_meta("clip", clip)
	retain_hidden_actors(creatures, known, retained, MAX_HIDDEN_CREATURES)
	# Clear the canopy around the fight closest to the camera centre.
	var focus_wanted := 0.0
	var focus_at := focus_centre
	var best := INF
	for fight_id in fight_positions:
		var at: Vector3 = fight_positions[fight_id]
		var gap := Vector2(at.x - camera_target.x, at.z - camera_target.z).length_squared()
		if gap < best:
			best = gap
			focus_at = at
			focus_wanted = 19.0 if map_name == "city" else 12.0
	fight_positions.clear()
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
	update_battle_focus(focus_at, focus_wanted, delta)
	battle_fx.finish()
	for cue in effects.get_children():
		if not cues.has(String(cue.name)):
			cue.queue_free()

# Damage timeline of one battle from the server events: soldier hits with the
# creature's remaining hp, and the creature's strikes on formation members.
var fx_timelines := {}

func battle_timeline(army: Dictionary, encounter: Dictionary, events: Array) -> Dictionary:
	var cached: Dictionary = fx_timelines.get(army.id, {})
	if cached.get("source") == events:
		return cached
	var spec: Dictionary = encounter.get("spec", {})
	var start_hp := float(spec.get("hp", encounter.get("maxHp", encounter.get("hp", 1))))
	var hits: Array = []
	var strikes: Array = []
	var ordered := events.duplicate()
	ordered.sort_custom(func(a, b): return (float(a[0]) if a is Array else float(a.at)) < (float(b[0]) if b is Array else float(b.at)))
	var hp := start_hp
	for event in ordered:
		var e: Array = event if event is Array else [event.at, event.kind, event.get("unitId", ""), event.get("index", 0), event.get("hp")]
		if e[1] == "soldier_attack":
			var after: float = float(e[4]) if e.size() > 4 and e[4] != null else hp
			hits.append([float(e[0]), maxf(0.0, hp - after), after])
			hp = after
		else:
			strikes.append([float(e[0]), "%s:%d" % [e[2], int(e[3])], e[1]])
	cached = {"source": events, "hits": hits, "strikes": strikes, "max": maxf(1.0, start_hp)}
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
	battle_fx.ring(p.lerp(centre, 0.5), maxf(7.5, p.distance_to(centre) * 0.5 + 6.0), Color("#62e07a"))
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
		if age <= 900.0 and float(hit[1]) > 0.0:
			# Fan consecutive numbers sideways so they never stack on one spot.
			var side := 1.0 if int(at / 97.0) % 2 == 0 else -1.0
			var fan := Vector3(side * (1.6 + fposmod(at * 0.0031, 1.0) * 1.2), 0.0, 0.0).rotated(Vector3.UP, camera_yaw)
			battle_fx.number(p + fan, "-%d" % roundi(float(hit[1])), age / 900.0, Color("#ffe7a8"), float(hit[1]) >= timeline.max * 0.08)
		if age <= 320.0:
			battle_fx.spark(p, age / 320.0, Color("#ffb054"), 2.4, fposmod(at * 0.013, 1.0))
	for strike in timeline.strikes:
		var age := elapsed - float(strike[0])
		if age < -380.0 or age > 420.0:
			continue
		var target: Vector3 = members.get(strike[1], centre)
		battle_fx.slash(p, target, (age + 380.0) / 800.0, Color("#ff5a3c"), 4.4 if strike[2] == "antler_charge" else 3.8)
		if age >= 0.0:
			battle_fx.spark(target, age / 420.0, Color("#ff6a4a"), 2.0, fposmod(float(strike[0]) * 0.007, 1.0))
	var spec: Dictionary = encounter.get("spec", {})
	var title := "%s · %s" % [spec.get("name", encounter.get("species", "")), ["I", "II", "III"][clampi(int(encounter.get("level", 1)), 1, 3) - 1]]
	var height := 2.6 + 0.5 * clampi(int(encounter.get("level", 1)), 1, 3)
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
	cue.scale = Vector3.ONE * (1.1 + 2.2 * progress)
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

func route_for(path: Array) -> Dictionary:
	var points := PackedVector3Array()
	var distances := PackedFloat32Array()
	for entry in path:
		var next := point(entry)
		var total := 0.0
		if not points.is_empty():
			var previous := points[-1]
			total = distances[-1] + Vector2(next.x - previous.x, next.z - previous.z).length()
		points.append(next)
		distances.append(total)
	return {"source":path,"points":points,"distances":distances}

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
	return p

func battle_events(army: Dictionary) -> Dictionary:
	var by_member := {}
	var fallen := {}
	var entries: Array = army.get("events", [])
	if army.get("battle") is Dictionary:
		entries = army.battle.get("events", [])
	for event in entries:
		var e: Array = event if event is Array else [event.at, event.kind, event.unitId, event.index, event.get("hp")]
		var key := "%s:%d" % [e[2], int(e[3])]
		if not by_member.has(key):
			by_member[key] = []
		by_member[key].append(e)
	for unit in army.get("fallen", []):
		fallen["%s:%d" % [unit[0], int(unit[1])]] = true
	return {"members":by_member, "fallen":fallen}

func present_armies(state: Dictionary, server_ms: float) -> void:
	battle_fx.begin()
	var alive := {}
	var known := {}
	var rows: Array = state.world.armies if map_name == "world" else state.get("armies", [])
	army_markers.clear()
	var creation_budget := 6
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
		if cache.get("source", []) != path:
			cache.merge(route_for(path), true)
		if cache.get("bag", {}) != bag or not cache.has("slots"):
			cache.bag = bag
			cache.slots = Formations.field_slots(bag, data.englishRoster)
		var timeline: Variant = [army.get("events"), army.get("fallen"), army.get("battle")]
		if cache.get("timeline") != timeline:
			cache.timeline = timeline
			cache.events = battle_events(army) if fighting else {"members":{}, "fallen":{}}
		army_routes[id] = cache
		if cache.slots.is_empty():
			continue
		var start := float(army.get("returnStartsAt", server_ms) if returning else army.get("startsAt", server_ms))
		var end := float(army.get("returnsAt", server_ms) if returning else army.get("arrivesAt", server_ms))
		var travelling: bool = army.status == "outbound" or returning
		var duration := maxf(1.0, end - start)
		var fraction := (server_ms - start) / duration if travelling else 1.0
		var p := ground_point(along_route(cache, fraction))
		var before := along_route(cache, fraction - 250.0 / duration)
		var after := along_route(cache, fraction + 250.0 / duration)
		var direction := after - before
		if direction.length_squared() > 0.0001:
			cache.heading = atan2(direction.x, direction.z)
		var heading := float(cache.get("heading", 0.0))
		army_markers.append({"position":p + Vector3.UP * 2.6, "id":id, "kind":"army", "item":army})
		if not camera.is_position_in_frustum(p + Vector3.UP) or (map_name == "world" and camera_zoom > 132.0):
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
		if fighting:
			cache.member_at = {}
		var walking: bool = travelling and fraction >= 0.0 and fraction < 1.0
		# Authoritative ground speed of the formation (world units per second).
		var ground_speed := float(cache.distances[-1]) / (duration / 1000.0) if walking and cache.distances.size() > 1 else 0.0
		var elapsed := server_ms - float(army.get("battleAt", end))
		var spread := smoothstep(0.0, 700.0, elapsed) if fighting else 0.0
		if returning:
			spread = 1.0 - smoothstep(0.0, 700.0, server_ms - start)
		var events: Dictionary = cache.get("events", {"members":{}, "fallen":{}})
		var retained := {}
		for i in range(cache.slots.size()):
			var slot: Dictionary = cache.slots[i]
			var key := "%s:%d" % [slot.id, int(slot.index)]
			var node_name := "%s_%d" % [slot.id, int(slot.index)]
			var unit := actor.get_node_or_null(NodePath(node_name)) as Node3D
			if unit == null:
				if creation_budget <= 0:
					continue
				unit = add_warrior(actor, data.unitModels[slot.id].field, Transform3D.IDENTITY)
				unit.name = node_name
				creation_budget -= 1
			retained[node_name] = true
			var side := float(slot.side) * (1.0 + spread * 0.22)
			var rear := float(slot.rear) + spread * (4.0 if slot.ranged else 2.5)
			var offset := Vector3(side * cos(heading) - rear * sin(heading), 0.0, -side * sin(heading) - rear * cos(heading))
			if spread > 0.0:
				var angle: float = TAU * i / cache.slots.size()
				offset = offset.lerp(Vector3(cos(angle), 0.0, sin(angle)) * (7.5 if slot.mounted else 4.8), spread)
			var place := ground_point(p + offset)
			if fighting:
				cache.member_at[key] = place
			var facing := atan2(-offset.x, -offset.z) if fighting else heading
			unit.transform = model_transform(place.x - p.x, place.y - p.y, place.z - p.z, facing, FIELD_UNIT_SCALE)
			var clip := "walk" if walking else "idle"
			var tempo := 1.0
			if walking:
				var gait := gait_for(slot.id, ground_speed)
				clip = gait[0]
				tempo = gait[1]
			var phase := -1.0
			var strike := -INF
			var hit := -INF
			var down: bool = fighting and events.fallen.has(key)
			if fighting:
				for event in events.members.get(key, []):
					var at := float(event[0])
					if event[1] == "soldier_attack":
						if elapsed >= at - 490.0 and elapsed <= at + 510.0:
							strike = at
					elif at <= elapsed:
						hit = at
						down = down or event[4] == 0
				if down:
					clip = "death"
					phase = 1.0 if hit == -INF else (elapsed - hit) / 700.0
				elif elapsed - hit < 400.0:
					clip = "hit"
					phase = (elapsed - hit) / 400.0
				elif strike > -INF:
					clip = "attack"
					phase = (elapsed - strike + 490.0) / 1000.0
					if not slot.ranged:
						# Weapon sweep timed to the swing's contact frame (event time).
						battle_fx.slash(place, p, (elapsed - strike + 260.0) / 420.0, Color("#ffd27a"), 3.2)
				elif army.get("worldKind") == "pvp":
					clip = "attack"
					phase = fposmod(elapsed + i * 125.0, 1000.0) / 1000.0
			if phase >= 0.0 or unit.get_meta("clip", "") != clip:
				play_animation(unit, clip, data.unitModels[slot.id].drill if clip == "attack" else "", phase,
					fposmod(float(i) * 0.381966, 1.0))
				unit.set_meta("clip", clip)
			if unit.get_meta("tempo", 1.0) != tempo:
				unit.set_meta("tempo", tempo)
				for player: AnimationPlayer in unit.get_meta("animation_players", []):
					player.speed_scale = tempo
			var shot := unit.get_node_or_null("Arrow") as MeshInstance3D
			var firing: bool = slot.ranged and clip == "attack" and strike > -INF and elapsed >= strike - 260.0 and elapsed <= strike
			if firing:
				draw_arrow(unit, shot, p, (elapsed - strike + 260.0) / 260.0)
			elif shot != null:
				shot.hide()
		for unit in actor.get_children():
			if not retained.has(String(unit.name)):
				unit.free()
	retain_hidden_actors(actors, known, alive, MAX_HIDDEN_ARMIES)
	for id in army_routes.keys():
		if not rows.any(func(army): return army.id == id and army.status != "returned"):
			army_routes.erase(id)

static func gait_for(unit_id: String, ground_speed: float) -> Array:
	# Picks walk or run and the playback tempo at which planted feet travel at the
	# formation's ground speed, so soldiers do not skate along the route. The gait
	# changes at the geometric mean of both strides, which keeps tempo distortion
	# symmetric; only speeds outside the supported range are clamped.
	var stance: Dictionary = GaitTable.STANCE_SPEED.get(unit_id, {})
	var walk := float(stance.get("walk", 0.0)) * FIELD_UNIT_SCALE
	var run := float(stance.get("run", 0.0)) * FIELD_UNIT_SCALE
	if walk <= 0.0 or ground_speed <= 0.0:
		return ["walk", 1.0]
	if run <= 0.0 or ground_speed < sqrt(walk * run):
		return ["walk", clampf(ground_speed / walk, WALK_TEMPO.x, INF)]
	return ["run", clampf(ground_speed / run, 0.0, RUN_TEMPO.y)]

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

func draw_arrow(unit: Node3D, shaft: MeshInstance3D, destination: Vector3, phase: float) -> void:
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
	var a := unit.global_position + Vector3.UP * 1.35
	var b := destination + Vector3.UP * 1.45
	var tail_phase := maxf(0.0, phase - 0.13)
	var tip := a.lerp(b, phase) + Vector3.UP * sin(PI * phase) * 0.6
	var tail := a.lerp(b, tail_phase) + Vector3.UP * sin(PI * tail_phase) * 0.6
	var direction := tip - tail
	if direction.length_squared() <= 0.00001:
		shaft.hide()
		return
	var rotation := Basis(Quaternion(Vector3.UP, direction.normalized()))
	shaft.global_transform = Transform3D(rotation.scaled(Vector3.ONE), (tip + tail) * 0.5)
	shaft.scale.y = direction.length() / unit.scale.y
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
		var fallback: String = {"INF-01":"ENG-09", "RNG-01":"ENG-03", "CAV-01":"ENG-05"}[group]
		var unit_id: String = order.get("unitId", fallback) if active else fallback
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

# valid: green plate (buildable); otherwise amber (forest, must be cleared) or red (no plot).
func move_placement(at: Vector3, plate_state: String, lifted: bool) -> void:
	if not is_instance_valid(placement):
		return
	var color := Color(0.4, 0.95, 0.5) if plate_state == "ready" else (Color(1.0, 0.7, 0.28) if plate_state == "forest" else Color(1.0, 0.36, 0.3))
	(placement_plate.material_override as StandardMaterial3D).albedo_color = Color(color, 0.34)
	placement_overlay.albedo_color = Color(color.lightened(0.2), 0.2)
	placement_lift = 1.2 if lifted else 0.0
	placement_plate.position = at + Vector3.UP * 0.18
	placement_ghost.position = at + Vector3.UP * placement_lift

func placement_position() -> Vector3:
	return placement_plate.position - Vector3.UP * 0.18 if is_instance_valid(placement_plate) else Vector3.ZERO

func clear_placement() -> void:
	if is_instance_valid(placement):
		placement.queue_free()
	placement = null
	placement_ghost = null
	placement_plate = null
	placement_rings.clear()
