extends SceneTree
var game
var folder := ""
var checks := 0
var failures: Array[String] = []
func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures.append(label)
		push_error(label)
func wait_until(test: Callable, seconds := 90.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec()>end:
			return false
		await process_frame
	return true
func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-dir="):
			folder=arg.trim_prefix("--qa-dir=")
	call_deferred("run")
func run() -> void:
	if folder.is_empty():
		quit(2)
		return
	root.size=Vector2i(844,390)
	game=load("res://main.tscn").instantiate()
	root.add_child(game)
	check(await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and is_instance_valid(game.modal_title) and not game.busy),"scene ready")
	game.reset_session()
	await game.device_login()
	check(not game.v6_panels.enabled(),"new device has no replacement city")
	check(await wait_until(func(): return FileAccess.file_exists(folder.path_join("web-handoff.json"))),"signed-in browser opens main city")
	var handoff: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("web-handoff.json")))
	var paired: Dictionary=await game.send_request("pair/accept",{"code":handoff.code})
	check(paired.get("paired",false),"phone connects by one-use code")
	game.player_id=""
	await game.sync_account()
	check(game.v6_panels.enabled(),"main city loaded")
	check(game.player_id==handoff.player_id,"browser and phone share player identity")
	check(int(game.state.v6.buildings.filter(func(b): return b.type=="B01")[0].level)==5,"existing hall V preserved")
	var before: Dictionary=game.state.v6.stock.duplicate(true)
	check(await game.command({"kind":"v6","intent":{"economy_version":"DRENOVAR-V6-C1.0","kind":"construction","building":"B06","target":2}}),"phone starts a paid order")
	var file:=FileAccess.open(folder.path_join("native-started.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify({"ready":true}))
	file.close()
	check(await wait_until(func(): return FileAccess.file_exists(folder.path_join("web-done.json")),120.0),"browser cancels that order through its UI")
	await game.sync_account()
	check(game.state.v6.orders.filter(func(o): return o.status=="pending").is_empty(),"phone sees browser cancellation")
	check(game.state.v6.escrow.values().all(func(v): return int(v)==0),"reservation released once")
	for resource: String in before:
		check(int(game.state.v6.stock[resource])==int(before[resource]),"original stock restored exactly: "+resource)
	await game.show_scene("world")
	await game.show_scene("city")
	check(game.player_id==handoff.player_id,"city/world round trip keeps the main city")
	var result:={"status":"passed" if failures.is_empty() else "failed","checks":checks,"failures":failures,"device":"Godot Linux844x390, not iPhone","flow":"existing browser account -> same main city on phone -> paid order -> browser cancel -> phone"}
	file=FileAccess.open(folder.path_join("native-result.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(result))
	file.close()
	print(JSON.stringify(result))
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if failures.is_empty() else 1)
