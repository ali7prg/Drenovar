extends SceneTree

# Main scene + real HTTP solver + actual touch input. No replay scene and no
# direct calls to the march/Continue handlers. The server is loopback-only.
var game
var checks := 0
var failures: Array[String] = []
var folder := ""
var capture := false
var phases := {}
var battle_id := ""
var observed_actions := {}
var clip_samples := 0
var round_index := 0
var rounds := 2
var results := []
var fast_travel := false
var evidence_root := ""
var attack_shots := 0
var selected_units := {"ENG-01":20,"ENG-03":20,"ENG-05":5}
var start_level := 1

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-dir="): folder = arg.trim_prefix("--qa-dir=")
		if arg == "--capture": capture = true
		if arg == "--army-200": selected_units = {"ENG-01":105,"ENG-02":95}
		if arg.begins_with("--start-level="): start_level = int(arg.trim_prefix("--start-level="))
		if arg == "--fast-travel": fast_travel = true
		if arg.begins_with("--rounds="): rounds = int(arg.trim_prefix("--rounds="))
	call_deferred("run")

func check(ok: bool, label: String) -> bool:
	checks += 1
	print("PLAYABLE_CHECK ", label, " ", ok)
	if not ok: failures.append(label)
	return ok

func wait_until(test: Callable, seconds := 60.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec() > deadline: return false
		await process_frame
	return true

func button(node: Node, title: String) -> Button:
	if node is Button and node.text == title: return node
	for child in node.get_children():
		var found := button(child, title)
		if found != null: return found
	return null

func tap(control: Control) -> void:
	if control == null:
		check(false, "touch target exists")
		return
	await process_frame
	await process_frame
	var at := control.get_global_rect().get_center()
	check(root.get_visible_rect().has_point(at), "touch target within viewport: " + str(control.name))
	for pressed in [true, false]:
		var event := InputEventScreenTouch.new()
		event.position = at
		event.pressed = pressed
		root.push_input(event, true)
		await process_frame
	await process_frame

func shot(name: String) -> void:
	if not capture: return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join(name + ".png"))

func write_json(name: String, value: Variant) -> void:
	var file := FileAccess.open(folder.path_join(name), FileAccess.WRITE)
	file.store_string(JSON.stringify(value, "  "))
	file.close()

func observe_actions() -> void:
	if not is_instance_valid(game) or not is_instance_valid(game.stage) or battle_id.is_empty(): return
	var actor: Node = game.stage.actors.get_node_or_null(NodePath(battle_id))
	if actor == null: return
	clip_samples += 1
	for unit in actor.get_children():
		var clip: String = str(unit.get_meta("clip", ""))
		if not clip.is_empty(): observed_actions[clip] = true
		if capture and clip == "attack" and attack_shots < 3:
			root.get_texture().get_image().save_png(folder.path_join("attack-%02d.png" % attack_shots))
			attack_shots += 1
			break

func run() -> void:
	if folder.is_empty(): quit(2); return
	root.size = Vector2i(844, 390) if capture else Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.single_scene = true # Same scene lifetime policy as the iOS client.
	root.add_child(game)
	if not check(game.endpoint.begins_with("http://127.0.0.1:"), "synthetic loopback only"): quit(2); return
	if not check(await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.busy), "normal game ready"): finish(); return
	await game.device_login()
	await game.create_settlement()
	await game.sync_account()
	check(game.v6_panels.enabled(), "interactive V6 account loaded")
	var player: String = game.player_id
	process_frame.connect(observe_actions)
	evidence_root = folder
	for i in rounds:
		round_index = i
		folder = evidence_root.path_join("hunt-%02d" % (i+1))
		DirAccess.make_dir_recursive_absolute(folder)
		phases = {}; observed_actions = {}; clip_samples = 0; battle_id = ""; attack_shots = 0
		var target: Dictionary = game.state.encounters.filter(func(e): return int(e.level) == (i + start_level - 1) % 3 + 1)[0]
		if fast_travel and target.status == "defeated": await jump_clock(float(target.respawnAt) + 1.0)
		await hunt()
		results.append({"round":i+1,"level":(i+start_level-1)%3+1,"actions":observed_actions.keys(),"samples":clip_samples,"phases":phases.duplicate(),"trace":game.stage.combat_view.trace.duplicate(true),"memory_static_mb":Performance.get_monitor(Performance.MEMORY_STATIC)/1048576.0,"nodes":Performance.get_monitor(Performance.OBJECT_NODE_COUNT),"orphans":Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)})
		if not failures.is_empty(): break
	folder = evidence_root
	check(game.diagnostics.network_failures == 0, "no false offline notice after a server error")
	check(not game.command_in_progress and not game.busy, "second hunt leaves commands unlocked")
	# Existing encrypted session survives a full scene teardown/restart.
	game.process_mode = Node.PROCESS_MODE_DISABLED
	game.queue_free()
	await process_frame
	game = load("res://main.tscn").instantiate()
	game.single_scene = true
	root.add_child(game)
	check(await wait_until(func(): return not game.scene_loading and game.player_id == player and game.v6_panels.enabled()), "restart restores same settlement")
	await process_frame
	await process_frame
	check(await wait_until(func(): return not game.busy and not game.restoring_session and not game.v6_panels.catalogue_loading, 10), "restored account requests finish")
	finish()

