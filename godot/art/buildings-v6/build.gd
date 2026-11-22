extends SceneTree
## Run from repo root:
## godot --headless --path godot/project -s ../art/buildings-v6/build.gd -- [--only=ECO-05] [--skip-web]
## This builder never writes the legacy I–V scenes/materials or assets/game.json.

const Kit = preload("res://tools/architecture/arch_kit.gd")
const LegacyBuild = preload("res://tools/architecture/build.gd")
const Recipes = preload("res://../art/buildings-v6/recipes.gd")
const AssetIO = preload("res://../art/buildings-v6/asset_io.gd")
const OUT := "res://assets/city/architecture-v6/"
var copied_textures := {}

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var only := ""
	var web := true
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--only="):
			only = arg.trim_prefix("--only=")
		if arg == "--skip-web":
			web = false
	for folder in ["levels", "units", "web", "web-staging"]:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT + folder))
	for folder in ["web", "web-staging"]:
		var ignored := FileAccess.open(OUT + folder + "/.gdignore", FileAccess.WRITE)
		ignored.store_string("# Web delivery assets; native game uses the .res/.tscn counterparts.\n")
		ignored.close()
	var table := {}
	var report := []
	for entry in Recipes.ENTRIES:
		if not only.is_empty() and entry.type != only:
			continue
		var previous: ArrayMesh = null
		for L in range(6, 12):
			var key := "%s-%d" % [entry.type, L]
			var kit = Kit.new(hash(entry.type))
			Callable(Recipes, entry.fn).call(kit, L)
			var mesh: ArrayMesh = kit.bake()
			if previous != null:
				var prev_keys := LegacyBuild.mesh_keys(previous)
				var cur_keys := LegacyBuild.mesh_keys(mesh)
				mesh = LegacyBuild.relink(mesh, func(key2, uv, _a, _b, _c):
					return Vector2(0.0 if prev_keys.has(key2) else uv.x, uv.y))
				var top: float = maxf(1.0, previous.get_aabb().end.y)
				previous = LegacyBuild.relink(previous, func(key2, uv, a, b, c):
					var h := clampf(((a.y + b.y + c.y) / 3.0) / top, 0.0, 1.0)
					return Vector2(uv.x, 2.0 if cur_keys.has(key2) else 0.12 + 0.83 * (0.1 + 0.46 * pow(h, 0.85)) - 0.02))
				AssetIO.save_mesh(previous, OUT + "levels/%s-%d.res" % [entry.type, L - 1])
			var mesh_path := OUT + "levels/" + key + ".res"
			var scene_path := OUT + "levels/" + key + ".tscn"
			AssetIO.save_mesh(mesh, mesh_path)
			mesh.take_over_path(mesh_path)
			var node := Node3D.new()
			node.name = key.replace("-", "_")
			node.set_meta("series", entry.id + "_" + entry.name.replace(" ", ""))
			node.set_meta("economy_version", "DRENOVAR-V6-C1.0")
			node.set_meta("art_version", Recipes.VERSION)
			node.set_meta("stage", Recipes.STAGES[L])
			node.set_meta("lanes", kit.lanes)
			node.set_meta("worker_offset", Vector3(0, 0, 5.9))
			var visual := MeshInstance3D.new()
			visual.name = "Architecture"
			visual.mesh = mesh
			node.add_child(visual)
			visual.owner = node
			var packed := PackedScene.new()
			packed.pack(node)
			AssetIO.save_scene(packed, scene_path)
			var b: AABB = mesh.get_aabb()
			var materials := []
			for si in mesh.get_surface_count():
				materials.append(mesh.surface_get_name(si))
			var row := {"id":entry.id, "type":entry.type, "level":L, "path":scene_path,
				"web":"/assets/city/architecture-v6/web/" + key + ".glb", "scale":1.0,
				"series":entry.id + "_" + entry.name.replace(" ", ""), "worker":[0, 0, 5.9],
				"stage":Recipes.STAGES[L], "triangles":kit.triangle_count(), "materials":materials,
				"bounds":{"min":[b.position.x,b.position.y,b.position.z], "max":[b.end.x,b.end.y,b.end.z]},
				"natural_fields":entry.id in ["B09", "B22", "B25"],
				"site":{"center":[0,0,0],"radius":6.1}}
			table.get_or_add(entry.type, {})[str(L)] = row
			report.append(row)
			node.free()
			previous = mesh
			print("BUILT ", key, " triangles=", kit.triangle_count(), " materials=", materials.size())
	var units := {}
	if only.is_empty() or only == "SIEGE-RAM-01":
		units["SIEGE-RAM-01"] = build_ram()
	var manifest := {"version":Recipes.VERSION,"economy_version":"DRENOVAR-V6-C1.0",
		"source":"13_BUILDING_PASSPORTS_RU.md","levels":table,"states":report.size(),
		"units":units,
		"legacy_preservation":"All architecture-v2 files remain byte-identical; see legacy-sha256.json",
		"web_textures":"Full source resolution; PBR textures shared externally by GLBs",
		"web_mapping":"Dominant-face planar UV equivalent of native triplanar on planar architecture; sloped-face seams require visual review"}
	var manifest_path := OUT + ("manifest.json" if only.is_empty() else "manifest-" + only + ".json")
	var file := FileAccess.open(manifest_path, FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest, "\t") + "\n")
	file.close()
	if web:
		for row in report + units.values():
			var key: String = row.id if row.get("kind", "") == "unit" else "%s-%d" % [row.type, row.level]
			var native_mesh: ArrayMesh = ResourceLoader.load(String(row.path).replace(".tscn", ".res"), "ArrayMesh", ResourceLoader.CACHE_MODE_IGNORE)
			export_web(native_mesh, key)
	print("V6_ASSETS states=", report.size(), " units=", units.size(), " native=passed web_staging=", web)
	quit(0)

