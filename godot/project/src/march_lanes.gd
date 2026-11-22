extends RefCounted

# March lanes (build 1021, presentation only). The server's route is a grid path:
# on the world map 5 m cells that know only the height of the ground, in the city
# cells that keep 5 m from the building plots. Up to build 1020 the column was drawn
# exactly on it, so on the owner's phone it walked through the forest, through the
# houses of the villages, along and into the palisade and across the river with its
# rear rows. Here the drawn route keeps the server's start and end and its general
# course, but each metre of it may step up to CORRIDOR metres aside to pass between
# trees, houses, fences, rocks, the wall (only the gates are open) and the water, as
# wide as the column needs where it can; where it cannot, the column closes up
# (squeeze). The army's timing stays the server's: it covers the drawn route in the
# same time (along_route takes a fraction of it).
#
# The route is cut into stations every STEP metres; at each station the lane may lie
# at one of the lateral offsets 0.5 m (city) or LATERAL (world) apart. A dynamic
# programme picks the cheapest sequence of offsets (clearance from obstacles, distance
# from the server's route, turning), shifting at most MAX_SHIFT offsets per station
# (about 1-2 m sideways per metre). Measured on the server's own routes (qa_march_lanes:
# owner-like city with 16 buildings at level V, world map): samples of the drawn route
# inside an obstacle 0-2 instead of 6-45 on 7 of the 10 city routes; 14 instead of 29
# where two routes leave the home square between level-V buildings whose outlines
# touch, 6 instead of 26 on the longest one. Obstacles
# are discs (tree trunks) and oriented boxes (buildings, rocks, fences, the wall
# footing and its towers) in a hash of HASH-metre cells; water is read from the
# ground. Ferry legs of a city route are kept as they are (the raft carries the army).
# The work is done in slices of SLICE_USEC so a departing march never stalls a frame;
# while its column musters (1.4 s on the server, and the shown clock runs at least
# 1.65 s behind it) in slices of MUSTER_SLICE_USEC, so the lane is there before the
# column sets off (the stage sets slice_usec).

const STEP := 1.0
const LATERAL := 0.75
const HASH := 2.0
const MAX_SHIFT := 3
const SLICE_USEC := 2000
const MUSTER_SLICE_USEC := 6000
var slice_usec := SLICE_USEC
# Tools that render a frame in a second plan in one go (0: the game's slices).
static var slice_override := 0
const FOOTPRINTS := "res://assets/environment/scenery-footprints.json"
# World scenery the soldiers walk over (ground patches, grass, flat stones, a bridge).
const WALKABLE := {"dry_soil": true, "green_plain": true, "sandy_ground": true, "snow_patch": true,
	"stony_ground": true, "marsh_ground": true, "grass_hill": true, "small_hill": true, "farmland": true,
	"fern": true, "grass_tuft": true, "wildflowers": true, "fallen_branches": true, "forest_mushrooms": true,
	"pebbles": true, "flat_stone": true, "tall_reeds": true, "dry_shrub": true, "tiny_stone": true,
	"stone_bridge": true}
# Trunk radius of a tree per unit of its scale (the same as the battle places use).
const TRUNK := 0.24
# Free passage of the B18 gate scenes at scale 1 (measured from the meshes: the
# ground slab 0.3-2.2 m is empty for |x| < 1.25; the scene spans |x| < 5.6, |z| < 6.4).
const GATE_PASSAGE := 1.25
const GATE_SPAN := Vector2(5.6, 6.4)
# Costs per metre of lane.
const BLOCKED := 10000.0
const W_CLEAR := 3.0
const W_OFFSET := 0.12
const W_TURN := 0.25
const W_WATER := 40.0

static var footprints := {}

var stage
var disc_c := PackedVector2Array()
var disc_r := PackedFloat32Array()
var box_c := PackedVector2Array()
var box_h := PackedVector2Array()
var box_axis := PackedVector2Array()
var cells := {}
var signature := ""
var slice_end := 0
# Diagnostics of the last plan (QA, debug overlay).
var last := {}

# Set when the scene went away while a plan waited for the next frame (a switch to the
# other map on the phone frees the scene): the plan stops and nothing is drawn from it.
var aborted := false

