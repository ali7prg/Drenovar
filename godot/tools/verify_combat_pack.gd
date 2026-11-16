extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var failures: Array = []
	if not OS.has_feature("combat_lab"): failures.append("offline lab feature missing")
	var lab = load("res://combat_lab.tscn").instantiate()
	root.add_child(lab)
	while lab.loading: await process_frame
	if not is_instance_valid(lab.stage): failures.append("lab did not boot")
	var models := 0
	for id in lab.data.unitModels:
		for role in (["field"] if id=="SIEGE-RAM-01" else ["preview","field"]):
			var model = load(lab.data.unitModels[id][role]).instantiate()
			if id!="SIEGE-RAM-01":
				var players: Array = model.find_children("*","AnimationPlayer",true,false)
				if players.is_empty() or not players[0].has_animation("Death"): failures.append(id+" "+role)
			models+=1;model.free()
	lab.queue_free();await process_frame
	print(JSON.stringify({"lab_boot":true,"models_loaded":models,"failures":failures,"scope":"Linux exported pack load; no iOS acceptance"}))
	quit(0 if failures.is_empty() else 1)
