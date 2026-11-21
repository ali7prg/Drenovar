extends SceneTree
## In-game evidence for the «Лес потерянных» asset integration, rendered from the real DRENOVAR
## city camera (orthographic, size = zoom, target + (75, 83, 75), only target/zoom are moved).
## States are recorded realm fixtures injected through a stub transport (no network); live
## beats (cage unlock, mechanism inputs, boss attacks) are produced by feeding the next fixture
## and advancing the presentation clock frame by frame (run with --fixed-fps 30).
##   xvfb-run -a -s "-screen 0 1366x630x24" godot --path godot/project --rendering-driver vulkan \
##     --fixed-fps 30 -s qa_forest_integration_shots.gd -- --out=/abs/dir [--shots=a,b] [--prefix=p_]

const FIXTURES := "res://data/forest_rescue/game/fixtures/"
const PathMotion = preload("res://src/forest_rescue/game/path_motion.gd")
const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const FPS := 30.0

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
var stub: StubHost
var out := ""
var prefix := ""
var only: PackedStringArray = []
var saved: PackedStringArray = []
var report: Array = []
var clock := 0.0

var looks: Array = []


func _initialize() -> void:
	call_deferred("run")

func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))

func wanted(name: String) -> bool:
	if only.is_empty():
		return true
	for item in only:
		if name.begins_with(item):
			return true
	return false

func frames(count: int, advance_clock := true) -> void:
	for i in count:
		if advance_clock and clock > 0.0:
			clock += 1000.0 / FPS
			forest.client.manual_clock_ms = clock
		await process_frame

func shoot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var summary: PackedStringArray = []
	for id in forest.actors.rigs:
		var rig = forest.actors.rigs[id]
		if is_instance_valid(rig):
			summary.append("%s:%s:%s:L%d:%s" % [id, rig.load_state, "v" if rig.is_visible_in_tree() else "h", rig.lod_level, rig.current_id])
	var occl := ""
	var world = forest.world
	if world != null and world.get("occluders") != null:
		var q: Dictionary = world.occluders.last_query
		occl = " occluders(hiding=%d faded=%d targets=%d cand=%d ms=%.2f)" % [int(q.hiding), world.occluders.faded.size(), int(q.targets), int(q.candidates), float(q.ms)]
	var line := "SHOT %s zoom=%.1f%s actors=%s" % [name, game.stage.camera_zoom, occl, ", ".join(summary)]
	print(line)
	report.append(line)
	var path := out.path_join(prefix + name + ".png")
	root.get_texture().get_image().save_png(path)
	saved.append(path)

func fresh(state_name: String) -> void:
	await fresh_dict(fixture(state_name))


func fresh_dict(state: Dictionary) -> void:
	game.close_modal()
	if forest.mech.is_open():
		forest.mech.close()
	forest.actors.on_stage_changed()
	forest.actors.first_state = true
	forest.client.adv = {}
	forest.client.primed = false
	clock = float(state.get("adventure", {}).get("serverTime", -1.0))
	forest.client.manual_clock_ms = clock
	game.accept(state)
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()
	await process_frame

## Feeds the next recorded state as a live transition (choreography plays).
func live(state_name: String, keep_clock := true) -> void:
	var state := fixture(state_name)
	if not keep_clock:
		clock = float(state.get("adventure", {}).get("serverTime", clock))
		forest.client.manual_clock_ms = clock
	game.accept(state)
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()
	await process_frame

func look(target: Vector3, zoom: float) -> void:
	game.stage.target = target
	game.stage.zoom = zoom
	game.stage.update_camera(0, true)

func settle_world() -> void:
	var world = forest.world
	if world != null and world.get("landmarks") != null and world.landmarks.has_method("finish_arena_load"):
		world.landmarks.finish_arena_load()

