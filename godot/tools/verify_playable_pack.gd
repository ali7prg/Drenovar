extends SceneTree

# Verify the exported entry, not just a manually instantiated game behind a lab
# export override. No account credentials and no requests to the shared server.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var failures: Array[String] = []
	var entry: String = ProjectSettings.get_setting_with_override("application/run/main_scene")
	if OS.has_feature("combat_lab") or entry != "res://main.tscn":
		failures.append("export must open the interactive game")
	var game = load(entry).instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while game.scene_loading or not is_instance_valid(game.stage):
		if Time.get_ticks_msec() > deadline:
			push_error("playable city boot timeout")
			quit(1)
			return
		await process_frame
	if game.endpoint != "https://drenovar-game.ali069587.workers.dev": failures.append("unexpected game server")
	if game.api.requests_total != 0: failures.append("fresh install must wait for account confirmation")
	if not game.modal.visible or game.modal_title.text != "Аккаунт": failures.append("account entry missing")
	if not is_instance_valid(game.stage.combat_view): failures.append("combat presentation missing from main game")
	# Build 1021: data read at run time by the march lanes and the town plan.
	for data_file in ["res://assets/environment/scenery-footprints.json", "res://assets/city/town_lots.json"]:
		if not FileAccess.file_exists(data_file): failures.append("missing " + data_file)
	if load("res://src/march_lanes.gd").footprint_table().size() < 70: failures.append("scenery footprints not loaded")
	var models := 0
	var architecture := 0
	for id in game.data.unitModels:
		for role in (["field"] if id == "SIEGE-RAM-01" else ["preview", "field"]):
			var model = load(game.data.unitModels[id][role]).instantiate()
			if id != "SIEGE-RAM-01":
				var players: Array = model.find_children("*", "AnimationPlayer", true, false)
				if players.is_empty() or not players[0].has_animation("Death"): failures.append(id + " " + role)
			models += 1
			model.free()
	for type in game.data.levelModels:
		for level in range(6, 12):
			var packed = load(str(game.data.levelModels[type].get(str(level), {}).get("path", ""))) as PackedScene
			if packed == null:
				failures.append("missing building %s/%s" % [type, level])
				continue
			var model = packed.instantiate()
			if model.find_children("*", "MeshInstance3D", true, false).is_empty(): failures.append("empty building %s/%s" % [type, level])
			else: architecture += 1
			model.free()
	await game.show_scene("world")
	if game.map_name != "world" or not is_instance_valid(game.stage.combat_view): failures.append("world combat presentation missing")
	await game.show_scene("city")
	# Build 1022: five-unit roster (ENG-01, 02, 03, 04, 06) x preview+field, plus the siege ram field model.
	if models != 11 or architecture != 162: failures.append("model coverage changed")
	for kept in ["ENG-01", "ENG-02", "ENG-03", "ENG-04", "ENG-06"]:
		if not game.data.unitModels.has(kept): failures.append("missing unit model " + kept)
	print(JSON.stringify({"entry":entry,"build":ProjectSettings.get_setting("application/config/build_number"),"models_loaded":models,"architecture":architecture,"failures":failures,"scope":"Linux exported game pack; no physical iPhone acceptance"}))
	game.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)
