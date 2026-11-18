extends Node
## Adventure actors under forest_world.actors_root() / props under props_root().
## Every pose is derived from the authoritative projection (state.adventure) and the server
## clock; events only add short presentation beats (cage opening, death, arrival) during a
## live session. After a reload the stable pose is restored from state: open door, artifact
## hidden or in the socket, captives absent once home, defeated guardians removed.

const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const PathMotion = preload("res://src/forest_rescue/game/path_motion.gd")
const Telegraphs = preload("res://src/forest_rescue/game/boss_telegraphs.gd")
const ASSETS := "res://assets/forest_rescue/"
const HORSE_GLB := ASSETS + "horse/lf_horse_origin.glb"
const SQUAD_GLBS := [ASSETS + "humans/lf_squad_captain.glb", ASSETS + "humans/lf_squad_shield_guard.glb", ASSETS + "humans/lf_squad_scout.glb"]
const BOSS_GLB := ASSETS + "boss/lf_boss_ancient_maw.glb"
const CAGE_FILES := {"oak":"lf_cage_wood", "wood":"lf_cage_wood", "iron":"lf_cage_iron", "root":"lf_cage_root"}
const HORSE_CLIPS := {"idle":["lf_horse_idle", "Idle"], "walk":["lf_horse_walk", "Walk"], "run":["lf_horse_trot", "Run"], "walk_speed":1.6, "run_speed":3.4}
const SOLDIER_CLIPS := {"idle":["lf_soldier_idle", "Idle"], "walk":["lf_soldier_walk", "Walk"], "run":["lf_soldier_jog", "Run"], "walk_speed":1.4, "run_speed":3.0}
const GUARD_CLIPS := {"idle":["lf_soldier_guard", "lf_soldier_idle", "Shield_Block", "Idle"], "walk":["lf_soldier_walk", "Walk"], "run":["lf_soldier_jog", "Run"], "walk_speed":1.4, "run_speed":3.0}
const CIVILIAN_CLIPS := {"idle":["lf_civilian_wait", "Idle"], "walk":["lf_civilian_follow", "Walk"], "walk_speed":1.2}
const TIRED_CLIPS := {"idle":["lf_civilian_wait", "Idle"], "walk":["lf_civilian_follow_tired", "lf_civilian_follow", "Walk"], "walk_speed":0.95}
const CREATURE_CLIPS := {"idle":["Idle"], "walk":["Walk"], "run":["Run"], "walk_speed":1.6, "run_speed":4.0}
const CAGE_IDLES := [["lf_civilian_cage_sit", "Idle"], ["lf_civilian_cage_stand", "Idle"], ["lf_civilian_cage_wait", "Idle"]]
const CAGE_SLOTS := [Vector3(-0.72, 0, 0.1), Vector3(0.05, 0, -0.45), Vector3(0.74, 0, 0.18)]
const SQUAD_FORMATION := [Vector3(0, 0, 0), Vector3(-0.85, 0, -1.25), Vector3(0.85, 0, -1.25)]
const LIVE_RANGE := 70.0

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
var guardian_alerted: Dictionary = {}

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "ForestActors"
	var parsed: Variant = game.content.read_json(ASSETS + "humans/captive_variants.json")
	variants = parsed if parsed is Dictionary else {}
	parsed = game.content.read_json(ASSETS + "props/site_props.json")
	props_index = parsed if parsed is Dictionary else {}

func on_stage_changed() -> void:
	for id in rigs.keys():
		var rig: Node = rigs[id]
		if is_instance_valid(rig):
			rig.queue_free()
	rigs.clear()
	motion.clear()
	site_props.clear()
	choreo.clear()
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
		telegraphs.setup(game)
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

## Moves an actor towards a computed ground pose, measures its real speed for locomotion.
func place(id: String, actor: Rig, target: Vector3, yaw: float, delta: float, snap := false) -> float:
	var state: Dictionary = motion.get(id, {})
	var ground: Vector3 = game.ground(target.x, target.z)
	if state.is_empty() or snap or state.position.distance_to(ground) > 8.0:
		state = {"position":ground, "yaw":yaw, "speed":0.0}
	else:
		var previous: Vector3 = state.position
		var next := previous.lerp(ground, 1.0 - exp(-14.0 * delta))
		var moved := Vector2(next.x - previous.x, next.z - previous.z).length()
		var measured := moved / maxf(delta, 0.0001)
		state.speed = lerpf(float(state.speed), measured, 1.0 - exp(-6.0 * delta))
		state.position = next
		state.yaw = PathMotion.turn_towards(float(state.yaw), yaw, 7.0, delta)
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

# ------------------------------------------------------------------ per frame
func tick(delta: float) -> void:
	if not game.client.unlocked():
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
	adv = game.client.adv
	markers.clear()
	tags.clear()
	var now := now_ms()
	update_lod()
	update_horse(now, delta)
	update_squad(now, delta)
	update_sites(now, delta)
	update_boss(now, delta)
	update_beacon(delta)
	update_ribbon()
	update_preview()
	update_battle_hud(now)
	run_choreography(delta)

func update_lod() -> void:
	# Orthographic size decides the LOD (hysteresis 4 units); new rigs pick it up immediately.
	var zoom: float = float(game.stage.camera_zoom)
	if absf(zoom - lod_zoom) >= 4.0:
		lod_zoom = zoom
	var level := 0 if lod_zoom < 42.0 else (1 if lod_zoom < 85.0 else 2)
	for id in rigs:
		var actor: Rig = rigs[id]
		if is_instance_valid(actor) and actor.is_ready() and actor.lod_level != level:
			actor.set_lod(level)

func squad_member_count() -> int:
	var squad: Dictionary = game.client.squad()
	if game.total_units(squad.get("units", {})) <= 0:
		return 0
	return clampi(int(squad.get("members", 3)), 1, 3)

