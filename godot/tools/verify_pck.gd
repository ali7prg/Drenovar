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
