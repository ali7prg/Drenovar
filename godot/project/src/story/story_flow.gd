extends Node
## Story chapters for Town Hall I–V (build 1025).
##
## * The quest flag: a compact button under the profile on the settlement screen with the current
##   goal's name and counter (gold «Claim» when a reward is ready). It opens the quest journal.
## * The quest journal: chapters I–V, each goal with its action, counter, exact reward, Go (leads to
##   the object or screen) and Claim. Rewards are credited only by the server (story72 claim, the same
##   receipts path as every V6 order: one Idempotency-Key per tap, a lost answer is retried with the
##   same key, a second tap of a claimed goal is a no-op on the server). Ready rewards stay ready
##   across sessions and town hall upgrades (server record p.story72).
## * Scenes that play once: the intro (a new settlement at Town Hall I) and the villagers' talk when the
##   hall reaches II (also when the upgrade finished while the player was away). The server keeps the
##   «seen» marks.
## The journal is data-driven by state.v6.story (server module v6/story-quests.mjs); without it the
## flag falls back to First Steps (state.v6.starter).

const UiKit = preload("res://src/ui_kit.gd")
const KitMore = preload("res://src/kit_more.gd")
const StoryIntro = preload("res://src/story/story_intro.gd")
const StoryTalk = preload("res://src/story/story_talk.gd")

const ROMAN := ["I", "II", "III", "IV", "V"]
const RESOURCE_EN := {"food": "Food", "wood": "Wood", "stone": "Stone", "iron": "Iron", "coins": "Coins"}
const ICONS := {"visit": "kit_emb_town", "starter": "kit_emb_award", "building": "kit_emb_up", "trained": "kit_emb_inf",
	"felled": "kit_emb_tree", "forest_phase": "kit_emb_horse", "site_step": "kit_emb_key", "rescued": "kit_emb_heal"}

var ui: Node                 # src/main.gd
var flag: Control
var flag_title: Label
var flag_eyebrow: Label
var flag_count: Label
var flag_pulse := 0.0
var story: Dictionary = {}
var focus_goal := ""         # shown on the flag after a scene (chapter II → the recruiting goal)
var focus_hall := 0
var claiming: Dictionary = {}
var scene_requested: Dictionary = {}
var visit_sent := false
var intro: Node
var talk: Node
var journal_visible := false
var last_gain := ""

func attach(main: Node, outer: Container) -> void:
	ui = main
	name = "StoryFlow"
	build_flag(outer)
	set_process(true)

# ------------------------------------------------------------------ the flag

func build_flag(outer: Container) -> void:
	var row := HBoxContainer.new()
	row.name = "QuestFlagRow"
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	outer.add_child(row)
	outer.move_child(row, 1)
	flag = Button.new()
	flag.name = "QuestFlag"
	flag.flat = true
	flag.focus_mode = Control.FOCUS_NONE
	flag.custom_minimum_size = Vector2(300, 56)
	flag.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	flag.mouse_filter = Control.MOUSE_FILTER_STOP
	flag.pressed.connect(open_journal)
	flag.draw.connect(draw_flag)
	flag.tooltip_text = "Quest journal"
	row.add_child(flag)
	flag_eyebrow = Label.new()
	flag_eyebrow.add_theme_font_override("font", UiKit.LABEL_FONT)
	flag_eyebrow.add_theme_font_size_override("font_size", 12)
	flag_eyebrow.add_theme_color_override("font_color", Color("#d9b46a"))
	flag_eyebrow.position = Vector2(48, 6)
	flag_eyebrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flag.add_child(flag_eyebrow)
	flag_title = Label.new()
	flag_title.add_theme_font_override("font", UiKit.LABEL_FONT)
	flag_title.add_theme_font_size_override("font_size", 17)
	flag_title.add_theme_color_override("font_color", UiKit.IVORY)
	flag_title.add_theme_color_override("font_outline_color", Color("#120c07"))
	flag_title.add_theme_constant_override("outline_size", 3)
	flag_title.position = Vector2(48, 23)
	flag_title.size = Vector2(190, 26)
	flag_title.clip_text = true
	flag_title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	flag_title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flag.add_child(flag_title)
	flag_count = Label.new()
	flag_count.add_theme_font_override("font", UiKit.LABEL_FONT)
	flag_count.add_theme_font_size_override("font_size", 15)
	flag_count.add_theme_color_override("font_color", Color("#f7e2ad"))
	flag_count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	flag_count.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	flag_count.position = Vector2(236, 13)
	flag_count.size = Vector2(56, 30)
	flag_count.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flag.add_child(flag_count)
	flag.hide()

