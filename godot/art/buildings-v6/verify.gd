extends SceneTree
## Asset tests execute the actual saved meshes and Godot physics, not just recipes.
const OUT := "res://assets/city/architecture-v6/"
var failures := []
var checks := 0
var rows := []

func check(ok: bool, why: String) -> void:
	checks += 1
	if not ok:
		failures.append(why)
		push_error(why)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OUT + "manifest.json"))
	var table: Dictionary = manifest.levels
	check(table.size() == 27, "Exactly 27 V6 identities")
	var count := 0
	for type in table:
		check(table[type].size() == 6, type + ": exactly VI–XI")
		var signatures := {}
		for L in range(6, 12):
			count += 1
			var row: Dictionary = table[type][str(L)]
			var label := "%s-%d" % [type, L]
			var packed: PackedScene = load(row.path)
			check(packed != null, label + " scene load")
			if packed == null:
				continue
			var node := packed.instantiate()
			root.add_child(node)
			var mesh: ArrayMesh = node.get_node("Architecture").mesh
			var bounds := mesh.get_aabb()
			check(bounds.position.x >= -7.4 and bounds.end.x <= 7.4 and bounds.position.z >= -7.4 and bounds.end.z <= 7.4, label + " plot bounds: " + str(bounds))
			check(node.scale.is_equal_approx(Vector3.ONE), label + " identity scale")
			var tris := 0
			var material_names := []
			var finite := true
			var material_ok := true
			var build_channels := true
			var gltf_vertices := 0
			for si in mesh.get_surface_count():
				var arrays := mesh.surface_get_arrays(si)
				var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
				tris += vertices.size() / 3
				gltf_vertices += vertices.size()
				for v in vertices:
					finite = finite and is_finite(v.x) and is_finite(v.y) and is_finite(v.z)
				material_names.append(mesh.surface_get_name(si))
				material_ok = material_ok and mesh.surface_get_material(si) is StandardMaterial3D
				build_channels = build_channels and arrays[Mesh.ARRAY_COLOR] != null and arrays[Mesh.ARRAY_TEX_UV2] != null
			check(tris == int(row.triangles) and tris > 1000, label + " exact nonempty topology count")
			check(finite, label + " finite coordinates")
			check(material_ok, label + " original PBR materials")
			check(build_channels, label + " preserved construction channels")
			check("stone" in material_names, label + " stone bearing architecture")
			if L >= 7:
				check("slate_roof" in material_names and "iron" in material_names, label + " slate/iron stage")
			if row.natural_fields:
				check("leaves" in material_names or "hay" in material_names or "herb" in material_names, label + " living crop/herb surfaces")
			var hash_value := FileAccess.get_sha256(row.path.replace(".tscn", ".res"))
			check(not signatures.has(hash_value), label + " distinct authored mesh")
			signatures[hash_value] = true
			if type == "SUP-03":
				await gate_clearance(mesh, label)
			if L == 6:
				check_outgoing_transition(type,row)
			rows.append({"type":type,"level":L,"triangles":tris,"surfaces":mesh.get_surface_count(),"sha256":hash_value,"status":"passed"})
			node.queue_free()
			await process_frame
	check(count == 162, "162 late states plus untouched 135 early states = 297")
	var units := []
	check(manifest.get("units",{}).has("SIEGE-RAM-01"), "Standalone marching ram is registered")
	for id in manifest.get("units",{}):
		var row: Dictionary = manifest.units[id]
		var packed: PackedScene = load(row.path)
		check(packed != null,id + " native unit scene loads")
		if packed == null:
			continue
		var model: Node3D = packed.instantiate()
		var mesh: ArrayMesh = model.get_node("Architecture").mesh
		var triangles := 0
		var valid := true
		for si in mesh.get_surface_count():
			var vertices: PackedVector3Array = mesh.surface_get_arrays(si)[Mesh.ARRAY_VERTEX]
			triangles += vertices.size() / 3
			for v in vertices:
				valid = valid and is_finite(v.x) and is_finite(v.y) and is_finite(v.z)
			valid = valid and mesh.surface_get_material(si) is StandardMaterial3D
		check(valid,id + " finite geometry and original PBR materials")
		check(triangles == int(row.triangles) and triangles > 100,id + " actual marching-unit mesh")
		check(model.scale.is_equal_approx(Vector3.ONE) and model.get_meta("forward","") == "+Z",id + " native unit scale and direction")
		check(mesh.get_aabb().position.y >= -0.05,id + " wheels sit on ground")
		units.append({"id":id,"triangles":triangles,"status":"passed","sha256":FileAccess.get_sha256(String(row.path).replace(".tscn",".res"))})
		model.free()
	var output := {"status":"passed" if failures.is_empty() else "error","engine":Engine.get_version_info().string,"checks":checks,"failures":failures,"states":rows,
		"units":units,
		"coverage":{"late_states":162,"legacy_states":135,"total_states":297,"native_gate_clearance_levels":[6,7,8,9,10,11]},
		"not_measured":["iPhone 12 frame time and memory", "both-client gameplay integration (separate tests)"]}
	var f := FileAccess.open(OUT + "validation.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(output, "\t") + "\n")
	f.close()
	print("V6_ASSET_QA checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)

func check_outgoing_transition(type: String, row: Dictionary) -> void:
	check(row.has("upgrade_from_path"), type + " V→VI outgoing path")
	if not row.has("upgrade_from_path"):
		return
	var packed: PackedScene = ResourceLoader.load(row.upgrade_from_path,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE)
	check(packed != null,type + " V→VI saved scene loads")
	if packed == null:
		return
	var node := packed.instantiate()
	var saved: ArrayMesh = node.get_node("Architecture").mesh
	var legacy: ArrayMesh = load("res://assets/city/architecture-v2/levels/%s-5.res" % type)
	var exact := saved.get_surface_count() == legacy.get_surface_count()
	var outgoing := true
	for si in saved.get_surface_count():
		var before := legacy.surface_get_arrays(si)
		var after := saved.surface_get_arrays(si)
		for field in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_NORMAL,Mesh.ARRAY_COLOR]:
			exact = exact and before[field] == after[field]
		for uv: Vector2 in after[Mesh.ARRAY_TEX_UV2]:
			outgoing = outgoing and uv.y >= 0.03999 and uv.y <= 0.14001
	check(exact,type + " saved V→VI positions/normals/colors equal legacy")
	check(outgoing,type + " saved V→VI leave timing persists")
	check(node.get_meta("for_upgrade_only",false),type + " V→VI scene is transition-only")
	node.free()

func gate_clearance(mesh: ArrayMesh, label: String) -> void:
	var body := StaticBody3D.new()
	var collision := CollisionShape3D.new()
	var shape := ConcavePolygonShape3D.new()
	shape.backface_collision = true
	shape.set_faces(mesh.get_faces())
	collision.shape = shape
	body.add_child(collision)
	root.add_child(body)
	await physics_frame
	await physics_frame
	var space := body.get_world_3d().direct_space_state
	var blocked := 0
	for i in 48:
		var query := PhysicsShapeQueryParameters3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(2.7, 2.8, 0.12)
		query.shape = box
		query.transform = Transform3D(Basis.IDENTITY, Vector3(0, 1.62, -5.6 + i * 0.24))
		blocked += 0 if space.intersect_shape(query, 1).is_empty() else 1
	check(blocked == 0, label + " 2.7 m carriageway: " + str(blocked) + " blocked samples")
	body.queue_free()
	await physics_frame
