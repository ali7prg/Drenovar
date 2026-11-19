extends SceneTree
## Headless helper for evidence runs: plays the adventure through the real client (guide
## «Продолжить», mechanism UI, squad panel) against the local realm until the requested phase,
## advancing the realm's simulated clock (/test/clock) instead of waiting. Nothing is skipped on
## the server side: every task is a normal authoritative command.
##   godot --headless --path godot/project -s qa_forest_advance.gd -- --until=boss_unlocked

var game: Node
var forest: Node
var until := "boss_unlocked"
var steps := 0

func _initialize() -> void:
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func test_post(path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else {}
	return parsed if parsed is Dictionary else {}

func refresh() -> void:
	while game.busy:
		await process_frame
	var response: Dictionary = await game.request("state")
	if response.has("city"):
		game.accept(response)
	await frames(2)

func advance_to(server_ms: float) -> void:
	var now := float(forest.client.adv.get("serverTime", 0))
	await test_post("/test/clock?time=%d" % int(ceil(maxf(server_ms, now + 50.0))))
	await refresh()

func wait_settle() -> void:
	var settle: float = forest.client.last_settle_ms()
	if settle == INF:
		await refresh()
	else:
		await advance_to(settle + 300.0)

func solve_mechanism(site_id: String) -> void:
	var site: Dictionary = forest.content.site(site_id)
	forest.mech.open(site_id)
	await frames(1)
	if String(site.variation) == "paired_latch":
		await forest.mech.occupy()
		await wait_settle()
	for symbol in site.artifact.puzzle.solution:
		var before := int(forest.mech.mechanism().get("progress", 0))
		await forest.mech.send_symbol(String(symbol))
		var guard := 0
		while int(forest.mech.mechanism().get("progress", 0)) <= before and not bool(forest.mech.mechanism().get("solved", false)) and guard < 12:
			guard += 1
			await wait_settle()
			await frames(4)
			while forest.mech.sending or forest.client.in_flight:
				await process_frame
	forest.mech.close()

func form_squad() -> void:
	forest.panels.open_squad()
	await frames(1)
	for spin: SpinBox in game.modal_body.find_children("Squad_*", "SpinBox", true, false):
		spin.value = spin.max_value
	var submit: Button = game.modal_body.find_child("SquadSubmit", true, false)
	if submit != null:
		submit.pressed.emit()
	while forest.acting or forest.client.in_flight:
		await process_frame
	await frames(2)
	game.close_modal()

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--until="):
			until = argument.trim_prefix("--until=")
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty():
		await process_frame
	forest = game.forest_game
	await frames(5)
	await refresh()
	# Hall III intro (one-time presentation): acknowledge it the way «Пропустить» does.
	var deadline := Time.get_ticks_msec() + 8000
	while String(forest.client.adv.get("intro", {}).get("status", "")) != "acknowledged" and Time.get_ticks_msec() < deadline:
		if forest.intro.presenting():
			forest.intro.on_skip()
		else:
			await forest.request_action("skip_intro", {}, "adventure_intro")
		await frames(10)
		while forest.acting or forest.client.in_flight:
			await process_frame
		await refresh()
	game.close_modal()
	var hall5 := false
	while steps < 1200:
		steps += 1
		var phase: String = forest.client.phase()
		if phase == until or phase == "completed":
			break
		var adv: Dictionary = forest.client.adv
		if not hall5 and (phase == "boss_unlocked" or (int(forest.client.site_state("lf_site_07").get("step", 0)) == 0 and bool(forest.client.site_state("lf_site_07").get("available", false)))):
			hall5 = true
			await test_post("/test/hall?level=5")
			await refresh()
			continue
		var step: Dictionary = forest.guide()
		var next: Variant = adv.get("nextTask")
		var site_id := String(next.siteId) if next is Dictionary and next.get("siteId") != null else ""
		if String(step.get("panel", "")) == "mechanism":
			await solve_mechanism(site_id)
			continue
		if String(step.get("panel", "")) == "squad":
			await form_squad()
			continue
		if String(step.get("panel", "")) == "journal":
			break
		if bool(step.get("enabled", false)) and not String(step.get("action", "")).is_empty():
			var action := String(step.action)
			forest.hud.continue_button.pressed.emit()
			await frames(1)
			while forest.acting or forest.client.in_flight:
				await process_frame
			await frames(2)
			if action in ["engage_guardian", "engage_boss"]:
				var fight: Dictionary = forest.client.battle()
				if not fight.is_empty():
					await advance_to(float(fight.endsAt) + 300.0)
				game.close_modal()
			continue
		await wait_settle()
	print("ADVANCE_DONE phase=", forest.client.phase(), " rescued=", forest.client.campaign().get("rescuedCount", -1), " steps=", steps,
		" node=", forest.client.squad().get("node", ""))
	quit(0)
