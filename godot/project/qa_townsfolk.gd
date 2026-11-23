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
#   - no stepping on the spot: nobody turns back (> 120 deg between two 0.15 m steps) twice
#     within 2 m and 3 s, and nobody moves while standing at a stop (work, wait, talk);
#   - one network: every door on one part of the walk graph (the plan's lanes joined round
#     fences, corners and buildings that grew over them);
#   - neighbours who meet stand at their two places at the same time (>= 3 s), facing;
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
## People on screen every 0.5 s of each view (written with --dump for the plots).
var visible_series := {}

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
func drawn_ground(x: float, z: float, feet := NAN) -> float:
	var best := -INF
	if not is_nan(tf.floor_at(Vector2(x, z))) and not is_nan(feet) and is_instance_valid(solids):
		# On the square a market draws: its paving (a ray down against the building meshes).
		var query := PhysicsRayQueryParameters3D.create(Vector3(x, feet + 0.45, z), Vector3(x, feet - 0.6, z))
		var hit := solids.get_world_3d().direct_space_state.intersect_ray(query)
		if not hit.is_empty():
			return hit.position.y
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
		# (The square a market draws inside its footprint is walked.)
		if (lot.body as Rect2).has_point(p) and not tf.on_street_band(p) and is_nan(tf.floor_at(p)) and not tf.in_green_yard(p):
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

## The walk graph: every door on one part; the street nodes too (the plan's lanes that a
## fence end, a yard's corner, a gate's plinth or a building cut joined round them).
func network_checks(label: String) -> void:
	var door_parts := {}
	for li in tf.door_node:
		door_parts[tf.component[tf.door_node[li]]] = true
	var street_parts := {}
	for n: int in tf.street_nodes:
		if n < tf.g_edges.size() and not tf.g_edges[n].is_empty():
			street_parts[tf.component[n]] = int(street_parts.get(tf.component[n], 0)) + 1
	var detours: Array = tf.bridges.map(func(b): return "%s-%s %.1f m" % [str(b[0]), str(b[1]), b[2]])
	print("%s: %d doors on %d part(s), street nodes on %d part(s) %s, %d detours %s" % [label, tf.door_node.size(), door_parts.size(), street_parts.size(), str(street_parts.values()), detours.size(), str(detours)])
	check(door_parts.size() == 1, "%s: the doors are on %d separate parts of the walk graph" % [label, door_parts.size()])
	check(street_parts.size() == 1, "%s: the streets are cut in %d parts" % [label, street_parts.size()])
	report.append("%s doors=%d door_parts=%d street_parts=%d detours=%d" % [label, tf.door_node.size(), door_parts.size(), street_parts.size(), detours.size()])
	# Two people meeting never stand in the only way between two parts of the town: without
	# their two places every door and every other place is still reached.
	var cut_by := 0
	for pair: Array in tf.meet_pairs:
		var skip := {pair[0]: true, pair[1]: true}
		var start: int = tf.door_node.values()[0]
		var seen := {start: true}
		var queue: Array = [start]
		while not queue.is_empty():
			var n: int = queue.pop_back()
			for e: int in tf.g_edges[n]:
				if not tf.e_live[e]:
					continue
				var m: int = tf.e_b[e] if tf.e_a[e] == n else tf.e_a[e]
				if not seen.has(m) and not skip.has(m):
					seen[m] = true
					queue.append(m)
		var lost: Array = []
		for li in tf.door_node:
			if tf.component[tf.door_node[li]] == tf.component[start] and not seen.has(tf.door_node[li]):
				lost.append(tf.lot_base[li])
		for n: int in tf.yard_spots:
			if not skip.has(n) and n < tf.g_edges.size() and not tf.g_edges[n].is_empty() and tf.component[n] == tf.component[start] and not seen.has(n):
				lost.append("%s %s" % [tf.place_kind.get(n, ""), str(tf.g_nodes[n])])
		if not lost.is_empty():
			cut_by += 1
			print("  meeting places %s / %s are the only way to %s" % [str(tf.g_nodes[pair[0]]), str(tf.g_nodes[pair[1]]), str(lost)])
	print("%s: %d meeting pairs, %d of them in the only way somewhere" % [label, tf.meet_pairs.size(), cut_by])
	check(cut_by == 0, "%s: %d meeting pairs stand in the only way between parts of the town" % [label, cut_by])

