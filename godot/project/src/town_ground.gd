extends Node3D

# Draws a TownPlan (src/town_plan.gd): the town ground (earth yards and lanes, paved
# streets, town square and forecourts) as one mesh over the painted cells, and the
# yard dressing that grows with the building level, the same for every building:
#   I    earth yard
#   II   timber kerb around the yard (an opening at the door)
#   III  paved forecourt from the door to the yard front
#   IV   stone kerb and two stone gate posts at the door
#   V    paved yard and lanterns on the gate posts
# The town hall always stands on the paved town square.

const TownPlan = preload("res://src/town_plan.gd")
const SHADER = preload("res://src/town_ground.gdshader")
const MATERIALS := "res://assets/city/architecture-v2/materials/"
const LIFT := 0.08
const POST := 0.42

var ground: MeshInstance3D
var dressing: Array[MeshInstance3D] = []
var material: ShaderMaterial
var mask_texture: ImageTexture
var kerb_pieces := 0
var post_count := 0
var lantern_count := 0
var ground_cells := PackedByteArray()
var ground_builds := 0
var near_segments: Array = []
var near_lots: Array = []

static func ground_material() -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SHADER
	m.set_shader_parameter("earth_tex", load("res://assets/city/premium/surfaces07/soil-albedo.webp"))
	m.set_shader_parameter("stone_tex", load("res://assets/city/premium/surfaces07/stone-albedo.jpg"))
	m.set_shader_parameter("area", Vector4(-TownPlan.HALF, -TownPlan.HALF, TownPlan.HALF * 2.0, TownPlan.HALF * 2.0))
	return m

func clear(keep_ground := false) -> void:
	if is_instance_valid(ground) and not keep_ground:
		ground.free()
	for node in dressing:
		if is_instance_valid(node):
			node.free()
	dressing.clear()
	kerb_pieces = 0
	post_count = 0
	lantern_count = 0

func build(plan: TownPlan, height: Callable) -> void:
	# The ground mesh only covers painted cells: reused while they are the same
	# (an upgrade repaints the mask, not the cells).
	var same_cells := is_instance_valid(ground) and ground_cells == plan.coarse
	clear(same_cells)
	if material == null:
		material = ground_material()
	if mask_texture == null or mask_texture.get_width() != plan.mask.get_width():
		mask_texture = ImageTexture.create_from_image(plan.mask)
	else:
		mask_texture.update(plan.mask)
	material.set_shader_parameter("mask", mask_texture)
	if not same_cells:
		ground_cells = plan.coarse.duplicate()
		ground = build_ground(plan, height)
		ground_builds += 1
		if ground != null:
			ground.material_override = material
			ground.name = "TownGround"
			add_child(ground)
	build_dressing(plan, height)

func build_ground(plan: TownPlan, height: Callable) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var heights := {}
	var cells := 0
	var step := TownPlan.COARSE * 0.5
	for cz in TownPlan.COARSE_SIZE:
		for cx in TownPlan.COARSE_SIZE:
			if not plan.coarse_cell(cx, cz):
				continue
			cells += 1
			var x0 := cx * TownPlan.COARSE - TownPlan.HALF
			var z0 := cz * TownPlan.COARSE - TownPlan.HALF
			for sz in 2:
				for sx in 2:
					var corners: Array[Vector3] = []
					for c: Vector2 in [Vector2(0, 0), Vector2(1, 0), Vector2(0, 1), Vector2(1, 1)]:
						var x := x0 + (sx + c.x) * step
						var z := z0 + (sz + c.y) * step
						var key := Vector2(x, z)
						if not heights.has(key):
							heights[key] = float(height.call(x, z)) + LIFT
						corners.append(Vector3(x, heights[key], z))
					for i in [0, 1, 2, 2, 1, 3]:
						st.add_vertex(corners[i])
	if cells == 0:
		return null
	st.index()
	st.generate_normals()
	var node := MeshInstance3D.new()
	node.mesh = st.commit()
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node

# ------------------------------------------------------------------ dressing

func on_street(plan: TownPlan, p: Vector2, margin: float, segments: Array = []) -> bool:
	for s: Dictionary in (segments if not segments.is_empty() else plan.segments):
		var q := Geometry2D.get_closest_point_to_segment(p, s.a, s.b)
		if p.distance_to(q) < float(s.w) * 0.5 + margin:
			return true
	return false

