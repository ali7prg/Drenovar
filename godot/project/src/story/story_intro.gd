extends Node
## DRENOVAR story intro «The Birch Clearing» (build 1025).
##
## Plays on the REAL maps: the forest of the town (Birch Clearing, lf_site_01 of the forest campaign:
## its cage, guardian Tenerys, the trail to the ruined arch) and the town itself (the first town hall).
## Four beats: the round-up at the cage, the cage and the escape, the chase, home. Ends in the city
## camera the player had before it started, so the player can tap the town hall at once.
##
## Presentation only: the server state is never touched (the fog opened round the scenes is a
## projection shown through forest_game.set_presentation and dropped at the end; the campaign's own
## cage, captives and artifact of site 01 are not used — the story stages its own copies, hidden by the
## presentation, and the campaign keeps them exactly as the player will find them at Town Hall III).
##
## Deterministic: every motion advances with the frame delta (fixed-fps recordings, qa_story_record.gd).

signal finished(skipped: bool)

const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")
const StoryDialogue = preload("res://src/story/story_dialogue.gd")
const StoryCast = preload("res://src/story/story_cast.gd")
const UiKit = preload("res://src/ui_kit.gd")

## Seconds behind black before t = 0: the presentation fog finishes its reveal (2 s) and the trees of
## the clearing stream in, so the first frame is the finished map.
const PREROLL := 3.0
const HUMANS := "res://assets/forest_rescue/humans/"
const PROPS := "res://assets/forest_rescue/props/"
const VOICE := "res://assets/story/voice/"
const AUDIO := "res://assets/audio/"
const FR_AUDIO := "res://assets/forest_rescue/audio/"

## Where things are (metres, the town's world space; site 01 of world-atlas.json).
const CAGE := Vector2(-80.0, -16.0)          # site 01 cage, door faces +Z
const ARCH := Vector2(-70.0, 16.0)           # lf_mark_ruined_arch: the cover on the trail
const HALL := Vector2(-5.0, -5.0)            # B01 (first town hall)

## What a one-shot clip settles into when it ends (no cue needed). Clips not listed hold their last frame.
const FOLLOW := {
	"lf_orc_look": "lf_orc_idle", "lf_orc_turn_left": "lf_orc_idle", "lf_orc_turn_right": "lf_orc_idle",
	"lf_orc_order_point": "lf_orc_idle", "lf_orc_order_point_left": "lf_orc_idle", "lf_orc_drain": "lf_orc_idle",
	"lf_orc_roar": "lf_orc_idle",
	"alert": "idle", "attack_bite": "idle", "attack_claw": "idle", "howl": "idle", "turn_left": "idle", "turn_right": "idle",
	"lf_story_collapse": "lf_story_collapse_hold", "lf_story_support": "lf_story_support_hold",
	"lf_story_hide": "lf_story_hide_hold", "lf_story_sit_down": "lf_story_sit", "lf_story_guide_sit": "lf_civilian_wait",
	"lf_story_catch": "lf_civilian_wait", "lf_story_offer": "lf_civilian_wait", "lf_story_point_low": "lf_civilian_wait",
	"lf_story_show_wrist": "lf_story_sit", "lf_story_drink": "lf_story_sit", "lf_civilian_stand_up": "lf_civilian_wait",
	"lf_civilian_look_back": "lf_civilian_cage_wait", "lf_story_take_lantern": "lf_civilian_wait",
	"lf_story_peek": "lf_story_hide_hold",
}

## Spoken lines: id → [speaker, text, side]. Voices: assets/story/voice/<id>.ogg.
const LINES := {
	"l01_orc_trail": ["orc", "They're running for the birch trail. It's the only way out. Close it!", "left"],
	"l02_ten_ferns": ["tenerys", "Not the trail. Through the ferns. I'll be there first.", "right"],
	"l03_orc_edge": ["orc", "Walk the edge till dusk. Nobody leaves.", "left"],
	"l04_ten_smell": ["tenerys", "One of them is out. I can smell him.", "right"],
	"l05_mit_wrist": ["mitya", "Grandpa, look at his wrist. Bar marks.", "right"],
	"l06_dan_cage": ["danko", "An orc keeps a cage in the birch clearing. The bars drain your strength.", "left"],
	"l07_mit_others": ["mitya", "And the others? You left them there?", "right"],
	"l08_ost_many": ["ostap", "How many?", "right"],
	"l09_dan_three": ["danko", "Three. Lada, Tim and Sava.", "left"],
	"l10_ves_bread": ["vesna", "I'll pack the bread.", "right"],
}

var game: Node                 # main.gd
var stage: Node3D              # landscape.gd
var forest: Node               # forest_game.gd
var world: Node                # forest_world.gd
var root: Node3D
var layer: CanvasLayer
var dialogue: StoryDialogue
var blocker: Control
var fade_rect: ColorRect
var caption: Label
var skip_button: Button
var voice_player: AudioStreamPlayer
var sfx_players: Array[AudioStreamPlayer] = []
var cast: Dictionary = {}      # id -> Rig
var t := 0.0
var length := 0.0
var cues: Array = []           # [time, Callable], sorted
var cue_index := 0
var walkers: Dictionary = {}   # id -> walk state
var turners: Dictionary = {}   # id -> {from, to, t0, seconds}
var cam_keys: Array = []       # {t, at (Vector3 | String actor id | Callable), zoom, offset}
var fade_keys: Array = []      # [time, alpha]
var line_hide_at := -1.0
var running := false
var start_target := Vector3.ZERO
var start_zoom := 68.0
var hud_was_visible := true
var door_time := -1.0          # seconds into lf_cage_gate_open shown by hand (-1: clip-driven)
var door_goal := -1.0
var door_rate := 0.0
var sweep: ShaderMaterial
var sweep_energy := 0.0
var sweep_goal := 0.0
var orc_glow := 0.0
var orc_glow_goal := 0.0
var lantern_prop: Node3D
var lantern_hook: Node3D
var cup_prop: Node3D
var skipped := false
var forest_presented := false
var actor_y_offset: Dictionary = {}
var cage_floor := 0.12

# ------------------------------------------------------------------ setup

## main: the game (src/main.gd). Builds the cast (blocking loads: QA and the first-launch path wait
## on a loading screen) and starts at t = 0.
func begin(main: Node) -> void:
	game = main
	stage = main.stage
	forest = main.forest_game
	world = forest.world if forest != null else null
	start_target = stage.target
	start_zoom = stage.zoom
	root = Node3D.new()
	root.name = "StoryIntro"
	stage.add_child(root)
	build_ui()
	build_audio()
	build_cast()
	build_props()
	present_forest(true)
	if "hud" in game and game.hud != null:
		hud_was_visible = game.hud.visible
		game.hud.visible = false
	var sound := get_node_or_null("/root/Sound")
	if sound != null:
		sound.set_theme_override("forest")
	script_timeline()
	t = -PREROLL
	running = true
	apply_frame(0.0)

