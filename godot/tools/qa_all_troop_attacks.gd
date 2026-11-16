extends SceneTree
# Main scene, real touch, loopback server with DRENOVAR_QA_ALL_UNITS=1: a party
# of all ten troop types against every city creature, real travel time.
# Checks that the creature plays Roar/Attack/Death and that every troop type
# the server has striking is also drawn striking (1013: most types stood idle
# because their strikes belonged to members without a model or in reserve).
# Headless Linux; not iPhone acceptance.
var game
var checks := 0
var failures: Array[String] = []
var report := []
func _initialize() -> void: call_deferred("run")
func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("ATTACKS ", label, " ", ok)
func wait_until(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec()+int(seconds*1000)
	while not test.call():
		if Time.get_ticks_msec()>end: return false
		await process_frame
	return true
func find_button(node: Node, title: String) -> Button:
	if node is Button and node.text==title: return node
	for c in node.get_children():
		var v := find_button(c,title)
		if v != null: return v
	return null
func tap(node: Control) -> void:
	if node == null: check(false, "touch target exists"); return
	var at := node.get_global_rect().get_center()
	for pressed in [true,false]:
		var e := InputEventScreenTouch.new(); e.position=at; e.pressed=pressed; root.push_input(e,true)
		await process_frame
	await process_frame
func run() -> void:
	root.size = Vector2i(1366,630)
	game = load("res://main.tscn").instantiate(); game.single_scene=true; root.add_child(game)
	if not await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.busy, 90): quit(2); return
	if not game.endpoint.begins_with("http://127.0.0.1:"): quit(2); return
	await game.device_login(); await game.create_settlement(); await game.sync_account(); game.close_modal()
	for target in game.state.encounters.duplicate():
		await game.poll_account_state(true)
		var cur: Dictionary = game.state.encounters.filter(func(e): return e.id == target.id)[0]
		var label := "%s L%d" % [cur.species, int(cur.level)]
		game.inspect_encounter(cur); await process_frame; await process_frame
		await tap(find_button(game.modal_footer,"Атаковать"))
		check(await wait_until(func(): return game.modal_title.text=="Создать войско",5), label + " formation opens")
		var spins: Array = game.modal_body.find_children("*","SpinBox",true,false)
		for s in spins: s.value = 0
		for s in spins: s.value = 6
		await create_timer(0.6).timeout
		await tap(game.modal_footer.find_child("MarchSend",true,false))
		await wait_until(func(): return not game.command_in_progress and not game.modal.visible, 10)
		var army: Dictionary = {}
		for a in game.state.armies:
			if a.target == cur.id and a.status != "returned": army = a
		check(not army.is_empty(), label + " army sent")
		if army.is_empty(): continue
		game.stage.target = game.stage.point(cur.position); game.stage.zoom = 34.0
		var drawn := {}
		var beast := {}
		var fight_ms := 0.0
		var worst := 0.0
		var last := Time.get_ticks_usec()
		var end := Time.get_ticks_msec() + int(float(army.arrivesAt) - game.server_time() + 15000)
		while Time.get_ticks_msec() < end:
			await process_frame
			var tick := Time.get_ticks_usec()
			var dt := (tick - last) / 1000.0
			last = tick
			worst = maxf(worst, dt)
			for row in game.stage.combat_view.frame_state.get("armies", []):
				if row.id == army.id and row.status == "fighting": fight_ms += dt
			if game.modal.visible: game.close_modal()
			var actor = game.stage.actors.get_node_or_null(NodePath(str(army.id)))
			if actor:
				for u in actor.get_children():
					if u.get_meta("clip","") == "attack": drawn[str(u.name).get_slice("_",0)] = true
			var creature = game.stage.creatures.get_node_or_null(NodePath(str(cur.id)))
			if creature: beast[creature.get_meta("clip","")] = true
		var server := {}
		var creature_struck := false
		for a in game.state.armies:
			if a.id == army.id:
				for e in game.stage.army_battle_events(a):
					var r: Array = game.stage.event_row(e)
					if r[1] == "soldier_attack": server[r[2]] = true
					else: creature_struck = true
		# A creature killed by the first volleys never strikes: Attack is
		# required only when the server reports a creature strike.
		for clip in ["Roar","Attack","Death"] if creature_struck else ["Roar","Death"]:
			check(beast.has(clip), "%s creature plays %s" % [label, clip])
		for type in server:
			check(drawn.has(type), "%s %s strikes shown" % [label, type])
		# The server fight lasts about a second; it must be watchable.
		check(fight_ms >= 5000.0, "%s fight shown for %.1f s" % [label, fight_ms / 1000.0])
		check(worst < 250.0, "%s no stall (worst %.0f ms)" % [label, worst])
		report.append({"target":label,"fight_shown_ms":fight_ms,"worst_frame_ms":worst,"creature":beast.keys(),"server_striking":server.keys(),"drawn_striking":drawn.keys()})
	print(JSON.stringify({"checks":checks,"failures":failures,"fights":report,"method":"Linux Godot headless main scene, real touch, loopback synthetic V6 server, all ten troop types; not iPhone acceptance"}))
	game.queue_free(); await process_frame; await process_frame
	quit(0 if failures.is_empty() else 1)
