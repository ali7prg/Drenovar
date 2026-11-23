extends Button
## A battle report in the chronicle (premium UI stage 4a, ui_premium/STAGE4A.md), one drawn
## node: the outcome medallion, an enamel badge (Победа / Поражение / Разведка), the
## opponent and its level, when it was, the losses and the spoils with resource icons.

const UiKit = preload("res://src/ui_kit.gd")

var outcome := "victory"
var opponent := ""
var when := ""
var losses := ""
var spoils: Array = []
var unread := false
## [[portrait, count text], ...] of the party (premium UI stage 4b), and the opponent's face
## (a creature's portrait; a settlement shows a crest).
var party: Array = []
var foe: Texture2D
var foe_emblem: Texture2D

func _init() -> void:
	flat = true
	text = ""
	focus_mode = Control.FOCUS_NONE
	custom_minimum_size.y = 96
	size_flags_horizontal = Control.SIZE_EXPAND_FILL

static func badge_of(value: String) -> Array:
	match value:
		"victory":
			return ["Победа", Color("#2e7a32"), "kit_emb_sword"]
		"scout":
			return ["Разведка", Color("#2f6aa8"), "kit_emb_map"]
	return ["Поражение", Color("#a8231d"), "kit_emb_shield"]

func _draw() -> void:
	var mode := get_draw_mode()
	var pressed_now := mode == DRAW_PRESSED or mode == DRAW_HOVER_PRESSED
	var plate := Rect2(Vector2.ZERO, size)
	draw_style_box(UiKit.row_style(), plate)
	if pressed_now:
		draw_rect(plate.grow(-6), Color(0, 0, 0, 0.08))
	var badge := badge_of(outcome)
	var d := 72.0
	var centre := Vector2(16.0 + d * 0.5, size.y * 0.5 + (1.0 if pressed_now else 0.0))
	draw_texture_rect(UiKit.tex("kit_rail_on" if outcome == "victory" else "kit_rail"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false,
		Color.WHITE if outcome != "defeat" else Color(0.82, 0.78, 0.76))
	var side := d * 0.58
	draw_texture_rect(UiKit.tex(badge[2]), Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false)
	if unread:
		draw_circle(centre + Vector2(d * 0.36, -d * 0.36), 7.0, Color("#f2d48b"))
		draw_circle(centre + Vector2(d * 0.36, -d * 0.36), 5.0, Color("#a8231d"))
	var x := 16.0 + d + 16.0
	# The right end: the opponent in a framed tile, the party's portraits before it (wide rows).
	var right := size.x - 18.0
	var wide := size.x > 900.0
	if wide:
		var tile := Rect2(size.x - 16.0 - (size.y - 20.0), 10.0, size.y - 20.0, size.y - 20.0)
		draw_texture_rect(UiKit.tex("kit_ink"), tile.grow(6.0), false, Color(0.42, 0.36, 0.3, 0.55))
		draw_style_box(UiKit.nine("kit_tile", Vector4(14, 14, 14, 14), Vector4.ZERO), tile)
		if foe != null:
			draw_texture_rect(foe, tile.grow(-4.0), false)
		elif foe_emblem != null:
			draw_texture_rect(foe_emblem, Rect2(tile.get_center() - tile.size * 0.3, tile.size * 0.6), false)
		right = tile.position.x - 14.0
		var cell := 54.0
		var px := right - party.size() * (cell + 8.0)
		for entry: Array in party:
			var spot := Rect2(px, 12.0, cell, cell)
			draw_style_box(UiKit.nine("kit_tile", Vector4(14, 14, 14, 14), Vector4.ZERO), spot)
			if entry[0] != null:
				draw_texture_rect(entry[0], spot.grow(-3.0), false)
			var count := UiKit.KitText.line(str(entry[1]), UiKit.LABEL_FONT, 14)
			var tag := Rect2(spot.get_center().x - count.get_size().x * 0.5 - 7.0, spot.end.y - 2.0, count.get_size().x + 14.0, 20.0)
			draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), tag)
			count.draw(get_canvas_item(), Vector2(tag.position.x + 7.0, tag.position.y + roundf((20.0 - count.get_size().y) * 0.5)), UiKit.GOLD)
			px += cell + 8.0
		if not party.is_empty():
			right -= party.size() * (cell + 8.0) + 6.0
	var width := maxf(60.0, right - x)
	var y := 12.0
	# The outcome on an enamel pill, the opponent beside it, the time on the right.
	var word := UiKit.KitText.line(badge[0], UiKit.LABEL_FONT, 15)
	var pill := Rect2(x, y + 1.0, word.get_size().x + 20.0, 24.0)
	var enamel := StyleBoxFlat.new()
	enamel.bg_color = badge[1]
	enamel.border_color = Color("#e7c47a")
	enamel.set_border_width_all(2)
	enamel.set_corner_radius_all(12)
	enamel.anti_aliasing = true
	draw_style_box(enamel, pill)
	word.draw(get_canvas_item(), Vector2(pill.position.x + 10.0, pill.position.y + roundf((pill.size.y - word.get_size().y) * 0.5)), Color.WHITE)
	var time_line := UiKit.KitText.line(when, UiKit.BODY_FONT, 15)
	time_line.draw(get_canvas_item(), Vector2(right - time_line.get_size().x, y + 3.0), UiKit.INK_MUTED)
	var name_line := UiKit.KitText.line(opponent, UiKit.LABEL_FONT, 20, maxf(40.0, width - pill.size.x - time_line.get_size().x - 30.0))
	name_line.draw(get_canvas_item(), Vector2(pill.end.x + 12.0, y), UiKit.INK)
	y += 34.0
	if not losses.is_empty():
		var loss := UiKit.KitText.line(losses, UiKit.BODY_FONT, 15, width)
		loss.draw(get_canvas_item(), Vector2(x, y), UiKit.INK_MUTED)
		y += loss.get_size().y + 4.0
	var cx := x
	for entry: Array in spoils:
		var icon: Texture2D = entry[0]
		if icon != null:
			draw_texture_rect(icon, Rect2(cx, y, 22.0, 22.0), false)
			cx += 25.0
		var value := UiKit.KitText.line(str(entry[1]), UiKit.LABEL_FONT, 15)
		value.draw(get_canvas_item(), Vector2(cx, y + roundf((22.0 - value.get_size().y) * 0.5)), UiKit.GOOD)
		cx += value.get_size().x + 14.0
		if cx > right - 40.0:
			break
