extends RefCounted
## The world map's windows as premium cards (premium UI stage 4b, ui_premium/STAGE4B.md):
## a creature, a settlement, a free place, a march, the hunt list, the cities, the marches,
## the world directory and the map layers.
##
## Every window starts with a head card (src/kit_more.gd HeadCard: a portrait or a crest on
## an ink wash, the name, a line, a kokoshnik badge with the level), then chips (distance
## from the player's city, coordinates, rewards) and the facts; the main action (gather a
## party, attack, enter the city, confirm the move) is a primary button in the footer, as
## the march tests expect it there (modal_footer's first child).
## A march's travel time comes from the server's route quote in the march window: nothing
## here guesses it.

const UiKit = preload("res://src/ui_kit.gd")
const KitMore = preload("res://src/kit_more.gd")
const CreatureVisuals = preload("res://src/creature_visuals.gd")
const ROMAN := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
const MATERIALS := {"claws":"когтей", "horns":"рогов", "fangs":"клыков", "scales":"чешуи"}

var panels
var ui
var last_open_usec := 0

func _init(owner_panels) -> void:
	panels = owner_panels
	ui = owner_panels.ui

func roman(level: int) -> String:
	return ROMAN[clampi(level, 1, 11) - 1]

## Coordinates as the map shows them.
func coordinates(position: Dictionary) -> String:
	return "%d : %d" % [roundi(float(position.get("x", 0)) + 150), roundi(float(position.get("z", 0)) + 120)]

## Distance from the player's city on the world map (map units), "" without a city.
func distance(position: Dictionary) -> String:
	for city: Dictionary in ui.state.get("world", {}).get("cities", []):
		if city.id == ui.player_id:
			var d := Vector2(float(position.get("x", 0)) - float(city.position.x), float(position.get("z", 0)) - float(city.position.z)).length()
			return "%d от города" % roundi(d)
	return ""

func head(picture: Texture2D, title: String, subtitle: String, level := "", tint := Color("#6d7a5a")) -> KitMore.HeadCard:
	var card := KitMore.HeadCard.new()
	card.name = "WorldHead"
	card.picture = picture
	card.title = title
	card.subtitle = subtitle
	card.level = level
	card.tint = tint
	card.custom_minimum_size.y = 132
	ui.modal_body.add_child(card)
	return card

func chips(entries: Array) -> KitMore.ChipRow:
	var row := KitMore.ChipRow.new()
	row.name = "WorldChips"
	row.chips = entries.filter(func(entry): return not str(entry[1]).is_empty())
	ui.modal_body.add_child(row)
	return row

## A calm note: muted ink, or warm when it explains why an action is closed.
func note(text: String, warn := false) -> Label:
	var label: Label = UiKit.label(ui.modal_body, text, 16, UiKit.WARN if warn else UiKit.INK_MUTED)
	return label

func styled(control: Button, kind := "tertiary", height := 48.0) -> Button:
	UiKit.style_button(control, kind, 18)
	control.custom_minimum_size.y = height
	return control

## Secondary actions in a row that fills the width.
func actions() -> HFlowContainer:
	var flow := HFlowContainer.new()
	flow.name = "WorldActions"
	flow.add_theme_constant_override("h_separation", 10)
	flow.add_theme_constant_override("v_separation", 10)
	ui.modal_body.add_child(flow)
	return flow

func action(parent: Container, caption: String, callback: Callable, enabled := true, kind := "tertiary") -> Button:
	var control: Button = styled(ui.button(parent, caption, callback, enabled), kind)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	control.custom_minimum_size.x = 180
	return control

func creature_portrait(encounter: Dictionary) -> Texture2D:
	var species := str(encounter.get("species", encounter.spec.get("id", "velkor")))
	var portraits: Array = CreatureVisuals.entry(species).get("portraits", []) if CreatureVisuals.active(species) else []
	var path := str(portraits[clampi(int(encounter.level), 1, 3) - 1]) if portraits.size() == 3 else ""
	if not path.is_empty() and ResourceLoader.exists(path):
		return load(path)
	return ui.panel_texture("velkor%d.webp" % clampi(int(encounter.level), 1, 3))

