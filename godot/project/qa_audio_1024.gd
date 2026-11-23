extends SceneTree
## Build 1024, stage 4: sound and music. Headless checks of the Sound hub (src/audio/sound.gd) in the real
## game scene (main.tscn) against the LOCAL V6 harness with the forest adventure on (never production):
##   godot --headless --path godot/project -s qa_audio_1024.gd -- --server=http://127.0.0.1:8801 \
##     [--report=/abs/report.json] [--shots=/abs/dir [--window-only]] [--record=/abs/dir]
## Without --server only the offline checks run (buses, files, licences, loudness table, settings).
## --shots (rendered run): saves the «Звук и музыка» window. --record (rendered run with an audio
## driver): records about 30 s of each scene's soundscape from the Master bus (AudioEffectRecord).
##
## Checks:
##  1 buses Master/Music/SFX/UI/Ambient/Voice exist and send to Master; Master has the compressor and a
##    limiter at <= -1 dB; iOS session category Ambient (0) mixing with other apps
##  2 every sound of the bank, music, stinger and ambience exists and loads; music and beds loop at
##    the bank's loop points; every file in assets/audio is in CREDITS.md with an allowed licence only
##  3 loudness (runtime-audit-1024/audio/loudness.tsv, made offline by tools/audio/loudness_report.py):
##    one row per file on disk with the same size, music -16 ±1 LUFS, true peak <= -1 dBTP, SFX lead
##    <= 10 ms, total <= 25 MB
##  4 settings: the six sliders and five switches of the window change the bus volumes and mutes and the
##    values survive a restart (a fresh hub reads user://hud.cfg and applies the same bus levels)
##  5 buttons: every press of a sampled button (menu, sound window, credits, HUD, forest HUD) gives
##    exactly one interface sound
##  6 music: city → world → city → forest → battle each get their theme, crossfade (both players
##    playing in between, the old one stopped after it), the same theme does not restart and a theme
##    resumes where it was left
##  7 events: combat markers (bow, crossbow, arrow, blades, shield, armour, deaths), the fight's roar
##    and war cry, construction finished, orders (purchase, collect, march, error), stingers and the
##    forest signals (horse fear, roar, fight hits, cage, buttons, hooves, fog) each play their sound
##  8 voice limits: a burst of 400 combat sounds keeps every sound within its limit, the Voice bus
##    within VOICE_LIMIT and the pools bounded; CPU per frame of the hub is measured

const ALLOWED := ["CC0 1.0", "CC-BY 3.0", "CC-BY 4.0"]
const BUSES := ["Master", "Music", "SFX", "UI", "Ambient", "Voice"]
const SKIP_TEXT := ["Выйти", "Удалить", "Сменить", "Переселить", "Сбросить", "Отвязать", "Забыть", "Перенести", "Новое поселение", "Код"]
const SKIP_NAMES := ["Tile_map", "Tile_town", "Tile_globe", "Tile_rotate", "Tile_aim", "Tile_zoom_in", "Tile_zoom_out", "Tile_key", "Tile_tree"]

var checks := 0
var failures: Array[String] = []
var report := {}
var server := ""
var report_path := ""
var shots := ""
var record := ""
var window_only := false
var game: Node
var sound: Node

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func frames(n: int) -> void:
	for i in n:
		await process_frame

func wait(seconds: float) -> void:
	await create_timer(seconds).timeout

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			server = arg.trim_prefix("--server=")
		elif arg.begins_with("--report="):
			report_path = arg.trim_prefix("--report=")
		elif arg.begins_with("--shots="):
			shots = arg.trim_prefix("--shots=")
		elif arg.begins_with("--record="):
			record = arg.trim_prefix("--record=")
		elif arg == "--window-only":
			window_only = true
	call_deferred("run")

func run() -> void:
	sound = root.get_node_or_null("Sound")
	check(sound != null, "Sound autoload present")
	if sound == null:
		finish()
		return
	buses_check()
	files_check()
	loudness_check()
	await settings_check()
	if server.is_empty():
		report.note = "no --server: game checks skipped"
		finish()
		return
	await boot()
	if game == null:
		finish()
		return
	await window_check()
	if window_only:
		finish()
		return
	await music_check()
	await unlock_forest()
	await buttons_check()
	await forest_mood_check()
	await events_check()
	await burst_check()
	if not record.is_empty():
		await record_soundscapes()
	finish()

