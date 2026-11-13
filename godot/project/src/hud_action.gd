extends Button

var caption := ""
var symbol := "menu"
var glyph: Texture2D

func _ready() -> void:
	# Act when the finger lifts (the pressed look shows at once on touch-down), so
	# the window that opens is never under a finger that is still on the glass.
	action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
	custom_minimum_size = Vector2(84, 88)
	size_flags_horizontal = Control.SIZE_SHRINK_END
	size_flags_vertical = Control.SIZE_SHRINK_CENTER
	for state in ["normal", "hover", "pressed", "focus", "disabled"]:
		add_theme_stylebox_override(state, StyleBoxEmpty.new())
	glyph = load("res://assets/ui/actions/" + symbol + ".svg")
	mouse_entered.connect(queue_redraw)
	mouse_exited.connect(queue_redraw)
	button_down.connect(queue_redraw)
	button_up.connect(queue_redraw)
	focus_entered.connect(queue_redraw)
	focus_exited.connect(queue_redraw)

func _draw() -> void:
	var center := Vector2(size.x * 0.5, 33)
	var pressed_now := is_pressed()
	var highlighted := is_hovered() or has_focus()
	var half := 32.0
	if pressed_now:
		# Immediate touch-down acknowledgement, independent of what the action does next.
		center.y += 2
		half = 29.0
		draw_circle(center, 31, Color("#0b0f12a8"), true, -1.0, true)
	if glyph != null:
		draw_texture_rect(glyph, Rect2(center - Vector2(half, half), Vector2(half, half) * 2.0), false)
	if highlighted:
		draw_arc(center, 29, 0, TAU, 64, Color("#ffe2a0"), 1.8, true)
	var font := get_theme_default_font()
	var baseline := Vector2((size.x-font.get_string_size(caption,HORIZONTAL_ALIGNMENT_LEFT,-1,15).x)*0.5,80)
	draw_string_outline(font,baseline,caption,HORIZONTAL_ALIGNMENT_LEFT,-1,15,5,Color("#111821"))
	draw_string(font,baseline,caption,HORIZONTAL_ALIGNMENT_LEFT,-1,15,Color("#fff1d2"))
