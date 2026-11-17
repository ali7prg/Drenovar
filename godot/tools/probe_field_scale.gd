extends SceneTree
# Build 1021 audit: pictures of one hunt in the real scene at chosen battle times,
# with the field soldiers and creatures at a chosen size, to compare their size with
# the houses, trees and walls around them (before/after). Offline; one PNG per time.
#   cd godot/project
#   xvfb-run -s "-screen 0 1280x720x24" godot --path . --rendering-method gl_compatibility --audio-driver Dummy \
#     -s ../tools/probe_field_scale.gd -- --scene=world --soldier=1.15 --creature=1.0 --times=-6,2,5 --out=/tmp/probe --tag=before
# --scene=world|city   --x/--z encounter place (world default: Velkor I by the village of slot-4)
# --soldier/--creature  sizes (default: the game's own for that map)
# --from=dx,dz          start of the march relative to the creature (straight route)
# --zoom --yaw --frame_dx --frame_dz   camera
const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const CombatPresentation = preload("res://src/combat_presentation.gd")
var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.trim_prefix("--").get_slice("=", 0)] = a.get_slice("=", 1)
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(int(args.get("w", "1280")), int(args.get("h", "720")))
	CombatV010.set_enabled(true)
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	var scene: String = args.get("scene", "world")
	if game.map_name != scene:
		await game.show_scene(scene)
	for child in game.get_children():
		if child is CanvasLayer or child is Control:
			child.visible = false
	var stage = game.stage
	if args.has("soldier") or args.has("creature"):
		stage.set_field_scale(float(args.get("soldier", str(stage.unit_scale))), float(args.get("creature", str(stage.beast_k))))
	stage.engage_sync = true
	var case: Dictionary = {}
	for c in JSON.parse_string(FileAccess.get_file_as_string("res://tests/combat_v010/server_combat_cases.json")).cases:
		if c.name == args.get("case", "mixed_all_types_velkor"):
			case = c
	var state: Dictionary = game.state.duplicate(true)
	# --city=owner: a city like the owner's (16 buildings at level V, the wall) and the
	# server's own route to a creature (tests/march_lanes/owner_city_routes.json).
	var fixture_route: Array = []
	if scene == "city" and args.get("city", "") == "owner":
		var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/march_lanes/owner_city_routes.json"))
		state = fixture.state.duplicate(true)
		game.state = state
		stage.present(state)
		fixture_route = fixture.routes[int(args.get("route_index", "0"))].path
	var holder: Dictionary = state.world if scene == "world" else state
	var enc: Dictionary = holder.encounters[0]
	if scene == "city":
		for e in holder.encounters:
			if int(e.level) == int(case.level): enc = e
	holder.encounters = [enc]
	enc.patrol = []
	if scene == "world":
		enc.position = {"x": float(args.get("x", "-0.35")), "z": float(args.get("z", "-60.13"))}
	elif args.has("x"):
		enc.position = {"x": float(args.get("x")), "z": float(args.get("z"))}
	enc.level = int(args.get("level", str(case.level)))
	if not enc.has("spec"):
		enc.spec = {"id": str(enc.get("species", case.species)), "name": str(enc.get("species", case.species)).capitalize(), "hp": 1400}
	if not fixture_route.is_empty():
		enc.position = {"x": float(fixture_route[-1].x), "z": float(fixture_route[-1].z)}
	var at: Vector3 = stage.point(enc.position)
	var start: Array = str(args.get("from", "0,34" if scene == "world" else "")).split(",", false)
	var path := []
	if not fixture_route.is_empty():
		path = fixture_route.duplicate(true)
	elif start.size() == 2:
		var from := at + Vector3(float(start[0]), 0.0, float(start[1]))
		path = [{"x": from.x, "z": from.z}, {"x": at.x, "z": at.z}]
		if scene == "world" and args.get("route", "server") == "server":
			path = world_path(stage, from, at)
	elif scene == "city" and args.get("route", "home") == "home":
		# From the town's home square: the client takes it out of the main gate (gate_path).
		path = [{"x": 0.0, "z": 16.0}, {"x": at.x, "z": at.z}]
	else:
		var out := Vector3(at.x, 0.0, at.z).normalized()
		path = [{"x": at.x - out.x * 30.0, "z": at.z - out.z * 30.0}, {"x": at.x - out.x * 14.0, "z": at.z - out.z * 14.0}, {"x": at.x, "z": at.z}]
	var arrive := 200000.0
	var walk := float(args.get("walk", "14000"))
	var source := {"id": "army-probe", "owner": game.player_id, "status": "outbound", "target": enc.id, "worldKind": "velkor" if scene == "world" else null,
		"path": path, "units": case.party.duplicate(), "startsAt": arrive - walk, "arrivesAt": arrive, "battleAt": arrive,
		"battleEndsAt": arrive + float(case.result.duration), "battle": {"events": case.result.events.duplicate(true)}, "fallen": [],
		"returnStartsAt": arrive + float(case.result.duration), "returnsAt": arrive + float(case.result.duration) + walk}
	var shown: Dictionary = source.duplicate(true)
	CombatPresentation.stretch(shown, {})
	var ends := float(shown.battleEndsAt)
	var back: Array = path.duplicate(); back.reverse()
	stage.target = at + Vector3(float(args.get("frame_dx", "0")), 0, float(args.get("frame_dz", "4")))
	stage.zoom = float(args.get("zoom", "40" if scene == "world" else "34"))
	stage.world_yaw = float(args.get("yaw", "0"))
	stage.update_camera(0, true)
	# The march lane (march_lanes.gd) is planned while the column waits to set off.
	if args.get("lane", "1") == "1":
		# A tool renders a frame in ~1 s: plan in one go instead of 2 ms slices.
		stage.lanes.slice_override = 1000000
		var waiting: Dictionary = shown.duplicate(true)
		holder.armies = [waiting]
		stage.present_armies(state, arrive - walk - 500.0)
		var cache: Dictionary = stage.army_routes.get("army-probe", {})
		while not cache.get("lane_job", {}).get("done", false):
			await process_frame
		stage.present_armies(state, arrive - walk - 400.0)
		var job: Dictionary = cache.lane_job
		print("PROBE_LANE ", JSON.stringify({"ms": snappedf(float(job.get("usec", 0)) / 1000.0, 0.1), "applied": cache.has("lane"),
			"moved_m": snappedf(float(job.get("lane", {}).get("moved", 0.0)), 0.01), "length_m": snappedf(float(job.get("lane", {}).get("length", 0.0)), 0.1),
			"server_m": snappedf(float(stage.lanes.last.get("reference", 0.0)), 0.1), "kept": stage.lanes.last.get("kept", ""),
			"narrowest": snappedf(Array(cache.get("lane", {}).get("clearance", PackedFloat32Array([0.0]))).min(), 0.01)}))
	# Troop models load in the background in the game; have them all before the clock runs.
	stage.prewarm_troops(case.party.keys())
	for id in case.party:
		while not stage.model_ready(str(game.data.unitModels[id].field)) or not CombatV010.ready_for("troop", id):
			await process_frame
	var out_dir: String = args.get("out", "/tmp/probe")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var times: Array = Array(str(args.get("times", "-5,3,6")).split(",", false)).map(func(t): return float(t))
	var first := arrive + float(times.min()) * 1000.0 - 3000.0
	var now := first
	var shot := 0
	# Walk the clock in 1/30 s steps so the march, the charge and the clips advance as
	# in the game; far from a picture several steps share one rendered frame.
	var steps := 0
	while shot < times.size():
		var army: Dictionary = shown.duplicate(true)
		if now < arrive:
			army.status = "outbound"; enc.status = "alive"
		elif now < ends:
			army.status = "fighting"; enc.status = "fighting"
		else:
			army.status = "returning"; army.returnPath = back
			army.returnUnits = case.result.get("surviving", {}) if not case.result.get("surviving", {}).is_empty() else case.party
			enc.status = "defeated"
		holder.armies = [army]
		if args.get("follow", "0") == "1" and not stage.army_markers.is_empty():
			stage.target = stage.army_markers[0].position - Vector3.UP * 2.6
		stage.update_camera(1.0 / 30.0, false)
		stage.present_armies(state, now)
		stage.present_creatures(state, now, 1.0 / 30.0)
		steps += 1
		var due := arrive + float(times[shot]) * 1000.0
		if due - now > 700.0 and steps % 12 != 0:
			now += 1000.0 / 30.0
			continue
		await process_frame
		if now >= due:
			await process_frame
			var image: Image = root.get_texture().get_image()
			var file := "%s/%s-%s-%+.1f.png" % [out_dir, args.get("tag", "probe"), scene, float(times[shot])]
			image.save_png(file)
			print("PROBE_SHOT ", file)
			shot += 1
		now += 1000.0 / 30.0
	quit()

