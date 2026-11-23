extends RefCounted

const VERSION := "DRENOVAR-V6-C1.0"
const UnitStage = preload("res://src/unit_stage.gd")
const V6Build = preload("res://src/v6_build.gd")
const BuildingStage = preload("res://src/building_stage.gd")
# The recruitment, queues, academy/lazaret and army windows are compiled off the launch
# path (premium UI stage 4a): main.gd asks warm_views() once the city is shown, their
# scripts load on a worker thread, and the first open finds them ready. (As preloads they
# added about 190 ms of compiling to every launch here.) A window opened before that
# compiles its script once, then and there.
const VIEW_SCRIPTS := {
	"recruit": "res://src/v6_recruit.gd",
	"queue_view": "res://src/v6_queues.gd",
	"service_view": "res://src/v6_services.gd",
	"army_view": "res://src/v6_army.gd",
	"menu_view": "res://src/v6_menu.gd",
	"economy_view": "res://src/v6_economy.gd",
	"world_view": "res://src/world_cards.gd",
}
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
var ui: Node
var catalogue: Dictionary = {}
var catalogue_loading := false
var quote_request := 0
var navigation_request := 0
var submitting := false
# Recruitment window of the training buildings (src/v6_recruit.gd).
var recruit:
	get:
		return view("recruit")
# Construction strip and placement of new buildings (src/v6_build.gd).
var build
# Queues and speed-ups window (src/v6_queues.gd).
var queue_view:
	get:
		return view("queue_view")
# Academy and infirmary windows (src/v6_services.gd).
var service_view:
	get:
		return view("service_view")
# Army and march windows (src/v6_army.gd).
var army_view:
	get:
		return view("army_view")
# Menu, account, pairing code and confirmations (src/v6_menu.gd, stage 4b).
var menu_view:
	get:
		return view("menu_view")
# Market, economy, objectives and archive (src/v6_economy.gd, stage 4b).
var economy_view:
	get:
		return view("economy_view")
# World map windows (src/world_cards.gd, stage 4b).
var world_view:
	get:
		return view("world_view")
var views := {}
var scripts := {}
var warming: Array[String] = []

func begin_view() -> int:
	navigation_request += 1
	return navigation_request
signal catalogue_loaded(success: bool)

func _init(owner_node: Node) -> void:
	ui = owner_node
	build = V6Build.new(self)

## A window of VIEW_SCRIPTS, made on first use.
func view(key: String) -> RefCounted:
	if not views.has(key):
		views[key] = script_of(VIEW_SCRIPTS[key]).new(self)
	return views[key]

## A script loaded at most once: taken from the worker thread's load when warm_views asked
## for it (waiting if it is still compiling), else loaded here.
func script_of(path: String) -> GDScript:
	if not scripts.has(path):
		var script: GDScript = null
		if ResourceLoader.load_threaded_get_status(path) != ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
			script = ResourceLoader.load_threaded_get(path) as GDScript
		scripts[path] = script if script != null else load(path)
	return scripts[path]

## After launch (main.gd): compiles the window scripts on a worker thread, `extra` too.
func warm_views(extra: Array = []) -> void:
	for path: String in VIEW_SCRIPTS.values() + extra:
		if not scripts.has(path) and not path in warming and ResourceLoader.load_threaded_request(path, "GDScript") == OK:
			warming.append(path)
	while not warming.is_empty():
		if not is_instance_valid(ui) or not ui.is_inside_tree():
			return
		await ui.get_tree().process_frame
		for path: String in warming.duplicate():
			if scripts.has(path) or ResourceLoader.load_threaded_get_status(path) != ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				warming.erase(path)
				script_of(path)

## Starts one view's compile on a worker now. main.gd asks it for the first launch's «Аккаунт»
## while the city's first frames are drawn behind the launch screen, so the account opens
## without compiling the menu's script (about 70 ms here) on the main thread.
func request_view(key: String) -> void:
	var path: String = VIEW_SCRIPTS[key]
	if not scripts.has(path) and not path in warming and ResourceLoader.load_threaded_request(path, "GDScript") == OK:
		warming.append(path)