func route_for(key: String, path: Array) -> Dictionary:
	if not routes.has(key):
		routes[key] = PathMotion.build(path)
		if routes.size() > 24:
			routes.erase(routes.keys()[0])
	return routes[key]

func move_sample(move: Dictionary, now: float, back := 0.0) -> Dictionary:
	var key := "%s|%s|%s" % [str(move.get("departAt", 0)), str(move.get("arriveAt", 0)), str(move.get("targetId", ""))]
	var route := route_for(key, move.get("path", []))
	var distance := PathMotion.travelled(move, route, now)
	var sample := PathMotion.sample(route, maxf(0.0, distance - back))
	sample.arrived = now >= float(move.get("arriveAt", 0))
	sample.speed = 0.0 if sample.arrived else PathMotion.speed(move, route)
	sample.route = route
	sample.distance = distance
	return sample

# ------------------------------------------------------------------ horse (guide)
func update_horse(now: float, delta: float) -> void:
	var horse: Dictionary = adv.get("horse", {})
	var actor := rig("horse", HORSE_GLB)
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
		var speed := place("horse", actor, target, yaw, delta, elapsed < 0.05)
		if moving:
			actor.locomote(maxf(speed, from.distance_to(to) / walk_seconds), HORSE_CLIPS)
		elif elapsed < walk_seconds + 0.8:
			actor.play(["lf_horse_stop", "lf_horse_idle", "Idle"], 0.2)
		else:
			actor.play(["lf_horse_look_back", "lf_horse_idle", "Idle"], 0.3)
		# The entrance corridor is opening right now: the mare walks out of the mist.
		actor.set_active(actor.is_ready() and visible_in_view(actor.position))
		markers.append({"position":actor.position + Vector3.UP * 1.6, "kind":"horse", "id":"horse"})
		return
	if move is Dictionary and not (move.get("path", []) as Array).is_empty():
		var sample := move_sample(move, now)
		target = sample.position
		yaw = PathMotion.yaw_of(sample.tangent)
		moving = not sample.arrived
	var speed := place("horse", actor, target, yaw, delta)
	var mood := String(horse.get("mood", "calm"))
	var walking := moving or speed > 0.25
	# Authored start/stop clips carry the weight shift between standing and walking.
	if walking != horse_was_walking:
		horse_was_walking = walking
		if actor.play(["lf_horse_start"] if walking else ["lf_horse_stop"], 0.15, true):
			horse_transition_until = Time.get_ticks_msec() + int(1000.0 * actor.clip_length(["lf_horse_start"] if walking else ["lf_horse_stop"]) * 0.85)
	if Time.get_ticks_msec() < horse_transition_until:
		pass
	elif walking:
		actor.locomote(speed, HORSE_CLIPS)
		horse_wait_ticks = 0
	else:
		var squad_pos: Vector3 = squad_focus()
		var waiting := mood == "waiting" or (squad_pos != Vector3.INF and squad_pos.distance_to(actor.position) > 7.0)
		if mood == "alert":
			actor.play(["lf_horse_alert", "lf_horse_idle", "Idle"], 0.25)
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
		tags.append({"position":actor.position + Vector3.UP * 2.6, "text":game.content.text("hud.horse"), "kind":"horse"})
	game.pin("lf_horse", actor.position, 14.0)

func forest_heading() -> float:
	var origin: Vector3 = game.target_position("lf_horse_origin")
	var first: Vector3 = game.target_position("lf_site_01")
	if origin == Vector3.INF or first == Vector3.INF:
		return PI
	return PathMotion.yaw_of(first - origin)

## Intro presentation: the mare walks out of the mist along the entrance corridor.
func start_intro_horse(from: Vector3, to: Vector3, walk_seconds: float) -> void:
	intro_horse = {"from":from, "to":to, "walk":walk_seconds, "started":Time.get_ticks_msec()}
	motion.erase("horse")

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
	if fallback.is_empty() and data.unitModels.has("ENG-09"):
		fallback = data.unitModels["ENG-09"].field
	return [SQUAD_GLBS[index], fallback]

func update_squad(now: float, delta: float) -> void:
	var squad: Dictionary = game.client.squad()
	var count := squad_member_count()
	for index in 3:
		var id := "squad_%d" % index
		if index >= count:
			if rigs.has(id):
				drop(id)
			continue
		var paths := squad_model_paths(index)
		var actor := rig(id, paths[0], paths[1])
		var pose := squad_pose(index, now)
		var speed := place(id, actor, pose.position, pose.yaw, delta)
		if choreo_owns(id):
			pass
		elif pose.has("clip"):
			if pose.get("hold", false):
				actor.hold_end(pose.clip)
			elif pose.has("at"):
				actor.pose_at(pose.clip, pose.at)
			else:
				actor.play(pose.clip, 0.2)
		else:
			actor.locomote(maxf(speed, float(pose.get("speed", 0.0))) if pose.get("moving", false) else speed, GUARD_CLIPS if pose.get("guard", false) else SOLDIER_CLIPS)
		if show_actor(actor, actor.position):
			markers.append({"position":actor.position + Vector3.UP * 1.4, "kind":"squad", "id":id})
	if count > 0:
		var leader: Dictionary = motion.get("squad_0", {})
		if not leader.is_empty():
			game.pin("lf_squad", leader.position, 16.0)
			if game.fog_clear(leader.position):
				tags.append({"position":leader.position + Vector3.UP * 2.6, "text":game.content.text("hud.squad"), "kind":"squad"})

