extends RefCounted
## DRENOVAR premium UI kit ("Резной дуб и кованая бронза").
##
## One place for the look of every window: the window frame (carved oak header band with
## a bronze lozenge trim, warm linen body, bronze corner brackets), buttons (gilded bronze
## primary, lapis / forest enamel secondary, cranberry danger, linen tertiary), section
## headers with a cross-stitch rushnyk band, cost strips, timer pills, progress bars,
## quantity slider + field, tier cards, list rows, info chips, rail buttons and toasts.
## See ui_premium/ART_DIRECTION.md.
##
## Textures: res://assets/ui/premium/*.res (painted by godot/art/ui/premium/paint_kit.py at
## 2 texels per canvas unit, baked by tools/bake_ui_kit.gd with size_override), so every
## margin below is in canvas units and the pixels stay crisp on the phone.
## preload_async() starts decoding them on worker threads at launch; the first window
## that needs one only waits if the worker has not finished.

const DIR := "res://assets/ui/premium/"
const TITLE_FONT := preload("res://assets/ui/fonts/RuslanDisplay-Regular.ttf")
const LABEL_FONT := preload("res://assets/ui/fonts/Philosopher-Bold.ttf")
const BODY_FONT := preload("res://assets/ui/NotoSerif-Regular.ttf")

# Text on the linen body.
const INK := Color("#2b2016")
const INK_MUTED := Color("#6a5843")
const BRONZE := Color("#8d5f22")
const GOOD := Color("#2e7a32")
const BAD := Color("#b02a25")
const WARN := Color("#9c4f10")
# Text on oak, enamel and dark plates.
const IVORY := Color("#fbf1dc")
const GOLD := Color("#f3d28a")
const GOLD_DIM := Color("#cfae6c")
const SHADE := Color("#140c06")
const PRIMARY_INK := Color("#3a2208")
# Tier colours I–V: grey iron, forest green, lapis, purple, amber gold.
const TIERS := [Color("#7d8288"), Color("#3f8a4b"), Color("#2f6aa8"), Color("#7b45a8"), Color("#d39a2c")]

const TEXTURES := ["kit_body", "kit_body_dark", "kit_hourglass", "kit_header", "kit_frame", "kit_close", "kit_close_pressed",
	"kit_btn_primary", "kit_btn_primary_pressed", "kit_btn_secondary", "kit_btn_secondary_pressed",
	"kit_btn_green", "kit_btn_green_pressed", "kit_btn_danger", "kit_btn_danger_pressed",
	"kit_btn_tertiary", "kit_btn_tertiary_pressed", "kit_btn_disabled", "kit_rail", "kit_rail_on",
	"kit_card_fill", "kit_card_frame", "kit_badge", "kit_strip", "kit_pill", "kit_row", "kit_tile",
	"kit_field", "kit_track", "kit_fill", "kit_fill_green", "kit_knob", "kit_stitch", "kit_rosette",
	"kit_flourish", "kit_splash"]

static var textures := {}
static var requested := {}
static var styles := {}
static var themes := {}

# ------------------------------------------------------------------ textures

## Starts decoding every kit texture on worker threads (non-blocking).
static func preload_async() -> void:
	for name: String in TEXTURES:
		var path: String = DIR + name + ".res"
		if not textures.has(name) and not requested.has(name) and ResourceLoader.exists(path):
			if ResourceLoader.load_threaded_request(path, "Texture2D") == OK:
				requested[name] = path

static func tex(name: String) -> Texture2D:
	if textures.has(name):
		return textures[name]
	var path: String = DIR + name + ".res"
	var texture: Texture2D
	if requested.has(name):
		texture = ResourceLoader.load_threaded_get(path) as Texture2D
		requested.erase(name)
	if texture == null:
		texture = load(path) as Texture2D
	textures[name] = texture
	return texture

static func nine(name: String, margin: Vector4, content: Vector4, tile := false, draw_center := true) -> StyleBoxTexture:
	var key := "%s|%s|%s|%s|%s" % [name, margin, content, tile, draw_center]
	if styles.has(key):
		return styles[key]
	var box := StyleBoxTexture.new()
	box.texture = tex(name)
	box.texture_margin_left = margin.x
	box.texture_margin_top = margin.y
	box.texture_margin_right = margin.z
	box.texture_margin_bottom = margin.w
	box.content_margin_left = content.x
	box.content_margin_top = content.y
	box.content_margin_right = content.z
	box.content_margin_bottom = content.w
	box.draw_center = draw_center
	if tile:
		box.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE
		box.axis_stretch_vertical = StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	styles[key] = box
	return box

