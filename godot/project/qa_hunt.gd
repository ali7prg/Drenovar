extends SceneTree

# Creature hunt choreography in the city, driven by a server-shaped battle timeline:
# the column halts in front of the creature (never on it), soldiers run to places
# around it and none stands inside its body or in the river, the creature faces the
# army head first and roars, melee soldiers swing during the fight, the slain
# creature lies on the field and then sinks away, the march line shows the route
# ahead only while marching.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func frame(stage, state: Dictionary, at: float) -> void:
	stage.present_armies(state, at)
	stage.present_creatures(state, at, 0.25)

func settle(stage, state: Dictionary, at: float) -> void:
	# The creature turns and moves smoothly: a few frames at the same moment.
	for i in 24:
		frame(stage, state, at)
		await process_frame

func soldiers(stage, id: String) -> Array:
	var actor: Node3D = stage.actors.get_node_or_null(NodePath(id))
	if actor == null:
		return []
	return actor.get_children().filter(func(child): return child.name != &"Ferry" and child.visible)

# Distance of a point outside the creature's body outline (ellipse of its half
# length along the facing and half width across), in metres along the ray.
func outside_body(point: Vector3, beast: Vector3, face: Vector3, body: Vector2) -> float:
	var offset := Vector3(point.x - beast.x, 0.0, point.z - beast.z)
	var ahead := offset.dot(face)
	var across := offset.dot(Vector3(face.z, 0.0, -face.x))
	return sqrt(pow(ahead / body.x, 2.0) + pow(across / body.y, 2.0)) - 1.0

func run() -> void:
	root.size = Vector2i(1366, 630)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	if game.map_name != "city":
		await game.show_scene("city")
	var stage = game.stage
	# A volley: several blows on one server tick keep their order, each number is its own blow.
	var volley := []
	var left := 3500
	for k in 12:
		left -= 70 + k
		volley.append([2000.0 if k >= 6 else 0.0, "soldier_attack", "ENG-03", k % 6, left])
	var fx: Dictionary = stage.battle_timeline({"id": "volley"}, {"spec": {"hp": 3500}}, volley)
	var damages: Array = fx.hits.map(func(hit): return roundi(float(hit[1])))
	check(damages == range(12).map(func(k): return 70 + k), "Volley damage shuffled: " + str(damages))
	check(fx.hits[11][3] == 5, "Volley blows not ranked: " + str(fx.hits[11]))
	var state: Dictionary = game.state.duplicate(true)
	var target: Dictionary = state.encounters[0]
	target.patrol = []
	target.level = 2
	target.status = "reserved"
	target.spec = {"hp": 1400, "name": "Тенерис"}
	var beast: Vector3 = stage.ground_point(stage.point(target.position))
	# Server-like route: grid steps from the barracks area to the creature itself.
	var home := Vector3(-5, 0, 8)
	var path := []
	for k in 9:
		var q := home.lerp(beast, k / 8.0)
		path.append({"x": q.x, "z": q.z})
	var party := {"ENG-01": 8, "ENG-02": 8, "ENG-03": 6, "ENG-05": 2}
	var events := []
	var hp := 1400.0
	for k in 14:
		hp = maxf(0.0, hp - 100.0)
		events.append([300.0 + k * 400.0, "soldier_attack", ["ENG-03", "ENG-01", "ENG-02"][k % 3], k % 6, hp])
		if k % 3 == 0:
			events.append([500.0 + k * 400.0, "creature_attack", "ENG-01", k % 8, 40])
	var slain_at := 300.0 + 13 * 400.0
	var start := 500000.0
	var arrive := start + 14000.0
	var ends := arrive + slain_at
	var army := {"id": "army-hunt", "status": "outbound", "target": target.id, "path": path, "units": party,
		"startsAt": start, "arrivesAt": arrive, "owner": state.get("playerId", "")}
	state.armies = [army]
	state.encounters = [target]
	stage.target = beast
	stage.zoom = 40.0
	stage.update_camera(0, true)

	# Marching: the line shows the route still ahead.
	await settle(stage, state, start + 6000.0)
	var line: MeshInstance3D = stage.march_lines.get_node_or_null("army-hunt")
	check(line != null and line.visible, "March line not shown while marching")
	var plan: Dictionary = stage.army_routes["army-hunt"].get("engage", {})
	check(not plan.is_empty(), "No battle plan for the hunt")
	if plan.is_empty():
		finish()
		return
	var face: Vector3 = plan.face
	var body: Vector2 = plan.body
	check(float(plan.stop) < float(stage.army_routes["army-hunt"].distances[-1]) - 1.0, "Column does not halt before the creature")
	if line != null:
		var to_m: float = line.material_override.get_shader_parameter("to_m")
		check(absf(to_m - float(plan.stop)) < 0.01, "March line runs past the halt point")
	var halt_at := float(plan.halt_at)
	check(halt_at < arrive, "Halt is not before the arrival")

	# The column halted: the creature turns to the army and roars.
	await settle(stage, state, halt_at + 500.0)
	var creature: Node3D = stage.creatures.get_node_or_null(NodePath(target.id))
	check(creature != null and creature.visible, "Creature not shown during the approach")
	if creature != null:
		var head := creature.global_transform.basis.x.normalized()
		check(Vector3(head.x, 0, head.z).normalized().dot(face) > 0.95, "Creature does not face the army head first (dot %.2f)" % Vector3(head.x, 0, head.z).normalized().dot(face))
		check(creature.get_meta("clip", "") == "Roar", "Creature does not roar when the army halts: " + str(creature.get_meta("clip", "")))

	# Fighting: everyone on a battle place, none inside the body or in the river.
	army.status = "fighting"
	army.battleAt = arrive
	army.battleEndsAt = ends
	army.battle = {"events": events}
	army.fallen = []
	target.status = "fighting"
	await settle(stage, state, arrive + 2600.0)
	var units := soldiers(stage, "army-hunt")
	check(units.size() == 24, "Soldiers on the field: %d" % units.size())
	var closest := INF
	var wet := 0
	var melee_close := 0
	var melee := 0
	var attacking := 0
	for unit: Node3D in units:
		var at := unit.global_position
		closest = minf(closest, outside_body(at, beast, face, body))
		if stage.sample_city(at.x, at.z) <= -0.2:
			wet += 1
		var id := String(unit.name).get_slice("_", 0)
		if id in ["ENG-01", "ENG-02"]:
			melee += 1
			if Vector2(at.x - beast.x, at.z - beast.z).length() < body.x + 4.5:
				melee_close += 1
			if unit.get_meta("clip", "") == "attack":
				attacking += 1
		var looking := Vector3(sin(unit.rotation.y), 0, cos(unit.rotation.y))
		var toward := Vector3(beast.x - at.x, 0, beast.z - at.z).normalized()
		check(looking.dot(toward) > 0.7, "%s does not face the creature" % unit.name)
	check(closest > 0.05, "A soldier stands inside the creature (%.2f)" % closest)
	check(wet == 0, "%d soldiers stand in the river" % wet)
	check(melee_close == melee, "Melee soldiers away from the creature: %d of %d close" % [melee_close, melee])
	check(attacking >= 3, "Melee line idle during the fight: %d swinging" % attacking)
	check(stage.battle_fx.pools["ring"].filter(func(node): return node.visible).size() == 1, "No ring under the creature during the fight")

	# The creature falls at the last blow.
	await settle(stage, state, arrive + slain_at + 1300.0)
	check(creature.get_meta("clip", "") == "Death", "Creature did not die: " + str(creature.get_meta("clip", "")))

	# The army leaves: the body stays a moment, then sinks away; soldiers regroup.
	army.status = "returning"
	army.returnPath = path.duplicate()
	army.returnPath.reverse()
	army.returnStartsAt = ends
	army.returnsAt = ends + 14000.0
	army.returnUnits = party
	target.status = "defeated"
	target.hp = 0
	await settle(stage, state, ends + 600.0)
	check(creature.visible and creature.get_meta("clip", "") == "Death", "Slain creature vanished at once when the army left")
	var lying_y := creature.position.y
	line = stage.march_lines.get_node_or_null("army-hunt")
	check(line != null and line.visible, "No march line home")
	await settle(stage, state, ends + stage.CORPSE_MS - 300.0)
	check(creature.position.y < lying_y - 1.0, "Slain creature does not sink away")
	await settle(stage, state, ends + stage.CORPSE_MS + 400.0)
	check(not is_instance_valid(creature) or not creature.visible, "Slain creature still shown after it sank")
	await settle(stage, state, ends + 3000.0)
	units = soldiers(stage, "army-hunt")
	var leader: Vector3 = stage.army_routes["army-hunt"].position
	var gathered := units.filter(func(unit): return unit.global_position.distance_to(leader) < 18.0).size()
	check(gathered == units.size(), "Soldiers not back in the column: %d of %d" % [gathered, units.size()])
	await river_bank(stage, state, target, party, events)
	finish()

