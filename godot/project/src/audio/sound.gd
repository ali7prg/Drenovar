extends Node
## DRENOVAR sound (build 1024), autoload «Sound».
## Buses (default_bus_layout.tres): Master (gentle compressor + limiter at -1 dB) → Music, SFX, UI,
## Ambient, Voice. Settings (six volumes, five mutes; the master mute is the old «Звук» switch) live in
## user://hud.cfg [settings] and are applied in _ready, before anything can play.
## - UI: every BaseButton in the tree is hooked on node_added. Requests made in one frame (the click,
##   the window it opens, a purchase…) collapse into the single most important UI sound.
## - Music: one theme per scene (city, world, forest, battle), crossfades of CROSSFADE seconds,
##   the same theme never restarts, each track resumes where it left off; the city alternates two
##   pieces. Stingers (victory, defeat, construction, reward) duck the theme. Lowered in background.
## - Ambient beds follow the scene; the forest adds rare howls and owls.
## - SFX: 2D and 3D pools with per-sound voice limits, priorities, pitch and volume variation and
##   2–6 recorded variations. 3D sounds are heard from a listener above the camera's ground target,
##   with attenuation scaled to the visible area (works for the orthographic city camera).
## Streams load on worker threads (ResourceLoader.load_threaded_request); nothing is decoded on a tap.

const Bank = preload("res://src/audio/sound_bank.gd")
const SETTINGS_PATH := "user://hud.cfg"
const BUSES := ["Master", "Music", "SFX", "UI", "Ambient", "Voice"]
const KEY_OF := {"Master": "master", "Music": "music", "SFX": "sfx", "UI": "ui", "Ambient": "ambient", "Voice": "voice"}
const DEFAULTS := {"master": 1.0, "music": 0.85, "sfx": 1.0, "ui": 0.85, "ambient": 0.8, "voice": 0.9}
## Mix trims of each bus at 100 % (the slider scales below these).
const BUS_TRIM := {"Master": 0.0, "Music": -1.0, "SFX": 0.0, "UI": -4.0, "Ambient": -3.0, "Voice": -2.0}
const CROSSFADE := 2.2
const POOL_2D := 12
const POOL_3D := 14
const UI_VOICES := 3
const UI_DEDUPE_MS := 90

const UI_PRIORITY := {"press": 1, "slider": 1, "toggle": 2, "tab": 2, "building_tap": 2, "close": 3, "open": 4,
	"puzzle_right": 5, "puzzle_wrong": 5, "speedup": 6, "train": 6, "march": 6, "build_start": 6,
	"collect": 7, "purchase": 7, "reward": 8, "error": 9}
## Base level of each sound (dB before the bus).
const LEVEL := {"ui/press": -7.0, "ui/slider": -14.0, "ui/toggle": -6.0, "ui/tab": -6.0, "ui/open": -6.0, "ui/close": -7.0,
	"ui/error": -4.0, "ui/purchase": -4.0, "ui/collect": -4.0, "ui/reward": -3.0, "ui/build_start": -4.0,
	"ui/building_tap": -7.0, "ui/march": -5.0, "ui/train": -5.0, "ui/speedup": -6.0, "ui/puzzle_right": -4.0, "ui/puzzle_wrong": -4.0,
	"city/hammer": -7.0, "city/axe": -5.0, "city/tree_fall": -2.0, "city/build_done": -3.0,
	"combat/foot": -15.0, "combat/hoof": -11.0, "combat/swing": -8.0, "combat/clash": -5.0, "combat/flesh": -6.0,
	"combat/armor": -6.0, "combat/shield": -6.0, "combat/wood": -7.0, "combat/bow": -6.0, "combat/crossbow": -6.0,
	"combat/arrow_hit": -8.0, "combat/javelin": -8.0, "combat/fall": -5.0, "combat/creature_hurt": -5.0,
	"combat/creature_roar": -2.0, "combat/creature_death": -2.0, "combat/horn": -4.0,
	"voice/war_cry": -6.0, "voice/soldier_hurt": -9.0, "voice/soldier_death": -6.0,
	"forest/horse_neigh": -6.0, "forest/horse_snort": -8.0, "forest/horse_fear": -4.0, "forest/roar": -1.0,
	"forest/growl": -4.0, "forest/fog_reveal": -9.0, "forest/howl": -12.0, "forest/owl": -13.0}
