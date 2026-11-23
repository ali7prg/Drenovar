extends Node3D
## One adventure actor (horse, squad member, civilian, guardian, boss, cage, prop).
## * GLB is loaded lazily on a worker thread and shared between actors; a missing file is
##   logged once and an optional fallback (an existing game model) is used instead.
## * <id>.meta.json gives clip lengths, loop flags, ground speed, stride, markers, sockets.
## * Clips crossfade; locomotion is speed-matched to the authoritative path speed
##   (speed_scale = path speed / authored groundSpeed_mps), never root motion.
## * Painted look: every forest-rescue actor/prop uses the kit painted material
##   (albedo * mix(1, lambert, paintedLightMix)); materials named *_glow keep their emission.
##   Guardians (original creature models) keep their original materials (painted = false).
## * Exactly one LOD mesh set is visible (set_lod); the director picks the level by zoom.
## * Animation markers fire at clip start (t = 0), while playing, and at the clip end
##   (t = length) when a one-shot finishes; they are presentation-only cues.
## * Prop pose composer (mechanisms): node transforms sampled per node from several clips,
##   independent of the AnimationPlayer (their clips key every node, often with values that
##   only make sense for the nodes the clip owns).

signal marker(rig: Node3D, clip_id: String, marker_name: String)
signal ready_to_show(rig: Node3D)
signal clip_finished(rig: Node3D, clip_id: String)

const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
## Painted-light mix for delivered assets whose meta has none (horse, rune lock, winch,
## artifacts): same family as the props v2 (0.38) / humans (0.40).
const DEFAULT_LIGHT_MIX := 0.38
const SPEED_SCALE_RANGE := Vector2(0.3, 2.6)

static var scenes: Dictionary = {}
static var requested: Dictionary = {}
static var metas: Dictionary = {}
static var reported_missing: Dictionary = {}
## Threaded actor loads still in progress. 1022: one at a time. Four creatures v2 guardians (three LODs,
## ~40 textures each) requested together filled every WorkerThreadPool thread and deadlocked the
## texture upload against the main thread in the rendered game (Godot 4.6.3, mobile renderer).
static var loading: Dictionary = {}
const MAX_PARALLEL_LOADS := 1
## 1023: the first view first. A rig on screen (the horse, the squad, the site's guardian) takes the
## next load slot before the background warm-up rigs ("__warm_*"), which used to queue every model of
## the campaign ahead of it. A path a live rig waits for is kept here (with the frame it last asked).
static var live_waiting: Dictionary = {}
## 1023: at most INSTANCE_BUDGET_USEC of model instancing per frame (at least one model), so a frame
## where several loads finish together does not instance them all at once.
const INSTANCE_BUDGET_USEC := 6000
static var instance_frame := -1
static var instance_spent := 0

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
## LOD thresholds are multiplied by this (big actors keep their detail at wider zooms).
var lod_scale := 1.0
var last_position_ms := 0.0
var marker_cursor := -1.0
var model_scale := 1.0
## 1022: a campaign guardian drawn with the game's creatures v2 model (src/creature_visuals.gd owns its
## level materials, LOD switch and authored clip names; semantic ids "Idle", "Attack"... map to them).
var creature_species := ""
var creature_level := 1
var model_yaw := 0.0
var tint := Color.WHITE
var hold_pending := ""
## false: keep the GLB's own materials (guardians = original DRENOVAR creature models).
var painted := true
## Per-actor look variation (humans/captive_variants.json entry): {"tint": {"cloth": [r,g,b],
## "hair": [r,g,b]}, "hide": ["Bag"]} - tints multiply the albedo of materials named *_<key>,
## hidden bones collapse their accessory (pouch / satchel / rope coil / hammer on the Bag bone).
var variant: Dictionary = {}
## Duplicated *_glow materials of this instance (emission driven per actor).
var glow_materials: Array[BaseMaterial3D] = []
var node_cache: Dictionary = {}
var last_speed_scale := 1.0

