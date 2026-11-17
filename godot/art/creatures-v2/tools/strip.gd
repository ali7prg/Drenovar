extends SceneTree
## Film strip of one clip: --glb= --anim= --out= [--frames=8 --view=side|3q|front|top --h=4.6 --cols=8]
var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	call_deferred("run")

func run() -> void:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(args.glb, state) != OK:
		quit(1)
		return
	var model: Node3D = doc.generate_scene(state)
	var frames := int(args.get("frames", "8"))
	var size := Vector2i(int(args.get("w", "360")), int(args.get("hpx", "300")))
	var span := float(args.get("h", "4.6"))
	var dirs := {"side": Vector3(0, 0.12, -1), "3q": Vector3(0.75, 0.42, -0.62), "front": Vector3(1, 0.15, 0), "top": Vector3(0.01, 1, 0), "rear": Vector3(-1, 0.2, 0.0), "3qr": Vector3(-0.6, 0.45, 0.7)}
	var dir: Vector3 = dirs.get(args.get("view", "side"), Vector3(0, 0.12, -1))
	var vps: Array = []
	for i in frames:
		var vp := SubViewport.new()
		vp.size = size
		vp.msaa_3d = Viewport.MSAA_4X
		vp.own_world_3d = true
		vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(vp)
		var env := WorldEnvironment.new()
		var e := Environment.new()
		e.background_mode = Environment.BG_COLOR
		e.background_color = Color(0.80, 0.79, 0.75)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color(0.55, 0.57, 0.62)
		e.ambient_light_energy = 0.45
		env.environment = e
		vp.add_child(env)
		var sun := DirectionalLight3D.new()
		sun.light_energy = 1.3
		sun.shadow_enabled = true
		vp.add_child(sun)
		sun.look_at_from_position(Vector3(3, 6, -4), Vector3.ZERO, Vector3.UP)
		var inst: Node3D = model.duplicate()
		vp.add_child(inst)
		var ground := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(14, 14)
		ground.mesh = pm
		var gm := StandardMaterial3D.new()
		gm.albedo_color = Color(0.62, 0.60, 0.56)
		ground.material_override = gm
		vp.add_child(ground)
		var cam := Camera3D.new()
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = span
		vp.add_child(cam)
		var centre := Vector3(float(args.get("cx", "0.1")), float(args.get("cy", "1.7")), 0)
		var upv := Vector3.UP if args.get("view", "side") != "top" else Vector3(1, 0, 0)
		cam.look_at_from_position(centre + dir.normalized() * 12.0, centre, upv)
		var ap: AnimationPlayer = inst.find_children("*", "AnimationPlayer", true, false)[0]
		var anim: Animation = ap.get_animation(args.anim)
		ap.play(args.anim)
		var t := anim.length * float(i) / float(max(1, frames - 1)) if not args.has("loop") else anim.length * float(i) / float(frames)
		ap.seek(t, true)
		ap.pause()
		var lab := Label3D.new()
		vps.append(vp)
	for k in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var cols := int(args.get("cols", str(frames)))
	var rows := int(ceil(float(frames) / cols))
	var sheet := Image.create(size.x * cols, size.y * rows, false, Image.FORMAT_RGB8)
	for i in vps.size():
		var img: Image = vps[i].get_texture().get_image()
		img.convert(Image.FORMAT_RGB8)
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, size), Vector2i((i % cols) * size.x, (i / cols) * size.y))
	sheet.save_png(args.out)
	print("saved ", args.out)
	quit()