# ------------------------------------------------------------------ 1 buses
func buses_check() -> void:
	var found := {}
	for bus in BUSES:
		var index := AudioServer.get_bus_index(bus)
		check(index >= 0, "bus %s exists" % bus)
		if index > 0:
			check(AudioServer.get_bus_send(index) == &"Master", "bus %s sends to Master" % bus)
		found[bus] = index
	var effects := []
	var ceiling := 0.0
	for e in AudioServer.get_bus_effect_count(0):
		var effect := AudioServer.get_bus_effect(0, e)
		effects.append(effect.get_class())
		if effect is AudioEffectHardLimiter:
			ceiling = (effect as AudioEffectHardLimiter).ceiling_db
	check("AudioEffectCompressor" in effects, "Master has a compressor")
	check("AudioEffectHardLimiter" in effects and ceiling <= -1.0, "Master limiter at <= -1 dB")
	var category := int(ProjectSettings.get_setting("audio/general/ios/session_category", -1))
	check(category == 0, "iOS session category Ambient (honours the silent switch)")
	check(bool(ProjectSettings.get_setting("audio/general/ios/mix_with_others", false)), "iOS mixes with other apps")
	report.buses = {"found": found, "master_effects": effects, "limiter_ceiling_db": ceiling, "ios_session_category": category}

# ------------------------------------------------------------------ 2 files and licences
func all_files() -> Array:
	var out := []
	var stack := ["res://assets/audio"]
	while not stack.is_empty():
		var dir_path: String = stack.pop_back()
		var dir := DirAccess.open(dir_path)
		if dir == null:
			continue
		for sub in dir.get_directories():
			stack.append(dir_path + "/" + sub)
		for name in dir.get_files():
			if name.ends_with(".ogg"):
				out.append((dir_path + "/" + name).trim_prefix("res://assets/audio/"))
	out.sort()
	return out

func files_check() -> void:
	var Bank = sound.Bank
	var missing := []
	var paths := []
	for stem in Bank.VARIANTS:
		check(int(Bank.VARIANTS[stem]) >= 1, "sound %s has variants" % stem)
		for i in int(Bank.VARIANTS[stem]):
			paths.append(sound.variant_path(stem, i))
	for name in Bank.MUSIC:
		paths.append(Bank.MUSIC[name].path)
	for name in sound.STINGERS:
		paths.append("res://assets/audio/stingers/%s.ogg" % name)
	for scene in sound.AMBIENCE:
		for bed in sound.AMBIENCE[scene]:
			paths.append(sound.ambient_path(bed[0]))
	paths.append(sound.ambient_path("battle_din"))
	for stem in sound.LEVEL:
		check(Bank.VARIANTS.has(stem), "level entry %s is a bank sound" % stem)
	for path in paths:
		if not ResourceLoader.exists(path):
			missing.append(path)
			continue
		var stream := load(path) as AudioStreamOggVorbis
		if stream == null or stream.get_length() <= 0.0:
			missing.append(path)
	check(missing.is_empty(), "no missing audio files: %s" % str(missing))
	for name in Bank.MUSIC:
		var music := load(Bank.MUSIC[name].path) as AudioStreamOggVorbis
		check(music.loop and absf(music.loop_offset - float(Bank.MUSIC[name].loop_offset)) < 0.01, "music %s loops at %.2f s" % [name, Bank.MUSIC[name].loop_offset])
	for bed in ["city_birds", "city_market", "world_wind", "forest_birds", "battle_din"]:
		check((load(sound.ambient_path(bed)) as AudioStreamOggVorbis).loop, "ambient bed %s loops" % bed)
	# Licences: every file on disk is credited, with allowed licences only.
	var credits := FileAccess.get_file_as_string("res://assets/audio/CREDITS.md")
	var files := all_files()
	var uncredited := []
	var bad := []
	for file in files:
		if not credits.contains("`%s`" % file) or not Bank.LICENCES.has(file):
			uncredited.append(file)
			continue
		for licence in Bank.LICENCES[file]:
			if not licence in ALLOWED:
				bad.append("%s: %s" % [file, licence])
	check(files.size() == Bank.LICENCES.size(), "bank lists exactly the files on disk (%d / %d)" % [files.size(), Bank.LICENCES.size()])
	check(uncredited.is_empty(), "every audio file is in CREDITS.md: %s" % str(uncredited))
	check(bad.is_empty(), "only CC0 and CC-BY licences: %s" % str(bad))
	for word in ["NonCommercial", "CC-BY-NC", "CC-BY-SA", "ShareAlike"]:
		check(not credits.contains(word), "CREDITS.md has no %s licence" % word)
	report.files = {"count": files.size(), "missing": missing, "uncredited": uncredited, "variants": Bank.VARIANTS.size()}

