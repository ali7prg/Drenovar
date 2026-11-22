extends SceneTree
## Stills of the construction windows (premium UI stage 3, ui_premium/STAGE3.md), rendered
## (not headless) against the synthetic buildings fixture of a local server checkout:
##   (cd ../drenovar-server && node v6/tests/buildings-ui-local.mjs)        # port 8792
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s qa_build_strip_shots.gd -- --server=http://127.0.0.1:8792 --shots=/abs/dir [--prefix=after_]
##     [--size=1366x630] [--only=build,maxed,swipe,upgrade,confirm,place,soon]
## The strip shots use a young settlement (the fixture's house case at VI: eleven types built,
## sixteen to build); the upgrade and confirm shots use barracks IV -> V, the soon shot barracks
## V (levels past V are not offered yet). Works on the stage-2 code too (before shots): it opens the old windows there.
## Prints BUILD_SHOTS with the saved names and the window-open main-thread times.

var game: Node
var shots_dir := "user://build_shots"
var prefix := ""
var only: PackedStringArray = []
var view_size := Vector2i(1366, 630)
var saved: Array = []
var timings := {}
var fixture := "http://127.0.0.1:8792"

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

func shot(name: String, settle := 24) -> void:
	await frames(settle)
	await RenderingServer.frame_post_draw
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
	return "build" in game.v6_panels and game.v6_panels.build != null

func seed_case(type: String, level: int) -> void:
	if game.modal.visible:
		game.close_modal()
	await admin("case", {"type":type, "level":level, "bounded":true})
	await game.sync_account()
	await wait_until(func(): return game.v6_panels.enabled(), 30.0)
	await frames(30)

# Opens a window and records the call plus its first frame.
func timed(name: String, open: Callable) -> void:
	var started := Time.get_ticks_usec()
	open.call()
	var call_ms := (Time.get_ticks_usec() - started) / 1000.0
	await process_frame
	timings[name] = {"call_ms": snappedf(call_ms, 0.01), "with_frame_ms": snappedf((Time.get_ticks_usec() - started) / 1000.0, 0.01)}
	await wait_until(func(): return game.modal.visible and game.modal_body.get_child_count() > 0)

func strip() -> Variant:
	return game.v6_panels.build.strip if premium() else null

func run() -> void:
	root.size = view_size
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 240000
	while (game.scene_loading or not is_instance_valid(game.stage)) and Time.get_ticks_msec() < deadline:
		await process_frame
	game.session = "device." + "a".repeat(64)
	await seed_case("B02", 6)
	await game.v6_panels.load_catalogue()
	# Catalogue once, so the timed opens below measure the windows, not the network.
	await frames(60)
	if wanted("build"):
		await timed("build", game.v6_panels.catalog)
		if premium():
			var names := ["economy", "craft", "army", "defence"]
			for index in names.size():
				game.v6_panels.build.show_category(index)
				await shot("build_" + names[index], 40 if index == 0 else 16)
		else:
			await shot("build")
	if wanted("maxed") and premium():
		await timed("build", game.v6_panels.catalog)
		game.v6_panels.build.show_category(0)
		await frames(4)
		strip().scroll_to_type("B03", false)
		await shot("build_maxed", 30)
	if wanted("swipe") and premium():
		await timed("build", game.v6_panels.catalog)
		game.v6_panels.build.show_category(1)
		await frames(20)
		# A finger flick to the left: the strip is caught mid-glide.
		strip().fling(2600.0)
		await frames(5)
		await RenderingServer.frame_post_draw
		var dir := ProjectSettings.globalize_path(shots_dir)
		root.get_texture().get_image().save_png(dir.path_join(prefix + "build_swipe.png"))
		saved.append("build_swipe")
		print("SHOT build_swipe")
	if wanted("place"):
		if premium():
			await timed("build", game.v6_panels.catalog)
			game.v6_panels.build.show_category(1)
			await frames(10)
			game.v6_panels.build.begin_placement("B05")
			await shot("place", 50)
			var plots: Array = game.v6_panels.build.placement_plots()
			if not plots.is_empty():
				game.v6_panels.build.pick_plot(str(plots[0].id))
				await wait_until(func(): return game.v6_panels.build.quote_ready(), 10.0)
				await shot("place_confirm", 30)
			game.v6_panels.build.cancel_placement()
		else:
			await timed("inspect_unbuilt", game.v6_panels.inspect.bind("B05"))
			await shot("place")
	# Barracks IV: the upgrade to V (the open level, main.gd MAX_OPEN_BUILDING_LEVEL) and its
	# quote; barracks V: «После» is the «Скоро» card.
	if wanted("upgrade") or wanted("confirm"):
		await seed_case("B11", 4)
		await game.v6_panels.load_catalogue()
		await frames(30)
		if wanted("upgrade"):
			await timed("inspect", game.v6_panels.inspect.bind("B11"))
			await shot("upgrade_B11", 90)
		if wanted("confirm"):
			await timed("confirm", game.v6_panels.confirm.bind({"kind":"construction", "building":"B11", "target":5}))
			await wait_until(func(): return game.modal_footer.get_child_count() > 0, 10.0)
			await shot("confirm_B11", 40)
	if wanted("soon"):
		await seed_case("B11", 5)
		await game.v6_panels.load_catalogue()
		await frames(30)
		await timed("inspect_soon", game.v6_panels.inspect.bind("B11"))
		await shot("upgrade_B11_soon", 90)
	print("BUILD_SHOTS ", JSON.stringify({"saved": saved, "timings": timings}))
	quit(0)
