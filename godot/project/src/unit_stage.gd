extends Control
## Recruitment hero stage (premium UI, ui_premium/STAGE2.md): the live 3D unit on a carved
## oak plinth over a mossy stone, in a painterly ink-wash splash tinted by the unit's tier
## (StageBackdrop, drawn under the rail and the stage), with a carved solar medallion, warm
## light falling on the figure, drifting embers and a name plate. Drag to turn the plinth.
##
## Cost rules:
## - The window opens with only the 2D layers and the baked portrait of the unit (its first
##   frame costs no 3D work). The 3D world is built after that frame, the model comes from a
##   worker thread (request() is called when the barracks ring or inspector opens), and the
##   live view fades in over the portrait, which is placed where the model will stand.
## - The SubViewport lives only while the window is open: it is a child of this node, which
##   the window frees on close. It renders at device resolution (canvas size x content scale)
##   with 4x MSAA, so the unit stays as crisp as the rest of the UI on the phone.
## The same camera, framing rule and three-point light bake the card portraits
## (tools/bake_unit_portraits.gd), which also measures each unit's posed silhouette, weapons
## included (assets/ui/units/framing.json): skinned meshes only report their rest pose.

const UiKit = preload("res://src/ui_kit.gd")
const WarriorVisual = preload("res://src/warrior_visual.gd")

## One 3/4 view for the whole roster: from the front right, a little above the chest.
const VIEW := Vector3(0.62, 0.2, 1.0)
const FOV := 24.0
## Stage framing in fractions of the stage height (0 top): the whole figure, lance tip
## included, between TOP and FEET; the plinth below the feet; the name plate on its front.
const TOP := 0.035
const FEET := 0.82
const WIDTH_SHARE := 0.8
# The ram is long and low: a little narrower, so it stands inside the wash.
const RAM_WIDTH_SHARE := 0.7
## Card portraits (no plinth): the same rule with the figure from top to bottom.
const PORTRAIT_TOP := 0.03
const PORTRAIT_FEET := 0.97
const PORTRAIT_WIDTH := 0.9
const PORTRAIT_SIZE := Vector2(288, 352)
## Kept for the bust framing of the portrait bake.
const FIGURE_SHARE := 0.66
const FIGURE_CENTRE := 0.43
const PORTRAIT_DIR := "res://assets/ui/units/"
const FRAMING_PATH := "res://assets/ui/units/framing.json"
const DAIS_STONE := "res://assets/city/premium/surfaces07/stone-albedo.jpg"

static var scenes := {}
static var recent: Array = []
static var requested := {}
static var portraits := {}
static var materials := {}
static var framing := {}
static var environment: Environment

signal info_pressed

var data: Dictionary
var unit_id := ""
var tier := 1
var title := ""
var tint := Color("#7d8288")
var backdrop: StageBackdrop
var placeholder: TextureRect
var view: TextureRect
var viewport: SubViewport
var turntable: Node3D
var holder: Node3D
var camera: Camera3D
var model: Node3D
var model_path := ""
var waiting_path := ""
var motes: CPUParticles2D
var plate: Control
var info: Button
var fade: Tween
var spin := 0.0
var spin_velocity := 0.0
var sway := 0.0
var dragging := false
var last_drag_msec := 0
var world_built := false
var built_usec := 0

# ------------------------------------------------------------------ shared helpers

## Path of the 3D model the stage shows for a unit (the detailed preview mesh of the
## troops; the ram has one scene for the field and the stage).
static func model_for(game_data: Dictionary, id: String) -> String:
	var visual: Dictionary = game_data.get("unitModels", {}).get(id, {})
	var path := str(visual.get("preview", visual.get("field", "")))
	return path if not path.is_empty() and ResourceLoader.exists(path) else ""

## Starts loading a model on a worker thread; harmless when it is loaded or loading.
static func request(path: String) -> void:
	if path.is_empty() or scenes.has(path) or requested.has(path):
		return
	if ResourceLoader.load_threaded_request(path, "PackedScene", true) == OK:
		requested[path] = true
	if not requested.has(DAIS_STONE) and not ResourceLoader.has_cached(DAIS_STONE):
		# The dais stone (shared with the city ground) decodes on a worker as well.
		requested[DAIS_STONE] = ResourceLoader.load_threaded_request(DAIS_STONE, "Texture2D") == OK

## The loaded scene, or null while the worker is still busy. While the window is open the
## last three stay cached (switching back and forth between units costs no reload).
static func take(path: String) -> PackedScene:
	if scenes.has(path):
		recent.erase(path)
		recent.push_front(path)
		return scenes[path]
	if not requested.has(path):
		request(path)
		return null
	if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		return null
	requested.erase(path)
	var scene := ResourceLoader.load_threaded_get(path) as PackedScene
	if scene != null:
		scenes[path] = scene
		recent.push_front(path)
		while recent.size() > 3:
			scenes.erase(recent.pop_back())
	return scene

## Baked portrait of a unit: full figure for cards, bust for queues and small slots.
static func portrait(id: String, bust := false) -> Texture2D:
	var key := id + ("-bust" if bust else "")
	if portraits.has(key):
		return portraits[key]
	var path := PORTRAIT_DIR + key + ".webp"
	var texture: Texture2D = null
	if ResourceLoader.has_cached(path) or ResourceLoader.exists(path):
		if ResourceLoader.load_threaded_get_status(path) != ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
			texture = ResourceLoader.load_threaded_get(path) as Texture2D
		if texture == null:
			texture = load(path) as Texture2D
	portraits[key] = texture
	return texture

