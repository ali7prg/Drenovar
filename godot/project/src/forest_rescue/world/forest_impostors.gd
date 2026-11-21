extends Node
## Fixed-view tree impostors for the city camera.
##
## The city camera never rotates (orthographic, constant offset (75, 83, 75)), so each tree
## variant is rendered once from exactly that direction under the scene's sun (4 yaw steps per
## variant) into one atlas. Distant trees then become camera-plane quads (2 triangles each) in a
## single MultiMesh; INSTANCE_CUSTOM.a selects the atlas cell. The bake uses a LINEAR tonemap
## (the impostor shader is unshaded, the city FILMIC tonemap then applies once, like the 3D
## painted trees) and the quads also cast shadows (they face the sun in the shadow pass).
## Requires a rendering device; in headless runs `available` stays false and the 3D LOD2
## meshes are used instead.

const SHADER := preload("res://src/forest_rescue/world/forest_impostor.gdshader")
const CAMERA_OFFSET := Vector3(75, 83, 75)
const YAWS := 4
const CELL_PIXELS := 320
const BAKE_VERSION := "painted_v4c_species"
## Offline bake shipped in the pack (iPhone: no impostor bake while the forest loads): the atlas PNG
## (imported lossless with mipmaps, the same CELL_PIXELS cells) + the cell table, written by any
## rendering run started with `-- --ship-impostors` when the signature changed. Loaded directly when its
## signature matches; else the user:// cache; else a runtime bake (fallback, then cached).
const SHIPPED_DIR := "res://assets/forest_rescue/impostors/"
const SHIPPED_PNG := SHIPPED_DIR + "forest_impostors.png"
const SHIPPED_JSON := SHIPPED_DIR + "forest_impostors.json"

static var _atlas: Texture2D
static var source := ""                   # shipped | cache | baked (QA / perf report)
static var _cells: Dictionary = {}        # mesh key -> {first_cell, size: Vector2 (world w,h), center: Vector3}
static var _grid := 1

var available := false
var material: ShaderMaterial
var quad: ArrayMesh


static func camera_basis() -> Basis:
	var forward := -CAMERA_OFFSET.normalized()
	var right := forward.cross(Vector3.UP).normalized()
	var up := right.cross(forward).normalized()
	return Basis(right, up, -forward)


func can_render() -> bool:
	return DisplayServer.get_name() != "headless" and RenderingServer.get_rendering_device() != null


## meshes: Array of [key: String, mesh: Mesh]. sun_rotation: the city sun's rotation (radians).
## signature: export-safe content signature (ForestWorld: bake keys, looks, kit json / shader digests);
## editor_check: kit GLB md5s (editor only: an exported pack has no raw .glb), stored with the shipped bake.
func bake(meshes: Array, sun_rotation: Vector3, environment: Environment, signature := "", editor_check := {}) -> void:
	var digest := ("%s|%s|%d|%d|%.4f,%.4f,%.4f" % [signature, BAKE_VERSION, CELL_PIXELS, YAWS,
		sun_rotation.x, sun_rotation.y, sun_rotation.z]).md5_text()
	var cache := "user://forest_rescue_v1_impostors_%s" % digest
	if _atlas == null and not signature.is_empty():
		await _load_shipped(digest, editor_check)
		if _atlas == null:
			_load_cache(cache)
			if _atlas != null:
				source = "cache"
	var pending: Array = []
	for entry in meshes:
		if not _cells.has(entry[0]):
			pending.append(entry)
	if not pending.is_empty() and can_render():
		await _render(pending, sun_rotation, environment)
		source = "baked"
		if not signature.is_empty():
			_save_cache(cache)
			if OS.get_cmdline_user_args().has("--ship-impostors"):
				_save_shipped(digest, editor_check)
	available = _atlas != null and not _cells.is_empty()
	if available:
		material = ShaderMaterial.new()
		material.shader = SHADER
		material.set_shader_parameter("atlas", _atlas)
		material.set_shader_parameter("grid", float(_grid))
		quad = _make_quad()


func has_impostor(key: String) -> bool:
	return available and _cells.has(key)


