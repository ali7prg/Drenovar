extends RefCounted
## The market, the economy, the objectives and the archive of the V6 settlement (premium UI
## stage 4b, ui_premium/STAGE4B.md).
##
## «Рынок»: the market's diorama in the hero; the day's turnover on a bar with the fee; one
## quantity (a slider, a field and quick amounts) for every deal; a card per resource with
## its stock, what the chosen amount costs or brings in coins, «Продать» (lapis) and «Купить»
## (forest enamel). The coin figures are an estimate from the balance (base prices and the
## market's fee); the server decides every deal.
## «Экономика поселения»: the hourly income on an oak band, then a card per resource with its
## stock against the storage on a bar, the reserve, the rate as a green delta (or why it
## stopped) and when the storage fills; workers and the army as bars; links.
## «Цели поселения»: the progress on the oak column, a quest card per objective (its number,
## what to do, the reward with icons, a ribbon), «Получить награду» on the current one when it
## is done, «Как выполнить» (it goes there) when it is not.
## «Архив прежних зданий»: a card per archived building with its diorama, level, former plot
## and the compensation with icons.

const UiKit = preload("res://src/ui_kit.gd")
const KitMore = preload("res://src/kit_more.gd")
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
const TRADED := ["wood", "food", "stone", "iron"]
## Base coin prices of the balance (spec 05, policy.trade_base_coin_prices): display only.
const BASE_PRICES := {"wood": 2, "food": 2, "stone": 3, "iron": 4}
## What each starter objective asks, in the player's words, and where it is done.
const OBJECTIVE_HINTS := {
	"wood": ["Коснитесь лагеря лесорубов в городе и соберите добычу.", "kit_emb_sheaf"],
	"train": ["Обучите любой отряд в казармах и дождитесь конца обучения.", "kit_emb_inf"],
	"hall": ["Улучшите ратушу до второго уровня.", "kit_emb_town"],
	"build": ["Постройте каменоломню на участке у скал.", "kit_emb_craft"],
	"hunt": ["Соберите отряд и победите Тенериса у поселения.", "kit_emb_sword"],
}

var panels
var ui
var amount: SpinBox
var deal_cards := {}
var last_open_usec := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

func v6() -> Dictionary:
	return ui.state.v6

func icon(resource: String) -> Texture2D:
	return ui.resource_icons.get(resource)

# ------------------------------------------------------------------ market

func trade_terms() -> Dictionary:
	var market: Dictionary = panels.building("B05")
	var row: Dictionary = panels.row_for("B05", int(market.get("level", 1))) if not market.is_empty() else {}
	var effects: Dictionary = row.get("effects", {})
	var today := floori(float(v6().get("server_time", 0)) / 86400.0)
	var trade: Dictionary = v6().get("trade", {}) if v6().get("trade") is Dictionary else {}
	var used := int(trade.get("used", 0)) if int(trade.get("day", -1)) == today else 0
	return {"fee_bp": int(effects.get("trade_fee_bp", 1500)), "daily": int(effects.get("trade_daily_value", 0)), "used": used}