# ------------------------------------------------------------------ 3 loudness
func loudness_check() -> void:
	var path := ProjectSettings.globalize_path("res://").path_join("../runtime-audit-1024/audio/loudness.tsv").simplify_path()
	var text := FileAccess.get_file_as_string(path)
	check(not text.is_empty(), "loudness.tsv present (run tools/audio/loudness_report.py)")
	var rows := {}
	var total := 0
	for line in text.split("\n"):
		var cells := line.split("\t")
		if cells.size() < 8 or cells[0] == "file":
			continue
		rows[cells[0]] = cells
		total += int(cells[6])
	var stale := []
	var off := []
	for file in all_files():
		if not rows.has(file):
			stale.append(file)
			continue
		var cells: PackedStringArray = rows[file]
		var size := FileAccess.open("res://assets/audio/" + file, FileAccess.READ).get_length()
		if size != int(cells[6]):
			stale.append(file)
		var lufs := float(cells[2])
		var peak := float(cells[4])
		var lead := float(cells[5])
		if peak > -1.0 or (cells[1] == "music" and absf(lufs + 16.0) > 1.0) or (cells[1] == "sfx" and lead > 10.0):
			off.append("%s %.1f LUFS %.1f dBTP %.1f ms" % [file, lufs, peak, lead])
	check(stale.is_empty(), "loudness table matches the files on disk: %s" % str(stale))
	check(off.is_empty(), "loudness targets met: %s" % str(off))
	check(total <= 25 * 1048576, "audio total %.2f MB <= 25 MB" % (total / 1048576.0))
	report.loudness = {"rows": rows.size(), "total_mb": snappedf(total / 1048576.0, 0.01), "off_target": off}

# ------------------------------------------------------------------ 4 settings
func settings_check() -> void:
	var backup := FileAccess.get_file_as_bytes("user://hud.cfg") if FileAccess.file_exists("user://hud.cfg") else PackedByteArray()
	var wanted := {"master": 0.9, "music": 0.4, "sfx": 0.6, "ui": 0.3, "ambient": 0.5, "voice": 0.7}
	for key in wanted:
		sound.set_volume(key, wanted[key], false)
	sound.set_muted("ambient", true, false)
	sound.set_muted("voice", false, false)
	sound.save_settings()
	var expected := {}
	for bus in BUSES:
		expected[bus] = AudioServer.get_bus_volume_db(AudioServer.get_bus_index(bus)) - (sound.duck_db + sound.background_db if bus == "Music" else sound.background_db if bus == "Ambient" else 0.0)
	# «Restart»: every bus back to 0 dB, then a fresh hub reads the file and applies it.
	for bus in BUSES:
		AudioServer.set_bus_volume_db(AudioServer.get_bus_index(bus), 0.0)
		AudioServer.set_bus_mute(AudioServer.get_bus_index(bus), false)
	var fresh: Node = load("res://src/audio/sound.gd").new()
	fresh.load_settings()
	fresh.apply_all()
	for key in wanted:
		check(is_equal_approx(float(fresh.volume[key]), wanted[key]), "volume %s persists (%.2f)" % [key, fresh.volume[key]])
	check(bool(fresh.muted.ambient) and not bool(fresh.muted.voice), "mutes persist")
	for bus in BUSES:
		var index := AudioServer.get_bus_index(bus)
		check(absf(AudioServer.get_bus_volume_db(index) - expected[bus]) < 0.05, "bus %s level applied at start (%.1f dB)" % [bus, expected[bus]])
	check(AudioServer.is_bus_mute(AudioServer.get_bus_index("Ambient")), "muted ambience applied at start")
	report.settings = {"saved": wanted, "bus_db": expected, "music_db_at_40": snappedf(expected.Music, 0.1)}
	fresh.free()
	# Back to the machine's own settings.
	if backup.is_empty():
		DirAccess.remove_absolute(ProjectSettings.globalize_path("user://hud.cfg"))
	else:
		var file := FileAccess.open("user://hud.cfg", FileAccess.WRITE)
		file.store_buffer(backup)
		file.close()
	sound.volume = sound.DEFAULTS.duplicate()
	sound.muted = {"master": false, "music": false, "sfx": false, "ui": false, "ambient": false, "voice": false}
	sound.load_settings()
	sound.apply_all()
	await frames(1)

# ------------------------------------------------------------------ game
func boot() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 120000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(is_instance_valid(game.stage), "game scene ready")
	if not is_instance_valid(game.stage):
		game = null
		return
	while game.forest_game == null and Time.get_ticks_msec() < deadline:
		await process_frame
	if game.forest_game != null:
		while not game.forest_game.world_ready() and Time.get_ticks_msec() < deadline:
			await process_frame
	sound.finish_loading()
	await frames(5)

## Town hall level 3 opens «Лес потерянных» (its intro then shows the forest).
func unlock_forest() -> void:
	await post("/test/army", {"units": {"ENG-02": 3000, "ENG-03": 3000, "ENG-06": 3000}})
	await post("/test/hall?level=3")
	var response: Dictionary = await game.request("state")
	if response.has("city"):
		game.accept(response)
	await frames(10)
	report.forest_unlocked = game.forest_game != null and game.forest_game.client.unlocked()

