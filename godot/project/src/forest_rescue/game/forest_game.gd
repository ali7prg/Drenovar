extends Node
## «Лес потерянных» gameplay layer coordinator (hooks live in src/main.gd, marked FOREST_RESCUE).
## Owns: authored content, adventure client (state/commands/events), HUD overlay, panels,
## mechanism UI, intro director, actors under forest_world.actors_root(), reward FX, audio.
## Presentation only: the server decides every success, reward, position and timer.

const Content = preload("res://src/forest_rescue/game/adventure_content.gd")
const Client = preload("res://src/forest_rescue/game/adventure_client.gd")
const Hud = preload("res://src/forest_rescue/game/adventure_hud.gd")
const Panels = preload("res://src/forest_rescue/game/adventure_panels.gd")
const MechanismUi = preload("res://src/forest_rescue/game/mechanism_ui.gd")
const IntroDirector = preload("res://src/forest_rescue/game/intro_director.gd")
const Actors = preload("res://src/forest_rescue/game/actor_director.gd")
const RewardFx = preload("res://src/forest_rescue/game/reward_fx.gd")
const Audio = preload("res://src/forest_rescue/game/adventure_audio.gd")
const PathMotion = preload("res://src/forest_rescue/game/path_motion.gd")
const SETTINGS_PATH := "user://forest_rescue_v1.cfg"
const BASE_HALF := 56.0
const BOSS_TARGET := "lf_boss_ancient_maw"
const HORSE_TARGET := "lf_horse_origin"
const HOME_TARGET := "lf_home_reception"

var main: Node
var content: Content
var client: Client
var hud: Hud
var panels: Panels
var mech: MechanismUi
var intro: IntroDirector
var actors: Actors
var fx: RewardFx
var audio: Audio
var stage: Node3D
var world: Node3D
var fallback_root: Node3D
var reduced_motion := false
var sound_enabled := true
var foreground := true
var last_state_ref: Variant = null
var applied_signature := ""
var settle_polled_for := -1.0
var settle_poll_ticks := 0
var dwell_started := 0
var locked_shown_for_excursion := false
var guide_cache: Dictionary = {}
var guide_signature := ""
var acting := false
var anchors_cache: Dictionary = {}
var site_post_steps: Dictionary = {}
var boss_arena_state := ""
var entered_session := false
var mirrored_message := ""
var guide_timer := 0.0

func setup(host: Node) -> void:
	main = host
	name = "ForestRescueGame"
	load_settings()
	content = Content.new()
	content.load_all()
	client = Client.new(main, content)
	client.events_arrived.connect(on_events)
	client.network_status.connect(on_network)
	var hud_root: Control = main.dimmer.get_parent()
	hud = Hud.new()
	hud_root.add_child(hud)
	hud_root.move_child(hud, main.dimmer.get_index())
	hud.setup(self)
	mech = MechanismUi.new()
	hud_root.add_child(mech)
	hud_root.move_child(mech, main.dimmer.get_index())
	mech.setup(self)
	panels = Panels.new(self)
	audio = Audio.new()
	add_child(audio)
	audio.setup(self)
	fx = RewardFx.new()
	add_child(fx)
	fx.setup(self)
	actors = Actors.new()
	add_child(actors)
	actors.setup(self)
	intro = IntroDirector.new()
	add_child(intro)
	intro.setup(self)
	refresh_hud()

# ------------------------------------------------------------------ hooks from main.gd
func on_state(state: Dictionary) -> void:
	last_state_ref = state
	track_stage()
	var previous := client.adv
	client.ingest(state)
	enter_session_once()
	sync_world()
	actors.on_state(client.adv, previous)
	mech.on_state()
	refresh_hud()
	intro.evaluate()

## Returns true when the tap was consumed by the adventure (POI, landmark or locked card).
func pick(screen_position: Vector2) -> bool:
	if not city_active():
		return false
	if intro.presenting():
		return true
	if client.unlocked():
		var picked: Dictionary = actors.pick(screen_position)
		if picked.is_empty():
			return false
		on_marker_picked(picked)
		return true
	if existing_marker_near(screen_position):
		return false
	var ground: Vector3 = stage.ground_at(screen_position)
	if inside_base(ground):
		return false
	hud.locked_dismissed = false
	hud.show_locked(locked_reason())
	return true

func add_menu_entries(parent: Container) -> void:
	if not client.available():
		return
	var entry := Button.new()
	entry.text = content.text("title")
	entry.custom_minimum_size = Vector2(48, 42)
	entry.pressed.connect(open_journal)
	parent.add_child(entry)

