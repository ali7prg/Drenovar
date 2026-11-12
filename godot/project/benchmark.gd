extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	await process_frame
	game.set_process(false)
	for scene in ["city", "world"]:
		if scene != game.map_name:
			await game.show_scene(scene)
		var stage = game.stage
		stage.zoom = 46.0 if scene == "city" else 100.0
		stage.target = Vector3.ZERO
		stage.update_camera(0, true)
		var durations: Array = []
		for i in 120:
			stage.target = Vector3(sin(i * 0.08) * 30, 0, cos(i * 0.08) * 22)
			var start = Time.get_ticks_usec()
			stage.update_camera(0, true)
			durations.append((Time.get_ticks_usec() - start) / 1000.0)
			await process_frame
		durations.sort()
		print("BENCH ", scene, " cull median_ms=", durations[60], " p95_ms=", durations[113], " batches=", stage.render_batches.size())
		if DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("/workspace/scratch/3674ed446801/" + scene + "-" + str(ProjectSettings.get_setting("application/config/version")) + ".png")
	quit()
