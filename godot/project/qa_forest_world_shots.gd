extends SceneTree
## In-engine screenshots of the «Лес потерянных» world layer through the game's own city camera
## (ortho, size = zoom, position = target + (75, 83, 75), 38° elevation, no yaw).
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile -s qa_forest_world_shots.gd -- --out=<dir> --prefix=iter08_ [--only=a,b]
## Writes <prefix><view>.png (+ <prefix>shots.json with camera/perf per view); fixtures are synthetic
## adventure projections (no server needed). Compose with src/forest_rescue/world/tools/compose_compare.py.

const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")

var out := "res://../../forest_rescue/qa/ingame/world"
var prefix := "iter_"
var only: PackedStringArray = []
var hud := false
var game: Node
var stage: Node3D
var world: Node3D
var report := {}


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--prefix="):
			prefix = arg.trim_prefix("--prefix=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",")
		elif arg == "--hud":
			hud = true
	call_deferred("run")


func town_bits() -> PackedByteArray:
	return ForestFog.default_town_bits()


func corridor_bits() -> PackedByteArray:
	var corridor: Dictionary = world.atlas.entrance_corridor
	return ForestFog.corridor_bits(corridor.from, corridor.to, corridor.radius)


## Explored = town + entrance corridor + 10 m discs along the given routes (fog.mjs reveal radius),
## optionally only the first `fraction` of the last route (squad still walking).
func explored_bits(route_ids: Array, last_fraction := 1.0) -> PackedByteArray:
	var bits := town_bits()
	for r in route_ids.size():
		var points: PackedVector3Array = world.route_points(route_ids[r])
		var count := points.size()
		if r == route_ids.size() - 1:
			count = int(ceil(points.size() * last_fraction))
		for i in range(0, count, 2):
			ForestFog.stamp_disc(bits, Vector2(points[i].x, points[i].z), 10.0)
	var c := corridor_bits()
	for i in bits.size():
		bits[i] = bits[i] | c[i]
	return bits


func all_bits() -> PackedByteArray:
	var bits := PackedByteArray()
	bits.resize(392)
	bits.fill(255)
	return bits


func adventure(unlocked: bool, bits: PackedByteArray, revision: int, intro := "acknowledged", squad := "lf_horse_origin") -> Dictionary:
	return {"campaignId": "forest_rescue_v1", "schemaVersion": 1, "serverTime": 1794370000000,
		"access": {"unlocked": unlocked, "hallLevel": 3 if unlocked else 2, "requiredHall": 3,
			"reason": null if unlocked else "FOREST_LOCKED_HALL_LEVEL"},
		"intro": {"status": intro, "deferred": false, "offer": intro != "acknowledged"},
		"fog": {"explorationLocked": not unlocked, "columns": 56, "rows": 56, "cellSize": 4,
			"origin": {"x": -112, "z": -112}, "visibleBase64": Marshalls.raw_to_base64(bits), "revision": revision},
		"pois": [], "horse": {"visible": unlocked, "node": "lf_horse_origin"},
		"squad": {"units": {}, "members": 3, "node": squad, "move": null, "busy": null},
		"boss": {"state": "locked"}}


func view(target: Vector3, zoom: float) -> void:
	stage.target = target
	stage.zoom = zoom
	stage.camera_target = target
	stage.camera_zoom = zoom
	stage.apply_camera_pose()
	stage.refresh_camera_visibility(true)


func settle(frames := 4) -> void:
	for i in frames:
		await process_frame


func wants(name: String) -> bool:
	return only.is_empty() or only.has(name)


func shot(name: String, target: Vector3, zoom: float) -> void:
	if not wants(name):
		return
	view(target, zoom)
	await settle(4)
	var image := root.get_texture().get_image()
	var path := out.path_join(prefix + name + ".png")
	image.save_png(path)
	var perf := _short_perf()
	report[name] = {"target": [target.x, target.z], "zoom": zoom, "px_per_m": float(root.size.y) / zoom, "perf": perf}
	print("SHOT ", path, " ", JSON.stringify(perf))


func _short_perf() -> Dictionary:
	var p: Dictionary = world.perf_snapshot()
	return {"full": p.full_chunks, "proxy": p.proxy_chunks, "fogOnly": p.fog_only_chunks, "inst": p.instances,
		"tris_est": p.tris_est, "landmark_tris": p.get("landmark_tris", 0),
		"draws": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"prims": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}


func _horse_stand_in() -> Node3D:
	var path := "res://assets/forest_rescue/horse/lf_horse_origin.glb"
	if not ResourceLoader.exists(path):
		return null
	var node: Node3D = (load(path) as PackedScene).instantiate()
	var origin: Vector3 = world.poi_position("lf_horse_origin")
	node.position = origin
	node.rotation.y = atan2(-12.0 - origin.x, -60.0 - origin.z)
	world.actors_root().add_child(node)
	for player: AnimationPlayer in node.find_children("*", "AnimationPlayer", true, false):
		for clip in player.get_animation_list():
			if String(clip).to_lower().contains("idle"):
				player.play(clip)
				break
	return node


func apply(adv: Dictionary, finish := true) -> void:
	world.apply_adventure(adv)
	if finish:
		world.fog.finish_now()
	await settle(2)


func run() -> void:
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var waited := 0
	while game.get("scene_loading") or not is_instance_valid(game.get("stage")):
		await process_frame
		waited += 1
		if waited > 3000:
			push_error("stage never became ready")
			quit(2)
			return
	stage = game.stage
	world = stage.get("forest_world")
	if world == null:
		push_error("forest_world missing (flag off?)")
		quit(3)
		return
	game.set_process(false)
	# The gameplay layer syncs the world from its own (offline) state when it first sees the
	# stage; let it do that, then freeze it so the synthetic fixtures below are not overridden.
	await settle(6)
	# Warm-up: let pipelines/shaders compile before the first capture (first frames can be unlit).
	view(Vector3(5, 0, -4), 68.0)
	await settle(30)
	var forest_game: Node = game.get("forest_game")
	if forest_game != null:
		forest_game.process_mode = Node.PROCESS_MODE_DISABLED
	if not hud:
		game.hud.visible = false
	world.set_reduced_motion(false)
	print("KIT ", JSON.stringify(world.kit_status()))
	print("LAYOUT ", JSON.stringify(world.layout_info()))
	# 1. Locked (hall 1–II): town clear, entire outer forest under the animated boundary.
	await apply(adventure(false, town_bits(), 0, "pending"))
	await shot("locked_town_z68", Vector3(5, 0, -4), 68.0)
	await shot("locked_town_z40", Vector3(0, 0, -30), 40.0)
	await shot("locked_overview_z130", Vector3(0, 0, 0), 130.0)
	# 2. Hall III reached: entrance corridor held until the intro reveal, then the 1.2 s reveal.
	await apply(adventure(true, explored_bits([]), 1, "playing"))
	if wants("entrance_reveal_0") or wants("entrance_reveal_2") or wants("entrance_reveal_4"):
		await shot("entrance_reveal_0", Vector3(-8, 0, -50), 46.0)
		world.play_entrance_reveal(1200)
		world.fog.set_process(false)
		for step in [1, 2, 3, 4]:
			world.fog.reveal_t = step / 4.0
			world.fog._push_reveal()
			await shot("entrance_reveal_%d" % step, Vector3(-8, 0, -50), 46.0)
		world.fog.reveal_t = 1.0
		world.fog.revealing = true
		world.fog._process(0.0)
	else:
		world.play_entrance_reveal(0)
		world.fog.finish_now()
	# art/18 panels 2–3: the corridor (-8,-55)→(-12,-60) framed at zoom 46 and 30, a stand-in
	# horse (the delivered horse GLB, QA only) under actors_root so the canopy fade is exercised.
	var horse := _horse_stand_in()
	await shot("unlocked_entrance_z68", Vector3(-4, 0, -44), 68.0)
	await shot("entrance_corridor_z46", Vector3(-12, 0, -58), 46.0)
	await shot("unlocked_horse_z30", Vector3(-11, 0, -58), 30.0)
	if horse != null:
		horse.queue_free()
	# 3. Partly explored: act 1 done, the squad halfway along route 03→04 (art/07 panels).
	await apply(adventure(true, explored_bits(["lf_route_entry", "lf_route_01_02", "lf_route_02_03", "lf_route_03_04"], 0.5), 2, "acknowledged", "lf_site_03"))
	await shot("partial_squad_z40", Vector3(-72, 0, -52), 40.0)
	await shot("partial_path_z40", Vector3(-38, 0, -66), 40.0)
	await shot("partial_edge_z68", Vector3(-55, 0, -58), 68.0)
	await shot("partial_overview_z130", Vector3(-10, 0, -10), 130.0)
	# 4. Fully explored: composition vs. the masterplan, biomes, bridge, arena.
	await apply(adventure(true, all_bits(), 3, "acknowledged", "lf_site_12"))
	world.fog.set_dim(0.0)
	await shot("full_overview_z120", Vector3(0, 0, 0), 120.0)
	await shot("full_overview_z140", Vector3(0, 0, 0), 140.0)
	for spec in [["grove", Vector3(-88, 0, 8)], ["spruce", Vector3(38, 0, 84)], ["river_bridge", Vector3(88, 0, 16)],
			["quarry", Vector3(-31, 0, 92)], ["arena", Vector3(75, 0, -84)], ["town", Vector3(5, 0, -4)],
			["top_birch", Vector3(-30, 0, -72)], ["east", Vector3(98, 0, -30)]]:
		await shot("full_%s_z68" % spec[0], spec[1], 68.0)
		await shot("full_%s_z40" % spec[0], spec[1], 40.0)
	var file := FileAccess.open(out.path_join(prefix + "shots.json"), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "  "))
	print("SHOTS_DONE")
	quit()
