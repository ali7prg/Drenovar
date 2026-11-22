extends SceneTree
## Arena gameplay-camera check (atlas v2 arena spot, art/08): in each boss phase (hunt / fury /
## last_stand fixtures) the game's own fight camera (ActorDirector.boss_fight_frame + BOSS_FRAME_ZOOM,
## set once per battle) must show the boss and every squad member
##  * in frame: the actor's full silhouette (drawn flat magenta without depth test) inside the viewport
##    (24 px margin, the top 64 px kept for the compact battle panel);
##  * unoccluded: >= 60 % of that silhouette still shows when drawn flat magenta WITH the depth test (the
##    rest is hidden by a cliff, a rock, a tree or a banner in front).
## One still per phase. Needs a renderer:
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan --fixed-fps 30 \
##     -s qa_forest_arena_camera.gd [-- --out=<dir>]

const FIXTURES := "res://data/forest_rescue/game/fixtures/"
const FPS := 30.0
const PHASES := [["hunt", "boss_battle_10"], ["fury", "boss_battle_35"], ["last_stand", "boss_battle_60"]]
const MARGIN := 24.0
const PANEL_TOP := 64.0
const MIN_VISIBLE := 0.6
const MAGENTA := Color(1, 0, 1)

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
var clock := 0.0
var checks := 0
var failures: Array[String] = []
var notes := {}
var out := "res://../../forest_rescue/qa/ingame/integration/arena_camera"


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
	call_deferred("run")


func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		printerr("QA_FOREST_ARENA_CAMERA FAIL: ", detail)


func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))


func frames(count: int) -> void:
	for i in count:
		clock += 1000.0 / FPS
		forest.client.manual_clock_ms = clock
		await process_frame


func load_rigs() -> void:
	for attempt in 40:
		var loading := false
		for id in forest.actors.rigs:
			var rig = forest.actors.rigs[id]
			if is_instance_valid(rig) and rig.load_state == "loading":
				rig.poll_load(true)
				loading = loading or rig.load_state == "loading"
		var world = forest.world
		if world != null and world.get("landmarks") != null and world.landmarks.has_method("finish_arena_load"):
			world.landmarks.finish_arena_load()
		await frames(1)
		if not loading:
			break


## Screen rectangle of a rig's model meshes (projected AABB corners).
func screen_rect(rig: Node3D) -> Rect2:
	var camera: Camera3D = root.get_viewport().get_camera_3d()
	var rect := Rect2()
	var first := true
	for mesh: MeshInstance3D in (rig.model as Node).find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh == null or not mesh.is_visible_in_tree():
			continue
		var box: AABB = mesh.global_transform * mesh.get_aabb()
		for i in 8:
			var p := camera.unproject_position(box.get_endpoint(i))
			rect = Rect2(p, Vector2.ZERO) if first else rect.expand(p)
			first = false
	return rect


func grab() -> Image:
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


## Flat magenta override on a rig's meshes (depth test on / off), null to restore.
func paint(rig: Node3D, material: Material) -> void:
	for mesh: MeshInstance3D in (rig.model as Node).find_children("*", "MeshInstance3D", true, false):
		mesh.material_override = material


## Magenta pixel count and their bounding box.
func magenta(img: Image) -> Array:
	var count := 0
	var lo := Vector2i(1 << 20, 1 << 20)
	var hi := Vector2i(-1, -1)
	for y in range(0, img.get_height(), 2):
		for x in range(0, img.get_width(), 2):
			var c := img.get_pixel(x, y)
			# magenta, also under the additive telegraph / spark FX (they add yellow, never green-only)
			if c.r > 0.7 and c.b > 0.6 and c.g < 0.55 and c.r - c.g > 0.35 and c.b - c.g > 0.25:
				count += 1
				lo = lo.min(Vector2i(x, y))
				hi = hi.max(Vector2i(x, y))
	return [count, Rect2(Vector2(lo), Vector2(hi - lo)) if count > 0 else Rect2()]


func changed_share(a: Image, b: Image, rect: Rect2) -> float:
	var r := Rect2i(rect.position.floor(), rect.size.ceil()).intersection(Rect2i(Vector2i.ZERO, a.get_size()))
	if r.size.x <= 0 or r.size.y <= 0:
		return 0.0
	var changed := 0
	for y in range(r.position.y, r.end.y, 2):
		for x in range(r.position.x, r.end.x, 2):
			var ca := a.get_pixel(x, y)
			var cb := b.get_pixel(x, y)
			if absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b) > 0.08:
				changed += 1
	return float(changed) / float(maxi(1, ((r.size.x + 1) / 2) * ((r.size.y + 1) / 2)))


