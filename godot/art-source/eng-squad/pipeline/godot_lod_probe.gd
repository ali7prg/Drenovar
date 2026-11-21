extends SceneTree
# ENG squad pipeline · empirical Godot mesh-LOD selection (needs the real renderer: godot_render).
# One model (default scale 1.15 = field), no shadows; reads primitives drawn per frame at several
# perspective distances (world camera tilt) and orthographic sizes (city camera).
# usage: godot_render 1366x630 -s "$SQUAD/pipeline/godot_lod_probe.gd" -- --out=/abs/lod.json [--model=res://...] [--scale=1.15]

var out_path := ""
var model_path := "res://assets/army/assets/ENG-01-spearman27-lod2.glb"
var scale := 1.15

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--model="):
			model_path = arg.trim_prefix("--model=")
		elif arg.begins_with("--scale="):
			scale = float(arg.trim_prefix("--scale="))
	call_deferred("run")

func prims() -> int:
	return RenderingServer.viewport_get_render_info(get_root().get_viewport_rid(),
		RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)

func run() -> void:
	var world := Node3D.new()
	get_root().add_child(world)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.3, 0.3, 0.3)
	world.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = false
	sun.rotation_degrees = Vector3(-50, 30, 0)
	world.add_child(sun)
	var cam := Camera3D.new()
	world.add_child(cam)
	cam.make_current()
	cam.fov = 43.0
	cam.near = 0.5
	cam.far = 1100.0
	var actor := (load(model_path) as PackedScene).instantiate() as Node3D
	actor.scale = Vector3.ONE * scale
	world.add_child(actor)
	for i in 5:
		await process_frame
	var rows: Array = []
	var tilt := 0.88
	for d in [3.0, 5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 68.0, 90.0, 120.0, 132.0]:
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		var target := Vector3(0, 1, 0)
		cam.position = target + Vector3(0, sin(tilt), cos(tilt)) * d
		cam.look_at(target, Vector3.UP)
		for i in 4:
			await process_frame
		rows.append({"projection": "perspective", "distance": d, "primitives": prims()})
	for size in [24.0, 30.0, 40.0, 50.0, 70.0, 90.0, 120.0]:
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = size
		cam.position = Vector3(75, 83, 75)
		cam.look_at(Vector3.ZERO, Vector3.UP)
		for i in 4:
			await process_frame
		rows.append({"projection": "orthogonal", "size": size, "primitives": prims()})
	actor.visible = false
	for i in 4:
		await process_frame
	rows.append({"projection": "empty", "primitives": prims()})
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify({"model": model_path, "viewport": get_root().get_visible_rect().size, "rows": rows}, " "))
	f.close()
	print("LOD_PROBE_OK ", rows.size())
	quit(0)
