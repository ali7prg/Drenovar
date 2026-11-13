extends SceneTree

# City march to a creature next to a building, against the real server
# (godot/tools/test-realm.mjs with DRENOVAR_TEST_BLOCKED_CREATURE). Run with:
#   -- --server=http://127.0.0.1:8417
# DRENOVAR_QA_MODE (with the matching realm fixture):
#   refused  - server v92, DRENOVAR_TEST_BLOCKED_CREATURE=1 (clock frozen, the
#              creature never leaves the building's clearance): «Отправляем…» goes
#              away, the client waits one patrol round, then shows the refusal; the
#              button and «Повторить расчёт» work again; no army, no soldiers lost.
#   wait     - server v92, DRENOVAR_TEST_BLOCKED_CREATURE=moving: the order pressed
#              while the creature is blocked is held by the client («Выход через N с»)
#              and sent for the moment the creature is in the open: the server
#              accepts it at once, never refusing it.
#   approach - server with route-approach-v2, DRENOVAR_TEST_BLOCKED_CREATURE=1: the
#              march leaves at once, through the gates of the city wall.

const BLOCKED := "Нет безопасного пути к цели"
var checks := 0
var failures := 0
var game

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
	else:
		print("ok  ", description)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func send_button() -> Button:
	return game.modal_footer.find_child("MarchSend", true, false) as Button

func quote() -> Label:
	return game.modal_body.find_child("MarchQuote", true, false) as Label

func retry_button() -> Button:
	for button: Button in game.modal_body.find_children("*", "Button", true, false):
		if button.text == "Повторить расчёт":
			return button
	return null

func open_march(target: Dictionary) -> bool:
	game.inspect_encounter(target)
	var attack := game.modal_footer.get_child(0) as Button
	if attack == null or attack.text != "Атаковать":
		return false
	attack.pressed.emit()
	return await wait_until(func(): return game.modal_title.text == "Создать войско" and send_button() != null, 5.0)

func armies() -> Array:
	return game.state.get("armies", [])

# Every step that crosses the wall line does it inside a gate opening; the route
# crosses the wall exactly when the army and the target are on different sides.
func wall_route(path: Array, target: Vector2, label: String) -> void:
	var walls = game.stage.walls
	var bad := 0
	var crossings := 0
	for i in range(1, path.size()):
		var a := Vector2(float(path[i - 1].x), float(path[i - 1].z))
		var b := Vector2(float(path[i].x), float(path[i].z))
		for t in range(1, 11):
			var p := a.lerp(b, float(t) / 10.0)
			var q := a.lerp(b, float(t - 1) / 10.0)
			if walls.inside(p.x, p.y) != walls.inside(q.x, q.y):
				crossings += 1
				var f: float = walls.sample_index(p.x, p.y)
				var at_gate := false
				for k in walls.gates.size():
					var d := absf(f - float(walls.gates[k]))
					at_gate = at_gate or minf(d, walls.SAMPLES - d) <= walls.gate_half(k) + 0.5
				if not at_gate:
					bad += 1
	var inside_target: bool = walls.inside(target.x, target.y)
	var inside_start: bool = walls.inside(float(path[0].x), float(path[0].z))
	check(bad == 0, "%s: crosses the wall only through gates (%d crossings, target %s the wall)" % [label, crossings, "inside" if inside_target else "outside"])
	check(crossings == (0 if inside_target == inside_start else 1), "%s: no needless crossing of the wall" % label)

func fresh_state() -> void:
	game.accept(await game.request("state"))

