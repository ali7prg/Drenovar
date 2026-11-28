extends RefCounted
## Story intro cast helpers: the story clip library on any human_shared rig, small hand props, the
## wrist mark, the "light along the bars" sweep on the cage. Presentation only (no game state).

const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const CLIPS_PATH := "res://assets/forest_rescue/humans/lf_story_clips.glb"
const CLIPS_META := "res://assets/forest_rescue/humans/lf_story_clips.meta.json"
const CLIPS_PREFIX := "lf_story_clips_rig/"
const PORTRAITS := "res://assets/story/portraits/"
## Painted portraits (owner's art, background removed) for every story speaker: name, file, share of
## the screen height, epithet, accent (aura, quote mark, flourish). All of them look to the right in
## the picture; the dialogue mirrors them on the right side so they look into the screen. An optional
## sixth value keeps the text clear of a hand that matters (Danko's marked wrist).
const SPEAKER_PORTRAITS := {
	"orc": ["Vargash", "orc_warden.png", 0.78, "Warden of the Birch Cage", "#e0782e"],
	"tenerys": ["Tenerys", "tenerys.png", 0.76, "Dusk hunter", "#5aa8ff"],
	"danko": ["Danko", "danko.png", 0.8, "Escaped from the cage", "#d8b06a", 1.04],
	"ostap": ["Grandpa Ostap", "ostap.png", 0.8, "Elder of Drenovar", "#f0a845"],
	"vesna": ["Grandma Vesna", "vesna.png", 0.78, "Keeper of the hearth", "#8fb874"],
	"mitya": ["Mitya", "mitya.png", 0.7, "Ostap's grandson", "#d4704f"],
}

static var library_cache: Dictionary = {}   # rig prefix -> AnimationLibrary (retargeted copies)
static var clips_meta: Dictionary = {}
static var source_player: AnimationPlayer
static var source_root: Node

## Registers the painted portrait of each speaker in `ids` on a StoryDialogue.
static func add_portrait_speakers(dialogue: Node, ids: Array) -> void:
	for id: String in ids:
		var entry: Array = SPEAKER_PORTRAITS[id]
		dialogue.add_image_speaker(id, String(entry[0]), PORTRAITS + String(entry[1]),
			{"height": float(entry[2]), "faces": "right", "edge": 0.0, "epithet": String(entry[3]), "accent": Color(String(entry[4])),
			"inset": float(entry[5]) if entry.size() > 5 else 0.86})

## Adds every lf_story_* clip to `rig` (track prefix retargeted to the rig's own armature) and merges
## their meta (markers, ground speed, loop) so play()/markers work as for the rig's own clips.
static func add_story_clips(rig: Rig) -> void:
	if rig == null or rig.player == null or rig.model == null:
		return
	var prefix := find_rig_prefix(rig)
	if prefix.is_empty():
		push_warning("StoryCast: no *_rig armature on " + rig.actor_id)
		return
	if clips_meta.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(CLIPS_META))
		clips_meta = parsed.get("clips", {}) if parsed is Dictionary else {}
	if not library_cache.has(prefix):
		library_cache[prefix] = build_library(prefix)
	var library: AnimationLibrary = library_cache[prefix]
	if library == null:
		return
	if not rig.player.has_animation_library("story"):
		rig.player.add_animation_library("story", library)
	var meta_clips: Dictionary = rig.meta.get("clips", {}).duplicate()
	for id in clips_meta:
		meta_clips[id] = clips_meta[id]
	rig.meta = rig.meta.duplicate()
	rig.meta["clips"] = meta_clips
	rig.resolved.clear()

static func find_rig_prefix(rig: Rig) -> String:
	for child in rig.model.get_children():
		if String(child.name).ends_with("_rig"):
			return String(child.name) + "/"
	for node in rig.model.find_children("*_rig", "Node3D", true, false):
		return String(rig.model.get_path_to(node)) + "/"
	return ""

