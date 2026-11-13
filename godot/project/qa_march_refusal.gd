extends SceneTree

# City march to a creature next to a building, against the real server
# (godot/tools/test-realm.mjs with DRENOVAR_TEST_BLOCKED_CREATURE=1). Run with:
#   -- --server=http://127.0.0.1:8417
# DRENOVAR_QA_EXPECT_REFUSAL=1 (server v92 without the route-approach patch):
#   the server refuses the route; «Отправляем…» goes away, the refusal is shown,
#   the button is usable again and a second attempt is possible (no army, no
#   soldiers lost, no stuck order).
# Without it (server with the route-approach patch): the march leaves at once.

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

func open_march(target: Dictionary) -> bool:
	game.inspect_encounter(target)
	var attack := game.modal_footer.get_child(0) as Button
	if attack == null or attack.text != "Атаковать":
		return false
	attack.pressed.emit()
	return await wait_until(func(): return game.modal_title.text == "Создать войско" and send_button() != null, 5.0)

func retry_button() -> Button:
	for button: Button in game.modal_body.find_children("*", "Button", true, false):
		if button.text == "Повторить расчёт":
			return button
	return null

func run() -> void:
	var expect_refusal := OS.get_environment("DRENOVAR_QA_EXPECT_REFUSAL") == "1"
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var connected_ok: bool = await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.player_id.is_empty() and game.state.city.get("kingdom") is Dictionary, 60.0)
	check(connected_ok, "Connected to the local server")
	if not connected_ok:
		quit(1)
		return
	game.poll = 1.0e6
	var target: Dictionary = game.state.encounters.filter(func(e): return int(e.level) == 1)[0]
	check(Vector2(float(target.position.x), float(target.position.z)).distance_to(Vector2(-40, -40)) < 0.01, "Fixture: Tenerys I stands next to the building on v1-33")
	var soldiers_before := int(game.state.healthy.get("ENG-09", 0))
	var armies_before: int = game.state.get("armies", []).size()
	check(await open_march(target), "March window opened from «Атаковать»")
	var send := send_button()
	# Press at once, before the route preview answers (the order goes without it).
	check(not send.disabled, "Party can be sent at once")
	send.pressed.emit()
	await process_frame
	check(send.text == "Отправляем…" and send.disabled, "Button shows «Отправляем…» while the order is on its way")
	var settled: bool = await wait_until(func(): return not game.command_in_progress, 20.0)
	check(settled, "The order got an answer")
	await process_frame
	if expect_refusal:
		check(game.modal.visible and game.modal_title.text == "Создать войско", "Window stays open after the refusal")
		send = send_button()
		check(send.text == "Марш", "«Отправляем…» removed from the button after the refusal (text: %s)" % send.text)
		check(game.modal_status.text != "Отправляем…", "«Отправляем…» removed from the status line")
		check(game.modal_status.visible and game.modal_status.text == "Нет безопасного пути к цели", "Refusal shown: " + game.modal_status.text)
		check(game.state.get("armies", []).size() == armies_before, "No army created by the refused order")
		check(int(game.state.healthy.get("ENG-09", 0)) == soldiers_before, "No soldiers lost")
		var quote := game.modal_body.find_child("MarchQuote", true, false) as Label
		var preview_done: bool = await wait_until(func(): return quote.text == "Нет безопасного пути к цели", 8.0)
		check(preview_done, "Route preview shows the refusal (%s)" % quote.text)
		var retry := retry_button()
		check(retry != null and retry.visible, "«Повторить расчёт» offered after the refused route")
		# A second attempt: the button is usable again when the preview has not refused yet,
		# otherwise «Повторить расчёт» asks the server again; both must end cleanly.
		retry.pressed.emit()
		await wait_until(func(): return quote.text != "Нет безопасного пути к цели", 3.0)
		var answered: bool = await wait_until(func(): return quote.text == "Нет безопасного пути к цели", 8.0)
		check(answered and retry.visible, "Second route attempt answered by the server")
		# The order itself once more, with a fresh window (the preview no longer disables it).
		check(await open_march(target), "March window reopened for another attempt")
		send = send_button()
		check(not send.disabled, "Send button usable on the new attempt")
		send.pressed.emit()
		await wait_until(func(): return not game.command_in_progress, 20.0)
		await process_frame
		send = send_button()
		check(send != null and send.text == "Марш" and game.modal_status.text == "Нет безопасного пути к цели", "Second order refused cleanly, button reset")
		check(not game.command_in_progress and game.queued_commands == 0, "No order left hanging")
	else:
		var armies: Array = game.state.get("armies", [])
		var army_ok: bool = armies.size() == armies_before + 1 and armies.back().get("target", "") == target.id
		check(army_ok, "Army marched to Tenerys I next to the building")
		check(not game.modal.visible or game.modal_title.text != "Создать войско", "March window closed after the order")
		check(int(game.state.healthy.get("ENG-09", 0)) < soldiers_before, "Soldiers left the garrison")
		if army_ok:
			var path: Array = armies.back().get("path", [])
			check(path.size() > 2 and Vector2(float(path.back().x), float(path.back().z)).distance_to(Vector2(-40, -40)) < 0.01, "Route ends at the creature")
	print("QA_MARCH_REFUSAL expect_refusal=", expect_refusal, " checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
