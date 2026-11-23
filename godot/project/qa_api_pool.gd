extends SceneTree

# Keep-alive connection pool against a real local HTTP/1.1 server
# (tests/support/keepalive_server.py, started by this script). Verifies that
# consecutive requests share one TCP connection, a server-dropped idle connection
# is replaced transparently, "Connection: close" is honoured, gzip bodies are
# decoded, concurrent requests get separate connections, and timeouts fire.

const PORT := 18731
var failures: Array[String] = []
var checks := 0
var pid := -1

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func body_of(result: Array) -> Dictionary:
	var parsed: Variant = JSON.parse_string((result[3] as PackedByteArray).get_string_from_utf8())
	return parsed if parsed is Dictionary else {}

func get_json(pool: ApiPool, path: String, timeout := 5.0) -> Array:
	return await pool.request(HTTPClient.METHOD_GET, path, PackedStringArray(["Accept: application/json"]), "", timeout, 1 << 20)

func connections(pool: ApiPool) -> int:
	return int(body_of(await get_json(pool, "/stats")).get("connections", -1))

## 1023: a 304 must never stall (whatever framing an intermediary gives it), and a request on a
## kept-alive connection that died silently goes again on a fresh connection at once.
func dead_links_and_304(pool: ApiPool) -> void:
	for kind in ["plain", "zero", "length", "chunked"]:
		var started := Time.get_ticks_msec()
		var answer := await get_json(pool, "/not-modified?" + kind, 8.0)
		var ms := Time.get_ticks_msec() - started
		check(answer[0] == HTTPRequest.RESULT_SUCCESS and int(answer[1]) == 304 and (answer[3] as PackedByteArray).is_empty(),
			"304 (%s) result %d code %d" % [kind, answer[0], answer[1]])
		check(ms < 1000, "304 (%s) stalled %d ms" % [kind, ms])
		var after := await get_json(pool, "/api/state")
		check(after[0] == HTTPRequest.RESULT_SUCCESS and body_of(after).get("path") == "/api/state", "request after a 304 (%s) failed" % kind)
		print("QA_API_POOL 304 framing=", kind, " ms=", ms)
	# A connection kept alive and then dead (no FIN, no RST, no answer ever): the next request is
	# answered on a fresh connection within the reused-answer limit, not after its 12 s timeout.
	await get_json(pool, "/api/state")
	var kill := await get_json(pool, "/kill-open")
	check(kill[0] == HTTPRequest.RESULT_SUCCESS, "kill-open failed")
	var retries_before := pool.fresh_retries
	var reused_before := pool.requests_reused
	var started := Time.get_ticks_msec()
	var revived := await pool.request(HTTPClient.METHOD_GET, "/api/state", PackedStringArray(["Accept: application/json"]), "", 12.0, 1 << 20)
	var revived_ms := Time.get_ticks_msec() - started
	check(pool.requests_reused > reused_before, "the request after the link died did not try the kept-alive connection")
	check(revived[0] == HTTPRequest.RESULT_SUCCESS and body_of(revived).get("path") == "/api/state", "request on a dead kept-alive connection failed: %s" % str(revived.slice(0, 2)))
	check(revived_ms < (ApiPool.REUSED_ANSWER_USEC / 1000) + 1500, "dead connection held the request %d ms" % revived_ms)
	check(pool.fresh_retries == retries_before + 1, "dead connection not retried on a fresh one")
	print("QA_API_POOL dead_link_ms=", revived_ms, " fresh_retries=", pool.fresh_retries)
	# A command (POST) keeps its Idempotency-Key on the fresh connection.
	await get_json(pool, "/kill-open")
	var command := await pool.request(HTTPClient.METHOD_POST, "/api/command", PackedStringArray(["Content-Type: application/json", "Idempotency-Key: dead-1"]),
		JSON.stringify({"kind": "train"}), 12.0, 1 << 20)
	check(command[0] == HTTPRequest.RESULT_SUCCESS and body_of(command).get("key") == "dead-1", "command after a dead link lost its key: %s" % str(body_of(command)))
	# An idle connection older than IDLE_REUSE_USEC is closed, not reused.
	await get_json(pool, "/api/state")
	check(pool.idle.size() >= 1, "no idle connection kept")
	for i in pool.idle_since.size():
		pool.idle_since[i] -= ApiPool.IDLE_REUSE_USEC + 1000000
	var dropped_before := pool.stale_dropped
	reused_before = pool.requests_reused
	var aged := await get_json(pool, "/api/state")
	check(aged[0] == HTTPRequest.RESULT_SUCCESS and pool.requests_reused == reused_before and pool.stale_dropped > dropped_before, "an old idle connection was reused")
	# drop_idle (the app came back to the foreground) closes every idle connection.
	await get_json(pool, "/api/state")
	pool.drop_idle()
	check(pool.idle.is_empty() and pool.idle_since.is_empty(), "drop_idle left idle connections")
	reused_before = pool.requests_reused
	var fresh := await get_json(pool, "/api/state")
	check(fresh[0] == HTTPRequest.RESULT_SUCCESS and pool.requests_reused == reused_before, "request after drop_idle reused a connection")

