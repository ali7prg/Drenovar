extends SceneTree
# Frame-by-frame record of a real city hunt in the main scene (loopback V6 server).
# Writes one JSON line per frame: presentation clock, army/creature state, and for
# every drawn soldier its visibility, on-screen bounds (bone origins), clip, clip
# position and a pose probe. tools/analyze_combat_telemetry.py turns the record into
# per-symptom numbers (invisible strikes, jumps, disappearances, freezes, stalls).
# Linux evidence only: not a measurement of iPhone frame time.
#
# User args (after --):
#   --server=URL           loopback V6 server (required by main.gd)
#   --out=PATH             JSONL output
#   --species=tenerys      city creature to hunt (any if not found)
#   --spin=12              soldiers of each troop type in the march window
#   --zoom=34              camera zoom kept on the fight (city ortho height)
#   --offset=X,Z           camera target offset from the creature (metres)
#   --pan=1                pan the camera away and back during the fight
#   --stall=P:MS           each frame, with probability P, block the main thread MS ms
#   --hunts=N              hunts in a row (repeated attacks, cold first fight)
var game
var out: FileAccess
var args := {}
var rng := RandomNumberGenerator.new()

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.substr(2, a.find("=") - 2)] = a.substr(a.find("=") + 1)
	rng.seed = int(args.get("seed", "7"))
	call_deferred("run")

