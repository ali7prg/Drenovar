extends RefCounted
## The menu, the account and its pairing code, the names window and the confirmations
## (premium UI stage 4b, ui_premium/STAGE4B.md).
##
## «Меню»: a full window. At the left, on dark oak, the settlement's crest with its name, the
## hall level and a few figures, and the settings as premium switches (sound, less motion).
## At the right, grouped medallion tiles (Поселение, Карта, Сведения) with enamel badges: free
## builders, running work, rewards ready, unread reports. Every tile is a real Button whose
## `text` is its caption.
## «Аккаунт»: the same oak column (or the game's crest before a city is joined) and, at the
## right, what the player can do now as cards: sign in (a large code), another device (the
## pairing code), names and settlements, the archive, join by code, sign out.
## «Код подключения»: the code large and legible in groups of four, the time it is valid,
## «Скопировать код». The code is drawn, never printed or logged.
## Confirmations: a small centred window with a medallion, the question, «Отмена» and the
## action.

const UiKit = preload("res://src/ui_kit.gd")
const KitMore = preload("res://src/kit_more.gd")
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]

var panels
var ui
var last_open_usec := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

# ------------------------------------------------------------------ shared parts

## The left column on dark oak: the profile card and, under it, extra controls.
func oak_column(card: Control, share := 0.3) -> VBoxContainer:
	var hero: Control = ui.modal_hero
	var backdrop := Panel.new()
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var back := UiKit.nine("kit_body_dark", Vector4.ZERO, Vector4.ZERO, true)
	backdrop.add_theme_stylebox_override("panel", back)
	hero.add_child(backdrop)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	hero.add_child(column)
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	column.offset_left = 26
	column.offset_right = -20
	column.offset_top = 26
	column.offset_bottom = -16
	card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(card)
	ui.modal_hero_share = share
	ui.arrange_modal()
	return column

## A colour of the settlement's pennant, the same for a name every time.
static func banner_colour(seed_text: String) -> Color:
	var colours := [Color("#8e2419"), Color("#2c5a86"), Color("#2f6b3a"), Color("#6b3f86"), Color("#9a6a1a"), Color("#7a2f4f")]
	return colours[absi(hash(seed_text)) % colours.size()]

func hall_line() -> String:
	if panels.enabled():
		var hall: Dictionary = panels.building("B01")
		if not hall.is_empty():
			return "%s %s" % [str(panels.row_for("B01", 1).get("name_ru", "Ратуша")), ROMAN[clampi(int(hall.get("level", 1)), 1, 11) - 1]]
	return "Ратуша %s" % ROMAN[clampi(int(ui.hall_level()), 1, 11) - 1]

## The player's settlement on the profile card: name, hall, troops at home, builders, work.
func settlement_card() -> Control:
	var card := KitMore.ProfileCard.new()
	card.name = "ProfileCard"
	card.emblem = UiKit.tex("kit_emb_helm")
	var city: Dictionary = ui.state.get("city", {})
	card.title = str(city.get("name", "Поселение"))
	card.banner = banner_colour(str(ui.player_id) + card.title)
	card.pill = hall_line()
	if panels.enabled():
		var v6: Dictionary = ui.state.v6
		var home := 0
		for id: String in v6.get("healthy", {}):
			home += int(v6.healthy[id])
		var use: Array = panels.build.builder_use() if panels.build != null else [0, 0]
		var running: int = v6.get("orders", []).filter(func(o): return o.get("status", "") == "pending").size()
		card.lines = [["Воинов дома", ui.format_balance(home), UiKit.tex("kit_emb_sword")],
			["Строители", "%d из %d свободны" % [maxi(0, int(use[1]) - int(use[0])), int(use[1])], UiKit.tex("kit_emb_craft")],
			["Работы в очередях", str(running), UiKit.tex("kit_emb_speed")],
			["Армия", "%s / %s" % [UiKit.compact(int(v6.get("army_used", 0))), UiKit.compact(int(v6.get("army_capacity", 0)))], UiKit.tex("kit_emb_shield")]]
	elif not ui.player_id.is_empty():
		card.lines = [["Поселение", "подключено", null]]
	return card