func build_ui() -> void:
	layer = CanvasLayer.new()
	layer.name = "StoryLayer"
	layer.layer = 30
	add_child(layer)
	blocker = Control.new()
	blocker.name = "InputBlocker"
	blocker.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	blocker.mouse_filter = Control.MOUSE_FILTER_STOP
	layer.add_child(blocker)
	dialogue = StoryDialogue.new()
	layer.add_child(dialogue)
	caption = Label.new()
	caption.name = "Caption"
	caption.add_theme_font_override("font", UiKit.TITLE_FONT)
	caption.add_theme_font_size_override("font_size", 30)
	caption.add_theme_color_override("font_color", Color("#f7e2ad"))
	caption.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.85))
	caption.add_theme_constant_override("shadow_offset_x", 2)
	caption.add_theme_constant_override("shadow_offset_y", 3)
	caption.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	caption.position = Vector2(56, 34)
	caption.modulate.a = 0.0
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(caption)
	skip_button = Button.new()
	skip_button.name = "Skip"
	skip_button.text = "Skip  ›"
	skip_button.flat = true
	skip_button.focus_mode = Control.FOCUS_NONE
	skip_button.add_theme_font_override("font", UiKit.LABEL_FONT)
	skip_button.add_theme_font_size_override("font_size", 18)
	skip_button.add_theme_color_override("font_color", Color(0.97, 0.89, 0.68, 0.72))
	skip_button.add_theme_color_override("font_hover_color", Color("#f7e2ad"))
	skip_button.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	skip_button.position = Vector2(-120, 18)
	skip_button.size = Vector2(100, 40)
	skip_button.pressed.connect(skip)
	layer.add_child(skip_button)
	fade_rect = ColorRect.new()
	fade_rect.name = "Fade"
	fade_rect.color = Color(0.02, 0.016, 0.012, 1.0)
	fade_rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(fade_rect)

func build_audio() -> void:
	voice_player = AudioStreamPlayer.new()
	voice_player.bus = &"Voice"
	add_child(voice_player)
	for i in 6:
		var player := AudioStreamPlayer.new()
		player.bus = &"SFX"
		add_child(player)
		sfx_players.append(player)

func human(id: String, visual: String, scale := 1.0, look: Dictionary = {}) -> Rig:
	var actor := Rig.new()
	actor.model_scale = scale
	if not look.is_empty():
		actor.variant = look
	actor.setup("story_" + id, HUMANS + "lf_civilian_%s.glb" % visual)
	root.add_child(actor)
	actor.poll_load(true)
	StoryCast.add_story_clips(actor)
	actor.set_meta("fog_exempt", true)
	actor.clip_finished.connect(on_clip_finished)
	cast[id] = actor
	return actor

func on_clip_finished(rig: Node3D, clip_id: String) -> void:
	if FOLLOW.has(clip_id) and rig is Rig:
		(rig as Rig).play([String(FOLLOW[clip_id])], 0.25)

func beast(id: String, level: int, tint := Color.WHITE, size := 1.0) -> Rig:
	var species := "tenerys"
	var actor := Rig.new()
	actor.model_scale = (1.02 + 0.16 * level) * CreatureVisuals.display_scale(species) * size
	actor.painted = false
	if CreatureVisuals.active(species):
		actor.creature_species = species
		actor.creature_level = level
	var original := ""
	var models: Dictionary = game.data.get("creatureModels", {}) if game.data is Dictionary else {}
	if models.has(species):
		original = String(models[species][level - 1])
	actor.tint = tint
	actor.setup("story_" + id, CreatureVisuals.model_path(species, level, original))
	root.add_child(actor)
	actor.poll_load(true)
	actor.clip_finished.connect(on_clip_finished)
	cast[id] = actor
	return actor

func captive_look(captive_id: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(HUMANS + "captive_variants.json"))
	if parsed is Dictionary:
		var entry: Variant = parsed.get("captives", {}).get(captive_id)
		if entry is Dictionary:
			return entry
	return {}

func build_cast() -> void:
	# The fugitive: a man not among site 01's three captives (Lada, Tim, Sava stay in the cage).
	human("danko", "quarry_worker", 1.0, {"tint": {"cloth": [0.82, 0.86, 0.95], "hair": [0.55, 0.45, 0.4]}})
	human("lada", "courier", 1.0, captive_look("lf_captive_01_a"))
	human("tim", "ferryman", 1.0, captive_look("lf_captive_01_b"))
	human("sava", "miller", 1.0, captive_look("lf_captive_01_c"))
	human("ostap", "cooper", 1.0, {"tint": {"cloth": [0.9, 0.85, 0.78], "hair": [2.2, 2.2, 2.2]}})
	human("vesna", "herbalist", 0.96, {"tint": {"cloth": [0.95, 0.8, 0.72], "hair": [2.0, 2.0, 2.0]}})
	human("mitya", "courier", 0.7, {"tint": {"cloth": [0.75, 0.9, 0.8], "hair": [0.8, 0.62, 0.45]}})
	var orc := Rig.new()
	orc.setup("story_orc", HUMANS + "lf_orc_warden.glb")
	root.add_child(orc)
	orc.poll_load(true)
	orc.clip_finished.connect(on_clip_finished)
	cast["orc"] = orc
	# Site 01's guardian is Tenerys I (campaign.json); the wolf of the pack is smaller and darker.
	beast("tenerys", 1)
	beast("wolf", 2, Color.WHITE, 0.74)
	var cage := Rig.new()
	cage.setup("story_cage", PROPS + "lf_cage_wood.glb")
	root.add_child(cage)
	cage.poll_load(true)
	cast["cage"] = cage
	# From the city camera the roof hides the people inside (the game fades it the same way near it).
	for node in cage.model.find_children("*", "Node3D", true, false):
		if String(node.name).to_lower().contains("roof"):
			(node as Node3D).visible = false
	(cast.ostap as Rig).marker.connect(on_marker)
	# The cage floor (captive_slot_N nodes of lf_cage_wood): the people inside stand on it, not in it.
	var slot := cage.part("captive_slot_0")
	if slot != null and slot.is_inside_tree():
		cage_floor = maxf(0.05, slot.global_position.y - cage.global_position.y)
	sweep = StoryCast.bar_sweep(cage)
	var mark := StoryCast.make_wrist_mark()
	StoryCast.attach(cast.danko, "LeftHand", mark, Transform3D(Basis.IDENTITY, Vector3(0, 0.06, 0)))
	for id in cast:
		(cast[id] as Rig).visible = false
	register_speakers()

func register_speakers() -> void:
	# Everyone speaks from a painted portrait (owner's art, background removed).
	StoryCast.add_portrait_speakers(dialogue, ["orc", "tenerys", "danko", "mitya", "ostap", "vesna"])