## CONTRACT v1.1 «Session entry»: once per app launch, POST /api/session/new with the existing
## settlement counts as a new foreground entry (an interrupted intro becomes an invitation).
func enter_session_once() -> void:
	if entered_session or not client.known or not main.connected() or main.player_id.is_empty():
		return
	entered_session = true
	var response: Dictionary = await main.request("session/new", {})
	if response.has("city") and response.has("world"):
		main.accept(response)
	elif not response.has("error"):
		main.poll_account_state()

# ------------------------------------------------------------------ world access (WORLD_API.md)
func city_active() -> bool:
	return is_instance_valid(main.stage) and main.map_name == "city" and not main.scene_loading

func track_stage() -> void:
	var current: Node3D = main.stage if is_instance_valid(main.stage) else null
	if current != stage:
		stage = current
		world = null
		applied_signature = ""
		anchors_cache.clear()
		site_post_steps.clear()
		boss_arena_state = ""
		actors.on_stage_changed()
	if is_instance_valid(stage) and main.map_name == "city":
		var candidate: Variant = stage.get("forest_world")
		var resolved: Node3D = candidate if candidate is Node3D and is_instance_valid(candidate) else null
		if resolved != world:
			world = resolved
			applied_signature = ""
			anchors_cache.clear()
			if world != null:
				if world.has_method("set_reduced_motion"):
					world.set_reduced_motion(reduced_motion)
				if world.has_signal("fog_reveal_finished") and not world.fog_reveal_finished.is_connected(on_fog_revealed):
					world.fog_reveal_finished.connect(on_fog_revealed)
			actors.on_stage_changed()
			sync_world()

func world_call(method: String, args: Array = []) -> Variant:
	if world != null and is_instance_valid(world) and world.has_method(method):
		return world.callv(method, args)
	return null

func sync_world() -> void:
	if world == null or not is_instance_valid(world):
		return
	var adv := client.adv if client.available() else {}
	var fog: Dictionary = adv.get("fog", {})
	var camp: Dictionary = adv.get("campaign", {})
	var signature := "%s|%s|%s|%s|%s|%s" % [str(client.available()), str(adv.get("access", {}).get("unlocked", false)),
		str(fog.get("revision", -1)), str(camp.get("revision", -1)), str(adv.get("pois", []).size()), str(adv.get("serverTime", 0))]
	if signature == applied_signature:
		return
	applied_signature = signature
	world_call("apply_adventure", [adv])
	for entry in camp.get("sites", []):
		var id := String(entry.get("id", ""))
		var step := int(entry.get("step", 0))
		if site_post_steps.get(id, -1) != step:
			site_post_steps[id] = step
			world_call("set_site_post_state", [id, step])
	var boss_state := String(adv.get("boss", {}).get("state", "locked"))
	if boss_state != boss_arena_state and not adv.is_empty():
		boss_arena_state = boss_state
		world_call("set_boss_arena_state", [boss_state])

func actors_root() -> Node3D:
	var value: Variant = world_call("actors_root")
	if value is Node3D:
		return value
	return ensure_fallback_root()

func props_root() -> Node3D:
	var value: Variant = world_call("props_root")
	if value is Node3D:
		return value
	return ensure_fallback_root()

func ensure_fallback_root() -> Node3D:
	if not is_instance_valid(stage):
		return null
	if not is_instance_valid(fallback_root) or fallback_root.get_parent() != stage:
		fallback_root = Node3D.new()
		fallback_root.name = "ForestRescueActorsFallback"
		stage.add_child(fallback_root)
	return fallback_root

func ground(x: float, z: float) -> Vector3:
	var value: Variant = world_call("ground_point", [x, z])
	if value is Vector3:
		return value
	if is_instance_valid(stage) and stage.has_method("ground_point"):
		return stage.ground_point(Vector3(x, 0, z))
	return Vector3(x, 0, z)

func fog_clear(p: Vector3) -> bool:
	var value: Variant = world_call("fog_cleared_at", [p.x, p.z])
	if value is bool:
		return value
	return true

func inside_base(p: Vector3) -> bool:
	if not client.unlocked():
		return maxf(absf(p.x), absf(p.z)) <= BASE_HALF
	var value: Variant = world_call("fog_cleared_at", [p.x, p.z])
	if value is bool:
		return value
	return maxf(absf(p.x), absf(p.z)) <= BASE_HALF

## Server-side XZ of a targetId from the projection (POIs, POI targets, landmarks), or INF.
func server_xz(target_id: String) -> Vector3:
	var adv := client.adv
	for poi in adv.get("pois", []):
		if String(poi.get("id", "")) == target_id:
			return Vector3(float(poi.get("x", 0)), float(poi.get("y", 0)), float(poi.get("z", 0)))
		var targets: Dictionary = poi.get("targets", {})
		for key in targets:
			var entry: Variant = targets[key]
			if entry is Dictionary and String(entry.get("id", "")) == target_id:
				return Vector3(float(entry.get("x", 0)), float(entry.get("y", 0)), float(entry.get("z", 0)))
			if entry is Array:
				for item in entry:
					if item is Dictionary and String(item.get("id", "")) == target_id:
						return Vector3(float(item.get("x", 0)), float(item.get("y", 0)), float(item.get("z", 0)))
	return Vector3.INF

