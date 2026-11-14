extends SceneTree

# Speedups (client side, no server):
# - only the server catalogue (construction/training, 1, 5, 15, 60 min) is usable,
#   with the count from the server inventory; tiers the server does not know and
#   every march item are listed as unavailable with the reason;
# - a preview shows how much the remaining time shrinks before anything is spent;
# - one press sends one order: the button locks, a second press does nothing;
# - the action ring of a training building offers "Ускорить" while it trains.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func texts(game) -> Array:
	return game.modal_body.find_children("*", "Button", true, false).map(func(b): return b.text)

func labels(game) -> String:
	return " | ".join(game.modal_body.find_children("*", "Label", true, false).map(func(l): return l.text))

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.endpoint = "http://127.0.0.1:9"
	game.player_id = "qa-speed"
	check(game.server_speed_items("construction") == ["construction-1", "construction-2", "construction-3", "construction-4"], "Construction catalogue differs from server v92")
	check(game.server_speed_items("march").is_empty(), "March items offered although the server has none")
	# Owned 5 min construction item: usable, others listed with count 0 (disabled).
	game.state.items = {"construction-2": 2}
	var order := {"kind": "upgrade", "requestId": "req-1", "endsAt": game.timer_now() + 3.0 * 60000.0}
	game.show_speedups("construction", order, "")
	var list: Array = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return "в наличии" in b.text)
	check(list.size() == 4, "Four server items listed: %d" % list.size())
	var enabled: Array = list.filter(func(b): return not b.disabled)
	check(enabled.size() == 1 and enabled[0].text == "5 мин · в наличии 2", "Only the owned item is usable: %s" % [enabled.map(func(b): return b.text)])
	check("30 мин, 2 ч, 5 ч, 10 ч" in labels(game) and "обновления сервера" in labels(game), "Unsupported tiers not explained: " + labels(game))
	# Preview: 3:00 left, 5 min item -> finishes at once, 2:00 would be lost.
	enabled[0].pressed.emit()
	check(game.modal_title.text == "Применить ускоритель?", "No preview before spending")
	check("завершится сразу" in labels(game) and "пропадут" in labels(game), "Preview does not show the result: " + labels(game))
	var apply: Button = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text == "Применить")[0]
	# Double press: exactly one command.
	var sent := [0]
	var before: int = game.api.requests_total
	apply.pressed.emit()
	apply.pressed.emit()
	await process_frame
	# The window closes at once (build 51: the speedup works on the tap); a button
	# still on screen must be locked.
	check(not is_instance_valid(apply) or apply.disabled, "Apply button not locked while sending")
	check(not game.modal.visible, "Speedup window still open after the tap")
	while game.command_in_progress or game.speedup_in_flight:
		await process_frame
	sent[0] = game.api.requests_total - before
	# command() retries a lost answer twice with the same key: 1 order = up to 3 requests.
	check(sent[0] >= 1 and sent[0] <= 3, "Requests for one press: %d" % sent[0])
	var keys: Array = game.retry_keys.values()
	check(keys.size() == 1, "A failed speedup must keep one idempotency key for a retry: %d" % keys.size())
	# Preview for a longer order: 20:00 left, 5 min -> 15:00.
	order.endsAt = game.timer_now() + 20.0 * 60000.0 + 500.0
	game.preview_speedup("construction", order, "", "construction-2")
	check("20:01 → станет 15:01" in labels(game) or "20:00 → станет 15:00" in labels(game), "Preview of the remaining time: " + labels(game))
	# March: nothing usable, explained.
	var army := {"id": "army-q", "name": "Отряд", "status": "outbound", "owner": "qa-speed",
		"startsAt": game.timer_now(), "arrivesAt": game.timer_now() + 600000.0, "units": {}}
	game.state.armies = [army]
	game.show_armies()
	var march: Array = game.modal_body.find_children("*", "Button", true, false).filter(func(b): return b.text == "Ускорить марш")
	check(march.size() == 1, "No march speedup entry in the garrison")
	if not march.is_empty():
		march[0].pressed.emit()
	check(game.modal_body.find_children("*", "Button", true, false).all(func(b): return not "в наличии" in b.text), "March offers an item to use")
	check("обновления сервера" in labels(game), "March speedup not explained: " + labels(game))
	game.state.armies = []
	# Ring of a training building with a running order offers "Ускорить".
	var barracks: Array = game.state.city.buildings.filter(func(b): return b.type == "MIL-01")
	check(not barracks.is_empty(), "No barracks in the demo city")
	if not barracks.is_empty():
		var b: Dictionary = barracks[0]
		game.state.city.military.queues[b.id] = [{"id": "ord-1", "unitId": "ENG-09", "quantity": 2, "startsAt": game.timer_now() - 1000.0, "endsAt": game.timer_now() + 60000.0}]
		game.close_modal()
		var captured := []
		var ring = game.action_ring
		var original: Callable = Callable(ring, "open")
		var marker: Dictionary = game.stage.place_markers.filter(func(m): return m.get("item", {}).get("id", "") == b.id)[0]
		game.open_building_ring(marker)
		await process_frame
		var titles: Array = ring.find_children("*", "Label", true, false).map(func(l): return l.text)
		check("Ускорить" in titles, "Ring of a training barracks has no speedup: %s" % [titles])
		game.state.city.military.queues[b.id] = []
		ring.close()
		game.open_building_ring(marker)
		await process_frame
		titles = ring.find_children("*", "Label", true, false).map(func(l): return l.text).filter(func(t): return ring.is_open())
		check(not "Ускорить" in titles, "Idle barracks offers a speedup")
	print("QA_SPEEDUPS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
