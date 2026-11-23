extends RefCounted
## Drawn controls of the premium UI stage 4b (ui_premium/STAGE4B.md), shared by the menu, the
## account, the market, the economy, the objectives, the archive, the world map windows and
## the forest panels. Each is one node that draws itself from cached text lines
## (UiKit.KitText), so a window of twenty rows does not lay out sixty labels; buttons stay
## real Buttons (tests, screen readers, touch feedback).
##
## Compiled off the launch path with the window scripts (v6_panels.warm_views), never preloaded
## by main.gd.

const UiKit = preload("res://src/ui_kit.gd")

static var tile_themes := {}
## A Theme for a container of drawn buttons: no stylebox and transparent text, so a drawn
## button keeps its caption in `text` (tests and screen readers read it) without the
## Button drawing it a second time.
static func drawn_buttons_theme() -> Theme:
	if tile_themes.has("drawn"):
		return tile_themes.drawn
	var theme := Theme.new()
	for state in ["normal", "hover", "pressed", "focus", "disabled", "hover_pressed"]:
		theme.set_stylebox(state, "Button", StyleBoxEmpty.new())
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_disabled_color", "font_hover_pressed_color"]:
		theme.set_color(state, "Button", Color.TRANSPARENT)
	theme.set_font("font", "Button", UiKit.LABEL_FONT)
	theme.set_font_size("font_size", "Button", 16)
	tile_themes.drawn = theme
	return theme

