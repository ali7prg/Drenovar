extends SceneTree
## Stills of the game windows for the premium UI work (ui_premium/), rendered (not headless)
## against the synthetic V6 fixture (godot/tools/qa-v6-1022-server.mjs, port 8799):
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s qa_ui_premium_shots.gd -- --server=http://127.0.0.1:8799 --shots=/abs/dir [--prefix=after_]
##     [--size=1366x630] [--only=build,inspect]
## Saves PNGs named <prefix><window>.png and prints UI_PREMIUM_SHOTS with the list and the
## main-thread time each window took to open (call + first frame).
## Windows: city, menu, build, inspect, upgrade, recruit, queues, speedups, army, reports,
## account, economy, trade, report (one battle report when the fixture has one).

var game: Node
var shots_dir := "user://ui_premium_shots"
var prefix := ""
var only: PackedStringArray = []
var view_size := Vector2i(1366, 630)
var saved: Array = []
var timings := {}
var fast := false

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots_dir = arg.trim_prefix("--shots=")
		elif arg.begins_with("--prefix="):
			prefix = arg.trim_prefix("--prefix=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",")
		elif arg == "--fast":
			# Iteration only: no 3D world under full-screen windows (renders much faster).
			fast = true
		elif arg.begins_with("--size="):
			var parts := arg.trim_prefix("--size=").split("x")
			view_size = Vector2i(int(parts[0]), int(parts[1]))
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func wanted(name: String) -> bool:
	return only.is_empty() or name in only

func shot(name: String) -> void:
	await frames(14)
	var dir := ProjectSettings.globalize_path(shots_dir)
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_texture().get_image().save_png(dir.path_join(prefix + name + ".png"))
	saved.append(name)
	print("SHOT ", name)

func wait_until(condition: Callable, seconds := 8.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call():
			return true
		await process_frame
	return false

# Opens a window and records the synchronous call time plus the frame after it.
func timed(name: String, open: Callable) -> void:
	var started := Time.get_ticks_usec()
	open.call()
	var call_ms := (Time.get_ticks_usec() - started) / 1000.0
	await process_frame
	timings[name] = {"call_ms": snappedf(call_ms, 0.01), "with_frame_ms": snappedf((Time.get_ticks_usec() - started) / 1000.0, 0.01)}

func body_text() -> String:
	var parts: PackedStringArray = []
	for label: Label in game.modal_body.find_children("*", "Label", true, false):
		parts.append(label.text)
	for item: Button in game.modal_body.find_children("*", "Button", true, false):
		parts.append(item.text)
	return " | ".join(parts)

func run() -> void:
	root.size = view_size
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 240000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	await wait_until(func(): return game.v6_panels.enabled(), 30.0)
	await frames(90)
	if game.modal.visible:
		game.close_modal()
	# Catalogue once, so the timed opens below measure the windows, not the network.
	await game.v6_panels.load_catalogue()
	await frames(10)
	if fast:
		game.stage.visible = false
	if wanted("city"):
		await shot("city")
	if wanted("menu"):
		await timed("menu", game.show_controls_menu)
		await shot("menu")
	if wanted("build"):
		await timed("build", game.show_build_menu)
		await wait_until(func(): return game.modal_title.text == "Строительство")
		await shot("build")
	if wanted("inspect"):
		await timed("inspect", func(): game.v6_panels.inspect("B01"))
		await wait_until(func(): return game.modal.visible and not game.modal_title.text.is_empty())
		await shot("inspect")
	var order := {}
	if wanted("upgrade") or wanted("queues") or wanted("speedups"):
		# The first affordable upgrade among a few cheap buildings.
		for type in ["B06", "B07", "B22", "B01", "B08", "B11"]:
			var current: Dictionary = game.v6_panels.building(type)
			if current.is_empty():
				continue
			game.v6_panels.confirm({"kind":"construction", "building":type, "target":int(current.level) + 1})
			await wait_until(func(): return game.modal_footer.visible or "Повторить" in body_text() or game.modal_body.get_child_count() > 1 and not "Рассчитываем" in body_text(), 10.0)
			await frames(4)
			if game.modal_footer.visible:
				break
		if wanted("upgrade"):
			await shot("upgrade")
		if game.modal_footer.visible:
			var start: Button = game.modal_footer.find_children("*", "Button", true, false)[0]
			start.pressed.emit()
			await wait_until(func(): return game.modal_title.text == "Очереди поселения" and not game.command_in_progress, 15.0)
			for item: Dictionary in game.state.v6.orders:
				if item.status == "pending":
					order = item
	if wanted("queues"):
		await timed("queues", game.v6_panels.queues)
		await shot("queues")
	if wanted("speedups") and not order.is_empty():
		# Display only: a few items in the local inventory so the list is not empty.
		if not game.state.has("items") or not game.state.items is Dictionary:
			game.state.items = {}
		for index in [1, 2, 3, 5]:
			game.state.items["construction-%d" % index] = 3 * index
		await timed("speedups", game.v6_panels.speedups.bind(order))
		await shot("speedups")
	if wanted("recruit"):
		var barracks: Array = game.state.city.buildings.filter(func(b): return b.type == "MIL-01")
		if not barracks.is_empty():
			await timed("recruit", func(): game.open_recruitment(barracks[0], "ENG-01", 1))
			await wait_until(func(): return game.modal.visible and game.modal_body.get_child_count() > 0)
			await shot("recruit")
	if wanted("army"):
		await timed("army", game.show_armies)
		await wait_until(func(): return game.modal_title.text == "Армия и осада")
		await shot("army")
	if wanted("reports"):
		await timed("reports", game.show_reports)
		await shot("reports")
	if wanted("account"):
		await timed("account", game.show_account)
		await shot("account")
	if wanted("economy"):
		await timed("economy", game.v6_panels.economy)
		await wait_until(func(): return game.modal_title.text == "Экономика поселения")
		await shot("economy")
	if wanted("trade"):
		await timed("trade", game.v6_panels.trade)
		await wait_until(func(): return game.modal_title.text == "Рынок")
		await shot("trade")
	if game.modal.visible:
		game.close_modal()
	print("UI_PREMIUM_SHOTS ", JSON.stringify({"saved": saved, "timings": timings, "size": [view_size.x, view_size.y]}))
	quit(0)
