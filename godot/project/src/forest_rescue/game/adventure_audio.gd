extends Node
## Adventure sound (docs/AUDIO_RU.md): at most 4 simultaneous voices including the wind loop,
## priority stealing with a short fade, hoof only on animation contact markers, wind only over
## the forest (300 ms fades), nothing in background, respects the game's master bus mute and
## the adventure sound setting. Streams are OGG conversions of the delivered cues.

const DIR := "res://assets/forest_rescue/audio/"
const VOICES := 4
const LEVELS := {"fr_forest_wind":-9.0, "fr_distant_rumble":-8.0, "fr_horse_hoof":-10.0, "fr_artifact_discovery":-8.0,
	"fr_cage_latch":-8.0, "fr_gate_creak":-8.0, "fr_people_rescued":-8.0, "fr_large_reward":-7.0}
const PRIORITY := {"fr_large_reward":5, "fr_people_rescued":5, "fr_cage_latch":4, "fr_gate_creak":4,
	"fr_artifact_discovery":3, "fr_horse_hoof":2, "fr_distant_rumble":2, "fr_forest_wind":1}

var game: Node
var players: Array[AudioStreamPlayer] = []
var streams: Dictionary = {}
var cooldowns: Dictionary = {}
var wind_on := false
var hoof_index := 0
var played: Array[String] = []

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "ForestAudio"
	for i in VOICES:
		var player := AudioStreamPlayer.new()
		player.name = "Voice%d" % i
		player.set_meta("cue", "")
		add_child(player)
		players.append(player)
	# Decode ahead of time (never inside a tap or contact callback).
	for id in LEVELS:
		stream(id)

func stream(id: String) -> AudioStream:
	if streams.has(id):
		return streams[id]
	var path := DIR + id + ".ogg"
	var value: AudioStream = null
	if ResourceLoader.exists(path):
		value = load(path)
		if id == "fr_forest_wind" and value is AudioStreamOggVorbis:
			value = value.duplicate()
			value.loop = true
	else:
		push_warning("Forest rescue audio missing: " + path)
	streams[id] = value
	return value

func allowed() -> bool:
	return game.sound_enabled and game.foreground and not AudioServer.is_bus_mute(0)

func voice_for(priority: int) -> AudioStreamPlayer:
	for player in players:
		if not player.playing:
			return player
	var lowest: AudioStreamPlayer = null
	for player in players:
		var p := int(PRIORITY.get(String(player.get_meta("cue", "")), 0))
		if p < priority and (lowest == null or p < int(PRIORITY.get(String(lowest.get_meta("cue", "")), 0))):
			lowest = player
	if lowest != null:
		var tween := create_tween()
		tween.tween_property(lowest, "volume_db", -60.0, 0.03)
		tween.tween_callback(lowest.stop)
		return null
	return null

func play_cue(id: String, cooldown := 0.0, rate := 1.0) -> void:
	if not allowed():
		return
	var now := Time.get_ticks_msec() / 1000.0
	if cooldown > 0.0 and now < float(cooldowns.get(id, -INF)):
		return
	var value := stream(id)
	if value == null:
		return
	var player := voice_for(int(PRIORITY.get(id, 1)))
	if player == null:
		# A lower priority voice is fading out; take it on the next frame.
		await get_tree().process_frame
		player = voice_for(int(PRIORITY.get(id, 1)))
		if player == null:
			return
	cooldowns[id] = now + cooldown
	player.stream = value
	player.volume_db = float(LEVELS.get(id, -8.0))
	player.pitch_scale = rate
	player.set_meta("cue", id)
	player.play()
	played.append(id)
	if played.size() > 64:
		played.pop_front()

func hoof(_position: Vector3) -> void:
	hoof_index += 1
	# Deterministic small variation (0.95–1.05), no random per-frame timer.
	var rate := 0.95 + 0.1 * float((hoof_index * 7) % 11) / 10.0
	for player in players:
		if player.playing and int(PRIORITY.get(String(player.get_meta("cue", "")), 0)) > 2:
			return
	play_cue("fr_horse_hoof", 0.12, rate)

func set_forest_ambience(on: bool) -> void:
	var wanted := on and allowed()
	if wanted == wind_on:
		return
	wind_on = wanted
	var wind: AudioStreamPlayer = null
	for player in players:
		if String(player.get_meta("cue", "")) == "fr_forest_wind" and player.playing:
			wind = player
	if wanted and wind == null:
		var value := stream("fr_forest_wind")
		if value == null:
			return
		wind = voice_for(1)
		if wind == null:
			return
		wind.stream = value
		wind.set_meta("cue", "fr_forest_wind")
		wind.volume_db = -60.0
		wind.play()
		create_tween().tween_property(wind, "volume_db", float(LEVELS.fr_forest_wind), 0.3)
	elif not wanted and wind != null:
		var tween := create_tween()
		tween.tween_property(wind, "volume_db", -60.0, 0.3)
		tween.tween_callback(wind.stop)

func on_background() -> void:
	wind_on = false
	for player in players:
		player.stop()

func apply_settings() -> void:
	if not allowed():
		on_background()
