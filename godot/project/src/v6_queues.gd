extends RefCounted
## Settlement queues and speed-ups (premium UI stage 4a, ui_premium/STAGE4A.md).
##
## One full-screen window for every running job of the settlement. Left, on dark oak: the
## queues under section bands (the builders, each training building, research, healing,
## marches), each lane with a portrait or an emblem, a bar with the time left, or «Свободно».
## A tap selects a lane. Right: the timer band of the selected job, «Быстрое использование»
## (the owned items that finish the job with the least waste, or shorten it the most), one
## row per speed-up item of the queue with its painted tier tile, then the reserve and the
## cancel of the job. A free lane offers what starts work there.
##
## Items are spent through the server's own speed-up command, one at a time, each with the
## order's current end (expectedEndsAt): a repeated or stale use is refused by the server
## (TIMER_CHANGED) rather than applied twice, and a retried request keeps its idempotency
## key (main.gd command). Only the last item of a set can outlast the job, and only that one
## is sent with confirmUnused.

const UiKit = preload("res://src/ui_kit.gd")
const UnitStage = preload("res://src/unit_stage.gd")
const VERSION := "DRENOVAR-V6-C1.0"
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
const TRAINING := ["B11", "B12", "B13", "B17"]
const EMBLEMS := {"B11": "kit_emb_inf", "B12": "kit_emb_bow", "B13": "kit_emb_horse", "B17": "kit_emb_ram",
	"B15": "kit_emb_book", "B16": "kit_emb_heal"}
const KIND_NAMES := {"construction": "Строительство", "train": "Обучение", "heal": "Лечение", "research": "Исследование",
	"siege": "Сборка таранов", "repair_ram": "Ремонт тарана", "repair_wall": "Ремонт стены"}
## Order kinds the server speeds up, and the item queue each one takes.
const SPEEDABLE := {"construction": "construction", "train": "training", "siege": "training"}
const FAMILIES := {"R_BUILD": "Организация строительства", "R_ECON": "Организация производства",
	"R_ATTACK": "Тактика наступления", "R_DEFENCE": "Тактика защиты"}
## How far below the greedy count the least-waste search looks at each item size; three
## already matches an exhaustive search (ui_premium/STAGE4A.md), four keeps a margin.
const SEARCH_WINDOW := 4

var panels
var ui
var generation := -1
var selected := ""
var back := Callable()
var lanes: Array = []
var lane_controls := {}
var rail: VBoxContainer
var rail_scroll: ScrollContainer
var band: TimerBand
var ticker: Timer
var applying := false
var armed_item := ""
var note: Label
var shown_signature := ""
var focus_order := {}
var finish_requested := {}
var finished_shown := {}
var last_open_usec := 0
var plan := {}

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

func is_open() -> bool:
	var modal: Variant = ui.get("modal")
	return generation == ui.modal_generation and (modal == null or modal.visible) and is_instance_valid(rail)

# ------------------------------------------------------------------ data

func v6() -> Dictionary:
	var value: Variant = ui.state.get("v6")
	return value if value is Dictionary else {}

func pending_orders() -> Array:
	var list: Array = v6().get("orders", []).filter(func(o): return o.get("status", "") == "pending")
	list.sort_custom(func(a, b): return float(a.get("starts_at", 0)) < float(b.get("starts_at", 0)))
	return list

func level_of(type: String) -> int:
	for b: Dictionary in v6().get("buildings", []):
		if str(b.get("type", "")) == type:
			return int(b.get("level", 0))
	return 0

func building_name(type: String) -> String:
	return str(panels.row_for(type, 1).get("name_ru", type))

func unit_name(id: String) -> String:
	for unit: Dictionary in panels.catalogue.get("units", []):
		if str(unit.get("unit_id", "")) == id:
			return str(unit.get("name_ru", id))
	var roster: Dictionary = ui.data.get("units", {}).get(id, {}) if ui.get("data") is Dictionary else {}
	return str(roster.get("name", id))

func builders() -> int:
	if panels.build != null:
		return maxi(1, int(panels.build.builder_use()[1]))
	return 1

func now_ms() -> float:
	return ui.timer_now()

func ends_ms(order: Dictionary) -> float:
	if order.has("ends_at"):
		return float(order.ends_at) * 1000.0
	return float(order.get("finish_ms", 0.0))

func starts_ms(order: Dictionary) -> float:
	if order.has("starts_at"):
		return float(order.starts_at) * 1000.0
	return float(order.get("start_ms", 0.0))

func order_by_id(id: String) -> Dictionary:
	for order: Dictionary in v6().get("orders", []):
		if str(order.get("id", "")) == id:
			return order
	if str(focus_order.get("id", "")) == id:
		return focus_order
	return {}

