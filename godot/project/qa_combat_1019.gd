extends SceneTree

# Build 1019 regression checks for the combat presentation fixes (headless, real
# Landscape of the main scene, synthetic server-shaped data):
#  1. blows are spread over free drawn soldiers of their type, reserves in reach
#     swing, no shown swing is cut, decisions survive later polls;
#  2. the shown clock never stands still or jumps when the response cadence
#     changes during a march, and keeps its delay during a fight;
#  3. a column follows its route row by row (no rigid swing at a corner) and the
#     charge starts exactly where each soldier stands at the halt;
#  4. a formation stays drawn while its anchor is off screen but soldiers are not;
#  5. creature reactions are not restarted by every blow;
#  6. diagnostics: bounded log, a report with frame statistics.
# Not iPhone acceptance.

const Clock = preload("res://src/combat_presentation.gd")
const Diagnostics = preload("res://src/combat_diagnostics.gd")
var checks := 0
var failures: Array[String] = []

func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures.append(message)
		push_error(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	var stage = game.stage
	strikes(stage)
	clock()
	reactions(stage)
	await column(game, stage)
	diagnostics(game)
	print(JSON.stringify({"checks": checks, "failures": failures, "method": "headless Linux, real Landscape, synthetic events; not iPhone acceptance"}))
	game.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)

# --- 1. strike assignment -------------------------------------------------------
func strikes(stage) -> void:
	var slots: Array = []
	for i in 6:
		slots.append({"id": "ENG-05", "index": i, "ranged": false, "mounted": true})
	for i in 4:
		slots.append({"id": "ENG-01", "index": i, "ranged": false, "mounted": false})
	# One rider in contact, four in the first reserve row, one far away (row 3).
	var plan := {"reserves": {"ENG-05:1": true, "ENG-05:2": true, "ENG-05:3": true, "ENG-05:4": true, "ENG-05:5": true},
		"reserve_rows": {"ENG-05:1": 1, "ENG-05:2": 1, "ENG-05:3": 1, "ENG-05:4": 1, "ENG-05:5": 3}}
	var events: Array = []
	# 11 server riders strike four times each, all within 3.2 s; spearmen too.
	for round in 4:
		for member in 11:
			events.append([float(round * 900 + member * 30), "soldier_attack", "ENG-05", member, 1000.0])
		for member in 8:
			events.append([float(round * 900 + member * 40 + 10), "soldier_attack", "ENG-01", member, 1000.0])
	events.append([500.0, "creature_attack", "ENG-05", 4, 0])
	events.sort_custom(func(a, b): return a[0] < b[0])
	var memo := {}
	var army := {"id": "qa-strikes", "battle": {"events": events}}
	var result: Dictionary = stage.battle_events(army, slots, plan, memo)
	var members: Dictionary = result.members
	var riders := 0
	for key in members:
		if key.begins_with("ENG-05") and members[key].any(func(e): return e[1] == "soldier_attack"):
			riders += 1
	check(riders >= 5, "cavalry blows shown by %d riders, expected the contact rider and the first reserve row" % riders)
	# The far rider (no room within reach) takes a blow only when the nearer riders are busy.
	var first_round: Array = []
	for key in members:
		for e in members[key]:
			if e[1] == "soldier_attack" and e[2] == "ENG-05" and float(e[0]) < 200.0:
				first_round.append([float(e[0]), key])
	first_round.sort()
	var nearer_first := first_round.size() >= 5 and first_round.slice(0, 5).all(func(item): return item[1] != "ENG-05:5")
	check(nearer_first, "far reserve rider took a blow while a nearer rider was free: " + str(first_round.slice(0, 6)))
	check(result.far.has("ENG-05:5") and not result.far.has("ENG-05:1"), "far reserves not marked")
	check(members.get("ENG-05:4", []).any(func(e): return e[1] == "creature_attack"), "the creature's blow left its own member")
	var cut := 0
	for key in members:
		var window: Vector2 = result.windows[key.get_slice(":", 0)]
		var times: Array = members[key].filter(func(e): return e[1] == "soldier_attack").map(func(e): return float(e[0]))
		for n in range(1, times.size()):
			if times[n] - window.x < times[n - 1] + stage.MIN_FOLLOW_MS:
				cut += 1
	check(cut == 0, "%d shown swings would cut the previous windup/contact" % cut)
	var shown := 0
	for key in members:
		shown += members[key].filter(func(e): return e[1] == "soldier_attack").size()
	var server := events.filter(func(e): return e[1] == "soldier_attack").size()
	check(shown > server * 0.35, "shown %d of %d blows" % [shown, server])
	# A later poll adds blows: earlier decisions do not move.
	var before := {}
	for key in members:
		for e in members[key]:
			before["%s|%s|%d" % [e[0], e[2], e[3]]] = key
	var more: Array = events.duplicate()
	for member in 11:
		more.append([3600.0 + member * 30, "soldier_attack", "ENG-05", member, 1000.0])
	var later: Dictionary = stage.battle_events({"id": "qa-strikes", "battle": {"events": more}}, slots, plan, memo).members
	var moved := 0
	for key in later:
		for e in later[key]:
			var id := "%s|%s|%d" % [e[0], e[2], e[3]]
			if before.has(id) and before[id] != key:
				moved += 1
	check(moved == 0, "%d blows moved to another soldier after a later poll" % moved)
	# A type whose every drawn soldier is far in reserve still swings.
	var far := {"reserves": {}, "reserve_rows": {}}
	for i in 6:
		far.reserves["ENG-05:%d" % i] = true
		far.reserve_rows["ENG-05:%d" % i] = 3
	var forced: Dictionary = stage.battle_events(army, slots, far, {})
	check(not forced.forced.is_empty() and not forced.strikers.is_empty(), "a type with only far reserves stands idle")

