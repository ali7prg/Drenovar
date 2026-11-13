extends SceneTree
## QA for architecture-v2 building levels (godot --headless --path project -s qa_architecture.gd).
## 1. every reworked level scene loads, has geometry and stays inside its plot;
## 2. landscape.present() picks the right visual for every type/level on construction,
##    step-by-step upgrade and after a save round-trip (JSON);
## 3. shared models and overlays used by untouched levels are byte-identical to the snapshot;
## 4. passages (gates, ramps, decks, stairs) are swept with a unit/cart volume against the
##    real triangle geometry: no obstacle inside the clearance and no step in the floor.

const PLOT_HALF := 7.4
const MAX_STEP := 0.07
const MAX_GRADE := 0.2

var failures: Array[String] = []
var checks := 0
var data: Dictionary

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	data = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var table: Dictionary = data.get("levelModels", {})
	var count := 0
	for type in table:
		count += (table[type] as Dictionary).size()
	var carried := 0
	for type in table:
		for level in table[type]:
			carried += 1 if table[type][level].get("carried", false) else 0
	# 40 positions from CHANGES.md + unchanged neighbours that carry them forward
	check(count - carried == 40, "Expected 40 reworked levels from CHANGES.md, found %d" % (count - carried))
	print("LEVEL_SCENES changes=%d carried=%d" % [count - carried, carried])
	check_untouched_assets(table)
	for type in table:
		for level in table[type]:
			await check_level(type, int(level), table[type][level])
	await check_presentation(table)
	print("QA_ARCHITECTURE checks=%d failures=%d" % [checks, failures.size()])
	for f in failures:
		print("FAIL ", f)
	quit(1 if failures.size() > 0 else 0)

# ---------------------------------------------------------------- 1 + 4
func check_level(type: String, level: int, entry: Dictionary) -> void:
	var scene: PackedScene = load(entry.path)
	check(scene != null, "%s-%d scene missing" % [type, level])
	if scene == null:
		return
	var inst: Node3D = scene.instantiate()
	root.add_child(inst)
	var meshes := inst.find_children("*", "MeshInstance3D", true, false)
	check(meshes.size() > 0, "%s-%d has no geometry" % [type, level])
	var bounds := AABB()
	var faces := PackedVector3Array()
	var new_faces := PackedVector3Array()
	for m: MeshInstance3D in meshes:
		var xf := m.global_transform
		var b := xf * m.get_aabb()
		if m.name == "Architecture":
			bounds = b if not bounds.has_volume() else bounds.merge(b)
		var f := m.mesh.get_faces()
		for i in f.size():
			f[i] = xf * f[i]
		faces.append_array(f)
		if m.name == "Architecture":
			new_faces.append_array(f)
	check(bounds.position.x >= -PLOT_HALF and bounds.end.x <= PLOT_HALF and bounds.position.z >= -PLOT_HALF and bounds.end.z <= PLOT_HALF,
		"%s-%d new geometry exceeds the plot: %s" % [type, level, str(bounds)])
	var lanes: Array = inst.get_meta("lanes", [])
	if not lanes.is_empty():
		await sweep_lanes(type, level, faces, lanes)
	await check_worker(type, level, new_faces, inst.get_meta("worker_offset", null))
	inst.queue_free()
	await process_frame

