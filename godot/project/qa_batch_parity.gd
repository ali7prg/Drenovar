extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var original = load("res://tests/reference052/landscape.gd")
	var candidate = load("res://tests/reference053/landscape.gd")
	var comparisons := 0
	var expected_upload := 0
	var candidate_upload := 0
	for scene in ["city","world"]:
		var before = original.new()
		var after = candidate.new()
		root.add_child(before)
		root.add_child(after)
		await before.setup(data,data.demo,scene,{})
		await after.setup(data,data.demo,scene,{})
		for i in 24:
			var previous_masks: Array = before.render_batches.map(func(b): return b.mask)
			var position := Vector3(sin(i*.3)*35,0,cos(i*.3)*25)
			var zoom: float = [32.0,70.0,110.0][i%3] if scene == "city" else [60.0,100.0,260.0][i%3]
			for stage in [before,after]:
				stage.target=position
				stage.zoom=zoom
				stage.world_yaw=0.5 if scene == "world" else 0.0
				stage.update_camera(0,true)
			if before.render_batches.size()!=after.render_batches.size():
				push_error("Batch count changed");quit(1);return
			for index in before.render_batches.size():
				var a: Dictionary=before.render_batches[index]
				var b: Dictionary=after.render_batches[index]
				comparisons+=1
				if a.node.visible!=b.node.visible or a.mask!=b.mask or a.visible!=b.visible or a.total!=b.total:
					push_error("Visible instances changed: "+scene);quit(1);return
				if a.visible > 0:
					var used:int=a.visible*12
					if a.node.multimesh.buffer.slice(0,used)!=b.node.multimesh.buffer.slice(0,used):
						push_error("Instance transform changed");quit(1);return
					if b.capacity>b.total or b.capacity<b.visible:
						push_error("Capacity bound violation");quit(1);return
					if previous_masks[index] != a.mask:
						expected_upload+=a.total*48
						candidate_upload+=b.capacity*48
		before.free()
		after.free()
		await process_frame
	print("QA_BATCH_PARITY comparisons=",comparisons," failures=0 reference_buffer_bytes=",expected_upload," candidate_buffer_bytes=",candidate_upload)
	quit()
