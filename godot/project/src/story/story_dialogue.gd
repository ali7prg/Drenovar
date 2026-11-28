extends Control
## Story dialogue over the map (story intro, chapter talks), build 1025.
##
## Cinematic: thin letterbox bars ease in, the speaker rises on its side over a coloured aura and a
## drift of smoke, the bottom of the figure melts into a deep band; an oak name plate with gold ends
## carries the name in the title face and the speaker's epithet below it; a gold flourish and a large
## faint quote mark open the line, which types in with a soft fade. Every speaker has an accent colour
## (the warden's embers, Tenerys's cold blue, the village's warm gold). The map stays visible above and
## between; hide_line() lets the speaker sink away and the bars open so the action reads again.
##
## Speakers are either painted portraits (PNG with alpha: the warden and Tenerys, the owner's art) or
## the game's own 3D model drawn larger in its own small world (villagers), waist-up, playing a talk clip.
## Deterministic: everything advances with tick(delta) (fixed-fps recordings).

const UiKit = preload("res://src/ui_kit.gd")
const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
const CHARS_PER_SECOND := 42.0
const SLIDE_SECONDS := 0.34
const BAR_SECONDS := 0.45
const BAR_SHARE := 0.055
const DEFAULT_ACCENT := Color("#e2b45a")

var portrait_view: SubViewport
var portrait_rect: TextureRect
var portrait_root: Node3D
var portrait_camera: Camera3D
var portrait_shader: ShaderMaterial
var medal_shader: ShaderMaterial
var aura: ColorRect
var aura_material: ShaderMaterial
var smoke: TextureRect
var band: ColorRect
var backdrop: ColorRect
var backdrop_material: ShaderMaterial
var bar_top: ColorRect
var bar_bottom: ColorRect
var name_plate: NinePatchRect
var name_label: Label
var epithet_label: Label
var flourish: TextureRect
var quote_mark: Label
var line_label: Label
var speakers: Dictionary = {}      # id -> {rig | image, name, epithet, accent, frame, talk, idle, options}
var current := ""
var side := "left"
var shown := 0.0                    # 0 hidden .. 1 shown (slide)
var want_shown := false
var bars := 0.0
var typed := 0.0
var line_text := ""
var push := 0.0
var talk_energy := 0.0
var accent := DEFAULT_ACCENT