static func flat(fill: Color, border := Color.TRANSPARENT, radius := 6, pad := Vector2(10, 6), width := 1) -> StyleBoxFlat:
	var key := "flat|%s|%s|%d|%s|%d" % [fill.to_html(), border.to_html(), radius, pad, width]
	if styles.has(key):
		return styles[key]
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.border_color = border
	box.set_border_width_all(width if border.a > 0.0 else 0)
	box.set_corner_radius_all(radius)
	box.corner_detail = 6
	box.anti_aliasing = true
	box.content_margin_left = pad.x
	box.content_margin_right = pad.x
	box.content_margin_top = pad.y
	box.content_margin_bottom = pad.y
	styles[key] = box
	return box

# ------------------------------------------------------------------ window surfaces

static func body_style() -> StyleBoxTexture:
	return nine("kit_body", Vector4.ZERO, Vector4.ZERO, true)

## Carved oak header band: 56 units of plank, an 8-unit bronze trim, 4 units of shadow.
static func header_style() -> StyleBoxTexture:
	var box := nine("kit_header", Vector4(0, 10, 0, 16), Vector4(14, 4, 10, 15))
	box.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	return box

## Bronze rim with corner brackets, drawn over docked and centred windows.
static func frame_style() -> StyleBoxTexture:
	return nine("kit_frame", Vector4(30, 30, 30, 30), Vector4.ZERO, false, false)

static func vignette_texture() -> GradientTexture2D:
	if styles.has("vignette"):
		return styles.vignette
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.62, 1.0])
	gradient.colors = PackedColorArray([Color(0.36, 0.25, 0.12, 0.0), Color(0.36, 0.25, 0.12, 0.06), Color(0.30, 0.19, 0.08, 0.30)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.42)
	texture.fill_to = Vector2(1.05, 0.42)
	texture.width = 128
	texture.height = 64
	styles.vignette = texture
	return texture

static func make_vignette() -> TextureRect:
	var vignette := TextureRect.new()
	vignette.name = "KitVignette"
	vignette.texture = vignette_texture()
	vignette.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	vignette.stretch_mode = TextureRect.STRETCH_SCALE
	vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return vignette

static func make_frame() -> Panel:
	var rim := Panel.new()
	rim.name = "KitFrame"
	rim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rim.add_theme_stylebox_override("panel", frame_style())
	return rim

## Window title: display font, warm gold on oak, dark outline.
static func title_label(size := 30) -> Label:
	var label := Label.new()
	label.add_theme_font_override("font", TITLE_FONT)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", Color("#f7e2ad"))
	label.add_theme_color_override("font_outline_color", Color("#1a0f07"))
	label.add_theme_constant_override("outline_size", 6)
	label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.55))
	label.add_theme_constant_override("shadow_offset_y", 2)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return label

static func eyebrow_label() -> Label:
	var label := Label.new()
	label.add_theme_font_override("font", LABEL_FONT)
	label.add_theme_font_size_override("font_size", 13)
	label.add_theme_color_override("font_color", GOLD_DIM)
	label.add_theme_constant_override("outline_size", 3)
	label.add_theme_color_override("font_outline_color", Color("#1a0f07"))
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return label

static func flourish(mirrored: bool) -> TextureRect:
	var art := TextureRect.new()
	art.texture = tex("kit_flourish")
	art.flip_h = mirrored
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.custom_minimum_size = Vector2(96, 24)
	art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return art

## Round bronze medallion with a forged X. The "×" text stays for code that finds the
## button by its caption; it is drawn transparent because the X is in the medal.
static func close_button(action: Callable) -> Button:
	var control := Button.new()
	control.text = "×"
	control.tooltip_text = "Закрыть"
	control.accessibility_name = "Закрыть"
	control.custom_minimum_size = Vector2(56, 56)
	control.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var normal := nine("kit_close", Vector4.ZERO, Vector4.ZERO)
	var pressed := nine("kit_close_pressed", Vector4.ZERO, Vector4.ZERO)
	for state in ["normal", "hover", "focus"]:
		control.add_theme_stylebox_override(state, normal)
	control.add_theme_stylebox_override("pressed", pressed)
	control.add_theme_stylebox_override("disabled", pressed)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_disabled_color", "font_hover_pressed_color"]:
		control.add_theme_color_override(state, Color.TRANSPARENT)
	if action.is_valid():
		control.pressed.connect(action)
	return control

# ------------------------------------------------------------------ buttons

