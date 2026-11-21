extends SceneTree
## In-engine screenshots of the «Лес потерянных» gameplay layer from the real DRENOVAR city
## camera (orthographic, target/zoom only). States are recorded realm fixtures injected through
## a stub transport (no network). Usage (Vulkan under Xvfb):
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     -s qa_forest_flow_capture.gd -- --out=/abs/dir --prefix=iter01_ [--shots=a,b]

const FIXTURES := "res://data/forest_rescue/game/fixtures/"

class StubHost extends Node:
	var main: Node
	var busy := false
	var replies: Array = []
	func request(_path: String, _payload: Variant = null, _key := "") -> Dictionary:
		return replies.pop_front() if not replies.is_empty() else {"error":"Сервер недоступен"}
	func accept(response: Dictionary) -> void:
		main.accept(response)
	func poll_account_state() -> void:
		pass

var game: Node
var forest: Node
var stub: StubHost
var out := ""
var prefix := ""
var only: PackedStringArray = []
var saved: PackedStringArray = []

func _initialize() -> void:
	call_deferred("run")

func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))

func wanted(name: String) -> bool:
	return only.is_empty() or only.has(name)

func shoot(name: String, settle := 0.6) -> void:
	await create_timer(settle).timeout
	await RenderingServer.frame_post_draw
	var summary: PackedStringArray = []
	for id in forest.actors.rigs:
		var rig = forest.actors.rigs[id]
		summary.append("%s:%s:%s" % [id, rig.load_state, "v" if rig.visible else "h"])
	print("SHOT ", name, " world=", forest.world != null, " actors=", ", ".join(summary))
	var path := out.path_join(prefix + name + ".png")
	root.get_texture().get_image().save_png(path)
	saved.append(path)

func fresh(state_name: String, live := false) -> void:
	game.close_modal()
	forest.mech.close() if forest.mech.is_open() else null
	if not live:
		forest.actors.on_stage_changed()
		forest.actors.first_state = true
		forest.client.adv = {}
		forest.client.primed = false
	var state := fixture(state_name)
	# Freeze presentation time at the recorded server time: llvmpipe needs seconds per frame,
	# and a still must show the recorded moment (mid-battle, mid-walk), not a later one.
	forest.client.manual_clock_ms = float(state.get("adventure", {}).get("serverTime", -1.0))
	game.accept(state)
	# Recorded fixtures carry earlier battle reports: keep DRENOVAR's own result popup for the
	# battle shots only (it is the separate ordinary-loot line), not over unrelated scenes.
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()
	await process_frame

func look(target: Vector3, zoom: float) -> void:
	game.stage.target = target
	game.stage.zoom = zoom
	game.stage.update_camera(0, true)

func preload_actors(seconds := 1.2) -> void:
	# Lets threaded GLB loads finish so a frame never shows half-loaded actors.
	var until := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < until:
		await process_frame
	for i in 30:
		var loading := false
		for id in forest.actors.rigs:
			var rig = forest.actors.rigs[id]
			if is_instance_valid(rig) and rig.load_state == "loading":
				rig.poll_load(true)
				loading = loading or rig.load_state == "loading"
		await process_frame
		if not loading:
			break

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--out="):
			out = argument.trim_prefix("--out=")
		elif argument.begins_with("--prefix="):
			prefix = argument.trim_prefix("--prefix=")
		elif argument.begins_with("--shots="):
			only = argument.trim_prefix("--shots=").split(",", false)
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	forest = game.forest_game
	stub = StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub
	await preload_actors(0.5)

	if wanted("locked_card"):
		await fresh("locked_hall2")
		look(Vector3(-24, 0, -78), 64.0)
		forest.hud.locked_dismissed = false
		forest.locked_shown_for_excursion = false
		await create_timer(0.5).timeout
		await shoot("locked_card", 0.4)
		forest.hud.hide_locked()

	if wanted("intro_banner") or wanted("intro_horse") or wanted("intro_prompt"):
		await fresh("intro_offer")
		look(Vector3(5, 0, -4), 70.0)
		stub.replies = [fixture("intro_playing").merged({"events":[{"type":"intro_present", "seq":9001, "revision":1}]})]
		var started := Time.get_ticks_msec()
		while not forest.intro.presenting() and Time.get_ticks_msec() - started < 3000:
			await process_frame
		await shoot("intro_banner", 1.0)
		while forest.intro.elapsed < 6.3:
			await process_frame
		await shoot("intro_horse", 0.0)
		while forest.intro.elapsed < 12.4:
			await process_frame
		await shoot("intro_prompt", 0.2)
		stub.replies = [fixture("prologue")]
		forest.intro.on_skip()
		await process_frame

	if wanted("hud_forest"):
		await fresh("site01_trail_1of3")
		await preload_actors()
		look(Vector3(-17, 6, -62), 40.0)
		await shoot("hud_forest", 1.2)

	if wanted("route_moving"):
		await fresh("prologue_moving")
		await preload_actors()
		look(Vector3(-9, 6, -55), 34.0)
		await shoot("route_moving", 0.4)

	for item in [["mech_trail", "site01_trail_1of3", "lf_site_01"], ["mech_rune", "site02_rune_1of3", "lf_site_02"],
			["mech_winch", "site03_winch_solved", "lf_site_03"], ["mech_paired", "site04_plates_held", "lf_site_04"]]:
		if not wanted(item[0]):
			continue
		await fresh(item[1])
		await preload_actors()
		forest.mech.open(item[2])
		await shoot(item[0], 1.2)
		forest.mech.close()

	if wanted("guardian_battle"):
		await fresh("site01_battle_active")
		await preload_actors()
		look(forest.target_position("lf_site_01") + Vector3(0, 0, 3), 30.0)
		await shoot("guardian_battle", 1.0)

	if wanted("cage_open"):
		await fresh("site01_battle_victory")
		await preload_actors()
		look(forest.target_position("lf_site_01:cage"), 24.0)
		await create_timer(0.4).timeout
		forest.client.manual_clock_ms = -1.0
		game.accept(fixture("site01_cage_open"))
		await shoot("cage_unlock_key", 1.5)
		await shoot("cage_open_exit", 2.6)

	if wanted("escort"):
		await fresh("site01_escort_walking")
		await preload_actors()
		var walk: Dictionary = forest.client.escort()
		var mid: Vector3 = forest.actors.squad_focus()
		look(mid if mid != Vector3.INF else forest.target_position("lf_site_01"), 30.0)
		await shoot("escort_home", 1.0)

	if wanted("boss"):
		for pct in [10, 35, 60, 85]:
			await fresh("boss_battle_%d" % pct)
			await preload_actors()
			look(forest.target_position("lf_boss_ancient_maw") + Vector3(0, 0, 2), 46.0)
			await shoot("boss_telegraph_%d" % pct, 0.8)

	if wanted("rewards"):
		await fresh("completed")
		look(Vector3(5, 0, -4), 70.0)
		forest.panels.open_rewards()
		await shoot("rewards_panel", 0.6)
		forest.panels.open_journal()
		await shoot("journal_panel", 0.6)
		game.close_modal()

	print("FOREST_CAPTURE saved=", saved.size())
	for path in saved:
		print("  ", path)
	quit(0)
