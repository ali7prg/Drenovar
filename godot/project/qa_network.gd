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
	# 1022 rule 10: failures are silent; 1024: the small dim «Связь…» first, the pill only after 20 s
	# without any 200 or 304.
	check(not game.connection_badge.visible, "Two quick failures already reported offline (notice is due only after 20 s)")
	game.last_ok_msec = Time.get_ticks_msec() - 10001
	game.update_connection_notice()
	check(not game.connection_badge.visible and game.link_hint.visible, "After 10 s only the quiet «Связь…» shows")
	game.last_ok_msec = Time.get_ticks_msec() - 20001
	game.update_connection_notice()
	check(game.connection_badge.visible and not game.link_hint.visible and game.message.text != game.OFFLINE_NOTICE, "Outage must show the small badge, not the centre message")
	check(game.connection_badge.text == game.OFFLINE_NOTICE, "A port that refuses connections reads «Нет связи»: " + game.connection_badge.text)
	check(not game.busy and not game.polling_state, "Failed request left the client busy")
	var started := Time.get_ticks_msec()
	var response: Dictionary = await game.request("command", {"type": "qa"})
	check(response.has("error") and Time.get_ticks_msec() - started < 13000, "Command did not fail cleanly")
	check(not game.busy, "Command failure left busy flag set")
	var events: Array = game.diagnostics.record.events.slice(logged_before).map(func(e): return e.kind)
	check(events.count("network_error") == 1, "Outage logged %d times" % events.count("network_error"))
	# 1024: a lost network is probed again within a few seconds (a failed connection costs the server
	# nothing); a failing server (5xx) is given room: base x 2^(n-1) up to 15 s.
	check(game.diagnostics.network_failures >= 3, "Failure counter not advanced")
	check(game.poll_interval() >= 1.5 * 0.85 and game.poll_interval() <= 5.0 * 1.15, "Lost network not probed quickly: %.2f s" % game.poll_interval())
	game.diagnostics.server_failures = 3
	check(game.poll_interval() > 4.0 and game.poll_interval() <= 15.0 * 1.15, "No backoff after server failures: %.2f s" % game.poll_interval())
	game.diagnostics.server_failures = 0
	game.diagnostics.network_result(true, "", Time.get_unix_time_from_system(), Time.get_ticks_msec())
	game.update_connection_notice()
	check(not game.connection_badge.visible, "Badge not hidden after recovery")
	check(game.diagnostics.record.events[-1].kind == "network_recovered", "Recovery not logged")
	DirAccess.remove_absolute(game.diagnostics.path)
	print("QA_NETWORK checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
