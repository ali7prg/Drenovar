extends RefCounted
## Recruitment window of the V6 training buildings (premium UI stage 2, ui_premium/STAGE2.md):
## barracks B11, range B12, stables B13 and the siege workshop B17.
##
## Left: a rail of round bronze medallions, one per training building of the settlement
## (switching keeps the window and its 3D stage), and the hero stage (src/unit_stage.gd).
## Right (the scrolling body): tier cards with portraits and owned counts, a summary with
## «Подробнее», then either the order (quantity, cost strip, time, «Обучить»), the lock
## with what opens the unit, or the running orders of the building with «Ускорить» and
## «Отменить». Costs and times use the server's own rules (cost x quantity, time with the
## building's speed bonus, rounded up); «Обучить» checks the authoritative quote and sends
## that exact intent, so the order never differs from what the window shows.

const UiKit = preload("res://src/ui_kit.gd")
const UnitStage = preload("res://src/unit_stage.gd")
const VERSION := "DRENOVAR-V6-C1.0"
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
const TRAINING := ["B11", "B12", "B13", "B17"]
const BRANCH := {"B11": "Пехота", "B12": "Стрелки", "B13": "Конница", "B17": "Осада"}
const RESOURCES := ["wood", "food", "stone", "iron", "coins"]
const CARD := Vector2(128, 178)

var panels
var ui
var type := ""
var unit_id := ""
var generation := -1
var chosen := {}
var quantities := {}
var details := false
var submitting := false
var cancel_armed := ""
var hero: Control
var stage: Control
var rail: VBoxContainer
var slider: HSlider
var field: SpinBox
var cost_labels := {}
var cost_cells := {}
var clock: Label
var train_button: Button
var hint: Label
var cards := {}
var shown_signature := ""
var watched := {}
var last_open_usec := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

static func trains(building_type: String) -> bool:
	return building_type in TRAINING

# ------------------------------------------------------------------ data

func catalogue() -> Dictionary:
	return panels.catalogue

func level_of(building_type: String) -> int:
	return int(panels.building(building_type).get("level", 0))

func units_of(building_type: String) -> Array:
	var list: Array = catalogue().get("units", []).filter(func(u): return str(u.building_id) == building_type)
	list.sort_custom(func(a, b): return [int(a.required_building), int(a.required_hall)] < [int(b.required_building), int(b.required_hall)])
	return list

func unit(id: String) -> Dictionary:
	for item: Dictionary in catalogue().get("units", []):
		if item.unit_id == id:
			return item
	return {}

func roster(id: String) -> Dictionary:
	return ui.unit_for_id(id)

func tier_of(item: Dictionary) -> int:
	return clampi(int(item.get("required_building", 1)), 1, 5)

func requirements(item: Dictionary) -> Array:
	var needs := []
	var hall := int(item.get("required_hall", 1))
	var own := int(item.get("required_building", 1))
	var home := str(item.get("building_id", type))
	needs.append([str(panels.row_for(home, 1).get("name_ru", home)), own, level_of(home) >= own])
	if hall > 1:
		needs.append([str(panels.row_for("B01", 1).get("name_ru", "Ратуша")), hall, level_of("B01") >= hall])
	return needs

func locked(item: Dictionary) -> bool:
	for need: Array in requirements(item):
		if not need[2]:
			return true
	return false

func prefix() -> String:
	return "siege" if type == "B17" else "training"

func effect(metric: String) -> int:
	return int(panels.row_for(type, maxi(1, level_of(type))).get("effects", {}).get(metric, 0))

func orders() -> Array:
	return ui.state.v6.orders.filter(func(o): return o.status == "pending" and str(o.building) == type and o.kind in ["train", "siege", "repair_ram"])

func owned(id: String) -> int:
	return int(ui.state.v6.get("healthy", {}).get(id, 0))

func stock() -> Dictionary:
	return ui.state.v6.get("stock", {})

## Same rounding as the server (v6/orders.mjs duration): ceil(base x 10000 / (10000 + bonus)).
func seconds_for(item: Dictionary, count: int) -> int:
	var base := int(item.get("seconds", 0)) * count
	var bonus := effect(prefix() + "_speed_bp")
	return maxi(1, ceili(float(base) * 10000.0 / float(10000 + bonus)))

