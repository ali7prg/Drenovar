extends SceneTree
## 1022 network rules (drenovar-server v6/docs/CONDITIONAL-STATE-1022.md and STATUS-1022-SERVER.md
## §10–12) in the real game scene against the synthetic in-memory V6 fixture:
##   DRENOVAR_SERVER_ROOT=<server checkout> DRENOVAR_QA_CONDITIONAL=1 node godot/tools/qa-v6-1022-server.mjs
##   godot --headless --path godot/project -s qa_net_1022.gd -- --server=http://127.0.0.1:8799
## Checks: city load from V6, five-unit roster, a 304 poll cycle (stock and clock advanced from the
## cached full answer, equal to a full answer), silent command retries with the same key after a
## lost answer and after 503s, no connection notice before 10 s without a 200/304, foreground
## requests never refused while another is in flight, poll cadence, forest locked and no extra
## polling while the server reports the adventure off.

const ROSTER := ["ENG-01", "ENG-02", "ENG-03", "ENG-04", "ENG-06"]
const RETIRED_NAMES := ["Пеший новобранец", "Городской ополченец", "Тяжёлый пеший воин", "Конный разведчик", "Лёгкий метатель дротиков"]
var game: Node
var checks := 0
var failures: Array[String] = []
var report := {}

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_NET_1022: " + detail)

func _initialize() -> void:
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func post(path: String, body: Variant = null) -> Variant:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST,
		"" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else null

func fixture_log() -> Array:
	var value: Variant = await post("/qa/requests")
	return value if value is Array else []

func ui_texts(node: Node) -> PackedStringArray:
	var out := PackedStringArray()
	for child in node.find_children("*", "", true, false):
		if child is Label or child is Button:
			out.append(str(child.text))
	return out