## On exit (main.gd): a compile still running on the worker is waited for, not cut short.
func finish_warm() -> void:
	for path: String in warming.duplicate():
		script_of(path)
	warming.clear()

## Whether a building trains units (its window is the recruitment window).
func trains(type: String) -> bool:
	return script_of(VIEW_SCRIPTS.recruit).trains(type)

## New confirmed server state (main.gd accept): the open recruitment window follows it.
func state_changed() -> void:
	if views.has("recruit") and views.recruit.is_open():
		views.recruit.refresh()
	if views.has("queue_view") and views.queue_view.is_open():
		views.queue_view.refresh()

## Starts loading the 3D unit of a training building on a worker thread, so its window
## opens in one frame and the live model is ready (or nearly) when the stage asks for it.
func warm_recruitment(type: String) -> void:
	if not trains(type) or catalogue.is_empty():
		return
	var chosen: String = recruit.chosen.get(type, "")
	if chosen.is_empty():
		chosen = recruit.default_unit(recruit.units_of(type))
	if not chosen.is_empty():
		UnitStage.request(UnitStage.model_for(ui.data, chosen))

## Test and screenshot hooks of the recruitment window.
func recruit_pick(unit_id: String) -> void:
	recruit.pick(unit_id)

func recruit_details() -> void:
	recruit.toggle_details()

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
	var level := int(b.level)
	# Past the open level (main.gd MAX_OPEN_BUILDING_LEVEL) the ring offers the window, not an
	# upgrade: «Сведения» always, «Улучшить» below the open level, a dim «Скоро» from it on.
	var upgradable: bool = level < 11 and level_open(type, level + 1)
	var actions: Array = [["Сведения", "info", inspect_instance.bind(str(b.id)), {"primary": false}]]
	if upgradable:
		actions.append(["Улучшить", "upgrade", inspect_instance.bind(str(b.id)), {"primary": true}])
	elif level < 11:
		actions.append(["Скоро", "upgrade", inspect_instance.bind(str(b.id)), {"soon": true}])
	if type in ["B11", "B12", "B13", "B15", "B16", "B17"]:
		var emblem: String = {"B11": "kit_emb_inf", "B12": "kit_emb_bow", "B13": "kit_emb_horse", "B15": "kit_emb_book", "B16": "kit_emb_heal", "B17": "kit_emb_ram"}[type]
		actions.append(["Обучение" if trains(type) else ("Исследования" if type == "B15" else ("Лечение" if type == "B16" else "Работы здания")),
			"heal" if type == "B16" else "train", services.bind(type), {"emblem": emblem}])
		warm_recruitment(type)
	# A running job here: «Ускорить» with its time left (or «Очередь» for jobs no item speeds up).
	var job := running_job(b)
	if not job.is_empty():
		var started: bool = float(job.get("starts_at", 0)) * 1000.0 <= ui.timer_now()
		if job.kind in ["construction", "train", "siege"] and started:
			actions.append(["Ускорить", "speed", speedups.bind(job), {"ends": float(job.ends_at) * 1000.0}])
		else:
			actions.append(["Очередь", "queue", queue_view.open.bind(job), {"ends": float(job.ends_at) * 1000.0}])
	if type == "B05":
		actions.append(["Рынок", "trade", trade])
	if type in ["B18", "B19"]:
		actions.append(["Оборона", "defence", inspect_instance.bind(str(b.id))])
	if type in ["B06", "B07", "B08", "B09", "B10", "B22", "B24"]:
		actions.append(["Производство", "collect", economy])
	actions.append(["Переместить", "move", move_building.bind(b, str(row_for(type,int(b.level)).environment))])
	ui.action_ring.open(str(b.id), "%s · %s" % [row_for(type,1).name_ru, ROMAN[int(b.level)-1]], marker.position, ui.stage.camera, actions)

