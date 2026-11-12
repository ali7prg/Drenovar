extends Node

const Landscape = preload("res://src/landscape.gd")
const Minimap = preload("res://src/minimap.gd")
const LaunchScreen = preload("res://src/launch_screen.gd")
const TouchScroll = preload("res://src/touch_scroll.gd")
const SessionStore = preload("res://src/session_store.gd")
const Interface = preload("res://src/ui_theme.gd")
const WebPanels = preload("res://src/web_panel_theme.gd")
const MarchMap = preload("res://src/march_map.gd")
const BattleResults = preload("res://src/battle_results.gd")
const WarriorVisual = preload("res://src/warrior_visual.gd")
const HudAction = preload("res://src/hud_action.gd")
const SessionDiagnostics = preload("res://src/session_diagnostics.gd")
const TITLE_FONT = preload("res://assets/ui/NotoSerif-Regular.ttf")
const RECRUIT_ORDER := ["ENG-09", "ENG-08", "ENG-01", "ENG-02", "ENG-07", "ENG-10", "ENG-03", "ENG-04", "ENG-05", "ENG-06"]
const RECRUIT_FACILITIES := {"MIL-01":"Казармы пехоты", "MIL-02":"Стрельбище", "MIL-03":"Конюшня"}
const RESOURCE_NAMES := {"food":"Еда","wood":"Дерево","stone":"Камень","iron":"Железо","coins":"Монеты"}
const SCENE_REUSE_SECONDS := 40.0
const SCENE_REUSE_HARD_LIMIT := 60.0
const LIVE_SERVER := "https://drenovar.pink-lyric-9420.chatgpt.site"
var data: Dictionary
var state: Dictionary
var stage: Landscape
var scene_cache: Dictionary = {}
var retired_nodes: Array[Node] = []
var saved_views: Dictionary = {}
var scene_loading := false
var scene_switch_msec := 0
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
var minimap: Minimap
var environment_atlas: Texture2D
var endpoint := LIVE_SERVER
var loopback := false
var session := ""
var restoring_session := false
var saved_session_error := false
var login_proof := ""
var login_deadline := 0
var login_link_used := false
var busy := false
var polling_state := false
var request_generation := 0
var login_in_progress := false
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
var last_frame_us := 0
var modal_generation := 0
var action_list_key := ""
var next_training_update := 0.0
var followed_army := ""
var next_minimap_draw := 0
var diagnostics := SessionDiagnostics.new()
const OFFLINE_NOTICE := "Нет связи с сервером. Переподключаемся…"
var offline_notice_shown := false
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
	Input.use_accumulated_input = false
	frame_samples.resize(240)
	motion_samples.resize(120)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			var override := arg.trim_prefix("--server=").trim_suffix("/")
			if override.begins_with("http://127.0.0.1:"):
				endpoint = override
				loopback = true
		if arg == "--smoke":
			smoke = true
		if arg.begins_with("--diagnostics="):
			diagnostics.path = arg.trim_prefix("--diagnostics=")
	diagnostics.start(str(ProjectSettings.get_setting("application/config/version")), Time.get_unix_time_from_system())
	var launch := LaunchScreen.new()
	add_child(launch)
	# Give the branded screen a frame before parsing game data and loading meshes.
	await get_tree().process_frame
	await get_tree().process_frame
	data = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	state = data.demo
	add_child(hud)
	build_ui()
	if loopback:
		await sync_account(true)
	else:
		session = SessionStore.read_session()
		if not session.is_empty():
			launch.show_step("Восстанавливаем поселение…", 38)
			await restore_account()
	launch.show_step("Готовим поселение…", 72)
	await show_scene("city")
	launch.finish()
	warm_panel_textures()
	if restoring_session:
		message.text = "Подключаемся к сохранённому поселению…"
	if smoke:
		await run_smoke()

func build_ui() -> void:
	var root := Control.new()
	root.theme = Interface.make_theme()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	var outer := VBoxContainer.new()
	outer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	outer.offset_left = 52
	outer.offset_right = -52
	outer.offset_top = 4
	outer.offset_bottom = -24
	outer.add_theme_constant_override("separation",12)
	outer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(outer)
	var bar := HBoxContainer.new()
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	outer.add_child(bar)
	setup_resource_icons()
	profile_button = hud_action(bar, "Профиль", "profile", show_account)
	profile_button.name = "ProfileButton"
	var wallet := HBoxContainer.new()
	wallet.add_theme_constant_override("separation", 2)
	wallet.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	wallet.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	wallet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	wallet.alignment = BoxContainer.ALIGNMENT_END
	bar.add_child(wallet)
	for key in RESOURCE_NAMES:
		add_resource_button(wallet, key)
	var navigation := HBoxContainer.new()
	navigation.add_theme_constant_override("separation", 5)
	navigation.alignment = BoxContainer.ALIGNMENT_END
	nav_buttons.city = hud_action(navigation, "Город", "city", show_scene.bind("city"))
	nav_buttons.world = hud_action(navigation, "Карта", "world", show_scene.bind("world"))
	hud_action(navigation, "Армия", "army", show_armies)
	hud_action(navigation, "Отчёты", "reports", show_reports)
	hud_action(navigation, "Меню", "menu", show_controls_menu)
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
	message = Label.new()
	message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	message.add_theme_color_override("font_outline_color", Color("#121916"))
	message.add_theme_constant_override("outline_size", 7)
	outer.add_child(message)
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
	modal = PanelContainer.new()
	modal.theme = WebPanels.make_theme(root.theme)
	web_sheet_style = WebPanels.gradient_style(Color("#30353b"), Color("#1d2025"), WebPanels.BRASS, 12)
	result_sheet_style = WebPanels.gradient_style(Color("#354c34"), Color("#122a21"), Color("#e5c57d"), 20, 15)
	modal.add_theme_stylebox_override("panel", web_sheet_style)
	root.add_child(modal)
	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 8)
	modal.add_child(inner)
	var header := PanelContainer.new()
	modal_header = header
	header.add_theme_stylebox_override("panel", Interface.style(Color("#272c31"), Color.TRANSPARENT, 4, 7, 4))
	inner.add_child(header)
	var heading := HBoxContainer.new()
	header.add_child(heading)
	var titles := VBoxContainer.new()
	titles.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	titles.add_theme_constant_override("separation", 0)
	heading.add_child(titles)
	modal_eyebrow = Label.new()
	modal_eyebrow.add_theme_font_size_override("font_size", 14)
	modal_eyebrow.add_theme_color_override("font_color", WebPanels.GOLD)
	titles.add_child(modal_eyebrow)
	modal_title = Label.new()
	modal_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_title.add_theme_font_override("font", TITLE_FONT)
	modal_title.add_theme_font_size_override("font_size", 31)
	modal_title.add_theme_color_override("font_color", WebPanels.IVORY)
	modal_title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	titles.add_child(modal_title)
	var close_button := button(heading,"×",close_modal)
	close_button.custom_minimum_size = Vector2(62, 57)
	close_button.tooltip_text = "Закрыть"
	close_button.accessibility_name = "Закрыть"
	var divider := ColorRect.new()
	modal_divider = divider
	divider.color = Color("#77684a")
	divider.custom_minimum_size.y = 1
	inner.add_child(divider)
	modal_tools = HBoxContainer.new()
	inner.add_child(modal_tools)
	var scroll := TouchScroll.new()
	modal_scroll = scroll
	scroll.custom_minimum_size.y = 84
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	inner.add_child(scroll)
	modal_body = VBoxContainer.new()
	modal_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	modal_body.add_theme_constant_override("separation",8)
	scroll.add_child(modal_body)
	modal_status = Label.new()
	modal_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	modal_status.add_theme_color_override("font_color", Color("#ffc28b"))
	modal_status.hide()
	inner.add_child(modal_status)
	modal_footer = HBoxContainer.new()
	inner.add_child(modal_footer)
	place_modal("center")
	modal.hide()
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

func hud_action(parent: Container, caption: String, symbol: String, action: Callable) -> Button:
	var control := HudAction.new()
	control.caption = caption
	control.symbol = symbol
	control.tooltip_text = caption
	control.accessibility_name = caption
	control.pressed.connect(action)
	parent.add_child(control)
	return control

func show_controls_menu() -> void:
	var selecting := relocation_pins.visible
	open_modal("Меню", "left", "DRENOVAR")
	if selecting:
		button(modal_body, "Список свободных мест", show_relocation_list)
		button(modal_body, "Вернуться к выбору на карте", show_relocation)
	if map_name == "city":
		button(modal_body, "Поселение и строительство", show_city_actions)
		button(modal_body, "Центрировать город", func(): close_modal(); center_city())
	else:
		button(modal_body, "Показать весь мир", show_world_overview)
		button(modal_body, "Общий мир", show_world_directory)
		button(modal_body, "Слои карты", show_map_options)
		button(modal_body, "Повернуть карту", func(): close_modal(); rotate_world())
	button(modal_body, "Приблизить", func(): close_modal(); zoom_scene(1.2))
	button(modal_body, "Отдалить", func(): close_modal(); zoom_scene(0.83))
	button(modal_body, "Плавность на устройстве", show_performance)
	button(modal_body, "О приложении", show_application)

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
	control.custom_minimum_size = Vector2(108, 44)
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
	var control := PanelContainer.new()
	control.add_theme_stylebox_override("panel", Interface.panel_style(inset, dialog))
	return control

