extends Node

const V6Panels = preload("res://src/v6_panels.gd")
# Rows of the chronicle (stage 4a): compiled after launch with the V6 windows (warm_views).
const REPORT_ROW := "res://src/report_row.gd"
var v6_panels = V6Panels.new(self)

const Landscape = preload("res://src/landscape.gd")
const Minimap = preload("res://src/minimap.gd")
const LaunchScreen = preload("res://src/launch_screen.gd")
const TouchScroll = preload("res://src/touch_scroll.gd")
const SessionStore = preload("res://src/session_store.gd")
const Interface = preload("res://src/ui_theme.gd")
const WebPanels = preload("res://src/web_panel_theme.gd")
const UiKit = preload("res://src/ui_kit.gd")
const UnitStage = preload("res://src/unit_stage.gd")
const BuildingStage = preload("res://src/building_stage.gd")
const CityBackdrop = preload("res://src/city_backdrop.gd")
const MarchMap = preload("res://src/march_map.gd")
const BattleResults = preload("res://src/battle_results.gd")
const WarriorVisual = preload("res://src/warrior_visual.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
const HudAction = preload("res://src/hud_action.gd")
const SessionDiagnostics = preload("res://src/session_diagnostics.gd")
const CombatDiagnostics = preload("res://src/combat_diagnostics.gd")
const BuildingPlates = preload("res://src/building_plates.gd")
const CityDefence = preload("res://src/city_defence.gd")
const TownGround = preload("res://src/town_ground.gd")
const TITLE_FONT = preload("res://assets/ui/NotoSerif-Regular.ttf")
# FOREST_RESCUE hook: gameplay layer of «Лес потерянных» (src/forest_rescue/game/). 1022: not preloaded
# (its scripts compile in ~0.3 s); created after the launch, only when the server projects the adventure.
const ForestFlags = preload("res://src/forest_rescue/world/forest_flags.gd")
const ForestProgress = preload("res://src/forest_progress.gd")
const SafeArea = preload("res://src/safe_area.gd")
# DRENOVAR-V6-ROSTER-5: spearman, swordsman, longbowman, crossbowman, knight (ENG-05/07/08/09/10 retired).
const RECRUIT_ORDER := ["ENG-01", "ENG-02", "ENG-03", "ENG-04", "ENG-06"]
const RECRUIT_FACILITIES := {"MIL-01":"Казармы пехоты", "MIL-02":"Стрельбище", "MIL-03":"Конюшня"}
const RESOURCE_NAMES := {"food":"Еда","wood":"Дерево","stone":"Камень","iron":"Железо","coins":"Монеты"}
## The highest building level the game offers for now (owner, stage 3): the level scenes above V
## are not made yet, so nothing in the client takes a building past it: the V6 building window
## and its quote, the action ring, the construction strip, the commands and the legacy flows
## all read this one constant. Raise it when the level-VI models ship.
const MAX_OPEN_BUILDING_LEVEL := 5
const SOON_LINE := "Новые уровни зданий скоро появятся"
const SCENE_REUSE_SECONDS := 40.0
const SCENE_REUSE_HARD_LIMIT := 60.0
# With VRAM-compressed textures both scenes fit together, so the inactive one is
# kept (instant city <-> world) unless process + video memory exceeds this or iOS
# sends a memory warning. Above it, the 0.5.9 timed release applies.
const TWO_SCENE_MEMORY_MB := 1300.0
# The other scene is prepared in the background after this much idle time.
const PREWARM_IDLE_MSEC := 2500
const PREWARM_QUIET_MSEC := 600
# The game server on the owner's Cloudflare (device accounts, settlement transfer,
# route-approach-v2). The old ChatGPT Sites server is OLD_SERVER_URL below.
const LIVE_SERVER := "https://drenovar-game.ali069587.workers.dev"
# The ChatGPT Sites server. On the Cloudflare server it is only used to move a
# settlement: the player confirms the old login there, the new server reads it.
const OLD_SERVER_URL := "https://drenovar.pink-lyric-9420.chatgpt.site"
var OLD_SERVER := OLD_SERVER_URL
var data: Dictionary
var state: Dictionary
var stage: Landscape
var scene_cache: Dictionary = {}
var retired_nodes: Array[Node] = []
var saved_views: Dictionary = {}
var scene_loading := false
var scene_switch_msec := 0
var prewarm_name := ""
var prewarm_stage: Landscape
var prewarm_cancelled := false
# After the inactive scene had to be released for memory, it is not rebuilt in the background.
var prewarm_paused_until := 0
var last_interaction_msec := 0
var camera_moving_now := false
signal prewarm_finished
var map_name := "city"
var hud := CanvasLayer.new()
var resource_buttons: Dictionary = {}
var resource_amounts: Dictionary = {}
var resource_icons: Dictionary = {}
var nav_buttons: Dictionary = {}
var dimmer: ColorRect
var dialog_tween: Tween
var message: Label
var profile_button: Button
# Finish time of the newest battle report the player has seen (the «Отчёты» badge counts
# the newer ones); kept in user://hud.cfg.
var reports_seen_ms := 0.0
const HUD_STATE_PATH := "user://hud.cfg"
## Settings of the menu (premium UI stage 4b): sound on the master bus, less motion (no window
## settle, no ring unfold). Kept in the HUD's file.
var sound_on := true
var reduced_motion := false
## Tone of the notice toast: "info", "good" or "warn" (an error, said calmly).
var message_tone := "info"
var message_shown := ""
var message_warn_text := ""
var message_tween: Tween
var modal: PanelContainer
var modal_title: Label
var modal_eyebrow: Label
var modal_body: VBoxContainer
var modal_status: Label
var modal_scroll: TouchScroll
var modal_tools: HBoxContainer
var modal_footer: HBoxContainer
var modal_header: PanelContainer
var modal_divider: ColorRect
# Premium window parts (src/ui_kit.gd).
var modal_vignette: TextureRect
var modal_frame: Panel
var modal_hero: Control
var modal_content: MarginContainer
var modal_side_space: Array = []
var modal_flourishes: Array = []
var modal_titles: VBoxContainer
var modal_header_balance: Control
var modal_layout := "center"
# Share of the screen width the hero column of a full-screen window takes (the recruitment
# window sets a wider one for its rail and 3D stage; reset on every open).
var modal_hero_share := 0.4
## A full window without a hero column whose body spans the screen (the chronicle's rows);
## the others keep a 900-unit reading width.
var modal_full_width := false
# Upper board of the tall header of full-screen windows: section line on the left, the
# player's resources (live) on the right.
var modal_top: Control
var modal_crumb: Label
var modal_crumb_plate: PanelContainer
var modal_wallet: HBoxContainer
var modal_wallet_amounts := {}
var web_sheet_style: StyleBoxTexture
var result_sheet_style: StyleBoxTexture
var result_notice: Button
var battle_results := BattleResults.new()
var result_open := false
var panel_textures := {}
var economy_rows: Dictionary = {}
var economy_source_label: Label
var starter_panel_open := false
var relocation_pins: Control
## The blurred city behind the construction strip (src/city_backdrop.gd).
var city_backdrop: CityBackdrop
var minimap: Minimap
var environment_atlas: Texture2D
var endpoint := LIVE_SERVER
var loopback := false
# QA only: key of a closed staging server, read from a file named on the command line
# (--staging-key-file=). A shipped app has no command line, so it never sends one.
var staging_key := ""
var hosted_override := false
var session := ""
var restoring_session := false
var saved_session_error := false
var login_proof := ""
var login_deadline := 0
var login_link_used := false
# True while a foreground (player-initiated) request is in flight. 1022: it no longer refuses
# other requests (the pool keeps several kept-alive connections); routine polls skip a beat.
var busy := false
var foreground_in_flight := 0
var api := ApiPool.new()
# Connections to the old server during a settlement transfer.
var old_api := ApiPool.new()
# Login mode reported by the server (/api/auth/info): "device" on Cloudflare.
var server_login := ""
var server_transfer := false
# The old-server login of the login screen moves a settlement instead of signing in.
var login_for_transfer := false
# A session of the old server saved by an earlier version of the app.
var pending_old_session := ""
var transfer_refresh := false
var web_link_hint_shown := false
var action_ring := ActionRing.new()
var last_command_ms := -1.0
var polling_state := false
var request_generation := 0
var login_in_progress := false
var client_update_required := false
var v6_protocol_confirmed := false
var pending_login_save_error := false
var command_in_progress := false
var player_id := ""
var server_offset := 0.0
var poll := 0.0
var fingers: Dictionary = {}
var last_pinch := 0.0
var pinch_center := Vector2.ZERO
var tap_candidate := false
var dragging := false
var pointer_distance := 0.0
var smoke := false
var frame_samples := PackedFloat32Array()
var frame_index := 0
var frame_count := 0
var motion_samples := PackedFloat32Array()
var motion_index := 0
var motion_count := 0
var last_scene_ms := 0
var last_scene_label := ""
var memory_peak_mb := 0.0
var last_frame_us := 0
var modal_generation := 0
var action_list_key := ""
var next_training_update := 0.0
var followed_army := ""
var next_minimap_draw := 0
var forest_game: Node # FOREST_RESCUE hook (null until the server offers the adventure)
var forest_game_loading := false
var forest_load_started_msec := -1
var forest_progress: Control   # 1023: «Лес потерянных · готовим лес» while the layers load
# 1023: the display's safe area (src/safe_area.gd): the HUD, the windows' heads and close buttons,
# the construction strip and the forest row keep clear of the notch and the home indicator.
var hud_outer: Control
var modal_safe_spacers: Array[Control] = []
var modal_close: Control
var safe_check_accum := 0.0
var fitting_modal := false
const HUD_MARGIN := Vector4(52, 4, 52, 24)
const FOREST_PROGRESS_MARGIN := Vector2(16, 14)
var forest_ratio := 0.0
var launch_done := false
signal forest_game_ready
var diagnostics := SessionDiagnostics.new()
# Combat diagnostics overlay and event log (off unless switched on in the
# smoothness panel or with --combat-diagnostics); see src/combat_diagnostics.gd.
var combat_diagnostics: CanvasLayer = null
const OFFLINE_NOTICE := "Нет связи · повторяем"
var offline_notice_shown := false
# 1022 network rules (drenovar-server v6/docs/STATUS-1022-SERVER.md §10–11): transient failures
# are repeated silently with the same Idempotency-Key; the connection pill shows only after
# 10 s without any 200 or 304.
const COMMAND_RETRY_DELAYS := [0.4, 1.2, 2.8]
const COMMAND_RETRY_WINDOW_MS := 30000
const CONNECTION_NOTICE_AFTER_MS := 10000
# When the last 200 or 304 arrived, in the app's own running time (1023): a frame longer than
# LINK_FRAME_CAP_MS (the forest compiling a script, a scene build) and the time the app spent
# suspended in the background move it on by their excess, so neither counts as time without
# a connection; only real request failures and real silence do.
var last_ok_msec := 0
const LINK_FRAME_CAP_MS := 250
var link_frame_msec := 0
var paused_at_msec := -1
var creature_portraits: Array[Texture2D] = []
var next_notice_check_msec := 0
# Conditional state polls (v6/docs/CONDITIONAL-STATE-1022.md): the full tagged answer is kept
# (never an advanced copy); a 304 re-applies it with the time moved on. Off for the rest of the
# session after an unexpected 304; never required (no tag ever is fine).
const CONDITIONAL_POLLS := true
const STATE_ETAG_PATTERN := "^W/\"v6s1\\.\\d{1,15}\\.\\d{13,15}\\.[0-9a-f]{32}\"$"
var conditional_polls_ok := true
var state_etag := ""
var state_etag_owner := ""
var state_etag_serial := 0
var state_cache: Dictionary = {}
var not_modified_polls := 0
var full_polls := 0
var etag_regex: RegEx = null
# Small pill under the resource bar; replaces the large centre message for link state.
var connection_badge: Label
var building_plates: Control
# The city shown at launch may come from the encrypted local copy (the last state
# the server sent); the server copy replaces it as soon as it arrives.
var showing_cached_state := false
var restore_running := false
signal restore_finished
const STATE_SAVE_INTERVAL_MSEC := 8000
var state_saved_msec := -STATE_SAVE_INTERVAL_MSEC
var state_save_pending := false
# Kinetic camera glide after a quick one-finger swipe.
const FLING_MIN_SPEED := 280.0
const FLING_STOP_SPEED := 24.0
const FLING_FRICTION := 5.5
const FLING_SAMPLE_USEC := 90000
var drag_samples: Array = []
# Idempotency keys kept for commands whose response was lost in transport, so a
# retry of the same order can never be applied twice by the server.
var retry_keys: Dictionary = {}
var fling_velocity := Vector2.ZERO
var fling_point := Vector2.ZERO

func _ready() -> void:
	last_ok_msec = Time.get_ticks_msec()
	Input.use_accumulated_input = false
	frame_samples.resize(240)
	motion_samples.resize(120)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			var override := arg.trim_prefix("--server=").trim_suffix("/")
			if override.begins_with("http://127.0.0.1:"):
				endpoint = override
				loopback = true
			elif override.begins_with("https://"):
				# QA against a hosted test server (e.g. the Cloudflare staging Worker).
				endpoint = override
		if arg.begins_with("--old-server=http://127.0.0.1:"):
			# QA: a local stand-in for the old server in transfer tests.
			OLD_SERVER = arg.trim_prefix("--old-server=").trim_suffix("/")
		if arg == "--hosted":
			# QA: the 127.0.0.1 address is a forwarder to a hosted server
			# (godot/tools/qa-hosted-forwarder.py), not the loopback test realm.
			hosted_override = true
		if arg.begins_with("--staging-key-file="):
			staging_key = FileAccess.get_file_as_string(arg.trim_prefix("--staging-key-file=")).strip_edges()
		if arg == "--smoke":
			smoke = true
		if arg.begins_with("--diagnostics="):
			diagnostics.path = arg.trim_prefix("--diagnostics=")
	if hosted_override:
		loopback = false
	diagnostics.start(str(ProjectSettings.get_setting("application/config/version")), Time.get_unix_time_from_system())
	if "--combat-diagnostics" in OS.get_cmdline_user_args() or CombatDiagnostics.stored_enabled():
		set_combat_diagnostics(true, false)
	api.name = "ApiPool"
	add_child(api)
	old_api.name = "OldApiPool"
	add_child(old_api)
	var launch := LaunchScreen.new()
	add_child(launch)
	# Window kit textures decode on worker threads while the launch screen shows.
	UiKit.preload_async()
	# Give the branded screen a frame before parsing game data and loading meshes.
	await get_tree().process_frame
	await get_tree().process_frame
	data = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	# Generated from the versioned V6 art recipes before export. Original I–V
	# entries stay untouched; VI–XI have their own full-size scenes.
	var v6_art: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://assets/city/architecture-v6/manifest.json"))
	if v6_art is Dictionary:
		for type: String in v6_art.get("levels", {}):
			if not data.levelModels.has(type):
				data.levelModels[type] = {}
			data.levelModels[type].merge(v6_art.levels[type], false)
		for unit_id: String in v6_art.get("units", {}):
			data.unitModels[unit_id] = {"field":v6_art.units[unit_id].path, "drill":""}
			data.englishRoster.append({"id":unit_id,"name":"Таран","unit_class":"Осадная машина","training_building":"SIEGE","power":0})
	state = data.demo
	add_child(hud)
	build_ui()
	SafeArea.parse_args(OS.get_cmdline_user_args())
	SafeArea.refresh(get_viewport())
	apply_safe_area()
	get_viewport().size_changed.connect(refresh_safe_area)
	# FOREST_RESCUE hook: adventure overlay, actors, intro and network client. 1022: lazy, see
	# maybe_start_forest_game() (QA/capture tools may ask for the eager 1021+forest order).
	if ForestFlags.eager():
		await ensure_forest_game()
	if loopback:
		await sync_account(true)
	else:
		session = SessionStore.read_session()
		resume_pending_main_login()
		if not session.is_empty() and not SessionStore.is_device(session) and LIVE_SERVER != OLD_SERVER_URL and endpoint == LIVE_SERVER:
			# A login of the old server: never sent to this one; offered for the transfer.
			pending_old_session = session
			session = ""
		if not session.is_empty():
			# The saved city opens at once; the server is asked in parallel with the
			# scene load and its answer replaces the copy without any waiting screen.
			show_cached_state(SessionStore.read_state(session, endpoint))
			if login_proof.is_empty():
				restore_account()
	launch.show_step("Готовим поселение…", 52 if restore_running else 72)
	var launch_started := Time.get_ticks_msec()
	# Under the launch screen the city is built in large slices (Landscape.launching).
	Landscape.launching = true
	await show_scene("city")
	Landscape.launching = false
	var city_built_ms := Time.get_ticks_msec() - launch_started
	if restore_running and not showing_cached_state:
		# First launch after an update (no local copy yet): wait a little for the
		# server so the player lands in their own city, not in the demo one.
		launch.show_step("Загружаем ваше поселение…", 86)
		var deadline := Time.get_ticks_msec() + 6000
		while restore_running and Time.get_ticks_msec() < deadline:
			await get_tree().process_frame
	if endpoint == LIVE_SERVER and (not v6_panels.enabled() or not login_proof.is_empty()) and not smoke:
		# «Аккаунт» opens after the launch (below) and is a lazy view (premium UI stage 4b):
		# its script compiles on a worker while the first frames are drawn.
		v6_panels.request_view("menu_view")
	var warm := await settle_first_frames(launch)
	diagnostics.log_event("launch", {"city_ms": city_built_ms, "first_frames_ms": warm.x, "first_frames": warm.y,
		"total_ms": Time.get_ticks_msec() - launch_started}, Time.get_unix_time_from_system(), false)
	launch.finish()
	launch_done = true
	warm_panel_textures()
	# Unit portraits (cards, queues, army) decode on worker threads now, not on first use.
	UnitStage.warm_portraits(data.get("unitModels", {}).keys() + ["SIEGE-RAM-01"])
	warm_windows()
	maybe_start_forest_game() # FOREST_RESCUE hook: only after the city is interactive
	if restoring_session and not showing_cached_state:
		message.text = "Подключаемся к поселению…"
	if endpoint == LIVE_SERVER and (not v6_panels.enabled() or not login_proof.is_empty()) and not smoke:
		show_account()
	if smoke:
		await run_smoke()

# The city's first frames are drawn behind the opaque launch screen, which fades only
# once frames come at a normal pace. Up to build 1020 the fade started together with
# the first frame of the city: that frame prepares the shaders of every building, tree
# and the ground (Metal on the phone) and took seconds, so the launch screen stood
# half faded over the city ("Поселение готово") until it was done. Returns
# (milliseconds, frames) spent here; at most FIRST_FRAMES_MS.
const FIRST_FRAMES_MS := 4000

func settle_first_frames(launch) -> Vector2:
	if DisplayServer.get_name() == "headless" or not is_instance_valid(launch):
		return Vector2.ZERO
	launch.show_step("Рисуем поселение…", 92)
	var started := Time.get_ticks_msec()
	var previous := Time.get_ticks_usec()
	var frames := 0
	var recent: Array[float] = []
	while Time.get_ticks_msec() - started < FIRST_FRAMES_MS:
		await get_tree().process_frame
		var now := Time.get_ticks_usec()
		recent.append((now - previous) / 1000.0)
		previous = now
		frames += 1
		if recent.size() > 3:
			recent.pop_front()
		# Three quick frames, or three alike (a slower device at its own steady pace).
		if frames >= 4 and recent.size() == 3 and (recent.max() < 40.0 or recent.max() < recent.min() * 1.25):
			break
	return Vector2(Time.get_ticks_msec() - started, frames)

func make_vignette() -> TextureRect:
	# Soft darkening toward the screen edges frames the scene and keeps the eye on the
	# centre. One small gradient texture stretched over the screen; drawn under the HUD.
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.55, 0.82, 1.0])
	gradient.colors = PackedColorArray([Color(0.04, 0.05, 0.04, 0.0), Color(0.04, 0.05, 0.04, 0.0),
		Color(0.04, 0.05, 0.04, 0.22), Color(0.03, 0.035, 0.03, 0.5)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(1.0, 0.5)
	texture.width = 128
	texture.height = 64
	var vignette := TextureRect.new()
	vignette.name = "Vignette"
	vignette.texture = texture
	vignette.stretch_mode = TextureRect.STRETCH_SCALE
	vignette.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	vignette.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return vignette

func build_ui() -> void:
	var root := Control.new()
	root.theme = Interface.make_theme()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	root.add_child(make_vignette())
	building_plates = BuildingPlates.new()
	building_plates.name = "BuildingPlates"
	building_plates.game = self
	root.add_child(building_plates)
	action_ring.clock = timer_now
	root.add_child(action_ring)
	var outer := VBoxContainer.new()
	hud_outer = outer
	outer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	outer.offset_left = HUD_MARGIN.x
	outer.offset_right = -HUD_MARGIN.z
	outer.offset_top = HUD_MARGIN.y
	outer.offset_bottom = -HUD_MARGIN.w
	outer.add_theme_constant_override("separation",12)
	outer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(outer)
	var bar := HBoxContainer.new()
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	outer.add_child(bar)
	setup_resource_icons()
	profile_button = hud_action(bar, "Профиль", "profile", show_account)
	profile_button.name = "ProfileButton"
	var saved := ConfigFile.new()
	if saved.load(HUD_STATE_PATH) == OK:
		reports_seen_ms = float(saved.get_value("hud", "reports_seen_ms", 0.0))
		sound_on = bool(saved.get_value("settings", "sound", true))
		reduced_motion = bool(saved.get_value("settings", "reduced_motion", false))
		action_ring.reduced_motion = reduced_motion
	if not sound_on:
		AudioServer.set_bus_mute(0, true)
	var wallet := HBoxContainer.new()
	wallet.add_theme_constant_override("separation", 2)
	wallet.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	wallet.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	wallet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	wallet.alignment = BoxContainer.ALIGNMENT_END
	bar.add_child(wallet)
	for key in RESOURCE_NAMES:
		add_resource_button(wallet, key)
	# One soft oak ribbon behind the counters (the counters themselves stay plate-less).
	wallet.draw.connect(draw_wallet_band.bind(wallet))
	wallet.sort_children.connect(wallet.queue_redraw)
	var navigation := HBoxContainer.new()
	navigation.add_theme_constant_override("separation", 5)
	navigation.alignment = BoxContainer.ALIGNMENT_END
	nav_buttons.city = hud_action(navigation, "Город", "city", show_scene.bind("city"))
	nav_buttons.world = hud_action(navigation, "Карта", "world", show_scene.bind("world"))
	nav_buttons.build = hud_action(navigation, "Строить", "build", show_build_menu)
	nav_buttons.army = hud_action(navigation, "Армия", "army", show_armies)
	nav_buttons.reports = hud_action(navigation, "Отчёты", "reports", show_reports)
	nav_buttons.menu = hud_action(navigation, "Меню", "menu", show_controls_menu)
	var space := Control.new()
	space.mouse_filter = Control.MOUSE_FILTER_IGNORE
	space.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(space)
	var controls := HBoxContainer.new()
	controls.add_theme_constant_override("separation",8)
	controls.mouse_filter = Control.MOUSE_FILTER_IGNORE
	outer.add_child(controls)
	var spacer := Control.new()
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	controls.add_child(spacer)
	var map_controls := VBoxContainer.new()
	map_controls.size_flags_vertical = Control.SIZE_SHRINK_END
	map_controls.add_theme_constant_override("separation", 6)
	controls.add_child(map_controls)
	minimap = Minimap.new()
	minimap.setup(Marshalls.base64_to_raw(data.minimap))
	minimap.location_chosen.connect(focus_minimap)
	minimap.size_flags_horizontal = Control.SIZE_SHRINK_END
	map_controls.add_child(minimap)
	minimap.hide()
	map_controls.add_child(navigation)
	# The notice toast (premium UI stage 4b): the carved oak plate of the completion banners,
	# a small medallion with its tone (info, done, a calm amber «!» for an error) and ivory
	# text. It eases in when its text changes and hides when the text is empty.
	message = Label.new()
	message.name = "Message"
	message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	message.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	message.add_theme_color_override("font_color", UiKit.IVORY)
	message.add_theme_color_override("font_outline_color", Color("#120c07"))
	message.add_theme_constant_override("outline_size", 4)
	message.add_theme_font_override("font", UiKit.LABEL_FONT)
	message.add_theme_font_size_override("font_size", 18)
	message.add_theme_stylebox_override("normal", toast_plate(58))
	message.self_modulate.a = 0.0
	message.draw.connect(draw_toast_mark.bind(message))
	outer.add_child(message)
	connection_badge = Label.new()
	connection_badge.name = "ConnectionBadge"
	connection_badge.text = OFFLINE_NOTICE
	connection_badge.add_theme_font_override("font", UiKit.LABEL_FONT)
	connection_badge.add_theme_font_size_override("font_size", 16)
	connection_badge.add_theme_color_override("font_color", Color("#f6e2b8"))
	connection_badge.add_theme_stylebox_override("normal", toast_plate(46))
	connection_badge.draw.connect(draw_toast_mark.bind(connection_badge))
	connection_badge.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	connection_badge.grow_horizontal = Control.GROW_DIRECTION_BOTH
	connection_badge.offset_top = 60
	connection_badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(connection_badge)
	connection_badge.hide()
	forest_progress = ForestProgress.new()
	forest_progress.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	root.add_child(forest_progress)
	relocation_pins = Control.new()
	relocation_pins.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(relocation_pins)
	relocation_pins.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	relocation_pins.draw.connect(draw_relocation_pins)
	var relocation_tools := HBoxContainer.new()
	relocation_pins.add_child(relocation_tools)
	relocation_tools.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	relocation_tools.offset_left = -145
	relocation_tools.offset_top = 66
	relocation_tools.offset_right = 145
	button(relocation_tools, "Свободные места", show_relocation_list)
	button(relocation_tools, "Закрыть ×", close_modal)
	relocation_pins.hide()
	dimmer = ColorRect.new()
	dimmer.color = Color("#050c0980")
	dimmer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dimmer.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(dimmer)
	dimmer.hide()
	city_backdrop = CityBackdrop.new()
	root.add_child(city_backdrop)
	city_backdrop.settled.connect(func():
		if modal.visible and modal_layout == "strip":
			cover_city(true))
	modal = PanelContainer.new()
	modal.name = "Modal"
	# Premium window (src/ui_kit.gd): carved oak header band, linen body, bronze rim.
	modal.theme = UiKit.theme(root.theme)
	web_sheet_style = UiKit.body_style()
	result_sheet_style = UiKit.nine("kit_body_dark", Vector4.ZERO, Vector4.ZERO, true)
	modal.add_theme_stylebox_override("panel", web_sheet_style)
	root.add_child(modal)
	modal_vignette = UiKit.make_vignette()
	modal.add_child(modal_vignette)
	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 0)
	modal.add_child(inner)
	var header := PanelContainer.new()
	modal_header = header
	header.name = "ModalHeader"
	header.add_theme_stylebox_override("panel", UiKit.header_style())
	header.custom_minimum_size.y = 70
	inner.add_child(header)
	var heading := HBoxContainer.new()
	heading.add_theme_constant_override("separation", 6)
	header.add_child(heading)
	# Balances the close button so the title stays centred on the window.
	modal_header_balance = Control.new()
	modal_header_balance.custom_minimum_size.x = 56
	modal_header_balance.mouse_filter = Control.MOUSE_FILTER_IGNORE
	heading.add_child(modal_header_balance)
	var centre := HBoxContainer.new()
	centre.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	centre.alignment = BoxContainer.ALIGNMENT_CENTER
	centre.add_theme_constant_override("separation", 10)
	heading.add_child(centre)
	modal_flourishes = [UiKit.flourish(false), UiKit.flourish(true)]
	centre.add_child(modal_flourishes[0])
	var titles := VBoxContainer.new()
	titles.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	titles.alignment = BoxContainer.ALIGNMENT_CENTER
	titles.add_theme_constant_override("separation", -2)
	centre.add_child(titles)
	centre.add_child(modal_flourishes[1])
	modal_titles = titles
	modal_eyebrow = UiKit.eyebrow_label()
	titles.add_child(modal_eyebrow)
	modal_title = UiKit.title_label(30)
	modal_title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	titles.add_child(modal_title)
	var close_button := UiKit.close_button(close_modal)
	heading.add_child(close_button)
	modal_close = close_button
	# Safe-area spacers at both ends of the head and the body (1023): the oak band stays edge to
	# edge, the title, the close button and the content keep clear of the notch.
	var head_left := Control.new()
	head_left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	heading.add_child(head_left)
	heading.move_child(head_left, 0)
	var head_right := Control.new()
	head_right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	heading.add_child(head_right)
	# Kept for callers of the previous layout; the bronze trim of the band is the divider now.
	var divider := ColorRect.new()
	modal_divider = divider
	divider.color = Color.TRANSPARENT
	divider.custom_minimum_size.y = 0
	divider.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inner.add_child(divider)
	var body_row := HBoxContainer.new()
	body_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body_row.add_theme_constant_override("separation", 0)
	inner.add_child(body_row)
	modal_side_space = [Control.new(), Control.new()]
	modal_hero = Control.new()
	modal_hero.name = "ModalHero"
	modal_hero.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var body_left := Control.new()
	body_left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body_row.add_child(body_left)
	body_row.add_child(modal_side_space[0])
	body_row.add_child(modal_hero)
	modal_content = MarginContainer.new()
	modal_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body_row.add_child(modal_content)
	body_row.add_child(modal_side_space[1])
	var body_right := Control.new()
	body_right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body_row.add_child(body_right)
	modal_safe_spacers = [head_left, head_right, body_left, body_right]
	for side_space: Control in modal_side_space:
		side_space.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		side_space.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	modal_content.add_child(column)
	modal_tools = HBoxContainer.new()
	column.add_child(modal_tools)
	var scroll := TouchScroll.new()
	modal_scroll = scroll
	scroll.press_root = modal
	scroll.custom_minimum_size.y = 84
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	column.add_child(scroll)
	modal_body = VBoxContainer.new()
	modal_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_body.add_theme_constant_override("separation",10)
	scroll.add_child(modal_body)
	# What went wrong inside a window, said calmly: ink on a warm parchment note with a
	# small amber medallion (stage 4b), never red alarm text.
	modal_status = Label.new()
	modal_status.name = "ModalStatus"
	modal_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	modal_status.add_theme_color_override("font_color", UiKit.INK)
	modal_status.add_theme_font_override("font", UiKit.LABEL_FONT)
	modal_status.add_theme_font_size_override("font_size", 17)
	var note := StyleBoxFlat.new()
	note.bg_color = Color("#f6e6c4")
	note.border_color = Color("#c08a3e")
	note.set_border_width_all(1)
	note.border_width_left = 4
	note.set_corner_radius_all(8)
	note.content_margin_left = 48
	note.content_margin_right = 14
	note.content_margin_top = 8
	note.content_margin_bottom = 8
	note.anti_aliasing = true
	modal_status.add_theme_stylebox_override("normal", note)
	modal_status.draw.connect(draw_toast_mark.bind(modal_status))
	modal_status.hide()
	column.add_child(modal_status)
	modal_footer = HBoxContainer.new()
	modal_footer.alignment = BoxContainer.ALIGNMENT_CENTER
	modal_footer.add_theme_constant_override("separation", 18)
	column.add_child(modal_footer)
	build_modal_top()
	modal_frame = UiKit.make_frame()
	modal.add_child(modal_frame)
	place_modal("center")
	modal.hide()
	# A full window never grows past the screen (1023): the building window's hero (half the
	# width) and its widest row of chips asked for about 30 units more than 1366, so the band
	# sat 15 units right and the close button was cut by the screen's edge.
	modal.minimum_size_changed.connect(fit_full_modal)
	modal.resized.connect(fit_full_modal)
	result_notice = Button.new()
	result_notice.text = "Бой завершён · Открыть результат"
	result_notice.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	result_notice.offset_left = -220
	result_notice.offset_right = 220
	result_notice.offset_top = 70
	result_notice.offset_bottom = 119
	WebPanels.primary(result_notice)
	result_notice.pressed.connect(present_next_battle_result)
	root.add_child(result_notice)
	result_notice.hide()
	refresh_hud()

## The toast plate: carved oak with gold lozenge ends (kit_strip), room at the left for the
## tone medallion.
func toast_plate(left: int) -> StyleBoxTexture:
	var plate := UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(left, 9, 30, 11)).duplicate() as StyleBoxTexture
	return plate

## The tone medallion at the left of a toast, the connection pill and a window's notice.
func draw_toast_mark(item: Label) -> void:
	if item.text.is_empty():
		return
	var small := item == connection_badge
	var centre := Vector2(28.0 if item != modal_status else 24.0, item.size.y * 0.5)
	var r := 11.0 if small or item == modal_status else 14.0
	# «Отправляем…» on the window's status line is a wait, not a warning.
	var tone := message_tone if item == message else ("wait" if item != modal_status or modal_status.text.ends_with("…") else "warn")
	UiKit.draw_tone(item, centre, r, tone)

## A new notice: its tone (an error, a done job, or news), then a short ease-in (80 ms
## fade and a 6 px rise; none with less motion). Empty text hides the toast at once.
func show_toast_change() -> void:
	message_shown = message.text
	if message_tween != null:
		message_tween.kill()
	if message.text.is_empty():
		message.self_modulate.a = 0.0
		return
	if message.text != message_warn_text:
		message_tone = "good" if message.text.begins_with("Готово") or message.text.ends_with("скопирован") or message.text.contains("завершен") else "info"
	message.queue_redraw()
	if reduced_motion:
		message.self_modulate.a = 1.0
		return
	message.self_modulate.a = 0.0
	message.pivot_offset = message.size * 0.5
	message.scale = Vector2(0.97, 0.97)
	message_tween = create_tween().set_parallel()
	message_tween.tween_property(message, "self_modulate:a", 1.0, 0.08)
	message_tween.tween_property(message, "scale", Vector2.ONE, 0.14).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

func hud_action(parent: Container, caption: String, symbol: String, action: Callable) -> Button:
	var control := HudAction.new()
	control.caption = caption
	control.symbol = symbol
	control.tooltip_text = caption
	control.accessibility_name = caption
	control.pressed.connect(action)
	parent.add_child(control)
	return control

## «Меню» (premium UI stage 4b, src/v6_menu.gd): grouped medallion tiles and the settings.
func show_controls_menu() -> void:
	v6_panels.menu_view.open()

## Sound on or off (the master bus), kept with the HUD's state; the forest follows it.
func set_sound(on: bool) -> void:
	sound_on = on
	AudioServer.set_bus_mute(0, not on)
	save_setting("sound", on)
	if forest_game != null and forest_game.sound_enabled != on:
		forest_game.set_sound(on)

## Less motion: windows open without their settle, the ring without its unfold, and the
## forest's own reduced motion.
func set_reduced_motion(on: bool) -> void:
	reduced_motion = on
	action_ring.reduced_motion = on
	save_setting("reduced_motion", on)
	if forest_game != null and forest_game.reduced_motion != on:
		forest_game.set_reduced_motion(on)

func save_setting(key: String, value: Variant) -> void:
	var saved := ConfigFile.new()
	saved.load(HUD_STATE_PATH)
	saved.set_value("settings", key, value)
	saved.save(HUD_STATE_PATH)

func setup_resource_icons() -> void:
	var atlas := load("res://assets/ui/resources.png") as Texture2D
	var tile := atlas.get_size() / Vector2(3, 2)
	var ids := ["food", "wood", "stone", "iron", "coins", "brand"]
	for index in ids.size():
		var icon := AtlasTexture.new()
		icon.atlas = atlas
		icon.filter_clip = true
		icon.region = Rect2(Vector2(index % 3, floori(index / 3.0)) * tile, tile)
		resource_icons[ids[index]] = icon

func add_resource_button(wallet: Container, key: String) -> void:
	var control := button(wallet, "", show_economy.bind(key))
	control.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
	control.custom_minimum_size = Vector2(108, 44)
	# No backing plate over the city (qa_camera_hud); the outline + shadow carry legibility.
	Interface.hud_button(control)
	resource_buttons[key] = control
	var card := HBoxContainer.new()
	card.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	card.offset_left = 7
	card.offset_right = -7
	card.add_theme_constant_override("separation", 4)
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	control.add_child(card)
	add_resource_icon(card, key, 28)
	var labels := VBoxContainer.new()
	labels.mouse_filter = Control.MOUSE_FILTER_IGNORE
	labels.alignment = BoxContainer.ALIGNMENT_CENTER
	labels.add_theme_constant_override("separation", 0)
	labels.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_child(labels)
	var amount := Label.new()
	amount.add_theme_font_size_override("font_size", 18)
	amount.add_theme_color_override("font_color", Color("#fff0d4"))
	amount.add_theme_color_override("font_outline_color", Color("#191511"))
	amount.add_theme_constant_override("outline_size", 6)
	# Soft drop shadow keeps the counters legible over bright grass without a backing plate.
	amount.add_theme_color_override("font_shadow_color", Color(0.05, 0.04, 0.03, 0.7))
	amount.add_theme_constant_override("shadow_offset_x", 0)
	amount.add_theme_constant_override("shadow_offset_y", 2)
	amount.add_theme_constant_override("shadow_outline_size", 8)
	amount.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	labels.add_child(amount)
	resource_amounts[key] = amount

static var wallet_band: GradientTexture2D

## The ribbon behind the resource counters: dark oak fading out at both ends, a bronze
## hairline along its foot and a small lozenge between counters. Drawn by the wallet row
## itself, only when its layout changes.
func draw_wallet_band(wallet: Control) -> void:
	var shown: Array = wallet.get_children().filter(func(c): return c is Control and c.visible)
	if shown.is_empty():
		return
	var first: Control = shown[0]
	var last: Control = shown[-1]
	var rect := Rect2(first.position.x - 34.0, first.position.y - 3.0, last.position.x + last.size.x - first.position.x + 58.0, first.size.y + 6.0)
	if wallet_band == null:
		var fade := Gradient.new()
		fade.offsets = PackedFloat32Array([0.0, 0.12, 0.88, 1.0])
		fade.colors = PackedColorArray([Color(0.08, 0.05, 0.03, 0.0), Color(0.08, 0.05, 0.03, 0.58), Color(0.08, 0.05, 0.03, 0.58), Color(0.08, 0.05, 0.03, 0.0)])
		wallet_band = GradientTexture2D.new()
		wallet_band.gradient = fade
		wallet_band.width = 128
		wallet_band.height = 4
	wallet.draw_texture_rect(wallet_band, rect, false)
	var foot := Rect2(rect.position.x, rect.end.y - 1.0, rect.size.x, 1.5)
	wallet.draw_texture_rect(wallet_band, foot, false, Color(3.2, 2.4, 1.3, 1.0))
	for index in range(1, shown.size()):
		var x: float = shown[index].position.x - 1.0
		var y := rect.get_center().y
		wallet.draw_colored_polygon(PackedVector2Array([Vector2(x, y - 4.0), Vector2(x + 3.0, y), Vector2(x, y + 4.0), Vector2(x - 3.0, y)]), Color("#c9a05aaa"))

## Badges of the HUD medallions and the profile line: unread reports, free builders.
func refresh_hud_badges() -> void:
	if not nav_buttons.has("reports"):
		return
	var unread := 0
	for report in state.get("reports", []):
		if report is Dictionary and float(report.get("finishedAt", 0.0)) > reports_seen_ms:
			unread += 1
	nav_buttons.reports.set_badge("" if unread == 0 else ("9+" if unread > 9 else str(unread)))
	var free := 0
	if v6_panels.enabled() and v6_panels.build != null:
		var use: Array = v6_panels.build.builder_use()
		free = maxi(0, int(use[1]) - int(use[0]))
	nav_buttons.build.set_badge(str(free) if free > 0 else "", true)
	var name_text := str(state.get("city", {}).get("name", ""))
	if name_text.is_empty():
		name_text = str(state.get("nickname", "Профиль"))
	var line := ""
	if v6_panels.enabled():
		var hall: Dictionary = v6_panels.building("B01")
		if not hall.is_empty():
			line = "%s %s" % [str(v6_panels.row_for("B01", 1).get("name_ru", "Ратуша")), V6Panels.ROMAN[clampi(int(hall.get("level", 1)), 1, 11) - 1]]
	profile_button.set_profile(name_text, line)

func mark_reports_seen() -> void:
	var newest := reports_seen_ms
	for report in state.get("reports", []):
		if report is Dictionary:
			newest = maxf(newest, float(report.get("finishedAt", 0.0)))
	if newest == reports_seen_ms:
		return
	reports_seen_ms = newest
	var saved := ConfigFile.new()
	saved.load(HUD_STATE_PATH)
	saved.set_value("hud", "reports_seen_ms", reports_seen_ms)
	saved.save(HUD_STATE_PATH)
	refresh_hud_badges()

func add_resource_icon(parent: Control, key: String, pixels: float) -> void:
	var icon := TextureRect.new()
	icon.texture = resource_icons[key]
	icon.custom_minimum_size = Vector2(pixels, pixels)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(icon)

func panel(inset := 14, dialog := false) -> PanelContainer:
	# Window sub-panel: a linen card in a bronze hairline (src/ui_kit.gd).
	var control := PanelContainer.new()
	var card := UiKit.row_style().duplicate() as StyleBoxTexture
	card.content_margin_left = inset
	card.content_margin_right = inset
	card.content_margin_top = maxi(inset - 4, 4)
	card.content_margin_bottom = inset
	control.add_theme_stylebox_override("panel", card)
	return control

func button(parent: Container, title: String, action: Callable, enabled := true) -> Button:
	var value := Button.new()
	value.text = title
	value.custom_minimum_size = Vector2(48,42)
	value.disabled = not enabled
	if action.is_valid():
		value.pressed.connect(action)
	parent.add_child(value)
	return value

func row(parent: Container, title: String) -> void:
	var label := Label.new()
	label.text = title
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(label)

func bind_countdown(label: Label, title: String, ends_at: float) -> void:
	var update := func():
		var left := display_end(ends_at) - timer_now()
		var value := timer_end_label() if left <= 0.0 else clock_text(ceili(left / 1000.0))
		label.text = value if title.is_empty() else "%s · %s" % [title, value]
	var clock := Timer.new()
	clock.wait_time = 1.0
	clock.autostart = true
	label.add_child(clock)
	clock.timeout.connect(update)
	update.call()

static func clock_text(seconds: int) -> String:
	if seconds >= 3600:
		return "%d:%02d:%02d" % [seconds / 3600, (seconds / 60) % 60, seconds % 60]
	return "%d:%02d" % [seconds / 60, seconds % 60]

func countdown(title: String, ends_at: float) -> void:
	# Hourglass pill: what is running on the left, the time left in gold on the right.
	bind_countdown(UiKit.timer_pill(modal_body, title, ""), "", ends_at)

func balance(id: String) -> int:
	if id == "wood":
		return int(state.city.get("progress", {}).get("wood", 0))
	return int(state.city.get("demo", {}).get("wallet", {}).get(id, 0))

func capacity() -> int:
	var value := 1200
	for building in state.city.buildings:
		value += int(data.buildingTerms.get(building.type, {}).get("storage", 0)) * int(building.level)
	return value

func hall_level() -> int:
	for building in state.city.buildings:
		if building_definition(building.type).get("base", building.type) == "ECO-05":
			return int(building.level)
	return 1

func reward_label(resources: Dictionary) -> String:
	var labels := PackedStringArray()
	var names := {"food":"еды", "wood":"дерева", "stone":"камня", "iron":"железа", "coins":"монет"}
	for resource in resources:
		if int(resources[resource]) > 0:
			labels.append("+%s %s" % [format_balance(int(resources[resource])), names.get(resource, resource)])
	return " · ".join(labels)

func cost_label(cost: Dictionary) -> String:
	var items: PackedStringArray = []
	for resource in cost:
		if int(cost[resource]) > 0:
			items.append("%s %d" % [RESOURCE_NAMES[resource], int(cost[resource])])
	return " · ".join(items) if not items.is_empty() else "Без затрат"

func can_afford(cost: Dictionary) -> bool:
	for resource in cost:
		if int(cost[resource]) > balance(resource):
			return false
	return true

func construction_order() -> Dictionary:
	var city: Dictionary = state.city
	var construction: Variant = city.get("kingdom", city.get("legacyUpgrades"))
	if construction is Dictionary and construction.get("order") is Dictionary:
		return construction.order
	return {}

# ---------------------------------------------------------------- workers
# Builders and lumberjacks of the settlement. The server says how many there are
# (server patch workers-v1: a second worker from «Жилой дом» III; an older server
# has one and sends nothing). A worker holds one task: a construction order or a
# forest job. Orders sent but not yet answered hold a worker too, so a second tap
# never takes the worker the first order already uses (the old single forecast slot
# was overwritten, and the first upgrade seemed to move to the second building).
const WORKERS_HOUSING_LEVEL := 3

func worker_total() -> int:
	return clampi(int(state.get("workers", 1)), 1, 2)

func construction_orders() -> Array:
	var city: Dictionary = state.get("city", {})
	var construction: Variant = city.get("kingdom", city.get("legacyUpgrades"))
	var orders: Array = []
	if construction is Dictionary:
		for slot in ["order", "order2"]:
			if construction.get(slot) is Dictionary:
				orders.append(construction[slot])
	return orders

func server_jobs() -> Array:
	var progress: Variant = state.get("city", {}).get("progress", {})
	var jobs: Array = []
	if progress is Dictionary:
		for slot in ["job", "job2"]:
			if progress.get(slot) is Dictionary:
				jobs.append(progress[slot])
	return jobs

func busy_workers() -> int:
	if v6_panels.enabled():
		return state.v6.orders.filter(func(o): return o.status == "pending" and o.kind in ["construction", "repair_wall"]).size() + server_jobs().size()
	return construction_orders().size() + server_jobs().size() + pending_works.size()

func free_workers() -> int:
	return maxi(0, worker_total() - busy_workers())

func builder_ready() -> bool:
	return free_workers() > 0

func workers_busy_text() -> String:
	return "Все рабочие заняты" if worker_total() > 1 else "Строитель занят"

# The order running (or sent) on one building, else {}.
func building_order(building_id: String) -> Dictionary:
	for order in construction_orders():
		if str(order.get("buildingId", "")) == building_id:
			return order
	for slot in pending_works:
		var predicted: Dictionary = pending_works[slot]
		if str(predicted.get("building", "")) == building_id:
			return {"kind": str(predicted.order.get("action", "")), "buildingId": building_id, "endsAt": float(predicted.ends),
				"predicted": true}
	return {}

# When the next worker is free (the soonest end of the running tasks), or INF.
func next_worker_free_at() -> float:
	var soonest := INF
	for order in construction_orders():
		soonest = minf(soonest, float(order.get("endsAt", INF)))
	for job in server_jobs():
		soonest = minf(soonest, float(job.get("endsAt", INF)))
	for slot in pending_works:
		soonest = minf(soonest, float(pending_works[slot].get("ends", INF)))
	return soonest

# A line under a refused action: who is busy and, with one worker, how the second comes.
func add_workers_note(parent: Container) -> void:
	if v6_panels.enabled():
		row(parent, "Строители заняты. Откройте очереди, чтобы проверить оставшееся время или отменить работу.")
		if int(state.workers) < 2:
			row(parent, "Второй бесплатный строитель открывается с IV уровня ратуши.")
		return
	var ends := next_worker_free_at()
	if ends < INF and ends > timer_now():
		var label := Label.new()
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.add_theme_color_override("font_color", UiKit.WARN)
		parent.add_child(label)
		bind_countdown(label, workers_busy_text() + " · свободен через", ends)
	else:
		row(parent, workers_busy_text() + ".")
	if worker_total() < 2 and int(state.get("workers", 0)) > 0:
		row(parent, "Второй рабочий появится с «Жилым домом» %d уровня." % WORKERS_HOUSING_LEVEL)

func show_city_actions() -> void:
	if is_v6_server():
		if not await ensure_v6_ready():
			return
		v6_panels.menu_view.city_actions()
		return
	open_modal("Поселение")
	button(modal_body, "Строить", show_build_menu)
	button(modal_body, "Ресурсы и доход", show_economy)
	button(modal_body, "Найти существо", show_city_hunt)
	if not stage.parade_slots.is_empty():
		button(modal_body, "Парадный строй", focus_parade)
	row(modal_body, "Предел производства на ресурс · %d" % capacity())
	if worker_total() > 1:
		row(modal_body, "Рабочие · свободно %d из %d" % [free_workers(), worker_total()])
	for order in construction_orders():
		var title: String = {"clear":"Расчистка", "build":"Строительство", "upgrade":"Улучшение"}.get(order.kind, "Заказ")
		countdown(title, order.endsAt)
		button(modal_body, "Подробнее о заказе", inspect_construction_order.bind(order))
		if order.kind != "clear":
			button(modal_body, "Ускорить строительство", show_speedups.bind("construction", order, ""))
	for job in server_jobs():
		if job.has("endsAt"):
			countdown("Работа на участке", job.endsAt)
	if state.get("starterEligible71", false):
		button(modal_body, "Первые шаги", show_starter_goals)
	elif state.city.get("kingdom") is Dictionary and not state.city.kingdom.guide.get("skipped", false):
		button(modal_body, "Первые шаги", show_city_guide)
	button(modal_body, "Расчистка рощ", show_clearings)
	button(modal_body, "Гарнизон", show_armies)

func show_city_guide() -> void:
	if is_v6_server():
		await v6_panels.objectives()
		return
	open_modal("Первые шаги", "right")
	var guide: Dictionary = state.city.kingdom.guide
	if not guide.get("entered", false):
		row(modal_body, "Добро пожаловать в английское поселение.")
		button(modal_body, "Начать", command.bind({"kind":"kingdom", "action":"enter"}))
	elif not guide.get("collected", false):
		row(modal_body, "Открой лагерь лесорубов и собери производство.")
		var camp: int = state.city.buildings.find_custom(func(building): return building_definition(building.type).get("base") == "RES-01")
		if camp >= 0:
			button(modal_body, "Лагерь лесорубов", inspect_building.bind(state.city.buildings[camp]))
	else:
		button(modal_body, "Ресурсы и доход", show_economy)
		button(modal_body, "Обучить воинов", show_training_buildings)
		button(modal_body, "Найти существо", show_city_hunt)
	button(modal_body, "Пропустить подсказки", command.bind({"kind":"kingdom", "action":"skip"}))

func show_application() -> void:
	open_modal("Приложение DRENOVAR")
	row(modal_body, "Версия %s · сборка %s · общий сервер" % [ProjectSettings.get_setting("application/config/version"), ProjectSettings.get_setting("application/config/build_number", "")])
	row(modal_body, "Игровой прогресс сохраняется в серверном поселении аккаунта." if not player_id.is_empty() else "Войди в аккаунт, чтобы играть со своим поселением.")
	button(modal_body, "Аккаунт", show_account)
	button(modal_body, "Проверка плавности", show_performance)

func show_economy(resource := "") -> void:
	if is_v6_server():
		v6_panels.economy()
		return
	open_modal(RESOURCE_NAMES.get(resource, "Запасы поселения"), "left")
	if not resource.is_empty():
		add_economy_card(resource, true)
		economy_source_label = Label.new()
		economy_source_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		modal_body.add_child(economy_source_label)
	for key in RESOURCE_NAMES:
		if key != resource:
			add_economy_card(key, false)
	if state.city.buildings.any(func(building): return building_definition(building.type).get("base") == "ECO-03"):
		Interface.accent_button(button(modal_body, "Обмен на рынке", show_trade.bind(resource), not player_id.is_empty()))
	refresh_economy()

func add_economy_card(resource: String, selected: bool) -> void:
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UiKit.row_style())
	modal_body.add_child(card)
	var contents := HBoxContainer.new()
	contents.add_theme_constant_override("separation", 11)
	card.add_child(contents)
	add_resource_icon(contents, resource, 51 if selected else 33)
	var values := VBoxContainer.new()
	values.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	contents.add_child(values)
	var total := Label.new()
	total.add_theme_color_override("font_color", UiKit.INK)
	total.add_theme_font_override("font", UiKit.LABEL_FONT)
	total.add_theme_font_size_override("font_size", 24 if selected else 19)
	values.add_child(total)
	var production := Label.new()
	production.add_theme_font_size_override("font_size", 15 if selected else 14)
	production.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	values.add_child(production)
	economy_rows[resource] = {"total": total, "production": production, "selected": selected}

func refresh_economy() -> void:
	if economy_rows.is_empty():
		return
	var limit := capacity()
	var totals := {}
	var sources := PackedStringArray()
	for building in state.city.buildings:
		var terms: Dictionary = data.buildingTerms.get(building.type, {})
		var resource: Variant = terms.get("production")
		if resource == null:
			continue
		var level := int(building.level)
		var rate := int(terms.rates[clampi(level, 1, 5) - 1])
		totals[resource] = int(totals.get(resource, 0)) + rate
		if economy_rows.get(resource, {}).get("selected", false):
			sources.append("%s · ур. %d · +%d/мин" % [building_title(building.type), level, rate])
	if is_instance_valid(economy_source_label):
		economy_source_label.text = "\n".join(sources)
		economy_source_label.visible = not sources.is_empty()
	var founder: bool = state.city.get("demo", {}).get("unlimitedResources", false) == true
	for resource in economy_rows:
		var labels: Dictionary = economy_rows[resource]
		var value := balance(resource)
		var rate := int(totals.get(resource, 0))
		var stopped := rate > 0 and value >= limit and not founder
		labels.total.text = "%s — %s" % [RESOURCE_NAMES[resource], format_balance(value)]
		var status := "Производство приостановлено" if stopped else "+%d/мин" % rate
		labels.production.text = "Запас основателя" if founder else status + " · предел производства — " + format_balance(limit)
		labels.production.add_theme_color_override("font_color", UiKit.WARN if stopped else UiKit.INK_MUTED)

func format_balance(value: int) -> String:
	var digits := str(value)
	var groups := PackedStringArray()
	while digits.length() > 3:
		groups.insert(0, digits.right(3))
		digits = digits.left(-3)
	groups.insert(0, digits)
	return " ".join(groups)

const BUILD_GROUPS := [["", "Все"], ["resources", "Ресурсы"], ["civil", "Хозяйство"], ["military", "Войска"], ["support", "Оборона и помощь"]]
var build_group := ""
var build_cards := {}

func building_card(type: String) -> Texture2D:
	var key: String = data.types.get(type, "")
	if key.is_empty():
		return null
	if not build_cards.has(key):
		var path := "res://assets/ui/buildings/%s.png" % key
		build_cards[key] = load(path) if ResourceLoader.exists(path) else null
	return build_cards[key]

# Card art of a V6 building type: the model the city shows for its instance, else the
# model of the same purpose (premium window hero, src/ui_kit.gd).
const V6_CARD_KEYS := {"B01":"hall", "B02":"house", "B03":"warehouse", "B05":"market27", "B06":"lumber",
	"B07":"quarry27", "B08":"ironmine27", "B09":"farm", "B10":"hunt27", "B11":"barracks26", "B12":"range26",
	"B13":"stables26", "B14":"smith", "B15":"academy27", "B16":"hospital27", "B17":"workshop27", "B18":"gate27",
	"B19":"watchtower27", "B20":"well", "B21":"lumber", "B22":"farm", "B23":"hunt27", "B24":"fishing27",
	"B25":"herbal27"}

func v6_card(type: String) -> Texture2D:
	# The diorama of the construction strip (level I on its turf tile, baked from the city's
	# own scene): one look for the building in every window.
	var diorama := BuildingStage.card_art(type)
	if diorama != null:
		return diorama
	var instance: Dictionary = v6_panels.building(type) if v6_panels.enabled() else {}
	if not instance.is_empty():
		for city_building in state.city.get("buildings", []):
			if str(city_building.get("id", "")) == str(instance.id):
				var art := building_card(str(city_building.type))
				if art != null:
					return art
	var key: String = V6_CARD_KEYS.get(type, "")
	if key.is_empty():
		return null
	if not build_cards.has(key):
		var path := "res://assets/ui/buildings/%s.png" % key
		build_cards[key] = load(path) if ResourceLoader.exists(path) else null
	return build_cards[key]

# Status of a core building type for the construction window.
func legacy_city() -> bool:
	return not state.city.get("kingdom") is Dictionary

# Settlements of the earlier model (duplicates allowed, no clearing, no hall gate)
# take "legacyBuilding place"; kingdom settlements take "kingdom build".
func build_order(plot_id: String, type: String) -> Dictionary:
	if legacy_city():
		return {"kind":"legacyBuilding", "action":"place", "type":type, "plotId":plot_id}
	return {"kind":"kingdom","action":"build","plotId":plot_id,"type":type}

# An earlier-layout settlement moved to the new server builds through the paid queue,
# one building per purpose, like a kingdom (server feature "legacyBuild").
# Which building already holds this purpose (a variant counts: Сад травника is a Лазарет).
func built_reason(definition: Dictionary) -> String:
	for item in state.city.buildings:
		var other := building_definition(item.type)
		if other.get("base", item.type) == definition.get("base", definition.get("id", "")) and other.get("id", item.type) != definition.get("id", ""):
			return "Уже есть: %s (%d ур.). Одно здание каждого назначения; улучшение — в самом здании." % [other.get("ru", item.type), int(item.level)]
	return "Уже построено. Улучшение — в самом здании."

func paid_legacy_build() -> bool:
	return legacy_city() and state.get("city", {}).get("legacyUpgrades") is Dictionary and "legacyBuild" in state.get("cityFeatures", [])

func build_option(definition: Dictionary) -> Dictionary:
	if legacy_city() and not paid_legacy_build():
		return {"state": "ready", "required": 1, "terms": data.buildingTerms.get(definition.id, {"cost": {}, "seconds": 0})}
	var exists: bool = state.city.buildings.any(func(item): return building_definition(item.type).get("base", item.type) == definition.base)
	var required := int(data.unlockLevels.get(definition.id, 3))
	var terms: Dictionary = data.buildingTerms.get(definition.id, {"cost": {}, "seconds": 0})
	var state_name := "built" if exists else ("locked" if required > hall_level() else ("short" if not can_afford(terms.cost) else "ready"))
	return {"state": state_name, "required": required, "terms": terms}

# Construction window: a bottom sheet over the city (the settlement stays visible)
# with category tabs and a horizontal strip of cards for every building. A card
# that can be built starts placement mode: the building follows the finger and
# snaps onto a free plot; "Построить" there sends the order.
func show_build_menu(group := build_group) -> void:
	if is_v6_server():
		v6_panels.catalog()
		return
	build_group = group
	open_modal("Строительство", "sheet")
	modal_title.add_theme_font_size_override("font_size", 25)
	modal_scroll.horizontal = true
	modal_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	modal_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	modal_scroll.outside_tap = close_modal
	modal_scroll.armed_at = Time.get_ticks_msec() + modal_scroll.OPEN_GUARD_MSEC
	modal_tools.show()
	modal_tools.add_theme_constant_override("separation", 6)
	for entry in BUILD_GROUPS:
		var tab := button(modal_tools, entry[1], show_build_menu.bind(entry[0]))
		tab.custom_minimum_size = Vector2(0, 40)
		tab.add_theme_font_size_override("font_size", 16)
		if entry[0] == group:
			WebPanels.primary(tab)
	var spring := Control.new()
	spring.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	modal_tools.add_child(spring)
	var order := construction_order()
	var status := Label.new()
	status.add_theme_font_size_override("font_size", 15)
	status.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	modal_tools.add_child(status)
	if not builder_ready():
		bind_countdown(status, workers_busy_text(), next_worker_free_at())
		status.add_theme_color_override("font_color", UiKit.WARN)
		if not order.is_empty() and order.kind != "clear":
			var hurry := button(modal_tools, "Ускорить", show_speedups.bind("construction", order, ""))
			hurry.add_theme_font_size_override("font_size", 16)
	else:
		status.text = "Ратуша · ур. %d" % hall_level()
		if worker_total() > 1:
			status.text += " · рабочих свободно %d из %d" % [free_workers(), worker_total()]
		status.add_theme_color_override("font_color", UiKit.BRONZE)
	var strip := HBoxContainer.new()
	strip.add_theme_constant_override("separation", 10)
	strip.size_flags_vertical = Control.SIZE_EXPAND_FILL
	modal_body.add_child(strip)
	var options := []
	for definition in data.buildings:
		if definition.variant != "core" or definition.base == "ECO-05" or not data.types.has(definition.id):
			continue
		if not group.is_empty() and definition.group != group:
			continue
		options.append([definition, build_option(definition)])
	# Buildable first, then short of resources, locked by hall level, built.
	var rank := {"ready": 0, "short": 1, "locked": 2, "built": 3}
	options.sort_custom(func(a, b):
		if rank[a[1].state] != rank[b[1].state]:
			return rank[a[1].state] < rank[b[1].state]
		return int(a[1].required) < int(b[1].required))
	for entry in options:
		strip.add_child(build_card_button(entry[0], entry[1]))
	if options.is_empty():
		row(modal_body, "В этом разделе пока нечего строить.")

func build_card_glow(color: Color) -> GradientTexture2D:
	var key := "glow:" + color.to_html()
	if build_cards.has(key):
		return build_cards[key]
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.62, 1.0])
	gradient.colors = PackedColorArray([Color(color, 0.55), Color(color, 0.12), Color(color, 0.0)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.62)
	texture.fill_to = Vector2(1.0, 0.62)
	texture.width = 96
	texture.height = 64
	build_cards[key] = texture
	return texture

func build_card_button(definition: Dictionary, option: Dictionary) -> Button:
	var ready: bool = option.state == "ready"
	var card := Button.new()
	card.add_to_group("build_card")
	card.custom_minimum_size = Vector2(196, 206)
	card.clip_contents = true
	card.accessibility_name = definition.ru
	card.tooltip_text = definition.ru
	var top: Color = {"ready": Color("#4a5a47"), "short": Color("#4a4440"), "locked": Color("#33363a"), "built": Color("#39434a")}[option.state]
	var edge := WebPanels.GOLD if ready else Color("#76664e")
	card.add_theme_stylebox_override("normal", WebPanels.gradient_style(top, Color("#14181b"), edge, 6, 9))
	card.add_theme_stylebox_override("hover", WebPanels.gradient_style(top.lightened(0.08), Color("#14181b"), WebPanels.GOLD, 6, 9))
	card.add_theme_stylebox_override("pressed", WebPanels.gradient_style(top.darkened(0.15), Color("#14181b"), WebPanels.GOLD, 6, 9))
	card.pressed.connect(func():
		if build_option(definition).state == "ready" and builder_ready():
			start_placement(definition)
		else:
			show_build_details(definition))
	var glow := TextureRect.new()
	glow.texture = build_card_glow({"ready": Color("#ffd889"), "short": Color("#e6a676"), "locked": Color("#9aa3ad"), "built": Color("#9fd2c8")}[option.state])
	glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glow.stretch_mode = TextureRect.STRETCH_SCALE
	glow.position = Vector2(8, 6)
	glow.size = Vector2(180, 104)
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(glow)
	var box := VBoxContainer.new()
	box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	box.offset_left = 7
	box.offset_right = -7
	box.offset_top = 6
	box.offset_bottom = -8
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_theme_constant_override("separation", 3)
	card.add_child(box)
	var art := TextureRect.new()
	art.texture = building_card(definition.id)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.custom_minimum_size.y = 100
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if option.state == "locked":
		art.modulate = Color(0.5, 0.52, 0.55)
	box.add_child(art)
	var title := Label.new()
	title.text = definition.ru
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 16 if definition.ru.length() <= 16 else 14)
	title.custom_minimum_size.x = 1
	title.add_theme_color_override("font_color", WebPanels.IVORY if option.state != "locked" else Color("#c4bcae"))
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(title)
	# Cost wraps onto a second line instead of widening the card.
	var foot := HFlowContainer.new()
	foot.alignment = FlowContainer.ALIGNMENT_CENTER
	foot.add_theme_constant_override("h_separation", 6)
	foot.add_theme_constant_override("v_separation", 0)
	foot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(foot)
	match option.state:
		"built":
			card_note(foot, "Построено", Color("#9fd29a"))
		"locked":
			card_note(foot, "Нужна ратуша %d" % option.required, Color("#d7c7a8"))
		_:
			for resource in option.terms.cost:
				var amount := int(option.terms.cost[resource])
				if amount <= 0 or not resource_icons.has(resource):
					continue
				var item := HBoxContainer.new()
				item.add_theme_constant_override("separation", 2)
				item.mouse_filter = Control.MOUSE_FILTER_IGNORE
				foot.add_child(item)
				add_resource_icon(item, resource, 18)
				card_note(item, compact_number(amount), Color("#fff0d4") if amount <= balance(resource) else Color("#ff8f7a"), 14)
	var time := HBoxContainer.new()
	time.alignment = BoxContainer.ALIGNMENT_CENTER
	time.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(time)
	if option.state in ["ready", "short"]:
		card_note(time, ("Выбрать место · %s" if ready else "Мало ресурсов · %s") % duration_label(int(option.terms.seconds)),
			WebPanels.GOLD if ready else Color("#ffb08f"), 13)
	# Disable mouse capture on the whole subtree: the card itself takes the tap.
	for child in card.find_children("*", "Control", true, false):
		(child as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
	return card

func card_note(parent: Container, text: String, color: Color, font_size := 15) -> Label:
	var note := Label.new()
	note.text = text
	note.add_theme_font_size_override("font_size", font_size)
	note.add_theme_color_override("font_color", color)
	note.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(note)
	return note

func duration_label(seconds: int) -> String:
	if seconds < 60:
		return "%d с" % seconds
	if seconds < 3600:
		return "%d мин %02d с" % [seconds / 60, seconds % 60] if seconds % 60 else "%d мин" % (seconds / 60)
	return "%d ч %02d мин" % [seconds / 3600, (seconds % 3600) / 60]

# --- Placement mode -----------------------------------------------------------
var placing := {}
var placement_bar: PanelContainer
var placement_title: Label
var placement_info: Label
var placement_confirm: Button
var placement_finger := -1
var placement_grab_offset := Vector2.ZERO
const PLACEMENT_GRAB_RADIUS := 120.0
const PLACEMENT_SNAP := 9.0
const PLACEMENT_EDGE := 64.0

func plot_cleared(plot: Dictionary) -> bool:
	var kingdom: Variant = state.city.get("kingdom")
	return not kingdom is Dictionary or plot.id in kingdom.get("clearedPlots", []) or str(plot.id).begins_with("site-")

func start_placement(definition: Dictionary) -> void:
	close_modal()
	if map_name != "city" or not is_instance_valid(stage):
		return
	var plots := []
	for marker in stage.empty_plots:
		plots.append({"position": marker.position, "plot": marker.item, "cleared": plot_cleared(marker.item)})
	if plots.is_empty():
		message.text = "Нет свободного участка: сруби дерево и подготовь место."
		return
	var first := free_build_plot()
	var asset: Dictionary = data.models[data.types[definition.id]]
	stage.show_placement(asset.path, float(asset.scale), plots)
	placing = {"definition": definition, "plots": plots, "plot": first.plot, "position": first.position,
		"cleared": first.cleared, "free": first.position, "lifted": false}
	stage.target = first.position
	stage.zoom = minf(stage.zoom, 58.0)
	action_ring.close()
	ensure_placement_bar()
	placement_title.text = definition.ru
	placement_bar.show()
	refresh_placement()

const MOVE_FEATURE := "moveBuilding"

func move_supported() -> bool:
	return MOVE_FEATURE in state.get("cityFeatures", [])

# Moving a finished building: the same placement mode as a new building, onto a
# free cleared plot inside the wall. Free of charge, no builder, no timer; the
# server keeps the building's level, queues and production.
func start_move(building: Dictionary) -> void:
	if is_v6_server():
		await v6_panels.inspect_instance(str(building.id))
		return
	close_modal()
	action_ring.close()
	if map_name != "city" or not is_instance_valid(stage):
		return
	var plots := []
	for marker in stage.empty_plots:
		if plot_cleared(marker.item):
			plots.append({"position": marker.position, "plot": marker.item, "cleared": true})
	if plots.is_empty():
		message.text = "Нет свободного расчищенного участка внутри стен: расчистите участок."
		return
	var definition := building_definition(building.type)
	var key: String = data.starterHall if building.type == "ECO-05" and int(building.level) == 1 else data.types.get(building.type, "")
	if key.is_empty():
		return
	var asset: Dictionary = data.models[key]
	var origin := Vector3.ZERO
	for marker in stage.place_markers:
		if marker.get("id") == building.id:
			origin = marker.position - Vector3.UP * 5.0
	var first: Dictionary = plots[0]
	for entry in plots:
		if entry.position.distance_squared_to(origin) < first.position.distance_squared_to(origin):
			first = entry
	stage.show_placement(asset.path, float(asset.scale) * (1 + 0.055 * (int(building.level) - 1)), plots)
	placing = {"definition": definition, "move": building, "plots": plots, "plot": first.plot, "position": first.position,
		"cleared": true, "free": first.position, "lifted": false}
	stage.target = first.position
	stage.zoom = minf(stage.zoom, 58.0)
	ensure_placement_bar()
	placement_title.text = "Перенос: %s" % building_title(building.type)
	placement_bar.show()
	refresh_placement()

func ensure_placement_bar() -> void:
	if is_instance_valid(placement_bar):
		return
	placement_bar = PanelContainer.new()
	placement_bar.name = "PlacementBar"
	placement_bar.add_theme_stylebox_override("panel", WebPanels.gradient_style(Color("#353c43ee"), Color("#16191ce8"), WebPanels.GOLD, 9, 12))
	placement_bar.mouse_filter = Control.MOUSE_FILTER_STOP
	modal.get_parent().add_child(placement_bar)
	modal.get_parent().move_child(placement_bar, dimmer.get_index())
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 5)
	placement_bar.add_child(column)
	placement_title = Label.new()
	placement_title.add_theme_font_override("font", TITLE_FONT)
	placement_title.add_theme_font_size_override("font_size", 21)
	placement_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(placement_title)
	placement_info = Label.new()
	placement_info.add_theme_font_size_override("font_size", 14)
	placement_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	placement_info.add_theme_color_override("font_color", Color("#e8dcc4"))
	column.add_child(placement_info)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 8)
	column.add_child(actions)
	var cancel := button(actions, "Отмена", cancel_placement)
	cancel.name = "PlacementCancel"
	cancel.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
	cancel.custom_minimum_size = Vector2(128, 50)
	WebPanels.primary(cancel, true)
	placement_confirm = button(actions, "Построить", confirm_placement)
	placement_confirm.name = "PlacementConfirm"
	placement_confirm.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
	placement_confirm.custom_minimum_size = Vector2(170, 50)
	WebPanels.primary(placement_confirm)

func refresh_placement() -> void:
	if placing.is_empty():
		return
	if placing.has("move"):
		refresh_move()
		return
	var definition: Dictionary = placing.definition
	var terms: Dictionary = data.buildingTerms.get(definition.id, {"cost": {}, "seconds": 0})
	var snapped: bool = placing.position.distance_to(placing.free) < 0.01
	var plate := "none"
	if snapped:
		plate = "ready" if placing.cleared else "forest"
	stage.move_placement(placing.free, plate, placing.lifted)
	var busy_builder: bool = not builder_ready()
	if not snapped:
		placement_info.text = "Отпустите здание над свободным участком"
	elif busy_builder:
		placement_info.text = "%s: дождитесь завершения" % workers_busy_text()
	elif not placing.cleared:
		placement_info.text = "Участок в лесу: сначала расчистка · 15 еды"
	else:
		placement_info.text = "%s · %s — перетащите пальцем, чтобы выбрать место" % [cost_label(terms.cost), duration_label(int(terms.seconds))]
	placement_confirm.text = "Построить" if placing.cleared else "Расчистить"
	var affordable: bool = can_afford(terms.cost) if placing.cleared else balance("food") >= 15
	placement_confirm.disabled = not snapped or busy_builder or not affordable or player_id.is_empty() or command_in_progress

func refresh_move() -> void:
	var building: Dictionary = placing.move
	var snapped: bool = placing.position.distance_to(placing.free) < 0.01
	stage.move_placement(placing.free, "ready" if snapped else "none", placing.lifted)
	var building_busy: bool = not building_order(str(building.id)).is_empty()
	if not snapped:
		placement_info.text = "Отпустите здание над свободным участком"
	elif building_busy:
		placement_info.text = "Здание строится: перенос после завершения"
	elif not move_supported():
		placement_info.text = "Перенос заработает после обновления сервера"
	else:
		placement_info.text = "Бесплатно · уровень и очереди сохранятся — перетащите пальцем"
	placement_confirm.text = "Переместить"
	placement_confirm.disabled = not snapped or building_busy or not move_supported() or player_id.is_empty() or command_in_progress

func move_order(building: Dictionary, plot_id: String) -> Dictionary:
	if legacy_city():
		return {"kind": "legacyBuilding", "action": "move", "buildingId": building.id, "plotId": plot_id}
	return {"kind": "kingdom", "action": "move", "buildingId": building.id, "plotId": plot_id}

func update_placement_bar() -> void:
	if placing.is_empty() or not is_instance_valid(stage):
		return
	placement_bar.visible = not modal.visible
	var anchor: Vector3 = placing.free
	var screen := stage.camera.unproject_position(anchor)
	var view := get_viewport().get_visible_rect().size
	var bar_size := placement_bar.get_combined_minimum_size()
	placement_bar.size = bar_size
	var at := screen + Vector2(-bar_size.x * 0.5, 64)
	if at.y + bar_size.y > view.y - 110:
		at.y = screen.y - bar_size.y - 150
	placement_bar.position = Vector2(clampf(at.x, 12, view.x - bar_size.x - 12), clampf(at.y, 70, view.y - bar_size.y - 12))

func cancel_placement() -> void:
	if v6_panels != null and v6_panels.build != null:
		v6_panels.build.cancel_placement()
	if placing.is_empty():
		return
	placing = {}
	placement_finger = -1
	if is_instance_valid(stage):
		stage.clear_placement()
	if is_instance_valid(placement_bar):
		placement_bar.hide()

func nearest_placement_plot(at: Vector3) -> Dictionary:
	var best := {}
	var best_gap := INF
	for entry in placing.get("plots", []):
		var gap: float = Vector2(at.x, at.z).distance_to(Vector2(entry.position.x, entry.position.z))
		if gap < best_gap:
			best_gap = gap
			best = entry
	if best.is_empty():
		return {}
	best = best.duplicate()
	best["gap"] = best_gap
	return best

func placement_screen_point() -> Vector2:
	return stage.camera.unproject_position(placing.free + Vector3.UP * 3.0)

# Finger down near the ghost: the building is picked up instead of the camera.
func try_grab_placement(index: int, at: Vector2) -> bool:
	if placing.is_empty() or placement_finger != -1 or not fingers.is_empty():
		return false
	var anchor := placement_screen_point()
	if at.distance_to(anchor) > PLACEMENT_GRAB_RADIUS:
		return false
	placement_finger = index
	placement_grab_offset = anchor - at
	placing.lifted = true
	refresh_placement()
	return true

func drag_placement(at: Vector2) -> void:
	var ground := stage.ground_at(at + placement_grab_offset)
	ground.y = stage.sample_city(ground.x, ground.z)
	var near := nearest_placement_plot(ground)
	if not near.is_empty() and near.gap <= PLACEMENT_SNAP:
		placing.free = near.position
		placing.position = near.position
		placing.plot = near.plot
		placing.cleared = near.cleared
	else:
		placing.free = ground
		placing.position = Vector3.INF
	# Near a screen edge the view follows the finger.
	var view := get_viewport().get_visible_rect().size
	var push := Vector2.ZERO
	if at.x < PLACEMENT_EDGE: push.x = -1
	elif at.x > view.x - PLACEMENT_EDGE: push.x = 1
	if at.y < PLACEMENT_EDGE + 40: push.y = -1
	elif at.y > view.y - PLACEMENT_EDGE: push.y = 1
	placing["edge"] = push
	refresh_placement()

func release_placement(at: Vector2) -> void:
	placement_finger = -1
	placing.lifted = false
	placing.erase("edge")
	if placing.position == Vector3.INF:
		var ground := stage.ground_at(at + placement_grab_offset)
		var near := nearest_placement_plot(ground)
		if not near.is_empty():
			placing.free = near.position
			placing.position = near.position
			placing.plot = near.plot
			placing.cleared = near.cleared
	refresh_placement()

func tap_placement(at: Vector2) -> void:
	var ground := stage.ground_at(at)
	var near := nearest_placement_plot(ground)
	if not near.is_empty() and near.gap <= 14.0:
		placing.free = near.position
		placing.position = near.position
		placing.plot = near.plot
		placing.cleared = near.cleared
		refresh_placement()

func confirm_placement() -> void:
	if placing.is_empty() or placement_confirm.disabled:
		return
	var definition: Dictionary = placing.definition
	var plot: Dictionary = placing.plot
	var position: Vector3 = placing.position
	if placing.has("move"):
		var building: Dictionary = placing.move
		cancel_placement()
		stage.target = position
		if await command(move_order(building, plot.id)):
			message.text = "Здание перенесено: %s" % building_title(building.type)
		return
	var order := build_order(plot.id, definition.id) if placing.cleared else \
		{"kind":"kingdom","action":"clear","plotId":plot.id}
	# Instant: the placement closes, builders start on the plot at once and the
	# server confirms in the background (a refusal is reported and undone).
	cancel_placement()
	stage.target = position
	var done := await command(order)
	if done:
		message.text = "Строительство началось: %s" % definition.ru if order.action == "build" else "Участок расчищается — затем здесь можно строить"

func free_build_plot() -> Dictionary:
	var kingdom: Variant = state.city.get("kingdom")
	var best := {}
	var best_gap := INF
	var hall := stage.target
	for marker in stage.empty_plots:
		var plot: Dictionary = marker.item
		var cleared: bool = not kingdom is Dictionary or plot.id in kingdom.get("clearedPlots", []) or plot.id.begins_with("site-")
		var gap: float = hall.distance_squared_to(marker.position) + (0.0 if cleared else 1.0e9)
		if gap < best_gap:
			best_gap = gap
			best = {"plot": plot, "position": marker.position, "cleared": cleared}
	return best

func show_build_details(definition: Dictionary) -> void:
	var option := build_option(definition)
	open_modal(definition.ru, "wide", "ДРЕНОВАР · ЗОДЧИЙ")
	var layout := HBoxContainer.new()
	layout.add_theme_constant_override("separation", 14)
	modal_body.add_child(layout)
	var art_panel := panel(8)
	art_panel.add_theme_stylebox_override("panel", WebPanels.gradient_style(Color("#3d4c45"), Color("#141b19"), WebPanels.BRASS, 8))
	art_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	layout.add_child(art_panel)
	var art := TextureRect.new()
	art.texture = building_card(definition.id)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.custom_minimum_size = Vector2(0, 240)
	art_panel.add_child(art)
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	layout.add_child(info)
	row(info, "Назначение · %s" % definition.get("function", ""))
	var metrics: Dictionary = data.buildingTerms.get(definition.id, {})
	if metrics.get("production") != null:
		row(info, "Производство · +%d/мин" % int(metrics.rates[0]))
	var cost_plate := PanelContainer.new()
	cost_plate.add_theme_stylebox_override("panel", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(30, 8, 30, 8)))
	info.add_child(cost_plate)
	var cost_row := HBoxContainer.new()
	cost_row.alignment = BoxContainer.ALIGNMENT_CENTER
	cost_row.add_theme_constant_override("separation", 18)
	cost_plate.add_child(cost_row)
	fill_cost_row(cost_row, option.terms.cost)
	row(info, "Время · %d сек." % int(option.terms.seconds))
	var worker_free := builder_ready()
	var site := free_build_plot()
	var reason := ""
	match option.state:
		"built": reason = built_reason(definition)
		"locked": reason = "Нужна ратуша %d-го уровня." % option.required
		"short": reason = "Недостаточно ресурсов."
	if reason.is_empty() and not worker_free:
		reason = "%s: дождитесь завершения." % workers_busy_text()
	if reason.is_empty() and site.is_empty():
		reason = "Нет свободного участка: сруби дерево и подготовь место."
	if reason.is_empty() and not site.cleared:
		reason = "Ближайший участок в лесу: сначала его нужно расчистить."
	if not reason.is_empty():
		var why := Label.new()
		why.text = reason
		why.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		why.add_theme_color_override("font_color", UiKit.WARN)
		info.add_child(why)
	var can_build: bool = reason.is_empty() and not player_id.is_empty()
	var placeable: bool = option.state == "ready" and worker_free and not site.is_empty()
	var build := panel_action(info, "Выбрать место", start_placement.bind(definition), placeable)
	build.name = "BuildConfirm"
	if can_build:
		button(info, "Построить на ближайшем участке", func():
			stage.target = site.position
			command(build_order(site.plot.id, definition.id)))
	if not site.is_empty() and not site.cleared and option.state == "ready" and worker_free:
		button(info, "Расчистить участок · 15 еды", command.bind({"kind":"kingdom","action":"clear","plotId":site.plot.id}),
			not player_id.is_empty() and balance("food") >= 15)
	if not site.is_empty():
		button(info, "Показать участок", focus_build_plot.bind(site.plot, site.position))
	modal_footer.show()
	button(modal_footer, "← Все здания", show_build_menu.bind(build_group))

func show_construction() -> void:
	if is_v6_server():
		await v6_panels.catalog()
		return
	open_modal("Строительство", "right")
	for order in construction_orders():
		countdown({"clear":"Расчистка", "build":"Строительство", "upgrade":"Улучшение"}.get(order.kind, "Заказ"), order.endsAt)
		button(modal_body, "Подробнее о заказе", inspect_construction_order.bind(order))
	if not builder_ready():
		add_workers_note(modal_body)
	var plots: Array[Dictionary] = stage.empty_plots.duplicate()
	var center := stage.target
	plots.sort_custom(func(a, b): return center.distance_squared_to(a.position) < center.distance_squared_to(b.position))
	for marker in plots:
		var plot: Dictionary = marker.item
		var kingdom: Variant = state.city.get("kingdom")
		var cleared: bool = not kingdom is Dictionary or plot.id in kingdom.get("clearedPlots", []) or plot.id.begins_with("site-")
		var title := "%d : %d · %s" % [roundi(marker.position.x), roundi(marker.position.z), "расчищен" if cleared else "лес"]
		button(modal_body, title, focus_build_plot.bind(plot, marker.position))
	if plots.is_empty():
		row(modal_body, "Подготовь новый участок после вырубки дерева.")

func focus_build_plot(plot: Dictionary, position: Vector3) -> void:
	stage.target = position
	stage.zoom = minf(stage.zoom, 45.0)
	inspect_plot(plot)

func inspect_construction_order(order: Dictionary) -> void:
	if is_v6_server():
		await v6_panels.queues()
		return
	open_modal(building_title(order.type) if order.has("type") else "Расчистка участка")
	var title: String = {"clear":"Расчистка", "build":"Строительство", "upgrade":"Улучшение"}.get(order.kind, "Заказ")
	countdown(title, order.endsAt)
	if order.kind != "clear":
		button(modal_body, "Ускорить", show_speedups.bind("construction", order, ""))
	button(modal_body, "К поселению", show_city_actions)

func show_clearings() -> void:
	open_modal("Расчистка рощ", "right")
	for grove in data.clearings:
		if grove.id in state.city.progress.get("cleared", []):
			row(modal_body, grove.name + " · расчищена")
			continue
		button(modal_body, "%s · уровень %d" % [grove.name, int(grove.level)], func():
			var x := float(grove.x)
			var z := float(grove.z)
			stage.target = Vector3(x, stage.sample_city(x, z), z)
			stage.zoom = minf(stage.zoom, 48.0)
			open_modal(grove.name)
			row(modal_body, "Требуется уровень %d." % int(grove.level))
			var level := hall_level()
			if not state.city.get("kingdom") is Dictionary:
				while level < 25 and int(state.city.progress.get("xp", 0)) >= 25 * level * (level + 1):
					level += 1
			if not builder_ready():
				add_workers_note(modal_body)
			button(modal_body, "Начать расчистку", command.bind({"kind":"resource", "action":"area", "id":grove.id}),
				not player_id.is_empty() and level >= int(grove.level) and builder_ready()))

func show_starter_goals() -> void:
	if is_v6_server():
		v6_panels.objectives()
		return
	open_modal("Первые шаги", "right")
	starter_panel_open = true
	var guide: Dictionary = state.city.kingdom.guide
	var claims: Dictionary = guide.get("starterClaims71", {})
	for index in data.starterGoals.size():
		var goal: Dictionary = data.starterGoals[index]
		if claims.has(goal.id):
			continue
		var ready := false
		match goal.id:
			"wood":
				ready = guide.get("collected", false)
			"train":
				ready = state.city.military.receipts.values().any(func(receipt): return receipt.status == "completed")
			"hall":
				ready = hall_level() >= 2
			"build":
				ready = state.city.buildings.any(func(building): return building_definition(building.type).get("base", building.type) == "RES-02")
			"hunt":
				ready = guide.get("firstHuntWon", false)
		var reward: Dictionary = goal.reward
		var full := reward.keys().any(func(resource): return balance(resource) + int(reward[resource]) > capacity())
		row(modal_body, "Первые шаги · %d/%d" % [index + 1, data.starterGoals.size()])
		row(modal_body, goal.title)
		row(modal_body, "Награда · " + reward_label(reward))
		button(modal_body, "Освободи место на складе" if ready and full else "Получить награду",
			command.bind({"kind":"starter71", "objectiveId":goal.id}, show_starter_goals),
			ready and not full and not player_id.is_empty())
		return
	row(modal_body, "Все стартовые цели выполнены.")

# Speedups. Usable items are exactly the server catalogue (data.speedItems, the same
# as dist/city/upgrade-v1.js speedItems in server v92: construction and training,
# 1, 5, 15 and 60 min) and the count is the server inventory (state.items). Tiers the
# server does not know yet (30 min, 2 h, 5 h, 10 h, every march item) are listed as
# unavailable with the reason; nothing pretends to use them.
const SPEED_QUEUES := {"construction": "Строительство", "training": "Обучение войск", "march": "Марш"}
const SPEED_TIERS := [60, 300, 900, 1800, 3600, 7200, 18000, 36000]
const SPEED_SERVER_PENDING := "Появится после обновления сервера."
var speedup_in_flight := false

# The server's own catalogue when it sends one (speedCatalog, server patch
# speedups-v2), else the v92 catalogue shipped with the game.
func speed_catalog() -> Dictionary:
	var catalog: Variant = state.get("speedCatalog")
	return catalog if catalog is Dictionary and not catalog.is_empty() else data.get("speedItems", {})

func server_speed_items(queue: String) -> Array:
	var catalog := speed_catalog()
	var ids: Array = catalog.keys().filter(func(id): return catalog[id].kind == queue)
	ids.sort_custom(func(a, b): return int(catalog[a].seconds) < int(catalog[b].seconds))
	return ids

static func speed_duration(seconds: int) -> String:
	if seconds >= 3600:
		return "%d ч" % (seconds / 3600)
	return "%d мин" % (seconds / 60)

func show_speedups(queue: String, order: Dictionary, building_id: String) -> void:
	if is_v6_server() and queue in ["construction", "training"]:
		if not await ensure_v6_ready():
			return
		for current: Dictionary in state.v6.orders:
			if current.id == order.get("requestId", order.get("id", "")) and current.status == "pending":
				v6_panels.speedups(current)
				return
		await v6_panels.queues()
		return
	if order.get("predicted", false):
		await wait_for_order(queue, order, building_id)
		return
	open_modal("Ускорение · " + SPEED_QUEUES.get(queue, ""))
	countdown("Осталось", order.endsAt)
	var ids := server_speed_items(queue)
	var known := {}
	var owned_any := false
	for id in ids:
		var duration := int(speed_catalog()[id].seconds)
		known[duration] = true
		var count := int(state.get("items", {}).get(id, 0))
		owned_any = owned_any or count > 0
		var label := "%s · в наличии %d" % [speed_duration(duration), count]
		var use := button(modal_body, label, preview_speedup.bind(queue, order, building_id, id),
			count > 0 and not player_id.is_empty() and not speedup_in_flight)
		# The painted item of its tier (stage 4a), the same art as the V6 window.
		use.icon = UiKit.tex("kit_item_%s_%d" % ["train" if queue == "training" else "build", v6_panels.script_of(V6Panels.VIEW_SCRIPTS.queue_view).tier_of(duration)])
		use.expand_icon = true
		use.add_theme_constant_override("icon_max_width", 44)
		use.custom_minimum_size.y = maxf(use.custom_minimum_size.y, 56)
	if ids.is_empty():
		row(modal_body, "Ускорение этой очереди сервер пока не поддерживает. " + SPEED_SERVER_PENDING)
	elif not owned_any:
		row(modal_body, "Ускорителей для этой очереди нет. Сервер выдаёт их за развитие поселения и обучение войск.")
	var pending: Array = SPEED_TIERS.filter(func(seconds): return not known.has(seconds)).map(speed_duration)
	if not pending.is_empty() and not ids.is_empty():
		row(modal_body, "%s — %s" % [", ".join(pending), SPEED_SERVER_PENDING.to_lower()])

# «Ускорить» right after «Улучшить»: the server's order (its id and end) is needed for
# the speedup, so the window waits for the answer that is already on its way.
func wait_for_order(queue: String, order: Dictionary, building_id: String) -> void:
	open_modal("Ускорение · " + SPEED_QUEUES.get(queue, ""))
	row(modal_body, "Заказ отправлен, получаем его с сервера…")
	var generation := modal_generation
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec() - started < 15000:
		await get_tree().create_timer(0.1).timeout
		if generation != modal_generation:
			return
		var confirmed := building_order(str(order.get("buildingId", "")))
		if not confirmed.is_empty() and not confirmed.get("predicted", false):
			show_speedups(queue, confirmed, building_id)
			return
		if confirmed.is_empty():
			break
	if generation == modal_generation:
		row(modal_body, "Заказ не подтверждён сервером. Попробуй ещё раз через несколько секунд.")

# Before anything is spent: how much the remaining time shrinks.
func preview_speedup(queue: String, order: Dictionary, building_id: String, id: String) -> void:
	var duration := int(speed_catalog()[id].seconds)
	var remaining := float(order.endsAt) - timer_now()
	if remaining <= 0.0:
		show_error({"error":"Таймер уже закончился. Ждём подтверждения сервера."})
		return
	var left := ceili(remaining / 1000.0)
	var after := maxi(0, left - duration)
	open_modal("Применить ускоритель?")
	row(modal_body, "%s · в наличии %d" % [speed_duration(duration), int(state.get("items", {}).get(id, 0))])
	if after > 0:
		row(modal_body, "Осталось %s → станет %s" % [clock_text(left), clock_text(after)])
	else:
		row(modal_body, "Осталось %s → завершится сразу" % clock_text(left))
	var payload := {"kind":"speedup", "queue":queue, "item":id, "buildingId":building_id,
		"orderId":order.id if queue != "construction" else order.get("requestId", order.get("id", "")),
		"expectedEndsAt":order.endsAt, "confirmUnused":false}
	if queue == "march":
		payload.erase("buildingId")
		payload.erase("orderId")
		payload.armyId = order.id
	if duration > left:
		row(modal_body, "Неиспользованные %s пропадут." % clock_text(duration - left))
		payload.confirmUnused = true
	var apply := button(modal_body, "Применить", Callable())
	apply.pressed.connect(func(): apply_speedup(apply, payload))
	button(modal_body, "Назад", show_speedups.bind(queue, order, building_id))

# One press spends one item and works at once: the timer moves by the same rule as
# the server's (the order ends earlier by the item's time, never before now; an
# upgrade that ends now takes its new level at once), the window closes, and the
# server confirms in the background. A second speedup cannot be sent while the
# first is in flight, a lost answer is repeated with the same idempotency key (the
# server never applies it twice), and expectedEndsAt makes the server refuse any
# other copy once the timer has moved. Answers to polls sent before the server
# applied it keep the local result (speed_overrides); a refusal brings the server's
# timer back.
var speed_overrides: Array = []

func apply_speedup(apply: Button, payload: Dictionary) -> void:
	if speedup_in_flight:
		return
	speedup_in_flight = true
	apply.disabled = true
	var entry := {"payload": payload, "count": int(state.get("items", {}).get(payload.item, 0))}
	speed_overrides.append(entry)
	var changed := apply_speed_override(entry)
	if changed:
		after_local_change()
	close_modal()
	message.text = "Ускорение применено"
	var ok := await command(payload)
	speed_overrides.erase(entry)
	speedup_in_flight = false
	if not ok:
		message.text = "Ускорение не применено: " + last_command_error
		if changed:
			# The local timer goes: the server's state comes back at once.
			poll_account_state(true)

# The speedup on the current state, if the server has not applied it yet there
# (the order still ends at expectedEndsAt). Returns whether anything changed.
func apply_speed_override(entry: Dictionary) -> bool:
	var payload: Dictionary = entry.payload
	var shift_ms := float(speed_catalog().get(payload.item, {}).get("seconds", 0)) * 1000.0
	var now := timer_now()
	var expected := float(payload.get("expectedEndsAt", 0.0))
	var applied := false
	if payload.queue == "construction":
		var construction: Variant = state.city.get("kingdom", state.city.get("legacyUpgrades"))
		if not construction is Dictionary:
			return false
		for slot in ["order", "order2"]:
			var order: Variant = construction.get(slot)
			if not order is Dictionary or str(order.get("requestId", "")) != str(payload.get("orderId", "")) or float(order.endsAt) != expected:
				continue
			var ends := maxf(now, expected - shift_ms)
			if ends <= now and order.get("kind", "") == "upgrade":
				# Done now: the building takes its new level at once.
				for building in state.city.buildings:
					if str(building.id) == str(order.get("buildingId", "")):
						building.level = int(order.get("level", int(building.level) + 1))
				if slot == "order2":
					construction.erase("order2")
				else:
					construction.order = construction.get("order2")
					construction.erase("order2")
			else:
				order.endsAt = ends
			applied = true
			break
	elif payload.queue == "training":
		var queue: Array = state.city.get("military", {}).get("queues", {}).get(str(payload.get("buildingId", "")), [])
		if not queue.is_empty() and str(queue[0].get("id", "")) == str(payload.get("orderId", "")) and float(queue[0].endsAt) == expected:
			var shift := minf(shift_ms, maxf(0.0, expected - now))
			queue[0].endsAt = expected - shift
			for k in range(1, queue.size()):
				queue[k].startsAt = float(queue[k].startsAt) - shift
				queue[k].endsAt = float(queue[k].endsAt) - shift
			applied = true
	if applied:
		var items: Dictionary = state.get("items", {})
		if int(items.get(payload.item, 0)) == int(entry.count):
			items[payload.item] = maxi(0, int(entry.count) - 1)
	return applied

# Local changes made before the server's answer: redraw the stores and the city.
func after_local_change() -> void:
	refresh_hud()
	if is_instance_valid(stage) and map_name == "city":
		stage.present(state)

func march_finish(army: Dictionary) -> Variant:
	return army.get("returnsAt") if army.status == "returning" else (army.get("battleEndsAt") if army.status == "fighting" else army.get("arrivesAt"))

func show_march_speedups(army: Dictionary) -> void:
	var finish: Variant = march_finish(army)
	if finish == null:
		return
	show_speedups("march", {"id": army.id, "endsAt": float(finish)}, "")

func show_trade(resource := "") -> void:
	if is_v6_server():
		v6_panels.trade()
		return
	open_modal("Рынок", "right")
	var resources := OptionButton.new()
	var keys: Array = data.tradePrices.keys()
	for key in keys:
		resources.add_item(RESOURCE_NAMES[key])
	if keys.has(resource):
		resources.select(keys.find(resource))
	modal_body.add_child(resources)
	var direction := OptionButton.new()
	direction.add_item("Купить за монеты")
	direction.add_item("Продать за монеты")
	modal_body.add_child(direction)
	var amount := SpinBox.new()
	amount.min_value = 1
	amount.max_value = 1000
	amount.update_on_text_changed = true
	modal_body.add_child(amount)
	var quote := Label.new()
	modal_body.add_child(quote)
	var submit := button(modal_body, "Обменять", func():
		amount.apply()
		command({"kind":"trade", "resource":keys[resources.selected],
			"direction":"buy" if direction.selected == 0 else "sell", "quantity":int(amount.value)}))
	var update := func(_value: float):
		var key: String = keys[resources.selected]
		var coins := int(data.tradePrices[key]) * int(amount.value)
		var buying := direction.selected == 0
		var give := "coins" if buying else key
		var take := key if buying else "coins"
		var debit := coins if buying else int(amount.value)
		var credit := int(amount.value) if buying else coins
		quote.text = "%s −%d · %s +%d" % [RESOURCE_NAMES[give], debit, RESOURCE_NAMES[take], credit]
		submit.disabled = balance(give) < debit or balance(take) + credit > capacity()
	resources.item_selected.connect(update)
	direction.item_selected.connect(update)
	amount.value_changed.connect(update)
	update.call(0)

func total_units(units: Dictionary) -> int:
	var count := 0
	for value in units.values():
		count += int(value)
	return count

func show_hospital() -> void:
	if is_v6_server():
		v6_panels.services("B16")
		return
	open_modal("Лазарет", "right")
	for order in state.get("healing", []):
		countdown("Лечатся · %d" % total_units(order.units), order.endsAt)
	var inputs := {}
	for unit in data.englishRoster:
		var count := int(state.get("wounded", {}).get(unit.id, 0))
		if count > 0:
			inputs[unit.id] = unit_quantity("%s · %d" % [unit.name, count], mini(count, march_limit()))
	if inputs.is_empty():
		row(modal_body, "Нет раненых, ожидающих лечения.")
		return
	var hospital_index: int = state.city.buildings.find_custom(func(building): return building_definition(building.type).get("base") == "SUP-01")
	if hospital_index < 0:
		row(modal_body, "Для лечения нужен лазарет. Он открывается при ратуше III.")
		button(modal_body, "Открыть строительство", open_construction)
		return
	var hospital: Dictionary = state.city.buildings[hospital_index]
	button(modal_body, "Лечить выбранных", func():
		var units := {}
		for id in inputs:
			inputs[id].apply()
			if inputs[id].value > 0:
				units[id] = int(inputs[id].value)
		var count := total_units(units)
		if count < 1 or count > march_limit():
			show_error({"error":"Превышен размер похода: %d мест." % march_limit()})
			return
		open_modal("Подтвердить лечение")
		var cost := {"food":count * 5, "coins":count * 2}
		if state.city.demo.get("unlimitedResources", false):
			cost = {}
		var reduction := clampi(int(hospital.level) - 1, 0, 4) * 8 if state.city.get("kingdom", state.city.get("legacyUpgrades")) is Dictionary else 0
		row(modal_body, "%d воинов · %s · %.0f сек." % [count, cost_label(cost), count * 10.0 * (1.0 - reduction / 100.0)])
		button(modal_body, "Начать лечение", command.bind({"kind":"heal", "units":units}), can_afford(cost))
		button(modal_body, "Назад", show_hospital))

func unit_quantity(title: String, limit: int) -> SpinBox:
	var line := HBoxContainer.new()
	modal_body.add_child(line)
	var label := Label.new()
	label.text = title
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_child(label)
	var quantity := SpinBox.new()
	quantity.max_value = limit
	line.add_child(quantity)
	return quantity

func show_armies() -> void:
	if is_v6_server():
		v6_panels.army()
		return
	open_modal("Армия наготове", "garrison", "ГАРНИЗОН DRENOVAR")
	row(modal_body, "Свободны · %d    Ранены · %d" % [total_units(state.get("healthy", {})), total_units(state.get("wounded", {}))])
	panel_action(modal_body, "Найм", func():
		var buildings := recruitment_buildings()
		if buildings.is_empty():
			show_training_buildings()
		else:
			open_recruitment(buildings[0]))
	button(modal_body, "Ступени армии", show_military_cultures)
	button(modal_body, "Показать плац в городе", open_parade)
	button(modal_body, "Раненые и лечение", show_hospital)
	for army in state.get("armies", []) + state.world.armies:
		if army.status == "returned" or army.get("owner", player_id) != player_id:
			continue
		var title: String = army.get("name", "Городской отряд")
		button(modal_body, "Показать · " + title, focus_army.bind(army))
		match army.status:
			"outbound":
				countdown(title + " · в пути", army.arrivesAt)
				button(modal_body, "Ускорить марш", show_march_speedups.bind(army))
				if not army.has("worldKind"):
					button(modal_body, "Отозвать отряд", command.bind({"kind":"recall", "armyId":army.id}))
			"fighting":
				countdown(title + " · бой", army.battleEndsAt)
			"returning":
				countdown(title + " · возвращается", army.returnsAt)
				button(modal_body, "Ускорить возвращение", show_march_speedups.bind(army))
	for unit in data.englishRoster:
		var available := int(state.get("healthy", {}).get(unit.id, 0))
		if available > 0:
			var entry := HBoxContainer.new()
			modal_body.add_child(entry)
			unit_art(entry, unit.id, Vector2(48, 60), true)
			var details := button(entry, "%s · %d" % [unit.name, available], show_garrison_unit.bind(unit, available))
			details.size_flags_horizontal = Control.SIZE_EXPAND_FILL

func show_garrison_unit(unit: Dictionary, available: int) -> void:
	open_modal(unit.name)
	row(modal_body, "%s · в строю %d · общая мощь %d" % [unit.unit_class, available, available * int(unit.power)])
	var amount := unit_quantity("Распустить воинов", available)
	amount.min_value = 1
	button(modal_body, "Распустить", func():
		amount.apply()
		var count := int(amount.value)
		open_modal("Подтвердить роспуск", "garrison", "ГАРНИЗОН DRENOVAR")
		row(modal_body, "%s · %d" % [unit.name, count])
		panel_action(modal_body, "Подтвердить роспуск", command.bind({"kind":"dismiss", "unitId":unit.id, "quantity":count}), true, true)
		button(modal_body, "Назад", show_armies))

func show_military_cultures() -> void:
	open_modal("Ступени армии", "garrison", "ДРЕНОВАР · ОРУЖЕЙНАЯ")
	for culture in data.militaryCultures:
		var title := "%s · %s" % [culture.roman, culture.name]
		if culture.get("available", false):
			button(modal_body, title, show_training_buildings)
		else:
			row(modal_body, title + " · закрыто")
	button(modal_body, "К армии", show_armies)

func show_training_buildings() -> void:
	if is_v6_server():
		v6_panels.catalog()
		return
	open_modal("Военные здания")
	button(modal_body, "I · Англия", show_military_cultures)
	for type in ["MIL-01", "MIL-02", "MIL-03"]:
		var index: int = state.city.buildings.find_custom(func(building): return building_definition(building.type).get("base") == type)
		if index >= 0:
			var building: Dictionary = state.city.buildings[index]
			button(modal_body, "%s · ур. %d" % [building_title(building.type), int(building.level)], open_recruitment.bind(building))
		else:
			row(modal_body, "%s · нужно построить · ратуша %d" % [building_title(type), int(data.unlockLevels[type])])
	button(modal_body, "Открыть строительство", open_construction)
	button(modal_body, "К армии", show_armies)

func open_parade() -> void:
	await show_scene("city")
	if map_name == "city":
		focus_parade()

func open_construction() -> void:
	await show_scene("city")
	if map_name == "city":
		show_construction()

func empty(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()

func refresh_hud() -> void:
	if resource_buttons.is_empty():
		return
	for id in RESOURCE_NAMES:
		var value := balance(id)
		resource_amounts[id].text = short_amount(value)
		resource_buttons[id].tooltip_text = "%s · %s" % [RESOURCE_NAMES[id], format_balance(value)]
		resource_buttons[id].accessibility_name = resource_buttons[id].tooltip_text
	refresh_modal_wallet()
	refresh_hud_badges()
	if not connected():
		message.text = ""
	elif v6_panels.enabled():
		var incoming: Array = state.v6.get("warnings", [])
		if not incoming.is_empty():
			var eta: int = int(incoming[0].eta_seconds)
			for warning: Dictionary in incoming:
				eta = mini(eta, int(warning.eta_seconds))
			message.text = "Башня: нападение через %d с" % eta
		elif message.text.begins_with("Башня:"):
			message.text = ""

func show_scene(scene_name: String) -> void:
	if scene_loading:
		return
	if is_instance_valid(stage) and scene_name == map_name:
		close_modal()
		return
	scene_loading = true
	diagnostics.log_event("scene", {"action": scene_name, "memory_mb": snappedf(memory_in_use_mb(), 1.0)}, Time.get_unix_time_from_system())
	action_ring.close()
	cancel_placement()
	var started_at := Time.get_ticks_msec()
	followed_army = ""
	close_modal()
	var next: Landscape = scene_cache.get(scene_name)
	last_scene_label = ("город" if scene_name == "city" else "мир") + (", из кэша" if next != null else ", первая загрузка")
	if next == null and prewarm_name == scene_name and not prewarm_cancelled:
		# Prepared in the background: finish the remaining slices at full speed.
		message.text = "Открываем карту…" if scene_name == "world" else "Открываем город…"
		last_scene_label = ("город" if scene_name == "city" else "мир") + ", дозагрузка из фона"
		prewarm_stage.background_gate = Callable()
		await prewarm_finished
		next = scene_cache.get(scene_name)
	elif not prewarm_name.is_empty():
		prewarm_stage.background_gate = Callable()
		await prewarm_finished
		next = scene_cache.get(scene_name)
	if next == null:
		message.text = "Открываем карту…" if scene_name == "world" else "Открываем город…"
		if single_scene:
			release_inactive_scene()
			free_current_scene()
		await get_tree().process_frame
		next = Landscape.new()
		next.set_active(false)
		add_child(next)
		await next.setup(data, state, scene_name, saved_views.get(scene_name, {}))
		scene_cache[scene_name] = next
	if is_instance_valid(stage):
		stage.set_active(false)
	stage = next
	if not stage.fight_started.is_connected(focus_fight):
		stage.fight_started.connect(focus_fight)
	map_name = scene_name
	nav_buttons.city.visible = map_name != "city"
	nav_buttons.world.visible = map_name != "world"
	nav_buttons.build.visible = map_name == "city"
	minimap.visible = map_name == "world"
	frame_index = 0
	frame_count = 0
	motion_index = 0
	motion_count = 0
	last_frame_us = 0
	stage.present(state)
	stage.set_active(true)
	scene_switch_msec = Time.get_ticks_msec()
	scene_loading = false
	last_scene_ms = Time.get_ticks_msec() - started_at
	message.text = ""
	refresh_hud()

func memory_in_use_mb() -> float:
	return (Performance.get_monitor(Performance.MEMORY_STATIC) + Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)) / 1048576.0

# iOS ends an app that crosses its memory limit without a warning first, and the
# engine counters do not include the graphics driver's own memory. Keeping the
# second scene is therefore limited to a share of the device RAM (about 880 MB on
# a 4 GB iPhone) as well as to TWO_SCENE_MEMORY_MB.
var memory_budget_mb := -1.0

func scene_memory_budget() -> float:
	if memory_budget_mb < 0.0:
		var physical := float(OS.get_memory_info().get("physical", -1))
		memory_budget_mb = TWO_SCENE_MEMORY_MB
		if physical > 0.0 and OS.has_feature("mobile"):
			memory_budget_mb = minf(TWO_SCENE_MEMORY_MB, physical / 1048576.0 * 0.22)
	return memory_budget_mb

# On the phone only one scene lives in memory at a time. The device report showed
# the city alone at ~510 MB of video memory with the engine's CPU counter at 0 in
# release builds, so the budget could not see the real footprint; keeping the city
# while the world loaded is what ended the app (last events before each
# unexpected end: scene·world). Switching now frees the old scene first.
var single_scene := OS.has_feature("mobile")

func two_scenes_fit() -> bool:
	if single_scene:
		return false
	return memory_in_use_mb() < scene_memory_budget()

func free_current_scene() -> void:
	if not is_instance_valid(stage):
		return
	saved_views[map_name] = stage.view_state()
	scene_cache.erase(map_name)
	stage.set_active(false)
	if get_viewport().size_changed.is_connected(stage.update_visible_batches):
		get_viewport().size_changed.disconnect(stage.update_visible_batches)
	retired_nodes.append(stage)
	retired_nodes.append_array(stage.find_children("*", "", true, false))
	stage = null
	drain_retired_scenes(true)

func prewarm_may_continue() -> bool:
	return fingers.is_empty() and not dragging and not camera_moving_now and not scene_loading and \
		Time.get_ticks_msec() - last_interaction_msec >= PREWARM_QUIET_MSEC

func maybe_prewarm_other_scene() -> void:
	if smoke or not prewarm_name.is_empty() or scene_loading or not is_instance_valid(stage) or Time.get_ticks_msec() < prewarm_paused_until:
		return
	var other := "world" if map_name == "city" else "city"
	if scene_cache.has(other) or not two_scenes_fit():
		return
	if Time.get_ticks_msec() - maxi(last_interaction_msec, scene_switch_msec) < PREWARM_IDLE_MSEC or not prewarm_may_continue():
		return
	prewarm_scene(other)

func prewarm_scene(scene_name: String) -> void:
	diagnostics.log_event("prewarm", {"action": scene_name, "memory_mb": snappedf(memory_in_use_mb(), 1.0)}, Time.get_unix_time_from_system(), false)
	# Builds the other scene inactive, in small slices, only while the player is idle.
	prewarm_name = scene_name
	prewarm_cancelled = false
	var next := Landscape.new()
	prewarm_stage = next
	next.background_gate = prewarm_may_continue
	next.set_active(false)
	add_child(next)
	await next.setup(data, state, scene_name, saved_views.get(scene_name, {}))
	next.background_gate = Callable()
	if prewarm_cancelled:
		if get_viewport().size_changed.is_connected(next.update_visible_batches):
			get_viewport().size_changed.disconnect(next.update_visible_batches)
		retired_nodes.append(next)
		retired_nodes.append_array(next.find_children("*", "", true, false))
	else:
		scene_cache[scene_name] = next
	prewarm_name = ""
	prewarm_stage = null
	prewarm_finished.emit()

# When one of the player's armies starts fighting near the view, glide the camera
# onto the fight (only if the player is not touching or reading a window).
func focus_fight(army_id: String, position: Vector3) -> void:
	var own: bool = (state.get("armies", []) + state.get("world", {}).get("armies", [])).any(
		func(army): return army.id == army_id and str(army.get("owner", player_id)) == player_id)
	if not own or modal.visible or not fingers.is_empty() or dragging:
		return
	var near: bool = followed_army == army_id or Vector2(position.x - stage.target.x, position.z - stage.target.z).length() < 70.0
	if not near:
		return
	followed_army = ""
	stage.target = position
	# The world map's soldiers are half the city's size (build 1021): its fight is
	# framed closer.
	stage.zoom = minf(stage.zoom, 34.0 if map_name == "city" else 36.0)

func release_inactive_scene() -> void:
	prewarm_paused_until = Time.get_ticks_msec() + 10 * 60 * 1000
	if not prewarm_name.is_empty():
		prewarm_cancelled = true
	for name in scene_cache.keys():
		var cached: Landscape = scene_cache[name]
		if cached == stage:
			continue
		saved_views[name] = cached.view_state()
		scene_cache.erase(name)
		cached.set_active(false)
		if get_viewport().size_changed.is_connected(cached.update_visible_batches):
			get_viewport().size_changed.disconnect(cached.update_visible_batches)
		# Free leaves before parents in small batches, avoiding a whole-scene teardown spike.
		retired_nodes.append(cached)
		retired_nodes.append_array(cached.find_children("*", "", true, false))

func drain_retired_scenes(urgent := false) -> void:
	var deadline := Time.get_ticks_usec() + 1000
	var freed := 0
	while not retired_nodes.is_empty() and (urgent or (freed < 48 and Time.get_ticks_usec() < deadline)):
		var node: Node = retired_nodes.pop_back()
		if is_instance_valid(node):
			node.free()
		freed += 1

func _exit_tree() -> void:
	# Window scripts still compiling on a worker thread (v6_panels.warm_views) finish first.
	v6_panels.finish_warm()

func _notification(what: int) -> void:
	if combat_diagnostics != null:
		if what == NOTIFICATION_APPLICATION_PAUSED or what == NOTIFICATION_APPLICATION_FOCUS_OUT:
			combat_diagnostics.note("app_background")
		elif what == NOTIFICATION_APPLICATION_RESUMED or what == NOTIFICATION_APPLICATION_FOCUS_IN:
			combat_diagnostics.note("app_foreground")
		elif what == NOTIFICATION_OS_MEMORY_WARNING:
			combat_diagnostics.note("memory_warning")
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		diagnostics.set_state("exited", Time.get_unix_time_from_system())
	elif what == NOTIFICATION_APPLICATION_RESUMED or what == NOTIFICATION_APPLICATION_FOCUS_IN:
		diagnostics.set_state("foreground", Time.get_unix_time_from_system())
		on_app_resumed()
	if what == NOTIFICATION_OS_MEMORY_WARNING:
		diagnostics.log_event("memory_warning", {"memory_mb": snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1),
			"scenes": scene_cache.size()}, Time.get_unix_time_from_system())
		release_inactive_scene()
		drain_retired_scenes(true)
	elif what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_APPLICATION_PAUSED:
		diagnostics.set_state("background", Time.get_unix_time_from_system())
		if what == NOTIFICATION_APPLICATION_PAUSED and paused_at_msec < 0:
			paused_at_msec = Time.get_ticks_msec()
		if state_save_pending:
			remember_state(true)
		last_frame_us = 0
		if is_instance_valid(modal_scroll):
			modal_scroll.cancel_touch()
		reset_gestures()

func zoom_scene(amount: float) -> void:
	if is_instance_valid(stage) and not scene_loading:
		stage.change_zoom(amount)

func reset_gestures() -> void:
	drag_samples.clear()
	fling_velocity = Vector2.ZERO
	fingers.clear()
	last_pinch = 0.0
	pinch_center = Vector2.ZERO
	tap_candidate = false
	dragging = false
	pointer_distance = 0
	if placement_finger != -1:
		placement_finger = -1
		if not placing.is_empty():
			release_placement(placement_screen_point())

func close_modal() -> void:
	result_open = false
	modal_scroll.set_modal_active(false)
	economy_rows.clear()
	economy_source_label = null
	starter_panel_open = false
	if relocation_pins.visible:
		message.text = ""
	relocation_pins.hide()
	modal_generation += 1
	reset_gestures()
	last_frame_us = 0
	if is_instance_valid(stage):
		stage.clear_route()
	if dialog_tween != null:
		dialog_tween.kill()
	dimmer.hide()
	modal.hide()
	cover_city(false)
	city_backdrop.close()
	modal.scale = Vector2.ONE
	modal.modulate.a = 1.0
	empty(modal_body)
	empty(modal_tools)
	empty(modal_footer)
	empty(modal_hero)

func show_world_overview() -> void:
	if scene_loading or map_name != "world":
		return
	close_modal()
	followed_army = ""
	stage.fit_world()

func focus_minimap(location: Vector2) -> void:
	if scene_loading or map_name != "world":
		return
	close_modal()
	followed_army = ""
	stage.target = Vector3(location.x, 1.0, location.y)
	stage.zoom = minf(stage.zoom, 110.0)

func focus_parade() -> void:
	close_modal()
	followed_army = ""
	stage.target = stage.parade_center
	stage.zoom = 32.0

func center_city() -> void:
	close_modal()
	followed_army = ""
	for marker in stage.place_markers:
		if building_definition(marker.item.type).get("base") == "ECO-05":
			stage.target = marker.position
			stage.zoom = 64.0
			return

func rotate_world() -> void:
	if map_name == "world" and not scene_loading:
		stage.world_yaw = wrapf(stage.world_yaw + PI / 4.0, -PI, PI)

func show_map_options() -> void:
	v6_panels.world_view.map_options()

func show_world_directory() -> void:
	v6_panels.world_view.directory()

func show_world_cities() -> void:
	v6_panels.world_view.cities()

func show_world_marches() -> void:
	v6_panels.world_view.marches()

func show_environment_catalog(category_index := 0) -> void:
	open_modal("Окружение мира", "right")
	if environment_atlas == null:
		environment_atlas = load(data.environmentAtlas)
	var categories := ["Все объекты", "Деревья", "Растения", "Скалы и камни", "Ландшафт", "Ресурсы",
		"Вода", "Постройки", "Мелкие детали", "Животные"]
	var groups := [[], [1, 2, 3], [4], [5, 6, 7], [8], [9], [10], [11], [12], [13]]
	var filter := OptionButton.new()
	for category in categories:
		filter.add_item(category)
	filter.select(category_index)
	modal_body.add_child(filter)
	filter.item_selected.connect(show_environment_catalog)
	var grid := GridContainer.new()
	grid.columns = 4
	modal_body.add_child(grid)
	var generation := modal_generation
	var made := 0
	for entry in data.atlasData.assets:
		var group := int(String(entry.category).get_slice("_", 0))
		if category_index > 0 and group not in groups[category_index]:
			continue
		# Fill the grid progressively: the first cards appear at once, the rest
		# over the next frames, so opening never builds every card in one frame.
		if made > 0 and made % 24 == 0:
			await get_tree().process_frame
			if generation != modal_generation or not is_instance_valid(grid):
				return
		made += 1
		var thumbnail := AtlasTexture.new()
		thumbnail.atlas = environment_atlas
		thumbnail.filter_clip = true
		var index := int(entry.index)
		var columns := int(data.atlasData.columns)
		var tile := environment_atlas.get_size() / Vector2(columns, int(data.atlasData.rows))
		thumbnail.region = Rect2(Vector2(index % columns, floori(float(index) / columns)) * tile, tile)
		var item := button(grid, entry.name, focus_environment.bind(entry, category_index))
		item.icon = thumbnail
		item.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
		item.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		item.expand_icon = true
		item.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		item.custom_minimum_size = Vector2(118, 94)
		item.tooltip_text = entry.name
	if generation == modal_generation:
		button(modal_body, "К общему миру", show_world_directory)

func focus_environment(entry: Dictionary, category_index: int) -> void:
	var index: int = data.environment.find_custom(func(item): return item.id == entry.id)
	open_modal(entry.name)
	if index >= 0:
		var item: Dictionary = data.environment[index]
		var spec: Dictionary = data.environmentModels[item.id]
		stage.resource_layer = stage.resource_layer or spec.resource
		stage.detail_layer = stage.detail_layer or spec.detail
		followed_army = ""
		stage.target = stage.point(item)
		stage.zoom = 47.0
		stage.update_visible_batches()
		row(modal_body, "Координаты · %d : %d" % [roundi(item.x + 150), roundi(item.z + 120)])
		button(modal_body, "Рассмотреть на карте", close_modal)
	else:
		row(modal_body, "У этого объекта нет размещения на карте.")
	button(modal_body, "К окружению", show_environment_catalog.bind(category_index))

func focus_own_city() -> void:
	for city in state.world.cities:
		if city.id == state.playerId:
			focus_minimap(Vector2(city.position.x, city.position.z))
			return

func focus_army(army: Dictionary) -> void:
	var scene_name := "world" if army.has("worldKind") else "city"
	await show_scene(scene_name)
	if map_name != scene_name:
		return
	close_modal()
	followed_army = army.id
	stage.target = stage.ground_point(stage.point(army.position))
	stage.zoom = 66.0 if scene_name == "world" else 42.0

func inspect_current_encounter(id: String) -> void:
	var encounters: Array = state.get("encounters", []) if map_name == "city" else state.world.encounters
	for encounter in encounters:
		if encounter.id == id:
			inspect_encounter(encounter)
			return

func building_title(type: String) -> String:
	return building_definition(type).get("ru", type)

func building_definition(type: String) -> Dictionary:
	for building in data.buildings:
		if building.id == type:
			return building
	return {}

## Re-reads the display's safe area (rotation, a resized window) and re-lays what depends on it.
func refresh_safe_area() -> void:
	if SafeArea.refresh(get_viewport()):
		apply_safe_area()

## The HUD's frame, the loading plate, the open window and the construction strip follow the safe
## area; the forest row reads SafeArea itself (adventure_hud.gd). With no insets every value is the
## 1022 one.
func apply_safe_area() -> void:
	if hud_outer != null:
		hud_outer.offset_left = SafeArea.left(HUD_MARGIN.x)
		hud_outer.offset_top = SafeArea.top(HUD_MARGIN.y)
		hud_outer.offset_right = -SafeArea.right(HUD_MARGIN.z)
		hud_outer.offset_bottom = -SafeArea.bottom(HUD_MARGIN.w)
	if forest_progress != null:
		var plate: Vector2 = ForestProgress.PLATE_SIZE
		forest_progress.offset_left = SafeArea.left(FOREST_PROGRESS_MARGIN.x)
		forest_progress.offset_right = forest_progress.offset_left + plate.x
		forest_progress.offset_bottom = -SafeArea.bottom(FOREST_PROGRESS_MARGIN.y)
		forest_progress.offset_top = forest_progress.offset_bottom - plate.y
	if modal != null and not modal_layout.is_empty():
		place_modal(modal_layout)
	for strip in get_tree().get_nodes_in_group("safe_area_layout"):
		if strip.has_method("layout"):
			strip.layout()

func place_modal(layout: String) -> void:
	modal_layout = layout
	var anchors := Rect2(0.5, 0.5, 0, 0)
	var offsets := Rect2(-320, -232, 640, 464)
	match layout:
		"full":
			# Full-screen window (premium kit): header band across the screen.
			anchors = Rect2(0, 0, 1, 1)
			offsets = Rect2(0, 0, 0, 0)
		"wide":
			anchors = Rect2(0, 0, 1, 1)
			offsets = Rect2(48, 13, -96, -26)
		"right", "left":
			anchors = Rect2(0.57, 0, 0.43, 1) if layout == "right" else Rect2(0, 0, 0.43, 1)
			offsets = Rect2(14, 74, -62, -102) if layout == "right" else Rect2(48, 74, -62, -102)
		"city_target":
			anchors = Rect2(0, 0, 0.43, 1)
			offsets = Rect2(48, 74, -62, -206)
		"profile":
			anchors = Rect2(0.5, 0, 0, 1)
			offsets = Rect2(-330, 50, 660, -66)
		"garrison":
			anchors = Rect2(0.5, 0, 0, 1)
			offsets = Rect2(-480, 13, 960, -26)
		"result":
			offsets = Rect2(-310, -249, 620, 498)
		"dialog":
			# Confirmations and the pairing code (stage 4b): a small centred window.
			offsets = Rect2(-300, -190, 600, 380)
		"strip":
			# Construction strip (src/build_strip.gd): the whole screen, no panel; the blurred
			# city (city_backdrop) is the window's background.
			anchors = Rect2(0, 0, 1, 1)
			offsets = Rect2(0, 0, 0, 0)
		"sheet":
			# Bottom sheet: the city stays visible above it.
			anchors = Rect2(0, 1, 1, 0)
			offsets = Rect2(40, -396, -80, 388)
	var edges := Vector4(offsets.position.x, offsets.position.y, offsets.end.x, offsets.end.y)
	# Windows docked to a screen edge keep their 1022 gap or the safe area, whichever is larger
	# (1023). Full windows and the strip stay edge to edge: their band and backdrop may run under
	# the notch, their head, close button and content are inset in arrange_modal().
	if layout != "full" and layout != "strip":
		if anchors.position.x == 0.0 and edges.x >= 0.0:
			edges.x = SafeArea.left(edges.x)
		if anchors.position.y == 0.0 and edges.y >= 0.0:
			edges.y = SafeArea.top(edges.y)
		if anchors.end.x == 1.0 and edges.z <= 0.0:
			edges.z = -SafeArea.right(-edges.z)
		if anchors.end.y == 1.0 and edges.w <= 0.0:
			var lift := SafeArea.bottom(-edges.w) + edges.w
			edges.w -= lift
			if anchors.position.y == 1.0:
				edges.y -= lift   # a bottom sheet keeps its height and rises above the home indicator
	modal.anchor_left = anchors.position.x
	modal.anchor_top = anchors.position.y
	modal.anchor_right = anchors.end.x
	modal.anchor_bottom = anchors.end.y
	modal.offset_left = edges.x
	modal.offset_top = edges.y
	modal.offset_right = edges.z
	modal.offset_bottom = edges.w
	arrange_modal()

# Frame, header and content column for the current layout (src/ui_kit.gd).
func arrange_modal() -> void:
	var full := modal_layout == "full"
	var strip := modal_layout == "strip"
	var docked := modal_layout in ["right", "left", "city_target", "sheet"]
	modal_frame.visible = not full and not strip
	# Full windows: the tall two-board band (resources above, a larger title below).
	var band := UiKit.header_tall_style() if full else UiKit.header_style()
	if modal_header.get_theme_stylebox("panel") != band:
		modal_header.add_theme_stylebox_override("panel", band)
	modal_header.custom_minimum_size.y = 92 if full else 62
	var title_size := 40 if full else (32 if modal_layout == "wide" else (23 if docked else 26))
	var top_on := (full or strip) and not result_open
	if modal_top.visible != top_on:
		modal_top.visible = top_on
	modal_crumb.text = modal_eyebrow.text
	modal_crumb_plate.visible = not modal_crumb.text.is_empty()
	modal_eyebrow.visible = not full and not modal_eyebrow.text.is_empty()
	refresh_modal_wallet()
	if modal_title.get_theme_font_size("font_size") != title_size:
		modal_title.add_theme_font_size_override("font_size", title_size)
	var roomy := full or modal_layout in ["wide", "garrison"]
	for art: Control in modal_flourishes:
		art.visible = roomy
	# Centred titles size to their text on wide windows; narrow ones trim with an ellipsis.
	modal_title.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING if roomy else TextServer.OVERRUN_TRIM_ELLIPSIS
	modal_titles.size_flags_horizontal = Control.SIZE_SHRINK_CENTER if roomy else Control.SIZE_EXPAND_FILL
	var view := Vector2(1366, 630)
	if is_inside_tree():
		view = get_viewport().get_visible_rect().size
	var hero_on := full and modal_hero.get_child_count() > 0
	var side := 28 if full else 22
	# Safe area of a full window (1023): the head's ends and the body's ends give way to the notch;
	# the head band keeps its 14 / 10 content margins and its 6 unit spacing, the body its margins.
	var safe := SafeArea.insets if full else Vector4.ZERO
	var head_sep := 6.0
	var head_need := Vector2(maxf(0.0, safe.x - 14.0), maxf(0.0, safe.z - 10.0))
	var body_left := safe.x if hero_on else maxf(0.0, safe.x - side)
	var body_right := maxf(0.0, safe.z - (side + 10 if hero_on else side))
	var spacer_widths := [maxf(0.0, head_need.x - head_sep), maxf(0.0, head_need.y - head_sep), body_left, body_right]
	for index in modal_safe_spacers.size():
		var spacer: Control = modal_safe_spacers[index]
		spacer.custom_minimum_size.x = spacer_widths[index]
		# A head spacer also adds the row's spacing, so it shows only when the inset needs it.
		spacer.visible = (head_need[index] > 0.0) if index < 2 else spacer_widths[index] > 0.0
	if modal_wallet != null:
		# The resource plates stay left of the close medallion when it moves in from the notch
		# (the strip's medallion is 14 units from the edge, a full window's 10 plus the band's 6).
		var strip_need := maxf(0.0, SafeArea.insets.z - 14.0) if strip else 0.0
		modal_wallet.offset_right = -82.0 - head_need.y - strip_need
	modal_hero.visible = hero_on
	modal_hero.custom_minimum_size.x = maxf(0.0, roundf(view.x * modal_hero_share) - body_left) if hero_on else 0.0
	for side_space: Control in modal_side_space:
		side_space.visible = full and not hero_on
	if full and not hero_on:
		var room := view.x - 56.0 - body_left - body_right
		modal_content.size_flags_horizontal = Control.SIZE_FILL
		modal_content.custom_minimum_size.x = room if modal_full_width else minf(900.0, room)
	else:
		modal_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		modal_content.custom_minimum_size.x = 0.0
	# Full windows keep air between the values and the scroll bar on the right.
	# Full windows leave room for the section plate that hangs under the title.
	var crumb_on := full and not modal_eyebrow.text.is_empty()
	# A full window's list ends above the home indicator (its band and backdrop run to the edge).
	var margins := {"margin_left": 8 if hero_on else side, "margin_right": side + (10 if hero_on else 0), "margin_top": 22 if crumb_on else 12, "margin_bottom": int(SafeArea.bottom(18)) if full else 20}
	if strip:
		margins = {"margin_left": 0, "margin_right": 0, "margin_top": 0, "margin_bottom": 0}
	modal_content.begin_bulk_theme_override()
	for key: String in margins:
		if modal_content.get_theme_constant(key) != margins[key]:
			modal_content.add_theme_constant_override(key, margins[key])
	modal_content.end_bulk_theme_override()

## A full window never asks for more than the screen's width (1023). The building window's hero
## column takes half the width and its widest row of chips asked for about 30 units more than
## 1366: the window grew past the right edge, the band slid 15 units and the close button was cut.
## The hero gives up the excess (never below 30 % of the width; its art is centred in it).
func fit_full_modal() -> void:
	if fitting_modal or modal_layout != "full" or not modal_hero.visible or not is_inside_tree():
		return
	var view := get_viewport().get_visible_rect().size
	var excess := modal.get_combined_minimum_size().x - view.x
	if excess <= 0.5:
		return
	fitting_modal = true
	modal_hero.custom_minimum_size.x = maxf(roundf(view.x * 0.3), modal_hero.custom_minimum_size.x - ceilf(excess))
	fitting_modal = false

# Optional illustration column of a full-screen window: art over a tinted ink-wash splash.
# Section line and resource plates on the upper board of the tall header (full windows).
func build_modal_top() -> void:
	modal_top = Control.new()
	modal_top.name = "ModalTop"
	modal_top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	modal.add_child(modal_top)
	# The section line hangs under the title on a small oak plate (it read poorly as a tiny
	# line in the corner of the upper board).
	modal_crumb_plate = PanelContainer.new()
	modal_crumb_plate.name = "ModalCrumbPlate"
	modal_crumb_plate.add_theme_stylebox_override("panel", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(26, 3, 26, 5)))
	modal_crumb_plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	modal_top.add_child(modal_crumb_plate)
	modal_crumb_plate.set_anchors_preset(Control.PRESET_CENTER_TOP)
	modal_crumb_plate.grow_horizontal = Control.GROW_DIRECTION_BOTH
	modal_crumb_plate.offset_left = 0
	modal_crumb_plate.offset_right = 0
	modal_crumb_plate.offset_top = 80
	modal_crumb_plate.offset_bottom = 108
	modal_crumb = UiKit.eyebrow_label()
	modal_crumb.name = "ModalCrumb"
	modal_crumb.add_theme_font_size_override("font_size", 15)
	modal_crumb.add_theme_color_override("font_color", UiKit.GOLD)
	modal_crumb.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	modal_crumb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	modal_crumb_plate.add_child(modal_crumb)
	modal_wallet = HBoxContainer.new()
	modal_wallet.name = "ModalWallet"
	modal_wallet.alignment = BoxContainer.ALIGNMENT_END
	modal_wallet.add_theme_constant_override("separation", 8)
	modal_wallet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	modal_top.add_child(modal_wallet)
	modal_wallet.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	modal_wallet.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	modal_wallet.offset_right = -82
	modal_wallet.offset_top = 3
	modal_wallet.offset_bottom = 28
	for id: String in RESOURCE_NAMES:
		var plate := PanelContainer.new()
		plate.name = "Wallet_" + id
		plate.add_theme_stylebox_override("panel", UiKit.flat(Color("#120b06c0"), Color("#c9a25e55"), 7, Vector2(8, 0)))
		plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
		modal_wallet.add_child(plate)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 5)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		plate.add_child(row)
		add_resource_icon(row, id, 21)
		var amount := Label.new()
		amount.add_theme_font_override("font", UiKit.LABEL_FONT)
		amount.add_theme_font_size_override("font_size", 16)
		amount.add_theme_color_override("font_color", UiKit.IVORY)
		amount.add_theme_color_override("font_outline_color", UiKit.SHADE)
		amount.add_theme_constant_override("outline_size", 3)
		amount.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		amount.custom_minimum_size.x = 64
		amount.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(amount)
		modal_wallet_amounts[id] = amount
	modal_top.hide()

func short_amount(value: int) -> String:
	var amount := str(value)
	if value >= 1000000:
		amount = "%.1f млн" % (value / 1000000.0)
	elif value >= 1000:
		amount = "%.1f тыс" % (value / 1000.0)
	return amount.replace(".", ",")

func refresh_modal_wallet() -> void:
	if not is_instance_valid(modal_top) or not modal_top.visible or not state.has("city"):
		return
	for id: String in modal_wallet_amounts:
		var value := balance(id)
		var label: Label = modal_wallet_amounts[id]
		label.text = short_amount(value)
		label.get_parent().get_parent().tooltip_text = "%s · %s" % [RESOURCE_NAMES[id], format_balance(value)]

## Title and section line of the open window (a window that switches in place).
func set_modal_heading(title: String, eyebrow: String) -> void:
	modal_title.text = title
	modal_eyebrow.text = eyebrow
	modal_crumb.text = eyebrow
	modal_crumb_plate.visible = not eyebrow.is_empty()
	modal_eyebrow.visible = not eyebrow.is_empty() and modal_layout != "full"

func set_modal_hero(art: Texture2D, tint := Color("#b98c52"), caption := "") -> void:
	empty(modal_hero)
	if art != null:
		add_hero_art(art, tint, caption)
	arrange_modal()

## The live view of a building's level in the window's hero (the quote window of a build or an
## upgrade, src/building_stage.gd): «После · ур. N» on its turf tile, the new parts glowing.
func building_hero(type: String, level: int) -> void:
	empty(modal_hero)
	var view := BuildingStage.new()
	view.setup(data, type, level - 1, 11, true)
	modal_hero.add_child(view)
	view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	modal_hero_share = 0.42
	arrange_modal()

func add_hero_art(art: Texture2D, tint := Color("#b98c52"), caption := "") -> void:
	var picture := UiKit.hero(art, Color(tint, 0.5), caption)
	picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	modal_hero.add_child(picture)

func open_modal(title: String, layout := "center", eyebrow := "", art: Texture2D = null) -> void:
	action_ring.close()
	cancel_placement()
	var strip := layout == "strip"
	modal_scroll.horizontal = false
	modal_scroll.outside_tap = Callable()
	modal_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	modal_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED if strip else ScrollContainer.SCROLL_MODE_AUTO
	modal_scroll.scroll_horizontal = 0
	result_open = layout == "result"
	modal_header.visible = not result_open and not strip
	modal_divider.visible = not result_open
	var sheet: StyleBox = UiKit.bare() if strip else (result_sheet_style if result_open else web_sheet_style)
	if modal.get_theme_stylebox("panel") != sheet:
		modal.add_theme_stylebox_override("panel", sheet)
	modal_vignette.visible = not result_open and not strip
	modal.modulate.a = 1.0
	if modal_vignette.texture != UiKit.vignette_texture():
		modal_vignette.texture = UiKit.vignette_texture()
	economy_rows.clear()
	economy_source_label = null
	starter_panel_open = false
	if relocation_pins.visible:
		message.text = ""
	relocation_pins.hide()
	var entering := not modal.visible
	modal_generation += 1
	reset_gestures()
	last_frame_us = 0
	if is_instance_valid(stage):
		stage.clear_route()
	modal_title.text = title
	modal_eyebrow.text = eyebrow
	modal_eyebrow.visible = not eyebrow.is_empty()
	modal_hero_share = 0.4
	modal_full_width = false
	modal_status.hide()
	empty(modal_body)
	empty(modal_tools)
	empty(modal_footer)
	empty(modal_hero)
	modal_tools.hide()
	modal_footer.hide()
	if art != null:
		add_hero_art(art)
	place_modal(layout)
	modal_body.get_parent().set_deferred("scroll_vertical", 0)
	dimmer.color = Color.TRANSPARENT if layout in ["left", "right", "city_target", "strip"] else (Color("#10141740") if layout == "sheet" else Color("#0b0805b0"))
	if result_open:
		dimmer.color = Color("#09140bc9")
		result_notice.hide()
	dimmer.show()
	modal.show()
	modal_scroll.set_modal_active(true)
	if entering and not reduced_motion:
		# Quick settle (fade + 2 % scale, 120 ms); input is live from the first frame.
		modal.modulate.a = 0.75
		modal.pivot_offset = modal.get_rect().size * 0.5 if modal.size.x > 0 else Vector2.ZERO
		modal.scale = Vector2(0.985, 0.985) if layout != "sheet" else Vector2.ONE
		dialog_tween = create_tween()
		dialog_tween.tween_property(modal, "modulate:a", 1.0, 0.12)
		dialog_tween.parallel().tween_property(modal, "scale", Vector2.ONE, 0.12).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		if layout == "sheet":
			# Bottom sheet slides up from the screen edge.
			var rest := modal.offset_top
			modal.offset_top = rest + 60
			modal.offset_bottom += 60
			dialog_tween.parallel().tween_property(modal, "offset_top", rest, 0.14).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
			dialog_tween.parallel().tween_property(modal, "offset_bottom", modal.offset_bottom - 60, 0.14).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	else:
		modal.scale = Vector2.ONE
	# The construction strip stands on a blurred snapshot of the city; the city's own 3D pass
	# stops once the snapshot is on screen (city_backdrop.settled).
	if strip:
		if not city_backdrop.visible:
			city_backdrop.open(stage.camera if is_instance_valid(stage) else null, not entering)
		return
	city_backdrop.close()
	# A full-screen window hides the whole city: its 3D pass is skipped once the window has
	# settled (the recruitment stage renders in its own SubViewport).
	if layout != "full":
		cover_city(false)
	elif entering and dialog_tween != null and dialog_tween.is_running():
		dialog_tween.finished.connect(func(): cover_city(modal.visible and modal_layout == "full"))
	else:
		cover_city(true)

func cover_city(covered: bool) -> void:
	var view := get_viewport()
	if view != null and view.disable_3d != covered:
		view.disable_3d = covered

func panel_action(parent: Container, caption: String, action: Callable, enabled := true, danger := false) -> Button:
	var control := button(parent, caption, action, enabled)
	control.custom_minimum_size.y = 54
	if parent == modal_footer and control.custom_minimum_size.x < 260:
		control.custom_minimum_size.x = 260
	UiKit.style_button(control, "danger" if danger else "primary", 20)
	return control

func panel_art(parent: Container, path: String, pixels: Vector2) -> TextureRect:
	var art := TextureRect.new()
	art.texture = panel_texture(path)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.custom_minimum_size = pixels
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(art)
	return art

## Font sizes (and outlines) of the premium windows, as their first open shapes them.
const WARM_TEXT_SIZES := {"title": [[40, 0], [40, 1], [40, 6]],
	"label": [[14, 0], [15, 0], [15, 3], [16, 0], [16, 3], [16, 4], [17, 0], [18, 0], [21, 0], [21, 4], [22, 0], [22, 4], [26, 0]],
	"body": [[15, 0], [16, 0], [17, 0]]}

## After launch (the launch screen is gone): the glyphs of the window fonts are shaped a
## few sizes per frame and the stage's gradients and framing are made, so the first window
## of a session opens as fast as the later ones. Adds nothing to the launch itself.
func warm_windows() -> void:
	var fonts := {"title": UiKit.TITLE_FONT, "label": UiKit.LABEL_FONT, "body": UiKit.BODY_FONT}
	var combos: Array = []
	for key: String in WARM_TEXT_SIZES:
		for pair: Array in WARM_TEXT_SIZES[key]:
			combos.append([fonts[key], pair[0], pair[1]])
	UiKit.warm_text(hud, combos)
	UnitStage.warm_stage()
	warm_views_soon()

## The window scripts (premium UI stage 4a) compile on a worker thread a frame after the
## launch screen starts to fade: that frame's own warm-ups load scripts on the main thread,
## which would wait for a compile running beside them.
func warm_views_soon() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	v6_panels.warm_views([REPORT_ROW])

func warm_panel_textures() -> void:
	# Decode recruitment portraits on a worker thread after launch, so the first
	# barracks window does not decode eleven images inside the touch handler.
	var pending: Array[String] = []
	for id in RECRUIT_ORDER:
		var full: String = "res://assets/ui/web-panels/" + id + ".png"
		# Units with a baked portrait (assets/ui/units) do not need the older panel art.
		if not ResourceLoader.exists(UnitStage.PORTRAIT_DIR + id + ".webp") and ResourceLoader.exists(full) and ResourceLoader.load_threaded_request(full, "Texture2D") == OK:
			pending.append(full)
	var atlas: String = data.environmentAtlas
	if environment_atlas == null and ResourceLoader.load_threaded_request(atlas, "Texture2D") == OK:
		pending.append(atlas)
	warm_dioramas()
	# Building card art too: the build catalogue and the premium window heroes show it.
	var card_keys := {}
	for key: String in V6_CARD_KEYS.values() + data.types.values():
		card_keys[key] = true
	for key: String in card_keys:
		var card := "res://assets/ui/buildings/%s.png" % key
		if not build_cards.has(key) and ResourceLoader.exists(card) and ResourceLoader.load_threaded_request(card, "Texture2D") == OK:
			pending.append(card)
	# Creature portraits of the world windows (src/world_cards.gd): twelve small images, kept
	# referenced so the hunt list and a creature's window find them in the resource cache.
	for species: String in CreatureVisuals.registry().get("species", {}):
		for path: Variant in CreatureVisuals.entry(species).get("portraits", []):
			if ResourceLoader.exists(str(path)) and ResourceLoader.load_threaded_request(str(path), "Texture2D") == OK:
				pending.append(str(path))
	while not pending.is_empty():
		await get_tree().process_frame
		for full: String in pending.duplicate():
			if ResourceLoader.load_threaded_get_status(full) != ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				pending.erase(full)
				var texture := ResourceLoader.load_threaded_get(full) as Texture2D
				if full.begins_with("res://assets/creatures-v2/"):
					if texture != null:
						creature_portraits.append(texture)
					continue
				if full == atlas:
					if environment_atlas == null:
						environment_atlas = texture
					continue
				if full.begins_with("res://assets/ui/buildings/"):
					var card_key := full.get_file().get_basename()
					if texture != null and build_cards.get(card_key) == null:
						build_cards[card_key] = texture
					continue
				var key: String = full.trim_prefix("res://assets/ui/web-panels/")
				if texture != null and not panel_textures.has(key):
					panel_textures[key] = texture
	# The construction strip's first open (card class and styles, the blurred city's
	# viewports), a few frames after launch rather than in the first tap on «Строить».
	await get_tree().process_frame
	v6_panels.build.warm()

## The dioramas of the construction strip and the turf of its live 3D view, decoded on worker
## threads once the server is known to be V6 (the legacy build sheet never shows them), four
## at a time, so the decoding does not slow whatever the player opens first.
func warm_dioramas() -> void:
	var deadline := Time.get_ticks_msec() + 60000
	while not is_v6_server():
		if Time.get_ticks_msec() > deadline or not is_inside_tree():
			return
		await get_tree().create_timer(0.5).timeout
	var types: Array = V6_CARD_KEYS.keys() + ["B04", "B26", "B27"]
	for start in range(0, types.size(), 4):
		var batch: Array = types.slice(start, start + 4)
		BuildingStage.warm_art(batch)
		while BuildingStage.art_loading(batch) and is_inside_tree():
			await get_tree().process_frame

## Baked portrait of a unit (tools/bake_unit_portraits.gd): the full figure, or the bust for
## small slots. Falls back to the older painted panel art for units without one.
func unit_portrait(id: String, bust := false) -> Texture2D:
	var baked := UnitStage.portrait(id, bust)
	return baked if baked != null else panel_texture(id + ".png")

## full: the whole unit (a portrait-shaped slot); otherwise the bust (dense tables).
func unit_art(parent: Container, id: String, pixels: Vector2, full := false) -> TextureRect:
	var art := TextureRect.new()
	art.texture = unit_portrait(id, not full)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	art.custom_minimum_size = pixels
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(art)
	return art

func panel_texture(path: String) -> Texture2D:
	if not panel_textures.has(path):
		panel_textures[path] = load("res://assets/ui/web-panels/" + path) as Texture2D
	return panel_textures[path]

func open_building_ring(marker: Dictionary) -> void:
	if is_v6_server():
		await v6_panels.open_ring(marker)
		return
	var building: Dictionary = marker.item
	var level := int(building.level)
	var actions: Array = []
	var upgradable: bool = level < MAX_OPEN_BUILDING_LEVEL and building.type in data.upgradable
	actions.append(["Улучшить" if upgradable else "Сведения", "upgrade" if upgradable else "info", inspect_building.bind(building)])
	var construction := building_order(str(building.id))
	if not construction.is_empty() and construction.get("kind", "") != "clear":
		actions.append(["Ускорить", "speed", show_speedups.bind("construction", construction, "")])
	var group: String = data.trainingGroups.get(building_definition(building.type).get("base", building.type), "")
	if group != "":
		actions.append(["Обучить", "train", open_recruitment.bind(building)])
		# Active training in this building: speed up its running (first) order.
		var queue: Array = state.city.get("military", {}).get("queues", {}).get(building.id, [])
		if not queue.is_empty() and float(queue[0].get("endsAt", 0.0)) > timer_now() and not player_id.is_empty():
			var title := "Ускорить" if construction.get("buildingId") != building.id else "Обучение"
			actions.append([title, "speed", show_speedups.bind("training", queue[0], building.id)])
	if building.type in data.producers and not player_id.is_empty():
		actions.append(["Собрать", "collect", command.bind({"kind":"kingdom","action":"collect","buildingId":building.id})])
	if building.type == "ECO-03":
		actions.append(["Обмен", "trade", show_trade])
	if building.type == "SUP-01":
		actions.append(["Лазарет", "heal", show_hospital])
	if building_definition(building.type).get("base", building.type) in ["SUP-03", "SUP-04"]:
		actions.append(["Оборона", "defence", show_city_defence])
	if not marker.get("wall", false) and construction.get("buildingId") != building.id:
		actions.append(["Переместить", "move", start_move.bind(building)])
	if upgradable:
		actions.append(["Сведения", "info", inspect_building.bind(building)])
	action_ring.open(str(building.id), "%s · ур. %d" % [building_title(building.type), level], marker.position, stage.camera, actions)

func inspect_building(building: Dictionary) -> void:
	if is_v6_server():
		if building.get("wall", false) and not building.has("id"):
			await v6_panels.inspect("B18")
		else:
			await v6_panels.inspect_instance(str(building.id))
		return
	open_modal(building_title(building.type), "right", "ПОСЕЛЕНИЕ")
	var level := int(building.level)
	row(modal_body,"Уровень %d" % level)
	var metrics: Dictionary = data.buildingTerms.get(building.type, {})
	if metrics.get("production") != null:
		row(modal_body, "%s · +%d/мин" % [RESOURCE_NAMES[metrics.production], int(metrics.rates[clampi(level, 1, 5) - 1])])
	if int(metrics.get("storage", 0)) > 0:
		row(modal_body, "Вместимость · +%d" % (int(metrics.storage) * level))
	var construction := building_order(str(building.id))
	if not construction.is_empty():
		countdown("Улучшение в процессе", construction.endsAt)
		button(modal_body, "Ускорить строительство", show_speedups.bind("construction", construction, ""))
	if not state.city.get("kingdom") is Dictionary:
		var definition := building_definition(building.type)
		if not state.city.get("legacyUpgrades") is Dictionary:
			for target_level in range(1, mini(int(definition.get("maxLevel", 1)), MAX_OPEN_BUILDING_LEVEL) + 1):
				if target_level != level:
					button(modal_body, "Уровень %d" % target_level, command.bind({"kind":"legacyBuilding",
						"action":"level", "buildingId":building.id, "level":target_level}), not player_id.is_empty())
		for variant in data.buildings:
			if variant.id != building.type and variant.base == definition.get("base", building.type) and data.types.has(variant.id):
				button(modal_body, variant.ru, command.bind({"kind":"legacyBuilding", "action":"variant",
					"buildingId":building.id, "type":variant.id}), not player_id.is_empty())
	if level < MAX_OPEN_BUILDING_LEVEL and building.type in data.upgradable:
		var terms: Dictionary = data.buildingTerms[building.type].upgrades[level - 1]
		add_upgrade_preview(modal_body, building, level, terms)
		var available := can_afford(terms.cost) and construction.is_empty() and builder_ready()
		var base: String = building_definition(building.type).get("base", building.type)
		if base == "ECO-05":
			for prerequisite in data.upgradeRequirements.get(str(level + 1), []):
				if not state.city.buildings.any(func(item): return building_definition(item.type).get("base") == prerequisite[0] and item.level >= prerequisite[1]):
					row(modal_body, "Требуется %s · ур. %d" % [building_title(prerequisite[0]), int(prerequisite[1])])
					available = false
		elif level >= hall_level():
			row(modal_body, "Требуется ратуша уровня %d." % (level + 1))
			available = false
		if construction.is_empty() and not builder_ready():
			add_workers_note(modal_body)
		elif construction.is_empty() and not can_afford(terms.cost):
			row(modal_body, "Недостаточно ресурсов.")
		panel_action(modal_body,"Улучшить",command.bind({"kind":"kingdom","action":"upgrade","buildingId":building.id,"expectedLevel":level}),not player_id.is_empty() and available)
	elif level >= MAX_OPEN_BUILDING_LEVEL and building.type in data.upgradable:
		row(modal_body, "Достигнут максимальный уровень текущего этапа. " + SOON_LINE + ".")
	if building.type in data.producers:
		button(modal_body, "Собрать ресурсы", command.bind({"kind":"kingdom","action":"collect","buildingId":building.id}),not player_id.is_empty())
	if building.type == "ECO-03":
		button(modal_body, "Обменять ресурсы", show_trade, not player_id.is_empty())
	if building.type == "SUP-01":
		button(modal_body, "Лазарет", show_hospital)
	var defence_base: String = building_definition(building.type).get("base", building.type)
	if defence_base in ["SUP-03", "SUP-04"]:
		add_defence_rows(modal_body, defence_base, level)
		button(modal_body, "Оборона поселения", show_city_defence)
	var group: String = data.trainingGroups.get(building_definition(building.type).get("base", building.type), "")
	if group == "":
		return
	var queue: Array = state.city.get("military", {}).get("queues", {}).get(building.id, [])
	for order in queue:
		var unit: Dictionary = unit_for_id(order.unitId)
		var queue_row := HBoxContainer.new()
		modal_body.add_child(queue_row)
		var label := Label.new()
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		queue_row.add_child(label)
		bind_countdown(label, "%s × %d" % [unit.get("name", order.unitId), int(order.quantity)], order.endsAt)
		if order == queue[0]:
			button(queue_row, "Ускорить", show_speedups.bind("training", order, building.id), not player_id.is_empty())
		button(queue_row, "Отменить", confirm_cancel_training.bind(building, order), not player_id.is_empty())
	panel_action(modal_body, "Подготовка войск", open_recruitment.bind(building))

# ---------------------------------------------------------------- defence

func defence_active() -> bool:
	return CityDefence.FEATURE in state.get("cityFeatures", [])

func built_level(base: String) -> int:
	var level := 0
	for building in state.city.buildings:
		if building_definition(building.type).get("base", building.type) == base:
			level = maxi(level, int(building.level))
	return level

func defence_table(parent: Container, rows: Array, next_rows: Array = []) -> void:
	var grid := GridContainer.new()
	grid.columns = 3 if not next_rows.is_empty() else 2
	grid.add_theme_constant_override("h_separation", 18)
	grid.add_theme_constant_override("v_separation", 4)
	parent.add_child(grid)
	for i in rows.size():
		var name := card_note(grid, rows[i][0], Color("#e8dcc4"), 16)
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card_note(grid, rows[i][1], Color("#ffe3a1"), 17)
		if not next_rows.is_empty():
			var later: String = next_rows[i][1]
			card_note(grid, "→ " + later if later != rows[i][1] else "", Color("#9fd27a"), 15)

func defence_note(parent: Container) -> void:
	var text := "Действует, когда на город нападают с мировой карты: защита гарнизона, лучники на стенах и меньше потерь."
	if not defence_active():
		text = "Сервер ещё не обновлён: пока в бою за город считается только гарнизон. После обновления сервера (city-defence) эти показатели начнут действовать при нападении с мировой карты."
	card_note(parent, text, Color("#c9b58f"), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

func add_defence_rows(parent: Container, base: String, level: int) -> void:
	var hall := hall_level()
	var wall := built_level("SUP-03")
	var watch := built_level("SUP-04")
	if base == "SUP-03":
		card_note(parent, "Стены поселения · ур. %d" % level, Color("#f2dfac"), 18)
		var later := CityDefence.wall_rows(CityDefence.stats(hall, mini(wall + 1, 5), watch)) if wall < 5 else []
		defence_table(parent, CityDefence.wall_rows(CityDefence.stats(hall, wall, watch)), later)
	else:
		card_note(parent, "Сторожевая башня · ур. %d" % level, Color("#f2dfac"), 18)
		var later := CityDefence.watchtower_rows(hall, wall, mini(watch + 1, 5)) if watch < 5 else []
		defence_table(parent, CityDefence.watchtower_rows(hall, wall, watch), later)
	defence_note(parent)

# The defence of the settlement in one panel: what the wall and the watchtower give
# when the city is attacked from the world map, what the next level adds, and the
# yard inside the wall.
func show_city_defence() -> void:
	if is_v6_server():
		await v6_panels.inspect("B18")
		return
	action_ring.close()
	open_modal("Оборона поселения", "right", "СТЕНЫ И БАШНИ")
	var hall := hall_level()
	var walls = stage.walls if is_instance_valid(stage) and map_name == "city" else null
	var wall := built_level("SUP-03")
	var watch := built_level("SUP-04")
	var now := CityDefence.stats(hall, wall, watch)
	card_note(modal_body, "Стены", Color("#f2dfac"), 20)
	if now.standing:
		var status := "Частокол с башнями стоит вокруг двора с ратуши II."
		if wall > 0:
			status = "Стены и ворота · ур. %d. %s" % [wall, ["", "Деревянный частокол.", "Деревянный частокол выше.", "Каменные башни.", "Каменные башни, стена выше.", "Каменная стена с зубцами."][wall]]
		row(modal_body, status)
		var later := CityDefence.wall_rows(CityDefence.stats(hall, mini(wall + 1, 5), watch)) if wall < 5 else []
		defence_table(modal_body, CityDefence.wall_rows(now), later)
		if wall == 0:
			row(modal_body, "Постройте «Стены и ворота» (ратуша %d) и улучшайте их: каждый уровень усиливает город." % int(data.unlockLevels.get("SUP-03", 3)))
		elif wall < 5:
			row(modal_body, "Справа — что даст следующий уровень «Стен и ворот».")
		else:
			row(modal_body, "Стены последнего уровня: наибольшая защита города.")
	else:
		row(modal_body, "Стены встанут вокруг двора, когда ратуша достигнет уровня 2. Пока город защищает только гарнизон.")
	card_note(modal_body, "Сторожевая башня", Color("#f2dfac"), 20)
	if watch > 0:
		var later := CityDefence.watchtower_rows(hall, wall, mini(watch + 1, 5)) if watch < 5 else []
		defence_table(modal_body, CityDefence.watchtower_rows(hall, wall, watch), later)
	else:
		row(modal_body, "Не построена · откроется с ратуши %d. Добавляет лучников и защиту гарнизону." % int(data.unlockLevels.get("SUP-04", 3)))
	defence_note(modal_body)
	card_note(modal_body, "Двор", Color("#f2dfac"), 20)
	if walls != null:
		var size: Vector2 = walls.yard_size()
		row(modal_body, "Двор %d × %d м · ратуша ур. %d · свободных участков внутри: %d" % [roundi(size.x), roundi(size.y), hall, stage.empty_plots.size()])
		if hall < 5:
			var grow: float = walls.yard_extent(hall + 1) - walls.yard_extent(hall)
			row(modal_body, "Ратуша ур. %d: стена отодвинется примерно на %d м, внутри появятся новые участки." % [hall + 1, roundi(grow)])
		else:
			row(modal_body, "Двор достиг наибольшего размера текущего этапа.")
	panel_action(modal_body, "Строить оборону", show_build_menu.bind("support"))

func confirm_cancel_training(building: Dictionary, order: Dictionary) -> void:
	open_modal("Отменить обучение?", "center", "ДРЕНОВАР · ОРУЖЕЙНАЯ")
	var refund: bool = not state.city.demo.get("unlimitedResources", false)
	if order.has("chargedCost"):
		refund = not order.chargedCost.is_empty()
	row(modal_body, "Воины из этого заказа не будут добавлены.")
	if refund:
		row(modal_body, "Списанные ресурсы вернутся.")
	panel_action(modal_body, "Да, отменить", command.bind({"kind":"cancelTraining", "orderId":order.id},
		refresh_recruitment.bind(building.id, order.unitId, 1)), true, true)
	button(modal_body, "Продолжить обучение", open_recruitment.bind(building, order.unitId))

func unit_for_id(id: String) -> Dictionary:
	for unit in data.englishRoster:
		if unit.id == id:
			return unit
	return {}

func server_time() -> float:
	return Time.get_unix_time_from_system() * 1000 + server_offset

# Server clock without jumps. Every response's serverTime is already old by its
# network delay, which varies by hundreds of ms between polls; setting the offset
# from each response made marching armies jump back and forth. The newest-sample
# maximum over a short window is the least delayed estimate; the displayed offset
# then slews toward it at most 8% of real time, so game time never runs backward.
const CLOCK_WINDOW_MS := 20000
const CLOCK_SLEW := 0.08
const CLOCK_SNAP_MS := 2500.0
var clock_samples: Array = []
var clock_target := 0.0
var clock_ready := false

func note_server_time(server_ms: float) -> void:
	var local := Time.get_unix_time_from_system() * 1000.0
	var now := Time.get_ticks_msec()
	clock_samples.append([now, server_ms - local])
	while clock_samples.size() > 1 and now - int(clock_samples[0][0]) > CLOCK_WINDOW_MS:
		clock_samples.pop_front()
	clock_target = -INF
	for sample in clock_samples:
		clock_target = maxf(clock_target, float(sample[1]))
	if not clock_ready or absf(clock_target - server_offset) > CLOCK_SNAP_MS:
		# First contact, or a real jump (device clock changed, long suspension).
		server_offset = clock_target
		clock_ready = true

func advance_server_clock(delta: float) -> void:
	if not clock_ready:
		return
	var step := CLOCK_SLEW * delta * 1000.0
	server_offset += clampf(clock_target - server_offset, -step, step)

func recruitment_buildings() -> Array:
	var result := []
	for base in RECRUIT_FACILITIES:
		var index: int = state.city.buildings.find_custom(func(item): return building_definition(item.type).get("base") == base)
		if index >= 0:
			result.append(state.city.buildings[index])
	return result

func open_recruitment(building: Dictionary, unit_id := "", quantity := 1) -> void:
	if is_v6_server():
		if await ensure_v6_ready():
			var current: Dictionary = v6_panels.instance(str(building.id))
			if not current.is_empty():
				await v6_panels.services(str(current.type))
		return
	var group: String = data.trainingGroups.get(building.type, data.trainingGroups.get(building_definition(building.type).get("base"), ""))
	var units: Array = RECRUIT_ORDER.map(unit_for_id).filter(func(unit): return unit.training_building == group)
	if units.is_empty():
		show_training_buildings()
		return
	var selected: Dictionary = unit_for_id(unit_id) if not unit_id.is_empty() else units[0]
	show_recruitment(building, selected, true, quantity)

var pending_training := {}
var recruitment_view := {}
var last_command_error := ""

var last_training_press_msec := -100000

func send_training(building: Dictionary, unit: Dictionary, amount: int) -> void:
	last_training_press_msec = Time.get_ticks_msec()
	var key := Crypto.new().generate_random_bytes(16).hex_encode()
	var list: Array = pending_training.get(building.id, [])
	list.append({"unitId": unit.id, "quantity": amount, "key": key})
	pending_training[building.id] = list
	refresh_recruitment(building.id, unit.id, amount)
	var ok: bool = await command({"kind":"train", "buildingId":building.id, "unitId":unit.id, "quantity":amount,
		"requestId":key, "paidTraining":true}, func(): pass)
	list = pending_training.get(building.id, [])
	list = list.filter(func(entry): return entry.key != key)
	pending_training[building.id] = list
	message.text = "" if ok else "Найм не выполнен: " + last_command_error
	if modal.visible and recruitment_view.get("building", "") == building.id and recruitment_view.get("generation", -1) == modal_generation:
		refresh_recruitment(building.id, str(recruitment_view.unit), amount)
		if not ok:
			modal_status.text = message.text
			modal_status.show()

func refresh_recruitment(building_id: String, unit_id: String, quantity: int) -> void:
	for building in recruitment_buildings():
		if building.id == building_id:
			open_recruitment(building, unit_id, quantity)
			return
	show_training_buildings()

func show_recruitment(building: Dictionary, unit: Dictionary, queue_has_room: bool, quantity := 1) -> void:
	var base: String = building_definition(building.type).get("base", building.type)
	open_modal("%s · ур. %d" % [RECRUIT_FACILITIES.get(base, building_title(building.type)), int(building.level)],
		"wide", "ДРЕНОВАР · ОРУЖЕЙНАЯ")
	modal_tools.show()
	var buildings := recruitment_buildings()
	for type in RECRUIT_FACILITIES:
		var index := buildings.find_custom(func(item): return building_definition(item.type).get("base") == type)
		var candidate: Dictionary = buildings[index] if index >= 0 else {}
		var tab := button(modal_tools, RECRUIT_FACILITIES[type], open_recruitment.bind(candidate), index >= 0)
		tab.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if candidate.get("id") == building.id:
			UiKit.style_button(tab, "primary")
	button(modal_tools, "I · Англия ▾", show_military_cultures)

	var layout := HBoxContainer.new()
	layout.add_theme_constant_override("separation", 10)
	modal_body.add_child(layout)
	var tier := recruit_tier(unit.id)
	var stage_panel := panel(8)
	stage_panel.add_theme_stylebox_override("panel", WebPanels.gradient_style(Color("#2c3433"), Color("#121817"), WebPanels.BRASS, 8))
	stage_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stage_panel.size_flags_stretch_ratio = 0.62
	stage_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	layout.add_child(stage_panel)
	var display := VBoxContainer.new()
	stage_panel.add_child(display)
	var preview := create_unit_preview(display, 258, unit_portrait(unit.id))
	preview.name = "RecruitPreview"
	# Rank-coloured glow behind the unit (I grey ... V gold), under the live 3D view.
	var glow := TextureRect.new()
	glow.name = "Backdrop"
	glow.texture = rank_backdrop(tier)
	glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glow.stretch_mode = TextureRect.STRETCH_SCALE
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	preview.get_parent().add_child(glow)
	preview.get_parent().move_child(glow, 0)
	glow.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var staged: Dictionary = data.unitModels[unit.id].duplicate()
	staged.pedestal = true
	load_unit_preview.call_deferred(preview, staged, 0.72)
	var name_label := Label.new()
	name_label.text = unit.name
	var rank := Label.new()
	rank.text = "РАНГ %s · %s" % [["I", "II", "III", "IV", "V"][tier - 1], unit.get("unit_class", "")]
	rank.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank.add_theme_font_size_override("font_size", 14)
	rank.add_theme_color_override("font_color", RANK_COLOURS[tier - 1][0].lightened(0.45))
	display.add_child(rank)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.add_theme_color_override("font_color", UiKit.IVORY)
	name_label.add_theme_font_override("font", TITLE_FONT)
	name_label.add_theme_font_size_override("font_size", 26)
	display.add_child(name_label)
	var role := Label.new()
	role.text = unit.role
	role.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	role.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	role.add_theme_color_override("font_color", Color("#e3d6bb"))
	display.add_child(role)

	var browser := VBoxContainer.new()
	browser.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	browser.size_flags_stretch_ratio = 0.43
	browser.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	layout.add_child(browser)
	var cards := GridContainer.new()
	cards.columns = 2
	browser.add_child(cards)
	for id in RECRUIT_ORDER:
		var candidate := unit_for_id(id)
		if candidate.training_building != unit.training_building:
			continue
		var card := button(cards, candidate.name, open_recruitment.bind(building, id, quantity))
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card.custom_minimum_size.y = 94
		card.icon = unit_portrait(id)
		card.expand_icon = true
		card.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
		card.add_theme_constant_override("icon_max_width", 60)
		card.add_theme_font_size_override("font_size", 14)
		card.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		style_rank_card(card, recruit_tier(id), id == unit.id, int(state.city.get("military", {}).get("owned", {}).get(id, 0)))
	var owned := int(state.city.get("military", {}).get("owned", {}).get(unit.id, 0))
	var stats := GridContainer.new()
	stats.columns = 2
	browser.add_child(stats)
	for item in [["Мощь", unit.power], ["Атака", unit.attack], ["Защита", unit.defense], ["Гарнизон", owned]]:
		var stat := Label.new()
		stat.text = "%s  %d" % [item[0], int(item[1])]
		stat.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		stat.add_theme_font_size_override("font_size", 16)
		stats.add_child(stat)
	var attributes := VBoxContainer.new()
	button(browser, "Характеристики и роль", func(): attributes.visible = not attributes.visible)
	browser.add_child(attributes)
	attributes.hide()
	row(attributes, "Здоровье %d · Скорость %.1f" % [int(unit.hp), float(unit.speed)])
	for key in ["strengths", "weakness", "special"]:
		if not str(unit.get(key, "")).is_empty():
			row(attributes, unit[key])

	var order := VBoxContainer.new()
	order.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	order.size_flags_stretch_ratio = 0.60
	layout.add_child(order)
	row(order, "Число воинов · до 100 за заказ")
	var numbers := HBoxContainer.new()
	order.add_child(numbers)
	var count := SpinBox.new()
	button(numbers, "−", func(): count.value -= 1)
	count.min_value = 1
	count.max_value = 100
	count.value = quantity
	count.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	count.custom_minimum_size = Vector2(65, 46)
	numbers.add_child(count)
	button(numbers, "+", func(): count.value += 1)
	for shortcut in [10, 100]:
		button(numbers, str(shortcut), func(): count.value = shortcut)
	var slider := HSlider.new()
	slider.min_value = 1
	slider.max_value = 100
	slider.value = count.value
	slider.custom_minimum_size.y = 34
	slider.add_to_group("panel_slider")
	order.add_child(slider)
	slider.value_changed.connect(func(value): count.value = value)
	count.value_changed.connect(func(value): slider.set_value_no_signal(value))
	var quote := Label.new()
	quote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var terms := panel(8)
	terms.add_theme_stylebox_override("panel", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(30, 8, 30, 10)))
	quote.add_theme_color_override("font_color", Color("#e9dcc2"))
	order.add_child(terms)
	var terms_box := VBoxContainer.new()
	terms.add_child(terms_box)
	var cost_row := HBoxContainer.new()
	cost_row.name = "CostRow"
	cost_row.add_theme_constant_override("separation", 14)
	terms_box.add_child(cost_row)
	terms_box.add_child(quote)
	var train := panel_action(order, "Обучить", func(): pass)
	var reason := Label.new()
	reason.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	reason.add_theme_color_override("font_color", UiKit.WARN)
	order.add_child(reason)
	var levels: Array = data.unitRequirements[unit.id]
	if not state.city.get("kingdom") is Dictionary:
		levels = [1, int(unit.legacyLevel)]
	var paid_training: bool = not state.city.demo.get("unlimitedResources", false) or state.get("trainingUsesResources", false)
	var unlocked := hall_level() >= int(levels[0]) and int(building.level) >= int(levels[1])
	var queue: Array = state.city.get("military", {}).get("queues", {}).get(building.id, [])
	var sending: Array = pending_training.get(building.id, [])
	queue_has_room = queue_has_room and queue.size() + sending.size() < 3
	var submission := {"pending": false, "key": "", "quantity": 0}
	recruitment_view = {"building": building.id, "unit": unit.id, "generation": modal_generation}
	var update_quote := func(amount: float):
		var costs := {}
		for resource in ["wood", "food", "iron", "coins"]:
			var cost := int(unit.get(resource, 0))
			if resource == "iron" and state.city.get("kingdom") != null and unit.id == "ENG-01":
				cost = 0
			costs[resource] = cost * int(amount)
		var reduction := clampi(int(building.level) - 1, 0, 4) * 8 if state.city.get("kingdom", state.city.get("legacyUpgrades")) is Dictionary else 0
		var seconds := maxi(1, ceili(float(unit.train_seconds) * amount * (1.0 - reduction / 100.0)))
		quote.text = "Время обучения · %d сек." % seconds
		fill_cost_row(cost_row, costs)
		var affordable := can_afford(costs)
		# A short pause after a press so one tap never becomes two orders.
		var just_pressed := Time.get_ticks_msec() - last_training_press_msec < 600
		train.disabled = submission.pending or just_pressed or player_id.is_empty() or not paid_training or not queue_has_room or not unlocked or not affordable
		train.text = "Принято" if submission.pending else "Обучить %d" % int(amount)
		reason.text = ""
		if not paid_training:
			reason.text = "Подключаем списание ресурсов для этого поселения."
		elif not unlocked:
			reason.text = "Требуется ратуша %d-го уровня и военное здание %d-го уровня." % [int(levels[0]), int(levels[1])]
		elif not queue_has_room:
			reason.text = "Очередь заполнена"
		elif not affordable:
			reason.text = "Недостаточно ресурсов"
		elif player_id.is_empty():
			reason.text = "Войдите в аккаунт"
		reason.visible = not reason.text.is_empty()
	update_quote.call(count.value)
	count.value_changed.connect(update_quote)
	if Time.get_ticks_msec() - last_training_press_msec < 600:
		# The timer belongs to the button: a rebuilt window frees both together.
		var unlock := Timer.new()
		unlock.wait_time = 0.1
		unlock.autostart = true
		train.add_child(unlock)
		unlock.timeout.connect(func():
			if Time.get_ticks_msec() - last_training_press_msec >= 600:
				unlock.stop()
				update_quote.call(count.value))
	# The order goes into the queue on screen at once (marked "отправляем…") and the
	# server confirms in the background; the button is ready again right away, so
	# nobody waits for the network. Resources, the timer and the soldiers stay the
	# server's: the row turns into the real order when its answer arrives.
	train.pressed.connect(func():
		if train.disabled:
			return
		count.apply()
		if train.disabled:
			return
		var amount := int(count.value)
		submission.pending = true
		update_quote.call(count.value)
		send_training(building, unit, amount))
	button(order, "Улучшить здание", inspect_building.bind(building))
	row(order, "ОЧЕРЕДЬ %d / 3" % mini(3, queue.size() + sending.size()))
	for index in 3:
		if index >= queue.size():
			var waiting := index - queue.size()
			if waiting < sending.size():
				var entry: Dictionary = sending[waiting]
				row(order, "%d · %s × %d · отправляем…" % [index + 1, unit_for_id(entry.unitId).get("name", entry.unitId), int(entry.quantity)])
			else:
				row(order, "%d · Свободное место" % (index + 1))
			continue
		var entry: Dictionary = queue[index]
		var timer := Label.new()
		order.add_child(timer)
		bind_countdown(timer, "%s × %d" % [unit_for_id(entry.unitId).get("name", entry.unitId), int(entry.quantity)], entry.endsAt)
		var controls := HBoxContainer.new()
		order.add_child(controls)
		if index == 0:
			button(controls, "Ускорить", show_speedups.bind("training", entry, building.id), not player_id.is_empty())
		button(controls, "Отменить", confirm_cancel_training.bind(building, entry), not player_id.is_empty())
	modal_footer.show()
	var reserves := Label.new()
	reserves.text = "Королевство · ресурсы и очередь сохраняются" if state.city.get("kingdom") is Dictionary else "Запасы основателя"
	reserves.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_footer.add_child(reserves)
	button(modal_footer, "Готовые войска →", show_armies)

const RANK_COLOURS := [[Color("#6d7276"), Color("#24272a")], [Color("#46804f"), Color("#15291a")],
	[Color("#3f63a0"), Color("#152239")], [Color("#70499c"), Color("#241634")], [Color("#b08a3e"), Color("#382810")]]
var rank_backdrops := {}

# Rank I..V of a unit: the military building level that unlocks it.
func recruit_tier(id: String) -> int:
	var levels: Array = data.unitRequirements.get(id, [1, 1])
	return clampi(int(levels[1]), 1, 5)

func rank_backdrop(tier: int) -> Texture2D:
	if rank_backdrops.has(tier):
		return rank_backdrops[tier]
	var colours: Array = RANK_COLOURS[tier - 1]
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.45, 1.0])
	gradient.colors = PackedColorArray([Color(colours[0], 0.95), Color(colours[0].darkened(0.35), 0.7), Color(colours[1], 0.0)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.42)
	texture.fill_to = Vector2(1.05, 0.42)
	texture.width = 128
	texture.height = 128
	rank_backdrops[tier] = texture
	return texture

func style_rank_card(card: Button, tier: int, selected: bool, owned: int) -> void:
	var colours: Array = RANK_COLOURS[tier - 1]
	var edge: Color = WebPanels.GOLD if selected else colours[0].lightened(0.25)
	var top: Color = colours[0].lightened(0.12) if selected else colours[0]
	card.add_theme_stylebox_override("normal", WebPanels.gradient_style(top, colours[1], edge, 5))
	card.add_theme_stylebox_override("hover", WebPanels.gradient_style(top.lightened(0.08), colours[1], WebPanels.GOLD, 5))
	card.add_theme_stylebox_override("pressed", WebPanels.gradient_style(top.darkened(0.15), colours[1], WebPanels.GOLD, 5))
	var badge := Label.new()
	badge.text = ["I", "II", "III", "IV", "V"][tier - 1]
	badge.add_theme_font_override("font", TITLE_FONT)
	badge.add_theme_font_size_override("font_size", 15)
	badge.add_theme_color_override("font_color", Color("#f7e3b4"))
	badge.add_theme_color_override("font_outline_color", Color("#120e0a"))
	badge.add_theme_constant_override("outline_size", 5)
	badge.position = Vector2(7, 3)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(badge)
	var count := Label.new()
	count.text = str(owned)
	count.add_theme_font_size_override("font_size", 14)
	count.add_theme_color_override("font_color", Color("#fff1d2"))
	count.add_theme_color_override("font_outline_color", Color("#120e0a"))
	count.add_theme_constant_override("outline_size", 5)
	count.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	count.offset_left = -42
	count.offset_right = -7
	count.offset_top = 3
	count.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	count.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(count)

func fill_cost_row(row_box: HBoxContainer, costs: Dictionary) -> void:
	empty(row_box)
	for resource in costs:
		if int(costs[resource]) <= 0 or not resource_icons.has(resource):
			continue
		var item := HBoxContainer.new()
		item.add_theme_constant_override("separation", 4)
		row_box.add_child(item)
		add_resource_icon(item, resource, 26)
		var amount := Label.new()
		amount.text = compact_number(int(costs[resource]))
		amount.add_theme_font_size_override("font_size", 18)
		amount.add_theme_color_override("font_color", Color("#fff0d4") if int(costs[resource]) <= balance(resource) else Color("#ff8f7a"))
		item.add_child(amount)

func compact_number(value: int) -> String:
	if value >= 1000000:
		return "%.1fM" % (value / 1000000.0)
	if value >= 10000:
		return "%.1fK" % (value / 1000.0)
	return str(value)

func create_unit_preview(parent: Container, height: int, portrait: Texture2D = null) -> SubViewportContainer:
	var frame := Control.new()
	frame.custom_minimum_size.y = height
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(frame)
	var fallback: Control
	if portrait != null:
		var art := TextureRect.new()
		art.texture = portrait
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		fallback = art
	else:
		var loading := Label.new()
		loading.text = "Загружаем модель…"
		loading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		loading.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		loading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		fallback = loading
	fallback.name = "PreviewFallback"
	fallback.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(fallback)
	fallback.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var preview := SubViewportContainer.new()
	preview.stretch = true
	preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(preview)
	preview.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	return preview

func load_unit_preview(preview: SubViewportContainer, visual: Dictionary, framing: float) -> void:
	if not is_instance_valid(preview) or not preview.is_inside_tree():
		return
	var path: String = visual.preview
	if ResourceLoader.load_threaded_request(path, "PackedScene") != OK:
		return
	# The panel and portrait get a frame before building the live 3D view.
	if DisplayServer.get_name() == "headless":
		await get_tree().process_frame
	else:
		await RenderingServer.frame_post_draw
	while ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		await get_tree().process_frame
	var resource := ResourceLoader.load_threaded_get(path) as PackedScene
	if resource == null or not is_instance_valid(preview) or not preview.is_inside_tree():
		return
	var viewport := SubViewport.new()
	viewport.own_world_3d = true
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	preview.add_child(viewport)
	var root := Node3D.new()
	viewport.add_child(root)
	var unit := resource.instantiate() as Node3D
	var warrior := visual.has("field")
	if warrior:
		WarriorVisual.prepare(unit)
	root.add_child(unit)
	if visual.has("creature"):
		# creatures-v2 preview: the same level materials and authored idle as on the field.
		CreatureVisuals.install(unit, str(visual.creature), int(visual.get("level", 1)), 1.0)
	var bounds := AABB()
	for part: MeshInstance3D in unit.find_children("*", "MeshInstance3D", true, false):
		var box := part.global_transform * part.get_aabb()
		bounds = box if not bounds.has_volume() else bounds.merge(box)
	if warrior and visual.get("pedestal", false):
		bounds = WarriorVisual.pedestal(root, bounds, load(data.stoneTexture))
	var center := bounds.get_center()
	var size := maxf(0.6, bounds.size.length())
	var camera := Camera3D.new()
	root.add_child(camera)
	camera.position = center + Vector3(0.55, 0.24, 1.2) * size * framing
	if warrior:
		camera.fov = 46.0
		var depth := maxf(bounds.size.x, bounds.size.z)
		var distance := maxf(1.0, bounds.size.y * 1.59 + depth * 0.15)
		camera.position = center + Vector3(0.64, 0.21, 1.2).normalized() * distance
	camera.look_at(center)
	camera.make_current()
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-36, -38, 0)
	light.light_color = Color("#ffe3bd")
	light.light_energy = 1.6
	root.add_child(light)
	var fill := Environment.new()
	fill.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	fill.ambient_light_color = Color("#d9e3f0")
	fill.ambient_light_energy = 0.68
	if warrior:
		fill.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		fill.ambient_light_color = Color("#d1d9dd")
		fill.ambient_light_energy = 0.46
		light.light_color = Color("#fff1de")
		light.light_energy = 1.7
		var rim := DirectionalLight3D.new()
		rim.rotation_degrees = Vector3(-25, 134, 0)
		rim.light_color = Color("#bdd6f1")
		rim.light_energy = 0.75
		root.add_child(rim)
		WarriorVisual.ground_shadow(root, bounds)
	WarriorVisual.add_reflections(fill, Color("#8b9874"))
	camera.environment = fill
	var clip: String = "Recruit_Showcase" if warrior and visual.drill == "Mounted_Drill" else visual.drill
	stage.play_animation(unit, clip, visual.drill)
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
	if is_instance_valid(preview) and preview.is_inside_tree():
		preview.get_parent().get_node("PreviewFallback").hide()

# ---------------------------------------------------------------- upgrade preview
# Before "Улучшить": the building now and on the next level side by side (the same
# scenes the city draws), the build time, the cost and what the level improves.
func add_upgrade_preview(parent: Container, building: Dictionary, level: int, terms: Dictionary) -> void:
	var title := Label.new()
	title.text = "Улучшение: уровень %d → %d" % [level, level + 1]
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_font_override("font", UiKit.LABEL_FONT)
	title.add_theme_color_override("font_color", UiKit.BRONZE)
	parent.add_child(title)
	var pair := HBoxContainer.new()
	pair.add_theme_constant_override("separation", 6)
	parent.add_child(pair)
	for target in [level, level + 1]:
		var column := VBoxContainer.new()
		column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		pair.add_child(column)
		var preview := create_unit_preview(column, 170)
		preview.name = "UpgradePreview%d" % target
		var caption := Label.new()
		caption.text = ("Сейчас · ур. %d" if target == level else "После · ур. %d") % target
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.add_theme_color_override("font_color", UiKit.INK_MUTED if target == level else UiKit.GOOD)
		column.add_child(caption)
		load_building_preview(preview, building.type, target)
	row(parent, "Время улучшения · %s" % duration_label(int(terms.seconds)))
	row(parent, "Стоимость · %s" % cost_label(terms.cost))
	for gain in upgrade_gains(building.type, level):
		var label := Label.new()
		label.text = "▲ " + str(gain)
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.add_theme_color_override("font_color", UiKit.GOOD)
		parent.add_child(label)

func upgrade_gains(type: String, level: int) -> Array:
	var gains: Array = []
	var metrics: Dictionary = data.buildingTerms.get(type, {})
	if metrics.get("production") != null:
		var now := int(metrics.rates[clampi(level, 1, 5) - 1])
		var next := int(metrics.rates[clampi(level + 1, 1, 5) - 1])
		gains.append("%s · %d → %d/мин (+%d)" % [RESOURCE_NAMES[metrics.production], now, next, next - now])
	if int(metrics.get("storage", 0)) > 0:
		gains.append("Вместимость · %d → %d" % [int(metrics.storage) * level, int(metrics.storage) * (level + 1)])
	var base: String = building_definition(type).get("base", type)
	if base in ["SUP-01", "MIL-01", "MIL-02", "MIL-03", "MIL-05"]:
		gains.append("Время лечения и обучения · −%d%% → −%d%%" % [(level - 1) * 8, level * 8])
	if base in ["SUP-03", "SUP-04"]:
		gains.append("Оборона поселения усиливается, стена становится выше и прочнее")
	if base == "ECO-05":
		gains.append("Двор и стена города расширяются, открываются новые постройки")
	if gains.is_empty():
		gains.append("Здание становится больше и получает новый облик")
	return gains

func building_preview_parts(type: String, level: int) -> Array:
	## [[scene path, scale, material override?], ...] exactly as the city draws this level.
	var entry: Variant = data.get("levelModels", {}).get(type, {}).get(str(level))
	if entry is Dictionary:
		return [[entry.path, float(entry.get("scale", 1.0)), false]]
	var id: String = data.starterHall if type == "ECO-05" and level == 1 else data.types.get(type, "")
	if id.is_empty():
		return []
	var asset: Dictionary = data.models[id]
	# Level props are the yard dressing of the town plan (added by load_building_preview).
	return [[asset.path, float(asset.scale) * (1.0 + 0.055 * (level - 1)), false]]

func load_building_preview(preview: SubViewportContainer, type: String, level: int) -> void:
	var parts := building_preview_parts(type, level)
	if parts.is_empty() or not is_instance_valid(preview):
		return
	for part in parts:
		ResourceLoader.load_threaded_request(part[0], "PackedScene")
	if DisplayServer.get_name() == "headless":
		await get_tree().process_frame
	else:
		await RenderingServer.frame_post_draw
	for part in parts:
		while ResourceLoader.load_threaded_get_status(part[0]) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			await get_tree().process_frame
	if not is_instance_valid(preview) or not preview.is_inside_tree():
		return
	var viewport := SubViewport.new()
	viewport.own_world_3d = true
	viewport.transparent_bg = true
	viewport.msaa_3d = Viewport.MSAA_2X
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	preview.add_child(viewport)
	var root := Node3D.new()
	viewport.add_child(root)
	var model := Node3D.new()
	root.add_child(model)
	for part in parts:
		var scene := ResourceLoader.load_threaded_get(part[0]) as PackedScene
		if scene == null:
			continue
		var node := scene.instantiate() as Node3D
		node.scale = Vector3.ONE * float(part[1])
		model.add_child(node)
		if part[2]:
			for mesh: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
				mesh.material_override = stage.scenery_material
	# The yard as the city draws it at this level (kerb, forecourt, posts, lanterns).
	var lots: Variant = stage.get("town_lots") if is_instance_valid(stage) else null
	if lots is Dictionary and lots.has(type) and building_definition(type).get("base", type) != "SUP-03":
		model.add_child(TownGround.preview(lots, type, level))
	var bounds := AABB()
	for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		var box := mesh.global_transform * mesh.get_aabb()
		bounds = box if not bounds.has_volume() else bounds.merge(box)
	# Both columns use one fixed plot-sized frame, so growth between levels is visible.
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 16.0
	root.add_child(camera)
	var focus := Vector3(0, 2.6, 0)
	camera.position = focus + Vector3(75, 83, 75).normalized() * 40.0
	camera.look_at(focus)
	camera.make_current()
	var ground := MeshInstance3D.new()
	var disc := CylinderMesh.new()
	disc.top_radius = 9.4
	disc.bottom_radius = 9.4
	disc.height = 0.1
	ground.mesh = disc
	var turf := StandardMaterial3D.new()
	turf.albedo_color = Color("#3f5a2c")
	turf.roughness = 1.0
	ground.material_override = turf
	ground.position.y = -0.06
	root.add_child(ground)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-48, -32, 0)
	light.light_color = Color("#ffe4b8")
	light.light_energy = 1.7
	light.shadow_enabled = true
	root.add_child(light)
	var fill := Environment.new()
	fill.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	fill.ambient_light_color = Color("#d8e5ee")
	fill.ambient_light_energy = 0.6
	fill.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	camera.environment = fill
	# slow turntable so every side of the new level can be seen
	var spin := create_tween().set_loops()
	spin.tween_property(model, "rotation:y", TAU, 24.0).from(0.0)
	viewport.tree_exiting.connect(spin.kill)
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
	if is_instance_valid(preview) and preview.is_inside_tree():
		preview.get_parent().get_node("PreviewFallback").hide()

func encounter_title(encounter: Dictionary) -> String:
	var roman: String = ["I", "II", "III"][clampi(int(encounter.level), 1, 3) - 1]
	return "%s · %s" % [encounter.spec.name, roman]

## A creature (src/world_cards.gd): its portrait (the live model in the city), level, health,
## rewards and «Атаковать»/«Собрать отряд» in the footer.
func inspect_encounter(encounter: Dictionary) -> void:
	v6_panels.world_view.encounter(encounter)

# Server worldKind of a world hunt: "velkor" for the Velkor sites (the only kind server v92
# knows); other world creatures (server patch creatures-world-v1) are addressed by species.
func world_kind(encounter: Dictionary) -> String:
	var species := str(encounter.get("species", encounter.get("spec", {}).get("id", "velkor")))
	return "velkor" if species.is_empty() or species == "velkor" else species

func show_city_hunt() -> void:
	open_modal("Цели охоты", "garrison", "ДИКИЕ ЗЕМЛИ")
	append_hunt_targets(state.get("encounters", []))
	modal_footer.show()
	UiKit.style_button(button(modal_footer, "К поселению", show_city_actions), "tertiary", 18).size_flags_horizontal = Control.SIZE_EXPAND_FILL

func show_world_hunt() -> void:
	open_modal("Цели охоты", "right", "ДРЕНОВАР · ДИКИЕ ЗЕМЛИ")
	append_hunt_targets(state.world.encounters)
	v6_panels.world_view.back_to_world()

func append_hunt_targets(encounters: Array) -> void:
	v6_panels.world_view.hunts(encounters)

func compose_march(kind: String, id: String, title: String) -> void:
	if v6_panels.enabled() and kind == "pvp":
		v6_panels.formation(id, title)
		return
	var city := kind == "city"
	open_modal("Создать войско" if city else "Сбор отряда", "wide" if city else "right",
		"DRENOVAR · ПОХОД" if city else "ДРЕНОВАР · ВОЕННЫЙ СОВЕТ")
	var layout := HBoxContainer.new()
	layout.add_theme_constant_override("separation", 13)
	modal_body.add_child(layout)
	var slots := VBoxContainer.new() if city else null
	var roster := VBoxContainer.new()
	roster.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var route_map := MarchMap.new()
	if city:
		var formation := panel(12)
		formation.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		formation.size_flags_stretch_ratio = 0.74
		layout.add_child(formation)
		var aside := VBoxContainer.new()
		aside.add_theme_constant_override("separation", 8)
		formation.add_child(aside)
		UiKit.section_header(aside, "Состав отряда")
		slots.add_theme_constant_override("separation", 6)
		aside.add_child(slots)
		UiKit.label(aside, "%s → %s" % [state.city.name, title], 17, UiKit.BRONZE, UiKit.LABEL_FONT)
		route_map.custom_minimum_size.y = 90
		route_map.hide()
		aside.add_child(route_map)
		UiKit.style_button(button(aside, "Обучить ещё воинов", show_training_buildings), "secondary", 18)
	else:
		roster.add_child(route_map)
		route_map.hide()
		row(roster, title)
	layout.add_child(roster)
	var tools := HBoxContainer.new()
	roster.add_child(tools)
	var selected := {}
	var selection_batch := {"active": false}
	var summary := Label.new()
	summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	summary.add_theme_color_override("font_color", UiKit.BRONZE)
	summary.add_theme_font_size_override("font_size", 18)
	var quote := Label.new()
	quote.name = "MarchQuote"
	quote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	roster.add_child(quote)
	modal_footer.show()
	var back := inspect_current_settlement.bind(id) if kind == "pvp" else inspect_current_encounter.bind(id)
	button(modal_footer, "Назад", back)
	if city:
		modal_footer.add_child(summary)
	else:
		# The narrow side panel keeps the footer for actions only.
		roster.add_child(summary)
	var send := panel_action(modal_footer, "Марш" if city else "Отправить отряд", func(): pass, false, not city)
	send.name = "MarchSend"
	var submit := {"order": {}, "sending": false}
	var generation := modal_generation
	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = 0.12 if city else 0.18
	roster.add_child(timer)
	var preview := {"revision": 0, "units": {}, "in_flight": false}
	# A creature beside a building is out of reach only while its patrol keeps it in
	# the building's clearance (server v92 refuses that route). Ask again while it walks
	# its 20 s round; a refused order leaves as soon as a route is found.
	var blocked := {"until": 0, "send": false, "orders": 0}
	# The client's forecast of when the creature is in the open (route_wait_ms). Off
	# once the server refuses a route the forecast called open: then the window falls
	# back to asking the server.
	var forecast := {"on": city and not is_v6_server(), "asked": false}
	# Lives in the window: closing it ends the waiting.
	var blocked_timer := Timer.new()
	blocked_timer.one_shot = true
	blocked_timer.wait_time = 1.2
	roster.add_child(blocked_timer)
	blocked_timer.timeout.connect(func():
		if generation == modal_generation and not submit.sending and not preview.units.is_empty():
			timer.start())
	var retry := button(roster, "Повторить расчёт", func():
		blocked.until = 0
		timer.start())
	retry.hide()
	var update := func():
		if submit.sending:
			return
		var units := {}
		var power := 0
		for unit_id in selected:
			var count: int = int(selected[unit_id].value)
			if count > 0:
				units[unit_id] = count
				power += count * int(unit_for_id(unit_id).power)
		var total := total_units(units)
		summary.text = "Мощь %s · войска %d / %d" % [compact_number(power), total, march_limit()]
		if city:
			empty(slots)
			for unit_id in units:
				var unit: Dictionary = unit_for_id(unit_id)
				var slot := HBoxContainer.new()
				slots.add_child(slot)
				var portrait := PanelContainer.new()
				portrait.add_theme_stylebox_override("panel", UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), UiKit.TIERS[recruit_tier(unit_id) - 1].lightened(0.18)))
				slot.add_child(portrait)
				unit_art(portrait, unit_id, Vector2(46, 58), true)
				var remove := button(slot, "%s × %d" % [unit.name, units[unit_id]], func(): selected[unit_id].value = 0)
				UiKit.style_button(remove, "tertiary", 17)
				remove.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				remove.accessibility_name = "Убрать из отряда: " + unit.name
			if units.is_empty():
				row(slots, "Добавить войска из списка")
			if state.get("encounters", []).any(func(target): return target.id == id and target.get("species") == "tenerys" and int(target.level) == 1):
				row(slots, "Ориентир для Тенериса I: 11 копейщиков (около 960 мощи).")
		preview.revision += 1
		preview.units = units
		submit.order = {}
		blocked.until = 0
		blocked.orders = 0
		if blocked.send and not submit.sending:
			send.text = "Марш"
		blocked.send = false
		retry.hide()
		# The party can be sent at once; the route preview only draws the path and the
		# arrival time, the server computes the real route for the order anyway.
		send.disabled = total == 0 or submit.sending
		send.set_meta("route_ready", false)
		stage.clear_route()
		route_map.set_path([])
		if total == 0:
			timer.stop()
			quote.text = "Выберите воинов"
			return
		quote.text = "Прокладываем путь…" if city else "Рассчитываем маршрут…"
		if city and show_local_march(id, route_map):
			quote.text = "Путь через главные ворота · уточняем время…"
		timer.start()
	var set_party := func(all_available: bool):
		selection_batch.active = true
		fill_party(selected, all_available)
		selection_batch.active = false
		update.call()
	var heading := UiKit.label(tools, "Доступные войска", 20, UiKit.INK, UiKit.LABEL_FONT)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	UiKit.style_button(button(tools, "Все доступные", set_party.bind(true)), "secondary", 18)
	var clear_party := button(modal_footer, "Очистить", set_party.bind(false))
	UiKit.style_button(clear_party, "tertiary", 18)
	# Load the models of every troop type on hand while the party is chosen.
	if is_instance_valid(stage):
		stage.prewarm_troops(state.get("healthy", {}).keys())
	var first_row_index := roster.get_child_count() - 1
	for unit in data.englishRoster:
		if unit.id == "SIEGE-RAM-01":
			continue
		var available := int(state.healthy.get(unit.id, 0))
		if available < 1:
			continue
		var tier := recruit_tier(unit.id)
		var entry := PanelContainer.new()
		entry.add_theme_stylebox_override("panel", UiKit.row_style())
		roster.add_child(entry)
		roster.move_child(entry, first_row_index)
		first_row_index += 1
		var card := VBoxContainer.new()
		entry.add_child(card)
		var controls := HBoxContainer.new()
		card.add_child(controls)
		controls.add_theme_constant_override("separation", 8)
		var frame := PanelContainer.new()
		frame.add_theme_stylebox_override("panel", UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), UiKit.TIERS[tier - 1].lightened(0.18)))
		controls.add_child(frame)
		unit_art(frame, unit.id, Vector2(56, 72), true)
		var badge := Label.new()
		badge.text = ["I", "II", "III", "IV", "V"][tier - 1]
		badge.add_theme_font_size_override("font_size", 12)
		badge.add_theme_color_override("font_color", UiKit.IVORY)
		badge.add_theme_color_override("font_outline_color", Color("#120e0a"))
		badge.add_theme_constant_override("outline_size", 4)
		badge.size_flags_vertical = Control.SIZE_SHRINK_END
		badge.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		frame.add_child(badge)
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		controls.add_child(info)
		info.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		info.add_theme_constant_override("separation", 0)
		UiKit.label(info, unit.name, 19, UiKit.INK, UiKit.LABEL_FONT)
		UiKit.label(info, "%s %s" % ["Доступно" if city else "В гарнизоне", format_balance(available)], 15, UiKit.INK_MUTED)
		var amount := SpinBox.new()
		var less := button(controls, "−", func(): amount.value -= 1)
		UiKit.style_button(less, "tertiary", 22)
		less.custom_minimum_size = Vector2(46, 46)
		less.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		amount.min_value = 0
		amount.max_value = mini(available, march_limit())
		amount.custom_minimum_size.x = 70
		amount.get_line_edit().editable = city
		amount.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		controls.add_child(amount)
		var more := button(controls, "+", func(): amount.value += 1)
		UiKit.style_button(more, "tertiary", 22)
		more.custom_minimum_size = Vector2(46, 46)
		more.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		selected[unit.id] = amount
		if true:
			var slider := HSlider.new()
			slider.max_value = amount.max_value
			slider.custom_minimum_size.y = 29
			slider.add_to_group("panel_slider")
			card.add_child(slider)
			slider.value_changed.connect(func(value): amount.value = value)
			amount.value_changed.connect(func(value): slider.set_value_no_signal(value))
		var unit_id: String = unit.id
		amount.value_changed.connect(func(value):
			if selection_batch.active:
				return
			var used := 0
			for other in selected:
				if other != unit_id:
					used += int(selected[other].value)
			if value > march_limit() - used:
				amount.set_value_no_signal(march_limit() - used)
				amount.get_line_edit().text = str(int(amount.value))
				(card.get_child(1) as HSlider).set_value_no_signal(amount.value)
			update.call())
	if selected.is_empty():
		row(roster, "Свободных воинов нет. Откройте казармы и завершите обучение.")
	var lock_party := func(locked: bool):
		clear_party.disabled = locked
		for control in roster.find_children("*", "Button", true, false): control.disabled = locked
		if city:
			for control in slots.find_children("*", "Button", true, false): control.disabled = locked
		for control in roster.find_children("*", "SpinBox", true, false): control.editable = not locked
		for control in roster.find_children("*", "HSlider", true, false): control.editable = not locked
	timer.timeout.connect(func():
		if preview.units.is_empty() or generation != modal_generation or submit.sending:
			return
		# Slider changes coalesce into the latest selection. Never leave a growing
		# group of obsolete route requests competing with the actual command.
		if preview.in_flight:
			timer.start()
			return
		var revision: int = preview.revision
		var order := {"kind":"deploy" if city else "worldMarch", "encounterId":id, "units":preview.units.duplicate()}
		if not city:
			order.worldKind = kind
		elif not march_wall().is_empty():
			order.wall = march_wall()
		retry.hide()
		var predicted := route_wait_ms(id) if forecast.on else 0.0
		if forecast.on and forecast.asked and not submit.sending:
			# The creature is beside a building right now: server v92 would refuse the
			# route (and take long to do so). Ask again when the way is open. The first
			# preview always goes to the server: a server that reaches such a creature
			# (route-approach patch) turns the forecast off.
			var wait := predicted
			if wait > 300.0:
				if not route_map.visible:
					show_local_march(id, route_map)
				quote.text = "Зверь у постройки, путь откроется через %d с. Нажмите «Марш» — отряд выйдет сам, как только путь будет свободен." % ceili(wait / 1000.0)
				send.disabled = false
				blocked_timer.start(minf(wait / 1000.0, 1.0))
				return
		forecast.asked = true
		if not (city and route_map.visible):
			quote.text = "Прокладываем путь…" if city else "Рассчитываем маршрут…"
		preview.in_flight = true
		var current := func(): return generation == modal_generation and revision == preview.revision and not submit.sending and modal.visible
		var response := await send_request("march-preview" if loopback else "native/game/march-preview", order, false, 8.0, "", "", current)
		preview.in_flight = false
		if generation != modal_generation or submit.sending:
			return
		if revision != preview.revision:
			if not preview.units.is_empty(): timer.start()
			return
		if response.get("httpStatus", 0) == 401 and not loopback:
			reset_session()
			close_modal()
			show_account()
			return
		if not response.has("path"):
			if city and response.get("error", "") == BLOCKED_ROUTE and not submit.sending:
				if predicted <= 300.0:
					forecast.on = false
				var now := Time.get_ticks_msec()
				if blocked.until == 0:
					blocked.until = now + BLOCKED_ROUTE_WAIT_MS
				if now < blocked.until:
					quote.text = "Путь к цели перекрыт постройкой. Ждём, пока зверь отойдёт…"
					send.disabled = blocked.send
					blocked_timer.start(1.2)
					return
				if blocked.send:
					blocked.send = false
					send.text = "Марш"
			# A slow or lost answer is only the preview: the order carries the same
			# party and the server lays the route itself, so «Марш» stays available.
			if response.get("transportFailure", false) or int(response.get("httpStatus", 0)) >= 500:
				if city and (route_map.visible or show_local_march(id, route_map)):
					quote.text = "Путь через главные ворота. Нажмите «Марш» — время пути рассчитает сервер."
				else:
					quote.text = "Маршрут ещё не рассчитан, но отряд можно отправить."
					retry.show()
				send.disabled = submit.sending
				return
			quote.text = response.get("error", "Путь недоступен")
			retry.show()
			# A refused route (not a lost connection) cannot be marched.
			send.disabled = true
			return
		if predicted > 300.0:
			# The server reached a creature the forecast called blocked: no holding.
			forecast.on = false
		quote.text = "Прибытие через %d с%s" % [ceili((float(response.get("travelMs", 0)) + 1400.0) / 1000.0),
			" · через переправу" if response.get("usesFerry", false) else ""]
		stage.show_route(response.path)
		if city:
			route_map.set_path(stage.march_path(response.path))
		order.requestId = Crypto.new().generate_random_bytes(16).hex_encode()
		submit.order = order
		send.set_meta("route_ready", true)
		send.disabled = submit.sending
		blocked.until = 0
		if blocked.send and not submit.sending:
			# The order refused for a blocked route leaves now that a route is open.
			blocked.send = false
			send.text = "Марш"
			send.pressed.emit())
	# A city order waits for the moment the creature is in the open (route_wait_ms).
	var departure := {"at": 0.0}
	var countdown := Timer.new()
	countdown.wait_time = 0.2
	roster.add_child(countdown)
	# Lambdas capture locals by value: the order sender lives in a shared dictionary.
	var orders := {"dispatch": Callable()}
	countdown.timeout.connect(func():
		if generation != modal_generation:
			countdown.stop()
			return
		var left := float(departure.at) - server_time()
		if left > 0.0:
			send.text = "Выход через %d с" % ceili(left / 1000.0)
			return
		countdown.stop()
		submit.sending = false
		orders.dispatch.call())
	send.pressed.connect(func():
		if submit.sending or preview.units.is_empty():
			return
		if forecast.on:
			var wait := route_wait_ms(id)
			if wait > 150.0:
				submit.sending = true
				send.disabled = true
				timer.stop()
				blocked_timer.stop()
				departure.at = server_time() + wait
				send.text = "Выход через %d с" % ceili(wait / 1000.0)
				quote.text = "Зверь проходит у постройки. Отряд выйдет из главных ворот, как только путь будет свободен."
				countdown.start()
				return
		orders.dispatch.call())
	orders.dispatch = func():
		if submit.sending or preview.units.is_empty():
			return
		timer.stop()
		blocked_timer.stop()
		preview.revision += 1
		if submit.order.is_empty():
			# Route preview still on its way: send the same order without waiting for it.
			timer.stop()
			var direct := {"kind":"deploy" if city else "worldMarch", "encounterId":id, "units":preview.units.duplicate(),
				"requestId": Crypto.new().generate_random_bytes(16).hex_encode()}
			if not city:
				direct.worldKind = kind
			elif not march_wall().is_empty():
				direct.wall = march_wall()
			submit.order = direct
		submit.sending = true
		lock_party.call(true)
		retry.hide()
		send.disabled = true
		send.text = "Отправляем…"
		quote.text = "Отправляем отряд…"
		modal_status.text = "Отправляем…"
		modal_status.show()
		var order: Dictionary = submit.order
		var result := await command(order, Callable() if city else show_world_directory)
		if not result and generation == modal_generation:
			submit.sending = false
			lock_party.call(false)
			send.text = "Марш" if city else "Отправить отряд"
			send.disabled = preview.units.is_empty()
			# Sent before its route preview (stopped on press): the quote would keep
			# saying «Прокладываем путь…». Show the server's reason and offer a retry.
			if city and last_command_error == BLOCKED_ROUTE:
				forecast.on = false
				if route_wait_ms(id) < 0.0:
					# The whole patrol runs beside a building: waiting cannot help with
					# server v92 (route-approach-v2 lets the army stop next to the creature).
					blocked.orders = 3
					quote.text = "Зверь всё время ходит вплотную к постройке, и сервер не прокладывает к нему путь. Атака на этого зверя заработает после обновления сервера (route-approach-v2)."
					modal_status.hide()
					retry.show()
					return
			if city and last_command_error == BLOCKED_ROUTE and not preview.units.is_empty() and blocked.orders < 3:
				# Keep the order: ask for the route again and send it once the way is open.
				blocked.orders += 1
				blocked.send = true
				blocked.until = 0
				submit.order = {}
				send.set_meta("route_ready", false)
				send.text = "Ждём путь…"
				send.disabled = true
				modal_status.text = "Путь перекрыт постройкой. Отряд выйдет, как только зверь отойдёт."
				retry.hide()
				timer.start()
			elif not send.get_meta("route_ready", false) and not preview.units.is_empty():
				quote.text = last_command_error
				retry.show()
	if city:
		set_party.call(true)
	else:
		update.call()

# The route of a city march drawn by the client at once, from the troop base to the
# creature through the main gate, before (or without) the server's preview.
func show_local_march(id: String, route_map) -> bool:
	if map_name != "city" or not is_instance_valid(stage) or stage.parade_center == Vector3.ZERO:
		return false
	var target: Dictionary = {}
	for encounter in state.get("encounters", []):
		if encounter.id == id:
			target = encounter
	if target.is_empty() or not (target.get("position") is Dictionary):
		return false
	var from: Vector3 = stage.parade_center
	var path: Array = [{"x": from.x, "y": from.y, "z": from.z}, target.position]
	stage.show_route(path)
	route_map.set_path(stage.march_path(path))
	return true

# ---------------------------------------------------------------- route window
# Server v92 builds a city march route only to a creature cell (snapped to its 2 m
# grid) that is not within 5 m (on both axes) of a building. A creature whose patrol
# passes a building is out of reach only for part of its 20 s round. The client
# knows the patrol, the round and the buildings, so it sends the order for the
# moment the server will see the creature in the open.
const PATROL_ROUND_MS := 20000.0
const ROUTE_CLEARANCE := 5.0

func plot_point(plot_id: String) -> Variant:
	for plot in data.plots:
		if plot.id == plot_id:
			return Vector2(float(plot.x), float(plot.z))
	if plot_id.begins_with("site-") and data.treePlots.has(plot_id.trim_prefix("site-")):
		var tree: Dictionary = data.treePlots[plot_id.trim_prefix("site-")]
		return Vector2(float(tree.x), float(tree.z))
	if plot_id.begins_with("plot-"):
		var n := int(plot_id.trim_prefix("plot-"))
		if n < 36:
			return Vector2((n % 6 - 2.5) * 12.0 * 0.82, (floor(n / 6.0) - 2.5) * 12.0 * 0.82)
	return null

func building_points() -> Array:
	var points: Array = []
	for building in state.get("city", {}).get("buildings", []):
		var at: Variant = plot_point(str(building.get("plotId", "")))
		if at != null:
			points.append(at)
	return points

# Where the server places the creature at a server time (core.mjs refresh).
func creature_point(encounter: Dictionary, server_ms: float) -> Vector2:
	var patrol: Array = encounter.get("patrol", [])
	if patrol.size() < 2:
		var p: Dictionary = encounter.get("position", {})
		return Vector2(float(p.get("x", 0)), float(p.get("z", 0)))
	var cycle := fposmod(maxf(0.0, server_ms - float(encounter.get("spawnedAt", 0))), PATROL_ROUND_MS)
	var fraction := clampf((cycle - 4000.0) / 16000.0, 0.0, 1.0)
	var total := 0.0
	for i in range(1, patrol.size()):
		total += Vector2(float(patrol[i].x) - float(patrol[i - 1].x), float(patrol[i].z) - float(patrol[i - 1].z)).length()
	var left := total * fraction
	for i in range(1, patrol.size()):
		var a := Vector2(float(patrol[i - 1].x), float(patrol[i - 1].z))
		var b := Vector2(float(patrol[i].x), float(patrol[i].z))
		var d := a.distance_to(b)
		if left <= d:
			return a.lerp(b, left / d if d > 0.0 else 0.0)
		left -= d
	return Vector2(float(patrol[-1].x), float(patrol[-1].z))

func cell_open(p: Vector2, buildings: Array) -> bool:
	# JavaScript Math.round: halves go up.
	var cell := Vector2(floor(p.x / 2.0 + 0.5) * 2.0, floor(p.y / 2.0 + 0.5) * 2.0)
	for b in buildings:
		if absf(cell.x - b.x) < ROUTE_CLEARANCE and absf(cell.y - b.y) < ROUTE_CLEARANCE:
			return false
	return true

# Milliseconds to wait before sending an order for this creature so that the server,
# when it receives it, finds the creature in the open: 0 when it may go now, -1 when
# the whole patrol is beside a building (then the server alone decides).
func route_wait_ms(encounter_id: String) -> float:
	var encounter: Dictionary = {}
	for row in state.get("encounters", []):
		if row.id == encounter_id:
			encounter = row
	if encounter.is_empty() or encounter.get("status", "alive") != "alive":
		return 0.0
	var buildings := building_points()
	var latency := expected_latency_ms()
	# The order reaches the server about one round trip after the local estimate of
	# its clock; it must find the creature in the open over a margin around that.
	var margin := 500.0 + latency * 0.5
	var arrival := server_time() + latency
	var any_open := false
	var t := 0.0
	while t <= PATROL_ROUND_MS:
		var ok := true
		var probe := -margin
		while probe <= margin:
			if not cell_open(creature_point(encounter, arrival + t + probe), buildings):
				ok = false
				break
			probe += 100.0
		if ok:
			return t
		if cell_open(creature_point(encounter, arrival + t), buildings):
			any_open = true
		t += 100.0
	if any_open:
		# Open only for moments shorter than the margin: aim at the middle of the
		# longest open stretch.
		var best := -1.0
		var best_len := 0.0
		var run_start := -1.0
		t = 0.0
		while t <= PATROL_ROUND_MS * 2.0:
			if cell_open(creature_point(encounter, arrival + t), buildings):
				if run_start < 0.0:
					run_start = t
				if t - run_start > best_len:
					best_len = t - run_start
					best = run_start + best_len * 0.5
			else:
				run_start = -1.0
			t += 100.0
		return maxf(0.0, best)
	return -1.0

const BLOCKED_ROUTE := "Нет безопасного пути к цели"
# One patrol round of a city creature (server: 4 s rest + 16 s walk) and a margin.
const BLOCKED_ROUTE_WAIT_MS := 22000

# The city wall as drawn, for a city march: the army leaves the yard through a gate
# and walks around the wall (server patch route-approach-v2; server v92 ignores it).
func march_wall() -> Dictionary:
	if map_name != "city" or not is_instance_valid(stage) or not stage.walls.visible or stage.walls.radii.size() != stage.walls.SAMPLES:
		return {}
	var walls = stage.walls
	var radii: Array = []
	for r in walls.radii:
		radii.append(snappedf(r, 0.1))
	var gates: Array = []
	for k in walls.gates.size():
		gates.append([int(walls.gates[k]), int(walls.gate_half(k))])
	return {"cx": snappedf(walls.center.x, 0.01), "cz": snappedf(walls.center.y, 0.01), "radii": radii, "gates": gates}

func fill_party(selected: Dictionary, all_available: bool) -> void:
	var remaining := march_limit() if all_available else 0
	for input: SpinBox in selected.values():
		input.value = minf(input.max_value, remaining)
		remaining -= int(input.value)

func show_account() -> void:
	if is_instance_valid(v6_panels):
		v6_panels.account()
		return
	open_modal("Твоё королевство", "profile", "ДРЕНОВАР · КОРОЛЕВСТВО")
	if not connected() or (login_for_transfer and not login_proof.is_empty()):
		if login_proof.is_empty():
			row(modal_body, "Войди в аккаунт, чтобы открыть свои поселения и общий мир." if server_login == "device" else "Войди через ChatGPT, чтобы открыть свои поселения и общий мир.")
			panel_action(modal_body, "Начать вход", begin_login)
			button(modal_body, "Проверка плавности", show_performance)
		else:
			var challenge := login_proof.sha256_text()
			var code := challenge.left(8).to_upper()
			row(modal_body, "Код подтверждения  " + code)
			if login_for_transfer:
				row(modal_body, "Подключение веб-версии: нажми «Открыть страницу входа», в Safari войди в тот же аккаунт ChatGPT, что и на сайте, введи код и нажми «Разрешить вход». Вернись в приложение — всё подключится само, или нажми «Проверить вход». Все поселения аккаунта (и брата) появятся на телефоне.")
			else:
				row(modal_body, "На странице DRENOVAR войди в тот же аккаунт ChatGPT, введи код и нажми «Разрешить вход».")
			button(modal_body, "Открыть страницу входа", open_login_page.bind(challenge))
			var copy_buttons := HBoxContainer.new()
			modal_body.add_child(copy_buttons)
			button(copy_buttons, "Скопировать код", func(): DisplayServer.clipboard_set(code))
			button(copy_buttons, "Скопировать ссылку", copy_login_link.bind(challenge))
			button(modal_body, "Проверить вход", finish_login.bind(true))
			button(modal_body, "Получить новый код", restart_login)
			if login_for_transfer and not connected():
				button(modal_body, "Нет аккаунта на веб-версии — начать новое поселение", confirm_profile_action.bind(
					"Новое поселение начнётся с нуля. Подключить веб-версию можно и потом в профиле. Начать?", device_login))
			if connected():
				button(modal_body, "Отмена", cancel_transfer)
		return
	if restoring_session:
		row(modal_body, "Подключаемся к сохранённому поселению…")
		button(modal_body, "Повторить подключение", restore_account)
		button(modal_body, "Выйти из аккаунта", confirm_profile_action.bind(sign_out_question(), sign_out))
		return
	if loopback:
		row(modal_body, state.city.name)
		row(modal_body, "Локальный тестовый мир")
		button(modal_body, "Проверка плавности", show_performance)
		return
	row(modal_body, "Загружаем поселения…")
	var generation := modal_generation
	var profile: Dictionary = await request("account")
	if generation != modal_generation:
		return
	empty(modal_body)
	button(modal_body, "Проверка плавности", show_performance)
	if saved_session_error:
		row(modal_body, "Не удалось сохранить вход на устройстве. Сессия действует до закрытия приложения.")
	if not profile.has("profiles"):
		show_error(profile)
		button(modal_body, "Повторить", show_account)
	else:
		if profile.playerId != null:
			add_name_fields(profile)
		var web_link: Dictionary = profile.get("webLink", {}) if profile.get("webLink") is Dictionary else {}
		var followed: Array = web_link.get("follow", [])
		for item in profile.profiles:
			var title := "%s · %d воинов" % [item.name, int(item.troops)]
			if followed.has(item.id) and web_link.get("on", false):
				title += " · с веб-версии"
			if item.active:
				row(modal_body, title + " · текущее поселение")
			else:
				button(modal_body, title, confirm_profile_action.bind("Открыть «%s»?" % item.name, select_profile.bind(item.id)))
		if profile.profiles.is_empty():
			button(modal_body, "Основать поселение", create_settlement)
		if SessionStore.is_device(session):
			# More settlements of the old server (e.g. a brother's, or another ChatGPT
			# account) join the ones already on this phone.
			if web_link.get("on", false):
				var until := Time.get_datetime_string_from_unix_time(int(float(web_link.get("until", 0)) / 1000.0 + Time.get_time_zone_from_system().get("bias", 0) * 60), true).right(8).left(5)
				row(modal_body, "Трансляция с веб-версии включена до %s. Новые поселения и изменения с сайта приходят сами; поселение, в котором ты играешь на телефоне, остаётся основным." % until)
			else:
				if web_link.get("lastError", null) == "login":
					row(modal_body, "Вход веб-версии истёк, трансляция остановлена. Подключи веб-версию снова.")
				else:
					row(modal_body, "Поселения с веб-версии (например, брата) появятся здесь после подключения веб-версии.")
				panel_action(modal_body, "Подключить веб-версию", begin_transfer)
	button(modal_body, "Выйти из приложения", confirm_profile_action.bind(sign_out_question(), sign_out))

## The player's and the settlement's names (editNames), restyled in stage 4b: a caption
## over each field, the save as a gold button that wakes when a name changes. `after` is the
## window to show once the server has them (the account by default).
func add_name_fields(profile: Dictionary, after := Callable()) -> void:
	var saved_nickname := str(profile.get("nickname")) if profile.get("nickname") != null else ""
	var saved_settlement: String = state.city.name
	var fields := GridContainer.new()
	fields.columns = 2
	fields.add_theme_constant_override("h_separation", 16)
	fields.add_theme_constant_override("v_separation", 4)
	modal_body.add_child(fields)
	for caption in ["Имя игрока", "Название поселения"]:
		UiKit.label(fields, caption, 16, UiKit.BRONZE, UiKit.LABEL_FONT, false)
	var nickname := LineEdit.new()
	nickname.name = "NicknameField"
	nickname.placeholder_text = "Имя игрока"
	nickname.max_length = 60
	nickname.text = saved_nickname
	nickname.custom_minimum_size = Vector2(0, 50)
	nickname.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fields.add_child(nickname)
	var settlement := LineEdit.new()
	settlement.name = "SettlementField"
	settlement.placeholder_text = "Название поселения"
	settlement.max_length = 60
	settlement.text = saved_settlement
	settlement.custom_minimum_size = Vector2(0, 50)
	settlement.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fields.add_child(settlement)
	var save := Button.new()
	save.text = "Сохранить имена"
	save.custom_minimum_size = Vector2(260, 50)
	save.size_flags_horizontal = Control.SIZE_SHRINK_END
	save.disabled = true
	UiKit.style_button(save, "primary", 19)
	modal_body.add_child(save)
	var back: Callable = after if after.is_valid() else show_account
	var changes_for_fields := func() -> Dictionary:
		var changes := {}
		var next_nickname := nickname.text.strip_edges()
		var next_settlement := settlement.text.strip_edges()
		if next_nickname != saved_nickname:
			changes.nickname = next_nickname
		if next_settlement != saved_settlement:
			changes.settlementName = next_settlement
		return changes
	var refresh_save := func(_text: String):
		var values: Array = changes_for_fields.call().values()
		save.disabled = not nickname.editable or values.is_empty() or values.has("")
	nickname.text_changed.connect(refresh_save)
	settlement.text_changed.connect(refresh_save)
	save.pressed.connect(func():
		var changes: Dictionary = changes_for_fields.call()
		if changes.is_empty() or changes.values().has("") or command_in_progress:
			return
		save.disabled = true
		nickname.editable = false
		settlement.editable = false
		modal_status.text = "Сохраняем…"
		modal_status.show()
		changes.kind = "editNames"
		var accepted := await command(changes, back)
		if not accepted and is_instance_valid(nickname) and nickname.is_inside_tree():
			nickname.editable = true
			settlement.editable = true
			refresh_save.call(""))

## A question before an account action (premium UI stage 4b): signing out is a cranberry
## «Выйти» under a door; opening another settlement and starting anew are gold.
func confirm_profile_action(title: String, action: Callable) -> void:
	var leaving := action == sign_out
	v6_panels.menu_view.confirm(title, action, "Подтвердить", leaving, "kit_emb_exit" if leaving else "kit_emb_town")

func show_performance() -> void:
	var primitives := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
	var draw_calls := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	open_modal("Плавность на этом устройстве")
	row(modal_body, diagnostics.summary())
	if frame_count < 30:
		row(modal_body, "Поиграй несколько секунд, чтобы получить замер.")
		return
	var samples := frame_samples.slice(0, frame_count)
	samples.sort()
	var report := "DRENOVAR %s\nМодель: %s\nКадры: %d\nМедиана: %.1f мс\n95-й перцентиль: %.1f мс\nСамый долгий кадр: %.1f мс\nПоследний переход: %d мс" % [
		ProjectSettings.get_setting("application/config/version"), OS.get_model_name(), frame_count,
		samples[floori((frame_count - 1) * 0.5)], samples[floori((frame_count - 1) * 0.95)], samples[-1], last_scene_ms
	]
	var batches := stage.batch_counts()
	if motion_count >= 10:
		var movement := motion_samples.slice(0, motion_count)
		movement.sort()
		report += "\nПри движении камеры: медиана %.1f мс · 95-й перцентиль %.1f мс · %d кадров" % [
			movement[floori((motion_count - 1) * 0.5)], movement[floori((motion_count - 1) * 0.95)], motion_count]
	report += "\nСцена: %s\nЭкземпляры в отрисовке: %d из %d" % ["город" if map_name == "city" else "мир", batches.x, batches.y]
	report += "\nПоследний пересчёт окружения: %.2f мс" % stage.last_cull_ms
	# The 3D image actually drawn: the window's pixels times the 3D scale. (The root
	# viewport texture's get_size() includes the canvas_items stretch: on an iPhone 12
	# it reported 4694 × 2162 for a 2532 × 1170 render target.)
	var output_size := Vector2(get_window().size) * get_viewport().scaling_3d_scale
	report += "\nРазмер интерфейса: %d × %d\nРазмер буфера: %d × %d\nВызовы отрисовки: %d\nПримитивы: %d" % [
		get_viewport().get_visible_rect().size.x, get_viewport().get_visible_rect().size.y,
		output_size.x, output_size.y, draw_calls, primitives
	]
	if map_name == "world":
		var lod := stage.world_lod_counts()
		report += "\nДистанция камеры: %.1f\nЗдания (3D / дальние): %d / %d\nДальние кроны: %d" % [
			stage.camera_zoom, lod.x, lod.y, lod.z
		]
	report += "\nРендерер: %s\nGPU: %s\nПередано матриц окружения: %.1f МБ" % [RenderingServer.get_current_rendering_method(), RenderingServer.get_video_adapter_name(), stage.uploaded_transform_bytes / 1048576.0]
	# Resolution chain: is the 3D drawn at the panel's native size or larger?
	var window := get_window()
	report += "\nОкно: %s · экран: %s · масштаб экрана: %.2f · растяжение: %.3f · 3D-масштаб: %.2f · %s" % [
		DisplayServer.window_get_size(), DisplayServer.screen_get_size(), DisplayServer.screen_get_scale(),
		window.content_scale_factor, get_viewport().scaling_3d_scale, str(get_viewport().get_visible_rect().size)]
	var device_memory := OS.get_memory_info()
	report += "\nПамять устройства: всего %.0f МБ · доступно %.0f МБ · одна сцена в памяти: %s" % [
		float(device_memory.get("physical", -1)) / 1048576.0, float(device_memory.get("available", -1)) / 1048576.0,
		"да" if single_scene else "нет"]
	report += "\nПамять (CPU): %.0f МБ, пик %.0f МБ · видеопамять: %.0f МБ · текстуры: %.0f МБ" % [
		Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, memory_peak_mb,
		Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0,
		Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0]
	report += "\nПоследний переход: %s · время работы: %d мин" % [last_scene_label, Time.get_ticks_msec() / 60000]
	var fx: BattleFx = stage.battle_fx if is_instance_valid(stage) else null
	report += "\nБой: эффекты %s · событий %d" % [
		("%d с назад" % ((Time.get_ticks_msec() - fx.last_battle_msec) / 1000)) if fx != null and fx.last_battle_msec >= 0 else "ещё не показывались",
		fx.last_battle_events if fx != null else 0]
	report += "\nСвязь: последний запрос %s · запросов %d, из них по открытому соединению %d · новых соединений %d" % [
		("%.0f мс" % last_command_ms) if last_command_ms >= 0.0 else "—", api.requests_total, api.requests_reused, api.connections_opened]
	report += "\n" + diagnostics.summary()
	row(modal_body, report)
	button(modal_body, "Скопировать замер", func(): DisplayServer.clipboard_set(report))
	add_combat_diagnostics_buttons()

func add_combat_diagnostics_buttons() -> void:
	if combat_diagnostics == null:
		button(modal_body, "Диагностика боя: включить", func():
			set_combat_diagnostics(true)
			show_performance())
	else:
		button(modal_body, "Скопировать отчёт боя", func(): combat_diagnostics.copy_report())
		button(modal_body, "Диагностика боя: выключить", func():
			set_combat_diagnostics(false)
			show_performance())

# On: an overlay with frame time, memory, counts and a selected fighter, and a
# bounded event log for the report. Remembered across launches until switched off.
func set_combat_diagnostics(on: bool, remember := true) -> void:
	if remember:
		CombatDiagnostics.store_enabled(on)
	if on and combat_diagnostics == null:
		combat_diagnostics = CombatDiagnostics.new()
		combat_diagnostics.name = "CombatDiagnostics"
		add_child(combat_diagnostics)
	elif not on and combat_diagnostics != null:
		combat_diagnostics.queue_free()
		combat_diagnostics = null

func connected() -> bool:
	return loopback or not session.is_empty()

func resume_pending_main_login() -> void:
	var pending := SessionStore.read_pending_login(endpoint, OLD_SERVER)
	if pending.is_empty():
		return
	login_proof = pending.proof
	login_for_transfer = true
	login_link_used = true
	login_deadline = Time.get_ticks_msec() + int((float(pending.expires_at) - Time.get_unix_time_from_system()) * 1000.0)

func begin_main_login(open_browser := true) -> void:
	if login_in_progress:
		return
	# Keep the last confirmed city and device key until ownership is confirmed.
	# Ignore a late restore response while the player starts browser sign-in.
	request_generation += 1
	restoring_session = false
	if SessionStore.valid(pending_old_session) and not SessionStore.is_device(pending_old_session):
		await import_old(pending_old_session)
		return
	login_for_transfer = true
	transfer_refresh = false
	login_proof = Crypto.new().generate_random_bytes(32).hex_encode()
	login_deadline = Time.get_ticks_msec() + 300000
	login_link_used = false
	pending_login_save_error = SessionStore.save_pending_login(login_proof, endpoint, OLD_SERVER, Time.get_unix_time_from_system() + 300.0) != OK
	show_account()
	if open_browser:
		open_login_page(login_proof.sha256_text())

func begin_login() -> void:
	if endpoint == LIVE_SERVER:
		await begin_main_login()
		return
	# A server with device accounts (Cloudflare) signs in at once: no browser step.
	if not loopback:
		var info := await send_request("auth/info", null, false, 6.0)
		if info.get("login", "") == "device":
			server_login = "device"
			server_transfer = info.get("transfer", false)
			if server_transfer:
				# Straight to the web version's login: its settlements come to this phone.
				await begin_transfer()
			else:
				await device_login()
			return
	login_proof = Crypto.new().generate_random_bytes(32).hex_encode()
	login_deadline = Time.get_ticks_msec() + 300000
	login_link_used = false
	show_account()

# The account lives on this phone: a random 256-bit secret, kept encrypted in the
# app's private storage. The server knows only its hash.
func device_login() -> void:
	if login_in_progress:
		return
	login_in_progress = true
	session = SessionStore.DEVICE_PREFIX + Crypto.new().generate_random_bytes(32).hex_encode()
	saved_session_error = SessionStore.save_session(session) != OK
	login_proof = ""
	message.text = ""
	await sync_account()
	login_in_progress = false
	if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
		await show_account()

# A new confirmation code for the login in progress (sign-in or transfer).
func restart_login() -> void:
	if endpoint == LIVE_SERVER:
		await begin_main_login()
	elif login_for_transfer:
		await begin_transfer(transfer_refresh)
	else:
		await begin_login()

func show_transfer_choice() -> void:
	open_modal("Твоё королевство", "profile", "ДРЕНОВАР · НОВЫЙ СЕРВЕР")
	row(modal_body, "DRENOVAR переехал на новый сервер. Аккаунт теперь хранится на этом телефоне.")
	row(modal_body, "Поселение со старого сервера переносится целиком: постройки, войска, ресурсы, предметы и отчёты. Отряды должны быть дома.")
	panel_action(modal_body, "Перенести поселение со старого сервера", begin_transfer)
	button(modal_body, "Начать новое поселение", confirm_profile_action.bind(
		"Новое поселение начнётся с нуля. Перенести старое потом тоже можно. Начать?", device_login))

func begin_refresh() -> void:
	await begin_transfer(true)

func begin_transfer(refresh := false) -> void:
	if endpoint == LIVE_SERVER:
		await begin_main_login()
		return
	if is_instance_valid(v6_panels):
		v6_panels.account()
		return
	transfer_refresh = refresh
	if SessionStore.valid(pending_old_session) and not SessionStore.is_device(pending_old_session):
		set_login_status("Переносим поселение…")
		await import_old(pending_old_session)
		return
	login_for_transfer = true
	login_proof = Crypto.new().generate_random_bytes(32).hex_encode()
	login_deadline = Time.get_ticks_msec() + 300000
	login_link_used = false
	show_account()

# Moves the settlement of an old-server login to this phone: the new server reads it
# from the old server with that login and binds it to a new device account.
func import_old(old_session: String) -> void:
	if login_in_progress:
		return
	login_in_progress = true
	# The account already on this phone keeps its settlements: the old ones join it.
	var previous := session if SessionStore.is_device(session) and SessionStore.valid(session) else ""
	var device := previous if not previous.is_empty() else SessionStore.DEVICE_PREFIX + Crypto.new().generate_random_bytes(32).hex_encode()
	session = device
	var response := await send_request("auth/import-old", {"oldSession": old_session, "refresh": transfer_refresh}, true, 45.0)
	login_in_progress = false
	if response.get("linked", false):
		SessionStore.forget_pending_login()
		if previous.is_empty():
			saved_session_error = SessionStore.save_session(device) != OK
		pending_old_session = ""
		login_for_transfer = false
		login_proof = ""
		message.text = "Вход через ChatGPT выполнен. Открываем ваш основной город." if response.get("sharedServer", false) else transfer_message(response)
		transfer_refresh = false
		player_id = ""
		await sync_account()
		await show_account()
		return
	session = previous
	if response.get("transportFailure", false) or int(response.get("httpStatus", 0)) >= 500:
		show_account()
		show_error(response)
		return
	SessionStore.forget_pending_login()
	if response.get("oldLogin", false):
		# The old login expired: confirm it again on the old server.
		pending_old_session = ""
		await begin_main_login()
		set_login_status("Подтвердите вход через ChatGPT ещё раз.")
		return
	login_for_transfer = false
	login_proof = ""
	show_account()
	if response.get("armiesOut", false):
		set_login_status("Отряды ещё в походе на старом сервере. Дождись их возвращения и повтори перенос.")
	else:
		show_error(response)

func cancel_transfer() -> void:
	SessionStore.forget_pending_login()
	login_for_transfer = false
	transfer_refresh = false
	login_proof = ""
	await show_account()

func transfer_message(response: Dictionary) -> String:
	var count := int(response.get("profiles", []).size())
	var refreshed := int(response.get("refreshedProfiles", []).size())
	var text := ("Со старого сервера перенесено поселений: %d." % count) if response.get("imported", false) else "Поселения снова на этом телефоне."
	if refreshed > 0:
		text = "Обновлено с веб-версии поселений: %d." % refreshed
	var skipped: Array = response.get("skipped", [])
	if not skipped.is_empty():
		var names := PackedStringArray()
		for item in skipped:
			names.append(str(item.get("name", "")) if str(item.get("name", "")) != "" else "без названия")
		text += " Не перенесены: %s. Если там отряды в походе — дождись их и повтори перенос." % ", ".join(names)
	return text

func login_url(challenge: String) -> String:
	if login_for_transfer:
		return OLD_SERVER + "/api/native/approve?challenge=" + challenge
	return endpoint + "/api/native/approve?challenge=" + challenge

func copy_login_link(challenge: String) -> void:
	if Time.get_ticks_msec() >= login_deadline:
		await restart_login()
		set_login_status("Код истёк. Открой страницу с новым кодом.")
		return
	DisplayServer.clipboard_set(login_url(challenge))
	login_link_used = true
	set_login_status("Ссылка скопирована. Вставь её в адресную строку Safari.")

func open_login_page(challenge: String) -> void:
	if Time.get_ticks_msec() >= login_deadline:
		await restart_login()
		set_login_status("Код истёк. Открой страницу с новым кодом.")
		return
	if OS.shell_open(login_url(challenge)) != OK:
		set_login_status("Не удалось открыть браузер. Скопируй ссылку и открой её в Safari.")
		return
	login_link_used = true
	set_login_status("Если браузер не открылся, скопируй ссылку и вставь её в Safari.")

func set_login_status(value: String) -> void:
	if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
		modal_status.text = value
		modal_status.show()

func finish_login(manual := false) -> void:
	if login_proof.is_empty() or login_in_progress:
		return
	if busy:
		if manual:
			set_login_status("Запрос уже выполняется.")
		return
	if Time.get_ticks_msec() >= login_deadline:
		login_proof = ""
		SessionStore.forget_pending_login()
		if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
			show_account()
			set_login_status("Код истёк. Начни вход заново.")
		return
	var proof := login_proof
	login_in_progress = true
	if manual:
		set_login_status("Проверяем подтверждение…")
	var response := await send_request("native/exchange", {"proof":proof}, true, 12.0, "", OLD_SERVER if login_for_transfer else "")
	if proof != login_proof:
		login_in_progress = false
		return
	if login_for_transfer and response.get("session") is String and SessionStore.valid(response.session):
		login_in_progress = false
		set_login_status("Вход подтверждён. Открываем ваш основной город…")
		await import_old(response.session)
		return
	if response.get("session") is String and SessionStore.valid(response.session):
		session = response.session
		saved_session_error = SessionStore.save_session(session) != OK
		login_proof = ""
		message.text = ""
		await sync_account()
		if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
			await show_account()
	elif response.get("pending", false):
		if manual:
			set_login_status("Подтверждение ещё не получено. В Safari введи код и нажми «Разрешить вход».")
	elif modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
		show_error(response)
	login_in_progress = false

# FOREST_RESCUE hook (1022): the adventure layer follows the server. A state without state.adventure
# (production today) never loads it; with it, it loads after the launch, one script per frame.
func adventure_offered(value: Dictionary) -> bool:
	var adventure: Variant = value.get("adventure")
	return adventure is Dictionary and not str(adventure.get("campaignId", "")).is_empty()

func forest_state_changed() -> void:
	if forest_game != null:
		forest_game.on_state(state)
	else:
		maybe_start_forest_game()

## The forest layers' load as a share (1023, the loading indicator): the two script lists, then the
## world layer's setup steps in their order, then the city's forest swap. Never goes back.
const FOREST_STAGE_SHARE := {"data": 0.24, "landmarks.plan": 0.28, "terrain.new": 0.32, "terrain.shadows+tiles": 0.36,
	"terrain.bake (thread)": 0.42, "kit": 0.56, "canopy+paths": 0.6, "river+water": 0.63, "quarry": 0.66,
	"impostor meshes": 0.68, "impostors": 0.72, "fog": 0.76, "landmarks.populate": 0.8, "fog receivers": 0.84,
	"adventure state": 0.86, "post-setup (city build / first ticks)": 0.9}

func forest_loading() -> bool:
	if forest_load_started_msec < 0 or not ForestFlags.enabled():
		return false
	if forest_game_loading or forest_game == null:
		return true
	var attach: String = str(stage.get("forest_attach_state")) if is_instance_valid(stage) and map_name == "city" else ""
	return attach == "" or attach == "attaching"

func forest_load_share() -> float:
	var game: Vector2i = ForestFlags.progress.get("game", Vector2i(0, 1))
	var world: Vector2i = ForestFlags.progress.get("world", Vector2i(0, 1))
	var share := 0.14 * float(game.x) / maxf(1.0, float(game.y)) + 0.08 * float(world.x) / maxf(1.0, float(world.y))
	if is_instance_valid(stage):
		var node: Variant = stage.get("forest_world")
		if node == null:
			node = stage.find_child("ForestWorld", false, false)
		if node is Node and is_instance_valid(node):
			share = maxf(share, float(FOREST_STAGE_SHARE.get(str(node.get("setup_stage")), 0.22)))
		if str(stage.get("forest_attach_state")) == "attached":
			share = 1.0
	return share

func update_forest_progress(delta: float) -> void:
	if not is_instance_valid(forest_progress):
		return
	var loading := forest_loading() and map_name == "city" and not scene_loading and \
		bool(state.get("adventure", {}).get("access", {}).get("unlocked", false)) if state.get("adventure") is Dictionary else false
	if not loading and not forest_progress.visible:
		return
	forest_ratio = maxf(forest_ratio, forest_load_share())
	forest_progress.reduced_motion = reduced_motion
	forest_progress.update(loading, forest_ratio, delta)

func maybe_start_forest_game() -> void:
	if forest_game == null and not forest_game_loading and launch_done and adventure_offered(state):
		ensure_forest_game()

## Creates the adventure layer (QA may await it directly). Returns it once its setup has run.
func ensure_forest_game() -> Node:
	if forest_game != null:
		return forest_game
	if forest_game_loading:
		await forest_game_ready
		return forest_game
	forest_game_loading = true
	forest_load_started_msec = Time.get_ticks_msec()
	# 1023: both layers' scripts compile on worker threads side by side, whatever the player does.
	if ForestFlags.enabled():
		ForestFlags.prefetch(ForestFlags.WORLD_LAYER, get_tree())
	await ForestFlags.load_staged(ForestFlags.GAME_LAYER, get_tree(), Callable(), "game")
	var layer: Node = load(ForestFlags.GAME_LAYER_SCRIPT).new()
	add_child(layer)
	layer.setup(self)
	forest_game = layer
	forest_game_loading = false
	layer.on_state(state)
	forest_game_ready.emit()
	return forest_game

func show_cached_state(cached: Dictionary) -> void:
	if cached.is_empty():
		return
	var game_state: Dictionary = cached.state
	# Game time continues from the offset measured when the copy was written; the
	# first server answer snaps it to the exact value.
	server_offset = float(cached.offset)
	clock_target = server_offset
	clock_ready = false
	state = game_state
	player_id = str(state.playerId)
	showing_cached_state = true
	battle_results.observe(player_id, state.get("reports", []))
	refresh_hud()
	v6_panels.state_changed()
	if is_instance_valid(stage):
		stage.present(state)
	forest_state_changed() # FOREST_RESCUE hook: the saved copy may carry state.adventure

func restore_account() -> void:
	restoring_session = true
	restore_running = true
	# Background request (does not block taps); the poll loop retries every ~1.5 s
	# until the server answers.
	var generation := request_generation
	var response := await send_request("native/game/state", null, false, 8.0)
	restore_running = false
	if generation == request_generation and restoring_session:
		apply_restored_state(response)
	restore_finished.emit()

func apply_restored_state(response: Dictionary) -> void:
	if int(response.get("httpStatus", 0)) in [403, 426]:
		restoring_session = false
		client_update_required = int(response.get("httpStatus", 0)) == 426
		show_account.call_deferred()
		return
	if response.get("httpStatus", 0) == 401:
		reset_session()
		if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
			show_account.call_deferred()
		return
	if response.has("city") and response.has("world"):
		restoring_session = false
		accept(response)
		if message.text.begins_with("Подключаемся"):
			message.text = ""
		if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
			show_account.call_deferred()
	elif response.get("needsSettlement", false):
		restoring_session = false
		message.text = "Открой профиль, чтобы подключить свой город" if endpoint == LIVE_SERVER else "Открой профиль, чтобы основать поселение"
		if modal.visible and modal_title.text in ["Твоё королевство", "Аккаунт"]:
			show_account.call_deferred()

func sync_account(create_if_needed := false) -> void:
	var response := await request("state")
	if response.get("needsSettlement", false):
		if create_if_needed:
			var created := await request("session/new", {})
			if not created.has("playerId"):
				show_error(created)
				return
			response = await request("state")
		else:
			message.text = "Открой профиль, чтобы подключить свой основной город" if endpoint == LIVE_SERVER else "Открой профиль в левом верхнем углу, чтобы основать поселение"
			return
	if not response.has("city"):
		show_error(response)
		return
	accept(response)
	if not is_instance_valid(v6_panels) and SessionStore.is_device(session) and not web_link_hint_shown:
		web_link_hint_shown = true
		var account: Dictionary = await request("account")
		var link = account.get("webLink")
		if link is Dictionary and not link.get("on", false):
			message.text = "Чтобы поселения с веб-версии (например, брата) были на телефоне, открой профиль и нажми «Подключить веб-версию»."

func create_settlement() -> void:
	await sync_account(true)
	await show_account()

func select_profile(id: String) -> void:
	var result := await request("profile/select", {"playerId":id})
	if not result.has("profiles"):
		show_error(result)
		return
	player_id = ""
	await sync_account()
	await show_account()

func sign_out_question() -> String:
	if endpoint == LIVE_SERVER:
		return "Выйти на этом устройстве? Город сохранится на сервере. Вернуться можно через ChatGPT или код подключения."
	if SessionStore.is_device(session):
		return "Аккаунт хранится только на этом телефоне. После выхода вернуться в это поселение будет нельзя. Выйти?"
	return "Выйти из аккаунта на этом устройстве?"

func sign_out() -> void:
	var response := await send_request("native/logout", {})
	if not response.get("signedOut", false) and response.get("httpStatus", 0) != 401:
		show_error(response)
		return
	reset_session("sign_out")
	await show_account()

func reset_session(reason := "auth_401") -> void:
	drop_state_tag()
	diagnostics.log_event("session_reset", {"reason": reason}, Time.get_unix_time_from_system())
	request_generation += 1
	SessionStore.forget()
	session = ""
	restoring_session = false
	saved_session_error = false
	player_id = ""
	battle_results.reset()
	result_notice.hide()
	state = data.demo
	if is_instance_valid(stage):
		stage.present(state)
	forest_state_changed() # FOREST_RESCUE hook
	refresh_hud()

## The chronicle of battles (premium UI stage 4a): one drawn row per report, newest first,
## with the outcome badge, the opponent, when it was, the losses and the spoils.
func show_reports() -> void:
	open_modal("Летопись сражений", "full", "ОТЧЁТЫ О БОЯХ")
	modal_full_width = true
	arrange_modal()
	var reports: Array = state.get("reports", []).duplicate()
	if reports.is_empty():
		UiKit.label(modal_body, "Пока нет боевых отчётов. Они появятся после первого похода или охоты.", 17, UiKit.INK_MUTED)
		mark_reports_seen()
		return
	reports.reverse()
	var now := timer_now()
	var row_script := v6_panels.script_of(REPORT_ROW)
	for report: Dictionary in reports:
		var row = row_script.new()
		row.name = "Report_" + str(report.get("id", modal_body.get_child_count()))
		row.outcome = "scout" if report.get("outcome", "") == "scout" else ("victory" if report.get("outcome", "") == "victory" else "defeat")
		var opponent: Dictionary = report.get("creature", {})
		row.opponent = "%s · ур. %d" % [str(opponent.get("name", "Цель")), int(opponent.get("level", 1))] if opponent.has("level") else str(opponent.get("name", "Цель"))
		row.when = report_age(now - float(report.get("finishedAt", now)))
		var parts: Array[String] = []
		for section: Array in [["surviving", "в строю"], ["wounded", "ранены"], ["dead", "погибли"]]:
			var count := total_units(report.get(section[0], {}))
			if count > 0:
				parts.append("%s %s" % [format_balance(count), section[1]])
		row.losses = ", ".join(parts)
		# Premium UI stage 4b: the party's portraits with their counts, and the opponent's.
		var party: Dictionary = {}
		for section: String in ["surviving", "wounded", "dead"]:
			for id: String in report.get(section, {}):
				party[id] = int(party.get(id, 0)) + int(report[section][id])
		for id: String in party:
			if row.party.size() < 4 and int(party[id]) > 0:
				row.party.append([unit_portrait(id, true), format_balance(int(party[id]))])
		var species := str(opponent.get("species", ""))
		var faces: Array = CreatureVisuals.entry(species).get("portraits", []) if not species.is_empty() else []
		var face_path := str(faces[clampi(int(opponent.get("level", 1)), 1, faces.size()) - 1]) if not faces.is_empty() else ""
		row.foe = load(face_path) as Texture2D if not face_path.is_empty() and ResourceLoader.exists(face_path) else null
		row.foe_emblem = UiKit.tex("kit_emb_helm") if row.foe == null else null
		var resources: Dictionary = report.get("rewards", {}).get("resources", {})
		for id in RESOURCE_NAMES:
			if int(resources.get(id, 0)) > 0:
				row.spoils.append([resource_icons.get(id), "+" + short_amount(int(resources[id]))])
		if int(report.get("rewards", {}).get("xp", 0)) > 0:
			row.spoils.append([UiKit.tex("kit_ic_power"), "+%s опыта" % format_balance(int(report.rewards.xp))])
		row.unread = float(report.get("finishedAt", 0.0)) > reports_seen_ms
		row.tooltip_text = "%s · %s" % [str(opponent.get("name", "Цель")), battle_outcome(report)]
		row.accessibility_name = row.tooltip_text
		row.pressed.connect(show_report.bind(report))
		modal_body.add_child(row)
	mark_reports_seen()

static func report_age(milliseconds: float) -> String:
	var minutes := int(maxf(0.0, milliseconds) / 60000.0)
	if minutes < 1:
		return "только что"
	if minutes < 60:
		return "%d мин назад" % minutes
	if minutes < 24 * 60:
		return "%d ч назад" % (minutes / 60)
	var days := minutes / (24 * 60)
	return "вчера" if days == 1 else "%d дн. назад" % days

func battle_outcome(report: Dictionary) -> String:
	return "Победа" if report.outcome == "victory" else "Поражение"

func update_battle_result_notice() -> void:
	var available := not battle_results.pending.is_empty() and Time.get_ticks_msec() >= battle_results.ready_at
	if available and is_instance_valid(stage):
		var report: Dictionary = battle_results.pending[0]
		available = stage.combat_view.frame_time >= stage.combat_view.visual_end(float(report.get("finishedAt",0))) + 1200.0
	result_notice.visible = available and modal.visible and not result_open
	if available and not modal.visible and not relocation_pins.visible and not command_in_progress:
		present_next_battle_result()

func present_next_battle_result() -> void:
	var report := battle_results.next()
	if not report.is_empty():
		show_report(report, true)

func result_label(parent: Container, value: String, font_size: int, color: Color, serif := false) -> Label:
	var label := Label.new()
	label.text = value
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	if serif:
		label.add_theme_font_override("font", TITLE_FONT)
	parent.add_child(label)
	return label

func show_report(report: Dictionary, announced := false) -> void:
	var victory: bool = report.get("outcome") == "victory"
	var title := "Победа" if victory else "Отряд потерпел поражение"
	open_modal(title, "result")
	var heading := HBoxContainer.new()
	modal_body.add_child(heading)
	var spacer := Control.new()
	spacer.custom_minimum_size.x = 48
	heading.add_child(spacer)
	var sigil := Control.new()
	sigil.name = "ReportSigil"
	sigil.custom_minimum_size = Vector2(0, 74)
	sigil.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sigil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sigil_emblem: String = v6_panels.script_of(REPORT_ROW).badge_of("victory" if victory else str(report.get("outcome", "defeat")))[2]
	sigil.draw.connect(func():
		var d := 72.0
		var centre := Vector2(sigil.size.x * 0.5, 37.0)
		sigil.draw_circle(centre + Vector2(0, 3), d * 0.5 + 2.0, Color(0, 0, 0, 0.4), true, -1.0, true)
		sigil.draw_texture_rect(UiKit.tex("kit_rail_on" if victory else "kit_rail"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false)
		sigil.draw_texture_rect(UiKit.tex(sigil_emblem), Rect2(centre - Vector2(d, d) * 0.29, Vector2(d, d) * 0.58), false))
	heading.add_child(sigil)
	var back := close_modal if announced else show_reports
	# Kit bronze medallion (the result sheet has no header band of its own).
	var dismiss := UiKit.close_button(back)
	heading.add_child(dismiss)
	dismiss.tooltip_text = "Закрыть"
	dismiss.accessibility_name = "Закрыть результат боя"
	result_label(modal_body, title, 37, Color("#f1d28c"), true)
	var opponent: Dictionary = report.get("creature", {})
	result_label(modal_body, "%s · уровень %d" % [opponent.get("name", "Цель"), int(opponent.get("level", 1))], 21, Color("#becab2"))
	var stats := HBoxContainer.new()
	stats.add_theme_constant_override("separation", 9)
	modal_body.add_child(stats)
	for section in [["surviving", "В строю", Color("#9fe08f")], ["wounded", "Ранены", Color("#f0c76a")], ["dead", "Погибли", Color("#f08a7a")]]:
		var box := PanelContainer.new()
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		box.add_theme_stylebox_override("panel", report_tile_style())
		stats.add_child(box)
		var labels := VBoxContainer.new()
		labels.add_theme_constant_override("separation", 0)
		box.add_child(labels)
		result_label(labels, format_balance(total_units(report.get(section[0], {}))), 31, section[2], true)
		result_label(labels, section[1], 15, Color("#d8c7a4"))
	# Each unit of the party: its portrait, then standing, wounded and fallen.
	var unit_ids: Array = []
	for section in ["surviving", "wounded", "dead"]:
		for unit_id in report.get(section, {}):
			if not unit_id in unit_ids:
				unit_ids.append(unit_id)
	if not unit_ids.is_empty():
		var table := VBoxContainer.new()
		table.name = "ReportUnits"
		table.add_theme_constant_override("separation", 4)
		modal_body.add_child(table)
		var header := HBoxContainer.new()
		header.add_theme_constant_override("separation", 10)
		table.add_child(header)
		var indent := Control.new()
		indent.custom_minimum_size.x = 40
		header.add_child(indent)
		var header_name := result_label(header, "Отряд", 14, Color("#b9a580"))
		header_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
		header_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		for caption in ["в строю", "ранены", "погибли"]:
			result_label(header, caption, 14, Color("#b9a580")).custom_minimum_size.x = 64
		for unit_id in unit_ids:
			var line := HBoxContainer.new()
			line.add_theme_constant_override("separation", 10)
			table.add_child(line)
			unit_art(line, str(unit_id), Vector2(40, 40))
			var unit_name := result_label(line, str(unit_for_id(str(unit_id)).get("name", unit_id)), 16, Color("#efe2c6"))
			unit_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
			unit_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			for section in [["surviving", Color("#9fe08f")], ["wounded", Color("#f0c76a")], ["dead", Color("#f08a7a")]]:
				var count := result_label(line, format_balance(int(report.get(section[0], {}).get(unit_id, 0))), 17, section[1])
				count.custom_minimum_size.x = 64
	# Attack on a city: what its wall and watchtower added to the defenders.
	var fort: Variant = report.get("fortification")
	if fort is Dictionary:
		var walls_text := "Стены города · ур. %d" % int(fort.get("wallLevel", 0)) if int(fort.get("wallLevel", 0)) > 0 else "Частокол города"
		result_label(modal_body, "%s: защита +%d%%, мощь укреплений %s · оборона %s против %s" % [walls_text, int(fort.get("defencePct", 0)),
			format_balance(int(fort.get("fortPower", 0))), format_balance(int(fort.get("defenderPower", 0))), format_balance(int(fort.get("attackerPower", 0)))],
			15, Color("#e5c57d")).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var rewards: Dictionary = report.get("rewards", {})
	if rewards.get("delivery", "") == "return":
		row(modal_body, "Добыча поступает в город только по прибытии отряда.")
	var resources: Dictionary = rewards.get("resources", {})
	var items: Dictionary = rewards.get("items", {})
	var loot := HFlowContainer.new()
	loot.name = "BattleLoot"
	loot.alignment = FlowContainer.ALIGNMENT_CENTER
	modal_body.add_child(loot)
	for id in RESOURCE_NAMES:
		if int(resources.get(id, 0)) > 0:
			add_reward_chip(loot, RESOURCE_NAMES[id], int(resources[id]), id)
	var item_names := {"horn":"Рог", "velkor-horn":"Рог Велькора", "hides":"Шкуры", "claws":"Когти",
		"antlers":"Рога", "bones":"Кости", "armor_plates":"Пластины", "dusk_crystal":"Сумеречный кристалл",
		"stone":"Камень", "iron":"Железо",
		"forest_crystal":"Лесной кристалл", "stone_crystal":"Каменный кристалл", "ember_crystal":"Огненный кристалл"}
	for id in items:
		if int(items[id]) > 0:
			add_reward_chip(loot, item_names.get(id, id), int(items[id]))
	if int(rewards.get("xp", 0)) > 0:
		add_reward_chip(loot, "Опыт", int(rewards.xp))
	loot.visible = loot.get_child_count() > 0
	# The spoils right under the figures, the per-unit table after them.
	modal_body.move_child(loot, stats.get_index() + 1)
	var wounded := total_units(report.get("wounded", {}))
	var dead := total_units(report.get("dead", {}))
	var recovery := "Уцелевшие пополнят гарнизон после возвращения."
	if wounded > 0:
		recovery = "Раненые учтены в летописи. Для лечения нужен лазарет."
	elif dead > 0:
		recovery = "Погибших можно заменить, обучив воинов в казармах."
	result_label(modal_body, recovery, 17, Color("#becab2")).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if wounded > 0:
		button(modal_body, "Открыть раненых и лечение", show_hospital)
	modal_footer.show()
	var continue_button := panel_action(modal_footer, "Продолжить", back)
	continue_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL

static var report_tile: StyleBox
static var reward_plate: StyleBox

## Dark enamel tile of a report figure in a bronze rim.
static func report_tile_style() -> StyleBox:
	if report_tile == null:
		var tile := StyleBoxFlat.new()
		tile.bg_color = Color("#1f1710")
		tile.border_color = Color("#b48a4a")
		tile.set_border_width_all(2)
		tile.set_corner_radius_all(8)
		tile.content_margin_top = 6
		tile.content_margin_bottom = 6
		tile.shadow_color = Color(0, 0, 0, 0.35)
		tile.shadow_size = 3
		report_tile = tile
	return report_tile

func add_reward_chip(parent: Container, name: String, amount: int, icon := "") -> void:
	# An oak plate with the resource icon and the credited amount (the label text is what
	# the reward checks read: «Еда +1 500»).
	if reward_plate == null:
		reward_plate = UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(24, 4, 24, 6))
	var chip := PanelContainer.new()
	chip.add_theme_stylebox_override("panel", reward_plate)
	parent.add_child(chip)
	var content := HBoxContainer.new()
	content.add_theme_constant_override("separation", 6)
	chip.add_child(content)
	if not icon.is_empty():
		add_resource_icon(content, icon, 26)
	elif name == "Опыт":
		var star := TextureRect.new()
		star.texture = UiKit.tex("kit_ic_power")
		star.custom_minimum_size = Vector2(24, 24)
		star.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		star.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		star.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		content.add_child(star)
	var value := result_label(content, "%s +%s" % [name, format_balance(amount)], 17, UiKit.GOLD)
	value.add_theme_font_override("font", UiKit.LABEL_FONT)

func accept(response: Dictionary) -> void:
	if not loopback and response.has("city") and response.get("economy_version", "") != "DRENOVAR-V6-C1.0":
		show_error({"error":"Сервер не поддерживает эту тестовую версию V6. Прогресс не изменён."})
		return
	if response.has("v6") and state.has("v6") and response.get("playerId", "") == state.get("playerId", "") and int(response.v6.revision) < int(state.v6.revision):
		stale_responses += 1
		return
	if not response.has("city") or not response.has("world"):
		return
	# A late answer (a poll sent before a command, a replayed command receipt) never
	# replaces a newer confirmed state: timers would run again, felled trees return.
	if not showing_cached_state and state.has("serverTime") and str(response.get("playerId", "")) == str(state.get("playerId", "")) \
			and float(response.get("serverTime", 0.0)) < float(state.serverTime):
		stale_responses += 1
		return
	state = response
	if v6_panels.enabled() and v6_panels.catalogue.is_empty() and not v6_panels.catalogue_loading:
		v6_panels.load_catalogue.call_deferred()
	v6_protocol_confirmed = response.get("economy_version", "") == "DRENOVAR-V6-C1.0"
	# Orders sent but not in this answer yet (a poll that left before them): their
	# local effect stays (costs of works just ordered, speedups in flight).
	for slot in pending_works:
		var predicted: Dictionary = pending_works[slot]
		if not predicted.get("cost", {}).is_empty() and not prediction_settled(predicted):
			spend_locally(predicted.cost)
	for entry in speed_overrides:
		apply_speed_override(entry)
	player_id = state.playerId
	showing_cached_state = false
	confirmed_server_ms = float(state.get("serverTime", 0.0))
	confirmed_local_ms = Time.get_unix_time_from_system() * 1000.0
	battle_results.observe(player_id, state.get("reports", []))
	note_server_time(float(state.serverTime))
	remember_state()
	refresh_hud()
	if is_instance_valid(stage):
		stage.present(state)
	forest_state_changed() # FOREST_RESCUE hook: ingest state.adventure
	refresh_economy()
	if starter_panel_open and not command_in_progress and state.get("starterEligible71", false):
		show_starter_goals()
	if relocation_pins.visible:
		relocation_pins.queue_redraw()
	if not placing.is_empty() and is_instance_valid(stage) and map_name == "city":
		var plots := []
		for marker in stage.empty_plots:
			if placing.has("move") and not plot_cleared(marker.item):
				continue
			plots.append({"position": marker.position, "plot": marker.item, "cleared": plot_cleared(marker.item)})
		placing.plots = plots
		var current: Dictionary = nearest_placement_plot(placing.free)
		if not current.is_empty() and current.gap < 0.5:
			placing.cleared = current.cleared
		elif placement_finger == -1:
			placing.position = Vector3.INF
		refresh_placement()

func remember_state(force := false) -> void:
	# Throttled: the copy only has to be recent, and writing it costs a few ms.
	if loopback or session.is_empty() or showing_cached_state or not state.has("city"):
		return
	var now := Time.get_ticks_msec()
	if not force and now - state_saved_msec < STATE_SAVE_INTERVAL_MSEC:
		state_save_pending = true
		return
	state_saved_msec = now
	state_save_pending = false
	SessionStore.save_state(session, state, server_offset, endpoint)

## An error, said calmly and with what to do: the server's own words, a hint where the
## words alone leave the player stuck, and the amber medallion (not red alarm text).
func calm_error(text: String) -> String:
	var hints := {"Ответ сервера не удалось прочитать.": "Сервер ответил неразборчиво. Попробуйте ещё раз через минуту.",
		"Сервер недоступен": "Сервер сейчас недоступен. Мы повторим сами; можно продолжать играть."}
	return hints.get(text, text)

func show_error(response: Dictionary) -> void:
	if int(response.get("httpStatus", 0)) == 426:
		client_update_required = true
		restoring_session = false
		show_account.call_deferred()
	message_tone = "warn"
	message_warn_text = calm_error(str(response.get("error","Ответ сервера не удалось прочитать.")))
	message.text = message_warn_text
	if modal.visible:
		modal_status.text = message.text
		modal_status.show()

# Orders that start visible work at once (the window closes and the work is
# shown immediately); the server confirms in the background.
const INSTANT_ACTIONS := ["tree", "site", "upgrade", "collect", "build", "clear", "area", "place", "level"]
signal command_settled
var pending_works := {}
var shown_job := {}
# Every shown work (one per busy worker): forest jobs and construction sites.
var shown_jobs: Array = []
var shown_sites: Array = []
var next_due_poll_msec := 0
var due_poll_streak := 0
var shown_site := {}
var stale_responses := 0
# Latest confirmed server state: its serverTime and the local wall clock when it
# arrived. Timers count from it, so zero on the phone is never before the server's
# own end (the answer's time is older than now by the network delay, never newer).
var latency_samples: Array = []
# Duration of a felling as the server sets it (v92: 5 s; server patch: 10 s).
var tree_job_ms := 0.0
var polls_in_flight := 0
var confirmed_server_ms := 0.0
var confirmed_local_ms := 0.0
var timer_clock_last := 0.0
var queued_commands := 0
var command_retries := 0

func instant_order(order: Dictionary) -> bool:
	return order.get("kind", "") in ["kingdom", "resource", "legacyBuilding"] and order.get("action", "") in INSTANT_ACTIONS

## True when an order or a quote would take a building past MAX_OPEN_BUILDING_LEVEL.
func beyond_open_level(order: Variant) -> bool:
	if not order is Dictionary:
		return false
	match str(order.get("kind", "")):
		"v6", "v6quote":
			var intent: Variant = order.get("intent", {})
			return intent is Dictionary and str(intent.get("kind", "")) == "construction" and int(intent.get("target", 0)) > MAX_OPEN_BUILDING_LEVEL
		"kingdom":
			return str(order.get("action", "")) == "upgrade" and int(order.get("expectedLevel", 0)) >= MAX_OPEN_BUILDING_LEVEL
		"legacyBuilding":
			return str(order.get("action", "")) == "level" and int(order.get("level", 0)) > MAX_OPEN_BUILDING_LEVEL
	return false

## Upgrades past the open level that reached the client's last guard (nothing is sent), and the
## quotes actually sent (tests and diagnostics).
var capped_requests := 0
var quotes_sent := 0

func command(order: Dictionary, after_success := Callable()) -> bool:
	if beyond_open_level(order):
		capped_requests += 1
		message.text = SOON_LINE
		return false
	if is_v6_server() and order.get("kind", "") not in ["v6", "v6quote", "v6catalog", "deploy", "worldMarch", "recall", "retreat", "editNames", "relocateCity", "resource", "speedup", "starter71", "v6collect"]:
		if not await ensure_v6_ready():
			return false
		if order.get("kind", "") == "trade":
			await v6_panels.trade()
		elif order.get("kind", "") == "cancelTraining":
			await v6_panels.queues()
		elif str(order.get("buildingId", "")) != "":
			await v6_panels.inspect_instance(str(order.buildingId))
		else:
			await v6_panels.catalog()
		return false
	var instant := instant_order(order) and not after_success.is_valid()
	if instant:
		predict_work(order)
		if modal.visible:
			close_modal()
		action_ring.close()
	# Orders run one at a time: a second tap waits for the first one instead of
	# being silently dropped.
	if command_in_progress:
		queued_commands += 1
		while command_in_progress:
			await command_settled
		queued_commands -= 1
	command_in_progress = true
	diagnostics.log_event("command", {"kind": str(order.get("kind", "")), "action": str(order.get("action", ""))},
		Time.get_unix_time_from_system())
	var generation := modal_generation
	# Only mention the server when it is actually slow: most commands answer well
	# under half a second and a flashing status line reads as a problem.
	if not instant:
		var slow_notice := get_tree().create_timer(0.45)
		slow_notice.timeout.connect(func():
			if command_in_progress and generation == modal_generation and modal.visible:
				modal_status.text = "Отправляем…"
				modal_status.show())
	var signature := JSON.stringify(order)
	var key: String = str(order.get("requestId", ""))
	if key.is_empty():
		key = retry_keys.get(signature, Crypto.new().generate_random_bytes(16).hex_encode())
	var first_sent := Time.get_ticks_msec()
	var response: Dictionary = await request("command", order, key)
	# Quiet retries with the same idempotency key and body (the server never applies an
	# order twice): a dropped mobile connection is usually back within a second (rule 10).
	for pause in COMMAND_RETRY_DELAYS:
		if not transient_failure(response) or Time.get_ticks_msec() - first_sent + int(pause * 1000.0) > COMMAND_RETRY_WINDOW_MS:
			break
		command_retries += 1
		await get_tree().create_timer(pause).timeout
		response = await request("command", order, key)
	if transient_failure(response):
		retry_keys[signature] = key
	else:
		retry_keys.erase(signature)
	if not response.has("city"):
		last_command_error = str(response.get("error", "сервер не ответил"))
		command_in_progress = false
		command_settled.emit()
		if instant:
			forget_prediction(order)
			message.text = "Не выполнено: " + str(response.get("error", "сервер не ответил"))
		elif generation == modal_generation:
			show_error(response)
		return false
	accept(response)
	command_in_progress = false
	command_settled.emit()
	if instant:
		# The answer is in: a forecast the state does not carry goes after a moment.
		for slot in pending_works:
			if pending_works[slot].get("order", {}) == order:
				pending_works[slot].answered = Time.get_ticks_msec()
		message.text = ""
		return true
	if generation == modal_generation:
		modal_status.hide()
		if after_success.is_valid():
			after_success.call()
		else:
			close_modal()
	message.text = "Действие выполнено"
	return true

# Local forecast of the work an order starts, shown until the server state takes over.
# The countdown runs at once with the server's own duration (the same terms the
# server uses), so «Улучшить» starts the work on the tap; the server's order replaces
# the forecast when its answer arrives (the bar never moves backward: bar_floor).
# Slots: "tree"/"tree2" (forest), "site"/"site2" (construction), one per worker.
func predict_work(order: Dictionary) -> void:
	var now := server_time()
	var action: String = order.get("action", "")
	match action:
		"tree", "site", "area":
			if order.get("kind", "") != "resource":
				return
			var seconds := 5.0
			for tree in stage.selectable_trees if is_instance_valid(stage) else []:
				if tree.id == order.get("id", ""):
					seconds = (tree_job_ms if tree_job_ms > 0.0 else float(tree.get("durationMs", 5000))) / 1000.0
			if tree_job_ms > 0.0:
				seconds = tree_job_ms / 1000.0
			pending_works[free_slot("tree")] = {"tree": str(order.id) if action != "area" else "", "started": now,
				"ends": now + seconds * 1000.0, "order": order, "sent": Time.get_ticks_msec()}
		"upgrade", "build", "place", "level":
			var key := str(order.get("buildingId", order.get("plotId", "")))
			var type := str(order.get("type", ""))
			var seconds := 30.0
			var cost := {}
			var expected := -1
			if action == "upgrade":
				for building in state.city.buildings:
					if str(building.id) == str(order.get("buildingId", "")):
						type = str(building.type)
						expected = int(order.get("expectedLevel", building.level))
						var upgrades: Array = data.buildingTerms.get(type, {}).get("upgrades", [])
						if expected >= 1 and expected <= upgrades.size():
							seconds = float(upgrades[expected - 1].seconds)
							cost = upgrades[expected - 1].cost
			elif data.buildingTerms.get(type, {}).has("seconds"):
				seconds = float(data.buildingTerms[type].seconds)
				if action == "build":
					cost = data.buildingTerms[type].get("cost", {})
			pending_works[free_slot("site")] = {"key": key, "building": str(order.get("buildingId", "")), "plot": str(order.get("plotId", "")),
				"type": type, "started": now, "ends": now + seconds * 1000.0, "order": order, "cost": cost,
				"level": expected, "sent": Time.get_ticks_msec()}
			# The cost leaves the stores at once (the server charges the same terms).
			spend_locally(cost)
	if is_instance_valid(stage) and map_name == "city":
		refresh_hud()

func free_slot(prefix: String) -> String:
	var index := 1
	while pending_works.has(prefix if index == 1 else prefix + str(index)):
		index += 1
	return prefix if index == 1 else prefix + str(index)

func spend_locally(cost: Dictionary, sign := 1) -> void:
	for resource in cost:
		var amount := int(cost[resource]) * sign
		if amount == 0:
			continue
		if resource == "wood":
			state.city.progress.wood = maxi(0, int(state.city.progress.get("wood", 0)) - amount)
		elif state.city.get("demo") is Dictionary and state.city.demo.get("wallet") is Dictionary:
			state.city.demo.wallet[resource] = maxi(0, int(state.city.demo.wallet.get(resource, 0)) - amount)

func forget_prediction(order: Dictionary) -> void:
	# A refused order removes its forecast (same action on the same target).
	for slot in pending_works.keys():
		var predicted: Dictionary = pending_works[slot].get("order", {})
		if predicted.get("action") == order.get("action") and predicted.get("id") == order.get("id") and \
				predicted.get("plotId") == order.get("plotId") and predicted.get("buildingId") == order.get("buildingId"):
			# The cost taken from the stores on the tap comes back.
			spend_locally(pending_works[slot].get("cost", {}), -1)
			pending_works.erase(slot)
	refresh_hud()

var tree_ids := {}

# The server job names its tree under some field; any value that is a known tree
# id (forest "tree-N" or village "village-tree-N") identifies it.
func job_tree_id(job: Variant) -> String:
	if not job is Dictionary or not is_instance_valid(stage):
		return ""
	if tree_ids.size() != stage.selectable_trees.size():
		tree_ids.clear()
		for tree in stage.selectable_trees:
			tree_ids[tree.id] = true
	for field in ["treeId", "tree", "id", "target", "targetId", "resourceId"]:
		var value: Variant = job.get(field)
		if value is String and tree_ids.has(value):
			return value
	for value in job.values():
		if value is String and tree_ids.has(value):
			return value
	return ""

# Whether the server state already carries (or has finished) the predicted work.
func prediction_settled(predicted: Dictionary) -> bool:
	var order: Dictionary = predicted.get("order", {})
	if predicted.has("tree"):
		var target := str(order.get("id", ""))
		for job in server_jobs():
			if str(job.get("target", "")) == target or (not predicted.tree.is_empty() and job_tree_id(job) == predicted.tree):
				return true
		var progress: Dictionary = state.city.get("progress", {})
		return order.get("action") == "tree" and target in progress.get("felled", []) or \
			order.get("action") == "area" and target in progress.get("cleared", []) or \
			order.get("action") == "site" and target in progress.get("sites", [])
	for server_order in construction_orders():
		if not str(predicted.building).is_empty() and str(server_order.get("buildingId", "")) == predicted.building:
			return true
		if not str(predicted.plot).is_empty() and str(server_order.get("plotId", "")) == predicted.plot:
			return true
	for building in state.city.buildings:
		if not str(predicted.building).is_empty() and str(building.id) == predicted.building and int(predicted.get("level", -1)) >= 1 \
				and int(building.level) > int(predicted.level):
			return true
		# A level set directly (older settlements without construction orders).
		if order.get("action") == "level" and str(building.id) == str(order.get("buildingId", "")) and int(building.level) == int(order.get("level", -1)):
			return true
		if not str(predicted.plot).is_empty() and str(building.get("plotId", "")) == predicted.plot:
			return true
	return false

# What the city shows as work right now: the server's jobs and orders, then the
# local forecasts not yet in the server state. Returns [jobs, sites].
func current_works(now: float) -> Array:
	var jobs: Array = []
	var sites: Array = []
	for slot in pending_works.keys():
		var predicted: Dictionary = pending_works[slot]
		# Already in the server state, or answered and still not there: drop the
		# forecast. While its order is on the way it stays (a slow link is no reason
		# to take the work off the screen).
		var answered := int(predicted.get("answered", 0))
		if prediction_settled(predicted) or (answered > 0 and Time.get_ticks_msec() - answered > 3000) \
				or Time.get_ticks_msec() - int(predicted.get("sent", Time.get_ticks_msec())) > 120000:
			pending_works.erase(slot)
	for server_job in server_jobs():
		var server_tree := job_tree_id(server_job)
		if server_tree.is_empty() or not server_job.has("endsAt"):
			continue
		# Only the server's job runs the confirmed countdown: its own start and end.
		var ends := float(server_job.endsAt)
		var job := {"tree": server_tree, "started": float(server_job.get("startedAt", ends - 5000.0)), "ends": ends,
			"confirmed": true, "key": server_tree}
		tree_job_ms = ends - float(job.started)
		jobs.append(job)
	var sources: Array = []
	for order in construction_orders():
		if order.get("kind", "") == "clear":
			continue
		sources.append({"key": str(order.get("buildingId", order.get("plotId", ""))), "kind": str(order.get("kind", "")),
			"type": str(order.get("type", "")), "ends": float(order.get("endsAt", now)),
			"started": float(order.get("startedAt", order.get("startsAt", 0.0))),
			"confirmed": true, "id": str(order.get("requestId", "")), "plot": str(order.get("plotId", ""))})
	for slot in pending_works:
		var predicted: Dictionary = pending_works[slot]
		if predicted.has("tree"):
			if not str(predicted.tree).is_empty():
				# Sent, not yet confirmed: the worker walks to the tree, the timer runs.
				var job: Dictionary = predicted.duplicate()
				job.confirmed = false
				job.predicted = true
				job.key = str(predicted.tree)
				jobs.append(job)
		else:
			# Sent, not yet confirmed: scaffolding and builders, the timer runs.
			sources.append({"key": predicted.key, "kind": str(predicted.order.get("action", "")), "type": str(predicted.get("type", "")),
				"ends": float(predicted.ends), "started": float(predicted.started), "confirmed": false, "predicted": true,
				"plot": str(predicted.get("plot", ""))})
	for source in sources:
		var site := site_view(source)
		if not site.is_empty():
			sites.append(site)
	return [jobs, sites]

func site_view(source: Dictionary) -> Dictionary:
	if not is_instance_valid(stage):
		return {}
	var site := {}
	var plot_id: String = source.plot if not str(source.get("plot", "")).is_empty() else source.key
	var existing := {}
	for building in state.city.buildings:
		if str(building.id) == source.key:
			plot_id = str(building.plotId)
			existing = building
	if source.started <= 0.0:
		var terms: Dictionary = data.buildingTerms.get(source.type if existing.is_empty() else str(existing.type), {})
		source.started = float(source.ends) - 1000.0 * float(terms.get("seconds", 30))
	if stage.work_sites.has(plot_id):
		site = source
		site.position = stage.work_sites[plot_id]
		# A new building rises inside the scaffolding; an upgrade keeps the building.
		if existing.is_empty() and data.types.has(source.type):
			var asset: Dictionary = data.models[data.types[source.type]]
			site.model = asset.path
			site.scale = float(asset.scale)
			# A reworked level I rises as its own scene (architecture-v2).
			var first_level: Variant = data.get("levelModels", {}).get(source.type, {}).get("1")
			if first_level is Dictionary:
				site.model = first_level.path
				site.scale = float(first_level.get("scale", 1.0))
		site.upgrade = not existing.is_empty()
		# Build 54: an upgrade rebuilds on the plot from the current level scene to the
		# next one (what stays, what is taken down, what is added), so both are named.
		if site.upgrade and str(source.get("kind", "")) in ["upgrade", "level", ""]:
			var level := int(existing.get("level", 1))
			var before: Array = stage.level_visual(str(existing.type), level)
			var after: Array = stage.level_visual(str(existing.type), level + 1)
			if not before.is_empty() and not after.is_empty():
				site.from_model = stage.level_model_for(str(existing.type), level + 1).get("upgrade_from_path", before[0])
				site.from_scale = before[1]
				site.to_model = after[0]
				site.to_scale = after[1]
				site.type = str(existing.type)
				# Build 59: a level may lay out its own building site (scaffolding round
				# the part that rises, piles and hoist on free ground).
				var layout: Variant = stage.level_model_for(str(existing.type), level + 1).get("site")
				if layout is Dictionary:
					site.layout = layout
		elif not site.upgrade:
			site.type = str(source.type)
		# "Walls and gate" stands in the main gate of the city wall: the works go there.
		var site_type: String = str(source.type) if existing.is_empty() else str(existing.type)
		if stage.city_base_type(site_type) == "SUP-03" and stage.walls.visible:
			var gate_level := maxi(1, int(existing.get("level", 1)))
			var gate_scale: float = stage.gate_scene_scale(gate_level)
			var out: Vector3 = stage.walls.main_gate_outward
			var half := 5.6 if site.upgrade else 4.6
			var tops := [4.1, 4.9, 7.3, 7.3, 8.6]
			var top: float = float(tops[mini(gate_level, 5) - 1])
			if gate_level >= 6:
				var gate_bounds: Dictionary = stage.level_model_for(site_type, gate_level).get("bounds", {})
				if gate_bounds.has("max"):
					top = float(gate_bounds.max[1])
			site.position = stage.walls.main_gate
			site.yaw = atan2(out.x, out.z)
			site.frame = Vector3(5.9 * gate_scale / half + 0.1, maxf(1.0, top * gate_scale / 7.4 * 1.08), 1.9 * gate_scale / half)
			site.erase("model")
	return site

# Each crew keeps its work: a work that is already shown by one crew stays there
# when another work finishes (the builders do not jump between sites).
var crew_keys := ["", "", "", ""]

func assign_crews(items: Array, index: int) -> Array:
	var crews := [{}, {}]
	var placed := {}
	for crew in 2:
		var wanted: String = crew_keys[crew * 2 + index] if crew_keys.size() > crew * 2 + index else ""
		for item in items:
			if not wanted.is_empty() and str(item.get("key", item.get("tree", ""))) == wanted and not placed.has(wanted):
				crews[crew] = item
				placed[wanted] = true
	for item in items:
		var key := str(item.get("key", item.get("tree", "")))
		if placed.has(key):
			continue
		for crew in 2:
			if crews[crew].is_empty():
				crews[crew] = item
				placed[key] = true
				break
	for crew in 2:
		crew_keys[crew * 2 + index] = str(crews[crew].get("key", crews[crew].get("tree", "")))
	return crews

# Clock for timers: server time, but never ahead of the latest confirmed answer plus
# the wall time since it arrived, and never backward. After the app is suspended or
# the clock jumps, the next answer sets it again.
func timer_now() -> float:
	var estimate := server_time()
	if confirmed_local_ms > 0.0:
		# Only small differences (clock slew, network delay) are taken from the last
		# answer; a large one means that answer's clock is not the live one.
		var anchored := confirmed_server_ms + Time.get_unix_time_from_system() * 1000.0 - confirmed_local_ms
		if anchored < estimate and estimate - anchored < 5000.0:
			estimate = anchored
	if absf(estimate - timer_clock_last) > 60000.0 or estimate > timer_clock_last:
		timer_clock_last = estimate
	return timer_clock_last

# Every confirmed timer that has reached zero (felling, construction, the first
# order of each training queue, healing): the server is asked at once, then every
# 0.7 s for at most a minute, until its state no longer carries the finished work.
func ask_server_at_zero(works: Array) -> void:
	if not connected() or player_id.is_empty():
		return
	var now := timer_now()
	var ends: Array = []
	for work in works:
		if not work.is_empty() and work.get("confirmed", true):
			ends.append(float(work.ends))
	for queue in state.city.get("military", {}).get("queues", {}).values():
		if queue is Array and not queue.is_empty():
			ends.append(float(queue[0].get("endsAt", INF)))
	for healing in state.get("healing", []):
		ends.append(float(healing.get("endsAt", INF)))
	# An army reaching its creature (or ending the fight): the server starts the
	# battle only when asked, so ask at that moment instead of the next routine poll.
	for army in state.get("armies", []) + state.get("world", {}).get("armies", []):
		if army.status in ["outbound", "fighting"] and str(army.get("owner", player_id)) == player_id:
			var finish: Variant = march_finish(army)
			if finish != null:
				ends.append(float(finish))
	var due := ends.any(func(at): return now >= at and now < at + 60000.0)
	if not due:
		due_poll_streak = 0
		return
	var now_msec := Time.get_ticks_msec()
	if now_msec >= next_due_poll_msec:
		next_due_poll_msec = now_msec + 700
		due_poll_streak += 1
		poll_account_state(true)

# Round trip to the server now (75th percentile of the last answers): a timer on
# screen runs this much longer than the server's end, so it reaches zero when the
# answer that reports the work done arrives, not before it.
func expected_latency_ms() -> float:
	if latency_samples.is_empty():
		return 350.0
	var sorted: Array = latency_samples.duplicate()
	sorted.sort()
	return clampf(float(sorted[int(floor((sorted.size() - 1) * 0.75))]), 0.0, 6000.0)

func display_end(ends_at: float) -> float:
	return ends_at + expected_latency_ms()

func server_reachable() -> bool:
	return connected() and not connection_notice_due() and not showing_cached_state

# What a timer shows at and after zero: the server is asked; without a link the
# result is not presented as done.
func timer_end_label() -> String:
	return "Завершаем…" if server_reachable() else "Нет связи · ждём сервер"

func is_v6_server() -> bool:
	return endpoint == LIVE_SERVER or v6_protocol_confirmed or v6_panels.enabled()

func ensure_v6_ready(force_refresh := false) -> bool:
	if v6_panels.enabled() and not showing_cached_state and not force_refresh:
		return true
	if not connected():
		show_account()
		return false
	var response := await send_request("state" if loopback else "native/game/state", null, false)
	if response.has("city"):
		accept(response)
	if v6_panels.enabled() and not showing_cached_state:
		return true
	if response.get("needsSettlement", false) or int(response.get("httpStatus",0)) == 401:
		show_account()
	else:
		show_error(response if response.has("error") else {"error":"Не удалось загрузить актуальное состояние города. Повторите подключение."})
	return false

func request(path: String, payload: Variant = null, idempotency_key := "") -> Dictionary:
	if path == "command" and beyond_open_level(payload):
		capped_requests += 1
		return {"ok": false, "capped": true, "reason": {"message": SOON_LINE}}
	if not connected():
		return {"error":"Сначала войди в аккаунт."}
	if payload is Dictionary and payload.get("kind", "") == "v6quote":
		quotes_sent += 1
	var query_only: bool = payload is Dictionary and payload.get("kind", "") in ["v6catalog", "v6quote"]
	var response := await send_request(path if loopback else "native/game/" + path, payload, not query_only, 20.0 if query_only else 12.0, idempotency_key)
	if not loopback and response.get("httpStatus", 0) == 401:
		# One refused command must not sign the player out: only forget the saved
		# login when the session itself is rejected by the state endpoint too.
		var check := await send_request("native/game/state", null, false, 6.0)
		if check.get("httpStatus", 0) == 401:
			reset_session()
		elif check.has("city"):
			accept(check)
	return response

func send_request(path: String, payload: Variant = null, foreground := true, timeout_seconds := 12.0, idempotency_key := "", host := "", is_current := Callable(), extra_headers := PackedStringArray()) -> Dictionary:
	# 1022: a tap never waits for (or is refused by) another request in flight.
	if foreground:
		foreground_in_flight += 1
		busy = true
		request_generation += 1
	# Rule 4/6: a command, session, login or profile answer replaces the cached tagged state.
	if payload != null and host.is_empty() and not path.ends_with("march-preview") \
			and not (payload is Dictionary and payload.get("kind", "") in ["v6catalog", "v6quote"]):
		drop_state_tag()
	var headers := PackedStringArray(["Accept: application/json", "Accept-Encoding: gzip"])
	if host.is_empty():
		headers.append("X-Drenovar-Economy: DRENOVAR-V6-C1.0")
		headers.append("X-Drenovar-Client: godot")
		headers.append("X-Drenovar-Client-Build: " + str(ProjectSettings.get_setting("application/config/build_number", "")))
	# A request to another server (the old one, during a transfer) carries none of
	# this server's credentials.
	var base := endpoint if host.is_empty() else host
	var pool: ApiPool = api if host.is_empty() else old_api
	if host.is_empty():
		if player_id != "":
			headers.append("X-Drenovar-Player: "+player_id)
		if not session.is_empty():
			headers.append("X-Drenovar-Session: " + session)
		if not staging_key.is_empty():
			headers.append("X-Drenovar-Staging-Key: " + staging_key)
	if payload != null:
		headers.append("Content-Type: application/json")
		headers.append("Origin: "+base)
		var request_key := idempotency_key
		if request_key.is_empty() and path.get_file() == "command" and payload is Dictionary:
			request_key = str(payload.get("requestId", ""))
		if request_key.is_empty():
			request_key = Crypto.new().generate_random_bytes(16).hex_encode()
		headers.append("Idempotency-Key: "+request_key)
	headers.append_array(extra_headers)
	# Kept-alive connections: a command no longer pays for a new TCP and TLS handshake.
	pool.configure(base)
	var started_us := Time.get_ticks_usec()
	var result: Array = await pool.request(HTTPClient.METHOD_GET if payload == null else HTTPClient.METHOD_POST, "/api/" + path,
		headers, "" if payload == null else JSON.stringify(payload), timeout_seconds, 8 * 1024 * 1024, foreground, is_current)
	# An obsolete read-only preview is cancelled deliberately. It must not report
	# a network outage after its window closed or a newer request succeeded.
	if is_current.is_valid() and not is_current.call():
		if foreground:
			foreground_in_flight = maxi(0, foreground_in_flight - 1)
			busy = foreground_in_flight > 0
		return {"cancelled":true}
	var elapsed_ms := (Time.get_ticks_usec() - started_us) / 1000.0
	if result[0] == HTTPRequest.RESULT_SUCCESS and int(result[1]) > 0 and int(result[1]) < 500:
		latency_samples.append(elapsed_ms)
		if latency_samples.size() > 12:
			latency_samples.pop_front()
	if foreground:
		foreground_in_flight = maxi(0, foreground_in_flight - 1)
		busy = foreground_in_flight > 0
		last_command_ms = elapsed_ms
	# An HTTP 5xx response proves that the server was reached. Keep transport and
	# server failures separate; Cloudflare CPU errors are not a lost connection.
	var transport_ok: bool = result[0] == HTTPRequest.RESULT_SUCCESS and int(result[1]) > 0
	diagnostics.network_result(transport_ok, "timeout" if result[0] == HTTPRequest.RESULT_TIMEOUT else ("http_%d" % int(result[1]) if result[0] == HTTPRequest.RESULT_SUCCESS else "transport_%d" % int(result[0])),
		Time.get_unix_time_from_system(), Time.get_ticks_msec())
	if transport_ok:
		diagnostics.server_result(int(result[1]), Time.get_unix_time_from_system())
		if (int(result[1]) >= 200 and int(result[1]) < 300) or int(result[1]) == 304:
			last_ok_msec = Time.get_ticks_msec()
	update_connection_notice()
	if not transport_ok:
		if result[0] == HTTPRequest.RESULT_TIMEOUT:
			return {"error":"Сервер не ответил вовремя. Проверь соединение и повтори.", "transportFailure":true}
		if result[0] == HTTPRequest.RESULT_TLS_HANDSHAKE_ERROR:
			return {"error":"Не удалось установить защищённое соединение с сервером.", "transportFailure":true}
		return {"error":"Сервер недоступен", "transportFailure":true}
	# Rule 2: a 304 (conditional state poll) is a success with an empty body. It is handled
	# before the empty-body and JSON paths, which would read it as an outage.
	if int(result[1]) == 304:
		return {"notModified":true, "httpStatus":304, "etag":header_value(result[2], "etag"),
			"serverTime":header_value(result[2], "x-drenovar-server-time"), "quietUntil":header_value(result[2], "x-drenovar-quiet-until")}
	var response := JSON.new()
	if response.parse(result[3].get_string_from_utf8()) == OK and response.data is Dictionary:
		if int(result[1]) >= 400:
			response.data.httpStatus = result[1]
		elif not extra_headers.is_empty():
			var tag := header_value(result[2], "etag")
			if not tag.is_empty():
				response.data["__etag"] = tag
		return response.data
	# Preserve the status on HTML/empty error pages too, so the existing bounded
	# retry keeps the original Idempotency-Key and cannot create another army.
	return {"error":"Сервер временно перегружен. Повторите попытку." if int(result[1]) >= 500 else "Сервер вернул неожиданный ответ (HTTP %d)." % int(result[1]),
		"httpStatus":int(result[1]), "unreadable":true}

static func header_value(headers: PackedStringArray, name: String) -> String:
	for line in headers:
		var colon := line.find(":")
		if colon > 0 and line.substr(0, colon).strip_edges().to_lower() == name:
			return line.substr(colon + 1).strip_edges()
	return ""

# Rule 10: failures that are repeated silently (the outcome is unknown or the server was busy).
static func transient_failure(response: Dictionary) -> bool:
	if response.get("transportFailure", false) or response.get("unreadable", false):
		return true
	var status := int(response.get("httpStatus", 0))
	if status in [408, 425, 429, 500, 502, 503, 504, 530] or (status >= 520 and status <= 527):
		return true
	return status == 409 and response.get("retryable", false) == true

func drop_state_tag() -> void:
	state_etag = ""
	state_etag_owner = ""
	state_cache = {}
	state_etag_serial += 1

func state_tag_owner() -> String:
	return endpoint + "|" + session + "|" + player_id

# Rule 2/3/12: the cached full answer with the time moved on to the 304's server time.
const CARRY_UNITS := 36000000.0

func advanced_state(server_ms: float) -> Dictionary:
	var next: Dictionary = state_cache.duplicate(true)
	next.serverTime = server_ms
	if next.get("adventure") is Dictionary:
		next.adventure.serverTime = server_ms
	var v6: Variant = next.get("v6")
	if v6 is Dictionary and v6.get("stock") is Dictionary:
		var t := floorf(server_ms / 1000.0)
		var since := t - float(v6.get("server_time", t))
		for resource in v6.stock:
			if bool(v6.get("production_stopped", {}).get(resource, false)):
				continue
			# Counted in the server's carry units (1/36 000 000 of a resource; an hour of production is
			# pph × 10 000 units per second), so a whole stock stays whole: the old "− 1e-7 before the
			# floor" turned an idle 0 into −1 (stone and iron showed −1 after a 304). A rational carry
			# {n, d} (a fraction of one resource) is converted exactly with integers while n × 36e6 fits
			# in 64 bits, so a whole stock stays whole (taking it one unit low showed 401 for 402.0);
			# only larger values fall back to floats, one unit low, so the client never shows more.
			var carry_value: Variant = v6.get("carry", {}).get(resource, 0)
			var carry_units := 0.0
			if carry_value is Dictionary:
				var numerator := str(carry_value.get("n", "0")).strip_edges()
				var denominator := str(carry_value.get("d", "1")).strip_edges()
				if numerator.is_valid_int() and denominator.is_valid_int() and numerator.length() <= 11 \
						and denominator.length() <= 18 and denominator.to_int() > 0 and numerator.to_int() >= 0:
					carry_units = float((numerator.to_int() * int(CARRY_UNITS)) / denominator.to_int())
				elif numerator != "0" and float(denominator) != 0.0:
					carry_units = maxf(0.0, floorf(float(numerator) / float(denominator) * CARRY_UNITS) - 1.0)
			else:
				carry_units = floorf(float(carry_value))
			var gained := float(v6.get("production_per_hour", {}).get(resource, 0)) * since * (CARRY_UNITS / 3600.0)
			var units := float(v6.stock[resource]) * CARRY_UNITS + carry_units + floorf(gained)
			var cap := floorf(float(v6.get("capacities", {}).get(resource, INF)) - float(v6.get("escrow", {}).get(resource, 0)))
			v6.stock[resource] = int(minf(cap, floorf(units / CARRY_UNITS)))
		# The server's projection (v6/game.mjs project): wood in progress, the rest in the wallet.
		if next.get("city") is Dictionary:
			if next.city.get("progress") is Dictionary and v6.stock.has("wood"):
				next.city.progress.wood = v6.stock.wood
			if next.city.get("demo") is Dictionary and next.city.demo.get("wallet") is Dictionary:
				for resource in v6.stock:
					if resource != "wood":
						next.city.demo.wallet[resource] = v6.stock[resource]
	# Creatures walk their patrol with time alone (core.mjs refresh).
	for list: Variant in [next.get("encounters", []), next.get("world", {}).get("encounters", [])]:
		if not list is Array:
			continue
		for encounter: Variant in list:
			if not encounter is Dictionary or str(encounter.get("status", "")) != "alive" or (encounter.get("patrol", []) as Array).size() < 2:
				continue
			var at := creature_point(encounter, server_ms)
			if encounter.get("position") is Dictionary:
				encounter.position.x = at.x
				encounter.position.z = at.y
			if encounter.has("spawnedAt") and encounter.has("behavior"):
				var cycle := fposmod(maxf(0.0, server_ms - float(encounter.spawnedAt)), PATROL_ROUND_MS)
				encounter.behavior = "idle" if cycle < 4000.0 else "roaming"
	return next

## The outage meter's clock (1023): the excess of a long frame is not silence of the server.
func discount_stall() -> void:
	var now := Time.get_ticks_msec()
	if link_frame_msec > 0 and now - link_frame_msec > LINK_FRAME_CAP_MS:
		last_ok_msec = mini(now, last_ok_msec + now - link_frame_msec - LINK_FRAME_CAP_MS)
	link_frame_msec = now

## The app came back from the background (1023): the kept-alive connections may be dead (another
## network, a NAT that forgot them, sockets iOS tore down), so none is reused; the time away is not
## counted by the outage meter; the state is asked for at once on a fresh connection.
func on_app_resumed() -> void:
	api.drop_idle()
	old_api.drop_idle()
	var now := Time.get_ticks_msec()
	if paused_at_msec >= 0:
		last_ok_msec = mini(now, last_ok_msec + now - paused_at_msec)
		paused_at_msec = -1
	link_frame_msec = now
	poll = 1000.0

func connection_notice_due() -> bool:
	return connected() and (diagnostics.network_failures > 0 or diagnostics.server_failures > 0) \
		and Time.get_ticks_msec() - last_ok_msec >= CONNECTION_NOTICE_AFTER_MS

func update_connection_notice() -> void:
	# 1022 rule 10: a blip is repeated silently; the small pill under the resources shows only
	# after 10 s without any 200 or 304 (never over the game).
	var due := connection_notice_due()
	var offline := due and diagnostics.network_failures > 0
	offline_notice_shown = offline
	if is_instance_valid(connection_badge):
		connection_badge.text = OFFLINE_NOTICE if offline else "Ошибка сервера · повторяем"
		connection_badge.visible = due

func poll_account_state(due := false) -> void:
	if restore_running or login_in_progress or not connected() or (player_id.is_empty() and not restoring_session):
		return
	# A routine poll waits for the previous one and for commands (their answers carry
	# the state). The poll at a timer's zero goes at once: a poll sent before the
	# zero cannot report the work done, so waiting for it only adds its round trip.
	if not due and (polling_state or busy):
		return
	if due and polls_in_flight >= 2:
		return
	polling_state = true
	polls_in_flight += 1
	var generation := request_generation
	# Conditional poll (rule 5): opt in on the state poll only; If-None-Match only while the
	# state from that tagged answer is the one on screen, for the same session and player.
	var conditional := PackedStringArray()
	var sent_tag := ""
	var tag_serial := state_etag_serial
	if CONDITIONAL_POLLS and conditional_polls_ok:
		conditional.append("X-Drenovar-Conditional: 1")
		if not state_etag.is_empty() and state_etag_owner == state_tag_owner() and not showing_cached_state and not state_cache.is_empty():
			sent_tag = state_etag
			conditional.append("If-None-Match: " + sent_tag)
		elif not state_etag.is_empty():
			drop_state_tag()
			tag_serial = state_etag_serial
	var response := await send_request("state" if loopback else "native/game/state", null, false, 12.0, "", "", Callable(), conditional)
	polls_in_flight -= 1
	polling_state = polls_in_flight > 0
	if response.get("notModified", false):
		apply_not_modified(response, sent_tag, tag_serial)
		return
	var tag: String = str(response.get("__etag", ""))
	response.erase("__etag")
	if not sent_tag.is_empty() and not response.has("city") and tag_serial == state_etag_serial:
		drop_state_tag()  # rule 6: an error on a tagged poll
	# An older answer never replaces a newer state: accept() compares serverTime.
	if restoring_session and generation != request_generation:
		return
	if response.has("city"):
		full_polls += 1
	if restoring_session:
		if not restore_running:
			apply_restored_state(response)
	elif not loopback and response.get("httpStatus", 0) == 401:
		reset_session()
	elif response.get("profileChanged", false):
		player_id = ""
		drop_state_tag()
		await sync_account()
	else:
		var cache: Dictionary = response.duplicate(true) if not tag.is_empty() and response.has("city") else {}
		accept(response)
		# Keep the tag only for the answer now on screen (accept() may refuse a stale one).
		if is_same(state, response) and not cache.is_empty() and tag_serial == state_etag_serial \
				and etag_matcher().search(tag) != null:
			state_cache = cache
			state_etag = tag
			state_etag_owner = state_tag_owner()
		elif is_same(state, response):
			drop_state_tag()

func etag_matcher() -> RegEx:
	if etag_regex == null:
		etag_regex = RegEx.create_from_string(STATE_ETAG_PATTERN)
	return etag_regex

# Rule 2/7: the cached state with the time advanced (stock, creatures, clock); an unexpected
# 304 (another tag, no server time, nothing sent) turns conditional polls off for the session.
func apply_not_modified(response: Dictionary, sent_tag: String, tag_serial: int) -> void:
	if tag_serial != state_etag_serial:
		return  # the tag was dropped meanwhile (a command answer replaced the cache)
	var server_time := float(str(response.get("serverTime", "")).to_int())
	if sent_tag.is_empty() or str(response.get("etag", "")) != sent_tag or server_time <= 0.0 or state_cache.is_empty():
		conditional_polls_ok = false
		drop_state_tag()
		diagnostics.log_event("conditional_off", {"reason": "unexpected_304"}, Time.get_unix_time_from_system())
		return
	not_modified_polls += 1
	accept(advanced_state(server_time))

func _process(delta: float) -> void:
	discount_stall()
	advance_server_clock(delta)
	update_forest_progress(delta)
	# The safe area can change without a resize (the phone turned from one landscape side to the
	# other); twice a second is enough and costs two display queries.
	safe_check_accum += delta
	if safe_check_accum >= 0.5:
		safe_check_accum = 0.0
		refresh_safe_area()
	# The notice toast shows only while there is a notice; a new one eases in.
	if message != null and message.text != message_shown:
		show_toast_change()
	drain_retired_scenes()
	memory_peak_mb = maxf(memory_peak_mb, Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0)
	diagnostics.heartbeat(map_name, memory_in_use_mb(),
		Time.get_ticks_msec() / 1000.0, Time.get_unix_time_from_system(), Time.get_ticks_msec())
	if not is_instance_valid(stage) or scene_loading:
		return
	var camera_moving := stage.camera_dirty or stage.camera_target.distance_squared_to(stage.target) >= 0.01 or \
		absf(stage.camera_zoom - stage.zoom) >= 0.1 or absf(angle_difference(stage.camera_yaw, stage.world_yaw)) >= 0.01
	update_fling(delta)
	camera_moving = camera_moving or fling_velocity != Vector2.ZERO
	camera_moving_now = camera_moving
	if not placing.is_empty():
		var push: Vector2 = placing.get("edge", Vector2.ZERO)
		if push != Vector2.ZERO and placement_finger != -1:
			var center := get_viewport().get_visible_rect().size * 0.5
			stage.drag_between(center, center + push * 420.0 * delta)
			drag_placement(fingers.get(placement_finger, center))
	stage.update_camera(delta)
	update_placement_bar()
	if relocation_pins.visible and camera_moving:
		relocation_pins.queue_redraw()
	maybe_prewarm_other_scene()
	if scene_cache.size() > 1 and not two_scenes_fit():
		var inactive_seconds := (Time.get_ticks_msec() - scene_switch_msec) / 1000.0
		if inactive_seconds >= SCENE_REUSE_HARD_LIMIT or (
			inactive_seconds >= SCENE_REUSE_SECONDS and not camera_moving and fingers.is_empty()
		):
			release_inactive_scene()
	if smoke:
		return
	update_battle_result_notice()
	if not modal.visible:
		var now_us := Time.get_ticks_usec()
		if last_frame_us > 0 and now_us >= last_frame_us:
			var elapsed := (now_us - last_frame_us) / 1000.0
			frame_samples[frame_index] = elapsed
			frame_index = (frame_index + 1) % frame_samples.size()
			frame_count = mini(frame_count + 1, frame_samples.size())
			if camera_moving:
				motion_samples[motion_index] = elapsed
				motion_index = (motion_index + 1) % motion_samples.size()
				motion_count = mini(motion_count + 1, motion_samples.size())
		last_frame_us = now_us
	else:
		last_frame_us = 0
	var now := server_time()
	var combat_started := Time.get_ticks_usec()
	var combat_frame: Dictionary = stage.combat_view.frame(state, now, map_name)
	stage.present_armies(combat_frame.state, combat_frame.time)
	var combat_usec := Time.get_ticks_usec() - combat_started
	if not followed_army.is_empty():
		var found := false
		for marker in stage.army_markers:
			if marker.id == followed_army:
				stage.target = marker.position - Vector3.UP * 2.6
				found = true
				break
		if not found:
			followed_army = ""
	var creatures_started := Time.get_ticks_usec()
	stage.present_creatures(combat_frame.state, combat_frame.time, delta)
	combat_usec += Time.get_ticks_usec() - creatures_started
	if combat_diagnostics != null:
		combat_diagnostics.frame(self, combat_usec)
	if map_name == "world":
		var now_ms := Time.get_ticks_msec()
		if now_ms >= next_minimap_draw:
			minimap.update_locations(state.world.cities, state.world.encounters, player_id)
			minimap.armies = stage.army_markers
			minimap.focus = Vector2(stage.camera_target.x, stage.camera_target.z)
			minimap.queue_redraw()
			next_minimap_draw = now_ms + 50
		ask_server_at_zero([])
	else:
		stage.present_parade()
		stage.present_workers(now / 1000.0)
		var timer := timer_now()
		var works := current_works(timer)
		shown_jobs = works[0]
		shown_sites = works[1]
		shown_job = shown_jobs[0] if not shown_jobs.is_empty() else {}
		shown_site = shown_sites[0] if not shown_sites.is_empty() else {}
		var jobs := assign_crews(shown_jobs, 0)
		var sites := assign_crews(shown_sites, 1)
		stage.works.present(jobs[0], sites[0], timer, delta)
		stage.works2.present(jobs[1], sites[1], timer, delta)
		# The moment a timer reaches zero the server is asked at once, so the tree
		# falls / the building appears exactly then, not at the next routine poll.
		# After zero the server is asked every 1.5 s until it reports the work done
		# (at most a minute), never more often.
		ask_server_at_zero(shown_jobs + shown_sites)
	if map_name == "city" and now >= next_training_update:
		stage.present_training(state, now)
		next_training_update = now + 300.0
	poll += delta
	if Time.get_ticks_msec() >= next_notice_check_msec:
		next_notice_check_msec = Time.get_ticks_msec() + 1000
		update_connection_notice()
	if poll <= 0.65 or busy or login_in_progress:
		return
	var interval := poll_interval()
	if restoring_session or not login_proof.is_empty():
		# Retry a pending server restore or browser confirmation promptly.
		interval = 1.5
	if state_save_pending and Time.get_ticks_msec() - state_saved_msec >= STATE_SAVE_INTERVAL_MSEC:
		remember_state()
	if poll > interval:
		poll = 0
		if login_link_used and not login_proof.is_empty():
			await finish_login()
		elif connected() and (not player_id.is_empty() or restoring_session):
			await poll_account_state()

# Rule 11 (server net-policy): 650 ms only within 3 s of a visible fight (an army within 3 s of
# arrival, a fight, a return started less than 3 s ago), 2 s while any army is out, 4 s at rest;
# after n >= 2 failures in a row base x 2^(n-1), up to 15 s.
func poll_interval() -> float:
	var now := timer_now()
	var armies: Array = state.get("world", {}).get("armies", []).filter(func(army): return army.get("owner") == player_id or army.get("target") == player_id)
	armies.append_array(state.get("armies", []).filter(func(army): return army.get("status", "") != "returned"))
	var base := 4.0
	for army: Dictionary in armies:
		base = minf(base, 2.0)
		var arrive := float(army.get("arrivesAt", army.get("battleAt", 0.0)))
		var ends := float(army.get("battleEndsAt", army.get("returnStartsAt", arrive)))
		var back := float(army.get("returnStartsAt", ends))
		if arrive > 0.0 and ((now >= arrive - 3000.0 and now <= maxf(ends, arrive)) or (now >= back and now < back + 3000.0)):
			base = 0.65
			break
	var failures := maxi(diagnostics.network_failures, diagnostics.server_failures)
	if failures >= 2:
		return minf(base * pow(2.0, failures - 1), 15.0)
	return base

func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch or event is InputEventScreenDrag or event is InputEventMouseButton or \
			(event is InputEventMouseMotion and event.button_mask != 0):
		last_interaction_msec = Time.get_ticks_msec()
	# A finger lifted while a window opens or a scene loads must still be released.
	# Otherwise the stale contact turns the next one-finger drag into a false pinch.
	if event is InputEventScreenTouch and not event.pressed and fingers.has(event.index) and \
			(not is_instance_valid(stage) or modal.visible or scene_loading):
		fingers.erase(event.index)
		tap_candidate = false
		last_pinch = 0.0
		return
	if event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT and dragging and \
			(not is_instance_valid(stage) or modal.visible or scene_loading):
		dragging = false
		return
	if not is_instance_valid(stage) or modal.visible or scene_loading:
		return
	if event is InputEventScreenDrag and event.index == placement_finger and not placing.is_empty():
		fingers[event.index] = event.position
		drag_placement(event.position)
		get_viewport().set_input_as_handled()
		return
	if event is InputEventScreenTouch and not event.pressed and event.index == placement_finger:
		fingers.erase(event.index)
		tap_candidate = false
		release_placement(event.position)
		get_viewport().set_input_as_handled()
		return
	if event is InputEventScreenDrag and fingers.has(event.index):
		move_world_touch(event)
		get_viewport().set_input_as_handled()
	elif event is InputEventScreenTouch and not event.pressed and fingers.has(event.index):
		var picked: bool = tap_candidate and not event.canceled and pointer_distance < 10.0
		if fingers.size() == 1 and not picked and not event.canceled:
			start_fling(event.position)
		drag_samples.clear()
		fingers.erase(event.index)
		tap_candidate = false
		last_pinch = 0.0
		get_viewport().set_input_as_handled()
		if picked and not modal.visible and not scene_loading:
			pick_marker(event.position)

func move_world_touch(event: InputEventScreenDrag) -> void:
	var previous: Vector2 = fingers[event.index]
	fingers[event.index] = event.position
	pointer_distance += event.relative.length()
	if fingers.size() == 2:
		drag_samples.clear()
		var points: Array = fingers.values()
		var gap: float = points[0].distance_to(points[1])
		var center: Vector2 = (points[0] + points[1]) * 0.5
		if last_pinch > 2 and gap > 2:
			followed_army = ""
			stage.pinch_between(pinch_center, center, gap / last_pinch)
		last_pinch = gap
		pinch_center = center
	elif fingers.size() == 1:
		followed_army = ""
		stage.drag_between(previous, event.position)
		var now := Time.get_ticks_usec()
		drag_samples.append([now, event.position])
		while drag_samples.size() > 2 and now - int(drag_samples[0][0]) > FLING_SAMPLE_USEC:
			drag_samples.pop_front()

func start_fling(release_position: Vector2) -> void:
	fling_velocity = Vector2.ZERO
	if drag_samples.size() < 2:
		return
	var first: Array = drag_samples[0]
	var last: Array = drag_samples[-1]
	var seconds := (int(last[0]) - int(first[0])) / 1000000.0
	# A finger that paused before lifting does not glide.
	if seconds <= 0.004 or Time.get_ticks_usec() - int(last[0]) > FLING_SAMPLE_USEC:
		return
	var velocity: Vector2 = (last[1] - first[1]) / seconds
	if velocity.length() >= FLING_MIN_SPEED:
		fling_velocity = velocity.limit_length(4200.0)
		fling_point = release_position

func update_fling(delta: float) -> void:
	if fling_velocity == Vector2.ZERO:
		return
	if not fingers.is_empty() or modal.visible or not followed_army.is_empty():
		fling_velocity = Vector2.ZERO
		return
	var step := fling_velocity * delta
	stage.drag_between(fling_point, fling_point + step)
	fling_velocity *= exp(-FLING_FRICTION * delta)
	if fling_velocity.length() < FLING_STOP_SPEED:
		fling_velocity = Vector2.ZERO

func _unhandled_input(event: InputEvent) -> void:
	if (modal.visible or relocation_pins.visible) and event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		close_modal()
		get_viewport().set_input_as_handled()
		return
	if not is_instance_valid(stage) or modal.visible or scene_loading:
		return
	if event is InputEventMouse and event.device == InputEvent.DEVICE_ID_EMULATION:
		return
	if event is InputEventScreenTouch:
		if event.pressed and v6_panels.build.blocks_touch(event.position):
			return
		if event.pressed and not placing.is_empty() and placement_bar.visible and \
				placement_bar.get_global_rect().grow(6).has_point(event.position):
			return
		if event.pressed:
			if fingers.is_empty() and action_ring.is_open() and Time.get_ticks_msec() - action_ring.opened_at > 150:
				action_ring.close()
			fling_velocity = Vector2.ZERO
			drag_samples.clear()
			if try_grab_placement(event.index, event.position):
				fingers[event.index] = event.position
				tap_candidate = false
				get_viewport().set_input_as_handled()
				return
			if fingers.is_empty():
				stage.begin_direct_manipulation()
			tap_candidate = fingers.is_empty()
			fingers[event.index] = event.position
			pointer_distance = 0
			if fingers.size() == 2:
				var points: Array = fingers.values()
				last_pinch = points[0].distance_to(points[1])
				pinch_center = (points[0] + points[1]) * 0.5
	elif event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				dragging = true
				pointer_distance = 0
				stage.begin_direct_manipulation()
			elif dragging:
				dragging = false
				if pointer_distance < 8:
					pick_marker(event.position)
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			stage.zoom_at(1.1, event.position)
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			stage.zoom_at(0.9, event.position)
	elif event is InputEventMouseMotion and dragging:
		pointer_distance += event.relative.length()
		followed_army = ""
		stage.drag_between(event.position - event.relative, event.position)

func pick_marker(screen_position: Vector2) -> void:
	if not placing.is_empty():
		tap_placement(screen_position)
		return
	if v6_panels.build.placing_active():
		v6_panels.build.tap_city(screen_position)
		return
	var distance := 38.0
	var best := {}
	if relocation_pins.visible:
		for marker in stage.empty_plots:
			if stage.camera.is_position_behind(marker.position):
				continue
			var gap := stage.camera.unproject_position(marker.position).distance_to(screen_position)
			if gap < minf(distance, 24.0):
				best = marker
				distance = gap
		if not best.is_empty():
			inspect_world_plot(best.item)
		return
	if forest_game != null and forest_game.pick(screen_position): # FOREST_RESCUE hook: forest POIs / locked card
		return
	for marker in stage.place_markers + stage.army_markers + stage.creature_markers:
		if stage.camera.is_position_behind(marker.position):
			continue
		var at: Vector2 = stage.camera.unproject_position(marker.position)
		var gap := at.distance_to(screen_position)
		if gap < distance:
			best = marker
			distance = gap
	action_ring.close()
	if best.get("kind","") == "building":
		open_building_ring(best)
	elif best.get("kind","") == "wall":
		action_ring.open("city-walls", "Стены поселения", best.position, stage.camera,
			[["Оборона", "defence", show_city_defence], ["Строить", "build", show_build_menu.bind("support")]])
	elif best.get("kind","") == "encounter":
		inspect_encounter(best.item)
	elif best.get("kind","") == "settlement":
		inspect_settlement(best.item)
	elif best.get("kind","") == "army":
		inspect_army(best.item)
	else:
		for marker in stage.empty_plots:
			if stage.camera.is_position_behind(marker.position):
				continue
			var gap := stage.camera.unproject_position(marker.position).distance_to(screen_position)
			if gap < minf(distance, 23.0):
				best = marker
				distance = gap
		if best.get("kind", "") == "plot":
			inspect_plot(best.item)
		elif best.get("kind", "") == "world-plot":
			inspect_world_plot(best.item)
		elif map_name == "city":
			pick_tree(screen_position)
		else:
			pick_world_feature(screen_position)

func inspect_army(army: Dictionary) -> void:
	v6_panels.world_view.army(army)

func pick_world_feature(screen_position: Vector2) -> void:
	if stage.camera_zoom > 132.0:
		return
	var gap := 19.0
	var chosen := {}
	for item in data.environment:
		var spec: Dictionary = data.environmentModels[item.id]
		if not spec.resource or not stage.resource_layer:
			continue
		var p := stage.point(item)
		if stage.camera.is_position_behind(p):
			continue
		var distance := stage.camera.unproject_position(p).distance_to(screen_position)
		if distance < gap:
			gap = distance
			chosen = item
	if not chosen.is_empty():
		open_modal(data.environmentModels[chosen.id].name)
		row(modal_body, "Координаты · %d : %d" % [roundi(chosen.x + 150), roundi(chosen.z + 120)])

func inspect_settlement(item: Dictionary) -> void:
	v6_panels.world_view.settlement(item)

func inspect_current_settlement(id: String) -> void:
	for item in state.world.cities:
		if item.id == id:
			inspect_settlement(item)
			return

func inspect_world_plot(item: Dictionary) -> void:
	v6_panels.world_view.world_plot(item)

func show_relocation() -> void:
	if map_name != "world" or scene_loading or player_id.is_empty():
		return
	close_modal()
	relocation_pins.show()
	relocation_pins.queue_redraw()
	message.text = "Выбери зелёную метку или открой список свободных мест"

func draw_relocation_pins() -> void:
	if map_name != "world" or not is_instance_valid(stage):
		return
	for marker in stage.empty_plots:
		if stage.camera.is_position_behind(marker.position):
			continue
		var point := stage.camera.unproject_position(marker.position)
		if get_viewport().get_visible_rect().has_point(point):
			relocation_pins.draw_circle(point, 13.0, Color("#174a37"))
			relocation_pins.draw_arc(point, 13.0, 0, TAU, 20, Color("#8cf5ad"), 2.0, true)
			relocation_pins.draw_line(point - Vector2(5, 0), point + Vector2(5, 0), Color.WHITE, 2)
			relocation_pins.draw_line(point - Vector2(0, 5), point + Vector2(0, 5), Color.WHITE, 2)

func show_relocation_list() -> void:
	v6_panels.world_view.relocation_list()

func inspect_plot(plot: Dictionary) -> void:
	if is_v6_server():
		await v6_panels.catalog(str(plot.get("id", "")))
		return
	open_modal("Участок", "right")
	row(modal_body, "Координаты · %d : %d" % [roundi(plot.x), roundi(plot.z)])
	var kingdom: Variant = state.city.get("kingdom")
	if not kingdom is Dictionary:
		for definition in data.buildings:
			if definition.base != "ECO-05" and data.types.has(definition.id):
				button(modal_body, definition.ru, command.bind({"kind":"legacyBuilding", "action":"place",
					"type":definition.id, "plotId":plot.id}), not player_id.is_empty() and builder_ready())
		button(modal_body, "К списку участков", show_construction)
		return
	var worker_free := builder_ready()
	if not worker_free:
		add_workers_note(modal_body)
	if plot.id not in kingdom.get("clearedPlots", []) and not plot.id.begins_with("site-"):
		button(modal_body, "Расчистить · 15 еды · 6 сек.", command.bind({"kind":"kingdom","action":"clear","plotId":plot.id}),
			not player_id.is_empty() and worker_free and balance("food") >= 15)
		button(modal_body, "К списку участков", show_construction)
		return
	var existing := {}
	for building in state.city.buildings:
		existing[building_definition(building.type).get("base", building.type)] = true
	var hall := hall_level()
	for definition in data.buildings:
		if definition.base == "ECO-05" or existing.has(definition.base) or not data.types.has(definition.id):
			continue
		var required := int(data.unlockLevels.get(definition.id, 3))
		if required <= hall:
			var terms: Dictionary = data.buildingTerms[definition.id]
			var order := {"kind":"kingdom","action":"build","plotId":plot.id,"type":definition.id}
			button(modal_body, "%s · %s · %d сек." % [definition.ru, cost_label(terms.cost), int(terms.seconds)], command.bind(order),
				not player_id.is_empty() and worker_free and can_afford(terms.cost))
		else:
			row(modal_body, "%s · ратуша %d" % [definition.ru, required])
	button(modal_body, "К списку участков", show_construction)

func pick_tree(screen_position: Vector2) -> void:
	var distance := 34.0
	var selected := {}
	var felled: Array = state.city.get("progress", {}).get("felled", [])
	# A tree is tapped anywhere along its trunk or crown, not only at its foot.
	distance = 34.0
	for tree in stage.selectable_trees:
		var base := stage.array_point(tree.p)
		if base.distance_squared_to(stage.camera_target) > 90.0 * 90.0 or stage.camera.is_position_behind(base):
			continue
		var height := 7.0 * float(tree.get("scale", 1.0))
		for lift in [1.0, height * 0.45, height * 0.8]:
			var gap := stage.camera.unproject_position(base + Vector3.UP * lift).distance_to(screen_position)
			if gap < distance:
				distance = gap
				selected = tree
	if selected.is_empty():
		return
	open_modal(selected.name)
	var worked := pending_works.values().any(func(work): return str(work.get("tree", "")) == str(selected.id)) or \
		server_jobs().any(func(job): return str(job.get("target", "")) == str(selected.id))
	if worked:
		row(modal_body, "Здесь уже работает рабочий.")
	elif not builder_ready():
		add_workers_note(modal_body)
	if selected.id in felled:
		var order := {"kind":"resource","action":"site","id":selected.id}
		button(modal_body,"Подготовить участок",command.bind(order),not player_id.is_empty() and builder_ready() and not worked)
	else:
		var seconds := (tree_job_ms if tree_job_ms > 0.0 else float(selected.durationMs)) / 1000.0
		row(modal_body, "%d дерева · %.0f сек." % [int(selected.wood), seconds])
		var order := {"kind":"resource","action":"tree","id":selected.id}
		button(modal_body,"Срубить",command.bind(order),not player_id.is_empty() and builder_ready() and not worked)

func run_smoke() -> void:
	await get_tree().process_frame
	if stage.place_markers.size() != 4 or endpoint == "" or player_id == "":
		get_tree().quit(2)
		return
	var city_children: int = stage.trees.node.get_child_count()
	if stage.parade_slots.size() != int(state.healthy.get("ENG-01", 0)):
		printerr("Parade composition differs from the server garrison.")
		get_tree().quit(23)
		return
	if stage.terrain_bounds.size.x < 670.0 or stage.terrain_bounds.size.z < 670.0:
		get_tree().quit(14)
		return
	var barracks: Dictionary = state.city.buildings.filter(func(b): return b.type == "MIL-01")[0]
	inspect_building(barracks)
	var footman := unit_for_id("ENG-01")
	if footman.is_empty() or not modal.visible:
		get_tree().quit(10)
		return
	show_recruitment(barracks, footman, true)
	var preview_view := modal_body.find_child("RecruitPreview", true, false) as SubViewportContainer
	var preview_deadline := Time.get_ticks_msec() + 5000
	while preview_view != null and preview_view.get_child_count() == 0 and Time.get_ticks_msec() < preview_deadline:
		await get_tree().process_frame
	if preview_view == null or preview_view.get_child_count() != 1 or not RECRUIT_ORDER.all(func(id): return data.unitModels.has(id)):
		get_tree().quit(15)
		return
	var training: Dictionary = await request("command", {"kind":"train", "buildingId":barracks.id, "unitId":footman.id, "quantity":2})
	var queue: Array = training.get("city", {}).get("military", {}).get("queues", {}).get(barracks.id, [])
	if queue.size() != 1 or int(queue[0].quantity) != 2:
		printerr(training.get("error", "Training order missing"))
		get_tree().quit(11)
		return
	accept(training)
	stage.present_training(state, float(queue[0].startsAt) + 1)
	var training_actor := stage.training.get_node_or_null(NodePath(barracks.id))
	if training_actor == null or training_actor.get_meta("clip", "") != data.unitModels[footman.id].drill:
		get_tree().quit(22)
		return
	var cancelled: Dictionary = await request("command", {"kind":"cancelTraining", "orderId":queue[0].id})
	if not cancelled.has("city") or not cancelled.city.military.queues.get(barracks.id, []).is_empty():
		get_tree().quit(12)
		return
	accept(cancelled)
	show_economy("wood")
	if modal_title.text != RESOURCE_NAMES.wood or modal_body.get_child_count() < RESOURCE_NAMES.size():
		get_tree().quit(32)
		return
	var food: int = balance("food")
	state.city.demo.wallet.food = capacity() + 1500
	show_economy("food")
	var full: Array = modal_body.find_children("*", "Label", true, false)
	if not full.any(func(label): return label.text == "Еда — " + format_balance(capacity() + 1500)) or \
		not full.any(func(label): return label.text.begins_with("Производство приостановлено")):
		get_tree().quit(40)
		return
	state.city.demo.wallet.food = mini(food, capacity() - 1)
	show_economy("food")
	if modal_body.find_children("*", "Label", true, false).any(func(label): return label.text.begins_with("Производство приостановлено")):
		get_tree().quit(41)
		return
	state.city.demo.wallet.food = food
	close_modal()
	var center := stage.target
	var original_zoom := stage.zoom
	var touch := InputEventScreenTouch.new()
	touch.index = 0
	touch.pressed = true
	touch.position = Vector2(540, 280)
	_unhandled_input(touch)
	var drag := InputEventScreenDrag.new()
	drag.index = 0
	drag.position = Vector2(570, 280)
	drag.relative = Vector2(30, 0)
	_input(drag)
	if stage.target == center:
		get_tree().quit(42)
		return
	touch.index = 1
	touch.position = Vector2(730, 280)
	_unhandled_input(touch)
	drag.index = 1
	drag.position = Vector2(780, 280)
	drag.relative = Vector2(50, 0)
	_input(drag)
	if stage.zoom >= original_zoom:
		get_tree().quit(43)
		return
	touch.pressed = false
	_input(touch)
	touch.index = 0
	_input(touch)
	if not fingers.is_empty():
		get_tree().quit(44)
		return
	stage.target = center
	stage.zoom = original_zoom
	stage.update_camera(0.0, true)
	show_construction()
	if stage.empty_plots.is_empty() or modal_body.get_child_count() < stage.empty_plots.size():
		get_tree().quit(33)
		return
	show_military_cultures()
	if modal_body.get_child_count() != data.militaryCultures.size() + 1:
		get_tree().quit(34)
		return
	if not await smoke_city_march_preview():
		get_tree().quit(31)
		return
	var city_stage := stage
	await show_scene("world")
	await get_tree().process_frame
	var world_children: int = stage.scenery.get_child_count()
	if city_children == 0 or world_children == 0 or stage.place_markers.is_empty() or not stage.has_node("Roads") or not stage.has_node("Water"):
		get_tree().quit(3)
		return
	var original_view := stage.view_state()
	rotate_world()
	stage.update_camera(0.0, true)
	if not is_equal_approx(stage.camera_yaw, PI / 4.0) or is_zero_approx(stage.camera.position.x - stage.target.x):
		get_tree().quit(35)
		return
	stage.pan(Vector2(-170, 90))
	stage.change_zoom(2.4)
	show_world_overview()
	for i in range(90):
		stage.update_camera(1.0 / 60)
	var viewport_bounds := get_viewport().get_visible_rect()
	for corner in range(8):
		var p := stage.terrain_bounds.get_endpoint(corner)
		if stage.camera.is_position_behind(p) or not viewport_bounds.has_point(stage.camera.unproject_position(p)):
			printerr("World overview clipped terrain corner ", corner)
			get_tree().quit(16)
			return
	if stage.view_state() != original_view or stage.camera_target != stage.target or stage.camera_zoom != stage.zoom:
		get_tree().quit(17)
		return
	var overview_models := stage.world_lod_counts()
	if overview_models.x != 0 or overview_models.y == 0 or overview_models.z == 0:
		printerr("Overview must render the original distant buildings and canopies.")
		get_tree().quit(29)
		return
	show_world_directory()
	if modal_body.get_child_count() < 6:
		get_tree().quit(36)
		return
	show_world_cities()
	if modal_body.get_child_count() <= 1:
		get_tree().quit(37)
		return
	show_environment_catalog(5)
	var grid := modal_body.get_child(1) as GridContainer
	if grid == null or grid.get_child_count() < 1 or not grid.get_child(0).icon is AtlasTexture:
		get_tree().quit(38)
		return
	grid.get_child(0).pressed.emit()
	if modal_title.text == "Окружение мира":
		get_tree().quit(39)
		return
	close_modal()
	stage.target = stage.point(state.world.cities[0].position)
	stage.zoom = 60.0
	stage.update_camera(0.0, true)
	var close_models := stage.world_lod_counts()
	if close_models.x == 0 or close_models.z != 0:
		printerr("Close inspection must restore the original 3D models.")
		get_tree().quit(30)
		return
	stage.fit_world()
	stage.update_camera(0.0, true)
	var site: Dictionary = stage.empty_plots[0].item
	inspect_world_plot(site)
	var relocate := modal_body.get_child(modal_body.get_child_count() - 1) as Button
	if relocate == null or relocate.disabled:
		get_tree().quit(18)
		return
	var previous_slot: String = state.city.worldSlotId
	await command({"kind":"relocateCity", "slot":int(site.slot.trim_prefix("slot-")), "fromSlot":int(previous_slot.trim_prefix("slot-"))})
	if state.city.worldSlotId != site.slot:
		printerr(message.text)
		get_tree().quit(19)
		return
	var nickname := "Северный дозор"
	var city_name := "Речной дозор"
	await command({"kind":"editNames", "nickname":nickname, "settlementName":city_name})
	if state.nickname != nickname or state.city.name != city_name:
		printerr(message.text)
		get_tree().quit(20)
		return
	var encounter: Dictionary = state.world.encounters[0]
	var order := {"kind":"worldMarch","worldKind":"velkor","encounterId":encounter.id,"units":{"ENG-01":int(state.healthy["ENG-01"])}}
	var preview: Dictionary = await request("march-preview",order)
	if preview.get("path",[]).size() < 2:
		printerr(preview)
		get_tree().quit(4)
		return
	stage.show_route(preview.path)
	if not is_instance_valid(stage.route_preview) or stage.route_preview.mesh.get_surface_count() != 1:
		get_tree().quit(21)
		return
	close_modal()
	var march: Dictionary = await request("command",order)
	if march.get("world",{}).get("armies",[]).size() != 1:
		printerr(march)
		get_tree().quit(5)
		return
	accept(march)
	var active_march: Dictionary = state.world.armies[0]
	stage.target = stage.point(active_march.path[0])
	stage.zoom = 80.0
	stage.update_camera(0.0, true)
	stage.present_armies(state, float(active_march.startsAt))
	if stage.actors.get_child_count() != 1:
		get_tree().quit(6)
		return
	var actor := stage.actors.get_child(0) as Node3D
	if actor.get_child_count() != total_units(order.units):
		printerr("Field formation is missing unit models.")
		get_tree().quit(24)
		return
	var departure := actor.position
	var midpoint := (float(active_march.startsAt) + float(active_march.arrivesAt)) / 2.0
	stage.target = stage.along_route(stage.army_routes[active_march.id], 0.5)
	stage.update_camera(0.0, true)
	stage.present_armies(state, midpoint)
	if not is_instance_valid(actor) or actor.position.distance_to(departure) < 0.1 or actor.get_child(0).get_meta("clip", "") != "walk":
		get_tree().quit(13)
		return
	var world_stage := stage
	stage.pan(Vector2(48, -15))
	stage.change_zoom(1.2)
	rotate_world()
	stage.toggle_scenery_layer(true)
	var world_view := stage.view_state()
	for i in range(6):
		await show_scene("city")
		if stage != city_stage or world_stage.visible:
			get_tree().quit(7)
			return
		await show_scene("world")
		if stage != world_stage or stage.view_state() != world_view or city_stage.visible:
			get_tree().quit(8)
			return
		await get_tree().process_frame
	await show_scene("city")
	release_inactive_scene()
	await get_tree().process_frame
	await show_scene("world")
	if stage.view_state() != world_view or stage.camera_zoom != world_view.zoom:
		get_tree().quit(9)
		return
	await advance_test_clock(int(active_march.arrivesAt) + 1)
	var fighting := await request("state")
	if fighting.get("world", {}).get("armies", []).is_empty() or fighting.world.armies[0].status != "fighting":
		printerr("Server battle phase did not start.")
		get_tree().quit(25)
		return
	accept(fighting)
	var battle: Dictionary = state.world.armies[0]
	stage.target = stage.point(battle.position)
	stage.zoom = 68.0
	stage.update_camera(0.0, true)
	var checked_event := false
	for offset in range(1, mini(6000, int(battle.battleEndsAt) - int(battle.battleAt)), 900):
		if offset > 1:
			await advance_test_clock(int(battle.battleAt) + offset)
			accept(await request("state"))
		for event in state.world.armies[0].get("events", []):
			if event[1] != "soldier_attack":
				continue
			stage.present_armies(state, float(battle.battleAt) + float(event[0]) - 20.0)
			var member := stage.actors.get_node_or_null(NodePath(battle.id + "/" + str(event[2]) + "_" + str(int(event[3]))))
			if member != null and member.get_meta("clip", "") == "attack":
				checked_event = true
				break
		if checked_event:
			break
	if not checked_event:
		printerr("The server attack event did not drive the correct formation member.")
		get_tree().quit(26)
		return
	stage.present_creatures(state, float(state.serverTime), 0.016)
	await advance_test_clock(int(battle.battleEndsAt) + 1)
	var settled := await request("state")
	var report_index: int = settled.get("reports", []).find_custom(func(report): return report.id == battle.id)
	if report_index < 0:
		printerr("No authoritative report for the completed march.")
		get_tree().quit(27)
		return
	accept(settled)
	show_report(state.reports[report_index])
	if not modal.visible or modal_body.get_child_count() < 5:
		get_tree().quit(28)
		return
	print("DRENOVAR native smoke: resource balances and production cap, drag and pinch, construction, military tiers, city march preview, world directory and atlas, rotation, full map framing, scene caching, server relocation and names, animated training and parade, real march, timed combat events and authoritative report.")
	get_tree().quit()

func smoke_city_march_preview() -> bool:
	var target: Dictionary = state.encounters.filter(func(item): return int(item.level) == 1)[0]
	inspect_encounter(target)
	var attack := modal_footer.get_child(0) as Button
	if attack.text != "Атаковать":
		return false
	attack.pressed.emit()
	var send := modal_footer.find_child("MarchSend", true, false) as Button
	var quote := modal_body.find_child("MarchQuote", true, false) as Label
	var quantity := modal_body.find_children("*", "SpinBox", true, false)[0] as SpinBox
	if quantity.value <= 0 or send.get_meta("route_ready", false) or modal_title.text != "Создать войско":
		return false
	var clear_button := modal_footer.get_children().filter(func(child): return child is Button and child.text == "Очистить")[0] as Button
	clear_button.pressed.emit()
	if not send.disabled or quote.text != "Выберите воинов":
		return false
	quantity.value = 1
	var deadline := Time.get_ticks_msec() + 8000
	var retry := modal_body.find_children("*", "Button", true, false).filter(func(child): return child.text == "Повторить расчёт")[0] as Button
	while not send.get_meta("route_ready", false) and not retry.visible and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if OS.get_environment("DRENOVAR_TEST_CITY_PREVIEW_TIMEOUT") == "1":
		if not retry.visible or quantity.value != 1 or send.get_meta("route_ready", false):
			return false
		retry.pressed.emit()
		deadline = Time.get_ticks_msec() + 8000
		while not send.get_meta("route_ready", false) and Time.get_ticks_msec() < deadline:
			await get_tree().process_frame
		print("DRENOVAR native smoke: recovered from city march preview timeout.")
	var confirmed: bool = send.get_meta("route_ready", false) and not send.disabled and is_instance_valid(stage.route_preview) and quote.text.begins_with("Прибытие")
	if not confirmed:
		printerr("The city march did not calculate the route inline: ", quote.text)
	close_modal()
	return confirmed

func advance_test_clock(value: int) -> void:
	if not loopback or not smoke:
		return
	var client := HTTPRequest.new()
	add_child(client)
	client.timeout = 4.0
	if client.request(endpoint + "/test/clock?time=" + str(value), [], HTTPClient.METHOD_POST) == OK:
		await client.request_completed
	client.queue_free()

func march_limit() -> int:
	return int(state.get("v6", {}).get("march_capacity", 200))
