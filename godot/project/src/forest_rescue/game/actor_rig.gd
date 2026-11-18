extends Node3D
## One adventure actor (horse, squad member, civilian, guardian, boss, cage, prop).
## * GLB is loaded lazily on a worker thread and shared between actors; a missing file is
##   logged once and an optional fallback (an existing game model) is used instead.
## * <id>.meta.json gives clip lengths, loop flags, ground speed, stride, markers, sockets.
## * Clips crossfade; locomotion is speed-matched to the authoritative path speed
##   (speed_scale = path speed / authored ground speed, bounded), never root motion.
## * Animation markers are presentation-only cues (hoof sound, latch click); nothing here
##   can commit progress.

signal marker(rig: Node3D, clip_id: String, marker_name: String)
signal ready_to_show(rig: Node3D)

static var scenes: Dictionary = {}
static var requested: Dictionary = {}
static var metas: Dictionary = {}
static var reported_missing: Dictionary = {}

var actor_id := ""
var asset_path := ""
var fallback_path := ""
var using_fallback := false
var meta: Dictionary = {}
var model: Node3D
var player: AnimationPlayer
var load_state := "idle"
var current := ""
var current_id := ""
var resolved: Dictionary = {}
var reverse: Dictionary = {}
var lods: Array = [[], [], []]
var lod_level := -1
var last_position_ms := 0.0
var marker_cursor := -1.0
var model_scale := 1.0
var model_yaw := 0.0
var tint := Color.WHITE
var hold_pending := ""

static func fetch(path: String) -> Variant:
	if path.is_empty():
		return false
	if scenes.has(path):
		return scenes[path]
	if not ResourceLoader.exists(path):
		scenes[path] = false
		if not reported_missing.has(path):
			reported_missing[path] = true
			push_warning("Forest rescue asset missing (presentation skipped until it lands): " + path)
		return false
	if not requested.has(path):
		requested[path] = true
		if ResourceLoader.load_threaded_request(path, "PackedScene") != OK:
			scenes[path] = load(path)
			return scenes[path]
	var status := ResourceLoader.load_threaded_get_status(path)
	if status == ResourceLoader.THREAD_LOAD_LOADED:
		scenes[path] = ResourceLoader.load_threaded_get(path)
		return scenes[path]
	if status == ResourceLoader.THREAD_LOAD_FAILED or status == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
		scenes[path] = false
		push_warning("Forest rescue asset failed to load: " + path)
		return false
	return null

## Blocking variant used by QA/capture so a frame never shows a half-loaded scene.
static func fetch_now(path: String) -> Variant:
	if scenes.has(path) and scenes[path] != null:
		return scenes[path]
	if not ResourceLoader.exists(path):
		return fetch(path)
	if requested.has(path):
		var status := ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS or status == ResourceLoader.THREAD_LOAD_LOADED:
			scenes[path] = ResourceLoader.load_threaded_get(path)
			return scenes[path]
	scenes[path] = load(path)
	requested[path] = true
	return scenes[path]

static func meta_for(path: String) -> Dictionary:
	if metas.has(path):
		return metas[path]
	var file := path.get_basename() + ".meta.json"
	var parsed: Variant = null
	if FileAccess.file_exists(file):
		parsed = JSON.parse_string(FileAccess.get_file_as_string(file))
	metas[path] = parsed if parsed is Dictionary else {}
	return metas[path]

func setup(id: String, path: String, fallback := "") -> void:
	actor_id = id
	name = id.validate_node_name()
	asset_path = path
	fallback_path = fallback
	load_state = "loading"
	set_process(true)

func is_ready() -> bool:
	return load_state == "ready"

func is_missing() -> bool:
	return load_state == "missing"

func _process(_delta: float) -> void:
	if load_state == "loading":
		poll_load()
	if load_state == "ready":
		dispatch_markers()