func squad_pose(index: int, now: float) -> Dictionary:
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
			return {"position":sample.position + side * [0.0, -0.9, 0.9][index], "yaw":PathMotion.yaw_of(tangent), "moving":not sample.arrived, "speed":sample.speed}
	var center: Vector3 = game.target_position(node)
	var rest: Variant = squad.get("position")
	if rest is Dictionary and (center == Vector3.INF or node.contains("#")):
		center = game.ground(float(rest.get("x", 0)), float(rest.get("z", 0)))
	if center == Vector3.INF:
		center = game.target_position("lf_horse_origin")
	var focus := focus_for_node(node, center)
	var forward := (focus - center)
	forward.y = 0
	if forward.length_squared() < 0.01:
		forward = Vector3(sin(forest_heading()), 0, cos(forest_heading()))
	forward = forward.normalized()
	var right := Vector3(forward.z, 0, -forward.x)
	var site_here := node.get_slice(":", 0).replace("lf_key_", "lf_site_")
	var plates: Variant = game.client.poi(site_here).get("mechanism", {}).get("plates")
	if plates is Dictionary and String(plates.get("state", "free")) in ["walking", "held"]:
		var site_id := site_here
		var anchor: Dictionary = game.site_anchor(site_id)
		if anchor.has("plate_left") and index < 2:
			var plate: Vector3 = anchor.plate_left if index == 0 else anchor.plate_right
			return {"position":plate, "yaw":PathMotion.yaw_of(anchor.get("center", plate) - plate), "clip":["lf_soldier_guard", "lf_soldier_idle", "Shield_Block", "Idle"]}
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
		update_props(site_id, poi, anchor, near)
		update_captives(site_id, poi, anchor, now, delta, near)
		update_guardian(site_id, poi, anchor, now, delta, near)
		var step := int(game.client.site_state(site_id).get("step", 0))
		markers.append({"position":center + Vector3.UP * 2.0, "kind":"site", "id":site_id, "site":site_id})
		var trail_open: bool = game.mech.is_open() and game.mech.site_id == site_id and game.mech.kind == "trail_cache"
		if game.fog_clear(center) and not trail_open:
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

func update_props(site_id: String, poi: Dictionary, anchor: Dictionary, near: bool) -> void:
	var record: Dictionary = site_props.get(site_id, {})
	var cage_kind := String(poi.get("cage", "oak"))
	var cage_file := String(props_index.get("cages", {}).get(cage_kind, {}).get("asset", "props/" + CAGE_FILES.get(cage_kind, "lf_cage_wood") + ".glb"))
	var cage_id := "cage_" + site_id
	var cage := rig(cage_id, ASSETS + cage_file, "", 1.0, props_parent)
	record.cage = cage_id
	var cage_pos: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	cage.position = game.ground(cage_pos.x, cage_pos.z)
	cage.rotation.y = float(anchor.get("cage_yaw", 0.0))
	cage.set_active(near and cage.is_ready())
	if cage.is_ready() and not choreo.has("cage:" + site_id):
		if String(poi.get("cagePose", "closed")) == "open":
			if cage.get_meta("pose", "") != "open":
				cage.set_meta("pose", "open")
				if not cage.hold_end(["lf_cage_gate_open", "lf_cage_gate_settle"]):
					swing_door(cage, 1.0)
		elif cage.get_meta("pose", "") != "closed":
			cage.set_meta("pose", "closed")
			swing_door(cage, 0.0)
	if near:
		markers.append({"position":cage.position + Vector3.UP * 1.6, "kind":"cage", "site":site_id, "id":cage_id})
	var artifact: Dictionary = poi.get("artifact", {})
	var family := String(artifact.get("family", "stone_rune"))
	var artifact_id := "artifact_" + site_id
	var art_file := String(props_index.get("artifacts", {}).get(family, {}).get("asset", "props/lf_artifact_%s.glb" % family)) if props_index.get("artifacts", {}).get(family) is Dictionary else "props/lf_artifact_%s.glb" % family
	var key_prop := rig(artifact_id, ASSETS + art_file, "", 1.0, props_parent)
	record.artifact = artifact_id
	var state := String(artifact.get("state", "hidden"))
	var mechanism: Dictionary = poi.get("mechanism", {})
	var spot: Vector3 = anchor.get("artifact", cage_pos)
	if choreo.has("key:" + site_id):
		pass
	elif state == "in_socket":
		key_prop.position = socket_point(site_id, cage)
		key_prop.set_active(near and key_prop.is_ready())
	elif state == "hidden" and bool(mechanism.get("solved", false)):
		key_prop.position = game.ground(spot.x, spot.z) + Vector3.UP * (0.55 + 0.08 * sin(Time.get_ticks_msec() / 400.0))
		key_prop.rotation.y += 0.02
		key_prop.set_active(near and key_prop.is_ready())
		game.fx.glow_world("artifact_" + site_id, key_prop.position)
	else:
		key_prop.set_active(false)
		game.fx.glow_world("artifact_" + site_id, Vector3.INF)
	var kind := String(poi.get("variation", mechanism.get("kind", "")))
	if not kind.is_empty():
		var mech_id := "mechanism_" + site_id
		var mech_file := String(props_index.get("mechanisms", {}).get(kind, {}).get("asset", "props/lf_mechanism_%s.glb" % kind)) if props_index.get("mechanisms", {}).get(kind) is Dictionary else "props/lf_mechanism_%s.glb" % kind
		var device := rig(mech_id, ASSETS + mech_file, "", 1.0, props_parent)
		record.mechanism = mech_id
		device.position = game.ground(spot.x, spot.z)
		device.rotation.y = float(anchor.get("cage_yaw", 0.0))
		device.set_active(near and device.is_ready())
		if device.is_ready():
			var solved := bool(mechanism.get("solved", false)) or state != "hidden"
			if solved and device.get_meta("pose", "") != "solved":
				device.set_meta("pose", "solved")
				device.hold_end(["lf_lock_mechanism", "lf_rope_release", "solved", "open"])
		if near and not solved_or_found(poi):
			markers.append({"position":device.position + Vector3.UP * 1.2, "kind":"artifact", "site":site_id, "id":mech_id})
	site_props[site_id] = record

