extends "res://qa_townsfolk.gd"

# Wall guards (build 1024, src/wall_guards.gd): archers and crossbowmen on the city wall, offline
# (the built-in demo city grown as qa_townsfolk.gd grows it, "walls and gate" on v1-17), at
# wall levels I-V. Independent checks (against what is drawn, not the guards' own numbers):
#   - feet: a ray down from 0.5 m above the feet against the drawn wall (every multimesh
#     instance of src/city_walls.gd as triangles), the gate scene and the buildings, and the
#     drawn ground (town ground / terrain) for the pair at the gate: |feet - surface| (worst);
#   - clearance: a body capsule (r 0.25 m, from 0.15 m to 1.8 m above the feet) against the same
#     triangles: no hit; and the widest capsule that still fits (worst, with the part it touches:
#     posts, merlons, rails, tower bodies...);
#   - jitter: nobody turns back (> 120 deg between two 0.15 m steps) twice within 2 m and 3 s;
#     heading never turns faster than TURN_RATE; standing guards do not drift;
#   - stride: ground speed = walk clip playback x stride (GaitTable) within 10 %;
#   - seen from the game's camera (a ray from the head / chest towards it, against the same
#     triangles): the share of the time per role; wall I sentries >= 80 %, wall II-IV patrols
#     >= 60 % (the towers' roofs hide the decks from wall III up, wall V's gallery its walkway);
#   - no two guards closer than 0.7 m; nobody of the townsfolk walks through a guard (0.45 m);
#   - count per level (wall I-V), the archer / crossbowman mix, roles; nobody without a wall;
#   - re-plan on level change (hall and wall up, the watchtower built): plan time (spread over
#     frames: the dearest frame and how many), the models kept (no new instancing for the same
#     kinds), the frame times while it happens;
#   - cost at hall V / wall V in the default view (zoom 70): the guards' update median <= 0.25 ms,
#     p95 <= 0.40 ms; the AnimationPlayers advanced at 20 Hz measured apart; skeletons and
#     triangles on screen; off screen nobody animated; frame times while the models come in.
#   godot --headless --path . -s qa_wall_guards.gd [-- --dump=/abs/dir]
# --dump writes wall_guards_L<level>.json (wall, towers, stretches, beats, trails) for
# tools/wall_guards_map.py.

const WallGuards = preload("res://src/wall_guards.gd")
const GUARD_SECONDS := 90.0
## From a point towards the city camera (landscape.apply_camera_pose(): target + (75, 83, 75),
## normalised).
const CAMERA_DIR := Vector3(0.5569, 0.6163, 0.5569)
var wg: Node3D
var wall_solids: StaticBody3D
var body := CapsuleShape3D.new()
var levels_report := {}

var quick := false
var only_levels: PackedStringArray = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--dump="):
			dump_dir = arg.trim_prefix("--dump=")
		elif arg == "--quick":
			quick = true
		elif arg.begins_with("--levels="):
			only_levels = arg.trim_prefix("--levels=").split(",")
	call_deferred("run_guards")

func wall_level(level: int) -> void:
	for b in game.state.city.buildings:
		if b.type == "SUP-03":
			if level <= 0:
				game.state.city.buildings.erase(b)
			else:
				b.level = level
			return
	if level > 0:
		add_building("SUP-03", "v1-17", level)

## The city presented, the townsfolk's plan done and the guards' models in.
func settle(label: String) -> void:
	await stage.present_city(game.state)
	await frames(2)
	var waited := 0
	var worst_frame := 0.0
	var worst_guards := 0.0
	var last := Time.get_ticks_usec()
	while waited < 900:
		stage.present_workers(Time.get_unix_time_from_system())
		await process_frame
		var now := Time.get_ticks_usec()
		worst_frame = maxf(worst_frame, (now - last) / 1000.0)
		last = now
		if wg != null:
			worst_guards = maxf(worst_guards, wg.frame_usec / 1000.0)
		waited += 1
		if wg != null and not tf.building and wg.signature == wg.layout_key() and wg.guards.all(func(g): return g.node != null) and wg.lod1_state in ["ready", "failed", ""]:
			break
	if wg == null:
		wg = stage.wall_guards
	var made: Array = Array(wg.instance_samples) if wg != null else []
	made.sort()
	print("%s: settled in %d frames (worst frame %.1f ms, the guards' worst %.2f ms; models instanced so far %d, worst %.2f ms)" % [label, waited, worst_frame, worst_guards,
		made.size(), (made[-1] if not made.is_empty() else 0) / 1000.0])
	guards_worst_frame = maxf(guards_worst_frame, worst_guards)