func build_dressing(plan: TownPlan, height: Callable) -> void:
	var timber := SurfaceTool.new()
	var stone := SurfaceTool.new()
	var posts := SurfaceTool.new()
	var iron := SurfaceTool.new()
	var glow := SurfaceTool.new()
	for st in [timber, stone, posts, iron, glow]:
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for lot: Dictionary in plan.lots:
		var level := int(lot.level)
		var r: Rect2 = lot.rect
		var door_x := float(lot.door_x)
		near_segments = plan.segments.filter(func(sg): return plan.street_rect(sg).grow(0.6).intersects(r.grow(0.6)))
		near_lots = plan.lots.filter(func(other): return other != lot and other.rect.grow(0.2).intersects(r.grow(0.2)))
		if level >= 2 and not lot.hall:
			var kerb := stone if level >= 4 else timber
			var width := 0.3 if level >= 4 else 0.2
			var tall := 0.24 if level >= 4 else 0.17
			var inset := width * 0.5 + 0.08
			var edges := [
				[Vector2(r.position.x + inset, r.position.y + inset), Vector2(r.position.x + inset, r.end.y - inset), lot.open[0]],
				[Vector2(r.end.x - inset, r.position.y + inset), Vector2(r.end.x - inset, r.end.y - inset), lot.open[1]],
				[Vector2(r.position.x + inset, r.position.y + inset), Vector2(r.end.x - inset, r.position.y + inset), lot.open[2]],
				[Vector2(r.position.x + inset, r.end.y - inset), Vector2(r.end.x - inset, r.end.y - inset), lot.open[3]],
			]
			for e in edges.size():
				if not edges[e][2]:
					continue
				var front: bool = e == 3
				add_kerb_runs(plan, lot, kerb, edges[e][0], edges[e][1], width, tall, front, height)
		var gate_level := 3 if lot.hall else 4
		if level >= gate_level:
			var z := r.end.y - 0.3
			for side: float in [-1.0, 1.0]:
				var x := door_x + side * (TownPlan.DOOR_GAP * 0.5 + POST * 0.5)
				var p := Vector2(x, z)
				if not TownPlan.inside(r, 0.1, p) or on_street(plan, p, 0.3) and not lot.hall:
					continue
				if lot.hall and on_street(plan, p, 0.2) and not plan.plaza.has_point(p):
					continue
				var y := float(height.call(x, z))
				add_box(posts, Vector3(x, y - 0.1, z), Vector3(POST, 1.05, POST), Color(0.92, 0.9, 0.86))
				add_box(posts, Vector3(x, y + 0.95, z), Vector3(POST + 0.12, 0.1, POST + 0.12), Color(1, 1, 1))
				post_count += 1
				if level >= 5:
					add_box(iron, Vector3(x, y + 1.05, z), Vector3(0.26, 0.05, 0.26), Color(1, 1, 1))
					add_box(glow, Vector3(x, y + 1.1, z), Vector3(0.18, 0.24, 0.18), Color(1, 1, 1))
					add_box(iron, Vector3(x, y + 1.34, z), Vector3(0.3, 0.06, 0.3), Color(1, 1, 1))
					lantern_count += 1
	var looks := {timber: "dark_oak", stone: "stone_light", posts: "stone", iron: "iron", glow: "glow"}
	for st: SurfaceTool in looks:
		var mesh := st.commit()
		if mesh.get_surface_count() == 0:
			continue
		var node := MeshInstance3D.new()
		node.mesh = mesh
		node.material_override = load(MATERIALS + looks[st] + ".tres")
		node.name = "Town_" + looks[st]
		add_child(node)
		dressing.append(node)

# A kerb along one yard edge, broken at the door, at streets and where another yard is.
func add_kerb_runs(plan: TownPlan, lot: Dictionary, st: SurfaceTool, a: Vector2, b: Vector2, width: float, tall: float, front: bool, height: Callable) -> void:
	var length := a.distance_to(b)
	var steps := maxi(1, ceili(length / 0.4))
	var run_start: Variant = null
	var previous := a
	for k in range(steps + 1):
		var p := a.lerp(b, float(k) / steps)
		var free := near_segments.is_empty() or not on_street(plan, p, 0.15, near_segments)
		if front and absf(p.x - float(lot.door_x)) < TownPlan.DOOR_GAP * 0.5:
			free = false
		if free:
			for other: Dictionary in near_lots:
				if other.rect.grow(0.05).has_point(p):
					free = false
					break
		if free and run_start == null:
			run_start = p
		if (not free or k == steps) and run_start != null:
			var end := p if free else previous
			add_kerb(st, run_start, end, width, tall, height)
			run_start = null
		previous = p

