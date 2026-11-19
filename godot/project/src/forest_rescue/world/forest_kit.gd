extends RefCounted
## Forest kit loader. Picks up kit GLBs automatically when the asset agents deliver them:
##   res://assets/forest_rescue/forest/forest_kit.json  (if present: explicit species → files)
##   res://assets/forest_rescue/forest/<asset_id>*.glb   (fallback discovery by file name)
## Inside a GLB, meshes named *_LOD0/_LOD1/_LOD2 (optionally *_v1.._v3_*) give variants/LODs.
## Wind vertex colours (COLOR_0): R branch sway, G leaf flutter, B phase, A ambient occlusion.
## Kit v2: every surface gets the painted-light material (forest_painted.gdshaderinc) with k from
## <asset>.meta.json paintedLightMix (lf_foliage_vol 0.5); meshes keep their authored real-metre
## size (meta heightM/footprintM) — the world layer scales instances, it never normalises.
## A species that is missing falls back to a clearly logged legacy stand-in so the layout is
## still visible; kit_status() reports exactly what is missing.

const KIT_DIR := "res://assets/forest_rescue/forest/"
const KIT_JSON := KIT_DIR + "forest_kit.json"
const WIND_SHADER := preload("res://src/forest_rescue/world/forest_wind.gdshader")
const CUTOUT_SHADER := preload("res://src/forest_rescue/world/forest_wind_cutout.gdshader")
const VOLUME_LIGHT_MIX := 0.5            # lf_foliage_vol (forest_kit.json "shading")
const DEFAULT_LIGHT_MIX := 0.3

## Legacy stand-ins (game.json model keys / cityDetails keys), used only when a kit asset is absent.
const LEGACY_TREES := {
	"lf_env_golden_oak": ["tree3", "tree4", "tree5"],
	"lf_env_dark_pine": ["tree0", "tree1", "tree2"],
	"lf_env_birch": ["tree1", "tree0", "tree2"],
	"lf_env_willow": ["tree4", "tree5", "tree3"],
	"lf_env_hollow_oak": ["tree5", "tree3", "tree4"],
}
const LEGACY_UNDERSTORY := {
	"fern": ["fern"], "reed": ["tall_reeds"], "bramble": ["berry_bush", "round_bush"],
	"rock": ["mossy_rocks"], "trunk": ["fallen_branches"], "stump": ["tree_stump"],
}

static var _cache: Dictionary = {}      # asset key -> entry (shared across scene rebuilds)
static var _kit_json: Dictionary = {}
static var _kit_json_mtime := -1

var data: Dictionary                    # game.json (for legacy stand-ins)
var scenery_material: Material          # landscape material for legacy city details
var missing: Dictionary = {}            # asset id -> reason
var loaded: Dictionary = {}             # asset id -> source path
var wind_enabled := true
static var materials: Array = []         # every painted ShaderMaterial (canopy fade uniforms)
static var light_dir := Vector3(0.45, 0.74, 0.5)   # direction TO the sun (set by ForestWorld)
static var _metas: Dictionary = {}


func _init(game_data: Dictionary, legacy_detail_material: Material) -> void:
	data = game_data
	scenery_material = legacy_detail_material


static func clear_cache() -> void:
	_cache.clear()
	_kit_json.clear()
	_kit_json_mtime = -1
	_metas.clear()


## <asset_id>.meta.json (cached): paintedLightMix, heroScale, recommendedScale, variants{heightM, footprintM}.
static func meta(asset_id: String) -> Dictionary:
	if _metas.has(asset_id):
		return _metas[asset_id]
	var path := KIT_DIR + asset_id + ".meta.json"
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
	_metas[asset_id] = parsed if parsed is Dictionary else {}
	return _metas[asset_id]


static func light_mix(asset_id: String) -> float:
	return float(meta(asset_id).get("paintedLightMix", DEFAULT_LIGHT_MIX))


func kit_status() -> Dictionary:
	return {"loaded": loaded.duplicate(), "missing": missing.duplicate(), "kitJson": FileAccess.file_exists(KIT_JSON)}


