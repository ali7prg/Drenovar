extends Control
## «Лес потерянных» loading indicator (1023): a small carved oak plate at the bottom left, where the
## adventure row appears, with the forest's medallion, «Лес потерянных», «готовим лес · NN %» and a
## thin gold line. It shows only when the load has taken longer than SHOW_AFTER_MSEC, never covers the
## city's controls (mouse ignored) and fades out once the forest is ready. main.gd feeds `ratio`.

const UiKit = preload("res://src/ui_kit.gd")
const SHOW_AFTER_MSEC := 1200
const FADE_SECONDS := 0.25
const PLATE_SIZE := Vector2(292, 50)

var ratio := 0.0
var shown_ratio := 0.0
var active := false
var started_msec := -1
var reduced_motion := false
var plate: StyleBoxTexture
var title_line := TextLine.new()
var note_line := TextLine.new()
var note_text := ""
var safe_left := 0.0

func _init() -> void:
	name = "ForestProgress"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	modulate.a = 0.0
	visible = false
	size = PLATE_SIZE
	title_line.add_string("Лес потерянных", UiKit.LABEL_FONT, 16)

## Called every frame by main.gd while the forest loads (loading = false once it is ready).
func update(loading: bool, value: float, delta: float) -> void:
	if loading and started_msec < 0:
		started_msec = Time.get_ticks_msec()
	active = loading and Time.get_ticks_msec() - started_msec >= SHOW_AFTER_MSEC
	ratio = clampf(maxf(ratio, value), 0.0, 1.0)
	# The line eases towards the measured share (never back), so steps between stages read as a flow.
	shown_ratio = minf(ratio, shown_ratio + maxf(ratio - shown_ratio, 0.02) * minf(1.0, delta * 6.0))
	var target := 1.0 if active else 0.0
	if reduced_motion:
		modulate.a = target
	else:
		modulate.a = move_toward(modulate.a, target, delta / FADE_SECONDS)
	visible = modulate.a > 0.01
	if not loading and not visible:
		started_msec = -1
	var text := "готовим лес · %d %%" % int(round(shown_ratio * 100.0))
	if text != note_text:
		note_text = text
		note_line.clear()
		note_line.add_string(text, UiKit.BODY_FONT, 13)
	if visible:
		queue_redraw()

func _draw() -> void:
	if plate == null:
		plate = UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(0, 0, 0, 0)).duplicate() as StyleBoxTexture
	var rect := Rect2(Vector2.ZERO, PLATE_SIZE)
	draw_style_box(plate, rect)
	# The forest's medallion: gold rim, deep green face, the forged tree emblem.
	var centre := Vector2(30, PLATE_SIZE.y * 0.5)
	draw_circle(centre + Vector2(0, 1.5), 17.5, Color(0, 0, 0, 0.3), true, -1.0, true)
	draw_circle(centre, 17.0, Color("#e2b766"), true, -1.0, true)
	draw_circle(centre, 15.0, Color("#244a2c"), true, -1.0, true)
	var emblem := UiKit.tex("kit_emb_tree")
	if emblem != null:
		draw_texture_rect(emblem, Rect2(centre - Vector2(11, 11), Vector2(22, 22)), false)
	var x := 56.0
	title_line.draw(get_canvas_item(), Vector2(x, 7), UiKit.GOLD)
	note_line.draw(get_canvas_item(), Vector2(x, 26), Color(UiKit.IVORY, 0.86))
	# The thin line: a dark groove and the gold share.
	var track := Rect2(Vector2(x + 128, 31), Vector2(PLATE_SIZE.x - x - 128 - 22, 4))
	draw_rect(track, Color(0, 0, 0, 0.45), true)
	draw_rect(Rect2(track.position, Vector2(track.size.x * shown_ratio, track.size.y)), UiKit.GOLD, true)
	draw_rect(Rect2(track.position, Vector2(track.size.x * shown_ratio, 1)), Color(1, 0.95, 0.8, 0.6), true)
