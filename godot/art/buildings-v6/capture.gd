extends SceneTree
## Fixed light/camera renderer for VI–XI acceptance sheets. No game quality setting is edited.
## DISPLAY=:99 godot --rendering-method gl_compatibility --path godot/project -s ../art/buildings-v6/capture.gd -- --out=/tmp/v6-architecture-captures
const OUT := "res://assets/city/architecture-v6/"
const SIZE := Vector2i(480, 420)
const Recipes = preload("res://../art/buildings-v6/recipes.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var out := "/tmp/v6-architecture-captures"
	var only := ""
	var unit := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		if arg.begins_with("--only="):
			only = arg.trim_prefix("--only=")
		if arg.begins_with("--unit="):
			unit = arg.trim_prefix("--unit=")
	DirAccess.make_dir_recursive_absolute(out)
	var manifest_path := OUT + "manifest.json"
	if not FileAccess.file_exists(manifest_path) and not only.is_empty():
		manifest_path = OUT + "manifest-" + only + ".json"
	var manifest := {"levels":{}}
	if FileAccess.file_exists(manifest_path):
		manifest = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	else:
		# Native generation finishes before the slower web texture export.
		for entry in Recipes.ENTRIES:
			var levels := {}
			for L in range(6, 12):
				levels[str(L)] = {"path":OUT + "levels/%s-%d.tscn" % [entry.type, L]}
			manifest.levels[entry.type] = levels
	var viewport := SubViewport.new()
	viewport.size = SIZE
	viewport.msaa_3d = Viewport.MSAA_4X
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var holder := Node3D.new()
	viewport.add_child(holder)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 18.5
	camera.position = Vector3(15, 17, 20)
	holder.add_child(camera)
	camera.look_at(Vector3(0, 2.7, 0))
	camera.current = true
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, -30, 0)
	sun.light_color = Color("#ffe6c2")
	sun.light_energy = 1.7
	sun.shadow_enabled = true
	holder.add_child(sun)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#24312c")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d6dfe8")
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	camera.environment = env
	if not unit.is_empty():
		camera.size = 5.0
		camera.position = Vector3(4,4.5,6)
		camera.look_at(Vector3(0,1.1,0))
		var unit_row: Dictionary = manifest.get("units",{}).get(unit,{})
		if unit_row.is_empty():
			var unit_manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OUT + "manifest-" + unit + ".json"))
			unit_row = unit_manifest.units[unit]
		var model: Node3D = load(unit_row.path).instantiate()
		holder.add_child(model)
		for i in 6:
			await process_frame
		await RenderingServer.frame_post_draw
		viewport.get_texture().get_image().save_png(out + "/" + unit + ".png")
		model.queue_free()
		print("CAPTURED_UNIT ",unit)
		quit(0)
		return
	for type in manifest.levels:
		if not only.is_empty() and only != type:
			continue
		var sheet := Image.create(SIZE.x * 6, SIZE.y, false, Image.FORMAT_RGBA8)
		for L in range(6, 12):
			var model: Node3D = load(manifest.levels[type][str(L)].path).instantiate()
			holder.add_child(model)
			for i in 5:
				await process_frame
			await RenderingServer.frame_post_draw
			var capture := viewport.get_texture().get_image()
			capture.convert(Image.FORMAT_RGBA8)
			capture.save_png(out + "/%s-%d.png" % [type, L])
			sheet.blit_rect(capture, Rect2i(Vector2i.ZERO, SIZE), Vector2i((L - 6) * SIZE.x, 0))
			model.queue_free()
			await process_frame
		sheet.save_png(out + "/" + type + "-VI-XI.png")
		print("CAPTURED ", type)
	viewport.queue_free()
	quit(0)
