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

signal _finished(id: int, outcome: Array)

const MAX_CONNECTIONS := 4
const POLL_USEC := 500

var host := ""
var port := 443
var tls := true
var current_target := ""
var idle: Array[HTTPClient] = []
var open_count := 0
var next_id := 0
var threads := {}
var shutting_down := false
# Statistics for the device report and QA.
var connections_opened := 0
var requests_reused := 0
var requests_total := 0

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
		current_target = target
	host = rest
	port = next_port

func request(method: HTTPClient.Method, path: String, headers: PackedStringArray, body: String, timeout_seconds: float, body_limit: int) -> Array:
	if host.is_empty() or shutting_down:
		return [HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray()]
	var client: HTTPClient = idle.pop_back() if not idle.is_empty() else null
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
		"deadline": Time.get_ticks_usec() + int(timeout_seconds * 1000000.0), "limit": body_limit,
	}
	var thread := Thread.new()
	threads[id] = thread
	thread.start(_run.bind(id, job))
	var outcome: Array = []
	while true:
		var done: Array = await _finished
		if done[0] == id:
			outcome = done[1]
			break
	thread.wait_to_finish()
	threads.erase(id)
	var keep: bool = outcome[4] and job.target == current_target
	if keep and not shutting_down and idle.size() < MAX_CONNECTIONS:
		idle.append(client)
	else:
		client.close()
		open_count -= 1
	if outcome[5]:
		connections_opened += 1
	return outcome.slice(0, 4)

func _exit_tree() -> void:
	shutting_down = true
	for thread: Thread in threads.values():
		thread.wait_to_finish()
	threads.clear()
	for client in idle:
		client.close()
	idle.clear()

# --- worker thread -----------------------------------------------------------

func _run(id: int, job: Dictionary) -> void:
	var outcome := _perform(job, job.reused)
	# A server may silently drop an idle keep-alive connection. When nothing at all
	# came back on a reused connection, the request is sent again on a fresh one.
	# Commands carry an Idempotency-Key, so the server never applies one twice.
	if job.reused and outcome[6]:
		(job.client as HTTPClient).close()
		outcome = _perform(job, false)
	_finished.emit.call_deferred(id, outcome)

func _timed_out(job: Dictionary) -> bool:
	return Time.get_ticks_usec() > int(job.deadline) or shutting_down

# Returns [result, code, headers, body, keep_alive, opened_connection, nothing_received].
func _perform(job: Dictionary, reuse: bool) -> Array:
	var client: HTTPClient = job.client
	var opened := false
	var status := client.get_status()
	if not reuse or status != HTTPClient.STATUS_CONNECTED:
		client.close()
		var options: TLSOptions = TLSOptions.client() if job.tls else null
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
	while true:
		client.poll()
		status = client.get_status()
		if status == HTTPClient.STATUS_BODY or (status == HTTPClient.STATUS_CONNECTED and client.has_response()):
			break
		if status != HTTPClient.STATUS_REQUESTING:
			return [HTTPRequest.RESULT_CONNECTION_ERROR, 0, PackedStringArray(), PackedByteArray(), false, opened, true]
		if _timed_out(job):
			return [HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray(), false, opened, false]
		OS.delay_usec(POLL_USEC)
	var code := client.get_response_code()
	var headers := client.get_response_headers()
	var keep := true
	for line in headers:
		var lower := line.to_lower()
		if lower.begins_with("connection:") and lower.contains("close"):
			keep = false
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
