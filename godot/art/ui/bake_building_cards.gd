extends SceneTree

# Renders a lit 3/4 portrait of every building model used by the city into
# assets/ui/buildings/<model key>.png (320x240, transparent background) for the
# construction window. Needs a renderer:
#   xvfb-run godot --rendering-driver opengl3 --path godot/project -s <copy of this script>

const SIZE := Vector2i(320, 240)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var out := "res://assets/ui/buildings"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var keys := {}
	for id in data.types:
		keys[data.types[id]] = true
	for key in keys:
		var path: String = data.models[key].path
		var viewport := SubViewport.new()
		viewport.size = SIZE * 2
		viewport.transparent_bg = true
		viewport.msaa_3d = Viewport.MSAA_4X
		viewport.own_world_3d = true
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(viewport)
		var holder := Node3D.new()
		viewport.add_child(holder)
		var model: Node3D = load(path).instantiate()
		holder.add_child(model)
		var box := AABB()
		for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
			var b := mesh.global_transform * mesh.get_aabb()
			box = b if box.size == Vector3.ZERO else box.merge(b)
		var camera := Camera3D.new()
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		camera.size = maxf(box.size.y * 1.25, maxf(box.size.x, box.size.z) * 1.05)
		var centre := box.get_center()
		camera.position = centre + Vector3(1.0, 0.82, 1.15).normalized() * (box.size.length() + 10.0)
		holder.add_child(camera)
		camera.look_at(centre)
		camera.current = true
		var sun := DirectionalLight3D.new()
		sun.rotation_degrees = Vector3(-42, -28, 0)
		sun.light_color = Color("#ffe6c2")
		sun.light_energy = 1.7
		holder.add_child(sun)
		var env := Environment.new()
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color("#d6dfe8")
		env.ambient_light_energy = 0.6
		env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		camera.environment = env
		for i in 4:
			await process_frame
		await RenderingServer.frame_post_draw
		var image := viewport.get_texture().get_image()
		image.resize(SIZE.x, SIZE.y, Image.INTERPOLATE_LANCZOS)
		image.save_png(ProjectSettings.globalize_path(out.path_join(key + ".png")))
		viewport.queue_free()
		print("CARD ", key)
	quit()