## The game's crest before a settlement is joined (the account entry at the first launch).
func game_card() -> Control:
	var card := KitMore.ProfileCard.new()
	card.name = "ProfileCard"
	card.emblem = UiKit.tex("kit_emb_key")
	card.title = "DRENOVAR"
	card.banner = Color("#2c5a86")
	card.pill = "Общий город" if primary_server() else "Тестовый мир"
	card.lines = [["Версия", str(ProjectSettings.get_setting("application/config/version")), null],
		["Сборка", str(ProjectSettings.get_setting("application/config/build_number", "")), null]]
	card.note = "Город хранится на сервере."
	return card

func primary_server() -> bool:
	return ui.endpoint == "https://drenovar-game.ali069587.workers.dev"

func tile_grid(parent: Container) -> GridContainer:
	var grid := GridContainer.new()
	grid.columns = 6
	grid.theme = KitMore.drawn_buttons_theme()
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	parent.add_child(grid)
	return grid

func tile(grid: Container, caption: String, emblem: String, action: Callable, note := "", badge := "", tone := "red") -> Button:
	var control := KitMore.MenuTile.new().setup(caption, emblem, note, badge, tone)
	control.name = "Tile_" + emblem.trim_prefix("kit_emb_")
	control.pressed.connect(action)
	grid.add_child(control)
	return control

func close_then(action: Callable) -> Callable:
	return func():
		ui.close_modal()
		action.call()

## A muted note on linen (calm: what to do next, never alarming).
func note(text: String, colour := UiKit.INK_MUTED, size := 16) -> Label:
	var label: Label = UiKit.label(ui.modal_body, text, size, colour)
	return label

func card(title: String, subtitle: String, emblem: String, height := 88.0) -> Control:
	var row := KitMore.Card.new()
	row.title = title
	row.subtitle = subtitle
	row.icon = UiKit.tex(emblem)
	row.icon_mode = "disc"
	row.custom_minimum_size.y = height
	ui.modal_body.add_child(row)
	return row

func styled(control: Button, kind: String, size := 18, height := 50.0) -> Button:
	UiKit.style_button(control, kind, size)
	control.custom_minimum_size.y = height
	return control

# ------------------------------------------------------------------ menu