## Stealing priority (a full pool gives a voice to an equal or more important sound).
const PRIORITY := {"combat/foot": 0, "combat/hoof": 1, "city/hammer": 1, "city/axe": 1, "forest/owl": 1, "forest/howl": 1,
	"combat/swing": 2, "combat/arrow_hit": 2, "combat/bow": 2, "combat/crossbow": 2, "combat/javelin": 2, "combat/wood": 2,
	"forest/fog_reveal": 2, "forest/horse_snort": 2, "combat/clash": 3, "combat/flesh": 3, "combat/armor": 3,
	"combat/shield": 3, "voice/soldier_hurt": 3, "voice/war_cry": 4, "combat/fall": 4, "voice/soldier_death": 4,
	"forest/horse_neigh": 4, "forest/horse_fear": 5, "combat/creature_hurt": 4, "city/tree_fall": 4, "city/build_done": 5,
	"combat/horn": 5, "forest/growl": 5, "combat/creature_roar": 6, "combat/creature_death": 6, "forest/roar": 6}
## At most this many copies of one sound at once (default 3); the Voice bus has VOICE_LIMIT in total.
const LIMIT := {"combat/foot": 3, "combat/hoof": 3, "city/hammer": 2, "city/axe": 1, "city/tree_fall": 1,
	"combat/creature_roar": 1, "combat/creature_death": 1, "combat/horn": 1, "forest/roar": 1, "forest/growl": 1,
	"forest/howl": 1, "forest/owl": 1, "forest/horse_fear": 1, "forest/horse_neigh": 1, "voice/war_cry": 2,
	"voice/soldier_death": 2, "voice/soldier_hurt": 2}
const VOICE_LIMIT := 3
## Minimum seconds between two starts of one sound.
const MIN_GAP := {"combat/foot": 0.06, "combat/hoof": 0.07, "city/hammer": 0.14, "city/axe": 0.3, "combat/clash": 0.05,
	"combat/flesh": 0.05, "voice/soldier_hurt": 0.35, "voice/war_cry": 1.5, "combat/creature_roar": 2.0, "forest/roar": 2.0,
	"forest/growl": 1.2, "forest/horse_snort": 1.5, "forest/horse_neigh": 3.0, "forest/horse_fear": 2.0,
	"forest/fog_reveal": 1.5, "combat/horn": 4.0}
## Sounds that lower the music a little while they ring (dB, seconds).
const DUCK := {"combat/creature_roar": [-5.0, 1.6], "forest/roar": [-5.0, 1.8], "combat/creature_death": [-5.0, 1.4],
	"combat/horn": [-5.0, 2.0], "voice/war_cry": [-4.0, 1.2], "city/tree_fall": [-4.0, 1.4], "ui/reward": [-4.0, 0.9],
	"ui/collect": [-4.0, 0.7], "ui/purchase": [-4.0, 0.6], "ui/march": [-4.0, 1.6]}

const CITY_PLAYLIST := ["city_irelands_coast", "city_woodland_fantasy"]
const THEME_TRACK := {"world": "world_heroic_demise", "forest": "forest_mystery_forest", "battle": "battle_defying_commodus"}
const STINGERS := {"victory": -1.0, "defeat": -2.0, "construction_done": -3.0, "reward": -4.0}
## Ambient beds per scene: [file, dB].
const AMBIENCE := {"city": [["city_birds", -3.0], ["city_market", -11.0]], "world": [["world_wind", -6.0], ["city_birds", -16.0]],
	"forest": [["forest_birds", -2.0], ["world_wind", -13.0]], "": []}
const BATTLE_DIN := -9.0

signal changed(key: String)

var volume := DEFAULTS.duplicate()
var muted := {"master": false, "music": false, "sfx": false, "ui": false, "ambient": false, "voice": false}
var enabled := true

var paths := {}            # path -> true once requested
var loaded := {}           # path -> AudioStream
var last_variant := {}     # stem -> index
var last_start := {}       # stem -> seconds
var pool_2d: Array[AudioStreamPlayer] = []
var pool_3d: Array[AudioStreamPlayer3D] = []
var ui_players: Array[AudioStreamPlayer] = []
var ui_pending: Array[String] = []
var ui_flush_queued := false
var ui_last := {"kind": "", "msec": -100000, "priority": 0}
var trace: Array = []      # recent plays {kind, stem, file, bus, msec, spatial}
var counts := {}           # stem -> plays
var ui_requests := 0
var ui_plays := 0
var listener: AudioListener3D
var listener_stage: Node3D
var main_cache: Node

