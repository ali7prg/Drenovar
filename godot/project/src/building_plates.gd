extends Control

# Name plates over the city buildings: the building name with an outline and a
# round level badge under it, and a progress bar with the remaining time over the
# plot under construction. One Control draws them all (no node per building), so
# the cost is a handful of text draws per frame.

var game: Node
var font: Font
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
	var order: Dictionary = game.construction_order()
	for marker in stage.place_markers:
		if marker.get("kind", "") != "building":
			continue
		var anchor: Vector3 = marker.position + Vector3.UP * 3.5
		if camera.is_position_behind(anchor):
			continue
		var at := camera.unproject_position(anchor)
		if at.x < -80 or at.y < -40 or at.x > view.x + 80 or at.y > view.y + 40:
			continue
		var building: Dictionary = marker.item
		var title: String = game.building_title(building.type).get_slice("/", 0)
		draw_name(at, title, alpha)
		draw_badge(at + Vector2(0, 17), int(building.get("level", 1)), alpha)
		if order.get("buildingId", "") == building.get("id", "_") and order.has("endsAt"):
			draw_progress(at + Vector2(0, 38), order, alpha)
	# Tree being felled: progress bar over it.
	var job: Dictionary = game.shown_job
	if not job.is_empty():
		var tree: Dictionary = stage.works.tree_by_id(job.tree)
		if not tree.is_empty():
			var at := camera.unproject_position(stage.array_point(tree.p) + Vector3.UP * 7.5)
			draw_name(at, "Рубка", alpha)
			draw_progress(at + Vector2(0, 8), {"startedAt": job.started, "endsAt": job.ends}, alpha)
	# Plot of a new building under construction (no building yet).
	if order.get("kind", "") == "build" and order.has("plotId"):
		for plot in stage.empty_plots:
			if plot.item.id == order.plotId:
				var at := camera.unproject_position(plot.position + Vector3.UP * 7.0)
				draw_name(at, game.building_title(order.get("type", "")).get_slice("/", 0), alpha)
				draw_progress(at + Vector2(0, 14), order, alpha)

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

func draw_progress(at: Vector2, order: Dictionary, alpha: float) -> void:
	var now: float = game.server_time()
	var ends := float(order.endsAt)
	var starts := float(order.get("startedAt", ends - 1000.0 * float(order.get("seconds", 60))))
	var fraction := clampf((now - starts) / maxf(ends - starts, 1.0), 0.0, 1.0)
	var rect := Rect2(at + Vector2(-48, 0), Vector2(96, 9))
	draw_rect(rect.grow(1.5), Color(BAR_BACK, 0.9 * alpha))
	draw_rect(Rect2(rect.position, Vector2(rect.size.x * fraction, rect.size.y)), Color(BAR_FILL, alpha))
	var left := maxi(0, ceili((ends - now) / 1000.0))
	# At zero the server finishes the work; say so instead of a frozen 0:00.
	var label := "%d:%02d" % [left / 60, left % 60] if now < ends else "Завершаем…"
	var size := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13)
	var base := at + Vector2(-size.x * 0.5, 24)
	draw_string_outline(font, base, label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, 4, Color(OUTLINE, alpha))
	draw_string(font, base, label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 0.93, 0.78, alpha))
