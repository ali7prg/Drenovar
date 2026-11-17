extends RefCounted

## creatures-v2 visual binding (see godot/art/creatures-v2/README.md).
##
## One runtime GLB per species (LOD1 + LOD2 meshes and level II/III overlays on one
## skeleton, exactly 12/12/14/14 authored clips "<species>__<name>") replaces the
## 0.5.9 prototypes for the SAME species ids and encounters. Level I/II/III are
## material parameters of one shared shader (creature_v2.gdshader) and the overlays
## a level shows; geometry, skeleton and clips are shared by all levels.
##
## Nothing here talks to the server, changes hp, damage, rewards or battle timing:
## it only chooses what is drawn for a creature the server already published.
## Rollback: project setting drenovar/creatures_v2/enabled=false (or --no-creatures-v2)
## draws the previous models from assets/game.json creatureModels again.

const SETTING := "drenovar/creatures_v2/enabled"
const REGISTRY := "res://assets/creatures-v2/registry.json"
const SHADER := preload("res://src/creature_v2.gdshader")
const META := &"creature_v2"
# Old semantic states (exact case) and the combat v0.1.0 logical clips -> authored clip short names.
const V010 := {"idle": "Idle", "combat_idle": "Idle", "walk": "Walk", "run": "Run", "alert": "Alert",
	"attack_a": "Attack", "hit_front": "Hit", "hit_left": "Hit", "hit_right": "Hit", "death": "Death", "roar": "Roar"}
# Server event kinds of a creature's special attack (gameplay37/server/catalog.mjs abilities).
const SPECIAL_EVENTS := ["antler_charge", "pounce", "tusk_sweep", "shockwave"]
## LOD1 <-> LOD2 hysteresis around the switch distance (fraction of it).
const LOD_HYSTERESIS := 0.12

static var _enabled := -1
static var _registry := {}
static var _manifests := {}
static var _materials := {}
static var _looped := {}
static var _masks := {}

static func enabled() -> bool:
	if _enabled < 0:
		var on := bool(ProjectSettings.get_setting(SETTING, true))
		var args := OS.get_cmdline_user_args()
		if "--no-creatures-v2" in args:
			on = false
		if "--creatures-v2" in args:
			on = true
		_enabled = 1 if on else 0
	return _enabled == 1

static func set_enabled(on: bool) -> void:
	_enabled = 1 if on else 0

static func registry() -> Dictionary:
	if _registry.is_empty() and FileAccess.file_exists(REGISTRY):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(REGISTRY))
		if parsed is Dictionary:
			_registry = parsed
	return _registry

static func entry(species: String) -> Dictionary:
	return registry().get("species", {}).get(species, {})

## True when this species is drawn with its creatures-v2 asset.
static func active(species: String) -> bool:
	if not enabled():
		return false
	var e := entry(species)
	return not e.is_empty() and ResourceLoader.exists(str(e.get("model", "")))

static func model_path(species: String, level: int, legacy: String) -> String:
	return str(entry(species).model) if active(species) else legacy

static func display_scale(species: String) -> float:
	return float(entry(species).get("display_scale", 1.0)) if active(species) else 1.0

## Half length (head at +X) and half width at actor scale 1, as the battle places expect.
static func body(species: String, legacy: Vector2) -> Vector2:
	if not active(species):
		return legacy
	var b: Array = entry(species).get("body", [legacy.x, legacy.y])
	return Vector2(float(b[0]), float(b[1]))

static func manifest(species: String) -> Dictionary:
	if not _manifests.has(species):
		var path := str(entry(species).get("manifest", ""))
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
		_manifests[species] = parsed if parsed is Dictionary else {}
	return _manifests[species]

static func clip_row(species: String, short: String) -> Dictionary:
	return manifest(species).get("clips", {}).get(short, {})

## Authored clip short name for an old semantic state ("Idle"... "Roar"), a combat
## v0.1.0 logical clip ("attack_a", "hit_left"...), a server event kind, or a short name.
static func short_name(species: String, state: String) -> String:
	var m := manifest(species)
	var sem: Dictionary = m.get("semantic_states", {})
	if sem.has(state):
		return str(sem[state])
	if V010.has(state):
		return str(sem.get(V010[state], "idle"))
	var events: Dictionary = m.get("server_events", {})
	if state == "attack_b" or state == "special":
		for kind in SPECIAL_EVENTS:
			if events.has(kind):
				return str(events[kind])
		return str(sem.get("Attack", "idle"))
	if events.has(state):
		return str(events[state])
	if m.get("clips", {}).has(state):
		return state
	return ""

static func clip_name(species: String, state: String) -> StringName:
	var short := short_name(species, state)
	return StringName("%s__%s" % [species, short]) if not short.is_empty() else &""

