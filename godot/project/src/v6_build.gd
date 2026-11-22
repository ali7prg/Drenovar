extends RefCounted
## Construction in the V6 economy (premium UI stage 3, ui_premium/STAGE3.md): the strip of
## building cards over the blurred city (src/build_strip.gd, src/build_card.gd) and placing a
## new building on a plot of the city (glowing plots, a ghost of the building, a compact
## floating confirm with the server's cost and time; src/build_place.gd).
##
## Every number comes from the server: the catalogue rows (cost, time, requirements, terrain,
## limits) and the confirmed state (buildings, orders, stock, bonuses, plots). The cards only
## read them; the server quote decides what a build costs before it is sent.

const UiKit = preload("res://src/ui_kit.gd")
const BuildStrip = preload("res://src/build_strip.gd")
const BuildCard = preload("res://src/build_card.gd")
const BuildingStage = preload("res://src/building_stage.gd")
const BuildPlace = preload("res://src/build_place.gd")
const VERSION := "DRENOVAR-V6-C1.0"
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]

## The rail: caption, emblem, types. Every type of the catalogue is in exactly one category
## (qa_build_strip checks it against the catalogue).
const CATEGORIES := [
	["Хозяйство", "kit_emb_town", ["B01", "B02", "B03", "B04", "B05", "B20"]],
	["Промыслы", "kit_emb_craft", ["B06", "B07", "B08", "B09", "B10", "B21", "B22", "B23", "B24", "B26", "B27"]],
	["Войско", "kit_emb_inf", ["B11", "B12", "B13", "B14", "B15", "B16", "B17", "B25"]],
	["Оборона", "kit_emb_wall", ["B18", "B19"]],
]
## One line on each card about what the building gives (the effects are the catalogue's).
const BLURBS := {
	"B01": "Сердце поселения: участки, строители, запасы",
	"B02": "Даёт поселению новых работников",
	"B03": "Хранит дерево, камень, железо и монеты",
	"B04": "Хранит запасы еды",
	"B05": "Приносит монеты и открывает торговлю",
	"B06": "Заготавливает дерево",
	"B07": "Добывает камень",
	"B08": "Добывает железо",
	"B09": "Выращивает еду",
	"B10": "Охота даёт ещё еды",
	"B11": "Обучает пехоту",
	"B12": "Обучает лучников",
	"B13": "Обучает конницу",
	"B14": "Усиливает нападение и защиту войск",
	"B15": "Исследования для войска",
	"B16": "Лечит раненых воинов",
	"B17": "Строит тараны для осады",
	"B18": "Стена и ворота вокруг поселения",
	"B19": "Заранее видит нападение",
	"B20": "Орошает поля: больше еды",
	"B21": "Больше дерева с лесорубов",
	"B22": "Зерно на общем пищевом участке",
	"B23": "Больше добычи с охоты",
	"B24": "Рыба на общем пищевом участке",
	"B25": "Ускоряет лечение раненых",
	"B26": "Больше камня, быстрее стройка",
	"B27": "Больше железа из руды",
}
## Strip order: what can be built first, what is finished last.
const ORDER := {"build": 0, "short": 1, "busy": 2, "locked": 3, "noplot": 4, "maxed": 5, "group": 5, "start": 5}
const TERRAIN := {"dry": "сухая земля", "fertile": "плодородная земля", "forest": "лес", "forest_edge": "опушка",
	"rock": "скалы", "ore": "рудная жила", "shore": "берег", "edge": "край поселения", "perimeter": "граница поселения",
	"center": "центр"}

var panels
var ui
var view: BuildStrip
var strip
var category := 0
var states := {}
## The plot a tap on an empty plot opened the strip from: placement starts there.
var plot_hint := ""
## Placement of a new building: type, plots [{id, position}], chosen plot, quote.
var placing := {}
var place: BuildPlace
var quote_serial := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