const BUTTON_TEXT := {
	"primary": [PRIMARY_INK, Color("#fff2c8"), 0],
	"secondary": [IVORY, Color("#0c1a2a"), 5],
	"green": [IVORY, Color("#0c2412"), 5],
	"danger": [IVORY, Color("#2a0808"), 5],
	"tertiary": [INK, Color("#fff8ea"), 0],
}

static func button_styles(kind: String) -> Dictionary:
	var key := "buttons|" + kind
	if styles.has(key):
		return styles[key]
	var margin := Vector4(20, 16, 20, 16)
	var normal := nine("kit_btn_" + kind, margin, Vector4(22, 7, 22, 9))
	var hover := normal.duplicate() as StyleBoxTexture
	hover.modulate_color = Color(1.08, 1.06, 1.02)
	var pressed := nine("kit_btn_%s_pressed" % kind, margin, Vector4(22, 9, 22, 7))
	var disabled := nine("kit_btn_disabled", margin, Vector4(22, 7, 22, 9))
	var focus := StyleBoxEmpty.new()
	var result := {"normal": normal, "hover": hover, "pressed": pressed, "hover_pressed": pressed, "disabled": disabled, "focus": focus}
	styles[key] = result
	return result

## kind: primary (gilded), secondary (lapis), green (forest enamel), danger (cranberry),
## tertiary (linen plate). Sets styles, font and text colours on one button.
static func style_button(control: Button, kind := "tertiary", font_size := 19) -> Button:
	var boxes := button_styles(kind)
	for state: String in boxes:
		control.add_theme_stylebox_override(state, boxes[state])
	var colours: Array = BUTTON_TEXT.get(kind, BUTTON_TEXT.tertiary)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		control.add_theme_color_override(state, colours[0])
	control.add_theme_color_override("font_disabled_color", Color("#efe9dc"))
	control.add_theme_color_override("font_outline_color", colours[1])
	control.add_theme_constant_override("outline_size", colours[2])
	control.add_theme_font_override("font", LABEL_FONT)
	control.add_theme_font_size_override("font_size", font_size)
	if control.custom_minimum_size.y < 46:
		control.custom_minimum_size.y = 46
	return control

## Round rail button (left category rail): enamel disc in a bronze ring, gold glow when selected.
static func rail_button(icon: Texture2D, selected: bool, caption := "") -> Button:
	var control := Button.new()
	control.custom_minimum_size = Vector2(72, 72)
	control.tooltip_text = caption
	control.accessibility_name = caption
	var disc := nine("kit_rail_on" if selected else "kit_rail", Vector4.ZERO, Vector4(14, 14, 14, 14))
	for state in ["normal", "hover", "pressed", "focus", "disabled"]:
		control.add_theme_stylebox_override(state, disc)
	control.icon = icon
	control.expand_icon = true
	control.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	control.add_theme_constant_override("icon_max_width", 40)
	return control

## Small round "i" chip; pressing it shows the text in a toast-like tooltip.
static func info_chip(text: String) -> Button:
	var control := Button.new()
	control.text = "i"
	control.tooltip_text = text
	control.accessibility_name = text
	control.custom_minimum_size = Vector2(30, 30)
	control.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var box := flat(Color("#2b1f16"), Color("#c59a4f"), 15, Vector2(0, 0), 2)
	for state in ["normal", "hover", "pressed", "focus"]:
		control.add_theme_stylebox_override(state, box)
	control.add_theme_font_override("font", LABEL_FONT)
	control.add_theme_font_size_override("font_size", 17)
	control.add_theme_color_override("font_color", GOLD)
	control.add_theme_color_override("font_hover_color", Color.WHITE)
	control.add_theme_color_override("font_pressed_color", Color.WHITE)
	return control

# ------------------------------------------------------------------ text blocks

static func label(parent: Node, text: String, size := 18, colour := INK, font: Font = null, wrap := true) -> Label:
	var item := Label.new()
	item.text = text
	item.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART if wrap else TextServer.AUTOWRAP_OFF
	item.add_theme_font_size_override("font_size", size)
	item.add_theme_color_override("font_color", colour)
	if font != null:
		item.add_theme_font_override("font", font)
	if parent != null:
		parent.add_child(item)
	return item