func draw_flag() -> void:
	var box := Rect2(Vector2.ZERO, flag.size)
	var plate := StyleBoxFlat.new()
	plate.bg_color = Color(0.09, 0.065, 0.04, 0.86)
	plate.border_color = Color("#8c6a3c")
	plate.set_border_width_all(1)
	plate.set_corner_radius_all(10)
	plate.shadow_color = Color(0, 0, 0, 0.35)
	plate.shadow_size = 4
	var ready: bool = current_goal().get("state", "") == "ready"
	if ready:
		var glow := 0.5 + 0.5 * sin(flag_pulse * 4.0)
		plate.border_color = Color("#e9c15f").lerp(Color("#fff1b8"), glow)
		plate.set_border_width_all(2)
		plate.shadow_color = Color(0.95, 0.7, 0.2, 0.25 + 0.25 * glow)
		plate.shadow_size = 8
	flag.draw_style_box(plate, box)
	# The pennant on its pole.
	var pole_x := 22.0
	flag.draw_line(Vector2(pole_x, 9), Vector2(pole_x, box.size.y - 9), Color("#d8c08c"), 2.0)
	var wave := sin(flag_pulse * 3.0) * 1.5
	var cloth := PackedVector2Array([Vector2(pole_x + 1, 11), Vector2(pole_x + 19, 15 + wave), Vector2(pole_x + 13, 20),
		Vector2(pole_x + 19, 26 - wave), Vector2(pole_x + 1, 28)])
	flag.draw_colored_polygon(cloth, Color("#e0b23e") if ready else Color("#b0352a"))
	flag.draw_polyline(PackedVector2Array([cloth[0], cloth[1], cloth[2], cloth[3], cloth[4]]), Color(0, 0, 0, 0.35), 1.0)
	# Counter / Claim badge.
	var badge := Rect2(Vector2(236, 13), Vector2(56, 30))
	var badge_box := StyleBoxFlat.new()
	badge_box.set_corner_radius_all(7)
	badge_box.bg_color = Color("#3d6b2e") if ready else Color(1, 1, 1, 0.07)
	flag.draw_style_box(badge_box, badge)

var last_map := ""
var scene_timer := 0.0

func _process(delta: float) -> void:
	if ui != null and String(ui.map_name) != last_map:
		last_map = String(ui.map_name)
		refresh_flag()
	# Conditional polls answer «not modified» most of the time: the scene check also runs on a timer
	# (the forest layer the intro plays on finishes loading after the first state).
	scene_timer += delta
	if scene_timer >= 1.0 and ui != null:
		scene_timer = 0.0
		check_scenes()
	if flag != null and flag.visible:
		flag_pulse += delta
		if current_goal().get("state", "") == "ready":
			flag.queue_redraw()

# ------------------------------------------------------------------ state

func v6() -> Dictionary:
	var state: Variant = ui.state
	if state is Dictionary and state.get("v6") is Dictionary:
		return state.v6
	return {}

## Called by main after every confirmed state (src/main.gd, after forest_state_changed()).
func state_changed() -> void:
	var view: Variant = v6().get("story")
	story = view if view is Dictionary else {}
	if not focus_goal.is_empty():
		var goal := goal_by_id(focus_goal)
		# The scene's goal stays on the flag until it is done, or the hall grows past its chapter.
		if goal.is_empty() or goal.get("state", "") in ["claimed", "ready"] or int(story.get("hall", 1)) != focus_hall:
			focus_goal = ""
	refresh_flag()
	if journal_visible and ui.modal.visible and not ui.command_in_progress:
		build_journal()
	check_scenes()