# ------------------------------------------------------------------ rules (read-only)

func level_of(type: String) -> int:
	return int(panels.building(type).get("level", 0))

func pending_orders() -> Array:
	return ui.state.v6.orders.filter(func(o): return o.status == "pending")

## Free plots of a terrain: in the server's plot table, with the terrain, no building and no
## construction order on them.
func free_plots(environment: String) -> Array:
	var taken := {}
	for b: Dictionary in ui.state.v6.buildings:
		taken[str(b.get("plot", ""))] = true
	for order: Dictionary in pending_orders():
		if order.get("kind", "") == "construction" and order.has("plot"):
			taken[str(order.plot)] = true
	var out: Array = []
	var plots: Dictionary = ui.state.get("v6_plots", {})
	for id: String in plots:
		if environment in plots[id] and not taken.has(id):
			out.append(id)
	return out

## How many plots are open (the town hall's building_slots) and how many are used.
func plot_use() -> Array:
	var slots := int(panels.row_for("B01", maxi(1, level_of("B01"))).get("effects", {}).get("building_slots", 0))
	var used: int = ui.state.v6.buildings.size()
	for order: Dictionary in pending_orders():
		if order.get("kind", "") == "construction" and int(order.get("target", 0)) == 1:
			used += 1
	return [used, slots]

func builder_use() -> Array:
	var parallel := int(panels.row_for("B01", maxi(1, level_of("B01"))).get("effects", {}).get("construction_parallel", 1))
	var busy := 0
	for order: Dictionary in pending_orders():
		if order.get("kind", "") in ["construction", "repair_wall"]:
			busy += 1
	return [busy, parallel]

func speed_bp() -> int:
	return int(ui.state.v6.get("bonuses", {}).get("construction", 0))

## The server's time rule for a construction at the current bonus.
func build_seconds(seconds: int) -> int:
	return ceili(float(seconds) * 10000.0 / (10000.0 + speed_bp()))

## The state of a type's card (src/build_card.gd) with the reason and the numbers it shows.
func card_state(type: String) -> Dictionary:
	var row: Dictionary = panels.row_for(type, 1)
	var b: Dictionary = panels.building(type)
	var limit := int(row.get("instance_limit", 1))
	var built := 0 if b.is_empty() else 1
	var info := {"type": type, "row": row, "built": built, "limit": limit, "level": int(b.get("level", 0)), "state": "build",
		"note": "", "missing": [], "short": {}, "cost": row.get("cost", {}), "seconds": build_seconds(int(row.get("duration_seconds", 0)))}
	if built >= limit:
		info.state = "maxed"
		return info
	if row.get("free_start", false):
		info.state = "start"
		info.note = "Даётся при основании поселения"
		return info
	var group := group_of(row)
	if not group.is_empty():
		for other: Dictionary in ui.state.v6.buildings:
			if group_of(panels.row_for(str(other.type), 1)) == group:
				info.state = "group"
				info.level = int(other.level)
				info.group_type = str(other.type)
				return info
	for order: Dictionary in pending_orders():
		if order.get("kind", "") == "construction" and str(order.get("building", "")) == type:
			info.state = "busy"
			info.order = order
			return info
	for d: Dictionary in row.get("requirements", []):
		if level_of(str(d.building_id)) < int(d.level):
			info.missing.append({"building": str(d.building_id), "level": int(d.level)})
	for d: Dictionary in row.get("resource_source_requirements", []):
		if level_of(str(d.source_building)) < int(d.source_level):
			info.missing.append({"building": str(d.source_building), "level": int(d.source_level)})
	if not info.missing.is_empty():
		info.state = "locked"
		var first: Dictionary = info.missing[0]
		info.note = "Нужно: %s %s" % [panels.row_for(first.building, 1).get("name_ru", first.building), ROMAN[clampi(int(first.level), 1, 11) - 1]]
		if info.missing.size() > 1:
			info.note += " и ещё %d" % (info.missing.size() - 1)
		return info
	var use := plot_use()
	if int(use[0]) >= int(use[1]):
		info.state = "noplot"
		info.note = "Все участки заняты: улучшите ратушу"
		return info
	if free_plots(str(row.get("environment", ""))).is_empty():
		info.state = "noplot"
		info.note = "Нет свободного участка: %s" % TERRAIN.get(str(row.get("environment", "")), str(row.get("environment", "")))
		return info
	var stock: Dictionary = ui.state.v6.get("stock", {})
	for resource: String in info.cost:
		if int(info.cost[resource]) > int(stock.get(resource, 0)):
			info.short[resource] = true
	if not info.short.is_empty():
		info.state = "short"
	return info

