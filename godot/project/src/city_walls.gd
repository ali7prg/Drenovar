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
		# the ring overlaps the ends of the gate wings slightly, so no gap shows
		main_gate_half = maxi(GATE_HALF, floori(main_gate_span / maxf(step, 0.5)))
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
	m.normal_scale = 0.7
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
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

# Look of the wall by the level of "walls and gate" (1 = palisade of town hall II).
# Every level follows the B18 references and grows in height, thickness and detail:
# I   palisade of pointed logs on a low stone footing, timber watch towers;
# II  taller, thicker palisade, heavy posts with caps, a fighting walkway;
# III boarded timber curtain with crenellated timber parapet, towers on stone bases;
# IV  stone curtain carrying a timber gallery on corbels, stone towers with timber tops;
# V   high stone curtain with a covered gallery and battlements, tall stone towers.
const STYLE := {
	1: {"footing": 0.5, "height": 3.3, "thick": 0.5, "stake": 0.22, "tower": 3.4, "tower_height": 5.8, "spacing": 32.0},
	2: {"footing": 0.7, "height": 3.9, "thick": 0.6, "stake": 0.27, "tower": 3.8, "tower_height": 6.8, "spacing": 28.0},
	3: {"footing": 0.9, "height": 4.3, "thick": 0.7, "stake": 0.0, "tower": 4.2, "tower_height": 7.8, "spacing": 24.0},
	4: {"footing": 1.0, "height": 3.8, "thick": 1.4, "stake": 0.0, "tower": 4.6, "tower_height": 8.8, "spacing": 22.0},
	5: {"footing": 1.2, "height": 4.7, "thick": 1.7, "stake": 0.0, "tower": 5.0, "tower_height": 10.0, "spacing": 20.0},
}

static func style(level: int) -> Dictionary:
	return STYLE[clampi(level, 1, 5)]

# Top of the wall (walking level + parapet) above the ground, by level.
static func wall_top(level: int) -> float:
	var st := style(level)
	var top: float = st.footing + st.height
	if level == 4:
		top += 1.5
	elif level == 5:
		top += 2.4
	return top

static func tier(level: int) -> String:
	if level >= 4:
		return "stone"
	if level >= 3:
		return "towers"
	return "timber"

func put(parts: Dictionary, key: String, mesh: String, surface: String, transform_value: Transform3D, xform: Transform3D) -> void:
	if not parts.has(key):
		parts[key] = {"mesh": mesh, "material": surface, "transforms": []}
	parts[key].transforms.append(xform * transform_value)

func noise(i: int, k: int) -> float:
	var v := sin(float(i) * 12.9898 + float(k) * 78.233) * 43758.5453
	return v - floor(v)

func inward_of(a: Vector3, b: Vector3) -> Vector3:
	var flat_along := Vector3(b.x - a.x, 0.0, b.z - a.z)
	var across := flat_along.cross(Vector3.UP).normalized()
	var to_center := Vector3(center.x, 0.0, center.y) - (a + b) * 0.5
	to_center.y = 0.0
	return across if across.dot(to_center) >= 0.0 else -across

func piece(along: Vector3, inward: Vector3, size: Vector3, origin: Vector3) -> Transform3D:
	return Transform3D(Basis(along * size.x, Vector3.UP * size.y, inward * size.z), origin)