## World position of a CONTRACT targetId: server XZ first, world layer next, authored fallback.
func target_position(target_id: String) -> Vector3:
	if target_id.is_empty():
		return Vector3.INF
	var xz := server_xz(target_id)
	if xz != Vector3.INF:
		return ground(xz.x, xz.z)
	var value: Variant = world_call("poi_position", [target_id])
	if value is Vector3 and value != Vector3.ZERO and value != Vector3.INF:
		return value
	var base_id := target_id.get_slice(":", 0)
	if target_id.contains(":"):
		var anchor := site_anchor(base_id)
		var part := target_id.get_slice(":", 1)
		if part == "landmark":
			var marks: Dictionary = anchor.get("landmarks", {})
			if marks.get(target_id.get_slice(":", 2)) is Vector3:
				return marks[target_id.get_slice(":", 2)]
		if anchor.get(part) is Vector3:
			return anchor[part]
	if base_id.begins_with("lf_key_"):
		var site_id := "lf_site_" + base_id.trim_prefix("lf_key_")
		return site_anchor(site_id).get("artifact", Vector3.INF)
	var known := {HORSE_TARGET:Vector2(-8, -55), HOME_TARGET:Vector2(-8, -52), "lf_bridge_crossing":Vector2(90.5, 20),
		BOSS_TARGET:Vector2(75, -86)}
	if known.has(base_id):
		var flat: Vector2 = known[base_id]
		return ground(flat.x, flat.y)
	var site := content.site(base_id)
	if not site.is_empty():
		var center: Array = site.get("layoutCenterXZReference", [0, 0])
		return ground(float(center[0]), float(center[1]))
	return Vector3.INF

## Site anchors from the world layer; authored atlas offsets as a fallback.
func site_anchor(site_id: String) -> Dictionary:
	var poi := client.poi(site_id)
	var targets: Dictionary = poi.get("targets", {})
	var cache_key := site_id + ":" + str(targets.size()) + ":" + str((targets.get("landmarks", []) as Array).size() if targets.get("landmarks") is Array else 0)
	if anchors_cache.has(cache_key):
		return anchors_cache[cache_key]
	var value: Variant = world_call("site_anchor", [site_id])
	var anchor: Dictionary = (value as Dictionary).duplicate() if value is Dictionary and not value.is_empty() else {}
	if anchor.is_empty():
		var site := content.site(site_id)
		var center_xz: Array = site.get("layoutCenterXZReference", [0, 0])
		pass
		var cx := float(poi.get("x", center_xz[0]))
		var cz := float(poi.get("z", center_xz[1]))
		var side := -1.0 if int(site.get("number", 1)) % 2 == 1 else 1.0
		anchor = {"center":ground(cx, cz), "cage":ground(cx, cz - 2.0), "guardian":ground(cx, cz + 3.0),
			"artifact":ground(cx + side * 3.5, cz - 1.0), "approach":ground(cx, cz + 7.5),
			"plate_left":ground(cx - 3.0, cz + 0.8), "plate_right":ground(cx + 3.0, cz + 0.8), "cage_yaw":0.0, "landmarks":{}}
		var solution: Array = site.get("artifact", {}).get("puzzle", {}).get("solution", [])
		var marks := {}
		for i in solution.size():
			var angle := -2.2 + 1.1 * i
			marks[String(solution[i])] = ground(cx + cos(angle) * 5.2, cz + sin(angle) * 5.2)
		anchor.landmarks = marks
	# Authoritative server node positions win over authored offsets (same XZ the squad walks to).
	for part in ["center", "cage", "guardian", "plate_left", "plate_right"]:
		if targets.get(part) is Dictionary:
			anchor[part] = ground(float(targets[part].get("x", 0)), float(targets[part].get("z", 0)))
	if targets.get("key") is Dictionary:
		anchor["artifact"] = ground(float(targets.key.get("x", 0)), float(targets.key.get("z", 0)))
	if targets.get("landmarks") is Array:
		var marks_now := {}
		for mark in targets.landmarks:
			marks_now[String(mark.get("symbol", ""))] = ground(float(mark.get("x", 0)), float(mark.get("z", 0)))
		anchor["landmarks"] = marks_now
	if not anchor.has("approach") and anchor.get("center") is Vector3 and anchor.get("guardian") is Vector3:
		anchor["approach"] = anchor.center + (anchor.guardian - anchor.center).normalized() * 7.5
	anchors_cache[cache_key] = anchor
	return anchor