func open() -> void:
	var started := Time.get_ticks_usec()
	var selecting: bool = ui.relocation_pins.visible
	var city: bool = ui.map_name == "city"
	ui.open_modal("Меню", "full", "DRENOVAR")
	var column := oak_column(settlement_card() if not ui.player_id.is_empty() else game_card())
	settings(column)
	var v6: bool = panels.enabled()
	if selecting:
		UiKit.section_header(ui.modal_body, "Переселение")
		var moving := tile_grid(ui.modal_body)
		tile(moving, "Список свободных мест", "kit_emb_march", ui.show_relocation_list)
		tile(moving, "Вернуться к выбору на карте", "kit_emb_map", ui.show_relocation)
	UiKit.section_header(ui.modal_body, "Поселение")
	var home := tile_grid(ui.modal_body)
	home.name = "MenuSettlement"
	var builders: String = ui.nav_buttons.build.badge if ui.nav_buttons.has("build") else ""
	tile(home, "Поселение и строительство", "kit_emb_craft", ui.show_city_actions, "", builders, "green")
	if v6:
		var running: int = ui.state.v6.get("orders", []).filter(func(o): return o.get("status", "") == "pending").size()
		tile(home, "Очереди", "kit_emb_speed", panels.queues, "", str(running) if running > 0 else "", "bronze")
	tile(home, "Экономика", "kit_emb_sheaf", ui.show_economy)
	var ready := 0
	if v6:
		for step: Dictionary in ui.state.v6.get("starter", []):
			if step.get("ready", false) and not step.get("claimed", false):
				ready += 1
	tile(home, "Цели поселения", "kit_emb_award", panels.objectives if v6 else ui.show_starter_goals, "", str(ready) if ready > 0 else "", "green")
	tile(home, "Армия", "kit_emb_sword", ui.show_armies)
	var unread: String = ui.nav_buttons.reports.badge if ui.nav_buttons.has("reports") else ""
	tile(home, "Летопись сражений", "kit_emb_scroll", ui.show_reports, "", unread, "red")
	UiKit.section_header(ui.modal_body, "Карта и вид")
	var map := tile_grid(ui.modal_body)
	map.name = "MenuMap"
	if city:
		tile(map, "Центрировать город", "kit_emb_aim", close_then(ui.center_city))
		tile(map, "Карта мира", "kit_emb_map", close_then(ui.show_scene.bind("world")))
	else:
		tile(map, "Показать весь мир", "kit_emb_map", ui.show_world_overview)
		tile(map, "Общий мир", "kit_emb_globe", ui.show_world_directory)
		tile(map, "Слои карты", "kit_emb_layers", ui.show_map_options)
		tile(map, "Повернуть карту", "kit_emb_rotate", close_then(ui.rotate_world))
		tile(map, "Мой город", "kit_emb_town", close_then(ui.show_scene.bind("city")))
	tile(map, "Приблизить", "kit_emb_zoom_in", close_then(ui.zoom_scene.bind(1.2)))
	tile(map, "Отдалить", "kit_emb_zoom_out", close_then(ui.zoom_scene.bind(0.83)))
	UiKit.section_header(ui.modal_body, "Сведения")
	var about := tile_grid(ui.modal_body)
	about.name = "MenuAbout"
	tile(about, "Аккаунт", "kit_emb_key", ui.show_account)
	var forest = ui.forest_game
	if forest != null and forest.client.available(): # FOREST_RESCUE hook: journal entry
		tile(about, str(forest.content.text("title")), "kit_emb_tree", forest.open_journal)
	tile(about, "Плавность на устройстве", "kit_emb_gauge", ui.show_performance)
	tile(about, "О приложении", "kit_emb_info", ui.show_application)
	last_open_usec = Time.get_ticks_usec() - started

## The settings under the profile card: premium switches on the oak.
func settings(column: VBoxContainer) -> void:
	var caption: Label = UiKit.label(column, "Настройки", 16, UiKit.GOLD_DIM, UiKit.LABEL_FONT, false)
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	for entry: Array in [["Звук", ui.sound_on, ui.set_sound, "SoundSwitch"], ["Меньше движения", ui.reduced_motion, ui.set_reduced_motion, "MotionSwitch"]]:
		var toggle := CheckButton.new()
		toggle.name = entry[3]
		toggle.text = entry[0]
		toggle.button_pressed = entry[1]
		toggle.focus_mode = Control.FOCUS_NONE
		toggle.custom_minimum_size.y = 40
		for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
			toggle.add_theme_color_override(state, UiKit.IVORY)
		toggle.toggled.connect(entry[2])
		column.add_child(toggle)

## «Поселение» (city actions of a V6 settlement): a docked window of tiles.
func city_actions() -> void:
	ui.open_modal("Поселение", "right", "ОБЩИЙ ГОРОД · I–XI")
	var grid := tile_grid(ui.modal_body)
	grid.columns = 3
	var builders: String = ui.nav_buttons.build.badge if ui.nav_buttons.has("build") else ""
	tile(grid, "Строить", "kit_emb_craft", panels.catalog, "", builders, "green")
	tile(grid, "Очереди и отмена", "kit_emb_speed", panels.queues)
	tile(grid, "Ресурсы и доход", "kit_emb_sheaf", panels.economy)
	tile(grid, "Армия", "kit_emb_sword", panels.army)
	tile(grid, "Найти существо", "kit_emb_march", ui.show_city_hunt)
	tile(grid, "Цели поселения", "kit_emb_award", panels.objectives)
	var s: Dictionary = ui.state.v6
	var figures := KitMore.ChipRow.new()
	figures.chips = [[UiKit.tex("kit_emb_craft"), "Строители: %d" % int(ui.state.get("workers", 0))],
		[UiKit.tex("kit_ic_places"), "Работники: %d / %d" % [int(s.workforce.used), int(s.workforce.capacity)]]]
	ui.modal_body.add_child(figures)

