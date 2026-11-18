extends SceneTree
## End-to-end QA of «Лес потерянных» against the local realm (forest_rescue/server/local-realm).
## The game plays itself the way a player would: HUD «Продолжить» (guide), squad panel,
## mechanism UI, reward panel. The server clock is advanced through /test/clock; the scene
## is really reloaded (new main.tscn instance) at several steps to verify restored poses.
## Run:  node forest_rescue/server/local-realm/server.mjs   (fresh DRENOVAR_FR_DB)
##       godot --headless --path godot/project -s qa_forest_e2e.gd -- --server=http://127.0.0.1:8418

var game: Node
var forest: Node
var checks := 0
var failures: Array[String] = []
var reloads := 0
var steps := 0
var log_lines: PackedStringArray = []

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_FOREST_E2E: " + detail)

func note(value: String) -> void:
	log_lines.append(value)
	print("E2E ", value)

func _initialize() -> void:
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func test_post(path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	var headers := PackedStringArray(["Content-Type: application/json"])
	client.request(game.endpoint + path, headers, HTTPClient.METHOD_POST, "" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else {}
	return parsed if parsed is Dictionary else {"httpStatus":result[1]}

func refresh() -> void:
	while game.busy:
		await process_frame
	var response: Dictionary = await game.request("state")
	if response.has("city"):
		game.accept(response)
	await frames(2)

func advance_to(server_ms: float) -> void:
	var now := float(forest.client.adv.get("serverTime", 0))
	var target := maxf(server_ms, now + 50.0)
	await test_post("/test/clock?time=%d" % int(ceil(target)))
	await refresh()

func boot() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 60000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	forest = game.forest_game
	await frames(3)
	while not forest.entered_session and Time.get_ticks_msec() < deadline:
		await process_frame
	await frames(3)

func reload(reason: String) -> void:
	reloads += 1
	var before: Dictionary = forest.client.adv.duplicate(true)
	game.queue_free()
	await frames(2)
	await boot()
	var after: Dictionary = forest.client.adv
	check(forest.client.available(), "adventure after reload " + reason)
	check(forest.actors.choreo.is_empty(), "no replayed choreography after reload " + reason)
	check(int(after.get("campaign", {}).get("rescuedCount", -1)) == int(before.get("campaign", {}).get("rescuedCount", -2)), "rescued count kept " + reason)
	for entry in before.get("campaign", {}).get("sites", []):
		var now_entry: Dictionary = forest.client.site_state(String(entry.id))
		check(int(now_entry.get("step", -1)) == int(entry.get("step", 0)), "site step kept " + String(entry.id) + " " + reason)
	for i in 4:
		forest.actors.tick(0.05)
	for poi in after.get("pois", []):
		if String(poi.get("kind", "")) != "site":
			continue
		var site_id := String(poi.id)
		for person in poi.get("captives", []):
			var has_rig: bool = forest.actors.rigs.has(String(person.id))
			if String(person.get("state", "")) == "home":
				check(not has_rig, "home captive absent after reload " + String(person.id))
		if String(poi.get("guardian", {}).get("state", "")) == "defeated":
			check(not forest.actors.rigs.has("guardian_" + site_id), "defeated guardian removed after reload " + site_id)
	note("reload %d (%s) ok" % [reloads, reason])

func form_squad_from_panel() -> void:
	forest.panels.open_squad()
	await frames(1)
	for spin: SpinBox in game.modal_body.find_children("Squad_*", "SpinBox", true, false):
		spin.value = spin.max_value
	var submit: Button = game.modal_body.find_child("SquadSubmit", true, false)
	check(submit != null and not submit.disabled, "squad submit available")
	if submit != null:
		submit.pressed.emit()
	while forest.acting or forest.client.in_flight:
		await process_frame
	await frames(2)
	check(forest.total_units(forest.client.squad().get("units", {})) > 0, "squad formed from the panel")

func wait_settle() -> void:
	var settle: float = forest.client.last_settle_ms()
	if settle == INF:
		await refresh()
	else:
		await advance_to(settle + 300.0)

func solve_mechanism(site_id: String) -> void:
	var site: Dictionary = forest.content.site(site_id)
	var solution: Array = site.artifact.puzzle.solution
	var kind := String(site.variation)
	forest.mech.open(site_id)
	await frames(1)
	check(forest.mech.is_open() and forest.mech.kind == kind, "mechanism UI open " + site_id)
	if kind == "rune_lock" or kind == "winch_sequence":
		# One wrong input first: only the attempt resets (no damage, no loss).
		await forest.mech.send_symbol(String(solution[1]))
		await frames(2)
		var reset_ok: bool = int(forest.mech.mechanism().get("progress", -1)) == 0 and forest.mech.feedback.text == forest.content.text("mechanism.wrong")
		check(reset_ok, "wrong input resets the attempt " + site_id)
	if kind == "paired_latch":
		await forest.mech.occupy()
		await wait_settle()
		check(forest.mech.plates_state() == "held", "plates held " + site_id)
	for symbol in solution:
		var before := int(forest.mech.mechanism().get("progress", 0))
		await forest.mech.send_symbol(String(symbol))
		var guard := 0
		while int(forest.mech.mechanism().get("progress", 0)) <= before and not bool(forest.mech.mechanism().get("solved", false)) and guard < 12:
			guard += 1
			await wait_settle()
			await frames(4)
			while forest.mech.sending or forest.client.in_flight:
				await process_frame
	check(bool(forest.mech.mechanism().get("solved", false)), "mechanism solved through the UI " + site_id)
	forest.mech.close()

func run() -> void:
	root.size = Vector2i(1366, 630)
	await boot()
	check(game.loopback, "running against the loopback realm")
	check(forest.client.known, "server exposes state.adventure")
	# Hall II: locked; no POIs.
	await test_post("/test/hall?level=2")
	await refresh()
	check(not forest.client.unlocked() and forest.client.adv.get("pois", []).is_empty(), "hall2 locked, no POIs")
	var refused: Dictionary = await forest.request_action("move", {"targetId":"lf_horse_origin"})
	check(not bool(refused.get("ok", true)), "locked: adventure command refused locally")
	# Real army for real battles (a 5-recruit starter squad loses to Tenerys I).
	await test_post("/test/army", {"units":{"ENG-02":30000, "ENG-03":30000, "ENG-07":30000}})
	# Hall III: intro offered once; presentation starts by itself in the safe city view.
	await test_post("/test/hall?level=3")
	await refresh()
	check(forest.client.unlocked(), "hall3 unlocked")
	var deadline := Time.get_ticks_msec() + 8000
	while forest.intro.mode != "animated" and Time.get_ticks_msec() < deadline:
		await process_frame
	check(forest.intro.mode == "animated", "intro presented once")
	check(String(forest.client.adv.intro.status) == "playing", "server intro playing")
	await reload("intro interrupted")
	check(String(forest.client.adv.intro.status) == "pending" and bool(forest.client.adv.intro.deferred), "interrupted intro → deferred invitation")
	await frames(5)
	check(not forest.intro.presenting() and forest.hud.invite_button.visible, "no auto-replay; invitation button")
	forest.hud.invite_button.pressed.emit()
	deadline = Time.get_ticks_msec() + 8000
	while forest.intro.mode != "animated" and Time.get_ticks_msec() < deadline:
		await process_frame
	check(forest.intro.mode == "animated", "invitation restarts the intro")
	forest.intro.on_follow()
	deadline = Time.get_ticks_msec() + 8000
	while (String(forest.client.adv.intro.status) != "acknowledged" or forest.acting or forest.client.in_flight) and Time.get_ticks_msec() < deadline:
		await process_frame
	await frames(3)
	if String(forest.client.adv.intro.status) != "acknowledged":
		note("intro debug status=%s last=%s sent=%s" % [str(forest.client.adv.intro), str(forest.client.last_result), str(forest.client.sent_log.map(func(e): return [e.body, e.attempt]))])
	check(String(forest.client.adv.intro.status) == "acknowledged", "intro acknowledged after follow")
	check(game.modal.visible, "follow opens the player's own choice (squad panel)")
	game.close_modal()
	var escrow_before: Dictionary = forest.client.adv.escrow.earned.duplicate()
	var zero_intro := true
	for key in escrow_before:
		zero_intro = zero_intro and int(escrow_before[key]) == 0
	check(zero_intro, "intro awarded nothing")
	await form_squad_from_panel()
	var hall5 := false
	var reload_points := {"lf_site_01":["discover", "recover_artifact", "defeat_guardian", "unlock_cage", "escort_home"]}
	var last_signature := ""
	var stuck := 0
	while steps < 900:
		steps += 1
		var adv: Dictionary = forest.client.adv
		var phase: String = forest.client.phase()
		if phase == "completed":
			break
		if not hall5 and (phase in ["boss_unlocked"] or int(forest.client.site_state("lf_site_07").get("step", 0)) == 0 and bool(forest.client.site_state("lf_site_07").get("available", false))):
			hall5 = true
			await test_post("/test/hall?level=5")
			await refresh()
			continue
		var step: Dictionary = forest.guide()
		var signature := JSON.stringify([step.get("action", ""), step.get("fields", {}), step.get("panel", ""), adv.get("revision", 0), forest.client.squad().get("move") != null])
		stuck = stuck + 1 if signature == last_signature else 0
		last_signature = signature
		if stuck > 6:
			check(false, "guide stuck at " + signature + " hint=" + String(step.get("hint", "")))
			break
		var next: Variant = adv.get("nextTask")
		var site_id := String(next.siteId) if next is Dictionary and next.get("siteId") != null else ""
		var task_id := String(next.taskId) if next is Dictionary and next.get("taskId") != null else ""
		if String(step.get("panel", "")) == "mechanism":
			await solve_mechanism(site_id)
			continue
		if String(step.get("panel", "")) == "squad":
			await form_squad_from_panel()
			continue
		if bool(step.get("enabled", false)) and not String(step.get("action", "")).is_empty():
			var action := String(step.action)
			var before_step := int(forest.client.site_state(site_id).get("step", 0))
			forest.hud.continue_button.pressed.emit()
			await frames(1)
			while forest.acting or forest.client.in_flight:
				await process_frame
			await frames(2)
			if action == "attempt_task":
				var after_step := int(forest.client.site_state(site_id).get("step", 0))
				check(after_step == before_step + 1, "task %s/%s completed" % [site_id, task_id])
				note("%s %s → step %d" % [site_id, task_id, after_step])
				if reload_points.get(site_id, []).has(task_id) or (task_id == "unlock_cage"):
					await reload("%s after %s" % [site_id, task_id])
			elif action == "engage_guardian" or action == "engage_boss":
				var fight: Dictionary = forest.client.battle()
				check(not fight.is_empty() and fight.has("timeline"), "battle with server timeline " + action)
				if site_id == "lf_site_01" or action == "engage_boss":
					await advance_to(float(fight.startedAt) + (float(fight.endsAt) - float(fight.startedAt)) * 0.5)
					await reload("mid-battle " + action)
					for i in 3:
						forest.actors.tick(0.05)
					check(forest.hud.battle_header.visible, "battle header restored mid-battle")
				await advance_to(float(fight.endsAt) + 300.0)
				var result: Dictionary = forest.client.battle()
				check(String(result.get("outcome", "")) == "victory", "battle victory " + action + " " + String(result.get("outcome", "")))
				game.close_modal()
			elif action == "escort_start":
				var walk: Dictionary = forest.client.escort()
				check(String(walk.get("state", "")) == "walking" and (walk.get("captiveIds", []) as Array).size() == 3, "escort of exactly three")
				if site_id == "lf_site_01":
					await advance_to(float(walk.move.departAt) + (float(walk.move.arriveAt) - float(walk.move.departAt)) * 0.5)
					await reload("escort walking")
			continue
		await wait_settle()
	check(forest.client.phase() == "completed", "campaign completed: " + forest.client.phase())
	check(int(forest.client.campaign().get("rescuedCount", 0)) == 36, "36 rescued")
	var boss_state := String(forest.client.adv.get("boss", {}).get("state", ""))
	check(boss_state == "defeated", "boss defeated")
	await reload("completed")
	# Rewards: earned = claimed + pending; claim through the panel (warehouse fills, rest kept).
	forest.panels.open_rewards()
	await frames(1)
	var claim: Button = game.modal_body.find_child("ClaimRewards", true, false)
	check(claim != null and not claim.disabled, "claim button enabled")
	var pending_before: Dictionary = forest.client.adv.escrow.pending.duplicate()
	if claim != null:
		claim.pressed.emit()
		await frames(1)
		while forest.acting or forest.client.in_flight:
			await process_frame
		await frames(2)
	var escrow: Dictionary = forest.client.adv.escrow
	for key in ["food", "wood", "stone", "iron", "coins"]:
		check(int(escrow.earned[key]) == int(escrow.claimed[key]) + int(escrow.pending[key]), "earned = claimed + pending " + key)
		check(int(escrow.pending[key]) <= int(pending_before[key]), "pending did not grow " + key)
	check(int(escrow.earned.food) == 2325000 and int(escrow.earned.coins) == 190000, "campaign totals food/coins")
	var toggle: CheckButton = game.modal_body.find_child("AutoRefill", true, false) if game.modal.visible else null
	if toggle == null:
		forest.panels.open_rewards()
		await frames(1)
		toggle = game.modal_body.find_child("AutoRefill", true, false)
	check(toggle != null, "auto-refill toggle")
	if toggle != null:
		toggle.button_pressed = true
		await frames(1)
		while forest.acting or forest.client.in_flight:
			await process_frame
		await frames(2)
		check(bool(forest.client.adv.get("autoRefill", false)), "auto-refill opt-in stored by server")
	for entry in forest.client.sent_log:
		check(String(entry.body.get("requestId", "")) == String(entry.key), "requestId equals Idempotency-Key")
		for forbidden in ["success", "reward", "rewards", "wallet", "capacity", "ownerId", "playerId", "time", "position", "revision", "proof"]:
			check(not entry.body.has(forbidden), "client never sends " + forbidden)
	print("QA_FOREST_E2E steps=", steps, " reloads=", reloads, " commands=", forest.client.sent_log.size(), " checks=", checks, " failures=", failures.size())
	for failure in failures:
		print("  FAIL ", failure)
	quit(0 if failures.is_empty() else 1)
