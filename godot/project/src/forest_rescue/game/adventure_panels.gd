extends RefCounted
## Adventure panels built inside the existing DRENOVAR modal (main.open_modal), so they keep
## the game's look, scrolling and touch handling: route, squad formation, journal (12 sites,
## captives, testimony), reward reserve (escrow) with claim and auto-refill, site, horse, boss,
## battle result. All strings come from the authored JSON files (see adventure_content.gd).

const Style = preload("res://src/forest_rescue/game/hud_style.gd")
const RESOURCE_ORDER := ["food", "wood", "stone", "iron", "coins"]
const ROMAN := ["I", "II", "III", "IV"]
const RECRUIT_ORDER := ["ENG-09", "ENG-08", "ENG-01", "ENG-02", "ENG-07", "ENG-10", "ENG-03", "ENG-04", "ENG-05", "ENG-06"]

var game: Node
var main: Node
var content
var client

func _init(owner_game: Node) -> void:
	game = owner_game
	main = owner_game.main
	content = owner_game.content
	client = owner_game.client

func t(key: String, args := {}) -> String:
	return content.text(key, args)

func body_label(value: String, size := 18, color := Color("#f2e7d0")) -> Label:
	var label := Label.new()
	label.text = value
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	main.modal_body.add_child(label)
	return label

func heading(value: String) -> Label:
	var label := body_label(value, 22, Color("#ebcc89"))
	label.add_theme_font_override("font", Style.TITLE_FONT)
	return label

func action(caption: String, callable: Callable, enabled := true, primary := false) -> Button:
	if primary:
		return main.panel_action(main.modal_body, caption, callable, enabled)
	return main.button(main.modal_body, caption, callable, enabled)

func close_then(callable: Callable) -> Callable:
	return func():
		main.close_modal()
		callable.call()

# ------------------------------------------------------------------ route («Маршрут»)
func open_route() -> void:
	main.open_modal(t("hud.route"), "left", t("title").to_upper())
	var squad: Dictionary = client.squad()
	var move: Variant = squad.get("move")
	if move is Dictionary:
		var left := maxi(0, ceili((float(move.get("arriveAt", 0)) - client.server_now()) / 1000.0))
		body_label("%s → %s · %d:%02d" % [t("hud.squad"), game.target_name(String(move.get("targetId", ""))), left / 60, left % 60])
		action(t("hud.stop"), close_then(func(): game.request_action("stop")))
	var step: Dictionary = game.guide()
	var suggested := String(step.get("target", ""))
	if not suggested.is_empty() and String(step.get("action", "")) == "move":
		action("%s → %s" % [t("hud.continue"), game.target_name(suggested)], close_then(func(): game.request_action("move", {"targetId":suggested})), true, true)
	if not String(step.get("hint", "")).is_empty():
		body_label(String(step.hint), 16, Color("#d9cdb2"))
	var targets: Array[String] = []
	if bool(client.adv.get("horse", {}).get("visible", false)):
		targets.append("lf_horse_origin")
	for poi in client.adv.get("pois", []):
		var id := String(poi.get("id", ""))
		if String(poi.get("kind", "site")) == "site" and not id.is_empty():
			targets.append(id)
		elif String(poi.get("kind", "")) in ["boss", "arena"]:
			targets.append(id)
	if String(client.adv.get("boss", {}).get("state", "locked")) != "locked" and not targets.has("lf_boss_ancient_maw"):
		targets.append("lf_boss_ancient_maw")
	targets.append("lf_home_reception")
	for id in targets:
		var caption: String = game.target_name(id)
		var site_entry: Dictionary = client.site_state(id)
		if not site_entry.is_empty():
			caption += " · " + t("site.progress", {"count":int(site_entry.get("step", 0))})
		var enabled: bool = not (move is Dictionary) and String(squad.get("node", "")) != id and game.total_units(squad.get("units", {})) > 0
		action(caption, close_then(func(): game.request_action("move", {"targetId":id})), enabled)

