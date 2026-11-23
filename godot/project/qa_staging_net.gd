extends SceneTree
## The real game client against a hosted staging Worker over the real Cloudflare network, with every
## request logged (method, path, start, duration, result, HTTP status, connection reused or opened),
## the connection pill, long main-thread frames and the forest's lazy load milestones.
##   godot --headless --path godot/project -s qa_staging_net.gd -- --server=https://<staging> \
##     --qa-https-proxy=127.0.0.1:<relay> --qa-ca-file=<proxy CA> --qa-net-trace \
##     --session-file=<file holding the synthetic staging device's 64 hex secret> [--relay-pid=<pid>] \
##     [--scenario=idle|touch] [--gap=<s>] [--freeze] [--minutes=<m>] [--out=<json>]
## The session file is read, never printed; the saved session is forgotten at the end.
## Timeline after the city is interactive:
##   0 s        forest lazy load starts; --scenario=touch pans the camera with a finger without pause
##              (a drag every frame, a new finger every 1.2 s) until the forest is ready or 90 s;
##   +settle    polls at rest for 40 s;
##   --gap=N    the main thread stops for N s with no request in flight (the app in the background),
##              then NOTIFICATION_APPLICATION_RESUMED; the next 30 s are logged;
##   --freeze   the relay (qa-freeze-relay.py, SIGUSR1) turns every open connection into a dead one
##              (a network change or a NAT timeout); the next 45 s are logged.
## Headless CPU timings on a desktop container, not an iPhone 12.

const SessionStore = preload("res://src/session_store.gd")
const ForestFlags = preload("res://src/forest_rescue/world/forest_flags.gd")

var game: Node
var t0 := 0
var events: Array = []
var long_frames: Array = []
var frame_ms: Array = []
var label := ""
var badge_visible := false
var scenario := "idle"
var gap_s := 0
var freeze := false
var relay_pid := 0
var out_path := ""
var minutes := 0.0
var milestones := {}
var touching := false
var finger_down := false
var finger_pos := Vector2(700, 330)
var finger_dir := 1.0
var next_finger_ms := 0

func now() -> int:
	return Time.get_ticks_msec() - t0

func note(kind: String, detail := {}) -> void:
	var entry := {"t": now(), "event": kind}
	entry.merge(detail)
	events.append(entry)
	print("EVENT ", JSON.stringify(entry))

func milestone(key: String) -> void:
	if not milestones.has(key):
		milestones[key] = now()
		note("milestone", {"what": key})

func _initialize() -> void:
	var session_file := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--session-file="):
			session_file = arg.trim_prefix("--session-file=")
		elif arg.begins_with("--scenario="):
			scenario = arg.trim_prefix("--scenario=")
		elif arg.begins_with("--gap="):
			gap_s = int(arg.trim_prefix("--gap="))
		elif arg == "--freeze":
			freeze = true
		elif arg.begins_with("--relay-pid="):
			relay_pid = int(arg.trim_prefix("--relay-pid="))
		elif arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--minutes="):
			minutes = float(arg.trim_prefix("--minutes="))
	var secret := FileAccess.get_file_as_string(session_file).strip_edges()
	var token := SessionStore.DEVICE_PREFIX + secret
	if not SessionStore.valid(token):
		print("QA_STAGING_NET no valid device session in the session file")
		quit(2)
		return
	SessionStore.forget()
	SessionStore.save_session(token)
	secret = ""
	token = ""
	call_deferred("run")

func _process(_delta: float) -> bool:
	if game == null or not is_instance_valid(game):
		return false
	var ms := Time.get_ticks_usec()
	if has_meta("last_us"):
		var elapsed := (ms - int(get_meta("last_us"))) / 1000.0
		frame_ms.append(elapsed)
		if elapsed > 50.0:
			long_frames.append({"t": now(), "ms": snappedf(elapsed, 0.1), "during": label})
	set_meta("last_us", ms)
	var badge: Variant = game.get("connection_badge")
	var visible: bool = badge is Control and is_instance_valid(badge) and badge.visible
	if visible != badge_visible:
		badge_visible = visible
		note("pill_shown" if visible else "pill_hidden", {"text": str(badge.text) if badge is Label else ""})
	var stage: Variant = game.get("stage")
	var world: Variant = stage.get("forest_world") if stage is Node and is_instance_valid(stage) else null
	label = "%s|%s|%s|%s" % [str(stage.get("forest_attach_state")) if stage is Node and is_instance_valid(stage) else "",
		str(world.get("setup_stage")) if world is Node and is_instance_valid(world) else "", ForestFlags.staged_last,
		"gameload" if game.get("forest_game_loading") == true else ""]
	if game.get("forest_game_loading") == true:
		milestone("forest_game_loading")
	if game.get("forest_game") != null:
		milestone("forest_game_ready")
	if stage is Node and is_instance_valid(stage) and str(stage.get("forest_attach_state")) == "attaching":
		milestone("world_attaching")
	if world is Node and is_instance_valid(world) and world.get("_ready_emitted") == true:
		milestone("world_ready")
	if touching:
		touch_step()
	return false

