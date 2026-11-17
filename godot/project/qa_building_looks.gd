extends SceneTree

# Reworked looks of build 53 (0.6.0 test 5 QA: VIS-01 warehouse/granary, VIS-02 market,
# VIS-03 quarry/iron mine) through the game's own state path (main.accept -> present):
# every upgrade step I->V keeps the level, the plot and the marker position, shows the
# level scene of that step and keeps the name plate; after a client restart (a second
# process that receives the saved state, as restore_account() does) all of it is the same.
#   godot --headless --path . -s qa_building_looks.gd                 # upgrade I->V, save
#   godot --headless --path . -s qa_building_looks.gd -- --restart    # fresh client, compare

const SAVE := "user://qa_building_looks.json"
const PLACED := [["ECO-01", "v1-1"], ["ECO-02", "v1-2"], ["ECO-03", "v1-5"], ["RES-02", "v1-3"], ["RES-03", "v1-4"]]

var checks := 0
var failures := 0
var game

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
		print("FAIL ", description)

func state_at(level: int, server_time: float) -> Dictionary:
	var state: Dictionary = game.data.demo.duplicate(true)
	state.serverTime = server_time
	var city: Dictionary = state.city
	city.buildings = [{"id": "building-hall", "type": "ECO-05", "plotId": "v1-0", "level": 5}]
	var cleared: Array = ["v1-0"]
	for entry in PLACED:
		city.buildings.append({"id": "building-" + entry[0], "type": entry[0], "plotId": entry[1], "level": level})
		cleared.append(entry[1])
	city.kingdom.clearedPlots = cleared
	return state

func plot_xz(id: String) -> Vector2:
	for plot in game.data.plots:
		if plot.id == id:
			return Vector2(float(plot.x), float(plot.z))
	return Vector2.INF

func snapshot() -> Dictionary:
	## building id -> {type, level, plot, marker [x,y,z], scene, title, on_screen}
	var stage = game.stage
	var out := {}
	var scenes := {}
	for child in stage.buildings.get_children():
		scenes[child.scene_file_path] = true
	for marker in stage.place_markers:
		if marker.get("kind", "") != "building":
			continue
		var b: Dictionary = marker.item
		if not str(b.id).begins_with("building-") or b.id == "building-hall":
			continue
		var level_model: Dictionary = stage.level_model_for(b.type, int(b.level))
		if level_model.is_empty():
			# levels that keep the original model (market I-II)
			level_model = {"path": game.data.models[game.data.types[b.type]].path}
		var p: Vector3 = marker.position
		stage.target = p
		stage.zoom = 40.0
		stage.update_camera(0, true)
		var anchor: Vector3 = p + Vector3.UP * 3.5
		var at: Vector2 = stage.camera.unproject_position(anchor)
		var view: Vector2 = root.get_visible_rect().size
		out[b.id] = {"type": b.type, "level": int(b.level), "plot": b.plotId, "marker": [p.x, p.y, p.z],
			"scene": level_model.get("path", ""), "scene_shown": scenes.has(level_model.get("path", "")),
			"title": game.building_title(b.type), "plates": game.building_plates.plates_visible(),
			"on_screen": at.x >= 0 and at.y >= 0 and at.x <= view.x and at.y <= view.y}
	return out

func verify(snap: Dictionary, level: int, tag: String) -> void:
	check(snap.size() == PLACED.size(), "%s: %d of %d buildings have a marker" % [tag, snap.size(), PLACED.size()])
	for entry in PLACED:
		var id: String = "building-" + entry[0]
		var s: Dictionary = snap.get(id, {})
		if s.is_empty():
			continue
		var xz := plot_xz(entry[1])
		check(s.level == level, "%s %s level %d, expected %d" % [tag, id, s.level, level])
		check(s.plot == entry[1], "%s %s on plot %s, expected %s" % [tag, id, s.plot, entry[1]])
		check(absf(float(s.marker[0]) - xz.x) < 0.001 and absf(float(s.marker[2]) - xz.y) < 0.001, "%s %s marker %s off plot %s" % [tag, id, str(s.marker), str(xz)])
		check(not str(s.scene).is_empty() and s.scene_shown, "%s %s level scene %s not shown" % [tag, id, s.scene])
		check(not str(s.title).is_empty() and s.title != entry[0], "%s %s has no name" % [tag, id])
		check(s.plates and s.on_screen, "%s %s name plate hidden (plates=%s on_screen=%s)" % [tag, id, s.plates, s.on_screen])

func run() -> void:
	var restart := "--restart" in OS.get_cmdline_user_args()
	root.size = Vector2i(1100, 760)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	if not restart:
		var first := {}
		var time := 1.8e12
		for level in range(1, 6):
			time += 60000.0
			game.accept(state_at(level, time))
			await process_frame
			var snap := snapshot()
			verify(snap, level, "upgrade L%d" % level)
			if level == 1:
				first = snap
			for id in snap:
				# the marker never moves on an upgrade
				check(first.has(id) and str(first[id].marker) == str(snap[id].marker), "upgrade L%d %s marker moved" % [level, id])
			print("STEP L%d %s" % [level, JSON.stringify(snap.keys().map(func(k): return "%s:%s" % [snap[k].type, snap[k].scene.get_file()]))])
		var file := FileAccess.open(SAVE, FileAccess.WRITE)
		file.store_string(JSON.stringify({"state": game.state, "snapshot": snapshot()}))
		file.close()
		print("SAVED ", ProjectSettings.globalize_path(SAVE))
	else:
		check(FileAccess.file_exists(SAVE), "run without --restart first")
		var saved: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SAVE))
		game.accept(saved.state)
		await process_frame
		var snap := snapshot()
		verify(snap, 5, "restart")
		for id in saved.snapshot:
			var before: Dictionary = saved.snapshot[id]
			var after: Dictionary = snap.get(id, {})
			check(int(before.level) == int(after.get("level", -1)), "restart %s level %s -> %s" % [id, str(before.level), str(after.get("level"))])
			for key in ["type", "plot", "scene", "title"]:
				check(str(before.get(key)) == str(after.get(key)), "restart %s %s %s -> %s" % [id, key, str(before.get(key)), str(after.get(key))])
			check(str(before.marker) == str(after.get("marker")), "restart %s marker %s -> %s" % [id, str(before.marker), str(after.get("marker"))])
			print("RESTART %s L%d %s plot=%s marker=%s name=%s" % [id, after.level, str(after.scene).get_file(), after.plot, str(after.marker), after.title])
	print("QA_BUILDING_LOOKS %s checks=%d failures=%d" % ["restart" if restart else "upgrade", checks, failures])
	quit(1 if failures > 0 else 0)