## Every drawn part of the wall as triangles (each multimesh instance), the gate scene and the
## buildings: one static body; each shape knows its part.
func build_wall_solids() -> void:
	if is_instance_valid(wall_solids):
		wall_solids.free()
	wall_solids = StaticBody3D.new()
	var triangles := 0
	if stage.walls.visible:
		# The parts exactly as the ring's multimeshes are filled (CityWalls.collect -> emit; a
		# headless run keeps no multimesh transforms to read back).
		var parts := {}
		stage.walls.collect(parts)
		var shapes: Dictionary = stage.walls.meshes()
		for key in parts:
			var part: Dictionary = parts[key]
			var faces: PackedVector3Array = (shapes[part.mesh] as Mesh).get_faces()
			var all := PackedVector3Array()
			for xform: Transform3D in part.transforms:
				all.append_array(xform * faces)
			add_shape(all, "wall:" + str(key))
			triangles += all.size() / 3
	var models: Array = [stage.gate_node] if is_instance_valid(stage.gate_node) else []
	for child in stage.buildings.get_children():
		if child != stage.gate_node and child is Node3D and (child as Node3D).global_position.distance_to(stage.walls.main_gate) < 60.0:
			models.append(child)
	for model: Node3D in models:
		var source := "gate" if model == stage.gate_node else "building:" + str(model.get_meta("city_signature", "")).get_slice("|", 1).get_file()
		for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
			if mesh.mesh == null:
				continue
			var faces: PackedVector3Array = mesh.global_transform * mesh.mesh.get_faces()
			add_shape(faces, source)
			triangles += faces.size() / 3
	root.add_child(wall_solids)
	await physics_frame
	await physics_frame
	if not stage.walls.towers.is_empty():
		var t: Vector3 = stage.walls.towers[0].p
		var probe := PhysicsRayQueryParameters3D.create(t + Vector3.UP * 40.0, t - Vector3.UP * 5.0)
		var hit := wall_solids.get_world_3d().direct_space_state.intersect_ray(probe)
		print("probe ray down the first tower %s: %s (deck top %.3f)" % [str(t), str(hit.get("position", "no hit")), t.y + float(stage.walls.towers[0].deck)])
	report.append("wall solids: %d triangles" % triangles)

func add_shape(faces: PackedVector3Array, source: String) -> void:
	if faces.is_empty():
		return
	var shape := ConcavePolygonShape3D.new()
	shape.backface_collision = true
	shape.set_faces(faces)
	var holder := CollisionShape3D.new()
	holder.shape = shape
	holder.set_meta("source", source)
	wall_solids.add_child(holder)

var touched := ""

## The capsule of radius r around a guard standing at `feet` hits drawn geometry.
func body_hits(feet: Vector3, r: float) -> bool:
	body.radius = r
	body.height = 1.65
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = body
	# From feet + 0.15 to feet + 1.8.
	query.transform = Transform3D(Basis.IDENTITY, feet + Vector3.UP * (0.15 + 1.65 * 0.5))
	var hits := wall_solids.get_world_3d().direct_space_state.intersect_shape(query, 1)
	if hits.is_empty():
		return false
	var shape := int(hits[0].shape)
	touched = str(wall_solids.get_child(shape).get_meta("source", "")) if shape < wall_solids.get_child_count() else "?"
	return true

## The widest body (m) that fits at `feet` (0.0 .. 0.8), and what it touches.
func clearance(feet: Vector3) -> Array:
	var lo := 0.0
	var hi := 1.5
	if not body_hits(feet, hi):
		return [hi, ""]
	var what := touched
	for step in 7:
		var mid := (lo + hi) * 0.5
		if body_hits(feet, maxf(mid, 0.01)):
			hi = mid
			what = touched
		else:
			lo = mid
	return [lo, what]

