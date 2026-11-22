extends SceneTree
## Full-frame performance probe (port of delivery/tools/performance-probe.mjs ideas):
## 0.25 ms histogram distributions → p50/p95/p99 of the whole frame interval, plus CPU time of the
## world-layer camera update, draw calls, primitives, active forest instances and memory counters.
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile -s qa_forest_perf.gd -- --tag=after [--forest-rescue-v1=off]
## Numbers from this machine are SOFTWARE-RENDERED DESKTOP numbers (llvmpipe), NOT iPhone 12.

const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")

class Distribution:
	var bins := PackedInt32Array()
	var count := 0
	var total := 0.0
	var maximum := 0.0
	var over50 := 0
	var over100 := 0

	func _init() -> void:
		bins.resize(4001)

	func add(ms: float) -> void:
		if is_nan(ms) or ms < 0.0:
			return
		bins[mini(4000, int(floor(ms * 4.0)))] += 1
		count += 1
		total += ms
		maximum = maxf(maximum, ms)
		if ms > 50.0:
			over50 += 1
		if ms > 100.0:
			over100 += 1

	func percentile(q: float) -> Variant:
		var cumulative := 0
		for i in bins.size():
			cumulative += bins[i]
			if count > 0 and cumulative >= ceili(count * q):
				return ">=1000" if i == 4000 else (i + 1) / 4.0
		return null

	func report() -> Dictionary:
		return {"count": count, "meanMs": total / count if count else null, "p50UpperMs": percentile(0.5),
			"p95UpperMs": percentile(0.95), "p99UpperMs": percentile(0.99), "maxMs": maximum if count else null,
			"over50": over50, "over100": over100, "resolutionMs": 0.25}


var tag := "probe"
var out_dir := "res://../../forest_rescue/qa/ingame/world"
var frames_per_scenario := 90
var segments_mode := false
var save_frames := ""

## --segments: actor-aware probe. One scenario per evidence video segment at its busiest moment,
## played from recorded realm fixtures through a stub transport (live choreography included):
## environment triangles (forest instances + landmarks/arena at the chosen LOD), actor/prop
## triangles (visible meshes of every adventure rig at its current LOD), draw calls, primitives.
## Targets: environment <= 110k, environment + actors <= 180k triangles.
const FIXTURES := "res://data/forest_rescue/game/fixtures/"
const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const SEGMENTS := [
	{"name": "a_intro_horse_z40", "fixture": "intro_playing", "intro": true, "target": "lf_horse_origin", "zoom": 40.0, "seconds": 6.3},
	{"name": "b_route_follow_z38", "fixture": "prologue_moving", "target": "squad", "zoom": 38.0, "seconds": 1.0},
	{"name": "c_site1_unlock_exit_z26", "fixture": "site01_battle_victory", "live": "site01_cage_open", "target": "lf_site_01:cage", "zoom": 26.0, "seconds": 7.0},
	{"name": "c_site1_battle_z30", "fixture": "site01_battle_active", "target": "lf_site_01:guardian", "zoom": 30.0, "seconds": 1.0},
	{"name": "d_escort_home_z26", "fixture": "site01_escort_walking", "live": "site01_escort_home", "target": "lf_home_reception", "zoom": 26.0, "seconds": 3.0},
	{"name": "e_site2_rune_z26", "fixture": "site02_rune_1of3", "target": "lf_site_02", "zoom": 26.0, "seconds": 1.0},
	{"name": "f_boss_fight_z40", "fixture": "boss_battle_35", "target": "lf_boss_ancient_maw", "zoom": 40.0, "seconds": 1.0},
	{"name": "f_boss_fight_z68", "fixture": "boss_battle_60", "target": "lf_boss_ancient_maw", "zoom": 68.0, "seconds": 1.0},
	{"name": "g_escort_walking_z30", "fixture": "site01_escort_walking", "target": "squad", "zoom": 30.0, "seconds": 1.0},
	# look checks (run with --only=t_): the trail cache in its mechanism-UI zoom, the kit fallen trunk close up
	{"name": "t_trail_cache_z24", "fixture": "site01_trail_1of3", "target": "lf_site_01", "zoom": 24.0, "seconds": 1.0},
	{"name": "t_fallen_trunk_z12", "fixture": "site01_trail_1of3", "target_xz": [-74.04, 2.8], "zoom": 12.0, "seconds": 0.5},
	{"name": "t_trail_cache_ui", "fixture": "site01_trail_1of3", "target": "lf_site_01", "zoom": 24.0, "seconds": 1.0, "mech_ui": "lf_site_01"},
	{"name": "t_winch_z26", "fixture": "site03_winch_solved", "target": "lf_site_03", "zoom": 26.0, "seconds": 1.0},
	# the winch in its mechanism UI (zoom 28, the panel on the left): must read clearly, not hidden by the cage
	{"name": "t_winch_ui", "fixture": "site03_winch_solved", "target": "lf_site_03", "zoom": 28.0, "seconds": 1.0, "mech_ui": "lf_site_03"},
	{"name": "t_bush_z26", "fixture": "site02_rune_1of3", "target": "lf_site_02", "zoom": 26.0, "seconds": 1.0},
	{"name": "t_bush_z68", "fixture": "site02_rune_1of3", "target": "lf_site_02", "zoom": 68.0, "seconds": 1.0},
	{"name": "t_bush_z120", "fixture": "site02_rune_1of3", "target": "lf_site_02", "zoom": 120.0, "seconds": 1.0},
]