# music
var music_players: Array[AudioStreamPlayer] = []
var stinger_player: AudioStreamPlayer
var theme := ""
var theme_override := ""
var track := ""
var track_player: AudioStreamPlayer
var track_wanted := ""
var track_played := 0.0
var positions := {}        # track -> seconds
var city_index := 0
var fades := {}            # player -> [from, to, t, duration, stop]
var gains := {}            # player -> linear gain
var theme_history: Array = []
var battle_since := -1
var battle_last := -100000
var duck_db := 0.0
var duck_target := 0.0
var duck_until := 0.0
var background_db := 0.0
var background_target := 0.0
var poll_timer := 0.0
var theme_candidate := ""
var candidate_msec := 0
var save_timer := -1.0
var next_ambient_shot := 0.0
# ambient
var ambient_players := {}  # bed name -> player
var ambient_scene := "-"
var battle_din_on := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	load_settings()
	apply_all()
	for i in POOL_2D:
		var p := AudioStreamPlayer.new()
		p.name = "Sfx%d" % i
		p.bus = &"SFX"
		add_child(p)
		pool_2d.append(p)
	for i in UI_VOICES:
		var u := AudioStreamPlayer.new()
		u.name = "Ui%d" % i
		u.bus = &"UI"
		add_child(u)
		ui_players.append(u)
	for i in POOL_3D:
		var s := AudioStreamPlayer3D.new()
		s.name = "Spatial%d" % i
		s.bus = &"SFX"
		s.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
		s.attenuation_filter_db = -8.0
		s.attenuation_filter_cutoff_hz = 7000.0
		s.panning_strength = 0.7
		add_child(s)
		pool_3d.append(s)
	for i in 2:
		var m := AudioStreamPlayer.new()
		m.name = "Music%d" % i
		m.bus = &"Music"
		add_child(m)
		music_players.append(m)
		gains[m] = 0.0
	stinger_player = AudioStreamPlayer.new()
	stinger_player.name = "Stinger"
	stinger_player.bus = &"Music"
	add_child(stinger_player)
	get_tree().node_added.connect(_on_node_added)
	# The interface sounds first (a tap may come early), then the rest, all on worker threads.
	for stem in Bank.VARIANTS:
		if stem.begins_with("ui/"):
			for i in int(Bank.VARIANTS[stem]):
				request(variant_path(stem, i))
	request(Bank.MUSIC[CITY_PLAYLIST[0]].path)
	for stem in Bank.VARIANTS:
		if not stem.begins_with("ui/"):
			for i in int(Bank.VARIANTS[stem]):
				request(variant_path(stem, i))
	for bed in ["city_birds", "city_market"]:
		request(ambient_path(bed))
	for name in STINGERS:
		request("%sstingers/%s.ogg" % [Bank.ROOT, name])

# ------------------------------------------------------------------ settings
func load_settings() -> void:
	var file := ConfigFile.new()
	if file.load(SETTINGS_PATH) != OK:
		return
	for key in DEFAULTS:
		volume[key] = clampf(float(file.get_value("settings", "vol_" + key, DEFAULTS[key])), 0.0, 1.0)
		if key != "master":
			muted[key] = bool(file.get_value("settings", "mute_" + key, false))
	muted.master = not bool(file.get_value("settings", "sound", true))

func save_settings() -> void:
	save_timer = -1.0
	var file := ConfigFile.new()
	file.load(SETTINGS_PATH)
	for key in DEFAULTS:
		file.set_value("settings", "vol_" + key, snappedf(float(volume[key]), 0.01))
		if key != "master":
			file.set_value("settings", "mute_" + key, bool(muted[key]))
	file.set_value("settings", "sound", not bool(muted.master))
	file.save(SETTINGS_PATH)

func bus_db(bus: String) -> float:
	var v := float(volume[KEY_OF[bus]])
	var db := float(BUS_TRIM[bus]) + (linear_to_db(v * v) if v > 0.001 else -80.0)
	if bus == "Music":
		db += duck_db + background_db
	elif bus == "Ambient":
		db += background_db
	return db

func apply_bus(bus: String) -> void:
	var index := AudioServer.get_bus_index(bus)
	if index < 0:
		return
	var key: String = KEY_OF[bus]
	AudioServer.set_bus_volume_db(index, bus_db(bus))
	AudioServer.set_bus_mute(index, bool(muted[key]) or float(volume[key]) <= 0.001)

func apply_all() -> void:
	for bus in BUSES:
		apply_bus(bus)