## The job running in a building now: its construction, or the first started order of the
## building's own queue (training, research, healing, repairs).
func running_job(b: Dictionary) -> Dictionary:
	var best := {}
	for order: Dictionary in ui.state.v6.orders:
		if order.status != "pending":
			continue
		var here: bool = str(order.get("instance_id", "")) == str(b.id) or (str(order.get("building", "")) == str(b.type) and order.kind != "construction")
		if here and (best.is_empty() or float(order.starts_at) < float(best.starts_at)):
			best = order
	return best

## A level the game offers now: at most MAX_OPEN_BUILDING_LEVEL, and every building it needs
## can be reached too (a requirement past the open level counts only when it already stands).
func level_open(type: String, target: int) -> bool:
	if target > ui.MAX_OPEN_BUILDING_LEVEL:
		return false
	var row := row_for(type, target)
	for d: Dictionary in row.get("requirements", []):
		if int(d.level) > ui.MAX_OPEN_BUILDING_LEVEL and int(building(str(d.building_id)).get("level", 0)) < int(d.level):
			return false
	for d: Dictionary in row.get("resource_source_requirements", []):
		if int(d.source_level) > ui.MAX_OPEN_BUILDING_LEVEL and int(building(str(d.source_building)).get("level", 0)) < int(d.source_level):
			return false
	return true

func building(type: String) -> Dictionary:
	for b: Dictionary in ui.state.v6.buildings:
		if b.type == type:
			return b
	return {}

# Index of the catalogue rows by type and level (built once per catalogue): the windows
# look rows up dozens of times while they open.
var row_index := {}
var row_index_source: Array = []

func row_for(type: String, level: int) -> Dictionary:
	var rows: Array = catalogue.get("buildings", [])
	if not is_same(rows, row_index_source):
		row_index.clear()
		for row: Dictionary in rows:
			row_index["%s|%d" % [row.building_id, int(row.level)]] = row
		row_index_source = rows
	return row_index.get("%s|%d" % [type, level], {})

func warnings() -> void:
	for warning: Dictionary in ui.state.v6.get("warnings", []):
		var alarm: Label = ui.UiKit.label(ui.modal_body, "Башня обнаружила нападение · до прибытия %d с" % int(warning.eta_seconds), 18, ui.UiKit.BAD, ui.UiKit.LABEL_FONT)
		alarm.name = "AttackWarning"

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

## «Экономика поселения» (src/v6_economy.gd): the hourly income, a card per resource with its
## storage bar and rate, workers and the army.
func economy() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	economy_view.economy()

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
			ui.button(ui.modal_body, build.plot_name(plot), send.bind({"kind":"move", "building_id":b.id, "plot":plot}))

## The construction strip (src/v6_build.gd): every type of the catalogue as a card over the
## blurred city. `plot`: an empty plot the player tapped (placement starts there).
func catalog(plot := "") -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	build.open_strip(plot)