## Section header: title in bronze small caps between two cross-stitch rushnyk bands.
static func section_header(parent: Node, text: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "KitSection"
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(_stitch_band())
	var title := Label.new()
	title.text = text
	title.add_theme_font_override("font", LABEL_FONT)
	title.add_theme_font_size_override("font_size", 21)
	title.add_theme_color_override("font_color", Color("#5a3510"))
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	title.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	row.add_child(title)
	row.add_child(_stitch_band())
	if parent != null:
		parent.add_child(row)
	return row

static func _stitch_band() -> HBoxContainer:
	var band := HBoxContainer.new()
	band.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	band.add_theme_constant_override("separation", 0)
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var line := TextureRect.new()
	line.texture = tex("kit_stitch")
	line.stretch_mode = TextureRect.STRETCH_TILE
	line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	line.custom_minimum_size = Vector2(24, 12)
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.modulate = Color(1, 1, 1, 0.9)
	band.add_child(line)
	var rose := TextureRect.new()
	rose.texture = tex("kit_rosette")
	rose.custom_minimum_size = Vector2(13, 13)
	rose.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	rose.mouse_filter = Control.MOUSE_FILTER_IGNORE
	band.add_child(rose)
	return band

## Dark oak strip with resource icons and amounts; an amount above the stock turns red.
## icons: resource id -> Texture2D; stock: resource id -> available amount (or empty).
static func cost_strip(parent: Node, cost: Dictionary, icons: Dictionary, stock: Dictionary, names := {}) -> PanelContainer:
	var plate := PanelContainer.new()
	plate.name = "KitCost"
	plate.add_theme_stylebox_override("panel", nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(30, 8, 30, 8)))
	plate.mouse_filter = Control.MOUSE_FILTER_PASS
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 26)
	plate.add_child(row)
	var tips: PackedStringArray = []
	for resource: String in cost:
		var amount := int(cost[resource])
		if amount <= 0:
			continue
		var item := HBoxContainer.new()
		item.add_theme_constant_override("separation", 6)
		item.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(item)
		if icons.has(resource):
			var icon := TextureRect.new()
			icon.texture = icons[resource]
			icon.custom_minimum_size = Vector2(30, 30)
			icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
			item.add_child(icon)
		var short := not stock.is_empty() and amount > int(stock.get(resource, 0))
		var value := Label.new()
		value.text = compact(amount)
		value.add_theme_font_override("font", LABEL_FONT)
		value.add_theme_font_size_override("font_size", 21)
		value.add_theme_color_override("font_color", Color("#ff7a66") if short else IVORY)
		value.add_theme_color_override("font_outline_color", SHADE)
		value.add_theme_constant_override("outline_size", 4)
		value.mouse_filter = Control.MOUSE_FILTER_IGNORE
		item.add_child(value)
		tips.append("%s: %d%s" % [names.get(resource, resource), amount, " — не хватает" if short else ""])
	plate.tooltip_text = "\n".join(tips)
	if parent != null:
		parent.add_child(plate)
	return plate

static func compact(value: int) -> String:
	if value >= 1000000:
		return String.num(value / 1000000.0, 1).trim_suffix(".0") + "M"
	if value >= 10000:
		return String.num(value / 1000.0, 1).trim_suffix(".0") + "K"
	var digits := str(value)
	if digits.length() > 3:
		return digits.left(-3) + " " + digits.right(3)
	return digits

## Hourglass pill: caption on the left, time in gold on the right. Returns the time label
## (callers bind a countdown to it).
static func timer_pill(parent: Node, caption: String, time_text: String) -> Label:
	var plate := PanelContainer.new()
	plate.name = "KitTimer"
	plate.add_theme_stylebox_override("panel", nine("kit_pill", Vector4(18, 12, 18, 12), Vector4(18, 6, 20, 6)))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	plate.add_child(row)
	var glass := Label.new()
	glass.text = "⧗"
	glass.add_theme_font_size_override("font_size", 22)
	glass.add_theme_color_override("font_color", GOLD)
	row.add_child(glass)
	var title := Label.new()
	title.text = caption
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.add_theme_font_size_override("font_size", 17)
	title.add_theme_color_override("font_color", Color("#e9dcc2"))
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(title)
	var clock := Label.new()
	clock.text = time_text
	clock.add_theme_font_override("font", LABEL_FONT)
	clock.add_theme_font_size_override("font_size", 22)
	clock.add_theme_color_override("font_color", GOLD)
	clock.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(clock)
	if parent != null:
		parent.add_child(plate)
	return clock

static func progress_bar(parent: Node, ratio: float, green := false) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.min_value = 0.0
	bar.max_value = 1.0
	bar.step = 0.0
	bar.value = clampf(ratio, 0.0, 1.0)
	bar.custom_minimum_size = Vector2(120, 22)
	bar.add_theme_stylebox_override("background", nine("kit_track", Vector4(11, 10, 11, 10), Vector4.ZERO))
	bar.add_theme_stylebox_override("fill", nine("kit_fill_green" if green else "kit_fill", Vector4(11, 10, 11, 10), Vector4.ZERO))
	if parent != null:
		parent.add_child(bar)
	return bar