## The lanes of the rail, in order: builders, troops (each training building), research,
## healing, marches. Each lane carries its running order (or none: «Свободно»).
func collect_lanes() -> Array:
	var list: Array = []
	var pending := pending_orders()
	var used := {}
	var works: Array = pending.filter(func(o): return o.get("kind", "") in ["construction", "repair_wall"])
	for index in maxi(builders(), works.size()):
		var order: Dictionary = works[index] if index < works.size() else {}
		var lane := {"key": "build-%d" % index, "section": "Строительство", "emblem": "kit_emb_craft", "order": order, "waiting": 0,
			"title": "Строитель %d" % (index + 1), "subtitle": "", "free": "Свободен", "cta": "Строить", "action": panels.catalog}
		if not order.is_empty():
			used[order.id] = true
			var type := str(order.get("building", ""))
			lane.face = ui.v6_card(type)
			if order.kind == "repair_wall":
				lane.title = building_name(type)
				lane.subtitle = "Ремонт стены"
			else:
				var target := int(order.get("target", 1))
				lane.title = "%s → %s" % [building_name(type), ROMAN[clampi(target, 1, 11) - 1]] if target > 1 else building_name(type)
				lane.subtitle = "Улучшение" if target > 1 else "Новое здание"
		list.append(lane)
	for type: String in TRAINING:
		if level_of(type) <= 0:
			continue
		var of_type: Array = pending.filter(func(o): return str(o.get("building", "")) == type and o.get("kind", "") in ["train", "siege", "repair_ram"])
		var lane := {"key": type, "section": "Войска", "emblem": EMBLEMS[type], "order": {}, "waiting": 0, "title": building_name(type),
			"subtitle": "", "free": "Свободно", "cta": "Обучить", "action": panels.services.bind(type)}
		if not of_type.is_empty():
			var order: Dictionary = of_type[0]
			lane.order = order
			lane.waiting = of_type.size() - 1
			for item: Dictionary in of_type:
				used[item.id] = true
			if order.kind == "repair_ram":
				lane.subtitle = "Ремонт тарана"
				lane.face = UnitStage.portrait("SIEGE-RAM-01", true)
			else:
				lane.subtitle = "%s × %s" % [unit_name(str(order.get("unit", ""))), ui.format_balance(int(order.get("quantity", 1)))]
				lane.face = UnitStage.portrait(str(order.get("unit", "")), true)
		list.append(lane)
	for pair: Array in [["B15", "research", "Исследования", "Исследовать"], ["B16", "heal", "Лечение", "Лечить"]]:
		var type: String = pair[0]
		var running: Array = pending.filter(func(o): return o.get("kind", "") == pair[1])
		if level_of(type) <= 0 and running.is_empty():
			continue
		var lane := {"key": type, "section": pair[2], "emblem": EMBLEMS[type], "order": {}, "waiting": 0, "title": building_name(type),
			"subtitle": "", "free": "Свободно", "cta": pair[3], "action": panels.services.bind(type)}
		if not running.is_empty():
			var order: Dictionary = running[0]
			lane.order = order
			lane.waiting = running.size() - 1
			for item: Dictionary in running:
				used[item.id] = true
			if pair[1] == "research":
				lane.subtitle = "%s → %s" % [FAMILIES.get(str(order.get("family", "")), str(order.get("family", ""))), ROMAN[clampi(int(order.get("target", 1)), 1, 11) - 1]]
			else:
				var count := 0
				for id: String in order.get("units", {}):
					count += int(order.units[id])
				lane.subtitle = "Лечение · %s воинов" % ui.format_balance(count)
		list.append(lane)
	for army: Dictionary in ui.state.get("armies", []):
		if str(army.get("owner", ui.state.get("playerId", ""))) != str(ui.state.get("playerId", "")) or str(army.get("status", "")) == "returned":
			continue
		var finish: Variant = ui.march_finish(army) if ui.has_method("march_finish") else null
		var march := {"id": str(army.get("id", "")), "kind": "march", "start_ms": float(army.get("departedAt", army.get("startedAt", 0.0))),
			"finish_ms": float(finish) if finish != null else 0.0, "army": army}
		list.append({"key": "march-" + str(army.get("id", "")), "section": "Походы", "emblem": "kit_emb_march", "order": march, "waiting": 0,
			"title": str(army.get("name", "Отряд")), "subtitle": {"outbound": "В пути к цели", "fighting": "В бою", "returning": "Возвращается"}.get(str(army.status), str(army.status)),
			"free": "", "cta": "", "action": Callable()})
	# Anything else still running (and the order a caller asked for) gets a lane of its own.
	var extra: Array = pending.filter(func(o): return not used.has(o.id))
	if not focus_order.is_empty() and not used.has(focus_order.get("id", "")) and not extra.any(func(o): return o.id == focus_order.get("id", "")):
		extra.append(focus_order)
	for order: Dictionary in extra:
		var type := str(order.get("building", ""))
		list.insert(0, {"key": "order-" + str(order.id), "section": "Работы", "emblem": EMBLEMS.get(type, "kit_emb_craft"), "order": order, "waiting": 0,
			"title": building_name(type) if not type.is_empty() else KIND_NAMES.get(str(order.get("kind", "")), "Работа"),
			"subtitle": KIND_NAMES.get(str(order.get("kind", "")), ""), "free": "", "cta": "", "action": Callable(), "face": ui.v6_card(type) if not type.is_empty() else null})
	return list

func lane_by_key(key: String) -> Dictionary:
	for lane: Dictionary in lanes:
		if lane.key == key:
			return lane
	return lanes[0] if not lanes.is_empty() else {}

func lane_of_order(id: String) -> String:
	for lane: Dictionary in lanes:
		if str(lane.order.get("id", "")) == id:
			return lane.key
	return ""

func signature() -> String:
	var parts: Array = [selected, ui.state.get("items", {})]
	for lane: Dictionary in lanes:
		parts.append([lane.key, lane.order.get("id", ""), lane.order.get("ends_at", lane.order.get("finish_ms", 0)), lane.waiting])
	return str(parts)

# ------------------------------------------------------------------ speed-up items

## Items of a queue from the server catalogue, longest first: [[id, seconds, owned], ...].
func items_of(queue: String) -> Array:
	var catalog: Dictionary = ui.speed_catalog() if ui.has_method("speed_catalog") else {}
	var list: Array = []
	for id: String in catalog:
		if str(catalog[id].get("kind", "")) == queue:
			list.append([id, int(catalog[id].seconds), int(ui.state.get("items", {}).get(id, 0))])
	list.sort_custom(func(a, b): return a[1] > b[1])
	return list

## The owned items that finish `remaining` seconds with the least waste (then the fewest
## items); when everything owned falls short, all of it (the most it can shorten).
## items: [[id, seconds, owned], ...] longest first. Returns {"use": [[id, n], ...],
## "seconds": total, "finishes": bool, "waste": seconds, "count": items}.
static func least_waste(items: Array, remaining: int) -> Dictionary:
	var owned: Array = items.filter(func(i): return int(i[2]) > 0 and int(i[1]) > 0)
	var result := {"use": [], "seconds": 0, "finishes": remaining <= 0, "waste": 0, "count": 0}
	if remaining <= 0 or owned.is_empty():
		return result
	var total := 0
	for item: Array in owned:
		total += int(item[1]) * int(item[2])
	if total <= remaining:
		for item: Array in owned:
			result.use.append([item[0], int(item[2])])
			result.count += int(item[2])
		result.seconds = total
		result.finishes = total == remaining
		return result
	var suffix: Array = []
	suffix.resize(owned.size() + 1)
	suffix[owned.size()] = 0
	for index in range(owned.size() - 1, -1, -1):
		suffix[index] = suffix[index + 1] + int(owned[index][1]) * int(owned[index][2])
	var best := {"sum": -1, "count": 0, "pick": []}
	var pick: Array = []
	pick.resize(owned.size())
	pick.fill(0)
	_search(owned, suffix, remaining, 0, 0, 0, pick, best)
	for index in owned.size():
		if int(best.pick[index]) > 0:
			result.use.append([owned[index][0], int(best.pick[index])])
	result.seconds = int(best.sum)
	result.count = int(best.count)
	result.finishes = true
	result.waste = int(best.sum) - remaining
	return result