## Static painting helpers (an inner class, so the drawn classes below can call them).
class Paint:
	static var badge_boxes := {}

	## An enamel count badge (red: unread, green: ready, bronze: running) centred at `spot`.
	static func draw_badge(item: CanvasItem, spot: Vector2, text: String, tone: String) -> void:
		if text.is_empty():
			return
		var tag := UiKit.KitText.line(text, UiKit.LABEL_FONT, 14)
		var radius := maxf(11.0, tag.get_size().x * 0.5 + 6.0)
		if not badge_boxes.has(tone):
			var rim := StyleBoxFlat.new()
			rim.bg_color = {"green": Color("#2f7d36"), "bronze": Color("#7a5222"), "blue": Color("#2a5d93")}.get(tone, Color("#a8231d"))
			rim.border_color = Color("#f2d48b")
			rim.set_border_width_all(2)
			rim.set_corner_radius_all(11)
			rim.anti_aliasing = true
			rim.shadow_color = Color(0, 0, 0, 0.4)
			rim.shadow_size = 3
			badge_boxes[tone] = rim
		item.draw_style_box(badge_boxes[tone], Rect2(spot - Vector2(radius, 11.0), Vector2(radius * 2.0, 22.0)))
		tag.draw(item.get_canvas_item(), Vector2(roundf(spot.x - tag.get_size().x * 0.5), roundf(spot.y - tag.get_size().y * 0.5)), Color.WHITE)

	## A bronze medallion with an emblem (the HUD's disc), `d` across, centred at `centre`.
	static func draw_medal(item: CanvasItem, centre: Vector2, d: float, emblem: Texture2D, gold := false, tone := Color.WHITE) -> void:
		item.draw_circle(centre + Vector2(0, 2), d * 0.5 + 2.0, Color(0, 0, 0, 0.3), true, -1.0, true)
		item.draw_texture_rect(UiKit.tex("kit_rail_on" if gold else "kit_rail"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false, tone)
		if emblem != null:
			var side := d * 0.6
			item.draw_texture_rect(emblem, Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false, tone)

	## Text split over at most two lines of `width` (at the space nearest the middle).
	static func two_lines(text: String, font: Font, size: int, width: float) -> Array:
		var whole := UiKit.KitText.line(text, font, size)
		if whole.get_size().x <= width or not " " in text:
			return [UiKit.KitText.line(text, font, size, width)]
		var best := -1
		var middle := text.length() / 2
		for i in text.length():
			if text[i] == " " and (best < 0 or absi(i - middle) < absi(best - middle)):
				best = i
		return [UiKit.KitText.line(text.left(best), font, size, width), UiKit.KitText.line(text.substr(best + 1), font, size, width)]

# ------------------------------------------------------------------ menu tile

## A tile of the menu: a linen plate, a bronze medallion with a forged emblem, the caption
## under it (two lines at most), an optional note and an enamel badge. Touch-down shows at
## once (the plate darkens, the medallion sinks 2 px).
class MenuTile extends Button:
	var emblem: Texture2D
	var caption := ""
	var note := ""
	var badge := ""
	var badge_tone := "red"
	var accent := false

	func _init() -> void:
		focus_mode = Control.FOCUS_NONE
		# The caption is drawn in two lines; the Button's own (transparent) text must not
		# widen the tile to one line of it, or a row of six pushes the window off the screen.
		clip_text = true
		custom_minimum_size = Vector2(136, 116)
		mouse_entered.connect(queue_redraw)
		mouse_exited.connect(queue_redraw)
		button_down.connect(queue_redraw)
		button_up.connect(queue_redraw)

	func setup(title: String, emblem_name: String, line := "", count := "", tone := "red") -> MenuTile:
		caption = title
		text = title
		tooltip_text = title if line.is_empty() else "%s · %s" % [title, line]
		accessibility_name = tooltip_text
		emblem = UiKit.tex(emblem_name)
		note = line
		badge = count
		badge_tone = tone
		return self

	func _draw() -> void:
		var mode := get_draw_mode()
		var down := mode == DRAW_PRESSED or mode == DRAW_HOVER_PRESSED
		var plate := Rect2(Vector2.ZERO, size)
		draw_style_box(UiKit.row_style(), plate)
		if accent:
			draw_rect(plate.grow(-6), Color(1.0, 0.82, 0.4, 0.14), true)
		if down:
			draw_rect(plate.grow(-4), Color(0.25, 0.16, 0.06, 0.14), true)
		elif is_hovered():
			draw_rect(plate.grow(-4), Color(1.0, 0.9, 0.6, 0.12), true)
		var d := 60.0 - (3.0 if down else 0.0)
		var centre := Vector2(size.x * 0.5, 38.0 + (2.0 if down else 0.0))
		Paint.draw_medal(self, centre, d, emblem, accent, Color(0.86, 0.82, 0.78) if down else Color.WHITE)
		var lines := Paint.two_lines(caption, UiKit.LABEL_FONT, 16, size.x - 14.0)
		var y := 72.0 + (1.0 if down else 0.0)
		if lines.size() == 1 and not note.is_empty():
			y -= 2.0
		for line: TextLine in lines:
			line.draw(get_canvas_item(), Vector2(roundf((size.x - line.get_size().x) * 0.5), y), UiKit.INK)
			y += line.get_size().y - 3.0
		if not note.is_empty() and lines.size() == 1:
			var small := UiKit.KitText.line(note, UiKit.BODY_FONT, 13, size.x - 14.0)
			small.draw(get_canvas_item(), Vector2(roundf((size.x - small.get_size().x) * 0.5), y + 2.0), UiKit.INK_MUTED)
		Paint.draw_badge(self, centre + Vector2(d * 0.4, -d * 0.36), badge, badge_tone)

# ------------------------------------------------------------------ card (row)

## A drawn row card: a plate (linen, gold or dim), an icon (an enamel tile, a medallion or a
## portrait), a title with an enamel ribbon, a subtitle, a line, chips with icons and an
## optional bar; buttons are real children anchored at the right (add_action).
class Card extends Control:
	var plate := "row"
	var icon: Texture2D
	var icon_mode := "tile"
	var icon_tint := Color.WHITE
	var numeral := ""
	var title := ""
	var title_size := 19
	var subtitle := ""
	var subtitle_colour := UiKit.INK_MUTED
	var line := ""
	var line_colour := UiKit.BRONZE
	var ribbon := ""
	var ribbon_colour := UiKit.GOOD
	## [[Texture2D or null, text, Color], ...]
	var chips: Array = []
	var bar := -1.0
	var bar_green := false
	var bar_text := ""
	var actions: Array[Button] = []
	var action_column := 0.0
	static var gold_fill: StyleBox
	static var gold_frame: StyleBox

	func _init() -> void:
		custom_minimum_size.y = 92
		size_flags_horizontal = Control.SIZE_EXPAND_FILL
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	## A button at the right (several stack leftwards), vertically centred.
	func add_action(caption: String, kind: String, at_size: Vector2) -> Button:
		var control := Button.new()
		control.text = caption
		add_child(control)
		UiKit.style_button(control, kind, 19 if kind == "primary" else 18)
		control.custom_minimum_size = at_size
		var right := 18.0 + action_column
		control.anchor_left = 1.0
		control.anchor_right = 1.0
		control.anchor_top = 0.5
		control.anchor_bottom = 0.5
		control.offset_left = -at_size.x - right
		control.offset_right = -right
		control.offset_top = -at_size.y * 0.5
		control.offset_bottom = at_size.y * 0.5
		action_column += at_size.x + 12.0
		actions.append(control)
		queue_redraw()
		return control

	func _draw() -> void:
		var box := Rect2(Vector2.ZERO, size)
		draw_style_box(UiKit.row_style(), box)
		if plate == "gold":
			if gold_fill == null:
				var warm := StyleBoxFlat.new()
				warm.bg_color = Color(1.0, 0.8, 0.34, 0.2)
				warm.set_corner_radius_all(8)
				warm.shadow_color = Color(0.95, 0.68, 0.2, 0.32)
				warm.shadow_size = 7
				gold_fill = warm
				gold_frame = UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color(1.35, 1.18, 0.82))
			draw_style_box(gold_fill, box.grow(-5))
			draw_style_box(gold_frame, box)
		elif plate == "dim":
			draw_rect(box.grow(-4), Color(0.42, 0.36, 0.3, 0.12), true)
		var x := 18.0
		if icon != null or not numeral.is_empty():
			var side := minf(70.0, size.y - 18.0)
			var tile := Rect2(16.0, roundf((size.y - side) * 0.5), side, side)
			match icon_mode:
				"disc":
					Paint.draw_medal(self, tile.get_center(), side, icon, plate == "gold", icon_tint)
				"portrait":
					draw_style_box(UiKit.nine("kit_tile", Vector4(14, 14, 14, 14), Vector4.ZERO), tile)
					if icon != null:
						draw_texture_rect(icon, tile.grow(-4), false, icon_tint)
				"plain":
					if icon != null:
						draw_texture_rect(icon, tile.grow(-4), false, icon_tint)
				_:
					draw_style_box(UiKit.nine("kit_tile", Vector4(14, 14, 14, 14), Vector4.ZERO), tile)
					if icon != null:
						draw_texture_rect(icon, tile.grow(-12), false, icon_tint)
			if not numeral.is_empty():
				var mark := UiKit.KitText.line(numeral, UiKit.TITLE_FONT, 26)
				var at := tile.get_center() - mark.get_size() * 0.5
				mark.draw_outline(get_canvas_item(), at, 5, UiKit.SHADE)
				mark.draw(get_canvas_item(), at, UiKit.GOLD)
			x = tile.end.x + 16.0
		var right := size.x - 18.0 - action_column
		var width := maxf(40.0, right - x)
		var parts: Array = []
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, title_size, width - (_ribbon_width() if not ribbon.is_empty() else 0.0))
		parts.append(["head", head])
		if not subtitle.is_empty():
			parts.append(["sub", UiKit.KitText.line(subtitle, UiKit.BODY_FONT, 15, width)])
		if not line.is_empty():
			parts.append(["line", UiKit.KitText.line(line, UiKit.LABEL_FONT, 16, width)])
		if not chips.is_empty():
			parts.append(["chips", null])
		if bar >= 0.0:
			parts.append(["bar", null])
		var heights := {"chips": 26.0, "bar": 22.0}
		var total := 0.0
		for part: Array in parts:
			total += heights[part[0]] if heights.has(part[0]) else (part[1] as TextLine).get_size().y
		total += 2.0 * (parts.size() - 1)
		var y := roundf((size.y - total) * 0.5)
		for part: Array in parts:
			match part[0]:
				"head":
					var t: TextLine = part[1]
					t.draw(get_canvas_item(), Vector2(x, y), UiKit.INK)
					if not ribbon.is_empty():
						_draw_ribbon(Vector2(x + t.get_size().x + 10.0, y + t.get_size().y * 0.5))
					y += t.get_size().y + 2.0
				"sub":
					(part[1] as TextLine).draw(get_canvas_item(), Vector2(x, y), subtitle_colour)
					y += (part[1] as TextLine).get_size().y + 2.0
				"line":
					(part[1] as TextLine).draw(get_canvas_item(), Vector2(x, y), line_colour)
					y += (part[1] as TextLine).get_size().y + 2.0
				"chips":
					var cx := x
					for chip: Array in chips:
						var words := UiKit.KitText.line(str(chip[1]), UiKit.LABEL_FONT, 16)
						if chip[0] != null:
							draw_texture_rect(chip[0], Rect2(cx, y + 2.0, 22, 22), false)
							cx += 25.0
						words.draw(get_canvas_item(), Vector2(cx, y + roundf((24.0 - words.get_size().y) * 0.5) + 1.0), chip[2] if chip.size() > 2 else UiKit.INK)
						cx += words.get_size().x + 16.0
						if cx > right:
							break
					y += 28.0
				"bar":
					var track := Rect2(x, y + 3.0, width - (0.0 if bar_text.is_empty() else 0.0), 16.0)
					draw_style_box(UiKit.nine("kit_track", Vector4(11, 10, 11, 10), Vector4.ZERO), track)
					if bar > 0.0:
						var fill := UiKit.nine("kit_fill_green" if bar_green else "kit_fill", Vector4(11, 10, 11, 10), Vector4.ZERO)
						draw_style_box(fill, Rect2(track.position, Vector2(maxf(20.0, track.size.x * clampf(bar, 0.0, 1.0)), track.size.y)))
					if not bar_text.is_empty():
						var words := UiKit.KitText.line(bar_text, UiKit.LABEL_FONT, 13)
						var at := Vector2(roundf(track.get_center().x - words.get_size().x * 0.5), roundf(track.get_center().y - words.get_size().y * 0.5))
						words.draw_outline(get_canvas_item(), at, 4, Color("#fff8e8"))
						words.draw(get_canvas_item(), at, UiKit.INK)
					y += 24.0

	func _ribbon_width() -> float:
		return UiKit.KitText.line(ribbon, UiKit.LABEL_FONT, 14).get_size().x + 34.0

	func _draw_ribbon(at: Vector2) -> void:
		var words := UiKit.KitText.line(ribbon, UiKit.LABEL_FONT, 14)
		var tag := Rect2(at.x, at.y - 11.0, words.get_size().x + 20.0, 22.0)
		draw_style_box(UiKit.flat(ribbon_colour, Color("#f2d48b"), 11, Vector2.ZERO, 1), tag)
		words.draw(get_canvas_item(), Vector2(tag.position.x + 10.0, roundf(tag.get_center().y - words.get_size().y * 0.5)), Color.WHITE)

