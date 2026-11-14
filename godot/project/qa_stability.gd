extends SceneTree

# Headless stability profile: scene-switch cost, worst frame during transitions,
# CPU-side memory and node/object growth across repeated city <-> world cycles.
# It does not measure GPU time or iPhone memory; it detects main-thread stalls
# and leaks that are platform-independent.

var failures: Array[String] = []
var checks := 0
var worst_frame_ms := 0.0
var last_frame_us := 0
var tracking := false

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func _process(_delta: float) -> bool:
	var now := Time.get_ticks_usec()
	if tracking and last_frame_us > 0:
		worst_frame_ms = maxf(worst_frame_ms, (now - last_frame_us) / 1000.0)
	last_frame_us = now
	return false

func memory_mb() -> float:
	return Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0

func measure_switch(game: Node, scene: String) -> Dictionary:
	worst_frame_ms = 0.0
	last_frame_us = 0
	tracking = true
	var started := Time.get_ticks_msec()
	await game.show_scene(scene)
	await process_frame
	tracking = false
	return {"scene": scene, "ms": Time.get_ticks_msec() - started, "worst_frame_ms": snappedf(worst_frame_ms, 0.1),
		"memory_mb": snappedf(memory_mb(), 0.1), "nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"objects": int(Performance.get_monitor(Performance.OBJECT_COUNT))}

func run() -> void:
	root.size = Vector2i(1366, 630)
	var boot := Time.get_ticks_msec()
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	await process_frame
	var report := {"boot_ms": Time.get_ticks_msec() - boot, "boot_memory_mb": snappedf(memory_mb(), 0.1), "cycles": []}
	game.smoke = true
	var first_world := await measure_switch(game, "world")
	report.first_world = first_world
	# Desktop CPU budget; the world build is time-sliced (0.5.9: ~70-105 ms frames).
	check(first_world.worst_frame_ms < 60.0, "World load frame spike: %.1f ms" % first_world.worst_frame_ms)
	var cached_city := await measure_switch(game, "city")
	report.cached_city = cached_city
	check(cached_city.ms < 200, "Cached city switch stalled: %d ms" % cached_city.ms)
	var baseline_nodes := 0
	var baseline_memory := 0.0
	for cycle in 4:
		# Force the cold path each cycle: retire the inactive scene and drain it.
		await game.show_scene("world")
		game.release_inactive_scene()
		while not game.retired_nodes.is_empty():
			game.drain_retired_scenes()
			await process_frame
		var city := await measure_switch(game, "city")
		game.release_inactive_scene()
		while not game.retired_nodes.is_empty():
			game.drain_retired_scenes()
			await process_frame
		for i in 3:
			await process_frame
		var sample := {"cycle": cycle, "cold_city": city, "settled_nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
			"settled_memory_mb": snappedf(memory_mb(), 0.1), "orphans": int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT))}
		report.cycles.append(sample)
		if cycle == 1:
			baseline_nodes = sample.settled_nodes
			baseline_memory = sample.settled_memory_mb
		elif cycle > 1:
			check(sample.settled_nodes <= baseline_nodes + 8, "Node leak across scene cycles: %d -> %d" % [baseline_nodes, sample.settled_nodes])
			check(sample.settled_memory_mb <= baseline_memory + 24.0, "Memory growth across scene cycles: %.1f -> %.1f MB" % [baseline_memory, sample.settled_memory_mb])
	print("QA_STABILITY_REPORT ", JSON.stringify(report))
	print("QA_STABILITY checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
