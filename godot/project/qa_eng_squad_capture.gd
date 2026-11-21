extends SceneTree
# DRENOVAR ENG squad · stage capture tool (QA only, excluded from export by "qa_*").
#
# Runs the REAL res://src/landscape.gd (world or city) with a synthetic server state,
# advances server time with a fixed step, saves frames from the game camera and writes
# per-frame telemetry (bones, clips, phases, arrows, events). Game scripts are not modified:
# the tool only builds state dictionaries and calls the same per-frame functions that
# main.gd::_process calls (update_camera, present_armies, present_creatures, parade, workers).
#
# Typical run (fixed engine step = capture step, real Mobile renderer through lavapipe):
#   . godot/art-source/eng-squad/pipeline/env.sh
#   godot_render 1366x630 --fixed-fps 30 -s qa_eng_squad_capture.gd -- \
#       --map=world --units=ENG-01:2,ENG-02:2,ENG-03:2,ENG-04:2,ENG-06:1 \
#       --scenario=battle --camera=battle --fps=30 --seconds=6 --out=$WORK/cap/battle
#
# Options (after "--"):
#   --map=world|city            scene (world: perspective camera, city: orthographic)
#   --units=ID:N,ID:N           army composition (order kept, as the server bag)
#   --scenario=march|battle|idle|parade|armory
#   --camera=battle|close|orbit|<zoom>   battle = world 68 / city 70, close = world 15 / city 24
#                               (world + --follow=center: camera distance to the group = this value)
#   --orbit=dist,yaw,pitch      orbit camera (not a game camera) around --focus, yaw relative to march heading
#   --focus=ENG-02_0            follow one member instead of the army centre
#   --follow=center|game|none   center: camera on the formation centroid, world target panned so the
#                               group stays centred at the requested distance (default);
#                               game: exactly main.gd follow (x/z of the army, camera aims at y = 1)
#   --fps=30 --seconds=6        capture rate and length (server time step = 1000/fps ms)
#   --speed=1.2                 march speed along the route, m/s (route length / (arrivesAt-startsAt))
#   --turn=60                   heading change in the middle of the route, degrees (battle default 0)
#   --slope=0|1                 flat or sloped route found on the real height field
#   --at=x,z --heading=deg      explicit route anchor (overrides automatic search)
#   --yaw=deg                   world camera yaw (game rotates in 45 degree steps)
#   --out=DIR                   output directory (frames/, telemetry.json)
#   --models=FILE.json|{...}    {"ENG-01":{"field":"res://...","preview":"res://...","drill":"..."}}
#                               non-res:// GLB paths are loaded with runtime GLTFDocument (no import LODs!)
#   --every=1 --format=png|jpg  frame decimation and image format; --frames=0 telemetry only
#   --poll=800 --latency=120    emulate client polling of /state (0 = state always current)
#   --reveal=all|progressive    battle events visible at once, or only when at <= polled server time
#   --interval=2000 | ENG-04:3000,ENG-03:2200   soldier attack spacing per member, ms
#   --grid=200                  server step for event times, ms
#   --deaths=0                  members killed by creature hits (hp = 0 events)
#   --approach=2.5              battle: seconds of march before arrival inside the capture
#   --level=1                   creature level (world: velkor, city: tenerys)
#   --warmup=1.0                seconds simulated before the first saved frame
#   --phases=0,0.25,0.5,0.75    armory: clip phases to capture

const Landscape = preload("res://src/landscape.gd")
const Formations = preload("res://src/formations.gd")

const HUMAN_BONES := ["Hips", "Spine", "Chest", "Neck", "Head", "RightUpperArm", "RightForearm", "RightHand",
	"LeftUpperArm", "LeftForearm", "LeftHand", "RightThigh", "RightShin", "RightFoot", "RightToe",
	"LeftThigh", "LeftShin", "LeftFoot", "LeftToe"]
const HORSE_BONES := ["HorseRoot", "HorseBack", "HorseNeck", "HorseHead", "HorseEarR", "HorseEarL",
	"FrontRScapula", "FrontRUpper", "FrontRKnee", "FrontRHoof", "FrontLScapula", "FrontLUpper", "FrontLKnee", "FrontLHoof",
	"HindLHip", "HindLStifle", "HindLHock", "HindLHoof", "HindRHip", "HindRStifle", "HindRHock", "HindRHoof", "TailBase", "TailMid"]
const TRACKED := ["Hips", "Head", "Chest", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftToe", "RightToe",
	"HorseRoot", "HorseBack", "HorseHead", "FrontLHoof", "FrontRHoof", "HindLHoof", "HindRHoof"]

var opt := {
	"map": "world", "units": "ENG-01:4", "scenario": "march", "camera": "battle", "orbit": "6,90,12", "focus": "",
	"fps": "30", "seconds": "6", "speed": "1.2", "turn": "", "slope": "0", "at": "", "heading": "", "yaw": "0",
	"out": "", "models": "", "every": "1", "format": "png", "frames": "1", "poll": "800", "latency": "120",
	"reveal": "all", "interval": "2000", "grid": "200", "deaths": "0", "approach": "2.5", "level": "1",
	"warmup": "1.0", "phases": "0,0.25,0.5,0.75", "follow": "center", "telemetry": "1"
}
var data: Dictionary
var stage: Landscape
var client_state: Dictionary
var server := {}           # synthetic server timeline
var out_dir := ""
var fps := 30.0
var step_ms := 33.333
var last_delta := -1.0
var manual_animation := false
var orbit_camera: Camera3D
var telemetry_rows: Array = []
var header := {}
var warnings: PackedStringArray = []
var next_poll := 0.0
var poll_count := 0
var last_poll_server := -INF
var training_next := 0.0

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			var key := arg.substr(2, arg.find("=") - 2)
			opt[key] = arg.substr(arg.find("=") + 1)
	call_deferred("run")

