extends SceneTree

# creatures-v2 encounter lifecycle on the real world stage (landscape.present_creatures), all four species:
#   alive (new model, idle, glow on) -> server battle from the real simulator (tests/combat_v010/*cases.json)
#   -> the creature falls (Death clip, glow out by the end of the clip) -> corpse while the army leaves
#   -> corpse removed -> the server respawns the same encounter id: a fresh actor, alive, glow back,
#   same model and scale. Only the server state drives it; the client never decides the outcome.
# Run: godot --headless --path godot/project -s qa_creatures_v2_lifecycle.gd

const CreatureVisuals = preload("res://src/creature_visuals.gd")
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const CombatPresentation = preload("res://src/combat_presentation.gd")
const CASES := {"velkor": ["res://tests/combat_v010/server_combat_cases.json", "mixed_all_types_velkor"],
	"tenerys": ["res://tests/combat_v010/server_combat_cases.json", "spear_sword_tenerys"],
	"kamneklyk": ["res://tests/combat_v010/creatures_v2_cases.json", "mixed_all_types_kamneklyk"],
	"dragor": ["res://tests/combat_v010/creatures_v2_cases.json", "mixed_all_types_dragor"]}
const CORPSE_MS := 4500.0

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error("FAIL " + description)
		print("FAIL ", description)

func life_of(actor: Node3D) -> float:
	for part in actor.find_children("*", "GeometryInstance3D", true, false):
		var v: Variant = (part as GeometryInstance3D).get_instance_shader_parameter(&"life")
		if v != null:
			return float(v)
	return 1.0 # never set: the shader default

func show_at(stage, state: Dictionary, at: float, frames := 3) -> void:
	for i in frames:
		stage.battle_fx.begin()
		stage.present_armies(state, at)
		stage.present_creatures(state, at, 0.1)
		await process_frame

