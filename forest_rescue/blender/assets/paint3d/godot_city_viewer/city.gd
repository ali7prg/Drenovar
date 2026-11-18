extends Node3D
## Game-camera QA scene for the forest kit: EXACT city camera + light + environment of
## godot/project/src/landscape.gd (setup() / apply_camera_pose(), map "city").
##   camera: orthogonal, size = zoom, position = target + (75, 83, 75), look_at(target)  (38.0 deg elevation)
##   sun: rotation_degrees (-48, -32, 0), #ffe4b8, energy 1.85, shadows (orthogonal mode)
##   env: background #8b9874, ambient COLOR #d8e5ee x0.58, FILMIC, depth fog 160..300
## Instances come from a JSON spec: {"instances": [{"glb": "x.glb", "node": "lf_..._v2_LOD0", "x":.., "z":.., "yaw":.., "s":.., "tag": "oak"}],
##   "ground": [r,g,b], "target": [x,y,z]}
## Foliage/bark use the painted override albedo * mix(1, lambert(sun), k), k per material ("vol" -> k_vol).
## Args: --spec=res://spec.json --zooms=68,40 --out=/abs/dir --k=0.3 --k_vol=0.5 --only=<tag>

var args := {}
var cam: Camera3D
var sun: DirectionalLight3D
var shots: Array = []

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
	env.fog_enabled = true
	env.fog_light_color = env.background_color
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_density = 0.72
	env.fog_depth_begin = 160.0
	env.fog_depth_end = 300.0
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
	var only: String = args.get("only", "")
	var scenes := {}
	var meshes := {}
	var to_light: Vector3 = sun.global_transform.basis.z.normalized()
	var k := float(args.get("k", "0.3"))
	var k_vol := float(args.get("k_vol", "0.5"))
	var n := 0
	for inst in spec.instances:
		if only != "" and str(inst.get("tag", "")) != only:
			continue
		var key: String = inst.glb + ":" + inst.node
		if not meshes.has(key):
			if not scenes.has(inst.glb):
				var ps: PackedScene = load("res://models/" + inst.glb)
				scenes[inst.glb] = ps.instantiate()
			var root: Node = scenes[inst.glb]
			var found: MeshInstance3D = null
			for mi in root.find_children("*", "MeshInstance3D", true, false):
				if String(mi.name) == inst.node:
					found = mi
			if found == null:
				push_error("VIEWER missing node " + key)
				continue
			meshes[key] = _painted_mesh(found.mesh, to_light, k, k_vol)
		var m := MeshInstance3D.new()
		m.mesh = meshes[key]
		var s := float(inst.get("s", 1.0))
		m.transform = Transform3D(Basis(Vector3.UP, float(inst.get("yaw", 0.0))).scaled(Vector3(s, s, s)),
			Vector3(float(inst.x), 0.0, float(inst.z)))
		add_child(m)
		n += 1
	print("VIEWER_INSTANCES ", n)
	_shots.call_deferred(spec)

func _painted_mesh(mesh: Mesh, to_light: Vector3, k: float, k_vol: float) -> Mesh:
	var sh: Shader = load("res://lf_painted.gdshader")
	var copy: Mesh = mesh.duplicate()
	for i in copy.get_surface_count():
		var sm := copy.surface_get_material(i) as BaseMaterial3D
		if sm == null or sm.albedo_texture == null:
			continue
		var mat := ShaderMaterial.new()
		mat.shader = sh
		mat.set_shader_parameter("albedo_tex", sm.albedo_texture)
		mat.set_shader_parameter("albedo_color", sm.albedo_color)
		mat.set_shader_parameter("alpha_test", sm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED)
		mat.set_shader_parameter("alpha_cutoff", sm.alpha_scissor_threshold)
		var name := String(sm.resource_name)
		mat.set_shader_parameter("painted_light_mix", k_vol if name.contains("vol") else k)
		mat.set_shader_parameter("light_dir_world", to_light)
		mat.set_shader_parameter("wind_strength", 0.0)
		copy.surface_set_material(i, mat)
	return copy

func _shots(spec: Dictionary) -> void:
	var out: String = args.get("out", "/tmp")
	DirAccess.make_dir_recursive_absolute(out)
	var t: Array = spec.get("target", [0, 0, 0])
	var target := Vector3(float(t[0]), float(t[1]), float(t[2]))
	for z in str(args.get("zooms", "68,40")).split(","):
		cam.size = float(z)
		cam.position = target + Vector3(75, 83, 75)
		cam.look_at(target, Vector3.UP)
		for _f in 10:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		img.save_png(out.path_join("city_zoom%s%s.png" % [z, ("_" + str(args.get("only", ""))) if args.get("only", "") != "" else ""]))
	print("VIEWER_SHOTS_DONE ", out)
	get_tree().quit()
