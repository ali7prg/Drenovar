extends RefCounted
## Army and march windows of the V6 settlement (premium UI stage 4a, ui_premium/STAGE4A.md).
##
## «Армия и осада»: on dark oak at the left, the army's capacity bar, the march limits, the
## beds and the wounded with a way to the infirmary; at the right, the troops at home as
## tier cards with their portraits and counts (a card opens its training building), the
## rams, the parties on the march with their timers and recall, and the targets.
## «Поход»: the target on the left with the march capacity filling as troops are chosen;
## each unit at home as a row with its portrait, a slider and a field; «Все доступные»,
## «Очистить» and «Рассчитать поход» (the server's preview), then «Отправить отряд».

const UiKit = preload("res://src/ui_kit.gd")
const UnitStage = preload("res://src/unit_stage.gd")
const Queues = preload("res://src/v6_queues.gd")
const Services = preload("res://src/v6_services.gd")
const KitMore = preload("res://src/kit_more.gd")

var panels
var ui
var last_open_usec := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

func v6() -> Dictionary:
	return ui.state.v6

func tier_of(unit: Dictionary) -> int:
	return clampi(int(unit.get("required_building", 1)), 1, 5)

func rams_home() -> int:
	return v6().get("machines", []).filter(func(m): return m.get("location", "") == "home").size()

## The left column of both windows: dark oak with a summary drawn in one node and the
## buttons under it.
func oak_column(summary: Control, buttons: Array) -> VBoxContainer:
	var hero: Control = ui.modal_hero
	var backdrop := Panel.new()
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.add_theme_stylebox_override("panel", Queues.rail_back_style())
	hero.add_child(backdrop)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	hero.add_child(column)
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	column.offset_left = 26
	column.offset_right = -18
	column.offset_top = 30
	column.offset_bottom = -18
	summary.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(summary)
	for entry: Array in buttons:
		var control: Button = ui.button(column, entry[0], entry[1])
		UiKit.style_button(control, entry[2], 18)
		control.custom_minimum_size = Vector2(0, 50)
		if entry.size() > 3:
			control.name = entry[3]
	ui.modal_hero_share = 0.34
	ui.arrange_modal()
	return column

# ------------------------------------------------------------------ army

func army() -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal("Армия и осада", "full", "ВОЙСКО ПОСЕЛЕНИЯ")
	panels.warnings()
	var wounded := 0
	for id: String in v6().get("wounded", {}):
		wounded += int(v6().wounded[id])
	var summary := OakSummary.new()
	summary.emblem = UiKit.tex("kit_emb_sword")
	summary.title = "Войско поселения"
	summary.bar_caption = "Армия"
	summary.used = int(v6().get("army_used", 0))
	summary.capacity = int(v6().get("army_capacity", 0))
	summary.lines = [["Поход", "до %s мест" % ui.format_balance(int(v6().get("march_capacity", 0)))],
		["Отрядов одновременно", str(int(v6().get("march_parallel", 0)))],
		["Коек в лазарете", ui.format_balance(int(v6().get("hospital_capacity", 0)))],
		["Раненых", ui.format_balance(wounded)]]
	summary.note = "Таран занимает 5 мест. Раненые сверх коек погибают."
	oak_column(summary, [["Лазарет", panels.services.bind("B16"), "secondary", "ArmyHospital"], ["Показать плац в городе", ui.open_parade, "tertiary"]])
	summary_band(wounded)
	units_section()
	marches_section()
	var targets: Array = ui.state.get("world", {}).get("cities", []).filter(func(c): return c.id != ui.state.playerId and c.get("pvp", false))
	if not targets.is_empty():
		UiKit.section_header(ui.modal_body, "Цели похода")
		for target: Dictionary in targets:
			var row := Queues.SpeedRow.new()
			row.name = "Target_" + str(target.id)
			row.custom_minimum_size.y = 86
			row.icon = UiKit.tex("kit_emb_march")
			row.round_icon = true
			row.title = str(target.name)
			row.text = "Поселение другого правителя · %s" % ("стена %s" % str(target.get("wallLevel")) if target.has("wallLevel") else "осада и добыча")
			ui.modal_body.add_child(row)
			row.add_action("Поход", "primary", Vector2(190, 52)).pressed.connect(panels.formation.bind(str(target.id), str(target.name)))
	last_open_usec = Time.get_ticks_usec() - started

