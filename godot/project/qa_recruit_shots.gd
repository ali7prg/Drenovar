extends SceneTree
## Stills of the recruitment window (premium UI stage 2, ui_premium/STAGE2.md), rendered
## (not headless) against the synthetic buildings fixture of a local server checkout:
##   (cd ../drenovar-server && node v6/tests/buildings-ui-local.mjs)        # port 8792
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s qa_recruit_shots.gd -- --server=http://127.0.0.1:8792 --shots=/abs/dir [--prefix=after_]
##     [--size=1366x630] [--only=B11,locked,details,progress,speedups,B12,B13,B17]
## The fixture seeds a whole settlement at XI with the barracks at II (so the shield swordsman
## is locked); a few finished training orders give the cards real owned counts.
## Works on the stage-1 code too (before shots): it falls back to the old windows there.
## Prints RECRUIT_SHOTS with the saved names and the window-open main-thread times.

var game: Node
var shots_dir := "user://recruit_shots"
var prefix := ""
var only: PackedStringArray = []
var view_size := Vector2i(1366, 630)
var saved: Array = []
var timings := {}
var fixture := "http://127.0.0.1:8792"
const VERSION := "DRENOVAR-V6-C1.0"

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots_dir = arg.trim_prefix("--shots=")
		elif arg.begins_with("--prefix="):
			prefix = arg.trim_prefix("--prefix=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",")
		elif arg.begins_with("--size="):
			var parts := arg.trim_prefix("--size=").split("x")
			view_size = Vector2i(int(parts[0]), int(parts[1]))
		elif arg.begins_with("--server="):
			fixture = arg.trim_prefix("--server=").trim_suffix("/")
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func wanted(name: String) -> bool:
	return only.is_empty() or name in only

func shot(name: String) -> void:
	await frames(24)
	var dir := ProjectSettings.globalize_path(shots_dir)
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_texture().get_image().save_png(dir.path_join(prefix + name + ".png"))
	saved.append(name)
	print("SHOT ", name)

func wait_until(condition: Callable, seconds := 10.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call():
			return true
		await process_frame
	return false

func admin(path: String, body: Dictionary) -> Variant:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request(fixture + "/qa/" + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(body))
	var result: Array = await request.request_completed
	request.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8())

func premium() -> bool:
	return game.v6_panels.has_method("recruit_pick")

# Opens the works window of a building type and records the call plus its first frame.
func open_services(type: String) -> void:
	var started := Time.get_ticks_usec()
	game.v6_panels.services(type)
	var call_ms := (Time.get_ticks_usec() - started) / 1000.0
	await process_frame
	timings[type] = {"call_ms": snappedf(call_ms, 0.01), "with_frame_ms": snappedf((Time.get_ticks_usec() - started) / 1000.0, 0.01)}
	await wait_until(func(): return game.modal.visible and game.modal_body.get_child_count() > 0)

func train(unit: String, quantity: int) -> void:
	await game.command({"kind":"v6", "intent":{"kind":"train", "unit":unit, "quantity":quantity, "economy_version":VERSION}})

func pending() -> Array:
	return game.state.v6.orders.filter(func(o): return o.status == "pending")

func run() -> void:
	root.size = view_size
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 240000
	while (game.scene_loading or not is_instance_valid(game.stage)) and Time.get_ticks_msec() < deadline:
		await process_frame
	game.session = "device." + "a".repeat(64)
	await admin("case", {"type":"B11", "level":2, "bounded":true})
	await game.sync_account()
	await wait_until(func(): return game.v6_panels.enabled(), 30.0)
	await game.v6_panels.load_catalogue()
	# Owned troops: three finished orders (the fixture clock only moves when told to).
	await train("ENG-01", 24)
	await train("ENG-03", 24)
	await train("ENG-06", 12)
	var last := 0
	for order: Dictionary in pending():
		last = maxi(last, int(order.ends_at))
	if last > 0:
		await admin("time", {"now": last * 1000 + 1000})
	await game.sync_account()
	if game.modal.visible:
		game.close_modal()
	await frames(60)
	if wanted("B11"):
		await open_services("B11")
		await shot("recruit_B11")
	if wanted("locked") and premium():
		await open_services("B11")
		game.v6_panels.recruit_pick("ENG-02")
		await shot("recruit_locked")
	if wanted("details") and premium():
		await open_services("B11")
		game.v6_panels.recruit_pick("ENG-01")
		game.v6_panels.recruit_details()
		await shot("recruit_details")
		game.v6_panels.recruit_details()
	for type: String in ["B12", "B13", "B17"]:
		if wanted(type):
			await open_services(type)
			await shot("recruit_" + type)
	if wanted("progress") or wanted("speedups"):
		await train("ENG-01", 30)
		var order: Dictionary = pending()[0] if not pending().is_empty() else {}
		if not order.is_empty():
			# A third of the way through, so the bar and the timer read as a running order.
			var span := int(order.ends_at) - int(order.starts_at)
			await admin("time", {"now": (int(order.starts_at) + span / 3) * 1000})
			await game.sync_account()
			if not game.state.has("items") or not game.state.items is Dictionary:
				game.state.items = {}
			for index in [1, 2, 3, 5]:
				game.state.items["training-%d" % index] = 2 * index + 1
			if wanted("progress"):
				if premium():
					await open_services("B11")
				else:
					await game.v6_panels.queues()
				await shot("recruit_progress")
			if wanted("speedups"):
				if premium():
					await game.v6_panels.speedups(pending()[0], game.v6_panels.services.bind("B11"))
				else:
					await game.v6_panels.speedups(pending()[0])
				await shot("recruit_speedups")
	if game.modal.visible:
		game.close_modal()
	print("RECRUIT_SHOTS ", JSON.stringify({"saved": saved, "timings": timings, "size": [view_size.x, view_size.y], "premium": premium()}))
	quit(0)