func button(parent: Container, title: String, action: Callable, enabled := true) -> Button:
	var value := Button.new()
	value.text = title
	value.custom_minimum_size = Vector2(48,42)
	value.disabled = not enabled
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
		var seconds := maxi(0, ceili((ends_at - server_time()) / 1000.0))
		label.text = "%s · %d:%02d" % [title, floori(seconds / 60.0), seconds % 60]
	var clock := Timer.new()
	clock.wait_time = 1.0
	clock.autostart = true
	label.add_child(clock)
	clock.timeout.connect(update)
	update.call()

func countdown(title: String, ends_at: float) -> void:
	var label := Label.new()
	modal_body.add_child(label)
	bind_countdown(label, title, ends_at)

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

func show_city_actions() -> void:
	open_modal("Поселение")
	button(modal_body, "Строить", show_construction)
	button(modal_body, "Ресурсы и доход", show_economy)
	button(modal_body, "Найти существо", show_city_hunt)
	if not stage.parade_slots.is_empty():
		button(modal_body, "Парадный строй", focus_parade)
	row(modal_body, "Предел производства на ресурс · %d" % capacity())
	var order := construction_order()
	if not order.is_empty():
		var title: String = {"clear":"Расчистка", "build":"Строительство", "upgrade":"Улучшение"}.get(order.kind, "Заказ")
		countdown(title, order.endsAt)
		button(modal_body, "Подробнее о заказе", inspect_construction_order.bind(order))
		if order.kind != "clear":
			button(modal_body, "Ускорить строительство", show_speedups.bind("construction", order, ""))
	var job: Variant = state.city.progress.get("job")
	if job is Dictionary and job.has("endsAt"):
		countdown("Работа на участке", job.endsAt)
	if state.get("starterEligible71", false):
		button(modal_body, "Первые шаги", show_starter_goals)
	elif state.city.get("kingdom") is Dictionary and not state.city.kingdom.guide.get("skipped", false):
		button(modal_body, "Первые шаги", show_city_guide)
	button(modal_body, "Расчистка рощ", show_clearings)
	button(modal_body, "Гарнизон", show_armies)

func show_city_guide() -> void:
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
	row(modal_body, "Версия %s · совместимость с веб-сборкой 91" % ProjectSettings.get_setting("application/config/version"))
	row(modal_body, "Игровой прогресс сохраняется в серверном поселении аккаунта." if not player_id.is_empty() else "Войди в аккаунт, чтобы играть со своим поселением.")
	button(modal_body, "Аккаунт", show_account)
	button(modal_body, "Проверка плавности", show_performance)

func show_economy(resource := "") -> void:
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
	var accent: Color = Interface.RESOURCES[resource]
	var border := accent.darkened(0.38) if selected else Color("#41574a")
	card.add_theme_stylebox_override("panel", Interface.style(Color("#22312a"), border, 10, 10, 7))
	modal_body.add_child(card)
	var contents := HBoxContainer.new()
	contents.add_theme_constant_override("separation", 11)
	card.add_child(contents)
	add_resource_icon(contents, resource, 51 if selected else 33)
	var values := VBoxContainer.new()
	values.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	contents.add_child(values)
	var total := Label.new()
	total.add_theme_color_override("font_color", accent)
	total.add_theme_font_size_override("font_size", 24 if selected else 18)
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
		labels.production.add_theme_color_override("font_color", Color("#f4c592") if stopped else Interface.MUTED)

func format_balance(value: int) -> String:
	var digits := str(value)
	var groups := PackedStringArray()
	while digits.length() > 3:
		groups.insert(0, digits.right(3))
		digits = digits.left(-3)
	groups.insert(0, digits)
	return " ".join(groups)

func show_construction() -> void:
	open_modal("Строительство", "right")
	var order := construction_order()
	if not order.is_empty():
		countdown("Строитель занят", order.endsAt)
		button(modal_body, "Подробнее о заказе", inspect_construction_order.bind(order))
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
			button(modal_body, "Начать расчистку", command.bind({"kind":"resource", "action":"area", "id":grove.id}),
				not player_id.is_empty() and level >= int(grove.level) and construction_order().is_empty()
				and state.city.progress.get("job") == null))

func show_starter_goals() -> void:
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

func show_speedups(queue: String, order: Dictionary, building_id: String) -> void:
	open_modal("Ускорение")
	countdown("Осталось", order.endsAt)
	var available := false
	for id in data.speedItems:
		var item: Dictionary = data.speedItems[id]
		var count := int(state.get("items", {}).get(id, 0))
		if item.kind != queue or count < 1:
			continue
		available = true
		var duration := int(item.seconds)
		var label := "%d мин · ×%d" % [duration / 60.0, count]
		button(modal_body, label, func():
			var remaining := float(order.endsAt) - server_time()
			if remaining <= 0:
				show_error({"error":"Заказ уже завершился. Открой очередь заново."})
				return
			var payload := {"kind":"speedup", "queue":queue, "item":id, "buildingId":building_id,
				"orderId":order.id if queue == "training" else order.requestId,
				"expectedEndsAt":order.endsAt, "confirmUnused":false}
			if duration * 1000 > remaining:
				open_modal("Подтвердить ускорение")
				row(modal_body, "Часть времени ускорения останется неиспользованной.")
				payload.confirmUnused = true
				button(modal_body, "Применить", command.bind(payload))
				button(modal_body, "Назад", show_speedups.bind(queue, order, building_id))
			else:
				command(payload))
	if not available:
		row(modal_body, "Для этой очереди пока нет ускорителей.")

func show_trade(resource := "") -> void:
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
	open_modal("Лазарет", "right")
	for order in state.get("healing", []):
		countdown("Лечатся · %d" % total_units(order.units), order.endsAt)
	var inputs := {}
	for unit in data.englishRoster:
		var count := int(state.get("wounded", {}).get(unit.id, 0))
		if count > 0:
			inputs[unit.id] = unit_quantity("%s · %d" % [unit.name, count], mini(count, 200))
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
		if count < 1 or count > 200:
			show_error({"error":"Выбери от 1 до 200 воинов."})
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
				if not army.has("worldKind"):
					button(modal_body, "Отозвать отряд", command.bind({"kind":"recall", "armyId":army.id}))
			"fighting":
				countdown(title + " · бой", army.battleEndsAt)
			"returning":
				countdown(title + " · возвращается", army.returnsAt)
	for unit in data.englishRoster:
		var available := int(state.get("healthy", {}).get(unit.id, 0))
		if available > 0:
			var entry := HBoxContainer.new()
			modal_body.add_child(entry)
			panel_art(entry, unit.id + ".png", Vector2(56, 56))
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
		var amount := str(value)
		if value >= 1000000:
			amount = "%.1f млн" % (value / 1000000.0)
		elif value >= 1000:
			amount = "%.1f тыс" % (value / 1000.0)
		resource_amounts[id].text = amount.replace(".", ",")
		resource_buttons[id].tooltip_text = "%s · %s" % [RESOURCE_NAMES[id], format_balance(value)]
		resource_buttons[id].accessibility_name = resource_buttons[id].tooltip_text
	if not connected():
		message.text = ""

func show_scene(scene_name: String) -> void:
	if scene_loading:
		return
	if is_instance_valid(stage) and scene_name == map_name:
		close_modal()
		return
	scene_loading = true
	var started_at := Time.get_ticks_msec()
	followed_army = ""
	close_modal()
	var next: Landscape = scene_cache.get(scene_name)
	if next == null:
		message.text = "Открываем карту…" if scene_name == "world" else "Открываем город…"
		await get_tree().process_frame
		next = Landscape.new()
		next.set_active(false)
		add_child(next)
		await next.setup(data, state, scene_name, saved_views.get(scene_name, {}))
		scene_cache[scene_name] = next
	if is_instance_valid(stage):
		stage.set_active(false)
	stage = next
	map_name = scene_name
	nav_buttons.city.visible = map_name != "city"
	nav_buttons.world.visible = map_name != "world"
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

func release_inactive_scene() -> void:
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

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		diagnostics.set_state("exited", Time.get_unix_time_from_system())
	elif what == NOTIFICATION_APPLICATION_RESUMED or what == NOTIFICATION_APPLICATION_FOCUS_IN:
		diagnostics.set_state("foreground", Time.get_unix_time_from_system())
	if what == NOTIFICATION_OS_MEMORY_WARNING:
		diagnostics.log_event("memory_warning", {"memory_mb": snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1),
			"scenes": scene_cache.size()}, Time.get_unix_time_from_system())
		release_inactive_scene()
		drain_retired_scenes(true)
	elif what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_APPLICATION_PAUSED:
		diagnostics.set_state("background", Time.get_unix_time_from_system())
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
	empty(modal_body)
	empty(modal_tools)
	empty(modal_footer)

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
	open_modal("Слои мира", "right")
	for resources in [true, false]:
		var toggle := CheckButton.new()
		toggle.text = "Месторождения и угодья" if resources else "Мелкие детали"
		toggle.button_pressed = stage.resource_layer if resources else stage.detail_layer
		toggle.toggled.connect(func(_enabled): stage.toggle_scenery_layer(resources))
		modal_body.add_child(toggle)
	button(modal_body, "Найти своё поселение", focus_own_city)
	button(modal_body, "Окружение мира", show_environment_catalog)

