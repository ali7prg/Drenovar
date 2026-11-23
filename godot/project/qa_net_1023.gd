extends SceneTree
## 1023 network and forest-load rules in the real game scene against the synthetic V6 fixture with the
## adventure on and the town hall at III:
##   DRENOVAR_SERVER_ROOT=<server checkout> DRENOVAR_QA_CONDITIONAL=1 DRENOVAR_QA_ADVENTURE=1 DRENOVAR_QA_HALL=3 \
##     node godot/tools/qa-v6-1022-server.mjs
##   godot --headless --path godot/project -s qa_net_1023.gd -- --server=http://127.0.0.1:8799
## Checks:
## - the forest's layers load while a finger pans the city without pause (1022 waited for an idle
##   moment: nothing loaded while the player touched), the loading indicator shows and then hides,
##   and no frame of the load is longer than LONG_FRAME_MS (headless CPU here);
## - a long main-thread frame is not time without a connection: after a 9.5 s frame following one
##   failed request the pill stays hidden; real silence (10 s without a 200/304) still shows it;
## - the app's time in the background is not counted either; coming back drops the kept-alive
##   connections and asks for the state at once on a fresh one.

const ForestFlags = preload("res://src/forest_rescue/world/forest_flags.gd")
const LONG_FRAME_MS := 120.0
var game: Node
var checks := 0
var failures: Array[String] = []

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_NET_1023: " + detail)

func _initialize() -> void:
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func touch(index: int, position: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.position = position
	event.pressed = pressed
	root.push_input(event)

func drag(index: int, position: Vector2, relative: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = index
	event.position = position
	event.relative = relative
	root.push_input(event)

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while (game.scene_loading or not is_instance_valid(game.stage) or not game.launch_done) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(game.launch_done, "city interactive")
	# --- the forest loads while a finger pans the city without pause ---------------------------
	var finger := Vector2(683, 330)
	var direction := 1.0
	var next_finger := Time.get_ticks_msec() + 1100
	touch(0, finger, true)
	var started := Time.get_ticks_msec()
	var longest := 0.0
	var last := Time.get_ticks_usec()
	var indicator_seen := false
	var indicator_ratio := 0.0
	var gate_closed_frames := 0
	var frames_seen := 0
	deadline = Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		var now := Time.get_ticks_usec()
		var frame_ms := (now - last) / 1000.0
		last = now
		frames_seen += 1
		if frames_seen > 2:
			longest = maxf(longest, frame_ms)
		if not game.prewarm_may_continue():
			gate_closed_frames += 1
		var indicator: Variant = game.get("forest_progress")
		if indicator is Control and is_instance_valid(indicator) and indicator.visible:
			indicator_seen = true
			indicator_ratio = maxf(indicator_ratio, indicator.ratio)
		if Time.get_ticks_msec() >= next_finger:
			touch(0, finger, false)
			finger = Vector2(683, 330)
			touch(0, finger, true)
			next_finger = Time.get_ticks_msec() + 1100
			direction = -direction
		else:
			finger += Vector2(4.0 * direction, 0.0)
			drag(0, finger, Vector2(4.0 * direction, 0.0))
		if game.forest_game != null and str(game.stage.get("forest_attach_state")) == "attached":
			break
	touch(0, finger, false)
	var loaded_ms := Time.get_ticks_msec() - started
	check(game.forest_game != null, "forest game layer loaded while the finger panned (%d ms)" % loaded_ms)
	check(str(game.stage.get("forest_attach_state")) == "attached", "forest world layer attached while the finger panned: %s" % str(game.stage.get("forest_attach_state")))
	check(gate_closed_frames >= frames_seen * 0.9, "the finger kept the old idle gate closed (%d of %d frames)" % [gate_closed_frames, frames_seen])
	check(longest < LONG_FRAME_MS, "longest frame of the forest load while touching: %.1f ms" % longest)
	check(indicator_seen, "loading indicator shown while the forest loaded")
	await frames(40)
	var shown_after: Variant = game.get("forest_progress")
	check(not (shown_after is Control and shown_after.visible), "loading indicator hidden once the forest is ready")
	print("QA_NET_1023 forest_while_touching_ms=%d longest_frame_ms=%.1f indicator=%s ratio_max=%.2f" % [loaded_ms, longest, str(indicator_seen), indicator_ratio])
	# --- a long frame is not time without a connection ------------------------------------------
	deadline = Time.get_ticks_msec() + 20000
	while (game.player_id.is_empty() or game.showing_cached_state) and Time.get_ticks_msec() < deadline:
		await process_frame
	game.diagnostics.network_failures = 1
	game.last_ok_msec = Time.get_ticks_msec() - 2000
	OS.delay_msec(9500)
	await frames(2)
	game.diagnostics.network_failures = maxi(1, game.diagnostics.network_failures)
	game.update_connection_notice()
	check(not game.connection_badge.visible, "a 9.5 s frame after one failure showed «%s»" % game.connection_badge.text)
	# Real silence still shows the pill (the 1022 rule is kept).
	game.last_ok_msec = Time.get_ticks_msec() - 10001
	game.update_connection_notice()
	check(game.connection_badge.visible and game.connection_badge.text == game.OFFLINE_NOTICE, "10 s of real silence with a failure shows the pill")
	game.diagnostics.network_failures = 0
	game.last_ok_msec = Time.get_ticks_msec()
	game.update_connection_notice()
	check(not game.connection_badge.visible, "pill hidden after an answer")
	# --- the background is not counted; coming back starts on fresh connections ----------------
	while game.api.idle.is_empty() and Time.get_ticks_msec() < deadline + 10000:
		await process_frame
	check(not game.api.idle.is_empty(), "a kept-alive connection is idle before the pause")
	game.diagnostics.network_failures = 1
	game.last_ok_msec = Time.get_ticks_msec() - 3000
	game.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
	OS.delay_msec(11000)
	var total_before: int = game.api.requests_total
	var opened_before: int = game.api.connections_opened
	game.notification(Node.NOTIFICATION_APPLICATION_RESUMED)
	check(game.api.idle.is_empty(), "coming back closed the kept-alive connections")
	await frames(2)
	game.update_connection_notice()
	check(not game.connection_badge.visible, "11 s in the background after a failure showed «%s»" % game.connection_badge.text)
	deadline = Time.get_ticks_msec() + 3000
	while game.api.requests_total == total_before and Time.get_ticks_msec() < deadline:
		await process_frame
	check(game.api.requests_total > total_before, "the state is asked for at once after coming back")
	while game.api.connections_opened == opened_before and Time.get_ticks_msec() < deadline + 3000:
		await process_frame
	check(game.api.connections_opened > opened_before, "the first request after coming back opens a fresh connection")
	game.diagnostics.network_failures = 0
	print("QA_NET_1023 checks=%d failures=%d" % [checks, failures.size()])
	for failure in failures:
		print("  FAIL ", failure)
	game.queue_free()
	await frames(2)
	quit(0 if failures.is_empty() else 1)