## Neighbours who meet: each pair (two people whose meeting places face each other) stands at
## its places at the same time for >= 3 s, each facing the other (the plan's clocks, before
## anyone is held back on the way).
func meeting_checks(label: String) -> void:
	var meeting: Array = tf.people.filter(func(p): return p.meet_phase >= 0)
	var pairs := 0
	for a in meeting:
		for b in meeting:
			if a.key >= b.key or a.spot_a[a.meet_phase].distance_to(b.spot_a[b.meet_phase]) > Townsfolk.MEET_HALF * 2.0 + 0.05:
				continue
			pairs += 1
			var start: float = a.starts[a.meet_phase] - a.phase
			var together := 0.0
			var facing := true
			var t := start - 2.0
			while t < start + Townsfolk.MEET_DWELL + 2.0:
				var da: float = a.delay
				var db: float = b.delay
				a.delay = 0.0
				b.delay = 0.0
				tf.evaluate(a, t)
				tf.evaluate(b, t)
				a.delay = da
				b.delay = db
				if a.index == a.meet_phase and b.index == b.meet_phase and a.kinds[a.index] == Townsfolk.K_DWELL and b.kinds[b.index] == Townsfolk.K_DWELL:
					together += 0.1
					if not a.turning and not b.turning:
						var to_b: Vector2 = b.at - a.at
						var look_a := Vector2(sin(a.want_yaw), cos(a.want_yaw))
						var look_b := Vector2(sin(b.want_yaw), cos(b.want_yaw))
						if look_a.dot(to_b.normalized()) < 0.85 or look_b.dot(-to_b.normalized()) < 0.85:
							facing = false
				t += 0.1
			print("%s: %s and %s meet for %.1f s%s" % [label, a.key, b.key, together, "" if facing else " (not facing)"])
			check(together >= 3.0 and facing, "%s: %s and %s stand together %.1f s, facing %s" % [label, a.key, b.key, together, str(facing)])
	print("%s: %d meetings" % [label, pairs])
	report.append("%s meetings=%d" % [label, pairs])

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
	network_checks(label)
	meeting_checks(label)
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
	# Stepping on the spot: the last 0.15 m step of each person and its last turn back.
	var step_from := PackedVector2Array()
	var step_dir := PackedVector2Array()
	var back_t := PackedFloat64Array()
	var back_at := PackedVector2Array()
	var reversals := 0
	var jitter := 0
	var drift := 0
	var drift_worst := 0.0
	step_from.resize(count)
	step_dir.resize(count)
	back_t.resize(count)
	back_t.fill(-100.0)
	back_at.resize(count)
	var tracked := PackedByteArray()
	tracked.resize(count)
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
			if p.shown and p.alpha >= 0.5:
				if tracked[i] == 0:
					tracked[i] = 1
					step_from[i] = p.pos
					step_dir[i] = Vector2.ZERO
				else:
					var moved_step: Vector2 = p.pos - step_from[i]
					if moved_step.length() >= 0.15:
						if step_dir[i] != Vector2.ZERO and absf(moved_step.angle_to(step_dir[i])) > 2.094:
							reversals += 1
							if t - back_t[i] < 3.0 and p.pos.distance_to(back_at[i]) < 2.0:
								jitter += 1
								if jitter <= 5:
									print("  turned back twice in %.2f s, %.2f m: %s kind %d leg %d at %s" % [t - back_t[i], p.pos.distance_to(back_at[i]), p.key, p.kinds[p.index], p.leg[p.index], str(p.pos)])
							back_t[i] = t
							back_at[i] = p.pos
						step_dir[i] = moved_step
						step_from[i] = p.pos
				if p.kinds[p.index] == Townsfolk.K_DWELL and prev_index[i] == p.index and prev_shown[i] == 1:
					var still: float = p.pos.distance_to(prev_at[i])
					drift_worst = maxf(drift_worst, still)
					if still > 0.001:
						drift += 1
			else:
				tracked[i] = 0
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
					if footprint_hits <= 3:
						print("  in a footprint at %s (%s kind %d)" % [str(at2), p.key, p.kinds[p.index]])
				if stage.sample_city(at2.x, at2.y) < -0.25:
					water_hits += 1
				if stage.walls.visible and not stage.walls.inside(at2.x, at2.y, 0.5):
					wall_hits += 1
				for rect: Rect2 in district_rects:
					if rect.has_point(at2):
						blocked_hits += 1
				var ground := drawn_ground(at2.x, at2.y, feet.y)
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
	print("%s: %d turns back (> 120 deg between 0.15 m steps), %d twice within 2 m / 3 s; standing: %d frames moved (worst %.4f m)" % [label, reversals, jitter, drift, drift_worst])
	check(jitter == 0, "%s: %d times someone turned back twice within 2 m and 3 s (stepping on the spot)" % [label, jitter])
	check(drift == 0, "%s: %d frames someone standing at a stop moved (up to %.4f m)" % [label, drift, drift_worst])
	report.append("%s turns_back=%d twice_2m_3s=%d standing_moved=%d" % [label, reversals, jitter, drift])
	check(inside_count >= 2, "%s: nobody went in through a door (%d)" % [label, inside_count])
	check(prop_legs >= 1 or hall == 1, "%s: nobody carried a load" % label)
	# Everybody evaluated and posed every frame (the worst case): 15 us a person.
	check(median < 15 * count, "%s: townsfolk update median %d us with all %d on screen (budget %d)" % [label, median, count, 15 * count])
	report.append("%s people=%d median_us=%d p95_us=%d close_longest=%.2f min_tree=%.2f ground_worst=%.3f" % [label, count, median, p95, worst_close, min_tree, ground_worst])
	if not dump_dir.is_empty():
		write_dump(hall, trails)
	await default_view_cost(label)
	await visible_counts(label)
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
## Skeletons posed and triangles drawn by the people on screen now.
func on_screen_load() -> Vector2i:
	var skeletons := 0
	var triangles := 0
	for p in tf.people:
		if not p.shown or p.rig == null:
			continue
		skeletons += 1
		for mesh in p.rig.lods[p.lod]:
			if is_instance_valid(mesh) and mesh.mesh != null:
				triangles += mesh_triangles(mesh.mesh)
	return Vector2i(skeletons, triangles)

