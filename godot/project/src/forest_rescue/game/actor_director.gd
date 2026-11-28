extends Node
## Adventure actors under forest_world.actors_root() / props under props_root().
## Every pose is derived from the authoritative projection (state.adventure) and the server
## clock; events only add short presentation beats (cage opening, death, arrival) during a
## live session. After a reload the stable pose is restored from state: open door, artifact
## hidden or in the socket, captives absent once home, defeated guardians removed.
##
## Asset wiring (each GLB per its <id>.meta.json):
## * LOD: one LOD visible at a time, chosen by the city zoom (actor_rig.set_lod, lod_scale).
## * Painted look on actors/props (actor_rig.apply_look); *_glow keeps its emission.
## * Locomotion playback = route speed / authored groundSpeed_mps (actor_rig.locomote).
## * Captives sit on the cage floor (captive_slot_N nodes): sit → stand_up → exit through the
##   door (exit_corridor_N), follow / follow_tired during the escort, arrive + thank at home.
## * Unlock: the soldier's lf_soldier_unlock `latch_release` marker starts lf_cage_unlock, its
##   `latch_clear` marker swings the gate (lf_cage_gate_open → settle), `passage_clear` lets
##   the captives out. The artifact (site variant node) is parented to the live key_slot node
##   (moves with the door), plays lf_artifact_insert and glows (lf_artifact_glow).
## * Socket plates: socket_<family> of the server's artifact family is shown, the rest hidden.
## * Cage roof fades while captives are inside (the city camera is always above).
## * Mechanisms: node poses composed from their clips per state (progress/solved/plates) and
##   animated on every change (mechanism_ui reports the chosen symbol for wrong inputs).
## * Boss: recommendedScale 1.52, telegraphs scaled with it, awaken / attacks (server
##   telegraph windows) / hit / stagger + phase_roar at phase changes / death; turn clips
##   yaw the node with the meta rootYawDeg smoothstep curve (horse turns the same way).

const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
const PathMotion = preload("res://src/forest_rescue/game/path_motion.gd")
const Telegraphs = preload("res://src/forest_rescue/game/boss_telegraphs.gd")
const ASSETS := "res://assets/forest_rescue/"
const HORSE_GLB := ASSETS + "horse/lf_horse_origin.glb"
const SQUAD_GLBS := [ASSETS + "humans/lf_squad_captain.glb", ASSETS + "humans/lf_squad_shield_guard.glb", ASSETS + "humans/lf_squad_scout.glb"]
const BOSS_GLB := ASSETS + "boss/lf_boss_ancient_maw.glb"
const SUPPLIES_GLB := ASSETS + "props/lf_props_supplies.glb"
const CAGE_FILES := {"oak":"lf_cage_wood", "wood":"lf_cage_wood", "iron":"lf_cage_iron", "root":"lf_cage_root"}
const HORSE_CLIPS := {"idle":["lf_horse_idle", "Idle"], "walk":["lf_horse_walk", "Walk"], "run":["lf_horse_trot", "Run"], "walk_speed":1.3, "run_speed":3.2}
const SOLDIER_CLIPS := {"idle":["lf_soldier_idle", "Idle"], "walk":["lf_soldier_walk", "Walk"], "run":["lf_soldier_jog", "Run"], "walk_speed":1.4, "run_speed":3.0}
const GUARD_CLIPS := {"idle":["lf_soldier_guard", "lf_soldier_idle", "Shield_Block", "Idle"], "walk":["lf_soldier_walk", "Walk"], "run":["lf_soldier_jog", "Run"], "walk_speed":1.4, "run_speed":3.0}
const CIVILIAN_CLIPS := {"idle":["lf_civilian_wait", "Idle"], "walk":["lf_civilian_follow", "Walk"], "walk_speed":1.2}
const TIRED_CLIPS := {"idle":["lf_civilian_wait", "Idle"], "walk":["lf_civilian_follow_tired", "lf_civilian_follow", "Walk"], "walk_speed":0.95}
const EXIT_CLIPS := {"idle":["lf_civilian_wait", "Idle"], "walk":["lf_civilian_exit", "lf_civilian_follow", "Walk"], "walk_speed":1.0}
const CREATURE_CLIPS := {"idle":["Idle"], "walk":["Walk"], "run":["Run"], "walk_speed":1.6, "run_speed":4.0}
const BOSS_CLIPS := {"idle":["lf_boss_idle", "Idle"], "walk":["lf_boss_walk", "Walk"], "walk_speed":2.25}
const CAGE_IDLES := [["lf_civilian_cage_sit", "Idle"], ["lf_civilian_cage_stand", "Idle"], ["lf_civilian_cage_wait", "Idle"]]
const CAGE_SLOTS := [Vector3(-0.72, 0, 0.1), Vector3(0.05, 0, -0.45), Vector3(0.74, 0, 0.18)]
const GATHER_SLOTS := [Vector3(-1.25, 0, 4.35), Vector3(0.0, 0, 4.95), Vector3(1.2, 0, 4.4)]
const SQUAD_FORMATION := [Vector3(0, 0, 0), Vector3(-0.85, 0, -1.25), Vector3(0.85, 0, -1.25)]
const LIVE_RANGE := 70.0
## Where the squad stops short of a glade sub-target (server node = the cage / guardian /
## device spot itself): door front, fighting distance, device front.
const STAND_OFF := {"cage":2.0, "guardian":5.2, "key":1.9, "boss":12.5}
## The mare keeps back from the boss: she waits at the arena gap, behind the squad.
const HORSE_BOSS_STAND_OFF := 21.0
## Orthographic size thresholds for LOD0 / LOD1 (× rig.lod_scale); beyond = LOD2.
const LOD_ZOOM := [34.0, 72.0]
const BOSS_LOD_SCALE := 1.4
const BOSS_FIGHT_DISTANCE := 12.5
const ARENA_FACING_DEG := 72.9         # authored fallback (atlas v2 entranceYawDeg); see arena_facing_deg()
const SUPPLY_ITEMS := {"food":["supply_bread", "supply_sacks"], "wood":["supply_crate_closed"], "stone":["supply_crate_open"],
	"iron":["supply_arrows", "supply_bandages"], "coins":["supply_coins", "supply_chest"]}

var game: Node
var root: Node3D
var props_parent: Node3D
var rigs: Dictionary = {}
var motion: Dictionary = {}
var routes: Dictionary = {}
var choreo: Dictionary = {}
var site_props: Dictionary = {}
var adv: Dictionary = {}
var first_state := true
var markers: Array[Dictionary] = []
var tags: Array[Dictionary] = []
var beacon: Node3D
var beacon_target := ""
var ribbon: MultiMeshInstance3D
var ribbon_signature := ""
var preview: MultiMeshInstance3D
var preview_signature := ""
var preview_target := ""
var telegraphs: Telegraphs
var intro_horse: Dictionary = {}
var variants: Dictionary = {}
var props_index: Dictionary = {}
var last_battle: Dictionary = {}
var dead_guardians: Dictionary = {}
var arrival_until: Dictionary = {}
var lod_zoom := -1.0
var horse_wait_ticks := 0
var horse_was_walking := false
var horse_transition_until := 0
var horse_afraid: Dictionary = {}
var guardian_alerted: Dictionary = {}   # (1023, kept for saved QA hooks; the menace replaces it)
## Root-yaw turns in progress: id -> {from, root, length, clip}.
var turns: Dictionary = {}
## Mechanism presentation per site: {signature, progress, solved, pose (stable), live: {...}}.
var mechanisms: Dictionary = {}
var mechanism_symbols: Dictionary = {}
var boss_awake_ms := -1.0
var boss_scale := 1.52
var exit_paths: Dictionary = {}
var supplies_signature := ""

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "ForestActors"
	var parsed: Variant = game.content.read_json(ASSETS + "humans/captive_variants.json")
	variants = parsed if parsed is Dictionary else {}
	parsed = game.content.read_json(ASSETS + "props/site_props.json")
	props_index = parsed if parsed is Dictionary else {}
	boss_scale = float(Rig.meta_for(BOSS_GLB).get("recommendedScale", 1.52))

func on_stage_changed() -> void:
	for id in rigs.keys():
		var rig: Node = rigs[id]
		if is_instance_valid(rig):
			rig.queue_free()
	rigs.clear()
	motion.clear()
	site_props.clear()
	choreo.clear()
	turns.clear()
	mechanisms.clear()
	exit_paths.clear()
	supplies_signature = ""
	if is_instance_valid(beacon):
		beacon.queue_free()
	if is_instance_valid(ribbon):
		ribbon.queue_free()
	if is_instance_valid(preview):
		preview.queue_free()
	preview = null
	preview_signature = ""
	if telegraphs != null and is_instance_valid(telegraphs):
		telegraphs.queue_free()
	beacon = null
	ribbon = null
	telegraphs = null
	ribbon_signature = ""
	root = null
	props_parent = null

func ensure_roots() -> bool:
	var wanted: Node3D = game.actors_root()
	if wanted == null:
		return false
	if wanted != root:
		on_stage_changed()
		root = wanted
		props_parent = game.props_root()
		telegraphs = Telegraphs.new()
		telegraphs.scale_factor = boss_scale
		telegraphs.setup(game)
		telegraphs.set_meta("no_canopy_fade", true)
		telegraphs.set_meta("fog_exempt", true)
		root.add_child(telegraphs)
	return true

# ------------------------------------------------------------------ state transitions
func on_state(value: Dictionary, previous: Dictionary) -> void:
	adv = value
	if value.is_empty():
		return
	if first_state or previous.is_empty():
		first_state = false
		last_battle = game.client.battle()
		return
	for poi in value.get("pois", []):
		var id := String(poi.get("id", ""))
		var before := poi_from(previous, id)
		if before.is_empty():
			continue
		if String(before.get("cagePose", "closed")) == "closed" and String(poi.get("cagePose", "closed")) == "open" and not choreo.has("cage:" + id):
			on_cage_opened(id)
		var was := String(before.get("guardian", {}).get("state", "alive"))
		var now := String(poi.get("guardian", {}).get("state", "alive"))
		if was != "defeated" and now == "defeated":
			start_guardian_death(id)
	var walk_before: Variant = previous.get("escort")
	var walk_now: Variant = value.get("escort")
	if walk_before is Dictionary and String(walk_before.get("state", "")) == "walking":
		if (walk_now is Dictionary and String(walk_now.get("state", "")) == "home") or walk_now == null:
			on_escort_arrived(String(walk_before.get("siteId", "")))
	var fight: Dictionary = game.client.battle()
	if not last_battle.is_empty() and String(last_battle.get("outcome", "pending")) == "pending":
		var finished: bool = fight.is_empty() or String(fight.get("reportId", "")) != String(last_battle.get("reportId", "")) or String(fight.get("outcome", "pending")) != "pending"
		if finished:
			var shown: Dictionary = fight if not fight.is_empty() and String(fight.get("reportId", "")) == String(last_battle.get("reportId", "")) else last_battle
			if String(shown.get("outcome", "pending")) != "pending":
				# DRENOVAR's own battle popup already presents reports listed in state.reports
				# (outcome, losses, ordinary loot): do not stack a second window over it.
				var listed := false
				for report in game.main.state.get("reports", []):
					if String(report.get("id", "")) == String(shown.get("reportId", "")):
						listed = true
				if listed:
					var site_id := String(shown.get("siteId", ""))
					if String(shown.get("outcome", "")) == "victory" and game.content.site(site_id).size() > 0:
						game.hud.toast(String(game.content.task(site_id, "defeat_guardian").get("title", "")), "reward", 5.0)
				else:
					game.panels.open_battle_result(shown)
	last_battle = fight

func poi_from(state: Dictionary, id: String) -> Dictionary:
	for entry in state.get("pois", []):
		if String(entry.get("id", "")) == id:
			return entry
	return {}

# ------------------------------------------------------------------ rigs
func rig(id: String, path: String, fallback := "", scale := 1.0, parent: Node3D = null) -> Rig:
	var existing: Rig = rigs.get(id)
	if existing != null and is_instance_valid(existing):
		return existing
	var created := Rig.new()
	created.model_scale = scale
	created.setup(id, path, fallback)
	created.marker.connect(on_marker)
	created.clip_finished.connect(on_clip_finished)
	created.ready_to_show.connect(on_rig_ready)
	(parent if parent != null else root).add_child(created)
	created.visible = false
	rigs[id] = created
	return created

func drop(id: String) -> void:
	var existing: Rig = rigs.get(id)
	if existing != null and is_instance_valid(existing):
		existing.queue_free()
	rigs.erase(id)
	motion.erase(id)
	turns.erase(id)

## Moves an actor towards a computed ground pose, measures its real speed for locomotion.
## keep_y: the target height is used as is (cage floor, plate top) instead of the terrain.
func place(id: String, actor: Rig, target: Vector3, yaw: float, delta: float, snap := false, keep_y := false) -> float:
	var state: Dictionary = motion.get(id, {})
	var ground: Vector3 = target if keep_y else game.ground(target.x, target.z)
	if state.is_empty() or snap or state.position.distance_to(ground) > 8.0:
		state = {"position":ground, "yaw":yaw, "speed":0.0}
	else:
		var previous: Vector3 = state.position
		var next := previous.lerp(ground, 1.0 - exp(-14.0 * delta))
		var moved := Vector2(next.x - previous.x, next.z - previous.z).length()
		var measured := moved / maxf(delta, 0.0001)
		state.speed = lerpf(float(state.speed), measured, 1.0 - exp(-6.0 * delta))
		state.position = next
		if not turns.has(id):
			state.yaw = PathMotion.turn_towards(float(state.yaw), yaw, 7.0, delta)
	if snap and turns.has(id):
		turns.erase(id)
	motion[id] = state
	actor.position = state.position
	actor.rotation.y = state.yaw
	return float(state.speed)

func visible_in_view(p: Vector3) -> bool:
	var stage: Node3D = game.stage
	if not is_instance_valid(stage):
		return false
	var camera: Camera3D = stage.camera
	var focus: Vector3 = stage.camera_target
	if Vector2(p.x - focus.x, p.z - focus.z).length() > maxf(LIVE_RANGE, float(stage.camera_zoom) * 0.95):
		return false
	return camera.is_position_in_frustum(p + Vector3.UP)

func show_actor(actor: Rig, p: Vector3, allow := true) -> bool:
	var shown: bool = allow and actor.is_ready() and visible_in_view(p) and game.fog_clear(p)
	actor.set_active(shown)
	if not shown and actor.load_state == "loading":
		actor.process_mode = Node.PROCESS_MODE_INHERIT
	return shown

func now_ms() -> float:
	return game.client.server_now()

func on_rig_ready(actor: Node3D) -> void:
	var zoom: float = float(game.stage.camera_zoom) if is_instance_valid(game.stage) else 68.0
	(actor as Rig).set_lod(lod_for(zoom, (actor as Rig).lod_scale), true)

# ------------------------------------------------------------------ per frame
## iPhone smoothness: once per session, as soon as the forest is up, every adventure model (with its painted
## look) and the reward FX are instanced for a few frames far below the terrain, so their pipelines are built
## before play: no pipeline compilation when an actor, a cage opening or the boss first appears
## (qa_forest_perf --segments reports the RENDERING_INFO_PIPELINE_COMPILATIONS_* deltas per moment).
static var pipelines_warmed := false

const WARM_PER_FRAME := 4
const WARM_BUDGET_USEC := 4000

func warm_pipelines() -> void:
	var world_node: Variant = game.get("world")
	if world_node is Node and world_node.get("setup_stage") != null:
		world_node.set("setup_stage", "pipeline warm-up")
	var paths: Array = [HORSE_GLB, BOSS_GLB, SUPPLIES_GLB]
	paths.append_array(SQUAD_GLBS)
	for file in CAGE_FILES.values():
		var path := ASSETS + "props/%s.glb" % file
		if not paths.has(path):
			paths.append(path)
	for dir in ["props/", "humans/"]:
		for file in ResourceLoader.list_directory(ASSETS + dir):
			if file.ends_with(".glb") and (file.begins_with("lf_mechanism_") or file.begins_with("lf_artifact_") or file.begins_with("lf_civilian_")):
				paths.append(ASSETS + dir + file)
	for site in game.content.campaign.get("sites", []):
		var guardian: Variant = site.get("guardian")
		if guardian is Dictionary:
			var g_path: String = guardian_paths(guardian)[0]
			if not g_path.is_empty() and not paths.has(g_path):
				paths.append(g_path)
	var ids: Array = []
	# 1022: the layer arrives while the city is interactive: a few rigs per frame (their models load one
	# at a time, ActorRig.MAX_PARALLEL_LOADS) and, below, a few shown per frame so the pipelines compile
	# over several frames instead of in one.
	# 1023: by time, not count (WARM_PER_FRAME at most): a frame stops adding rigs after WARM_BUDGET_USEC.
	var slice := Time.get_ticks_usec()
	var in_slice := 0
	for i in paths.size():
		var id := "__warm_%d" % i
		var actor := rig(id, String(paths[i]))
		actor.position = Vector3(float(i % 8) * 4.0, -400.0, float(i / 8) * 4.0)
		ids.append(id)
		in_slice += 1
		if in_slice >= WARM_PER_FRAME or Time.get_ticks_usec() - slice > WARM_BUDGET_USEC:
			await game.get_tree().process_frame
			slice = Time.get_ticks_usec()
			in_slice = 0
	var fx: Variant = game.get("fx")
	if fx != null and fx.has_method("ensure_world") and fx.ensure_world():
		fx.burst_world(Vector3(0, -400, -8))
		fx.glow_world("__warm", Vector3(0, -400, -12))
	for attempt in 900:
		var loading := false
		for id in ids:
			var actor: Rig = rigs.get(id)
			if actor != null and is_instance_valid(actor) and actor.load_state == "loading":
				loading = true
		if not loading:
			break
		await game.get_tree().process_frame
	slice = Time.get_ticks_usec()
	in_slice = 0
	for i in ids.size():
		var actor: Rig = rigs.get(ids[i])
		if actor != null and is_instance_valid(actor):
			actor.visible = true
		in_slice += 1
		if in_slice >= WARM_PER_FRAME or Time.get_ticks_usec() - slice > WARM_BUDGET_USEC:
			await game.get_tree().process_frame
			slice = Time.get_ticks_usec()
			in_slice = 0
	for frame in 3:
		await game.get_tree().process_frame
	for id in ids:
		drop(id)
	if fx != null and fx.has_method("glow_world"):
		fx.glow_world("__warm", Vector3.INF)
	if world_node is Node and is_instance_valid(world_node) and world_node.get("setup_stage") != null:
		world_node.set("setup_stage", "post-setup (warmed)")

func tick(delta: float) -> void:
	# A story scene (src/story) plays its own cast at the sites: the adventure's actors step aside.
	if not game.client.unlocked() or game.story_presenting():
		if root != null and is_instance_valid(root):
			for id in rigs:
				if is_instance_valid(rigs[id]):
					rigs[id].set_active(false)
		markers.clear()
		tags.clear()
		if is_instance_valid(beacon):
			beacon.hide()
		if is_instance_valid(ribbon):
			ribbon.hide()
		return
	if not ensure_roots():
		return
	if not pipelines_warmed:
		pipelines_warmed = true
		warm_pipelines()
	adv = game.client.adv
	markers.clear()
	tags.clear()
	var now := now_ms()
	update_lod()
	update_horse(now, delta)
	update_squad(now, delta)
	update_sites(now, delta)
	update_boss(now, delta)
	update_supplies()
	update_beacon(delta)
	update_ribbon()
	update_preview()
	update_battle_hud(now)
	update_fight_fx(now)
	run_choreography(delta)