## The shared plot group of a type (FOOD_ESTATE), "" for none (the catalogue sends null).
static func group_of(row: Dictionary) -> String:
	var group: Variant = row.get("exclusive_group")
	return group if group is String else ""

func compute_states() -> void:
	states.clear()
	for entry: Array in CATEGORIES:
		for type: String in entry[2]:
			if not panels.row_for(type, 1).is_empty():
				states[type] = card_state(type)

func buildable_count(index: int) -> int:
	var count := 0
	for type: String in CATEGORIES[index][2]:
		if states.get(type, {}).get("state", "") == "build":
			count += 1
	return count

func category_of(type: String) -> int:
	for index in CATEGORIES.size():
		if type in CATEGORIES[index][2]:
			return index
	return 0

# ------------------------------------------------------------------ the strip window

func is_open() -> bool:
	return is_instance_valid(view) and view.is_inside_tree() and ui.modal.visible and ui.modal_layout == "strip"

## Opens the strip (v6_panels.catalog has loaded the catalogue). `hint`: an empty plot the
## player tapped; the strip opens on the category with the most cards that fit it.
func open_strip(hint := "") -> void:
	plot_hint = hint
	compute_states()
	ui.open_modal("Строительство", "strip", "")
	view = BuildStrip.new()
	ui.modal_body.add_child(view)
	strip = view.swipe
	view.closed.connect(ui.close_modal)
	view.category_chosen.connect(show_category)
	var builders := builder_use()
	var plots := plot_use()
	view.set_heading("Строительство", "Свободно строителей %d из %d · Занято участков %d из %d" % [maxi(0, int(builders[1]) - int(builders[0])), int(builders[1]), int(plots[0]), int(plots[1])])
	if not hint.is_empty():
		category = best_category_for(hint)
	var entries: Array = []
	for index in CATEGORIES.size():
		entries.append([CATEGORIES[index][0], UiKit.tex(CATEGORIES[index][1]), buildable_count(index)])
	view.set_categories(entries, category)
	show_category(category, false)
	prepare_place()

## Builds the placement banner and confirm (hidden) a few frames after the strip is up, so the
## first tap on a card does not pay for them.
func prepare_place() -> void:
	for i in 3:
		await ui.get_tree().process_frame
	if not is_open():
		return
	ensure_place()
	if is_instance_valid(ui.stage) and ui.stage.has_method("prepare_plot_glow"):
		ui.stage.prepare_plot_glow()

## First-open costs of the strip, paid once after launch (main.warm_panel_textures) instead of
## in the first tap on «Строить»: the card class with its grey material and stamp, the card
## style boxes, and the viewports of the blurred city.
func warm() -> void:
	var card := BuildCard.new()
	card.state = "maxed"
	card.refresh()
	for key: String in ["body", "panel", "panel_dim", "band", "frame", "frame_lit", "foot", "shadow", "glow", "track", "fill"]:
		BuildCard.style(key)
	card.free()
	if is_instance_valid(ui.city_backdrop):
		ui.city_backdrop.prepare()