func cost_for(item: Dictionary, count: int) -> Dictionary:
	var cost := {}
	for resource: String in RESOURCES:
		var each := int(item.get("cost", {}).get(resource, 0))
		if each > 0:
			cost[resource] = each * count
	return cost

## The largest batch the order can take now: the building's batch limit, free army places
## and the stores. 0 when none fits.
func max_quantity(item: Dictionary) -> int:
	var limit := effect(prefix() + "_batch")
	var slots := maxi(1, int(item.get("army_slots", 1)))
	var free := int(ui.state.v6.get("army_capacity", 0)) - int(ui.state.v6.get("army_used", 0))
	limit = mini(limit, free / slots)
	for resource: String in item.get("cost", {}):
		var each := int(item.cost[resource])
		if each > 0:
			limit = mini(limit, int(stock().get(resource, 0)) / each)
	return maxi(0, limit)

func queue_full() -> bool:
	return orders().size() >= maxi(1, effect(prefix() + "_orders"))

# ------------------------------------------------------------------ window

func is_open() -> bool:
	return generation == ui.modal_generation and ui.modal.visible and is_instance_valid(stage)

## Opens the window on a building (or switches the open window to it).
func open(building_type: String, pick := "") -> void:
	var started := Time.get_ticks_usec()
	if building_type != type:
		details = false
	type = building_type
	var list := units_of(type)
	if not pick.is_empty():
		chosen[type] = pick
	if not chosen.has(type) or unit(chosen[type]).is_empty() or str(unit(chosen[type]).building_id) != type:
		chosen[type] = default_unit(list)
	unit_id = chosen[type]
	var item := unit(unit_id)
	var title := str(panels.row_for(type, 1).get("name_ru", type))
	var eyebrow: String = "ОБУЧЕНИЕ ВОЙСК · УРОВЕНЬ " + str(ROMAN[clampi(level_of(type), 1, 11) - 1])
	if is_open():
		ui.set_modal_heading(title, eyebrow)
		stage.show_unit(unit_id, tier_of(item), unit_name(unit_id))
		build_rail()
		ui.modal_scroll.scroll_vertical = 0
	else:
		ui.open_modal(title, "full", eyebrow)
		generation = ui.modal_generation
		build_hero(item)
	render()
	last_open_usec = Time.get_ticks_usec() - started

func default_unit(list: Array) -> String:
	var best := ""
	for item: Dictionary in list:
		if best.is_empty() or not locked(item):
			best = item.unit_id
	return best

func unit_name(id: String) -> String:
	return str(unit(id).get("name_ru", roster(id).get("name", id)))

func build_hero(item: Dictionary) -> void:
	hero = HBoxContainer.new()
	hero.name = "RecruitHero"
	hero.add_theme_constant_override("separation", 0)
	hero.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.modal_hero.add_child(hero)
	hero.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rail = VBoxContainer.new()
	rail.name = "RecruitRail"
	rail.custom_minimum_size.x = 104
	rail.alignment = BoxContainer.ALIGNMENT_CENTER
	rail.add_theme_constant_override("separation", 8)
	rail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hero.add_child(rail)
	stage = UnitStage.new()
	stage.setup(ui.data, unit_id, tier_of(item), unit_name(unit_id))
	stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stage.info_pressed.connect(toggle_details)
	hero.add_child(stage)
	build_rail()
	ui.modal_hero_share = 0.43
	ui.arrange_modal()

func build_rail() -> void:
	for child in rail.get_children():
		rail.remove_child(child)
		child.queue_free()
	for building_type: String in TRAINING:
		if level_of(building_type) <= 0:
			continue
		var list := units_of(building_type)
		if list.is_empty():
			continue
		var face: String = list[0].unit_id
		var busy: bool = ui.state.v6.orders.any(func(o): return o.status == "pending" and str(o.building) == building_type)
		var medal := UiKit.rail_medal(UnitStage.portrait(face, true), building_type == type, str(BRANCH.get(building_type, "")), busy)
		medal.name = "Rail" + building_type
		medal.tooltip_text = str(panels.row_for(building_type, 1).get("name_ru", building_type))
		medal.pressed.connect(panels.services.bind(building_type))
		rail.add_child(medal)

# ------------------------------------------------------------------ right panel