func build_props() -> void:
	# Lantern on its hook by the hall door (Ostap takes it down) and the bench where Vesna seats Danko.
	var door := hall_door()
	var out := hall_out()
	var side := Vector3(out.z, 0, -out.x)
	var hook_base: Vector3 = stage.ground_point(door + side * 1.7 + out * 0.6)
	lantern_hook = Node3D.new()
	lantern_hook.name = "LanternHook"
	root.add_child(lantern_hook)
	lantern_hook.position = hook_base
	var post := MeshInstance3D.new()
	var post_mesh := CylinderMesh.new()
	post_mesh.top_radius = 0.06
	post_mesh.bottom_radius = 0.08
	post_mesh.height = 2.3
	post.mesh = post_mesh
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("#5c4128")
	wood.roughness = 0.95
	post.material_override = wood
	post.position = Vector3(0, 1.15, 0)
	lantern_hook.add_child(post)
	var arm := MeshInstance3D.new()
	var arm_mesh := BoxMesh.new()
	arm_mesh.size = Vector3(0.06, 0.06, 0.55)
	arm.mesh = arm_mesh
	arm.material_override = wood
	arm.position = Vector3(0, 2.2, 0.25)
	lantern_hook.add_child(arm)
	lantern_hook.look_at(lantern_hook.position + out, Vector3.UP)
	lantern_hook.rotate_y(PI)
	lantern_prop = make_lantern()
	lantern_hook.add_child(lantern_prop)
	lantern_prop.position = Vector3(0, 1.82, 0.45)
	var bench := MeshInstance3D.new()
	var bench_mesh := BoxMesh.new()
	bench_mesh.size = Vector3(1.3, 0.45, 0.42)
	bench.mesh = bench_mesh
	bench.material_override = wood
	bench.name = "Bench"
	root.add_child(bench)
	var seat := bench_spot()
	bench.position = stage.ground_point(seat) + Vector3.UP * 0.225
	bench.look_at(bench.position + out, Vector3.UP)
	cup_prop = StoryCast.make_cup()
	lantern_hook.visible = false
	bench.visible = false
	cast["bench"] = bench
	cast["hook"] = lantern_hook

func make_lantern() -> Node3D:
	var path := "res://assets/forest_rescue/landmarks/lf_env_lantern.glb"
	var scene: PackedScene = load(path) if ResourceLoader.exists(path) else null
	var holder := Node3D.new()
	holder.name = "Lantern"
	if scene != null:
		var model: Node3D = scene.instantiate()
		holder.add_child(model)
		var light := OmniLight3D.new()
		light.light_color = Color("#ffb45e")
		light.light_energy = 1.4
		light.omni_range = 3.5
		light.position = Vector3(0, 0.15, 0)
		holder.add_child(light)
	return holder

# ------------------------------------------------------------------ geometry helpers

func p3(xz: Vector2, lift := 0.0) -> Vector3:
	return stage.ground_point(Vector3(xz.x, 0, xz.y)) + Vector3.UP * lift

## Height of the cage floor under xz: the stone plinth inside, a ramp over the door step, 0 elsewhere.
func cage_lift(xz: Vector2) -> float:
	var cage: Node3D = cast.get("cage")
	if cage == null or not cage.visible:
		return 0.0
	var local := xz - CAGE
	if absf(local.x) > 1.75 or local.y < -1.7 or local.y > 2.7:
		return 0.0
	return cage_floor * (1.0 - smoothstep(1.35, 2.5, local.y))

func cage_point(local: Vector3) -> Vector3:
	return p3(CAGE) + local

## The hall's front: model yaw 0 in the town plan (landscape.gd model_transform), front faces +Z.
const HALL_FRONT := Vector3(0, 0, 1)
## The door steps of the hall I model, from its plan point (measured in the city camera).
const HALL_DOOR_OFFSET := Vector3(3.6, 0, 5.4)
## The ruined watchpost (lf_env_ruined_watchpost_1 of the forest world): the cover on the trail.
const RUIN := Vector2(-69.7, 24.8)

func hall_out() -> Vector3:
	return HALL_FRONT

func hall_center() -> Vector3:
	for marker: Dictionary in stage.get("place_markers") if stage.get("place_markers") != null else []:
		if String(marker.get("kind", "")) != "building":
			continue
		var item: Variant = marker.get("item")
		if item is Dictionary and String(item.get("type", "")).begins_with("ECO-05"):
			var position: Vector3 = marker.get("position", Vector3.ZERO)
			return stage.ground_point(Vector3(position.x, 0, position.z))
	return p3(HALL)

func hall_door() -> Vector3:
	return hall_center() + HALL_DOOR_OFFSET

func bench_spot() -> Vector3:
	var out := hall_out()
	var side := Vector3(out.z, 0, -out.x)
	return hall_door() + out * 1.6 - side * 1.4

# ------------------------------------------------------------------ presentation fog

func present_forest(on: bool) -> void:
	if forest == null or world == null:
		return
	if not on:
		forest.set_presentation({})
		forest_presented = false
		return
	var bits := ForestFog.default_town_bits()
	stamp(bits, CAGE + Vector2(2, 2), 24.0)
	for pair in [["lf_site_01", "lf_mark_ruined_arch"], ["lf_site_01", "lf_junction_grove"], ["lf_mark_ruined_arch", "lf_junction_w"]]:
		var trail: PackedVector3Array = world.trail_path(pair[0], pair[1])
		for p in trail:
			stamp(bits, Vector2(p.x, p.z), 11.0)
	stamp(bits, ARCH, 15.0)
	stamp(bits, RUIN, 16.0)
	stamp(bits, Vector2(-56.0, 16.0), 12.0)
	stamp(bits, Vector2(-62, 6), 12.0)
	var now := 0.0
	if forest.client != null and forest.client.adv is Dictionary:
		now = float(forest.client.adv.get("serverTime", 0))
	forest.set_presentation({"access": {"unlocked": true}, "intro": {"status": "acknowledged"},
		"fog": {"visibleBase64": Marshalls.raw_to_base64(bits), "revision": 9_000_000}, "serverTime": now})
	forest_presented = true

func stamp(bits: PackedByteArray, p: Vector2, r: float) -> void:
	var x := p.x - r
	while x <= p.x + r:
		var z := p.y - r
		while z <= p.y + r:
			if Vector2(x, z).distance_to(p) <= r:
				var cell := ForestFog.cell_of(x, z)
				ForestFog.set_bit(bits, cell.x, cell.y)
			z += 2.0
		x += 2.0

# ------------------------------------------------------------------ timeline primitives

func at(time: float, action: Callable) -> void:
	cues.append([time, action])

func show_actor(id: String, xz: Vector2, yaw_deg: float, clip: Array = [], lift := 0.0) -> void:
	var actor: Node3D = cast[id]
	actor.position = p3(xz, lift)
	actor.rotation.y = deg_to_rad(yaw_deg)
	actor.visible = true
	actor_y_offset[id] = lift
	if not clip.is_empty() and actor is Rig:
		(actor as Rig).play(clip, 0.0, true)

