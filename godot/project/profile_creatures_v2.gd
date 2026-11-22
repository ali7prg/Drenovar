extends SceneTree

# creatures-v2 performance probe: N animated creatures (all species and levels) at game scale in
# one view, measured after a warm-up: frame time median/p95, draw calls, primitives, texture and
# video memory, cold load time of every model. --flag=off measures the 0.5.9 models the same way.
#   DISPLAY=:99 godot --path godot/project --rendering-method gl_compatibility \
#     -s profile_creatures_v2.gd -- --flag=on --count=12 --seconds=60 --runs=3
# On this Linux container the renderer is llvmpipe (CPU): the numbers compare old/new models under
# identical conditions; they are not iPhone measurements.

const CreatureVisuals = preload("res://src/creature_visuals.gd")
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const Landscape = preload("res://src/landscape.gd")
var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	call_deferred("run")

func run() -> void:
	var on: bool = args.get("flag", "on") == "on"
	CreatureVisuals.set_enabled(on)
	CombatV010.set_enabled(true)
	var count := int(args.get("count", "12"))
	var seconds := float(args.get("seconds", "60"))
	var runs := int(args.get("runs", "3"))
	root.size = Vector2i(1280, 720)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color("#7f9aa8")
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color("#c9d3e0")
	e.ambient_light_energy = 0.6
	env.environment = e
	world.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	world.add_child(sun)
	sun.look_at_from_position(Vector3(10, 20, 8), Vector3.ZERO, Vector3.UP)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(200, 200)
	ground.mesh = pm
	world.add_child(ground)
	var cam := Camera3D.new()
	cam.fov = 40.0
	world.add_child(cam)
	# --near: a hunt seen up close (LOD1); default: the whole group from the world-map height (mostly LOD2)
	var near: bool = args.has("near")
	cam.look_at_from_position(Vector3(0, 16, 22) if near else Vector3(0, 34, 46), Vector3(0, 2, 0), Vector3.UP)
	cam.make_current()
	await process_frame
	var tex0 := Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)
	var vid0 := Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)
	var species := ["velkor", "tenerys", "kamneklyk", "dragor"]
	var load_ms := {}
	var actors: Array = []
	for i in count:
		var sp: String = species[i % 4]
		var level := 1 + (i / 4) % 3
		var legacy: String = data.creatureModels[sp][level - 1]
		var path := CreatureVisuals.model_path(sp, level, legacy)
		var t0 := Time.get_ticks_usec()
		var scene: PackedScene = load(path)
		if not load_ms.has(path):
			load_ms[path] = snappedf((Time.get_ticks_usec() - t0) / 1000.0, 0.1)
		var a := scene.instantiate() as Node3D
		world.add_child(a)
		var k := Landscape.creature_scale(level) * CreatureVisuals.display_scale(sp)
		a.scale = Vector3.ONE * k
		a.position = Vector3((i % 6 - 2.5) * 11.0, 0, (i / 6 - 0.5) * 13.0)
		a.rotation.y = -PI * 0.5 + 0.3 * i
		CreatureVisuals.install(a, sp, level, k)
		if CombatV010.install(a, "creature", path):
			CombatV010.drive(a, [&"walk", &"idle", &"attack_a", &"run"][i % 4] if i % 4 != 2 else &"idle")
		else:
			var p: AnimationPlayer = a.find_children("*", "AnimationPlayer", true, false)[0]
			var anim := p.get_animation_list()[i % p.get_animation_list().size()]
			p.get_animation(anim).loop_mode = Animation.LOOP_LINEAR
			p.play(anim)
		actors.append(a)
	for f in 120:
		for a in actors:
			CreatureVisuals.update_lod(a, cam)  # as landscape.present_creatures does every frame
		await process_frame
	var results := []
	for r in runs:
		var times := PackedFloat32Array()
		var last := Time.get_ticks_usec()
		var start := last
		var draws := 0.0
		var prims := 0.0
		var n := 0
		while (Time.get_ticks_usec() - start) / 1e6 < seconds:
			for a in actors:
				CreatureVisuals.update_lod(a, cam)
			await process_frame
			var now := Time.get_ticks_usec()
			times.append((now - last) / 1000.0)
			last = now
			draws += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
			prims += Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
			n += 1
		times.sort()
		results.append({"frames": n, "median_ms": snappedf(times[times.size() / 2], 0.01), "p95_ms": snappedf(times[int(times.size() * 0.95)], 0.01),
			"draw_calls": roundi(draws / n), "primitives": roundi(prims / n)})
	var lod_counts := {}
	for a in actors:
		var lod := CreatureVisuals.update_lod(a, cam)
		lod_counts[str(lod)] = int(lod_counts.get(str(lod), 0)) + 1
	var out := {"flag": "creatures-v2" if on else "0.5.9 models", "view": "near" if near else "far", "creatures": count, "seconds": seconds, "runs": results, "lod_counts": lod_counts,
		"texture_mem_mb": snappedf((Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) - tex0) / 1048576.0, 0.1),
		"video_mem_mb": snappedf((Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) - vid0) / 1048576.0, 0.1),
		"static_mem_mb": snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1),
		"cold_load_ms": load_ms, "renderer": RenderingServer.get_video_adapter_name(), "method": "Linux container, Xvfb, CPU rasteriser; not a target device"}
	print("PROFILE_CREATURES_V2 ", JSON.stringify(out))
	quit()