# ------------------------------------------------------------------ creature

func encounter(encounter: Dictionary) -> void:
	var started := Time.get_ticks_usec()
	var city_hunt: bool = ui.map_name == "city"
	var spec: Dictionary = encounter.spec
	var level := int(spec.get("requiredHall", 1))
	var available: bool = encounter.status != "defeated" and int(encounter.hp) > 0
	ui.open_modal(spec.name if city_hunt else ui.encounter_title(encounter), "city_target" if city_hunt else "right",
		"ДИКИЕ ЗЕМЛИ" if city_hunt else "ДРЕНОВАР · ДИКИЕ ЗЕМЛИ")
	var details: Container = ui.modal_body
	if city_hunt:
		# The live creature on the left of the city window (as before), in an ink-washed frame.
		var card := HBoxContainer.new()
		card.add_theme_constant_override("separation", 14)
		ui.modal_body.add_child(card)
		var frame := PanelContainer.new()
		frame.name = "CreatureFrame"
		frame.add_theme_stylebox_override("panel", UiKit.nine("kit_strip", Vector4(26, 14, 26, 14), Vector4(10, 10, 10, 10)))
		frame.custom_minimum_size.x = 150
		frame.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		card.add_child(frame)
		details = VBoxContainer.new()
		details.add_theme_constant_override("separation", 8)
		details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card.add_child(details)
		var portrait := VBoxContainer.new()
		frame.add_child(portrait)
		var preview: Control = ui.create_unit_preview(portrait, 145)
		var species: String = encounter.get("species", spec.get("id", ""))
		if ui.data.creatureModels.has(species):
			var tier := clampi(int(encounter.level), 1, 3)
			var model: String = CreatureVisuals.model_path(species, tier, ui.data.creatureModels[species][tier - 1])
			ui.load_unit_preview.call_deferred(preview, {"preview":model, "drill":"idle", "creature":species, "level":tier}, 0.63)
		var badge: Label = UiKit.label(portrait, "УРОВЕНЬ %s" % roman(int(encounter.level)), 15, UiKit.GOLD, UiKit.LABEL_FONT, false)
		badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	else:
		var where := coordinates(encounter.get("position", {}))
		head(creature_portrait(encounter), ui.encounter_title(encounter),
			"Дикие земли · %s" % where, roman(int(encounter.level)), Color("#56624a"))
	var tiers := HBoxContainer.new()
	tiers.name = "Tiers"
	tiers.add_theme_constant_override("separation", 8)
	details.add_child(tiers)
	var tier_caption: Label = UiKit.label(tiers, "Уровень", 16, UiKit.INK_MUTED, UiKit.LABEL_FONT, false)
	tier_caption.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var encounters: Array = ui.state.get("encounters", []) if city_hunt else ui.state.world.encounters
	for other: Dictionary in encounters:
		if other.get("species") != encounter.get("species"):
			continue
		var tier: Button = ui.button(tiers, roman(int(other.level)), ui.inspect_current_encounter.bind(other.id))
		tier.accessibility_name = ui.encounter_title(other)
		styled(tier, "primary" if other.id == encounter.id else "tertiary", 44)
		tier.custom_minimum_size.x = 58
	var health := KitMore.Card.new()
	health.name = "Health"
	health.icon = UiKit.tex("kit_emb_shield")
	health.icon_mode = "disc"
	health.title = "Здоровье"
	health.bar = (float(encounter.hp) / float(maxi(1, int(spec.hp)))) if available else 0.0
	health.bar_green = true
	health.bar_text = "%d / %d" % [int(encounter.hp) if available else 0, int(spec.hp)]
	health.custom_minimum_size.y = 84
	details.add_child(health)
	var rewards: Dictionary = spec.get("rewards", {})
	var reward_chips: Array = []
	if not rewards.is_empty():
		reward_chips.append([ui.resource_icons.get("food"), "+%d еды" % int(rewards.get("food", 0)), UiKit.GOLD])
		reward_chips.append([UiKit.tex("kit_emb_chest"), "%d %s" % [int(rewards.get("material", 0)), MATERIALS.get(spec.get("item", ""), "трофеев")], UiKit.GOLD])
		reward_chips.append([UiKit.tex("kit_emb_up"), "%d опыта" % int(spec.get("xp", 0)), UiKit.GOLD])
	if not city_hunt:
		reward_chips.append([UiKit.tex("kit_emb_march"), distance(encounter.get("position", {})), Color("#f6e2b8")])
	if not reward_chips.is_empty():
		var row := KitMore.ChipRow.new()
		row.name = "Rewards"
		row.chips = reward_chips.filter(func(entry): return not str(entry[1]).is_empty())
		details.add_child(row)
	if city_hunt:
		var dossier := VBoxContainer.new()
		var about_button: Button = styled(ui.button(details, "О существе", func(): dossier.visible = not dossier.visible), "tertiary", 44)
		about_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		about_button.custom_minimum_size.x = 180
		details.add_child(dossier)
		dossier.hide()
		UiKit.label(dossier, "Мощь %d · Атака %d · Защита %d" % [int(spec.strength), int(spec.attack), int(spec.defense)], 16, UiKit.INK)
	else:
		var about := str(CreatureVisuals.entry(str(encounter.get("species", spec.get("id", "")))).get("description", ""))
		UiKit.label(details, about if not about.is_empty() else "Рывком бьёт по передней линии. Копейщики могут принять удар, пока стрелки ведут огонь.", 16, UiKit.INK_MUTED)
	if encounter.status == "reserved":
		UiKit.label(details, "Эту цель уже преследует другой отряд.", 16, UiKit.WARN)
	elif not available:
		if encounter.get("respawnAt", 0) > ui.server_time():
			var remaining: Label = UiKit.label(details, "", 16, UiKit.BRONZE, UiKit.LABEL_FONT)
			ui.bind_countdown(remaining, "Возрождение через", encounter.respawnAt)
		else:
			UiKit.label(details, "Существо побеждено.", 16, UiKit.INK_MUTED)
	if ui.hall_level() < level:
		UiKit.label(details, "Требуется ратуша уровня %d." % level, 16, UiKit.WARN)
	elif ui.player_id.is_empty():
		UiKit.label(details, "Войдите в аккаунт, чтобы отправить отряд.", 16, UiKit.WARN)
	var p: Vector3 = ui.stage.point(encounter.position)
	if available:
		for marker in ui.stage.creature_markers:
			if marker.id == encounter.id:
				p = marker.position
				break
		ui.stage.target = ui.stage.ground_point(p)
		ui.stage.zoom = minf(ui.stage.zoom, 42.0 if city_hunt else 85.0)
	ui.modal_footer.show()
	var attack: Button = ui.panel_action(ui.modal_footer, "Атаковать" if city_hunt else "Собрать отряд",
		ui.compose_march.bind("city" if city_hunt else ui.world_kind(encounter), encounter.id, ui.encounter_title(encounter)),
		not ui.player_id.is_empty() and available and encounter.status == "alive" and ui.hall_level() >= level)
	attack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	attack.icon = UiKit.tex("kit_emb_sword")
	attack.expand_icon = true
	attack.add_theme_constant_override("icon_max_width", 30)
	last_open_usec = Time.get_ticks_usec() - started