func show_world_directory() -> void:
	open_modal("Общий мир", "right", "ДРЕНОВАР · КАРТА МИРА")
	button(modal_body, "Мой город", focus_own_city, state.world.cities.any(func(city): return city.id == player_id))
	var reason: String = state.world.get("relocationReason", "")
	button(modal_body, "Переселить город", show_relocation, not player_id.is_empty() and reason.is_empty())
	if not reason.is_empty():
		row(modal_body, reason)
	button(modal_body, "Города", show_world_cities)
	button(modal_body, "Цели охоты", show_world_hunt)
	button(modal_body, "Походы", show_world_marches)
	button(modal_body, "Окружение мира", show_environment_catalog)

func show_world_cities() -> void:
	open_modal("Города", "right", "ДРЕНОВАР · КАРТА МИРА")
	for city in state.world.cities:
		var name_suffix := " · ваш город" if city.id == player_id else ""
		button(modal_body, "%s · ур. %d%s" % [city.name, int(city.level), name_suffix], inspect_settlement.bind(city))
	if state.world.cities.is_empty():
		row(modal_body, "На карте пока нет серверных поселений.")
	button(modal_body, "К общему миру", show_world_directory)

func show_world_marches() -> void:
	open_modal("Походы", "right", "ДРЕНОВАР · КАРТА МИРА")
	var has_marches := false
	for army in state.world.armies:
		if army.status == "returned":
			continue
		has_marches = true
		button(modal_body, army.get("name", "Поход"), inspect_army.bind(army))
	if not has_marches:
		row(modal_body, "На карте сейчас нет активных походов.")
	button(modal_body, "К общему миру", show_world_directory)

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

func place_modal(layout: String) -> void:
	var anchors := Rect2(0.5, 0.5, 0, 0)
	var offsets := Rect2(-300, -220, 600, 440)
	match layout:
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
	modal.anchor_left = anchors.position.x
	modal.anchor_top = anchors.position.y
	modal.anchor_right = anchors.end.x
	modal.anchor_bottom = anchors.end.y
	modal.offset_left = offsets.position.x
	modal.offset_top = offsets.position.y
	modal.offset_right = offsets.end.x
	modal.offset_bottom = offsets.end.y

func open_modal(title: String, layout := "center", eyebrow := "") -> void:
	result_open = layout == "result"
	modal_header.visible = not result_open
	modal_divider.visible = not result_open
	modal.add_theme_stylebox_override("panel", result_sheet_style if result_open else web_sheet_style)
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
	modal_status.hide()
	empty(modal_body)
	empty(modal_tools)
	empty(modal_footer)
	modal_tools.hide()
	modal_footer.hide()
	place_modal(layout)
	modal_body.get_parent().set_deferred("scroll_vertical", 0)
	dimmer.color = Color.TRANSPARENT if layout in ["left", "right", "city_target"] else Color("#101417a0")
	if result_open:
		dimmer.color = Color("#09140bc9")
		result_notice.hide()
	dimmer.show()
	modal.show()
	modal_scroll.set_modal_active(true)
	if entering:
		modal.modulate.a = 0.82
		dialog_tween = create_tween()
		dialog_tween.tween_property(modal, "modulate:a", 1.0, 0.13)

func panel_action(parent: Container, caption: String, action: Callable, enabled := true, danger := false) -> Button:
	var control := button(parent, caption, action, enabled)
	control.custom_minimum_size.y = 51
	WebPanels.primary(control, danger)
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

func warm_panel_textures() -> void:
	# Decode recruitment portraits on a worker thread after launch, so the first
	# barracks window does not decode eleven images inside the touch handler.
	var pending: Array[String] = []
	for id in RECRUIT_ORDER:
		var full: String = "res://assets/ui/web-panels/" + id + ".png"
		if ResourceLoader.exists(full) and ResourceLoader.load_threaded_request(full, "Texture2D") == OK:
			pending.append(full)
	var atlas: String = data.environmentAtlas
	if environment_atlas == null and ResourceLoader.load_threaded_request(atlas, "Texture2D") == OK:
		pending.append(atlas)
	while not pending.is_empty():
		await get_tree().process_frame
		for full: String in pending.duplicate():
			if ResourceLoader.load_threaded_get_status(full) != ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				pending.erase(full)
				var texture := ResourceLoader.load_threaded_get(full) as Texture2D
				if full == atlas:
					if environment_atlas == null:
						environment_atlas = texture
					continue
				var key: String = full.trim_prefix("res://assets/ui/web-panels/")
				if texture != null and not panel_textures.has(key):
					panel_textures[key] = texture

func panel_texture(path: String) -> Texture2D:
	if not panel_textures.has(path):
		panel_textures[path] = load("res://assets/ui/web-panels/" + path) as Texture2D
	return panel_textures[path]

func inspect_building(building: Dictionary) -> void:
	open_modal(building_title(building.type), "right", "ПОСЕЛЕНИЕ")
	var level := int(building.level)
	row(modal_body,"Уровень %d" % level)
	var metrics: Dictionary = data.buildingTerms.get(building.type, {})
	if metrics.get("production") != null:
		row(modal_body, "%s · +%d/мин" % [RESOURCE_NAMES[metrics.production], int(metrics.rates[clampi(level, 1, 5) - 1])])
	if int(metrics.get("storage", 0)) > 0:
		row(modal_body, "Вместимость · +%d" % (int(metrics.storage) * level))
	var construction := construction_order()
	if construction.get("buildingId") == building.id:
		countdown("Улучшение в процессе", construction.endsAt)
		button(modal_body, "Ускорить строительство", show_speedups.bind("construction", construction, ""))
	if not state.city.get("kingdom") is Dictionary:
		var definition := building_definition(building.type)
		if not state.city.get("legacyUpgrades") is Dictionary:
			for target_level in range(1, int(definition.get("maxLevel", 1)) + 1):
				if target_level != level:
					button(modal_body, "Уровень %d" % target_level, command.bind({"kind":"legacyBuilding",
						"action":"level", "buildingId":building.id, "level":target_level}), not player_id.is_empty())
		for variant in data.buildings:
			if variant.id != building.type and variant.base == definition.get("base", building.type) and data.types.has(variant.id):
				button(modal_body, variant.ru, command.bind({"kind":"legacyBuilding", "action":"variant",
					"buildingId":building.id, "type":variant.id}), not player_id.is_empty())
	if level < 5 and building.type in data.upgradable:
		var terms: Dictionary = data.buildingTerms[building.type].upgrades[level - 1]
		row(modal_body, "Уровень %d · %s · %d сек." % [level + 1, cost_label(terms.cost), int(terms.seconds)])
		var available := can_afford(terms.cost) and construction_order().is_empty()
		var base: String = building_definition(building.type).get("base", building.type)
		if base == "ECO-05":
			for prerequisite in data.upgradeRequirements.get(str(level + 1), []):
				if not state.city.buildings.any(func(item): return building_definition(item.type).get("base") == prerequisite[0] and item.level >= prerequisite[1]):
					row(modal_body, "Требуется %s · ур. %d" % [building_title(prerequisite[0]), int(prerequisite[1])])
					available = false
		elif level >= hall_level():
			row(modal_body, "Требуется ратуша уровня %d." % (level + 1))
			available = false
		panel_action(modal_body,"Улучшить",command.bind({"kind":"kingdom","action":"upgrade","buildingId":building.id,"expectedLevel":level}),not player_id.is_empty() and available)
	elif level >= 5 and building.type in data.upgradable:
		row(modal_body, "Достигнут максимальный уровень текущего этапа.")
	if building.type in data.producers:
		button(modal_body, "Собрать ресурсы", command.bind({"kind":"kingdom","action":"collect","buildingId":building.id}),not player_id.is_empty())
	if building.type == "ECO-03":
		button(modal_body, "Обменять ресурсы", show_trade, not player_id.is_empty())
	if building.type == "SUP-01":
		button(modal_body, "Лазарет", show_hospital)
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

func recruitment_buildings() -> Array:
	var result := []
	for base in RECRUIT_FACILITIES:
		var index: int = state.city.buildings.find_custom(func(item): return building_definition(item.type).get("base") == base)
		if index >= 0:
			result.append(state.city.buildings[index])
	return result