func build_ram() -> Dictionary:
	const ID := "SIEGE-RAM-01"
	var kit = Kit.new(hash(ID))
	Recipes.ram_display(kit,Vector3.ZERO)
	var mesh: ArrayMesh = kit.bake()
	var mesh_path := OUT + "units/" + ID + ".res"
	var scene_path := OUT + "units/" + ID + ".tscn"
	AssetIO.save_mesh(mesh,mesh_path)
	mesh.take_over_path(mesh_path)
	var root_node := Node3D.new()
	root_node.name = ID.replace("-","_")
	root_node.set_meta("unit_id",ID)
	root_node.set_meta("art_version",Recipes.VERSION)
	root_node.set_meta("forward","+Z")
	var visual := MeshInstance3D.new()
	visual.name = "Architecture"
	visual.mesh = mesh
	root_node.add_child(visual)
	visual.owner = root_node
	var scene := PackedScene.new()
	assert(scene.pack(root_node) == OK)
	AssetIO.save_scene(scene,scene_path)
	root_node.free()
	var materials := []
	for si in mesh.get_surface_count():
		materials.append(mesh.surface_get_name(si))
	var b := mesh.get_aabb()
	print("BUILT_UNIT ",ID," triangles=",kit.triangle_count())
	return {"id":ID,"kind":"unit","name":"Battering ram","path":scene_path,
		"web":"/assets/city/architecture-v6/web/" + ID + ".glb","scale":1.0,"forward":"+Z",
		"static":true,"source":"recipes.ram_display","triangles":kit.triangle_count(),"materials":materials,
		"bounds":{"min":[b.position.x,b.position.y,b.position.z],"max":[b.end.x,b.end.y,b.end.z]}}

func export_web(native_mesh: ArrayMesh, key: String) -> void:
	## glTF has no triplanar material. Bake per-face projection at the same metre scale
	## and retain the full PBR textures, normals, vertex contact shading and mesh detail.
	var mesh := ArrayMesh.new()
	for si in native_mesh.get_surface_count():
		var arr := native_mesh.surface_get_arrays(si)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var mat: StandardMaterial3D = native_mesh.surface_get_material(si).duplicate()
		# Godot's exporter falls back to an empty image name for imported JPEGs.
		# Explicit stable names avoid overwriting every albedo with textures/.png.
		for texture in [mat.albedo_texture, mat.normal_texture, mat.roughness_texture]:
			if texture != null:
				texture.resource_name = texture.resource_path.get_file().get_basename()
		var uv := PackedVector2Array()
		uv.resize(verts.size())
		for i in verts.size():
			var p: Vector3 = verts[i] * mat.uv1_scale
			var n := normals[i].abs()
			if n.y >= n.x and n.y >= n.z:
				uv[i] = Vector2(p.x, p.z)
			elif n.x >= n.z:
				uv[i] = Vector2(p.z, -p.y)
			else:
				uv[i] = Vector2(p.x, -p.y)
		arr[Mesh.ARRAY_TEX_UV] = uv
		var colors: PackedColorArray = arr[Mesh.ARRAY_COLOR]
		for i in colors.size():
			colors[i].a = 1.0
		arr[Mesh.ARRAY_COLOR] = colors
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		mat.uv1_triplanar = false
		mat.uv1_scale = Vector3.ONE
		mesh.surface_set_material(si, mat)
		mesh.surface_set_name(si, native_mesh.surface_get_name(si))
	mesh.regen_normal_maps()
	write_raw_gltf(mesh, key)
	print("WEB_STAGING ", key)