# ------------------------------------------------------------------ account

func account() -> void:
	var started := Time.get_ticks_usec()
	var primary := primary_server()
	ui.open_modal("Аккаунт", "full", "DRENOVAR · ОБЩИЙ ГОРОД" if primary else "DRENOVAR · ТЕСТОВАЯ ВЕРСИЯ")
	ui.message.text = ""
	var joined: bool = panels.enabled() and ui.connected()
	oak_column(settlement_card() if joined else game_card())
	if not ui.login_proof.is_empty():
		login_code(primary)
		version_line()
		return
	if ui.client_update_required:
		UiKit.section_header(ui.modal_body, "Обновление")
		note("Сервер запросил обновление приложения. Здесь указан номер установленной сборки.")
		styled(ui.button(ui.modal_body, "Открыть сборки DRENOVAR", func(): OS.shell_open("https://github.com/ali7prg/Drenovar/releases")), "secondary")
	if primary and not panels.enabled():
		UiKit.section_header(ui.modal_body, "Вход")
		styled(ui.button(ui.modal_body, "Войти через ChatGPT", ui.begin_main_login), "primary", 20, 54)
	if not joined:
		UiKit.section_header(ui.modal_body, "О городе" if primary else "Тестовый мир")
	note("Войдите через ChatGPT, чтобы открыть свой существующий город. Здания, ресурсы и армия останутся на общем сервере. Подключение по коду — дополнительный способ входа." if primary else "Это отдельный тестовый мир V6. Поселения действующей игры здесь пока недоступны; их прогресс сохранён в действующей версии.")
	styled(ui.button(ui.modal_body, "Открыть основной город в браузере" if primary else "Открыть действующую веб-версию", func(): OS.shell_open(ui.OLD_SERVER_URL)), "tertiary", 18, 46)
	if ui.restoring_session:
		note("Восстанавливаем подключение к вашему городу…", UiKit.BRONZE)
		styled(ui.button(ui.modal_body, "Повторить подключение", ui.restore_account), "secondary")
		version_line()
		return
	if not ui.connected():
		styled(ui.button(ui.modal_body, "Подключить устройство" if primary else "Подключиться к тестовому миру", func():
			await ui.device_login()
			panels.account()
		), "primary", 20, 54)
		version_line()
		return
	if ui.saved_session_error:
		note("Не удалось сохранить вход на устройстве. Не закрывайте приложение до подключения второго устройства.", UiKit.WARN)
	if panels.enabled():
		UiKit.section_header(ui.modal_body, "Поселение")
		var names := card("Имена и поселения", "Имя игрока, название поселения и другие поселения аккаунта.", "kit_emb_helm")
		names.name = "NamesCard"
		names.add_action("Изменить", "tertiary", Vector2(170, 50)).pressed.connect(profile)
		if not ui.state.v6.get("legacy_building_archive", []).is_empty():
			var kept := card("Архив прежних зданий", "Здания прежней версии и компенсация за них.", "kit_emb_chest")
			var open_archive: Button = kept.add_action("Архив прежних зданий", "tertiary", Vector2(250, 50))
			open_archive.pressed.connect(panels.archive)
		UiKit.section_header(ui.modal_body, "Другое устройство")
		var pair := card("Код подключения", "Чтобы открыть этот же город на другом устройстве, получите код и введите его там. Код действует 10 минут.", "kit_emb_key", 104.0)
		pair.name = "PairCard"
		pair.add_action("Получить код подключения", "secondary", Vector2(300, 52)).pressed.connect(panels.pairing_code)
	else:
		note("Введите код из своего города в веб-версии. Новое поселение для этого создавать не нужно." if primary else "Введите код из аккаунта веб-версии V6 или создайте отдельное тестовое поселение.")
		if not primary:
			styled(ui.button(ui.modal_body, "Создать тестовое поселение", ui.create_settlement), "primary", 20, 54)
	UiKit.section_header(ui.modal_body, "Подключить по коду")
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 12)
	ui.modal_body.add_child(line)
	var input := LineEdit.new()
	input.name = "PairInput"
	input.placeholder_text = "16 знаков из веб-версии V6"
	input.max_length = 20
	input.custom_minimum_size = Vector2(300, 52)
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_child(input)
	var join: Button = ui.button(line, "Открыть мой город" if primary else "Подключить тестовое поселение", func():
		var response: Dictionary = await ui.send_request("pair/accept", {"code":input.text})
		if response.has("error"):
			ui.show_error(response)
		else:
			ui.player_id = ""
			await ui.sync_account()
			panels.account()
	)
	styled(join, "secondary", 18, 52)
	var out: Button = ui.button(ui.modal_body, "Выйти из аккаунта на устройстве", ui.confirm_profile_action.bind(ui.sign_out_question(), ui.sign_out))
	styled(out, "tertiary", 17, 46)
	out.icon = UiKit.tex("kit_emb_exit")
	out.expand_icon = true
	out.add_theme_constant_override("icon_max_width", 26)
	version_line()
	last_open_usec = Time.get_ticks_usec() - started

