extends CanvasLayer

const CREST = preload("res://assets/icons/drenovar_icon_512.png")
const TITLE_FONT = preload("res://assets/ui/NotoSerif-Regular.ttf")

var panel := Control.new()
var status: Label
var progress: ProgressBar

func _ready() -> void:
	layer = 10
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panel.mouse_filter = Control.MOUSE_FILTER_STOP

	var scene := TextureRect.new()
	scene.texture = load("res://assets/intro/keep-wide.png")
	scene.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	scene.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	panel.add_child(scene)
	scene.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scene.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var shade := ColorRect.new()
	shade.color = Color(0.02, 0.04, 0.06, 0.32)
	panel.add_child(shade)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var stack := VBoxContainer.new()
	panel.add_child(stack)
	stack.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	stack.offset_left = -370
	stack.offset_right = 370
	stack.offset_top = -147
	stack.offset_bottom = 75
	stack.add_theme_constant_override("separation", 9)
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var crest := TextureRect.new()
	crest.texture = CREST
	crest.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	crest.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	crest.custom_minimum_size = Vector2(88, 88)
	crest.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	crest.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(crest)
	stack.add_child(centered_label("D R E N O V A R", 63, Color("#f3e8d4"), true))
	stack.add_child(centered_label("ЗЕМЛИ СЕМИ ЗНАМЁН", 19, Color("#f1cd90")))

	var footer := VBoxContainer.new()
	panel.add_child(footer)
	footer.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	footer.offset_left = -205
	footer.offset_right = 205
	footer.offset_top = -105
	footer.offset_bottom = -48
	footer.add_theme_constant_override("separation", 12)
	footer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	status = centered_label("Открываем земли семи знамён…", 18, Color("#f4e5cb"))
	footer.add_child(status)
	progress = ProgressBar.new()
	progress.show_percentage = false
	progress.custom_minimum_size.y = 4
	var track := StyleBoxFlat.new()
	track.bg_color = Color("#ffffff45")
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color("#f2ce87")
	progress.add_theme_stylebox_override("background", track)
	progress.add_theme_stylebox_override("fill", fill)
	progress.value = 12
	progress.mouse_filter = Control.MOUSE_FILTER_IGNORE
	footer.add_child(progress)

func centered_label(value: String, pixels: int, color: Color, serif := false) -> Label:
	var label := Label.new()
	label.text = value
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", pixels)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", Color("#081115"))
	label.add_theme_constant_override("shadow_offset_y", 2)
	label.add_theme_constant_override("shadow_outline_size", 7)
	if serif:
		label.add_theme_font_override("font", TITLE_FONT)
	return label

func show_step(value: String, amount: int) -> void:
	status.text = value
	progress.value = amount

func finish() -> void:
	show_step("Поселение готово", 100)
	if DisplayServer.get_name() == "headless":
		queue_free()
		return
	var fade := create_tween()
	fade.tween_property(panel, "modulate:a", 0.0, 0.28)
	fade.tween_callback(queue_free)