## The hunt list: a card per creature with its portrait, level, state and «Осмотреть».
func hunts(encounters: Array) -> void:
	var city_hunt: bool = ui.map_name == "city"
	for item: Dictionary in encounters:
		var status: String = {"alive":"Доступен", "reserved":"Занят", "defeated":"Побеждён"}.get(item.status, str(item.status))
		var card := KitMore.Card.new()
		card.name = "Hunt_" + str(item.id)
		card.icon = creature_portrait(item) if not city_hunt or item.has("spec") else null
		card.icon_mode = "portrait"
		card.title = "%s · %s" % [item.spec.name, roman(int(item.level))]
		card.subtitle = status
		card.subtitle_colour = {"alive": UiKit.GOOD, "reserved": UiKit.WARN}.get(item.status, UiKit.INK_MUTED)
		card.plate = "dim" if item.status == "defeated" else "row"
		var facts: Array = []
		var rewards: Dictionary = item.spec.get("rewards", {})
		if not rewards.is_empty():
			facts.append([ui.resource_icons.get("food"), "+%d" % int(rewards.get("food", 0)), UiKit.GOOD])
			facts.append([UiKit.tex("kit_emb_up"), "%d опыта" % int(item.spec.get("xp", 0)), UiKit.BRONZE])
		if not city_hunt:
			var away := distance(item.get("position", {}))
			if not away.is_empty():
				facts.append([UiKit.tex("kit_emb_march"), away, UiKit.INK])
		card.chips = facts
		card.custom_minimum_size.y = 100
		ui.modal_body.add_child(card)
		var open: Button = card.add_action("Открыть", "secondary", Vector2(116, 46))
		open.accessibility_name = "%s · ур. %d · %s" % [item.spec.name, int(item.level), status.to_lower()]
		open.pressed.connect(ui.inspect_current_encounter.bind(item.id))
	if encounters.is_empty():
		note("Здесь пока нет целей охоты.")