func pin(id: String, center: Vector3, radius: float) -> void:
	world_call("pin_area", [id, center, radius])

func unpin(id: String) -> void:
	world_call("unpin_area", [id])

func existing_marker_near(screen_position: Vector2) -> bool:
	for marker in stage.place_markers + stage.army_markers + stage.creature_markers:
		if stage.camera.is_position_behind(marker.position):
			continue
		if stage.camera.unproject_position(marker.position).distance_to(screen_position) < 38.0:
			return true
	for tree in stage.selectable_trees:
		var p: Vector3 = stage.array_point(tree.p) + Vector3.UP
		if p.distance_squared_to(stage.camera_target) > 68.0 * 68.0 or stage.camera.is_position_behind(p):
			continue
		if stage.camera.unproject_position(p).distance_to(screen_position) < 18.0:
			return true
	return false

func locked_reason() -> String:
	if client.known and not client.available():
		return "error"
	return "unavailable" if not client.available() else "locked"

# ------------------------------------------------------------------ frame loop
func _process(delta: float) -> void:
	track_stage()
	var active := city_active()
	hud.visible = active
	mech.visible = active and mech.is_open()
	if not active:
		audio.set_forest_ambience(false)
		return
	update_locked_dwell()
	update_visibility()
	actors.tick(delta)
	hud.tick(delta)
	intro.tick(delta)
	mech.tick(delta)
	schedule_settle_poll()
	# The next-step guide is cheap but string-heavy: refresh at 5 Hz or right after a new state.
	guide_timer -= delta
	if guide_timer <= 0.0 or guide_signature.is_empty():
		guide_timer = 0.2
		var guide_now := guide()
		var signature := JSON.stringify([guide_now.get("caption", ""), guide_now.get("hint", ""), guide_now.get("enabled", false), guide_now.get("title", "")])
		if signature != guide_signature:
			apply_guide(guide_now)
	audio.set_forest_ambience(client.unlocked() and foreground and camera_over_forest())

func camera_over_forest() -> bool:
	if not is_instance_valid(stage):
		return false
	var p: Vector3 = stage.camera_target
	return maxf(absf(p.x), absf(p.z)) > BASE_HALF - 8.0

func update_visibility() -> void:
	var modal_open: bool = main.modal.visible
	var unlocked := client.unlocked()
	var presenting := intro.presenting()
	var show_bar := unlocked and not modal_open and not presenting and not mech.is_open()
	if hud.bar.visible != show_bar:
		hud.bar.visible = show_bar
		hud.layout()
	hud.hint.visible = show_bar and not hud.hint_label.text.is_empty()
	# The adventure row covers the bottom message line: mirror its text as a toast instead.
	main.message.modulate.a = 0.0 if show_bar else 1.0
	if show_bar and main.message.text != mirrored_message:
		mirrored_message = main.message.text
		if not mirrored_message.is_empty():
			hud.toast(mirrored_message, "info", 3.5)
	if modal_open or presenting or unlocked:
		if hud.locked_card.visible:
			hud.hide_locked()

func update_locked_dwell() -> void:
	if client.unlocked() or intro.presenting():
		dwell_started = 0
		return
	var camera_target: Vector3 = stage.camera_target
	var outside := not inside_base(camera_target)
	var still: bool = stage.camera_target.distance_squared_to(stage.target) < 0.01 and main.fingers.is_empty() and not main.dragging
	if outside:
		if main.modal.visible:
			return
		if still:
			if dwell_started == 0:
				dwell_started = Time.get_ticks_msec()
			if Time.get_ticks_msec() - dwell_started >= 200 and not hud.locked_card.visible and not hud.locked_dismissed and not locked_shown_for_excursion:
				locked_shown_for_excursion = true
				hud.show_locked(locked_reason())
		else:
			dwell_started = 0
	else:
		dwell_started = 0
		locked_shown_for_excursion = false
		hud.locked_dismissed = false
		if hud.locked_card.visible:
			hud.hide_locked()

func schedule_settle_poll() -> void:
	if not client.available():
		return
	var settle := client.next_settle_ms()
	if settle == INF:
		return
	var now := client.server_now()
	if now < settle + 250.0:
		return
	var ticks := Time.get_ticks_msec()
	if settle_polled_for == settle and ticks - settle_poll_ticks < 1500:
		return
	if main.busy or main.polling_state or client.in_flight:
		return
	settle_polled_for = settle
	settle_poll_ticks = ticks
	main.poll_account_state()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_APPLICATION_PAUSED:
		foreground = false
		if intro != null:
			intro.on_background()
		if audio != null:
			audio.on_background()
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN or what == NOTIFICATION_APPLICATION_RESUMED:
		foreground = true