func wait_until(test: Callable, seconds := 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while not test.call():
		if Time.get_ticks_msec() > end: return false
		await process_frame
	return true

func find_button(node: Node, title: String) -> Button:
	if node is Button and node.text == title: return node
	for c in node.get_children():
		var v := find_button(c, title)
		if v != null: return v
	return null

func tap(node: Control) -> void:
	if node == null: return
	var at := node.get_global_rect().get_center()
	for pressed in [true, false]:
		var e := InputEventScreenTouch.new(); e.position = at; e.pressed = pressed; root.push_input(e, true)
		await process_frame
	await process_frame

func v3(p: Vector3) -> Array:
	return [snappedf(p.x, 0.001), snappedf(p.y, 0.001), snappedf(p.z, 0.001)]

# Bone-origin bounds: the skinned pose, independent of the mesh's rest AABB.
func pose_bounds(unit: Node3D) -> Dictionary:
	var lo := Vector3.INF; var hi := -Vector3.INF
	var hand := Vector3.ZERO
	var found := false
	for sk: Skeleton3D in unit.find_children("*", "Skeleton3D", true, false):
		for b in sk.get_bone_count():
			var p := (sk.global_transform * sk.get_bone_global_pose(b)).origin
			lo = lo.min(p); hi = hi.max(p); found = true
			var n := sk.get_bone_name(b).to_lower()
			if n == "wrist.r" or n == "righthand" or n == "hand.r":
				hand = unit.global_transform.affine_inverse() * p
		break
	if not found:
		return {"ok": false}
	return {"ok": true, "lo": lo, "hi": hi, "hand": hand}

func on_screen(cam: Camera3D, lo: Vector3, hi: Vector3) -> String:
	# "in" all corners in frustum, "part" some, "out" none.
	var inside := 0
	for i in 8:
		var c := Vector3(lo.x if i & 1 == 0 else hi.x, lo.y if i & 2 == 0 else hi.y, lo.z if i & 4 == 0 else hi.z)
		if cam.is_position_in_frustum(c): inside += 1
	return "in" if inside == 8 else ("part" if inside > 0 else "out")

func player_of(node: Node) -> AnimationPlayer:
	var players: Array = node.get_meta("animation_players", [])
	if players.is_empty():
		players = node.find_children("*", "AnimationPlayer", true, false)
	return players[0] if not players.is_empty() else null

func shown_armies() -> Array:
	var fs: Dictionary = game.stage.combat_view.frame_state
	return fs.get("world", {}).get("armies", []) if game.map_name == "world" else fs.get("armies", [])

var current_map := "city"

func world() -> bool:
	return current_map == "world"

func sample(frame: int, dt: float, army_id: String, creature_id: String, phase: String) -> void:
	var stage = game.stage
	if not is_instance_valid(stage): return
	var cam: Camera3D = stage.camera
	var row := {"f": frame, "t": Time.get_ticks_usec(), "dt": snappedf(dt, 0.01), "phase": phase,
		"now": game.server_time(), "ft": stage.combat_view.frame_time, "delay": stage.combat_view.delay_ms,
		"cam": v3(stage.camera_target), "zoom": snappedf(stage.camera_zoom, 0.01)}
	for a in shown_armies():
		if str(a.id) == army_id:
			row.status = str(a.status)
			row.battleAt = a.get("battleAt"); row.returnStartsAt = a.get("returnStartsAt"); row.returnsAt = a.get("returnsAt")
	var cache: Dictionary = stage.army_routes.get(army_id, {})
	var plan: Dictionary = cache.get("engage", {})
	if not plan.is_empty():
		row.plan = [plan.get("halt_at"), snappedf(float(plan.get("stop", 0)), 0.01), plan.get("locked", false), plan.get("solving", false),
			plan.get("approaches", {}).size(), hash(cache.get("source", [])), hash(cache.get("bag", {})), hash(plan.get("places", {}))]
	var actor: Node3D = stage.actors.get_node_or_null(NodePath(army_id))
	row.actor = "none" if actor == null else ("shown" if actor.is_visible_in_tree() else "hidden")
	if actor != null:
		row.anchor = v3(actor.global_position)
		row.anchor_in = cam.is_position_in_frustum(actor.global_position + Vector3.UP)
		var units := []
		for u in actor.get_children():
			if not u is Node3D or u.name == &"Ferry": continue
			var pb := pose_bounds(u)
			var p := player_of(u)
			var rec := {"n": str(u.name), "vis": u.is_visible_in_tree(), "pos": v3(u.global_position),
				"yaw": snappedf(u.global_rotation.y, 0.001), "clip": str(u.get_meta("clip", "")),
				"strike": u.get_meta("v010_strike") if u.has_meta("v010_strike") else null}
			if p != null:
				rec.anim = str(p.assigned_animation); rec.ap = snappedf(p.current_animation_position, 0.001); rec.play = p.is_playing()
			if pb.ok:
				rec.scr = on_screen(cam, pb.lo, pb.hi); rec.hand = v3(pb.hand)
			units.append(rec)
		row.units = units
	var fallen := []
	for body in stage.fallen_bodies:
		if is_instance_valid(body.node): fallen.append(str(body.node.name))
	row.fallen = fallen
	var beast: Node3D = stage.creatures.get_node_or_null(NodePath(creature_id))
	if beast != null:
		var p := player_of(beast)
		var pb := pose_bounds(beast)
		row.beast = {"vis": beast.is_visible_in_tree(), "pos": v3(beast.global_position), "clip": str(beast.get_meta("clip", "")),
			"anim": str(p.assigned_animation) if p else "", "ap": snappedf(p.current_animation_position, 0.001) if p else -1.0,
			"scr": on_screen(cam, pb.lo, pb.hi) if pb.ok else "?"}
	else:
		row.beast = null
	row.fx_children = stage.effects.get_child_count()
	row.proc = snappedf(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, 0.01)
	# Creatures the scene shows vs creatures inside the camera frustum (any distance).
	var shown := 0
	for c in stage.creatures.get_children():
		if c is Node3D and c.is_visible_in_tree(): shown += 1
	var framed := 0
	for e in (game.state.world.encounters if world() else game.state.encounters):
		if e.get("status", "") != "defeated" and cam.is_position_in_frustum(stage.ground_point(stage.point(e.position)) + Vector3.UP): framed += 1
	row.creatures = [shown, framed]
	row.nodes = Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	row.objects = Performance.get_monitor(Performance.OBJECT_COUNT)
	row.mem = snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1)
	# Pipelines compiled at draw time stall the frame that first shows a material.
	row.pc = [Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_DRAW), Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_SURFACE),
		Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_MESH), Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_SPECIALIZATION),
		Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_CANVAS)]
	var vp := root.get_viewport_rid()
	row.rcpu = snappedf(RenderingServer.viewport_get_measured_render_time_cpu(vp), 0.01)
	row.rgpu = snappedf(RenderingServer.viewport_get_measured_render_time_gpu(vp), 0.01)
	out.store_line(JSON.stringify(row))

