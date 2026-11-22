extends Control
## Building dioramas of the construction windows (premium UI stage 3, ui_premium/STAGE3.md).
##
## One look for every building picture: the level scene the city draws, standing on a turf
## diorama tile (grass top, a cut of dark soil and field stones round the rim, a soft shadow
## under it), lit by a warm key from the upper left with soft shadows, a cool fill and a warm
## rim, seen from the front right at a three-quarter view through an orthographic lens.
##
## - The card art of the strip (assets/ui/buildings/v6/<type>.webp) is baked from level I with
##   exactly this rig (tools/bake_building_art.gd, godot/art/ui/buildings/finish_art.py).
## - The upgrade window shows the building live: «Сейчас» (the current level) and «После» (the
##   next one) on two tiles side by side in one SubViewport, turning gently together. The parts
##   the next level adds glow gold (building_new_parts.gdshader reads the UV2 build data of the
##   level scenes), so even a small change reads at once.
##
## Cost rules (as the recruitment stage, src/unit_stage.gd):
## - The window opens with only 2D: the wash, the plates and the baked empty tile where the
##   live view will be. The 3D world is built after that first frame; the level scenes load on
##   worker threads (request() is called as the window opens; the current level is usually
##   already in memory because the city shows it).
## - The SubViewport and everything in it are children of this node: nothing 3D outlives the
##   window. It renders at device resolution with 4x MSAA.

const UiKit = preload("res://src/ui_kit.gd")
const NEW_PARTS := preload("res://src/building_new_parts.gdshader")

## The camera looks from the front right, about 31 degrees above the ground.
const VIEW := Vector3(0.82, 0.74, 1.0)
## Diorama tile: half the side (metres), the corner rounding (superellipse power) and depth.
const TILE_HALF := 7.6
const TILE_POWER := 4.6
const TILE_DEPTH := 1.55
## Orthographic framing: the tile fills this share of a slot's width; the tallest building
## the view must hold (metres above the tile).
const TILE_SHARE := 0.9
const ART_DIR := "res://assets/ui/buildings/v6/"
const GRASS := "res://assets/city/premium/surfaces07/grass20-albedo.webp"
const SOIL := "res://assets/city/premium/surfaces07/soil-albedo.webp"
const STONE := "res://assets/city/premium/surfaces07/stone-albedo.jpg"

static var scenes := {}
static var requested := {}
static var arts := {}
static var runtime := {}
static var materials := {}
static var environment: Environment
static var glow_material: ShaderMaterial

# ------------------------------------------------------------------ data

## Runtime (city) type of a V6 building type: B01 -> ECO-05, read from the level table
## (the V6 entries carry their concept id).
static func runtime_type(data: Dictionary, type: String) -> String:
	if runtime.is_empty():
		for key: String in data.get("levelModels", {}):
			for level: String in data.levelModels[key]:
				var entry: Variant = data.levelModels[key][level]
				if entry is Dictionary and entry.has("id"):
					runtime[str(entry.id)] = key
					break
	return str(runtime.get(type, ""))

## [scene path, scale] the city draws for a runtime type at a level. The same rule as
## Landscape.level_visual (a level scene, else the shared model grown by level); the window
## asks the city's own Landscape when it is there, so the two cannot disagree.
static func level_visual(data: Dictionary, type: String, level: int) -> Array:
	if level < 1 or level > 11:
		return []
	var entry: Variant = data.get("levelModels", {}).get(type, {}).get(str(level))
	if entry is Dictionary:
		return [str(entry.path), float(entry.get("scale", 1.0))]
	var id: String = str(data.get("starterHall", "")) if type == "ECO-05" and level == 1 else str(data.get("types", {}).get(type, ""))
	if id.is_empty() or not data.get("models", {}).has(id):
		return []
	return [str(data.models[id].path), float(data.models[id].scale) * (1 + 0.055 * (level - 1))]