## Gold slider with a numeric field; the two stay in sync. Returns [HSlider, SpinBox].
static func quantity(parent: Node, low: int, high: int, value: int) -> Array:
	var row := HBoxContainer.new()
	row.name = "KitQuantity"
	row.add_theme_constant_override("separation", 14)
	var slider := HSlider.new()
	slider.min_value = low
	slider.max_value = high
	slider.step = 1
	slider.value = value
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.custom_minimum_size = Vector2(160, 40)
	slider.add_to_group("panel_slider")
	row.add_child(slider)
	var field := SpinBox.new()
	field.min_value = low
	field.max_value = high
	field.value = value
	field.custom_minimum_size = Vector2(128, 46)
	field.alignment = HORIZONTAL_ALIGNMENT_CENTER
	row.add_child(field)
	slider.value_changed.connect(func(v: float): if not is_equal_approx(field.value, v): field.value = v)
	field.value_changed.connect(func(v: float): if not is_equal_approx(slider.value, v): slider.value = v)
	if parent != null:
		parent.add_child(row)
	return [slider, field]

## Tier card: tier-coloured enamel inside a bronze chamfered frame, a kokoshnik badge with
## the Roman numeral, art, title and a count plate.
static func tier_card(tier: int, title: String, count_text: String, art: Texture2D, selected := false) -> Button:
	tier = clampi(tier, 1, TIERS.size())
	var colour: Color = TIERS[tier - 1]
	var card := Button.new()
	card.name = "KitTier%d" % tier
	card.custom_minimum_size = Vector2(112, 156)
	card.tooltip_text = title
	card.accessibility_name = title
	card.clip_contents = false
	var fill := nine("kit_card_fill", Vector4(14, 14, 14, 14), Vector4(8, 8, 8, 8)).duplicate() as StyleBoxTexture
	fill.modulate_color = colour.lightened(0.12)
	var pressed := fill.duplicate() as StyleBoxTexture
	pressed.modulate_color = colour.darkened(0.15)
	for state in ["normal", "hover", "focus", "disabled"]:
		card.add_theme_stylebox_override(state, fill)
	card.add_theme_stylebox_override("pressed", pressed)
	var glow := TextureRect.new()
	glow.texture = tex("kit_splash")
	glow.modulate = Color(colour.lightened(0.55), 0.55)
	glow.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	glow.offset_left = 4
	glow.offset_right = -4
	glow.offset_top = 10
	glow.offset_bottom = -34
	glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glow.stretch_mode = TextureRect.STRETCH_SCALE
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(glow)
	if art != null:
		var picture := TextureRect.new()
		picture.texture = art
		picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		picture.offset_left = 6
		picture.offset_right = -6
		picture.offset_top = 14
		picture.offset_bottom = -36
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(picture)
	var plate := Panel.new()
	plate.add_theme_stylebox_override("panel", flat(Color("#1e140dcc"), Color.TRANSPARENT, 4, Vector2.ZERO))
	plate.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	plate.offset_left = 5
	plate.offset_right = -5
	plate.offset_top = -32
	plate.offset_bottom = -5
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(plate)
	var count := Label.new()
	count.text = count_text
	count.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	count.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	count.add_theme_font_override("font", LABEL_FONT)
	count.add_theme_font_size_override("font_size", 18)
	count.add_theme_color_override("font_color", IVORY)
	count.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plate.add_child(count)
	var frame := Panel.new()
	frame.add_theme_stylebox_override("panel", nine("kit_card_frame", Vector4(16, 16, 16, 16), Vector4.ZERO, false, false))
	frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if selected:
		frame.modulate = Color(1.25, 1.15, 0.85)
	card.add_child(frame)
	var badge := TextureRect.new()
	badge.texture = tex("kit_badge")
	badge.position = Vector2(4, -6)
	badge.size = Vector2(36, 34)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(badge)
	var numeral := Label.new()
	numeral.text = ["I", "II", "III", "IV", "V"][tier - 1]
	numeral.position = Vector2(0, 8)
	numeral.size = Vector2(36, 24)
	numeral.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	numeral.add_theme_font_override("font", LABEL_FONT)
	numeral.add_theme_font_size_override("font_size", 15)
	numeral.add_theme_color_override("font_color", GOLD)
	badge.add_child(numeral)
	if selected:
		var ring := Panel.new()
		ring.add_theme_stylebox_override("panel", flat(Color.TRANSPARENT, Color("#ffd36b"), 10, Vector2.ZERO, 3))
		ring.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		ring.offset_left = -3
		ring.offset_top = -3
		ring.offset_right = 3
		ring.offset_bottom = 3
		ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(ring)
	return card