class StubHost extends Node:
	var main: Node
	var busy := false
	var replies: Array = []
	func request(_path: String, _payload: Variant = null, _key := "") -> Dictionary:
		return replies.pop_front() if not replies.is_empty() else {"error":"Сервер недоступен"}
	func accept(response: Dictionary) -> void:
		main.accept(response)
	func poll_account_state() -> void:
		pass


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=")
		elif arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
		elif arg.begins_with("--frames="):
			frames_per_scenario = int(arg.trim_prefix("--frames="))
		elif arg == "--segments":
			segments_mode = true
		elif arg.begins_with("--save-frames="):
			save_frames = arg.trim_prefix("--save-frames=")     # last frame of every segment (texture A/B checks)
	if OS.get_cmdline_user_args().has("--entry"):
		call_deferred("run_entry")
		return
	call_deferred("run_segments" if segments_mode else "run")


## Entry probe (iPhone smoothness): every frame interval from main.tscn's instantiation until the forest
## world is ready (+1 s), the longest single frame and where the world setup was, and the impostor source.
func run_entry() -> void:
	root.size = Vector2i(1366, 630)
	var t_start := Time.get_ticks_usec()
	var game = load("res://main.tscn").instantiate()
	# 1022: offline, fixture-fed (forest local-realm states predate V6): an unreachable loopback
	# endpoint, so accept() takes them and nothing reaches a real server (1021 qa_city_works pattern).
	game.endpoint = "http://127.0.0.1:9"
	game.loopback = true
	root.add_child(game)
	var first_frame_us := Time.get_ticks_usec() - t_start
	var intervals := PackedFloat32Array()
	var longest := 0.0
	var longest_at := ""
	var last := Time.get_ticks_usec()
	var ready_at := -1
	var frame := 0
	var forest_started := -1
	var stages: Array = []
	while frame < 4000:
		await process_frame
		frame += 1
		var now := Time.get_ticks_usec()
		var ms := (now - last) / 1000.0
		last = now
		intervals.append(ms)
		# the stage is only published to the game when its build is done: find the world layer in the tree
		var world: Node = root.find_child("ForestWorld", true, false)
		if world != null and forest_started < 0:
			forest_started = frame
		# each setup step sets its label, runs, then awaits: the label seen now names the work of this interval
		var where := "city" if world == null else ("forest:" + String(world.get("setup_stage")))
		stages.append(where)
		if ms > longest:
			longest = ms
			longest_at = "frame %d %s" % [frame, where.left(160)]
		if world != null and world.get("_ready_emitted") == true and ready_at < 0:
			ready_at = frame
		if ready_at > 0 and frame > ready_at + 30:
			break
	var forest_intervals := intervals.slice(maxi(0, forest_started - 1)) if forest_started > 0 else PackedFloat32Array()
	var sorted := forest_intervals.duplicate()
	sorted.sort()
	var pick := func(q: float) -> float: return sorted[clampi(int(q * (sorted.size() - 1)), 0, sorted.size() - 1)] if not sorted.is_empty() else 0.0
	var longest_forest := sorted[-1] if not sorted.is_empty() else 0.0
	var top := []
	var order := range(forest_intervals.size())
	order.sort_custom(func(a: int, b: int) -> bool: return forest_intervals[a] > forest_intervals[b])
	var offset := maxi(0, forest_started - 1)
	for i in mini(6, order.size()):
		top.append("%.0f ms (%s)" % [forest_intervals[order[i]], stages[offset + order[i]] if offset + order[i] < stages.size() else "?"])
	var ForestImpostors = load("res://src/forest_rescue/world/forest_impostors.gd")
	var row := {"format": "drenovar-forest-entry-probe-v1", "renderer": RenderingServer.get_current_rendering_method(),
		"adapter": RenderingServer.get_video_adapter_name(),
		"limits": "SOFTWARE-RENDERED desktop (llvmpipe/Xvfb) timings, NOT iPhone 12.",
		"mainSceneInstantiateMs": snappedf(first_frame_us / 1000.0, 0.1),
		"framesUntilForestReady": ready_at, "forestFrames": forest_intervals.size(),
		"forestEntryMs": snappedf(Array(forest_intervals).reduce(func(a, b): return a + b, 0.0), 1.0),
		"longestFrameMs": snappedf(longest_forest, 0.1), "longestFrameAt": longest_at,
		"topFramesMs": top, "p50Ms": snappedf(pick.call(0.5), 0.1), "p95Ms": snappedf(pick.call(0.95), 0.1),
		"p99Ms": snappedf(pick.call(0.99), 0.1), "impostorSource": String(ForestImpostors.source),
		"impostorShippedNote": String(ForestImpostors.shipped_note)}
	var world_now: Node = root.find_child("ForestWorld", true, false)
	if world_now != null:
		row.impostorSignatureParts = world_now.get("impostor_signature_parts")
	print("PERF_ENTRY ", JSON.stringify(row))
	quit()


