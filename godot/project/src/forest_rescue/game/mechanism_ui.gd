extends Control
## Four mechanism interfaces (art/10_artifact_mechanisms): trail cache (tap landmarks on the
## map or the list), rune lock (three concentric rings), winch (brake → pawl → raise),
## paired latch (occupy both plates, then the centre latch). Every input is one
## `mechanism_input` command; the server decides ok/wrong. A wrong input shows a reset
## (shake, rings spin back, chest drops) and the authored text «mechanism.wrong».

const Style = preload("res://src/forest_rescue/game/hud_style.gd")
const Art = preload("res://src/forest_rescue/game/hud_art.gd")

var game: Node
var site_id := ""
var kind := ""
var panel: PanelContainer
var eyebrow: Label
var title: Label
var clue: Label
var dots: Control
var count_label: Label
var widget: Control
var inputs: HFlowContainer
var feedback: Label
var occupy_button: Button
var recover_button: Button
var close_button: Button
var open_flag := false
var shake := 0.0
var flash := 0.0
var flash_color := Color.TRANSPARENT
var reset_spin := 0.0
var sending := false
var plates_occupied := false
var last_progress := 0
var symbols: Array = []
var solution: Array = []
var previous_camera := {}
var pending_landmark := ""

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "ForestMechanism"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel = PanelContainer.new()
	panel.name = "MechanismPanel"
	panel.add_theme_stylebox_override("panel", Style.dark_panel())
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.set_anchors_and_offsets_preset(Control.PRESET_LEFT_WIDE)
	panel.offset_left = 48
	panel.offset_top = 70
	panel.offset_right = 48 + 430
	panel.offset_bottom = -20
	add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	panel.add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var titles := VBoxContainer.new()
	titles.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	titles.add_theme_constant_override("separation", 0)
	header.add_child(titles)
	eyebrow = Style.label("", 14, Color("#e9cf95"), true)
	titles.add_child(eyebrow)
	title = Style.title("", 24)
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	titles.add_child(title)
	close_button = Button.new()
	close_button.name = "MechanismClose"
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(44, 44)
	close_button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	Style.close_style(close_button)
	close_button.tooltip_text = game.content.text("button.close")
	close_button.accessibility_name = game.content.text("button.close")
	close_button.pressed.connect(close)
	header.add_child(close_button)
	var clue_box := PanelContainer.new()
	clue_box.add_theme_stylebox_override("panel", Style.parchment())
	column.add_child(clue_box)
	clue = Style.label("", 17, Style.PARCHMENT_INK, true)
	clue.name = "MechanismClue"
	clue.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	clue_box.add_child(clue)
	var progress := HBoxContainer.new()
	progress.alignment = BoxContainer.ALIGNMENT_CENTER
	progress.add_theme_constant_override("separation", 10)
	column.add_child(progress)
	dots = Control.new()
	dots.custom_minimum_size = Vector2(110, 22)
	dots.draw.connect(draw_dots)
	progress.add_child(dots)
	count_label = Style.label("", 18, Style.GOLD, true, 3)
	progress.add_child(count_label)
	widget = Control.new()
	widget.name = "MechanismWidget"
	widget.custom_minimum_size = Vector2(380, 196)
	widget.size_flags_vertical = Control.SIZE_EXPAND_FILL
	widget.mouse_filter = Control.MOUSE_FILTER_STOP
	widget.draw.connect(draw_widget)
	widget.gui_input.connect(widget_input)
	column.add_child(widget)
	inputs = HFlowContainer.new()
	inputs.name = "MechanismInputs"
	inputs.alignment = FlowContainer.ALIGNMENT_CENTER
	inputs.add_theme_constant_override("h_separation", 6)
	inputs.add_theme_constant_override("v_separation", 6)
	column.add_child(inputs)
	feedback = Style.label("", 16, Color("#ffd49a"))
	feedback.name = "MechanismFeedback"
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	feedback.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(feedback)
	var footer := HBoxContainer.new()
	footer.alignment = BoxContainer.ALIGNMENT_CENTER
	footer.add_theme_constant_override("separation", 8)
	column.add_child(footer)
	occupy_button = Button.new()
	occupy_button.name = "OccupyPlates"
	occupy_button.text = game.content.text("hud.occupy")
	occupy_button.custom_minimum_size = Vector2(0, 48)
	Style.apply_button(occupy_button, "leather")
	occupy_button.pressed.connect(occupy)
	footer.add_child(occupy_button)
	recover_button = Button.new()
	recover_button.name = "RecoverSeal"
	recover_button.text = game.content.text("button.recover")
	recover_button.custom_minimum_size = Vector2(0, 48)
	Style.apply_button(recover_button, "gold")
	recover_button.pressed.connect(recover)
	footer.add_child(recover_button)
	hide()