## Made after launch, not in the first window's open: the backdrop's gradients, the framing
## of every unit and the stage environment; the plinth stone starts decoding on a worker.
static func warm_stage() -> void:
	UiKit.warm_glow()
	UiKit.warm_vignette_texture()
	UiKit.ground_shadow()
	extents("", {})
	stage_environment()
	if not requested.has(DAIS_STONE) and not ResourceLoader.has_cached(DAIS_STONE):
		requested[DAIS_STONE] = ResourceLoader.load_threaded_request(DAIS_STONE, "Texture2D") == OK

## Decodes every portrait on worker threads (called at launch).
static func warm_portraits(ids: Array) -> void:
	for id: String in ids:
		for suffix: String in ["", "-bust"]:
			var path := PORTRAIT_DIR + id + suffix + ".webp"
			if not portraits.has(id + suffix) and ResourceLoader.exists(path):
				ResourceLoader.load_threaded_request(path, "Texture2D")

## Figure metrics of a posed unit: feet, helmet top (from the head bone; long spears and
## lances do not count) and the box of the body. Skinned meshes report their rest-pose
## (T-pose) bounds, so a rigged unit is measured on its posed bones instead.
static func figure(unit: Node3D) -> Dictionary:
	var box := AABB()
	for part: MeshInstance3D in unit.find_children("*", "MeshInstance3D", true, false):
		var lower := part.name.to_lower()
		if "spear" in lower or "lance" in lower:
			continue
		var bounds := part.global_transform * part.get_aabb()
		box = bounds if not box.has_volume() else box.merge(bounds)
	var top := box.end.y
	for skeleton: Skeleton3D in unit.find_children("*", "Skeleton3D", true, false):
		var bones := AABB()
		var first := true
		for bone in skeleton.get_bone_count():
			var at := (skeleton.global_transform * skeleton.get_bone_global_pose(bone)).origin
			if first:
				bones = AABB(at, Vector3.ZERO)
				first = false
			else:
				bones = bones.expand(at)
		if not first:
			# Flesh, cloth and armour around the bones.
			var grown := bones.grow(0.16)
			box = AABB(Vector3(grown.position.x, box.position.y, grown.position.z), Vector3(grown.size.x, box.size.y, grown.size.z))
		var head := skeleton.find_bone("head")
		if head >= 0:
			top = minf(box.end.y, (skeleton.global_transform * skeleton.get_bone_global_pose(head)).origin.y + 0.24)
	return {"bottom": box.position.y, "top": top, "box": box}

## Width of a box seen from a camera direction (for wide figures: the knight, the ram).
static func projected_width(box: AABB, direction: Vector3) -> float:
	var right := Vector3.UP.cross(direction).normalized()
	var low := INF
	var high := -INF
	for i in 8:
		var along := box.get_endpoint(i).dot(right)
		low = minf(low, along)
		high = maxf(high, along)
	return high - low

## Warm key from the upper left (soft shadows), cool fill from the right, a bright warm
## rim from behind and a cooler kicker on the other side, sky reflections for the metal;
## transparent background. Shared with the portrait bake.
static func light_rig(parent: Node3D, shadows := true) -> void:
	var key := DirectionalLight3D.new()
	key.name = "Key"
	key.rotation_degrees = Vector3(-36, -26, 0)
	key.light_color = Color("#ffdcb0")
	key.light_energy = 1.85
	key.shadow_enabled = shadows
	key.shadow_blur = 1.5
	key.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	key.directional_shadow_max_distance = 18.0
	parent.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.name = "Fill"
	fill.rotation_degrees = Vector3(-8, 66, 0)
	fill.light_color = Color("#a8bfdc")
	fill.light_energy = 0.42
	fill.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	parent.add_child(fill)
	var rim := DirectionalLight3D.new()
	rim.name = "Rim"
	rim.rotation_degrees = Vector3(-18, 158, 0)
	rim.light_color = Color("#ffe6c0")
	rim.light_energy = 2.0
	# Edge light, not a mirror flash: little specular, and no second sun in the reflections
	# (a lit hat brim seen edge-on flared white).
	rim.light_specular = 0.2
	rim.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	parent.add_child(rim)
	var kicker := DirectionalLight3D.new()
	kicker.name = "Kicker"
	kicker.rotation_degrees = Vector3(-12, -150, 0)
	kicker.light_color = Color("#cfdcf2")
	kicker.light_energy = 0.75
	kicker.light_specular = 0.3
	kicker.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	parent.add_child(kicker)
	var world := WorldEnvironment.new()
	world.environment = stage_environment()
	parent.add_child(world)

static func stage_environment() -> Environment:
	if environment == null:
		environment = Environment.new()
		environment.background_mode = Environment.BG_CLEAR_COLOR
		environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		environment.ambient_light_color = Color("#d4cbbd")
		environment.ambient_light_energy = 0.3
		environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		environment.tonemap_exposure = 1.0
		WarriorVisual.add_reflections(environment, Color("#8b8a74"))
		environment.background_mode = Environment.BG_CLEAR_COLOR
	return environment

