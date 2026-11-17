extends SceneTree

# Build 1020 regression checks: the hunt is one crowd fighting continuously.
# Headless, real Landscape of the main scene, offline (unreachable endpoint), the
# server simulator's own output (tests/combat_v010/server_combat_cases.json):
#  1. battle places: the whole party in one crowd around the creature, riders
#     spread among the foot, archers mixed in the next ring (no rows per type);
#  2. ambient swings: a pure function of member and clock, never before the
#     soldier stands at its place, never past the creature's fall, never over a
#     server blow of that soldier, phases spread over the crowd;
#  3. clips: sword/spear/heavy/rider/crossbow fight with the models' authored
#     Attack (the wrist reaches forward at the contact time) and Idle stance;
#  4. the creature's swipes between server attacks are deterministic, keep clear
#     of server attacks and land on shield bearers in front of it;
#  5. in the scene: every melee soldier at the creature swings again and again
#     through the shown fight, a swiped soldier raises its shield, the creature
#     swipes, trees on the crowd's ground do not push riders out of the crowd.
# Not iPhone acceptance.

const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const Clock = preload("res://src/combat_presentation.gd")
var checks := 0
var failures: Array[String] = []
var notes := {}

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
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	await game.show_scene("world")
	CombatV010.set_enabled(true)
	var stage = game.stage
	crowd(stage)
	ambient(stage)
	clips(stage)
	await scene(game, stage)
	print(JSON.stringify({"checks": checks, "failures": failures, "notes": notes, "method": "headless Linux, real Landscape, server simulator events; not iPhone acceptance"}))
	game.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)

# --- 1. battle places -------------------------------------------------------------
func crowd(stage) -> void:
	var slots: Array = []
	var origins := {}
	var kinds := [["ENG-01", 3, false, false], ["ENG-02", 4, false, false], ["ENG-09", 2, false, false],
		["ENG-05", 3, true, false], ["ENG-06", 2, true, false], ["ENG-03", 4, false, true], ["ENG-04", 3, false, true], ["ENG-10", 3, false, true]]
	var row := 0
	for kind in kinds:
		for index in int(kind[1]):
			slots.append({"id": kind[0], "index": index, "mounted": kind[2], "ranged": kind[3]})
			# A column behind the creature's face (+x), rows going back.
			origins["%s:%d" % [kind[0], index]] = Vector2(6.0 + row * 0.6, (index % 5 - 2) * 1.45)
		row += 1
	var body := Vector2(2.96, 1.40)
	var places: Dictionary = stage.crowd_places(slots, origins, body)
	check(places.size() == slots.size(), "every member has a battle place: %d of %d" % [places.size(), slots.size()])
	check(JSON.stringify(stage.crowd_places(slots, origins, body)) == JSON.stringify(places), "battle places are deterministic")
	var outline := func(q: Vector2) -> float:
		var n := q.normalized()
		return q.length() - 1.0 / sqrt(pow(n.x / body.x, 2) + pow(n.y / body.y, 2))
	var melee_angles: Array = []
	var melee_near: Array = []
	var kind_at := {}
	var melee_out := 0.0
	var archer_out := INF
	for slot in slots:
		var key := "%s:%d" % [slot.id, int(slot.index)]
		var q: Vector2 = places[key]
		var angle := rad_to_deg(atan2(q.y, q.x))
		if slot.ranged:
			archer_out = minf(archer_out, outline.call(q))
		else:
			melee_angles.append(angle)
			kind_at[angle] = "r" if slot.mounted else "f"
			melee_out = maxf(melee_out, outline.call(q) - (1.3 if slot.mounted else 0.0))
			melee_near.append(outline.call(q) - (1.3 if slot.mounted else 0.0))
	melee_angles.sort()
	# All round: melee in front of, beside and behind the creature.
	check(melee_angles.any(func(a): return absf(a) < 35.0) and melee_angles.any(func(a): return absf(a) > 140.0)
		and melee_angles.any(func(a): return a > 60.0 and a < 120.0) and melee_angles.any(func(a): return a < -60.0 and a > -120.0),
		"melee surrounds the creature: " + str(melee_angles))
	var largest_gap: float = 360.0 - float(melee_angles[-1]) + float(melee_angles[0])
	for n in range(1, melee_angles.size()):
		largest_gap = maxf(largest_gap, melee_angles[n] - melee_angles[n - 1])
	check(largest_gap < 75.0, "no side of the creature is left empty: largest gap %.0f deg" % largest_gap)
	# Riders spread among the foot: never two riders side by side round the ring.
	var adjacent := 0
	for n in melee_angles.size():
		if kind_at[melee_angles[n]] == "r" and kind_at[melee_angles[(n + 1) % melee_angles.size()]] == "r":
			adjacent += 1
	check(adjacent == 0, "riders stand among the foot, %d rider pairs side by side" % adjacent)
	melee_near.sort()
	# One ring at the body (1.15 m out); what does not fit there stands one rank behind.
	check(float(melee_near[melee_near.size() / 2]) < 1.6 and melee_out < 3.2, "melee hugs the creature: median %.2f m, farthest %.2f m from its outline" % [melee_near[melee_near.size() / 2], melee_out])
	check(archer_out > melee_out + 0.8 and archer_out < 5.5, "archers one ring out, among the crowd: %.2f m (melee %.2f m)" % [archer_out, melee_out])
	var archer_angles: Array = []
	var archer_radii: Array = []
	for slot in slots:
		if slot.ranged:
			var q: Vector2 = places["%s:%d" % [slot.id, int(slot.index)]]
			archer_angles.append(rad_to_deg(atan2(q.y, q.x)))
			archer_radii.append(snappedf(outline.call(q), 0.05))
	archer_angles.sort()
	check(archer_angles[-1] - archer_angles[0] > 200.0, "archers spread round the crowd, not a line behind it: " + str(archer_angles))
	var radii := {}
	for r in archer_radii: radii[r] = true
	check(radii.size() >= archer_radii.size() / 2, "archers not on one line: " + str(archer_radii))
	var closest := INF
	var keys: Array = places.keys()
	for a in keys.size():
		for b in range(a + 1, keys.size()):
			closest = minf(closest, (places[keys[a]] as Vector2).distance_to(places[keys[b]]))
	check(closest > 0.85, "no two places on top of each other: %.2f m" % closest)
	notes.crowd = {"largest_gap_deg": snappedf(largest_gap, 1.0), "melee_from_outline_m": snappedf(melee_out, 0.01), "archers_from_outline_m": snappedf(archer_out, 0.01)}

