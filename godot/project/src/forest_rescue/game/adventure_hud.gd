extends Control
## Adventure overlay inside the existing HUD root (below the main modal/dimmer):
## * bottom row like art/07: task card (banner, title, progress dots, n/N), reward strip
##   (chest, label, five resources), buttons «Маршрут» «Отряд» «Продолжить»;
## * hint pill with the next step, toasts, banner (art/18 centre), locked card (art/18 left),
##   intro prompt (art/18 right), battle header, off-screen target arrow.
## It never blocks map gestures outside its own visible widgets.

const Style = preload("res://src/forest_rescue/game/hud_style.gd")
const Art = preload("res://src/forest_rescue/game/hud_art.gd")
const STRIP_ORDER := ["wood", "stone", "food", "iron", "coins"]

var game: Node
var bar: HBoxContainer
var task_card: PanelContainer
var task_icon: Control
var task_title: Label
var task_dots: Control
var task_count: Label
var reward_strip: PanelContainer
var reward_caption: Label
var reward_amounts: Dictionary = {}
var reward_cells: Dictionary = {}
var route_button: Button
var squad_button: Button
var continue_button: Button
var continue_caption: Label
var hint: PanelContainer
var hint_label: Label
var toasts: VBoxContainer
var banner: Control
var banner_title: Label
var banner_sub: Label
var banner_until := 0.0
var banner_column: VBoxContainer
var banner_plate: PanelContainer
var locked_card: PanelContainer
var locked_title: Label
var locked_body: Label
var locked_progress: Label
var locked_cta: Button
var locked_reason := ""
var locked_dismissed := false
var dwell_started := 0
var dwell_point := Vector3.INF
var invite_button: Button
var battle_header: PanelContainer
var battle_title: Label
var battle_sub: Label
var battle_bar: ProgressBar
var battle_retreat: Button
var battle_timer: Label
var arrow: Control
var arrow_target := Vector3.INF
var arrow_label := ""
var progress_value := 0
var progress_total := 3
var sparkle_rect := Rect2()
var compact := false
var strip_head: BoxContainer
var strip_chest: Control
var last_nav_edge := -1.0

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "ForestAdventureHud"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	build_bar()
	build_hint()
	build_toasts()
	build_banner()
	build_locked_card()
	build_invite()
	build_battle_header()
	arrow = Control.new()
	arrow.name = "TargetArrow"
	arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	arrow.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	arrow.draw.connect(draw_arrow)
	add_child(arrow)
	move_child(arrow, 0)  # name plates and the target arrow stay under cards and toasts
	get_viewport().size_changed.connect(layout)
	layout()

func text(key: String, args := {}) -> String:
	return game.content.text(key, args)

