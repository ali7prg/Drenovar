extends Node
## Hall III unlock presentation (data/unlock-intro.json, docs/HALL3_UNLOCK_AND_INTRO_RU.md).
## * Offered once (intro.offer) and only at a safe moment: city view, foreground, no modal,
##   no loading, no battle. Otherwise deferred.
## * start_intro → 12 s: soft cue + banner «Лес потерянных открыт» → camera glides (existing
##   orthographic city camera: target/zoom only) to the northern entrance, the entrance
##   corridor fog opens in 1200 ms → Iskra walks out, stops, looks back → explanation;
##   camera returns at 12 s; the text stays until the player acts.
## * «Следовать за лошадью» → finish_intro, then the player chooses squad/route (no march).
##   «Пропустить» → skip_intro (always available). «Позже» → defer_intro.
## * Reduced motion: one static card with the same text, no camera motion.
## * Voluntary replay (hall ≥ 3) is local; it sends nothing. Nothing here awards anything.

const Style = preload("res://src/forest_rescue/game/hud_style.gd")
const Art = preload("res://src/forest_rescue/game/hud_art.gd")
const ENTRANCE := Vector3(-10.0, 0.0, -57.5)
const HORSE_FROM := Vector2(-13.6, -62.0)
const HORSE_TO := Vector2(-8.0, -55.0)

var game: Node
var mode := ""
var elapsed := 0.0
var requested := false
var replaying := false
var camera_home := {}
var camera_user_took := false
var reveal_started := false
var horse_started := false
var shown_lines: Dictionary = {}
var card: Control
var card_text: Label
var card_note: Label
var follow_button: Button
var skip_button: Button
var later_button: Button
var static_card: PanelContainer
var glow: Node3D
var prompt_ready := false
var invite_reason := ""

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "IntroDirector"
	build_card()
	build_static_card()

func t(key: String, args := {}) -> String:
	return game.content.text(key, args)

func presenting() -> bool:
	return mode in ["animated", "static", "waiting"]

func intro_state() -> Dictionary:
	return game.client.adv.get("intro", {})

func safe() -> bool:
	var main: Node = game.main
	if not game.city_active() or not game.foreground or main.modal.visible or main.scene_loading or not game.world_ready():
		return false
	if main.result_open or main.result_notice.visible:
		return false
	var fight: Dictionary = game.client.battle()
	if not fight.is_empty() and String(fight.get("outcome", "pending")) == "pending":
		return false
	for army in main.state.get("armies", []):
		if String(army.get("status", "")) == "fighting":
			return false
	return true

## Called on every new state and every frame; starts the offered intro once when safe.
func evaluate() -> void:
	refresh_invite()
	if presenting() or requested or not game.client.unlocked():
		return
	var intro := intro_state()
	if String(intro.get("status", "")) == "pending" and bool(intro.get("offer", false)) and not bool(intro.get("deferred", false)) and safe():
		start_offered()

func refresh_invite() -> void:
	var hud: Control = game.hud
	var intro := intro_state()
	var status := String(intro.get("status", "acknowledged"))
	var show: bool = game.client.unlocked() and game.world_ready() and not presenting() and status != "acknowledged" and (bool(intro.get("deferred", false)) or status == "playing" or not bool(intro.get("offer", true)))
	if show:
		hud.invite_button.text = t("intro.continue") if status == "playing" else t("intro.start")
	if hud.invite_button.visible != show:
		hud.invite_button.visible = show
		hud.layout()

func invite_pressed() -> void:
	if presenting() or requested:
		return
	var status := String(intro_state().get("status", ""))
	if status == "pending":
		start_offered()
	elif status == "playing":
		begin(false)

func start_offered() -> void:
	requested = true
	mode = "waiting"
	var fields := {"reducedMotion":true} if game.reduced_motion else {}
	var result: Dictionary = await game.request_action("start_intro", fields, "adventure_intro")
	requested = false
	if not bool(result.get("ok", false)):
		mode = ""
		return
	if mode == "waiting":
		begin(false)

func on_intro_present(_event: Dictionary) -> void:
	if mode == "waiting":
		begin(false)

func replay() -> void:
	if presenting():
		return
	begin(true)

