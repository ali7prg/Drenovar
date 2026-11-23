class_name ApiPool
extends Node

# Keep-alive HTTP(S) connections to the game server.
#
# HTTPRequest opens a new TCP connection and a new TLS handshake for every call,
# which adds two to three network round trips before the server even sees a
# command. Here each connection stays open between requests, so a tap on
# "Отправить", "Обучить" or "Улучшить" costs one round trip once the link is warm.
#
# A request runs on a worker thread (blocking poll loop, ~0.5 ms granularity) so
# frame time is unaffected. A connection is used by one request at a time; the
# pool opens another when all are busy. Results have the same shape as
# HTTPRequest.request_completed: [result, response_code, headers, body].
#
# 1023: a kept-alive connection can die without a word: the phone changed networks, a NAT
# forgot the flow while the app slept, iOS suspended the app. A request written into such a
# connection gets no answer and used to wait for its whole timeout (12 s for a poll), which
# showed «Нет связи · повторяем» and held back every poll meanwhile (a real-network run through
# a relay that kills open connections: one poll 12 006 ms, RESULT_TIMEOUT, then the pill).
# Now:
# - a connection is reused only if it is still open (polled first) and was idle for at most
#   IDLE_REUSE_USEC; `drop_idle()` (main.gd: the app comes back to the foreground) closes all;
# - a reused connection that sends nothing back within REUSED_ANSWER_USEC is taken for dead:
#   the request goes again at once on a fresh connection (same headers and Idempotency-Key,
#   within the same deadline), for every request whose own timeout is at most 15 s;
# - a wait that the device's suspension interrupted (the clock jumped while every thread slept)
#   does not count against the request's timeout.

signal _finished(id: int, outcome: Array)

const MAX_CONNECTIONS := 4
const POLL_USEC := 500
const IDLE_REUSE_USEC := 20000000
const REUSED_ANSWER_USEC := 3500000
const STALE_PROBE_MAX_TIMEOUT := 15.0
# A gap this long between two turns of a wait loop is a suspension (or a stall), not network time.
const SUSPEND_GAP_USEC := 1500000

class Cancellation extends RefCounted:
	var mutex := Mutex.new()
	var cancelled := false
	func cancel() -> void:
		mutex.lock()
		cancelled = true
		mutex.unlock()
	func is_cancelled() -> bool:
		mutex.lock()
		var value := cancelled
		mutex.unlock()
		return value

var host := ""
var port := 443
var tls := true
var current_target := ""
var idle: Array[HTTPClient] = []
var idle_since: Array[int] = []   # when each idle connection was returned (ticks usec)
var open_count := 0
var next_id := 0
var threads := {}
var shutting_down := false
# Statistics for the device report and QA.
var connections_opened := 0
var requests_reused := 0
var requests_total := 0
var peak_active := 0
var requests_cancelled := 0
var stale_dropped := 0     # idle connections closed unused (too old, or the app came back)
var fresh_retries := 0     # requests sent again on a fresh connection after a dead reused one
# The last requests (method, path without query, timing, outcome) for the device report and QA.
const TRACE_KEEP := 64
var trace: Array[Dictionary] = []
var trace_all := false   # QA: keep every request
# QA only: an HTTPS proxy and the CA it re-signs with (-- --qa-https-proxy=host:port
# --qa-ca-file=<pem>), for runs from a container whose traffic must go through one. A shipped
# app has no command line, so it never sets either.
var proxy_host := ""
var proxy_port := -1
var trusted_ca: X509Certificate = null

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-https-proxy="):
			var value := arg.trim_prefix("--qa-https-proxy=")
			proxy_host = value.get_slice(":", 0)
			proxy_port = int(value.get_slice(":", 1))
		elif arg.begins_with("--qa-ca-file="):
			trusted_ca = X509Certificate.new()
			if trusted_ca.load(arg.trim_prefix("--qa-ca-file=")) != OK:
				trusted_ca = null
		elif arg == "--qa-net-trace":
			trace_all = true

