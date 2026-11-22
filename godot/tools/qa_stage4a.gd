extends SceneTree
## Stage 4a checks (ui_premium/STAGE4A.md) against the buildings-ui fixture on 8792:
## quick use picks the least waste (checked against an exhaustive search) and the server
## consumes exactly that sequence; the queue rail switches lanes and the band follows;
## the HUD badges count unread reports and free builders; the building ring offers
## «Улучшить» below the open level, a dim «Скоро» at V and «Ускорить» with the time
## left over a busy building.

const Queues = preload("res://src/v6_queues.gd")
const VERSION := "DRENOVAR-V6-C1.0"

var game
var checks := 0
var hud_saved := PackedByteArray()
var hud_existed := false

func check(ok: bool, label: String) -> bool:
	checks += 1
	if not ok:
		push_error(label)
		print(JSON.stringify({"status": "failed", "checks": checks, "reason": label}))
		restore_hud()
		quit(1)
	return ok

func wait_for(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not test.call():
		if Time.get_ticks_msec() > end:
			return false
		await process_frame
	return true

func admin(path: String, body: Dictionary) -> Variant:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request("http://127.0.0.1:8792/qa/" + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(body))
	var result: Array = await request.request_completed
	request.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8())

func order(intent: Dictionary) -> bool:
	intent.economy_version = VERSION
	return await game.command({"kind": "v6", "intent": intent}, func(): pass)

func pending_of(kind: String, building := "") -> Dictionary:
	for item: Dictionary in game.state.v6.orders:
		if item.status == "pending" and item.kind == kind and (building.is_empty() or str(item.get("building", "")) == building):
			return item
	return {}

func instance_of(type: String) -> Dictionary:
	for b: Dictionary in game.state.city.buildings:
		if str(b.get("conceptType", "")) == type:
			return b
	return {}

func ring_actions() -> Dictionary:
	var out := {}
	for item: Button in game.action_ring.buttons:
		out[item.tooltip_text] = item
	return out

func restore_hud() -> void:
	var path := "user://hud.cfg"
	if hud_existed:
		var file := FileAccess.open(path, FileAccess.WRITE)
		if file != null:
			file.store_buffer(hud_saved)
	elif FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))

