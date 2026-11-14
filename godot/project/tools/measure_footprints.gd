extends SceneTree

# Ground footprints of every building type at levels I-V, as the city draws the
# building itself (base model × level scale, or the reworked level scene), relative to
# the plot centre. The town plan (src/town_plan.gd) sizes each yard from them.
#   godot --headless --path . -s tools/measure_footprints.gd            # print
#   godot --headless --path . -s tools/measure_footprints.gd -- --write  # update the table
#   godot --headless --path . -s tools/measure_footprints.gd -- --check  # exit 1 if stale

const TABLE := "res://assets/city/town_lots.json"

func _initialize() -> void:
	call_deferred("run")

func bounds_of(node: Node3D, parent := Transform3D.IDENTITY) -> AABB:
	# Accumulates local transforms, so the scene does not have to be in the tree.
	var box := AABB()
	var here := parent * node.transform
	if node is MeshInstance3D and node.mesh != null:
		box = here * node.get_aabb()
	for child in node.get_children():
		if child is Node3D:
			var inner := bounds_of(child, here)
			if inner.has_surface():
				box = inner if not box.has_surface() else box.merge(inner)
	return box

static func level_parts(data: Dictionary, type: String, level: int) -> Array:
	var entry: Variant = data.get("levelModels", {}).get(type, {}).get(str(level))
	if entry is Dictionary:
		return [entry.path, float(entry.get("scale", 1.0))]
	var id: String = data.starterHall if type == "ECO-05" and level == 1 else str(data.types.get(type, ""))
	if id.is_empty():
		return []
	return [data.models[id].path, float(data.models[id].scale) * (1.0 + 0.055 * (level - 1))]

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var table := {}
	var types: Array = data.types.keys()
	types.sort()
	for type: String in types:
		var levels := {}
		for level in range(1, 6):
			var parts := level_parts(data, type, level)
			var scene: Node3D = load(parts[0]).instantiate()
			scene.scale = Vector3.ONE * float(parts[1])
			var b := bounds_of(scene)
			scene.free()
			levels[str(level)] = [snappedf(b.position.x, 0.01), snappedf(b.position.z, 0.01),
				snappedf(b.end.x, 0.01), snappedf(b.end.z, 0.01), snappedf(b.end.y, 0.01)]
		table[type] = levels
		print(type, " ", JSON.stringify(levels))
	var text := JSON.stringify({"schema": 1, "note": "x0,z0,x1,z1,height of each level around the plot centre; tools/measure_footprints.gd", "types": table}, "\t", true) + "\n"
	var args := OS.get_cmdline_user_args()
	if "--write" in args:
		var file := FileAccess.open(TABLE, FileAccess.WRITE)
		file.store_string(text)
		file.close()
		print("WROTE ", TABLE)
	elif "--check" in args:
		var current: Variant = JSON.parse_string(FileAccess.get_file_as_string(TABLE)) if FileAccess.file_exists(TABLE) else null
		var same: bool = current is Dictionary and JSON.stringify(current.types, "", true) == JSON.stringify(JSON.parse_string(JSON.stringify(table)), "", true)
		print("TOWN_LOTS_TABLE ", "current" if same else "STALE")
		quit(0 if same else 1)
		return
	quit(0)