func poll_load(blocking := false) -> void:
	var scene: Variant = fetch_now(asset_path) if blocking else fetch(asset_path)
	if scene is bool and not fallback_path.is_empty():
		scene = fetch_now(fallback_path) if blocking else fetch(fallback_path)
		using_fallback = true
	if scene == null:
		return
	if scene is bool or not scene is PackedScene:
		load_state = "missing"
		return
	model = (scene as PackedScene).instantiate() as Node3D
	model.name = "Model"
	model.scale = Vector3.ONE * model_scale
	model.rotation.y = model_yaw
	add_child(model)
	meta = {} if using_fallback else meta_for(asset_path)
	var players := model.find_children("*", "AnimationPlayer", true, false)
	player = players[0] if not players.is_empty() else null
	if player != null:
		player.playback_default_blend_time = 0.2
		for clip_name in player.get_animation_list():
			var animation := player.get_animation(clip_name)
			var spec := clip_meta(clip_name)
			if bool(spec.get("loop", false)) or clip_name in ["Idle", "Walk", "Run"]:
				animation.loop_mode = Animation.LOOP_LINEAR
	for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		var lower := String(mesh.name).to_lower()
		for level in 3:
			if lower.ends_with("_lod%d" % level) or lower.contains("_lod%d_" % level):
				lods[level].append(mesh)
		if tint != Color.WHITE:
			apply_tint(mesh)
	load_state = "ready"
	if lods[1].size() + lods[2].size() > 0:
		set_lod(0)
	if not current_id.is_empty():
		var wanted := current_id
		current_id = ""
		current = ""
		play([wanted], 0.0)
	if not hold_pending.is_empty():
		hold_end([hold_pending])
	ready_to_show.emit(self)

func apply_tint(mesh: MeshInstance3D) -> void:
	if mesh.mesh == null:
		return
	for surface in mesh.mesh.get_surface_count():
		var material := mesh.get_active_material(surface)
		if material is BaseMaterial3D:
			var copy := material.duplicate() as BaseMaterial3D
			copy.albedo_color = copy.albedo_color * tint
			mesh.set_surface_override_material(surface, copy)

func clip_meta(clip_name: String) -> Dictionary:
	var clips: Dictionary = meta.get("clips", {})
	if clips.has(clip_name):
		return clips[clip_name]
	for id in clips:
		if clip_name.ends_with(String(id)):
			return clips[id]
	return {}

## Returns the actual animation name for the first candidate the model provides.
func resolve(candidates: Array) -> String:
	if player == null:
		return ""
	var key := ",".join(PackedStringArray(candidates))
	if resolved.has(key):
		return resolved[key]
	var names: PackedStringArray = player.get_animation_list()
	var found := ""
	for wanted in candidates:
		var id := String(wanted)
		for clip_name in names:
			if clip_name == id or clip_name.ends_with("|" + id) or clip_name.ends_with("/" + id):
				found = clip_name
				break
		if found.is_empty():
			for clip_name in names:
				if clip_name.to_lower() == id.to_lower():
					found = clip_name
					break
		if not found.is_empty():
			reverse[found] = id
			break
	resolved[key] = found
	return found

func has_clip(candidates: Array) -> bool:
	return not resolve(candidates).is_empty()

func clip_length(candidates: Array) -> float:
	var clip_name := resolve(candidates)
	if clip_name.is_empty():
		return 0.0
	return player.get_animation(clip_name).length

## Crossfades to the first available clip. Returns false when none exists (pose kept).
func play(candidates: Array, blend := 0.25, restart := false, speed := 1.0) -> bool:
	if candidates.is_empty():
		return false
	if load_state != "ready":
		current_id = String(candidates[0])
		return false
	var clip_name := resolve(candidates)
	if clip_name.is_empty():
		return false
	player.speed_scale = speed
	if clip_name == current and not restart and player.is_playing():
		return true
	current = clip_name
	current_id = String(reverse.get(clip_name, candidates[0]))
	player.play(clip_name, blend)
	if restart:
		player.seek(0.0, true)
	marker_cursor = -1.0
	return true

## Plays a one-shot clip and freezes on its last frame (stable restored pose after reload).
func hold_end(candidates: Array) -> bool:
	if load_state != "ready":
		hold_pending = String(candidates[0]) if not candidates.is_empty() else ""
		return false
	hold_pending = ""
	var clip_name := resolve(candidates)
	if clip_name.is_empty():
		return false
	var animation := player.get_animation(clip_name)
	current = clip_name
	current_id = String(reverse.get(clip_name, candidates[0]))
	player.play(clip_name, 0.0)
	player.seek(maxf(0.0, animation.length - 0.001), true)
	player.pause()
	return true

