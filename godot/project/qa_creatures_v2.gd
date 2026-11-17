extends SceneTree

# creatures-v2 (velkor, tenerys, kamneklyk, dragor) in the real client code:
# - the existing species ids map to the new runtime GLBs (registry), rollback flag restores the old ones;
# - each GLB carries exactly its authored clips (12/12/14/14), no alias copies;
# - the eight old states Idle/Walk/Run/Alert/Attack/Hit/Death/Roar and the server's special event of each
#   species resolve to existing clips (Alert and Roar to different ones), loop modes follow the manifest;
# - combat v0.1.0 drives the authored clips (no animation library added) with manifest contact timing;
# - two instances of one species play different clips independently; levels share textures, differ in
#   material parameters and overlays; level materials are shared between instances of the same level;
#   per-group level overrides (Dragor III skin vs plate seams) reach the right meshes;
# - 20 spawn/despawn cycles do not accumulate nodes or resources; the death clip ends above the ground.
# Run: godot --headless --path godot/project -s qa_creatures_v2.gd

const CreatureVisuals = preload("res://src/creature_visuals.gd")
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const EXPECTED := {"velkor": 12, "kamneklyk": 12, "tenerys": 14, "dragor": 14}
const BONES := {"velkor": [40, 56], "kamneklyk": [36, 48], "tenerys": [44, 60], "dragor": [48, 64]}
const SPECIAL := {"velkor": "antler_charge", "tenerys": "pounce", "kamneklyk": "tusk_sweep", "dragor": "shockwave"}

var checks := 0
var failures := 0
var report := {}

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error("FAIL " + description)
		print("FAIL ", description)

