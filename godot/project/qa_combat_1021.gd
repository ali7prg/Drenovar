extends SceneTree
# Build 1021 checks (headless Linux; not iPhone acceptance).
#  1. Late battle: the server sends a hunt's battle only after the army arrives; when
#     its answer is late, the shown fight starts then and keeps every server blow
#     (CombatPresentation.late_starts / stretch(late)), and the army is home at
#     returnsAt.
#  2. Engaging: in the real scene a crowd that reached its creature fights at once,
#     before the battle is known (no idle stand), the creature shows its health and
#     strikes back; the swings go on without a gap when the battle comes.
#  3. Sizes: field soldiers 1.0 in the city (as on the parade ground), 0.5 on the world
#     map; world creatures at 0.6; the world soldiers stand lower than a house. A world
#     creature (about as tall as the trees) stands in a glade of faded crowns.
const Clock = preload("res://src/combat_presentation.gd")
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
var checks := 0
var failures: Array = []
var notes := {}

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failures.append(what)

func case_named(name: String) -> Dictionary:
	for c in JSON.parse_string(FileAccess.get_file_as_string("res://tests/combat_v010/server_combat_cases.json")).cases:
		if c.name == name:
			return c
	return {}

# 1. The clock alone, polls every 800 ms, the battle's answer `late_ms` late. As in
# main.gd the clock is given the server's time (server_time()); the shown time runs
# delay_ms (at least 1650 ms) behind it, so an answer at the first poll after the
# arrival is in time.
func late_battle(late_ms: float) -> Dictionary:
	var clock = Clock.new()
	var case := case_named("mixed_all_types_velkor")
	var arrive := 300000.0
	var walk := 20000.0
	var duration := float(case.result.duration)
	var base := {"id": "late-army", "target": "beast", "worldKind": "velkor", "path": [{"x": 0, "z": 0}, {"x": 20, "z": 0}],
		"units": case.party, "startsAt": arrive - walk, "arrivesAt": arrive, "battleAt": arrive}
	var shown_events := {}
	var first_fight := INF
	var known_at := arrive + late_ms
	var result := {}
	var now := arrive - 6000.0
	var last_poll := -INF
	var state := {}
	while now < arrive + duration + 30000.0:
		if now - last_poll >= 800.0:
			last_poll = now
			var army: Dictionary = base.duplicate(true)
			if now < known_at:
				army.status = "outbound"
			else:
				army.status = "fighting" if now < arrive + duration else "returning"
				army.battleEndsAt = arrive + duration
				army.battle = {"events": case.result.events.filter(func(e): return arrive + float(e.at) <= now)}
				if now >= arrive + duration:
					army.returnStartsAt = arrive + duration
					army.returnsAt = arrive + duration + walk
					army.returnUnits = case.party
					army.returnPath = [{"x": 20, "z": 0}, {"x": 0, "z": 0}]
			state = {"serverTime": now, "playerId": "p", "armies": [army]}
		var frame: Dictionary = clock.frame(state, now, "city")
		var t := float(frame.time)
		for a in frame.state.get("armies", []):
			if a.status == "fighting" and first_fight == INF:
				first_fight = t
				result.late = float(clock.late_starts.get("late-army", 0.0))
				result.blows_from = float(a.get("blows_from", 0.0))
				result.return_starts = float(a.get("returnStartsAt", INF))
			if a.get("battle") is Dictionary:
				for e in a.battle.events:
					if t >= float(a.battleAt) + float(e.at):
						shown_events["%s|%s|%d" % [e.kind, e.unitId, int(e.index)] + "|" + str(e.get("creatureHP", e.get("hp")))] = true
			if a.status == "returning":
				result.returning_at = minf(float(result.get("returning_at", INF)), t)
				result.returns_at = float(a.get("returnsAt", INF))
		now += 50.0
	result.first_fight = first_fight
	result.shown = shown_events.size()
	result.total = case.result.events.size()
	result.late_completions = clock.trace.filter(func(r): return r.phase == "late-completion").size()
	return result