func run() -> void:
	root.size = Vector2i(1366, 630)
	var started := Time.get_ticks_msec()
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty() or not game.state.has("v6")) and Time.get_ticks_msec() < deadline:
		await process_frame
	report.city_load_ms = Time.get_ticks_msec() - started
	check(game.loopback and game.endpoint.begins_with("http://127.0.0.1:"), "runs against the local fixture")
	check(str(game.state.get("economy_version", "")) == "DRENOVAR-V6-C1.0" and game.state.has("city"), "city loaded from the V6 server")
	check(game.is_v6_server(), "V6 protocol confirmed")
	await frames(10)
	game.set_process(false)  # polls are driven by this script from here on
	# --- roster: exactly the five kept units, nowhere a retired one
	var soldiers: Array = game.data.englishRoster.filter(func(u): return str(u.get("training_building", "")) != "SIEGE").map(func(u): return str(u.id))
	check(soldiers == ROSTER, "roster is exactly five units: " + str(soldiers))
	check(Array(game.RECRUIT_ORDER) == ROSTER, "recruit order: " + str(game.RECRUIT_ORDER))
	check((game.state.get("healthy", {}) as Dictionary).keys().all(func(id): return id in ROSTER), "server army uses kept units only: " + str(game.state.get("healthy", {})))
	report.roster = soldiers
	report.healthy = game.state.get("healthy", {})
	# --- 304 cycle
	var log_start: int = (await fixture_log()).size()
	await game.poll_account_state()
	check(not game.state_etag.is_empty(), "the tagged 200 is kept (ETag)")
	var tagged_time := float(game.state.serverTime)
	var tagged_wood := int(game.balance("wood"))
	await post("/test/clock?time=%d" % int(tagged_time + 9000.0))
	var tries := 0
	while game.not_modified_polls == 0 and tries < 5:
		tries += 1
		await game.poll_account_state()
	check(game.not_modified_polls > 0, "a conditional poll answered 304")
	check(float(game.state.serverTime) >= tagged_time + 9000.0, "the 304 moved the server time on (%d -> %d)" % [int(tagged_time), int(game.state.serverTime)])
	var advanced_wood := int(game.balance("wood"))
	var cycle: Array = (await fixture_log()).slice(log_start).filter(func(r): return str(r.path).ends_with("/state"))
	var full: Dictionary = await game.send_request("state", null, false)
	var stock_ok := full.has("v6")
	if stock_ok:
		for resource in full.v6.stock:
			stock_ok = stock_ok and absi(int(game.state.v6.stock.get(resource, -99)) - int(full.v6.stock[resource])) <= 1
	check(stock_ok, "stock advanced on the 304 equals a full answer: %s vs %s" % [str(game.state.get("v6", {}).get("stock")), str(full.get("v6", {}).get("stock"))])
	check(advanced_wood == int(game.state.v6.stock.wood), "HUD wood follows the advanced stock")
	check(not game.connection_badge.visible, "no connection notice around a 304")
	check(cycle.any(func(r): return int(r.status) == 304 and r.ifNoneMatch), "fixture saw If-None-Match answered by 304")
	check(cycle.all(func(r): return r.conditional), "every state poll opts in")
	report["304_cycle"] = {"polls": cycle.map(func(r): return [int(r.status), r.ifNoneMatch, r.etag]), "wood_tagged": tagged_wood,
		"wood_after_304": advanced_wood, "wood_full": int(full.get("v6", {}).get("stock", {}).get("wood", -1)),
		"server_time_tagged": int(tagged_time), "server_time_after_304": int(game.state.serverTime)}
	# --- silent retry: the answer of a committed command is lost twice (the pool resends a request
	# lost on a reused kept-alive connection at once; the second loss is repeated after 0.4 s)
	log_start = (await fixture_log()).size()
	await post("/qa/fault", {"kind": "editNames", "count": 2, "mode": "drop"})
	var retries_before: int = game.command_retries
	var sent_at := Time.get_ticks_msec()
	var ok: bool = await game.command({"kind": "editNames", "nickname": "Проверка", "settlementName": "Город проверки"})
	report.silent_retry_ms = Time.get_ticks_msec() - sent_at
	check(ok, "command succeeds after a lost answer")
	check(game.command_retries == retries_before + 1, "one silent command retry after the pool resend (%d)" % (game.command_retries - retries_before))
	check(game.state_etag.is_empty(), "a command answer drops the tag")
	var sent: Array = (await fixture_log()).slice(log_start).filter(func(r): return str(r.path).ends_with("/command"))
	check(sent.size() == 3 and sent.all(func(r): return str(r.receipt) == str(sent[0].receipt)) and str(sent[0].get("fault", "")) == "drop" \
		and str(sent[1].get("fault", "")) == "drop" and int(sent[2].status) == 200, "retries repeat the same Idempotency-Key: " + str(sent))
	check(not game.connection_badge.visible, "no connection notice for a lost answer")
	check(not game.message.text.contains("Сервер недоступен") and not game.message.text.contains("Нет связи"), "no outage message: " + game.message.text)
	report.silent_retry = sent.map(func(r): return [str(r.receipt), int(r.status), str(r.get("fault", ""))])
	# two 503 pages before the server sees the command: retried at 0.4 and 1.2 s
	log_start = (await fixture_log()).size()
	await post("/qa/fault", {"kind": "editNames", "count": 2, "mode": "503"})
	retries_before = game.command_retries
	sent_at = Time.get_ticks_msec()
	ok = await game.command({"kind": "editNames", "nickname": "Проверка", "settlementName": "Город проверки II"})
	report.retry_503_ms = Time.get_ticks_msec() - sent_at
	check(ok and game.command_retries == retries_before + 2, "two 503 pages retried silently (%d)" % (game.command_retries - retries_before))
	sent = (await fixture_log()).slice(log_start).filter(func(r): return str(r.path).ends_with("/command"))
	check(sent.size() == 3 and sent.all(func(r): return str(r.receipt) == str(sent[0].receipt)), "same key on every 503 retry")
	check(not game.connection_badge.visible, "no connection notice for two 503 pages")
	report.retry_503 = sent.map(func(r): return [str(r.receipt), int(r.status), str(r.get("fault", ""))])
	# --- the connection notice: only after 10 s without any 200 or 304
	await post("/qa/poll-fault", {"count": 2, "mode": "503"})
	await game.poll_account_state()
	await game.poll_account_state()
	check(game.diagnostics.server_failures >= 2, "two failed polls counted")
	check(not game.connection_badge.visible, "two failed polls stay silent (notice only after 10 s)")
	game.last_ok_msec = Time.get_ticks_msec() - 10001
	game.update_connection_notice()
	check(game.connection_badge.visible, "notice after 10 s without a 200/304")
	await game.poll_account_state()
	check(not game.connection_badge.visible and game.diagnostics.server_failures == 0, "a 200/304 clears the notice")
	report.banner = {"after_two_failures": false, "after_10s": true, "after_success": game.connection_badge.visible}
	# --- a tap is never refused because another request is in flight
	game.send_request("state", null, true)
	check(game.busy, "the first foreground request is in flight")
	var second: Dictionary = await game.send_request("state", null, true)
	check(second.has("city"), "a second foreground request is not refused: " + str(second.get("error", "")))
	await frames(30)
	check(not game.busy and game.foreground_in_flight == 0, "busy clears after both answers")
	# --- cadence (rule 11)
	var saved_armies: Array = game.state.get("armies", []).duplicate(true)
	check(is_equal_approx(game.poll_interval(), 4.0), "4 s at rest (%.2f)" % game.poll_interval())
	var now: float = game.timer_now()
	game.state.armies = [{"id": "qa-out", "status": "outbound", "owner": game.player_id, "arrivesAt": now + 20000.0, "battleEndsAt": now + 30000.0, "returnStartsAt": now + 30000.0}]
	check(is_equal_approx(game.poll_interval(), 2.0), "2 s while an army is out (%.2f)" % game.poll_interval())
	game.state.armies[0].arrivesAt = now + 2000.0
	check(is_equal_approx(game.poll_interval(), 0.65), "650 ms within 3 s of a fight (%.2f)" % game.poll_interval())
	game.state.armies[0].arrivesAt = now - 20000.0
	game.state.armies[0].battleEndsAt = now - 1000.0
	game.state.armies[0].returnStartsAt = now - 1000.0
	check(is_equal_approx(game.poll_interval(), 0.65), "650 ms for 3 s after the return starts (%.2f)" % game.poll_interval())
	game.state.armies = saved_armies
	game.diagnostics.server_failures = 3
	check(is_equal_approx(game.poll_interval(), 15.0), "back-off up to 15 s (%.2f)" % game.poll_interval())
	game.diagnostics.server_failures = 2
	check(is_equal_approx(game.poll_interval(), 8.0), "back-off base x 2^(n-1) (%.2f)" % game.poll_interval())
	game.diagnostics.server_failures = 0
	report.cadence = {"rest": 4.0, "march": 2.0, "fight": 0.65, "backoff_n2": 8.0, "backoff_max": 15.0}
	# --- adventure off on the server: forest locked, no forest requests, no extra polling
	# 1022: without state.adventure neither forest layer is ever loaded (the city keeps the 1021 forest).
	check(not game.adventure_offered(game.state), "no state.adventure from this server")
	check(game.forest_game == null and not game.forest_game_loading, "adventure off: the forest game layer is not loaded")
	check(game.stage.forest_world == null and game.stage.forest_attach_state == "", "adventure off: no forest world layer, 1021 forest")
	log_start = (await fixture_log()).size()
	game.set_process(true)
	var watch_until := Time.get_ticks_msec() + 9000
	while Time.get_ticks_msec() < watch_until:
		await process_frame
	game.set_process(false)
	var idle: Array = (await fixture_log()).slice(log_start)
	var idle_polls: int = idle.filter(func(r): return str(r.path).ends_with("/state")).size()
	check(idle_polls >= 1 and idle_polls <= 4, "rest polling about every 4 s with the adventure off: %d polls in 9 s" % idle_polls)
	check(idle.all(func(r): return str(r.path).ends_with("/state")), "only state polls while idle: " + str(idle.map(func(r): return r.path)))
	check(idle.all(func(r): return str(r.get("kind", "")) not in ["adventure", "adventure_intro"]), "no adventure commands with the adventure off")
	check(not game.connection_badge.visible and not game.message.text.contains("Сервер недоступен"), "no notices while idle")
	check(game.forest_game == null and game.stage.forest_world == null, "still no forest layer after 9 s of polling")
	report.idle_9s = {"polls": idle_polls, "statuses": idle.map(func(r): return int(r.status))}
	report.counters = {"not_modified": game.not_modified_polls, "full": game.full_polls, "retries": game.command_retries}
	print("QA_NET_1022_REPORT ", JSON.stringify(report))
	print("QA_NET_1022 checks=%d failures=%d" % [checks, failures.size()])
	for failure in failures:
		print("  FAIL ", failure)
	quit(0 if failures.is_empty() else 1)