var triangle_cache := {}

func mesh_triangles(mesh: Mesh) -> int:
	if not triangle_cache.has(mesh):
		var total := 0
		for surface in mesh.get_surface_count():
			var arrays := mesh.surface_get_arrays(surface)
			var indices: Variant = arrays[Mesh.ARRAY_INDEX]
			total += (indices as PackedInt32Array).size() / 3 if indices is PackedInt32Array and not (indices as PackedInt32Array).is_empty() else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
		triangle_cache[mesh] = total
	return triangle_cache[mesh]

## The player's first view of the city (zoom 70 at the start target): the townsfolk's update
## (script; budget at hall V: median <= 0.30 ms, p95 <= 0.45 ms), the AnimationPlayers advanced
## at ANIM_FAR_HZ (measured apart), and the engine's whole process time with and without them.
func default_view_cost(label: String) -> void:
	tf.simulate_all = false
	stage.target = Vector3(5, 0, -4)
	stage.zoom = 70.0
	stage.update_camera(0, true)
	await frames(3)
	tf.update_samples = PackedInt32Array()
	tf.anim_samples = PackedInt32Array()
	tf.section_usec = PackedInt64Array([0, 0, 0])
	for i in 300:
		tf.present(Time.get_unix_time_from_system())
		await process_frame
	var shown := 0
	for p in tf.people:
		if p.shown:
			shown += 1
	var load := on_screen_load()
	var costs := Array(tf.update_samples)
	costs.sort()
	var anim := Array(tf.anim_samples)
	anim.sort()
	var anim_mean := 0.0
	for a in anim:
		anim_mean += a
	anim_mean /= maxf(1.0, anim.size())
	var sections: PackedInt64Array = tf.section_usec
	var median: int = costs[costs.size() / 2]
	var p95: int = costs[int(costs.size() * 0.95)]
	print("%s default view: %d of %d on screen (%d skeletons, %d triangles), update median %d us p95 %d us (evaluate %d, hold %d, pose %d us per frame); animation (manual %s, %.0f Hz) mean %.0f us p95 %d us per frame" % [label, shown, tf.people.size(),
		load.x, load.y, median, p95, sections[0] / costs.size(), sections[1] / costs.size(), sections[2] / costs.size(), str(tf.anim_manual), Townsfolk.ANIM_FAR_HZ, anim_mean, anim[int(anim.size() * 0.95)]])
	report.append("%s default view: %d on screen, update median %d us p95 %d us, animation mean %.0f us" % [label, shown, median, p95, anim_mean])
	if label == "hall 5":
		check(median <= 300 and p95 <= 450, "%s default view: townsfolk update median %d us p95 %d us (budget 300 / 450)" % [label, median, p95])
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
	stage.target = Vector3(5, 0, -4)
	stage.update_camera(0, true)