static func fetch(path: String, background := false) -> Variant:
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
		collect_loads()
		var frame := Engine.get_process_frames()
		if background:
			for waiting: String in live_waiting.keys():
				if frame - int(live_waiting[waiting]) > 2 or requested.has(waiting):
					live_waiting.erase(waiting)
			if not live_waiting.is_empty():
				return null
		if loading.size() >= MAX_PARALLEL_LOADS:
			if not background:
				live_waiting[path] = frame
			return null
		live_waiting.erase(path)
		requested[path] = true
		if ResourceLoader.load_threaded_request(path, "PackedScene") != OK:
			scenes[path] = load(path)
			return scenes[path]
		loading[path] = true
	collect_loads()
	return scenes.get(path) if scenes.has(path) else null

## Moves finished threaded loads into the scene cache (also those whose rig is gone).
static func collect_loads() -> void:
	for path in loading.keys():
		var status := ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			continue
		loading.erase(path)
		if status == ResourceLoader.THREAD_LOAD_LOADED:
			scenes[path] = ResourceLoader.load_threaded_get(path)
		else:
			scenes[path] = false
			push_warning("Forest rescue asset failed to load: " + path)

## Blocking variant used by QA/capture so a frame never shows a half-loaded scene.
static func fetch_now(path: String) -> Variant:
	if scenes.has(path) and scenes[path] != null:
		return scenes[path]
	if not ResourceLoader.exists(path):
		return fetch(path)
	if requested.has(path):
		var status := ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS or status == ResourceLoader.THREAD_LOAD_LOADED:
			loading.erase(path)
			scenes[path] = ResourceLoader.load_threaded_get(path)
			return scenes[path]
	scenes[path] = load(path)
	requested[path] = true
	return scenes[path]

static var uv2_materials: Dictionary = {}
static var uv2_manifest: Variant = null

## Generated by src/forest_rescue/world/tools/build_uv2_manifest.gd: res path of every GLB whose
## materials sample baseColorTexture with texCoord 1 -> those material names. An exported pack holds
## no raw .glb (only the imported scenes), so the runtime reads this manifest; a GLB missing from it
## has no UV2 materials. qa_forest_world checks the manifest against the raw GLBs.
const UV2_MANIFEST := "res://assets/forest_rescue/uv2_materials.json"

## Names of the GLB's materials whose baseColorTexture uses texCoord 1 (Godot's importer samples
## every texture with UV1). Manifest first; the raw GLB is read only in the editor as a fallback for
## a GLB the manifest does not know yet (a warning says to regenerate it).
static func glb_uv2_materials(path: String) -> Dictionary:
	if uv2_materials.has(path):
		return uv2_materials[path]
	var listed := uv2_manifest_entries()
	var found := {}
	if listed.has(path):
		for material_name in listed[path]:
			found[String(material_name)] = true
	elif OS.has_feature("editor"):
		found = glb_uv2_materials_raw(path)
		if not found.is_empty():
			push_warning("ActorRig: %s has UV2 materials missing from %s; run build_uv2_manifest.gd" % [path, UV2_MANIFEST])
	uv2_materials[path] = found
	return found

static func uv2_manifest_entries() -> Dictionary:
	if uv2_manifest == null:
		var parsed: Variant = null
		if FileAccess.file_exists(UV2_MANIFEST):
			parsed = JSON.parse_string(FileAccess.get_file_as_string(UV2_MANIFEST))
		uv2_manifest = parsed.get("materials", {}) if parsed is Dictionary else {}
	return uv2_manifest