# ------------------------------------------------------------------ squad («Отряд»)
func open_squad() -> void:
	main.open_modal(t("hud.squad"), "left", t("title").to_upper())
	body_label(t("hud.squadNote"), 16, Color("#d9cdb2"))
	var squad: Dictionary = client.squad()
	var current: Dictionary = squad.get("units", {})
	if not current.is_empty():
		var parts: PackedStringArray = []
		for id in current:
			parts.append("%s × %d" % [main.unit_for_id(id).get("name", id), int(current[id])])
		body_label(" · ".join(parts), 17, Color("#ebcc89"))
	var healthy: Dictionary = main.state.get("healthy", {})
	var pool := {}
	for id in healthy:
		pool[id] = int(healthy[id])
	for id in current:
		pool[id] = maxi(int(pool.get(id, 0)), int(current[id]))
	var total := 0
	for id in pool:
		total += int(pool[id])
	if total <= 0:
		body_label(t("hud.squadEmpty"), 17, Color("#ffc28b"))
		return
	var spins := {}
	for id in RECRUIT_ORDER:
		if int(pool.get(id, 0)) <= 0:
			continue
		var row := HBoxContainer.new()
		main.modal_body.add_child(row)
		var name := Label.new()
		name.text = "%s · %d" % [main.unit_for_id(id).get("name", id), int(pool[id])]
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(name)
		var spin := SpinBox.new()
		spin.name = "Squad_" + id
		spin.min_value = 0
		spin.max_value = int(pool[id])
		spin.value = int(current.get(id, 0))
		spin.custom_minimum_size = Vector2(120, 42)
		row.add_child(spin)
		spins[id] = spin
	var fill_all := func():
		for id in spins:
			spins[id].value = spins[id].max_value
	action(t("hud.squadAll"), fill_all)
	var submit := func():
		var units := {}
		for id in spins:
			if int(spins[id].value) > 0:
				units[id] = int(spins[id].value)
		if units.is_empty():
			main.modal_status.text = t("error.insufficientSquad")
			main.modal_status.show()
			return
		main.close_modal()
		await game.request_action("form_squad", {"units":units})
	var button := action(t("hud.squadForm"), submit, not (squad.get("move") is Dictionary) and squad.get("busy") == null, true)
	button.name = "SquadSubmit"

# ------------------------------------------------------------------ journal («Дороги домой»)
func open_journal() -> void:
	main.open_modal(t("journal"), "wide", t("title").to_upper())
	var camp: Dictionary = client.campaign()
	var phase := String(camp.get("phase", "prologue"))
	if not client.unlocked():
		body_label(t("forest.locked.body") if client.available() else t("hud.unavailable"))
		if client.available():
			body_label(t("forest.locked.progress", {"level":clampi(client.hall_level(), 1, 3)}), 16)
		return
	body_label(t("objective." + phase), 19, Color("#ebcc89"))
	var tasks_done := 0
	for entry in camp.get("sites", []):
		tasks_done += int(entry.get("step", 0))
	var tools := HFlowContainer.new()
	main.modal_body.add_child(tools)
	var chip := func(text_value: String):
		var label := Label.new()
		label.text = text_value
		label.add_theme_color_override("font_color", Color("#d9cdb2"))
		tools.add_child(label)
	chip.call(t("campaign.progress", {"count":tasks_done}) + "   ")
	chip.call(t("people.progress", {"count":int(camp.get("rescuedCount", camp.get("rescuedIds", []).size()))}))
	var controls := HFlowContainer.new()
	main.modal_body.add_child(controls)
	main.button(controls, t("reward.ledger"), open_rewards)
	if bool(camp.get("paused", false)):
		main.button(controls, t("button.resume"), close_then(func(): game.request_action("resume")))
	else:
		main.button(controls, t("button.pause"), close_then(func(): game.request_action("pause")))
	if client.hall_level() >= 3:
		main.button(controls, t("intro.replay"), close_then(func(): game.intro.replay()))
	var motion := CheckButton.new()
	motion.text = t("hud.settings.motion")
	motion.button_pressed = game.reduced_motion
	motion.toggled.connect(func(on): game.set_reduced_motion(on))
	controls.add_child(motion)
	var sound := CheckButton.new()
	sound.text = t("hud.settings.sound")
	sound.button_pressed = game.sound_enabled
	sound.toggled.connect(func(on): game.set_sound(on))
	controls.add_child(sound)
	body_label(t("pause.note"), 15, Color("#b9ae96"))
	var unlocked_acts: Array = camp.get("actUnlocked", [true, false, false, false])
	for act in 4:
		var act_open: bool = bool(unlocked_acts[act]) if act < unlocked_acts.size() else false
		heading("%s · %s" % [ROMAN[act], ", ".join(PackedStringArray(site_names_for_act(act + 1)))] if act_open else ROMAN[act])
		if not act_open:
			body_label(t("act.locked"), 16, Color("#b9ae96"))
			continue
		for site_id in content.site_order:
			var site: Dictionary = content.site(site_id)
			if int(site.get("act", 0)) != act + 1:
				continue
			add_site_summary(site_id, false)
	heading(String(content.campaign.get("boss", {}).get("displayName", "")))
	var boss_state := String(client.adv.get("boss", {}).get("state", "locked"))
	if boss_state == "locked":
		body_label(t("boss.locked"), 16)
	elif boss_state == "defeated" or phase == "completed":
		body_label(t("boss.victory"), 16)
		heading(t("ending.title"))
		body_label(t("ending.body"), 17)
	else:
		body_label(t("boss.warning"), 16)
		body_label(t("boss.noPrisoners"), 16)