func configure(base_url: String) -> void:
	var url := base_url.strip_edges()
	tls = url.begins_with("https://")
	var rest := url.trim_prefix("https://").trim_prefix("http://")
	var slash := rest.find("/")
	if slash >= 0:
		rest = rest.substr(0, slash)
	var colon := rest.rfind(":")
	var next_port := port
	if colon > 0 and rest.substr(colon + 1).is_valid_int():
		next_port = int(rest.substr(colon + 1))
		rest = rest.substr(0, colon)
	else:
		next_port = 443 if tls else 80
	var target := "%s://%s:%d" % ["https" if tls else "http", rest, next_port]
	if target != current_target:
		# Pooled connections belong to the previous server.
		for client in idle:
			client.close()
		open_count -= idle.size()
		idle.clear()
		idle_since.clear()
		current_target = target
	host = rest
	port = next_port

func request(method: HTTPClient.Method, path: String, headers: PackedStringArray, body: String, timeout_seconds: float, body_limit: int, foreground := true, is_current := Callable()) -> Array:
	if host.is_empty() or shutting_down:
		return [HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray()]
	var deadline := Time.get_ticks_usec() + int(timeout_seconds * 1000000.0)
	# Bound active workers as well as idle sockets. Background polling/previews
	# leave one connection available for a user's command.
	var capacity := MAX_CONNECTIONS if foreground else MAX_CONNECTIONS - 1
	var waited_from := Time.get_ticks_usec()
	while threads.size() >= capacity:
		# A long frame or a suspension while waiting for a free connection is not network time.
		var tick := Time.get_ticks_usec()
		if tick - waited_from > SUSPEND_GAP_USEC:
			deadline += tick - waited_from
		waited_from = tick
		if shutting_down or Time.get_ticks_usec() >= deadline or (is_current.is_valid() and not is_current.call()):
			return [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray()]
		await get_tree().process_frame
		if Time.get_ticks_usec() - waited_from > SUSPEND_GAP_USEC:
			deadline += Time.get_ticks_usec() - waited_from
		waited_from = Time.get_ticks_usec()
	if is_current.is_valid() and not is_current.call():
		return [HTTPRequest.RESULT_REQUEST_FAILED, 0, PackedStringArray(), PackedByteArray()]
	var client := take_idle()
	var reused := client != null
	if client == null:
		client = HTTPClient.new()
		client.blocking_mode_enabled = false
		open_count += 1
	requests_total += 1
	if reused:
		requests_reused += 1
	next_id += 1
	var id := next_id
	var job := {
		"client": client, "reused": reused, "target": current_target, "host": host, "port": port, "tls": tls,
		"method": method, "path": path, "headers": headers, "body": body,
		"deadline": deadline, "limit": body_limit, "cancel": Cancellation.new(),
		"proxy_host": proxy_host, "proxy_port": proxy_port, "ca": trusted_ca,
		"stale_probe": timeout_seconds <= STALE_PROBE_MAX_TIMEOUT,
		# Written by the worker only (the keys exist before it starts; the main thread reads
		# nothing but "cancel" and "target" while it runs).
		"tick": 0, "answer_by": 0,
	}
	var started_ms := Time.get_ticks_msec()
	var thread := Thread.new()
	threads[id] = thread
	peak_active = maxi(peak_active, threads.size())
	var received := {"outcome": []}
	var completed := func(done_id: int, value: Array):
		if done_id == id: received.outcome = value
	_finished.connect(completed)
	thread.start(_run.bind(id, job))
	while received.outcome.is_empty():
		if is_current.is_valid() and not is_current.call():
			(job.cancel as Cancellation).cancel()
		await get_tree().process_frame
	_finished.disconnect(completed)
	var outcome: Array = received.outcome
	if (job.cancel as Cancellation).is_cancelled(): requests_cancelled += 1
	thread.wait_to_finish()
	threads.erase(id)
	var keep: bool = outcome[4] and job.target == current_target
	if keep and not shutting_down and idle.size() < MAX_CONNECTIONS:
		idle.append(client)
		idle_since.append(Time.get_ticks_usec())
	else:
		client.close()
		open_count -= 1
	if outcome[5]:
		connections_opened += 1
	if outcome[7]:
		fresh_retries += 1
	record(method, path, started_ms, reused, outcome)
	return outcome.slice(0, 4)

