extends SceneTree
## Stills of the premium UI stage 4a (ui_premium/STAGE4A.md): the queues and speed-ups window,
## quick use, the city HUD, the building ring (busy and idle), the army, the formation, the
## compose-march window, research, the hospital and the battle reports. Rendered (not
## headless) against the synthetic buildings fixture (drenovar-server v6/tests/buildings-ui-local.mjs,
## 127.0.0.1:8792); every order in the stills is a real server order:
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1366x630x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s qa_stage4a_shots.gd -- --server=http://127.0.0.1:8792 --shots=/abs/dir [--prefix=after_]
##     [--size=2532x1170] [--only=speedups,army]
## Display-only additions (not on the server, stated in STAGE4A.md): battle reports (the fixture
## has no battles), extra wounded for the hospital, a march in the queue rail.
## Prints STAGE4A_SHOTS with the stills and the main-thread time of each window open.

var game: Node
var shots_dir := "user://stage4a_shots"
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

func shot(name: String, settle := 20) -> void:
	await frames(settle)
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

## Main-thread time of a window open: the call until it returns, and with the next frame.
func timed(name: String, open: Callable) -> void:
	var started := Time.get_ticks_usec()
	open.call()
	var call_ms := (Time.get_ticks_usec() - started) / 1000.0
	await process_frame
	timings[name] = {"call_ms": snappedf(call_ms, 0.01), "with_frame_ms": snappedf((Time.get_ticks_usec() - started) / 1000.0, 0.01)}

func order(intent: Dictionary) -> bool:
	intent.economy_version = VERSION
	return await game.command({"kind": "v6", "intent": intent}, func(): pass)

func pending() -> Array:
	return game.state.v6.orders.filter(func(o): return o.status == "pending")

func pending_of(building_type: String) -> Dictionary:
	for item: Dictionary in pending():
		if str(item.building) == building_type:
			return item
	return {}

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

## Display only: three battle reports in the shape the server sends (the fixture fights none).
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

func ring_shot(type: String, name: String) -> void:
	var marker := marker_of(type)
	if marker.is_empty():
		return
	await look_at_marker(marker)
	await timed(name, func(): game.open_building_ring({"item": instance_of(type), "position": marker.position, "kind": "building"}))
	await wait_until(func(): return game.action_ring.is_open(), 5.0)
	await shot(name, 24)
	game.action_ring.close()

