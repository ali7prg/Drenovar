extends SceneTree
## First slice of «Лес потерянных» as one continuous in-engine movie, played through the real
## game client against the local realm, from the DRENOVAR city camera (target/zoom only):
## locked fog → hall III intro → Iskra leads → squad walks the entrance route (fog opens) →
## site 1 discovery → trail cache → Tenerys I battle → seal into the socket, cage opens →
## three captives walk home → reward reserve claim.
## Movie time drives everything: each rendered frame advances the client presentation clock
## by 1/FPS and the realm's simulated clock is synced before every request.
##   DRENOVAR_FR_START_TIME=1795000000000 node forest_rescue/server/local-realm/server.mjs
##   godot --path godot/project --rendering-driver vulkan --resolution 1366x630 \
##     --write-movie /abs/slice.avi --fixed-fps 10 -s qa_forest_e2e_movie.gd -- --server=http://127.0.0.1:8418

const FPS := 10.0
var game: Node
var forest: Node
var clock := 0.0
var follow := true
var follow_zoom := 30.0
var log_lines: PackedStringArray = []

func _initialize() -> void:
	call_deferred("run")

func say(text: String) -> void:
	log_lines.append(text)
	print("SLICE ", text)

func post(path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(game.endpoint + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "" if body == null else JSON.stringify(body))
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
	forest.client.manual_clock_ms = clock
	if follow:
		var focus: Vector3 = forest.actors.squad_focus()
		if focus != Vector3.INF:
			game.stage.target = game.stage.target.lerp(Vector3(focus.x, focus.y, focus.z), 0.18)
			game.stage.zoom = lerpf(game.stage.zoom, follow_zoom, 0.12)
	await process_frame

func hold(seconds: float) -> void:
	for i in int(seconds * FPS):
		await frame()

func act(action: String, fields := {}, kind := "adventure") -> Dictionary:
	await sync_clock()
	var result: Dictionary = await forest.request_action(action, fields, kind)
	say("%s %s → %s" % [action, str(fields), "ok" if result.get("ok", false) else String(result.get("error", ""))])
	return result

## Plays movie frames until the authoritative timers settle (moves, battle, plates).
func until_settled(limit := 40.0) -> void:
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
	await hold(0.4)
	await until_settled()
	return result

func run() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty():
		await process_frame
	forest = game.forest_game
	clock = float(game.state.get("serverTime", 0)) + 1000.0
	forest.client.manual_clock_ms = clock
	await post("/test/hall?level=2")
	await post("/test/army", {"units":{"ENG-02":30000, "ENG-03":30000, "ENG-07":30000}})
	await refresh()
	say("locked hall II")
	follow = false
	game.stage.target = Vector3(-12, 0, -40)
	game.stage.zoom = 70.0
	await hold(1.5)
	game.stage.target = Vector3(-26, 0, -78)
	await hold(2.5)
	game.stage.target = Vector3(5, 0, -4)
	await hold(1.0)
	await post("/test/hall?level=3")
	await refresh()
	say("hall III: intro")
	await hold(13.0)
	forest.intro.on_follow()
	await hold(1.0)
	await forest.wait_idle()
	await hold(0.5)
	# The player forms the squad in the panel opened by «Следовать за лошадью».
	if not game.modal.visible:
		forest.panels.open_squad()
	for spin: SpinBox in game.modal_body.find_children("Squad_*", "SpinBox", true, false):
		spin.value = spin.max_value
	await hold(1.2)
	var submit: Button = game.modal_body.find_child("SquadSubmit", true, false)
	if submit != null:
		submit.pressed.emit()
	await forest.wait_idle()
	await hold(0.8)
	follow = true
	follow_zoom = 34.0
	say("prologue")
	await continue_step()
	await continue_step()
	await hold(1.5)
	say("to site 1")
	await continue_step()
	await hold(0.6)
	await continue_step()
	await hold(1.5)
	say("trail cache")
	follow_zoom = 26.0
	forest.mech.open("lf_site_01")
	await hold(1.0)
	for symbol in forest.content.site("lf_site_01").artifact.puzzle.solution:
		await sync_clock()
		forest.mech.send_symbol(String(symbol))
		await hold(0.5)
		await until_settled()
		var guard := 0
		while not forest.mech.observed(String(symbol)) and guard < 30:
			await hold(0.3)
			guard += 1
		await forest.wait_idle()
		await hold(1.0)
	await hold(1.0)
	forest.mech.close()
	follow_zoom = 28.0
	await continue_step()
	await continue_step()
	await hold(2.0)
	say("guardian")
	await continue_step()
	var fight: Dictionary = forest.client.battle()
	if not fight.is_empty():
		follow = false
		game.stage.target = forest.target_position("lf_site_01:guardian")
		game.stage.zoom = 26.0
		while clock < float(fight.endsAt) + 400.0:
			await frame()
		await refresh()
		await hold(2.5)
		game.close_modal()
		follow = true
	await continue_step()
	await hold(1.0)
	say("unlock cage")
	await continue_step()
	follow = false
	game.stage.target = forest.target_position("lf_site_01:cage")
	game.stage.zoom = 22.0
	await continue_step()
	await hold(9.0)
	say("escort home")
	follow = true
	follow_zoom = 30.0
	await continue_step()
	await until_settled(60.0)
	await hold(2.0)
	await continue_step()
	await hold(5.0)
	say("rewards")
	follow = false
	forest.panels.open_rewards()
	await hold(2.0)
	var claim: Button = game.modal_body.find_child("ClaimRewards", true, false)
	if claim != null:
		claim.pressed.emit()
	await forest.wait_idle()
	await hold(3.5)
	print("SLICE_DONE frames=", int((clock - float(game.state.serverTime)) / (1000.0 / FPS)), " phase=", forest.client.phase(),
		" site01 step=", forest.client.site_state("lf_site_01").get("step", -1), " rescued=", forest.client.campaign().get("rescuedCount", -1))
	quit(0)