## Over the unlocked forest the forest layer itself asks for the forest theme (music_mood).
func forest_mood_check() -> void:
	var forest = game.forest_game
	if forest == null or not forest.client.unlocked():
		check(false, "forest unlocked for the mood check")
		return
	sound.set_theme_override("")
	await ensure_city()
	game.stage.camera_target = Vector3(game.stage.camera_target.x, game.stage.camera_target.y, 80.0)
	game.stage.target = game.stage.camera_target
	game.stage.apply_camera_pose()
	var t := await wait_theme("forest", 6.0)
	check(forest.music_mood() == "forest" and sound.theme == "forest", "the forest layer asks for the forest theme over the forest (mood %s)" % forest.music_mood())
	report.forest_mood = {"mood": forest.music_mood(), "after_s": t, "wind_on": forest.audio.wind_on}

func post(path: String, body: Variant = null) -> Dictionary:
	var client := HTTPRequest.new()
	root.add_child(client)
	client.request(server + path, PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, "" if body == null else JSON.stringify(body))
	var result: Array = await client.request_completed
	client.queue_free()
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8()) if not result[3].is_empty() else {}
	return parsed if parsed is Dictionary else {}

func window_check() -> void:
	var backup := FileAccess.get_file_as_bytes("user://hud.cfg") if FileAccess.file_exists("user://hud.cfg") else PackedByteArray()
	var menu = game.v6_panels.menu_view
	game.show_controls_menu()
	await frames(2)
	var entry: Node = game.modal_body.find_child("Tile_bell", true, false)
	var shortcut: Node = game.modal.find_child("SoundSettingsButton", true, false)
	check(entry != null, "menu has the «Звук и музыка» tile")
	check(shortcut != null, "menu settings have the «Громкость…» button")
	menu.sound_settings()
	await frames(3)
	var levels := {}
	for row in menu.SOUND_ROWS:
		var key: String = row[0]
		var slider := game.modal_body.find_child("Volume_" + key, true, false) as HSlider
		var toggle := game.modal_body.find_child("Mute_" + key, true, false) as CheckButton
		check(slider != null and toggle != null, "sound window row %s" % key)
		if slider == null or toggle == null:
			continue
		check(slider.size.y >= 44 and toggle.size.x >= 44, "row %s is touch-sized" % key)
		var before := float(sound.volume[key])
		slider.value = 30
		check(is_equal_approx(float(sound.volume[key]), 0.3), "slider %s sets 30 %%" % key)
		var bus_index := AudioServer.get_bus_index(sound.bus_of(key))
		var db := AudioServer.get_bus_volume_db(bus_index)
		levels[key] = snappedf(db, 0.1)
		toggle.button_pressed = false
		await frames(1)
		check(AudioServer.is_bus_mute(bus_index), "switch %s mutes its bus" % key)
		toggle.button_pressed = true
		await frames(1)
		check(not AudioServer.is_bus_mute(bus_index), "switch %s unmutes its bus" % key)
		slider.value = roundf(before * 100.0)
	report.window = {"bus_db_at_30_percent": levels}
	check(game.modal_body.find_child("SoundCredits", true, false) != null, "credits entry in the sound window")
	if not shots.is_empty():
		DirAccess.make_dir_recursive_absolute(shots)
		await frames(10)
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(shots.path_join("sound_settings.png"))
	menu.sound_credits()
	await frames(3)
	var lines: Node = game.modal_body.find_child("CreditsList", true, false)
	check(lines != null and lines.get_child_count() >= 20, "credits list shows the authors")
	if not shots.is_empty():
		await frames(10)
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(shots.path_join("sound_credits.png"))
	game.close_modal()
	await frames(2)
	# The window saved while it was used: put the machine's own file back.
	sound.save_timer = -1.0
	if backup.is_empty():
		DirAccess.remove_absolute(ProjectSettings.globalize_path("user://hud.cfg"))
	else:
		var file := FileAccess.open("user://hud.cfg", FileAccess.WRITE)
		file.store_buffer(backup)
		file.close()
	sound.volume = sound.DEFAULTS.duplicate()
	sound.load_settings()
	sound.apply_all()

# ------------------------------------------------------------------ 5 one sound per press
func sample_buttons(container: Node) -> Array:
	var out := []
	for node in container.find_children("*", "BaseButton", true, false):
		var button := node as BaseButton
		if not button.is_visible_in_tree() or button.disabled or String(button.get_meta("sfx", "")) == "none":
			continue
		var text := String(button.get("text")) if button.get("text") != null else ""
		var skip := button.name in SKIP_NAMES
		for word in SKIP_TEXT:
			if text.contains(word):
				skip = true
		if not skip:
			out.append(game.get_path_to(button))
	return out

func press_count(path: NodePath) -> int:
	var button := game.get_node_or_null(path) as BaseButton
	if button == null or not button.is_visible_in_tree():
		return -1
	sound.ui_last = {"kind": "", "msec": -100000, "priority": 0}
	await frames(1)
	var before: int = sound.ui_plays
	button.pressed.emit()
	await frames(3)
	return sound.ui_plays - before

