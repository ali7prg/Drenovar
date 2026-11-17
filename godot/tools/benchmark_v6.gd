extends SceneTree
# Identical authored I–V fixture for baseline/current; CPU-only in headless mode.
# No login, endpoint, network requests or player save is involved.
var output := ""
var level := 5
var fixture := ""
func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--report="): output = arg.trim_prefix("--report=")
		if arg.begins_with("--fixture="): fixture = arg.trim_prefix("--fixture=")
		if arg.begins_with("--level="): level = int(arg.trim_prefix("--level="))
	call_deferred("run")
func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	if FileAccess.file_exists("res://assets/city/architecture-v6/manifest.json"):
		var art: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/city/architecture-v6/manifest.json"))
		for type: String in art.levels:
			if not data.levelModels.has(type): data.levelModels[type] = {}
			data.levelModels[type].merge(art.levels[type], false)
	var state: Dictionary = data.demo.duplicate(true)
	if not fixture.is_empty(): state.city.buildings = JSON.parse_string(FileAccess.get_file_as_string(fixture))
	for building: Dictionary in state.city.buildings: building.level = level
	state.serverTime = 0
	var result := {"engine":Engine.get_version_info().string, "device":"Linux headless CPU; no GPU or physical iPhone measurements", "building_count":state.city.buildings.size(), "level":level, "scenarios":[]}
	for scene: String in ["city", "world"]:
		var stage = load("res://src/landscape.gd").new()
		root.add_child(stage)
		var started := Time.get_ticks_usec()
		await stage.setup(data, state, scene, {})
		var loading := (Time.get_ticks_usec() - started) / 1000.0
		stage.set_process(false)
		stage.zoom = 46.0 if scene == "city" else 100.0
		var samples: Array[float] = []
		for i in 140:
			stage.target = Vector3(sin(i * 0.08) * 30, 0, cos(i * 0.08) * 22)
			started = Time.get_ticks_usec()
			stage.update_camera(0, true)
			stage.present(state)
			if i >= 20: samples.append((Time.get_ticks_usec() - started) / 1000.0)
			await process_frame
		samples.sort()
		result.scenarios.append({"scene":scene,"load_ms":loading,"cpu_median_ms":samples[60],"cpu_p95_ms":samples[113],"render_batches":stage.render_batches.size(),"static_memory_bytes":OS.get_static_memory_usage()})
		stage.queue_free()
		await process_frame
	var file := FileAccess.open(output,FileAccess.WRITE)
	file.store_string(JSON.stringify(result,"\t"))
	file.close()
	print("V6_BENCHMARK_DONE level=",level)
	quit()
