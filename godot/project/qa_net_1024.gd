extends SceneTree
## Build 1024 network chaos: the real game scene against a LOCAL V6 server that injects mobile-network
## faults. Never point it at production or staging: it only accepts --server=http://127.0.0.1:<port>.
##
## The server: a local stand-in for the live V6 Worker over an in-memory SQLite "D1" (the harness of
## qa_build_e2e.gd, with the forest adventure on and the 1022 fixture controls /qa/fault, /qa/poll-fault,
## /qa/requests), plus these chaos controls (all POST, JSON; they never touch /api/*):
##   /test/chaos {scope:'all'|'state'|'command', jitter:[min,max] ms (added round trip), loss:p (the answer
##               comes one TCP retransmission late, 1–3 s), blackhole:p (the flow dies: no answer, socket
##               left open), reset:p (socket destroyed before the server sees the request), reset_after:p
##               (applied, then the socket is destroyed: the answer is lost), stall:p with stall_ms:[min,max],
##               p503:p, p429:p (refused before processing), p524_after:p (applied, then a 524 page), seed:n}
##   /test/handoff   every open socket goes silent (a cellular handoff: old flows dead, new ones fine)
##   /test/down?ms=  the port closes for ms: new connections are refused, open ones reset (a real outage)
##   /qa/ledger      per hashed Idempotency-Key: attempts, applications (200, replayed=false), replays, body hash
##   /qa/stats       bytes of the answers (raw and gzip) by method, path and status
##   /qa/clear       clears the request log and the ledger
##   /test/reset, /test/clock?time=<ms>, /test/v6 {hall, stock}, /test/army {units}
## The chaos layer is QA tooling kept outside the repository (it wraps the qa_build_e2e harness); the
## controls above are its whole contract.
##
##   godot --headless --path godot/project -s qa_net_1024.gd -- --server=http://127.0.0.1:8811 \
##     [--out=<report.json>] [--scale=1.0] [--phases=idle,rest,active,mobile,resets,errors,stalls,handoffs,background,outage,restart]
##
## Each phase runs the game as it runs on a phone (its own polling, its own command path) and measures:
## - the alarming «Нет связи · повторяем» while the network is up (a false outage) and its time on screen;
## - after a real outage, a handoff or a return from the background: the time to the next 200/304;
## - orders (V6 training, small parties, each with its own "qa_order" number so every logical order has its
##   own body; the local server ignores the field): the keys the server saw for each one, how often it
##   applied each key; an order is lost when the client said «done»
##   and the server never applied it, doubled when it was applied under two keys or twice under one;
## - poll bytes per minute at rest (touched within 90 s, and left untouched: "rest") and with orders
##   running, the share of 304 answers;
## - the longest frame and the frames over 33 ms while answers arrive (headless: CPU only).

const VERSION := "DRENOVAR-V6-C1.0"
const STOCK := {"wood": 9000000, "food": 9000000, "stone": 9000000, "iron": 9000000, "coins": 9000000}
const ALL_PHASES := ["idle", "rest", "active", "mobile", "resets", "errors", "stalls", "handoffs", "background", "outage", "restart"]

var game: Node
var server := ""
var out_path := ""
var scale := 1.0
var phases: Array = ALL_PHASES.duplicate()
var checks := 0
var failures: Array[String] = []
var report := {"phases": {}}
# Logical orders: {qty, body_hash, result(bool), attempts(user taps), phase}
var orders: Array[Dictionary] = []
var next_quantity := 1
# Per-frame watch of the link notices and frame times.
var phase_name := ""
var network_down := false
var watch := {}
var last_frame_usec := 0
var ok_events: Array[int] = []   # local msec of every 200/304 the client accepted (from last_ok_msec changes)
var last_seen_ok := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_NET_1024: " + detail)
	print(("ok   " if value else "FAIL ") + detail)

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			server = arg.trim_prefix("--server=").trim_suffix("/")
		elif arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--scale="):
			scale = float(arg.trim_prefix("--scale="))
		elif arg.begins_with("--phases="):
			phases = Array(arg.trim_prefix("--phases=").split(","))
	if not server.begins_with("http://127.0.0.1:"):
		push_error("QA_NET_1024: --server must be a local harness (http://127.0.0.1:<port>)")
		quit(2)
		return
	call_deferred("run")