## Stage materials of a unit: skin and cloth lose the plastic sheen, cloth and leather get
## a faint velvet rim (fresnel), so the silhouette reads against the dark wash. Applied once
## per material (the preview meshes are only shown here and in the legacy preview).
static func stage_materials(unit: Node3D) -> void:
	for part: MeshInstance3D in unit.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		for surface in part.mesh.get_surface_count():
			var material := part.get_active_material(surface) as BaseMaterial3D
			if material == null or material.has_meta("drenovar_stage_helmet"):
				continue
			# Premium UI stage 4b: the spearman's polished kettle hat caught the stage's sky as
			# a bright white ring round the brim. On the stage only (this instance, never the
			# shared material the city uses) the steel is darker and less glossy.
			if material.resource_name.to_lower().contains("steel_helmet"):
				part.set_surface_override_material(surface, stage_helmet(material))
				continue
			if material.has_meta("drenovar_stage_surface"):
				continue
			material.set_meta("drenovar_stage_surface", true)
			var name := material.resource_name.to_lower()
			if WarriorVisual.has_part(name, ["skin", "_head", "beard"]):
				material.metallic_specular = 0.22
			elif WarriorVisual.has_part(name, ["cloth", "wool", "linen", "pants", "leather", "boot", "horsecoat", "surcoat", "aketon"]):
				material.rim_enabled = true
				material.rim = 0.28
				material.rim_tint = 0.65

static var helmet_tones := {}

## The stage's tone of a polished steel helmet (one per source material).
static func stage_helmet(material: BaseMaterial3D) -> BaseMaterial3D:
	var key := material.get_instance_id()
	if not helmet_tones.has(key):
		var toned := material.duplicate() as BaseMaterial3D
		# The brim's underside faces the stage's bright floor and sky at a grazing angle, where
		# a polished metal turns white whatever its colour: rougher and less metallic keeps it
		# reading as dark forged iron.
		toned.albedo_color = material.albedo_color * Color(0.56, 0.54, 0.51, 1.0)
		toned.roughness = maxf(material.roughness, 0.74)
		toned.metallic = minf(material.metallic, 0.28)
		toned.metallic_specular = 0.2
		toned.set_meta("drenovar_stage_helmet", true)
		helmet_tones[key] = toned
	return helmet_tones[key]

# ------------------------------------------------------------------ framing

## Camera axes of the stage view: right, up, and the direction toward the camera.
static func axes() -> Array:
	var direction := VIEW.normalized()
	var right := Vector3.UP.cross(direction).normalized()
	return [right, direction.cross(right).normalized(), direction]

## Silhouette of a unit in the camera plane, metres from the centre of its feet:
## {"up": [low, high], "right": [low, high]}. Measured by the portrait bake on the posed,
## animated unit (weapons included); without it, from the unit's figure (no weapons). The
## bake also stores "card": the same silhouette cut at the helmet (card portraits keep the
## figure large and let a long lance leave the card).
static func extents(id: String, shape: Dictionary) -> Dictionary:
	if framing.is_empty() and FileAccess.file_exists(FRAMING_PATH):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FRAMING_PATH))
		framing = parsed if parsed is Dictionary else {"": {}}
	if framing.has(id):
		return framing[id]
	if shape.is_empty():
		return {"up": [0.0, 1.9], "right": [-0.45, 0.45]}
	var basis := axes()
	var box: AABB = shape.box
	var feet := Vector3(box.get_center().x, shape.bottom, box.get_center().z)
	var up := [INF, -INF]
	var side := [INF, -INF]
	for i in 8:
		var corner := box.get_endpoint(i)
		corner.y = minf(corner.y, shape.top)
		var u: float = (corner - feet).dot(basis[1])
		var r: float = (corner - feet).dot(basis[0])
		up = [minf(up[0], u), maxf(up[1], u)]
		side = [minf(side[0], r), maxf(side[1], r)]
	return {"up": up, "right": side}

## Height of the view (metres at the figure) that puts the silhouette between `top` and
## `feet` (fractions of the frame height), or fits `width_share` of the frame width.
static func width_share(id: String) -> float:
	return WIDTH_SHARE if id.begins_with("ENG-") else RAM_WIDTH_SHARE

static func fit(ext: Dictionary, aspect: float, top: float, feet: float, width_share: float) -> float:
	var tall: float = float(ext.up[1]) - float(ext.up[0])
	var wide: float = float(ext.right[1]) - float(ext.right[0])
	return maxf(tall / (feet - top), wide / (width_share * maxf(0.1, aspect)))

## Aims the camera so the lowest point of the silhouette sits at `feet` and the silhouette is
## centred across the frame.
static func aim(camera_node: Camera3D, origin: Vector3, ext: Dictionary, visible_height: float, feet: float) -> void:
	var basis := axes()
	camera_node.fov = FOV
	var middle: float = (float(ext.right[0]) + float(ext.right[1])) * 0.5
	var target: Vector3 = origin + basis[0] * middle - basis[1] * ((0.5 - feet) * visible_height - float(ext.up[0]))
	var distance := visible_height * 0.5 / tan(deg_to_rad(FOV * 0.5))
	camera_node.position = target + basis[2] * distance
	camera_node.look_at(target)

## Camera for a figure: the same direction and lens for every unit; the figure fills
## `share` of the frame height (or 0.86 of its width) centred at `centre` (0 top, 1 bottom).
static func frame_camera(camera_node: Camera3D, shape: Dictionary, aspect: float, share: float, centre: float, width_share := 0.86) -> void:
	var direction := VIEW.normalized()
	camera_node.fov = FOV
	var tall: float = shape.top - shape.bottom
	var wide := projected_width(shape.box, direction)
	var visible_height := maxf(tall / share, wide / width_share / aspect)
	var distance := visible_height * 0.5 / tan(deg_to_rad(FOV * 0.5))
	var middle := Vector3(shape.box.get_center().x, (shape.top + shape.bottom) * 0.5, shape.box.get_center().z)
	# Look a little below the figure centre so the figure rides higher in the frame.
	var target := middle - Vector3.UP * (0.5 - centre) * visible_height
	camera_node.position = target + direction * distance
	camera_node.look_at(target)

