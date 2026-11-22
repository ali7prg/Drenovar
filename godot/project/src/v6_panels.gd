extends RefCounted

const VERSION := "DRENOVAR-V6-C1.0"
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
var ui: Node
var catalogue: Dictionary = {}
var catalogue_loading := false
var quote_request := 0
var navigation_request := 0
var submitting := false

func begin_view() -> int:
	navigation_request += 1
	return navigation_request
signal catalogue_loaded(success: bool)

func _init(owner_node: Node) -> void:
	ui = owner_node

func enabled() -> bool:
	return ui.state.get("economy_version", "") == VERSION and ui.state.get("v6") is Dictionary

func load_catalogue() -> bool:
	if not await ui.ensure_v6_ready():
		return false
	if catalogue.get("economy_version", "") == VERSION:
		return true
	if catalogue_loading:
		return await catalogue_loaded
	catalogue_loading = true
	var response: Dictionary = await ui.request("command", {"kind":"v6catalog"})
	var success: bool = not response.has("error") and response.get("economy_version", "") == VERSION and response.get("buildings", []).size() == 297
	if success:
		catalogue = response
	elif response.has("error"):
		ui.show_error(response)
	else:
		ui.show_error({"error":"Получен каталог другой версии. Повторите подключение к общему серверу.", "code":"CATALOGUE_VERSION_MISMATCH"})
	catalogue_loading = false
	catalogue_loaded.emit(success and enabled())
	return success and enabled()

func instance(id: String) -> Dictionary:
	if not enabled():
		return {}
	for b: Dictionary in ui.state.v6.buildings:
		if b.id == id:
			return b
	return {}

func inspect_instance(id: String) -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	var b := instance(id)
	if b.is_empty():
		ui.show_error({"error":"Здание изменилось. Обновите город и выберите его снова."})
		return
	await inspect(str(b.type))

func open_ring(marker: Dictionary) -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	var instance_id := str(marker.item.get("id", ""))
	if instance_id.is_empty() and marker.item.get("wall", false):
		await inspect("B18")
		return
	var b := instance(instance_id)
	if b.is_empty():
		ui.show_error({"error":"Здание изменилось. Выберите его снова после обновления города."})
		return
	var type: String = b.type
	var actions: Array = [["Улучшить" if int(b.level) < 11 else "Сведения", "upgrade" if int(b.level) < 11 else "info", inspect_instance.bind(str(b.id))]]
	for order: Dictionary in ui.state.v6.orders:
		if order.status == "pending" and order.get("instance_id", "") == b.id:
			actions.append(["Очереди", "speed", queues])
			break
	if type in ["B11", "B12", "B13", "B15", "B16", "B17"]:
		actions.append(["Работы здания", "heal" if type == "B16" else "train", services.bind(type)])
	if type == "B05":
		actions.append(["Рынок", "trade", trade])
	if type in ["B18", "B19"]:
		actions.append(["Оборона", "defence", inspect_instance.bind(str(b.id))])
	if type in ["B06", "B07", "B08", "B09", "B10", "B22", "B24"]:
		actions.append(["Производство", "collect", economy])
	actions.append(["Переместить", "move", move_building.bind(b, str(row_for(type,int(b.level)).environment))])
	ui.action_ring.open(str(b.id), "%s · %s" % [row_for(type,1).name_ru, ROMAN[int(b.level)-1]], marker.position, ui.stage.camera, actions)

func building(type: String) -> Dictionary:
	for b: Dictionary in ui.state.v6.buildings:
		if b.type == type:
			return b
	return {}

func row_for(type: String, level: int) -> Dictionary:
	for row: Dictionary in catalogue.get("buildings", []):
		if row.building_id == type and int(row.level) == level:
			return row
	return {}

func warnings() -> void:
	for warning: Dictionary in ui.state.v6.get("warnings", []):
		var alarm: Label = ui.UiKit.label(ui.modal_body, "Башня обнаружила нападение · до прибытия %d с" % int(warning.eta_seconds), 18, ui.UiKit.BAD, ui.UiKit.LABEL_FONT)
		alarm.name = "AttackWarning"

func stock_line(alarms := true) -> void:
	if alarms:
		warnings()
	var s: Dictionary = ui.state.v6
	for r: String in ["wood", "food", "stone", "iron", "coins"]:
		var amount := "%s / %s" % [ui.format_balance(int(s.stock[r])), ui.format_balance(int(s.capacities[r]))]
		if int(s.escrow[r]) > 0:
			amount += " · резерв %s" % ui.format_balance(int(s.escrow[r]))
		var stopped: bool = s.production_stopped[r]
		var rate := "производство приостановлено" if stopped else "+%s/ч" % per_hour(float(s.production_per_hour[r]))
		ui.UiKit.resource_row(ui.modal_body, ui.resource_icons.get(r), str(ui.RESOURCE_NAMES[r]), amount, rate, stopped)
	ui.UiKit.stat_row(ui.modal_body, "Работники", "%d / %d" % [int(s.workforce.used), int(s.workforce.capacity)])
	ui.UiKit.stat_row(ui.modal_body, "Армия", "%d / %d" % [int(s.army_used), int(s.army_capacity)])