func run() -> void:
	root.size = Vector2i(1366, 630)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	out = FileAccess.open(args.get("out", "user://combat_telemetry.jsonl"), FileAccess.WRITE)
	game = load("res://main.tscn").instantiate(); game.single_scene = true; root.add_child(game)
	if not await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.busy, 120): quit(2); return
	if not game.endpoint.begins_with("http://127.0.0.1:"): quit(2); return
	await game.device_login(); await game.create_settlement(); await game.sync_account(); game.close_modal()
	if args.get("diag", "0") == "1":
		game.set_combat_diagnostics(true, false)
	# --maps=city,world alternates the map per hunt (scene transitions included);
	# --minutes=N keeps hunting until N minutes have passed, with a fresh test
	# settlement whenever every creature is down; --background=1 emulates a 4 s
	# suspension of the app in the middle of each fight.
	var maps: PackedStringArray = str(args.get("maps", args.get("map", "city"))).split(",")
	var minutes := float(args.get("minutes", "0"))
	var session_start := Time.get_ticks_msec()
	var stall: PackedStringArray = str(args.get("stall", "0:0")).split(":")
	var stall_p := float(stall[0]); var stall_ms := int(stall[1])
	var hunts := int(args.get("hunts", "1"))
	var frame := 0
	var used := {}
	var dumped := {}
	var suspended := {}
	var every := maxi(1, int(args.get("every", "1")))
	var recall_ms := int(args.get("recall", "0"))
	var hunt := -1
	var accounts := 1
	while true:
		hunt += 1
		if minutes > 0.0:
			if Time.get_ticks_msec() - session_start > minutes * 60000.0: break
		elif hunt >= hunts: break
		var wanted := maps[hunt % maps.size()]
		if wanted != game.map_name:
			current_map = wanted
			await game.show_scene(wanted)
			await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and game.map_name == wanted, 120)
			out.store_line(JSON.stringify({"scene": wanted, "at_ms": Time.get_ticks_msec() - session_start}))
		current_map = game.map_name
		await game.poll_account_state(true)
		var pick: Dictionary = {}
		var pool: Array = game.state.world.encounters if world() else game.state.encounters
		for e in pool:
			if used.has(e.id) or e.status == "defeated" or int(e.get("hp", 1)) <= 0: continue
			if not e.has("species"): e.species = game.stage.creature_species(e)
			if world() and e.get("status", "alive") != "alive": continue
			if pick.is_empty() or (str(e.species) == args.get("species", "tenerys") and str(pick.species) != args.get("species", "tenerys")):
				pick = e
		if hunt == 0:
			print("TELEMETRY encounters ", pool.slice(0, 12).map(func(e): return "%s L%d %s" % [game.stage.creature_species(e), int(e.get("level", 0)), e.get("status", "")]))
		if pick.is_empty() and minutes > 0.0 and world() and maps.size() > 1:
			# The world's creatures are shared by every test settlement: once they are
			# down the session goes on in the city.
			maps = PackedStringArray(Array(maps).filter(func(m): return m != "world"))
			hunt -= 1
			continue
		if pick.is_empty() and minutes > 0.0 and accounts < 40:
			# Every creature of this settlement is down: a fresh test settlement.
			accounts += 1
			game.reset_session("qa-session")
			await game.device_login(); await game.create_settlement(); await game.sync_account(); game.close_modal()
			used.clear()
			hunt -= 1
			continue
		if pick.is_empty(): break
		used[pick.id] = true
		await wait_until(func(): return not game.player_id.is_empty() and game.hall_level() >= 3 and not game.busy, 30)
		print("TELEMETRY ready player=%s hall=%d busy=%s" % [not game.player_id.is_empty(), game.hall_level(), game.busy])
		game.inspect_encounter(pick); await process_frame; await process_frame
		var caption := "Собрать отряд" if world() else "Атаковать"
		await wait_until(func(): var b := find_button(game.modal_footer, caption); return b != null and not b.disabled, 25)
		await tap(find_button(game.modal_footer, caption))
		if not await wait_until(func(): return game.modal_footer.find_child("MarchSend", true, false) != null and not game.modal_body.find_children("*", "SpinBox", true, false).is_empty(), 25):
			print("TELEMETRY no march window: title=%s buttons=%s" % [game.modal_title.text, game.modal_footer.find_children("*", "Button", true, false).map(func(b): return "%s%s" % [b.text, "(off)" if b.disabled else ""])])
			continue
		var spins: Array = game.modal_body.find_children("*", "SpinBox", true, false)
		for s in spins: s.value = 0
		for s in spins: s.value = int(args.get("spin", "12"))
		await create_timer(2.5).timeout
		await tap(game.modal_footer.find_child("MarchSend", true, false))
		var target_id: String = str(pick.id)
		await wait_until(func(): return (game.state.world.armies if world() else game.state.armies).any(func(a): return str(a.target) == target_id and a.status != "returned") or (not game.command_in_progress and not game.modal.visible), 30)
		var army: Dictionary = {}
		for a in (game.state.world.armies if world() else game.state.armies):
			if a.target == pick.id and a.status != "returned": army = a
		if army.is_empty(): print("TELEMETRY no army"); continue
		print("TELEMETRY hunt %s L%s army %s arrives in %.1f s" % [pick.species, pick.level, army.id, (float(army.arrivesAt) - game.server_time()) / 1000.0])
		out.store_line(JSON.stringify({"hunt": hunt, "army": army.id, "creature": pick.id, "species": pick.species, "level": pick.level, "arrivesAt": army.arrivesAt}))
		var offset: PackedStringArray = str(args.get("offset", "0,0")).split(",")
		var centre: Vector3 = game.stage.point(pick.position) + Vector3(float(offset[0]), 0, float(offset[1]))
		var last := Time.get_ticks_usec()
		var started := Time.get_ticks_msec()
		var deadline := started + int(float(army.arrivesAt) - game.server_time()) + 60000
		var phase := "march"
		var recalled := false
		while Time.get_ticks_msec() < deadline:
			await process_frame
			var tick := Time.get_ticks_usec()
			var dt := (tick - last) / 1000.0
			last = tick
			frame += 1
			if game.modal.visible: game.close_modal()
			var st := ""
			for a in shown_armies():
				if str(a.id) == str(army.id): st = str(a.status)
			if st == "fighting": phase = "fight"
			elif st == "returning": phase = "return"
			elif phase != "march" and st == "": phase = "home"
			# Camera like a phone player: on the creature; optionally panned away and back.
			var c := centre
			if args.get("pan", "0") == "1" and phase == "fight":
				c += Vector3(sin((Time.get_ticks_msec() - started) / 900.0) * 26.0, 0, 0)
			game.stage.target = c
			game.stage.zoom = float(args.get("zoom", "34"))
			if frame % every == 0 or dt > 50.0:
				sample(frame, dt, str(army.id), str(pick.id), phase)
			for a in shown_armies():
				if str(a.id) == str(army.id) and phase in ["fight", "return"]:
					var known: int = game.stage.army_battle_events(a).size()
					if int(dumped.get(army.id, -1)) != known:
						dumped[army.id] = known
						var cache: Dictionary = game.stage.army_routes.get(str(army.id), {})
						var plan: Dictionary = cache.get("engage", {})
						out.store_line(JSON.stringify({"frame": frame, "events": game.stage.army_battle_events(a).map(func(e): return game.stage.event_row(e)),
							"members": cache.get("events", {}).get("members", {}).keys(), "forced": cache.get("events", {}).get("forced", {}).keys(),
							"reserves": plan.get("reserves", {}).keys().filter(func(k): return plan.reserves[k]), "slots": cache.get("slots", []).map(func(s): return "%s:%d" % [s.id, int(s.index)]),
							"battleAt": a.get("battleAt"), "stretched": a.get("stretched"), "delay": game.stage.combat_view.delay_ms}))
			if stall_p > 0.0 and rng.randf() < stall_p:
				OS.delay_msec(stall_ms)
			# --recall=MS: recall the march MS ms (server time) after it set off.
			if recall_ms > 0 and not recalled and game.server_time() >= float(army.startsAt) + recall_ms:
				recalled = true
				print("TELEMETRY recall sent")
				game.command({"kind": "recall", "armyId": army.id})
			if args.get("background", "0") == "1" and phase == "fight" and not suspended.has(army.id):
				suspended[army.id] = true
				game._notification(Node.NOTIFICATION_APPLICATION_PAUSED)
				OS.delay_msec(4000)
				game._notification(Node.NOTIFICATION_APPLICATION_RESUMED)
			if phase == "home":
				break
		await create_timer(1.0).timeout
	out.close()
	if "combat_diagnostics" in game and game.combat_diagnostics != null:
		var report: Dictionary = game.combat_diagnostics.report()
		var text := JSON.stringify(report)
		var file := FileAccess.open(str(args.get("out", "user://combat_telemetry.jsonl")) + ".diag.json", FileAccess.WRITE)
		file.store_string(text); file.close()
		print("TELEMETRY diagnostics report bytes=%d log=%d/%d frames=%s" % [text.length(), report.log.size(), report.log_total, JSON.stringify(report.frames)])
	print("TELEMETRY done frames=%d hunts=%d accounts=%d minutes=%.1f" % [frame, hunt, accounts, (Time.get_ticks_msec() - session_start) / 60000.0])
	game.queue_free(); await process_frame; await process_frame
	quit(0)
