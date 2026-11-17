extends SceneTree

# Main scene, real touch, loopback synthetic server (playable-server.mjs), real
# travel time (no test clock). Fails when sending a march or showing it stalls
# the main thread. Build 1013 held one frame for ~14 s on a desktop CPU here
# (synchronous contact-place search, restarted by every patrol position).
# Headless Linux frame times; not a measurement of iPhone FPS.
var game
var checks := 0
var failures: Array[String] = []
const STALL_MS := 250.0

func _initialize() -> void: call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("SMOOTHNESS ", label, " ", ok)

func wait_until(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec() > end: return false
		await process_frame
	return true

func find_button(node: Node, title: String) -> Button:
	if node is Button and node.text == title: return node
	for child in node.get_children():
		var value := find_button(child, title)
		if value != null: return value
	return null

func tap(node: Control) -> void:
	if node == null:
		check(false, "touch target exists")
		return
	var at := node.get_global_rect().get_center()
	for pressed in [true, false]:
		var event := InputEventScreenTouch.new(); event.position = at; event.pressed = pressed; root.push_input(event, true)
		await process_frame
	await process_frame

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate(); game.single_scene = true; root.add_child(game)
	if not await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.busy, 90): quit(2); return
	if not game.endpoint.begins_with("http://127.0.0.1:"): quit(2); return
	await game.device_login(); await game.create_settlement(); await game.sync_account(); game.close_modal()
	# The level I lair is where build 1013 stalled (archers behind the melee).
	var level := 1
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--level="): level = int(arg.trim_prefix("--level="))
	# The creature patrols a 20 s round; where it stands at departure decides how
	# crowded its contact arc is. 1013 stalled from about 6 s into the round.
	var wait := 6.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--wait="): wait = float(arg.trim_prefix("--wait="))
	await create_timer(wait).timeout
	await game.poll_account_state(true)
	var target: Dictionary = game.state.encounters.filter(func(e): return int(e.level) == level)[0]
	game.inspect_encounter(target); await process_frame; await process_frame
	await tap(find_button(game.modal_footer, "Атаковать"))
	check(await wait_until(func(): return game.modal_title.text == "Создать войско", 5), "Attack opens formation")
	# 200 members, mixed: melee, riders and archers (archers were the slowest).
	var roster: Array = game.data.englishRoster.filter(func(u): return u.id != "SIEGE-RAM-01" and int(game.state.healthy.get(u.id, 0)) > 0)
	var wanted := {"ENG-01": 70, "ENG-02": 60, "ENG-03": 40, "ENG-05": 30}
	var spins: Array = game.modal_body.find_children("*", "SpinBox", true, false)
	if "--first-two" in OS.get_cmdline_user_args():
		# The window's own preselection plus 20 in each of the first two rows.
		spins[0].value = 20; spins[1].value = 20
	else:
		for i in mini(spins.size(), roster.size()): spins[i].value = wanted.get(roster[i].id, 0)
	await create_timer(1.0).timeout
	var send: Button = game.modal_footer.find_child("MarchSend", true, false)
	var tapped := Time.get_ticks_msec()
	# Frame times are measured from the tap: the stall began with the answer.
	var worst := 0.0
	var previous := Time.get_ticks_usec()
	await tap(send)
	var accept_end := Time.get_ticks_msec() + 30000
	while not (not game.command_in_progress and not game.busy and not game.modal.visible) and Time.get_ticks_msec() < accept_end:
		await process_frame
		var now := Time.get_ticks_usec()
		worst = maxf(worst, (now - previous) / 1000.0)
		previous = now
	check(not game.command_in_progress and not game.modal.visible, "march accepted and window closed")
	var accepted_ms := Time.get_ticks_msec() - tapped
	check(accepted_ms < 2000, "march accepted within 2 s on loopback (%d ms)" % accepted_ms)
	var army: Dictionary = {}
	for a in game.state.armies:
		if a.target == target.id: army = a
	check(not army.is_empty(), "one army sent")
	# Watch the whole outbound walk, the fight and the start of the return.
	var clips := {}
	var seen_actor := false
	var end := Time.get_ticks_msec() + int(maxf(8000.0, float(army.get("arrivesAt", 0)) - game.server_time() + 9000.0))
	while Time.get_ticks_msec() < end:
		await process_frame
		var now := Time.get_ticks_usec()
		worst = maxf(worst, (now - previous) / 1000.0)
		previous = now
		var actor = game.stage.actors.get_node_or_null(NodePath(str(army.id)))
		if actor != null:
			seen_actor = true
			for unit in actor.get_children(): clips[unit.get_meta("clip", "")] = true
		if game.result_open: break
	check(worst < STALL_MS, "no frame stalls during march and fight (worst %.1f ms)" % worst)
	check(seen_actor, "marching army is drawn")
	check(clips.has("attack"), "fight plays attack clips")
	var plan: Dictionary = game.stage.army_routes.get(str(army.id), {}).get("engage", {})
	check(not plan.is_empty() and not plan.get("solving", true), "contact places refined before the result")
	print(JSON.stringify({"checks": checks, "failures": failures, "worst_frame_ms": worst, "accepted_ms": accepted_ms, "clips": clips.keys(), "units": army.get("units", {}), "level": level,
		"method": "Linux Godot headless main scene, real touch, loopback synthetic V6 server, real travel time; not iPhone FPS"}))
	game.queue_free(); await process_frame; await process_frame
	quit(0 if failures.is_empty() else 1)