func is_open() -> bool:
	return open_flag

func mechanism() -> Dictionary:
	return game.client.poi(site_id).get("mechanism", {})

func plates_state() -> String:
	var plates: Variant = mechanism().get("plates")
	return String(plates.get("state", "free")) if plates is Dictionary else "free"

func observed(symbol: String) -> bool:
	return (mechanism().get("observed", []) as Array).has(symbol)

func open(target_site: String) -> void:
	if target_site.is_empty():
		return
	site_id = target_site
	var site: Dictionary = game.content.site(site_id)
	var poi: Dictionary = game.client.poi(site_id)
	kind = String(poi.get("variation", mechanism().get("kind", site.get("variation", ""))))
	solution = site.get("artifact", {}).get("puzzle", {}).get("solution", [])
	symbols = []
	for value in mechanism().get("symbols", []):
		if String(value) != "..." and not symbols.has(String(value)):
			symbols.append(String(value))
	if symbols.is_empty():
		symbols = solution.duplicate()
		var seed := int(site.get("number", 1))
		for i in symbols.size():
			var j := (i * 7 + seed * 3) % symbols.size()
			var swap = symbols[i]
			symbols[i] = symbols[j]
			symbols[j] = swap
	if kind == "winch_sequence":
		symbols = ["brake", "pawl", "raise"]
	elif kind == "paired_latch":
		symbols = ["left_plate", "right_plate", "center_latch"]
	eyebrow.text = String(site.get("artifact", {}).get("name", "")).to_upper()
	title.text = String(site.get("name", ""))
	clue.text = String(site.get("artifact", {}).get("puzzle", {}).get("clue", game.content.text("artifact.missing")))
	feedback.text = game.content.text("mechanism.paired") if kind == "paired_latch" else ""
	last_progress = int(mechanism().get("progress", 0))
	plates_occupied = plates_state() == "held"
	pending_landmark = ""
	build_inputs()
	open_flag = true
	show()
	panel.modulate.a = 0.0
	create_tween().tween_property(panel, "modulate:a", 1.0, 0.18)
	focus_camera()
	refresh()

func close() -> void:
	open_flag = false
	hide()
	restore_camera()

func focus_camera() -> void:
	var stage: Node3D = game.stage
	if not is_instance_valid(stage):
		return
	previous_camera = {"target":stage.target, "zoom":stage.zoom}
	var spot: Vector3 = game.site_anchor(site_id).get("artifact", game.target_position(site_id))
	if game.get("actors") != null and game.actors.has_method("device_focus"):
		spot = game.actors.device_focus(site_id)      # the device itself (the winch stands clear of its cage)
	if spot == Vector3.INF:
		return
	var zoom := 24.0 if kind in ["trail_cache", "winch_sequence"] else 28.0
	var view := get_viewport_rect().size
	var right := Vector3(1, 0, -1).normalized()
	var shift := (view.x * 0.18) * zoom / maxf(view.y, 1.0)
	stage.target = spot - right * shift
	stage.zoom = zoom

func restore_camera() -> void:
	var stage: Node3D = game.stage
	if is_instance_valid(stage) and not previous_camera.is_empty():
		stage.target = previous_camera.target
		stage.zoom = previous_camera.zoom
	previous_camera = {}

func build_inputs() -> void:
	for child in inputs.get_children():
		child.queue_free()
	for symbol in symbols:
		var control := Button.new()
		control.name = "Symbol_" + String(symbol)
		control.text = game.content.symbol_label(String(symbol))
		control.custom_minimum_size = Vector2(0, 46)
		control.add_theme_font_size_override("font_size", 16)
		Style.apply_button(control, "leather")
		control.pressed.connect(send_symbol.bind(String(symbol)))
		inputs.add_child(control)

func refresh() -> void:
	var state := mechanism()
	var progress := int(state.get("progress", 0))
	var length := maxi(1, int(state.get("length", 3)))
	var solved := bool(state.get("solved", false))
	var found := String(game.client.poi(site_id).get("artifact", {}).get("state", "hidden")) != "hidden"
	count_label.text = "%d / %d" % [length if solved else progress, length]
	dots.queue_redraw()
	widget.queue_redraw()
	occupy_button.visible = kind == "paired_latch" and not solved and plates_state() == "free"
	recover_button.visible = solved and not found
	inputs.visible = not solved
	for child in inputs.get_children():
		(child as Button).disabled = sending or (kind == "paired_latch" and not plates_occupied)
	if solved:
		feedback.text = game.content.text("artifact.bound")
		feedback.add_theme_color_override("font_color", Color("#c8f0a0"))