func per_hour(value: float) -> String:
	if is_equal_approx(value, roundf(value)):
		return ui.format_balance(int(roundf(value)))
	return String.num(value, 2)

# A row of secondary actions under a window's main content.
func links() -> HFlowContainer:
	var flow := HFlowContainer.new()
	flow.name = "Links"
	flow.add_theme_constant_override("h_separation", 12)
	flow.add_theme_constant_override("v_separation", 10)
	ui.modal_body.add_child(flow)
	return flow

func link(parent: Container, title: String, action: Callable) -> Button:
	var control: Button = ui.button(parent, title, action)
	control.custom_minimum_size = Vector2(220, 50)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return control

func economy() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal("Экономика поселения", "full", "ЗАПАСЫ И ДОХОД В ЧАС")
	section_title("Запасы и доход")
	stock_line()
	var more := links()
	link(more, "Очереди и отмена", queues)
	link(more, "Цели поселения", objectives)

func move_building(b: Dictionary, environment: String) -> void:
	begin_view()
	ui.open_modal("Переместить здание", "full", "ПОДХОДЯЩИЕ УЧАСТКИ", ui.v6_card(str(b.type)))
	for plot: String in ui.state.get("v6_plots", {}):
		if environment not in ui.state.v6_plots[plot]:
			continue
		var occupied := false
		for other: Dictionary in ui.state.v6.buildings:
			occupied = occupied or other.plot == plot
		if not occupied:
			ui.button(ui.modal_body, "Участок " + plot, send.bind({"kind":"move", "building_id":b.id, "plot":plot}))

func catalog() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal("Строительство", "full", "27 ТИПОВ · I–XI")
	muted("Пшеница и рыбалка занимают один общий пищевой участок.")
	var grid := GridContainer.new()
	grid.name = "Catalogue"
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 12)
	ui.modal_body.add_child(grid)
	for row: Dictionary in catalogue.buildings:
		if int(row.level) != 1:
			continue
		var b: Dictionary = building(row.building_id)
		var built := not b.is_empty()
		var art: Texture2D = ui.v6_card(str(row.building_id))
		if art == null:
			art = load("res://assets/ui/actions/build.svg")
		var tile: Button = ui.UiKit.tile_button(str(row.name_ru), "Уровень " + ROMAN[int(b.level)-1] if built else "Построить",
			art, ui.UiKit.INK_MUTED if built else ui.UiKit.GOOD)
		tile.pressed.connect(inspect.bind(str(row.building_id)))
		grid.add_child(tile)
	var more := links()
	link(more, "Все очереди", queues)
	link(more, "Армия и осада", army)
	link(more, "Подключить другое устройство", account)

