extends Control
## Story dialogue over the map (story intro, chapter talks).
##
## The speaker is the same game model as on the map, drawn larger in its own small 3D world
## (SubViewport, own world, transparent): waist-up, three-quarter view, slow push-in, playing a talk
## clip. The portrait slides in on its side (left or right), the name plate sits at the portrait's
## inner edge above the line, the English line types in over a dark band at the bottom, the map
## stays visible above. hide_line() slides the portrait out so the map is whole again.
## Deterministic: everything advances with tick(delta) (fixed-fps recordings).

const UiKit = preload("res://src/ui_kit.gd")
const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
const CHARS_PER_SECOND := 46.0
const SLIDE_SECONDS := 0.28

var portrait_view: SubViewport
var portrait_rect: TextureRect
var portrait_root: Node3D
var portrait_camera: Camera3D
var band: Control
var name_plate: PanelContainer
var name_label: Label
var line_label: Label
var speakers: Dictionary = {}      # speaker id -> {rig, frame:{height, distance, side_offset}, talk:[clips], idle:[clips]}
var current := ""
var side := "left"
var shown := 0.0                    # 0 hidden .. 1 shown (slide)
var want_shown := false
var typed := 0.0
var line_text := ""
var push := 0.0
var talk_energy := 0.0
var band_texture: GradientTexture2D

func _init() -> void:
	name = "StoryDialogue"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	band = Control.new()
	band.name = "Band"
	band.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	band.draw.connect(draw_band)
	add_child(band)
	portrait_view = SubViewport.new()
	portrait_view.name = "PortraitView"
	portrait_view.own_world_3d = true
	portrait_view.transparent_bg = true
	portrait_view.size = Vector2i(720, 900)
	portrait_view.msaa_3d = Viewport.MSAA_4X
	portrait_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(portrait_view)
	portrait_root = Node3D.new()
	portrait_root.name = "PortraitWorld"
	portrait_view.add_child(portrait_root)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_CLEAR_COLOR
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("#d9c9ac")
	environment.ambient_light_energy = 0.9
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	portrait_root.add_child(world_environment)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38, -32, 0)
	key.light_energy = 1.25
	key.light_color = Color("#fff1d6")
	portrait_root.add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-20, 150, 0)
	rim.light_energy = 0.7
	rim.light_color = Color("#a9c4ff")
	portrait_root.add_child(rim)
	portrait_camera = Camera3D.new()
	portrait_camera.fov = 26.0
	portrait_camera.current = true
	portrait_root.add_child(portrait_camera)
	portrait_rect = TextureRect.new()
	portrait_rect.name = "Portrait"
	portrait_rect.texture = portrait_view.get_texture()
	portrait_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	portrait_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(portrait_rect)
	name_plate = PanelContainer.new()
	name_plate.name = "NamePlate"
	name_plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var plate := StyleBoxFlat.new()
	plate.bg_color = Color(0.05, 0.04, 0.03, 0.92)
	plate.border_color = Color("#b48a4e")
	plate.border_width_top = 1
	plate.border_width_bottom = 1
	plate.content_margin_left = 22
	plate.content_margin_right = 22
	plate.content_margin_top = 3
	plate.content_margin_bottom = 4
	name_plate.add_theme_stylebox_override("panel", plate)
	add_child(name_plate)
	name_label = Label.new()
	name_label.add_theme_font_override("font", UiKit.LABEL_FONT)
	name_label.add_theme_font_size_override("font_size", 21)
	name_label.add_theme_color_override("font_color", Color("#f7e2ad"))
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_plate.add_child(name_label)
	line_label = Label.new()
	line_label.name = "Line"
	line_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line_label.add_theme_font_override("font", UiKit.BODY_FONT)
	line_label.add_theme_font_size_override("font_size", 22)
	line_label.add_theme_color_override("font_color", Color("#fbf1dc"))
	line_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	line_label.add_theme_constant_override("shadow_offset_x", 1)
	line_label.add_theme_constant_override("shadow_offset_y", 2)
	line_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(line_label)
	modulate.a = 0.0