# --- 2. presentation clock -------------------------------------------------------
func clock() -> void:
	var view = Clock.new()
	var army := {"id": "march", "target": "beast", "status": "outbound", "units": {"ENG-01": 1}, "startsAt": 0.0, "arrivesAt": 120000.0}
	var now := 1000.0
	var poll := now
	var gap := 900.0
	var previous := -INF
	var stood := 0.0
	var fastest := 0.0
	var delays: Array = []
	for frame in 4000:
		now += 16.0
		if now >= poll:
			# Cadence worsens to 3 s gaps half-way: the delay has to grow.
			gap = 900.0 if frame < 1500 else 3000.0
			poll = now + gap
			view.frame({"playerId": "qa", "serverTime": now, "armies": [army], "encounters": []}, now, "city")
		else:
			view.frame({"playerId": "qa", "serverTime": poll - gap, "armies": [army], "encounters": []}, now, "city")
		if previous > -INF:
			var advanced: float = view.frame_time - previous
			if advanced <= 0.0:
				stood += 16.0
			fastest = maxf(fastest, advanced / 16.0)
		previous = view.frame_time
		delays.append(view.delay_ms)
	check(delays[-1] > 3000.0, "delay did not follow the slower cadence (%.0f ms)" % delays[-1])
	check(stood <= 32.0, "march stood still for %.0f ms while the delay changed" % stood)
	check(fastest <= 1.1, "march ran %.2fx while the delay changed" % fastest)
	var steps := 0
	for n in range(1, delays.size()):
		if absf(delays[n] - delays[n - 1]) > 16.0 * 0.15 + 0.01:
			steps += 1
	check(steps == 0, "delay changed faster than the slew %d times" % steps)
	# During a fight on screen the delay stays.
	var fight = Clock.new()
	var row := {"id": "fight", "target": "beast", "status": "fighting", "units": {"ENG-01": 1}, "startsAt": 0.0, "arrivesAt": 3000.0,
		"battleAt": 3000.0, "battleEndsAt": 60000.0, "battle": {"events": [[0.0, "soldier_attack", "ENG-01", 0, 10.0]]}}
	var t := 5000.0
	var p := t
	var held: Array = []
	for frame in 2000:
		t += 16.0
		if t >= p:
			p = t + (900.0 if frame < 600 else 3000.0)
		fight.frame({"playerId": "qa", "serverTime": p - (900.0 if frame < 600 else 3000.0), "armies": [row], "encounters": []}, t, "city")
		if fight.fight_on_screen:
			held.append(fight.delay_ms)
	check(not held.is_empty() and held.max() - held.min() < 0.01, "delay changed during a fight on screen")

# --- 5. creature reactions -------------------------------------------------------
func reactions(stage) -> void:
	var events: Array = []
	for k in 40:
		events.append([float(k * 90), "soldier_attack", "ENG-03", k % 6, 5000.0 - k * 10])
	var timeline: Dictionary = stage.battle_timeline({"id": "qa-reactions"}, {"spec": {"hp": 5000}}, events)
	var starts: Array = timeline.reactions.map(func(r): return float(r[0]))
	var close := 0
	for n in range(1, starts.size()):
		if starts[n] - starts[n - 1] < stage.REACTION_GAP_MS:
			close += 1
	check(close == 0 and starts.size() >= 8, "creature reactions restart too often (%d starts, %d too close)" % [starts.size(), close])