## glTF JSON chunk of a raw .glb (editor / tools only: not present in an exported pack).
static func glb_uv2_materials_raw(path: String) -> Dictionary:
	var found := {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file != null and file.get_length() > 20 and file.get_32() == 0x46546C67:
		file.get_32()
		file.get_32()
		var chunk := file.get_32()
		if file.get_32() == 0x4E4F534A and chunk > 0 and chunk < 32 * 1024 * 1024:
			var parsed: Variant = JSON.parse_string(file.get_buffer(chunk).get_string_from_utf8())
			if parsed is Dictionary:
				for material in parsed.get("materials", []):
					var base: Variant = material.get("pbrMetallicRoughness", {}).get("baseColorTexture")
					if base is Dictionary and int(base.get("texCoord", 0)) == 1:
						found[String(material.get("name", ""))] = true
	return found

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
	# Visibility is decided by the director (fog projection + view); the world layer's
	# periodic fog cull must not re-show a rig the director hid.
	set_meta("fog_exempt", true)
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
	var background := actor_id.begins_with("__warm_")
	var scene: Variant = fetch_now(asset_path) if blocking else fetch(asset_path, background)
	if scene is bool and not fallback_path.is_empty():
		scene = fetch_now(fallback_path) if blocking else fetch(fallback_path, background)
		using_fallback = true
	if scene == null:
		return
	if scene is bool or not scene is PackedScene:
		load_state = "missing"
		return
	var frame := Engine.get_process_frames()
	if frame != instance_frame:
		instance_frame = frame
		instance_spent = 0
	elif not blocking and instance_spent >= INSTANCE_BUDGET_USEC:
		return   # this frame's instancing budget is spent: the next frame
	var instanced_at := Time.get_ticks_usec()
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
		player.animation_finished.connect(_on_animation_finished)
	var creature_v2 := not creature_species.is_empty() and CreatureVisuals.active(creature_species) and not using_fallback
	if creature_v2:
		CreatureVisuals.install(model, creature_species, creature_level, model_scale)
	for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		var lower := String(mesh.name).to_lower()
		for level in 3:
			if not creature_v2 and (lower.ends_with("_lod%d" % level) or lower.contains("_lod%d_" % level)):
				lods[level].append(mesh)
		if tint != Color.WHITE:
			apply_tint(mesh)
	if not using_fallback and (painted or not variant.is_empty()):
		apply_look()
	load_state = "ready"
	instance_spent += Time.get_ticks_usec() - instanced_at
	if lods[1].size() + lods[2].size() > 0:
		set_lod(maxi(lod_level, 0), true)
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

## Painted look (meta paintedLightMix, DEFAULT_LIGHT_MIX when the meta has none): the atlas
## carries the painted light, so the engine light is mixed in partially (forest kit painted
## material). *_glow materials keep their StandardMaterial3D emission (duplicated per actor so
## the director can drive emission_energy_multiplier). Then the per-actor variant.
func apply_look() -> void:
	var k := float(meta.get("paintedLightMix", DEFAULT_LIGHT_MIX)) if painted else -1.0
	var tints: Dictionary = variant.get("tint", {})
	var uv2_set := glb_uv2_materials(asset_path) if k >= 0.0 else {}
	# Material-path props (meta vertexAO, e.g. the winch): COLOR_0.a carries baked ambient occlusion + soft sun
	# shadow; the painted shader applies it as mix(ao_floor, 1, a^2) (use_ao), never as wind.
	var vertex_ao := bool(meta.get("vertexAO", false))
	for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh == null:
			continue
		for s in mesh.mesh.get_surface_count():
			var material: Material = mesh.get_active_material(s)
			if material == null:
				continue
			var material_name := String(material.resource_name)
			if material_name.ends_with("_glow"):
				var glow := material.duplicate() as Material
				if glow is BaseMaterial3D:
					glow_materials.append(glow)
				mesh.set_surface_override_material(s, glow)
				mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				continue
			if k >= 0.0:
				var has_ao := vertex_ao and mesh.mesh is ArrayMesh \
					and ((mesh.mesh as ArrayMesh).surface_get_format(s) & Mesh.ARRAY_FORMAT_COLOR) != 0
				material = ForestKit.painted_material(material, has_ao, k, false, false)
				if uv2_set.has(material_name) and material is ShaderMaterial:
					material = material.duplicate()
					material.set_shader_parameter("albedo_uv2", true)
			if not tints.is_empty():
				material = apply_variant_tints(material, material_name, tints)
			mesh.set_surface_override_material(s, material)
	var hidden: Array = variant.get("hide", [])
	if not hidden.is_empty():
		for skeleton: Skeleton3D in model.find_children("*", "Skeleton3D", true, false):
			for bone_name in hidden:
				var index := skeleton.find_bone(String(bone_name))
				if index >= 0:
					skeleton.set_bone_pose_scale(index, Vector3.ONE * 0.001)

## Look variation on one surface. The v2 civilians carry ONE merged body material, so the
## cloth / hair tints go through <asset>_variant_mask.png (R cloth, G hair, B keep) baked by
## forest_rescue/tools/bake_variant_masks.py; the hair cards take the hair tint as a whole;
## materials named *_<group> (older split assets) take that group's tint.
func apply_variant_tints(material: Material, material_name: String, tints: Dictionary) -> Material:
	var cloth := tint_color(tints.get("cloth"))
	var hair := tint_color(tints.get("hair"))
	if material_name.ends_with("_hair_cards") or material_name.ends_with("_hair"):
		return multiplied(material, hair)
	if material_name.ends_with("_cloth"):
		return multiplied(material, cloth)
	if material_name.ends_with("_body") and material is ShaderMaterial:
		var mask_path := asset_path.get_basename() + "_variant_mask.png"
		if ResourceLoader.exists(mask_path):
			var copy := material.duplicate() as ShaderMaterial
			copy.set_shader_parameter("variant_mask", load(mask_path))
			copy.set_shader_parameter("use_variant_mask", true)
			copy.set_shader_parameter("tint_cloth", Vector3(cloth.r, cloth.g, cloth.b))
			copy.set_shader_parameter("tint_hair", Vector3(hair.r, hair.g, hair.b))
			return copy
	return material

static func tint_color(value: Variant) -> Color:
	if value is Array and value.size() >= 3:
		return Color(float(value[0]), float(value[1]), float(value[2]), 1.0)
	return Color.WHITE

static func multiplied(material: Material, factor: Color) -> Material:
	if factor == Color.WHITE:
		return material
	var copy := material.duplicate()
	if copy is ShaderMaterial:
		var base: Color = copy.get_shader_parameter("albedo_color")
		copy.set_shader_parameter("albedo_color", base * factor)
	elif copy is BaseMaterial3D:
		copy.albedo_color = copy.albedo_color * factor
	return copy

## Emission of the *_glow materials (0 = off, ~3 seated in a socket).
func set_glow(energy: float) -> void:
	for material in glow_materials:
		material.emission_enabled = energy > 0.001
		material.emission_energy_multiplier = energy

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
		if not creature_species.is_empty() and model != null and CreatureVisuals.owns(model):
			var authored := String(CreatureVisuals.clip_name(creature_species, id))
			if not authored.is_empty():
				id = authored
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
			reverse[found] = String(wanted)
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

func playing_id() -> String:
	return current_id if player != null and player.is_playing() else ""

## Seconds into the current clip (0 when nothing plays).
func clip_time() -> float:
	if player == null or current.is_empty():
		return 0.0
	return player.current_animation_position if player.is_playing() else player.get_animation(current).length

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
	last_speed_scale = speed
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
	if current == clip_name and not player.is_playing() and is_equal_approx(player.current_animation_position, animation.length - 0.001):
		return true
	current = clip_name
	current_id = String(reverse.get(clip_name, candidates[0]))
	player.play(clip_name, 0.0)
	player.seek(maxf(0.0, animation.length - 0.001), true)
	player.pause()
	marker_cursor = animation.length
	return true

## Plays a clip at an explicit phase (used to resync to the server timeline).
func pose_at(candidates: Array, seconds: float, blend := 0.15) -> bool:
	if load_state != "ready":
		return false
	var clip_name := resolve(candidates)
	if clip_name.is_empty():
		return false
	var length := player.get_animation(clip_name).length
	player.speed_scale = 1.0
	if current != clip_name or not player.is_playing():
		if current == clip_name and seconds >= length:
			return true
		current = clip_name
		current_id = String(reverse.get(clip_name, candidates[0]))
		player.play(clip_name, blend)
		marker_cursor = -1.0 if seconds < 0.25 else seconds
		player.seek(clampf(seconds, 0.0, length), true)
		return true
	if absf(player.current_animation_position - seconds) > 0.25 and seconds < length:
		player.seek(clampf(seconds, 0.0, length), true)
		marker_cursor = seconds
	return true

func ground_speed(clip_id: String, fallback: float) -> float:
	var spec: Dictionary = meta.get("clips", {}).get(clip_id, {})
	var value := float(spec.get("groundSpeed_mps", spec.get("groundSpeed", 0.0)))
	if value <= 0.0 and float(spec.get("strideLength_m", 0.0)) > 0.0 and float(spec.get("seconds", 0.0)) > 0.0:
		value = float(spec.strideLength_m) / float(spec.seconds)
	return value if value > 0.05 else fallback

## Locomotion selection + speed matching. clips = {idle, walk, run, walk_speed, run_speed}.
## playback speed = actual ground speed / authored groundSpeed_mps (feet do not slide).
func locomote(speed: float, clips: Dictionary) -> void:
	if load_state != "ready":
		current_id = String(clips.idle[0]) if speed < 0.15 else String(clips.walk[0])
		return
	if speed < 0.15:
		play(clips.idle, 0.3)
		player.speed_scale = 1.0
		last_speed_scale = 1.0
		return
	var walk_speed := ground_speed(String(clips.walk[0]), float(clips.get("walk_speed", 1.4)))
	var use_run: bool = clips.has("run") and speed > walk_speed * 1.45 and has_clip(clips.run)
	var chosen: Array = clips.run if use_run else clips.walk
	var authored := ground_speed(String(chosen[0]), float(clips.get("run_speed", 3.2)) if use_run else walk_speed)
	play(chosen, 0.25)
	last_speed_scale = clampf(speed / authored, SPEED_SCALE_RANGE.x, SPEED_SCALE_RANGE.y)
	player.speed_scale = last_speed_scale

func set_lod(level: int, force := false) -> void:
	if (level == lod_level and not force) or load_state != "ready":
		return
	lod_level = level
	var available := level
	while available > 0 and lods[available].is_empty():
		available -= 1
	if lods[available].is_empty():
		return
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

## World position of a meta socket (or a node of that name), INF when unknown.
func socket_global(name_hint: String) -> Vector3:
	var node := part(name_hint)
	if node != null and node.is_inside_tree():
		return node.global_position
	var local: Variant = socket(name_hint)
	if local == null:
		return Vector3.INF
	return global_transform * Vector3(local) if is_inside_tree() else position + Vector3(local)

func find_part(hints: Array) -> Node3D:
	if model == null:
		return null
	for hint in hints:
		var lower := String(hint).to_lower()
		for node in model.find_children("*", "Node3D", true, false):
			if String(node.name).to_lower().contains(lower):
				return node
	return null

## Exact node by name (cached), null when absent.
func part(node_name: String) -> Node3D:
	if model == null:
		return null
	if node_cache.has(node_name):
		var cached: Variant = node_cache[node_name]
		return cached if cached != null and is_instance_valid(cached) else null
	var found: Node = model.find_child(node_name, true, false)
	node_cache[node_name] = found if found is Node3D else null
	return node_cache[node_name]

func markers_of(clip_id: String) -> Dictionary:
	var spec := clip_meta(clip_id)
	var markers: Variant = spec.get("markers", {})
	if markers is Array:
		var converted := {}
		for entry in markers:
			if entry is Dictionary:
				converted[String(entry.get("name", ""))] = float(entry.get("timeSeconds", entry.get("time", 0.0)))
		markers = converted
	return markers if markers is Dictionary else {}

## Emits every marker of clip_id with previous < at <= position (a previous < 0 includes t = 0).
func emit_markers_between(clip_id: String, previous: float, position: float) -> void:
	var markers := markers_of(clip_id)
	for marker_name in markers:
		var times: Variant = markers[marker_name]
		for at_value in (times if times is Array else [times]):
			var at := float(at_value)
			if at > previous and at <= position:
				marker.emit(self, clip_id, String(marker_name))

func dispatch_markers() -> void:
	if player == null or current.is_empty() or not player.is_playing():
		return
	var position := player.current_animation_position
	var previous := marker_cursor
	marker_cursor = position
	if previous < 0.0:
		# Clip just started: markers at t = 0 (telegraph_begin, footfall at 0) fire now.
		emit_markers_between(current_id, -0.001, position)
		return
	if position < previous:
		# Looped: tail of the previous cycle, then the head of the new one.
		emit_markers_between(current_id, previous, player.get_animation(current).length + 0.001)
		emit_markers_between(current_id, -0.001, position)
		return
	emit_markers_between(current_id, previous, position)

func _on_animation_finished(clip_name: StringName) -> void:
	if String(clip_name) != current:
		return
	var length := player.get_animation(current).length
	if marker_cursor < length:
		# Markers at the very end (recovery_end, last footfall) are dispatched on finish.
		emit_markers_between(current_id, marker_cursor, length + 0.001)
	marker_cursor = length
	clip_finished.emit(self, current_id)

func set_active(active: bool) -> void:
	if visible != active:
		visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED

# ------------------------------------------------------------------ prop pose composer
func animation_of(clip_id: String) -> Animation:
	var clip_name := resolve([clip_id])
	return player.get_animation(clip_name) if not clip_name.is_empty() else null

## Writes the clip's values at `time` into pose[node_path] = {pos, rot, scale}; nodes: only
## tracks whose node name is listed (empty = all); channels: subset of ["pos", "rot", "scale"].
func sample_into(pose: Dictionary, clip_id: String, time: float, nodes: Array = [], channels: Array = ["pos", "rot", "scale"]) -> void:
	if load_state != "ready" or player == null:
		return
	var animation := animation_of(clip_id)
	if animation == null:
		return
	var t := clampf(time, 0.0, animation.length)
	for track in animation.get_track_count():
		var path := animation.track_get_path(track)
		var node_name := String(path.get_name(path.get_name_count() - 1))
		if not nodes.is_empty() and not nodes.has(node_name):
			continue
		var key := String(path.get_concatenated_names())
		var entry: Dictionary = pose.get(key, {})
		match animation.track_get_type(track):
			Animation.TYPE_POSITION_3D:
				if channels.has("pos"):
					entry.pos = animation.position_track_interpolate(track, t)
			Animation.TYPE_ROTATION_3D:
				if channels.has("rot"):
					entry.rot = animation.rotation_track_interpolate(track, t)
			Animation.TYPE_SCALE_3D:
				if channels.has("scale"):
					entry.scale = animation.scale_track_interpolate(track, t)
		pose[key] = entry

func apply_pose(pose: Dictionary) -> void:
	if model == null or player == null:
		return
	if player.is_playing():
		player.stop(true)
	var base: Node = player.get_node_or_null(player.root_node)
	if base == null:
		return
	for key in pose:
		var node: Variant = node_cache.get("path:" + key)
		if node == null or not is_instance_valid(node):
			node = base.get_node_or_null(NodePath(key))
			node_cache["path:" + key] = node
		if not node is Node3D:
			continue
		var entry: Dictionary = pose[key]
		var target := node as Node3D
		if entry.has("pos"):
			target.position = entry.pos
		if entry.has("rot"):
			target.quaternion = entry.rot
		if entry.has("scale"):
			target.scale = entry.scale