## Registers a speaker: the model is loaded now (blocking) so its first line has no pop-in.
## frame: {"height": eye height m, "distance": camera distance m, "yaw": model yaw rad}.
func add_speaker(id: String, display_name: String, path: String, frame: Dictionary, talk: Array, idle: Array,
		model_scale := 1.0, species := "", level := 1, setup_rig := Callable()) -> void:
	var rig := Rig.new()
	rig.model_scale = model_scale
	if not species.is_empty():
		rig.painted = false
		rig.creature_species = species
		rig.creature_level = level
	rig.setup("portrait_" + id, path)
	rig.visible = false
	portrait_root.add_child(rig)
	rig.poll_load(true)
	if setup_rig.is_valid():
		setup_rig.call(rig)
	rig.rotation.y = float(frame.get("yaw", -0.42))
	if not species.is_empty() and rig.model != null:
		CreatureVisuals.update_lod(rig.model, portrait_camera)
	frame = fit_frame(rig, frame, not species.is_empty())
	speakers[id] = {"rig": rig, "name": display_name, "frame": frame, "talk": talk, "idle": idle}

## Frames the speaker from its real bounds: humans waist-up (eyes at ~0.93 of the height), a beast
## head and chest. Explicit frame values win over the fitted ones only for yaw/lateral.
func fit_frame(rig: Rig, frame: Dictionary, beast: bool) -> Dictionary:
	if rig.model == null:
		return frame
	var box := AABB()
	var first := true
	for mesh: MeshInstance3D in rig.model.find_children("*", "MeshInstance3D", true, false):
		if not mesh.is_visible_in_tree() or mesh.mesh == null:
			continue
		var local := mesh.global_transform * mesh.get_aabb()
		box = local if first else box.merge(local)
		first = false
	if first or box.size.y < 0.1:
		return frame
	var fitted := frame.duplicate()
	var height := box.end.y
	if beast:
		var length := maxf(box.size.x, box.size.z)
		fitted["height"] = height * 0.86
		fitted["distance"] = maxf(height, length * 0.55) * 1.55
	else:
		fitted["height"] = height * 0.93
		fitted["distance"] = height * 1.22
	return fitted

## Registers a speaker drawn from a painted portrait (background removed, PNG with alpha) instead of
## the 3D model. options: {"height": share of the screen height, "faces": "right" | "left" (where the
## figure looks in the picture; it is mirrored to look into the screen)}.
func add_image_speaker(id: String, display_name: String, texture_path: String, options: Dictionary = {}) -> void:
	var texture: Texture2D = load(texture_path) if ResourceLoader.exists(texture_path) else null
	if texture == null:
		push_warning("StoryDialogue: portrait missing " + texture_path)
		return
	speakers[id] = {"image": texture, "name": display_name, "options": options, "talk": [], "idle": []}

## Shows `text` said by `speaker_id` on `on_side` ("left" | "right").
func show_line(speaker_id: String, text: String, on_side := "left") -> void:
	if not speakers.has(speaker_id):
		return
	var changed := speaker_id != current or on_side != side or not want_shown
	if changed:
		for id in speakers:
			if speakers[id].has("rig"):
				(speakers[id].rig as Rig).visible = id == speaker_id
		current = speaker_id
		side = on_side
		push = 0.0
		if shown > 0.0 and on_side != side:
			shown = 0.0
	var entry: Dictionary = speakers[speaker_id]
	if entry.has("image"):
		portrait_rect.texture = entry.image
		portrait_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT
		var faces := String(entry.options.get("faces", "right"))
		portrait_rect.flip_h = (on_side == "right") == (faces == "right")
		portrait_view.render_target_update_mode = SubViewport.UPDATE_DISABLED
	else:
		portrait_rect.texture = portrait_view.get_texture()
		portrait_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		portrait_rect.flip_h = false
		portrait_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		(entry.rig as Rig).play(entry.talk, 0.2)
	name_label.text = String(entry.name)
	line_text = text
	line_label.text = text
	typed = 0.0
	want_shown = true
	layout_now()

func hide_line() -> void:
	want_shown = false
	if current != "" and speakers.has(current) and speakers[current].has("rig"):
		var entry: Dictionary = speakers[current]
		(entry.rig as Rig).play(entry.idle, 0.3)