## The most recently used idle connection that is young enough to trust (LIFO: polls keep one warm).
## Older ones are closed: after 20 s of silence a mobile link may be gone without a word.
func take_idle() -> HTTPClient:
	var now := Time.get_ticks_usec()
	while not idle.is_empty():
		var client: HTTPClient = idle.pop_back()
		var since: int = idle_since.pop_back()
		if now - since <= IDLE_REUSE_USEC:
			return client
		client.close()
		open_count -= 1
		stale_dropped += 1
	return null

## Closes every idle connection (main.gd calls it when the app returns to the foreground: the
## network may have changed and iOS may have torn the sockets down while it was suspended).
func drop_idle() -> void:
	for client in idle:
		client.close()
	stale_dropped += idle.size()
	open_count -= idle.size()
	idle.clear()
	idle_since.clear()

func record(method: int, path: String, started_ms: int, reused: bool, outcome: Array) -> void:
	var entry := {"method": "GET" if method == HTTPClient.METHOD_GET else "POST", "path": path.get_slice("?", 0),
		"at": started_ms, "ms": Time.get_ticks_msec() - started_ms, "result": int(outcome[0]), "code": int(outcome[1]),
		"reused": reused, "opened": bool(outcome[5]), "fresh_retry": bool(outcome[7])}
	trace.append(entry)
	if not trace_all and trace.size() > TRACE_KEEP:
		trace.pop_front()

func _exit_tree() -> void:
	shutting_down = true
	for thread: Thread in threads.values():
		thread.wait_to_finish()
	threads.clear()
	for client in idle:
		client.close()
	idle.clear()
	idle_since.clear()

# --- worker thread -----------------------------------------------------------

func _run(id: int, job: Dictionary) -> void:
	job.tick = Time.get_ticks_usec()
	var outcome := _perform(job, job.reused)
	# A server may silently drop an idle keep-alive connection, and a phone's link can die under
	# it. When nothing at all came back on a reused connection (an error, or no answer within
	# REUSED_ANSWER_USEC), the request is sent again on a fresh one. Commands carry an
	# Idempotency-Key, so the server never applies one twice.
	var retried := false
	if job.reused and outcome[6] and not (job.cancel as Cancellation).is_cancelled() and not shutting_down:
		(job.client as HTTPClient).close()
		retried = true
		outcome = _perform(job, false)
	outcome.append(retried)
	_finished.emit.call_deferred(id, outcome)

## Called on every turn of a wait loop: a jump of the clock between two turns (the app was
## suspended with every thread, or the device starved this one) moves the deadline on by it.
func _timed_out(job: Dictionary) -> bool:
	var now := Time.get_ticks_usec()
	var gap: int = now - int(job.tick)
	if gap > SUSPEND_GAP_USEC:
		job.deadline = int(job.deadline) + gap
		if int(job.answer_by) > 0:
			job.answer_by = int(job.answer_by) + gap
	job.tick = now
	return now > int(job.deadline) or shutting_down or (job.cancel as Cancellation).is_cancelled()