func site_names_for_act(act: int) -> Array:
	var names := []
	for site_id in content.site_order:
		var site: Dictionary = content.site(site_id)
		if int(site.get("act", 0)) == act:
			var known: bool = not client.site_state(site_id).is_empty() and bool(client.site_state(site_id).get("visible", false))
			names.append(String(site.get("name", "")) if known else t("site.unknown"))
	return names

func add_site_summary(site_id: String, detailed: bool) -> void:
	var site: Dictionary = content.site(site_id)
	var entry: Dictionary = client.site_state(site_id)
	var step := int(entry.get("step", 0))
	var visible := bool(entry.get("visible", false)) or step > 0
	var box := PanelContainer.new()
	box.add_theme_stylebox_override("panel", Style.frame(Color("#2a2620"), Color("#1d1a16"), Color("#6f5a3a"), 8, 1, Vector4(12, 8, 12, 8)))
	main.modal_body.add_child(box)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 3)
	box.add_child(column)
	var title := Label.new()
	title.text = "%d. %s · %s" % [int(site.get("number", 0)), String(site.get("name", "")) if visible else t("site.unknown"), t("site.progress", {"count":step})]
	title.add_theme_font_override("font", Style.TITLE_FONT)
	title.add_theme_font_size_override("font_size", 19)
	title.add_theme_color_override("font_color", Color("#f2e7d0"))
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(title)
	if not visible:
		return
	var guardian: Dictionary = site.get("guardian", {})
	var lines: PackedStringArray = [t("site.guardian", {"name":content.species_name(String(guardian.get("species", ""))), "level":int(guardian.get("level", 1))})]
	if int(guardian.get("requiredHall", 1)) > client.hall_level():
		lines.append(t("site.requiredHall", {"level":int(guardian.get("requiredHall", 1))}))
	var artifact: Dictionary = site.get("artifact", {})
	if step >= 1:
		lines.append(String(artifact.get("name", "")) + " — " + (t("artifact.bound") if step in [2, 3] else (t("cage.released") if step == 4 else t("artifact.missing") if step < 2 else "")))
	for value in lines:
		var label := Label.new()
		label.text = value
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.add_theme_font_size_override("font_size", 16)
		label.add_theme_color_override("font_color", Color("#d9cdb2"))
		column.add_child(label)
	var people: PackedStringArray = []
	for person in site.get("captives", []):
		people.append("%s — %s" % [person.get("name", ""), person.get("role", "")])
	var who := Label.new()
	who.text = " · ".join(people)
	who.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	who.add_theme_font_size_override("font_size", 16)
	who.add_theme_color_override("font_color", Color("#ebcc89"))
	column.add_child(who)
	if step >= 4 or detailed:
		for person in site.get("captives", []):
			var said: String = content.released_line(String(person.get("id", "")))
			if step >= 4 and not said.is_empty():
				var quote := Label.new()
				quote.text = "%s: «%s»" % [person.get("name", ""), said]
				quote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
				quote.add_theme_font_size_override("font_size", 15)
				quote.add_theme_color_override("font_color", Color("#cfc3a8"))
				column.add_child(quote)
	if step >= 5:
		var testimony: Dictionary = content.testimony(site_id)
		if not testimony.is_empty():
			var said_label := Label.new()
			said_label.text = "%s: «%s»" % [testimony.get("speaker", ""), testimony.get("text", "")]
			said_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			said_label.add_theme_font_override("font", Style.TITLE_FONT)
			said_label.add_theme_font_size_override("font_size", 16)
			said_label.add_theme_color_override("font_color", Color("#f4e1b4"))
			column.add_child(said_label)
		var post := Label.new()
		post.text = String(site.get("postState", ""))
		post.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		post.add_theme_font_size_override("font_size", 14)
		post.add_theme_color_override("font_color", Color("#a99f88"))
		column.add_child(post)