## Returns {variants: [{lods: [Mesh, Mesh, Mesh], tris: [int,int,int], height: float, source}], kit: bool}
func tree_asset(asset_id: String) -> Dictionary:
	var key := "tree:" + asset_id
	if _cache.has(key) and (_cache[key].kit or not _kit_available(asset_id)):
		_note(asset_id, _cache[key])
		return _cache[key]
	var entry := _load_kit(asset_id)
	if entry.is_empty():
		entry = _legacy_tree(asset_id)
	_cache[key] = entry
	_note(asset_id, entry)
	return entry


func understory_asset(kind: String, asset_id: String) -> Dictionary:
	var key := "under:" + kind
	if _cache.has(key) and (_cache[key].kit or not _kit_available(asset_id)):
		_note(asset_id + "#" + kind, _cache[key])
		return _cache[key]
	var entry := _load_kit(asset_id)
	if not entry.is_empty():
		# Named variants (reed_v1, fern_v2 …): keep the ones matching the requested kind.
		var matching: Array = entry.variants.filter(func(v): return String(v.get("name", "")).begins_with(kind))
		if not matching.is_empty():
			entry = entry.duplicate()
			entry.variants = matching
	if entry.is_empty():
		entry = _legacy_detail(kind)
	_cache[key] = entry
	_note(asset_id + "#" + kind, entry)
	return entry


## Legacy stump for felled resource trees (not a tree model).
func stump_asset() -> Dictionary:
	var kit := _load_kit("lf_env_stump")
	if not kit.is_empty():
		return kit
	return _legacy_detail("stump")


func _note(asset_id: String, entry: Dictionary) -> void:
	if entry.get("kit", false):
		loaded[asset_id] = entry.get("source", "")
		missing.erase(asset_id)
	else:
		missing[asset_id] = "kit GLB not delivered yet → legacy stand-in " + str(entry.get("source", ""))


func _kit_available(asset_id: String) -> bool:
	return not _kit_files(asset_id).is_empty()


func _read_kit_json() -> Dictionary:
	if not FileAccess.file_exists(KIT_JSON):
		return {}
	var mtime := FileAccess.get_modified_time(KIT_JSON)
	if mtime != _kit_json_mtime:
		_kit_json_mtime = mtime
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(KIT_JSON))
		_kit_json = parsed if parsed is Dictionary else {}
	return _kit_json


## Candidate GLB files for an asset id (kit json first, then name discovery).
func _kit_files(asset_id: String) -> PackedStringArray:
	var files := PackedStringArray()
	var kit := _read_kit_json()
	for section in ["species", "assets", "items", "trees", "understory"]:
		var block: Variant = kit.get(section)
		var entries: Array = []
		if block is Dictionary:
			for id in block:
				var value: Variant = block[id]
				if value is Dictionary:
					var copy: Dictionary = value.duplicate()
					copy["id"] = copy.get("id", id)
					entries.append(copy)
		elif block is Array:
			entries = block
		for item in entries:
			if not item is Dictionary or String(item.get("id", "")) != asset_id:
				continue
			for field in ["glb", "path", "file"]:
				if item.get(field) is String:
					files.append(_res(item[field]))
			for variant in item.get("variants", []):
				if variant is Dictionary:
					for field in ["glb", "path", "file"]:
						if variant.get(field) is String:
							files.append(_res(variant[field]))
				elif variant is String and variant.ends_with(".glb"):
					files.append(_res(variant))
	if files.is_empty():
		var dir := DirAccess.open(KIT_DIR)
		if dir != null:
			for file in dir.get_files():
				if file.ends_with(".glb") and file.begins_with(asset_id):
					files.append(KIT_DIR + file)
	var existing := PackedStringArray()
	for file in files:
		if ResourceLoader.exists(file) and not existing.has(file):
			existing.append(file)
	existing.sort()
	return existing