# ------------------------------------------------------------------ plinth

static func dais_materials() -> Dictionary:
	if not materials.is_empty():
		return materials
	var stone := StandardMaterial3D.new()
	if requested.get(DAIS_STONE, false):
		stone.albedo_texture = ResourceLoader.load_threaded_get(DAIS_STONE) as Texture2D
	if stone.albedo_texture == null:
		stone.albedo_texture = load(DAIS_STONE)
	stone.albedo_color = Color("#d2c8b4")
	stone.metallic_specular = 0.08
	stone.vertex_color_use_as_albedo = true
	stone.roughness = 0.95
	stone.uv1_triplanar = true
	stone.uv1_scale = Vector3.ONE * 3.4
	stone.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var oak := StandardMaterial3D.new()
	oak.albedo_texture = UiKit.tex("kit_dais")
	oak.normal_enabled = true
	oak.normal_texture = UiKit.tex("kit_dais_n")
	oak.normal_scale = 1.25
	oak.roughness = 0.86
	oak.metallic_specular = 0.12
	oak.vertex_color_use_as_albedo = true
	oak.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var grain := StandardMaterial3D.new()
	grain.albedo_texture = UiKit.tex("kit_dais_top")
	grain.roughness = 0.94
	grain.metallic_specular = 0.05
	grain.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	materials = {"stone": stone, "oak": oak, "grain": grain}
	return materials

## A hewn radius round the plinth (a few slow waves; seeded, so a unit keeps its plinth).
static func wobble(angle: float, seed: int, amount: float) -> float:
	var waves := 0.0
	for k in 4:
		var phase := float(hash(seed * 31 + k) % 6283) / 1000.0
		waves += sin(angle * float(k + 2) + phase) / float(k + 1)
	return 1.0 + amount * waves * 0.55

## Carved oak plinth on a mossy field stone: an oak log section (end grain, bark and moss on
## top, a band of Slavic notch carving round the side, a small chamfer at the rim) standing on
## an irregular flat stone with moss and a dark contact ring where the oak meets it. Top of
## the oak at y = 0 (the unit's feet). Heights come from the framing, so the plinth looks the
## same on screen for a footman and for the ram.
static func make_plinth(radius: float, drum: float, rock: float, seed := 1) -> Node3D:
	var kit := dais_materials()
	var root := Node3D.new()
	root.name = "Plinth"
	var steps := 72
	var repeats := maxf(2.0, roundf(TAU * radius / (drum * 6.4)))
	# Oak drum: chamfer ring, then the carved side.
	var side := SurfaceTool.new()
	side.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings := [[0.965, 0.0, 0.0], [1.0, -drum * 0.08, 0.06], [1.0, -drum * 0.92, 0.94], [1.015, -drum, 1.0]]
	for i in steps:
		for j in rings.size() - 1:
			var quad: Array = []
			for corner in [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]]:
				var angle := TAU * float(corner[0]) / steps
				var ring: Array = rings[corner[1]]
				var r: float = radius * float(ring[0]) * wobble(angle, seed, 0.035)
				quad.append([Vector3(cos(angle) * r, float(ring[1]), sin(angle) * r), Vector2(float(corner[0]) / steps * repeats, float(ring[2])), angle, corner[1]])
			# Clockwise seen from outside (Godot's front faces).
			for index in [0, 2, 1, 0, 3, 2]:
				var v: Array = quad[index]
				# The foot of the oak darkens where it stands on the stone (contact shade).
				side.set_color(Color(0.58, 0.56, 0.54) if v[3] == 3 else Color.WHITE)
				side.set_normal(Vector3(cos(v[2]), 0.6 if v[3] == 0 else 0.0, sin(v[2])).normalized())
				side.set_uv(v[1])
				side.add_vertex(v[0])
	side.generate_tangents()
	var drum_mesh := MeshInstance3D.new()
	drum_mesh.name = "Oak"
	drum_mesh.mesh = side.commit()
	drum_mesh.material_override = kit.oak
	root.add_child(drum_mesh)
	# End grain on top.
	var top := SurfaceTool.new()
	top.begin(Mesh.PRIMITIVE_TRIANGLES)
	top.set_normal(Vector3.UP)
	for i in steps:
		for k in [0, 1, 2]:
			var point := Vector3.ZERO
			if k > 0:
				var angle := TAU * float(i + k - 1) / steps
				var r: float = radius * 0.965 * wobble(angle, seed, 0.035)
				point = Vector3(cos(angle) * r, 0.0, sin(angle) * r)
			top.set_uv(Vector2(0.5 + point.x / radius * 0.5, 0.5 + point.z / radius * 0.5))
			top.add_vertex(point)
	var grain := MeshInstance3D.new()
	grain.name = "Grain"
	grain.mesh = top.commit()
	grain.material_override = kit.grain
	root.add_child(grain)
	# Field stone: a domed top with moss, a rounded edge, darker where the oak stands on it.
	var stone := SurfaceTool.new()
	stone.begin(Mesh.PRIMITIVE_TRIANGLES)
	var base := -drum
	var profile := [[0.0, base + rock * 0.08], [0.98, base + rock * 0.02], [1.18, base - rock * 0.1], [1.3, base - rock * 0.55], [1.26, base - rock]]
	for i in steps:
		for j in profile.size() - 1:
			var quad: Array = []
			for corner in [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]]:
				var angle := TAU * float(corner[0]) / steps
				var ring: Array = profile[corner[1]]
				var reach: float = float(ring[0])
				var r := radius * reach * (wobble(angle, seed + 7, 0.12) if reach > 0.99 else wobble(angle, seed, 0.035))
				var y: float = float(ring[1])
				var moss := smoothstep(0.35, 0.8, 0.5 + 0.5 * sin(angle * 3.0 + float(seed)) * cos(angle * 5.0 - 1.3)) * (1.0 if corner[1] in [1, 2, 3] else 0.0)
				var shade := 0.62 if corner[1] == 1 else (0.8 if corner[1] == 0 else (0.86 if corner[1] == 4 else 1.0))
				var colour := Color(1.0, 0.97, 0.9).lerp(Color(0.5, 0.64, 0.28), moss * 0.7) * shade
				colour.a = 1.0
				quad.append([Vector3(cos(angle) * r, y, sin(angle) * r), colour, angle, corner[1]])
			for index in [0, 2, 1, 0, 3, 2]:
				var v: Array = quad[index]
				var tilt: float = [1.0, 0.85, 0.4, 0.05, -0.4][int(v[3])]
				stone.set_color(v[1])
				stone.set_normal(Vector3(cos(v[2]) * (1.0 - absf(tilt)), tilt, sin(v[2]) * (1.0 - absf(tilt))).normalized())
				stone.add_vertex(v[0])
	var slab := MeshInstance3D.new()
	slab.name = "Stone"
	slab.mesh = stone.commit()
	slab.material_override = kit.stone
	root.add_child(slab)
	return root

