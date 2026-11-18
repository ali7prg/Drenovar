extends SceneTree

# creatures-v2 capture: combat_v010/tools/record_battle.gd (real game scene, real server simulator
# result, offline) plus --cases=<res://...json> and --png=<abs prefix> (one PNG per recorded frame).
#   DISPLAY=:99 godot --path godot/project --rendering-method gl_compatibility --audio-driver Dummy \
#     -s ../art/creatures-v2/tools/capture_battle.gd -- --case=mixed_all_types_velkor --camera=fixed --png=/abs/out/v

# Records one hunt of the real game scene (world map, real models, real landscape
# code) from a real simulator result (tests/combat_v010/server_combat_cases.json).
# Offline: unreachable loopback endpoint. The scene clock advances exactly 1/30 s per
# rendered frame, so use Godot Movie Maker for a frame-exact video:
#
#   xvfb-run -s "-screen 0 1280x720x24" godot --path godot/project --rendering-method gl_compatibility \
#     --audio-driver Dummy --fixed-fps 30 --write-movie OUT.avi \
#     -s res://combat_v010/tools/record_battle.gd -- --case=mixed_all_types_velkor --flag=on --camera=fixed
#
# --flag=on|off   v0.1.0 presenter or the legacy clips (same scene, same camera)
# --camera=fixed|orbit|close
# The on-screen label shows case, mode and the battle clock for frame comparison.

const CombatV010 = preload("res://combat_v010/runtime/combat_v010_presenter.gd")
const CreatureVisualsRef = preload("res://src/creature_visuals.gd")
const CombatPresentation = preload("res://src/combat_presentation.gd")
const APPROACH_MS := 4000.0
const TAIL_MS := 4000.0

var args := {}

var shot := 0

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.trim_prefix("--").get_slice("=", 0)] = a.get_slice("=", 1)
	call_deferred("run")

func save_frame() -> void:
	if not args.has("png"):
		return

	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	if img != null:
		img.save_png("%s_%04d.png" % [args.png, shot])
	shot += 1