# ------------------------------------------------------------------ oak profile column

## The dark oak column of the menu and the account: a gold medallion with the crest, the
## settlement's name, a pill with the hall level, a few figures and a note. One node.
class ProfileCard extends Control:
	var emblem: Texture2D
	var title := ""
	var pill := ""
	var lines: Array = []
	var note := ""
	var banner := Color("#8e2419")

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	## Room for the crest, the name, the pill and every line (the settings sit under it).
	func _get_minimum_size() -> Vector2:
		return Vector2(0, 162.0 + (40.0 if not pill.is_empty() else 0.0) + lines.size() * 32.0 + (24.0 if not note.is_empty() else 0.0))

	func _draw() -> void:
		var d := 92.0
		var centre := Vector2(size.x * 0.5, d * 0.5 + 4.0)
		# A pennant of the settlement's colour hangs behind the crest.
		var pennant := PackedVector2Array([centre + Vector2(-30, -6), centre + Vector2(30, -6), centre + Vector2(30, 70), centre + Vector2(0, 58), centre + Vector2(-30, 70)])
		draw_colored_polygon(pennant, banner)
		draw_polyline(pennant + PackedVector2Array([pennant[0]]), Color("#e2b766"), 2.0, true)
		Paint.draw_medal(self, centre, d, emblem, true)
		var y := d + 34.0
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, 23, size.x)
		var at := Vector2(roundf((size.x - head.get_size().x) * 0.5), y)
		head.draw_outline(get_canvas_item(), at, 5, Color(0, 0, 0, 0.55))
		head.draw(get_canvas_item(), at, UiKit.GOLD)
		y += head.get_size().y + 6.0
		if not pill.is_empty():
			var words := UiKit.KitText.line(pill, UiKit.LABEL_FONT, 15)
			var plate := Rect2(roundf((size.x - words.get_size().x - 30.0) * 0.5), y, words.get_size().x + 30.0, 26.0)
			draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), plate)
			words.draw(get_canvas_item(), Vector2(plate.position.x + 15.0, roundf(plate.get_center().y - words.get_size().y * 0.5)), Color("#f6e7c4"))
			y += 40.0
		for pair: Array in lines:
			var name_line := UiKit.KitText.line(str(pair[0]), UiKit.BODY_FONT, 16, size.x * 0.62)
			var value_line := UiKit.KitText.line(str(pair[1]), UiKit.LABEL_FONT, 17, size.x * 0.36)
			if pair.size() > 2 and pair[2] != null:
				draw_texture_rect(pair[2], Rect2(0, y, 22, 22), false)
				name_line = UiKit.KitText.line(str(pair[0]), UiKit.BODY_FONT, 16, size.x * 0.62 - 28.0)
				name_line.draw(get_canvas_item(), Vector2(28, y), Color("#e4d3b0"))
			else:
				name_line.draw(get_canvas_item(), Vector2(0, y), Color("#e4d3b0"))
			value_line.draw(get_canvas_item(), Vector2(size.x - value_line.get_size().x, y), UiKit.IVORY)
			y += maxf(name_line.get_size().y, value_line.get_size().y) + 3.0
			draw_rect(Rect2(0, y, size.x, 1.0), Color("#c9a05a40"))
			y += 7.0
		if not note.is_empty() and y + 20.0 < size.y:
			var tip := UiKit.KitText.line(note, UiKit.BODY_FONT, 14, size.x)
			tip.draw(get_canvas_item(), Vector2(0, y + 2.0), Color("#c8b48f"))