# ------------------------------------------------------------------ reward reserve (escrow)
func open_rewards() -> void:
	main.open_modal(t("hud.rewards"), "left", t("title").to_upper())
	var escrow: Dictionary = client.adv.get("escrow", {})
	var earned: Dictionary = escrow.get("earned", {})
	var claimed: Dictionary = escrow.get("claimed", {})
	var pending: Dictionary = escrow.get("pending", {})
	var grid := GridContainer.new()
	grid.name = "EscrowGrid"
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 14)
	main.modal_body.add_child(grid)
	var pending_total := 0
	for key in RESOURCE_ORDER:
		var head := HBoxContainer.new()
		main.add_resource_icon(head, key, 26)
		var name := Label.new()
		name.text = t("reward.resources." + key)
		head.add_child(name)
		grid.add_child(head)
		for pair in [["hud.earned", earned], ["reward.claimed", claimed], ["reward.pending", pending]]:
			var cell := Label.new()
			cell.name = "%s_%s" % [key, String(pair[0]).get_slice(".", 1)]
			cell.text = t(pair[0], {"amount":content.format_amount(int(pair[1].get(key, 0)))})
			cell.add_theme_font_size_override("font_size", 15)
			cell.add_theme_color_override("font_color", Color("#d9cdb2") if pair[0] != "reward.pending" else Color("#ebcc89"))
			grid.add_child(cell)
		pending_total += int(pending.get(key, 0))
	body_label(t("reward.capacity") if pending_total > 0 else t("reward.reserve"), 15, Color("#b9ae96"))
	var claim := action(t("reward.claim"), func(): await claim_rewards(), pending_total > 0 and client.unlocked(), true)
	claim.name = "ClaimRewards"
	var toggle := CheckButton.new()
	toggle.name = "AutoRefill"
	toggle.text = t("reward.autoRefill.label")
	toggle.button_pressed = bool(client.adv.get("autoRefill", false))
	toggle.disabled = not client.unlocked()
	main.modal_body.add_child(toggle)
	body_label(t("reward.autoRefill.description"), 15, Color("#b9ae96"))
	if not toggle.button_pressed:
		body_label(t("reward.autoRefill.off"), 15, Color("#8f8775"))
	toggle.toggled.connect(func(on):
		var result: Dictionary = await game.request_action("set_auto_refill", {"enabled":on})
		if main.modal.visible and main.modal_title.text == t("hud.rewards"):
			open_rewards()
		if not bool(result.get("ok", false)) and is_instance_valid(toggle):
			toggle.set_pressed_no_signal(bool(client.adv.get("autoRefill", false))))

