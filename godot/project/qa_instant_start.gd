extends SceneTree

# Saved login + local copy of the city: the app opens the player's own city at
# launch without waiting for the server (here the server is unreachable), shows
# no centre "reconnecting" message, and keeps retrying quickly in the background.
# A copy written by another login is never shown.

const SessionStore = preload("res://src/session_store.gd")
var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func cached_state() -> Dictionary:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var game_state: Dictionary = data.demo.duplicate(true)
	game_state.playerId = "qa-instant-player"
	game_state.city.progress.wood = 98765
	return game_state

func launch() -> Node:
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	return game

func run() -> void:
	root.size = Vector2i(1366, 630)
	SessionStore.forget()
	var token := "c".repeat(64) + "." + "d".repeat(64)
	check(SessionStore.save_session(token) == OK, "Session save failed")
	check(SessionStore.save_state(token, cached_state(), 1234.0) == OK, "State save failed")
	check(SessionStore.read_state("e".repeat(64) + "." + "f".repeat(64)).is_empty(), "Another login read this copy")
	var started := Time.get_ticks_msec()
	var game = launch()
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	await process_frame
	var elapsed := Time.get_ticks_msec() - started
	check(str(game.state.playerId) == "qa-instant-player", "Saved city not shown at launch")
	check(game.balance("wood") == 98765, "Saved resources not shown: %d" % game.balance("wood"))
	check(not game.message.text.begins_with("Подключаемся"), "Centre message shown with a saved city: " + game.message.text)
	check(not game.get_children().any(func(n): return n is CanvasLayer and n.layer == 10 and n.visible and n.get_child(0).visible and n.get_child(0).modulate.a > 0.99),
		"Launch screen still covering the city")
	# Background retries: the server is down, the restore keeps going at ~1.5 s.
	check(game.restoring_session, "Restore stopped after a failed first answer")
	var polls_before: int = game.api.requests_total
	var until := Time.get_ticks_msec() + 4500
	while Time.get_ticks_msec() < until:
		await process_frame
	check(game.api.requests_total - polls_before >= 2, "Background retries too slow: %d in 4.5 s" % (game.api.requests_total - polls_before))
	check(not game.busy, "Background restore blocked commands")
	check(not game.message.text.contains("Нет связи"), "Centre offline message shown")
	print("QA_INSTANT_START checks=%d failures=%d launch_ms=%d" % [checks, failures, elapsed])
	game.queue_free()
	await process_frame
	SessionStore.forget()
	quit(0 if failures == 0 else 1)