# ------------------------------------------------------------------ code plate

## A pairing code, large and legible: groups of four on a carved oak strip, gold Philosopher
## figures, a lozenge between the groups. The code is drawn, never logged.
class CodePlate extends Control:
	var code := ""

	func _init() -> void:
		custom_minimum_size = Vector2(0, 92)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func groups() -> PackedStringArray:
		var out: PackedStringArray = []
		var clean := code.replace(" ", "")
		for i in range(0, clean.length(), 4):
			out.append(clean.substr(i, 4))
		return out

	func _draw() -> void:
		var parts := groups()
		var lines: Array = []
		var total := 0.0
		for part in parts:
			var t := UiKit.KitText.line(part, UiKit.LABEL_FONT, 40)
			lines.append(t)
			total += t.get_size().x
		var gap := 34.0
		total += gap * maxf(0.0, lines.size() - 1)
		var plate := Rect2(roundf((size.x - total) * 0.5) - 44.0, 4.0, total + 88.0, size.y - 8.0)
		draw_style_box(UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO), plate)
		var x := plate.position.x + 44.0
		for i in lines.size():
			var t: TextLine = lines[i]
			var at := Vector2(x, roundf(plate.get_center().y - t.get_size().y * 0.5))
			t.draw_outline(get_canvas_item(), at, 5, UiKit.SHADE)
			t.draw(get_canvas_item(), at, UiKit.GOLD)
			x += t.get_size().x
			if i < lines.size() - 1:
				var c := Vector2(x + gap * 0.5, plate.get_center().y)
				draw_colored_polygon(PackedVector2Array([c + Vector2(0, -6), c + Vector2(5, 0), c + Vector2(0, 6), c + Vector2(-5, 0)]), UiKit.GOLD_DIM)
				x += gap

