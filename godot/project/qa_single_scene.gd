extends SceneTree

# Phone memory: only one scene is kept. Switching city -> world -> city frees the
# previous scene before the next one loads, nothing keeps a reference to it, and
# the game keeps running (works, plates, input) in the reloaded city.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	game.single_scene = true
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	var city = game.stage
	check(not game.two_scenes_fit(), "Phone mode still keeps two scenes")
	await game.show_scene("world")
	for i in 3:
		await process_frame
	check(not is_instance_valid(city), "City scene still in memory while the world is shown")
	check(game.scene_cache.size() == 1 and game.scene_cache.has("world"), "Scene cache: %s" % str(game.scene_cache.keys()))
	var world = game.stage
	# Idle long enough that a background preparation would have started.
	game.last_interaction_msec = Time.get_ticks_msec() - 10000
	game.scene_switch_msec = Time.get_ticks_msec() - 10000
	for i in 20:
		await process_frame
	check(game.prewarm_name.is_empty() and game.scene_cache.size() == 1, "Other scene prepared in the background on a phone")
	await game.show_scene("city")
	for i in 5:
		await process_frame
	check(not is_instance_valid(world), "World scene still in memory in the city")
	check(game.map_name == "city" and is_instance_valid(game.stage) and game.stage.visible, "City did not come back")
	check(is_instance_valid(game.stage.works) and not game.stage.place_markers.is_empty(), "Reloaded city is incomplete")
	game.show_build_menu()
	await process_frame
	check(game.modal.visible, "Build window does not open in the reloaded city")
	game.close_modal()
	print("QA_SINGLE_SCENE checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