func _res(path: String) -> String:
	if path.begins_with("res://"):
		return path
	return KIT_DIR + path.get_file() if not path.contains("/") else "res://" + path.trim_prefix("godot/project/")


func _load_kit(asset_id: String) -> Dictionary:
	var files := _kit_files(asset_id)
	if files.is_empty():
		return {}
	var variants := {}       # variant number -> [Mesh, Mesh, Mesh]
	var lod_regex := RegEx.create_from_string("(?i)_LOD(\\d)")
	var variant_regex := RegEx.create_from_string("(?i)_v(\\d)")
	# Kit GLBs lay variants side by side for display; meta.json carries that offset per variant.
	var offsets := {}
	var meta_path := KIT_DIR + asset_id + ".meta.json"
	if FileAccess.file_exists(meta_path):
		var meta: Variant = JSON.parse_string(FileAccess.get_file_as_string(meta_path))
		if meta is Dictionary and meta.get("variants") is Dictionary:
			for key in meta.variants:
				var info: Dictionary = meta.variants[key]
				var number := int(String(key).trim_prefix("v"))
				var offset: Array = info.get("display_offset_gltf", [0, 0, 0])
				offsets[number] = Vector3(float(offset[0]), float(offset[1]), float(offset[2]))
	var named := {}
	if FileAccess.file_exists(meta_path):
		var meta: Variant = JSON.parse_string(FileAccess.get_file_as_string(meta_path))
		if meta is Dictionary and meta.get("variants") is Dictionary:
			named = meta.variants
	if not named.is_empty():
		var result_named := _load_named(files, named, light_mix(asset_id))
		if not result_named.is_empty():
			return result_named
	for file in files:
		var scene: Variant = load(file)
		if not scene is PackedScene:
			continue
		var root: Node = scene.instantiate()
		var file_variant := variant_regex.search(file.get_file())
		for part: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			if part.mesh == null:
				continue
			var name := String(part.name)
			var lod_match := lod_regex.search(name)
			var lod := int(lod_match.get_string(1)) if lod_match != null else 0
			var variant_match := variant_regex.search(name)
			var variant := int(variant_match.get_string(1)) if variant_match != null else (int(file_variant.get_string(1)) if file_variant != null else 1)
			if not variants.has(variant):
				variants[variant] = [null, null, null]
			if lod <= 2:
				var transform := Transform3D.IDENTITY
				var node: Node = part
				while node != null and node != root:
					if node is Node3D:
						transform = (node as Node3D).transform * transform
					node = node.get_parent()
				transform.origin -= offsets.get(variant, Vector3.ZERO)
				variants[variant][lod] = _wind_mesh(part.mesh, transform, light_mix(asset_id))
		root.free()
	if variants.is_empty():
		return {}
	var result := {"kit": true, "source": ", ".join(files), "variants": []}
	var keys := variants.keys()
	keys.sort()
	for key in keys:
		var lods: Array = variants[key]
		for i in 3:
			if lods[i] == null:
				lods[i] = lods[i - 1] if i > 0 and lods[i - 1] != null else lods.filter(func(m): return m != null)[0]
		result.variants.append(_variant_entry(lods, file_label(files)))
	return result


