extends SceneTree

# Construction window: HUD button in the city, cards with portraits for every core
# building, category tabs, details with cost/time and a reason when building is
# not possible; opens fast.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func cards(game) -> Array:
	return game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.is_in_group("build_card"))

func touch(index: int, at: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.position = at
	event.pressed = pressed
	root.push_input(event, true)

func drag(index: int, from: Vector2, to: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = index
	event.position = to
	event.relative = to - from
	root.push_input(event, true)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	var capture := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture = argument.trim_prefix("--capture=")
	check(game.nav_buttons.build.visible, "No build button in the city HUD")
	var started := Time.get_ticks_usec()
	game.nav_buttons.build.pressed.emit()
	var open_ms := (Time.get_ticks_usec() - started) / 1000.0
	check(game.modal.visible and game.modal_title.text == "Строительство", "Build button did not open the window")
	var all := cards(game)
	check(all.size() >= 15, "Only %d building cards" % all.size())
	check(all.all(func(card): return card.find_children("*", "TextureRect", true, false)[0].texture != null), "A card has no portrait")
	if not capture.is_empty():
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("build_menu.png"))
	check(game.modal.anchor_top == 1.0, "Build window is not a bottom sheet over the city")
	check(game.modal_scroll.horizontal, "Cards are not a horizontal strip")
	game.show_build_menu("military")
	check(cards(game).size() == 5, "Military tab shows %d cards" % cards(game).size())
	# A locked/built card opens details with "Выбрать место".
	var details_card = cards(game)[-1]
	details_card.pressed.emit()
	await process_frame
	var confirm := game.modal_body.find_child("BuildConfirm", true, false) as Button
	check(confirm != null, "Details have no build action")
	if not capture.is_empty():
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("build_details.png"))
	# Placement: a buildable definition, ghost dragged by finger onto another plot.
	game.close_modal()
	var definition: Dictionary = game.data.buildings.filter(func(d): return d.id == "RES-01")[0]
	game.start_placement(definition)
	await process_frame
	check(not game.placing.is_empty(), "Placement mode did not start")
	check(is_instance_valid(game.stage.placement_ghost), "No ghost building shown")
	check(game.placement_bar.visible and game.placement_confirm != null, "No confirm bar")
	for i in 4:
		await process_frame
	var first_plot: String = game.placing.plot.id
	var others: Array = game.placing.plots.filter(func(p): return p.plot.id != first_plot)
	check(not others.is_empty(), "Only one free plot in the demo city")
	if not others.is_empty():
		var goal: Dictionary = others[0]
		var start: Vector2 = game.placement_screen_point()
		var finish: Vector2 = game.stage.camera.unproject_position(goal.position + Vector3.UP * 3.0)
		touch(0, start, true)
		await process_frame
		check(game.placement_finger == 0, "Finger on the ghost did not pick it up")
		var camera_before: Vector3 = game.stage.target
		var steps := 8
		var previous := start
		for step in range(1, steps + 1):
			var point := start.lerp(finish, float(step) / steps)
			drag(0, previous, point)
			previous = point
			await process_frame
		check(game.stage.target.distance_to(camera_before) < 2.0 or finish.x < 64 or finish.x > root.size.x - 64, "Dragging the ghost moved the camera")
		touch(0, finish, false)
		await process_frame
		check(game.placing.plot.id == goal.plot.id, "Ghost did not snap to the plot under the finger (%s)" % game.placing.plot.id)
		check(game.placement_finger == -1, "Ghost still held after release")
	if not capture.is_empty():
		await create_timer(0.4).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("build_placement.png"))
	game.placement_bar.find_child("PlacementCancel", true, false).pressed.emit()
	check(game.placing.is_empty() and not is_instance_valid(game.stage.placement_ghost), "Cancel left placement active")
	game.close_modal()
	await game.show_scene("world")
	check(not game.nav_buttons.build.visible, "Build button shown on the world map")
	check(open_ms < 120.0, "Build window took %.0f ms" % open_ms)
	print("QA_BUILD_MENU open_ms=", snappedf(open_ms, 0.1), " cards=", all.size())
	print("QA_BUILD_MENU checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
