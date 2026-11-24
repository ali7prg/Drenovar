extends SceneTree
## Stills of the premium UI stage 4b (ui_premium/STAGE4B.md): the menu, the account and its
## pairing code and confirmations, the market, the economy, the objectives, the archive, the
## world map windows, the toasts and banners, and the polish of the army, the chronicle, the
## ring, the upgrade window, the «Скоро» card and the recruitment stage. Rendered (not
## headless) against the synthetic buildings fixture (drenovar-server v6/tests/buildings-ui-local.mjs,
## 127.0.0.1:8792):
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s qa_stage4b_shots.gd -- --server=http://127.0.0.1:8792 --shots=/abs/dir [--prefix=after_]
##     [--size=2532x1170] [--only=menu,account]
## Headless with --repeat=N: no stills; each window opens N times and the median main-thread
## time of opens 2..N is printed (STAGE4B_TIMINGS).
## Display-only additions (not on the server, stated in STAGE4B.md): battle reports, an
## archive entry, world stand-ins where the fixture's world has none (a march, a creature).

var game: Node
var shots_dir := "user://stage4b_shots"
var prefix := ""
var only: PackedStringArray = []
var view_size := Vector2i(1366, 630)
var saved: Array = []
var timings := {}
var repeat := 0
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
		elif arg.begins_with("--repeat="):
			repeat = int(arg.trim_prefix("--repeat="))
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

func shot(name: String, settle := 20, before_capture := Callable()) -> void:
	if repeat > 0:
		return
	await frames(settle)
	if before_capture.is_valid():
		before_capture.call()
		await frames(2)
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

## Main-thread time of a window open (the call until it returns). With --repeat the window
## opens N times (closing between) and the median of opens 2..N is kept beside the first.
func timed(name: String, open: Callable) -> void:
	var runs: Array = []
	for i in maxi(1, repeat):
		if i > 0:
			game.close_modal()
			await frames(3)
		var started := Time.get_ticks_usec()
		open.call()
		runs.append((Time.get_ticks_usec() - started) / 1000.0)
		await process_frame
	var later: Array = runs.slice(1) if runs.size() > 1 else runs.duplicate()
	later.sort()
	timings[name] = {"first_ms": snappedf(runs[0], 0.01), "median_ms": snappedf(later[later.size() / 2], 0.01), "runs": runs.size()}

func order(intent: Dictionary) -> bool:
	intent.economy_version = VERSION
	return await game.command({"kind": "v6", "intent": intent}, func(): pass)

func pending() -> Array:
	return game.state.v6.orders.filter(func(o): return o.status == "pending")

func instance_of(type: String) -> Dictionary:
	for b: Dictionary in game.state.city.buildings:
		if str(b.get("conceptType", "")) == type:
			return b
	return {}

func marker_of(type: String) -> Dictionary:
	var b := instance_of(type)
	for marker: Dictionary in game.stage.place_markers:
		if marker.get("kind", "") == "building" and str(marker.item.get("id", "")) == str(b.get("id", "-")):
			return marker
	return {}

func look_at_marker(marker: Dictionary, zoom := 46.0) -> void:
	game.stage.target = marker.position - Vector3.UP * 2.0
	game.stage.zoom = zoom
	game.stage.update_camera(0, true)
	await frames(4)

func sample_reports() -> Array:
	var now: float = game.timer_now()
	return [
		{"id": "qa-r3", "outcome": "victory", "finishedAt": now - 240000.0, "creature": {"name": "Тенерис", "level": 3, "species": "tenerys"},
			"surviving": {"ENG-01": 34, "ENG-03": 20, "ENG-06": 8}, "wounded": {"ENG-01": 6}, "dead": {"ENG-01": 2},
			"rewards": {"resources": {"food": 1200, "wood": 800, "coins": 240}, "items": {"claws": 3}, "xp": 180}},
		{"id": "qa-r2", "outcome": "defeat", "finishedAt": now - 3900000.0, "creature": {"name": "Велькор", "level": 5, "species": "velkor"},
			"surviving": {"ENG-01": 12}, "wounded": {"ENG-01": 18, "ENG-03": 9}, "dead": {"ENG-01": 10, "ENG-03": 4},
			"rewards": {"resources": {}, "items": {}, "xp": 20}},
		{"id": "qa-r1", "outcome": "victory", "finishedAt": now - 90000000.0, "creature": {"name": "Английское поселение", "level": 4},
			"surviving": {"ENG-01": 40, "ENG-06": 10}, "wounded": {"ENG-01": 4}, "dead": {},
			"fortification": {"wallLevel": 3, "defencePct": 12, "fortPower": 1800, "defenderPower": 5200, "attackerPower": 9100},
			"rewards": {"resources": {"food": 2600, "stone": 900, "iron": 300}, "items": {}, "xp": 260}},
	]