# The march mask (0..255) at a ground point; 0 outside it or when it is off.
func glade_value(stage, p: Vector3) -> int:
	var area: Vector4 = stage.march_clear_area
	if area.w <= 0.0 or stage.march_clear_bytes.is_empty():
		return 0
	var px := int(sqrt(float(stage.march_clear_bytes.size())))
	var c := (Vector2(p.x, p.z) - Vector2(area.x, area.y)) * (px / area.z)
	if c.x < 0.0 or c.y < 0.0 or c.x >= px or c.y >= px:
		return 0
	return int(stage.march_clear_bytes[int(c.y) * px + int(c.x)])

# 4. A city march with a ferry (the server's own route, tests/march_lanes): every
# soldier over the river stands on the raft's deck while the raft is there.
func ferry_rows() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/march_lanes/owner_city_routes.json"))
	var stage = load("res://src/landscape.gd").new()
	root.add_child(stage)
	await stage.setup(data, fixture.state, "city", {})
	stage.set_active(true)
	stage.lanes.slice_override = 1000000
	var route: Dictionary = {}
	for r in fixture.routes:
		if r.get("ferry", false):
			route = r
			break
	var units := {"ENG-01": 6, "ENG-02": 6, "ENG-03": 4, "ENG-05": 4, "ENG-06": 4}
	stage.prewarm_troops(units.keys())
	for id in units:
		while not stage.model_ready(str(data.unitModels[id].field)) or not CombatV010.ready_for("troop", id):
			await process_frame
	var start := 1000000.0
	var walk := float(route.length) / 3.0 * 1000.0
	var army := {"id": "qa-ferry", "status": "outbound", "target": "none", "path": route.path, "units": units,
		"startsAt": start, "arrivesAt": start + walk}
	var state := {"armies": [army], "encounters": [], "world": {"armies": [], "encounters": []}}
	stage.present_armies(state, start - 800.0)
	while not stage.army_routes["qa-ferry"].get("lane_job", {}).get("done", false):
		await process_frame
	var wet_without_raft := 0
	var wet_rows := 0
	var t := start
	while t < start + walk:
		var cache: Dictionary = stage.army_routes["qa-ferry"]
		# The camera follows the column, so it is drawn.
		var total := float(cache.distances[-1])
		stage.target = stage.along_route(cache, clampf((t - start) / walk, 0.0, 1.0))
		stage.zoom = 40.0
		stage.update_camera(0, true)
		stage.present_armies(state, t)
		var actor: Node3D = stage.actors.get_node_or_null("qa-ferry")
		if actor != null:
			var raft := actor.get_node_or_null("Ferry") as Node3D
			for unit in actor.get_children():
				if not unit is Node3D or unit.name == &"Ferry":
					continue
				var at: Vector3 = unit.global_position
				if not stage.dry_ground(at):
					wet_rows += 1
					if raft == null or not raft.visible or at.y < stage.FERRY_DECK - 0.05:
						wet_without_raft += 1
		await process_frame
		t += 100.0
	check(wet_rows > 0, "the ferry route crosses the river: %d soldier-frames over water" % wet_rows)
	check(wet_without_raft == 0, "no soldier over the river without the raft: %d soldier-frames" % wet_without_raft)
	notes.ferry = {"route": str(route.target).left(8), "soldier_frames_over_water": wet_rows, "without_raft": wet_without_raft}
	stage.free()

