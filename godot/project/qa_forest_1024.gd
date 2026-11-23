extends SceneTree
## Build 1024, stage 3: «Лес потерянных» as the owner played it on an iPhone, measured end to end with
## hard numbers. The real game scene (main.tscn, lazy forest layer) plays the adventure against a LOCAL
## copy of the live V6 Worker with the adventure switched on (never production or staging): the same
## harness as qa_build_e2e.gd (releaseWorker().fetch over an in-memory SQLite "D1", the deployed
## worker.mjs kept outside the repository) with env DRENOVAR_V6_ADVENTURE="true" and these controls:
##   POST /test/reset · /test/clock?time=<ms>[&freeze=1|0] · /test/latency?ms=<n> (every /api request
##   answers n ms later, half before and half after the server) · /test/hall?level=<n> ·
##   /test/army {units} · /test/legacy {layout} (an earlier-model settlement, like the owner's city) ·
##   /qa/requests (log with server CPU ms per request).
##
## Run (headless, checks):
##   godot --headless --path godot/project -s qa_forest_1024.gd -- --server=http://127.0.0.1:8801 \
##     [--latency=700] [--sites=12] [--city=legacy] [--report=/abs/report.json]
## Run (rendered evidence under Xvfb, frames written per segment; OpenGL compatibility — Vulkan on
## lavapipe deadlocked after the forest world build on this machine):
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver opengl3 \
##     --fixed-fps 15 -s qa_forest_1024.gd -- --server=... --shots=/abs/dir --fps=15 --sites=1 --city=legacy
##   (presentation and server clocks advance 1/fps s per rendered frame, COARSE× outside the recorded
##   segments; the server clock is frozen). --only=intro stops after the intro. Rendered latency numbers
##   are wall-clock and meaningless (seconds per frame): the latency table comes from headless runs.
## Then: python3 godot/tools/forest_1024_evidence.py <before shots> <after shots> <before qa> <after qa> <out>
##
## Checks (problem numbers of the owner's report):
##  1 fog: the fog clears around the squad and the horse as they walk: lag ≤ 0.3 s behind them
##  2 intro: the horse walks out of the fog on screen, unoccluded by the city wall, for ≥ 1.5 s
##  3 puzzle: every option picture of every artifact puzzle is an icon of the atlas (forest_rescue/ui)
##  4 menace: the creature menaces within 1 s of the squad's arrival; the horse shows fear; the squad
##    takes the guard stance facing it
##  5 fight: ≥ 4 s of fight animation on screen before the result text
##  6 buttons: first visual response ≤ 100 ms after a press (at the --latency given), the server
##    confirmation measured separately (latency table in the report)
##  7 cages: at every site the cage and its three captives are loaded, shown and on screen before
##    the release, and the release (door, captives out) plays on screen

const ForestFlags := preload("res://src/forest_rescue/world/forest_flags.gd")
const LEGACY_LAYOUT := [["ECO-05", "plot-14", 5], ["RES-01", "plot-0", 5], ["RES-02", "plot-5", 5],
	["RES-03", "plot-30", 5], ["RES-04", "plot-35", 5], ["ECO-01", "plot-8", 5], ["ECO-02", "plot-9", 5],
	["ECO-03", "plot-15", 5], ["ECO-04", "plot-20", 5], ["MIL-01", "plot-21", 5], ["MIL-02", "plot-26", 5],
	["MIL-03", "plot-27", 5], ["SUP-01", "plot-13", 5], ["SUP-03", "plot-2", 5], ["SUP-04", "plot-19", 5],
	["SUP-05", "plot-7", 5]]
const FOG_LAG_MAX := 0.3
## Fog "clear around" an actor: the displayed signed distance at its feet ≥ 4.5 m — past the shader's
## 2.5 m soft band and its ≤ 1 m lobes, so no fog body stands within a metre of the actor.
const FOG_CLEAR_M := 4.5
const INTRO_VISIBLE_MIN := 1.5
const MENACE_MAX := 1.0
const MENACE_RANGE_M := 18.0  # actor_director.MENACE_RANGE: the squad counts as near the lair
const FIGHT_MIN := 4.0
const FIRST_VISUAL_MAX := 100.0

var game: Node
var forest: Node
var server := "http://127.0.0.1:8801"
var shots := ""
var latency := 0
var site_limit := 12
var city := "kingdom"
var report_path := ""
var fps := 30.0
var rendered := false
var clock_ms := 0.0
var recording := ""
var frame_index := 0
var segment_frames: Dictionary = {}
var checks := 0
var failures: Array[String] = []
var report := {"latency": {}, "cages": {}, "menace": {}, "fight": {}, "fog": {}, "intro": {}, "puzzle": {}, "cpu": {}}
var actions: Array = []
var finished := false
var fog_track: Array = []
var lead_max_us := 0
var lead_sum_us := 0
var lead_n := 0
var horse_track: Array = []
var intro_frame := 0
var only := ""

func _initialize() -> void:
	call_deferred("run")

func check(value: bool, detail: String) -> void:
	checks += 1
	print(("CHECK ok   " if value else "CHECK FAIL ") + detail)
	if not value:
		failures.append(detail)