## Premium UI stage 4b: the army at a glance (troops at home, their might, the wounded, the
## troops away) and the way to a march (choose a target, then the party).
func summary_band(wounded: int) -> void:
	var home := 0
	var might := 0
	var power := {}
	for unit: Dictionary in panels.catalogue.get("units", []):
		power[str(unit.unit_id)] = int(unit.get("power_reference", 0))
	var healthy: Dictionary = v6().get("healthy", {})
	for id: String in healthy:
		home += int(healthy[id])
		might += int(healthy[id]) * int(power.get(id, 0))
	var away := 0
	for march: Dictionary in ui.state.get("armies", []) + ui.state.get("world", {}).get("armies", []):
		if march.get("owner", ui.state.playerId) == ui.state.playerId and march.status != "returned":
			for id: String in march.get("units", {}):
				away += int(march.units[id])
	var band := KitMore.StatBand.new()
	band.name = "ArmyBand"
	band.cells = [[UiKit.tex("kit_emb_inf"), ui.format_balance(home), "Воинов дома"],
		[UiKit.tex("kit_emb_sword"), UiKit.compact(might), "Мощь войска"],
		[UiKit.tex("kit_emb_heal"), ui.format_balance(wounded), "Раненых"],
		[UiKit.tex("kit_emb_march"), ui.format_balance(away), "В походе"]]
	ui.modal_body.add_child(band)
	var go := HBoxContainer.new()
	go.name = "ArmyMarch"
	go.add_theme_constant_override("separation", 12)
	ui.modal_body.add_child(go)
	var compose: Button = ui.panel_action(go, "Собрать отряд", ui.show_city_hunt, home > 0)
	compose.name = "ComposeEntry"
	compose.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	compose.icon = UiKit.tex("kit_emb_sword")
	compose.expand_icon = true
	compose.add_theme_constant_override("icon_max_width", 30)
	var note: Label = UiKit.label(go, "Выберите цель охоты или поселение — состав отряда собирается там.", 15, UiKit.INK_MUTED)
	note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	note.size_flags_vertical = Control.SIZE_SHRINK_CENTER

func units_section() -> void:
	var home: Dictionary = v6().get("healthy", {})
	var shown: Array = []
	for unit: Dictionary in panels.catalogue.get("units", []):
		var count := rams_home() if unit.unit_id == "SIEGE-RAM-01" else int(home.get(unit.unit_id, 0))
		if count > 0:
			shown.append([unit, count])
	UiKit.section_header(ui.modal_body, "Войска в городе")
	if shown.is_empty():
		UiKit.label(ui.modal_body, "В городе нет воинов. Обучите их в казармах, на стрельбище и в конюшне.", 16, UiKit.INK_MUTED)
		return
	var flow := HFlowContainer.new()
	flow.name = "ArmyUnits"
	flow.add_theme_constant_override("h_separation", 12)
	flow.add_theme_constant_override("v_separation", 12)
	ui.modal_body.add_child(flow)
	for entry: Array in shown:
		var unit: Dictionary = entry[0]
		var card: BaseButton = UiKit.tier_card(tier_of(unit), str(unit.name_ru), ui.format_balance(int(entry[1])), UnitStage.portrait(str(unit.unit_id), true))
		card.name = "Unit_" + str(unit.unit_id)
		# Larger cards than the recruitment roster (stage 4b): the army is the subject here.
		card.custom_minimum_size = Vector2(138, 192)
		card.tooltip_text = "%s · %s" % [unit.name_ru, ui.format_balance(int(entry[1]))]
		var building_type := str(unit.get("building_id", ""))
		var unit_id := str(unit.unit_id)
		card.pressed.connect(func():
			panels.recruit.chosen[building_type] = unit_id
			panels.services(building_type))
		# The card and the unit's name under it (Viking-style rosters name every card).
		var cell := VBoxContainer.new()
		cell.add_theme_constant_override("separation", 2)
		cell.add_child(card)
		var caption := UiKit.label(cell, str(unit.name_ru), 15, UiKit.INK, UiKit.LABEL_FONT, false)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.custom_minimum_size.x = card.custom_minimum_size.x
		caption.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		caption.clip_text = true
		flow.add_child(cell)
	var damaged: Array = v6().get("machines", []).filter(func(m): return m.get("location", "") == "home" and int(m.hp) < int(m.max_hp))
	if not damaged.is_empty():
		UiKit.label(ui.modal_body, "Повреждённых таранов: %d — ремонт в осадной мастерской." % damaged.size(), 16, UiKit.WARN)

