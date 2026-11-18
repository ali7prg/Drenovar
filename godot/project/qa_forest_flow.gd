extends SceneTree
## Headless QA of the «Лес потерянных» gameplay layer against CONTRACT §3 fixtures recorded
## from the local realm (res://data/forest_rescue/game/fixtures). Uses a stub transport so
## command bodies, Idempotency-Key reuse on uncertain retries and event dedup are checked
## without a server. Run: godot --headless --path godot/project -s qa_forest_flow.gd

const FIXTURES := "res://data/forest_rescue/game/fixtures/"
const ALLOWED := {
	"adventure_intro":["kind", "campaignId", "action", "requestId", "attempt", "reducedMotion"],
	"form_squad":["kind", "campaignId", "action", "units"], "move":["kind", "campaignId", "action", "targetId"],
	"stop":["kind", "campaignId", "action"], "discover_horse":["kind", "campaignId", "action"],
	"attempt_task":["kind", "campaignId", "action", "siteId", "taskId"], "mechanism_input":["kind", "campaignId", "action", "siteId", "symbol"],
	"occupy_plates":["kind", "campaignId", "action", "siteId"], "engage_guardian":["kind", "campaignId", "action", "siteId"],
	"retreat":["kind", "campaignId", "action"], "escort_start":["kind", "campaignId", "action", "siteId"],
	"begin_boss":["kind", "campaignId", "action"], "engage_boss":["kind", "campaignId", "action"], "finish_boss":["kind", "campaignId", "action"],
	"claim_rewards":["kind", "campaignId", "action"], "set_auto_refill":["kind", "campaignId", "action", "enabled"],
	"pause":["kind", "campaignId", "action"], "resume":["kind", "campaignId", "action"]
}

class StubHost extends Node:
	var main: Node
	var busy := false
	var replies: Array = []
	var requests: Array = []
	func request(path: String, payload: Variant = null, key := "") -> Dictionary:
		requests.append({"path":path, "body":payload.duplicate(true) if payload is Dictionary else payload, "key":key})
		if replies.is_empty():
			return {"error":"Сервер недоступен"}
		var reply: Variant = replies.pop_front()
		return reply
	func accept(response: Dictionary) -> void:
		main.accept(response)
	func poll_account_state() -> void:
		pass

var checks := 0
var failures: Array[String] = []
var game: Node
var forest: Node
var stub: StubHost

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_FOREST_FLOW: " + detail)

func fixture(name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))
	check(parsed is Dictionary, "fixture " + name)
	return parsed if parsed is Dictionary else {}

func labels_text(node: Node) -> String:
	var parts: PackedStringArray = []
	for label: Label in node.find_children("*", "Label", true, false):
		if label.is_visible_in_tree():
			parts.append(label.text)
	for button: Button in node.find_children("*", "Button", true, false):
		if button.is_visible_in_tree():
			parts.append(button.text)
	return "\n".join(parts)

func frames(count: int) -> void:
	for i in count:
		await process_frame