func claim_rewards() -> void:
	var before: Dictionary = client.adv.get("escrow", {}).get("pending", {}).duplicate()
	var result: Dictionary = await game.request_action("claim_rewards")
	if bool(result.get("ok", false)):
		var seen_transfer := false
		for event in result.get("events", []):
			if String(event.get("type", "")) == "transfer_rewards":
				seen_transfer = true
		if not seen_transfer:
			var after: Dictionary = client.adv.get("escrow", {}).get("pending", {})
			var moved := {}
			for key in RESOURCE_ORDER:
				moved[key] = maxi(0, int(before.get(key, 0)) - int(after.get(key, 0)))
			on_transfer(moved)
	if main.modal.visible and main.modal_title.text == t("hud.rewards"):
		open_rewards()

func on_transfer(resources: Dictionary) -> void:
	var moved := 0
	var parts: PackedStringArray = []
	for key in RESOURCE_ORDER:
		var amount := int(resources.get(key, 0))
		moved += amount
		if amount > 0:
			parts.append("%s +%s" % [t("reward.resources." + key), content.format_amount(amount)])
	var remaining := 0
	for key in RESOURCE_ORDER:
		remaining += int(client.adv.get("escrow", {}).get("pending", {}).get(key, 0))
	if moved > 0:
		game.hud.toast(t("reward.claimed", {"amount":" · ".join(parts)}), "reward", 5.0)
		game.fx.fly_to_wallet(resources)
		game.audio.play_cue("fr_large_reward")
	if remaining > 0:
		game.hud.toast(t("reward.capacity") if moved > 0 else t("reward.noRoom"), "info", 6.0)

func offer_retry() -> void:
	game.hud.toast(t("network.offline"), "network", 6.0)
	if main.modal.visible:
		return
	main.open_modal(t("network.pending"), "center", t("title").to_upper())
	body_label(t("network.offline"))
	action(t("button.retry"), close_then(func(): game.retry_last()), true, true)
	action(t("button.close"), main.close_modal)

# ------------------------------------------------------------------ site / horse / boss
func open_site(site_id: String) -> void:
	var site: Dictionary = content.site(site_id)
	if site.is_empty():
		return
	main.open_modal(String(site.get("name", "")), "left", "%s · %s" % [t("title").to_upper(), ROMAN[clampi(int(site.get("act", 1)) - 1, 0, 3)]])
	var step := int(client.site_state(site_id).get("step", 0))
	var next: Variant = client.adv.get("nextTask")
	if step < 5:
		var task_id: String = content.TASKS[clampi(step, 0, 4)]
		var task: Dictionary = content.task(site_id, task_id)
		heading(String(task.get("title", "")))
		body_label(String(task.get("objective", "")), 17)
	add_site_summary(site_id, true)
	var step_guide: Dictionary = game.guide()
	if next is Dictionary and String(next.get("siteId", "")) == site_id and bool(step_guide.get("enabled", false)):
		action(String(step_guide.get("label", t("hud.continue"))), close_then(func(): game.on_continue_pressed()), true, true)
	elif String(client.squad().get("node", "")) != site_id and step < 5:
		var enabled: bool = not (client.squad().get("move") is Dictionary) and game.total_units(client.squad().get("units", {})) > 0
		action("%s → %s" % [t("hud.route"), String(site.get("name", ""))], close_then(func(): game.request_action("move", {"targetId":site_id})), enabled)

func open_horse() -> void:
	var prologue: Dictionary = content.campaign.get("prologue", {})
	main.open_modal(String(prologue.get("title", "")), "left", t("title").to_upper())
	for paragraph in content.line("horse_intro").get("paragraphs", prologue.get("intro", [])):
		body_label(String(paragraph), 17)
	if int(client.site_state("lf_site_01").get("step", 0)) >= 5:
		var spoken: Dictionary = content.line("horse_return")
		body_label("%s: «%s»" % [spoken.get("speaker", ""), spoken.get("text", "")], 17, Color("#f4e1b4"))
	if client.phase() == "prologue":
		action(t("button.follow"), close_then(func(): game.on_continue_pressed()), true, true)