# ------------------------------------------------------------------ guide: next step & hints
func total_units(units: Dictionary) -> int:
	var count := 0
	for id in units:
		count += int(units[id])
	return count

func site_name(site_id: String) -> String:
	return String(content.site(site_id).get("name", site_id))

func target_name(target_id: String) -> String:
	var base := target_id.get_slice(":", 0)
	if base == HORSE_TARGET:
		return String(content.campaign.get("prologue", {}).get("title", content.text("hud.horse")))
	if base == HOME_TARGET:
		return content.text("hud.home")
	if base == BOSS_TARGET:
		return String(content.line("boss_enter").get("speaker", content.text("hud.arena")))
	if base == "lf_bridge_crossing":
		return content.text("hud.bridge")
	if base.begins_with("lf_key_"):
		var site_id := "lf_site_" + base.trim_prefix("lf_key_")
		return String(content.site(site_id).get("artifact", {}).get("name", site_name(site_id)))
	return site_name(base)

func guardian_ready(site_id: String) -> Dictionary:
	var spec: Dictionary = content.site(site_id).get("guardian", {})
	var required := int(spec.get("requiredHall", 1))
	return {"ok":client.hall_level() >= required, "required":required}

## Computes the contextual next step from the authoritative projection only.
func guide() -> Dictionary:
	var result := {"title":"", "hint":"", "caption":content.text("hud.continue"), "enabled":false, "action":"",
		"fields":{}, "target":"", "progress":Vector2i(0, 3), "reward":{}, "panel":""}
	if not client.unlocked():
		return result
	var adv := client.adv
	var camp := client.campaign()
	var squad := client.squad()
	var units: Dictionary = squad.get("units", {})
	var node := String(squad.get("node", ""))
	var moving: bool = squad.get("move") is Dictionary
	var busy: Variant = squad.get("busy")
	var current_phase := client.phase()
	var fight := client.battle()
	var next: Variant = adv.get("nextTask")
	var next_site := ""
	var next_task := ""
	if next is Dictionary:
		next_site = String(next.siteId) if next.get("siteId") != null else ""
		next_task = String(next.taskId) if next.get("taskId") != null else ""
	if next_site != "":
		result.reward = content.task_reward(next_site, "escort_home")
		result.title = String(content.task(next_site, next_task).get("title", site_name(next_site)))
		var site_entry := client.site_state(next_site)
		result.progress = Vector2i(int(site_entry.get("step", 0)), 5)
	if current_phase == "prologue":
		result.title = String(content.campaign.get("prologue", {}).get("title", ""))
		result.reward = content.prologue_reward()
		result.progress = Vector2i(1 if total_units(units) > 0 else 0, 3)
		if node == HORSE_TARGET and not moving:
			result.progress.x = 2
	elif current_phase in ["boss_unlocked", "boss_active"]:
		result.title = String(content.campaign.get("boss", {}).get("displayName", ""))
		result.reward = content.final_reward()
		# Three dots = the three authored boss phases (hunt, fury, last stand).
		var phase_ids := ["hunt", "fury", "last_stand"]
		var reached := phase_ids.find(String(adv.get("boss", {}).get("phase", "hunt"))) + 1 if current_phase == "boss_active" else 0
		result.progress = Vector2i(clampi(reached, 0, 3), 3)
	elif current_phase == "completed":
		result.title = content.text("ending.title")
		result.reward = content.final_reward()
	if bool(camp.get("paused", false)):
		result.hint = content.text("pause.note")
		result.caption = content.text("hud.continue")
		result.enabled = true
		result.action = "resume"
		return result
	if not fight.is_empty() and String(fight.get("outcome", "pending")) == "pending" and bool(fight.get("active", true)):
		result.hint = content.text("boss.warning") if String(fight.get("species", "")) == "ancient_maw" else String(content.site(String(fight.get("siteId", ""))).get("guardianTactics", ""))
		return result
	if moving:
		var move: Dictionary = squad.move
		var left := maxi(0, ceili((float(move.get("arriveAt", 0)) - client.server_now()) / 1000.0))
		result.hint = "%s → %s · %d:%02d" % [content.text("hud.squad"), target_name(String(move.get("targetId", ""))), left / 60, left % 60]
		result.target = String(move.get("targetId", ""))
		return result
	if total_units(units) <= 0:
		result.hint = content.text("objective.prologue") if current_phase == "prologue" else content.text("error.insufficientSquad")
		result.enabled = true
		result.panel = "squad"
		return result
	if busy != null and String(busy) == "escort":
		var walk := client.escort()
		if String(walk.get("state", "")) == "home":
			return finish_with(result, "button.escort", "attempt_task", {"siteId":String(walk.get("siteId", next_site)), "taskId":"escort_home"}, content.text("cage.released"))
		result.hint = content.text("cage.released")
		result.target = HOME_TARGET
		return result
	match current_phase:
		"prologue":
			result.target = HORSE_TARGET
			if node != HORSE_TARGET:
				return finish_with(result, "button.follow", "move", {"targetId":HORSE_TARGET}, content.text("objective.prologue"))
			return finish_with(result, "button.follow", "discover_horse", {}, String(content.campaign.get("prologue", {}).get("completionText", "")))
		"rescue":
			if next_site.is_empty():
				result.hint = content.text("act.locked")
				return result
			return rescue_step(result, next_site, next_task, node)
		"boss_unlocked", "boss_active":
			result.target = BOSS_TARGET
			var required := int(adv.get("boss", {}).get("requiredHall", 5))
			if client.hall_level() < required:
				result.hint = content.text("site.requiredHall", {"level":required}) + " " + content.text("boss.warning")
				return result
			# The server names the finale step: begin_boss → engage_boss → finish_boss.
			var finale := next_task if next_task in ["begin_boss", "engage_boss", "finish_boss"] else ("begin_boss" if current_phase == "boss_unlocked" else "engage_boss")
			var boss_fight := not fight.is_empty() and (String(fight.get("kind", "")) == "boss" or String(fight.get("species", "")) == "ancient_maw")
			if finale == "finish_boss" or (boss_fight and String(fight.get("outcome", "")) == "victory"):
				return finish_with(result, "boss.begin", "finish_boss", {}, content.text("objective.boss_active"))
			if node != BOSS_TARGET:
				return finish_with(result, "boss.begin", "move", {"targetId":BOSS_TARGET}, content.text("boss.noPrisoners") if current_phase == "boss_unlocked" else content.text("objective.boss_active"))
			if finale == "begin_boss":
				return finish_with(result, "boss.begin", "begin_boss", {}, content.text("boss.warning"))
			return finish_with(result, "boss.begin", "engage_boss", {}, content.text("objective.boss_active"))
		"completed":
			result.hint = content.text("objective.completed")
			result.enabled = true
			result.panel = "journal"
			return result
	return result

