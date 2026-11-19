extends Node3D
## Props v2 game-camera test: EXACT city camera / light / environment of landscape.gd (orthographic, size = zoom,
## position = target + (75, 83, 75), look_at; sun (-48, -32, 0) #ffe4b8 x1.85; ambient #d8e5ee x0.58; FILMIC).
## Every prop / human surface gets the game's painted-light path (unshaded: albedo * mix(1, lambert(sun), k),
## k = meta paintedLightMix), exactly like actor_rig.apply_look -> ForestKit.painted_material.
## Scene: cage (state closed or open) with 3 captives in lf_civilian_cage_sit seated on the cage's floor socket,
## the artifact on the cage key_slot, a mechanism, the supplies pile.
## Args: --cage=lf_cage_wood --mech=lf_mechanism_paired_latch --artifact=lf_artifact_stone_rune --open=0|1
##       --zooms=40,68 --out=/abs/dir --colour=1 (adds a cage-only close shot on magenta for colour stats)

var args := {}
var cam: Camera3D
var sun: DirectionalLight3D
var env: Environment
var ground: MeshInstance3D
var painted_shader: Shader
var to_light: Vector3
var players: Array = []
var made: Array = []
var cage_inst: Node3D

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and a.contains("="):
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1]
	painted_shader = load("res://lf_painted.gdshader")
	env = Environment.new()
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
	to_light = sun.global_transform.basis.z.normalized()
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 0.5
	cam.far = 700.0
	cam.environment = env
	add_child(cam)
	ground = MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(400, 400)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.42, 0.45, 0.27)
	gm.roughness = 1.0
	ground.material_override = gm
	add_child(ground)
	var cage_name: String = args.get("cage", "lf_cage_wood")
	var meta := _meta(cage_name)
	var cage := _instance(cage_name, Vector3.ZERO, 0.0, float(meta.get("paintedLightMix", 0.38)))
	cage_inst = cage
	var open := str(args.get("open", "0")) == "1"
	var cp := _player(cage)
	if cp != null and open:
		cp.play("lf_cage_gate_open")
		cp.seek(1.6, true)
		cp.pause()
	# floor socket -> captives seated on the floor
	var floor_h := 0.0
	var sockets: Dictionary = meta.get("sockets", {})
	if sockets.has("floor"):
		floor_h = float(sockets["floor"][1])
	var people := ["lf_civilian_miller", "lf_civilian_herbalist", "lf_civilian_ferryman"]
	for i in 3:
		var slot: Array = sockets.get("captive_slot_%d" % i, [[-0.72, 0, 0.1], [0.05, 0, -0.45], [0.74, 0, 0.18]][i])
		var pos := Vector3(float(slot[0]), floor_h, float(slot[2]))
		if open:
			pos = Vector3(-1.2 + 1.2 * i, 0.0, 3.4)
		var h := _instance(people[i], pos, 0.35 * (i - 1), 0.4, "humans")
		var hp := _player(h)
		if hp != null:
			var clip := "lf_civilian_cage_sit" if not open else "lf_civilian_wait"
			if hp.has_animation(clip):
				hp.play(clip)
				hp.seek(1.0 + i * 0.7, true)
				hp.pause()
	# artifact in the cage socket (live key_slot node, parented)
	var art_name: String = args.get("artifact", "lf_artifact_stone_rune")
	var slot_node: Node3D = _find(cage, "key_slot")
	if slot_node != null:
		var art := _instance(art_name, Vector3.ZERO, 0.0, 0.38)
		art.reparent(slot_node, false)
		art.transform = Transform3D.IDENTITY
		for n in art.find_children("*", "Node3D", true, false):
			var nm := String(n.name)
			if (nm.contains("_v2") or nm.contains("_v3") or nm.ends_with("_socket") or nm.contains("_socket_")) and n is Node3D:
				n.visible = false
	# mechanism and supplies like a site layout (mechanism at the artifact spot side, supplies near the cage)
	var mech_name: String = args.get("mech", "lf_mechanism_paired_latch")
	_instance(mech_name, Vector3(float(args.get("mx", "6.5")), 0, float(args.get("mz", "1.5"))), float(args.get("myaw", "0.0")), 0.38)
	_instance("lf_props_supplies", Vector3(-5.2, 0, 2.6), 0.4, 0.38)
	print("CAGETEST floor_h ", floor_h, " open ", open)
	_shots.call_deferred()

func _meta(id: String) -> Dictionary:
	for dir in ["props", "humans"]:
		var p := "res://models/%s.meta.json" % id
		if FileAccess.file_exists(p):
			var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
			return d if d is Dictionary else {}
	return {}

func _player(n: Node) -> AnimationPlayer:
	var ps := n.find_children("*", "AnimationPlayer", true, false)
	return ps[0] if not ps.is_empty() else null

func _find(n: Node, nm: String) -> Node3D:
	for c in n.find_children("*", "Node3D", true, false):
		if String(c.name) == nm:
			return c
	return null

func _instance(id: String, pos: Vector3, yaw: float, k: float, _kind := "props") -> Node3D:
	var ps: PackedScene = load("res://models/%s.glb" % id)
	var inst: Node3D = ps.instantiate()
	add_child(inst)
	made.append(inst)
	inst.position = pos
	inst.rotation.y = yaw
	var meta := _meta(id)
	k = float(meta.get("paintedLightMix", k))
	for mi: MeshInstance3D in inst.find_children("*", "MeshInstance3D", true, false):
		var lower := String(mi.name).to_lower()
		if lower.ends_with("_lod1") or lower.ends_with("_lod2"):
			mi.visible = false
		if mi.mesh == null:
			continue
		for s in mi.mesh.get_surface_count():
			var m: Material = mi.get_active_material(s)
			if m is BaseMaterial3D:
				var bm := m as BaseMaterial3D
				var sm := ShaderMaterial.new()
				sm.shader = painted_shader
				sm.set_shader_parameter("albedo_tex", bm.albedo_texture)
				sm.set_shader_parameter("albedo_color", bm.albedo_color)
				sm.set_shader_parameter("alpha_test", bm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED)
				sm.set_shader_parameter("painted_light_mix", k)
				sm.set_shader_parameter("light_dir_world", to_light)
				sm.set_shader_parameter("wind_strength", 0.0)
				sm.set_shader_parameter("use_ao", false)
				mi.set_surface_override_material(s, sm)
	return inst

func _shots() -> void:
	var out: String = args.get("out", "/tmp")
	DirAccess.make_dir_recursive_absolute(out)
	var target := Vector3(float(args.get("tx", "0.5")), 1.0, float(args.get("tz", "1.0")))
	var tag: String = args.get("tag", "")
	for z in str(args.get("zooms", "68,40")).split(","):
		cam.size = float(z)
		cam.position = target + Vector3(75, 83, 75)
		cam.look_at(target, Vector3.UP)
		for _f in 12:
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(out.path_join("city_zoom%s%s.png" % [z, tag]))
	if str(args.get("colour", "0")) == "1":
		# cage-only close shot on a flat magenta background (ambient light is a fixed colour, unaffected)
		for n in made:
			if is_instance_valid(n) and n != cage_inst and n.get_parent() == self:
				n.visible = false
		ground.visible = false
		env.background_color = Color(1, 0, 1)
		cam.size = 6.5
		var t2 := Vector3(0, 1.6, 0)
		cam.position = t2 + Vector3(75, 83, 75)
		cam.look_at(t2, Vector3.UP)
		for _f in 12:
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(out.path_join("cage_colour%s.png" % tag))
	print("CAGETEST_DONE ", out)
	get_tree().quit()
