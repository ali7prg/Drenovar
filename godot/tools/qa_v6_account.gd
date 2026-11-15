extends SceneTree
# Real UI + HTTP. Uses a fresh private XDG_DATA_HOME and synthetic local/staging data.
var game
var checks := 0
var failures: Array[String] = []
func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures.append(label)
		push_error(label)
func wait_until(test: Callable, seconds := 60.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec() > end:
			return false
		await process_frame
	return true
func texts(node: Node) -> Array[String]:
	var result: Array[String] = []
	if node is Label or node is Button:
		result.append(node.text)
	for child: Node in node.get_children():
		result.append_array(texts(child))
	return result
func find_button(node: Node, title: String) -> Button:
	if node is Button and node.text == title:
		return node
	for child: Node in node.get_children():
		var found := find_button(child, title)
		if found != null:
			return found
	return null
func find_input(node: Node) -> LineEdit:
	if node is LineEdit:
		return node
	for child: Node in node.get_children():
		var found := find_input(child)
		if found != null:
			return found
	return null
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	root.size = Vector2i(844, 390)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	check(await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and is_instance_valid(game.modal_title) and not game.busy), "scene loaded")
	game.reset_session()
	await game.show_account()
	check(game.modal_title.text == "Аккаунт", "V6 account screen before login")
	check(find_button(game.modal_body, "Подключить веб-версию") == null, "old transfer button absent")
	check(find_button(game.modal_body, "Подключиться к тестовому миру") != null, "supported login available")
	await game.device_login()
	await game.show_account()
	check(not game.v6_panels.enabled(), "login does not create a free city")
	check(find_button(game.modal_body, "Создать тестовое поселение") != null, "empty account has explicit create action")
	var account: Dictionary = await game.request("account")
	check(account.get("profiles", []).is_empty(), "empty server account remains empty")
	check(not game.message.text.contains("Нет такого API"), "no unsupported API error on empty account")
	await game.create_settlement()
	check(game.v6_panels.enabled(), "create loads V6 city")
	var owner: String = game.session
	var player: String = game.player_id
	var pair: Dictionary = await game.send_request("pair/create", {})
	check(pair.has("code"), "existing city can pair")
	await game.sign_out()
	check(not game.connected(), "logout succeeds with supported V6 API")
	await game.device_login()
	await game.show_account()
	check(not game.v6_panels.enabled(), "second device still has no city")
	find_input(game.modal_body).text = str(pair.get("code", ""))
	find_button(game.modal_body, "Подключить тестовое поселение").pressed.emit()
	check(await wait_until(func(): return game.v6_panels.enabled() and not game.busy), "pair through real account button")
	check(game.player_id == player, "same account city after pairing")
	check(not game.message.text.contains("Нет такого API"), "no unsupported API error after pairing")
	await game.sign_out()
	game.session = owner
	await game.sync_account()
	check(game.player_id == player, "logout does not delete city or original account")
	print(JSON.stringify({"status":"passed" if failures.is_empty() else "failed", "checks":checks, "failures":failures, "device":"Godot Linux 844x390; not physical iPhone"}))
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if failures.is_empty() else 1)
