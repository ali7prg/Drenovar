extends SceneTree
## 1023 safe area and full-window width in the real game scene against the synthetic V6 fixture with
## the adventure on and the town hall at III:
##   DRENOVAR_SERVER_ROOT=<server checkout> DRENOVAR_QA_CONDITIONAL=1 DRENOVAR_QA_ADVENTURE=1 DRENOVAR_QA_HALL=3 \
##     node godot/tools/qa-v6-1022-server.mjs
##   godot --headless --path godot/project -s qa_safe_area.gd -- --server=http://127.0.0.1:8799
## Checks, on the 1366 × 630 canvas:
## - no insets (a screen without a notch): the HUD keeps its 1022 frame (52 / 4 / 52 / 24) and the
##   building window (its hero takes half the width) is never wider than the screen, so its close
##   medallion is whole (1022: the window grew past the right edge and the medallion was cut);
## - an iPhone 12 in landscape (47 pt at each side, 21 pt at the bottom: 76 / 0 / 76 / 34 units,
##   simulated with SafeArea.override): every visible HUD button, the full windows' titles, close
##   medallions, resource plates and content, the construction strip's medallion, title and rail,
##   the forest row and its loading plate keep inside the safe area; the close medallion stays to
##   the right of the resource plates; docked windows keep inside it; the band still runs edge to
##   edge.

const SafeArea = preload("res://src/safe_area.gd")
const IPHONE_12 := Vector4(76, 0, 76, 34)
var game: Node
var checks := 0
var failures: Array[String] = []
var view := Vector2(1366, 630)

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_SAFE_AREA: " + detail)

