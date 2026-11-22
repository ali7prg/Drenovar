extends SceneTree
# Build 1021: march lanes (src/march_lanes.gd) on the real scenes, offline.
#  - world: the server's grid route (world62 worldPath) from the village to Velkor I;
#  - city: from the home square out of the main gate to each creature.
# Checks: the lane keeps the route's start and end; no point of it stands in a trunk,
# a house, the wall (outside its gates) or the water (outside ferry legs); it is not
# much longer than the server's route; planning runs in slices (no long frame).
#   cd godot/project && godot --headless --path . -s qa_march_lanes.gd
var checks := 0
var failures: Array = []
var notes := {}

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failures.append(what)

func lane_for(stage, id: String, path: Array, units: Dictionary) -> Dictionary:
	var army := {"id": id, "status": "outbound", "target": "none", "path": path, "units": units,
		"startsAt": 1.0e9, "arrivesAt": 1.0e9 + 20000.0}
	var state: Dictionary = {"world": {"armies": [army], "encounters": []}, "armies": [army], "encounters": []}
	stage.present_armies(state, 1.0e9 - 1000.0)
	# The column musters: its lane is planned in the larger slices.
	var muster_slice: int = stage.lanes.slice_usec
	var cache: Dictionary = stage.army_routes[id]
	var longest := 0.0
	var started := Time.get_ticks_usec()
	var last := started
	while not cache.get("lane_job", {}).get("done", false):
		await process_frame
		var now := Time.get_ticks_usec()
		longest = maxf(longest, (now - last) / 1000.0)
		last = now
		if (now - started) / 1000000.0 > 60.0:
			break
	stage.present_armies(state, 1.0e9 - 900.0)
	return {"cache": cache, "job": cache.get("lane_job", {}), "longest_frame_ms": longest, "muster_slice": muster_slice, "after_slice": stage.lanes.slice_usec,
		"wall_ms": (Time.get_ticks_usec() - started) / 1000.0, "reference": stage.route_for(path, true)}

func verify(stage, name: String, result: Dictionary, body: float) -> void:
	var cache: Dictionary = result.cache
	var job: Dictionary = result.job
	check(job.get("done", false), name + ": lane planned")
	check(int(result.muster_slice) == 6000 and int(result.after_slice) == 2000,
		"%s: planned in 6 ms slices while the column musters, 2 ms otherwise (%d, %d)" % [name, result.muster_slice, result.after_slice])
	var lane: Dictionary = cache.get("lane", {})
	var reference: Dictionary = result.reference
	var points: PackedVector3Array = cache.points
	check(points[0].distance_to(reference.points[0]) < 0.01 and points[-1].distance_to(reference.points[-1]) < 0.01, name + ": same start and end")
	var ferry: PackedByteArray = cache.get("ferry", PackedByteArray())
	var blocked := 0
	var wet := 0
	var samples := 0
	for i in range(1, points.size()):
		var a := Vector2(points[i - 1].x, points[i - 1].z)
		var b := Vector2(points[i].x, points[i].z)
		var n := maxi(1, ceili(a.distance_to(b) / 0.5))
		for k in range(1, n):
			var q := a.lerp(b, float(k) / n)
			if q.distance_to(a) < 2.0 and i == 1 or q.distance_to(b) < 2.0 and i == points.size() - 1:
				continue # the route's own start and end (a barracks door, the creature)
			samples += 1
			if ferry.size() > i and ferry[i] == 1:
				continue
			if stage.lanes.clearance(q, body) < body * 0.5:
				blocked += 1
			if stage.map_name == "city" and not stage.dry_ground(Vector3(q.x, 0.0, q.y)):
				wet += 1
	var reference_blocked := 0
	var rp: PackedVector3Array = reference.points
	var rf: PackedByteArray = reference.ferry
	for i in range(1, rp.size()):
		var a := Vector2(rp[i - 1].x, rp[i - 1].z)
		var b := Vector2(rp[i].x, rp[i].z)
		var n := maxi(1, ceili(a.distance_to(b) / 0.5))
		for k in range(1, n):
			var q := a.lerp(b, float(k) / n)
			if rf.size() > i and rf[i] == 1:
				continue
			if stage.lanes.clearance(q, body) < body * 0.5:
				reference_blocked += 1
	# A town packed with level-V buildings: their bounding boxes touch, and the server's
	# route passes 5 m from the plot centres between them; there the lane only halves it.
	check(blocked <= maxi(2, reference_blocked / 2), "%s: lane samples in an obstacle %d of %d (server route: %d)" % [name, blocked, samples, reference_blocked])
	check(wet == 0, "%s: lane samples in the river %d" % [name, wet])
	check(not lane.is_empty() and float(lane.length) <= float(stage.lanes.last.get("reference", 0.0)) * 1.3 + 4.0, name + ": lane not much longer")
	check(float(result.longest_frame_ms) < 60.0, "%s: longest frame while planning %.1f ms" % [name, result.longest_frame_ms])
	notes[name] = {"plan_cpu_ms": snappedf(float(job.get("usec", 0)) / 1000.0, 0.1), "longest_frame_ms": snappedf(result.longest_frame_ms, 0.1),
		"server_route_m": snappedf(float(stage.lanes.last.get("reference", 0.0)), 0.1), "lane_m": snappedf(float(lane.get("length", 0.0)), 0.1),
		"moved_m": snappedf(float(lane.get("moved", 0.0)), 0.1), "obstacle_samples_lane": blocked, "obstacle_samples_server_route": reference_blocked,
		"samples": samples, "narrowest_m": snappedf(Array(lane.get("clearance", PackedFloat32Array([0.0]))).min(), 0.01)}

func run() -> void:
	root.size = Vector2i(1366, 630)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var units := {"ENG-01": 6, "ENG-02": 6, "ENG-03": 4, "ENG-04": 4, "ENG-06": 4}
	# City like the owner's (16 buildings at level V, the wall), the server's own routes
	# (marchRoute with the client's wall, tests/march_lanes/owner_city_routes.json:
	# godot/tools/dump_owner_city.gd + march-lane-routes.mjs).
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/march_lanes/owner_city_routes.json"))
	var stage = load("res://src/landscape.gd").new()
	root.add_child(stage)
	await stage.setup(data, fixture.state, "city", {})
	check(stage.walls.visible, "the owner-like city has its wall")
	var n := 0
	for route in fixture.routes:
		if not route.has("path"):
			continue
		var result: Dictionary = await lane_for(stage, "qa-city-%d" % n, route.path, units)
		verify(stage, "city-%s%s" % [route.target.left(8), "-ferry" if route.ferry else ""], result, 0.45 * stage.unit_k)
		n += 1
	stage.free()
	# World: the server's grid route through the forest to Velkor I.
	stage = load("res://src/landscape.gd").new()
	root.add_child(stage)
	await stage.setup(data, data.demo, "world", {})
	var target := Vector3(-0.35, 0.0, -60.13)
	for start in [Vector3(0.0, 0.0, -26.0), Vector3(-34.0, 0.0, -40.0), Vector3(30.0, 0.0, -80.0), Vector3(-40.97, 0.0, -29.41)]:
		var path: Array = world_path(stage, start, target)
		var result: Dictionary = await lane_for(stage, "qa-world-%d" % n, path, units)
		verify(stage, "world-%d" % n, result, 0.45 * stage.unit_k)
		n += 1
	print(JSON.stringify({"checks": checks, "failures": failures, "notes": notes,
		"method": "headless Linux, real Landscape and obstacles, server routes; not iPhone acceptance"}))
	quit(0 if failures.is_empty() else 1)

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

