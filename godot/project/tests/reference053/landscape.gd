extends Node3D

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
const Formations = preload("res://src/formations.gd")
var data: Dictionary
var map_name := "city"
var world_heights := PackedFloat32Array()
var actors := Node3D.new()
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
	for path in ground_paths:
		var ground := scene_resource(path).instantiate()
		add_child(ground)
		for mesh in ground.find_children("*", "MeshInstance3D", true, false):
			mesh.material_override = ground_material
			var bounds: AABB = mesh.transform * mesh.get_aabb()
			terrain_bounds = bounds if not terrain_bounds.has_volume() else terrain_bounds.merge(bounds)
	add_child(buildings)
	add_child(actors)
	add_child(creatures)
	add_child(training)
	add_child(scenery)
	add_child(city_ground_detail)
	add_child(parade)
	add_child(workers)
	add_child(effects)
	add_child(camera)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL if is_city else Camera3D.PROJECTION_PERSPECTIVE
	camera.fov = 43.0
	camera.near = 0.5
	camera.far = 700.0 if is_city else 1100.0
	await get_tree().process_frame
	if is_city:
		zoom = 70.0
		target = Vector3(5, 0, -4)
		build_water()
	else:
		fit_world()
		await build_world_scenery()
		await get_tree().process_frame
		build_towns()
		build_world_water()
		await get_tree().process_frame
		build_world_roads()
	if not saved_view.is_empty():
		target = saved_view.target
		zoom = saved_view.zoom
		world_yaw = saved_view.get("yaw", 0.0)
		resource_layer = saved_view.get("resources", true)
		detail_layer = saved_view.get("details", true)
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
	mesh.material_override = water_material(Color("#347e8b"))
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
	for part in instance.find_children("*", "MeshInstance3D", true, false):
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
	var clusters: Array[Dictionary] = []
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
		clusters.append({"center":bounds.get_center(), "extent":bounds.size * 0.5,
			"origin":origins / placements.size(), "transforms":buffer})
	multi.custom_aabb = all_bounds
	multi.visible_instance_count = 0
	var node := MultiMeshInstance3D.new()
	node.multimesh = multi
	node.material_override = appearance
	if not casts_shadow:
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)
	render_batches.append({"node":node, "clusters":clusters, "mask":PackedByteArray(),
		"total":count, "visible":0, "capacity":0, "layer":layer})

func build_forest(city: Dictionary, exclusions: Array) -> void:
	if is_instance_valid(trees.get("node")):
		trees.node.free()
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
	for tree in data.woods:
		if tree.village and not city.get("kingdom") is Dictionary:
			continue
		var p := array_point(tree.p)
		if inside_exclusions(p.x, p.z, exclusions) or on_street(Vector2(p.x, p.z), 1.5):
			continue
		selectable_trees.append(tree)
		if felled.has(tree.id):
			if not details.has("tree_stump"):
				details.tree_stump = []
			details.tree_stump.append(model_transform(p.x, p.y, p.z, 0.0, 0.7))
			continue
		var cell := Vector2i(floori(p.x / 4.0), floori(p.z / 4.0))
		if not standing_tree_cells.has(cell):
			standing_tree_cells[cell] = []
		standing_tree_cells[cell].append(Vector2(p.x, p.z))
		var key := "tree" + str(int(tree.variant))
		var detail: int = {"":0, "mid":1, "far":2}.get(tree.lod, 2)
		key += str(detail)
		if not batches.has(key):
			batches[key] = {"model":"tree" + str(int(tree.variant)), "best":detail, "placements":[]}
		batches[key].placements.append(model_transform(p.x,p.y,p.z,float(tree.angle),float(tree.scale)))
	for key in batches:
		var batch: Dictionary = batches[key]
		var cells := group_placements(batch.placements, CITY_TREE_CELL_SIZE)
		for detail in range(batch.best, 3):
			var model: String = batch.model + ["", "mid", "far"][detail]
			batch_model(group, data.models[model].path, batch.placements, null,
				{"city":true, "far":false, "detail":false, "resource":false,
					"tree_lod":detail, "tree_best":batch.best}, cells)
	for prop in data.cityUnderstory:
		if inside_exclusions(prop.x, prop.z, exclusions):
			continue
		if not details.has(prop.id):
			details[prop.id] = []
		details[prop.id].append(model_transform(prop.x, sample_city(prop.x, prop.z), prop.z, prop.angle, prop.scale))
	for key in details:
		batch_model(city_ground_detail, data.cityDetails[key], details[key], scenery_material,
			{"city":true,"far":true,"detail":true,"resource":false})
	build_meadow(exclusions)

