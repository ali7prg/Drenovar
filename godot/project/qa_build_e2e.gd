extends SceneTree

## Build 1024, end to end: a new building ordered from the V6 construction strip shows its
## scaffolding and builders on the chosen plot at once, and stands there (model, name plate,
## tap marker, clear of every other building) when the server finishes it. Run against a
## local copy of the live V6 Worker, never against production:
##
##   1. Start a local V6 server on 127.0.0.1 that serves the live Worker's fetch handler over
##      an in-memory SQLite "D1" and offers the QA controls below (the server code itself is
##      private and is not in this repository; the harness used for build 1024 imports the
##      deployed worker.mjs and calls releaseWorker({clock}).fetch(request, env) with
##      env = {DB, DRENOVAR_V6_RELEASE_ENABLED:"true", DRENOVAR_V6_NEW_SETTLEMENTS:"true",
##      DRENOVAR_V6_CONDITIONAL:"true"} on a realm already marked migrated). The D1 binding is
##      a small wrapper over node:sqlite (prepare/bind/first/all/run and an atomic batch, the
##      table game_realm37(id, revision, data)); a local copy of worker.mjs, kept outside the
##      repository, adds one export line for snapshotStore, project and planMigration, which
##      the controls use:
##        POST /test/reset              empty realm
##        POST /test/clock?time=<ms>    move the server clock forward
##        POST /test/latency?ms=<n>     commands answer n ms later (a mobile link)
##        POST /test/legacy {layout}    turn the settlement into one of the earlier model
##                                      (an imported device save: no kingdom, legacyUpgrades,
##                                      buildings [[type, "plot-N", level], ...]) migrated to
##                                      V6 by the server's own planMigration
##        POST /test/v6 {hall, stock}   town hall level and stores of the V6 state
##      Requests without X-Drenovar-Session get one fixed synthetic device session.
##   2. godot --headless --path godot/project -s qa_build_e2e.gd -- \
##        --server=http://127.0.0.1:8431 --scenario=legacy|kingdom [--latency=700] [--shots=<dir>]
##      --latency also checks that the scaffolding shows before the server answers; --shots
##      saves stills in a rendered run.
##
## Each scenario: Build → a card → a plot (ghost and glow) → «Построить»; scaffolding and
## builders at that spot right away; a second building at once (second builder, order2); the
## server clock past the end; the state poll (conditional, as the game polls); both buildings
## stand on their spots with a name plate and a tap marker and overlap nothing; the cards say
## «built» only once they exist; then a third building the same way, and an order the server
## refuses (its scaffolding goes again).

const ECONOMY := "DRENOVAR-V6-C1.0"
## A settlement of the earlier model like the owner's: sixteen buildings at level V on the
## legacy grid (plot-N), the town hall in the middle.
const LEGACY_LAYOUT := [["ECO-05", "plot-14", 5], ["RES-01", "plot-0", 5], ["RES-02", "plot-5", 5],
	["RES-03", "plot-30", 5], ["RES-04", "plot-35", 5], ["ECO-01", "plot-8", 5], ["ECO-02", "plot-9", 5],
	["ECO-03", "plot-15", 5], ["ECO-04", "plot-20", 5], ["MIL-01", "plot-21", 5], ["MIL-02", "plot-26", 5],
	["MIL-03", "plot-27", 5], ["SUP-01", "plot-13", 5], ["SUP-03", "plot-2", 5], ["SUP-04", "plot-19", 5],
	["SUP-05", "plot-7", 5]]
const STOCK := {"wood": 20000, "food": 20000, "stone": 20000, "iron": 20000, "coins": 20000}
## Two buildings closer than this (metres, ground plane) overlap.
const CLEARANCE := 7.0

var game
var server := ""
var scenario := "legacy"
var shots := ""
var latency := 0
var checks := 0
var failures := 0
var report: Array = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			server = arg.trim_prefix("--server=").trim_suffix("/")
		elif arg.begins_with("--scenario="):
			scenario = arg.trim_prefix("--scenario=")
		elif arg.begins_with("--shots="):
			shots = arg.trim_prefix("--shots=")
		elif arg.begins_with("--latency="):
			latency = int(arg.trim_prefix("--latency="))
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if condition:
		print("ok   ", description)
	else:
		failures += 1
		print("FAIL ", description)
		push_error("QA_BUILD_E2E: " + description)