func inspect(type: String) -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	if row_for(type,1).is_empty():
		ui.show_error({"error":"Неизвестный тип здания в текущем каталоге."})
		return
	var b: Dictionary = building(type)
	var level: int = int(b.get("level", 0))
	var row: Dictionary = row_for(type, maxi(1, level))
	ui.open_modal(str(row.name_ru), "full", "УРОВЕНЬ " + (ROMAN[level-1] if level > 0 else "НЕ ПОСТРОЕНО"), ui.v6_card(type))
	var upcoming: Dictionary = row_for(type, level + 1) if level < 11 else {}
	if level > 0:
		var step := HBoxContainer.new()
		step.alignment = BoxContainer.ALIGNMENT_CENTER
		step.add_theme_constant_override("separation", 18)
		ui.modal_body.add_child(step)
		# Display face: Philosopher's capital I reads like a lower-case l in numerals.
		ui.UiKit.label(step, "Уровень " + ROMAN[level-1], 25, ui.UiKit.INK, ui.UiKit.TITLE_FONT, false)
		if not upcoming.is_empty():
			ui.UiKit.mark(step, "arrow", ui.UiKit.GOOD, 24.0)
			ui.UiKit.label(step, ROMAN[level], 25, ui.UiKit.GOOD, ui.UiKit.TITLE_FONT, false)
		# Effects as a compact ruled list, so the cost, time and requirements stay on screen.
		var stats := VBoxContainer.new()
		stats.name = "Effects"
		stats.add_theme_constant_override("separation", 0)
		ui.modal_body.add_child(stats)
		for metric: String in row.effects:
			var later: Variant = upcoming.get("effects", {}).get(metric)
			var gain := ""
			if later != null and str(later) != str(row.effects[metric]):
				gain = metric_value(metric, later)
			ui.UiKit.stat_row(stats, str(catalogue.get("metrics", {}).get(metric, {}).get("name_ru", metric)), metric_value(metric, row.effects[metric]), gain, true)
	if level < 11:
		var next: Dictionary = upcoming
		# The step above already reads «Уровень II ➜ III» in the display face.
		section_title("Следующий уровень" if level > 0 else "Строительство · " + ROMAN[level])
		# What it costs, then the time and the action on one row, then what it needs.
		cost_cards(next.cost)
		var action := {"kind":"construction", "building":type, "target":level+1}
		if level > 0:
			# The time pill and the call to action share a row, so the action is in view without
			# scrolling; it stays in the body, where qa_building_actions looks for it.
			var go := HBoxContainer.new()
			go.name = "KitTimeAction"
			go.add_theme_constant_override("separation", 14)
			ui.modal_body.add_child(go)
			ui.UiKit.timer_pill(go, "Базовое время", duration(int(next.duration_seconds)))
			var pill: Control = go.get_child(0)
			pill.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			pill.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			var check: Button = ui.panel_action(go, "Проверить улучшение", confirm.bind(action))
			check.custom_minimum_size.x = 300
		else:
			time_card("Базовое время", int(next.duration_seconds))
			ui.row(ui.modal_body, "Выберите участок подходящей местности: " + str(next.environment))
			for plot: String in ui.state.get("v6_plots", {}):
				if next.environment in ui.state.v6_plots[plot]:
					var placement: Dictionary = action.duplicate()
					placement.plot = plot
					ui.button(ui.modal_body, "Участок " + plot, confirm.bind(placement))
		# Requirements in two columns under the action (the server quote names any that are missing).
		var needs := HFlowContainer.new()
		needs.name = "KitRequirements"
		needs.add_theme_constant_override("h_separation", 16)
		needs.add_theme_constant_override("v_separation", 4)
		if not next.requirements.is_empty():
			ui.modal_body.add_child(needs)
		for d: Dictionary in next.requirements:
			var current: Dictionary = building(d.building_id)
			var ok: bool = int(current.get("level", 0)) >= int(d.level)
			var need := HBoxContainer.new()
			need.name = "KitRequirement"
			need.add_theme_constant_override("separation", 10)
			need.custom_minimum_size.x = 340
			needs.add_child(need)
			ui.UiKit.mark(need, "tick" if ok else "lozenge", ui.UiKit.GOOD if ok else ui.UiKit.BAD, 18.0)
			ui.UiKit.label(need, "%s · уровень %s или выше" % [row_for(d.building_id, 1).name_ru, ROMAN[int(d.level)-1]], 17, ui.UiKit.GOOD if ok else ui.UiKit.BAD).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	else:
		ui.row(ui.modal_body, "XI — окончательный уровень.")
	if type == "B18" and level > 0:
		ui.UiKit.stat_row(ui.modal_body, "Прочность стены", "%d / %d" % [int(ui.state.v6.wall_hp), int(ui.state.v6.wall_max_hp)])
		ui.UiKit.progress_bar(ui.modal_body, float(ui.state.v6.wall_hp) / maxf(1.0, float(ui.state.v6.wall_max_hp)), true)
	var more := links()
	if type in ["B11", "B12", "B13", "B17", "B15", "B16"] and level > 0:
		link(more, "Работы здания", services.bind(type))
	if type == "B06" and level > 0:
		link(more, "Посетить лагерь", func(): await ui.command({"kind":"v6collect"}); objectives())
	if type == "B18" and level > 0:
		link(more, "Ремонт стены", confirm.bind({"kind":"repair_wall"}))
	if type == "B05" and level > 0:
		link(more, "Рынок", trade)
	if type in ["B22", "B24"] and level > 0:
		link(more, "Сменить пищевую специализацию", send.bind({"kind":"switch_food", "variant":"B24" if type == "B22" else "B22"}))
	if level > 0:
		link(more, "Переместить здание", move_building.bind(b, str(row.environment)))
	link(more, "Очереди и отмена", queues)

func confirm(action: Dictionary) -> void:
	var navigation := begin_view()
	quote_request += 1
	var request_id := quote_request
	ui.open_modal("Подтвердить работу", "full", "УЛУЧШЕНИЕ ПОСЕЛЕНИЯ", ui.v6_card(str(action.get("building", ""))))
	var panel_generation: int = ui.modal_generation
	ui.row(ui.modal_body, "Рассчитываем стоимость и время…")
	var intent: Dictionary = action.duplicate(true)
	intent.economy_version = VERSION
	var response: Dictionary = await ui.request("command", {"kind":"v6quote", "intent":intent})
	if request_id != quote_request or panel_generation != ui.modal_generation or navigation != navigation_request:
		return
	ui.empty(ui.modal_body)
	if not response.get("ok", false):
		ui.row(ui.modal_body, str(response.get("reason", {}).get("message", response.get("error", "Нет ответа сервера"))))
		var reason: Dictionary = response.get("reason", {})
		if reason.has("resource") and reason.has("required") and reason.has("available"):
			ui.row(ui.modal_body, "%s: нужно %s, доступно %s" % [ui.RESOURCE_NAMES.get(reason.resource, reason.resource), str(reason.get("required", "")), str(reason.get("available", ""))])
		elif reason.has("building"):
			ui.row(ui.modal_body, "Требуется: " + str(row_for(str(reason.building),1).get("name_ru",reason.building)))
		if response.has("error"):
			ui.button(ui.modal_body, "Повторить расчёт", confirm.bind(action))
		return
	var q: Dictionary = response.quote
	section_title("Стоимость работы")
	cost_cards(q.cost)
	time_card("До завершения", int(q.duration_seconds))
	if int(q.speed_bp) > 0:
		muted("Бонус скорости +%.2f%%" % (float(q.speed_bp)/100.0))
	muted("Отмена вернёт резерв невыполненной части ремонта." if action.kind == "repair_wall" else "Ресурсы резервируются при начале работы. При отмене до завершения резерв возвращается.")
	intent.expected_duration_seconds = int(q.duration_seconds)
	ui.modal_footer.show()
	work_button(ui.modal_footer, "Начать", send.bind(intent), true)