func goal_by_id(id: String) -> Dictionary:
	for chapter: Dictionary in story.get("chapters", []):
		for goal: Dictionary in chapter.get("goals", []):
			if String(goal.get("id", "")) == id:
				return goal
	return {}

func chapter_of(goal_id: String) -> Dictionary:
	for chapter: Dictionary in story.get("chapters", []):
		for goal: Dictionary in chapter.get("goals", []):
			if String(goal.get("id", "")) == goal_id:
				return chapter
	return {}

func current_goal() -> Dictionary:
	if story.is_empty():
		return {}
	if not focus_goal.is_empty():
		var focused := goal_by_id(focus_goal)
		if not focused.is_empty():
			return focused
	var current: Variant = story.get("current")
	if current is Dictionary:
		return goal_by_id(String(current.get("goal", "")))
	return {}

## Without the story module on the server (state.v6.story absent) the flag shows First Steps.
func starter_flag() -> bool:
	var steps: Variant = v6().get("starter")
	if not steps is Array or (steps as Array).is_empty():
		return false
	var current := {}
	var done := 0
	for step: Dictionary in steps:
		if step.get("claimed", false):
			done += 1
		elif current.is_empty():
			current = step
	if current.is_empty():
		return false
	flag.visible = String(ui.map_name) == "city" and not ((intro != null and is_instance_valid(intro)))
	flag_eyebrow.text = "FIRST STEPS · %d/%d" % [done + 1, (steps as Array).size()]
	flag_title.text = String(current.get("title", ""))
	flag_count.text = "Claim" if current.get("ready", false) else "→"
	flag.queue_redraw()
	return true

func refresh_flag() -> void:
	if flag == null:
		return
	if story.is_empty() and starter_flag():
		return
	var goal := current_goal()
	var playing := (intro != null and is_instance_valid(intro)) or (talk != null and is_instance_valid(talk))
	if story.is_empty() or goal.is_empty() or playing or String(ui.map_name) != "city":
		flag.visible = not story.is_empty() and not playing and String(ui.map_name) == "city"
		if flag.visible:
			flag_eyebrow.text = "QUEST JOURNAL"
			flag_title.text = "All goals done"
			flag_count.text = "✓"
		return
	flag.visible = true
	var chapter := chapter_of(String(goal.get("id", "")))
	flag_eyebrow.text = "CHAPTER %s · %s" % [ROMAN[clampi(int(chapter.get("hall", 1)), 1, 5) - 1], String(chapter.get("title", "")).to_upper()]
	flag_title.text = String(goal.get("title", ""))
	if goal.get("state", "") == "ready":
		flag_count.text = "Claim"
	else:
		flag_count.text = "%s/%s" % [short_number(int(goal.get("have", 0))), short_number(int(goal.get("need", 1)))]
	flag.queue_redraw()

static func short_number(value: int) -> String:
	if value >= 10000:
		return "%dk" % (value / 1000)
	return str(value)

# ------------------------------------------------------------------ scenes that play once

const LOCAL_SEEN := "user://hud.cfg"

func local_seen(scene: String) -> bool:
	var config := ConfigFile.new()
	return config.load(LOCAL_SEEN) == OK and bool(config.get_value("story", scene, false))

func remember_local(scene: String) -> void:
	var config := ConfigFile.new()
	config.load(LOCAL_SEEN)
	config.set_value("story", scene, true)
	config.save(LOCAL_SEEN)