func run() -> void:
	var script := ProjectSettings.globalize_path("res://tests/support/keepalive_server.py")
	pid = OS.create_process("python3", [script, str(PORT)])
	var pool := ApiPool.new()
	root.add_child(pool)
	pool.configure("http://127.0.0.1:%d" % PORT)
	var ready := false
	for attempt in 50:
		var probe := await get_json(pool, "/stats", 1.0)
		if probe[0] == HTTPRequest.RESULT_SUCCESS:
			ready = true
			break
		await create_timer(0.1).timeout
	check(ready, "Test server did not start")
	if ready:
		var before := await connections(pool)
		var times: Array[float] = []
		for index in 10:
			var started := Time.get_ticks_usec()
			var echo := await pool.request(HTTPClient.METHOD_POST, "/api/command", PackedStringArray(["Content-Type: application/json", "Idempotency-Key: k%d" % index]),
				JSON.stringify({"kind": "train", "n": index}), 5.0, 1 << 20)
			times.append((Time.get_ticks_usec() - started) / 1000.0)
			var answer := body_of(echo)
			check(echo[0] == HTTPRequest.RESULT_SUCCESS and int(echo[1]) == 200, "POST %d failed: %s" % [index, str(echo.slice(0, 2))])
			check(answer.get("key") == "k%d" % index and str(answer.get("body", "")).contains("\"n\":%d" % index), "POST %d echo wrong: %s" % [index, str(answer)])
		var after := await connections(pool)
		check(after == before, "Sequential requests opened %d new connections (expected 0)" % (after - before))
		print("QA_API_POOL sequential_ms=", times, " new_connections=", after - before)
		# Server drops idle connections: next request must still succeed on a fresh one.
		var drop := await get_json(pool, "/drop")
		check(drop[0] == HTTPRequest.RESULT_SUCCESS, "Drop request failed")
		await create_timer(0.2).timeout
		var revived := await get_json(pool, "/api/state")
		check(revived[0] == HTTPRequest.RESULT_SUCCESS and body_of(revived).get("path") == "/api/state", "Request after server-side close failed: %s" % str(revived.slice(0, 2)))
		# Connection: close is honoured, and the following request reconnects.
		var closed := await get_json(pool, "/close")
		check(closed[0] == HTTPRequest.RESULT_SUCCESS and body_of(closed).get("closed") == true, "Connection: close response lost")
		var reopened := await get_json(pool, "/api/state")
		check(reopened[0] == HTTPRequest.RESULT_SUCCESS, "Request after Connection: close failed")
		# gzip bodies are decoded.
		var packed := await get_json(pool, "/gzip")
		check(packed[0] == HTTPRequest.RESULT_SUCCESS and str(body_of(packed).get("city", {}).get("big", "")).length() == 5000, "gzip body not decoded")
		# Concurrent requests do not wait for each other.
		var slow_started := Time.get_ticks_msec()
		var slow_done := [false]
		var slow := func():
			await get_json(pool, "/slow", 10.0)
			slow_done[0] = true
		slow.call()
		await process_frame
		var fast_started := Time.get_ticks_msec()
		var fast := await get_json(pool, "/api/state")
		check(fast[0] == HTTPRequest.RESULT_SUCCESS and Time.get_ticks_msec() - fast_started < 1500 and not slow_done[0], "A request waited behind a slow one")
		while not slow_done[0]:
			await process_frame
		check(Time.get_ticks_msec() - slow_started >= 2900, "Slow request returned early")
		# Timeouts fire.
		var late := await get_json(pool, "/slow", 0.5)
		check(late[0] == HTTPRequest.RESULT_TIMEOUT, "Timeout not reported: %d" % late[0])
		check(pool.requests_reused > 0, "No request reused a connection")
		# Obsolete previews never consume unbounded workers or all command slots.
		var current := [true]
		var completed := [0]
		var background := func():
			await pool.request(HTTPClient.METHOD_GET, "/slow", PackedStringArray(), "", 8.0, 1 << 20, false, func(): return current[0])
			completed[0] += 1
		for i in 6: background.call()
		await process_frame
		check(pool.threads.size() == 3, "Background requests exceeded three active workers")
		fast_started = Time.get_ticks_msec()
		fast = await get_json(pool, "/api/state")
		check(fast[0] == HTTPRequest.RESULT_SUCCESS and Time.get_ticks_msec() - fast_started < 500, "A command waited behind obsolete previews")
		var cancel_started := Time.get_ticks_msec()
		current[0] = false
		while completed[0] < 6 and Time.get_ticks_msec() - cancel_started < 1000: await process_frame
		check(completed[0] == 6 and Time.get_ticks_msec() - cancel_started < 500, "Cancelled previews kept waiting for their HTTP timeout")
		check(pool.peak_active <= 4 and pool.requests_cancelled >= 3, "Active worker bound/cancellation not enforced")
		print("QA_API_POOL reused=", pool.requests_reused, " total=", pool.requests_total, " opened=", pool.connections_opened)
	if ready:
		await dead_links_and_304(pool)
	# Closed port: clean connection failure.
	pool.configure("http://127.0.0.1:9")
	var refused := await get_json(pool, "/api/state", 3.0)
	check(refused[0] == HTTPRequest.RESULT_CANT_CONNECT or refused[0] == HTTPRequest.RESULT_CONNECTION_ERROR, "Closed port result %d" % refused[0])
	OS.kill(pid)
	print("QA_API_POOL checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
