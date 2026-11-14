extends SceneTree

# Captures of a grown settlement (town hall V, fourteen buildings at level IV, felled
# trees around the town), laid out like a real player base, for before/after
# comparisons of the town look. Needs a real renderer:
#   xvfb-run -s "-screen 0 2000x924x24" godot --rendering-driver opengl3 --path . \
#     -s profile_base_capture.gd -- --out=/abs/dir --tag=after

const BASE := [
	["ECO-05", "v1-0", 5], ["ECO-01", "v1-1", 4], ["ECO-02", "v1-6", 4], ["MIL-02", "v1-3", 4],
	["ECO-04", "v1-2", 4], ["SUP-05", "v1-5", 4], ["MIL-01", "v1-8", 4], ["MIL-03", "v1-4", 4],
	["MIL-01", "v1-7", 4], ["RES-01", "v1-11", 4], ["SUP-04", "v1-12", 4], ["RES-04", "v1-14", 4],
	["RES-03", "v1-9", 4], ["RES-02", "v1-30", 4], ["ALT-08", "v1-33", 4],
]
const SHOTS := [
	[Vector3(-8, 0, -10), 60.0, Vector2i(2000, 924)],
	[Vector3(-8, 0, -6), 100.0, Vector2i(2000, 924)],
	[Vector3(-6, 0, -4), 34.0, Vector2i(2000, 924)],
]

func _initialize() -> void:
	call_deferred("run")

func base_state(data: Dictionary) -> Dictionary:
	var state: Dictionary = data.demo.duplicate(true)
	var city: Dictionary = state.city
	city.buildings = []
	var cleared: Array = []
	for entry in BASE:
		city.buildings.append({"id": "building-" + entry[1], "type": entry[0], "plotId": entry[1], "level": entry[2]})
		cleared.append(entry[1])
	city.kingdom.clearedPlots = cleared
	# Every second tree within reach of the town has been felled for wood.
	var felled: Array = []
	var index := 0
	for tree in data.woods:
		var p: Array = tree.p
		if Vector2(float(p[0]) + 5.0, float(p[2]) + 5.0).length() < 62.0:
			index += 1
			if index % 2 == 0:
				felled.append(tree.id)
	city.progress.felled = felled
	return state

func run() -> void:
	var out := "user://captures"
	var tag := "base"
	var only: Array = []
	var demo := false
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=")
		elif arg == "--demo":
			demo = true
		elif arg.begins_with("--shots="):
			only = Array(arg.trim_prefix("--shots=").split(",")).map(func(v): return int(v))
	DirAccess.make_dir_recursive_absolute(out)
	root.size = SHOTS[0][2]
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.state = game.data.demo.duplicate(true) if demo else base_state(game.data)
	game.stage.present(game.state)
	if game.has_method("refresh_hud"):
		game.refresh_hud()
	var index := 0
	for shot in SHOTS:
		if not only.is_empty() and not index in only:
			index += 1
			continue
		root.size = shot[2]
		var stage = game.stage
		stage.target = shot[0]
		stage.zoom = shot[1]
		stage.update_camera(0, true)
		stage.update_visible_batches()
		for i in 20:
			await process_frame
		await RenderingServer.frame_post_draw
		var path := "%s/%s_%d.png" % [out, tag, index]
		root.get_texture().get_image().save_png(path)
		print("CAPTURE ", path)
		index += 1
	quit(0)