func on_state() -> void:
	if not open_flag:
		return
	if game.client.poi(site_id).is_empty():
		close()
		return
	plates_occupied = plates_state() == "held"
	if kind == "paired_latch" and plates_state() == "walking":
		feedback.text = game.content.text("mechanism.paired")
	var found := String(game.client.poi(site_id).get("artifact", {}).get("state", "hidden")) != "hidden"
	if found:
		close()
		return
	refresh()

func on_progress(target_site: String, ok: bool) -> void:
	if target_site != site_id or not open_flag:
		return
	if ok:
		flash = 1.0
		flash_color = Color(1.0, 0.85, 0.4, 0.5)
		feedback.text = ""
		game.audio.play_cue("fr_cage_latch")
		if bool(mechanism().get("solved", false)):
			game.fx.burst_hud(widget.get_global_rect().get_center())
			game.audio.play_cue("fr_gate_creak" if kind == "winch_sequence" else "fr_artifact_discovery")
	else:
		shake = 1.0
		flash = 1.0
		reset_spin = 1.0
		flash_color = Color(1.0, 0.3, 0.2, 0.45)
		feedback.text = game.content.text("mechanism.wrong")
		feedback.add_theme_color_override("font_color", Color("#ffb08a"))
	refresh()

func send_symbol(symbol: String) -> void:
	if sending:
		return
	if kind == "trail_cache" and not observed(symbol):
		# The squad must really reach the landmark first (server records it as observed).
		pending_landmark = symbol
		sending = true
		refresh()
		await game.request_action("move", {"targetId":site_id + ":landmark:" + symbol})
		sending = false
		refresh()
		return
	sending = true
	refresh()
	var before := int(mechanism().get("progress", 0))
	# The 3D device animates from the authoritative state change; it needs the chosen symbol
	# (a wrong rune turns the active ring to it before the rings spin back).
	game.actors.mechanism_feedback(site_id, symbol, true)
	var result: Dictionary = await game.request_action("mechanism_input", {"siteId":site_id, "symbol":symbol})
	sending = false
	if bool(result.get("ok", false)):
		var announced := false
		for event in result.get("events", []):
			if String(event.get("type", "")) == "mechanism_progress":
				announced = true
		if not announced:
			var after := int(mechanism().get("progress", 0))
			var last := String(mechanism().get("lastResult", ""))
			on_progress(site_id, last == "ok" or after > before or bool(mechanism().get("solved", false)))
	refresh()

func landmark_tapped(symbol: String) -> void:
	if open_flag and kind == "trail_cache" and not symbol.is_empty():
		send_symbol(symbol)

func occupy() -> void:
	if sending:
		return
	sending = true
	refresh()
	var result: Dictionary = await game.request_action("occupy_plates", {"siteId":site_id})
	sending = false
	if bool(result.get("ok", false)):
		plates_occupied = plates_state() == "held"
		feedback.text = game.content.text("mechanism.paired")
	refresh()

func recover() -> void:
	var result: Dictionary = await game.request_action("attempt_task", {"siteId":site_id, "taskId":"recover_artifact"})
	if bool(result.get("ok", false)):
		close()

func tick(delta: float) -> void:
	if not open_flag:
		return
	if not pending_landmark.is_empty() and not sending and observed(pending_landmark) and not (game.client.squad().get("move") is Dictionary):
		var symbol := pending_landmark
		pending_landmark = ""
		send_symbol(symbol)
	if shake > 0.0 or flash > 0.0 or reset_spin > 0.0:
		shake = maxf(0.0, shake - delta * 2.2)
		flash = maxf(0.0, flash - delta * 1.6)
		reset_spin = maxf(0.0, reset_spin - delta * 1.2)
		widget.position.x = sin(Time.get_ticks_msec() / 22.0) * 9.0 * shake
		widget.queue_redraw()
	elif kind == "trail_cache" or kind == "rune_lock":
		widget.queue_redraw()

func draw_dots() -> void:
	var state := mechanism()
	var total := maxi(1, int(state.get("length", 3)))
	var value := total if bool(state.get("solved", false)) else int(state.get("progress", 0))
	var spacing := 32.0
	var start := (dots.size.x - spacing * (total - 1)) * 0.5
	var y := dots.size.y * 0.5
	dots.draw_line(Vector2(start, y), Vector2(start + spacing * (total - 1), y), Color("#6b5434"), 2.0)
	for i in total:
		var c := Vector2(start + spacing * i, y)
		dots.draw_circle(c, 8.0, Color("#f6b73c") if i < value else Color("#4d4539"))
		dots.draw_arc(c, 8.0, 0, TAU, 20, Color("#2a2118"), 1.5, true)