func open_boss() -> void:
	var boss: Dictionary = content.campaign.get("boss", {})
	main.open_modal(String(boss.get("displayName", "")), "left", t("title").to_upper())
	body_label(String(boss.get("visualDirection", "")), 16, Color("#d9cdb2"))
	var state := String(client.adv.get("boss", {}).get("state", "locked"))
	if state == "locked":
		body_label(t("boss.locked"))
	else:
		body_label(t("boss.warning"))
		body_label(t("boss.noPrisoners"), 16)
	for phase in boss.get("phases", []):
		var attacks: PackedStringArray = []
		for attack in phase.get("attacks", []):
			attacks.append(t("boss.telegraph." + String(attack)))
		body_label("%s — %s" % [t("boss.phase." + String(phase.get("id", ""))), "; ".join(attacks)], 15, Color("#cfc3a8"))
	if state in ["available", "active"] or client.phase() in ["boss_unlocked", "boss_active"]:
		action(t("boss.begin"), close_then(func(): game.on_continue_pressed()), true, true)

func open_battle_result(fight: Dictionary) -> void:
	var outcome := String(fight.get("outcome", ""))
	var species := String(fight.get("species", ""))
	var boss_fight := species == "ancient_maw"
	var title := t("boss.victory") if boss_fight and outcome == "victory" else String(content.task(String(fight.get("siteId", "")), "defeat_guardian").get("resultText", "")) if outcome == "victory" else t("boss.retreat") if outcome == "retreat" else t("error.unverifiedBattle")
	main.open_modal(content.species_name(species) + " · " + str(int(fight.get("level", 1))), "result")
	var big: Label = main.result_label(main.modal_body, content.species_name(species), 34, Color("#f1d28c"), true)
	big.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var verdict: Label = main.result_label(main.modal_body, title, 19, Color("#becab2"))
	verdict.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var losses: Dictionary = fight.get("losses", {})
	var lost := 0
	for bucket in ["wounded", "dead"]:
		for id in losses.get(bucket, {}):
			lost += int(losses[bucket][id])
	if lost > 0:
		var parts: PackedStringArray = []
		for bucket in ["wounded", "dead"]:
			for id in losses.get(bucket, {}):
				parts.append("%s × %d" % [main.unit_for_id(id).get("name", id), int(losses[bucket][id])])
		main.result_label(main.modal_body, " · ".join(parts), 16, Color("#ffc28b")).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var loot: Dictionary = fight.get("loot", {})
	var resources: Dictionary = loot.get("resources", loot)
	var chips := HFlowContainer.new()
	chips.alignment = FlowContainer.ALIGNMENT_CENTER
	var has_loot := false
	for key in RESOURCE_ORDER:
		if int(resources.get(key, 0)) > 0:
			has_loot = true
			main.add_reward_chip(chips, t("reward.resources." + key), int(resources[key]), key)
	if has_loot:
		main.result_label(main.modal_body, t("hud.ordinaryLoot"), 16, Color("#ebcc89"))
		main.modal_body.add_child(chips)
	else:
		chips.queue_free()
	if outcome == "victory" and not boss_fight:
		var site_id := String(fight.get("siteId", ""))
		var reward: Dictionary = content.task_reward(site_id, "defeat_guardian")
		var parts: PackedStringArray = []
		for key in RESOURCE_ORDER:
			if int(reward.get(key, 0)) > 0:
				parts.append("%s +%s" % [t("reward.resources." + key), content.format_amount(int(reward[key]))])
		main.result_label(main.modal_body, String(content.task(site_id, "defeat_guardian").get("title", "")) + ": " + " · ".join(parts), 15, Color("#d9cdb2")).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	main.modal_footer.show()
	var next_button: Button = main.panel_action(main.modal_footer, t("hud.continue"), close_then(func(): game.on_continue_pressed()))
	next_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
