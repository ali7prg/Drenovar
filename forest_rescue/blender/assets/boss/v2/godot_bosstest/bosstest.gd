extends Node3D
## Ancient Maw v2 in the game pipeline: Rig (actor_rig.gd) blocking load, LOD discovery, clip lengths vs meta,
## marker dispatch for every clip (13 rigs played in parallel), painted look (meta paintedLightMix);
## game camera shots (ortho, size = zoom, target + (75, 83, 75)) of the boss in the arena with the squad at
## zoom 40 (LOD0) and 68 (LOD1), attack key frames, and a size line-up boss / horse / human.
const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const A := "res://assets/forest_rescue/"
const BOSS := A + "boss/lf_boss_ancient_maw.glb"
const SQUAD := [A + "humans/lf_squad_captain.glb", A + "humans/lf_squad_shield_guard.glb", A + "humans/lf_squad_scout.glb"]
const HORSE := A + "horse/lf_horse_origin.glb"
var out := "/tmp"
var report := {}
var marks := {}
var cam: Camera3D
var boss: Node3D
var squad: Array = []
var arena0: Node3D
var arena1: Node3D
var clip_rigs := {}

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#5d6b52")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d8e5ee")
	env.ambient_light_energy = 0.58
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -32, 0)
	sun.light_color = Color("#ffe4b8")
	sun.light_energy = 1.85
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 220.0
	add_child(sun)
	ForestKit.light_dir = sun.global_transform.basis.z.normalized()
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 0.5
	cam.far = 900
	add_child(cam)
	# arena (assembled LOD0 and, when delivered, the light LOD1 assembly), painted like forest_landmarks.gd
	arena0 = _arena(A + "arena/lf_boss_arena_assembled.glb")
	arena1 = _arena(A + "arena/lf_boss_arena_assembled_lod1.glb")
	# boss at the arena centre facing the entrance (+Z), squad on the approach point (enemy + (0, 0, 9..10))
	boss = Rig.new()
	boss.setup("boss", BOSS)
	add_child(boss)
	boss.poll_load(true)
	boss.marker.connect(_on_marker)
	var formation := [Vector3(0, 0, 0), Vector3(-0.85, 0, -1.25), Vector3(0.85, 0, -1.25)]
	for i in 3:
		var r := Rig.new()
		r.setup("squad%d" % i, SQUAD[i])
		add_child(r)
		r.poll_load(true)
		r.position = Vector3(0, 0, 10.0) + Basis(Vector3.UP, PI) * formation[i]
		r.rotation.y = PI
		r.play(["lf_soldier_guard", "lf_soldier_idle", "Idle"], 0.0)
		squad.append(r)
	var meta: Dictionary = boss.meta
	var r := {"ready": boss.is_ready(), "lods": [boss.lods[0].size(), boss.lods[1].size(), boss.lods[2].size()],
		"clips_ok": 0, "clips_missing": [], "length_mismatch": [], "painted": false, "tris_by_lod": [], "clip_lengths": {}}
	for clip_id in meta.get("clips", {}):
		if not boss.has_clip([clip_id]):
			r.clips_missing.append(clip_id)
			continue
		var want := float(meta.clips[clip_id].get("seconds", 0.0))
		r.clip_lengths[clip_id] = boss.clip_length([clip_id])
		if absf(boss.clip_length([clip_id]) - want) > 0.02:
			r.length_mismatch.append([clip_id, boss.clip_length([clip_id]), want])
		else:
			r.clips_ok += 1
	for mi: MeshInstance3D in boss.model.find_children("*", "MeshInstance3D", true, false):
		if mi.get_surface_override_material(0) is ShaderMaterial:
			r.painted = true
	for lvl in 3:
		var t := 0
		for mi in boss.lods[lvl]:
			for s in mi.mesh.get_surface_count():
				t += mi.mesh.surface_get_array_index_len(s) / 3
		r.tris_by_lod.append(t)
	var skel: Array = boss.model.find_children("*", "Skeleton3D", true, false)
	r["skeleton_bones"] = (skel[0] as Skeleton3D).get_bone_count() if not skel.is_empty() else 0
	report["boss"] = r
	# one rig per clip, far outside the view, so every marker is dispatched in one pass
	var k := 0
	for clip_id in meta.get("clips", {}):
		var cr := Rig.new()
		cr.setup("clip_%s" % clip_id, BOSS)
		add_child(cr)
		cr.poll_load(true)
		cr.position = Vector3(400 + 30 * k, 0, 400)
		cr.marker.connect(_on_marker)
		cr.play([clip_id], 0.0, true)
		clip_rigs[clip_id] = cr
		k += 1
	_run.call_deferred()

func _arena(path: String) -> Node3D:
	if not ResourceLoader.exists(path):
		return null
	var root := Node3D.new()
	root.rotation.y = deg_to_rad(5.4)
	add_child(root)
	var node: Node3D = (load(path) as PackedScene).instantiate()
	root.add_child(node)
	ForestKit.paint_scene(node, 0.35)
	for n in node.find_children("state_*", "Node3D", true, false):
		(n as Node3D).visible = String(n.name).trim_prefix("state_").begins_with("active")
	return root

