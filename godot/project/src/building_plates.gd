extends Control

# Name plates over the city buildings: the building name with an outline and a
# round level badge under it, and a progress bar with the remaining time over the
# plot under construction. One Control draws them all (no node per building), so
# the cost is a handful of text draws per frame.

const UiKit = preload("res://src/ui_kit.gd")
var game: Node
var font: Font
var pill: StyleBox
var glass: Texture2D
const NAME_SIZE := 15
const BADGE_RADIUS := 11.0
const MAX_ZOOM := 118.0
const OUTLINE := Color("#0e1316")
const BADGE_FILL := Color("#244a72")
const BADGE_RIM := Color("#e6c47c")
const BAR_BACK := Color("#0f1418d0")
const BAR_FILL := Color("#7fc35a")

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	font = get_theme_default_font()
	pill = UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO)
	glass = UiKit.tex("kit_hourglass")

func _process(_delta: float) -> void:
	queue_redraw()

func plates_visible() -> bool:
	if game == null or not is_instance_valid(game.stage) or game.map_name != "city" or game.scene_loading:
		return false
	if game.modal.visible or not game.placing.is_empty():
		return false
	return game.stage.camera_zoom <= MAX_ZOOM

func _draw() -> void:
	if not plates_visible():
		return
	var stage = game.stage
	var camera: Camera3D = stage.camera
	var view := get_viewport_rect().size
	# Fade the plates as the camera pulls back.
	var alpha := clampf((MAX_ZOOM - stage.camera_zoom) / 20.0, 0.0, 1.0)
	var sites: Array = game.shown_sites
	# Running jobs of the V6 buildings (training, research, healing, repairs): a timer plate
	# over the building, like the construction bar (premium UI stage 4a).
	var jobs := {}
	if game.v6_panels.enabled():
		for order: Dictionary in game.state.v6.orders:
			if order.status == "pending" and order.kind != "construction":
				var type := str(order.get("building", ""))
				if not jobs.has(type) or float(order.starts_at) < float(jobs[type].starts_at):
					jobs[type] = order
	for marker in stage.place_markers:
		if not marker.get("kind", "") in ["building", "wall"]:
			continue
		var anchor: Vector3 = marker.position + Vector3.UP * 3.5
		if camera.is_position_behind(anchor):
			continue
		var at := camera.unproject_position(anchor)
		if at.x < -80 or at.y < -40 or at.x > view.x + 80 or at.y > view.y + 40:
			continue
		var building: Dictionary = marker.item
		var title: String = "Стены" if marker.kind == "wall" else game.building_title(building.type).get_slice("/", 0)
		draw_name(at, title, alpha)
		draw_badge(at + Vector2(0, 17), int(building.get("level", 1)), alpha)
		var shown := false
		for site in sites:
			if site.get("key", "") == str(building.get("id", "_")):
				draw_progress(at + Vector2(0, 38), site, alpha)
				shown = true
		var job: Variant = jobs.get(str(building.get("conceptType", building.get("type", ""))))
		if not shown and job != null:
			draw_progress(at + Vector2(0, 38), {"started": float(job.starts_at) * 1000.0, "ends": float(job.ends_at) * 1000.0, "key": str(job.id)}, alpha)
	# Trees being felled (one per busy worker): progress bar over each.
	for job in game.shown_jobs:
		var tree: Dictionary = stage.works.tree_by_id(job.tree)
		if not tree.is_empty():
			var at := camera.unproject_position(stage.array_point(tree.p) + Vector3.UP * 7.5)
			if camera.is_position_behind(stage.array_point(tree.p)):
				continue
			draw_name(at, "Рубка", alpha)
			draw_progress(at + Vector2(0, 8), job, alpha)
	# Plots of new buildings under construction (no building yet).
	for site in sites:
		if not site.get("kind", "") in ["build", "place"]:
			continue
		for plot in stage.empty_plots:
			if str(plot.item.id) == str(site.get("plot", "")) or str(plot.item.id) == str(site.key):
				var at := camera.unproject_position(plot.position + Vector3.UP * 7.0)
				draw_name(at, game.building_title(site.get("type", "")).get_slice("/", 0), alpha)
				draw_progress(at + Vector2(0, 14), site, alpha)

