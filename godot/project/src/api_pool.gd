class_name ApiPool
extends Node

# Keep-alive HTTP(S) connections to the game server.
#
# HTTPRequest opens a new TCP connection and a new TLS handshake for every call,
# which adds two to three network round trips before the server even sees a
# command. Here each connection stays open between requests, so a tap on
# "Отправить", "Обучить" or "Улучшить" costs one round trip once the link is warm.
#
# A request runs on a worker thread (non-blocking poll loop, ~0.5 ms granularity) so
# frame time is unaffected. A connection is used by one request at a time; the
# pool opens another when all are busy. Results have the same shape as
# HTTPRequest.request_completed: [result, response_code, headers, body], plus (1024) the
# parsed JSON body as a fifth element when the caller asks for it (parsed on the worker thread:
# the 670 KB building catalogue took 14 ms to parse on the main thread here).
#
# 1023: a kept-alive connection can die without a word: the phone changed networks, a NAT
# forgot the flow while the app slept, iOS suspended the app. A request written into such a
# connection gets no answer and used to wait for its whole timeout (12 s for a poll), which
# showed «Нет связи · повторяем» and held back every poll meanwhile.
# - a connection is reused only if it is still open (polled first) and was idle for at most
#   IDLE_REUSE_USEC; `drop_idle()` (main.gd: the app comes back to the foreground) closes all;
# - a wait that the device's suspension interrupted (the clock jumped while every thread slept)
#   does not count against the request's timeout.
#
# 1024 (network chaos, qa_net_1024.gd): a second try runs BESIDE the first instead of replacing it
# ("hedging"): for every request whose own timeout is at most 15 s, when nothing at all has come
# back on a reused connection within REUSED_ANSWER_USEC, or on a fresh one within FRESH_ANSWER_USEC,
# the same request (same headers and Idempotency-Key, same deadline) goes once more on a new
# connection, and the first complete answer wins (the other connection is closed). A flow that died
# in a cellular handoff costs those seconds, not the 12 s timeout, and a server that is merely slow
# still answers on the first connection. The same second try starts at once:
# - when a reused connection fails before any answer (it was closed under it);
# - when the app comes back from the background (`hedge_in_flight()`, main.gd on_app_resumed) or the
#   worker sees the clock jump (the device suspended it): the flows of a suspended app are usually dead.
# Commands carry an Idempotency-Key, so the server applies one at most once whichever try it sees.
# When the second try wins over a reused connection, every other idle connection is closed as well
# (they went through the same, now changed, network).
# `link_usec` is the last moment the network itself was seen working (a connection opened, a byte of
# an answer arrived), so main.gd can tell a slow server from a lost network.

signal _finished(id: int, outcome: Array)

const MAX_CONNECTIONS := 4
const POLL_USEC := 500
const IDLE_REUSE_USEC := 20000000
const REUSED_ANSWER_USEC := 3500000
const FRESH_ANSWER_USEC := 5000000
const STALE_PROBE_MAX_TIMEOUT := 15.0
# A gap this long between two turns of a wait loop is a suspension (or a stall), not network time.
const SUSPEND_GAP_USEC := 1500000

## The main thread's handle on a running request: cancel it, or ask for a second try at once.
class Cancellation extends RefCounted:
	var mutex := Mutex.new()
	var cancelled := false
	var hedge := false
	func cancel() -> void:
		mutex.lock()
		cancelled = true
		mutex.unlock()
	func is_cancelled() -> bool:
		mutex.lock()
		var value := cancelled
		mutex.unlock()
		return value
	func request_hedge() -> void:
		mutex.lock()
		hedge = true
		mutex.unlock()
	func hedge_requested() -> bool:
		mutex.lock()
		var value := hedge
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
var jobs := {}   # id -> job of every request in flight (main thread only)
var shutting_down := false
# Statistics for the device report and QA.
var connections_opened := 0
var requests_reused := 0
var requests_total := 0
var peak_active := 0
var requests_cancelled := 0
var stale_dropped := 0     # idle connections closed unused (too old, or the app came back)
var fresh_retries := 0     # requests that needed a second try on a fresh connection (1024: a hedge)
var hedge_wins := 0        # ... and the second try answered first
# The network seen working (written by the workers, read by main.gd): ticks usec, 0 = never.
var link_mutex := Mutex.new()
var link_usec := 0
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