# ------------------------------------------------------------------ harness

func control(path: String, body: Variant = null, method := HTTPClient.METHOD_POST) -> Variant:
	var client := HTTPRequest.new()
	client.timeout = 10.0
	root.add_child(client)
	client.request(server + path, PackedStringArray(["Content-Type: application/json"]), method,
		"" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else null

func stats() -> Dictionary:
	var value: Variant = await control("/qa/stats", null, HTTPClient.METHOD_GET)
	return value if value is Dictionary else {}

func ledger() -> Dictionary:
	var value: Variant = await control("/qa/ledger", null, HTTPClient.METHOD_GET)
	return value if value is Dictionary else {}

func chaos(config: Dictionary) -> void:
	await control("/test/chaos", config)

# ------------------------------------------------------------------ watch (every frame)

func link_hint_visible() -> bool:
	var hint: Variant = game.get("link_hint")
	return hint is Control and is_instance_valid(hint) and hint.visible

func alarm_visible() -> bool:
	return is_instance_valid(game.connection_badge) and game.connection_badge.visible

func reset_watch() -> void:
	watch = {"frames": [], "alarm_ms": 0.0, "alarm_episodes": 0, "hint_ms": 0.0, "hint_episodes": 0,
		"alarm_on": false, "hint_on": false, "first_alarm_at": -1, "first_hint_at": -1, "started": Time.get_ticks_msec(),
		"alarm_texts": {}}

func tick() -> void:
	var now := Time.get_ticks_usec()
	var frame_ms := (now - last_frame_usec) / 1000.0 if last_frame_usec > 0 else 0.0
	last_frame_usec = now
	if watch.is_empty() or not is_instance_valid(game):
		return
	(watch.frames as Array).append(frame_ms)
	var alarm := alarm_visible()
	var hint := link_hint_visible()
	if alarm:
		watch.alarm_ms += frame_ms
		watch.alarm_texts[str(game.connection_badge.text)] = true
		if not watch.alarm_on:
			watch.alarm_episodes += 1
			if watch.first_alarm_at < 0:
				watch.first_alarm_at = Time.get_ticks_msec() - int(watch.started)
	if hint:
		watch.hint_ms += frame_ms
		if not watch.hint_on:
			watch.hint_episodes += 1
			if watch.first_hint_at < 0:
				watch.first_hint_at = Time.get_ticks_msec() - int(watch.started)
	watch.alarm_on = alarm
	watch.hint_on = hint
	if int(game.last_ok_msec) != last_seen_ok:
		last_seen_ok = int(game.last_ok_msec)
		ok_events.append(Time.get_ticks_msec())

func wait_ms(ms: float) -> void:
	var until := Time.get_ticks_msec() + int(ms)
	while Time.get_ticks_msec() < until:
		await process_frame

func wait_until(condition: Callable, ms: float) -> bool:
	var until := Time.get_ticks_msec() + int(ms)
	while Time.get_ticks_msec() < until:
		if condition.call():
			return true
		await process_frame
	return condition.call()

## Local msec of the first 200/304 accepted at or after `since`, or -1.
func first_ok_after(since: int) -> int:
	for at in ok_events:
		if at >= since:
			return at
	return -1

static func percentile(values: Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var sorted := values.duplicate()
	sorted.sort()
	return float(sorted[clampi(int(ceil(p * sorted.size())) - 1, 0, sorted.size() - 1)])

func frame_summary(frames: Array) -> Dictionary:
	var kept := frames.slice(2)
	return {"frames": kept.size(), "median_ms": snappedf(percentile(kept, 0.5), 0.1), "p95_ms": snappedf(percentile(kept, 0.95), 0.1),
		"p99_ms": snappedf(percentile(kept, 0.99), 0.1), "max_ms": snappedf(percentile(kept, 1.0), 0.1),
		"over_33ms": kept.filter(func(f): return f > 33.0).size()}

func close_phase(name: String, before: Dictionary, extra: Dictionary = {}) -> Dictionary:
	var after := await stats()
	var minutes := maxf(0.001, (Time.get_ticks_msec() - int(watch.started)) / 60000.0)
	var polls := {"200": 0, "304": 0, "other": 0, "bytes": 0, "gzip": 0}
	for key: String in (after.get("by", {}) as Dictionary):
		if not key.begins_with("GET /api/state"):
			continue
		var now_entry: Dictionary = after.by[key]
		var then_entry: Dictionary = before.get("by", {}).get(key, {"n": 0, "bytes": 0, "gzip": 0})
		var n := int(now_entry.n) - int(then_entry.n)
		var status := key.get_slice(" ", 2)
		polls[status if status in ["200", "304"] else "other"] += n
		polls.bytes += int(now_entry.bytes) - int(then_entry.bytes)
		polls.gzip += int(now_entry.gzip) - int(then_entry.gzip)
	var entry := {"seconds": snappedf(minutes * 60.0, 0.1), "polls": polls,
		"poll_bytes_per_min": int(polls.bytes / minutes), "poll_gzip_bytes_per_min": int(polls.gzip / minutes),
		"alarm_ms": int(watch.alarm_ms), "alarm_episodes": int(watch.alarm_episodes), "alarm_texts": (watch.alarm_texts as Dictionary).keys(),
		"hint_ms": int(watch.hint_ms), "hint_episodes": int(watch.hint_episodes),
		"first_alarm_ms": int(watch.first_alarm_at), "first_hint_ms": int(watch.first_hint_at),
		"frames": frame_summary(watch.frames),
		"pool": {"opened": game.api.connections_opened, "reused": game.api.requests_reused, "fresh_retries": game.api.fresh_retries,
			"total": game.api.requests_total}}
	entry.merge(extra, true)
	report.phases[name] = entry
	print("QA_NET_1024_PHASE %s %s" % [name, JSON.stringify(entry)])
	return entry

# ------------------------------------------------------------------ orders

## One logical training order the way a player gives it: the quote, then «Обучить»; when the game says it
## failed, the player taps again (up to `taps` times, `gap_ms` apart). The server's clock then runs past
## the order's end so the next one can start.
func give_order(taps := 4, gap_ms := 2500.0) -> Dictionary:
	# Small parties (the barracks takes at most 20 per party); "qa_order" keeps every logical order's body
	# unique, so the ledger can tell one order's retries from the next order (the local server ignores it).
	var order_no := next_quantity
	next_quantity += 1
	var quantity := 1 + (order_no - 1) % 5
	var intent := {"kind": "train", "unit": "ENG-01", "quantity": quantity, "economy_version": VERSION}
	# The army is emptied first so that the army limit never refuses an order (each order's body differs
	# by its quantity: one logical order, one body).
	await control("/test/army", {"units": {}})
	var quote: Dictionary = {}
	var quote_taps := 0
	while quote_taps < 30:
		quote_taps += 1
		game.set("last_interaction_msec", Time.get_ticks_msec())   # a tap on «Обучить»
		quote = await game.request("command", {"kind": "v6quote", "intent": intent})
		if quote.get("ok", false):
			break
		await wait_ms(1500)
	var entry := {"order": order_no, "qty": quantity, "phase": phase_name, "taps": 0, "result": false, "quote_taps": quote_taps}
	if not quote.get("ok", false):
		entry.error = "no quote: " + str(quote.get("error", quote.get("reason", "")))
		orders.append(entry)
		return entry
	intent.expected_duration_seconds = int(quote.quote.duration_seconds)
	var order := {"kind": "v6", "qa_order": order_no, "intent": intent}
	entry.body_hash = JSON.stringify(order).sha256_text().substr(0, 12)
	var started := Time.get_ticks_msec()
	while int(entry.taps) < taps:
		entry.taps += 1
		game.set("last_interaction_msec", Time.get_ticks_msec())   # a tap on «Отправить»
		var ok: bool = await game.command(order, func(): pass)
		if ok:
			entry.result = true
			break
		entry.last_error = game.last_command_error
		await wait_ms(gap_ms)
	entry.ms = Time.get_ticks_msec() - started
	orders.append(entry)
	if entry.result:
		var ends := float(game.state.get("serverTime", 0.0)) + float(quote.quote.duration_seconds) * 1000.0 + 2000.0
		await control("/test/clock?time=%d" % int(ends))
	return entry

## give_order() running beside the caller; task.done turns true when it ends.
func order_task(task: Dictionary, taps := 4, gap_ms := 2500.0) -> void:
	task.entry = await give_order(taps, gap_ms)
	task.done = true

## Orders every `every_ms` while the phase runs.
func run_with_orders(total_ms: float, every_ms: float) -> void:
	var until := Time.get_ticks_msec() + int(total_ms)
	while Time.get_ticks_msec() < until:
		await give_order()
		var rest := minf(every_ms, float(until - Time.get_ticks_msec()))
		if rest > 0:
			await wait_ms(rest)

func order_audit() -> Dictionary:
	var book := await ledger()
	var by_body := {}
	for receipt: String in book:
		var e: Dictionary = book[receipt]
		if not by_body.has(e.body):
			by_body[e.body] = []
		by_body[e.body].append(e)
	var lost := 0
	var doubled := 0
	var unconfirmed := 0
	var keys_per_order: Array = []
	var applied_total := 0
	for entry in orders:
		if not entry.has("body_hash"):
			continue
		var seen: Array = by_body.get(entry.body_hash, [])
		var applied := 0
		for e: Dictionary in seen:
			applied += int(e.applied)
			if int(e.applied) > 1:
				doubled += 1
		keys_per_order.append(seen.size())
		applied_total += applied
		if applied > 1:
			doubled += 1
		if entry.result and applied == 0:
			lost += 1
		if not entry.result and applied > 0:
			unconfirmed += 1
		entry.keys = seen.size()
		entry.applied = applied
		entry.attempts = seen.reduce(func(sum, e): return sum + int(e.attempts), 0)
	return {"orders": orders.size(), "confirmed": orders.filter(func(o): return o.result).size(), "applied": applied_total,
		"lost": lost, "doubled": doubled, "unconfirmed_but_applied": unconfirmed,
		"max_keys_per_order": keys_per_order.max() if not keys_per_order.is_empty() else 0,
		"attempts": orders.reduce(func(sum, o): return sum + int(o.get("attempts", 0)), 0)}

# ------------------------------------------------------------------ run

func boot() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 120000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty() or not game.state.has("v6") \
			or game.showing_cached_state) and Time.get_ticks_msec() < deadline:
		await process_frame
	last_seen_ok = int(game.last_ok_msec)

func run() -> void:
	root.size = Vector2i(1366, 630)
	process_frame.connect(tick)
	await control("/test/reset")
	await boot()
	check(game.loopback and game.endpoint == server, "runs against the local harness only (%s)" % game.endpoint)
	check(str(game.state.get("economy_version", "")) == VERSION, "city loaded from the local V6 server")
	await control("/test/v6", {"stock": STOCK})
	await game.poll_account_state()
	await wait_ms(3000)
	for name in phases:
		phase_name = name
		await chaos({})
		var before := await stats()
		reset_watch()
		print("QA_NET_1024 phase ", name)
		match name:
			"idle": await phase_idle(before)
			"rest": await phase_rest(before)
			"active": await phase_active(before)
			"mobile": await phase_mobile(before)
			"resets": await phase_resets(before)
			"errors": await phase_errors(before)
			"stalls": await phase_stalls(before)
			"handoffs": await phase_handoffs(before)
			"background": await phase_background(before)
			"outage": await phase_outage(before)
			"restart": await phase_restart(before)
		await chaos({})
		network_down = false
	reset_watch()
	await wait_ms(6000)
	report.orders = await order_audit()
	report.order_log = orders
	report.pool = {"opened": game.api.connections_opened, "reused": game.api.requests_reused, "fresh_retries": game.api.fresh_retries,
		"total": game.api.requests_total, "stale_dropped": game.api.stale_dropped, "cancelled": game.api.requests_cancelled}
	var false_alarm_ms := 0
	var up_ms := 0
	for name: String in report.phases:
		var p: Dictionary = report.phases[name]
		if name != "outage":
			false_alarm_ms += int(p.alarm_ms)
			up_ms += int(float(p.seconds) * 1000.0)
	report.false_outage = {"alarm_ms_while_up": false_alarm_ms, "up_ms": up_ms, "rate": snappedf(float(false_alarm_ms) / maxf(1.0, up_ms), 0.0001),
		"episodes_while_up": report.phases.keys().filter(func(n): return n != "outage").reduce(func(sum, n): return sum + int(report.phases[n].alarm_episodes), 0)}
	check(int(report.orders.lost) == 0, "no order lost: %s" % JSON.stringify(report.orders))
	check(int(report.orders.doubled) == 0, "no order applied twice")
	check(int(report.orders.max_keys_per_order) <= 1, "one Idempotency-Key per logical order across retries, taps and restarts (max %d)" % int(report.orders.max_keys_per_order))
	check(int(report.false_outage.episodes_while_up) == 0, "no «Нет связи» while the network is up: %s" % JSON.stringify(report.false_outage))
	print("QA_NET_1024_REPORT ", JSON.stringify(report))
	if not out_path.is_empty():
		var file := FileAccess.open(out_path, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify(report, "  "))
	print("QA_NET_1024 checks=%d failures=%d" % [checks, failures.size()])
	for failure in failures:
		print("  FAIL ", failure)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if failures.is_empty() else 1)