func build_meadow(exclusions: Array) -> void:
	for kind in data.groundCover:
		var transforms: Array = []
		for item in data.groundCover[kind]:
			if inside_exclusions(item.x, item.z, exclusions) or on_street(Vector2(item.x, item.z), 0.85):
				continue
			var y := sample_city(item.x, item.z)
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

func build_world_scenery() -> void:
	var batches := {}
	var distant_canopies := {}
	for item in data.environment:
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
	var slice_started := Time.get_ticks_msec()
	var loaded := 0
	for id in batches:
		var spec: Dictionary = data.environmentModels[id]
		var transforms: Array = batches[id]
		var cells := group_placements(transforms)
		var has_silhouette: bool = spec.canopy is Dictionary and float(spec.canopy.scale) < 0.65
		for far in [false, true]:
			batch_model(scenery, spec.far if far else spec.near, transforms, scenery_material,
				{"far":far, "tree":spec.tree, "detail":spec.detail, "resource":spec.resource, "canopy":has_silhouette}, cells)
		loaded += 1
		if loaded % 8 == 0 and Time.get_ticks_msec() - slice_started >= 25:
			await get_tree().process_frame
			slice_started = Time.get_ticks_msec()

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
		var selected: Array[Dictionary] = []
		for i in range(batch.clusters.size()):
			var cluster: Dictionary = batch.clusters[i]
			var center: Vector3 = cluster.center
			var extent: Vector3 = cluster.extent
			if city_tree_lod >= 0:
				var origin: Vector3 = cluster.origin
				var dx := origin.x - camera_target.x
				var dz := origin.z - camera_target.z
				var distance_squared := dx * dx + dz * dz
				var desired := 0 if distance_squared < city_near_squared else (1 if distance_squared < city_mid_squared else 2)
				if city_tree_lod != maxi(desired, layer.tree_best):
					continue
			if landscape and not (silhouette and not town):
				var near := near_zoom
				if near and (town or layer.tree):
					var origin: Vector3 = cluster.origin
					var x := origin.x - camera_target.x
					var z := origin.z - camera_target.z
					var radius := TOWN_DETAIL_RADIUS if town else 50.0
					near = x * x + z * z < radius * radius
				if near == bool(layer.far):
					continue
			var visible_cluster := true
			for plane in planes:
				var radius := plane.normal.abs().dot(extent)
				if plane.distance_to(center) > radius:
					visible_cluster = false
					break
			if visible_cluster:
				mask[i] = 1
				selected.append(cluster)
		node.visible = not selected.is_empty()
		if batch.mask == mask:
			continue
		batch.mask = mask
		var visible_transforms := PackedFloat32Array()
		for cluster in selected:
			visible_transforms.append_array(cluster.transforms)
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
		batch_silhouettes(group, data.distantModels[key], cells, transforms.size(),
			layer.merged({"far":true, "silhouette":true}, true))

func add_model(parent: Node3D, model_path: String, transform_value: Transform3D) -> Node3D:
	var instance := scene_resource(model_path).instantiate() as Node3D
	prepare_model_materials(instance)
	instance.transform = transform_value
	parent.add_child(instance)
	return instance

func prepare_model_materials(instance: Node3D) -> void:
	# Reuse original maps and geometry; preserve normal/ORM values and alpha settings.
	for part: MeshInstance3D in instance.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		for index in part.mesh.get_surface_count():
			var material := part.get_active_material(index)
			if material is BaseMaterial3D:
				material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC

func play_animation(model: Node3D, preferred: String, fallback := "", phase := -1.0) -> void:
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
		else:
			if animation.assigned_animation != selected:
				animation.play(selected)
			animation.pause()
			animation.seek(clampf(phase, 0.0, 0.999) * resource.length, true)

