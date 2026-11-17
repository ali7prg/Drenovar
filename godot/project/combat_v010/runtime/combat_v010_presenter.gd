extends RefCounted

# Combat v0.1.0 pose presenter (feature flag, default OFF).
#
# When enabled, a field soldier or a creature gets the combat_v010 AnimationLibrary
# added to its OWN imported AnimationPlayer under one namespace, and from then on
# only this presenter writes its pose (landscape.gd never calls play_animation or
# additive_hit for it). Positions/rotations of the scene roots stay with the
# existing code; the clips carry no actor-root motion.
#
# Every pose is a pure function of server-derived time (event.at = contact), so a
# repeated snapshot, a rewind or a late join re-poses without replaying anything.
# Nothing here calls the API, changes HP, rewards, inventory or battle cadence; one
# shot FX/audio stay where they were (driven by event times in landscape.gd).
#
# Rollback: set_enabled(false) bumps the generation, removes only the
# combat_v010 library from each player it was added to and hands the pose back to
# the legacy path (meta "clip" cleared so it re-selects its clip next frame).

const Registry := preload("res://combat_v010/runtime/combat_v010_registry.gd")
const SETTING := "drenovar/combat_v010/enabled"
const META := &"combat_v010"
# Visual arrow flight already used by landscape.draw_arrow (release precedes contact).
const FLIGHT_MS := 260.0
# Drift (s) tolerated between the playing clip and the server-derived time before a seek.
const DRIFT_S := 0.05
const BLEND_S := 0.12
# Longest a soldier waits for its library before it is created on the legacy clips.
const LOAD_DEADLINE_MS := 2000
const RANGED := ["bow", "crossbow", "javelin"]
const TROOP_CLIPS := ["idle", "walk", "run", "attack_a", "attack_b", "hit", "death"]
const CREATURE_CLIPS := ["idle", "combat_idle", "walk", "run", "alert", "attack_a", "attack_b", "hit_front", "hit_left", "hit_right", "death"]

static var _enabled := -1  # -1 = not resolved yet
static var generation := 0
static var _requests := {}
static var _libraries := {}
static var _owned: Array = []  # weak refs to models this presenter installed into
static var _warned := {}

static func enabled() -> bool:
	if _enabled < 0:
		var args := OS.get_cmdline_user_args()
		var on := bool(ProjectSettings.get_setting(SETTING, false))
		if "--combat-v010" in args: on = true
		if "--no-combat-v010" in args: on = false
		_enabled = 1 if on else 0
	return _enabled == 1

# Runtime switch (rollback path). Returns how many models were handed back.
static func set_enabled(on: bool) -> int:
	var was := enabled()
	_enabled = 1 if on else 0
	if was == on:
		return 0
	generation += 1
	var released := 0
	if not on:
		for ref in _owned:
			var model := (ref as WeakRef).get_ref() as Node3D
			if model != null and release(model):
				released += 1
		_owned.clear()
	return released

# ---- library loading (background, like landscape.model_ready) -------------

static func library_path(kind: String, key: String) -> String:
	return Registry.troop_library_path(key) if kind == "troop" else Registry.library_path_for_model(key)

static func ready(kind: String, key: String) -> bool:
	var path := library_path(kind, key)
	if _libraries.has(path):
		return true
	if not ResourceLoader.exists(path):
		_libraries[path] = null
		return true
	if not _requests.has(path):
		if ResourceLoader.load_threaded_request(path, "AnimationLibrary") != OK:
			_libraries[path] = load(path)
			return true
		_requests[path] = Time.get_ticks_msec()
	var status := ResourceLoader.load_threaded_get_status(path)
	if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		# Never keep soldiers off the field: past the deadline they are created
		# on the legacy clips (no library yet, see _library) and later ones get
		# the library once the background load has finished.
		return Time.get_ticks_msec() - int(_requests[path]) > LOAD_DEADLINE_MS
	_requests.erase(path)
	_libraries[path] = ResourceLoader.load_threaded_get(path) if status == ResourceLoader.THREAD_LOAD_LOADED else null
	return true

static func prewarm(kind: String, keys: Array) -> void:
	if enabled():
		for key in keys:
			ready(kind, str(key))

static func _library(kind: String, key: String) -> AnimationLibrary:
	var path := library_path(kind, key)
	if _requests.has(path):
		return null # still loading in the background: do not block the frame on it
	if not _libraries.has(path):
		_libraries[path] = load(path) if ResourceLoader.exists(path) else null
	return _libraries[path]

# ---- ownership -------------------------------------------------------------

static func _player(model: Node3D) -> AnimationPlayer:
	var players := model.find_children("*", "AnimationPlayer", true, false)
	return players[0] as AnimationPlayer if players.size() == 1 else null

