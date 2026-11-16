extends SceneTree

var failures := []
var checks := 0
func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	var game = load("res://main.tscn").instantiate()
	game.single_scene = true
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage): await process_frame
	game.set_process(false)
	check(game.endpoint.begins_with("http://127.0.0.1:"), "loopback only")
	for i in 2:
		var response: Dictionary = await game.send_request("qa-status/503", null, false)
		check(response.get("httpStatus") == 503, "HTML 503 retains status for bounded retry")
		check(not response.get("transportFailure", false), "reachable server is not offline")
	check(game.diagnostics.network_failures == 0, "no false network failures")
	check(game.connection_badge.visible and game.connection_badge.text == "Ошибка сервера · повторяем", "correct error badge")
	check(not game.busy and not game.polling_state, "no stuck request")
	await game.send_request("qa-status/200", null, false)
	check(not game.connection_badge.visible, "badge clears on recovery")
	var kinds: Array = game.diagnostics.record.events.map(func(e): return e.kind)
	check(kinds.count("server_error") == 1 and kinds.count("server_recovered") == 1, "one incident and recovery")
	game.queue_free()
	await process_frame
	print(JSON.stringify({"checks":checks,"failures":failures,"method":"real local HTTP 503 HTML, then 200; no device acceptance"}))
	quit(0 if failures.is_empty() else 1)