func write_raw_gltf(mesh: ArrayMesh, key: String) -> void:
	## Export exact mesh arrays directly. Godot's stock exporter repeatedly transcodes
	## every texture and aliases unnamed JPEG albedos; this writer shares original
	## images and keeps float32 data. Final packer validates every compressed buffer.
	var json := {"asset":{"version":"2.0","generator":"DRENOVAR-V6-C1.0-ART1 Godot exact-array exporter"},
		"scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"name":key,"mesh":0}],"meshes":[{"name":key,"primitives":[]}],
		"buffers":[],"bufferViews":[],"accessors":[],"materials":[],"images":[],"textures":[],
		"samplers":[{"magFilter":9729,"minFilter":9987,"wrapS":10497,"wrapT":10497}]}
	var bytes := PackedByteArray()
	for si in mesh.get_surface_count():
		var a := mesh.surface_get_arrays(si)
		var p: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var primitive := {"attributes":{},"material":si,"mode":4}
		for info in [["POSITION",Mesh.ARRAY_VERTEX,"VEC3",12], ["NORMAL",Mesh.ARRAY_NORMAL,"VEC3",12],
			["TANGENT",Mesh.ARRAY_TANGENT,"VEC4",16], ["TEXCOORD_0",Mesh.ARRAY_TEX_UV,"VEC2",8],
			["TEXCOORD_1",Mesh.ARRAY_TEX_UV2,"VEC2",8], ["COLOR_0",Mesh.ARRAY_COLOR,"VEC4",16]]:
			var raw: PackedByteArray = a[info[1]].to_byte_array()
			var view: int = json.bufferViews.size()
			json.bufferViews.append({"buffer":0,"byteOffset":bytes.size(),"byteLength":raw.size(),"byteStride":info[3],"target":34962})
			bytes.append_array(raw)
			var accessor := {"bufferView":view,"componentType":5126,"count":p.size(),"type":info[2]}
			if info[0] == "POSITION":
				var low := p[0]
				var high := p[0]
				for point in p:
					low = low.min(point)
					high = high.max(point)
				accessor["min"] = [low.x,low.y,low.z]
				accessor["max"] = [high.x,high.y,high.z]
			primitive.attributes[info[0]] = json.accessors.size()
			json.accessors.append(accessor)
		# Godot's clockwise front faces become glTF's counter-clockwise faces.
		var indices := PackedInt32Array()
		indices.resize(p.size())
		for i in range(0, p.size(), 3):
			indices[i] = i
			indices[i + 1] = i + 2
			indices[i + 2] = i + 1
		var raw_indices := indices.to_byte_array()
		var index_view: int = json.bufferViews.size()
		json.bufferViews.append({"buffer":0,"byteOffset":bytes.size(),"byteLength":raw_indices.size(),"target":34963})
		bytes.append_array(raw_indices)
		primitive.indices = json.accessors.size()
		json.accessors.append({"bufferView":index_view,"componentType":5125,"count":indices.size(),"type":"SCALAR"})
		json.meshes[0].primitives.append(primitive)
		var mat: StandardMaterial3D = mesh.surface_get_material(si)
		var color := mat.albedo_color.srgb_to_linear()
		var material := {"name":mesh.surface_get_name(si),"pbrMetallicRoughness":{
			"baseColorFactor":[color.r,color.g,color.b,color.a],"metallicFactor":mat.metallic,"roughnessFactor":mat.roughness}}
		if mat.albedo_texture:
			material.pbrMetallicRoughness["baseColorTexture"] = {"index":gltf_texture(json, mat.albedo_texture)}
		if mat.roughness_texture:
			# Source roughness textures are grayscale: glTF G matches the native G channel.
			# Textured architecture has metallicFactor=0, so the B channel is immaterial.
			assert(is_zero_approx(mat.metallic))
			material.pbrMetallicRoughness["metallicRoughnessTexture"] = {"index":gltf_texture(json, mat.roughness_texture)}
		if mat.normal_enabled and mat.normal_texture:
			material["normalTexture"] = {"index":gltf_texture(json, mat.normal_texture),"scale":mat.normal_scale}
		if mat.emission_enabled:
			var ec := mat.emission.srgb_to_linear()
			material["emissiveFactor"] = [ec.r,ec.g,ec.b]
			material["extensions"] = {"KHR_materials_emissive_strength":{"emissiveStrength":mat.emission_energy_multiplier}}
			json["extensionsUsed"] = ["KHR_materials_emissive_strength"]
		json.materials.append(material)
	json.buffers.append({"uri":key + ".bin","byteLength":bytes.size()})
	var binary := FileAccess.open(OUT + "web-staging/" + key + ".bin", FileAccess.WRITE)
	binary.store_buffer(bytes)
	binary.close()
	var file := FileAccess.open(OUT + "web-staging/" + key + ".gltf", FileAccess.WRITE)
	file.store_string(JSON.stringify(json) + "\n")
	file.close()

func gltf_texture(json: Dictionary, texture: Texture2D) -> int:
	var source := texture.resource_path
	var name := source.get_file()
	var target := OUT + "web-staging/textures/" + name
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT + "web-staging/textures"))
	if not copied_textures.has(source):
		assert(DirAccess.copy_absolute(ProjectSettings.globalize_path(source), ProjectSettings.globalize_path(target)) == OK)
		copied_textures[source] = true
	var index: int = json.images.size()
	json.images.append({"uri":"textures/" + name})
	json.textures.append({"source":index,"sampler":0})
	return index