# A creature on the river bank (the column comes from the land side): no soldier
# is placed in the water; places that would be wet turn around the creature.
func river_bank(stage, state: Dictionary, target: Dictionary, party: Dictionary, events: Array) -> void:
	var z := -30.0
	var x := 0.0
	while x < 60.0 and stage.sample_city(x, z) > -0.2:
		x += 0.25
	check(x < 60.0, "No river found for the bank case")
	target.position = {"x": x - 3.0, "z": z}
	target.status = "fighting"
	target.erase("hp")
	var beast: Vector3 = stage.ground_point(stage.point(target.position))
	var home := Vector3(-5, 0, -20)
	var path := []
	for k in 9:
		var q := home.lerp(beast, k / 8.0)
		path.append({"x": q.x, "z": q.z})
	var start := 900000.0
	var arrive := start + 14000.0
	var army := {"id": "army-bank", "status": "fighting", "target": target.id, "path": path, "units": party,
		"startsAt": start, "arrivesAt": arrive, "battleAt": arrive, "battleEndsAt": arrive + 6000.0,
		"battle": {"events": events}, "fallen": [], "owner": state.get("playerId", "")}
	state.armies = [army]
	stage.target = beast
	stage.update_camera(0, true)
	await settle(stage, state, arrive + 2600.0)
	var plan: Dictionary = stage.army_routes["army-bank"].get("engage", {})
	var wet := 0
	var inside := 0
	var units := soldiers(stage, "army-bank")
	for unit: Node3D in units:
		var at := unit.global_position
		if stage.sample_city(at.x, at.z) <= -0.2:
			wet += 1
		if outside_body(at, beast, plan.face, plan.body) <= 0.05:
			inside += 1
	check(units.size() == 24, "River bank: soldiers on the field %d" % units.size())
	check(wet == 0, "River bank: %d soldiers stand in the river" % wet)
	check(inside == 0, "River bank: %d soldiers inside the creature" % inside)
	print("QA_HUNT river_x=", snappedf(x, 0.01), " wet=", wet)

func finish() -> void:
	print("QA_HUNT checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