static func lod_for(zoom: float, scale := 1.0) -> int:
	var z := zoom / maxf(scale, 0.1)
	return 0 if z <= LOD_ZOOM[0] else (1 if z <= LOD_ZOOM[1] else 2)

func update_lod() -> void:
	# Orthographic size decides the LOD (hysteresis 3 units); new rigs pick it up when ready.
	var zoom: float = float(game.stage.camera_zoom)
	if lod_zoom < 0.0 or absf(zoom - lod_zoom) >= 3.0:
		lod_zoom = zoom
	for id in rigs:
		var actor: Rig = rigs[id]
		if is_instance_valid(actor) and actor.is_ready():
			var level := lod_for(lod_zoom, actor.lod_scale)
			if actor.lod_level != level:
				actor.set_lod(level)

func squad_member_count() -> int:
	var squad: Dictionary = game.client.squad()
	if game.total_units(squad.get("units", {})) <= 0:
		if String(predicted.get("action", "")) == "form_squad":
			return clampi(game.total_units(predicted.get("fields", {}).get("units", {})), 0, 3)
		return 0
	return clampi(int(squad.get("members", 3)), 1, 3)

# ------------------------------------------------------------------ 1024: optimistic presentation
## Build 1024 «кнопки ждут сервер»: a press starts its animation at once (forest_game.request_action →
## predict), the server's answer takes over (settle_prediction), a refusal rolls back (the stable pose
## from the unchanged state returns, place() eases them there). Nothing here decides an outcome or
## grants anything: the walk follows the drawn trail to the target the button names, the charge, the
## soldier's unlock / inspect gesture are presentation; positions, fights, rewards stay the server's.
const PREDICT_TTL_MS := 15000
const HANDOFF_MS := 2500.0
var predicted: Dictionary = {}
var handoffs: Dictionary = {}
var walk_speed_mps := 2.4
## Per-frame cost probe (QA).
var predict_usec := 0

func predict(action: String, fields: Dictionary) -> void:
	var started := Time.get_ticks_usec()
	var squad: Dictionary = game.client.squad()
	var node := String(squad.get("node", ""))
	predicted = {"action": action, "fields": fields, "at": Time.get_ticks_msec(), "server_at": now_ms(), "node": node}
	match action:
		"move", "escort_start":
			var target := String(fields.get("targetId", "lf_home_reception" if action == "escort_start" else ""))
			if not (squad.get("move") is Dictionary) and not target.is_empty() and squad_member_count() > 0:
				var path := predicted_path(node, target)
				if path.size() >= 2:
					predicted.move = {"path": path, "targetId": target, "departAt": now_ms(), "predicted": true}
					# The points already lie on the drawn trail: no visual_path() remap (≈ 0.1 ms per metre
					# of trail on the press frame).
					predicted.route = PathMotion.build(path)
					if float(predicted.route.total) - float(STAND_OFF.get(target_kind(target), 0.0)) < 0.6:
						# Already there (a step to the guardian from the guard stance): a nod instead of a walk.
						predicted.erase("move")
						predicted.erase("route")
						predicted.gesture = ["lf_soldier_salute", "lf_soldier_idle", "Idle"]
		"engage_guardian":
			engage_pending_for = String(fields.get("siteId", ""))
			menace.erase(engage_pending_for)
		"attempt_task":
			var site_id := String(fields.get("siteId", ""))
			match String(fields.get("taskId", "")):
				"unlock_cage":
					if not choreo.has("cage:" + site_id):
						on_cage_opened(site_id)
						choreo["cage:" + site_id].confirmed = false
				"discover", "recover_artifact":
					predicted.gesture = ["lf_soldier_help", "lf_soldier_idle", "Idle"]
				_:
					predicted.gesture = ["lf_soldier_salute", "lf_soldier_idle", "Idle"]
		"discover_horse":
			predicted.gesture = ["lf_soldier_salute", "lf_soldier_idle", "Idle"]
			var horse: Rig = rigs.get("horse")
			if horse != null and horse.is_ready():
				horse.play(["lf_horse_call", "lf_horse_idle", "Idle"], 0.15, true)
				horse_transition_until = Time.get_ticks_msec() + 1400
	if predicted.has("gesture"):
		var leader: Rig = rigs.get("squad_0")
		if leader != null and leader.is_ready():
			leader.play(predicted.gesture, 0.15, true)
	predict_usec = Time.get_ticks_usec() - started

## The server answered: hand the predicted walk over (no step back) or roll back a refusal.
func settle_prediction(ok: bool) -> void:
	var action := String(predicted.get("action", ""))
	if ok and predicted.has("move"):
		var squad: Dictionary = game.client.squad()
		var move: Variant = squad.get("move")
		if move is Dictionary:
			var pred_d := predicted_distance(predicted.move, now_ms())
			var key := "%s|%s|%s" % [str(move.get("departAt", 0)), str(move.get("arriveAt", 0)), str(move.get("targetId", ""))]
			var route := route_for(key, move.get("path", []))
			var server_d := PathMotion.travelled(move, route, now_ms())
			if float(route.total) > 0.1 and move.get("arriveAt") != null:
				walk_speed_mps = clampf(float(route.total) / maxf(0.1, (float(move.arriveAt) - float(move.departAt)) / 1000.0), 0.6, 6.0)
			if pred_d > server_d:
				handoffs["%s|%s" % [str(move.get("departAt", 0)), str(move.get("targetId", ""))]] = {"lead": minf(pred_d - server_d, 4.0), "at": Time.get_ticks_msec()}
	if not ok:
		if action == "engage_guardian":
			engage_pending_for = ""
		if action == "attempt_task" and String(predicted.get("fields", {}).get("taskId", "")) == "unlock_cage":
			var beat_id := "cage:" + String(predicted.fields.get("siteId", ""))
			if choreo.has(beat_id) and not bool(choreo[beat_id].get("confirmed", true)):
				choreo.erase(beat_id)
				choreo.erase("key:" + String(predicted.fields.get("siteId", "")))
				var soldier: Rig = rigs.get("squad_0")
				if soldier != null:
					soldier.play(["lf_soldier_idle", "Idle"], 0.3)
	else:
		if action == "attempt_task" and String(predicted.get("fields", {}).get("taskId", "")) == "unlock_cage":
			var beat_id := "cage:" + String(predicted.fields.get("siteId", ""))
			if choreo.has(beat_id):
				choreo[beat_id].confirmed = true
	if action != "engage_guardian" or not ok:
		engage_pending_for = "" if not ok else engage_pending_for
	predicted = {}
	for key in handoffs.keys():
		if Time.get_ticks_msec() - int(handoffs[key].at) > HANDOFF_MS * 2.0:
			handoffs.erase(key)

## The drawn trail (world trail_path) from the squad's node to the target as server-style points.
func predicted_path(from_node: String, target: String) -> Array:
	var value: Variant = game.world_call("trail_path", [from_node, target])
	var points: Array = []
	var start := squad_focus()
	if start != Vector3.INF:
		points.append({"x": start.x, "z": start.z})
	if value is PackedVector3Array and value.size() >= 2:
		for p: Vector3 in value:
			if points.is_empty() or Vector2(p.x - float(points.back().x), p.z - float(points.back().z)).length() > 0.3:
				points.append({"x": p.x, "z": p.z})
	else:
		var b: Vector3 = game.target_position(target)
		if b == Vector3.INF:
			return []
		points.append({"x": b.x, "z": b.z})
	return points

## Metres walked by a predicted move: a start that ramps up over the first PREDICT_RAMP_S (the first
## step), then the squad's walking speed.
const PREDICT_RAMP_S := 0.4
func predicted_distance(move: Dictionary, now: float) -> float:
	var t := maxf(0.0, (now - float(move.get("departAt", now))) / 1000.0)
	return walk_speed_mps * (t * t * 0.5 / PREDICT_RAMP_S if t < PREDICT_RAMP_S else t - PREDICT_RAMP_S * 0.5)

## Pose of a squad member on the predicted walk (or {} when none applies).
func predicted_pose(index: int, now: float) -> Dictionary:
	if predicted.is_empty() or Time.get_ticks_msec() - int(predicted.at) > PREDICT_TTL_MS:
		return {}
	var squad: Dictionary = game.client.squad()
	if predicted.has("move") and not (squad.get("move") is Dictionary):
		var move: Dictionary = predicted.move
		var route: Dictionary = predicted.get("route", {})
		if route.is_empty():
			return {}
		var d := minf(float(route.total) - float(STAND_OFF.get(target_kind(String(move.targetId)), 0.0)), predicted_distance(move, now))
		var behind := maxf(0.0, d - float(index) * 1.6)
		var sample := PathMotion.sample(route, behind)
		var tangent: Vector3 = sample.tangent
		var side := Vector3(tangent.z, 0, -tangent.x)
		var t := (now - float(move.departAt)) / 1000.0
		return {"position": sample.position + side * SQUAD_FORMATION[index].x * 0.8, "yaw": PathMotion.yaw_of(tangent), "moving": true,
			"speed": maxf(0.6, walk_speed_mps * minf(1.0, t / PREDICT_RAMP_S)), "predicted": true}
	if String(predicted.action) == "engage_guardian" and game.client.battle().is_empty():
		var site_id := String(predicted.fields.get("siteId", ""))
		var fake := {"siteId": site_id, "startedAt": float(predicted.server_at), "endsAt": float(predicted.server_at) + 60000.0, "timeline": []}
		var pose := battle_member_pose(index, fake, now)
		pose.erase("clip")
		return pose
	return {}



## Presentation route of a server move: its path mapped onto the drawn, meandered trail
## (world.visual_path) — same arc-length fraction and timing as the server move.
func route_for(key: String, path: Array) -> Dictionary:
	if not routes.has(key):
		routes[key] = PathMotion.build(visual_path(path))
		if routes.size() > 24:
			routes.erase(routes.keys()[0])
	return routes[key]

func visual_path(path: Array) -> Array:
	var value: Variant = game.world_call("visual_path", [path])
	return value if value is Array and not (value as Array).is_empty() else path

## Sub-target kind of a CONTRACT targetId («lf_site_01:cage» → cage, lf_key_NN → key).
static func target_kind(target_id: String) -> String:
	if target_id.begins_with("lf_key_"):
		return "key"
	if target_id == "lf_boss_ancient_maw":
		return "boss"
	if target_id.contains(":"):
		return target_id.get_slice(":", 1)
	return ""

func move_sample(move: Dictionary, now: float, back := 0.0, stand_off := -1.0, who := "squad") -> Dictionary:
	var key := "%s|%s|%s" % [str(move.get("departAt", 0)), str(move.get("arriveAt", 0)), str(move.get("targetId", ""))]
	var route := route_for(key, move.get("path", []))
	var distance := PathMotion.travelled(move, route, now)
	# 1024: the optimistic walk started before the server answered; the authoritative walk takes over
	# without stepping back — the lead the prediction had fades over HANDOFF_MS (a slightly slower pace).
	var handoff_key := "%s|%s" % [str(move.get("departAt", 0)), str(move.get("targetId", ""))]
	if handoffs.has(handoff_key):
		var handoff: Dictionary = handoffs[handoff_key]
		var fade := 1.0 - smoothstep(0.0, HANDOFF_MS, float(Time.get_ticks_msec() - int(handoff.at)))
		distance = minf(float(route.total), distance + float(handoff.lead) * fade)
	# Presentation: the squad stops short of a cage / guardian / device / boss spot (the server
	# node is the spot itself); the ribbon and arrival timing are unchanged.
	if stand_off < 0.0:
		stand_off = float(STAND_OFF.get(target_kind(String(move.get("targetId", ""))), 0.0))
	var limit := float(route.total) - stand_off
	var shown := minf(distance, maxf(limit, 0.0))
	var sample := PathMotion.sample(route, maxf(0.0, shown - back))
	var shift := origin_shift(move, route, maxf(0.0, shown - back), who)
	if shift != Vector3.ZERO:
		sample.position = (sample.position as Vector3) + shift
	sample.arrived = now >= float(move.get("arriveAt", 0)) or distance >= limit
	sample.speed = 0.0 if sample.arrived else PathMotion.speed(move, route)
	sample.route = route
	sample.distance = distance
	sample.behind = shown - back
	return sample

# ------------------------------------------------------------------ root-yaw turns
## Starts a turn clip whose node yaw follows rootYawDeg * smoothstep(t / length) (meta).
func start_turn(id: String, actor: Rig, delta_yaw: float, left_clip: String, right_clip: String) -> bool:
	if turns.has(id) or not actor.is_ready():
		return false
	var clip := left_clip if delta_yaw > 0.0 else right_clip
	var spec := actor.clip_meta(clip)
	if spec.is_empty() or not actor.has_clip([clip]):
		return false
	var state: Dictionary = motion.get(id, {})
	if state.is_empty():
		return false
	turns[id] = {"from":float(state.yaw), "root":deg_to_rad(float(spec.get("rootYawDeg", 0.0))), "length":float(spec.get("seconds", actor.clip_length([clip]))), "clip":clip}
	actor.play([clip], 0.15, true)
	return true

## Applies the turn curve; returns true while a turn is running.
func run_turn(id: String, actor: Rig) -> bool:
	var turn: Dictionary = turns.get(id, {})
	if turn.is_empty():
		return false
	var state: Dictionary = motion.get(id, {})
	var t := actor.clip_time() if actor.current_id == String(turn.clip) else float(turn.length)
	var f := smoothstep(0.0, 1.0, clampf(t / maxf(float(turn.length), 0.01), 0.0, 1.0))
	var yaw := float(turn.from) + float(turn.root) * f
	if not state.is_empty():
		state.yaw = yaw
	actor.rotation.y = yaw
	if t >= float(turn.length) - 0.001 or actor.current_id != String(turn.clip):
		if not state.is_empty():
			state.yaw = float(turn.from) + float(turn.root)
		turns.erase(id)
		return false
	return true

# ------------------------------------------------------------------ horse (guide)
func update_horse(now: float, delta: float) -> void:
	var horse: Dictionary = adv.get("horse", {})
	var actor := rig("horse", HORSE_GLB)
	actor.set_meta("occluder_height", 2.4)
	if not bool(horse.get("visible", false)) and intro_horse.is_empty():
		actor.set_active(false)
		return
	var target: Vector3 = game.target_position(String(horse.get("node", "lf_horse_origin")))
	var yaw := float(motion.get("horse", {}).get("yaw", forest_heading()))
	var moving := false
	var move: Variant = horse.get("move")
	if not intro_horse.is_empty():
		intro_horse.elapsed = float(intro_horse.get("elapsed", 0.0)) + delta
		var elapsed := float(intro_horse.elapsed)
		var walk_seconds := float(intro_horse.get("walk", 2.4))
		var from: Vector3 = intro_horse.from
		var to: Vector3 = intro_horse.to
		var f := clampf(elapsed / walk_seconds, 0.0, 1.0)
		target = from.lerp(to, f)
		yaw = PathMotion.yaw_of(to - from)
		moving = f < 1.0
		place("horse", actor, target, yaw, delta, elapsed < 0.05)
		if moving:
			actor.locomote(from.distance_to(to) / walk_seconds, HORSE_CLIPS)
		elif elapsed < walk_seconds + 0.8:
			actor.play(["lf_horse_stop", "lf_horse_idle", "Idle"], 0.2)
		else:
			actor.play(["lf_horse_look_back", "lf_horse_idle", "Idle"], 0.3)
		# The entrance corridor is opening right now: the mare walks out of the mist.
		actor.set_active(actor.is_ready() and visible_in_view(actor.position))
		markers.append({"position":actor.position + Vector3.UP * 1.6, "kind":"horse", "id":"horse"})
		return
	var speed_now := 0.0
	if String(horse.get("node", "")) == "lf_boss_ancient_maw":
		target = boss_gap_point(HORSE_BOSS_STAND_OFF, -2.5)
		yaw = PathMotion.yaw_of(game.target_position("lf_boss_ancient_maw") - target)
	else:
		target = horse_rest_point(String(horse.get("node", "")), target)
	if move is Dictionary and not (move.get("path", []) as Array).is_empty():
		var boss_move := String(move.get("targetId", "")) == "lf_boss_ancient_maw"
		var sample := move_sample(move, now, 0.0, HORSE_BOSS_STAND_OFF if boss_move else -1.0, "horse")
		target = sample.position
		yaw = PathMotion.yaw_of(sample.tangent)
		moving = not sample.arrived
		speed_now = float(sample.speed)
		if not boss_move:
			# Final 4 m: she steers off the path end to her own spot beside the squad.
			var rest := horse_rest_point(String(move.get("targetId", "")), Vector3.INF)
			if rest != Vector3.INF:
				var left := float(sample.route.total) - float(sample.distance)
				var w := smoothstep(4.0, 0.0, left)
				if w > 0.0:
					var blended: Vector3 = (sample.position as Vector3).lerp(rest, w)
					if blended.distance_to(target) > 0.01:
						yaw = PathMotion.yaw_of(blended - target) if moving else yaw
					target = blended
	# 1024: a menacing creature nearby frightens her: an alarmed start (alert), then she backs off
	# ~2.5 m away from it, turned away, and stays alert, looking back at it.
	var fear := "" if moving else menace_near(actor.position, 24.0)
	if not fear.is_empty():
		var creature: Rig = rigs.get("guardian_" + fear)
		var away := Vector3(actor.position.x - creature.position.x, 0, actor.position.z - creature.position.z)
		away = away.normalized() if away.length_squared() > 0.01 else Vector3.BACK
		if not horse_afraid.has(fear):
			horse_afraid[fear] = {"at": Time.get_ticks_msec(), "from": target}
			actor.play(["lf_horse_alert", "lf_horse_idle", "Idle"], 0.12, true)
			horse_transition_until = Time.get_ticks_msec() + 1100
			game.horse_feared.emit(fear)
		var startled := Time.get_ticks_msec() - int(horse_afraid[fear].at) < 900
		target = (horse_afraid[fear].from as Vector3) + (Vector3.ZERO if startled else away * 2.6)
		yaw = float(motion.get("horse", {}).get("yaw", yaw)) if startled else PathMotion.yaw_of(away)
	else:
		horse_afraid.clear()
	var measured := place("horse", actor, target, yaw, delta)
	var speed := speed_now if moving else measured
	var mood := "alert" if not fear.is_empty() else String(horse.get("mood", "calm"))
	var walking := moving or measured > 0.35
	if walking:
		turns.erase("horse")
	# Authored start/stop clips carry the weight shift between standing and walking.
	if walking != horse_was_walking:
		horse_was_walking = walking
		if actor.play(["lf_horse_start"] if walking else ["lf_horse_stop"], 0.15, true):
			horse_transition_until = Time.get_ticks_msec() + int(1000.0 * actor.clip_length(["lf_horse_start"] if walking else ["lf_horse_stop"]) * 0.85)
	if run_turn("horse", actor):
		pass
	elif Time.get_ticks_msec() < horse_transition_until:
		pass
	elif walking:
		actor.locomote(speed, HORSE_CLIPS)
		horse_wait_ticks = 0
	else:
		var squad_pos: Vector3 = squad_focus()
		var waiting := mood == "waiting" or (squad_pos != Vector3.INF and squad_pos.distance_to(actor.position) > 7.0)
		# Leading: once the squad is with her she turns towards the next destination (turn
		# clips, ±90° root yaw); while waiting she looks back over her shoulder and calls.
		var facing := horse_facing(actor.position)
		var state: Dictionary = motion.get("horse", {})
		var diff := angle_difference(float(state.get("yaw", 0.0)), facing) if facing != INF else 0.0
		if not waiting and mood != "alert" and absf(diff) > deg_to_rad(65.0) and start_turn("horse", actor, diff, "lf_horse_turn_left", "lf_horse_turn_right"):
			pass
		elif mood == "alert":
			# Alert, glancing back at what frightens her now and then.
			var glance := fmod((Time.get_ticks_msec() - int(horse_afraid.values()[0].at if not horse_afraid.is_empty() else 0)) / 1000.0, 5.0)
			actor.play(["lf_horse_look_back", "lf_horse_alert", "Idle"] if glance > 3.6 else ["lf_horse_alert", "lf_horse_idle", "Idle"], 0.25)
		elif waiting:
			if horse_wait_ticks == 0:
				horse_wait_ticks = Time.get_ticks_msec()
			var phase := fmod((Time.get_ticks_msec() - horse_wait_ticks) / 1000.0, 7.0)
			actor.play(["lf_horse_look_back", "lf_horse_idle", "Idle"] if phase < 1.8 else (["lf_horse_call", "lf_horse_idle", "Idle"] if phase > 5.0 and phase < 7.0 and mood == "waiting" else ["lf_horse_idle", "Idle"]), 0.3)
		else:
			horse_wait_ticks = 0
			actor.play(["lf_horse_idle", "Idle"], 0.35)
	if show_actor(actor, actor.position):
		markers.append({"position":actor.position + Vector3.UP * 1.6, "kind":"horse", "id":"horse"})
		if plates_for_actors():
			tags.append({"position":actor.position + Vector3.UP * 3.0, "text":game.content.text("hud.horse"), "kind":"horse"})
	game.pin("lf_horse", actor.position, 14.0)

