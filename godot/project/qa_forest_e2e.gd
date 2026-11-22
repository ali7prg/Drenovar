extends SceneTree
## End-to-end QA of «Лес потерянных» on the V6 server line (1022): the real game scene against the
## synthetic in-memory V6 fixture with the adventure switched on (the path production uses).
## The game plays all 12 sites and the boss itself the way a player would: HUD «Продолжить» (guide),
## squad panel, mechanism UI, reward panel. The server clock is advanced through /test/clock; the
## scene is really reloaded (new main.tscn instance) at several steps to verify restored poses.
## 1022 launch order: main.tscn opens the city first; the forest game layer and its world layer load
## lazily afterwards (only because the server projects state.adventure). boot() waits for both on
## that real lazy path (no --forest-eager).
## Run:  DRENOVAR_SERVER_ROOT=<server checkout> DRENOVAR_QA_PORT=8801 DRENOVAR_QA_ADVENTURE=1 \
##         DRENOVAR_QA_CONDITIONAL=1 DRENOVAR_QA_HALL=2 node godot/tools/qa-v6-1022-server.mjs
##       godot --headless --path godot/project -s qa_forest_e2e.gd -- --server=http://127.0.0.1:8801
## (Before 1022 it ran against the old local realm, forest_rescue/server/local-realm/server.mjs.)

const ForestFlags := preload("res://src/forest_rescue/world/forest_flags.gd")

var game: Node
var forest: Node
var finished := false
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

## The V6 fixture's request log (a JSON array; test_post keeps only objects).
func fixture_requests() -> Array:
	var client := HTTPRequest.new()
	client.body_size_limit = -1
	root.add_child(client)
	client.request(game.endpoint + "/qa/requests", PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "")
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else null
	return parsed if parsed is Array else []

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

var boot_ms: Array[int] = []
var started_ms := 0
## What the run covered (printed as QA_FOREST_E2E_REPORT).
var report := {"tasks": {}, "guardian_victories": [], "cages": [], "escorts": [], "boss_phases_shown": [],
	"boss_phase_events": [], "reloads": []}

func on_adventure_events(events: Array) -> void:
	for event in events:
		if event is Dictionary and String(event.get("type", "")) == "boss_phase":
			report.boss_phase_events.append(String(event.get("phase", "")))

## One app launch: the city first, then (1022) the lazy forest game layer and its world layer.
func boot() -> void:
	var started := Time.get_ticks_msec()
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 120000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	# 1022: the game layer is created after the launch, once the server projects state.adventure.
	while game.forest_game == null and Time.get_ticks_msec() < deadline:
		await process_frame
	forest = game.forest_game
	if forest == null:
		check(false, "forest game layer loaded lazily after the launch (reload %d)" % reloads)
		finish()
		return
	check(not ForestFlags.eager(), "lazy forest path (no --forest-eager)")
	# The world layer (terrain, forest, fog, landmarks) attaches itself after the city.
	while not forest.world_ready() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(forest.world_ready(), "forest world layer attached by itself after the city (reload %d)" % reloads)
	forest.client.events_arrived.connect(on_adventure_events)
	await frames(3)
	while not forest.entered_session and Time.get_ticks_msec() < deadline:
		await process_frame
	await frames(3)
	boot_ms.append(Time.get_ticks_msec() - started)

func reload(reason: String) -> void:
	reloads += 1
	var before: Dictionary = forest.client.adv.duplicate(true)
	game.queue_free()
	await frames(2)
	await boot()
	if finished:
		return
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
	report.reloads.append(reason)
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