# ------------------------------------------------------------------ chips

## A row of oak chips: [[icon Texture2D or null, text], ...]; for distances, times and
## coordinates on the world cards. One node.
class ChipRow extends Control:
	const LINE := 34.0
	const LINE_GAP := 6.0
	var chips: Array = []

	func _init() -> void:
		custom_minimum_size.y = LINE
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		resized.connect(fit)

	## The pills in reading order at this width, [rect, line, chip]: a chip that does not fit
	## goes to the next line (a distance after three rewards in a side window), never dropped.
	func pills() -> Array:
		var placed: Array = []
		var x := 0.0
		var y := 0.0
		for chip: Array in chips:
			var words := UiKit.KitText.line(str(chip[1]), UiKit.LABEL_FONT, 16)
			var w := words.get_size().x + (54.0 if chip[0] != null else 28.0)
			if x + w > size.x and x > 0.0:
				x = 0.0
				y += LINE + LINE_GAP
			placed.append([Rect2(x, y + 2.0, w, LINE - 4.0), words, chip])
			x += w + 10.0
		return placed

	## Height for the lines the chips take at the current width.
	func fit() -> void:
		var placed := pills()
		var height := LINE if placed.is_empty() else (placed[-1][0] as Rect2).end.y + 2.0
		if not is_equal_approx(custom_minimum_size.y, height):
			custom_minimum_size.y = height
		queue_redraw()

	func _draw() -> void:
		for entry: Array in pills():
			var pill: Rect2 = entry[0]
			var chip: Array = entry[2]
			draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), pill)
			var tx := pill.position.x + 14.0
			if chip[0] != null:
				draw_texture_rect(chip[0], Rect2(pill.position.x + 10.0, pill.get_center().y - 11.0, 22, 22), false)
				tx = pill.position.x + 38.0
			entry[1].draw(get_canvas_item(), Vector2(tx, roundf(pill.get_center().y - entry[1].get_size().y * 0.5)), UiKit.GOLD if chip.size() < 3 else chip[2])