func check_scenes() -> void:
	if ui.scene_loading or not is_instance_valid(ui.stage) or String(ui.map_name) != "city" or ui.state.is_empty():
		return
	if (intro != null and is_instance_valid(intro)) or (talk != null and is_instance_valid(talk)):
		return
	if story.is_empty():
		# A server without the story module: the intro once on this device for a new settlement.
		if not ui.player_id.is_empty() and ui.hall_level() == 1 and not local_seen("intro") and not scene_requested.has("intro") \
				and ui.forest_game != null and ui.forest_game.world_ready():
			scene_requested["intro"] = true
			play_intro()
		return
	var scenes: Dictionary = story.get("scenes", {})
	var hall := int(story.get("hall", 1))
	if hall == 1 and not scenes.has("intro") and not scene_requested.has("intro"):
		if ui.forest_game != null and ui.forest_game.world_ready():
			play_intro()
		return
	if hall >= 2 and not scenes.has("chapter2_talk") and not scene_requested.has("chapter2_talk"):
		play_talk()

func play_intro(replay := false) -> void:
	if ui.forest_game == null or not ui.forest_game.world_ready():
		ui.message.text = "The forest is still loading."
		return
	if ui.modal.visible:
		ui.close_modal()
	intro = StoryIntro.new()
	ui.add_child(intro)
	intro.finished.connect(func(_skipped: bool) -> void:
		intro = null
		if not replay:
			mark_seen("intro")
			focus_goal = ""
		refresh_flag()
		highlight_flag())
	intro.begin(ui)
	refresh_flag()

func play_talk() -> void:
	if ui.modal.visible:
		ui.close_modal()
	talk = StoryTalk.new()
	ui.add_child(talk)
	talk.finished.connect(func() -> void:
		talk = null
		mark_seen("chapter2_talk")
		focus_goal = "ch2_train"
		focus_hall = int(story.get("hall", 2))
		refresh_flag()
		highlight_flag())
	talk.begin(ui)
	refresh_flag()

func mark_seen(scene: String) -> void:
	scene_requested[scene] = true
	remember_local(scene)
	if not story.is_empty():
		ui.command({"kind": "story72", "action": "seen", "scene": scene})

func highlight_flag() -> void:
	if flag == null or not flag.visible:
		return
	flag.pivot_offset = flag.size * 0.5
	var tween := create_tween()
	tween.tween_property(flag, "scale", Vector2(1.08, 1.08), 0.18)
	tween.tween_property(flag, "scale", Vector2.ONE, 0.25)
	tween.tween_property(flag, "scale", Vector2(1.05, 1.05), 0.15)
	tween.tween_property(flag, "scale", Vector2.ONE, 0.2)

## Main calls this when the player taps the town hall (chapter I: «Hear the fugitive out»).
func hall_tapped() -> void:
	if visit_sent or story.is_empty():
		return
	var goal := goal_by_id("ch1_hall")
	if goal.is_empty() or goal.get("state", "") != "active":
		return
	visit_sent = true
	ui.command({"kind": "story72", "action": "visit", "target": "B01"})

# ------------------------------------------------------------------ the journal

func open_journal() -> void:
	if story.is_empty():
		ui.show_starter_goals()
		return
	journal_visible = true
	build_journal()

