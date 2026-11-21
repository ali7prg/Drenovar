extends Node3D
## Layout pass 4 (art/01 SW quarry): clean terraced limestone ledges round the quarry pit — flat lit tops,
## vertical shaded faces, warm cream limestone (the kit limestone texture through the painted `limestone`
## look: noise compressed, strata) — and a tall timber crane with a boom over the pit. Client visuals only:
## the terraces stay off every trail, glade 05 and the mine mouth; hidden under unexplored fog like every
## forest visual (update_view).

const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const ROCK_TEX := "res://assets/forest_rescue/forest/lf_rock_limestone_c.jpg"
const WOOD_TEX := "res://assets/forest_rescue/landmarks/lm_wood_c.jpg"

const TIERS := 4
const TIER_DEPTH := 3.0          # m: top width of a ledge
const TIER_RISE := 1.45          # m: height step per ledge
const HALF_SPAN := [104.0, 96.0, 88.0, 80.0]   # deg either side of the quarry axis
const SEG_DEG := 3.0
const TRAIL_KEEP := 3.4          # m: no ledge within this of a trail centre line
const MINE_KEEP := 5.2           # m: the mine mouth stays open
const LIGHT_MIX := 0.42

var items: Array = []            # [{node, center: Vector2, radius}]


## center / axis: quarry pit centre and the direction (rad) toward the mine and the cliff arc.
## route_dist: Callable(x, z) -> distance to the nearest trail centre line.
func build(center: Vector2, axis: float, mine: Vector2, glade: Vector2, glade_r: float, height_fn: Callable,
		route_dist: Callable) -> void:
	var h0: float = height_fn.call(center.x, center.y)
	var r0 := maxf(11.5, center.distance_to(mine) + 2.6)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in TIERS:
		var r_in := r0 + k * TIER_DEPTH
		var r_out := r_in + TIER_DEPTH
		var top := h0 + (k + 1) * TIER_RISE
		var half := deg_to_rad(float(HALF_SPAN[k]))
		var n := int(ceil(rad_to_deg(2.0 * half) / SEG_DEG))
		var keep: Array = []
		for i in n:
			var a := axis - half + 2.0 * half * (i + 0.5) / n
			var mid := center + Vector2(cos(a), sin(a)) * (r_in + TIER_DEPTH * 0.5)
			var face := center + Vector2(cos(a), sin(a)) * r_in
			var ok: bool = float(route_dist.call(mid.x, mid.y)) > TRAIL_KEEP and float(route_dist.call(face.x, face.y)) > TRAIL_KEEP
			ok = ok and mid.distance_to(glade) > glade_r + 2.0 and face.distance_to(mine) > MINE_KEEP and mid.distance_to(mine) > MINE_KEEP
			keep.append(ok)
		for i in n:
			if not keep[i]:
				continue
			var a0 := axis - half + 2.0 * half * i / n
			var a1 := axis - half + 2.0 * half * (i + 1) / n
			var e0 := 0.22 * sin(a0 * 9.0 + k * 1.7)          # irregular ledge edge
			var e1 := 0.22 * sin(a1 * 9.0 + k * 1.7)
			var d0 := Vector2(cos(a0), sin(a0))
			var d1 := Vector2(cos(a1), sin(a1))
			var i0 := center + d0 * (r_in + e0)
			var i1 := center + d1 * (r_in + e1)
			var o0 := center + d0 * r_out
			var o1 := center + d1 * r_out
			# flat lit top
			_quad(st, Vector3(i0.x, top, i0.y), Vector3(o0.x, top, o0.y), Vector3(o1.x, top, o1.y), Vector3(i1.x, top, i1.y),
				Vector3.UP, 1.0, true)
			# vertical face toward the pit (down into the ground)
			var b0: float = float(height_fn.call(i0.x, i0.y)) - 0.4
			var b1: float = float(height_fn.call(i1.x, i1.y)) - 0.4
			var nrm := -Vector3(cos((a0 + a1) * 0.5), 0.0, sin((a0 + a1) * 0.5))
			_quad(st, Vector3(i0.x, b0, i0.y), Vector3(i0.x, top, i0.y), Vector3(i1.x, top, i1.y), Vector3(i1.x, b1, i1.y),
				nrm, 0.62, false)
			# side caps where the ledge ends
			if i == 0 or not keep[i - 1]:
				_side(st, i0, o0, top, height_fn, Vector3(sin(a0), 0, -cos(a0)))
			if i == n - 1 or not keep[i + 1]:
				_side(st, i1, o1, top, height_fn, Vector3(-sin(a1), 0, cos(a1)))
			# the last ledge slopes back down into the ground
			if k == TIERS - 1:
				var g0 := center + d0 * (r_out + 3.2)
				var g1 := center + d1 * (r_out + 3.2)
				var y0: float = float(height_fn.call(g0.x, g0.y)) - 0.3
				var y1: float = float(height_fn.call(g1.x, g1.y)) - 0.3
				_quad(st, Vector3(o0.x, top, o0.y), Vector3(g0.x, y0, g0.y), Vector3(g1.x, y1, g1.y), Vector3(o1.x, top, o1.y),
					(Vector3(d0.x, 1.2, d0.y)).normalized(), 0.85, true)
	var mesh := st.commit()
	var base := StandardMaterial3D.new()
	base.resource_name = "lf_rock_quarry_terrace"
	base.albedo_texture = load(ROCK_TEX) if ResourceLoader.exists(ROCK_TEX) else null
	var material := ForestKit.painted_material(base, true, LIGHT_MIX, false)
	if material is ShaderMaterial:
		material.set_shader_parameter("limestone", 0.92)
		material.set_shader_parameter("limestone_base_y", h0)
		material.set_shader_parameter("ao_floor", 0.3)
		material.set_shader_parameter("vertex_wind", false)
	mesh.surface_set_material(0, material)
	var node := MeshInstance3D.new()
	node.name = "QuarryTerraces"
	node.mesh = mesh
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(node)
	items.append({"node": node, "center": center, "radius": r0 + TIERS * TIER_DEPTH + 3.0})
	_build_crane(center, axis, mine, r0, h0, height_fn, route_dist)