## Plays a clip at an explicit normalized phase (used to resync to the server timeline).
func pose_at(candidates: Array, seconds: float) -> bool:
	if load_state != "ready":
		return false
	var clip_name := resolve(candidates)
	if clip_name.is_empty():
		return false
	if current != clip_name or not player.is_playing():
		current = clip_name
		current_id = String(reverse.get(clip_name, candidates[0]))
		player.play(clip_name, 0.15)
	var length := player.get_animation(clip_name).length
	if absf(player.current_animation_position - seconds) > 0.25 and seconds < length:
		player.seek(clampf(seconds, 0.0, length), true)
	return true

func ground_speed(clip_id: String, fallback: float) -> float:
	var spec: Dictionary = meta.get("clips", {}).get(clip_id, {})
	var value := float(spec.get("groundSpeed_mps", spec.get("groundSpeed", 0.0)))
	if value <= 0.0 and float(spec.get("strideLength_m", 0.0)) > 0.0 and float(spec.get("seconds", 0.0)) > 0.0:
		value = float(spec.strideLength_m) / float(spec.seconds)
	return value if value > 0.05 else fallback

## Locomotion selection + speed matching. clips = {idle, walk, run, walk_speed, run_speed}.
func locomote(speed: float, clips: Dictionary) -> void:
	if load_state != "ready":
		current_id = String(clips.idle[0]) if speed < 0.15 else String(clips.walk[0])
		return
	if speed < 0.15:
		play(clips.idle, 0.3)
		player.speed_scale = 1.0
		return
	var walk_speed := ground_speed(String(clips.walk[0]), float(clips.get("walk_speed", 1.4)))
	var use_run: bool = clips.has("run") and speed > walk_speed * 1.45 and has_clip(clips.run)
	var chosen: Array = clips.run if use_run else clips.walk
	var authored := ground_speed(String(chosen[0]), float(clips.get("run_speed", 3.2)) if use_run else walk_speed)
	play(chosen, 0.25)
	player.speed_scale = clampf(speed / authored, 0.55, 1.7)

func set_lod(level: int) -> void:
	if level == lod_level or load_state != "ready":
		return
	var available := level
	while available > 0 and lods[available].is_empty():
		available -= 1
	if lods[available].is_empty():
		return
	lod_level = level
	for index in 3:
		for mesh in lods[index]:
			if is_instance_valid(mesh):
				mesh.visible = index == available

func socket(name_hint: String) -> Variant:
	var sockets: Dictionary = meta.get("sockets", {})
	if sockets.has(name_hint):
		var value: Array = sockets[name_hint]
		if value.size() >= 3:
			return Vector3(float(value[0]), float(value[1]), float(value[2])) * model_scale
	return null

func find_part(hints: Array) -> Node3D:
	if model == null:
		return null
	for hint in hints:
		var lower := String(hint).to_lower()
		for node in model.find_children("*", "Node3D", true, false):
			if String(node.name).to_lower().contains(lower):
				return node
	return null

func dispatch_markers() -> void:
	if player == null or current.is_empty() or not player.is_playing():
		return
	var spec := clip_meta(current_id)
	var markers: Variant = spec.get("markers", {})
	if markers is Array:
		var converted := {}
		for entry in markers:
			if entry is Dictionary:
				converted[String(entry.get("name", ""))] = float(entry.get("timeSeconds", entry.get("time", 0.0)))
		markers = converted
	if not markers is Dictionary or markers.is_empty():
		return
	var position := player.current_animation_position
	var previous := marker_cursor
	marker_cursor = position
	if previous < 0.0:
		return
	var wrapped := position < previous
	for marker_name in markers:
		var at := float(markers[marker_name])
		var crossed := (at > previous and at <= position) if not wrapped else (at > previous or at <= position)
		if crossed:
			marker.emit(self, current_id, String(marker_name))

func set_active(active: bool) -> void:
	if visible != active:
		visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
