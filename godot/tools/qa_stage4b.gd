extends SceneTree
## Stage 4b checks (ui_premium/STAGE4B.md) against the buildings-ui fixture on 8792:
## the menu's medallion tiles (grouped, badges, real Buttons that open their windows) and its
## premium switches (sound, less motion); an objective claimed from its quest card (only the
## current one offers the claim, the reward reaches the stock, a good-tone toast); the toasts'
## tones and the connection pill's rule (only after a failure and 10 s without an answer); the
## ring's unfold (≤ 180 ms, every medallion's rect at its place from the first frame, a tap
## during the unfold runs its action).

const VERSION := "DRENOVAR-V6-C1.0"

var game
var checks := 0
var hud_saved := PackedByteArray()
var hud_existed := false

func check(ok: bool, label: String) -> bool:
	checks += 1
	if not ok:
		push_error(label)
		print(JSON.stringify({"status": "failed", "checks": checks, "reason": label}))
		restore_hud()
		quit(1)
	return ok

func wait_for(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not test.call():
		if Time.get_ticks_msec() > end:
			return false
		await process_frame
	return true

func admin(path: String, body: Dictionary) -> Variant:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request("http://127.0.0.1:8792/qa/" + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(body))
	var result: Array = await request.request_completed
	request.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8())

func instance_of(type: String) -> Dictionary:
	for b: Dictionary in game.state.city.buildings:
		if str(b.get("conceptType", "")) == type:
			return b
	return {}

func buttons(node: Node) -> Array:
	return node.find_children("*", "Button", true, false)

func button(node: Node, title: String) -> Button:
	for item: Button in buttons(node):
		if item.text == title:
			return item
	return null

func restore_hud() -> void:
	var path := "user://hud.cfg"
	if hud_existed:
		var file := FileAccess.open(path, FileAccess.WRITE)
		if file != null:
			file.store_buffer(hud_saved)
	elif FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))