func open_recruitment(building: Dictionary, unit_id := "", quantity := 1) -> void:
	var group: String = data.trainingGroups.get(building.type, data.trainingGroups.get(building_definition(building.type).get("base"), ""))
	var units: Array = RECRUIT_ORDER.map(unit_for_id).filter(func(unit): return unit.training_building == group)
	if units.is_empty():
		show_training_buildings()
		return
	var selected: Dictionary = unit_for_id(unit_id) if not unit_id.is_empty() else units[0]
	show_recruitment(building, selected, true, quantity)

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
			tab.add_theme_stylebox_override("normal", Interface.style(Color("#504331"), Color("#d3ae6b"), 7, 8, 6))
	button(modal_tools, "I · Англия ▾", show_military_cultures)

	var layout := HBoxContainer.new()
	layout.add_theme_constant_override("separation", 10)
	modal_body.add_child(layout)
	var stage_panel := panel(8)
	stage_panel.add_theme_stylebox_override("panel", WebPanels.gradient_style(Color("#405450"), Color("#182724"), WebPanels.BRASS, 8))
	stage_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stage_panel.size_flags_stretch_ratio = 0.62
	stage_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	layout.add_child(stage_panel)
	var display := VBoxContainer.new()
	stage_panel.add_child(display)
	var preview := create_unit_preview(display, 258, panel_texture(unit.id + ".png"))
	preview.name = "RecruitPreview"
	load_unit_preview.call_deferred(preview, data.unitModels[unit.id], 0.72)
	var name_label := Label.new()
	name_label.text = unit.name
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.add_theme_font_override("font", TITLE_FONT)
	name_label.add_theme_font_size_override("font_size", 26)
	display.add_child(name_label)
	var role := Label.new()
	role.text = unit.role
	role.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	role.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
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
		card.icon = panel_texture(id + ".png")
		card.expand_icon = true
		card.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
		card.add_theme_constant_override("icon_max_width", 60)
		card.add_theme_font_size_override("font_size", 14)
		card.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		if id == unit.id:
			card.add_theme_stylebox_override("normal", Interface.style(Color("#504331"), Color("#d3ae6b"), 7, 4, 5))
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
	terms.add_theme_stylebox_override("panel", Interface.style(Color("#272c31"), Color("#846d4d"), 6, 8, 6))
	order.add_child(terms)
	terms.add_child(quote)
	var train := panel_action(order, "Обучить", func(): pass)
	var reason := Label.new()
	reason.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	reason.add_theme_color_override("font_color", WebPanels.GOLD)
	order.add_child(reason)
	var levels: Array = data.unitRequirements[unit.id]
	if not state.city.get("kingdom") is Dictionary:
		levels = [1, int(unit.legacyLevel)]
	var paid_training: bool = not state.city.demo.get("unlimitedResources", false) or state.get("trainingUsesResources", false)
	var unlocked := hall_level() >= int(levels[0]) and int(building.level) >= int(levels[1])
	var queue: Array = state.city.get("military", {}).get("queues", {}).get(building.id, [])
	queue_has_room = queue_has_room and queue.size() < 3
	var submission := {"pending": false, "key": "", "quantity": 0}
	var update_quote := func(amount: float):
		var costs := {}
		for resource in ["wood", "food", "iron", "coins"]:
			var cost := int(unit.get(resource, 0))
			if resource == "iron" and state.city.get("kingdom") != null and unit.id in ["ENG-09", "ENG-08", "ENG-01"]:
				cost = 0
			costs[resource] = cost * int(amount)
		var reduction := clampi(int(building.level) - 1, 0, 4) * 8 if state.city.get("kingdom", state.city.get("legacyUpgrades")) is Dictionary else 0
		var seconds := maxi(1, ceili(float(unit.train_seconds) * amount * (1.0 - reduction / 100.0)))
		quote.text = "Стоимость · %s\nВремя обучения · %d сек." % [cost_label(costs), seconds]
		var affordable := can_afford(costs)
		train.disabled = submission.pending or player_id.is_empty() or not paid_training or not queue_has_room or not unlocked or not affordable
		train.text = "Создаём заказ…" if submission.pending else "Обучить %d" % int(amount)
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
	train.pressed.connect(func():
		if train.disabled or command_in_progress:
			return
		count.apply()
		if train.disabled:
			return
		var amount := int(count.value)
		if submission.quantity != amount or submission.key.is_empty():
			submission.key = Crypto.new().generate_random_bytes(16).hex_encode()
			submission.quantity = amount
		submission.pending = true
		update_quote.call(count.value)
		var generation := modal_generation
		var submitted := await command(
			{"kind":"train", "buildingId":building.id, "unitId":unit.id, "quantity":amount,
				"requestId":submission.key, "paidTraining":true},
			refresh_recruitment.bind(building.id, unit.id, amount))
		if not submitted and generation == modal_generation:
			submission.pending = false
			update_quote.call(count.value))
	button(order, "Улучшить здание", inspect_building.bind(building))
	row(order, "ОЧЕРЕДЬ %d / 3" % queue.size())
	for index in 3:
		if index >= queue.size():
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
	var bounds := AABB()
	for part: MeshInstance3D in unit.find_children("*", "MeshInstance3D", true, false):
		var box := part.global_transform * part.get_aabb()
		bounds = box if not bounds.has_volume() else bounds.merge(box)
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

func encounter_title(encounter: Dictionary) -> String:
	var roman: String = ["I", "II", "III"][clampi(int(encounter.level), 1, 3) - 1]
	return "%s · %s" % [encounter.spec.name, roman]

func inspect_encounter(encounter: Dictionary) -> void:
	var city_hunt := map_name == "city"
	var spec: Dictionary = encounter.spec
	var level := int(spec.get("requiredHall", 1))
	var available: bool = encounter.status != "defeated" and int(encounter.hp) > 0
	open_modal(spec.name if city_hunt else encounter_title(encounter), "city_target" if city_hunt else "right",
		"ДИКИЕ ЗЕМЛИ" if city_hunt else "ДРЕНОВАР · ДИКИЕ ЗЕМЛИ")
	var details: Container = modal_body
	var art_panel := panel(4)
	art_panel.add_theme_stylebox_override("panel", WebPanels.gradient_style(Color("#465647"), Color("#1a2d25"), WebPanels.BRASS, 4))
	if city_hunt:
		var card := HBoxContainer.new()
		modal_body.add_child(card)
		card.add_child(art_panel)
		art_panel.custom_minimum_size.x = 144
		art_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		details = VBoxContainer.new()
		details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card.add_child(details)
		var portrait := VBoxContainer.new()
		art_panel.add_child(portrait)
		var preview := create_unit_preview(portrait, 145)
		var species: String = encounter.get("species", spec.get("id", ""))
		if data.creatureModels.has(species):
			var model: String = data.creatureModels[species][int(encounter.level) - 1]
			load_unit_preview.call_deferred(preview, {"preview":model, "drill":"idle"}, 0.63)
		row(portrait, "УР. %d" % int(encounter.level))
	else:
		modal_body.add_child(art_panel)
		panel_art(art_panel, "velkor%d.webp" % int(encounter.level), Vector2(0, 148))
	var tiers := HBoxContainer.new()
	details.add_child(tiers)
	var encounters: Array = state.get("encounters", []) if city_hunt else state.world.encounters
	for other in encounters:
		if other.get("species") != encounter.get("species"):
			continue
		var tier := button(tiers, ["I", "II", "III"][clampi(int(other.level), 1, 3) - 1], inspect_current_encounter.bind(other.id))
		tier.accessibility_name = encounter_title(other)
		if other.id == encounter.id:
			WebPanels.primary(tier)
	var health := ProgressBar.new()
	health.max_value = maxi(1, int(spec.hp))
	health.value = int(encounter.hp) if available else 0
	health.show_percentage = false
	health.custom_minimum_size.y = 9
	health.add_theme_stylebox_override("background", Interface.style(Color("#1c2524"), Color("#756345"), 4, 0, 0))
	health.add_theme_stylebox_override("fill", Interface.style(Color("#bcb968"), Color.TRANSPARENT, 4, 0, 0))
	details.add_child(health)
	row(details, "%d / %d здоровья" % [int(health.value), int(spec.hp)])
	var rewards: Dictionary = spec.get("rewards", {})
	if not rewards.is_empty():
		var material: String = {"claws":"когтей", "horns":"рогов", "fangs":"клыков", "scales":"чешуи"}.get(spec.get("item", ""), "трофеев")
		row(details, "За победу · %d еды · %d %s · %d опыта" %
			[int(rewards.get("food", 0)), int(rewards.get("material", 0)), material, int(spec.get("xp", 0))])
	if city_hunt:
		var dossier := VBoxContainer.new()
		button(details, "О существе", func(): dossier.visible = not dossier.visible)
		details.add_child(dossier)
		dossier.hide()
		row(dossier, "Мощь %d · Атака %d · Защита %d" % [int(spec.strength), int(spec.attack), int(spec.defense)])
	else:
		row(details, "Рывком бьёт по передней линии. Копейщики могут принять удар, пока стрелки ведут огонь.")
	if encounter.status == "reserved":
		row(details, "Эту цель уже преследует другой отряд.")
	elif not available:
		if encounter.get("respawnAt", 0) > server_time():
			var remaining := Label.new()
			details.add_child(remaining)
			bind_countdown(remaining, "Возрождение через", encounter.respawnAt)
		else:
			row(details, "Существо побеждено.")
	if hall_level() < level:
		row(details, "Требуется ратуша уровня %d." % level)
	elif player_id.is_empty():
		row(details, "Войдите в аккаунт, чтобы отправить отряд.")
	var p: Vector3 = stage.point(encounter.position)
	if available:
		for marker in stage.creature_markers:
			if marker.id == encounter.id:
				p = marker.position
				break
		stage.target = stage.ground_point(p)
		stage.zoom = minf(stage.zoom, 42.0 if city_hunt else 85.0)
	modal_footer.show()
	var attack := panel_action(modal_footer, "Атаковать" if city_hunt else "Собрать отряд",
		compose_march.bind("city" if city_hunt else "velkor", encounter.id, encounter_title(encounter)),
		not player_id.is_empty() and available and encounter.status == "alive" and hall_level() >= level)
	attack.size_flags_horizontal = Control.SIZE_EXPAND_FILL