func version_line() -> void:
	var line: Label = UiKit.label(ui.modal_body, "Версия %s · сборка %s" % [ProjectSettings.get_setting("application/config/version"), ProjectSettings.get_setting("application/config/build_number", "")], 14, UiKit.INK_MUTED)
	line.name = "VersionLine"
	line.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT

## Sign-in in Safari with a confirmation code (shown large; never logged).
func login_code(primary: bool) -> void:
	var challenge: String = ui.login_proof.sha256_text()
	var code: String = challenge.left(8).to_upper()
	UiKit.section_header(ui.modal_body, "Вход через ChatGPT" if primary else "Подтверждение входа")
	var caption: Label = UiKit.label(ui.modal_body, "Код подтверждения", 17, UiKit.BRONZE, UiKit.LABEL_FONT, false)
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var plate := KitMore.CodePlate.new()
	plate.name = "LoginCode"
	plate.code = code
	plate.accessibility_name = "Код подтверждения: " + code
	ui.modal_body.add_child(plate)
	if ui.pending_login_save_error:
		note("Не удалось сохранить незавершённый вход. Если приложение перезапустится, начните вход заново.", UiKit.WARN)
	note("В Safari войдите в тот же аккаунт ChatGPT, которому принадлежит ваш город. Введите этот код и нажмите «Разрешить вход». Затем вернитесь в DRENOVAR — откроется существующий город.")
	styled(ui.button(ui.modal_body, "Открыть вход через ChatGPT", ui.open_login_page.bind(challenge)), "primary", 20, 54)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	ui.modal_body.add_child(row)
	for entry: Array in [["Скопировать код", func(): DisplayServer.clipboard_set(code); ui.message.text = "Код скопирован", "secondary"],
			["Проверить вход", ui.finish_login.bind(true), "tertiary"]]:
		var control: Button = styled(ui.button(row, entry[0], entry[1]), entry[2])
		control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var again := HBoxContainer.new()
	again.add_theme_constant_override("separation", 12)
	ui.modal_body.add_child(again)
	for entry: Array in [["Начать вход заново", ui.restart_login], ["Отмена входа", ui.cancel_transfer]]:
		var control: Button = styled(ui.button(again, entry[0], entry[1]), "tertiary", 17, 46)
		control.size_flags_horizontal = Control.SIZE_EXPAND_FILL