func build_journal() -> void:
	ui.open_modal("Quest Journal", "full", "TOWN HALL " + ROMAN[clampi(int(story.get("hall", 1)), 1, 5) - 1])
	var body: Container = ui.modal_body
	var current := current_goal()
	var claimed_all := 0
	var total_all := 0
	for chapter: Dictionary in story.get("chapters", []):
		claimed_all += int(chapter.get("claimed", 0))
		total_all += int(chapter.get("total", 0))
	var oak := KitMore.ProfileCard.new()
	oak.emblem = UiKit.tex("kit_emb_book")
	var chapter_now := chapter_of(String(current.get("id", "")))
	oak.title = String(chapter_now.get("title", "Quest Journal")) if not chapter_now.is_empty() else "Quest Journal"
	oak.banner = Color("#7a2f22")
	oak.pill = "%d of %d rewards" % [claimed_all, total_all]
	oak.lines = [["Chapter", ROMAN[clampi(int(chapter_now.get("hall", story.get("hall", 1))), 1, 5) - 1], null],
		["Now", String(current.get("title", "—")), null]]
	oak.note = "Rewards wait here until you claim them, even after the town hall grows."
	ui.v6_panels.menu_view.oak_column(oak, 0.3)
	if not last_gain.is_empty():
		var gain := UiKit.label(body, last_gain, 18, UiKit.GOOD)
		gain.name = "LastGain"
		last_gain = ""
	var hall := int(story.get("hall", 1))
	for chapter: Dictionary in story.get("chapters", []):
		var unlocked := bool(chapter.get("unlocked", false))
		if not unlocked and int(chapter.get("hall", 1)) > hall + 1:
			continue
		UiKit.section_header(body, "%s · %s   %d/%d" % [ROMAN[clampi(int(chapter.get("hall", 1)), 1, 5) - 1], String(chapter.get("title", "")),
			int(chapter.get("claimed", 0)), int(chapter.get("total", 0))])
		if not String(chapter.get("who", "")).is_empty():
			UiKit.label(body, String(chapter.who), 15, UiKit.INK_MUTED)
		if not unlocked:
			var lock := KitMore.Card.new()
			lock.icon = UiKit.tex("kit_emb_town")
			lock.icon_mode = "disc"
			lock.title = "Opens with Town Hall " + ROMAN[clampi(int(chapter.get("hall", 1)), 1, 5) - 1]
			lock.subtitle = "%d goals and their rewards are waiting." % int(chapter.get("total", 0))
			lock.plate = "dim"
			lock.custom_minimum_size.y = 84
			body.add_child(lock)
			continue
		for goal: Dictionary in chapter.get("goals", []):
			body.add_child(goal_card(goal, goal.get("id") == current.get("id")))
	var footer: Container = ui.modal_footer
	if footer != null:
		footer.show()
		var replay: Button = ui.button(footer, "Watch the intro", func() -> void: play_intro(true))
		UiKit.style_button(replay, "tertiary", 17)

func goal_card(goal: Dictionary, is_current: bool) -> Control:
	var id := String(goal.get("id", ""))
	var state := String(goal.get("state", "active"))
	var card := KitMore.Card.new()
	card.name = "Goal_" + id
	card.icon = UiKit.tex(ICONS.get(String(goal.get("kind", "")), "kit_emb_award"))
	card.icon_mode = "disc"
	card.title = String(goal.get("title", ""))
	card.subtitle = String(goal.get("action", ""))
	card.line = String(goal.get("helps", ""))
	var have := int(goal.get("have", 0))
	var need := maxi(1, int(goal.get("need", 1)))
	card.bar = clampf(float(have) / need, 0.0, 1.0)
	card.bar_green = have >= need
	card.bar_text = "%s / %s" % [ui.format_balance(mini(have, need)), ui.format_balance(need)]
	for resource: String in goal.get("reward", {}):
		var amount := int(goal.reward[resource])
		if amount > 0:
			card.chips.append([ui.resource_icons.get(resource), "+%s %s" % [ui.format_balance(amount), RESOURCE_EN.get(resource, resource)], UiKit.GOOD])
	card.custom_minimum_size.y = 128
	match state:
		"claimed":
			card.ribbon = "Claimed"
			card.ribbon_colour = Color("#5d6b4a")
			card.plate = "dim"
		"ready":
			card.ribbon = "Done"
			card.ribbon_colour = UiKit.GOOD
			card.plate = "gold"
			var claim: Button = card.add_action("Claim", "green", Vector2(150, 54))
			claim.name = "Claim"
			claim.disabled = claiming.has(id)
			claim.pressed.connect(claim_goal.bind(goal, claim))
		"waiting":
			card.ribbon = "Done · claim in order"
			card.ribbon_colour = Color("#7a6a52")
			var after := String(goal.get("waitsFor", "")).trim_prefix("starter:")
			card.subtitle = "First Steps are claimed in order: claim «%s» first." % title_of_starter(after)
		_:
			card.ribbon = "Now" if is_current else "Open"
			card.ribbon_colour = Color("#2a5d93") if is_current else Color("#7a6a52")
			if is_current:
				card.plate = "gold"
			var go: Button = card.add_action("Go", "primary" if is_current else "tertiary", Vector2(120, 50))
			go.name = "Go"
			go.pressed.connect(go_to.bind(goal))
	card.accessibility_name = "%s · %s · %d/%d · %s" % [card.title, card.subtitle, have, need, card.ribbon]
	return card

