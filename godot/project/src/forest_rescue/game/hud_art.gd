extends Control
## Procedural emblems for the adventure HUD (art/07 bottom row, art/18 cards):
## banner with the tree sigil, treasure chest, map pin, squad, double chevron, medallion.
## Drawn as vectors so they stay crisp on every iPhone scale; no text is drawn here.

const GOLD := Color("#e9c77f")
const GOLD_DARK := Color("#9c7337")
const RED := Color("#8e2419")
const RED_DARK := Color("#5c140e")
const IVORY := Color("#f6ead0")
const INK := Color("#2e2014")

@export var kind := "banner"
@export var tint := Color.WHITE
var active := false

func _init(icon_kind := "banner", size_hint := Vector2(48, 48)) -> void:
	kind = icon_kind
	custom_minimum_size = size_hint
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _draw() -> void:
	var r := Rect2(Vector2.ZERO, size)
	match kind:
		"banner": draw_banner(self, r)
		"chest": draw_chest(self, r)
		"pin": draw_pin(self, r, tint)
		"squad": draw_squad(self, r, tint)
		"chevrons": draw_chevrons(self, r, tint)
		"medallion": draw_medallion(self, r)
		"tree": draw_tree(self, r.get_center(), minf(r.size.x, r.size.y) * 0.9, GOLD)
		"ornament": draw_ornament(self, r)
		"horse": draw_horse(self, r, tint)

static func draw_tree(ci: CanvasItem, c: Vector2, s: float, color: Color) -> void:
	var w := maxf(1.2, s * 0.055)
	var trunk_top := c + Vector2(0, -s * 0.05)
	var base := c + Vector2(0, s * 0.36)
	ci.draw_line(base, trunk_top, color, w * 1.6, true)
	for side in [-1.0, 1.0]:
		ci.draw_line(base, base + Vector2(side * s * 0.16, s * 0.08), color, w, true)
		ci.draw_line(base + Vector2(0, -s * 0.02), base + Vector2(side * s * 0.08, s * 0.1), color, w * 0.8, true)
		var a := trunk_top + Vector2(0, s * 0.12)
		var b := a + Vector2(side * s * 0.2, -s * 0.16)
		var tip := b + Vector2(side * s * 0.1, -s * 0.12)
		ci.draw_polyline(PackedVector2Array([a, b, tip]), color, w, true)
		ci.draw_polyline(PackedVector2Array([trunk_top, trunk_top + Vector2(side * s * 0.1, -s * 0.18), trunk_top + Vector2(side * s * 0.06, -s * 0.3)]), color, w * 0.85, true)
	ci.draw_line(trunk_top, trunk_top + Vector2(0, -s * 0.3), color, w, true)
	var crown := c + Vector2(0, -s * 0.2)
	for i in 11:
		var angle := -PI + PI * float(i) / 10.0
		var p := crown + Vector2(cos(angle) * s * 0.33, sin(angle) * s * 0.24)
		ci.draw_circle(p, s * 0.045, color)

static func draw_banner(ci: CanvasItem, r: Rect2) -> void:
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center()
	var w := s * 0.66
	var h := s * 0.92
	var top := c.y - h * 0.5
	var left := c.x - w * 0.5
	var shape := PackedVector2Array([Vector2(left, top), Vector2(left + w, top), Vector2(left + w, top + h),
		Vector2(c.x, top + h * 0.82), Vector2(left, top + h)])
	ci.draw_colored_polygon(shape, RED)
	var inner := PackedVector2Array()
	for p in shape:
		inner.append(c + (p - c) * 0.86)
	inner.append(inner[0])
	ci.draw_polyline(inner, GOLD_DARK, maxf(1.0, s * 0.025), true)
	var outline := shape.duplicate()
	outline.append(shape[0])
	ci.draw_polyline(outline, RED_DARK, maxf(1.0, s * 0.03), true)
	ci.draw_line(Vector2(left - s * 0.06, top), Vector2(left + w + s * 0.06, top), GOLD_DARK, maxf(2.0, s * 0.06), true)
	draw_tree(ci, c + Vector2(0, -h * 0.04), s * 0.5, GOLD)