## The drawn surface under the feet: a ray from 0.5 m above against the wall, gate and buildings;
## the town ground / terrain where nothing of those is hit.
func surface_under(feet: Vector3) -> Array:
	var query := PhysicsRayQueryParameters3D.create(feet + Vector3.UP * 0.5, feet - Vector3.UP * 1.5)
	var hit := wall_solids.get_world_3d().direct_space_state.intersect_ray(query)
	var ground := drawn_ground(feet.x, feet.z, feet.y)
	if hit.is_empty():
		return [ground, "ground"]
	var y: float = hit.position.y
	if not is_nan(ground) and ground > y:
		return [ground, "ground"]
	var shape := int(hit.shape)
	return [y, str(wall_solids.get_child(shape).get_meta("source", "")) if shape < wall_solids.get_child_count() else "?"]

func wait_guards() -> void:
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		stage.present_workers(Time.get_unix_time_from_system())
		if wg != null and wg.guards.all(func(g): return g.node != null and g.ready):
			return
		await process_frame

func guard_scenario(label: String, hall: int, level: int, expected: int) -> void:
	if not only_levels.is_empty() and not str(maxi(level, 1)) in only_levels:
		return
	await town(hall)
	wall_level(level)
	var instanced_before := count_instanced()
	var plans_before: int = wg.replans if wg != null else 0
	await settle(label)
	await wait_guards()
	var walls = stage.walls
	var guards: Array = wg.guards
	var roles := {}
	var units := {}
	for g in guards:
		roles[g.role] = int(roles.get(g.role, 0)) + 1
		units[g.unit] = int(units.get(g.unit, 0)) + 1
	var defence: Dictionary = load("res://src/city_defence.gd").stats(hall, level, 0)
	print("%s: wall level %d, %d towers, %d gates, walkway %s; %d guards %s %s (defence table: %d archers), %d stretches %s, plan %.2f ms" % [label, walls.wall_level,
		walls.towers.size(), walls.gates.size(), str(wg.walk), guards.size(), str(roles), str(units), defence.archers, wg.stretches.size(),
		str(wg.stretches.map(func(s): return snappedf(s.length, 0.1))), wg.last_plan_usec / 1000.0])
	print("  plan steps (us): %s over %d frames, the dearest %.2f ms" % [str(wg.plan_profile), wg.plan_frames, wg.plan_slice_worst / 1000.0])
	check(guards.size() == expected, "%s: %d guards, expected %d" % [label, guards.size(), expected])
	check(guards.size() <= defence.archers, "%s: more guards drawn (%d) than archers on the wall (%d)" % [label, guards.size(), defence.archers])
	var archers: int = units.get("ENG-03", 0)
	var crossbows: int = units.get("ENG-04", 0)
	check(crossbows >= floori(guards.size() / 3.0) and crossbows <= ceili(guards.size() / 3.0) + 1 and archers > crossbows, "%s: mix %d archers / %d crossbowmen" % [label, archers, crossbows])
	check(int(roles.get("gate", 0)) == 2, "%s: %d at the main gate (expected a pair)" % [label, int(roles.get("gate", 0))])
	if level >= 2:
		check(int(roles.get("patrol", 0)) >= 2, "%s: %d patrols on the walkway" % [label, int(roles.get("patrol", 0))])
	else:
		check(int(roles.get("patrol", 0)) == 0, "%s: patrols on a wall without a walkway" % label)
	check(int(roles.get("tower", 0)) >= 3, "%s: %d sentries on towers" % [label, int(roles.get("tower", 0))])
	levels_report[maxi(level, 1)] = {"guards": guards.size(), "roles": roles, "units": units, "archers_table": defence.archers}
	await build_wall_solids()
	build_ground()
	await simulate(label, level)
	if not dump_dir.is_empty():
		var data: Dictionary = wg.debug_dump()
		data["trails"] = last_trails
		DirAccess.make_dir_recursive_absolute(dump_dir)
		var file := FileAccess.open(dump_dir.path_join("wall_guards_L%d.json" % maxi(level, 1)), FileAccess.WRITE)
		file.store_string(JSON.stringify(data))
		file.close()

var last_trails: Array = []
var guards_worst_frame := 0.0

func count_instanced() -> int:
	return wg.instance_samples.size() if wg != null else 0