# ------------------------------------------------------------------ settlement

func settlement(item: Dictionary) -> void:
	var started := Time.get_ticks_usec()
	var own: bool = item.id == ui.state.get("playerId", "")
	ui.open_modal(item.name, "right", "ПОСЕЛЕНИЕ")
	var crest := head(null, str(item.name), ("Ваше поселение" if own else ("Игрок · " + str(item.nickname)) if item.get("nickname") is String and not str(item.nickname).is_empty() else "Поселение"), roman(int(item.level)))
	crest.emblem = UiKit.tex("kit_emb_town" if own else "kit_emb_helm")
	crest.banner = panels.menu_view.banner_colour(str(item.id))
	var facts: Array = [[UiKit.tex("kit_emb_town"), "Ратуша %d" % int(item.level)]]
	if item.has("wallLevel"):
		var wall := int(item.wallLevel)
		facts.append([UiKit.tex("kit_emb_wall"), ("Стены %d" % wall) if wall > 0 else ("Частокол" if int(item.level) >= 2 else "Без стен")])
	facts.append([UiKit.tex("kit_emb_aim"), coordinates(item.get("position", {}))])
	if not own:
		facts.append([UiKit.tex("kit_emb_march"), distance(item.get("position", {}))])
	chips(facts)
	if item.has("wallLevel"):
		var wall := int(item.wallLevel)
		note("Стены и ворота · уровень %d" % wall if wall > 0 else ("Частокол без «Стен и ворот»" if int(item.level) >= 2 else "Без стен"))
	var flow := actions()
	action(flow, "Рассмотреть на карте", ui.focus_minimap.bind(Vector2(item.position.x, item.position.z)))
	ui.modal_footer.show()
	if own:
		action(flow, "Найти место для переселения", ui.show_relocation)
		action(flow, "К списку городов", ui.show_world_cities)
		ui.panel_action(ui.modal_footer, "Войти в город", ui.show_scene.bind("city")).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	elif item.get("pvp", false):
		var own_index: int = ui.state.world.cities.find_custom(func(city): return city.id == ui.player_id)
		var eligible: bool = own_index >= 0 and ui.state.world.cities[own_index].get("pvp", false)
		if own_index >= 0 and not eligible:
			note("Ваше поселение · " + str(ui.state.world.cities[own_index].get("pvpReason", "PvP закрыто")), true)
		action(flow, "К списку городов", ui.show_world_cities)
		var march: Button = ui.panel_action(ui.modal_footer, "Собрать отряд", ui.compose_march.bind("pvp", item.id, item.name), eligible)
		march.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		march.icon = UiKit.tex("kit_emb_sword")
		march.expand_icon = true
		march.add_theme_constant_override("icon_max_width", 30)
	else:
		if item.get("pvpReason") is String:
			note(str(item.pvpReason))
		ui.modal_footer.hide()
		action(flow, "К списку городов", ui.show_world_cities)
	last_open_usec = Time.get_ticks_usec() - started