func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3, ao: float, top: bool) -> void:
	var verts: Array[Vector3] = [a, b, c, a, c, d]
	for v: Vector3 in verts:
		st.set_normal(n)
		st.set_color(Color(1, 1, 1, ao))
		if top:
			st.set_uv(Vector2(v.x, v.z) / 3.6)
		else:
			st.set_uv(Vector2(v.x + v.z, v.y) / 3.6)
		st.add_vertex(v)


func _side(st: SurfaceTool, inner: Vector2, outer: Vector2, top: float, height_fn: Callable, n: Vector3) -> void:
	var bi: float = float(height_fn.call(inner.x, inner.y)) - 0.4
	var bo: float = float(height_fn.call(outer.x, outer.y)) - 0.4
	_quad(st, Vector3(inner.x, bi, inner.y), Vector3(inner.x, top, inner.y), Vector3(outer.x, top, outer.y),
		Vector3(outer.x, bo, outer.y), n, 0.7, false)


## Timber crane (art/01: a tall frame with a boom over the pit): an A-frame mast with braces and a back
## stay, a boom from the mast foot out over the pit, the rope with a hook and a limestone block, a winch drum.
func _build_crane(center: Vector2, axis: float, mine: Vector2, r0: float, h0: float, height_fn: Callable,
		route_dist: Callable) -> void:
	var spot := Vector2.INF
	for side: float in [1.0, -1.0]:
		for off: float in [52.0, 62.0, 42.0, 72.0]:
			var a: float = axis + side * deg_to_rad(off)
			var p := center + Vector2(cos(a), sin(a)) * (r0 + TIER_DEPTH * 1.5)
			if float(route_dist.call(p.x, p.y)) > 4.5 and p.distance_to(mine) > 6.5:
				spot = p
				break
		if spot != Vector2.INF:
			break
	if spot == Vector2.INF:
		return
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# local frame: +Z toward the pit centre
	_beam(st, Vector3(-1.3, 0, -0.5), Vector3(-0.22, 8.6, 0.0), 0.3)
	_beam(st, Vector3(1.3, 0, -0.5), Vector3(0.22, 8.6, 0.0), 0.3)
	_beam(st, Vector3(0, 0, -3.4), Vector3(0, 8.4, -0.15), 0.26)           # back stay
	_beam(st, Vector3(-1.0, 2.6, -0.4), Vector3(1.0, 2.6, -0.4), 0.2)
	_beam(st, Vector3(-0.65, 5.4, -0.25), Vector3(0.65, 5.4, -0.25), 0.18)
	_beam(st, Vector3(-1.0, 2.6, -0.4), Vector3(0.65, 5.4, -0.25), 0.15)    # diagonal brace
	_beam(st, Vector3(-0.5, 8.8, 0.0), Vector3(0.5, 8.8, 0.0), 0.32)        # mast head
	_beam(st, Vector3(0, 1.1, 0.4), Vector3(0, 7.9, 7.2), 0.3)              # boom
	_beam(st, Vector3(0, 8.7, 0.0), Vector3(0, 7.95, 7.1), 0.06)            # boom stay rope
	_beam(st, Vector3(0, 7.8, 7.2), Vector3(0, 2.4, 7.2), 0.05)             # load rope
	_beam(st, Vector3(-0.5, 0.6, -1.2), Vector3(0.5, 0.6, -1.2), 0.5)       # winch drum
	var wood := st.commit()
	var base := StandardMaterial3D.new()
	base.resource_name = "lf_proc_crane_wood"
	base.albedo_texture = load(WOOD_TEX) if ResourceLoader.exists(WOOD_TEX) else null
	base.albedo_color = Color(0.86, 0.72, 0.55)
	wood.surface_set_material(0, ForestKit.painted_material(base, false, LIGHT_MIX, false))
	var st2 := SurfaceTool.new()
	st2.begin(Mesh.PRIMITIVE_TRIANGLES)
	_beam(st2, Vector3(-0.5, 1.75, 7.2), Vector3(0.5, 1.75, 7.2), 0.75)    # limestone block on the hook
	st2.commit(wood)
	var stone := StandardMaterial3D.new()
	stone.resource_name = "lf_rock_crane_block"
	stone.albedo_texture = load(ROCK_TEX) if ResourceLoader.exists(ROCK_TEX) else null
	var stone_mat := ForestKit.painted_material(stone, false, LIGHT_MIX, false)
	if stone_mat is ShaderMaterial:
		stone_mat.set_shader_parameter("limestone", 0.9)
	wood.surface_set_material(1, stone_mat)
	var node := MeshInstance3D.new()
	node.name = "QuarryCrane"
	node.mesh = wood
	var to_pit := (center - spot).normalized()
	node.position = Vector3(spot.x, float(height_fn.call(spot.x, spot.y)) - 0.1, spot.y)
	node.rotation.y = atan2(to_pit.x, to_pit.y)
	add_child(node)
	items.append({"node": node, "center": spot, "radius": 8.0})