func _process(delta: float) -> bool:
	last_delta = delta
	return false

func fail(message: String) -> void:
	push_error("ENG_CAPTURE: " + message)
	printerr("ENG_CAPTURE_FAILED ", message)
	quit(1)

# ---------------------------------------------------------------- setup helpers

func parse_units(text: String) -> Dictionary:
	var bag := {}
	for part in text.split(",", false):
		var bits := part.strip_edges().split(":")
		bag[bits[0]] = int(bits[1]) if bits.size() > 1 else 1
	return bag

func parse_floats(text: String) -> PackedFloat64Array:
	var values := PackedFloat64Array()
	for part in text.split(",", false):
		values.append(float(part))
	return values

func load_data() -> bool:
	data = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	if data.is_empty():
		fail("res://assets/game.json not readable")
		return false
	header.models = {}
	var override: Dictionary = {}
	var text: String = opt.models
	if not text.is_empty():
		if not text.begins_with("{"):
			text = FileAccess.get_file_as_string(text)
		var parsed: Variant = JSON.parse_string(text)
		if not parsed is Dictionary:
			fail("--models is not a JSON object")
			return false
		override = parsed
	for id in override:
		if not data.unitModels.has(id):
			data.unitModels[id] = {"preview": "", "field": "", "drill": "Idle"}
		for key in ["preview", "field", "drill"]:
			if (override[id] as Dictionary).has(key):
				data.unitModels[id][key] = override[id][key]
	for id in parse_units(opt.units):
		if not data.unitModels.has(id):
			fail("unknown unit id " + id)
			return false
		header.models[id] = data.unitModels[id].duplicate()
	return true

func runtime_scene(path: String) -> PackedScene:
	# Non-imported GLB: runtime glTF import (no Godot mesh LODs, no .import settings).
	var document := GLTFDocument.new()
	var gltf := GLTFState.new()
	if document.append_from_file(path, gltf) != OK:
		return null
	var node := document.generate_scene(gltf)
	var packed := PackedScene.new()
	packed.pack(node)
	node.free()
	warnings.append("runtime glTF import for " + path + " (no import LODs / settings)")
	return packed

func register_runtime_models() -> void:
	for id in header.models:
		for role in ["field", "preview"]:
			var path: String = data.unitModels[id][role]
			if not path.begins_with("res://") and not path.is_empty():
				var packed := runtime_scene(path)
				if packed == null:
					fail("cannot load " + path)
					return
				stage.models[path] = packed

func ground(p: Vector3) -> Vector3:
	return stage.ground_point(p)

func height_at(x: float, z: float) -> float:
	return stage.ground_point(Vector3(x, 0, z)).y

func route_points(anchor: Vector2, heading: float, first: float, second: float, turn: float) -> Array:
	var a := anchor
	var dir1 := Vector2(sin(heading), cos(heading))
	var b := a + dir1 * first
	var dir2 := Vector2(sin(heading + turn), cos(heading + turn))
	var c := b + dir2 * second
	var points: Array = []
	for i in range(0, 9):
		var p := a.lerp(b, i / 8.0)
		points.append(p)
	for i in range(1, 9):
		points.append(b.lerp(c, i / 8.0))
	return points

func route_metrics(points: Array) -> Dictionary:
	var ys := PackedFloat64Array()
	var slopes := PackedFloat64Array()
	var length := 0.0
	for i in range(points.size()):
		var p: Vector2 = points[i]
		ys.append(height_at(p.x, p.y))
		if i > 0:
			var q: Vector2 = points[i - 1]
			var d := p.distance_to(q)
			length += d
			if d > 0.0:
				slopes.append((ys[i] - ys[i - 1]) / d)
	var mean_abs := 0.0
	var mean := 0.0
	var max_abs := 0.0
	for s in slopes:
		mean_abs += absf(s)
		mean += s
		max_abs = maxf(max_abs, absf(s))
	mean_abs /= maxf(1, slopes.size())
	mean /= maxf(1, slopes.size())
	var low := INF
	for y in ys:
		low = minf(low, y)
	return {"length": length, "min_y": low, "slope_mean": mean, "slope_abs_mean": mean_abs, "slope_max": max_abs}

func obstacle_points() -> Array:
	var points: Array = []
	if stage.map_name == "world":
		for o in data.environment:
			var spec: Dictionary = data.environmentModels.get(o.id, {})
			if spec.get("tree", false) or not spec.get("detail", true):
				points.append(Vector2(float(o.x), float(o.z)))
		for site in data.sites:
			points.append(Vector2(float(site.x), float(site.z)))
	else:
		for tree in data.woods:
			points.append(Vector2(float(tree.p[0]), float(tree.p[2])))
		for marker in stage.place_markers:
			points.append(Vector2(marker.position.x, marker.position.z))
	return points

func obstacle_grid(points: Array) -> Dictionary:
	var grid := {}
	for o: Vector2 in points:
		var cell := Vector2i(floori(o.x / 4.0), floori(o.y / 4.0))
		if not grid.has(cell):
			grid[cell] = []
		grid[cell].append(o)
	return grid

func clutter(points: Array, grid: Dictionary, radius: float) -> int:
	# number of obstacles closer than radius to the route polyline samples
	var seen := {}
	var r2 := radius * radius
	for p: Vector2 in points:
		var cell := Vector2i(floori(p.x / 4.0), floori(p.y / 4.0))
		for dz in range(-1, 2):
			for dx in range(-1, 2):
				for o: Vector2 in grid.get(cell + Vector2i(dx, dz), []):
					if p.distance_squared_to(o) < r2:
						seen[o] = true
	return seen.size()

