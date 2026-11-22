extends Control
## Recruitment hero stage (premium UI stage 2, ui_premium/STAGE2.md): the live 3D unit on a
## carved oak-and-stone dais, over an ink-wash pool tinted by the unit's tier, with drifting
## embers, a soft contact shadow and a name plate. Drag to turn the dais slowly.
##
## Cost rules:
## - The window opens with only the 2D layers and the baked portrait of the unit (its first
##   frame costs no 3D work). The 3D world is built after that frame, the model comes from a
##   worker thread (request() is called when the barracks ring or inspector opens), and the
##   live view fades in over the portrait.
## - The SubViewport lives only while the window is open: it is a child of this node, which
##   the window frees on close. It renders at device resolution (canvas size x content scale)
##   with 4x MSAA, so the unit stays as crisp as the rest of the UI on the phone.
## The same camera, framing and three-point light bake the card portraits
## (tools/bake_unit_portraits.gd), so the portrait and the live view line up.

const UiKit = preload("res://src/ui_kit.gd")
const WarriorVisual = preload("res://src/warrior_visual.gd")

## One 3/4 view for the whole roster: from the front right, a little above the chest.
const VIEW := Vector3(0.62, 0.2, 1.0)
const FOV := 24.0
## The figure (feet to helmet) fills this share of the stage height; its centre sits here.
const FIGURE_SHARE := 0.6
const FIGURE_CENTRE := 0.44
const PORTRAIT_DIR := "res://assets/ui/units/"
const DAIS_STONE := "res://assets/city/premium/surfaces07/stone-albedo.jpg"

static var scenes := {}
static var recent: Array = []
static var requested := {}
static var portraits := {}
static var materials := {}

signal info_pressed

var data: Dictionary
var unit_id := ""
var tier := 1
var title := ""
var tint := Color("#7d8288")
var splash: Texture2D
var ground: Texture2D
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

## The loaded scene, or null while the worker is still busy. The last three stay cached.
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

## Warm key from the upper left (soft shadows), cool fill from the right, a bright rim
## from behind, sky reflections for the metal; transparent background.
static func light_rig(parent: Node3D, shadows := true) -> void:
	var key := DirectionalLight3D.new()
	key.name = "Key"
	key.rotation_degrees = Vector3(-38, -16, 0)
	key.light_color = Color("#ffe5c2")
	key.light_energy = 1.9
	key.shadow_enabled = shadows
	key.shadow_blur = 1.6
	key.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	key.directional_shadow_max_distance = 14.0
	parent.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.name = "Fill"
	fill.rotation_degrees = Vector3(-10, 64, 0)
	fill.light_color = Color("#c3d4ea")
	fill.light_energy = 0.4
	parent.add_child(fill)
	var rim := DirectionalLight3D.new()
	rim.name = "Rim"
	rim.rotation_degrees = Vector3(-20, 158, 0)
	rim.light_color = Color("#fff0d4")
	rim.light_energy = 1.5
	parent.add_child(rim)
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d2d4d0")
	env.ambient_light_energy = 0.36
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.08
	WarriorVisual.add_reflections(env, Color("#8b9874"))
	env.background_mode = Environment.BG_CLEAR_COLOR
	world.environment = env
	parent.add_child(world)

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

# ------------------------------------------------------------------ dais

static func dais_materials() -> Dictionary:
	if not materials.is_empty():
		return materials
	var stone := StandardMaterial3D.new()
	if requested.get(DAIS_STONE, false):
		stone.albedo_texture = ResourceLoader.load_threaded_get(DAIS_STONE) as Texture2D
	if stone.albedo_texture == null:
		stone.albedo_texture = load(DAIS_STONE)
	stone.albedo_color = Color("#9a907f")
	stone.roughness = 0.86
	stone.uv1_triplanar = true
	stone.uv1_scale = Vector3.ONE * 1.4
	stone.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var plinth := stone.duplicate() as StandardMaterial3D
	plinth.albedo_color = Color("#6f675c")
	var oak := StandardMaterial3D.new()
	oak.albedo_texture = UiKit.tex("kit_dais")
	oak.normal_enabled = true
	oak.normal_texture = UiKit.tex("kit_dais_n")
	oak.normal_scale = 1.1
	oak.roughness = 0.62
	oak.metallic_specular = 0.42
	oak.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var bronze := StandardMaterial3D.new()
	bronze.albedo_color = Color("#b98a45")
	bronze.metallic = 0.86
	bronze.roughness = 0.34
	materials = {"stone": stone, "plinth": plinth, "oak": oak, "bronze": bronze}
	return materials

