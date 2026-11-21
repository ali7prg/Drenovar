extends SceneTree
## Short world-layer movies through the city camera (movie time, not wall time):
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile --write-movie /abs/out.avi --fixed-fps 30 -s qa_forest_world_movie.gd -- --scenario=reveal|overview
##   ffmpeg -i out.avi -c:v libx264 -pix_fmt yuv420p out.mp4
## reveal:   hall III, intro done; the squad walks the entry trail → glade 01 → toward 02. Every 0.5 s
##           the projection grows by the committed path (10 m discs, as fog.mjs), the fog rolls back
##           (~2 s reveal) around the moving sight circle; the camera follows like the city camera.
## overview: hall I–II locked overview (animated border), then the explored map.

const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")
const FPS := 30.0

var game: Node
var stage: Node3D
var world: Node3D


func _initialize() -> void:
	call_deferred("run")


func frames(seconds: float) -> void:
	for i in int(seconds * FPS):
		await process_frame


func look(target: Vector3, zoom: float) -> void:
	stage.target = target
	stage.zoom = zoom
	stage.camera_target = target
	stage.camera_zoom = zoom
	stage.apply_camera_pose()
	stage.refresh_camera_visibility()


func adventure(unlocked: bool, bits: PackedByteArray, revision: int) -> Dictionary:
	return {"campaignId": "forest_rescue_v1", "serverTime": 1794370000000,
		"access": {"unlocked": unlocked, "hallLevel": 3 if unlocked else 2},
		"intro": {"status": "acknowledged"}, "fog": {"visibleBase64": Marshalls.raw_to_base64(bits), "revision": revision},
		"squad": {"node": "lf_horse_origin"}, "horse": {"visible": false}, "boss": {"state": "locked"}}


func path_points(ids: Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	for id in ids:
		out.append_array(world.route_points(id))
	return out


func run() -> void:
	var scenario := "reveal"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--scenario="):
			scenario = arg.trim_prefix("--scenario=")
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.get("scene_loading") or not is_instance_valid(game.get("stage")):
		await process_frame
	stage = game.stage
	world = stage.forest_world
	game.set_process(false)
	game.hud.visible = false
	await frames(0.3)
	game.forest_game.process_mode = Node.PROCESS_MODE_DISABLED
	world.set_reduced_motion(false)
	var town := ForestFog.default_town_bits()
	var corridor: Dictionary = world.atlas.entrance_corridor
	var c := ForestFog.corridor_bits(corridor.from, corridor.to, corridor.radius)
	for i in town.size():
		town[i] = town[i] | c[i]
	if scenario == "overview":
		world.apply_adventure(adventure(false, ForestFog.default_town_bits(), 1))
		world.fog.finish_now()
		look(Vector3(0, 0, 0), 130.0)
		await frames(1.0)
		for i in int(4.0 * FPS):
			look(Vector3(0, 0, 0).lerp(Vector3(-20, 0, -16), i / (4.0 * FPS)), 130.0)
			await process_frame
		var all := PackedByteArray()
		all.resize(392)
		all.fill(255)
		world.apply_adventure(adventure(true, all, 2))
		for i in int(5.0 * FPS):
			look(Vector3(-20, 0, -16).lerp(Vector3(10, 0, 6), i / (5.0 * FPS)), lerpf(130.0, 112.0, i / (5.0 * FPS)))
			await process_frame
		quit(0)
		return
	# reveal: squad along entry → 01 → 02 (≈ 70 m) in 9 s
	world.apply_adventure(adventure(true, town, 1))
	world.fog.finish_now()
	var points := path_points(["lf_trail_horse_origin__junction_corridor", "lf_trail_junction_corridor__junction_stones",
		"lf_trail_junction_stones__junction_grove"])
	var lengths := PackedFloat32Array([0.0])
	for i in range(1, points.size()):
		lengths.append(lengths[i - 1] + Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length())
	var total: float = lengths[-1]
	var bits := town.duplicate()
	var revision := 2
	var duration := 9.0
	var next_commit := 0.0
	look(points[0], 48.0)
	await frames(0.8)
	for f in int(duration * FPS):
		var t := f / FPS
		var travelled := total * clampf(t / duration, 0.0, 1.0)
		var k := 1
		while k < points.size() - 1 and lengths[k] < travelled:
			k += 1
		var w := clampf((travelled - lengths[k - 1]) / maxf(0.001, lengths[k] - lengths[k - 1]), 0.0, 1.0)
		var p := points[k - 1].lerp(points[k], w)
		world.set_sight_points([Vector4(p.x, p.z, 10.0, 1.0)])
		if t >= next_commit:
			# committed movement: the server reveals 10 m around the walked path (≤ 2 m steps)
			for j in k:
				ForestFog.stamp_disc(bits, Vector2(points[j].x, points[j].z), 10.0)
			ForestFog.stamp_disc(bits, Vector2(p.x, p.z), 10.0)
			world.apply_adventure(adventure(true, bits, revision))
			revision += 1
			next_commit += 0.5
		look(Vector3(p.x, 0.0, p.z) + Vector3(-6, 0, -6), 48.0)
		await process_frame
	await frames(2.2)
	quit(0)