## Where the mare waits at a glade (site centre / key / sub-targets): beside the squad, back
## towards the approach, on the side away from the mechanism; `fallback` elsewhere.
func horse_rest_point(node: String, fallback: Vector3) -> Vector3:
	if node == "lf_horse_origin":
		var spots := horse_origin_spots()
		return spots.get("horse", fallback) if not spots.is_empty() else fallback
	var site_id := node.get_slice(":", 0).replace("lf_key_", "lf_site_")
	if not site_id.begins_with("lf_site_"):
		return fallback
	var anchor: Dictionary = game.site_anchor(site_id)
	if anchor.is_empty() or not anchor.get("center") is Vector3:
		return fallback
	var center: Vector3 = anchor.center
	var approach: Vector3 = anchor.get("approach", center + Vector3(0, 0, 7))
	var back := Vector3(approach.x - center.x, 0, approach.z - center.z)
	back = back.normalized() if back.length_squared() > 0.01 else Vector3.BACK
	var right := Vector3(back.z, 0, -back.x)
	var art: Vector3 = anchor.get("artifact", center)
	var side := -1.0 if (art - center).dot(right) > 0.0 else 1.0
	# Clear of the cage door / gathering spot (cage + 4–5 m towards the approach) and of the device.
	var p := center + back * 5.6 + right * side * 3.8
	return game.ground(p.x, p.z)

## The arena gap's facing (deg): the world's atlas entranceYawDeg, the authored value offline.
func arena_facing_deg() -> float:
	var value: Variant = game.world_call("arena_entrance_yaw_deg")
	return float(value) if value != null else ARENA_FACING_DEG

## Point on the arena's entrance axis `distance` m from the centre (side offset in m).
func boss_gap_point(distance: float, side := 0.0) -> Vector3:
	var arena: Vector3 = game.target_position("lf_boss_ancient_maw")
	var axis := Vector3(sin(deg_to_rad(arena_facing_deg())), 0, cos(deg_to_rad(arena_facing_deg())))
	var p := arena + axis * distance + Vector3(axis.z, 0, -axis.x) * side
	return game.ground(p.x, p.z)

## Yaw towards the guide's next destination (INF when unknown or too close to matter).
func horse_facing(from: Vector3) -> float:
	if beacon_target.is_empty() or beacon_target.begins_with("lf_horse"):
		return INF
	var p: Vector3 = game.target_position(beacon_target)
	if p == Vector3.INF or Vector2(p.x - from.x, p.z - from.z).length() < 4.0:
		return INF
	return PathMotion.yaw_of(p - from)

func forest_heading() -> float:
	var origin: Vector3 = game.target_position("lf_horse_origin")
	var first: Vector3 = game.target_position("lf_site_01")
	if origin == Vector3.INF or first == Vector3.INF:
		return PI
	return PathMotion.yaw_of(first - origin)

# ------------------------------------------------------------------ 1024: the mare's spot by the entrance
## Build 1024 «коня не видно за стеной»: lf_horse_origin (server node) lies in the 10 m strip of known
## ground between the city wall and the forest; with a high wall, a tower or a gate tower between it
## and the fixed city camera (azimuth 45°, 38° down) the mare stood hidden behind masonry for the whole
## intro (the owner saw only her plate over a tower). The presentation spot is the nearest point of
## known ground (town square ±55 m or the entrance corridor), on the forest side, that no wall /
## tower / gate / building box hides from the camera; the squad's spot the same, beside her.
## Presentation only: the server node and every rule stay at lf_horse_origin; moves that start or end
## there blend onto the spots over their first / last ORIGIN_BLEND metres (move_sample).
const ORIGIN_SEARCH := 10.0
const ORIGIN_BLEND := 6.0
var origin_spots: Dictionary = {}
var origin_key := ""
var origin_at := 0
const ORIGIN_RECHECK_MS := 2000
## Per-frame cost probe (QA): usec of the last spot search (per layout change; re-checked every 2 s during the intro).
var origin_usec := 0

func origin_point() -> Vector3:
	return game.target_position("lf_horse_origin")

## {"horse": Vector3, "squad": Vector3, "out": Vector3 (unit, towards the forest)} or {} without a city.
func horse_origin_spots() -> Dictionary:
	var origin := origin_point()
	var stage: Node3D = game.stage
	if origin == Vector3.INF or not is_instance_valid(stage) or stage.get("walls") == null or stage.camera == null:
		return {}
	var walls = stage.walls
	# The city rebuilds its walls / buildings in stages (a hall upgrade, a layout change): the key holds
	# the node counts as well, and a cached answer is re-checked every ORIGIN_RECHECK_MS.
	var buildings: Variant = stage.get("buildings")
	var key := "%s|%d|%s|%s|%d|%d" % [str(origin.snapped(Vector3.ONE * 0.25)), stage.get_instance_id(), str(walls.signature),
		str(walls.node.get_instance_id() if is_instance_valid(walls.node) else 0), walls.node.get_child_count() if is_instance_valid(walls.node) else 0,
		(buildings as Node).get_child_count() if buildings is Node else 0]
	var intro_on: bool = not intro_horse.is_empty() or (game.get("intro") != null and game.intro.mode == "animated")
	if key == origin_key and (not intro_on or Time.get_ticks_msec() - origin_at < ORIGIN_RECHECK_MS):
		return origin_spots
	origin_at = Time.get_ticks_msec()
	origin_key = key
	var started := Time.get_ticks_usec()
	var corridor := {"from": Vector2(-8, -55), "to": Vector2(-12, -60), "radius": 3.0}
	var atlas_corridor: Variant = game.world_call("entrance_corridor_spec")
	if atlas_corridor is Dictionary and not atlas_corridor.is_empty():
		corridor = atlas_corridor
	var out2: Vector2 = (corridor.to - corridor.from).normalized()
	var out := Vector3(out2.x, 0, out2.y)
	var boxes := structure_boxes(origin, 48.0)
	var toward: Vector3 = stage.camera.global_transform.basis.z.normalized()
	var candidates: Array = []
	var step := 1.0
	var r := -ORIGIN_SEARCH
	while r <= ORIGIN_SEARCH:
		var c := -ORIGIN_SEARCH
		while c <= ORIGIN_SEARCH:
			var offset := Vector3(c, 0, r)
			if offset.length() <= ORIGIN_SEARCH and offset.dot(out) >= -1.5:
				candidates.append(offset)
			c += step
		r += step
	candidates.sort_custom(func(a: Vector3, b: Vector3) -> bool: return a.length_squared() < b.length_squared())
	var horse := Vector3.INF
	var squad := Vector3.INF
	# Nearest fully visible spot; if a structure hides every one, the least hidden (fewest sample points).
	var fallback := Vector3.INF
	var fallback_hidden := 6
	for offset: Vector3 in candidates:
		var p: Vector3 = origin + offset
		if not known_ground(p, corridor):
			continue
		var g: Vector3 = game.ground(p.x, p.z)
		var hidden := structure_hidden_points(g, boxes, toward)
		if hidden > 0:
			if hidden < fallback_hidden:
				fallback_hidden = hidden
				fallback = g
			continue
		if horse == Vector3.INF:
			horse = g
		elif g.distance_to(horse) >= 2.6 and g.distance_to(horse) <= 5.0 and (g - horse).dot(out) <= 0.5:
			squad = g
			break
	if horse == Vector3.INF:
		horse = fallback if fallback != Vector3.INF else origin
	if squad == Vector3.INF:
		squad = horse - out * 2.8
	origin_spots = {"horse": horse, "squad": squad, "out": out, "shifted": horse.distance_to(origin) > 0.5}
	origin_usec = Time.get_ticks_usec() - started
	return origin_spots

## Known ground by construction: the town square (createFogState: cell centres −54…54 → ±56) or the
## entrance corridor (cells whose centre lies within its radius); 1 m inside, so the fog edge band
## never covers the actor.
func known_ground(p: Vector3, corridor: Dictionary) -> bool:
	if maxf(absf(p.x), absf(p.z)) <= 55.0:
		return true
	var a: Vector2 = corridor.from
	var b: Vector2 = corridor.to
	var q := Vector2(p.x, p.z)
	var t := clampf((q - a).dot(b - a) / maxf((b - a).length_squared(), 0.0001), 0.0, 1.0)
	return q.distance_to(a.lerp(b, t)) <= float(corridor.radius) - 1.0

## Oriented boxes of the city structures (wall pieces, towers, roofs, gate, buildings) within `reach` m
## of p: {"xf": instance → world, "inv": world → instance, "box": local AABB, "world": world AABB}.
## Oriented, not world AABBs: a tower roof is a pyramid turned 45°, its world AABB is twice its area
## and hid the whole entrance.
func structure_boxes(center: Vector3, reach: float) -> Array:
	var stage: Node3D = game.stage
	var roots: Array = []
	if stage.walls != null and is_instance_valid(stage.walls.node):
		roots.append(stage.walls.node)
	if stage.get("buildings") is Node:
		roots.append(stage.buildings)
	if is_instance_valid(stage.get("gate_node")):
		roots.append(stage.gate_node)
	var boxes: Array = []
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
				var count := multi.visible_instance_count if multi.visible_instance_count >= 0 else multi.instance_count
				for i in count:
					var xf: Transform3D = geometry.global_transform * multi.get_instance_transform(i)
					add_structure_box(boxes, xf, local, center, reach)
			elif geometry is MeshInstance3D and (geometry as MeshInstance3D).mesh != null:
				add_structure_box(boxes, geometry.global_transform, (geometry as MeshInstance3D).mesh.get_aabb(), center, reach)
	return boxes

func add_structure_box(boxes: Array, xf: Transform3D, local: AABB, center: Vector3, reach: float) -> void:
	var world: AABB = xf * local
	if Vector2(world.get_center().x - center.x, world.get_center().z - center.z).length() > reach + world.size.length() * 0.5:
		return
	if absf(xf.basis.determinant()) < 0.000001:
		return
	boxes.append({"xf": xf, "inv": xf.affine_inverse(), "box": local, "world": world})

## How many of the actor's sample points (legs 0.5 m, body 1.3 m, head 2.0 m, ±0.9 m flanks at 1.0 m) a
## structure hides from the orthographic camera (0…5); inside a structure counts as hidden. The legs
## count: a spot right behind a wall walk showed only the mare's back.
func structure_hidden_points(g: Vector3, boxes: Array, toward: Vector3) -> int:
	var side := Vector3(toward.z, 0, -toward.x).normalized()
	var hidden := 0
	for p: Vector3 in [g + Vector3.UP * 0.5, g + Vector3.UP * 1.3, g + Vector3.UP * 2.0, g + Vector3.UP * 1.0 + side * 0.9, g + Vector3.UP * 1.0 - side * 0.9]:
		var a := p + toward * 0.3
		var b := p + toward * 140.0
		for entry: Dictionary in boxes:
			if not (entry.world as AABB).grow(0.3).intersects_segment(a, b) and not (entry.world as AABB).grow(0.3).has_point(p):
				continue
			var inv: Transform3D = entry.inv
			var box: AABB = entry.box
			if box.grow(0.2).has_point(inv * p) or box.intersects_segment(inv * a, inv * b):
				hidden += 1
				break
	return hidden

func structure_hides(g: Vector3, boxes: Array, toward: Vector3) -> bool:
	return structure_hidden_points(g, boxes, toward) > 0

## Presentation shift of a move that starts or ends at the horse origin onto the spot of `who`
## ("horse" / "squad"), faded over ORIGIN_BLEND m.
func origin_shift(move: Dictionary, route: Dictionary, distance: float, who: String) -> Vector3:
	var spots := horse_origin_spots()
	if spots.is_empty() or not bool(spots.get("shifted", false)):
		return Vector3.ZERO
	var origin := origin_point()
	var path: Array = move.get("path", [])
	if path.is_empty():
		return Vector3.ZERO
	var spot: Vector3 = spots.get(who, spots.horse)
	var shift := Vector3(spot.x - origin.x, 0, spot.z - origin.z)
	var first := Vector2(float(path[0].get("x", 0)), float(path[0].get("z", 0)))
	var last := Vector2(float(path.back().get("x", 0)), float(path.back().get("z", 0)))
	var w := 0.0
	if first.distance_to(Vector2(origin.x, origin.z)) < 1.5:
		w = maxf(w, 1.0 - smoothstep(0.0, ORIGIN_BLEND, distance))
	if String(move.get("targetId", "")) == "lf_horse_origin" or last.distance_to(Vector2(origin.x, origin.z)) < 1.5:
		w = maxf(w, smoothstep(float(route.total) - ORIGIN_BLEND, float(route.total), distance))
	return shift * w

## Intro presentation: the mare walks out of the mist along the entrance corridor.
func start_intro_horse(from: Vector3, to: Vector3, walk_seconds: float) -> void:
	intro_horse = {"from":from, "to":to, "walk":walk_seconds, "started":Time.get_ticks_msec()}
	motion.erase("horse")
	turns.erase("horse")

func stop_intro_horse() -> void:
	intro_horse = {}

# ------------------------------------------------------------------ squad representatives
func squad_focus() -> Vector3:
	var leader: Dictionary = motion.get("squad_0", {})
	if not leader.is_empty():
		return leader.position
	var node := String(game.client.squad().get("node", ""))
	if node.is_empty():
		return Vector3.INF
	return game.target_position(node)

func squad_model_paths(index: int) -> Array:
	var fallback := ""
	var units: Dictionary = game.client.squad().get("units", {})
	var data: Dictionary = game.main.data
	for id in units:
		if data.unitModels.has(id) and not data.unitModels[id].get("mounted", false):
			fallback = data.unitModels[id].field
			break
	if fallback.is_empty() and data.unitModels.has("ENG-01"):        # forest roster: ENG-01/02/03/04/06 only
		fallback = data.unitModels["ENG-01"].field
	return [SQUAD_GLBS[index], fallback]

func update_squad(now: float, delta: float) -> void:
	var count := squad_member_count()
	for index in 3:
		var id := "squad_%d" % index
		if index >= count:
			if rigs.has(id):
				drop(id)
			continue
		var paths := squad_model_paths(index)
		var actor := rig(id, paths[0], paths[1])
		actor.set_meta("occluder_height", 2.0)
		if choreo_owns(id):
			if show_actor(actor, actor.position):
				markers.append({"position":actor.position + Vector3.UP * 1.4, "kind":"squad", "id":id})
			continue
		var pose := squad_pose(index, now)
		var speed := place(id, actor, pose.position, pose.yaw, delta, false, bool(pose.get("keep_y", false)))
		if pose.has("clip"):
			if pose.get("hold", false):
				actor.hold_end(pose.clip)
			elif pose.has("at"):
				actor.pose_at(pose.clip, pose.at)
			else:
				actor.play(pose.clip, 0.2)
		elif not soldier_one_shot(actor) or pose.get("predicted", false):
			# Speed-matched: the authoritative path speed while moving, the measured speed otherwise.
			actor.locomote(float(pose.get("speed", 0.0)) if pose.get("moving", false) else speed, GUARD_CLIPS if pose.get("guard", false) else SOLDIER_CLIPS)
		if show_actor(actor, actor.position):
			markers.append({"position":actor.position + Vector3.UP * 1.4, "kind":"squad", "id":id})
	if count > 0:
		var leader: Dictionary = motion.get("squad_0", {})
		if not leader.is_empty():
			game.pin("lf_squad", leader.position, 16.0)
			if game.fog_clear(leader.position) and plates_for_actors():
				tags.append({"position":leader.position + Vector3.UP * 3.0, "text":game.content.text("hud.squad"), "kind":"squad"})

## Name plates for the horse / squad only while they are small on screen (wide zoom); up
## close the 3D actors read by themselves and the plates would cover them.
func plates_for_actors() -> bool:
	return float(game.stage.camera_zoom) >= 44.0

## A live one-shot (salute, help, attack beat) finishes before locomotion takes over.
func soldier_one_shot(actor: Rig) -> bool:
	return actor.playing_id() in ["lf_soldier_salute", "lf_soldier_help", "lf_soldier_unlock"]

