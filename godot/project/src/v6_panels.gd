extends RefCounted

const VERSION := "DRENOVAR-V6-C1.0"
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
var ui: Node
var catalogue: Dictionary = {}

func _init(owner_node: Node) -> void:
	ui = owner_node

func enabled() -> bool:
	return ui.state.get("economy_version", "") == VERSION and ui.state.get("v6") is Dictionary

func load_catalogue() -> bool:
	if catalogue.get("economy_version", "") == VERSION:
		return true
	var response: Dictionary = await ui.request("command", {"kind":"v6catalog"})
	if response.get("economy_version", "") != VERSION:
		ui.show_error({"error":"Сервер не поддерживает экономику V6. Обновите тестовую версию."})
		return false
	catalogue = response
	return true

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
		ui.row(ui.modal_body, "Башня обнаружила нападение · до прибытия %d с" % int(warning.eta_seconds))

func stock_line() -> void:
	warnings()
	var s: Dictionary = ui.state.v6
	for r: String in ["wood", "food", "stone", "iron", "coins"]:
		ui.row(ui.modal_body, "%s: %d / %d · резерв %d · %.2f/ч%s" % [ui.RESOURCE_NAMES[r], int(s.stock[r]), int(s.capacities[r]), int(s.escrow[r]), float(s.production_per_hour[r]), " · производство приостановлено" if s.production_stopped[r] else ""])
	ui.row(ui.modal_body, "Работники: %d / %d · армия: %d / %d" % [int(s.workforce.used), int(s.workforce.capacity), int(s.army_used), int(s.army_capacity)])

func economy() -> void:
	ui.open_modal("Экономика поселения", "right", "V6 · В ЧАС")
	stock_line()
	ui.button(ui.modal_body, "Очереди и отмена", queues)
	ui.button(ui.modal_body, "Цели поселения", objectives)

func move_building(b: Dictionary, environment: String) -> void:
	ui.open_modal("Переместить здание", "right", "ПОДХОДЯЩИЕ УЧАСТКИ")
	for plot: String in ui.state.get("v6_plots", {}):
		if environment not in ui.state.v6_plots[plot]:
			continue
		var occupied := false
		for other: Dictionary in ui.state.v6.buildings:
			occupied = occupied or other.plot == plot
		if not occupied:
			ui.button(ui.modal_body, "Участок " + plot, send.bind({"kind":"move", "building_id":b.id, "plot":plot}))

func catalog() -> void:
	if not await load_catalogue():
		return
	ui.open_modal("Строительство", "right", "27 ТИПОВ · I–XI")
	ui.row(ui.modal_body, "Пшеница и рыбалка занимают один общий пищевой участок.")
	for row: Dictionary in catalogue.buildings:
		if int(row.level) != 1:
			continue
		var b: Dictionary = building(row.building_id)
		ui.button(ui.modal_body, "%s · %s" % [row.name_ru, ROMAN[int(b.level)-1] if not b.is_empty() else "построить"], inspect.bind(str(row.building_id)))
	ui.button(ui.modal_body, "Все очереди", queues)
	ui.button(ui.modal_body, "Армия и осада", army)
	ui.button(ui.modal_body, "Подключить другое устройство", account)