func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))


## Pipeline compilations so far (Godot 4.4+ monitors): canvas, mesh (on mesh load), surface (on material /
## surface setup), draw (needed at draw time: the stutter kind), specialization (background).
func pipeline_counts() -> Dictionary:
	return {"canvas": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_CANVAS),
		"mesh": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_MESH),
		"surface": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SURFACE),
		"draw": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_DRAW),
		"specialization": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SPECIALIZATION)}


static func pipeline_delta(a: Dictionary, b: Dictionary) -> Dictionary:
	var out := {}
	for k in b:
		out[k] = int(b[k]) - int(a.get(k, 0))
	return out


static func frame_stats(intervals: PackedFloat32Array) -> Dictionary:
	var sorted := intervals.duplicate()
	sorted.sort()
	if sorted.is_empty():
		return {}
	var at := func(q: float) -> float: return snappedf(sorted[clampi(int(q * (sorted.size() - 1)), 0, sorted.size() - 1)], 0.1)
	return {"frames": sorted.size(), "p50Ms": at.call(0.5), "p95Ms": at.call(0.95), "p99Ms": at.call(0.99), "maxMs": snappedf(sorted[-1], 0.1)}


## Visible triangles of every adventure rig (actors + props) at its current LOD.
func actor_tris(forest: Node) -> Vector2i:
	var tris := 0
	var shown := 0
	for id in forest.actors.rigs:
		var rig = forest.actors.rigs[id]
		if not is_instance_valid(rig) or not rig.is_visible_in_tree() or rig.model == null:
			continue
		shown += 1
		for mesh: MeshInstance3D in rig.model.find_children("*", "MeshInstance3D", true, false):
			if mesh.mesh != null and mesh.is_visible_in_tree():
				tris += ForestKit.mesh_triangles(mesh.mesh)
	return Vector2i(tris, shown)


