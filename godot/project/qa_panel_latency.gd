extends SceneTree

# Measures the main-thread cost of opening every major game window and the
# frame that follows it (layout + first draw). Headless CPU timing only: it
# catches synchronous work in touch handlers, not GPU cost on the device.

const BUDGET_MS := 40.0
var failures: Array[String] = []
var checks := 0
var rows: Array = []

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func measure(game: Node, label: String, action: Callable) -> void:
	game.close_modal()
	await process_frame
	var started := Time.get_ticks_usec()
	action.call()
	var call_ms := (Time.get_ticks_usec() - started) / 1000.0
	var frame_started := Time.get_ticks_usec()
	await process_frame
	var frame_ms := (Time.get_ticks_usec() - frame_started) / 1000.0
	rows.append({"panel": label, "call_ms": snappedf(call_ms, 0.01), "next_frame_ms": snappedf(frame_ms, 0.01)})
	check(call_ms < BUDGET_MS, "%s opened in %.1f ms (budget %.0f ms)" % [label, call_ms, BUDGET_MS])

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	if game.player_id.is_empty():
		game.player_id = "fixture"
		game.state = game.state.duplicate(true)
		game.state.healthy = {"ENG-09": 18, "ENG-01": 6}
	# Warm caches once, as a player would have after the first visit.
	game.show_controls_menu()
	await process_frame
	var panels := {
		"controls_menu": game.show_controls_menu,
		"city_actions": game.show_city_actions,
		"economy": game.show_economy,
		"construction": game.show_construction,
		"starter_goals": game.show_starter_goals,
		"armies": game.show_armies,
		"hospital": game.show_hospital,
		"training_buildings": game.show_training_buildings,
		"reports": game.show_reports,
		"account": game.show_account,
		"performance": game.show_performance,
		"city_hunt": game.show_city_hunt,
		"clearings": game.show_clearings,
	}
	for label in panels:
		await measure(game, label, panels[label])
	for building in game.state.city.buildings:
		await measure(game, "building_" + building.type, func(): game.inspect_building(building))
	var barracks: Dictionary = game.recruitment_buildings()[0]
	await measure(game, "recruitment_first", func(): game.open_recruitment(barracks))
	await measure(game, "recruitment_again", func(): game.open_recruitment(barracks))
	if not game.state.encounters.is_empty():
		await measure(game, "encounter", func(): game.inspect_encounter(game.state.encounters[0]))
	game.close_modal()
	await game.show_scene("world")
	await measure(game, "world_directory", game.show_world_directory)
	await measure(game, "world_cities", game.show_world_cities)
	await measure(game, "world_marches", game.show_world_marches)
	await measure(game, "map_options", game.show_map_options)
	await measure(game, "environment_catalog", func(): game.show_environment_catalog(0))
	await measure(game, "world_hunt", game.show_world_hunt)
	rows.sort_custom(func(a, b): return a.call_ms > b.call_ms)
	for row in rows:
		print("PANEL ", JSON.stringify(row))
	print("QA_PANEL_LATENCY panels=", rows.size(), " checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