func _init() -> void:
	name = "StoryDialogue"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	# The map behind a line goes softly out of focus (and a touch darker), back to sharp when it ends.
	backdrop = ColorRect.new()
	backdrop.name = "Backdrop"
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var blur := Shader.new()
	blur.code = """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float amount = 0.0;
void fragment() {
	float lod = 1.6 * amount;
	vec2 px = SCREEN_PIXEL_SIZE * 2.5 * amount;
	vec3 acc = textureLod(screen_tex, SCREEN_UV, lod).rgb * 0.36;
	acc += textureLod(screen_tex, SCREEN_UV + vec2(px.x, 0.0), lod).rgb * 0.16;
	acc += textureLod(screen_tex, SCREEN_UV - vec2(px.x, 0.0), lod).rgb * 0.16;
	acc += textureLod(screen_tex, SCREEN_UV + vec2(0.0, px.y), lod).rgb * 0.16;
	acc += textureLod(screen_tex, SCREEN_UV - vec2(0.0, px.y), lod).rgb * 0.16;
	float grey = dot(acc, vec3(0.299, 0.587, 0.114));
	acc = mix(acc, vec3(grey), 0.12 * amount) * mix(1.0, 0.84, amount);
	COLOR = vec4(acc, 1.0);
}
"""
	backdrop_material = ShaderMaterial.new()
	backdrop_material.shader = blur
	backdrop.material = backdrop_material
	add_child(backdrop)
	band = ColorRect.new()
	band.name = "Band"
	band.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var band_shader := Shader.new()
	band_shader.code = """
shader_type canvas_item;
// The dark band under the line: a smooth ease from clear (half height) to deep at the bottom,
// dithered (8-bit steps would show as stripes on a phone screen).
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	float t = clamp((UV.y - 0.48) / 0.52, 0.0, 1.0);
	float a = t * t * (3.0 - 2.0 * t) * 0.88;
	a += (hash(FRAGCOORD.xy) - 0.5) / 255.0;
	COLOR = vec4(0.016, 0.012, 0.009, clamp(a, 0.0, 1.0));
}
"""
	var band_material := ShaderMaterial.new()
	band_material.shader = band_shader
	band.material = band_material
	add_child(band)
	aura = ColorRect.new()
	aura.name = "Aura"
	aura.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var aura_shader := Shader.new()
	aura_shader.code = """
shader_type canvas_item;
// Soft radial glow behind the speaker, dithered so no rings show on dark maps.
uniform vec4 tint : source_color = vec4(1.0, 0.7, 0.3, 1.0);
uniform float strength = 0.5;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	// Gaussian core that reaches exactly zero before the rect's edges (no seam on the map).
	vec2 p = (UV - vec2(0.5, 0.62)) * vec2(1.0, 1.25);
	float r = length(p) * 2.0;
	float g = exp(-dot(p, p) * 7.0) * (1.0 - smoothstep(0.55, 0.98, r));
	float a = g * strength + (hash(FRAGCOORD.xy) - 0.5) / 255.0;
	COLOR = vec4(tint.rgb, clamp(a, 0.0, 1.0));
}
"""
	aura_material = ShaderMaterial.new()
	aura_material.shader = aura_shader
	aura.material = aura_material
	add_child(aura)
	smoke = TextureRect.new()
	smoke.name = "Smoke"
	smoke.mouse_filter = Control.MOUSE_FILTER_IGNORE
	smoke.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	smoke.stretch_mode = TextureRect.STRETCH_SCALE
	smoke.texture = UiKit.tex("kit_splash")
	add_child(smoke)
	portrait_view = SubViewport.new()
	portrait_view.name = "PortraitView"
	portrait_view.own_world_3d = true
	portrait_view.transparent_bg = true
	portrait_view.size = Vector2i(720, 720)
	portrait_view.msaa_3d = Viewport.MSAA_4X
	portrait_view.render_target_update_mode = SubViewport.UPDATE_DISABLED
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
	rim.light_energy = 0.8
	rim.light_color = Color("#a9c4ff")
	portrait_root.add_child(rim)
	portrait_camera = Camera3D.new()
	portrait_camera.fov = 26.0
	portrait_camera.current = true
	portrait_root.add_child(portrait_camera)
	portrait_rect = TextureRect.new()
	portrait_rect.name = "Portrait"
	portrait_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	portrait_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	portrait_rect.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	var shader := Shader.new()
	shader.code = """
shader_type canvas_item;
// The figure melts into the band: alpha fades over the lowest `fade` of the rect; a faint warm rim.
uniform float fade = 0.2;
uniform vec4 rim : source_color = vec4(1.0, 0.8, 0.5, 0.0);
void fragment() {
	vec4 c = texture(TEXTURE, UV);
	float bottom = smoothstep(1.0, 1.0 - fade, UV.y);
	c.rgb += rim.rgb * rim.a * c.a * smoothstep(0.55, 0.0, UV.y) * 0.25;
	COLOR = vec4(c.rgb, c.a * bottom);
}
"""
	portrait_shader = ShaderMaterial.new()
	portrait_shader.shader = shader
	var medal := Shader.new()
	medal.code = """
shader_type canvas_item;
// A village speaker in a round medallion: the bust inside a disc, a dark inner vignette, a gold ring.
uniform vec4 ring : source_color = vec4(0.9, 0.72, 0.36, 1.0);
uniform vec4 back : source_color = vec4(0.16, 0.11, 0.07, 0.92);
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	vec4 c = texture(TEXTURE, UV);
	vec3 inside = mix(back.rgb * (1.15 - r * 0.5), c.rgb, c.a);
	inside *= 1.0 - smoothstep(0.55, 0.9, r) * 0.45;
	float disc = 1.0 - smoothstep(0.86, 0.875, r);
	float band = smoothstep(0.855, 0.87, r) * (1.0 - smoothstep(0.95, 0.965, r));
	float bevel = 0.75 + 0.35 * (1.0 - (p.y + 1.0) * 0.5);
	vec3 gold = ring.rgb * bevel;
	vec3 col = mix(inside, gold, band);
	float alpha = max(disc * back.a, band) ;
	alpha = max(alpha, c.a * disc);
	COLOR = vec4(col, alpha * (1.0 - smoothstep(0.96, 0.975, r)));
}
"""
	medal_shader = ShaderMaterial.new()
	medal_shader.shader = medal
	portrait_rect.material = portrait_shader
	add_child(portrait_rect)
	bar_top = ColorRect.new()
	bar_top.color = Color(0.012, 0.01, 0.008, 0.94)
	bar_top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bar_top)
	bar_bottom = ColorRect.new()
	bar_bottom.color = Color(0.012, 0.01, 0.008, 0.94)
	bar_bottom.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bar_bottom)
	flourish = TextureRect.new()
	flourish.name = "Flourish"
	flourish.texture = UiKit.tex("kit_flourish")
	flourish.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	flourish.stretch_mode = TextureRect.STRETCH_SCALE
	flourish.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(flourish)
	name_plate = NinePatchRect.new()
	name_plate.name = "NamePlate"
	name_plate.texture = UiKit.tex("kit_strip")
	name_plate.patch_margin_left = 44
	name_plate.patch_margin_right = 44
	name_plate.patch_margin_top = 22
	name_plate.patch_margin_bottom = 22
	name_plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(name_plate)
	name_label = Label.new()
	name_label.add_theme_font_override("font", UiKit.TITLE_FONT)
	name_label.add_theme_font_size_override("font_size", 23)
	name_label.add_theme_color_override("font_color", UiKit.GOLD)
	name_label.add_theme_color_override("font_outline_color", Color("#1a0f06"))
	name_label.add_theme_constant_override("outline_size", 5)
	name_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	name_label.add_theme_constant_override("shadow_offset_y", 2)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	name_plate.add_child(name_label)
	epithet_label = Label.new()
	epithet_label.add_theme_font_override("font", UiKit.LABEL_FONT)
	epithet_label.add_theme_font_size_override("font_size", 15)
	epithet_label.add_theme_color_override("font_color", Color("#d9c39a"))
	epithet_label.add_theme_color_override("font_outline_color", Color("#120c07"))
	epithet_label.add_theme_constant_override("outline_size", 3)
	epithet_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(epithet_label)
	quote_mark = Label.new()
	quote_mark.text = "“"
	quote_mark.add_theme_font_override("font", UiKit.TITLE_FONT)
	quote_mark.add_theme_font_size_override("font_size", 92)
	quote_mark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(quote_mark)
	line_label = Label.new()
	line_label.name = "Line"
	line_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line_label.add_theme_font_override("font", UiKit.BODY_FONT)
	line_label.add_theme_font_size_override("font_size", 25)
	line_label.add_theme_constant_override("line_spacing", 4)
	line_label.add_theme_color_override("font_color", UiKit.IVORY)
	line_label.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.02, 0.9))
	line_label.add_theme_constant_override("outline_size", 4)
	line_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.75))
	line_label.add_theme_constant_override("shadow_offset_x", 1)
	line_label.add_theme_constant_override("shadow_offset_y", 3)
	line_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(line_label)
	modulate.a = 0.0

