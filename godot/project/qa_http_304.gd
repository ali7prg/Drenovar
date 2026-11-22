extends SceneTree
## 1022 network rule 3: Godot must complete a real V6 304 at once (HTTP/1.1 keep-alive, no
## Content-Length, no body, no Content-Encoding), through ApiPool (HTTPClient on a worker thread,
## the game's transport) and through HTTPRequest with max_redirects = 0, and ApiPool must reuse the
## kept-alive connection after it. Needs the synthetic fixture with conditional polls on:
##   DRENOVAR_SERVER_ROOT=<server checkout> DRENOVAR_QA_CONDITIONAL=1 node godot/tools/qa-v6-1022-server.mjs
##   godot --headless --path godot/project -s qa_http_304.gd -- --server=http://127.0.0.1:8799

const ApiPool = preload("res://src/api_pool.gd")
var checks := 0
var failures: Array[String] = []
var base := "http://127.0.0.1:8799"

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_HTTP_304: " + detail)

func header(headers: PackedStringArray, name: String) -> String:
	for line in headers:
		var colon := line.find(":")
		if colon > 0 and line.substr(0, colon).strip_edges().to_lower() == name.to_lower():
			return line.substr(colon + 1).strip_edges()
	return ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			base = arg.trim_prefix("--server=").trim_suffix("/")
	call_deferred("run")

func run() -> void:
	var pool := ApiPool.new()
	root.add_child(pool)
	pool.configure(base)
	var common := PackedStringArray(["Accept: application/json", "Accept-Encoding: gzip", "X-Drenovar-Economy: DRENOVAR-V6-C1.0"])
	var created: Array = await pool.request(HTTPClient.METHOD_POST, "/api/session/new", common + PackedStringArray(["Content-Type: application/json", "Origin: " + base]), "{}", 10.0, 1 << 20)
	check(created[0] == HTTPRequest.RESULT_SUCCESS and int(created[1]) in [200, 201], "settlement ready (%d)" % int(created[1]))
	var opt := common + PackedStringArray(["X-Drenovar-Conditional: 1"])
	var first: Array = await pool.request(HTTPClient.METHOD_GET, "/api/native/game/state", opt, "", 10.0, 8 << 20)
	var tag := header(first[2], "ETag")
	check(int(first[1]) == 200 and not first[3].is_empty(), "tagged 200 with a body")
	check(not tag.is_empty() and tag.begins_with("W/\"v6s1."), "ETag present: " + tag)
	var reused_before := pool.requests_reused
	var started := Time.get_ticks_msec()
	var second: Array = await pool.request(HTTPClient.METHOD_GET, "/api/native/game/state", opt + PackedStringArray(["If-None-Match: " + tag]), "", 10.0, 8 << 20)
	var pool_ms := Time.get_ticks_msec() - started
	check(second[0] == HTTPRequest.RESULT_SUCCESS, "ApiPool 304 result SUCCESS (got %d)" % int(second[0]))
	check(int(second[1]) == 304, "ApiPool status 304 (got %d)" % int(second[1]))
	check(second[3].is_empty(), "ApiPool 304 body empty")
	check(pool_ms < 1500, "ApiPool 304 completes at once (%d ms)" % pool_ms)
	check(header(second[2], "ETag") == tag, "304 repeats the tag")
	check(not header(second[2], "X-Drenovar-Server-Time").is_empty(), "304 carries X-Drenovar-Server-Time")
	check(pool.requests_reused > reused_before, "keep-alive connection reused for the 304")
	# After the 304 the same pooled connection must still serve a full answer.
	var third: Array = await pool.request(HTTPClient.METHOD_GET, "/api/native/game/state", opt + PackedStringArray(["If-None-Match: " + tag]), "", 10.0, 8 << 20)
	check(third[0] == HTTPRequest.RESULT_SUCCESS and int(third[1]) in [200, 304], "connection usable after a 304 (%d)" % int(third[1]))
	var plain: Array = await pool.request(HTTPClient.METHOD_GET, "/api/native/game/state", common, "", 10.0, 8 << 20)
	check(int(plain[1]) == 200 and header(plain[2], "ETag").is_empty(), "no opt-in: full 200 without a tag")
	# HTTPRequest (Godot's high-level node) with max_redirects = 0.
	var node := HTTPRequest.new()
	node.max_redirects = 0
	node.timeout = 10.0
	root.add_child(node)
	started = Time.get_ticks_msec()
	node.request(base + "/api/native/game/state", opt + PackedStringArray(["If-None-Match: " + tag]))
	var done: Array = await node.request_completed
	var node_ms := Time.get_ticks_msec() - started
	check(done[0] == HTTPRequest.RESULT_SUCCESS, "HTTPRequest 304 result SUCCESS (got %d)" % int(done[0]))
	check(int(done[1]) in [304, 200], "HTTPRequest status 304/200 (got %d)" % int(done[1]))
	check(node_ms < 1500, "HTTPRequest 304 completes at once (%d ms)" % node_ms)
	node.queue_free()
	print("QA_HTTP_304 checks=%d failures=%d pool_304_ms=%d httprequest_ms=%d httprequest_code=%d connections_opened=%d reused=%d" % [checks, failures.size(), pool_ms, node_ms, int(done[1]), pool.connections_opened, pool.requests_reused])
	for failure in failures:
		print("  FAIL ", failure)
	quit(0 if failures.is_empty() else 1)
