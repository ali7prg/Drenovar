extends SceneTree
## In-game stills of build 1022 (rendered, not headless) against the synthetic V6 fixture:
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile -s qa_merge_1022_shots.gd -- --server=http://127.0.0.1:8799 --shots=<dir>
## city.png (the 1021 city with the forest layer), roster_army.png (army panel), roster_recruit.png
## (barracks recruitment), forest_off_locked.png (camera over the forest with the adventure off).

var game: Node
var shots_dir := "res://../../forest_rescue/qa/ingame/merge_1022"
var saved: Array = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots_dir = arg.trim_prefix("--shots=")
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func shot(name: String) -> void:
	await frames(12)
	var dir := ProjectSettings.globalize_path(shots_dir)
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_texture().get_image().save_png(dir.path_join(name + ".png"))
	saved.append(name)
	print("SHOT ", name)

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 240000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	# let the launch screen fade and the forest world finish
	var world: Node = root.find_child("ForestWorld", true, false)
	deadline = Time.get_ticks_msec() + 240000
	while (world == null or world.get("_ready_emitted") != true) and Time.get_ticks_msec() < deadline:
		await process_frame
		world = root.find_child("ForestWorld", true, false)
	await frames(90)
	await shot("city")
	game.show_armies()
	await shot("roster_army")
	game.close_modal()
	var barracks: Array = game.state.city.buildings.filter(func(b): return b.type == "MIL-01")
	if not barracks.is_empty():
		game.open_recruitment(barracks[0], "ENG-01", 1)
		await frames(60)
		await shot("roster_recruit")
		game.close_modal()
	# camera over the outer forest: locked (fogged) with the adventure off
	game.stage.target = Vector3(-78.0, 0.0, 30.0)
	game.stage.update_camera(0, true)
	await frames(120)
	await shot("forest_off_locked")
	print("MERGE_1022_SHOTS ", JSON.stringify(saved), " adventure_known=", game.forest_game.client.known)
	quit(0)