func dense(points: Array) -> Array:
	var out: Array = []
	for i in range(1, points.size()):
		var a: Vector2 = points[i - 1]
		var b: Vector2 = points[i]
		var n := maxi(1, ceili(a.distance_to(b) / 1.0))
		for k in range(n):
			out.append(a.lerp(b, float(k) / n))
	out.append(points.back())
	return out

func cross_slope(points: Array) -> float:
	# height difference across a 6 m wide formation band, per metre
	var worst := 0.0
	for i in range(1, points.size()):
		var a: Vector2 = points[i - 1]
		var b: Vector2 = points[i]
		var dir := (b - a).normalized()
		var side := Vector2(-dir.y, dir.x) * 3.0
		worst = maxf(worst, absf(height_at(a.x + side.x, a.y + side.y) - height_at(a.x - side.x, a.y - side.y)) / 6.0)
	return worst

func choose_route(first: float, second: float, turn: float) -> Dictionary:
	if not str(opt.at).is_empty():
		var at := parse_floats(opt.at)
		var heading := deg_to_rad(float(opt.heading)) if not str(opt.heading).is_empty() else 0.0
		var pts := route_points(Vector2(at[0], at[1]), heading, first, second, turn)
		var em := route_metrics(pts)
		em.cross_slope = cross_slope(pts)
		return {"points": pts, "anchor": [at[0], at[1]], "heading": heading, "metrics": em, "search": "explicit"}
	var sloped := int(opt.slope) != 0
	var world := stage.map_name == "world"
	var obstacles := obstacle_grid(obstacle_points())
	var towns: Array = []
	if world:
		for site in data.sites:
			towns.append(Vector2(float(site.x), float(site.z)))
	var limit_x := 145.0 if world else 125.0
	var limit_z := 115.0 if world else 125.0
	var min_height := 1.8 if world else 0.2
	# candidates (anchor grid 6 m, 8 headings), metrics on the centre line
	var candidates: Array = []
	var x := -limit_x + 5.0
	while x <= limit_x - 5.0:
		var z := -limit_z + 5.0
		while z <= limit_z - 5.0:
			for k in range(8):
				var heading := k * PI / 4.0
				if not str(opt.heading).is_empty() and absf(angle_difference(heading, deg_to_rad(float(opt.heading)))) > 0.01:
					continue
				var pts := route_points(Vector2(x, z), heading, first, second, turn)
				var inside := true
				for p: Vector2 in pts:
					if absf(p.x) > limit_x or absf(p.y) > limit_z:
						inside = false
						break
				if not inside:
					continue
				var m := route_metrics(pts)
				if m.min_y < min_height:
					continue
				candidates.append({"anchor": Vector2(x, z), "heading": heading, "points": pts, "metrics": m})
			z += 6.0
		x += 6.0
	var tiers: Array = []
	if sloped:
		tiers = [[0.10, 0.30, 0.07, 0.45], [0.07, 0.40, 0.05, 0.6], [0.04, 0.6, 0.03, 0.9]]
	else:
		tiers = [[0.0, 0.06, 0.0, 0.06], [0.0, 0.10, 0.0, 0.10], [0.0, 0.16, 0.0, 0.16], [0.0, 0.3, 0.0, 0.3]]
	for tier in tiers:
		var best := {}
		var best_score := INF
		for c in candidates:
			var m: Dictionary = c.metrics
			var ok := false
			if sloped:
				ok = m.slope_abs_mean >= tier[0] and m.slope_abs_mean <= tier[1] and absf(m.slope_mean) >= tier[2] and m.slope_max <= tier[3]
			else:
				ok = m.slope_max <= tier[1]
			if not ok:
				continue
			var cs := cross_slope(c.points)
			if cs > (0.35 if sloped else tier[1] * 1.5):
				continue
			var dense_pts := dense(c.points)
			var near := clutter(dense_pts, obstacles, 3.2)
			var town_penalty := 0.0
			for t: Vector2 in towns:
				for p: Vector2 in dense_pts:
					if p.distance_to(t) < 28.0:
						town_penalty = 40.0
						break
				if town_penalty > 0.0:
					break
			# world camera looks at y = 1 (landscape.gd::apply_camera_pose): prefer low ground so the
			# followed army stays near the screen centre, as on most of the playable map
			var height_penalty := maxf(0.0, float(m.min_y) - 2.5) * 3.0 if world else 0.0
			var score := float(near) * 10.0 + town_penalty + height_penalty + (c.anchor as Vector2).length() * 0.01 + cs * 20.0
			score += (-absf(m.slope_mean) * 20.0) if sloped else m.slope_max * 50.0
			if score < best_score:
				best_score = score
				m.cross_slope = cs
				best = {"points": c.points, "anchor": [c.anchor.x, c.anchor.y], "heading": c.heading, "metrics": m, "clutter": near,
					"town_penalty": town_penalty, "search": "auto tier " + str(tiers.find(tier))}
		if not best.is_empty():
			return best
	warnings.append("no route matched the slope filters; using map centre")
	var pts := route_points(Vector2.ZERO, 0.0, first, second, turn)
	return {"points": pts, "anchor": [0, 0], "heading": 0.0, "metrics": route_metrics(pts), "search": "fallback"}

func creature_for(position: Vector2, level: int) -> Dictionary:
	var world := stage.map_name == "world"
	var demo: Dictionary = data.demo
	var source: Dictionary = (demo.world.encounters[0] if world else demo.encounters[0]).duplicate(true)
	source.id = "qa-creature"
	source.level = level
	source.position = {"x": position.x, "z": position.y}
	source.patrol = []
	source.status = "fighting"
	source.hp = int(source.spec.get("hp", 1000))
	if not world:
		source.behavior = "idle"
		source.species = source.get("species", "tenerys")
	else:
		source.species = "velkor"
	return source