func rescue_step(result: Dictionary, site_id: String, task_id: String, node: String) -> Dictionary:
	var site := content.site(site_id)
	var poi := client.poi(site_id)
	var key_target := String(site.get("artifact", {}).get("id", ""))
	result.target = site_id
	match task_id:
		"discover":
			if node != site_id:
				return finish_with(result, "button.inspect", "move", {"targetId":site_id}, String(content.task(site_id, "discover").get("objective", "")))
			return finish_with(result, "button.inspect", "attempt_task", {"siteId":site_id, "taskId":"discover"}, String(content.task(site_id, "discover").get("objective", "")))
		"recover_artifact":
			var mechanism: Dictionary = poi.get("mechanism", {})
			var key_entry: Variant = poi.get("targets", {}).get("key")
			if key_entry is Dictionary:
				key_target = String(key_entry.get("id", key_target))
			result.target = key_target
			result.progress = Vector2i(int(mechanism.get("progress", 0)), int(mechanism.get("length", 3)))
			var clue := String(site.get("artifact", {}).get("puzzle", {}).get("clue", content.text("artifact.missing")))
			if bool(mechanism.get("solved", false)):
				result.progress.x = result.progress.y
				if node != key_target:
					return finish_with(result, "button.recover", "move", {"targetId":key_target}, content.text("artifact.bound"))
				return finish_with(result, "button.recover", "attempt_task", {"siteId":site_id, "taskId":"recover_artifact"}, content.text("artifact.bound"))
			if not node.begins_with(site_id) and node != key_target:
				result.target = site_id
				return finish_with(result, "button.recover", "move", {"targetId":site_id}, content.text("artifact.missing"))
			result = finish_with(result, "button.recover", "", {}, clue)
			result.panel = "mechanism"
			return result
		"defeat_guardian":
			result.target = site_id + ":guardian"
			var guardian: Dictionary = poi.get("guardian", {})
			var gate := guardian_ready(site_id)
			if String(guardian.get("state", "alive")) == "defeated":
				return finish_with(result, "button.attack", "attempt_task", {"siteId":site_id, "taskId":"defeat_guardian"}, String(content.task(site_id, "defeat_guardian").get("title", "")))
			if not gate.ok:
				result.hint = content.text("site.requiredHall", {"level":gate.required})
				return result
			if node != site_id + ":guardian" and node != site_id:
				return finish_with(result, "button.attack", "move", {"targetId":site_id + ":guardian"}, content.text("guardian.required"))
			return finish_with(result, "button.attack", "engage_guardian", {"siteId":site_id}, String(site.get("guardianTactics", "")))
		"unlock_cage":
			result.target = site_id + ":cage"
			if node != site_id + ":cage":
				return finish_with(result, "button.unlock", "move", {"targetId":site_id + ":cage"}, String(content.task(site_id, "unlock_cage").get("objective", "")))
			return finish_with(result, "button.unlock", "attempt_task", {"siteId":site_id, "taskId":"unlock_cage"}, String(content.task(site_id, "unlock_cage").get("objective", "")))
		"escort_home":
			result.target = HOME_TARGET
			var walk := client.escort()
			if not walk.is_empty() and String(walk.get("siteId", "")) == site_id and String(walk.get("state", "")) == "home":
				return finish_with(result, "button.escort", "attempt_task", {"siteId":site_id, "taskId":"escort_home"}, content.text("cage.released"))
			return finish_with(result, "button.escort", "escort_start", {"siteId":site_id}, content.text("cage.released"))
	return result