## Registers a 3D speaker: the model is loaded now (blocking) so its first line has no pop-in.
## frame: {"yaw", "lateral"} (height and distance are fitted from the model's bounds).
## style: {"epithet": String, "accent": Color}.
func add_speaker(id: String, display_name: String, path: String, frame: Dictionary, talk: Array, idle: Array,
		model_scale := 1.0, species := "", level := 1, setup_rig := Callable(), style: Dictionary = {}) -> void:
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
	speakers[id] = {"rig": rig, "name": display_name, "frame": frame, "talk": talk, "idle": idle,
		"epithet": String(style.get("epithet", "")), "accent": style.get("accent", DEFAULT_ACCENT)}

## Registers a speaker drawn from a painted portrait (background removed, PNG with alpha).
## options: {"height": share of the screen height, "faces": "right" | "left" (where the figure looks in
## the picture; it is mirrored to look into the screen), "edge": screen share kept free at the side,
## "inset": share of the figure's width the text column may overlap from its far side (0.86),
## "epithet": String, "accent": Color}.
func add_image_speaker(id: String, display_name: String, texture_path: String, options: Dictionary = {}) -> void:
	var texture: Texture2D = load(texture_path) if ResourceLoader.exists(texture_path) else null
	if texture == null:
		push_warning("StoryDialogue: portrait missing " + texture_path)
		return
	speakers[id] = {"image": texture, "name": display_name, "options": options, "talk": [], "idle": [],
		"epithet": String(options.get("epithet", "")), "accent": options.get("accent", DEFAULT_ACCENT)}

