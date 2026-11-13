extends RefCounted

# Perimeter wall of the settlement: a timber palisade on a stone footing with a
# walkway, pointed log tops, square towers with pyramid roofs, banners and gate
# houses where the roads leave the yard.
#
# The yard (the area inside the wall) grows with the town hall: every hall level
# moves the wall outward, so more plots fall inside and can be built on. The wall
# never cuts through a building, a construction site or the troop base: around
# them it bulges outward. Over the river it pulls back to the bank.
#
# Everything is drawn with a few MultiMesh batches (one draw call per part), so the
# whole ring costs about a dozen draw calls. The plan depends only on the city
# state; plan() returns a signature and the geometry is rebuilt only when it
# changes.

const SAMPLES := 144
# Half extent of the yard by town hall level (metres from the yard centre).
const YARD_BY_HALL := {1: 31.0, 2: 37.0, 3: 44.0, 4: 51.0, 5: 58.0}
const SHAPE_POWER := 2.6
const ASPECT_X := 1.1
const BUILDING_CLEARANCE := 12.0
const DISTRICT_CLEARANCE := 4.5
# Cleared strip along the wall (no trees, bushes or grass): inside and outside.
const BAND_INSIDE := 3.6
const BAND_OUTSIDE := 8.0
const TOWER_SPACING := 24.0
const GATE_HALF := 2
const WALL_FROM_HALL := 2
const TEXTURES := "res://assets/city/premium/surfaces07/"

var center := Vector2.ZERO
var radii := PackedFloat32Array()
var required := PackedFloat32Array()
var visible := false
var hall_level := 1
var wall_level := 1
var gates: Array[int] = []
var gate_roads: Array = []
var main_gate := Vector3.ZERO
var main_gate_outward := Vector3.BACK
# When the "walls and gate" level scene stands in the main gate, the ring leaves an
# opening of main_gate_span metres each side and draws no gate house of its own there.
var custom_main_gate := false
var main_gate_span := 0.0
var main_gate_half := GATE_HALF
var signature := ""
var tower_count := 0
var node: Node3D
var height_at: Callable

static func yard_extent(level: int) -> float:
	return float(YARD_BY_HALL.get(clampi(level, 1, 5), 31.0))

func angle_of(i: int) -> float:
	return TAU * float(i) / SAMPLES

func direction(i: int) -> Vector2:
	var a := angle_of(i)
	return Vector2(cos(a), sin(a))

func base_radius(i: int, half: float) -> float:
	var d := direction(i)
	var cx := absf(d.x) / ASPECT_X
	var cz := absf(d.y)
	return half / pow(pow(cx, SHAPE_POWER) + pow(cz, SHAPE_POWER), 1.0 / SHAPE_POWER)

func sample_index(x: float, z: float) -> float:
	var a := fposmod(atan2(z - center.y, x - center.x), TAU)
	return a / TAU * SAMPLES

func radius_at(x: float, z: float) -> float:
	if radii.is_empty():
		return INF
	var f := sample_index(x, z)
	var i := int(floor(f)) % SAMPLES
	return lerpf(radii[i], radii[(i + 1) % SAMPLES], f - floor(f))

func wall_point(i: int) -> Vector2:
	return center + direction(i % SAMPLES) * radii[i % SAMPLES]

# Inside the yard with a margin (metres) from the wall line.
func inside(x: float, z: float, margin := 0.0) -> bool:
	return Vector2(x, z).distance_to(center) <= radius_at(x, z) - margin

# On the wall band or a gate road: no trees, bushes or grass tufts there.
func blocks(x: float, z: float) -> bool:
	if not visible:
		return false
	var offset := Vector2(x, z).distance_to(center) - radius_at(x, z)
	if offset > -BAND_INSIDE and offset < BAND_OUTSIDE:
		return true
	for road in gate_roads:
		var p := Vector2(x, z)
		var near := Geometry2D.get_closest_point_to_segment(p, road[0], road[1])
		if p.distance_squared_to(near) < 6.25:
			return true
	return false

