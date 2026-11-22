extends TextureButton
## One card of the construction strip (premium UI stage 3, ui_premium/STAGE3.md), drawn in
## one node (no theme boxes, no Label children): the diorama of the building rising out of an
## enamel panel, its name on a carved oak band, a line about what it gives, the cost (red where
## the stock is short) and the build time, and «Построено x/max» on the foot of the card.
##
## States (src/v6_build.gd decides them from the server catalogue and state):
## - build   bright, a warm gold glow round the frame;
## - short   bright, the missing amounts in red;
## - busy    being built: a progress bar and the time left;
## - locked  the art dimmed under a bronze padlock, the missing requirement in ochre;
## - noplot  dimmed, the reason (no free plot of its terrain, no open plot) in ochre;
## - maxed / group / start  built to the limit: the whole card in a light silver greyscale
##   (one shared material), no glow, no cost; a plain caption «Больше строить нельзя» where the
##   cost would be (a child node, so it keeps its colour; nothing about it looks like a
##   button) and the level of the standing building on a gold badge.
##
## Geometry (polish pass 4): the card body is the lower part of the node; the diorama (baked
## close on the building, transparent) stands on the body's top edge, its tile half inside the
## body and the building rising above it into the city behind the strip.

const UiKit = preload("res://src/ui_kit.gd")
const SIZE := Vector2(206, 404)
## The card body starts this far down; the building rises above it into the gap.
const TOP := 112.0
## The diorama: its square side, and where the bottom of its soil lands (below the body top).
const ART := 222.0
const ART_FOOT := 80.0
## The baked pictures put the soil bottom this far down (tools/bake_building_art.gd BOTTOM).
const ART_BOTTOM := 0.975
## Top of the caption of a finished type (where the cost of the others is).
const CAPTION_TOP := TOP + ART_FOOT + 2.0 + 36.0 + 6.0 + 42.0 + 12.0
const GREY_SHADER := preload("res://src/build_card_grey.gdshader")
const DONE_STATES := ["maxed", "group", "start"]

static var grey_material: ShaderMaterial
static var paragraphs := {}
static var name_sizes := {}
static var styles := {}

var type := ""
var title := ""
var blurb := ""
var note := ""
var art: Texture2D
var cost := {}
var short := {}
var icons := {}
var time_text := ""
var state := "build"
var built_text := "0/1"
var level_text := ""
var progress := -1.0
var stamp: Control

static func grey() -> ShaderMaterial:
	if grey_material == null:
		grey_material = ShaderMaterial.new()
		grey_material.shader = GREY_SHADER
	return grey_material

static func style(key: String) -> StyleBox:
	if styles.has(key):
		return styles[key]
	var box: StyleBox
	match key:
		"body":
			box = UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), Color("#f6ecd8"))
		"panel":
			box = UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), Color("#5b3f2a"))
		"panel_dim":
			box = UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), Color("#3d3530"))
		"band":
			box = UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO)
		"frame":
			box = UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color.WHITE)
		"frame_lit":
			box = UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color(1.35, 1.2, 0.86))
		"foot":
			box = UiKit.flat(Color("#e3d2b2"), Color("#a67c3f66"), 4, Vector2.ZERO)
		"shadow":
			var flat := StyleBoxFlat.new()
			flat.bg_color = Color(0, 0, 0, 0)
			flat.shadow_color = Color(0, 0, 0, 0.55)
			flat.shadow_size = 14
			flat.shadow_offset = Vector2(0, 6)
			flat.set_corner_radius_all(14)
			box = flat
		"glow":
			var lit := StyleBoxFlat.new()
			lit.bg_color = Color(0, 0, 0, 0)
			lit.shadow_color = Color("#ffc25a99")
			lit.shadow_size = 12
			lit.set_corner_radius_all(16)
			box = lit
		"track":
			box = UiKit.nine("kit_track", Vector4(8, 6, 8, 6), Vector4.ZERO)
		"fill":
			box = UiKit.nine("kit_fill_green", Vector4(8, 6, 8, 6), Vector4.ZERO)
	styles[key] = box
	return box

## Wrapped, centred text, shaped once per string and width for the session.
static func paragraph(text: String, font: Font, size: int, width: float, lines := 2) -> TextParagraph:
	var key := "%d|%d|%d|%s" % [font.get_instance_id(), size, int(width), text]
	var shaped: TextParagraph = paragraphs.get(key)
	if shaped == null:
		if paragraphs.size() > 300:
			paragraphs.clear()
		shaped = TextParagraph.new()
		shaped.add_string(text, font, size)
		shaped.width = width
		shaped.alignment = HORIZONTAL_ALIGNMENT_CENTER
		shaped.max_lines_visible = lines
		shaped.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		paragraphs[key] = shaped
	return shaped

