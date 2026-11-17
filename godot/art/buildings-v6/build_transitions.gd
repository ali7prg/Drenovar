extends SceneTree
## Transition-only outgoing V scenes. The displayed legacy V assets remain unchanged.
## Full capital replacement at VI: timber is dismantled roof-first before new stone
## pieces arrive. Existing city_works.gd consumes row.upgrade_from_path via site_view.
const OUT := "res://assets/city/architecture-v6/"
const AssetIO = preload("res://../art/buildings-v6/asset_io.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT + "transitions"))
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OUT + "manifest.json"))
	var report := []
	for type in manifest.levels:
		var source_path := "res://assets/city/architecture-v2/levels/%s-5.tscn" % type
		var original: Node3D = load(source_path).instantiate()
		var source_mesh: ArrayMesh = original.get_node("Architecture").mesh
		var top := maxf(1.0, source_mesh.get_aabb().end.y)
		# Patch only UV2.y in a raw-buffer duplicate. Rebuilding ArrayMesh surfaces
		# would re-encode their packed normals; this preserves their exact bit pattern.
		var surfaces: Array = source_mesh.get("_surfaces").duplicate(true)
		for si in source_mesh.get_surface_count():
			var source_arrays := source_mesh.surface_get_arrays(si)
			var vertices: PackedVector3Array = source_arrays[Mesh.ARRAY_VERTEX]
			var format := source_mesh.surface_get_format(si)
			assert((format & Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES) == 0)
			var stride := RenderingServer.mesh_surface_get_format_attribute_stride(format, vertices.size())
			var uv_offset := RenderingServer.mesh_surface_get_format_offset(format, vertices.size(), Mesh.ARRAY_TEX_UV2)
			var raw: PackedByteArray = surfaces[si].attribute_data.duplicate()
			for i in range(0, vertices.size(), 3):
				var h := clampf(((vertices[i].y + vertices[i + 1].y + vertices[i + 2].y) / 3.0) / top, 0.0, 1.0)
				var leave := 0.04 + 0.1 * (1.0 - h)
				for corner in 3:
					raw.encode_float((i + corner) * stride + uv_offset + 4, leave)
			surfaces[si].attribute_data = raw
		var mesh := ArrayMesh.new()
		# Godot's serialised ArrayMesh storage preserves raw packed normals; a GPU-only
		# attribute update would not be saved by the headless renderer.
		mesh.set("_surfaces",surfaces)
		assert(mesh.get_surface_count() == source_mesh.get_surface_count())
		for si in mesh.get_surface_count():
			var a := source_mesh.surface_get_arrays(si)
			var b := mesh.surface_get_arrays(si)
			for field in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_NORMAL,Mesh.ARRAY_COLOR]:
				assert(a[field] == b[field], "Outgoing transition altered legacy visible geometry")
			for uv: Vector2 in b[Mesh.ARRAY_TEX_UV2]:
				assert(uv.y >= 0.03999 and uv.y <= 0.14001)
		var key := "%s-5-to-6-from" % type
		var mesh_path := OUT + "transitions/" + key + ".res"
		var scene_path := OUT + "transitions/" + key + ".tscn"
		AssetIO.save_mesh(mesh, mesh_path)
		mesh.take_over_path(mesh_path)
		original.name = key.replace("-", "_")
		original.get_node("Architecture").mesh = mesh
		original.set_meta("for_upgrade_only", true)
		original.set_meta("from_level",5)
		original.set_meta("to_level",6)
		original.set_meta("art_version",manifest.version)
		var packed := PackedScene.new()
		assert(packed.pack(original) == OK)
		AssetIO.save_scene(packed, scene_path)
		manifest.levels[type]["6"]["upgrade_from_path"] = scene_path
		report.append({"type":type,"from":5,"to":6,"path":scene_path,"status":"passed",
			"legacy_geometry_unchanged":true,"leave_clock_min":0.04,"leave_clock_max":0.14})
		original.free()
	assert(report.size() == 27)
	var file := FileAccess.open(OUT + "manifest.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest, "\t") + "\n")
	file.close()
	file = FileAccess.open(OUT + "transition-validation.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"status":"passed","transitions":report,"legacy_files_modified":0},"\t") + "\n")
	file.close()
	print("V_VI_TRANSITIONS count=",report.size()," geometry_preserved=true")
	quit(0)