func panel_buttons(label: String, opener: Callable, container_of: Callable, limit: int, results: Dictionary) -> void:
	opener.call()
	await frames(3)
	var paths := sample_buttons(container_of.call())
	var counts := []
	for i in mini(paths.size(), limit):
		opener.call()
		await frames(3)
		# Generated node names differ between openings: take the i-th button of a fresh one.
		var fresh := sample_buttons(container_of.call())
		if i >= fresh.size():
			continue
		var n: int = await press_count(fresh[i])
		if n < 0:
			continue
		counts.append(n)
		check(n == 1, "%s: %s gave %d interface sounds" % [label, String(paths[i]).get_file(), n])
		game.close_modal()
		await frames(2)
	results[label] = {"buttons": paths.size(), "pressed": counts.size(), "sounds": counts}

func buttons_check() -> void:
	var results := {}
	var menu = game.v6_panels.menu_view
	await panel_buttons("menu", game.show_controls_menu, func(): return game.modal, 30, results)
	await panel_buttons("sound window", menu.sound_settings, func(): return game.modal, 14, results)
	await panel_buttons("credits", menu.sound_credits, func(): return game.modal, 4, results)
	await panel_buttons("city actions", menu.city_actions, func(): return game.modal, 8, results)
	await panel_buttons("economy", game.show_economy, func(): return game.modal, 6, results)
	await panel_buttons("reports", game.show_reports, func(): return game.modal, 6, results)
	await panel_buttons("application", game.show_application, func(): return game.modal, 4, results)
	await ensure_city()
	var forest = game.forest_game
	if forest != null:
		await panel_buttons("forest hud", func(): game.close_modal(), func(): return forest.hud, 12, results)
		await panel_buttons("forest journal", forest.open_journal, func(): return game.modal, 12, results)
		# Taps without a Button: the task card and the mechanism input emit button_pressed.
		sound.ui_last = {"kind": "", "msec": -100000, "priority": 0}
		var before: int = sound.ui_plays
		forest.button_pressed.emit("mechanism_input")
		await frames(3)
		check(sound.ui_plays - before == 1, "forest mechanism input gives one interface sound")
		# A real forest button: its own click and the game's button_pressed collapse into one.
		sound.ui_last = {"kind": "", "msec": -100000, "priority": 0}
		before = sound.ui_plays
		var probe := Button.new()
		forest.hud.add_child(probe)
		probe.pressed.connect(func(): forest.button_pressed.emit("probe"))
		probe.pressed.emit()
		await frames(3)
		check(sound.ui_plays - before == 1, "a forest button and its button_pressed give one sound")
		probe.queue_free()
	else:
		check(false, "forest game layer present (server with the adventure on)")
	# The HUD last: its map switch changes the scene.
	await panel_buttons("hud", func(): game.close_modal(), func(): return game.profile_button.get_parent().get_parent(), 10, results)
	var total := 0
	for key in results:
		total += (results[key].sounds as Array).size()
	check(total >= 40, "sampled at least 40 button presses (%d)" % total)
	report.buttons = results
	game.close_modal()
	await frames(2)

# ------------------------------------------------------------------ 6 music
func wait_theme(theme: String, seconds: float) -> float:
	var started := Time.get_ticks_msec()
	while sound.theme != theme and Time.get_ticks_msec() - started < seconds * 1000.0:
		await process_frame
	return (Time.get_ticks_msec() - started) / 1000.0

## The theme changes at once; its track starts when its stream is in (worker load), meanwhile the old
## one keeps playing.
func wait_track(track: String, seconds: float) -> float:
	var started := Time.get_ticks_msec()
	while sound.track != track and Time.get_ticks_msec() - started < seconds * 1000.0:
		await process_frame
	return (Time.get_ticks_msec() - started) / 1000.0

func crossfade_seen(seconds: float) -> Dictionary:
	var both := 0
	var samples := 0
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec() - started < seconds * 1000.0:
		var playing := 0
		for p in sound.music_players:
			if p.playing:
				playing += 1
		if playing == 2:
			both += 1
		samples += 1
		await process_frame
	var still := 0
	for p in sound.music_players:
		if p.playing:
			still += 1
	return {"both_frames": both, "frames": samples, "playing_after": still}

func ensure_city() -> void:
	game.close_modal()
	if game.map_name != "city":
		game.show_scene("city")
	await frames(2)
	while game.scene_loading:
		await process_frame
	look_at_city()
	await frames(3)

## The camera over the settlement (not over the forest around it).
func look_at_city() -> void:
	var stage = game.stage
	if stage.map_name != "city":
		return
	stage.camera_target = Vector3(0.0, stage.camera_target.y, 0.0)
	stage.target = stage.camera_target
	stage.apply_camera_pose()