func trade() -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal("Рынок", "full", "ОБЩИЙ ДНЕВНОЙ ОБОРОТ", ui.v6_card("B05"))
	panels.warnings()
	var terms := trade_terms()
	var left := maxi(0, int(terms.daily) - int(terms.used)) if int(terms.daily) > 0 else 0
	var turnover := KitMore.Card.new()
	turnover.name = "Turnover"
	turnover.icon = UiKit.tex("kit_emb_trade")
	turnover.icon_mode = "disc"
	turnover.title = "Оборот за день"
	turnover.subtitle = "Пошлина рынка %s%% · счёт обнуляется в полночь по серверу" % String.num(float(terms.fee_bp) / 100.0, 1).trim_suffix(".0")
	if int(terms.daily) > 0:
		turnover.bar = float(terms.used) / float(terms.daily)
		turnover.bar_text = "%s из %s монет" % [ui.format_balance(int(terms.used)), ui.format_balance(int(terms.daily))]
	turnover.chips = [[icon("coins"), "В казне: %s" % ui.format_balance(int(v6().stock.get("coins", 0))), UiKit.BRONZE]]
	turnover.custom_minimum_size.y = 118
	ui.modal_body.add_child(turnover)
	UiKit.section_header(ui.modal_body, "Сделка")
	var pair: Array = UiKit.quantity(ui.modal_body, 1, 10000000, 1)
	var slider: HSlider = pair[0]
	amount = pair[1]
	amount.name = "TradeAmount"
	amount.custom_minimum_size.x = 170
	# The slider spans what the day's turnover still allows (the field takes any number).
	slider.max_value = maxf(100.0, float(left) / 2.0) if left > 0 else 100000.0
	slider.exp_edit = true
	var quick := HBoxContainer.new()
	quick.name = "QuickAmounts"
	quick.add_theme_constant_override("separation", 10)
	ui.modal_body.add_child(quick)
	for step: int in [100, 1000, 10000, 100000]:
		var preset: Button = ui.button(quick, "×" + ui.format_balance(step), func(): amount.value = step)
		UiKit.style_button(preset, "tertiary", 17)
		preset.custom_minimum_size = Vector2(0, 44)
		preset.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	deal_cards.clear()
	for resource: String in TRADED:
		var r := resource
		var row := KitMore.Card.new()
		row.name = "Deal_" + r
		row.icon = icon(r)
		row.title = str(ui.RESOURCE_NAMES[r])
		row.custom_minimum_size.y = 96
		ui.modal_body.add_child(row)
		var buy: Button = row.add_action("Купить " + str(ui.RESOURCE_NAMES[r]), "green", Vector2(200, 50))
		buy.pressed.connect(func(): panels.send({"kind":"trade", "direction":"buy", "resource":r, "quantity":int(amount.value)}))
		var sell: Button = row.add_action("Продать " + str(ui.RESOURCE_NAMES[r]), "secondary", Vector2(200, 50))
		sell.pressed.connect(func(): panels.send({"kind":"trade", "direction":"sell", "resource":r, "quantity":int(amount.value)}))
		deal_cards[r] = row
	amount.value_changed.connect(func(_v): refresh_deals())
	refresh_deals()
	last_open_usec = Time.get_ticks_usec() - started

## Stock and the estimated coins of the chosen amount on every card (no request).
func refresh_deals() -> void:
	if not is_instance_valid(amount):
		return
	var terms := trade_terms()
	var q := int(amount.value)
	var fee := float(terms.fee_bp) / 10000.0
	var stock: Dictionary = v6().get("stock", {})
	var caps: Dictionary = v6().get("capacities", {})
	for r: String in deal_cards:
		var row: KitMore.Card = deal_cards[r]
		if not is_instance_valid(row):
			continue
		var nominal := q * int(BASE_PRICES.get(r, 2))
		row.subtitle = "В запасе %s из %s" % [UiKit.compact(int(stock.get(r, 0))), UiKit.compact(int(caps.get(r, 0)))]
		row.chips = [[icon("coins"), "купить −%s" % ui.format_balance(ceili(nominal * (1.0 + fee))), UiKit.BAD if ceili(nominal * (1.0 + fee)) > int(stock.get("coins", 0)) else UiKit.INK],
			[icon("coins"), "продать +%s" % ui.format_balance(floori(nominal * (1.0 - fee))), UiKit.GOOD]]
		row.queue_redraw()

# ------------------------------------------------------------------ economy

func duration_text(seconds: float) -> String:
	var s := int(seconds)
	if s >= 86400:
		return "%d д %d ч" % [s / 86400, (s % 86400) / 3600]
	if s >= 3600:
		return "%d ч %d мин" % [s / 3600, (s % 3600) / 60]
	return "%d мин" % maxi(1, s / 60)