## The building window (premium UI stage 3): the live «Сейчас · ур. N» ➜ «После · ур. N+1»
## pair of the exact scenes the city draws (src/building_stage.gd; the parts the next level
## adds glow gold), the effects with their green gains, the cost with icons (red where short),
## the time with the construction bonus, «Улучшить», and the requirements as chips (a missing
## one goes to its building). Unbuilt types show «Будет построено · ур. I», «Построить» and
## the plot list; XI shows the building alone.
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
	ui.open_modal(str(row.name_ru), "full", "УРОВЕНЬ " + (ROMAN[level-1] if level > 0 else "НЕ ПОСТРОЕНО"))
	# The next level is offered only up to the open level; past it «После» is a «Скоро» card.
	var open := level < 11 and level_open(type, level + 1)
	var stage := BuildingStage.new()
	stage.setup(ui.data, type, level, 11, false, level > 0 and level < 11 and not open)
	ui.modal_hero.add_child(stage)
	stage.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.modal_hero_share = 0.5
	ui.arrange_modal()
	warm_recruitment(type)
	var upcoming: Dictionary = row_for(type, level + 1) if open else {}
	# Effects: now, and what the next level adds (green). Unbuilt: what level I gives.
	var stats := VBoxContainer.new()
	stats.name = "Effects"
	stats.add_theme_constant_override("separation", 0)
	ui.modal_body.add_child(stats)
	var shown: Dictionary = row if level > 0 else row_for(type, 1)
	for metric: String in shown.get("effects", {}):
		if metric == "workers_required":
			continue
		var now: Variant = shown.effects[metric]
		var gain := ""
		if level > 0 and not upcoming.is_empty():
			gain = delta_value(metric, now, upcoming.get("effects", {}).get(metric))
		ui.UiKit.stat_row(stats, str(catalogue.get("metrics", {}).get(metric, {}).get("name_ru", metric)), metric_value(metric, now), gain, true, true)
	if level < 11 and not open:
		soon_section(level)
	elif level < 11:
		var next: Dictionary = upcoming
		section_title(("Улучшение до ур. " + ROMAN[level]) if level > 0 else "Строительство · ур. I")
		cost_cards(next.cost)
		var missing: Array = []
		for d: Dictionary in next.requirements:
			if str(d.building_id) != type and int(building(d.building_id).get("level", 0)) < int(d.level):
				missing.append(d)
		var action := {"kind":"construction", "building":type, "target":level+1}
		# Time (with the construction bonus) and the call to action on one row, in view without
		# scrolling; it stays in the body, where qa_building_actions looks for it.
		var go := HBoxContainer.new()
		go.name = "KitTimeAction"
		go.add_theme_constant_override("separation", 14)
		ui.modal_body.add_child(go)
		var seconds: int = build.build_seconds(int(next.duration_seconds))
		ui.UiKit.timer_pill(go, "Время" if seconds == int(next.duration_seconds) else "Время · с бонусом", duration(seconds))
		var pill: Control = go.get_child(0)
		pill.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		pill.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		pill.tooltip_text = "Базовое время %s" % duration(int(next.duration_seconds))
		var main: Button
		if not missing.is_empty():
			var first: Dictionary = missing[0]
			main = ui.panel_action(go, "Сначала: %s %s" % [row_for(first.building_id, 1).get("name_ru", first.building_id), ROMAN[int(first.level)-1]], inspect.bind(str(first.building_id)))
			ui.UiKit.style_button(main, "secondary", 19)
		elif level > 0:
			main = ui.panel_action(go, "Улучшить", confirm.bind(action))
		else:
			main = ui.panel_action(go, "Построить", build.begin_placement.bind(type))
		main.custom_minimum_size.x = 300
		requirement_chips(type, next)
		if level == 0:
			section_title("Или участок из списка")
			var plots := HFlowContainer.new()
			plots.name = "PlotList"
			plots.add_theme_constant_override("h_separation", 10)
			plots.add_theme_constant_override("v_separation", 8)
			ui.modal_body.add_child(plots)
			for plot: String in build.free_plots(str(next.environment)):
				var placement: Dictionary = action.duplicate()
				placement.plot = plot
				var choice: Button = ui.button(plots, build.plot_name(plot), confirm.bind(placement))
				choice.custom_minimum_size = Vector2(180, 48)
			if plots.get_child_count() == 0:
				muted("Нет свободного участка: %s." % build.TERRAIN.get(str(next.environment), str(next.environment)))
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

## Requirements of the next level as chips: the building's diorama, its name and level, a
## tick or a cross; a missing one opens that building's window.
## Past the open level: no cost, no time, no requirements; one line and a disabled «Скоро»
## where «Улучшить» would be (in the same row, so the window keeps its shape).
func soon_section(level: int) -> void:
	section_title("Следующий уровень · скоро" if level > 0 else "Строительство · скоро")
	var go := HBoxContainer.new()
	go.name = "KitTimeAction"
	go.add_theme_constant_override("separation", 14)
	ui.modal_body.add_child(go)
	var line: Label = ui.UiKit.label(go, ui.SOON_LINE + ".", 17, ui.UiKit.INK_MUTED)
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var main: Button = ui.panel_action(go, "Скоро", func(): pass, false)
	main.name = "SoonAction"
	main.tooltip_text = ui.SOON_LINE
	main.custom_minimum_size.x = 300

