extends SceneTree
# Build 1021 audit: the launch of the real app (main.tscn) with a saved login and a
# local copy of a city like the owner's (16 buildings at level V, the wall, felled
# trees), offline. Then the first "server answer" arrives with what changes while the
# app was closed (a few more felled trees, a finished building order). Prints the
# phases of the launch, every frame longer than 50 ms with its cause, and the cost of
# applying that answer.
#   cd godot/project && godot --headless --max-fps 60 --path . -s ../tools/profile_startup.gd
# Headless: CPU only (no GPU, no shader pipelines); --max-fps 60 paces the frames
# like the phone's display (a frame lasts at least 16.7 ms).
# --slice=3500 builds with the slice of build 1020 (Landscape.LAUNCH_SLICE_USEC off).
const SessionStore = preload("res://src/session_store.gd")
const OWNER_TYPES := ["ECO-05", "RES-01", "RES-02", "RES-03", "RES-04", "ECO-01", "ECO-02", "ECO-03", "ECO-04",
	"MIL-01", "MIL-02", "MIL-03", "SUP-01", "SUP-03", "SUP-04", "SUP-05"]
var args := {}

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.trim_prefix("--").get_slice("=", 0)] = a.get_slice("=", 1)
	call_deferred("run")

static func owner_state(data: Dictionary, felled: int) -> Dictionary:
	var state: Dictionary = data.demo.duplicate(true)
	state.playerId = "qa-startup-owner"
	var buildings: Array = []
	for n in OWNER_TYPES.size():
		buildings.append({"id": "building-%d" % n, "type": OWNER_TYPES[n], "plotId": data.plots[n].id, "level": 5})
	state.city.buildings = buildings
	state.city.kingdom.clearedPlots = data.plots.slice(0, OWNER_TYPES.size()).map(func(p): return p.id)
	state.city.progress.felled = data.woods.slice(0, felled).map(func(t): return t.id)
	return state

func run() -> void:
	root.size = Vector2i(1366, 630)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var endpoint := "http://127.0.0.1:9"
	SessionStore.forget()
	var token := "c".repeat(64) + "." + "d".repeat(64)
	SessionStore.save_session(token)
	var cached := owner_state(data, int(args.get("felled", "40")))
	SessionStore.save_state(token, cached, 1234.0, endpoint)
	# --cold=1: no town plan kept from an earlier launch (the first launch of a build).
	if args.get("cold", "0") == "1" and FileAccess.file_exists("user://town-plan.json"):
		DirAccess.remove_absolute(ProjectSettings.globalize_path("user://town-plan.json"))
	if args.get("slice", "") == "3500":
		var Landscape = load("res://src/landscape.gd")
		Landscape.launch_slices = false
	var started := Time.get_ticks_usec()
	var game = load("res://main.tscn").instantiate()
	game.endpoint = endpoint
	root.add_child(game)
	var phases := []
	var long_frames := []
	var previous := Time.get_ticks_usec()
	var launch_seen := true
	var stage_at := -1.0
	var finished_at := -1.0
	var frames := 0
	var steps := {}
	var build_from := -1.0
	while frames < 600:
		await process_frame
		frames += 1
		var now := Time.get_ticks_usec()
		var frame_ms := (now - previous) / 1000.0
		previous = now
		var t := (now - started) / 1000.0
		var launch = game.get_children().filter(func(n): return n is CanvasLayer and n.layer == 10)
		if stage_at < 0.0 and is_instance_valid(game.stage) and not game.scene_loading:
			stage_at = t
			phases.append(["city shown", snappedf(t, 1.0)])
		if launch_seen and launch.is_empty():
			launch_seen = false
			finished_at = t
			phases.append(["splash gone", snappedf(t, 1.0)])
		if frame_ms > 50.0:
			long_frames.append([snappedf(t, 1.0), snappedf(frame_ms, 1.0), "loading" if stage_at < 0.0 else "after city shown"])
		# Frames per launch step (the text on the launch screen).
		var step := "no splash"
		if not launch.is_empty():
			step = str(launch[0].status.text)
		if game.scene_loading:
			step += " / scene"
		steps[step] = steps.get(step, 0) + 1
		if step.begins_with("Готовим") and build_from < 0.0:
			build_from = t
		if finished_at > 0.0 and t - finished_at > 1500.0:
			break
	# The server's first answer: what changed while the app was closed.
	var answer := owner_state(data, int(args.get("felled", "40")) + int(args.get("more_felled", "3")))
	answer.serverTime = float(cached.serverTime) + 60000.0
	answer.economy_version = "DRENOVAR-V6-C1.0"
	if args.get("order", "1") == "1":
		answer.city.buildings[1].level = 5
		answer.city.kingdom.order = {"kind": "upgrade", "buildingId": "building-2", "plotId": data.plots[2].id, "type": "RES-02", "level": 6, "startedAt": answer.serverTime - 1000.0, "endsAt": answer.serverTime + 600000.0}
	var t0 := Time.get_ticks_usec()
	game.showing_cached_state = true
	game.accept(answer)
	var accept_ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("STARTUP_PROFILE ", JSON.stringify({"phases": phases, "long_frames": long_frames, "first_answer_ms": snappedf(accept_ms, 0.1),
		"frames": frames, "frames_per_step": steps, "city_build_ms": snappedf(stage_at - build_from, 1.0)}))
	SessionStore.forget()
	quit()