func build_events(slots: Array, battle_ms: float, creature: Dictionary) -> Array:
	var events: Array = []
	var grid := maxf(1.0, float(opt.grid))
	var per_type := {}
	var default_interval := 2000.0
	for part in str(opt.interval).split(",", false):
		if ":" in part:
			var bits := part.split(":")
			per_type[bits[0]] = float(bits[1])
		else:
			default_interval = float(part)
	for i in range(slots.size()):
		var slot: Dictionary = slots[i]
		var interval: float = per_type.get(slot.id, default_interval)
		var at := 600.0 + fmod(i * 230.0, interval)
		at = ceilf(at / grid) * grid
		while at < battle_ms - 300.0:
			events.append([at, "soldier_attack", slot.id, int(slot.index), null])
			at += interval
	var cooldown := float(creature.spec.get("cooldown", 2.0)) * 1000.0
	var kind: String = creature.spec.get("ability", "claw")
	var deaths := int(opt.deaths)
	var hits := {}
	var at_c := 1400.0
	var k := 0
	var dead := {}
	while at_c < battle_ms - 300.0 and not slots.is_empty():
		var slot: Dictionary = slots[k % slots.size()]
		var key := "%s:%d" % [slot.id, int(slot.index)]
		k += 1
		if dead.has(key):
			at_c += cooldown
			continue
		hits[key] = int(hits.get(key, 0)) + 1
		var hp := 60
		if dead.size() < deaths and k <= deaths:
			hp = 0
			dead[key] = true
		events.append([ceilf(at_c / grid) * grid, kind, slot.id, int(slot.index), hp])
		at_c += cooldown
	events.sort_custom(func(a, b): return a[0] < b[0])
	return events

# ---------------------------------------------------------------- server timeline / polling

func server_snapshot(server_ms: float) -> Dictionary:
	var snapshot: Dictionary = server.base.duplicate(true)
	snapshot.serverTime = server_ms
	if server.has("army"):
		var army: Dictionary = server.army.duplicate(true)
		if server.scenario == "battle" and server_ms >= float(army.arrivesAt):
			army.status = "fighting"
			army.battleAt = server.battle_at
			army.battleEndsAt = server.battle_ends
			army.position = server.army_end
			var visible: Array = []
			for event: Array in server.events:
				if opt.reveal == "progressive" and float(server.battle_at) + float(event[0]) > server_ms:
					continue
				visible.append(event)
			army.events = visible
			army.fallen = []
		if stage.map_name == "world":
			snapshot.world.armies = [army]
		else:
			snapshot.armies = [army]
	return snapshot

func advance_client_state(now: float) -> void:
	var poll := float(opt.poll)
	if poll <= 0.0:
		client_state = server_snapshot(now)
		return
	var latency := float(opt.latency)
	var changed := false
	while next_poll + latency <= now:
		client_state = server_snapshot(next_poll)
		last_poll_server = next_poll
		poll_count += 1
		next_poll += poll
		changed = true
	if changed:
		stage.present(client_state)   # main.gd::accept() -> stage.present(state)

# ---------------------------------------------------------------- per-frame drive (mirrors main.gd::_process)

func army_marker() -> Variant:
	for marker in stage.army_markers:
		if marker.id == "qa-eng-squad":
			return marker
	return null

func focus_node() -> Node3D:
	if str(opt.focus).is_empty():
		return null
	var army := stage.actors.get_node_or_null("qa-eng-squad") as Node3D
	if army:
		var unit := army.get_node_or_null(NodePath(str(opt.focus))) as Node3D
		if unit:
			return unit
	return stage.parade.get_node_or_null(NodePath(str(opt.focus))) as Node3D

var view_distance := 68.0   # requested camera distance to the followed group (world, "center" follow)

func view_target(p: Vector3) -> Vector3:
	# The world camera always looks at y = 1 from `zoom` metres away (landscape.gd::apply_camera_pose
	# ignores terrain height), so over high ground the game camera is closer to the soldiers than
	# `zoom`, and at zoom 15 the followed army can leave the frustum. "center" follow pans the target
	# along the view ray and sets zoom = distance + offset, so the group (1 m above ground) is centred
	# at exactly --camera distance: a pose the player reaches by panning and zooming.
	# "game" keeps main.gd behaviour (x/z of the army, zoom unchanged).
	if stage.map_name != "world" or str(opt.follow) == "game":
		return p
	var d := Vector3(0, sin(Landscape.WORLD_CAMERA_TILT), cos(Landscape.WORLD_CAMERA_TILT)).rotated(Vector3.UP, stage.world_yaw)
	var aim := p + Vector3.UP
	var offset := (aim.y - 1.0) / d.y
	stage.zoom = clampf(view_distance + offset, 15.0, 500.0)
	return aim - d * offset

func formation_centre(fallback: Vector3) -> Vector3:
	# centroid of the drawn members (the army marker is the front anchor of the formation)
	var army := stage.actors.get_node_or_null("qa-eng-squad") as Node3D
	if army == null or army.get_child_count() == 0 or not army.visible:
		return fallback
	var sum := Vector3.ZERO
	for unit in army.get_children():
		sum += (unit as Node3D).global_position
	var centre := sum / army.get_child_count()
	return ground(centre)

func following() -> bool:
	return not (str(opt.follow) in ["0", "none", "off"])