# Adds the library to the model's own AnimationPlayer. Returns false (legacy path
# keeps the actor) when the flag is off or anything does not match exactly.
static func install(model: Node3D, kind: String, key: String) -> bool:
	if not enabled() or model == null:
		return false
	var library := _library(kind, key)
	var player := _player(model)
	if library == null or player == null:
		_warn("%s %s: library or single AnimationPlayer missing" % [kind, key])
		return false
	for clip in (TROOP_CLIPS if kind == "troop" else CREATURE_CLIPS):
		if not library.has_animation(clip):
			_warn("%s %s: clip %s missing" % [kind, key, clip])
			return false
	if player.is_playing() or str(player.assigned_animation) != "":
		# Only fresh players (see ready_for); a live one stays on the legacy path.
		_warn("%s %s: player already in use, left on legacy clips" % [kind, key])
		return false
	if not player.has_animation_library(Registry.NAMESPACE):
		player.add_animation_library(Registry.NAMESPACE, library)
	var info := {"kind": kind, "key": key, "generation": generation, "player": player, "clip": &"", "until": 0.0}
	if kind == "troop":
		var spec := Registry.troop(key)
		var length := float(spec.get("length_s", 1.7)) * 1000.0
		var event := float(spec.get("contact_or_release_s", 0.64)) * 1000.0
		var ranged: bool = spec.get("family", "") in RANGED
		info.ranged = ranged
		info.family = str(spec.get("family", ""))
		info.release_ms = event if ranged else -1.0
		info.prepare_ms = event + (FLIGHT_MS if ranged else 0.0)
		info.follow_ms = length - info.prepare_ms
		info.hit_ms = library.get_animation("hit").length * 1000.0
	model.set_meta(META, info)
	model.set_meta("animation_players", [player])
	# Dead references are dropped: every soldier of every fight passes through here
	# (the list grew by ~26 objects per hunt over a 22-minute session).
	if _owned.size() >= 128:
		_owned = _owned.filter(func(ref): return (ref as WeakRef).get_ref() != null)
	_owned.append(weakref(model))
	return true

# Creation gate: with the flag on, a field actor is created only once its library
# is loaded (binary .res, a few ms in the background), so the library is attached
# to a fresh AnimationPlayer before anything has played on it. Attaching to a player
# with live playback/blend state crashed Godot 4.6.3 in tests (signal 11 / malloc).
# With the flag off this is always true and nothing changes.
# Creatures are not gated: their GLB is already loaded synchronously by
# landscape.scene_resource and the binary library adds ~2 ms once per model.
static func ready_for(kind: String, key: String) -> bool:
	return not enabled() or ready(kind, key)

static func owns(model: Node3D) -> bool:
	if model == null or not model.has_meta(META):
		return false
	var info: Dictionary = model.get_meta(META)
	if int(info.generation) == generation and enabled():
		return true
	release(model)
	return false

static func release(model: Node3D) -> bool:
	if not model.has_meta(META):
		return false
	var info: Dictionary = model.get_meta(META)
	var player: AnimationPlayer = info.player
	if is_instance_valid(player):
		player.stop()
		if player.has_animation_library(Registry.NAMESPACE):
			player.remove_animation_library(Registry.NAMESPACE)
		player.speed_scale = 1.0
	model.remove_meta(META)
	model.set_meta("clip", "")
	model.set_meta("tempo", 1.0)
	return true

static func info(model: Node3D) -> Dictionary:
	return model.get_meta(META, {})

# ---- troop timing (server event.at = contact) ------------------------------

static func attack_window(model: Node3D, legacy_prepare: float) -> Vector2:
	var i := info(model)
	if i.is_empty():
		return Vector2(legacy_prepare, 1000.0 - legacy_prepare)
	return Vector2(i.prepare_ms, i.follow_ms)

# Swing window of a troop type before any soldier exists (strike scheduling):
# the same prepare/follow numbers install() puts on each soldier, or the legacy
# 1 s swing when the flag is off.
static func strike_window(unit_id: String, ranged: bool) -> Vector2:
	var spec := Registry.troop(unit_id) if enabled() else {}
	if spec.is_empty():
		var legacy := 760.0 if ranged else 490.0
		return Vector2(legacy, 1000.0 - legacy)
	var length := float(spec.get("length_s", 1.7)) * 1000.0
	var event := float(spec.get("contact_or_release_s", 0.64)) * 1000.0
	var prepare := event + (FLIGHT_MS if spec.get("family", "") in RANGED else 0.0)
	return Vector2(prepare, length - prepare)

static func hit_window(model: Node3D, legacy_ms: float) -> float:
	return float(info(model).get("hit_ms", legacy_ms))

# Clip time of an attack whose contact is at `strike` (battle-relative ms).
static func attack_time(model: Node3D, elapsed: float, strike: float) -> float:
	return (elapsed - strike + float(info(model).get("prepare_ms", 490.0))) / 1000.0