func marches_section() -> void:
	var first := true
	for march: Dictionary in ui.state.get("armies", []) + ui.state.get("world", {}).get("armies", []):
		if march.get("owner", ui.state.playerId) != ui.state.playerId or march.status == "returned":
			continue
		if first:
			first = false
			UiKit.section_header(ui.modal_body, "Отряды в походе")
		var status: String = {"outbound": "В пути к цели", "fighting": "В бою", "returning": "Возвращается"}.get(str(march.status), str(march.status))
		var row := Queues.SpeedRow.new()
		row.name = "March_" + str(march.id)
		row.custom_minimum_size.y = 92
		row.icon = UiKit.tex("kit_emb_march")
		row.round_icon = true
		row.title = str(march.get("name", "Отряд"))
		var finish: Variant = ui.march_finish(march)
		row.text = status + (" · %s" % Queues.Clock.text(float(finish) - ui.timer_now()) if finish != null else "")
		if march.has("cargo") and not march.cargo.get("issued", false):
			var parts: Array[String] = []
			for resource: String in march.cargo.get("resources", {}):
				if int(march.cargo.resources[resource]) > 0:
					parts.append("%s %s" % [ui.RESOURCE_NAMES.get(resource, resource), UiKit.compact(int(march.cargo.resources[resource]))])
			row.count_text = "Груз: " + ", ".join(parts) if not parts.is_empty() else ""
		ui.modal_body.add_child(row)
		if march.status in ["outbound", "fighting"]:
			var action := {"kind": "recall" if march.status == "outbound" else "retreat", "armyId": march.id}
			row.add_action("Отозвать" if march.status == "outbound" else "Отступить", "danger", Vector2(170, 48)).pressed.connect(func():
				await ui.command(action)
				panels.army())
		else:
			row.add_action("Показать", "secondary", Vector2(170, 48)).pressed.connect(ui.focus_army.bind(march))

# ------------------------------------------------------------------ formation

