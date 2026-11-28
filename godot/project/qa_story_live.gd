extends SceneTree
## Story dev loop (QA only, not shipped): boots the real game against the local V6 fixture, waits for
## the forest world layer, then runs GDScript snippets dropped into <cmd>/*.gd (each a script with
## `func run(t: SceneTree) -> void`, may await). A snippet's file is renamed *.done afterwards.
##   godot --path . --rendering-driver vulkan --rendering-method mobile -s qa_story_live.gd -- \
##     --server=http://127.0.0.1:8800 --cmd=/abs/dir
## Helpers for snippets: t.game, t.forest, t.frames(n), t.shot(path), t.look(target, zoom).

var game: Node
var forest: Node
var cmd_dir := ""
var busy := false

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--cmd="):
			cmd_dir = arg.trim_prefix("--cmd=")
	call_deferred("boot")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func shot(path: String) -> void:
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var image := root.get_texture().get_image()
	if path.ends_with(".png"):
		image.save_png(path)
	else:
		image.save_jpg(path, 0.88)
	print("LIVE shot ", path)

func look(target: Vector3, zoom: float) -> void:
	var stage: Node = game.stage
	stage.target = target
	stage.zoom = zoom
	stage.update_camera(0, true)
	stage.update_visible_batches()
	await frames(6)

func boot() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 900000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	while game.forest_game == null and Time.get_ticks_msec() < deadline:
		await process_frame
	forest = game.forest_game
	while forest != null and not forest.world_ready() and Time.get_ticks_msec() < deadline:
		await process_frame
	print("LIVE ready hall=", game.hall_level(), " world=", forest != null and forest.world_ready())
	FileAccess.open(cmd_dir.path_join("READY"), FileAccess.WRITE).store_string("ok")

func _process(_delta: float) -> bool:
	if busy or cmd_dir.is_empty() or forest == null or not FileAccess.file_exists(cmd_dir.path_join("READY")):
		return false
	var dir := DirAccess.open(cmd_dir)
	if dir == null:
		return false
	var names := Array(dir.get_files()).filter(func(n): return n.ends_with(".gd"))
	if names.is_empty():
		return false
	names.sort()
	run_snippet(cmd_dir.path_join(names[0]))
	return false

func run_snippet(path: String) -> void:
	busy = true
	var source := FileAccess.get_file_as_string(path)
	DirAccess.rename_absolute(path, path + ".running")
	var script := GDScript.new()
	script.source_code = source
	var err := script.reload()
	if err != OK:
		print("LIVE compile error ", path, " ", err)
	else:
		var obj: Object = script.new()
		print("LIVE run ", path)
		await obj.run(self)
		print("LIVE done ", path)
	DirAccess.rename_absolute(path + ".running", path + ".done")
	busy = false
