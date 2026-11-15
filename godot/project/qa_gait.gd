extends SceneTree

# Foot-slide check for marching formations: the planted-foot speed of the
# selected clip at the selected tempo must match the authoritative ground speed
# whenever that speed lies inside the supported gait range.

const Landscape = preload("res://src/landscape.gd")
const GaitTable = preload("res://src/gait_table.gd")
var failures: Array[String] = []
var checks := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	for id in data.unitModels:
		check(GaitTable.STANCE_SPEED.has(id), "Gait table misses " + id)
		var stance: Dictionary = GaitTable.STANCE_SPEED.get(id, {})
		check(float(stance.get("walk", 0)) > 0.1 and float(stance.get("run", 0)) > float(stance.get("walk", 0)), "Implausible stride for " + id)
		var walk := float(stance.walk) * Landscape.FIELD_UNIT_SCALE
		var run_speed := float(stance.run) * Landscape.FIELD_UNIT_SCALE
		var low := walk * Landscape.WALK_TEMPO.x
		var high := run_speed * Landscape.RUN_TEMPO.y
		for k in 9:
			var speed := lerpf(low, high, k / 8.0)
			var gait: Array = Landscape.gait_for(id, speed)
			var foot := (walk if gait[0] == "walk" else run_speed) * float(gait[1])
			check(absf(foot - speed) / speed < 0.02, "%s skates at %.2f u/s: %s x%.2f gives %.2f" % [id, speed, gait[0], gait[1], foot])
		check(Landscape.gait_for(id, walk)[0] == "walk", id + " should walk at natural walk speed")
		check(Landscape.gait_for(id, run_speed)[0] == "run", id + " should run at natural run speed")
	# Integration: a real formation on the stage plays the matched clip and tempo.
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	var stage = game.stage
	var local_state: Dictionary = game.state.duplicate(true)
	for case in [{"distance": 10.0, "ms": 10000.0}, {"distance": 4.0, "ms": 10000.0}]:
		var army := {"id": "qa_gait_%d" % int(case.distance), "status": "outbound", "units": {"ENG-01": 3, "ENG-06": 1},
			"path": [{"x": 0, "z": 0}, {"x": case.distance, "z": 0}], "startsAt": 0, "arrivesAt": case.ms}
		local_state.armies = [army]
		stage.target = Vector3.ZERO
		stage.zoom = 40
		stage.update_camera(0, true)
		for frame in 3:
			stage.present_armies(local_state, 5000 + frame * 16)
		var group: Node3D = stage.actors.get_node_or_null(NodePath(army.id))
		check(group != null and group.get_child_count() == 4, "Formation missing")
		if group == null:
			continue
		var speed: float = case.distance / (case.ms / 1000.0)
		for unit: Node3D in group.get_children():
			var unit_id := String(unit.name).split("_")[0]
			var expected: Array = Landscape.gait_for(unit_id, speed)
			check(unit.get_meta("clip", "") == expected[0], "%s plays %s instead of %s" % [unit.name, unit.get_meta("clip", ""), expected[0]])
			for player: AnimationPlayer in unit.get_meta("animation_players", []):
				check(is_equal_approx(player.speed_scale, expected[1]), "%s tempo %.2f != %.2f" % [unit.name, player.speed_scale, expected[1]])
				check(expected[0] in player.current_animation.to_lower(), "%s current clip %s" % [unit.name, player.current_animation])
		army.status = "returned"
		stage.present_armies(local_state, 6000)
		await process_frame
	print("QA_GAIT checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