## Stone slab on a carved oak drum with bronze rings, on a wider stone plinth. The top of
## the slab is at y = 0 (the unit's feet).
static func make_dais(radius: float) -> Node3D:
	var kit := dais_materials()
	var root := Node3D.new()
	root.name = "Dais"
	var parts := [
		# [top radius, bottom radius, height, centre y, material]
		[radius, radius * 1.01, 0.05, -0.025, "stone"],
		[radius * 1.03, radius * 1.05, 0.2, -0.15, "oak"],
		[radius * 1.17, radius * 1.21, 0.1, -0.3, "plinth"],
	]
	for part: Array in parts:
		var mesh := CylinderMesh.new()
		mesh.top_radius = part[0]
		mesh.bottom_radius = part[1]
		mesh.height = part[2]
		mesh.radial_segments = 72
		mesh.rings = 1
		var item := MeshInstance3D.new()
		item.mesh = mesh
		var material: StandardMaterial3D = kit[part[4]]
		if part[4] == "oak":
			# Whole repeats of the carving around the drum (one motif ~0.16 m).
			material = material.duplicate()
			material.uv1_scale = Vector3(maxf(2.0, roundf(TAU * radius / 1.28)), 1.0, 1.0)
		item.material_override = material
		item.position.y = part[3]
		root.add_child(item)
	for ring_y: float in [-0.05, -0.25]:
		var ring := TorusMesh.new()
		ring.inner_radius = radius * 1.035
		ring.outer_radius = radius * 1.035 + 0.035
		ring.rings = 72
		ring.ring_segments = 10
		var item := MeshInstance3D.new()
		item.mesh = ring
		item.material_override = kit.bronze
		item.position.y = ring_y
		root.add_child(item)
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
	splash = UiKit.tex("kit_splash")
	ground = UiKit.ground_shadow()
	placeholder = TextureRect.new()
	placeholder.name = "Portrait"
	placeholder.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	placeholder.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
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
	motes.amount = 18
	add_child(motes)
	build_plate()
	show_portrait()
	resized.connect(layout)
	layout()
	set_process(true)

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
	var frame_h := size.y * FIGURE_SHARE * 1.06
	var frame_w := frame_h * 288.0 / 352.0
	placeholder.size = Vector2(frame_w, frame_h)
	placeholder.position = Vector2((size.x - frame_w) * 0.5, size.y * FIGURE_CENTRE - frame_h * 0.5)
	motes.position = Vector2(size.x * 0.5, size.y * 0.8)
	motes.emission_rect_extents = Vector2(size.x * 0.26, 14.0)
	var plate_size := plate.custom_minimum_size
	plate.size = plate_size
	plate.position = Vector2(roundf((size.x - plate_size.x) * 0.5), size.y - plate_size.y - 6.0)
	info.size = info.get_combined_minimum_size()
	info.position = plate.position + Vector2(plate_size.x - info.size.x - 14.0, roundf((plate_size.y - info.size.y) * 0.5))
	if viewport != null:
		viewport.size = render_size()
	queue_redraw()

func render_size() -> Vector2i:
	var scale := get_viewport().get_final_transform().get_scale() if is_inside_tree() else Vector2.ONE
	return Vector2i(maxi(2, roundi(size.x * scale.x)), maxi(2, roundi(size.y * scale.y)))

func _draw() -> void:
	if splash != null:
		# Ink wash in the tier colour: a wide pale bleed, a dense dark core behind the figure,
		# and a lighter bloom behind the head so the helmet reads against it.
		draw_texture_rect(splash, Rect2(size.x * 0.0, size.y * 0.0, size.x * 1.0, size.y * 0.9), false, Color(tint.darkened(0.05), 0.5))
		draw_texture_rect(splash, Rect2(size.x * 0.1, size.y * 0.06, size.x * 0.8, size.y * 0.72), false, Color(tint.darkened(0.5), 0.78))
		draw_texture_rect(splash, Rect2(size.x * 0.2, size.y * 0.12, size.x * 0.6, size.y * 0.5), false, Color(tint.darkened(0.62), 0.55))
		draw_texture_rect(splash, Rect2(size.x * 0.32, size.y * 0.06, size.x * 0.36, size.y * 0.3), false, Color(tint.lightened(0.3), 0.22))
	if ground != null:
		draw_texture_rect(ground, Rect2(size.x * 0.12, size.y * 0.7, size.x * 0.76, size.y * 0.2), false, Color(1, 1, 1, 0.9))

func _process(delta: float) -> void:
	if not world_built:
		return
	if not waiting_path.is_empty():
		var scene := take(waiting_path)
		if scene != null:
			waiting_path = ""
			place_model(scene)
	if not dragging and turntable != null:
		if absf(spin_velocity) > 0.0005:
			spin += spin_velocity
			spin_velocity *= pow(0.02, delta)
		elif Time.get_ticks_msec() - last_drag_msec > 3500 and absf(spin) > 0.001:
			# The unit turns back to face the viewer after a while.
			spin = lerp_angle(spin, 0.0, 1.0 - pow(0.12, delta))
		turntable.rotation.y = spin

func _notification(what: int) -> void:
	if what == NOTIFICATION_ENTER_TREE and not world_built:
		build_world.call_deferred()

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
	mount.add_child(model)
	if not warrior:
		model.rotation_degrees.y = -28.0
	play_idle(model)
	var shape := figure(model)
	var box: AABB = shape.box
	# Warriors stand on a round slab a little wider than their stance; the ram's slab is
	# sized to its wheelbase (its long axis overhangs a little, as on a display plinth).
	var radius := clampf(maxf(box.size.x, box.size.z) * 0.5 * 0.78, 0.5, 1.6) if warrior else clampf(maxf(box.size.x, box.size.z) * 0.5 * 0.8, 0.8, 3.0)
	var dais := make_dais(radius)
	dais.position = Vector3(box.get_center().x, shape.bottom, box.get_center().z)
	mount.add_child(dais)
	# Contact shadow just above the slab (WarriorVisual puts it under the feet).
	WarriorVisual.ground_shadow(mount, box)
	mount.get_child(mount.get_child_count() - 1).position.y = shape.bottom + 0.004
	# The dais is part of the framing: the figure stands in the upper part of the frame.
	if warrior:
		frame_camera(camera, shape, float(size.x) / maxf(1.0, size.y), FIGURE_SHARE, FIGURE_CENTRE)
	else:
		# A machine is wide: smaller in the frame so the dais and the wash show around it.
		frame_camera(camera, shape, float(size.x) / maxf(1.0, size.y), 0.42, FIGURE_CENTRE + 0.04, 0.7)
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
	create_tween().tween_method(func(c: Color): tint = c; queue_redraw(), from, to, 0.22)
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