# Returns [result, code, headers, body, keep_alive, opened_connection, nothing_received].
func _perform(job: Dictionary, reuse: bool) -> Array:
	var client: HTTPClient = job.client
	var opened := false
	if reuse:
		# Read what arrived while the connection was idle: a close (FIN, TLS close_notify, RST)
		# turns the status from CONNECTED, and the request opens a new connection instead.
		client.poll()
	var status := client.get_status()
	if not reuse or status != HTTPClient.STATUS_CONNECTED:
		client.close()
		var options: TLSOptions = (TLSOptions.client(job.ca) if job.ca != null else TLSOptions.client()) if job.tls else null
		if not String(job.proxy_host).is_empty() and job.tls:
			client.set_https_proxy(job.proxy_host, job.proxy_port)
		if client.connect_to_host(job.host, job.port, options) != OK:
			return [HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray(), false, false, false]
		opened = true
		while true:
			client.poll()
			status = client.get_status()
			if status == HTTPClient.STATUS_CONNECTED:
				break
			if status == HTTPClient.STATUS_CANT_RESOLVE:
				return [HTTPRequest.RESULT_CANT_RESOLVE, 0, PackedStringArray(), PackedByteArray(), false, opened, false]
			if status == HTTPClient.STATUS_CANT_CONNECT or status == HTTPClient.STATUS_CONNECTION_ERROR or status == HTTPClient.STATUS_DISCONNECTED:
				return [HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray(), false, opened, false]
			if status == HTTPClient.STATUS_TLS_HANDSHAKE_ERROR:
				return [HTTPRequest.RESULT_TLS_HANDSHAKE_ERROR, 0, PackedStringArray(), PackedByteArray(), false, opened, false]
			if _timed_out(job):
				return [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray(), false, opened, false]
			OS.delay_usec(POLL_USEC)
	if client.request(job.method, job.path, job.headers, job.body) != OK:
		return [HTTPRequest.RESULT_CONNECTION_ERROR, 0, PackedStringArray(), PackedByteArray(), false, opened, true]
	# On a reused connection, silence past REUSED_ANSWER_USEC means the link is dead.
	job.answer_by = Time.get_ticks_usec() + REUSED_ANSWER_USEC if not opened and job.stale_probe else 0
	while true:
		client.poll()
		status = client.get_status()
		if status == HTTPClient.STATUS_BODY or (status == HTTPClient.STATUS_CONNECTED and client.has_response()):
			break
		if status != HTTPClient.STATUS_REQUESTING:
			return [HTTPRequest.RESULT_CONNECTION_ERROR, 0, PackedStringArray(), PackedByteArray(), false, opened, true]
		if _timed_out(job):
			return [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray(), false, opened, false]
		if int(job.answer_by) > 0 and Time.get_ticks_usec() > int(job.answer_by):
			return [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray(), false, opened, true]
		OS.delay_usec(POLL_USEC)
	var code := client.get_response_code()
	var headers := client.get_response_headers()
	var keep := true
	for line in headers:
		var lower := line.to_lower()
		if lower.begins_with("connection:") and lower.contains("close"):
			keep = false
	# A 304 or 204 never has a body, whatever its headers say (RFC 9112 §6.3). HTTPClient reads one
	# when a Content-Length above 0 or Transfer-Encoding: chunked comes with it (an intermediary may
	# add either), and would wait for bytes that never come until the timeout. The answer is
	# complete here; a connection whose framing HTTPClient now misreads is not kept.
	if code == 304 or code == 204:
		if client.get_status() == HTTPClient.STATUS_BODY and client.get_response_body_length() == 0:
			client.read_response_body_chunk()   # Content-Length: 0: settles back to CONNECTED
		return [HTTPRequest.RESULT_SUCCESS, code, headers, PackedByteArray(), keep and client.get_status() == HTTPClient.STATUS_CONNECTED, opened, false]
	var body := PackedByteArray()
	while client.get_status() == HTTPClient.STATUS_BODY:
		client.poll()
		var chunk := client.read_response_body_chunk()
		if not chunk.is_empty():
			body.append_array(chunk)
			if body.size() > int(job.limit):
				return [HTTPRequest.RESULT_BODY_SIZE_LIMIT_EXCEEDED, code, headers, PackedByteArray(), false, opened, false]
		elif _timed_out(job):
			return [HTTPRequest.RESULT_TIMEOUT, code, headers, PackedByteArray(), false, opened, false]
		else:
			OS.delay_usec(POLL_USEC)
	status = client.get_status()
	if status != HTTPClient.STATUS_CONNECTED:
		# The server closed after the body (HTTP/1.0 style or Connection: close).
		keep = false
		if status != HTTPClient.STATUS_DISCONNECTED:
			return [HTTPRequest.RESULT_CONNECTION_ERROR, code, headers, body, false, opened, false]
	for line in headers:
		var lower := line.to_lower()
		if lower.begins_with("content-encoding:") and lower.contains("gzip"):
			body = body.decompress_dynamic(int(job.limit), FileAccess.COMPRESSION_GZIP)
			if body.is_empty():
				return [HTTPRequest.RESULT_BODY_DECOMPRESS_FAILED, code, headers, body, false, opened, false]
	return [HTTPRequest.RESULT_SUCCESS, code, headers, body, keep, opened, false]