## 0..1; the slider's square law gives a natural loudness curve (50 % ≈ -12 dB).
func set_volume(key: String, value: float, save := true) -> void:
	volume[key] = clampf(value, 0.0, 1.0)
	if value > 0.001 and bool(muted[key]) and key != "master":
		muted[key] = false
	apply_bus(bus_of(key))
	if save:
		save_timer = 0.4
	changed.emit(key)

func set_muted(key: String, on: bool, save := true) -> void:
	muted[key] = on
	apply_bus(bus_of(key))
	if save:
		save_settings()
	changed.emit(key)

func bus_of(key: String) -> String:
	for bus in KEY_OF:
		if KEY_OF[bus] == key:
			return bus
	return "Master"

func audible(key: String) -> bool:
	return not bool(muted.master) and not bool(muted[key]) and float(volume[key]) > 0.001 and float(volume.master) > 0.001

# ------------------------------------------------------------------ loading
func variant_path(stem: String, index: int) -> String:
	return "%ssfx/%s_%d.ogg" % [Bank.ROOT, stem, index]

func ambient_path(bed: String) -> String:
	return "%sambient/%s.ogg" % [Bank.ROOT, bed]

func request(path: String) -> void:
	if paths.has(path) or loaded.has(path):
		return
	paths[path] = true
	if ResourceLoader.load_threaded_request(path, "AudioStream", false) != OK:
		push_warning("Sound: cannot load " + path)

## The stream if it is ready; never blocks the frame (a sound that is still loading is skipped).
func stream(path: String) -> AudioStream:
	if loaded.has(path):
		return loaded[path]
	if not paths.has(path):
		request(path)
		return null
	var status := ResourceLoader.load_threaded_get_status(path)
	if status == ResourceLoader.THREAD_LOAD_LOADED:
		var value := ResourceLoader.load_threaded_get(path) as AudioStream
		loaded[path] = value
		paths.erase(path)
		return value
	if status == ResourceLoader.THREAD_LOAD_FAILED or status == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
		paths.erase(path)
		loaded[path] = null
	return null

## The stream now, waiting for its worker load if needed (combat cues right after launch, stingers).
func stream_now(path: String) -> AudioStream:
	var value := stream(path)
	if value != null or loaded.has(path):
		return value
	if paths.has(path):
		value = ResourceLoader.load_threaded_get(path) as AudioStream
		paths.erase(path)
	else:
		value = load(path) as AudioStream
	loaded[path] = value
	return value

## QA and the settings preview: wait until every queued stream is in.
func finish_loading() -> void:
	for path in paths.keys():
		loaded[path] = ResourceLoader.load_threaded_get(path) as AudioStream
	paths.clear()

func release(path: String) -> void:
	loaded.erase(path)
	paths.erase(path)

# ------------------------------------------------------------------ UI
func _on_node_added(node: Node) -> void:
	if node is BaseButton:
		var button := node as BaseButton
		if not button.pressed.is_connected(_on_button_pressed):
			button.pressed.connect(_on_button_pressed.bind(button))

func _on_button_pressed(button: BaseButton) -> void:
	if not is_instance_valid(button):
		return
	var kind := String(button.get_meta("sfx", ""))
	if kind == "none":
		return
	if kind.is_empty():
		kind = "toggle" if button.toggle_mode or button is CheckBox or button is CheckButton else "press"
	ui(kind)

## One interface sound per gesture: requests in the same frame (and a repeat of an equal or
## weaker sound within UI_DEDUPE_MS) collapse into the most important one.
func ui(kind: String) -> void:
	ui_requests += 1
	ui_pending.append(kind)
	if not ui_flush_queued:
		ui_flush_queued = true
		_flush_ui.call_deferred()

func _flush_ui() -> void:
	ui_flush_queued = false
	var best := ""
	for kind in ui_pending:
		if best.is_empty() or int(UI_PRIORITY.get(kind, 1)) > int(UI_PRIORITY.get(best, 1)):
			best = kind
	ui_pending.clear()
	if best.is_empty():
		return
	var now := Time.get_ticks_msec()
	var priority := int(UI_PRIORITY.get(best, 1))
	if now - int(ui_last.msec) < UI_DEDUPE_MS and priority <= int(ui_last.priority):
		return
	ui_last = {"kind": best, "msec": now, "priority": priority}
	ui_plays += 1
	var stem := "ui/" + best
	var player: AudioStreamPlayer = null
	for p in ui_players:
		if not p.playing:
			player = p
			break
	if player == null:
		player = ui_players[0]
		for p in ui_players:
			if p.get_playback_position() > player.get_playback_position():
				player = p
	start(player, stem, 0.0, 1.0, 0.025, "UI")
	if DUCK.has(stem):
		duck(DUCK[stem][0], DUCK[stem][1])