# ---------------------------------------------------------------- bottom row (art/07)
func build_bar() -> void:
	bar = HBoxContainer.new()
	bar.name = "AdventureBar"
	bar.add_theme_constant_override("separation", 8)
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bar)
	task_card = PanelContainer.new()
	task_card.name = "TaskCard"
	task_card.add_theme_stylebox_override("panel", Style.parchment())
	task_card.custom_minimum_size = Vector2(214, 78)
	task_card.mouse_filter = Control.MOUSE_FILTER_STOP
	task_card.gui_input.connect(_on_card_input.bind("journal"))
	bar.add_child(task_card)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	task_card.add_child(row)
	task_icon = Art.new("banner", Vector2(38, 54))
	row.add_child(task_icon)
	var column := VBoxContainer.new()
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 3)
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(column)
	task_title = Style.label("", 15, Style.PARCHMENT_INK, true)
	task_title.name = "TaskTitle"
	task_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	task_title.max_lines_visible = 2
	task_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(task_title)
	var progress := HBoxContainer.new()
	progress.alignment = BoxContainer.ALIGNMENT_CENTER
	progress.add_theme_constant_override("separation", 10)
	progress.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(progress)
	task_dots = Control.new()
	task_dots.name = "ProgressDots"
	task_dots.custom_minimum_size = Vector2(96, 22)
	task_dots.mouse_filter = Control.MOUSE_FILTER_IGNORE
	task_dots.draw.connect(draw_dots)
	progress.add_child(task_dots)
	var divider := ColorRect.new()
	divider.color = Color("#8d6c42")
	divider.custom_minimum_size = Vector2(1, 20)
	divider.mouse_filter = Control.MOUSE_FILTER_IGNORE
	progress.add_child(divider)
	task_count = Style.label("", 18, Style.PARCHMENT_INK, true)
	task_count.name = "TaskCount"
	progress.add_child(task_count)
	reward_strip = PanelContainer.new()
	reward_strip.name = "RewardStrip"
	reward_strip.add_theme_stylebox_override("panel", Style.leather_strip())
	reward_strip.custom_minimum_size = Vector2(0, 78)
	reward_strip.mouse_filter = Control.MOUSE_FILTER_STOP
	reward_strip.gui_input.connect(_on_card_input.bind("rewards"))
	bar.add_child(reward_strip)
	var strip := HBoxContainer.new()
	strip.add_theme_constant_override("separation", 6)
	strip.alignment = BoxContainer.ALIGNMENT_CENTER
	strip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	reward_strip.add_child(strip)
	strip_head = BoxContainer.new()
	strip_head.name = "RewardHead"
	strip_head.alignment = BoxContainer.ALIGNMENT_CENTER
	strip_head.add_theme_constant_override("separation", 2)
	strip_head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	strip.add_child(strip_head)
	strip_chest = Art.new("chest", Vector2(36, 40))
	strip_chest.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	strip_head.add_child(strip_chest)
	reward_caption = Style.label(text("hud.rewardFor"), 13, Style.IVORY, true)
	reward_caption.name = "RewardCaption"
	reward_caption.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	reward_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	strip_head.add_child(reward_caption)
	for index in STRIP_ORDER.size():
		var key: String = STRIP_ORDER[index]
		if index > 0:
			var line := ColorRect.new()
			line.color = Color("#5c4830")
			line.custom_minimum_size = Vector2(1, 52)
			line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			line.mouse_filter = Control.MOUSE_FILTER_IGNORE
			strip.add_child(line)
		var cell := VBoxContainer.new()
		cell.name = "Reward_" + key
		cell.alignment = BoxContainer.ALIGNMENT_CENTER
		cell.add_theme_constant_override("separation", 0)
		cell.custom_minimum_size = Vector2(64, 0)
		cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
		strip.add_child(cell)
		var icon := TextureRect.new()
		icon.texture = game.main.resource_icons.get(key)
		icon.custom_minimum_size = Vector2(30, 28)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		cell.add_child(icon)
		var amount := Style.label("", 14, Style.IVORY, false, 3)
		amount.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(amount)
		reward_amounts[key] = amount
		reward_cells[key] = cell
	route_button = make_action_button("RouteButton", "pin", text("hud.route"), "leather", func(): game.on_route_pressed())
	squad_button = make_action_button("SquadButton", "squad", text("hud.squad"), "leather", func(): game.on_squad_pressed())
	continue_button = make_action_button("ContinueButton", "chevrons", text("hud.continue"), "gold", func(): game.on_continue_pressed())
	continue_button.custom_minimum_size = Vector2(118, 78)

func make_action_button(id: String, icon_kind: String, caption: String, style: String, action: Callable) -> Button:
	var control := Button.new()
	control.name = id
	control.custom_minimum_size = Vector2(88, 78)
	control.tooltip_text = caption
	control.accessibility_name = caption
	Style.apply_button(control, style)
	control.pressed.connect(action)
	bar.add_child(control)
	var column := VBoxContainer.new()
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 1)
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	control.add_child(column)
	var icon := Art.new(icon_kind, Vector2(30, 30))
	icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(icon)
	var label := Style.label(caption, 14, Style.IVORY, true, 2)
	label.name = "Caption"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(label)
	if id == "ContinueButton":
		continue_caption = label
	return control

func draw_dots() -> void:
	var total := maxi(1, progress_total)
	var spacing := minf(30.0, (task_dots.size.x - 16.0) / maxf(1.0, total - 1))
	var y := task_dots.size.y * 0.5
	var start := (task_dots.size.x - spacing * (total - 1)) * 0.5
	task_dots.draw_line(Vector2(start, y), Vector2(start + spacing * (total - 1), y), Color("#6b5434"), 2.0, true)
	for i in total:
		var c := Vector2(start + spacing * i, y)
		if i < progress_value:
			task_dots.draw_circle(c, 9.5, Color(1.0, 0.78, 0.32, 0.28))
			task_dots.draw_circle(c, 7.0, Color("#f6b73c"))
			task_dots.draw_circle(c + Vector2(-2, -2), 2.6, Color("#fff1c4"))
			task_dots.draw_arc(c, 7.0, 0, TAU, 20, Color("#8a5a14"), 1.3, true)
		else:
			task_dots.draw_circle(c, 7.0, Color("#5e5547"))
			task_dots.draw_circle(c + Vector2(-1.5, -1.5), 2.2, Color("#8d8270"))
			task_dots.draw_arc(c, 7.0, 0, TAU, 20, Color("#3a3128"), 1.3, true)