# 5. Launch: the town plan of a city like the owner's, computed once and kept on the
# device, gives the same lots, streets and ground mask at the next launch.
func town_plan_cache() -> void:
	var TownPlan = load("res://src/town_plan.gd")
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var table: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/city/town_lots.json")).types
	var types := ["ECO-05", "RES-01", "RES-02", "RES-03", "RES-04", "ECO-01", "ECO-02", "ECO-03", "ECO-04", "MIL-01", "MIL-02", "MIL-03", "SUP-01", "SUP-04", "SUP-05"]
	var buildings: Array = []
	for n in types.size():
		buildings.append({"id": "b%d" % n, "type": types[n], "level": 5, "x": float(data.plots[n].x), "z": float(data.plots[n].z), "hall": types[n] == "ECO-05"})
	var corners: Array = data.plots.map(func(p): return Vector2(float(p.x), float(p.z)))
	var gates := [[Vector2(23.5, 34.0), Vector2(38.3, 51.6)], [Vector2(22.9, -23.4), Vector2(40.6, -38.2)]]
	if FileAccess.file_exists(TownPlan.CACHE_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TownPlan.CACHE_PATH))
	var first = TownPlan.new()
	var t0 := Time.get_ticks_usec()
	first.plan(buildings, table, gates, corners, [], Callable())
	var computed_ms := (Time.get_ticks_usec() - t0) / 1000.0
	var second = TownPlan.new()
	t0 = Time.get_ticks_usec()
	second.plan(buildings, table, gates, corners, [], Callable())
	var cached_ms := (Time.get_ticks_usec() - t0) / 1000.0
	check(FileAccess.file_exists(TownPlan.CACHE_PATH), "the town plan is kept on the device")
	check(second.segments.size() == first.segments.size() and second.lots.size() == first.lots.size(), "the kept plan has the same streets and yards")
	check(second.mask.get_data() == first.mask.get_data(), "the kept plan paints the same ground mask")
	check(cached_ms < computed_ms * 0.5, "the kept plan is quicker: %.1f ms instead of %.1f ms" % [cached_ms, computed_ms])
	# An upgrade keeps the layout and restyles the yard (level V -> VI of one building).
	buildings[1].level = 4
	var third = TownPlan.new()
	third.plan(buildings, table, gates, corners, [], Callable())
	check(int(third.lots[1].level) == 4, "a kept plan takes the buildings' current levels")
	notes.town_plan = {"computed_ms": snappedf(computed_ms, 0.1), "kept_ms": snappedf(cached_ms, 0.1), "streets": first.segments.size()}

