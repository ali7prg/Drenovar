extends SceneTree
## Story chapters (build 1025) end to end: the real game against the local V6 fixture with the story
## module (server-patches/story-quests-v1):
##   DRENOVAR_SERVER_ROOT=<server checkout with the patch> DRENOVAR_QA_PORT=8800 DRENOVAR_QA_ADVENTURE=1 \
##     DRENOVAR_QA_CONDITIONAL=1 DRENOVAR_QA_HALL=1 node godot/tools/qa-v6-1022-server.mjs
##   godot --headless --path godot/project -s qa_story_flow.gd -- --server=http://127.0.0.1:8800 [--shots=<dir>]
## A new settlement: the intro starts by itself and Skip ends it (seen once); the flag shows chapter I's
## first goal; tapping the town hall completes it; Claim pays once although pressed twice; a claim whose
## answer is lost is retried with the same key and pays once; hall II plays the villagers' talk once and
## puts the recruiting goal on the flag; hall III opens the forest with a chapter II reward unclaimed, the
## reward stays ready and is claimed later; a developed settlement (hall V) opens all five chapters.

var game: Node
var flow: Node
var checks := 0
var failures: Array[String] = []
var server := "http://127.0.0.1:8800"
var shots_dir := ""

func check(value: bool, detail: String) -> void:
	checks += 1
	print("STORY_QA ", "ok   " if value else "FAIL ", detail)
	if not value:
		failures.append(detail)

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):
			server = arg.trim_prefix("--server=")
		elif arg.begins_with("--shots="):
			shots_dir = arg.trim_prefix("--shots=")
	call_deferred("run")

func frames(count: int) -> void:
	for i in count:
		await process_frame

func shot(name: String) -> void:
	if shots_dir.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(shots_dir)
	root.get_texture().get_image().save_jpg(shots_dir.path_join(name + ".jpg"), 0.9)

func http(path: String, body := "") -> Variant:
	var request := HTTPRequest.new()
	root.add_child(request)
	request.request(server + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, body)
	var result: Array = await request.request_completed
	request.queue_free()
	return JSON.parse_string((result[3] as PackedByteArray).get_string_from_utf8())