## GUARD_SECONDS at 30 Hz, every guard evaluated and posed as if on screen.
func simulate(label: String, level: int) -> void:
	wg.simulate_all = true
	var guards: Array = wg.guards
	var count := guards.size()
	var start := 1794500000.0 + level * 1000.0
	var prev_heading := PackedFloat32Array()
	prev_heading.resize(count)
	var prev_pos := PackedVector3Array()
	prev_pos.resize(count)
	var prev_index := PackedInt32Array()
	prev_index.resize(count)
	var prev_walked := PackedFloat32Array()
	prev_walked.resize(count)
	var prev_v := PackedFloat32Array()
	prev_v.resize(count)
	var step_from := PackedVector3Array()
	step_from.resize(count)
	var step_dir := PackedVector2Array()
	step_dir.resize(count)
	var back_t := PackedFloat64Array()
	back_t.resize(count)
	back_t.fill(-100.0)
	var back_at := PackedVector3Array()
	back_at.resize(count)
	last_trails.clear()
	for i in count:
		last_trails.append([])
	var seen_by_role := {}
	var samples_by_role := {}
	var feet_worst := 0.0
	var feet_where := ""
	var feet_fail := 0
	var feet_by_role := {}
	var hits := 0
	var hit_where: Array = []
	var clear_worst := INF
	var clear_where := ""
	var clear_by_role := {}
	var heading_worst := 0.0
	var heading_fail := 0
	var reversals := 0
	var jitter := 0
	var drift := 0
	var stride_samples := 0
	var stride_fail := 0
	var stride_worst := 0.0
	var close_pairs := 0
	var closest := INF
	var acts := 0
	var walking_frames := 0
	var townsfolk_close := 0
	var townsfolk_nearest := INF
	var steps := int(GUARD_SECONDS / DT)
	for step in steps + 1:
		var t := start + step * DT
		wg.present(t)
		if step % 4 == 0:
			tf.present(t)
		for i in count:
			var g = guards[i]
			if step > 0:
				var turn := absf(angle_difference(prev_heading[i], g.heading))
				heading_worst = maxf(heading_worst, turn)
				if turn > WallGuards.TURN_RATE * DT + 0.0005:
					heading_fail += 1
				if not g.walking and g.index == prev_index[i] and g.pos.distance_to(prev_pos[i]) > 0.0005:
					drift += 1
				if g.walking and g.index == prev_index[i] and g.v > 0.3 and prev_v[i] > 0.3 and g.clip_now == WallGuards.C_WALK:
					var moved: float = (g.walked - prev_walked[i]) / DT
					var stride: float = g.player.speed_scale * g.stride
					var ratio := moved / maxf(stride, 0.001)
					stride_samples += 1
					stride_worst = maxf(stride_worst, absf(ratio - 1.0))
					if absf(ratio - 1.0) > 0.1:
						stride_fail += 1
			if g.walking:
				walking_frames += 1
			if g.clip_now == WallGuards.C_ACT and g.clip_offset < DT * 1.5:
				acts += 1
			# Turning back: 0.15 m steps.
			var moved_step := Vector2(g.pos.x - step_from[i].x, g.pos.z - step_from[i].z)
			if step == 0:
				step_from[i] = g.pos
			elif moved_step.length() >= 0.15:
				if step_dir[i] != Vector2.ZERO and absf(moved_step.angle_to(step_dir[i])) > 2.094:
					reversals += 1
					if t - back_t[i] < 3.0 and g.pos.distance_to(back_at[i]) < 2.0:
						jitter += 1
						print("  turned back twice in %.2f s / %.2f m: %s at %s" % [t - back_t[i], g.pos.distance_to(back_at[i]), g.key, str(g.pos)])
					back_t[i] = t
					back_at[i] = g.pos
				step_dir[i] = moved_step
				step_from[i] = g.pos
			prev_heading[i] = g.heading
			prev_pos[i] = g.pos
			prev_index[i] = g.index
			prev_walked[i] = g.walked
			prev_v[i] = g.v if g.walking else 0.0
			if step % 6 != 0:
				continue
			last_trails[i].append([snappedf(g.pos.x, 0.01), snappedf(g.pos.z, 0.01)])
			var feet: Vector3 = g.node.global_position
			var under: Array = surface_under(feet)
			var off := absf(feet.y - float(under[0])) if not is_nan(float(under[0])) else 0.0
			if off > feet_worst:
				feet_worst = off
				feet_where = "%s on %s at %s" % [g.key, under[1], str(feet)]
			feet_by_role[g.role] = maxf(float(feet_by_role.get(g.role, 0.0)), off)
			if off > 0.03:
				feet_fail += 1
				if feet_fail <= 4:
					print("  feet off %.3f m: %s (%s) on %s at %s" % [feet.y - float(under[0]), g.key, g.role, under[1], str(feet)])
			# Seen from the game's camera (fixed direction, orthographic): the head or the chest
			# with nothing of the wall, the gate or a building between it and the camera.
			var seen := 0
			for up: float in [1.2, 1.6]:
				var eye: Vector3 = feet + Vector3.UP * up * float(g.scale)
				var look := PhysicsRayQueryParameters3D.create(eye, eye + CAMERA_DIR * 70.0)
				if wall_solids.get_world_3d().direct_space_state.intersect_ray(look).is_empty():
					seen = 1
			seen_by_role[g.role] = int(seen_by_role.get(g.role, 0)) + seen
			samples_by_role[g.role] = int(samples_by_role.get(g.role, 0)) + 1
			if body_hits(feet, 0.25):
				hits += 1
				if hit_where.size() < 6:
					hit_where.append("%s (%s) touches %s at %s" % [g.key, g.role, touched, str(feet)])
			if step % 30 == 0:
				var c: Array = clearance(feet)
				clear_by_role[g.role] = minf(float(clear_by_role.get(g.role, INF)), float(c[0]))
				if float(c[0]) < clear_worst:
					clear_worst = c[0]
					clear_where = "%s (%s) by %s" % [g.key, g.role, c[1]]
			# Nobody of the townsfolk walks through a guard.
			for p in tf.people:
				if p.alpha >= 0.5:
					var d := Vector2(p.pos.x - g.pos.x, p.pos.y - g.pos.z).length()
					if absf(p.y - g.pos.y) < 1.0:
						townsfolk_nearest = minf(townsfolk_nearest, d)
						if d < 0.45:
							townsfolk_close += 1
		if step % 6 == 0:
			for i in count:
				for j in range(i + 1, count):
					var d: float = guards[i].pos.distance_to(guards[j].pos)
					closest = minf(closest, d)
					if d < 0.7:
						close_pairs += 1
	var seen_share := {}
	var seen_all := 0
	var samples_all := 0
	for role in samples_by_role:
		seen_share[role] = snappedf(float(seen_by_role.get(role, 0)) / samples_by_role[role], 0.01)
		seen_all += int(seen_by_role.get(role, 0))
		samples_all += int(samples_by_role[role])
	print("%s: seen from the game's camera (head or chest clear of the wall, gate and buildings) %.0f %% of the time, by role %s" % [label, 100.0 * seen_all / maxi(samples_all, 1), str(seen_share)])
	# The tower roofs hide the decks from wall III up and wall V's covered gallery most of its
	# walkway (the wall's art): there the share is reported, not checked.
	if level <= 1:
		check(float(seen_share.get("tower", 0.0)) >= 0.8, "%s: tower sentries seen from the game's camera %.0f %% of the time" % [label, 100.0 * float(seen_share.get("tower", 0.0))])
	elif level <= 4:
		check(float(seen_share.get("patrol", 0.0)) >= 0.6, "%s: patrols seen from the game's camera %.0f %% of the time" % [label, 100.0 * float(seen_share.get("patrol", 0.0))])
	print("%s: feet worst %.4f m (%s), by role %s; capsule r0.25 hits %d %s; widest body worst %.2f m (%s), by role %s" % [label, feet_worst, feet_where, str(feet_by_role), hits, str(hit_where), clear_worst, clear_where, str(clear_by_role)])
	print("%s: heading worst %.3f rad/frame; %d turns back, %d twice within 2 m / 3 s; standing drift %d; stride worst %.1f %% of %d; closest pair %.2f m; flourishes %d; townsfolk nearest %.2f m (%d < 0.45 m)" % [label, heading_worst, reversals, jitter, drift, stride_worst * 100.0, stride_samples, closest, acts, townsfolk_nearest, townsfolk_close])
	check(feet_fail == 0, "%s: feet off the walkway / deck / ground by up to %.3f m (%d samples)" % [label, feet_worst, feet_fail])
	check(hits == 0, "%s: %d samples of a guard's body inside drawn geometry %s" % [label, hits, str(hit_where)])
	check(heading_fail == 0, "%s: heading turned %.3f rad in a frame" % [label, heading_worst])
	check(jitter == 0, "%s: %d times a guard turned back twice within 2 m / 3 s" % [label, jitter])
	check(drift == 0, "%s: standing guards moved %d frames" % [label, drift])
	check(level < 2 or (stride_samples > 100 and stride_fail == 0), "%s: walk speed off the stride by %.1f %% (%d of %d)" % [label, stride_worst * 100.0, stride_fail, stride_samples])
	check(close_pairs == 0, "%s: two guards closer than 0.7 m (%.2f m)" % [label, closest])
	check(townsfolk_close == 0, "%s: townsfolk within 0.45 m of a guard %d times" % [label, townsfolk_close])
	report.append("L%d guards=%d feet_worst=%.4f (%s) clearance_worst=%.2f (%s) jitter=%d heading_worst=%.3f stride_worst=%.1f%% closest=%.2f" % [maxi(level, 1), count, feet_worst, feet_where.get_slice(" at ", 0), clear_worst, clear_where, jitter, heading_worst, stride_worst * 100.0, closest])
	levels_report[maxi(level, 1)].merge({"seen": snappedf(float(seen_all) / maxi(samples_all, 1), 0.01), "seen_by_role": seen_share, "feet_worst": feet_worst, "clearance_worst": clear_worst, "clearance_by_role": clear_by_role, "feet_by_role": feet_by_role})
	wg.simulate_all = false

