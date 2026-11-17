extends SceneTree

# Structural checks for the rebuilt English soldiers (godot/art/troops pipeline):
# clips, skin weights, weapon binding, grounding and triangle budgets, for every
# unit and both LODs as the game loads them from game.json.

const REQUIRED := ["Idle", "Walk", "Run", "Attack", "Hit", "Death"]
# Field LODs may not be heavier than the 0.5.9 field models they replace (+3%).
const FIELD_BUDGET := {"ENG-01": 21898, "ENG-02": 21401, "ENG-03": 20275, "ENG-04": 21989, "ENG-05": 29114,
	"ENG-06": 34754, "ENG-07": 17591, "ENG-08": 22548, "ENG-09": 22360, "ENG-10": 21316}
var failures: Array[String] = []
var checks := 0
var rows: Array = []

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func triangles(model: Node) -> int:
	var total := 0
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		for s in mi.mesh.get_surface_count():
			var arrays := mi.mesh.surface_get_arrays(s)
			var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
			total += index.size() / 3 if not index.is_empty() else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return total

func weight_problems(model: Node) -> Array:
	var bad := []
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if mi.skin == null:
			continue
		for s in mi.mesh.get_surface_count():
			var arrays := mi.mesh.surface_get_arrays(s)
			var weights = arrays[Mesh.ARRAY_WEIGHTS]
			if weights == null:
				bad.append("%s has no weights" % mi.name)
				continue
			var per := 8 if (mi.mesh.surface_get_format(s) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) else 4
			var count: int = weights.size() / per
			var zero := 0
			for v in count:
				var sum := 0.0
				for k in per:
					sum += weights[v * per + k]
				if sum < 0.99:
					zero += 1
			if zero > 0:
				bad.append("%s: %d of %d vertices unweighted" % [mi.name, zero, count])
	return bad

func weapon_binding(model: Node) -> Array:
	"""Main weapons must follow exactly one hand bone."""
	var out := []
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		var name := String(mi.name)
		if name.contains("Case") or not (name.begins_with("Spear") or name.begins_with("Sword") or name.begins_with("Longbow") or name.begins_with("Crossbow") or name.begins_with("Javelin") or name.begins_with("Lance")):
			continue
		var arrays := mi.mesh.surface_get_arrays(0)
		var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
		var weights = arrays[Mesh.ARRAY_WEIGHTS]
		var used := {}
		for i in bones.size():
			if weights[i] > 0.001:
				used[bones[i]] = true
		out.append([name, used.size()])
	return out

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	for id in data.unitModels:
		var visual: Dictionary = data.unitModels[id]
		var mounted: bool = visual.drill == "Mounted_Drill"
		check(String(visual.preview).contains("troops06") and String(visual.field).contains("troops06"), id + " still uses a 0.5.9 model")
		var row := {"unit": id}
		for role in ["preview", "field"]:
			var packed := load(visual[role]) as PackedScene
			check(packed != null, "%s %s does not load" % [id, role])
			if packed == null:
				continue
			var model: Node3D = packed.instantiate()
			root.add_child(model)
			var player: AnimationPlayer = model.find_children("*", "AnimationPlayer", true, false)[0]
			var clips := player.get_animation_list()
			for clip in REQUIRED + [visual.drill]:
				check(clips.has(clip), "%s %s misses clip %s" % [id, role, clip])
			if mounted:
				check(clips.has("Recruit_Showcase"), id + " lacks Recruit_Showcase")
			for problem in weight_problems(model):
				check(false, "%s %s %s" % [id, role, problem])
			for binding in weapon_binding(model):
				check(binding[1] == 1, "%s %s weapon %s follows %d bones" % [id, role, binding[0], binding[1]])
			row[role + "_triangles"] = triangles(model)
			if role == "field":
				check(row.field_triangles <= int(FIELD_BUDGET[id] * 1.03),
					"%s field LOD has %d triangles (0.5.9: %d)" % [id, row.field_triangles, FIELD_BUDGET[id]])
			# Grounding and stature in the idle pose.
			var skeleton: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
			player.play("Idle")
			player.seek(0.0, true)
			player.pause()
			var foot_l: float = skeleton.get_bone_global_pose(skeleton.find_bone("foot.L")).origin.y
			var foot_r: float = skeleton.get_bone_global_pose(skeleton.find_bone("foot.R")).origin.y
			var head: float = skeleton.get_bone_global_pose(skeleton.find_bone("head")).origin.y
			if not mounted:
				check(foot_l > 0.0 and foot_l < 0.13 and foot_r > 0.0 and foot_r < 0.13, "%s feet not planted at idle: %.3f %.3f" % [id, foot_l, foot_r])
				check(head > 1.45 and head < 1.75, "%s head height %.2f" % [id, head])
			else:
				var hoof: float = skeleton.get_bone_global_pose(skeleton.find_bone("FrontLHoof")).origin.y
				check(hoof < 0.2, "%s horse hoof off the ground: %.2f" % [id, hoof])
				check(head > foot_l + 0.9, "%s rider not seated upright" % id)
			row[role + "_head"] = snappedf(head, 0.01)
			model.free()
			await process_frame
		rows.append(row)
	for row in rows:
		print("TROOP06 ", JSON.stringify(row))
	print("QA_TROOPS06 checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
