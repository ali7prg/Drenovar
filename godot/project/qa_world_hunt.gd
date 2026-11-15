extends SceneTree

# Creature hunt on the WORLD map (Велькор), driven by world-shaped server data:
# the world encounter names its kind only in spec.id, the army comes from
# state.world.armies and its fight arrives as windows of timeline rows
# [at, kind, unitId, index, hp, damage] around each poll. Before build 51 the world
# fight had no battle places, no charge and no blows (soldiers stood in the column).
# Also checks the city's object events: the creature hp after a blow is creatureHP.

var checks := 0
var failures := 0
# Optional PNG frames of the fight (needs a renderer):
#   xvfb-run -s "-screen 0 1366x630x24" godot --rendering-driver opengl3 --path . -s qa_world_hunt.gd -- --capture=/abs/dir
var capture := ""

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func frame(stage, state: Dictionary, at: float) -> void:
	stage.battle_fx.begin()
	stage.present_armies(state, at)
	stage.present_creatures(state, at, 0.25)

func settle(stage, state: Dictionary, at: float) -> void:
	for i in 24:
		frame(stage, state, at)
		await process_frame

func shot(stage, state: Dictionary, at: float, name: String) -> void:
	if capture.is_empty():
		return
	frame(stage, state, at)
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(capture.path_join(name + ".png"))

func soldiers(stage, id: String) -> Array:
	var actor: Node3D = stage.actors.get_node_or_null(NodePath(id))
	if actor == null:
		return []
	return actor.get_children().filter(func(child): return child.name != &"Ferry" and child.visible)

func visible_count(stage, kind: String) -> int:
	return stage.battle_fx.pools[kind].filter(func(node): return node.visible).size()

func outside_body(point: Vector3, beast: Vector3, face: Vector3, body: Vector2) -> float:
	var offset := Vector3(point.x - beast.x, 0.0, point.z - beast.z)
	var ahead := offset.dot(face)
	var across := offset.dot(Vector3(face.z, 0.0, -face.x))
	return sqrt(pow(ahead / body.x, 2.0) + pow(across / body.y, 2.0)) - 1.0

