extends SceneTree

# Settlement transfer from the old server to the new one, through the real client UI flow.
#   node ../tools/qa-transfer-realm.mjs <drenovar-server>   (old :8420, new :8421)
#   godot --path . -s qa_transfer.gd -- --server=http://127.0.0.1:8421 --hosted --old-server=http://127.0.0.1:8420

const SessionStore = preload("res://src/session_store.gd")
var checks := 0
var failures := 0
var game

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if condition:
		print("ok  ", description)
	else:
		failures += 1
		push_error(description)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func modal_has(text: String) -> bool:
	for node in game.modal_body.find_children("*", "", true, false):
		if (node is Label or node is Button) and node.text.contains(text):
			return true
	return false

func approve(challenge: String) -> int:
	# The player's Safari: the approval page of the old server, signed in to ChatGPT.
	var http := HTTPRequest.new()
	root.add_child(http)
	http.request(game.OLD_SERVER + "/__qa/approve?challenge=" + challenge)
	var result: Array = await http.request_completed
	http.queue_free()
	return int(result[1])

func run() -> void:
	SessionStore.forget()
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	check(await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage), 90.0), "Game scene loaded")
	check(not game.loopback and game.OLD_SERVER.ends_with(":8420"), "New server with a local old server")
	game.show_account()
	await game.begin_login()
	check(game.server_login == "device" and game.server_transfer, "Server reports device login with transfer")
	check(modal_has("Перенести поселение со старого сервера") and modal_has("Начать новое поселение"), "Choice: transfer or a new settlement")
	await game.begin_transfer()
	check(game.login_for_transfer and not game.login_proof.is_empty(), "Old-server login started for the transfer")
	var challenge: String = game.login_proof.sha256_text()
	check(game.login_url(challenge).begins_with(game.OLD_SERVER + "/api/native/approve?challenge="), "Approval page is on the OLD server")
	check(modal_has("Перенос поселения"), "Login screen explains the transfer")
	check(await approve(challenge) == 200, "Player approved on the old server")
	await game.finish_login(true)
	check(await wait_until(func(): return SessionStore.is_device(game.session) and not game.player_id.is_empty() and game.state.has("city"), 30.0), "Device account holds the transferred settlement")
	check(SessionStore.read_session() == game.session, "Device session saved on the phone")
	check(int(game.state.healthy.get("ENG-09", 0)) == 110 and int(game.state.healthy.get("ENG-01", 0)) == 90, "Soldiers moved: %s" % str(game.state.healthy))
	check(int(game.state.city.demo.wallet.get("iron", 0)) == 997700 and game.state.get("nickname") == "Ali", "Resources and nickname moved")
	check(game.message.text.contains("перенесено"), "Message: " + game.message.text)
	var level := 0
	for building in game.state.city.buildings:
		if building.type == "ECO-05":
			level = int(building.level)
	check(level == 2, "Town hall level moved: %d" % level)
	print("QA_TRANSFER checks=", checks, " failures=", failures, " player=", game.player_id)
	quit(0 if failures == 0 else 1)