static func build_library(prefix: String) -> AnimationLibrary:
	if source_player == null:
		var scene: PackedScene = load(CLIPS_PATH)
		if scene == null:
			push_warning("StoryCast: story clip library missing")
			return null
		source_root = scene.instantiate()
		var players := source_root.find_children("*", "AnimationPlayer", true, false)
		source_player = players[0] if not players.is_empty() else null
		if source_player == null:
			return null
	var library := AnimationLibrary.new()
	for clip_name in source_player.get_animation_list():
		var short := String(clip_name).get_slice("/", String(clip_name).get_slice_count("/") - 1)
		if not short.begins_with("lf_story_"):
			continue
		var animation: Animation = source_player.get_animation(clip_name).duplicate(true)
		for track in animation.get_track_count():
			var path := String(animation.track_get_path(track))
			if path.begins_with(CLIPS_PREFIX):
				animation.track_set_path(track, NodePath(prefix + path.trim_prefix(CLIPS_PREFIX)))
		var spec: Dictionary = clips_meta.get(short, {})
		if bool(spec.get("loop", false)):
			animation.loop_mode = Animation.LOOP_LINEAR
		library.add_animation(short, animation)
	return library

## A small prop parented to a bone (PropR / PropL / a hand) of the rig's skeleton.
static func attach(rig: Rig, bone_name: String, prop: Node3D, offset := Transform3D.IDENTITY) -> BoneAttachment3D:
	if rig == null or rig.model == null:
		return null
	var skeletons := rig.model.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty():
		return null
	var skeleton: Skeleton3D = skeletons[0]
	if skeleton.find_bone(bone_name) < 0:
		return null
	var holder := BoneAttachment3D.new()
	holder.name = "Story_" + bone_name + "_" + String(prop.name)
	holder.bone_name = bone_name
	skeleton.add_child(holder)
	prop.transform = offset
	holder.add_child(prop)
	return holder

## A wooden cup (top view reads as a dark ring with water).
static func make_cup() -> Node3D:
	var cup := Node3D.new()
	cup.name = "Cup"
	var body := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.055
	mesh.bottom_radius = 0.045
	mesh.height = 0.1
	mesh.radial_segments = 12
	body.mesh = mesh
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("#7a5532")
	wood.roughness = 0.9
	body.material_override = wood
	body.position = Vector3(0, 0.05, 0)
	cup.add_child(body)
	var water := MeshInstance3D.new()
	var disc := CylinderMesh.new()
	disc.top_radius = 0.046
	disc.bottom_radius = 0.046
	disc.height = 0.004
	disc.radial_segments = 12
	water.mesh = disc
	var wet := StandardMaterial3D.new()
	wet.albedo_color = Color("#9fc4d6")
	wet.metallic = 0.2
	wet.roughness = 0.15
	water.material_override = wet
	water.position = Vector3(0, 0.092, 0)
	cup.add_child(water)
	return cup

## Red-brown stripes round the wrist: the print of the bars (read in the dialogue close-up and at
## the threshold when the boy looks).
static func make_wrist_mark() -> Node3D:
	var mark := Node3D.new()
	mark.name = "BarMark"
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("#8a2f22")
	material.roughness = 0.8
	for i in 3:
		var band := MeshInstance3D.new()
		var torus := TorusMesh.new()
		torus.inner_radius = 0.034
		torus.outer_radius = 0.043
		torus.rings = 12
		torus.ring_segments = 6
		band.mesh = torus
		band.material_override = material
		band.position = Vector3(0, -0.035 * i, 0)
		mark.add_child(band)
	return mark

## The cage bars light up in a band that runs along them (the orc drains strength through the bars).
## Returns the overlay material: set "sweep" 0..1 (band position) and "energy" 0..1.
static func bar_sweep(cage: Rig) -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never;
uniform float sweep = 0.0;
uniform float energy = 0.0;
uniform vec3 tint : source_color = vec3(0.45, 1.0, 0.55);
uniform vec3 origin = vec3(0.0);
varying vec3 local_pos;
void vertex() { local_pos = VERTEX; }
void fragment() {
	float h = clamp(local_pos.y / 3.4, 0.0, 1.0);
	float around = atan(local_pos.x - origin.x, local_pos.z - origin.z) / 6.2831 + 0.5;
	float phase = fract(around + h * 0.35 - sweep);
	float band = smoothstep(0.0, 0.05, phase) * (1.0 - smoothstep(0.05, 0.22, phase));
	float glow = energy * (band * 1.6 + 0.12);
	ALBEDO = tint * glow;
	ALPHA = clamp(glow, 0.0, 1.0);
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	if cage != null and cage.model != null:
		for mesh: MeshInstance3D in cage.model.find_children("*", "MeshInstance3D", true, false):
			var lower := String(mesh.name).to_lower()
			if lower.contains("roof") or lower.contains("socket"):
				continue
			mesh.material_overlay = material
	return material