func draw_name(at: Vector2, title: String, alpha: float) -> void:
	var width := font.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_SIZE).x
	var base := at + Vector2(-width * 0.5, 0)
	draw_string_outline(font, base, title, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_SIZE, 5, Color(OUTLINE, 0.85 * alpha))
	draw_string(font, base, title, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_SIZE, Color(1, 0.97, 0.9, alpha))

func draw_badge(center: Vector2, level: int, alpha: float) -> void:
	draw_circle(center + Vector2(0, 1.5), BADGE_RADIUS + 1.5, Color(0, 0, 0, 0.35 * alpha), true, -1.0, true)
	draw_circle(center, BADGE_RADIUS + 1.5, Color(BADGE_RIM, alpha), true, -1.0, true)
	draw_circle(center, BADGE_RADIUS, Color(BADGE_FILL, alpha), true, -1.0, true)
	draw_arc(center, BADGE_RADIUS - 2.5, PI * 1.1, PI * 1.9, 12, Color(1, 1, 1, 0.22 * alpha), 1.5, true)
	var text := str(level)
	var size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 13)
	draw_string(font, center + Vector2(-size.x * 0.5, 4.6), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 1, alpha))

# Bar of a work: {started, ends, confirmed, predicted, key|id}. A work just ordered
# counts down at once with its known duration (predicted); the server's order takes
# over when it answers. After zero the server is asked, and without a link nothing is
# shown as done. The bar never moves backward for the same work (clock corrections),
# and moves forward at once after a speedup.
var bar_floor := {}

func draw_progress(at: Vector2, work: Dictionary, alpha: float) -> void:
	if alpha < 0.4:
		return
	var now: float = game.timer_now()
	# The bar includes the network round trip, so it fills when the answer arrives.
	var starts := float(work.get("started", float(work.get("ends", 0.0)) - 60000.0))
	var ends: float = game.display_end(float(work.get("ends", 0.0)))
	var confirmed: bool = work.get("confirmed", true) or work.get("predicted", false)
	var key := str(work.get("key", work.get("id", work.get("tree", ""))))
	var fraction := 0.0
	if confirmed:
		fraction = clampf((now - starts) / maxf(ends - starts, 1.0), 0.0, 1.0)
		fraction = maxf(fraction, float(bar_floor.get(key, 0.0)))
		if bar_floor.size() > 32:
			bar_floor.clear()
		bar_floor[key] = fraction
	var label := "Отправляем…"
	if confirmed:
		label = game.clock_text(ceili((ends - now) / 1000.0)) if now < ends else game.timer_end_label()
	# An oak pill in a bronze rim: the hourglass, the time in gold, a gold line filling along
	# its foot.
	var line := UiKit.KitText.line(label, UiKit.LABEL_FONT, 14)
	var width := maxf(96.0, line.get_size().x + 46.0)
	var rect := Rect2(at + Vector2(-width * 0.5, -2.0), Vector2(width, 25.0))
	draw_style_box(pill, rect)
	draw_rect(Rect2(rect.position + Vector2(10, rect.size.y - 6.0), Vector2((rect.size.x - 20.0) * fraction, 2.5)), Color(0.93, 0.72, 0.31, alpha))
	draw_texture_rect(glass, Rect2(rect.position + Vector2(9, 5), Vector2(12, 14)), false, Color(1, 1, 1, alpha))
	line.draw(get_canvas_item(), Vector2(rect.position.x + 27.0, rect.position.y + roundf((rect.size.y - 3.0 - line.get_size().y) * 0.5)), Color(UiKit.GOLD, alpha))
