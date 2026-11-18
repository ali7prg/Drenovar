extends SceneTree

# Workers, instant upgrades and instant speedups (build 51):
# - «Улучшить» starts the work on the tap: scaffolding and a running countdown with
#   the server's own duration, the cost leaves the stores at once; a refused order
#   is undone and the cost comes back;
# - with one worker the second building cannot be upgraded while the first upgrade
#   is sent or running, and the first upgrade stays where it is (before build 51 the
#   single forecast slot was overwritten and the upgrade "moved" to the second
#   building);
# - with two workers (server patch workers-v1: «Жилой дом» III) two upgrades run at
#   once, each with its own crew, and the crews keep their sites;
# - a speedup moves the timer at once (an upgrade that ends now takes its level at
#   once), an older poll answer does not undo it, a refusal does;
# - «Ускорить» on an order the server has not confirmed yet waits for its id.

var checks := 0
var failures := 0
# Optional PNG of the two crews (needs a renderer): -- --capture=/abs/dir
var capture := ""

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

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func texts(node: Node) -> Array:
	var found: Array = []
	for child in node.find_children("*", "Label", true, false):
		found.append(child.text)
	return found

func button_named(node: Node, caption: String) -> Button:
	for child in node.find_children("*", "Button", true, false):
		if child.text == caption:
			return child
	return null