func sync_case(type: String, level: int) -> void:
	await admin("case", {"type": type, "level": level})
	await game.sync_account()
	await wait_until(func(): return game.v6_panels.enabled(), 30.0)
	await game.v6_panels.load_catalogue()
	if game.modal.visible:
		game.close_modal()

func run() -> void:
	root.size = view_size
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 240000
	while (game.scene_loading or not is_instance_valid(game.stage)) and Time.get_ticks_msec() < deadline:
		await process_frame
	await frames(30)
	# The window scripts' warm compile after launch (stage 4a) finishes first, as it does long
	# before a player's first tap; the first launch's own «Аккаунт» compiles its script during
	# the launch's first frames (main.gd, v6_panels.request_view).
	while is_instance_valid(game.v6_panels) and not game.v6_panels.warming.is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	if wanted("account_entry"):
		# A fresh device: the account entry the first launch shows («Аккаунт»).
		game.reset_session()
		await timed("account_entry", game.show_account)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Аккаунт")
		await shot("account_entry")
	game.session = "device." + "a".repeat(64)
	await sync_case("B11", 4)
	# Troops at home for the army window (trained on the server, then the clock moves past them).
	for pair: Array in [["ENG-01", 60], ["ENG-03", 40], ["ENG-06", 16]]:
		await order({"kind": "train", "unit": pair[0], "quantity": pair[1]})
	await order({"kind": "siege", "unit": "SIEGE-RAM-01", "quantity": 2})
	var last := 0
	for item: Dictionary in pending():
		last = maxi(last, int(item.ends_at))
	if last > 0:
		await admin("time", {"now": last * 1000 + 1000})
	await game.sync_account()
	if game.modal.visible:
		game.close_modal()
	await frames(30)
	game.state.reports = sample_reports()
	game.reports_seen_ms = 0.0
	game.refresh_hud()
	if wanted("upgrade"):
		await timed("upgrade", func(): game.v6_panels.inspect("B11"))
		await shot("upgrade", 60)
	if wanted("recruit"):
		await timed("recruit", func(): game.v6_panels.services("B11"))
		await wait_until(func(): return game.modal.visible and game.modal_body.get_child_count() > 0)
		# The spearman (his kettle hat is item f of the backlog).
		game.v6_panels.recruit.pick("ENG-01")
		await shot("recruit", 90)
	if game.modal.visible:
		game.close_modal()
	if wanted("ring"):
		var marker := marker_of("B05")
		if not marker.is_empty():
			await look_at_marker(marker)
			await timed("ring", func(): game.open_building_ring({"item": instance_of("B05"), "position": marker.position, "kind": "building"}))
			game.close_modal()
			game.open_building_ring({"item": instance_of("B05"), "position": marker.position, "kind": "building"})
			if repeat == 0:
				# Mid-unfold and at rest. Lavapipe frames are slower than the 170 ms unfold, so
				# the unfold is held at 45 % for the still (the same drawing a phone shows ~75 ms in).
				var ring = game.action_ring
				if ring.get("unfold_tween") != null:
					ring.unfold_tween.kill()
					ring.set_unfold(0.45)
				await frames(2)
				var dir := ProjectSettings.globalize_path(shots_dir)
				DirAccess.make_dir_recursive_absolute(dir)
				root.get_texture().get_image().save_png(dir.path_join(prefix + "ring_unfold.png"))
				saved.append("ring_unfold")
				if ring.has_method("set_unfold"):
					ring.set_unfold(1.0)
			await shot("ring", 24)
			game.action_ring.close()
	if wanted("menu"):
		await timed("menu", game.show_controls_menu)
		await shot("menu")
	if wanted("account"):
		await timed("account", game.show_account)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Аккаунт")
		await shot("account")
	if wanted("pairing"):
		await timed("pairing", game.v6_panels.pairing_code)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Код подключения", 8.0)
		await shot("pairing")
	if wanted("confirm"):
		# The sign-out question as the account asks it (danger: it cannot be undone); the action
		# is a no-op here so the still does not sign out.
		var ask := func():
			if game.v6_panels.VIEW_SCRIPTS.has("menu_view"):
				game.v6_panels.menu_view.confirm(game.sign_out_question(), func(): pass, "Подтвердить", true, "kit_emb_exit")
			else:
				game.confirm_profile_action(game.sign_out_question(), func(): pass)
		await timed("confirm", ask)
		await shot("confirm")
	if wanted("trade"):
		await timed("trade", game.v6_panels.trade)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Рынок")
		await shot("trade")
	if wanted("economy"):
		await timed("economy", game.v6_panels.economy)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Экономика поселения")
		await shot("economy")
	if wanted("objectives"):
		await timed("objectives", game.v6_panels.objectives)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Цели поселения")
		await shot("objectives")
	if wanted("archive"):
		# Display only: one archived building (the COMPAT-P2 test realm has them; the fixture not).
		game.state.v6.legacy_building_archive = [{"instance": {"to_type": "B05", "level": 3, "plot": "P07"},
			"proposed_compensation": {"wood": 1200, "stone": 800, "coins": 150}}]
		await timed("archive", game.v6_panels.archive)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Архив прежних зданий")
		await shot("archive")
	if wanted("army"):
		await timed("army", game.v6_panels.army)
		await wait_until(func(): return game.modal.visible and game.modal_title.text != "")
		await shot("army", 60)
	if wanted("reports"):
		game.state.reports = sample_reports()
		await timed("reports", game.show_reports)
		await shot("reports")
	if game.modal.visible:
		game.close_modal()
	if wanted("toast"):
		game.message.text = "Строительство началось: Рынок · ур. IV"
		await shot("toast", 12)
		game.show_error({"error": "Не хватает железа: нужно ещё 340."})
		await shot("toast_error", 12)
		game.message.text = ""
		# The banner's own rule: a failure and 20 s without an answer (1024; the clock is moved back).
		var failures: int = game.diagnostics.network_failures
		var last_ok: int = game.last_ok_msec
		var offline := func():
			game.diagnostics.network_failures = maxi(1, failures)
			game.last_ok_msec = Time.get_ticks_msec() - 21000
			game.update_connection_notice()
		offline.call()
		# The fixture keeps answering the game's polls: the state is set again just before
		# the capture, so an answer that landed meanwhile does not hide the pill.
		await shot("banner_offline", 8, offline)
		game.diagnostics.network_failures = failures
		game.last_ok_msec = Time.get_ticks_msec()
		game.update_connection_notice()
	if wanted("soon"):
		await sync_case("B11", 5)
		await timed("soon", func(): game.v6_panels.inspect("B11"))
		await shot("soon", 60)
		game.close_modal()
	# World map.
	if wanted("world") or wanted("world_windows"):
		await game.show_scene("world")
		await wait_until(func(): return game.map_name == "world" and not game.scene_loading, 60.0)
		await frames(40)
		var world: Dictionary = game.state.get("world", {})
		print("WORLD cities=", world.get("cities", []).size(), " encounters=", world.get("encounters", []).size(), " armies=", world.get("armies", []).size())
		if wanted("world"):
			await shot("world", 30)
		if wanted("world_windows"):
			await timed("world_menu", game.show_controls_menu)
			await shot("world_menu")
			await timed("directory", game.show_world_directory)
			await shot("directory")
			await timed("cities", game.show_world_cities)
			await shot("cities")
			var own := {}
			var rival := {}
			for city: Dictionary in world.get("cities", []):
				if city.id == game.player_id:
					own = city
				elif rival.is_empty():
					rival = city
			if not own.is_empty():
				await timed("settlement", func(): game.inspect_settlement(own))
				await shot("settlement")
			if rival.is_empty() and not own.is_empty():
				rival = own.duplicate(true)
				rival.id = "qa-rival"
				rival.name = "Застава Ярополка"
				rival.nickname = "Ярополк"
				rival.level = 7
				rival.wallLevel = 3
				rival.pvp = true
				# A neighbour's spot east of the player's city (display only), not on top of it.
				var spot: Dictionary = own.get("position", {"x": 0, "z": 0})
				rival.position = {"x": float(spot.get("x", 0)) + 42.0, "z": float(spot.get("z", 0)) + 30.0}
			if not rival.is_empty():
				await timed("settlement_rival", func(): game.inspect_settlement(rival))
				await shot("settlement_rival")
			var encounters: Array = world.get("encounters", [])
			if not encounters.is_empty():
				await timed("encounter", func(): game.inspect_encounter(encounters[0]))
				await shot("encounter", 40)
			await timed("hunts", game.show_world_hunt)
			await shot("hunts")
			var army := {"id": "qa-march", "name": "Отряд на Велькора", "status": "outbound", "owner": game.player_id,
				"units": {"ENG-01": 40, "ENG-03": 20}, "arrivesAt": game.timer_now() + 252000.0, "worldKind": "velkor",
				"position": own.get("position", {"x": 0, "z": 0})}
			await timed("march", func(): game.inspect_army(army))
			await shot("march")
			await timed("map_layers", game.show_map_options)
			await shot("map_layers")
			var plots: Array = game.stage.empty_plots if is_instance_valid(game.stage) else []
			if not plots.is_empty():
				await timed("world_plot", func(): game.inspect_world_plot(plots[0].item))
				await shot("world_plot")
	if game.modal.visible:
		game.close_modal()
	print("STAGE4B_SHOTS ", JSON.stringify({"saved": saved, "size": [view_size.x, view_size.y]}))
	print("STAGE4B_TIMINGS ", JSON.stringify(timings))
	quit(0)