func done() -> bool:
	return state in DONE_STATES

## Applies the state: the desaturating material and the colour stamp of finished types.
func refresh() -> void:
	material = grey() if done() else null
	if done() and stamp == null:
		stamp = Stamp.new()
		stamp.card = self
		stamp.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(stamp)
		stamp.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	if stamp != null:
		stamp.visible = done()
		stamp.queue_redraw()
	accessibility_name = "%s · %s" % [title, note if not note.is_empty() else ("построено " + built_text)]
	queue_redraw()

## The largest font size (19, 17 or 15) at which a name fits the band; trimmed only past 15.
static func name_size(text: String, width: float) -> int:
	var key := "%s|%d" % [text, int(width)]
	if not name_sizes.has(key):
		name_sizes[key] = 15
		for font_size: int in [19, 17]:
			if UiKit.LABEL_FONT.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x <= width:
				name_sizes[key] = font_size
				break
	return name_sizes[key]

## Where the diorama is drawn: its soil bottom ART_FOOT below the body top, centred.
static func art_rect() -> Rect2:
	return Rect2((SIZE.x - ART) * 0.5, TOP + ART_FOOT - ART * ART_BOTTOM, ART, ART)

func _draw() -> void:
	var mode := get_draw_mode()
	var pressed := mode == DRAW_PRESSED or mode == DRAW_HOVER_PRESSED
	var body := Rect2(0, TOP, size.x, size.y - TOP)
	var lit := state in ["build", "short"]
	draw_style_box(style("shadow"), body.grow(-4))
	if lit:
		draw_style_box(style("glow"), body.grow(-3))
	draw_style_box(style("body"), body)
	# Enamel panel under the diorama's tile, with a pool of warm light on it.
	var panel := Rect2(7, TOP + 7, size.x - 14, ART_FOOT - 2.0)
	var dim := state in ["locked", "noplot"]
	draw_style_box(style("panel_dim" if dim else "panel"), panel)
	draw_texture_rect(UiKit.warm_glow(), Rect2(panel.position.x - 20, panel.position.y - 10, panel.size.x + 40, panel.size.y + 20), false, Color(1, 1, 1, 0.4 if dim else 0.75))
	# (The diorama itself is drawn last, over the frame, so the building rises above the card.)
	# Name on a carved oak band across the card.
	var band := Rect2(0, TOP + ART_FOOT + 2.0, size.x, 36)
	draw_style_box(style("band"), band)
	var name_line := UiKit.KitText.line(title, UiKit.LABEL_FONT, name_size(title, size.x - 36.0), size.x - 36.0)
	var name_at := Vector2(roundf((size.x - name_line.get_size().x) * 0.5), band.position.y + roundf((band.size.y - name_line.get_size().y) * 0.5) - 1.0)
	name_line.draw_outline(get_canvas_item(), name_at, 4, UiKit.SHADE)
	name_line.draw(get_canvas_item(), name_at, UiKit.GOLD)
	var y := band.end.y + 6.0
	# What it gives, or what stands in the way.
	var line_text := note if not note.is_empty() and state in ["locked", "noplot"] else blurb
	var words := paragraph(line_text, UiKit.BODY_FONT, 14, size.x - 24.0)
	words.draw(get_canvas_item(), Vector2(12, y), UiKit.WARN if line_text == note else UiKit.INK_MUTED)
	y += 42.0
	if not done():
		if state == "busy":
			draw_busy(y)
		else:
			draw_cost(y)
	# Foot: «Построено x/max».
	var foot := Rect2(8, size.y - 36, size.x - 16, 27)
	draw_style_box(style("foot"), foot)
	var left := UiKit.KitText.line("Строится" if state == "busy" else "Построено", UiKit.BODY_FONT, 14)
	left.draw(get_canvas_item(), Vector2(foot.position.x + 9, foot.position.y + roundf((foot.size.y - left.get_size().y) * 0.5)), UiKit.INK_MUTED)
	var right := UiKit.KitText.line(time_text if state == "busy" else built_text, UiKit.LABEL_FONT, 16)
	right.draw(get_canvas_item(), Vector2(foot.end.x - 9 - right.get_size().x, foot.position.y + roundf((foot.size.y - right.get_size().y) * 0.5)), UiKit.INK)
	draw_style_box(style("frame_lit" if lit else "frame"), body)
	if art != null:
		var tone := Color(0.6, 0.57, 0.55) if state == "locked" else (Color(0.8, 0.78, 0.76) if state == "noplot" else Color.WHITE)
		if pressed:
			tone = tone.darkened(0.08)
		var picture := art_rect()
		# A soft shadow of the diorama on the card.
		draw_texture_rect(UiKit.ground_shadow(), Rect2(picture.position.x + 18, TOP + ART_FOOT - 22, picture.size.x - 36, 30), false, Color(1, 1, 1, 0.5))
		draw_texture_rect(art, picture, false, tone)
	if state == "locked":
		UiKit.KitPaint.lock(self, Vector2(size.x * 0.5, TOP + ART_FOOT * 0.5 - 6.0), 50.0)