func requirement_chips(type: String, next: Dictionary) -> void:
	var needs := HFlowContainer.new()
	needs.name = "KitRequirements"
	needs.add_theme_constant_override("h_separation", 10)
	needs.add_theme_constant_override("v_separation", 8)
	var seen := {}
	for d: Dictionary in next.get("requirements", []):
		var other := str(d.building_id)
		if other == type or seen.has(other):
			continue
		seen[other] = true
		var met: bool = int(building(other).get("level", 0)) >= int(d.level)
		var chip: BaseButton = ui.UiKit.need_chip(ui.v6_card(other), "%s · %s" % [row_for(other, 1).get("name_ru", other), ROMAN[int(d.level)-1]], met)
		chip.name = "Need_" + other
		if not met:
			chip.pressed.connect(inspect.bind(other))
		needs.add_child(chip)
	if needs.get_child_count() > 0:
		muted("Требуется")
		ui.modal_body.add_child(needs)
	else:
		needs.free()

## The green gain of an effect from one level to the next ("+300", "+10%"), or "" when it
## does not change.
func delta_value(metric: String, now: Variant, later: Variant) -> String:
	if later == null or str(later) == str(now):
		return ""
	if (now is float or now is int) and (later is float or later is int):
		var change := float(later) - float(now)
		if is_zero_approx(change):
			return ""
		var sign := "+" if change > 0.0 else "−"
		if metric.ends_with("_bp"):
			return sign + String.num(absf(change) / 100.0, 2).trim_suffix("0").trim_suffix("0").trim_suffix(".") + "%"
		if metric.ends_with("_rate_h") or metric.ends_with("_hp_h"):
			return sign + "%s/ч" % plain_number(absf(change))
		return sign + plain_number(absf(change))
	return metric_value(metric, later)

## The quote window: the server's exact cost and time before a work starts. For a building it
## shows what the work gives (the server's effects before and after), the cost against the
## stock, the time with the bonus, the builders and workers it takes, and «Начать».
func confirm(action: Dictionary) -> void:
	# Past the open level nothing is asked of the server (main.gd MAX_OPEN_BUILDING_LEVEL).
	if str(action.get("kind", "")) == "construction" and not level_open(str(action.get("building", "")), int(action.get("target", 0))):
		ui.capped_requests += 1
		ui.message.text = ui.SOON_LINE
		return
	var navigation := begin_view()
	quote_request += 1
	var request_id := quote_request
	var type := str(action.get("building", ""))
	var target := int(action.get("target", 0))
	var eyebrow := "УЛУЧШЕНИЕ ПОСЕЛЕНИЯ"
	if action.get("kind", "") == "construction" and target > 0:
		eyebrow = "СТРОИТЕЛЬСТВО · УР. I" if target == 1 else "УЛУЧШЕНИЕ ДО УР. " + ROMAN[clampi(target, 1, 11) - 1]
		if action.has("plot"):
			eyebrow += " · " + build.plot_name(str(action.plot), false).to_upper()
	elif action.get("kind", "") == "repair_wall":
		eyebrow = "РЕМОНТ СТЕНЫ"
	ui.open_modal("Подтвердить работу", "full", eyebrow, ui.v6_card(type))
	if target > 0 and ui.has_method("building_hero"):
		ui.building_hero(type, target)
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
	var before: Dictionary = q.get("effects_before", {})
	var after: Dictionary = q.get("effects_after", {})
	if not after.is_empty():
		section_title("Что даст работа")
		var stats := VBoxContainer.new()
		stats.name = "Effects"
		stats.add_theme_constant_override("separation", 0)
		ui.modal_body.add_child(stats)
		for metric: String in after:
			if metric == "workers_required":
				continue
			var now: Variant = before.get(metric, 0)
			var name := str(catalogue.get("metrics", {}).get(metric, {}).get("name_ru", metric))
			if before.is_empty():
				ui.UiKit.stat_row(stats, name, metric_value(metric, after[metric]), "", true)
			else:
				ui.UiKit.stat_row(stats, name, metric_value(metric, now), delta_value(metric, now, after[metric]), true, true)
	section_title("Стоимость работы")
	cost_cards(q.cost)
	time_card("До завершения", int(q.duration_seconds))
	if int(q.speed_bp) > 0:
		muted("Базовое время %s · бонус скорости +%s%%" % [duration(int(q.get("base_seconds", q.duration_seconds))), String.num(float(q.speed_bp)/100.0, 2).trim_suffix("0").trim_suffix("0").trim_suffix(".")])
	if q.get("kind", "") in ["construction", "repair_wall"]:
		var builders: Array = build.builder_use()
		var note := "Строители: свободно %d из %d" % [maxi(0, int(builders[1]) - int(builders[0])), int(builders[1])]
		if int(q.get("reserved_workers", 0)) > 0:
			var force: Dictionary = ui.state.v6.get("workforce", {})
			note += " · работники +%d (заняты %d из %d)" % [int(q.reserved_workers), int(force.get("used", 0)), int(force.get("capacity", 0))]
		muted(note)
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