func title_of_starter(starter_id: String) -> String:
	for chapter: Dictionary in story.get("chapters", []):
		for goal: Dictionary in chapter.get("goals", []):
			if String(goal.get("id", "")) == "starter:" + starter_id:
				return String(goal.get("title", starter_id))
	return starter_id

## Claim: disabled at once (a double tap sends nothing more); the server credits the reward once
## (receipt story:<id>, or the First Steps receipt); a retry after a dropped answer replays the same
## Idempotency-Key (main.command).
func claim_goal(goal: Dictionary, control: Button) -> void:
	var id := String(goal.get("id", ""))
	if claiming.has(id) or control.disabled:
		return
	claiming[id] = true
	control.disabled = true
	control.text = "…"
	var before := balances()
	var accepted: bool = await ui.command({"kind": "story72", "action": "claim", "goalId": id})
	claiming.erase(id)
	if accepted:
		var parts: PackedStringArray = []
		var after := balances()
		for resource: String in goal.get("reward", {}):
			var amount := int(goal.reward[resource])
			if amount > 0:
				parts.append("+%s %s" % [ui.format_balance(amount), RESOURCE_EN.get(resource, resource)])
		var gained := 0
		for resource in after:
			gained += maxi(0, int(after[resource]) - int(before.get(resource, 0)))
		Sound.ui("reward")
		var next := current_goal()
		last_gain = "Claimed «%s»: %s." % [String(goal.get("title", "")), ", ".join(parts)]
		ui.message.text = last_gain + ("  Next: " + String(next.get("title", "")) if not next.is_empty() and next.get("id") != id else "")
		focus_goal = ""
	refresh_flag()
	if journal_visible and ui.modal.visible:
		build_journal()

func balances() -> Dictionary:
	var out := {}
	var stock: Variant = v6().get("stock", {})
	for resource in RESOURCE_EN:
		out[resource] = int(stock.get(resource, 0)) if stock is Dictionary else 0
	return out

## Go: to the object or screen where the goal is done.
func go_to(goal: Dictionary) -> void:
	var target := String(goal.get("go", ""))
	var kind := String(goal.get("kind", ""))
	journal_visible = false
	if target == "tree":
		ui.close_modal()
		ui.message.text = "Tap a tree at the edge of the town and fell it."
		return
	if target == "hunt":
		ui.show_city_hunt()
		return
	if target.begins_with("build:"):
		ui.v6_panels.inspect(target.trim_prefix("build:"))
		return
	if target.begins_with("forest:"):
		ui.close_modal()
		var game: Node = ui.forest_game
		if game != null and game.client.unlocked():
			game.world_call("focus_site", [target.trim_prefix("forest:"), 34.0])
		elif game != null and game.hud != null:
			game.hud.show_locked("locked")
		return
	if target == "B01" and kind == "visit":
		ui.close_modal()
		focus_building("B01")
		ui.message.text = "Tap the town hall."
		return
	if target == "B11" or kind == "trained":
		ui.v6_panels.services("B11")
		return
	if target.begins_with("B"):
		ui.v6_panels.inspect(target)
		return
	ui.close_modal()

func focus_building(concept: String) -> void:
	var stage: Node = ui.stage
	if not is_instance_valid(stage):
		return
	for marker: Dictionary in stage.place_markers:
		if String(marker.get("kind", "")) != "building":
			continue
		var item: Variant = marker.get("item")
		if item is Dictionary and (String(item.get("conceptType", "")) == concept or (concept == "B01" and String(item.get("type", "")).begins_with("ECO-05"))):
			var at: Vector3 = marker.position - Vector3(0, 5, 0)
			stage.target = Vector3(at.x, stage.target.y, at.z)
			return