func drive(now: float, delta: float) -> void:
	advance_client_state(now)
	stage.update_camera(delta)
	stage.present_armies(client_state, now)
	if following():
		var focus := focus_node()
		if focus:
			stage.target = view_target(focus.global_position)
		elif server.scenario == "parade":
			stage.target = view_target(stage.parade_center)
		else:
			var marker: Variant = army_marker()
			if marker != null:
				var anchor: Vector3 = marker.position - Vector3.UP * 2.6
				if str(opt.follow) != "game":
					anchor = formation_centre(anchor)
				stage.target = view_target(anchor)
	stage.present_creatures(client_state, now, delta)
	if stage.map_name == "city":
		stage.present_parade()
		stage.present_workers(now / 1000.0)
		if now >= training_next:
			stage.present_training(client_state, now)
			training_next = now + 300.0
	if manual_animation:
		for parent in [stage.actors, stage.creatures, stage.parade, stage.training, stage.workers]:
			for player: AnimationPlayer in (parent as Node).find_children("*", "AnimationPlayer", true, false):
				if player.callback_mode_process != AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL:
					player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
				player.advance(delta)
	if orbit_camera:
		update_orbit()

func update_orbit() -> void:
	var params := parse_floats(opt.orbit)
	var dist: float = params[0] if params.size() > 0 else 6.0
	var yaw := deg_to_rad(params[1] if params.size() > 1 else 90.0)
	var pitch := deg_to_rad(params[2] if params.size() > 2 else 12.0)
	var focus := focus_node()
	var center: Vector3
	var heading := 0.0
	var cache: Dictionary = stage.army_routes.get("qa-eng-squad", {})
	heading = float(cache.get("heading", 0.0))
	if focus:
		center = focus.global_position
	elif server.scenario == "parade":
		center = stage.parade_center
	else:
		var marker: Variant = army_marker()
		center = (marker.position - Vector3.UP * 2.6) if marker != null else stage.target
	center += Vector3.UP * 1.0
	var a := heading + yaw
	var offset := Vector3(sin(a) * cos(pitch), sin(pitch), cos(a) * cos(pitch)) * dist
	orbit_camera.position = center + offset
	orbit_camera.look_at(center, Vector3.UP)
	orbit_camera.make_current()

# ---------------------------------------------------------------- telemetry

func v3(v: Vector3) -> Array:
	return [snappedf(v.x, 0.0001), snappedf(v.y, 0.0001), snappedf(v.z, 0.0001)]

func q4(b: Basis) -> Array:
	var q := b.orthonormalized().get_rotation_quaternion()
	return [snappedf(q.x, 0.0001), snappedf(q.y, 0.0001), snappedf(q.z, 0.0001), snappedf(q.w, 0.0001)]

func active_camera() -> Camera3D:
	return orbit_camera if orbit_camera else stage.camera

func screen(p: Vector3) -> Variant:
	var cam := active_camera()
	if cam.is_position_behind(p):
		return null
	var s := cam.unproject_position(p)
	return [snappedf(s.x, 0.01), snappedf(s.y, 0.01)]

func player_record(model: Node3D) -> Dictionary:
	var players := model.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		return {}
	var player := players[0] as AnimationPlayer
	var name := String(player.assigned_animation)
	var rec := {"animation": name, "playing": player.is_playing(), "speed_scale": player.speed_scale}
	if not name.is_empty() and player.has_animation(name):
		var length := player.get_animation(name).length
		var pos := player.current_animation_position   # also valid while paused (scrubbed battle clips)
		rec.position = snappedf(pos, 0.0001)
		rec.length = snappedf(length, 0.0001)
		rec.phase = snappedf(pos / length if length > 0.0 else 0.0, 0.0001)
	return rec

func unit_record(unit: Node3D) -> Dictionary:
	var rec := {"name": String(unit.name), "visible": unit.is_visible_in_tree(), "clip": unit.get_meta("clip", ""),
		"origin": v3(unit.global_position), "yaw": snappedf(unit.global_rotation.y, 0.0001),
		"scale": snappedf(unit.global_transform.basis.get_scale().y, 0.0001)}
	rec.merge(player_record(unit))
	var skeletons := unit.find_children("*", "Skeleton3D", true, false)
	if not skeletons.is_empty():
		var sk := skeletons[0] as Skeleton3D
		var bones := {}
		var items := {}
		for b in sk.get_bone_count():
			var bone_name := sk.get_bone_name(b)
			var standard := bone_name in HUMAN_BONES or bone_name in HORSE_BONES
			if not standard or bone_name in TRACKED:
				var g: Transform3D = sk.global_transform * sk.get_bone_global_pose(b)
				if standard:
					var row := v3(g.origin)
					if bone_name.ends_with("Foot") or bone_name.ends_with("Toe") or bone_name.ends_with("Hoof"):
						row.append(snappedf(ground(g.origin).y, 0.0001))
					bones[bone_name] = row
				else:
					items[bone_name] = {"p": v3(g.origin), "q": q4(g.basis)}
		rec.bones = bones
		if not items.is_empty():
			rec.item_bones = items
		var head := sk.find_bone("Head")
		if head >= 0:
			var top: Vector3 = (sk.global_transform * sk.get_bone_global_pose(head)).origin + Vector3.UP * 0.226 * float(rec.scale)
			rec.screen_head_top = screen(top)
			rec.screen_ground = screen(ground(unit.global_position))
	var attachments := {}
	for attachment: BoneAttachment3D in unit.find_children("*", "BoneAttachment3D", true, false):
		attachments[String(attachment.name)] = {"bone": attachment.bone_name, "p": v3(attachment.global_position), "q": q4(attachment.global_basis)}
	if not attachments.is_empty():
		rec.attachments = attachments
	var arrow := unit.get_node_or_null("Arrow") as MeshInstance3D
	if arrow:
		var axis := arrow.global_basis.y
		var length := axis.length()
		var dir := axis.normalized() if length > 0.0 else Vector3.UP
		rec.arrow = {"visible": arrow.visible, "center": v3(arrow.global_position), "dir": v3(dir), "length": snappedf(length, 0.0001),
			"tip": v3(arrow.global_position + dir * length * 0.5), "tail": v3(arrow.global_position - dir * length * 0.5)}
	return rec

