extends SceneTree
# Runs against an exported PCK (--main-pack): game boots, city and world build,
# all ten troop scenes and clips load from the package.
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	print("VERSION ", ProjectSettings.get_setting("application/config/version"))
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var t := Time.get_ticks_msec()
	while (game.scene_loading or not is_instance_valid(game.stage)) and Time.get_ticks_msec() - t < 60000:
		await process_frame
	print("CITY ", is_instance_valid(game.stage), " batches ", game.stage.render_batches.size(), " parade_slots ", game.stage.parade_slots.size())
	# Let the city run so the parade spawns its soldiers, then check which models they are.
	var stage = game.stage
	stage.target = stage.parade_center
	stage.zoom = 40
	stage.update_camera(0, true)
	for i in 60:
		await process_frame
	var spawned := {}
	for actor in stage.parade.get_children():
		if actor is Node3D and String(actor.scene_file_path) != "":
			spawned[String(actor.scene_file_path)] = true
	var new_models: int = spawned.keys().filter(func(p): return p.contains("troops06")).size()
	print("PARADE_MODELS ", spawned.keys(), " troops06=", new_models)
	await game.show_scene("world")
	print("WORLD ", game.map_name, " batches ", game.stage.render_batches.size())
	var data: Dictionary = game.data
	var ok := 0
	for id in data.unitModels:
		for role in ["preview", "field"]:
			var scene := load(data.unitModels[id][role]) as PackedScene
			if scene == null:
				print("MISSING ", id, " ", role); continue
			var m: Node3D = scene.instantiate()
			var ap: AnimationPlayer = m.find_children("*", "AnimationPlayer", true, false)[0]
			var clips := ap.get_animation_list()
			if clips.has("Idle") and clips.has("Walk") and clips.has(data.unitModels[id].drill):
				ok += 1
			m.free()
	print("TROOP_SCENES_OK ", ok, " of 20")
	print("TROOP_PATH ", data.unitModels["ENG-01"].preview)
	quit(0)
