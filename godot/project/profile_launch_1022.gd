extends SceneTree
## Launch profile, 1022 against 1021 (runs unchanged on both trees: copy it next to a 1021 checkout).
## Same launch as qa_instant_start: saved login + local city copy, server unreachable. Reports the launch
## time (city interactive), the main.tscn load, the frames before and after (max, p99, >50 ms), when the
## forest world layer became ready and, for frames over 33 ms, what the forest layers were doing.
##   godot --headless --path godot/project -s profile_launch_1022.gd [-- --cached=<state.json>] [--after=<ms>]
##   -- --capture=<server> --out=<file> with -- --server=<server>: save a fixture state for --cached
##      (an adventure-on state from qa-v6-1022-server.mjs DRENOVAR_QA_ADVENTURE=1)
## Headless CPU timings on a desktop, not iPhone 12.

const SessionStore = preload("res://src/session_store.gd")
var cached_path := ""
var capture := ""
var out_path := ""
var after_ms := 10000

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--cached="):
			cached_path = arg.trim_prefix("--cached=")
		elif arg.begins_with("--capture="):
			capture = arg.trim_prefix("--capture=")
		elif arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--after="):
			after_ms = int(arg.trim_prefix("--after="))
	call_deferred("run_capture" if not capture.is_empty() else "run")

func run_capture() -> void:
	root.size = Vector2i(1366, 630)
	SessionStore.forget()
	var game = load("res://main.tscn").instantiate()
	pass  # main.gd reads -- --server=<capture> itself (loopback realm)
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 120000
	while (game.player_id.is_empty() or not game.state.has("adventure")) and Time.get_ticks_msec() < deadline:
		await process_frame
	var state: Dictionary = game.state.duplicate(true)
	state.erase("__etag")
	var file := FileAccess.open(out_path, FileAccess.WRITE)
	file.store_string(JSON.stringify(state))
	file.close()
	print("CAPTURED adventure=", state.has("adventure"), " keys=", state.keys().size())
	SessionStore.forget()
	quit(0)

func cached_state() -> Dictionary:
	if not cached_path.is_empty():
		var parsed: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(cached_path))
		parsed.playerId = "qa-instant-player"
		return parsed
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var game_state: Dictionary = data.demo.duplicate(true)
	game_state.playerId = "qa-instant-player"
	return game_state

static func stats(frames: Array) -> Dictionary:
	if frames.is_empty():
		return {"n": 0, "max": 0.0, "p99": 0.0, "over50": 0}
	var sorted := frames.duplicate()
	sorted.sort()
	var p99: float = sorted[mini(sorted.size() - 1, int(ceil(sorted.size() * 0.99)) - 1)]
	return {"n": frames.size(), "max": snappedf(sorted[-1], 0.1), "p99": snappedf(p99, 0.1),
		"over50": frames.filter(func(f): return f > 50.0).size()}

func run() -> void:
	root.size = Vector2i(1366, 630)
	SessionStore.forget()
	var token := "c".repeat(64) + "." + "d".repeat(64)
	SessionStore.save_session(token)
	SessionStore.save_state(token, cached_state(), 1234.0, "http://127.0.0.1:9")
	var started := Time.get_ticks_msec()
	var t := Time.get_ticks_usec()
	var packed: PackedScene = load("res://main.tscn")
	var load_ms := (Time.get_ticks_usec() - t) / 1000.0
	t = Time.get_ticks_usec()
	var game = packed.instantiate()
	var instantiate_ms := (Time.get_ticks_usec() - t) / 1000.0
	game.endpoint = "http://127.0.0.1:9"
	t = Time.get_ticks_usec()
	root.add_child(game)
	var ready_sync_ms := (Time.get_ticks_usec() - t) / 1000.0
	var before: Array = []
	var last := Time.get_ticks_usec()
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
		var now := Time.get_ticks_usec()
		before.append((now - last) / 1000.0)
		last = now
	await process_frame
	var launch_ms := Time.get_ticks_msec() - started
	last = Time.get_ticks_usec()
	var interactive: Array = []
	var long_frames: Array = []
	var flags: Variant = load("res://src/forest_rescue/world/forest_flags.gd") if ResourceLoader.exists("res://src/forest_rescue/world/forest_flags.gd") else null
	var label := ""
	var forest_ready_ms := -1
	var until := Time.get_ticks_msec() + after_ms
	while Time.get_ticks_msec() < until:
		await process_frame
		var now := Time.get_ticks_usec()
		var frame_ms := (now - last) / 1000.0
		interactive.append(frame_ms)
		last = now
		if frame_ms > 33.0:
			long_frames.append([snappedf(frame_ms, 0.1), label + " end@" + str(Time.get_ticks_msec())])
		# what this frame is about to run (read after it, attributed to the next long frame)
		var wn: Node = game.stage.find_child("ForestWorld", false, false) if is_instance_valid(game.stage) else null
		label = "%s|%s|%s|%s" % [str(game.stage.get("forest_attach_state")) if is_instance_valid(game.stage) else "",
			str(wn.get("setup_stage")) if wn != null else "", str(flags.staged_last) if flags != null else "",
			"gameload" if game.get("forest_game_loading") == true else ""]
		if forest_ready_ms < 0 and is_instance_valid(game.stage):
			var world: Variant = game.stage.get("forest_world")
			if world is Node and is_instance_valid(world) and world.get("_ready_emitted") == true:
				forest_ready_ms = Time.get_ticks_msec() - started
	var world_node: Variant = game.stage.get("forest_world") if is_instance_valid(game.stage) else null
	var forest_game: Variant = game.get("forest_game")
	var report := {
		"launch_ms": launch_ms,
		"load_ms": snappedf(load_ms, 0.1), "instantiate_ms": snappedf(instantiate_ms, 0.1), "ready_sync_ms": snappedf(ready_sync_ms, 0.1),
		"scene_ms": game.get("last_scene_ms"),
		"before_launch": stats(before),
		"interactive": stats(interactive),
		"forest_world": world_node is Node and is_instance_valid(world_node),
		"forest_ready_ms": forest_ready_ms,
		"adventure_known": forest_game != null and forest_game.client.known,
		"city_shown": str(game.state.get("playerId", "")) == "qa-instant-player",
	}
	print("PROFILE_LAUNCH ", JSON.stringify(report))
	for f in long_frames:
		print("LONG_FRAME ", f[0], " ", f[1])
	game.queue_free()
	await process_frame
	SessionStore.forget()
	quit(0)
