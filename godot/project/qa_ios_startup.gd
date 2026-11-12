extends SceneTree

const Store = preload("res://src/session_store.gd")
var failures := 0
var checks := 0

func _initialize() -> void:
	call_deferred("run")

func check(value: bool, description: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(description)

func touch(index: int, at: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.position = at
	event.pressed = pressed
	root.push_input(event, true)

func check_panel(game: Node) -> void:
	var emulation := Input.emulate_mouse_from_touch
	game.open_modal("Прокрутка")
	var taps := [0]
	var first: Button
	for i in 25:
		var entry: Button = game.button(game.modal_body, "Строка %d" % (i + 1), func(): taps[0] += 1)
		if i == 0:
			first = entry
	await process_frame
	await process_frame
	var scroll: ScrollContainer = game.modal_scroll
	check(not Input.emulate_mouse_from_touch, "Modal must own its touch gestures")
	check(scroll.get_v_scroll_bar().max_value > scroll.get_v_scroll_bar().page, "Test panel must overflow")
	var start := first.get_global_rect().get_center()
	var end := start - Vector2(0, 170)
	var previous_target: Vector3 = game.stage.target
	touch(0, start, true)
	var drag := InputEventScreenDrag.new()
	drag.index = 0
	drag.position = end
	drag.relative = end - start
	root.push_input(drag, true)
	touch(0, end, false)
	await process_frame
	check(scroll.scroll_vertical >= 160, "Dragging on a button did not scroll the panel")
	check(taps[0] == 0, "Scrolling activated a button")
	check(game.stage.target == previous_target, "Panel gesture moved the camera")
	start = scroll.get_global_rect().get_center()
	end = start + Vector2(0, 180)
	touch(0, start, true)
	drag.position = end
	drag.relative = end - start
	root.push_input(drag, true)
	touch(0, end, false)
	await process_frame
	check(scroll.scroll_vertical == 0, "Reverse finger drag did not scroll back to the start")
	start = first.get_global_rect().get_center()
	touch(0, start, true)
	touch(0, start, false)
	await process_frame
	check(taps[0] == 1, "Finger tap did not activate the button")
	game.close_modal()
	check(Input.emulate_mouse_from_touch == emulation, "Closing the panel changed touch settings")

func run() -> void:
	root.size = Vector2i(1366, 630)
	var scenario := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--case="):
			scenario = arg.trim_prefix("--case=")
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:8426"
	root.add_child(game)
	# The native splash is present before game assets and account data load.
	check(game.get_children().any(func(node): return node is CanvasLayer and node.layer == 10), "Launch layer is missing")
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	await process_frame
	game.set_process(false)
	check(not game.get_children().any(func(node): return node is CanvasLayer and node.layer == 10), "Launch layer blocked a ready city")
	match scenario:
		"login":
			check(Store.read_session().is_empty(), "Login case started with a persisted session")
			game.login_proof = "a".repeat(64)
			game.login_deadline = Time.get_ticks_msec() + 5000
			await game.finish_login(true)
			check(game.player_id == "native-qa-player", "Native sign-in did not load the settlement")
			check(Store.valid(Store.read_session()), "Successful login did not persist the token")
			check(FileAccess.get_file_as_bytes(Store.SESSION_PATH).size() > 0, "Encrypted session file missing")
			var stored_bytes := FileAccess.get_file_as_bytes(Store.SESSION_PATH)
			check(not stored_bytes.hex_encode().contains(game.session.to_utf8_buffer().hex_encode()), "Raw token is visible in the stored file")
			await check_panel(game)
		"restore":
			check(game.player_id == "native-qa-player" and not game.restoring_session, "Cold launch did not restore account")
			check(Store.valid(Store.read_session()), "Restored token disappeared")
		"offline":
			check(game.restoring_session and game.player_id.is_empty(), "Temporary failure should leave restoration pending")
			check(Store.valid(Store.read_session()), "Temporary failure erased login")
		"expired":
			check(game.player_id.is_empty() and game.session.is_empty(), "Expired session remained connected")
			check(Store.read_session().is_empty(), "Expired session was not removed")
		"logout":
			check(game.player_id == "native-qa-player", "Logout case did not restore account")
			await game.sign_out()
			check(game.session.is_empty() and Store.read_session().is_empty(), "Sign out did not clear the saved session")
		_:
			check(false, "Expected a QA scenario")
	print("QA_IOS_STARTUP ", scenario, " checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