static func _search(owned: Array, suffix: Array, remaining: int, index: int, total: int, count: int, pick: Array, best: Dictionary) -> void:
	if total >= remaining:
		if best.sum < 0 or total < best.sum or (total == best.sum and count < best.count):
			best.sum = total
			best.count = count
			best.pick = pick.duplicate()
		return
	if index >= owned.size() or total + int(suffix[index]) < remaining:
		return
	var seconds := int(owned[index][1])
	var have := int(owned[index][2])
	var greedy := mini(have, (remaining - total) / seconds)
	for n in range(mini(have, greedy + 1), maxi(0, greedy - SEARCH_WINDOW) - 1, -1):
		pick[index] = n
		_search(owned, suffix, remaining, index + 1, total + n * seconds, count + n, pick, best)
	pick[index] = 0

## The plan as single uses, longest first: only the last one can outlast the job.
static func sequence(plan_value: Dictionary) -> Array:
	var list: Array = []
	for entry: Array in plan_value.get("use", []):
		for i in int(entry[1]):
			list.append(str(entry[0]))
	return list

static func tier_of(seconds: int) -> int:
	if seconds <= 60:
		return 1
	if seconds <= 300:
		return 2
	if seconds <= 900:
		return 3
	if seconds <= 10800:
		return 4
	return 5

static func span(seconds: int) -> String:
	seconds = maxi(0, seconds)
	if seconds >= 86400:
		var hours := (seconds % 86400) / 3600
		return "%d д %d ч" % [seconds / 86400, hours] if hours else "%d д" % (seconds / 86400)
	if seconds >= 3600:
		var minutes := (seconds % 3600) / 60
		return "%d ч %d мин" % [seconds / 3600, minutes] if minutes else "%d ч" % (seconds / 3600)
	if seconds >= 60:
		var rest := seconds % 60
		return "%d мин %d с" % [seconds / 60, rest] if rest else "%d мин" % (seconds / 60)
	return "%d с" % seconds

static func short_span(seconds: int) -> String:
	if seconds >= 3600 and seconds % 3600 == 0:
		return "%d ч" % (seconds / 3600)
	if seconds >= 60 and seconds % 60 == 0:
		return "%d мин" % (seconds / 60)
	return span(seconds)

# ------------------------------------------------------------------ window

## Opens the window (or switches the open one): `order` selects the lane of that job,
## `back` is the window to return to when the job finishes (the recruitment window).
func open(order := {}, back_action := Callable(), title := "Очереди поселения") -> void:
	var started := Time.get_ticks_usec()
	back = back_action
	focus_order = order.duplicate() if not order.is_empty() else {}
	armed_item = ""
	lanes = collect_lanes()
	var wanted := lane_of_order(str(order.get("id", ""))) if not order.is_empty() else ""
	if not wanted.is_empty():
		selected = wanted
	elif not (is_open() and lanes.any(func(l): return l.key == selected)):
		# A fresh window starts on the first running job (or the first lane).
		selected = ""
		for lane: Dictionary in lanes:
			if not lane.order.is_empty() and selected.is_empty():
				selected = lane.key
		if selected.is_empty() and not lanes.is_empty():
			selected = lanes[0].key
	var eyebrow := "УСКОРЕНИЕ РАБОТ" if not order.is_empty() else "ЗАКАЗЫ И УСКОРЕНИЕ"
	if is_open():
		ui.set_modal_heading(title, eyebrow)
	else:
		ui.open_modal(title, "full", eyebrow)
		generation = ui.modal_generation
		build_frame()
	build_rail()
	render()
	last_open_usec = Time.get_ticks_usec() - started

func build_frame() -> void:
	var hero: Control = ui.modal_hero
	var backdrop := Panel.new()
	backdrop.name = "QueueRailBack"
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.add_theme_stylebox_override("panel", rail_back_style())
	hero.add_child(backdrop)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rail_scroll = ScrollContainer.new()
	rail_scroll.name = "QueueRailScroll"
	rail_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	rail_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	rail_scroll.add_to_group("panel_scroll")
	hero.add_child(rail_scroll)
	rail_scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rail_scroll.offset_left = 18
	rail_scroll.offset_right = -12
	rail_scroll.offset_top = 26
	rail_scroll.offset_bottom = -12
	rail = VBoxContainer.new()
	rail.name = "QueueRail"
	rail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rail.add_theme_constant_override("separation", 6)
	rail_scroll.add_child(rail)
	ticker = Timer.new()
	ticker.wait_time = 1.0
	ticker.autostart = true
	ticker.timeout.connect(tick)
	rail_scroll.add_child(ticker)
	ui.modal_hero_share = 0.35
	if ui.has_method("arrange_modal"):
		ui.arrange_modal()

static var back_style: StyleBoxTexture

static func rail_back_style() -> StyleBoxTexture:
	if back_style == null:
		back_style = UiKit.nine("kit_body_dark", Vector4.ZERO, Vector4.ZERO, true).duplicate()
		back_style.modulate_color = Color(1.0, 0.94, 0.86)
	return back_style

func build_rail() -> void:
	for child in rail.get_children():
		rail.remove_child(child)
		child.queue_free()
	lane_controls.clear()
	var section := ""
	for lane: Dictionary in lanes:
		if lane.section != section:
			section = lane.section
			var header := RailBand.new()
			header.text = section
			header.emblem = UiKit.tex({"Строительство": "kit_emb_craft", "Войска": "kit_emb_inf", "Исследования": "kit_emb_book",
				"Лечение": "kit_emb_heal", "Походы": "kit_emb_march"}.get(section, "kit_emb_craft"))
			header.custom_minimum_size.y = 34
			header.mouse_filter = Control.MOUSE_FILTER_IGNORE
			rail.add_child(header)
		var control := QueueLane.new()
		control.name = "Lane" + str(lane.key)
		control.custom_minimum_size.y = 78
		control.focus_mode = Control.FOCUS_NONE
		control.tooltip_text = str(lane.title)
		control.accessibility_name = "%s · %s" % [lane.title, lane.subtitle if not lane.order.is_empty() else lane.free]
		control.clock = ui.timer_now
		apply_lane(control, lane)
		control.pressed.connect(select.bind(str(lane.key)))
		rail.add_child(control)
		lane_controls[lane.key] = control
	follow_later()

func apply_lane(control: QueueLane, lane: Dictionary) -> void:
	control.title = str(lane.title)
	control.subtitle = str(lane.subtitle)
	control.free_text = str(lane.free)
	control.face = lane.get("face")
	control.emblem = UiKit.tex(str(lane.emblem))
	control.selected = lane.key == selected
	control.waiting = int(lane.waiting)
	control.busy = not lane.order.is_empty()
	control.starts = starts_ms(lane.order) if control.busy else 0.0
	control.ends = ends_ms(lane.order) if control.busy else 0.0
	control.queue_redraw()