func _beam(st: SurfaceTool, a: Vector3, b: Vector3, w: float) -> void:
	var axis := b - a
	var f := axis.normalized()
	var up := Vector3.UP if absf(f.dot(Vector3.UP)) < 0.95 else Vector3.RIGHT
	var r := f.cross(up).normalized() * w * 0.5
	var u := r.cross(f).normalized() * w * 0.5
	var corners: Array[Vector3] = [-r - u, r - u, r + u, -r + u]
	for i in 4:
		var c0: Vector3 = corners[i]
		var c1: Vector3 = corners[(i + 1) % 4]
		var n := (c0 + c1).normalized()
		var length := axis.length()
		var quad: Array[Vector3] = [a + c0, a + c1, b + c1, a + c0, b + c1, b + c0]
		var uvs: Array[Vector2] = [Vector2(0, 0), Vector2(w, 0), Vector2(w, length), Vector2(0, 0), Vector2(w, length), Vector2(0, length)]
		for j in 6:
			st.set_normal(n)
			st.set_uv(uvs[j] / 1.6)
			st.add_vertex(quad[j])
	for end in [[a, -f], [b, f]]:
		var o: Vector3 = end[0]
		var nn: Vector3 = end[1]
		var cap: Array[Vector3] = [o + corners[0], o + corners[1], o + corners[2], o + corners[0], o + corners[2], o + corners[3]]
		for v: Vector3 in cap:
			st.set_normal(nn)
			st.set_uv(Vector2(0.5, 0.5))
			st.add_vertex(v)


func update_view(visible_fn: Callable) -> void:
	for item in items:
		item.node.visible = visible_fn.call(item.center.x, item.center.y, item.radius) if visible_fn.is_valid() else true
