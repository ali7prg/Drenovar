extends SceneTree

# Close-up turnaround of troop GLBs (front, three-quarter, side, back) under one
# light setup. Usage (real renderer):
#   xvfb-run -s "-screen 0 1800x900x24" godot --rendering-driver opengl3 --path . \
#     -s profile_troop_views.gd -- --model=res://... [--clip=Idle] [--time=0.0] --out=/abs/file.png

const WarriorVisual = preload("res://src/warrior_visual.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var model_paths: PackedStringArray = []
	var clip := "Idle"
	var at := 0.0
	var out := "user://troop-views.png"
	var angles := [0.0, 40.0, 90.0, 180.0]
	var close := false
	var frames := 0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--model="):
			model_paths.append(arg.trim_prefix("--model="))
		elif arg.begins_with("--clip="):
			clip = arg.trim_prefix("--clip=")
		elif arg.begins_with("--time="):
			at = float(arg.trim_prefix("--time="))
		elif arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--angles="):
			angles = Array(arg.trim_prefix("--angles=").split(",")).map(func(a): return float(a))
		elif arg == "--close":
			close = true
		elif arg.begins_with("--frames="):
			frames = int(arg.trim_prefix("--frames="))
	root.size = Vector2i(1800, 900)
	var world := Node3D.new()
	root.add_child(world)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#3a3f44")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d8e5ee")
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	if not OS.get_cmdline_user_args().has("--no-reflections"):
		WarriorVisual.add_reflections(env, Color("#8b9874"))
	var camera := Camera3D.new()
	camera.environment = env
	camera.fov = 30
	world.add_child(camera)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-38, -32, 0)
	sun.light_energy = 1.7
	sun.light_color = Color("#ffe8c8")
	sun.shadow_enabled = true
	world.add_child(sun)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 20)
	floor_mesh.mesh = plane
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color("#4b4f52")
	floor_mesh.material_override = floor_mat
	world.add_child(floor_mesh)
	var spacing := 1.2 if close else 2.4
	var index := 0
	for path in model_paths:
		for angle in angles:
			var model: Node3D = load(path).instantiate()
			WarriorVisual.prepare(model)
			model.position = Vector3(index * spacing, 0, 0)
			model.rotation_degrees.y = angle
			world.add_child(model)
			for player: AnimationPlayer in model.find_children("*", "AnimationPlayer", true, false):
				for name in player.get_animation_list():
					if name.to_lower() == clip.to_lower():
						player.play(name)
						player.seek(at, true)
						player.pause()
			index += 1
	var width := (index - 1) * spacing
	if close:
		camera.position = Vector3(width * 0.5, 1.55, 1.6 + width * 0.75)
		camera.look_at(Vector3(width * 0.5, 1.45, 0), Vector3.UP)
	elif OS.get_cmdline_user_args().has("--tall"):
		camera.position = Vector3(width * 0.5, 1.9, 8.2 + width * 0.62)
		camera.look_at(Vector3(width * 0.5, 1.6, 0), Vector3.UP)
	else:
		camera.position = Vector3(width * 0.5, 1.15, 4.6 + width * 0.62)
		camera.look_at(Vector3(width * 0.5, 0.95, 0), Vector3.UP)
	for i in 6:
		await process_frame
	if frames <= 0:
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out)
		print("TROOP_VIEWS ", out)
		quit(0)
		return
	# Frame sequence across the clip (for motion sheets / GIFs).
	var players: Array = world.find_children("*", "AnimationPlayer", true, false)
	var length := 1.0
	for player: AnimationPlayer in players:
		if player.has_animation(clip):
			length = player.get_animation(clip).length
	for f in frames:
		for player: AnimationPlayer in players:
			if player.has_animation(clip):
				player.seek(length * f / frames, true)
		await process_frame
		await RenderingServer.frame_post_draw
		var path := out.replace(".png", "_%02d.png" % f)
		root.get_texture().get_image().save_png(path)
	print("TROOP_VIEWS ", out, " frames=", frames)
	quit(0)