func frame_record(index: int, now: float) -> Dictionary:
	var cam := active_camera()
	var row := {"frame": index, "server_ms": snappedf(now, 0.01), "t": snappedf((now - float(server.capture_start)) / 1000.0, 0.0001),
		"camera": {"position": v3(cam.global_position), "forward": v3(-cam.global_basis.z), "projection": cam.projection,
			"fov": cam.fov, "size": cam.size, "zoom": stage.camera_zoom, "target": v3(stage.camera_target), "game_camera": orbit_camera == null}}
	if server.has("battle_at"):
		row.battle_elapsed_ms = snappedf(now - float(server.battle_at), 0.01)
	if client_state.has("world") or client_state.has("armies"):
		var armies: Array = client_state.world.armies if stage.map_name == "world" else client_state.get("armies", [])
		if not armies.is_empty():
			row.client_status = armies[0].status
			row.client_events = (armies[0].get("events", []) as Array).size()
	if last_poll_server > -INF:
		row.poll_server_ms = last_poll_server
	var marker: Variant = army_marker()
	if marker != null:
		row.army = {"position": v3(marker.position - Vector3.UP * 2.6), "heading": snappedf(float(stage.army_routes.get("qa-eng-squad", {}).get("heading", 0.0)), 0.0001)}
	var units: Array = []
	var army := stage.actors.get_node_or_null("qa-eng-squad") as Node3D
	if army:
		for unit in army.get_children():
			units.append(unit_record(unit as Node3D))
	if server.scenario == "parade":
		for unit in stage.parade.get_children():
			if String(unit.name).begins_with("rank"):
				units.append(unit_record(unit as Node3D))
	row.units = units
	var creatures: Array = []
	for creature in stage.creatures.get_children():
		var c := {"name": String(creature.name), "visible": (creature as Node3D).is_visible_in_tree(), "clip": creature.get_meta("clip", ""),
			"origin": v3((creature as Node3D).global_position), "yaw": snappedf((creature as Node3D).global_rotation.y, 0.0001)}
		c.merge(player_record(creature as Node3D))
		creatures.append(c)
	row.creatures = creatures
	return row

# ---------------------------------------------------------------- capture loop

func save_frame(index: int) -> void:
	if not wants_image(index):
		return
	var image := get_root().get_texture().get_image()
	var path := out_dir.path_join("frames/f_%05d.%s" % [index, "jpg" if opt.format == "jpg" else "png"])
	if opt.format == "jpg":
		image.save_jpg(path, 0.92)
	else:
		image.save_png(path)

func wants_image(index: int) -> bool:
	return int(opt.frames) != 0 and index % maxi(1, int(opt.every)) == 0 and DisplayServer.get_name() != "headless"

func set_render(enabled: bool) -> void:
	# Frames that are not saved are simulated but not drawn (lavapipe draws ~3 s per world frame).
	if DisplayServer.get_name() != "headless":
		RenderingServer.render_loop_enabled = enabled or int(opt.get("render_all", "0")) != 0

func write_json(path: String, value: Variant) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()

func run() -> void:
	fps = maxf(1.0, float(opt.fps))
	step_ms = 1000.0 / fps
	out_dir = str(opt.out)
	if out_dir.is_empty():
		out_dir = ProjectSettings.globalize_path("user://eng-squad-capture")
	DirAccess.make_dir_recursive_absolute(out_dir.path_join("frames"))
	if not load_data():
		return
	header.engine = Engine.get_version_info().string
	header.renderer = RenderingServer.get_current_rendering_method()
	header.adapter = RenderingServer.get_video_adapter_name()
	header.viewport = [get_root().get_visible_rect().size.x, get_root().get_visible_rect().size.y]
	header.options = opt.duplicate()
	if opt.scenario == "armory":
		await run_armory()
		return
	await run_field()