func inspect(type: String) -> void:
	if not await load_catalogue():
		return
	var b: Dictionary = building(type)
	var level: int = int(b.get("level", 0))
	var row: Dictionary = row_for(type, maxi(1, level))
	ui.open_modal(str(row.name_ru), "right", "УРОВЕНЬ " + (ROMAN[level-1] if level > 0 else "НЕ ПОСТРОЕНО"))
	if level > 0:
		for metric: String in row.effects:
			ui.row(ui.modal_body, "%s: %s" % [str(catalogue.get("metrics", {}).get(metric, {}).get("name_ru", metric)), metric_value(metric, row.effects[metric])])
	if level < 11:
		var next: Dictionary = row_for(type, level + 1)
		ui.row(ui.modal_body, "Следующий уровень: " + ROMAN[level])
		for d: Dictionary in next.requirements:
			var current: Dictionary = building(d.building_id)
			var ok: bool = int(current.get("level", 0)) >= int(d.level)
			ui.row(ui.modal_body, "%s %s ≥ %s" % ["✓" if ok else "•", row_for(d.building_id, 1).name_ru, ROMAN[int(d.level)-1]])
		var action := {"kind":"construction", "building":type, "target":level+1}
		if level > 0:
			ui.button(ui.modal_body, "Проверить улучшение", confirm.bind(action))
		else:
			ui.row(ui.modal_body, "Выберите участок подходящей местности: " + str(next.environment))
			for plot: String in ui.state.get("v6_plots", {}):
				if next.environment in ui.state.v6_plots[plot]:
					var placement: Dictionary = action.duplicate()
					placement.plot = plot
					ui.button(ui.modal_body, "Участок " + plot, confirm.bind(placement))
	else:
		ui.row(ui.modal_body, "XI — окончательный уровень.")
	if type in ["B11", "B12", "B13", "B17", "B15", "B16"] and level > 0:
		ui.button(ui.modal_body, "Работы здания", services.bind(type))
	if type == "B06" and level > 0:
		ui.button(ui.modal_body, "Посетить лагерь", func(): await ui.command({"kind":"v6collect"}); objectives())
	if type == "B18" and level > 0:
		ui.row(ui.modal_body, "Прочность стены: %d / %d" % [int(ui.state.v6.wall_hp), int(ui.state.v6.wall_max_hp)])
		ui.button(ui.modal_body, "Ремонт стены", confirm.bind({"kind":"repair_wall"}))
	if type == "B05" and level > 0:
		ui.button(ui.modal_body, "Рынок", trade)
	if type in ["B22", "B24"] and level > 0:
		ui.button(ui.modal_body, "Сменить пищевую специализацию", send.bind({"kind":"switch_food", "variant":"B24" if type == "B22" else "B22"}))
	if level > 0:
		ui.button(ui.modal_body, "Переместить здание", move_building.bind(b, str(row.environment)))
	ui.button(ui.modal_body, "Очереди и отмена", queues)

func confirm(action: Dictionary) -> void:
	var intent: Dictionary = action.duplicate(true)
	intent.economy_version = VERSION
	var response: Dictionary = await ui.request("command", {"kind":"v6quote", "intent":intent})
	ui.open_modal("Подтвердить работу", "right", "РАСЧЁТ СЕРВЕРА")
	if not response.get("ok", false):
		ui.row(ui.modal_body, str(response.get("reason", {}).get("message", response.get("error", "Нет ответа сервера"))))
		var reason: Dictionary = response.get("reason", {})
		if reason.has("resource"):
			ui.row(ui.modal_body, "%s: нужно %s, доступно %s" % [ui.RESOURCE_NAMES.get(reason.resource, reason.resource), str(reason.get("required", "")), str(reason.get("available", ""))])
		return
	var q: Dictionary = response.quote
	for resource: String in q.cost:
		ui.row(ui.modal_body, "%s: %d" % [ui.RESOURCE_NAMES[resource], int(q.cost[resource])])
	ui.row(ui.modal_body, "Базовое время: %d с · итоговое: %d с · скорость +%.2f%%" % [int(q.base_seconds), int(q.duration_seconds), float(q.speed_bp)/100.0])
	ui.row(ui.modal_body, "Отмена вернёт оставшийся резерв. В ремонте стены выполненная часть уже оплачена." if action.kind == "repair_wall" else "Цена будет зарезервирована до завершения. Отмена возвращает сохранённый резерв.")
	intent.expected_duration_seconds = int(q.duration_seconds)
	ui.button(ui.modal_body, "Начать", send.bind(intent))

func send(action: Dictionary) -> void:
	var intent: Dictionary = action.duplicate(true)
	intent.economy_version = VERSION
	var success: bool = await ui.command({"kind":"v6", "intent":intent})
	if success:
		queues()