func begin(local_replay: bool) -> void:
	replaying = local_replay
	elapsed = 0.0
	reveal_started = false
	horse_started = false
	prompt_ready = false
	camera_user_took = false
	shown_lines.clear()
	game.main.close_modal()
	game.hud.hide_locked()
	var stage: Node3D = game.main.stage
	camera_home = {"target":stage.target, "zoom":stage.zoom} if is_instance_valid(stage) and game.main.map_name == "city" else {}
	if game.reduced_motion:
		mode = "static"
		game.world_call("set_reduced_motion", [true])
		if not replaying:
			game.world_call("play_entrance_reveal", [0])
		show_static_card()
		game.audio.play_cue("fr_artifact_discovery")
		return
	mode = "animated"
	game.audio.play_cue("fr_artifact_discovery")
	game.hud.show_banner(t("forest.unlocked.title"), "", 0.0)
	show_hall_glow(true)
	set_line("", false)

func tick(delta: float) -> void:
	evaluate()
	if mode != "animated":
		return
	elapsed += delta
	var stage: Node3D = game.main.stage
	var main: Node = game.main
	if not main.fingers.is_empty() or main.dragging:
		camera_user_took = true
	if is_instance_valid(stage) and not camera_user_took and not camera_home.is_empty():
		if elapsed >= 2.0 and elapsed < 10.0:
			var f := smoothstep(2.0, 4.6, elapsed)
			stage.target = (camera_home.target as Vector3).lerp(entrance_target(), f)
			stage.zoom = lerpf(float(camera_home.zoom), 40.0, f)
		elif elapsed >= 10.0:
			var back := smoothstep(10.0, 12.0, elapsed)
			stage.target = entrance_target().lerp(camera_home.target, back)
			stage.zoom = lerpf(40.0, float(camera_home.zoom), back)
	if elapsed >= 2.0 and not shown_lines.has("line1"):
		shown_lines.line1 = true
		game.hud.hide_banner()
		show_hall_glow(false)
		set_line(t("intro.line1"), false)
	if elapsed >= 2.6 and not reveal_started:
		reveal_started = true
		if not replaying:
			game.world_call("play_entrance_reveal", [1200])
	if elapsed >= 5.0 and not horse_started:
		horse_started = true
		set_line(t("intro.line2"), false)
		var from: Vector3 = game.ground(HORSE_FROM.x, HORSE_FROM.y)
		var to: Vector3 = game.target_position("lf_horse_origin")
		if to == Vector3.INF:
			to = game.ground(HORSE_TO.x, HORSE_TO.y)
		# 1024: she walks out of the mist onto a spot no wall or tower hides from the camera, ~7 m.
		var spots: Dictionary = game.actors.horse_origin_spots()
		if not spots.is_empty():
			to = spots.horse
			var start: Vector3 = to + (spots.out as Vector3) * 7.0
			from = game.ground(start.x, start.z)
		game.actors.start_intro_horse(from, to, 3.2)
	if elapsed >= 8.0 and not shown_lines.has("line3"):
		shown_lines.line3 = true
		set_line(t("intro.line3"), true)
	if elapsed >= 12.0 and not prompt_ready:
		prompt_ready = true
		game.actors.stop_intro_horse()

func entrance_target() -> Vector3:
	var spots: Dictionary = game.actors.horse_origin_spots()
	if not spots.is_empty():
		# Framing: the spot she stops on and the mist she comes out of (3 m into it), above the card.
		var spot: Vector3 = spots.horse
		return spot + (spots.out as Vector3) * 3.0 + Vector3(0.0, 0.0, 0.0)
	var p: Vector3 = game.target_position("lf_horse_origin")
	if p == Vector3.INF:
		p = ENTRANCE
	return Vector3(p.x - 2.0, p.y, p.z - 2.5)