# ------------------------------------------------------------------ portrait card

## The head of a world window: a framed picture on an ink wash (a creature, a settlement's
## crest, a party's portraits), the name, a line under it and a kokoshnik badge with a level.
class HeadCard extends Control:
	var picture: Texture2D
	var pictures: Array = []
	var emblem: Texture2D
	var banner := Color("#8e2419")
	var title := ""
	var subtitle := ""
	var level := ""
	var tint := Color("#6d7a5a")

	func _init() -> void:
		custom_minimum_size.y = 150
		size_flags_horizontal = Control.SIZE_EXPAND_FILL
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var frame := Rect2(0, 0, size.x, size.y)
		draw_style_box(UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO), frame)
		var art := Rect2(14, 10, size.y - 20.0, size.y - 20.0)
		# Ink-wash pool behind the picture.
		draw_texture_rect(UiKit.tex("kit_ink"), art.grow(10), false, Color(tint, 0.85))
		if picture != null:
			var source := picture.get_size()
			var k := minf(art.size.x / source.x, art.size.y / source.y)
			var drawn := source * k
			draw_texture_rect(picture, Rect2(art.get_center() - drawn * 0.5, drawn), false)
		elif not pictures.is_empty():
			var count := mini(3, pictures.size())
			for i in count:
				var side := art.size.y * 0.62
				var spot := art.get_center() + Vector2((i - (count - 1) * 0.5) * side * 0.52, (absf(i - (count - 1) * 0.5)) * 6.0)
				draw_style_box(UiKit.nine("kit_tile", Vector4(14, 14, 14, 14), Vector4.ZERO), Rect2(spot - Vector2(side, side) * 0.5, Vector2(side, side)))
				draw_texture_rect(pictures[i], Rect2(spot - Vector2(side, side) * 0.5, Vector2(side, side)).grow(-4), false)
		elif emblem != null:
			var pennant := PackedVector2Array([art.get_center() + Vector2(-26, -40), art.get_center() + Vector2(26, -40), art.get_center() + Vector2(26, 40), art.get_center() + Vector2(0, 28), art.get_center() + Vector2(-26, 40)])
			draw_colored_polygon(pennant, banner)
			draw_polyline(pennant + PackedVector2Array([pennant[0]]), Color("#e2b766"), 2.0, true)
			Paint.draw_medal(self, art.get_center() + Vector2(0, -6), 76.0, emblem, true)
		var x := art.end.x + 22.0
		var width := size.x - x - (96.0 if not level.is_empty() else 28.0)
		# A long name steps down (24 → 21 → 19) before it is trimmed.
		var title_size := 24
		for step in [24, 21, 19]:
			title_size = step
			if UiKit.KitText.line(title, UiKit.LABEL_FONT, step).get_size().x <= width:
				break
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, title_size, width)
		var sub := UiKit.KitText.line(subtitle, UiKit.BODY_FONT, 16, width)
		var y := roundf((size.y - head.get_size().y - sub.get_size().y) * 0.5)
		head.draw_outline(get_canvas_item(), Vector2(x, y), 4, UiKit.SHADE)
		head.draw(get_canvas_item(), Vector2(x, y), UiKit.GOLD)
		y += head.get_size().y
		sub.draw(get_canvas_item(), Vector2(x, y), Color("#e4d3b0"))
		if not level.is_empty():
			# The level on a kokoshnik badge at the right end of the plate.
			var badge := Rect2(size.x - 84.0, roundf(size.y * 0.5 - 30.0), 60, 56)
			draw_texture_rect(UiKit.tex("kit_badge"), badge, false)
			var mark := UiKit.KitText.line(level, UiKit.TITLE_FONT, 20)
			var at := Vector2(roundf(badge.get_center().x - mark.get_size().x * 0.5), roundf(badge.get_center().y - mark.get_size().y * 0.5 + 5.0))
			mark.draw_outline(get_canvas_item(), at, 4, UiKit.SHADE)
			mark.draw(get_canvas_item(), at, UiKit.GOLD)

