extends SceneTree

# Combat v0.1.0 binding audit (headless, offline, no network).
# For every in-game model (assets/game.json unitModels preview+field, creatureModels)
# load the matching combat_v010 library and check that each track resolves to an
# existing node and bone through the model's own AnimationPlayer root, and compare
# the library's first-frame bone positions with the target skeleton's rest.
# Writes res://combat_v010/reports/binding_audit.json. Exit code 1 on any failure.

const Registry := preload("res://combat_v010/runtime/combat_v010_registry.gd")

func _init() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var report := {"engine": Engine.get_version_info().string, "models": [], "failures": 0}
	var targets: Array = []
	for id in data.unitModels:
		for lod in ["preview", "field"]:
			targets.append({"kind": "troop", "id": id, "model": data.unitModels[id][lod]})
	for species in data.creatureModels:
		for path in data.creatureModels[species]:
			targets.append({"kind": "creature", "id": species, "model": path})
	for t in targets:
		var row := audit(t)
		report.models.append(row)
		if not row.ok:
			report.failures += 1
		print("%s %s %s tracks=%d missing=%d bad_keys=%d scale=%d node=%d seam=%.3f rest_dev_max=%.4f" % ["OK " if row.ok else "BAD", t.id, t.model, row.tracks, row.missing.size(), row.bad_keys, row.scale_tracks, row.node_tracks, row.loop_seam_max_rad, row.rest_position_deviation_max])
	DirAccess.make_dir_recursive_absolute("res://combat_v010/reports")
	var f := FileAccess.open("res://combat_v010/reports/binding_audit.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  ", false))
	f.close()
	print("binding audit: %d models, %d failures" % [report.models.size(), report.failures])
	quit(1 if report.failures > 0 else 0)

func audit(t: Dictionary) -> Dictionary:
	var row := {"id": t.id, "model": t.model, "ok": false, "tracks": 0, "missing": [], "rest_position_deviation_max": 0.0, "worst_bone": ""}
	var lib_path := Registry.library_path_for_model(t.model) if t.kind == "creature" else Registry.troop_library_path(t.id)
	row.library = lib_path
	var library := load(lib_path) as AnimationLibrary
	var scene := load(t.model) as PackedScene
	if library == null or scene == null:
		row.missing.append("load failed")
		return row
	var model := scene.instantiate() as Node3D
	var players := model.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		row.missing.append("no AnimationPlayer")
		model.free()
		return row
	var player := players[0] as AnimationPlayer
	var root := player.get_node(player.root_node)
	row.player = str(model.get_path_to(player))
	row.bad_keys = 0
	row.scale_tracks = 0
	row.node_tracks = 0
	row.loop_seam_max_rad = 0.0
	row.clips = {}
	for clip in library.get_animation_list():
		var anim := library.get_animation(clip)
		row.clips[clip] = {"length": anim.length, "loop": anim.loop_mode != Animation.LOOP_NONE}
		for i in anim.get_track_count():
			var type := anim.track_get_type(i)
			if type == Animation.TYPE_SCALE_3D:
				row.scale_tracks += 1
			for k in anim.track_get_key_count(i):
				var v: Variant = anim.track_get_key_value(i, k)
				if v is Quaternion and (not v.is_finite() or absf(v.length() - 1.0) > 0.001):
					row.bad_keys += 1
				elif v is Vector3 and not v.is_finite():
					row.bad_keys += 1
			if anim.loop_mode != Animation.LOOP_NONE and type == Animation.TYPE_ROTATION_3D and anim.track_get_key_count(i) > 1:
				var a: Quaternion = anim.track_get_key_value(i, 0)
				var b: Quaternion = anim.track_get_key_value(i, anim.track_get_key_count(i) - 1)
				row.loop_seam_max_rad = maxf(row.loop_seam_max_rad, a.angle_to(b))
		for i in anim.get_track_count():
			row.tracks += 1
			var path := anim.track_get_path(i)
			if path.get_subname_count() == 0:
				# A transform track on a node (not a bone) would move the actor root.
				row.node_tracks += 1
			var node := root.get_node_or_null(NodePath(path.get_concatenated_names()))
			if node == null:
				row.missing.append("%s: node %s" % [clip, path.get_concatenated_names()])
				continue
			if path.get_subname_count() > 0:
				var sk := node as Skeleton3D
				var bone_name := path.get_concatenated_subnames()
				var bone := sk.find_bone(bone_name) if sk != null else -1
				if bone < 0:
					row.missing.append("%s: bone %s" % [clip, bone_name])
					continue
				if anim.track_get_type(i) == Animation.TYPE_POSITION_3D and anim.track_get_key_count(i) > 0:
					var first: Vector3 = anim.track_get_key_value(i, 0)
					var dev := first.distance_to(sk.get_bone_rest(bone).origin)
					if dev > row.rest_position_deviation_max:
						row.rest_position_deviation_max = dev
						row.worst_bone = "%s/%s" % [clip, bone_name]
	row.ok = row.missing.is_empty() and row.tracks > 0 and row.bad_keys == 0 and row.scale_tracks == 0 and row.node_tracks == 0
	if row.missing.size() > 12:
		row.missing = row.missing.slice(0, 12) + ["…"]
	model.free()
	return row
