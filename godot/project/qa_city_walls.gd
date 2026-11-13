extends SceneTree

# City wall checks: no wall at town hall I, a closed ring from hall II that grows
# with the hall, every building and the troop base inside, gates on dry ground,
# only plots inside the wall offered for building, "walls and gate" plate on the
# main gate. With --out=DIR (and a real renderer) it also saves captures:
#   xvfb-run -s "-screen 0 1366x630x24" godot --rendering-driver opengl3 --path . \
#     -s qa_city_walls.gd -- --out=/abs/dir

var failures := 0

func check(condition: bool, label: String) -> void:
	if condition:
		print("PASS ", label)
	else:
		failures += 1
		printerr("FAIL ", label)

func _initialize() -> void:
	call_deferred("run")

func set_hall(game, level: int) -> void:
	for building in game.state.city.buildings:
		if building.type == "ECO-05":
			building.level = level

func add_building(game, type: String, plot: String, level := 1) -> void:
	game.state.city.buildings.append({"id": "building-" + plot, "type": type, "plotId": plot, "level": level})
	var cleared: Array = game.state.city.kingdom.clearedPlots
	if not plot in cleared:
		cleared.append(plot)

func present(game) -> void:
	await game.stage.present_city(game.state)
	game.stage.update_visible_batches()
	for i in 4:
		await process_frame