func signature() -> String:
	var parts: Array = [type, unit_id, details, level_of(type), level_of("B01"), ui.state.v6.get("army_capacity", 0)]
	for order: Dictionary in orders():
		parts.append([order.id, order.ends_at, order.starts_at])
	for item: Dictionary in units_of(type):
		parts.append(owned(item.unit_id))
	return str(parts)

func render() -> void:
	ui.empty(ui.modal_body)
	cost_labels.clear()
	cost_cells.clear()
	cards.clear()
	slider = null
	field = null
	clock = null
	train_button = null
	hint = null
	cancel_armed = ""
	var item := unit(unit_id)
	shown_signature = signature()
	watched.clear()
	for order: Dictionary in orders():
		watched[order.id] = {"unit": str(order.get("unit", "")), "quantity": int(order.get("quantity", 1)), "kind": order.kind}
	top_row(item)
	if details:
		details_sheet(item)
	elif locked(item):
		lock_panel(item)
	else:
		if not queue_full():
			order_panel(item)
		for order: Dictionary in orders():
			queue_card(order)
		var free := maxi(0, effect(prefix() + "_orders") - orders().size())
		if free > 0:
			free_slot(free)
		if queue_full():
			UiKit.label(ui.modal_body, "Очередь здания заполнена: %d из %d. Новое обучение — после завершения или отмены." % [orders().size(), maxi(1, effect(prefix() + "_orders"))], 16, UiKit.INK_MUTED)
	if type == "B17" and not details:
		for machine: Dictionary in ui.state.v6.get("machines", []):
			if machine.location == "home" and int(machine.hp) < int(machine.max_hp):
				var repair: Button = ui.button(ui.modal_body, "Ремонт тарана · %d / %d" % [int(machine.hp), int(machine.max_hp)], panels.confirm.bind({"kind":"repair_ram", "machine_id":machine.id}))
				UiKit.style_button(repair, "secondary", 18)
	update_quote()

func top_row(item: Dictionary) -> void:
	var row := HBoxContainer.new()
	row.name = "RecruitTop"
	row.add_theme_constant_override("separation", 12)
	ui.modal_body.add_child(row)
	for candidate: Dictionary in units_of(type):
		var id: String = candidate.unit_id
		var closed := locked(candidate)
		# A closed card says what opens it (the building level) instead of the count.
		var count: String = "Нужен ур. " + str(ROMAN[int(candidate.get("required_building", 1)) - 1]) if closed else UiKit.compact(owned(id))
		if closed and level_of(type) >= int(candidate.get("required_building", 1)):
			count = "Ратуша " + str(ROMAN[int(candidate.get("required_hall", 1)) - 1])
		var card: BaseButton = UiKit.tier_card(tier_of(candidate), unit_name(id), count, UnitStage.portrait(id), id == unit_id, closed)
		card.name = "Card" + id
		card.custom_minimum_size = CARD
		card.pressed.connect(pick.bind(id))
		row.add_child(card)
		cards[id] = card
	var info := VBoxContainer.new()
	info.name = "RecruitSummary"
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.alignment = BoxContainer.ALIGNMENT_CENTER
	info.add_theme_constant_override("separation", 4)
	row.add_child(info)
	var stats := roster(unit_id)
	UiKit.label(info, unit_name(unit_id), 25, UiKit.INK, UiKit.LABEL_FONT, false)
	var kind := str(stats.get("unit_class", "Осадная машина" if type == "B17" else BRANCH.get(type, "")))
	UiKit.label(info, "%s · ступень %s · в войске %s" % [kind, ROMAN[tier_of(item) - 1], ui.format_balance(owned(unit_id))], 16, UiKit.INK_MUTED, null, false)
	var role := str(stats.get("role", ""))
	if type == "B17":
		role = "Бьёт стену: %d урона за удар каждые %d с. Обычным войскам урона не наносит." % [int(item.get("wall_damage_per_strike", 0)), int(item.get("strike_period_seconds", 0))]
	if not role.is_empty():
		var text := UiKit.label(info, role, 16, UiKit.INK)
		text.max_lines_visible = 2
	var figures := HBoxContainer.new()
	figures.add_theme_constant_override("separation", 10)
	info.add_child(figures)
	var values: Array = []
	if type == "B17":
		values = [["Урон стене", int(item.get("wall_damage_per_strike", 0))], ["Мест в армии", int(item.get("army_slots", 1))]]
	else:
		values = [["Атака", int(stats.get("attack", 0))], ["Защита", int(stats.get("defense", 0))], ["Здоровье", int(stats.get("hp", 0))], ["Мощь", int(item.get("power_reference", stats.get("power", 0)))]]
	UiKit.figures(figures, values)
	var more: Button = ui.button(figures, "Назад" if details else "Подробнее", toggle_details)
	more.name = "RecruitDetails"
	UiKit.style_button(more, "tertiary", 17)
	more.custom_minimum_size = Vector2(138, 44)
	more.size_flags_horizontal = Control.SIZE_SHRINK_END | Control.SIZE_EXPAND
	more.size_flags_vertical = Control.SIZE_SHRINK_CENTER