## Variants described by <asset>.meta.json: {name: {nodes: [LOD0, LOD1, LOD2], display_offset_gltf}}.
func _load_named(files: PackedStringArray, named: Dictionary, k := DEFAULT_LIGHT_MIX) -> Dictionary:
	var parts := {}
	var roots: Array = []
	for file in files:
		var scene: Variant = load(file)
		if not scene is PackedScene:
			continue
		var root: Node = scene.instantiate()
		roots.append(root)
		for part: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			var transform := Transform3D.IDENTITY
			var node: Node = part
			while node != null and node != root:
				if node is Node3D:
					transform = (node as Node3D).transform * transform
				node = node.get_parent()
			parts[String(part.name)] = [part.mesh, transform]
	var result := {"kit": true, "source": file_label(files), "variants": []}
	var keys := named.keys()
	keys.sort()
	for key in keys:
		var info: Dictionary = named[key]
		var offset_list: Array = info.get("display_offset_gltf", [0, 0, 0])
		var offset := Vector3(float(offset_list[0]), float(offset_list[1]), float(offset_list[2]))
		var lods: Array = []
		for node_name in info.get("nodes", []):
			if parts.has(node_name) and parts[node_name][0] != null:
				var transform: Transform3D = parts[node_name][1]
				transform.origin -= offset
				lods.append(_wind_mesh(parts[node_name][0], transform, k))
		if lods.is_empty():
			continue
		while lods.size() < 3:
			lods.append(lods[-1])
		var entry := _variant_entry(lods.slice(0, 3), result.source)
		entry.name = String(key)
		# Authored real-metre size (meta heightM / footprintM) when present.
		if info.has("heightM"):
			entry.height = float(info.heightM)
		var footprint: Variant = info.get("footprintM")
		if footprint is Array and footprint.size() >= 2:
			entry.radius = maxf(float(footprint[0]), float(footprint[1])) * 0.5
		result.variants.append(entry)
	for root in roots:
		root.free()
	return result if not result.variants.is_empty() else {}


func file_label(files: PackedStringArray) -> String:
	return files[0].get_file() if files.size() == 1 else "%d files" % files.size()


func _variant_entry(lods: Array, source: String) -> Dictionary:
	var tris := []
	for mesh: Mesh in lods:
		tris.append(mesh_triangles(mesh))
	var aabb: AABB = lods[0].get_aabb()
	return {"lods": lods, "tris": tris, "height": aabb.end.y, "radius": maxf(aabb.size.x, aabb.size.z) * 0.5, "source": source}


static func mesh_triangles(mesh: Mesh) -> int:
	var total := 0
	if mesh is ArrayMesh:
		var array_mesh := mesh as ArrayMesh
		for s in array_mesh.get_surface_count():
			var count: int = array_mesh.surface_get_array_index_len(s)
			total += (count if count > 0 else array_mesh.surface_get_array_len(s)) / 3
	return total


## Copies a kit mesh with painted ShaderMaterials (texture maps carried over from the GLB).
func _wind_mesh(mesh: Mesh, transform: Transform3D, k := DEFAULT_LIGHT_MIX) -> Mesh:
	var source: Mesh = mesh
	var copy := ArrayMesh.new()
	for s in source.get_surface_count():
		var arrays := source.surface_get_arrays(s)
		if transform != Transform3D.IDENTITY:
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for i in vertices.size():
				vertices[i] = transform * vertices[i]
			arrays[Mesh.ARRAY_VERTEX] = vertices
			if arrays[Mesh.ARRAY_NORMAL] != null:
				var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
				for i in normals.size():
					normals[i] = (transform.basis * normals[i]).normalized()
				arrays[Mesh.ARRAY_NORMAL] = normals
		copy.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var original := source.surface_get_material(s)
		copy.surface_set_material(s, painted_material(original, arrays[Mesh.ARRAY_COLOR] != null, k, wind_enabled))
	return copy


static var _painted: Dictionary = {}     # (material id, flags) -> shared ShaderMaterial


## Painted-light override for a GLB material (kit trees/understory and landmarks share it).
## k: meta paintedLightMix; lf_foliage_vol surfaces use 0.5. Cached per source material.
static func painted_material(original: Material, has_colors: bool, k: float, wind := true) -> Material:
	if not original is BaseMaterial3D:
		return original
	var base := original as BaseMaterial3D
	var key := "%d:%s:%s:%.3f:%s" % [base.get_instance_id(), has_colors, base.resource_name, k, wind]
	if _painted.has(key) and is_instance_valid(_painted[key]):
		return _painted[key]
	var name := String(base.resource_name).to_lower()
	var cutout := base.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED
	var material := ShaderMaterial.new()
	material.shader = CUTOUT_SHADER if cutout else WIND_SHADER
	material.resource_name = base.resource_name
	material.set_shader_parameter("albedo_texture", base.albedo_texture)
	material.set_shader_parameter("albedo_color", base.albedo_color)
	material.set_shader_parameter("use_albedo_texture", base.albedo_texture != null)
	material.set_shader_parameter("alpha_cut", base.alpha_scissor_threshold if base.alpha_scissor_threshold > 0.0 else 0.5)
	material.set_shader_parameter("painted_light_mix", VOLUME_LIGHT_MIX if name.contains("_vol") else k)
	material.set_shader_parameter("light_dir_world", light_dir.normalized())
	material.set_shader_parameter("use_ao", has_colors)
	material.set_shader_parameter("vertex_wind", has_colors and wind)
	materials.append(material)
	_painted[key] = material
	return material