func economy() -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal("Экономика поселения", "full", "ЗАПАСЫ И ДОХОД В ЧАС")
	panels.warnings()
	var s := v6()
	var income := KitMore.Card.new()
	income.name = "Income"
	income.icon = UiKit.tex("kit_emb_sheaf")
	income.icon_mode = "disc"
	income.title = "Доход в час"
	income.custom_minimum_size.y = 96
	for r: String in ["wood", "food", "stone", "iron", "coins"]:
		var stopped: bool = s.production_stopped[r]
		income.chips.append([icon(r), ("+" + panels.per_hour(float(s.production_per_hour[r]))) if not stopped else "стоит", UiKit.GOOD if not stopped else UiKit.WARN])
	ui.modal_body.add_child(income)
	UiKit.section_header(ui.modal_body, "Запасы и доход")
	var grid := GridContainer.new()
	grid.name = "Resources"
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 10)
	ui.modal_body.add_child(grid)
	for r: String in ["wood", "food", "stone", "iron", "coins"]:
		var stock := int(s.stock[r])
		var cap := int(s.capacities[r])
		var rate := float(s.production_per_hour[r])
		var stopped: bool = s.production_stopped[r]
		var card := KitMore.Card.new()
		card.name = "Resource_" + r
		card.icon = icon(r)
		card.title = str(ui.RESOURCE_NAMES[r])
		card.custom_minimum_size = Vector2(0, 124)
		var line := "%s / %s" % [ui.format_balance(stock), ui.format_balance(cap)]
		if int(s.escrow[r]) > 0:
			line += " · резерв %s" % ui.format_balance(int(s.escrow[r]))
		card.subtitle = line
		card.bar = float(stock) / float(maxi(1, cap))
		card.bar_green = card.bar < 0.9
		if stopped:
			card.ribbon = "Склад полон" if stock >= cap else "Стоит"
			card.ribbon_colour = Color("#9c4f10")
			card.line = "Освободите место на складе" if stock >= cap else "Производство приостановлено"
			card.line_colour = UiKit.WARN
		else:
			card.line = "+%s/ч" % panels.per_hour(rate)
			card.line_colour = UiKit.GOOD
			if rate > 0.0 and stock < cap:
				card.line += " · склад заполнится через " + duration_text((cap - stock) / rate * 3600.0)
		grid.add_child(card)
	UiKit.section_header(ui.modal_body, "Люди и войско")
	var people := GridContainer.new()
	people.columns = 2
	people.add_theme_constant_override("h_separation", 12)
	ui.modal_body.add_child(people)
	for entry: Array in [["Работники", int(s.workforce.used), int(s.workforce.capacity), "kit_emb_craft"],
			["Армия", int(s.army_used), int(s.army_capacity), "kit_emb_sword"]]:
		var card := KitMore.Card.new()
		card.icon = UiKit.tex(entry[3])
		card.icon_mode = "disc"
		card.title = entry[0]
		card.subtitle = "%s из %s" % [ui.format_balance(entry[1]), ui.format_balance(entry[2])]
		card.bar = float(entry[1]) / float(maxi(1, entry[2]))
		card.custom_minimum_size = Vector2(0, 100)
		people.add_child(card)
	var more: HFlowContainer = panels.links()
	panels.link(more, "Очереди и отмена", panels.queues)
	panels.link(more, "Цели поселения", panels.objectives)
	if not panels.building("B05").is_empty():
		panels.link(more, "Рынок", panels.trade)
	last_open_usec = Time.get_ticks_usec() - started

# ------------------------------------------------------------------ objectives

func objectives() -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal("Цели поселения", "full", "НАГРАДЫ")
	var steps: Array = v6().get("starter", [])
	var done := steps.filter(func(o): return o.get("claimed", false)).size()
	var current := {}
	for step: Dictionary in steps:
		if not step.get("claimed", false):
			current = step
			break
	var oak := KitMore.ProfileCard.new()
	oak.emblem = UiKit.tex("kit_emb_award")
	oak.title = "Первые шаги"
	oak.banner = Color("#9a6a1a")
	oak.pill = "%d из %d наград" % [done, steps.size()]
	oak.lines = [["Получено", "%d" % done, null], ["Осталось", "%d" % (steps.size() - done), null]]
	if not current.is_empty():
		oak.lines.append(["Сейчас", str(current.get("title", "")), null])
	oak.note = "Награды приходят в запасы сразу." if not steps.is_empty() else ""
	panels.menu_view.oak_column(oak, 0.3)
	if steps.is_empty():
		UiKit.label(ui.modal_body, "Все первые цели этого поселения пройдены. Новые цели появятся вместе с новыми зданиями.", 17, UiKit.INK_MUTED)
		return
	UiKit.section_header(ui.modal_body, "Цели и награды")
	for index in steps.size():
		var step: Dictionary = steps[index]
		var id := str(step.get("id", ""))
		var card := KitMore.Card.new()
		card.name = "Objective_" + id
		card.icon = UiKit.tex(OBJECTIVE_HINTS.get(id, ["", "kit_emb_award"])[1])
		card.icon_mode = "disc"
		card.title = "%s. %s" % [ROMAN[index], str(step.get("title", ""))]
		card.subtitle = str(OBJECTIVE_HINTS.get(id, ["", ""])[0])
		card.custom_minimum_size.y = 112
		for resource: String in step.get("reward", {}):
			card.chips.append([icon(resource), "+%s" % ui.format_balance(int(step.reward[resource])), UiKit.GOOD])
		ui.modal_body.add_child(card)
		if step.get("claimed", false):
			card.ribbon = "Получено"
			card.ribbon_colour = Color("#5d6b4a")
			card.plate = "dim"
		elif step == current and step.get("ready", false):
			card.ribbon = "Готово"
			card.ribbon_colour = UiKit.GOOD
			card.plate = "gold"
			var claim: Button = card.add_action("Получить награду", "green", Vector2(230, 54))
			claim.name = "ClaimReward"
			claim.pressed.connect(claim_reward.bind(step, claim))
		elif step == current:
			card.ribbon = "Сейчас"
			card.ribbon_colour = Color("#2a5d93")
			var how: Button = card.add_action("Как выполнить", "tertiary", Vector2(200, 50))
			how.name = "HowTo"
			how.pressed.connect(go_to.bind(id))
		else:
			card.ribbon = "Готово · после текущей" if step.get("ready", false) else "Впереди"
			card.ribbon_colour = Color("#7a6a52")
	last_open_usec = Time.get_ticks_usec() - started

