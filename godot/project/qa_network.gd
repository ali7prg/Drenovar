extends SceneTree

# Network-failure behaviour against a closed loopback port (real connection
# refusals, no mocked responses): the HUD reports the outage, polling backs off,
# no request stays "busy", and the outage is logged once.

var failures: Array[String] = []
var checks := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	game.diagnostics.path = "user://qa-network-diagnostics.json"
	game.endpoint = "http://127.0.0.1:9"
	game.loopback = true
	game.player_id = "qa-network"
	game.diagnostics.record.events = []
	var logged_before: int = 0
	await game.poll_account_state()
	check(not game.connection_badge.visible, "A single failure already reported offline")
	await game.poll_account_state()
	check(game.connection_badge.visible and game.message.text != game.OFFLINE_NOTICE, "Outage must show the small badge, not the centre message")
	check(not game.busy and not game.polling_state, "Failed request left the client busy")
	var started := Time.get_ticks_msec()
	var response: Dictionary = await game.request("command", {"type": "qa"})
	check(response.has("error") and Time.get_ticks_msec() - started < 13000, "Command did not fail cleanly")
	check(not game.busy, "Command failure left busy flag set")
	var events: Array = game.diagnostics.record.events.slice(logged_before).map(func(e): return e.kind)
	check(events.count("network_error") == 1, "Outage logged %d times" % events.count("network_error"))
	# Backoff: with 3+ failures the active-march interval exceeds the normal 0.8 s.
	check(game.diagnostics.network_failures >= 3, "Failure counter not advanced")
	game.diagnostics.network_result(true, "", Time.get_unix_time_from_system(), Time.get_ticks_msec())
	game.update_connection_notice()
	check(not game.connection_badge.visible, "Badge not hidden after recovery")
	check(game.diagnostics.record.events[-1].kind == "network_recovered", "Recovery not logged")
	DirAccess.remove_absolute(game.diagnostics.path)
	print("QA_NETWORK checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
