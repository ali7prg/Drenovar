extends SceneTree
## In-engine screenshots of the «Лес потерянных» world layer through the game's own city camera.
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile -s qa_forest_world_shots.gd -- --out=<dir> --prefix=iter01_ [--only=a,b]
## Writes <prefix><view>.png; fixtures are synthetic adventure projections (no server needed).

const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")

var out := "res://../../forest_rescue/qa/ingame/world"
var prefix := "iter_"
var only: PackedStringArray = []
var hud := false
var game: Node
var stage: Node3D
var world: Node3D


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


func explored_bits(route_ids: Array, extra_discs: Array = []) -> PackedByteArray:
	var bits := town_bits()
	for id in route_ids:
		var points: PackedVector3Array = world.route_points(id)
		for i in range(0, points.size(), 4):
			ForestFog.stamp_disc(bits, Vector2(points[i].x, points[i].z), 10.0)
	for disc in extra_discs:
		ForestFog.stamp_disc(bits, disc[0], disc[1])
	var corridor: Dictionary = world.atlas.entrance_corridor
	var c := ForestFog.corridor_bits(corridor.from, corridor.to, corridor.radius)
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
	stage.update_camera(0.0, true)


func settle(frames := 4) -> void:
	for i in frames:
		await process_frame


func shot(name: String) -> void:
	if not only.is_empty() and not only.has(name):
		return
	await settle(3)
	var image := root.get_texture().get_image()
	var path := out.path_join(prefix + name + ".png")
	image.save_png(path)
	print("SHOT ", path, " ", JSON.stringify(_short_perf()))


func _short_perf() -> Dictionary:
	var p: Dictionary = world.perf_snapshot()
	return {"full": p.full_chunks, "proxy": p.proxy_chunks, "fogOnly": p.fog_only_chunks, "inst": p.instances,
		"tris_est": p.tris_est, "draws": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"prims": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}


func wants(name: String) -> bool:
	return only.is_empty() or only.has(name)


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
	if not hud:
		game.hud.visible = false
	world.set_reduced_motion(false)
	print("KIT ", JSON.stringify(world.kit_status()))
	# 1. Locked (hall 2): town clear, entire outer forest under the animated boundary.
	world.apply_adventure(adventure(false, town_bits(), 0, "pending"))
	world.fog.finish_now()
	if wants("locked_default"):
		view(Vector3(5, 0, -4), 70.0)
		await shot("locked_default")
	if wants("locked_overview"):
		view(Vector3(0, 0, 0), 120.0)
		await shot("locked_overview")
	# 2. Hall III reached: entrance corridor held until the intro reveal, then 1.2 s reveal.
	var unlocked_bits := explored_bits([])
	world.apply_adventure(adventure(true, unlocked_bits, 1, "playing"))
	world.fog.finish_now()
	view(Vector3(-8, 0, -50), 46.0)
	if wants("entrance_reveal_0"):
		await shot("entrance_reveal_0")
	world.play_entrance_reveal(1200)
	world.fog.set_process(false)
	for step in [1, 2, 3, 4]:
		world.fog.reveal_t = step / 4.0
		world.fog._push_reveal()
		if wants("entrance_reveal_%d" % step):
			await shot("entrance_reveal_%d" % step)
	world.fog.reveal_t = 1.0
	world.fog.revealing = true
	world.fog._process(0.0)
	if wants("unlocked_entrance"):
		view(Vector3(-4, 0, -40), 70.0)
		await shot("unlocked_entrance")
	# 3. Partly explored act 1 (entry → 01 → 02 → 03), explored-but-not-current dim veil.
	var act1 := explored_bits(["lf_route_entry", "lf_route_01_02", "lf_route_02_03"])
	world.apply_adventure(adventure(true, act1, 2, "acknowledged", "lf_site_02"))
	world.fog.finish_now()
	if wants("explored_act1"):
		view(Vector3(-40, 0, -62), 60.0)
		await shot("explored_act1")
	if wants("explored_path_close"):
		view(Vector3(-22, 0, -62), 34.0)
		await shot("explored_path_close")
	# 4. Fully explored (composition vs. the masterplan), biomes, bridge, arena.
	world.apply_adventure(adventure(true, all_bits(), 3, "acknowledged", "lf_site_12"))
	world.fog.finish_now()
	world.fog.set_dim(0.0)
	if wants("overview_explored"):
		view(Vector3(0, 0, 0), 120.0)
		await shot("overview_explored")
	for spec in [["biome_1_birch", Vector3(-20, 0, -80)], ["biome_2_limestone", Vector3(-75, 0, -78)],
			["biome_3_dark_conifer", Vector3(-92, 0, -18)], ["biome_4_charcoal", Vector3(-80, 0, 45)],
			["biome_5_alder_meadow", Vector3(-25, 0, 88)], ["biome_6_fern_ridge", Vector3(60, 0, 78)],
			["biome_7_river_terraces", Vector3(98, 0, 0)], ["biome_8_ancient_grove", Vector3(88, 0, -66)]]:
		if wants(spec[0]):
			view(spec[1], 48.0)
			await shot(spec[0])
	if wants("bridge"):
		view(Vector3(90.48, 0, 20), 36.0)
		await shot("bridge")
	if wants("arena"):
		view(Vector3(75, 0, -86), 44.0)
		await shot("arena")
	if wants("inner_town"):
		view(Vector3(5, 0, -4), 46.0)
		await shot("inner_town")
	print("SHOTS_DONE")
	quit()