## Instance transform + custom (r/g = tree base x/z for the fog cull, a = atlas cell).
func instance_for(key: String, origin: Vector3, yaw: float, scale: float) -> Array:
	var info: Dictionary = _cells[key]
	var step := int(roundi(fposmod(yaw, TAU) / TAU * YAWS)) % YAWS
	var basis := camera_basis()
	var size: Vector2 = info.size * scale
	var center: Vector3 = Basis(Vector3.UP, step * TAU / YAWS) * (info.center * scale)
	var transform := Transform3D(Basis(basis.x * size.x, basis.y * size.y, basis.z), origin + center)
	return [transform, Color(origin.x, origin.z, 1.0, float(info.first_cell + step))]


func _make_quad() -> ArrayMesh:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3(-0.5, -0.5, 0), Vector3(0.5, -0.5, 0), Vector3(0.5, 0.5, 0), Vector3(-0.5, 0.5, 0)])
	arrays[Mesh.ARRAY_NORMAL] = PackedVector3Array([Vector3.BACK, Vector3.BACK, Vector3.BACK, Vector3.BACK])
	arrays[Mesh.ARRAY_TEX_UV] = PackedVector2Array([Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)])
	arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 2, 1, 0, 3, 2])
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, material)
	return mesh


func _render(pending: Array, sun_rotation: Vector3, environment: Environment) -> void:
	var total := _cells.size() / 1 + pending.size() * YAWS
	var existing := 0
	for key in _cells:
		existing += YAWS
	total = existing + pending.size() * YAWS
	_grid = maxi(1, ceili(sqrt(float(total))))
	var atlas_image := Image.create(_grid * CELL_PIXELS, _grid * CELL_PIXELS, false, Image.FORMAT_RGBA8)
	atlas_image.fill(Color(0, 0, 0, 0))
	if _atlas != null:
		var old := _atlas.get_image()
		old.decompress()
		if old.has_mipmaps():
			old.clear_mipmaps()
		atlas_image.blit_rect(old, Rect2i(Vector2i.ZERO, old.get_size().min(atlas_image.get_size())), Vector2i.ZERO)
	var basis := camera_basis()
	var viewports: Array = []
	var cell := existing
	for entry in pending:
		var mesh: Mesh = entry[1]
		var aabb := mesh.get_aabb()
		var info := {"first_cell": cell, "size": Vector2.ZERO, "center": aabb.get_center()}
		# Projected extent over all yaw steps (conservative square-ish frame).
		var extent := Vector2.ZERO
		for y in YAWS:
			var rotation := Basis(Vector3.UP, y * TAU / YAWS)
			for corner in 8:
				var p := rotation * (aabb.get_endpoint(corner) - aabb.get_center())
				extent = extent.max(Vector2(absf(p.dot(basis.x)), absf(p.dot(basis.y))))
		var size := maxf(extent.x, extent.y) * 2.08
		info.size = Vector2(size, size)
		for y in YAWS:
			var viewport := SubViewport.new()
			viewport.size = Vector2i(CELL_PIXELS, CELL_PIXELS)
			viewport.transparent_bg = true
			viewport.own_world_3d = true
			viewport.msaa_3d = Viewport.MSAA_4X
			viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
			var holder := Node3D.new()
			viewport.add_child(holder)
			var instance := MeshInstance3D.new()
			instance.mesh = mesh
			instance.rotation.y = y * TAU / YAWS
			holder.add_child(instance)
			var sun := DirectionalLight3D.new()
			sun.rotation = sun_rotation
			sun.light_color = Color("#ffe4b8")
			sun.light_energy = 1.85
			sun.shadow_enabled = true
			holder.add_child(sun)
			var camera := Camera3D.new()
			camera.projection = Camera3D.PROJECTION_ORTHOGONAL
			camera.size = size
			camera.near = 0.05
			camera.far = 400.0
			var center := Basis(Vector3.UP, y * TAU / YAWS) * aabb.get_center()
			camera.transform = Transform3D(basis, center + basis.z * 150.0)
			var env := environment.duplicate() if environment != null else Environment.new()
			env.background_mode = Environment.BG_CLEAR_COLOR
			env.fog_enabled = false
			env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
			env.tonemap_exposure = 1.0
			env.glow_enabled = false
			camera.environment = env
			holder.add_child(camera)
			camera.current = true
			add_child(viewport)
			viewports.append([viewport, cell + y])
		_cells[entry[0]] = info
		cell += YAWS
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	for item in viewports:
		var viewport: SubViewport = item[0]
		var index: int = item[1]
		var image := viewport.get_texture().get_image()
		if image != null and not image.is_empty():
			image.convert(Image.FORMAT_RGBA8)
			atlas_image.blit_rect(image, Rect2i(0, 0, CELL_PIXELS, CELL_PIXELS),
				Vector2i((index % _grid) * CELL_PIXELS, (index / _grid) * CELL_PIXELS))
		viewport.queue_free()
	atlas_image.fix_alpha_edges()   # bleed colour into transparent texels (no dark mip halos)
	atlas_image.generate_mipmaps()
	_atlas = ImageTexture.create_from_image(atlas_image)