func _on_marker(rig: Node3D, clip_id: String, marker_name: String) -> void:
	var key := clip_id + ":" + marker_name
	marks[key] = int(marks.get(key, 0)) + 1

func _shot(name: String, zoom: float, target: Vector3) -> void:
	cam.size = zoom
	cam.position = target + Vector3(75, 83, 75)
	cam.look_at(target, Vector3.UP)
	for _f in 6:
		await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(out.path_join(name + ".png"))

func _set_lod(level: int) -> void:
	boss.set_lod(level)
	for s in squad:
		s.set_lod(level)
	if arena0 != null:
		arena0.visible = level == 0 or arena1 == null
	if arena1 != null:
		arena1.visible = level != 0

func _run() -> void:
	for _f in 20:
		await get_tree().process_frame
	var target := Vector3(0, 1.0, 4.0)
	boss.play(["lf_boss_idle"], 0.0, true)
	for z in [40.0, 68.0]:
		_set_lod(0 if z < 42.0 else 1)
		await _shot("game_zoom%d_idle" % int(z), z, target)
	# attack key frames at the game zoom 40 (telegraph and active)
	_set_lod(0)
	for pair in [["lf_boss_jaw_arc", 2.0], ["lf_boss_jaw_arc", 2.55], ["lf_boss_tail_sweep", 2.8], ["lf_boss_tail_sweep", 3.45],
			["lf_boss_lane_charge", 2.2], ["lf_boss_lane_charge", 3.5], ["lf_boss_stomp_waves", 2.9], ["lf_boss_stomp_waves", 3.25],
			["lf_boss_phase_roar", 1.2], ["lf_boss_death", 5.19]]:
		boss.play([pair[0]], 0.0, true)
		boss.player.seek(float(pair[1]), true)
		boss.player.pause()
		await _shot("game_zoom40_%s_%.2f" % [pair[0].trim_prefix("lf_boss_"), float(pair[1])], 40.0, target)
	# heads5 in the game look (painted shader), LOD0 and LOD1: front, 3/4 L, 3/4 R, profile L, profile R
	boss.play(["lf_boss_idle"], 0.0, true)
	boss.player.seek(0.0, true)
	boss.player.pause()
	for s in squad:
		s.visible = false
	if arena0 != null:
		arena0.visible = false
	if arena1 != null:
		arena1.visible = false
	var head := Vector3(0, 3.02, 3.82)
	var dirs := {"front": Vector3(0, 0.18, 1), "34L": Vector3(1, 0.18, 1), "34R": Vector3(-1, 0.18, 1), "profL": Vector3(1, 0.18, 0), "profR": Vector3(-1, 0.18, 0)}
	cam.size = 2.6
	for lvl in [0, 1]:
		boss.set_lod(lvl)
		for key in dirs:
			cam.position = head + (dirs[key] as Vector3).normalized() * 12.0
			cam.look_at(head, Vector3.UP)
			for _f in 4:
				await get_tree().process_frame
			get_viewport().get_texture().get_image().save_png(out.path_join("heads5_lod%d_%s.png" % [lvl, key]))
	boss.set_lod(0)
	for s in squad:
		s.visible = true
	# size line-up: boss, horse, captain on a plain ground
	if arena0 != null:
		arena0.visible = false
	if arena1 != null:
		arena1.visible = false
	boss.play(["lf_boss_idle"], 0.0, true)
	boss.position = Vector3(0, 0, 0)
	boss.rotation.y = -PI / 2
	var horse := Rig.new()
	horse.setup("horse", HORSE)
	add_child(horse)
	horse.poll_load(true)
	horse.position = Vector3(-1.0, 0, 4.0)
	horse.rotation.y = -PI / 2
	horse.play(["lf_horse_idle", "Idle"], 0.0)
	for i in 3:
		squad[i].position = Vector3(2.2 + 1.0 * i, 0, 4.0)
		squad[i].rotation.y = PI / 4
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.42, 0.40, 0.30)
	ground.material_override = gm
	add_child(ground)
	await _shot("size_lineup_game_zoom20", 20.0, Vector3(0, 1.5, 2.0))
	# side view of the line-up (ortho, from +X)
	cam.size = 14.0
	cam.position = Vector3(0, 2.0, 40.0)
	cam.look_at(Vector3(0, 2.0, 0), Vector3.UP)
	for _f in 6:
		await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(out.path_join("size_lineup_side.png"))
	# wait until every clip rig has run past its end so all markers fired
	for _f in 240:
		await get_tree().process_frame
	report["markers"] = marks
	var f := FileAccess.open(out.path_join("bosstest_report.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	print("BOSSTEST_DONE ", JSON.stringify(report))
	get_tree().quit()