func run_field() -> void:
	var map: String = opt.map
	var scenario: String = opt.scenario
	var units := parse_units(opt.units)
	var t0 := 1794370000000.0 + 600000.0
	var base: Dictionary = data.demo.duplicate(true)
	base.serverTime = t0
	base.world.armies = []
	base.armies = []
	base.encounters = []
	base.world.encounters = []
	if scenario == "parade":
		base.city.military.owned = units.duplicate()
		base.city.military.garrison = null
		map = "city"
	else:
		base.city.military.owned = {}   # no demo garrison parade in field captures
	stage = Landscape.new()
	stage.set_active(false)
	get_root().add_child(stage)
	var setup_started := Time.get_ticks_msec()
	await stage.setup(data, base, map, {})
	print("ENG_CAPTURE setup ", map, " ", Time.get_ticks_msec() - setup_started, " ms")
	register_runtime_models()
	stage.set_active(true)
	var speed := maxf(0.05, float(opt.speed))
	var seconds := maxf(0.1, float(opt.seconds))
	var warm := maxf(0.0, float(opt.warmup))
	var approach := clampf(float(opt.approach), 0.0, seconds)
	var turn_deg := float(opt.turn) if not str(opt.turn).is_empty() else (60.0 if scenario == "march" else 0.0)
	var turn := deg_to_rad(turn_deg)
	var first := 0.0
	var second := 0.0
	var capture_start := t0 + 3000.0
	match scenario:
		"march":
			first = speed * (warm + 3.0 + seconds * 0.5)
			second = speed * (seconds * 0.5 + 3.0)
		"battle":
			first = speed * (warm + approach + 3.0) * 0.5
			second = speed * (warm + approach + 3.0) * 0.5
		_:
			first = 6.0
			second = 6.0
	var search_started := Time.get_ticks_msec()
	var route := choose_route(first, second, turn)
	print("ENG_CAPTURE route ", route.search, " anchor=", route.anchor, " heading=", snappedf(rad_to_deg(float(route.heading)), 0.1),
		" slope_mean=", snappedf(float(route.metrics.slope_mean), 0.001), " clutter=", route.get("clutter", -1), " (", Time.get_ticks_msec() - search_started, " ms)")
	var path: Array = []
	for p: Vector2 in route.points:
		path.append({"x": snappedf(p.x, 0.001), "z": snappedf(p.y, 0.001)})
	var route_length := float(route.metrics.length)
	var travel_ms := route_length / speed * 1000.0
	var starts_at := t0
	var arrives_at := t0 + travel_ms
	match scenario:
		"march":
			capture_start = t0 + (warm + 3.0) * 1000.0
		"battle":
			capture_start = arrives_at - approach * 1000.0
		"idle":
			arrives_at = t0 + 1000.0
			capture_start = t0 + 6000.0
		"parade":
			capture_start = t0 + 2000.0
	server = {"scenario": scenario, "base": base, "capture_start": capture_start}
	var end_point: Vector2 = route.points.back()
	var slots := Formations.field_slots(units, data.englishRoster)
	if scenario != "parade":
		var army := {"id": "qa-eng-squad", "owner": base.playerId, "status": "outbound", "units": units, "path": path,
			"startsAt": starts_at, "arrivesAt": arrives_at, "events": [], "fallen": []}
		if map == "world":
			army.worldKind = "velkor"
		server.army = army
		server.army_end = {"x": end_point.x, "z": end_point.y}
	if scenario == "battle":
		var creature := creature_for(end_point, int(opt.level))
		server.army.target = creature.id
		if map == "world":
			server.base.world.encounters = [creature]
		else:
			server.base.encounters = [creature]
		server.battle_at = arrives_at
		var battle_ms := (capture_start + seconds * 1000.0) - arrives_at + 2000.0
		server.battle_ends = arrives_at + battle_ms
		server.events = build_events(slots, battle_ms, creature)
	# camera
	var zoom := 68.0 if map == "world" else 70.0
	match str(opt.camera):
		"battle":
			zoom = 68.0 if map == "world" else 70.0
		"close", "orbit":
			zoom = 15.0 if map == "world" else 24.0
		_:
			zoom = float(opt.camera)
	if zoom <= 0.0:
		fail("--camera must be battle, close, orbit or a positive zoom")
		return
	stage.zoom = zoom
	view_distance = zoom
	stage.world_yaw = deg_to_rad(float(opt.yaw)) if map == "world" else 0.0
	var start_p := ground(Vector3(path[0].x, 0, path[0].z))
	stage.target = view_target(start_p if scenario != "parade" else stage.parade_center)
	if scenario == "battle" or scenario == "idle":
		stage.target = view_target(ground(Vector3(end_point.x, 0, end_point.y)))
	stage.update_camera(0.0, true)
	if str(opt.camera) == "orbit":
		orbit_camera = Camera3D.new()
		orbit_camera.fov = 35.0
		orbit_camera.near = 0.1
		orbit_camera.far = 400.0
		stage.add_child(orbit_camera)
	# header
	var route_world: Array = []
	for p in path:
		route_world.append(v3(ground(Vector3(p.x, 0, p.z))))
	header.map = map
	header.scenario = scenario
	header.units = units
	header.slots = slots
	header.route = {"points": route_world, "length": snappedf(route_length, 0.001), "speed": speed, "turn_deg": turn_deg,
		"anchor": route.anchor, "heading_deg": snappedf(rad_to_deg(float(route.heading)), 0.01), "metrics": route.metrics,
		"search": route.search, "clutter_3m": route.get("clutter", -1)}
	header.time = {"t0": t0, "startsAt": starts_at, "arrivesAt": arrives_at, "capture_start": capture_start, "fps": fps, "step_ms": step_ms,
		"seconds": seconds, "warmup": warm, "poll_ms": float(opt.poll), "latency_ms": float(opt.latency), "reveal": opt.reveal}
	if server.has("battle_at"):
		header.time.battleAt = server.battle_at
		header.time.battleEndsAt = server.battle_ends
		header.events = server.events
		header.event_format = "[at_ms_after_battleAt, kind, unitId, index, hp]"
	header.camera = {"zoom": zoom, "yaw_deg": float(opt.yaw), "mode": opt.camera, "follow": opt.follow, "focus": opt.focus}
	header.controller = {"scale": 1.15, "attack_window_ms": [-490, 510], "hit_ms": 400, "death_ms": 700, "arrow_ms": [-260, 0], "crossfade_s": 0.16}
	# clip tables of every model used
	var clips := {}
	for id in units:
		var packed: PackedScene = stage.scene_resource(data.unitModels[id].field)
		var probe := packed.instantiate()
		for player: AnimationPlayer in probe.find_children("*", "AnimationPlayer", true, false):
			var table := {}
			for clip in player.get_animation_list():
				table[clip] = snappedf(player.get_animation(clip).length, 0.0001)
			clips[id] = table
		var sk_list := probe.find_children("*", "Skeleton3D", true, false)
		if not sk_list.is_empty():
			var sk := sk_list[0] as Skeleton3D
			var rest := {}
			for b in sk.get_bone_count():
				rest[sk.get_bone_name(b)] = v3(sk.get_bone_global_rest(b).origin)
			header["rest_" + id] = rest
		probe.free()
	header.clips = clips
	# poll schedule: first poll aligned with the simulation start
	var sim_start := capture_start - warm * 1000.0
	next_poll = sim_start - float(opt.poll)
	client_state = server_snapshot(sim_start - float(opt.poll) - float(opt.latency))
	stage.present(client_state)
	# warm-up (actors are created at most 6 per frame, camera settles, loops start); not drawn
	var now := sim_start
	var warm_frames := int(round(warm * fps))
	var dt := 1.0 / fps
	set_render(int(opt.get("render_warmup", "0")) != 0)
	for i in range(warm_frames):
		await process_frame
		if i == 3 and absf(last_delta - dt) > 0.0002:
			manual_animation = true
			warnings.append("engine delta %.5f differs from 1/fps; animation advanced manually (run with --fixed-fps %d)" % [last_delta, int(fps)])
		drive(now, dt)
		now += step_ms
	header.animation_advance = "manual" if manual_animation else "engine fixed-fps"
	print("ENG_CAPTURE warm-up done t=", Time.get_ticks_msec(), " ms")
	# capture: drive -> (draw) -> image; telemetry of frame k is read at the start of frame k+1,
	# i.e. after the engine advanced the AnimationPlayers of frame k (the pose that was drawn).
	var total := int(round(seconds * fps))
	var pending := -1
	var pending_now := 0.0
	for k in range(total):
		await process_frame
		if pending >= 0 and int(opt.telemetry) != 0:
			telemetry_rows.append(frame_record(pending, pending_now))
		if warm_frames < 4 and k == 3 and absf(last_delta - dt) > 0.0002:
			manual_animation = true
			warnings.append("engine delta differs from 1/fps; animation advanced manually")
		var draw := wants_image(k)
		set_render(draw)
		drive(now, dt)
		if draw:
			await RenderingServer.frame_post_draw
			save_frame(k)
		pending = k
		pending_now = now
		if k % 30 == 0:
			print("ENG_CAPTURE frame ", k, "/", total, " t=", Time.get_ticks_msec(), " ms")
		now += step_ms
	await process_frame
	if pending >= 0 and int(opt.telemetry) != 0:
		telemetry_rows.append(frame_record(pending, pending_now))
	set_render(true)
	header.warnings = warnings
	header.polls = poll_count
	write_json(out_dir.path_join("telemetry.json"), {"header": header, "frames": telemetry_rows})
	print("ENG_CAPTURE_OK frames=", total, " out=", out_dir, " route=", snappedf(route_length, 0.01), "m speed=", speed,
		" slope_mean=", snappedf(float(route.metrics.slope_mean), 0.001), " warnings=", warnings.size())
	quit(0)