# Thrown javelin: hidden in the hand from release until the recovery re-arms.
static func javelin_in_hand(model: Node3D, clip_time_s: float) -> bool:
	var i := info(model)
	var release_s := float(i.get("release_ms", 660.0)) / 1000.0
	var length_s := (float(i.get("prepare_ms", 0.0)) + float(i.get("follow_ms", 0.0))) / 1000.0
	return not (clip_time_s >= release_s and clip_time_s < length_s - 0.35)

# Minimum follow-through after a shown contact before the next windup may cut in.
const MIN_FOLLOW_MS := 300.0

# Which server strike (event.at, battle-relative ms) this soldier shows now, or -INF.
# A drawn soldier can carry several overlapping strikes (members without a model
# lend theirs). Windup and contact are never cut: walking the strikes in time order,
# one is shown only when its windup starts at least MIN_FOLLOW_MS after the previous
# shown contact; otherwise it is skipped visually (HP, numbers and the authoritative
# outcome are unaffected). A pure function of the event list, so repeated snapshots,
# rewinds and appended poll windows never change an earlier decision.
static func pick_strike(model: Node3D, member_events: Array, elapsed: float) -> float:
	var i := info(model)
	var prepare := float(i.get("prepare_ms", 490.0))
	var follow := float(i.get("follow_ms", 510.0))
	var shown := -INF
	var current := -INF
	for e in member_events:
		if e[1] != "soldier_attack":
			continue
		var at := float(e[0])
		if at < shown:
			continue # not in time order (should not happen); never go back
		if shown > -INF and at - prepare < shown + MIN_FOLLOW_MS:
			continue
		if at - prepare > elapsed:
			break
		shown = at
		current = at if elapsed <= at + follow else -INF
	return current

# Deterministic variant per strike: identical across snapshots and devices.
static func attack_clip(member_key: String, strike: float) -> StringName:
	return &"attack_b" if (hash("%s@%d" % [member_key, int(strike)]) & 1) == 1 else &"attack_a"

# ---- playback ---------------------------------------------------------------

# Loops: started once (blended), then left running; `tempo` scales walk/run.
# One-shots: `time_s` is derived from server time; the clip plays naturally and
# is re-seeked only when it drifts, so blends survive and snapshots never restart it.
static func drive(model: Node3D, clip: StringName, time_s := -1.0, tempo := 1.0, start_fraction := 0.0) -> void:
	var i := info(model)
	var player: AnimationPlayer = i.get("player")
	if not is_instance_valid(player):
		return
	var name := StringName("%s/%s" % [Registry.NAMESPACE, clip])
	var anim := player.get_animation(name)
	if anim == null:
		return
	player.speed_scale = tempo if time_s < 0.0 else 1.0
	# No blend for the very first clip after hand-over (nothing of ours to blend from).
	var blend := BLEND_S if str(i.clip) != "" else 0.0
	if time_s < 0.0:
		if player.assigned_animation != name or not player.is_playing():
			player.play(name, blend)
			if start_fraction > 0.0:
				player.seek(start_fraction * anim.length, true)
		i.clip = clip
		return
	var t := clampf(time_s, 0.0, anim.length)
	if player.assigned_animation != name:
		player.play(name, blend)
		player.seek(t, true)
	elif t >= anim.length:
		if player.is_playing() or absf(player.current_animation_position - anim.length) > 0.001:
			player.seek(anim.length, true)
			player.pause()
	else:
		if not player.is_playing():
			player.play(name)
		if absf(player.current_animation_position - t) > DRIFT_S:
			player.seek(t, true)
	i.clip = clip

# ---- creatures --------------------------------------------------------------

const CREATURE_MAP := {"Idle": &"idle", "Walk": &"walk", "Run": &"run", "Roar": &"alert", "Alert": &"alert", "Attack": &"attack_a", "Hit": &"hit_front", "Death": &"death"}

static func creature_attack_window(model: Node3D) -> Vector2:
	var clip := Registry.animal_clip(str(info(model).get("key", "")), "attack_a")
	var contact := float(clip.get("contact", 0.52)) * 1000.0
	return Vector2(contact, float(clip.get("length", 1.3)) * 1000.0 - contact)

# Which reaction a creature shows when struck from `source` (world position).
static func creature_hit_clip(model: Node3D, source: Variant, heading: float) -> StringName:
	if not (source is Vector3):
		return &"hit_front"
	var to: Vector3 = (source as Vector3) - model.global_position
	var side := angle_difference(heading, atan2(to.x, to.z))
	if absf(side) < 0.6:
		return &"hit_front"
	return &"hit_left" if side > 0.0 else &"hit_right"

static func _warn(text: String) -> void:
	if not _warned.has(text):
		_warned[text] = true
		push_warning("combat_v010: " + text)
