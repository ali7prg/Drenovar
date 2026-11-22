extends Control
## The construction window (premium UI stage 3, ui_premium/STAGE3.md): a horizontal strip of
## building cards over the player's own city (blurred and dimmed behind it, src/city_backdrop.gd),
## a rail of four category medallions on the left, the title and the builders and plots on a
## carved plate at the top, the resources and the close medallion on the right.
##
## The strip (Swipe) follows the finger, glides on with inertia when flicked and comes to rest
## with a card at its left edge (a critically damped spring from the release velocity, so the
## glide and the snap are one motion with no bounce). A drag never presses a card: TouchScroll
## hands a touch inside the strip to Swipe (group "panel_swipe") and only taps on release when
## the finger did not travel; a touch on a moving strip just catches it.

const UiKit = preload("res://src/ui_kit.gd")
const BuildCard = preload("res://src/build_card.gd")

signal category_chosen(index: int)
signal closed

var swipe: Swipe
var rail: VBoxContainer
var rail_light: RailLight
var selected_category := 0
var medals: Array = []
var heading: Heading
var close_button: Button
var queues_button: Button

func _ready() -> void:
	name = "BuildStrip"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	heading = Heading.new()
	heading.name = "StripHeading"
	heading.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(heading)
	rail_light = RailLight.new()
	rail_light.name = "RailLight"
	rail_light.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(rail_light)
	rail = VBoxContainer.new()
	rail.name = "CategoryRail"
	rail.add_theme_constant_override("separation", 10)
	rail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(rail)
	swipe = Swipe.new()
	swipe.name = "CardStrip"
	add_child(swipe)
	close_button = UiKit.close_button(func(): closed.emit())
	close_button.name = "StripClose"
	add_child(close_button)
	resized.connect(layout)
	# The window body is a vertical list: the strip asks for the whole screen.
	fit_screen()
	get_viewport().size_changed.connect(fit_screen)

func fit_screen() -> void:
	if is_inside_tree():
		custom_minimum_size = get_viewport().get_visible_rect().size

## The rail: [caption, emblem texture, count of cards that can be built now].
func set_categories(entries: Array, selected: int) -> void:
	for medal: Node in medals:
		medal.queue_free()
	medals.clear()
	for index in entries.size():
		var entry: Array = entries[index]
		var medal: BaseButton = UiKit.rail_medal(null, index == selected, str(entry[0]), false, entry[1])
		medal.name = "Category%d" % index
		medal.tooltip_text = str(entry[0])
		medal.pressed.connect(func(): category_chosen.emit(index))
		var badge := Badge.new()
		badge.count = int(entry[2])
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		medal.add_child(badge)
		badge.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		rail.add_child(medal)
		medals.append(medal)
	select_category(selected)
	layout()

func select_category(selected: int) -> void:
	selected_category = selected
	for index in medals.size():
		var medal = medals[index]
		medal.selected = index == selected
		medal.disc = UiKit.tex("kit_rail_on" if index == selected else "kit_rail")
		# On the dark city the chosen medallion must stand out: the others step back.
		medal.modulate = Color.WHITE if index == selected else Color(0.74, 0.71, 0.68)
		medal.queue_redraw()
	place_light.call_deferred()

## The warm pool and the gold notch behind the chosen medallion (after the rail has sorted).
func place_light() -> void:
	if rail_light == null or selected_category >= medals.size():
		return
	var medal: Control = medals[selected_category]
	rail_light.size = size
	rail_light.at = rail.position + medal.position + Vector2(medal.size.x * 0.5, 44.0)
	rail_light.queue_redraw()

func set_heading(title: String, info: String) -> void:
	heading.title = title
	heading.info = info
	heading.queue_redraw()
	layout()