func pause() -> void:
	if Time.get_ticks_usec() < slice_end:
		return
	if not is_instance_valid(stage) or not stage.is_inside_tree():
		aborted = true
		return
	await stage.get_tree().process_frame
	if not is_instance_valid(stage) or not stage.is_inside_tree():
		aborted = true
	slice_end = Time.get_ticks_usec() + (slice_override if slice_override > 0 else slice_usec)

func clear() -> void:
	disc_c.clear(); disc_r.clear(); box_c.clear(); box_h.clear(); box_axis.clear(); cells.clear()

func insert(code: int, centre: Vector2, reach: float) -> void:
	var x0 := floori((centre.x - reach) / HASH)
	var x1 := floori((centre.x + reach) / HASH)
	var z0 := floori((centre.y - reach) / HASH)
	var z1 := floori((centre.y + reach) / HASH)
	for cz in range(z0, z1 + 1):
		for cx in range(x0, x1 + 1):
			var key := Vector2i(cx, cz)
			if not cells.has(key):
				cells[key] = PackedInt32Array()
			cells[key].append(code)

func add_disc(centre: Vector2, radius: float) -> void:
	disc_c.append(centre)
	disc_r.append(radius)
	insert(disc_c.size() - 1, centre, radius)

# An oriented box: centre, half extents along its own axes, `axis` = its local x
# direction on the ground (unit vector).
func add_box(centre: Vector2, half: Vector2, axis: Vector2) -> void:
	box_c.append(centre)
	box_h.append(half)
	box_axis.append(axis.normalized() if axis.length_squared() > 0.0 else Vector2.RIGHT)
	insert(-box_c.size(), centre, half.length())

func add_transformed_box(xform: Transform3D, local_centre: Vector2, local_half: Vector2) -> void:
	var c := xform * Vector3(local_centre.x, 0.0, local_centre.y)
	var ax := xform.basis.x
	var az := xform.basis.z
	var half := Vector2(local_half.x * Vector2(ax.x, ax.z).length(), local_half.y * Vector2(az.x, az.z).length())
	add_box(Vector2(c.x, c.z), half, Vector2(ax.x, ax.z))

static func footprint_table() -> Dictionary:
	if footprints.is_empty() and FileAccess.file_exists(FOOTPRINTS):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FOOTPRINTS))
		if parsed is Dictionary:
			footprints = parsed
	return footprints

# The obstacle tables of the stage; rebuilt when the city's buildings, wall or trees change.
func prepare(owner) -> void:
	stage = owner
	aborted = false
	var key := "world" if stage.map_name == "world" else "%d/%d/%s" % [stage.vegetation_rebuilds, stage.town_rebuilds, stage.walls.signature]
	if key == signature:
		return
	slice_end = Time.get_ticks_usec() + slice_usec
	clear()
	var table := footprint_table()
	if stage.map_name == "world":
		var counted := 0
		for item in stage.data.environment:
			counted += 1
			if counted % 32 == 0:
				await pause()
				if aborted:
					signature = ""
					return
			var id := str(item.id)
			var spec: Dictionary = stage.data.environmentModels.get(id, {})
			var scale := float(item.scale)
			if spec.get("tree", false):
				add_disc(Vector2(float(item.x), float(item.z)), TRUNK * scale)
				continue
			if WALKABLE.has(id) or not table.has(id):
				continue
			var f: Array = table[id]
			var xform := Transform3D(Basis(Vector3.UP, float(item.rotation)).scaled(Vector3.ONE * scale), Vector3(float(item.x), 0.0, float(item.z)))
			add_transformed_box(xform, Vector2(float(f[0]), float(f[1])), Vector2(float(f[2]), float(f[3])))
		for site in stage.data.sites:
			for part in site.parts:
				var f: Array = table.get("site:" + str(part.key), [])
				if f.is_empty():
					continue
				var xform := Transform3D(Basis(Vector3.UP, float(part.rotation)).scaled(Vector3.ONE * float(part.scale)), Vector3(float(part.x), 0.0, float(part.z)))
				# The walls of a house, not its eaves: 80 % of the model's outline.
				add_transformed_box(xform, Vector2(float(f[0]), float(f[1])), Vector2(float(f[2]), float(f[3])) * 0.8)
	else:
		for cell in stage.standing_tree_cells:
			await pause()
			if aborted:
				signature = ""
				return
			for tree: Vector2 in stage.standing_tree_cells[cell]:
				add_disc(tree, 0.4)
		for lot: Dictionary in stage.town_plan.lots:
			var body: Rect2 = lot.body
			add_box(body.get_center(), body.size * 0.5 + Vector2(0.2, 0.2), Vector2.RIGHT)
		await pause()
		if aborted:
			signature = ""
			return
		add_wall()
	signature = key

