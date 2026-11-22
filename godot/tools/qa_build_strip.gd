extends SceneTree
## The construction strip, its cards and the placement on glowing plots (premium UI stage 3,
## ui_premium/STAGE3.md), through the real main scene, the real touch path and the
## authoritative local fixture (no real account):
##   (cd ../drenovar-server && node v6/tests/buildings-ui-local.mjs)        # port 8792
##   godot --headless --path godot/project -s ../tools/qa_build_strip.gd -- --server=http://127.0.0.1:8792
## Checks:
## - the rail's categories hold every catalogue type exactly once;
## - a horizontal drag moves the strip and taps nothing; a vertical drag neither moves nor taps;
##   a touch that catches a gliding strip stops it and taps nothing; a plain tap on a buildable
##   card starts placement;
## - a type built to its limit draws grey with the stamp and «1/1», cannot be built, and its tap
##   opens the existing building's window;
## - «Сейчас/После» show exactly the scenes the city draws, for every type and level;
## - placement: glowing plots, the banner, a tap on a plot quotes it (named «Участок N», never
##   by its id), the floating confirm never covers the plot, the ghost is the building's own
##   translucent scene, «Построить» sends the order on that plot; «Списком» falls back to the
##   plot list; «Отмена» clears everything;
## - the open level (main.gd MAX_OPEN_BUILDING_LEVEL, V for now): barracks IV still offers V; at
##   V and above «После» is a «Скоро» card, «Улучшить» is a disabled «Скоро», and no entry point
##   (ring, button, confirm(), request(), command(), legacy orders) sends a quote or an order;
##   no card of the strip names a level past V as a requirement;
## - the live pair renders while it moves and then holds its picture.

const V6Build = preload("res://src/v6_build.gd")
const BuildingStage = preload("res://src/building_stage.gd")
const BuildCard = preload("res://src/build_card.gd")

var game
var checks := 0
var fixture := "http://127.0.0.1:8792"
var cases: Array = []

func check(ok: bool, label: String) -> bool:
	checks += 1
	if not ok:
		push_error(label)
		print(JSON.stringify({"status":"failed","checks":checks,"reason":label}))
		quit(1)
	return ok

func wait_for(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not test.call():
		if Time.get_ticks_msec() > end:
			return false
		await process_frame
	return true

func frames(count: int) -> void:
	for i in count:
		await process_frame

func admin(path: String, body: Dictionary) -> Dictionary:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request(fixture + "/qa/" + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(body))
	var result: Array = await request.request_completed
	request.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8())

func seed_case(type: String, level: int) -> void:
	if game.modal.visible:
		game.close_modal()
	game.v6_panels.build.cancel_placement()
	await admin("case", {"type":type, "level":level, "bounded":true})
	await game.sync_account()
	await wait_for(func(): return game.v6_panels.enabled(), 30.0)
	await frames(4)