func duration(seconds: int) -> String:
	seconds = maxi(0, seconds)
	if seconds >= 3600:
		var minutes := (seconds % 3600) / 60
		return "%d ч %d мин" % [seconds / 3600, minutes] if minutes else "%d ч" % (seconds / 3600)
	if seconds >= 60:
		return "%d мин%s" % [seconds / 60, " %d с" % (seconds % 60) if seconds % 60 else ""]
	return "%d с" % seconds

func section_title(text: String) -> void:
	ui.UiKit.section_header(ui.modal_body, text)

func muted(text: String) -> void:
	ui.UiKit.label(ui.modal_body, text, 16, ui.UiKit.INK_MUTED)

# Resource icons and amounts on a dark oak strip; an amount above the stock is red.
func cost_cards(cost: Dictionary) -> void:
	var stock: Dictionary = ui.state.v6.get("stock", {}) if enabled() else {}
	ui.UiKit.cost_strip(ui.modal_body, cost, ui.resource_icons, stock, ui.RESOURCE_NAMES)

func time_card(title: String, seconds: int, ends_at := 0.0) -> void:
	var clock: Label = ui.UiKit.timer_pill(ui.modal_body, title, duration(seconds))
	if ends_at > 0:
		ui.bind_countdown(clock, "", ends_at)

func work_button(parent: Container, title: String, action: Callable, primary := false) -> Button:
	var control: Button = ui.button(parent, title, Callable())
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	control.custom_minimum_size.y = 52
	if parent == ui.modal_footer:
		# Footer actions keep a plate shape instead of spanning the whole window.
		control.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		control.custom_minimum_size = Vector2(300, 56)
	if primary:
		ui.UiKit.style_button(control, "primary", 21)
	control.pressed.connect(func():
		if submitting or control.disabled:
			return
		submitting = true
		var previous: Array = []
		for root: Node in [ui.modal_body, ui.modal_footer]:
			for item: Node in root.find_children("*", "Button", true, false):
				previous.append([item, item.disabled])
				item.disabled = true
		control.text = "Выполняем…"
		await action.call()
		submitting = false
		for entry: Array in previous:
			if is_instance_valid(entry[0]):
				entry[0].disabled = entry[1]
		if is_instance_valid(control):
			control.text = title
	)
	return control

func send(action: Dictionary) -> void:
	var navigation := navigation_request
	var intent: Dictionary = action.duplicate(true)
	intent.economy_version = VERSION
	var success: bool = await ui.command({"kind":"v6", "intent":intent})
	if success and navigation == navigation_request:
		await queues()

func queues() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal("Очереди поселения", "full", "ЗАКАЗЫ И РЕЗЕРВ")
	warnings()
	section_title("Работы")
	var count := 0
	for order: Dictionary in ui.state.v6.orders:
		if order.status != "pending":
			continue
		count += 1
		var names := {"construction":"Строительство", "train":"Обучение", "heal":"Лечение", "research":"Исследование", "siege":"Сборка таранов", "repair_ram":"Ремонт тарана", "repair_wall":"Ремонт стены"}
		var card: PanelContainer = ui.panel(14)
		ui.modal_body.add_child(card)
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 8)
		card.add_child(box)
		var head := HBoxContainer.new()
		head.add_theme_constant_override("separation", 12)
		box.add_child(head)
		var art: Texture2D = ui.v6_card(str(order.building))
		if art != null:
			head.add_child(ui.UiKit.icon_tile(art, 64))
		var titles := VBoxContainer.new()
		titles.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		titles.alignment = BoxContainer.ALIGNMENT_CENTER
		head.add_child(titles)
		ui.UiKit.label(titles, str(row_for(str(order.building), 1).get("name_ru", order.building)), 20, ui.UiKit.INK, ui.UiKit.LABEL_FONT)
		ui.UiKit.label(titles, str(names.get(order.kind, order.kind)), 16, ui.UiKit.INK_MUTED)
		var starts := float(order.starts_at) * 1000.0
		var ends := float(order.ends_at) * 1000.0
		if starts > ui.timer_now():
			ui.bind_countdown(ui.UiKit.timer_pill(box, "Ожидание начала", ""), "", starts)
		ui.bind_countdown(ui.UiKit.timer_pill(box, "До завершения", ""), "", ends)
		if ends > starts:
			ui.UiKit.progress_bar(box, (ui.timer_now() - starts) / (ends - starts))
		var reserved: Array[String] = []
		for resource: String in order.get("escrow", {}):
			if int(order.escrow[resource]) > 0:
				reserved.append(ui.RESOURCE_NAMES.get(resource,resource) + " " + ui.format_balance(int(order.escrow[resource])))
		if not reserved.is_empty():
			ui.UiKit.label(box, "Резерв заказа: " + ", ".join(reserved), 16, ui.UiKit.INK_MUTED)
		var actions := HBoxContainer.new()
		actions.add_theme_constant_override("separation", 12)
		box.add_child(actions)
		var cancel: Button = link(actions, "Отменить работу", send.bind({"kind":"cancel", "order_id":order.id}))
		ui.UiKit.style_button(cancel, "danger")
		if order.kind in ["construction", "train", "siege"]:
			ui.UiKit.style_button(link(actions, "Использовать ускоритель", speedups.bind(order)), "secondary")
	if count == 0:
		muted("Активных заказов нет.")
	for receipt: String in ui.state.v6.rewards:
		if ui.state.v6.rewards[receipt].status == "pending":
			ui.UiKit.style_button(ui.button(ui.modal_body, "Получить награду " + receipt, send.bind({"kind":"claim", "receipt_id":receipt})), "green")
	section_title("Запасы поселения")
	stock_line(false)