func note(text: String) -> void:
	report.append(text)
	print("E2E  ", text)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func http(method: int, path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	var headers := PackedStringArray(["Accept: application/json", "X-Drenovar-Economy: " + ECONOMY])
	var text := ""
	if body != null:
		text = JSON.stringify(body)
		headers.append_array(["Content-Type: application/json", "Origin: " + server,
			"Idempotency-Key: " + Crypto.new().generate_random_bytes(12).hex_encode()])
	client.request(server + path, headers, method, text)
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string((result[3] as PackedByteArray).get_string_from_utf8())
	var out: Dictionary = parsed if parsed is Dictionary else {}
	out["httpStatus"] = int(result[1])
	return out

func shot(name: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless":
		return
	await create_timer(1.6).timeout
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(shots)
	root.get_texture().get_image().save_jpg(shots.path_join("%s_%s.jpg" % [scenario, name]), 0.88)

func flat(at: Vector3) -> Vector2:
	return Vector2(at.x, at.z)

func building_of(concept: String) -> Dictionary:
	for b: Dictionary in game.state.city.buildings:
		if str(b.get("conceptType", "")) == concept:
			return b
	return {}

## A visible model of the city at a spot (ground plane), or null.
func model_at(at: Vector3) -> Node3D:
	for child in game.stage.buildings.get_children():
		if child is Node3D and child.visible and flat(child.global_position).distance_to(flat(at)) < 0.6:
			return child
	return null

## The construction site of the city's crews at a spot: [site dict, crew] or [].
func site_at(at: Vector3) -> Array:
	for index in game.shown_sites.size():
		var site: Dictionary = game.shown_sites[index]
		if site.has("position") and flat(site.position).distance_to(flat(at)) < 0.6:
			return [site, index]
	return []

func crew_shows(at: Vector3) -> bool:
	for crew in [game.stage.works, game.stage.works2]:
		if is_instance_valid(crew.site_node) and crew.site_node.visible and flat(crew.site_node.position).distance_to(flat(at)) < 0.6 \
				and crew.builders.size() >= 2 and crew.builders.all(func(b): return b.visible):
			return true
	return false

func card_state(type: String) -> String:
	return str(game.v6_panels.build.card_state(type).get("state", ""))

func run() -> void:
	root.size = Vector2i(1366, 630)
	check(server.begins_with("http://127.0.0.1:"), "Local server given (--server=http://127.0.0.1:PORT)")
	if not server.begins_with("http://127.0.0.1:"):
		finish()
		return
	# The settlement, before the game opens: a new one, or one of the earlier model.
	check(int((await http(HTTPClient.METHOD_POST, "/test/reset", {})).httpStatus) == 200, "Local realm reset")
	# A mobile link: the server answers commands this much later.
	await http(HTTPClient.METHOD_POST, "/test/latency?ms=%d" % latency, {})
	var created := await http(HTTPClient.METHOD_POST, "/api/session/new", {})
	check(int(created.httpStatus) == 201, "Settlement created on the local V6 server (%d)" % int(created.httpStatus))
	if scenario == "legacy":
		var legacy := await http(HTTPClient.METHOD_POST, "/test/legacy", {"layout": LEGACY_LAYOUT})
		check(int(legacy.get("changes", 0)) == 1, "Settlement turned into one of the earlier model and migrated by the server")
	var setup := {"stock": STOCK}
	if scenario == "kingdom":
		setup.hall = 4  # two builders and free plots
	await http(HTTPClient.METHOD_POST, "/test/v6", setup)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var connected: bool = await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) \
		and not game.player_id.is_empty() and game.v6_panels.enabled() and game.map_name == "city", 90.0)
	check(connected, "Game connected to the local V6 server and shows the city")
	if not connected:
		finish()
		return
	var city: Dictionary = game.state.city
	if scenario == "legacy":
		check(not city.has("kingdom") and city.get("legacyUpgrades") is Dictionary, "City is of the earlier model (legacyUpgrades, no kingdom)")
		check(city.buildings.all(func(b): return str(b.plotId).begins_with("plot-")), "Older buildings stand on the legacy grid plot-N")
	else:
		check(city.get("kingdom") is Dictionary, "City is a kingdom")
	check(int(game.state.get("workers", 1)) == 2, "Two builders")
	await wait_until(func(): return game.stage.townsfolk == null or game.stage.townsfolk.rebuilds > 0, 20.0)
	if not shots.is_empty():
		var view: Vector3 = game.stage.target
		game.stage.target = Vector3.ZERO
		game.stage.zoom = 100.0
		await shot("0_overview_before")
		game.stage.target = view
		game.stage.zoom = 68.0
	var before_models: int = game.stage.buildings.get_child_count()
	# Two buildings at once (the first and the second builder), then a third.
	var built: Array = []
	var first := await order_building("")
	if first.is_empty():
		finish()
		return
	built.append(first)
	var second := await order_building(str(first.type))
	if not second.is_empty():
		built.append(second)
		var construction: Variant = game.state.city.get("kingdom", game.state.city.get("legacyUpgrades"))
		check(construction is Dictionary and construction.get("order") is Dictionary and construction.get("order2") is Dictionary,
			"The server runs both orders (order and order2)")
		check(site_at(first.spot).size() > 0 and site_at(second.spot).size() > 0 and crew_shows(first.spot) and crew_shows(second.spot),
			"Both sites have scaffolding and builders")
		check_ground(str(first.title) + " (first site, second order running)", first.spot)
	await shot("1_sites")
	# A routine poll with the tag of the state on screen (the game polls conditionally): the
	# sites stay while nothing changes on the server.
	var full_before: int = game.full_polls
	var quiet_before: int = game.not_modified_polls
	for i in 3:
		await wait_until(func(): return not game.polling_state and not game.busy, 5.0)
		await game.poll_account_state()
	await process_frame
	await process_frame
	check(game.not_modified_polls > quiet_before, "The server answers a poll with 304 (cached state, advanced_state)")
	check(built.all(func(entry): return site_at(entry.spot).size() > 0 and crew_shows(entry.spot)), "Sites stay through the conditional polls")
	note("state polls while building: %d full, %d not modified" % [game.full_polls - full_before, game.not_modified_polls - quiet_before])
	await finish_orders(built)
	for entry: Dictionary in built:
		await check_standing(entry)
	var third := await order_building("")
	if not third.is_empty():
		await finish_orders([third])
		await check_standing(third)
		built.append(third)
	# Nothing stands inside anything else.
	var spots: Array = []
	for marker: Dictionary in game.stage.place_markers:
		if marker.get("kind", "") == "building" and not marker.get("wall", false):
			spots.append([str(marker.id), flat(marker.position)])
	var overlaps: Array = []
	for i in spots.size():
		for j in range(i + 1, spots.size()):
			if (spots[i][1] as Vector2).distance_to(spots[j][1]) < CLEARANCE:
				overlaps.append("%s~%s" % [spots[i][0], spots[j][0]])
	check(overlaps.is_empty(), "No two buildings overlap (%s)" % ", ".join(overlaps))
	check(game.stage.buildings.get_child_count() >= before_models + built.size(), "The city draws %d more building models" % built.size())
	# Stills (rendered runs with --shots): each new building close up, then the settlement.
	if not shots.is_empty():
		for entry: Dictionary in built:
			game.stage.target = entry.spot
			game.stage.zoom = 56.0
			await shot("2_built_" + str(entry.type))
		game.stage.target = Vector3.ZERO
		game.stage.zoom = 100.0
		await shot("3_overview")
	await refused_order()
	note("built: " + ", ".join(built.map(func(e): return "%s on %s at (%.1f, %.1f)" % [e.type, e.plot, e.spot.x, e.spot.z])))
	finish()