## The default view at hall V / wall V: the guards' update, the animation, what is on screen.
func guard_cost(label: String) -> void:
	wg.simulate_all = false
	stage.target = Vector3(5, 0, -4)
	stage.zoom = 70.0
	stage.update_camera(0, true)
	await frames(3)
	for i in 30:
		wg.present(Time.get_unix_time_from_system())
		await process_frame
	wg.update_samples = PackedInt32Array()
	wg.anim_samples = PackedInt32Array()
	for i in 600:
		wg.present(Time.get_unix_time_from_system())
		await process_frame
	var shown := 0
	var skeletons := 0
	var triangles := 0
	for g in wg.guards:
		if g.shown:
			shown += 1
			skeletons += 1
			for mesh in g.meshes:
				if mesh.visible:
					triangles += mesh_triangles(mesh.mesh)
	var costs := Array(wg.update_samples)
	costs.sort()
	var anim := Array(wg.anim_samples)
	anim.sort()
	var anim_mean := 0.0
	for a in anim:
		anim_mean += a
	anim_mean /= maxf(1.0, anim.size())
	var median: int = costs[costs.size() / 2]
	var p95: int = costs[int(costs.size() * 0.95)]
	print("%s default view (zoom 70): %d of %d guards on screen (%d skeletons, %d source triangles, LOD%d), update median %d us p95 %d us max %d us; animation (manual %s, %.0f Hz) mean %.0f us p95 %d us" % [label,
		shown, wg.guards.size(), skeletons, triangles, wg.lod_level, median, p95, costs[costs.size() - 1], str(wg.anim_manual), WallGuards.ANIM_FAR_HZ, anim_mean, anim[int(anim.size() * 0.95)]])
	check(median <= 250 and p95 <= 400, "%s default view: guards' update median %d us p95 %d us (budget 250 / 400)" % [label, median, p95])
	report.append("%s default view: %d/%d on screen, %d skeletons, %d triangles, update median %d us p95 %d us, animation mean %.0f us p95 %d us" % [label, shown, wg.guards.size(), skeletons, triangles, median, p95, anim_mean, anim[int(anim.size() * 0.95)]])
	# Engine side: process time with and without the guards.
	var with_guards := 0.0
	for i in 120:
		wg.present(Time.get_unix_time_from_system())
		await process_frame
		with_guards += Performance.get_monitor(Performance.TIME_PROCESS)
	wg.process_mode = Node.PROCESS_MODE_DISABLED
	wg.visible = false
	var without := 0.0
	for i in 120:
		await process_frame
		without += Performance.get_monitor(Performance.TIME_PROCESS)
	wg.process_mode = Node.PROCESS_MODE_INHERIT
	wg.visible = true
	print("%s process time per frame: %.3f ms with the guards, %.3f ms without" % [label, with_guards / 120.0 * 1000.0, without / 120.0 * 1000.0])
	report.append("%s process %.3f ms with guards, %.3f ms without" % [label, with_guards / 120.0 * 1000.0, without / 120.0 * 1000.0])
	# Close up: LOD1 meshes, sun shadows, the engine's own animation rate.
	var near: Vector3 = wg.guards.filter(func(g): return g.role == "patrol")[0].pos if not wg.guards.filter(func(g): return g.role == "patrol").is_empty() else wg.guards[0].pos
	stage.target = near
	stage.zoom = 30.0
	stage.update_camera(0, true)
	for i in 20:
		wg.present(Time.get_unix_time_from_system())
		await process_frame
	var close_shown: Array = wg.guards.filter(func(g): return g.shown)
	var lod1 := close_shown.filter(func(g): return g.lod_mesh == 1).size()
	var close_tris := 0
	for g in close_shown:
		for mesh in g.meshes:
			if mesh.visible:
				close_tris += mesh_triangles(mesh.mesh)
	print("%s close up (zoom 30): %d on screen, %d with LOD1 meshes, %d source triangles, shadows %s, manual %s" % [label, close_shown.size(), lod1, close_tris, str(wg.cast_real_shadows), str(wg.anim_manual)])
	check(close_shown.size() > 0 and lod1 == close_shown.size(), "%s close up: %d of %d guards on screen with LOD1 meshes" % [label, lod1, close_shown.size()])
	check(wg.cast_real_shadows and not wg.anim_manual, "%s close up: sun shadows on, engine-rate animation" % label)
	report.append("%s close up: %d on screen (LOD1 %d), %d triangles" % [label, close_shown.size(), lod1, close_tris])
	# Far away: nobody on screen, every model and AnimationPlayer off.
	stage.target = Vector3(140, 0, 110)
	stage.zoom = 70.0
	stage.update_camera(0, true)
	for i in 8:
		wg.present(Time.get_unix_time_from_system())
		await process_frame
	var active := 0
	for g in wg.guards:
		if g.node != null and (g.node.visible or g.node.process_mode != Node.PROCESS_MODE_DISABLED):
			active += 1
	check(active == 0, "%s: %d guards still drawn or animated off screen" % [label, active])
	stage.target = Vector3(5, 0, -4)
	stage.update_camera(0, true)