func cities() -> void:
	ui.open_modal("Города", "right", "ДРЕНОВАР · КАРТА МИРА")
	for city: Dictionary in ui.state.world.cities:
		var own: bool = city.id == ui.player_id
		var card := KitMore.Card.new()
		card.name = "City_" + str(city.id)
		card.icon = UiKit.tex("kit_emb_town" if own else "kit_emb_helm")
		card.icon_mode = "disc"
		card.icon_tint = Color.WHITE
		card.title = str(city.name)
		card.subtitle = "Ваш город" if own else ("Игрок · " + str(city.nickname) if city.get("nickname") is String and not str(city.nickname).is_empty() else "Поселение")
		card.subtitle_colour = UiKit.BRONZE if own else UiKit.INK_MUTED
		card.plate = "gold" if own else "row"
		card.chips = [[UiKit.tex("kit_emb_town"), "Ратуша %d" % int(city.level), UiKit.INK]]
		if not own:
			var away := distance(city.get("position", {}))
			if not away.is_empty():
				card.chips.append([UiKit.tex("kit_emb_march"), away, UiKit.INK])
		card.custom_minimum_size.y = 100
		ui.modal_body.add_child(card)
		var open: Button = card.add_action("Открыть", "secondary", Vector2(116, 46))
		open.accessibility_name = "%s · ур. %d%s" % [city.name, int(city.level), " · ваш город" if own else ""]
		open.pressed.connect(ui.inspect_settlement.bind(city))
	if ui.state.world.cities.is_empty():
		note("На карте пока нет серверных поселений.")
	back_to_world()

func back_to_world() -> void:
	ui.modal_footer.show()
	styled(ui.button(ui.modal_footer, "К общему миру", ui.show_world_directory), "tertiary", 50).size_flags_horizontal = Control.SIZE_EXPAND_FILL

# ------------------------------------------------------------------ marches

func army(army: Dictionary) -> void:
	var started := Time.get_ticks_usec()
	ui.open_modal(str(army.get("name", "Поход")), "right", "ПОХОД")
	var status: String = {"outbound":"В пути", "fighting":"В бою", "returning":"Возвращается"}.get(army.status, str(army.status))
	var units: Dictionary = army.get("returnUnits", army.units) if army.status == "returning" else army.units
	var faces: Array = []
	var counts: Array = []
	var total := 0
	for id: String in units:
		if int(units[id]) <= 0:
			continue
		total += int(units[id])
		var face: Texture2D = ui.unit_portrait(id, true)
		if face != null and faces.size() < 3:
			faces.append(face)
		counts.append([face, "%s × %d" % [ui.unit_for_id(id).get("name", id), int(units[id])], UiKit.INK, ui.unit_portrait(id)])
	var top := head(null, str(army.get("name", "Поход")), "%s · %d воинов" % [status, total], "", Color("#5a4a3a"))
	top.pictures = faces
	if faces.is_empty():
		top.emblem = UiKit.tex("kit_emb_march")
	for entry: Array in counts:
		var row := KitMore.Card.new()
		row.icon = entry[3] if entry[3] != null else entry[0]
		row.icon_mode = "figure"
		row.title = entry[1]
		row.custom_minimum_size.y = 84
		ui.modal_body.add_child(row)
	var finish: Variant = ui.march_finish(army)
	if finish != null:
		ui.countdown("До следующей фазы", float(finish))
	var flow := actions()
	action(flow, "Следить за отрядом", ui.focus_army.bind(army))
	if finish != null and army.status in ["outbound", "returning"] and army.get("owner", ui.player_id) == ui.player_id and not ui.player_id.is_empty():
		action(flow, "Ускорить марш", ui.show_march_speedups.bind(army), true, "secondary")
	if ui.map_name == "city" and army.status == "outbound" and not ui.player_id.is_empty():
		action(flow, "Отозвать отряд", ui.command.bind({"kind":"recall", "armyId":army.id}), true, "danger")
	last_open_usec = Time.get_ticks_usec() - started