## parse_json (1024): the body is parsed as JSON on the worker thread; the parsed value (or null when
## the body is not JSON) is the fifth element of the result.
func request(method: HTTPClient.Method, path: String, headers: PackedStringArray, body: String, timeout_seconds: float, body_limit: int, foreground := true, is_current := Callable(), parse_json := false) -> Array:
	if host.is_empty() or shutting_down:
		return [HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray(), null]
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
			return [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray(), null]
		await get_tree().process_frame
		if Time.get_ticks_usec() - waited_from > SUSPEND_GAP_USEC:
			deadline += Time.get_ticks_usec() - waited_from
		waited_from = Time.get_ticks_usec()
	if is_current.is_valid() and not is_current.call():
		return [HTTPRequest.RESULT_REQUEST_FAILED, 0, PackedStringArray(), PackedByteArray(), null]
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
		"stale_probe": timeout_seconds <= STALE_PROBE_MAX_TIMEOUT, "parse_json": parse_json, "started_ms": Time.get_ticks_msec(),
		# Written by the worker only (the keys exist before it starts; the main thread reads
		# nothing but "cancel" and "target" while it runs).
		"tick": 0,
	}
	var started_ms := Time.get_ticks_msec()
	var thread := Thread.new()
	threads[id] = thread
	jobs[id] = job
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
	jobs.erase(id)
	# outcome: [result, code, headers, body, keep_alive, opened_connection, nothing_received,
	#           hedged, connection to keep (the winner's, or null), parsed JSON]
	var winner: HTTPClient = outcome[8]
	# A reused flow found dead (the second try answered instead): the other idle flows went through the
	# same network and are most likely dead too (a handoff kills them all), so none of them is trusted.
	if outcome[7] and reused and winner != client:
		drop_idle()
	var keep: bool = outcome[4] and winner != null and job.target == current_target
	if keep and not shutting_down and idle.size() < MAX_CONNECTIONS:
		idle.append(winner)
		idle_since.append(Time.get_ticks_usec())
	else:
		if winner != null:
			winner.close()
		open_count -= 1
	if outcome[5]:
		connections_opened += 1
	if outcome[7]:
		fresh_retries += 1
		if winner != null and winner != client:
			hedge_wins += 1
	record(method, path, started_ms, reused, outcome)
	return [outcome[0], outcome[1], outcome[2], outcome[3], outcome[9]]

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

## 1024: every request in flight tries once more on a fresh connection now, beside its first try
## (main.gd: the app came back from the background, when the flows it had are usually dead).
func hedge_in_flight() -> int:
	for id in jobs:
		(jobs[id].cancel as Cancellation).request_hedge()
	return jobs.size()

## Microseconds since the network was last seen working (a connection opened or an answer arrived);
## -1 when it never was.
func link_age_usec() -> int:
	link_mutex.lock()
	var at := link_usec
	link_mutex.unlock()
	return -1 if at == 0 else Time.get_ticks_usec() - at

func note_link() -> void:
	link_mutex.lock()
	link_usec = Time.get_ticks_usec()
	link_mutex.unlock()

func record(method: int, path: String, started_ms: int, reused: bool, outcome: Array) -> void:
	var entry := {"method": "GET" if method == HTTPClient.METHOD_GET else "POST", "path": path.get_slice("?", 0),
		"at": started_ms, "ms": Time.get_ticks_msec() - started_ms, "result": int(outcome[0]), "code": int(outcome[1]),
		"reused": reused, "opened": bool(outcome[5]), "fresh_retry": bool(outcome[7]), "bytes": (outcome[3] as PackedByteArray).size()}
	trace.append(entry)
	if not trace_all and trace.size() > TRACE_KEEP:
		trace.pop_front()

func _exit_tree() -> void:
	shutting_down = true
	for thread: Thread in threads.values():
		thread.wait_to_finish()
	threads.clear()
	jobs.clear()
	for client in idle:
		client.close()
	idle.clear()
	idle_since.clear()

# --- worker thread -----------------------------------------------------------

