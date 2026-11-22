extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var failures: Array = []
	if not OS.has_feature("combat_lab"): failures.append("offline lab feature missing")
	if ProjectSettings.get_setting_with_override("application/run/main_scene") != "res://combat_lab.tscn": failures.append("offline entry scene missing")
	var lab = load("res://combat_lab.tscn").instantiate()
	root.add_child(lab)
	while lab.loading: await process_frame
	if not is_instance_valid(lab.stage): failures.append("lab did not boot")
	var models := 0
	var architecture := 0
	for id in lab.data.unitModels:
		for role in (["field"] if id=="SIEGE-RAM-01" else ["preview","field"]):
			var model = load(lab.data.unitModels[id][role]).instantiate()
			if id!="SIEGE-RAM-01":
				var players: Array = model.find_children("*","AnimationPlayer",true,false)
				if players.is_empty() or not players[0].has_animation("Death"): failures.append(id+" "+role)
			models+=1;model.free()
	for type in lab.data.levelModels:
		for level in range(6,12):
			var entry: Dictionary=lab.data.levelModels[type].get(str(level),{})
			var packed=load(str(entry.get("path",""))) as PackedScene
			if packed==null:failures.append("missing building: %s/%s"%[type,level]);continue
			var model=packed.instantiate()
			if model.find_children("*","MeshInstance3D",true,false).is_empty():failures.append("empty building: %s/%s"%[type,level])
			else:architecture+=1
			model.free()
	if lab.cases.size()!=77:failures.append("expected 77 selectable fixtures")
	if models!=21 or architecture!=162:failures.append("model coverage changed")
	lab.queue_free();await process_frame
	print(JSON.stringify({"lab_boot":true,"models_loaded":models,"architecture":architecture,"failures":failures,"scope":"Linux exported pack load; no iOS acceptance"}))
	quit(0 if failures.is_empty() else 1)
