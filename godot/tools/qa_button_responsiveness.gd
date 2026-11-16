extends SceneTree

# Ordinary scene, synthetic authenticated HTTP fixture only. Measures software
# input dispatch, not display/input latency or performance on an iPhone.
var game
var checks := 0
var failures := []
var timings := []
var folder := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-dir="): folder = arg.trim_prefix("--qa-dir=")
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	print("BUTTON_CHECK ", label, " ", ok)
	if not ok: failures.append(label)

func wait_until(test: Callable, seconds := 60.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec() > end: return false
		await process_frame
	return true

func find_button(node: Node, title: String) -> Button:
	if node is Button and (node.text == title or str(node.get("caption")) == title): return node
	for child in node.get_children():
		var found := find_button(child, title)
		if found != null: return found
	return null

func tap(target: Button) -> void:
	if target == null:
		check(false, "button exists")
		return
	await process_frame
	await process_frame
	var at := target.get_global_rect().get_center()
	check(root.get_visible_rect().has_point(at), "touch target on canvas: " + str(target.get("caption") if target.text.is_empty() else target.text))
	for pressed in [true, false]:
		var event := InputEventScreenTouch.new()
		event.position = at
		event.pressed = pressed
		Input.parse_input_event(event)
		Input.flush_buffered_events()
		await process_frame
	await process_frame

func close_by_touch() -> void:
	await tap(find_button(game.modal_header, "×"))
	check(not game.modal.visible and not game.dimmer.visible, "close restores HUD and map input")
	check(Input.emulate_mouse_from_touch, "close restores native touch emulation")

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.single_scene = true
	root.add_child(game)
	if not await wait_until(func(): return is_instance_valid(game.stage) and not game.scene_loading and not game.busy):
		check(false, "normal game boots"); finish(); return
	if not game.endpoint.begins_with("http://127.0.0.1:"):
		check(false, "synthetic loopback only"); finish(); return
	await game.device_login()
	await game.create_settlement()
	await game.sync_account()
	check(game.v6_panels.enabled(), "synthetic V6 account loaded")
	# Disable background polls while checking interaction independently of server
	# response time. A slow foreground request is represented by busy=true.
	game.set_process(false)
	game.close_modal()
	for label in ["Меню", "Армия", "Строить", "Отчёты"]:
		game.busy = true
		var target := find_button(game.hud, label)
		var stamp := {"pressed":0}
		var observer := func(): stamp.pressed = Time.get_ticks_usec()
		if target != null: target.pressed.connect(observer, CONNECT_ONE_SHOT)
		var started := Time.get_ticks_usec()
		await tap(target)
		var elapsed := (Time.get_ticks_usec() - started) / 1000.0
		timings.append({"button":label,"touch_roundtrip_ms":elapsed,"pressed_signal":stamp.pressed>0,"title":game.modal_title.text})
		check(stamp.pressed > 0, label + " dispatches while a command is busy")
		check(game.modal.visible, label + " opens a panel")
		await close_by_touch()
		game.busy = false
	# A modal is opened and closed repeatedly without leaving an input blocker.
	for i in 4:
		await tap(find_button(game.hud, "Меню"))
		check(game.modal.visible and game.modal_title.text == "Меню", "menu reopens after previous close")
		await close_by_touch()
	var map_button := find_button(game.hud, "Карта")
	game.busy = true
	await tap(map_button)
	check(game.scene_loading or game.map_name == "world", "map starts despite a pending command")
	check(await wait_until(func(): return not game.scene_loading and game.map_name == "world"), "map opens")
	game.busy = false
	await tap(find_button(game.hud, "Город"))
	check(await wait_until(func(): return not game.scene_loading and game.map_name == "city"), "city returns")
	finish()

func finish() -> void:
	var data := {"checks":checks,"failures":failures,"timings":timings,"method":"Linux Godot 4.6.3 headless; real Input.parse_input_event touch; synthetic V6 fixture; busy flag held; no device latency claim"}
	print(JSON.stringify(data))
	if not folder.is_empty():
		DirAccess.make_dir_recursive_absolute(folder)
		var f := FileAccess.open(folder.path_join("buttons.json"), FileAccess.WRITE)
		f.store_string(JSON.stringify(data,"  "))
		f.close()
	if is_instance_valid(game): game.queue_free()
	await process_frame
	await process_frame
	await create_timer(.2).timeout
	quit(0 if failures.is_empty() else 1)