func hide_actor(id: String) -> void:
	(cast[id] as Node3D).visible = false
	walkers.erase(id)

## Walks `id` along `points` (xz) at `speed` m/s playing `clip` (speed scaled to the clip's ground speed);
## at the end plays `end_clip` (and faces `end_yaw` if given).
func walk(id: String, points: Array, speed: float, clip: Array, end_clip: Array = [], end_yaw := NAN, lift := 0.0, clip_speed := -1.0) -> void:
	var actor: Rig = cast[id]
	var path: Array = [Vector2(actor.position.x, actor.position.z)]
	path.append_array(points)
	walkers[id] = {"path": path, "segment": 0, "speed": speed, "end_clip": end_clip, "end_yaw": end_yaw, "lift": lift}
	actor_y_offset[id] = lift
	var natural := actor.ground_speed(String(clip[0]), speed) if not clip.is_empty() else speed
	var rate := clip_speed if clip_speed > 0.0 else clampf(speed / maxf(natural, 0.1), 0.55, 1.6)
	if not clip.is_empty():
		actor.play(clip, 0.18, false, rate)

## Moves `id` along a clip's own root path (meta rootPathXYZ_m: offsets from the start root every 0.1 s,
## the actor keeps its yaw): for in-place clips whose feet were authored against that path.
func follow_root_path(id: String, clip_id: String) -> void:
	var actor: Rig = cast[id]
	var samples: Array = StoryCast.clips_meta.get(clip_id, {}).get("rootPathXYZ_m", [])
	if samples.is_empty():
		return
	var start := Vector2(actor.position.x, actor.position.z)
	walkers[id] = {"track": samples, "t0": t, "start": start, "lift": cage_lift(start), "yaw": actor.rotation.y}

func play(id: String, clip: Array, blend := 0.2, restart := true, speed := 1.0) -> void:
	(cast[id] as Rig).play(clip, blend, restart, speed)

func face(id: String, target: Variant, seconds := 0.45) -> void:
	var actor: Node3D = cast[id]
	var yaw: float
	if target is Vector2:
		var d: Vector2 = (target as Vector2) - Vector2(actor.position.x, actor.position.z)
		yaw = atan2(d.x, d.y)
	else:
		yaw = deg_to_rad(float(target))
	turners[id] = {"from": actor.rotation.y, "to": actor.rotation.y + angle_difference(actor.rotation.y, yaw), "t0": t, "seconds": seconds}

func say(line_id: String) -> void:
	var spec: Array = LINES[line_id]
	dialogue.show_line(String(spec[0]), String(spec[1]), String(spec[2]))
	var stream: AudioStream = load(VOICE + line_id + ".ogg") if ResourceLoader.exists(VOICE + line_id + ".ogg") else null
	var seconds := 0.6 + String(spec[1]).length() / 15.0
	if stream != null:
		voice_player.stream = stream
		voice_player.play()
		seconds = stream.get_length()
	line_hide_at = t + seconds + 0.45

func sfx(path: String, gain_db := 0.0, pitch := 1.0) -> void:
	if not ResourceLoader.exists(path):
		return
	var stream: AudioStream = load(path)
	var chosen: AudioStreamPlayer = sfx_players[0]
	for player in sfx_players:
		if not player.playing:
			chosen = player
			break
	chosen.stream = stream
	chosen.volume_db = gain_db
	chosen.pitch_scale = pitch
	chosen.play()

## Camera key: from the previous key the view eases (smootherstep) to this one by `time`.
## at: Vector3 (world) | String (actor id, followed live) | Array [id, id] (midpoint).
func cam(time: float, at_value: Variant, zoom: float, offset := Vector3.ZERO) -> void:
	cam_keys.append({"t": time, "at": at_value, "zoom": zoom, "offset": offset})

func fade(time: float, alpha: float) -> void:
	fade_keys.append([time, alpha])

func show_caption(text: String) -> void:
	caption.text = text
	var tween := create_tween()
	tween.tween_property(caption, "modulate:a", 1.0, 0.6)
	tween.tween_interval(2.4)
	tween.tween_property(caption, "modulate:a", 0.0, 0.8)

# ------------------------------------------------------------------ the story

