extends SceneTree
## Build 1024, stage 5: frame times of the representative scenes in the real game (main.tscn) against a
## LOCAL copy of the live V6 Worker (the harness of qa_build_e2e.gd / qa_net_1024.gd, adventure on; never
## production or staging), with the game's own frame loop and polling running:
##   godot --headless --path godot/project -s profile_1024.gd -- --server=http://127.0.0.1:8813 [--out=<json>]
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver opengl3 \
##     -s profile_1024.gd -- --server=... --out=<json>          (rendered: software GL, not an iPhone)
## Scenes: the new settlement at hall I, III and V, the owner's settlement of the earlier model (sixteen
## buildings at V), construction with builders, the world map with a march, the battle at its end, the
## forest adventure (camera over the forest, the squad on its way), at the default zoom and close up; and
## the frames that open the construction strip, the recruitment window and «Звук и музыка».
## Every scene: frame intervals (median, p95, p99, max, frames over 33 ms); headless numbers are CPU only.

const VERSION := "DRENOVAR-V6-C1.0"
const STOCK := {"wood": 9000000, "food": 9000000, "stone": 9000000, "iron": 9000000, "coins": 9000000}
const LEGACY_LAYOUT := [["ECO-05", "plot-14", 5], ["RES-01", "plot-0", 5], ["RES-02", "plot-5", 5],
	["RES-03", "plot-30", 5], ["RES-04", "plot-35", 5], ["ECO-01", "plot-8", 5], ["ECO-02", "plot-9", 5],
	["ECO-03", "plot-15", 5], ["ECO-04", "plot-20", 5], ["MIL-01", "plot-21", 5], ["MIL-02", "plot-26", 5],
	["MIL-03", "plot-27", 5], ["SUP-01", "plot-13", 5], ["SUP-03", "plot-2", 5], ["SUP-04", "plot-19", 5],
	["SUP-05", "plot-7", 5]]
const FRAMES := 300
const DEFAULT_ZOOM := 68.0
const CLOSE_ZOOM := 28.0

var game: Node
var server := ""
var out_path := ""
var only := ""
var rows: Array = []
var panels: Array = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			server = arg.trim_prefix("--server=").trim_suffix("/")
		elif arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=")
	if not server.begins_with("http://127.0.0.1:"):
		push_error("PROFILE_1024: --server must be a local harness")
		quit(2)
		return
	call_deferred("run")

func control(path: String, body: Variant = null, method := HTTPClient.METHOD_POST) -> Variant:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(server + path, PackedStringArray(["Content-Type: application/json"]), method, "" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else null

func frames(count: int) -> void:
	for i in count:
		await process_frame

func wait_until(condition: Callable, seconds: float) -> bool:
	var until := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < until:
		if condition.call():
			return true
		await process_frame
	return condition.call()

static func percentile(values: Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var sorted := values.duplicate()
	sorted.sort()
	return float(sorted[clampi(int(ceil(p * sorted.size())) - 1, 0, sorted.size() - 1)])

func summary(values: Array) -> Dictionary:
	return {"frames": values.size(), "median_ms": snappedf(percentile(values, 0.5), 0.01), "p95_ms": snappedf(percentile(values, 0.95), 0.01),
		"p99_ms": snappedf(percentile(values, 0.99), 0.01), "max_ms": snappedf(percentile(values, 1.0), 0.01),
		"over_33ms": values.filter(func(f): return f > 33.0).size()}

## A fresh state from the server (the harness changed it).
func refresh() -> void:
	game.drop_state_tag()
	await game.poll_account_state(true)
	await frames(30)

## FRAMES frames at a zoom with the camera drifting slowly round `center` (culling and LOD change as
## on a phone), the game's own loop running.
func measure(label: String, zoom: float, center: Vector3, radius := 6.0) -> void:
	if only != "" and not label.begins_with(only):
		return
	var stage: Node3D = game.stage
	stage.target = center
	stage.zoom = zoom
	stage.update_camera(0, true)
	await frames(45)
	var values: Array = []
	var cpu: Array = []
	var last := Time.get_ticks_usec()
	for i in FRAMES:
		var angle := float(i) / FRAMES * TAU
		stage.target = center + Vector3(cos(angle), 0.0, sin(angle)) * radius
		await process_frame
		var now := Time.get_ticks_usec()
		values.append((now - last) / 1000.0)
		cpu.append((Performance.get_monitor(Performance.TIME_PROCESS) + Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)) * 1000.0)
		last = now
	var row := {"scene": label, "zoom": zoom, "map": game.map_name}
	row.merge(summary(values))
	row.cpu = summary(cpu)
	row.nodes = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	row.memory_mb = snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1)
	row.draw_calls = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
	row.primitives = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
	row.video_mb = snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0, 0.1)
	row.texture_mb = snappedf(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0, 0.1)
	row.townsfolk = stage.townsfolk.people.size() if stage.get("townsfolk") != null and stage.townsfolk.get("people") != null else -1
	rows.append(row)
	print("PROFILE_1024 ", JSON.stringify(row))