# ------------------------------------------------------------------ widget drawing
func widget_center() -> Vector2:
	return widget.size * 0.5

func ring_radius(index: int) -> float:
	var base := minf(widget.size.x, widget.size.y) * 0.46
	return base * [1.0, 0.72, 0.44][index]

func ring_symbol_position(ring: int, slot: int, count: int, spin: float) -> Vector2:
	var angle := -PI * 0.5 + TAU * float(slot) / float(count) + spin
	var r := ring_radius(ring) - minf(widget.size.x, widget.size.y) * 0.075
	return widget_center() + Vector2(cos(angle), sin(angle)) * r

func draw_widget() -> void:
	var state := mechanism()
	var progress := int(state.get("progress", 0))
	var solved := bool(state.get("solved", false))
	if solved:
		progress = int(state.get("length", 3))
	var rect := Rect2(Vector2.ZERO, widget.size)
	widget.draw_rect(rect, Color("#14110d"))
	widget.draw_rect(rect, Color("#6f5a3a"), false, 1.5)
	match kind:
		"rune_lock":
			draw_rune_lock(progress, solved)
		"winch_sequence":
			draw_winch(progress, solved)
		"paired_latch":
			draw_paired(progress, solved)
		_:
			draw_trail(progress, solved)
	if flash > 0.0:
		widget.draw_rect(rect, Color(flash_color, flash_color.a * flash))

const BRONZE := Color("#b8894a")
const BRONZE_LIGHT := Color("#e2b673")
const BRONZE_DARK := Color("#6d4b22")
const STONE := Color("#7d786e")
const STONE_DARK := Color("#4a463f")
const WOOD := Color("#7a4f2a")
const WOOD_DARK := Color("#4a2e17")
const ENGRAVE := Color("#3a2614")

func stone_block(rect: Rect2) -> void:
	widget.draw_rect(rect, STONE)
	var rows := maxi(1, int(rect.size.y / 14.0))
	for r in rows:
		var y := rect.position.y + rect.size.y * float(r) / rows
		widget.draw_line(Vector2(rect.position.x, y), Vector2(rect.end.x, y), STONE_DARK, 1.0)
		var offset := 9.0 if r % 2 == 0 else 0.0
		var x := rect.position.x + offset
		while x < rect.end.x:
			widget.draw_line(Vector2(x, y), Vector2(x, y + rect.size.y / rows), STONE_DARK, 1.0)
			x += 22.0
	widget.draw_rect(rect, STONE_DARK, false, 1.5)

func bronze_disc(c: Vector2, r: float, lit: bool) -> void:
	widget.draw_circle(c, r, BRONZE_DARK)
	widget.draw_circle(c, r - 2.0, BRONZE_LIGHT if lit else BRONZE)
	widget.draw_circle(c + Vector2(-r * 0.25, -r * 0.3), r * 0.45, Color(1, 0.92, 0.7, 0.18))
	widget.draw_arc(c, r - 1.0, 0, TAU, 48, BRONZE_DARK, 2.0, true)

func draw_rune_lock(progress: int, solved: bool) -> void:
	var c := widget_center()
	var spin := reset_spin * TAU * 0.5
	widget.draw_circle(c, ring_radius(0) + 10.0, STONE_DARK)
	widget.draw_circle(c, ring_radius(0) + 7.0, STONE)
	for i in 24:
		var a := TAU * float(i) / 24.0
		widget.draw_line(c + Vector2(cos(a), sin(a)) * (ring_radius(0) + 1.0), c + Vector2(cos(a), sin(a)) * (ring_radius(0) + 9.0), STONE_DARK, 1.0)
	for ring in 3:
		var r := ring_radius(ring)
		var active := ring == progress and not solved
		bronze_disc(c, r, ring < progress or solved)
		if active:
			var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 220.0)
			widget.draw_arc(c, r + 1.5, 0, TAU, 64, Color(1.0, 0.85, 0.4, 0.55 + 0.35 * pulse), 3.0, true)
		var count := symbols.size()
		for slot in count:
			var symbol := String(symbols[slot])
			var p := ring_symbol_position(ring, slot, count, spin * (1 if ring % 2 == 0 else -1))
			var chosen := ring < progress and solution.size() > ring and String(solution[ring]) == symbol
			if ring < progress:
				if not chosen:
					continue
				p = c + Vector2(0, -(ring_radius(ring) - minf(widget.size.x, widget.size.y) * 0.075))
			draw_symbol(widget, symbol, p, 22.0 if ring == 0 else 18.0, ENGRAVE if not active else Color("#2a1608"))
	widget.draw_circle(c, ring_radius(2) * 0.42, BRONZE_DARK)
	Art.draw_tree(widget, c, ring_radius(2) * 0.7, Color("#f4d48e") if solved else Color("#d8b070"))
	var pointer := PackedVector2Array([c + Vector2(-9, -ring_radius(0) - 14), c + Vector2(9, -ring_radius(0) - 14), c + Vector2(0, -ring_radius(0) + 2)])
	widget.draw_colored_polygon(pointer, Color("#e9c77f"))
	if solved:
		var gem := c + Vector2(ring_radius(0) + 2.0, ring_radius(0) * 0.35)
		widget.draw_circle(gem, 9.0, Color("#9fdc3c"))
		widget.draw_circle(gem + Vector2(-3, -3), 3.0, Color("#eaffb0"))