func finish_with(result: Dictionary, label_key: String, action: String, fields: Dictionary, detail: String) -> Dictionary:
	result.action = action
	result.fields = fields
	result.enabled = true
	var label := content.text(label_key)
	result.hint = label + ": " + detail if not detail.is_empty() else label
	result.label = label
	return result

func apply_guide(value: Dictionary) -> void:
	guide_cache = value
	guide_signature = JSON.stringify([value.get("caption", ""), value.get("hint", ""), value.get("enabled", false), value.get("title", "")])
	if not client.unlocked():
		hud.set_hint("")
		hud.set_arrow(Vector3.INF, "")
		actors.set_beacon("")
		return
	var progress: Vector2i = value.get("progress", Vector2i(0, 3))
	hud.set_task(String(value.get("title", "")), progress.x, progress.y)
	hud.set_reward(content.text("hud.rewardFor"), value.get("reward", {}))
	hud.set_continue(String(value.get("caption", content.text("hud.continue"))), bool(value.get("enabled", false)))
	hud.set_hint(String(value.get("hint", "")))
	var target := String(value.get("target", ""))
	actors.set_beacon(target)
	actors.set_preview(target if String(value.get("action", "")) == "move" else "")
	var position := target_position(target) if not target.is_empty() else Vector3.INF
	hud.set_arrow(position + Vector3.UP * 1.5 if position != Vector3.INF else Vector3.INF, target_name(target) if not target.is_empty() else "")

func refresh_hud() -> void:
	guide_signature = ""
	if hud != null:
		hud.layout()

# ------------------------------------------------------------------ actions
func on_continue_pressed() -> void:
	var step := guide()
	if not bool(step.get("enabled", false)):
		return
	var panel := String(step.get("panel", ""))
	if panel == "squad":
		panels.open_squad()
		return
	if panel == "journal":
		open_journal()
		return
	if panel == "mechanism":
		var site_id := String(client.adv.get("nextTask", {}).get("siteId", ""))
		mech.open(site_id)
		return
	var action := String(step.get("action", ""))
	if action.is_empty():
		return
	await request_action(action, step.get("fields", {}))

func on_route_pressed() -> void:
	panels.open_route()

func on_squad_pressed() -> void:
	panels.open_squad()

func open_journal() -> void:
	panels.open_journal()

func open_rewards() -> void:
	panels.open_rewards()

func open_town_hall() -> void:
	hud.hide_locked()
	for building in main.state.city.get("buildings", []):
		if main.building_definition(building.type).get("base", building.type) == "ECO-05":
			main.center_city()
			main.inspect_building(building)
			return

## Waits (bounded) until no adventure command is in flight.
func wait_idle() -> void:
	var waited := 0
	while (acting or client.in_flight) and waited < 900:
		await get_tree().process_frame
		waited += 1

## Sends one authoritative command; UI feedback only. Returns the client result.
func request_action(action: String, fields: Dictionary = {}, kind := "adventure") -> Dictionary:
	# Commands are serialized: a tap during another command waits for it (bounded), never drops.
	var waited := 0
	while (acting or client.in_flight) and waited < 900:
		await get_tree().process_frame
		waited += 1
	if acting or client.in_flight:
		return {"ok":false, "error":"LOCAL_BUSY", "message":content.text("network.pending")}
	acting = true
	hud.continue_button.disabled = true
	var result: Dictionary = await client.send(action, fields, kind)
	acting = false
	guide_signature = ""
	if not bool(result.get("ok", false)):
		var message := String(result.get("message", ""))
		if not message.is_empty():
			hud.toast(message, "network" if result.get("retry", false) else "error", 5.0)
		if result.get("retry", false):
			panels.offer_retry()
	return result

