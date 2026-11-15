extends SceneTree

# Taps on panel buttons through the real touch path (TouchScroll -> synthesized
# click), at the 1366x630 canvas used on iPhone 12. Checks: immediate pressed
# tint on touch-down, taps with natural finger roll still activate, a real
# scroll or sliding off the button does not, and footer buttons respond.

var checks := 0
var failures := 0
var hits := {}

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func touch(at: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.pressed = pressed
	event.position = at
	root.push_input(event, true)

func drag(from: Vector2, to: Vector2, steps := 4) -> void:
	for step in steps:
		var event := InputEventScreenDrag.new()
		var a := from.lerp(to, float(step) / steps)
		var b := from.lerp(to, float(step + 1) / steps)
		event.position = b
		event.relative = b - a
		root.push_input(event, true)

func gesture(target: Control, offset: Vector2) -> bool:
	var before: int = hits.get(target.name, 0)
	var at := target.get_global_rect().get_center()
	touch(at, true)
	var tinted := target.self_modulate != Color.WHITE
	if offset != Vector2.ZERO:
		drag(at, at + offset)
	touch(at + offset, false)
	await process_frame
	await process_frame
	return tinted if offset == Vector2.ZERO else hits.get(target.name, 0) > before

func fired(target: Control) -> int:
	return hits.get(target.name, 0)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	game.open_modal("QA")
	var buttons: Array[Button] = []
	for index in 30:
		var name := "B%d" % index
		var item: Button = game.button(game.modal_body, "Кнопка %d" % index, func(): hits[name] = hits.get(name, 0) + 1)
		item.name = name
		buttons.append(item)
	game.modal_footer.show()
	var footer: Button = game.panel_action(game.modal_footer, "Отправить", func(): hits["F"] = hits.get("F", 0) + 1)
	footer.name = "F"
	await process_frame
	await process_frame
	var first := buttons[1]

	# Touch-down tint appears in the same frame as the finger lands.
	var tinted := await gesture(first, Vector2.ZERO)
	check(tinted, "No pressed feedback on touch-down")
	check(fired(first) == 1, "Plain tap did not activate (%d)" % fired(first))
	await create_timer(0.15).timeout
	check(first.self_modulate == Color.WHITE, "Pressed tint stayed after the tap")

	# Natural finger roll: 12 units (~7 pt) was lost with the old 9-unit slop.
	check(await gesture(first, Vector2(7, 9)), "Tap with 12-unit finger roll was lost")
	# Horizontal slide that stays on the button, list does not move.
	check(await gesture(first, Vector2(40, 0)), "Finger slid 40 units along the button: tap lost")
	# Footer button outside the scroll area.
	check(await gesture(footer, Vector2(5, 6)), "Footer action did not respond")

	# A real scroll never activates a button and clears the tint.
	var count := fired(buttons[3])
	var at := buttons[3].get_global_rect().get_center()
	touch(at, true)
	drag(at, at + Vector2(0, -90))
	check(buttons[3].self_modulate == Color.WHITE, "Tint stayed while scrolling")
	touch(at + Vector2(0, -90), false)
	await process_frame
	await process_frame
	check(game.modal_scroll.scroll_vertical > 0, "List did not scroll")
	check(fired(buttons[3]) == count, "Scrolling activated a button")

	# Sliding off the button sideways cancels it.
	var side := buttons[5]
	count = fired(side)
	var start := side.get_global_rect().get_center()
	var outside := Vector2(side.get_global_rect().end.x + 60, start.y) - start
	touch(start, true)
	drag(start, start + outside)
	touch(start + outside, false)
	await process_frame
	await process_frame
	check(fired(side) == count, "Button fired after the finger left it")

	game.close_modal()
	print("QA_TOUCH_BUTTONS checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