# ------------------------------------------------------------------ prompt card (art/18 right)
func build_card() -> void:
	card = Control.new()
	card.name = "IntroPrompt"
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	card.offset_top = -262
	card.offset_bottom = 0
	game.hud.add_child(card)
	var shade := TextureRect.new()
	shade.name = "Shade"
	var gradient := Gradient.new()
	gradient.set_color(0, Color(0.03, 0.03, 0.025, 0.0))
	gradient.set_color(1, Color(0.03, 0.03, 0.025, 0.82))
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill_from = Vector2(0, 0)
	texture.fill_to = Vector2(0, 1)
	texture.width = 8
	texture.height = 128
	shade.texture = texture
	shade.stretch_mode = TextureRect.STRETCH_SCALE
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(shade)
	var column := VBoxContainer.new()
	column.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	column.offset_left = -330
	column.offset_right = 330
	column.offset_top = -244
	column.offset_bottom = -14
	column.alignment = BoxContainer.ALIGNMENT_END
	column.add_theme_constant_override("separation", 8)
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(column)
	card_text = Style.label("", 24, Style.IVORY, true, 5)
	card_text.name = "IntroLine"
	card_text.add_theme_font_override("font", Style.italic())
	card_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	card_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(card_text)
	card_note = Style.label("", 16, Color("#e8d9b8"), false, 4)
	card_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	card_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(card_note)
	var ornament := Art.new("ornament", Vector2(300, 14))
	ornament.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(ornament)
	follow_button = Button.new()
	follow_button.name = "IntroFollow"
	follow_button.text = t("intro.follow")
	follow_button.custom_minimum_size = Vector2(390, 56)
	follow_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	follow_button.add_theme_font_override("font", Style.TITLE_FONT)
	follow_button.add_theme_font_size_override("font_size", 24)
	Style.apply_button(follow_button, "red")
	follow_button.pressed.connect(on_follow)
	column.add_child(follow_button)
	var links := HBoxContainer.new()
	links.alignment = BoxContainer.ALIGNMENT_CENTER
	links.add_theme_constant_override("separation", 34)
	links.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(links)
	skip_button = link_button("IntroSkip", t("intro.skip"), on_skip)
	links.add_child(skip_button)
	later_button = link_button("IntroLater", t("intro.later"), on_later)
	links.add_child(later_button)
	card.hide()

func link_button(id: String, caption: String, action: Callable) -> Button:
	var control := Button.new()
	control.name = id
	control.text = caption
	control.flat = true
	control.custom_minimum_size = Vector2(120, 48)
	control.add_theme_font_override("font", Style.TITLE_FONT)
	control.add_theme_font_size_override("font_size", 17)
	control.add_theme_color_override("font_color", Color("#efe2c6"))
	control.add_theme_color_override("font_hover_color", Color.WHITE)
	control.pressed.connect(action)
	control.draw.connect(func():
		var font := control.get_theme_font("font")
		var width := font.get_string_size(caption, HORIZONTAL_ALIGNMENT_LEFT, -1, 17).x
		var y := control.size.y * 0.5 + 11.0
		control.draw_line(Vector2((control.size.x - width) * 0.5, y), Vector2((control.size.x + width) * 0.5, y), Color("#d9c9a4"), 1.0))
	return control

func draw_card_shade() -> void:
	var rect := Rect2(Vector2.ZERO, card.size)
	var steps := 24
	for i in steps:
		var a := float(i) / steps
		card.draw_rect(Rect2(0, rect.size.y * a, rect.size.x, rect.size.y / steps + 1.0), Color(0.03, 0.03, 0.025, 0.72 * a * a))

func set_line(value: String, final_line: bool) -> void:
	card.show()
	card_text.text = value
	card_text.visible = not value.is_empty()
	card_note.text = t("intro.rewardsNote") if final_line else ""
	card_note.visible = final_line
	follow_button.visible = final_line
	follow_button.text = t("button.close") if replaying else t("intro.follow")
	later_button.visible = not replaying
	skip_button.visible = true
	card.queue_redraw()
	if not value.is_empty():
		card_text.modulate.a = 0.0
		create_tween().tween_property(card_text, "modulate:a", 1.0, 0.45)