func solved_or_found(poi: Dictionary) -> bool:
	return String(poi.get("artifact", {}).get("state", "hidden")) != "hidden"

func socket_point(site_id: String, cage: Rig) -> Vector3:
	var local: Variant = cage.socket("key_slot")
	if local == null:
		local = cage.socket("socket")
	if local == null:
		var part := cage.find_part(["key_slot", "socket", "lock"])
		if part != null:
			return part.global_position
		local = Vector3(0.55, 1.05, 1.32)
	return cage.global_transform * (local as Vector3) if cage.is_inside_tree() else cage.position + (local as Vector3)

func door_node(cage: Rig) -> Node3D:
	if cage.has_meta("door_node"):
		var cached: Variant = cage.get_meta("door_node")
		if cached is Node3D and is_instance_valid(cached):
			return cached
	var hint := String(props_index.get("doorNode", "door"))
	var found := cage.find_part([hint, "gate", "door"])
	cage.set_meta("door_node", found)
	return found

## Fallback when a cage GLB has no gate clip: rotate the door node around its hinge pivot.
func swing_door(cage: Rig, amount: float) -> void:
	var door := door_node(cage)
	if door == null:
		return
	if not door.has_meta("closed_yaw"):
		door.set_meta("closed_yaw", door.rotation.y)
	var opening := deg_to_rad(float(cage.meta.get("sockets", {}).get("door_open_deg", [105])[0]) if cage.meta.get("sockets", {}).get("door_open_deg") is Array else float(cage.meta.get("door_open_deg", 105.0)))
	door.rotation.y = float(door.get_meta("closed_yaw")) + opening * amount

func captive_visual(captive: Dictionary) -> String:
	var id := String(captive.get("id", ""))
	var variant: Variant = variants.get("captives", {}).get(id, variants.get(id))
	if variant is Dictionary and variant.has("visual"):
		return String(variant.visual)
	return String(captive.get("visual", "miller"))

func update_captives(site_id: String, poi: Dictionary, anchor: Dictionary, now: float, delta: float, near: bool) -> void:
	var people: Array = poi.get("captives", [])
	var cage_pos: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	var cage_yaw := float(anchor.get("cage_yaw", 0.0))
	var basis := Basis(Vector3.UP, cage_yaw)
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
		var actor := rig(id, ASSETS + "humans/lf_civilian_%s.glb" % visual)
		if choreo_owns(id):
			show_actor(actor, actor.position, near or arriving)
			continue
		var slot: Vector3 = cage_pos + basis * CAGE_SLOTS[index % 3]
		var gather: Vector3 = cage_pos + basis * Vector3(-1.1 + 1.1 * index, 0, 2.6 + 0.3 * (index % 2))
		match state:
			"caged":
				place(id, actor, slot, cage_yaw + (0.35 * (index - 1)), delta, true)
				actor.play(CAGE_IDLES[(index + int(game.content.site_number(site_id))) % 3], 0.3)
			"freed":
				place(id, actor, gather, cage_yaw, delta)
				actor.play(["lf_civilian_wait", "lf_civilian_cage_stand", "Idle"], 0.3)
			"escorted":
				var walk_move: Variant = walk.get("move")
				if walk_move is Dictionary and String(walk.get("siteId", "")) == site_id:
					var sample := move_sample(walk_move, now, 1.7 + 1.5 * index)
					var tangent: Vector3 = sample.tangent
					var side := Vector3(tangent.z, 0, -tangent.x)
					var speed := place(id, actor, sample.position + side * [0.5, -0.5, 0.0][index % 3], PathMotion.yaw_of(tangent), delta)
					actor.locomote(maxf(speed, sample.speed) if not sample.arrived else speed, TIRED_CLIPS if index == 2 else CIVILIAN_CLIPS)
				else:
					place(id, actor, gather, cage_yaw, delta)
					actor.play(["lf_civilian_wait", "Idle"], 0.3)
			"home":
				var home: Vector3 = game.target_position("lf_home_reception")
				place(id, actor, home + Vector3(-1.2 + 1.2 * index, 0, 1.4), PathMotion.yaw_of(-home), delta)
		if show_actor(actor, actor.position, near or arriving or state == "escorted"):
			markers.append({"position":actor.position + Vector3.UP * 1.3, "kind":"cage" if state == "caged" else "site", "site":site_id, "id":id})

func guardian_paths(spec: Dictionary) -> Array:
	# Product decision (2026-11-18): campaign guardians use the game's EXISTING creature
	# models (data.creatureModels, species × level 1–3) — no new guardian art.
	var species := String(spec.get("species", "tenerys"))
	var level := clampi(int(spec.get("level", 1)), 1, 3)
	var original := ""
	var models: Dictionary = game.main.data.get("creatureModels", {})
	if models.has(species):
		original = String(models[species][level - 1])
	return [original, original]

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
	# Same scale rule as ordinary hunts in landscape.gd (1.02 + 0.16 × level), original materials.
	var actor := rig(id, paths[0], paths[1], 1.02 + 0.16 * level)
	var home: Vector3 = anchor.get("guardian", anchor.get("center", Vector3.ZERO))
	var approach: Vector3 = anchor.get("approach", home + Vector3(0, 0, 4))
	var squad_pos := squad_focus()
	var face := approach
	if squad_pos != Vector3.INF and squad_pos.distance_to(home) < 14.0:
		face = squad_pos
	if dying:
		show_actor(actor, actor.position, near)
		return
	var fight: Dictionary = game.client.battle()
	var in_battle: bool = not fight.is_empty() and String(fight.get("siteId", "")) == site_id and String(fight.get("species", "")) != "ancient_maw"
	var speed := place(id, actor, home, PathMotion.yaw_of(face - home), delta)
	if in_battle:
		guardian_battle_pose(actor, fight, now)
	elif squad_pos != Vector3.INF and squad_pos.distance_to(home) < 12.0 and not guardian_alerted.get(site_id, false):
		guardian_alerted[site_id] = true
		actor.play(["Alert", "Roar", "Idle"], 0.2, true)
		game.audio.play_cue("fr_distant_rumble", 10.0)
	elif not actor.player or not actor.player.is_playing() or actor.current_id in ["Idle", "Walk", "Run"]:
		actor.locomote(speed, CREATURE_CLIPS)
	if show_actor(actor, actor.position, near):
		markers.append({"position":actor.position + Vector3.UP * 2.2, "kind":"guardian", "site":site_id, "id":id})

