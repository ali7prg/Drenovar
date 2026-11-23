extends Node
## Adventure sound (docs/AUDIO_RU.md): at most 4 simultaneous voices including the wind loop,
## priority stealing with a short fade, hoof only on animation contact markers, wind only over
## the forest (300 ms fades), nothing in background, respects the game's master bus mute and
## the adventure sound setting. Streams are OGG conversions of the delivered cues.
## Build 1024: the cues play on the SFX bus and the game's sound hub (autoload Sound) adds the
## recorded layer: hooves, the horse's snorts, neighs and fear, Teneris' roar and growl, the fight's
## blade, shield and body hits, deaths, the reward stinger, the fog's swish, the puzzle's right and
## wrong, and one interface sound for every adventure button (button_pressed). The forest's wind and
## birds are the hub's forest ambience (and its music theme) while wind_on is true.

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
var last_hoof_msec := -100000
var fight_count := 0

func hub() -> Node:
	return get_node_or_null("/root/Sound")

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "ForestAudio"
	for i in VOICES:
		var player := AudioStreamPlayer.new()
		player.name = "Voice%d" % i
		player.set_meta("cue", "")
		player.bus = &"SFX"
		add_child(player)
		players.append(player)
	# Decode ahead of time (never inside a tap or contact callback).
	for id in LEVELS:
		if id != "fr_forest_wind" and id != "fr_horse_hoof":
			stream(id)
	game.horse_feared.connect(func(_site: String): recorded("forest/horse_fear"))
	game.creature_roared.connect(on_roar)
	game.fight_hit.connect(on_fight_hit)
	game.cage_opened.connect(func(_site: String): recorded("ui/reward", -4.0))
	game.button_pressed.connect(func(_action: String):
		var sound := hub()
		if sound != null:
			sound.ui("press"))

## A recorded sound through the hub (2D: the camera follows the adventure).
func recorded(stem: String, gain_db := 0.0) -> void:
	var sound := hub()
	if sound != null and allowed():
		sound.sfx(stem, null, gain_db)

func on_roar(site_id: String, species: String) -> void:
	# The boss and a guardian in its lair roar; in a fight the attack's warning is a growl.
	var fight: Dictionary = game.client.battle()
	var fighting := not fight.is_empty() and String(fight.get("siteId", "")) == site_id and String(fight.get("outcome", "pending")) == "pending"
	recorded("forest/growl" if fighting and species != "ancient_maw" else "forest/roar")

func on_fight_hit(_site_id: String, attacker: String, target: String) -> void:
	fight_count += 1
	match attacker:
		"squad":
			recorded("combat/clash" if fight_count % 3 != 0 else "combat/flesh", -2.0)
			if fight_count % 3 == 1:
				recorded("combat/creature_hurt", -3.0)
		"guardian":
			recorded("combat/shield" if fight_count % 2 == 0 else "combat/flesh", -2.0)
			if fight_count % 3 == 0:
				recorded("voice/soldier_hurt", -2.0)
		"death":
			if target == "guardian":
				recorded("combat/creature_death")
			else:
				recorded("voice/soldier_death")
			recorded("combat/fall", -2.0)

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
	var sound := hub()
	if sound != null:
		match id:
			"fr_large_reward":
				sound.stinger("reward")
				sound.sfx("ui/reward", null, -2.0)
			"fr_people_rescued":
				sound.stinger("reward")
				sound.sfx("forest/horse_neigh", null, -4.0)
			"fr_artifact_discovery":
				sound.sfx("ui/reward", null, -5.0)
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
	if not allowed():
		return
	var now := Time.get_ticks_msec()
	var sound := hub()
	if sound == null:
		return
	# The recorded gallop (combat/hoof); the horse snorts when it sets off, now and then neighs.
	if now - last_hoof_msec > 2500:
		sound.sfx("forest/horse_neigh" if hoof_index % 5 == 0 else "forest/horse_snort", null, -3.0)
	last_hoof_msec = now
	sound.sfx("combat/hoof", null, -1.0)

func set_forest_ambience(on: bool) -> void:
	var wanted := on and allowed()
	if wanted == wind_on:
		return
	wind_on = wanted
	if hub() != null:
		# The hub plays the forest's recorded wind and birds (Sound.AMBIENCE.forest).
		return
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
