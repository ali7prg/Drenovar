extends ScrollContainer

const TAP_SLOP := 9.0
var active := false
var emulation_before_modal := true
var finger := -1
var origin := Vector2.ZERO
var previous := Vector2.ZERO
var finger_drag_started := false
var can_scroll := false
var offset := 0.0
var gesture_revision := 0
var slider: HSlider
var sliding := false

func set_modal_active(enabled: bool) -> void:
	cancel_touch()
	if active == enabled:
		return
	active = enabled
	if active:
		emulation_before_modal = Input.emulate_mouse_from_touch
		Input.emulate_mouse_from_touch = false
	else:
		Input.emulate_mouse_from_touch = emulation_before_modal

func cancel_touch() -> void:
	finger = -1
	slider = null
	sliding = false
	gesture_revision += 1

func _exit_tree() -> void:
	if active:
		Input.emulate_mouse_from_touch = emulation_before_modal

func _input(event: InputEvent) -> void:
	if not active or not is_visible_in_tree():
		return
	if event is InputEventScreenTouch:
		get_viewport().set_input_as_handled()
		if event.pressed and finger == -1:
			finger = event.index
			origin = event.position
			previous = origin
			offset = float(scroll_vertical)
			can_scroll = get_global_rect().has_point(origin)
			finger_drag_started = false
			slider = slider_at(origin) if can_scroll else null
			sliding = false
		elif not event.pressed and event.index == finger:
			finger = -1
			if not event.canceled and not finger_drag_started and event.position.distance_to(origin) < TAP_SLOP:
				tap.call_deferred(event.position, gesture_revision)
	elif event is InputEventScreenDrag:
		get_viewport().set_input_as_handled()
		if event.index != finger:
			return
		var travel: Vector2 = event.position - origin
		if not finger_drag_started and travel.length() >= TAP_SLOP:
			finger_drag_started = true
			sliding = is_instance_valid(slider) and absf(travel.x) > absf(travel.y)
		if sliding and is_instance_valid(slider):
			var track := slider.get_global_rect()
			slider.ratio = clampf((event.position.x - track.position.x) / track.size.x, 0.0, 1.0)
		elif can_scroll and finger_drag_started:
			var bar := get_v_scroll_bar()
			offset = clampf(offset + previous.y - event.position.y, 0.0, maxf(0.0, bar.max_value - bar.page))
			scroll_vertical = roundi(offset)
		previous = event.position

func slider_at(at: Vector2) -> HSlider:
	for item: HSlider in get_tree().get_nodes_in_group("panel_slider"):
		if is_ancestor_of(item) and item.is_visible_in_tree() and item.editable and item.get_global_rect().has_point(at):
			return item
	return null

func tap(at: Vector2, revision: int) -> void:
	if not active or revision != gesture_revision or not is_visible_in_tree():
		return
	for is_pressed in [true, false]:
		var click := InputEventMouseButton.new()
		click.button_index = MOUSE_BUTTON_LEFT
		click.pressed = is_pressed
		click.button_mask = MOUSE_BUTTON_MASK_LEFT if is_pressed else 0
		click.position = at
		click.global_position = at
		get_viewport().push_input(click, true)