func script_timeline() -> void:
	var cage_door_out := CAGE + Vector2(0.0, 2.7)
	var inside := {
		"lada": CAGE + Vector2(-0.85, -0.2), "sava": CAGE + Vector2(0.05, -0.45), "tim": CAGE + Vector2(-0.35, 0.55),
		"danko": CAGE + Vector2(0.25, 0.55)}
	# The latch_reach root (lf_story_clips meta cagePlacement): inside, by the latch-side bars, facing the door.
	var latch_spot := CAGE + Vector2(0.95, 0.95)
	var exit := Vector2(-76.4, -8.3)

	# ----- beat 1: the round-up (0 – 17 s) -----
	fade(0.0, 1.0)
	fade(0.9, 0.0)
	at(0.0, func() -> void:
		show_actor("cage", CAGE, 0.0)
		var cage: Rig = cast.cage
		cage.hold_end(["lf_cage_gate_settle", "lf_cage_gate_open"])
		show_actor("orc", Vector2(-84.6, -12.6), 80.0, ["lf_orc_idle"])
		show_actor("tenerys", Vector2(-87.6, -19.6), 30.0, ["idle"])
		show_actor("danko", Vector2(-68.4, -39.5), 190.0)
		show_actor("tim", Vector2(-67.4, -41.0), 190.0)
		show_actor("lada", Vector2(-69.4, -41.4), 190.0)
		show_actor("sava", Vector2(-68.2, -43.0), 190.0)
		walk("danko", [Vector2(-73.4, -18.5), exit], 2.9, ["lf_story_run"], ["lf_story_halt"])
		walk("tim", [Vector2(-72.5, -20.0), exit + Vector2(0.9, -1.9)], 2.95, ["lf_story_run"])
		walk("lada", [Vector2(-74.5, -20.3), exit + Vector2(-0.8, -2.6)], 2.9, ["lf_story_run"])
		walk("sava", [Vector2(-73.6, -22.0), exit + Vector2(0.4, -3.6)], 2.95, ["lf_story_run"])
		sfx(FR_AUDIO + "fr_forest_wind.ogg", -10.0))
	at(0.6, func() -> void: show_caption("Birch Clearing"))
	cam(0.0, Vector3(-77.0, 0, -17.5), 27.0)
	cam(6.5, Vector3(-79.0, 0, -15.0), 23.0)
	at(1.4, func() -> void: play("orc", ["lf_orc_look"], 0.25))
	at(3.3, func() -> void:
		face("orc", Vector2(-87.6, -19.6), 1.0)
		play("orc", ["lf_orc_turn_left"], 0.2))
	at(4.3, func() -> void:
		face("orc", Vector2(-82.0, -9.0), 0.6)
		play("orc", ["lf_orc_order_point"], 0.2)
		say("l01_orc_trail"))
	at(5.0, func() -> void: play("tenerys", ["alert", "idle"], 0.2))
	at(8.6, func() -> void: say("l02_ten_ferns"))
	cam(8.6, Vector3(-80.0, 0, -14.0), 22.0)
	at(8.9, func() -> void:
		play("orc", ["lf_orc_idle"], 0.3)
		walk("tenerys", [Vector2(-86.3, -10.5), Vector2(-82.6, -5.2), Vector2(-77.6, -5.0)], 9.0, ["run"], ["attack_bite", "alert"], deg_to_rad(15.0))
		sfx(AUDIO + "sfx/forest/growl_1.ogg", -3.0))
	at(10.2, func() -> void:
		show_actor("wolf", Vector2(-61.5, -12.0), -100.0)
		walk("wolf", [Vector2(-71.0, -10.6)], 3.2, ["stalk", "walk"], ["attack_claw", "alert"], deg_to_rad(-95.0)))
	cam(11.5, Vector3(-77.0, 0, -10.5), 18.5)
	at(11.6, func() -> void: sfx(AUDIO + "sfx/forest/roar_0.ogg", -2.0))
	at(12.6, func() -> void: sfx(AUDIO + "sfx/forest/growl_0.ogg", -4.0))
	# Danko halts (walker end clip), Tim almost runs into him, the others pull up behind.
	at(11.8, func() -> void:
		play("tim", ["lf_story_catch", "lf_story_halt"], 0.12))
	at(11.95, func() -> void: play("lada", ["lf_story_halt"], 0.15))
	at(12.1, func() -> void: play("sava", ["lf_story_halt"], 0.15))
	at(13.0, func() -> void:
		for id in ["danko", "tim", "lada", "sava"]:
			face(id, Vector2(-77.6, -5.0), 0.3)
			play(id, ["lf_story_backstep"], 0.2))
	at(13.0, func() -> void:
		var actor: Rig = cast.danko
		walkers["danko"] = {"path": [Vector2(actor.position.x, actor.position.z), Vector2(actor.position.x - 0.5, actor.position.z - 0.8)], "segment": 0, "speed": 0.9, "end_clip": [], "end_yaw": NAN, "lift": 0.0, "keep_yaw": true})
	# The open door is the only place between the two beasts: in they go.
	at(14.1, func() -> void:
		walk("sava", [cage_door_out + Vector2(-0.3, 0.3), CAGE + Vector2(0.0, 1.2), inside.sava], 3.1, ["lf_story_run"], ["lf_civilian_cage_sit", "lf_civilian_cage_wait"], deg_to_rad(10.0))
		walk("lada", [cage_door_out + Vector2(-0.5, 0.2), CAGE + Vector2(-0.2, 1.2), inside.lada], 3.0, ["lf_story_run"], ["lf_civilian_cage_stand", "lf_civilian_cage_wait"], deg_to_rad(30.0)))
	at(14.4, func() -> void:
		walk("tim", [cage_door_out + Vector2(0.3, 0.2), CAGE + Vector2(0.2, 1.2), inside.tim], 3.0, ["lf_story_run"], ["lf_civilian_cage_wait"], deg_to_rad(90.0)))
	at(14.6, func() -> void:
		walk("danko", [cage_door_out + Vector2(0.6, 0.1), CAGE + Vector2(0.8, 1.3), inside.danko], 2.9, ["lf_story_run"], ["lf_civilian_cage_wait"], deg_to_rad(-90.0))
		walk("orc", [Vector2(-81.5, -13.0)], 1.25, ["lf_orc_walk"], ["lf_orc_idle"], deg_to_rad(90.0)))
	cam(15.2, Vector3(-80.0, 0, -14.6), 12.5)
	# ----- beat 2: the cage and the escape -----
	at(16.6, func() -> void:
		var cage: Rig = cast.cage
		cage.play(["lf_cage_gate_close"], 0.0, true)
		sfx(FR_AUDIO + "fr_gate_creak.ogg", -2.0, 1.15))
	cam(17.1, cage_point(Vector3(0.6, 1.0, 1.5)), 7.5)
	at(17.8, func() -> void: sfx(FR_AUDIO + "fr_cage_latch.ogg", 2.0))   # the bolt falls (gate_close end)
	cam(18.6, cage_point(Vector3(0.0, 0.8, 0.4)), 10.5)
	at(18.5, func() -> void:
		face("orc", Vector2(CAGE.x, CAGE.y), 0.4)
		play("orc", ["lf_orc_drain"], 0.2)
		sfx(FR_AUDIO + "fr_distant_rumble.ogg", -4.0))
	at(18.9, func() -> void:
		sweep_goal = 1.0
		orc_glow_goal = 1.0
		sfx(AUDIO + "sfx/forest/fog_reveal_0.ogg", -2.0, 0.7))
	at(19.6, func() -> void:
		play("danko", ["lf_story_collapse"], 0.12)
		face("tim", Vector2(inside.danko.x, inside.danko.y), 0.3))
	at(19.85, func() -> void: play("tim", ["lf_story_support"], 0.12))
	at(21.0, func() -> void:
		play("danko", ["lf_story_collapse_hold"], 0.25, false)
		play("tim", ["lf_story_support_hold"], 0.25, false)
		play("lada", ["lf_civilian_cage_sit"], 0.4)
		play("sava", ["lf_civilian_cage_sit"], 0.4))
	at(21.6, func() -> void:
		sweep_goal = 0.0
		orc_glow_goal = 0.0)
	# The warden turns his back: Tenerys is sent to the edge, the wolf with him.
	at(22.2, func() -> void:
		face("orc", Vector2(-92.0, -10.0), 0.9)
		play("orc", ["lf_orc_turn_left"], 0.2))
	at(22.6, func() -> void: say("l03_orc_edge"))
	cam(22.8, Vector3(-82.0, 0, -13.0), 15.0)
	at(23.3, func() -> void:
		walk("orc", [Vector2(-85.4, -12.2)], 1.1, ["lf_orc_walk"], ["lf_orc_idle"], deg_to_rad(-80.0))
		walk("tenerys", [Vector2(-80.5, 2.0), Vector2(-86.0, 8.0)], 3.0, ["walk"], [])
		walk("wolf", [Vector2(-66.0, -18.0), Vector2(-62.0, -26.0)], 3.0, ["walk"], []))
	at(24.0, func() -> void:
		play("danko", ["lf_civilian_stand_up", "lf_civilian_wait"], 0.25, true, 1.4)
		play("tim", ["lf_civilian_cage_wait"], 0.35))
	at(25.4, func() -> void:
		walk("danko", [CAGE + Vector2(0.7, 0.62), latch_spot], 0.9, ["lf_story_sneak"], [], 0.0, 0.0, 0.8))
	at(26.2, func() -> void:
		hide_actor("tenerys")
		hide_actor("wolf")
		face("danko", 0.0, 0.25)
		play("danko", ["lf_story_latch_reach"], 0.2))
	# Close-up: the hand on the latch (marker lift 1.6 s → cage latch_clear 0.7 s).
	cam(26.4, cage_point(Vector3(0.95, 1.2, 1.55)), 3.4)
	at(27.1, func() -> void:
		var cage: Rig = cast.cage
		cage.play(["lf_cage_unlock"], 0.0, true))
	at(27.8, func() -> void: sfx(FR_AUDIO + "fr_cage_latch.ogg", -6.0, 1.25))
	at(28.4, func() -> void:
		door_time = 0.0
		door_goal = 0.55
		door_rate = 0.35
		sfx(FR_AUDIO + "fr_gate_creak.ogg", -9.0, 0.9))
	at(29.2, func() -> void:
		play("danko", ["lf_story_squeeze"], 0.2)
		follow_root_path("danko", "lf_story_squeeze"))
	cam(29.6, cage_point(Vector3(0.8, 0.9, 2.0)), 9.5)
	at(30.9, func() -> void:
		door_goal = 0.0
		door_rate = 0.5
		play("danko", ["lf_story_sneak"], 0.2)
		walk("danko", [CAGE + Vector2(2.3, 3.0), CAGE + Vector2(3.4, 4.6), Vector2(-75.6, -8.6)], 1.3, ["lf_story_sneak"], [], NAN, 0.0, 1.0))
	at(31.4, func() -> void:
		face("tim", Vector2(CAGE.x + 1.0, CAGE.y + 3.0), 0.5)
		play("tim", ["lf_civilian_look_back", "lf_civilian_cage_wait"], 0.3))
	cam(32.0, ["danko", "orc"], 14.0)
	cam(35.4, "danko", 15.0)
	# ----- beat 3: the chase -----
	var trail: Array = trail_points("lf_site_01", "lf_mark_ruined_arch", Vector2(-75.6, -8.6), ARCH)
	var hide_spot := RUIN + Vector2(2.6, 2.6)
	at(35.4, func() -> void:
		walk("danko", trail + [ARCH + Vector2(3.6, 3.0), RUIN + Vector2(3.6, 0.2), hide_spot], 3.6, ["lf_story_run"], ["lf_story_hide"], deg_to_rad(-135.0))
		show_actor("wolf", Vector2(-79.4, -13.0), 150.0, ["stalk"])
		show_actor("tenerys", Vector2(-88.5, -3.0), 120.0, ["idle"]))
	at(36.3, func() -> void:
		play("wolf", ["alert", "idle"], 0.2)
		play("tenerys", ["alert", "idle"], 0.2)
		say("l04_ten_smell"))
	cam(38.0, ["danko", "wolf"], 26.0)
	at(37.8, func() -> void:
		var track: Array = trail_points("lf_site_01", "lf_mark_ruined_arch", Vector2(-77.5, -9.0), ARCH)
		track.append_array(trail_points("lf_mark_ruined_arch", "lf_site_02", ARCH, Vector2(-80.0, 34.0)))
		walk("wolf", track, 3.25, ["stalk", "run"], [], NAN, 0.0, 1.0)
		walk("tenerys", [Vector2(-85.0, 5.0), Vector2(-79.5, 13.5), RUIN + Vector2(-4.2, -3.6), RUIN + Vector2(-5.0, 1.5), Vector2(-82.0, 38.0)], 5.6, ["run"], []))
	cam(41.5, Vector3(-75.0, 0, 8.0), 36.0)    # the one top shot with all three
	at(42.6, func() -> void: sfx(AUDIO + "sfx/forest/howl_0.ogg", -6.0))
	cam(45.6, p3(RUIN + Vector2(0.6, 0.6)), 15.0)
	at(46.6, func() -> void: play("danko", ["lf_story_hide_hold"], 0.2, false))
	at(47.2, func() -> void: play("wolf", ["run"], 0.2))
	at(47.8, func() -> void: sfx(AUDIO + "sfx/forest/growl_2.ogg", -1.0))
	cam(50.0, p3(RUIN + Vector2(1.6, 1.6)), 13.0)
	at(51.6, func() -> void: play("danko", ["lf_story_peek"], 0.25))
	at(53.8, func() -> void:
		hide_actor("wolf")
		hide_actor("tenerys")
		walk("danko", [hide_spot + Vector2(5.0, -4.6), Vector2(-58.0, 17.0), Vector2(-51.0, 10.5)], 3.4, ["lf_story_run"], []))
	cam(55.4, "danko", 15.0, Vector3(2.0, 0, -2.0))
	fade(55.6, 0.0)
	fade(56.3, 1.0)
	# ----- beat 4: home (town hall I) -----
	var door := hall_door()
	var out := hall_out()
	var side := Vector3(out.z, 0, -out.x)
	var door2 := Vector2(door.x, door.z)
	var out2 := Vector2(out.x, out.z)
	var side2 := Vector2(side.x, side.z)
	var bench := bench_spot()
	var bench2 := Vector2(bench.x, bench.z)
	var threshold := door2 + out2 * 1.0
	var entry_dir := (threshold - Vector2(-20.0, 6.0)).normalized()
	at(56.5, func() -> void:
		present_forest(false)
		var sound := get_node_or_null("/root/Sound")
		if sound != null:
			sound.set_theme_override("city")
		hide_actor("danko")
		show_actor("bench", bench2, 0.0)
		(cast.bench as Node3D).position = p3(bench2, 0.225)
		(cast.bench as Node3D).look_at((cast.bench as Node3D).position + out, Vector3.UP)
		show_actor("hook", Vector2(lantern_hook.position.x, lantern_hook.position.z), rad_to_deg(lantern_hook.rotation.y))
		show_actor("ostap", door2 + side2 * 0.6 + out2 * 0.4, rad_to_deg(atan2(out2.x, out2.y)), ["lf_civilian_wait"])
		show_actor("vesna", door2 - side2 * 0.9 - out2 * 0.2, rad_to_deg(atan2(out2.x, out2.y)) + 20.0, ["lf_civilian_wait"])
		show_actor("mitya", door2 - side2 * 2.4 + out2 * 1.2, rad_to_deg(atan2(out2.x, out2.y)) - 30.0, ["lf_civilian_wait"])
		show_actor("danko", threshold - entry_dir * 19.0, rad_to_deg(atan2(entry_dir.x, entry_dir.y)))
		walk("danko", [threshold - entry_dir * 1.4], 3.4, ["lf_story_run"], ["lf_story_stumble"]))
	cam(56.5, p3(threshold - entry_dir * 11.0), 16.0)
	fade(56.6, 1.0)
	fade(57.3, 0.0)
	at(57.2, func() -> void: show_caption("Drenovar"))
	cam(60.6, p3(threshold + out2 * 0.6), 11.0)
	at(60.4, func() -> void:
		face("ostap", threshold - entry_dir * 2.0, 0.25)
		walk("ostap", [threshold], 2.2, ["lf_civilian_follow"], ["lf_story_catch"]))
	at(61.6, func() -> void:
		play("danko", ["lf_civilian_follow_tired"], 0.25)
		walk("danko", [bench2 + out2 * 0.05], 0.9, ["lf_civilian_follow_tired"], ["lf_story_sit_down", "lf_story_sit"], atan2(out2.x, out2.y))
		walk("vesna", [bench2 + side2 * 0.7 + out2 * 0.5], 1.2, ["lf_civilian_follow"], ["lf_story_guide_sit"], atan2(-side2.x - out2.x, -side2.y - out2.y))
		walk("mitya", [door2 - out2 * 1.5], 2.8, ["lf_story_run"], []))
	at(64.8, func() -> void:
		walk("ostap", [bench2 - side2 * 1.0 + out2 * 0.6], 1.0, ["lf_civilian_follow"], ["lf_civilian_wait"], atan2(side2.x, side2.y))
		walk("mitya", [bench2 + out2 * 1.1 - side2 * 0.25], 1.6, ["lf_story_carry_cup"], ["lf_story_offer"], atan2(-out2.x, -out2.y))
		var holder := StoryCast.attach(cast.mitya, "PropR", cup_prop)
		cup_prop.visible = holder != null)
	cam(65.0, p3(bench2 + out2 * 0.6), 7.2)
	at(66.8, func() -> void:
		play("danko", ["lf_story_show_wrist"], 0.25)
		play("mitya", ["lf_story_point_low"], 0.2)
		say("l05_mit_wrist"))
	at(69.5, func() -> void:
		if cup_prop.get_parent() != null:
			cup_prop.get_parent().remove_child(cup_prop)
		StoryCast.attach(cast.danko, "PropR", cup_prop)
		play("danko", ["lf_story_drink"], 0.3)
		play("mitya", ["lf_civilian_wait"], 0.3))
	at(70.4, func() -> void:
		play("danko", ["lf_story_talk_seated"], 0.3)
		say("l06_dan_cage"))
	at(75.9, func() -> void:
		face("mitya", Vector2((cast.ostap as Node3D).position.x, (cast.ostap as Node3D).position.z), 0.4)
		play("mitya", ["lf_story_talk"], 0.3)
		say("l07_mit_others"))
	at(78.2, func() -> void:
		face("ostap", Vector2((cast.danko as Node3D).position.x, (cast.danko as Node3D).position.z), 0.4)
		play("ostap", ["lf_story_talk"], 0.3)
		say("l08_ost_many"))
	at(79.6, func() -> void:
		play("danko", ["lf_story_talk_seated"], 0.3)
		say("l09_dan_three"))
	# Grandpa answers with a deed: the lantern from its hook.
	var hook_xz := Vector2(lantern_hook.position.x, lantern_hook.position.z)
	var under_hook := hook_xz + out2 * 0.05
	at(82.4, func() -> void:
		walk("ostap", [under_hook], 1.4, ["lf_civilian_follow"], ["lf_story_take_lantern"], atan2(out2.x, out2.y) + PI))
	cam(83.0, p3(bench2.lerp(hook_xz, 0.5)), 8.5)
	at(83.6, func() -> void:
		face("vesna", door2, 0.5)
		say("l10_ves_bread"))
	at(84.6, func() -> void:
		walk("vesna", [door2 - out2 * 0.6], 1.2, ["lf_civilian_follow"], []))
	at(87.6, func() -> void:
		hide_actor("vesna"))
	at(88.8, func() -> void:
		walk("ostap", [door2 + out2 * 2.2 - side2 * 0.6, bench2 + out2 * 1.6], 1.3, ["lf_story_walk_lantern"], ["lf_civilian_wait"], atan2(-side2.x, -side2.y))
		play("danko", ["lf_civilian_stand_up", "lf_civilian_wait"], 0.3)
		walk("mitya", [bench2 + out2 * 2.0 - side2 * 1.2], 1.6, ["lf_civilian_follow"], ["lf_civilian_wait"], atan2(-side2.x, -side2.y)))
	at(87.7, func() -> void: sfx(AUDIO + "sfx/ui/collect_0.ogg", -16.0))
	# Back to the city camera of the player: the hall in the middle, ready to be tapped.
	cam(89.0, p3(bench2 + out2 * 1.2), 10.0)
	cam(94.0, start_target, start_zoom)
	length = 95.0
	cues.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	cam_keys.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.t) < float(b.t))