# ------------------------------------------------------------------ battles (server timeline)
func battle_elapsed(fight: Dictionary, now: float) -> float:
	return (now - float(fight.get("startedAt", now))) / 1000.0

func timeline(fight: Dictionary) -> Array:
	return fight.get("timeline", [])

func latest_event(fight: Dictionary, elapsed: float, actor: String, window: float) -> Dictionary:
	var best := {}
	for event in timeline(fight):
		var at := float(event.get("t", 0.0))
		if at > elapsed or elapsed - at > window:
			continue
		if not actor.is_empty() and String(event.get("actor", "")) != actor:
			continue
		if best.is_empty() or at >= float(best.get("t", 0.0)):
			best = event
	return best

func guardian_battle_pose(actor: Rig, fight: Dictionary, now: float) -> void:
	var elapsed := battle_elapsed(fight, now)
	var ending := float(fight.get("endsAt", now)) <= now
	for event in timeline(fight):
		if String(event.get("type", "")) == "death" and String(event.get("actor", "")) == "guardian" and float(event.get("t", 0.0)) <= elapsed:
			actor.pose_at(["Death"], elapsed - float(event.t))
			return
	if ending and String(fight.get("outcome", "")) == "victory":
		actor.hold_end(["Death"])
		return
	var own := latest_event(fight, elapsed, "guardian", 1.3)
	if not own.is_empty() and String(own.get("type", "")) in ["attack", "ability"]:
		actor.pose_at(["Attack"] if String(own.type) == "attack" else ["Roar", "Alert", "Attack"], elapsed - float(own.get("t", 0.0)))
		return
	var struck := latest_event(fight, elapsed, "squad", 0.6)
	if not struck.is_empty() and String(struck.get("type", "")) == "attack":
		actor.pose_at(["Hit"], maxf(0.0, elapsed - float(struck.get("t", 0.0)) - 0.35))
		return
	if elapsed < 1.2:
		actor.pose_at(["Alert", "Idle"], elapsed)
		return
	actor.play(["Idle"], 0.25)

func battle_member_pose(index: int, fight: Dictionary, now: float) -> Dictionary:
	var site_id := String(fight.get("siteId", ""))
	var boss_fight := String(fight.get("species", "")) == "ancient_maw"
	var enemy: Vector3 = game.target_position("lf_boss_ancient_maw") if boss_fight else game.site_anchor(site_id).get("guardian", Vector3.ZERO)
	var approach: Vector3 = enemy + Vector3(0, 0, 10) if boss_fight else game.site_anchor(site_id).get("approach", enemy + Vector3(0, 0, 4))
	var away := (approach - enemy)
	away.y = 0
	away = away.normalized() if away.length_squared() > 0.01 else Vector3.BACK
	var distance := 9.0 if boss_fight else 3.6
	var spread: float = [0.0, -0.75, 0.75][index]
	var p := enemy + away.rotated(Vector3.UP, spread) * distance
	var yaw := PathMotion.yaw_of(enemy - p)
	var elapsed := battle_elapsed(fight, now)
	for event in timeline(fight):
		var at := float(event.get("t", 0.0))
		if at > elapsed or elapsed - at > 1.25:
			continue
		var who := int(event.get("member", event.get("index", -1)))
		var actor_kind := String(event.get("actor", ""))
		if actor_kind == "squad" and String(event.get("type", "")) == "attack" and (who == index or (who < 0 and int(at * 10.0) % 3 == index)):
			return {"position":p + (enemy - p).normalized() * 0.4 * sin(PI * clampf((elapsed - at) / 1.2, 0.0, 1.0)), "yaw":yaw, "clip":["lf_soldier_attack", "Sword_Drill", "Attack"], "at":elapsed - at}
		if actor_kind in ["guardian", "boss"] and String(event.get("type", "")) in ["attack", "hit"] and (who == index or (who < 0 and index == 0)) and elapsed - at > 0.55 and elapsed - at < 1.05:
			return {"position":p, "yaw":yaw, "clip":["lf_soldier_hit", "Hit"], "at":elapsed - at - 0.55}
	return {"position":p, "yaw":yaw, "clip":["lf_soldier_guard", "lf_soldier_idle", "Shield_Block", "Idle"]}

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
	for event in timeline(fight):
		if float(event.get("t", 0.0)) <= elapsed and event.has("hp"):
			hp = float(event.hp)
	var left := maxi(0, ceili((float(fight.get("endsAt", now)) - now) / 1000.0))
	var title: String = game.content.text("site.guardian", {"name":game.content.species_name(species), "level":int(fight.get("level")) if fight.get("level") != null else 1})
	var sub := "%d:%02d" % [left / 60, left % 60]
	if boss_fight:
		title = "%s · %s" % [game.content.species_name(species), game.content.text("boss.phase." + String(adv.get("boss", {}).get("phase", "hunt")))]
		var warning: String = telegraphs.current_warning()
		if not warning.is_empty():
			sub = warning + " · " + sub
	game.hud.show_battle(title, hp, hp_max, sub, true)