## Level changes while the game runs: the guards re-plan (the models kept), frame by frame.
func replan_checks() -> void:
	var before: int = wg.replans
	var made := count_instanced()
	var nodes := {}
	for g in wg.guards:
		nodes[g.node] = true
	wall_level(4)
	wg.plan_slice_worst = 0
	var started := Time.get_ticks_usec()
	await stage.present_city(game.state)
	var city_ms := (Time.get_ticks_usec() - started) / 1000.0
	var worst := 0.0
	for i in 40:
		stage.present_workers(Time.get_unix_time_from_system())
		worst = maxf(worst, wg.frame_usec / 1000.0)
		await process_frame
	var kept := 0
	for g in wg.guards:
		if nodes.has(g.node):
			kept += 1
	print("  re-plan steps (us): ", wg.plan_profile)
	print("re-plan wall V -> IV: %d re-plans, plan %.2f ms CPU over %d frames (the dearest %.2f ms), %d of %d models kept, %d instanced anew; present_city %.1f ms (the wall itself), guards' worst frame %.2f ms" % [wg.replans - before,
		wg.last_plan_usec / 1000.0, wg.plan_frames, wg.plan_slice_worst / 1000.0, kept, wg.guards.size(), count_instanced() - made, city_ms, worst])
	check(wg.replans > before, "wall V -> IV: the guards did not re-plan")
	check(wg.plan_slice_worst < 4000, "wall V -> IV: a frame of the plan took %.2f ms" % (wg.plan_slice_worst / 1000.0))
	check(wg.plan_frames <= 8, "wall V -> IV: the plan took %d frames" % wg.plan_frames)
	check(worst < 6.0, "wall V -> IV: the guards' whole update (re-plan included) took %.2f ms in a frame" % worst)
	report.append("re-plan V->IV: plan %.2f ms CPU over %d frames (dearest %.2f ms), %d/%d models kept, %d new, guards' worst frame %.2f ms" % [wg.last_plan_usec / 1000.0, wg.plan_frames, wg.plan_slice_worst / 1000.0, kept, wg.guards.size(), count_instanced() - made, worst])
	# The watchtower (SUP-04) built: the wall is the same, the guards are not disturbed.
	var plans: int = wg.replans
	add_building("SUP-04", "v1-16", 2)
	await stage.present_city(game.state)
	for i in 10:
		stage.present_workers(Time.get_unix_time_from_system())
		await process_frame
	print("watchtower built: %d re-plans (the wall bulges round it when it moves the ring), %d guards" % [wg.replans - plans, wg.guards.size()])
	report.append("watchtower built: %d re-plans, %d guards" % [wg.replans - plans, wg.guards.size()])
	wall_level(5)
	await stage.present_city(game.state)
	await wait_guards()