# ------------------------------------------------------------------ SFX
func pick(stem: String) -> String:
	var count := int(Bank.VARIANTS.get(stem, 0))
	if count <= 0:
		return ""
	var index := randi() % count
	if count > 1 and index == int(last_variant.get(stem, -1)):
		index = (index + 1 + randi() % (count - 1)) % count
	last_variant[stem] = index
	return variant_path(stem, index)

## Plays a sound effect. `at` = a Vector3 world position for a spatial sound, null for 2D.
## Returns false when it was limited, still loading or the bus is silent.
func sfx(stem: String, at: Variant = null, gain_db := 0.0, pitch := 1.0) -> bool:
	if not enabled or not Bank.VARIANTS.has(stem):
		return false
	var bus := "Voice" if stem.begins_with("voice/") else ("UI" if stem.begins_with("ui/") else "SFX")
	if not audible(KEY_OF[bus]):
		return false
	var now := Time.get_ticks_msec() / 1000.0
	if now - float(last_start.get(stem, -100.0)) < float(MIN_GAP.get(stem, 0.03)):
		return false
	var spatial := at is Vector3
	var limit := int(LIMIT.get(stem, 3))
	var same := 0
	var voices := 0
	var pool: Array = pool_3d if spatial else pool_2d
	for p in pool_2d + pool_3d:
		if p.playing:
			if String(p.get_meta("stem", "")) == stem:
				same += 1
			if String(p.bus) == "Voice":
				voices += 1
	if same >= limit or (bus == "Voice" and voices >= VOICE_LIMIT):
		return false
	var priority := int(PRIORITY.get(stem, 2))
	var chosen: Node = null
	for p in pool:
		if not p.playing:
			chosen = p
			break
	if chosen == null:
		var weakest: Node = null
		for p in pool:
			var pp := int(PRIORITY.get(String(p.get_meta("stem", "")), 2))
			if pp <= priority and (weakest == null or pp < int(PRIORITY.get(String(weakest.get_meta("stem", "")), 2))):
				weakest = p
		chosen = weakest
	if chosen == null:
		return false
	if spatial:
		var s := chosen as AudioStreamPlayer3D
		var extent := view_extent()
		s.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
		s.unit_size = extent * 0.55
		s.max_distance = extent * 3.2
		s.global_position = at
	if not start(chosen, stem, gain_db, pitch, 0.04, bus):
		return false
	last_start[stem] = now
	if DUCK.has(stem):
		duck(DUCK[stem][0], DUCK[stem][1])
	return true

func start(player: Node, stem: String, gain_db: float, pitch: float, spread: float, bus: String) -> bool:
	var path := pick(stem)
	var value := stream(path) if not path.is_empty() else null
	if value == null:
		return false
	player.stop()
	player.stream = value
	player.bus = StringName(bus)
	var level := float(LEVEL.get(stem, -6.0)) + gain_db + randf_range(-1.2, 1.2)
	player.volume_db = level
	player.pitch_scale = pitch * (1.0 + randf_range(-spread, spread))
	player.set_meta("stem", stem)
	player.play()
	counts[stem] = int(counts.get(stem, 0)) + 1
	trace.append({"stem": stem, "file": path, "bus": bus, "msec": Time.get_ticks_msec(), "spatial": player is AudioStreamPlayer3D})
	if trace.size() > 256:
		trace.pop_front()
	return true

func stop_all_sfx() -> void:
	for p in pool_2d + pool_3d + ui_players:
		p.stop()

# ------------------------------------------------------------------ listener (3D)
## The game scene (main.tscn): the current scene, or (QA scripts) the root child that shows scenes.
func main_node() -> Node:
	var main := get_tree().current_scene
	if main != null and main.has_method("show_scene"):
		return main
	if is_instance_valid(main_cache) and main_cache.is_inside_tree():
		return main_cache
	for child in get_tree().root.get_children():
		if child.has_method("show_scene") and child.get("stage") != null:
			main_cache = child
			return child
	return null

func current_stage() -> Node3D:
	var main := main_node()
	if main == null:
		return null
	var stage: Variant = main.get("stage")
	return stage if stage is Node3D and is_instance_valid(stage) and (stage as Node3D).is_inside_tree() else null

