extends RefCounted
## Works of the V6 academy and infirmary (premium UI stage 4a, ui_premium/STAGE4A.md).
##
## Military academy (B15): one card per research family with its forged emblem, the rank
## as eleven lozenges (I–XI), the effect now and after the next rank, the cost with icons,
## the time with the academy's speed, and «Исследовать». Ranks are the server's: the next
## rank needs the academy at that level (required_academy = rank; the academy's
## research_rank_cap), so ranks past the open building level need an academy past it.
## A running research shows its bar; the academy researches one family at a time.
##
## Infirmary (B16): the wounded per unit with portraits and a slider each (up to the
## infirmary's batch), the cost (food and coins per soldier) and the time with the healing
## bonus, then «Лечить». Both send through the authoritative quote (v6_panels.confirm).

const UiKit = preload("res://src/ui_kit.gd")
const UnitStage = preload("res://src/unit_stage.gd")
const Queues = preload("res://src/v6_queues.gd")
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
const FAMILIES := ["R_BUILD", "R_ECON", "R_ATTACK", "R_DEFENCE"]
const FAMILY_EMBLEMS := {"R_BUILD": "kit_emb_craft", "R_ECON": "kit_emb_sheaf", "R_ATTACK": "kit_emb_sword", "R_DEFENCE": "kit_emb_shield"}
## Server healing terms (v6 orders: healing_food, healing_coins, healing_seconds_per_unit).
const HEAL_FOOD := 5
const HEAL_COINS := 2
const HEAL_SECONDS := 10

var panels
var ui
var last_open_usec := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

func level_of(type: String) -> int:
	return int(panels.building(type).get("level", 0))

func effect(type: String, key: String) -> int:
	return int(panels.row_for(type, maxi(1, level_of(type))).get("effects", {}).get(key, 0))

func running(kind: String) -> Dictionary:
	for order: Dictionary in ui.state.v6.orders:
		if order.status == "pending" and order.kind == kind:
			return order
	return {}

# ------------------------------------------------------------------ academy

func research_row(family: String, rank: int) -> Dictionary:
	for row: Dictionary in panels.catalogue.get("research", []):
		if str(row.get("family", "")) == family and int(row.get("rank", 0)) == rank:
			return row
	return {}

func research() -> void:
	var started := Time.get_ticks_usec()
	var academy := level_of("B15")
	ui.open_modal(str(panels.row_for("B15", 1).get("name_ru", "Военная академия")), "full",
		"ИССЛЕДОВАНИЯ · АКАДЕМИЯ " + ROMAN[clampi(academy, 1, 11) - 1], ui.v6_card("B15"))
	var active := running("research")
	var speed := effect("B15", "research_speed_bp")
	var line := "Академия исследует одну ветвь за раз · скорость +%s%%" % String.num(speed / 100.0, 0)
	UiKit.label(ui.modal_body, line, 16, UiKit.INK_MUTED)
	var first := true
	for family: String in FAMILIES:
		var rank := int(ui.state.v6.get("research", {}).get(family, 0))
		var current := research_row(family, rank)
		var next := research_row(family, rank + 1)
		var card := ResearchCard.new()
		card.name = "Research_" + family
		card.emblem = UiKit.tex(FAMILY_EMBLEMS[family])
		card.title = str((next if not next.is_empty() else current).get("name_ru", family))
		card.rank = rank
		var metric := str((next if not next.is_empty() else current).get("metric_id", ""))
		var metric_name := str(panels.catalogue.get("metrics", {}).get(metric, {}).get("name_ru", "Бонус"))
		var now_text := "+%s%%" % String.num(float(current.get("effect_total_bp", 0)) / 100.0, 2) if not current.is_empty() else "+0%"
		card.icons = ui.resource_icons
		card.stock = ui.state.v6.get("stock", {})
		ui.modal_body.add_child(card)
		if next.is_empty():
			card.effect = "%s: %s · ветвь изучена до конца" % [metric_name, now_text]
			continue
		card.effect = "%s: %s → +%s%%" % [metric_name, now_text, String.num(float(next.get("effect_total_bp", 0)) / 100.0, 2)]
		if not active.is_empty() and str(active.get("family", "")) == family:
			card.starts = float(active.starts_at) * 1000.0
			card.ends = float(active.ends_at) * 1000.0
			card.clock = ui.timer_now
			card.note = "Идёт исследование ранга %s" % ROMAN[clampi(int(active.get("target", rank + 1)), 1, 11) - 1]
			var watch := card.add_action("Очередь", "tertiary")
			watch.pressed.connect(panels.queue_view.open.bind(active))
			continue
		card.cost = next.get("cost", {})
		card.seconds = ceili(float(next.get("duration_seconds", 0)) * 10000.0 / (10000.0 + speed))
		var needs := int(next.get("required_academy", rank + 1))
		if academy < needs:
			card.note = "Нужна академия %s" % ROMAN[clampi(needs, 1, 11) - 1]
			var locked := card.add_action("Исследовать", "primary")
			locked.disabled = true
			continue
		var go := card.add_action("Исследовать", "primary")
		if first:
			go.name = "ServiceAction"
			first = false
		if not active.is_empty():
			go.disabled = true
			card.note = "Академия занята другой ветвью"
		var research_id := str(next.get("research_id", "%s-%d" % [family, rank + 1]))
		go.pressed.connect(panels.confirm.bind({"kind": "research", "research": research_id}))
	last_open_usec = Time.get_ticks_usec() - started

