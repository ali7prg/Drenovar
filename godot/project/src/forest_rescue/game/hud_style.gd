extends RefCounted
## Framed gradient panels in the style of the art/07 and art/18 references
## (parchment task card, dark leather strip, brass frames, red and gold buttons).

const TITLE_FONT = preload("res://assets/ui/NotoSerif-Regular.ttf")
const IVORY := Color("#f6ead0")
const PARCHMENT_INK := Color("#3a2716")
const MUTED := Color("#d5c7a8")
const BRASS := Color("#b48a4e")
static var cache: Dictionary = {}
static var italic_font: FontVariation

## Faux-italic NotoSerif (only the Regular face ships with the game); used where art/18 is italic.
static func italic() -> Font:
	if italic_font == null:
		italic_font = FontVariation.new()
		italic_font.base_font = TITLE_FONT
		italic_font.variation_transform = Transform2D(Vector2(1, 0), Vector2(0.22, 1), Vector2.ZERO)
	return italic_font

## Vertical gradient fill, outer border, optional inner highlight line, rounded corners.
static func frame(top: Color, bottom: Color, border: Color, radius := 9, border_width := 2,
		padding := Vector4(12, 8, 12, 8), inner := Color.TRANSPARENT) -> StyleBoxTexture:
	var key := "%s|%s|%s|%d|%d|%s|%s" % [top.to_html(), bottom.to_html(), border.to_html(), radius, border_width, str(padding), inner.to_html()]
	if cache.has(key):
		return cache[key]
	var size := maxi(48, radius * 2 + 16)
	var image := Image.create_empty(size, size, false, Image.FORMAT_RGBA8)
	var r := float(radius)
	for y in size:
		var shade := top.lerp(bottom, float(y) / float(size - 1))
		for x in size:
			var dx := maxf(r - minf(x + 0.5, size - x - 0.5), 0.0)
			var dy := maxf(r - minf(y + 0.5, size - y - 0.5), 0.0)
			var distance := Vector2(dx, dy).length()
			var edge_distance := minf(minf(x + 0.5, size - x - 0.5), minf(y + 0.5, size - y - 0.5))
			if dx > 0.0 and dy > 0.0:
				edge_distance = r - distance
			if edge_distance < 0.0:
				continue
			var color := shade
			if edge_distance < border_width:
				color = border
			elif inner.a > 0.0 and edge_distance < border_width + 1.5 and edge_distance >= border_width + 0.5:
				color = inner
			var alpha := clampf(edge_distance + 0.5, 0.0, 1.0)
			image.set_pixel(x, y, Color(color, color.a * alpha))
	var style := StyleBoxTexture.new()
	style.texture = ImageTexture.create_from_image(image)
	for side in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
		style.set_texture_margin(side, radius + border_width + 2)
	style.content_margin_left = padding.x
	style.content_margin_top = padding.y
	style.content_margin_right = padding.z
	style.content_margin_bottom = padding.w
	cache[key] = style
	return style

static func parchment() -> StyleBoxTexture:
	return frame(Color("#f4e7c6"), Color("#dcc596"), Color("#7b5a32"), 8, 3, Vector4(10, 6, 14, 6), Color("#c9a86c"))

static func leather_strip() -> StyleBoxTexture:
	return frame(Color("#2f241a"), Color("#1a140e"), Color("#9c7a48"), 9, 2, Vector4(10, 4, 12, 4), Color("#4d3b28"))

static func leather_button(pressed := false) -> StyleBoxTexture:
	if pressed:
		return frame(Color("#5d4128"), Color("#7a5634"), Color("#e2bf84"), 11, 2, Vector4(6, 4, 6, 4), Color("#3c2a19"))
	return frame(Color("#7f5a37"), Color("#553923"), Color("#cfa769"), 11, 2, Vector4(6, 4, 6, 4), Color("#a07a4b"))

static func gold_button(pressed := false) -> StyleBoxTexture:
	if pressed:
		return frame(Color("#c26b1f"), Color("#e59a3c"), Color("#ffe1a0"), 11, 2, Vector4(6, 4, 6, 4), Color("#9a4f12"))
	return frame(Color("#f0ad48"), Color("#bf6a1e"), Color("#ffd98d"), 11, 2, Vector4(6, 4, 6, 4), Color("#ffe8b5"))

static func red_button(pressed := false) -> StyleBoxTexture:
	if pressed:
		return frame(Color("#6c1b13"), Color("#8f2a1d"), Color("#e2b979"), 7, 2, Vector4(18, 8, 18, 8), Color("#4a120c"))
	return frame(Color("#a43a29"), Color("#6f1d14"), Color("#e7c27f"), 7, 2, Vector4(18, 8, 18, 8), Color("#c76b4f"))

static func slate_card() -> StyleBoxTexture:
	return frame(Color("#383b3e"), Color("#1f2124"), Color("#b38f55"), 10, 3, Vector4(26, 14, 26, 18), Color("#5b4a30"))

static func green_banner() -> StyleBoxTexture:
	return frame(Color("#47663f"), Color("#24391f"), Color("#d4b06b"), 8, 3, Vector4(34, 10, 34, 10), Color("#7a6a3b"))

static func dark_panel() -> StyleBoxTexture:
	return frame(Color("#2b2a26e8"), Color("#191815ee"), Color("#a4814d"), 9, 2, Vector4(14, 10, 14, 10), Color("#4a3c27"))

static func hint_pill() -> StyleBoxTexture:
	return frame(Color("#1f1a14d8"), Color("#14110dd8"), Color("#8f7346"), 14, 1, Vector4(14, 5, 14, 5))

static func apply_button(button: Button, kind := "leather") -> void:
	var normal: StyleBox
	var pressed: StyleBox
	match kind:
		"gold":
			normal = gold_button()
			pressed = gold_button(true)
		"red":
			normal = red_button()
			pressed = red_button(true)
		_:
			normal = leather_button()
			pressed = leather_button(true)
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", normal)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	var disabled := (normal as StyleBoxTexture).duplicate() as StyleBoxTexture
	disabled.modulate_color = Color(0.62, 0.62, 0.62, 0.85)
	button.add_theme_stylebox_override("disabled", disabled)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		button.add_theme_color_override(state, IVORY)
	button.add_theme_color_override("font_disabled_color", Color("#cbbfa8"))

static func label(text: String, font_size := 18, color := IVORY, serif := false, outline := 0) -> Label:
	var value := Label.new()
	value.text = text
	value.add_theme_font_size_override("font_size", font_size)
	value.add_theme_color_override("font_color", color)
	if serif:
		value.add_theme_font_override("font", TITLE_FONT)
	if outline > 0:
		value.add_theme_color_override("font_outline_color", Color("#120d08"))
		value.add_theme_constant_override("outline_size", outline)
	value.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return value