func services(type: String) -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal(str(row_for(type, 1).name_ru), "full", "РАБОТЫ ЗДАНИЯ", ui.v6_card(type))
	section_title("Количество")
	var amount: SpinBox = ui.UiKit.quantity(ui.modal_body, 1, 4000, 1)[1]
	section_title({"B15":"Исследования", "B16":"Раненые"}.get(type, "Отряды"))
	if type == "B17":
		for machine: Dictionary in ui.state.v6.get("machines", []):
			if machine.location == "home" and int(machine.hp) < int(machine.max_hp):
				ui.button(ui.modal_body, "Ремонт тарана · %d / %d" % [int(machine.hp), int(machine.max_hp)], confirm.bind({"kind":"repair_ram", "machine_id":machine.id}))
	if type == "B15":
		for family: String in ["R_BUILD", "R_ECON", "R_ATTACK", "R_DEFENCE"]:
			var rank: int = int(ui.state.v6.research.get(family, 0))
			if rank < 11:
				var title: String = {"R_BUILD":"Организация строительства", "R_ECON":"Экономика", "R_ATTACK":"Атака войск", "R_DEFENCE":"Защита войск"}[family]
				ui.button(ui.modal_body, "%s → %s" % [title, ROMAN[rank]], confirm.bind({"kind":"research", "research":family + "-" + str(rank+1)}))
	elif type == "B16":
		for unit: String in ui.state.v6.wounded:
			var unit_id := unit
			ui.button(ui.modal_body, "%s · раненых %d" % [unit_id, int(ui.state.v6.wounded[unit_id])], func(): confirm({"kind":"heal", "units":{unit_id:int(amount.value)}}))
	else:
		for unit: Dictionary in catalogue.units:
			if unit.building_id == type:
				var unit_id: String = unit.unit_id
				var pick: Button = ui.button(ui.modal_body, str(unit.name_ru), func(): confirm({"kind":"siege" if type == "B17" else "train", "unit":unit_id, "quantity":int(amount.value)}))
				unit_card(pick, unit_id)

# A unit button of a building's work list: portrait on the left, name, a taller plate.
func unit_card(control: Button, unit_id: String) -> void:
	control.custom_minimum_size.y = 76
	control.alignment = HORIZONTAL_ALIGNMENT_LEFT
	control.begin_bulk_theme_override()
	control.add_theme_font_size_override("font_size", 21)
	if ResourceLoader.exists("res://assets/ui/web-panels/" + unit_id + ".png"):
		control.icon = ui.panel_texture(unit_id + ".png")
		control.expand_icon = true
		control.add_theme_constant_override("icon_max_width", 58)
		control.add_theme_constant_override("h_separation", 16)
	control.end_bulk_theme_override()

func trade() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal("Рынок", "full", "ОБЩИЙ ДНЕВНОЙ ОБОРОТ", ui.v6_card("B05"))
	section_title("Сделка")
	var amount: SpinBox = ui.UiKit.quantity(ui.modal_body, 1, 10000000, 1)[1]
	amount.custom_minimum_size.x = 170
	var deals := GridContainer.new()
	deals.name = "Deals"
	deals.columns = 3
	deals.add_theme_constant_override("h_separation", 12)
	deals.add_theme_constant_override("v_separation", 10)
	ui.modal_body.add_child(deals)
	for resource: String in ["wood", "food", "stone", "iron"]:
		var r := resource
		var name := HBoxContainer.new()
		name.add_theme_constant_override("separation", 10)
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		deals.add_child(name)
		ui.add_resource_icon(name, r, 34)
		ui.UiKit.label(name, str(ui.RESOURCE_NAMES[r]), 19, ui.UiKit.INK, ui.UiKit.LABEL_FONT, false).size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var buy: Button = ui.button(deals, "Купить " + str(ui.RESOURCE_NAMES[r]), func(): send({"kind":"trade", "direction":"buy", "resource":r, "quantity":int(amount.value)}))
		ui.UiKit.style_button(buy, "green", 17)
		buy.custom_minimum_size.x = 200
		var sell: Button = ui.button(deals, "Продать " + str(ui.RESOURCE_NAMES[r]), func(): send({"kind":"trade", "direction":"sell", "resource":r, "quantity":int(amount.value)}))
		ui.UiKit.style_button(sell, "secondary", 17)
		sell.custom_minimum_size.x = 200
	section_title("Запасы поселения")
	stock_line()

