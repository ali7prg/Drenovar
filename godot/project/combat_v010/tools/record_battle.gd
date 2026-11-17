extends SceneTree

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
const CombatPresentation = preload("res://src/combat_presentation.gd")
const APPROACH_MS := 4000.0
const TAIL_MS := 4000.0

var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.trim_prefix("--").get_slice("=", 0)] = a.get_slice("=", 1)
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1280, 720)
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
	for c in JSON.parse_string(FileAccess.get_file_as_string("res://tests/combat_v010/server_combat_cases.json")).cases:
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
	enc.level = int(case.level)
	if not enc.has("spec"):
		enc.spec = {"id": str(enc.get("species", case.species)), "name": str(enc.get("species", case.species)).capitalize(), "hp": 1400}
	var species_models: Dictionary = game.data.creatureModels
	# --species=keep: the encounter's own creature (e.g. a city Tenerys) with the case's party and events.
	if args.get("species", "") != "keep" and species_models.has(case.species) and str(enc.spec.get("id", "")) != case.species:
		# The demo encounter is a Velkor; use the case's species and a neutral label.
		enc.species = case.species
		enc.spec = enc.spec.duplicate(true)
		enc.spec.id = case.species
		enc.spec.name = str(case.species).capitalize()
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
	for frame in frames:
		var now := begin + frame * (1000.0 / 30.0)
		if only > -1000.0 and absf((now - arrive) / 1000.0 - only) > 0.2 and frame > 3:
			continue
		if not times.is_empty() and not times.any(func(t): return absf((now - arrive) / 1000.0 - t) < 0.5 / 30.0):
			continue
		if span.size() == 2 and ((now - arrive) / 1000.0 < float(span[0]) or (now - arrive) / 1000.0 > float(span[1])):
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
		stage.update_camera(1.0 / 30.0, camera == "orbit")
		stage.present_armies(state, now)
		stage.present_creatures(state, now, 1.0 / 30.0)
		label.text = "%s · %s · battle clock %+.2f s" % [case.name, "v0.1.0" if args.get("flag", "on") == "on" else "legacy clips", (now - arrive) / 1000.0]
		await process_frame
	quit()