func on_battle_report(_report_id: String) -> void:
	last_battle = game.client.battle()

# ------------------------------------------------------------------ boss
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
	var actor := rig("boss", BOSS_GLB, "", 1.0)
	var fight: Dictionary = game.client.battle()
	var boss_fight: bool = not fight.is_empty() and String(fight.get("species", "")) == "ancient_maw"
	var squad_pos := squad_focus()
	var face := squad_pos if squad_pos != Vector3.INF else arena + Vector3(0, 0, 10)
	place("boss", actor, arena, PathMotion.yaw_of(face - arena), delta)
	if state == "defeated" or (boss_fight and String(fight.get("outcome", "")) == "victory" and float(fight.get("endsAt", 0)) <= now):
		actor.hold_end(["lf_boss_death", "Death"])
		telegraphs.clear()
	elif boss_fight and String(fight.get("outcome", "pending")) == "pending":
		var elapsed := battle_elapsed(fight, now)
		var attack: Dictionary = telegraphs.update_from_battle(fight, elapsed, actor.position, float(motion.get("boss", {}).get("yaw", 0.0)), squad_pos)
		if not attack.is_empty():
			actor.pose_at(["lf_boss_" + String(attack.attack), "Attack"], float(attack.local))
		else:
			var phase_event := latest_event(fight, elapsed, "boss", 2.8)
			if not phase_event.is_empty() and String(phase_event.get("type", "")) == "phase":
				actor.pose_at(["lf_boss_phase_roar", "Roar"], elapsed - float(phase_event.get("t", 0.0)))
			elif elapsed < 4.2:
				actor.pose_at(["lf_boss_awaken", "lf_boss_idle", "Idle"], elapsed)
			else:
				actor.play(["lf_boss_idle", "Idle"], 0.3)
	else:
		telegraphs.clear()
		actor.play(["lf_boss_idle", "Idle"], 0.3)
	if show_actor(actor, actor.position):
		markers.append({"position":actor.position + Vector3.UP * 3.0, "kind":"boss", "id":"boss"})
		tags.append({"position":actor.position + Vector3.UP * 6.5, "text":game.content.species_name("ancient_maw"), "kind":"boss"})

func on_boss_started() -> void:
	var actor: Rig = rigs.get("boss")
	if actor != null and is_instance_valid(actor):
		actor.play(["lf_boss_awaken", "Roar"], 0.2, true)

func on_boss_phase(_phase_id: String) -> void:
	var actor: Rig = rigs.get("boss")
	if actor != null and is_instance_valid(actor):
		actor.play(["lf_boss_phase_roar", "Roar"], 0.2, true)
	game.audio.play_cue("fr_distant_rumble", 10.0)

# ------------------------------------------------------------------ beacon, route ribbon, tags, picking
func set_beacon(target_id: String) -> void:
	beacon_target = target_id

func update_beacon(delta: float) -> void:
	if beacon == null or not is_instance_valid(beacon):
		beacon = build_beacon()
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
		root.add_child(ribbon)
		ribbon_signature = ""
	ribbon.show()
	if signature != ribbon_signature:
		ribbon_signature = signature
		var route := PathMotion.build(source.get("path", []))
		var total := float(route.total)
		var count := clampi(int(total / 1.15), 2, 400)
		var multimesh := ribbon.multimesh
		multimesh.instance_count = count
		for i in count:
			var d := total * float(i) / float(count - 1)
			var sample := PathMotion.sample(route, d)
			var p: Vector3 = game.ground(sample.position.x, sample.position.z) + Vector3.UP * 0.18
			multimesh.set_instance_transform(i, Transform3D(Basis.IDENTITY, p))
			multimesh.set_instance_custom_data(i, Color(d / maxf(total, 0.01), d, 0, 0))
	var progress := 0.0
	var sample_now := move_sample(source, now_ms())
	progress = float(sample_now.distance)
	(ribbon.material_override as ShaderMaterial).set_shader_parameter("travelled", progress)

## Faint golden dots along the authored route to the next suggested target (art/07 panel 3).
func set_preview(target_id: String) -> void:
	preview_target = target_id

func route_index(node: String) -> int:
	var base := node.get_slice(":", 0).get_slice("#", 0)
	if base in ["lf_horse_origin", "lf_home_reception"]:
		return 0
	if base.begins_with("lf_site_"):
		return int(base.trim_prefix("lf_site_"))
	if base.begins_with("lf_key_"):
		return int(base.trim_prefix("lf_key_"))
	if base == "lf_boss_ancient_maw":
		return 13
	return -1

