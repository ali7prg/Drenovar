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
	var line := "SHOT %s zoom=%.1f actors=%s" % [name, game.stage.camera_zoom, ", ".join(summary)]
	print(line)
	report.append(line)
	var path := out.path_join(prefix + name + ".png")
	root.get_texture().get_image().save_png(path)
	saved.append(path)

func fresh(state_name: String) -> void:
	game.close_modal()
	if forest.mech.is_open():
		forest.mech.close()
	forest.actors.on_stage_changed()
	forest.actors.first_state = true
	forest.client.adv = {}
	forest.client.primed = false
	var state := fixture(state_name)
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
			look(arena + Vector3(0, 0, 3), 40.0)
			await preload_actors()
			await frames(int(FPS * 0.8))
			await shoot("boss_%d_z40" % pct)
		look(forest.target_position("lf_boss_ancient_maw"), 68.0)
		await frames(4)
		settle_world()
		await frames(2)
		await shoot("boss_85_z68")

	# -------------------------------------------------- each boss attack: telegraph + active window
	if wanted("tele"):
		var seen := {}
		for pct in [10, 35, 60, 85]:
			await fresh("boss_battle_%d" % pct)
			var fight: Dictionary = forest.client.battle()
			var arena: Vector3 = forest.target_position("lf_boss_ancient_maw")
			look(arena + Vector3(0, 0, 4), 34.0)
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
