extends SceneTree

# Market (ECO-03) IV -> V on a real order of the local server v92 (godot/tools/test-realm.mjs
# with DRENOVAR_TEST_MARKET_IV=1: town hall V, market IV; DRENOVAR_TEST_ORDER_SECONDS shortens
# the accepted upgrade order for the recording). Build 59 pilot.
#   phase 1:  -- --server=http://127.0.0.1:8417 --out=/abs/dir
#             upgrade through main.command (the "Улучшить" button), fixed camera frames in real
#             time; at ~35 % the map is opened and the city entered again; at ~55 % the client
#             process ends (the order keeps running on the server).
#   phase 2:  -- --server=http://127.0.0.1:8417 --out=/abs/dir --restart
#             a new client process signs in with the saved session, finds the same order and
#             the stage for the time left, records to the end and checks the finished V.
# Checks: the stage shown is the one of the order's own clock (start, after return, after
# restart), IV stands at the start, the market keeps its plot and marker, scaffolding and
# workers are gone after the end, the V scene stands and the walks of V are clear.

const BuildReveal = preload("res://src/build_reveal.gd")
const CityWorks = preload("res://src/city_works.gd")
const MARKET := "building-market-qa"

var checks := 0
var failures := 0
var game
var out := "user://market_qa"
var frame_no := 0
var log_lines: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

var order_started := 0.0

func note(line: String) -> void:
	if order_started > 0.0 and is_instance_valid(game):
		line = "[t+%5.1f s] %s" % [(game.timer_now() - order_started) / 1000.0, line]
	print(line)
	log_lines.append(line)

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
		note("FAIL " + description)
	else:
		note("ok   " + description)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

func market() -> Dictionary:
	for b in game.state.city.buildings:
		if b.id == MARKET:
			return b
	return {}

func order() -> Dictionary:
	var city: Dictionary = game.state.city
	var k: Dictionary = city.get("kingdom", city.get("legacyUpgrades", {})) if city.get("kingdom") is Dictionary or city.get("legacyUpgrades") is Dictionary else {}
	for o in [k.get("order"), k.get("order2")]:
		if o is Dictionary and o.get("buildingId", "") == MARKET and o.get("kind", "") == "upgrade":
			return o
	return {}

func marker_position() -> Variant:
	for marker in game.stage.place_markers:
		if marker.get("kind", "") == "building" and marker.item.id == MARKET:
			return marker.position
	return null

func shown_clock() -> float:
	## build clock the upgrade scene is drawn at (shader parameter of the new level)
	var works = game.stage.works
	if works.reveal_to.is_empty():
		return -1.0
	return float((works.reveal_to[0] as ShaderMaterial).get_shader_parameter("build_t"))

func expected_clock(o: Dictionary) -> float:
	var started := float(o.startedAt)
	var ends := float(o.endsAt)
	return CityWorks.build_clock(clampf((game.timer_now() - started) / maxf(ends - started, 1.0), 0.0, 1.0))

func progress(o: Dictionary) -> float:
	if o.is_empty():
		return 1.0
	return clampf((game.timer_now() - float(o.startedAt)) / maxf(float(o.endsAt) - float(o.startedAt), 1.0), 0.0, 1.0)

func aim(at: Vector3) -> void:
	game.stage.target = at
	game.stage.zoom = 30.0
	game.stage.update_camera(0, true)

func shoot(tag := "") -> void:
	await RenderingServer.frame_post_draw
	var path := "%s/frame_%s_%04d%s.png" % [out, "b" if "--restart" in OS.get_cmdline_user_args() else "a", frame_no, tag]
	root.get_texture().get_image().save_png(path)
	frame_no += 1

func record_until(stop: Callable, at: Vector3, fps := 1.0) -> void:
	var next := Time.get_ticks_msec()
	while not stop.call():
		if Time.get_ticks_msec() >= next:
			aim(at)
			await shoot()
			next += int(1000.0 / fps)
		await process_frame

