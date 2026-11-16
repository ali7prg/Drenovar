extends SceneTree
var game
func labels(node: Node) -> Array[String]:
	var values: Array[String]=[]
	if node is Label or node is Button:
		values.append(node.text)
	for child: Node in node.get_children():
		values.append_array(labels(child))
	return values
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	root.size=Vector2i(844,390)
	game=load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline:=Time.get_ticks_msec()+60000
	while not (is_instance_valid(game.modal_title) and game.modal_title.text=="Аккаунт" and game.modal.visible):
		if Time.get_ticks_msec()>deadline:
			push_error("PRIMARY_ACCOUNT_SCREEN_TIMEOUT")
			quit(1)
			return
		await process_frame
	var text:=labels(game.modal_body)
	assert(game.endpoint=="https://drenovar-game.ali069587.workers.dev")
	assert(text.has("Открыть основной город в браузере"))
	assert(text.has("Подключить устройство"))
	assert(not text.has("Создать тестовое поселение"))
	assert(not text.has("Основать поселение"))
	assert(not game.v6_panels.enabled())
	assert(game.api.requests_total==0)
	print("PRIMARY_ACCOUNT_SCREEN_OK 7; existing account connection, no free city, no network mutation")
	game.queue_free()
	await process_frame
	await process_frame
	quit()