func music_check() -> void:
	var steps := []
	sound.set_theme_override("")
	await ensure_city()
	var t := await wait_theme("city", 6.0)
	check(sound.theme == "city" and sound.track in sound.CITY_PLAYLIST, "city theme in the city (%s)" % sound.track)
	await wait(1.0)
	var city_track: String = sound.track
	var city_player: AudioStreamPlayer = sound.track_player
	check(city_player != null and city_player.playing, "city music playing")
	steps.append({"to": "city", "after_s": t, "track": city_track})
	# The same theme again: no restart.
	var position := city_player.get_playback_position()
	game.show_scene("city")
	await wait(0.6)
	check(sound.track_player == city_player and city_player.get_playback_position() >= position, "same theme continues without restart")
	game.show_scene("world")
	t = await wait_theme("world", 8.0)
	var load_s := await wait_track("world_heroic_demise", 4.0)
	check(sound.theme == "world" and sound.track == "world_heroic_demise", "world theme on the world map")
	var fade := await crossfade_seen(sound.CROSSFADE + 0.8)
	check(fade.both_frames > 0 and fade.playing_after == 1, "city → world crossfades (%s)" % str(fade))
	steps.append({"to": "world", "after_s": t, "track_start_s": load_s, "track": sound.track, "crossfade": fade})
	var left_at := float(sound.positions.get(city_track, 0.0))
	check(left_at > 0.5, "city position remembered (%.1f s)" % left_at)
	game.show_scene("city")
	while game.scene_loading:
		await process_frame
	look_at_city()
	t = await wait_theme("city", 8.0)
	await frames(3)
	var resumed: float = sound.track_player.get_playback_position()
	check(sound.track == city_track and resumed >= left_at - 0.1 and resumed < left_at + 3.0, "city resumes where it was (%.1f → %.1f s)" % [left_at, resumed])
	fade = await crossfade_seen(sound.CROSSFADE + 0.8)
	steps.append({"to": "city", "after_s": t, "track": sound.track, "resumed_s": resumed, "crossfade": fade})
	# The forest theme (the forest layer's own request is checked in forest_mood_check once unlocked).
	var mood := ""
	sound.set_theme_override("forest")
	t = await wait_theme("forest", 8.0)
	load_s = await wait_track("forest_mystery_forest", 4.0)
	check(sound.theme == "forest" and sound.track == "forest_mystery_forest", "forest theme in the forest (mood %s)" % mood)
	fade = await crossfade_seen(sound.CROSSFADE + 0.8)
	check(fade.both_frames > 0 and fade.playing_after == 1, "city → forest crossfades")
	steps.append({"to": "forest", "after_s": t, "track": sound.track, "by_forest_mood": mood == "forest", "crossfade": fade})
	var wanted: Dictionary = sound.get_meta("ambient_wanted", {})
	check(wanted.has("forest_birds"), "forest ambience follows (%s)" % str(wanted.keys()))
	# A fight on screen: battle music and the battle din, back afterwards.
	sound.set_theme_override("")
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec() - started < 1500:
		game.stage.battle_fx.last_battle_msec = Time.get_ticks_msec()
		await process_frame
	t = await wait_theme("battle", 3.0)
	load_s = await wait_track("battle_defying_commodus", 4.0)
	check(sound.theme == "battle" and sound.track == "battle_defying_commodus", "battle theme while a fight is shown")
	wanted = sound.get_meta("ambient_wanted", {})
	check(wanted.has("battle_din"), "battle din under the fight")
	steps.append({"to": "battle", "track": sound.track})
	await wait(1.0)
	sound.set_theme_override("city")
	t = await wait_theme("city", 4.0)
	sound.set_theme_override("")
	report.music = {"steps": steps, "history": sound.theme_history}

# ------------------------------------------------------------------ 7 events
func played(stem: String, before: Dictionary) -> bool:
	return int(sound.counts.get(stem, 0)) > int(before.get(stem, 0))

