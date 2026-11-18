extends SceneTree
# Build 1021: ground footprints of the world map's scenery and settlement models (at
# scale 1, in the model's own axes) for the march lanes (src/march_lanes.gd), so the
# game never loads a model just to measure it.
#   cd godot/project && godot --headless --path . -s ../tools/make_scenery_footprints.gd
# Writes res://assets/environment/scenery-footprints.json: id -> [centre x, centre z,
# half width x, half depth z, height].

func _initialize() -> void:
	call_deferred("run")

func footprint(path: String) -> Array:
	var scene: PackedScene = load(path)
	var node := scene.instantiate() as Node3D
	root.add_child(node)
	var box := AABB()
	var first := true
	for mesh: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh == null:
			continue
		var b: AABB = node.global_transform.affine_inverse() * mesh.global_transform * mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	node.free()
	var c := box.get_center()
	return [snappedf(c.x, 0.001), snappedf(c.z, 0.001), snappedf(box.size.x * 0.5, 0.001), snappedf(box.size.z * 0.5, 0.001), snappedf(box.size.y, 0.001)]

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var out := {}
	for id in data.environmentModels:
		out[id] = footprint(str(data.environmentModels[id].near))
	for key in ["hall", "house"]:
		out["site:" + key] = footprint(str(data.models[key].path))
	var file := FileAccess.open("res://assets/environment/scenery-footprints.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(out, "", true))
	file.close()
	print("FOOTPRINTS ", out.size())
	quit()