# --- 2. ambient swings ----------------------------------------------------------
func ambient(stage) -> void:
	var window := Vector2(470.0, 530.0)
	var first := {}
	var counts: Array = []
	for n in 24:
		var key := "ENG-0%d:%d" % [1 + n % 9, n]
		var contacts := {}
		var before_from := 0
		var after_until := 0
		for t in range(-1000, 9600, 25):
			var c: float = stage.ambient_strike(key, float(t), 800.0, 9000.0, window, 0.0, [])
			if c > -INF:
				contacts[c] = true
				if c - window.x < 800.0: before_from += 1
				if c > 9000.0 - 120.0: after_until += 1
				check(float(t) >= c - window.x and float(t) <= c + window.y, "%s: elapsed %d outside its swing %.0f" % [key, t, c])
		check(before_from == 0 and after_until == 0, "%s swings outside [arrival, fall]: %d / %d" % [key, before_from, after_until])
		counts.append(contacts.size())
		var sorted: Array = contacts.keys(); sorted.sort()
		if not sorted.is_empty(): first[snappedf(fposmod(sorted[0], 1000.0), 50.0)] = true
		check(stage.ambient_strike(key, 4321.0, 800.0, 9000.0, window, 0.0, []) == stage.ambient_strike(key, 4321.0, 800.0, 9000.0, window, 0.0, []), "ambient swing not a pure function")
	counts.sort()
	check(int(counts[0]) >= 4, "every soldier swings again and again in a 9 s fight: fewest %d" % counts[0])
	check(first.size() >= 8, "swing phases spread over the crowd: %d distinct" % first.size())
	# A server blow of this soldier keeps its windup, contact and follow-through clear.
	var own := [3000.0, 6100.0]
	for t in range(0, 9000, 10):
		var c: float = stage.ambient_strike("ENG-02:7", float(t), 0.0, 9000.0, window, 0.0, own)
		if c > -INF:
			for at in own:
				check(c + window.y + stage.MIN_FOLLOW_MS <= at - window.x or c - window.x >= at + window.y + stage.MIN_FOLLOW_MS,
					"ambient swing %.0f overlaps the server blow %.0f" % [c, at])
	# The crossbow's reload is part of its busy span.
	var reload_seen := false
	for t in range(0, 9000, 20):
		var c: float = stage.ambient_strike("ENG-04:1", float(t), 0.0, 9000.0, Vector2(760.0, 240.0), 2000.0, [])
		if c > -INF and float(t) > c + 240.0: reload_seen = true
	check(reload_seen, "crossbow reload span is reported")
	notes.ambient_swings_in_9s = [counts[0], counts[-1]]