func jump_clock(at: float) -> void:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request(game.endpoint + "/qa/clock", ["Content-Type: application/json", "X-Drenovar-Staging-Key: " + game.staging_key], HTTPClient.METHOD_POST, JSON.stringify({"time":at}))
	await request.request_completed
	request.queue_free()
	await game.poll_account_state(true)
	await process_frame

func hunt() -> void:
	var garrison: Dictionary = game.state.healthy.duplicate(true)
	game.close_modal()
	# Pick an actually reachable city target through the same preview endpoint.
	var chosen: Dictionary = {}
	for target in game.state.encounters:
		if int(target.level) != (round_index + start_level - 1) % 3 + 1: continue
		var preview: Dictionary = await game.send_request("march-preview", {"kind":"deploy", "encounterId":target.id, "units":selected_units, "wall":game.march_wall()}, false, 5.0)
		if preview.has("path"): chosen = target; break
	if not check(not chosen.is_empty(), "server supplies a reachable target"): return
	game.inspect_encounter(chosen)
	await tap(button(game.modal_footer, "Атаковать"))
	if not check(await wait_until(func(): return game.modal_title.text == "Создать войско", 5), "Attack opens formation"): return
	await tap(button(game.modal_footer, "Очистить"))
	# Input values in the genuine roster controls. Final command is a touch.
	var spins: Array = game.modal_body.find_children("*", "SpinBox", true, false)
	var roster: Array = game.data.englishRoster.filter(func(unit): return int(garrison.get(unit.id, 0)) > 0)
	for i in spins.size(): spins[i].value = int(selected_units.get(roster[i].id, 0))
	var send: Button = game.modal_footer.find_child("MarchSend", true, false)
	if not check(await wait_until(func(): return send.get_meta("route_ready", false) and not send.disabled, 35), "selected formation has server route"): return
	await shot("01-formation")
	var old_ids: Array = game.state.armies.map(func(a): return a.id)
	await tap(send)
	if not check(await wait_until(func(): return game.state.armies.any(func(a): return a.target == chosen.id and a.id not in old_ids), 35), "one touch starts a real army"): return
	var army: Dictionary = game.state.armies.filter(func(a): return a.target == chosen.id and a.id not in old_ids)[0]
	battle_id = army.id
	if not process_frame.is_connected(observe_actions): process_frame.connect(observe_actions)
	write_json("departed-army.json", army)
	check(army.units.size() == selected_units.size() and selected_units.keys().all(func(id): return int(army.units.get(id, 0)) == int(selected_units[id])), "server army equals selected formation")
	check(game.state.armies.filter(func(a): return a.target == chosen.id and a.id not in old_ids).size() == 1, "one army from one touch")
	game.close_modal()
	game.followed_army = battle_id
	game.stage.zoom = 32.0
	if fast_travel: await jump_clock(float(army.arrivesAt) - 3000.0)
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline:
		for a in game.state.armies:
			if a.id != battle_id: continue
			if not phases.has(a.status):
				phases[a.status] = game.server_time()
				print("PLAYABLE_PHASE ", a.status)
				await shot("02-" + a.status)
		if game.state.reports.any(func(r): return r.id == battle_id and game.stage.combat_view.frame_time >= game.stage.combat_view.visual_end(float(r.finishedAt))+1200): break
		await process_frame
	if not check(game.state.reports.any(func(r): return r.id == battle_id), "real server battle produces a report"): return
	check(not observed_actions.is_empty(), "normal gameplay creates visual actors")
	check(observed_actions.has("attack"), "actual game renders scheduled attacks")
	var report: Dictionary = game.state.reports.filter(func(r): return r.id == battle_id)[0]
	write_json("server-report.json", report)
	if not check(await wait_until(func(): return game.result_notice.visible or game.result_open, 12), "result becomes available after visual contact"): return
	if not game.result_open: await tap(game.result_notice)
	await shot("03-result")
	await tap(button(game.modal_footer, "Продолжить"))
	check(not game.modal.visible and not game.dimmer.visible, "Continue restores game control")
	await shot("04-continue")
	if fast_travel:
		var current: Array = game.state.armies.filter(func(a): return a.id == battle_id)
		if not current.is_empty(): await jump_clock(float(current[0].returnsAt) + 1.0)
	check(await wait_until(func(): return game.state.armies.all(func(a): return a.id != battle_id or a.status == "returned"), 180), "survivors return through real server clock")
	await game.sync_account()
	for unit_id in selected_units:
		var expected: int = int(garrison.get(unit_id, 0)) - int(report.dead.get(unit_id, 0)) - int(report.wounded.get(unit_id, 0))
		check(int(game.state.healthy.get(unit_id, 0)) == expected, "returned garrison matches report: " + unit_id)

func finish() -> void:
	var result := {"status":"passed" if failures.is_empty() else "failed", "checks":checks, "failures":failures, "phases":phases, "observed_actions":observed_actions.keys(), "clip_samples":clip_samples, "device":"Linux Godot; no physical iPhone acceptance", "clock":"test clock skips travel and respawn only; combat wall clock" if fast_travel else "wall clock", "rounds":results, "entry":"main.tscn, interactive UI and HTTP"}
	write_json("result.json", result)
	print(JSON.stringify(result))
	if is_instance_valid(game):
		game.process_mode = Node.PROCESS_MODE_DISABLED
		game.queue_free()
	await process_frame
	await process_frame
	await create_timer(0.2).timeout
	quit(0 if failures.is_empty() else 1)
