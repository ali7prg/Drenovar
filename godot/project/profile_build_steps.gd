extends SceneTree

# Frames of a construction or upgrade on its plot with a fixed camera, through the
# game's own site path (main.site_view -> CityWorks.present), at chosen points of the
# order's progress. Used for the build/upgrade recordings.
#   xvfb-run -s "-screen 0 1100x760x24" godot --rendering-driver opengl3 --path . \
#     -s profile_build_steps.gd -- --out=/abs/dir --type=ECO-02[,RES-02] --from=2[,3] [--frames=24] [--zoom=30]
# --from=0 builds level I from scratch; --from=N upgrades N -> N+1.
# Output: <out>/<TYPE>_<from>to<to>_<NNN>.png (NNN = frame), plus _before/_after stills
# of the city building itself.

const PLOT := "v1-5"

func _initialize() -> void:
	call_deferred("run")

func plot_at(data: Dictionary, id: String) -> Vector3:
	for plot in data.plots:
		if plot.id == id:
			return Vector3(float(plot.x), 0, float(plot.z))
	return Vector3.ZERO

func city_state(game, type: String, level: int) -> Dictionary:
	var state: Dictionary = game.data.demo.duplicate(true)
	var city: Dictionary = state.city
	city.buildings = [{"id": "building-hall", "type": "ECO-05", "plotId": "v1-0", "level": 5}]
	var cleared: Array = ["v1-0", PLOT]
	if level > 0:
		city.buildings.append({"id": "building-site", "type": type, "plotId": PLOT, "level": level})
	city.kingdom.clearedPlots = cleared
	var at := plot_at(game.data, PLOT)
	var felled: Array = []
	for tree in game.data.woods:
		var p: Array = tree.p
		if Vector2(float(p[0]) - at.x, float(p[2]) - at.z).length() < 16.0:
			felled.append(tree.id)
	city.progress.felled = felled
	return state

func shoot(path: String) -> void:
	for i in 3:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)

func run() -> void:
	var out := "user://captures"
	var types: Array = ["ECO-01"]
	var froms: Array = [0]
	var frames := 24
	var zoom := 30.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--type="):
			types = Array(arg.trim_prefix("--type=").split(","))
		elif arg.begins_with("--from="):
			froms = Array(arg.trim_prefix("--from=").split(",")).map(func(v): return int(v))
		elif arg.begins_with("--frames="):
			frames = int(arg.trim_prefix("--frames="))
		elif arg.begins_with("--zoom="):
			zoom = float(arg.trim_prefix("--zoom="))
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1100, 760)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.smoke = true
	for type in types:
		for from in froms:
			await record(game, out, type, from, frames, zoom)
	quit(0)

func record(game, out: String, type: String, from: int, frames: int, zoom: float) -> void:
	var stage = game.stage
	var at := plot_at(game.data, PLOT)
	var tag := "%s_%dto%d" % [type, from, from + 1]
	game.state = city_state(game, type, from)
	stage.present(game.state)
	stage.target = at
	stage.zoom = zoom
	stage.update_camera(0, true)
	stage.update_visible_batches()
	for i in 10:
		await process_frame
	await shoot("%s/%s_before.png" % [out, tag])
	var started := 1.0e12
	var ends := started + 600000.0
	var source := {"key": "building-site" if from > 0 else PLOT, "kind": "upgrade" if from > 0 else "build",
		"type": type, "ends": ends, "started": started, "confirmed": true, "plot": PLOT}
	var site: Dictionary = game.site_view(source.duplicate())
	for f in frames + 1:
		var p := float(f) / frames
		stage.works.present({}, site, started + p * (ends - started), 0.016)
		await shoot("%s/%s_%03d.png" % [out, tag, f])
	stage.works.present({}, {}, ends, 0.016)
	game.state = city_state(game, type, from + 1)
	stage.present(game.state)
	for i in 6:
		await process_frame
	await shoot("%s/%s_after.png" % [out, tag])
	print("FRAMES ", tag, " ", frames + 1)