## The frames that open a window: the call itself and the next three frames.
func open_panel(label: String, action: Callable) -> void:
	if only != "" and not ("panel_" + label).begins_with(only):
		return
	game.close_modal()
	await frames(20)
	var started := Time.get_ticks_usec()
	action.call()
	var call_ms := (Time.get_ticks_usec() - started) / 1000.0
	var next: Array = []
	var last := Time.get_ticks_usec()
	for i in 3:
		await process_frame
		var now := Time.get_ticks_usec()
		next.append((now - last) / 1000.0)
		last = now
	var row := {"panel": label, "call_ms": snappedf(call_ms, 0.01), "next_frames_ms": next.map(func(v): return snappedf(v, 0.01)),
		"worst_ms": snappedf(maxf(call_ms + next[0], next.max()), 0.01)}
	panels.append(row)
	print("PROFILE_1024_PANEL ", JSON.stringify(row))
	await frames(10)

func hall_center() -> Vector3:
	for marker: Dictionary in game.stage.place_markers:
		if str(marker.get("type", "")) in ["ECO-05", "B01"] or str(marker.get("v6_type", "")) == "B01":
			return marker.position
	return Vector3(0, 0, 0)

func city_pair(label: String) -> void:
	var center := hall_center()
	await measure(label + "_default", DEFAULT_ZOOM, center, 8.0)
	await measure(label + "_close", CLOSE_ZOOM, center, 4.0)