func run() -> void:
	root.size = Vector2i(1366, 630)
	# 1. A battle on time, and one whose answer comes 4 s late.
	var on_time := late_battle(0.0)
	var late := late_battle(4000.0)
	check(float(on_time.late) == 0.0, "an answer in time starts nothing late: %.0f" % on_time.late)
	check(float(late.late) > 3000.0 and float(late.late) < 5500.0, "a 4 s late answer is measured: %.0f ms" % late.late)
	check(float(late.blows_from) > 3000.0, "the server's blows begin when the answer is there: %.0f ms" % late.blows_from)
	check(int(late.late_completions) == 0, "no blow of a late battle is skipped: %d skipped" % late.late_completions)
	check(int(late.shown) >= int(late.total) - 1, "every server blow is shown: %d of %d" % [late.shown, late.total])
	check(float(late.returning_at) < float(late.returns_at), "the walk home still ends at the server's returnsAt")
	notes.on_time = on_time
	notes.late_4s = late
	# 2 and 3: the real scene, a world hunt whose battle is late.
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	check(is_equal_approx(game.stage.unit_scale, 1.0), "city field soldiers at 1.0 (parade ground scale)")
	await game.show_scene("world")
	CombatV010.set_enabled(true)
	var stage = game.stage
	stage.engage_sync = true
	check(is_equal_approx(stage.unit_scale, 0.5) and is_equal_approx(stage.beast_k, 0.6), "world soldiers 0.5, creatures 0.6")
	var case := case_named("mixed_all_types_velkor")
	var state: Dictionary = game.state.duplicate(true)
	var enc: Dictionary = state.world.encounters[0]
	state.world.encounters = [enc]
	enc.patrol = []
	enc.position = {"x": -0.35, "z": -60.13}
	enc.level = 1
	var at: Vector3 = stage.point(enc.position)
	var arrive := 500000.0
	var walk := 16000.0
	var path := [{"x": at.x, "z": at.z + 30.0}, {"x": at.x, "z": at.z}]
	var army := {"id": "qa-late", "owner": game.player_id, "status": "outbound", "target": enc.id, "worldKind": "velkor", "path": path,
		"units": case.party.duplicate(), "startsAt": arrive - walk, "arrivesAt": arrive, "battleAt": arrive}
	stage.prewarm_troops(case.party.keys())
	for id in case.party:
		while not stage.model_ready(str(game.data.unitModels[id].field)) or not CombatV010.ready_for("troop", id):
			await process_frame
	stage.lanes.slice_override = 1000000
	stage.target = at
	stage.zoom = 30.0
	stage.update_camera(0, true)
	state.world.armies = [army]
	# Before the column sets off: its lane is planned and taken.
	stage.present_armies(state, arrive - walk - 600.0)
	while not stage.army_routes["qa-late"].get("lane_job", {}).get("done", false):
		await process_frame
	# The creature's glade: present_creatures notes it, the next present_armies draws
	# it into the march mask (forest.gdshader march_clear).
	stage.present_creatures(state, arrive - walk - 550.0, 0.05)
	stage.present_armies(state, arrive - walk - 500.0)
	var glade := glade_value(stage, at)
	var beside := glade_value(stage, at + Vector3(14.0, 0.0, 0.0))
	check(stage.creature_clear.size() == 1 and glade >= 250, "the world creature stands in a glade of faded crowns: mask %d" % glade)
	check(beside == 0, "the glade is the creature's own: 14 m away the mask is %d" % beside)
	notes.glade = {"radius_m": snappedf(stage.creature_clear[0].z, 0.01) if not stage.creature_clear.is_empty() else 0.0,
		"mask_size_m": snappedf(stage.march_clear_area.z, 0.1), "mask_px": int(sqrt(float(stage.march_clear_bytes.size())))}
	var swings := {}
	var health_frames := 0
	var engaged_seen := 0
	var t := arrive - 5000.0
	var house_top := 0.0
	for site in game.data.sites.slice(0, 8):
		for part in site.parts:
			if part.key == "house":
				house_top = maxf(house_top, 4.742 * float(part.scale))
	# The battle is not known until arrive + 4 s (the army is still "outbound").
	while t < arrive + 4000.0:
		stage.present_armies(state, t)
		stage.present_creatures(state, t, 0.05)
		var actor: Node3D = stage.actors.get_node_or_null("qa-late")
		if actor != null and t > arrive - 500.0:
			for unit in actor.get_children():
				if not unit is Node3D or unit.name == &"Ferry":
					continue
				if unit.get_meta("clip", "") == "attack":
					var key := String(unit.name)
					var at_ms := float(unit.get_meta("ambient_strike", -INF))
					if at_ms > -INF:
						if not swings.has(key): swings[key] = {}
						swings[key][roundi(at_ms)] = true
				engaged_seen += 1
		if t > arrive - 500.0:
			for node in stage.battle_fx.get_children():
				if node is Label3D and node.visible and " · " in node.text:
					health_frames += 1
					break
		await process_frame
		t += 50.0
	var swinging := swings.keys().size()
	var counts: Array = swings.values().map(func(d): return d.size())
	check(swinging >= 10, "soldiers swing while the battle is not yet known: %d soldiers" % swinging)
	check(not counts.is_empty() and counts.max() >= 2, "several swings each in the wait: most %s" % [str(counts.max()) if not counts.is_empty() else "0"])
	var actor: Node3D = stage.actors.get_node_or_null("qa-late")
	var tallest := 0.0
	if actor != null:
		for unit in actor.get_children():
			if unit is Node3D and unit.name != &"Ferry":
				check(is_equal_approx(unit.scale.y, 0.5) or unit.basis.get_scale().y < 0.51, "a world soldier is drawn at 0.5")
				break
	var beast: Node3D = stage.creatures.get_node_or_null(str(enc.id))
	check(beast != null and absf(beast.scale.x - stage.creature_scale(1) * 0.6) < 0.01, "the world creature at 0.6 of its city size")
	check(health_frames >= 60, "the creature shows its health from the start of the fight: %d frames" % health_frames)
	notes.engaging = {"soldiers_swinging": swinging, "swings_each": counts, "health_frames": health_frames, "house_top_m": snappedf(house_top, 0.01)}
	await ferry_rows()
	town_plan_cache()
	print(JSON.stringify({"checks": checks, "failures": failures, "notes": notes,
		"method": "headless Linux, presentation clock and real Landscape; not iPhone acceptance"}))
	quit(0 if failures.is_empty() else 1)