# Width and depth of the yard (metres) and the average distance to the wall.
func yard_size() -> Vector2:
	if radii.is_empty():
		return Vector2.ZERO
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for i in SAMPLES:
		var p := wall_point(i)
		low = low.min(p)
		high = high.max(p)
	return high - low

func gate_half(gate_index: int) -> int:
	return main_gate_half if gate_index == 0 else GATE_HALF

func is_gate_segment(i: int) -> bool:
	for k in gates.size():
		var h := gate_half(k)
		var offset := posmod(i - gates[k] + h, SAMPLES)
		if offset < h * 2:
			return true
	return false

# obstacles: Array of [Vector2 position, float clearance]
func plan(hall_position: Vector2, level: int, defence_level: int, show_wall: bool, obstacles: Array, district: Variant, heights: Callable) -> String:
	hall_level = level
	wall_level = maxi(1, defence_level)
	visible = show_wall
	height_at = heights
	center = hall_position + Vector2(0.0, 5.0)
	var half := yard_extent(level)
	var points: Array = obstacles.duplicate()
	if district is Dictionary:
		var dc := Vector2(float(district.x), float(district.z))
		var hw := float(district.get("halfWidth", 14.0)) + 1.7
		var hd := float(district.get("halfDepth", 11.0)) + 1.7
		var step := 3.0
		var x := -hw
		while x <= hw:
			points.append([dc + Vector2(x, -hd), DISTRICT_CLEARANCE])
			points.append([dc + Vector2(x, hd), DISTRICT_CLEARANCE])
			x += step
		var z := -hd
		while z <= hd:
			points.append([dc + Vector2(-hw, z), DISTRICT_CLEARANCE])
			points.append([dc + Vector2(hw, z), DISTRICT_CLEARANCE])
			z += step
	radii.resize(SAMPLES)
	required.resize(SAMPLES)
	for i in SAMPLES:
		radii[i] = base_radius(i, half)
		required[i] = 0.0
	for entry in points:
		var p: Vector2 = entry[0]
		var clearance: float = entry[1]
		var offset := p - center
		var distance := offset.length()
		var need := distance + clearance
		var spread := PI if distance <= clearance else asin(clearance / distance)
		var mid := fposmod(atan2(offset.y, offset.x), TAU) / TAU * SAMPLES
		var reach := int(ceil(spread / TAU * SAMPLES))
		for k in range(-reach, reach + 1):
			var i := posmod(int(round(mid)) + k, SAMPLES)
			required[i] = maxf(required[i], need)
	for i in SAMPLES:
		radii[i] = maxf(radii[i], required[i])
	# Soften the bulges: a widening pass, then two averaging passes.
	var widened := PackedFloat32Array()
	widened.resize(SAMPLES)
	for i in SAMPLES:
		var top := 0.0
		for k in range(-3, 4):
			top = maxf(top, radii[posmod(i + k, SAMPLES)])
		widened[i] = top
	radii = widened
	for _pass in 2:
		var smooth := PackedFloat32Array()
		smooth.resize(SAMPLES)
		for i in SAMPLES:
			var sum := 0.0
			for k in range(-4, 5):
				sum += radii[posmod(i + k, SAMPLES)]
			smooth[i] = maxf(sum / 9.0, required[i])
		radii = smooth
	# The river: pull the line back to dry ground.
	for i in SAMPLES:
		var d := direction(i)
		var r := radii[i]
		var floor_r := maxf(required[i], half * 0.6)
		while r > floor_r and float(heights.call(center.x + d.x * r, center.y + d.y * r)) < -0.25:
			r -= 1.0
		radii[i] = r
	# Even out the dents at the river bank, never stepping back onto the water.
	var dry := radii.duplicate()
	for _pass in 2:
		var eased := PackedFloat32Array()
		eased.resize(SAMPLES)
		for i in SAMPLES:
			var low := INF
			for k in range(-2, 3):
				low = minf(low, radii[posmod(i + k, SAMPLES)])
			var sum := 0.0
			for k in range(-3, 4):
				sum += radii[posmod(i + k, SAMPLES)]
			eased[i] = minf(dry[i], maxf(required[i], (low + sum / 7.0) * 0.5))
		radii = eased
	plan_gates(obstacles, district)
	var parts: Array = [visible, wall_level, Array(gates), custom_main_gate, main_gate_half]
	for i in range(0, SAMPLES, 3):
		parts.append(snappedf(radii[i], 0.1))
	signature = JSON.stringify(parts)
	return signature