func order_panel(item: Dictionary) -> void:
	var limit := maxi(1, effect(prefix() + "_batch"))
	var most := max_quantity(item)
	var start := clampi(int(quantities.get(type, maxi(1, mini(10, most)))), 1, limit)
	var quantity := HBoxContainer.new()
	quantity.name = "RecruitQuantity"
	quantity.add_theme_constant_override("separation", 12)
	ui.modal_body.add_child(quantity)
	var pair: Array = UiKit.quantity(quantity, 1, limit, start)
	slider = pair[0]
	field = pair[1]
	quantity.get_child(0).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var top: Button = ui.button(quantity, "Макс", func():
		var best := max_quantity(unit(unit_id))
		if best > 0:
			field.value = best)
	top.name = "RecruitMax"
	UiKit.style_button(top, "tertiary", 17)
	top.custom_minimum_size = Vector2(92, 46)
	top.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	field.value_changed.connect(func(value: float):
		quantities[type] = int(value)
		update_quote())
	var strip := UiKit.cost_strip(ui.modal_body, cost_for(item, start), ui.resource_icons, stock(), ui.RESOURCE_NAMES)
	strip.name = "RecruitCost"
	for cell: Node in strip.get_child(0).get_children():
		var resource := resource_of(str(cell.tooltip_text))
		cost_cells[resource] = cell
		cost_labels[resource] = cell.get_child(0).get_child(cell.get_child(0).get_child_count() - 1)
	var go := HBoxContainer.new()
	go.name = "RecruitAction"
	go.add_theme_constant_override("separation", 14)
	ui.modal_body.add_child(go)
	clock = UiKit.timer_pill(go, "Время обучения", "")
	var pill: Control = go.get_child(0)
	pill.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pill.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	train_button = ui.button(go, "В очередь" if not orders().is_empty() else "Обучить", train)
	train_button.name = "RecruitTrain"
	UiKit.style_button(train_button, "primary", 22)
	train_button.custom_minimum_size = Vector2(250, 56)
	# One line (no wrapping pass when the window opens); long reasons end with an ellipsis.
	hint = UiKit.label(ui.modal_body, "", 15, UiKit.INK_MUTED, null, false)
	hint.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	hint.name = "RecruitHint"

func resource_of(tip: String) -> String:
	for resource: String in RESOURCES:
		if tip.begins_with(str(ui.RESOURCE_NAMES.get(resource, resource)) + ":"):
			return resource
	return ""

## Cost, time, limits and the state of «Обучить» for the current quantity.
func update_quote() -> void:
	if field == null or not is_instance_valid(field):
		return
	var item := unit(unit_id)
	var count := int(field.value)
	var cost := cost_for(item, count)
	var short := []
	for resource: String in cost_labels:
		var amount := int(cost.get(resource, 0))
		var have := int(stock().get(resource, 0))
		var label: Label = cost_labels[resource]
		label.text = UiKit.compact(amount)
		label.add_theme_color_override("font_color", Color("#ff7a66") if amount > have else UiKit.IVORY)
		cost_cells[resource].tooltip_text = "%s: %d" % [ui.RESOURCE_NAMES.get(resource, resource), amount]
		if amount > have:
			short.append(str(ui.RESOURCE_NAMES.get(resource, resource)).to_lower())
	if clock != null:
		clock.text = panels.duration(seconds_for(item, count))
	var free := int(ui.state.v6.get("army_capacity", 0)) - int(ui.state.v6.get("army_used", 0))
	var places := count * maxi(1, int(item.get("army_slots", 1)))
	var reason := ""
	if not short.is_empty():
		reason = "Не хватает: " + ", ".join(short) + "."
	elif places > free:
		reason = "В армии свободно %s мест из %s." % [ui.format_balance(maxi(0, free)), ui.format_balance(int(ui.state.v6.get("army_capacity", 0)))]
	if hint != null:
		hint.text = reason if not reason.is_empty() else "Партия до %s · армия %s / %s · ресурсы резервируются, отмена их вернёт." % [
			ui.format_balance(effect(prefix() + "_batch")), ui.format_balance(int(ui.state.v6.get("army_used", 0))), ui.format_balance(int(ui.state.v6.get("army_capacity", 0)))]
		hint.add_theme_color_override("font_color", UiKit.BAD if not reason.is_empty() else UiKit.INK_MUTED)
	if train_button != null and not submitting:
		train_button.disabled = not reason.is_empty()