func formation(target: String, name: String) -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal("Поход: " + name, "full", "СОСТАВ ОТРЯДА")
	var capacity := int(v6().get("march_capacity", 0))
	var summary := OakSummary.new()
	summary.emblem = UiKit.tex("kit_emb_march")
	summary.title = name
	summary.bar_caption = "Мест в походе"
	summary.capacity = capacity
	summary.lines = [["Отрядов одновременно", str(int(v6().get("march_parallel", 0)))], ["Войск выбрано", "0"]]
	summary.note = "Потери зависят от гарнизона цели и сопровождения."
	oak_column(summary, [])
	var inputs: Dictionary = {}
	var slots: Dictionary = {}
	var update := func():
		var used := 0
		var count := 0
		for id: String in inputs:
			used += int(inputs[id].value) * int(slots[id])
			count += int(inputs[id].value)
		summary.used = used
		summary.lines[1] = ["Войск выбрано", ui.format_balance(count)]
		summary.queue_redraw()
	ui.modal_tools.show()
	var heading := UiKit.label(ui.modal_tools, "Войска в городе", 20, UiKit.INK, UiKit.LABEL_FONT)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var all_button: Button = ui.button(ui.modal_tools, "Все доступные", Callable())
	UiKit.style_button(all_button, "tertiary", 17)
	all_button.custom_minimum_size = Vector2(190, 46)
	var clear_button: Button = ui.button(ui.modal_tools, "Очистить", Callable())
	UiKit.style_button(clear_button, "tertiary", 17)
	clear_button.custom_minimum_size = Vector2(150, 46)
	for unit: Dictionary in panels.catalogue.get("units", []):
		var available: int = rams_home() if unit.unit_id == "SIEGE-RAM-01" else int(v6().get("healthy", {}).get(unit.unit_id, 0))
		if available <= 0:
			continue
		var id := str(unit.unit_id)
		var per := maxi(1, int(unit.get("army_slots", 1)))
		var row := PanelContainer.new()
		row.name = "Pick_" + id
		row.add_theme_stylebox_override("panel", UiKit.row_style())
		ui.modal_body.add_child(row)
		var middle := VBoxContainer.new()
		middle.add_theme_constant_override("separation", 0)
		row.add_child(middle)
		# Portrait on its tier's tile, name and what is at home in one drawn node.
		var head := Services.UnitHead.new()
		head.face = UnitStage.portrait(id, true)
		head.tier = tier_of(unit)
		head.title = str(unit.name_ru)
		head.line = "Доступно %s · мест на воина %d" % [ui.format_balance(available), per]
		head.accessibility_name = "%s · %s" % [head.title, head.line]
		middle.add_child(head)
		var pick: Array = UiKit.quantity(middle, 0, mini(available, capacity / per), 0)
		inputs[id] = pick[1]
		slots[id] = per
		var field: SpinBox = pick[1]
		field.value_changed.connect(func(value: float):
			# The march holds at most its capacity: a slider past the free places stops there.
			var others := 0
			for other: String in inputs:
				if other != id:
					others += int(inputs[other].value) * int(slots[other])
			var most := maxi(0, (capacity - others) / per)
			if int(value) > most:
				field.set_value_no_signal(most)
				field.get_line_edit().text = str(most)
				(pick[0] as HSlider).set_value_no_signal(most)
			update.call())
	if inputs.is_empty():
		UiKit.label(ui.modal_body, "В городе нет воинов для похода.", 17, UiKit.INK_MUTED)
	all_button.pressed.connect(func():
		var left := capacity
		for id: String in inputs:
			var field: SpinBox = inputs[id]
			field.set_value_no_signal(0)
		for id: String in inputs:
			var field: SpinBox = inputs[id]
			var take := mini(int(field.max_value), left / int(slots[id]))
			field.value = take
			left -= take * int(slots[id])
		update.call())
	clear_button.pressed.connect(func():
		for id: String in inputs:
			inputs[id].value = 0
		update.call())
	ui.modal_footer.show()
	var preview: Button = panels.work_button(ui.modal_footer, "Рассчитать поход", func():
		var units: Dictionary = {}
		for id: String in inputs:
			if int(inputs[id].value) > 0:
				units[id] = int(inputs[id].value)
		if units.is_empty():
			ui.show_error({"error": "Выберите войска для похода."})
			return
		var body := {"kind": "worldMarch", "worldKind": "pvp", "encounterId": target, "units": units}
		var result: Dictionary = await ui.request("march-preview", body)
		if result.has("error"):
			ui.show_error(result)
			return
		confirm_march(body, result, name), true)
	preview.name = "FormationPreview"
	update.call()
	last_open_usec = Time.get_ticks_usec() - started