## «Код подключения»: the code in groups of four on oak, how long it is valid, copy.
func pairing(response: Dictionary) -> void:
	var code := str(response.get("code", ""))
	ui.open_modal("Код подключения", "dialog")
	var plate := KitMore.CodePlate.new()
	plate.name = "PairingCode"
	plate.code = code
	plate.accessibility_name = "Код подключения: " + code
	ui.modal_body.add_child(plate)
	var ends := float(response.get("expiresAt", 0.0))
	if ends <= 0.0:
		ends = float(ui.timer_now()) + 600000.0
	var left := Label.new()
	left.name = "PairingTime"
	left.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	left.add_theme_font_override("font", UiKit.LABEL_FONT)
	left.add_theme_font_size_override("font_size", 17)
	left.add_theme_color_override("font_color", UiKit.BRONZE)
	ui.modal_body.add_child(left)
	ui.bind_countdown(left, "Действует ещё", ends)
	var tip: Label = UiKit.label(ui.modal_body, "В веб-версии откройте «Аккаунт» и введите код. Показывайте код только своему устройству.", 16, UiKit.INK_MUTED)
	tip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ui.modal_footer.show()
	var back: Button = styled(ui.button(ui.modal_footer, "Готово", panels.account), "tertiary", 18, 50)
	back.custom_minimum_size.x = 180
	var copy: Button = styled(ui.button(ui.modal_footer, "Скопировать код", func():
		DisplayServer.clipboard_set(code)
		ui.message.text = "Код скопирован"), "secondary", 18, 50)
	copy.name = "CopyCode"
	copy.custom_minimum_size.x = 240
	copy.icon = UiKit.tex("kit_emb_copy")
	copy.expand_icon = true
	copy.add_theme_constant_override("icon_max_width", 26)

## A question before an action: a medallion, the question, «Отмена» and the action.
## «Отмена» returns to the account (as the window it replaces did).
func confirm(question: String, action: Callable, confirm_text := "Подтвердить", danger := true, emblem := "kit_emb_exit") -> void:
	ui.open_modal("Подтверждение", "dialog")
	var medal := MedalHead.new()
	medal.emblem = UiKit.tex(emblem)
	ui.modal_body.add_child(medal)
	var text: Label = UiKit.label(ui.modal_body, question, 19, UiKit.INK)
	text.name = "Question"
	text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ui.modal_footer.show()
	var cancel: Button = styled(ui.button(ui.modal_footer, "Отмена", ui.show_account), "tertiary", 18, 52)
	cancel.custom_minimum_size.x = 190
	var go: Button = styled(ui.button(ui.modal_footer, confirm_text, action), "danger" if danger else "primary", 19, 52)
	go.name = "ConfirmAction"
	go.custom_minimum_size.x = 230

## «Имена и поселения»: the player's and the settlement's names (editNames) and the
## settlements of the account (switch with a confirmation).
func profile() -> void:
	ui.open_modal("Имена и поселения", "full", "ПРОФИЛЬ")
	oak_column(settlement_card())
	var wait: Label = note("Загружаем поселения…", UiKit.BRONZE)
	var generation: int = ui.modal_generation
	var answer: Dictionary = await ui.request("account")
	if generation != ui.modal_generation:
		return
	wait.queue_free()
	if not answer.has("profiles"):
		ui.show_error(answer)
		styled(ui.button(ui.modal_body, "Повторить", profile), "secondary")
		return
	if answer.get("playerId") != null:
		UiKit.section_header(ui.modal_body, "Имена")
		ui.add_name_fields(answer, profile)
	UiKit.section_header(ui.modal_body, "Поселения аккаунта")
	for item: Dictionary in answer.profiles:
		var row := KitMore.Card.new()
		row.title = str(item.get("name", "Поселение"))
		row.subtitle = "%s воинов" % ui.format_balance(int(item.get("troops", 0)))
		row.icon = UiKit.tex("kit_emb_town")
		row.icon_mode = "disc"
		row.custom_minimum_size.y = 84
		ui.modal_body.add_child(row)
		if item.get("active", false):
			row.ribbon = "Текущее"
			row.plate = "gold"
		else:
			var id := str(item.id)
			row.add_action("Открыть", "secondary", Vector2(170, 48)).pressed.connect(ui.confirm_profile_action.bind("Открыть «%s»?" % item.name, ui.select_profile.bind(id)))
	if answer.profiles.is_empty():
		styled(ui.button(ui.modal_body, "Основать поселение", ui.create_settlement), "primary", 20, 54)

## The medallion at the head of a confirmation.
class MedalHead extends Control:
	var emblem: Texture2D

	func _init() -> void:
		custom_minimum_size.y = 84
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		KitMore.Paint.draw_medal(self, Vector2(size.x * 0.5, 42.0), 76.0, emblem, true)
