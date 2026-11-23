extends SceneTree

# Townsfolk (build 1024, src/townsfolk.gd): the people walking the town at hall I, III and V,
# 120 simulated seconds each (30 Hz), offline (the built-in demo city, grown for III and V).
# Independent checks (not the walker's own tests):
#   - distance to every standing tree trunk (both forests) >= 0.9 m;
#   - building geometry: a body capsule (r 0.2 m, 0.3..1.7 m above the feet) against trimesh
#     collision of every building mesh of the city (as qa_architecture checks lanes);
#   - never in a building footprint off the streets, never on water, inside the wall, off the
#     troop ground and building sites;
#   - feet on the drawn ground: a ray against the town ground mesh (where its shader draws it)
#     and the terrain meshes, |feet - ground| < 0.05 m;
#   - heading change per frame <= TURN_RATE * dt; corners of the walked line rounded (a turn of
#     more than 0.5 rad between two frames in at most 0.2 % of walking frames); the walk clip's
#     stride speed measured from the
#     planted foot equals STRIDE_SPEED, and ground speed = playback x stride (within 10 %);
#   - no two people closer than 0.6 m for more than MOMENT (1.5 s);
#   - CityWorks walkers (the lumberjack's approach, the site carrier) on the drawn ground and
#     clear of trees and buildings;
#   - update cost per frame (all people on screen, and the default view).
#   godot --headless --path . -s qa_townsfolk.gd [-- --dump=/abs/dir]
# --dump writes townsfolk_<hall>.json (plan, graph, obstacles, every trail) for
# tools/townsfolk_map.py, the top-down debug image.

const Townsfolk = preload("res://src/townsfolk.gd")
const SECONDS := 120.0
## "A moment": two people may be closer than 0.6 m (passing at a door, one letting the other
## go first) for at most this long.
const MOMENT := 1.5
const DT := 1.0 / 30.0
var checks := 0
var failures := 0
var game: Node
var stage: Node3D
var tf: Node3D
var dump_dir := ""
var solids: StaticBody3D
var capsule := CapsuleShape3D.new()
var town_mesh: TriangleMesh
var terrain: Array = []
var report: Array = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--dump="):
			dump_dir = arg.trim_prefix("--dump=")
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
		print("FAIL ", description)

func frames(count: int) -> void:
	for i in count:
		await process_frame

func add_building(type: String, plot: String, level: int) -> void:
	var city: Dictionary = game.state.city
	for b in city.buildings:
		if b.plotId == plot:
			b.type = type
			b.level = level
			return
	city.buildings.append({"id": "building-" + plot, "type": type, "plotId": plot, "level": level})
	if not plot in city.kingdom.clearedPlots:
		city.kingdom.clearedPlots.append(plot)

func set_level(type: String, level: int) -> void:
	for b in game.state.city.buildings:
		if b.type == type:
			b.level = level

func town(hall: int) -> void:
	set_level("ECO-05", hall)
	if hall >= 3:
		set_level("RES-01", 2)
		set_level("RES-04", 3)
		add_building("ECO-01", "v1-4", 2)
		add_building("ECO-03", "v1-5", 2)
		add_building("MIL-04", "v1-6", 1)
		add_building("ECO-04", "v1-7", 2)
	if hall >= 5:
		set_level("RES-01", 4)
		set_level("RES-04", 5)
		set_level("ECO-01", 4)
		set_level("ECO-03", 4)
		set_level("MIL-04", 3)
		set_level("ECO-04", 3)
		add_building("RES-02", "v1-15", 3)
		add_building("ALT-08", "v1-14", 3)
		add_building("SUP-05", "v1-12", 2)
		add_building("ECO-04", "v1-8", 4)
		add_building("ECO-02", "v1-13", 3)
		add_building("SUP-01", "v1-9", 2)
	await stage.present_city(game.state)
	await frames(3)
	# The game's frame loop (stage.present_workers) starts the plan; main.gd's loop is off here.
	tf.present(Time.get_unix_time_from_system())
	# The townsfolk plan in the background (a few ms per frame).
	var waited := 0
	while tf.building and waited < 600:
		waited += 1
		await process_frame
	print("plan: %.1f ms over %d frames %s" % [tf.last_build_usec / 1000.0, tf.last_build_frames, str(tf.build_profile)])