# ------------------------------------------------------------------ static cards (reduced motion)
func build_static_card() -> void:
	static_card = PanelContainer.new()
	static_card.name = "IntroStaticCard"
	static_card.add_theme_stylebox_override("panel", Style.slate_card())
	static_card.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	static_card.offset_left = -330
	static_card.offset_right = 330
	static_card.offset_top = -250
	static_card.offset_bottom = 250
	game.hud.add_child(static_card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	static_card.add_child(column)
	var medal := Art.new("medallion", Vector2(180, 52))
	medal.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(medal)
	var heading := Style.title(t("forest.unlocked.title"), 28)
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(heading)
	var horse := Art.new("horse", Vector2(150, 92))
	horse.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(horse)
	for key in ["intro.line1", "intro.line2", "intro.line3"]:
		var line := Style.label(t(key), 18, Color("#efe2c6"), true)
		line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		column.add_child(line)
	var note := Style.label(t("intro.rewardsNote"), 15, Color("#e9cf95"), true)
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(note)
	var follow := Button.new()
	follow.name = "StaticFollow"
	follow.text = t("intro.follow")
	follow.custom_minimum_size = Vector2(360, 54)
	follow.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	follow.add_theme_font_override("font", Style.TITLE_FONT)
	follow.add_theme_font_size_override("font_size", 22)
	Style.apply_button(follow, "red")
	follow.pressed.connect(on_follow)
	column.add_child(follow)
	var links := HBoxContainer.new()
	links.alignment = BoxContainer.ALIGNMENT_CENTER
	links.add_theme_constant_override("separation", 30)
	column.add_child(links)
	links.add_child(link_button("StaticSkip", t("intro.skip"), on_skip))
	links.add_child(link_button("StaticLater", t("intro.later"), on_later))
	static_card.hide()

func show_static_card() -> void:
	static_card.show()
	var follow: Button = static_card.find_child("StaticFollow", true, false)
	follow.text = t("button.close") if replaying else t("intro.follow")
	var later: Button = static_card.find_child("StaticLater", true, false)
	later.visible = not replaying

# ------------------------------------------------------------------ actions
func finish_presentation() -> void:
	mode = ""
	card.hide()
	static_card.hide()
	game.hud.hide_banner()
	show_hall_glow(false)
	game.actors.stop_intro_horse()
	var stage: Node3D = game.main.stage
	if is_instance_valid(stage) and not camera_home.is_empty() and not camera_user_took:
		stage.target = camera_home.target
		stage.zoom = camera_home.zoom
	camera_home = {}
	if game.world != null:
		game.world_call("set_reduced_motion", [game.reduced_motion])
	refresh_invite()

func on_follow() -> void:
	var was_replay := replaying
	finish_presentation()
	if was_replay:
		return
	await game.wait_idle()
	var attempt := int(intro_state().get("attempt", 0))
	var result: Dictionary = await game.request_action("finish_intro", {"attempt":attempt} if attempt > 0 else {}, "adventure_intro")
	if not bool(result.get("ok", false)) and String(intro_state().get("status", "")) == "playing":
		return
	# The player now chooses the squad and the route; nothing marches automatically.
	if game.total_units(game.client.squad().get("units", {})) <= 0:
		game.panels.open_squad()
	else:
		game.panels.open_route()

func on_skip() -> void:
	var was_replay := replaying
	finish_presentation()
	if not was_replay:
		await game.request_action("skip_intro", {}, "adventure_intro")

func on_later() -> void:
	finish_presentation()
	await game.request_action("defer_intro", {}, "adventure_intro")
	refresh_invite()

## App went to background mid-presentation: stop, never auto-replay; offer «Продолжить вступление».
func on_background() -> void:
	if mode in ["animated", "static"]:
		finish_presentation()

func show_hall_glow(on: bool) -> void:
	var root: Node3D = game.actors_root()
	if not on:
		if is_instance_valid(glow):
			glow.queue_free()
		glow = null
		return
	if root == null or is_instance_valid(glow):
		return
	var hall := Vector3.INF
	for marker in game.stage.place_markers:
		if game.main.building_definition(marker.item.type).get("base", "") == "ECO-05":
			hall = marker.position - Vector3(0, 5, 0)
	if hall == Vector3.INF:
		return
	glow = Node3D.new()
	glow.name = "HallGlow"
	var halo := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(16, 16)
	var gradient := Gradient.new()
	gradient.set_color(0, Color(1.0, 0.86, 0.5, 0.85))
	gradient.set_color(1, Color(1.0, 0.7, 0.3, 0.0))
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(0.5, 0.0)
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	material.albedo_texture = texture
	material.no_depth_test = true
	quad.material = material
	halo.mesh = quad
	halo.position = Vector3(0, 7, 0)
	halo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	glow.add_child(halo)
	var light := OmniLight3D.new()
	light.light_color = Color("#ffd27a")
	light.light_energy = 3.0
	light.omni_range = 12.0
	light.position = Vector3(0, 6, 0)
	glow.add_child(light)
	root.add_child(glow)
	glow.global_position = hall
	var tween := glow.create_tween().set_loops(3)
	tween.tween_property(light, "light_energy", 1.2, 0.6)
	tween.tween_property(light, "light_energy", 3.0, 0.6)
