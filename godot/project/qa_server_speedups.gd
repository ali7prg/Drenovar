extends SceneTree

# Speedups against the patched server (server-patches/speedups-v2 on a copy of v92,
# test realm started with DRENOVAR_TEST_SPEEDUP_GRANTS=1, isolated, in memory).
# Run with: -- --server=http://127.0.0.1:8417
#  - the server's catalogue enables the new tiers and march items in the window;
#  - the starter kit arrives from the server (not from the client);
#  - march: preview, one press → one item, arrival earlier by the item, return later
#    keeps its own duration; a battle cannot be sped up.

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

func labels() -> String:
	return " | ".join(game.modal_body.find_children("*", "Label", true, false).map(func(l): return l.text))

func army_by_id(id: String) -> Dictionary:
	for army in game.state.get("armies", []):
		if army.id == id:
			return army
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
	check(game.server_speed_items("march").size() == 8, "Server catalogue enables 8 march items")
	check(game.server_speed_items("construction").size() == 8, "Server catalogue enables 8 construction items")
	check(int(game.state.items.get("march-1", 0)) == 3, "Starter kit from the server: march-1 ×%d" % int(game.state.items.get("march-1", 0)))
	# Soldiers for a march.
	var barracks: Dictionary = game.state.city.buildings.filter(func(b): return b.type == "MIL-01")[0]
	await game.command({"kind": "train", "buildingId": barracks.id, "unitId": "ENG-09", "quantity": 10, "paidTraining": true, "requestId": "qa-sp-%d" % Time.get_ticks_msec()})
	var queue: Array = game.state.city.military.queues[barracks.id]
	await set_clock(float(queue[-1].endsAt))
	await fresh_state()
	var target: Dictionary = game.state.encounters.filter(func(e): return int(e.level) == 1)[0]
	var sent: bool = await game.command({"kind": "deploy", "encounterId": target.id, "units": {"ENG-09": 10}})
	check(sent, "Army sent: " + game.message.text)
	var army: Dictionary = game.state.armies[-1]
	await set_clock(float(army.startsAt) + 500.0)
	await fresh_state()
	army = army_by_id(army.id)
	var travel := float(army.travelMs)
	var arrives := float(army.arrivesAt)
	game.show_armies()
	var entry: Array = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text == "Ускорить марш")
	check(entry.size() == 1, "Garrison offers a march speedup")
	entry[0].pressed.emit()
	var usable: Array = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return "в наличии" in b.text and not b.disabled)
	check(usable.size() == 1 and usable[0].text == "1 мин · в наличии 3", "Only the owned march item is usable: %s" % [usable.map(func(b): return b.text)])
	usable[0].pressed.emit()
	check(game.modal_title.text == "Применить ускоритель?" and "→" in labels(), "Preview before spending: " + labels())
	var apply: Button = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text == "Применить")[0]
	apply.pressed.emit()
	apply.pressed.emit()
	await wait_until(func(): return not game.speedup_in_flight and not game.command_in_progress, 15.0)
	await fresh_state()
	var after := army_by_id(army.id)
	var shift := minf(60000.0, arrives - (float(army.startsAt) + 500.0) - 1.0)
	check(int(game.state.items.get("march-1", 0)) == 2, "Double press spent one item (%d left)" % int(game.state.items.get("march-1", 0)))
	check(is_equal_approx(float(after.arrivesAt), arrives - shift), "Arrival earlier by %.0f ms once" % (arrives - float(after.arrivesAt)))
	# Battle cannot be sped up; the return keeps its own duration.
	await set_clock(float(after.arrivesAt))
	await fresh_state()
	after = army_by_id(army.id)
	check(after.status == "fighting", "Army fighting at the new arrival time")
	game.inspect_army(after)
	check(game.modal_body.find_children("*", "Button", true, false).all(func(b): return b.text != "Ускорить марш"), "No speedup offered during the battle")
	await set_clock(float(after.battleEndsAt))
	await fresh_state()
	after = army_by_id(army.id)
	check(after.status == "returning" and is_equal_approx(float(after.returnsAt) - float(after.returnStartsAt), travel), "Return keeps the original walk time")
	print("QA_SERVER_SPEEDUPS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
