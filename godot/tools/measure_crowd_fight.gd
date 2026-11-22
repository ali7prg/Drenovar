extends SceneTree
# Build 1020 audit: one hunt of the real scene, offline, from the server simulator's
# own output (tests/combat_v010/server_combat_cases.json), stretched by the game's
# CombatPresentation, presented in 50 ms steps. Prints per-soldier swings, the share
# of soldier-frames mid-blow, distances from the creature and far reserves.
#   cd godot/project && godot --headless --path . -s ../tools/measure_crowd_fight.gd -- --scene=city
#   (--scene=world --x=-50 --z=-30, --case=spear_sword_tenerys)
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const Clock = preload("res://src/combat_presentation.gd")
var args := {}
func _initialize():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a: args[a.substr(2, a.find("=")-2)] = a.substr(a.find("=")+1)
	call_deferred("run")
func run():
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage): await process_frame
	game.set_process(false)
	var scene: String = args.get("scene", "world")
	if game.map_name != scene: await game.show_scene(scene)
	CombatV010.set_enabled(true)
	var stage = game.stage
	var cases := {}
	for c in JSON.parse_string(FileAccess.get_file_as_string("res://tests/combat_v010/server_combat_cases.json")).cases: cases[c.name] = c
	var case: Dictionary = cases[args.get("case", "mixed_all_types_velkor")]
	var state: Dictionary = game.state.duplicate(true)
	var holder: Dictionary = state.world if scene == "world" else state
	var enc: Dictionary = holder.encounters[0]
	if scene == "city":
		for e in holder.encounters:
			if int(e.level) == int(case.level): enc = e
		holder.encounters = [enc]
	else:
		enc.position = {"x": float(args.get("x", "-50")), "z": float(args.get("z", "-30"))}
		enc.level = int(case.level)
	enc.patrol = []
	if not enc.has("spec"): enc.spec = {"id": str(enc.get("species", "tenerys")), "name": "x", "hp": 1400}
	var at: Vector3 = stage.point(enc.position)
	var start := 300000.0
	var walk := 20000.0
	var path := [{"x": at.x - 30.0, "z": at.z + 26.0}, {"x": at.x - 12.0, "z": at.z + 8.0}, {"x": at.x, "z": at.z}]
	if scene == "city":
		var out := Vector3(at.x, 0.0, at.z).normalized()
		path = [{"x": at.x - out.x * 30.0, "z": at.z - out.z * 30.0}, {"x": at.x - out.x * 14.0, "z": at.z - out.z * 14.0}, {"x": at.x, "z": at.z}]
	var army := {"id": "m-crowd", "status": "outbound", "target": enc.id, "worldKind": "creature", "path": path,
		"units": case.party.duplicate(), "startsAt": start - walk, "arrivesAt": start, "battleAt": start,
		"battleEndsAt": start + float(case.result.duration), "battle": {"events": case.result.events.duplicate(true)}, "fallen": [],
		"returnStartsAt": start + float(case.result.duration), "returnsAt": start + float(case.result.duration) + walk}
	Clock.stretch(army, {})
	var ends := float(army.battleEndsAt)
	stage.engage_sync = true
	stage.target = at; stage.zoom = 30.0; stage.update_camera(0, true)
	# Models and clip libraries load in the background: let every soldier exist first.
	var warm := Time.get_ticks_msec()
	while Time.get_ticks_msec() - warm < 20000:
		var shown0: Dictionary = army.duplicate(true)
		holder.armies = [shown0]
		stage.present_armies(state, start - 4000.0)
		var actor0: Node3D = stage.actors.get_node_or_null("m-crowd")
		if actor0 != null and actor0.get_child_count() >= stage.army_routes["m-crowd"].slots.size():
			break
		await process_frame
	var swings := {}
	var last_clip := {}
	var frames := 0
	var mid := 0
	var dist := {}
	var cost: Array = []
	var t := start - 4000.0
	while t < ends:
		var shown: Dictionary = army.duplicate(true)
		shown.status = "outbound" if t < start else "fighting"
		enc.status = "alive" if t < start else "fighting"
		holder.armies = [shown]
		var t0 := Time.get_ticks_usec()
		stage.present_armies(state, t)
		stage.present_creatures(state, t, 0.05)
		if t >= start: cost.append((Time.get_ticks_usec() - t0) / 1000.0)
		if t >= start + 1500.0:
			var actor: Node3D = stage.actors.get_node_or_null("m-crowd")
			for unit in (actor.get_children() if actor != null else []):
				if not unit is Node3D or unit.name == &"Ferry": continue
				var key := String(unit.name)
				var clip: String = unit.get_meta("clip", "")
				frames += 1
				if clip == "attack": mid += 1
				if clip == "attack" and last_clip.get(key, "") != "attack": swings[key] = int(swings.get(key, 0)) + 1
				last_clip[key] = clip
				var p: Vector3 = unit.global_position
				dist[key] = Vector2(p.x - at.x, p.z - at.z).length()
		t += 50.0
	var plan: Dictionary = stage.army_routes["m-crowd"].get("engage", {})
	var per_type := {}
	for key in dist:
		var id: String = str(key).get_slice("_", 0)
		if not per_type.has(id): per_type[id] = []
		per_type[id].append([int(swings.get(key, 0)), snappedf(dist[key], 0.1)])
	var riders_far := 0
	var far := 0
	for key in plan.get("reserve_rows", {}):
		if int(plan.reserve_rows[key]) >= 3:
			far += 1
			if key.begins_with("ENG-06"): riders_far += 1
	var counts: Array = dist.keys().map(func(k): return int(swings.get(k, 0)))
	counts.sort()
	cost.sort()
	print("MEASURE ", JSON.stringify({"scene": scene, "shown_fight_ms": ends - start, "soldiers": dist.size(), "mid_blow_share": snappedf(float(mid) / maxf(1, frames), 0.01),
		"swings_min": counts[0] if not counts.is_empty() else 0, "swings_median": counts[counts.size() / 2] if not counts.is_empty() else 0,
		"soldiers_without_swing": counts.filter(func(c): return c == 0).size(), "far_reserves": far, "riders_far": riders_far,
		"present_ms_median": snappedf(cost[cost.size() / 2], 0.01), "present_ms_p95": snappedf(cost[int(cost.size() * 0.95)], 0.01), "present_ms_p99": snappedf(cost[int(cost.size() * 0.99)], 0.01), "present_ms_max": snappedf(cost[-1], 0.01)}))
	print("PERTYPE ", JSON.stringify(per_type))
	quit()
