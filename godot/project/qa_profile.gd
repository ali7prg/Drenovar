extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	var result: Array = []
	var tag := "native-profile"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=").validate_filename()
	for spec in [["city",70.0], ["city",32.0], ["world",100.0]]:
		if game.map_name != spec[0]:
			await game.show_scene(spec[0])
		game.stage.target = Vector3(5,0,-4)
		game.stage.zoom = spec[1]
		game.stage.update_camera(0,true)
		for _warm in 20:
			await game.get_tree().process_frame
		var frames: Array = []
		var cull: Array = []
		var draws: Array = []
		var primitives: Array = []
		for i in 60:
			var before := Time.get_ticks_usec()
			game.stage.target = Vector3(5+sin(i*.1)*16,0,-4+cos(i*.1)*12)
			game.stage.update_camera(0,true)
			cull.append((Time.get_ticks_usec()-before)/1000.0)
			await game.get_tree().process_frame
			frames.append((Time.get_ticks_usec()-before)/1000.0)
			draws.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
			primitives.append(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
		frames.sort(); cull.sort(); draws.sort(); primitives.sort()
		var row := {"scene":spec[0],"zoom":spec[1],"frame_median_ms":frames[30],"frame_p95_ms":frames[56],"cull_median_ms":cull[30],"cull_p95_ms":cull[56],"draws_median":draws[30],"triangles_median":primitives[30],"renderer":RenderingServer.get_current_rendering_method(),"adapter":RenderingServer.get_video_adapter_name(),"viewport":str(game.get_viewport().get_texture().get_size())}
		result.append(row)
		print("RENDER_PROFILE ", JSON.stringify(row))
		FileAccess.open("user://"+tag+"-render.json",FileAccess.WRITE).store_string(JSON.stringify(result,"  "))
	await game.show_scene("city")
	print("RENDER_PROFILE_DONE ", tag)

	quit()
