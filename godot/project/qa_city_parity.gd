extends SceneTree

# Proves that the incremental city presentation (0.6.0) renders exactly what the
# full-rebuild implementation from 0.5.9 renders, for a sequence of authoritative
# state changes, while rebuilding vegetation only when it actually changes.

var failures: Array[String] = []
var checks := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func material_key(material: Material) -> String:
	if material == null:
		return "-"
	if material is BaseMaterial3D and material.albedo_texture != null:
		return material.get_class() + ":" + material.albedo_texture.resource_path
	if material is ShaderMaterial:
		return "shader:" + material.shader.resource_path
	return material.get_class()

func batch_rows(stage: Node3D, raw := false) -> Array:
	var rows: Array = []
	for batch in stage.render_batches:
		if not is_instance_valid(batch.node):
			continue
		var node: MultiMeshInstance3D = batch.node
		var mesh: Mesh = node.multimesh.mesh
		# Imported meshes are shared resources; generated quads are compared by shape.
		var mesh_key := "%s#%d" % [mesh.resource_path, mesh.get_instance_id()] if not mesh.resource_path.is_empty() or not mesh is PrimitiveMesh \
			else "%s:%s" % [mesh.get_class(), str(mesh.get_aabb())]
		var head := "%s|%s|%s|%s|%s" % [mesh_key, material_key(node.material_override), str(batch.total),
			JSON.stringify(batch.layer), str(node.cast_shadow)]
		if raw:
			var used: PackedFloat32Array = node.multimesh.buffer.slice(0, int(batch.visible) * 12) if node.visible else PackedFloat32Array()
			rows.append(head + "|" + str(node.visible) + "|" + str(hash(used)))
			continue
		var instances: Array = []
		if node.visible:
			var buffer: PackedFloat32Array = node.multimesh.buffer
			for i in int(batch.visible):
				var values: Array = []
				for j in 12:
					values.append(snappedf(buffer[i * 12 + j], 0.0001))
				instances.append(str(values))
		instances.sort()
		rows.append(head + "|" + str(node.visible) + "|" + str(instances.hash()))
	rows.sort()
	return rows

func node_rows(parent: Node3D) -> Array:
	var rows: Array = []
	for child: Node3D in parent.get_children():
		var overrides: Array = []
		for mesh: MeshInstance3D in child.find_children("*", "MeshInstance3D", true, false):
			overrides.append(material_key(mesh.material_override))
		rows.append("%s|%s|%s|%s" % [child.scene_file_path, var_to_str(child.transform.origin), str(child.transform.basis.get_scale().snappedf(0.0001)), str(overrides)])
	rows.sort()
	return rows

func marker_rows(markers: Array) -> Array:
	var rows: Array = markers.map(func(m): return "%s|%s|%s" % [m.get("id", ""), m.kind, var_to_str(m.position)])
	rows.sort()
	return rows

func snapshot(stage: Node3D) -> Dictionary:
	return {"batches": batch_rows(stage), "buildings": node_rows(stage.buildings), "workers": node_rows(stage.workers),
		"markers": marker_rows(stage.place_markers), "plots": marker_rows(stage.empty_plots),
		"trees": stage.selectable_trees.map(func(t): return t.id), "standing": stage.standing_tree_cells.size(),
		"parade": stage.parade_slots.map(func(s): return var_to_str(s.position)),
		"road": var_to_str(stage.city_road_mesh.mesh.get_faces()) if is_instance_valid(stage.city_road_mesh) else ""}

