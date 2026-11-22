extends Control
## Placing a new building in the city (premium UI stage 3, ui_premium/STAGE3.md): a carved
## plate at the top names the building and offers the plot list and «Отмена»; a tap on a
## glowing plot opens a compact floating confirm over it (src/v6_build.gd pick_plot): the
## plot, the cost with icons (red where the stock is short), the time and «Построить», which
## turns on once the server has quoted the build on that plot.

const UiKit = preload("res://src/ui_kit.gd")

var build
var banner: PanelContainer
var banner_title: Label
var banner_info: Label
var bubble: PanelContainer
var bubble_title: Label
var cost_row: HBoxContainer
var time_label: Label
var problem: Label
var go: Button
var anchor := Vector3.INF
var cost := {}
var appear: Tween

func _ready() -> void:
	name = "BuildPlace"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	make_banner()
	make_bubble()
	hide()

func make_banner() -> void:
	banner = PanelContainer.new()
	banner.name = "PlacementBanner"
	banner.add_theme_stylebox_override("panel", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(34, 8, 34, 10)))
	banner.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(banner)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	banner.add_child(row)
	var words := VBoxContainer.new()
	words.add_theme_constant_override("separation", -2)
	words.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(words)
	banner_title = label(words, "", UiKit.TITLE_FONT, 24, UiKit.GOLD)
	banner_info = label(words, "", UiKit.LABEL_FONT, 16, UiKit.IVORY)
	var list := Button.new()
	list.name = "PlacementList"
	list.text = "Списком"
	UiKit.style_button(list, "tertiary", 18)
	list.custom_minimum_size = Vector2(132, 46)
	list.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	list.pressed.connect(func(): build.plot_list())
	row.add_child(list)
	var cancel := Button.new()
	cancel.name = "PlacementCancel"
	cancel.text = "Отмена"
	UiKit.style_button(cancel, "secondary", 18)
	cancel.custom_minimum_size = Vector2(124, 46)
	cancel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	cancel.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
	cancel.pressed.connect(func(): build.cancel_placement())
	row.add_child(cancel)

## The small pointer of the floating confirm toward the plot; `toward` is the side of the
## bubble it sits on (and points out of): "left", "right", "down" or "up".
class Pointer extends Control:
	const LONG := 26.0
	const DEEP := 14.0
	var toward := "down":
		set(value):
			if toward != value:
				toward = value
				queue_redraw()

	func _draw() -> void:
		var outer: PackedVector2Array
		var inner: PackedVector2Array
		match toward:
			"left":
				outer = PackedVector2Array([Vector2(DEEP, 0), Vector2(DEEP, LONG), Vector2(0, LONG * 0.5)])
				inner = PackedVector2Array([Vector2(DEEP + 1, 3), Vector2(DEEP + 1, LONG - 3), Vector2(4, LONG * 0.5)])
			"right":
				outer = PackedVector2Array([Vector2(0, 0), Vector2(0, LONG), Vector2(DEEP, LONG * 0.5)])
				inner = PackedVector2Array([Vector2(-1, 3), Vector2(-1, LONG - 3), Vector2(DEEP - 4, LONG * 0.5)])
			"up":
				outer = PackedVector2Array([Vector2(0, DEEP), Vector2(LONG, DEEP), Vector2(LONG * 0.5, 0)])
				inner = PackedVector2Array([Vector2(3, DEEP + 1), Vector2(LONG - 3, DEEP + 1), Vector2(LONG * 0.5, 4)])
			_:
				outer = PackedVector2Array([Vector2(0, 0), Vector2(LONG, 0), Vector2(LONG * 0.5, DEEP)])
				inner = PackedVector2Array([Vector2(3, -1), Vector2(LONG - 3, -1), Vector2(LONG * 0.5, DEEP - 4)])
		draw_colored_polygon(outer, Color("#b8873e"))
		draw_colored_polygon(inner, Color("#f4e8cf"))

var pointer: Control

