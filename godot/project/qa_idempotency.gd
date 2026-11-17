extends SceneTree

# A loopback TCP server records the Idempotency-Key of each command. It drops
# the first connections without answering (lost response), then answers a
# validation error. Retries of the same order must carry the same key; after a
# real server answer the next attempt must use a fresh key.

var failures: Array[String] = []
var checks := 0
var server := TCPServer.new()
var keys: Array[String] = []
var mode := "drop"
var served := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func serve_one() -> void:
	while not server.is_connection_available():
		await process_frame
	var peer := server.take_connection()
	var text := ""
	var deadline := Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < deadline:
		peer.poll()
		var available := peer.get_available_bytes()
		if available > 0:
			text += peer.get_utf8_string(available)
			var head_end := text.find("\r\n\r\n")
			if head_end >= 0:
				var length := 0
				for line in text.substr(0, head_end).split("\r\n"):
					if line.to_lower().begins_with("content-length:"):
						length = int(line.split(":")[1].strip_edges())
				if text.length() >= head_end + 4 + length:
					break
		await process_frame
	for line in text.split("\r\n"):
		if line.to_lower().begins_with("idempotency-key:"):
			keys.append(line.split(":")[1].strip_edges())
	if mode == "answer":
		var body := JSON.stringify({"error": "Недостаточно ресурсов"})
		peer.put_data(("HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % [body.to_utf8_buffer().size(), body]).to_utf8_buffer())
		await process_frame
	peer.disconnect_from_host()
	served += 1

func serve(count: int) -> void:
	for index in count:
		await serve_one()

func attempt(game: Node, order: Dictionary) -> Dictionary:
	# A lost response is retried twice inside command() with the same key.
	var requests := 3 if mode == "drop" else 1
	var expected := served + requests
	serve(requests)
	var outcome: bool = await game.command(order, func(): pass)
	while served < expected:
		await process_frame
	return {"ok": outcome, "status": game.modal_status.text}

func run() -> void:
	check(server.listen(0, "127.0.0.1") == OK, "Could not open loopback server")
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	game.diagnostics.path = "user://qa-idempotency-diagnostics.json"
	game.endpoint = "http://127.0.0.1:%d" % server.get_local_port()
	game.loopback = true
	game.player_id = "qa-idempotency"
	var order := {"kind": "trade", "resource": "wood", "amount": 100}
	mode = "drop"
	await attempt(game, order)
	await attempt(game, order)
	mode = "answer"
	await attempt(game, order)
	await attempt(game, order)
	var other := {"kind": "trade", "resource": "stone", "amount": 100}
	await attempt(game, other)
	check(keys.size() == 9, "Server saw %d requests" % keys.size())
	if keys.size() == 9:
		check(keys.slice(0, 7).all(func(k): return k == keys[0]), "Retries after lost responses changed the key")
		check(keys[7] != keys[6], "Key reused after the server answered")
		check(keys[8] != keys[7], "Different order reused a key")
	check(not game.busy and not game.command_in_progress, "Client stuck after failures")
	check(game.retry_keys.is_empty(), "Retry keys leaked after answers")
	server.stop()
	DirAccess.remove_absolute(game.diagnostics.path)
	print("QA_IDEMPOTENCY checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