## Build → a «build» card (not `skip`) → the plot the camera shows first → «Построить».
## Returns {type, plot, spot} or {} when nothing could be ordered.
func order_building(skip: String) -> Dictionary:
	var build = game.v6_panels.build
	game.nav_buttons.build.pressed.emit()
	var opened: bool = await wait_until(func(): return build.is_open() and not build.states.is_empty(), 20.0)
	check(opened, "Build opens the V6 construction strip")
	if not opened:
		return {}
	await create_timer(0.4).timeout
	var type := ""
	for entry: Array in build.CATEGORIES:
		for candidate: String in entry[2]:
			if type.is_empty() and candidate != skip and str(build.states.get(candidate, {}).get("state", "")) == "build":
				type = candidate
	check(not type.is_empty(), "A card can be built")
	if type.is_empty():
		var seen: Array = build.states.keys().map(func(t): return "%s:%s" % [t, build.states[t].state])
		note("cards: " + " ".join(seen))
		return {}
	var title := str(build.states[type].row.get("name_ru", type))
	build.category = build.category_of(type)
	build.show_category(build.category, false)
	build.card_tapped(type)
	await process_frame
	check(build.placing_active(), "%s: tapping the card starts placement" % title)
	if not build.placing_active():
		return {}
	var offered: Array = build.placement_plots()
	check(not offered.is_empty() and offered.all(func(p): return p.position != Vector3.INF), "%s: %d plots offered, each with a spot" % [title, offered.size()])
	# The plot the camera moved to (the free plot nearest the town hall) is the one tapped.
	var plot := ""
	var spot := Vector3.INF
	for entry: Dictionary in offered:
		if flat(entry.position).distance_to(flat(game.stage.target)) < 0.5:
			plot = entry.id
			spot = entry.position
	check(not plot.is_empty(), "%s: the camera shows a free plot" % title)
	if plot.is_empty():
		plot = offered[0].id
		spot = offered[0].position
	# Every glowing plot is clear of the buildings already standing.
	var crowded: Array = []
	for entry: Dictionary in offered:
		for marker: Dictionary in game.stage.place_markers:
			if marker.get("kind", "") == "building" and not marker.get("wall", false) and flat(marker.position).distance_to(flat(entry.position)) < CLEARANCE:
				crowded.append("%s~%s" % [entry.id, marker.id])
	check(crowded.is_empty(), "%s: no offered plot lies on a building (%s)" % [title, ", ".join(crowded)])
	build.pick_plot(plot)
	var quoted: bool = await wait_until(func(): return build.quote_ready(), 10.0)
	check(quoted and not build.placing.quote.is_empty(), "%s: the server quotes the build on %s" % [title, plot])
	var ghost: Node3D = game.stage.placement_ghost
	check(is_instance_valid(ghost) and ghost.visible and flat(ghost.position).distance_to(flat(spot)) < 0.1, "%s: the ghost stands on the chosen plot" % title)
	var glow := false
	for ring: MeshInstance3D in game.stage.placement_rings:
		glow = glow or flat(ring.position).distance_to(flat(spot)) < 0.1
	check(glow, "%s: the chosen plot glows" % title)
	if not quoted or build.placing.quote.is_empty():
		build.cancel_placement()
		return {}
	await shot("place_" + type)
	# «Построить». The scaffolding must stand where the ghost stood.
	var sent := Time.get_ticks_msec()
	var frames := 0
	var first_shown := -1
	var first_shown_ms := -1
	var confirm: Callable = build.confirm_build
	var done := [false]
	var runner := func():
		await confirm.call()
		done[0] = true
	runner.call()
	while not done[0] and Time.get_ticks_msec() - sent < 15000:
		await process_frame
		frames += 1
		if first_shown < 0 and site_at(spot).size() > 0 and crew_shows(spot):
			first_shown = frames
			first_shown_ms = Time.get_ticks_msec() - sent
	var reply_ms := Time.get_ticks_msec() - sent
	check(done[0], "%s: the server answered the order" % title)
	var shown: bool = await wait_until(func(): return site_at(spot).size() > 0 and crew_shows(spot), 3.0)
	check(shown, "%s: scaffolding and builders at the chosen spot after «Построить»" % title)
	note("%s on %s: answer after %d ms; scaffolding and builders after %d ms (frame %d of %d)" % [type, plot, reply_ms,
		first_shown_ms, first_shown, frames])
	# «Построить» shows where the building goes at once (the first frames after the tap), not one
	# server round trip later; with a slow link (--latency) well before the answer.
	check(first_shown >= 1 and first_shown <= 2, "%s: scaffolding and builders at once after «Построить» (frame %d, %d ms; answer %d ms)" % [title, first_shown, first_shown_ms, reply_ms])
	if latency >= 300:
		check(first_shown_ms < reply_ms - latency / 2, "%s: scaffolding before the server answers (%d ms, answer %d ms)" % [title, first_shown_ms, reply_ms])
	var site: Array = site_at(spot)
	if not site.is_empty():
		check(not str(site[0].get("model", "")).is_empty(), "%s: the new building rises inside the scaffolding" % title)
	check(flat(game.stage.target).distance_to(flat(spot)) < 0.5, "%s: the camera is on the site" % title)
	await process_frame
	check_ground(title + " (site)", spot)
	var named := false
	for marker: Dictionary in game.stage.empty_plots:
		named = named or str(marker.item.id) == plot and flat(marker.position).distance_to(flat(spot)) < 0.5
	check(named, "%s: the site carries the name and progress plate" % title)
	check(card_state(type) == "busy", "%s: the card says under construction (%s), not built" % [title, card_state(type)])
	check(building_of(type).is_empty() and model_at(spot) == null, "%s: no finished building before the end" % title)
	return {"type": type, "plot": plot, "spot": spot, "title": title}

