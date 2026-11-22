class_name ActionRing
extends Control

# Round action buttons that open in an arc above a tapped building, with its name
# and level on an oak plate. The ring follows the building while the camera moves and
# closes on any other tap, window or scene change. Actions call existing panels
# and commands; nothing here talks to the server by itself.
#
# Premium UI stage 4a (ui_premium/STAGE4A.md): each action is a bronze medallion with a
# forged emblem (one drawn node, RingButton) and its caption under it; the main action
# sits on a gold disc. An action can carry options: {"soon": true} dims it under a «Скоро»
# ribbon (the level after the open one), {"ends": msec} shows the time left of the job the
# action speeds up, {"emblem": "kit_emb_bow"} picks another emblem.

const UiKit = preload("res://src/ui_kit.gd")
const BUTTON := 70.0
const RADIUS := 112.0
## Emblem of each action symbol; an unknown symbol draws its SVG from assets/ui/actions.
const EMBLEMS := {"upgrade": "kit_emb_up", "info": "kit_emb_info", "speed": "kit_emb_speed", "train": "kit_emb_inf",
	"heal": "kit_emb_heal", "trade": "kit_emb_trade", "defence": "kit_emb_shield", "collect": "kit_emb_sheaf",
	"move": "kit_emb_move", "research": "kit_emb_book", "queue": "kit_emb_speed", "army": "kit_emb_sword"}

var anchor := Vector3.ZERO
var camera: Camera3D
var plate: Label
var buttons: Array[Button] = []
var subject_id := ""
var opened_at := 0
var clock := Callable()

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	visible = false
	plate = Label.new()
	plate.name = "RingPlate"
	plate.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	plate.add_theme_font_override("font", UiKit.LABEL_FONT)
	plate.add_theme_font_size_override("font_size", 18)
	plate.add_theme_color_override("font_color", UiKit.GOLD)
	plate.add_theme_color_override("font_outline_color", Color("#14100b"))
	plate.add_theme_constant_override("outline_size", 4)
	plate.add_theme_stylebox_override("normal", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(30, 5, 30, 7)))
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(plate)

# actions: [[caption, icon name, Callable, options?], ...]
func open(id: String, title: String, at: Vector3, view: Camera3D, actions: Array) -> void:
	for old in buttons:
		old.queue_free()
	buttons.clear()
	subject_id = id
	anchor = at
	camera = view
	plate.text = title
	for index in actions.size():
		var action: Array = actions[index]
		var options: Dictionary = action[3] if action.size() > 3 and action[3] is Dictionary else {}
		var control := RingButton.new()
		control.flat = true
		control.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
		control.custom_minimum_size = Vector2(BUTTON, BUTTON + 24)
		control.size = control.custom_minimum_size
		control.tooltip_text = action[0]
		control.accessibility_name = action[0] + (" · скоро" if options.get("soon", false) else "")
		control.focus_mode = Control.FOCUS_NONE
		for state in ["normal", "hover", "pressed", "focus", "disabled"]:
			control.add_theme_stylebox_override(state, StyleBoxEmpty.new())
		control.primary = options.get("primary", index == 0) and not options.get("soon", false)
		control.soon = options.get("soon", false)
		control.ends = float(options.get("ends", 0.0))
		control.clock = clock
		var emblem_name: String = options.get("emblem", EMBLEMS.get(action[1], ""))
		if not emblem_name.is_empty():
			control.emblem = UiKit.tex(emblem_name)
		if control.emblem == null and ResourceLoader.exists("res://assets/ui/actions/%s.svg" % action[1]):
			control.glyph = load("res://assets/ui/actions/%s.svg" % action[1])
		# The caption stays a Label (tests and screen readers read it); premium type.
		var caption := Label.new()
		caption.text = action[0]
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.add_theme_font_override("font", UiKit.LABEL_FONT)
		caption.add_theme_font_size_override("font_size", 15)
		caption.add_theme_color_override("font_color", Color("#fff1d2") if not control.soon else Color("#d9cdb5"))
		caption.add_theme_color_override("font_outline_color", Color("#120c07"))
		caption.add_theme_constant_override("outline_size", 7)
		caption.position = Vector2(-22, BUTTON + 1)
		caption.size = Vector2(BUTTON + 44, 22)
		caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
		control.add_child(caption)
		var callback: Callable = action[2]
		control.pressed.connect(func():
			close()
			callback.call())
		add_child(control)
		buttons.append(control)
	opened_at = Time.get_ticks_msec()
	visible = true
	follow()
	# Pop in: each medallion grows from the building in turn.
	for index in buttons.size():
		var item := buttons[index]
		item.modulate.a = 0.0
		item.pivot_offset = Vector2(BUTTON, BUTTON) * 0.5
		item.scale = Vector2.ONE * 0.6
		var tween := create_tween().set_parallel(true)
		tween.tween_property(item, "modulate:a", 1.0, 0.12).set_delay(index * 0.025)
		tween.tween_property(item, "scale", Vector2.ONE, 0.16).set_delay(index * 0.025).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