# ------------------------------------------------------------------ the control

func setup(game_data: Dictionary, id: String, unit_tier: int, caption: String) -> void:
	data = game_data
	unit_id = id
	tier = clampi(unit_tier, 1, UiKit.TIERS.size())
	title = caption
	tint = UiKit.TIERS[tier - 1]
	model_path = model_for(data, unit_id)
	request(model_path)

func _ready() -> void:
	name = "UnitStage"
	add_to_group("panel_drag")
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = false
	placeholder = TextureRect.new()
	placeholder.name = "Portrait"
	placeholder.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	placeholder.stretch_mode = TextureRect.STRETCH_SCALE
	placeholder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	placeholder.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(placeholder)
	view = TextureRect.new()
	view.name = "LiveView"
	view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	view.stretch_mode = TextureRect.STRETCH_SCALE
	view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	view.modulate.a = 0.0
	add_child(view)
	motes = UiKit.embers(400.0, 460.0)
	motes.amount = 22
	add_child(motes)
	build_plate()
	show_portrait()
	resized.connect(layout)
	layout()
	set_process(true)

## The painted backdrop (ink wash, medallion, warm light, plinth shadow) is drawn by a node
## placed under the rail and the stage (index 0 of `parent`), so the wash can spread behind
## the rail without covering it.
func attach_backdrop(parent: Control) -> void:
	backdrop = StageBackdrop.new()
	backdrop.stage = self
	parent.add_child(backdrop)
	parent.move_child(backdrop, 0)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	item_rect_changed.connect(backdrop.queue_redraw_all)

# Name plate: one drawn node (kit strip, tier badge, gold name) and the «i» chip.
func build_plate() -> void:
	plate = StagePlate.new()
	plate.name = "NamePlate"
	plate.strip = UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO)
	plate.badge = UiKit.tex("kit_badge")
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(plate)
	info = UiKit.info_chip("Подробнее о войске")
	info.name = "UnitInfo"
	info.pressed.connect(func(): info_pressed.emit())
	add_child(info)
	refresh_plate()

func refresh_plate() -> void:
	plate.title = title
	plate.numeral = ["I", "II", "III", "IV", "V"][tier - 1]
	plate.custom_minimum_size = plate.measure()
	plate.queue_redraw()

class StagePlate extends Control:
	var title := ""
	var numeral := "I"
	var strip: StyleBox
	var badge: Texture2D

	func measure() -> Vector2:
		var text := UiKit.KitText.line(title, UiKit.LABEL_FONT, 22)
		return Vector2(roundf(text.get_size().x) + 104.0, 44.0)

	func _draw() -> void:
		draw_style_box(strip, Rect2(16, 2, size.x - 16, size.y - 4))
		var text := UiKit.KitText.line(title, UiKit.LABEL_FONT, 22)
		var at := Vector2(48, roundf((size.y - text.get_size().y) * 0.5))
		text.draw_outline(get_canvas_item(), at, 4, UiKit.SHADE)
		text.draw(get_canvas_item(), at, UiKit.GOLD)
		draw_texture_rect(badge, Rect2(0, 0, 44, 42), false)
		var mark := UiKit.KitText.line(numeral, UiKit.TITLE_FONT, 16)
		mark.draw(get_canvas_item(), Vector2(roundf(22 - mark.get_size().x * 0.5), 10), UiKit.GOLD)