## Baked card art of a V6 type (level I on its tile); null when it was not baked.
static func card_art(type: String) -> Texture2D:
	if arts.has(type):
		return arts[type]
	var path := ART_DIR + type + ".webp"
	var texture: Texture2D = null
	if ResourceLoader.exists(path):
		if ResourceLoader.load_threaded_get_status(path) != ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
			texture = ResourceLoader.load_threaded_get(path) as Texture2D
		if texture == null:
			texture = load(path) as Texture2D
	arts[type] = texture
	return texture

## Decodes the card art on worker threads (after launch).
static func warm_art(types: Array) -> void:
	for type: String in types + ["tile"]:
		var path := ART_DIR + type + ".webp"
		if not arts.has(type) and ResourceLoader.exists(path):
			ResourceLoader.load_threaded_request(path, "Texture2D")
	for path: String in [GRASS, SOIL, STONE]:
		if not ResourceLoader.has_cached(path) and not requested.has(path):
			requested[path] = ResourceLoader.load_threaded_request(path, "Texture2D") == OK

## Starts loading a level scene on a worker thread (harmless when loaded or loading).
static func request(path: String) -> void:
	if path.is_empty() or scenes.has(path) or requested.has(path) or not ResourceLoader.exists(path):
		return
	if ResourceLoader.has_cached(path):
		scenes[path] = load(path)
		return
	if ResourceLoader.load_threaded_request(path, "PackedScene", true) == OK:
		requested[path] = true

## The loaded scene, null while a worker still reads it (or when there is no such file).
static func take(path: String) -> PackedScene:
	if scenes.has(path):
		return scenes[path]
	if not requested.has(path):
		request(path)
		if scenes.has(path):
			return scenes[path]
		if not requested.has(path):
			return null
	if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		return null
	requested.erase(path)
	var scene := ResourceLoader.load_threaded_get(path) as PackedScene
	if scene != null:
		scenes[path] = scene
	return scene

static func surface(path: String) -> Texture2D:
	if requested.get(path, false) and ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_LOADED:
		requested.erase(path)
		return ResourceLoader.load_threaded_get(path) as Texture2D
	return load(path) as Texture2D

# ------------------------------------------------------------------ the diorama

static func tile_materials() -> Dictionary:
	if not materials.is_empty():
		return materials
	var grass := StandardMaterial3D.new()
	grass.albedo_texture = surface(GRASS)
	grass.albedo_color = Color("#ffffff")
	grass.vertex_color_use_as_albedo = true
	grass.uv1_triplanar = true
	grass.uv1_scale = Vector3.ONE * 0.62
	grass.roughness = 0.97
	grass.metallic_specular = 0.12
	grass.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var soil := StandardMaterial3D.new()
	soil.albedo_texture = surface(SOIL)
	soil.albedo_color = Color("#ffffff")
	soil.vertex_color_use_as_albedo = true
	soil.uv1_triplanar = true
	soil.uv1_scale = Vector3.ONE * 0.22
	soil.roughness = 1.0
	soil.metallic_specular = 0.06
	soil.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var stone := StandardMaterial3D.new()
	stone.albedo_texture = surface(STONE)
	stone.albedo_color = Color("#ffffff")
	stone.vertex_color_use_as_albedo = true
	stone.uv1_triplanar = true
	stone.uv1_scale = Vector3.ONE * 0.45
	stone.roughness = 0.9
	stone.metallic_specular = 0.18
	stone.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var shade := StandardMaterial3D.new()
	shade.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	shade.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	shade.albedo_texture = UiKit.ground_shadow()
	shade.albedo_color = Color(1, 1, 1, 0.9)
	var leaf := StandardMaterial3D.new()
	leaf.albedo_texture = grass.albedo_texture
	leaf.albedo_color = Color("#ffffff")
	leaf.vertex_color_use_as_albedo = true
	leaf.uv1_triplanar = true
	leaf.uv1_scale = Vector3.ONE * 0.9
	leaf.roughness = 0.9
	leaf.metallic_specular = 0.2
	leaf.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	materials = {"grass": grass, "soil": soil, "stone": stone, "shade": shade, "leaf": leaf}
	return materials

