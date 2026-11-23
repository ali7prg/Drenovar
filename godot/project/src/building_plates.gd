extends Control

# Name plates over the city buildings: the building name with an outline and a
# round level badge under it, and a progress bar with the remaining time over the
# plot under construction. One Control draws them all (no node per building), so
# the cost is a handful of text draws per frame.
#
# Stage 4a (ui_premium/STAGE4A.md): the names and levels are cached shaped lines, the
# level badge is one texture painted once (it was four antialiased shapes per building
# per frame), so the timer pills over every busy building cost no more than before.

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

var titles := {}
var badge_texture: Texture2D
var badge_task := -1
const BADGE_SCALE := 2.0
const BADGE_HALF := 15.0

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	font = get_theme_default_font()
	pill = UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO)
	glass = UiKit.tex("kit_hourglass")
	# Painted on a worker thread after launch; the shapes stand in until it is ready.
	badge_task = WorkerThreadPool.add_task(func(): adopt_badge.call_deferred(paint_badge()))

## On the main thread: the texture is made here, only the pixels on the worker.
func adopt_badge(image: Image) -> void:
	finish_badge_task()
	badge_texture = ImageTexture.create_from_image(image)

## Every pool task is waited for once, or the pool keeps it (and its callable) until exit.
func finish_badge_task() -> void:
	if badge_task >= 0:
		WorkerThreadPool.wait_for_task_completion(badge_task)
		badge_task = -1

func _exit_tree() -> void:
	finish_badge_task()

## The level badge painted once at twice its size: a soft shadow, the gold rim, the blue
## enamel and a faint highlight arc, each edge antialiased by its pixel coverage.
static func paint_badge() -> Image:
	var side := int(BADGE_HALF * 2.0 * BADGE_SCALE)
	var image := Image.create(side, side, false, Image.FORMAT_RGBA8)
	var centre := Vector2(BADGE_HALF, BADGE_HALF)
	for py in side:
		for px in side:
			var p := (Vector2(px, py) + Vector2(0.5, 0.5)) / BADGE_SCALE
			var colour := Color(0, 0, 0, 0)
			var shadow := clampf(BADGE_RADIUS + 2.0 - p.distance_to(centre + Vector2(0, 1.5)), 0.0, 1.0) * 0.35
			colour = colour.blend(Color(0, 0, 0, shadow))
			var d := p.distance_to(centre)
			colour = colour.blend(Color(BADGE_RIM, clampf(BADGE_RADIUS + 1.5 - d + 0.5, 0.0, 1.0)))
			colour = colour.blend(Color(BADGE_FILL, clampf(BADGE_RADIUS - d + 0.5, 0.0, 1.0)))
			var angle := fposmod(atan2(p.y - centre.y, p.x - centre.x), TAU)
			if angle > PI * 1.1 and angle < PI * 1.9:
				colour = colour.blend(Color(1, 1, 1, 0.22 * clampf(1.0 - absf(d - (BADGE_RADIUS - 2.5)) / 0.9, 0.0, 1.0)))
			image.set_pixel(px, py, colour)
	return image

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
	var ring_subject: String = game.action_ring.subject_id if is_instance_valid(game.action_ring) and game.action_ring.is_open() else ""
	# Plates keep clear of the HUD: no name or badge peeks between the medallions or under
	# the resource row.
	var avoid: Array[Rect2] = []
	for control: Control in game.nav_buttons.values() + game.resource_buttons.values() + [game.profile_button]:
		if is_instance_valid(control) and control.is_visible_in_tree():
			avoid.append(control.get_global_rect().grow(10.0))
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
		var hidden := false
		for rect in avoid:
			if rect.has_point(at) or rect.has_point(at + Vector2(0, 17)):
				hidden = true
				break
		if hidden:
			continue
		var building: Dictionary = marker.item
		if ring_subject != "" and str(building.get("id", "")) == ring_subject:
			# The open ring carries this building's name and level on its own plate.
			continue
		var title: String = "Стены" if marker.kind == "wall" else titles.get(building.type, "")
		if title.is_empty():
			title = game.building_title(building.type).get_slice("/", 0)
			titles[building.type] = title
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
	# `at` is the baseline, as for draw_string; the cached line draws from its top.
	var line := UiKit.KitText.line(title, font, NAME_SIZE)
	var top := at + Vector2(-line.get_size().x * 0.5, -line.get_line_ascent())
	line.draw_outline(get_canvas_item(), top, 5, Color(OUTLINE, 0.85 * alpha))
	line.draw(get_canvas_item(), top, Color(1, 0.97, 0.9, alpha))

func draw_badge(center: Vector2, level: int, alpha: float) -> void:
	if badge_texture != null:
		draw_texture_rect(badge_texture, Rect2(center - Vector2(BADGE_HALF, BADGE_HALF), Vector2(BADGE_HALF, BADGE_HALF) * 2.0), false, Color(1, 1, 1, alpha))
	else:
		draw_circle(center + Vector2(0, 1.5), BADGE_RADIUS + 1.5, Color(0, 0, 0, 0.35 * alpha), true, -1.0, true)
		draw_circle(center, BADGE_RADIUS + 1.5, Color(BADGE_RIM, alpha), true, -1.0, true)
		draw_circle(center, BADGE_RADIUS, Color(BADGE_FILL, alpha), true, -1.0, true)
	var line := UiKit.KitText.line(str(level), font, 13)
	line.draw(get_canvas_item(), center + Vector2(-line.get_size().x * 0.5, 4.6 - line.get_line_ascent()), Color(1, 1, 1, alpha))

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