func update_preview() -> void:
	var squad: Dictionary = game.client.squad()
	var from := route_index(String(squad.get("node", "")))
	var to := route_index(preview_target)
	var show_it := preview_target != "" and not (squad.get("move") is Dictionary) and from >= 0 and to >= 0 and absi(to - from) == 1
	var signature := "%d>%d" % [from, to]
	if not show_it:
		if is_instance_valid(preview):
			preview.hide()
		return
	if preview == null or not is_instance_valid(preview):
		preview = build_ribbon()
		preview.name = "RoutePreview"
		(preview.material_override as ShaderMaterial).set_shader_parameter("dim", 0.55)
		(preview.material_override as ShaderMaterial).set_shader_parameter("travelled", -1.0)
		root.add_child(preview)
		preview_signature = ""
	preview.show()
	if signature == preview_signature:
		return
	preview_signature = signature
	var low := mini(from, to)
	var route_id := "lf_route_entry" if low == 0 else ("lf_route_boss" if low == 12 else "lf_route_%02d_%02d" % [low, low + 1])
	var value: Variant = game.world_call("route_points", [route_id])
	var points: Array = []
	if value is PackedVector3Array and value.size() >= 2:
		for p in value:
			points.append(p)
	else:
		var a: Vector3 = game.target_position(String(squad.get("node", "")))
		var b: Vector3 = game.target_position(preview_target)
		if a == Vector3.INF or b == Vector3.INF:
			preview.hide()
			return
		points = [a, b]
	if to < from:
		points.reverse()
	var route := PathMotion.build(points)
	var total := float(route.total)
	var count := clampi(int(total / 1.4), 2, 300)
	var multimesh := preview.multimesh
	multimesh.instance_count = count
	for i in count:
		var d := total * float(i) / float(count - 1)
		var sample := PathMotion.sample(route, d)
		var p: Vector3 = game.ground(sample.position.x, sample.position.z) + Vector3.UP * 0.16
		multimesh.set_instance_transform(i, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * 0.8), p))
		multimesh.set_instance_custom_data(i, Color(d / maxf(total, 0.01), d, 0, 0))