# The server's world route (world62.mjs worldPath): A* on 5 m cells, water four times
# dearer, the height difference adds to the cost; from, the cells, to.
static func world_path(stage, from: Vector3, to: Vector3) -> Array:
	var step := 5.0
	var x0 := -145.0
	var z0 := -115.0
	var width := 59
	var depth := 47
	var cell := func(p: Vector3) -> int: return clampi(roundi((p.z - z0) / step), 0, depth - 1) * width + clampi(roundi((p.x - x0) / step), 0, width - 1)
	var coord := func(i: int) -> Vector3: return Vector3(x0 + (i % width) * step, 0.0, z0 + floori(float(i) / width) * step)
	var height := func(p: Vector3) -> float: return stage.terrain_y(p)
	var begin: int = cell.call(from)
	var end: int = cell.call(to)
	var open := {begin: true}
	var cost := {begin: 0.0}
	var previous := {}
	while not open.is_empty():
		var best := -1
		var score := INF
		for i in open:
			var f: float = cost[i] + Vector2(coord.call(i).x - to.x, coord.call(i).z - to.z).length()
			if f < score:
				score = f
				best = i
		if best == end:
			break
		open.erase(best)
		var p: Vector3 = coord.call(best)
		var x := best % width
		var z := floori(float(best) / width)
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]:
			if x + d.x < 0 or x + d.x >= width or z + d.y < 0 or z + d.y >= depth:
				continue
			var j: int = (z + d.y) * width + x + d.x
			var q: Vector3 = coord.call(j)
			var y: float = height.call(q)
			var next: float = cost[best] + step * Vector2(d).length() * (4.0 if y < 2.0 else 1.0) + absf(height.call(p) - y) * 0.4
			if next >= float(cost.get(j, INF)):
				continue
			cost[j] = next
			previous[j] = best
			open[j] = true
	var path := [{"x": to.x, "z": to.z}]
	var i := end
	while i != begin and previous.has(i):
		var c: Vector3 = coord.call(i)
		path.append({"x": c.x, "z": c.z})
		i = previous[i]
	path.append({"x": from.x, "z": from.z})
	path.reverse()
	return path

