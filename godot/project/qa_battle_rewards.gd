extends SceneTree

const ReportFeed = preload("res://src/battle_results.gd")

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, detail: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(detail)

func advance(game: Node, server_ms: int) -> void:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + "/test/clock?time=" + str(server_ms), [], HTTPClient.METHOD_POST)
	var response: Array = await client.request_completed
	client.queue_free()
	check(response[1] == 204, "Fixture clock update failed")

func has_label(parent: Node, text: String) -> bool:
	return parent.find_children("*", "Label", true, false).any(func(label): return label.text == text)

func check_battle(game: Node, city: bool) -> void:
	var target: Dictionary = (game.state.encounters if city else game.state.world.encounters)[0]
	var order := {"kind":"deploy" if city else "worldMarch", "encounterId":target.id,
		"units":{"ENG-03":int(game.state.healthy.get("ENG-03", 0))}}
	if not city:
		order.worldKind = "velkor"
	var start: Dictionary = await game.request("command", order)
	if not start.has("city"):
		check(false, str(start))
		return
	game.accept(start)
	var march: Dictionary = (start.armies if city else start.world.armies).back()
	var pre_food: int = int(game.balance("food"))
	var pre_xp: int = int(game.state.city.progress.xp)
	var item_id: String = target.spec.item
	var pre_items: int = int(game.state.items.get(item_id, 0))
	await advance(game, int(march.arrivesAt) + 10)
	var fighting: Dictionary = await game.request("state")
	var army: Dictionary = (fighting.armies if city else fighting.world.armies).back()
	await advance(game, int(army.battleEndsAt) + 1)
	var settled: Dictionary = await game.request("state")
	var report: Dictionary = settled.reports.back()
	check(report.outcome == "victory", "Fixture army must defeat " + target.spec.name)
	if report.outcome != "victory":
		return
	check(report.creature.species == target.spec.id, "Wrong reward report")
	check(int(settled.city.demo.wallet.food) - pre_food == int(report.rewards.resources.food), "Server food reward did not match the balance")
	check(int(settled.items[item_id]) - pre_items == int(report.rewards.items[item_id]), "Server material reward did not match inventory")
	check(int(settled.city.progress.xp) - pre_xp == int(report.rewards.xp), "Server XP did not match the report")
	if not city:
		game.open_modal("Проверка открытого окна")
	game.accept(settled)
	game.battle_results.ready_at = 0
	game.update_battle_result_notice()
	if not city:
		check(game.result_notice.visible and game.modal_title.text == "Проверка открытого окна", "Result interrupted an open panel or hid the notice")
		game.result_notice.pressed.emit()
	check(game.result_open and game.modal_title.text == "Победа", "Victory popup did not open")
	check(has_label(game.modal_body, "Еда +" + game.format_balance(int(report.rewards.resources.food))), "Popup did not show exact food")
	check(has_label(game.modal_body, "Опыт +" + game.format_balance(int(report.rewards.xp))), "Popup did not show exact XP")
	check(has_label(game.modal_body, ("Когти" if city else "Рога") + " +" + game.format_balance(int(report.rewards.items[item_id]))), "Popup did not show the trophy")
	game.close_modal()
	var unpaired_release := InputEventMouseButton.new()
	unpaired_release.button_index = MOUSE_BUTTON_LEFT
	unpaired_release.position = game.stage.camera.unproject_position(game.stage.place_markers[0].position)
	game._unhandled_input(unpaired_release)
	check(not game.modal.visible, "Closing the result selected a map marker")
	var reopened := ReportFeed.new()
	reopened.observe(game.player_id, settled.reports)
	check(reopened.pending.is_empty(), "Read result reappeared after reopening the game")
	game.accept(settled)
	game.update_battle_result_notice()
	check(not game.modal.visible, "Same result reappeared")
	await advance(game, int(army.battleEndsAt) + int(march.travelMs) + 1000)
	game.accept(await game.request("state"))

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	await game.show_scene("world")
	await check_battle(game, false)
	await game.show_scene("city")
	await check_battle(game, true)
	print("QA_BATTLE_REWARDS checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