func draw_winch(progress: int, solved: bool) -> void:
	var w := widget.size
	var ground := w.y * 0.86
	widget.draw_rect(Rect2(0, ground, w.x, w.y - ground), Color("#3b4a2a"))
	var well := Rect2(w.x * 0.22, ground - 6.0, w.x * 0.36, 18.0)
	stone_block(well)
	widget.draw_rect(Rect2(well.position + Vector2(10, 4), Vector2(well.size.x - 20, 10)), Color("#120f0b"))
	var top := w.y * 0.16
	for x in [w.x * 0.2, w.x * 0.6]:
		widget.draw_line(Vector2(x - 12, ground), Vector2(x + (8.0 if x < w.x * 0.4 else -8.0), top), WOOD_DARK, 9.0)
		widget.draw_line(Vector2(x - 12, ground), Vector2(x + (8.0 if x < w.x * 0.4 else -8.0), top), WOOD, 6.0)
		widget.draw_rect(Rect2(Vector2(x - 20, ground - 8), Vector2(26, 10)), Color("#5a5a5a"))
	widget.draw_line(Vector2(w.x * 0.18, top + 8), Vector2(w.x * 0.62, top + 8), WOOD, 7.0)
	var drum := Vector2(w.x * 0.40, top + 14.0)
	widget.draw_rect(Rect2(drum - Vector2(34, 14), Vector2(68, 28)), Color("#a3814f"))
	for i in 9:
		var x := drum.x - 32 + i * 8
		widget.draw_line(Vector2(x, drum.y - 14), Vector2(x + 4, drum.y + 14), Color("#d9c08a"), 2.0)
	var gear := drum + Vector2(-46, 2)
	for i in 10:
		var a := TAU * float(i) / 10.0 + (0.0 if progress < 2 else 0.3)
		widget.draw_line(gear + Vector2(cos(a), sin(a)) * 10.0, gear + Vector2(cos(a), sin(a)) * 16.0, Color("#3d3a36"), 4.0)
	widget.draw_circle(gear, 11.0, Color("#56524b"))
	var crank := drum + Vector2(46, 2)
	var turn := float(progress) * 1.2
	widget.draw_line(crank, crank + Vector2(cos(turn), sin(turn)) * 20.0, Color("#56524b"), 5.0)
	widget.draw_circle(crank + Vector2(cos(turn), sin(turn)) * 20.0, 5.0, WOOD)
	var drop := 0.0 if solved else (1.0 - float(progress) / 3.0) * (1.0 - reset_spin) + reset_spin
	var chest_y := lerpf(w.y * 0.36, ground - 4.0, clampf(drop, 0.0, 1.0))
	widget.draw_line(drum + Vector2(0, 14), Vector2(drum.x, chest_y - 14), Color("#e0c58e"), 2.5)
	Art.draw_chest(widget, Rect2(drum.x - 24, chest_y - 18, 48, 38))
	var steps := ["brake", "pawl", "raise"]
	for i in 3:
		var p := Vector2(w.x * 0.83, w.y * (0.2 + 0.28 * i))
		var done := i < progress or solved
		bronze_disc(p, 22.0, done)
		draw_symbol(widget, steps[i], p, 26.0, ENGRAVE)
		widget.draw_string(get_theme_default_font(), p + Vector2(-28, 34), "%d" % (i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("#d8c39a"))

func draw_paired(progress: int, solved: bool) -> void:
	var w := widget.size
	var base := Rect2(Vector2(w.x * 0.03, w.y * 0.42), Vector2(w.x * 0.94, w.y * 0.5))
	stone_block(base)
	var plate_size := Vector2(w.x * 0.24, w.y * 0.2)
	var left := Rect2(Vector2(w.x * 0.06, w.y * 0.3), plate_size)
	var right := Rect2(Vector2(w.x * 0.70, w.y * 0.3), plate_size)
	var latch := Rect2(Vector2(w.x * 0.43, w.y * 0.12), Vector2(w.x * 0.14, w.y * 0.62))
	for i in 2:
		var plate: Rect2 = left if i == 0 else right
		var pressed := plates_occupied or plates_state() == "walking"
		var sink := 6.0 if pressed else 0.0
		var spring := Rect2(plate.position + Vector2(plate.size.x * 0.35, plate.size.y + sink), Vector2(plate.size.x * 0.3, base.end.y - plate.end.y - sink - 8.0))
		for k in 5:
			var y := spring.position.y + spring.size.y * float(k) / 5.0
			widget.draw_line(Vector2(spring.position.x, y), Vector2(spring.end.x, y + spring.size.y / 10.0), Color("#c8a46a"), 2.0)
		var top := Rect2(plate.position + Vector2(0, sink), plate.size)
		widget.draw_rect(top.grow(3), BRONZE_DARK)
		widget.draw_rect(top, Color("#8d877c") if progress <= i else Color("#c9a65e"))
		widget.draw_rect(top.grow(-5), STONE_DARK, false, 1.0)
		var lever_from := Vector2(top.get_center().x, base.end.y - 14.0)
		var lever_to := Vector2(latch.position.x if i == 0 else latch.end.x, latch.end.y - 18.0)
		widget.draw_line(lever_from, lever_to, WOOD_DARK, 9.0)
		widget.draw_line(lever_from, lever_to, Color("#e0b86a") if progress > i or solved else WOOD, 6.0)
		if pressed:
			var person := top.get_center() + Vector2(0, -plate_size.y * 0.55)
			widget.draw_circle(person + Vector2(0, -16), 7.0, Color("#e6d2b0"))
			widget.draw_rect(Rect2(person + Vector2(-8, -9), Vector2(16, 24)), Color("#5a6b3a") if i == 0 else Color("#6b4a2e"))
			widget.draw_line(top.get_center() + Vector2(0, -plate_size.y * 1.4), top.get_center() + Vector2(0, -plate_size.y * 1.05), Color("#ffe9b0"), 2.0)
	stone_block(latch)
	var arch := latch.grow(-6)
	widget.draw_rect(arch, BRONZE_DARK)
	widget.draw_rect(arch.grow(-3), BRONZE)
	var bolt_drop := 1.0 if solved else 0.0
	var bolt := Rect2(arch.position + Vector2(arch.size.x * 0.28, arch.size.y * (0.35 + 0.4 * bolt_drop)), Vector2(arch.size.x * 0.44, arch.size.y * 0.24))
	widget.draw_rect(bolt, BRONZE_LIGHT)
	widget.draw_rect(bolt, BRONZE_DARK, false, 1.5)
	Art.draw_tree(widget, arch.get_center() + Vector2(0, -arch.size.y * 0.3), 24.0, Color("#3a2614"))

func trail_points() -> Array:
	var w := widget.size
	return [Vector2(w.x * 0.16, w.y * 0.7), Vector2(w.x * 0.46, w.y * 0.3), Vector2(w.x * 0.76, w.y * 0.62)]

func draw_trail(progress: int, solved: bool) -> void:
	var w := widget.size
	widget.draw_rect(Rect2(Vector2.ZERO, w), Color("#2f3a24"))
	for i in 18:
		var p := Vector2(fmod(i * 73.0, w.x), fmod(i * 41.0 + 13.0, w.y))
		widget.draw_circle(p, 9.0 + float(i % 3) * 3.0, Color("#3a4a2c"))
	var points := trail_points()
	var order := solution if solution.size() == 3 else symbols
	var cache := Vector2(w.x * 0.9, w.y * 0.3)
	var stops := points + [cache]
	for i in range(1, stops.size()):
		var a: Vector2 = stops[i - 1]
		var b: Vector2 = stops[i]
		var lit := i <= progress or solved
		for k in 10:
			var p := a.lerp(b, (float(k) + 0.5) / 10.0)
			widget.draw_circle(p, 3.2, Color("#ffcf5c") if lit else Color("#6f6450"))
	for i in min(3, order.size()):
		var p: Vector2 = points[i]
		var found: bool = i < progress or solved
		var symbol := String(order[i])
		if not found and i == progress:
			var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 260.0 + i)
			widget.draw_circle(p, 31.0, Color(1.0, 0.8, 0.35, 0.12 + 0.14 * pulse))
		bronze_disc(p, 24.0, found)
		if found or observed(symbol):
			draw_symbol(widget, symbol, p, 28.0, ENGRAVE)
		else:
			widget.draw_string(get_theme_default_font(), p + Vector2(-5, 7), "?", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, ENGRAVE)
	var log := Rect2(cache - Vector2(34, 10), Vector2(68, 20))
	widget.draw_rect(log, WOOD)
	widget.draw_rect(log, WOOD_DARK, false, 2.0)
	widget.draw_circle(log.end - Vector2(0, 10), 9.0, Color("#a3814f"))
	if solved:
		Art.draw_chest(widget, Rect2(cache.x - 22, cache.y - 40, 44, 34))