static func draw_chest(ci: CanvasItem, r: Rect2) -> void:
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center() + Vector2(0, s * 0.06)
	var w := s * 0.9
	var body := Rect2(c.x - w * 0.5, c.y - s * 0.08, w, s * 0.38)
	var wood := Color("#7a4a24")
	var wood_dark := Color("#4a2b14")
	var brass := Color("#d3a659")
	var lid := PackedVector2Array()
	for i in 13:
		var t := float(i) / 12.0
		lid.append(Vector2(body.position.x + w * t, body.position.y - sin(t * PI) * s * 0.22))
	lid.append(Vector2(body.end.x, body.position.y + s * 0.02))
	lid.append(Vector2(body.position.x, body.position.y + s * 0.02))
	ci.draw_colored_polygon(lid, Color("#8b5a2d"))
	ci.draw_rect(body, wood)
	for i in 3:
		var y := body.position.y + body.size.y * (0.3 + 0.32 * i)
		ci.draw_line(Vector2(body.position.x, y), Vector2(body.end.x, y), wood_dark, maxf(1.0, s * 0.02))
	for x in [body.position.x + w * 0.12, body.end.x - w * 0.12]:
		ci.draw_line(Vector2(x, body.position.y - s * 0.17), Vector2(x, body.end.y), brass, maxf(2.0, s * 0.07))
	ci.draw_rect(body, wood_dark, false, maxf(1.0, s * 0.03))
	var lid_outline := lid.duplicate()
	lid_outline.append(lid[0])
	ci.draw_polyline(lid_outline, wood_dark, maxf(1.0, s * 0.03), true)
	ci.draw_rect(Rect2(c.x - s * 0.08, body.position.y - s * 0.03, s * 0.16, s * 0.18), brass)
	ci.draw_circle(Vector2(c.x, body.position.y + s * 0.07), s * 0.025, wood_dark)
	ci.draw_arc(Vector2(c.x, body.position.y - s * 0.1), s * 0.5, PI * 1.15, PI * 1.85, 16, Color(1, 0.86, 0.5, 0.35), s * 0.05, true)

static func draw_pin(ci: CanvasItem, r: Rect2, tint: Color) -> void:
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center() + Vector2(0, -s * 0.08)
	var color := IVORY * tint
	var head := c + Vector2(0, -s * 0.12)
	var radius := s * 0.22
	var points := PackedVector2Array()
	for i in 25:
		var a := PI * 0.82 + (PI * 2.0 - PI * 0.64) * float(i) / 24.0 - PI * 0.5
		points.append(head + Vector2(cos(a), sin(a)) * radius)
	points.append(c + Vector2(0, s * 0.3))
	ci.draw_colored_polygon(points, color)
	ci.draw_circle(head, radius * 0.42, Color("#5b3c22"))
	ci.draw_arc(c + Vector2(0, s * 0.32), s * 0.22, PI * 0.15, PI * 0.85, 12, Color(color, 0.7), maxf(1.0, s * 0.05), true)

static func draw_squad(ci: CanvasItem, r: Rect2, tint: Color) -> void:
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center()
	var color := IVORY * tint
	for offset in [Vector2(-s * 0.26, s * 0.03), Vector2(s * 0.26, s * 0.03), Vector2(0, 0)]:
		var big: bool = offset == Vector2.ZERO
		var k: float = 1.0 if big else 0.8
		var head: Vector2 = c + offset + Vector2(0, -s * 0.16 * k)
		var shoulders := PackedVector2Array()
		for i in 13:
			var a := PI + PI * float(i) / 12.0
			shoulders.append(c + offset + Vector2(cos(a) * s * 0.2 * k, s * 0.22 + sin(a) * s * 0.2 * k))
		var fill := color if big else color.darkened(0.15)
		ci.draw_colored_polygon(shoulders, fill)
		ci.draw_circle(head, s * 0.12 * k, fill)
		if big:
			ci.draw_arc(head, s * 0.12 * k + 1.5, 0, TAU, 20, Color("#5b3c22"), 2.0, true)

static func draw_chevrons(ci: CanvasItem, r: Rect2, tint: Color) -> void:
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center()
	var color := IVORY * tint
	for dx in [-s * 0.18, s * 0.14]:
		var tip := c + Vector2(dx + s * 0.16, 0)
		var shape := PackedVector2Array([tip + Vector2(-s * 0.3, -s * 0.3), tip + Vector2(-s * 0.18, -s * 0.3),
			tip, tip + Vector2(-s * 0.18, s * 0.3), tip + Vector2(-s * 0.3, s * 0.3), tip + Vector2(-s * 0.12, 0)])
		ci.draw_colored_polygon(shape, color)