# --- 3/4. column, charge and visibility ------------------------------------------
func column(game, stage) -> void:
	var state: Dictionary = game.state.duplicate(true)
	var target: Dictionary = state.encounters[0]
	target.patrol = []
	target.level = 2
	target.status = "reserved"
	target.spec = {"hp": 1400, "name": "Тенерис"}
	var beast: Vector3 = stage.ground_point(stage.point(target.position))
	# An L-shaped route: 30 m one way, a right angle, then to the creature.
	var corner := beast + Vector3(-28, 0, 0)
	var home := corner + Vector3(0, 0, -30)
	var path := []
	for k in 16:
		var q := home.lerp(corner, k / 15.0)
		path.append({"x": q.x, "z": q.z})
	for k in range(1, 15):
		var q := corner.lerp(beast, k / 14.0)
		path.append({"x": q.x, "z": q.z})
	var start := 900000.0
	var arrive := start + 30000.0
	var army := {"id": "qa-column", "status": "outbound", "target": target.id, "path": path,
		"units": {"ENG-01": 8, "ENG-02": 8, "ENG-03": 6, "ENG-05": 2}, "startsAt": start, "arrivesAt": arrive, "owner": state.get("playerId", "")}
	state.armies = [army]
	state.encounters = [target]
	stage.engage_sync = true
	stage.target = corner
	stage.zoom = 70.0
	stage.update_camera(0, true)
	# Let the soldiers be created.
	for i in 30:
		stage.present_armies(state, start + 1000.0)
		await process_frame
	var actor: Node3D = stage.actors.get_node_or_null("qa-column")
	check(actor != null and actor.get_child_count() >= 20, "column not drawn")
	if actor == null:
		return
	# Walk through the corner in 50 ms steps: the fastest soldier speed stays near the march speed.
	var speed := (float(stage.army_routes["qa-column"].distances[-1]) / 30.0)
	var last := {}
	var worst := 0.0
	var plan: Dictionary = stage.army_routes["qa-column"].get("engage", {})
	var halt_at := float(plan.get("halt_at", arrive))
	var t := start + 2000.0
	while t < halt_at - 200.0:
		stage.present_armies(state, t)
		for unit in actor.get_children():
			if unit is Node3D and unit.name != &"Ferry":
				var at: Vector3 = unit.global_position
				if last.has(unit.name):
					worst = maxf(worst, Vector2(at.x - last[unit.name].x, at.z - last[unit.name].z).length() / 0.05)
				last[unit.name] = at
		t += 50.0
	# A row wheels round the corner: its outer rider (3.6 m off the axis) goes about
	# twice the column speed. Build 1018 swung the rear rows about 100x faster.
	check(worst < speed * 2.5, "a soldier moved %.1f m/s at the corner (march %.1f m/s)" % [worst, speed])
	# The charge starts where each soldier stands at the halt.
	stage.present_armies(state, halt_at - 1.0)
	var at_halt := {}
	for unit in actor.get_children():
		if unit is Node3D and unit.name != &"Ferry":
			at_halt[unit.name] = unit.global_position
	stage.present_armies(state, halt_at + 16.0)
	var jump := 0.0
	for unit in actor.get_children():
		if unit is Node3D and at_halt.has(unit.name):
			jump = maxf(jump, unit.global_position.distance_to(at_halt[unit.name]))
	check(jump < 0.6, "a soldier jumped %.2f m when the charge started" % jump)
	# Anchor off screen, soldiers (and the battle places) still on screen: drawn.
	stage.target = beast + Vector3(0, 0, 14)
	stage.zoom = 24.0
	stage.update_camera(0, true)
	stage.present_armies(state, halt_at + 3000.0)
	var anchor_in: bool = stage.camera.is_position_in_frustum(actor.global_position + Vector3.UP)
	var on_screen := 0
	for unit in actor.get_children():
		if unit is Node3D and stage.camera.is_position_in_frustum(unit.global_position + Vector3.UP):
			on_screen += 1
	check(anchor_in or on_screen == 0 or actor.visible, "formation hidden with %d soldiers on screen" % on_screen)
	stage.engage_sync = false

# --- 6. diagnostics ---------------------------------------------------------------
func diagnostics(game) -> void:
	var diag = Diagnostics.new()
	game.add_child(diag)
	for i in Diagnostics.LOG_LIMIT + 250:
		diag.note("qa", {"n": i})
	var log: Array = diag.ordered_log()
	check(log.size() == Diagnostics.LOG_LIMIT, "diagnostic log is not bounded (%d)" % log.size())
	check(int(log[-1].n) == Diagnostics.LOG_LIMIT + 249 and int(log[0].n) == 250, "diagnostic log lost its order")
	for i in 50:
		diag.frame(game, 1200)
	var report: Dictionary = diag.report()
	check(report.has("frames") and report.frames.frames > 0 and report.has("log") and report.kind == "drenovar-combat-diagnostics", "diagnostic report incomplete")
	check(JSON.stringify(report).length() < 400000, "diagnostic report too large")
	diag.queue_free()
