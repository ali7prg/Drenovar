extends SceneTree
## Premium UI stage 4b: stills and open times of the «Лес потерянных» interface (the bottom bar,
## hint, toasts and banner, the invitation, the intro card, the locked card, the battle header,
## the journal, the rewards, a mechanism). States are recorded realm fixtures through a stub
## transport, as in qa_forest_integration_shots.gd (no network).
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --rendering-method mobile -s qa_stage4b_forest.gd -- --shots=/abs/dir [--prefix=p_] [--only=a,b]
## Headless with --repeat=N: no stills; the journal, the rewards, the locked card and the intro
## card open N times and the median main-thread time of opens 2..N is printed beside the first.

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
var timings := {}
var repeat := 0

func _initialize() -> void:
	call_deferred("run")

func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))

func wanted(name: String) -> bool:
	return only.is_empty() or only.has(name)

func frames(count: int) -> void:
	for i in count:
		await process_frame

func shoot(name: String) -> void:
	# The stub transport never answers the game's own polls: keep the offline pill (rule 10)
	# out of the forest stills (banner_offline in qa_stage4b_shots.gd shows it).
	game.diagnostics.network_failures = 0
	game.diagnostics.server_failures = 0
	game.last_ok_msec = Time.get_ticks_msec()
	game.update_connection_notice()
	await RenderingServer.frame_post_draw
	if DisplayServer.get_name() == "headless":
		return
	root.get_texture().get_image().save_png(out.path_join(prefix + name + ".png"))
	saved.append(name)
	print("SHOT ", name, " t=", Time.get_ticks_msec())

func timed(name: String, action: Callable, undo := Callable()) -> void:
	var runs: Array = []
	for i in maxi(1, repeat):
		if i > 0:
			if undo.is_valid():
				undo.call()
			else:
				game.close_modal()
			await frames(3)
		var started := Time.get_ticks_usec()
		await action.call()
		runs.append((Time.get_ticks_usec() - started) / 1000.0)
		await process_frame
	var later: Array = runs.slice(1) if runs.size() > 1 else runs.duplicate()
	later.sort()
	timings[name] = {"first_ms": snappedf(runs[0], 0.01), "median_ms": snappedf(later[later.size() / 2], 0.01), "runs": runs.size()}

func fresh(state_name: String) -> void:
	game.close_modal()
	if forest.mech.is_open():
		forest.mech.close()
	forest.actors.on_stage_changed()
	forest.actors.first_state = true
	forest.client.adv = {}
	forest.client.primed = false
	var state := fixture(state_name)
	forest.client.manual_clock_ms = float(state.get("adventure", {}).get("serverTime", -1.0))
	game.showing_cached_state = true
	game.accept(state)
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()
	await frames(2)

func look(target: Vector3, zoom: float) -> void:
	game.stage.target = target
	game.stage.zoom = zoom
	game.stage.update_camera(0, true)

## The adventure row as forest_game.update_visibility shows it once the world is ready.
func show_bar(hud) -> void:
	hud.visible = true
	hud.bar.visible = true
	forest.guide_signature = ""
	forest.apply_guide(forest.guide())
	hud.layout()
	hud.hint.visible = not hud.hint_label.text.is_empty()

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--shots="):
			out = argument.trim_prefix("--shots=")
		elif argument.begins_with("--prefix="):
			prefix = argument.trim_prefix("--prefix=")
		elif argument.begins_with("--only="):
			only = argument.trim_prefix("--only=").split(",", false)
		elif argument.begins_with("--repeat="):
			repeat = int(argument.trim_prefix("--repeat="))
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	game.loopback = true
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	forest = await game.ensure_forest_game()
	stub = StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub
	await frames(10)
	var hud = forest.hud
	# The forest world itself is not attached: lavapipe renders it at seconds per frame. The
	# interface is driven as the game drives it, over the city (forest_game's frame loop is
	# paused so it does not hide the bar while the world is missing).
	forest.set_process(false)
	look(Vector3.ZERO, 68.0)
	if wanted("forest_bar"):
		await fresh("site02_rune_1of3")
		show_bar(hud)
		await frames(8)
		await shoot("forest_bar")
	if wanted("forest_toast"):
		hud.toast("Награда отложена: +120 дерева, +60 еды", "reward")
		hud.toast("Нет связи с лесом · повторяем", "network")
		hud.show_banner("Пленник освобождён", "Он идёт домой с вашим отрядом")
		await frames(16)
		await shoot("forest_toast")
		hud.hide_banner()
		for pill in hud.toasts.get_children():
			pill.queue_free()
	if wanted("forest_battle"):
		await fresh("site01_battle_active")
		show_bar(hud)
		hud.bar.hide()
		hud.hint.hide()
		hud.show_battle("Тенерис · страж просеки", 620.0, 900.0, "Готовит рывок — копейщики, держите строй", true, "1:12")
		await frames(8)
		await shoot("forest_battle")
		hud.hide_battle()
	if wanted("forest_journal"):
		await fresh("site02_rune_1of3")
		await timed("forest_journal", forest.panels.open_journal)
		await frames(8)
		await shoot("forest_journal")
		game.close_modal()
	if wanted("forest_rewards"):
		await timed("forest_rewards", forest.panels.open_rewards)
		await frames(8)
		await shoot("forest_rewards")
		game.close_modal()
	if wanted("forest_mech"):
		await fresh("site02_rune_1of3")
		forest.mech.open("lf_site_02")
		forest.mech.visible = true
		hud.visible = true
		hud.bar.hide()
		hud.hint.hide()
		await frames(12)
		await shoot("forest_mech")
		forest.mech.close()
	if wanted("forest_invite"):
		await fresh("intro_offer")
		show_bar(hud)
		hud.invite_button.text = forest.content.text("intro.start")
		hud.invite_button.show()
		hud.layout()
		await frames(8)
		await shoot("forest_invite")
		hud.invite_button.hide()
	if wanted("forest_intro_card"):
		hud.bar.hide()
		hud.hint.hide()
		await timed("forest_intro_card", forest.intro.show_static_card, func(): forest.intro.static_card.hide())
		await frames(12)
		await shoot("forest_intro_card")
		if is_instance_valid(forest.intro.static_card):
			forest.intro.static_card.hide()
	if wanted("forest_locked"):
		await fresh("locked_hall2")
		hud.bar.hide()
		hud.hint.hide()
		await timed("forest_locked", func(): hud.show_locked("hall"), hud.hide_locked)
		await frames(16)
		await shoot("forest_locked")
		hud.hide_locked()
	print("STAGE4B_FOREST_SHOTS ", JSON.stringify(saved))
	print("STAGE4B_FOREST_TIMINGS ", JSON.stringify(timings))
	quit(0)
