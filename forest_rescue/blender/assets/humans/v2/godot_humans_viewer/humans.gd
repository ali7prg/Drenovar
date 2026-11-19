extends Node3D
## Game-camera QA for the v2 humans (exact city camera/light of landscape.gd, map "city"):
##   camera orthogonal, size = zoom, position = target + (75, 83, 75), look_at(target)
##   sun rotation_degrees (-48, -32, 0), #ffe4b8 x1.85, shadows; ambient #d8e5ee x0.58; FILMIC.
## Characters are full GLB scenes (Skeleton3D + AnimationPlayer), posed at a clip time; every
## surface of a human gets the painted-light override albedo * mix(1, lambert(sun), k) with
## k = meta paintedLightMix (the horse keeps its own PBR materials, as in the game).
## spec.json: {"instances":[{"glb":"x.glb","x":0,"z":0,"yaw":0,"anim":"lf_civilian_wait","t":0.5,
##   "lod":0,"painted":true,"k":0.4,"tint":{"cloth":[r,g,b]}}], "target":[x,y,z], "ground":[r,g,b],
##   "zooms":"40,68", "res":[w,h], "out_prefix":"city"}
var args := {}
var cam: Camera3D
var sun: DirectionalLight3D

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and a.contains("="):
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1]
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args.get("spec", "res://spec.json")))
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#8b9874")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d8e5ee")
	env.ambient_light_energy = 0.58
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -32, 0)
	sun.light_color = Color("#ffe4b8")
	sun.light_energy = 1.85
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	add_child(sun)
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 0.5
	cam.far = 700.0
	cam.environment = env
	add_child(cam)
	var g: Array = spec.get("ground", [0.42, 0.45, 0.25])
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(400, 400)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(float(g[0]), float(g[1]), float(g[2]))
	gm.roughness = 1.0
	ground.material_override = gm
	add_child(ground)
	var to_light: Vector3 = sun.global_transform.basis.z.normalized()
	var shader: Shader = load("res://lf_painted.gdshader")
	var n := 0
	for inst in spec.instances:
		var ps: PackedScene = load("res://models/" + String(inst.glb))
		if ps == null:
			push_error("VIEWER missing " + String(inst.glb))
			continue
		var root: Node3D = ps.instantiate()
		root.position = Vector3(float(inst.get("x", 0.0)), 0.0, float(inst.get("z", 0.0)))
		root.rotation.y = float(inst.get("yaw", 0.0))
		var s := float(inst.get("s", 1.0))
		root.scale = Vector3(s, s, s)
		add_child(root)
		var lod := int(inst.get("lod", 0))
		for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			var lower := String(mi.name).to_lower()
			var is_lod := false
			for l in 3:
				if lower.ends_with("_lod%d" % l) or lower.contains("_lod%d_" % l):
					is_lod = true
					mi.visible = (l == lod)
			if bool(inst.get("painted", false)) and mi.mesh != null:
				var tint: Dictionary = inst.get("tint", {})
				for si in mi.mesh.get_surface_count():
					var sm := mi.get_active_material(si) as BaseMaterial3D
					if sm == null:
						continue
					var mat := ShaderMaterial.new()
					mat.shader = shader
					mat.set_shader_parameter("albedo_tex", sm.albedo_texture)
					var col := sm.albedo_color
					for key in tint:
						if String(sm.resource_name).ends_with("_" + String(key)):
							var t: Array = tint[key]
							col = Color(float(t[0]), float(t[1]), float(t[2]))
					mat.set_shader_parameter("albedo_color", col)
					mat.set_shader_parameter("alpha_test", false)
					mat.set_shader_parameter("painted_light_mix", float(inst.get("k", 0.4)))
					mat.set_shader_parameter("light_dir_world", to_light)
					mat.set_shader_parameter("wind_strength", 0.0)
					mat.set_shader_parameter("use_ao", false)
					mi.set_surface_override_material(si, mat)
		var players := root.find_children("*", "AnimationPlayer", true, false)
		if not players.is_empty():
			var ap: AnimationPlayer = players[0]
			var want := String(inst.get("anim", ""))
			var found := ""
			for nm in ap.get_animation_list():
				if nm == want or String(nm).ends_with(want):
					found = nm
			if found != "":
				ap.play(found)
				ap.seek(float(inst.get("t", 0.0)), true)
				ap.pause()
		n += 1
	print("VIEWER_INSTANCES ", n)
	_shots.call_deferred(spec)

func _shots(spec: Dictionary) -> void:
	var out: String = args.get("out", "/tmp")
	DirAccess.make_dir_recursive_absolute(out)
	var t: Array = spec.get("target", [0, 0, 0])
	var target := Vector3(float(t[0]), float(t[1]), float(t[2]))
	var prefix := String(spec.get("out_prefix", "city"))
	for z in String(spec.get("zooms", "68,40")).split(","):
		cam.size = float(z)
		cam.position = target + Vector3(75, 83, 75)
		cam.look_at(target, Vector3.UP)
		for _f in 12:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		img.save_png(out.path_join("%s_zoom%s.png" % [prefix, z]))
	if spec.has("close"):
		# close QA camera (same direction, small ortho size) for detail
		var c: Dictionary = spec.close
		cam.size = float(c.get("size", 6.0))
		var ct: Array = c.get("target", t)
		var tt := Vector3(float(ct[0]), float(ct[1]), float(ct[2]))
		cam.position = tt + Vector3(75, 83, 75)
		cam.look_at(tt, Vector3.UP)
		for _f in 8:
			await get_tree().process_frame
		var img2 := get_viewport().get_texture().get_image()
		img2.save_png(out.path_join("%s_close.png" % prefix))
	print("VIEWER_SHOTS_DONE ", out)
	get_tree().quit()
