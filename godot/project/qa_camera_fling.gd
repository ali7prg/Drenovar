extends SceneTree

# Touch-driven camera checks through the real input path (push_input):
# quick swipe glides and decays to rest, slow drag-and-hold does not glide,
# a new touch stops the glide at once, a tap selects without moving the camera,
# and an opened window cancels the glide.

var failures: Array[String] = []
var checks := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func touch(at: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = 0
	event.position = at
	event.pressed = pressed
	root.push_input(event, true)

func drag(from: Vector2, to: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = 0
	event.position = to
	event.relative = to - from
	root.push_input(event, true)

func swipe(game: Node, from: Vector2, step: Vector2, frames: int, hold_frames := 0) -> void:
	touch(from, true)
	var at := from
	# Real 60 Hz event spacing: headless frames are not vsynced.
	for i in frames:
		await create_timer(0.016).timeout
		drag(at, at + step)
		at += step
	if hold_frames > 0:
		await create_timer(hold_frames * 0.016).timeout
	touch(at, false)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.smoke = true
	# Let the launch screen (queue_free in headless) leave the tree.
	await process_frame
	await process_frame
	var stage = game.stage
	var center := Vector2(683, 330)
	# 1. Quick swipe: glides beyond the release point, then stops.
	await swipe(game, center, Vector2(-40, 0), 6)
	var at_release: Vector3 = stage.target
	check(game.fling_velocity.length() > game.FLING_MIN_SPEED, "Quick swipe did not start a glide")
	await create_timer(1.6).timeout
	check(stage.target.distance_to(at_release) > 0.5, "Glide did not move the camera")
	check(game.fling_velocity == Vector2.ZERO, "Glide never came to rest")
	# 2. Drag then hold still before lifting: no glide.
	await swipe(game, center, Vector2(-40, 0), 4, 12)
	check(game.fling_velocity == Vector2.ZERO, "Paused finger still glided")
	# 3. New touch stops the glide immediately.
	await swipe(game, center, Vector2(0, 45), 6)
	check(game.fling_velocity != Vector2.ZERO, "Second swipe did not glide")
	touch(center, true)
	var held: Vector3 = stage.target
	await process_frame
	await process_frame
	check(game.fling_velocity == Vector2.ZERO and stage.target.is_equal_approx(held), "Touch did not stop the glide")
	touch(center, false)
	await process_frame
	# 4. Tap: no movement, no glide.
	var before_tap: Vector3 = stage.target
	touch(center + Vector2(200, 0), true)
	await process_frame
	touch(center + Vector2(200, 0), false)
	await process_frame
	game.close_modal()
	check(stage.target.is_equal_approx(before_tap) and game.fling_velocity == Vector2.ZERO, "Tap moved the camera")
	check(game.fingers.is_empty(), "Tap left a stale finger")
	# 5. Window opened during a glide cancels it.
	await swipe(game, center, Vector2(35, 20), 6)
	game.show_controls_menu()
	await process_frame
	check(game.fling_velocity == Vector2.ZERO, "Glide survived an opened window")
	game.close_modal()
	print("QA_CAMERA_FLING checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