func set_task(title: String, value: int, total: int) -> void:
	task_title.text = title
	progress_value = clampi(value, 0, maxi(1, total))
	progress_total = maxi(1, total)
	task_count.text = "%d / %d" % [progress_value, progress_total]
	task_dots.custom_minimum_size.x = clampf(26.0 * progress_total + 8.0, 70.0, 150.0)
	task_dots.queue_redraw()

func set_reward(caption: String, resources: Dictionary) -> void:
	reward_caption.text = caption
	reward_caption.visible = not caption.is_empty()
	for key in STRIP_ORDER:
		var amount := int(resources.get(key, 0))
		reward_amounts[key].text = "+" + game.content.format_amount(amount) if amount > 0 else "—"
		reward_cells[key].modulate.a = 1.0 if amount > 0 else 0.55

func set_continue(caption: String, enabled: bool) -> void:
	continue_caption.text = caption
	continue_button.disabled = not enabled
	continue_button.tooltip_text = caption

func strip_center() -> Vector2:
	return reward_strip.get_global_rect().get_center() if is_instance_valid(reward_strip) else Vector2.ZERO

func _on_card_input(event: InputEvent, which: String) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if which == "journal":
			game.open_journal()
		else:
			game.open_rewards()

func _on_locked_close() -> void:
	locked_dismissed = true
	locked_card.hide()

# ---------------------------------------------------------------- hint, toasts, banner
func build_hint() -> void:
	hint = PanelContainer.new()
	hint.name = "HintPill"
	hint.add_theme_stylebox_override("panel", Style.hint_pill())
	hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(hint)
	hint_label = Style.label("", 17, Style.IVORY, false, 0)
	hint_label.name = "HintLabel"
	hint_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint_label.max_lines_visible = 2
	hint.add_child(hint_label)
	hint.hide()

func set_hint(value: String) -> void:
	hint_label.text = value
	hint.visible = not value.is_empty() and bar.visible
	layout_hint()

func build_toasts() -> void:
	toasts = VBoxContainer.new()
	toasts.name = "Toasts"
	toasts.alignment = BoxContainer.ALIGNMENT_BEGIN
	toasts.add_theme_constant_override("separation", 6)
	toasts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toasts.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	toasts.offset_left = -330
	toasts.offset_right = 330
	toasts.offset_top = 64
	add_child(toasts)

func toast(value: String, kind := "info", seconds := 4.5) -> void:
	if value.is_empty():
		return
	for existing in toasts.get_children():
		if existing.get_meta("text", "") == value:
			existing.set_meta("until", Time.get_ticks_msec() + seconds * 1000.0)
			return
	var pill := PanelContainer.new()
	var colors := {"info":Color("#8f7346"), "reward":Color("#e8c36f"), "error":Color("#c9694e"), "network":Color("#6f8fa8")}
	pill.add_theme_stylebox_override("panel", Style.frame(Color("#231c14e6"), Color("#15110ce6"), colors.get(kind, Color("#8f7346")), 12, 2, Vector4(16, 7, 16, 7)))
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.set_meta("text", value)
	pill.set_meta("until", Time.get_ticks_msec() + seconds * 1000.0)
	var label := Style.label(value, 17, Style.IVORY)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pill.add_child(label)
	toasts.add_child(pill)
	while toasts.get_child_count() > 3:
		var oldest := toasts.get_child(0)
		toasts.remove_child(oldest)
		oldest.queue_free()