## The boss fight in its three phases: as the server clock passes each phase change of the server
## timeline, the server projection, the client's battle view and the battle header show that phase.
func check_boss_phases(fight: Dictionary, from_ms: float, to_ms: float) -> void:
	for event in fight.get("timeline", []):
		if String(event.get("type", "")) != "phase":
			continue
		var at := float(fight.startedAt) + float(event.t) * 1000.0
		if at < from_ms or at >= to_ms:
			continue
		var id := String(event.phase)
		await advance_to(at + 150.0)
		for i in 3:
			forest.actors.tick(0.05)
		var shown := String(forest.client.battle().get("phase", ""))
		check(shown == id and String(forest.client.adv.get("boss", {}).get("phase", "")) == id, "boss phase %s projected at %.1f s (battle %s)" % [id, float(event.t), shown])
		var header: String = forest.hud.battle_title.text if forest.hud.battle_header.visible else ""
		check(header.contains(forest.content.text("boss.phase." + id)), "battle header shows the boss phase %s: %s" % [id, header])
		report.boss_phases_shown.append(id)
		note("boss phase %s at %.1f s" % [id, float(event.t)])

func run() -> void:
	root.size = Vector2i(1366, 630)
	started_ms = Time.get_ticks_msec()
	await boot()
	if finished:
		return
	check(game.loopback, "running against the loopback realm")
	check(str(game.state.get("economy_version", "")) == "DRENOVAR-V6-C1.0", "city from the V6 fixture (production server line)")
	check(forest.client.known, "server exposes state.adventure")
	# Hall II: locked; no POIs.
	await test_post("/test/hall?level=2")
	await refresh()
	check(not forest.client.unlocked() and forest.client.adv.get("pois", []).is_empty(), "hall2 locked, no POIs")
	var refused: Dictionary = await forest.request_action("move", {"targetId":"lf_horse_origin"})
	check(not bool(refused.get("ok", true)), "locked: adventure command refused locally")
	# Real army for real battles (a 5-recruit starter squad loses to Tenerys I).
	await test_post("/test/army", {"units":{"ENG-02":30000, "ENG-03":30000, "ENG-06":30000}})
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
				if after_step == before_step + 1:
					if not report.tasks.has(site_id):
						report.tasks[site_id] = []
					report.tasks[site_id].append(task_id)
				if task_id == "unlock_cage":
					var freed := 0
					for person in forest.client.poi(site_id).get("captives", []):
						freed += 1 if String(person.get("state", "")) != "caged" else 0
					check(freed == 3, "cage opened: three captives out of the cage at " + site_id)
					report.cages.append(site_id)
				if task_id == "escort_home":
					var home := 0
					for person in forest.client.poi(site_id).get("captives", []):
						home += 1 if String(person.get("state", "")) == "home" else 0
					check(home == 3, "escort home: three captives home from " + site_id)
					report.escorts.append(site_id)
				if reload_points.get(site_id, []).has(task_id) or (task_id == "unlock_cage"):
					await reload("%s after %s" % [site_id, task_id])
			elif action == "engage_guardian" or action == "engage_boss":
				var fight: Dictionary = forest.client.battle()
				check(not fight.is_empty() and fight.has("timeline"), "battle with server timeline " + action)
				var boss_fight := action == "engage_boss"
				var mid := float(fight.startedAt) + (float(fight.endsAt) - float(fight.startedAt)) * 0.5
				if boss_fight:
					var ids: Array = (fight.get("timeline", []) as Array).filter(func(e): return String(e.get("type", "")) == "phase").map(func(e): return String(e.phase))
					check(ids == ["hunt", "fury", "last_stand"], "boss timeline: three phases in order " + str(ids))
					report.boss_timeline_phases = ids
					await check_boss_phases(fight, -INF, mid)
				if site_id == "lf_site_01" or boss_fight:
					await advance_to(mid)
					await reload("mid-battle " + action)
					for i in 3:
						forest.actors.tick(0.05)
					check(forest.hud.battle_header.visible, "battle header restored mid-battle")
				if boss_fight:
					await check_boss_phases(fight, mid, float(fight.endsAt))
					# The final boss model, loaded in the background like every forest actor.
					var wait_until := Time.get_ticks_msec() + 30000
					while (forest.actors.rigs.get("boss") == null or forest.actors.rigs.boss.model == null) and Time.get_ticks_msec() < wait_until:
						await process_frame
					var boss_rig: Node = forest.actors.rigs.get("boss")
					check(boss_rig != null and boss_rig.model != null, "boss drawn with its model during the fight")
					report.boss_model = String(boss_rig.asset_path) if boss_rig != null and boss_rig.model != null else ""
				await advance_to(float(fight.endsAt) + 300.0)
				var result: Dictionary = forest.client.battle()
				check(String(result.get("outcome", "")) == "victory", "battle victory " + action + " " + String(result.get("outcome", "")))
				if action == "engage_guardian" and String(result.get("outcome", "")) == "victory":
					report.guardian_victories.append("%s:%s" % [site_id, String(fight.get("species", ""))])
				if boss_fight:
					report.boss_outcome = String(result.get("outcome", ""))
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
	# Coverage of the whole adventure in this one run (the real client, the V6 code).
	var all_tasks := 0
	for site_id in report.tasks:
		all_tasks += (report.tasks[site_id] as Array).size()
	var five := (forest.client.campaign().get("sites", []) as Array).all(func(e): return int(e.get("step", 0)) == 5)
	check(report.tasks.size() == 12 and all_tasks == 60 and five, "all 12 sites, every task (%d sites, %d tasks)" % [report.tasks.size(), all_tasks])
	check(report.guardian_victories.size() == 12, "12 guardian battles won: %d" % report.guardian_victories.size())
	check(report.cages.size() == 12 and report.escorts.size() == 12, "12 cages opened, 12 escorts home: %d / %d" % [report.cages.size(), report.escorts.size()])
	check(report.boss_phases_shown == ["hunt", "fury", "last_stand"], "boss shown in its three phases: " + str(report.boss_phases_shown))
	check(report.boss_phase_events.has("fury") and report.boss_phase_events.has("last_stand"), "boss phase changes announced to the client: " + str(report.boss_phase_events))
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
	report.reward = {"earned": escrow.earned.duplicate(), "claimed": escrow.claimed.duplicate(), "pending": escrow.pending.duplicate()}
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
	# The whole campaign on the V6 stack: every adventure command of every launch, as the fixture logged it.
	var fixture_log: Array = await fixture_requests()
	var commands: Array = fixture_log.filter(func(r): return str(r.get("kind", "")) in ["adventure", "adventure_intro"])
	var statuses := {}
	for r in commands:
		statuses[str(int(r.get("status", 0)))] = int(statuses.get(str(int(r.get("status", 0))), 0)) + 1
	report.adventure_commands = commands.size()
	report.adventure_command_statuses = statuses
	check(commands.size() > 100 and commands.all(func(r): return str(r.get("economy", "")) == "DRENOVAR-V6-C1.0"), "all %d adventure commands on the V6 stack (economy header)" % commands.size())
	check(commands.all(func(r): return int(r.get("status", 0)) == 200 or int(r.get("status", 0)) == 201), "every adventure command answered 200: " + str(statuses))
	for entry in forest.client.sent_log:
		check(String(entry.body.get("requestId", "")) == String(entry.key), "requestId equals Idempotency-Key")
		for forbidden in ["success", "reward", "rewards", "wallet", "capacity", "ownerId", "playerId", "time", "position", "revision", "proof"]:
			check(not entry.body.has(forbidden), "client never sends " + forbidden)
	finish()

func finish() -> void:
	if finished:
		return
	finished = true
	var commands: int = forest.client.sent_log.size() if is_instance_valid(forest) else 0
	report.boot_ms = {"count": boot_ms.size(), "min": boot_ms.min() if not boot_ms.is_empty() else 0, "max": boot_ms.max() if not boot_ms.is_empty() else 0}
	report.run_s = snappedf((Time.get_ticks_msec() - started_ms) / 1000.0, 0.1)
	print("QA_FOREST_E2E_REPORT ", JSON.stringify(report))
	print("QA_FOREST_E2E steps=", steps, " reloads=", reloads, " commands=", commands, " checks=", checks, " failures=", failures.size())
	for failure in failures:
		print("  FAIL ", failure)
	var code := 0 if failures.is_empty() else 1
	if is_instance_valid(game):
		game.queue_free()
		await frames(3)
	quit(code)