func follow_later() -> void:
	var tree: SceneTree = ui.get_tree()
	if tree == null:
		return
	await tree.process_frame
	follow_selected()

func follow_selected() -> void:
	if not is_instance_valid(rail_scroll) or not lane_controls.has(selected) or not is_instance_valid(lane_controls[selected]):
		return
	var lane: Control = lane_controls[selected]
	var top := lane.position.y
	var index := lane.get_index()
	if index > 0 and rail.get_child(index - 1) is RailBand:
		top = rail.get_child(index - 1).position.y
	var view := rail_scroll.size.y
	if top < rail_scroll.scroll_vertical:
		rail_scroll.scroll_vertical = int(top)
	elif lane.position.y + lane.size.y > rail_scroll.scroll_vertical + view:
		rail_scroll.scroll_vertical = int(lane.position.y + lane.size.y - view)

func select(key: String) -> void:
	if not is_open() or applying or key == selected:
		return
	selected = key
	armed_item = ""
	for lane_key: String in lane_controls:
		var control: QueueLane = lane_controls[lane_key]
		if is_instance_valid(control):
			control.selected = lane_key == key
			control.queue_redraw()
	render()
	if ui.get("modal_scroll") != null:
		ui.modal_scroll.scroll_vertical = 0

# ------------------------------------------------------------------ right side

func render() -> void:
	ui.empty(ui.modal_body)
	ui.empty(ui.modal_tools)
	note = null
	plan = {}
	shown_signature = signature()
	var lane := lane_by_key(selected)
	ui.modal_tools.show()
	ui.modal_tools.add_theme_constant_override("separation", 10)
	if back.is_valid():
		var home: Button = ui.button(ui.modal_tools, "Вернуться к обучению", back)
		home.name = "SpeedBack"
		UiKit.style_button(home, "tertiary", 17)
		home.custom_minimum_size = Vector2(236, 50)
		home.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	band = TimerBand.new()
	band.name = "QueueBand"
	band.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	band.custom_minimum_size.y = 56
	band.clock = ui.timer_now
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.modal_tools.add_child(band)
	if lane.is_empty():
		band.title = "Очередей пока нет"
		return
	var order: Dictionary = lane.order
	band.title = str(lane.title) if lane.subtitle.is_empty() or order.is_empty() else "%s · %s" % [lane.title, lane.subtitle]
	if order.is_empty():
		band.title = "%s · %s" % [lane.title, lane.free]
		free_panel(lane)
		return
	band.starts = starts_ms(order)
	band.ends = ends_ms(order)
	band.waiting = int(lane.waiting)
	var kind := str(order.get("kind", ""))
	if SPEEDABLE.has(kind) and starts_ms(order) <= now_ms():
		speed_rows(order)
	elif SPEEDABLE.has(kind):
		info_row("Работа ждёт своей очереди", "Ускорители действуют на работу, которая уже идёт. Эта начнётся после текущей.", lane)
	elif kind == "march":
		march_rows(lane)
		return
	else:
		var text: String = {"research": "Исследования ускоряет уровень Военной академии. Предметов ускорения для них нет.",
			"heal": "Лечение ускоряет уровень лазарета. Предметов ускорения для него нет.",
			"repair_ram": "Ремонт идёт в осадной мастерской. Предметов ускорения для него нет.",
			"repair_wall": "Ремонт стены ведут строители. Предметов ускорения для него нет."}.get(kind, "Для этой работы предметов ускорения нет.")
		info_row(KIND_NAMES.get(kind, "Работа"), text, lane)
	order_footer(order)

func speed_rows(order: Dictionary) -> void:
	var queue: String = SPEEDABLE[str(order.kind)]
	var items := items_of(queue)
	var remaining := ceili((ends_ms(order) - now_ms()) / 1000.0)
	plan = least_waste(items, remaining)
	var quick := SpeedRow.new()
	quick.name = "QuickUse"
	quick.quick = true
	quick.title = "Быстрое использование"
	var owned: Array = items.filter(func(i): return int(i[2]) > 0)
	if owned.is_empty():
		quick.text = "Ускорителей этой очереди нет. Их дают награды целей и походов."
	elif plan.finishes:
		quick.text = "%s — закончит работу%s" % [plan_text(plan, items), "" if int(plan.waste) <= 0 else ", пропадёт %s" % span(int(plan.waste))]
	else:
		quick.text = "%s — сократит на %s" % [plan_text(plan, items), span(int(plan.seconds))]
	quick.stack = []
	for entry: Array in plan.get("use", []):
		for item: Array in items:
			if item[0] == entry[0]:
				quick.stack.append(item_texture(queue, int(item[1])))
	if quick.stack.is_empty() and not items.is_empty():
		quick.stack.append(item_texture(queue, int(items[0][1])))
	ui.modal_body.add_child(quick)
	if not owned.is_empty():
		var apply := quick.add_action("Применить", "primary", Vector2(206, 56))
		apply.name = "QuickApply"
		apply.pressed.connect(func(): use_sequence(sequence(plan), apply))
	note = Label.new()
	note.name = "SpeedNote"
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.add_theme_color_override("font_color", UiKit.WARN)
	note.add_theme_font_size_override("font_size", 16)
	note.visible = false
	ui.modal_body.add_child(note)
	var grid := VBoxContainer.new()
	grid.name = "SpeedItems"
	grid.add_theme_constant_override("separation", 8)
	ui.modal_body.add_child(grid)
	var noun := "строительства" if queue == "construction" else "обучения"
	for item: Array in items:
		var row := SpeedRow.new()
		row.name = "Item_" + str(item[0])
		row.icon = item_texture(queue, int(item[1]))
		row.duration = short_span(int(item[1]))
		row.title = "Ускорение %s · %s" % [noun, short_span(int(item[1]))]
		row.text = "Сокращает любую работу %s на %s." % [noun, short_span(int(item[1]))]
		row.count = int(item[2])
		row.count_text = "В наличии: %s" % ui.format_balance(int(item[2])) if int(item[2]) > 0 else "Нет в наличии · даются в наградах"
		grid.add_child(row)
		if int(item[2]) > 0:
			var id := str(item[0])
			var use := row.add_action("Использовать", "secondary", Vector2(190, 52))
			use.pressed.connect(use_single.bind(id, int(item[1]), use))