## Lantern into Ostap's hand on take_lantern's `grab` marker (1.0 s): handled in on_marker.
func on_marker(rig: Node3D, clip_id: String, marker_name: String) -> void:
	if rig == cast.get("ostap") and clip_id == "lf_story_take_lantern" and marker_name == "grab":
		if lantern_prop.get_parent() != null:
			lantern_prop.get_parent().remove_child(lantern_prop)
		StoryCast.attach(cast.ostap, "PropR", lantern_prop, Transform3D(Basis.IDENTITY, Vector3(0, -0.18, 0)))
		sfx(AUDIO + "sfx/city/hammer_0.ogg", -20.0, 1.8)

func trail_points(from_id: String, to_id: String, start: Vector2, end: Vector2) -> Array:
	var out: Array = []
	if world == null:
		return [end]
	var trail: PackedVector3Array = world.trail_path(from_id, to_id)
	var best := 0
	var best_d := INF
	for i in trail.size():
		var d := Vector2(trail[i].x, trail[i].z).distance_to(start)
		if d < best_d:
			best_d = d
			best = i
	var step := 4
	var i := best + step
	while i < trail.size() - 1:
		out.append(Vector2(trail[i].x, trail[i].z))
		i += step
	out.append(end)
	return out

# ------------------------------------------------------------------ per frame