func ensure_place() -> void:
	if place == null or not is_instance_valid(place):
		place = BuildPlace.new()
		place.build = self
		ui.modal.get_parent().add_child(place)
		ui.modal.get_parent().move_child(place, ui.dimmer.get_index())

func best_category_for(plot: String) -> int:
	var tags: Array = ui.state.get("v6_plots", {}).get(plot, [])
	var best := category
	var most := -1
	for index in CATEGORIES.size():
		var fits := 0
		for type: String in CATEGORIES[index][2]:
			var info: Dictionary = states.get(type, {})
			if info.get("state", "") in ["build", "short"] and str(info.row.get("environment", "")) in tags:
				fits += 1
		if fits > most:
			most = fits
			best = index
	return best

func show_category(index: int, animate := true) -> void:
	if not is_instance_valid(view):
		return
	category = clampi(index, 0, CATEGORIES.size() - 1)
	view.select_category(category)
	var types: Array = CATEGORIES[category][2].filter(func(t): return states.has(t))
	types.sort_custom(func(a, b):
		var ra: int = ORDER.get(states[a].state, 9)
		var rb: int = ORDER.get(states[b].state, 9)
		return ra < rb if ra != rb else CATEGORIES[category][2].find(a) < CATEGORIES[category][2].find(b))
	var cards: Array = []
	for type: String in types:
		cards.append(make_card(states[type]))
	strip.set_cards(cards, animate)

func make_card(info: Dictionary) -> BuildCard:
	var card := BuildCard.new()
	var type: String = info.type
	card.name = "Card_" + type
	card.type = type
	card.title = str(info.row.get("name_ru", type))
	card.blurb = BLURBS.get(type, "")
	card.art = BuildingStage.card_art(type)
	card.state = info.state
	card.note = info.note
	card.cost = info.cost
	card.short = info.short
	card.icons = ui.resource_icons
	card.time_text = panels.duration(int(info.seconds))
	card.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	card.custom_minimum_size = BuildCard.SIZE
	card.focus_mode = Control.FOCUS_NONE
	var group := group_of(info.row)
	if info.state == "group":
		card.built_text = "1/1"
		card.level_text = ROMAN[clampi(int(info.level), 1, 11) - 1]
	else:
		card.built_text = "%d/%d" % [int(info.built), int(info.limit)]
		card.level_text = ROMAN[int(info.level) - 1] if int(info.level) > 0 else ""
	if info.state == "busy":
		var order: Dictionary = info.order
		var span := maxf(1.0, float(order.ends_at) - float(order.get("starts_at", order.ends_at)))
		var now: float = ui.timer_now() / 1000.0
		card.progress = clampf((now - float(order.get("starts_at", now))) / span, 0.0, 1.0)
		card.time_text = panels.duration(maxi(0, int(float(order.ends_at) - now)))
	card.tooltip_text = card.title + ("" if group.is_empty() else " · общий пищевой участок")
	card.pressed.connect(card_tapped.bind(type))
	card.refresh()
	return card

func card_tapped(type: String) -> void:
	if strip == null or not strip.tap_allowed():
		return
	var info: Dictionary = states.get(type, {})
	match str(info.get("state", "")):
		"build", "short":
			begin_placement(type)
		"busy":
			panels.queues()
		"group":
			panels.inspect(str(info.get("group_type", type)))
		_:
			panels.inspect(type)

# ------------------------------------------------------------------ placement

## Human name of a plot: «Участок 4» (the number the web client shows for v1-4) and, where the
## plot has one, its place from the server's terrain tags: «Участок 4 · на опушке».
const PLOT_PLACES := [["center", "в центре"], ["ore", "у рудной жилы"], ["rock", "у скал"],
	["shore", "у берега"], ["forest_edge", "на опушке"], ["edge", "на краю поселения"]]

func plot_name(id: String, with_place := true) -> String:
	var title := "Участок " + id.trim_prefix("v1-")
	if not with_place:
		return title
	var place_name := plot_place(id)
	return title if place_name.is_empty() else title + " · " + place_name