func retry_last() -> void:
	if not client.has_pending_retry() or acting:
		return
	acting = true
	var result: Dictionary = await client.retry_pending()
	acting = false
	guide_signature = ""
	if not bool(result.get("ok", false)) and not String(result.get("message", "")).is_empty():
		hud.toast(String(result.message), "network" if result.get("retry", false) else "error", 5.0)

func on_marker_picked(marker: Dictionary) -> void:
	var kind := String(marker.get("kind", ""))
	match kind:
		"landmark":
			mech.landmark_tapped(String(marker.get("symbol", "")))
		"site", "cage", "guardian", "artifact":
			panels.open_site(String(marker.get("site", marker.get("id", ""))))
		"horse":
			panels.open_horse()
		"squad":
			panels.open_squad()
		"boss":
			panels.open_boss()

# ------------------------------------------------------------------ events and feedback
func on_events(events: Array) -> void:
	for event in events:
		var kind := String(event.get("type", ""))
		match kind:
			"task_completed":
				var site_id := String(event.get("siteId", ""))
				var task_id := String(event.get("taskId", ""))
				hud.toast(String(content.task(site_id, task_id).get("resultText", "")), "reward", 6.0)
				var reward: Dictionary = event.get("reward", content.task_reward(site_id, task_id))
				fx.award(reward, actors.squad_focus())
				if task_id == "recover_artifact":
					audio.play_cue("fr_artifact_discovery")
					fx.burst_world(actors.artifact_spot(site_id), "discovery")
				elif task_id == "escort_home":
					audio.play_cue("fr_people_rescued")
				else:
					audio.play_cue("fr_large_reward" if int(reward.get("food", 0)) >= 20000 else "fr_artifact_discovery")
				actors.on_task_completed(site_id, task_id)
			"reward_escrowed":
				hud.toast(content.text("reward.reserve"), "reward", 3.5)
			"transfer_rewards":
				var moved: Dictionary = (event.get("resources", {}) as Dictionary).duplicate()
				moved["storageFull"] = bool(event.get("storageFull", false))
				panels.on_transfer(moved)
			"horse_joined":
				hud.toast(String(content.campaign.get("prologue", {}).get("completionText", "")), "reward", 6.0)
				audio.play_cue("fr_large_reward")
				fx.award(content.prologue_reward(), actors.squad_focus())
			"mechanism_progress":
				mech.on_progress(String(event.get("siteId", "")), bool(event.get("ok", false)))
			"battle_report":
				actors.on_battle_report(String(event.get("reportId", "")))
			"cage_opened":
				actors.on_cage_opened(String(event.get("siteId", "")))
			"escort_arrived":
				actors.on_escort_arrived(String(event.get("siteId", "")))
			"boss_unlocked":
				hud.show_banner(content.text("objective.boss_unlocked"), content.text("boss.noPrisoners"), 5.0)
				audio.play_cue("fr_distant_rumble")
			"boss_started":
				hud.show_banner(String(content.campaign.get("boss", {}).get("displayName", "")), String(content.line("boss_enter").get("text", "")), 5.0)
				audio.play_cue("fr_distant_rumble")
				actors.on_boss_started()
			"boss_phase":
				var phase_id := String(event.get("phase", ""))
				hud.show_banner(content.text("boss.phase." + phase_id), "", 3.0)
				actors.on_boss_phase(phase_id)
			"campaign_completed":
				hud.show_banner(content.text("ending.title"), content.text("boss.victory"), 7.0)
				audio.play_cue("fr_large_reward")
			"intro_present":
				intro.on_intro_present(event)
			"fog_revealed":
				pass

func on_network(status: String, detail: String) -> void:
	if status in ["retrying", "offline"]:
		hud.toast(detail, "network", 4.0)

func on_fog_revealed(_revision: int) -> void:
	pass

# ------------------------------------------------------------------ settings
func load_settings() -> void:
	var file := ConfigFile.new()
	if file.load(SETTINGS_PATH) == OK:
		reduced_motion = bool(file.get_value("presentation", "reduced_motion", false))
		sound_enabled = bool(file.get_value("presentation", "sound", true))

func save_settings() -> void:
	var file := ConfigFile.new()
	file.set_value("presentation", "reduced_motion", reduced_motion)
	file.set_value("presentation", "sound", sound_enabled)
	file.save(SETTINGS_PATH)

func set_reduced_motion(on: bool) -> void:
	reduced_motion = on
	save_settings()
	world_call("set_reduced_motion", [on])

func set_sound(on: bool) -> void:
	sound_enabled = on
	save_settings()
	audio.apply_settings()
