extends SceneTree
## «Лес потерянных» on the V6 server line (1022): the real game scene against the synthetic in-memory
## V6 fixture with the adventure switched on (DRENOVAR_V6_ADVENTURE=true for the fixture only):
##   DRENOVAR_SERVER_ROOT=<server checkout> DRENOVAR_QA_PORT=8800 DRENOVAR_QA_ADVENTURE=1 \
##     DRENOVAR_QA_CONDITIONAL=1 node godot/tools/qa-v6-1022-server.mjs
##   godot --headless --path godot/project -s qa_forest_v6.gd -- --server=http://127.0.0.1:8800
## The game plays the first site the way a player would (HUD «Продолжить», squad panel, mechanism UI):
## entering the forest (intro), one task, one guardian battle and one cage rescue. One network
## stack: every adventure command goes through main.request() with requestId == Idempotency-Key.
## Optional: -- --shots=<dir> saves in-game stills (city, forest on).

var game: Node
var forest: Node
var checks := 0
var failures: Array[String] = []
var steps := 0
var shots_dir := ""
var report := {"tasks": [], "battles": [], "cages": []}
const ActorRig := preload("res://src/forest_rescue/game/actor_rig.gd")
var peak_actor_loads := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_FOREST_V6: " + detail)

func note(value: String) -> void:
	print("FOREST_V6 ", value)

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots_dir = arg.trim_prefix("--shots=")
	call_deferred("run")

## Threaded actor loads in flight, sampled every frame: the rendered game deadlocked with four
## creatures v2 guardians loading at once (1022 gate: one at a time).
func _process(_delta: float) -> bool:
	peak_actor_loads = maxi(peak_actor_loads, ActorRig.loading.size())
	return false

func frames(count: int) -> void:
	for i in count:
		await process_frame

func test_post(path: String, body: Variant = null) -> Variant:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST,
		"" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else null

func refresh() -> void:
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

func shot(name: String) -> void:
	if shots_dir.is_empty() or DisplayServer.get_name() == "headless":
		return
	await frames(8)
	DirAccess.make_dir_recursive_absolute(shots_dir)
	root.get_texture().get_image().save_png(shots_dir.path_join(name + ".png"))
	note("shot " + name)

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

