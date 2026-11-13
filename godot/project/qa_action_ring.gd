extends SceneTree

# Building tap opens the action ring (not a window), with context actions; the
# ring follows the camera, an action opens its window, other taps close it.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func captions(ring: Node) -> Array:
	return ring.buttons.map(func(b): return b.tooltip_text)

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
	var stage = game.stage
	var barracks: Dictionary = game.recruitment_buildings()[0]
	var marker: Dictionary = {}
	for item in stage.place_markers:
		if item.get("kind") == "building" and item.item.id == barracks.id:
			marker = item
	check(not marker.is_empty(), "Barracks marker missing")
	stage.target = marker.position - Vector3.UP * 2.0
	stage.update_camera(0, true)
	await process_frame
	game.pick_marker(stage.camera.unproject_position(marker.position))
	await process_frame
	var ring = game.action_ring
	check(ring.is_open() and not game.modal.visible, "Building tap did not open the ring")
	check("Обучить" in captions(ring), "Military building ring has no training action: " + str(captions(ring)))
	check(captions(ring)[0] in ["Улучшить", "Сведения"], "First action is not upgrade/info")
	var before: Vector2 = ring.buttons[0].position
	if not capture.is_empty():
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(capture.path_join("ring.png"))
	stage.target += Vector3(3, 0, 0)
	stage.update_camera(0, true)
	await process_frame
	await process_frame
	check(ring.buttons[0].position != before, "Ring did not follow the building")
	var train: Button = ring.buttons[captions(ring).find("Обучить")]
	train.pressed.emit()
	await process_frame
	check(not ring.is_open() and game.modal.visible, "Training action did not open its window")
	game.close_modal()
	game.pick_marker(stage.camera.unproject_position(marker.position))
	check(ring.is_open(), "Ring did not reopen")
	game.open_modal("QA")
	check(not ring.is_open(), "Opening a window left the ring open")
	game.close_modal()
	game.pick_marker(stage.camera.unproject_position(marker.position))
	await create_timer(0.35).timeout
	var touch := InputEventScreenTouch.new()
	touch.pressed = true
	touch.position = Vector2(80, 560)
	game._unhandled_input(touch)
	check(not ring.is_open(), "A tap elsewhere did not close the ring")
	print("QA_ACTION_RING checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