func plan_gates(obstacles: Array, district: Variant) -> void:
	gates.clear()
	gate_roads.clear()
	# The main gate faces the default camera (+x+z, the bottom of the screen); side
	# gates open to the left and right of the screen from hall level 3, and the far
	# side from level 5.
	var wanted: Array = [PI * 0.25]
	if hall_level >= 3:
		wanted.append_array([PI * 1.75, PI * 0.75])
	if hall_level >= 5:
		wanted.append(PI * 1.25)
	for angle in wanted:
		var ideal := int(round(angle / TAU * SAMPLES)) % SAMPLES
		var chosen := -1
		for shift in [0, 2, -2, 4, -4, 6, -6, 8, -8, 10, -10]:
			var i := posmod(ideal + shift, SAMPLES)
			if gate_blocked(i, obstacles, district):
				continue
			chosen = i
			break
		if chosen >= 0:
			gates.append(chosen)
	if gates.is_empty():
		gates.append(int(round(0.25 * SAMPLES)))
	var g := gates[0]
	main_gate_half = GATE_HALF
	if custom_main_gate and main_gate_span > 0.0:
		var step := wall_point(g).distance_to(wall_point(g + 1))
		main_gate_half = maxi(GATE_HALF, ceili(main_gate_span / maxf(step, 0.5)))
	var at := wall_point(g)
	var outward := direction(g)
	main_gate = Vector3(at.x, float(height_at.call(at.x, at.y)), at.y)
	main_gate_outward = Vector3(outward.x, 0.0, outward.y)
	for gate in gates:
		var p := wall_point(gate)
		var d := direction(gate)
		gate_roads.append([p - d * 7.0, p + d * 16.0])

func gate_blocked(i: int, obstacles: Array, district: Variant) -> bool:
	var p := wall_point(i)
	var outside := p + direction(i) * 10.0
	if float(height_at.call(p.x, p.y)) < -0.1 or float(height_at.call(outside.x, outside.y)) < -0.1:
		return true
	if district is Dictionary:
		var rect := Rect2(float(district.x) - 18.0, float(district.z) - 15.0, 36.0, 30.0)
		if rect.has_point(p) or rect.has_point(outside):
			return true
	for entry in obstacles:
		if (entry[0] as Vector2).distance_to(p) < 9.0:
			return true
	# Steep ground does not suit a gate.
	var a := wall_point(i - GATE_HALF)
	var b := wall_point(i + GATE_HALF)
	return absf(float(height_at.call(a.x, a.y)) - float(height_at.call(b.x, b.y))) > 2.2

# ---------------------------------------------------------------- geometry