func compare(label: String, before: Node3D, after: Node3D) -> void:
	for zoom in [32.0, 70.0, 110.0]:
		for stage in [before, after]:
			stage.target = Vector3(4, 0, -6)
			stage.zoom = zoom
			stage.update_camera(0, true)
			stage.update_visible_batches()
		var a := snapshot(before)
		var b := snapshot(after)
		for key in a:
			check(a[key] == b[key], "%s zoom=%d: %s differs from 0.5.9" % [label, zoom, key])

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var original = load("res://tests/reference059/landscape.gd")
	var candidate = load("res://src/landscape.gd")
	var before = original.new()
	var after = candidate.new()
	root.add_child(before)
	root.add_child(after)
	var state: Dictionary = data.demo.duplicate(true)
	await before.setup(data, state, "city", {})
	await after.setup(data, state, "city", {})
	compare("initial", before, after)
	var steps: Array = []
	# 1. Building upgrade: no vegetation change.
	steps.append(func(s): s.city.buildings[1].level = 2)
	# 2. Construction order on a free plot (scaffold appears).
	steps.append(func(s): s.city.kingdom.order = {"kind": "build", "plotId": "v1-5", "type": "RES-02"})
	# 3. Trees felled.
	steps.append(func(s): s.city.progress.felled = [data.woods[3].id, data.woods[40].id, data.woods[400].id])
	# 4. New building placed and plot cleared (vegetation exclusions change).
	steps.append(func(s):
		s.city.kingdom.order = null
		s.city.kingdom.clearedPlots.append("v1-5")
		s.city.buildings.append({"id": "building-v1-5", "type": "RES-02", "plotId": "v1-5", "level": 1}))
	# 5. A grove cleared.
	steps.append(func(s): s.city.progress.cleared = [data.clearings[0].id])
	# 6. Troops trained: parade only.
	steps.append(func(s): s.city.military.owned = {"ENG-01": 6, "ENG-03": 4})
	# 7. Unrelated state echo (poll with identical city).
	steps.append(func(s): s.serverTime = float(s.serverTime) + 800.0)
	var rebuilds_before: int = after.vegetation_rebuilds
	var ground_before: int = after.ground_rebuilds
	var index := 0
	var vegetation_steps: Array = []
	for step: Callable in steps:
		index += 1
		state = state.duplicate(true)
		step.call(state)
		var counted: int = after.vegetation_rebuilds
		before.present(state)
		after.present(state)
		if after.vegetation_rebuilds != counted:
			vegetation_steps.append(index)
		compare("step %d" % index, before, after)
	check(vegetation_steps == [3, 4, 5], "Vegetation rebuilt on unexpected steps: " + str(vegetation_steps))
	check(after.ground_rebuilds - ground_before == 2, "Ground cover rebuilt %d times, expected 2 (plot + grove)" % (after.ground_rebuilds - ground_before))
	var vegetation_total: int = after.vegetation_rebuilds - rebuilds_before
	before.free()
	after.free()
	await process_frame
	# World map: identical batches at several poses after the time-sliced build.
	var world_before = original.new()
	var world_after = candidate.new()
	root.add_child(world_before)
	root.add_child(world_after)
	await world_before.setup(data, data.demo, "world", {})
	await world_after.setup(data, data.demo, "world", {})
	check(world_before.render_batches.size() == world_after.render_batches.size(), "World batch count differs from 0.5.9")
	for pose in [[Vector3.ZERO, 60.0, 0.0], [Vector3(40, 0, -30), 100.0, 0.7], [Vector3(-60, 0, 50), 260.0, 2.1], [Vector3(10, 0, 10), 45.0, -1.2]]:
		for stage in [world_before, world_after]:
			stage.target = pose[0]
			stage.zoom = pose[1]
			stage.world_yaw = pose[2]
			stage.update_camera(0, true)
			stage.update_visible_batches()
		check(batch_rows(world_before, true) == batch_rows(world_after, true), "World batches differ from 0.5.9 at zoom %d" % int(pose[1]))
		check(marker_rows(world_before.place_markers) == marker_rows(world_after.place_markers), "World markers differ")
		check(marker_rows(world_before.empty_plots) == marker_rows(world_after.empty_plots), "World plots differ")
	print("QA_CITY_PARITY steps=", steps.size(), " vegetation_rebuilds=", vegetation_total,
		" checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