func plot_place(id: String) -> String:
	var tags: Array = ui.state.get("v6_plots", {}).get(id, [])
	for pair: Array in PLOT_PLACES:
		if pair[0] in tags:
			return pair[1]
	# A plain plot near the town hall says so.
	var hall: Dictionary = panels.building("B01")
	var at := plot_position(id)
	if not hall.is_empty() and at != Vector3.INF:
		var heart := plot_position(str(hall.get("plot", "")))
		if heart != Vector3.INF and Vector2(at.x - heart.x, at.z - heart.z).length() < 17.0:
			return "у ратуши"
	return ""

func placing_active() -> bool:
	return not placing.is_empty()

func plot_position(id: String) -> Vector3:
	for plot: Dictionary in ui.data.get("plots", []):
		if str(plot.id) == id:
			var x := float(plot.x)
			var z := float(plot.z)
			return Vector3(x, ui.stage.sample_city(x, z) if is_instance_valid(ui.stage) else 0.0, z)
	return Vector3.INF

## The plots offered for the type being placed: [{id, position}].
func placement_plots() -> Array:
	return placing.get("plots", [])

## A card was tapped: the strip slides away, the city comes back into focus, the free plots of
## the building's terrain glow and the player taps one.
func begin_placement(type: String) -> void:
	var row: Dictionary = panels.row_for(type, 1)
	if row.is_empty() or ui.map_name != "city" or not is_instance_valid(ui.stage):
		panels.inspect(type)
		return
	var plots: Array = []
	for id: String in free_plots(str(row.environment)):
		var at := plot_position(id)
		if at != Vector3.INF:
			plots.append({"id": id, "position": at})
	if plots.is_empty():
		panels.inspect(type)
		return
	panels.begin_view()
	var hint := plot_hint
	if is_open():
		leave_strip()
	else:
		ui.close_modal()
	var visual := BuildingStage.level_visual(ui.data, BuildingStage.runtime_type(ui.data, type), 1)
	placing = {"type": type, "row": row, "plots": plots, "plot": "", "quote": {}, "pending": false}
	var rings: Array = []
	for plot: Dictionary in plots:
		rings.append({"position": plot.position, "cleared": true})
	ui.stage.show_plot_glow(str(visual[0]) if not visual.is_empty() else "", float(visual[1]) if not visual.is_empty() else 1.0, rings)
	# The camera moves to the free plot nearest the town hall (the heart of the settlement)
	# and pulls back enough to see its neighbours.
	var heart: Vector3 = ui.stage.target
	var hall: Dictionary = panels.building("B01")
	if not hall.is_empty() and plot_position(str(hall.get("plot", ""))) != Vector3.INF:
		heart = plot_position(str(hall.plot))
	plots.sort_custom(func(a, b): return a.position.distance_squared_to(heart) < b.position.distance_squared_to(heart))
	var nearest: Dictionary = plots[0]
	ui.stage.target = nearest.position
	ui.stage.zoom = clampf(ui.stage.zoom, 46.0, 72.0)
	ensure_place()
	place.begin(str(row.get("name_ru", type)), plots.size())
	if not hint.is_empty() and plots.any(func(p): return p.id == hint):
		pick_plot(hint)

## The strip slides down and away, the city sharpens under it (its 3D pass is back on at
## once; the blurred snapshot fades out over it), then the window closes.
func leave_strip() -> void:
	var leaving: Control = view
	ui.cover_city(false)
	if is_instance_valid(ui.city_backdrop):
		ui.city_backdrop.close(0.22)
	var generation: int = ui.modal_generation
	var slide := leaving.create_tween().set_parallel()
	slide.tween_property(leaving, "position:y", leaving.position.y + 360.0, 0.2).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	slide.tween_property(leaving, "modulate:a", 0.0, 0.18)
	ui.modal_top.hide()
	slide.chain().tween_callback(func():
		if ui.modal_generation == generation and ui.modal_layout == "strip":
			ui.close_modal())

