extends SceneTree

# The real Godot client against the Cloudflare staging Worker with device accounts.
#   godot --path . -s qa_staging_device.gd -- --server=https://<staging> --staging-key-file=<file>
# DRENOVAR_QA_PHASE:
#   first   - forget any saved login, sign in with a new device account, found a settlement,
#             place a training order.
#   restart - a new app start reads the saved device session and gets the same settlement;
#             then the march window sends an army to Tenerys I (the staging fixture puts a
#             building beside its patrol and gives the settlement soldiers between phases).

const SessionStore = preload("res://src/session_store.gd")
var checks := 0
var failures := 0
var game

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if condition:
		print("ok  ", description)
	else:
		failures += 1
		push_error(description)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func finish() -> void:
	print("QA_STAGING_DEVICE phase=", OS.get_environment("DRENOVAR_QA_PHASE"), " checks=", checks, " failures=", failures,
		" player=", game.player_id if game else "")
	quit(0 if failures == 0 else 1)

func run() -> void:
	var phase := OS.get_environment("DRENOVAR_QA_PHASE")
	if phase == "first":
		SessionStore.forget()
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	check(await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage), 90.0), "Game scene loaded")
	check(not game.loopback, "Client talks to a hosted server (not the loopback realm): " + game.endpoint)
	if phase == "first":
		game.begin_login()
		check(await wait_until(func(): return SessionStore.is_device(game.session) and not game.login_in_progress, 30.0), "Device login without a browser step")
		check(SessionStore.read_session() == game.session, "Device session saved encrypted on the device")
		await game.create_settlement()
		check(await wait_until(func(): return not game.player_id.is_empty() and game.state.has("city") and game.state.has("world"), 30.0), "Settlement founded and loaded")
		var barracks: Dictionary = {}
		for building in game.state.city.buildings:
			if game.stage.city_base_type(building.type) == "MIL-01":
				barracks = building
		check(not barracks.is_empty(), "Settlement has barracks")
		if not barracks.is_empty():
			var training: Dictionary = await game.request("command", {"kind":"train", "buildingId":barracks.id, "unitId":"ENG-09", "quantity":1})
			var queue: Array = training.get("city", {}).get("military", {}).get("queues", {}).get(barracks.id, [])
			check(queue.size() >= 1, "Training order accepted by the server (%s)" % training.get("error", "queued"))
			if training.has("city"):
				game.accept(training)
		finish()
		return
	# restart
	check(SessionStore.is_device(game.session), "Saved device session read at start")
	check(await wait_until(func(): return not game.player_id.is_empty() and game.state.has("city") and not game.showing_cached_state, 30.0), "Same settlement restored from the server")
	await game.sync_account()
	var target: Dictionary = {}
	for encounter in game.state.get("encounters", []):
		if encounter.get("species") == "tenerys" and int(encounter.level) == 1 and encounter.status == "alive":
			target = encounter
	check(not target.is_empty(), "Tenerys I alive in the settlement")
	check(int(game.state.healthy.get("ENG-09", 0)) > 0, "Soldiers available: %d" % int(game.state.healthy.get("ENG-09", 0)))
	if target.is_empty():
		finish()
		return
	var armies_before: int = game.state.get("armies", []).size()
	game.inspect_encounter(target)
	var attack := game.modal_footer.get_child(0) as Button
	check(attack != null and attack.text == "Атаковать", "Creature panel offers «Атаковать»")
	attack.pressed.emit()
	check(await wait_until(func(): return game.modal_title.text == "Создать войско" and game.modal_footer.find_child("MarchSend", true, false) != null, 5.0), "March window opened")
	var send := game.modal_footer.find_child("MarchSend", true, false) as Button
	# The first route preview goes to the server; with route-approach-v2 it finds a route
	# even while the creature is beside the building, and the order leaves at once.
	await wait_until(func(): return is_instance_valid(send) and send.get_meta("route_ready", false), 10.0)
	send.pressed.emit()
	var left: bool = await wait_until(func(): return game.state.get("armies", []).size() > armies_before, 40.0)
	check(left, "Army marched to Tenerys I (button: %s)" % (send.text if is_instance_valid(send) else "window closed"))
	check(game.last_command_error != game.BLOCKED_ROUTE, "No «Нет безопасного пути к цели»")
	finish()
