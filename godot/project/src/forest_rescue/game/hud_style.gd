extends RefCounted
## Surfaces of «Лес потерянных» on the premium kit (src/ui_kit.gd, ui_premium/STAGE4B.md):
## a linen task card, carved oak strips and plates with gold lozenge ends, the kit's gilded and
## linen buttons, dark oak cards inside the bronze corner frame, forest-enamel banners. The
## function names are those of the art/07 and art/18 pass, so every forest widget keeps its
## structure and behaviour; only the look changed. frame() still paints a gradient plate for
## the few small drawn things (name plates over the forest map).

const UiKit = preload("res://src/ui_kit.gd")
## Labels and captions (Philosopher Bold, like every kit button and caption).
const TITLE_FONT = UiKit.LABEL_FONT
## Window-sized titles (the display face of the window headers).
const DISPLAY_FONT = UiKit.TITLE_FONT
const BODY_FONT = UiKit.BODY_FONT
const IVORY := Color("#fbf1dc")
const PARCHMENT_INK := Color("#2b2016")
const MUTED := Color("#d5c7a8")
const BRASS := Color("#b48a4e")
const GOLD := Color("#f3d28a")
## Forest button kinds on the kit: leather → linen plate, gold and red (calls to action) →
## gilded bronze, the one primary look of the game.
const KINDS := {"leather": "tertiary", "gold": "primary", "red": "primary"}
static var cache: Dictionary = {}
static var italic_font: FontVariation

## Faux-italic NotoSerif (only the Regular face ships with the game); used where art/18 is italic.
static func italic() -> Font:
	if italic_font == null:
		italic_font = FontVariation.new()
		italic_font.base_font = BODY_FONT
		italic_font.variation_transform = Transform2D(Vector2(1, 0), Vector2(0.22, 1), Vector2.ZERO)
	return italic_font

## Several style boxes drawn over one another (a tiled oak body under the bronze rim), so a
## PanelContainer keeps one "panel" style.
class Layered extends StyleBox:
	@export var layers: Array[StyleBox] = []

	func _draw(to_canvas_item: RID, rect: Rect2) -> void:
		for layer in layers:
			layer.draw(to_canvas_item, rect)

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

## Linen plate with a bronze rim (the kit's list row): the task card, the clue.
static func parchment() -> StyleBox:
	return UiKit.nine("kit_row", Vector4(14, 14, 14, 14), Vector4(10, 6, 14, 6))

## Carved oak plate with gold lozenge ends: the reward strip, the battle header.
static func leather_strip(padding := Vector4(18, 4, 18, 4)) -> StyleBox:
	return UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), padding)

static func leather_button(pressed := false) -> StyleBox:
	return UiKit.button_styles("tertiary")["pressed" if pressed else "normal"]

static func gold_button(pressed := false) -> StyleBox:
	return UiKit.button_styles("primary")["pressed" if pressed else "normal"]

static func red_button(pressed := false) -> StyleBox:
	return gold_button(pressed)

## Dark oak card in the bronze corner frame (the windows' rim): the locked card, the intro
## card, the mechanism panel.
static func dark_card(padding: Vector4) -> StyleBox:
	var key := "dark|%s" % padding
	if cache.has(key):
		return cache[key]
	var box := Layered.new()
	box.layers = [UiKit.nine("kit_body_dark", Vector4.ZERO, Vector4.ZERO, true), UiKit.frame_style()]
	box.content_margin_left = padding.x
	box.content_margin_top = padding.y
	box.content_margin_right = padding.z
	box.content_margin_bottom = padding.w
	cache[key] = box
	return box

static func slate_card() -> StyleBox:
	return dark_card(Vector4(30, 18, 30, 22))

## Forest enamel with a bronze rim (the kit's green button face, larger): the banner.
static func green_banner() -> StyleBox:
	return UiKit.nine("kit_btn_green", Vector4(20, 16, 20, 16), Vector4(40, 10, 40, 13))

static func dark_panel() -> StyleBox:
	return dark_card(Vector4(20, 16, 20, 16))

## Dark oak pill with a bronze rim (the HUD chips and the city's notices): the hint.
static func hint_pill() -> StyleBox:
	return UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4(20, 7, 20, 8))

## Carved oak toast plate; room at the left for the tone medallion (UiKit.draw_tone).
static func toast_plate() -> StyleBox:
	return UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(50, 9, 30, 11))

static func apply_button(button: Button, kind := "leather") -> void:
	var kit: String = KINDS.get(kind, "tertiary")
	var boxes := UiKit.button_styles(kit)
	var colours: Array = UiKit.BUTTON_TEXT[kit]
	button.begin_bulk_theme_override()
	for state: String in boxes:
		button.add_theme_stylebox_override(state, boxes[state])
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		button.add_theme_color_override(state, colours[0])
	button.add_theme_color_override("font_disabled_color", Color("#efe9dc"))
	button.add_theme_color_override("font_outline_color", colours[1])
	button.add_theme_constant_override("outline_size", colours[2])
	if not button.has_theme_font_override("font"):
		button.add_theme_font_override("font", TITLE_FONT)
	button.end_bulk_theme_override()

## The kit's round bronze close button; the "×" stays the button's text (transparent).
static func close_style(button: Button) -> void:
	var normal := UiKit.nine("kit_close", Vector4.ZERO, Vector4.ZERO)
	var pressed := UiKit.nine("kit_close_pressed", Vector4.ZERO, Vector4.ZERO)
	button.flat = false
	for state in ["normal", "hover", "focus"]:
		button.add_theme_stylebox_override(state, normal)
	for state in ["pressed", "hover_pressed", "disabled"]:
		button.add_theme_stylebox_override(state, pressed)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_disabled_color", "font_hover_pressed_color"]:
		button.add_theme_color_override(state, Color.TRANSPARENT)

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

## A card or banner title: the display face in gold on a dark outline.
static func title(text: String, font_size := 28) -> Label:
	var value := label(text, font_size, GOLD, false, 6)
	value.add_theme_font_override("font", DISPLAY_FONT)
	value.add_theme_color_override("font_outline_color", Color("#140c06"))
	return value
