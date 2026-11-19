extends SceneTree
## «Лес потерянных» vertical slice, played by the real game client against the local realm and
## recorded from the DRENOVAR city camera (orthographic, only target/zoom move). Movie time drives
## everything: each frame advances the client presentation clock by 1/FPS and the realm's
## simulated clock is synced before every request. MARK lines (movie frame numbers) let the
## recording be cut into the evidence segments (a)–(g).
##   --part=early : hall II fog → hall III intro (a) → squad follows the mare, fog opens (b) →
##                  site 1: trail cache, seal, Tenerys, unlock, exit, escort start (c) → reload
##                  mid-escort (g) → arrival home + reward claim (d) → site 2: rune lock, iron
##                  cage (e)
##   --part=boss  : (realm advanced to boss_unlocked by qa_forest_advance.gd) squad formed at
##                  home → arena → awaken → 3-phase fight with telegraphs → death → final reward (f)
##   DRENOVAR_FR_START_TIME=1795000000000 node forest_rescue/server/local-realm/server.mjs
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --write-movie /abs/out.avi --fixed-fps 30 -s qa_forest_slice_movie.gd -- --part=early

const FPS := 30.0
var game: Node
var forest: Node
var clock := 0.0
var follow := true
var follow_zoom := 30.0
var follow_offset := Vector3.ZERO
var part := "early"
var endpoint := ""
var marks: PackedStringArray = []
var frame_count := 0
var boss_units := 1500

func _initialize() -> void:
	call_deferred("run")

func mark(name: String) -> void:
	var line := "MARK %s frame=%d drawn=%d clock=%.0f" % [name, frame_count, Engine.get_frames_drawn(), clock]
	marks.append(line)
	print(line)