func metric_value(metric: String, value: Variant) -> String:
	if metric.ends_with("_bp"):
		return String.num(float(value) / 100.0, 2) + "%"
	if metric.ends_with("_rate_h") or metric.ends_with("_hp_h"):
		return "%s/ч" % plain_number(value)
	return plain_number(value)

# 3000.0 reads "3 000"; fractions keep up to two decimals.
func plain_number(value: Variant) -> String:
	if not (value is float or value is int):
		return str(value)
	if is_equal_approx(float(value), roundf(float(value))):
		return ui.format_balance(int(roundf(float(value))))
	return String.num(float(value), 2)

func account() -> void:
	begin_view()
	var primary: bool = ui.endpoint == "https://drenovar-game.ali069587.workers.dev"
	ui.open_modal("Аккаунт", "full", "DRENOVAR · ОБЩИЙ ГОРОД" if primary else "DRENOVAR · ТЕСТОВАЯ ВЕРСИЯ")
	ui.message.text = ""
	ui.row(ui.modal_body, "Версия %s · сборка %s" % [ProjectSettings.get_setting("application/config/version"), ProjectSettings.get_setting("application/config/build_number", "")])
	if not ui.login_proof.is_empty():
		var challenge: String = ui.login_proof.sha256_text()
		var code: String = challenge.left(8).to_upper()
		ui.row(ui.modal_body, "Код подтверждения: " + code)
		if ui.pending_login_save_error:
			ui.row(ui.modal_body, "Не удалось сохранить незавершённый вход. Если приложение перезапустится, начните вход заново.")
		ui.row(ui.modal_body, "В Safari войдите в тот же аккаунт ChatGPT, которому принадлежит ваш город. Введите этот код и нажмите «Разрешить вход». Затем вернитесь в DRENOVAR — откроется существующий город.")
		ui.button(ui.modal_body, "Открыть вход через ChatGPT", ui.open_login_page.bind(challenge))
		ui.button(ui.modal_body, "Скопировать код", func(): DisplayServer.clipboard_set(code))
		ui.button(ui.modal_body, "Проверить вход", ui.finish_login.bind(true))
		ui.button(ui.modal_body, "Начать вход заново", ui.restart_login)
		ui.button(ui.modal_body, "Отмена входа", ui.cancel_transfer)
		return
	if ui.client_update_required:
		ui.row(ui.modal_body, "Сервер запросил обновление приложения. Здесь указан номер установленной сборки.")
		ui.button(ui.modal_body, "Открыть сборки DRENOVAR", func(): OS.shell_open("https://github.com/ali7prg/Drenovar/releases"))
	if primary and not enabled():
		ui.button(ui.modal_body, "Войти через ChatGPT", ui.begin_main_login)
	ui.row(ui.modal_body, "Войдите через ChatGPT, чтобы открыть свой существующий город. Здания, ресурсы и армия останутся на общем сервере. Подключение по коду — дополнительный способ входа." if primary else "Это отдельный тестовый мир V6. Поселения действующей игры здесь пока недоступны; их прогресс сохранён в действующей версии.")
	ui.button(ui.modal_body, "Открыть основной город в браузере" if primary else "Открыть действующую веб-версию", func(): OS.shell_open(ui.OLD_SERVER_URL))
	if ui.restoring_session:
		ui.row(ui.modal_body, "Восстанавливаем подключение к вашему городу…")
		ui.button(ui.modal_body, "Повторить подключение", ui.restore_account)
		return
	if not ui.connected():
		ui.button(ui.modal_body, "Подключить устройство" if primary else "Подключиться к тестовому миру", func():
			await ui.device_login()
			account()
		)
		return
	if ui.saved_session_error:
		ui.row(ui.modal_body, "Не удалось сохранить вход на устройстве. Не закрывайте приложение до подключения второго устройства.")
	if enabled():
		ui.row(ui.modal_body, str(ui.state.city.name))
		if not ui.state.v6.get("legacy_building_archive", []).is_empty():
			ui.button(ui.modal_body, "Архив прежних зданий", archive)
		ui.row(ui.modal_body, "Чтобы открыть этот же город на другом устройстве, получите код и введите его там. Код действует 10 минут.")
		ui.button(ui.modal_body, "Получить код подключения", pairing_code)
	else:
		ui.row(ui.modal_body, "Введите код из своего города в веб-версии. Новое поселение для этого создавать не нужно." if primary else "Введите код из аккаунта веб-версии V6 или создайте отдельное тестовое поселение.")
		if not primary:
			ui.button(ui.modal_body, "Создать тестовое поселение", ui.create_settlement)
	var input := LineEdit.new()
	input.placeholder_text = "16 знаков из веб-версии V6"
	input.max_length = 20
	input.custom_minimum_size = Vector2(260, 48)
	ui.modal_body.add_child(input)
	ui.button(ui.modal_body, "Открыть мой город" if primary else "Подключить тестовое поселение", func():
		var response: Dictionary = await ui.send_request("pair/accept", {"code":input.text})
		if response.has("error"):
			ui.show_error(response)
		else:
			ui.player_id = ""
			await ui.sync_account()
			account()
	)
	ui.button(ui.modal_body, "Выйти из аккаунта на устройстве", ui.confirm_profile_action.bind(ui.sign_out_question(), ui.sign_out))