func capture(game, out: String, tag: String, target: Vector3, zoom: float) -> void:
	if out.is_empty():
		return
	var stage = game.stage
	stage.target = target
	stage.zoom = zoom
	stage.update_camera(0, true)
	stage.update_visible_batches()
	for i in 14:
		await process_frame
	await RenderingServer.frame_post_draw
	var path := "%s/walls_%s.png" % [out, tag]
	root.get_texture().get_image().save_png(path)
	print("CAPTURE ", path, " draw_calls=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))

func ring_ok(stage) -> bool:
	var walls = stage.walls
	for i in walls.SAMPLES:
		var r: float = walls.radii[i]
		if not is_finite(r) or r < 20.0 or r > 120.0:
			return false
	return true

func run() -> void:
	var out := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
	if not out.is_empty():
		DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.smoke = true
	var stage = game.stage
	var walls = stage.walls
	check(not walls.visible and stage.get_node_or_null("CityWalls") == null, "hall I: no wall")
	var offered_l1: int = stage.empty_plots.size()
	set_hall(game, 2)
	await present(game)
	check(walls.visible and is_instance_valid(walls.node), "hall II: wall is built")
	check(ring_ok(stage), "hall II: closed ring with sane radii")
	var r2: float = walls.radius_at(-5.0, 60.0)
	for marker in stage.place_markers:
		if marker.kind == "building":
			check(walls.inside(marker.position.x, marker.position.z, 8.0), "inside wall: " + str(marker.item.type))
	for plot in stage.empty_plots:
		if not str(plot.item.id).begins_with("site-"):
			check(walls.inside(plot.position.x, plot.position.z, 6.0), "offered plot inside wall: " + str(plot.item.id))
	check(not walls.gates.is_empty(), "main gate exists")
	for g in walls.gates:
		var p: Vector2 = walls.wall_point(g)
		check(stage.sample_city(p.x, p.y) > -0.1, "gate %d on dry ground" % g)
	var trees_on_wall := 0
	for tree in stage.selectable_trees:
		var at: Array = tree.p
		if walls.blocks(float(at[0]), float(at[2])):
			trees_on_wall += 1
	check(trees_on_wall == 0, "no trees on the wall band")
	await capture(game, out, "hall2_overview", Vector3(-5, 0, 2), 128.0)
	await capture(game, out, "hall2_gate", walls.main_gate, 46.0)
	# More buildings, a bigger hall: the yard grows and keeps them all inside.
	set_hall(game, 4)
	for entry in [["RES-02", "v1-17"], ["SUP-03", "v1-6"], ["SUP-04", "v1-16"], ["RES-03", "v1-27"], ["ECO-03", "v1-22"]]:
		add_building(game, entry[0], entry[1])
	game.state.city.military.garrison = {"x": -38.0, "z": 44.0, "elevation": stage.sample_city(-38.0, 44.0) + 0.65, "halfWidth": 14, "halfDepth": 11}
	await present(game)
	check(ring_ok(stage), "hall IV: closed ring")
	check(walls.radius_at(-5.0, 60.0) > r2, "hall IV: yard is wider than at hall II")
	check(stage.empty_plots.size() >= offered_l1, "hall IV: at least as many plots as at hall I")
	for marker in stage.place_markers:
		if marker.kind == "building" and not marker.get("wall", false):
			check(walls.inside(marker.position.x, marker.position.z, 8.0), "hall IV inside wall: " + str(marker.item.type))
	var district: Dictionary = game.state.city.military.garrison
	for corner in [Vector2(-14, -11), Vector2(14, -11), Vector2(-14, 11), Vector2(14, 11)]:
		var p: Vector2 = Vector2(district.x, district.z) + corner
		check(absf(p.distance_to(walls.center) - walls.radius_at(p.x, p.y)) > 2.0, "wall clear of troop base corner " + str(corner))
	var gate_plate := false
	for marker in stage.place_markers:
		if marker.get("wall", false):
			gate_plate = marker.item.type == "SUP-03" and marker.position.distance_to(walls.main_gate) < 8.0
	check(gate_plate, "walls-and-gate plate stands on the main gate")
	check(walls.gates.size() >= 2, "hall IV: side gates")
	await capture(game, out, "hall4_overview", Vector3(-5, 0, 4), 150.0)
	await capture(game, out, "hall4_gate", walls.main_gate, 40.0)
	# Same table as the server patch city-defence-v1 (gameplay37/tests/city-defence.mjs).
	var CityDefence = load("res://src/city_defence.gd")
	var s2: Dictionary = CityDefence.stats(2, 0, 0)
	var s5: Dictionary = CityDefence.stats(5, 5, 5)
	check(not CityDefence.stats(1, 0, 0).standing and CityDefence.stats(1, 0, 0).fort_power == 0, "defence table: no wall at hall I")
	check(s2.towers == 8 and s2.archers == 16 and s2.fort_power == 288 and s2.defence_pct == 4 and s2.loss_cut_pct == 2, "defence table matches server at hall II")
	check(s5.towers == 14 and s5.archers == 112 and s5.fort_power == 5376 and s5.defence_pct == 56 and s5.loss_cut_pct == 28, "defence table matches server at top level")
	# The look follows the level of "walls and gate": stone towers from 3, a stone curtain at 5.
	check(walls.node.get_node_or_null("curtain_planks") != null and walls.node.get_node_or_null("tower_body_planks") != null, "walls and gate I: timber palisade")
	for building in game.state.city.buildings:
		if building.type == "SUP-03":
			building.level = 5
	set_hall(game, 5)
	await present(game)
	check(walls.node.get_node_or_null("curtain_stone_wall") != null and walls.node.get_node_or_null("merlons") != null, "walls and gate V: stone curtain with battlements")
	check(walls.node.get_node_or_null("tower_body_stone_wall") != null, "walls and gate V: stone towers")
	await capture(game, out, "hall5_wall5_gate", walls.main_gate, 40.0)
	check(ring_ok(stage), "hall V: closed ring")
	await capture(game, out, "hall5_overview", Vector3(-5, 0, 4), 175.0)
	# Defence panel: wall, yard and watchtower numbers.
	game.show_city_defence()
	await process_frame
	check(game.modal.visible and game.modal_title.text == "Оборона поселения", "defence panel opens")
	var text := ""
	for child in game.modal_body.find_children("*", "Label", true, false):
		text += child.text + "\n"
	check(text.contains("Мощь укреплений") and text.contains("Лучники на башне") and text.contains("Двор"), "defence panel shows wall, yard and watchtower")
	check(text.contains("только гарнизон"), "defence panel says the server does not apply the bonus yet")
	await capture(game, out, "defence_panel", walls.main_gate, 60.0)
	game.close_modal()
	var tower: Dictionary = {}
	for building in game.state.city.buildings:
		if building.type == "SUP-04":
			tower = building
	game.inspect_building(tower)
	await process_frame
	text = ""
	for child in game.modal_body.find_children("*", "Label", true, false):
		text += child.text + "\n"
	check(text.contains("Сторожевая башня · ур. 1") and text.contains("→ +6%"), "watchtower panel shows its function and next level")
	game.close_modal()
	print("RESULT failures=%d" % failures)
	quit(1 if failures > 0 else 0)