## At rest on a clean link: the cadence, the share of 304 and the bytes per minute.
func phase_idle(before: Dictionary) -> void:
	await wait_ms(60000 * scale)
	var p := await close_phase("idle", before)
	check(int(p.polls["200"]) + int(p.polls["304"]) >= int(10 * scale), "polls at rest (%s)" % JSON.stringify(p.polls))
	check(int(p.polls["304"]) >= int(p.polls["200"]) - 1, "at rest most polls are answered 304 (%s)" % JSON.stringify(p.polls))
	check(int(p.alarm_episodes) == 0 and int(p.hint_episodes) == 0, "a clean link shows no link notice")

## The phone left on the table: nothing running and no touch for more than 90 s (1024: polls every
## 8 s instead of 4; the build before 1024 has no such rest cadence and keeps polling every 4 s).
func phase_rest(before: Dictionary) -> void:
	game.set("last_interaction_msec", Time.get_ticks_msec() - 100000)
	await wait_ms(60000 * scale)
	var p := await close_phase("rest", before)
	check(int(p.polls["200"]) + int(p.polls["304"]) >= int(5 * scale), "polls when left untouched (%s)" % JSON.stringify(p.polls))
	check(int(p.alarm_episodes) == 0 and int(p.hint_episodes) == 0, "untouched: no link notice")

