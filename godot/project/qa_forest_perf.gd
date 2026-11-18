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


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=")
		elif arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
		elif arg.begins_with("--frames="):
			frames_per_scenario = int(arg.trim_prefix("--frames="))
	call_deferred("run")


func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
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
	var scenarios := [
		{"name": "town_default_pan", "zoom": 70.0, "center": Vector3(5, 0, -4), "radius": Vector2(16, 12)},
		{"name": "forest_edge_pan_locked", "zoom": 70.0, "center": Vector3(-30, 0, -70), "radius": Vector2(30, 18)},
		{"name": "overview_zoom120", "zoom": 120.0, "center": Vector3(0, 0, 0), "radius": Vector2(20, 14)},
		{"name": "close_zoom32_glade", "zoom": 32.0, "center": Vector3(-20, 0, -62), "radius": Vector2(10, 8)},
		{"name": "explored_forest_pan", "zoom": 60.0, "center": Vector3(-60, 0, -40), "radius": Vector2(28, 22), "explored": true},
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
		draws.sort()
		prims.sort()
		instances.sort()
		tris_est.sort()
		var row := {"scenario": spec.name, "zoom": spec.zoom, "frame": frame.report(), "cameraUpdateCpu": cull.report(),
			"drawCallsMedian": draws[draws.size() / 2], "drawCallsMax": draws[-1],
			"primitivesMedian": prims[prims.size() / 2], "primitivesMax": prims[-1],
			"forestInstancesMedian": instances[instances.size() / 2] if not instances.is_empty() else 0,
			"forestTrisEstMedian": tris_est[tris_est.size() / 2] if not tris_est.is_empty() else 0,
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
