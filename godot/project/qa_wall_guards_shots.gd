extends "res://qa_wall_guards.gd"

# Rendered frames of the wall guards (build 1024), offline (the demo city grown as in
# qa_wall_guards.gd): 10 s sequences at 12 fps (JPG q 85) of
#   patrol_close   - a walkway stretch with a patrol walking up to its tower, stopping and
#                    looking out (zoom 30, hall III / wall III from outside, as the reference);
#   tower_close    - a tower deck of wall II with its sentry (zoom 30);
#   gate_close     - the main gate (zoom 34) and the walls beside it;
#   default_view   - the player's first view (zoom 70) at hall V / wall V;
#   wall2_patrol   - wall II (hall III): a patrol on the palisade's walkway, far side (zoom 30);
#   wall1_towers   - wall I (hall II): no walkway, sentries on the towers (zoom 34);
# and stills (in SHOTS_stills): gate_inside (a QA camera turned round, inside the yard, looking
# at the main gate: the pair beside the passage, which the game's camera sees from outside),
# compare_ours (the close wall shot for the Viking Rise comparison).
# The guards and the townsfolk run on a virtual clock that advances 1/12 s per frame; with
# --fixed-fps 12 the animation advances by the same step.
#   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
#     godot --path . --rendering-driver vulkan --rendering-method mobile --fixed-fps 12 \
#     -s qa_wall_guards_shots.gd -- --shots=/abs/dir [--seconds=10] [--only=a,b]
# Contact sheets, mp4 and gif: python3 godot/tools/townsfolk_sheets.py SHOTS_DIR OUT_DIR.

const FPS := 12
var out_dir := ""
var seconds := 10.0
var only: PackedStringArray = []
var clock := 1794600000.0

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			out_dir = arg.trim_prefix("--shots=")
		elif arg.begins_with("--seconds="):
			seconds = float(arg.trim_prefix("--seconds="))
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",")
	call_deferred("run_shots")

## Stills go beside the sequences' folder (SHOTS_stills), so the sheets tool sees only sequences.
func stills_dir() -> String:
	return out_dir.trim_suffix("/") + "_stills"

func wanted(name: String) -> bool:
	return only.is_empty() or name in only

func step() -> void:
	clock += 1.0 / FPS
	stage.present_parade()
	tf.present(clock)
	wg.present(clock)
	await process_frame

func look(target: Vector3, zoom: float) -> void:
	stage.target = target
	stage.zoom = zoom
	stage.update_camera(0, true)
	stage.update_visible_batches()
	for i in 10:
		await step()