func archive() -> void:
	begin_view()
	await load_catalogue()
	ui.open_modal("Архив прежних зданий", "full", "ТЕСТОВЫЙ ВАРИАНТ COMPAT-P2")
	ui.row(ui.modal_body, "Исходные здания сохранены в архиве; они не дают второй игровой эффект. Компенсация за преобразование выдаётся один раз.")
	for entry: Dictionary in ui.state.v6.get("legacy_building_archive", []):
		var previous: Dictionary = entry.instance
		var row: Dictionary = row_for(str(previous.to_type), int(previous.level))
		ui.row(ui.modal_body, "%s · %s · прежний участок %s" % [str(row.get("name_ru", "Прежнее здание")), ROMAN[int(previous.level)-1], str(previous.plot)])
		for resource: String in entry.proposed_compensation:
			ui.row(ui.modal_body, "%s: %d" % [ui.RESOURCE_NAMES[resource], int(entry.proposed_compensation[resource])])

func pairing_code() -> void:
	var response: Dictionary = await ui.send_request("pair/create", {})
	if response.has("error"):
		ui.show_error(response)
		return
	ui.open_modal("Код подключения", "center", "ДЕЙСТВУЕТ 10 МИНУТ")
	ui.row(ui.modal_body, str(response.code))
	ui.row(ui.modal_body, "В веб-версии откройте «Аккаунт» и введите код. Показывайте код только своему устройству.")

func objectives() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal("Цели поселения", "full", "НАГРАДЫ")
	for step: Dictionary in ui.state.v6.get("starter", []):
		ui.row(ui.modal_body, str(step.title) + (" · получено" if step.claimed else " · выполнено" if step.ready else " · в процессе"))
		if step.ready and not step.claimed:
			var objective: String = step.id
			ui.button(ui.modal_body, "Получить награду", func(): await ui.command({"kind":"starter71", "objectiveId":objective}); objectives())

func speedups(order: Dictionary) -> void:
	begin_view()
	ui.open_modal("Ускорить работу", "full", "ПРЕДМЕТЫ УСКОРЕНИЯ")
	var queue: String = "construction" if order.kind == "construction" else "training"
	time_card("До завершения", ceili((float(order.ends_at)*1000.0-ui.timer_now())/1000.0), float(order.ends_at)*1000.0)
	muted("Выберите ускоритель для текущей работы.")
	var grid := VBoxContainer.new()
	grid.name = "SpeedItems"
	grid.add_theme_constant_override("separation", 10)
	ui.modal_body.add_child(grid)
	var tiers := [60, 300, 900, 1800, 3600, 7200, 18000, 36000]
	var confirmation := {"item":""}
	var note := Label.new()
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.add_theme_color_override("font_color", ui.UiKit.WARN)
	note.add_theme_font_size_override("font_size", 16)
	for index: int in tiers.size():
		var item: String = queue + "-" + str(index+1)
		var count: int = int(ui.state.items.get(item, 0))
		if count > 0:
			var seconds: int = tiers[index]
			var body := {"kind":"speedup", "queue":queue, "item":item, "orderId":order.id, "expectedEndsAt":float(order.ends_at)*1000.0, "confirmUnused":false}
			var card := PanelContainer.new()
			card.add_theme_stylebox_override("panel", ui.UiKit.row_style())
			grid.add_child(card)
			var line := HBoxContainer.new()
			line.add_theme_constant_override("separation", 14)
			card.add_child(line)
			line.add_child(ui.UiKit.icon_tile(ui.UiKit.tex("kit_hourglass"), 64))
			var texts := VBoxContainer.new()
			texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			texts.alignment = BoxContainer.ALIGNMENT_CENTER
			line.add_child(texts)
			ui.UiKit.label(texts, "Ускорение · %s" % duration(seconds), 20, ui.UiKit.INK, ui.UiKit.LABEL_FONT)
			ui.UiKit.label(texts, "Сокращает время работы «%s» на %s" % ["Строительство" if queue == "construction" else "Обучение", duration(seconds)], 16, ui.UiKit.INK_MUTED)
			ui.UiKit.label(texts, "В наличии: %d" % count, 16, ui.UiKit.BRONZE, ui.UiKit.LABEL_FONT)
			var use := work_button(line, "Использовать", func():
				var remaining: float = (float(order.ends_at)*1000.0-ui.timer_now())/1000.0
				if remaining <= 0:
					note.text = "Работа завершена. Обновляем состояние…"
					await ui.ensure_v6_ready(true)
					queues()
					return
				if seconds > remaining and confirmation.item != item:
					confirmation.item = item
					note.text = "Остаток %s пропадёт. Нажмите ускоритель ещё раз, чтобы подтвердить." % duration(ceili(seconds-remaining))
					return
				body.confirmUnused = seconds > remaining
				if await ui.command(body):
					queues()
			)
			use.size_flags_horizontal = Control.SIZE_SHRINK_END
			use.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			use.custom_minimum_size = Vector2(190, 52)
			ui.UiKit.style_button(use, "secondary")
	muted("Неиспользованный остаток ускорения пропадёт." if grid.get_child_count() else "Ускорителей пока нет. Таймер продолжает идти.")
	ui.modal_body.add_child(note)