func run() -> void:
	root.size = Vector2i(1366, 630)
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture = argument.trim_prefix("--capture=")
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	city_events(game.stage)
	if game.map_name != "world":
		await game.show_scene("world")
	var stage = game.stage
	check(stage.map_name == "world", "World map not shown")
	var state: Dictionary = game.state.duplicate(true)
	var me := str(state.get("playerId", ""))
	var target: Dictionary = state.world.encounters[0]
	check(not target.has("species") and str(target.spec.get("id", "")) == "velkor", "World encounter is not shaped like the server's")
	check(stage.creature_species(target) == "velkor", "World creature kind not found from spec.id")
	target.patrol = []
	target.status = "reserved"
	var beast: Vector3 = stage.ground_point(stage.point(target.position))
	var home_city: Dictionary = state.world.cities[0]
	var home: Vector3 = stage.point(home_city.position)
	var path := []
	for k in 13:
		var q := home.lerp(beast, k / 12.0)
		path.append({"x": q.x, "z": q.z})
	var party := {"ENG-01": 6, "ENG-02": 6, "ENG-03": 4, "ENG-05": 2}
	var start := 700000.0
	var arrive := start + 16000.0
	var army := {"id": "world-hunt", "owner": me, "target": target.id, "name": target.spec.name, "worldKind": "velkor",
		"status": "outbound", "path": path, "units": party, "startsAt": start, "arrivesAt": arrive,
		"travelMs": arrive - start, "count": 18}
	state.world.armies = [army]
	state.world.encounters = [target]
	stage.target = beast
	stage.zoom = 40.0
	stage.update_camera(0, true)

	# Marching on the world map: a battle plan exists, the column halts in front.
	await settle(stage, state, start + 7000.0)
	var cache: Dictionary = stage.army_routes.get("world-hunt", {})
	var plan: Dictionary = cache.get("engage", {})
	check(not plan.is_empty(), "No battle plan for the world hunt (soldiers would stand in the column)")
	if plan.is_empty():
		finish()
		return
	check(float(plan.stop) < float(cache.distances[-1]) - 1.0, "World column does not halt before the creature")
	var halt_at := float(plan.halt_at)
	var face: Vector3 = plan.face
	var body: Vector2 = plan.body

	# The column halted: soldiers charge to their places, dust under the runners.
	await settle(stage, state, halt_at + 400.0)
	await shot(stage, state, halt_at + 400.0, "world_1_roar_charge")
	check(visible_count(stage, "dust") > 0, "No dust under the charging soldiers")
	var running := soldiers(stage, "world-hunt").filter(func(unit): return str(unit.get_meta("clip", "")) in ["run", "walk", "gallop", "trot", "canter"])
	check(running.size() >= 6, "Soldiers do not run to the creature: %d" % running.size())
	var creature: Node3D = stage.creatures.get_node_or_null(NodePath(target.id))
	check(creature != null and creature.visible, "Велькор not shown on the world map")
	if creature != null:
		check(creature.get_meta("clip", "") == "Roar", "Велькор does not roar at the halt: " + str(creature.get_meta("clip", "")))

	# Fighting, first poll window: rows with the creature hp and the blow's damage.
	var hp := 1900.0
	var all_rows := []
	for k in 18:
		var at := 200.0 + k * 300.0
		var damage := 60.0 + (k % 5) * 7.0 if k < 17 else hp
		hp = maxf(0.0, hp - damage)
		all_rows.append([at, "soldier_attack", ["ENG-01", "ENG-02", "ENG-03"][k % 3], k % 6, hp, damage])
		if k % 4 == 1:
			all_rows.append([at + 120.0, "antler_charge" if k % 8 == 1 else "creature_attack", "ENG-01", k % 6, 30, 40])
	var slain_at := 200.0 + 17 * 300.0
	army.status = "fighting"
	army.battleAt = arrive
	army.battleEndsAt = arrive + slain_at + 200.0
	army.fallen = []
	army.events = all_rows.filter(func(row): return float(row[0]) <= 2700.0)
	var first_window: int = army.events.size()
	await settle(stage, state, arrive + 1450.0)
	await shot(stage, state, arrive + 1450.0, "world_2_fight")
	await settle(stage, state, arrive + 2160.0)
	await shot(stage, state, arrive + 2160.0, "world_3_fight")
	await settle(stage, state, arrive + 1450.0)
	var units := soldiers(stage, "world-hunt")
	check(units.size() == 18, "Soldiers on the world field: %d" % units.size())
	var inside := 0
	var melee := 0
	var melee_close := 0
	var attacking := 0
	for unit: Node3D in units:
		var at := unit.global_position
		if outside_body(at, beast, face, body) <= 0.05:
			inside += 1
		var id := String(unit.name).get_slice("_", 0)
		if id in ["ENG-01", "ENG-02"]:
			melee += 1
			if Vector2(at.x - beast.x, at.z - beast.z).length() < body.x + 4.5:
				melee_close += 1
			if unit.get_meta("clip", "") == "attack":
				attacking += 1
	check(inside == 0, "%d soldiers inside Велькор" % inside)
	check(melee_close == melee, "Melee soldiers away from Велькор: %d of %d" % [melee_close, melee])
	check(attacking >= 3, "Melee line idle in the world fight: %d swinging" % attacking)
	check(visible_count(stage, "number") > 0, "No damage numbers in the world fight")
	var fx: Dictionary = stage.fx_timelines.get("world-hunt", {})
	check(not fx.is_empty() and fx.hits.all(func(hit): return float(hit[1]) >= 60.0), "World blows lost their damage: " + str(fx.get("hits", []).slice(0, 3)))
	check(visible_count(stage, "bar") == 1, "No health bar over Велькор")

	# Second poll window: the earlier rows stay known (merged), the creature falls at the last blow.
	army.events = all_rows.filter(func(row): return float(row[0]) >= 2400.0)
	await settle(stage, state, arrive + slain_at + 1300.0)
	await shot(stage, state, arrive + slain_at + 1300.0, "world_4_slain")
	var merged: Array = stage.army_routes["world-hunt"].get("merged_rows", [])
	check(merged.size() == all_rows.size(), "Poll windows not merged: %d of %d rows (first window %d)" % [merged.size(), all_rows.size(), first_window])
	if creature != null:
		check(creature.get_meta("clip", "") == "Death", "Велькор did not die at the last blow: " + str(creature.get_meta("clip", "")))

	# An old server's rows (no hp on soldier blows): no crash, no wrong numbers.
	var legacy := [[300.0, "soldier_attack", "ENG-01", 0, null], [600.0, "creature_attack", "ENG-01", 1, 50]]
	var old_fx: Dictionary = stage.battle_timeline({"id": "legacy"}, target, legacy)
	check(old_fx.hits.size() == 1 and float(old_fx.hits[0][1]) == 0.0, "Rows without hp give a made-up damage: " + str(old_fx.hits))
	finish()

# City fights send event objects (simulate() in combat.mjs): the creature's hp after
# a blow is creatureHP. Before build 51 the client read "hp" there, so the real game
# showed no damage numbers and the creature never fell at its last blow.
func city_events(stage) -> void:
	var events := []
	var hp := 600
	for k in 6:
		hp -= 100
		events.append({"at": 200 + k * 300, "kind": "soldier_attack", "unitId": "ENG-01", "index": k, "damage": 100, "creatureHP": hp})
	events.append({"at": 500, "kind": "creature_attack", "unitId": "ENG-01", "index": 2, "damage": 40, "hp": 0})
	var fx: Dictionary = stage.battle_timeline({"id": "city-objects"}, {"spec": {"hp": 600}}, events)
	check(fx.hits.size() == 6 and fx.hits.all(func(hit): return float(hit[1]) == 100.0), "City blows show no damage: " + str(fx.hits))
	check(float(fx.hits[-1][2]) == 0.0, "City creature never reaches 0 hp: " + str(fx.hits[-1]))
	var members: Dictionary = stage.battle_events({"battle": {"events": events}})
	check(members.members.get("ENG-01:2", []).any(func(e): return e[1] == "creature_attack" and e[4] == 0), "Soldier felled by the creature not seen")

func finish() -> void:
	print("QA_WORLD_HUNT checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
