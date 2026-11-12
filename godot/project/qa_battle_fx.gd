extends SceneTree

# Creature battle effects driven by a server-shaped battle timeline: ring, health
# plate (ratio from the last hit's hp), damage numbers only for recent hits, pool
# limits, everything hidden once the battle is over, and the per-frame cost.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func shown(stage: Node, kind: String) -> Array:
	return stage.battle_fx.pools[kind].filter(func(node): return node.visible)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	await game.show_scene("world")
	var stage = game.stage
	var state: Dictionary = game.state.duplicate(true)
	var enc: Dictionary = state.world.encounters[0]
	enc.patrol = []
	enc.position = {"x": -28.0, "z": -54.0}
	var at: Vector3 = stage.point(enc.position)
	var max_hp := float(enc.spec.hp)
	var events := []
	var hp := max_hp
	for i in 30:
		hp -= 50.0
		events.append([300.0 + i * 120.0, "soldier_attack", ["ENG-09", "ENG-01"][i % 2], i % 6, hp])
		if i % 4 == 0:
			events.append([360.0 + i * 120.0, "bite", "ENG-09", i % 8, 10])
	var start := 100000.0
	var army := {"id":"army-qa", "status":"fighting", "target":enc.id, "path":[{"x":at.x - 16,"z":at.z + 2},{"x":at.x,"z":at.z}],
		"units":{"ENG-09":8, "ENG-01":4}, "startsAt":start - 20000, "arrivesAt":start, "battleAt":start, "battleEndsAt":start + 9000, "events":events, "fallen":[]}
	state.world.armies = [army]
	stage.target = at
	stage.zoom = 46.0
	stage.update_camera(0, true)
	var worst := 0.0
	for frame in 60:
		var t0 := Time.get_ticks_usec()
		stage.present_armies(state, start + 1000.0 + frame * 16.0)
		stage.present_creatures(state, start + 1000.0 + frame * 16.0, 0.016)
		# The first frames instantiate soldiers and the creature (budgeted by the landscape).
		if frame >= 15:
			worst = maxf(worst, (Time.get_ticks_usec() - t0) / 1000.0)
		await process_frame
	var elapsed := 1000.0 + 59 * 16.0
	check(shown(stage, "ring").size() == 1, "Battle ring not shown")
	check(shown(stage, "bar").size() == 1 and shown(stage, "plate").size() == 1, "Health plate not shown")
	var expected_hp := max_hp
	var recent_hits := 0
	for e in events:
		if e[1] == "soldier_attack" and float(e[0]) <= elapsed:
			expected_hp = float(e[4])
			if elapsed - float(e[0]) <= 900.0:
				recent_hits += 1
	var bar: MeshInstance3D = shown(stage, "bar")[0]
	var ratio: float = bar.material_override.get_shader_parameter("ratio")
	check(absf(ratio - expected_hp / max_hp) < 0.001, "Health ratio %.3f, expected %.3f" % [ratio, expected_hp / max_hp])
	check(shown(stage, "number").size() == mini(recent_hits, stage.battle_fx.POOL.number), "Numbers %d for %d recent hits" % [shown(stage, "number").size(), recent_hits])
	for kind in stage.battle_fx.POOL:
		check(stage.battle_fx.pools[kind].size() == stage.battle_fx.POOL[kind], "Pool grew: " + kind)
	check(worst < 6.0, "Steady battle frame update took %.1f ms" % worst)
	# Battle over: no effect stays on screen.
	army.status = "returning"
	army.returnPath = army.path.duplicate()
	army.returnPath.reverse()
	army.returnStartsAt = start + 9000
	army.returnsAt = start + 30000
	stage.present_armies(state, start + 9500.0)
	stage.present_creatures(state, start + 9500.0, 0.016)
	for kind in stage.battle_fx.POOL:
		check(shown(stage, kind).is_empty(), "Effect left on screen after the battle: " + kind)
	print("QA_BATTLE_FX worst_update_ms=", snappedf(worst, 0.01), " numbers=", recent_hits)
	print("QA_BATTLE_FX checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
