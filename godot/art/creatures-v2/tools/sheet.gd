extends SceneTree
## Orthographic contact sheet: front, left side, rear, top, three-quarter.
## godot --path viewer -s sheet.gd -- --glb=<file> --out=<png> [--h=4.2] [--anim=name --t=0.5]
var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	call_deferred("run")

func load_glb(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		push_error("load failed %s" % path)
		quit(1)
	return doc.generate_scene(state)

func run() -> void:
	var size := Vector2i(int(args.get("w", "560")), int(args.get("hpx", "520")))
	var views := [["front", Vector3(1, 0, 0)], ["side", Vector3(0, 0, -1)], ["rear", Vector3(-1, 0, 0)], ["top", Vector3(0, 1, 0)], ["3q", Vector3(0.75, 0.42, -0.62)]]
	var span := float(args.get("h", "4.4"))
	var model := load_glb(args.glb)
	var images: Array[Image] = []
	for v in views:
		var vp := SubViewport.new()
		vp.size = size
		vp.msaa_3d = Viewport.MSAA_4X
		vp.own_world_3d = true
		vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(vp)
		var env := WorldEnvironment.new()
		var e := Environment.new()
		e.background_mode = Environment.BG_COLOR
		e.background_color = Color(0.82, 0.80, 0.76)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color(0.62, 0.64, 0.68)
		e.ambient_light_energy = 0.55
		env.environment = e
		vp.add_child(env)
		var sun := DirectionalLight3D.new()
		sun.light_energy = 1.25
		sun.shadow_enabled = true
		vp.add_child(sun)
		sun.look_at_from_position(Vector3(3, 6, -4), Vector3.ZERO, Vector3.UP)
		var fill := DirectionalLight3D.new()
		fill.light_energy = 0.35
		vp.add_child(fill)
		fill.look_at_from_position(Vector3(-4, 2, 3), Vector3.ZERO, Vector3.UP)
		var inst: Node3D = model.duplicate()
		vp.add_child(inst)
		var ap := inst.find_children("*", "AnimationPlayer", true, false)
		if args.has("anim") and ap.size() > 0:
			var p: AnimationPlayer = ap[0]
			p.play(args.anim)
			p.seek(float(args.get("t", "0")) * p.get_animation(args.anim).length, true)
			p.pause()
		# ground + 1.8 m human for scale
		var ground := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(12, 12)
		ground.mesh = pm
		var gm := StandardMaterial3D.new()
		gm.albedo_color = Color(0.68, 0.66, 0.62)
		ground.material_override = gm
		vp.add_child(ground)
		var man := MeshInstance3D.new()
		var cap := CapsuleMesh.new()
		cap.radius = 0.22
		cap.height = 1.8
		man.mesh = cap
		var mm := StandardMaterial3D.new()
		mm.albedo_color = Color(0.35, 0.36, 0.40)
		man.material_override = mm
		man.position = Vector3(0.0, 0.9, 2.6) if v[0] != "top" else Vector3(3.0, 0.9, 2.2)
		if v[0] == "side" or v[0] == "3q":
			man.position = Vector3(-0.2, 0.9, 1.9)
		vp.add_child(man)
		var cam := Camera3D.new()
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = span
		vp.add_child(cam)
		var centre := Vector3(float(args.get("cx", "0.1")), float(args.get("cy", "1.8")), 0)
		var dir: Vector3 = v[1]
		var upv := Vector3.UP if v[0] != "top" else Vector3(1, 0, 0)
		cam.look_at_from_position(centre + dir.normalized() * 12.0, centre, upv)
		images.append(null)
	for i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var vps := root.get_children().filter(func(n): return n is SubViewport)
	var sheet := Image.create(size.x * vps.size(), size.y, false, Image.FORMAT_RGB8)
	for i in vps.size():
		var img: Image = vps[i].get_texture().get_image()
		img.convert(Image.FORMAT_RGB8)
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, size), Vector2i(i * size.x, 0))
	sheet.save_png(args.out)
	print("saved ", args.out)
	quit()