func run_segments() -> void:
	root.size = Vector2i(1366, 630)
	if OS.get_cmdline_user_args().has("--no-msaa"):
		root.msaa_3d = Viewport.MSAA_DISABLED       # look diagnosis (alpha-tested edge artefacts)
	var game = load("res://main.tscn").instantiate()
	# 1022: offline, fixture-fed (forest local-realm states predate V6): an unreachable loopback
	# endpoint, so accept() takes them and nothing reaches a real server (1021 qa_city_works pattern).
	game.endpoint = "http://127.0.0.1:9"
	game.loopback = true
	root.add_child(game)
	while game.get("scene_loading") or not is_instance_valid(game.get("stage")):
		await process_frame
	var forest: Node = game.forest_game
	var stub := StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub
	for warm in 10:
		await process_frame
	var stage: Node3D = game.stage
	var world: Node3D = stage.get("forest_world")
	var results: Array = []
	var only := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--only="):
			only = arg.trim_prefix("--only=")
	for spec in SEGMENTS:
		if String(spec.name).begins_with("t_") and not only.begins_with("t_"):
			continue          # look checks only on request
		if not only.is_empty() and not String(spec.name).begins_with(only):
			continue
		# The intro presentation owns the camera while it runs: end it before the next scenario.
		if forest.intro.presenting():
			forest.intro.finish_presentation()
		# The city stage can be rebuilt when a state is accepted: always use the live one.
		game.close_modal()
		forest.actors.on_stage_changed()
		forest.actors.first_state = true
		forest.client.adv = {}
		forest.client.primed = false
		var state := fixture(spec.fixture)
		var clock := float(state.get("adventure", {}).get("serverTime", 0.0))
		forest.client.manual_clock_ms = clock
		game.showing_cached_state = true  # 1022: fixtures may be older than the state on screen
		game.accept(state)
		game.battle_results.pending.clear()
		game.result_notice.hide()
		game.close_modal()
		await process_frame
		for settle in 5:
			await process_frame
		stage = game.stage
		world = stage.get("forest_world")
		if spec.get("intro", false):
			forest.intro.begin(true)
		var target := Vector3.INF
		for warm in 40:
			await process_frame
		for id in forest.actors.rigs:
			var rig = forest.actors.rigs[id]
			if is_instance_valid(rig) and rig.load_state == "loading":
				rig.poll_load(true)
		var pipes_before := pipeline_counts()
		var intervals := PackedFloat32Array()
		var last_us := Time.get_ticks_usec()
		var tex_mem := 0.0
		var vid_mem := 0.0
		if spec.has("mech_ui"):
			forest.mech.open(String(spec.mech_ui))      # the mechanism UI owns the camera (its own zoom)
			for f in 20:
				await process_frame
		if spec.has("live"):
			game.showing_cached_state = true  # 1022: fixtures may be older than the state on screen
			game.accept(fixture(spec.live))
			game.battle_results.pending.clear()
			game.result_notice.hide()
			game.close_modal()
		for step in int(float(spec.seconds) * 30.0):
			clock += 1000.0 / 30.0
			forest.client.manual_clock_ms = clock
			if spec.has("target_xz"):
				target = Vector3(float(spec.target_xz[0]), 0.0, float(spec.target_xz[1]))
				target.y = float(world.height_at(target.x, target.z)) if world != null else 0.0
			else:
				target = forest.actors.squad_focus() if String(spec.target) == "squad" else forest.target_position(String(spec.target))
			stage = game.stage
			world = stage.get("forest_world")
			if not spec.has("mech_ui"):
				if target != Vector3.INF:
					stage.target = target
				stage.zoom = float(spec.zoom)
				stage.update_camera(0.0, true)
			await process_frame
			var now_us := Time.get_ticks_usec()
			intervals.append((now_us - last_us) / 1000.0)
			last_us = now_us
			tex_mem = maxf(tex_mem, Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED))
			vid_mem = maxf(vid_mem, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED))
		if world != null and world.get("landmarks") != null and world.landmarks.has_method("finish_arena_load"):
			world.landmarks.finish_arena_load()
		var draws := PackedInt32Array()
		var prims := PackedInt32Array()
		var env := PackedInt32Array()
		var actors := PackedInt32Array()
		var totals := PackedInt32Array()
		var inst := PackedInt32Array()
		var shown_max := 0
		for i in 45:
			clock += 1000.0 / 30.0
			forest.client.manual_clock_ms = clock
			await process_frame
			var now2_us := Time.get_ticks_usec()
			intervals.append((now2_us - last_us) / 1000.0)
			last_us = now2_us
			tex_mem = maxf(tex_mem, Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED))
			vid_mem = maxf(vid_mem, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED))
			draws.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
			prims.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
			var snap: Dictionary = world.perf_snapshot() if world != null else {}
			var e := int(snap.get("tris_est", 0)) + int(snap.get("landmark_tris", 0))
			var a := actor_tris(forest)
			env.append(e)
			actors.append(a.x)
			totals.append(e + a.x)
			inst.append(int(snap.get("instances", 0)) + a.y)
			shown_max = maxi(shown_max, a.y)
		if OS.get_cmdline_user_args().has("--debug"):
			print("CAM ", spec.name, " zoom=", game.stage.camera_zoom, " target=", game.stage.camera_target, " same=", forest.stage == game.stage, " unlocked=", forest.client.unlocked(), " active=", forest.city_active(), " fproc=", forest.can_process(), " lodzoom=", forest.actors.lod_zoom)
			for id in forest.actors.rigs:
				var r = forest.actors.rigs[id]
				if is_instance_valid(r):
					print("RIG ", spec.name, " ", id, " ", r.load_state, " vis=", r.visible, " tree=", r.is_visible_in_tree(), " lod=", r.lod_level, " pos=", r.global_position.snapped(Vector3.ONE * 0.1))
		if not save_frames.is_empty():
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(save_frames.path_join(String(spec.name) + ".png"))
			if OS.get_cmdline_user_args().has("--tint-kinds") and world != null:
				# identification frame: every forest MultiMesh drawn flat in its kind's colour
				tint_kinds(world)
				for f in 3:
					await process_frame
				await RenderingServer.frame_post_draw
				root.get_texture().get_image().save_png(save_frames.path_join(String(spec.name) + "_tint.png"))
				tint_kinds(world, true)
		for arr in [draws, prims, env, actors, totals, inst]:
			arr.sort()
		var row := {"segment": spec.name, "zoom": spec.zoom,
			"envTrisMax": env[-1], "actorTrisMax": actors[-1], "totalTrisMax": totals[-1], "totalTrisMedian": totals[totals.size() / 2],
			"envBudgetOk": env[-1] <= 110000, "totalBudgetOk": totals[-1] <= 180000,
			"drawCallsMedian": draws[draws.size() / 2], "drawCallsMax": draws[-1],
			"primitivesMedian": prims[prims.size() / 2], "primitivesMax": prims[-1],
			"instancesMax": inst[-1], "actorRigsVisibleMax": shown_max,
			"frameTime": frame_stats(intervals), "textureMemMiBMax": snappedf(tex_mem / 1048576.0, 0.1),
			"videoMemMiBMax": snappedf(vid_mem / 1048576.0, 0.1),
			"pipelineCompilations": pipeline_delta(pipes_before, pipeline_counts())}
		results.append(row)
		print("PERF_SEGMENT ", JSON.stringify(row))
	var report := {"format": "drenovar-forest-segment-probe-v1", "tag": tag,
		"renderer": RenderingServer.get_current_rendering_method(), "adapter": RenderingServer.get_video_adapter_name(),
		"viewport": str(root.size), "targets": {"envTris": 110000, "totalTris": 180000},
		"impostorSource": String(load("res://src/forest_rescue/world/forest_impostors.gd").source),
		"limits": "SOFTWARE-RENDERED desktop (llvmpipe/Xvfb) counts and timings; NOT iPhone 12 measurements. Frame times are whole-frame intervals of the software renderer (relative comparisons only). Triangles: environment = forest instances (tris_est) + landmarks/arena at the chosen LOD; actors = visible meshes of adventure rigs at their LOD (upper bound, before Godot's automatic mesh LOD). draw calls / primitives are renderer totals incl. shadow passes.",
		"segments": results}
	var path := out_dir.path_join("perf_segments_" + tag + ".json")
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	print("PERF_DONE ", path)
	quit()


