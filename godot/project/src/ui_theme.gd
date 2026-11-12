extends RefCounted

const GOLD := Color("#e7c17d")
const INK := Color("#111916")
const TEXT := Color("#f6f0e4")
const MUTED := Color("#b9c5b7")
const STROKE := Color("#65573e")
const RESOURCES := {
	"food":Color("#e5c56e"), "wood":Color("#dc9a61"), "stone":Color("#c2ced3"),
	"iron":Color("#8fb4d2"), "coins":Color("#efbd5f")
}

static func style(fill: Color, stroke: Color, radius: int, horizontal: float, vertical: float) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.border_color = stroke
	box.set_border_width_all(1)
	box.set_corner_radius_all(radius)
	box.content_margin_left = horizontal
	box.content_margin_right = horizontal
	box.content_margin_top = vertical
	box.content_margin_bottom = vertical
	return box

static func panel_style(inset := 14, dialog := false) -> StyleBoxFlat:
	var box := style(Color("#19232fef") if dialog else Color("#151b22cf"), STROKE, 3, inset, inset)
	box.border_width_top = 2
	box.shadow_color = Color("#080c0ba6")
	box.shadow_size = 10 if dialog else 5
	box.shadow_offset = Vector2(0, 4)
	return box

static func button_styles(accent: Color = GOLD, filled := false) -> Dictionary:
	var base := Color("#273749").lerp(accent, 0.13 if filled else 0.035)
	var border := accent.darkened(0.43) if filled else Color("#7a8791")
	var focus := style(Color.TRANSPARENT, accent, 2, 0, 0)
	focus.draw_center = false
	focus.set_border_width_all(2)
	return {
		"normal":style(base, border, 2, 12, 6),
		"hover":style(base.lerp(accent, 0.23), accent.darkened(0.25), 2, 12, 6),
		"pressed":style(base.lerp(accent, 0.32), accent, 2, 12, 6),
		"disabled":style(Color("#242a30"), Color("#444e56"), 2, 12, 6),
		"focus":focus
	}

static func accent_button(control: Button, accent: Color = GOLD) -> void:
	var styles := button_styles(accent, true)
	for state in styles:
		control.add_theme_stylebox_override(state, styles[state])

static func hud_button(control: Button, framed := false) -> void:
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var fill := Color("#201c16b8") if framed else Color.TRANSPARENT
		if state == "hover":
			fill = Color("#d8b77322")
		elif state == "pressed":
			fill = Color("#d8b77344")
		var stroke := Color("#a68d5c99") if framed or state == "focus" else Color.TRANSPARENT
		var box := style(fill, stroke, 2, 10, 0)
		control.add_theme_stylebox_override(state, box)

static func make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = 18
	theme.set_color("font_color", "Label", TEXT)
	for type in ["Button", "LineEdit", "CheckButton"]:
		theme.set_color("font_color", type, TEXT)
		theme.set_color("font_hover_color", type, Color.WHITE)
		theme.set_color("font_pressed_color", type, Color.WHITE)
		theme.set_color("font_focus_color", type, TEXT)
		theme.set_color("font_disabled_color", type, Color("#819086"))
	for type in ["Button", "OptionButton"]:
		var styles := button_styles()
		for state in styles:
			theme.set_stylebox(state, type, styles[state])
	theme.set_stylebox("normal", "LineEdit", style(Color("#0e1915"), Color("#607264"), 8, 10, 6))
	theme.set_stylebox("focus", "LineEdit", style(Color("#17251e"), GOLD, 8, 10, 6))
	theme.set_stylebox("panel", "PopupMenu", panel_style(10))
	theme.set_stylebox("hover", "PopupMenu", style(Color("#405447"), STROKE, 6, 8, 6))
	theme.set_stylebox("scroll", "VScrollBar", style(Color("#1a2821"), Color.TRANSPARENT, 4, 2, 2))
	for state in ["grabber", "grabber_highlight", "grabber_pressed"]:
		theme.set_stylebox(state, "VScrollBar", style(Color("#778675"), Color.TRANSPARENT, 4, 3, 3))
	return theme