func build_solids() -> void:
	if is_instance_valid(solids):
		solids.free()
	solids = StaticBody3D.new()
	var parents: Array = [stage.buildings]
	if stage.walls.visible and is_instance_valid(stage.walls.node):
		parents.append(stage.walls.node)
	var count := 0
	for parent: Node in parents:
		for mesh: MeshInstance3D in parent.find_children("*", "MeshInstance3D", true, false):
			if mesh.mesh == null or not mesh.is_visible_in_tree():
				continue
			var faces: PackedVector3Array = mesh.global_transform * mesh.mesh.get_faces()
			if faces.is_empty():
				continue
			var shape := ConcavePolygonShape3D.new()
			shape.backface_collision = true
			shape.set_faces(faces)
			var holder := CollisionShape3D.new()
			holder.shape = shape
			holder.set_meta("source", str(mesh.get_path()).replace(str(stage.get_path()), ""))
			solids.add_child(holder)
			count += faces.size() / 3
	root.add_child(solids)
	await physics_frame
	await physics_frame
	capsule.radius = 0.2
	capsule.height = 1.4
	report.append("solid triangles %d" % count)

var last_hit := ""

func inside_building(at: Vector3) -> bool:
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.transform = Transform3D(Basis.IDENTITY, at + Vector3.UP * 1.0)
	var hits := solids.get_world_3d().direct_space_state.intersect_shape(query, 1)
	if hits.is_empty():
		return false
	var holder: Node = solids.get_child(int(hits[0].shape)) if int(hits[0].shape) < solids.get_child_count() else null
	last_hit = str(holder.get_meta("source", "")) if holder != null else ""
	return true

func build_ground() -> void:
	town_mesh = stage.town.ground.mesh.generate_triangle_mesh() if is_instance_valid(stage.town.ground) else null
	terrain.clear()
	for mesh: MeshInstance3D in stage.city_ground_meshes:
		if is_instance_valid(mesh) and mesh.mesh != null:
			terrain.append([mesh.mesh.generate_triangle_mesh(), mesh.global_transform, mesh.global_transform * mesh.get_aabb()])

## Coverage of the town ground mask at (x, z), filtered like its shader samples it: the shader
## keeps a fragment where it is >= 0.5 (+-0.25 fray on earth edges).
func mask_cover(x: float, z: float) -> float:
	var mask: Image = stage.town_plan.mask
	if mask == null:
		return 0.0
	var u := (x + 64.0) / 0.25 - 0.5
	var v := (z + 64.0) / 0.25 - 0.5
	var i := floori(u)
	var j := floori(v)
	var fu := u - i
	var fv := v - j
	var c := func(a: int, b: int) -> float:
		if a < 0 or b < 0 or a >= mask.get_width() or b >= mask.get_height():
			return 0.0
		var p := mask.get_pixel(a, b)
		return maxf(p.r, p.g)
	return lerpf(lerpf(c.call(i, j), c.call(i + 1, j), fu), lerpf(c.call(i, j + 1), c.call(i + 1, j + 1), fu), fv)

## The drawn ground under (x, z): the town ground where its shader keeps it, else the terrain
## (the higher one where both are there); NAN on the frayed edge where either may show.
func drawn_ground(x: float, z: float) -> float:
	var best := -INF
	var cover := mask_cover(x, z)
	if cover > 0.25 and cover < 0.75:
		return NAN
	if town_mesh != null and cover >= 0.75:
		var hit: Dictionary = town_mesh.intersect_ray(Vector3(x, 80.0, z), Vector3.DOWN)
		if not hit.is_empty():
			best = hit.position.y
	for tile: Array in terrain:
		var box: AABB = tile[2]
		if x < box.position.x - 0.01 or x > box.end.x + 0.01 or z < box.position.z - 0.01 or z > box.end.z + 0.01:
			continue
		var xf: Transform3D = tile[1]
		var inverse := xf.affine_inverse()
		var hit: Dictionary = (tile[0] as TriangleMesh).intersect_ray(inverse * Vector3(x, 80.0, z), (inverse.basis * Vector3.DOWN).normalized())
		if not hit.is_empty():
			best = maxf(best, (xf * Vector3(hit.position)).y)
	return best

