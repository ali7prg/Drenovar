extends SceneTree

# Before/after CPU cost of applying authoritative city updates.
# Builds the 0.5.9 reference landscape and the current one, applies the same
# state changes to both and reports the median of repeated runs (ms).
# Usage: godot --headless --path . -s profile_city_updates.gd

const REPEATS := 5

func _initialize() -> void:
	call_deferred("run")

func timed(stage: Node3D, state: Dictionary) -> float:
	var started := Time.get_ticks_usec()
	stage.present(state)
	return (Time.get_ticks_usec() - started) / 1000.0

func median(values: Array) -> float:
	values.sort()
	return values[values.size() / 2]

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var report := {}
	for label in ["0.5.9", "current"]:
		var script = load("res://tests/reference059/landscape.gd" if label == "0.5.9" else "res://src/landscape.gd")
		var stage = script.new()
		root.add_child(stage)
		var base: Dictionary = data.demo.duplicate(true)
		await stage.setup(data, base, "city", {})
		var cases := {"poll_echo": [], "building_upgrade": [], "construction_order": [], "tree_felled": [], "troops_trained": []}
		for r in REPEATS:
			var s0: Dictionary = base.duplicate(true)
			s0.city.progress.felled = []
			stage.present(s0)
			var echo: Dictionary = s0.duplicate(true)
			echo.serverTime = float(echo.serverTime) + 800.0
			stage.geometries.erase("city_signature")  # forces the update path even for an identical city
			cases.poll_echo.append(timed(stage, echo))
			var upgrade: Dictionary = s0.duplicate(true)
			upgrade.city.buildings[1].level = 2 + r
			cases.building_upgrade.append(timed(stage, upgrade))
			var order: Dictionary = upgrade.duplicate(true)
			order.city.kingdom.order = {"kind": "build", "plotId": "v1-5", "type": "RES-02", "r": r}
			cases.construction_order.append(timed(stage, order))
			var felled: Dictionary = order.duplicate(true)
			felled.city.progress.felled = [data.woods[10 + r].id]
			cases.tree_felled.append(timed(stage, felled))
			var trained: Dictionary = felled.duplicate(true)
			trained.city.military.owned = {"ENG-01": 4 + r}
			cases.troops_trained.append(timed(stage, trained))
		var row := {}
		for key in cases:
			row[key] = snappedf(median(cases[key]), 0.01)
		report[label] = row
		stage.free()
		await process_frame
	print("CITY_UPDATE_PROFILE ", JSON.stringify(report))
	quit(0)