func run() -> void:
	var game_json: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	CreatureVisuals.set_enabled(true)
	CombatV010.set_enabled(true)
	for species in EXPECTED:
		var row := {}
		var legacy: String = game_json.creatureModels[species][0]
		check(CreatureVisuals.active(species), species + ": creatures-v2 asset active")
		if not CreatureVisuals.active(species):
			continue
		var path := CreatureVisuals.model_path(species, 1, legacy)
		check(path != legacy and path.ends_with(species + "_runtime.gltf"), species + ": new versioned asset path " + path)
		# rollback: the old visual reference stays valid and is used when the flag is off
		CreatureVisuals.set_enabled(false)
		check(CreatureVisuals.model_path(species, 2, game_json.creatureModels[species][1]) == game_json.creatureModels[species][1], species + ": rollback returns the old asset")
		check(ResourceLoader.exists(game_json.creatureModels[species][1]), species + ": rollback asset still in the project")
		CreatureVisuals.set_enabled(true)
		var scene := load(path) as PackedScene
		check(scene != null, species + ": GLB imports as a scene")
		if scene == null:
			continue
		var man := CreatureVisuals.manifest(species)
		var a := scene.instantiate() as Node3D
		var b := scene.instantiate() as Node3D
		root.add_child(a)
		root.add_child(b)
		CreatureVisuals.install(a, species, 1, 1.0)
		CreatureVisuals.install(b, species, 3, 1.0)
		var players := a.find_children("*", "AnimationPlayer", true, false)
		check(players.size() == 1, species + ": one AnimationPlayer")
		var player: AnimationPlayer = players[0]
		var names := Array(player.get_animation_list())
		row.clips = names.size()
		check(names.size() == EXPECTED[species], "%s: exactly %d clips (got %d)" % [species, EXPECTED[species], names.size()])
		check(names.all(func(n): return str(n).begins_with(species + "__")), species + ": clip names <species>__<name>")
		check(int(man.get("clip_count", 0)) == EXPECTED[species], species + ": manifest clip count")
		for state in ["Idle", "Walk", "Run", "Alert", "Attack", "Hit", "Death", "Roar"]:
			var clip := CreatureVisuals.clip_name(species, state)
			check(clip != &"" and player.has_animation(clip), "%s: %s -> %s exists" % [species, state, clip])
		check(CreatureVisuals.clip_name(species, "Alert") != CreatureVisuals.clip_name(species, "Roar"), species + ": Alert and Roar are different clips")
		var special := CreatureVisuals.clip_name(species, SPECIAL[species])
		check(special != &"" and player.has_animation(special), "%s: server event %s -> %s" % [species, SPECIAL[species], special])
		check(CreatureVisuals.clip_name(species, "attack_b") == special, species + ": combat special clip = server special")
		for short in man.clips:
			var anim := player.get_animation(StringName(str(man.clips[short].name)))
			check(anim != null and (anim.loop_mode != Animation.LOOP_NONE) == bool(man.clips[short].loop), "%s: %s loop mode = manifest" % [species, short])
			check(anim != null and absf(anim.length - float(man.clips[short].length_s)) < 0.034, "%s: %s length %.3f = manifest" % [species, short, anim.length if anim else -1.0])
		# skeleton
		var skel: Skeleton3D = a.find_children("*", "Skeleton3D", true, false)[0]
		row.bones = skel.get_bone_count()
		check(skel.get_bone_count() >= BONES[species][0] and skel.get_bone_count() <= BONES[species][1], "%s: %d bones within %s" % [species, skel.get_bone_count(), BONES[species]])
		var sockets := a.find_children("socket_*", "", true, false)
		row.sockets = sockets.size()
		check(sockets.size() >= 9, "%s: sockets present (%d)" % [species, sockets.size()])
		# levels: overlays and materials
		var mats_a := {}
		var mats_b := {}
		var overlays := 0
		for part: MeshInstance3D in a.find_children("*", "MeshInstance3D", true, false):
			if String(part.name).contains("VARIANT"):
				overlays += 1
				check(not part.visible, "%s: level I hides overlay %s" % [species, part.name])
			mats_a[String(part.name)] = part.get_surface_override_material(0)
			check(part.get_surface_override_material(0) is ShaderMaterial, "%s: %s uses the creature shader" % [species, part.name])
		for part: MeshInstance3D in b.find_children("*", "MeshInstance3D", true, false):
			mats_b[String(part.name)] = part.get_surface_override_material(0)
			if String(part.name).contains("VARIANT_L3") or String(part.name).contains("VARIANT_L2"):
				check(part.visible, "%s: level III shows overlay %s" % [species, part.name])
		row.overlays = overlays
		var any_name: String = mats_a.keys()[0]
		check(mats_a[any_name] != mats_b[any_name], species + ": level I and III have their own material parameters")
		var ma: ShaderMaterial = mats_a[any_name]
		var mb: ShaderMaterial = mats_b[any_name]
		check(ma.get_shader_parameter("albedo_tex") == mb.get_shader_parameter("albedo_tex"), species + ": levels share the same textures")
		# per-group level overrides (registry "groups"), e.g. Dragor III: skin creases glow less than plate seams
		var lv3: Dictionary = CreatureVisuals.entry(species).get("levels", {}).get("3", {})
		var labels: Dictionary = CreatureVisuals.entry(species).get("groups", {})
		var overridden := 0
		for part_name: String in mats_b:
			var group := ""
			for g in labels:
				if part_name.to_lower().contains("_" + str(labels[g]).to_lower() + "_"):
					group = g
			var over: Dictionary = lv3.get("groups", {}).get(group, {})
			var want := Vector3(float(over.get("emit_r", lv3.get("emit_r", 0.0))), float(over.get("emit_g", lv3.get("emit_g", 0.0))),
				float(over.get("emit_b", lv3.get("emit_b", 0.0))))
			var got: Vector3 = (mats_b[part_name] as ShaderMaterial).get_shader_parameter("emit_masks")
			check(got.is_equal_approx(want), "%s: level III %s glow %s = registry %s" % [species, part_name, got, want])
			overridden += 1 if not over.is_empty() else 0
		if not lv3.get("groups", {}).is_empty():
			check(overridden > 0, "%s: level III group override reaches its meshes (%d)" % [species, overridden])
		var c := scene.instantiate() as Node3D
		root.add_child(c)
		CreatureVisuals.install(c, species, 1, 1.0)
		var shared := true
		for part: MeshInstance3D in c.find_children("*", "MeshInstance3D", true, false):
			shared = shared and part.get_surface_override_material(0) == mats_a.get(String(part.name))
		check(shared, species + ": instances of one level share their materials")
		# LOD1 near / LOD2 far with hysteresis, exactly one LOD drawn, also for a creature first seen inside
		# the band (Godot's own range margins started it hidden on both LODs there)
		var lods := {1: 0, 2: 0}
		for part: MeshInstance3D in a.find_children("*", "MeshInstance3D", true, false):
			if String(part.name).contains("_LOD1"):
				lods[1] += 1
			elif String(part.name).contains("_LOD2"):
				lods[2] += 1
		check(lods[1] > 0 and lods[2] > 0, species + ": LOD1 and LOD2 meshes present")
		var cam := Camera3D.new()
		root.add_child(cam)
		var switch_m := float(CreatureVisuals.entry(species).lod_switch_m)  # actor a has scale 1
		var drawn := func(actor: Node3D) -> Array:
			var shown := {1: 0, 2: 0}
			for part: MeshInstance3D in actor.find_children("*", "MeshInstance3D", true, false):
				var n := String(part.name)
				if part.visible and part.is_visible_in_tree() and not n.contains("VARIANT"):
					shown[2 if n.contains("_LOD2") else 1] += 1
			return [shown[1], shown[2]]
		var steps := [[0.5, 1], [1.05, 1], [1.2, 2], [1.05, 2], [0.95, 2], [0.8, 1], [1.0, 1]]
		var lod_ok := true
		for step in steps:
			cam.global_position = a.global_position + Vector3(0, 0, float(step[0]) * switch_m)
			var got := CreatureVisuals.update_lod(a, cam)
			var shown: Array = drawn.call(a)
			var one: bool = (int(shown[0]) > 0) != (int(shown[1]) > 0)
			lod_ok = lod_ok and got == int(step[1]) and one and (int(shown[0]) > 0 if got == 1 else int(shown[1]) > 0)
		check(lod_ok, species + ": LOD hysteresis 0.5/1.05/1.2/1.05/0.95/0.8/1.0 x switch -> 1/1/2/2/2/1/1, one LOD drawn")
		var fresh := scene.instantiate() as Node3D
		root.add_child(fresh)
		CreatureVisuals.install(fresh, species, 1, 1.0)
		cam.global_position = fresh.global_position + Vector3(0, 0, switch_m * 1.08)
		CreatureVisuals.update_lod(fresh, cam)
		var first: Array = drawn.call(fresh)
		check(int(first[0]) > 0 or int(first[1]) > 0, species + ": a creature first seen inside the LOD band is drawn")
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = 2.0 * tan(deg_to_rad(cam.fov) * 0.5) * switch_m * 1.5
		check(CreatureVisuals.update_lod(fresh, cam) == 2, species + ": orthographic view (city) uses its on-screen size for LOD")
		fresh.queue_free()
		cam.queue_free()
		# combat v0.1.0 drives the authored clips: no library, manifest timing
		check(CombatV010.install(a, "creature", path), species + ": combat v0.1.0 accepts the actor")
		check(not player.has_animation_library(&"combat_v010"), species + ": no extra animation library (no duplicated tracks)")
		var w: Vector2 = CombatV010.creature_attack_window(a)
		var attack_row: Dictionary = CreatureVisuals.clip_row(species, CreatureVisuals.short_name(species, "Attack"))
		check(absf(w.x - float(attack_row.contact_s) * 1000.0) < 1.0, "%s: attack contact %.0f ms from the manifest" % [species, w.x])
		check(CombatV010.install(b, "creature", path), species + ": second instance accepted")
		# independence: two instances, two clips
		CombatV010.drive(a, &"walk")
		CombatV010.drive(b, &"attack_a", 0.4)
		await process_frame
		await process_frame
		var pa: AnimationPlayer = a.find_children("*", "AnimationPlayer", true, false)[0]
		var pb: AnimationPlayer = b.find_children("*", "AnimationPlayer", true, false)[0]
		check(pa.current_animation != pb.current_animation and pa.current_animation != "", "%s: instances play different clips (%s / %s)" % [species, pa.current_animation, pb.current_animation])
		var sa: Skeleton3D = a.find_children("*", "Skeleton3D", true, false)[0]
		var sb: Skeleton3D = b.find_children("*", "Skeleton3D", true, false)[0]
		var head := sa.find_bone("Head")
		check(not sa.get_bone_global_pose(head).origin.is_equal_approx(sb.get_bone_global_pose(head).origin), species + ": skeleton poses independent")
		# death ends above the ground and stays there
		CombatV010.drive(a, &"death", INF)
		await process_frame
		await process_frame
		var lowest := INF
		for i in sa.get_bone_count():
			lowest = minf(lowest, (sa.global_transform * sa.get_bone_global_pose(i)).origin.y)
		row.death_lowest_bone_m = snappedf(lowest, 0.001)
		check(lowest > -0.12, "%s: dead pose bones above ground (lowest %.3f m)" % [species, lowest])
		for n in [a, b, c]:
			n.queue_free()
		await process_frame
		# 20 spawn/despawn cycles: node and resource counts return to the baseline
		await process_frame
		var nodes0 := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
		var res0 := Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)
		for cycle in 20:
			var x := scene.instantiate() as Node3D
			root.add_child(x)
			CreatureVisuals.install(x, species, 1 + cycle % 3, 1.0)
			CombatV010.install(x, "creature", path)
			CombatV010.drive(x, &"idle")
			await process_frame
			x.queue_free()
			await process_frame
		await process_frame
		var nodes1 := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
		var res1 := Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)
		row.cycle_node_delta = nodes1 - nodes0
		row.cycle_resource_delta = res1 - res0
		check(nodes1 - nodes0 <= 0, "%s: 20 cycles leave no nodes (%d)" % [species, nodes1 - nodes0])
		check(res1 - res0 <= 2, "%s: 20 cycles leave no resources (%d)" % [species, res1 - res0])
		report[species] = row
	print("CREATURES_V2 ", JSON.stringify(report))
	print("CREATURES_V2_CHECKS ", checks, " failures ", failures)
	print("QA_CREATURES checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