func solve_mechanism(site_id: String) -> void:
	var site: Dictionary = forest.content.site(site_id)
	var solution: Array = site.artifact.puzzle.solution
	forest.mech.open(site_id)
	await frames(1)
	check(forest.mech.is_open(), "mechanism UI open " + site_id)
	if String(site.variation) == "paired_latch":
		await forest.mech.occupy()
		await wait_settle()
	for symbol in solution:
		var before := int(forest.mech.mechanism().get("progress", 0))
		await forest.mech.send_symbol(String(symbol))
		var guard := 0
		while int(forest.mech.mechanism().get("progress", 0)) <= before and not bool(forest.mech.mechanism().get("solved", false)) and guard < 12:
			guard += 1
			await wait_settle()
		await frames(1)
	check(bool(forest.mech.mechanism().get("solved", false)), "mechanism solved " + site_id)
	forest.mech.close()
	await frames(1)

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	forest = game.forest_game
	await frames(3)
	check(game.loopback and str(game.state.get("economy_version", "")) == "DRENOVAR-V6-C1.0", "city from the V6 fixture")
	check(forest.client.known, "the V6 server projects state.adventure")
	# Hall II: the forest stays locked.
	await test_post("/test/hall?level=2")
	await refresh()
	check(not forest.client.unlocked(), "town hall II: forest locked")
	await test_post("/test/army", {"units": {"ENG-02": 30000, "ENG-03": 30000, "ENG-06": 30000}})
	await test_post("/test/hall?level=3")
	await refresh()
	check(forest.client.unlocked(), "town hall III: forest unlocked")
	await shot("forest_on_unlocked")
	# Entering the forest: the intro plays once, «follow» acknowledges it.
	deadline = Time.get_ticks_msec() + 10000
	while forest.intro.mode != "animated" and Time.get_ticks_msec() < deadline:
		await process_frame
	check(forest.intro.mode == "animated", "intro presented")
	forest.intro.on_follow()
	deadline = Time.get_ticks_msec() + 10000
	while (String(forest.client.adv.get("intro", {}).get("status", "")) != "acknowledged" or forest.acting or forest.client.in_flight) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(String(forest.client.adv.get("intro", {}).get("status", "")) == "acknowledged", "entered the forest (intro acknowledged)")
	if game.modal.visible:
		game.close_modal()
	await form_squad_from_panel()
	var done_task := false
	var done_battle := false
	var done_cage := false
	var last_signature := ""
	var stuck := 0
	while steps < 200 and not (done_task and done_battle and done_cage):
		steps += 1
		var adv: Dictionary = forest.client.adv
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
				note("%s %s -> step %d" % [site_id, task_id, after_step])
				report.tasks.append("%s/%s" % [site_id, task_id])
				done_task = true
				if task_id == "unlock_cage":
					var site_poi: Dictionary = {}
					for poi in forest.client.adv.get("pois", []):
						if String(poi.get("id", "")) == site_id:
							site_poi = poi
					var freed: Array = site_poi.get("captives", []).filter(func(p): return String(p.get("state", "")) != "caged")
					check(not freed.is_empty(), "cage rescue: captives out of the cage (%d)" % freed.size())
					report.cages.append({"site": site_id, "freed": freed.size()})
					done_cage = not freed.is_empty()
					await shot("forest_on_cage_open")
			elif action == "engage_guardian":
				var fight: Dictionary = forest.client.battle()
				check(not fight.is_empty() and fight.has("timeline"), "guardian battle with a server timeline")
				var guardian: Node = forest.actors.rigs.get("guardian_" + site_id)
				var v2: bool = guardian != null and guardian.model != null and guardian.creature_species != ""
				check(v2, "guardian drawn with the creatures v2 model")
				await advance_to(float(fight.startedAt) + (float(fight.endsAt) - float(fight.startedAt)) * 0.5)
				for i in 4:
					forest.actors.tick(0.05)
				await shot("forest_on_guardian_battle")
				await advance_to(float(fight.endsAt) + 300.0)
				var result: Dictionary = forest.client.battle()
				check(String(result.get("outcome", "")) == "victory", "guardian battle victory: " + String(result.get("outcome", "")))
				report.battles.append({"site": site_id, "species": String(fight.get("species", "")), "outcome": String(result.get("outcome", "")),
					"events": (fight.get("timeline", []) as Array).size(), "guardian_model": String(guardian.asset_path) if guardian != null else ""})
				done_battle = String(result.get("outcome", "")) == "victory"
				game.close_modal()
			continue
		await wait_settle()
	check(done_task and done_battle and done_cage, "first site: task, guardian battle and cage rescue (%s %s %s)" % [done_task, done_battle, done_cage])
	for entry in forest.client.sent_log:
		check(String(entry.body.get("requestId", "")) == String(entry.key), "requestId equals Idempotency-Key")
	var log_value: Variant = await test_post("/qa/requests")
	var log: Array = log_value if log_value is Array else []
	var commands: Array = log.filter(func(r): return str(r.get("kind", "")) in ["adventure", "adventure_intro"])
	check(not commands.is_empty() and commands.all(func(r): return str(r.get("economy", "")) == "DRENOVAR-V6-C1.0"), "adventure commands on the V6 stack (economy header)")
	report.commands = commands.size()
	report.statuses = commands.map(func(r): return int(r.status))
	report.steps = steps
	report.peak_actor_loads = peak_actor_loads
	check(peak_actor_loads <= ActorRig.MAX_PARALLEL_LOADS, "actor models load one at a time (peak %d)" % peak_actor_loads)
	print("QA_FOREST_V6_REPORT ", JSON.stringify(report))
	print("QA_FOREST_V6 steps=%d commands=%d checks=%d failures=%d" % [steps, forest.client.sent_log.size(), checks, failures.size()])
	for failure in failures:
		print("  FAIL ", failure)
	quit(0 if failures.is_empty() else 1)