func plan_text(value: Dictionary, items: Array) -> String:
	var parts: Array[String] = []
	for entry: Array in value.get("use", []):
		for item: Array in items:
			if item[0] == entry[0]:
				parts.append("%s × %d" % [short_span(int(item[1])), int(entry[1])])
	return ", ".join(parts)

func item_texture(queue: String, seconds: int) -> Texture2D:
	return UiKit.tex("kit_item_%s_%d" % ["build" if queue == "construction" else "train", tier_of(seconds)])

func info_row(title: String, text: String, lane: Dictionary) -> void:
	var row := SpeedRow.new()
	row.name = "QueueInfo"
	row.title = title
	row.text = text
	row.icon = lane.get("face") if lane.get("face") != null else UiKit.tex(str(lane.emblem))
	row.round_icon = lane.get("face") == null
	ui.modal_body.add_child(row)

func free_panel(lane: Dictionary) -> void:
	var row := SpeedRow.new()
	row.name = "QueueFree"
	row.title = "%s · %s" % [lane.title, lane.free]
	row.text = {"Строить": "Строитель ждёт работы: начните стройку или улучшение.", "Обучить": "Здание не занято: наберите новых воинов.",
		"Исследовать": "Академия не занята: начните исследование.", "Лечить": "Лазарет не занят. Раненых можно лечить здесь."}.get(str(lane.cta), "Очередь свободна.")
	row.icon = UiKit.tex(str(lane.emblem))
	row.round_icon = true
	ui.modal_body.add_child(row)
	if lane.action.is_valid():
		var go := row.add_action(str(lane.cta), "primary", Vector2(206, 56))
		go.name = "QueueStart"
		var action: Callable = lane.action
		go.pressed.connect(func(): action.call())

func march_rows(lane: Dictionary) -> void:
	var army: Dictionary = lane.order.get("army", {})
	info_row(str(lane.title), "%s. Походы не ускоряются предметами; отозвать отряд можно в окне армии." % lane.subtitle, lane)
	var actions := HBoxContainer.new()
	actions.alignment = BoxContainer.ALIGNMENT_CENTER
	actions.add_theme_constant_override("separation", 14)
	ui.modal_body.add_child(actions)
	if ui.has_method("focus_army"):
		UiKit.style_button(ui.button(actions, "Показать отряд", ui.focus_army.bind(army)), "secondary", 18).custom_minimum_size = Vector2(230, 50)
	UiKit.style_button(ui.button(actions, "Армия", panels.army), "tertiary", 18).custom_minimum_size = Vector2(170, 50)

## The reserve of the job and its cancel (the server refunds the reserve of the undone part).
func order_footer(order: Dictionary) -> void:
	var escrow: Dictionary = order.get("escrow", {})
	if escrow.values().any(func(v): return int(v) > 0):
		UiKit.label(ui.modal_body, "Резерв заказа — вернётся при отмене:", 16, UiKit.INK_MUTED)
		UiKit.cost_strip(ui.modal_body, escrow, ui.resource_icons, {}, ui.RESOURCE_NAMES)
	var cancel: Button = panels.work_button(ui.modal_body, "Отменить работу", cancel_order.bind(str(order.id)))
	cancel.name = "QueueCancel"
	UiKit.style_button(cancel, "danger", 18)
	cancel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	cancel.custom_minimum_size = Vector2(280, 50)

func cancel_order(order_id: String) -> void:
	var intent := {"kind": "cancel", "order_id": order_id, "economy_version": VERSION}
	var view := generation
	applying = true
	var success: bool = await ui.command({"kind": "v6", "intent": intent}, stay)
	applying = false
	if success and view == generation and is_open():
		refresh(true)

func stay() -> void:
	pass

# ------------------------------------------------------------------ using items

func use_single(item_id: String, seconds: int, button: Button) -> void:
	if applying or not is_open():
		return
	var order: Dictionary = order_by_id(str(lane_by_key(selected).order.get("id", "")))
	var remaining := (ends_ms(order) - now_ms()) / 1000.0
	if remaining > 0.0 and seconds > remaining and armed_item != item_id:
		# Two taps when an item outlasts the job: the first one says what is lost.
		armed_item = item_id
		button.text = "Подтвердить"
		if is_instance_valid(note):
			note.text = "Остаток %s пропадёт. Нажмите ещё раз, чтобы использовать." % span(ceili(seconds - remaining))
			note.visible = true
		return
	await use_sequence([item_id], button)

## Sends the uses one by one, each with the order's current end; stops at the first refusal.
func use_sequence(items: Array, button: Button) -> void:
	if applying or items.is_empty() or not is_open():
		return
	var lane := lane_by_key(selected)
	var order_id := str(lane.order.get("id", ""))
	var queue: String = SPEEDABLE.get(str(lane.order.get("kind", "")), "")
	if order_id.is_empty() or queue.is_empty():
		return
	applying = true
	var view := generation
	var disabled: Array = []
	for root: Node in [ui.modal_body, ui.modal_tools]:
		for item: Node in root.find_children("*", "Button", true, false):
			if item != button and item.name != "SpeedBack":
				disabled.append([item, item.disabled])
				item.disabled = true
	button.disabled = true
	var catalog: Dictionary = ui.speed_catalog() if ui.has_method("speed_catalog") else {}
	var done := 0
	var failed := false
	for item_id: String in items:
		var order := order_by_id(order_id)
		if order.is_empty() or str(order.get("status", "pending")) != "pending":
			break
		var remaining := ends_ms(order) - now_ms()
		if remaining <= 0.0:
			break
		if is_instance_valid(button):
			button.text = "Применяем %d из %d…" % [done + 1, items.size()] if items.size() > 1 else "Выполняем…"
		var seconds := int(catalog.get(item_id, {}).get("seconds", 0))
		var body := {"kind": "speedup", "queue": queue, "item": item_id, "orderId": order_id,
			"expectedEndsAt": ends_ms(order), "confirmUnused": float(seconds) * 1000.0 > remaining}
		var success: bool = await ui.command(body, stay)
		if not success:
			failed = true
			break
		done += 1
		if view != generation or not is_open():
			break
		# Instant feedback after each use: the bar jumps, the count goes down.
		var current := order_by_id(order_id)
		if is_same(current, focus_order) and seconds > 0:
			focus_order.ends_at = float(focus_order.get("ends_at", 0)) - float(seconds)
		update_live()
	applying = false
	armed_item = ""
	for entry: Array in disabled:
		if is_instance_valid(entry[0]):
			entry[0].disabled = entry[1]
	if view != generation or not is_open():
		return
	var after := order_by_id(order_id)
	if not failed and (after.is_empty() or str(after.get("status", "pending")) != "pending" or ends_ms(after) <= now_ms()):
		finished(order_id)
		return
	refresh(true)

