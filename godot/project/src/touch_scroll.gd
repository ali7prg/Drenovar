extends ScrollContainer

# Finger travel (in canvas units) before a touch becomes a scroll. 9 units was
# ~0.9 mm on an iPhone 12 (17 device pixels), so ordinary finger roll on a tap
# turned it into a drag and the press was lost. 16 units is ~10 pt, the iOS norm.
const TAP_SLOP := 16.0
# A finger that moved but stayed on the button it pressed still activates it,
# unless the list actually scrolled.
const BUTTON_MARGIN := 10.0
const PRESSED_TINT := Color(0.78, 0.74, 0.68)
const PRESS_HOLD_SEC := 0.09
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
# Controls that can receive the press highlight (the modal panel).
var press_root: Control
var pressed_button: BaseButton
var pressed_tint_from := Color.WHITE
var scrolled := false

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
	release_highlight()
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
			scrolled = false
			highlight(button_at(origin))
		elif not event.pressed and event.index == finger:
			finger = -1
			var on_button := is_instance_valid(pressed_button) and not scrolled and not sliding and \
					pressed_button.get_global_rect().grow(BUTTON_MARGIN).has_point(event.position)
			if not event.canceled and ((not finger_drag_started and event.position.distance_to(origin) < TAP_SLOP) or on_button):
				# Click where the finger first landed: that is the control it meant.
				tap.call_deferred(origin if on_button else event.position, gesture_revision)
				hold_highlight()
			else:
				release_highlight()
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
			if roundi(offset) != scroll_vertical:
				scrolled = true
			scroll_vertical = roundi(offset)
		if is_instance_valid(pressed_button) and (scrolled or sliding or \
				not pressed_button.get_global_rect().grow(BUTTON_MARGIN).has_point(event.position)):
			release_highlight()
		previous = event.position

# Topmost enabled button under the finger inside the modal, honouring scroll clipping.
func button_at(at: Vector2) -> BaseButton:
	if not is_instance_valid(press_root) or not press_root.is_visible_in_tree():
		return null
	var found: Array = [null]
	collect_button(press_root, at, found)
	return found[0]

func collect_button(node: Node, at: Vector2, found: Array) -> void:
	for child in node.get_children():
		var item := child as Control
		if item == null or not item.visible:
			continue
		if item is ScrollContainer and not item.get_global_rect().has_point(at):
			continue
		if item is BaseButton and not item.disabled and item.mouse_filter != Control.MOUSE_FILTER_IGNORE and item.get_global_rect().has_point(at):
			found[0] = item
		collect_button(item, at, found)

func highlight(target: BaseButton) -> void:
	release_highlight()
	if target == null:
		return
	pressed_button = target
	pressed_tint_from = target.self_modulate
	target.self_modulate = pressed_tint_from * PRESSED_TINT

func hold_highlight() -> void:
	# Keep the tint for a moment so even a quick tap is visibly acknowledged.
	var target := pressed_button
	var tint := pressed_tint_from
	pressed_button = null
	if is_instance_valid(target) and is_inside_tree():
		get_tree().create_timer(PRESS_HOLD_SEC).timeout.connect(func():
			if is_instance_valid(target):
				target.self_modulate = tint)

func release_highlight() -> void:
	if is_instance_valid(pressed_button):
		pressed_button.self_modulate = pressed_tint_from
	pressed_button = null

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