## Smooth value noise in [0, 1] (seeded), for the hand-made wobble and the grass tones.
static func noise(x: float, z: float, seed: int) -> float:
	var ix := floori(x)
	var iz := floori(z)
	var fx := x - ix
	var fz := z - iz
	var a := float(hash(Vector3i(ix, iz, seed)) % 1000) / 999.0
	var b := float(hash(Vector3i(ix + 1, iz, seed)) % 1000) / 999.0
	var c := float(hash(Vector3i(ix, iz + 1, seed)) % 1000) / 999.0
	var d := float(hash(Vector3i(ix + 1, iz + 1, seed)) % 1000) / 999.0
	var u := fx * fx * (3.0 - 2.0 * fx)
	var v := fz * fz * (3.0 - 2.0 * fz)
	return lerpf(lerpf(a, b, u), lerpf(c, d, u), v)

## Noise round the rim, periodic in the angle (no seam where the ring closes).
static func ring_noise(angle: float, frequency: float, seed: int, lane := 0.0) -> float:
	return noise(cos(angle) * frequency + lane * 7.3, sin(angle) * frequency - lane * 3.1, seed)

## Outline of the tile at an angle: a rounded square (superellipse), wobbled a little.
static func outline(angle: float, seed: int) -> float:
	var c := absf(cos(angle))
	var s := absf(sin(angle))
	var r := TILE_HALF / pow(pow(c, TILE_POWER) + pow(s, TILE_POWER), 1.0 / TILE_POWER)
	return r * (1.0 + 0.022 * (ring_noise(angle, 1.6, seed) - 0.5) * 2.0)