## An order the server refuses (the stores emptied after the quote): the scaffolding shown on
## «Построить» goes again and nothing is left on the plot.
func refused_order() -> void:
	var build = game.v6_panels.build
	game.nav_buttons.build.pressed.emit()
	if not await wait_until(func(): return build.is_open() and not build.states.is_empty(), 20.0):
		check(false, "Build opens the V6 construction strip (refusal)")
		return
	await create_timer(0.4).timeout
	var type := ""
	for entry: Array in build.CATEGORIES:
		for candidate: String in entry[2]:
			if type.is_empty() and str(build.states.get(candidate, {}).get("state", "")) == "build":
				type = candidate
	if type.is_empty():
		note("refusal: no card left to build")
		build.view.closed.emit()
		return
	build.card_tapped(type)
	await process_frame
	var plot := ""
	var spot := Vector3.INF
	for entry: Dictionary in build.placement_plots():
		if flat(entry.position).distance_to(flat(game.stage.target)) < 0.5:
			plot = entry.id
			spot = entry.position
	build.pick_plot(plot)
	await wait_until(func(): return build.quote_ready(), 10.0)
	await http(HTTPClient.METHOD_POST, "/test/v6", {"stock": {"wood": 0, "food": 0, "stone": 0, "iron": 0, "coins": 0}})
	var done := [false, false]
	var runner := func():
		await build.confirm_build()
		done[0] = true
	runner.call()
	var shown_early: bool = await wait_until(func(): return site_at(spot).size() > 0, 0.25)
	await wait_until(func(): return done[0], 15.0)
	var gone: bool = await wait_until(func(): return site_at(spot).is_empty() and not crew_shows(spot), 2.0)
	check(gone and building_of(type).is_empty() and game.construction_orders().is_empty(), "Refused order: no scaffolding or building is left on %s" % plot)
	check(not str(game.last_command_error).is_empty(), "Refused order: the server's reason is kept (%s)" % game.last_command_error)
	note("refused %s on %s: forecast shown %s, removed %s" % [type, plot, shown_early, gone])
	await http(HTTPClient.METHOD_POST, "/test/v6", {"stock": STOCK})