func present(state: Dictionary) -> void:
	if map_name == "city":
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
		for child in buildings.get_children():
			child.free()
		for child in workers.get_children():
			child.free()
		place_markers.clear()
		empty_plots.clear()
		var plots: Array = data.plots.duplicate() if kingdom is Dictionary else data.legacyPlots.duplicate()
		for id in progress.get("sites", []):
			if data.treePlots.has(id):
				plots.append(data.treePlots[id])
		var occupied := {}
		var exclusions: Array = []
		if district is Dictionary:
			exclusions.append(Rect2(district.x - 15.7, district.z - 12.7, 31.4, 25.4))
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
				exclusions.append(Rect2(x - 7.0, z - 7.0, 14.0, 14.0))
				var scale := float(asset.scale)*(1+0.055*(int(building.level)-1))
				add_model(buildings,asset.path,model_transform(x,y,z,0,scale))
				add_worker(id, Vector3(x,y,z))
				var levels: Dictionary = data.architecture.get(building.type, {})
				var upgrade: String = levels.get(str(int(building.level)), "")
				if not upgrade.is_empty():
					add_city_detail(buildings, upgrade, Vector3(x,y,z))
				place_markers.append({"position":Vector3(x,y+5,z),"id":building.id,"kind":"building","item":building})
				break
		for plot in plots:
			if (kingdom is Dictionary and plot.id in kingdom.get("clearedPlots", [])) or plot.id.begins_with("site-"):
				exclusions.append(Rect2(plot.x - 6.7, plot.z - 6.7, 13.4, 13.4))
			if order is Dictionary and order.get("kind", "") != "clear" and order.get("plotId", "") == plot.id:
				add_city_detail(buildings, data.scaffold, Vector3(plot.x, sample_city(plot.x, plot.z), plot.z))
			if not occupied.has(plot.id):
				var x := float(plot.x)
				var z := float(plot.z)
				empty_plots.append({"position":Vector3(x, sample_city(x, z), z), "kind":"plot", "item":plot})
		for grove in data.clearings:
			if grove.id in progress.get("cleared", []):
				var half := float(grove.size) * 0.5
				exclusions.append(Rect2(grove.x - half, grove.z - half, grove.size, grove.size))
		build_city_roads(city, plots)
		build_forest(city, exclusions)
		geometries.erase("parade_signature")
		sync_parade(army, district)
		update_visible_batches()
	else:
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

func add_worker(building: String, base: Vector3) -> void:
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
			p.y = sample_city(p.x, p.z) + (sin(time * 2.0) * 0.025 if kind == "farm" else 0.0)
		actor.position = p

func add_city_detail(parent: Node3D, path: String, p: Vector3) -> void:
	var detail := add_model(parent, path, Transform3D(Basis.IDENTITY, p))
	for mesh in detail.find_children("*", "MeshInstance3D", true, false):
		mesh.material_override = scenery_material

func sync_parade(army: Dictionary, district: Variant) -> void:
	var key := JSON.stringify([army, district])
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
			var actor := add_model(parade, data.unitModels[slot.id].field, Transform3D(Basis.IDENTITY, slot.position))
			actor.name = "rank" + str(i)
			play_animation(actor, "Idle")
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
		if encounter.status == "defeated" or int(encounter.get("hp", 1)) <= 0:
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
			if attack > -INF:
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
	for cue in effects.get_children():
		if not cues.has(String(cue.name)):
			cue.queue_free()

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
		var walking: bool = travelling and fraction >= 0.0 and fraction < 1.0
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
				unit = add_model(actor, data.unitModels[slot.id].field, Transform3D.IDENTITY)
				unit.name = node_name
				creation_budget -= 1
			retained[node_name] = true
			var side := float(slot.side) * (1.0 + spread * 0.22)
			var rear := float(slot.rear) + spread * (4.0 if slot.ranged else 2.5)
			var offset := Vector3(side * cos(heading) - rear * sin(heading), 0.0, -side * sin(heading) - rear * cos(heading))
			if map_name == "city" and spread > 0.0:
				var angle: float = TAU * i / cache.slots.size()
				offset = offset.lerp(Vector3(cos(angle), 0.0, sin(angle)) * (7.5 if slot.mounted else 4.8), spread)
			var place := ground_point(p + offset)
			var facing := atan2(-offset.x, -offset.z) if fighting else heading
			unit.transform = model_transform(place.x - p.x, place.y - p.y, place.z - p.z, facing, 1.15)
			var clip := "walk" if walking else "idle"
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
				elif army.get("worldKind") == "pvp":
					clip = "attack"
					phase = fposmod(elapsed + i * 125.0, 1000.0) / 1000.0
			if phase >= 0.0 or unit.get_meta("clip", "") != clip:
				play_animation(unit, clip, data.unitModels[slot.id].drill if clip == "attack" else "", phase)
				unit.set_meta("clip", clip)
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
			actor = add_model(training, visual.preview, model_transform(p.x, p.y, p.z, PI, 1.0))
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
