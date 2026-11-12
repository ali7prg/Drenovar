extends SceneTree

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func has_label(game: Node, expected: String) -> bool:
	return game.modal_body.find_children("*", "Label", true, false).any(
		func(label): return label.text == expected
	)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	if game.player_id.is_empty():
		push_error("Start the seeded web v91 QA server and pass --server=http://127.0.0.1:4187")
		quit(1)
		return
	var start_food: int = game.balance("food")
	check(start_food >= 2400 and start_food < 2420 and game.capacity() == 2800, "Seed balance or capacity differs")
	game.show_economy("food")
	check(has_label(game, "+120/мин · предел производства — 2 800"), "Farm should be producing below the limit")
	await create_timer(1.25).timeout
	var updated: Dictionary = await game.request("state")
	game.accept(updated)
	check(game.balance("food") > start_food, "Server farm production did not increase food")
	check(has_label(game, "Еда — " + game.format_balance(game.balance("food"))), "Open economy panel did not update")
	game.show_starter_goals()
	check(has_label(game, "Первые шаги · 2/5"), "Initial starter progress differs")
	var claim := game.modal_body.find_children("*", "Button", false, false).filter(
		func(button): return button.text == "Получить награду"
	).front() as Button
	check(claim != null and not claim.disabled, "Training reward should be available")
	if claim == null or claim.disabled:
		quit(1)
		return
	var before: int = game.balance("food")
	claim.pressed.emit()
	var deadline := Time.get_ticks_msec() + 6000
	while game.command_in_progress and Time.get_ticks_msec() < deadline:
		await process_frame
	check(game.balance("food") - before >= 60 and game.balance("food") - before <= 62, "Server did not credit the 60-food reward")
	check(game.modal.visible and has_label(game, "Первые шаги · 3/5"), "Claim did not advance the open panel")
	var refreshed: Dictionary = await game.request("state")
	check(refreshed.city.kingdom.guide.starterClaims71.has("train"), "Claim was missing after reloading state")
	var excessive := refreshed.duplicate(true)
	excessive.city.demo.wallet.food = 4300
	game.show_economy("food")
	game.accept(excessive)
	check(has_label(game, "Еда — 4 300"), "Over-cap food balance was clipped or stale")
	check(has_label(game, "Производство приостановлено · предел производства — 2 800"), "Over-cap production status differs")
	game.show_report({"creature":{"name":"Тенерис I"}, "outcome":"victory", "rewards":{"resources":{"food":1500}}})
	check(has_label(game, "Еда +1 500"), "Battle report did not display the credited amount")
	game.accept(refreshed)
	await game.show_scene("world")
	game.stage.world_yaw = 0.6
	game.stage.zoom = 37
	game.stage.target = Vector3(70, 0, 25)
	game.show_world_overview()
	game.stage.update_camera(0, true)
	check(is_zero_approx(game.stage.world_yaw), "Full world view did not reset rotation")
	for i in 8:
		var point: Vector3 = game.stage.terrain_bounds.get_endpoint(i)
		check(root.get_visible_rect().has_point(game.stage.camera.unproject_position(point)), "Map bounds were clipped")
	var creature: Dictionary = game.state.world.encounters[0].duplicate(true)
	creature.status = "defeated"
	creature.hp = 0
	var target: Vector3 = game.stage.target
	var zoom: float = game.stage.zoom
	game.inspect_encounter(creature)
	check(game.stage.target == target and game.stage.zoom == zoom, "Defeated creature moved the camera")
	game.show_relocation()
	check(game.relocation_pins.visible and not game.modal.visible, "Relocation mode did not open on map")
	var site: Dictionary = game.stage.empty_plots[0]
	game.pick_marker(game.stage.camera.unproject_position(site.position))
	check(game.modal.visible and game.modal_title.text == "Свободное место", "Vacant location did not open confirmation")
	game.close_modal()
	check(not game.relocation_pins.visible and not game.modal.visible, "Close did not dismiss relocation")
	print("QA_WEB91 checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