func make_bubble() -> void:
	bubble = PanelContainer.new()
	bubble.name = "PlacementConfirm"
	bubble.add_theme_stylebox_override("panel", UiKit.flat(Color("#f4e8cff4"), Color("#b8873e"), 10, Vector2(18, 12), 2))
	bubble.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(bubble)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	bubble.add_child(column)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 10)
	column.add_child(head)
	bubble_title = label(head, "", UiKit.LABEL_FONT, 19, UiKit.INK)
	bubble_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var close := Button.new()
	close.name = "PlacementDeselect"
	close.text = "✕"
	close.flat = true
	close.add_theme_font_override("font", UiKit.LABEL_FONT)
	close.add_theme_font_size_override("font_size", 20)
	close.add_theme_color_override("font_color", UiKit.INK_MUTED)
	close.custom_minimum_size = Vector2(40, 34)
	close.pressed.connect(deselect)
	head.add_child(close)
	cost_row = HBoxContainer.new()
	cost_row.name = "PlacementCost"
	cost_row.add_theme_constant_override("separation", 14)
	column.add_child(cost_row)
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 14)
	column.add_child(foot)
	var clock := TextureRect.new()
	clock.texture = UiKit.tex("kit_hourglass")
	clock.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	clock.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	clock.custom_minimum_size = Vector2(18, 22)
	clock.modulate = Color(0.55, 0.4, 0.2)
	clock.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	foot.add_child(clock)
	time_label = label(foot, "", UiKit.LABEL_FONT, 18, UiKit.BRONZE)
	time_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	go = Button.new()
	go.name = "PlacementBuild"
	go.text = "Построить"
	UiKit.style_button(go, "primary", 19)
	go.custom_minimum_size = Vector2(168, 48)
	go.pressed.connect(func(): build.confirm_build())
	foot.add_child(go)
	problem = label(column, "", UiKit.LABEL_FONT, 16, UiKit.BAD)
	problem.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	problem.custom_minimum_size.x = 300
	problem.hide()
	bubble.hide()
	pointer = Pointer.new()
	pointer.name = "PlacementPointer"
	pointer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pointer.size = Vector2(26, 14)
	add_child(pointer)
	pointer.hide()

func label(parent: Node, text: String, font: Font, size: int, colour: Color) -> Label:
	var line := Label.new()
	line.text = text
	line.add_theme_font_override("font", font)
	line.add_theme_font_size_override("font_size", size)
	line.add_theme_color_override("font_color", colour)
	if colour == UiKit.GOLD or colour == UiKit.IVORY:
		line.add_theme_color_override("font_outline_color", UiKit.SHADE)
		line.add_theme_constant_override("outline_size", 4)
	line.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(line)
	return line

func begin(title: String, count: int) -> void:
	banner_title.text = title
	banner_info.text = "Коснитесь светящегося участка · подходит %d" % count
	bubble.hide()
	anchor = Vector3.INF
	show()
	banner.size = banner.get_combined_minimum_size()
	banner.position = Vector2(roundf((get_viewport_rect().size.x - banner.size.x) * 0.5), -banner.size.y)
	if appear != null:
		appear.kill()
	appear = create_tween()
	# Under the top row of the city (profile, resources), in the middle.
	appear.tween_property(banner, "position:y", 58.0, 0.22).set_delay(0.12).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	set_process(true)

## The floating confirm for a plot; `plot_title` is its human name (V6Build.plot_name).
func show_offer(at: Vector3, price: Dictionary, time_text: String, plot_title: String) -> void:
	anchor = at
	bubble_title.text = plot_title
	fill_cost(price)
	time_label.text = time_text
	problem.hide()
	go.disabled = true
	go.text = "Расчёт…"
	bubble.show()
	bubble.size = bubble.get_combined_minimum_size()
	bubble.pivot_offset = Vector2(0.0, bubble.size.y * 0.5)
	bubble.scale = Vector2(0.9, 0.9)
	bubble.modulate.a = 0.0
	var pop := create_tween().set_parallel()
	pop.tween_property(bubble, "scale", Vector2.ONE, 0.14).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	pop.tween_property(bubble, "modulate:a", 1.0, 0.1)

func show_quote(price: Dictionary, time_text: String, failure: String) -> void:
	fill_cost(price)
	time_label.text = time_text
	go.text = "Построить"
	go.disabled = not failure.is_empty()
	problem.text = failure
	problem.visible = not failure.is_empty()
	bubble.size = bubble.get_combined_minimum_size()

func fill_cost(price: Dictionary) -> void:
	cost = price
	for child in cost_row.get_children():
		child.queue_free()
	var stock: Dictionary = build.ui.state.v6.get("stock", {})
	for resource: String in price:
		var amount := int(price[resource])
		if amount <= 0:
			continue
		var cell := HBoxContainer.new()
		cell.add_theme_constant_override("separation", 4)
		cell.tooltip_text = "%s: %d" % [build.ui.RESOURCE_NAMES.get(resource, resource), amount]
		cost_row.add_child(cell)
		var icon := TextureRect.new()
		icon.texture = build.ui.resource_icons.get(resource)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.custom_minimum_size = Vector2(26, 26)
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		cell.add_child(icon)
		label(cell, UiKit.compact(amount), UiKit.LABEL_FONT, 18, UiKit.BAD if amount > int(stock.get(resource, 0)) else UiKit.INK)

func deselect() -> void:
	bubble.hide()
	pointer.hide()
	anchor = Vector3.INF
	if build.placing_active():
		build.placing.plot = ""
		build.quote_serial += 1