# Cost in rows of three (icon and amount, red where the stock is short) and the build time.
func draw_cost(y: float) -> void:
	var keys: Array = []
	for resource: String in cost:
		if int(cost[resource]) > 0:
			keys.append(resource)
	var rows: Array = []
	if keys.size() <= 3:
		rows = [keys]
	else:
		var split := ceili(keys.size() / 2.0)
		rows = [keys.slice(0, split), keys.slice(split)]
	if keys.is_empty():
		rows = []
		var free := UiKit.KitText.line("Бесплатно", UiKit.LABEL_FONT, 17)
		free.draw(get_canvas_item(), Vector2(roundf((size.x - free.get_size().x) * 0.5), y + 6), UiKit.GOOD)
	for row: Array in rows:
		var parts: Array = []
		var total := 0.0
		for resource: String in row:
			var amount := UiKit.KitText.line(UiKit.compact(int(cost[resource])), UiKit.LABEL_FONT, 16)
			parts.append([resource, amount])
			total += 22.0 + 4.0 + amount.get_size().x
		total += 12.0 * (row.size() - 1)
		var x := roundf((size.x - total) * 0.5)
		for part: Array in parts:
			var icon: Texture2D = icons.get(part[0])
			if icon != null:
				draw_texture_rect(icon, Rect2(x, y, 22, 22), false)
			var amount: TextLine = part[1]
			amount.draw(get_canvas_item(), Vector2(x + 26.0, y + roundf((22.0 - amount.get_size().y) * 0.5)), UiKit.BAD if short.has(part[0]) else UiKit.INK)
			x += 26.0 + amount.get_size().x + 12.0
		y += 26.0
	if rows.size() < 2:
		y += 26.0
	# Time on a small pill.
	var clock := UiKit.KitText.line(time_text, UiKit.LABEL_FONT, 16)
	var width := 22.0 + 8.0 + clock.get_size().x
	var at := Vector2(roundf((size.x - width) * 0.5), y + 3.0)
	draw_texture_rect(UiKit.tex("kit_hourglass"), Rect2(at.x, at.y - 1.0, 18, 22), false, Color(0.55, 0.4, 0.2))
	clock.draw(get_canvas_item(), Vector2(at.x + 26.0, at.y + roundf((20.0 - clock.get_size().y) * 0.5)), UiKit.BRONZE)

func draw_busy(y: float) -> void:
	var bar := Rect2(20, y + 10, size.x - 40, 16)
	draw_style_box(style("track"), bar)
	if progress > 0.0:
		draw_style_box(style("fill"), Rect2(bar.position, Vector2(maxf(16.0, bar.size.x * clampf(progress, 0.0, 1.0)), bar.size.y)))
	var label := UiKit.KitText.line("Строительство идёт", UiKit.LABEL_FONT, 16)
	label.draw(get_canvas_item(), Vector2(roundf((size.x - label.get_size().x) * 0.5), y + 34), UiKit.GOOD)

## The colour layer of a finished type over its silver card: a plain caption where the cost
## would be (text only: nothing about it looks like a button) and the level badge.
class Stamp extends Control:
	const INK := Color("#4d4741")
	var card

	func caption() -> Array:
		return {"group": ["Пищевой участок", "уже занят"], "start": ["Даётся только", "при основании"]}.get(card.state, ["Больше строить", "нельзя"])

	func _draw() -> void:
		if card == null:
			return
		var w := size.x
		var words: Array = caption()
		var first := UiKit.KitText.line(words[0], UiKit.LABEL_FONT, 16)
		var second := UiKit.KitText.line(words[1], UiKit.LABEL_FONT, 16)
		first.draw(get_canvas_item(), Vector2(roundf((w - first.get_size().x) * 0.5), CAPTION_TOP), INK)
		second.draw(get_canvas_item(), Vector2(roundf((w - second.get_size().x) * 0.5), CAPTION_TOP + first.get_size().y), INK)
		if not card.level_text.is_empty():
			# Level of the standing building on a gold badge at the corner of the body.
			draw_texture_rect(UiKit.tex("kit_badge"), Rect2(8, TOP + 8, 44, 42), false)
			var numeral := UiKit.KitText.line(card.level_text, UiKit.TITLE_FONT, 15 if card.level_text.length() < 3 else 12)
			numeral.draw(get_canvas_item(), Vector2(roundf(30 - numeral.get_size().x * 0.5), TOP + 18), UiKit.GOLD)