# --- 3. clips -----------------------------------------------------------------------
func clips(stage) -> void:
	var parent := Node3D.new()
	stage.add_child(parent)
	for id in ["ENG-01", "ENG-02", "ENG-05", "ENG-04", "ENG-03", "ENG-10"]:
		while not CombatV010.ready_for("troop", id):
			OS.delay_msec(5)
		var unit: Node3D = stage.add_warrior(parent, stage.data.unitModels[id].field, Transform3D.IDENTITY)
		check(CombatV010.install(unit, "troop", id), id + " not installed")
		var info: Dictionary = CombatV010.info(unit)
		var window: Vector2 = CombatV010.attack_window(unit, 0.0)
		check(CombatV010.strike_window(id, info.ranged).distance_to(window) < 1.0, "%s: strike window before creation %s != installed %s" % [id, CombatV010.strike_window(id, info.ranged), window])
		var player: AnimationPlayer = info.player
		if id in ["ENG-01", "ENG-02", "ENG-05", "ENG-04"]:
			check(info.clips.get(&"attack_a") == &"Attack" and info.clips.get(&"idle") == &"Idle", id + " does not fight with its authored Attack/Idle: " + str(info.clips))
		else:
			check(info.clips.is_empty(), id + " should keep the library clips: " + str(info.clips))
		if id in ["ENG-01", "ENG-02"]:
			check(info.clips.get(&"block") == &"Shield_Block", id + " has no shield block")
		if id == "ENG-04":
			check(absf(float(info.reload_ms) - 2000.0) < 1.0 and absf(window.x - 760.0) < 1.0, "crossbow: release 0.5 s + flight, reload 2 s: %s %s" % [window, info.get("reload_ms")])
		if id in ["ENG-01", "ENG-02", "ENG-05"]:
			# The wrist is forward of its stance at the contact time (the authored blow).
			var skeleton: Skeleton3D = unit.find_children("*", "Skeleton3D", true, false)[0]
			var wrist := skeleton.find_bone("wrist.R")
			var reach := func(clip: StringName, at: float) -> Vector3:
				# The presenter's mapping, played without a blend (a blend would still
				# show the previous clip in this same frame).
				player.play(CombatV010.animation_name(info, clip))
				player.seek(at, true)
				skeleton.force_update_all_bone_transforms()
				return skeleton.get_bone_global_pose(wrist).origin
			var guard: Vector3 = reach.call(&"idle", 0.0)
			var start: Vector3 = reach.call(&"attack_a", 0.0)
			var contact: Vector3 = reach.call(&"attack_a", window.x / 1000.0)
			check(contact.z - start.z > 0.1, "%s: wrist not forward at contact (%.2f -> %.2f)" % [id, start.z, contact.z])
			if id == "ENG-02":
				# Build 1019's stance held the blade level behind the shoulder (wrist 1.15 m).
				check(guard.y < 1.0, "%s stance holds the arm raised: wrist %.2f m" % [id, guard.y])
			notes[id + "_wrist_forward_at_contact_m"] = snappedf(contact.z - start.z, 0.01)
	parent.free()

