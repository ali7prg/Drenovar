extends SceneTree

var failures: Array[String] = []
var checks := 0

func check(value: bool, description: String) -> void:
	checks += 1
	if not value:
		failures.append(description)
		push_error(description)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	await process_frame
	game.set_process(false)
	for viewport_size in [Vector2i(1366, 630), Vector2i(1194, 630), Vector2i(1493, 630)]:
		root.size = viewport_size
		await process_frame
		await process_frame
		var logical_size := root.get_visible_rect().size
		print("QA size physical=", viewport_size, " logical=", logical_size)
		var previous_end := 0.0
		for key in game.resource_buttons:
			var b: Button = game.resource_buttons[key]
			var rect := b.get_global_rect()
			check(rect.position.x >= previous_end and rect.end.x <= logical_size.x - 40, "HUD resource overlap or clipping: " + key)
			check(rect.size.y <= 44.1, "Resource strip unexpectedly tall")
			check(b.get_theme_stylebox("normal").bg_color.a == 0, "Resource card background remains")
			previous_end = rect.end.x
		for scene in ["city", "world"]:
			if scene != game.map_name:
				await game.show_scene(scene)
			var stage = game.stage
			for view_zoom in ([32.0, 70.0, 110.0] if scene == "city" else [45.0, 100.0, 260.0]):
				stage.target = Vector3.ZERO
				stage.zoom = view_zoom
				stage.world_yaw = 0 if scene == "city" else 0.7
				stage.update_camera(0, true)
				stage.begin_direct_manipulation()
				var origin := logical_size * Vector2(0.45, 0.48)
				var destination := origin + Vector2(37, 19)
				var anchor: Vector3 = stage.ground_at(origin)
				stage.drag_between(origin, destination)
				print("ANCHOR ", scene, " z=", view_zoom, " error=", stage.camera.unproject_position(anchor).distance_to(destination))
				check(stage.camera.unproject_position(anchor).distance_to(destination) < 0.1, "Drag anchor drift: " + scene)
				check(stage.target.is_equal_approx(stage.camera_target), "Camera still follows with lag")
				var before: Vector3 = stage.camera.position
				stage.update_camera(1.0 / 60.0)
				check(stage.camera.position.is_equal_approx(before), "Camera continues chasing after finger stops")
				anchor = stage.ground_at(destination)
				stage.pinch_between(destination, destination + Vector2(11, -7), 1.2)
				check(stage.camera.unproject_position(anchor).distance_to(destination + Vector2(11, -7)) < 0.1, "Pinch anchor drift: " + scene)
				check(is_equal_approx(stage.camera_zoom, stage.zoom), "Pinch still interpolates")
			# Scripted centering remains smooth; taking over does not jump to its target.
			stage.target += Vector3(12, 0, 6)
			stage.update_camera(1.0 / 60.0)
			check(stage.target.distance_to(stage.camera_target) > 0.1, "Scripted fly-to lost smoothing")
			var displayed: Vector3 = stage.camera_target
			stage.begin_direct_manipulation()
			check(stage.target == displayed, "Touch interrupts fly-to with a jump")
	# Exercise real touch handlers, including canceled release and pinch-to-one-finger transition.
	await game.show_scene("city")
	var touch := InputEventScreenTouch.new()
	touch.index = 0
	touch.position = Vector2(500, 280)
	touch.pressed = true
	game._unhandled_input(touch)
	var drag := InputEventScreenDrag.new()
	drag.index = 0
	drag.position = Vector2(530, 290)
	drag.relative = Vector2(30, 10)
	game._input(drag)
	check(game.stage.camera_target == game.stage.target, "Real handler delays pan")
	touch.index = 1
	touch.position = Vector2(700, 280)
	game._unhandled_input(touch)
	drag.index = 1
	drag.position = Vector2(740, 280)
	drag.relative = Vector2(40, 0)
	game._input(drag)
	touch.pressed = false
	game._input(touch)
	drag.index = 0
	drag.position = Vector2(540, 290)
	drag.relative = Vector2(10, 0)
	game._input(drag)
	check(game.fingers.size() == 1, "Pinch release loses surviving finger")
	touch.index = 0
	touch.canceled = true
	game._input(touch)
	check(game.fingers.is_empty() and not game.tap_candidate, "Canceled gesture sticks")
	game.show_economy("food")
	var saved_target: Vector3 = game.stage.target
	game._input(drag)
	check(game.stage.target == saved_target, "Modal allows camera gesture")
	game.close_modal()
	var saved_food: int = game.balance("food")
	game.state.city.demo.wallet.food = game.capacity() + 1500
	game.show_economy("food")
	check(game.modal_body.find_children("*", "Label", true, false).any(func(label): return label.text.begins_with("Производство приостановлено")), "Over-cap message missing")
	game.close_modal()
	await process_frame
	game.state.city.demo.wallet.food = mini(saved_food, game.capacity() - 1)
	game.show_economy("food")
	check(not game.modal_body.find_children("*", "Label", true, false).any(func(label): return label.text.begins_with("Производство приостановлено")), "Under-cap message incorrect")
	game.state.city.demo.wallet.food = saved_food
	print("QA_CAMERA_HUD checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
