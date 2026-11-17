extends SceneTree

# Renders a contact sheet of all ten English field models in Idle, side by side,
# from the same camera. Needs a real renderer (e.g. xvfb-run + opengl3).
# Usage: xvfb-run -s "-screen 0 1600x700x24" godot --rendering-driver opengl3 \
#   --path . -s profile_troop_sheet.gd -- --out=/abs/path.png [--lod=preview|field]

const WarriorVisual = preload("res://src/warrior_visual.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var out := "user://troop-sheet.png"
	var lod := "field"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		if arg.begins_with("--lod="):
			lod = arg.trim_prefix("--lod=")
	root.size = Vector2i(2000, 900)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var world := Node3D.new()
	root.add_child(world)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#8b9874")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d8e5ee")
	env.ambient_light_energy = 0.6
	var camera := Camera3D.new()
	camera.environment = env
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 9.2
	camera.position = Vector3(9.0, 2.3, 14)
	world.add_child(camera)
	camera.look_at(Vector3(9.0, 2.0, 0), Vector3.UP)
	camera.make_current()
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40, -30, 0)
	sun.light_energy = 1.6
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(40, 10)
	ground.mesh = plane
	ground.position = Vector3(9, 0, 0)
	world.add_child(ground)
	var index := 0
	for id in data.unitModels:
		var model: Node3D = load(data.unitModels[id][lod]).instantiate()
		WarriorVisual.prepare(model)
		model.position = Vector3(index * 2.0, 0, 0)
		model.rotation.y = 0.35
		world.add_child(model)
		for player: AnimationPlayer in model.find_children("*", "AnimationPlayer", true, false):
			for clip in player.get_animation_list():
				if clip.to_lower() == "idle":
					player.play(clip)
					player.seek(0.0, true)
		var label := Label3D.new()
		label.text = id
		label.font_size = 48
		label.position = Vector3(index * 2.0, 0.1, 0.8)
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		world.add_child(label)
		index += 1
	for i in 8:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out)
	print("TROOP_SHEET ", out)
	quit(0)