# ------------------------------------------------------------------ transport to the local harness
func post(path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(server + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else {}
	return parsed if parsed is Dictionary else {}

func refresh() -> void:
	var guard := 0
	while game.busy and guard < 600:
		guard += 1
		await tick()
	var response: Dictionary = await game.request("state")
	if response.has("city"):
		game.accept(response)
	await tick()

func advance_to(server_ms: float) -> void:
	var now := float(forest.client.adv.get("serverTime", 0))
	var target := maxf(server_ms, now + 50.0)
	if rendered:
		clock_ms = maxf(clock_ms, target)
		forest.client.manual_clock_ms = clock_ms
	await post("/test/clock?time=%d" % int(ceil(target)))
	await refresh()

func settle() -> void:
	var at: float = forest.client.last_settle_ms()
	if at == INF:
		await refresh()
	else:
		await advance_to(at + 300.0)

# ------------------------------------------------------------------ frames (and the movie clock)
## Rendered: outside a recorded segment the movie clock runs COARSE times faster (walks between the
## recorded moments are not filmed; the engine still steps 1/fps per frame).
const COARSE := 4.0

func tick() -> void:
	if rendered:
		clock_ms += 1000.0 / fps * (1.0 if not recording.is_empty() else COARSE)
		forest.client.manual_clock_ms = clock_ms
		post("/test/clock?time=%d" % int(clock_ms))
	await process_frame
	if rendered and not recording.is_empty():
		await RenderingServer.frame_post_draw
		var dir := shots.path_join(recording)
		var index: int = int(segment_frames.get(recording, 0))
		root.get_texture().get_image().save_jpg(dir.path_join("f_%05d.jpg" % index), 0.9)
		segment_frames[recording] = index + 1

func seconds(value: float) -> void:
	if rendered:
		var until := clock_ms + value * 1000.0
		while clock_ms < until - 0.5:
			await tick()
		return
	var until := Time.get_ticks_msec() + int(value * 1000.0)
	while Time.get_ticks_msec() < until:
		await tick()

func now_s() -> float:
	return clock_ms / 1000.0 if rendered else Time.get_ticks_msec() / 1000.0

func record(segment: String) -> void:
	recording = segment
	if rendered and not segment.is_empty():
		DirAccess.make_dir_recursive_absolute(shots.path_join(segment))

func still(name: String) -> void:
	if not rendered:
		return
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(shots.path_join(name + ".png"))

func look(target: Vector3, zoom: float) -> void:
	game.stage.target = target
	game.stage.zoom = zoom

func follow(target: Vector3, zoom: float) -> void:
	if target == Vector3.INF:
		return
	game.stage.target = game.stage.target.lerp(target, 0.12)
	game.stage.zoom = lerpf(game.stage.zoom, zoom, 0.1)

# ------------------------------------------------------------------ boot
func boot() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + (1800000 if rendered else 180000)
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty() or game.forest_game == null) and Time.get_ticks_msec() < deadline:
		await process_frame
	forest = game.forest_game
	check(forest != null, "forest game layer loaded lazily after the launch")
	if forest == null:
		finish()
		return
	while not forest.world_ready() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(forest.world_ready() and not ForestFlags.eager(), "forest world layer attached by itself after the city")
	while not forest.entered_session and Time.get_ticks_msec() < deadline:
		await process_frame

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--server="):
			server = argument.trim_prefix("--server=")
		elif argument.begins_with("--shots="):
			shots = argument.trim_prefix("--shots=")
		elif argument.begins_with("--latency="):
			latency = int(argument.trim_prefix("--latency="))
		elif argument.begins_with("--sites="):
			site_limit = int(argument.trim_prefix("--sites="))
		elif argument.begins_with("--city="):
			city = argument.trim_prefix("--city=")
		elif argument.begins_with("--report="):
			report_path = argument.trim_prefix("--report=")
		elif argument.begins_with("--only="):
			only = argument.trim_prefix("--only=")
		elif argument.begins_with("--fps="):
			fps = float(argument.trim_prefix("--fps="))
	rendered = not shots.is_empty()
	if rendered:
		DirAccess.make_dir_recursive_absolute(shots)
	root.size = Vector2i(1366, 630)
	await post("/test/reset")
	await boot()
	if finished:
		return
	if city == "legacy":
		await post("/test/legacy", {"layout": LEGACY_LAYOUT})
	await post("/test/army", {"units": {"ENG-02": 30000, "ENG-03": 30000, "ENG-06": 30000}})
	if rendered:
		clock_ms = float(forest.client.server_now())
		forest.client.manual_clock_ms = clock_ms
		await post("/test/clock?time=%d&freeze=1" % int(clock_ms))
	await post("/test/hall?level=%d" % (5 if city == "legacy" else 3))
	await refresh()
	check(forest.client.unlocked(), "forest unlocked")
	check_puzzle_art()
	await intro_section()
	if only == "intro":
		summarize()
		finish()
		return
	await post("/test/latency?ms=%d" % latency)
	await play_sites()
	await post("/test/latency?ms=0")
	if not rendered:
		await intro_spot_matrix()
	else:
		await puzzle_stills()
	summarize()
	await server_cpu()
	finish()

# ------------------------------------------------------------------ 2: intro horse
## The horse counts as seen in a frame when its rig is shown, its body is inside the viewport (not under
## the HUD prompt), no city wall / tower / building box lies between it and the camera, and the fog
## at its feet is displayed clear.
func intro_section() -> void:
	var deadline := Time.get_ticks_msec() + (600000 if rendered else 15000)
	while forest.intro.mode != "animated" and Time.get_ticks_msec() < deadline:
		await tick()
	check(forest.intro.mode == "animated", "hall intro plays")
	record("intro")
	var seen := 0.0
	var best := 0.0
	var last := now_s()
	var first_seen := -1.0
	var occluded_frames := 0
	var horse_frames := 0
	var started := now_s()
	while forest.intro.mode == "animated" and now_s() - started < 12.6:
		await tick()
		var dt := now_s() - last
		last = now_s()
		var horse: Node3D = forest.actors.rigs.get("horse")
		intro_frame += 1
		if intro_frame % 15 == 0:
			var cam: Camera3D = game.stage.camera
			print("INTRO_DIAG ", JSON.stringify({"t": snappedf(now_s() - started, 0.1), "intro_t": snappedf(float(forest.intro.elapsed), 0.1), "target": str(game.stage.target.snapped(Vector3.ONE * 0.1)),
				"zoom": snappedf(float(game.stage.camera_zoom), 0.1), "rig": horse != null, "state": String(horse.get("load_state")) if horse != null else "",
				"pos": str(horse.global_position.snapped(Vector3.ONE * 0.1)) if horse != null else "", "screen": str(cam.unproject_position(horse.global_position + Vector3.UP).snapped(Vector2.ONE)) if horse != null else "",
				"shown": horse.is_visible_in_tree() if horse != null else false, "intro_horse": forest.actors.intro_horse.size() > 0, "seen": horse_seen(horse) if horse != null else {}}))
		if (intro_frame == 90 or intro_frame == 150) and horse != null:
			blockers_diag(horse.global_position + Vector3.UP * 1.3)
		if horse == null or not forest.actors.intro_horse.size():
			continue
		horse_frames += 1
		var verdict := horse_seen(horse)
		if verdict.occluded:
			occluded_frames += 1
		if verdict.seen:
			seen += dt
			best = maxf(best, seen)
			if first_seen < 0.0:
				first_seen = now_s() - started
		else:
			seen = 0.0
		horse_track.append([now_s(), horse.global_position])
	record("")
	report.intro = {"visible_run_s": snappedf(best, 0.01), "first_seen_s": snappedf(first_seen, 0.01), "occluded_frames": occluded_frames, "horse_frames": horse_frames}
	check(best >= INTRO_VISIBLE_MIN, "intro: the horse is on screen, unoccluded and out of the fog for %.2f s in a row (≥ %.1f)" % [best, INTRO_VISIBLE_MIN])
	if forest.actors.has_method("horse_origin_spots"):
		var spots: Dictionary = forest.actors.horse_origin_spots()
		var origin: Vector3 = forest.target_position("lf_horse_origin")
		report.intro.origin_hidden = forest.actors.structure_hides(forest.ground(origin.x, origin.z), forest.actors.structure_boxes(origin, 48.0), game.stage.camera.global_transform.basis.z.normalized())
		report.intro.spot_shift_m = snappedf((spots.get("horse", origin) as Vector3).distance_to(origin), 0.01)
		report.intro.spot_search_ms = snappedf(forest.actors.origin_usec / 1000.0, 0.01)
	if rendered:
		await still("intro_end")
	forest.intro.on_follow()
	await forest.wait_idle()
	await tick()
	game.close_modal()

## The mare's spot by the entrance for each town-hall level (wall height, towers, bulges change): is
## lf_horse_origin itself hidden from the camera by a wall / tower / gate / building, and is the spot
## the director uses free?
func intro_spot_matrix() -> void:
	report.intro.halls = {}
	if not forest.actors.has_method("horse_origin_spots"):
		return
	for level in [2, 3, 4, 5]:
		var signature := str(game.stage.walls.signature)
		await post("/test/hall?level=%d" % level)
		await refresh()
		var guard := 0
		while str(game.stage.walls.signature) == signature and guard < 240:
			guard += 1
			await tick()
		for i in 30:
			await tick()
		var origin: Vector3 = forest.target_position("lf_horse_origin")
		var toward: Vector3 = game.stage.camera.global_transform.basis.z.normalized()
		var boxes: Array = forest.actors.structure_boxes(origin, 48.0)
		var spots: Dictionary = forest.actors.horse_origin_spots()
		var spot: Vector3 = spots.get("horse", origin)
		var squad_spot: Vector3 = spots.get("squad", origin)
		var entry := {"origin_hidden": forest.actors.structure_hides(forest.ground(origin.x, origin.z), boxes, toward),
			"spot_hidden": forest.actors.structure_hides(spot, boxes, toward), "squad_spot_hidden": forest.actors.structure_hides(squad_spot, boxes, toward),
			"shift_m": snappedf(spot.distance_to(origin), 0.01), "search_ms": snappedf(forest.actors.origin_usec / 1000.0, 0.01)}
		report.intro.halls[str(level)] = entry
		check(not entry.spot_hidden and not entry.squad_spot_hidden, "intro spot, hall %d: the mare's spot%s is in view (origin %s, shift %.1f m)" % [level, "" if entry.shift_m < 0.5 else " (moved)", "hidden" if entry.origin_hidden else "free", entry.shift_m])
	# The owner's city: a wall tower stands between the entrance and the camera. None of the QA cities
	# hides the origin, so a tower-sized box (5 × 10 × 5 m, the wall's own node) is put in front of it,
	# then on it: the mare's spot must move into view.
	report.intro.synthetic_tower = {}
	for placement in ["in_front", "on_origin"]:
		var origin: Vector3 = forest.ground(forest.target_position("lf_horse_origin").x, forest.target_position("lf_horse_origin").z)
		var toward: Vector3 = game.stage.camera.global_transform.basis.z.normalized()
		var flat := Vector3(toward.x, 0, toward.z).normalized()
		var tower := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(5, 10, 5)
		tower.mesh = box
		game.stage.walls.node.add_child(tower)
		tower.global_position = origin + Vector3.UP * 5.0 + (flat * 5.5 if placement == "in_front" else Vector3.ZERO)
		forest.actors.origin_key = ""
		var spots: Dictionary = forest.actors.horse_origin_spots()
		var boxes: Array = forest.actors.structure_boxes(origin, 48.0)
		var spot: Vector3 = spots.get("horse", origin)
		var squad_spot: Vector3 = spots.get("squad", origin)
		var entry := {"origin_hidden": forest.actors.structure_hides(origin, boxes, toward), "spot_hidden": forest.actors.structure_hides(spot, boxes, toward),
			"squad_spot_hidden": forest.actors.structure_hides(squad_spot, boxes, toward), "shift_m": snappedf(Vector2(spot.x - origin.x, spot.z - origin.z).length(), 0.01),
			"search_ms": snappedf(forest.actors.origin_usec / 1000.0, 0.01)}
		report.intro.synthetic_tower[placement] = entry
		check(entry.origin_hidden and not entry.spot_hidden and not entry.squad_spot_hidden, "intro spot with a tower %s: origin hidden %s → the mare's spot moves %.1f m into view (spot hidden %s, squad hidden %s, %.2f ms)" % [placement, entry.origin_hidden, entry.shift_m, entry.spot_hidden, entry.squad_spot_hidden, entry.search_ms])
		tower.queue_free()
		await tick()
		forest.actors.origin_key = ""

func horse_seen(horse: Node3D) -> Dictionary:
	var camera: Camera3D = game.stage.camera
	var body: Vector3 = horse.global_position + Vector3.UP * 1.3
	var points := [body, horse.global_position + Vector3.UP * 2.0, body + Vector3(0.9, 0, 0), body - Vector3(0.9, 0, 0)]
	var rect := Rect2(Vector2(20, 60), Vector2(root.size) - Vector2(40, 60 + 262))
	var on_screen := horse.visible and horse.is_visible_in_tree() and not camera.is_position_behind(body) and rect.has_point(camera.unproject_position(body))
	var blocked := 0
	for p in points:
		if occluded(p):
			blocked += 1
	var fog_clear := float(forest.world.fog.displayed_clear(horse.global_position.x, horse.global_position.z)) if forest.world != null else 1.0
	return {"seen": on_screen and blocked <= 1 and fog_clear >= 0.85, "occluded": blocked > 1, "fog": fog_clear}

## Diagnostic: the structure nodes whose boxes hide p from the camera (path, box).
func blockers_diag(p: Vector3) -> void:
	var toward: Vector3 = game.stage.camera.global_transform.basis.z.normalized()
	var roots: Array = [game.stage.walls.node, game.stage.buildings]
	if is_instance_valid(game.stage.gate_node):
		roots.append(game.stage.gate_node)
	var out: Array = []
	for node_root in roots:
		for node in (node_root as Node).find_children("*", "GeometryInstance3D", true, false):
			var geometry := node as GeometryInstance3D
			if not geometry.is_visible_in_tree():
				continue
			var boxes: Array = []
			if geometry is MultiMeshInstance3D and (geometry as MultiMeshInstance3D).multimesh != null and (geometry as MultiMeshInstance3D).multimesh.mesh != null:
				var multi: MultiMesh = (geometry as MultiMeshInstance3D).multimesh
				for i in (multi.visible_instance_count if multi.visible_instance_count >= 0 else multi.instance_count):
					boxes.append([geometry.global_transform * multi.get_instance_transform(i), multi.mesh.get_aabb()])
			elif geometry is MeshInstance3D and (geometry as MeshInstance3D).mesh != null:
				boxes.append([geometry.global_transform, (geometry as MeshInstance3D).mesh.get_aabb()])
			for entry: Array in boxes:
				var xf: Transform3D = entry[0]
				if absf(xf.basis.determinant()) < 0.000001:
					continue
				var inv := xf.affine_inverse()
				var local: AABB = entry[1]
				if local.has_point(inv * p) or local.intersects_segment(inv * (p + toward * 0.3), inv * (p + toward * 120.0)):
					out.append("%s %s" % [String(geometry.get_path()).trim_prefix("/root/Drenovar/City/"), str(xf * local)])
					break
	print("INTRO_BLOCKERS ", JSON.stringify({"p": str(p), "blockers": out, "spots": str(forest.actors.horse_origin_spots()) if forest.actors.has_method("horse_origin_spots") else ""}))

var occluder_boxes: Array = []
var occluder_frame := -100

## City structures between a point and the orthographic camera (wall pieces, towers, gates and
## buildings as world AABBs; the forest layer and the ground are not occluders here: trees fade).
func occluded(p: Vector3) -> bool:
	if Engine.get_process_frames() - occluder_frame > 30:
		occluder_frame = Engine.get_process_frames()
		occluder_boxes.clear()
		var roots: Array = []
		if game.stage.walls != null and is_instance_valid(game.stage.walls.node):
			roots.append(game.stage.walls.node)
		roots.append(game.stage.buildings)
		if is_instance_valid(game.stage.gate_node):
			roots.append(game.stage.gate_node)
		for node_root in roots:
			for node in (node_root as Node).find_children("*", "GeometryInstance3D", true, false):
				var geometry := node as GeometryInstance3D
				if not geometry.is_visible_in_tree():
					continue
				if geometry is MultiMeshInstance3D:
					var multi: MultiMesh = (geometry as MultiMeshInstance3D).multimesh
					if multi == null or multi.mesh == null:
						continue
					var local := multi.mesh.get_aabb()
					for i in multi.visible_instance_count if multi.visible_instance_count >= 0 else multi.instance_count:
						var xf: Transform3D = geometry.global_transform * multi.get_instance_transform(i)
						if absf(xf.basis.determinant()) > 0.000001:
							occluder_boxes.append([xf * local, xf.affine_inverse(), local])
				elif geometry is MeshInstance3D and (geometry as MeshInstance3D).mesh != null:
					var local := (geometry as MeshInstance3D).mesh.get_aabb()
					occluder_boxes.append([geometry.global_transform * local, geometry.global_transform.affine_inverse(), local])
	# Oriented boxes (instance space): a roof pyramid turned 45° covers half of its world AABB.
	var toward: Vector3 = game.stage.camera.global_transform.basis.z.normalized()
	var from := p + toward * 0.3
	var to := p + toward * 120.0
	for entry: Array in occluder_boxes:
		var world: AABB = entry[0]
		if world.has_point(p) or not world.intersects_segment(from, to):
			continue
		var inv: Transform3D = entry[1]
		var local: AABB = entry[2]
		if not local.has_point(inv * p) and local.intersects_segment(inv * from, inv * to):
			return true
	return false

# ------------------------------------------------------------------ 3: puzzle option pictures
## Rendered: the puzzle panel of the other mechanism kinds (rune lock, winch, paired latch) as stills.
func puzzle_stills() -> void:
	for site_id in ["lf_site_02", "lf_site_03", "lf_site_04"]:
		if forest.client.poi(site_id).is_empty():
			continue
		forest.mech.open(site_id)
		await seconds(0.4)
		await still("puzzle_%s" % site_id)
		forest.mech.close()

func check_puzzle_art() -> void:
	var MechanismUi: Script = load("res://src/forest_rescue/game/mechanism_ui.gd")
	var symbols := {}
	for site in forest.content.campaign.get("sites", []):
		for symbol in site.get("artifact", {}).get("puzzle", {}).get("solution", []):
			symbols[String(symbol)] = true
	var drawn := 0
	var pictures := 0
	for symbol in symbols:
		drawn += 1
		if MechanismUi.has_method("symbol_icon") and MechanismUi.symbol_icon(String(symbol)) != null:
			pictures += 1
	report.puzzle = {"symbols": symbols.size(), "pictures": pictures}
	check(pictures == drawn and drawn > 0, "puzzle: %d of %d option symbols have a picture icon (atlas)" % [pictures, drawn])

# ------------------------------------------------------------------ the adventure, site by site
func current_site() -> String:
	var next: Variant = forest.client.adv.get("nextTask")
	return String(next.siteId) if next is Dictionary and next.get("siteId") != null else ""

func current_task() -> String:
	var next: Variant = forest.client.adv.get("nextTask")
	return String(next.taskId) if next is Dictionary and next.get("taskId") != null else ""

func play_sites() -> void:
	await form_squad()
	var stuck := 0
	var last := ""
	var menace_done := {}
	var cage_done := {}
	var steps := 0
	while steps < 400:
		steps += 1
		var phase: String = forest.client.phase()
		if phase != "prologue" and phase != "rescue":
			break
		var site_id := current_site()
		var task_id := current_task()
		if phase == "rescue" and not site_id.is_empty() and forest.content.site_number(site_id) > site_limit:
			break
		if site_id == "lf_site_07" and forest.client.hall_level() < 5:
			await post("/test/hall?level=5")
			await refresh()
		var step: Dictionary = forest.guide()
		var signature := JSON.stringify([step.get("action", ""), step.get("fields", {}), step.get("panel", ""), forest.client.revision(), forest.client.squad().get("move") != null])
		stuck = stuck + 1 if signature == last else 0
		last = signature
		if stuck > 8:
			check(false, "guide stuck at " + signature)
			break
		var node := String(forest.client.squad().get("node", ""))
		if not site_id.is_empty() and node.begins_with(site_id) and not menace_done.has(site_id) and forest.client.squad().get("move") == null:
			menace_done[site_id] = true
			await menace_section(site_id)
			continue
		if task_id == "unlock_cage" and not cage_done.has(site_id) and String(step.get("action", "")) == "attempt_task":
			cage_done[site_id] = true
			await cage_before(site_id)
		if String(step.get("panel", "")) == "mechanism":
			await solve_mechanism(site_id)
			continue
		if String(step.get("panel", "")) == "squad":
			await form_squad()
			continue
		if not bool(step.get("enabled", false)) or String(step.get("action", "")).is_empty():
			await settle()
			continue
		var action := String(step.action)
		var fields: Dictionary = step.get("fields", {})
		var label := action if action != "attempt_task" else String(fields.get("taskId", action))
		if action == "move":
			label = "move→" + String(fields.get("targetId", "")).get_slice(":", 1) if String(fields.get("targetId", "")).contains(":") else "move"
		var watch_fight := action == "engage_guardian"
		var measured := await press(label, func(): forest.hud.continue_button.pressed.emit(), site_id)
		if not bool(measured.get("ok", false)):
			continue
		if action == "move" and String(fields.get("targetId", "")) == "lf_site_01" and not report.fog.has("walk_s"):
			await fog_section()
		if watch_fight:
			await fight_section(site_id)
		elif task_id == "unlock_cage" and action == "attempt_task":
			await cage_release(site_id)
		elif action in ["move", "escort_start"]:
			await settle()

## Presses through a real control and measures time to the first visual response (actors, devices,
## mechanism widget; not the button's own disabled state) and to the server's confirmation.
func press(label: String, action: Callable, site_id := "") -> Dictionary:
	var before := visual_signature(site_id, label)
	var sent_before: int = forest.client.sent_log.size()
	var started := Time.get_ticks_usec()
	action.call()
	var first_visual := -1.0
	var confirmed := -1.0
	var result := {}
	var guard := Time.get_ticks_msec() + 20000
	while Time.get_ticks_msec() < guard:
		if first_visual < 0.0 and visual_signature(site_id, label) != before:
			first_visual = (Time.get_ticks_usec() - started) / 1000.0
		var done: bool = forest.client.sent_log.size() > sent_before and not forest.client.in_flight and not forest.acting
		if done and confirmed < 0.0:
			confirmed = (Time.get_ticks_usec() - started) / 1000.0
			result = forest.client.last_result
		if confirmed >= 0.0 and (first_visual >= 0.0 or (Time.get_ticks_usec() - started) / 1000.0 > confirmed + 400.0):
			break
		await tick()
	if first_visual < 0.0:
		first_visual = confirmed
	var entry := {"action": label, "first_visual_ms": snappedf(first_visual, 0.1), "confirmed_ms": snappedf(confirmed, 0.1), "ok": bool(result.get("ok", false))}
	actions.append(entry)
	print("PRESS ", JSON.stringify(entry))
	return entry

## What the press visibly changes: the squad's clips and positions, the cage / key choreography, the
## puzzle panel; the horse only for the horse's own button. Things that move by themselves (the
## stalking creature, the frightened mare, turning to face the creature) are left out so ambient
## motion never counts as a response.
func visual_signature(site_id: String, label := "") -> String:
	var parts: PackedStringArray = []
	for id in ["squad_0", "squad_1", "squad_2"]:
		var rig: Node3D = forest.actors.rigs.get(id)
		if rig != null and is_instance_valid(rig):
			parts.append("%s:%s:%s" % [id, String(rig.get("current_id")), str(rig.position.snapped(Vector3(0.05, 0.05, 0.05)))])
	var horse: Node3D = forest.actors.rigs.get("horse")
	if label == "discover_horse" and horse != null and is_instance_valid(horse):
		parts.append("horse:%s:%s" % [String(horse.get("current_id")), str(horse.position.snapped(Vector3(0.1, 0.1, 0.1)))])
	parts.append(",".join(PackedStringArray(forest.actors.choreo.keys())))
	if forest.mech.is_open():
		parts.append(forest.mech.count_label.text + "|" + forest.mech.feedback.text + "|" + str(forest.mech.get("checking_symbol")))
	return "/".join(parts)

func form_squad() -> void:
	forest.panels.open_squad()
	await tick()
	for spin: SpinBox in game.modal_body.find_children("Squad_*", "SpinBox", true, false):
		spin.value = spin.max_value
	var submit: Button = game.modal_body.find_child("SquadSubmit", true, false)
	if submit == null or submit.disabled:
		game.close_modal()
		return
	await press("form_squad", func(): submit.pressed.emit())
	await tick()

func solve_mechanism(site_id: String) -> void:
	var site: Dictionary = forest.content.site(site_id)
	var solution: Array = site.artifact.puzzle.solution
	var kind := String(site.variation)
	forest.mech.open(site_id)
	await tick()
	if rendered and int(site.get("number", 0)) <= 2:
		await seconds(0.6)
		await still("puzzle_%s" % site_id)
	var cards := 0
	var pictured := 0
	for card: Button in forest.mech.inputs.get_children():
		cards += 1
		if card.icon != null and card.get_combined_minimum_size().y >= 120.0:
			pictured += 1
	check(cards > 0 and pictured == cards, "%s: %d/%d option cards show their picture (≥ 120 px tall)" % [site_id, pictured, cards])
	if kind == "paired_latch":
		await press("occupy_plates", func(): forest.mech.occupy(), site_id)
		await settle()
	for symbol in solution:
		var before := int(forest.mech.mechanism().get("progress", 0))
		var button: Button = forest.mech.inputs.find_child("Symbol_" + String(symbol), true, false)
		var label := "mechanism_input" if kind != "trail_cache" or forest.mech.observed(String(symbol)) else "landmark→input"
		var fire := func():
			if button != null:
				button.pressed.emit()
			else:
				forest.mech.send_symbol(String(symbol))
		var measured := await press(label, fire, site_id)
		var guard := 0
		while int(forest.mech.mechanism().get("progress", 0)) <= before and not bool(forest.mech.mechanism().get("solved", false)) and guard < 40:
			guard += 1
			if forest.client.squad().get("move") is Dictionary:
				await settle()
			await seconds(0.1)
		if label == "landmark→input":
			measured.confirmed_ms = -1.0
	check(bool(forest.mech.mechanism().get("solved", false)), "mechanism solved through the UI " + site_id)
	forest.mech.close()

# ------------------------------------------------------------------ 1: fog follows the squad
## The squad walks to the first glade in real time (presentation clock). Every 0.25 s the spots of the
## squad leader and of the horse (she leads, 1.5 s ahead) are recorded, then the moment the fog there is
## displayed clear: the state texture read the way the fog shader reads it (bilinear, mean reveal delay)
## with the signed distance ≥ FOG_CLEAR_M. Lag = clear − reached.
func fog_section() -> void:
	record("fog")
	var move: Dictionary = forest.client.squad().get("move", {})
	var walk := 14.0
	var started := now_s()
	var samples: Array = []
	var next_sample := started + 1.0
	while now_s() - started < walk:
		await tick()
		var leader: Vector3 = forest.actors.squad_focus()
		follow(leader, 34.0)
		if leader == Vector3.INF:
			continue
		var lead_us: Variant = forest.world.get("lead_usec")
		if lead_us is int and int(lead_us) > 0:
			lead_max_us = maxi(lead_max_us, int(lead_us))
			lead_sum_us += int(lead_us)
			lead_n += 1
			forest.world.set("lead_usec", 0)
		if not report.has("cpu") or not report.cpu.has("walk"):
			if now_s() - started >= 6.0:
				cpu_bench("walk")
		var horse: Node3D = forest.actors.rigs.get("horse")
		if now_s() >= next_sample:
			next_sample += 0.25
			samples.append({"t": now_s(), "p": leader, "clear": -1.0, "who": "squad"})
			if horse != null and horse.is_ready() and bool(forest.client.adv.get("horse", {}).get("visible", false)):
				samples.append({"t": now_s(), "p": horse.global_position, "clear": -1.0, "who": "horse"})
		for sample in samples:
			if float(sample.clear) < 0.0 and shader_sdf(sample.p) >= FOG_CLEAR_M:
				sample.clear = now_s()
	record("")
	var stats := {}
	for who in ["squad", "horse"]:
		var lags: Array = []
		for sample in samples:
			if sample.who != who:
				continue
			var cleared := float(sample.clear) if float(sample.clear) >= 0.0 else now_s() + 1.0
			lags.append(maxf(0.0, cleared - float(sample.t)))
		lags.sort()
		var mean := 0.0
		for value in lags:
			mean += float(value)
		stats[who] = {"samples": lags.size(), "lag_max_s": snappedf(float(lags.back()) if not lags.is_empty() else 99.0, 0.01),
			"lag_p95_s": snappedf(float(lags[int((lags.size() - 1) * 0.95)]) if not lags.is_empty() else 99.0, 0.01),
			"lag_mean_s": snappedf(mean / maxf(1.0, lags.size()), 0.01)}
	if not report.has("cpu"):
		report.cpu = {}
	report.cpu.lead_update = {"updates": lead_n, "max_us": lead_max_us, "mean_us": snappedf(lead_sum_us / maxf(1.0, lead_n), 0.1)}
	report.fog = {"walk_s": walk, "move_ms": float(move.get("arriveAt", 0)) - float(move.get("departAt", 0)), "squad": stats.squad, "horse": stats.horse}
	for who in ["squad", "horse"]:
		check(float(stats[who].lag_max_s) <= FOG_LAG_MAX, "fog clears with the %s: worst lag %.2f s, p95 %.2f s, mean %.2f s (≤ %.1f)" % [who, stats[who].lag_max_s, stats[who].lag_p95_s, stats[who].lag_mean_s, FOG_LAG_MAX])

## Signed distance (m, + = clear) the fog shader sees at p right now: the state texture sampled bilinearly
## (filter_linear), previous→target blended with the mean per-pixel reveal delay (noise .a ≈ 0.5).
func shader_sdf(p: Vector3) -> float:
	var fog: Node = forest.world.fog
	var image: Image = fog.state_image
	var fx := clampf((p.x - fog.GRID_ORIGIN) / fog.CELL - 0.5, 0.0, fog.GRID - 1.001)
	var fz := clampf((p.z - fog.GRID_ORIGIN) / fog.CELL - 0.5, 0.0, fog.GRID - 1.001)
	var i := int(fx)
	var j := int(fz)
	var u := fx - i
	var v := fz - j
	var a := image.get_pixel(i, j).lerp(image.get_pixel(i + 1, j), u)
	var b := image.get_pixel(i, j + 1).lerp(image.get_pixel(i + 1, j + 1), u)
	var px := a.lerp(b, v)
	var local_t := smoothstep(0.25, 0.75, float(fog.reveal_t))
	return (lerpf(px.g, px.r, local_t) - 0.5) * float(fog.SDF_RANGE)

## Per-frame CPU of the presentation logic (headless only): 60 extra actor-director ticks with delta 0
## (no animation advance) timed on the main thread; the same probe runs on the baseline build.
func cpu_bench(label: String) -> void:
	if not report.has("cpu"):
		report.cpu = {}
	if rendered:
		report.cpu[label] = {}
		return
	var started := Time.get_ticks_usec()
	for i in 60:
		forest.actors.tick(0.0)
	var entry := {"actors_tick_us": snappedf((Time.get_ticks_usec() - started) / 60.0, 0.1)}
	for key in ["predict_usec", "origin_usec"]:
		var value: Variant = forest.actors.get(key)
		if value is int:
			entry[key] = value
	if label == "walk" and forest.world.has_method("_update_lead"):
		# Worst case of the fog lead: the whole walk restamped from its start (a new server move),
		# 20 times; the shown-fog push is included (the distance fields run on a worker thread).
		var worst := 0
		var total := 0
		for i in 20:
			forest.world.set("_lead_reach", 0.0)
			forest.world.set("lead_bits", PackedByteArray())
			var t0 := Time.get_ticks_usec()
			forest.world._update_lead()
			var spent := Time.get_ticks_usec() - t0
			worst = maxi(worst, spent)
			total += spent
		entry.lead_restamp_mean_us = snappedf(total / 20.0, 0.1)
		entry.lead_restamp_max_us = worst
	report.cpu[label] = entry

# ------------------------------------------------------------------ 4: menace at the glade
func menace_section(site_id: String) -> void:
	var anchor: Dictionary = forest.site_anchor(site_id)
	look(anchor.get("center", forest.target_position(site_id)), 30.0)
	var first := site_id == "lf_site_01"
	if first:
		record("menace")
	var guardian_id := "guardian_" + site_id
	# Proximity = the squad as presented reaches the lair's menace range (after a QA clock jump the
	# shown squad still walks the last stretch there; a player sees it walk the whole way).
	var lair: Vector3 = anchor.get("guardian", anchor.get("center", Vector3.ZERO))
	var approach_started := now_s()
	while now_s() - approach_started < 30.0:
		var focus: Vector3 = forest.actors.squad_focus()
		if focus != Vector3.INF and Vector2(focus.x - lair.x, focus.z - lair.z).length() < MENACE_RANGE_M:
			break
		await tick()
	var approach_s := now_s() - approach_started
	var started := now_s()
	var menace_at := -1.0
	var fear_at := -1.0
	var guard_at := -1.0
	var guardian_state := String(forest.client.poi(site_id).get("guardian", {}).get("state", "alive"))
	while now_s() - started < (6.0 if first else 2.0):
		await tick()
		var t := now_s() - started
		if first and t >= 3.0 and not report.get("cpu", {}).has("menace"):
			cpu_bench("menace")
		var creature: Node3D = forest.actors.rigs.get(guardian_id)
		var menace: Variant = forest.actors.get("menace")
		if menace_at < 0.0 and menace is Dictionary and (menace as Dictionary).has(site_id) and creature != null and String(creature.get("current_id")) in ["Roar", "Alert", "stalk", "Walk"]:
			menace_at = t
		var horse: Node3D = forest.actors.rigs.get("horse")
		if fear_at < 0.0 and horse != null and String(horse.get("current_id")) in ["lf_horse_alert", "lf_horse_turn_left", "lf_horse_turn_right", "lf_horse_start"] and menace is Dictionary and (menace as Dictionary).has(site_id):
			fear_at = t
		if guard_at < 0.0 and creature != null:
			var facing := 0
			for index in 3:
				var soldier: Node3D = forest.actors.rigs.get("squad_%d" % index)
				if soldier == null:
					continue
				var to := creature.global_position - soldier.global_position
				var yaw_to := atan2(to.x, to.z)
				if String(soldier.get("current_id")) in ["lf_soldier_guard"] and absf(angle_difference(soldier.rotation.y, yaw_to)) < deg_to_rad(35.0):
					facing += 1
			if facing >= mini(2, forest.actors.squad_member_count()):
				guard_at = t
	if first:
		record("")
	if menace_at < 0.0:
		var creature_now: Node3D = forest.actors.rigs.get(guardian_id)
		var focus: Vector3 = forest.actors.squad_focus()
		var home: Vector3 = anchor.get("guardian", anchor.get("center", Vector3.ZERO))
		print("MENACE_DIAG ", JSON.stringify({"site": site_id, "rig": creature_now != null, "state": String(creature_now.get("load_state")) if creature_now != null else "",
			"clip": String(creature_now.get("current_id")) if creature_now != null else "", "squad_d": Vector2(focus.x - home.x, focus.z - home.z).length() if focus != Vector3.INF else -1.0,
			"members": forest.actors.squad_member_count(), "pending": forest.actors.get("engage_pending_for"), "battle": forest.client.battle().get("siteId", ""),
			"node": forest.client.squad().get("node", ""), "move": forest.client.squad().get("move") != null}))
	report.menace[site_id] = {"approach_s": snappedf(approach_s, 0.01), "guardian": guardian_state, "menace_s": snappedf(menace_at, 0.01), "horse_fear_s": snappedf(fear_at, 0.01), "squad_guard_s": snappedf(guard_at, 0.01)}
	if guardian_state == "alive":
		check(menace_at >= 0.0 and menace_at <= MENACE_MAX, "%s: the creature menaces %.2f s after the squad arrives (≤ %.1f)" % [site_id, menace_at, MENACE_MAX])
		check(fear_at >= 0.0 and fear_at <= 2.0, "%s: the horse shows fear (%.2f s)" % [site_id, fear_at])
		check(guard_at >= 0.0 and guard_at <= 2.0, "%s: the squad takes the guard stance facing the creature (%.2f s)" % [site_id, guard_at])

# ------------------------------------------------------------------ 5: the fight
func fight_section(site_id: String) -> void:
	var fight: Dictionary = forest.client.battle()
	check(not fight.is_empty() and fight.has("timeline"), "fight with a server timeline at " + site_id)
	var first := site_id == "lf_site_01"
	if first:
		record("fight")
	var started := now_s()
	var animated := 0.0
	var last := now_s()
	var result_at := -1.0
	var ends := float(fight.get("endsAt", 0))
	var guardian_id := "guardian_" + site_id
	var contact := 0.0
	var beats := {}
	var last_gap := {}
	while now_s() - started < 14.0:
		await tick()
		var dt := now_s() - last
		last = now_s()
		if first and now_s() - started >= 3.0 and not report.get("cpu", {}).has("fight"):
			cpu_bench("fight")
		var creature: Node3D = forest.actors.rigs.get(guardian_id)
		var soldier: Node3D = forest.actors.rigs.get("squad_0")
		var fighting := false
		if creature != null and soldier != null and creature.visible and soldier.visible:
			var camera: Camera3D = game.stage.camera
			var view := Rect2(Vector2.ZERO, Vector2(root.size))
			var on_screen := view.has_point(camera.unproject_position(creature.global_position + Vector3.UP)) and view.has_point(camera.unproject_position(soldier.global_position + Vector3.UP))
			var clips := String(creature.get("current_id")) + "|" + String(soldier.get("current_id"))
			fighting = on_screen and (clips.contains("Attack") or clips.contains("Hit") or clips.contains("Death") or clips.contains("attack") or clips.contains("lf_soldier_hit") or clips.contains("Roar"))
			# Beats of the fight as the player sees them (on screen, before the result text).
			if on_screen and result_at < 0.0:
				var creature_clip := String(creature.get("current_id")).to_lower()
				for word in ["attack", "pounce", "hit", "death", "roar"]:
					if creature_clip.contains(word):
						beats["creature_" + ("attack" if word == "pounce" else word)] = true
				var nearest := INF
				for index in 3:
					var member: Node3D = forest.actors.rigs.get("squad_%d" % index)
					if member == null or not member.visible:
						continue
					var clip := String(member.get("current_id"))
					if clip.contains("attack"):
						beats.squad_strike = true
					elif clip.contains("lf_soldier_hit"):
						beats.squad_hit = true
					elif clip.contains("death"):
						beats.squad_death = true
					elif clip.contains("help") and beats.has("creature_death"):
						beats.wounded_react = true
					var gap := Vector2(member.global_position.x - creature.global_position.x, member.global_position.z - creature.global_position.z).length()
					nearest = minf(nearest, gap)
					if now_s() - started < 2.0 and last_gap.has(index) and float(last_gap[index]) - gap > 0.02:
						beats.charge = true
					last_gap[index] = gap
				if fighting and nearest < 3.0:
					contact += dt
		if fighting and result_at < 0.0:
			animated += dt
		if result_at < 0.0 and result_shown(site_id):
			result_at = now_s() - started
			break
		if float(forest.client.server_now()) > ends + 1500.0 and String(forest.client.battle().get("outcome", "pending")) == "pending":
			await refresh()
	if first:
		await seconds(1.0)
		record("")
	var outcome := String(forest.client.battle().get("outcome", ""))
	report.fight[site_id] = {"server_s": (ends - float(fight.get("startedAt", 0))) / 1000.0, "animated_s": snappedf(animated, 0.01), "melee_contact_s": snappedf(contact, 0.01),
		"result_at_s": snappedf(result_at, 0.01), "beats": beats.keys()}
	check(animated >= FIGHT_MIN and result_at >= 0.0, "%s: %.2f s of fight animation on screen before the result text (≥ %.1f), result at %.2f s" % [site_id, animated, FIGHT_MIN, result_at])
	var needed := ["charge", "squad_strike", "creature_attack", "creature_hit"] + (["creature_death"] if outcome == "victory" else [])
	var missing: Array = needed.filter(func(beat): return not beats.has(beat))
	check(contact >= 2.0 and missing.is_empty(), "%s: a visible melee — %.2f s in contact (< 3 m, ≥ 2.0), beats %s%s" % [site_id, contact, ",".join(PackedStringArray(beats.keys())), "" if missing.is_empty() else " (missing " + ",".join(PackedStringArray(missing)) + ")"])
	check(String(forest.client.battle().get("outcome", "")) == "victory", "fight won at " + site_id)
	game.close_modal()

func result_shown(site_id: String) -> bool:
	if game.modal.visible or game.result_open or game.result_notice.visible:
		return true
	var text := String(forest.content.task(site_id, "defeat_guardian").get("resultText", ""))
	for pill in forest.hud.toasts.get_children():
		if String(pill.get_meta("text", "")) == text:
			return true
	return false

# ------------------------------------------------------------------ 7: cages
func cage_before(site_id: String) -> void:
	var anchor: Dictionary = forest.site_anchor(site_id)
	var cage_spot: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	look(cage_spot, 32.0)
	await seconds(1.2)
	var camera: Camera3D = game.stage.camera
	var view := Rect2(Vector2.ZERO, Vector2(root.size))
	var cage: Node3D = forest.actors.rigs.get("cage_" + site_id)
	var cage_ok: bool = cage != null and String(cage.get("load_state")) == "ready" and cage.visible and cage.is_visible_in_tree() and view.has_point(camera.unproject_position(cage.global_position + Vector3.UP))
	var captives := 0
	var shown := 0
	for person in forest.client.poi(site_id).get("captives", []):
		if String(person.get("state", "")) != "caged":
			continue
		captives += 1
		var rig: Node3D = forest.actors.rigs.get(String(person.id))
		if rig != null and String(rig.get("load_state")) == "ready" and rig.visible and rig.is_visible_in_tree() and view.has_point(camera.unproject_position(rig.global_position + Vector3.UP)):
			if cage != null and rig.global_position.distance_to(cage.global_position) < 2.5:
				shown += 1
	var fog_ok: bool = forest.fog_clear(cage_spot)
	report.cages[site_id] = {"name": forest.site_name(site_id), "cage": String(forest.client.poi(site_id).get("cage", "")), "cage_shown": cage_ok, "captives": captives, "captives_in_cage_shown": shown, "fog_clear": fog_ok, "released": false}
	check(cage_ok and captives == 3 and shown == 3 and fog_ok, "%s (%s): cage %s, %d/%d captives in it, on screen before the release" % [site_id, forest.site_name(site_id), "shown" if cage_ok else "MISSING", shown, captives])
	if rendered and forest.content.site_number(site_id) <= 12:
		await still("cage_before_%s" % site_id)

func cage_release(site_id: String) -> void:
	var first := site_id == "lf_site_01"
	if first:
		record("cage")
	var cage: Node3D = forest.actors.rigs.get("cage_" + site_id)
	var seats := {}
	for person in forest.client.poi(site_id).get("captives", []):
		var rig: Node3D = forest.actors.rigs.get(String(person.id))
		if rig != null:
			seats[String(person.id)] = rig.global_position
	var door_start := door_yaw(cage)
	var started := now_s()
	var choreo_s := 0.0
	var last := now_s()
	var door_moved := false
	var out := 0
	while now_s() - started < 12.0:
		await tick()
		var dt := now_s() - last
		last = now_s()
		if forest.actors.choreo.has("cage:" + site_id) and cage != null and cage.visible:
			choreo_s += dt
		if absf(door_yaw(cage) - door_start) > 0.4:
			door_moved = true
	for id in seats:
		var rig: Node3D = forest.actors.rigs.get(id)
		if rig != null and rig.global_position.distance_to(seats[id]) > 1.5:
			out += 1
	if first:
		record("")
	if report.cages.has(site_id):
		report.cages[site_id].released = door_moved and out == 3
		report.cages[site_id].release_scene_s = snappedf(choreo_s, 0.01)
	check(door_moved and out == 3 and choreo_s >= 2.0, "%s: the release plays on screen (%.1f s, door %s, %d captives out)" % [site_id, choreo_s, "opened" if door_moved else "still", out])

func door_yaw(cage: Node3D) -> float:
	if cage == null or not cage.has_method("part"):
		return 0.0
	var door: Node3D = forest.actors.door_node(cage) if cage.get("model") != null else null
	return door.global_transform.basis.get_euler().y if door != null else 0.0

# ------------------------------------------------------------------ report
func summarize() -> void:
	var by_action := {}
	for entry in actions:
		var key := String(entry.action)
		if not by_action.has(key):
			by_action[key] = {"n": 0, "first_visual_ms": [], "confirmed_ms": []}
		by_action[key].n += 1
		by_action[key].first_visual_ms.append(float(entry.first_visual_ms))
		if float(entry.confirmed_ms) >= 0.0:
			by_action[key].confirmed_ms.append(float(entry.confirmed_ms))
	var table := {}
	for key in by_action:
		var visual: Array = by_action[key].first_visual_ms
		var confirmed: Array = by_action[key].confirmed_ms
		visual.sort()
		confirmed.sort()
		table[key] = {"n": by_action[key].n, "first_visual_ms_median": median(visual), "first_visual_ms_max": visual.back() if not visual.is_empty() else -1,
			"confirmed_ms_median": median(confirmed), "confirmed_ms_max": confirmed.back() if not confirmed.is_empty() else -1}
		check(float(visual.back()) <= FIRST_VISUAL_MAX, "button %s: first visual response %.0f ms worst (≤ %.0f) at %d ms latency" % [key, float(visual.back()), FIRST_VISUAL_MAX, latency])
	report.latency = {"latency_ms": latency, "actions": table}

## Server CPU per adventure action and per state read, from the harness log (median ms).
func server_cpu() -> void:
	var client := HTTPRequest.new()
	client.body_size_limit = -1
	root.add_child(client)
	client.request(server + "/qa/requests", PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "")
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else null
	if not parsed is Array:
		return
	var buckets := {}
	for entry in parsed:
		if not entry is Dictionary or not entry.has("cpu_ms"):
			continue
		var key := String(entry.get("action", "")) if entry.get("action") != null else ""
		if key.is_empty():
			key = String(entry.get("method", "")) + " " + String(entry.get("path", "")).get_file()
		if not buckets.has(key):
			buckets[key] = []
		buckets[key].append(float(entry.cpu_ms))
	var out := {}
	for key in buckets:
		var values: Array = buckets[key]
		values.sort()
		out[key] = {"n": values.size(), "median_ms": median(values), "max_ms": snappedf(float(values.back()), 0.1)}
	report.server_cpu = out

func median(values: Array) -> float:
	if values.is_empty():
		return -1.0
	return snappedf(float(values[values.size() / 2]), 0.1)

func finish() -> void:
	if finished:
		return
	finished = true
	report.checks = checks
	report.failures = failures
	print("QA_FOREST_1024_REPORT ", JSON.stringify(report))
	if not report_path.is_empty():
		var file := FileAccess.open(report_path, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify(report, "  "))
	print("QA_FOREST_1024 checks=", checks, " failures=", failures.size())
	for failure in failures:
		print("  FAIL ", failure)
	if rendered:
		await post("/test/clock?time=%d&freeze=0" % int(clock_ms))
	if is_instance_valid(game):
		game.queue_free()
		for i in 3:
			await process_frame
	quit(0 if failures.is_empty() else 1)