func build_banner() -> void:
	banner = Control.new()
	banner.name = "Banner"
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	banner.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	banner.offset_left = -300
	banner.offset_right = 300
	banner.offset_top = 70
	banner.offset_bottom = 190
	add_child(banner)
	var column := VBoxContainer.new()
	banner_column = column
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	column.add_theme_constant_override("separation", -10)
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	banner.add_child(column)
	var medal := Art.new("medallion", Vector2(150, 50))
	medal.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(medal)
	var plate := PanelContainer.new()
	banner_plate = plate
	plate.name = "BannerPlate"
	plate.add_theme_stylebox_override("panel", Style.green_banner())
	plate.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plate.draw.connect(draw_banner_ribbons)
	column.add_child(plate)
	var words := VBoxContainer.new()
	words.add_theme_constant_override("separation", 0)
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plate.add_child(words)
	banner_title = Style.label("", 30, Style.IVORY, true, 4)
	banner_title.name = "BannerTitle"
	banner_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	words.add_child(banner_title)
	banner_sub = Style.label("", 16, Color("#e3d7b8"), false, 3)
	banner_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	banner_sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	banner_sub.custom_minimum_size.x = 380
	words.add_child(banner_sub)
	banner.hide()

func draw_banner_ribbons() -> void:
	# Red ribbon tails behind the plate edges (art/18 centre), drawn in the plate's own space.
	var rect := Rect2(Vector2.ZERO, banner_plate.size)
	for side in [-1.0, 1.0]:
		var x: float = rect.position.x if side < 0 else rect.end.x
		var y := rect.position.y + 10.0
		var h := rect.size.y - 6.0
		var out: float = x + side * 30.0
		var tail := PackedVector2Array([Vector2(x, y), Vector2(out, y + 6.0), Vector2(out - side * 11.0, y + h * 0.55),
			Vector2(out, y + h), Vector2(x, y + h - 4.0)])
		banner_plate.draw_colored_polygon(tail, Color("#8b2a1c"))
		banner_plate.draw_polyline(PackedVector2Array([tail[0], tail[1], tail[2], tail[3], tail[4]]), Color("#4f150e"), 2.0, true)

func show_banner(title: String, subtitle := "", seconds := 4.0) -> void:
	banner_title.text = title
	banner_sub.text = subtitle
	banner_sub.visible = not subtitle.is_empty()
	banner.show()
	toasts.offset_top = 196
	banner.modulate.a = 0.0
	var tween := create_tween()
	tween.tween_property(banner, "modulate:a", 1.0, 0.35)
	banner_until = Time.get_ticks_msec() + seconds * 1000.0 if seconds > 0.0 else INF
	banner.queue_redraw()

func hide_banner() -> void:
	banner_until = 0.0
	banner.hide()
	toasts.offset_top = 64

