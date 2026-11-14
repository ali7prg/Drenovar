extends SceneTree

# Fixed-camera captures of single buildings by level in the running game (real city,
# town plan, name plates on), for before/after comparisons of a building's look.
# Every frame of one type uses the same plot, camera target, zoom and yaw.
#   xvfb-run -s "-screen 0 1100x760x24" godot --rendering-driver opengl3 --path . \
#     -s profile_building_levels.gd -- --out=/abs/dir --tag=after \
#     [--set=ECO-01:1-5,ECO-02:1-5] [--pairs] [--zoom=34]
# Output: <out>/<tag>_<TYPE>-<L>.png and, with --pairs, <tag>_pair_<A>_<B>-<L>.png
# (both types on neighbouring plots at the same level).

const PLOT := "v1-5"          # (9, 11): open ground away from the town hall
const PAIR_PLOTS := ["v1-5", "v1-2"]
const CLEAR_RADIUS := 16.0   # trees felled around the shot (a normal grown town)
const DEFAULT_SET := {"ECO-01": [1, 2, 3, 4, 5], "ECO-02": [1, 2, 3, 4, 5], "ECO-03": [1, 2, 3, 4, 5],
	"RES-02": [1, 2, 3, 4, 5], "RES-03": [1, 2, 3, 4, 5]}
const PAIRS := [["ECO-01", "ECO-02"], ["RES-02", "RES-03"]]

func _initialize() -> void:
	call_deferred("run")

func state_with(data: Dictionary, placed: Array) -> Dictionary:
	var state: Dictionary = data.demo.duplicate(true)
	var city: Dictionary = state.city
	city.buildings = [{"id": "building-hall", "type": "ECO-05", "plotId": "v1-0", "level": 5}]
	var cleared: Array = ["v1-0"]
	for entry in placed:
		city.buildings.append({"id": "building-" + entry[1], "type": entry[0], "plotId": entry[1], "level": entry[2]})
		cleared.append(entry[1])
	city.kingdom.clearedPlots = cleared
	var felled: Array = []
	for tree in data.woods:
		var p: Array = tree.p
		for entry in placed:
			var at := plot_at(data, entry[1])
			if Vector2(float(p[0]) - at.x, float(p[2]) - at.z).length() < CLEAR_RADIUS:
				felled.append(tree.id)
				break
	city.progress.felled = felled
	return state

func plot_at(data: Dictionary, id: String) -> Vector3:
	for plot in data.plots:
		if plot.id == id:
			return Vector3(float(plot.x), 0, float(plot.z))
	return Vector3.ZERO

func shoot(game, placed: Array, target: Vector3, zoom: float, path: String) -> void:
	game.state = state_with(game.data, placed)
	game.stage.present(game.state)
	var stage = game.stage
	stage.target = target
	stage.zoom = zoom
	stage.update_camera(0, true)
	stage.update_visible_batches()
	for i in 16:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)
	print("CAPTURE ", path)

func run() -> void:
	var out := "user://captures"
	var tag := "levels"
	var wanted: Dictionary = DEFAULT_SET
	var pairs := false
	var zoom := 34.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=")
		elif arg == "--pairs":
			pairs = true
		elif arg.begins_with("--zoom="):
			zoom = float(arg.trim_prefix("--zoom="))
		elif arg.begins_with("--set="):
			wanted = {}
			for item in arg.trim_prefix("--set=").split(","):
				var parts := item.split(":")
				var span := parts[1].split("-")
				var levels: Array = []
				for l in range(int(span[0]), int(span[-1]) + 1):
					levels.append(l)
				wanted[parts[0]] = levels
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1100, 760)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	var at := plot_at(game.data, PLOT)
	for type in wanted:
		for level in wanted[type]:
			await shoot(game, [[type, PLOT, level]], at, zoom, "%s/%s_%s-%d.png" % [out, tag, type, level])
	if pairs:
		var a := plot_at(game.data, PAIR_PLOTS[0])
		var b := plot_at(game.data, PAIR_PLOTS[1])
		for pair in PAIRS:
			for level in [1, 2, 3, 4, 5]:
				await shoot(game, [[pair[0], PAIR_PLOTS[0], level], [pair[1], PAIR_PLOTS[1], level]],
					(a + b) * 0.5, zoom * 1.35, "%s/%s_pair_%s_%s-%d.png" % [out, tag, pair[0], pair[1], level])
	quit(0)