func queues() -> void:
	ui.open_modal("Очереди поселения", "right", "ЗАКАЗЫ СЕРВЕРА")
	stock_line()
	var count := 0
	for order: Dictionary in ui.state.v6.orders:
		if order.status != "pending":
			continue
		count += 1
		var names := {"construction":"Строительство", "train":"Обучение", "heal":"Лечение", "research":"Исследование", "siege":"Сборка таранов", "repair_ram":"Ремонт тарана", "repair_wall":"Ремонт стены"}
		if float(order.starts_at)*1000.0 > ui.timer_now():
			ui.countdown("Ожидание начала", float(order.starts_at)*1000.0)
		ui.countdown("%s · %s" % [str(row_for(str(order.building), 1).get("name_ru", order.building)), str(names.get(order.kind, order.kind))], float(order.ends_at)*1000.0)
		ui.button(ui.modal_body, "Отменить работу", send.bind({"kind":"cancel", "order_id":order.id}))
		if order.kind in ["construction", "train", "siege"]:
			ui.button(ui.modal_body, "Использовать ускоритель", speedups.bind(order))
	if count == 0:
		ui.row(ui.modal_body, "Активных заказов нет.")
	for receipt: String in ui.state.v6.rewards:
		if ui.state.v6.rewards[receipt].status == "pending":
			ui.button(ui.modal_body, "Получить награду " + receipt, send.bind({"kind":"claim", "receipt_id":receipt}))

func services(type: String) -> void:
	if not await load_catalogue():
		return
	ui.open_modal(str(row_for(type, 1).name_ru), "right", "РАБОТЫ ЗДАНИЯ")
	var amount := SpinBox.new()
	amount.min_value = 1
	amount.max_value = 4000
	amount.value = 1
	amount.custom_minimum_size = Vector2(180, 48)
	ui.modal_body.add_child(amount)
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
				ui.button(ui.modal_body, str(unit.name_ru), func(): confirm({"kind":"siege" if type == "B17" else "train", "unit":unit_id, "quantity":int(amount.value)}))

func trade() -> void:
	ui.open_modal("Рынок", "right", "ОБЩИЙ ДНЕВНОЙ ОБОРОТ")
	stock_line()
	var amount := SpinBox.new()
	amount.min_value = 1
	amount.max_value = 10000000
	amount.custom_minimum_size = Vector2(180, 48)
	ui.modal_body.add_child(amount)
	for resource: String in ["wood", "food", "stone", "iron"]:
		var r := resource
		ui.button(ui.modal_body, "Купить " + str(ui.RESOURCE_NAMES[r]), func(): send({"kind":"trade", "direction":"buy", "resource":r, "quantity":int(amount.value)}))
		ui.button(ui.modal_body, "Продать " + str(ui.RESOURCE_NAMES[r]), func(): send({"kind":"trade", "direction":"sell", "resource":r, "quantity":int(amount.value)}))

func metric_value(metric: String, value: Variant) -> String:
	if metric.ends_with("_bp"):
		return "%g%%" % (float(value) / 100.0)
	if metric.ends_with("_rate_h") or metric.ends_with("_hp_h"):
		return "%s/ч" % str(value)
	return str(value)