func layout() -> void:
	if swipe == null:
		return
	var w := size.x
	var h := size.y
	close_button.size = close_button.get_combined_minimum_size()
	close_button.position = Vector2(w - close_button.size.x - 14.0, 10.0)
	heading.size = Vector2(heading.measure(), 84)
	heading.position = Vector2(18, 6)
	var rail_size := rail.get_combined_minimum_size()
	rail.size = rail_size
	var top := 96.0
	rail.position = Vector2(18, roundf(top + maxf(0.0, (h - top - 12.0 - rail_size.y) * 0.5)))
	var left := 18.0 + maxf(100.0, rail_size.x) + 20.0
	swipe.position = Vector2(left, 84)
	swipe.size = Vector2(maxf(100.0, w - left), maxf(100.0, h - 84 - 6))
	swipe.layout_cards()
	place_light.call_deferred()

## Light behind the chosen category: a warm pool and a small gold notch toward the cards.
class RailLight extends Control:
	var at := Vector2(-1000, -1000)

	func _draw() -> void:
		draw_texture_rect(UiKit.warm_glow(), Rect2(at - Vector2(84, 70), Vector2(168, 140)), false, Color(1, 1, 1, 0.95))
		var tip := at + Vector2(58, 0)
		var notch := PackedVector2Array([tip + Vector2(-7, -9), tip + Vector2(4, 0), tip + Vector2(-7, 9)])
		var shade := PackedVector2Array()
		for p in notch:
			shade.append(p + Vector2(0, 2))
		draw_colored_polygon(shade, Color(0, 0, 0, 0.45))
		draw_colored_polygon(notch, UiKit.GOLD)

## Title plate: the window's name in the display face on carved oak, the builders and plots
## under it.
class Heading extends Control:
	var title := ""
	var info := ""

	func measure() -> float:
		var line := UiKit.KitText.line(title, UiKit.TITLE_FONT, 34)
		var under := UiKit.KitText.line(info, UiKit.LABEL_FONT, 17)
		return maxf(line.get_size().x + 92.0, under.get_size().x + 64.0)

	func _draw() -> void:
		var plate := Rect2(0, 4, size.x, 50)
		draw_style_box(UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO), plate)
		var line := UiKit.KitText.line(title, UiKit.TITLE_FONT, 34)
		var at := Vector2(roundf((size.x - line.get_size().x) * 0.5), plate.position.y + roundf((plate.size.y - line.get_size().y) * 0.5))
		line.draw_outline(get_canvas_item(), at, 6, UiKit.SHADE)
		line.draw(get_canvas_item(), at, UiKit.GOLD)
		if not info.is_empty():
			var under := UiKit.KitText.line(info, UiKit.LABEL_FONT, 17)
			var below := Vector2(roundf((size.x - under.get_size().x) * 0.5), plate.end.y + 5.0)
			under.draw_outline(get_canvas_item(), below, 4, UiKit.SHADE)
			under.draw(get_canvas_item(), below, UiKit.IVORY)

## Count of the cards that can be built now, on a green enamel dot at the rim of a medallion.
class Badge extends Control:
	var count := 0

	func _draw() -> void:
		if count <= 0:
			return
		var at := Vector2(size.x * 0.5 + 30.0, 16.0)
		draw_circle(at, 13.0, Color("#e9c779"))
		draw_circle(at, 11.0, Color("#2f7a37"))
		var digits := UiKit.KitText.line(str(count), UiKit.LABEL_FONT, 15)
		digits.draw(get_canvas_item(), at - digits.get_size() * 0.5 + Vector2(0, -1), UiKit.IVORY)