func run() -> void:
	root.size = view_size
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 240000
	while (game.scene_loading or not is_instance_valid(game.stage)) and Time.get_ticks_msec() < deadline:
		await process_frame
	game.session = "device." + "a".repeat(64)
	if wanted("ring_soon"):
		# The market at the open level V: the ring offers a dim «Скоро» instead of «Улучшить».
		await admin("case", {"type": "B05", "level": 5})
		await game.sync_account()
		await wait_until(func(): return game.v6_panels.enabled(), 30.0)
		await game.v6_panels.load_catalogue()
		await frames(30)
		await ring_shot("B05", "ring_soon")
	await admin("case", {"type": "B05", "level": 3})
	await game.sync_account()
	await wait_until(func(): return game.v6_panels.enabled(), 30.0)
	await game.v6_panels.load_catalogue()
	if game.modal.visible:
		game.close_modal()
	if wanted("ring_idle"):
		# The market at III, idle: «Улучшить» on the gold medallion.
		await frames(30)
		await ring_shot("B05", "ring_idle")
	# Troops at home (trained on the server, then the clock moves past them).
	for pair: Array in [["ENG-01", 60], ["ENG-03", 40], ["ENG-06", 16]]:
		await order({"kind": "train", "unit": pair[0], "quantity": pair[1]})
	await order({"kind": "siege", "unit": "SIEGE-RAM-01", "quantity": 2})
	var last := 0
	for item: Dictionary in pending():
		last = maxi(last, int(item.ends_at))
	if last > 0:
		await admin("time", {"now": last * 1000 + 1000})
	await game.sync_account()
	# Running orders: an upgrade, two trainings, research and healing.
	await order({"kind": "construction", "building": "B05", "target": 4})
	await order({"kind": "train", "unit": "ENG-01", "quantity": 40})
	await order({"kind": "train", "unit": "ENG-03", "quantity": 24})
	await order({"kind": "research", "research": "R_ECON-1"})
	await order({"kind": "heal", "units": {"ENG-01": 1}})
	await game.sync_account()
	# A few minutes in, so the bars have moved.
	var server_now := int(game.state.v6.server_time)
	await admin("time", {"now": (server_now + 170) * 1000})
	await game.sync_account()
	if game.modal.visible:
		game.close_modal()
	await frames(40)
	# Display only: unread battle reports for the «Отчёты» badge (the fixture fights none).
	game.state.reports = sample_reports()
	game.refresh_hud()
	if wanted("city"):
		var hall := marker_of("B11")
		if not hall.is_empty():
			await look_at_marker(hall, 64.0)
		await shot("city", 30)
	if wanted("ring_busy"):
		var marker := marker_of("B11")
		if not marker.is_empty():
			await look_at_marker(marker)
			game.open_building_ring({"item": instance_of("B11"), "position": marker.position, "kind": "building"})
			await wait_until(func(): return game.action_ring.is_open(), 5.0)
			await shot("ring_busy", 24)
			game.action_ring.close()
	if wanted("queues"):
		await timed("queues", game.v6_panels.queues)
		await wait_until(func(): return game.modal.visible and game.modal_title.text == "Очереди поселения")
		await shot("queues")
	var training := pending_of("B11")
	if wanted("speedups") and not training.is_empty():
		await timed("speedups", game.v6_panels.speedups.bind(training, game.v6_panels.services.bind("B11")))
		await wait_until(func(): return game.modal.visible)
		await shot("speedups")
	var upgrade := pending_of("B05")
	if wanted("quickuse") and not upgrade.is_empty():
		# The upgrade outlasts every owned item: «Быстрое использование» stacks them all.
		await timed("quickuse", game.v6_panels.speedups.bind(upgrade))
		await shot("quickuse")
		if wanted("quickuse_done"):
			var apply: Button = game.modal_body.find_child("QuickApply", true, false)
			if apply != null:
				apply.pressed.emit()
				await wait_until(func(): return not game.v6_panels.queue_view.applying, 20.0)
				await shot("quickuse_done")
	if wanted("army"):
		await timed("army", game.v6_panels.army)
		await wait_until(func(): return game.modal.visible and game.modal_title.text != "")
		await shot("army")
	if wanted("formation"):
		var target := {}
		for city: Dictionary in game.state.get("world", {}).get("cities", []):
			if city.id != game.state.playerId and city.get("pvp", false):
				target = city
		if target.is_empty():
			# The fixture has no rival city: a stand-in target (display only).
			target = {"id": "qa-target", "name": "Застава Ярополка"}
		await timed("formation", func(): game.v6_panels.formation(str(target.id), str(target.name)))
		await shot("formation")
		game.close_modal()
	if wanted("compose"):
		var encounters: Array = game.state.get("encounters", [])
		if encounters.is_empty():
			# The settlement fixture has no creature nearby: a stand-in (display only).
			encounters = [{"id": "qa-prey", "level": 2, "status": "active", "hp": 100, "species": "tenerys", "spec": {"name": "Тенерис"}}]
			game.state.encounters = encounters
		if game.state.get("healthy", {}).is_empty():
			game.state.healthy = {"ENG-01": 61, "ENG-03": 40, "ENG-06": 16}
		if true:
			var prey: Dictionary = encounters[0]
			await timed("compose", func(): game.compose_march("city", str(prey.id), game.encounter_title(prey)))
			await shot("compose", 30)
			game.close_modal()
	if wanted("research"):
		await timed("research", func(): game.v6_panels.services("B15"))
		await wait_until(func(): return game.modal.visible and game.modal_body.get_child_count() > 0)
		await shot("research")
	if wanted("hospital"):
		# Display only: more wounded than the fixture's one spearman.
		game.state.v6.wounded = {"ENG-01": 46, "ENG-03": 18, "ENG-06": 5}
		await timed("hospital", func(): game.v6_panels.services("B16"))
		await wait_until(func(): return game.modal.visible and game.modal_body.get_child_count() > 0)
		await shot("hospital")
	if wanted("reports") or wanted("report"):
		game.state.reports = sample_reports()
		if wanted("reports"):
			await timed("reports", game.show_reports)
			await shot("reports")
		if wanted("report"):
			await timed("report", func(): game.show_report(game.state.reports[0]))
			await shot("report")
	if game.modal.visible:
		game.close_modal()
	print("STAGE4A_SHOTS ", JSON.stringify({"saved": saved, "timings": timings, "size": [view_size.x, view_size.y]}))
	quit(0)