## Orders running on a clean link.
func phase_active(before: Dictionary) -> void:
	await run_with_orders(60000 * scale, 5000)
	var p := await close_phase("active", before)
	check(int(p.alarm_episodes) == 0, "orders on a clean link: no alarm")

## A 3G-like link: 300–800 ms added round trip, 3 % of answers one retransmission late.
func phase_mobile(before: Dictionary) -> void:
	await chaos({"scope": "all", "jitter": [300, 800], "loss": 0.03, "seed": 11})
	await run_with_orders(90000 * scale, 4000)
	var p := await close_phase("mobile", before)
	check(int(p.alarm_episodes) == 0, "3G-like link: no alarm (%d ms)" % int(p.alarm_ms))

## Connection resets: before the server sees a request, and after it applied one (the answer is lost).
func phase_resets(before: Dictionary) -> void:
	await chaos({"scope": "all", "reset": 0.08, "reset_after": 0.08, "jitter": [100, 300], "seed": 23})
	await run_with_orders(60000 * scale, 3000)
	var p := await close_phase("resets", before)
	check(int(p.alarm_episodes) == 0, "connection resets: no alarm (%d ms)" % int(p.alarm_ms))

## An overloaded edge: 503 and 429 pages before the server, 524 after it applied the order.
func phase_errors(before: Dictionary) -> void:
	await chaos({"scope": "all", "p503": 0.12, "p429": 0.08, "p524_after": 0.05, "seed": 37})
	await run_with_orders(60000 * scale, 3000)
	var p := await close_phase("errors", before)
	check(int(p.alarm_episodes) == 0 or not (p.alarm_texts as Array).has(game.OFFLINE_NOTICE), "server errors never read as «Нет связи»: %s" % str(p.alarm_texts))

