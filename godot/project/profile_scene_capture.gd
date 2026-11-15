extends SceneTree

# Fixed-camera captures of the running game (city and world) for before/after
# comparisons. Needs a real renderer, e.g.:
#   xvfb-run -s "-screen 0 1366x630x24" godot --rendering-driver opengl3 --path . \
#     -s profile_scene_capture.gd -- --out=/abs/dir --tag=after

const SHOTS := [
	["city", Vector3(4, 0, -4), 34.0, 0.0],
	["city", Vector3(-10, 0, 8), 70.0, 0.0],
	["world", Vector3(0, 0, 0), 60.0, 0.6],
	["world", Vector3(40, 0, -30), 140.0, 0.0],
]

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var out := "user://captures"
	var tag := "capture"
	var only := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=")
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.smoke = true
	var index := 0
	for shot in SHOTS:
		if not only.is_empty() and shot[0] != only:
			index += 1
			continue
		if game.map_name != shot[0]:
			await game.show_scene(shot[0])
		var stage = game.stage
		stage.target = shot[1]
		stage.zoom = shot[2]
		stage.world_yaw = shot[3]
		stage.update_camera(0, true)
		stage.update_visible_batches()
		for i in 12:
			await process_frame
		await RenderingServer.frame_post_draw
		var path := "%s/%s_%d_%s.png" % [out, tag, index, shot[0]]
		root.get_texture().get_image().save_png(path)
		print("CAPTURE ", path, " draw_calls=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			" primitives=", Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
			" objects=", Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME))
		index += 1
	quit(0)
