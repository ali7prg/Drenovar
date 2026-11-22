extends SceneTree
## P2.9 captive check (layout v2 / atlas v2):
##  A. all 12 sites closed: each site's three captives stand / sit inside their cage (footprint of the
##     cage model, 0.12 m margin) on the cage floor over the terrain, never under it or floating;
##  B. site 01 cage opening (site01_battle_victory → live site01_cage_open, key + cage choreography, 24 s):
##     the captives leave through
##     the door (no teleport: ≤ 0.6 m per frame), end outside the cage on the ground;
##  C. site 01 escort (site01_escort_walking, the clock running): they walk behind the squad on the
##     trail (move, stay on the ground, within 9 m of the squad focus);
##  D. one still per act (sites 01 / 04 / 07 / 10 at zoom 22, fog revealed) when a renderer exists.
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan --fixed-fps 30 \
##     -s qa_forest_captives.gd [-- --out=<dir>]
## Headless runs (godot --headless --fixed-fps 30 …) do A–C (no stills). --fixed-fps 30 is required: the
## choreography advances by frame delta.

const FIXTURES := "res://data/forest_rescue/game/fixtures/"
const FPS := 30.0
const ACT_SITES := ["lf_site_01", "lf_site_04", "lf_site_07", "lf_site_10"]

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
var out := "res://../../forest_rescue/qa/ingame/integration/captives"


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
	call_deferred("run")


func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		printerr("QA_FOREST_CAPTIVES FAIL: ", detail)


func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))


func frames(count: int) -> void:
	for i in count:
		clock += 1000.0 / FPS
		forest.client.manual_clock_ms = clock
		await process_frame


func apply(state: Dictionary) -> void:
	game.close_modal()
	forest.actors.on_stage_changed()
	forest.actors.first_state = true
	forest.client.adv = {}
	forest.client.primed = false
	clock = float(state.get("adventure", {}).get("serverTime", 0.0))
	forest.client.manual_clock_ms = clock
	# 1022: fixtures jump back in time; 1021's accept() keeps a newer state unless the one on screen is a cached copy
	game.showing_cached_state = true
	game.accept(state)
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()
	await frames(4)


func live(state: Dictionary) -> void:
	game.accept(state)
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()


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


func look(target: Vector3, zoom: float) -> void:
	game.stage.target = target
	game.stage.zoom = zoom
	game.stage.update_camera(0, true)


## World-space AABB of a rig's visible model meshes.
func model_box(rig: Node3D) -> AABB:
	var box := AABB()
	var first := true
	if rig == null or rig.get("model") == null:
		return box
	for mesh: MeshInstance3D in (rig.model as Node).find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh == null:
			continue
		var b: AABB = mesh.global_transform * mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


func ground(p: Vector3) -> float:
	return float(forest.world.height_at(p.x, p.z))


func captive_ids(site_id: String) -> Array:
	var out_ids: Array = []
	for poi in forest.client.adv.get("pois", []):
		if String(poi.get("id", "")) == site_id:
			for person in poi.get("captives", []):
				out_ids.append(String(person.get("id", "")))
	return out_ids