func run() -> void:
	root.size = Vector2i(1366, 630)
	await control("/test/reset")
	var booted := Time.get_ticks_msec()
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.player_id.is_empty() \
		and game.state.has("v6") and not game.showing_cached_state, 120.0)
	print("PROFILE_1024 boot_ms=%d" % (Time.get_ticks_msec() - booted))
	await control("/test/v6", {"stock": STOCK})
	await control("/test/army", {"units": {"ENG-01": 400, "ENG-02": 400, "ENG-03": 400, "ENG-04": 200, "ENG-06": 200}})
	await refresh()
	# Launch-time background work (forest layer, windows, townsfolk) settles first, as a player sees it.
	await wait_until(func(): return game.forest_game != null and str(game.stage.get("forest_attach_state")) == "attached", 90.0)
	await frames(240)
	await city_pair("city_hall1")
	await control("/test/v6", {"hall": 3})
	await refresh()
	await frames(240)
	await city_pair("city_hall3")
	await control("/test/v6", {"hall": 5})
	await refresh()
	await frames(240)
	await city_pair("city_hall5")
	await control("/test/legacy", {"layout": LEGACY_LAYOUT})
	await control("/test/v6", {"stock": STOCK})
	await refresh()
	await frames(300)
	await city_pair("owner_city_v")
	# --- panels (the owner's city)
	var build = game.v6_panels.build
	await open_panel("build_strip", func(): game.nav_buttons.build.pressed.emit())
	await wait_until(func(): return build.is_open() and not build.states.is_empty(), 20.0)
	await frames(30)
	game.close_modal()
	await open_panel("build_strip_again", func(): game.nav_buttons.build.pressed.emit())
	await frames(20)
	game.close_modal()
	var barracks := {}
	for b: Dictionary in game.state.v6.buildings:
		if str(b.type) == "B11":
			barracks = b
	if not barracks.is_empty():
		await open_panel("recruitment", func(): game.v6_panels.inspect_instance(str(barracks.id)))
		await frames(30)
	await open_panel("sound_settings", func(): game.v6_panels.menu_view.sound_settings())
	await open_panel("menu", func(): game.show_controls_menu())
	game.close_modal()
	await frames(20)
	# --- construction with builders: two buildings ordered from the strip
	for n in 2:
		if not await order_building():
			break
	await frames(60)
	var site := Vector3.INF
	for marker: Dictionary in game.stage.place_markers:
		if str(marker.get("kind", "")) == "site" or marker.has("site"):
			site = marker.position
	if site == Vector3.INF:
		site = game.stage.target
	await measure("construction_default", DEFAULT_ZOOM, site, 6.0)
	await measure("construction_close", CLOSE_ZOOM, site, 3.0)
	# --- a battle in the city: the army against the creature at the gate
	var creature := {}
	for e: Dictionary in game.state.get("encounters", []):
		if str(e.get("status", "")) == "alive" and str(e.get("map", "city")) == "city":
			creature = e
			break
	if not creature.is_empty():
		var deployed: bool = await game.command({"kind": "deploy", "encounterId": creature.id, "units": {"ENG-01": 120, "ENG-02": 60, "ENG-03": 40}}, func(): pass)
		print("PROFILE_1024 deploy sent=%s %s" % [str(deployed), game.last_command_error])
		var mine := {}
		for a: Dictionary in game.state.get("armies", []):
			if str(a.get("status", "")) != "returned":
				mine = a
		if not mine.is_empty():
			await control("/test/clock?time=%d" % int(float(mine.get("arrivesAt", mine.get("battleAt", 0))) - 800.0))
			await refresh()
			var spot := Vector3(float(creature.position.x), 0, float(creature.position.z))
			await measure("city_battle_default", DEFAULT_ZOOM, spot, 2.0)
			await measure("city_battle_close", CLOSE_ZOOM, spot, 1.5)
	# --- the forest adventure: the camera over the forest, the squad on its way
	if game.forest_game != null:
		var forest = game.forest_game
		await wait_until(func(): return forest.world_ready(), 60.0)
		var toward: Vector3 = forest.target_position("lf_horse_origin")
		if toward != Vector3.INF and toward != Vector3.ZERO:
			forest.on_continue_pressed()
			await frames(30)
			await measure("forest_default", DEFAULT_ZOOM, toward, 6.0)
			await measure("forest_close", CLOSE_ZOOM, toward, 3.0)
	# --- the world map with a march, and the battle at its end
	await game.show_scene("world")
	await frames(120)
	var home: Vector3 = game.stage.target
	await measure("world_default", 100.0, home, 10.0)
	var encounter := {}
	for e: Dictionary in game.state.get("world", {}).get("encounters", []):
		if str(e.get("status", "")) == "alive":
			encounter = e
			break
	if not encounter.is_empty():
		var order := {"kind": "worldMarch", "worldKind": str(encounter.get("spec", {}).get("id", "")), "encounterId": encounter.id, "units": {"ENG-01": 120, "ENG-02": 60}}
		var sent: bool = await game.command(order, func(): pass)
		print("PROFILE_1024 march sent=%s %s" % [str(sent), game.last_command_error])
		await frames(30)
		var army := {}
		for a: Dictionary in game.state.get("world", {}).get("armies", []):
			if str(a.get("owner", "")) == game.player_id:
				army = a
		var mid := home
		if encounter.get("position") is Dictionary:
			mid = (home + Vector3(float(encounter.position.x), 0, float(encounter.position.z))) * 0.5
		await measure("world_march", 100.0, mid, 6.0)
		await measure("world_march_close", 40.0, mid, 4.0)
		if not army.is_empty():
			await control("/test/clock?time=%d" % int(float(army.get("arrivesAt", army.get("battleAt", 0))) - 1500.0))
			await refresh()
			var at := Vector3(float(encounter.position.x), 0, float(encounter.position.z)) if encounter.get("position") is Dictionary else mid
			await measure("battle", 40.0, at, 2.0)
	await game.show_scene("city")
	await frames(60)
	var result := {"rows": rows, "panels": panels, "renderer": RenderingServer.get_current_rendering_method(),
		"adapter": RenderingServer.get_video_adapter_name(), "headless": DisplayServer.get_name() == "headless"}
	if not out_path.is_empty():
		var file := FileAccess.open(out_path, FileAccess.WRITE)
		file.store_string(JSON.stringify(result, "  "))
	print("PROFILE_1024_DONE scenes=%d panels=%d" % [rows.size(), panels.size()])
	game.queue_free()
	await frames(3)
	quit(0)

## «Строительство» → the first buildable card → the plot the camera shows → «Построить».
func order_building() -> bool:
	var build = game.v6_panels.build
	game.nav_buttons.build.pressed.emit()
	if not await wait_until(func(): return build.is_open() and not build.states.is_empty(), 20.0):
		return false
	await frames(20)
	var type := ""
	for entry: Array in build.CATEGORIES:
		for candidate: String in entry[2]:
			if type.is_empty() and str(build.states.get(candidate, {}).get("state", "")) == "build":
				type = candidate
	if type.is_empty():
		game.close_modal()
		return false
	build.category = build.category_of(type)
	build.show_category(build.category, false)
	build.card_tapped(type)
	await process_frame
	if not build.placing_active():
		return false
	var offered: Array = build.placement_plots()
	if offered.is_empty():
		build.cancel_placement()
		return false
	build.pick_plot(offered[0].id)
	if not await wait_until(func(): return build.quote_ready(), 10.0):
		build.cancel_placement()
		return false
	var done := [false]
	var runner := func():
		await build.confirm_build()
		done[0] = true
	runner.call()
	await wait_until(func(): return done[0], 15.0)
	return true