static func draw_medallion(ci: CanvasItem, r: Rect2) -> void:
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center()
	for side in [-1.0, 1.0]:
		for i in 4:
			var t := float(i) / 3.0
			var base := c + Vector2(side * s * (0.42 + t * 0.42), s * (0.12 - t * 0.12))
			var leaf := PackedVector2Array([base, base + Vector2(side * s * 0.1, -s * 0.09), base + Vector2(side * s * 0.2, 0), base + Vector2(side * s * 0.1, s * 0.05)])
			ci.draw_colored_polygon(leaf, GOLD_DARK.lerp(GOLD, 0.5 + t * 0.4))
	ci.draw_circle(c, s * 0.42, Color("#2b2418"))
	ci.draw_arc(c, s * 0.42, 0, TAU, 48, GOLD, maxf(1.5, s * 0.06), true)
	ci.draw_arc(c, s * 0.34, 0, TAU, 48, GOLD_DARK, maxf(1.0, s * 0.02), true)
	draw_tree(ci, c + Vector2(0, s * 0.02), s * 0.55, GOLD)

static func draw_ornament(ci: CanvasItem, r: Rect2) -> void:
	var c := r.get_center()
	var half := r.size.x * 0.5
	ci.draw_line(c - Vector2(half, 0), c - Vector2(8, 0), Color(GOLD, 0.55), 1.2, true)
	ci.draw_line(c + Vector2(8, 0), c + Vector2(half, 0), Color(GOLD, 0.55), 1.2, true)
	var diamond := PackedVector2Array([c + Vector2(0, -5), c + Vector2(6, 0), c + Vector2(0, 5), c + Vector2(-6, 0)])
	ci.draw_colored_polygon(diamond, GOLD)

static func draw_horse(ci: CanvasItem, r: Rect2, tint: Color) -> void:
	# Small side silhouette of the riderless bay mare (used on static reduced-motion cards).
	var s := minf(r.size.x, r.size.y)
	var c := r.get_center()
	var body := Color("#8a4f2a") * tint
	var dark := Color("#2c1a10") * tint
	var u := s / 10.0
	var torso := PackedVector2Array()
	for i in 21:
		var a := TAU * float(i) / 20.0
		torso.append(c + Vector2(cos(a) * 2.9 * u, sin(a) * 1.25 * u))
	ci.draw_colored_polygon(torso, body)
	var neck := PackedVector2Array([c + Vector2(2.0 * u, -0.6 * u), c + Vector2(3.4 * u, -3.0 * u), c + Vector2(4.4 * u, -2.6 * u), c + Vector2(3.1 * u, 0.2 * u)])
	ci.draw_colored_polygon(neck, body)
	var head := PackedVector2Array([c + Vector2(3.3 * u, -3.2 * u), c + Vector2(4.5 * u, -3.1 * u), c + Vector2(5.4 * u, -1.7 * u), c + Vector2(4.9 * u, -1.4 * u), c + Vector2(4.0 * u, -2.2 * u)])
	ci.draw_colored_polygon(head, body)
	ci.draw_circle(c + Vector2(4.25 * u, -2.75 * u), 0.18 * u, Color.WHITE)
	ci.draw_polyline(PackedVector2Array([c + Vector2(3.3 * u, -3.1 * u), c + Vector2(2.4 * u, -1.7 * u), c + Vector2(1.9 * u, -0.7 * u)]), dark, 0.45 * u, true)
	ci.draw_polyline(PackedVector2Array([c + Vector2(-2.8 * u, -0.4 * u), c + Vector2(-3.6 * u, 0.6 * u), c + Vector2(-3.7 * u, 2.2 * u)]), dark, 0.5 * u, true)
	for x in [-2.1, -1.4, 1.4, 2.1]:
		ci.draw_line(c + Vector2(x * u, 0.8 * u), c + Vector2(x * u, 3.6 * u), body.darkened(0.1), 0.45 * u, true)
		ci.draw_line(c + Vector2(x * u, 3.3 * u), c + Vector2(x * u, 3.7 * u), dark, 0.5 * u, true)
	ci.draw_line(c + Vector2(4.6 * u, -2.0 * u), c + Vector2(4.2 * u, -0.6 * u), Color("#3f8f4a"), 0.3 * u, true)