## Frames a 3D speaker from its real bounds: humans waist-up (eyes at ~0.93 of the height), a beast
## head and chest.
func fit_frame(rig: Rig, frame: Dictionary, beast: bool) -> Dictionary:
	if rig.model == null:
		return frame
	var box := AABB()
	var first := true
	for mesh: MeshInstance3D in rig.model.find_children("*", "MeshInstance3D", true, false):
		if not mesh.visible or mesh.mesh == null or String(mesh.name).to_lower().contains("lod1") or String(mesh.name).to_lower().contains("lod2"):
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
		# The medallion frames head and shoulders round the Head bone (bounds can include bags or hair cards).
		var head_y := height * 0.9
		for skeleton: Skeleton3D in rig.model.find_children("*", "Skeleton3D", true, false):
			var bone := skeleton.find_bone("Head")
			if bone >= 0:
				head_y = (skeleton.global_transform * skeleton.get_bone_global_pose(bone)).origin.y
				break
		fitted["height"] = head_y + 0.06 * head_y / 1.55
		fitted["look"] = head_y - 0.1 * head_y / 1.55
		fitted["distance"] = 0.95 * head_y / 1.55
	return fitted

## Shows `text` said by `speaker_id` on `on_side` ("left" | "right").
func show_line(speaker_id: String, text: String, on_side := "left") -> void:
	if not speakers.has(speaker_id):
		return
	var changed := speaker_id != current or on_side != side or not want_shown
	if changed:
		for id in speakers:
			if speakers[id].has("rig"):
				(speakers[id].rig as Rig).visible = id == speaker_id
		if shown > 0.0 and (on_side != side or speaker_id != current):
			shown = 0.0
		current = speaker_id
		side = on_side
		push = 0.0
	var entry: Dictionary = speakers[speaker_id]
	accent = entry.get("accent", DEFAULT_ACCENT)
	if entry.has("image"):
		portrait_rect.material = portrait_shader
		portrait_rect.texture = entry.image
		portrait_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT
		var faces := String(entry.options.get("faces", "right"))
		portrait_rect.flip_h = (on_side == "right") == (faces == "right")
		portrait_view.render_target_update_mode = SubViewport.UPDATE_DISABLED
	else:
		portrait_rect.material = medal_shader
		medal_shader.set_shader_parameter("ring", accent.lerp(Color("#e8c27a"), 0.55))
		portrait_rect.texture = portrait_view.get_texture()
		portrait_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		portrait_rect.flip_h = false
		portrait_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		(entry.rig as Rig).play(entry.talk, 0.2)
	portrait_shader.set_shader_parameter("rim", Color(accent.r, accent.g, accent.b, 0.9))
	aura_material.set_shader_parameter("tint", accent)
	smoke.modulate = Color(accent.r * 0.18, accent.g * 0.14, accent.b * 0.12, 0.55)
	quote_mark.add_theme_color_override("font_color", Color(accent.r, accent.g, accent.b, 0.42))
	flourish.modulate = accent.lerp(Color.WHITE, 0.15)
	name_label.text = String(entry.name).to_upper()
	epithet_label.text = String(entry.get("epithet", ""))
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

## Voice loudness 0..1 of the current line.
func set_energy(value: float) -> void:
	talk_energy = value

func tick(delta: float) -> void:
	var target := 1.0 if want_shown else 0.0
	shown = move_toward(shown, target, delta / SLIDE_SECONDS)
	bars = move_toward(bars, target, delta / BAR_SECONDS)
	modulate.a = smoothstep(0.0, 1.0, maxf(shown, bars * 0.999))
	backdrop_material.set_shader_parameter("amount", smoothstep(0.0, 1.0, bars))
	typed += delta * CHARS_PER_SECOND
	line_label.visible_characters = int(typed) if typed < line_text.length() else -1
	push += delta
	if current != "" and speakers.has(current) and speakers[current].has("rig"):
		var entry: Dictionary = speakers[current]
		var frame: Dictionary = entry.frame
		var height := float(frame.get("height", 1.55))
		var distance := float(frame.get("distance", 2.2)) * (1.0 - 0.045 * minf(push / 4.0, 1.0))
		var lateral := float(frame.get("lateral", 0.0)) * (1.0 if side == "left" else -1.0)
		var look := float(frame.get("look", height - 0.22))
		portrait_camera.position = Vector3(lateral, height, distance)
		portrait_camera.look_at(Vector3(lateral * 0.35, look, 0.0), Vector3.UP)
		var rig: Rig = entry.rig
		rig.rotation.y = float(frame.get("yaw", -0.42)) * (1.0 if side == "left" else -1.0)
	layout_now()