## --tint-kinds (with --save-frames): flat colour per forest asset kind (ferns red, reeds orange, brambles blue,
## grass magenta, branches brown, rocks grey, mushrooms white, golden oak yellow, green oak green, pine dark
## green, birch lilac, willow cyan, hollow oak purple) to identify what a look defect is.
const TINT_KINDS := {"under_fern": Color(1, 0, 0), "under_reed": Color(1, 0.5, 0), "under_bramble": Color(0, 0.3, 1),
	"under_grass": Color(1, 0, 1), "under_branches": Color(0.5, 0.25, 0), "under_rock": Color(0.5, 0.5, 0.5),
	"under_mushrooms": Color(1, 1, 1), "tree_lf_env_golden_oak_green": Color(0, 1, 0), "tree_lf_env_golden_oak": Color(1, 1, 0),
	"tree_lf_env_dark_pine": Color(0, 0.4, 0.2), "tree_lf_env_birch": Color(0.8, 0.8, 1), "tree_lf_env_willow": Color(0, 1, 1),
	"tree_lf_env_hollow_oak": Color(0.6, 0, 0.6)}

func tint_kinds(world: Node, clear := false) -> void:
	var canopy: Node = world.get("canopy")          # re-parented under the stage's forest group (attach_canopy)
	if canopy == null:
		return
	for node: MultiMeshInstance3D in canopy.find_children("*", "MultiMeshInstance3D", true, false):
		if clear:
			node.material_override = null
			continue
		var n := String(node.name)
		for prefix in TINT_KINDS:
			if n.begins_with(prefix):
				var m := StandardMaterial3D.new()
				m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
				m.albedo_color = TINT_KINDS[prefix]
				node.material_override = m
				break