func marches() -> void:
	ui.open_modal("Походы", "right", "ДРЕНОВАР · КАРТА МИРА")
	var any := false
	for march: Dictionary in ui.state.world.armies:
		if march.status == "returned":
			continue
		any = true
		var card := KitMore.Card.new()
		card.icon = UiKit.tex("kit_emb_march")
		card.icon_mode = "disc"
		card.title = str(march.get("name", "Поход"))
		card.subtitle = {"outbound":"В пути", "fighting":"В бою", "returning":"Возвращается"}.get(march.status, str(march.status))
		card.custom_minimum_size.y = 84
		ui.modal_body.add_child(card)
		var open: Button = card.add_action("Открыть", "secondary", Vector2(116, 46))
		open.accessibility_name = str(march.get("name", "Поход"))
		open.pressed.connect(ui.inspect_army.bind(march))
	if not any:
		note("На карте сейчас нет активных походов.")
	back_to_world()

# ------------------------------------------------------------------ directory

func directory() -> void:
	ui.open_modal("Общий мир", "right", "ДРЕНОВАР · КАРТА МИРА")
	var own_city: bool = ui.state.world.cities.any(func(city): return city.id == ui.player_id)
	var reason: String = ui.state.world.get("relocationReason", "")
	var grid := GridContainer.new()
	grid.name = "WorldTiles"
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	grid.theme = KitMore.drawn_buttons_theme()
	ui.modal_body.add_child(grid)
	var armies: int = ui.state.world.armies.filter(func(a): return a.status != "returned").size()
	var alive: int = ui.state.world.encounters.filter(func(e): return e.status == "alive").size()
	for entry: Array in [["Мой город", "kit_emb_town", ui.focus_own_city, own_city, ""],
			["Переселить город", "kit_emb_move", ui.show_relocation, not ui.player_id.is_empty() and reason.is_empty(), ""],
			["Города", "kit_emb_helm", ui.show_world_cities, true, str(ui.state.world.cities.size())],
			["Цели охоты", "kit_emb_sword", ui.show_world_hunt, true, str(alive) if alive > 0 else ""],
			["Походы", "kit_emb_march", ui.show_world_marches, true, str(armies) if armies > 0 else ""],
			["Окружение мира", "kit_emb_tree", ui.show_environment_catalog, true, ""]]:
		var tile := KitMore.MenuTile.new().setup(entry[0], entry[1], "", entry[4], "bronze")
		tile.name = "World_" + str(entry[1]).trim_prefix("kit_emb_")
		tile.custom_minimum_size = Vector2(0, 104)
		tile.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tile.disabled = not entry[3]
		tile.pressed.connect(entry[2])
		grid.add_child(tile)
	if not reason.is_empty():
		note(reason, true)

