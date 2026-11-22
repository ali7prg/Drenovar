extends Button
## A round HUD action over the city and the map (premium UI stage 4a, ui_premium/STAGE4A.md):
## a bronze medallion with a forged emblem and a caption, an enamel badge with a count
## (unread reports, free builders). The profile medallion is larger and gold, with the
## settlement's name and its hall level beside it. One drawn node; it redraws only when
## its state changes, so the HUD costs nothing per frame.

const UiKit = preload("res://src/ui_kit.gd")
## Forged emblem of each action (src/ui_kit.gd textures); others draw their SVG glyph.
const EMBLEMS := {"city": "kit_emb_town", "world": "kit_emb_map", "build": "kit_emb_craft", "army": "kit_emb_sword",
	"reports": "kit_emb_scroll", "menu": "kit_emb_menu", "profile": "kit_emb_helm"}

var caption := ""
var symbol := "menu"
var glyph: Texture2D
var emblem: Texture2D
## Count on the enamel badge ("" hides it); green for something ready (free builders).
var badge := ""
var badge_good := false
## Profile medallion: the name and the line under it.
var title := ""
var subtitle := ""

func _ready() -> void:
	# Act when the finger lifts (the pressed look shows at once on touch-down), so
	# the window that opens is never under a finger that is still on the glass.
	action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
	custom_minimum_size = Vector2(310, 88) if symbol == "profile" else Vector2(84, 88)
	size_flags_horizontal = Control.SIZE_SHRINK_BEGIN if symbol == "profile" else Control.SIZE_SHRINK_END
	size_flags_vertical = Control.SIZE_SHRINK_CENTER
	for state in ["normal", "hover", "pressed", "focus", "disabled"]:
		add_theme_stylebox_override(state, StyleBoxEmpty.new())
	if EMBLEMS.has(symbol):
		emblem = UiKit.tex(EMBLEMS[symbol])
	if emblem == null:
		glyph = load("res://assets/ui/actions/" + symbol + ".svg")
	mouse_entered.connect(queue_redraw)
	mouse_exited.connect(queue_redraw)
	button_down.connect(queue_redraw)
	button_up.connect(queue_redraw)
	focus_entered.connect(queue_redraw)
	focus_exited.connect(queue_redraw)

func set_badge(text: String, good := false) -> void:
	if text == badge and good == badge_good:
		return
	badge = text
	badge_good = good
	queue_redraw()

func set_profile(name_text: String, line: String) -> void:
	if name_text == title and line == subtitle:
		return
	title = name_text
	subtitle = line
	queue_redraw()

func _draw() -> void:
	var profile := symbol == "profile"
	var pressed_now := is_pressed()
	var highlighted := is_hovered() or has_focus()
	var d := 74.0 if profile else 62.0
	var center := Vector2(d * 0.5 + 4.0 if profile else size.x * 0.5, 36.0 if profile else 33.0)
	if pressed_now:
		# Immediate touch-down acknowledgement, independent of what the action does next.
		center.y += 2.0
		d -= 4.0
	# A soft dark halo under the disc keeps it legible over bright grass and snow.
	draw_circle(center + Vector2(0, 2), d * 0.5 + 3.0, Color(0, 0, 0, 0.32), true, -1.0, true)
	draw_texture_rect(UiKit.tex("kit_rail_on" if profile else "kit_rail"), Rect2(center - Vector2(d, d) * 0.5, Vector2(d, d)), false,
		Color(0.8, 0.76, 0.72) if pressed_now else Color.WHITE)
	if emblem != null:
		var side := d * (0.6 if profile else 0.62)
		draw_texture_rect(emblem, Rect2(center - Vector2(side, side) * 0.5, Vector2(side, side)), false,
			Color(0.85, 0.82, 0.78) if pressed_now else Color.WHITE)
	elif glyph != null:
		var half := d * 0.42
		draw_texture_rect(glyph, Rect2(center - Vector2(half, half), Vector2(half, half) * 2.0), false)
	if highlighted and not pressed_now:
		draw_arc(center, d * 0.5 - 1.0, 0, TAU, 64, Color("#ffe2a0"), 1.8, true)
	if profile:
		draw_profile_text(center, d)
	else:
		var line := UiKit.KitText.line(caption, UiKit.LABEL_FONT, 15)
		var at := Vector2(roundf((size.x - line.get_size().x) * 0.5), 66.0 + (1.0 if pressed_now else 0.0))
		line.draw_outline(get_canvas_item(), at, 5, Color("#120c07"))
		line.draw(get_canvas_item(), at, Color("#fff1d2"))
	if not badge.is_empty():
		var tag := UiKit.KitText.line(badge, UiKit.LABEL_FONT, 14)
		var radius := maxf(11.0, tag.get_size().x * 0.5 + 6.0)
		var spot := center + Vector2(d * 0.36, -d * 0.36)
		var pill := Rect2(spot - Vector2(radius, 11.0), Vector2(radius * 2.0, 22.0))
		var rim := StyleBoxFlat.new()
		rim.bg_color = Color("#2f7d36") if badge_good else Color("#a8231d")
		rim.border_color = Color("#f2d48b")
		rim.set_border_width_all(2)
		rim.set_corner_radius_all(11)
		rim.anti_aliasing = true
		rim.shadow_color = Color(0, 0, 0, 0.4)
		rim.shadow_size = 3
		draw_style_box(rim, pill)
		tag.draw(get_canvas_item(), Vector2(roundf(spot.x - tag.get_size().x * 0.5), roundf(spot.y - tag.get_size().y * 0.5)), Color.WHITE)

func draw_profile_text(center: Vector2, d: float) -> void:
	var x := center.x + d * 0.5 + 10.0
	var width := maxf(40.0, size.x - x - 4.0)
	var name_line := UiKit.KitText.line(title if not title.is_empty() else caption, UiKit.LABEL_FONT, 19, width)
	var top := center.y - 22.0
	name_line.draw_outline(get_canvas_item(), Vector2(x, top), 5, Color("#120c07"))
	name_line.draw(get_canvas_item(), Vector2(x, top), UiKit.GOLD)
	if subtitle.is_empty():
		return
	# The hall level on a small oak plate under the name.
	var line := UiKit.KitText.line(subtitle, UiKit.LABEL_FONT, 14, width - 16.0)
	var plate := Rect2(x - 4.0, top + name_line.get_size().y + 3.0, line.get_size().x + 22.0, 24.0)
	draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), plate)
	line.draw(get_canvas_item(), Vector2(plate.position.x + 11.0, plate.position.y + roundf((plate.size.y - line.get_size().y) * 0.5)), Color("#f6e7c4"))