func account() -> void:
	ui.open_modal("Аккаунт", "profile", "DRENOVAR · ТЕСТОВАЯ ВЕРСИЯ")
	ui.message.text = ""
	ui.row(ui.modal_body, "Это отдельный тестовый мир V6. Поселения действующей игры здесь пока недоступны; их прогресс сохранён в действующей версии.")
	ui.button(ui.modal_body, "Открыть действующую веб-версию", func(): OS.shell_open(ui.OLD_SERVER_URL))
	if not ui.connected():
		ui.button(ui.modal_body, "Подключиться к тестовому миру", func():
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
		ui.row(ui.modal_body, "Чтобы продолжить этот тестовый город в браузере, получите код и введите его в веб-версии V6. Код действует 10 минут.")
		ui.button(ui.modal_body, "Получить код подключения", pairing_code)
	else:
		ui.row(ui.modal_body, "Введите код из аккаунта веб-версии V6 или создайте отдельное тестовое поселение.")
		ui.button(ui.modal_body, "Создать тестовое поселение", ui.create_settlement)
	var input := LineEdit.new()
	input.placeholder_text = "16 знаков из веб-версии V6"
	input.max_length = 20
	input.custom_minimum_size = Vector2(260, 48)
	ui.modal_body.add_child(input)
	ui.button(ui.modal_body, "Подключить тестовое поселение", func():
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
	await load_catalogue()
	ui.open_modal("Архив прежних зданий", "right", "ТЕСТОВЫЙ ВАРИАНТ COMPAT-P2")
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
	ui.open_modal("Код подключения", "right", "ДЕЙСТВУЕТ 10 МИНУТ")
	ui.row(ui.modal_body, str(response.code))
	ui.row(ui.modal_body, "В веб-версии откройте «Аккаунт» и введите код. Показывайте код только своему устройству.")

func objectives() -> void:
	ui.open_modal("Цели поселения", "right", "НАГРАДЫ")
	for step: Dictionary in ui.state.v6.get("starter", []):
		ui.row(ui.modal_body, str(step.title) + (" · получено" if step.claimed else " · выполнено" if step.ready else " · в процессе"))
		if step.ready and not step.claimed:
			var objective: String = step.id
			ui.button(ui.modal_body, "Получить награду", func(): await ui.command({"kind":"starter71", "objectiveId":objective}); objectives())

func speedups(order: Dictionary) -> void:
	ui.open_modal("Ускорить работу", "right", "ПРЕДМЕТЫ АККАУНТА")
	var queue: String = "construction" if order.kind == "construction" else "training"
	var tiers := [60, 300, 900, 1800, 3600, 7200, 18000, 36000]
	for index: int in tiers.size():
		var item: String = queue + "-" + str(index+1)
		var count: int = int(ui.state.items.get(item, 0))
		if count > 0:
			var body := {"kind":"speedup", "queue":queue, "item":item, "orderId":order.id, "expectedEndsAt":float(order.ends_at)*1000.0, "confirmUnused":true}
			ui.row(ui.modal_body, "Остаток ускорения сверх таймера пропадёт.")
			ui.button(ui.modal_body, "%d с · есть %d · использовать" % [int(tiers[index]), count], func(): await ui.command(body); queues())

func army() -> void:
	if not await load_catalogue():
		return
	ui.open_modal("Армия и осада", "right", "ПОХОДЫ")
	warnings()
	ui.row(ui.modal_body, "Армия %d / %d · поход до %d мест · отрядов %d" % [int(ui.state.v6.army_used), int(ui.state.v6.army_capacity), int(ui.state.v6.march_capacity), int(ui.state.v6.march_parallel)])
	ui.row(ui.modal_body, "Таран занимает 5 мест. Новые раненые сверх коек станут погибшими; доступно коек %d." % int(ui.state.v6.hospital_capacity))
	ui.button(ui.modal_body, "Показать плац в городе", ui.open_parade)
	ui.button(ui.modal_body, "Раненые и лечение", services.bind("B16"))
	for march: Dictionary in ui.state.get("armies", []) + ui.state.get("world", {}).get("armies", []):
		if march.get("owner", ui.state.playerId) != ui.state.playerId or march.status == "returned":
			continue
		ui.row(ui.modal_body, "%s · %s" % [str(march.name), {"outbound":"В пути к цели", "fighting":"В бою", "returning":"Возвращается"}.get(str(march.status), str(march.status))])
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
	ui.open_modal("Поход: " + name, "right", "СОСТАВ")
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
		ui.open_modal("Отправить отряд", "right", "ПОДТВЕРЖДЕНИЕ")
		ui.row(ui.modal_body, "Дорога: %d с · %d мест. Потери зависят от гарнизона и сопровождения." % [int(ceil(float(result.travelMs)/1000.0)), int(result.total)])
		ui.button(ui.modal_body, "Отправить", func(): await ui.command(body); army())
	)