func save(path: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_jpg(path, 0.85)

func sequence(name: String, target: Vector3, zoom: float) -> void:
	if not wanted(name):
		return
	await look(target, zoom)
	var dir := out_dir.path_join(name)
	DirAccess.make_dir_recursive_absolute(dir)
	var frames := int(seconds * FPS)
	for f in frames:
		await step()
		await save(dir.path_join("f%04d.jpg" % f))
	var shown: int = wg.guards.filter(func(g): return g.shown).size()
	var roles := {}
	for g in wg.guards:
		if g.shown:
			roles[g.role] = int(roles.get(g.role, 0)) + 1
	print("SEQUENCE %s: %d frames, %d of %d guards on screen %s, zoom %.0f, draw calls %d, primitives %d" % [name, frames, shown, wg.guards.size(), str(roles), zoom,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])

## The clock set so that guard g is `lead` s before the end of its walk number `walk` (Vector3:
## where that walk ends).
func walk_clock(g, walk: int, lead: float) -> Vector3:
	var seen := 0
	for i in g.kinds.size():
		if g.kinds[i] != 0:
			continue
		if seen == walk:
			var u: float = g.starts[i] + g.lengths[i] - lead
			clock += fposmod(u - g.phase - clock, g.cycle)
			var line: PackedVector3Array = g.lines[g.leg[i]]
			return line[line.size() - 1]
		seen += 1
	return g.pos

## The patrol whose beat the camera sees best: on the far walls (seen from the yard: the
## palisade's stakes, the boards and the covered gallery hide the walkway from outside), the
## longest such beat; `far` false: the walls facing the camera (+x+z).
func pick_patrol(far: bool):
	var best = null
	var best_score := -INF
	var c := Vector3(stage.walls.center.x, 0.0, stage.walls.center.y)
	for g in wg.guards:
		if g.role != "patrol":
			continue
		var mid: Vector3 = g.beat[g.beat.size() / 2]
		var facing := (mid - c).dot(Vector3(1, 0, 1).normalized())
		var score: float = (-facing if far else facing) + g.beat.size() * 0.3
		if score > best_score:
			best_score = score
			best = g
	return best

func pick_tower(far: bool):
	var best = null
	var best_score := -INF
	var c := Vector3(stage.walls.center.x, 0.0, stage.walls.center.y)
	for g in wg.guards:
		if g.role != "tower":
			continue
		var facing: float = (g.pos - c).dot(Vector3(1, 0, 1).normalized())
		var score: float = -facing if far else facing
		if score > best_score:
			best_score = score
			best = g
	return best

func prepare_level(hall: int, level: int) -> void:
	await town(hall)
	wall_level(level)
	await settle("hall %d wall %d" % [hall, level])
	await wait_guards()
	# Close-up meshes in as well, then a minute of the day so everybody is somewhere in it.
	stage.zoom = 30.0
	stage.update_camera(0, true)
	for i in 30:
		await step()
	for i in 60:
		clock += 1.0
		tf.present(clock)
		wg.present(clock)

## A camera turned round (QA only): inside the yard, looking out at the main gate.
func gate_inside() -> void:
	if not wanted("gate_inside"):
		return
	var walls = stage.walls
	var out: Vector3 = walls.main_gate_outward
	var gate: Vector3 = walls.main_gate
	stage.target = gate
	stage.zoom = 34.0
	stage.update_camera(0, true)
	for i in 6:
		await step()
	var camera: Camera3D = stage.camera
	camera.position = gate - out * 75.0 * 1.4142 + Vector3.UP * 83.0
	camera.look_at(gate - out * 3.0, Vector3.UP)
	for i in 6:
		await process_frame
	DirAccess.make_dir_recursive_absolute(stills_dir())
	await save(stills_dir().path_join("gate_inside.jpg"))
	stage.update_camera(0, true)
	stage.apply_camera_pose()
	print("STILL gate_inside: pair at ", wg.gate_spots)

func run_shots() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.player_id = "qa-wall-guards-shots"
	var settle_until := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < settle_until:
		await process_frame
	game.smoke = true
	stage = game.stage
	while not stage.attach_townsfolk():
		await process_frame
	tf = stage.townsfolk
	while stage.wall_guards == null:
		stage.present_workers(Time.get_unix_time_from_system())
		await process_frame
	wg = stage.wall_guards
	if wanted("wall1_towers"):
		await prepare_level(2, 0)
		var sentry = pick_tower(false)
		await sequence("wall1_towers", sentry.pos - Vector3.UP * 3.0, 34.0)
	if wanted("wall2_patrol") or wanted("tower_close"):
		await prepare_level(3, 2)
		# (The far side, seen from the yard: on the near side the stakes hide all but the heads.)
		var g = pick_patrol(true)
		var end := walk_clock(g, 0, 6.0)
		await sequence("wall2_patrol", end.lerp(g.beat[g.beat.size() / 2], 0.3) - Vector3.UP * 2.0, 30.0)
		# A tower of wall II with its sentry (from wall III up the towers' roofs hide the decks
		# from the game's camera).
		var sentry = pick_tower(false)
		await sequence("tower_close", sentry.pos - Vector3.UP * 4.0, 30.0)
	if wanted("patrol_close") or wanted("compare_ours"):
		# Wall III from outside, as the reference: the walkway over the timber merlons.
		await prepare_level(3, 3)
		var patrol = pick_patrol(false)
		var end := walk_clock(patrol, 0, 6.0)
		var at := end.lerp(patrol.beat[patrol.beat.size() / 2], 0.3) - Vector3.UP * 3.0
		await sequence("patrol_close", at, 30.0)
		if wanted("compare_ours"):
			await look(at, 28.0)
			DirAccess.make_dir_recursive_absolute(stills_dir())
			await save(stills_dir().path_join("compare_ours.jpg"))
	await prepare_level(5, 5)
	await sequence("gate_close", stage.walls.main_gate - stage.walls.main_gate_outward * 2.0, 34.0)
	await sequence("default_view", Vector3(5, 0, -4), 70.0)
	await gate_inside()
	print("SHOTS done")
	quit()