# Adds this wall to `parts` (one batch per part and material), moved by `xform`.
func collect(parts: Dictionary, xform := Transform3D.IDENTITY) -> void:
	tower_count = 0
	if not visible or radii.is_empty():
		return
	var level := clampi(wall_level, 1, 5)
	var st := style(level)
	var fh: float = st.footing
	var h: float = st.height
	var thick: float = st.thick
	var points: Array = []
	for i in SAMPLES:
		points.append(ground(wall_point(i)))
	for i in SAMPLES:
		if is_gate_segment(i):
			continue
		var a: Vector3 = points[i]
		var b: Vector3 = points[(i + 1) % SAMPLES]
		var along := Vector3(b.x - a.x, b.y - a.y, b.z - a.z)
		var length := along.length()
		along = along.normalized()
		var flat := Vector3(along.x, 0.0, along.z).normalized()
		var inward := inward_of(a, b)
		put(parts, "footing", "box", "stone", span(a, b, -2.6, 2.6 + fh, thick + 0.55, 0.0, 0.25), xform)
		if level <= 2:
			# palisade: round stakes with sharpened tops, rails on the inner side
			var r: float = st.stake
			var n := maxi(1, ceili(length / (r * 2.0)))
			for k in n:
				var t := (k + 0.5) / n
				var p := a.lerp(b, t)
				var hh := h * (0.95 + 0.1 * noise(i, k))
				put(parts, "curtain_planks", "log", "logs", Transform3D(Basis.IDENTITY.scaled(Vector3(r * 2.0, hh, r * 2.0)), p + Vector3.UP * (fh + hh * 0.5)), xform)
				put(parts, "stake_tips", "cone", "logs", Transform3D(Basis.IDENTITY.scaled(Vector3(r * 2.0, r * 2.6, r * 2.0)), p + Vector3.UP * (fh + hh + r * 1.3)), xform)
			for y in [0.3, 0.72]:
				put(parts, "rails", "box", "dark", span(a, b, fh + h * y, 0.16, 0.14, r + 0.08, 0.1), xform)
			if level == 2:
				put(parts, "walkway", "box", "timber", span(a, b, fh + h - 1.25, 0.2, 1.3, r + 0.75, 0.06), xform)
				put(parts, "walkway_rail", "box", "dark", span(a, b, fh + h - 0.25, 0.1, 0.1, r + 1.35, 0.06), xform)
				if i % 3 == 0:
					var q := a + inward * (r + 0.1)
					put(parts, "posts_heavy", "box", "planks", piece(flat, inward, Vector3(0.75, h + 1.2, 0.75), q + Vector3.UP * (fh + (h + 1.2) * 0.5)), xform)
					put(parts, "post_caps", "pyramid", "timber", Transform3D(Basis(Vector3.UP, PI * 0.25).scaled(Vector3(0.2, 0.22, 0.2)), q + Vector3.UP * (fh + h + 1.2 + 0.32)), xform)
					put(parts, "brackets", "box", "dark", piece(flat, inward, Vector3(0.14, 0.14, 1.3), q + inward * 0.6 + Vector3.UP * (fh + h - 1.5)), xform)
		elif level == 3:
			# boarded timber curtain, battens and rails outside, crenellated timber parapet
			put(parts, "curtain_boards", "box", "planks", span(a, b, fh - 0.05, h, 0.55, 0.0, 0.06), xform)
			var battens := maxi(1, roundi(length / 1.3))
			for k in battens:
				var p := a.lerp(b, (k + 0.5) / battens)
				put(parts, "battens", "box", "dark", piece(flat, inward, Vector3(0.18, h, 0.1), p - inward * 0.32 + Vector3.UP * (fh + h * 0.5)), xform)
			for y in [0.25, 0.65]:
				put(parts, "rails", "box", "dark", span(a, b, fh + h * y, 0.18, 0.1, -0.33, 0.06), xform)
			var merlons := maxi(1, int(length / 1.0))
			for k in merlons:
				var p := a.lerp(b, (k + 0.5) / merlons)
				put(parts, "parapet_timber", "box", "planks", piece(flat, inward, Vector3(0.55, 0.8, 0.5), p + Vector3.UP * (fh + h + 0.4)), xform)
			put(parts, "walkway", "box", "timber", span(a, b, fh + h - 0.2, 0.2, 1.5, 0.95, 0.06), xform)
			if i % 2 == 0:
				put(parts, "walk_posts", "box", "dark", piece(flat, inward, Vector3(0.25, h, 0.25), a + inward * 1.55 + Vector3.UP * (fh + h * 0.5)), xform)
		else:
			# masonry curtain with a string course, corbels and a timber gallery on top
			put(parts, "curtain_stone_wall", "box", "stone_wall", span(a, b, fh - 0.05, h, thick, 0.0, 0.08), xform)
			put(parts, "stone_course", "box", "stone", span(a, b, fh + h - 0.05, 0.25, thick + 0.25, 0.0, 0.1), xform)
			var top := fh + h + 0.2
			put(parts, "gallery_deck", "box", "timber", span(a, b, top, 0.18, thick + 0.8, -0.25, 0.06), xform)
			var corbels := maxi(1, roundi(length / 1.1))
			for k in corbels:
				var p := a.lerp(b, (k + 0.5) / corbels)
				put(parts, "corbels", "box", "dark", piece(flat, inward, Vector3(0.22, 0.55, 0.5), p - inward * (thick * 0.5 + 0.3) + Vector3.UP * (top - 0.3)), xform)
			var outer := -inward * (thick * 0.5 + 0.55)
			if level == 4:
				var boards := maxi(1, roundi(length / 0.6))
				for k in boards:
					var p := a.lerp(b, (k + 0.5) / boards)
					var bh := 1.3 if k % 2 == 0 else 0.9
					put(parts, "gallery_boards", "box", "planks", piece(flat, inward, Vector3(0.56, bh, 0.12), p + outer + Vector3.UP * (top + 0.18 + bh * 0.5)), xform)
				put(parts, "gallery_rail", "box", "dark", span(a, b, top + 1.0, 0.12, 0.12, thick * 0.5 + 0.1, 0.06), xform)
			else:
				var merlons := maxi(1, int(length / 1.1))
				for k in merlons:
					var p := a.lerp(b, (k + 0.5) / merlons)
					put(parts, "merlons", "box", "stone_wall", piece(flat, inward, Vector3(0.62, 0.95, 0.45), p + outer + Vector3.UP * (top + 0.18 + 0.47)), xform)
				put(parts, "gallery_posts", "box", "timber", piece(flat, inward, Vector3(0.24, 2.2, 0.24), a + outer + inward * 0.25 + Vector3.UP * (top + 1.25)), xform)
				put(parts, "gallery_posts", "box", "timber", piece(flat, inward, Vector3(0.24, 2.2, 0.24), a + inward * (thick * 0.5 + 0.2) + Vector3.UP * (top + 1.25)), xform)
				# covered gallery: roof slab sloping down to the outside
				var roof_basis := Basis(flat * (length + 0.12), Vector3.UP * 0.16, inward * (thick + 1.9)).rotated(flat, -0.38 if inward.cross(flat).y > 0.0 else 0.38)
				put(parts, "gallery_roof", "box", "roof", Transform3D(roof_basis, (a + b) * 0.5 + Vector3.UP * (top + 2.55) - inward * 0.2), xform)
	collect_towers(parts, xform, points, level)

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