# ---------------------------------------------------------------- armory (real main.gd preview)

func run_armory() -> void:
	if FileAccess.file_exists("user://drenovar-session.bin"):
		fail("a saved native session exists in user://; armory capture refuses to start the online client")
		return
	var game: Node = load("res://main.tscn").instantiate()
	get_root().add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	for i in range(30):
		await process_frame
	for id in header.models:
		for key in ["preview", "field", "drill"]:
			game.data.unitModels[id][key] = data.unitModels[id][key]
	var phases := parse_floats(opt.phases)
	var results := {}
	for id in parse_units(opt.units):
		var unit: Dictionary = game.unit_for_id(id)
		if unit.is_empty():
			warnings.append("no roster entry for " + id)
			continue
		var type: String = {"INF-01": "MIL-01", "RNG-01": "MIL-02", "CAV-01": "MIL-03"}.get(unit.training_building, "MIL-01")
		game.show_recruitment({"id": "qa-" + type, "type": type, "level": 5, "plotId": ""}, unit, true)
		var view := game.modal_body.find_child("RecruitPreview", true, false) as SubViewportContainer
		var deadline := Time.get_ticks_msec() + 30000
		while (view == null or view.get_child_count() == 0 or view.get_parent().get_node("PreviewFallback").visible) and Time.get_ticks_msec() < deadline:
			await process_frame
		if view == null or view.get_child_count() == 0:
			warnings.append("preview did not load for " + id)
			game.close_modal()
			continue
		var viewport := view.get_child(0) as SubViewport
		var players := viewport.find_children("*", "AnimationPlayer", true, false)
		var player: AnimationPlayer = players[0] if not players.is_empty() else null
		var camera := viewport.get_camera_3d()
		var info := {"clip": String(player.assigned_animation) if player else "", "viewport": [viewport.size.x, viewport.size.y],
			"container_rect": [view.get_global_rect().position.x, view.get_global_rect().position.y, view.get_global_rect().size.x, view.get_global_rect().size.y],
			"camera": {"position": v3(camera.global_position), "fov": camera.fov} if camera else {}, "frames": []}
		for phase in phases:
			if player and not String(player.assigned_animation).is_empty():
				var length := player.get_animation(player.assigned_animation).length
				player.pause()
				player.seek(clampf(phase, 0.0, 0.999) * length, true)
			for i in range(3):
				await process_frame
			if DisplayServer.get_name() != "headless":
				await RenderingServer.frame_post_draw
			var tag := "%s_p%03d" % [id, int(round(phase * 100))]
			get_root().get_texture().get_image().save_png(out_dir.path_join("frames/armory_%s.png" % tag))
			viewport.get_texture().get_image().save_png(out_dir.path_join("frames/armory_%s_view.png" % tag))
			info.frames.append({"phase": phase, "file": "frames/armory_%s.png" % tag})
		results[id] = info
		game.close_modal()
		for i in range(5):
			await process_frame
	header.armory = results
	header.warnings = warnings
	write_json(out_dir.path_join("telemetry.json"), {"header": header, "frames": []})
	print("ENG_CAPTURE_OK armory units=", results.size(), " out=", out_dir, " warnings=", warnings.size())
	quit(0)