# --- 4/5. the fight in the scene ------------------------------------------------------
func scene(game, stage) -> void:
	var cases := {}
	for c in JSON.parse_string(FileAccess.get_file_as_string("res://tests/combat_v010/server_combat_cases.json")).cases:
		cases[c.name] = c
	var mixed: Dictionary = cases.mixed_all_types_velkor
	var state: Dictionary = game.state.duplicate(true)
	var enc: Dictionary = state.world.encounters[0]
	enc.patrol = []
	enc.position = {"x": -50.0, "z": -30.0}
	enc.level = int(mixed.level)
	var at: Vector3 = stage.point(enc.position)
	var start := 300000.0
	var walk := 20000.0
	var army := {"id": "qa-crowd", "status": "outbound", "target": enc.id, "worldKind": "creature",
		"path": [{"x": at.x - 30.0, "z": at.z + 26.0}, {"x": at.x - 12.0, "z": at.z + 8.0}, {"x": at.x, "z": at.z}],
		"units": mixed.party.duplicate(), "startsAt": start - walk, "arrivesAt": start, "battleAt": start,
		"battleEndsAt": start + float(mixed.result.duration), "battle": {"events": mixed.result.events.duplicate(true)}, "fallen": [],
		"returnStartsAt": start + float(mixed.result.duration), "returnsAt": start + float(mixed.result.duration) + walk}
	Clock.stretch(army, {})
	var ends := float(army.battleEndsAt)
	stage.engage_sync = true
	stage.target = at
	stage.zoom = 30.0
	stage.update_camera(0, true)
	var swings := {}
	var attack_frames := 0
	var engaged_frames := 0
	var blocks := {}
	var beast_attacks := {}
	var creature: Node3D = null
	var t := start - 4000.0
	while t < ends:
		var shown: Dictionary = army.duplicate(true)
		shown.status = "outbound" if t < start else "fighting"
		enc.status = "alive" if t < start else "fighting"
		state.world.armies = [shown]
		stage.present_armies(state, t)
		stage.present_creatures(state, t, 0.05)
		if t >= start + 1500.0:
			var actor: Node3D = stage.actors.get_node_or_null("qa-crowd")
			var plan: Dictionary = stage.army_routes["qa-crowd"].get("engage", {})
			for unit in (actor.get_children() if actor != null else []):
				if not unit is Node3D or unit.name == &"Ferry":
					continue
				var key := String(unit.name).replace("_", ":")
				if key.begins_with("ENG-03") or key.begins_with("ENG-04") or key.begins_with("ENG-10") or plan.get("reserve_rows", {}).get(key, 0) >= 3:
					continue
				engaged_frames += 1
				var clip: String = unit.get_meta("clip", "")
				if clip == "attack":
					attack_frames += 1
					var shown_at: float = unit.get_meta("ambient_strike", -INF) if float(unit.get_meta("v010_strike", -INF)) == -INF else float(unit.get_meta("v010_strike"))
					if not swings.has(key): swings[key] = {}
					swings[key][shown_at] = true
				elif clip == "block":
					blocks[key] = true
			if creature == null:
				creature = stage.creatures.get_node_or_null(NodePath(str(enc.id)))
			if creature != null and creature.get_meta("clip", "") == "Attack":
				beast_attacks[snappedf(t - start, 500.0)] = true
		t += 50.0
	var cache: Dictionary = stage.army_routes.get("qa-crowd", {})
	var plan: Dictionary = cache.get("engage", {})
	var melee := 0
	var fewest := 1000
	for slot in cache.get("slots", []):
		var key := "%s:%d" % [slot.id, int(slot.index)]
		if slot.ranged or int(plan.reserve_rows.get(key, 0)) >= 3:
			continue
		melee += 1
		fewest = mini(fewest, swings.get(key, {}).size())
	check(melee >= 10, "melee soldiers at the creature: %d" % melee)
	check(fewest >= 3, "every melee soldier at the creature swings at least 3 times in the shown fight: fewest %d" % fewest)
	var share := float(attack_frames) / maxf(1.0, engaged_frames)
	check(share > 0.45, "the crowd is mostly mid-blow, not standing: %.0f %% of soldier frames" % (share * 100.0))
	var riders_far := 0
	for slot in cache.get("slots", []):
		if slot.mounted and int(plan.reserve_rows.get("%s:%d" % [slot.id, int(slot.index)], 0)) >= 3:
			riders_far += 1
	check(riders_far == 0, "riders kept out of the crowd (far reserves): %d" % riders_far)
	# Trees on the crowd's ground are no obstacle (they are cleared for the fight).
	var centre := Vector2(plan.beast.x, plan.beast.z)
	var trees_in: Array = plan.slot_solver.debug_obstacles.filter(func(o): return o.proxy and Vector2(o.transform.origin.x, o.transform.origin.z).distance_to(centre) < float(plan.clear))
	check(float(plan.get("clear", 0.0)) > 5.0 and trees_in.is_empty(), "cleared ground %.1f m, tree obstacles inside: %d" % [plan.get("clear", 0.0), trees_in.size()])
	var feints: Array = cache.get("feints", [])
	check(not feints.is_empty(), "the creature swipes between its server attacks")
	var server_creature: Array = mixed.result.events.filter(func(e): return e.kind != "soldier_attack").map(func(e): return float(e.at) * float(army.get("stretched", 1.0)))
	for feint in feints:
		check(not server_creature.any(func(s): return absf(s - float(feint.at)) < stage.FEINT_CLEAR_MS - 400.0), "swipe %.0f too close to a server creature attack" % feint.at)
		check(str(feint.target).get_slice(":", 0) in ["ENG-01", "ENG-02", "ENG-07", "ENG-08", "ENG-09"], "swipe at a soldier without a shield: " + str(feint.target))
	check(blocks.size() >= 1, "a swiped soldier raises its shield: %s" % str(blocks.keys()))
	check(beast_attacks.size() >= 2, "the creature strikes during the fight: %s" % str(beast_attacks.keys()))
	stage.engage_sync = false
	notes.scene = {"melee_at_creature": melee, "fewest_swings": fewest, "mid_blow_share": snappedf(share, 0.01), "riders_far": riders_far,
		"feints": feints.size(), "blocks": blocks.size(), "creature_attack_moments": beast_attacks.size(), "clear_m": snappedf(float(plan.get("clear", 0.0)), 0.1),
		"shown_fight_ms": ends - start}