func show_city_hunt() -> void:
	open_modal("Цели охоты", "garrison", "ДИКИЕ ЗЕМЛИ")
	append_hunt_targets(state.get("encounters", []))
	button(modal_body, "К поселению", show_city_actions)

func show_world_hunt() -> void:
	open_modal("Цели охоты", "right", "ДРЕНОВАР · ДИКИЕ ЗЕМЛИ")
	append_hunt_targets(state.world.encounters)
	button(modal_body, "К общему миру", show_world_directory)

func append_hunt_targets(encounters: Array) -> void:
	for encounter in encounters:
		var status: String = {"alive":"доступен", "reserved":"занят", "defeated":"побеждён"}.get(encounter.status, encounter.status)
		button(modal_body, "%s · ур. %d · %s" % [encounter.spec.name, int(encounter.level), status],
			inspect_current_encounter.bind(encounter.id))
	if encounters.is_empty():
		row(modal_body, "Здесь пока нет целей охоты.")

func compose_march(kind: String, id: String, title: String) -> void:
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
		formation.add_child(aside)
		row(aside, "СОСТАВ ОТРЯДА")
		aside.add_child(slots)
		row(aside, "%s → %s" % [state.city.name, title])
		route_map.custom_minimum_size.y = 90
		route_map.hide()
		aside.add_child(route_map)
		button(aside, "Обучить ещё воинов", show_training_buildings)
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
	var quote := Label.new()
	quote.name = "MarchQuote"
	quote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	roster.add_child(quote)
	modal_footer.show()
	var back := inspect_current_settlement.bind(id) if kind == "pvp" else inspect_current_encounter.bind(id)
	button(modal_footer, "Назад", back)
	modal_footer.add_child(summary)
	var send := panel_action(modal_footer, "Марш" if city else "Отправить отряд", func(): pass, false, not city)
	send.name = "MarchSend"
	var submit := {"order": {}, "sending": false}
	var generation := modal_generation
	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = 0.22 if city else 0.18
	roster.add_child(timer)
	var preview := {"revision": 0, "units": {}}
	var retry := button(roster, "Повторить расчёт", func(): timer.start())
	retry.hide()
	var update := func():
		var units := {}
		var power := 0
		for unit_id in selected:
			var count: int = int(selected[unit_id].value)
			if count > 0:
				units[unit_id] = count
				power += count * int(unit_for_id(unit_id).power)
		var total := total_units(units)
		summary.text = "%d / 200 воинов · мощь %d" % [total, power]
		if city:
			empty(slots)
			for unit_id in units:
				var unit: Dictionary = unit_for_id(unit_id)
				var slot := HBoxContainer.new()
				slots.add_child(slot)
				panel_art(slot, unit_id + ".png", Vector2(46, 46))
				var remove := button(slot, "%s × %d" % [unit.name, units[unit_id]], func(): selected[unit_id].value = 0)
				remove.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				remove.accessibility_name = "Убрать из отряда: " + unit.name
			if units.is_empty():
				row(slots, "Добавить войска из списка")
			if state.get("encounters", []).any(func(target): return target.id == id and target.get("species") == "tenerys" and int(target.level) == 1):
				row(slots, "Ориентир для Тенериса I: 15 новобранцев (900 мощи).")
		preview.revision += 1
		preview.units = units
		submit.order = {}
		retry.hide()
		send.disabled = true
		stage.clear_route()
		route_map.set_path([])
		if total == 0:
			timer.stop()
			quote.text = "Выберите воинов"
			return
		quote.text = "Прокладываем путь…" if city else "Рассчитываем маршрут…"
		timer.start()
	var set_party := func(all_available: bool):
		selection_batch.active = true
		fill_party(selected, all_available)
		selection_batch.active = false
		update.call()
	if city:
		var heading := Label.new()
		heading.text = "Доступные войска"
		heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tools.add_child(heading)
		button(tools, "Все доступные", set_party.bind(true))
		button(modal_footer, "Очистить", set_party.bind(false))
	var first_row_index := roster.get_child_count() - 1
	for unit in data.englishRoster:
		var available := int(state.healthy.get(unit.id, 0))
		if available < 1:
			continue
		var entry := panel(5)
		entry.add_theme_stylebox_override("panel", Interface.style(Color("#2b3036"), Color("#846d4d"), 6, 6, 5))
		roster.add_child(entry)
		roster.move_child(entry, first_row_index)
		first_row_index += 1
		var card := VBoxContainer.new()
		entry.add_child(card)
		var controls := HBoxContainer.new()
		card.add_child(controls)
		panel_art(controls, unit.id + ".png", Vector2(48, 48))
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		controls.add_child(info)
		row(info, unit.name)
		row(info, ("%s %d" % ["Доступно" if city else "В гарнизоне", available]))
		var amount := SpinBox.new()
		button(controls, "−", func(): amount.value -= 1)
		amount.min_value = 0
		amount.max_value = mini(available, 200)
		amount.custom_minimum_size.x = 70
		amount.get_line_edit().editable = city
		controls.add_child(amount)
		button(controls, "+", func(): amount.value += 1)
		selected[unit.id] = amount
		if city:
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
			if value > 200 - used:
				amount.set_value_no_signal(200 - used)
				amount.get_line_edit().text = str(int(amount.value))
				if city:
					(card.get_child(1) as HSlider).set_value_no_signal(amount.value)
			update.call())
	if selected.is_empty():
		row(roster, "Свободных воинов нет. Откройте казармы и завершите обучение.")
	timer.timeout.connect(func():
		if preview.units.is_empty() or generation != modal_generation:
			return
		var revision: int = preview.revision
		var order := {"kind":"deploy" if city else "worldMarch", "encounterId":id, "units":preview.units.duplicate()}
		if not city:
			order.worldKind = kind
		retry.hide()
		quote.text = "Прокладываем путь…" if city else "Рассчитываем маршрут…"
		var response := await send_request("march-preview" if loopback else "native/game/march-preview", order, false, 5.0)
		if generation != modal_generation or revision != preview.revision:
			return
		if response.get("httpStatus", 0) == 401 and not loopback:
			reset_session()
			close_modal()
			show_account()
			return
		if not response.has("path"):
			quote.text = response.get("error", "Путь недоступен")
			retry.show()
			return
		quote.text = "Прибытие через %d с%s" % [ceili((float(response.get("travelMs", 0)) + 1400.0) / 1000.0),
			" · через переправу" if response.get("usesFerry", false) else ""]
		stage.show_route(response.path)
		if city:
			route_map.set_path(response.path)
		order.requestId = Crypto.new().generate_random_bytes(16).hex_encode()
		submit.order = order
		send.disabled = submit.sending)
	send.pressed.connect(func():
		if submit.order.is_empty() or submit.sending:
			return
		submit.sending = true
		send.disabled = true
		var order: Dictionary = submit.order
		var result := await command(order, Callable() if city else show_world_directory)
		if not result and generation == modal_generation:
			submit.sending = false
			send.disabled = submit.order.is_empty())
	if city:
		set_party.call(true)
	else:
		update.call()

func fill_party(selected: Dictionary, all_available: bool) -> void:
	var remaining := 200 if all_available else 0
	for input: SpinBox in selected.values():
		input.value = minf(input.max_value, remaining)
		remaining -= int(input.value)