## Bar, band and counts after a use, without rebuilding the window.
func update_live() -> void:
	lanes = collect_lanes()
	for lane: Dictionary in lanes:
		if lane_controls.has(lane.key) and is_instance_valid(lane_controls[lane.key]):
			apply_lane(lane_controls[lane.key], lane)
	var lane := lane_by_key(selected)
	if is_instance_valid(band) and not lane.order.is_empty():
		band.starts = starts_ms(lane.order)
		band.ends = ends_ms(lane.order)
		band.queue_redraw()
	for row: Node in ui.modal_body.find_children("Item_*", "", true, false):
		var id := str(row.name).trim_prefix("Item_")
		row.count = int(ui.state.get("items", {}).get(id, 0))
		row.count_text = "В наличии: %s" % ui.format_balance(row.count) if row.count > 0 else "Нет в наличии · даются в наградах"
		row.queue_redraw()

## The job is done: «Закончено» on the band and the lane, then back to the window it came
## from (the recruitment window), or the next state of the queues.
func finished(order_id: String) -> void:
	finished_shown[order_id] = true
	if is_instance_valid(band):
		band.done = true
		band.queue_redraw()
		band.pivot_offset = band.size * 0.5
		var pulse := band.create_tween()
		pulse.tween_property(band, "scale", Vector2(1.03, 1.03), 0.12).set_trans(Tween.TRANS_SINE)
		pulse.tween_property(band, "scale", Vector2.ONE, 0.2).set_trans(Tween.TRANS_SINE)
	var key := lane_of_order(order_id)
	if lane_controls.has(key) and is_instance_valid(lane_controls[key]):
		lane_controls[key].done = true
		lane_controls[key].queue_redraw()
	var view := generation
	var tree: SceneTree = ui.get_tree()
	if tree == null:
		return
	await tree.create_timer(0.9).timeout
	if view != generation or not is_open():
		return
	if ui.has_method("ensure_v6_ready"):
		await ui.ensure_v6_ready(true)
	if view != generation or not is_open():
		return
	if back.is_valid():
		back.call()
	else:
		refresh(true)

# ------------------------------------------------------------------ live updates

## Once a second: lanes and band redraw; a job that ran out asks the server for the new
## state once (the order completes there).
func tick() -> void:
	if not is_open():
		return
	for key: String in lane_controls:
		var control: QueueLane = lane_controls[key]
		if is_instance_valid(control) and control.busy:
			control.queue_redraw()
	if is_instance_valid(band):
		band.queue_redraw()
	if applying:
		return
	for lane: Dictionary in lanes:
		var order: Dictionary = lane.order
		if order.is_empty() or str(order.get("kind", "")) == "march":
			continue
		var id := str(order.get("id", ""))
		if ends_ms(order) <= now_ms() and not finish_requested.has(id):
			finish_requested[id] = true
			if ui.has_method("ensure_v6_ready"):
				ui.ensure_v6_ready(true)

## New server state (v6_panels.state_changed): rebuild what changed.
func refresh(force := false) -> void:
	if not is_open() or applying:
		return
	lanes = collect_lanes()
	if not lanes.any(func(l): return l.key == selected):
		selected = lanes[0].key if not lanes.is_empty() else ""
	if force or signature() != shown_signature:
		var keep: int = ui.modal_scroll.scroll_vertical if ui.get("modal_scroll") != null else 0
		var keep_rail := rail_scroll.scroll_vertical
		build_rail()
		render()
		rail_scroll.set_deferred("scroll_vertical", keep_rail)
		if ui.get("modal_scroll") != null:
			ui.modal_scroll.set_deferred("scroll_vertical", keep)

# ------------------------------------------------------------------ drawn controls