func lock_panel(item: Dictionary) -> void:
	var card := PanelContainer.new()
	card.name = "RecruitLock"
	card.add_theme_stylebox_override("panel", UiKit.row_style())
	ui.modal_body.add_child(card)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	card.add_child(row)
	var mark := UiKit.lock_icon(46.0)
	mark.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(mark)
	var texts := VBoxContainer.new()
	texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	texts.add_theme_constant_override("separation", 4)
	row.add_child(texts)
	UiKit.label(texts, "Откроется, когда выполнены условия", 20, UiKit.INK, UiKit.LABEL_FONT)
	for need: Array in requirements(item):
		var line := HBoxContainer.new()
		line.add_theme_constant_override("separation", 10)
		texts.add_child(line)
		UiKit.mark(line, "tick" if need[2] else "lozenge", UiKit.GOOD if need[2] else UiKit.BAD, 18.0)
		UiKit.label(line, "%s · уровень %s" % [need[0], ROMAN[int(need[1]) - 1]], 18, UiKit.GOOD if need[2] else UiKit.BAD, null, false)
	var upgrade: Button = ui.button(row, "Улучшить здание", panels.inspect.bind(type if level_of(type) < int(item.get("required_building", 1)) else "B01"))
	upgrade.name = "RecruitUpgrade"
	UiKit.style_button(upgrade, "secondary", 18)
	upgrade.custom_minimum_size = Vector2(220, 52)
	upgrade.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var cost := cost_for(item, 1)
	UiKit.label(ui.modal_body, "Стоимость одного воина и время обучения на нынешнем уровне здания:", 15, UiKit.INK_MUTED)
	var strip := UiKit.cost_strip(ui.modal_body, cost, ui.resource_icons, {}, ui.RESOURCE_NAMES)
	strip.name = "RecruitCost"
	UiKit.timer_pill(ui.modal_body, "Время обучения", panels.duration(seconds_for(item, 1)))

func details_sheet(item: Dictionary) -> void:
	var stats := roster(unit_id)
	var grid := GridContainer.new()
	grid.name = "RecruitStats"
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 28)
	grid.add_theme_constant_override("v_separation", 0)
	ui.modal_body.add_child(grid)
	var rows: Array = []
	if type == "B17":
		rows = [["Урон стене за удар", str(int(item.get("wall_damage_per_strike", 0)))], ["Удар каждые", "%d с" % int(item.get("strike_period_seconds", 0))],
			["Урон обычным войскам", str(int(item.get("normal_troop_damage", 0)))], ["Мест в армии", str(int(item.get("army_slots", 1)))]]
	else:
		rows = [["Атака", str(int(stats.get("attack", 0)))], ["Защита", str(int(stats.get("defense", 0)))],
			["Здоровье", str(int(stats.get("hp", 0)))], ["Скорость", str(stats.get("speed", "—"))],
			["Мощь", str(int(item.get("power_reference", stats.get("power", 0))))], ["Мест в армии", str(int(item.get("army_slots", 1)))]]
	rows.append(["Содержание в час", "нет" if float(item.get("upkeep_per_hour", 0)) <= 0.0 else str(item.upkeep_per_hour)])
	rows.append(["Обучение одного", panels.duration(seconds_for(item, 1))])
	for pair: Array in rows:
		var line := UiKit.stat_row(grid, str(pair[0]), str(pair[1]), "", true)
		line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for key: String in ["strengths", "weakness", "special"]:
		var text := str(stats.get(key, ""))
		if not text.is_empty():
			var caption: String = {"strengths": "Сильные стороны", "weakness": "Слабости", "special": "Особенность"}[key]
			var line := UiKit.label(ui.modal_body, caption + ": " + text, 16, UiKit.INK)
			line.name = "RecruitNote"
	UiKit.label(ui.modal_body, "Требуется: " + " · ".join(requirements(item).map(func(n): return "%s %s" % [n[0], ROMAN[int(n[1]) - 1]])), 15, UiKit.INK_MUTED)