# The wall's footing and towers as they are drawn (city_walls.gd parts), and the
# two wings of the main gate scene around its passage.
func add_wall() -> void:
	var walls = stage.walls
	if not walls.visible or not is_instance_valid(walls.node):
		return
	for part in walls.node.get_children():
		var label := String(part.name)
		if not (label == "footing" or label == "tower_footing" or label == "tower_base_stone"):
			continue
		var multi: MultiMesh = (part as MultiMeshInstance3D).multimesh
		var bounds: AABB = multi.mesh.get_aabb()
		var local_centre := Vector2(bounds.get_center().x, bounds.get_center().z)
		var local_half := Vector2(bounds.size.x, bounds.size.z) * 0.5
		for i in multi.instance_count:
			add_transformed_box(part.global_transform * multi.get_instance_transform(i), local_centre, local_half)
	var gate: Node3D = stage.gate_node
	if walls.custom_main_gate and is_instance_valid(gate):
		var box := AABB()
		var first := true
		for mesh: MeshInstance3D in gate.find_children("*", "MeshInstance3D", true, false):
			if mesh.mesh == null:
				continue
			var b: AABB = gate.global_transform.affine_inverse() * mesh.global_transform * mesh.get_aabb()
			box = b if first else box.merge(b)
			first = false
		if not first:
			var half := Vector2(box.size.x, box.size.z) * 0.5
			var centre := Vector2(box.get_center().x, box.get_center().z)
			var passage := half.x * GATE_PASSAGE / GATE_SPAN.x
			var wing := (half.x - passage) * 0.5
			for side in [-1.0, 1.0]:
				add_transformed_box(gate.global_transform, centre + Vector2(side * (passage + wing), 0.0), Vector2(wing, half.y))

# Distance from q to the nearest obstacle, at most `cap` (0 on water in the city).
func clearance(q: Vector2, cap: float) -> float:
	var best := cap
	var x0 := floori((q.x - cap) / HASH)
	var x1 := floori((q.x + cap) / HASH)
	var z0 := floori((q.y - cap) / HASH)
	var z1 := floori((q.y + cap) / HASH)
	for cz in range(z0, z1 + 1):
		for cx in range(x0, x1 + 1):
			var list: Variant = cells.get(Vector2i(cx, cz))
			if list == null:
				continue
			for code: int in list:
				var d: float
				if code >= 0:
					d = q.distance_to(disc_c[code]) - disc_r[code]
				else:
					var k := -code - 1
					var rel: Vector2 = q - box_c[k]
					var axis: Vector2 = box_axis[k]
					var local := Vector2(absf(rel.dot(axis)), absf(rel.dot(Vector2(-axis.y, axis.x)))) - box_h[k]
					d = Vector2(maxf(local.x, 0.0), maxf(local.y, 0.0)).length() + minf(maxf(local.x, local.y), 0.0)
				if d < best:
					best = d
	return maxf(best, 0.0)

func wet(q: Vector2) -> bool:
	return not stage.dry_ground(Vector3(q.x, 0.0, q.y))

