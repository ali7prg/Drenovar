extends SceneTree

# Objective audit of the ten English troop models (preview LOD1 and field LOD2):
# height, head-to-body proportion, triangles, skeleton and animation clips.
# Usage: godot --headless --path . -s profile_troops.gd

func _initialize() -> void:
	call_deferred("run")

func triangles(model: Node3D) -> int:
	var total := 0
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		for surface in part.mesh.get_surface_count():
			var arrays := part.mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
			total += indices.size() / 3 if not indices.is_empty() else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return total

func bounds(model: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		var b := part.global_transform * part.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box

func bone_y(skeleton: Skeleton3D, names: Array) -> float:
	for bone in skeleton.get_bone_count():
		var n := skeleton.get_bone_name(bone).to_lower()
		for wanted in names:
			if n == wanted or n.ends_with(wanted):
				return (skeleton.global_transform * skeleton.get_bone_global_rest(bone)).origin.y
	return NAN

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var roster := {}
	for unit in data.englishRoster:
		roster[unit.id] = unit.get("name", unit.id)
	for id in data.unitModels:
		for lod in ["preview", "field"]:
			var model: Node3D = load(data.unitModels[id][lod]).instantiate()
			root.add_child(model)
			var box := bounds(model)
			var row := {"unit": id, "name": roster.get(id, ""), "lod": lod, "triangles": triangles(model),
				"height": snappedf(box.size.y, 0.001), "width": snappedf(box.size.x, 0.001)}
			var skeletons := model.find_children("*", "Skeleton3D", true, false)
			row.skeletons = skeletons.size()
			row.bones = skeletons.map(func(s): return s.get_bone_count())
			if not skeletons.is_empty():
				var rider: Skeleton3D = skeletons[0]
				for s: Skeleton3D in skeletons:
					if not is_nan(bone_y(s, ["head"])) and not is_nan(bone_y(s, ["neck"])):
						rider = s
						break
				var head := bone_y(rider, ["head"])
				var neck := bone_y(rider, ["neck"])
				var foot := bone_y(rider, ["foot.l", "foot_l", "leftfoot", "foot"])
				var top := box.end.y
				if not is_nan(neck) and not is_nan(foot) and top > neck:
					# Head height approximated as crown minus neck base; realistic adults ~7-7.5 heads.
					row.heads_tall = snappedf((top - foot) / maxf(0.001, top - neck), 0.01) if id not in ["ENG-05", "ENG-06"] else "mounted"
				row.head_bone_y = snappedf(head, 0.001) if not is_nan(head) else null
			var players := model.find_children("*", "AnimationPlayer", true, false)
			row.clips = Array(players[0].get_animation_list()) if not players.is_empty() else []
			print("TROOP ", JSON.stringify(row))
			model.free()
	quit(0)