func view_extent() -> float:
	var stage := current_stage()
	if stage == null:
		return 60.0
	var camera: Camera3D = stage.get("camera")
	if camera == null:
		return 60.0
	if camera.projection == Camera3D.PROJECTION_ORTHOGONAL:
		return maxf(camera.size, 4.0)
	var target: Vector3 = stage.get("camera_target")
	var distance := camera.global_position.distance_to(target)
	return maxf(2.0 * distance * tan(deg_to_rad(camera.fov) * 0.5), 4.0)

func update_listener() -> void:
	var stage := current_stage()
	if stage == null:
		return
	if listener_stage != stage or not is_instance_valid(listener):
		if is_instance_valid(listener):
			listener.queue_free()
		listener = AudioListener3D.new()
		listener.name = "SoundListener"
		stage.add_child(listener)
		listener_stage = stage
	var camera: Camera3D = stage.get("camera")
	if camera == null or not camera.is_inside_tree():
		return
	var target: Vector3 = stage.get("camera_target")
	var toward := camera.global_position - target
	toward = toward.normalized() if toward.length_squared() > 0.001 else Vector3.UP
	listener.global_transform = Transform3D(camera.global_basis, target + toward * view_extent() * 0.55)
	if not listener.is_current():
		listener.make_current()

# ------------------------------------------------------------------ music
func set_theme_override(value: String) -> void:
	theme_override = value
	poll_timer = 0.0

func wanted_theme() -> String:
	if not theme_override.is_empty():
		return theme_override
	var main := main_node()
	if main == null or main.get("stage") == null:
		return ""
	var now := Time.get_ticks_msec()
	var game: Variant = main.get("forest_game")
	var mood := ""
	if game is Node and is_instance_valid(game) and (game as Node).has_method("music_mood"):
		mood = String(game.music_mood())
	var stage := current_stage()
	var fighting := mood == "battle"
	if stage != null:
		var fx: Variant = stage.get("battle_fx")
		if fx != null and int(fx.get("last_battle_msec")) >= 0 and now - int(fx.get("last_battle_msec")) < 1200:
			fighting = true
	if fighting:
		battle_last = now
		if battle_since < 0:
			battle_since = now
	elif now - battle_last > 7000:
		battle_since = -1
	if battle_since >= 0 and now - battle_since >= 600:
		return "battle"
	if not mood.is_empty() and mood != "battle":
		return mood
	if theme == "battle" and battle_since >= 0:
		return "battle"
	if stage == null:
		return theme if not theme.is_empty() else "city"
	return "world" if String(stage.get("map_name")) == "world" else "city"

func track_for(name: String) -> String:
	if name == "city":
		return CITY_PLAYLIST[city_index % CITY_PLAYLIST.size()]
	return String(THEME_TRACK.get(name, ""))

func set_theme(name: String) -> void:
	if name == theme:
		return
	theme = name
	theme_history.append({"theme": name, "msec": Time.get_ticks_msec()})
	if theme_history.size() > 32:
		theme_history.pop_front()
	play_track(track_for(name))
	update_ambience()

func play_track(name: String) -> void:
	if name == track and is_instance_valid(track_player) and track_player.playing:
		track_wanted = ""
		return
	track_wanted = name
	if not name.is_empty():
		request(Bank.MUSIC[name].path)

func _start_wanted_track() -> void:
	if track_wanted.is_empty():
		return
	var info: Dictionary = Bank.MUSIC[track_wanted]
	var value := stream(info.path)
	if value == null:
		return
	if value is AudioStreamOggVorbis:
		value.loop = true
		value.loop_offset = float(info.loop_offset)
	var previous := track_player
	if is_instance_valid(previous) and previous.playing:
		# After a full play (the city's rotation) the piece starts from the top next time.
		positions[track] = 0.0 if track_played > float(Bank.MUSIC[track].duration) else previous.get_playback_position()
		fade(previous, 0.0, CROSSFADE, true)
	var next: AudioStreamPlayer = music_players[0] if previous != music_players[0] else music_players[1]
	next.stop()
	next.stream = value
	gains[next] = 0.0
	next.volume_db = -80.0
	var from := float(positions.get(track_wanted, 0.0))
	if from >= float(info.duration) - 1.0:
		from = float(info.loop_offset)
	next.play(from)
	fade(next, 1.0, CROSSFADE if is_instance_valid(previous) and previous.playing else 2.8, false)
	track_player = next
	track = track_wanted
	track_wanted = ""
	track_played = 0.0
	# Keep at most three music streams in memory (the current, the fading one, one recent).
	var keep := []
	for p in music_players:
		if p.stream != null:
			keep.append(p.stream.resource_path)
	var music_loaded := []
	for path in loaded.keys():
		if String(path).contains("/music/") and not keep.has(path):
			music_loaded.append(path)
	while music_loaded.size() > 1:
		release(music_loaded.pop_front())