func run() -> void:
	var restart := "--restart" in OS.get_cmdline_user_args()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
	DirAccess.make_dir_recursive_absolute(out)
	DisplayServer.window_set_size(Vector2i(1366, 630))
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var connected: bool = await wait_until(func(): return not game.scene_loading and is_instance_valid(game.stage) and not game.player_id.is_empty() and game.state.get("city", {}).get("buildings") is Array and not market().is_empty(), 90.0)
	check(connected, "%s: signed in on the local server v92, market found" % ("restart" if restart else "start"))
	if not connected:
		finish()
		return
	note("client version %s" % ProjectSettings.get_setting("application/config/version"))
	var b := market()
	var plot: String = b.plotId
	var site_at: Vector3 = game.stage.work_sites.get(plot, Vector3.ZERO)
	var marker0: Variant = marker_position()
	note("market %s level %d on plot %s, marker %s" % [MARKET, int(b.level), plot, str(marker0)])
	if not restart:
		check(int(b.level) == 4, "market starts at level IV")
		await game.command({"kind": "kingdom", "action": "enter"})
		for i in 20:
			aim(site_at)
			await process_frame
		await shoot("_before")
		# the "Улучшить" button sends exactly this command
		var ok: bool = await game.command({"kind": "kingdom", "action": "upgrade", "buildingId": MARKET, "expectedLevel": 4})
		check(ok, "upgrade IV -> V accepted by the server: " + str(game.message.text))
		var o := order()
		check(not o.is_empty(), "the server holds the upgrade order")
		if o.is_empty():
			finish()
			return
		order_started = float(o.startedAt)
		note("order startedAt=%d endsAt=%d (%.0f s)" % [int(o.startedAt), int(o.endsAt), (float(o.endsAt) - float(o.startedAt)) / 1000.0])
		for i in 6:
			await process_frame
		var c0 := shown_clock()
		check(c0 >= 0.0 and c0 < 0.05 and game.stage.works.site_from != null and game.stage.works.site_from.visible,
			"at the start the market IV stands on the plot (clock %.3f)" % c0)
		await record_until(func(): return progress(order()) >= 0.35, site_at)
		# out to the world map and back
		var before := progress(order())
		note("open the world map")
		game.show_scene("world")
		await wait_until(func(): return not game.scene_loading and game.map_name == "world", 60.0)
		for i in 10:
			await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out + "/world_map.png")
		note("world map opened at %.0f %% of the order" % (before * 100.0))
		await create_timer(4.0).timeout
		note("back to the city")
		game.show_scene("city")
		await wait_until(func(): return not game.scene_loading and game.map_name == "city", 60.0)
		for i in 8:
			aim(site_at)
			await process_frame
		var o2 := order()
		var expect := expected_clock(o2)
		var got := shown_clock()
		check(absf(got - expect) < 0.02 and got > 0.2, "after the return the stage of the time left is shown (clock %.3f, order clock %.3f, %.0f %% of the order)" % [got, expect, progress(o2) * 100.0])
		await shoot("_return")
		var m1: Variant = marker_position()
		check(str(m1) == str(marker0), "after the return the marker stands where it stood (%s)" % str(m1))
		await record_until(func(): return progress(order()) >= 0.55, site_at)
		note("client closed at %.0f %% of the order (clock %.3f)" % [progress(order()) * 100.0, shown_clock()])
		var f := FileAccess.open(out + "/phase1.json", FileAccess.WRITE)
		f.store_string(JSON.stringify({"marker": [marker0.x, marker0.y, marker0.z], "plot": plot, "order": order(), "frames": frame_no}))
		f.close()
		finish()
		return
	# ---- restart: a new client process
	var saved: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(out + "/phase1.json"))
	var o := order()
	order_started = float(saved.order.startedAt)
	check(not o.is_empty() and int(o.startedAt) == int(saved.order.startedAt) and int(o.endsAt) == int(saved.order.endsAt),
		"after the restart the same order runs (endsAt %s)" % str(o.get("endsAt")))
	for i in 10:
		aim(site_at)
		await process_frame
	if not o.is_empty():
		var expect := expected_clock(o)
		var got := shown_clock()
		check(absf(got - expect) < 0.02 and got > 0.4, "after the restart the stage of the time left is shown (clock %.3f, order clock %.3f, %.0f %% of the order)" % [got, expect, progress(o) * 100.0])
	await shoot("_restart")
	check(int(market().level) == 4 and market().plotId == saved.plot, "during the works the market is level IV on plot %s" % saved.plot)
	await record_until(func(): return int(market().get("level", 0)) == 5 and order().is_empty(), site_at)
	for i in 30:
		aim(site_at)
		await process_frame
	for i in 6:
		await shoot("_after")
	var m: Dictionary = market()
	check(int(m.level) == 5, "the order ended: market level V")
	check(m.plotId == saved.plot, "the market stays on plot %s" % saved.plot)
	var mk: Variant = marker_position()
	check(mk is Vector3 and absf(mk.x - float(saved.marker[0])) < 0.001 and absf(mk.z - float(saved.marker[2])) < 0.001, "the marker stays where it was (%s)" % str(mk))
	var works = game.stage.works
	check(not (is_instance_valid(works.site_node) and works.site_node.visible), "scaffolding and the building site are gone")
	var scenes := []
	for child in game.stage.buildings.get_children():
		if child.visible:
			scenes.append(child.scene_file_path)
	var v_scene: String = game.stage.level_model_for("ECO-03", 5).path
	check(scenes.count(v_scene) == 1, "one finished V scene stands (%d)" % scenes.count(v_scene))
	check(not scenes.has(game.stage.level_model_for("ECO-03", 4).path), "no IV scene is left")
	finish()

func finish() -> void:
	note("QA_MARKET_UPGRADE %s checks=%d failures=%d" % ["restart" if "--restart" in OS.get_cmdline_user_args() else "start", checks, failures])
	var f := FileAccess.open(out + "/qa_%s.log" % ("restart" if "--restart" in OS.get_cmdline_user_args() else "start"), FileAccess.WRITE)
	f.store_string("\n".join(log_lines) + "\n")
	f.close()
	quit(1 if failures > 0 else 0)