func confirm_march(body: Dictionary, result: Dictionary, name: String) -> void:
	ui.open_modal("Отправить отряд", "center", "ПОХОД · " + name.to_upper())
	UiKit.stat_row(ui.modal_body, "Дорога", Queues.span(ceili(float(result.get("travelMs", 0)) / 1000.0)))
	UiKit.stat_row(ui.modal_body, "Мест в отряде", ui.format_balance(int(result.get("total", 0))))
	var row := HFlowContainer.new()
	row.add_theme_constant_override("h_separation", 8)
	ui.modal_body.add_child(row)
	for id: String in body.units:
		row.add_child(UiKit.icon_tile(UnitStage.portrait(id, true), 60, "×" + UiKit.compact(int(body.units[id]))))
	UiKit.label(ui.modal_body, "Потери зависят от гарнизона цели и сопровождения.", 15, UiKit.INK_MUTED)
	ui.modal_footer.show()
	var send: Button = panels.work_button(ui.modal_footer, "Отправить", func():
		await ui.command(body)
		panels.army(), true)
	send.name = "FormationSend"

## The oak column's summary in one drawn node: a gold medallion with the emblem, the title,
## a capacity bar with its numbers, label–value lines and a note.
class OakSummary extends Control:
	var emblem: Texture2D
	var title := ""
	var bar_caption := ""
	var used := 0
	var capacity := 0
	var lines: Array = []
	var note := ""

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var d := 96.0
		var centre := Vector2(size.x * 0.5, d * 0.5 + 2.0)
		draw_circle(centre + Vector2(0, 3), d * 0.5 + 2.0, Color(0, 0, 0, 0.35), true, -1.0, true)
		draw_texture_rect(UiKit.tex("kit_rail_on"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false)
		if emblem != null:
			var side := d * 0.58
			draw_texture_rect(emblem, Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false)
		var y := d + 14.0
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, 22, size.x)
		head.draw_outline(get_canvas_item(), Vector2(roundf((size.x - head.get_size().x) * 0.5), y), 4, Color(0, 0, 0, 0.5))
		head.draw(get_canvas_item(), Vector2(roundf((size.x - head.get_size().x) * 0.5), y), UiKit.GOLD)
		y += head.get_size().y + 14.0
		if capacity > 0:
			var caption := UiKit.KitText.line(bar_caption, UiKit.LABEL_FONT, 16)
			caption.draw(get_canvas_item(), Vector2(0, y), Color("#e4d3b0"))
			var numbers := UiKit.KitText.line("%s / %s" % [UiKit.compact(used), UiKit.compact(capacity)], UiKit.LABEL_FONT, 16)
			numbers.draw(get_canvas_item(), Vector2(size.x - numbers.get_size().x, y), UiKit.GOLD if used <= capacity else UiKit.BAD)
			y += caption.get_size().y + 4.0
			var bar := Rect2(0, y, size.x, 20.0)
			draw_style_box(UiKit.nine("kit_track", Vector4(11, 10, 11, 10), Vector4.ZERO), bar)
			var ratio := clampf(float(used) / float(capacity), 0.0, 1.0)
			if ratio > 0.0:
				draw_style_box(UiKit.nine("kit_fill", Vector4(11, 10, 11, 10), Vector4.ZERO), Rect2(bar.position, Vector2(maxf(22.0, bar.size.x * ratio), bar.size.y)))
			y += 34.0
		for pair: Array in lines:
			var name_line := UiKit.KitText.line(str(pair[0]), UiKit.BODY_FONT, 16, size.x * 0.6)
			var value_line := UiKit.KitText.line(str(pair[1]), UiKit.LABEL_FONT, 17)
			name_line.draw(get_canvas_item(), Vector2(0, y), Color("#e4d3b0"))
			value_line.draw(get_canvas_item(), Vector2(size.x - value_line.get_size().x, y), UiKit.IVORY)
			y += maxf(name_line.get_size().y, value_line.get_size().y) + 3.0
			draw_rect(Rect2(0, y, size.x, 1.0), Color("#c9a05a40"))
			y += 7.0
		if not note.is_empty() and y + 22.0 < size.y:
			var tip := UiKit.KitText.line(note, UiKit.BODY_FONT, 14, size.x)
			tip.draw(get_canvas_item(), Vector2(0, y + 2.0), Color("#c8b48f"))