## Icon tile (dark enamel square in bronze) holding a texture.
static func icon_tile(icon: Texture2D, size := 64) -> PanelContainer:
	var tile := PanelContainer.new()
	tile.custom_minimum_size = Vector2(size, size)
	tile.add_theme_stylebox_override("panel", nine("kit_tile", Vector4(14, 14, 14, 14), Vector4(8, 8, 8, 8)))
	tile.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tile.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if icon != null:
		var picture := TextureRect.new()
		picture.texture = icon
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
		tile.add_child(picture)
	return tile

## Stat line: name on the left, value (and an optional green gain) on the right, a bronze
## hairline under it — for building effects and upgrade deltas.
static func stat_row(parent: Node, name: String, value: String, gain := "") -> HBoxContainer:
	var line := HBoxContainer.new()
	line.name = "KitStat"
	line.add_theme_constant_override("separation", 10)
	var left := label(line, name, 18, INK)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var right := label(line, value, 19, INK, LABEL_FONT)
	right.autowrap_mode = TextServer.AUTOWRAP_OFF
	right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	if not gain.is_empty():
		var plus := label(line, gain, 19, GOOD, LABEL_FONT)
		plus.autowrap_mode = TextServer.AUTOWRAP_OFF
	if parent != null:
		parent.add_child(line)
		hairline(parent)
	return line

static func hairline(parent: Node) -> void:
	var rule := ColorRect.new()
	rule.color = Color("#a67c3f55")
	rule.custom_minimum_size.y = 1
	rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(rule)

## Resource line: icon, name, amount / limit, rate (or a warning) on the right.
static func resource_row(parent: Node, icon: Texture2D, name: String, amount: String, rate: String, warning := false) -> HBoxContainer:
	var line := HBoxContainer.new()
	line.name = "KitResource"
	line.add_theme_constant_override("separation", 12)
	if icon != null:
		var picture := TextureRect.new()
		picture.texture = icon
		picture.custom_minimum_size = Vector2(32, 32)
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		picture.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
		line.add_child(picture)
	var title := label(line, name, 18, INK)
	title.custom_minimum_size.x = 110
	title.autowrap_mode = TextServer.AUTOWRAP_OFF
	var value := label(line, amount, 19, INK, LABEL_FONT)
	value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	value.autowrap_mode = TextServer.AUTOWRAP_OFF
	var speed := label(line, rate, 17, WARN if warning else GOOD, LABEL_FONT)
	speed.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	speed.autowrap_mode = TextServer.AUTOWRAP_OFF
	if parent != null:
		parent.add_child(line)
		hairline(parent)
	return line

## Catalogue tile: art on the left, name and state on the right, linen plate.
static func tile_button(title: String, note: String, art: Texture2D, note_colour := INK_MUTED) -> Button:
	var control := Button.new()
	control.custom_minimum_size = Vector2(250, 84)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	control.tooltip_text = title
	control.accessibility_name = title
	style_button(control, "tertiary")
	control.text = ""
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.offset_left = 14
	row.offset_right = -14
	row.offset_top = 6
	row.offset_bottom = -8
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	control.add_child(row)
	var picture := TextureRect.new()
	picture.texture = art
	picture.custom_minimum_size = Vector2(84, 0)
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(picture)
	var texts := VBoxContainer.new()
	texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	texts.alignment = BoxContainer.ALIGNMENT_CENTER
	texts.add_theme_constant_override("separation", 0)
	texts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(texts)
	var name_label := label(texts, title, 18, INK, LABEL_FONT)
	name_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var state := label(texts, note, 15, note_colour)
	state.autowrap_mode = TextServer.AUTOWRAP_OFF
	state.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return control

static func row_style() -> StyleBoxTexture:
	return nine("kit_row", Vector4(14, 14, 14, 14), Vector4(14, 10, 14, 12))