# ---------------------------------------------------------------- locked card (art/18 left)
func build_locked_card() -> void:
	locked_card = PanelContainer.new()
	locked_card.name = "LockedCard"
	locked_card.add_theme_stylebox_override("panel", Style.slate_card())
	locked_card.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(locked_card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	locked_card.add_child(column)
	var header := HBoxContainer.new()
	header.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(header)
	var left_space := Control.new()
	left_space.custom_minimum_size = Vector2(36, 0)
	left_space.mouse_filter = Control.MOUSE_FILTER_IGNORE
	header.add_child(left_space)
	var medal := Art.new("medallion", Vector2(170, 52))
	medal.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(medal)
	var close := Button.new()
	close.name = "LockedClose"
	close.text = "×"
	close.flat = true
	close.custom_minimum_size = Vector2(36, 36)
	close.tooltip_text = text("button.close")
	close.accessibility_name = text("button.close")
	close.add_theme_color_override("font_color", Color("#d9c9a4"))
	close.add_theme_font_size_override("font_size", 24)
	close.pressed.connect(_on_locked_close)
	header.add_child(close)
	locked_title = Style.label(text("forest.locked.title"), 31, Style.IVORY, true, 0)
	locked_title.name = "LockedTitle"
	locked_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(locked_title)
	locked_body = Style.label(text("forest.locked.body"), 19, Color("#e2d6bd"), true, 0)
	locked_body.name = "LockedBody"
	locked_body.add_theme_font_override("font", Style.italic())
	locked_body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	locked_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	locked_body.custom_minimum_size.x = 400
	column.add_child(locked_body)
	locked_progress = Style.label("", 16, Color("#b9ae96"), false, 0)
	locked_progress.name = "LockedProgress"
	locked_progress.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(locked_progress)
	locked_cta = Button.new()
	locked_cta.name = "LockedCta"
	locked_cta.text = text("forest.locked.cta")
	locked_cta.custom_minimum_size = Vector2(300, 54)
	locked_cta.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	locked_cta.add_theme_font_override("font", Style.TITLE_FONT)
	locked_cta.add_theme_font_size_override("font_size", 23)
	Style.apply_button(locked_cta, "red")
	locked_cta.pressed.connect(func(): game.open_town_hall())
	column.add_child(locked_cta)
	locked_card.hide()

func show_locked(reason: String) -> void:
	locked_reason = reason
	if reason in ["unavailable", "error"]:
		locked_body.text = text("hud.unavailable") if reason == "unavailable" else game.client.load_error()
		locked_progress.hide()
		locked_cta.hide()
	else:
		locked_body.text = text("forest.locked.body")
		locked_progress.text = text("forest.locked.progress", {"level":clampi(game.client.hall_level() if game.client.known else game.main.hall_level(), 1, 3)})
		locked_progress.show()
		locked_cta.show()
	locked_card.show()
	locked_card.modulate.a = 0.0
	create_tween().tween_property(locked_card, "modulate:a", 1.0, 0.2)
	layout()

func hide_locked() -> void:
	locked_card.hide()

# ---------------------------------------------------------------- invite / battle header
func build_invite() -> void:
	invite_button = Button.new()
	invite_button.name = "IntroInvite"
	invite_button.custom_minimum_size = Vector2(250, 50)
	invite_button.add_theme_font_override("font", Style.TITLE_FONT)
	invite_button.add_theme_font_size_override("font_size", 19)
	Style.apply_button(invite_button, "red")
	invite_button.pressed.connect(func(): game.intro.invite_pressed())
	add_child(invite_button)
	invite_button.hide()

## Compact battle panel (art/08): one slim block at the top edge, left of the DRENOVAR resource
## row — name · timer · «Отступить» on one line, a thin HP bar, the current telegraph warning in
## one short line. It never covers the fight: the fight camera frames the boss below it.
func build_battle_header() -> void:
	battle_header = PanelContainer.new()
	battle_header.name = "BattleHeader"
	var panel: StyleBoxTexture = Style.dark_panel().duplicate()
	panel.content_margin_top = 6
	panel.content_margin_bottom = 6
	panel.content_margin_left = 12
	panel.content_margin_right = 12
	battle_header.add_theme_stylebox_override("panel", panel)
	battle_header.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(battle_header)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 3)
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	battle_header.add_child(column)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(row)
	battle_title = Style.label("", 16, Style.IVORY, true, 0)
	battle_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	battle_title.clip_text = true
	row.add_child(battle_title)
	battle_timer = Style.label("", 14, Color("#ffd49a"), false, 0)
	row.add_child(battle_timer)
	battle_retreat = Button.new()
	battle_retreat.text = text("boss.retreat")
	battle_retreat.custom_minimum_size = Vector2(0, 26)
	battle_retreat.add_theme_font_size_override("font_size", 13)
	Style.apply_button(battle_retreat, "leather")
	battle_retreat.pressed.connect(func(): game.request_action("retreat"))
	row.add_child(battle_retreat)
	battle_bar = ProgressBar.new()
	battle_bar.custom_minimum_size = Vector2(380, 8)
	battle_bar.show_percentage = false
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color("#c4472f")
	fill.set_corner_radius_all(3)
	var back := StyleBoxFlat.new()
	back.bg_color = Color("#2a1712")
	back.border_color = Color("#8a6a3c")
	back.set_border_width_all(1)
	back.set_corner_radius_all(3)
	battle_bar.add_theme_stylebox_override("fill", fill)
	battle_bar.add_theme_stylebox_override("background", back)
	column.add_child(battle_bar)
	battle_sub = Style.label("", 13, Color("#ffd49a"), false, 0)
	battle_sub.clip_text = true
	battle_sub.custom_minimum_size.x = 380
	column.add_child(battle_sub)
	battle_header.hide()

func show_battle(title: String, hp: float, hp_max: float, sub: String, can_retreat: bool, timer := "") -> void:
	battle_title.text = title
	battle_bar.max_value = maxf(1.0, hp_max)
	battle_bar.value = clampf(hp, 0.0, battle_bar.max_value)
	battle_sub.text = sub
	battle_sub.visible = not sub.is_empty()
	battle_timer.text = timer
	battle_timer.visible = not timer.is_empty()
	battle_retreat.visible = can_retreat
	if not battle_header.visible:
		battle_header.show()
		layout()