func squad_pose(index: int, now: float) -> Dictionary:
	var guess := predicted_pose(index, now)
	if not guess.is_empty():
		return guess
	var squad: Dictionary = game.client.squad()
	var move: Variant = squad.get("move")
	var busy: Variant = squad.get("busy")
	var node := String(squad.get("node", "lf_horse_origin"))
	var lateral: Vector3 = SQUAD_FORMATION[index]
	if move is Dictionary and not (move.get("path", []) as Array).is_empty():
		var sample := move_sample(move, now, float(index) * 1.6)
		var tangent: Vector3 = sample.tangent
		var side := Vector3(tangent.z, 0, -tangent.x)
		var p: Vector3 = sample.position + side * lateral.x * 0.8
		return {"position":p, "yaw":PathMotion.yaw_of(tangent), "moving":not sample.arrived, "speed":sample.speed}
	var fight: Dictionary = game.client.battle()
	if busy != null and String(busy) == "battle" and not fight.is_empty():
		return battle_member_pose(index, fight, now)
	if busy != null and String(busy) == "escort":
		var walk: Dictionary = game.client.escort()
		var walk_move: Variant = walk.get("move")
		if walk_move is Dictionary:
			var back: float = [0.0, 6.2, 7.0][index]
			var sample := move_sample(walk_move, now, back)
			var tangent: Vector3 = sample.tangent
			var side := Vector3(tangent.z, 0, -tangent.x)
			var standing := float(sample.behind) < 0.0
			return {"position":sample.position + side * [0.0, -0.9, 0.9][index], "yaw":PathMotion.yaw_of(tangent), "moving":not sample.arrived and not standing, "speed":sample.speed}
	var center: Vector3 = game.target_position(node)
	var rest: Variant = squad.get("position")
	if rest is Dictionary and (center == Vector3.INF or node.contains("#")):
		center = game.ground(float(rest.get("x", 0)), float(rest.get("z", 0)))
	if center == Vector3.INF:
		center = game.target_position("lf_horse_origin")
	if node == "lf_horse_origin":
		var spots := horse_origin_spots()
		if not spots.is_empty():
			center = spots.squad
	var site_here := node.get_slice(":", 0).replace("lf_key_", "lf_site_")
	var anchor: Dictionary = game.site_anchor(site_here) if site_here.begins_with("lf_site_") else {}
	var plates: Variant = game.client.poi(site_here).get("mechanism", {}).get("plates")
	if plates is Dictionary and String(plates.get("state", "free")) in ["walking", "held"] and anchor.has("plate_left") and index < 2:
		var plate: Vector3 = plate_stand_point(site_here, index)
		return {"position":plate, "yaw":PathMotion.yaw_of(anchor.get("artifact", plate) - plate), "clip":["lf_soldier_guard", "lf_soldier_idle", "Shield_Block", "Idle"], "keep_y":plate.y > -INF}
	match target_kind(node):
		"boss":
			var arena: Vector3 = game.target_position("lf_boss_ancient_maw")
			var gap := boss_gap_point(BOSS_FIGHT_DISTANCE)
			var fwd := (arena - gap)
			fwd.y = 0
			fwd = fwd.normalized()
			var right := Vector3(fwd.z, 0, -fwd.x)
			return {"position":gap + right * lateral.x * 1.2 + fwd * lateral.z * 0.8, "yaw":PathMotion.yaw_of(fwd), "guard":true}
		"cage":
			# The unlocking soldier stands at the socket on the door; the others behind him.
			var cage: Rig = rigs.get("cage_" + site_here)
			if cage != null and cage.is_ready():
				var front: Vector3 = cage.global_transform * door_front_local(cage)
				var aim: Vector3 = cage.global_transform * key_slot_local(cage)
				var fwd := Vector3(aim.x - front.x, 0, aim.z - front.z).normalized()
				var right := Vector3(fwd.z, 0, -fwd.x)
				var spot: Vector3 = front + [Vector3.ZERO, -fwd * 1.3 - right * 1.3, -fwd * 1.5 + right * 0.4][index]
				return {"position":spot, "yaw":PathMotion.yaw_of(fwd)}
		"key":
			var device: Rig = rigs.get("mechanism_" + site_here)
			if device != null and device.is_ready():
				var front: Vector3 = device.global_transform * Vector3(0, 0, 2.0)
				var fwd := (device.global_position - front)
				fwd.y = 0
				fwd = fwd.normalized()
				var right := Vector3(fwd.z, 0, -fwd.x)
				return {"position":front + right * lateral.x * 1.1 - fwd * absf(lateral.z) * 0.8, "yaw":PathMotion.yaw_of(fwd)}
	# 1024: a menacing creature at this glade: the squad stands its ground in the guard stance,
	# shields towards it (centre of the glade or the guardian's approach).
	if menace.has(site_here) and (node == site_here or node.ends_with(":guardian")):
		var creature: Rig = rigs.get("guardian_" + site_here)
		if creature != null and is_instance_valid(creature):
			var focus_g := focus_for_node(node, center)
			var fwd := focus_g - center
			fwd.y = 0
			fwd = fwd.normalized() if fwd.length_squared() > 0.01 else Vector3.FORWARD
			var right_g := Vector3(fwd.z, 0, -fwd.x)
			var base := center - fwd * float(STAND_OFF.guardian) if node.ends_with(":guardian") else center
			var spot: Vector3 = base + right_g * [0.0, -1.3, 1.3][index] - fwd * [0.0, 0.5, 0.5][index]
			return {"position":spot, "yaw":PathMotion.yaw_of(creature.position - spot), "guard":true}
	var focus := focus_for_node(node, center)
	var forward := (focus - center)
	forward.y = 0
	if forward.length_squared() < 0.01:
		forward = Vector3(sin(forest_heading()), 0, cos(forest_heading()))
	forward = forward.normalized()
	var right := Vector3(forward.z, 0, -forward.x)
	if target_kind(node) == "guardian":
		center = center - forward * float(STAND_OFF.guardian)
	elif node.begins_with("lf_site_") and not node.contains(":"):
		# Glade centre: the three stand abreast on the cage side, clear of the guardian's spot.
		center = center - forward * 0.4
		lateral = [Vector3(0, 0, 0), Vector3(-1.2, 0, -0.3), Vector3(1.2, 0, -0.3)][index]
	var p: Vector3 = center + right * lateral.x + forward * lateral.z
	return {"position":p, "yaw":PathMotion.yaw_of(forward), "guard":node.ends_with(":guardian")}

func focus_for_node(node: String, center: Vector3) -> Vector3:
	if node.contains(":"):
		var site_id := node.get_slice(":", 0)
		var anchor: Dictionary = game.site_anchor(site_id)
		match node.get_slice(":", 1):
			"guardian":
				return anchor.get("guardian", center) + (anchor.get("guardian", center) - anchor.get("approach", center)).normalized() * 0.1
			"cage":
				return anchor.get("cage", center)
	if node.begins_with("lf_site_"):
		return game.site_anchor(node).get("cage", center)
	if node.begins_with("lf_key_"):
		return center + Vector3(0, 0, -1)
	if node == "lf_horse_origin":
		var horse: Dictionary = motion.get("horse", {})
		if not horse.is_empty():
			return horse.position
	return center + Vector3(sin(forest_heading()), 0, cos(forest_heading()))

## Standing point on a paired-latch plate (top of the live plate node, follows its press).
func plate_stand_point(site_id: String, index: int) -> Vector3:
	var anchor: Dictionary = game.site_anchor(site_id)
	var wanted: Vector3 = anchor.plate_left if index == 0 else anchor.plate_right
	var device: Rig = rigs.get("mechanism_" + site_id)
	if device != null and device.is_ready():
		var best: Node3D = null
		var gap := INF
		for name_id in ["plate_left", "plate_right"]:
			var node := device.part(name_id)
			if node != null and node.is_inside_tree():
				var d := Vector2(node.global_position.x - wanted.x, node.global_position.z - wanted.z).length()
				if d < gap:
					gap = d
					best = node
		if best != null and gap < 2.0:
			return best.global_position
	return wanted

# ------------------------------------------------------------------ sites: props, captives, guardians
func update_sites(now: float, delta: float) -> void:
	var present := {}
	for poi in adv.get("pois", []):
		if String(poi.get("kind", "site")) != "site":
			continue
		var site_id := String(poi.get("id", ""))
		present[site_id] = true
		var anchor: Dictionary = game.site_anchor(site_id)
		var center: Vector3 = anchor.get("center", game.target_position(site_id))
		var near := visible_in_view(center) or visible_in_view(anchor.get("cage", center))
		update_props(site_id, poi, anchor, near, delta)
		update_captives(site_id, poi, anchor, now, delta, near)
		update_guardian(site_id, poi, anchor, now, delta, near)
		var step := int(game.client.site_state(site_id).get("step", 0))
		markers.append({"position":center + Vector3.UP * 2.0, "kind":"site", "id":site_id, "site":site_id})
		var mech_open: bool = game.mech.is_open() and game.mech.site_id == site_id
		if game.fog_clear(center) and not mech_open:
			tags.append({"position":center + Vector3.UP * 4.2, "text":game.site_name(site_id), "kind":"site", "step":step})
		if String(poi.get("variation", "")) == "trail_cache" and game.mech.is_open() and game.mech.site_id == site_id:
			for symbol in anchor.get("landmarks", {}):
				var mark: Vector3 = anchor.landmarks[symbol]
				markers.append({"position":mark + Vector3.UP * 1.0, "kind":"landmark", "symbol":String(symbol), "site":site_id})
				tags.append({"position":mark + Vector3.UP * 0.6, "text":game.content.symbol_label(String(symbol)), "kind":"landmark"})
	for site_id in site_props.keys():
		if not present.has(site_id):
			for id in site_props[site_id].values():
				drop(String(id))
			site_props.erase(site_id)

func cage_file(cage_kind: String) -> String:
	return ASSETS + "props/" + String(CAGE_FILES.get(cage_kind, "lf_cage_wood")) + ".glb"

func update_props(site_id: String, poi: Dictionary, anchor: Dictionary, near: bool, delta: float) -> void:
	var record: Dictionary = site_props.get(site_id, {})
	var cage_id := "cage_" + site_id
	var cage := rig(cage_id, cage_file(String(poi.get("cage", "oak"))), "", 1.0, props_parent)
	record.cage = cage_id
	var cage_pos: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	cage.position = game.ground(cage_pos.x, cage_pos.z)
	cage.rotation.y = float(anchor.get("cage_yaw", 0.0))
	# 1024: set_active keeps a loading rig processing (actor_rig); `wanted` puts out-of-view props
	# behind the on-screen rigs in the load queue. Before, every cage stayed "loading" forever.
	cage.wanted = near
	cage.set_active(near and cage.is_ready())
	var artifact: Dictionary = poi.get("artifact", {})
	var family := String(artifact.get("family", "stone_rune"))
	if cage.is_ready():
		apply_socket_plate(cage, family)
		if not choreo.has("cage:" + site_id):
			if String(poi.get("cagePose", "closed")) == "open":
				if cage.get_meta("pose", "") != "open":
					cage.set_meta("pose", "open")
					if not cage.hold_end(["lf_cage_gate_settle", "lf_cage_gate_open"]):
						swing_door(cage, 1.0)
			elif cage.get_meta("pose", "") != "closed":
				cage.set_meta("pose", "closed")
				if not cage.hold_end(["lf_cage_gate_close"]):
					swing_door(cage, 0.0)
		update_roof(cage, site_id, poi, delta)
	if near:
		markers.append({"position":cage.position + Vector3.UP * 1.6, "kind":"cage", "site":site_id, "id":cage_id})
	var artifact_id := "artifact_" + site_id
	var key_prop := rig(artifact_id, ASSETS + "props/lf_artifact_%s.glb" % family, "", 1.0, props_parent)
	key_prop.wanted = near
	record.artifact = artifact_id
	if key_prop.is_ready():
		apply_artifact_variant(key_prop, family, String(artifact.get("id", "")), site_id)
	var state := String(artifact.get("state", "hidden"))
	var mechanism: Dictionary = poi.get("mechanism", {})
	var kind := String(poi.get("variation", mechanism.get("kind", "")))
	var device: Rig = null
	if not kind.is_empty():
		var mech_id := "mechanism_" + site_id
		device = rig(mech_id, ASSETS + "props/lf_mechanism_%s.glb" % kind, "", 1.0, props_parent)
		record.mechanism = mech_id
		place_device(device, kind, anchor)
		if kind == "winch_sequence" and device.is_ready() and not device.has_meta("void_lifted"):
			var pit_void := device.part("pit_void")
			if pit_void != null:
				pit_void.position.y += PIT_VOID_LIFT
			device.set_meta("void_lifted", true)
		device.wanted = near
		device.set_active(near and device.is_ready())
		if device.is_ready():
			update_mechanism_pose(site_id, kind, device, mechanism, state != "hidden", delta)
		if near and not solved_or_found(poi):
			markers.append({"position":device.global_position + Vector3.UP * 1.2, "kind":"artifact", "site":site_id, "id":mech_id})
	if choreo.has("key:" + site_id):
		pass
	elif state == "in_socket":
		seat_artifact(key_prop, cage, false)
		key_prop.set_active(near and key_prop.is_ready() and cage.is_ready())
		game.fx.glow_world("artifact_" + site_id, Vector3.INF)
	elif state == "hidden" and bool(mechanism.get("solved", false)):
		# Revealed by the solved mechanism: rests on the device's artifact spot, glowing softly.
		release_artifact(key_prop)
		var spot: Vector3 = device.socket_global("artifact_spot") if device != null and device.is_ready() else Vector3.INF
		if spot == Vector3.INF:
			var fallback: Vector3 = anchor.get("artifact", cage_pos)
			spot = game.ground(fallback.x, fallback.z) + Vector3.UP * 0.5
		key_prop.position = spot + Vector3.UP * (0.16 + 0.05 * sin(Time.get_ticks_msec() / 420.0))
		key_prop.rotation = Vector3(deg_to_rad(-35.0), deg_to_rad(45.0) + Time.get_ticks_msec() / 2600.0, 0.0)
		key_prop.set_glow(1.6 + 0.6 * sin(Time.get_ticks_msec() / 300.0))
		key_prop.set_active(near and key_prop.is_ready())
		game.fx.glow_world("artifact_" + site_id, key_prop.position)
	else:
		release_artifact(key_prop)
		key_prop.set_active(false)
		game.fx.glow_world("artifact_" + site_id, Vector3.INF)
	site_props[site_id] = record

func solved_or_found(poi: Dictionary) -> bool:
	return String(poi.get("artifact", {}).get("state", "hidden")) != "hidden"

## Only the plate of the server's artifact family is shown (all four sit at the same spot).
func apply_socket_plate(cage: Rig, family: String) -> void:
	if cage.get_meta("plate", "") == family:
		return
	cage.set_meta("plate", family)
	var plates: Dictionary = cage.meta.get("socketInfo", {}).get("socket_plates", {})
	if plates.is_empty():
		plates = {"stone_rune":"socket_stone_rune", "bronze_seal":"socket_bronze_seal", "amber_crystal":"socket_amber_crystal", "bone_key":"socket_bone_key"}
	for key in plates:
		var node := cage.part(String(plates[key]))
		if node != null:
			node.visible = String(key) == family

## Shows exactly one variant node of the artifact family: the meta variant whose key_id is
## this key, else v1..v3 by the site's place in its family (sites 01/05/09 → v1/v2/v3).
func apply_artifact_variant(prop: Rig, family: String, key_id: String, site_id: String) -> void:
	if prop.get_meta("variant_key", "") == key_id + family:
		return
	prop.set_meta("variant_key", key_id + family)
	var chosen := ""
	var variants_meta: Dictionary = prop.meta.get("variants", {})
	for v in variants_meta:
		if String(variants_meta[v].get("key_id", "")) == key_id:
			chosen = String(variants_meta[v].get("node", ""))
	if chosen.is_empty():
		var number := int(game.content.site_number(site_id))
		chosen = "lf_artifact_%s_v%d" % [family, (maxi(number, 1) - 1) / 4 % 3 + 1]
	for v in 3:
		var node := prop.part("lf_artifact_%s_v%d" % [family, v + 1])
		if node != null:
			node.visible = String(node.name) == chosen
	var own_socket := prop.part("lf_artifact_%s_socket" % family)
	if own_socket != null:
		own_socket.visible = false   # the cage door carries the socket plate
	prop.set_glow(0.0)

## Live key_slot node of the cage door (null when the cage has none).
func key_slot(cage: Rig) -> Node3D:
	return cage.part("key_slot") if cage != null and cage.is_ready() else null

## The artifact is parented to the live key_slot (moves with the door). key_slot's local +Y
## is the plate's outward normal, the artifact's front is its +Z: rotate -90° about X so the
## piece lies flush in the plate (its insert clip travels along that normal).
const KEY_SLOT_FIX := Vector3(-PI * 0.5, 0.0, 0.0)

func seat_artifact(prop: Rig, cage: Rig, animate: bool) -> void:
	var slot := key_slot(cage)
	if slot == null or not prop.is_ready():
		return
	if prop.get_parent() != slot:
		prop.reparent(slot, false)
	prop.position = Vector3.ZERO
	prop.rotation = KEY_SLOT_FIX
	prop.scale = Vector3.ONE
	prop.set_meta("seated", true)
	if animate:
		prop.play(["lf_artifact_insert"], 0.0, true)
		prop.set_glow(0.3)
		return
	var playing := prop.playing_id()
	if playing == "lf_artifact_insert":
		return
	if playing != "lf_artifact_glow":
		prop.play(["lf_artifact_glow"], 0.0)
	prop.set_glow(3.0 + 0.6 * sin(prop.clip_time() * PI))

func release_artifact(prop: Rig) -> void:
	if prop.get_parent() != props_parent and props_parent != null and is_instance_valid(props_parent):
		prop.reparent(props_parent, false)
		prop.set_meta("seated", false)
		prop.rotation = Vector3.ZERO

## Door-front standing point of the unlocking soldier (cage-local): 0.55 m in front of the
## key_slot on the door, on the ground.
func door_front_local(cage: Rig) -> Vector3:
	var k := key_slot_local(cage)
	return Vector3(k.x, 0.0, k.z + 0.62)

func key_slot_local(cage: Rig) -> Vector3:
	var info: Dictionary = cage.meta.get("socketInfo", {}).get("key_slot", {})
	var p: Variant = info.get("position_closed")
	if p is Array and p.size() >= 3:
		return Vector3(float(p[0]), float(p[1]), float(p[2]))
	return Vector3(0.95, 1.23, 1.57)

func door_node(cage: Rig) -> Node3D:
	if cage.has_meta("door_node"):
		var cached: Variant = cage.get_meta("door_node")
		if cached is Node3D and is_instance_valid(cached):
			return cached
	var found := cage.part(String(cage.meta.get("socketInfo", {}).get("door", {}).get("node", "door_pivot")))
	if found == null:
		found = cage.find_part(["door", "gate"])
	cage.set_meta("door_node", found)
	return found

## Fallback when a cage GLB has no gate clip: rotate the door node around its hinge pivot.
func swing_door(cage: Rig, amount: float) -> void:
	var door := door_node(cage)
	if door == null:
		return
	if not door.has_meta("closed_yaw"):
		door.set_meta("closed_yaw", door.rotation.y)
	var opening := deg_to_rad(float(cage.meta.get("door_open_deg", -95.0)))
	door.rotation.y = float(door.get_meta("closed_yaw")) + opening * amount

## Cage roof (meta roofNode) fades away while captives are inside (camera always above).
func update_roof(cage: Rig, site_id: String, poi: Dictionary, delta: float) -> void:
	var roof := cage.part(String(cage.meta.get("roofNode", "roof")))
	if roof == null:
		return
	var inside := choreo.has("cage:" + site_id)
	for person in poi.get("captives", []):
		if String(person.get("state", "caged")) == "caged":
			inside = true
	var zoom: float = float(game.stage.camera_zoom)
	var wanted := 1.0 if inside and zoom <= 95.0 else 0.0
	var current := float(cage.get_meta("roof_fade", 0.0))
	current = move_toward(current, wanted, delta * 2.5)
	if absf(current - float(cage.get_meta("roof_fade", -1.0))) < 0.0001:
		return
	cage.set_meta("roof_fade", current)
	roof.visible = current < 0.995
	for mesh: MeshInstance3D in roof.find_children("*", "MeshInstance3D", true, false):
		mesh.transparency = current * 0.92
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if current > 0.5 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON

# ------------------------------------------------------------------ mechanisms
## Device stands on the key spot; front (+Z) towards the approach. The paired latch is turned
## so its plates sit on the server's plate targets (and its front faces the city camera).
func place_device(device: Rig, kind: String, anchor: Dictionary) -> void:
	var spot: Vector3 = device_spot(kind, anchor)
	# P2.7: painted side towards the city camera (forest_game.PAINTED_DEVICE_YAW)
	var yaw := deg_to_rad(float(game.PAINTED_DEVICE_YAW.get(kind, rad_to_deg(float(anchor.get("cage_yaw", 0.0))))))
	if kind == "paired_latch" and anchor.get("plate_left") is Vector3 and anchor.get("plate_right") is Vector3:
		var a: Vector3 = anchor.plate_left
		var b: Vector3 = anchor.plate_right
		spot = (a + b) * 0.5
		var dir := b - a
		yaw = atan2(-dir.z, dir.x)
		if Vector3(sin(yaw), 0, cos(yaw)).dot(Vector3(1, 0, 1)) < 0.0:
			yaw += PI
	device.position = game.ground(spot.x, spot.z)
	device.rotation.y = yaw