func tap_city(screen: Vector2) -> void:
	if placing.is_empty() or not is_instance_valid(ui.stage):
		return
	var best := ""
	var gap := 64.0
	for plot: Dictionary in placing.plots:
		if ui.stage.camera.is_position_behind(plot.position):
			continue
		var distance: float = ui.stage.camera.unproject_position(plot.position).distance_to(screen)
		if distance < gap:
			gap = distance
			best = plot.id
	if not best.is_empty():
		pick_plot(best)

## The player chose a plot: the ghost stands on it, the floating confirm opens over it and the
## server quotes the build there.
func pick_plot(id: String) -> void:
	if placing.is_empty():
		return
	var plot: Dictionary = {}
	for entry: Dictionary in placing.plots:
		if entry.id == id:
			plot = entry
	if plot.is_empty():
		return
	placing.plot = id
	placing.quote = {}
	placing.pending = true
	# The camera eases to the chosen plot, so the floating confirm has room beside it.
	ui.stage.target = plot.position
	ui.stage.move_placement(plot.position, "ready", false)
	ui.stage.highlight_plot_glow(plot.position)
	var row: Dictionary = placing.row
	place.show_offer(plot.position, row.get("cost", {}), panels.duration(build_seconds(int(row.get("duration_seconds", 0)))), plot_name(id))
	quote_serial += 1
	var serial := quote_serial
	var intent := {"kind": "construction", "building": placing.type, "target": 1, "plot": id, "economy_version": VERSION}
	var response: Dictionary = await ui.request("command", {"kind": "v6quote", "intent": intent})
	if serial != quote_serial or placing.is_empty() or placing.plot != id:
		return
	placing.pending = false
	if response.get("ok", false):
		placing.quote = response.quote
		place.show_quote(response.quote.cost, panels.duration(int(response.quote.duration_seconds)), "")
	else:
		var reason: Dictionary = response.get("reason", {})
		var text := str(reason.get("message", response.get("error", "Нет ответа сервера")))
		if reason.has("resource"):
			text = "Не хватает: %s" % ui.RESOURCE_NAMES.get(reason.resource, reason.resource)
		place.show_quote(row.get("cost", {}), panels.duration(build_seconds(int(row.get("duration_seconds", 0)))), text)

func quote_ready() -> bool:
	return not placing.is_empty() and not placing.get("pending", true)

## «Построить»: the quoted terms are sent; the city shows the scaffolding when the server
## accepts it.
func confirm_build() -> void:
	if placing.is_empty() or placing.quote.is_empty():
		return
	var intent := {"kind": "construction", "building": placing.type, "target": 1, "plot": placing.plot,
		"economy_version": VERSION, "expected_duration_seconds": int(placing.quote.duration_seconds)}
	var title := str(placing.row.get("name_ru", placing.type))
	var at: Vector3 = Vector3.INF
	for plot: Dictionary in placing.plots:
		if plot.id == placing.plot:
			at = plot.position
	cancel_placement()
	if at != Vector3.INF:
		ui.stage.target = at
	if await ui.command({"kind": "v6", "intent": intent}):
		ui.message.text = "Строительство началось: %s" % title

## The plot list of the type (the inspector's «Участок N» buttons): the fallback to tapping
## a plot in the city.
func plot_list() -> void:
	var type := str(placing.get("type", ""))
	cancel_placement()
	if not type.is_empty():
		await panels.inspect(type)

func cancel_placement() -> void:
	quote_serial += 1
	if placing.is_empty():
		return
	placing = {}
	if is_instance_valid(ui.stage):
		ui.stage.clear_placement()
	if is_instance_valid(place):
		place.finish()

func blocks_touch(at: Vector2) -> bool:
	return not placing.is_empty() and is_instance_valid(place) and place.covers(at)