func touch_step() -> void:
	var t := Time.get_ticks_msec()
	if not finger_down or t >= next_finger_ms:
		if finger_down:
			var up := InputEventScreenTouch.new()
			up.index = 0
			up.position = finger_pos
			up.pressed = false
			root.push_input(up)
		finger_pos = Vector2(700, 330)
		var down := InputEventScreenTouch.new()
		down.index = 0
		down.position = finger_pos
		down.pressed = true
		root.push_input(down)
		finger_down = true
		next_finger_ms = t + 1200
		finger_dir = -finger_dir
		return
	var drag := InputEventScreenDrag.new()
	drag.index = 0
	drag.relative = Vector2(3.0 * finger_dir, 0.0)
	finger_pos += drag.relative
	drag.position = finger_pos
	root.push_input(drag)

func stop_touch() -> void:
	touching = false
	if finger_down:
		var up := InputEventScreenTouch.new()
		up.index = 0
		up.position = finger_pos
		up.pressed = false
		root.push_input(up)
		finger_down = false

func wait_ms(ms: int) -> void:
	var until := Time.get_ticks_msec() + ms
	while Time.get_ticks_msec() < until:
		await process_frame

func wait_idle_network(ms: int) -> void:
	var until := Time.get_ticks_msec() + ms
	while Time.get_ticks_msec() < until and (game.api.threads.size() > 0 or game.polls_in_flight > 0):
		await process_frame

func run() -> void:
	root.size = Vector2i(1366, 630)
	t0 = Time.get_ticks_msec()
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	game.api.trace_all = true
	while game.scene_loading or not is_instance_valid(game.stage) or not game.launch_done:
		await process_frame
	milestone("city_interactive")
	var deadline := Time.get_ticks_msec() + 30000
	while (game.player_id.is_empty() or game.showing_cached_state) and Time.get_ticks_msec() < deadline:
		await process_frame
	milestone("server_state")
	note("adventure", {"offered": game.adventure_offered(game.state)})
	if scenario == "touch":
		touching = true
		note("touch_start")
	var forest_until := Time.get_ticks_msec() + 90000
	while not milestones.has("world_ready") and Time.get_ticks_msec() < forest_until:
		await process_frame
	if touching:
		stop_touch()
		note("touch_stop")
	await wait_ms(40000)
	if gap_s > 0:
		await wait_idle_network(15000)
		note("suspend", {"seconds": gap_s, "in_flight": game.api.threads.size()})
		game.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
		OS.delay_msec(gap_s * 1000)
		set_meta("last_us", Time.get_ticks_usec())
		game.notification(Node.NOTIFICATION_APPLICATION_RESUMED)
		note("resume")
		await wait_ms(30000)
	if freeze and relay_pid > 0:
		await wait_idle_network(15000)
		OS.execute("kill", ["-USR1", str(relay_pid)])
		note("freeze")
		await wait_ms(45000)
	if minutes > 0.0:
		await wait_ms(int(minutes * 60000.0))
	finish()

static func percentile(values: Array, q: float) -> float:
	if values.is_empty():
		return 0.0
	var sorted := values.duplicate()
	sorted.sort()
	return sorted[mini(sorted.size() - 1, int(ceil(sorted.size() * q)) - 1)]

func finish() -> void:
	var trace: Array = game.api.trace
	var by_status := {}
	var ok_ms: Array = []
	for entry: Dictionary in trace:
		var key := "%s %s" % [entry.result, entry.code]
		by_status[key] = int(by_status.get(key, 0)) + 1
		if int(entry.result) == 0:
			ok_ms.append(float(entry.ms))
	var report := {
		"scenario": scenario, "gap_s": gap_s, "freeze": freeze, "t0_ticks": t0,
		"requests": trace.size(), "by_result_code": by_status,
		"ok_ms_p50": percentile(ok_ms, 0.5), "ok_ms_p95": percentile(ok_ms, 0.95), "ok_ms_max": percentile(ok_ms, 1.0),
		"opened": game.api.connections_opened, "reused": game.api.requests_reused,
		"full_polls": game.full_polls, "not_modified_polls": game.not_modified_polls,
		"milestones": milestones, "frames": frame_ms.size(), "long_frames_over50": long_frames.size(),
		"frame_p99": percentile(frame_ms, 0.99), "frame_max": percentile(frame_ms, 1.0),
		"network_failures_end": game.diagnostics.network_failures,
	}
	print("QA_STAGING_NET ", JSON.stringify(report))
	for entry: Dictionary in trace:
		print("REQ ", JSON.stringify(entry))
	for f in long_frames:
		print("LONG ", JSON.stringify(f))
	if not out_path.is_empty():
		var file := FileAccess.open(out_path, FileAccess.WRITE)
		file.store_string(JSON.stringify({"report": report, "requests": trace, "events": events, "long_frames": long_frames}, " "))
		file.close()
	SessionStore.forget()
	game.queue_free()
	await process_frame
	quit(0)