## No wall (hall I, no "walls and gate"): no guards; models hidden.
func no_wall_checks(label: String) -> void:
	var shown := 0
	for g in wg.guards:
		if g.node != null and g.node.visible:
			shown += 1
	var spares := 0
	for unit in wg.spare:
		for node: Node3D in wg.spare[unit]:
			if node.visible:
				spares += 1
	print("%s: wall shown %s, %d guards, %d drawn" % [label, str(stage.walls.visible), wg.guards.size(), shown + spares])
	check(not stage.walls.visible and wg.guards.is_empty() and shown + spares == 0, "%s: guards without a wall (%d)" % [label, wg.guards.size()])
	report.append("%s: walls %s, guards %d" % [label, str(stage.walls.visible), wg.guards.size()])

func run_guards() -> void:
	root.size = Vector2i(1366, 630)
	game = load("res://main.tscn").instantiate()
	game.endpoint = "http://127.0.0.1:9"
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.loopback = true
	game.player_id = "qa-wall-guards"
	var settle_until := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < settle_until:
		await process_frame
	game.smoke = true
	stage = game.stage
	while not stage.attach_townsfolk():
		await process_frame
	tf = stage.townsfolk
	# Hall I, no "walls and gate": no wall, nobody on it.
	await settle("hall I")
	while wg == null:
		stage.present_workers(Time.get_unix_time_from_system())
		wg = stage.wall_guards
		await process_frame
	await settle("hall I")
	await no_wall_checks("hall I, no wall")
	# Wall I (hall II, a bare palisade: no walkway, towers only), wall II and III at hall III,
	# IV at hall IV, V at hall V.
	await guard_scenario("hall II wall I", 2, 0, WallGuards.guards_wanted(2, 1))
	if quick:
		quit(0 if failures == 0 else 1)
		return
	await guard_scenario("hall III wall II", 3, 2, WallGuards.guards_wanted(3, 2))
	await guard_scenario("hall III wall III", 3, 3, WallGuards.guards_wanted(3, 3))
	await guard_scenario("hall IV wall IV", 4, 4, WallGuards.guards_wanted(4, 4))
	await guard_scenario("hall V wall V", 5, 5, WallGuards.guards_wanted(5, 5))
	await guard_cost("hall V wall V")
	await replan_checks()
	# The wall taken away (a test of the rule: hall I, no "walls and gate").
	wall_level(0)
	set_level("ECO-05", 1)
	await settle("back to hall I")
	await no_wall_checks("hall I again")
	print("levels: ", JSON.stringify(levels_report))
	var made: Array = Array(wg.instance_samples)
	made.sort()
	print("guards' worst frame over all level changes %.2f ms; %d models instanced, median %.2f ms, worst %.2f ms" % [guards_worst_frame, made.size(), made[made.size() / 2] / 1000.0, made[-1] / 1000.0])
	check(guards_worst_frame < 20.0, "the guards' worst frame %.2f ms (models coming in, re-plans)" % guards_worst_frame)
	report.append("guards' worst frame %.2f ms; models instanced %d (median %.2f ms, worst %.2f ms)" % [guards_worst_frame, made.size(), made[made.size() / 2] / 1000.0, made[-1] / 1000.0])
	for line in report:
		print(line)
	print("QA_WALL_GUARDS checks=%d failures=%d" % [checks, failures])
	quit(0 if failures == 0 else 1)
