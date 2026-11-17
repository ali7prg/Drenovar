extends SceneTree
# Uses the real application, API pool, scene and V6 panels. The one-use pairing
# code stays only in a caller-provided private temporary directory, never logs.
var game
var folder := ""
var checks := 0
var failures: Array[String] = []
func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures.append(label)
		push_error(label)
func wait_for(test: Callable, seconds := 90.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec() > end:
			return false
		await process_frame
	return true
func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-dir="):
			folder = arg.trim_prefix("--qa-dir=")
	call_deferred("run")
func run() -> void:
	if folder.is_empty():
		quit(2)
		return
	root.size = Vector2i(844, 390)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	check(await wait_for(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.busy), "application scene ready")
	await game.device_login()
	await game.sync_account(true)
	check(game.v6_panels.enabled(), "V6 server state accepted")
	if not game.v6_panels.enabled():
		finish()
		return
	check(await game.v6_panels.load_catalogue(), "catalogue from real server")
	check(game.v6_panels.catalogue.buildings.size() == 297, "all 297 states in app")
	game.v6_panels.catalog()
	await process_frame
	var before: Dictionary = game.state.v6.stock.duplicate(true)
	var action := {"kind":"construction", "building":"B01", "target":2, "economy_version":"DRENOVAR-V6-C1.0"}
	check(await game.command({"kind":"v6", "intent":action}), "app starts hall II")
	var pending: Array = game.state.v6.orders.filter(func(o): return o.status == "pending")
	check(pending.size() == 1, "one paid order in app")
	if pending.is_empty():
		finish()
		return
	var order: Dictionary = pending[0]
	var pairing: Dictionary = await game.send_request("pair/create", {})
	check(pairing.has("code"), "one-use link created")
	var handoff := {"code":pairing.get("code", ""), "order_id":order.id, "cost":order.cost, "player_id":game.player_id, "before":before}
	var file := FileAccess.open(folder.path_join("handoff.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(handoff))
	file.close()
	check(await wait_for(func(): return FileAccess.file_exists(folder.path_join("web-done.json")), 120.0), "browser completes shared-account action")
	await game.sync_account()
	pending = game.state.v6.orders.filter(func(o): return o.status == "pending")
	check(pending.is_empty(), "app sees browser cancellation")
	check(game.state.v6.escrow.values().all(func(v): return v == 0), "app sees zero remaining reservation")
	for r: String in before:
		check(float(game.state.v6.stock[r]) >= float(before[r]), "stock preserved after one cancellation: " + r)
	await game.show_scene("world")
	await game.show_scene("city")
	check(game.state.v6.orders.filter(func(o): return o.status == "pending").is_empty(), "map round-trip preserves shared result")
	finish()
func finish() -> void:
	var file := FileAccess.open(folder.path_join("native-result.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify({"status":"passed" if failures.is_empty() else "failed", "checks":checks, "failures":failures, "device":"Godot 4.6.3 Linux 844x390; not iPhone"}, "\t"))
	file.close()
	print("V6_CROSS_CLIENT checks=%d failures=%d" % [checks, failures.size()])
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if failures.is_empty() else 1)
