extends Node3D
## Loads every human GLB with the game's Rig (actor_rig.gd): blocking load, LOD discovery, clip
## resolution against the meta, marker dispatch (weapon_contact / latch_release), locomotion speed
## matching, captive variant look (painted light + tint + hidden accessory). Writes report.json +
## a city-camera screenshot.
const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const IDS := ["lf_squad_captain", "lf_squad_shield_guard", "lf_squad_scout", "lf_civilian_miller",
	"lf_civilian_herbalist", "lf_civilian_ferryman", "lf_civilian_courier", "lf_civilian_cooper",
	"lf_civilian_quarry_worker"]
var out := "/tmp"
var report := {}
var rigs := {}
var marks := {}
var cam: Camera3D

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	var variants: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/forest_rescue/humans/captive_variants.json"))
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#8b9874")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d8e5ee")
	env.ambient_light_energy = 0.58
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -32, 0)
	sun.light_color = Color("#ffe4b8")
	sun.light_energy = 1.85
	sun.shadow_enabled = true
	add_child(sun)
	Rig.ForestKit.light_dir = sun.global_transform.basis.z.normalized()
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.environment = env
	cam.near = 0.5
	cam.far = 700
	add_child(cam)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(200, 200)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.40, 0.42, 0.24)
	ground.material_override = gm
	add_child(ground)
	var perp := Vector3(1, 0, -1).normalized()
	for i in IDS.size():
		var id: String = IDS[i]
		var rig := Rig.new()
		rig.setup(id, "res://assets/forest_rescue/humans/%s.glb" % id)
		if id.begins_with("lf_civilian"):
			var visual := id.substr(12)
			var picked := {}
			for cid in variants.captives:
				var v: Dictionary = variants.captives[cid]
				if v.visual == visual and int(v.variant) == 1:
					picked = v
			rig.variant = picked
		add_child(rig)
		rig.position = perp * (i - 4) * 1.15
		rig.rotation.y = PI / 4
		rig.poll_load(true)
		rig.marker.connect(_on_marker)
		var meta: Dictionary = rig.meta
		var r := {"ready": rig.is_ready(), "lods": [rig.lods[0].size(), rig.lods[1].size(), rig.lods[2].size()],
			"clips_ok": 0, "clips_missing": [], "length_mismatch": [], "variant": rig.variant.get("tintNames", {}),
			"painted": false}
		for clip_id in meta.get("clips", {}):
			if not rig.has_clip([clip_id]):
				r.clips_missing.append(clip_id)
				continue
			var want := float(meta.clips[clip_id].get("seconds", 0.0))
			if absf(rig.clip_length([clip_id]) - want) > 0.05:
				r.length_mismatch.append([clip_id, rig.clip_length([clip_id]), want])
			else:
				r.clips_ok += 1
		for mi: MeshInstance3D in rig.model.find_children("*", "MeshInstance3D", true, false):
			if mi.get_surface_override_material(0) is ShaderMaterial:
				r.painted = true
		rig.set_lod(0)
		report[id] = r
		rigs[id] = rig
		if id.begins_with("lf_squad"):
			rig.play(["lf_soldier_attack"], 0.0, true)
		else:
			rig.locomote(1.2, {"idle": ["lf_civilian_wait", "Idle"], "walk": ["lf_civilian_follow", "Walk"], "walk_speed": 1.2})
	_run.call_deferred()

func _on_marker(rig: Node3D, clip_id: String, marker_name: String) -> void:
	var key := String(rig.name) + ":" + clip_id + ":" + marker_name
	marks[key] = int(marks.get(key, 0)) + 1

func _run() -> void:
	for _f in 45:
		await get_tree().process_frame
	# civilians: speed matching of the follow walk
	for id in IDS:
		var rig = rigs[id]
		if id.begins_with("lf_civilian"):
			report[id]["walk_speed_scale_at_1.2"] = rig.player.speed_scale if rig.player else -1
	# squad: unlock (latch_release marker at 1.6 s)
	for id in IDS:
		if id.begins_with("lf_squad"):
			rigs[id].play(["lf_soldier_unlock"], 0.0, true)
	for _f in 80:
		await get_tree().process_frame
	for id in IDS:
		if id.begins_with("lf_squad"):
			rigs[id].play(["lf_soldier_idle"], 0.2)
		else:
			rigs[id].play(["lf_civilian_wait"], 0.2)
	report["_markers"] = marks
	for z in [7.5, 40.0]:
		cam.size = z
		cam.position = Vector3(0, 0.9, 0) + Vector3(75, 83, 75)
		cam.look_at(Vector3(0, 0.9, 0), Vector3.UP)
		for _f in 10:
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(out.path_join("loadtest_zoom%d.png" % int(z)))
	var f := FileAccess.open(out.path_join("loadtest_report.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	print("LOADTEST_DONE ", JSON.stringify(report))
	get_tree().quit()