func reset_actors() -> void:
	forest.actors.on_stage_changed()
	forest.actors.first_state = true
	forest.client.adv = {}
	forest.client.primed = false

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	forest = game.forest_game
	var content = forest.content
	check(content.loaded, "authored content loaded: " + str(content.missing))
	# Delivered JSON copies are byte-identical to forest_rescue/delivery/data.
	var sums := FileAccess.get_file_as_string("res://data/forest_rescue/game/SOURCE_SHA256SUMS.txt")
	for line in sums.split("\n", false):
		var parts := line.split("  ")
		var actual := FileAccess.get_sha256("res://data/forest_rescue/game/" + parts[1])
		check(actual == parts[0], "content copy hash " + parts[1])
	stub = StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub

	# 1. Server without adventure (offline demo state): locked fog text, no commands.
	game.accept(game.data.demo.duplicate(true))
	await frames(2)
	check(not forest.client.available(), "demo state has no adventure")
	check(not forest.hud.bar.visible, "bar hidden without adventure")
	var outside: Vector2 = game.stage.camera.unproject_position(Vector3(-40, 6, -95))
	check(forest.pick(outside), "tap outside the wall consumed")
	check(forest.hud.locked_card.visible and forest.hud.locked_body.text == "Приключение недоступно на этом сервере", "unavailable card text")
	var sent: Dictionary = await forest.request_action("move", {"targetId":"lf_site_01"})
	check(not bool(sent.get("ok", true)) and stub.requests.is_empty(), "no adventure commands without server support")
	forest.hud.hide_locked()

	# 2. Hall II: locked card by camera dwell, «К ратуше» opens the hall panel, nothing spent/sent.
	game.accept(fixture("locked_hall2"))
	await frames(2)
	check(forest.client.available() and not forest.client.unlocked(), "hall2 locked")
	game.stage.target = Vector3(-30, 0, -85)
	game.stage.update_camera(0, true)
	forest.hud.locked_dismissed = false
	forest.locked_shown_for_excursion = false
	await frames(2)
	await create_timer(0.35).timeout
	await frames(2)
	check(forest.hud.locked_card.visible, "dwell over forest shows locked card")
	check(forest.hud.locked_title.text == content.text("forest.locked.title"), "locked title from ui.ru.json")
	check(forest.hud.locked_body.text == content.text("forest.locked.body"), "locked body from ui.ru.json")
	check(forest.hud.locked_progress.text == "Ратуша: уровень 2 из 3", "locked progress n/3: " + forest.hud.locked_progress.text)
	check(forest.hud.locked_cta.text == "К ратуше", "locked CTA")
	check(forest.actors.markers.is_empty() and not forest.hud.bar.visible, "no POI markers/horse/HUD while locked")
	var food_before: int = game.balance("food")
	forest.hud.locked_cta.pressed.emit()
	await frames(1)
	check(game.modal.visible and game.modal_title.text == game.building_title("ECO-05"), "К ратуше opens existing town hall panel: " + game.modal_title.text)
	check(stub.requests.is_empty() and game.balance("food") == food_before, "К ратуше spends/sends nothing")
	game.close_modal()
	game.stage.target = Vector3(5, 0, -4)
	game.stage.update_camera(0, true)
	await frames(2)
	check(not forest.hud.locked_card.visible, "card hides when camera returns to town")

	# 3. Intro offer: deferred while a modal is open, then start_intro once when safe.
	game.show_economy("food")
	stub.replies = [fixture("intro_playing").merged({"events":[{"type":"intro_present", "seq":9001, "revision":1}]})]
	game.accept(fixture("intro_offer"))
	await frames(3)
	check(stub.requests.is_empty(), "intro deferred while modal open")
	game.close_modal()
	await frames(4)
	check(stub.requests.size() == 1, "start_intro sent once when safe")
	if stub.requests.size() >= 1:
		var body: Dictionary = stub.requests[0].body
		check(body == {"kind":"adventure_intro", "campaignId":"forest_rescue_v1", "action":"start_intro", "requestId":stub.requests[0].key}, "start_intro exact body " + str(body))
		check(not String(stub.requests[0].key).is_empty(), "Idempotency-Key present")
	await frames(2)
	check(forest.intro.presenting() and forest.intro.mode == "animated", "presentation started")
	check(forest.hud.banner.visible and forest.hud.banner_title.text == "Лес потерянных открыт", "banner text")
	check(forest.intro.skip_button.is_visible_in_tree(), "skip available immediately")
	var home_target: Vector3 = game.stage.target
	for i in 260:
		forest.intro.tick(0.05)
	check(forest.intro.card_text.text == content.text("intro.line3"), "final explanation line")
	check(forest.intro.follow_button.is_visible_in_tree() and forest.intro.follow_button.text == "Следовать за лошадью", "follow button")
	check(forest.intro.later_button.is_visible_in_tree() and forest.intro.later_button.text == "Позже", "later button")
	check(game.stage.target.distance_to(home_target) < 0.5, "camera returned after 12 s")
	stub.replies = [fixture("prologue")]
	forest.intro.skip_button.pressed.emit()
	await frames(3)
	check(stub.requests.size() == 2 and stub.requests[1].body.action == "skip_intro", "skip sends skip_intro")
	check(not forest.intro.presenting(), "presentation closed")
	# Reduced motion: static card, no camera motion; local replay sends nothing.
	forest.reduced_motion = true
	var before_target: Vector3 = game.stage.target
	forest.intro.replay()
	await frames(2)
	check(forest.intro.static_card.visible and forest.intro.mode == "static", "reduced motion static card")
	check(game.stage.target == before_target, "no forced camera motion with reduced motion")
	check(labels_text(forest.intro.static_card).contains(content.text("intro.line2")), "static card text from JSON")
	forest.intro.on_skip()
	await frames(2)
	check(stub.requests.size() == 2, "replay sends no intro command")
	forest.reduced_motion = false

	# 4. Adventure HUD per art/07 with authored strings.
	reset_actors()
	game.accept(fixture("site01_trail_1of3"))
	await frames(3)
	check(forest.hud.bar.visible, "adventure bar visible when unlocked")
	var task_title: String = content.task("lf_site_01", "recover_artifact").title
	check(forest.hud.task_title.text == task_title, "task card title from campaign.json: " + forest.hud.task_title.text)
	check(forest.hud.task_count.text == "1 / 3", "progress n/3: " + forest.hud.task_count.text)
	check(forest.hud.reward_amounts.wood.text == "+20 000" and forest.hud.reward_amounts.coins.text == "+1 400", "reward strip amounts (escort_home of site 1)")
	check(forest.hud.route_button.find_child("Caption", true, false).text == "Маршрут", "route caption")
	check(forest.hud.squad_button.find_child("Caption", true, false).text == "Отряд", "squad caption")
	check(forest.hud.continue_caption.text == "Продолжить", "continue caption")
	check(forest.hud.hint_label.text.contains(content.site("lf_site_01").artifact.puzzle.clue), "hint shows the authored clue")
	check(not forest.hud.bar.get_global_rect().intersects(game.nav_buttons.world.get_parent().get_global_rect()), "bar does not overlap navigation")

	# 5. Event dedup by seq/revision; first state after load replays nothing.
	var replay_events: Array = []
	var catcher := func(list): replay_events.append_array(list)
	forest.client.events_arrived.connect(catcher)
	var later := fixture("site01_trail_1of3")
	later.adventure = later.adventure.duplicate(true)
	later.adventure.recentEvents.append({"type":"mechanism_progress", "siteId":"lf_site_01", "ok":true, "seq":99999, "revision":999})
	game.accept(later)
	game.accept(later)
	check(replay_events.size() == 1, "new recent event presented exactly once: " + str(replay_events.size()))
	check(forest.client.dedupe([{"type":"task_completed", "siteId":"x", "seq":5, "revision":3}]).size() == 1, "fresh event passes")
	check(forest.client.dedupe([{"type":"task_completed", "siteId":"x", "seq":5, "revision":3}]).is_empty(), "duplicate event dropped")
	forest.client.events_arrived.disconnect(catcher)

	# 6. Idempotency: uncertain transport failure → retry with SAME key and SAME body.
	stub.requests.clear()
	stub.replies = [{"error":"Сервер недоступен"}, {"error":"CAS_CONFLICT_RETRY", "message":"", "httpStatus":409}, fixture("site01_trail_1of3")]
	var retried: Dictionary = await forest.request_action("mechanism_input", {"siteId":"lf_site_01", "symbol":"white_moss"})
	check(bool(retried.get("ok", false)), "retried command succeeds")
	check(stub.requests.size() == 3, "three transport attempts")
	if stub.requests.size() == 3:
		check(stub.requests[0].key == stub.requests[1].key and stub.requests[1].key == stub.requests[2].key, "same Idempotency-Key on retry")
		check(stub.requests[0].body == stub.requests[2].body, "same body on retry")
	stub.requests.clear()
	stub.replies = [{"error":"IDEMPOTENCY_BODY_MISMATCH", "message":"Этот ключ уже использован.", "httpStatus":409}]
	var refused: Dictionary = await forest.request_action("claim_rewards")
	check(stub.requests.size() == 1 and String(refused.get("error", "")) == "IDEMPOTENCY_BODY_MISMATCH", "definitive 4xx not retried")
	check(String(refused.get("message", "")) == "Этот ключ уже использован.", "server Russian message shown")

	# 7. Reload restores stable poses from state (no replayed choreography).
	reset_actors()
	game.accept(fixture("site01_cage_open"))
	for i in 3:
		forest.actors.tick(0.05)
	check(forest.actors.choreo.is_empty(), "no choreography replay after reload")
	var poi: Dictionary = forest.client.poi("lf_site_01")
	check(poi.cagePose == "open" and poi.artifact.state == "in_socket", "fixture: door open, seal in socket")
	check(forest.actors.rigs.has("cage_lf_site_01") and forest.actors.rigs.has("lf_captive_01_a"), "cage and freed captives restored")
	check(not forest.actors.rigs.has("guardian_lf_site_01"), "defeated guardian removed")
	reset_actors()
	game.accept(fixture("site01_rescued"))
	for i in 3:
		forest.actors.tick(0.05)
	check(not forest.actors.rigs.has("lf_captive_01_a") and not forest.actors.rigs.has("lf_captive_01_b"), "rescued captives absent after reload")
	reset_actors()
	game.accept(fixture("site01_discovered"))
	for i in 3:
		forest.actors.tick(0.05)
	check(forest.actors.rigs.has("guardian_lf_site_01") and forest.actors.rigs.has("lf_captive_01_c"), "guardian + caged captives present")
	var leader: Dictionary = forest.actors.motion.get("squad_0", {})
	check(not leader.is_empty() and leader.position.distance_to(Vector3(-20, leader.position.y, -65)) < 3.5, "squad representatives at the site")

	# 8. Live transitions: cage opening choreography (key into socket, latch, door, exit).
	reset_actors()
	game.accept(fixture("site01_battle_victory"))
	forest.actors.tick(0.05)
	var opened := fixture("site01_cage_open")
	game.accept(opened)
	forest.actors.tick(0.05)
	check(forest.actors.choreo.has("cage:lf_site_01") and forest.actors.choreo.has("key:lf_site_01"), "live cage opening choreography")

	# 9. Panels: squad formation, rewards, journal, route.
	reset_actors()
	game.accept(fixture("prologue"))
	await frames(1)
	forest.panels.open_squad()
	check(labels_text(game.modal_body).contains(content.text("hud.squadNote")), "squad note explains the army size")
	check(game.modal_body.find_children("Squad_*", "SpinBox", true, false).size() >= 1, "squad spin boxes from healthy units")
	stub.requests.clear()
	stub.replies = [fixture("prologue")]
	var submit: Button = game.modal_body.find_child("SquadSubmit", true, false)
	for spin: SpinBox in game.modal_body.find_children("Squad_*", "SpinBox", true, false):
		spin.value = 2
	submit.pressed.emit()
	await frames(3)
	check(stub.requests.size() == 1 and stub.requests[0].body.action == "form_squad" and stub.requests[0].body.units is Dictionary, "form_squad body")
	game.accept(fixture("completed"))
	await frames(1)
	forest.panels.open_rewards()
	var rewards_text := labels_text(game.modal_body)
	check(rewards_text.contains("Начислено всего") and rewards_text.contains("Получено на склад") and rewards_text.contains("Осталось забрать"), "escrow columns")
	check(game.modal_body.find_child("ClaimRewards", true, false) != null and game.modal_body.find_child("AutoRefill", true, false) != null, "claim + auto-refill controls")
	check(rewards_text.contains(content.text("reward.autoRefill.description")), "auto-refill explanation")
	forest.panels.open_journal()
	var journal := labels_text(game.modal_body)
	for site_id in content.site_order:
		check(journal.contains(content.site(site_id).name), "journal lists " + site_id)
	check(journal.contains(content.testimony("lf_site_12").text), "journal testimony text")
	check(journal.contains(content.text("ending.title")), "journal ending")
	game.close_modal()

	# 10. Mechanism UIs (four kinds) with authored labels and reset feedback.
	for item in [["site01_trail_1of3", "lf_site_01", "trail_cache"], ["site02_rune_wrong", "lf_site_02", "rune_lock"], ["site04_plates_held", "lf_site_04", "paired_latch"]]:
		reset_actors()
		game.accept(fixture(item[0]))
		forest.mech.open(item[1])
		check(forest.mech.is_open() and forest.mech.kind == item[2], "mechanism UI " + item[2])
		check(forest.mech.inputs.get_child_count() >= 3, "symbol inputs " + item[2])
		forest.mech.on_progress(item[1], false)
		check(forest.mech.feedback.text == content.text("mechanism.wrong"), "wrong input feedback " + item[2])
		forest.mech.close()
	game.accept(fixture("site03_winch_solved"))
	var winch_poi: Dictionary = forest.client.poi("lf_site_03")
	check(String(winch_poi.get("variation", "")) == "winch_sequence", "winch fixture")

	# 11. Boss telegraphs from the server timeline.
	reset_actors()
	game.accept(fixture("boss_battle_35"))
	for i in 3:
		forest.actors.tick(0.05)
	var fight: Dictionary = forest.client.battle()
	var tele = forest.actors.telegraphs
	var hit_any := false
	for event in fight.timeline:
		if String(event.get("type", "")) == "telegraph":
			var t := float(event.t) + 0.5
			tele.update_from_battle(fight, t, Vector3(75, 6.5, -86), 0.0, Vector3(75, 6.5, -76))
			hit_any = hit_any or (tele.decals.size() > 0 and tele.current_warning() == content.text("boss.telegraph." + String(event.attack)))
	check(hit_any, "telegraph decals with authored warnings")

	# 12. Command bodies never carry client-decided fields.
	for entry in forest.client.sent_log:
		var body: Dictionary = entry.body
		var key: String = body.kind if body.kind == "adventure_intro" else String(body.action)
		check(String(body.get("requestId", "")) == String(entry.key), "body requestId equals Idempotency-Key")
		for field in body:
			check(field == "requestId" or ALLOWED.get(key, []).has(field), "allowed field %s in %s" % [field, key])
	print("QA_FOREST_FLOW checks=", checks, " failures=", failures.size())
	for failure in failures:
		print("  FAIL ", failure)
	quit(0 if failures.is_empty() else 1)
