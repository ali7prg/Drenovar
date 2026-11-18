extends SceneTree

# Combat v0.1.0 presenter lifecycle on the real landscape, fed with real output of
# the server's deterministic simulator (tests/combat_v010/server_combat_cases.json,
# server snapshot 365276cc, synthetic armies, no player data). Offline: the game
# runs on an unreachable loopback endpoint and never talks to a server.
#
#   godot --headless --path godot/project -s qa_combat_v010.gd
#
# Covers: hand-over to the new library for every soldier type and the creature,
# one shared read-only library per type, single pose owner, contact/release phase
# at event.at, repeated snapshot / rewind do not restart a swing, death in a
# windup, late join after a death, presenter never mutates the state, and the
# rollback switch (flag off) returns every actor to the legacy clips.

const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const Registry = preload("res://combat_v010/runtime/combat_v010_registry.gd")

var checks := 0
var failures := 0
var notes := []

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func player_of(unit: Node3D) -> AnimationPlayer:
	return unit.find_children("*", "AnimationPlayer", true, false)[0]

func soldiers(stage, id: String) -> Array:
	var actor: Node3D = stage.actors.get_node_or_null(NodePath(id))
	return [] if actor == null else actor.get_children().filter(func(n): return n is Node3D and n.name != &"Ferry" and n.name != &"Arrow")