func army() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	ui.open_modal("Армия и осада", "full", "ПОХОДЫ")
	warnings()
	ui.UiKit.stat_row(ui.modal_body, "Армия", "%d / %d" % [int(ui.state.v6.army_used), int(ui.state.v6.army_capacity)])
	ui.UiKit.progress_bar(ui.modal_body, float(ui.state.v6.army_used) / maxf(1.0, float(ui.state.v6.army_capacity)))
	ui.UiKit.stat_row(ui.modal_body, "Поход", "до %d мест" % int(ui.state.v6.march_capacity))
	ui.UiKit.stat_row(ui.modal_body, "Отрядов одновременно", str(int(ui.state.v6.march_parallel)))
	ui.UiKit.stat_row(ui.modal_body, "Коек в лазарете", str(int(ui.state.v6.hospital_capacity)))
	muted("Таран занимает 5 мест. Новые раненые сверх коек станут погибшими; доступно коек %d." % int(ui.state.v6.hospital_capacity))
	var more := links()
	link(more, "Показать плац в городе", ui.open_parade)
	link(more, "Раненые и лечение", services.bind("B16"))
	var marching := false
	for march: Dictionary in ui.state.get("armies", []) + ui.state.get("world", {}).get("armies", []):
		if march.get("owner", ui.state.playerId) != ui.state.playerId or march.status == "returned":
			continue
		if not marching:
			marching = true
			section_title("Отряды в походе")
		ui.UiKit.label(ui.modal_body, "%s · %s" % [str(march.name), {"outbound":"В пути к цели", "fighting":"В бою", "returning":"Возвращается"}.get(str(march.status), str(march.status))], 19, ui.UiKit.INK, ui.UiKit.LABEL_FONT)
		if march.has("cargo") and not march.cargo.get("issued", false):
			ui.row(ui.modal_body, "Груз поступит по прибытии отряда:")
			for resource: String in march.cargo.resources:
				if int(march.cargo.resources[resource]) > 0:
					ui.row(ui.modal_body, "%s: %d" % [ui.RESOURCE_NAMES[resource], int(march.cargo.resources[resource])])
		ui.button(ui.modal_body, "Показать отряд", ui.focus_army.bind(march))
		if march.status in ["outbound", "fighting"]:
			var action := {"kind":"recall" if march.status == "outbound" else "retreat", "armyId":march.id}
			ui.button(ui.modal_body, "Отозвать" if march.status == "outbound" else "Отступить", func(): await ui.command(action); army())
	for target: Dictionary in ui.state.get("world", {}).get("cities", []):
		if target.id != ui.state.playerId and target.get("pvp", false):
			ui.button(ui.modal_body, "Поход: " + str(target.name), formation.bind(str(target.id), str(target.name)))

func formation(target: String, name: String) -> void:
	begin_view()
	ui.open_modal("Поход: " + name, "full", "СОСТАВ")
	var inputs: Dictionary = {}
	for unit: Dictionary in catalogue.units:
		var available: int = int(ui.state.v6.healthy.get(unit.unit_id, 0))
		if available <= 0:
			continue
		ui.row(ui.modal_body, "%s · доступно %d · мест %d" % [str(unit.name_ru), available, int(unit.army_slots)])
		var input := SpinBox.new()
		input.min_value = 0
		input.max_value = mini(available, int(ui.state.v6.march_capacity)/int(unit.army_slots))
		input.custom_minimum_size = Vector2(180, 48)
		ui.modal_body.add_child(input)
		inputs[unit.unit_id] = input
	ui.button(ui.modal_body, "Рассчитать поход", func():
		var units: Dictionary = {}
		for id: String in inputs:
			if int(inputs[id].value) > 0:
				units[id] = int(inputs[id].value)
		var body := {"kind":"worldMarch", "worldKind":"pvp", "encounterId":target, "units":units}
		var result: Dictionary = await ui.request("march-preview", body)
		if result.has("error"):
			ui.show_error(result)
			return
		ui.open_modal("Отправить отряд", "center", "ПОДТВЕРЖДЕНИЕ")
		ui.row(ui.modal_body, "Дорога: %d с · %d мест. Потери зависят от гарнизона и сопровождения." % [int(ceil(float(result.travelMs)/1000.0)), int(result.total)])
		ui.button(ui.modal_body, "Отправить", func(): await ui.command(body); army())
	)