func _initialize() -> void:
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func wait_until(condition: Callable, seconds := 10.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call():
			return true
		await process_frame
	return false

func safe_rect(insets: Vector4) -> Rect2:
	return Rect2(insets.x, insets.y, view.x - insets.x - insets.z, view.y - insets.y - insets.w)

func inside(rect: Rect2, area: Rect2) -> bool:
	return rect.position.x >= area.position.x - 0.5 and rect.position.y >= area.position.y - 0.5 \
		and rect.end.x <= area.end.x + 0.5 and rect.end.y <= area.end.y + 0.5

func describe(rect: Rect2) -> String:
	return "(%.0f, %.0f – %.0f, %.0f)" % [rect.position.x, rect.position.y, rect.end.x, rect.end.y]

## Every visible, clickable control under `from` (buttons and controls that take touches).
func touch_targets(from: Node, found: Array) -> Array:
	for child in from.get_children():
		if child is Control and not child.is_visible_in_tree():
			continue
		if child is BaseButton and child.is_visible_in_tree() and child.size.x > 1.0:
			found.append(child)
		touch_targets(child, found)
	return found

func set_insets(insets: Vector4) -> void:
	SafeArea.override = insets
	game.refresh_safe_area()

func full_window_checks(name: String, insets: Vector4) -> void:
	var area := safe_rect(insets)
	var modal: Control = game.modal
	var screen := Rect2(Vector2.ZERO, view)
	check(modal.size.x <= view.x + 0.5, "%s: window %.0f wide on a %.0f screen" % [name, modal.size.x, view.x])
	check(inside(modal.get_global_rect(), screen), "%s: window %s leaves the screen" % [name, describe(modal.get_global_rect())])
	var close: Control = game.modal_close
	check(close.is_visible_in_tree() and inside(close.get_global_rect(), area), "%s: close medallion %s outside the safe area %s" % [name, describe(close.get_global_rect()), describe(area)])
	var title: Control = game.modal_title
	check(inside(title.get_global_rect(), area), "%s: title %s outside the safe area" % [name, describe(title.get_global_rect())])
	# The content column inside the window's margins (the margins themselves may reach the notch).
	var content: Control = game.modal_content.get_child(0)
	var body := content.get_global_rect()
	check(body.position.x >= area.position.x - 0.5 and body.end.x <= area.end.x + 0.5, "%s: content %s outside the safe area's sides" % [name, describe(body)])
	var wallet: Control = game.modal_wallet
	if wallet.is_visible_in_tree() and wallet.size.x > 1.0:
		var plates := wallet.get_global_rect()
		check(inside(plates, area), "%s: resource plates %s outside the safe area" % [name, describe(plates)])
		check(plates.end.x <= close.get_global_rect().position.x + 0.5, "%s: resource plates %s run into the close medallion %s" % [name, describe(plates), describe(close.get_global_rect())])
	var band: Control = game.modal_header
	check(band.get_global_rect().position.x <= 0.5 and band.get_global_rect().end.x >= view.x - 0.5, "%s: the head band no longer runs edge to edge %s" % [name, describe(band.get_global_rect())])

func run() -> void:
	root.size = Vector2i(view)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while (game.scene_loading or not is_instance_valid(game.stage) or not game.launch_done) and Time.get_ticks_msec() < deadline:
		await process_frame
	await wait_until(func(): return not game.player_id.is_empty() and not game.showing_cached_state, 20.0)
	await frames(30)
	# --- no insets: the 1022 frame, and the building window fits the screen ---------------------
	check(SafeArea.insets == Vector4.ZERO, "a headless run reports no insets: %s" % str(SafeArea.insets))
	var outer: Control = game.hud_outer
	check(outer.offset_left == 52 and outer.offset_top == 4 and outer.offset_right == -52 and outer.offset_bottom == -24,
		"HUD frame without insets: %s" % str([outer.offset_left, outer.offset_top, outer.offset_right, outer.offset_bottom]))
	game.v6_panels.inspect("B01")
	await wait_until(func(): return game.modal.visible and game.modal_layout == "full", 10.0)
	await frames(20)
	full_window_checks("building window, no insets", Vector4.ZERO)
	# The widest row of the 1022 upgrade window (B11 at IV: the chips of its requirements) asked for
	# 699 units beside the 683 unit hero; 1022 grew the window to 1382 units and cut the close
	# medallion at 1372. A row that wide is added here; the hero gives way instead.
	var wide_row := Control.new()
	wide_row.custom_minimum_size = Vector2(760, 8)
	game.modal_body.add_child(wide_row)
	await frames(6)
	full_window_checks("building window with a 760 unit row", Vector4.ZERO)
	check(game.modal_hero.size.x >= view.x * 0.3 - 0.5, "the hero keeps at least 30 %% of the width: %.0f" % game.modal_hero.size.x)
	print("QA_SAFE_AREA building_window width=%.0f close=%s hero=%.0f" % [game.modal.size.x, describe(game.modal_close.get_global_rect()), game.modal_hero.size.x])
	wide_row.queue_free()
	game.close_modal()
	await frames(10)
	# --- an iPhone 12 in landscape ------------------------------------------------------------
	set_insets(IPHONE_12)
	await frames(4)
	var area := safe_rect(IPHONE_12)
	check(outer.offset_left == 76 and outer.offset_right == -76 and outer.offset_bottom == -34 and outer.offset_top == 4,
		"HUD frame with iPhone insets: %s" % str([outer.offset_left, outer.offset_top, outer.offset_right, outer.offset_bottom]))
	var targets := touch_targets(outer, [])
	var outside: Array = []
	for target: Control in targets:
		if not inside(target.get_global_rect(), area):
			outside.append("%s %s" % [target.name, describe(target.get_global_rect())])
	check(targets.size() >= 4, "HUD buttons found: %d" % targets.size())
	check(outside.is_empty(), "HUD buttons outside the safe area: %s" % str(outside))
	# Full windows: the building window (hero column) and the economy (no hero).
	game.v6_panels.inspect("B01")
	await wait_until(func(): return game.modal.visible and game.modal_layout == "full", 10.0)
	await frames(20)
	full_window_checks("building window, iPhone insets", IPHONE_12)
	var hero: Control = game.modal_hero
	check(hero.get_global_rect().position.x >= area.position.x - 0.5, "building window: hero column %s under the notch" % describe(hero.get_global_rect()))
	game.close_modal()
	await frames(10)
	game.v6_panels.economy()
	await wait_until(func(): return game.modal.visible and game.modal_layout == "full", 10.0)
	await frames(20)
	full_window_checks("economy, iPhone insets", IPHONE_12)
	# A window that opens before the insets change follows them at once.
	set_insets(Vector4.ZERO)
	await frames(4)
	full_window_checks("economy, insets removed", Vector4.ZERO)
	set_insets(IPHONE_12)
	await frames(4)
	full_window_checks("economy, insets back", IPHONE_12)
	game.close_modal()
	await frames(10)
	# A docked window (wide): inside the safe area.
	game.open_modal("Проверка", "wide")
	await frames(6)
	check(inside(game.modal.get_global_rect(), area), "wide window %s outside the safe area" % describe(game.modal.get_global_rect()))
	game.close_modal()
	await frames(10)
	# The construction strip.
	await game.v6_panels.load_catalogue()
	game.v6_panels.catalog()
	await wait_until(func(): return game.modal.visible and game.modal_layout == "strip", 10.0)
	await frames(30)
	var strip: Control = game.v6_panels.build.view
	check(strip != null and strip.is_visible_in_tree(), "construction strip open")
	if strip != null:
		var close_rect: Rect2 = strip.close_button.get_global_rect()
		check(inside(close_rect, area), "strip close medallion %s outside the safe area" % describe(close_rect))
		check(inside(strip.heading.get_global_rect(), area), "strip title plate %s outside the safe area" % describe(strip.heading.get_global_rect()))
		check(inside(strip.rail.get_global_rect(), area), "strip rail %s outside the safe area" % describe(strip.rail.get_global_rect()))
		check(strip.swipe.pad_right >= IPHONE_12.z, "the strip's last card rests clear of the notch (pad %.0f)" % strip.swipe.pad_right)
		var wallet: Control = game.modal_wallet
		if wallet.is_visible_in_tree() and wallet.size.x > 1.0:
			check(wallet.get_global_rect().end.x <= close_rect.position.x + 0.5, "strip resource plates %s run into the close medallion %s" % [describe(wallet.get_global_rect()), describe(close_rect)])
		for target: Control in touch_targets(strip.rail, []):
			check(inside(target.get_global_rect(), area), "strip category %s outside the safe area" % describe(target.get_global_rect()))
	game.close_modal()
	await frames(10)
	# The forest row (the adventure is on in this fixture) and its loading plate. The row shows
	# once the forest is attached and no intro is presenting; its geometry is checked in the frame
	# it is laid out.
	await wait_until(func(): return game.forest_game != null and game.forest_game.hud != null and game.forest_game.hud.bar != null and game.forest_game.world_ready(), 60.0)
	if game.forest_game != null and game.forest_game.hud != null and game.forest_game.hud.bar != null:
		var hud: Control = game.forest_game.hud
		var bar: Control = hud.bar
		await wait_until(func(): return bar.is_visible_in_tree(), 5.0)
		bar.visible = true
		hud.layout()
		check(inside(bar.get_global_rect(), area), "forest row %s outside the safe area" % describe(bar.get_global_rect()))
		for target: Control in touch_targets(bar, []):
			check(inside(target.get_global_rect(), area), "forest row button %s %s outside the safe area" % [target.name, describe(target.get_global_rect())])
		var nav: Control = game.nav_buttons.world.get_parent()
		check(not bar.get_global_rect().intersects(nav.get_global_rect()), "forest row %s overlaps the navigation %s" % [describe(bar.get_global_rect()), describe(nav.get_global_rect())])
		print("QA_SAFE_AREA forest_row=%s nav=%s" % [describe(bar.get_global_rect()), describe(nav.get_global_rect())])
	else:
		check(false, "forest row available")
	var plate: Control = game.forest_progress
	check(inside(Rect2(plate.global_position, plate.size), area), "forest loading plate %s outside the safe area" % describe(Rect2(plate.global_position, plate.size)))
	# Back to no insets: the 1022 frame again.
	set_insets(Vector4.ZERO)
	await frames(4)
	check(outer.offset_left == 52 and outer.offset_right == -52 and outer.offset_bottom == -24, "HUD frame after the insets went away")
	print("QA_SAFE_AREA checks=%d failures=%d" % [checks, failures.size()])
	for failure in failures:
		print("  FAIL ", failure)
	SafeArea.override = Vector4(-1, -1, -1, -1)
	game.queue_free()
	await frames(2)
	quit(0 if failures.is_empty() else 1)
