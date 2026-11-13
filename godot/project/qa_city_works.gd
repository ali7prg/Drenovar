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
	game.pending_works.tree.ends = game.server_time() + 300.0
	await frames(2)
	var city: Dictionary = game.state.city
	city.progress.felled.append(tree.id)
	stage.present(game.state)
	await frames(2)
	var falling: Array = works.find_children("Falling", "", true, false)
	check(falling.size() == 1, "Tree did not topple")
	var texts: Array = []
	var wait_until := Time.get_ticks_msec() + 20000
	while texts.is_empty() and Time.get_ticks_msec() < wait_until:
		await process_frame
		texts = works.find_children("*", "Label3D", true, false).filter(func(l): return l.text.begins_with("+"))
	check(not texts.is_empty(), "No wood reward shown")
	await create_timer(0.3).timeout
	if not capture.is_empty():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("works_fell.png"))
	game.pending_works.erase("tree")
	# Upgrade: scaffolding + builders, completion burst.
	var building: Dictionary = city.buildings[1]
	var before: int = stage.buildings.get_child_count()
	city.kingdom.order = {"kind": "upgrade", "buildingId": building.id, "endsAt": game.server_time() + 20000.0}
	stage.present(game.state)
	await frames(6)
	check(stage.buildings.get_child_count() > before, "No scaffolding on the upgraded building")
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
	print("QA_CITY_WORKS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