static func is_special(kind: String) -> bool:
	return kind in SPECIAL_EVENTS

## Contact (ms from clip start) and follow-through (ms after contact) of the clip that
## shows `state` (attack_a, attack_b or a server event kind).
static func attack_window(species: String, state: String) -> Vector2:
	var row := clip_row(species, short_name(species, state))
	var length := float(row.get("length_s", 1.0)) * 1000.0
	var contact := float(row.get("contact_s", 0.5)) * 1000.0
	return Vector2(contact, length - contact)

## Controller displacement (model metres, scale 1) of a clip at time t (s); Vector2(forward, side).
static func motion_at(species: String, state: String, t: float) -> Vector2:
	var row := clip_row(species, short_name(species, state))
	var motion: Dictionary = row.get("motion", {})
	var fps := float(row.get("fps", 30.0))
	var out := Vector2.ZERO
	for key in ["forward_m", "side_m"]:
		var curve: Array = motion.get(key, [])
		if curve.is_empty():
			continue
		var f := clampf(t * fps, 0.0, float(curve.size() - 1))
		var i := int(floor(f))
		var v := lerpf(float(curve[i]), float(curve[mini(i + 1, curve.size() - 1)]), f - float(i))
		if key == "forward_m":
			out.x = v
		else:
			out.y = v
	return out

## Native ground speed (m/s at scale 1) of a locomotion clip, for tempo matching.
static func clip_speed(species: String, state: String) -> float:
	return float(clip_row(species, short_name(species, state)).get("speed_mps", 0.0))

static func _mask(path: String) -> Texture2D:
	if not _masks.has(path):
		_masks[path] = load(path) if ResourceLoader.exists(path) else null
	return _masks[path]

static func _material(species: String, level: int, source: Material, group: String, lod: int) -> Material:
	if not (source is BaseMaterial3D):
		return source
	var key := "%s:%d:%s:%d" % [species, level, group, source.get_instance_id()]
	if _materials.has(key):
		return _materials[key]
	var src := source as BaseMaterial3D
	var e := entry(species)
	var lv: Dictionary = e.get("levels", {}).get(str(level), {}).duplicate()
	# "groups": per material group overrides of the level (e.g. Dragor's skin creases glow less than plate seams)
	var over = lv.get("groups", {}).get(group, {}) if lv.get("groups") is Dictionary else {}
	if over is Dictionary:
		lv.merge(over, true)
	var m := ShaderMaterial.new()
	m.shader = SHADER
	m.set_shader_parameter("albedo_tex", src.albedo_texture)
	m.set_shader_parameter("normal_tex", src.normal_texture)
	var orm: Texture2D = src.roughness_texture if src.roughness_texture != null else src.ao_texture
	if src is ORMMaterial3D:
		orm = (src as ORMMaterial3D).orm_texture
	m.set_shader_parameter("orm_tex", orm)
	m.set_shader_parameter("emission_tex", src.emission_texture if src.emission_enabled else null)
	m.set_shader_parameter("variant_tex", _mask(str(e.get("variant_masks", {}).get(group, {}).get(str(lod), ""))))
	m.set_shader_parameter("normal_strength", src.normal_scale if src.normal_enabled else 1.0)
	for k in ["tint_r", "tint_g", "tint_b"]:
		var t: Array = lv.get(k, [1, 1, 1, 0])
		m.set_shader_parameter(k, Vector4(float(t[0]), float(t[1]), float(t[2]), float(t[3])))
	m.set_shader_parameter("emission_color", Color(str(e.get("emission_color", "#ffffff"))))
	m.set_shader_parameter("emission_strength", float(lv.get("emission_strength", 1.0)))
	m.set_shader_parameter("emit_masks", Vector3(float(lv.get("emit_r", 0.0)), float(lv.get("emit_g", 0.0)), float(lv.get("emit_b", 0.0))))
	_materials[key] = m
	return m