# ------------------------------------------------------------------ stat band

## A band of figures on carved oak (the army's summary): per cell a small medallion with an
## emblem, a large gold value and a caption, bronze rules between the cells. One node.
class StatBand extends Control:
	## [[Texture2D, value, caption], ...]
	var cells: Array = []

	func _init() -> void:
		custom_minimum_size.y = 84
		size_flags_horizontal = Control.SIZE_EXPAND_FILL
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var box := Rect2(Vector2.ZERO, size)
		draw_style_box(UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO), box)
		if cells.is_empty():
			return
		var width := (size.x - 40.0) / cells.size()
		for index in cells.size():
			var cell: Array = cells[index]
			var left := 20.0 + width * index
			if index > 0:
				draw_rect(Rect2(left, 16.0, 1.0, size.y - 32.0), Color("#c9a05a66"))
			var d := 50.0
			var centre := Vector2(left + 18.0 + d * 0.5, size.y * 0.5)
			Paint.draw_medal(self, centre, d, cell[0])
			var x := centre.x + d * 0.5 + 12.0
			var value := UiKit.KitText.line(str(cell[1]), UiKit.TITLE_FONT, 24, width - (x - left) - 8.0)
			var caption := UiKit.KitText.line(str(cell[2]), UiKit.LABEL_FONT, 15, width - (x - left) - 8.0)
			var y := roundf((size.y - value.get_size().y - caption.get_size().y) * 0.5)
			value.draw_outline(get_canvas_item(), Vector2(x, y), 4, UiKit.SHADE)
			value.draw(get_canvas_item(), Vector2(x, y), UiKit.GOLD)
			caption.draw(get_canvas_item(), Vector2(x, y + value.get_size().y), Color("#e4d3b0"))