## One try of a request on one connection, stepped by the worker without blocking, so that two tries of
## the same request can run side by side (1024).
class Attempt extends RefCounted:
	enum {START, CONNECTING, SEND, WAIT, BODY, DONE}
	var pool: ApiPool
	var client: HTTPClient
	var reuse := false
	var opened := false
	var phase := START
	# [result, code, headers, body, keep_alive, opened_connection, nothing_received] once DONE.
	var outcome: Array = []
	var code := 0
	var headers := PackedStringArray()
	var body := PackedByteArray()
	var answered := false   # the status line and headers of an answer arrived

	func _init(owner: ApiPool, connection: HTTPClient, reused: bool) -> void:
		pool = owner
		client = connection
		reuse = reused

	func finish(result: int, keep: bool, nothing_received: bool) -> void:
		outcome = [result, code, headers, body if result == HTTPRequest.RESULT_SUCCESS else PackedByteArray(), keep, opened, nothing_received]
		phase = DONE

	func succeeded() -> bool:
		return phase == DONE and int(outcome[0]) == HTTPRequest.RESULT_SUCCESS

	## One turn: polls the connection once and moves on as far as it can without waiting.
	func step(job: Dictionary) -> void:
		match phase:
			START:
				if reuse:
					# Read what arrived while the connection was idle: a close (FIN, TLS close_notify, RST)
					# turns the status from CONNECTED, and the request opens a new connection instead.
					client.poll()
				if not reuse or client.get_status() != HTTPClient.STATUS_CONNECTED:
					reuse = false
					client.close()
					var options: TLSOptions = (TLSOptions.client(job.ca) if job.ca != null else TLSOptions.client()) if job.tls else null
					if not String(job.proxy_host).is_empty() and job.tls:
						client.set_https_proxy(job.proxy_host, job.proxy_port)
					if client.connect_to_host(job.host, job.port, options) != OK:
						finish(HTTPRequest.RESULT_CANT_CONNECT, false, false)
						return
					opened = true
					phase = CONNECTING
				else:
					phase = SEND
					step(job)
			CONNECTING:
				client.poll()
				var status := client.get_status()
				if status == HTTPClient.STATUS_CONNECTED:
					pool.note_link()
					phase = SEND
					step(job)
				elif status == HTTPClient.STATUS_CANT_RESOLVE:
					finish(HTTPRequest.RESULT_CANT_RESOLVE, false, false)
				elif status == HTTPClient.STATUS_CANT_CONNECT or status == HTTPClient.STATUS_CONNECTION_ERROR or status == HTTPClient.STATUS_DISCONNECTED:
					finish(HTTPRequest.RESULT_CANT_CONNECT, false, false)
				elif status == HTTPClient.STATUS_TLS_HANDSHAKE_ERROR:
					finish(HTTPRequest.RESULT_TLS_HANDSHAKE_ERROR, false, false)
			SEND:
				if client.request(job.method, job.path, job.headers, job.body) != OK:
					finish(HTTPRequest.RESULT_CONNECTION_ERROR, false, true)
					return
				phase = WAIT
			WAIT:
				client.poll()
				var status := client.get_status()
				if status == HTTPClient.STATUS_BODY or (status == HTTPClient.STATUS_CONNECTED and client.has_response()):
					answered = true
					pool.note_link()
					code = client.get_response_code()
					headers = client.get_response_headers()
					# A 304 or 204 never has a body, whatever its headers say (RFC 9112 §6.3). HTTPClient reads
					# one when a Content-Length above 0 or Transfer-Encoding: chunked comes with it (an
					# intermediary may add either), and would wait for bytes that never come until the timeout.
					# The answer is complete here; a connection whose framing HTTPClient now misreads is not kept.
					if code == 304 or code == 204:
						if client.get_status() == HTTPClient.STATUS_BODY and client.get_response_body_length() == 0:
							client.read_response_body_chunk()   # Content-Length: 0: settles back to CONNECTED
						finish(HTTPRequest.RESULT_SUCCESS, closes_after() == false and client.get_status() == HTTPClient.STATUS_CONNECTED, false)
						return
					phase = BODY
					step(job)
				elif status != HTTPClient.STATUS_REQUESTING:
					finish(HTTPRequest.RESULT_CONNECTION_ERROR, false, true)
			BODY:
				while client.get_status() == HTTPClient.STATUS_BODY:
					client.poll()
					var chunk := client.read_response_body_chunk()
					if chunk.is_empty():
						return   # more next turn
					body.append_array(chunk)
					if body.size() > int(job.limit):
						finish(HTTPRequest.RESULT_BODY_SIZE_LIMIT_EXCEEDED, false, false)
						return
				var keep := not closes_after()
				var status := client.get_status()
				if status != HTTPClient.STATUS_CONNECTED:
					# The server closed after the body (HTTP/1.0 style or Connection: close).
					keep = false
					if status != HTTPClient.STATUS_DISCONNECTED:
						finish(HTTPRequest.RESULT_CONNECTION_ERROR, false, false)
						return
				for line in headers:
					var lower := line.to_lower()
					if lower.begins_with("content-encoding:") and lower.contains("gzip"):
						body = body.decompress_dynamic(int(job.limit), FileAccess.COMPRESSION_GZIP)
						if body.is_empty():
							finish(HTTPRequest.RESULT_BODY_DECOMPRESS_FAILED, false, false)
							return
				finish(HTTPRequest.RESULT_SUCCESS, keep, false)

	func closes_after() -> bool:
		for line in headers:
			var lower := line.to_lower()
			if lower.begins_with("connection:") and lower.contains("close"):
				return true
		return false

