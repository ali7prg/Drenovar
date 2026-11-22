extends SceneTree
## In-game stills of build 1022 (rendered, not headless) against the synthetic V6 fixture:
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile -s qa_merge_1022_shots.gd -- --server=http://127.0.0.1:8799 --shots=<dir>
## city.png (the 1021 city with the forest layer), roster_army.png (army panel), roster_recruit.png
## (barracks recruitment), forest_off_locked.png (camera over the forest with the adventure off).
## With -- --adventure (fixture with DRENOVAR_QA_ADVENTURE=1): forest_on_unlocked.png (town hall III,
## intro invitation), forest_on_forest.png (camera over the forest, adventure bar).

var game: Node
var shots_dir := "res://../../forest_rescue/qa/ingame/merge_1022"
var saved: Array = []
var adventure := false

func post(path: String, body: Variant = null) -> void:
	var client := HTTPRequest.new()
	client.timeout = 15.0
	root.add_child(client)
	client.request(game.endpoint + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST,
		"" if body == null else JSON.stringify(body))
	await client.request_completed
	client.queue_free()

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots_dir = arg.trim_prefix("--shots=")
		if arg == "--adventure":
			adventure = true
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame
		if OS.has_environment("QA_SHOTS_TRACE") and i % 10 == 0:
			print("FRAME ", i, " ", Time.get_ticks_msec())

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
	print("STAGE scene ", Time.get_ticks_msec())
	# let the launch screen fade and the forest world finish
	var world: Node = root.find_child("ForestWorld", true, false)
	deadline = Time.get_ticks_msec() + 240000
	while (world == null or world.get("_ready_emitted") != true) and Time.get_ticks_msec() < deadline:
		await process_frame
		world = root.find_child("ForestWorld", true, false)
	print("STAGE world ", Time.get_ticks_msec())
	await frames(90)
	print("STAGE settled ", Time.get_ticks_msec())
	if adventure:
		await post("/test/army", {"units": {"ENG-02": 3000, "ENG-03": 3000, "ENG-06": 3000}})
		await post("/test/hall?level=3")
		print("STAGE posted ", Time.get_ticks_msec())
		var fresh: Dictionary = await game.request("state")
		if fresh.has("city"):
			game.accept(fresh)
		await frames(150)
		await shot("forest_on_unlocked")
		if game.forest_game.intro.presenting():
			game.forest_game.intro.on_follow()
		var deadline2 := Time.get_ticks_msec() + 120000
		while (game.forest_game.acting or game.forest_game.client.in_flight) and Time.get_ticks_msec() < deadline2:
			await process_frame
		if game.modal.visible:
			game.close_modal()
		game.stage.target = Vector3(-78.0, 0.0, 30.0)
		game.stage.update_camera(0, true)
		await frames(150)
		await shot("forest_on_forest")
		print("MERGE_1022_SHOTS ", JSON.stringify(saved), " adventure_known=", game.forest_game.client.known, " unlocked=", game.forest_game.client.unlocked())
		quit(0)
		return
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
