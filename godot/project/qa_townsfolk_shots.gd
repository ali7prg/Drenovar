extends "res://qa_townsfolk.gd"

# Rendered frames of the townsfolk (build 1024): the town at hall V (qa_townsfolk.gd's town),
# offline, views of the town hall square, the warehouse and the lumber camp at the default city
# zoom and closer, 10 s each (the square close up at 12 fps, the others one frame per 0.33 s;
# JPG, q 85); an LOD comparison and a shadow comparison.
# The townsfolk run on a virtual clock that advances 1/12 s per frame; with --fixed-fps 12 the
# animation advances by the same step, so walking and the feet stay in step.
#   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
#     godot --path . --rendering-driver vulkan --rendering-method mobile --fixed-fps 12 \
#     -s qa_townsfolk_shots.gd -- --shots=/abs/dir [--hall=5] [--seconds=10] [--only=hall,lod]
# Contact sheets and the video: godot/tools/townsfolk_sheets.py.

const FPS := 12
## Townsfolk.K_DWELL: a person standing at a stop.
const STANDING := 1
var out_dir := ""
var hall_level := 5
var seconds := 10.0
var only: PackedStringArray = []
var clock := 1794371000.0

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			out_dir = arg.trim_prefix("--shots=")
		elif arg.begins_with("--hall="):
			hall_level = int(arg.trim_prefix("--hall="))
		elif arg.begins_with("--seconds="):
			seconds = float(arg.trim_prefix("--seconds="))
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",")
	call_deferred("run")

func wanted(name: String) -> bool:
	return only.is_empty() or name in only

## One frame of the town: the clock steps, the parade and the people are posed.
func step() -> void:
	clock += 1.0 / FPS
	stage.present_parade()
	tf.present(clock)
	await process_frame

func look(target: Vector3, zoom: float) -> void:
	stage.target = target
	stage.zoom = zoom
	stage.update_camera(0, true)
	stage.update_visible_batches()
	for i in 8:
		await step()