# Same surface family as the reworked buildings (architecture-v2), mapped in world
# space because every wall part is a scaled instance of one mesh.
func surfaces() -> Dictionary:
	if shared_surfaces.is_empty():
		shared_surfaces = {
			"stone": material("stone", Color(0.78, 0.74, 0.67), 0.32),
			"stone_wall": material("stone", Color(0.86, 0.81, 0.72), 0.26),
			"planks": material("oak", Color(0.86, 0.76, 0.68), 0.45),
			"logs": material("dark_oak", Color(1.3, 1.12, 0.92), 0.6),
			"dark": material("dark_oak", Color(0.82, 0.78, 0.76), 0.5),
			"timber": material("oak", Color(1.0, 0.9, 0.78), 0.5),
			"roof": material("oak", Color(0.8, 0.74, 0.74), 0.9),
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
	var cone := CylinderMesh.new()
	cone.top_radius = 0.0
	cone.bottom_radius = 0.5
	cone.height = 1.0
	cone.radial_segments = 8
	cone.rings = 1
	var prism := PrismMesh.new()
	prism.size = Vector3.ONE
	var pyramid := CylinderMesh.new()
	pyramid.top_radius = 0.0
	pyramid.bottom_radius = 3.3
	pyramid.height = 2.9
	pyramid.radial_segments = 4
	pyramid.rings = 1
	return {"box": BoxMesh.new(), "log": log_mesh, "cone": cone, "prism": prism, "pyramid": pyramid}

func emit(parent: Node3D, parts: Dictionary) -> void:
	var surface_set := surfaces()
	var mesh_set := meshes()
	var keys := parts.keys()
	keys.sort()
	for key in keys:
		var part: Dictionary = parts[key]
		batch(parent, str(key), mesh_set[part.mesh], surface_set[part.material], part.transforms)

func tower_at(parts: Dictionary, xform: Transform3D, p: Vector3, out: Vector3, size: float, height: float, level: int) -> void:
	var yaw := atan2(out.x, out.z)
	var turn := Basis(Vector3.UP, yaw)
	put(parts, "tower_footing", "box", "stone", Transform3D(turn.scaled(Vector3(size + 0.8, 3.4, size + 0.8)), p + Vector3.UP * (-1.0)), xform)
	var deck := height
	if level <= 3:
		if level == 3:
			put(parts, "tower_base_stone", "box", "stone_wall", Transform3D(turn.scaled(Vector3(size + 0.4, 1.8, size + 0.4)), p + Vector3.UP * 0.9), xform)
		put(parts, "tower_body_planks", "box", "planks", Transform3D(turn.scaled(Vector3(size, height, size)), p + Vector3.UP * (height * 0.5)), xform)
		for corner in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(-1, 0, 1), Vector3(1, 0, 1)]:
			var c: Vector3 = turn * (corner * (size * 0.5 + 0.05))
			put(parts, "tower_corner_posts", "box", "dark", Transform3D(Basis.IDENTITY.scaled(Vector3(0.32, height, 0.32)), p + c + Vector3.UP * (height * 0.5)), xform)
		for y in [0.35, 0.7]:
			put(parts, "tower_bands", "box", "dark", Transform3D(turn.scaled(Vector3(size + 0.08, 0.18, size + 0.08)), p + Vector3.UP * (height * y)), xform)
	else:
		var stone_h := height if level == 5 else height - 2.2
		put(parts, "tower_body_stone_wall", "box", "stone_wall", Transform3D(turn.scaled(Vector3(size, stone_h, size)), p + Vector3.UP * (stone_h * 0.5)), xform)
		put(parts, "tower_course", "box", "stone", Transform3D(turn.scaled(Vector3(size + 0.3, 0.3, size + 0.3)), p + Vector3.UP * stone_h), xform)
		if level == 4:
			# jettied timber watch room on the masonry
			put(parts, "tower_room", "box", "planks", Transform3D(turn.scaled(Vector3(size + 0.6, 2.2, size + 0.6)), p + Vector3.UP * (stone_h + 1.1)), xform)
		else:
			for side in 4:
				var dir := turn * Vector3(cos(side * PI * 0.5), 0, sin(side * PI * 0.5))
				var tangent := dir.cross(Vector3.UP)
				for k in [-1.0, 0.0, 1.0]:
					var c: Vector3 = p + dir * (size * 0.5 + 0.1) + tangent * k * size * 0.33
					put(parts, "tower_merlons", "box", "stone_wall", Transform3D(turn.scaled(Vector3(0.6, 0.85, 0.6)), c + Vector3.UP * (height + 0.42)), xform)
	put(parts, "tower_deck", "box", "timber", Transform3D(turn.scaled(Vector3(size + 0.9, 0.35, size + 0.9)), p + Vector3.UP * (deck + 0.17)), xform)
	for corner in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(-1, 0, 1), Vector3(1, 0, 1)]:
		var c: Vector3 = turn * (corner * (size * 0.5 + 0.25))
		put(parts, "tower_pillars", "box", "timber", Transform3D(Basis.IDENTITY.scaled(Vector3(0.3, 1.9, 0.3)), p + c + Vector3.UP * (deck + 1.25)), xform)
	var roof_scale := size / 3.2 * (1.0 + 0.05 * (level - 1))
	put(parts, "tower_roofs", "pyramid", "roof", Transform3D((turn * Basis(Vector3.UP, PI * 0.25)).scaled(Vector3(roof_scale, roof_scale * (1.0 + 0.08 * level), roof_scale)), p + Vector3.UP * (deck + 2.5 + 1.45 * roof_scale * (1.0 + 0.08 * level))), xform)
	if level >= 2:
		put(parts, "banners", "box", "banner", Transform3D(turn.scaled(Vector3(1.6, 3.0, 0.08)), p + Vector3.UP * (deck - 2.2) + out * (size * 0.5 + 0.06)), xform)
		put(parts, "banner_trim", "box", "trim", Transform3D(turn.scaled(Vector3(0.7, 0.7, 0.1)), p + Vector3.UP * (deck - 1.9) + out * (size * 0.5 + 0.12)), xform)

