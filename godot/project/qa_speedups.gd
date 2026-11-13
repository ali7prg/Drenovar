extends SceneTree

# Speedups: every queue (construction, training, march) offers the tiers
# 1 min, 5 min, 15 min, 30 min, 1 h, 2 h, 5 h, 10 h; owned items can be used, the
# others are shown as missing; the command names the queue, the item and the order.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func buttons(game) -> Array:
	return game.modal_body.find_children("*", "Button", true, false)

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.endpoint = "http://127.0.0.1:9"
	game.player_id = "qa-speed"
	var catalog: Dictionary = game.speed_catalog()
	for queue in ["construction", "training", "march"]:
		var tiers: Array = catalog.values().filter(func(item): return item.kind == queue).map(func(item): return int(item.seconds))
		tiers.sort()
		check(tiers == [60, 300, 900, 1800, 3600, 7200, 18000, 36000], "%s tiers: %s" % [queue, tiers])
	for id in game.data.speedItems:
		check(catalog.has(id) and int(catalog[id].seconds) == int(game.data.speedItems[id].seconds), "Server item id changed: " + id)
	check(game.speed_duration(1800) == "30 мин" and game.speed_duration(36000) == "10 ч", "Duration labels")
	# Owned 2 h construction item enabled, the rest shown as missing.
	var two_hours: String = catalog.keys().filter(func(id): return catalog[id].kind == "construction" and int(catalog[id].seconds) == 7200)[0]
	game.state.items = {two_hours: 3}
	var order := {"kind": "upgrade", "requestId": "req-1", "endsAt": game.server_time() + 3.0 * 3600000.0}
	game.show_speedups("construction", order, "")
	var list: Array = buttons(game).filter(func(b): return " · " in b.text)
	check(list.size() == 8, "Eight tiers listed: %d" % list.size())
	var enabled: Array = list.filter(func(b): return not b.disabled)
	check(enabled.size() == 1 and enabled[0].text == "2 ч · ×3", "Only the owned tier is usable: %s" % [enabled.map(func(b): return b.text)])
	# March: the garrison window offers a march speedup for an outbound army.
	var army := {"id": "army-q", "name": "Отряд", "status": "outbound", "owner": "qa-speed",
		"startsAt": game.server_time(), "arrivesAt": game.server_time() + 600000.0, "units": {}}
	game.state.armies = [army]
	game.show_armies()
	var march: Array = buttons(game).filter(func(b): return b.text == "Ускорить марш")
	check(march.size() == 1, "No march speedup in the garrison")
	var one_minute: String = catalog.keys().filter(func(id): return catalog[id].kind == "march" and int(catalog[id].seconds) == 60)[0]
	game.state.items = {one_minute: 1}
	if not march.is_empty():
		march[0].pressed.emit()
	check(game.modal_title.text.contains("Марш"), "March speedup window not opened")
	var use: Array = buttons(game).filter(func(b): return b.text == "1 мин · ×1" and not b.disabled)
	check(use.size() == 1, "Owned march item not usable")
	game.state.armies = []
	print("QA_SPEEDUPS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