func build_ribbon() -> MultiMeshInstance3D:
	var node := MultiMeshInstance3D.new()
	node.name = "RouteDots"
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.use_custom_data = true
	var dot := SphereMesh.new()
	dot.radius = 0.16
	dot.height = 0.2
	dot.radial_segments = 8
	dot.rings = 3
	multimesh.mesh = dot
	node.multimesh = multimesh
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, shadows_disabled;
uniform float travelled = 0.0;
uniform float dim = 1.0;
varying float along;
void vertex() {
	along = INSTANCE_CUSTOM.g;
}
void fragment() {
	float ahead = step(travelled, along);
	float wave = 0.55 + 0.45 * sin(along * 1.7 - TIME * 5.0);
	ALBEDO = mix(vec3(0.55, 0.42, 0.2), vec3(1.0, 0.8, 0.36), ahead);
	ALPHA = (0.25 + 0.75 * ahead) * wave * dim;
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
			choreo["key:" + site_id] = {"kind":"key_pickup", "site":site_id, "t":0.0, "from":prop.position, "actors":[]}

func on_cage_opened(site_id: String) -> void:
	if choreo.has("cage:" + site_id):
		return
	var people := []
	for person in game.client.poi(site_id).get("captives", []):
		people.append(String(person.get("id", "")))
	choreo["cage:" + site_id] = {"kind":"cage", "site":site_id, "t":0.0, "stage":0, "actors":people + ["squad_0"]}
	choreo["key:" + site_id] = {"kind":"key_insert", "site":site_id, "t":0.0, "actors":[]}

func start_guardian_death(site_id: String) -> void:
	if choreo.has("death:" + site_id):
		return
	choreo["death:" + site_id] = {"kind":"death", "site":site_id, "t":0.0, "actors":["guardian_" + site_id]}
	for person in game.client.poi(site_id).get("captives", []):
		var actor: Rig = rigs.get(String(person.get("id", "")))
		if actor != null and is_instance_valid(actor):
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
				done = run_cage(beat)
			"key_insert":
				done = run_key_insert(beat)
			"key_pickup":
				done = run_key_pickup(beat)
			"death":
				done = run_death(beat)
			"arrive":
				done = run_arrival(beat)
		if done:
			choreo.erase(key)

## art/rescue_animation_storyboard «4. UNLOCK»: soldier puts the seal into the socket, latch
## clears, door swings on its hinge, people leave one after another.
func run_cage(beat: Dictionary) -> bool:
	var site_id := String(beat.site)
	var t := float(beat.t)
	var cage: Rig = rigs.get("cage_" + site_id)
	var soldier: Rig = rigs.get("squad_0")
	var anchor: Dictionary = game.site_anchor(site_id)
	var cage_pos: Vector3 = anchor.get("cage", anchor.get("center", Vector3.ZERO))
	var basis := Basis(Vector3.UP, float(anchor.get("cage_yaw", 0.0)))
	var stage := int(beat.stage)
	if stage == 0:
		beat.stage = 1
		if soldier != null and is_instance_valid(soldier):
			var door_front: Vector3 = cage_pos + basis * Vector3(0.45, 0, 1.9)
			place("squad_0", soldier, door_front, PathMotion.yaw_of(cage_pos - door_front), 0.016, true)
			soldier.play(["lf_soldier_unlock", "Sword_Drill", "Idle"], 0.2, true)
	if stage == 1 and t >= 1.6:
		beat.stage = 2
		if cage != null and is_instance_valid(cage):
			cage.play(["lf_cage_unlock"], 0.0, true)
		game.audio.play_cue("fr_cage_latch")
	if stage == 2 and t >= 2.3:
		beat.stage = 3
		if cage != null and is_instance_valid(cage):
			cage.set_meta("pose", "open")
			if not cage.play(["lf_cage_gate_open"], 0.0, true):
				cage.set_meta("swing_from", t)
		game.audio.play_cue("fr_gate_creak")
	if cage != null and is_instance_valid(cage) and cage.has_meta("swing_from"):
		swing_door(cage, clampf((t - float(cage.get_meta("swing_from"))) / 1.6, 0.0, 1.0))
	if stage == 3 and t >= 3.9:
		beat.stage = 4
		if cage != null and is_instance_valid(cage) and not cage.has_meta("swing_from"):
			cage.play(["lf_cage_gate_settle", "lf_cage_gate_open"], 0.1)
		if soldier != null and is_instance_valid(soldier):
			soldier.play(["lf_soldier_help", "lf_soldier_idle", "Idle"], 0.25, true)
	var people: Array = beat.actors
	for index in people.size():
		var id := String(people[index])
		if id == "squad_0":
			continue
		var actor: Rig = rigs.get(id)
		if actor == null or not is_instance_valid(actor):
			continue
		var slot: Vector3 = cage_pos + basis * CAGE_SLOTS[index % 3]
		var door: Vector3 = cage_pos + basis * Vector3(0.0, 0, 1.25)
		var outside: Vector3 = cage_pos + basis * Vector3(-1.1 + 1.1 * index, 0, 2.6 + 0.3 * (index % 2))
		var sitter := (index + int(game.content.site_number(site_id))) % 3 == 0
		var start := 3.5 + 0.7 * index + (2.2 if sitter else 0.0)
		if t < 2.3:
			actor.play(["lf_civilian_react", "Idle"], 0.2)
		elif t < start:
			if sitter and t >= 3.5:
				actor.play(["lf_civilian_stand_up", "Idle"], 0.15)
			else:
				actor.play(CAGE_IDLES[1], 0.3)
			place(id, actor, slot, PathMotion.yaw_of(door - slot), 0.016, true)
		elif t < start + 2.8:
			var f := (t - start) / 2.8
			var p := slot.lerp(door, clampf(f * 2.0, 0.0, 1.0)) if f < 0.5 else door.lerp(outside, clampf((f - 0.5) * 2.0, 0.0, 1.0))
			var heading := (door - slot) if f < 0.5 else (outside - door)
			place(id, actor, p, PathMotion.yaw_of(heading), 0.016, true)
			actor.play(["lf_civilian_exit", "lf_civilian_follow", "Walk"], 0.2)
		else:
			place(id, actor, outside, PathMotion.yaw_of(basis * Vector3.BACK), 0.016, true)
			actor.play(["lf_civilian_wait", "Idle"], 0.3)
	return t > 3.5 + 0.7 * 3 + 2.2 + 3.2

func run_key_insert(beat: Dictionary) -> bool:
	var site_id := String(beat.site)
	var key_prop: Rig = rigs.get("artifact_" + site_id)
	var cage: Rig = rigs.get("cage_" + site_id)
	var soldier: Rig = rigs.get("squad_0")
	if key_prop == null or cage == null or not is_instance_valid(key_prop) or not is_instance_valid(cage):
		return float(beat.t) > 2.0
	var hand := (soldier.position + Vector3.UP * 1.15) if soldier != null and is_instance_valid(soldier) else cage.position + Vector3(0, 1.1, 2.2)
	var socket := socket_point(site_id, cage)
	var f := clampf((float(beat.t) - 0.4) / 1.2, 0.0, 1.0)
	key_prop.position = hand.lerp(socket, f * f * (3.0 - 2.0 * f))
	key_prop.rotation.y = lerpf(0.0, PI * 0.5, f)
	key_prop.set_active(key_prop.is_ready())
	if f >= 1.0 and float(beat.t) < 1.7:
		game.fx.burst_world(socket, "socket")
	return float(beat.t) > 1.8

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
		var captain: Rig = rigs.get("squad_0")
		if captain != null and is_instance_valid(captain):
			captain.play(["lf_soldier_help", "lf_soldier_unlock", "Idle"], 0.2, true)
	if float(beat.t) < 0.7:
		key_prop.set_active(key_prop.is_ready())
		game.fx.glow_world("artifact_" + site_id, key_prop.position)
		return false
	game.fx.glow_world("artifact_" + site_id, Vector3.INF)
	var f := clampf((float(beat.t) - 0.7) / 1.1, 0.0, 1.0)
	key_prop.position = (beat.from as Vector3).lerp(target + Vector3.UP * 1.2, f) + Vector3.UP * sin(PI * f) * 1.4
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
		actor.play(["Death"], 0.15, true)
	if t > 3.6:
		actor.scale = Vector3.ONE * clampf(1.0 - (t - 3.6) / 1.4, 0.01, 1.0)
	return t > 5.0

## art/rescue_animation_storyboard «5. ESCORT»: the three arrive at the settlement and thank.
func run_arrival(beat: Dictionary) -> bool:
	var t := float(beat.t)
	var home: Vector3 = game.target_position("lf_home_reception")
	var people: Array = beat.actors
	for index in people.size():
		var id := String(people[index])
		var actor: Rig = rigs.get(id)
		if actor == null or not is_instance_valid(actor):
			continue
		var spot := home + Vector3(-1.3 + 1.3 * index, 0, 1.6)
		place(id, actor, spot, PathMotion.yaw_of(Vector3(0, 0, 0) - spot), 0.016)
		if t < 2.6:
			actor.play(["lf_civilian_arrive", "lf_civilian_wait", "Idle"], 0.25)
		elif t < 5.0:
			actor.play(["lf_civilian_thank", "lf_civilian_wait", "Idle"], 0.25)
		else:
			actor.play(["lf_civilian_wait", "Idle"], 0.3)
		show_actor(actor, actor.position)
	if t > 0.2 and t < 0.3:
		var soldier: Rig = rigs.get("squad_0")
		if soldier != null and is_instance_valid(soldier):
			soldier.play(["lf_soldier_salute", "lf_soldier_idle", "Idle"], 0.2, true)
	return t > 8.0

func on_marker(actor: Node3D, clip_id: String, marker_name: String) -> void:
	var lower := marker_name.to_lower()
	if actor == rigs.get("horse") and (lower.contains("hoof") or lower.contains("contact") or lower.contains("foot")):
		var state: Dictionary = motion.get("horse", {})
		if float(state.get("speed", 0.0)) > 0.3 and actor.visible:
			game.audio.hoof(actor.global_position)
	elif clip_id == "lf_soldier_attack" and lower.contains("contact"):
		game.fx.burst_world(actor.global_position + Vector3.UP * 1.1 + actor.global_basis.z * 0.9, "hit")
