extends SceneTree
var game
var folder := ""
var checks := 0
var prepare_only := false
var resume_mode := false
var login_only := false
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
		if arg == "--prepare-login":
			prepare_only=true
		if arg == "--login-only":
			login_only=true
		if arg == "--resume-login":
			resume_mode=true
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
	if not resume_mode:
		game.reset_session()
		await game.device_login()
		check(not game.v6_panels.enabled(),"new device has no replacement city")
		await game.begin_main_login(false)
		check(game.login_proof.length()==64,"phone offers ChatGPT sign-in")
		var challenge: String=game.login_proof.sha256_text()
		var auth:=FileAccess.open(folder.path_join("native-auth.json"),FileAccess.WRITE)
		auth.store_string(JSON.stringify({"challenge":challenge,"code":challenge.left(8)}))
		auth.close()
		if prepare_only:
			check(not game.SessionStore.read_pending_login(game.endpoint,game.OLD_SERVER).is_empty(),"pending proof stored before browser")
			print("CHATGPT_PREPARE_OK; process exits before browser approval")
			await create_timer(0.5).timeout
			game.queue_free()
			await process_frame
			await process_frame
			quit(0 if failures.is_empty() else 1)
			return
	else:
		check(game.v6_panels.enabled() or game.login_proof.length()==64,"browser login resumes after app process restart")
	if not await wait_until(func(): return FileAccess.file_exists(folder.path_join("web-approved.json"))):
		check(false,"browser approval timeout")
		quit(1)
		return
	await game.finish_login(true)
	check(game.SessionStore.read_session()==game.session,"confirmed device login saved for next launch")
	check(game.SessionStore.read_pending_login(game.endpoint,game.OLD_SERVER).is_empty(),"successful login clears pending browser proof")
	check(game.v6_panels.enabled(),"main city loaded")
	var expected_id: String=game.player_id
	check(not expected_id.is_empty(),"existing player identity loaded")
	check(int(game.state.v6.buildings.filter(func(b): return b.type=="B01")[0].level)==5,"existing hall V preserved")
	if login_only:
		if not await wait_until(func(): return FileAccess.file_exists(folder.path_join("web-login-done.json"))):
			check(false,"web city comparison timeout")
			quit(1)
			return
		var web: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("web-login-done.json")))
		check(game.player_id==web.player_id,"same existing city in browser after app restart")
		check(game.state.v6.stock==web.stock,"same resources after app restart and ChatGPT confirmation")
		var result:={"status":"passed" if failures.is_empty() else "failed","checks":checks,"failures":failures,"flow":"process exits before browser approval; a new Godot process resumes encrypted proof and opens the same existing city as browser","device":"Godot Linux844x390; synthetic trusted Site identity; not physical iPhone"}
		var output:=FileAccess.open(folder.path_join("native-result.json"),FileAccess.WRITE)
		output.store_string(JSON.stringify(result))
		output.close()
		print(JSON.stringify(result))
		await create_timer(0.5).timeout
		game.queue_free()
		await process_frame
		await process_frame
		quit(0 if failures.is_empty() else 1)
		return
	var before: Dictionary=game.state.v6.stock.duplicate(true)
	check(await game.command({"kind":"v6","intent":{"economy_version":"DRENOVAR-V6-C1.0","kind":"construction","building":"B06","target":2}}),"phone starts a paid order")
	var file:=FileAccess.open(folder.path_join("native-started.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify({"ready":true}))
	file.close()
	if not await wait_until(func(): return FileAccess.file_exists(folder.path_join("web-done.json")),120.0):
		check(false,"browser cancellation timeout")
		quit(1)
		return
	var handoff: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("web-done.json")))
	check(game.player_id==handoff.player_id,"browser and phone share the ChatGPT owner's city")
	await game.sync_account()
	check(game.state.v6.orders.filter(func(o): return o.status=="pending").is_empty(),"phone sees browser cancellation")
	check(game.state.v6.escrow.values().all(func(v): return int(v)==0),"reservation released once")
	for resource: String in before:
		check(int(game.state.v6.stock[resource])==int(before[resource]),"original stock restored exactly: "+resource)
	await game.show_scene("world")
	await game.show_scene("city")
	check(game.player_id==expected_id,"city/world round trip keeps the main city")
	var result:={"status":"passed" if failures.is_empty() else "failed","checks":checks,"failures":failures,"device":"Godot Linux844x390, not iPhone","flow":"phone ChatGPT approval -> existing main city -> paid order -> browser cancel -> phone"}
	file=FileAccess.open(folder.path_join("native-result.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(result))
	file.close()
	print(JSON.stringify(result))
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if failures.is_empty() else 1)