func run() -> void:
	root.size = Vector2i(int(args.get("w", "1280")), int(args.get("h", "720")))
	CombatV010.set_enabled(args.get("flag", "on") == "on")
	var game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	# --scene=city: a city hunt outside the walls (the encounter of that level, or --x/--z).
	var scene: String = args.get("scene", "world")
	if game.map_name != scene:
		await game.show_scene(scene)
	for child in game.get_children():
		if child is CanvasLayer or child is Control:
			child.visible = false
	var stage = game.stage
	# The whole collision-checked plan at once (a phone refines it while the column walks).
	stage.engage_sync = args.get("sync", "1") == "1"
	var case: Dictionary = {}
	for c in JSON.parse_string(FileAccess.get_file_as_string(args.get("cases", "res://tests/combat_v010/server_combat_cases.json"))).cases:
		if c.name == args.get("case", "mixed_all_types_velkor"):
			case = c
	var state: Dictionary = game.state.duplicate(true)
	var holder: Dictionary = state.world if scene == "world" else state
	var enc: Dictionary = holder.encounters[0]
	if scene == "city":
		for e in holder.encounters:
			if int(e.level) == int(case.level): enc = e
		holder.encounters = [enc]
	enc.patrol = []
	if scene == "world" or args.has("x"):
		enc.position = {"x": float(args.get("x", "-50")), "z": float(args.get("z", "-30"))}
	# --level=N shows the creature at another level (look only: the party, events and timing stay the case's)
	enc.level = int(args.get("level", str(case.level)))
	if not enc.has("spec"):
		enc.spec = {"id": str(enc.get("species", case.species)), "name": str(enc.get("species", case.species)).capitalize(), "hp": 1400}
	var species_models: Dictionary = game.data.creatureModels
	# --species=keep: the encounter's own creature (e.g. a city Tenerys) with the case's party and events.
	if args.get("species", "") != "keep" and species_models.has(case.species) and str(enc.spec.get("id", "")) != case.species:
		# The demo encounter is a Velkor; use the case's species and a neutral label.
		enc.species = case.species
		enc.spec = enc.spec.duplicate(true)
		enc.spec.id = case.species
		# the catalog name the server sends with the encounter (creatures-v2 registry keeps the same names)
		enc.spec.name = str(CreatureVisualsRef.entry(case.species).get("name", str(case.species).capitalize()))
	var at: Vector3 = stage.point(enc.position)
	var arrive := 200000.0
	var walk := 14000.0
	var path := [{"x": at.x - 30.0, "z": at.z + 26.0}, {"x": at.x - 12.0, "z": at.z + 8.0}, {"x": at.x, "z": at.z}]
	if scene == "city":
		# From the town toward the creature (the column comes out of the walls).
		var out := Vector3(at.x, 0.0, at.z).normalized()
		path = [{"x": at.x - out.x * 30.0, "z": at.z - out.z * 30.0}, {"x": at.x - out.x * 14.0, "z": at.z - out.z * 14.0}, {"x": at.x, "z": at.z}]
	var source := {"id": "army-rec", "status": "outbound", "target": enc.id, "worldKind": "creature", "path": path,
		"units": case.party.duplicate(), "startsAt": arrive - walk, "arrivesAt": arrive, "battleAt": arrive,
		"battleEndsAt": arrive + float(case.result.duration), "battle": {"events": case.result.events.duplicate(true)}, "fallen": [],
		"returnStartsAt": arrive + float(case.result.duration), "returnsAt": arrive + float(case.result.duration) + walk}
	var shown: Dictionary = source.duplicate(true)
	CombatPresentation.stretch(shown, {})  # the game's own presentation copy of a short fight
	var ends := float(shown.battleEndsAt)
	var back: Array = path.duplicate(); back.reverse()
	var victory: bool = case.result.outcome == "victory"
	# Frame the fight (the creature, not the column) in the middle of the picture.
	stage.target = at + Vector3(float(args.get("frame_dx", "0")), 0, float(args.get("frame_dz", "-4"))).rotated(Vector3.UP, float(args.get("yaw", "0")))
	var label := Label.new()
	label.add_theme_font_size_override("font_size", 22)
	label.position = Vector2(16, 12)
	var layer := CanvasLayer.new(); layer.layer = 100; layer.add_child(label)
	root.add_child(layer)
	var camera: String = args.get("camera", "fixed")
	stage.zoom = float(args.get("zoom", "14" if camera == "close" else "24"))
	stage.world_yaw = float(args.get("yaw", "0"))
	stage.update_camera(0, true)
	var begin := arrive - APPROACH_MS
	var finish := ends + TAIL_MS
	var frames := int((finish - begin) / (1000.0 / 30.0))
	var only := float(args.get("only", "-100000")) # preview: a few frames around this battle time (s)
	# --times=a,b,c: one frame at each of these battle times (s), for a pose sheet.
	var times: Array = Array(str(args.get("times", "")).split(",", false)).map(func(t): return float(t))
	# --range=a:b: only the frames between these battle times (s).
	var span: PackedStringArray = str(args.get("range", "")).split(":", false)
	# --every=N renders one frame in N of the 30 fps scene clock (a 30/N fps preview, same timeline)
	var every := int(args.get("every", "1"))
	# --follow: the camera keeps the creature actor in the middle of the picture (close-ups)
	var follow := func() -> void:
		var tracked: Node3D = stage.creatures.get_node_or_null(NodePath(str(enc.id)))
		if args.has("follow") and tracked != null:
			# The world camera looks at a point 1 m above sea level: on a hill the body would sit high in the
			# picture, so the target moves along the view ray to where it passes the body (1.5 m above ground).
			var lift := 0.0
			if scene == "world":
				lift = -(tracked.global_position.y + 1.5 - 1.0) / tan(stage.WORLD_CAMERA_TILT)
			stage.target = Vector3(tracked.global_position.x, 0.0, tracked.global_position.z) \
				+ Vector3(float(args.get("frame_dx", "0")), 0, float(args.get("frame_dz", "0")) + lift).rotated(Vector3.UP, float(args.get("yaw", "0")))
	for frame in frames:
		if frame % every != 0:
			continue
		var now := begin + frame * (1000.0 / 30.0)
		if only > -1000.0 and absf((now - arrive) / 1000.0 - only) > 0.2 and frame > 3:
			continue
		if not times.is_empty() and not times.any(func(t): return absf((now - arrive) / 1000.0 - t) < 0.5 / 30.0):
			continue
		if span.size() == 2 and ((now - arrive) / 1000.0 < float(span[0]) or (now - arrive) / 1000.0 > float(span[1])):
			# --warm=S: the S seconds before the range are simulated without drawing (battle plan, canopy
			# clearing and camera settle as in the game), so the first saved frame is not a cold start.
			if (now - arrive) / 1000.0 < float(span[0]) and (now - arrive) / 1000.0 >= float(span[0]) - float(args.get("warm", "0")):
				var warm_army: Dictionary = shown.duplicate(true)
				warm_army.status = "outbound" if now < arrive else "fighting"
				enc.status = "alive" if now < arrive else "fighting"
				holder.armies = [warm_army]
				follow.call()
				stage.update_camera(every / 30.0, camera == "orbit")
				stage.present_armies(state, now)
				stage.present_creatures(state, now, every / 30.0)
			continue
		var army: Dictionary = shown.duplicate(true)
		if now < arrive:
			army.status = "outbound"; enc.status = "alive"
		elif now < ends:
			army.status = "fighting"; enc.status = "fighting"
		else:
			army.status = "returning"; army.returnPath = back
			army.returnUnits = case.result.get("surviving", {}) if not case.result.get("surviving", {}).is_empty() else case.party
			enc.status = "defeated" if victory else "alive"
			if victory: enc.hp = 0
		holder.armies = [army]
		if camera == "orbit":
			stage.world_yaw = float(args.get("yaw", "0")) + frame * 0.006
		follow.call()
		stage.update_camera(every / 30.0, camera == "orbit")
		stage.present_armies(state, now)
		stage.present_creatures(state, now, every / 30.0)
		label.text = "%s · %s · battle clock %+.2f s" % [case.name, "creatures-v2" if CreatureVisualsRef.active(str(enc.get("species", case.species))) else "v0.1.0", (now - arrive) / 1000.0]
		if args.has("debug_creature"):
			# --debug_creature: the creature actor's state per rendered frame (visibility, LOD ranges, distance)
			var actor: Node3D = stage.creatures.get_node_or_null(NodePath(str(enc.id)))
			var row := {"t": snappedf((now - arrive) / 1000.0, 0.01), "actor": actor != null}
			if actor != null:
				var cam_pos: Vector3 = stage.camera.global_position
				row.visible = actor.is_visible_in_tree()
				row.dist = snappedf(cam_pos.distance_to(actor.global_position), 0.01)
				row.y = snappedf(actor.global_position.y, 0.01)
				row.scale = snappedf(actor.scale.x, 0.001)
				row.clip = str(actor.get_meta("clip", ""))
				var parts := []
				for part: GeometryInstance3D in actor.find_children("*", "GeometryInstance3D", true, false):
					parts.append("%s v=%s b=%.1f±%.1f e=%.1f±%.1f" % [part.name.right(18), part.visible, part.visibility_range_begin, part.visibility_range_begin_margin, part.visibility_range_end, part.visibility_range_end_margin])
				row.parts = parts
			print("CREATURE_DEBUG ", JSON.stringify(row))
		await process_frame
		await save_frame()
	quit()
