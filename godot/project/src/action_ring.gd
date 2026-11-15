class_name ActionRing
extends Control

# Round action buttons that open in an arc above a tapped building, with its name
# and level on a plate. The ring follows the building while the camera moves and
# closes on any other tap, window or scene change. Actions call existing panels
# and commands; nothing here talks to the server by itself.

const BUTTON := 66.0
const RADIUS := 92.0

var anchor := Vector3.ZERO
var camera: Camera3D
var plate: Label
var buttons: Array[Button] = []
var subject_id := ""
var opened_at := 0

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	visible = false
	plate = Label.new()
	plate.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	plate.add_theme_font_size_override("font_size", 17)
	plate.add_theme_color_override("font_color", Color("#fff1d2"))
	plate.add_theme_color_override("font_outline_color", Color("#14100b"))
	plate.add_theme_constant_override("outline_size", 7)
	var back := StyleBoxFlat.new()
	back.bg_color = Color(0.07, 0.08, 0.09, 0.78)
	back.border_color = Color("#a4814d")
	back.set_border_width_all(1)
	back.set_corner_radius_all(6)
	back.content_margin_left = 12
	back.content_margin_right = 12
	back.content_margin_top = 3
	back.content_margin_bottom = 3
	plate.add_theme_stylebox_override("normal", back)
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(plate)

# actions: [[caption, icon name, Callable], ...]
func open(id: String, title: String, at: Vector3, view: Camera3D, actions: Array) -> void:
	for old in buttons:
		old.queue_free()
	buttons.clear()
	subject_id = id
	anchor = at
	camera = view
	plate.text = title
	for action in actions:
		var control := Button.new()
		control.flat = true
		control.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
		control.custom_minimum_size = Vector2(BUTTON, BUTTON + 20)
		control.size = control.custom_minimum_size
		control.tooltip_text = action[0]
		control.accessibility_name = action[0]
		for state in ["normal", "hover", "pressed", "focus", "disabled"]:
			control.add_theme_stylebox_override(state, StyleBoxEmpty.new())
		var icon := TextureRect.new()
		icon.texture = load("res://assets/ui/actions/%s.svg" % action[1])
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.size = Vector2(BUTTON, BUTTON)
		icon.pivot_offset = Vector2(BUTTON, BUTTON) * 0.5
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		control.add_child(icon)
		var caption := Label.new()
		caption.text = action[0]
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.add_theme_font_size_override("font_size", 13)
		caption.add_theme_color_override("font_color", Color("#fff1d2"))
		caption.add_theme_color_override("font_outline_color", Color("#14100b"))
		caption.add_theme_constant_override("outline_size", 6)
		caption.position = Vector2(-14, BUTTON - 4)
		caption.size = Vector2(BUTTON + 28, 20)
		caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
		control.add_child(caption)
		# Immediate touch-down feedback, like the HUD buttons.
		control.button_down.connect(func(): icon.scale = Vector2.ONE * 0.9; icon.modulate = Color(0.8, 0.8, 0.8))
		control.button_up.connect(func(): icon.scale = Vector2.ONE; icon.modulate = Color.WHITE)
		var callback: Callable = action[2]
		control.pressed.connect(func():
			close()
			callback.call())
		add_child(control)
		buttons.append(control)
	opened_at = Time.get_ticks_msec()
	visible = true
	follow()
	# Pop in.
	for index in buttons.size():
		var item := buttons[index]
		item.modulate.a = 0.0
		var tween := create_tween()
		tween.tween_interval(index * 0.025)
		tween.tween_property(item, "modulate:a", 1.0, 0.12)

func close() -> void:
	visible = false
	subject_id = ""

func is_open() -> bool:
	return visible

func _process(_delta: float) -> void:
	if visible:
		follow()

func follow() -> void:
	if not is_instance_valid(camera) or camera.is_position_behind(anchor):
		close()
		return
	var centre := camera.unproject_position(anchor)
	var count := buttons.size()
	# Spread over an upper arc; wider for more buttons.
	var spread := deg_to_rad(minf(150.0, 42.0 * maxf(1.0, count - 1)))
	for index in count:
		var t := 0.5 if count == 1 else float(index) / (count - 1)
		var angle := -PI * 0.5 - spread * 0.5 + spread * t
		var at := centre + Vector2(cos(angle), sin(angle)) * RADIUS
		buttons[index].position = at - Vector2(BUTTON, BUTTON) * 0.5
	plate.reset_size()
	plate.position = centre + Vector2(-plate.size.x * 0.5, 26.0)