# A lane for `points` (the route as drawn so far, with its ferry legs flagged).
# `half_width`: half the column's width (largest |side| plus a soldier); `body`: a
# soldier's radius. Returns {points, ferry, clearance (per STEP metre of the lane),
# moved (largest offset)} or {} when the server's route is kept.
func plan(owner, points: PackedVector3Array, ferry: PackedByteArray, half_width: float, body: float, corridor: float) -> Dictionary:
	await prepare(owner)
	slice_end = Time.get_ticks_usec() + slice_usec
	if aborted or points.size() < 2:
		return {}
	var given := 0.0
	for i in range(1, points.size()):
		given += Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length()
	var out_points := PackedVector3Array()
	var out_ferry := PackedByteArray()
	var start := 0
	var moved := 0.0
	var reference := 0.0
	for i in range(1, points.size()):
		reference += Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length()
	# Dry stretches between ferry legs; a ferry leg is copied as it is.
	var k := 1
	while k <= points.size():
		var leg := k < points.size() and ferry.size() > k and ferry[k] == 1
		if k == points.size() or leg:
			var stretch := points.slice(start, k)
			var lane: Dictionary = await plan_stretch(stretch, half_width, body, corridor)
			if aborted:
				return {}
			var drawn: PackedVector3Array = lane.get("points", stretch)
			moved = maxf(moved, float(lane.get("moved", 0.0)))
			for n in drawn.size():
				if not out_points.is_empty() and n == 0 and out_points[-1].is_equal_approx(drawn[0]):
					continue
				out_points.append(drawn[n])
				out_ferry.append(0)
			if leg:
				out_points.append(points[k])
				out_ferry.append(1)
				start = k
		k += 1
	var length := 0.0
	for i in range(1, out_points.size()):
		length += Vector2(out_points[i].x - out_points[i - 1].x, out_points[i].z - out_points[i - 1].z).length()
	# Each row walks this far in the same time: a much longer lane would hurry the army.
	if length > given * 1.3 + 4.0:
		last = {"kept": "detour", "reference": given, "length": length}
		return {}
	var profile := PackedFloat32Array()
	var cap := half_width + 0.5
	var walked := 0.0
	var i := 1
	while i < out_points.size():
		var a := Vector2(out_points[i - 1].x, out_points[i - 1].z)
		var b := Vector2(out_points[i].x, out_points[i].z)
		var span := a.distance_to(b)
		while walked <= span and span > 0.0:
			var q := a.lerp(b, walked / span)
			profile.append(cap if out_ferry[i] == 1 else clearance(q, cap))
			walked += STEP
		walked -= span
		i += 1
		await pause()
		if aborted:
			return {}
	profile.append(cap)
	last = {"reference": given, "length": length, "moved": moved, "stations": profile.size()}
	return {"points": out_points, "ferry": out_ferry, "clearance": profile, "moved": moved, "length": length}

