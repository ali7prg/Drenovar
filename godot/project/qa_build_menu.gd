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
	return game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.custom_minimum_size.y == 196)

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
	game.show_build_menu("military")
	check(cards(game).size() == 5, "Military tab shows %d cards" % cards(game).size())
	cards(game)[0].pressed.emit()
	await process_frame
	var confirm := game.modal_body.find_child("BuildConfirm", true, false) as Button
	check(confirm != null, "Details have no build action")
	if not capture.is_empty():
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("build_details.png"))
	game.close_modal()
	await game.show_scene("world")
	check(not game.nav_buttons.build.visible, "Build button shown on the world map")
	check(open_ms < 120.0, "Build window took %.0f ms" % open_ms)
	print("QA_BUILD_MENU open_ms=", snappedf(open_ms, 0.1), " cards=", all.size())
	print("QA_BUILD_MENU checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
