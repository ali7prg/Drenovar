extends SceneTree

# Background preparation of the world map while the city is on screen:
# it starts only after idle time, pauses while a finger is down, a transition
# requested mid-build finishes it instead of starting another, and the next
# city <-> world switch then comes from the cache.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func frames(count: int) -> void:
	for index in count:
		await process_frame

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	check(game.map_name == "city", "Did not start in the city")
	# Interaction keeps the build from starting.
	game.last_interaction_msec = Time.get_ticks_msec()
	await frames(10)
	check(game.prewarm_name.is_empty(), "Prewarm started during interaction")
	# Idle: it starts.
	game.last_interaction_msec -= 10000
	game.scene_switch_msec -= 10000
	var waited := 0
	while game.prewarm_name.is_empty() and waited < 120:
		await process_frame
		waited += 1
	check(game.prewarm_name == "world", "Prewarm did not start when idle")
	# A finger on the screen pauses it.
	await frames(3)
	var stage: Node = game.prewarm_stage
	if is_instance_valid(stage):
		game.fingers[0] = Vector2(600, 300)
		await frames(2)
		var before: int = stage.get_child_count(true) + stage.render_batches.size()
		await frames(25)
		var after: int = stage.get_child_count(true) + stage.render_batches.size()
		check(before == after and game.prewarm_name == "world", "Background build advanced while a finger was down (%d -> %d)" % [before, after])
		game.fingers.clear()
	# Requesting the world mid-build completes the same build.
	var started := Time.get_ticks_msec()
	await game.show_scene("world")
	check(game.map_name == "world" and game.stage == stage, "World switch did not reuse the background build")
	check(game.prewarm_name.is_empty() and game.scene_cache.has("city") and game.scene_cache.has("world"), "Both scenes are not cached")
	print("QA_PREWARM finish_after_request_ms=", Time.get_ticks_msec() - started, " label=", game.last_scene_label)
	# Next switches come from the cache.
	await game.show_scene("city")
	started = Time.get_ticks_usec()
	await game.show_scene("world")
	var cached_ms := (Time.get_ticks_usec() - started) / 1000.0
	check(game.last_scene_label.ends_with("из кэша"), "Second switch not from cache: " + game.last_scene_label)
	# The timed 40/60 s release does not apply while memory is within budget.
	game.scene_switch_msec -= 120000
	await frames(5)
	check(game.scene_cache.size() == 2 or not game.two_scenes_fit(), "Inactive scene released although memory fits")
	# A memory release cancels and pauses background builds.
	game.release_inactive_scene()
	game.drain_retired_scenes(true)
	game.last_interaction_msec -= 10000
	game.scene_switch_msec -= 10000
	await frames(10)
	check(game.prewarm_name.is_empty(), "Prewarm restarted right after a memory release")
	print("QA_PREWARM cached_switch_ms=", cached_ms, " memory_mb=", snappedf(game.memory_in_use_mb(), 1))
	print("QA_PREWARM checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