# One dry stretch: stations along the route, lateral offsets, cheapest sequence.
func plan_stretch(route: PackedVector3Array, half_width: float, body: float, corridor: float) -> Dictionary:
	var total := 0.0
	var marks := PackedFloat32Array([0.0])
	for i in range(1, route.size()):
		total += Vector2(route[i].x - route[i - 1].x, route[i].z - route[i - 1].z).length()
		marks.append(total)
	if total < STEP * 3.0:
		return {}
	var count := int(ceil(total / STEP)) + 1
	var stations := PackedVector2Array()
	for s in count:
		stations.append(at_distance(route, marks, minf(s * STEP, total)))
	# Smoothed directions (the grid route turns in 45-degree steps).
	var normals := PackedVector2Array()
	var reach := PackedFloat32Array()
	for s in count:
		var ahead := stations[mini(s + 3, count - 1)] - stations[maxi(s - 3, 0)]
		var t := ahead.normalized() if ahead.length_squared() > 0.0001 else Vector2.RIGHT
		normals.append(Vector2(-t.y, t.x))
	# The lane may not swing wider than the route's own turn allows (no loops on the
	# inner side of a corner): the offset stays within 0.8 of the local turn radius.
	for s in count:
		var before := normals[maxi(s - 2, 0)]
		var after := normals[mini(s + 2, count - 1)]
		var turn := absf(before.angle_to(after))
		var radius := (4.0 * STEP) / maxf(turn, 0.001)
		reach.append(minf(corridor, radius * 0.8))
	# Finer between the town's buildings, coarser on the open world map.
	var lateral := 0.5 if stage.map_name == "city" else LATERAL
	var lanes := int(round(corridor / lateral)) * 2 + 1
	var middle := lanes / 2
	var cap := half_width + 0.5
	var costs := PackedFloat32Array()
	costs.resize(count * lanes)
	for s in count:
		var side_sign := signf(normals[maxi(s - 2, 0)].cross(normals[mini(s + 2, count - 1)]))
		for j in lanes:
			var d := (j - middle) * lateral
			var cost := 0.0
			# Inner side of a turn beyond the turn radius: not allowed.
			if absf(d) > reach[s] + 0.001 and signf(d) == -side_sign and side_sign != 0.0:
				cost = BLOCKED
			elif absf(d) > corridor + 0.001:
				cost = BLOCKED
			else:
				var q := stations[s] + normals[s] * d
				var c := clearance(q, cap)
				var endpoint := s == 0 or s == count - 1
				if c < body and not endpoint:
					cost = BLOCKED
				else:
					cost = W_CLEAR * pow(maxf(0.0, half_width - c), 2.0) + W_OFFSET * absf(d)
				if wet(q) and not endpoint:
					cost += BLOCKED if stage.map_name == "city" else W_WATER
			costs[s * lanes + j] = cost
		await pause()
		if aborted:
			return {}
	# The lane starts and ends on the server's route.
	var best := PackedFloat32Array()
	best.resize(count * lanes)
	best.fill(INF)
	var from := PackedInt32Array()
	from.resize(count * lanes)
	best[middle] = costs[middle]
	for s in range(1, count):
		for j in lanes:
			var here := costs[s * lanes + j]
			var choice := -1
			var value := INF
			for shift in range(-MAX_SHIFT, MAX_SHIFT + 1):
				var p := j + shift
				if p < 0 or p >= lanes:
					continue
				var v := best[(s - 1) * lanes + p] + W_TURN * absf(shift)
				if v < value:
					value = v
					choice = p
			best[s * lanes + j] = value + here
			from[s * lanes + j] = choice
		if s % 8 == 0:
			await pause()
			if aborted:
				return {}
	var end := (count - 1) * lanes + middle
	if best[end] >= BLOCKED:
		# Somewhere nothing is free within the corridor: keep the server's route there.
		last = {"kept": "blocked"}
	var offsets := PackedFloat32Array()
	offsets.resize(count)
	var j := middle
	for s in range(count - 1, -1, -1):
		offsets[s] = (j - middle) * lateral
		if s > 0:
			j = from[s * lanes + j]
	# A light smoothing of the offsets (never onto an obstacle).
	var smooth := offsets.duplicate()
	for s in range(1, count - 1):
		var v := (offsets[s - 1] + offsets[s] * 2.0 + offsets[s + 1]) * 0.25
		var q := stations[s] + normals[s] * v
		if clearance(q, body + 0.01) >= body:
			smooth[s] = v
	var moved := 0.0
	var lane := PackedVector3Array()
	for s in count:
		var q := stations[s] + normals[s] * smooth[s]
		moved = maxf(moved, absf(smooth[s]))
		lane.append(Vector3(q.x, 0.0, q.y))
	lane[0] = route[0]
	lane[count - 1] = route[route.size() - 1]
	return {"points": simplify(lane, 0.06), "moved": moved}

static func at_distance(route: PackedVector3Array, marks: PackedFloat32Array, at: float) -> Vector2:
	var i := clampi(marks.bsearch(at), 1, marks.size() - 1)
	var span := marks[i] - marks[i - 1]
	var w := (at - marks[i - 1]) / span if span > 0.0 else 0.0
	var p := route[i - 1].lerp(route[i], w)
	return Vector2(p.x, p.z)

# Drops points that lie within `tolerance` of the straight line of their neighbours.
static func simplify(points: PackedVector3Array, tolerance: float) -> PackedVector3Array:
	if points.size() < 3:
		return points
	var kept := PackedVector3Array([points[0]])
	var anchor := 0
	for i in range(1, points.size() - 1):
		var a := Vector2(points[anchor].x, points[anchor].z)
		var b := Vector2(points[i + 1].x, points[i + 1].z)
		var worst := 0.0
		for k in range(anchor + 1, i + 1):
			var q := Vector2(points[k].x, points[k].z)
			worst = maxf(worst, q.distance_to(Geometry2D.get_closest_point_to_segment(q, a, b)))
		if worst > tolerance:
			kept.append(points[i])
			anchor = i
	kept.append(points[-1])
	return kept

# How far a row of the column may spread across at `at` metres along the lane:
# 1 = as formed, less where the lane passes close to an obstacle.
static func squeeze(lane: Dictionary, at: float, half_width: float, body: float) -> float:
	var profile: PackedFloat32Array = lane.get("clearance", PackedFloat32Array())
	if profile.is_empty() or half_width <= body:
		return 1.0
	var f := clampf(at / STEP, 0.0, profile.size() - 1.0)
	var i := floori(f)
	var c := lerpf(profile[i], profile[mini(i + 1, profile.size() - 1)], f - i)
	return clampf((c - body) / maxf(0.01, half_width - body), 0.15, 1.0)