## The swipeable strip of cards.
class Swipe extends Control:
	const GAP := 18.0
	const SLOP := 16.0
	## Spring of the glide-and-snap (critically damped; about a third of a second).
	const OMEGA := 12.5
	## How far a flick glides: the release velocity times this (seconds).
	const GLIDE := 0.26
	const PAD_LEFT := 4.0
	const PAD_RIGHT := 64.0
	var track: Control
	var edge: Control
	var indicator: Control
	var cards: Array = []
	var offset := 0.0
	var velocity := 0.0
	var moving := false
	var settle_from := 0.0
	var settle_velocity := 0.0
	var settle_target := 0.0
	var settle_started := 0
	var dragging := false
	var drag_origin_x := 0.0
	var drag_origin_offset := 0.0
	var samples: Array = []
	var mouse_down := false
	var mouse_origin := Vector2.ZERO
	var mouse_dragging := false
	var suppress_until := 0
	var appear: Tween

	func _ready() -> void:
		add_to_group("panel_swipe")
		mouse_filter = Control.MOUSE_FILTER_PASS
		clip_contents = true
		track = Control.new()
		track.name = "Track"
		track.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(track)
		edge = Edge.new()
		edge.swipe = self
		edge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(edge)
		indicator = Indicator.new()
		indicator.swipe = self
		indicator.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(indicator)
		set_process(false)

	func pitch() -> float:
		return BuildCard.SIZE.x + GAP

	func content_width() -> float:
		return PAD_LEFT + cards.size() * pitch() - GAP + PAD_RIGHT

	func max_offset() -> float:
		return maxf(0.0, content_width() - size.x)

	## Replaces the cards (a category switch): the strip starts at its first card and the new
	## cards slide in from the right while they fade in.
	func set_cards(list: Array, animate := true) -> void:
		for card: Node in cards:
			if is_instance_valid(card):
				card.queue_free()
		cards = list
		for card: Control in cards:
			track.add_child(card)
		offset = 0.0
		velocity = 0.0
		moving = false
		set_process(false)
		layout_cards()
		if appear != null:
			appear.kill()
		if animate:
			track.modulate.a = 0.0
			track.position.x = PAD_LEFT + 46.0
			appear = create_tween().set_parallel()
			appear.tween_property(track, "modulate:a", 1.0, 0.16).set_trans(Tween.TRANS_SINE)
			appear.tween_property(track, "position:x", PAD_LEFT, 0.22).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		else:
			track.modulate.a = 1.0

	func layout_cards() -> void:
		if track == null:
			return
		var top := roundf(maxf(0.0, (size.y - 18.0 - BuildCard.SIZE.y) * 0.5))
		for index in cards.size():
			var card: Control = cards[index]
			card.size = BuildCard.SIZE
			card.position = Vector2(index * pitch(), top)
		indicator.position = Vector2(0, size.y - 12)
		indicator.size = Vector2(size.x - PAD_RIGHT, 6)
		# Over the card bodies only, so the city between and below them is not darkened.
		edge.position = Vector2(0, top + BuildCard.TOP)
		edge.size = Vector2(size.x, BuildCard.SIZE.y - BuildCard.TOP)
		apply()

	func apply() -> void:
		if appear == null or not appear.is_running():
			track.position.x = PAD_LEFT - offset
		var left := offset - 40.0
		var right := offset + size.x + 40.0
		for index in cards.size():
			var card: Control = cards[index]
			var x := index * pitch()
			card.visible = x + BuildCard.SIZE.x > left and x < right
		indicator.queue_redraw()
		edge.queue_redraw()

	## Taps on cards are honoured unless the finger or the mouse just dragged the strip.
	func tap_allowed() -> bool:
		return not dragging and not mouse_dragging and Time.get_ticks_msec() >= suppress_until

	func is_moving() -> bool:
		return moving and absf(velocity) > 40.0

	# ------------------------------------------------------------ TouchScroll protocol

	## A finger landed on the strip. True when it caught the strip in motion (then the touch
	## presses nothing).
	func swipe_begin(at: Vector2) -> bool:
		var caught := is_moving()
		stop()
		drag_origin_x = at.x
		drag_origin_offset = offset
		samples = [[Time.get_ticks_usec(), at.x]]
		return caught

	## The finger travelled past the tap slop: from now on it moves the strip.
	func swipe_to(at: Vector2) -> void:
		if not dragging:
			dragging = true
			# Start from where the finger is now, so the strip does not jump by the slop.
			drag_origin_x = at.x
			drag_origin_offset = offset
		var raw := drag_origin_offset - (at.x - drag_origin_x)
		offset = rubber(raw)
		var now := Time.get_ticks_usec()
		samples.append([now, at.x])
		while samples.size() > 2 and now - int(samples[0][0]) > 90000:
			samples.pop_front()
		apply()

	func swipe_end(at: Vector2) -> void:
		if not dragging:
			# A tap (or a caught glide): rest on the nearest card edge; the tap goes through.
			samples.clear()
			if not moving and not is_equal_approx(offset, nearest_stop(offset)):
				settle(0.0)
			return
		var speed := 0.0
		if samples.size() >= 2:
			var first: Array = samples[0]
			var last: Array = samples[-1]
			var seconds := (int(last[0]) - int(first[0])) / 1000000.0
			# A finger that rested before lifting does not throw the strip.
			if seconds > 0.004 and Time.get_ticks_usec() - int(last[0]) < 90000:
				speed = -(float(last[1]) - float(first[1])) / seconds
		dragging = false
		suppress_until = Time.get_ticks_msec() + 60
		samples.clear()
		settle(clampf(speed, -7000.0, 7000.0))

	# ------------------------------------------------------------ physics

	func rubber(raw: float) -> float:
		var high := max_offset()
		if raw < 0.0:
			return -resist(-raw)
		if raw > high:
			return high + resist(raw - high)
		return raw

	static func resist(distance: float) -> float:
		return distance * 0.5 / (1.0 + distance / 520.0)

	func stops() -> Array:
		var list: Array = []
		var high := max_offset()
		var step := pitch()
		var at := 0.0
		while at < high - 1.0:
			list.append(at)
			at += step
		list.append(high)
		return list

	func nearest_stop(at: float) -> float:
		var best := 0.0
		var gap := INF
		for stop: float in stops():
			if absf(stop - at) < gap:
				gap = absf(stop - at)
				best = stop
		return best

	## Glides on from the current offset with `speed` (offset units per second) and comes to
	## rest on a card edge.
	func settle(speed: float) -> void:
		var best := nearest_stop(offset + speed * GLIDE)
		# A deliberate flick always moves at least one card on.
		if absf(speed) > 350.0 and absf(best - offset) < pitch() * 0.5:
			for stop: float in stops():
				if (speed > 0.0 and stop > offset + 1.0) or (speed < 0.0 and stop < offset - 1.0):
					if speed > 0.0:
						best = stop
						break
					best = stop
		settle_from = offset
		settle_velocity = speed
		settle_target = best
		settle_started = Time.get_ticks_usec()
		moving = true
		velocity = speed
		set_process(true)

	## Throws the strip as a flick of the finger would (tests and stills).
	func fling(speed: float) -> void:
		settle(speed)

	func stop() -> void:
		moving = false
		velocity = 0.0
		set_process(false)

	func scroll_to_index(index: int, animate := true) -> void:
		var target := clampf(index * pitch(), 0.0, max_offset())
		if animate:
			settle_from = offset
			settle_velocity = 0.0
			settle_target = target
			settle_started = Time.get_ticks_usec()
			moving = true
			set_process(true)
		else:
			stop()
			offset = target
			apply()

	func scroll_to_type(type: String, animate := true) -> void:
		for index in cards.size():
			if str(cards[index].type) == type:
				scroll_to_index(index, animate)
				return

	func _process(_delta: float) -> void:
		if not moving:
			set_process(false)
			return
		var t := (Time.get_ticks_usec() - settle_started) / 1000000.0
		var c1 := settle_from - settle_target
		var c2 := settle_velocity + OMEGA * c1
		var fall := exp(-OMEGA * t)
		offset = settle_target + (c1 + c2 * t) * fall
		velocity = (c2 - OMEGA * (c1 + c2 * t)) * fall
		if absf(offset - settle_target) < 0.25 and absf(velocity) < 8.0:
			offset = settle_target
			velocity = 0.0
			moving = false
			set_process(false)
		apply()

	# ------------------------------------------------------------ mouse (desktop, editor)

	func _input(event: InputEvent) -> void:
		if not is_visible_in_tree():
			return
		if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed and get_global_rect().has_point(event.position):
				mouse_down = true
				mouse_dragging = false
				mouse_origin = event.position
				if is_moving():
					# Catching a gliding strip with the mouse presses nothing.
					suppress_until = Time.get_ticks_msec() + 400
				swipe_begin(event.position)
			elif not event.pressed and mouse_down:
				mouse_down = false
				if mouse_dragging:
					swipe_end(event.position)
					# The card under the cursor sees this release next: it must not act.
					suppress_until = Time.get_ticks_msec() + 60
					mouse_dragging = false
				else:
					swipe_end(event.position)
		elif event is InputEventMouseMotion and mouse_down and (event.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0:
			if not mouse_dragging and absf(event.position.x - mouse_origin.x) >= SLOP:
				mouse_dragging = true
			if mouse_dragging:
				swipe_to(event.position)

## Soft shade at the strip's edges: a card sliding out of view sinks into shadow instead of
## being cut by a hard line (one gradient quad per edge, only while cards lie past that edge).
class Edge extends Control:
	const WIDTH := 64.0
	static var fades := {}
	var swipe

	## The shade ramp, dark at the left (or, mirrored, at the right).
	static func gradient(mirrored := false) -> GradientTexture2D:
		if not fades.has(mirrored):
			var ramp := Gradient.new()
			ramp.set_color(0, Color(0.04, 0.025, 0.012, 0.92))
			ramp.set_color(1, Color(0.04, 0.025, 0.012, 0.0))
			ramp.add_point(0.45, Color(0.04, 0.025, 0.012, 0.45))
			var fade := GradientTexture2D.new()
			fade.gradient = ramp
			fade.width = 64
			fade.height = 1
			if mirrored:
				fade.fill_from = Vector2(1, 0)
				fade.fill_to = Vector2(0, 0)
			fades[mirrored] = fade
		return fades[mirrored]

	func _draw() -> void:
		if swipe == null:
			return
		var hidden_left := clampf(float(swipe.offset) / 48.0, 0.0, 1.0)
		var hidden_right := clampf((float(swipe.max_offset()) - float(swipe.offset)) / 48.0, 0.0, 1.0)
		if hidden_left > 0.0:
			draw_texture_rect(gradient(), Rect2(0, 0, WIDTH, size.y), false, Color(1, 1, 1, hidden_left))
		if hidden_right > 0.0:
			# Mirrored: the dark side at the right edge.
			draw_texture_rect(gradient(true), Rect2(size.x - WIDTH * 0.75, 0, WIDTH * 0.75, size.y), false, Color(1, 1, 1, hidden_right * 0.8))

## The bronze scroll indicator under the cards.
class Indicator extends Control:
	var swipe

	func _draw() -> void:
		if swipe == null:
			return
		var whole: float = swipe.content_width()
		if whole <= swipe.size.x + 1.0:
			return
		draw_rect(Rect2(0, 2, size.x, 2), Color("#c9a25e40"))
		var share: float = clampf(swipe.size.x / whole, 0.08, 1.0)
		var thumb := size.x * share
		var ratio: float = clampf(swipe.offset / maxf(1.0, swipe.max_offset()), 0.0, 1.0)
		var x := (size.x - thumb) * ratio
		draw_rect(Rect2(x, 0, thumb, 6), Color("#1a0f06aa"))
		draw_rect(Rect2(x + 1, 1, thumb - 2, 4), Color("#e2b766"))