func hide_battle() -> void:
	battle_header.hide()

# ---------------------------------------------------------------- off-screen target arrow
func set_arrow(target: Vector3, caption: String) -> void:
	arrow_target = target
	arrow_label = caption
	arrow.queue_redraw()

func draw_tags(camera: Camera3D) -> void:
	# Name plates over revealed places (site, Iskra, landmarks, boss) — readable from the top camera.
	var font: Font = Style.TITLE_FONT
	var view := get_viewport_rect().size
	var placed: Array[Rect2] = []
	for tag in game.actors.tags:
		var p: Vector3 = tag.position
		if camera.is_position_behind(p):
			continue
		var at := camera.unproject_position(p)
		if at.x < -40 or at.y < 40 or at.x > view.x + 40 or at.y > view.y - 100:
			continue
		var caption := String(tag.text)
		var kind := String(tag.get("kind", "site"))
		var size := 15 if kind in ["site", "boss"] else 14
		if kind == "site" and int(tag.get("step", 0)) > 0:
			caption += "  %d/5" % int(tag.step)
		var width := font.get_string_size(caption, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		var box := Rect2(at - Vector2(width * 0.5 + 9, 13), Vector2(width + 18, 24))
		var origin_y := box.position.y
		for attempt in 6:
			var clash := false
			for other in placed:
				if other.intersects(box.grow(1.0)):
					clash = true
			if not clash:
				break
			var step := 27.0 * float(attempt / 2 + 1)
			box.position.y = origin_y + (step if attempt % 2 == 0 else -step)
		var blocked: bool = box.position.y > view.y - 118.0 or (game.mech.is_open() and box.position.x < 490.0)
		if blocked:
			continue
		placed.append(box)
		at = box.position + Vector2(width * 0.5 + 9, 13)
		var fill := Color("#f1e3c1e6") if kind == "site" else (Color("#2a2219e0") if kind != "landmark" else Color("#3d2f14e8"))
		var ink := Color("#3a2716") if kind == "site" else Color("#f6ead0")
		arrow.draw_style_box(Style.frame(fill, fill.darkened(0.08), Color("#8b6a3c"), 6, 1, Vector4(0, 0, 0, 0)), box)
		arrow.draw_string(font, Vector2(box.position.x + 9, box.position.y + 17), caption, HORIZONTAL_ALIGNMENT_LEFT, -1, size, ink)
		if kind == "landmark":
			arrow.draw_circle(at + Vector2(0, 22), 5.0, Color(1.0, 0.8, 0.35, 0.6 + 0.4 * sin(Time.get_ticks_msec() / 200.0)))

func draw_arrow() -> void:
	var stage = game.main.stage
	if not is_instance_valid(stage) or not game.client.unlocked() or not game.city_active():
		return
	var camera: Camera3D = stage.camera
	if game.actors != null and not game.intro.presenting():
		draw_tags(camera)
	if arrow_target == Vector3.INF or not bar.visible:
		return
	if camera.is_position_behind(arrow_target):
		return
	var at := camera.unproject_position(arrow_target)
	var view := get_viewport_rect().size
	var margin := Rect2(Vector2(70, 110), view - Vector2(140, 230))
	if margin.has_point(at):
		return
	var center := view * 0.5
	var direction := (at - center).normalized()
	var limit := INF
	for axis in 2:
		if absf(direction[axis]) > 0.0001:
			var edge: float = (margin.end[axis] if direction[axis] > 0 else margin.position[axis]) - center[axis]
			limit = minf(limit, edge / direction[axis])
	var tip := center + direction * limit
	var pulse := 0.75 + 0.25 * sin(Time.get_ticks_msec() / 260.0)
	var side := Vector2(-direction.y, direction.x)
	var shape := PackedVector2Array([tip, tip - direction * 26.0 + side * 15.0, tip - direction * 18.0, tip - direction * 26.0 - side * 15.0])
	arrow.draw_colored_polygon(shape, Color(1.0, 0.8, 0.35, 0.92 * pulse))
	arrow.draw_polyline(PackedVector2Array([shape[0], shape[1], shape[2], shape[3], shape[0]]), Color("#4a2e10"), 2.0, true)
	if not arrow_label.is_empty():
		var font := get_theme_default_font()
		var width := font.get_string_size(arrow_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		var anchor := tip - direction * 48.0 - Vector2(width * 0.5, -5)
		anchor.x = clampf(anchor.x, 8.0, view.x - width - 8.0)
		arrow.draw_string_outline(font, anchor, arrow_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, 4, Color("#120d08"))
		arrow.draw_string(font, anchor, arrow_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("#ffe6b0"))

# ---------------------------------------------------------------- layout and per-frame
func nav_left_edge() -> float:
	var nav: Dictionary = game.main.nav_buttons
	var left := get_viewport_rect().size.x - 52.0
	for key in nav:
		var control: Control = nav[key]
		if is_instance_valid(control) and control.is_visible_in_tree():
			left = minf(left, control.get_parent().get_global_rect().position.x)
	return left

func layout() -> void:
	if bar == null:
		return
	var view := get_viewport_rect().size
	var right_edge := nav_left_edge() - 12.0
	var available := right_edge - 52.0
	# One row like art/07: task card, reward strip (fills the rest), three buttons; the existing
	# DRENOVAR navigation keeps the bottom-right corner, so the row ends where it begins.
	var buttons_width := 76.0 + 72.0 + 108.0 + 16.0
	var strip_min := 36.0 + 6.0 + 46.0 * 5.0 + 4.0 * 13.0 + 24.0
	compact = available < 200.0 + 16.0 + strip_min + 84.0 + buttons_width
	# «За спасение:» stays visible: inline beside the chest when there is room (art/07),
	# otherwise stacked under a smaller chest.
	reward_caption.visible = not reward_caption.text.is_empty()
	strip_head.vertical = compact
	reward_caption.add_theme_font_size_override("font_size", 11 if compact else 13)
	strip_chest.custom_minimum_size = Vector2(30, 30) if compact else Vector2(36, 40)
	task_card.custom_minimum_size.x = 200.0
	for key in reward_cells:
		reward_cells[key].custom_minimum_size.x = 46.0
	route_button.custom_minimum_size.x = 76.0
	squad_button.custom_minimum_size.x = 72.0
	continue_button.custom_minimum_size.x = 108.0
	reward_strip.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reward_strip.visible = available >= 200.0 + 16.0 + strip_min + buttons_width
	bar.position = Vector2(52, view.y - 84 - 8)
	bar.size = Vector2(maxf(available, 300.0), 84)
	layout_hint()
	if locked_card.visible:
		locked_card.reset_size()
		var card := locked_card.get_combined_minimum_size()
		locked_card.position = Vector2((view.x - card.x) * 0.5, view.y - card.y - 110.0)
	invite_button.reset_size()
	invite_button.position = Vector2((view.x - invite_button.size.x) * 0.5, 70)
	if battle_header.visible:
		battle_header.reset_size()
		var size_now := battle_header.get_combined_minimum_size()
		# Top edge, between the profile button and the resource row (≈ 57 % of the width).
		var lane_left := 150.0
		var lane_right := maxf(lane_left + size_now.x, view.x * 0.56)
		battle_header.position = Vector2(lane_left + (lane_right - lane_left - size_now.x) * 0.5, 6)
	last_nav_edge = right_edge

func layout_hint() -> void:
	if hint == null:
		return
	hint.reset_size()
	var width := minf(640.0, bar.size.x)
	hint_label.custom_minimum_size.x = width - 28.0
	hint.reset_size()
	hint.position = Vector2(52, bar.position.y - hint.get_combined_minimum_size().y - 8.0)

func tick(_delta: float) -> void:
	var now := Time.get_ticks_msec()
	if bar.visible and absf(nav_left_edge() - 12.0 - last_nav_edge) > 0.5:
		layout()
	for pill in toasts.get_children():
		var until := float(pill.get_meta("until", 0))
		if now > until:
			pill.modulate.a = maxf(0.0, pill.modulate.a - 0.05)
			if pill.modulate.a <= 0.01:
				pill.queue_free()
	if banner.visible and now > banner_until:
		banner.modulate.a = maxf(0.0, banner.modulate.a - 0.04)
		if banner.modulate.a <= 0.01:
			hide_banner()
	arrow.queue_redraw()