## A lane of the rail in one drawn node: oak plate in a bronze frame (gold and lit when
## selected), a medallion with the portrait or the emblem, title, what runs, and a bar with
## the time left; «Свободно» in green when nothing runs.
class QueueLane extends Button:
	var title := ""
	var subtitle := ""
	var free_text := ""
	var face: Texture2D
	var emblem: Texture2D
	var selected := false
	var busy := false
	var done := false
	var waiting := 0
	var starts := 0.0
	var ends := 0.0
	var clock: Callable
	static var styles := {}

	func _init() -> void:
		flat = true
		text = ""
		mouse_filter = Control.MOUSE_FILTER_STOP

	static func style(key: String) -> StyleBox:
		if not styles.has(key):
			match key:
				"fill":
					styles[key] = UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), Color("#4a3220"))
				"fill_on":
					styles[key] = UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), Color("#7a5228"))
				"frame":
					styles[key] = UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color(0.9, 0.82, 0.7))
				"frame_on":
					styles[key] = UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color(1.4, 1.22, 0.84))
				"glow":
					var glow := StyleBoxFlat.new()
					glow.bg_color = Color(0, 0, 0, 0)
					glow.shadow_color = Color(1.0, 0.78, 0.35, 0.55)
					glow.shadow_size = 9
					glow.set_corner_radius_all(10)
					styles[key] = glow
				"track":
					styles[key] = UiKit.nine("kit_track", Vector4(11, 10, 11, 10), Vector4.ZERO)
				"fill_bar":
					styles[key] = UiKit.nine("kit_fill", Vector4(11, 10, 11, 10), Vector4.ZERO)
				"fill_done":
					styles[key] = UiKit.nine("kit_fill_green", Vector4(11, 10, 11, 10), Vector4.ZERO)
		return styles[key]

	func _draw() -> void:
		var mode := get_draw_mode()
		var pressed := mode == DRAW_PRESSED or mode == DRAW_HOVER_PRESSED
		var plate := Rect2(Vector2(2, 2), size - Vector2(4, 4))
		if selected:
			draw_style_box(style("glow"), plate.grow(-3))
		draw_style_box(style("fill_on" if selected else "fill"), plate)
		draw_style_box(style("frame_on" if selected else "frame"), plate)
		if pressed:
			draw_rect(plate.grow(-6), Color(0, 0, 0, 0.18))
		# Medallion: the bronze rail disc, a portrait clipped round or the forged emblem.
		var d := 60.0
		var centre := Vector2(14.0 + d * 0.5, size.y * 0.5 + (1.0 if pressed else 0.0))
		draw_texture_rect(UiKit.tex("kit_rail_on" if selected else "kit_rail"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false)
		var radius := d * 0.36
		if busy and face != null:
			var points := PackedVector2Array()
			var uvs := PackedVector2Array()
			var source := face.get_size()
			var k := minf(source.x, source.y)
			var uv_scale := Vector2(k / source.x, k / source.y) * 0.5
			for i in 40:
				var along := Vector2.from_angle(TAU * i / 40.0)
				points.append(centre + along * radius)
				uvs.append(Vector2(0.5, 0.5) + along * uv_scale)
			draw_polygon(points, PackedColorArray([Color.WHITE]), uvs, face)
			draw_arc(centre, radius - 0.5, 0.0, TAU, 40, Color(0, 0, 0, 0.4), 2.5, true)
		elif emblem != null:
			var side := radius * 1.7
			draw_texture_rect(emblem, Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false, Color(1, 1, 1, 1.0 if busy else 0.82))
		var x := 14.0 + d + 12.0
		var width := maxf(20.0, size.x - x - 16.0)
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, 18, width - (34.0 if waiting > 0 else 0.0))
		head.draw_outline(get_canvas_item(), Vector2(x, 9.0), 3, Color(0, 0, 0, 0.55))
		head.draw(get_canvas_item(), Vector2(x, 9.0), UiKit.GOLD if selected else UiKit.IVORY)
		if waiting > 0:
			var tag := UiKit.KitText.line("+%d" % waiting, UiKit.LABEL_FONT, 14)
			var at := Vector2(size.x - 16.0 - tag.get_size().x, 11.0)
			draw_circle(at + tag.get_size() * 0.5, 12.0, Color("#c59a4f"))
			draw_circle(at + tag.get_size() * 0.5, 10.5, Color("#22170f"))
			tag.draw(get_canvas_item(), at, UiKit.GOLD)
		if not busy:
			var idle := UiKit.KitText.line(free_text, UiKit.LABEL_FONT, 18, width)
			idle.draw_outline(get_canvas_item(), Vector2(x, 38.0), 3, Color(0, 0, 0, 0.5))
			idle.draw(get_canvas_item(), Vector2(x, 38.0), Color("#9fe08f"))
			return
		var sub := UiKit.KitText.line(subtitle, UiKit.BODY_FONT, 14, width)
		sub.draw(get_canvas_item(), Vector2(x, 31.0), Color("#e4d3b0"))
		var now: float = clock.call() if clock.is_valid() else 0.0
		var finished_now := done or (ends > 0.0 and now >= ends)
		var ratio := 1.0 if finished_now else (0.0 if ends <= starts or now < starts else clampf((now - starts) / (ends - starts), 0.0, 1.0))
		var bar := Rect2(x, size.y - 27.0, width, 20.0)
		draw_style_box(style("track"), bar)
		if ratio > 0.0:
			draw_style_box(style("fill_done" if finished_now else "fill_bar"), Rect2(bar.position, Vector2(maxf(22.0, bar.size.x * ratio), bar.size.y)))
		var left := "Закончено" if finished_now else ("Ожидает · " + Clock.text(starts - now) if now < starts else Clock.text(ends - now))
		var clock_line := UiKit.KitText.line(left, UiKit.LABEL_FONT, 15)
		var at := Vector2(roundf(bar.position.x + (bar.size.x - clock_line.get_size().x) * 0.5), roundf(bar.position.y + (bar.size.y - clock_line.get_size().y) * 0.5))
		clock_line.draw_outline(get_canvas_item(), at, 4, Color("#1a0f06"))
		clock_line.draw(get_canvas_item(), at, UiKit.IVORY)

## Section band of the rail: a short oak strip with the emblem and the name in gold.
class RailBand extends Control:
	var text := ""
	var emblem: Texture2D

	func _draw() -> void:
		var line := UiKit.KitText.line(text, UiKit.LABEL_FONT, 18)
		var total := line.get_size().x + 34.0
		var left := roundf((size.x - total) * 0.5)
		var y := roundf(size.y * 0.5)
		for side: float in [-1.0, 1.0]:
			var from := Vector2(left - 12.0, y) if side < 0.0 else Vector2(left + total + 12.0, y)
			var to := Vector2(14.0, y) if side < 0.0 else Vector2(size.x - 14.0, y)
			draw_line(from, to, Color("#c9a05a88"), 2.0, true)
			draw_line(from + Vector2(0, 2), to + Vector2(0, 2), Color(0, 0, 0, 0.35), 1.0, true)
			var tip := to + Vector2(side * -4.0, 0)
			draw_colored_polygon(PackedVector2Array([tip + Vector2(0, -4), tip + Vector2(side * 4.0, 0), tip + Vector2(0, 4), tip + Vector2(side * -4.0, 0)]), Color("#d8b46a"))
		if emblem != null:
			draw_texture_rect(emblem, Rect2(left, y - 13.0, 26.0, 26.0), false)
		line.draw_outline(get_canvas_item(), Vector2(left + 34.0, y - line.get_size().y * 0.5), 4, Color(0, 0, 0, 0.6))
		line.draw(get_canvas_item(), Vector2(left + 34.0, y - line.get_size().y * 0.5), UiKit.GOLD)

## Timer band of the selected job: an oak strip with the job on the left and an hourglass
## with the time left in gold on the right, a thin bar along its lower edge.
class TimerBand extends Control:
	var title := ""
	var starts := 0.0
	var ends := 0.0
	var waiting := 0
	var done := false
	var clock: Callable

	func _draw() -> void:
		var plate := Rect2(Vector2.ZERO, size)
		draw_style_box(UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4.ZERO), plate)
		var now: float = clock.call() if clock.is_valid() else 0.0
		var right := size.x - 30.0
		if ends > 0.0:
			var finished_now := done or now >= ends
			var value := "Закончено" if finished_now else (("Ожидает · " + Clock.text(starts - now)) if now < starts else Clock.text(ends - now))
			var time_line := UiKit.KitText.line(value, UiKit.LABEL_FONT, 23)
			right -= time_line.get_size().x
			var at := Vector2(right, roundf((size.y - time_line.get_size().y) * 0.5) - 2.0)
			time_line.draw_outline(get_canvas_item(), at, 4, Color(0, 0, 0, 0.5))
			time_line.draw(get_canvas_item(), at, Color("#9fe08f") if finished_now else UiKit.GOLD)
			right -= 30.0
			draw_texture_rect(UiKit.tex("kit_hourglass"), Rect2(right, roundf(size.y * 0.5) - 14.0, 22.0, 26.0), false)
			right -= 14.0
			var ratio := 1.0 if finished_now else (0.0 if ends <= starts or now < starts else clampf((now - starts) / (ends - starts), 0.0, 1.0))
			var track := Rect2(30.0, size.y - 12.0, size.x - 60.0, 4.0)
			draw_rect(track, Color(0, 0, 0, 0.45))
			draw_rect(Rect2(track.position, Vector2(track.size.x * ratio, track.size.y)), Color("#9fe08f") if finished_now else Color("#e8b54f"))
		var name := UiKit.KitText.line(title, UiKit.LABEL_FONT, 20, maxf(20.0, right - 30.0))
		var at := Vector2(30.0, roundf((size.y - name.get_size().y) * 0.5) - 2.0)
		name.draw_outline(get_canvas_item(), at, 3, Color(0, 0, 0, 0.5))
		name.draw(get_canvas_item(), at, UiKit.IVORY)