## Prepares a freshly instantiated creatures-v2 actor: level materials and overlays,
## LOD distances (scaled with the actor), clip loop modes from the manifest.
static func install(actor: Node3D, species: String, level: int, actor_scale: float) -> void:
	if actor == null or not active(species):
		return
	var e := entry(species)
	level = clampi(level, 1, 3)
	var lod_m := float(e.get("lod_switch_m", 50.0)) * actor_scale
	var meshes: Array = []
	var parts: Array = []
	for part: MeshInstance3D in actor.find_children("*", "MeshInstance3D", true, false):
		var n := String(part.name)
		var tier := 3 if n.contains("VARIANT_L3") else (2 if n.contains("VARIANT_L2") else 1)
		var group := ""
		for g in e.get("groups", {}):
			if n.to_lower().contains("_" + str(e.groups[g]).to_lower() + "_"):
				group = g
		var lod := 2 if n.contains("_LOD2") else (0 if n.contains("_LOD0") else 1)
		if n.contains("_FurCards_"):
			# alpha-masked strands keep their imported material (alpha scissor, explicit back faces, coat colour
			# per vertex, emissive glow strands)
			parts.append([part, lod, tier])
			continue
		if part.mesh != null:
			for s in part.mesh.get_surface_count():
				var mat := part.mesh.surface_get_material(s)
				if mat != null:
					part.set_surface_override_material(s, _material(species, level, mat, group, lod))
		# LOD1 near, LOD2 far: switched by update_lod() (not by visibility-range margins: Godot starts a
		# new instance hidden on both sides of the margin band, so a creature first seen 0.88-1.12 x the
		# switch distance away stayed invisible until it left the band).
		part.visibility_range_begin = 0.0
		part.visibility_range_end = 0.0
		parts.append([part, lod, tier])
		meshes.append(part)
	for player: AnimationPlayer in actor.find_children("*", "AnimationPlayer", true, false):
		if _looped.has(species):
			break
		for clip in manifest(species).get("clips", {}).values():
			var anim := player.get_animation(StringName(str(clip.name)))
			if anim != null:
				anim.loop_mode = Animation.LOOP_LINEAR if bool(clip.loop) else Animation.LOOP_NONE
		_looped[species] = true
	actor.set_meta(META, {"species": species, "level": level, "meshes": meshes, "parts": parts, "lod_m": lod_m})
	_show_lod(actor, 1)  # near until the first update_lod(): always one LOD drawn
	set_life(actor, 1.0)

## LOD by view distance with hysteresis from the shown LOD: LOD2 beyond (1 + h) x the switch distance,
## LOD1 again under (1 - h) x; between them the shown one stays. Exactly one LOD is drawn at any time.
## An orthographic camera (the city) counts as the perspective distance giving the same on-screen size.
static func update_lod(actor: Node3D, camera: Camera3D) -> int:
	if not owns(actor) or camera == null:
		return 0
	var info: Dictionary = actor.get_meta(META)
	var shown := int(info.get("lod", 1))
	var d := view_distance(camera, actor.global_position)
	var switch_m := float(info.get("lod_m", 50.0))
	if shown == 1 and d > switch_m * (1.0 + LOD_HYSTERESIS):
		_show_lod(actor, 2)
	elif shown == 2 and d < switch_m * (1.0 - LOD_HYSTERESIS):
		_show_lod(actor, 1)
	return int(info.get("lod", 1))

static func view_distance(camera: Camera3D, at: Vector3) -> float:
	if camera.projection == Camera3D.PROJECTION_ORTHOGONAL:
		return camera.size / (2.0 * tan(deg_to_rad(camera.fov) * 0.5))
	return camera.global_position.distance_to(at)

static func _show_lod(actor: Node3D, lod: int) -> void:
	var info: Dictionary = actor.get_meta(META)
	info.lod = lod
	for row in info.get("parts", []):
		var part: MeshInstance3D = row[0]
		if is_instance_valid(part):
			part.visible = int(row[1]) == lod and int(info.level) >= int(row[2])

static func owns(actor: Node3D) -> bool:
	return actor != null and actor.has_meta(META)

static func species_of(actor: Node3D) -> String:
	return str(actor.get_meta(META, {}).get("species", "")) if owns(actor) else ""

## Emission of runes/veins/seams: 1 alive, 0 dead (instance uniform, materials stay shared).
static func set_life(actor: Node3D, value: float) -> void:
	if not owns(actor):
		return
	var info: Dictionary = actor.get_meta(META)
	if is_equal_approx(float(info.get("life", -1.0)), value):
		return
	info.life = value
	for part in info.get("meshes", []):
		if is_instance_valid(part):
			(part as GeometryInstance3D).set_instance_shader_parameter(&"life", value)
	# glowing fur strands (imported material, shared): fade with a per-actor copy only while not fully alive
	for entry in info.get("parts", []):
		var fur := entry[0] as MeshInstance3D
		if not is_instance_valid(fur) or not String(fur.name).contains("_FurCards_") or fur.mesh == null:
			continue
		var fm := fur.mesh.surface_get_material(0) as BaseMaterial3D
		if fm == null or not fm.emission_enabled:
			continue
		if value >= 0.999:
			fur.material_override = null
			continue
		var faded := fur.material_override as BaseMaterial3D
		if faded == null:
			faded = fm.duplicate() as BaseMaterial3D
			fur.material_override = faded
		faded.emission_energy_multiplier = fm.emission_energy_multiplier * clampf(value, 0.0, 1.0)