func _ready() -> void:
	set_process(true)

func _process(delta: float) -> void:
	if not running:
		return
	t += delta
	apply_frame(delta)
	if t >= length:
		finish(false)

func apply_frame(delta: float) -> void:
	while cue_index < cues.size() and float(cues[cue_index][0]) <= t:
		var action: Callable = cues[cue_index][1]
		cue_index += 1
		action.call()
	update_walkers(delta)
	update_turners()
	update_door(delta)
	update_glow(delta)
	update_camera()
	update_fade()
	if line_hide_at > 0.0 and t >= line_hide_at:
		line_hide_at = -1.0
		dialogue.hide_line()
	dialogue.tick(delta)
	for id in cast:
		var actor: Variant = cast[id]
		if actor is Rig and (actor as Rig).visible and (actor as Rig).model != null and not (actor as Rig).creature_species.is_empty():
			CreatureVisuals.update_lod((actor as Rig).model, stage.camera)

func update_walkers(delta: float) -> void:
	for id in walkers.keys():
		var state: Dictionary = walkers[id]
		var actor: Rig = cast[id]
		if state.has("track"):
			var samples: Array = state.track
			var k := (t - float(state.t0)) / 0.1
			var i := clampi(int(floor(k)), 0, samples.size() - 1)
			var a: Array = samples[i]
			var b: Array = samples[mini(i + 1, samples.size() - 1)]
			var f := clampf(k - float(i), 0.0, 1.0)
			var offset := Vector3(lerpf(float(a[0]), float(b[0]), f), lerpf(float(a[1]), float(b[1]), f),
				lerpf(float(a[2]), float(b[2]), f)).rotated(Vector3.UP, float(state.yaw))
			var start: Vector2 = state.start
			actor.position = p3(start + Vector2(offset.x, offset.z), float(state.lift) + offset.y)
			if k >= float(samples.size() - 1):
				walkers.erase(id)
			continue
		var path: Array = state.path
		var remaining: float = float(state.speed) * delta
		var position := Vector2(actor.position.x, actor.position.z)
		var heading := Vector2.ZERO
		while remaining > 0.0 and int(state.segment) < path.size() - 1:
			var goal: Vector2 = path[int(state.segment) + 1]
			var gap := goal - position
			var distance := gap.length()
			if distance <= remaining:
				position = goal
				remaining -= distance
				state.segment = int(state.segment) + 1
				if distance > 0.001:
					heading = gap / distance
			else:
				heading = gap / distance
				position += heading * remaining
				remaining = 0.0
		actor.position = p3(position, float(state.get("lift", 0.0)) + cage_lift(position))
		if heading != Vector2.ZERO and not state.get("keep_yaw", false):
			var yaw := atan2(heading.x, heading.y)
			actor.rotation.y = lerp_angle(actor.rotation.y, yaw, minf(1.0, delta * 9.0))
		if int(state.segment) >= path.size() - 1:
			walkers.erase(id)
			var end_clip: Array = state.end_clip
			if not end_clip.is_empty():
				actor.play(end_clip, 0.15, true)
			var end_yaw := float(state.end_yaw)
			if not is_nan(end_yaw):
				face(id, rad_to_deg(end_yaw), 0.35)