# ------------------------------------------------------------------ infirmary

func hospital() -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal(str(panels.row_for("B16", 1).get("name_ru", "Лазарет")), "full", "ЛЕЧЕНИЕ РАНЕНЫХ", ui.v6_card("B16"))
	var wounded: Dictionary = ui.state.v6.get("wounded", {})
	var total := 0
	for id: String in wounded:
		total += int(wounded[id])
	var batch := maxi(1, effect("B16", "healing_batch"))
	var beds := int(ui.state.v6.get("hospital_capacity", 0))
	var figures := HBoxContainer.new()
	figures.add_theme_constant_override("separation", 10)
	ui.modal_body.add_child(figures)
	for pair: Array in [["kit_ic_health", "%s раненых" % ui.format_balance(total), "Раненых в лазарете"], ["kit_ic_places", "%s коек" % ui.format_balance(beds), "Коек в лазарете"],
			["kit_ic_batch", "до %s за раз" % ui.format_balance(batch), "Лечится за один заказ"]]:
		figures.add_child(UiKit.chip(pair[0], pair[1], pair[2]))
	var active := running("heal")
	if not active.is_empty():
		var count := 0
		for id: String in active.get("units", {}):
			count += int(active.units[id])
		var card := ResearchCard.new()
		card.name = "HealRunning"
		card.emblem = UiKit.tex("kit_emb_heal")
		card.title = "Идёт лечение · %s воинов" % ui.format_balance(count)
		card.rank = -1
		card.starts = float(active.starts_at) * 1000.0
		card.ends = float(active.ends_at) * 1000.0
		card.clock = ui.timer_now
		card.note = "Лазарет лечит одну партию за раз"
		ui.modal_body.add_child(card)
		card.add_action("Очередь", "tertiary").pressed.connect(panels.queue_view.open.bind(active))
	var shown: Array = []
	for unit: Dictionary in panels.catalogue.get("units", []):
		if int(wounded.get(unit.unit_id, 0)) > 0:
			shown.append(unit)
	for id: String in wounded:
		if int(wounded[id]) > 0 and not shown.any(func(u): return u.unit_id == id):
			shown.append({"unit_id": id, "name_ru": id, "required_building": 1})
	if shown.is_empty():
		var empty := Queues.SpeedRow.new()
		empty.name = "HealEmpty"
		empty.title = "Раненых нет"
		empty.text = "Раненые после боёв попадают сюда; лечение возвращает их в строй."
		empty.icon = UiKit.tex("kit_emb_heal")
		empty.round_icon = true
		ui.modal_body.add_child(empty)
		return
	UiKit.section_header(ui.modal_body, "Раненые")
	var fields := {}
	var cost_holder := VBoxContainer.new()
	# Lambdas capture locals by value: the button is reached through this holder.
	var holder := {"heal": null}
	var refresh := func():
		var amount := 0
		var units := {}
		for id: String in fields:
			var n := int(fields[id].value)
			if n > 0:
				units[id] = n
				amount += n
		var seconds := ceili(float(amount * HEAL_SECONDS) * 10000.0 / (10000.0 + float(ui.state.v6.get("bonuses", {}).get("healing", 0))))
		ui.empty(cost_holder)
		UiKit.cost_strip(cost_holder, {"food": amount * HEAL_FOOD, "coins": amount * HEAL_COINS}, ui.resource_icons, ui.state.v6.get("stock", {}), ui.RESOURCE_NAMES)
		UiKit.timer_pill(cost_holder, "Лечение %s воинов" % ui.format_balance(amount), Queues.span(seconds))
		var button: Button = holder.heal
		if is_instance_valid(button):
			button.disabled = amount <= 0 or amount > batch or not active.is_empty()
			button.set_meta("units", units)
	var left := batch
	for unit: Dictionary in shown:
		var id := str(unit.unit_id)
		var count := int(wounded.get(id, 0))
		var row := PanelContainer.new()
		row.name = "Wounded_" + id
		row.add_theme_stylebox_override("panel", UiKit.row_style())
		ui.modal_body.add_child(row)
		var middle := VBoxContainer.new()
		middle.add_theme_constant_override("separation", 0)
		row.add_child(middle)
		# Portrait, name and count in one drawn node; the slider and field under them.
		var head := UnitHead.new()
		head.face = UnitStage.portrait(id, true)
		head.tier = clampi(int(unit.get("required_building", 1)), 1, UiKit.TIERS.size())
		head.title = str(unit.get("name_ru", id))
		head.line = "Раненых: %s" % ui.format_balance(count)
		head.accessibility_name = "%s · %s" % [head.title, head.line]
		middle.add_child(head)
		var pick: Array = UiKit.quantity(middle, 0, count, mini(count, left))
		left -= mini(count, left)
		fields[id] = pick[1]
		pick[1].value_changed.connect(func(_v): refresh.call())
	ui.modal_body.add_child(cost_holder)
	var heal: Button = ui.button(ui.modal_body, "Лечить", Callable())
	holder.heal = heal
	heal.name = "ServiceAction"
	UiKit.style_button(heal, "primary", 21)
	heal.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	heal.custom_minimum_size = Vector2(300, 56)
	heal.pressed.connect(func():
		var units: Dictionary = heal.get_meta("units", {})
		if not units.is_empty():
			panels.confirm({"kind": "heal", "units": units}))
	refresh.call()
	if not active.is_empty():
		UiKit.label(ui.modal_body, "Новая партия начнётся, когда закончится текущая.", 15, UiKit.WARN)
	last_open_usec = Time.get_ticks_usec() - started