## The server clock past the last end; the game's own poll (as at a timer's zero) brings it.
func finish_orders(entries: Array) -> void:
	var last := 0.0
	for order: Dictionary in game.construction_orders():
		last = maxf(last, float(order.get("endsAt", 0.0)))
	check(last > 0.0, "Construction orders carry their end")
	await http(HTTPClient.METHOD_POST, "/test/clock?time=%d" % int(last + 5000.0), {})
	var finished: bool = await wait_until(func():
		if not game.polling_state:
			game.poll_account_state(true)
		return entries.all(func(e): return not building_of(e.type).is_empty()), 20.0)
	check(finished, "The state after the end has the new buildings")

func check_standing(entry: Dictionary) -> void:
	var title: String = entry.title
	var b := building_of(entry.type)
	check(str(b.get("plotId", "")) == entry.plot, "%s: on its plot %s" % [title, entry.plot])
	var marker: Dictionary = {}
	for item: Dictionary in game.stage.place_markers:
		if str(item.get("id", "")) == str(b.get("id", "~")):
			marker = item
	check(not marker.is_empty(), "%s: tap marker and name plate in the city" % title)
	if not marker.is_empty():
		check(flat(marker.position).distance_to(flat(entry.spot)) < 0.5, "%s: stands where it was built (%.1f m off)" % [title, flat(marker.position).distance_to(flat(entry.spot))])
	check(model_at(entry.spot) != null, "%s: its model is drawn at the spot" % title)
	check_ground(title, entry.spot)
	var cleared: bool = await wait_until(func(): return site_at(entry.spot).is_empty() and not crew_shows(entry.spot), 3.0)
	check(cleared, "%s: the scaffolding and builders are gone" % title)
	check(card_state(entry.type) == "maxed", "%s: the card says built (%s)" % [title, card_state(entry.type)])

## On dry ground, inside the wall ring when there is one, with no tree standing in it.
func check_ground(title: String, at: Vector3) -> void:
	var stage = game.stage
	check(stage.static_height(at.x, at.z) >= -0.2, "%s: on dry ground (height %.2f)" % [title, stage.static_height(at.x, at.z)])
	check(not stage.walls.visible or stage.walls.inside(at.x, at.z, 4.0), "%s: inside the wall ring" % title)
	var trees := 0
	for cell: Vector2i in stage.standing_tree_cells:
		for tree: Vector2 in stage.standing_tree_cells[cell]:
			if tree.distance_to(flat(at)) < 5.0:
				trees += 1
	check(trees == 0, "%s: no tree stands in it (%d)" % [title, trees])

func finish() -> void:
	print("QA_BUILD_E2E scenario=%s checks=%d failures=%d" % [scenario, checks, failures])
	for line in report:
		print("QA_BUILD_E2E ", line)
	quit(0 if failures == 0 and checks > 0 else 1)