## The fixed city camera's screen-right axis on the ground (camera at target + (75, 83, 75)).
const SCREEN_RIGHT := Vector3(0.70710678, 0.0, -0.70710678)
const SCREEN_TOWARD := Vector3(0.70710678, 0.0, 0.70710678)
const WINCH_BACK := 1.0
## Winch (yaw 45°: its +X is screen right): right end of the crank grip, and the half screen width a cage
## covers (root / iron / wood cages at their atlas yaw), metres.
const WINCH_SCREEN_RIGHT := 2.5
const CAGE_SCREEN_HALF := 2.1
## Lift of the winch's dark pit mouth (node pit_void, 0.24 m below the ground at rest in the GLB = the painting's
## view into the pit) onto the terrain surface, so the pit reads dark through the terrain in the game.
const PIT_VOID_LIFT := 0.29

## Ground spot of a mechanism device. The winch stands screen-left of its key spot when its site's cage, nearer
## the city camera, would hide its right half (drum, right trestle, crank): it is shifted along the screen's
## right axis until the crank clears the cage, so the whole painted face reads in the mechanism UI (art/10).
func device_spot(kind: String, anchor: Dictionary) -> Vector3:
	var spot: Vector3 = anchor.get("artifact", anchor.get("center", Vector3.ZERO))
	if kind != "winch_sequence" or not anchor.get("cage") is Vector3:
		return spot
	var du := (spot - (anchor.cage as Vector3)).dot(SCREEN_RIGHT)
	var need := -(WINCH_SCREEN_RIGHT + CAGE_SCREEN_HALF)
	if du < 0.0 and du > need:
		spot += SCREEN_RIGHT * (need - du)
		# and a step away from the camera: the guardian waiting in front stays below the pit on screen
		spot -= SCREEN_TOWARD * WINCH_BACK
	return spot

## Where the mechanism UI camera looks: the device's body (the winch's drum height), else its key spot.
func device_focus(site_id: String) -> Vector3:
	var device: Rig = rigs.get("mechanism_" + site_id)
	if device != null and is_instance_valid(device):
		return device.global_position + Vector3.UP * (1.1 if device.asset_path.contains("winch") else 0.4)
	return game.site_anchor(site_id).get("artifact", game.target_position(site_id))

func mechanism_feedback(site_id: String, symbol: String, ok: bool) -> void:
	mechanism_symbols[site_id] = {"symbol":symbol, "ok":ok, "at":Time.get_ticks_msec()}

## Stable node pose of a mechanism for an authoritative progress (node ownership per meta).
func mechanism_stable(device: Rig, kind: String, site_id: String, progress: int, solved: bool) -> Dictionary:
	var pose := {}
	var solution: Array = game.content.site(site_id).get("artifact", {}).get("puzzle", {}).get("solution", [])
	match kind:
		"rune_lock":
			device.sample_into(pose, "lf_lock_mechanism", 99.0 if solved else 0.0, ["door_pivot", "key_lever"])
			for k in 3:
				var symbol := String(solution[k]) if solution.size() > k else "mountain"
				device.sample_into(pose, "lf_rune_ring%d_%s" % [k + 1, symbol], 99.0 if k < progress else 0.0, ["ring_%d" % (k + 1)])
		"winch_sequence":
			device.sample_into(pose, "lf_lock_mechanism", 0.0)
			device.sample_into(pose, "lf_rope_release", 0.0, ["brake_lever", "chest", "crank", "drum", "rope", "big_gear", "pinion"])
			device.sample_into(pose, "lf_winch_brake", 99.0 if progress >= 1 else 0.0, ["brake_lever"])
			device.sample_into(pose, "lf_winch_pawl", 99.0 if progress >= 2 else 0.0, ["pawl"])
			if solved:
				device.sample_into(pose, "lf_rope_release", 99.0, ["brake_lever", "chest", "crank", "drum", "rope", "pawl", "big_gear", "pinion"])
				device.sample_into(pose, "lf_lock_mechanism", 99.0, ["chest", "chest_lid"])
		"paired_latch":
			device.sample_into(pose, "lf_latch_reset", 99.0)
			var sides := plate_sides(device, site_id)
			if progress >= 1:
				device.sample_into(pose, "lf_latch_plate_" + sides[0], 99.0, latch_nodes(sides[0]))
			if progress >= 2:
				device.sample_into(pose, "lf_latch_plate_" + sides[1], 99.0, latch_nodes(sides[1]))
			if solved:
				device.sample_into(pose, "lf_lock_mechanism", 99.0)
		"trail_cache":
			device.sample_into(pose, "lf_trail_cache_close", 99.0)
			if solved:
				device.sample_into(pose, "lf_lock_mechanism", 99.0)
	return pose

static func latch_nodes(side: String) -> Array:
	return ["lever_" + side, "plate_" + side, "spring_" + side]

## Asset plate sides (left/right) standing on the server's plate_left / plate_right targets.
func plate_sides(device: Rig, site_id: String) -> Array:
	var anchor: Dictionary = game.site_anchor(site_id)
	var node := device.part("plate_left")
	if node == null or not node.is_inside_tree() or not anchor.get("plate_left") is Vector3:
		return ["left", "right"]
	var left: Vector3 = anchor.plate_left
	var right: Vector3 = anchor.plate_right if anchor.get("plate_right") is Vector3 else left
	var p := node.global_position
	return ["left", "right"] if Vector2(p.x - left.x, p.z - left.z).length() <= Vector2(p.x - right.x, p.z - right.z).length() else ["right", "left"]

## Live steps for a progress change: [{clip, nodes, start}] on top of the previous stable pose.
func mechanism_steps(device: Rig, kind: String, site_id: String, before: int, after: int, solved: bool, was_solved: bool) -> Array:
	var steps: Array = []
	var solution: Array = game.content.site(site_id).get("artifact", {}).get("puzzle", {}).get("solution", [])
	if after < before and not solved:
		# Wrong input: the server reset the attempt (art/10 reset beats).
		match kind:
			"rune_lock":
				var chosen := String(mechanism_symbols.get(site_id, {}).get("symbol", ""))
				if not chosen.is_empty() and before < 3:
					steps.append({"clip":"lf_rune_ring%d_%s" % [before + 1, chosen], "nodes":["ring_%d" % (before + 1)], "start":0.0})
				steps.append({"blend":0.7, "start":0.6})
			"paired_latch":
				steps.append({"clip":"lf_latch_reset", "nodes":[], "start":0.0})
			_:
				steps.append({"blend":0.6, "start":0.0})
		return steps
	var t := 0.0
	for p in range(before, after):
		match kind:
			"rune_lock":
				if p < 3:
					var symbol := String(solution[p]) if solution.size() > p else "mountain"
					steps.append({"clip":"lf_rune_ring%d_%s" % [p + 1, symbol], "nodes":["ring_%d" % (p + 1)], "start":t})
					t += 0.6
			"winch_sequence":
				if p == 0:
					steps.append({"clip":"lf_winch_brake", "nodes":["brake_lever"], "start":t})
					t += 0.6
				elif p == 1:
					steps.append({"clip":"lf_winch_pawl", "nodes":["pawl"], "start":t})
					t += 0.5
			"paired_latch":
				if p < 2:
					var side: String = plate_sides(device, site_id)[p]
					steps.append({"clip":"lf_latch_plate_" + side, "nodes":latch_nodes(side), "start":t})
					t += 0.8
			"trail_cache":
				if p < 2:
					steps.append({"clip":"lf_trail_mark_%d" % (p + 1), "nodes":["mark_landmark_a" if p == 0 else "mark_landmark_b"], "start":t})
					t += 1.0
	if solved and not was_solved:
		match kind:
			"rune_lock":
				steps.append({"clip":"lf_lock_mechanism", "nodes":["door_pivot", "key_lever"], "start":t})
			"winch_sequence":
				steps.append({"clip":"lf_rope_release", "nodes":["brake_lever", "chest", "crank", "drum", "rope", "pawl", "big_gear", "pinion"], "start":t})
				steps.append({"clip":"lf_lock_mechanism", "nodes":["chest", "chest_lid"], "start":t + 1.3})
			"paired_latch":
				steps.append({"clip":"lf_lock_mechanism", "nodes":[], "start":t})
			"trail_cache":
				steps.append({"clip":"lf_lock_mechanism", "nodes":["cache_lid"], "start":t})
	return steps

func update_mechanism_pose(site_id: String, kind: String, device: Rig, mechanism: Dictionary, found: bool, delta: float) -> void:
	var progress := int(mechanism.get("progress", 0))
	var solved := bool(mechanism.get("solved", false)) or found
	if solved:
		progress = int(mechanism.get("length", 3))
	var entry: Dictionary = mechanisms.get(site_id, {})
	var signature := "%d|%s" % [progress, str(solved)]
	if entry.is_empty() or entry.get("device") != device:
		entry = {"device":device, "signature":signature, "progress":progress, "solved":solved,
			"pose":mechanism_stable(device, kind, site_id, progress, solved), "live":{}}
		mechanisms[site_id] = entry
		device.apply_pose(entry.pose)
		return
	if String(entry.signature) != signature:
		var before := int(entry.progress)
		var was_solved := bool(entry.solved)
		var target := mechanism_stable(device, kind, site_id, progress, solved)
		var base: Dictionary = entry.pose
		if progress > before or (solved and not was_solved):
			base = mechanism_stable(device, kind, site_id, before, was_solved)
		var steps := mechanism_steps(device, kind, site_id, before, progress, solved, was_solved)
		var end := 0.0
		for step in steps:
			end = maxf(end, float(step.start) + (float(step.blend) if step.has("blend") else device.clip_length([String(step.clip)])))
		entry.live = {"steps":steps, "base":base, "target":target, "t":0.0, "end":end} if not steps.is_empty() and not first_state else {}
		entry.signature = signature
		entry.progress = progress
		entry.solved = solved
		entry.pose = target
		if entry.live.is_empty():
			device.apply_pose(target)
	var live: Dictionary = entry.live
	if live.is_empty():
		return
	var previous := float(live.t)
	live.t = previous + delta
	var pose: Dictionary = (live.base as Dictionary).duplicate(true)
	for step in live.steps:
		var local := float(live.t) - float(step.start)
		if local < 0.0:
			continue
		if step.has("blend"):
			blend_pose(pose, live.target, clampf(local / float(step.blend), 0.0, 1.0))
		else:
			device.sample_into(pose, String(step.clip), local, step.nodes)
			var before_local := previous - float(step.start)
			if before_local < device.clip_length([String(step.clip)]):
				mechanism_markers(device, String(step.clip), before_local, local)
	device.apply_pose(pose)
	if float(live.t) >= float(live.end):
		entry.live = {}
		device.apply_pose(entry.pose)

static func blend_pose(pose: Dictionary, target: Dictionary, f: float) -> void:
	var w := smoothstep(0.0, 1.0, f)
	for key in target:
		var to: Dictionary = target[key]
		var from: Dictionary = pose.get(key, {})
		var out := from.duplicate()
		if to.has("pos"):
			out.pos = (from.get("pos", to.pos) as Vector3).lerp(to.pos, w)
		if to.has("rot"):
			out.rot = (from.get("rot", to.rot) as Quaternion).slerp(to.rot, w)
		if to.has("scale"):
			out.scale = (from.get("scale", to.scale) as Vector3).lerp(to.scale, w)
		pose[key] = out

## Mechanism clip markers (click, brake_set, pawl_engaged, plates_down, latch_open, cache_open,
## lid_open): the pose composer drives these clips, so markers are dispatched here.
func mechanism_markers(device: Rig, clip: String, previous: float, now: float) -> void:
	var marks := device.markers_of(clip)
	for marker_name in marks:
		var times: Variant = marks[marker_name]
		for at_value in (times if times is Array else [times]):
			var at := float(at_value)
			if at > previous and at <= now:
				on_marker(device, clip, String(marker_name))

# ------------------------------------------------------------------ captives
func captive_visual(captive: Dictionary) -> String:
	var id := String(captive.get("id", ""))
	var variant: Variant = variants.get("captives", {}).get(id, variants.get(id))
	if variant is Dictionary and variant.has("visual"):
		return String(variant.visual)
	return String(captive.get("visual", "miller"))

## Look variation of one captive (tint / hidden accessory / height scale), {} when none.
func captive_variant(captive: Dictionary) -> Dictionary:
	var id := String(captive.get("id", ""))
	var variant: Variant = variants.get("captives", {}).get(id, variants.get(id))
	return variant if variant is Dictionary else {}

## Seat on the cage floor: the cage's captive_slot_N node (floor height), world space.
func cage_slot(cage: Rig, index: int, cage_pos: Vector3, basis: Basis) -> Vector3:
	var node := cage.part("captive_slot_%d" % (index % 3)) if cage != null and cage.is_ready() else null
	if node != null and node.is_inside_tree():
		return node.global_position
	var floor_y := 0.12
	if cage != null and cage.socket("floor") != null:
		floor_y = (cage.socket("floor") as Vector3).y
	return game.ground(cage_pos.x, cage_pos.z) + basis * CAGE_SLOTS[index % 3] + Vector3.UP * floor_y

func gather_spot(cage_pos: Vector3, basis: Basis, index: int) -> Vector3:
	return cage_pos + basis * GATHER_SLOTS[index % 3]

func is_sitter(site_id: String, index: int) -> bool:
	return (index + int(game.content.site_number(site_id))) % 3 == 0

func update_captives(site_id: String, poi: Dictionary, anchor: Dictionary, now: float, delta: float, near: bool) -> void:
	var people: Array = poi.get("captives", [])
	var cage_pos: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	var cage_yaw := float(anchor.get("cage_yaw", 0.0))
	var basis := Basis(Vector3.UP, cage_yaw)
	var cage: Rig = rigs.get("cage_" + site_id)
	var walk: Dictionary = game.client.escort()
	for index in people.size():
		var person: Dictionary = people[index]
		var id := String(person.get("id", "%s_%d" % [site_id, index]))
		var state := String(person.get("state", "caged"))
		var arriving := arrival_until.has(id) and Time.get_ticks_msec() < int(arrival_until[id])
		if state == "home" and not arriving:
			if rigs.has(id):
				drop(id)
			continue
		var visual := captive_visual(person)
		var look := captive_variant(person)
		var fresh := not rigs.has(id)
		var actor := rig(id, ASSETS + "humans/lf_civilian_%s.glb" % visual, "", float(look.get("scale", 1.0)))
		if fresh:
			actor.variant = look
			actor.set_meta("occluder_height", 1.9)
		if choreo_owns(id):
			show_actor(actor, actor.position, near or arriving)
			continue
		var gather: Vector3 = gather_spot(cage_pos, basis, index)
		match state:
			"caged":
				var seat := cage_slot(cage, index, cage_pos, basis)
				place(id, actor, seat, cage_yaw + (0.35 * (index - 1)), delta, true, true)
				actor.play(CAGE_IDLES[0] if is_sitter(site_id, index) else CAGE_IDLES[1 + (index % 2)], 0.3)
			"freed":
				place(id, actor, gather, cage_yaw, delta)
				actor.play(["lf_civilian_wait", "lf_civilian_cage_stand", "Idle"], 0.3)
			"escorted":
				var walk_move: Variant = walk.get("move")
				if walk_move is Dictionary and String(walk.get("siteId", "")) == site_id:
					var sample := move_sample(walk_move, now, 1.7 + 1.5 * index)
					var tangent: Vector3 = sample.tangent
					var side := Vector3(tangent.z, 0, -tangent.x)
					if float(sample.behind) < 0.0:
						# Not yet their turn on the path: they wait at the gathering spot.
						place(id, actor, gather, PathMotion.yaw_of(tangent), delta)
						actor.play(["lf_civilian_wait", "Idle"], 0.3)
					else:
						var measured := place(id, actor, sample.position + side * [0.5, -0.5, 0.0][index % 3], PathMotion.yaw_of(tangent), delta)
						actor.locomote(float(sample.speed) if not sample.arrived else measured, TIRED_CLIPS if index == 2 else CIVILIAN_CLIPS)
				else:
					place(id, actor, gather, cage_yaw, delta)
					actor.play(["lf_civilian_wait", "Idle"], 0.3)
			"home":
				var home: Vector3 = game.target_position("lf_home_reception")
				place(id, actor, home + Vector3(-1.2 + 1.2 * index, 0, 1.4), PathMotion.yaw_of(-home), delta)
		if show_actor(actor, actor.position, near or arriving or state == "escorted"):
			markers.append({"position":actor.position + Vector3.UP * 1.3, "kind":"cage" if state == "caged" else "site", "site":site_id, "id":id})

# ------------------------------------------------------------------ guardians (original creature models)
func guardian_paths(spec: Dictionary) -> Array:
	# Product decision (2026-11-18): campaign guardians use the game's EXISTING creature
	# models — no new guardian art. 1022: the 1021 creatures v2 model, rig and clips
	# (CreatureVisuals, as the city and world hunts); data.creatureModels only when v2 is off.
	var species := String(spec.get("species", "tenerys"))
	var level := clampi(int(spec.get("level", 1)), 1, 3)
	var original := ""
	var models: Dictionary = game.main.data.get("creatureModels", {})
	if models.has(species):
		original = String(models[species][level - 1])
	var shown := CreatureVisuals.model_path(species, level, original)
	return [shown, original if shown != original else ""]

func update_guardian(site_id: String, poi: Dictionary, anchor: Dictionary, now: float, delta: float, near: bool) -> void:
	var spec: Dictionary = poi.get("guardian", {})
	var id := "guardian_" + site_id
	var state := String(spec.get("state", "alive"))
	var dying := choreo.has("death:" + site_id)
	if state == "defeated" and not dying:
		if rigs.has(id):
			drop(id)
		return
	var level := clampi(int(spec.get("level", 1)), 1, 3)
	var paths := guardian_paths(spec)
	var fresh := not rigs.has(id)
	# Same scale rule as ordinary hunts in landscape.gd (1.02 + 0.16 × level, creatures v2 display
	# scale), original materials.
	var species := String(spec.get("species", "tenerys"))
	var actor := rig(id, paths[0], paths[1], (1.02 + 0.16 * level) * CreatureVisuals.display_scale(species))
	if fresh:
		actor.painted = false
		actor.set_meta("occluder_height", 3.0)
		if CreatureVisuals.active(species):
			actor.creature_species = species
			actor.creature_level = level
	if actor.model != null and CreatureVisuals.owns(actor.model) and is_instance_valid(game.stage) and game.stage.camera != null:
		CreatureVisuals.update_lod(actor.model, game.stage.camera)
	var home: Vector3 = anchor.get("guardian", anchor.get("center", Vector3.ZERO))
	var approach: Vector3 = anchor.get("approach", home + Vector3(0, 0, 4))
	var squad_pos := squad_focus()
	var face := approach
	if squad_pos != Vector3.INF and squad_pos.distance_to(home) < 14.0:
		face = squad_pos
	if dying:
		menace.erase(site_id)
		show_actor(actor, actor.position, near)
		return
	var fight: Dictionary = game.client.battle()
	var in_battle: bool = not fight.is_empty() and String(fight.get("siteId", "")) == site_id and String(fight.get("species", "")) != "ancient_maw"
	if in_battle and engage_pending_for == site_id:
		engage_pending_for = ""  # the server's fight took over the optimistic charge
	var center: Vector3 = anchor.get("center", home)
	var out := Vector3(home.x - center.x, 0, home.z - center.z)
	var stand := home if in_battle or out.length_squared() < 0.01 else home + out.normalized() * 1.2
	var menacing := not in_battle and squad_pos != Vector3.INF and squad_member_count() > 0 \
		and Vector2(squad_pos.x - home.x, squad_pos.z - home.z).length() < MENACE_RANGE and engage_pending_for != site_id
	if not menacing:
		menace.erase(site_id)
	if in_battle:
		var lunge := guardian_battle_offset(fight, now, home)
		place(id, actor, home + lunge, PathMotion.yaw_of(battle_focus(fight) - home), delta)
		guardian_battle_pose(actor, fight, now)
	elif menacing:
		update_menace(site_id, actor, id, home, squad_pos, String(spec.get("species", "tenerys")), delta)
	else:
		var speed := place(id, actor, stand, PathMotion.yaw_of(face - stand), delta)
		if not actor.player or not actor.player.is_playing() or actor.current_id in ["Idle", "Walk", "Run", "stalk", "alert"]:
			actor.locomote(speed, CREATURE_CLIPS)
	update_menace_ring(site_id, actor)
	if show_actor(actor, actor.position, near):
		markers.append({"position":actor.position + Vector3.UP * 2.2, "kind":"guardian", "site":site_id, "id":id})

