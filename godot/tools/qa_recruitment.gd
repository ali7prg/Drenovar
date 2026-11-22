extends SceneTree
## Recruitment window flow (premium UI stage 2, ui_premium/STAGE2.md) against the synthetic
## buildings fixture of a local server checkout (no real account, localhost only):
##   (cd ../drenovar-server && node v6/tests/buildings-ui-local.mjs)        # port 8792
##   godot --headless --path godot/project -s /abs/godot/tools/qa_recruitment.gd
## Open the barracks, switch building on the rail without closing the window, pick a unit,
## change the quantity (cost and time follow the server rules), train (the order the server
## records is the one the window showed), the in-progress card, speed-ups and back, cancel,
## details, the locked unit, and the stage freed on close.
var game
var checks := 0
var cases: Array = []
var server := "http://127.0.0.1:8792"
const VERSION := "DRENOVAR-V6-C1.0"

func check(ok: bool, label: String) -> bool:
	checks += 1
	if not ok:
		push_error(label)
		print(JSON.stringify({"status":"failed", "checks":checks, "reason":label, "cases":cases}))
		quit(1)
	return ok

func wait_for(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not test.call():
		if Time.get_ticks_msec() > end:
			return false
		await process_frame
	return true

func node(name: String) -> Node:
	return game.modal.find_child(name, true, false)

func admin(path: String, body: Dictionary) -> Variant:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request(server + "/qa/" + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(body))
	var result: Array = await request.request_completed
	request.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8())

func pending() -> Array:
	return game.state.v6.orders.filter(func(o): return o.status == "pending")

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			server = arg.trim_prefix("--server=").trim_suffix("/")
	call_deferred("run")

# The server's rules (v6/orders.mjs), computed here from the catalogue on their own.
func expected_seconds(unit: Dictionary, building_type: String, count: int) -> int:
	var level := int(game.v6_panels.building(building_type).level)
	var effects: Dictionary = game.v6_panels.row_for(building_type, level).effects
	var bonus := int(effects.get("siege_speed_bp" if building_type == "B17" else "training_speed_bp", 0))
	return maxi(1, ceili(float(int(unit.seconds) * count) * 10000.0 / float(10000 + bonus)))