func fade(player: AudioStreamPlayer, to: float, duration: float, stop_after: bool) -> void:
	fades[player] = [float(gains.get(player, 0.0)), to, 0.0, maxf(duration, 0.01), stop_after]

func stinger(name: String) -> void:
	if not STINGERS.has(name) or not audible("music"):
		return
	var path := "%sstingers/%s.ogg" % [Bank.ROOT, name]
	var value := stream_now(path)
	if value == null:
		return
	stinger_player.stop()
	stinger_player.stream = value
	stinger_player.volume_db = float(STINGERS[name])
	stinger_player.play()
	duck(-9.0, maxf(value.get_length() - 1.0, 1.0))
	counts["stinger/" + name] = int(counts.get("stinger/" + name, 0)) + 1
	trace.append({"stem": "stinger/" + name, "file": value.resource_path, "bus": "Music", "msec": Time.get_ticks_msec(), "spatial": false})

func duck(db: float, hold: float) -> void:
	duck_target = minf(duck_target, db)
	duck_until = maxf(duck_until, Time.get_ticks_msec() / 1000.0 + hold)

# ------------------------------------------------------------------ ambience
func update_ambience() -> void:
	var scene := theme
	if scene == "battle":
		scene = ambient_scene if ambient_scene in ["city", "world", "forest"] else "city"
	var stage := current_stage()
	if theme == "battle" and stage != null and String(stage.get("map_name")) == "world":
		scene = "world"
	var wanted := {}
	for bed in AMBIENCE.get(scene, []):
		wanted[bed[0]] = float(bed[1])
	battle_din_on = theme == "battle"
	if battle_din_on:
		wanted["battle_din"] = BATTLE_DIN
	ambient_scene = scene
	for bed in wanted:
		request(ambient_path(bed))
	for bed in ambient_players.keys():
		if not wanted.has(bed):
			fade(ambient_players[bed], 0.0, 2.5, true)
	set_meta("ambient_wanted", wanted)

func _tick_ambience() -> void:
	var wanted: Dictionary = get_meta("ambient_wanted", {})
	for bed in wanted:
		var player: AudioStreamPlayer = ambient_players.get(bed)
		if player != null and player.playing and fades.has(player) and float(fades[player][1]) > 0.0:
			continue
		if player != null and player.playing and not fades.has(player):
			continue
		var value := stream(ambient_path(bed))
		if value == null:
			continue
		if value is AudioStreamOggVorbis:
			value.loop = true
		if player == null:
			player = AudioStreamPlayer.new()
			player.name = "Ambient_" + bed
			player.bus = &"Ambient"
			add_child(player)
			ambient_players[bed] = player
			gains[player] = 0.0
		player.set_meta("bed_db", float(wanted[bed]))
		if not player.playing:
			player.stream = value
			player.play(randf() * maxf(value.get_length() - 2.0, 0.0))
		fade(player, 1.0, 2.5, false)