func make_army(id: String, at: Vector3, enc: Dictionary, case: Dictionary, start: float) -> Dictionary:
	return {"id": id, "status": "fighting", "target": enc.id, "worldKind": "creature",
		"path": [{"x": at.x - 16, "z": at.z + 2}, {"x": at.x, "z": at.z}],
		"units": case.party.duplicate(), "startsAt": start - 20000, "arrivesAt": start, "battleAt": start,
		"battleEndsAt": start + float(case.result.duration), "battle": {"events": case.result.events.duplicate(true)}, "fallen": []}

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	await game.show_scene("world")
	var stage = game.stage
	var cases := {}
	for c in JSON.parse_string(FileAccess.get_file_as_string("res://tests/combat_v010/server_combat_cases.json")).cases:
		cases[c.name] = c
	CombatV010.set_enabled(true)
	var generation_on := CombatV010.generation

	# ---- mixed party of all ten types against Velkor ----------------------
	var state: Dictionary = game.state.duplicate(true)
	var enc: Dictionary = state.world.encounters[0]
	enc.patrol = []
	enc.position = {"x": -28.0, "z": -54.0}
	enc.level = int(cases.mixed_all_types_velkor.level)
	var at: Vector3 = stage.point(enc.position)
	var start := 100000.0
	var mixed: Dictionary = cases.mixed_all_types_velkor
	state.world.armies = [make_army("army-v010", at, enc, mixed, start)]
	stage.target = at
	stage.zoom = 46.0
	stage.update_camera(0, true)
	var before := JSON.stringify(state)
	var t := start + 200.0
	for frame in 90:
		stage.present_armies(state, t)
		stage.present_creatures(state, t, 0.016)
		await process_frame
	var units := soldiers(stage, "army-v010")
	check(units.size() == 24, "Soldiers on the field: %d" % units.size())
	var owned := units.filter(func(u): return CombatV010.owns(u))
	check(owned.size() == units.size(), "Soldiers handed to v0.1.0: %d of %d" % [owned.size(), units.size()])
	var types := {}
	var shared := {}
	var single_owner := true
	for unit: Node3D in owned:
		var id := String(unit.name).get_slice("_", 0)
		types[id] = true
		var library: AnimationLibrary = player_of(unit).get_animation_library(Registry.NAMESPACE)
		if shared.has(id):
			check(shared[id] == library, "%s instances do not share one library resource" % id)
		shared[id] = library
		# The presenter's clips only: the library's, or the model's own authored
		# Attack/Idle that the presenter maps for SOURCE_FIGHT families (build 1020).
		var playing := StringName(player_of(unit).assigned_animation)
		if not str(playing).begins_with("combat_v010/") and not CombatV010.info(unit).get("clips", {}).values().has(playing):
			single_owner = false
	check(types.size() == 10, "All ten troop types on the field: %s" % str(types.keys()))
	check(single_owner, "A v0.1.0 soldier plays a legacy clip (two pose owners)")
	var creature: Node3D = stage.creatures.get_node_or_null(NodePath(enc.id))
	check(creature != null and CombatV010.owns(creature), "Creature not handed to v0.1.0")

	# Contact / release phase at event.at for soldiers whose swing is unambiguous.
	var events: Array = mixed.result.events
	var verified := 0
	var skipped := 0
	for e in events:
		if e.kind != "soldier_attack":
			continue
		# The drawn soldier that shows this server strike (members without a model lend theirs).
		var unit: Node3D = null
		var member := ""
		var members: Dictionary = stage.army_routes["army-v010"].events.members
		for key in members:
			if members[key].any(func(r): return r[1] == "soldier_attack" and r[2] == e.unitId and int(r[3]) == int(e.index) and absf(float(r[0]) - float(e.at)) < 0.5):
				member = key
		unit = stage.actors.get_node_or_null(NodePath("army-v010/" + member.replace(":", "_"))) if member != "" else null
		if unit == null or not CombatV010.owns(unit):
			continue
		if CombatV010.pick_strike(unit, members[member], float(e.at)) != float(e.at):
			skipped += 1
			continue
		stage.present_armies(state, start + float(e.at))
		if unit.get_meta("clip", "") != "attack":
			continue
		var player := player_of(unit)
		var expected := float(CombatV010.info(unit).prepare_ms) / 1000.0
		var spec := Registry.troop(String(e.unitId))
		var name := str(player.assigned_animation)
		var attacks := [str(CombatV010.animation_name(CombatV010.info(unit), &"attack_a")), str(CombatV010.animation_name(CombatV010.info(unit), &"attack_b"))]
		check(name in attacks, "%s:%d not in an attack at its contact: %s" % [e.unitId, e.index, name])
		check(absf(player.current_animation_position - expected) <= CombatV010.DRIFT_S + 0.001,
			"%s:%d clip time %.3f at event.at, expected %.3f" % [e.unitId, e.index, player.current_animation_position, expected])
		if spec.event == "release":
			check(absf(expected - float(CombatV010.info(unit).release_ms) / 1000.0 - CombatV010.FLIGHT_MS / 1000.0) < 0.001, "%s release not one flight before contact" % e.unitId)
		# Same snapshot again (new object, same content) and a rewind: the swing is not restarted.
		var copy: Dictionary = state.duplicate(true)
		stage.present_armies(copy, start + float(e.at))
		check(absf(player.current_animation_position - expected) <= CombatV010.DRIFT_S + 0.001, "%s:%d repeated snapshot moved the swing" % [e.unitId, e.index])
		stage.present_armies(state, start + float(e.at) + 400.0)
		stage.present_armies(state, start + float(e.at))
		check(absf(player.current_animation_position - expected) <= CombatV010.DRIFT_S + 0.001, "%s:%d rewind lost the swing phase" % [e.unitId, e.index])
		verified += 1
	check(verified >= 5, "Contact phase verified for %d soldiers" % verified)
	notes.append("contact_phase_verified=%d strikes_skipped_visually=%d" % [verified, skipped])

	# The creature falls at the last blow and holds its grounded last frame.
	var last_hit := 0.0
	for e in events:
		if e.kind == "soldier_attack": last_hit = maxf(last_hit, float(e.at))
	for frame in 4:
		stage.present_armies(state, start + last_hit + 3000.0 + frame * 16.0)
		stage.present_creatures(state, start + last_hit + 3000.0 + frame * 16.0, 0.016)
		await process_frame
	if creature != null:
		var cp := player_of(creature)
		# The death clip the presenter maps for this creature: the library's "combat_v010/death", or
		# the creature's own authored "<species>__death" for creatures-v2 models (no library added).
		var death_clip := str(CombatV010.animation_name(CombatV010.info(creature), &"death"))
		check(str(cp.assigned_animation) == death_clip, "Creature not dying with v0.1.0: %s (expected %s)" % [cp.assigned_animation, death_clip])
		check(cp.current_animation_position >= cp.get_animation(cp.assigned_animation).length - 0.001 or not cp.is_playing(), "Creature death not held at its last frame")
	check(JSON.stringify(state) == before, "Presentation changed the server state")

	# ---- a spearman killed by a pounce (hp 0) -----------------------------
	var lone: Dictionary = cases.single_spearman_tenerys_defeat
	var enc2: Dictionary = state.world.encounters[0]
	state.world.armies = [make_army("army-lone", at, enc2, lone, start)]
	var kill := 0.0
	for e in lone.result.events:
		if e.get("hp", 1) == 0: kill = float(e.at)
	for frame in 6:
		stage.present_armies(state, start + kill - 900.0 + frame * 16.0)
		await process_frame
	var spear: Node3D = stage.actors.get_node_or_null(NodePath("army-lone/ENG-01_0"))
	check(spear != null and CombatV010.owns(spear), "Lone spearman not on v0.1.0")
	if spear != null:
		stage.present_armies(state, start + kill + 300.0)
		check(spear.get_meta("clip", "") == "death" and str(player_of(spear).assigned_animation) == "combat_v010/death", "Spearman does not die at the pounce")
		stage.present_armies(state, start + kill + 6000.0)
		var sp := player_of(spear)
		check(absf(sp.current_animation_position - sp.get_animation(sp.assigned_animation).length) < 0.001, "Death not held (no float/sink back up)")
		stage.present_armies(state, start + kill + 6100.0)
		check(spear.get_meta("clip", "") == "death", "A fallen soldier attacks again")

	# Late join: the app opens after the death; the body is shown down at once.
	state.world.armies = [make_army("army-late", at, enc2, lone, start)]
	for frame in 4:
		stage.present_armies(state, start + kill + 8000.0)
		await process_frame
	var late: Node3D = stage.actors.get_node_or_null(NodePath("army-late/ENG-01_0"))
	check(late != null and CombatV010.owns(late) and late.get_meta("clip", "") == "death", "Late join does not show the fallen soldier down")
	if late != null:
		var lp := player_of(late)
		check(absf(lp.current_animation_position - lp.get_animation(lp.assigned_animation).length) < 0.001, "Late join replays the fall instead of holding it")

	# ---- large battle sweep: 100 soldiers (24 drawn) against Velkor L3 ----------
	var large: Dictionary = cases.large_velkor_l3
	enc.level = int(large.level)
	state.world.armies = [make_army("army-large", at, enc, large, start)]
	var costs: Array = []
	var bad_phase := 0
	for step in int(float(large.result.duration) / 50.0) + 40:
		var now := start + 200.0 + step * 50.0
		var t0 := Time.get_ticks_usec()
		stage.present_armies(state, now)
		stage.present_creatures(state, now, 0.05)
		if step >= 20:
			costs.append((Time.get_ticks_usec() - t0) / 1000.0)
		for unit: Node3D in soldiers(stage, "army-large"):
			if CombatV010.owns(unit):
				var p := player_of(unit)
				var a := p.get_animation(p.assigned_animation)
				if a == null or p.current_animation_position < -0.001 or p.current_animation_position > a.length + 0.001:
					bad_phase += 1
		await process_frame
	costs.sort()
	var median: float = costs[costs.size() / 2]
	var p95: float = costs[mini(costs.size() - 1, int(costs.size() * 0.95))]
	check(bad_phase == 0, "Clip time outside its clip in the large battle: %d" % bad_phase)
	check(soldiers(stage, "army-large").all(func(u): return CombatV010.owns(u)), "Large battle soldiers not all on v0.1.0")
	notes.append("large_frames=%d median_ms=%.2f p95_ms=%.2f" % [costs.size(), median, p95])

	# ---- rollback: flag off hands every actor back to the legacy clips ------
	state.world.armies = [make_army("army-v010", at, enc, mixed, start)]
	stage.present_armies(state, start + 1500.0)
	var released := CombatV010.set_enabled(false)
	check(released > 0, "Rollback released nothing")
	check(CombatV010.generation > generation_on, "Rollback did not advance the generation")
	for frame in 3:
		stage.present_armies(state, start + 1600.0 + frame * 16.0)
		stage.present_creatures(state, start + 1600.0 + frame * 16.0, 0.016)
		await process_frame
	var legacy_ok := true
	for unit: Node3D in soldiers(stage, "army-v010"):
		var p := player_of(unit)
		if CombatV010.owns(unit) or p.has_animation_library(Registry.NAMESPACE) or str(p.assigned_animation).begins_with("combat_v010/"):
			legacy_ok = false
	check(legacy_ok, "Rollback left a v0.1.0 library or clip on a soldier")
	if creature != null and is_instance_valid(creature):
		check(not player_of(creature).has_animation_library(Registry.NAMESPACE), "Rollback left the library on the creature")
	check(JSON.stringify(state).length() > 0, "")
	print("QA_COMBAT_V010 %s" % " ".join(notes))
	print("QA_COMBAT_V010 checks=%d failures=%d" % [checks, failures])
	quit(1 if failures > 0 else 0)