## «Слои мира»: two premium switches on cards and the map's shortcuts.
func map_options() -> void:
	ui.open_modal("Слои мира", "right", "КАРТА МИРА")
	for resources: bool in [true, false]:
		var card := KitMore.Card.new()
		card.icon = UiKit.tex("kit_emb_sheaf" if resources else "kit_emb_tree")
		card.icon_mode = "disc"
		card.title = "Месторождения и угодья" if resources else "Мелкие детали"
		card.subtitle = "Где добывать камень, железо и еду" if resources else "Кусты, камни и травы на карте"
		card.custom_minimum_size.y = 84
		ui.modal_body.add_child(card)
		var toggle := CheckButton.new()
		toggle.text = card.title
		toggle.name = "LayerResources" if resources else "LayerDetails"
		# The switch alone on the card (its caption is the card's title).
		toggle.add_theme_color_override("font_color", Color.TRANSPARENT)
		toggle.add_theme_color_override("font_pressed_color", Color.TRANSPARENT)
		toggle.add_theme_color_override("font_hover_color", Color.TRANSPARENT)
		toggle.add_theme_color_override("font_hover_pressed_color", Color.TRANSPARENT)
		toggle.add_theme_color_override("font_focus_color", Color.TRANSPARENT)
		toggle.add_theme_font_size_override("font_size", 1)
		toggle.button_pressed = ui.stage.resource_layer if resources else ui.stage.detail_layer
		toggle.toggled.connect(func(_enabled): ui.stage.toggle_scenery_layer(resources))
		card.add_child(toggle)
		toggle.set_anchors_and_offsets_preset(Control.PRESET_CENTER_RIGHT)
		toggle.offset_left = -96
		toggle.offset_right = -18
		toggle.offset_top = -24
		toggle.offset_bottom = 24
	var flow := actions()
	action(flow, "Найти своё поселение", ui.focus_own_city)
	action(flow, "Окружение мира", ui.show_environment_catalog)

# ------------------------------------------------------------------ relocation

func world_plot(item: Dictionary) -> void:
	ui.open_modal("Свободное место", "right", "ПЕРЕСЕЛЕНИЕ")
	var current: String = ui.state.city.get("worldSlotId", "")
	if not current.begins_with("slot-") or not current.trim_prefix("slot-").is_valid_int():
		return
	var reason: String = ui.state.world.get("relocationReason", "")
	var top := head(null, "Свободное место", "Сюда можно перенести поселение", "", Color("#3f6a4a"))
	top.emblem = UiKit.tex("kit_emb_move")
	top.banner = Color("#2f6b3a")
	if not reason.is_empty():
		note(reason, true)
		return
	var spot := {"x": item.get("x", 0), "z": item.get("z", 0)}
	chips([[UiKit.tex("kit_emb_aim"), coordinates(spot)], [UiKit.tex("kit_emb_march"), distance(spot)]])
	var order := {"kind":"relocateCity","slot":int(str(item.slot).trim_prefix("slot-")),"fromSlot":int(current.trim_prefix("slot-"))}
	var occupied: bool = ui.state.world.cities.any(func(city): return city.slot == item.slot)
	if occupied:
		note("Это место уже занято. Выберите другое.", true)
	var flow := actions()
	action(flow, "Выбрать другое место", ui.show_relocation)
	ui.modal_footer.show()
	ui.panel_action(ui.modal_footer, "Подтвердить переселение", ui.command.bind(order, ui.focus_own_city),
		not ui.player_id.is_empty() and not occupied).size_flags_horizontal = Control.SIZE_EXPAND_FILL

func relocation_list() -> void:
	ui.open_modal("Переселение", "right", "СВОБОДНЫЕ МЕСТА")
	var origin: Vector3 = ui.stage.target
	for city: Dictionary in ui.state.world.cities:
		if city.id == ui.player_id:
			origin = ui.stage.point(city.position)
			break
	var sites: Array = ui.stage.empty_plots.duplicate()
	sites.sort_custom(func(a, b): return origin.distance_squared_to(a.position) < origin.distance_squared_to(b.position))
	if sites.is_empty():
		note("Свободных мест пока нет.")
	for site in sites:
		var card := KitMore.Card.new()
		card.icon = UiKit.tex("kit_emb_move")
		card.icon_mode = "disc"
		card.title = "%d : %d" % [roundi(site.position.x + 150), roundi(site.position.z + 120)]
		card.subtitle = "%d от города" % roundi(Vector2(site.position.x - origin.x, site.position.z - origin.z).length())
		card.custom_minimum_size.y = 76
		ui.modal_body.add_child(card)
		var pick: Button = card.add_action("Выбрать", "secondary", Vector2(130, 44))
		pick.accessibility_name = card.title
		pick.pressed.connect(func():
			ui.stage.target = site.position
			ui.stage.zoom = 85.0
			ui.inspect_world_plot(site.item))
