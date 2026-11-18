extends Node3D
## In-engine viewer: loads a GLB, frames it, plays a clip or orbits, optional screenshots.
## User args (after --): --model=res://models/x.glb --anim=<name|all> --mode=clip|turntable|shots
##   --yaw=deg --pitch=deg --dist=mult --speed=1 --out=/abs/dir --ground=1 --bg=r,g,b
## Video: godot --path . --write-movie /abs/frames.png --fixed-fps 30 --quit-after N -- --model=...

var args := {}
var model: Node3D
var player: AnimationPlayer
var cam: Camera3D
var aabb := AABB()
var t := 0.0
var anims: Array = []
var anim_index := 0

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and a.contains("="):
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1]
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var bg: PackedStringArray = str(args.get("bg", "0.72,0.70,0.64")).split(",")
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(float(bg[0]), float(bg[1]), float(bg[2]))
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.62, 0.64, 0.68)
	e.ambient_light_energy = 0.55
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -35, 0)
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	add_child(sun)
	if str(args.get("ground", "1")) == "1":
		var g := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(60, 60)
		g.mesh = pm
		var gm := StandardMaterial3D.new()
		gm.albedo_color = Color(0.46, 0.43, 0.34)
		gm.roughness = 1.0
		g.material_override = gm
		add_child(g)
	var path: String = args.get("model", "")
	var scene: PackedScene = load(path)
	if scene == null:
		push_error("VIEWER cannot load " + path)
		get_tree().quit(2)
		return
	model = scene.instantiate()
	add_child(model)
	if str(args.get("wind", "1")) == "1":
		_apply_wind(model)
	var only: String = args.get("only", "")
	if only != "":
		for c in model.find_children("*", "MeshInstance3D", true, false):
			c.visible = c.name.contains(only)
	aabb = _scene_aabb(model)
	print("VIEWER_AABB ", aabb.position, " ", aabb.size)
	player = _find_player(model)
	if player:
		anims = Array(player.get_animation_list())
		print("VIEWER_ANIMS ", anims)
		var want: String = args.get("anim", "")
		if want != "" and want != "all" and player.has_animation(want):
			anims = [want]
		if not anims.is_empty():
			_play(anims[0])
	cam = Camera3D.new()
	cam.fov = 38.0
	if str(args.get("ortho", "0")) == "1":
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	add_child(cam)
	_place_camera(0.0)
	if str(args.get("mode", "clip")) == "shots":
		_shots.call_deferred()

func _apply_wind(n: Node) -> void:
	var sh: Shader = load("res://lf_forest_wind.gdshader")
	for mi in n.find_children("*", "MeshInstance3D", true, false):
		var m: Mesh = mi.mesh
		var arrays_has_color := false
		for i in m.get_surface_count():
			var arr: Array = m.surface_get_arrays(i)
			if arr[Mesh.ARRAY_COLOR] != null and arr[Mesh.ARRAY_COLOR].size() > 0:
				arrays_has_color = true
		if not arrays_has_color:
			continue
		for i in m.get_surface_count():
			var sm := m.surface_get_material(i) as StandardMaterial3D
			if sm == null:
				continue
			var mat := ShaderMaterial.new()
			mat.shader = sh
			mat.set_shader_parameter("albedo_tex", sm.albedo_texture)
			mat.set_shader_parameter("alpha_test", sm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED)
			mat.set_shader_parameter("alpha_cutoff", sm.alpha_scissor_threshold)
			if sm.normal_enabled and sm.normal_texture:
				mat.set_shader_parameter("normal_tex", sm.normal_texture)
				mat.set_shader_parameter("use_normal_map", true)
			if sm.roughness_texture:
				mat.set_shader_parameter("rough_tex", sm.roughness_texture)
				mat.set_shader_parameter("use_rough_map", true)
			mat.set_shader_parameter("wind_strength", float(args.get("windk", "1")))
			mi.set_surface_override_material(i, mat)
	print("VIEWER_WIND applied")

func _play(name: String) -> void:
	var a := player.get_animation(name)
	if a and str(args.get("mode", "clip")) != "shots":
		a.loop_mode = Animation.LOOP_LINEAR
	player.play(name, 0.15, float(args.get("speed", "1")))
	print("VIEWER_PLAY ", name, " len=", a.length if a else 0)

func _scene_aabb(n: Node) -> AABB:
	var out := AABB()
	var first := true
	for c in n.find_children("*", "VisualInstance3D", true, false):
		var vi := c as VisualInstance3D
		if not vi.visible:
			continue
		var b := vi.global_transform * vi.get_aabb()
		if first:
			out = b
			first = false
		else:
			out = out.merge(b)
	return out

func _find_player(n: Node) -> AnimationPlayer:
	for c in n.find_children("*", "AnimationPlayer", true, false):
		return c
	return null

func _place_camera(extra_yaw: float) -> void:
	var yaw := deg_to_rad(float(args.get("yaw", "35")) + extra_yaw)
	var pitch := deg_to_rad(float(args.get("pitch", "18")))
	if args.has("pitches") and args.has("shot_index"):
		pitch = deg_to_rad(float(str(args["pitches"]).split(",")[int(args["shot_index"])]))
	var radius := aabb.size.length() * 0.5
	var dist := radius / tan(deg_to_rad(cam.fov * 0.5)) * float(args.get("dist", "1.15"))
	var center := aabb.get_center()
	var dir := Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	cam.global_position = center + dir * dist
	if abs(dir.y) > 0.999:
		cam.look_at(center, Vector3.FORWARD)
	else:
		cam.look_at(center, Vector3.UP)
	if cam.projection == Camera3D.PROJECTION_ORTHOGONAL:
		cam.size = aabb.size.length() * float(args.get("dist", "1.15")) * 0.75

func _process(delta: float) -> void:
	t += delta
	var mode := str(args.get("mode", "clip"))
	if mode == "turntable":
		_place_camera(t * 45.0)
	elif mode == "clip" and player and anims.size() > 1:
		var cur: String = anims[anim_index]
		var a := player.get_animation(cur)
		if a and t > max(a.length * 2.0, 1.5):
			t = 0.0
			anim_index = (anim_index + 1) % anims.size()
			_play(anims[anim_index])

func _shots() -> void:
	var out: String = args.get("out", "/tmp")
	DirAccess.make_dir_recursive_absolute(out)
	var yaws := [0, 45, 90, 135, 180, 270]
	if args.has("yaws"):
		yaws = []
		for y in str(args["yaws"]).split(","):
			yaws.append(int(y))
	for i in yaws.size():
		args["yaw"] = str(yaws[i])
		args["shot_index"] = str(i)
		_place_camera(0.0)
		for _f in 8:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		var pz := str(args.get("pitch", "18"))
		if args.has("pitches"):
			pz = str(args["pitches"]).split(",")[i]
		img.save_png(out.path_join("shot_%02d_yaw%03d_p%s.png" % [i, yaws[i], pz]))
	print("VIEWER_SHOTS_DONE ", out)
	get_tree().quit()