func run() -> void:
	var mode := OS.get_environment("DRENOVAR_QA_MODE")
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var connected_ok: bool = await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.player_id.is_empty() and game.state.city.get("kingdom") is Dictionary, 60.0)
	check(connected_ok, "Connected to the local server")
	if not connected_ok:
		quit(1)
		return
	game.poll = 1.0e6
	await fresh_state()
	var target: Dictionary = game.state.encounters.filter(func(e): return int(e.level) == 1)[0]
	var soldiers_before := int(game.state.healthy.get("ENG-09", 0))
	var armies_before := armies().size()
	if mode == "wait":
		# Open the window while the creature rests at (-44,-44) (route open), press when it
		# has walked into the building's clearance (patrol phase > 5 s; it leaves at ~13 s).
		var offset: float = float(game.state.serverTime) - Time.get_unix_time_from_system() * 1000.0
		var phase := func() -> float: return fmod(Time.get_unix_time_from_system() * 1000.0 + offset - float(target.spawnedAt), 20000.0)
		check(await wait_until(func(): return phase.call() > 1200.0 and phase.call() < 2600.0, 25.0), "Waited for the creature to rest at its corner")
		check(await open_march(target), "March window opened from «Атаковать»")
		check(await wait_until(func(): return send_button().get_meta("route_ready", false), 3.0), "Route ready while the creature rests")
		check(await wait_until(func(): return phase.call() > 6500.0, 5.0), "Creature walked into the clearance")
	else:
		check(Vector2(float(target.position.x), float(target.position.z)).distance_to(Vector2(-40, -40)) < 0.01, "Fixture: Tenerys I stands next to the building on v1-33")
	if mode == "approach":
		check(not game.march_wall().is_empty(), "City wall stands (town hall III): the order carries the wall")
		# Creatures beyond the wall (server with the patch): the route preview leaves through a gate.
		for other in game.state.encounters.filter(func(e): return int(e.level) == 2):
			var preview: Dictionary = await game.send_request("march-preview", {"kind": "deploy", "encounterId": other.id, "units": {"ENG-09": 1}, "wall": game.march_wall()}, false, 5.0)
			if preview.has("path"):
				wall_route(preview.path, Vector2(float(other.position.x), float(other.position.z)), "Tenerys %d (preview)" % int(other.level))
			else:
				check(false, "Tenerys %d (preview): %s" % [int(other.level), preview.get("error", "")])
	if mode != "wait":
		check(await open_march(target), "March window opened from «Атаковать»")
	var send := send_button()
	check(not send.disabled, "Party can be sent at once")
	if mode == "wait":
		var refusals := [0]
		var watch := func():
			if game.last_command_error == BLOCKED:
				refusals[0] += 1
		send.pressed.emit()
		await process_frame
		check(send.text.begins_with("Выход через") and send.disabled, "Order held until the way is open (%s)" % send.text)
		check(quote().text.contains("главных ворот"), "Quote explains the wait: " + quote().text)
		var left: bool = await wait_until(func():
			watch.call()
			return armies().size() == armies_before + 1, 30.0)
		check(left, "The army left by itself when the creature walked out")
		check(refusals[0] == 0 and game.last_command_error != BLOCKED, "The server never refused the timed order")
		if left:
			check(armies().back().get("target", "") == target.id, "Army marches to Tenerys I")
			check(int(game.state.healthy.get("ENG-09", 0)) < soldiers_before, "Soldiers left the garrison")
			check(not game.modal.visible or game.modal_title.text != "Создать войско", "March window closed after the order")
		print("QA_MARCH_REFUSAL mode=", mode, " checks=", checks, " failures=", failures)
		quit(0 if failures == 0 else 1)
		return
	send.pressed.emit()
	await process_frame
	# With the clock frozen the client still expects the creature to walk on (the real
	# server's clock never stops), so it may hold the order for the predicted opening.
	check((send.text == "Отправляем…" or send.text.begins_with("Выход через") or send.text == "Ждём путь…") and send.disabled, "Button shows «Отправляем…», «Выход через N с» or, refused at once, «Ждём путь…» (%s)" % send.text)
	# A held order («Выход через N с») is sent at its moment; then it gets an answer.
	check(await wait_until(func(): return not send.text.begins_with("Выход через") and not send.text == "Отправляем…" and not game.command_in_progress, 30.0), "The order got an answer")
	await process_frame
	match mode:
		"refused":
			send = send_button()
			check(send.text == "Ждём путь…" and send.disabled, "Refused order waits for an open route (button: %s)" % send.text)
			check(game.modal_status.visible and game.modal_status.text.begins_with("Путь перекрыт постройкой"), "Status explains the wait: " + game.modal_status.text)
			check(await wait_until(func(): return quote().text.begins_with("Путь к цели перекрыт постройкой"), 5.0), "Route preview keeps asking: " + quote().text)
			check(armies().size() == armies_before and int(game.state.healthy.get("ENG-09", 0)) == soldiers_before, "No army, no soldiers lost while waiting")
			var gave_up: bool = await wait_until(func(): return quote().text == BLOCKED, 30.0)
			check(gave_up, "After one patrol round the refusal is shown (%s)" % quote().text)
			send = send_button()
			check(send.text == "Марш", "«Отправляем…»/«Ждём путь…» removed from the button (%s)" % send.text)
			check(not game.command_in_progress and game.queued_commands == 0, "No order left hanging")
			var retry := retry_button()
			check(retry != null and retry.visible, "«Повторить расчёт» offered")
			retry.pressed.emit()
			check(await wait_until(func(): return quote().text.begins_with("Путь к цели перекрыт постройкой"), 5.0), "«Повторить расчёт» asks the server again")
			# A new window cancels the wait; the button is usable at once.
			check(await open_march(target), "March window reopened for another attempt")
			send = send_button()
			check(not send.disabled and send.text == "Марш", "Send button usable on the new attempt")
			game.close_modal()
			await create_timer(3.0).timeout
			check(armies().size() == armies_before and not game.command_in_progress, "Closing the window stops the waiting")
		"wait":
			check(send_button().text == "Ждём путь…" and armies().size() == armies_before, "The server refused the order first (creature in the clearance)")
			var left: bool = await wait_until(func(): return armies().size() == armies_before + 1, 30.0)
			check(left, "The refused order left by itself once the creature walked out")
			if left:
				check(armies().back().get("target", "") == target.id, "Army marches to Tenerys I")
				check(int(game.state.healthy.get("ENG-09", 0)) < soldiers_before, "Soldiers left the garrison")
				check(not game.modal.visible or game.modal_title.text != "Создать войско", "March window closed after the order")
		_:
			var army_ok: bool = armies().size() == armies_before + 1 and armies().back().get("target", "") == target.id
			check(army_ok, "Army marched to Tenerys I next to the building")
			check(not game.modal.visible or game.modal_title.text != "Создать войско", "March window closed after the order")
			check(int(game.state.healthy.get("ENG-09", 0)) < soldiers_before, "Soldiers left the garrison")
			if army_ok:
				var path: Array = armies().back().get("path", [])
				wall_route(path, Vector2(-40, -40), "Tenerys I (order)")
				check(path.size() > 2 and Vector2(float(path.back().x), float(path.back().z)).distance_to(Vector2(-40, -40)) < 0.01, "Route ends at the creature")
	print("QA_MARCH_REFUSAL mode=", mode, " checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