## Waits until a fresh state (a poll or a command answer) satisfies `predicate`.
func wait_state(predicate: Callable, seconds := 40.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if predicate.call():
			return true
		game.poll_account_state(true)
		await frames(20)
	return predicate.call()

func goal(id: String) -> Dictionary:
	return flow.goal_by_id(id)

func reward_status(receipt: String) -> String:
	var rewards: Variant = game.state.get("v6", {}).get("rewards", {})
	return String(rewards.get(receipt, {}).get("status", "")) if rewards is Dictionary else ""

func requests_of(action: String) -> Array:
	var log: Variant = await http("/qa/requests")
	var out: Array = []
	for entry in (log if log is Array else []):
		if String(entry.get("kind", "")) == "story72" and String(entry.get("action", "")) == action:
			out.append(entry)
	return out

func find_button(node: Node, button_name: String) -> Button:
	for child in node.find_children(button_name, "Button", true, false):
		return child
	return null

func run() -> void:
	root.size = Vector2i(1366, 630)
	await http("/test/story-reset")
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 120000
	while (game.scene_loading or not is_instance_valid(game.stage) or game.player_id.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	flow = game.story_flow
	check(await wait_state(func() -> bool: return not flow.story.is_empty()), "the server projects state.v6.story")
	check(int(flow.story.get("hall", 0)) == 1, "a new settlement starts at Town Hall I")
	# ---- the intro: by itself once the forest layer is ready, Skip ends it, seen once on the server
	deadline = Time.get_ticks_msec() + 600000
	while (flow.intro == null or not is_instance_valid(flow.intro)) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(flow.intro != null and is_instance_valid(flow.intro), "the intro starts by itself for the new settlement")
	if flow.intro != null and is_instance_valid(flow.intro):
		check(not game.hud.visible, "the game HUD is hidden during the intro")
		await frames(30)
		flow.intro.skip_button.pressed.emit()
		await frames(5)
	check(game.hud.visible, "the HUD is back after the intro")
	check(await wait_state(func() -> bool: return flow.story.get("scenes", {}).has("intro")), "the server marks the intro seen")
	await frames(60)
	check(flow.intro == null, "the intro does not start again")
	# ---- chapter I: the flag, the hall tap, Claim pressed twice
	check(flow.flag.visible, "the quest flag is on the settlement screen")
	check(flow.flag_title.text == String(goal("ch1_hall").get("title", "?")), "the flag names chapter I's first goal: " + flow.flag_title.text)
	var flag_rect: Rect2 = flow.flag.get_global_rect()
	var view := Vector2(root.size)
	check(flag_rect.position.x < view.x * 0.3 and flag_rect.end.y < view.y * 0.32, "the flag sits under the profile, clear of the wallet and the controls")
	await shot("01_flag")
	flow.open_journal()
	await frames(10)
	check(game.modal.visible, "the flag opens the quest journal")
	check(find_button(game.modal_body, "Go") != null, "the active goal has Go")
	await shot("02_journal")
	game.close_modal()
	for marker: Dictionary in game.stage.place_markers:
		if String(marker.get("kind", "")) == "building" and String(marker.item.get("type", "")).begins_with("ECO-05"):
			game.open_building_ring(marker)
			break
	check(await wait_state(func() -> bool: return goal("ch1_hall").get("state", "") == "ready"), "tapping the town hall completes «%s»" % goal("ch1_hall").get("title", ""))
	await frames(5)
	check(flow.flag_count.text == "Claim", "the flag shows Claim when the reward is ready")
	game.close_modal()
	flow.open_journal()
	await frames(10)
	var claim := find_button(game.modal_body, "Claim")
	check(claim != null, "the ready goal has Claim")
	var before: Dictionary = flow.balances()
	if claim != null:
		claim.pressed.emit()
		claim.pressed.emit()
	check(await wait_state(func() -> bool: return goal("ch1_hall").get("state", "") == "claimed"), "Claim credits the reward")
	check(reward_status("story:ch1_hall") in ["claimed", ""], "receipt story:ch1_hall is not left pending on the server")
	var claims := await requests_of("claim")
	check(claims.size() == 1, "a double tap sends one claim (sent %d)" % claims.size())
	var after: Dictionary = flow.balances()
	check(int(after.food) - int(before.food) >= 100 and int(after.food) - int(before.food) < 200, "food +100 once (%d → %d)" % [before.food, after.food])
	await shot("03_claimed")
	# ---- a lost answer: the retry with the same key pays once
	await http("/test/felled?count=1")
	check(await wait_state(func() -> bool: return goal("ch1_tree").get("state", "") == "ready"), "a felled tree completes «%s»" % goal("ch1_tree").get("title", ""))
	await http("/qa/fault", JSON.stringify({"kind": "story72", "count": 1, "mode": "drop"}))
	var wood_before := int(flow.balances().wood)
	var accepted: bool = await game.command({"kind": "story72", "action": "claim", "goalId": "ch1_tree"})
	check(await wait_state(func() -> bool: return goal("ch1_tree").get("state", "") == "claimed"), "the claim whose answer was lost ends claimed (accepted=%s)" % str(accepted))
	var tree_claims := (await requests_of("claim")).filter(func(e: Dictionary) -> bool: return true)
	var receipts := {}
	for entry in tree_claims.slice(1):
		receipts[String(entry.get("receipt", ""))] = true
	check(tree_claims.size() >= 3 and receipts.size() == 1, "the retry reuses the Idempotency-Key (%d sends, %d keys)" % [tree_claims.size() - 1, receipts.size()])
	var wood_gain := int(flow.balances().wood) - wood_before
	check(wood_gain >= 120 and wood_gain < 240, "wood +120 once after the retry (+%d)" % wood_gain)
	# ---- Town Hall II: the villagers' talk once, then the recruiting goal
	await http("/test/hall?level=2")
	check(await wait_state(func() -> bool: return int(flow.story.get("hall", 0)) == 2), "the server reports Town Hall II")
	deadline = Time.get_ticks_msec() + 20000
	while (flow.talk == null or not is_instance_valid(flow.talk)) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(flow.talk != null and is_instance_valid(flow.talk), "Town Hall II plays the villagers' talk")
	await shot("04_talk")
	while flow.talk != null and is_instance_valid(flow.talk):
		await process_frame
	check(flow.flag_title.text == String(goal("ch2_train").get("title", "?")), "after the talk the flag shows the recruiting goal: " + flow.flag_title.text)
	check(await wait_state(func() -> bool: return flow.story.get("scenes", {}).has("chapter2_talk")), "the talk is marked seen")
	await frames(90)
	check(flow.talk == null, "the talk does not play again")
	# ---- Town Hall III with a chapter II reward left unclaimed
	await http("/test/hall?level=3")
	check(await wait_state(func() -> bool: return int(flow.story.get("hall", 0)) == 3), "the server reports Town Hall III")
	check(goal("ch2_hall").get("state", "") == "ready", "chapter II's «%s» is ready and left unclaimed" % goal("ch2_hall").get("title", ""))
	check(await wait_state(func() -> bool: return game.forest_game != null and game.forest_game.client.unlocked()), "the forest opens at Town Hall III with the reward unclaimed")
	check(goal("ch3_find").get("go", "") == "forest:lf_site_01", "chapter III's first forest goal leads to the Birch Clearing")
	check(goal("ch3_find").get("state", "") == "active", "the intro itself completed no forest goal")
	flow.open_journal()
	await frames(10)
	await shot("05_journal_hall3")
	game.close_modal()
	check(await game.command({"kind": "story72", "action": "claim", "goalId": "ch2_hall"}), "the chapter II reward is claimed later")
	check(await wait_state(func() -> bool: return goal("ch2_hall").get("state", "") == "claimed"), "… and is credited at Town Hall III")
	# ---- a developed settlement
	await http("/test/hall?level=5")
	check(await wait_state(func() -> bool: return int(flow.story.get("hall", 0)) == 5), "the server reports Town Hall V")
	var unlocked := 0
	for chapter: Dictionary in flow.story.get("chapters", []):
		unlocked += 1 if chapter.get("unlocked", false) else 0
	check(unlocked == 5, "all five chapters are open at Town Hall V")
	var now: Dictionary = flow.current_goal()
	check(not now.is_empty() and (int(flow.chapter_of(String(now.get("id", ""))).get("hall", 0)) == 5 or now.get("state", "") == "ready"),
		"the flag names a chapter V goal or a ready reward: " + flow.flag_title.text)
	flow.open_journal()
	await frames(10)
	await shot("06_journal_hall5")
	print("STORY_QA %d checks, %d failures" % [checks, failures.size()])
	for failure in failures:
		print("STORY_QA failure: ", failure)
	quit(0 if failures.is_empty() else 1)
