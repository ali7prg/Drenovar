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
	eyebrow = Style.label("", 14, Color("#ebcc89"))
	titles.add_child(eyebrow)
	title = Style.label("", 25, Style.IVORY, true)
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	titles.add_child(title)
	close_button = Button.new()
	close_button.name = "MechanismClose"
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(48, 44)
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
	count_label = Style.label("", 18, Style.IVORY, true)
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
	plates_occupied = String(game.client.squad().get("busy", "")) == "mechanism"
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
	if spot == Vector3.INF:
		return
	var zoom := 30.0
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
	occupy_button.visible = kind == "paired_latch" and not solved and not plates_occupied
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
	if String(game.client.squad().get("busy", "")) == "mechanism":
		plates_occupied = true
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
	sending = true
	refresh()
	var before := int(mechanism().get("progress", 0))
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
		plates_occupied = true
		feedback.text = game.content.text("mechanism.paired")
	refresh()

func recover() -> void:
	var result: Dictionary = await game.request_action("attempt_task", {"siteId":site_id, "taskId":"recover_artifact"})
	if bool(result.get("ok", false)):
		close()

func tick(delta: float) -> void:
	if not open_flag:
		return
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

func draw_rune_lock(progress: int, solved: bool) -> void:
	var c := widget_center()
	var spin := reset_spin * TAU * 0.5
	for ring in 3:
		var r := ring_radius(ring)
		var active := ring == progress and not solved
		widget.draw_circle(c, r, Color("#3a2c1a") if ring % 2 == 0 else Color("#2c2216"))
		widget.draw_arc(c, r, 0, TAU, 64, Color("#d6ad62") if active else Color("#8a6a3c"), 3.0 if active else 1.6, true)
		if active:
			var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 220.0)
			widget.draw_arc(c, r + 3.0, 0, TAU, 64, Color(1.0, 0.8, 0.35, 0.35 * pulse), 4.0, true)
		var count := symbols.size()
		for slot in count:
			var symbol := String(symbols[slot])
			var p := ring_symbol_position(ring, slot, count, spin * (1 if ring % 2 == 0 else -1))
			var chosen := ring < progress and solution.size() > ring and String(solution[ring]) == symbol
			if ring < progress:
				if chosen:
					p = c + Vector2(0, -(ring_radius(ring) - minf(widget.size.x, widget.size.y) * 0.075))
				else:
					continue
			var color := Color("#ffe39a") if chosen else (Color("#f0d9a8") if active else Color("#9c8a6a"))
			draw_symbol(widget, symbol, p, 22.0 if ring == 0 else 18.0, color)
	widget.draw_circle(c, ring_radius(2) * 0.42, Color("#5a4024"))
	Art.draw_tree(widget, c, ring_radius(2) * 0.7, Color("#e9c77f") if solved else Color("#a88a52"))
	var pointer := PackedVector2Array([c + Vector2(-9, -ring_radius(0) - 12), c + Vector2(9, -ring_radius(0) - 12), c + Vector2(0, -ring_radius(0) + 2)])
	widget.draw_colored_polygon(pointer, Color("#e9c77f"))

func draw_winch(progress: int, solved: bool) -> void:
	var w := widget.size
	var frame_left := Vector2(w.x * 0.18, w.y * 0.88)
	var frame_right := Vector2(w.x * 0.62, w.y * 0.88)
	var top := w.y * 0.22
	var wood := Color("#8a5a32")
	widget.draw_line(frame_left, Vector2(w.x * 0.26, top), wood, 7.0)
	widget.draw_line(frame_right, Vector2(w.x * 0.54, top), wood, 7.0)
	widget.draw_line(Vector2(w.x * 0.22, top), Vector2(w.x * 0.58, top), wood, 6.0)
	var drum := Vector2(w.x * 0.40, top + 6.0)
	widget.draw_circle(drum, 16.0, Color("#b08a5a"))
	for i in 5:
		widget.draw_line(drum + Vector2(-14 + i * 7, -14), drum + Vector2(-14 + i * 7, 14), Color("#6d4a26"), 1.5)
	var drop := 0.0 if solved else (1.0 - float(progress) / 3.0) * (1.0 - reset_spin) + reset_spin * 1.0
	var chest_y := lerpf(w.y * 0.42, w.y * 0.8, clampf(drop, 0.0, 1.0))
	widget.draw_line(drum + Vector2(0, 14), Vector2(drum.x, chest_y - 14), Color("#d9c08a"), 2.0)
	widget.draw_rect(Rect2(w.x * 0.26, w.y * 0.84, w.x * 0.28, 8), Color("#3a3a3a"))
	Art.draw_chest(widget, Rect2(drum.x - 22, chest_y - 16, 44, 36))
	var steps := ["brake", "pawl", "raise"]
	for i in 3:
		var p := Vector2(w.x * 0.80, w.y * (0.24 + 0.27 * i))
		var done := i < progress
		widget.draw_circle(p, 22.0, Color("#3b2d1c") if not done else Color("#5c4a20"))
		widget.draw_arc(p, 22.0, 0, TAU, 32, Color("#e9c77f") if done else Color("#8a6a3c"), 2.0, true)
		draw_symbol(widget, steps[i], p, 26.0, Color("#ffe39a") if done else Color("#d8c39a"))

