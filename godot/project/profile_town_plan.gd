extends SceneTree

# Cost of the town plan on a grown settlement: planning, the mask and the ground mesh.
#   godot --headless --path . -s profile_town_plan.gd

const TownPlan = preload("res://src/town_plan.gd")
const TownGround = preload("res://src/town_ground.gd")
const Base = preload("res://profile_base_capture.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var table: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/city/town_lots.json")).types
	var stage = load("res://src/landscape.gd").new()
	root.add_child(stage)
	var state: Dictionary = Base.new().base_state(data)
	await stage.setup(data, state, "city", {})
	var buildings: Array = []
	for b in state.city.buildings:
		for p in data.plots:
			if p.id == b.plotId:
				buildings.append({"id": b.id, "type": b.type, "level": b.level, "x": float(p.x), "z": float(p.z), "hall": b.type == "ECO-05"})
	var gates: Array = stage.walls.gate_roads.map(func(r): return [r[0], r[1]])
	var corners: Array = data.plots.map(func(p): return Vector2(p.x, p.z))
	var plan := TownPlan.new()
	var t0 := Time.get_ticks_usec()
	for i in 5:
		plan.layout_key = ""
		plan.plan(buildings, table, gates, corners, [], stage.town_ground_ok)
	var t1 := Time.get_ticks_usec()
	var tp := Time.get_ticks_usec()
	for i in 5:
		plan.paint()
	print("PROFILE_PAINT_MS ", (Time.get_ticks_usec() - tp) / 5000.0)
	t1 = Time.get_ticks_usec()
	var ground := TownGround.new()
	root.add_child(ground)
	for i in 5:
		ground.build(plan, stage.static_height)
	var t2 := Time.get_ticks_usec()
	var tg := Time.get_ticks_usec()
	for i in 5:
		ground.build_ground(plan, stage.static_height).free()
	print("PROFILE_GROUND_MS ", (Time.get_ticks_usec() - tg) / 5000.0)
	# An upgrade: one level changes, streets stay.
	var segments_before := JSON.stringify(plan.street_lines())
	buildings[3].level = 5
	var tu := Time.get_ticks_usec()
	plan.plan(buildings, table, gates, corners, [], stage.town_ground_ok)
	ground.build(plan, stage.static_height)
	print("PROFILE_UPGRADE_MS ", (Time.get_ticks_usec() - tu) / 1000.0, " streets_same=", segments_before == JSON.stringify(plan.street_lines()), " ground_builds=", ground.ground_builds)
	print("PROFILE_TOWN lots=", plan.lots.size(), " streets=", plan.segments.size(), " plan_ms=", (t1 - t0) / 5000.0,
		" build_ms=", (t2 - t1) / 5000.0, " kerbs=", ground.kerb_pieces, " posts=", ground.post_count, " lanterns=", ground.lantern_count,
		" ground_tris=", ground.ground.mesh.get_faces().size() / 3)
	quit(0)