func layout() -> void:
	if not is_instance_valid(view):
		return
	view.position = Vector2.ZERO
	view.size = size
	place_portrait()
	motes.position = Vector2(size.x * 0.5, size.y * (FEET - 0.02))
	motes.emission_rect_extents = Vector2(size.x * 0.24, 10.0)
	var plate_size := plate.custom_minimum_size
	plate.size = plate_size
	plate.position = Vector2(roundf((size.x - plate_size.x) * 0.5), size.y - plate_size.y - 6.0)
	info.size = info.get_combined_minimum_size()
	info.position = plate.position + Vector2(plate_size.x - info.size.x - 14.0, roundf((plate_size.y - info.size.y) * 0.5))
	if viewport != null:
		viewport.size = render_size()
	if is_instance_valid(backdrop):
		backdrop.queue_redraw_all()

## The baked portrait stands where the live model will: the same framing rule on the same
## silhouette, so the fade from portrait to model does not jump.
func place_portrait() -> void:
	if size.y <= 0.0:
		return
	var ext := extents(unit_id, {})
	var stage_height := fit(ext, size.x / size.y, TOP, FEET, width_share(unit_id))
	var card_height := fit(ext.get("card", ext), PORTRAIT_SIZE.x / PORTRAIT_SIZE.y, PORTRAIT_TOP, PORTRAIT_FEET, PORTRAIT_WIDTH)
	var tall := size.y * card_height / stage_height
	var frame := Vector2(tall * PORTRAIT_SIZE.x / PORTRAIT_SIZE.y, tall)
	placeholder.size = frame
	placeholder.position = Vector2((size.x - frame.x) * 0.5, size.y * FEET - PORTRAIT_FEET * frame.y)

func render_size() -> Vector2i:
	var scale := get_viewport().get_final_transform().get_scale() if is_inside_tree() else Vector2.ONE
	return Vector2i(maxi(2, roundi(size.x * scale.x)), maxi(2, roundi(size.y * scale.y)))

func _process(delta: float) -> void:
	if not world_built:
		return
	if not waiting_path.is_empty():
		var scene := take(waiting_path)
		if scene != null:
			waiting_path = ""
			place_model(scene)
	if turntable == null:
		return
	var resting := not dragging and absf(spin_velocity) <= 0.0005 and Time.get_ticks_msec() - last_drag_msec > 3500
	if not dragging:
		if absf(spin_velocity) > 0.0005:
			spin += spin_velocity
			spin_velocity *= pow(0.02, delta)
		elif resting and absf(spin) > 0.001:
			# The unit turns back to face the viewer after a while.
			spin = lerp_angle(spin, 0.0, 1.0 - pow(0.12, delta))
	# A slow, gentle sway while nobody turns it (±5° over 11 s), so the stage never freezes.
	sway = lerpf(sway, 1.0 if resting else 0.0, 1.0 - pow(0.3, delta))
	var breathe := sin(Time.get_ticks_msec() * 0.001 * TAU / 11.0) * deg_to_rad(5.0) * sway
	turntable.rotation.y = spin + breathe

func _notification(what: int) -> void:
	if what == NOTIFICATION_ENTER_TREE and not world_built:
		build_world.call_deferred()
	elif what == NOTIFICATION_EXIT_TREE:
		# The window closed: nothing 3D outlives it (the viewport, world, model instance and
		# lights are children of this node; the loaded scenes go too, so their meshes and
		# textures leave memory). A ring or inspector of a training building requests the
		# model again on a worker thread before the next open.
		scenes.clear()
		recent.clear()

# Built after the window's first frame: the open itself costs no 3D work.
func build_world() -> void:
	if world_built or not is_inside_tree():
		return
	if DisplayServer.get_name() == "headless":
		await get_tree().process_frame
	else:
		await RenderingServer.frame_post_draw
	if not is_inside_tree() or world_built:
		return
	var started := Time.get_ticks_usec()
	world_built = true
	viewport = SubViewport.new()
	viewport.name = "StageViewport"
	viewport.own_world_3d = true
	viewport.transparent_bg = true
	viewport.msaa_3d = Viewport.MSAA_4X
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	viewport.size = render_size()
	add_child(viewport)
	holder = Node3D.new()
	viewport.add_child(holder)
	turntable = Node3D.new()
	turntable.name = "Turntable"
	holder.add_child(turntable)
	camera = Camera3D.new()
	holder.add_child(camera)
	camera.make_current()
	light_rig(holder)
	view.texture = viewport.get_texture()
	built_usec = Time.get_ticks_usec() - started
	waiting_path = model_path

func place_model(scene: PackedScene) -> void:
	if is_instance_valid(model):
		model.get_parent().queue_free()
	var mount := Node3D.new()
	turntable.add_child(mount)
	model = scene.instantiate() as Node3D
	var warrior := unit_id.begins_with("ENG-")
	if warrior:
		WarriorVisual.prepare(model)
	stage_materials(model)
	mount.add_child(model)
	if not warrior:
		# The ram faces +Z like the troops; turned a little more to show its length.
		model.rotation_degrees.y = -28.0
	play_idle(model)
	var shape := figure(model)
	var box: AABB = shape.box
	var feet := Vector3(box.get_center().x, shape.bottom, box.get_center().z)
	var aspect := size.x / maxf(1.0, size.y)
	var ext := extents(unit_id, shape)
	var visible_height := fit(ext, aspect, TOP, FEET, width_share(unit_id))
	# The plinth is sized from the framing, so it looks the same on screen for every unit:
	# a little wider than the stance (the ram: round its wheels), oak 5 % (the ram 3 %) and
	# stone 3 % of the view high.
	var reach := maxf(box.size.x, box.size.z) * 0.5
	var radius := clampf(reach * 0.78, 0.42, 1.5) if warrior else clampf(reach * 1.06, 1.0, 3.2)
	radius = minf(radius, visible_height * aspect * (0.4 if warrior else 0.33))
	var plinth := make_plinth(radius, visible_height * (0.05 if warrior else 0.032), visible_height * 0.03, hash(unit_id))
	plinth.position = feet
	mount.add_child(plinth)
	# Contact shadow just above the oak (WarriorVisual puts it under the feet).
	WarriorVisual.ground_shadow(mount, box)
	mount.get_child(mount.get_child_count() - 1).position.y = shape.bottom + 0.004
	aim(camera, feet, ext, visible_height, FEET)
	reveal()