## A speed-up row in one drawn node (its button is the only child): linen plate, the
## painted item tile with the duration on a small plate, name, what it does and how many
## are owned. quick: the gold «Быстрое использование» plate with the chosen items stacked.
class SpeedRow extends Control:
	var icon: Texture2D
	var round_icon := false
	var duration := ""
	var title := ""
	var text := ""
	var count := -1
	var count_text := ""
	var quick := false
	var stack: Array = []
	var action: Button
	static var quick_fill: StyleBox
	static var quick_frame: StyleBox

	func _init() -> void:
		custom_minimum_size.y = 98
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func add_action(caption: String, kind: String, at_size: Vector2) -> Button:
		var control := Button.new()
		control.text = caption
		add_child(control)
		action = control
		UiKit.style_button(control, kind, 19 if kind == "primary" else 18)
		control.custom_minimum_size = at_size
		control.anchor_left = 1.0
		control.anchor_right = 1.0
		control.anchor_top = 0.5
		control.anchor_bottom = 0.5
		control.offset_left = -at_size.x - 18.0
		control.offset_right = -18.0
		control.offset_top = -at_size.y * 0.5
		control.offset_bottom = at_size.y * 0.5
		queue_redraw()
		return control

	func _draw() -> void:
		var plate := Rect2(Vector2.ZERO, size)
		if quick:
			if quick_fill == null:
				var warm := StyleBoxFlat.new()
				warm.bg_color = Color(1.0, 0.8, 0.34, 0.2)
				warm.set_corner_radius_all(8)
				warm.shadow_color = Color(0.95, 0.68, 0.2, 0.35)
				warm.shadow_size = 7
				quick_fill = warm
				quick_frame = UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color(1.35, 1.18, 0.82))
			draw_style_box(UiKit.row_style(), plate)
			draw_style_box(quick_fill, plate.grow(-5))
			draw_style_box(quick_frame, plate)
		else:
			draw_style_box(UiKit.row_style(), plate)
		var tile := 74.0
		var box := Rect2(16.0, roundf((size.y - tile) * 0.5) - (5.0 if not duration.is_empty() else 0.0), tile, tile)
		var dim := count == 0
		if quick and not stack.is_empty():
			# The chosen items fanned out: up to three tiles, the last one in front.
			var shown := stack.slice(maxi(0, stack.size() - 3))
			for i in shown.size():
				var shift := Vector2(-10.0 + 10.0 * i, -6.0 + 6.0 * i) if shown.size() > 1 else Vector2.ZERO
				var small := Rect2(box.position + Vector2(6, 6) + shift, Vector2(tile - 12.0, tile - 12.0))
				draw_texture_rect(shown[i], small, false)
			if stack.size() > 1:
				var badge := UiKit.KitText.line("×%d" % stack.size(), UiKit.LABEL_FONT, 17)
				var at := box.end - badge.get_size() - Vector2(0, 2)
				badge.draw_outline(get_canvas_item(), at, 5, Color("#1a120a"))
				badge.draw(get_canvas_item(), at, UiKit.IVORY)
		elif icon != null:
			if round_icon:
				draw_texture_rect(UiKit.tex("kit_rail"), box, false)
				var side := tile * 0.58
				draw_texture_rect(icon, Rect2(box.get_center() - Vector2(side, side) * 0.5, Vector2(side, side)), false)
			else:
				draw_texture_rect(icon, box, false, Color(1, 1, 1, 0.55) if dim else Color.WHITE)
		if not duration.is_empty():
			# The duration on a small dark plate across the foot of the tile.
			var label := UiKit.KitText.line(duration, UiKit.LABEL_FONT, 15)
			var plate_w := maxf(46.0, label.get_size().x + 20.0)
			var foot := Rect2(roundf(box.get_center().x - plate_w * 0.5), box.end.y - 9.0, plate_w, 21.0)
			draw_style_box(UiKit.nine("kit_pill", Vector4(18, 12, 18, 12), Vector4.ZERO), foot)
			var at := Vector2(roundf(foot.get_center().x - label.get_size().x * 0.5), roundf(foot.position.y + (foot.size.y - label.get_size().y) * 0.5))
			label.draw(get_canvas_item(), at, Color(UiKit.GOLD, 0.6) if dim else UiKit.GOLD)
		var x := box.end.x + 16.0
		var right := size.x - 18.0 - (action.custom_minimum_size.x + 16.0 if is_instance_valid(action) else 0.0)
		var width := maxf(40.0, right - x)
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, 20, width)
		var body := UiKit.KitText.line(text, UiKit.BODY_FONT, 15, width)
		var lines: Array = [head, body]
		if not count_text.is_empty():
			lines.append(UiKit.KitText.line(count_text, UiKit.LABEL_FONT, 15, width))
		var total := 0.0
		for line: TextLine in lines:
			total += line.get_size().y
		var y := roundf((size.y - total) * 0.5)
		head.draw(get_canvas_item(), Vector2(x, y), Color(UiKit.INK, 0.6) if dim else UiKit.INK)
		y += head.get_size().y
		body.draw(get_canvas_item(), Vector2(x, y), UiKit.INK_MUTED)
		y += body.get_size().y
		if lines.size() > 2:
			lines[2].draw(get_canvas_item(), Vector2(x, y), UiKit.INK_MUTED if dim else UiKit.BRONZE)

## Time left as the rail and the band show it: m:ss, h:mm:ss, or days first.
class Clock:
	static func text(milliseconds: float) -> String:
		var seconds := ceili(maxf(0.0, milliseconds) / 1000.0)
		if seconds >= 86400:
			return "%d д %d:%02d:%02d" % [seconds / 86400, (seconds / 3600) % 24, (seconds / 60) % 60, seconds % 60]
		if seconds >= 3600:
			return "%d:%02d:%02d" % [seconds / 3600, (seconds / 60) % 60, seconds % 60]
		return "%d:%02d" % [seconds / 60, seconds % 60]