func collect_towers(parts: Dictionary, xform: Transform3D, points: Array, level: int) -> void:
	var st := style(level)
	var size: float = st.tower
	var tower_height: float = st.tower_height
	var near_gate := {}
	for gi in gates.size():
		var h := gate_half(gi)
		for k in range(-h - 6, h + 7):
			near_gate[posmod(gates[gi] + k, SAMPLES)] = true
	var spacing: float = st.spacing
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
		tower_at(parts, xform, p, out, size, tower_height, level)
		count += 1
	var top := wall_top(level)
	for gi in gates.size():
		var g := gates[gi]
		var h := gate_half(gi)
		var left: Vector3 = points[posmod(g - h, SAMPLES)]
		var right: Vector3 = points[posmod(g + h, SAMPLES)]
		var mid := (left + right) * 0.5
		var out := Vector3(mid.x - center.x, 0.0, mid.z - center.y).normalized()
		# The main gate is the B18 scene with its own posts and towers; side gates get
		# a tower on each side, a covered bridge and open leaves.
		if gi == 0 and custom_main_gate:
			continue
		tower_at(parts, xform, left, out, size + 0.6, tower_height + 1.2, level)
		tower_at(parts, xform, right, out, size + 0.6, tower_height + 1.2, level)
		count += 2
		var y := maxf(left.y, right.y)
		var a := Vector3(left.x, y, left.z)
		var b := Vector3(right.x, y, right.z)
		put(parts, "gate_bridge", "box", "timber", span(a, b, top + 0.35, 1.1, 2.4, 0.0, -1.2), xform)
		put(parts, "gate_roof", "box", "roof", span(a, b, top + 1.45, 1.6, 2.0, 0.0, -1.6), xform)
		var along := (right - left)
		along.y = 0.0
		var width := along.length()
		along = along.normalized()
		var inward := -out
		var opening := width - (size + 0.6)
		var leaf := opening * 0.5
		for side: float in [-1.0, 1.0]:
			var hinge: Vector3 = mid + along * side * (opening * 0.5)
			hinge.y = minf(left.y, right.y)
			var swing: Vector3 = (-along * side * cos(1.2) + inward * sin(1.2)).normalized()
			var across: Vector3 = swing.cross(Vector3.UP).normalized()
			put(parts, "gate_doors", "box", "planks", Transform3D(Basis(swing * leaf, Vector3.UP * top, across * 0.3),
				hinge + swing * (leaf * 0.5) + Vector3.UP * (top * 0.5)), xform)
	tower_count = count