## List row: icon tile, title + subtitle, optional action button on the right.
## Returns the action button (or null).
static func list_row(parent: Node, icon: Texture2D, title: String, subtitle: String, action_text := "", action := Callable(), kind := "secondary") -> Button:
	var card := PanelContainer.new()
	card.name = "KitRow"
	card.add_theme_stylebox_override("panel", row_style())
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	card.add_child(row)
	if icon != null:
		row.add_child(icon_tile(icon, 60))
	var texts := VBoxContainer.new()
	texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	texts.alignment = BoxContainer.ALIGNMENT_CENTER
	texts.add_theme_constant_override("separation", 2)
	row.add_child(texts)
	label(texts, title, 20, INK, LABEL_FONT)
	if not subtitle.is_empty():
		label(texts, subtitle, 16, INK_MUTED)
	var control: Button = null
	if not action_text.is_empty():
		control = Button.new()
		control.text = action_text
		control.custom_minimum_size = Vector2(150, 50)
		control.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		style_button(control, kind)
		if action.is_valid():
			control.pressed.connect(action)
		row.add_child(control)
	if parent != null:
		parent.add_child(card)
	return control

## Hero illustration: a tinted ink-wash splash with the art centred over it.
static func hero(art: Texture2D, tint: Color, caption := "") -> Control:
	var box := Control.new()
	box.name = "KitHero"
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Two washes: a wide warm one and a deeper core, so the art sits in a painted pool.
	for layer in [[Vector4(0, 4, 0, -4), Color(tint, tint.a * 0.75)], [Vector4(70, 70, -70, -80), Color(tint.darkened(0.25), tint.a * 0.55)]]:
		var splash := TextureRect.new()
		splash.texture = tex("kit_splash")
		splash.modulate = layer[1]
		splash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		splash.offset_left = layer[0].x
		splash.offset_top = layer[0].y
		splash.offset_right = layer[0].z
		splash.offset_bottom = layer[0].w
		splash.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		splash.stretch_mode = TextureRect.STRETCH_SCALE
		splash.mouse_filter = Control.MOUSE_FILTER_IGNORE
		box.add_child(splash)
	var ground := TextureRect.new()
	ground.texture = ground_shadow()
	ground.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	ground.offset_left = -170
	ground.offset_right = 170
	ground.offset_top = -150 if not caption.is_empty() else -120
	ground.offset_bottom = -70 if not caption.is_empty() else -40
	ground.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ground.stretch_mode = TextureRect.STRETCH_SCALE
	ground.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(ground)
	var picture := TextureRect.new()
	picture.name = "Art"
	picture.texture = art
	picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	picture.offset_left = 56
	picture.offset_right = -56
	picture.offset_top = 70
	picture.offset_bottom = -84 if not caption.is_empty() else -60
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(picture)
	if not caption.is_empty():
		var plate := PanelContainer.new()
		plate.add_theme_stylebox_override("panel", nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(30, 4, 30, 6)))
		plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
		plate.grow_horizontal = Control.GROW_DIRECTION_BOTH
		plate.offset_top = -58
		plate.offset_bottom = -12
		plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var text := Label.new()
		text.text = caption
		text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		text.add_theme_font_override("font", LABEL_FONT)
		text.add_theme_font_size_override("font_size", 20)
		text.add_theme_color_override("font_color", GOLD)
		plate.add_child(text)
		box.add_child(plate)
	return box

