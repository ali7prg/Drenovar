extends SceneTree
## creatures-v2 media from the game project itself (real import, CreatureVisuals level materials,
## creature_v2 shader). Writes PNG frames; tools/media.py turns them into WebP/MP4/sheets.
##   DISPLAY=:99 godot --path godot/project --rendering-method gl_compatibility \
##     -s ../art/creatures-v2/tools/media.gd -- --out=/abs/dir [--only=velkor] [--what=portraits,turntable,clips]
const CreatureVisuals = preload("res://src/creature_visuals.gd")
var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	call_deferred("run")

func stage(size: Vector2i, bg: Color) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = size
	vp.msaa_3d = Viewport.MSAA_4X
	vp.own_world_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = bg
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color("#c9d3e0")
	e.ambient_light_energy = 0.55
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.glow_enabled = true
	e.glow_intensity = 0.6
	env.environment = e
	vp.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.light_color = Color("#fff0dc")
	sun.light_energy = 1.8
	sun.shadow_enabled = true
	vp.add_child(sun)
	sun.look_at_from_position(Vector3(4, 7, 5), Vector3.ZERO, Vector3.UP)
	var rim := DirectionalLight3D.new()
	rim.light_color = Color("#a9c4e8")
	rim.light_energy = 0.7
	vp.add_child(rim)
	rim.look_at_from_position(Vector3(-5, 3, -4), Vector3.ZERO, Vector3.UP)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(40, 40)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color("#5c5a4c")
	gm.roughness = 0.95
	ground.material_override = gm
	vp.add_child(ground)
	return vp

func snap(vp: SubViewport, path: String) -> void:
	await RenderingServer.frame_post_draw
	var img := vp.get_texture().get_image()
	if not vp.transparent_bg:
		img.convert(Image.FORMAT_RGB8)
	img.save_png(path)

func creature(vp: SubViewport, species: String, level: int) -> Node3D:
	var scene: PackedScene = load(str(CreatureVisuals.entry(species).model))
	var a := scene.instantiate() as Node3D
	vp.add_child(a)
	CreatureVisuals.install(a, species, level, 1.0)
	return a

func pose(a: Node3D, clip: StringName, t: float) -> void:
	var p: AnimationPlayer = a.find_children("*", "AnimationPlayer", true, false)[0]
	p.play(clip)
	p.seek(t, true)
	p.pause()

func frame_camera(vp: SubViewport, species: String, yaw: float, pitch: float, zoom := 1.0, lift := 0.45) -> Camera3D:
	var b: Dictionary = CreatureVisuals.entry(species).authored_bounds_m
	var length: float = float(b.x[1]) - float(b.x[0])
	var top := float(b.top)
	var centre := Vector3((float(b.x[0]) + float(b.x[1])) * 0.5, top * lift, 0)
	var cam := Camera3D.new()
	cam.fov = 30.0
	vp.add_child(cam)
	var dist := maxf(length, top) * 2.2 * zoom
	var dir := Vector3(cos(yaw) * cos(pitch), sin(pitch), -sin(yaw) * cos(pitch))
	cam.look_at_from_position(centre + dir * dist, centre, Vector3.UP)
	return cam

func run() -> void:
	var out: String = args.get("out", "/tmp/creatures-media")
	var what: String = args.get("what", "portraits,turntable,clips")
	var species_list := ["velkor", "tenerys", "kamneklyk", "dragor"]
	if args.has("only"):
		species_list = [args.only]
	for species in species_list:
		DirAccess.make_dir_recursive_absolute(out + "/" + species)
		if "portraits" in what:
			for level in [1, 2, 3]:
				var vp := stage(Vector2i(480, 360), Color("#2d3a33"))
				# transparent backdrop, no floor: tools/media.py lays the hunt panel gradient under it
				vp.transparent_bg = true
				for n in vp.get_children():
					if n is MeshInstance3D:
						n.queue_free()
					elif n is WorldEnvironment:
						n.environment.background_mode = Environment.BG_CLEAR_COLOR
				var a := creature(vp, species, level)
				pose(a, CreatureVisuals.clip_name(species, "Alert"), 30.0)
				frame_camera(vp, species, 0.62, 0.16, 1.0, 0.5)
				for i in 3:
					await process_frame
				await snap(vp, "%s/%s/portrait_%d.png" % [out, species, level])
				vp.queue_free()
				await process_frame
		if "turntable" in what:
			var vp := stage(Vector2i(640, 480), Color("#bdb8ad"))
			var a := creature(vp, species, int(args.get("level", "1")))
			pose(a, CreatureVisuals.clip_name(species, "Idle"), 0.0)
			var cam := frame_camera(vp, species, 0.0, 0.16, 0.9)
			var b: Dictionary = CreatureVisuals.entry(species).authored_bounds_m
			var centre := Vector3((float(b.x[0]) + float(b.x[1])) * 0.5, float(b.top) * 0.45, 0)
			var dist := cam.global_position.distance_to(centre)
			var steps := int(args.get("turn", "72"))
			for i in steps:
				var yaw := TAU * i / float(steps)
				var dir := Vector3(cos(yaw) * cos(0.16), sin(0.16), -sin(yaw) * cos(0.16))
				cam.look_at_from_position(centre + dir * dist, centre, Vector3.UP)
				await process_frame
				await snap(vp, "%s/%s/turn_%03d.png" % [out, species, i])
			vp.queue_free()
			await process_frame
		if "clips" in what:
			var man := CreatureVisuals.manifest(species)
			var shots: Array = str(args.get("clips", "")).split(",", false)
			if shots.is_empty():
				shots = man.clips.keys()
			for short in shots:
				var row: Dictionary = man.clips[short]
				var vp := stage(Vector2i(640, 400), Color("#bdb8ad"))
				var a := creature(vp, species, 1)
				var cam := frame_camera(vp, species, 0.55, 0.20, 1.05)
				var frames := int(row.frames)
				var n := frames + 1 if not bool(row.loop) else frames * 2
				for f in n:
					var t := float(f % (frames + 1)) / 30.0 if not bool(row.loop) else float(f % frames) / 30.0
					pose(a, StringName(str(row.name)), t)
					# controller displacement that the game applies (charge, pounce, dodge)
					var m := CreatureVisuals.motion_at(species, short, t)
					a.position = Vector3(m.x, 0, m.y)
					await process_frame
					await snap(vp, "%s/%s/clip_%s_%03d.png" % [out, species, short, f])
				vp.queue_free()
				await process_frame
	quit()