func nearest_trunk(p: Vector2) -> float:
	var best := INF
	var cell := Vector2i(floori(p.x / 4.0), floori(p.y / 4.0))
	for z in range(-2, 3):
		for x in range(-2, 3):
			for tree: Vector2 in stage.standing_tree_cells.get(cell + Vector2i(x, z), []):
				best = minf(best, p.distance_to(tree))
			for tree: Vector2 in tf.extra_trees.get(cell + Vector2i(x, z), []):
				best = minf(best, p.distance_to(tree))
	return best

func in_footprint_off_street(p: Vector2) -> bool:
	for lot: Dictionary in stage.town_plan.lots:
		if (lot.body as Rect2).has_point(p) and not tf.on_street_band(p):
			return true
	return false

## Speed of the planted foot of a clip (m/s at playback 1, scale 1).
func stance_speed(player: AnimationPlayer, skeleton: Skeleton3D, clip: StringName) -> float:
	var animation := player.get_animation(clip)
	player.stop()
	player.play(clip, 0.0)
	player.pause()
	var foot := skeleton.find_bone("LeftFoot")
	var ys := PackedFloat32Array()
	var zs := PackedFloat32Array()
	var steps := 220
	for i in steps + 1:
		player.seek(animation.length * i / steps, true)
		var at := skeleton.get_bone_global_pose(foot).origin
		ys.append(at.y)
		zs.append(at.z)
	var low := INF
	for y in ys:
		low = minf(low, y)
	var travel := 0.0
	var time := 0.0
	for i in range(1, steps + 1):
		if ys[i] < low + 0.002 and ys[i - 1] < low + 0.002:
			travel += zs[i - 1] - zs[i]
			time += animation.length / steps
	player.stop()
	# Bone poses are in skeleton space: the model's scale does not enter.
	return travel / maxf(time, 0.0001)