func cage_center(site_id: String) -> Vector3:
	var anchor: Dictionary = forest.world.site_anchor(site_id)
	return anchor.get("cage", anchor.get("center", Vector3.INF))


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
	# ---------------------------------------------------------------- A. all 12 sites closed
	var st: Dictionary = fixture("boss_unlocked")
	var adv: Dictionary = st.adventure
	for poi in adv.pois:
		if String(poi.get("kind", "")) != "site":
			continue
		poi.step = 3
		poi.cagePose = "closed"
		poi.discovered = true
		poi.available = true
		for person in poi.get("captives", []):
			person.state = "caged"
		if poi.get("guardian") is Dictionary:
			poi.guardian.state = "defeated"
		if poi.get("artifact") is Dictionary:
			poi.artifact.state = "held"
			poi.artifact.held = true
	for site_entry in adv.campaign.sites:
		site_entry.step = 3
	adv.campaign.rescuedIds = []
	adv.campaign.rescuedCount = 0
	adv.campaign.phase = "rescue"
	var bits := PackedByteArray()
	bits.resize(392)
	bits.fill(255)
	adv.fog.visibleBase64 = Marshalls.raw_to_base64(bits)
	adv.fog.revision = 9999
	await apply(st)
	await frames(20)
	await load_rigs()
	await frames(30)
	var sites_checked := 0
	var captives_checked := 0
	var worst_floor := 0.0
	var worst_inside := 99.0
	for n in range(1, 13):
		var site_id := "lf_site_%02d" % n
		var cage = forest.actors.rigs.get("cage_" + site_id)
		check(cage != null and cage.load_state == "ready", "%s: cage rig ready" % site_id)
		if cage == null or cage.load_state != "ready":
			continue
		var box := model_box(cage)
		var ids := captive_ids(site_id)
		check(ids.size() == 3, "%s: three captives in the state (%d)" % [site_id, ids.size()])
		sites_checked += 1
		var base_gap: float = cage.global_position.y - ground(cage.global_position)
		check(absf(base_gap) <= 0.15, "%s: cage stands on the terrain (%.2f m)" % [site_id, base_gap])
		for index in ids.size():
			var id: String = ids[index]
			var rig = forest.actors.rigs.get(id)
			check(rig != null and rig.load_state == "ready", "%s: rig ready" % id)
			if rig == null:
				continue
			captives_checked += 1
			var p: Vector3 = rig.global_position
			var inside := minf(minf(p.x - box.position.x, box.end.x - p.x), minf(p.z - box.position.z, box.end.z - p.z))
			worst_inside = minf(worst_inside, inside)
			check(inside >= 0.12, "%s: inside its cage footprint (margin %.2f m) at %s" % [id, inside, p.snapped(Vector3.ONE * 0.01)])
			# on the cage floor: the cage's captive_slot node (raised floors: iron / stone cages), which itself
			# lies over the terrain
			var above := p.y - ground(p)
			var slot: Node3D = cage.part("captive_slot_%d" % (index % 3))
			var floor_y: float = slot.global_position.y if slot != null else ground(p) + 0.12
			worst_floor = maxf(worst_floor, absf(p.y - floor_y))
			check(absf(p.y - floor_y) <= 0.06, "%s: on its cage floor slot (%.2f m off)" % [id, p.y - floor_y])
			check(above >= -0.05 and above <= 0.75, "%s: cage floor over the terrain (%.2f m above ground)" % [id, above])
			check(p.y >= box.position.y - 0.05, "%s: not under the cage base" % id)
	notes.sites = sites_checked
	notes.captives = captives_checked
	notes.worst_inside_margin_m = snappedf(worst_inside, 0.01)
	notes.worst_floor_offset_m = snappedf(worst_floor, 0.01)
	# ---------------------------------------------------------------- D. one still per act
	var rendering := DisplayServer.get_name() != "headless"
	if rendering:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out) if out.begins_with("res://") else out)
		game.hud.visible = false
		if forest.get("hud") != null:
			forest.hud.visible = false
		forest.world.fog.set_dim(0.0)
		forest.world.fog.finish_now()
		var stills: Array = []
		for act in ACT_SITES.size():
			var site_id: String = ACT_SITES[act]
			look(cage_center(site_id), 22.0)
			await frames(12)
			await load_rigs()
			await frames(6)
			await RenderingServer.frame_post_draw
			var path := out.path_join("captives_act%d_%s.png" % [act + 1, site_id])
			root.get_texture().get_image().save_png(ProjectSettings.globalize_path(path) if path.begins_with("res://") else path)
			stills.append(path)
		notes.stills = stills
		game.hud.visible = true
		if forest.get("hud") != null:
			forest.hud.visible = true
	# ---------------------------------------------------------------- B. site 01 cage opening
	await apply(fixture("site01_battle_victory"))
	await frames(20)
	await load_rigs()
	var center := cage_center("lf_site_01")
	look(center, 26.0)
	await frames(10)
	var cage01 = forest.actors.rigs.get("cage_lf_site_01")
	var box01 := model_box(cage01)
	var ids01 := captive_ids("lf_site_01")
	var last := {}
	var max_step := 0.0
	live(fixture("site01_cage_open"))
	for step in int(24.0 * FPS):
		await frames(1)
		for id in ids01:
			var rig = forest.actors.rigs.get(id)
			if step % 45 == 0 and OS.get_cmdline_user_args().has("--debug"):
				print("B ", step, " ", id, " ", rig != null and is_instance_valid(rig), " ", rig.global_position if rig != null and is_instance_valid(rig) else Vector3.INF, " choreo=", forest.actors.choreo.keys())
			if rig == null or not is_instance_valid(rig):
				continue
			var p: Vector3 = rig.global_position
			if last.has(id):
				max_step = maxf(max_step, Vector2(p.x, p.z).distance_to(Vector2(last[id].x, last[id].z)))
			last[id] = p
	check(max_step <= 0.6, "cage opening: captives walk out (largest step %.2f m per frame)" % max_step)
	notes.exit_max_step_m = snappedf(max_step, 0.01)
	var outside := 0
	for id in ids01:
		var rig = forest.actors.rigs.get(id)
		if rig == null or not is_instance_valid(rig):
			continue
		var p: Vector3 = rig.global_position
		var out_of_box := p.x < box01.position.x - 0.05 or p.x > box01.end.x + 0.05 or p.z < box01.position.z - 0.05 or p.z > box01.end.z + 0.05
		outside += 1 if out_of_box else 0
		check(absf(p.y - ground(p)) <= 0.2, "%s: on the ground after leaving the cage (%.2f m)" % [id, p.y - ground(p)])
	check(outside == ids01.size() and ids01.size() == 3, "cage opening: all captives outside the cage afterwards (%d/%d)" % [outside, ids01.size()])
	# ---------------------------------------------------------------- C. site 01 escort
	await apply(fixture("site01_escort_walking"))
	await frames(20)
	await load_rigs()
	var start := {}
	var worst_gap := 0.0
	var worst_ground := 0.0
	for step in int(5.0 * FPS):
		await frames(1)
		var focus: Vector3 = forest.actors.squad_focus()
		look(focus, 30.0)
		if step < 15:
			continue
		for id in ids01:
			var rig = forest.actors.rigs.get(id)
			if rig == null or not is_instance_valid(rig) or not rig.visible:
				continue
			var p: Vector3 = rig.global_position
			if not start.has(id):
				start[id] = p
			worst_gap = maxf(worst_gap, Vector2(p.x, p.z).distance_to(Vector2(focus.x, focus.z)))
			worst_ground = maxf(worst_ground, absf(p.y - ground(p)))
	var moved := 0
	for id in start:
		var rig = forest.actors.rigs.get(id)
		if rig != null and is_instance_valid(rig) and Vector2(rig.global_position.x, rig.global_position.z).distance_to(Vector2(start[id].x, start[id].z)) > 1.0:
			moved += 1
	check(start.size() == 3, "escort: three captives on the trail (%d)" % start.size())
	check(moved == start.size(), "escort: every captive walks (%d/%d moved > 1 m)" % [moved, start.size()])
	check(worst_gap <= 9.0, "escort: captives follow within 9 m of the squad (worst %.1f m)" % worst_gap)
	check(worst_ground <= 0.2, "escort: captives stay on the ground (worst %.2f m)" % worst_ground)
	notes.escort_worst_gap_m = snappedf(worst_gap, 0.1)
	print("QA_FOREST_CAPTIVES_NOTES ", JSON.stringify(notes))
	print("QA_FOREST_CAPTIVES checks=", checks, " failures=", failures.size())
	for f in failures:
		print("  FAIL ", f)
	quit(0 if failures.is_empty() else 1)