## Replaces every surface material under `root` by its painted override (landmarks, arena).
static func paint_scene(root: Node, k: float) -> void:
	for part: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		for s in part.mesh.get_surface_count():
			var original: Material = part.get_active_material(s)
			var has_colors := false
			if part.mesh is ArrayMesh:
				has_colors = (part.mesh.surface_get_format(s) & Mesh.ARRAY_FORMAT_COLOR) != 0
			part.set_surface_override_material(s, painted_material(original, has_colors, k, false))


## Pushes fade circles (Vector4 x, ground y, z, radius) to every kit/impostor material.
static func set_fade_circles(circles: Array, extra: Array = []) -> void:
	var packed: Array[Vector4] = []
	for c in circles.slice(0, 8):
		packed.append(c)
	var count := packed.size()
	while packed.size() < 8:
		packed.append(Vector4.ZERO)
	for material: ShaderMaterial in materials + extra:
		if material != null:
			material.set_shader_parameter("fade_circles", packed)
			material.set_shader_parameter("fade_count", count)


func _legacy_tree(asset_id: String) -> Dictionary:
	var keys: Array = LEGACY_TREES.get(asset_id, ["tree0"])
	var result := {"kit": false, "source": "legacy " + ",".join(keys), "variants": []}
	for key in keys:
		var lods := []
		for suffix in ["", "mid", "far"]:
			var spec: Dictionary = data.models.get(key + suffix, data.models[key])
			lods.append(_scene_mesh(spec.path, null))
		result.variants.append(_variant_entry(lods, "legacy " + key))
	return result


func _legacy_detail(kind: String) -> Dictionary:
	var keys: Array = LEGACY_UNDERSTORY.get(kind, ["fern"])
	var result := {"kit": false, "source": "legacy " + ",".join(keys), "variants": []}
	for key in keys:
		var mesh := _scene_mesh(data.cityDetails[key], scenery_material)
		result.variants.append(_variant_entry([mesh, mesh, mesh], "legacy " + key))
	return result


## First mesh of a scene with its node transform baked in (and an optional material).
func _scene_mesh(path: String, material: Material) -> Mesh:
	var key := "mesh:" + path + ":" + str(material.get_instance_id() if material != null else 0)
	if _cache.has(key):
		return _cache[key]
	var root: Node = load(path).instantiate()
	var parts := root.find_children("*", "MeshInstance3D", true, false)
	var result := ArrayMesh.new()
	for part: MeshInstance3D in parts:
		var transform := Transform3D.IDENTITY
		var node: Node = part
		while node != null and node != root:
			if node is Node3D:
				transform = (node as Node3D).transform * transform
			node = node.get_parent()
		for s in part.mesh.get_surface_count():
			var arrays := part.mesh.surface_get_arrays(s)
			if transform != Transform3D.IDENTITY:
				var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
				for i in vertices.size():
					vertices[i] = transform * vertices[i]
				arrays[Mesh.ARRAY_VERTEX] = vertices
			result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			var surface_material: Material = material if material != null else part.get_active_material(s)
			if surface_material is BaseMaterial3D and material == null:
				surface_material = surface_material.duplicate()
				surface_material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
			result.surface_set_material(result.get_surface_count() - 1, surface_material)
	root.free()
	_cache[key] = result
	return result