func events_check() -> void:
	var results := {}
	var stage = game.stage
	var at: Vector3 = stage.camera_target
	sound.last_start = {}
	var before: Dictionary = sound.counts.duplicate()
	var markers: Array = stage.combat_view.markers.duplicate()
	var cases := [
		{"id": "qa/bow", "phase": "release", "event": {"kind": "soldier_attack", "unitId": "ENG-03"}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/xbow", "phase": "release", "event": {"kind": "soldier_attack", "unitId": "ENG-04"}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/arrow", "phase": "contact", "event": {"kind": "soldier_attack", "unitId": "ENG-03", "creatureHP": 50}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/sword", "phase": "contact", "event": {"kind": "soldier_attack", "unitId": "ENG-06", "creatureHP": 50}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/shield", "phase": "contact", "event": {"kind": "creature_attack", "unitId": "ENG-02", "index": 0, "hp": 30}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/armor", "phase": "contact", "event": {"kind": "creature_attack", "unitId": "ENG-06", "index": 0, "hp": 30}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/death", "phase": "contact", "event": {"kind": "creature_attack", "unitId": "ENG-01", "index": 1, "hp": 0}, "target": "none", "army_id": "qa", "lateness": 0.0},
		{"id": "qa/kill", "phase": "contact", "event": {"kind": "soldier_attack", "unitId": "ENG-02", "creatureHP": 0}, "target": "none", "army_id": "qa", "lateness": 0.0}]
	for marker in cases:
		for voice in stage.combat_audio.voices:
			voice.stop()
		stage.combat_view.markers = [marker]
		stage.combat_audio.consume(stage)
	stage.combat_view.markers = markers
	for stem in ["combat/bow", "combat/crossbow", "combat/arrow_hit", "combat/clash", "combat/flesh", "combat/shield", "combat/armor",
			"combat/fall", "voice/soldier_death", "combat/creature_death"]:
		check(played(stem, before), "combat marker plays %s" % stem)
		results[stem] = played(stem, before)
	for voice in stage.combat_audio.voices:
		voice.stop()
	before = sound.counts.duplicate()
	stage.combat_audio.fight_begins("qa-army", at)
	check(played("combat/creature_roar", before) and played("voice/war_cry", before), "a fight begins with a roar and a war cry")
	# Construction finished.
	before = sound.counts.duplicate()
	var works = stage.get("city_works")
	if works != null:
		works.celebrate(at, "Построено!")
		check(played("city/build_done", before) and played("stinger/construction_done", before), "construction finished: sound and stinger")
	# Orders and stingers.
	for pair in [[{"kind": "trade"}, "purchase"], [{"kind": "v6collect"}, "collect"], [{"kind": "deploy"}, "march"],
			[{"kind": "v6", "intent": {"kind": "construction"}}, "build_start"], [{"kind": "v6", "intent": {"kind": "train"}}, "train"], [{"kind": "speedup"}, "speedup"]]:
		before = sound.counts.duplicate()
		sound.ui_last = {"kind": "", "msec": -100000, "priority": 0}
		sound.order_sent(pair[0])
		await frames(2)
		check(played("ui/" + pair[1], before), "order %s plays ui/%s" % [pair[0].kind, pair[1]])
	before = sound.counts.duplicate()
	sound.ui_last = {"kind": "", "msec": -100000, "priority": 0}
	sound.order_failed()
	await frames(2)
	check(played("ui/error", before), "a refused order plays the error sound")
	for name in ["victory", "defeat", "reward", "construction_done"]:
		before = sound.counts.duplicate()
		sound.stinger(name)
		check(played("stinger/" + name, before), "stinger %s" % name)
	sound.stinger_player.stop()
	# Forest signals.
	var forest = game.forest_game
	if forest != null:
		var audio = forest.audio
		forest.foreground = true
		forest.sound_enabled = true
		for case in [["horse_feared", ["qa"], "forest/horse_fear"], ["creature_roared", ["qa", "ancient_maw"], "forest/roar"],
				["fight_hit", ["qa", "squad", "guardian"], ""], ["fight_hit", ["qa", "guardian", "squad"], ""],
				["fight_hit", ["qa", "death", "guardian"], "combat/creature_death"], ["fight_hit", ["qa", "death", "squad"], "voice/soldier_death"],
				["cage_opened", ["qa"], "ui/reward"]]:
			sound.last_start = {}
			sound.stop_all_sfx()
			before = sound.counts.duplicate()
			var total_before := 0
			for k in before:
				total_before += int(before[k])
			forest.emit_signal.callv([case[0]] + case[1])
			var total_after := 0
			for k in sound.counts:
				total_after += int(sound.counts[k])
			if String(case[2]).is_empty():
				check(total_after > total_before, "forest %s %s plays a hit" % [case[0], str(case[1])])
			else:
				check(played(case[2], before), "forest %s plays %s" % [case[0], case[2]])
		sound.last_start = {}
		sound.stop_all_sfx()
		before = sound.counts.duplicate()
		audio.last_hoof_msec = -100000
		audio.hoof(Vector3.ZERO)
		check(played("combat/hoof", before), "forest hoof contact plays the recorded hoof")
		check(played("forest/horse_snort", before) or played("forest/horse_neigh", before), "the horse snorts or neighs when it sets off")
		before = sound.counts.duplicate()
		forest.on_events([{"type": "fog_revealed"}])
		check(played("forest/fog_reveal", before), "fog reveal swish")
		before = sound.counts.duplicate()
		audio.recorded("ui/puzzle_right")
		audio.recorded("ui/puzzle_wrong")
		check(played("ui/puzzle_right", before) and played("ui/puzzle_wrong", before), "puzzle right and wrong")
	report.events = results
	sound.stop_all_sfx()