func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	# 1022: offline, fixture-fed (forest local-realm states predate V6): an unreachable loopback
	# endpoint, so accept() takes them and nothing reaches a real server (1021 qa_city_works pattern).
	game.endpoint = "http://127.0.0.1:9"
	game.loopback = true
	root.add_child(game)
	while game.get("scene_loading") or not is_instance_valid(game.get("stage")):
		await process_frame
	forest = game.forest_game
	var stub := StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub
	await process_frame
	if DisplayServer.get_name() == "headless":
		print("QA_FOREST_ARENA_CAMERA needs a renderer (xvfb-run … --rendering-driver vulkan)")
		quit(2)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out) if out.begins_with("res://") else out)
	var size := Vector2(root.size)
	var safe := Rect2(Vector2(MARGIN, PANEL_TOP), size - Vector2(2.0 * MARGIN, PANEL_TOP + MARGIN))
	var rows := []
	for phase in PHASES:
		var state: Dictionary = fixture(phase[1])
		game.close_modal()
		forest.actors.on_stage_changed()
		forest.actors.first_state = true
		forest.actors.boss_framed_for = ""
		forest.client.adv = {}
		forest.client.primed = false
		clock = float(state.get("adventure", {}).get("serverTime", 0.0))
		forest.client.manual_clock_ms = clock
		game.showing_cached_state = true  # 1022: fixtures may be older than the state on screen
		game.accept(state)
		game.battle_results.pending.clear()
		game.result_notice.hide()
		game.close_modal()
		await frames(10)
		await load_rigs()
		await frames(45)       # the fight camera flies in (focus_on once per battle) and the occluders settle
		var target: Vector3 = game.stage.target
		var zoom := float(game.stage.zoom)
		check(absf(zoom - float(forest.actors.BOSS_FRAME_ZOOM)) < 0.5, "%s: the fight camera framed the arena (zoom %.1f)" % [phase[0], zoom])
		var full := await grab()
		var still := out.path_join("arena_camera_%s.png" % phase[0])
		full.save_png(ProjectSettings.globalize_path(still) if still.begins_with("res://") else still)
		var row := {"phase": phase[0], "target": [snappedf(target.x, 0.1), snappedf(target.z, 0.1)], "zoom": zoom, "actors": {}}
		for id in ["boss", "squad_0", "squad_1", "squad_2"]:
			var rig = forest.actors.rigs.get(id)
			check(rig != null and is_instance_valid(rig) and rig.load_state == "ready" and rig.is_visible_in_tree(), "%s: %s shown" % [phase[0], id])
			if rig == null or not is_instance_valid(rig) or rig.model == null:
				continue
			var flat := StandardMaterial3D.new()
			flat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			flat.albedo_color = MAGENTA
			flat.cull_mode = BaseMaterial3D.CULL_DISABLED
			var xray := flat.duplicate() as StandardMaterial3D
			xray.no_depth_test = true
			xray.render_priority = 100
			paint(rig, xray)
			await frames(1)
			var all_px: Array = magenta(await grab())
			paint(rig, flat)
			await frames(1)
			var seen_px: Array = magenta(await grab())
			paint(rig, null)
			await frames(1)
			var rect: Rect2 = all_px[1]
			check(int(all_px[0]) > 20 and safe.encloses(rect), "%s: %s in frame (silhouette %s inside %s)" % [phase[0], id, rect, safe])
			var share := float(seen_px[0]) / float(maxi(1, int(all_px[0])))
			check(share >= MIN_VISIBLE, "%s: %s unoccluded (%.0f %% of its silhouette visible)" % [phase[0], id, share * 100.0])
			row.actors[id] = {"silhouette": [roundi(rect.position.x), roundi(rect.position.y), roundi(rect.size.x), roundi(rect.size.y)],
				"silhouettePx": int(all_px[0]) * 4, "visibleShare": snappedf(share, 0.01)}
		row.still = still
		rows.append(row)
	notes.phases = rows
	print("QA_FOREST_ARENA_CAMERA_NOTES ", JSON.stringify(notes))
	print("QA_FOREST_ARENA_CAMERA checks=", checks, " failures=", failures.size())
	for f in failures:
		print("  FAIL ", f)
	quit(0 if failures.is_empty() else 1)