func show_account() -> void:
	open_modal("Твоё королевство", "profile", "ДРЕНОВАР · КОРОЛЕВСТВО")
	if not connected():
		if login_proof.is_empty():
			row(modal_body, "Войди через ChatGPT, чтобы открыть свои поселения и общий мир.")
			panel_action(modal_body, "Начать вход", begin_login)
			button(modal_body, "Проверка плавности", show_performance)
		else:
			var challenge := login_proof.sha256_text()
			var code := challenge.left(8).to_upper()
			row(modal_body, "Код подтверждения  " + code)
			row(modal_body, "На странице DRENOVAR войди в тот же аккаунт ChatGPT, введи код и нажми «Разрешить вход».")
			button(modal_body, "Открыть страницу входа", open_login_page.bind(challenge))
			var copy_buttons := HBoxContainer.new()
			modal_body.add_child(copy_buttons)
			button(copy_buttons, "Скопировать код", func(): DisplayServer.clipboard_set(code))
			button(copy_buttons, "Скопировать ссылку", copy_login_link.bind(challenge))
			button(modal_body, "Проверить вход", finish_login.bind(true))
			button(modal_body, "Получить новый код", begin_login)
		return
	if restoring_session:
		row(modal_body, "Подключаемся к сохранённому поселению…")
		button(modal_body, "Повторить подключение", restore_account)
		button(modal_body, "Выйти из аккаунта", confirm_profile_action.bind("Выйти из аккаунта на этом устройстве?", sign_out))
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
		for item in profile.profiles:
			var title := "%s · %d воинов" % [item.name, int(item.troops)]
			if item.active:
				row(modal_body, title + " · текущее поселение")
			else:
				button(modal_body, title, confirm_profile_action.bind("Открыть «%s»?" % item.name, select_profile.bind(item.id)))
		if profile.profiles.is_empty():
			button(modal_body, "Основать поселение", create_settlement)
	button(modal_body, "Выйти из приложения", confirm_profile_action.bind("Выйти из аккаунта на этом устройстве?", sign_out))

func add_name_fields(profile: Dictionary) -> void:
	var saved_nickname := str(profile.get("nickname")) if profile.get("nickname") != null else ""
	var saved_settlement: String = state.city.name
	var nickname := LineEdit.new()
	nickname.placeholder_text = "Имя игрока"
	nickname.max_length = 60
	nickname.text = saved_nickname
	modal_body.add_child(nickname)
	var settlement := LineEdit.new()
	settlement.placeholder_text = "Название поселения"
	settlement.max_length = 60
	settlement.text = saved_settlement
	modal_body.add_child(settlement)
	var save := Button.new()
	save.text = "Сохранить имена"
	save.custom_minimum_size.y = 42
	save.disabled = true
	modal_body.add_child(save)
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
		var accepted := await command(changes, show_account)
		if not accepted and is_instance_valid(nickname) and nickname.is_inside_tree():
			nickname.editable = true
			settlement.editable = true
			refresh_save.call(""))

func confirm_profile_action(title: String, action: Callable) -> void:
	open_modal("Подтверждение")
	row(modal_body, title)
	button(modal_body, "Подтвердить", action)
	button(modal_body, "Отмена", show_account)

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
	var output_size := get_viewport().get_texture().get_size()
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
	row(modal_body, report)
	button(modal_body, "Скопировать замер", func(): DisplayServer.clipboard_set(report))

func connected() -> bool:
	return loopback or not session.is_empty()

func begin_login() -> void:
	login_proof = Crypto.new().generate_random_bytes(32).hex_encode()
	login_deadline = Time.get_ticks_msec() + 300000
	login_link_used = false
	show_account()

func login_url(challenge: String) -> String:
	return endpoint + "/api/native/approve?challenge=" + challenge

func copy_login_link(challenge: String) -> void:
	if Time.get_ticks_msec() >= login_deadline:
		begin_login()
		set_login_status("Код истёк. Открой страницу с новым кодом.")
		return
	DisplayServer.clipboard_set(login_url(challenge))
	login_link_used = true
	set_login_status("Ссылка скопирована. Вставь её в адресную строку Safari.")

func open_login_page(challenge: String) -> void:
	if Time.get_ticks_msec() >= login_deadline:
		begin_login()
		set_login_status("Код истёк. Открой страницу с новым кодом.")
		return
	if OS.shell_open(login_url(challenge)) != OK:
		set_login_status("Не удалось открыть браузер. Скопируй ссылку и открой её в Safari.")
		return
	login_link_used = true
	set_login_status("Если браузер не открылся, скопируй ссылку и вставь её в Safari.")

func set_login_status(value: String) -> void:
	if modal.visible and modal_title.text == "Твоё королевство":
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
		if modal.visible and modal_title.text == "Твоё королевство":
			show_account()
			set_login_status("Код истёк. Начни вход заново.")
		return
	var proof := login_proof
	login_in_progress = true
	if manual:
		set_login_status("Проверяем подтверждение…")
	var response := await send_request("native/exchange", {"proof":proof})
	if proof != login_proof:
		login_in_progress = false
		return
	if response.get("session") is String and SessionStore.valid(response.session):
		session = response.session
		saved_session_error = SessionStore.save_session(session) != OK
		login_proof = ""
		message.text = ""
		await sync_account()
		if modal.visible and modal_title.text == "Твоё королевство":
			await show_account()
	elif response.get("pending", false):
		if manual:
			set_login_status("Подтверждение ещё не получено. В Safari введи код и нажми «Разрешить вход».")
	elif modal.visible and modal_title.text == "Твоё королевство":
		show_error(response)
	login_in_progress = false

func restore_account() -> void:
	restoring_session = true
	var response := await send_request("native/game/state", null, true, 5.0)
	apply_restored_state(response)

func apply_restored_state(response: Dictionary) -> void:
	if response.get("httpStatus", 0) == 401:
		reset_session()
		if modal.visible and modal_title.text == "Твоё королевство":
			show_account.call_deferred()
		return
	if response.has("city") and response.has("world"):
		restoring_session = false
		accept(response)
		message.text = ""
		if modal.visible and modal_title.text == "Твоё королевство":
			show_account.call_deferred()
	elif response.get("needsSettlement", false):
		restoring_session = false
		message.text = "Открой профиль, чтобы основать поселение"
		if modal.visible and modal_title.text == "Твоё королевство":
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
			message.text = "Открой профиль в левом верхнем углу, чтобы основать поселение"
			return
	if not response.has("city"):
		show_error(response)
		return
	accept(response)

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

func sign_out() -> void:
	var response := await send_request("native/logout", {})
	if not response.get("signedOut", false) and response.get("httpStatus", 0) != 401:
		show_error(response)
		return
	reset_session("sign_out")
	await show_account()

func reset_session(reason := "auth_401") -> void:
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
	refresh_hud()

func show_reports() -> void:
	open_modal("Летопись сражений", "right")
	if state.reports.is_empty():
		row(modal_body,"Пока нет боевых отчётов.")
		return
	var reports: Array = state.reports.duplicate()
	reports.reverse()
	for report in reports:
		button(modal_body, "%s · %s" % [report.creature.name, battle_outcome(report)], show_report.bind(report))

func battle_outcome(report: Dictionary) -> String:
	return "Победа" if report.outcome == "victory" else "Поражение"

func update_battle_result_notice() -> void:
	var available := not battle_results.pending.is_empty() and Time.get_ticks_msec() >= battle_results.ready_at
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
	var sigil := result_label(heading, "⚔", 37, Color("#e5c57d"))
	sigil.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var back := close_modal if announced else show_reports
	var dismiss := button(heading, "×", back)
	dismiss.custom_minimum_size = Vector2(58, 54)
	dismiss.tooltip_text = "Закрыть"
	dismiss.accessibility_name = "Закрыть результат боя"
	result_label(modal_body, title, 37, Color("#f1d28c"), true)
	var opponent: Dictionary = report.get("creature", {})
	result_label(modal_body, "%s · уровень %d" % [opponent.get("name", "Цель"), int(opponent.get("level", 1))], 21, Color("#becab2"))
	var stats := HBoxContainer.new()
	stats.add_theme_constant_override("separation", 9)
	modal_body.add_child(stats)
	for section in [["surviving", "В строю"], ["wounded", "Ранены"], ["dead", "Погибли"]]:
		var box := panel(5)
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		box.add_theme_stylebox_override("panel", Interface.style(Color("#162e24"), Color("#a8995966"), 7, 5, 7))
		stats.add_child(box)
		var labels := VBoxContainer.new()
		box.add_child(labels)
		result_label(labels, format_balance(total_units(report.get(section[0], {}))), 33, WebPanels.IVORY, true)
		result_label(labels, section[1], 15, Color("#b6c4ab"))
	var rewards: Dictionary = report.get("rewards", {})
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
		"forest_crystal":"Лесной кристалл", "stone_crystal":"Каменный кристалл", "ember_crystal":"Огненный кристалл"}
	for id in items:
		if int(items[id]) > 0:
			add_reward_chip(loot, item_names.get(id, id), int(items[id]))
	if int(rewards.get("xp", 0)) > 0:
		add_reward_chip(loot, "Опыт", int(rewards.xp))
	loot.visible = loot.get_child_count() > 0
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

func add_reward_chip(parent: Container, name: String, amount: int, icon := "") -> void:
	var chip := panel(5)
	chip.add_theme_stylebox_override("panel", Interface.style(Color("#0c2119"), Color("#b49a5980"), 5, 8, 4))
	parent.add_child(chip)
	var content := HBoxContainer.new()
	chip.add_child(content)
	if not icon.is_empty():
		add_resource_icon(content, icon, 24)
	result_label(content, "%s +%s" % [name, format_balance(amount)], 17, WebPanels.IVORY)