func draw_paired(progress: int, solved: bool) -> void:
	var w := widget.size
	var y := w.y * 0.62
	var plate_size := Vector2(w.x * 0.22, w.y * 0.22)
	var left := Rect2(Vector2(w.x * 0.06, y - plate_size.y * 0.5), plate_size)
	var right := Rect2(Vector2(w.x * 0.72, y - plate_size.y * 0.5), plate_size)
	for i in 2:
		var plate: Rect2 = left if i == 0 else right
		var pressed := plates_occupied
		var held := progress > i
		widget.draw_rect(plate.grow(4), Color("#4a4a46"))
		widget.draw_rect(plate.grow(-2 if pressed else 0), Color("#8d8a80") if not held else Color("#c7a65a"))
		widget.draw_rect(plate, Color("#2b2b28"), false, 2.0)
		if pressed:
			var person := plate.get_center() + Vector2(0, -plate_size.y * 0.35)
			widget.draw_circle(person, 8.0, Color("#e8dcc0"))
			widget.draw_rect(Rect2(person + Vector2(-8, 8), Vector2(16, 22)), Color("#3f5a7a"))
	var latch_rect := Rect2(Vector2(w.x * 0.42, w.y * 0.2), Vector2(w.x * 0.16, w.y * 0.62))
	widget.draw_rect(latch_rect, Color("#7a6a52"))
	widget.draw_rect(latch_rect, Color("#2b2b28"), false, 2.0)
	var bolt_drop := 0.0 if not solved else 1.0
	var bolt := Rect2(latch_rect.position + Vector2(latch_rect.size.x * 0.3, latch_rect.size.y * (0.18 + 0.4 * bolt_drop)), Vector2(latch_rect.size.x * 0.4, latch_rect.size.y * 0.32))
	widget.draw_rect(bolt, Color("#d6ad62"))
	Art.draw_tree(widget, latch_rect.get_center() + Vector2(0, -latch_rect.size.y * 0.32), 26.0, Color("#e9c77f"))
	for i in 2:
		var from := Vector2(left.end.x, y) if i == 0 else Vector2(right.position.x, y)
		var to := Vector2(latch_rect.position.x, y + 12) if i == 0 else Vector2(latch_rect.end.x, y + 12)
		widget.draw_line(from, to, Color("#8a5a32") if progress <= i else Color("#e9c77f"), 5.0)

func trail_points() -> Array:
	var w := widget.size
	return [Vector2(w.x * 0.18, w.y * 0.72), Vector2(w.x * 0.5, w.y * 0.32), Vector2(w.x * 0.82, w.y * 0.62)]

func draw_trail(progress: int, solved: bool) -> void:
	var points := trail_points()
	var order := solution if solution.size() == 3 else symbols
	for i in range(1, 3):
		var a: Vector2 = points[i - 1]
		var b: Vector2 = points[i]
		var lit := i < progress or solved
		var steps := 9
		for k in steps:
			var p := a.lerp(b, (float(k) + 0.5) / steps)
			widget.draw_circle(p, 3.0, Color("#f6b73c") if lit else Color("#5e5547"))
	for i in min(3, order.size()):
		var p: Vector2 = points[i]
		var found: bool = i < progress or solved
		var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 260.0 + i)
		if not found and i == progress:
			widget.draw_circle(p, 30.0, Color(1.0, 0.8, 0.35, 0.12 + 0.12 * pulse))
		widget.draw_circle(p, 24.0, Color("#2e271d"))
		widget.draw_arc(p, 24.0, 0, TAU, 32, Color("#e9c77f") if found else Color("#7a6646"), 2.0, true)
		if found:
			draw_symbol(widget, String(order[i]), p, 28.0, Color("#ffe39a"))
		else:
			var font := get_theme_default_font()
			widget.draw_string(font, p + Vector2(-5, 7), "?", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("#a99474"))
	if solved:
		Art.draw_chest(widget, Rect2(widget.size.x * 0.43, widget.size.y * 0.66, 56, 46))

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