func run() -> void:
	root.size = Vector2i(1366, 630)
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture = argument.trim_prefix("--capture=")
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	var stage = game.stage
	# Offline: commands cannot reach a server (they fail after the quiet retries).
	game.loopback = true
	game.endpoint = "http://127.0.0.1:9"
	game.player_id = "qa-workers"
	var state: Dictionary = game.state
	state.city.buildings[0].level = 3
	state.city.progress.wood = 5000
	state.city.demo.wallet = {"food": 5000, "stone": 5000, "iron": 5000, "coins": 5000}
	stage.present(state)
	await frames(3)
	var lumber: Dictionary = state.city.buildings.filter(func(b): return b.type == "RES-01")[0]
	var farm: Dictionary = state.city.buildings.filter(func(b): return b.type == "RES-04")[0]
	var terms: Dictionary = game.data.buildingTerms["RES-01"].upgrades[0]

	# --- One worker: the tap starts the work at once ----------------------------------
	check(game.worker_total() == 1, "An older server must mean one worker")
	var wood: int = game.balance("wood")
	var tapped: float = game.server_time()
	var order := {"kind": "kingdom", "action": "upgrade", "buildingId": lumber.id, "expectedLevel": 1}
	game.command(order)
	await frames(2)
	check(game.shown_sites.size() == 1 and str(game.shown_sites[0].get("key", "")) == str(lumber.id), "Upgrade not shown at once")
	if not game.shown_sites.is_empty():
		var site: Dictionary = game.shown_sites[0]
		check(site.get("predicted", false), "The tapped upgrade is not a running forecast")
		check(absf(float(site.ends) - float(site.started) - float(terms.seconds) * 1000.0) < 1.0,
			"Forecast duration %.0f ms, server terms %d s" % [float(site.ends) - float(site.started), int(terms.seconds)])
		check(absf(float(site.started) - tapped) < 1500.0, "Countdown does not start on the tap")
	check(game.balance("wood") == wood - int(terms.cost.wood), "Cost not taken at once: %d → %d" % [wood, game.balance("wood")])
	check(is_instance_valid(stage.works.site_node) and stage.works.site_node.visible, "No scaffolding on the tap")
	check(not game.builder_ready(), "The only worker is still free after the tap")
	# The second building: «Улучшить» locked with the reason; the first upgrade stays.
	game.inspect_building(farm)
	var upgrade_button := button_named(game.modal_body, "Улучшить")
	check(upgrade_button != null and upgrade_button.disabled, "Second upgrade allowed while the only worker is busy")
	check(texts(game.modal_body).any(func(t): return str(t).begins_with("Строитель занят")), "No reason under the locked upgrade: " + str(texts(game.modal_body)))
	game.close_modal()
	await frames(2)
	check(game.shown_sites.size() == 1 and str(game.shown_sites[0].get("key", "")) == str(lumber.id), "The first upgrade moved away")
	# The server cannot be reached: the order is undone and the cost comes back.
	await wait_until(func(): return not game.command_in_progress, 20.0)
	await frames(2)
	check(game.pending_works.is_empty() and game.shown_sites.is_empty(), "Refused upgrade left on screen")
	check(game.balance("wood") == wood, "Cost of a refused order not returned: %d" % game.balance("wood"))
	check(game.message.text.begins_with("Не выполнено"), "No message for the refused order: " + game.message.text)

	# --- Two workers: two upgrades, one crew each ------------------------------------
	state.workers = 2
	check(game.worker_total() == 2 and game.builder_ready(), "Second worker not taken from the server")
	game.predict_work({"kind": "kingdom", "action": "upgrade", "buildingId": lumber.id, "expectedLevel": 1})
	check(game.builder_ready(), "Second worker busy after one order")
	game.inspect_building(farm)
	upgrade_button = button_named(game.modal_body, "Улучшить")
	check(upgrade_button != null and not upgrade_button.disabled, "Second worker cannot upgrade the second building")
	game.close_modal()
	game.predict_work({"kind": "kingdom", "action": "upgrade", "buildingId": farm.id, "expectedLevel": 1})
	await frames(3)
	check(game.shown_sites.size() == 2, "Two upgrades not shown: %d" % game.shown_sites.size())
	check(not game.builder_ready(), "A third task allowed with two workers")
	var crew_a: Node3D = stage.works.site_node
	var crew_b: Node3D = stage.works2.site_node
	check(is_instance_valid(crew_a) and is_instance_valid(crew_b) and crew_a.visible and crew_b.visible \
		and crew_a.position.distance_to(crew_b.position) > 4.0, "Each upgrade needs its own scaffolding and crew")
	check(stage.works2.builders.size() == 2 and stage.works2.builders[0].visible, "Second crew has no builders")
	var site_a: String = stage.works.builder_site
	if not capture.is_empty():
		stage.target = crew_a.position.lerp(crew_b.position, 0.5)
		stage.zoom = 42.0
		await create_timer(1.2).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("city_two_crews.png"))
	# The server confirms both (order and order2): forecasts settle, crews stay.
	var now: float = game.server_time()
	var fresh: Dictionary = game.state.duplicate(true)
	fresh.serverTime = float(game.state.get("serverTime", 0.0)) + 1.0
	fresh.workers = 2
	fresh.items = {"construction-1": 3}
	fresh.city.kingdom.order = {"kind": "upgrade", "buildingId": lumber.id, "requestId": "qa-req-a", "type": "RES-01",
		"plotId": lumber.plotId, "level": 2, "startedAt": now, "endsAt": now + 120000.0}
	fresh.city.kingdom.order2 = {"kind": "upgrade", "buildingId": farm.id, "requestId": "qa-req-b", "type": "RES-04",
		"plotId": farm.plotId, "level": 2, "startedAt": now, "endsAt": now + 100000.0}
	game.accept(fresh.duplicate(true))
	await frames(3)
	check(game.pending_works.is_empty(), "Forecasts kept after the server's orders arrived")
	check(game.shown_sites.size() == 2 and game.shown_sites.all(func(site): return site.get("confirmed", false)), "Server orders not shown")
	check(stage.works.builder_site == site_a, "Crews swapped their sites on confirmation")
	check(game.building_order(str(farm.id)).get("requestId", "") == "qa-req-b", "Order of the second building not found")

	# --- Speedup: at once ---------------------------------------------------------------
	var order_b: Dictionary = game.state.city.kingdom.order2.duplicate()
	var payload := {"kind": "speedup", "queue": "construction", "item": "construction-1", "buildingId": "", "orderId": "qa-req-b",
		"expectedEndsAt": order_b.endsAt, "confirmUnused": false}
	game.open_modal("Применить ускоритель?")
	game.apply_speedup(Button.new(), payload)
	check(not game.modal.visible, "Speedup window still open after the tap")
	check(game.message.text == "Ускорение применено", "No confirmation of the speedup: " + game.message.text)
	check(absf(float(game.state.city.kingdom.order2.endsAt) - (float(order_b.endsAt) - 60000.0)) < 1.0, "Timer did not move at once")
	check(int(game.state.items.get("construction-1", 0)) == 2, "Item not spent at once")
	# An older poll answer (before the server applied it) does not undo it.
	var poll: Dictionary = fresh.duplicate(true)
	poll.serverTime = float(fresh.serverTime) + 400.0
	game.accept(poll.duplicate(true))
	check(absf(float(game.state.city.kingdom.order2.endsAt) - (float(order_b.endsAt) - 60000.0)) < 1.0, "Poll answer undid the speedup")
	check(int(game.state.items.get("construction-1", 0)) == 2, "Poll answer gave the item back")
	# The server cannot be reached: the speedup is refused and its timer comes back.
	await wait_until(func(): return not game.speedup_in_flight, 20.0)
	check(game.message.text.begins_with("Ускорение не применено"), "No message for the refused speedup: " + game.message.text)
	var after: Dictionary = fresh.duplicate(true)
	after.serverTime = float(fresh.serverTime) + 800.0
	game.accept(after.duplicate(true))
	check(float(game.state.city.kingdom.order2.endsAt) == float(order_b.endsAt), "Refused speedup still shown")

	# A speedup that covers the rest of an upgrade: the building is done at once.
	var finish: Dictionary = after.duplicate(true)
	var soon: float = game.timer_now() + 30000.0
	finish.serverTime = float(after.serverTime) + 1.0
	finish.city.kingdom.order2.endsAt = soon
	game.accept(finish.duplicate(true))
	var level_before: int = int(game.state.city.buildings.filter(func(b): return b.id == farm.id)[0].level)
	game.apply_speedup(Button.new(), {"kind": "speedup", "queue": "construction", "item": "construction-1", "buildingId": "",
		"orderId": "qa-req-b", "expectedEndsAt": soon, "confirmUnused": true})
	var farm_now: Dictionary = game.state.city.buildings.filter(func(b): return b.id == farm.id)[0]
	check(int(farm_now.level) == level_before + 1, "Upgrade sped to its end is not done at once (level %d)" % int(farm_now.level))
	check(not game.state.city.kingdom.has("order2") and str(game.state.city.kingdom.order.get("requestId", "")) == "qa-req-a",
		"Finished order not removed (the other one must stay)")
	await wait_until(func(): return not game.speedup_in_flight, 20.0)

	# --- «Ускорить» right after «Улучшить»: waits for the server's order -------------------
	var waiting: Dictionary = finish.duplicate(true)
	waiting.serverTime = float(finish.serverTime) + 2000.0
	waiting.city.kingdom.erase("order2")
	game.accept(waiting.duplicate(true))
	game.predict_work({"kind": "kingdom", "action": "upgrade", "buildingId": farm.id, "expectedLevel": int(farm.level)})
	var sent: Dictionary = game.building_order(str(farm.id))
	check(sent.get("predicted", false), "Just sent order not known as sent")
	game.show_speedups("construction", sent, "")
	await frames(2)
	check(texts(game.modal_body).any(func(t): return str(t).begins_with("Заказ отправлен")), "No waiting line for the order id")
	var answered: Dictionary = waiting.duplicate(true)
	answered.serverTime = float(waiting.serverTime) + 1.0
	answered.city.kingdom.order2 = {"kind": "upgrade", "buildingId": farm.id, "requestId": "qa-req-c", "type": "RES-04",
		"plotId": farm.plotId, "level": int(farm.level) + 1, "startedAt": now, "endsAt": game.timer_now() + 90000.0}
	answered.items = {"construction-1": 2}
	game.accept(answered.duplicate(true))
	var listed: bool = await wait_until(func(): return game.modal_body.find_children("*", "Button", true, false).any(
		func(b): return "в наличии" in b.text), 3.0)
	check(listed, "Speedup list did not open when the order arrived")
	game.close_modal()
	print("QA_WORKERS checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