func touch(at: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.pressed = pressed
	event.position = at
	root.push_input(event, true)

## A finger drag from `from` to `to` over `steps` frames (so the strip sees a real velocity).
func drag(from: Vector2, to: Vector2, steps := 8) -> void:
	for step in steps:
		var event := InputEventScreenDrag.new()
		var a := from.lerp(to, float(step) / steps)
		var b := from.lerp(to, float(step + 1) / steps)
		event.position = b
		event.relative = b - a
		root.push_input(event, true)
		await process_frame

func find_button(node: Node, text: String) -> BaseButton:
	if node is Button and node.text == text:
		return node
	for child: Node in node.get_children():
		var found := find_button(child, text)
		if found != null:
			return found
	return null

func card(type: String) -> BuildCard:
	var strip = game.v6_panels.build.strip
	if strip == null:
		return null
	for item in strip.cards:
		if is_instance_valid(item) and item.type == type:
			return item
	return null

## Opens the strip on a category and waits for touches to be accepted (the modal's open guard).
func open_strip(category := -1) -> bool:
	await game.v6_panels.catalog()
	if not await wait_for(func(): return game.v6_panels.build.is_open()):
		return false
	if category >= 0:
		game.v6_panels.build.show_category(category, false)
	await create_timer(0.35).timeout
	await frames(2)
	return true

func at_rest() -> bool:
	return not game.v6_panels.build.strip.moving

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			fixture = arg.trim_prefix("--server=").trim_suffix("/")
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	if not check(await wait_for(func(): return not game.scene_loading and is_instance_valid(game.stage), 60.0), "scene ready"): return
	game.session = "device." + "a".repeat(64)
	await game.sync_account()
	var build = game.v6_panels.build
	# A young settlement: the house at VI (eleven types built, sixteen to build).
	await seed_case("B02", 6)
	if not check(await game.v6_panels.load_catalogue(), "catalogue loads"): return

	# ---------------------------------------------------------------- categories
	var types := {}
	for row: Dictionary in game.v6_panels.catalogue.get("buildings", []):
		types[str(row.building_id)] = true
	var seen := {}
	for entry: Array in V6Build.CATEGORIES:
		for type: String in entry[2]:
			if not check(not seen.has(type), "type in one category only " + type): return
			seen[type] = true
	if not check(types.size() == 27, "catalogue has 27 types: %d" % types.size()): return
	for type: String in types:
		if not check(seen.has(type), "catalogue type has a category " + type): return
	for type: String in seen:
		if not check(types.has(type), "category type is in the catalogue " + type): return
	cases.append({"case":"categories", "types":types.size()})

	# ---------------------------------------------------------------- the strip opens
	if not check(await open_strip(0), "strip opens"): return
	if not check(game.modal_layout == "strip" and game.city_backdrop.visible, "strip stands on the city backdrop"): return
	var strip = build.strip
	if not check(strip.cards.size() == V6Build.CATEGORIES[0][2].size(), "economy shows all its types: %d" % strip.cards.size()): return
	var medals: Array = build.view.medals
	if not check(medals.size() == V6Build.CATEGORIES.size(), "rail has a medal per category"): return

	# ---------------------------------------------------------------- built to the limit
	var hall: Dictionary = build.states.get("B01", {})
	if not check(hall.get("state", "") == "maxed", "town hall reads as built to its limit: " + str(hall.get("state", ""))): return
	var hall_card := card("B01")
	if not check(hall_card != null and hall_card.material == BuildCard.grey(), "maxed card is greyscale"): return
	if not check(hall_card.stamp != null and hall_card.stamp.visible and hall_card.stamp.caption()[0] == "Больше строить", "maxed card shows the plain caption"): return
	if not check(not hall_card.stamp is BaseButton and hall_card.stamp.get_child_count() == 0, "the caption is text, not a button"): return
	if not check(hall_card.built_text == "1/1" and not hall_card.level_text.is_empty(), "maxed card shows 1/1 and its level"): return
	var cards_before: int = strip.cards.size()
	strip.scroll_to_type("B01", false)
	await frames(2)
	if not check(hall_card.is_visible_in_tree() and strip.get_global_rect().has_point(hall_card.get_global_rect().get_center()), "maxed card scrolled into view"): return
	var centre := hall_card.get_global_rect().get_center()
	touch(centre, true)
	touch(centre, false)
	var hall_name := str(game.v6_panels.row_for("B01", 1).get("name_ru", ""))
	if not check(await wait_for(func(): return game.modal_title.text == hall_name and game.modal_layout == "full"), "maxed card opens the existing building: " + game.modal_title.text): return
	if not check(not build.placing_active(), "maxed card starts no placement"): return
	if not check(find_button(game.modal_body, "Построить") == null, "no build action for a maxed type"): return
	cases.append({"case":"maxed", "type":"B01", "cards":cards_before})

	# ---------------------------------------------------------------- swipe versus tap
	if not check(await open_strip(1), "craft strip opens"): return
	strip = build.strip
	if not check(strip.cards.size() == V6Build.CATEGORIES[1][2].size() and strip.max_offset() > 0.0, "craft strip is wider than the screen"): return
	var buildable := ""
	for item in strip.cards:
		if item.state == "build":
			buildable = item.type
			break
	if not check(not buildable.is_empty(), "a buildable craft card exists"): return
	# Horizontal drag starting on a card: the strip moves, nothing is tapped.
	var first: BuildCard = strip.cards[0]
	var from := first.get_global_rect().get_center()
	touch(from, true)
	await process_frame
	await drag(from, from + Vector2(-420, 6))
	touch(from + Vector2(-420, 6), false)
	await frames(2)
	if not check(strip.offset > 150.0, "horizontal drag moves the strip: %.1f" % strip.offset): return
	if not check(build.is_open() and not build.placing_active(), "a drag taps no card"): return
	if not check(await wait_for(at_rest, 3.0), "strip comes to rest"): return
	if not check(is_equal_approx(strip.offset, strip.nearest_stop(strip.offset)), "strip rests on a card edge: %.1f" % strip.offset): return
	cases.append({"case":"drag", "offset":strip.offset})
	# Vertical drag: no motion, no tap.
	var resting: float = strip.offset
	var mid: BuildCard = null
	for item in strip.cards:
		if item.is_visible_in_tree() and strip.get_global_rect().has_point(item.get_global_rect().get_center()):
			mid = item
			break
	from = mid.get_global_rect().get_center()
	touch(from, true)
	await process_frame
	await drag(from, from + Vector2(4, -120), 4)
	touch(from + Vector2(4, -120), false)
	await frames(3)
	if not check(is_equal_approx(strip.offset, resting) and build.is_open() and not build.placing_active(), "vertical drag neither moves nor taps"): return
	# A flick, then a touch while it glides: it stops and taps nothing.
	strip.scroll_to_index(0, false)
	await frames(1)
	strip.fling(2600.0)
	await frames(2)
	if not check(strip.is_moving(), "a flick glides"): return
	from = strip.get_global_rect().get_center()
	touch(from, true)
	if not check(not strip.moving, "a touch catches the gliding strip"): return
	await process_frame
	touch(from, false)
	await frames(3)
	if not check(build.is_open() and not build.placing_active(), "catching a glide taps no card"): return
	cases.append({"case":"catch"})
	# A plain tap on a buildable card starts its placement.
	if not check(await wait_for(at_rest, 3.0), "strip at rest before the tap"): return
	strip.scroll_to_type(buildable, false)
	await create_timer(0.1).timeout
	var target := card(buildable)
	centre = target.get_global_rect().get_center()
	touch(centre, true)
	await process_frame
	touch(centre, false)
	if not check(await wait_for(func(): return build.placing_active() and str(build.placing.type) == buildable, 5.0), "a tap on a buildable card starts placement " + buildable): return
	cases.append({"case":"tap", "type":buildable})

	# ---------------------------------------------------------------- placement
	if not check(await wait_for(func(): return not game.modal.visible), "the strip slides away"): return
	if not check(await wait_for(func(): return not game.city_backdrop.visible), "the city comes back into focus"): return
	if not check(not game.get_viewport().disable_3d, "the city's 3D pass is back on"): return
	var offered: Array = build.placement_plots()
	if not check(not offered.is_empty() and game.stage.placement_rings.size() == offered.size(), "every offered plot glows: %d" % offered.size()): return
	var free: Array = build.free_plots(str(build.placing.row.environment))
	if not check(offered.size() == free.size(), "the glowing plots are the free plots of the terrain"): return
	var place = build.place
	if not check(place.visible and place.banner_info.text.ends_with(str(offered.size())), "banner names the building and the count"): return
	if not check(build.blocks_touch(place.banner.get_global_rect().get_center()), "the banner takes its own touches"): return
	var plot: Dictionary = offered[0]
	var screen: Vector2 = game.stage.camera.unproject_position(plot.position)
	build.tap_city(screen)
	if not check(str(build.placing.plot) == str(plot.id), "a tap near a plot chooses it"): return
	if not check(place.bubble.visible and place.bubble_title.text == build.plot_name(str(plot.id)) and place.bubble_title.text.begins_with("Участок " + str(plot.id).trim_prefix("v1-")) and not place.bubble_title.text.contains("v1-"), "floating confirm names the plot: " + place.bubble_title.text): return
	if not check(place.go.disabled, "«Построить» waits for the quote"): return
	if not check(await wait_for(func(): return build.quote_ready()), "the plot is quoted"): return
	if not check(not build.placing.quote.is_empty() and not place.go.disabled and place.go.text == "Построить", "«Построить» is live once quoted"): return
	if not check(place.cost_row.get_child_count() > 0 and place.time_label.text == game.v6_panels.duration(int(build.placing.quote.duration_seconds)), "confirm shows the quoted cost and time"): return
	await frames(2)
	if not check(place.pointer.visible, "the confirm points at the plot"): return
	# The camera eases to the plot; the confirm stays clear of the plot and its ghost all along.
	for step in 40:
		await process_frame
		if not check(not place.bubble.get_global_rect().intersects(place.plot_rect(game.stage.camera)), "the confirm never covers the plot (frame %d)" % step): return
	var ghost: Node3D = game.stage.placement_ghost
	if not check(await wait_for(func(): return ghost.get_child_count() > 0, 10.0), "the ghost's scene is there"): return
	var parts: Array = ghost.find_children("*", "MeshInstance3D", true, false)
	if not check(not parts.is_empty() and ghost.visible, "the ghost stands on the plot"): return
	var surface: Material = parts[0].get_surface_override_material(0)
	if not check(surface is ShaderMaterial and surface.shader == game.stage.PLACEMENT_GHOST and surface.shader.code.contains("ALPHA = clamp(ghost_alpha"), "the ghost is the building's own translucent scene"): return
	place.go.pressed.emit()
	var chosen := str(plot.id)
	if not check(await wait_for(func(): return not game.command_in_progress and game.state.v6.orders.any(func(o): return o.status == "pending" and str(o.get("building", "")) == buildable and str(o.get("plot", "")) == chosen)), "the order stands on the chosen plot"): return
	if not check(not build.placing_active() and not place.visible and game.stage.placement_rings.is_empty(), "placement ends after «Построить»"): return
	if not check(await wait_for(func(): return game.message.text.begins_with("Строительство началось"), 5.0), "the city says the work began: " + game.message.text): return
	cases.append({"case":"placement", "type":buildable, "plot":chosen})
	# The strip now shows that card as under construction.
	if not check(await open_strip(1), "strip reopens"): return
	if not check(build.states[buildable].state == "busy" and card(buildable).progress >= 0.0, "the started type reads as under construction"): return
	# «Списком»: the plot list of the inspector (a fresh settlement, so a builder is free).
	await seed_case("B02", 6)
	if not check(await open_strip(1), "strip reopens for the list"): return
	var second := ""
	for item in build.strip.cards:
		if item.state == "build":
			second = item.type
			break
	if not check(not second.is_empty(), "another buildable craft card"): return
	build.card_tapped(second)
	if not check(await wait_for(func(): return build.placing_active() and not game.modal.visible), "second placement begins"): return
	build.place.banner.find_child("PlacementList", true, false).pressed.emit()
	var second_name := str(game.v6_panels.row_for(second, 1).get("name_ru", ""))
	if not check(await wait_for(func(): return game.modal.visible and game.modal_title.text == second_name), "«Списком» opens the building window"): return
	var list: Node = game.modal_body.find_child("PlotList", true, false)
	if not check(not build.placing_active() and list != null and list.get_child_count() > 0 and str(list.get_child(0).text).begins_with("Участок ") and not str(list.get_child(0).text).contains("v1-"), "the plot list is offered by name"): return
	list.get_child(0).pressed.emit()
	if not check(await wait_for(func(): return game.modal_title.text == "Подтвердить работу" and game.modal_eyebrow.text.contains("УЧАСТОК")), "a listed plot opens the confirm for that plot"): return
	if not check(await wait_for(func(): return find_button(game.modal, "Начать") != null), "the listed plot can be started"): return
	cases.append({"case":"list", "type":second})
	# «Отмена» clears the glow, the ghost and the plate.
	if not check(await open_strip(1), "strip reopens for cancel"): return
	build.card_tapped(second)
	if not check(await wait_for(func(): return build.placing_active() and not game.modal.visible), "third placement begins"): return
	build.pick_plot(str(build.placement_plots()[0].id))
	build.place.banner.find_child("PlacementCancel", true, false).pressed.emit()
	if not check(not build.placing_active() and not build.place.visible and game.stage.placement_rings.is_empty() and not is_instance_valid(game.stage.placement), "«Отмена» clears the placement"): return
	cases.append({"case":"cancel"})

	# ---------------------------------------------------------------- requirement chips
	await game.v6_panels.catalog()
	await wait_for(func(): return build.is_open())
	var locked := ""
	for type: String in build.states:
		if build.states[type].state != "locked":
			continue
		for d: Dictionary in game.v6_panels.row_for(type, 1).get("requirements", []):
			if str(d.building_id) != type and build.level_of(str(d.building_id)) < int(d.level):
				locked = type
		if not locked.is_empty():
			break
	if not locked.is_empty():
		await game.v6_panels.inspect(locked)
		var needs: Node = game.modal_body.find_child("KitRequirements", true, false)
		if not check(needs != null, "locked type lists its requirements " + locked): return
		var missing: BaseButton = null
		for chip in needs.get_children():
			if not chip.disabled:
				missing = chip
				break
		if not check(missing != null, "a missing requirement is a live chip"): return
		var other := str(missing.name).trim_prefix("Need_")
		missing.pressed.emit()
		var other_name := str(game.v6_panels.row_for(other, 1).get("name_ru", ""))
		if not check(await wait_for(func(): return game.modal_title.text == other_name), "a missing chip opens that building " + other): return
		cases.append({"case":"requirement", "type":locked, "goes_to":other})

	# ---------------------------------------------------------------- «Сейчас/После» = the city
	var compared := 0
	var without: Array = []
	for type: String in types:
		var runtime := BuildingStage.runtime_type(game.data, type)
		if runtime.is_empty():
			without.append(type)
			continue
		for level in range(1, 12):
			var mine := BuildingStage.level_visual(game.data, runtime, level)
			var city: Array = game.stage.level_visual(runtime, level)
			if not check(mine.size() == city.size() and (mine.is_empty() or (str(mine[0]) == str(city[0]) and is_equal_approx(float(mine[1]), float(city[1])))), "window draws the city's model %s %d" % [type, level]): return
			compared += 1
	for b: Dictionary in game.state.city.buildings:
		if b.has("conceptType") and str(b.conceptType).begins_with("B"):
			if not check(BuildingStage.runtime_type(game.data, str(b.conceptType)) == str(b.type), "city type of " + str(b.conceptType)): return
	if not check(compared >= 20 * 11, "most types have city models: %d (%s)" % [compared, str(without)]): return
	cases.append({"case":"models", "compared":compared, "without_city_model":without})
	# The pair inside a family (barracks II -> III), up to the open level (IV -> V), at the open
	# level (V: «Скоро»), above it (a fixture at VII: shown, not upgradable) and at XI.
	var cap: int = game.MAX_OPEN_BUILDING_LEVEL
	var fresh := 0
	for pair: Array in [["B11", 2], ["B11", cap - 1], ["B11", cap], ["B11", 7], ["B11", 11]]:
		await seed_case(str(pair[0]), int(pair[1]))
		var level: int = pair[1]
		await game.v6_panels.inspect(str(pair[0]))
		var stage: Node = game.modal_hero.find_child("BuildingStage", true, false)
		if not check(stage != null, "inspect shows the live pair"): return
		var runtime := BuildingStage.runtime_type(game.data, str(pair[0]))
		var row: Node = game.modal_body.find_child("KitTimeAction", true, false)
		var main_action := ""
		var main_button: Button = null
		if row != null:
			for child in row.get_children():
				if child is Button:
					main_action = child.text
					main_button = child
		if level < cap:
			if not check(stage.levels == [level, level + 1] and not stage.soon, "pair is now and next: " + str(stage.levels)): return
			if not check(stage.captions[0] == "Сейчас · ур. " + V6Build.ROMAN[level - 1] and stage.captions[1] == "После · ур. " + V6Build.ROMAN[level], "pair captions " + str(stage.captions)): return
			for side in 2:
				var visual: Array = game.stage.level_visual(runtime, stage.levels[side])
				if not visual.is_empty() and ResourceLoader.exists(str(visual[0])):
					if not check(stage.paths[side] == str(visual[0]), "pair side %d is the city's scene" % side): return
			var city_now: Array = game.stage.level_visual(runtime, level)
			var city_next: Array = game.stage.level_visual(runtime, level + 1)
			var differs := not city_now.is_empty() and not city_next.is_empty() and BuildingStage.family(str(city_now[0])) != BuildingStage.family(str(city_next[0]))
			if not city_now.is_empty() and not city_next.is_empty() and ResourceLoader.exists(str(city_now[0])) and ResourceLoader.exists(str(city_next[0])):
				if not check(stage.fresh_model() == differs, "a new model is marked as new"): return
				if differs:
					fresh += 1
			if not check(main_action == "Улучшить" or main_action.begins_with("Сначала: "), "one main upgrade action: " + main_action): return
			if level == cap - 1 and main_action == "Улучшить":
				# IV -> V is still offered: the quote opens for V.
				var sent: int = game.quotes_sent
				main_button.pressed.emit()
				if not check(await wait_for(func(): return game.modal_title.text == "Подтвердить работу" and find_button(game.modal, "Начать") != null), "level %d still upgrades to %d" % [level, level + 1]): return
				if not check(game.quotes_sent == sent + 1 and game.modal_eyebrow.text == "УЛУЧШЕНИЕ ДО УР. " + V6Build.ROMAN[level], "the quote is for the open level"): return
		elif level < 11:
			if not check(stage.levels == [level, 0] and stage.soon and stage.captions[1] == "После · скоро" and stage.paths[1] == "", "«После» past the open level is a «Скоро» card: " + str(stage.levels)): return
			if not check(stage.captions[0] == "Сейчас · ур. " + V6Build.ROMAN[level - 1], "the standing building shows as it is"): return
			if not check(main_button != null and main_button.text == "Скоро" and main_button.disabled and find_button(game.modal_body, "Улучшить") == null, "a disabled «Скоро» instead of «Улучшить»: " + main_action): return
			if not check(game.modal_body.find_child("KitRequirements", true, false) == null and game.modal_body.find_child("KitTimer", true, false) == null, "no cost, time or requirements of the next level"): return
			var sent: int = game.quotes_sent
			var refused: int = game.capped_requests
			var orders: int = game.state.v6.orders.size()
			main_button.pressed.emit()
			var b: Dictionary = game.v6_panels.building("B11")
			await game.open_building_ring({"item": game.state.city.buildings.filter(func(x): return x.get("conceptType", "") == "B11")[0], "position": Vector3.ZERO})
			var ring_labels: Array = game.action_ring.buttons.map(func(x): return x.tooltip_text)
			if not check(not ring_labels.has("Улучшить") and ring_labels.has("Сведения"), "the ring offers no upgrade: " + str(ring_labels)): return
			game.action_ring.close()
			await game.v6_panels.confirm({"kind": "construction", "building": "B11", "target": level + 1})
			var direct: Dictionary = await game.request("command", {"kind": "v6quote", "intent": {"kind": "construction", "building": "B11", "target": level + 1, "economy_version": game.v6_panels.VERSION}})
			var ordered: bool = await game.command({"kind": "v6", "intent": {"kind": "construction", "building": "B11", "target": level + 1, "economy_version": game.v6_panels.VERSION}})
			var legacy_upgrade: bool = await game.command({"kind": "kingdom", "action": "upgrade", "buildingId": str(b.get("id", "")), "expectedLevel": level})
			var legacy_level: bool = await game.command({"kind": "legacyBuilding", "action": "level", "buildingId": str(b.get("id", "")), "level": level + 1})
			if not check(game.quotes_sent == sent and game.capped_requests == refused + 5 and direct.get("capped", false) and not ordered and not legacy_upgrade and not legacy_level, "no entry point asks past the open level (%d refused)" % (game.capped_requests - refused)): return
			if not check(game.state.v6.orders.size() == orders and game.modal_title.text != "Подтвердить работу", "nothing was started"): return
			cases.append({"case": "open_level", "level": level, "refused": game.capped_requests - refused})
		else:
			if not check(stage.levels == [11, 0] and not stage.soon and stage.captions[0] == "Окончательный уровень · ур. XI", "XI shows the building alone"): return
	cases.append({"case":"pair", "fresh_models":fresh})
	# The strip never names a level past the open one as reachable.
	if not check(await open_strip(0), "strip opens for the open-level check"): return
	var romans_past: Array = V6Build.ROMAN.slice(cap)
	var soon_types: Array = []
	for type: String in build.states:
		var note := str(build.states[type].get("note", ""))
		for numeral: String in romans_past:
			if not check(not note.contains(" " + numeral + " ") and not note.ends_with(" " + numeral), "card %s names no level past the open one: %s" % [type, note]): return
		if build.states[type].state == "soon":
			soon_types.append(type)
	cases.append({"case":"strip_open_level", "soon":soon_types})
	# The live pair renders only while it moves (render on demand).
	await seed_case("B11", 2)
	await game.v6_panels.inspect("B11")
	var live: Node = game.modal_hero.find_child("BuildingStage", true, false)
	if not check(await wait_for(func(): return live.models_placed >= 2 and live.view.modulate.a > 0.99, 20.0), "the pair is shown"): return
	if not check(await wait_for(func(): return not live.rendering(), 6.0), "after the intro turn the pair holds its picture"): return
	var held: int = live.rendered_frames
	await frames(30)
	if not check(live.rendered_frames == held and not live.rendering(), "an idle window renders no 3D"): return
	live.drag_begin()
	live.drag_by(40.0)
	await frames(2)
	if not check(live.rendered_frames > held, "turning the pair renders it"): return
	live.drag_end()
	if not check(await wait_for(func(): return not live.rendering(), 10.0), "and it holds again once it settles"): return
	cases.append({"case":"render_on_demand", "frames_while_turning": live.rendered_frames - held})
	# An unbuilt type: «Будет построено · ур. I».
	await seed_case("B02", 6)
	var unbuilt := ""
	for type: String in types:
		if game.v6_panels.building(type).is_empty():
			unbuilt = type
			break
	await game.v6_panels.inspect(unbuilt)
	var single: Node = game.modal_hero.find_child("BuildingStage", true, false)
	if not check(single != null and single.levels == [0, 1] and single.captions[1] == "Будет построено · ур. I", "unbuilt type shows level I to build"): return

	var report := {"status":"passed", "checks":checks, "cases":cases, "fixture":"synthetic localhost; real main scene, touches and HTTP server; no real account writes"}
	var path := OS.get_environment("DRENOVAR_QA_REPORT")
	var file := FileAccess.open(path if not path.is_empty() else "user://qa-build-strip.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report))
	file.close()
	print(JSON.stringify({"status":"passed", "checks":checks, "cases":cases.size()}))
	game.queue_free()
	await frames(2)
	quit()