# ------------------------------------------------------------------ frame
func _process(delta: float) -> void:
	if save_timer >= 0.0:
		save_timer -= delta
		if save_timer < 0.0:
			save_settings()
	poll_timer -= delta
	if poll_timer <= 0.0:
		poll_timer = 0.25
		var wanted := wanted_theme()
		# A theme must be wanted for a moment before it takes over (no flapping at the forest edge);
		# the first theme and the battle start at once.
		if wanted.is_empty() or wanted == theme or background_target < 0.0:
			# (In the background the forest layer forgets its mood: keep the theme until return.)
			theme_candidate = ""
		elif theme.is_empty() or wanted == "battle" or not theme_override.is_empty():
			set_theme(wanted)
		elif wanted != theme_candidate:
			theme_candidate = wanted
			candidate_msec = Time.get_ticks_msec()
		elif Time.get_ticks_msec() - candidate_msec >= 900:
			theme_candidate = ""
			set_theme(wanted)
		if theme == "city" and is_instance_valid(track_player) and track_player.playing:
			# The city alternates its two pieces after one full play.
			if track_played > float(Bank.MUSIC[track].duration) and track_wanted.is_empty():
				city_index += 1
				play_track(track_for("city"))
		_tick_ambience()
		if theme == "forest" and Time.get_ticks_msec() / 1000.0 > next_ambient_shot:
			if next_ambient_shot > 0.0:
				sfx("forest/howl" if randf() < 0.55 else "forest/owl", null, randf_range(-3.0, 0.0))
			next_ambient_shot = Time.get_ticks_msec() / 1000.0 + randf_range(28.0, 65.0)
	if not track_wanted.is_empty():
		_start_wanted_track()
	if is_instance_valid(track_player) and track_player.playing:
		track_played += delta
	for player in fades.keys():
		var f: Array = fades[player]
		f[2] = float(f[2]) + delta
		var x := clampf(float(f[2]) / float(f[3]), 0.0, 1.0)
		var g := lerpf(float(f[0]), float(f[1]), sin(x * PI * 0.5)) if float(f[1]) > float(f[0]) else lerpf(float(f[0]), float(f[1]), 1.0 - cos(x * PI * 0.5))
		gains[player] = g
		var trim := float(player.get_meta("bed_db", 0.0))
		player.volume_db = linear_to_db(maxf(g, 0.00001)) + trim
		if x >= 1.0:
			fades.erase(player)
			if bool(f[4]) and g <= 0.001:
				player.stop()
	# Duck: fast down, slow back.
	var now := Time.get_ticks_msec() / 1000.0
	if now > duck_until:
		duck_target = 0.0
	var previous_duck := duck_db
	duck_db = move_toward(duck_db, duck_target, delta * (60.0 if duck_target < duck_db else 7.0))
	var previous_bg := background_db
	background_db = move_toward(background_db, background_target, delta * (30.0 if background_target < background_db else 12.0))
	if previous_duck != duck_db or previous_bg != background_db:
		apply_bus("Music")
		apply_bus("Ambient")
	update_listener()

func _exit_tree() -> void:
	# Let worker loads finish and drop every stream (no resource alive at exit).
	finish_loading()
	for p in pool_2d + pool_3d + ui_players + music_players + ambient_players.values() + [stinger_player]:
		p.stop()
		p.stream = null
	loaded.clear()
	if save_timer >= 0.0:
		save_settings()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		# Desktop / split view: keep playing, lower.
		background_target = -14.0
	elif what == NOTIFICATION_APPLICATION_PAUSED:
		background_target = -14.0
		background_db = -14.0
		for p in music_players + ambient_players.values() + [stinger_player]:
			p.stream_paused = true
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN or what == NOTIFICATION_APPLICATION_RESUMED:
		for p in music_players + ambient_players.values() + [stinger_player]:
			p.stream_paused = false
		background_target = 0.0

# ------------------------------------------------------------------ game events
## Sound of a server order: at the tap for instant orders, on success for the others.
static func order_cue(order: Dictionary) -> String:
	var kind := String(order.get("kind", ""))
	var action := String(order.get("action", ""))
	match kind:
		"v6":
			var intent: Variant = order.get("intent", {})
			var what := String(intent.get("kind", "")) if intent is Dictionary else ""
			match what:
				"construction", "move", "research":
					return "build_start"
				"train", "siege", "heal":
					return "train"
				"speedup":
					return "speedup"
				"dismiss", "cancel":
					return ""
			return ""
		"kingdom", "legacyBuilding", "construction", "building", "plot", "wall", "settlement", "research":
			if action == "collect":
				return "collect"
			if action in ["upgrade", "build", "place", "level", "site", "area", "clear"] or kind != "kingdom":
				return "build_start"
			return ""
		"resource":
			return "build_start" if action in ["site", "area", "clear"] else ""
		"train", "heal":
			return "train"
		"speedup":
			return "speedup"
		"trade":
			return "purchase"
		"v6collect":
			return "collect"
		"starter71":
			return "reward"
		"deploy", "worldMarch", "march", "siege", "encounter", "army":
			return "march"
	return ""

func order_sent(order: Dictionary) -> void:
	var cue := order_cue(order)
	if not cue.is_empty():
		ui(cue)
		if cue == "march":
			sfx("combat/horn", null, -6.0)

func order_failed() -> void:
	ui("error")

## Debug and QA summary.
func snapshot() -> Dictionary:
	var buses := {}
	for bus in BUSES:
		var index := AudioServer.get_bus_index(bus)
		buses[bus] = {"index": index, "db": snappedf(AudioServer.get_bus_volume_db(index), 0.1) if index >= 0 else null,
			"mute": AudioServer.is_bus_mute(index) if index >= 0 else null}
	return {"theme": theme, "track": track, "buses": buses, "volume": volume.duplicate(), "muted": muted.duplicate(),
		"ui_requests": ui_requests, "ui_plays": ui_plays, "loaded": loaded.size(), "loading": paths.size()}