func play_idle(unit: Node3D) -> void:
	var drill := str(data.get("unitModels", {}).get(unit_id, {}).get("drill", ""))
	var clip := "Recruit_Showcase" if drill == "Mounted_Drill" else "Idle"
	for player: AnimationPlayer in unit.find_children("*", "AnimationPlayer", true, false):
		for name: String in player.get_animation_list():
			if clip.to_lower() in name.to_lower():
				player.get_animation(name).loop_mode = Animation.LOOP_LINEAR
				player.play(name, 0.0)
				break

func reveal() -> void:
	if fade != null:
		fade.kill()
	fade = create_tween().set_parallel()
	fade.tween_property(view, "modulate:a", 1.0, 0.28).set_trans(Tween.TRANS_SINE)
	fade.tween_property(placeholder, "modulate:a", 0.0, 0.32).set_trans(Tween.TRANS_SINE)

func show_portrait() -> void:
	placeholder.texture = portrait(unit_id)
	placeholder.modulate.a = 1.0

## Switches the unit on the stage (card tap, building switch): the portrait of the new
## unit shows at once, the live model follows when its scene is ready.
func show_unit(id: String, unit_tier: int, caption: String) -> void:
	if id == unit_id:
		return
	unit_id = id
	tier = clampi(unit_tier, 1, UiKit.TIERS.size())
	title = caption
	refresh_plate()
	layout()
	var from := tint
	var to: Color = UiKit.TIERS[tier - 1]
	create_tween().tween_method(func(c: Color):
		tint = c
		if is_instance_valid(backdrop):
			backdrop.queue_redraw_all(), from, to, 0.22)
	if fade != null:
		fade.kill()
	view.modulate.a = 0.0
	show_portrait()
	spin = 0.0
	spin_velocity = 0.0
	model_path = model_for(data, unit_id)
	if is_instance_valid(model):
		model.get_parent().queue_free()
		model = null
	if world_built:
		waiting_path = model_path
	request(model_path)

# ------------------------------------------------------------------ backdrop

## Painted backdrop of the stage, drawn under the rail and the stage: a warm glow on the
## linen, the ink wash in the tier colour (a wide pale bleed, the main splash and a dense
## core), the carved solar medallion behind the figure and the soft shadow of the plinth.
## Its child StageLight adds the warm light falling on the figure (additive).
class StageBackdrop extends Control:
	var stage: Control
	var ink: Texture2D
	var solar: Texture2D
	var glow: Texture2D
	var shade: Texture2D
	var light: Control

	func _ready() -> void:
		name = "StageBackdrop"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		ink = UiKit.tex("kit_ink")
		solar = UiKit.tex("kit_solar")
		glow = UiKit.warm_glow()
		shade = UiKit.ground_shadow()
		light = StageLight.new()
		light.backdrop = self
		add_child(light)
		light.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	func stage_rect() -> Rect2:
		if not is_instance_valid(stage):
			return Rect2(Vector2.ZERO, size)
		return Rect2(stage.global_position - global_position, stage.size)

	func queue_redraw_all() -> void:
		queue_redraw()
		if is_instance_valid(light):
			light.queue_redraw()

	func _draw() -> void:
		var r := stage_rect()
		var tint: Color = stage.tint if is_instance_valid(stage) else Color("#7d8288")
		var w := r.size.x
		var h := r.size.y
		var centre := r.position + Vector2(w * 0.5, h * 0.46)
		# Warm candle glow on the linen behind the whole stage.
		draw_texture_rect(glow, Rect2(centre - Vector2(w * 1.0, h * 0.66), Vector2(w * 2.0, h * 1.32)), false, Color(1, 1, 1, 1.0))
		if ink != null:
			# A wide bleed (mirrored, so its strokes differ), the main splash laid twice
			# (saturated, nearly opaque), and a dense dark core behind the figure.
			var deep := Color.from_hsv(tint.h, minf(1.0, tint.s * 1.25 + 0.06), tint.v * 0.78)
			draw_set_transform(centre, 0.0, Vector2(-1, 1))
			draw_texture_rect(ink, Rect2(-Vector2(w * 0.74, h * 0.6), Vector2(w * 1.48, h * 1.2)), false, Color(tint, 0.62))
			draw_set_transform(centre, 0.0, Vector2.ONE)
			draw_texture_rect(ink, Rect2(-Vector2(w * 0.66, h * 0.54), Vector2(w * 1.32, h * 1.08)), false, Color(deep, 1.0))
			draw_texture_rect(ink, Rect2(-Vector2(w * 0.6, h * 0.5), Vector2(w * 1.2, h * 1.0)), false, Color(deep.darkened(0.2), 0.8))
			draw_set_transform(centre + Vector2(0, h * 0.04), PI, Vector2.ONE)
			draw_texture_rect(ink, Rect2(-Vector2(w * 0.44, h * 0.4), Vector2(w * 0.88, h * 0.8)), false, Color(deep.darkened(0.55), 0.78))
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		if solar != null:
			var side := minf(w * 0.92, h * 0.76)
			var at := r.position + Vector2(w * 0.5, h * 0.4)
			draw_texture_rect(solar, Rect2(at - Vector2(side, side) * 0.5, Vector2(side, side)), false, Color(tint.lightened(0.6), 0.34))
		# The plinth's soft shadow on the wash.
		var foot := r.position + Vector2(w * 0.5, h * (FEET + 0.095))
		draw_texture_rect(shade, Rect2(foot - Vector2(w * 0.46, h * 0.045), Vector2(w * 0.92, h * 0.09)), false, Color(1, 1, 1, 0.85))