func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	# 1022: offline, fixture-fed (forest local-realm states predate V6): an unreachable loopback
	# endpoint, so accept() takes them and nothing reaches a real server (1021 qa_city_works pattern).
	game.endpoint = "http://127.0.0.1:9"
	game.loopback = true
	root.add_child(game)
	var waited := 0
	while game.get("scene_loading") or not is_instance_valid(game.get("stage")):
		await process_frame
		waited += 1
		if waited > 4000:
			quit(2)
			return
	game.set_process(false)
	var stage: Node3D = game.stage
	var world: Node3D = stage.get("forest_world")
	for warm in 8:
		await process_frame
	if game.get("forest_game") != null:
		game.forest_game.process_mode = Node.PROCESS_MODE_DISABLED   # synthetic fixtures below
	# Environment budget (PERFORMANCE_AUDIT_RU / WORLD_LAYOUT_AND_FOG_RU): visible new environment
	# geometry ≤ 110k triangles, ≤ 4 full + ≤ 8 light (proxy) chunks, fog alpha overdraw ≤ 3.
	# atlas v2 spots (art/01 masterplan): grove + glade 01, south pines, bridge, arena, west oaks,
	# east willows, the waterfall below the arena.
	var scenarios := [
		{"name": "town_default_z68_locked", "zoom": 68.0, "center": Vector3(5, 0, -4), "radius": Vector2(16, 12)},
		{"name": "forest_edge_z68_locked", "zoom": 68.0, "center": Vector3(-30, 0, -70), "radius": Vector2(30, 18)},
		{"name": "overview_z120_locked", "zoom": 120.0, "center": Vector3(0, 0, 0), "radius": Vector2(20, 14)},
		{"name": "town_z40_explored", "zoom": 40.0, "center": Vector3(0, 0, -30), "radius": Vector2(10, 8), "explored": true},
		{"name": "grove_z40_explored", "zoom": 40.0, "center": Vector3(-84, 0, -16), "radius": Vector2(10, 8), "explored": true},
		{"name": "spruce_z40_explored", "zoom": 40.0, "center": Vector3(58, 0, 90), "radius": Vector2(10, 8), "explored": true},
		{"name": "bridge_z40_explored", "zoom": 40.0, "center": Vector3(88, 0, 16), "radius": Vector2(8, 6), "explored": true},
		{"name": "arena_z40_explored", "zoom": 40.0, "center": Vector3(20, 0, -90), "radius": Vector2(8, 6), "explored": true},
		{"name": "grove_z68_explored", "zoom": 68.0, "center": Vector3(-76, 0, 8), "radius": Vector2(24, 16), "explored": true},
		{"name": "east_z68_explored", "zoom": 68.0, "center": Vector3(90, 0, -36), "radius": Vector2(24, 16), "explored": true},
		{"name": "overview_z120_explored", "zoom": 120.0, "center": Vector3(0, 0, 0), "radius": Vector2(20, 14), "explored": true},
		{"name": "close_z32_glade_explored", "zoom": 32.0, "center": Vector3(-80, 0, -11), "radius": Vector2(8, 6), "explored": true},
		{"name": "arena_z32_explored", "zoom": 32.0, "center": Vector3(20, 0, -90), "radius": Vector2(6, 5), "explored": true},
		{"name": "bridge_z32_explored", "zoom": 32.0, "center": Vector3(88, 0, 16), "radius": Vector2(6, 5), "explored": true},
		{"name": "waterfall_z40_explored", "zoom": 40.0, "center": Vector3(22, 0, -66), "radius": Vector2(8, 6), "explored": true},
		{"name": "entrance_z32_unlocked", "zoom": 32.0, "center": Vector3(-11, 0, -58), "radius": Vector2(5, 4)},
	]
	var results: Array = []
	for spec in scenarios:
		if world != null:
			if spec.get("explored", false):
				var bits := PackedByteArray()
				bits.resize(392)
				bits.fill(255)
				world.apply_adventure({"access": {"unlocked": true, "hallLevel": 3}, "intro": {"status": "acknowledged"},
					"fog": {"visibleBase64": Marshalls.raw_to_base64(bits), "revision": 9}})
				world.fog.finish_now()
			else:
				world.apply_adventure({})
		stage.target = spec.center
		stage.zoom = spec.zoom
		stage.update_camera(0.0, true)
		for warm in 12:
			await process_frame
		var frame := Distribution.new()
		var cull := Distribution.new()
		var draws := PackedInt32Array()
		var prims := PackedInt32Array()
		var instances := PackedInt32Array()
		var tris_est := PackedInt32Array()
		var landmark_tris := PackedInt32Array()
		var env_tris := PackedInt32Array()
		var full_max := 0
		var proxy_max := 0
		var last := Time.get_ticks_usec()
		for i in frames_per_scenario:
			var a := TAU * i / float(frames_per_scenario)
			stage.target = spec.center + Vector3(sin(a) * spec.radius.x, 0, cos(a) * spec.radius.y)
			var before := Time.get_ticks_usec()
			stage.update_camera(0.0, true)
			cull.add((Time.get_ticks_usec() - before) / 1000.0)
			await process_frame
			var now := Time.get_ticks_usec()
			frame.add((now - last) / 1000.0)
			last = now
			draws.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
			prims.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
			if world != null:
				var snap: Dictionary = world.perf_snapshot()
				instances.append(int(snap.instances))
				tris_est.append(int(snap.tris_est))
				landmark_tris.append(int(snap.get("landmark_tris", 0)))
				env_tris.append(int(snap.tris_est) + int(snap.get("landmark_tris", 0)))
				full_max = maxi(full_max, int(snap.full_chunks))
				proxy_max = maxi(proxy_max, int(snap.proxy_chunks))
		draws.sort()
		prims.sort()
		instances.sort()
		tris_est.sort()
		landmark_tris.sort()
		env_tris.sort()
		var row := {"scenario": spec.name, "zoom": spec.zoom, "frame": frame.report(), "cameraUpdateCpu": cull.report(),
			"drawCallsMedian": draws[draws.size() / 2], "drawCallsMax": draws[-1],
			"primitivesMedian": prims[prims.size() / 2], "primitivesMax": prims[-1],
			"forestInstancesMedian": instances[instances.size() / 2] if not instances.is_empty() else 0,
			"forestTrisEstMedian": tris_est[tris_est.size() / 2] if not tris_est.is_empty() else 0,
			"landmarkTrisMedian": landmark_tris[landmark_tris.size() / 2] if not landmark_tris.is_empty() else 0,
			"envTrisMedian": env_tris[env_tris.size() / 2] if not env_tris.is_empty() else 0,
			"envTrisMax": env_tris[-1] if not env_tris.is_empty() else 0,
			"envBudgetOk": (env_tris[-1] if not env_tris.is_empty() else 0) <= 110000 and full_max <= 4 and proxy_max <= 8,
			"fullChunksMax": full_max, "proxyChunksMax": proxy_max,
			"objects": Performance.get_monitor(Performance.OBJECT_COUNT),
			"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
			"videoMemMiB": Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0,
			"textureMemMiB": Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0,
			"bufferMemMiB": Performance.get_monitor(Performance.RENDER_BUFFER_MEM_USED) / 1048576.0,
			"staticMemMiB": Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0}
		if world != null:
			var snap: Dictionary = world.perf_snapshot()
			row.chunks = {"full": snap.full_chunks, "proxy": snap.proxy_chunks, "fogOnly": snap.fog_only_chunks}
		results.append(row)
		print("PERF ", tag, " ", JSON.stringify(row))
	var report := {"format": "drenovar-forest-world-probe-v1", "tag": tag, "flagOn": world != null,
		"renderer": RenderingServer.get_current_rendering_method(), "adapter": RenderingServer.get_video_adapter_name(),
		"viewport": str(root.size), "framesPerScenario": frames_per_scenario,
		"limits": "Software-rendered desktop (llvmpipe/Xvfb) wall-clock frame intervals; NOT iPhone 12 measurements. renderer counts are submitted draw calls/primitives incl. shadow passes.",
		"setup": world.perf_snapshot().setup_ms if world != null else {}, "scenarios": results}
	var path := out_dir.path_join("perf_" + tag + ".json")
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	print("PERF_DONE ", path)
	quit()