# ---------------------------------------------------------------- march through the gate

# Server v92 does not know the wall and returns a city march route straight through
# it. The army is drawn leaving the yard through the main gate instead (and coming
# back the same way). The timing stays the server's; only the drawn line changes.
# A route that already crosses the wall only inside a gate opening is kept as is.
func gate_path(points: PackedVector3Array) -> PackedVector3Array:
	if not visible or radii.size() != SAMPLES or gates.is_empty() or points.size() < 2:
		return points
	var a := points[0]
	var b := points[points.size() - 1]
	var a_in := inside(a.x, a.z)
	var b_in := inside(b.x, b.z)
	if a_in == b_in or crosses_only_at_gates(points):
		return points
	if a_in:
		return leave_through_gate(a, b)
	var back := leave_through_gate(b, a)
	back.reverse()
	return back

func crosses_only_at_gates(points: PackedVector3Array) -> bool:
	for k in range(1, points.size()):
		var p := Vector2(points[k - 1].x, points[k - 1].z)
		var q := Vector2(points[k].x, points[k].z)
		var steps := maxi(1, ceili(p.distance_to(q)))
		var was := inside(p.x, p.y)
		for s in range(1, steps + 1):
			var at := p.lerp(q, float(s) / steps)
			var now := inside(at.x, at.y)
			if now != was and not is_gate_segment(int(round(sample_index(at.x, at.y))) % SAMPLES):
				return false
			was = now
	return true

# Whether the straight way between two points outside the yard stays outside.
func clear_outside(p: Vector2, q: Vector2) -> bool:
	var steps := maxi(1, ceili(p.distance_to(q)))
	for s in range(steps + 1):
		var at := p.lerp(q, float(s) / steps)
		if inside(at.x, at.y, -2.0):
			return false
	return true

func leave_through_gate(from: Vector3, to: Vector3) -> PackedVector3Array:
	var g := gates[0]
	var gate := wall_point(g)
	var out := direction(g)
	var result := PackedVector3Array([from])
	for p in [gate - out * 6.0, gate, gate + out * 8.0]:
		result.append(Vector3(p.x, 0.0, p.y))
	# Walk around the wall, a few metres outside it, the shorter way to the target,
	# until the target is in plain sight.
	var target := Vector2(to.x, to.z)
	var last := gate + out * 8.0
	var goal := int(round(sample_index(to.x, to.z))) % SAMPLES
	var span := posmod(goal - g, SAMPLES)
	var step := 1 if span <= SAMPLES / 2 else -1
	var i := g
	var guard := 0
	while not clear_outside(last, target) and guard < SAMPLES:
		i = posmod(i + step * 3, SAMPLES)
		guard += 3
		var ring := center + direction(i) * (radii[i] + 7.0)
		result.append(Vector3(ring.x, 0.0, ring.y))
		last = ring
		if posmod((goal - i) * step, SAMPLES) < 3:
			break
	result.append(to)
	return result