func _run(id: int, job: Dictionary) -> void:
	job.tick = Time.get_ticks_usec()
	var control: Cancellation = job.cancel
	var tries: Array[Attempt] = [Attempt.new(self, job.client, job.reused)]
	var hedged := false
	# Silence this long (no status line of an answer yet) brings in the second try; only requests
	# with a short timeout of their own (polls, commands), never the long catalogue and quote reads.
	var hedge_at := 0
	if job.stale_probe:
		hedge_at = int(job.tick) + (REUSED_ANSWER_USEC if job.reused else FRESH_ANSWER_USEC)
	var winner: Attempt = null
	var outcome: Array = []
	while true:
		var all_done := true
		for attempt in tries:
			if attempt.phase != Attempt.DONE:
				attempt.step(job)
			if attempt.succeeded():
				winner = attempt
				break
			if attempt.phase != Attempt.DONE:
				all_done = false
		if winner != null:
			outcome = winner.outcome
			break
		var stop := shutting_down or control.is_cancelled()
		var gap := Time.get_ticks_usec() - int(job.tick)
		if _timed_out(job):
			outcome = [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray(), false, tries.any(func(a): return a.opened), false]
			# An HTTP status that did arrive is kept (a body cut by the deadline still proves the server answered).
			for attempt in tries:
				if attempt.answered:
					outcome[1] = attempt.code
					outcome[2] = attempt.headers
			break
		if all_done:
			# Every try ended without an answer. A reused connection that was closed under the request
			# (nothing came back) gets its second try at once; otherwise the first failure is the result.
			var first: Attempt = tries[0]
			if not hedged and first.reuse and bool(first.outcome[6]) and not stop:
				hedged = true
				first.client.close()
				tries.append(Attempt.new(self, _fresh_client(), false))
				continue
			outcome = tries[tries.size() - 1].outcome
			for attempt in tries:
				if int(attempt.outcome[1]) > 0:
					outcome = attempt.outcome   # an HTTP error page beats a transport failure
			break
		# The second try beside the first: silence past hedge_at, the app came back from the background,
		# or the worker itself was suspended (the clock jumped).
		if not hedged and not stop and not tries[0].answered and (
				(hedge_at > 0 and Time.get_ticks_usec() > hedge_at) or control.hedge_requested() or gap > SUSPEND_GAP_USEC):
			hedged = true
			tries.append(Attempt.new(self, _fresh_client(), false))
			continue
		OS.delay_usec(POLL_USEC)
	# Close every connection but the winner's.
	var keep_client: HTTPClient = winner.client if winner != null else null
	for attempt in tries:
		if attempt.client != keep_client:
			attempt.client.close()
	if keep_client == null:
		keep_client = job.client   # closed above; main.gd closes it again and counts it
	var result := outcome.duplicate()
	result[5] = tries.any(func(a): return a.opened)
	result.append(hedged)
	result.append(keep_client if winner != null else null)
	var parsed: Variant = null
	if job.parse_json and int(result[0]) == HTTPRequest.RESULT_SUCCESS and not (result[3] as PackedByteArray).is_empty():
		var json := JSON.new()
		if json.parse((result[3] as PackedByteArray).get_string_from_utf8()) == OK:
			parsed = json.data
	result.append(parsed)
	_finished.emit.call_deferred(id, result)

func _fresh_client() -> HTTPClient:
	var client := HTTPClient.new()
	client.blocking_mode_enabled = false
	return client

## Called on every turn of a wait loop: a jump of the clock between two turns (the app was
## suspended with every thread, or the device starved this one) moves the deadline on by it.
func _timed_out(job: Dictionary) -> bool:
	var now := Time.get_ticks_usec()
	var gap: int = now - int(job.tick)
	if gap > SUSPEND_GAP_USEC:
		job.deadline = int(job.deadline) + gap
	job.tick = now
	return now > int(job.deadline) or shutting_down or (job.cancel as Cancellation).is_cancelled()