func is_showing() -> bool:
	return want_shown or shown > 0.001

## Voice loudness 0..1 of the current line (head motion while speaking).
func set_energy(value: float) -> void:
	talk_energy = value

func tick(delta: float) -> void:
	var target := 1.0 if want_shown else 0.0
	shown = move_toward(shown, target, delta / SLIDE_SECONDS)
	modulate.a = smoothstep(0.0, 1.0, shown)
	typed += delta * CHARS_PER_SECOND
	line_label.visible_characters = int(typed) if typed < line_text.length() else -1
	push += delta
	if current != "" and speakers.has(current) and speakers[current].has("rig"):
		var entry: Dictionary = speakers[current]
		var frame: Dictionary = entry.frame
		var height := float(frame.get("height", 1.55))
		var distance := float(frame.get("distance", 2.2)) * (1.0 - 0.045 * minf(push / 4.0, 1.0))
		var lateral := float(frame.get("lateral", 0.0)) * (1.0 if side == "left" else -1.0)
		portrait_camera.position = Vector3(lateral, height - 0.08, distance)
		portrait_camera.look_at(Vector3(lateral * 0.35, height - 0.22, 0.0), Vector3.UP)
		var rig: Rig = entry.rig
		rig.rotation.y = float(frame.get("yaw", -0.42)) * (1.0 if side == "left" else -1.0)
	layout_now()
	band.queue_redraw()

## Positions: portrait on its side (bottom-anchored, ~42 % of the width), the line on the
## opposite side of the band, the name plate at the portrait's inner edge.
func layout_now() -> void:
	var view := size
	if view.x <= 0.0:
		return
	var width := view.y * 0.8
	var top := view.y * 0.06
	var tall := view.y * 0.94
	var edge := 0.02
	var entry: Dictionary = speakers.get(current, {})
	if entry.has("image"):
		var texture: Texture2D = entry.image
		var aspect := float(texture.get_width()) / maxf(1.0, float(texture.get_height()))
		tall = view.y * float(entry.options.get("height", 0.92))
		width = minf(tall * aspect, view.x * 0.5)
		tall = width / aspect
		top = view.y - tall
		edge = float(entry.options.get("edge", 0.0))
	var slide := (1.0 - smoothstep(0.0, 1.0, shown)) * width * 0.35
	var x := (view.x * edge - slide) if side == "left" else (view.x * (1.0 - edge) - width + slide)
	# A painted portrait breathes: a slow push-in from its feet and a small rise while it speaks.
	var grow := 1.0 + 0.035 * minf(push / 5.0, 1.0) if entry.has("image") else 1.0
	portrait_rect.pivot_offset = Vector2(width * 0.5, tall)
	portrait_rect.scale = Vector2(grow, grow)
	portrait_rect.position = Vector2(x, top + (sin(push * 1.7) * 2.0 if entry.has("image") else 0.0))
	portrait_rect.size = Vector2(width, tall)
	var band_top := view.y * 0.70
	var text_left := (x + width * 0.82) if side == "left" else view.x * 0.08
	var text_right := (view.x * 0.94) if side == "left" else (x + width * 0.18)
	line_label.position = Vector2(text_left, band_top + 44.0)
	line_label.size = Vector2(maxf(200.0, text_right - text_left), view.y - band_top - 52.0)
	var plate_size := name_plate.get_combined_minimum_size()
	name_plate.size = plate_size
	name_plate.position = Vector2(text_left, band_top + 4.0)

func draw_band() -> void:
	var view := band.size
	var top := view.y * 0.56
	if band_texture == null:
		var gradient := Gradient.new()
		gradient.set_color(0, Color(0.02, 0.016, 0.012, 0.0))
		gradient.set_color(1, Color(0.02, 0.016, 0.012, 0.84))
		gradient.add_point(0.45, Color(0.02, 0.016, 0.012, 0.62))
		band_texture = GradientTexture2D.new()
		band_texture.gradient = gradient
		band_texture.fill_from = Vector2(0, 0)
		band_texture.fill_to = Vector2(0, 1)
		band_texture.width = 4
		band_texture.height = 256
	band.draw_texture_rect(band_texture, Rect2(0, top, view.x, view.y - top), false)
