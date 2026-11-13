extends SceneTree

# Visible work and instant orders:
# - "Срубить" closes the window at once and a lumberjack walks to the tree and
#   swings; when the tree is felled it topples and "+N дерева" rises;
# - an upgrade shows scaffolding and hammering builders; completion celebrates;
# - an order that the server cannot take is undone with a short message, and a
#   second order sent meanwhile waits instead of being dropped.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func frames(count: int) -> void:
	for i in count:
		await process_frame

func run() -> void:
	root.size = Vector2i(1366, 630)
	var capture := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture = argument.trim_prefix("--capture=")
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	var stage = game.stage
	var works = stage.works
	# A standing tree near the city centre, in view.
	var tree: Dictionary = {}
	var best := INF
	for candidate in stage.selectable_trees:
		var p: Vector3 = stage.array_point(candidate.p)
		var gap: float = p.distance_squared_to(stage.camera_target)
		if gap < best and not candidate.id in game.state.city.progress.felled and gap > 100.0:
			best = gap
			tree = candidate
	check(not tree.is_empty(), "No tree to fell")
	var trunk: Vector3 = stage.array_point(tree.p)
	stage.target = trunk
	await frames(20)
	# Instant order without a server: window closes at once, work starts, then the
	# failed order is undone with a message.
	game.loopback = true
	game.endpoint = "http://127.0.0.1:9"
	game.player_id = "qa-works"
	game.open_modal(tree.name)
	var order := {"kind": "resource", "action": "tree", "id": tree.id}
	var started := Time.get_ticks_msec()
	var first := func(): await game.command(order)
	first.call()
	check(not game.modal.visible, "Window did not close at once")
	check(game.pending_works.has("tree"), "Felling was not shown at once")
	var second_done := [false]
	var second := func():
		await game.command({"kind": "kingdom", "action": "collect", "buildingId": "x"})
		second_done[0] = true
	second.call()
	await process_frame
	await frames(3)
	check(is_instance_valid(works.lumberjack) and works.lumberjack.visible, "No lumberjack at the tree")
	while game.command_in_progress or not second_done[0]:
		await process_frame
		if Time.get_ticks_msec() - started > 90000:
			break
	check(second_done[0], "Second order was dropped while the first was in flight")
	check(not game.pending_works.has("tree"), "Failed order left the felling on screen")
	check(game.message.text.begins_with("Не выполнено"), "No message after a refused order: " + game.message.text)
	# Felling with a confirmed job: walk, swing, then topple with the reward.
	var now: float = game.server_time()
	game.pending_works.tree = {"tree": tree.id, "started": now - 1600.0, "ends": now + 600000.0, "order": {}}
	await frames(4)
	var lumberjack: Node3D = works.lumberjack
	check(lumberjack.position.distance_to(trunk) < 2.5, "Lumberjack not beside the tree (%.1f)" % lumberjack.position.distance_to(trunk))
	var arms: Array = lumberjack.get_meta("arms", [])
	check(not arms.is_empty(), "Worker model has no arm nodes")
	var angles := {}
	for i in 30:
		await process_frame
		if not arms.is_empty():
			angles[snappedf(arms[0].rotation.x, 0.1)] = true
	check(angles.size() >= 4, "Axe is not swinging")
	if not capture.is_empty():
		stage.zoom = 30.0
		await create_timer(0.5).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("works_chop.png"))
	# Before the server confirms: the worker goes to the tree, no countdown.
	check(game.shown_job.get("confirmed", true) == false, "Unconfirmed felling shows a countdown")
	# The server's job (started later than the tap by the network delay) is what
	# runs the countdown: its own end, never the forecast.
	game.state.serverTime = game.server_time()
	var server_now: float = game.timer_now()
	var city: Dictionary = game.state.city
	var wood_before: int = game.balance("wood")
	var fresh: Dictionary = game.state.duplicate(true)
	fresh.serverTime = float(game.state.get("serverTime", 0.0)) + 1.0
	fresh.city.progress.job = {"id": "job-qa", "kind": "tree", "target": tree.id, "startedAt": server_now - 3800.0, "endsAt": server_now + 1200.0}
	game.accept(fresh)
	city = game.state.city
	await frames(2)
	check(game.shown_job.get("confirmed", false) and is_equal_approx(float(game.shown_job.ends), server_now + 1200.0), "Countdown does not follow the server job")
	check(not game.pending_works.has("tree"), "Forecast kept after the server job arrived")
	# Zero on the phone without a server answer: nothing is granted or felled.
	var zero_at := Time.get_ticks_msec()
	while game.timer_now() < server_now + 1400.0 and Time.get_ticks_msec() - zero_at < 4000:
		await process_frame
	await frames(3)
	check(not tree.id in city.progress.felled, "Tree felled on the phone without the server")
	check(game.balance("wood") == wood_before, "Wood counted without the server")
	check(city.progress.job != null and not game.shown_job.is_empty(), "Job vanished before the server confirmed")
	game.diagnostics.network_failures = 3
	check(game.timer_end_label() == "Нет связи · ждём сервер", "Offline zero shown as done: " + game.timer_end_label())
	game.diagnostics.network_failures = 0
	# A late answer (older server time) never replaces the newer confirmed state.
	var stale: Dictionary = game.state.duplicate(true)
	stale.serverTime = float(game.state.serverTime) - 5000.0
	stale.city.progress.job = null
	game.accept(stale)
	check(game.state.city.progress.job != null and game.stale_responses >= 1, "Late answer replaced a newer state")
	# The server confirms: tree felled and wood from the server's numbers only.
	var confirmed: Dictionary = game.state.duplicate(true)
	confirmed.serverTime = float(game.state.serverTime) + 2000.0
	confirmed.city.progress.job = null
	confirmed.city.progress.felled.append(tree.id)
	confirmed.city.progress.wood = wood_before + int(tree.wood)
	game.accept(confirmed)
	city = game.state.city
	await frames(3)
	check(game.shown_job.is_empty(), "Job shown after the server finished it")
	check(game.balance("wood") == wood_before + int(tree.wood), "Wood differs from the server")
	var falling: Array = works.find_children("Falling", "", true, false)
	check(falling.size() == 1, "Tree did not topple on the server's confirmation")
	# A replayed older answer does not bring the tree or the timer back.
	var replay: Dictionary = fresh.duplicate(true)
	game.accept(replay)
	await frames(2)
	check(game.shown_job.is_empty() and tree.id in game.state.city.progress.felled, "Replayed answer restarted the felling")
	var texts: Array = []
	var wait_until := Time.get_ticks_msec() + 20000
	while texts.is_empty() and Time.get_ticks_msec() < wait_until:
		await process_frame
		texts = works.find_children("*", "Label3D", true, false).filter(func(l): return l.text.begins_with("+"))
	check(not texts.is_empty(), "No wood reward shown")
	if texts.is_empty():
		print("DBG labels ", works.find_children("*", "Label3D", true, false).map(func(l): return l.text), " falling ", works.find_children("Falling", "", true, false).size(), " lumber_ends ", works.lumber_ends, " last_now ", works.last_now, " tree ", works.lumber_tree)
	await create_timer(0.3).timeout
	if not capture.is_empty():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("works_fell.png"))
	game.pending_works.erase("tree")
	# Upgrade: scaffolding + builders, completion burst.
	var building: Dictionary = city.buildings[1]
	city.kingdom.order = {"kind": "upgrade", "buildingId": building.id, "endsAt": game.server_time() + 20000.0}
	stage.present(game.state)
	await frames(6)
	check(is_instance_valid(works.site_node) and works.site_node.visible and works.site_frames.size() == 1, "No scaffolding on the upgraded building")
	check(not is_instance_valid(works.site_model), "Upgrade must keep the building, not raise a new one")
	check(works.builders.size() == 2 and works.builders.all(func(b): return b.visible), "No builders at the site")
	stage.target = stage.work_sites[building.plotId]
	if not capture.is_empty():
		stage.zoom = 32.0
		await create_timer(0.6).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("works_build.png"))
	city.kingdom.erase("order")
	building.level = int(building.level) + 1
	stage.present(game.state)
	await frames(3)
	check(works.builders.all(func(b): return not b.visible), "Builders stayed after the work ended")
	var cheers: Array = works.find_children("*", "Label3D", true, false).filter(func(l): return l.text.begins_with("Уровень"))
	check(not cheers.is_empty(), "No completion effect")
	# Server job naming a village tree is recognised (not only "tree-N" ids).
	var village: Array = stage.selectable_trees.filter(func(t): return str(t.id).begins_with("village-"))
	if not village.is_empty():
		check(game.job_tree_id({"target": village[0].id, "endsAt": 1}) == village[0].id, "Village tree job not recognised")
	# New building: rises inside the scaffolding with its timer.
	var free_plot: Dictionary = stage.empty_plots[0].item
	var now2: float = game.server_time()
	city.kingdom.order = {"kind": "build", "plotId": free_plot.id, "type": "SUP-04", "endsAt": now2 + 100000.0, "startedAt": now2 - 50000.0}
	stage.present(game.state)
	await frames(4)
	check(is_instance_valid(works.site_model), "New building does not rise on its plot")
	if not capture.is_empty():
		stage.target = stage.work_sites[free_plot.id]
		stage.zoom = 34.0
		await create_timer(0.8).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("works_rising.png"))
	if is_instance_valid(works.site_model):
		var height: float = works.site_model.scale.y / float(game.data.models[game.data.types["SUP-04"]].scale)
		check(height > 0.3 and height < 0.8, "Rising height does not follow the timer (%.2f at one third)" % height)
	city.kingdom.erase("order")
	stage.present(game.state)
	await frames(2)
	check(not works.site_node.visible, "Construction site stayed after the order ended")
	# Settlement of the earlier model: build goes as "legacyBuilding place".
	var kingdom = city.kingdom
	city.erase("kingdom")
	var legacy: Dictionary = game.build_order("p1", "SUP-04")
	check(legacy.get("kind") == "legacyBuilding" and legacy.get("action") == "place", "Legacy settlement got a kingdom build order")
	city.kingdom = kingdom
	check(game.build_order("p1", "SUP-04").get("kind") == "kingdom", "Kingdom settlement lost its build order")
	# After a confirmed timer reaches zero the server is asked every 0.7 s, no storm.
	game.diagnostics.network_failures = 0
	var standing: Array = stage.selectable_trees.filter(func(t): return not t.id in game.state.city.progress.felled)
	game.state.city.progress.job = {"id": "job-due", "kind": "tree", "target": standing[0].id,
		"startedAt": game.timer_now() - 5100.0, "endsAt": game.timer_now() - 100.0}
	var asked_before: int = game.api.requests_total
	var until := Time.get_ticks_msec() + 4600
	while Time.get_ticks_msec() < until:
		await process_frame
	var asked: int = game.api.requests_total - asked_before
	check(asked >= 4 and asked <= 8, "Requests after zero: %d in 4.6 s (expected ~6)" % asked)
	game.state.city.progress.job = null
	print("QA_CITY_WORKS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