## Server stalls of 5–30 s on 15 % of requests.
func phase_stalls(before: Dictionary) -> void:
	await chaos({"scope": "all", "stall": 0.15, "stall_ms": [5000, 30000], "seed": 41})
	await run_with_orders(90000 * scale, 4000)
	var p := await close_phase("stalls", before)
	check(not (p.alarm_texts as Array).has(game.OFFLINE_NOTICE), "server stalls never read as «Нет связи»: %s (%d ms)" % [str(p.alarm_texts), int(p.alarm_ms)])

## Cellular handoffs every 15 s: every open connection goes silent; new ones work.
func phase_handoffs(before: Dictionary) -> void:
	await chaos({"scope": "all", "jitter": [300, 800], "seed": 53})
	var recover: Array = []
	var until := Time.get_ticks_msec() + int(90000 * scale)
	while Time.get_ticks_msec() < until:
		var task := {"done": false}
		order_task(task)
		await wait_ms(1200)
		var at := Time.get_ticks_msec()
		await control("/test/handoff")
		await wait_until(func(): return first_ok_after(at) >= 0, 40000)
		var ok := first_ok_after(at)
		recover.append(ok - at if ok >= 0 else 40000)
		await wait_until(func(): return task.done, 120000)
		await wait_ms(maxf(0.0, 15000.0 - (Time.get_ticks_msec() - at)))
	var p := await close_phase("handoffs", before, {"recover_ms": recover, "recover_p50_ms": percentile(recover, 0.5), "recover_max_ms": percentile(recover, 1.0)})
	check(int(p.alarm_episodes) == 0, "handoffs: no alarm (%d ms)" % int(p.alarm_ms))
	check(percentile(recover, 1.0) <= 8000.0, "handoffs: the next 200/304 within 8 s (%s)" % str(recover))