## Layout (the 1366×630 canvas, scaled with the screen): bars at the top and the bottom; the speaker on
## its side standing on the bottom edge; aura and smoke behind it; the plate, the epithet, the flourish,
## the quote mark and the line on the other side of the band.
func layout_now() -> void:
	var view := size
	if view.x <= 0.0:
		return
	var bar := view.y * BAR_SHARE * smoothstep(0.0, 1.0, bars)
	bar_top.position = Vector2.ZERO
	bar_top.size = Vector2(view.x, bar)
	bar_bottom.position = Vector2(0, view.y - bar)
	bar_bottom.size = Vector2(view.x, bar)
	var entry: Dictionary = speakers.get(current, {})
	var width := view.y * 0.42
	var tall := width
	var edge := 0.045
	var medallion := not entry.has("image")
	if entry.has("image"):
		var texture: Texture2D = entry.image
		var aspect := float(texture.get_width()) / maxf(1.0, float(texture.get_height()))
		tall = view.y * float(entry.options.get("height", 0.92))
		width = minf(tall * aspect, view.x * 0.5)
		tall = width / aspect
		edge = float(entry.options.get("edge", 0.0))
	var ease := smoothstep(0.0, 1.0, shown)
	var slide := (1.0 - ease) * width * 0.22
	var rise := (1.0 - ease) * tall * 0.06
	var x := (view.x * edge - slide) if side == "left" else (view.x * (1.0 - edge) - width + slide)
	var top := view.y - tall + rise
	if medallion:
		top = view.y * 0.6 - tall * 0.5 + rise
	# A portrait breathes: a slow push-in from its feet and a small rise and fall.
	var grow := 1.0 + 0.035 * minf(push / 5.0, 1.0)
	portrait_rect.pivot_offset = Vector2(width * 0.5, tall)
	portrait_rect.scale = Vector2(grow, grow)
	portrait_rect.position = Vector2(x, top + sin(push * 1.7) * 1.6)
	portrait_rect.size = Vector2(width, tall)
	portrait_rect.modulate.a = ease
	portrait_shader.set_shader_parameter("fade", 0.16)
	if medallion:
		portrait_rect.scale = Vector2.ONE * (0.94 + 0.06 * ease)
	var aura_size := Vector2(width * 1.35, tall * 1.05) if not medallion else Vector2(width * 1.7, tall * 1.7)
	aura.size = aura_size
	aura.position = Vector2(x + width * 0.5 - aura_size.x * 0.5, view.y - aura_size.y * 0.98) if not medallion \
		else Vector2(x + width * 0.5, top + tall * 0.5) - aura_size * Vector2(0.5, 0.62)
	aura_material.set_shader_parameter("strength", 0.42 * ease)
	var smoke_size := Vector2(width * 1.5, tall * 0.62)
	smoke.size = smoke_size
	smoke.position = Vector2(x + width * 0.5 - smoke_size.x * 0.5 + sin(push * 0.35) * 8.0, view.y - smoke_size.y * 0.78)
	smoke.modulate.a = (0.55 if not medallion else 0.0) * ease
	# The text column: on the other side of the band, never under the figure.
	var inset := 0.86 if not medallion else 1.06
	if entry.has("image"):
		inset = float(entry.options.get("inset", inset))
	var column_left := (x + width * inset) if side == "left" else view.x * 0.07
	var column_right := (view.x * 0.95) if side == "left" else (x + width * (1.0 - inset))
	column_left = maxf(column_left, view.x * 0.06)
	column_right = minf(column_right, view.x * 0.95)
	var column := maxf(260.0, column_right - column_left)
	column = minf(column, view.x * 0.52)
	if side == "right":
		column_left = maxf(view.x * 0.06, column_right - column)
	var band_top := view.y * 0.66
	var plate_height := 46.0
	var plate_width := maxf(200.0, UiKit.TITLE_FONT.get_string_size(name_label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 23).x + 96.0)
	var fly := (1.0 - ease) * 14.0
	name_plate.position = Vector2(column_left - 10.0, band_top + fly)
	name_plate.size = Vector2(plate_width, plate_height)
	name_label.position = Vector2(0, 0)
	name_label.size = name_plate.size
	epithet_label.position = Vector2(column_left + plate_width + 4.0, band_top + 13.0 + fly)
	epithet_label.size = Vector2(maxf(10.0, column - plate_width), 24)
	flourish.position = Vector2(column_left, band_top + plate_height + 4.0 + fly)
	flourish.size = Vector2(minf(column * 0.62, 300.0), 22.0)
	quote_mark.position = Vector2(column_left - 30.0, band_top + plate_height + 6.0 + fly)
	quote_mark.size = Vector2(60, 90)
	line_label.position = Vector2(column_left + 14.0, band_top + plate_height + 26.0 + fly)
	line_label.size = Vector2(column - 14.0, view.y - (band_top + plate_height + 26.0) - view.y * BAR_SHARE - 4.0)
	line_label.modulate.a = ease

func draw_band() -> void:
	pass