func update_turners() -> void:
	for id in turners.keys():
		var state: Dictionary = turners[id]
		var k := clampf((t - float(state.t0)) / maxf(float(state.seconds), 0.01), 0.0, 1.0)
		var s := k * k * (3.0 - 2.0 * k)
		(cast[id] as Node3D).rotation.y = lerpf(float(state.from), float(state.to), s)
		if k >= 1.0:
			turners.erase(id)

func update_door(delta: float) -> void:
	if door_time < 0.0:
		return
	var cage: Rig = cast.cage
	if cage.player == null:
		return
	door_time = move_toward(door_time, door_goal, door_rate * delta * 2.0)
	var clip := cage.resolve(["lf_cage_gate_open"])
	if clip.is_empty():
		return
	if cage.player.current_animation != clip:
		cage.player.play(clip, 0.0)
	cage.player.seek(door_time, true)
	cage.player.pause()

func update_glow(delta: float) -> void:
	sweep_energy = move_toward(sweep_energy, sweep_goal, delta / 0.5)
	orc_glow = move_toward(orc_glow, orc_glow_goal, delta / 0.4)
	if sweep != null:
		sweep.set_shader_parameter("energy", sweep_energy)
		sweep.set_shader_parameter("sweep", fmod(t * 0.85, 1.0))
	var orc: Rig = cast.get("orc")
	if orc != null:
		orc.set_glow(orc_glow * 2.4)

func key_point(value: Variant) -> Vector3:
	if value is Vector3:
		return value
	if value is String and cast.has(value):
		return (cast[value] as Node3D).position
	if value is Array:
		var sum := Vector3.ZERO
		for item in value:
			sum += key_point(item)
		return sum / maxf(1.0, (value as Array).size())
	return stage.target

func update_camera() -> void:
	if cam_keys.is_empty():
		return
	var index := 0
	while index < cam_keys.size() - 1 and float(cam_keys[index + 1].t) <= t:
		index += 1
	var from: Dictionary = cam_keys[index]
	var at_point := key_point(from.at) + (from.offset as Vector3)
	var zoom := float(from.zoom)
	if index < cam_keys.size() - 1 and t > float(from.t):
		var to: Dictionary = cam_keys[index + 1]
		var k := clampf((t - float(from.t)) / maxf(float(to.t) - float(from.t), 0.001), 0.0, 1.0)
		var s := k * k * k * (k * (k * 6.0 - 15.0) + 10.0)
		at_point = at_point.lerp(key_point(to.at) + (to.offset as Vector3), s)
		zoom = exp(lerpf(log(zoom), log(float(to.zoom)), s))
	set_view(at_point, zoom)

func set_view(at_point: Vector3, zoom: float) -> void:
	var ground: Vector3 = stage.ground_point(Vector3(at_point.x, 0, at_point.z))
	# A key above the ground (the latch, the door) centres that point; actors centre their feet.
	var target := Vector3(at_point.x, maxf(ground.y, at_point.y), at_point.z)
	stage.target = target
	stage.zoom = zoom
	stage.camera_target = target
	stage.camera_zoom = zoom
	stage.apply_camera_pose()
	stage.refresh_camera_visibility(false)

func update_fade() -> void:
	if fade_keys.is_empty():
		return
	var alpha := float(fade_keys[0][1])
	for i in fade_keys.size():
		var key: Array = fade_keys[i]
		if float(key[0]) <= t:
			alpha = float(key[1])
			if i + 1 < fade_keys.size():
				var next: Array = fade_keys[i + 1]
				var k := clampf((t - float(key[0])) / maxf(float(next[0]) - float(key[0]), 0.001), 0.0, 1.0)
				alpha = lerpf(float(key[1]), float(next[1]), k)
	fade_rect.color.a = alpha
	fade_rect.visible = alpha > 0.001

# ------------------------------------------------------------------ end

func skip() -> void:
	skipped = true
	finish(true)

func finish(was_skipped: bool) -> void:
	if not running:
		return
	running = false
	present_forest(false)
	var sound := get_node_or_null("/root/Sound")
	if sound != null:
		sound.set_theme_override("")
	stage.target = start_target
	stage.zoom = start_zoom
	stage.camera_target = start_target
	stage.camera_zoom = start_zoom
	stage.apply_camera_pose()
	stage.refresh_camera_visibility(true)
	if "hud" in game and game.hud != null:
		game.hud.visible = hud_was_visible
	if is_instance_valid(root):
		root.queue_free()
	finished.emit(was_skipped)
	queue_free()