func finish() -> void:
	bubble.hide()
	pointer.hide()
	anchor = Vector3.INF
	set_process(false)
	hide()

func covers(at: Vector2) -> bool:
	if not visible:
		return false
	return banner.get_global_rect().grow(8).has_point(at) or (bubble.visible and bubble.get_global_rect().grow(8).has_point(at))

## Screen rect of the chosen plot with its ghost: the ring round it and the building's head
## room above it. The floating confirm never covers it.
const PLOT_REACH := 6.5
const GHOST_HEIGHT := 8.0
const SAFE_TOP := 130.0
const GAP := 18.0

func plot_rect(camera: Camera3D) -> Rect2:
	var box := Rect2()
	var first := true
	for offset: Vector3 in [Vector3(PLOT_REACH, 0, 0), Vector3(-PLOT_REACH, 0, 0), Vector3(0, 0, PLOT_REACH), Vector3(0, 0, -PLOT_REACH),
			Vector3(PLOT_REACH * 0.7, GHOST_HEIGHT, PLOT_REACH * 0.7), Vector3(-PLOT_REACH * 0.7, GHOST_HEIGHT, -PLOT_REACH * 0.7),
			Vector3(PLOT_REACH * 0.7, GHOST_HEIGHT, -PLOT_REACH * 0.7), Vector3(-PLOT_REACH * 0.7, GHOST_HEIGHT, PLOT_REACH * 0.7)]:
		var point := camera.unproject_position(anchor + offset)
		if first:
			box = Rect2(point, Vector2.ZERO)
			first = false
		else:
			box = box.expand(point)
	return box

## Where the floating confirm goes: beside the plot (right, then left), else above or below
## it, inside the safe part of the screen and never over the plot.
func bubble_place(plot: Rect2, bubble_size: Vector2, view: Vector2) -> Array:
	var centre := plot.get_center()
	var candidates := [
		["left", Vector2(plot.end.x + GAP, centre.y - bubble_size.y * 0.5)],
		["right", Vector2(plot.position.x - GAP - bubble_size.x, centre.y - bubble_size.y * 0.5)],
		["down", Vector2(centre.x - bubble_size.x * 0.5, plot.position.y - GAP - bubble_size.y)],
		["up", Vector2(centre.x - bubble_size.x * 0.5, plot.end.y + GAP)]]
	var keep_clear := plot.grow(6.0)
	for candidate: Array in candidates:
		var at: Vector2 = candidate[1]
		at = Vector2(clampf(at.x, 12.0, view.x - bubble_size.x - 12.0), clampf(at.y, SAFE_TOP, view.y - bubble_size.y - 12.0))
		if not Rect2(at, bubble_size).intersects(keep_clear):
			return [candidate[0], at]
	# No room anywhere (a plot that fills the screen): beside it, as far right as it goes.
	return ["left", Vector2(view.x - bubble_size.x - 12.0, clampf(centre.y - bubble_size.y * 0.5, SAFE_TOP, view.y - bubble_size.y - 12.0))]

func _process(_delta: float) -> void:
	if not bubble.visible or anchor == Vector3.INF or not is_instance_valid(build.ui.stage):
		return
	var camera: Camera3D = build.ui.stage.camera
	if camera.is_position_behind(anchor):
		return
	var view := get_viewport_rect().size
	bubble.size = bubble.get_combined_minimum_size()
	var plot := plot_rect(camera)
	var placed := bubble_place(plot, bubble.size, view)
	bubble.position = placed[1]
	var side: String = placed[0]
	pointer.toward = side
	var centre := plot.get_center()
	var long := Pointer.LONG
	var deep := Pointer.DEEP
	match side:
		"left":
			pointer.size = Vector2(deep, long)
			pointer.position = Vector2(bubble.position.x - deep + 1.0, clampf(centre.y - long * 0.5, bubble.position.y + 10.0, bubble.position.y + bubble.size.y - long - 10.0))
		"right":
			pointer.size = Vector2(deep, long)
			pointer.position = Vector2(bubble.position.x + bubble.size.x - 1.0, clampf(centre.y - long * 0.5, bubble.position.y + 10.0, bubble.position.y + bubble.size.y - long - 10.0))
		"up":
			pointer.size = Vector2(long, deep)
			pointer.position = Vector2(clampf(centre.x - long * 0.5, bubble.position.x + 12.0, bubble.position.x + bubble.size.x - long - 12.0), bubble.position.y - deep + 1.0)
		_:
			pointer.size = Vector2(long, deep)
			pointer.position = Vector2(clampf(centre.x - long * 0.5, bubble.position.x + 12.0, bubble.position.x + bubble.size.x - long - 12.0), bubble.position.y + bubble.size.y - 1.0)
	pointer.visible = bubble.visible