func material(key: String, tint: Color, scale: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(TEXTURES + key + "-albedo.jpg")
	m.normal_enabled = true
	m.normal_texture = load(TEXTURES + key + "-normal.png")
	m.roughness_texture = load(TEXTURES + key + "-roughness.png")
	m.albedo_color = tint
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE * scale
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m

func flat(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.85
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m

func batch(parent: Node3D, label: String, mesh: Mesh, surface: Material, transforms: Array) -> void:
	if transforms.is_empty():
		return
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = mesh
	multimesh.instance_count = transforms.size()
	for i in transforms.size():
		multimesh.set_instance_transform(i, transforms[i])
	var instance := MultiMeshInstance3D.new()
	instance.name = label
	instance.multimesh = multimesh
	instance.material_override = surface
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	parent.add_child(instance)

func ground(p: Vector2) -> Vector3:
	return Vector3(p.x, float(height_at.call(p.x, p.y)), p.y)

# A box spanning a to b (wall direction, following the slope), with the given
# height above `bottom` and thickness across, shifted `inward` towards the yard.
func span(a: Vector3, b: Vector3, bottom: float, height: float, thickness: float, inward: float, extra := 0.0) -> Transform3D:
	var along := b - a
	var flat_along := Vector3(along.x, 0.0, along.z)
	var across := flat_along.cross(Vector3.UP).normalized()
	var to_center := Vector3(center.x, 0.0, center.y) - (a + b) * 0.5
	to_center.y = 0.0
	if across.dot(to_center) < 0.0:
		across = -across
	var length := along.length() + extra
	var basis := Basis(along.normalized() * length, Vector3.UP * height, across * thickness)
	var origin := (a + b) * 0.5 + Vector3.UP * (bottom + height * 0.5) + across * inward
	return Transform3D(basis, origin)

# Look of the wall by the level of "walls and gate" (0 = palisade of town hall II):
# timber up to level 2, stone towers from level 3, a stone curtain at level 5.
static func tier(level: int) -> String:
	if level >= 5:
		return "stone"
	if level >= 3:
		return "towers"
	return "timber"

func put(parts: Dictionary, key: String, mesh: String, surface: String, transform_value: Transform3D, xform: Transform3D) -> void:
	if not parts.has(key):
		parts[key] = {"mesh": mesh, "material": surface, "transforms": []}
	parts[key].transforms.append(xform * transform_value)

# Adds this wall to `parts` (one batch per part and material), moved by `xform`.
func collect(parts: Dictionary, xform := Transform3D.IDENTITY) -> void:
	tower_count = 0
	if not visible or radii.is_empty():
		return
	var look := tier(wall_level)
	var curtain := "stone_wall" if look == "stone" else "planks"
	var wall_height := 4.4 + 0.3 * (wall_level - 1) + (0.8 if look == "stone" else 0.0)
	var footing_height := 1.3
	var points: Array = []
	for i in SAMPLES:
		points.append(ground(wall_point(i)))
	for i in SAMPLES:
		if is_gate_segment(i):
			continue
		var a: Vector3 = points[i]
		var b: Vector3 = points[(i + 1) % SAMPLES]
		put(parts, "footing", "box", "stone", span(a, b, -2.6, 2.6 + footing_height, 1.9, 0.0, 0.25), xform)
		put(parts, "curtain_" + curtain, "box", curtain, span(a, b, footing_height - 0.05, wall_height, 0.9 if look == "stone" else 0.75, 0.0, 0.08), xform)
		put(parts, "walkway", "box", "timber", span(a, b, footing_height + wall_height - 0.95, 0.22, 1.5, 1.05, 0.05), xform)
		put(parts, "rail", "box", "timber", span(a, b, footing_height + wall_height - 0.05, 0.12, 0.12, 1.7, 0.05), xform)
		var along := b - a
		var across := span(a, b, 0.0, 1.0, 1.0, 0.0).basis.z.normalized()
		if look == "stone":
			# Battlements: merlons along the top of the stone curtain.
			var merlons := maxi(1, int(along.length() / 1.1))
			for k in merlons:
				var t := (k + 0.5) / merlons
				var p := a.lerp(b, t) + Vector3.UP * (footing_height + wall_height + 0.4)
				put(parts, "merlons", "box", "stone_wall", Transform3D(Basis(along.normalized() * 0.6, Vector3.UP * 0.8, across * 0.9), p), xform)
		else:
			# Pointed log tips along the top of the palisade.
			var count := maxi(1, int(along.length() / 0.5))
			for k in count:
				var t := (k + 0.5) / count
				var p := a.lerp(b, t) + Vector3.UP * (footing_height + wall_height + 0.28)
				put(parts, "spikes", "prism", "planks", Transform3D(Basis(along.normalized() * 0.42, Vector3.UP * 0.56, across * 0.5), p - across * 0.12), xform)
	if look != "stone":
		# Upright logs on the outer face at every sample.
		for i in SAMPLES:
			if is_gate_segment(i) and is_gate_segment(i - 1):
				continue
			var p: Vector3 = points[i]
			var out := Vector3(p.x - center.x, 0.0, p.z - center.y).normalized()
			put(parts, "posts", "log", "planks", Transform3D(Basis.IDENTITY.scaled(Vector3(0.62, wall_height + 0.9, 0.62)),
				p + Vector3.UP * (footing_height + (wall_height + 0.9) * 0.5 - 0.3) + out * 0.42), xform)
	collect_towers(parts, xform, points, wall_height, footing_height, look)

func build(parent: Node3D) -> void:
	if is_instance_valid(node):
		node.free()
	node = null
	var parts := {}
	collect(parts)
	if parts.is_empty():
		return
	node = Node3D.new()
	node.name = "CityWalls"
	parent.add_child(node)
	emit(node, parts)

static var shared_surfaces := {}

func surfaces() -> Dictionary:
	if shared_surfaces.is_empty():
		shared_surfaces = {
			"stone": material("stone", Color("#b9b3a6"), 0.32),
			"stone_wall": material("stone", Color("#bfb6a6"), 0.24),
			"planks": material("dark_oak", Color("#a77a55"), 0.42),
			"timber": material("oak", Color("#c49a6c"), 0.5),
			"roof": material("slate", Color("#4f8f86"), 0.45),
			"banner": flat(Color("#2f4f8f")),
			"trim": flat(Color("#d9b45c")),
		}
	return shared_surfaces

func meshes() -> Dictionary:
	var log_mesh := CylinderMesh.new()
	log_mesh.top_radius = 0.5
	log_mesh.bottom_radius = 0.5
	log_mesh.height = 1.0
	log_mesh.radial_segments = 8
	log_mesh.rings = 1
	var prism := PrismMesh.new()
	prism.size = Vector3.ONE
	var pyramid := CylinderMesh.new()
	pyramid.top_radius = 0.0
	pyramid.bottom_radius = 3.3
	pyramid.height = 2.9
	pyramid.radial_segments = 4
	pyramid.rings = 1
	return {"box": BoxMesh.new(), "log": log_mesh, "prism": prism, "pyramid": pyramid}

func emit(parent: Node3D, parts: Dictionary) -> void:
	var surface_set := surfaces()
	var mesh_set := meshes()
	var keys := parts.keys()
	keys.sort()
	for key in keys:
		var part: Dictionary = parts[key]
		batch(parent, str(key), mesh_set[part.mesh], surface_set[part.material], part.transforms)

func tower_at(parts: Dictionary, xform: Transform3D, p: Vector3, out: Vector3, size: float, height: float, footing_height: float, look: String) -> void:
	var yaw := atan2(out.x, out.z)
	var turn := Basis(Vector3.UP, yaw)
	var body := "planks" if look == "timber" else "stone_wall"
	put(parts, "tower_footing", "box", "stone", Transform3D(turn.scaled(Vector3(size + 0.8, 3.6 + footing_height, size + 0.8)), p + Vector3.UP * (footing_height - 2.6 + (3.6 + footing_height) * 0.5 - footing_height)), xform)
	put(parts, "tower_body_" + body, "box", body, Transform3D(turn.scaled(Vector3(size, height, size)), p + Vector3.UP * (footing_height + height * 0.5)), xform)
	var deck := footing_height + height
	put(parts, "tower_deck", "box", "timber", Transform3D(turn.scaled(Vector3(size + 0.9, 0.35, size + 0.9)), p + Vector3.UP * (deck + 0.17)), xform)
	for corner in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(-1, 0, 1), Vector3(1, 0, 1)]:
		var c: Vector3 = turn * (corner * (size * 0.5 + 0.25))
		put(parts, "tower_pillars", "box", "timber", Transform3D(Basis.IDENTITY.scaled(Vector3(0.3, 1.9, 0.3)), p + c + Vector3.UP * (deck + 1.25)), xform)
	var roof_scale := size / 3.2
	put(parts, "tower_roofs", "pyramid", "roof", Transform3D((turn * Basis(Vector3.UP, PI * 0.25)).scaled(Vector3(roof_scale, roof_scale, roof_scale)), p + Vector3.UP * (deck + 2.5 + 1.45 * roof_scale)), xform)
	put(parts, "banners", "box", "banner", Transform3D(turn.scaled(Vector3(1.6, 3.0, 0.08)), p + Vector3.UP * (deck - 2.2) + out * (size * 0.5 + 0.06)), xform)
	put(parts, "banner_trim", "box", "trim", Transform3D(turn.scaled(Vector3(0.7, 0.7, 0.1)), p + Vector3.UP * (deck - 1.9) + out * (size * 0.5 + 0.12)), xform)

func collect_towers(parts: Dictionary, xform: Transform3D, points: Array, wall_height: float, footing_height: float, look: String) -> void:
	var tower_height := wall_height + 3.4 + 0.3 * (wall_level - 1)
	var near_gate := {}
	for gi in gates.size():
		var h := gate_half(gi)
		for k in range(-h - 6, h + 7):
			near_gate[posmod(gates[gi] + k, SAMPLES)] = true
	# Plain towers at a steady spacing along the wall, away from the gates. From
	# level 3 the towers stand closer together.
	var spacing := TOWER_SPACING * (0.8 if look != "timber" else 1.0)
	var start := (gates[0] if not gates.is_empty() else 0) + SAMPLES / 2
	var travelled := spacing * 0.5
	var placed: Array = []
	var count := 0
	for step in SAMPLES:
		var i := (start + step) % SAMPLES
		var p: Vector3 = points[i]
		var previous: Vector3 = points[posmod(i - 1, SAMPLES)]
		travelled += Vector2(p.x - previous.x, p.z - previous.z).length()
		if near_gate.has(i) or travelled < spacing:
			continue
		if placed.any(func(q: Vector3): return Vector2(q.x - p.x, q.z - p.z).length() < spacing * 0.6):
			continue
		travelled = 0.0
		placed.append(p)
		var out := Vector3(p.x - center.x, 0.0, p.z - center.y).normalized()
		tower_at(parts, xform, p, out, 4.0, tower_height, footing_height, look)
		count += 1
	# Gate houses: a tower each side, a covered bridge over the opening, open doors.
	for gi in gates.size():
		var g := gates[gi]
		if gi == 0 and custom_main_gate:
			continue
		var left: Vector3 = points[posmod(g - GATE_HALF, SAMPLES)]
		var right: Vector3 = points[posmod(g + GATE_HALF, SAMPLES)]
		var mid := (left + right) * 0.5
		var out := Vector3(mid.x - center.x, 0.0, mid.z - center.y).normalized()
		tower_at(parts, xform, left, out, 4.6, tower_height + 1.4, footing_height, look)
		tower_at(parts, xform, right, out, 4.6, tower_height + 1.4, footing_height, look)
		count += 2
		var top := maxf(left.y, right.y)
		var a := Vector3(left.x, top, left.z)
		var b := Vector3(right.x, top, right.z)
		put(parts, "gate_bridge", "box", "timber", span(a, b, footing_height + wall_height + 0.35, 1.1, 2.4, 0.0, -1.2), xform)
		put(parts, "gate_roof", "box", "roof", span(a, b, footing_height + wall_height + 1.45, 1.6, 2.0, 0.0, -1.6), xform)
		var along := (right - left)
		along.y = 0.0
		var width := along.length()
		along = along.normalized()
		var inward := -out
		# Two leaves hinged at the tower faces, swung open into the yard.
		var opening := width - 4.6
		var leaf := opening * 0.5
		for side: float in [-1.0, 1.0]:
			var hinge: Vector3 = mid + along * side * (opening * 0.5)
			hinge.y = minf(left.y, right.y)
			var swing: Vector3 = (-along * side * cos(1.2) + inward * sin(1.2)).normalized()
			var across: Vector3 = swing.cross(Vector3.UP).normalized()
			var door_height: float = wall_height + footing_height
			put(parts, "gate_doors", "box", "planks", Transform3D(Basis(swing * leaf, Vector3.UP * door_height, across * 0.3),
				hinge + swing * (leaf * 0.5) + Vector3.UP * (door_height * 0.5)), xform)
	tower_count = count
