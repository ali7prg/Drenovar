extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func submitted(stage: Node) -> Vector2i:
	var counts := Vector2i.ZERO
	for batch in stage.render_batches:
		if not batch.node.visible:
			continue
		var mesh: Mesh = batch.node.multimesh.mesh
		var triangles := 0
		for surface in mesh.get_surface_count():
			var indices: int = mesh.surface_get_array_index_len(surface) if mesh is ArrayMesh else 0
			var vertices: int = mesh.surface_get_array_len(surface) if mesh is ArrayMesh else 6
			triangles += int((indices if indices > 0 else vertices) / 3.0)
		counts += Vector2i(batch.visible, triangles * batch.visible)
	return counts

func check_batches(before: Node, after: Node) -> bool:
	for index in before.render_batches.size():
		var old: Dictionary = before.render_batches[index]
		var candidate: Dictionary = after.render_batches[index]
		if old.total != candidate.total or old.layer != candidate.layer:
			return false
		if old.node.visible != candidate.node.visible:
			return false
		if not old.node.visible:
			continue
		if old.mask != candidate.mask or old.visible != candidate.visible:
			return false
		var used: int = old.visible * 12
		if old.node.multimesh.buffer.slice(0, used) != candidate.node.multimesh.buffer.slice(0, used):
			return false
	return true

func run() -> void:
	root.size = Vector2i(1366, 630)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var old_scene = load("res://tests/reference053/landscape.gd")
	var new_scene = load("res://src/landscape.gd")
	var comparisons := 0
	for scene in ["city", "world"]:
		var before = old_scene.new()
		var after = new_scene.new()
		root.add_child(before)
		root.add_child(after)
		await before.setup(data, data.demo, scene, {})
		await after.setup(data, data.demo, scene, {})
		for zoom: float in ([32.0, 70.0, 110.0] if scene == "city" else [60.0, 100.0, 260.0]):
			var counts := [Vector2i.ZERO, Vector2i.ZERO]
			var times := [[], []]
			for i in 20:
				for j in 2:
					var stage = [before, after][j]
					stage.target = Vector3(5 + sin(i * 0.25) * 30, 0, -4 + cos(i * 0.25) * 18)
					stage.zoom = zoom
					stage.world_yaw = 0.5 if scene == "world" else 0.0
					var start := Time.get_ticks_usec()
					stage.update_camera(0, true)
					times[j].append((Time.get_ticks_usec() - start) / 1000.0)
					counts[j] += submitted(stage)
				if before.render_batches.size() != after.render_batches.size() or not check_batches(before, after):
					push_error("Placement, LOD or visibility changed in %s at %.0f" % [scene, zoom])
					quit(1)
					return
				comparisons += after.render_batches.size()
			for samples in times:
				samples.sort()
			print(JSON.stringify({"scene": scene, "zoom": zoom, "instances_before": counts[0].x, "instances_after": counts[1].x, "triangles_before": counts[0].y, "triangles_after": counts[1].y, "cull_before_ms": times[0][10], "cull_after_ms": times[1][10]}))
		before.free()
		after.free()
	print("QA_OPTIMIZATION comparisons=", comparisons, " failures=0")
	quit()