# ------------------------------------------------------------------ 1024: the creature menaces
## Build 1024 «Тенерис безобиден»: once the squad comes within MENACE_RANGE of a living guardian's lair
## (and no fight runs) the creature roars at once (Roar = tenerys howl), then stalks an arc in front of
## its lair facing the squad (stalk clip, speed-matched) and roars again every MENACE_ROAR_EVERY s with
## a red ground ring pulsing under it (telegraph). The mare backs away from it, alert (update_horse);
## the squad takes the guard stance facing it (squad_pose). Presentation only.
const MENACE_RANGE := 18.0
const MENACE_ROAR_EVERY := 6.5
const MENACE_CLIPS := {"idle":["alert", "Alert", "Idle"], "walk":["stalk", "Walk"], "run":["Run"], "walk_speed":1.1, "run_speed":4.0}
var menace: Dictionary = {}
var menace_rings: Dictionary = {}
## A press on «Атаковать» (optimistic): the menace yields to the charge before the server answers.
var engage_pending_for := ""

func update_menace(site_id: String, actor: Rig, id: String, home: Vector3, squad_pos: Vector3, species: String, delta: float) -> void:
	var ticks := Time.get_ticks_msec()
	if not menace.has(site_id):
		menace[site_id] = {"since": ticks, "next_roar": ticks, "roar_until": 0, "species": species}
	var m: Dictionary = menace[site_id]
	var to_squad := Vector3(squad_pos.x - home.x, 0, squad_pos.z - home.z)
	var dir := to_squad.normalized() if to_squad.length_squared() > 0.01 else Vector3.BACK
	var side := Vector3(dir.z, 0, -dir.x)
	if ticks >= int(m.next_roar):
		var length := actor.clip_length(["Roar", "Alert"]) if actor.is_ready() else 1.6
		m.roar_until = ticks + int(1000.0 * clampf(length, 0.9, 2.6))
		m.next_roar = ticks + int(1000.0 * (MENACE_ROAR_EVERY + randf() * 1.5))
		m.roars = int(m.get("roars", 0)) + 1
		actor.play(["Roar", "Alert", "Idle"], 0.15, true)
		game.creature_roared.emit(site_id, species)
		game.audio.play_cue("fr_distant_rumble", 10.0)
	var roaring := ticks < int(m.roar_until)
	var phase := (ticks - int(m.since)) / 1000.0
	var stalk := home + dir * 0.9 + side * sin(phase * 0.85) * 1.7
	var state: Dictionary = motion.get(id, {})
	var target: Vector3 = state.get("position", stalk) if roaring else stalk
	var speed := place(id, actor, target, PathMotion.yaw_of(squad_pos - actor.position), delta)
	if roaring:
		if actor.current_id not in ["Roar", "Alert"]:
			actor.play(["Roar", "Alert", "Idle"], 0.15)
	else:
		actor.locomote(maxf(speed, 0.0), MENACE_CLIPS)

## The red ring under a roaring creature (one flat torus per site, alpha pulse; hidden otherwise).
func update_menace_ring(site_id: String, actor: Rig) -> void:
	var ring: MeshInstance3D = menace_rings.get(site_id)
	var m: Dictionary = menace.get(site_id, {})
	var ticks := Time.get_ticks_msec()
	var strength := 0.0
	if not m.is_empty() and actor.visible:
		var left := int(m.roar_until) - ticks
		if left > 0:
			strength = clampf(left / 400.0, 0.0, 1.0) * (0.65 + 0.35 * sin(ticks / 70.0))
	if strength <= 0.0:
		if ring != null and is_instance_valid(ring):
			ring.visible = false
		return
	if ring == null or not is_instance_valid(ring):
		ring = MeshInstance3D.new()
		ring.name = "MenaceRing_" + site_id
		var torus := TorusMesh.new()
		torus.inner_radius = 1.9
		torus.outer_radius = 2.25
		torus.rings = 32
		torus.ring_segments = 6
		ring.mesh = torus
		ring.scale = Vector3(1.0, 0.08, 1.0)
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.albedo_color = Color(1.0, 0.25, 0.1, 0.8)
		material.no_depth_test = false
		ring.material_override = material
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.set_meta("no_canopy_fade", true)
		ring.set_meta("fog_exempt", true)
		root.add_child(ring)
		menace_rings[site_id] = ring
	ring.visible = true
	ring.position = actor.position + Vector3.UP * 0.15
	(ring.material_override as StandardMaterial3D).albedo_color.a = 0.85 * strength

## Site whose menacing creature stands within `reach` m of p ("" when none).
func menace_near(p: Vector3, reach: float) -> String:
	for site_id in menace:
		var creature: Rig = rigs.get("guardian_" + String(site_id))
		if creature != null and is_instance_valid(creature) and Vector2(creature.position.x - p.x, creature.position.z - p.z).length() <= reach:
			return String(site_id)
	return ""

# ------------------------------------------------------------------ battles (server timeline)
func battle_elapsed(fight: Dictionary, now: float) -> float:
	return (now - float(fight.get("startedAt", now))) / 1000.0

func timeline(fight: Dictionary) -> Array:
	return fight.get("timeline", [])

## iPhone hot path (battle): the fight timeline is indexed once by event time; the per-frame pose / HP / FX
## queries read only the events of their time window (binary search) instead of scanning every event.
var _tl_source: Array = []
var _tl_times := PackedFloat32Array()
var _tl_events: Array = []
var _tl_hp_times := PackedFloat32Array()
var _tl_hp_values := PackedFloat32Array()

func _index_timeline(fight: Dictionary) -> void:
	var events: Array = timeline(fight)
	if is_same(events, _tl_source):
		return
	_tl_source = events
	var order: Array = events.duplicate()
	order.sort_custom(func(a, b) -> bool: return float(a.get("t", 0.0)) < float(b.get("t", 0.0)))
	_tl_events = order
	_tl_times = PackedFloat32Array()
	_tl_hp_times = PackedFloat32Array()
	_tl_hp_values = PackedFloat32Array()
	for event in order:
		_tl_times.append(float(event.get("t", 0.0)))
		if event.has("hp"):
			_tl_hp_times.append(float(event.get("t", 0.0)))
			_tl_hp_values.append(float(event.hp))

## Events with from_t <= t <= to_t, in time order.
func timeline_window(fight: Dictionary, from_t: float, to_t: float) -> Array:
	_index_timeline(fight)
	var lo := _tl_times.bsearch(from_t, true)
	var hi := _tl_times.bsearch(to_t, false)
	return _tl_events.slice(lo, hi) if hi > lo else []

## Last event hp at or before t (or `fallback`).
func timeline_hp(fight: Dictionary, t: float, fallback: float) -> float:
	_index_timeline(fight)
	var i := _tl_hp_times.bsearch(t, false) - 1
	return _tl_hp_values[i] if i >= 0 else fallback

func latest_event(fight: Dictionary, elapsed: float, actor: String, window: float, type := "") -> Dictionary:
	var best := {}
	for event in timeline_window(fight, elapsed - window, elapsed):
		var at := float(event.get("t", 0.0))
		if at > elapsed or elapsed - at > window:
			continue
		if not actor.is_empty() and String(event.get("actor", "")) != actor:
			continue
		if not type.is_empty() and String(event.get("type", "")) != type:
			continue
		if best.is_empty() or at >= float(best.get("t", 0.0)):
			best = event
	return best

## Build 1024 «у атаки Тенериса нет анимации»: the guardian fight reads on screen. The squad charges
## from its guard line onto the melee spots (CHARGE_S, jog), each squad volley is a lunge with the
## sword (lf_soldier_attack, contact marker 0.65 s → sparks + fight_hit), the creature strikes back
## with a lunge (attack_claw / attack_bite; its ability telegraphed by a roar), recoils on hits, the
## struck soldier reels (lf_soldier_hit, knocked back), the knocked-out representatives stay wounded
## (lf_soldier_help after the fight); the creature dies on the server's death event, or roars over a
## retreating squad on a defeat. Every beat comes from the server timeline (startedAt + t).
const MELEE := 2.4
const CHARGE_FROM := 2.8
const CHARGE_S := 1.0
var fight_fx_key := ""
var fight_fx_t := -1.0
var fight_wounded: Dictionary = {}

func battle_focus(fight: Dictionary) -> Vector3:
	var site_id := String(fight.get("siteId", ""))
	var anchor: Dictionary = game.site_anchor(site_id)
	var enemy: Vector3 = anchor.get("guardian", Vector3.ZERO)
	var approach: Vector3 = anchor.get("approach", enemy + Vector3(0, 0, 4))
	var away := Vector3(approach.x - enemy.x, 0, approach.z - enemy.z)
	away = away.normalized() if away.length_squared() > 0.01 else Vector3.BACK
	return enemy + away * MELEE

## The creature's own motion in the fight: a lunge at the squad on each strike, a recoil on hits.
func guardian_battle_offset(fight: Dictionary, now: float, home: Vector3) -> Vector3:
	var elapsed := battle_elapsed(fight, now)
	var toward := battle_focus(fight) - home
	toward.y = 0
	toward = toward.normalized() if toward.length_squared() > 0.01 else Vector3.BACK
	var amount := 0.0
	for event in timeline_window(fight, elapsed - 1.0, elapsed):
		var at := float(event.get("t", 0.0))
		var kind := String(event.get("type", ""))
		if String(event.get("actor", "")) == "guardian" and kind in ["attack", "ability"]:
			amount += 1.1 * sin(PI * clampf((elapsed - at) / 0.9, 0.0, 1.0))
		elif String(event.get("actor", "")) == "squad" and kind == "hit":
			amount -= 0.35 * sin(PI * clampf((elapsed - at) / 0.45, 0.0, 1.0))
	return toward * amount

func guardian_battle_pose(actor: Rig, fight: Dictionary, now: float) -> void:
	var elapsed := battle_elapsed(fight, now)
	var ending := float(fight.get("endsAt", now)) <= now
	for event in timeline_window(fight, -1.0e9, elapsed):
		if String(event.get("type", "")) == "death" and String(event.get("actor", "")) == "guardian" and float(event.get("t", 0.0)) <= elapsed:
			actor.pose_at(["Death"], elapsed - float(event.t))
			return
	if ending and String(fight.get("outcome", "")) == "victory":
		actor.hold_end(["Death"])
		return
	if ending:
		# The squad lost or withdrew: the creature roars over the field.
		actor.play(["Roar", "Alert", "Idle"], 0.2)
		return
	var own := latest_event(fight, elapsed, "guardian", 1.3)
	if not own.is_empty() and String(own.get("type", "")) in ["attack", "ability", "telegraph"]:
		var kind := String(own.type)
		var clip: Array = ["Roar", "Alert", "Attack"]
		if kind == "attack":
			clip = ["attack_claw", "Attack"] if int(own.get("order", 0)) % 2 == 0 else ["Attack"]
		elif kind == "ability":
			clip = ["attack_pounce", "Attack"]
		actor.pose_at(clip, elapsed - float(own.get("t", 0.0)))
		return
	var struck := latest_event(fight, elapsed, "squad", 0.6, "hit")
	if not struck.is_empty():
		actor.pose_at(["Hit"], maxf(0.0, elapsed - float(struck.get("t", 0.0))))
		return
	if elapsed < 1.2:
		actor.pose_at(["Roar", "Alert", "Idle"], elapsed)
		return
	actor.play(["alert", "Idle"], 0.25)

## Which representatives the guardian's hits knock out (wounded): the server's knocked units, mapped
## onto the three soldiers in hit order (index 2, then 1); none while every unit stands.
func wounded_members(fight: Dictionary, elapsed: float) -> Dictionary:
	var wounded := {}
	var hits := 0
	for event in timeline_window(fight, -1.0e9, elapsed):
		if String(event.get("actor", "")) == "guardian" and String(event.get("type", "")) == "hit":
			var knocked: Variant = event.get("knocked", {})
			if knocked is Dictionary and not (knocked as Dictionary).is_empty():
				wounded[[2, 1, 0][mini(hits, 2)]] = true
				hits += 1
	return wounded

func battle_member_pose(index: int, fight: Dictionary, now: float) -> Dictionary:
	var site_id := String(fight.get("siteId", ""))
	var boss_fight := String(fight.get("species", "")) == "ancient_maw"
	var enemy: Vector3 = game.target_position("lf_boss_ancient_maw") if boss_fight else game.site_anchor(site_id).get("guardian", Vector3.ZERO)
	var approach: Vector3 = enemy + Vector3(sin(deg_to_rad(arena_facing_deg())), 0, cos(deg_to_rad(arena_facing_deg()))) * 10.0 if boss_fight else game.site_anchor(site_id).get("approach", enemy + Vector3(0, 0, 4))
	var away := (approach - enemy)
	away.y = 0
	away = away.normalized() if away.length_squared() > 0.01 else Vector3.BACK
	# boss fight: a tight wedge inside the entrance gap — at ±24° the wing soldiers stood behind the entrance
	# rocks from the city camera (qa_forest_arena_camera: 2-17 % of their silhouette visible)
	var distance: float = ([BOSS_FIGHT_DISTANCE, BOSS_FIGHT_DISTANCE - 1.2, BOSS_FIGHT_DISTANCE - 1.2][index]) if boss_fight else MELEE + [0.0, 0.35, 0.35][index]
	var spread: float = ([0.0, -0.17, 0.17] if boss_fight else [0.0, -0.62, 0.62])[index]
	var p := enemy + away.rotated(Vector3.UP, spread) * distance
	var yaw := PathMotion.yaw_of(enemy - p)
	var elapsed := battle_elapsed(fight, now)
	var ended := float(fight.get("endsAt", now)) <= now
	if not boss_fight:
		var wounded := wounded_members(fight, elapsed)
		if ended:
			if String(fight.get("outcome", "")) != "victory":
				# Defeat / withdrawal: back to the guard line, shields up.
				return {"position":enemy + away.rotated(Vector3.UP, spread) * (distance + CHARGE_FROM + 1.5), "yaw":yaw, "guard":true}
			if wounded.has(index):
				return {"position":p + away * 0.6, "yaw":yaw, "clip":["lf_soldier_help", "lf_soldier_guard", "Idle"]}
			return {"position":p, "yaw":yaw, "clip":["lf_soldier_guard", "lf_soldier_idle", "Idle"]}
		if elapsed < CHARGE_S:
			# The charge: from the guard line onto the melee spot (jog, speed-matched).
			var from := enemy + away.rotated(Vector3.UP, spread * 0.8) * (distance + CHARGE_FROM)
			var f := smoothstep(0.0, CHARGE_S, elapsed)
			return {"position":from.lerp(p, f), "yaw":yaw, "moving":true, "speed":CHARGE_FROM / CHARGE_S * 1.2}
		for event in timeline_window(fight, -1.0e9, elapsed):
			if String(event.get("type", "")) == "death" and String(event.get("actor", "")) == "squad":
				return {"position":p, "yaw":yaw, "clip":["lf_soldier_death", "Death"], "at":elapsed - float(event.get("t", 0.0))}
	elif ended:
		return {"position":p, "yaw":yaw, "clip":["lf_soldier_guard", "lf_soldier_idle", "Idle"]}
	var hit_order := 0
	for event in timeline_window(fight, elapsed - 1.25, elapsed):
		var at := float(event.get("t", 0.0))
		if at > elapsed or elapsed - at > 1.25:
			continue
		var who := int(event.get("member", event.get("index", -1)))
		var actor_kind := String(event.get("actor", ""))
		if actor_kind == "squad" and String(event.get("type", "")) == "attack" and (who == index or (who < 0 and (int(at * 10.0) + index) % 3 != 2)):
			var lunge := (0.5 if boss_fight else 0.9) * sin(PI * clampf((elapsed - at) / 1.2, 0.0, 1.0))
			return {"position":p + (enemy - p).normalized() * lunge, "yaw":yaw, "clip":["lf_soldier_attack", "Sword_Drill", "Attack"], "at":elapsed - at}
		if actor_kind in ["guardian", "boss"] and String(event.get("type", "")) == "hit" and (who == index or (who < 0 and index == (int(event.get("order", int(at))) + hit_order) % 3)) and elapsed - at < 0.6:
			var reel := 0.0 if boss_fight else 0.5 * sin(PI * clampf((elapsed - at) / 0.6, 0.0, 1.0))
			return {"position":p - (enemy - p).normalized() * reel, "yaw":yaw, "clip":["lf_soldier_hit", "Hit"], "at":elapsed - at}
	return {"position":p, "yaw":yaw, "clip":["lf_soldier_guard", "lf_soldier_idle", "Shield_Block", "Idle"]}

## Sparks and sound hooks on the fight's contact moments (each timeline event once per fight).
func update_fight_fx(now: float) -> void:
	var fight: Dictionary = game.client.battle()
	if fight.is_empty() or String(fight.get("species", "")) == "ancient_maw":
		return
	var key := String(fight.get("reportId", str(fight.get("startedAt", 0))))
	var elapsed := battle_elapsed(fight, now)
	if key != fight_fx_key:
		fight_fx_key = key
		fight_fx_t = elapsed - 0.05 if elapsed > 0.5 else -1.0
	if elapsed <= fight_fx_t:
		return
	var site_id := String(fight.get("siteId", ""))
	var creature: Rig = rigs.get("guardian_" + site_id)
	for event in timeline_window(fight, fight_fx_t + 0.0001, elapsed):
		var kind := String(event.get("type", ""))
		var who := String(event.get("actor", ""))
		if kind == "hit" and who == "squad":
			if creature != null and creature.visible:
				game.fx.burst_world(creature.position + Vector3.UP * 0.6, "hit")
			game.fight_hit.emit(site_id, "squad", "guardian")
		elif kind == "hit" and who == "guardian":
			var struck: Rig = rigs.get("squad_%d" % (int(event.get("order", 0)) % maxi(1, squad_member_count())))
			if struck != null and struck.visible:
				game.fx.burst_world(struck.position + Vector3.UP * 0.4, "hit")
			game.fight_hit.emit(site_id, "guardian", "squad")
		elif kind in ["telegraph", "ability"] and who == "guardian":
			game.creature_roared.emit(site_id, String(fight.get("species", "")))
		elif kind == "death":
			game.fight_hit.emit(site_id, "death", who)
	fight_fx_t = elapsed