# ------------------------------------------------------------------ 8 voice limits, CPU
func burst_check() -> void:
	sound.stop_all_sfx()
	var at: Vector3 = game.stage.camera_target
	var started := Time.get_ticks_usec()
	var accepted := 0
	sound.last_start = {}
	for i in 200:
		sound.last_start = {}
		if sound.sfx("combat/clash", at + Vector3(randf_range(-20, 20), 0, randf_range(-20, 20))):
			accepted += 1
		sound.last_start = {}
		if sound.sfx("voice/war_cry" if i % 2 == 0 else "voice/soldier_hurt", at):
			accepted += 1
	var burst_us := Time.get_ticks_usec() - started
	var per_stem := {}
	var voice_bus := 0
	var playing := 0
	for p in sound.pool_2d + sound.pool_3d:
		if p.playing:
			playing += 1
			var stem := String(p.get_meta("stem", ""))
			per_stem[stem] = int(per_stem.get(stem, 0)) + 1
			if String(p.bus) == "Voice":
				voice_bus += 1
	for stem in per_stem:
		check(per_stem[stem] <= int(sound.LIMIT.get(stem, 3)), "burst: %s within its limit (%d)" % [stem, per_stem[stem]])
	check(voice_bus <= sound.VOICE_LIMIT, "burst: Voice bus within %d voices (%d)" % [sound.VOICE_LIMIT, voice_bus])
	check(playing <= sound.POOL_2D + sound.POOL_3D, "burst: pools bounded")
	var combat = game.stage.combat_audio
	for i in 300:
		combat.cue("qa-burst-%d" % i, ["clash", "flesh", "foot", "arrow_hit"][i % 4], at, i % 3)
	var combat_playing := 0
	for v in combat.voices:
		if v.playing:
			combat_playing += 1
	check(combat.voices.size() == 8 and combat_playing <= 8 and combat.seen.size() <= 512, "combat pool bounded")
	# CPU of the hub's frame (theme poll, fades, duck, listener).
	await frames(2)
	started = Time.get_ticks_usec()
	for i in 600:
		sound._process(0.016)
	var frame_us := (Time.get_ticks_usec() - started) / 600.0
	var memory := 0
	for path in sound.loaded:
		if sound.loaded[path] != null and FileAccess.file_exists(path):
			memory += FileAccess.open(path, FileAccess.READ).get_length()
	report.performance = {"burst_400_calls_us": burst_us, "accepted": accepted, "playing_after_burst": playing, "voice_bus": voice_bus,
		"per_stem": per_stem, "hub_frame_us": snappedf(frame_us, 0.1), "streams_loaded": sound.loaded.size(),
		"stream_memory_mb": snappedf(memory / 1048576.0, 0.01), "static_memory_mb": snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1)}
	check(frame_us < 300.0, "hub frame cost %.1f µs < 300 µs" % frame_us)
	sound.stop_all_sfx()

# ------------------------------------------------------------------ soundscapes (rendered runs)
func record_soundscapes() -> void:
	DirAccess.make_dir_recursive_absolute(record)
	var recorder := AudioEffectRecord.new()
	recorder.format = AudioStreamWAV.FORMAT_16_BITS
	AudioServer.add_bus_effect(0, recorder)
	var effect_index := AudioServer.get_bus_effect_count(0) - 1
	var scenes := [["city", ""], ["world", ""], ["forest", "forest"], ["battle", "battle"]]
	var recorded := {}
	for entry in scenes:
		if entry[0] == "world":
			game.show_scene("world")
		elif entry[0] == "city":
			game.show_scene("city")
		sound.set_theme_override(entry[1])
		await wait(3.0)
		recorder.set_recording_active(true)
		var started := Time.get_ticks_msec()
		var next_event := 0.0
		while Time.get_ticks_msec() - started < 30000:
			var seconds := (Time.get_ticks_msec() - started) / 1000.0
			if seconds > next_event:
				next_event = seconds + randf_range(1.5, 3.5)
				var at: Vector3 = game.stage.camera_target + Vector3(randf_range(-15, 15), 0, randf_range(-15, 15))
				match entry[0]:
					"city":
						sound.sfx("city/hammer", at)
					"battle":
						for stem in ["combat/clash", "combat/flesh", "combat/arrow_hit", "voice/soldier_hurt"]:
							sound.sfx(stem, at)
					"forest":
						sound.sfx(["forest/horse_snort", "combat/hoof", "forest/growl"][randi() % 3])
			await process_frame
		recorder.set_recording_active(false)
		var wav := recorder.get_recording()
		if wav != null:
			wav.save_to_wav(record.path_join("soundscape_%s.wav" % entry[0]))
			recorded[entry[0]] = wav.get_length()
	AudioServer.remove_bus_effect(0, effect_index)
	sound.set_theme_override("")
	report.soundscapes = recorded

func finish() -> void:
	report.checks = checks
	report.failures = failures
	if not report_path.is_empty():
		var file := FileAccess.open(report_path, FileAccess.WRITE)
		file.store_string(JSON.stringify(report, "  "))
		file.close()
	print("QA_AUDIO_1024 checks=%d failures=%d" % [checks, failures.size()])
	for failure in failures:
		print("FAIL ", failure)
	if game != null and is_instance_valid(game):
		game.queue_free()
	await frames(3)
	quit(0 if failures.is_empty() else 1)