## Every running job of the settlement with its speed-ups (src/v6_queues.gd).
func queues() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	# The catalogue (names) is loaded after sign-in (main.gd); the queues need only the state.
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	queue_view.open()

func services(type: String) -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	if trains(type) and int(building(type).get("level", 0)) > 0:
		# Training buildings: the recruitment window (switches in place when it is open).
		recruit.open(type)
		return
	if type == "B15" and int(building(type).get("level", 0)) > 0:
		service_view.research()
		return
	if type == "B16" and int(building(type).get("level", 0)) > 0:
		service_view.hospital()
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
	# The whole unit (expand_icon keeps the figure's aspect inside the button's height).
	var face: Texture2D = ui.unit_portrait(unit_id)
	if face != null:
		control.icon = face
		control.expand_icon = true
		control.add_theme_constant_override("icon_max_width", 58)
		control.add_theme_constant_override("h_separation", 16)
	control.end_bulk_theme_override()

## «Рынок» (src/v6_economy.gd): the day's turnover, one quantity and a card per resource with
## «Купить»/«Продать» and the estimated coins.
func trade() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	economy_view.trade()

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

## «Аккаунт» (src/v6_menu.gd): the profile column and the account's actions as cards.
func account() -> void:
	begin_view()
	menu_view.account()

func archive() -> void:
	var navigation := begin_view()
	await load_catalogue()
	if navigation != navigation_request:
		return
	economy_view.archive()

func pairing_code() -> void:
	var response: Dictionary = await ui.send_request("pair/create", {})
	if response.has("error"):
		ui.show_error(response)
		return
	menu_view.pairing(response)

## «Цели поселения» (src/v6_economy.gd): quest cards with rewards; the current one claims.
func objectives() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await ui.ensure_v6_ready():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	economy_view.objectives()

## Speed-up items for a running order: the queues window on that job. `back` reopens the
## window it came from (the recruitment window) when the job is done.
func speedups(order: Dictionary, back := Callable()) -> void:
	begin_view()
	queue_view.open(order, back, "Ускорить работу")

func army() -> void:
	var navigation := begin_view()
	var generation: int = ui.modal_generation
	if not await load_catalogue():
		return
	if navigation != navigation_request or generation != ui.modal_generation:
		return
	army_view.army()

func formation(target: String, name: String) -> void:
	begin_view()
	army_view.formation(target, name)