func add_kerb(st: SurfaceTool, a: Vector2, b: Vector2, width: float, tall: float, height: Callable) -> void:
	var length := a.distance_to(b)
	if length < 0.3:
		return
	var pieces := maxi(1, ceili(length / 1.2))
	for i in pieces:
		var p := a.lerp(b, float(i) / pieces)
		var q := a.lerp(b, float(i + 1) / pieces)
		add_beam(st, Vector3(p.x, float(height.call(p.x, p.y)), p.y), Vector3(q.x, float(height.call(q.x, q.y)), q.y), width, tall)
		kerb_pieces += 1

# A box between two ground points whose top follows the ground (sheared on slopes).
func add_beam(st: SurfaceTool, a: Vector3, b: Vector3, width: float, tall: float) -> void:
	var along := Vector3(b.x - a.x, 0.0, b.z - a.z).normalized()
	var across := Vector3(-along.z, 0.0, along.x) * width * 0.5
	var low := -0.12
	var corners := [
		a - across + Vector3.UP * low, a + across + Vector3.UP * low, b + across + Vector3.UP * low, b - across + Vector3.UP * low,
		a - across + Vector3.UP * tall, a + across + Vector3.UP * tall, b + across + Vector3.UP * tall, b - across + Vector3.UP * tall,
	]
	add_quads(st, corners)

func add_box(st: SurfaceTool, base: Vector3, size: Vector3, tint: Color) -> void:
	var h := Vector3(size.x * 0.5, 0.0, size.z * 0.5)
	var corners := [
		base + Vector3(-h.x, 0, -h.z), base + Vector3(h.x, 0, -h.z), base + Vector3(h.x, 0, h.z), base + Vector3(-h.x, 0, h.z),
		base + Vector3(-h.x, size.y, -h.z), base + Vector3(h.x, size.y, -h.z), base + Vector3(h.x, size.y, h.z), base + Vector3(-h.x, size.y, h.z),
	]
	add_quads(st, corners, tint)

# Top and four sides of a hexahedron (0-3 bottom ring, 4-7 top ring). Darker at the
# foot like the baked ground shading of the reworked buildings.
func add_quads(st: SurfaceTool, c: Array, tint := Color(1, 1, 1)) -> void:
	var faces := [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
	for f in faces:
		var p0: Vector3 = c[f[0]]
		var p1: Vector3 = c[f[1]]
		var p2: Vector3 = c[f[2]]
		var p3: Vector3 = c[f[3]]
		var normal := (p1 - p0).cross(p3 - p0).normalized()
		if f == faces[0]:
			normal = (p3 - p0).cross(p1 - p0).normalized()
			if normal.y < 0.0:
				normal = -normal
		var center := (p0 + p1 + p2 + p3) * 0.25
		var middle: Vector3 = (c[0] + c[1] + c[2] + c[3] + c[4] + c[5] + c[6] + c[7]) / 8.0
		var outward := center - middle
		if normal.dot(outward) < 0.0:
			normal = -normal
		var quad := [p0, p1, p2, p0, p2, p3]
		# Godot's front faces wind clockwise seen from outside.
		if (p1 - p0).cross(p2 - p0).dot(normal) > 0.0:
			quad = [p0, p2, p1, p0, p3, p2]
		for v: Vector3 in quad:
			var foot := 0.72 if v.y <= minf(minf(p0.y, p1.y), minf(p2.y, p3.y)) + 0.01 and f != faces[0] else 1.0
			st.set_color(Color(tint.r * foot, tint.g * foot, tint.b * foot))
			st.set_normal(normal)
			st.add_vertex(v)

# The yard of one building alone (upgrade window), on flat ground.
static func preview(table: Dictionary, type: String, level: int) -> Node3D:
	var plan := TownPlan.new()
	plan.plan([{"id": "preview", "type": type, "level": level, "x": 0.0, "z": 0.0, "hall": false}], table, [], [], [], Callable())
	var node := new()
	node.build(plan, func(_x, _z): return 0.0)
	return node