func close() -> void:
	visible = false
	subject_id = ""

func is_open() -> bool:
	return visible

var last_second := -1

func _process(_delta: float) -> void:
	if visible:
		follow()
		# The time on a speed-up medallion changes once a second.
		var second := Time.get_ticks_msec() / 1000
		if second != last_second:
			last_second = second
			for item in buttons:
				if item is RingButton and item.ends > 0.0:
					item.queue_redraw()

func follow() -> void:
	if not is_instance_valid(camera) or camera.is_position_behind(anchor):
		close()
		return
	var centre := camera.unproject_position(anchor)
	var count := buttons.size()
	# Spread over an upper arc; wider for more buttons.
	var spread := deg_to_rad(minf(170.0, 47.0 * maxf(1.0, count - 1)))
	for index in count:
		var t := 0.5 if count == 1 else float(index) / (count - 1)
		var angle := -PI * 0.5 - spread * 0.5 + spread * t
		var at := centre + Vector2(cos(angle), sin(angle)) * RADIUS
		buttons[index].position = at - Vector2(BUTTON, BUTTON) * 0.5
	plate.reset_size()
	plate.position = centre + Vector2(-plate.size.x * 0.5, 24.0)

## A ring action in one drawn node: the bronze (or gold) medallion and its emblem; «Скоро»
## dims it under a small ribbon; a speed-up shows the time left on a plate at its foot.
class RingButton extends Button:
	var emblem: Texture2D
	var glyph: Texture2D
	var primary := false
	var soon := false
	var ends := 0.0
	var clock := Callable()

	func _draw() -> void:
		var pressed_now := get_draw_mode() == DRAW_PRESSED or get_draw_mode() == DRAW_HOVER_PRESSED
		var d := BUTTON - (4.0 if pressed_now else 0.0)
		var centre := Vector2(BUTTON * 0.5, BUTTON * 0.5 + (1.5 if pressed_now else 0.0))
		draw_circle(centre + Vector2(0, 2.5), d * 0.5 + 2.0, Color(0, 0, 0, 0.35), true, -1.0, true)
		var tone := Color(0.72, 0.7, 0.68) if soon else (Color(0.82, 0.78, 0.74) if pressed_now else Color.WHITE)
		draw_texture_rect(UiKit.tex("kit_rail_on" if primary else "kit_rail"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false, tone)
		var side := d * 0.6
		if emblem != null:
			draw_texture_rect(emblem, Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false, Color(0.7, 0.68, 0.66, 0.85) if soon else tone)
		elif glyph != null:
			draw_texture_rect(glyph, Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false, tone)
		if soon:
			# «Скоро»: a small oak ribbon across the lower rim.
			var word := UiKit.KitText.line("Скоро", UiKit.LABEL_FONT, 13)
			var ribbon := Rect2(centre.x - word.get_size().x * 0.5 - 9.0, centre.y + d * 0.18, word.get_size().x + 18.0, 19.0)
			draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), ribbon)
			word.draw(get_canvas_item(), Vector2(ribbon.position.x + 9.0, ribbon.position.y + roundf((ribbon.size.y - word.get_size().y) * 0.5)), UiKit.GOLD)
		elif ends > 0.0 and clock.is_valid():
			var left := maxf(0.0, ends - float(clock.call()))
			var seconds := ceili(left / 1000.0)
			var value := "%d:%02d:%02d" % [seconds / 3600, (seconds / 60) % 60, seconds % 60] if seconds >= 3600 else "%d:%02d" % [seconds / 60, seconds % 60]
			var word := UiKit.KitText.line(value, UiKit.LABEL_FONT, 13)
			var ribbon := Rect2(centre.x - word.get_size().x * 0.5 - 8.0, centre.y + d * 0.2, word.get_size().x + 16.0, 19.0)
			draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), ribbon)
			word.draw(get_canvas_item(), Vector2(ribbon.position.x + 8.0, ribbon.position.y + roundf((ribbon.size.y - word.get_size().y) * 0.5)), UiKit.GOLD)