## Warm light falling on the figure from the upper left (additive): a soft beam with dust
## and a bloom round the upper body.
class StageLight extends Control:
	var backdrop: StageBackdrop
	var beam: Texture2D
	var bloom: Texture2D

	func _ready() -> void:
		name = "StageLight"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		var additive := CanvasItemMaterial.new()
		additive.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		material = additive
		beam = UiKit.tex("kit_beam")
		bloom = UiKit.warm_glow()

	func _draw() -> void:
		var r: Rect2 = backdrop.stage_rect()
		var w := r.size.x
		var h := r.size.y
		if beam != null:
			draw_set_transform(r.position + Vector2(w * 0.16, -h * 0.04), -0.5, Vector2.ONE)
			draw_texture_rect(beam, Rect2(-w * 0.2, 0, w * 0.4, h * 0.95), false, Color(1.0, 0.78, 0.5, 0.3))
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		var spot := r.position + Vector2(w * 0.5, h * 0.36)
		draw_texture_rect(bloom, Rect2(spot - Vector2(w * 0.36, h * 0.32), Vector2(w * 0.72, h * 0.64)), false, Color(1.0, 0.72, 0.42, 0.2))

# ------------------------------------------------------------------ feedback

## Completion feedback, short and non-blocking: a gold banner slides in over the stage,
## a burst of sparks rises from the dais, both are gone after ~2.4 s. Taps pass through.
func celebrate(text: String) -> void:
	var banner := PanelContainer.new()
	banner.name = "StageToast"
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	banner.add_theme_stylebox_override("panel", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(30, 8, 30, 10)))
	var words := Label.new()
	words.text = text
	words.add_theme_font_override("font", UiKit.LABEL_FONT)
	words.add_theme_font_size_override("font_size", 21)
	words.add_theme_color_override("font_color", UiKit.GOLD)
	words.add_theme_color_override("font_outline_color", UiKit.SHADE)
	words.add_theme_constant_override("outline_size", 4)
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	banner.add_child(words)
	add_child(banner)
	var wide := banner.get_combined_minimum_size()
	banner.size = wide
	var at := Vector2(roundf((size.x - wide.x) * 0.5), roundf(size.y * 0.08))
	banner.position = at - Vector2(0, 14)
	banner.modulate.a = 0.0
	var sparks := CPUParticles2D.new()
	sparks.name = "StageSparks"
	sparks.texture = UiKit.mote()
	sparks.amount = 36
	sparks.one_shot = true
	sparks.explosiveness = 0.85
	sparks.lifetime = 1.4
	sparks.local_coords = true
	sparks.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	sparks.emission_rect_extents = Vector2(size.x * 0.2, 8.0)
	sparks.position = Vector2(size.x * 0.5, size.y * 0.74)
	sparks.direction = Vector2(0, -1)
	sparks.spread = 34.0
	sparks.gravity = Vector2(0, 90)
	sparks.initial_velocity_min = 120.0
	sparks.initial_velocity_max = 220.0
	sparks.scale_amount_min = 0.35
	sparks.scale_amount_max = 0.9
	var glow := Gradient.new()
	glow.offsets = PackedFloat32Array([0.0, 0.15, 1.0])
	glow.colors = PackedColorArray([Color(1, 0.92, 0.6, 0), Color(1, 0.86, 0.5, 1), Color(1, 0.6, 0.25, 0)])
	sparks.color_ramp = glow
	add_child(sparks)
	sparks.emitting = true
	var show := banner.create_tween()
	show.set_parallel()
	show.tween_property(banner, "modulate:a", 1.0, 0.18)
	show.tween_property(banner, "position", at, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	show.chain().tween_interval(1.6)
	show.chain().tween_property(banner, "modulate:a", 0.0, 0.4)
	show.chain().tween_callback(banner.queue_free)
	get_tree().create_timer(2.4).timeout.connect(func():
		if is_instance_valid(sparks):
			sparks.queue_free())

# ------------------------------------------------------------------ turning

func drag_begin() -> void:
	dragging = true
	spin_velocity = 0.0

## Horizontal finger travel in canvas units; slow on purpose (a full turn is ~3 widths).
func drag_by(dx: float) -> void:
	var step := dx * TAU / maxf(300.0, size.x * 3.0)
	spin += step
	spin_velocity = step
	last_drag_msec = Time.get_ticks_msec()
	if turntable != null:
		turntable.rotation.y = spin

func drag_end() -> void:
	dragging = false
	last_drag_msec = Time.get_ticks_msec()

func _gui_input(event: InputEvent) -> void:
	# Mouse (desktop, editor); touch arrives through TouchScroll's drag areas.
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			drag_begin()
		else:
			drag_end()
		accept_event()
	elif event is InputEventMouseMotion and dragging:
		drag_by(event.relative.x)
		accept_event()