## A research family (or the running healing) in one drawn node with its action button:
## the emblem medallion, the name, eleven rank lozenges, the effect, then either the cost
## with icons and the time, or the bar of the running work.
class ResearchCard extends Control:
	var emblem: Texture2D
	var title := ""
	var rank := 0
	var effect := ""
	var note := ""
	var cost: Dictionary = {}
	var stock: Dictionary = {}
	var icons: Dictionary = {}
	var seconds := 0
	var starts := 0.0
	var ends := 0.0
	var clock := Callable()
	var action: Button
	var timer: Timer

	func _init() -> void:
		custom_minimum_size.y = 128
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func add_action(caption: String, kind: String) -> Button:
		var control := Button.new()
		control.text = caption
		add_child(control)
		action = control
		UiKit.style_button(control, kind, 19)
		var at_size := Vector2(210, 54)
		control.custom_minimum_size = at_size
		control.anchor_left = 1.0
		control.anchor_right = 1.0
		control.anchor_top = 0.5
		control.anchor_bottom = 0.5
		control.offset_left = -at_size.x - 18.0
		control.offset_right = -18.0
		# A little under the middle: the rank lozenges sit above it.
		control.offset_top = -at_size.y * 0.5 + 9.0
		control.offset_bottom = at_size.y * 0.5 + 9.0
		if ends > 0.0 and timer == null:
			timer = Timer.new()
			timer.wait_time = 1.0
			timer.autostart = true
			timer.timeout.connect(queue_redraw)
			add_child(timer)
		return control

	func _draw() -> void:
		draw_style_box(UiKit.row_style(), Rect2(Vector2.ZERO, size))
		var d := 78.0
		var centre := Vector2(18.0 + d * 0.5, size.y * 0.5)
		draw_texture_rect(UiKit.tex("kit_rail"), Rect2(centre - Vector2(d, d) * 0.5, Vector2(d, d)), false)
		if emblem != null:
			var side := d * 0.6
			draw_texture_rect(emblem, Rect2(centre - Vector2(side, side) * 0.5, Vector2(side, side)), false)
		var x := 18.0 + d + 16.0
		var right := size.x - 18.0 - (action.custom_minimum_size.x + 18.0 if is_instance_valid(action) else 0.0)
		var width := maxf(60.0, right - x)
		var y := 12.0
		var head := UiKit.KitText.line(title, UiKit.LABEL_FONT, 20, width)
		head.draw(get_canvas_item(), Vector2(x, y), UiKit.INK)
		if rank >= 0:
			# Rank I–XI as lozenges over the action (gold up to the current rank, the next
			# one outlined), clear of the name however long it is.
			var caption := UiKit.KitText.line("Ранг %s" % (ROMAN[rank - 1] if rank > 0 else "—"), UiKit.LABEL_FONT, 14)
			var step := 12.5
			var lx := size.x - 18.0 - 10.0 * step - 5.0
			var px := lx - 12.0 - caption.get_size().x
			var ly := 21.0
			caption.draw(get_canvas_item(), Vector2(px, roundf(ly - caption.get_size().y * 0.5)), UiKit.BRONZE)
			for i in 11:
				var c := Vector2(lx + i * step, ly)
				var shape := PackedVector2Array([c + Vector2(0, -6), c + Vector2(4.5, 0), c + Vector2(0, 6), c + Vector2(-4.5, 0)])
				if i < rank:
					draw_colored_polygon(shape, Color("#d9a441"))
					draw_polyline(shape + PackedVector2Array([shape[0]]), Color("#6b4314"), 1.2, true)
				else:
					draw_polyline(shape + PackedVector2Array([shape[0]]), Color("#b8894a") if i == rank else Color("#a67c3f66"), 1.4 if i == rank else 1.0, true)
		y += head.get_size().y + 4.0
		if not effect.is_empty():
			var gain := UiKit.KitText.line(effect, UiKit.BODY_FONT, 16, width)
			gain.draw(get_canvas_item(), Vector2(x, y), UiKit.GOOD)
			y += gain.get_size().y + 6.0
		if ends > 0.0:
			var now: float = clock.call() if clock.is_valid() else 0.0
			var ratio := clampf((now - starts) / maxf(1.0, ends - starts), 0.0, 1.0)
			var bar := Rect2(x, y + 2.0, width, 20.0)
			draw_style_box(UiKit.nine("kit_track", Vector4(11, 10, 11, 10), Vector4.ZERO), bar)
			if ratio > 0.0:
				draw_style_box(UiKit.nine("kit_fill", Vector4(11, 10, 11, 10), Vector4.ZERO), Rect2(bar.position, Vector2(maxf(22.0, bar.size.x * ratio), bar.size.y)))
			var left := UiKit.KitText.line(Queues.Clock.text(ends - now) if now < ends else "Закончено", UiKit.LABEL_FONT, 15)
			var at := Vector2(roundf(bar.get_center().x - left.get_size().x * 0.5), roundf(bar.position.y + (bar.size.y - left.get_size().y) * 0.5))
			left.draw_outline(get_canvas_item(), at, 4, Color("#1a0f06"))
			left.draw(get_canvas_item(), at, UiKit.IVORY)
			y += 28.0
		elif not cost.is_empty():
			# Cost with resource icons (red where the stock is short), then the time.
			var cx := x
			for key: String in ["wood", "food", "stone", "iron", "coins"]:
				var amount := int(cost.get(key, 0))
				if amount <= 0:
					continue
				if icons.has(key):
					draw_texture_rect(icons[key], Rect2(cx, y, 22.0, 22.0), false)
				var value := UiKit.KitText.line(UiKit.compact(amount), UiKit.LABEL_FONT, 15)
				value.draw(get_canvas_item(), Vector2(cx + 25.0, y + roundf((22.0 - value.get_size().y) * 0.5)), UiKit.BAD if int(stock.get(key, amount)) < amount else UiKit.INK)
				cx += 25.0 + value.get_size().x + 12.0
			if seconds > 0:
				draw_texture_rect(UiKit.tex("kit_hourglass"), Rect2(cx + 4.0, y + 1.0, 17.0, 20.0), false)
				var time := UiKit.KitText.line(Queues.span(seconds), UiKit.LABEL_FONT, 15)
				time.draw(get_canvas_item(), Vector2(cx + 26.0, y + roundf((22.0 - time.get_size().y) * 0.5)), UiKit.BRONZE)
			y += 28.0
		if not note.is_empty():
			var warn := UiKit.KitText.line(note, UiKit.LABEL_FONT, 15, width)
			warn.draw(get_canvas_item(), Vector2(x, y), UiKit.WARN)

## A unit's head line in one drawn node: the portrait on a tile of its tier, the name and
## a line under it (how many lie wounded; how many stand ready in the formation).
class UnitHead extends Control:
	var face: Texture2D
	var tier := 1
	var title := ""
	var line := ""

	func _init() -> void:
		custom_minimum_size.y = 72
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var tile := Rect2(0, 2, 68, 68)
		draw_style_box(UiKit.tinted("kit_card_fill", Vector4(14, 14, 14, 14), UiKit.TIERS[tier - 1].lightened(0.18)), tile)
		if face != null:
			draw_texture_rect(face, tile.grow(-2), false)
		draw_style_box(UiKit.tinted("kit_card_frame", Vector4(16, 16, 16, 16), Color.WHITE), tile)
		var x := tile.end.x + 16.0
		var width := maxf(40.0, size.x - x)
		var name_line := UiKit.KitText.line(title, UiKit.LABEL_FONT, 20, width)
		name_line.draw(get_canvas_item(), Vector2(x, 12), UiKit.INK)
		var count_line := UiKit.KitText.line(line, UiKit.BODY_FONT, 16, width)
		count_line.draw(get_canvas_item(), Vector2(x, 16 + name_line.get_size().y), UiKit.INK_MUTED)