## Exhaustive reference for least_waste: the smallest total that covers `remaining`, then
## the fewest items; everything owned when even that falls short.
func brute(items: Array, remaining: int) -> Array:
	var best := [-1, 0]
	var owned_total := 0
	var owned_count := 0
	for item: Array in items:
		owned_total += int(item[1]) * int(item[2])
		owned_count += int(item[2])
	if owned_total <= remaining:
		return [owned_total, owned_count]
	var picks: Array = []
	picks.resize(items.size())
	picks.fill(0)
	while true:
		var total := 0
		var count := 0
		for i in items.size():
			total += int(picks[i]) * int(items[i][1])
			count += int(picks[i])
		if total >= remaining and (best[0] < 0 or total < best[0] or (total == best[0] and count < best[1])):
			best = [total, count]
		var i := 0
		while i < items.size():
			picks[i] += 1
			if picks[i] <= int(items[i][2]):
				break
			picks[i] = 0
			i += 1
		if i == items.size():
			break
	return best

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	if FileAccess.file_exists("user://hud.cfg"):
		hud_existed = true
		hud_saved = FileAccess.get_file_as_bytes("user://hud.cfg")
	# 1. Least waste, pure: random inventories against the exhaustive search.
	var rng := RandomNumberGenerator.new()
	rng.seed = 4021
	var sizes := [3600, 900, 300, 60]
	for case_index in 400:
		var items: Array = []
		for seconds: int in sizes:
			items.append(["item-%d" % seconds, seconds, rng.randi_range(0, 6)])
		var remaining := rng.randi_range(1, 9000)
		var plan: Dictionary = Queues.least_waste(items, remaining)
		var expected := brute(items, remaining)
		if not check(int(plan.seconds) == int(expected[0]) and int(plan.count) == int(expected[1]),
			"least waste %s for %d s: got %d s / %d items, expected %d s / %d" % [str(items), remaining, plan.seconds, plan.count, expected[0], expected[1]]):
			return
		var sequence: Array = Queues.sequence(plan)
		if not check(sequence.size() == int(plan.count), "sequence has one use per item"):
			return
		var last := 1 << 30
		for item_id: String in sequence:
			var seconds := int(item_id.split("-")[1])
			if not check(seconds <= last, "sequence is longest first"):
				return
			last = seconds
	# A worked case: 1000 s with 2×60, 3×300, 1×900, 1×3600 → 900 + 60 + 60 (1020 s, three items).
	var worked: Dictionary = Queues.least_waste([["c-4", 3600, 1], ["c-3", 900, 1], ["c-2", 300, 3], ["c-1", 60, 2]], 1000)
	if not check(Queues.sequence(worked) == ["c-3", "c-1", "c-1"] and int(worked.waste) == 20, "worked least-waste case"):
		return
	# Everything owned falls short: all of it, longest first.
	var short: Dictionary = Queues.least_waste([["c-2", 300, 1], ["c-1", 60, 2]], 5000)
	if not check(Queues.sequence(short) == ["c-2", "c-1", "c-1"] and not short.finishes, "short inventory uses everything"):
		return

	root.size = Vector2i(844, 390)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	if not check(await wait_for(func(): return not game.scene_loading and is_instance_valid(game.stage), 240.0), "scene ready"):
		return
	game.session = "device." + "a".repeat(64)
	await admin("case", {"type": "B05", "level": 5})
	await game.sync_account()
	if not check(await wait_for(func(): return game.v6_panels.enabled(), 30.0), "v6 state"):
		return
	if not check(await game.v6_panels.load_catalogue(), "catalogue"):
		return

	# 2. Ring at the open level V: «Сведения» and a dim «Скоро», no «Улучшить».
	await game.open_building_ring({"item": instance_of("B05"), "position": Vector3.ZERO, "kind": "building"})
	await wait_for(func(): return game.action_ring.is_open(), 5.0)
	var actions := ring_actions()
	if not check(actions.has("Сведения") and actions.has("Скоро") and not actions.has("Улучшить"), "ring at V: Сведения + Скоро, no Улучшить (%s)" % str(actions.keys())):
		return
	if not check(actions["Скоро"].soon and not actions["Скоро"].primary, "Скоро is dim and not the main action"):
		return
	game.action_ring.close()
	# Below the open level: «Улучшить» on the gold medallion.
	await admin("case", {"type": "B05", "level": 3})
	await game.sync_account()
	await game.open_building_ring({"item": instance_of("B05"), "position": Vector3.ZERO, "kind": "building"})
	await wait_for(func(): return game.action_ring.is_open(), 5.0)
	actions = ring_actions()
	if not check(actions.has("Улучшить") and actions["Улучшить"].primary and not actions.has("Скоро"), "ring below V: primary Улучшить"):
		return
	if not check(not actions.has("Ускорить"), "idle building has no speed-up"):
		return
	game.action_ring.close()

	# 3. Running jobs: an upgrade (B05 → IV), two trainings, research and healing.
	for pair: Array in [["ENG-01", 20], ["ENG-03", 10]]:
		await order({"kind": "train", "unit": pair[0], "quantity": pair[1]})
	var last := 0
	for item: Dictionary in game.state.v6.orders:
		if item.status == "pending":
			last = maxi(last, int(item.ends_at))
	if last > 0:
		await admin("time", {"now": last * 1000 + 1000})
	await game.sync_account()
	await order({"kind": "construction", "building": "B05", "target": 4})
	await order({"kind": "train", "unit": "ENG-01", "quantity": 30})
	await order({"kind": "research", "research": "R_ECON-1"})
	await order({"kind": "heal", "units": {"ENG-01": 1}})
	await game.sync_account()
	var upgrade := pending_of("construction", "B05")
	var training := pending_of("train", "B11")
	if not check(not upgrade.is_empty() and not training.is_empty(), "fixture runs an upgrade and a training"):
		return

	# The ring over the busy barracks: «Ускорить» with the time left.
	await game.open_building_ring({"item": instance_of("B11"), "position": Vector3.ZERO, "kind": "building"})
	await wait_for(func(): return game.action_ring.is_open(), 5.0)
	actions = ring_actions()
	if not check(actions.has("Ускорить") and float(actions["Ускорить"].ends) > game.timer_now(), "busy barracks ring: Ускорить with the time left"):
		return
	actions["Ускорить"].pressed.emit()
	if not check(await wait_for(func(): return game.modal.visible and game.modal_title.text == "Ускорить работу", 5.0), "Ускорить opens the speed-up window"):
		return
	if not check(game.v6_panels.queue_view.lane_by_key(game.v6_panels.queue_view.selected).order.get("id", "") == training.id, "speed-up window opens on the barracks' order"):
		return
	game.close_modal()

	# 4. HUD badges: free builders (green) and unread reports.
	var use: Array = game.v6_panels.build.builder_use()
	var free := maxi(0, int(use[1]) - int(use[0]))
	game.refresh_hud_badges()
	if not check(game.nav_buttons.build.badge == (str(free) if free > 0 else "") and game.nav_buttons.build.badge_good, "free builders badge %s (busy %d of %d)" % [game.nav_buttons.build.badge, use[0], use[1]]):
		return
	var now: float = game.timer_now()
	game.reports_seen_ms = 0.0
	game.state.reports = [
		{"id": "r1", "outcome": "victory", "finishedAt": now - 90000.0, "creature": {"name": "Тенерис", "level": 2}, "surviving": {"ENG-01": 5}, "wounded": {}, "dead": {}, "rewards": {"resources": {"food": 300}, "xp": 40}},
		{"id": "r2", "outcome": "defeat", "finishedAt": now - 60000.0, "creature": {"name": "Велькор", "level": 4}, "surviving": {}, "wounded": {"ENG-01": 3}, "dead": {"ENG-01": 2}, "rewards": {"resources": {}, "xp": 5}},
		{"id": "r3", "outcome": "victory", "finishedAt": now - 30000.0, "creature": {"name": "Тенерис", "level": 1}, "surviving": {"ENG-01": 7}, "wounded": {}, "dead": {}, "rewards": {"resources": {"wood": 120}, "xp": 20}},
	]
	game.refresh_hud_badges()
	if not check(game.nav_buttons.reports.badge == "3" and not game.nav_buttons.reports.badge_good, "three unread reports on a red badge"):
		return
	game.show_reports()
	await process_frame
	if not check(game.modal_title.text == "Летопись сражений" and game.modal_body.find_children("Report_*", "", false, false).size() == 3, "chronicle lists every report"):
		return
	var newest: Button = game.modal_body.get_child(0)
	if not check(newest.name == "Report_r3" and newest.outcome == "victory" and newest.spoils.size() == 2, "newest report first, with its spoils"):
		return
	if not check(game.nav_buttons.reports.badge == "", "opening the chronicle marks reports seen"):
		return
	newest.pressed.emit()
	await process_frame
	if not check(game.modal_title.text == "Победа" and game.modal_body.find_child("ReportUnits", true, false) != null, "a report opens with its unit table"):
		return
	game.close_modal()
	game.state.reports.append({"id": "r4", "outcome": "defeat", "finishedAt": now + 1000.0, "creature": {"name": "Велькор"}, "surviving": {}, "wounded": {}, "dead": {}, "rewards": {}})
	game.refresh_hud_badges()
	if not check(game.nav_buttons.reports.badge == "1", "a new report after reading counts one"):
		return
	for i in 10:
		game.state.reports.append({"id": "x%d" % i, "outcome": "victory", "finishedAt": now + 2000.0 + i, "creature": {"name": "Тенерис"}})
	game.refresh_hud_badges()
	if not check(game.nav_buttons.reports.badge == "9+", "more than nine unread reads 9+"):
		return
	game.state.reports = []
	game.refresh_hud_badges()

	# 5. The queue rail: every lane selects, the band follows, free lanes offer work.
	game.v6_panels.queues()
	if not check(await wait_for(func(): return game.modal.visible and game.modal_title.text == "Очереди поселения", 5.0), "queues window opens"):
		return
	var view = game.v6_panels.queue_view
	var lanes: Array = view.lanes.duplicate()
	var sections := {}
	for lane: Dictionary in lanes:
		sections[lane.section] = true
	if not check(lanes.size() >= 4 and sections.has("Строительство") and sections.has("Войска"), "rail has building and troop lanes (%d lanes)" % lanes.size()):
		return
	var switched := 0
	for lane: Dictionary in lanes:
		var control: Button = game.modal_hero.find_child("Lane" + str(lane.key), true, false)
		if not check(control != null, "lane button " + str(lane.key)):
			return
		control.pressed.emit()
		await process_frame
		var band = game.modal_tools.find_child("QueueBand", true, false)
		if not check(view.selected == str(lane.key) and control.selected, "lane %s selected" % lane.key):
			return
		if not check(band != null and str(band.title).begins_with(str(lane.title)), "band follows lane %s (%s)" % [lane.key, band.title if band != null else "none"]):
			return
		if lane.order.is_empty():
			if not check(game.modal_body.find_child("QueueFree", true, false) != null, "free lane %s offers work" % lane.key):
				return
		elif str(lane.order.get("kind", "")) in ["construction", "train"]:
			if not check(game.modal_body.find_child("QuickUse", true, false) != null, "running lane %s offers quick use" % lane.key):
				return
		switched += 1
	game.close_modal()

	# 6. Quick use on the upgrade: 1000 s left; the server consumes the least-waste sequence.
	upgrade = pending_of("construction", "B05")
	await admin("time", {"now": int(float(upgrade.ends_at) * 1000.0) - 1000 * 1000})
	await game.sync_account()
	upgrade = pending_of("construction", "B05")
	var items: Array = view.items_of("construction")
	var before := {}
	for item: Array in items:
		before[item[0]] = int(item[2])
	var remaining := int(ceil(float(upgrade.ends_at) - float(game.state.v6.server_time)))
	var plan: Dictionary = Queues.least_waste(items, remaining)
	var expected := brute(items, remaining)
	if not check(int(plan.seconds) == int(expected[0]) and int(plan.count) == int(expected[1]) and int(plan.count) > 0, "live plan is the least waste (%s)" % str(plan)):
		return
	game.v6_panels.speedups(upgrade)
	if not check(await wait_for(func(): return game.modal.visible and game.modal_body.find_child("QuickApply", true, false) != null, 5.0), "quick use offered"):
		return
	(game.modal_body.find_child("QuickApply", true, false) as Button).pressed.emit()
	await process_frame
	if not check(view.applying, "quick use runs"):
		return
	if not check(await wait_for(func(): return not view.applying, 30.0), "quick use finishes"):
		return
	await game.sync_account()
	var used := {}
	for entry: Array in plan.use:
		used[entry[0]] = int(entry[1])
	for item: Array in view.items_of("construction"):
		var spent: int = int(before.get(item[0], 0)) - int(item[2])
		if not check(spent == int(used.get(item[0], 0)), "server consumed %d × %s, plan %d" % [spent, item[0], used.get(item[0], 0)]):
			return
	var after := pending_of("construction", "B05")
	if plan.finishes:
		if not check(after.is_empty() or str(after.get("id", "")) != str(upgrade.id), "upgrade finished by quick use"):
			return
	print(JSON.stringify({"status": "passed", "checks": checks, "lanes": switched, "plan": plan, "remaining": remaining}))
	restore_hud()
	quit(0)