func accept(response: Dictionary) -> void:
	if not response.has("city") or not response.has("world"):
		return
	state = response
	player_id = state.playerId
	battle_results.observe(player_id, state.get("reports", []))
	server_offset = float(state.serverTime)-Time.get_unix_time_from_system()*1000
	refresh_hud()
	if is_instance_valid(stage):
		stage.present(state)
	refresh_economy()
	if starter_panel_open and not command_in_progress and state.get("starterEligible71", false):
		show_starter_goals()
	if relocation_pins.visible:
		relocation_pins.queue_redraw()

func show_error(response: Dictionary) -> void:
	message.text = response.get("error","Ответ сервера не удалось прочитать.")
	if modal.visible:
		modal_status.text = message.text
		modal_status.show()

func command(order: Dictionary, after_success := Callable()) -> bool:
	if command_in_progress:
		return false
	command_in_progress = true
	var generation := modal_generation
	if modal.visible:
		modal_status.text = "Отправляем запрос…"
		modal_status.show()
	var signature := JSON.stringify(order)
	var key: String = str(order.get("requestId", ""))
	if key.is_empty():
		key = retry_keys.get(signature, Crypto.new().generate_random_bytes(16).hex_encode())
	var response: Dictionary = await request("command", order, key)
	if response.get("transportFailure", false) or int(response.get("httpStatus", 0)) >= 500:
		retry_keys[signature] = key
	else:
		retry_keys.erase(signature)
	if not response.has("city"):
		command_in_progress = false
		if generation == modal_generation:
			show_error(response)
		return false
	accept(response)
	command_in_progress = false
	if generation == modal_generation:
		modal_status.hide()
		if after_success.is_valid():
			after_success.call()
		else:
			close_modal()
	message.text = "Действие выполнено"
	return true

func request(path: String, payload: Variant = null, idempotency_key := "") -> Dictionary:
	if not connected():
		return {"error":"Сначала войди в аккаунт."}
	var response := await send_request(path if loopback else "native/game/" + path, payload, true, 12.0, idempotency_key)
	if not loopback and response.get("httpStatus", 0) == 401:
		reset_session()
	return response

func send_request(path: String, payload: Variant = null, foreground := true, timeout_seconds := 12.0, idempotency_key := "") -> Dictionary:
	if foreground and busy:
		return {"error":"Подожди завершения предыдущего запроса."}
	if foreground:
		busy = true
		request_generation += 1
	var client := HTTPRequest.new()
	client.timeout = timeout_seconds
	# A stalled preview must not block cancellation while the server withholds headers.
	client.use_threads = path.get_file() != "march-preview"
	client.max_redirects = 0
	client.body_size_limit = 8 * 1024 * 1024
	add_child(client)
	var headers := PackedStringArray(["Accept: application/json"])
	if player_id != "":
		headers.append("X-Drenovar-Player: "+player_id)
	if not session.is_empty():
		headers.append("X-Drenovar-Session: " + session)
	if payload != null:
		headers.append("Content-Type: application/json")
		headers.append("Origin: "+endpoint)
		var request_key := idempotency_key
		if request_key.is_empty() and path.get_file() == "command" and payload is Dictionary:
			request_key = str(payload.get("requestId", ""))
		if request_key.is_empty():
			request_key = Crypto.new().generate_random_bytes(16).hex_encode()
		headers.append("Idempotency-Key: "+request_key)
	var error := client.request(endpoint+"/api/"+path,headers,HTTPClient.METHOD_GET if payload==null else HTTPClient.METHOD_POST,"" if payload==null else JSON.stringify(payload))
	if error != OK:
		client.queue_free()
		if foreground:
			busy = false
		return {"error":"Сервер недоступен"}
	var result: Array = await client.request_completed
	client.queue_free()
	if foreground:
		busy = false
	var transport_ok: bool = result[0] == HTTPRequest.RESULT_SUCCESS and int(result[1]) > 0 and int(result[1]) < 500
	diagnostics.network_result(transport_ok, "timeout" if result[0] == HTTPRequest.RESULT_TIMEOUT else ("http_%d" % int(result[1]) if result[0] == HTTPRequest.RESULT_SUCCESS else "transport_%d" % int(result[0])),
		Time.get_unix_time_from_system(), Time.get_ticks_msec())
	update_connection_notice()
	if result[0] != HTTPRequest.RESULT_SUCCESS or result[3].is_empty():
		if result[0] == HTTPRequest.RESULT_TIMEOUT:
			return {"error":"Сервер не ответил вовремя. Проверь соединение и повтори.", "transportFailure":true}
		if result[0] == HTTPRequest.RESULT_TLS_HANDSHAKE_ERROR:
			return {"error":"Не удалось установить защищённое соединение с сервером.", "transportFailure":true}
		return {"error":"Сервер недоступен", "transportFailure":true}
	var response := JSON.new()
	if response.parse(result[3].get_string_from_utf8()) == OK and response.data is Dictionary:
		if int(result[1]) >= 400:
			response.data.httpStatus = result[1]
		return response.data
	return {"error":"Сервер вернул неожиданный ответ (HTTP %d)." % int(result[1])}

func update_connection_notice() -> void:
	# Two consecutive transport failures mean the link is down, not a single blip.
	var offline := diagnostics.network_failures >= 2 and connected()
	if offline and not offline_notice_shown:
		offline_notice_shown = true
		message.text = OFFLINE_NOTICE
	elif not offline and offline_notice_shown:
		offline_notice_shown = false
		if message.text == OFFLINE_NOTICE:
			message.text = "Связь восстановлена"

func poll_account_state() -> void:
	if polling_state or busy or login_in_progress or not connected() or (player_id.is_empty() and not restoring_session):
		return
	polling_state = true
	var generation := request_generation
	var response := await send_request("state" if loopback else "native/game/state", null, false)
	polling_state = false
	if generation != request_generation:
		return
	if restoring_session:
		apply_restored_state(response)
	elif not loopback and response.get("httpStatus", 0) == 401:
		reset_session()
	elif response.get("profileChanged", false):
		player_id = ""
		await sync_account()
	else:
		accept(response)

func _process(delta: float) -> void:
	drain_retired_scenes()
	diagnostics.heartbeat(map_name, Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0,
		Time.get_ticks_msec() / 1000.0, Time.get_unix_time_from_system(), Time.get_ticks_msec())
	if not is_instance_valid(stage) or scene_loading:
		return
	var camera_moving := stage.camera_dirty or stage.camera_target.distance_squared_to(stage.target) >= 0.01 or \
		absf(stage.camera_zoom - stage.zoom) >= 0.1 or absf(angle_difference(stage.camera_yaw, stage.world_yaw)) >= 0.01
	update_fling(delta)
	camera_moving = camera_moving or fling_velocity != Vector2.ZERO
	stage.update_camera(delta)
	if relocation_pins.visible and camera_moving:
		relocation_pins.queue_redraw()
	if scene_cache.size() > 1:
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
	stage.present_armies(state, now)
	if not followed_army.is_empty():
		var found := false
		for marker in stage.army_markers:
			if marker.id == followed_army:
				stage.target = marker.position - Vector3.UP * 2.6
				found = true
				break
		if not found:
			followed_army = ""
	stage.present_creatures(state, now, delta)
	if map_name == "world":
		var now_ms := Time.get_ticks_msec()
		if now_ms >= next_minimap_draw:
			minimap.update_locations(state.world.cities, state.world.encounters, player_id)
			minimap.armies = stage.army_markers
			minimap.focus = Vector2(stage.camera_target.x, stage.camera_target.z)
			minimap.queue_redraw()
			next_minimap_draw = now_ms + 50
	else:
		stage.present_parade()
		stage.present_workers(now / 1000.0)
	if map_name == "city" and now >= next_training_update:
		stage.present_training(state, now)
		next_training_update = now + 300.0
	poll += delta
	if poll <= 0.8 or busy or login_in_progress:
		return
	var active_march: bool = state.world.armies.any(func(army): return army.owner == player_id or army.target == player_id)
	active_march = active_march or state.get("armies", []).any(func(army): return army.status != "returned")
	# Back off while the server is unreachable: 0.8/5 s normally, up to 15 s offline.
	var interval := (0.8 if active_march else 5.0) * pow(2.0, mini(diagnostics.network_failures, 4))
	if poll > minf(interval, maxf(15.0, 0.8 if active_march else 5.0)):
		poll = 0
		if login_link_used and not login_proof.is_empty():
			await finish_login()
		elif connected() and (not player_id.is_empty() or restoring_session):
			await poll_account_state()