func catalogue_unit(id: String) -> Dictionary:
	for unit: Dictionary in game.v6_panels.catalogue.units:
		if unit.unit_id == id:
			return unit
	return {}

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	if not check(await wait_for(func(): return not game.scene_loading and is_instance_valid(game.stage), 240.0), "scene ready"): return
	game.session = "device." + "a".repeat(64)
	# Whole settlement at XI, barracks at II (the shield swordsman needs III), half-full stores.
	await admin("case", {"type":"B11", "level":2, "bounded":true})
	await game.sync_account()
	if not check(await game.v6_panels.load_catalogue(), "catalogue"): return
	var recruit = game.v6_panels.recruit

	# Open: one window, rail of every training building, stage, tier cards.
	await game.v6_panels.services("B11")
	if not check(recruit.is_open() and game.modal_layout == "full", "recruitment window opens"): return
	if not check(game.modal_title.text == str(game.v6_panels.row_for("B11", 1).name_ru), "barracks title"): return
	for type: String in ["B11", "B12", "B13", "B17"]:
		if not check(node("Rail" + type) is BaseButton, "rail medal " + type): return
	if not check(node("UnitStage") != null and node("CardENG-01") is BaseButton and node("CardENG-02") is BaseButton, "stage and tier cards"): return
	if not check(game.modal_top.visible and game.modal_wallet_amounts.wood.text != "", "resources on the window"): return
	var open_ms: float = recruit.last_open_usec / 1000.0
	cases.append({"case":"open", "open_ms":snappedf(open_ms, 0.01)})

	# Locked unit: lock, requirement, upgrade path; no train button.
	(node("CardENG-02") as BaseButton).pressed.emit()
	if not check(recruit.unit_id == "ENG-02" and node("RecruitLock") != null and node("RecruitTrain") == null and node("RecruitUpgrade") is Button, "locked unit shows what opens it"): return
	cases.append({"case":"locked"})

	# Switch building in place: same window (generation), same stage node.
	var stage: Control = node("UnitStage")
	var generation: int = game.modal_generation
	(node("RailB12") as BaseButton).pressed.emit()
	if not check(await wait_for(func(): return recruit.type == "B12"), "rail switches to the range"): return
	if not check(game.modal_generation == generation and node("UnitStage") == stage and game.modal.visible, "switching keeps the window and stage"): return
	if not check(game.modal_title.text == str(game.v6_panels.row_for("B12", 1).name_ru), "range title"): return
	cases.append({"case":"switch"})

	# Select a unit: stage and summary follow.
	(node("CardENG-04") as BaseButton).pressed.emit()
	if not check(recruit.unit_id == "ENG-04" and stage.unit_id == "ENG-04" and node("RecruitTrain") is Button, "crossbowman selected"): return
	var unit := catalogue_unit("ENG-04")

	# Quantity: cost and time follow the server rules.
	var field: SpinBox = recruit.field
	for count: int in [7, 13]:
		field.value = count
		for resource: String in unit.cost:
			if int(unit.cost[resource]) <= 0:
				continue
			var label: Label = recruit.cost_labels[resource]
			if not check(label.text == game.UiKit.compact(int(unit.cost[resource]) * count), "cost of %s × %d" % [resource, count]): return
			if not check(str(recruit.cost_cells[resource].tooltip_text).ends_with(": %d" % (int(unit.cost[resource]) * count)), "exact cost tooltip %s" % resource): return
		if not check(recruit.clock.text == game.v6_panels.duration(expected_seconds(unit, "B12", count)), "time of × %d" % count): return
	(node("RecruitMax") as Button).pressed.emit()
	if not check(int(field.value) == recruit.max_quantity(unit) and int(field.value) > 13, "max fills the largest batch"): return
	cases.append({"case":"quantity", "max":int(field.value)})

	# Train: the quote, then exactly this order.
	field.value = 5
	var stock_before: Dictionary = game.state.v6.stock.duplicate()
	(node("RecruitTrain") as Button).pressed.emit()
	if not check(await wait_for(func(): return not recruit.submitting and not game.command_in_progress and pending().size() == 1), "training accepted"): return
	var order: Dictionary = pending()[0]
	if not check(order.kind == "train" and order.unit == "ENG-04" and int(order.quantity) == 5 and str(order.building) == "B12", "server order is the shown one " + str(order)): return
	if not check(int(order.ends_at) - int(order.starts_at) == expected_seconds(unit, "B12", 5), "server time is the shown time"): return
	for resource: String in unit.cost:
		if int(unit.cost[resource]) > 0 and not check(int(stock_before[resource]) - int(game.state.v6.stock[resource]) == int(unit.cost[resource]) * 5, "server cost %s is the shown cost" % resource): return
	var log: Array = await admin("log", {})
	var kinds := log.map(func(r): return [r.get("kind"), r.get("intent")])
	if not check(kinds.has(["v6quote", "train"]) and kinds.has(["v6", "train"]), "quote then train intent " + str(kinds)): return
	cases.append({"case":"train", "order":order.id})

	# In progress: queue card with bar and timer, busy mark on the rail.
	if not check(await wait_for(func(): return node("RecruitOrder") != null), "in-progress card"): return
	if not check(node("RecruitProgress") is ProgressBar and (node("RecruitTimeLeft") as Label).text != "", "progress bar and timer"): return
	if not check(node("RailB12").busy, "rail marks the busy building"): return
	if not check(node("RecruitTrain") == null or (node("RecruitTrain") as Button).text == "В очередь", "next order queues"): return
	cases.append({"case":"progress"})

	# Speed-up opens the items for this order; back returns to the range.
	(node("RecruitSpeedup") as Button).pressed.emit()
	if not check(await wait_for(func(): return game.modal_title.text == "Ускорить работу"), "speed-ups open"): return
	if not check(not recruit.is_open() and node("UnitStage") == null, "stage freed when the window changes"): return
	(node("SpeedBack") as Button).pressed.emit()
	if not check(await wait_for(func(): return recruit.is_open() and recruit.type == "B12"), "back to training"): return
	cases.append({"case":"speedups"})

	# Cancel: two taps.
	var stop: Button = node("RecruitCancel")
	stop.pressed.emit()
	if not check(pending().size() == 1 and stop.text == "Точно отменить?", "first tap asks"): return
	stop.pressed.emit()
	if not check(await wait_for(func(): return not recruit.submitting and pending().is_empty() and node("RecruitOrder") == null), "order cancelled"): return
	cases.append({"case":"cancel"})

	# Details and back.
	(node("RecruitDetails") as Button).pressed.emit()
	if not check(node("RecruitStats") is GridContainer, "details sheet"): return
	(node("RecruitDetails") as Button).pressed.emit()
	if not check(node("RecruitStats") == null and node("RecruitTrain") is Button, "details close"): return

	# Siege workshop: the ram; then close frees the stage and its viewport.
	(node("RailB17") as BaseButton).pressed.emit()
	if not check(await wait_for(func(): return recruit.type == "B17" and recruit.unit_id == "SIEGE-RAM-01"), "siege workshop"): return
	var weak_stage: WeakRef = weakref(node("UnitStage"))
	game.close_modal()
	await process_frame
	await process_frame
	if not check(weak_stage.get_ref() == null, "stage freed on close"): return
	cases.append({"case":"close"})

	var summary: Dictionary = await admin("summary", {})
	if not check(int(summary.legacy) == 0, "no legacy commands"): return
	var report := {"status":"passed", "checks":checks, "cases":cases, "open_ms":snappedf(open_ms, 0.01), "fixture":"synthetic localhost"}
	var path := OS.get_environment("DRENOVAR_QA_REPORT")
	if not path.is_empty():
		var file := FileAccess.open(path, FileAccess.WRITE)
		file.store_string(JSON.stringify(report))
		file.close()
	print(JSON.stringify(report))
	game.queue_free()
	await process_frame
	await process_frame
	quit()