func _load_shipped(digest: String, editor_check: Dictionary) -> void:
	if not FileAccess.file_exists(SHIPPED_JSON) or not ResourceLoader.exists(SHIPPED_PNG):
		return
	var info: Variant = JSON.parse_string(FileAccess.get_file_as_string(SHIPPED_JSON))
	if not info is Dictionary or String(info.get("signature", "")) != digest:
		return
	if OS.has_feature("editor") and not editor_check.is_empty() and info.get("kitMd5", {}) != editor_check:
		push_warning("ForestImpostors: the shipped atlas predates a kit GLB change; baking at runtime (re-ship with --ship-impostors)")
		return
	# threaded: the city keeps animating while the atlas streams in
	if ResourceLoader.load_threaded_request(SHIPPED_PNG, "Texture2D") != OK:
		return
	while ResourceLoader.load_threaded_get_status(SHIPPED_PNG) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		await get_tree().process_frame
	var texture := ResourceLoader.load_threaded_get(SHIPPED_PNG) as Texture2D
	if texture == null:
		return
	_atlas = texture
	_grid = int(info.grid)
	_cells = {}
	for key in info.cells:
		var c: Dictionary = info.cells[key]
		_cells[key] = {"first_cell": int(c.first), "size": Vector2(float(c.w), float(c.h)),
			"center": Vector3(float(c.cx), float(c.cy), float(c.cz))}
	source = "shipped"


func _save_shipped(digest: String, editor_check: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SHIPPED_DIR))
	var image := _atlas.get_image()
	if image.has_mipmaps():
		image.clear_mipmaps()
	image.save_png(ProjectSettings.globalize_path(SHIPPED_PNG))
	var cells := {}
	for key in _cells:
		var c: Dictionary = _cells[key]
		cells[key] = {"first": c.first_cell, "w": c.size.x, "h": c.size.y, "cx": c.center.x, "cy": c.center.y, "cz": c.center.z}
	var file := FileAccess.open(ProjectSettings.globalize_path(SHIPPED_JSON), FileAccess.WRITE)
	file.store_string(JSON.stringify({"signature": digest, "bakeVersion": BAKE_VERSION, "cellPixels": CELL_PIXELS,
		"yaws": YAWS, "grid": _grid, "cells": cells, "kitMd5": editor_check}, "\t") + "\n")
	file.close()
	print("FOREST_IMPOSTORS_SHIPPED grid=%d cells=%d -> %s (import it: lossless, mipmaps)" % [_grid, cells.size(), SHIPPED_PNG])


func _load_cache(base: String) -> void:
	if not FileAccess.file_exists(base + ".json") or not FileAccess.file_exists(base + ".png"):
		return
	var info: Variant = JSON.parse_string(FileAccess.get_file_as_string(base + ".json"))
	var image := Image.load_from_file(base + ".png")
	if not info is Dictionary or image == null or image.is_empty():
		return
	image.generate_mipmaps()
	_atlas = ImageTexture.create_from_image(image)
	_grid = int(info.grid)
	for key in info.cells:
		var c: Dictionary = info.cells[key]
		_cells[key] = {"first_cell": int(c.first), "size": Vector2(float(c.w), float(c.h)),
			"center": Vector3(float(c.cx), float(c.cy), float(c.cz))}


func _save_cache(base: String) -> void:
	var image := _atlas.get_image()
	if image.has_mipmaps():
		image.clear_mipmaps()
	image.save_png(base + ".png")
	var cells := {}
	for key in _cells:
		var c: Dictionary = _cells[key]
		cells[key] = {"first": c.first_cell, "w": c.size.x, "h": c.size.y, "cx": c.center.x, "cy": c.center.y, "cz": c.center.z}
	var file := FileAccess.open(base + ".json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"grid": _grid, "cells": cells}))


static func atlas_texture() -> Texture2D:
	return _atlas


## QA toggle of the forest colour grade on the impostor cards (see ForestKit.set_grade_enabled).
func set_grade_enabled(enabled: bool) -> void:
	if material != null:
		material.set_shader_parameter("grade_on", enabled)