## The app goes to the background while a poll hangs on a dead flow, comes back 20 s later.
func phase_background(before: Dictionary) -> void:
	var recover: Array = []
	var shown_after: Array = []
	for cycle in 3:
		await wait_ms(2000)
		# A poll in flight on a flow that dies with the suspension.
		await chaos({"scope": "state", "blackhole": 1.0})
		game.poll = 1000.0
		await wait_ms(600)
		game.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
		game.set_process(false)
		await control("/test/handoff")
		await chaos({})
		OS.delay_msec(int(20000 * scale))   # the device suspends every thread of the app
		last_frame_usec = Time.get_ticks_usec()   # the suspension is not a frame
		var at := Time.get_ticks_msec()
		game.set_process(true)
		game.notification(Node.NOTIFICATION_APPLICATION_RESUMED)
		var alarm_before := int(watch.alarm_episodes)
		await wait_until(func(): return first_ok_after(at) >= 0, 30000)
		var ok := first_ok_after(at)
		recover.append(ok - at if ok >= 0 else 30000)
		await wait_ms(4000)
		shown_after.append(int(watch.alarm_episodes) - alarm_before)
	var p := await close_phase("background", before, {"recover_ms": recover, "alarm_after_resume": shown_after})
	check(shown_after.all(func(n): return n == 0), "no «Нет связи» flash after coming back: %s" % str(shown_after))
	check(percentile(recover, 1.0) <= 3000.0, "back from the background: state within 3 s (%s)" % str(recover))

