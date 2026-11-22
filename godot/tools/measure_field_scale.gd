extends SceneTree
# Build 1021 audit: heights (and footprints) of the field soldiers, the creatures and
# the buildings and trees around them, on each map, at the sizes of build 1020 and of
# this build, from the GLB models themselves. Prints one JSON line.
#   cd godot/project && godot --headless --path . -s ../tools/measure_field_scale.gd
const Landscape = preload("res://src/landscape.gd")

func _initialize() -> void:
	call_deferred("run")

func box_of(path: String, scale: float) -> AABB:
	var node := (load(path) as PackedScene).instantiate() as Node3D
	root.add_child(node)
	node.scale = Vector3.ONE * scale
	var box := AABB()
	var first := true
	for mesh: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh == null:
			continue
		var b: AABB = mesh.global_transform * mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	node.free()
	return box

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var out := {"soldiers": {}, "creatures": {}, "city": {}, "world": {}}
	for id in data.unitModels:
		if not str(id).begins_with("ENG-"):
			continue
		var h := box_of(data.unitModels[id].field, 1.0).size.y
		out.soldiers[id] = {"1020_both_maps_m": snappedf(h * 1.15, 0.01), "1021_city_m": snappedf(h * Landscape.FIELD_UNIT_SCALE, 0.01),
			"1021_world_m": snappedf(h * Landscape.WORLD_UNIT_SCALE, 0.01), "parade_m": snappedf(h, 0.01)}
	for species in data.creatureModels:
		var row := {}
		for level in [1, 3]:
			var h := box_of(data.creatureModels[species][level - 1], Landscape.creature_scale(level)).size.y
			row["L%d_city_m" % level] = snappedf(h, 0.01)
			row["L%d_world_1020_m" % level] = snappedf(h, 0.01)
			row["L%d_world_1021_m" % level] = snappedf(h * Landscape.WORLD_CREATURE_SCALE, 0.01)
		out.creatures[species] = row
	for key in ["hall", "house", "barracks26", "farm", "well"]:
		out.city[key + "_m"] = snappedf(box_of(data.models[key].path, float(data.models[key].scale)).size.y, 0.01)
	var houses := []
	var halls := []
	for site in data.sites:
		for part in site.parts:
			(houses if part.key == "house" else halls).append(float(part.scale))
	houses.sort()
	halls.sort()
	var house_h := box_of(data.models.house.path, 1.0).size.y
	var hall_h := box_of(data.models.hall.path, 1.0).size.y
	out.world.house_m = [snappedf(house_h * houses[0], 0.01), snappedf(house_h * houses[-1], 0.01)]
	out.world.hall_m = [snappedf(hall_h * halls[0], 0.01), snappedf(hall_h * halls[-1], 0.01)]
	var trees := {}
	for item in data.environment:
		if data.environmentModels[item.id].tree:
			if not trees.has(item.id): trees[item.id] = []
			trees[item.id].append(float(item.scale))
	var tree_h := []
	for id in trees:
		var list: Array = trees[id]
		list.sort()
		if list.size() > 100:
			tree_h.append(box_of(data.environmentModels[id].near, list[list.size() / 2]).size.y)
	tree_h.sort()
	out.world.common_trees_m = [snappedf(tree_h[0], 0.01), snappedf(tree_h[-1], 0.01)]
	print("FIELD_SCALE ", JSON.stringify(out))
	quit()