func _input(event: InputEvent) -> void:
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
		if event.pressed:
			fling_velocity = Vector2.ZERO
			drag_samples.clear()
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
	for marker in stage.place_markers + stage.army_markers + stage.creature_markers:
		if stage.camera.is_position_behind(marker.position):
			continue
		var at: Vector2 = stage.camera.unproject_position(marker.position)
		var gap := at.distance_to(screen_position)
		if gap < distance:
			best = marker
			distance = gap
	if best.get("kind","") == "building":
		inspect_building(best.item)
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
	open_modal(str(army.get("name", "Поход")))
	var status: String = {"outbound":"В пути", "fighting":"В бою", "returning":"Возвращается"}.get(army.status, army.status)
	row(modal_body, status)
	var units: Dictionary = army.get("returnUnits", army.units) if army.status == "returning" else army.units
	for id in units:
		if int(units[id]) > 0:
			row(modal_body, "%s × %d" % [unit_for_id(id).get("name", id), int(units[id])])
	button(modal_body, "Следить за отрядом", focus_army.bind(army))
	var finish: Variant = army.get("returnsAt") if army.status == "returning" else (army.get("battleEndsAt") if army.status == "fighting" else army.get("arrivesAt"))
	if finish != null:
		countdown("До следующей фазы", float(finish))
	if map_name == "city" and army.status == "outbound" and not player_id.is_empty():
		button(modal_body, "Отозвать отряд", command.bind({"kind":"recall", "armyId":army.id}))

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
	open_modal(item.name, "right", "ПОСЕЛЕНИЕ")
	row(modal_body, "Ратуша · уровень %d" % int(item.level))
	if item.get("nickname") is String and not item.nickname.is_empty():
		row(modal_body, "Игрок · " + item.nickname)
	button(modal_body, "Рассмотреть на карте", focus_minimap.bind(Vector2(item.position.x, item.position.z)))
	if item.id == state.playerId:
		button(modal_body, "Войти в город", show_scene.bind("city"))
		button(modal_body, "Найти место для переселения", show_relocation)
	elif item.get("pvp", false):
		var own_index: int = state.world.cities.find_custom(func(city): return city.id == player_id)
		var eligible: bool = own_index >= 0 and state.world.cities[own_index].get("pvp", false)
		if own_index >= 0 and not eligible:
			row(modal_body, "Ваше поселение · " + state.world.cities[own_index].get("pvpReason", "PvP закрыто"))
		panel_action(modal_body, "Собрать отряд", compose_march.bind("pvp", item.id, item.name), eligible)
	elif item.get("pvpReason") is String:
		row(modal_body, item.pvpReason)
	button(modal_body, "К списку городов", show_world_cities)

func inspect_current_settlement(id: String) -> void:
	for item in state.world.cities:
		if item.id == id:
			inspect_settlement(item)
			return

func inspect_world_plot(item: Dictionary) -> void:
	open_modal("Свободное место", "right", "ПЕРЕСЕЛЕНИЕ")
	var current: String = state.city.get("worldSlotId", "")
	if not current.begins_with("slot-") or not current.trim_prefix("slot-").is_valid_int():
		return
	var reason: String = state.world.get("relocationReason", "")
	if not reason.is_empty():
		row(modal_body, reason)
		return
	row(modal_body, "Координаты · %d : %d" % [roundi(float(item.x) + 150), roundi(float(item.z) + 120)])
	var order := {"kind":"relocateCity","slot":int(item.slot.trim_prefix("slot-")),"fromSlot":int(current.trim_prefix("slot-"))}
	button(modal_body, "Выбрать другое место", show_relocation)
	var occupied: bool = state.world.cities.any(func(city): return city.slot == item.slot)
	if occupied:
		row(modal_body, "Это место уже занято. Выбери другое.")
	panel_action(modal_body, "Подтвердить переселение", command.bind(order, focus_own_city),
		not player_id.is_empty() and not occupied)

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
	open_modal("Переселение", "right")
	var origin := stage.target
	for city in state.world.cities:
		if city.id == player_id:
			origin = stage.point(city.position)
			break
	var sites: Array = stage.empty_plots.duplicate()
	sites.sort_custom(func(a, b):
		return origin.distance_squared_to(a.position) < origin.distance_squared_to(b.position))
	if sites.is_empty():
		row(modal_body, "Свободных мест пока нет.")
	for site in sites:
		button(modal_body, "%d : %d" % [roundi(site.position.x + 150), roundi(site.position.z + 120)], func():
			stage.target = site.position
			stage.zoom = 85.0
			inspect_world_plot(site.item))

func inspect_plot(plot: Dictionary) -> void:
	open_modal("Участок", "right")
	row(modal_body, "Координаты · %d : %d" % [roundi(plot.x), roundi(plot.z)])
	var kingdom: Variant = state.city.get("kingdom")
	if not kingdom is Dictionary:
		for definition in data.buildings:
			if definition.base != "ECO-05" and data.types.has(definition.id):
				button(modal_body, definition.ru, command.bind({"kind":"legacyBuilding", "action":"place",
					"type":definition.id, "plotId":plot.id}), not player_id.is_empty() and construction_order().is_empty())
		button(modal_body, "К списку участков", show_construction)
		return
	var builder_ready := construction_order().is_empty() and state.city.progress.get("job") == null
	if plot.id not in kingdom.get("clearedPlots", []) and not plot.id.begins_with("site-"):
		button(modal_body, "Расчистить · 15 еды · 6 сек.", command.bind({"kind":"kingdom","action":"clear","plotId":plot.id}),
			not player_id.is_empty() and builder_ready and balance("food") >= 15)
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
				not player_id.is_empty() and builder_ready and can_afford(terms.cost))
		else:
			row(modal_body, "%s · ратуша %d" % [definition.ru, required])
	button(modal_body, "К списку участков", show_construction)

func pick_tree(screen_position: Vector2) -> void:
	var distance := 18.0
	var selected := {}
	var felled: Array = state.city.get("progress", {}).get("felled", [])
	for tree in stage.selectable_trees:
		var p := stage.array_point(tree.p) + Vector3(0, 1, 0)
		if p.distance_squared_to(stage.camera_target) > 68.0 * 68.0 or stage.camera.is_position_behind(p):
			continue
		var gap := stage.camera.unproject_position(p).distance_to(screen_position)
		if gap < distance:
			distance = gap
			selected = tree
	if selected.is_empty():
		return
	open_modal(selected.name)
	if selected.id in felled:
		var order := {"kind":"resource","action":"site","id":selected.id}
		button(modal_body,"Подготовить участок",command.bind(order),not player_id.is_empty())
	else:
		row(modal_body, "%d дерева · %.0f сек." % [int(selected.wood), float(selected.durationMs) / 1000])
		var order := {"kind":"resource","action":"tree","id":selected.id}
		button(modal_body,"Срубить",command.bind(order),not player_id.is_empty())

func run_smoke() -> void:
	await get_tree().process_frame
	if stage.place_markers.size() != 4 or endpoint == "" or player_id == "":
		get_tree().quit(2)
		return
	var city_children: int = stage.trees.node.get_child_count()
	if stage.parade_slots.size() != int(state.healthy.get("ENG-09", 0)):
		printerr("Parade composition differs from the server garrison.")
		get_tree().quit(23)
		return
	if stage.terrain_bounds.size.x < 670.0 or stage.terrain_bounds.size.z < 670.0:
		get_tree().quit(14)
		return
	var barracks: Dictionary = state.city.buildings.filter(func(b): return b.type == "MIL-01")[0]
	inspect_building(barracks)
	var footman := unit_for_id("ENG-09")
	if footman.is_empty() or not modal.visible:
		get_tree().quit(10)
		return
	show_recruitment(barracks, footman, true)
	var preview_view := modal_body.find_child("RecruitPreview", true, false) as SubViewportContainer
	var preview_deadline := Time.get_ticks_msec() + 5000
	while preview_view != null and preview_view.get_child_count() == 0 and Time.get_ticks_msec() < preview_deadline:
		await get_tree().process_frame
	if preview_view == null or preview_view.get_child_count() != 1 or data.unitModels.size() != 10:
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
	var order := {"kind":"worldMarch","worldKind":"velkor","encounterId":encounter.id,"units":{"ENG-09":int(state.healthy["ENG-09"])}}
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
	if quantity.value <= 0 or not send.disabled or modal_title.text != "Создать войско":
		return false
	var clear_button := modal_footer.get_children().filter(func(child): return child is Button and child.text == "Очистить")[0] as Button
	clear_button.pressed.emit()
	if not send.disabled or quote.text != "Выберите воинов":
		return false
	quantity.value = 1
	var deadline := Time.get_ticks_msec() + 8000
	var retry := modal_body.find_children("*", "Button", true, false).filter(func(child): return child.text == "Повторить расчёт")[0] as Button
	while send.disabled and not retry.visible and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if OS.get_environment("DRENOVAR_TEST_CITY_PREVIEW_TIMEOUT") == "1":
		if not retry.visible or quantity.value != 1 or not send.disabled:
			return false
		retry.pressed.emit()
		deadline = Time.get_ticks_msec() + 8000
		while send.disabled and Time.get_ticks_msec() < deadline:
			await get_tree().process_frame
		print("DRENOVAR native smoke: recovered from city march preview timeout.")
	var confirmed := not send.disabled and is_instance_valid(stage.route_preview) and quote.text.begins_with("Прибытие")
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
