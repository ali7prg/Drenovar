extends SceneTree

var checks := 0
var failures := 0
var capture_dir := ""

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func find_button(parent: Node, title: String) -> Button:
	for button: Button in parent.find_children("*", "Button", true, false):
		if button.text == title:
			return button
	return null

func settle_and_capture(name: String) -> void:
	await process_frame
	await process_frame
	if not capture_dir.is_empty():
		await create_timer(0.34).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture_dir.path_join(name + ".png"))

func check_safe(game: Node) -> void:
	var bounds := Rect2(Vector2.ZERO, root.get_visible_rect().size)
	check(bounds.encloses(game.modal.get_global_rect()), "Panel went outside the viewport: " + game.modal_title.text)
	check(game.modal.get_global_rect().encloses(game.modal_scroll.get_global_rect()), "Scroll escaped panel")

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture_dir = argument.trim_prefix("--capture=")
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	if game.player_id.is_empty():
		game.player_id = "fixture"
		game.state = game.state.duplicate(true)
		game.state.healthy = {"ENG-09": 18, "ENG-01": 6}
	var barracks: Dictionary = game.recruitment_buildings()[0]
	game.inspect_building(barracks)
	var recruit := find_button(game.modal_body, "Подготовка войск")
	check(recruit != null, "Recruitment could not be reached from the military building")
	recruit.pressed.emit()
	var immediate_preview := game.modal_body.find_child("RecruitPreview", true, false) as SubViewportContainer
	check(immediate_preview != null and immediate_preview.get_child_count() == 0, "Recruitment waited for the live model")
	check(immediate_preview.get_parent().get_node("PreviewFallback").texture != null, "Recruitment has no immediate portrait")
	await settle_and_capture("recruitment")
	check(game.modal_title.text.begins_with("Казармы пехоты · ур."), "Recruitment heading differs")
	check(game.modal_body.find_child("RecruitPreview", true, false) != null, "Missing 3D preview")
	check(find_button(game.modal_body, "Пеший новобранец") != null, "Missing roster card")
	check(find_button(game.modal_footer, "Готовые войска →") != null, "Missing garrison link")
	check_safe(game)
	var slider := game.modal_body.find_children("*", "HSlider", true, false)[0] as HSlider
	var at := slider.get_global_rect().get_center()
	var touch := InputEventScreenTouch.new()
	touch.pressed = true
	touch.position = at
	root.push_input(touch, true)
	var drag := InputEventScreenDrag.new()
	drag.position = at + Vector2(50, 1)
	drag.relative = Vector2(50, 1)
	root.push_input(drag, true)
	touch.pressed = false
	touch.position = drag.position
	root.push_input(touch, true)
	check(slider.value > 50, "Horizontal finger movement did not update the slider")
	check(game.modal_scroll.scroll_vertical == 0, "Slider swipe also scrolled the panel")
	find_button(game.modal_body, "10").pressed.emit()
	check(slider.value == 10, "Quantity shortcut did not update the slider")
	var selected := find_button(game.modal_body, "Копейщик")
	check(selected != null and selected.icon != null, "Missing original spearman portrait")
	selected.pressed.emit()
	await process_frame
	check(game.modal_body.find_children("*", "Label", true, false).any(func(label): return label.text == "Копейщик"), "Unit switch did not update the preview caption")
	if game.loopback:
		game.open_recruitment(barracks, "ENG-09", 2)
		var train := game.modal_body.find_children("*", "Button", true, false).filter(func(button): return button.text.begins_with("Обучить 2"))[0] as Button
		check(not train.disabled, "Training submission unexpectedly disabled")
		var wood := int(game.balance("wood"))
		var food := int(game.balance("food"))
		var coins := int(game.balance("coins"))
		train.pressed.emit()
		check(train.disabled and train.text == "Создаём заказ…", "Train button did not acknowledge the tap immediately")
		check(game.balance("wood") == wood, "The UI deducted resources before server confirmation")
		while game.command_in_progress:
			await process_frame
		var queue: Array = game.state.city.military.queues.get(barracks.id, [])
		check(queue.size() == 1 and queue[0].quantity == 2, "Recruitment action did not submit the chosen quantity")
		var charged: Dictionary = queue[0].get("chargedCost", {}) if not queue.is_empty() else {}
		check(int(charged.get("wood", -1)) == 50 and int(charged.get("food", -1)) == 60
			and int(charged.get("iron", -1)) == 0 and int(charged.get("coins", -1)) == 40,
			"Confirmed training did not record the expected cost: " + str(charged))
		check(game.balance("wood") < wood and game.balance("food") < food and game.balance("coins") < coins,
			"Confirmed training did not lower the displayed balances")
		check(game.modal_body.find_children("*", "Label", true, false).any(func(label): return label.text == "ОЧЕРЕДЬ 1 / 3"), "Queue was not refreshed after recruitment")
	game.close_modal()
	check(not game.modal.visible and game.modal_body.get_child_count() == 0, "Close did not clear the preview")
	var target: Dictionary = game.state.encounters[0]
	game.inspect_encounter(target)
	await settle_and_capture("city-target")
	check(game.modal.anchor_left == 0 and game.modal.anchor_right < 0.5, "City target is not docked on the left")
	check(find_button(game.modal_footer, "Атаковать") != null, "City attack action missing")
	check_safe(game)
	find_button(game.modal_footer, "Атаковать").pressed.emit()
	await settle_and_capture("city-march")
	check(game.modal_title.text == "Создать войско", "City order opened the wrong window")
	check(find_button(game.modal_body, "Все доступные") != null, "Missing select all action")
	check(find_button(game.modal_footer, "Марш") != null, "Missing march action")
	for amount: SpinBox in game.modal_body.find_children("*", "SpinBox", true, false):
		check(amount.get_line_edit().text.to_int() == int(amount.value), "Bulk selection left the displayed quantity out of date")
	check_safe(game)
	game.show_economy("food")
	await settle_and_capture("resources")
	check(game.modal.anchor_left == 0, "Resources did not dock on the left")
	check_safe(game)
	await game.show_scene("world")
	game.inspect_encounter(game.state.world.encounters[0])
	await settle_and_capture("world-target")
	check(game.modal.anchor_left > 0.5, "World target is not docked on the right")
	check(find_button(game.modal_footer, "Собрать отряд") != null, "Missing assemble action")
	check_safe(game)
	find_button(game.modal_footer, "Собрать отряд").pressed.emit()
	await settle_and_capture("world-march")
	check(game.modal_title.text == "Сбор отряда", "World march opened the wrong window")
	check(game.modal_footer.find_child("MarchSend", true, false).disabled, "Empty party can be sent")
	check_safe(game)
	if game.loopback:
		var quantity := game.modal_body.find_children("*", "SpinBox", true, false)[0] as SpinBox
		quantity.value = 1
		var send := game.modal_footer.find_child("MarchSend", true, false) as Button
		var deadline := Time.get_ticks_msec() + 6500
		while send.disabled and Time.get_ticks_msec() < deadline:
			await process_frame
		check(not send.disabled, "Valid world party did not get a server route")
		send.pressed.emit()
		while game.command_in_progress:
			await process_frame
		check(game.state.world.armies.size() == 1, "World send button did not create an army")
		check(game.modal_title.text == "Общий мир", "World march did not return to the directory")
	print("QA_WEB_PANELS checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
