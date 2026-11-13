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
		print("QA_API_POOL reused=", pool.requests_reused, " total=", pool.requests_total, " opened=", pool.connections_opened)
	# Closed port: clean connection failure.
	pool.configure("http://127.0.0.1:9")
	var refused := await get_json(pool, "/api/state", 3.0)
	check(refused[0] == HTTPRequest.RESULT_CANT_CONNECT or refused[0] == HTTPRequest.RESULT_CONNECTION_ERROR, "Closed port result %d" % refused[0])
	OS.kill(pid)
	print("QA_API_POOL checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