func sweep_lanes(type: String, level: int, faces: PackedVector3Array, lanes: Array) -> void:
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var concave := ConcavePolygonShape3D.new()
	concave.backface_collision = true
	concave.set_faces(faces)
	shape.shape = concave
	body.add_child(shape)
	root.add_child(body)
	await physics_frame
	await physics_frame
	var space := body.get_world_3d().direct_space_state
	for lane: Dictionary in lanes:
		var kind: String = lane.kind
		var width: float = maxf(0.4, float(lane.width))
		var height: float = float(lane.height)
		var points: Array[Vector3] = []
		var a: Vector3 = lane.from
		var b: Vector3 = lane.to
		if kind == "ring":
			# closed walk around a feature: from = centre, to = (radius x, 0, radius z)
			for i in 72:
				var t := TAU * i / 72.0
				points.append(a + Vector3(cos(t) * b.x, 0, sin(t) * b.z))
			points.append(points[0])
		else:
			var length := Vector2(b.x - a.x, b.z - a.z).length()
			var n := maxi(2, ceili(length / 0.1))
			for i in n + 1:
				points.append(a.lerp(b, float(i) / n))
		var floors: Array[float] = []
		var blocked := 0
		var first_block := ""
		for i in points.size():
			var p := points[i]
			var nxt := points[mini(i + 1, points.size() - 1)]
			var prv := points[maxi(i - 1, 0)]
			var dir := Vector3(nxt.x - prv.x, 0, nxt.z - prv.z).normalized()
			if dir.length_squared() < 0.5:
				dir = Vector3.FORWARD
			var side := Vector3(-dir.z, 0, dir.x)
			# floor = highest walkable surface under the lane (several rays: planks have gaps)
			var floor_y := 0.0
			for o in [-0.35, 0.0, 0.35]:
				for f in [-0.04, 0.04]:
					var q0: Vector3 = p + side * o * width + dir * f
					var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(q0.x, p.y + 0.45, q0.z), Vector3(q0.x, -0.5, q0.z)))
					if not hit.is_empty():
						floor_y = maxf(floor_y, hit.position.y)
			floors.append(floor_y)
			var box := BoxShape3D.new()
			box.size = Vector3(width, height - 0.25, 0.1)
			var q := PhysicsShapeQueryParameters3D.new()
			q.shape = box
			q.transform = Transform3D(Basis(side, Vector3.UP, dir), Vector3(p.x, floor_y + 0.2 + (height - 0.25) * 0.5, p.z))
			var rest := space.get_rest_info(q)
			if not rest.is_empty() or not space.intersect_shape(q, 1).is_empty():
				blocked += 1
				if first_block.is_empty():
					first_block = "lane %.2f,%.2f,%.2f contact %s" % [p.x, floor_y, p.z, str(rest.get("point", "?"))]
		var worst_step := 0.0
		var worst_grade := 0.0
		var step_at := Vector3.ZERO
		for i in range(1, floors.size()):
			if absf(floors[i] - floors[i - 1]) > worst_step:
				worst_step = absf(floors[i] - floors[i - 1])
				step_at = Vector3(points[i].x, floors[i], points[i].z)
		var spacing := 0.1 if kind != "ring" else TAU * maxf(b.x, b.z) / 72.0
		var win := maxi(1, roundi(0.5 / spacing))
		for i in range(win, floors.size()):
			worst_grade = maxf(worst_grade, absf(floors[i] - floors[i - win]) / (win * spacing))
		var tag := "%s-%d %s lane %s->%s" % [type, level, kind, str(a), str(b)]
		check(blocked == 0, "%s obstructed at %d samples (first %s)" % [tag, blocked, first_block])
		if kind != "stair" and kind != "rail":
			check(worst_step <= MAX_STEP, "%s has a step of %.3f m at %s" % [tag, worst_step, str(step_at)])
			check(worst_grade <= MAX_GRADE, "%s too steep (%.2f)" % [tag, worst_grade])
		print("LANE %s blocked=%d step=%.3f grade=%.3f samples=%d" % [tag, blocked, worst_step, worst_grade, points.size()])
	body.queue_free()
	await physics_frame

func check_worker(type: String, level: int, faces: PackedVector3Array, override: Variant) -> void:
	## Mirrors landscape.add_worker()/present_workers(): the worker's spot (or the hall
	## patrol ellipse) must not run into geometry added by the reworked level.
	var id: String = data.starterHall if type == "ECO-05" and level == 1 else data.types[type]
	var worker: String = {"hall":"c", "starterHall":"c", "warehouse":"c", "market27":"c", "quarry27":"c",
		"ironmine27":"c", "farm":"f", "lumber":"l", "smith":"s"}.get(id, "")
	if worker.is_empty() or faces.is_empty():
		return
	var offset := Vector3(3.2 if id == "farm" else (-3.4 if id == "lumber" else 0.0), 0.0, 2.8)
	if id in ["hall", "starterHall"]:
		offset.z = 4.1 if id == "starterHall" else 5.2
	if override is Vector3:
		offset = override
	var points: Array[Vector3] = [offset]
	if id in ["hall", "starterHall"]:
		points.clear()
		for i in 36:
			var phase := TAU * i / 36.0
			points.append(offset + Vector3(sin(phase) * 1.65, 0, cos(phase) * 0.42))
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var concave := ConcavePolygonShape3D.new()
	concave.backface_collision = true
	concave.set_faces(faces)
	shape.shape = concave
	body.add_child(shape)
	root.add_child(body)
	await physics_frame
	await physics_frame
	var space := body.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.28
	capsule.height = 1.55
	var hits := 0
	var first := ""
	for p in points:
		var q := PhysicsShapeQueryParameters3D.new()
		q.shape = capsule
		q.transform = Transform3D(Basis.IDENTITY, p + Vector3(0, 0.12 + 0.775, 0))
		var rest := space.get_rest_info(q)
		if not rest.is_empty():
			hits += 1
			if first.is_empty():
				first = "%s contact %s" % [str(p), str(rest.point)]
	check(hits == 0, "%s-%d worker (%s) collides with new geometry at %d spots (first %s)" % [type, level, id, hits, first])
	print("WORKER %s-%d %s points=%d hits=%d" % [type, level, id, points.size(), hits])
	body.queue_free()
	await physics_frame