## An empty place in the building's queue: where a new order will appear.
func free_slot(free: int) -> void:
	var card := PanelContainer.new()
	card.name = "RecruitFreeSlot"
	card.add_theme_stylebox_override("panel", UiKit.flat(Color("#5a3c1a12"), Color("#8a6a4055"), 10, Vector2(14, 10)))
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.modal_body.add_child(card)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(row)
	var glass := TextureRect.new()
	glass.texture = UiKit.tex("kit_hourglass")
	glass.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glass.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	glass.custom_minimum_size = Vector2(22, 28)
	glass.modulate = Color(1, 1, 1, 0.55)
	glass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(glass)
	# Orders of a building run one after another (v6/orders.mjs: starts at the queue's end).
	var places := "Свободно мест в очереди: %d из %d" % [free, maxi(1, effect(prefix() + "_orders"))]
	UiKit.label(row, places + (" · обучение начнётся сразу." if orders().is_empty() else " · новое начнётся после текущего."), 16, UiKit.INK_MUTED, null, false)

func queue_card(order: Dictionary) -> void:
	var card := PanelContainer.new()
	card.name = "RecruitOrder"
	card.add_theme_stylebox_override("panel", UiKit.row_style())
	ui.modal_body.add_child(card)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	card.add_child(row)
	var id := str(order.get("unit", "SIEGE-RAM-01" if order.kind == "repair_ram" else ""))
	row.add_child(UiKit.icon_tile(UnitStage.portrait(id, true), 72, "×" + str(int(order.get("quantity", 1)))))
	var middle := VBoxContainer.new()
	middle.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	middle.alignment = BoxContainer.ALIGNMENT_CENTER
	middle.add_theme_constant_override("separation", 6)
	row.add_child(middle)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 10)
	middle.add_child(head)
	var starts := float(order.starts_at) * 1000.0
	var ends := float(order.ends_at) * 1000.0
	var now: float = ui.timer_now()
	var waiting := starts > now
	var name := UiKit.label(head, ("Ремонт тарана" if order.kind == "repair_ram" else "%s × %s" % [unit_name(id), ui.format_balance(int(order.get("quantity", 1)))]), 20, UiKit.INK, UiKit.LABEL_FONT, false)
	name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var left := UiKit.label(head, "", 20, UiKit.BRONZE, UiKit.LABEL_FONT, false)
	left.name = "RecruitTimeLeft"
	ui.bind_countdown(left, "Ожидает" if waiting else "", starts if waiting else ends)
	var bar := UiKit.progress_bar(middle, 0.0 if waiting or ends <= starts else (now - starts) / (ends - starts))
	bar.name = "RecruitProgress"
	if not waiting and ends > now:
		# Smooth fill to the end of the order; no per-frame script.
		var tween := bar.create_tween()
		tween.tween_property(bar, "value", 1.0, (ends - now) / 1000.0)
	var actions := VBoxContainer.new()
	actions.add_theme_constant_override("separation", 6)
	actions.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(actions)
	if order.kind in ["train", "siege"] and not waiting:
		var hurry: Button = ui.button(actions, "Ускорить", panels.speedups.bind(order, panels.services.bind(type)))
		hurry.name = "RecruitSpeedup"
		UiKit.style_button(hurry, "secondary", 18)
		hurry.custom_minimum_size = Vector2(176, 46)
	var stop: Button = ui.button(actions, "Отменить", Callable())
	stop.name = "RecruitCancel"
	UiKit.style_button(stop, "danger", 16)
	stop.custom_minimum_size = Vector2(176, 40)
	stop.pressed.connect(cancel.bind(str(order.id), stop))

# ------------------------------------------------------------------ actions