func tap_at(at: Vector2) -> void:
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.position = at
		event.global_position = at
		event.pressed = pressed
		root.push_input(event, true)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	if FileAccess.file_exists("user://hud.cfg"):
		hud_existed = true
		hud_saved = FileAccess.get_file_as_bytes("user://hud.cfg")
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	if not check(await wait_for(func(): return not game.scene_loading and is_instance_valid(game.stage), 240.0), "scene ready"):
		return
	game.session = "device." + "a".repeat(64)
	await admin("case", {"type": "B05", "level": 5})
	await game.sync_account()
	if not check(await wait_for(func(): return game.v6_panels.enabled(), 30.0), "v6 state"):
		return
	if not check(await game.v6_panels.load_catalogue(), "catalogue"):
		return

	# 1. The menu: grouped medallion tiles that are real Buttons, and the switches.
	game.show_controls_menu()
	if not check(game.modal.visible and game.modal_title.text == "Меню", "menu opens"):
		return
	var tiles: Array = buttons(game.modal_body).filter(func(b): return String(b.name).begins_with("Tile_"))
	var captions: Array = tiles.map(func(b): return b.text)
	for wanted: String in ["Поселение и строительство", "Очереди", "Экономика", "Цели поселения", "Армия", "Летопись сражений", "Аккаунт", "Плавность на устройстве", "О приложении"]:
		if not check(captions.has(wanted), "menu tile «%s» (%s)" % [wanted, str(captions)]):
			return
	for group: String in ["MenuSettlement", "MenuMap", "MenuAbout"]:
		if not check(game.modal_body.find_child(group, true, false) != null, "menu group " + group):
			return
	for tile: Button in tiles:
		if not check(tile.size.x >= 100.0 and tile.size.y >= 100.0, "tile «%s» is a large touch target (%s)" % [tile.text, str(tile.size)]):
			return
	var goals: Button = button(game.modal_body, "Цели поселения")
	var ready_goals: int = game.state.v6.get("starter", []).filter(func(o): return o.get("ready", false) and not o.get("claimed", false)).size()
	if not check(ready_goals == 0 or goals.badge == str(ready_goals), "objectives tile badge counts ready rewards (%s, %d)" % [goals.badge, ready_goals]):
		return
	var sound: CheckButton = game.modal_body.get_parent().get_parent().get_parent().find_child("SoundSwitch", true, false)
	if sound == null:
		sound = game.modal.find_child("SoundSwitch", true, false)
	var motion: CheckButton = game.modal.find_child("MotionSwitch", true, false)
	if not check(sound != null and motion != null, "sound and motion switches"):
		return
	if not check(sound.get_theme_icon("checked").get_size() == Vector2(64, 34), "premium switch at 64×34 (%s)" % str(sound.get_theme_icon("checked").get_size())):
		return
	var sound_before: bool = game.sound_on
	var motion_before: bool = game.reduced_motion
	sound.button_pressed = not sound_before
	if not check(game.sound_on == (not sound_before) and AudioServer.is_bus_mute(0) == sound_before, "sound switch mutes the master bus"):
		return
	sound.button_pressed = sound_before
	motion.button_pressed = true
	if not check(game.reduced_motion and game.action_ring.reduced_motion, "less motion reaches the ring"):
		return
	motion.button_pressed = motion_before
	button(game.modal_body, "Экономика").pressed.emit()
	if not check(await wait_for(func(): return game.modal_title.text == "Экономика поселения", 5.0), "the economy tile opens the economy"):
		return
	if not check(game.modal_body.find_child("Resource_wood", true, false) != null and game.modal_body.find_child("Income", true, false) != null, "economy cards"):
		return

	# 2. Objectives: the current one claims; the reward reaches the stock.
	await game.command({"kind": "v6collect"}, func(): pass)
	await game.sync_account()
	var starter: Array = game.state.v6.get("starter", [])
	var current := {}
	for step: Dictionary in starter:
		if not step.get("claimed", false):
			current = step
			break
	if not check(not current.is_empty() and current.get("ready", false), "the current objective is ready after collecting (%s)" % str(current)):
		return
	await game.v6_panels.objectives()
	if not check(game.modal_title.text == "Цели поселения", "objectives window"):
		return
	var claims: Array = buttons(game.modal_body).filter(func(b): return b.text == "Получить награду")
	if not check(claims.size() == 1, "only the current objective offers the claim (%d)" % claims.size()):
		return
	var card: Control = game.modal_body.find_child("Objective_" + str(current.id), true, false)
	if not check(card != null and claims[0].get_parent() == card, "the claim sits on the current quest card"):
		return
	var reward: Dictionary = current.get("reward", {})
	var before := {}
	for resource: String in reward:
		before[resource] = int(game.state.v6.stock.get(resource, 0))
	claims[0].pressed.emit()
	if not check(await wait_for(func(): return not game.command_in_progress and game.state.v6.get("starter", []).any(func(o): return o.id == current.id and o.get("claimed", false)), 10.0), "objective claimed on the server"):
		return
	for resource: String in reward:
		var gained := int(game.state.v6.stock.get(resource, 0)) - int(before[resource])
		var capped := int(game.state.v6.stock.get(resource, 0)) >= int(game.state.v6.capacities.get(resource, 0))
		if not check(gained == int(reward[resource]) or capped, "reward %s +%d reached the stock (%d)" % [resource, int(reward[resource]), gained]):
			return
	if not check(await wait_for(func(): return game.modal_title.text == "Цели поселения" and game.message.text.begins_with("Готово: награда получена"), 5.0), "window refreshed and a good toast (%s)" % game.message.text):
		return
	await process_frame
	if not check(game.message_tone == "good", "claim toast tone is good (%s)" % game.message_tone):
		return
	var claimed_card: Control = game.modal_body.find_child("Objective_" + str(current.id), true, false)
	if not check(claimed_card != null and claimed_card.ribbon == "Получено", "the claimed card reads «Получено»"):
		return

	# 3. Toasts: tones, calm errors, the connection pill's rule.
	game.message.text = "Код скопирован"
	await process_frame
	if not check(game.message_tone == "good", "a copy confirmation is good"):
		return
	game.message.text = "Строительство началось: Рынок · ур. IV"
	await process_frame
	if not check(game.message_tone == "info", "a neutral notice is info (%s)" % game.message_tone):
		return
	game.show_error({"error": "Сервер недоступен"})
	await process_frame
	if not check(game.message_tone == "warn" and game.message.text.contains("недоступен") and game.message.text.contains("повторим"), "an error is warn, calm and says what happens next (%s)" % game.message.text):
		return
	if not check(game.message.get_theme_stylebox("normal") is StyleBoxTexture, "toast on the kit plate"):
		return
	game.message.text = ""
	var failures: int = game.diagnostics.network_failures
	game.diagnostics.network_failures = 1
	game.last_ok_msec = Time.get_ticks_msec() - 3000
	game.update_connection_notice()
	if not check(not game.connection_badge.visible, "no pill 3 s after a failure"):
		return
	game.last_ok_msec = Time.get_ticks_msec() - 10500
	game.update_connection_notice()
	if not check(game.connection_badge.visible and game.connection_badge.text == game.OFFLINE_NOTICE and game.message.text != game.OFFLINE_NOTICE, "the pill after 10 s, never in the message line"):
		return
	game.diagnostics.network_failures = failures
	game.last_ok_msec = Time.get_ticks_msec()
	game.update_connection_notice()
	if not check(not game.connection_badge.visible, "the pill leaves with the next answer"):
		return

	# 4. The ring's unfold never blocks a tap.
	game.close_modal()
	if not check(game.action_ring.UNFOLD_SECONDS <= 0.18, "unfold within 180 ms"):
		return
	game.action_ring.reduced_motion = false
	var marker := {"item": instance_of("B05"), "position": Vector3.ZERO, "kind": "building"}
	game.stage.target = Vector3.ZERO
	game.stage.zoom = 40.0
	await create_timer(1.5).timeout
	await game.open_building_ring(marker)
	if not check(game.action_ring.is_open(), "ring opens"):
		return
	var info: Button = null
	for item: Button in game.action_ring.buttons:
		if item.tooltip_text == "Сведения":
			info = item
	if not check(info != null, "ring offers «Сведения»"):
		return
	var at_open: Vector2 = info.position
	var unfolding: bool = game.action_ring.buttons.any(func(b): return b.unfold < 1.0)
	if not check(unfolding and info.scale == Vector2.ONE and info.mouse_filter == Control.MOUSE_FILTER_STOP, "unfolding, the buttons at full scale and live"):
		return
	await process_frame
	var ring = game.action_ring
	var slot: Vector2 = info.position + Vector2(ring.BUTTON, ring.BUTTON) * 0.5 + info.spoke
	if not check(slot.distance_to(ring.camera.unproject_position(ring.anchor)) < 0.5 and info.unfold < 1.0, "mid-unfold the rect is already at its slot (only the drawing moves)"):
		return
	var hit := Rect2(info.global_position, Vector2(game.action_ring.BUTTON, game.action_ring.BUTTON)).get_center()
	tap_at(hit)
	if not check(await wait_for(func(): return game.modal.visible and not game.action_ring.is_open(), 5.0), "a tap during the unfold opens «Сведения» (%s)" % game.modal_title.text):
		return
	game.close_modal()
	await game.open_building_ring(marker)
	await create_timer(0.25).timeout
	if not check(game.action_ring.buttons.all(func(b): return is_equal_approx(b.unfold, 1.0)), "every medallion at rest after 250 ms"):
		return
	game.action_ring.reduced_motion = true
	game.action_ring.close()
	await game.open_building_ring(marker)
	if not check(game.action_ring.buttons.all(func(b): return is_equal_approx(b.unfold, 1.0)), "less motion: no unfold"):
		return
	game.action_ring.reduced_motion = motion_before
	game.action_ring.close()
	restore_hud()
	print(JSON.stringify({"status": "passed", "checks": checks}))
	game.queue_free()
	await process_frame
	quit(0)