func update_battle_hud(now: float) -> void:
	var fight: Dictionary = game.client.battle()
	if fight.is_empty() or String(fight.get("outcome", "pending")) != "pending":
		game.hud.hide_battle()
		return
	var species := String(fight.get("species", ""))
	var boss_fight := species == "ancient_maw"
	var hp := 0.0
	var hp_max := 1.0
	if boss_fight:
		hp = float(adv.get("boss", {}).get("hp", 0))
		hp_max = float(adv.get("boss", {}).get("hpMax", 1))
	else:
		var guardian: Dictionary = game.client.poi(String(fight.get("siteId", ""))).get("guardian", {})
		hp = float(guardian.get("hp", 0))
		hp_max = float(guardian.get("hpMax", 1))
	var elapsed := battle_elapsed(fight, now)
	hp = timeline_hp(fight, elapsed, hp)
	var left := maxi(0, ceili((float(fight.get("endsAt", now)) - now) / 1000.0))
	var title: String = game.content.text("site.guardian", {"name":game.content.species_name(species), "level":int(fight.get("level")) if fight.get("level") != null else 1})
	var clock := "%d:%02d" % [left / 60, left % 60]
	var sub := ""
	if boss_fight:
		var phase := String(adv.get("boss", {}).get("phase", "hunt"))
		var shown := latest_event(fight, elapsed, "boss", 9999.0, "phase")
		if not shown.is_empty():
			phase = String(shown.get("phase", phase))
		title = "%s · %s" % [game.content.species_name(species), game.content.text("boss.phase." + phase)]
		sub = telegraphs.current_warning()
	game.hud.show_battle(title, hp, hp_max, sub, true, clock)

func on_battle_report(_report_id: String) -> void:
	last_battle = game.client.battle()

# ------------------------------------------------------------------ boss
## Fight framing: the camera target between the boss and the squad's fighting spot (the squad
## stands BOSS_FIGHT_DISTANCE m before the boss on the entrance axis), zoom 32 — inside the arena
## the server revealed along the squad's route; the panel stays above the boss.
const BOSS_FRAME_ZOOM := 32.0
var boss_framed_for := ""

func boss_fight_frame() -> Vector3:
	var arena: Vector3 = game.target_position("lf_boss_ancient_maw")
	if arena == Vector3.INF:
		return Vector3.INF
	var squad_spot := boss_gap_point(BOSS_FIGHT_DISTANCE)
	return arena.lerp(squad_spot, 0.5)

func update_boss(now: float, delta: float) -> void:
	var boss_state: Dictionary = adv.get("boss", {})
	var state := String(boss_state.get("state", "locked"))
	var arena: Vector3 = game.target_position("lf_boss_ancient_maw")
	var known: bool = state != "locked" or not game.client.poi("lf_boss_ancient_maw").is_empty()
	if not known or arena == Vector3.INF:
		if rigs.has("boss"):
			rigs.boss.set_active(false)
		telegraphs.clear()
		return
	var fresh := not rigs.has("boss")
	var actor := rig("boss", BOSS_GLB, "", boss_scale)
	if fresh:
		actor.lod_scale = BOSS_LOD_SCALE
		actor.set_meta("occluder_height", 7.0)
	var fight: Dictionary = game.client.battle()
	var boss_fight: bool = not fight.is_empty() and String(fight.get("species", "")) == "ancient_maw"
	var squad_pos := squad_focus()
	var entrance_yaw := deg_to_rad(arena_facing_deg())
	var wanted := entrance_yaw
	if boss_fight or (squad_pos != Vector3.INF and Vector2(squad_pos.x - arena.x, squad_pos.z - arena.z).length() < 34.0):
		if squad_pos != Vector3.INF and Vector2(squad_pos.x - arena.x, squad_pos.z - arena.z).length() > 1.0:
			wanted = PathMotion.yaw_of(squad_pos - arena)
	var state_motion: Dictionary = motion.get("boss", {})
	var current_yaw := float(state_motion.get("yaw", wanted))
	place("boss", actor, arena, current_yaw if not state_motion.is_empty() else wanted, delta)
	var elapsed := battle_elapsed(fight, now) if boss_fight else 0.0
	# Fight camera (art/08): once per boss battle the city camera flies to frame the revealed arena
	# — boss above the middle (below the compact panel), squad and entrance banners below.
	if boss_fight and String(fight.get("outcome", "pending")) == "pending":
		var report := String(fight.get("reportId", ""))
		if report != boss_framed_for:
			boss_framed_for = report
			if game.world != null and game.world.has_method("focus_on"):
				game.world.focus_on(boss_fight_frame(), BOSS_FRAME_ZOOM)
	var defeated := state == "defeated" or (boss_fight and String(fight.get("outcome", "")) == "victory" and float(fight.get("endsAt", 0)) <= now)
	var death_event := latest_event(fight, elapsed, "boss", 9999.0, "death") if boss_fight else {}
	if not death_event.is_empty():
		var since := elapsed - float(death_event.get("t", 0.0))
		if since < actor.clip_length(["lf_boss_death"]):
			actor.pose_at(["lf_boss_death", "Death"], since)
		else:
			actor.hold_end(["lf_boss_death", "Death"])
		telegraphs.clear()
	elif defeated:
		actor.hold_end(["lf_boss_death", "Death"])
		telegraphs.clear()
	elif boss_fight and String(fight.get("outcome", "pending")) == "pending":
		var attack: Dictionary = telegraphs.update_from_battle(fight, elapsed, actor.position, float(motion.get("boss", {}).get("yaw", 0.0)), squad_pos)
		boss_battle_pose(actor, fight, elapsed, attack)
		# The boss squares up to the squad between attacks (lane direction is committed by
		# the server window; the decal shows it).
		if attack.is_empty() and not turns.has("boss"):
			var diff := angle_difference(current_yaw, wanted)
			if absf(diff) > deg_to_rad(30.0):
				start_turn("boss", actor, diff, "lf_boss_turn_left", "lf_boss_turn_right")
		run_turn("boss", actor)
	else:
		telegraphs.clear()
		if run_turn("boss", actor):
			pass
		elif boss_awake_ms >= 0.0 and now - boss_awake_ms < actor.clip_length(["lf_boss_awaken"]) * 1000.0:
			actor.pose_at(["lf_boss_awaken", "Roar"], (now - boss_awake_ms) / 1000.0)
		else:
			var diff := angle_difference(current_yaw, wanted)
			if absf(diff) > deg_to_rad(30.0) and start_turn("boss", actor, diff, "lf_boss_turn_left", "lf_boss_turn_right"):
				pass
			else:
				if absf(diff) > 0.001:
					# Residual (< 30°): settle slowly without a clip.
					state_motion = motion.get("boss", {})
					state_motion.yaw = PathMotion.turn_towards(current_yaw, wanted, 0.8, delta)
					actor.rotation.y = state_motion.yaw
				actor.play(["lf_boss_idle", "Idle"], 0.3)
	if show_actor(actor, actor.position):
		markers.append({"position":actor.position + Vector3.UP * 3.0, "kind":"boss", "id":"boss"})
		tags.append({"position":actor.position + Vector3.UP * 6.5 * boss_scale, "text":game.content.species_name("ancient_maw"), "kind":"boss"})

## Boss clip for the server timeline at `elapsed`: phase change → stagger then phase_roar;
## the telegraphed attack (clip local time = schedule local time, so active_begin lines up
## with the decal's active window); a squad volley landing in the recovery → hit.
func boss_battle_pose(actor: Rig, fight: Dictionary, elapsed: float, attack: Dictionary) -> void:
	var phase := latest_event(fight, elapsed, "boss", 3.9, "phase")
	if not phase.is_empty() and float(phase.get("t", 0.0)) > 0.05:
		var since := elapsed - float(phase.get("t", 0.0))
		if since < 1.05:
			actor.pose_at(["lf_boss_stagger", "Hit"], since)
		else:
			actor.pose_at(["lf_boss_phase_roar", "Roar"], since - 1.05, 0.3)
		return
	if not attack.is_empty():
		var name := "lf_boss_" + String(attack.attack)
		var local := float(attack.local)
		var spec := actor.clip_meta(name)
		var recovery := float(spec.get("markers", {}).get("active_end", spec.get("markers", {}).get("wave_2_end", 99.0)))
		var struck := latest_event(fight, elapsed, "squad", 0.55, "hit")
		if local > recovery + 0.2 and not struck.is_empty() and float(struck.get("t", 0.0)) - (elapsed - local) > recovery:
			actor.pose_at(["lf_boss_hit", "Hit"], elapsed - float(struck.get("t", 0.0)))
			return
		actor.pose_at([name, "Attack"], local)
		return
	var struck_idle := latest_event(fight, elapsed, "squad", 0.55, "hit")
	if not struck_idle.is_empty():
		actor.pose_at(["lf_boss_hit", "Hit"], elapsed - float(struck_idle.get("t", 0.0)))
		return
	actor.play(["lf_boss_idle", "Idle"], 0.3)

func on_boss_started() -> void:
	boss_awake_ms = now_ms()
	var actor: Rig = rigs.get("boss")
	if actor != null and is_instance_valid(actor):
		turns.erase("boss")
		actor.play(["lf_boss_awaken", "Roar"], 0.2, true)

func on_boss_phase(_phase_id: String) -> void:
	game.audio.play_cue("fr_distant_rumble", 10.0)

# ------------------------------------------------------------------ reward pile at home (lf_props_supplies)
## Escrowed rewards waiting for «Забрать» stand as a supply pile at the home reception: one
## supply_<item> group per resource with a pending amount; claimed → the pile is gone.
func update_supplies() -> void:
	var pending: Dictionary = adv.get("escrow", {}).get("pending", {})
	var any := false
	for key in pending:
		any = any or int(pending[key]) > 0
	var home: Vector3 = game.target_position("lf_home_reception")
	if not any or home == Vector3.INF:
		if rigs.has("supplies_home"):
			rigs.supplies_home.set_active(false)
		return
	var pile := rig("supplies_home", SUPPLIES_GLB, "", 1.0, props_parent)
	var spot := home + Vector3(-3.4, 0, 0.6)
	pile.position = game.ground(spot.x, spot.z) + Vector3.UP * 0.35
	pile.rotation.y = deg_to_rad(40.0)
	if pile.is_ready():
		var signature := JSON.stringify(pending)
		if signature != supplies_signature:
			supplies_signature = signature
			for resource in SUPPLY_ITEMS:
				for item in SUPPLY_ITEMS[resource]:
					var node := pile.part(String(item))
					if node != null:
						node.visible = int(pending.get(resource, 0)) > 0
	pile.set_active(pile.is_ready() and visible_in_view(pile.position))

# ------------------------------------------------------------------ beacon, route ribbon, tags, picking
func set_beacon(target_id: String) -> void:
	beacon_target = target_id

func update_beacon(delta: float) -> void:
	if beacon == null or not is_instance_valid(beacon):
		beacon = build_beacon()
		beacon.set_meta("no_canopy_fade", true)
		beacon.set_meta("fog_exempt", true)
		root.add_child(beacon)
	if beacon_target.is_empty():
		beacon.hide()
		return
	var p: Vector3 = game.target_position(beacon_target)
	if p == Vector3.INF or not game.fog_clear(p) and not beacon_target.begins_with("lf_horse"):
		beacon.hide()
		return
	beacon.show()
	beacon.position = beacon.position.lerp(game.ground(p.x, p.z), 1.0 - exp(-8.0 * delta)) if beacon.position.distance_to(p) < 30.0 else game.ground(p.x, p.z)
	# Sized for the overview; up close it shrinks so it does not hide the glade.
	beacon.scale = Vector3.ONE * clampf(float(game.stage.camera_zoom) / 40.0, 0.45, 1.3)
	var gem: Node3D = beacon.get_node("Gem")
	var t := Time.get_ticks_msec() / 1000.0
	gem.position.y = 3.4 + 0.25 * sin(t * 2.2)
	gem.rotation.y = t * 1.3

func build_beacon() -> Node3D:
	var node := Node3D.new()
	node.name = "TargetBeacon"
	var ring := MeshInstance3D.new()
	ring.name = "Ring"
	var plane := PlaneMesh.new()
	plane.size = Vector2(7.0, 7.0)
	ring.mesh = plane
	ring.position.y = 0.12
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add, shadows_disabled;
uniform vec4 tint : source_color = vec4(1.0, 0.78, 0.32, 1.0);
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float pulse = fract(TIME * 0.45);
	float ring = smoothstep(0.06, 0.0, abs(r - 0.62)) * 0.9;
	float wave = smoothstep(0.08, 0.0, abs(r - (0.2 + pulse * 0.78))) * (1.0 - pulse);
	float core = smoothstep(0.35, 0.0, r) * 0.18;
	float a = clamp(ring + wave * 0.8 + core, 0.0, 1.0) * step(r, 1.0);
	ALBEDO = tint.rgb;
	ALPHA = a * tint.a;
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	ring.material_override = material
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.add_child(ring)
	var gem := MeshInstance3D.new()
	gem.name = "Gem"
	var cone := CylinderMesh.new()
	cone.top_radius = 0.0
	cone.bottom_radius = 0.55
	cone.height = 0.8
	cone.radial_segments = 4
	cone.rings = 1
	gem.mesh = cone
	var lower := MeshInstance3D.new()
	var lower_cone := CylinderMesh.new()
	lower_cone.top_radius = 0.55
	lower_cone.bottom_radius = 0.0
	lower_cone.height = 1.1
	lower_cone.radial_segments = 4
	lower_cone.rings = 1
	lower.mesh = lower_cone
	lower.position.y = -0.95
	var gold := StandardMaterial3D.new()
	gold.albedo_color = Color("#ffcf6a")
	gold.emission_enabled = true
	gold.emission = Color("#ffb83d")
	gold.emission_energy_multiplier = 1.6
	gold.metallic = 0.4
	gold.roughness = 0.35
	gem.material_override = gold
	lower.material_override = gold
	gem.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lower.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	gem.add_child(lower)
	node.add_child(gem)
	return node

func update_ribbon() -> void:
	var squad: Dictionary = game.client.squad()
	var move: Variant = squad.get("move")
	var walk_move: Variant = game.client.escort().get("move")
	var source: Variant = move if move is Dictionary else (walk_move if walk_move is Dictionary and String(game.client.escort().get("state", "")) == "walking" else null)
	if not source is Dictionary:
		if is_instance_valid(ribbon):
			ribbon.hide()
		ribbon_signature = ""
		return
	var signature := "%s|%s" % [str(source.get("departAt", 0)), str(source.get("arriveAt", 0))]
	if ribbon == null or not is_instance_valid(ribbon):
		ribbon = build_ribbon()
		ribbon.set_meta("no_canopy_fade", true)
		ribbon.set_meta("fog_exempt", true)
		root.add_child(ribbon)
		ribbon_signature = ""
	ribbon.show()
	if signature != ribbon_signature:
		ribbon_signature = signature
		var route := PathMotion.build(visual_path(source.get("path", [])))
		var total := float(route.total)
		var count := clampi(int(total / 1.15), 2, 400)
		var multimesh := ribbon.multimesh
		multimesh.instance_count = count
		for i in count:
			var d := total * float(i) / float(count - 1)
			var sample := PathMotion.sample(route, d)
			var p: Vector3 = game.ground(sample.position.x, sample.position.z) + Vector3.UP * 0.32
			multimesh.set_instance_transform(i, Transform3D(Basis.IDENTITY, p))
			multimesh.set_instance_custom_data(i, Color(d / maxf(total, 0.01), d, fposmod(float(i) * 0.6180339, 1.0), 0))
		var seconds := maxf(0.5, (float(source.get("arriveAt", 0)) - float(source.get("departAt", 0))) / 1000.0)
		(ribbon.material_override as ShaderMaterial).set_shader_parameter("speed", total / seconds)
	var progress := 0.0
	var sample_now := move_sample(source, now_ms())
	progress = float(sample_now.distance)
	(ribbon.material_override as ShaderMaterial).set_shader_parameter("travelled", progress)

## Faint golden dots along the authored route to the next suggested target (art/07 panel 3).
func set_preview(target_id: String) -> void:
	preview_target = target_id

func update_preview() -> void:
	var squad: Dictionary = game.client.squad()
	var from_node := String(squad.get("node", ""))
	var show_it := preview_target != "" and not (squad.get("move") is Dictionary) and from_node != "" \
		and from_node.get_slice(":", 0) != preview_target.get_slice(":", 0)
	var signature := "%s>%s" % [from_node.get_slice(":", 0), preview_target.get_slice(":", 0)]
	if not show_it:
		if is_instance_valid(preview):
			preview.hide()
		return
	if preview == null or not is_instance_valid(preview):
		preview = build_ribbon()
		preview.name = "RoutePreview"
		preview.set_meta("no_canopy_fade", true)
		preview.set_meta("fog_exempt", true)
		(preview.material_override as ShaderMaterial).set_shader_parameter("dim", 0.55)
		(preview.material_override as ShaderMaterial).set_shader_parameter("travelled", -1.0)
		root.add_child(preview)
		preview_signature = ""
	preview.show()
	if signature == preview_signature:
		return
	preview_signature = signature
	# atlas v2: the trail network's shortest walk (world trail_path, same no-transit rule as the
	# server graph); a straight hint only when the world cannot answer.
	var value: Variant = game.world_call("trail_path", [from_node, preview_target])
	var points: Array = []
	if value is PackedVector3Array and value.size() >= 2:
		for p in value:
			points.append(p)
	else:
		var a: Vector3 = game.target_position(from_node)
		var b: Vector3 = game.target_position(preview_target)
		if a == Vector3.INF or b == Vector3.INF:
			preview.hide()
			return
		points = [a, b]
	var route := PathMotion.build(points)
	var total := float(route.total)
	var count := clampi(int(total / 1.4), 2, 400)
	var multimesh := preview.multimesh
	multimesh.instance_count = count
	for i in count:
		var d := total * float(i) / float(count - 1)
		var sample := PathMotion.sample(route, d)
		var p: Vector3 = game.ground(sample.position.x, sample.position.z) + Vector3.UP * 0.3
		multimesh.set_instance_transform(i, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * 0.8), p))
		multimesh.set_instance_custom_data(i, Color(d / maxf(total, 0.01), d, fposmod(float(i) * 0.6180339, 1.0), 0))