func wait_ready(seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		tf.present(Time.get_unix_time_from_system())
		if tf.people.all(func(p): return p.ready):
			return true
		await process_frame
	return false

func scenario(hall: int, expected: int) -> void:
	await town(hall)
	var label := "hall %d" % hall
	var people: Array = tf.people
	print("%s: %d people (%s)" % [label, people.size(), ", ".join(people.map(func(p): return p.role))])
	check(people.size() >= expected, "%s: %d people, expected at least %d" % [label, people.size(), expected])
	if tf.dropped_legs > 0:
		print("%s: %d routines left out (a leg with no clear line)" % [label, tf.dropped_legs])
	if tf.crowded > 0:
		print("%s: %d people left out (no free place at a stop)" % [label, tf.crowded])
	for line in tf.left_out:
		print("  left out: ", line)
	tf.dropped_legs = 0
	tf.simulate_all = true
	var loaded: bool = await wait_ready(60.0)
	check(loaded, "%s: models not loaded in 60 s" % label)
	await build_solids()
	build_ground()
	if hall == 1:
		await stride_checks()
	# --- 120 simulated seconds -----------------------------------------------------------
	var start := 1794370000.0 + hall * 1000.0
	var count := people.size()
	var trails: Array = []
	for i in count:
		trails.append([])
	var close_time := {}
	var worst_close := 0.0
	var worst_pair := ""
	var traces := 0
	var close_pairs := 0
	var min_tree := INF
	var tree_fail := 0
	var geometry_hits := 0
	var geometry_at: Array = []
	var footprint_hits := 0
	var water_hits := 0
	var wall_hits := 0
	var blocked_hits := 0
	var ground_worst := 0.0
	var ground_fail := 0
	var ground_skipped := 0
	var heading_worst := 0.0
	var heading_fail := 0
	var stride_fail := 0
	var stride_samples := 0
	var stride_worst := 0.0
	var inside_count := 0
	var prop_legs := 0
	var prev_heading := PackedFloat32Array()
	var prev_shown := PackedByteArray()
	var prev_at := PackedVector2Array()
	var prev_index := PackedInt32Array()
	var prev_v := PackedFloat32Array()
	var prev_rate := PackedFloat32Array()
	var prev_walked := PackedFloat32Array()
	var prev_step := PackedVector2Array()
	var sharp_turns := 0
	var walk_frames := 0
	prev_walked.resize(count)
	prev_step.resize(count)
	prev_v.resize(count)
	prev_rate.resize(count)
	prev_heading.resize(count)
	prev_shown.resize(count)
	prev_at.resize(count)
	prev_index.resize(count)
	tf.update_samples = PackedInt32Array()
	var steps := int(SECONDS / DT)
	var district_rects: Array = tf.blocked_rects
	for step in steps + 1:
		var t := start + step * DT
		tf.present(t)
		var sample := step % 8 == 0
		for i in count:
			var p = people[i]
			var visible: bool = p.shown and p.alpha >= 0.99
			if visible and prev_shown[i] == 1 and step > 0:
				var turn := absf(angle_difference(prev_heading[i], p.heading))
				heading_worst = maxf(heading_worst, turn)
				if turn > Townsfolk.TURN_RATE * DT + 0.0005:
					heading_fail += 1
				if p.walking and p.index == prev_index[i] and prev_v[i] > 0.0 and p.pos.distance_to(prev_at[i]) > 0.001:
					# Sharp turns of the walked line (a corner taken at once, not rounded).
					var moved_by: Vector2 = p.pos - prev_at[i]
					if prev_step[i] != Vector2.ZERO and absf(moved_by.angle_to(prev_step[i])) > 0.5:
						sharp_turns += 1
						if sharp_turns <= 4:
							print("  sharp turn %.2f rad: %s leg %d at %.2f/%.2f %s" % [moved_by.angle_to(prev_step[i]), p.key, p.leg[p.index], p.walked, p.cums[p.leg[p.index]][-1], str(p.pos)])
					prev_step[i] = moved_by
				else:
					prev_step[i] = Vector2.ZERO
				if p.walking and p.index == prev_index[i] and p.v > 0.3 and prev_v[i] > 0.3 and (p.clip_now == Townsfolk.C_WALK or p.clip_now == Townsfolk.C_LOADED):
					# Distance walked along the line over the last frame against the clip's ground
					# speed at the middle of that frame (the mean of the playback rates at its ends).
					var moved: float = (p.walked - prev_walked[i]) / DT
					var stride: float = p.rig.player.speed_scale * Townsfolk.STRIDE_SPEED[p.clip_now] * p.scale
					var ratio := moved / maxf(stride, 0.001)
					stride_samples += 1
					stride_worst = maxf(stride_worst, absf(ratio - 1.0))
					if absf(ratio - 1.0) > 0.1:
						stride_fail += 1
						if stride_fail <= 3:
							print("  stride %.2f: %s kind %d local %.2f/%.2f v %.2f hold %.2f rate %.2f at %s" % [ratio, p.key, p.kinds[p.index], p.local, p.lengths[p.index], p.v, p.hold, p.rig.player.speed_scale, str(p.pos)])
			prev_shown[i] = 1 if visible else 0
			prev_v[i] = p.v if p.walking else 0.0
			prev_walked[i] = p.walked
			prev_rate[i] = p.rig.player.speed_scale if p.ready else 0.0
			prev_heading[i] = p.heading
			prev_at[i] = p.pos
			prev_index[i] = p.index
			if p.kinds[p.index] == Townsfolk.K_INSIDE and p.local < DT * 1.5:
				inside_count += 1
			if p.kinds[p.index] == Townsfolk.K_WALK and p.carrying and p.local < DT * 1.5:
				prop_legs += 1
			if not visible:
				continue
			if p.walking:
				walk_frames += 1
			var at2: Vector2 = p.pos
			if sample:
				trails[i].append([snappedf(at2.x, 0.01), snappedf(at2.y, 0.01)])
				var trunk := nearest_trunk(at2)
				min_tree = minf(min_tree, trunk)
				if trunk < 0.9:
					tree_fail += 1
				var feet: Vector3 = p.rig.global_position
				if inside_building(feet):
					geometry_hits += 1
					if geometry_at.size() < 5:
						geometry_at.append("%s %s %s" % [p.key, str(at2), last_hit])
				if in_footprint_off_street(at2):
					footprint_hits += 1
				if stage.sample_city(at2.x, at2.y) < -0.25:
					water_hits += 1
				if stage.walls.visible and not stage.walls.inside(at2.x, at2.y, 0.5):
					wall_hits += 1
				for rect: Rect2 in district_rects:
					if rect.has_point(at2):
						blocked_hits += 1
				var ground := drawn_ground(at2.x, at2.y)
				if is_nan(ground):
					ground_skipped += 1
					ground = feet.y
				var off := absf(feet.y - ground)
				ground_worst = maxf(ground_worst, off)
				if off >= 0.05:
					ground_fail += 1
					if ground_fail <= 3:
						print("  ground off %.3f at %s (%s)" % [feet.y - ground, str(at2), p.key])
		# Pairs closer than 0.6 m, and for how long.
		for i in count:
			var a = people[i]
			if not a.shown or a.alpha < 0.5:
				continue
			for j in range(i + 1, count):
				var b = people[j]
				var key := i * 100 + j
				if b.shown and b.alpha >= 0.5 and a.pos.distance_to(b.pos) < 0.6:
					close_time[key] = close_time.get(key, 0.0) + DT
					if close_time[key] > 0.75 and traces < 12 and int(close_time[key] / DT) % 10 == 0:
						traces += 1
						print("  close %.2f s: %s k%d %.1f/%.1f v%.2f h%.2f yaw%.2f %s | %s k%d %.1f/%.1f v%.2f h%.2f yaw%.2f %s" % [close_time[key],
							a.key, a.kinds[a.index], a.local, a.lengths[a.index], a.v, a.hold, a.want_yaw, str(a.pos),
							b.key, b.kinds[b.index], b.local, b.lengths[b.index], b.v, b.hold, b.want_yaw, str(b.pos)])
					if close_time[key] > worst_close:
						worst_close = close_time[key]
						worst_pair = "%s (kind %d %.1f/%.1f v %.2f hold %.2f, %s) / %s (kind %d %.1f/%.1f v %.2f hold %.2f, %s)" % [a.key, a.kinds[a.index], a.local, a.lengths[a.index], a.v, a.hold, str(a.at),
							b.key, b.kinds[b.index], b.local, b.lengths[b.index], b.v, b.hold, str(b.pos)]
				elif close_time.has(key):
					close_pairs += 1
					close_time.erase(key)
	var costs := Array(tf.update_samples)
	costs.sort()
	var median: int = costs[costs.size() / 2]
	var p95: int = costs[int(costs.size() * 0.95)]
	print("%s: min tree %.2f m, geometry hits %d, footprint %d, water %d, wall %d, troops/sites %d, ground worst %.3f m (%d >= 5 cm, %d on frayed edges), heading worst %.3f rad/frame, stride worst %.1f %% of %d, close pairs %d (longest %.2f s), entries %d, loaded legs %d, update median %d us p95 %d us (all %d on screen)" % [
		label, min_tree, geometry_hits, footprint_hits, water_hits, wall_hits, blocked_hits, ground_worst, ground_fail, ground_skipped, heading_worst,
		stride_worst * 100.0, stride_samples, close_pairs, worst_close, inside_count, prop_legs, median, p95, count])
	if not geometry_at.is_empty():
		print("  geometry: ", geometry_at)
	if worst_close > 0.0:
		print("  closest pair: ", worst_pair)
	check(min_tree >= 0.9, "%s: a person %.2f m from a tree trunk" % [label, min_tree])
	check(tree_fail == 0, "%s: %d samples within 0.9 m of a trunk" % [label, tree_fail])
	check(geometry_hits == 0, "%s: %d samples inside building geometry" % [label, geometry_hits])
	check(footprint_hits == 0, "%s: %d samples in a building footprint off the streets" % [label, footprint_hits])
	check(water_hits == 0, "%s: %d samples on water" % [label, water_hits])
	check(wall_hits == 0, "%s: %d samples outside the wall" % [label, wall_hits])
	check(blocked_hits == 0, "%s: %d samples on the troop ground / parade / a site" % [label, blocked_hits])
	check(ground_fail == 0, "%s: feet off the drawn ground by up to %.3f m (%d samples)" % [label, ground_worst, ground_fail])
	check(heading_fail == 0, "%s: heading turned %.3f rad in one frame (limit %.3f)" % [label, heading_worst, Townsfolk.TURN_RATE * DT])
	print("%s: %d sharp turns (> 0.5 rad in one frame) in %d walking frames" % [label, sharp_turns, walk_frames])
	check(sharp_turns * 500 <= walk_frames, "%s: %d sharp turns of the walked line in %d walking frames" % [label, sharp_turns, walk_frames])
	check(stride_samples > 100 and stride_fail == 0, "%s: ground speed differs from the stride by %.1f %% (%d of %d)" % [label, stride_worst * 100.0, stride_fail, stride_samples])
	check(worst_close <= MOMENT, "%s: two people closer than 0.6 m for %.2f s" % [label, worst_close])
	check(inside_count >= 2, "%s: nobody went in through a door (%d)" % [label, inside_count])
	check(prop_legs >= 1 or hall == 1, "%s: nobody carried a load" % label)
	check(median < 200, "%s: townsfolk update median %d us (all on screen)" % [label, median])
	report.append("%s people=%d median_us=%d p95_us=%d close_longest=%.2f min_tree=%.2f ground_worst=%.3f" % [label, count, median, p95, worst_close, min_tree, ground_worst])
	if not dump_dir.is_empty():
		write_dump(hall, trails)
	await default_view_cost(label)
	await works_checks(label)
	if hall == 3:
		await site_checks(label)
	tf.simulate_all = false

## A building site (the warehouse upgraded): the townsfolk plan round it and never enter it; the
## site carrier walks on the drawn ground and clear of the buildings.
func site_checks(label: String) -> void:
	var store: Dictionary = game.state.city.buildings.filter(func(b): return b.type == "ECO-01")[0]
	game.predict_work({"kind": "kingdom", "action": "upgrade", "buildingId": store.id, "expectedLevel": int(store.level)})
	var timer: float = game.timer_now()
	var works: Array = game.current_works(timer)
	check(not works[1].is_empty(), "%s: no site for the predicted upgrade" % label)
	if works[1].is_empty():
		return
	var site: Dictionary = works[1][0]
	stage.works.present({}, site, timer, 0.03)
	tf.present(Time.get_unix_time_from_system())
	var waited := 0
	while (tf.building or tf.layout_changed()) and waited < 600:
		waited += 1
		tf.present(Time.get_unix_time_from_system())
		await process_frame
	var rects: Array = tf.blocked_rects
	check(not rects.is_empty(), "%s: the site is not an obstacle of the plan" % label)
	await build_solids()
	var start := 1794390000.0
	var inside := 0
	var samples := 0
	var carrier_ground := 0.0
	var carrier_hits := 0
	for step in int(60.0 / DT):
		var t := start + step * DT
		tf.present(t)
		if step % 8 != 0:
			continue
		for p in tf.people:
			if not p.shown or p.alpha < 0.99:
				continue
			samples += 1
			for rect: Rect2 in rects:
				if rect.has_point(p.pos):
					inside += 1
		# CityWorks carrier on the same clock (ms).
		stage.works.present({}, site, (t - start) * 1000.0 + float(site.started), DT * 8.0)
		var carrier: Node3D = stage.works.site_carrier
		if is_instance_valid(carrier) and carrier.visible:
			var at := carrier.global_position
			var drawn := drawn_ground(at.x, at.z)
			if not is_nan(drawn):
				carrier_ground = maxf(carrier_ground, absf(at.y - drawn))
			if inside_building(at):
				carrier_hits += 1
	print("%s site: %d samples, %d in the site area; site carrier ground worst %.3f m, building hits %d" % [label, samples, inside, carrier_ground, carrier_hits])
	check(inside == 0, "%s: %d samples of townsfolk inside the building site" % [label, inside])
	check(carrier_ground < 0.05, "%s: site carrier off the drawn ground by %.3f m" % [label, carrier_ground])
	check(carrier_hits == 0, "%s: site carrier inside a building %d times" % [label, carrier_hits])
	game.pending_works.clear()
	stage.works.present({}, {}, timer, 0.03)

## Real frames at the default zoom: what an off-screen person costs (no AnimationPlayer).
func default_view_cost(label: String) -> void:
	tf.simulate_all = false
	stage.target = Vector3(-3, 0, 0)
	stage.zoom = 70.0
	stage.update_camera(0, true)
	await frames(3)
	tf.update_samples = PackedInt32Array()
	tf.section_usec = PackedInt64Array([0, 0, 0])
	for i in 150:
		tf.present(Time.get_unix_time_from_system())
		await process_frame
	var shown := 0
	for p in tf.people:
		if p.shown:
			shown += 1
	var costs := Array(tf.update_samples)
	costs.sort()
	var sections: PackedInt64Array = tf.section_usec
	print("%s default view: %d of %d on screen, update median %d us p95 %d us (evaluate %d, hold %d, pose %d us per frame)" % [label, shown, tf.people.size(),
		costs[costs.size() / 2], costs[int(costs.size() * 0.95)], sections[0] / costs.size(), sections[1] / costs.size(), sections[2] / costs.size()])
	report.append("%s default view: %d on screen, update median %d us" % [label, shown, costs[costs.size() / 2]])
	# Engine side (AnimationPlayer, skeletons, transforms) of the people on screen: the frame's
	# process time with them, and with the townsfolk node switched off.
	var with_people := 0.0
	for i in 120:
		tf.present(Time.get_unix_time_from_system())
		await process_frame
		with_people += Performance.get_monitor(Performance.TIME_PROCESS)
	tf.process_mode = Node.PROCESS_MODE_DISABLED
	tf.visible = false
	var without := 0.0
	for i in 120:
		await process_frame
		without += Performance.get_monitor(Performance.TIME_PROCESS)
	tf.process_mode = Node.PROCESS_MODE_INHERIT
	tf.visible = true
	print("%s process time per frame: %.3f ms with %d people on screen, %.3f ms without the townsfolk" % [label, with_people / 120.0 * 1000.0, shown, without / 120.0 * 1000.0])
	report.append("%s process %.3f ms with, %.3f ms without" % [label, with_people / 120.0 * 1000.0, without / 120.0 * 1000.0])
	# Far away: nobody on screen, every rig and AnimationPlayer off.
	stage.target = Vector3(140, 0, 110)
	stage.update_camera(0, true)
	for i in 4:
		tf.present(Time.get_unix_time_from_system())
		await process_frame
	var active := 0
	for p in tf.people:
		if p.rig != null and (p.rig.visible or p.rig.process_mode != Node.PROCESS_MODE_DISABLED and p.ready):
			active += 1
	check(active == 0, "%s: %d people still animated off screen" % [label, active])
	stage.target = Vector3(-3, 0, 0)
	stage.update_camera(0, true)

## CityWorks: the lumberjack's walk to a tree and the site carrier's walk stay on the drawn
## ground, clear of other trees and of buildings.
func works_checks(label: String) -> void:
	var works = stage.works
	var trees: Array = []
	for tree in stage.selectable_trees:
		var at := Vector2(float(tree.p[0]), float(tree.p[2]))
		if at.length() < 40.0 and stage.near_standing_tree(at, 0.01):
			trees.append([at.length(), tree])
	trees.sort_custom(func(a, b): return a[0] < b[0])
	var worst_tree := INF
	var worst_ground := 0.0
	var hits := 0
	var samples := 0
	var base := 1794370000000.0
	for k in mini(6, trees.size()):
		var tree: Dictionary = trees[k][1]
		var job := {"tree": tree.id, "started": base, "ends": base + 9000.0}
		works.lumber_tree = ""
		var target := Vector2(float(tree.p[0]), float(tree.p[2]))
		for step in 50:
			works.present(job, {}, base + step * 40.0, 0.04)
			var at: Vector3 = works.lumberjack.position
			var p := Vector2(at.x, at.z)
			samples += 1
			for z in range(-2, 3):
				for x in range(-2, 3):
					for other: Vector2 in stage.standing_tree_cells.get(Vector2i(floori(p.x / 4.0) + x, floori(p.y / 4.0) + z), []):
						if other.distance_to(target) > 0.05:
							worst_tree = minf(worst_tree, p.distance_to(other))
			if inside_building(at):
				hits += 1
			var drawn := drawn_ground(p.x, p.y)
			if not is_nan(drawn):
				worst_ground = maxf(worst_ground, absf(at.y - drawn))
	works.present({}, {}, base, 0.04)
	print("%s lumberjack: %d samples, nearest other trunk %.2f m, building hits %d, ground worst %.3f m" % [label, samples, worst_tree, hits, worst_ground])
	check(samples == 0 or worst_tree >= 0.9, "%s: lumberjack walks %.2f m from another trunk" % [label, worst_tree])
	check(hits == 0, "%s: lumberjack inside a building %d times" % [label, hits])
	check(worst_ground < 0.05, "%s: lumberjack off the drawn ground by %.3f m" % [label, worst_ground])

func stride_checks() -> void:
	var p = tf.people[0]
	var skeleton: Skeleton3D = p.rig.model.find_children("*", "Skeleton3D", true, false)[0]
	var walk := stance_speed(p.rig.player, skeleton, &"lf_civilian_follow")
	var loaded := stance_speed(p.rig.player, skeleton, &"lf_civilian_follow_tired")
	print("stride: walk %.4f m/s (STRIDE_SPEED %.3f), loaded %.4f m/s (%.3f)" % [walk, Townsfolk.STRIDE_SPEED[1], loaded, Townsfolk.STRIDE_SPEED[2]])
	check(absf(walk / Townsfolk.STRIDE_SPEED[1] - 1.0) < 0.02, "walk clip stride speed %.3f m/s, table %.3f" % [walk, Townsfolk.STRIDE_SPEED[1]])
	check(absf(loaded / Townsfolk.STRIDE_SPEED[2] - 1.0) < 0.02, "loaded clip stride speed %.3f m/s, table %.3f" % [loaded, Townsfolk.STRIDE_SPEED[2]])
	p.clip_now = -1

func write_dump(hall: int, trails: Array) -> void:
	var plan = stage.town_plan
	var lots: Array = plan.lots.map(func(l): return {"type": l.type, "level": l.level, "rect": [l.rect.position.x, l.rect.position.y, l.rect.size.x, l.rect.size.y],
		"body": [l.body.position.x, l.body.position.y, l.body.size.x, l.body.size.y], "hall": l.hall})
	var segments: Array = plan.segments.map(func(s): return [s.a.x, s.a.y, s.b.x, s.b.y, s.w, s.gate])
	var trees: Array = []
	for cell in stage.standing_tree_cells:
		for t: Vector2 in stage.standing_tree_cells[cell]:
			if absf(t.x) < 66.0 and absf(t.y) < 66.0:
				trees.append([snappedf(t.x, 0.01), snappedf(t.y, 0.01)])
	var water: Array = []
	for z in range(-64, 65):
		for x in range(-64, 65):
			if stage.static_height(float(x), float(z)) < -0.25:
				water.append([x, z])
	var wall: Array = []
	if stage.walls.visible:
		for i in stage.walls.SAMPLES:
			var w: Vector2 = stage.walls.wall_point(i)
			wall.append([w.x, w.y])
	var data: Dictionary = tf.debug_dump()
	data.merge({"hall": hall, "lots": lots, "lot_at": plan.lots.map(func(l): return [l.at.x, l.at.y]), "segments": segments, "plaza": [plan.plaza.position.x, plan.plaza.position.y, plan.plaza.size.x, plan.plaza.size.y],
		"trees": trees, "water": water, "wall": wall, "trails": trails})
	DirAccess.make_dir_recursive_absolute(dump_dir)
	var file := FileAccess.open(dump_dir.path_join("townsfolk_hall%d.json" % hall), FileAccess.WRITE)
	file.store_string(JSON.stringify(data))
	file.close()

func run() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.player_id = "qa-townsfolk"
	# main.gd's _ready runs its smoke test at its end when `smoke` is set: only after it.
	var settle := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < settle:
		await process_frame
	game.smoke = true
	stage = game.stage
	# The townsfolk script loads on a worker after the launch (landscape.attach_townsfolk).
	while not stage.attach_townsfolk():
		await process_frame
	tf = stage.townsfolk
	await scenario(1, 6)
	await scenario(3, 9)
	await scenario(5, 12)
	for line in report:
		print(line)
	print("QA_TOWNSFOLK checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