func claim_reward(step: Dictionary, control: Button) -> void:
	if control.disabled:
		return
	control.disabled = true
	control.text = "Получаем…"
	var parts: PackedStringArray = []
	for resource: String in step.get("reward", {}):
		parts.append("%s +%s" % [ui.RESOURCE_NAMES.get(resource, resource), ui.format_balance(int(step.reward[resource]))])
	var accepted: bool = await ui.command({"kind":"starter71", "objectiveId":str(step.id)}, panels.objectives)
	if accepted:
		ui.message.text = "Готово: награда получена · " + ", ".join(parts)

## Where an objective is done.
func go_to(id: String) -> void:
	match id:
		"wood":
			ui.close_modal()
			var camp: Dictionary = panels.building("B02")
			if not camp.is_empty():
				panels.inspect("B02")
		"train":
			panels.services("B11")
		"hall":
			panels.inspect("B01")
		"build":
			panels.catalog()
		_:
			ui.show_city_hunt()

# ------------------------------------------------------------------ archive

func archive() -> void:
	ui.open_modal("Архив прежних зданий", "full", "ТЕСТОВЫЙ ВАРИАНТ COMPAT-P2")
	var lead := KitMore.Card.new()
	lead.icon = UiKit.tex("kit_emb_chest")
	lead.icon_mode = "disc"
	lead.plate = "gold"
	lead.title = "Здания прежней версии"
	lead.subtitle = "Исходные здания сохранены в архиве и не дают второй игровой эффект."
	lead.line = "Компенсация за преобразование выдаётся один раз."
	lead.custom_minimum_size.y = 104
	ui.modal_body.add_child(lead)
	UiKit.section_header(ui.modal_body, "В архиве")
	for entry: Dictionary in v6().get("legacy_building_archive", []):
		var previous: Dictionary = entry.instance
		var row: Dictionary = panels.row_for(str(previous.to_type), int(previous.level))
		var card := KitMore.Card.new()
		card.icon = ui.v6_card(str(previous.to_type))
		card.icon_mode = "portrait"
		card.title = "%s · %s" % [str(row.get("name_ru", "Прежнее здание")), ROMAN[clampi(int(previous.level), 1, 11) - 1]]
		card.subtitle = "Прежний участок %s" % str(previous.plot)
		card.ribbon = "Компенсация"
		card.ribbon_colour = Color("#7a5222")
		for resource: String in entry.get("proposed_compensation", {}):
			card.chips.append([icon(resource), ui.format_balance(int(entry.proposed_compensation[resource])), UiKit.INK])
		card.custom_minimum_size.y = 108
		ui.modal_body.add_child(card)
		# Kept for screen readers and tests that read the old rows.
		card.accessibility_name = "%s · %s · прежний участок %s" % [str(row.get("name_ru", "Прежнее здание")), ROMAN[clampi(int(previous.level), 1, 11) - 1], str(previous.plot)]