func widget_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT):
		return
	if kind != "rune_lock" or sending:
		return
	var progress := int(mechanism().get("progress", 0))
	if progress >= 3 or bool(mechanism().get("solved", false)):
		return
	var count := symbols.size()
	var best := ""
	var best_gap := 30.0
	for slot in count:
		var p := ring_symbol_position(progress, slot, count, 0.0)
		var gap := p.distance_to(event.position)
		if gap < best_gap:
			best_gap = gap
			best = String(symbols[slot])
	if not best.is_empty():
		send_symbol(best)

# ------------------------------------------------------------------ symbol glyphs
static func draw_symbol(ci: CanvasItem, symbol: String, c: Vector2, s: float, color: Color) -> void:
	var w := maxf(1.5, s * 0.09)
	var h := s * 0.5
	match symbol:
		"mountain":
			ci.draw_polyline(PackedVector2Array([c + Vector2(-h, h * 0.6), c + Vector2(-h * 0.3, -h * 0.5), c + Vector2(0, -h * 0.1), c + Vector2(h * 0.35, -h * 0.7), c + Vector2(h, h * 0.6)]), color, w, true)
		"river":
			for row in 2:
				var pts := PackedVector2Array()
				for i in 9:
					var x := -h + 2.0 * h * float(i) / 8.0
					pts.append(c + Vector2(x, (row - 0.5) * h * 0.6 + sin(float(i) * 1.4) * h * 0.18))
				ci.draw_polyline(pts, color, w, true)
		"leaf", "seed":
			var pts := PackedVector2Array()
			for i in 17:
				var a := TAU * float(i) / 16.0
				pts.append(c + Vector2(cos(a) * h * (0.45 if symbol == "leaf" else 0.35), sin(a) * h * 0.8).rotated(0.6))
			ci.draw_polyline(pts, color, w, true)
			ci.draw_line(c + Vector2(0, h * 0.8).rotated(0.6), c - Vector2(0, h * 0.8).rotated(0.6), color, w * 0.7, true)
		"coal", "stone", "white_moss", "three_notches":
			var pts := PackedVector2Array([c + Vector2(-h, h * 0.4), c + Vector2(-h * 0.6, -h * 0.5), c + Vector2(h * 0.2, -h * 0.7), c + Vector2(h, -h * 0.1), c + Vector2(h * 0.7, h * 0.5), c + Vector2(-h, h * 0.4)])
			ci.draw_polyline(pts, color, w, true)
			if symbol == "coal":
				ci.draw_circle(c, h * 0.2, color)
			elif symbol == "white_moss":
				for i in 4:
					ci.draw_circle(c + Vector2(-h * 0.4 + i * h * 0.28, -h * 0.15 + (i % 2) * h * 0.2), h * 0.1, Color.WHITE)
			elif symbol == "three_notches":
				for i in 3:
					ci.draw_line(c + Vector2(-h * 0.35 + i * h * 0.35, -h * 0.3), c + Vector2(-h * 0.25 + i * h * 0.35, h * 0.25), color, w * 0.8, true)
		"tree", "resin_pine", "split_birch":
			ci.draw_line(c + Vector2(0, h), c + Vector2(0, -h * 0.2), color, w * 1.3, true)
			if symbol == "resin_pine":
				ci.draw_polyline(PackedVector2Array([c + Vector2(-h * 0.7, h * 0.3), c + Vector2(0, -h), c + Vector2(h * 0.7, h * 0.3), c + Vector2(-h * 0.7, h * 0.3)]), color, w, true)
			elif symbol == "split_birch":
				ci.draw_line(c + Vector2(-h * 0.2, h), c + Vector2(-h * 0.35, -h * 0.8), color, w, true)
				ci.draw_line(c + Vector2(h * 0.2, h), c + Vector2(h * 0.35, -h * 0.8), color, w, true)
			else:
				ci.draw_circle(c + Vector2(0, -h * 0.45), h * 0.5, Color(color, 0.0))
				ci.draw_arc(c + Vector2(0, -h * 0.45), h * 0.55, 0, TAU, 20, color, w, true)
		"sun":
			ci.draw_arc(c, h * 0.4, 0, TAU, 20, color, w, true)
			for i in 8:
				var a := TAU * float(i) / 8.0
				ci.draw_line(c + Vector2(cos(a), sin(a)) * h * 0.6, c + Vector2(cos(a), sin(a)) * h, color, w * 0.8, true)
		"root":
			ci.draw_line(c + Vector2(0, -h), c + Vector2(0, h * 0.1), color, w, true)
			for side in [-1.0, 0.0, 1.0]:
				ci.draw_polyline(PackedVector2Array([c + Vector2(0, h * 0.1), c + Vector2(side * h * 0.5, h * 0.5), c + Vector2(side * h * 0.8, h)]), color, w * 0.8, true)
		"fallen_trunk", "double_stump", "flat_slab":
			if symbol == "fallen_trunk":
				ci.draw_rect(Rect2(c + Vector2(-h, -h * 0.25), Vector2(h * 2.0, h * 0.5)), color, false, w)
				ci.draw_arc(c + Vector2(h, 0), h * 0.25, 0, TAU, 12, color, w * 0.7, true)
			elif symbol == "double_stump":
				for side in [-1.0, 1.0]:
					ci.draw_rect(Rect2(c + Vector2(side * h * 0.5 - h * 0.3, -h * 0.2), Vector2(h * 0.6, h * 0.8)), color, false, w)
			else:
				ci.draw_rect(Rect2(c + Vector2(-h, -h * 0.2), Vector2(h * 2.0, h * 0.45)), color, false, w)
		"resin_bowl":
			ci.draw_arc(c + Vector2(0, -h * 0.2), h * 0.8, 0.0, PI, 16, color, w, true)
			ci.draw_line(c + Vector2(-h * 0.8, -h * 0.2), c + Vector2(h * 0.8, -h * 0.2), color, w, true)
		"bent_fern":
			var pts := PackedVector2Array()
			for i in 9:
				var t := float(i) / 8.0
				pts.append(c + Vector2(-h + t * h * 1.6, h - t * t * h * 1.8))
			ci.draw_polyline(pts, color, w, true)
			for i in range(1, 8, 2):
				var p := pts[i]
				ci.draw_line(p, p + Vector2(-h * 0.25, -h * 0.25), color, w * 0.6, true)
				ci.draw_line(p, p + Vector2(h * 0.25, -h * 0.1), color, w * 0.6, true)
		"brake":
			ci.draw_line(c + Vector2(-h * 0.6, h * 0.8), c + Vector2(h * 0.4, -h * 0.8), color, w * 1.3, true)
			ci.draw_circle(c + Vector2(h * 0.4, -h * 0.8), h * 0.22, color)
			ci.draw_arc(c + Vector2(-h * 0.2, h * 0.3), h * 0.5, PI, TAU, 12, color, w, true)
		"pawl":
			for i in 10:
				var a := TAU * float(i) / 10.0
				ci.draw_line(c + Vector2(cos(a), sin(a)) * h * 0.55, c + Vector2(cos(a), sin(a)) * h * 0.85, color, w * 1.2, true)
			ci.draw_arc(c, h * 0.55, 0, TAU, 20, color, w, true)
			ci.draw_circle(c, h * 0.16, color)
		"raise":
			ci.draw_line(c + Vector2(0, h), c + Vector2(0, -h * 0.6), color, w * 1.3, true)
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -h), c + Vector2(-h * 0.5, -h * 0.3), c + Vector2(h * 0.5, -h * 0.3)]), color)
		"left_plate", "right_plate":
			ci.draw_rect(Rect2(c + Vector2(-h * 0.8, -h * 0.5), Vector2(h * 1.6, h)), color, false, w)
			var arrow_x := -h * 0.2 if symbol == "left_plate" else h * 0.2
			ci.draw_line(c + Vector2(arrow_x, -h), c + Vector2(arrow_x, -h * 0.55), color, w, true)
		"center_latch":
			ci.draw_rect(Rect2(c + Vector2(-h * 0.35, -h), Vector2(h * 0.7, h * 2.0)), color, false, w)
			ci.draw_rect(Rect2(c + Vector2(-h * 0.2, -h * 0.3), Vector2(h * 0.4, h * 0.6)), color)
		_:
			ci.draw_arc(c, h * 0.7, 0, TAU, 20, color, w, true)