func pick(id: String) -> void:
	if id == unit_id or not is_open():
		return
	chosen[type] = id
	unit_id = id
	stage.show_unit(id, tier_of(unit(id)), unit_name(id))
	render()

func toggle_details() -> void:
	if not is_open():
		return
	details = not details
	render()

func train() -> void:
	if submitting or train_button == null or train_button.disabled or not is_open():
		return
	# A number typed but not confirmed yet counts (the field still has the focus); the text
	# of a value set by the slider or «Макс» may be refreshed only on the next frame.
	if field.get_line_edit().has_focus():
		field.apply()
	var count := int(field.value)
	var item := unit(unit_id)
	submitting = true
	var button := train_button
	button.disabled = true
	button.text = "Выполняем…"
	var intent := {"kind": "siege" if type == "B17" else "train", "unit": unit_id, "quantity": count, "economy_version": VERSION}
	var view := generation
	var response: Dictionary = await ui.request("command", {"kind": "v6quote", "intent": intent})
	if view != generation or not is_open():
		submitting = false
		return
	if not response.get("ok", false):
		submitting = false
		var reason: Dictionary = response.get("reason", {})
		var text := str(reason.get("message", response.get("error", "Нет ответа сервера")))
		if reason.has("resource"):
			text += ": %s — нужно %s, есть %s" % [ui.RESOURCE_NAMES.get(reason.resource, reason.resource), ui.format_balance(int(reason.get("required", 0))), ui.format_balance(int(reason.get("available", 0)))]
		if is_instance_valid(button):
			button.text = "Обучить" if orders().is_empty() else "В очередь"
			button.disabled = false
		if is_instance_valid(hint):
			hint.text = text
			hint.add_theme_color_override("font_color", UiKit.BAD)
		return
	intent.expected_duration_seconds = int(response.quote.duration_seconds)
	# With a callback, a successful command keeps the window open (main.gd command).
	await ui.command({"kind": "v6", "intent": intent}, stay)
	submitting = false
	if is_open() and view == generation:
		refresh(true)

func cancel(order_id: String, button: Button) -> void:
	if submitting or not is_open():
		return
	if cancel_armed != order_id:
		# Two taps: the first one asks, the second one cancels (within four seconds).
		cancel_armed = order_id
		button.text = "Точно отменить?"
		var weak: WeakRef = weakref(button)
		ui.get_tree().create_timer(4.0).timeout.connect(func():
			var still := weak.get_ref() as Button
			if still != null and cancel_armed == order_id:
				cancel_armed = ""
				still.text = "Отменить")
		return
	submitting = true
	watched.erase(order_id)
	button.disabled = true
	button.text = "Отменяем…"
	await ui.command({"kind": "v6", "intent": {"kind": "cancel", "order_id": order_id, "economy_version": VERSION}}, stay)
	submitting = false
	cancel_armed = ""
	if is_open():
		refresh(true)

func stay() -> void:
	pass

## New server state: celebrate finished orders, rebuild what changed, refresh the rest.
func refresh(force := false) -> void:
	if not is_open() or submitting:
		return
	for id: String in watched:
		var still: Array = ui.state.v6.orders.filter(func(o): return o.id == id)
		if not still.is_empty() and still[0].status == "completed":
			if watched[id].kind != "repair_ram":
				celebrate(str(watched[id].unit), int(watched[id].quantity))
	if force or signature() != shown_signature:
		var keep_scroll: int = ui.modal_scroll.scroll_vertical
		build_rail()
		render()
		ui.modal_scroll.set_deferred("scroll_vertical", keep_scroll)
	else:
		update_quote()

## Short, non-blocking: a gold banner over the stage, a burst of sparks, the card pulses.
func celebrate(id: String, count: int) -> void:
	if not is_instance_valid(stage):
		return
	stage.celebrate("Обучено: %s × %s" % [unit_name(id), ui.format_balance(count)])
	var card: BaseButton = cards.get(id)
	if is_instance_valid(card):
		card.pivot_offset = card.size * 0.5
		var pulse := card.create_tween()
		pulse.tween_property(card, "scale", Vector2(1.06, 1.06), 0.12).set_trans(Tween.TRANS_SINE)
		pulse.tween_property(card, "scale", Vector2.ONE, 0.22).set_trans(Tween.TRANS_SINE)
