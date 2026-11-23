extends SceneTree

# Build 1024: a settlement of the earlier model (legacy plots plot-N) on the V6 server.
# The V6 server builds on its own plots (v1-N); before 1024 the city looked them up only in
# the legacy table, so a new building, its scaffolding and its builders never appeared and
# the construction strip still said the type was built. Offline, the demo city reshaped:
#  - an older building on plot-14 and a V6 building on v1-0 (0.1 m away): the V6 one is drawn,
#    at a clear spot (never inside the older one);
#  - a V6 building on a clear plot (v1-24) stands at its own spot;
#  - a construction order on a V6 plot has its work site (scaffolding, builders);
#  - the free V6 plots offered for building are all clear of every building;
#  - a kingdom settlement is unchanged (no remapped spots).

var checks := 0
var failures := 0
var game
var stage

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if condition:
		print("ok  ", description)
	else:
		failures += 1
		push_error(description)
		print("FAIL ", description)

func frames(count: int) -> void:
	for i in count:
		await process_frame

func model_near(at: Vector3, radius: float) -> int:
	var count := 0
	for child in stage.buildings.get_children():
		if child is Node3D and Vector2(child.position.x - at.x, child.position.z - at.z).length() < radius:
			count += 1
	return count

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.player_id = "qa-legacy-v6"
	var settle := Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < settle:
		await process_frame
	stage = game.stage
	var kingdom_state: Dictionary = game.state.duplicate(true)

	# --- kingdom settlement: no remap
	await stage.present_city(kingdom_state)
	await frames(2)
	check(stage.v6_spots.is_empty(), "Kingdom settlement: V6 plots are the city's own table (no remap)")

	# --- legacy settlement
	var state: Dictionary = game.state.duplicate(true)
	var city: Dictionary = state.city
	var legacy_ids: Array = game.data.legacyPlots.map(func(p): return str(p.id))
	var used := {}
	var older: Array = []
	var i := 14
	for b: Dictionary in city.buildings:
		# Older buildings on the legacy grid, around the centre (plot-14 first).
		while used.has(i):
			i += 1
		b.plotId = "plot-%d" % i
		used[i] = true
		older.append(b.plotId)
		i = [7, 8, 9, 13, 15, 19, 20, 21, 2, 3, 26, 27][older.size() - 1] if older.size() <= 12 else i + 1
	city.erase("kingdom")
	city["legacyUpgrades"] = {"order": null, "order2": null}
	# The lost buildings: V6 ids on V6 plots, as the server's projection sends them.
	city.buildings.append({"id": "b-lost-1", "type": "ECO-03", "plotId": "v1-0", "level": 1})
	city.buildings.append({"id": "b-lost-2", "type": "SUP-01", "plotId": "v1-24", "level": 1})
	var now := float(state.get("serverTime", Time.get_unix_time_from_system() * 1000.0))
	city.legacyUpgrades.order = {"kind": "build", "buildingId": "b-new-3", "type": "MIL-04", "conceptType": "B14",
		"plotId": "v1-2", "level": 1, "startedAt": now - 5000.0, "endsAt": now + 600000.0, "requestId": "qa-req"}
	await stage.present_city(state)
	await frames(3)
	check(not stage.v6_spots.is_empty(), "Legacy settlement: V6 plots get spots")
	var plot14: Vector3 = stage.work_sites.get("plot-14", Vector3.INF)
	var lost1: Vector3 = stage.work_sites.get("v1-0", Vector3.INF)
	var lost2: Vector3 = stage.work_sites.get("v1-24", Vector3.INF)
	var order_at: Vector3 = stage.work_sites.get("v1-2", Vector3.INF)
	check(lost1 != Vector3.INF, "V6 building on v1-0 has a place in the city")
	check(lost2 != Vector3.INF, "V6 building on v1-24 has a place in the city")
	check(order_at != Vector3.INF, "Construction order on v1-2 has a work site (scaffolding and builders)")
	if lost1 != Vector3.INF and plot14 != Vector3.INF:
		check(Vector2(lost1.x - plot14.x, lost1.z - plot14.z).length() >= 8.0,
			"v1-0 (0.1 m from the older building on plot-14) is drawn clear of it: %.1f m" % Vector2(lost1.x - plot14.x, lost1.z - plot14.z).length())
	var own24 := Vector2.ZERO
	for p in game.data.plots:
		if p.id == "v1-24":
			own24 = Vector2(float(p.x), float(p.z))
	check(lost2 != Vector3.INF and Vector2(lost2.x, lost2.z).distance_to(own24) < 0.01, "v1-24 (clear) stands at its own spot")
	if lost1 != Vector3.INF:
		check(model_near(lost1, 1.0) >= 1, "A building model stands at the v1-0 building's spot")
	if lost2 != Vector3.INF:
		check(model_near(lost2, 1.0) >= 1, "A building model stands at the v1-24 building's spot")
	var markers: Array = stage.place_markers.filter(func(m): return str(m.get("id", "")) in ["b-lost-1", "b-lost-2"])
	check(markers.size() == 2, "Both V6 buildings have their name plates / tap markers")
	# Every building spot vs every other: none inside another.
	var spots: Array = []
	for b: Dictionary in city.buildings:
		if stage.work_sites.has(b.plotId):
			spots.append([b.id, stage.work_sites[b.plotId]])
	var worst := INF
	for a in spots.size():
		for b in range(a + 1, spots.size()):
			worst = minf(worst, Vector2(spots[a][1].x - spots[b][1].x, spots[a][1].z - spots[b][1].z).length())
	check(worst >= 8.0, "No two buildings share a spot (closest pair %.1f m)" % worst)
	# Offered plots for a new building: clear of every building and of the order.
	var blocked := 0
	var offered := 0
	for id: String in stage.v6_spots:
		var spot: Vector3 = stage.v6_spots[id]
		var taken: bool = city.buildings.any(func(b): return b.plotId == id) or id == "v1-2"
		if spot == Vector3.INF or taken:
			continue
		offered += 1
		for s in spots + [["order", order_at]]:
			if Vector2(spot.x - s[1].x, spot.z - s[1].z).length() < 8.0:
				blocked += 1
	check(offered > 0, "Free V6 plots are offered (%d)" % offered)
	check(blocked == 0, "No offered V6 plot lands on a building or a work site")
	# The order becomes the building: same spot (the scaffolding's place).
	city.legacyUpgrades.order = null
	city.buildings.append({"id": "b-new-3", "type": "MIL-04", "plotId": "v1-2", "level": 1})
	await stage.present_city(state)
	await frames(2)
	var built: Vector3 = stage.work_sites.get("v1-2", Vector3.INF)
	check(built != Vector3.INF and built.distance_to(order_at) < 0.01, "The finished building stands where its scaffolding stood")
	check(stage.work_sites.get("v1-0", Vector3.INF).distance_to(lost1) < 0.01, "Earlier V6 buildings keep their spots after a new build")
	check(model_near(built, 1.0) >= 1, "The finished building is drawn")
	print("QA_LEGACY_V6_PLOTS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