## A real outage of 35 s with an order given in the middle of it; the player taps again once it is back.
func phase_outage(before: Dictionary) -> void:
	await wait_ms(3000)
	var at := Time.get_ticks_msec()
	network_down = true
	await control("/test/down?ms=%d" % int(35000 * scale))
	await wait_ms(5000 * scale)
	var task := {"done": false}
	order_task(task, 12, 4000)
	await wait_ms(maxf(0.0, 35000 * scale - (Time.get_ticks_msec() - at)))
	network_down = false
	var up := Time.get_ticks_msec()
	await wait_until(func(): return first_ok_after(up) >= 0, 40000)
	var ok := first_ok_after(up)
	await wait_until(func(): return task.done, 180000)
	await wait_ms(3000)
	var p := await close_phase("outage", before, {"recover_ms": ok - up if ok >= 0 else -1,
		"alarm_after_ms": int(watch.first_alarm_at), "hint_after_ms": int(watch.first_hint_at)})
	check(int(p.alarm_episodes) >= 1, "a real outage is reported (alarm after %d ms)" % int(p.first_alarm_ms))
	check(ok >= 0 and ok - up <= 6000, "after the outage the state is back within 6 s (%d ms)" % (ok - up if ok >= 0 else -1))
	check(not alarm_visible(), "the alarm is gone once the network is back")

## The answer of an applied order is lost on every try; the app is closed and opened again, and the player
## gives the same order: the server sees the same key (a replay), never a second order.
func phase_restart(before: Dictionary) -> void:
	# Small parties (the barracks takes at most 20 per party); "qa_order" keeps every logical order's body
	# unique, so the ledger can tell one order's retries from the next order (the local server ignores it).
	var order_no := next_quantity
	next_quantity += 1
	var quantity := 1 + (order_no - 1) % 5
	var intent := {"kind": "train", "unit": "ENG-01", "quantity": quantity, "economy_version": VERSION}
	await control("/test/army", {"units": {}})
	var quote: Dictionary = await game.request("command", {"kind": "v6quote", "intent": intent})
	intent.expected_duration_seconds = int(quote.get("quote", {}).get("duration_seconds", 0))
	var order := {"kind": "v6", "qa_order": order_no, "intent": intent}
	var entry := {"order": order_no, "qty": quantity, "phase": "restart", "taps": 1, "result": false, "body_hash": JSON.stringify(order).sha256_text().substr(0, 12)}
	await control("/qa/fault", {"kind": "v6", "count": 20, "mode": "drop"})
	var first: bool = await game.command(order, func(): pass)
	await control("/qa/fault", {"kind": "v6", "count": 0, "mode": "drop"})
	check(not first, "every answer lost: the game reports the order as not confirmed")
	game.notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	game.queue_free()
	await process_frame
	await process_frame
	await boot()
	entry.taps = 2
	var second: bool = await game.command(order, func(): pass)
	entry.result = second
	if not second:
		entry.last_error = game.last_command_error
	orders.append(entry)
	var p := await close_phase("restart", before)
	check(second, "the same order after a restart is confirmed (%s)" % str(entry.get("last_error", "")))