func post(path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(endpoint + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else {}
	return parsed if parsed is Dictionary else {}

func sync_clock() -> void:
	await post("/test/clock?time=%d" % int(clock))

func refresh() -> void:
	await sync_clock()
	while game.busy:
		await process_frame
	var response: Dictionary = await game.request("state")
	if response.has("city"):
		game.accept(response)

## One movie frame: advance presentation time and keep the camera on the squad (smoothly).
func frame() -> void:
	clock += 1000.0 / FPS
	frame_count += 1
	forest.client.manual_clock_ms = clock
	if follow:
		var focus: Vector3 = forest.actors.squad_focus()
		if focus != Vector3.INF:
			game.stage.target = game.stage.target.lerp(focus + follow_offset, 0.16)
			game.stage.zoom = lerpf(game.stage.zoom, follow_zoom, 0.1)
	await process_frame

func hold(seconds: float) -> void:
	for i in int(seconds * FPS):
		await frame()

func glide(target: Vector3, zoom: float, seconds: float) -> void:
	var from: Vector3 = game.stage.target
	var from_zoom: float = game.stage.zoom
	var steps := maxi(1, int(seconds * FPS))
	var was := follow
	follow = false
	for i in steps:
		var f := smoothstep(0.0, 1.0, float(i + 1) / steps)
		game.stage.target = from.lerp(target, f)
		game.stage.zoom = lerpf(from_zoom, zoom, f)
		await frame()
	follow = was

func act(action: String, fields := {}, kind := "adventure") -> Dictionary:
	await sync_clock()
	var result: Dictionary = await forest.request_action(action, fields, kind)
	print("SLICE %s %s → %s" % [action, str(fields), "ok" if result.get("ok", false) else String(result.get("error", ""))])
	return result

## Plays movie frames until the authoritative timers settle (moves, battle, plates).
func until_settled(limit := 60.0) -> void:
	var waited := 0.0
	while waited < limit:
		var settle: float = forest.client.last_settle_ms()
		if settle == INF:
			return
		if clock >= settle + 300.0:
			await refresh()
			if forest.client.last_settle_ms() == INF or clock < forest.client.last_settle_ms() + 300.0:
				continue
		await frame()
		waited += 1.0 / FPS

func continue_step() -> Dictionary:
	var step: Dictionary = forest.guide()
	if String(step.get("action", "")).is_empty():
		return {}
	var result: Dictionary = await act(String(step.action), step.get("fields", {}))
	await hold(0.3)
	await until_settled()
	return result

func boot() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
		frame_count += 1
		if frame_count % 600 == 0:
			print("BOOT wait loading=", game.scene_loading, " stage=", is_instance_valid(game.stage), " player=", game.player_id, " busy=", game.busy)
	forest = game.forest_game
	endpoint = game.endpoint

func close_popups() -> void:
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--part="):
			part = argument.trim_prefix("--part=")
		elif argument.begins_with("--boss-units="):
			boss_units = int(argument.trim_prefix("--boss-units="))
	root.size = Vector2i(1366, 630)
	await boot()
	clock = float(game.state.get("serverTime", 0)) + 1000.0
	forest.client.manual_clock_ms = clock
	if part == "boss":
		await run_boss()
	elif part == "site2":
		await refresh()
		close_popups()
		await run_site2()
	else:
		await run_early()
	mark("end")
	print("SLICE_DONE part=", part, " frames=", frame_count, " phase=", forest.client.phase(), " rescued=", forest.client.campaign().get("rescuedCount", -1))
	var file := FileAccess.open("user://slice_marks_%s.txt" % part, FileAccess.WRITE)
	if file != null:
		file.store_string("\n".join(marks))
	quit(0)

# ---------------------------------------------------------------- early slice (a)–(e), (g)
func run_early() -> void:
	await post("/test/hall?level=2")
	await post("/test/army", {"units":{"ENG-02":30000, "ENG-03":30000, "ENG-07":30000}})
	await refresh()
	follow = false
	var entrance: Vector3 = forest.target_position("lf_horse_origin")
	game.stage.target = Vector3(-14, 0, -46)
	game.stage.zoom = 68.0
	game.stage.update_camera(0, true)
	await hold(0.5)
	mark("a_start")
	await hold(1.5)
	# art/18 panel 1: the forest beyond the walls is fog; the locked card explains why.
	await glide(Vector3(-22, 0, -70), 68.0, 2.0)
	await hold(1.5)
	await glide(Vector3(5, 0, -4), 70.0, 1.6)
	forest.hud.hide_locked()
	await post("/test/hall?level=3")
	await refresh()
	mark("a_unlock")
	# 12 s intro: banner → camera to the entrance → corridor opens → Iskra walks out → prompt.
	await hold(13.0)
	mark("a_prompt")
	await hold(1.5)
	forest.intro.on_follow()
	await hold(0.6)
	await forest.wait_idle()
	mark("a_end")
	# The player forms the squad in the panel opened by «Следовать за лошадью».
	if not game.modal.visible:
		forest.panels.open_squad()
	for spin: SpinBox in game.modal_body.find_children("Squad_*", "SpinBox", true, false):
		spin.value = spin.max_value
	await hold(0.8)
	var submit: Button = game.modal_body.find_child("SquadSubmit", true, false)
	if submit != null:
		submit.pressed.emit()
	await forest.wait_idle()
	await hold(0.5)
	# (b) The squad follows the mare: to the horse, then along the entry route to site 1.
	mark("b_start")
	follow = true
	follow_zoom = 34.0
	await continue_step()
	await continue_step()
	await hold(1.2)
	follow_zoom = 38.0
	await continue_step()
	await hold(0.8)
	mark("b_end")
	# (c) Site 1: discover, trail cache (three landmarks), seal, Tenerys I, unlock, exit.
	mark("c_start")
	follow_zoom = 30.0
	await continue_step()
	await hold(1.0)
	mark("c_trail")
	follow_zoom = 24.0
	forest.mech.open("lf_site_01")
	await hold(0.8)
	for symbol in forest.content.site("lf_site_01").artifact.puzzle.solution:
		await sync_clock()
		forest.mech.send_symbol(String(symbol))
		await hold(0.4)
		await until_settled()
		var guard := 0
		while not forest.mech.observed(String(symbol)) and guard < 30:
			await hold(0.3)
			guard += 1
		await forest.wait_idle()
		await hold(0.8)
	await hold(1.2)
	forest.mech.close()
	mark("c_seal")
	follow_zoom = 26.0
	await continue_step()
	await continue_step()
	await hold(2.2)
	mark("c_guardian")
	await continue_step()
	await guardian_battle("lf_site_01")
	await continue_step()
	await hold(0.6)
	mark("c_unlock")
	await continue_step()
	follow = false
	await glide(forest.target_position("lf_site_01:cage") + Vector3(0.8, 0, 2.4), 13.0, 1.0)
	await continue_step()
	await hold(10.5)
	mark("c_escort")
	follow = true
	follow_zoom = 26.0
	await continue_step()
	await hold(5.0)
	mark("c_end")
	# (g) Reload mid-escort: a new client instance restores the walking escort from state.
	mark("g_start")
	await hold(2.0)
	mark("g_reload")
	var target: Vector3 = game.stage.target
	game.queue_free()
	await process_frame
	await boot()
	forest.client.manual_clock_ms = clock
	game.stage.target = target
	game.stage.zoom = follow_zoom
	game.stage.update_camera(0, true)
	await refresh()
	await hold(0.4)
	mark("g_restored")
	await hold(5.0)
	mark("g_end")
	# (d) Arrival at the settlement, thanks, the reward claim.
	mark("d_start")
	await until_settled(90.0)
	await hold(1.0)
	await continue_step()
	mark("d_arrived")
	await hold(6.0)
	follow = false
	forest.panels.open_rewards()
	await hold(2.0)
	var claim: Button = game.modal_body.find_child("ClaimRewards", true, false)
	if claim != null:
		claim.pressed.emit()
	await forest.wait_idle()
	await hold(3.0)
	game.close_modal()
	await hold(1.0)
	mark("d_end")

# ---------------------------------------------------------------- (e) site 2 (separate take)
func run_site2() -> void:
	# (e) Site 2: rune lock (one wrong input), iron cage, Tenerys, unlock, exit, escort start.
	var home: Vector3 = forest.actors.squad_focus()
	if home != Vector3.INF:
		game.stage.target = home
	game.stage.zoom = 40.0
	game.stage.update_camera(0, true)
	await hold(0.5)
	follow = true
	follow_zoom = 40.0
	await travel()               # home → site 2 (the walk itself is segment b's subject)
	mark("e_start")
	await hold(1.0)
	await continue_step()        # discover
	await hold(0.6)
	follow_zoom = 22.0
	await continue_step()        # to the rune lock
	mark("e_rune")
	forest.mech.open("lf_site_02")
	await hold(1.0)
	var solution: Array = forest.content.site("lf_site_02").artifact.puzzle.solution
	await rune_input(String(solution[1]))
	for symbol in solution:
		await rune_input(String(symbol))
	await hold(2.0)
	forest.mech.close()
	follow_zoom = 26.0
	await continue_step()
	await continue_step()
	await hold(1.5)
	mark("e_guardian")
	await continue_step()
	await guardian_battle("lf_site_02")
	await continue_step()
	mark("e_unlock")
	await continue_step()
	follow = false
	await glide(forest.target_position("lf_site_02:cage") + Vector3(0.8, 0, 2.4), 13.0, 1.0)
	await continue_step()
	await hold(10.5)
	follow = true
	follow_zoom = 26.0
	await continue_step()
	await hold(4.0)
	mark("e_end")

## Long walk: commit the move, show 1.5 s of it, then jump the presentation clock to the arrival.
func travel(show := 1.5) -> void:
	var step: Dictionary = forest.guide()
	if String(step.get("action", "")) != "move":
		return
	await act("move", step.get("fields", {}))
	await hold(show)
	var settle: float = forest.client.last_settle_ms()
	if settle != INF and clock < settle + 300.0:
		clock = settle + 300.0
		forest.client.manual_clock_ms = clock
		await refresh()
		var focus: Vector3 = forest.actors.squad_focus()
		if focus != Vector3.INF:
			game.stage.target = focus
			game.stage.update_camera(0, true)
		mark("travel_cut")

func rune_input(symbol: String) -> void:
	await sync_clock()
	await forest.mech.send_symbol(symbol)
	await hold(1.6)

func guardian_battle(site_id: String) -> void:
	var fight: Dictionary = forest.client.battle()
	if fight.is_empty():
		return
	follow = false
	await glide(forest.target_position(site_id + ":guardian") + Vector3(0, 0, 1.0), 22.0, 0.8)
	while clock < float(fight.endsAt) + 400.0:
		await frame()
	await refresh()
	await hold(1.5)
	close_popups()
	follow = true

# ---------------------------------------------------------------- boss (f)
func run_boss() -> void:
	await refresh()
	close_popups()
	follow = true
	follow_zoom = 46.0
	# Squad for the finale (formed at the reception): a measured force so the fight runs through
	# all three phases and every telegraphed attack before the Ancient Maw falls.
	await act("form_squad", {"units":{"ENG-02":boss_units, "ENG-03":boss_units, "ENG-07":boss_units}})
	await hold(0.5)
	mark("f_prep")
	await travel(1.0)           # home → arena (cut)
	follow = false
	var arena: Vector3 = forest.target_position("lf_boss_ancient_maw")
	game.stage.target = arena + Vector3(1.5, 0, 6.0)
	game.stage.zoom = 40.0
	game.stage.update_camera(0, true)
	await hold(0.6)
	mark("f_start")
	await continue_step()       # begin_boss → awaken
	await hold(4.6)
	mark("f_engage")
	var result: Dictionary = await act("engage_boss")
	var fight: Dictionary = forest.client.battle()
	if fight.is_empty():
		return
	mark("f_fight")
	while clock < float(fight.endsAt) + 600.0:
		await frame()
	await refresh()
	mark("f_dead")
	await hold(3.0)
	close_popups()
	await continue_step()       # finish_boss (server verifies the report) → campaign completed
	mark("f_victory")
	await hold(4.0)
	forest.panels.open_rewards()
	await hold(2.0)
	var claim: Button = game.modal_body.find_child("ClaimRewards", true, false)
	if claim != null:
		claim.pressed.emit()
	await forest.wait_idle()
	await hold(3.0)
	mark("f_end")
