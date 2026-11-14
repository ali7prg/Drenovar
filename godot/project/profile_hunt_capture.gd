extends SceneTree

# Renders a whole creature hunt in the city from a real server battle timeline
# (gameplay37/server/combat.mjs output): the army leaves through the gate, marches,
# reaches the creature, fights, the creature dies, the army returns. Frames are
# written as PNG for a video. Needs a real renderer:
#   xvfb-run -s "-screen 0 1280x600x24" godot --rendering-driver opengl3 --path . \
#     -s profile_hunt_capture.gd -- --battle=/abs/battle.json --out=/abs/dir [--fps=15] [--species=tenerys]

var out := "user://hunt"
var fps := 15.0

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var battle_path := ""
	var species := "tenerys"
	var level := 1
	var arrival_gap := 0.0
	# Recorded window in seconds from the march start (default: everything).
	var window_from := -1.5
	var window_to := 1.0e9
	var zoom := 34.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--battle="):
			battle_path = arg.trim_prefix("--battle=")
		elif arg.begins_with("--fps="):
			fps = float(arg.trim_prefix("--fps="))
		elif arg.begins_with("--species="):
			species = arg.trim_prefix("--species=")
		elif arg.begins_with("--level="):
			level = int(arg.trim_prefix("--level="))
		elif arg.begins_with("--from="):
			window_from = float(arg.trim_prefix("--from="))
		elif arg.begins_with("--to="):
			window_to = float(arg.trim_prefix("--to="))
		elif arg.begins_with("--zoom="):
			zoom = float(arg.trim_prefix("--zoom="))
		elif arg.begins_with("--poll-gap="):
			# Seconds between arrival and the state that reports the fight.
			arrival_gap = float(arg.trim_prefix("--poll-gap="))
	DirAccess.make_dir_recursive_absolute(out)
	var battle: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(battle_path))
	root.size = Vector2i(1280, 600)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.smoke = true
	if game.map_name != "city":
		await game.show_scene("city")
	var stage = game.stage
	var state: Dictionary = game.state.duplicate(true)
	var target: Dictionary = {}
	for encounter in state.get("encounters", []):
		if encounter.get("species") == species:
			target = encounter
			break
	if target.is_empty():
		target = state.encounters[0]
	target.species = species
	target.level = level
	target.patrol = []
	target.behavior = "idle"
	target.spec = battle.spec
	var beast: Vector3 = stage.point(target.position)
	var home := Vector3.ZERO
	for building in state.city.get("buildings", []):
		if str(building.get("type", "")).begins_with("MIL"):
			var at: Variant = game.plot_point(str(building.get("plotId", "")))
			if at != null:
				home = Vector3(at.x, 0, at.y)
	var path: Array = []
	var steps := 8
	for k in steps + 1:
		var q := home.lerp(beast, float(k) / steps)
		path.append({"x": q.x, "z": q.z})
	var party := {}
	for unit in battle.get("party", {}):
		party[unit] = int(battle.party[unit])
	var start := 1000000.0
	var travel := 16000.0
	var arrive := start + travel
	var ends := arrive + float(battle.duration)
	var back := ends + travel
	var army := {"id":"army-hunt", "status":"outbound", "target":target.id, "path":path, "units":party,
		"startsAt":start, "arrivesAt":arrive, "owner":state.get("playerId", "")}
	state.armies = [army]
	state.encounters = [target]
	stage.zoom = zoom
	var frame := 0
	var total_ms := minf(back - start + 3000.0, window_to * 1000.0)
	var step := 1000.0 / fps
	var t := start + window_from * 1000.0
	while t <= start + total_ms:
		# Server-side state as the client would hold it at time t.
		if t < arrive + arrival_gap * 1000.0:
			army.status = "outbound"
			target.status = "reserved"
		elif t < ends + 1500.0:
			army.status = "fighting"
			army.battleAt = arrive
			army.battleEndsAt = ends
			army.battle = {"events": battle.events}
			army.fallen = []
			target.status = "fighting"
		else:
			army.status = "returning"
			army.returnPath = path.duplicate()
			army.returnPath.reverse()
			army.returnStartsAt = ends
			army.returnsAt = back
			army.returnUnits = party
			target.status = "defeated" if battle.outcome == "victory" else "alive"
		stage.present_armies(state, t)
		for marker in stage.army_markers:
			stage.target = stage.target.lerp(marker.position - Vector3.UP * 2.6, 0.12 if frame > 0 else 1.0)
		stage.present_creatures(state, t, step / 1000.0)
		stage.update_camera(step / 1000.0, frame == 0)
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("%s/f_%04d.png" % [out, frame])
		frame += 1
		t += step
	print("HUNT_CAPTURE frames=", frame, " out=", out)
	quit(0)