static func ground_shadow() -> GradientTexture2D:
	if styles.has("ground"):
		return styles.ground
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	gradient.colors = PackedColorArray([Color(0.18, 0.11, 0.05, 0.42), Color(0.18, 0.11, 0.05, 0.16), Color(0.18, 0.11, 0.05, 0.0)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(1.0, 0.5)
	texture.width = 128
	texture.height = 64
	styles.ground = texture
	return texture

# ------------------------------------------------------------------ toasts / HUD

## Dark oak banner with a bronze rim, for toasts, the connection badge and notices.
static func toast_style() -> StyleBoxTexture:
	return nine("kit_pill", Vector4(18, 12, 18, 12), Vector4(24, 8, 24, 9))

## Resource chip on the HUD: a dark oak pill under the icon and amount.
static func hud_chip_styles() -> Dictionary:
	var normal := nine("kit_pill", Vector4(18, 12, 18, 12), Vector4(8, 2, 10, 2)).duplicate() as StyleBoxTexture
	normal.modulate_color = Color(1, 1, 1, 0.92)
	var hover := normal.duplicate() as StyleBoxTexture
	hover.modulate_color = Color(1.15, 1.1, 1.0, 1.0)
	var pressed := normal.duplicate() as StyleBoxTexture
	pressed.modulate_color = Color(0.78, 0.74, 0.68, 1.0)
	return {"normal": normal, "hover": hover, "pressed": pressed, "hover_pressed": pressed, "disabled": normal, "focus": StyleBoxEmpty.new()}

# ------------------------------------------------------------------ theme

## Theme for everything inside a window (linen body): ink text, kit buttons and fields.
static func theme(base: Theme) -> Theme:
	if themes.has(base):
		return themes[base]
	var t := base.duplicate() as Theme if base != null else Theme.new()
	t.default_font = BODY_FONT
	t.default_font_size = 19
	t.set_color("font_color", "Label", INK)
	t.set_color("font_shadow_color", "Label", Color.TRANSPARENT)
	t.set_color("default_color", "RichTextLabel", INK)
	var buttons := button_styles("tertiary")
	for type in ["Button", "OptionButton", "MenuButton"]:
		for state: String in buttons:
			t.set_stylebox(state, type, buttons[state])
		t.set_font("font", type, LABEL_FONT)
		t.set_font_size("font_size", type, 19)
		for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
			t.set_color(state, type, INK)
		t.set_color("font_disabled_color", type, Color("#efe9dc"))
	for type in ["CheckBox", "CheckButton"]:
		for state in ["normal", "hover", "pressed", "focus", "disabled", "hover_pressed"]:
			t.set_stylebox(state, type, StyleBoxEmpty.new())
		t.set_color("font_color", type, INK)
		t.set_color("font_hover_color", type, INK)
		t.set_color("font_pressed_color", type, INK)
		t.set_color("font_focus_color", type, INK)
	var field_box := nine("kit_field", Vector4(10, 10, 10, 10), Vector4(12, 6, 12, 6))
	t.set_stylebox("normal", "LineEdit", field_box)
	t.set_stylebox("focus", "LineEdit", flat(Color.TRANSPARENT, Color("#c99a45"), 6, Vector2.ZERO, 2))
	t.set_stylebox("read_only", "LineEdit", field_box)
	t.set_color("font_color", "LineEdit", INK)
	t.set_color("font_placeholder_color", "LineEdit", Color("#a08d72"))
	t.set_color("caret_color", "LineEdit", BRONZE)
	t.set_color("selection_color", "LineEdit", Color("#e9c77a88"))
	t.set_font("font", "LineEdit", LABEL_FONT)
	t.set_font_size("font_size", "LineEdit", 21)
	# Slider: recessed groove, gold fill, bronze knob.
	t.set_stylebox("slider", "HSlider", nine("kit_track", Vector4(11, 10, 11, 10), Vector4(0, 6, 0, 6)))
	var gold := nine("kit_fill", Vector4(11, 10, 11, 10), Vector4(0, 6, 0, 6))
	t.set_stylebox("grabber_area", "HSlider", gold)
	t.set_stylebox("grabber_area_highlight", "HSlider", gold)
	t.set_icon("grabber", "HSlider", tex("kit_knob"))
	t.set_icon("grabber_highlight", "HSlider", tex("kit_knob"))
	t.set_stylebox("background", "ProgressBar", nine("kit_track", Vector4(11, 10, 11, 10), Vector4.ZERO))
	t.set_stylebox("fill", "ProgressBar", nine("kit_fill", Vector4(11, 10, 11, 10), Vector4.ZERO))
	t.set_color("font_color", "ProgressBar", INK)
	t.set_stylebox("scroll", "VScrollBar", flat(Color("#5b46302a"), Color.TRANSPARENT, 4, Vector2(3, 3)))
	for state in ["grabber", "grabber_highlight", "grabber_pressed"]:
		t.set_stylebox(state, "VScrollBar", flat(Color("#a87b3fcc"), Color.TRANSPARENT, 4, Vector2(3, 3)))
	t.set_stylebox("scroll", "HScrollBar", flat(Color("#5b46302a"), Color.TRANSPARENT, 4, Vector2(3, 3)))
	for state in ["grabber", "grabber_highlight", "grabber_pressed"]:
		t.set_stylebox(state, "HScrollBar", flat(Color("#a87b3fcc"), Color.TRANSPARENT, 4, Vector2(3, 3)))
	t.set_stylebox("panel", "TooltipPanel", toast_style())
	t.set_color("font_color", "TooltipLabel", IVORY)
	t.set_font_size("font_size", "TooltipLabel", 17)
	t.set_stylebox("panel", "PopupMenu", toast_style())
	t.set_color("font_color", "PopupMenu", IVORY)
	themes[base] = t
	return t

## Instant touch-down acknowledgement used by the modal touch path (TouchScroll):
## a slight press-in scale around the centre.
static func press_in(control: Control) -> void:
	if control == null:
		return
	control.pivot_offset = control.size * 0.5
	control.scale = Vector2(0.965, 0.965)

static func press_out(control: Control) -> void:
	if control != null:
		control.scale = Vector2.ONE
