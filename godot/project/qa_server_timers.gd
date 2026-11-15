extends SceneTree

# Timers against the real server v92 (godot/tools/test-realm.mjs on 127.0.0.1:8417,
# isolated in-memory realm). Run with: -- --server=http://127.0.0.1:8417
#  1. two fellings in a row: countdown from the server's job, never restarted,
#     wood only from the server, exactly once; tree felled when the server says so;
#  2. a second felling order while one runs is refused, nothing is doubled;
#  3. a lost answer: the same command repeated with its key is applied once;
#  4. an upgrade at the edge of its timer: one ms before the end nothing changes,
#     at the end the level rises exactly once;
#  5. training ends: soldiers appear exactly at the end, once;
#  6. speedup pressed twice: one item spent, the order shortened once;
#  7. no link: zero is not shown as done; the link back restores the state.

var checks := 0
var failures := 0
var game

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
	else:
		print("ok  ", description)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func set_clock(value: float) -> void:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + "/test/clock?time=" + str(int(value)), [], HTTPClient.METHOD_POST)
	await client.request_completed
	client.queue_free()

func fresh_state() -> void:
	game.poll = 1.0e6
	var before: float = float(game.state.get("serverTime", 0.0))
	var asked := Time.get_ticks_msec()
	var response: Dictionary = await game.request("state")
	game.accept(response)

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var connected_ok: bool = await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.player_id.is_empty() and game.state.city.get("kingdom") is Dictionary, 60.0)
	check(connected_ok, "Connected to the local server v92")
	if not connected_ok:
		quit(1)
		return
	var stage = game.stage
	# --- 1. Two fellings in a row.
	var standing: Array = stage.selectable_trees.filter(func(t): return not t.id in game.state.city.progress.felled)
	standing.sort_custom(func(a, b): return stage.array_point(a.p).distance_squared_to(stage.camera_target) < stage.array_point(b.p).distance_squared_to(stage.camera_target))
	var felled_count := 0
	for tree in standing:
		if felled_count == 2:
			break
		var wood_before: int = game.balance("wood")
		var ok: bool = await game.command({"kind": "resource", "action": "tree", "id": tree.id})
		if not ok:
			continue
		await process_frame
		await process_frame
		var job: Dictionary = game.shown_job
		check(job.get("confirmed", false) and job.get("tree", "") == tree.id, "Felling %d: countdown from the server job" % (felled_count + 1))
		var ends := float(job.get("ends", 0.0))
		var restarted := [false]
		var granted_early := [false]
		var done := await wait_until(func():
			if not game.shown_job.is_empty() and absf(float(game.shown_job.ends) - ends) > 1.0:
				restarted[0] = true
			if game.timer_now() < ends - 50.0 and tree.id in game.state.city.progress.felled:
				granted_early[0] = true
			return tree.id in game.state.city.progress.felled, 15.0)
		# Zero on screen is the server's end plus the measured round trip: the answer
		# should arrive at that moment (within 0.5 s either side).
		var late: float = game.timer_now() - game.display_end(ends)
		check(done, "Felling %d: the server confirmed the tree" % (felled_count + 1))
		check(not restarted[0], "Felling %d: the countdown never restarted" % (felled_count + 1))
		check(not granted_early[0], "Felling %d: not felled before the timer end" % (felled_count + 1))
		check(absf(late) < 500.0, "Felling %d: done %.0f ms from zero on screen (|x| < 0.5 s, round trip %.0f ms)" % [felled_count + 1, late, game.expected_latency_ms()])
		var gained: int = game.balance("wood") - wood_before
		await fresh_state()
		# Production keeps adding a little wood every second; a second reward would add
		# a whole tree (50+).
		var drift: int = game.balance("wood") - wood_before - gained
		check(gained > 0 and drift >= 0 and drift < 20, "Felling %d: +%d wood, not doubled by the next state (production +%d)" % [felled_count + 1, gained, drift])
		check(game.shown_job.is_empty(), "Felling %d: no job after completion" % (felled_count + 1))
		felled_count += 1
	check(felled_count == 2, "Two trees felled in a row")
	# --- 2. Second order while one runs.
	var next_trees: Array = stage.selectable_trees.filter(func(t): return not t.id in game.state.city.progress.felled)
	var first_ok: bool = false
	var second_ok: bool = true
	for i in range(0, next_trees.size() - 1):
		first_ok = await game.command({"kind": "resource", "action": "tree", "id": next_trees[i].id})
		if first_ok:
			second_ok = await game.command({"kind": "resource", "action": "tree", "id": next_trees[i + 1].id})
			break
	check(first_ok and not second_ok, "A second felling while one runs is refused")
	check(game.message.text.begins_with("Не выполнено"), "The refusal is shown: " + game.message.text)
	await wait_until(func(): return game.state.city.progress.job == null, 12.0)
	# --- 2b. Training answers at once: the order is in the queue before the server
	# replies, the button is free again, the server's answer replaces the row.
	await fresh_state()
	var range_building: Dictionary = game.state.city.buildings.filter(func(b): return b.type == "MIL-01")[0]
	game.open_recruitment(range_building, "ENG-09", 1)
	var food_before := int(game.state.city.demo.wallet.food)
	var queued_before: int = game.state.city.military.queues.get(range_building.id, []).size()
	var train_button: Button = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text.begins_with("Обучить"))[0]
	var pressed_at := Time.get_ticks_msec()
	train_button.pressed.emit()
	var rows: String = " | ".join(game.modal_body.find_children("*", "Label", true, false).map(func(l): return l.text))
	check("отправляем…" in rows, "Order shown in the queue at once (%d ms)" % (Time.get_ticks_msec() - pressed_at))
	check(game.modal.visible, "Recruitment stays open")
	await wait_until(func(): return game.pending_training.get(range_building.id, []).is_empty(), 15.0)
	await process_frame
	var queue_now: Array = game.state.city.military.queues.get(range_building.id, [])
	check(queue_now.size() == queued_before + 1, "Server order replaced the row (%d → %d)" % [queued_before, queue_now.size()])
	var spent: int = food_before - int(game.state.city.demo.wallet.food)
	check(spent > 20 and spent <= 30, "Charged once by the server (food %d → %d; 30 minus farm production)" % [food_before, int(game.state.city.demo.wallet.food)])
	await create_timer(0.7).timeout
	var ready_again: Array = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text.begins_with("Обучить"))
	check(not ready_again.is_empty() and not ready_again[0].disabled, "Train button ready again")
	game.close_modal()
	await set_clock(float(queue_now[-1].endsAt))
	await fresh_state()
	# --- 3. Lost answer repeated with the same key.
	await fresh_state()
	var wallet_before: Dictionary = game.state.city.demo.wallet.duplicate()
	var barracks: Dictionary = game.state.city.buildings.filter(func(b): return b.type == "MIL-01")[0]
	var train := {"kind": "train", "buildingId": barracks.id, "unitId": "ENG-09", "quantity": 2, "paidTraining": true,
		"requestId": "qa-train-%d" % Time.get_ticks_msec()}
	var once: Dictionary = await game.request("command", train, train.requestId)
	var again: Dictionary = await game.request("command", train, train.requestId)
	game.accept(again)
	var queue: Array = game.state.city.military.queues.get(barracks.id, [])
	check(once.has("city") and queue.size() == 1 and int(queue[0].quantity) == 2, "Repeated command made one order")
	check(int(game.state.city.demo.wallet.food) == int(wallet_before.food) - 60, "Repeated command charged once (food %d → %d)" % [int(wallet_before.food), int(game.state.city.demo.wallet.food)])
	# --- 5. Training ends exactly at its end, once.
	var owned_before := int(game.state.healthy.get("ENG-09", 0))
	var train_ends := float(queue[0].endsAt)
	await set_clock(train_ends - 1.0)
	await fresh_state()
	check(int(game.state.healthy.get("ENG-09", 0)) == owned_before, "No soldiers 1 ms before the end")
	await set_clock(train_ends)
	await fresh_state()
	check(int(game.state.healthy.get("ENG-09", 0)) == owned_before + 2, "Soldiers at the end (%d → %d)" % [owned_before, int(game.state.healthy.get("ENG-09", 0))])
	await fresh_state()
	check(int(game.state.healthy.get("ENG-09", 0)) == owned_before + 2, "Soldiers granted once")
	# --- 4. Upgrade at the edge of its timer (first building the server accepts).
	await game.command({"kind": "kingdom", "action": "enter"})
	var camp: Dictionary = game.state.city.buildings.filter(func(b): return b.type == "RES-01")[0]
	await set_clock(float(game.state.serverTime) + 120000.0)
	await game.command({"kind": "kingdom", "action": "collect", "buildingId": camp.id})
	var upgraded := {}
	for building in game.state.city.buildings:
		if await game.command({"kind": "kingdom", "action": "upgrade", "buildingId": building.id, "expectedLevel": int(building.level)}):
			upgraded = building
			break
	check(not upgraded.is_empty(), "An upgrade was accepted: " + game.message.text)
	if not upgraded.is_empty():
		await process_frame
		await process_frame
		var order: Dictionary = game.construction_order()
		var level := int(upgraded.level)
		check(game.shown_site.get("confirmed", false) and float(game.shown_site.get("ends", 0.0)) == float(order.endsAt), "Upgrade countdown from the server order")
		# --- 6. Speedup pressed twice: one item, one shortening.
		var item_id := ""
		for id in ["construction-1", "construction-2"]:
			if int(game.state.get("items", {}).get(id, 0)) > 0:
				item_id = id
				break
		check(not item_id.is_empty(), "Server granted a construction speedup for the guide (items %s)" % [game.state.get("items", {})])
		if not item_id.is_empty():
			var count_before := int(game.state.items[item_id])
			var ends_before := float(order.endsAt)
			game.preview_speedup("construction", order, "", item_id)
			var apply: Button = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text == "Применить")[0]
			apply.pressed.emit()
			apply.pressed.emit()
			await wait_until(func(): return not game.speedup_in_flight and not game.command_in_progress, 15.0)
			await fresh_state()
			var shortened := ends_before - float(game.construction_order().get("endsAt", ends_before))
			check(int(game.state.items.get(item_id, 0)) == count_before - 1, "Double press spent one item (%d → %d)" % [count_before, int(game.state.items.get(item_id, 0))])
			check(is_equal_approx(shortened, float(game.data.speedItems[item_id].seconds) * 1000.0), "Order shortened once (%.0f ms)" % shortened)
			order = game.construction_order()
		var edge := float(order.endsAt)
		await set_clock(edge - 1.0)
		await fresh_state()
		var current: Dictionary = game.state.city.buildings.filter(func(b): return b.id == upgraded.id)[0]
		check(int(current.level) == level and not game.construction_order().is_empty(), "Level unchanged 1 ms before the end")
		await set_clock(edge)
		await fresh_state()
		current = game.state.city.buildings.filter(func(b): return b.id == upgraded.id)[0]
		check(int(current.level) == level + 1 and game.construction_order().is_empty(), "Level %d → %d exactly at the end" % [level, int(current.level)])
		await fresh_state()
		current = game.state.city.buildings.filter(func(b): return b.id == upgraded.id)[0]
		check(int(current.level) == level + 1, "Level raised once")
	# --- 7. No link: zero is not shown as done; the link back restores the state.
	var endpoint: String = game.endpoint
	game.endpoint = "http://127.0.0.1:9"
	for i in 3:
		await game.poll_account_state()
	check(game.timer_end_label() == "Нет связи · ждём сервер", "Offline zero label: " + game.timer_end_label())
	game.endpoint = endpoint
	game.api.configure(endpoint)
	await game.poll_account_state()
	await game.poll_account_state()
	check(game.server_reachable() and game.timer_end_label() == "Завершаем…", "Link restored")
	print("QA_SERVER_TIMERS checks=%d failures=%d stale=%d" % [checks, failures, game.stale_responses])
	quit(0 if failures == 0 else 1)