# ---------------------------------------------------------------- 2
func check_presentation(table: Dictionary) -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	var stage = game.stage
	var plot_id: String = data.plots[0].id
	for type in data.types:
		var base_id: String = data.types[type]
		var state: Dictionary = game.state.duplicate(true)
		# construction (level 1) followed by every upgrade step, then a save round-trip
		for level in range(1, 6):
			state.city.buildings = [{"id":"qa-arch", "type":type, "plotId":plot_id, "level":level}]
			for mode in ["upgrade", "reload"]:
				var s: Dictionary = state if mode == "upgrade" else JSON.parse_string(JSON.stringify(state))
				if mode == "reload":
					# a loaded save starts from an empty city: drop the cached signature
					stage.geometries.erase("city_signature")
				stage.present(s)
				var expected := expected_paths(type, level, base_id, table)
				var got := []
				for child in stage.buildings.get_children():
					got.append(child.scene_file_path)
				var ok := true
				for e in expected:
					ok = ok and got.has(e)
				for g in got:
					var visual: bool = String(g).contains("architecture-v2") or String(g).contains("city-details") or (String(g).contains("/premium/") and not String(g).contains("Worker_"))
					if visual:
						ok = ok and expected.has(g)
				check(ok, "%s L%d (%s) expected %s got %s" % [type, level, mode, str(expected), str(got)])
	game.queue_free()
	await process_frame

func expected_paths(type: String, level: int, base_id: String, table: Dictionary) -> Array:
	var paths := []
	var base_type: String = type
	for definition in data.buildings:
		if definition.id == type:
			base_type = str(definition.get("base", type))
	# From town hall II (or with "walls and gate" built) the city wall stands; its main
	# gate is the B18 scene of the current walls-and-gate level (I when none is built).
	if (base_type == "ECO-05" and level >= 2) or base_type == "SUP-03":
		var gate_level := level if base_type == "SUP-03" else 1
		paths.append(table["SUP-03"][str(gate_level)].path)
		if base_type == "SUP-03":
			return paths
	var entry: Variant = table.get(type, {}).get(str(level))
	if entry is Dictionary:
		paths.append(entry.path)
		return paths
	var id: String = data.starterHall if type == "ECO-05" and level == 1 else base_id
	paths.append(data.models[id].path)
	var overlay: String = data.architecture.get(type, {}).get(str(level), "")
	if not overlay.is_empty():
		paths.append(overlay)
	return paths

# ---------------------------------------------------------------- 3
func check_untouched_assets(table: Dictionary) -> void:
	## Compares every shared base model and upgrade overlay with the sha256 recorded in the
	## original handoff manifest (docs/02_FILE_MANIFEST.json).
	var manifest_path := ProjectSettings.globalize_path("res://").path_join("../../docs/02_FILE_MANIFEST.json")
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	check(manifest is Array, "Original file manifest not readable: " + manifest_path)
	if not manifest is Array:
		return
	var digests := {}
	for item in manifest:
		if item is Dictionary and item.get("res_path") is String:
			digests[item.res_path] = item.sha256
	var shared := {}
	for key in data.models:
		var path: String = data.models[key].path
		if path.contains("/city/premium/"):
			shared[path] = true
	for type in data.architecture:
		for level in data.architecture[type]:
			shared[data.architecture[type][level]] = true
	shared[data.scaffold] = true
	var compared := 0
	for path in shared:
		if not digests.has(path):
			continue
		check(FileAccess.get_sha256(path) == digests[path], "Shared asset changed: %s" % path)
		compared += 1
	check(compared == shared.size(), "Only %d of %d shared assets found in the manifest" % [compared, shared.size()])
	print("SHARED_ASSETS compared=%d of %d" % [compared, shared.size()])