## Turf diorama tile, top at y = 0: grass with tone variation and a rounded lip, a cut of
## dark soil with roots and lighter strata, field stones and a few bushes round the rim, and
## a soft shadow below.
static func make_tile(seed := 7) -> Node3D:
	var kit := tile_materials()
	var root := Node3D.new()
	root.name = "Diorama"
	var steps := 120
	# Top: rings from the centre to the lip (fractions of the outline, height).
	var rings := [[0.0, 0.0], [0.3, 0.0], [0.55, 0.0], [0.74, 0.0], [0.87, -0.015], [0.94, -0.05], [0.972, -0.11], [0.99, -0.19], [1.0, -0.28]]
	var top := SurfaceTool.new()
	top.begin(Mesh.PRIMITIVE_TRIANGLES)
	var grid: Array = []
	for j in rings.size():
		var row: Array = []
		for i in steps + 1:
			var angle := TAU * float(i % steps) / steps
			var reach: float = rings[j][0]
			var r := outline(angle, seed) * reach
			var p := Vector3(cos(angle) * r, float(rings[j][1]), sin(angle) * r)
			if j > 2 and j < 6:
				p.y += (noise(p.x * 0.35, p.z * 0.35, seed + 3) - 0.5) * 0.1
			# Grass tones over the city's grass texture: fresh and sun-dried patches, clover
			# shade, a darker lip.
			var patch := noise(p.x * 0.16 + 3.0, p.z * 0.16, seed + 11)
			var fine := noise(p.x * 0.8, p.z * 0.8, seed + 17)
			var tone := Color("#c2d6bc").lerp(Color("#e8dcae"), smoothstep(0.55, 0.9, patch) * 0.8)
			tone = tone.lerp(Color("#93b88e"), smoothstep(0.38, 0.08, patch) * 0.7)
			tone = tone * (0.9 + 0.18 * fine)
			if reach > 0.86:
				tone = tone.darkened(0.16 * smoothstep(0.86, 1.0, reach))
			tone.a = 1.0
			row.append([p, tone])
		grid.append(row)
	for j in rings.size() - 1:
		for i in steps:
			var quad := [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
			for index in [0, 2, 1, 0, 3, 2]:
				top.set_color(quad[index][1])
				top.add_vertex(quad[index][0])
	top.generate_normals()
	var turf := MeshInstance3D.new()
	turf.name = "Turf"
	turf.mesh = top.commit()
	turf.material_override = kit.grass
	root.add_child(turf)
	# Soil cut: from the lip down, drawn in toward the bottom, an uneven lower edge, darker
	# strata and the turf's root mat just under the grass.
	var side := SurfaceTool.new()
	side.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cuts := [[1.0, -0.28, Color("#4a3624")], [0.996, -0.5, Color("#5d4430")], [0.99, -0.78, Color("#8a6a4a")],
		[0.982, -1.05, Color("#6f5338")], [0.97, -1.3, Color("#7d6043")], [0.94, -TILE_DEPTH, Color("#3a2a1c")]]
	var wall: Array = []
	for j in cuts.size():
		var row: Array = []
		for i in steps + 1:
			var angle := TAU * float(i % steps) / steps
			var r: float = outline(angle, seed) * float(cuts[j][0])
			var y: float = float(cuts[j][1])
			if j == cuts.size() - 1:
				y -= ring_noise(angle, 4.0, seed + 5) * 0.55
				r -= ring_noise(angle, 3.0, seed + 6) * 0.35
			elif j > 0:
				r += (ring_noise(angle, 7.0, seed + 7, float(j)) - 0.5) * 0.18
				y += (ring_noise(angle, 5.0, seed + 8, float(j)) - 0.5) * 0.12
			var shade: Color = cuts[j][2]
			shade = shade * (0.84 + 0.3 * ring_noise(angle, 11.0, seed + 9, float(j)))
			shade.a = 1.0
			row.append([Vector3(cos(angle) * r, y, sin(angle) * r), shade])
		wall.append(row)
	for j in cuts.size() - 1:
		for i in steps:
			var quad := [wall[j][i], wall[j][i + 1], wall[j + 1][i + 1], wall[j + 1][i]]
			for index in [0, 2, 1, 0, 3, 2]:
				side.set_color(quad[index][1])
				side.add_vertex(quad[index][0])
	side.generate_normals()
	var soil := MeshInstance3D.new()
	soil.name = "Soil"
	soil.mesh = side.commit()
	soil.material_override = kit.soil
	root.add_child(soil)
	# Field stones half sunk at the lip and in the soil cut.
	var stones := SurfaceTool.new()
	stones.begin(Mesh.PRIMITIVE_TRIANGLES)
	var count := 9
	for k in count:
		var angle := TAU * (float(k) + noise(float(k), 0.3, seed + 21) * 0.6) / count
		var low := k % 3 == 0
		var r := outline(angle, seed) * (1.0 if low else 0.965)
		var size := 0.26 + 0.3 * noise(float(k), 1.7, seed + 23)
		var centre := Vector3(cos(angle) * r, (-0.85 if low else -0.16) + size * 0.15, sin(angle) * r)
		add_stone(stones, centre, Vector3(size * 1.3, size * 0.7, size), seed + k * 13)
	stones.generate_normals()
	var rocks := MeshInstance3D.new()
	rocks.name = "Stones"
	rocks.mesh = stones.commit()
	rocks.material_override = kit.stone
	root.add_child(rocks)
	# A few low bushes on the back corners (behind the building, never in front of it).
	var bushes := SurfaceTool.new()
	bushes.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in 3:
		var angle := -PI * 0.75 + (float(k) - 1.0) * 0.42 + (noise(float(k), 4.1, seed) - 0.5) * 0.2
		var r := outline(angle, seed) * 0.9
		var base := Vector3(cos(angle) * r, 0.0, sin(angle) * r)
		for leaf in 4:
			var spread := Vector3(noise(float(leaf), float(k), seed + 31) - 0.5, 0.0, noise(float(k), float(leaf), seed + 37) - 0.5) * 1.1
			var size := 0.42 + 0.3 * noise(float(leaf), float(k) + 9.0, seed + 41)
			add_stone(bushes, base + spread + Vector3(0, size * 0.55, 0), Vector3(size, size * 0.9, size), seed + leaf * 7 + k, Color("#7f9a4e"), Color("#4f6b31"))
	bushes.generate_normals()
	var green := MeshInstance3D.new()
	green.name = "Bushes"
	green.mesh = bushes.commit()
	green.material_override = kit.leaf
	root.add_child(green)
	# Soft shadow of the tile on whatever is behind it.
	var shadow := MeshInstance3D.new()
	shadow.name = "TileShadow"
	var plane := PlaneMesh.new()
	plane.size = Vector2(TILE_HALF * 2.9, TILE_HALF * 2.9)
	shadow.mesh = plane
	shadow.material_override = kit.shade
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	shadow.position = Vector3(-0.8, -TILE_DEPTH - 0.7, -0.8)
	root.add_child(shadow)
	for part: MeshInstance3D in [turf, soil, rocks, green]:
		part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return root

## A lumpy field stone (a squashed, dented sphere) into a SurfaceTool; with `lit` and `moss`
## colours it is a bush (lighter on top).
static func add_stone(tool: SurfaceTool, centre: Vector3, radius: Vector3, seed: int, lit := Color(0, 0, 0, 0), moss := Color("#7c8a55")) -> void:
	var rows := 6
	var cols := 10
	var points: Array = []
	for j in rows + 1:
		var row: Array = []
		var phi := PI * float(j) / rows
		for i in cols + 1:
			var theta := TAU * float(i % cols) / cols
			var dent := 0.8 + 0.34 * noise(cos(theta) * 1.6 + float(j) * 0.9, sin(theta) * 1.6, seed)
			var dir := Vector3(sin(phi) * cos(theta), cos(phi), sin(phi) * sin(theta))
			row.append(centre + dir * radius * dent)
		points.append(row)
	var bush := lit.a > 0.0
	var tone := Color(0.78, 0.75, 0.7).lerp(Color(0.62, 0.58, 0.5), noise(float(seed), 0.0, 3))
	for j in rows:
		for i in cols:
			var quad := [points[j][i], points[j][i + 1], points[j + 1][i + 1], points[j + 1][i]]
			for index in [0, 2, 1, 0, 3, 2]:
				if bush:
					tool.set_color(lit.lerp(moss, float(j) / rows))
				else:
					# Moss on the upper half of the stone.
					tool.set_color(tone.lerp(moss, 0.35) if j < 2 else tone)
				tool.add_vertex(quad[index])

## Warm key from the upper left of the view with soft shadows, a cool fill, a warm rim and a
## cool kicker; a filmic tonemap and sky reflections (the recruitment stage's rig, aimed for
## a building seen from above).
static func light_rig(parent: Node3D, shadows := true) -> void:
	var basis := axes()
	var key := DirectionalLight3D.new()
	key.name = "Key"
	# From the upper left of the view and a little in front.
	var from: Vector3 = (-basis[0] * 0.9 + Vector3.UP * 1.35 + basis[2] * 0.55).normalized()
	key.basis = Basis.looking_at(-from, Vector3.UP)
	key.light_color = Color("#ffd9a8")
	key.light_energy = 2.15
	key.shadow_enabled = shadows
	key.shadow_blur = 1.6
	key.shadow_bias = 0.04
	key.shadow_normal_bias = 1.2
	key.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	key.directional_shadow_max_distance = 120.0
	parent.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.name = "Fill"
	var fill_from: Vector3 = (basis[0] * 1.0 + Vector3.UP * 0.35 + basis[2] * 0.6).normalized()
	fill.basis = Basis.looking_at(-fill_from, Vector3.UP)
	fill.light_color = Color("#a9bfdc")
	fill.light_energy = 0.5
	fill.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	parent.add_child(fill)
	var rim := DirectionalLight3D.new()
	rim.name = "Rim"
	var rim_from: Vector3 = (basis[0] * 0.4 + Vector3.UP * 0.6 - basis[2] * 1.0).normalized()
	rim.basis = Basis.looking_at(-rim_from, Vector3.UP)
	rim.light_color = Color("#ffe2b8")
	rim.light_energy = 1.1
	rim.light_specular = 0.2
	rim.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	parent.add_child(rim)
	var world := WorldEnvironment.new()
	world.environment = stage_environment()
	parent.add_child(world)

static func stage_environment() -> Environment:
	if environment == null:
		environment = Environment.new()
		environment.background_mode = Environment.BG_CLEAR_COLOR
		environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		environment.ambient_light_color = Color("#d8cfbf")
		environment.ambient_light_energy = 0.34
		environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		environment.tonemap_exposure = 1.0
		environment.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	return environment

## Camera axes of the view: right, up, toward the camera.
static func axes() -> Array:
	var direction := VIEW.normalized()
	var right := Vector3.UP.cross(direction).normalized()
	return [right, direction.cross(right).normalized(), direction]

## Screen extents (metres in the camera plane, from the tile centre) of a tile with a building
## up to `height` metres tall: {"right": [low, high], "up": [low, high]}.
static func extents(height: float) -> Dictionary:
	var basis := axes()
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for corner in 48:
		var angle := TAU * float(corner) / 48.0
		var r := outline(angle, 0) * 1.01
		for y: float in [height, -TILE_DEPTH - 0.3]:
			var p := Vector3(cos(angle) * r, y, sin(angle) * r)
			var at := Vector2(p.dot(basis[0] as Vector3), p.dot(basis[1] as Vector3))
			low = low.min(at)
			high = high.max(at)
	return {"right": [low.x, high.x], "up": [low.y, high.y]}

## Orthographic camera on a tile centre: the tile takes `share` of the view width, the lowest
## point of the soil sits at `bottom` (fraction of the view height from the top).
static func aim(camera: Camera3D, centre: Vector3, aspect: float, share: float, bottom: float, height := 9.0) -> float:
	var basis := axes()
	var ext := extents(height)
	var wide: float = float(ext.right[1]) - float(ext.right[0])
	var view_width := wide / share
	var view_height := view_width / maxf(0.1, aspect)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.keep_aspect = Camera3D.KEEP_HEIGHT
	camera.size = view_height
	camera.near = 0.5
	camera.far = 400.0
	var down := float(ext.up[0])
	# The view centre in the camera plane, so the soil bottom lands at `bottom`.
	var up: Vector3 = basis[1]
	var toward: Vector3 = basis[2]
	var target: Vector3 = centre + up * (down + (bottom - 0.5) * view_height)
	camera.position = target + toward * 120.0
	camera.look_at(target, Vector3.UP)
	return view_height

## The gold overlay of new parts (one material for every «После» view).
static func new_parts_material() -> ShaderMaterial:
	if glow_material == null:
		glow_material = ShaderMaterial.new()
		glow_material.shader = NEW_PARTS
	return glow_material

## Puts a level scene on a tile: the city's scale, the texture filter the city uses.
static func place_building(parent: Node3D, scene: PackedScene, scale: float, glow_new := false) -> Node3D:
	var model := scene.instantiate() as Node3D
	model.scale = Vector3.ONE * scale
	parent.add_child(model)
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		for index in part.mesh.get_surface_count():
			var material := part.get_active_material(index)
			if material is BaseMaterial3D:
				material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		if glow_new and part.mesh is ArrayMesh and (part.mesh.surface_get_format(0) & Mesh.ARRAY_FORMAT_TEX_UV2) != 0:
			part.material_overlay = new_parts_material()
	return model

## Height of a level scene above its base (metres, at the city's scale), from its bounds.
static func model_height(model: Node3D) -> float:
	var top := 1.0
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if part.mesh != null:
			top = maxf(top, (part.global_transform * part.get_aabb()).end.y)
	return top