## Route dots (art/07 panel 3) + P1.6 walked-route sparkles: camera-facing star sprites along the
## move path. Ahead of the walkers they pulse calmly (gold dots); every point the walkers pass
## twinkles a moment and fades out over ~3.5 s (age = distance behind / walk speed). Additive,
## one layer, ≤ 400 sprites of 0.55 m: well inside the alpha-overdraw budget.
func build_ribbon() -> MultiMeshInstance3D:
	var node := MultiMeshInstance3D.new()
	node.name = "RouteDots"
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.use_custom_data = true
	var sprite := QuadMesh.new()
	sprite.size = Vector2(0.55, 0.55)
	multimesh.mesh = sprite
	node.multimesh = multimesh
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, shadows_disabled, cull_disabled;
uniform float travelled = 0.0;
uniform float dim = 1.0;
uniform float speed = 2.0;
uniform float fade_seconds = 3.5;
varying float along;
varying float seed;
void vertex() {
	along = INSTANCE_CUSTOM.g;
	seed = INSTANCE_CUSTOM.b;
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float core = exp(-dot(p, p) * 10.0);
	float rays = exp(-abs(p.x) * 16.0) * exp(-abs(p.y) * 2.8) + exp(-abs(p.y) * 16.0) * exp(-abs(p.x) * 2.8);
	float ahead = step(travelled, along);
	float age = max(travelled - along, 0.0) / max(speed, 0.1);
	float spark = (1.0 - ahead) * exp(-age * 2.2 / fade_seconds) * smoothstep(0.0, 0.25, age);
	float twinkle = 0.5 + 0.5 * sin(TIME * (5.0 + seed * 6.0) + seed * 41.0);
	float calm = ahead * (0.55 + 0.45 * sin(along * 1.7 - TIME * 5.0)) * 0.5;
	float shape = mix(core, core * 0.8 + rays * 0.7, 1.0 - ahead);
	ALBEDO = mix(vec3(1.0, 0.8, 0.36), vec3(1.0, 0.9, 0.6), 1.0 - ahead);
	ALPHA = clamp(shape * (calm + spark * (0.35 + 0.95 * twinkle)) * dim, 0.0, 1.0);
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node

func pick(screen_position: Vector2) -> Dictionary:
	var stage: Node3D = game.stage
	var camera: Camera3D = stage.camera
	var best := {}
	var distance := 40.0
	for marker in markers:
		var p: Vector3 = marker.position
		if camera.is_position_behind(p):
			continue
		var gap := camera.unproject_position(p).distance_to(screen_position)
		var limit := 48.0 if String(marker.get("kind", "")) == "landmark" else distance
		if gap < limit and gap < distance + (8.0 if String(marker.get("kind", "")) == "landmark" else 0.0):
			best = marker
			distance = gap
	return best

func artifact_spot(site_id: String) -> Vector3:
	var device: Rig = rigs.get("mechanism_" + site_id)
	if device != null and device.is_ready():
		var spot := device.socket_global("artifact_spot")
		if spot != Vector3.INF:
			return spot
	return game.site_anchor(site_id).get("artifact", game.target_position(site_id))

# ------------------------------------------------------------------ choreography (live beats)
func choreo_owns(actor_id: String) -> bool:
	for key in choreo:
		if choreo[key].get("actors", []).has(actor_id):
			return true
	return false

func on_task_completed(site_id: String, task_id: String) -> void:
	if task_id == "unlock_cage" and not choreo.has("cage:" + site_id):
		on_cage_opened(site_id)
	elif task_id == "recover_artifact":
		var key_id := "artifact_" + site_id
		if rigs.has(key_id):
			var prop: Rig = rigs[key_id]
			choreo["key:" + site_id] = {"kind":"key_pickup", "site":site_id, "t":0.0, "from":prop.global_position, "actors":[]}

func on_cage_opened(site_id: String) -> void:
	if choreo.has("cage:" + site_id):
		choreo["cage:" + site_id].confirmed = true
		return
	var people := []
	for person in game.client.poi(site_id).get("captives", []):
		people.append(String(person.get("id", "")))
	choreo["cage:" + site_id] = {"kind":"cage", "site":site_id, "t":0.0, "stage":"start", "stage_t":0.0, "actors":people + ["squad_0"],
		"people":people, "exit_start":{}, "flags":{}}
	# The seal's insertion (lf_artifact_insert on the key_slot) is owned by the cage beat;
	# this beat only keeps the stable-pose code away from the artifact meanwhile.
	choreo["key:" + site_id] = {"kind":"key_insert", "site":site_id, "t":0.0, "actors":[]}

func start_guardian_death(site_id: String) -> void:
	if choreo.has("death:" + site_id):
		return
	choreo["death:" + site_id] = {"kind":"death", "site":site_id, "t":0.0, "actors":["guardian_" + site_id]}
	var people: Array = game.client.poi(site_id).get("captives", [])
	for index in people.size():
		var actor: Rig = rigs.get(String(people[index].get("id", "")))
		# Standing captives react; a seated one stays seated (react is a standing clip).
		if actor != null and is_instance_valid(actor) and not is_sitter(site_id, index):
			actor.play(["lf_civilian_react", "Idle"], 0.2, true)

func on_escort_arrived(site_id: String) -> void:
	if site_id.is_empty() or choreo.has("arrive:" + site_id):
		return
	var people := []
	var site: Dictionary = game.content.site(site_id)
	for person in site.get("captives", []):
		var id := String(person.get("id", ""))
		people.append(id)
		arrival_until[id] = Time.get_ticks_msec() + 9000
	choreo["arrive:" + site_id] = {"kind":"arrive", "site":site_id, "t":0.0, "actors":people}

func run_choreography(delta: float) -> void:
	for key in choreo.keys():
		var beat: Dictionary = choreo[key]
		beat.t = float(beat.t) + delta
		var done := false
		match String(beat.kind):
			"cage":
				done = run_cage(beat, delta)
			"key_pickup":
				done = run_key_pickup(beat)
			"key_insert":
				var key_prop: Rig = rigs.get("artifact_" + String(beat.site))
				done = float(beat.t) > 3.0 or (float(beat.t) > 0.6 and (key_prop == null or not is_instance_valid(key_prop) or key_prop.playing_id() != "lf_artifact_insert"))
			"death":
				done = run_death(beat)
			"arrive":
				done = run_arrival(beat, delta)
		if done:
			choreo.erase(key)

func set_stage(beat: Dictionary, stage: String) -> void:
	beat.stage = stage
	beat.stage_t = 0.0

## art/rescue_animation_storyboard «4. UNLOCK» + art/12: the soldier sets the seal into the
## socket (lf_soldier_unlock; its latch_release marker frees the latch), steps aside, the gate
## swings outward; seated people stand up, standing ones react, all leave through the door.
func run_cage(beat: Dictionary, delta: float) -> bool:
	var site_id := String(beat.site)
	beat.stage_t = float(beat.stage_t) + delta
	var st := float(beat.stage_t)
	var cage: Rig = rigs.get("cage_" + site_id)
	var soldier: Rig = rigs.get("squad_0")
	var key_prop: Rig = rigs.get("artifact_" + site_id)
	var anchor: Dictionary = game.site_anchor(site_id)
	var cage_pos: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	var basis := Basis(Vector3.UP, float(anchor.get("cage_yaw", 0.0)))
	var ready_cage := cage != null and is_instance_valid(cage) and cage.is_ready()
	var front: Vector3 = cage.global_transform * door_front_local(cage) if ready_cage else cage_pos + basis * Vector3(0.95, 0, 2.2)
	var aside: Vector3 = cage.global_transform * Vector3(2.15, 0, 2.75) if ready_cage else cage_pos + basis * Vector3(2.2, 0, 2.8)
	var face_cage := PathMotion.yaw_of(basis * Vector3.FORWARD)
	var has_soldier := soldier != null and is_instance_valid(soldier)
	match String(beat.stage):
		"start":
			if has_soldier:
				place("squad_0", soldier, front, face_cage, delta, true)
				soldier.play(["lf_soldier_unlock", "Sword_Drill", "Idle"], 0.2, true)
			set_stage(beat, "unlock")
		"unlock":
			if has_soldier:
				place("squad_0", soldier, front, face_cage, delta)
			if st >= 0.35 and not beat.flags.has("insert") and key_prop != null and is_instance_valid(key_prop) and ready_cage:
				beat.flags.insert = true
				seat_artifact(key_prop, cage, true)
				key_prop.set_active(true)
			# latch_release (soldier marker) → lf_cage_unlock; fallback by time.
			# 1024: a predicted unlock (button pressed, server not answered yet) waits here for the
			# confirmation; a refusal removes the beat (settle_prediction).
			if (beat.flags.has("latch_release") or st >= 2.0) and bool(beat.get("confirmed", true)):
				if ready_cage:
					cage.play(["lf_cage_unlock"], 0.0, true)
				game.audio.play_cue("fr_cage_latch")
				set_stage(beat, "latch")
		"latch":
			if has_soldier and st > 0.25:
				# Step aside: the door swings outward through the spot in front of the socket.
				var moved := place("squad_0", soldier, front.lerp(aside, clampf((st - 0.25) / 0.7, 0.0, 1.0)), PathMotion.yaw_of(cage_pos - aside), delta, false)
				if st < 0.95:
					soldier.locomote(maxf(moved, 1.4), SOLDIER_CLIPS)
			if beat.flags.has("latch_clear") and st >= 0.95 or st >= 1.4:
				if ready_cage:
					cage.set_meta("pose", "open")
					cage.play(["lf_cage_gate_open"], 0.0, true)
				game.audio.play_cue("fr_gate_creak")
				game.cage_opened.emit(site_id)
				if has_soldier:
					soldier.play(["lf_soldier_help", "lf_soldier_idle", "Idle"], 0.25, true)
				set_stage(beat, "gate")
		"gate":
			if has_soldier:
				place("squad_0", soldier, aside, PathMotion.yaw_of(cage_pos + basis * Vector3(0, 0, 3.2) - aside), delta)
			if beat.flags.has("passage_clear") or st >= 1.35:
				var index := 0
				for id in beat.people:
					var sitter := is_sitter(site_id, index)
					# Seated: stand_up (2.2 s) then exit; standing: react (1.4 s) then exit.
					beat.exit_start[id] = st + 0.75 * index + (2.15 if sitter else 1.25)
					beat.flags["sitter_" + str(id)] = sitter
					index += 1
				beat.exit_t0 = float(beat.t)
				set_stage(beat, "exit")
		"exit":
			if has_soldier:
				place("squad_0", soldier, aside, PathMotion.yaw_of(cage_pos + basis * Vector3(0, 0, 3.6) - aside), delta)
				if not soldier_one_shot(soldier):
					soldier.play(["lf_soldier_idle", "Idle"], 0.3)
	var people: Array = beat.people
	var all_out := String(beat.stage) == "exit"
	for index in people.size():
		var id := String(people[index])
		var actor: Rig = rigs.get(id)
		if actor == null or not is_instance_valid(actor):
			continue
		var seat := cage_slot(cage, index, cage_pos, basis)
		var sitter := is_sitter(site_id, index)
		if String(beat.stage) != "exit":
			place(id, actor, seat, PathMotion.yaw_of(basis * Vector3.BACK), delta, true, true)
			if not sitter and String(beat.stage) == "gate" and beat.flags.get("reacted_" + id, false) == false:
				beat.flags["reacted_" + id] = true
				actor.play(["lf_civilian_react", "lf_civilian_cage_stand", "Idle"], 0.25, true)
			elif sitter:
				actor.play(CAGE_IDLES[0], 0.3)
			all_out = false
			continue
		var since := float(beat.t) - float(beat.exit_t0)
		var go := float(beat.exit_start.get(id, 0.0))
		var lead := 2.15 if sitter else 1.25
		if since < go - lead:
			place(id, actor, seat, PathMotion.yaw_of(basis * Vector3.BACK), delta, true, true)
			actor.play(CAGE_IDLES[0] if sitter else CAGE_IDLES[1], 0.3)
			all_out = false
		elif since < go:
			place(id, actor, seat, PathMotion.yaw_of(basis * Vector3.BACK), delta, true, true)
			if sitter:
				actor.play(["lf_civilian_stand_up", "Idle"], 0.12)
			elif actor.playing_id() != "lf_civilian_react":
				actor.play(["lf_civilian_react", "lf_civilian_cage_stand", "Idle"], 0.2)
			all_out = false
		else:
			var path := exit_path(cage, seat, cage_pos, basis, index)
			var route: Dictionary = PathMotion.build(path)
			var speed := float(Rig.meta_for(actor.asset_path).get("clips", {}).get("lf_civilian_exit", {}).get("groundSpeed_mps", 1.0))
			var d := (since - go) * speed
			var sample := PathMotion.sample(route, d)
			var p: Vector3 = sample.position
			if d < float(route.total):
				place(id, actor, p, PathMotion.yaw_of(sample.tangent), delta, true, true)
				actor.locomote(speed, EXIT_CLIPS if d < 2.6 else CIVILIAN_CLIPS)
				all_out = false
			else:
				place(id, actor, game.ground(p.x, p.z), PathMotion.yaw_of(basis * Vector3.BACK), delta)
				actor.play(["lf_civilian_wait", "Idle"], 0.3)
				if since - go - float(route.total) / speed < 1.0:
					all_out = false
	return all_out and String(beat.stage) == "exit"

## Slot → exit_corridor_0..3 (through the door, cage nodes) → gathering spot (world space;
## the floor-height points keep their height, the outside points take the ground).
func exit_path(cage: Rig, seat: Vector3, cage_pos: Vector3, basis: Basis, index: int) -> Array:
	var path: Array = [seat]
	if cage != null and cage.is_ready():
		for k in 4:
			var node := cage.part("exit_corridor_%d" % k)
			if node != null and node.is_inside_tree():
				var p := node.global_position
				if k >= 2:
					p = game.ground(p.x, p.z)
				path.append(p)
	else:
		path.append(cage_pos + basis * Vector3(0, 0.12, 1.25))
		path.append(game.ground(cage_pos.x, cage_pos.z) + basis * Vector3(0, 0, 2.8))
	var gather := gather_spot(cage_pos, basis, index)
	path.append(game.ground(gather.x, gather.z))
	return path

## art/rescue_animation_storyboard «2. DISCOVER»: the captain reaches into the cache and lifts the seal.
func run_key_pickup(beat: Dictionary) -> bool:
	var site_id := String(beat.site)
	var key_prop: Rig = rigs.get("artifact_" + site_id)
	if key_prop == null or not is_instance_valid(key_prop):
		return true
	var target := squad_focus()
	if target == Vector3.INF:
		return true
	if not beat.has("reached"):
		beat.reached = true
		release_artifact(key_prop)
		var captain: Rig = rigs.get("squad_0")
		if captain != null and is_instance_valid(captain):
			captain.play(["lf_soldier_help", "lf_soldier_unlock", "Idle"], 0.2, true)
	if float(beat.t) < 0.7:
		key_prop.global_position = beat.from
		key_prop.set_active(key_prop.is_ready())
		key_prop.set_glow(2.4)
		game.fx.glow_world("artifact_" + site_id, key_prop.global_position)
		return false
	game.fx.glow_world("artifact_" + site_id, Vector3.INF)
	var f := clampf((float(beat.t) - 0.7) / 1.1, 0.0, 1.0)
	key_prop.global_position = (beat.from as Vector3).lerp(target + Vector3.UP * 1.2, f) + Vector3.UP * sin(PI * f) * 1.4
	key_prop.set_active(key_prop.is_ready())
	if f >= 1.0:
		key_prop.set_active(false)
		return true
	return false

func run_death(beat: Dictionary) -> bool:
	var id := "guardian_" + String(beat.site)
	var actor: Rig = rigs.get(id)
	if actor == null or not is_instance_valid(actor):
		return true
	var t := float(beat.t)
	if not beat.has("started"):
		beat.started = true
		beat.base_scale = actor.scale
		actor.play(["Death"], 0.15, true)
	if t > 3.6:
		actor.scale = (beat.base_scale as Vector3) * clampf(1.0 - (t - 3.6) / 1.4, 0.01, 1.0)
	return t > 5.0

## art/rescue_animation_storyboard «5. ESCORT»: the three arrive at the settlement and thank.
func run_arrival(beat: Dictionary, delta: float) -> bool:
	var t := float(beat.t)
	var home: Vector3 = game.target_position("lf_home_reception")
	var people: Array = beat.actors
	for index in people.size():
		var id := String(people[index])
		var actor: Rig = rigs.get(id)
		if actor == null or not is_instance_valid(actor):
			continue
		var spot := home + Vector3(-1.3 + 1.3 * index, 0, 1.6)
		place(id, actor, spot, PathMotion.yaw_of(Vector3(0, 0, 0) - spot), delta)
		if t < 2.6:
			actor.play(["lf_civilian_arrive", "lf_civilian_wait", "Idle"], 0.25)
		elif t < 5.0:
			actor.play(["lf_civilian_thank", "lf_civilian_wait", "Idle"], 0.25)
		else:
			actor.play(["lf_civilian_wait", "Idle"], 0.3)
		show_actor(actor, actor.position)
	if t > 0.2 and not beat.has("saluted"):
		beat.saluted = true
		var soldier: Rig = rigs.get("squad_0")
		if soldier != null and is_instance_valid(soldier):
			soldier.play(["lf_soldier_salute", "lf_soldier_idle", "Idle"], 0.2, true)
	return t > 8.0

func on_marker(actor: Node3D, clip_id: String, marker_name: String) -> void:
	var lower := marker_name.to_lower()
	if clip_id.begins_with("lf_rune_ring"):
		if lower == "click":
			game.audio.play_cue("fr_cage_latch", 0.1, 1.3)
		return
	if actor == rigs.get("horse"):
		if lower.begins_with("footfall") or lower.begins_with("land"):
			var state: Dictionary = motion.get("horse", {})
			if (float(state.get("speed", 0.0)) > 0.3 or clip_id.contains("turn") or clip_id.contains("stop")) and actor.visible:
				game.audio.hoof(actor.global_position)
		return
	match clip_id:
		"lf_soldier_attack":
			if lower.contains("contact"):
				game.fx.burst_world(actor.global_position + Vector3.UP * 1.1 + actor.global_basis.z * 0.9, "hit")
		"lf_soldier_unlock":
			if lower == "latch_release":
				for key in choreo:
					if String(choreo[key].get("kind", "")) == "cage" and String(choreo[key].get("stage", "")) == "unlock":
						choreo[key].flags.latch_release = true
		"lf_cage_unlock":
			if lower == "latch_clear":
				for key in choreo:
					if String(choreo[key].get("kind", "")) == "cage" and actor == rigs.get("cage_" + String(choreo[key].site)):
						choreo[key].flags.latch_clear = true
		"lf_cage_gate_open":
			if lower == "passage_clear":
				for key in choreo:
					if String(choreo[key].get("kind", "")) == "cage" and actor == rigs.get("cage_" + String(choreo[key].site)):
						choreo[key].flags.passage_clear = true
		"lf_artifact_insert":
			if lower == "seated":
				game.fx.burst_world(actor.global_position - Vector3.UP * 0.8, "hit")
				game.audio.play_cue("fr_cage_latch")
				(actor as Rig).set_glow(2.0)
			elif lower == "glow_peak":
				(actor as Rig).set_glow(4.2)
		"lf_boss_jaw_arc", "lf_boss_tail_sweep", "lf_boss_lane_charge", "lf_boss_stomp_waves":
			if lower == "active_begin" or (lower.begins_with("wave_") and lower.ends_with("_begin")):
				game.fx.burst_world(actor.global_position + actor.global_basis.z * 4.0 * boss_scale, "hit")
				game.audio.play_cue("fr_distant_rumble", 1.5, 1.25)
		"lf_boss_death":
			if lower == "ground_contact":
				game.fx.burst_world(actor.global_position, "hit")
				game.audio.play_cue("fr_distant_rumble", 0.0, 0.8)
		"lf_winch_brake", "lf_winch_pawl":
			game.audio.play_cue("fr_cage_latch", 0.1, 1.15)
		"lf_rope_release", "lf_lock_mechanism":
			if lower in ["lid_open", "cache_open", "latch_open"]:
				game.audio.play_cue("fr_artifact_discovery", 0.5)
			elif lower in ["plates_down", "lid_unlocked"]:
				game.audio.play_cue("fr_cage_latch", 0.2)

func on_clip_finished(actor: Node3D, clip_id: String) -> void:
	match clip_id:
		"lf_cage_gate_open":
			(actor as Rig).play(["lf_cage_gate_settle"], 0.05, true)
		"lf_artifact_insert":
			(actor as Rig).play(["lf_artifact_glow"], 0.1)
			(actor as Rig).set_glow(3.0)
		"lf_horse_look_back", "lf_horse_call", "lf_horse_alert":
			(actor as Rig).play(["lf_horse_idle", "Idle"], 0.3)