func run() -> void:
	CreatureVisuals.set_enabled(true)
	CombatV010.set_enabled(true)
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	if game.map_name != "world":
		await game.show_scene("world")
	var stage = game.stage
	var base: Dictionary = game.state.duplicate(true)
	for species in CASES:
		var case: Dictionary = {}
		for c in JSON.parse_string(FileAccess.get_file_as_string(CASES[species][0])).cases:
			if c.name == CASES[species][1]:
				case = c
		check(not case.is_empty() and case.result.outcome == "victory", species + ": server simulator case found")
		var state: Dictionary = base.duplicate(true)
		var enc: Dictionary = state.world.encounters[0].duplicate(true)
		enc.id = "life-" + species
		enc.species = species
		enc.spec = {"id": species, "name": str(CreatureVisuals.entry(species).get("name", species)), "hp": 1400}
		enc.level = 3
		enc.patrol = []
		enc.status = "alive"
		enc.hp = 1400
		enc.position = {"x": -50.0, "z": -30.0}
		state.world.encounters = [enc]
		state.world.armies = []
		var at: Vector3 = stage.point(enc.position)
		stage.target = at
		stage.zoom = 30.0
		stage.update_camera(0, true)
		# 1) alive: the new model on its species id, idle, glow on
		var t0 := 500000.0
		await show_at(stage, state, t0, 6)
		var first: Node3D = stage.creatures.get_node_or_null(NodePath(enc.id))
		check(first != null and CreatureVisuals.owns(first), species + ": alive encounter shows the creatures-v2 actor")
		if first == null:
			continue
		var first_scale := first.scale.x
		var first_id := first.get_instance_id()
		check(str(first.get_meta("clip", "")) == "Idle", species + ": alive creature idles (" + str(first.get_meta("clip", "")) + ")")
		check(is_equal_approx(life_of(first), 1.0), species + ": alive glow on")
		# 2) the server battle (status/hp are final at battle start; the fight plays out on screen)
		var arrive := t0 + 20000.0
		var path := [{"x": at.x - 30.0, "z": at.z + 26.0}, {"x": at.x - 12.0, "z": at.z + 8.0}, {"x": at.x, "z": at.z}]
		var army := {"id": "life-army-" + species, "status": "outbound", "target": enc.id, "worldKind": "creature", "path": path,
			"units": case.party.duplicate(), "startsAt": arrive - 14000.0, "arrivesAt": arrive, "battleAt": arrive,
			"battleEndsAt": arrive + float(case.result.duration), "battle": {"events": case.result.events.duplicate(true)}, "fallen": [],
			"returnStartsAt": arrive + float(case.result.duration), "returnsAt": arrive + float(case.result.duration) + 14000.0}
		CombatPresentation.stretch(army, {})
		var ends := float(army.battleEndsAt)
		army.status = "fighting"
		enc.status = "defeated"
		enc.hp = 0
		state.world.armies = [army]
		var saw_attack := false
		var saw_death := false
		var t := arrive
		while t < ends:
			await show_at(stage, state, t, 1)
			var actor: Node3D = stage.creatures.get_node_or_null(NodePath(enc.id))
			if actor != null:
				saw_attack = saw_attack or str(actor.get_meta("clip", "")) == "Attack"
				saw_death = saw_death or str(actor.get_meta("clip", "")) == "Death"
			t += 100.0
		check(saw_attack, species + ": attacks during the server battle")
		check(stage.creatures.get_node_or_null(NodePath(enc.id)) != null and stage.creatures.get_node_or_null(NodePath(enc.id)).get_instance_id() == first_id,
			species + ": the same actor fights (no duplicate)")
		# 3) the army turns home. A long fight ends on the killing blow: the body falls now, from that blow
		#    (not popped to the last frame); a stretched short fight began the fall inside the battle.
		army.status = "returning"
		var back: Array = path.duplicate()
		back.reverse()
		army.returnPath = back
		army.returnUnits = case.result.get("surviving", {}) if not case.result.get("surviving", {}).is_empty() else case.party
		await show_at(stage, state, ends + 100.0, 2)
		var falling: Node3D = stage.creatures.get_node_or_null(NodePath(enc.id))
		check(falling != null and falling.get_instance_id() == first_id and str(falling.get_meta("clip", "")) == "Death",
			species + ": the same actor falls when the server's hp reaches 0")
		if falling != null:
			check(saw_death or life_of(falling) > 0.05, species + ": the fall plays after the killing blow (glow %.2f)" % life_of(falling))
		var death_s := float(CreatureVisuals.clip_row(species, "death").get("length_s", 2.0))
		await show_at(stage, state, ends + death_s * 1000.0 + 150.0, 3)
		var corpse: Node3D = stage.creatures.get_node_or_null(NodePath(enc.id))
		check(corpse != null and str(corpse.get_meta("clip", "")) == "Death", species + ": corpse lies in the death pose")
		if corpse != null:
			check(life_of(corpse) < 0.01, species + ": glow out on the corpse (life %.2f)" % life_of(corpse))
		# 4) corpse removed after the army left
		await show_at(stage, state, ends + CORPSE_MS + 400.0, 3)
		check(stage.creatures.get_node_or_null(NodePath(enc.id)) == null, species + ": corpse removed")
		# 5) server respawn: same id alive again -> a fresh actor, idle, glow back, same model and scale
		state.world.armies = []
		enc.status = "alive"
		enc.hp = 1400
		await show_at(stage, state, ends + 60000.0, 6)
		var again: Node3D = stage.creatures.get_node_or_null(NodePath(enc.id))
		check(again != null and CreatureVisuals.owns(again), species + ": respawned encounter shows the creatures-v2 actor")
		if again != null:
			check(again.get_instance_id() != first_id, species + ": respawn builds a fresh actor")
			check(str(again.get_meta("clip", "")) == "Idle", species + ": respawned creature idles (" + str(again.get_meta("clip", "")) + ")")
			check(is_equal_approx(life_of(again), 1.0), species + ": respawned glow back on")
			check(is_equal_approx(again.scale.x, first_scale), species + ": same scale after respawn")
		var count := 0
		for child in stage.creatures.get_children():
			if String(child.name) == enc.id:
				count += 1
		check(count == 1, species + ": one actor per encounter id (%d)" % count)
		state.world.encounters = []
		await show_at(stage, state, ends + 70000.0, 2)
	print("QA_CREATURES_LIFECYCLE checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
