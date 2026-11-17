extends RefCounted

const Palette = preload("res://src/ui_theme.gd")
const BRASS := Color("#a4814d")
const IVORY := Color("#f2e7d0")
const GOLD := Color("#ebcc89")
static var gradients := {}

static func gradient_style(top: Color, bottom: Color, edge: Color, padding: int, radius := 7) -> StyleBoxTexture:
	var key := "%s:%s:%s:%d:%d" % [top.to_html(), bottom.to_html(), edge.to_html(), padding, radius]
	if gradients.has(key):
		return gradients[key]
	var size := maxi(32, radius * 2 + 4)
	var image := Image.create_empty(size, size, false, Image.FORMAT_RGBA8)
	for y in size:
		var shade := top.lerp(bottom, float(y) / (size - 1))
		for x in size:
			var corner := Vector2(maxi(radius - mini(x, size - 1 - x), 0), maxi(radius - mini(y, size - 1 - y), 0))
			var distance := corner.length()
			if distance > radius:
				continue
			var border := distance > radius - 1.0
			image.set_pixel(x, y, edge if border else shade)
	var style := StyleBoxTexture.new()
	style.texture = ImageTexture.create_from_image(image)
	for side in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
		style.set_texture_margin(side, radius + 1)
		style.set_content_margin(side, padding)
	gradients[key] = style
	return style

static func make_theme(base: Theme) -> Theme:
	var theme := base.duplicate() as Theme
	theme.default_font_size = 19
	theme.set_color("font_color", "Label", IVORY)
	var normal := Palette.style(Color("#272c31"), BRASS, 7, 12, 6)
	var hover := Palette.style(Color("#353d44"), GOLD, 7, 12, 6)
	var pressed := Palette.style(Color("#191d21"), BRASS, 7, 12, 6)
	var disabled := Palette.style(Color("#3b3e3c"), Color("#81715d"), 7, 12, 6)
	var focus := Palette.style(Color.TRANSPARENT, GOLD, 7, 0, 0)
	focus.draw_center = false
	focus.set_border_width_all(2)
	for type in ["Button", "OptionButton"]:
		theme.set_stylebox("normal", type, normal)
		theme.set_stylebox("hover", type, hover)
		theme.set_stylebox("pressed", type, pressed)
		theme.set_stylebox("disabled", type, disabled)
		theme.set_stylebox("focus", type, focus)
		theme.set_color("font_color", type, IVORY)
		theme.set_color("font_disabled_color", type, Color("#c2b7a3"))
	theme.set_stylebox("normal", "LineEdit", Palette.style(Color("#20252a"), BRASS, 5, 8, 4))
	theme.set_stylebox("scroll", "VScrollBar", Palette.style(Color("#272c31"), Color.TRANSPARENT, 3, 3, 2))
	for state in ["grabber", "grabber_highlight", "grabber_pressed"]:
		theme.set_stylebox(state, "VScrollBar", Palette.style(BRASS, Color.TRANSPARENT, 3, 3, 3))
	# Quantity sliders: dark recessed track, gold fill.
	var track := Palette.style(Color("#15181b"), Color("#5d4d36"), 5, 0, 0)
	track.content_margin_top = 5
	track.content_margin_bottom = 5
	theme.set_stylebox("slider", "HSlider", track)
	var fill := gradient_style(Color("#f3d48e"), Color("#a97a35"), Color("#f6dc9c"), 0, 5)
	theme.set_stylebox("grabber_area", "HSlider", fill)
	theme.set_stylebox("grabber_area_highlight", "HSlider", fill)
	return theme

static func primary(control: Button, danger := false) -> void:
	var top := Color("#894d49") if danger else Color("#f1d497")
	var bottom := Color("#773c39") if danger else Color("#b98b4c")
	var edge := Color("#d59978") if danger else Color("#efce87")
	var text := Color("#fff0d9") if danger else Color("#221b13")
	control.add_theme_stylebox_override("normal", gradient_style(top, bottom, edge, 8))
	control.add_theme_stylebox_override("hover", gradient_style(top.lightened(0.1), bottom.lightened(0.1), edge, 8))
	control.add_theme_stylebox_override("pressed", gradient_style(top.darkened(0.12), bottom.darkened(0.12), edge, 8))
	for state in ["font_color", "font_hover_color", "font_focus_color", "font_pressed_color"]:
		control.add_theme_color_override(state, text)