## A point hidden from the camera by a building (a ray towards the camera hits its meshes).
func hidden_by_building(at: Vector3) -> bool:
	if not is_instance_valid(solids):
		return false
	var back: Vector3 = stage.camera.global_transform.basis.z
	var query := PhysicsRayQueryParameters3D.create(at, at + back * 150.0)
	return not solids.get_world_3d().direct_space_state.intersect_ray(query).is_empty()

## How many people a player sees: 120 s on the clock at 30 Hz with the camera still, at the
## default view (zoom 70 at the start target) and close up (zoom 34, as a tap on a building
## zooms) over the hall square, the warehouse, the market, the farm and the lumber camp.
## Counted: in the camera frustum, not inside a building (alpha >= 0.5); and of those, the ones
## no building hides (a ray from the chest to the camera), every 0.5 s (the series, --dump).
func visible_counts(label: String) -> void:
	var views: Array = [["default z70", Vector3(5, 0, -4), 70.0]]
	for type in ["ECO-05", "ECO-01", "ECO-03", "RES-04", "RES-01"]:
		for marker: Dictionary in stage.place_markers:
			if marker.get("kind", "") == "building" and str(marker.item.get("type", "")) == type:
				views.append(["%s z34" % type, marker.position - Vector3.UP * 5.0 + Vector3(0, 0, 4), 34.0])
				break
	tf.simulate_all = false
	var camera: Camera3D = stage.camera
	var close_sum := 0.0
	var close_frames := 0
	var close_min := 1000
	for view: Array in views:
		stage.target = view[1]
		stage.zoom = view[2]
		stage.update_camera(0, true)
		await frames(2)
		var start := 1794380000.0
		var low := 1000
		var high := 0
		var total := 0
		var steps := int(SECONDS / DT)
		var series := PackedInt32Array()
		var load_sum := Vector2i.ZERO
		var load_max := Vector2i.ZERO
		var open_total := 0
		var open_low := 1000
		var near_series := PackedInt32Array()
		var centre := Vector2(float(view[1].x), float(view[1].z))
		for step in steps:
			tf.present(start + step * DT)
			var seen := 0
			var open := 0
			var near := 0
			for p in tf.people:
				if p.alpha >= 0.5 and camera.is_position_in_frustum(Vector3(p.pos.x, p.y + 0.9, p.pos.y)):
					seen += 1
					if step % 15 == 0 and not hidden_by_building(Vector3(p.pos.x, p.y + 1.0, p.pos.y)):
						open += 1
						if p.pos.distance_to(centre) < 15.0:
							near += 1
			low = mini(low, seen)
			high = maxi(high, seen)
			total += seen
			if step % 15 == 0:
				series.append(open)
				near_series.append(near)
				open_total += open
				open_low = mini(open_low, open)
				var load := on_screen_load()
				load_sum += load
				load_max = Vector2i(maxi(load_max.x, load.x), maxi(load_max.y, load.y))
		var mean := float(total) / steps
		var samples := maxi(1, series.size())
		var near_low := 1000
		var near_sum := 0
		for v in near_series:
			near_low = mini(near_low, v)
			near_sum += v
		print("%s visible %s: min %d mean %.1f max %d of %d in the frame; not behind a building min %d mean %.1f; of those within 15 m of the view's centre min %d mean %.1f; skeletons mean %.1f max %d, triangles mean %d max %d" % [label, view[0], low, mean, high, tf.people.size(),
			open_low, float(open_total) / samples, near_low, float(near_sum) / samples, float(load_sum.x) / samples, load_max.x, load_sum.y / samples, load_max.y])
		visible_series["%s %s" % [label, view[0]]] = Array(series)
		visible_series["%s %s near" % [label, view[0]]] = Array(near_series)
		if view[2] < 50.0:
			close_sum += open_total
			close_frames += samples
			close_min = mini(close_min, open_low)
		else:
			report.append("%s visible z70 min %d mean %.1f (in the frame), %d / %.1f not behind a building" % [label, low, mean, open_low, float(open_total) / samples])
	if close_frames > 0:
		report.append("%s visible z34 (5 views, not behind a building) min %d mean %.1f" % [label, close_min, close_sum / close_frames])
	stage.target = Vector3(5, 0, -4)
	stage.zoom = 70.0
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
	await scenario(1, 8)
	await scenario(3, 14)
	await scenario(5, 20)
	if not dump_dir.is_empty():
		var file := FileAccess.open(dump_dir.path_join("townsfolk_visible.json"), FileAccess.WRITE)
		file.store_string(JSON.stringify(visible_series))
		file.close()
	for line in report:
		print(line)
	print("QA_TOWNSFOLK checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
