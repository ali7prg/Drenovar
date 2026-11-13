extends SceneTree

# Moving a building against the patched server (server-patches/move-building-v1 on
# a copy of v92, test realm, in memory). Run with: -- --server=http://127.0.0.1:8417
#  - the server reports cityFeatures: moveBuilding;
#  - "Переместить" in the ring of a building starts placement with free cleared plots;
#  - one confirmation moves the building on the server: same id and level, nothing
#    charged, drawn on the new plot;
#  - without the server feature the button stays off with an explanation.

var checks := 0
var failures := 0
var game

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
	else:
		print("ok  ", description)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func set_clock(value: float) -> void:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + "/test/clock?time=" + str(int(value)), [], HTTPClient.METHOD_POST)
	await client.request_completed
	client.queue_free()

func fresh_state() -> void:
	game.accept(await game.request("state"))

func building_of(type: String) -> Dictionary:
	for building in game.state.city.buildings:
		if building.type == type:
			return building
	return {}

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var connected_ok: bool = await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.player_id.is_empty(), 60.0)
	check(connected_ok, "Connected to the patched local server")
	if not connected_ok:
		quit(1)
		return
	await fresh_state()
	check(game.move_supported(), "Server reports cityFeatures moveBuilding")
	# A cleared free plot to move onto.
	check(await game.command({"kind": "kingdom", "action": "clear", "plotId": "v1-4"}), "Plot v1-4 clearing ordered")
	var order: Dictionary = game.construction_order()
	await set_clock(float(order.get("endsAt", game.state.serverTime)) + 50.0)
	await fresh_state()
	check("v1-4" in game.state.city.kingdom.clearedPlots, "Plot v1-4 cleared")
	var lumber := building_of("RES-01")
	var marker: Dictionary = {}
	for item in game.stage.place_markers:
		if item.get("id") == lumber.id:
			marker = item
	game.open_building_ring(marker)
	var captions: Array = game.action_ring.buttons.map(func(b): return b.tooltip_text)
	check("Переместить" in captions, "Ring of the lumber camp offers Переместить")
	game.action_ring.close()
	var wallet: String = JSON.stringify(game.state.city.demo.wallet)
	game.start_move(lumber)
	check(not game.placing.is_empty() and game.placing.has("move"), "Move placement started")
	check(game.placing.plots.all(func(p): return p.cleared), "Only cleared plots are offered")
	var target: Dictionary = {}
	for entry in game.placing.plots:
		if entry.plot.id == "v1-4":
			target = entry
	check(not target.is_empty(), "Plot v1-4 is offered")
	game.placing.free = target.position
	game.placing.position = target.position
	game.placing.plot = target.plot
	game.refresh_placement()
	check(not game.placement_confirm.disabled and game.placement_confirm.text == "Переместить", "Confirm enabled on a free plot")
	game.confirm_placement()
	var moved_ok: bool = await wait_until(func(): return building_of("RES-01").get("plotId", "") == "v1-4", 10.0)
	check(moved_ok, "Server moved the lumber camp to v1-4")
	var after := building_of("RES-01")
	check(after.id == lumber.id and int(after.level) == int(lumber.level), "Same id and level after the move")
	check(JSON.stringify(game.state.city.demo.wallet) == wallet, "Nothing charged for the move")
	var drawn := false
	for item in game.stage.place_markers:
		if item.get("id") == lumber.id:
			drawn = Vector2(item.position.x, item.position.z).distance_to(Vector2(target.position.x, target.position.z)) < 0.5
	check(drawn, "Lumber camp drawn on the new plot")
	# Without the server feature the move stays off and says why.
	game.state.erase("cityFeatures")
	game.start_move(after)
	check(game.placement_confirm.disabled and game.placement_info.text.contains("обновления сервера"), "Without the feature: confirm off with an explanation")
	game.cancel_placement()
	print("checks=%d failures=%d" % [checks, failures])
	quit(1 if failures > 0 else 0)