func save(path: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_jpg(path, 0.85)

## `every`: frames per capture (1: 12 fps video; 4: one capture per 0.33 s for the sheets).
func sequence(name: String, target: Vector3, zoom: float, every := 1) -> void:
	if not wanted(name):
		return
	await look(target, zoom)
	var dir := out_dir.path_join(name)
	DirAccess.make_dir_recursive_absolute(dir)
	var frames := int(seconds * FPS / every)
	for f in frames:
		# Engine and clock both step `every` frames between captures (no render in between
		# for the 0.33 s sequences: the people's clock and animation move by the same time).
		for k in every - 1:
			clock += 1.0 / FPS
			tf.present(clock)
			# (Zoomed out the townsfolk advance their AnimationPlayers themselves.)
			if not tf.anim_manual:
				for p in tf.people:
					if p.shown and p.rig.player != null:
						p.rig.player.advance(1.0 / FPS)
		await step()
		await save(dir.path_join("f%04d.jpg" % f))
	var shown: int = tf.people.filter(func(p): return p.shown).size()
	print("SEQUENCE %s: %d frames, %d of %d people on screen, zoom %.0f" % [name, frames, shown, tf.people.size(), zoom])

func marker_of(type: String) -> Vector3:
	for marker: Dictionary in stage.place_markers:
		if marker.get("kind", "") == "building" and str(marker.item.get("type", "")) == type:
			return marker.position - Vector3.UP * 5.0
	return Vector3.ZERO

## The clock set so that the first pair of neighbours meeting within `reach` m of `near` walk up
## to each other `lead` s after it; where they meet (Vector3.INF: nobody meets there).
func meet_clock(near: Vector3, reach := 16.0, lead := 3.5) -> Vector3:
	for p in tf.people:
		if p.meet_phase < 0 or p.spot_a[p.meet_phase].distance_to(Vector2(near.x, near.z)) > reach:
			continue
		var u: float = p.starts[p.meet_phase] - lead
		clock += fposmod(u - p.phase + p.delay - clock, p.cycle)
		tf.present(clock)
		print("meeting: %s at %s, clock %.1f" % [p.key, str(p.spot_a[p.meet_phase]), clock])
		var at: Vector2 = p.spot_a[p.meet_phase]
		return Vector3(at.x, tf.ground_y(at.x, at.y), at.y)
	return Vector3.INF

## Townsfolk at 1.0 and 1.12 of their size next to doors, the same frame, close up.
func scale_comparison(target: Vector3) -> void:
	if not wanted("scale"):
		return
	var dir := out_dir.path_join("scale")
	DirAccess.make_dir_recursive_absolute(dir)
	# In the middle of a meeting there (two people standing by the door).
	var meet := meet_clock(target, 16.0, -1.5)
	await look(meet + Vector3(0, 0, 1.5) if meet != Vector3.INF else target, 24.0)
	for factor in [1.0, 1.12]:
		for p in tf.people:
			if p.rig != null and p.rig.model != null:
				p.rig.model.scale = Vector3.ONE * p.scale * factor
		for i in 3:
			await process_frame
		await save(dir.path_join("scale_%s.jpg" % ("100" if factor == 1.0 else "112")))
	# ... and someone standing at a house's door (the clock set 1 s into their stop there), at
	# zoom 20 and 34.
	var door := door_clock()
	if door != Vector3.INF:
		for zoom: float in [20.0, 34.0]:
			await look(door + Vector3(0, 0, 1.0), zoom)
			for factor in [1.0, 1.12]:
				for p in tf.people:
					if p.rig != null and p.rig.model != null:
						p.rig.model.scale = Vector3.ONE * p.scale * factor
				for i in 3:
					await process_frame
				await save(dir.path_join("door_z%d_%s.jpg" % [int(zoom), "100" if factor == 1.0 else "112"]))
			clock -= 8.0 / FPS
			tf.present(clock)
	for p in tf.people:
		if p.rig != null and p.rig.model != null:
			p.rig.model.scale = Vector3.ONE * p.scale
	print("scale comparison saved")

## The clock set to 1 s into someone's stop at a house's (or the well's, a store's) door; where.
func door_clock() -> Vector3:
	for groups: Array in [Townsfolk.HOUSE, Townsfolk.WELL, Townsfolk.STORE]:
		for p in tf.people:
			for i in p.kinds.size():
				if p.kinds[i] != STANDING or p.lengths[i] < 3.0:
					continue
				for li in tf.door_stop:
					if tf.lot_base[li] in groups and p.spot_a[i].distance_to(tf.door_stop[li]) < 1.5:
						clock += fposmod(p.starts[i] + 1.0 - 8.0 / FPS - p.phase + p.delay - clock, p.cycle)
						tf.present(clock)
						print("at a door: %s at %s (%s), clock %.1f" % [p.key, str(p.spot_a[i]), tf.lot_base[li], clock])
						var at: Vector2 = p.spot_a[i]
						return Vector3(at.x, tf.ground_y(at.x, at.y), at.y)
	return Vector3.INF

## The same person at each LOD, at the closest and the default zoom.
func lod_comparison() -> void:
	if not wanted("lod"):
		return
	var dir := out_dir.path_join("lod")
	DirAccess.make_dir_recursive_absolute(dir)
	var person = null
	for p in tf.people:
		if p.shown and p.kinds[p.index] == STANDING:
			person = p
			break
	if person == null:
		person = tf.people[0]
	for zoom in [24.0, 40.0, 70.0]:
		for level in 3:
			stage.target = Vector3(person.pos.x, person.y, person.pos.y)
			stage.zoom = zoom
			stage.update_camera(0, true)
			tf.lod_level = level
			tf.present(clock)
			person.rig.set_lod(level, true)
			for i in 4:
				await process_frame
				person.rig.set_lod(level, true)
			await RenderingServer.frame_post_draw
			var image := root.get_texture().get_image()
			var c := Vector2i(683, 315)
			var half := Vector2i(int(260.0 * 24.0 / zoom) + 40, int(150.0 * 24.0 / zoom) + 30)
			image.get_region(Rect2i(c - half, half * 2)).save_png(dir.path_join("lod%d_zoom%d.png" % [level, int(zoom)]))
	tf.lod_level = 2
	print("LOD comparison saved")


## Real shadows against the contact blob alone, close and at the default zoom.
func shadow_comparison(target: Vector3) -> void:
	if not wanted("shadow"):
		return
	var dir := out_dir.path_join("shadow")
	DirAccess.make_dir_recursive_absolute(dir)
	for zoom in [34.0, 70.0]:
		for real in [true, false]:
			for p in tf.people:
				for mesh in p.meshes:
					mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if real else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			await look(target, zoom)
			await save(dir.path_join("%s_zoom%d.jpg" % ["real" if real else "blob", int(zoom)]))
	for p in tf.people:
		for mesh in p.meshes:
			mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if tf.cast_real_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	print("shadow comparison saved")

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.player_id = "qa-townsfolk-shots"
	# main.gd's _ready runs its smoke test at its end when `smoke` is set: only after it.
	var settle := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < settle:
		await process_frame
	game.smoke = true
	stage = game.stage
	# The townsfolk script loads on a worker after the launch (landscape.attach_townsfolk).
	while not stage.attach_townsfolk():
		await process_frame
	tf = stage.townsfolk
	await town(hall_level)
	# Models in, then a minute of town life so everybody is somewhere in their day.
	var deadline := Time.get_ticks_msec() + 120000
	while not tf.people.all(func(p): return p.ready) and Time.get_ticks_msec() < deadline:
		tf.simulate_all = true
		tf.present(clock)
		await process_frame
	tf.simulate_all = false
	for i in 60:
		clock += 1.0
		tf.present(clock)
	var hall_at := marker_of("ECO-05")
	var store_at := marker_of("ECO-01")
	var lumber_at := marker_of("RES-01")
	print("people %d, hall %s, warehouse %s, lumber camp %s" % [tf.people.size(), str(hall_at), str(store_at), str(lumber_at)])
	# (The square's meeting, where there is one, walking up a few seconds in.)
	if wanted("hall_close"):
		meet_clock(hall_at, 16.0)
	await sequence("hall_close", hall_at + Vector3(0, 0, 4), 34.0)
	await sequence("hall_default", hall_at + Vector3(2, 0, 4), 70.0, 4)
	await sequence("warehouse_close", store_at + Vector3(0, 0, 4), 36.0, 4)
	await sequence("lumber_close", lumber_at + Vector3(2, 0, 4), 36.0, 4)
	# Social moments: neighbours meeting at the well (the clock set to just before they walk up
	# to each other; at the market too where a pair meets there), the merchant at a stall.
	var market_at := marker_of("ECO-03")
	var well_at := marker_of("SUP-05")
	if market_at != Vector3.ZERO and wanted("market_close"):
		meet_clock(market_at)
		await sequence("market_close", market_at + Vector3(0, 0, 4), 34.0)
	if well_at != Vector3.ZERO and wanted("well_close"):
		meet_clock(well_at)
		await sequence("well_close", well_at + Vector3(0, 0, 3), 30.0)
	if well_at != Vector3.ZERO:
		await scale_comparison(well_at + Vector3(0, 0, 3))
	await shadow_comparison(hall_at + Vector3(0, 0, 4))
	await lod_comparison()
	print("SHOTS done")
	quit()