func preload_actors(seconds := 0.6) -> void:
	# Lets threaded GLB loads finish so a frame never shows half-loaded actors.
	for i in int(seconds * FPS):
		await frames(1, false)
	for i in 30:
		var loading := false
		for id in forest.actors.rigs:
			var rig = forest.actors.rigs[id]
			if is_instance_valid(rig) and rig.load_state == "loading":
				rig.poll_load(true)
				loading = loading or rig.load_state == "loading"
		settle_world()
		await frames(1, false)
		if not loading:
			break

func anchor(site_id: String, part := "center") -> Vector3:
	var value: Dictionary = forest.site_anchor(site_id)
	return value.get(part, value.get("center", Vector3.ZERO))

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--out="):
			out = argument.trim_prefix("--out=")
		elif argument.begins_with("--prefix="):
			prefix = argument.trim_prefix("--prefix=")
		elif argument.begins_with("--shots="):
			only = argument.trim_prefix("--shots=").split(",", false)
		elif argument.begins_with("--looks="):
			# x,z,zoom,name;x,z,zoom,name … (group v3look: full-reveal state, quick inspection frames)
			for spec in argument.trim_prefix("--looks=").split(";", false):
				var f := spec.split(",", false)
				if f.size() >= 4:
					looks.append([Vector3(float(f[0]), 0, float(f[1])), float(f[2]), f[3]])
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	forest = game.forest_game
	stub = StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub
	await frames(10, false)

	# -------------------------------------------------- debug: realm state fixture (zz_probe_realm)
	if wanted("zzprobe"):
		await fresh("zz_probe_realm")
		for site in ["lf_site_01", "lf_site_02"]:
			look(anchor(site, "cage"), 16.0)
			await preload_actors()
			await frames(10)
			await shoot("zzprobe_" + site)
			for id in forest.actors.rigs:
				var r = forest.actors.rigs[id]
				if is_instance_valid(r) and String(id).begins_with("cage_"):
					print("CAGE ", id, " state=", r.load_state, " vis=", r.visible, " tree=", r.is_visible_in_tree(), " parent=", r.get_parent().name, " pvis=", r.get_parent().visible, " pos=", r.global_position)

	# -------------------------------------------------- P0 set: the playable zooms (24 mechanism UI,
	# 34 route/intro, 68 default, 120 overview) + a z12 close-up, same camera before/after.
	var p0_all := only.is_empty() or only.has("p0")
	var p0_some := p0_all
	for item in only:
		p0_some = p0_some or item.begins_with("p0_")
	if p0_some:
		var scenes := [
			["horse", "horse_joined", "horse", [12.0, 24.0, 34.0, 68.0, 120.0]],
			["route", "prologue_moving", "squad", [12.0, 34.0, 68.0]],
			["site01", "site01_arrived", "site", [12.0, 24.0, 34.0, 68.0]],
			["escort", "site01_escort_walking", "squad", [12.0, 34.0, 68.0]],
			["overview", "completed", "overview", [120.0]],
		]
		for scene in scenes:
			if not p0_all and not only.has("p0_" + scene[0]):
				continue
			await fresh(scene[1])
			await preload_actors()
			await frames(30)
			var at := Vector3.ZERO
			match String(scene[2]):
				"horse":
					at = forest.target_position("lf_horse_origin")
				"squad":
					at = forest.actors.squad_focus()
				"site":
					at = anchor("lf_site_01", "center")
				"overview":
					at = Vector3(2, 0, -6)
			for zoom in scene[3]:
				look(at + (Vector3(0, 0.8, 0) if zoom <= 12.0 else Vector3.ZERO), zoom)
				settle_world()
				await frames(12)
				await shoot("p0_%s_z%d" % [scene[0], int(zoom)])
				var layers: Array = root.find_children("*", "CanvasLayer", true, false)
				for layer: CanvasLayer in layers:
					layer.set_meta("p0_was_visible", layer.visible)
					layer.visible = false
				await frames(2, false)
				await shoot("p0_%s_z%d_nohud" % [scene[0], int(zoom)])
				for layer: CanvasLayer in layers:
					layer.visible = bool(layer.get_meta("p0_was_visible", true))

	# -------------------------------------------------- hall III intro: the mare walks out of the mist
	if wanted("intro"):
		await fresh("intro_offer")
		look(Vector3(5, 0, -4), 70.0)
		stub.replies = [fixture("intro_playing").merged({"events":[{"type":"intro_present", "seq":9001, "revision":1}]})]
		var started := Time.get_ticks_msec()
		while not forest.intro.presenting() and Time.get_ticks_msec() - started < 4000:
			await frames(1)
		while forest.intro.elapsed < 6.4:
			await frames(1)
		var horse = forest.actors.rigs.get("horse")
		if horse != null and is_instance_valid(horse):
			horse.poll_load(true)
		await frames(2)
		await shoot("intro_horse_z40")
		var at: Vector3 = horse.global_position if horse != null and is_instance_valid(horse) else forest.target_position("lf_horse_origin")
		var keep: bool = forest.intro.camera_user_took
		forest.intro.camera_user_took = true
		look(at + Vector3(0, 0.8, 0), 12.0)
		await frames(3)
		await shoot("intro_horse_z12")
		forest.intro.camera_user_took = keep
		while forest.intro.elapsed < 12.4:
			await frames(1)
		await shoot("intro_prompt")
		stub.replies = [fixture("prologue")]
		forest.intro.on_skip()
		await frames(2)

	# -------------------------------------------------- horse + squad at the horse origin
	if wanted("horse"):
		await fresh("horse_joined")
		var p: Vector3 = forest.target_position("lf_horse_origin")
		look(p, 30.0)
		await preload_actors()
		await frames(20)
		await shoot("horse_squad_z30")
		look(p, 68.0)
		await frames(6)
		await shoot("horse_squad_z68")

	# -------------------------------------------------- site 01: oak cage, guardian, trail cache
	if wanted("site01"):
		await fresh("site01_discovered")
		var c := anchor("lf_site_01", "cage")
		look(c, 30.0)
		await preload_actors()
		await frames(20)
		await shoot("site01_caged_z30")
		look(c, 68.0)
		await frames(6)
		await shoot("site01_caged_z68")
		look(c + Vector3(0, 0, 1.0), 14.0)
		await frames(4)
		await shoot("site01_cage_close")

	# -------------------------------------------------- mechanisms (each kind, active state)
	for item in [["mech_trail", "site01_trail_1of3", "lf_site_01"], ["mech_rune", "site02_rune_1of3", "lf_site_02"],
			["mech_winch", "site03_winch_solved", "lf_site_03"], ["mech_paired", "site04_plates_held", "lf_site_04"]]:
		if not wanted(item[0]):
			continue
		await fresh(item[1])
		var spot := anchor(item[2], "artifact")
		look(spot, 30.0)
		await preload_actors()
		await frames(20)
		await shoot(item[0] + "_z30")
		look(spot + Vector3(0, 0.5, 0), 9.0)
		await frames(4)
		await shoot(item[0] + "_close")

	# -------------------------------------------------- guardian battle (original creature model)
	if wanted("battle"):
		await fresh("site01_battle_active")
		var g := anchor("lf_site_01", "guardian")
		look(g, 30.0)
		await preload_actors()
		for i in 4:
			await frames(int(FPS * 1.2))
			await shoot("battle_z30_%d" % i)

	# -------------------------------------------------- cage unlock: soldier, key, gate, exit
	if wanted("unlock"):
		await fresh("site01_battle_victory")
		var c := anchor("lf_site_01", "cage")
		look(c + Vector3(0.8, 0.8, 2.2), 12.0)
		await preload_actors()
		await frames(10)
		await live("site01_cage_open")
		for at in [0.9, 1.9, 3.1, 4.6, 6.2, 8.2, 11.0]:
			var target_frame := int(at * FPS)
			var done := int(forest.get_meta("unlock_frame", 0))
			await frames(maxi(0, target_frame - done))
			forest.set_meta("unlock_frame", target_frame)
			await shoot("unlock_%04.1fs" % at)
		forest.remove_meta("unlock_frame")

	# -------------------------------------------------- captive variety: three cages, real captives
	# (captive_variants.json + variant masks), seated, then leaving through the door. Rigs are
	# built with the game's own Rig/look code on open town ground (presentation check only).
	if wanted("variety"):
		# Each test cage stands in its own site's glade (all revealed in the completed state, the
		# real cage there is open and empty), 3 m towards the approach.
		await fresh("completed")
		await preload_actors()
		# The glade edges are narrow for three test cages: the canopy is hidden for this lineup so
		# nothing but the captives is judged (same lighting, camera and materials as the game).
		if forest.world != null and forest.world.get("canopy") != null:
			forest.world.canopy.visible = false
		var Rig = load("res://src/forest_rescue/game/actor_rig.gd")
		var cases := [["lf_site_12", "root"], ["lf_site_08", "iron"], ["lf_site_07", "oak"]]
		var built: Array = []
		for i in cases.size():
			var site_id: String = cases[i][0]
			var a: Dictionary = forest.site_anchor(site_id)
			var center: Vector3 = a.get("center", Vector3.ZERO)
			var approach: Vector3 = a.get("approach", center + Vector3(0, 0, 7))
			var out_dir := Vector3(approach.x - center.x, 0, approach.z - center.z).normalized()
			var p3: Vector3 = center + out_dir * 3.2
			var spot: Vector3 = forest.ground(p3.x, p3.z)
			var cage = Rig.new()
			cage.setup("variety_cage_%d" % i, forest.actors.cage_file(cases[i][1]))
			forest.actors.props_parent.add_child(cage)
			cage.position = spot
			cage.rotation.y = atan2(out_dir.x, out_dir.z) + deg_to_rad(25.0)
			var people: Array = []
			var letters := ["a", "b", "c"]
			for k in 3:
				var id := "lf_captive_%s_%s" % [site_id.trim_prefix("lf_site_"), letters[k]]
				var look: Dictionary = forest.actors.captive_variant({"id":id})
				var person = Rig.new()
				person.model_scale = float(look.get("scale", 1.0))
				person.variant = look
				person.setup("variety_%s" % id, "res://assets/forest_rescue/humans/lf_civilian_%s.glb" % forest.actors.captive_visual({"id":id}))
				forest.actors.root.add_child(person)
				people.append(person)
			built.append([cage, people, site_id])
		for entry in built:
			entry[0].poll_load(true)
			for person in entry[1]:
				person.poll_load(true)
		await frames(2)
		for entry in built:
			var cage = entry[0]
			cage.set_active(true)
			var roof: Node3D = cage.part("roof")
			if roof != null:
				roof.visible = false
			cage.hold_end(["lf_cage_gate_close"])
			for k in 3:
				var person = entry[1][k]
				person.set_active(true)
				var slot: Node3D = cage.part("captive_slot_%d" % k)
				person.global_position = slot.global_position if slot != null else cage.global_position
				person.rotation.y = cage.rotation.y + 0.35 * (k - 1)
				person.play(["lf_civilian_cage_sit"] if k == 0 else (["lf_civilian_cage_stand"] if k == 1 else ["lf_civilian_cage_wait"]), 0.0)
		await frames(40)
		for i in built.size():
			look(built[i][0].global_position + Vector3(0, 1.0, 0.6), 6.0)
			await frames(3)
			await shoot("variety_seated_%s" % built[i][2])
		look(built[0][0].global_position, 30.0)
		await frames(4)
		await shoot("variety_seated_z30")
		# Gates open, the three leave through the door one after another (exit clip on the path).
		for entry in built:
			entry[0].play(["lf_cage_gate_open"], 0.0, true)
		await frames(40)
		var t0 := 0.0
		for step in int(FPS * 4.2):
			t0 += 1.0 / FPS
			for entry in built:
				var cage = entry[0]
				for k in 3:
					var person = entry[1][k]
					var start := 0.6 * k
					if t0 < start:
						continue
					var a: Node3D = cage.part("exit_corridor_0")
					var b: Node3D = cage.part("exit_corridor_3")
					var slot: Node3D = cage.part("captive_slot_%d" % k)
					var path := [slot.global_position, a.global_position, b.global_position + cage.global_basis * Vector3(-1.2 + 1.2 * k, 0, 0.8)]
					var route: Dictionary = PathMotion.build(path)
					var sample: Dictionary = PathMotion.sample(route, (t0 - start) * 1.0)
					person.global_position = sample.position
					person.rotation.y = PathMotion.yaw_of(sample.tangent)
					person.play(["lf_civilian_exit"], 0.15)
			await frames(1)
		for i in built.size():
			look(built[i][0].global_position + Vector3(0.4, 1.0, 2.2), 6.5)
			await frames(3)
			await shoot("variety_exiting_%s" % built[i][2])
		for entry in built:
			entry[0].queue_free()
			for person in entry[1]:
				person.queue_free()
		if forest.world != null and forest.world.get("canopy") != null:
			forest.world.canopy.visible = true


	# -------------------------------------------------- cage floors (texture check): oak / iron / root,
	# empty, roof faded as with captives inside; z12 close (canopy hidden) and z30 game view.
	if wanted("cagefloor"):
		await fresh("completed")
		await preload_actors()
		var Rig = load("res://src/forest_rescue/game/actor_rig.gd")
		var built: Array = []
		for item in [["oak", "lf_site_07"], ["iron", "lf_site_08"], ["root", "lf_site_12"]]:
			var a: Dictionary = forest.site_anchor(item[1])
			var center: Vector3 = a.get("center", Vector3.ZERO)
			var approach: Vector3 = a.get("approach", center + Vector3(0, 0, 7))
			var out_dir := Vector3(approach.x - center.x, 0, approach.z - center.z).normalized()
			var p3: Vector3 = center + out_dir * 3.2
			var cage = Rig.new()
			cage.setup("floor_cage_" + item[0], forest.actors.cage_file(item[0]))
			forest.actors.props_parent.add_child(cage)
			cage.position = forest.ground(p3.x, p3.z)
			cage.rotation.y = atan2(out_dir.x, out_dir.z) + deg_to_rad(25.0)
			cage.poll_load(true)
			built.append([cage, item[0]])
		await frames(2)
		for entry in built:
			var cage = entry[0]
			cage.set_active(true)
			var roof: Node3D = cage.part("roof")
			if roof != null:
				roof.visible = false
			cage.hold_end(["lf_cage_gate_settle"])
		await frames(10)
		for entry in built:
			forest.world.canopy.visible = false
			look(entry[0].global_position + Vector3(0, 0.6, 0.3), 12.0)
			await frames(3)
			await shoot("cagefloor_%s_z12" % entry[1])
			forest.world.canopy.visible = true
			look(entry[0].global_position, 30.0)
			await frames(3)
			await shoot("cagefloor_%s_z30" % entry[1])
		for entry in built:
			entry[0].queue_free()

	# -------------------------------------------------- artifact seated in the door socket (glow)
	if wanted("socket"):
		await fresh("site01_cage_open")
		var c := anchor("lf_site_01", "cage")
		look(c, 20.0)
		await preload_actors()
		await frames(30)
		var prop = forest.actors.rigs.get("artifact_lf_site_01")
		var at: Vector3 = prop.global_position if prop != null and is_instance_valid(prop) else c
		look(at, 3.2)
		await frames(10)
		await shoot("socket_z3")
		look(at, 7.0)
		await frames(4)
		await shoot("socket_z7")

	# -------------------------------------------------- escort walking
	if wanted("escort"):
		await fresh("site01_escort_walking")
		await preload_actors()
		await frames(5)
		var mid: Vector3 = forest.actors.squad_focus()
		look(mid, 30.0)
		await frames(20)
		mid = forest.actors.squad_focus()
		look(mid, 30.0)
		await frames(4)
		await shoot("escort_z30")
		look(mid, 68.0)
		await frames(4)
		await shoot("escort_z68")

	# -------------------------------------------------- arrival home + reward pile
	if wanted("home"):
		await fresh("site01_escort_walking")
		await preload_actors()
		await live("site01_escort_home", false)
		var home: Vector3 = forest.target_position("lf_home_reception")
		look(home, 26.0)
		await preload_actors(0.2)
		await frames(int(FPS * 2.8))
		await shoot("home_arrive_z26")
		await frames(int(FPS * 1.2))
		await shoot("home_thank_z26")

	# -------------------------------------------------- boss fight
	if wanted("boss"):
		for pct in [10, 35, 60, 85]:
			await fresh("boss_battle_%d" % pct)
			var arena: Vector3 = forest.target_position("lf_boss_ancient_maw")
			# the game's own fight framing (actor_director.boss_fight_frame, zoom 36)
			var frame_at: Vector3 = forest.actors.boss_fight_frame() if forest.actors.has_method("boss_fight_frame") else arena + Vector3(0, 0, 3)
			look(frame_at, 32.0)
			await preload_actors()
			await frames(int(FPS * 0.8))
			await shoot("boss_%d_z32" % pct)
			if pct == 35:
				forest.world.canopy.visible = false
				await frames(3)
				await shoot("boss_35_z32_arena_only")
				forest.world.canopy.visible = true
		look(forest.target_position("lf_boss_ancient_maw"), 68.0)
		await frames(4)
		settle_world()
		await frames(2)
		await shoot("boss_85_z68")

	# -------------------------------------------------- atlas v2 pass 2: every glade as art/01 paints it
	# (QA projection: all 12 sites discovered, cages closed with their captives, guardians gone,
	# camps lit, the whole forest revealed, no HUD), the same zone frames as qa_forest_world_shots.
	if wanted("v2all"):
		var all_state: Dictionary = fixture("boss_unlocked")
		var adv: Dictionary = all_state.adventure
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
		await fresh_dict(all_state)
		game.hud.visible = false
		if forest.get("hud") != null:
			forest.hud.visible = false
		look(Vector3(-80, 0, -14), 68.0)
		await preload_actors(2.0)
		forest.world.fog.set_dim(0.0)
		forest.world.fog.finish_now()
		var zones := [["grove", Vector3(-84, 0, -16)], ["stones", Vector3(-56, 0, -70)], ["west", Vector3(-76, 0, 52)],
			["quarry", Vector3(-8, 0, 94)], ["south_pines", Vector3(62, 0, 92)], ["lake", Vector3(94, 0, 44)],
			["river_bridge", Vector3(88, 0, 16)], ["east", Vector3(94, 0, -40)], ["waterfall", Vector3(22, 0, -66)],
			["arena", Vector3(20, 0, -88)]]
		for spec in zones:
			look(spec[1], 68.0)
			settle_world()
			await preload_actors(0.4)
			await frames(12)
			await shoot("v2all_full_%s_z68" % spec[0])
		for spec in [["grove", Vector3(-82, 0, -15)], ["south_pines", Vector3(60, 0, 92)], ["lake", Vector3(92, 0, 42)],
				["quarry", Vector3(-6, 0, 98)], ["waterfall", Vector3(22, 0, -65)], ["arena", Vector3(19, 0, -90)],
				["river_bridge", Vector3(90, 0, 20)], ["east", Vector3(93, 0, -38)]]:
			look(spec[1], 34.0)
			settle_world()
			await preload_actors(0.3)
			await frames(10)
			await shoot("v2all_close_%s_z34" % spec[0])
		look(Vector3(0, 0, 0), 120.0)
		settle_world()
		await frames(20)
		await shoot("v2all_overview_z120")
		root.size = Vector2i(1536, 1024)
		await frames(6)
		look(Vector3(17.8, 0, 13.6), 195.0)
		settle_world()
		await frames(20)
		await shoot("v2all_full_overview_art01")
		root.size = Vector2i(1366, 630)
		await frames(6)
		game.hud.visible = true
		if forest.get("hud") != null:
			forest.hud.visible = true

	# -------------------------------------------------- layout pass 3: art-derived zone frames, feature
	# crops at zoom 68, overviews, the four extreme camera positions at zoom 120 (fog edge) and the city
	# same-state diff with the forest grade ("boost") on / off
	if wanted("v3"):
		var all3: Dictionary = fixture("boss_unlocked")
		var adv3: Dictionary = all3.adventure
		for poi in adv3.pois:
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
		for site_entry in adv3.campaign.sites:
			site_entry.step = 3
		adv3.campaign.rescuedIds = []
		adv3.campaign.rescuedCount = 0
		adv3.campaign.phase = "rescue"
		var bits3 := PackedByteArray()
		bits3.resize(392)
		bits3.fill(255)
		adv3.fog.visibleBase64 = Marshalls.raw_to_base64(bits3)
		adv3.fog.revision = 9999
		await fresh_dict(all3)
		game.hud.visible = false
		if forest.get("hud") != null:
			forest.hud.visible = false
		look(Vector3(-80, 0, -14), 68.0)
		await preload_actors(2.0)
		forest.world.fog.set_dim(0.0)
		forest.world.fog.finish_now()
		var zones_path := ProjectSettings.globalize_path("res://").path_join("../../forest_rescue/qa/ingame/integration/zones_v3.json").simplify_path()
		var zf: Variant = JSON.parse_string(FileAccess.get_file_as_string(zones_path))
		if zf is Dictionary:
			for zone in zf.zones:
				look(Vector3(float(zone.target[0]), 0, float(zone.target[1])), float(zone.zoom))
				settle_world()
				await preload_actors(0.4)
				await frames(12)
				await shoot("v3_zone_%s" % zone.name)
		for spec in [["bridge", Vector3(90.5, 0, 20)], ["waterfall", Vector3(21, 0, -66)], ["lake", Vector3(95, 0, 34)],
				["quarry", Vector3(-12, 0, 98)], ["arena", Vector3(18, 0, -90)], ["camp01", Vector3(-80, 0, -14)],
				["south_marsh", Vector3(64, 0, 96)]]:
			look(spec[1], 68.0)
			settle_world()
			await preload_actors(0.3)
			await frames(10)
			await shoot("v3feat_%s_z68" % spec[0])
		look(Vector3(0, 0, 0), 120.0)
		settle_world()
		await frames(20)
		await shoot("v3_overview_z120")
		for spec in [["ne", Vector3(147, 0, -118)], ["se", Vector3(147, 0, 118)], ["sw", Vector3(-147, 0, 118)],
				["nw", Vector3(-147, 0, -118)]]:
			look(spec[1], 120.0)
			settle_world()
			await frames(16)
			await shoot("v3edge_%s_z120" % spec[0])
		root.size = Vector2i(1536, 1024)
		await frames(6)
		look(Vector3(17.8, 0, 13.6), 195.0)
		settle_world()
		await frames(20)
		await shoot("v3_full_overview_art01")
		root.size = Vector2i(1366, 630)
		await frames(6)
		game.hud.visible = true
		if forest.get("hud") != null:
			forest.hud.visible = true

	# -------------------------------------------------- quick inspection frames (full reveal, all sites closed)
	if wanted("v3look") and not looks.is_empty():
		var st4: Dictionary = fixture("boss_unlocked")
		var adv4: Dictionary = st4.adventure
		for poi in adv4.pois:
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
		for site_entry in adv4.campaign.sites:
			site_entry.step = 3
		adv4.campaign.rescuedIds = []
		adv4.campaign.rescuedCount = 0
		adv4.campaign.phase = "rescue"
		var bits4 := PackedByteArray()
		bits4.resize(392)
		bits4.fill(255)
		adv4.fog.visibleBase64 = Marshalls.raw_to_base64(bits4)
		adv4.fog.revision = 9999
		await fresh_dict(st4)
		game.hud.visible = false
		if forest.get("hud") != null:
			forest.hud.visible = false
		look(looks[0][0], float(looks[0][1]))
		await preload_actors(2.0)
		forest.world.fog.set_dim(0.0)
		forest.world.fog.finish_now()
		for spec in looks:
			look(spec[0], float(spec[1]))
			settle_world()
			await preload_actors(0.3)
			await frames(10)
			await shoot("look_%s" % spec[2])
		game.hud.visible = true
		if forest.get("hud") != null:
			forest.hud.visible = true

	# -------------------------------------------------- layout pass 3: city unchanged (same state, boost off / on)
	if wanted("v3city"):
		await fresh_dict(fixture("boss_unlocked"))
		game.hud.visible = false
		if forest.get("hud") != null:
			forest.hud.visible = false
		look(Vector3(0, 0, 0), 40.0)
		await preload_actors(2.0)
		# city same-state diff: forest grade on / off (city buildings, ground and lighting must not change)
		for zoom_c in [40.0, 68.0]:
			look(Vector3(0, 0, 0), zoom_c)
			settle_world()
			await frames(12)
			ForestKit.set_grade_enabled(false)
			if forest.world.get("impostors") != null:
				forest.world.impostors.set_grade_enabled(false)
			await frames(6)
			await shoot("v3city_boost_off_z%d" % int(zoom_c))
			ForestKit.set_grade_enabled(true)
			if forest.world.get("impostors") != null:
				forest.world.impostors.set_grade_enabled(true)
			await frames(6)
			await shoot("v3city_boost_on_z%d" % int(zoom_c))
			await frames(6)
			await shoot("v3city_boost_on2_z%d" % int(zoom_c))      # same setting again: animation noise mask
		game.hud.visible = true
		if forest.get("hud") != null:
			forest.hud.visible = true

	# -------------------------------------------------- art/01 overview: the whole revealed forest
	if wanted("overview"):
		await fresh("completed")
		await preload_actors()
		look(Vector3(2, 0, -6), 130.0)
		settle_world()
		await frames(20)
		await shoot("overview_z130")
		look(forest.target_position("lf_site_01") + Vector3(6, 0, -4), 68.0)
		await frames(10)
		await shoot("overview_z68")

	# -------------------------------------------------- each boss attack: telegraph + active window
	if wanted("tele"):
		var seen := {}
		for pct in [10, 35, 60, 85]:
			await fresh("boss_battle_%d" % pct)
			var fight: Dictionary = forest.client.battle()
			var arena: Vector3 = forest.target_position("lf_boss_ancient_maw")
			var frame_at: Vector3 = forest.actors.boss_fight_frame() if forest.actors.has_method("boss_fight_frame") else arena + Vector3(0, 0, 4)
			look(frame_at, 32.0)
			await preload_actors()
			var death_at := INF
			for event in fight.get("timeline", []):
				if String(event.get("type", "")) == "death":
					death_at = float(event.t)
			for event in fight.get("timeline", []):
				var attack := String(event.get("attack", ""))
				if String(event.get("type", "")) != "telegraph" or seen.has(attack) or float(event.t) + 5.0 > death_at:
					continue
				seen[attack] = true
				var telegraph := float(event.get("telegraphSeconds", 2.4))
				for local in [telegraph * 0.75, telegraph + 0.12]:
					clock = float(fight.startedAt) + (float(event.t) + local) * 1000.0 - 400.0
					forest.client.manual_clock_ms = clock
					await frames(12)
					await shoot("tele_%s_%s" % [attack, "active" if local > telegraph else "warn"])

	print("FOREST_INTEGRATION_SHOTS saved=", saved.size())
	var file := FileAccess.open(out.path_join(prefix + "shots.log"), FileAccess.WRITE)
	if file != null:
		file.store_string("\n".join(report))
	quit(0)
