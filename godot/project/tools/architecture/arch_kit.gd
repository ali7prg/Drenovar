extends RefCounted
## Procedural architecture kit for DRENOVAR building levels (native Godot, Mobile renderer).
## Coordinates: metres relative to the plot centre, +Z = main facade (faces the city camera),
## +X = right-hand side on screen, Y = up. Geometry is merged per material on bake().

const MAT_DIR := "res://assets/city/architecture-v2/materials/"
const SURF := "res://assets/city/premium/surfaces07/"

var groups: Dictionary = {}
var stack: Array[Transform3D] = []
var xf := Transform3D.IDENTITY
var rng := RandomNumberGenerator.new()
var lanes: Array = []
var footprint := 6.3
var ao_floor := 0.0

func _init(seed_value: int = 1) -> void:
	rng.seed = seed_value

# ---------------------------------------------------------------- transform stack
func push(t: Transform3D) -> void:
	stack.append(xf)
	xf = xf * t

func push_at(pos: Vector3, yaw_deg := 0.0, scale_value := 1.0) -> void:
	push(Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)).scaled(Vector3.ONE * scale_value), pos))

func pop() -> void:
	xf = stack.pop_back()

func lane(from: Vector3, to: Vector3, width: float, height: float, kind := "unit") -> void:
	## Records a passage (in level space) that QA sweeps for obstacles and steps.
	lanes.append({"from": xf * from, "to": xf * to, "width": width, "height": height, "kind": kind})

# ---------------------------------------------------------------- low level emitters
func _group(mat: String) -> Dictionary:
	if not groups.has(mat):
		groups[mat] = {"v": PackedVector3Array(), "n": PackedVector3Array(), "c": PackedColorArray()}
	return groups[mat]

func _shade(p: Vector3, tint: Color) -> Color:
	# Baked contact shading: darker close to the ground, never below 0.6.
	var k := clampf((p.y - ao_floor) / 1.6, 0.0, 1.0)
	var ao := lerpf(0.66, 1.0, sqrt(k))
	return Color(tint.r * ao, tint.g * ao, tint.b * ao, 1.0)

func tri(mat: String, a: Vector3, b: Vector3, c: Vector3, tint := Color.WHITE) -> void:
	var wa := xf * a
	var wb := xf * b
	var wc := xf * c
	var n := (wb - wa).cross(wc - wa)
	if n.length_squared() < 1e-12:
		return
	n = n.normalized()
	var g := _group(mat)
	# Godot treats clockwise triangles as front faces.
	g.v.append(wa); g.v.append(wc); g.v.append(wb)
	for i in 3:
		g.n.append(n)
	g.c.append(_shade(wa, tint)); g.c.append(_shade(wc, tint)); g.c.append(_shade(wb, tint))

func quad(mat: String, a: Vector3, b: Vector3, c: Vector3, d: Vector3, tint := Color.WHITE) -> void:
	## a,b,c,d counter-clockwise when seen from the side the face points to.
	tri(mat, a, b, c, tint)
	tri(mat, a, c, d, tint)

func jitter(amount := 0.07) -> Color:
	var v := 1.0 + rng.randf_range(-amount, amount)
	return Color(v, v * rng.randf_range(0.985, 1.015), v, 1.0)

# ---------------------------------------------------------------- solids
func box(mat: String, center: Vector3, size: Vector3, yaw_deg := 0.0, tint := Color.WHITE, pitch_deg := 0.0, roll_deg := 0.0) -> void:
	var basis := Basis.from_euler(Vector3(deg_to_rad(pitch_deg), deg_to_rad(yaw_deg), deg_to_rad(roll_deg)))
	var h := size * 0.5
	var p := []
	for i in 8:
		var s := Vector3(-1 if i & 1 == 0 else 1, -1 if i & 2 == 0 else 1, -1 if i & 4 == 0 else 1)
		p.append(center + basis * (s * h))
	# faces: -x, +x, -y, +y, -z, +z
	quad(mat, p[0], p[4], p[6], p[2], tint)
	quad(mat, p[1], p[3], p[7], p[5], tint)
	quad(mat, p[0], p[1], p[5], p[4], tint)
	quad(mat, p[2], p[6], p[7], p[3], tint)
	quad(mat, p[0], p[2], p[3], p[1], tint)
	quad(mat, p[4], p[5], p[7], p[6], tint)

func aabb(mat: String, from: Vector3, to: Vector3, tint := Color.WHITE) -> void:
	box(mat, (from + to) * 0.5, (to - from).abs(), 0.0, tint)

func beam(mat: String, a: Vector3, b: Vector3, w := 0.16, h := -1.0, tint := Color.WHITE) -> void:
	## Square/rectangular timber from a to b.
	if h < 0:
		h = w
	var d := b - a
	var length := d.length()
	if length < 0.001:
		return
	var fwd := d / length
	var up := Vector3.UP if absf(fwd.dot(Vector3.UP)) < 0.95 else Vector3.FORWARD
	var right := fwd.cross(up).normalized()
	up = right.cross(fwd).normalized()
	var basis := Basis(right * w, up * h, fwd * length)
	var c := (a + b) * 0.5
	var p := []
	for i in 8:
		var s := Vector3(-0.5 if i & 1 == 0 else 0.5, -0.5 if i & 2 == 0 else 0.5, -0.5 if i & 4 == 0 else 0.5)
		p.append(c + basis * s)
	quad(mat, p[0], p[4], p[6], p[2], tint)
	quad(mat, p[1], p[3], p[7], p[5], tint)
	quad(mat, p[0], p[1], p[5], p[4], tint)
	quad(mat, p[2], p[6], p[7], p[3], tint)
	quad(mat, p[0], p[2], p[3], p[1], tint)
	quad(mat, p[4], p[5], p[7], p[6], tint)

func cyl(mat: String, a: Vector3, b: Vector3, r: float, sides := 10, caps := true, tint := Color.WHITE, r2 := -1.0) -> void:
	if r2 < 0:
		r2 = r
	var d := b - a
	if d.length() < 0.001:
		return
	var fwd := d.normalized()
	var up := Vector3.UP if absf(fwd.dot(Vector3.UP)) < 0.95 else Vector3.RIGHT
	var u := fwd.cross(up).normalized()
	var v := u.cross(fwd).normalized()
	var ring_a := []
	var ring_b := []
	for i in sides:
		var t := TAU * i / sides
		var o := u * cos(t) + v * sin(t)
		ring_a.append(a + o * r)
		ring_b.append(b + o * r2)
	for i in sides:
		var j := (i + 1) % sides
		quad(mat, ring_a[i], ring_a[j], ring_b[j], ring_b[i], tint)
	if caps:
		for i in range(1, sides - 1):
			tri(mat, ring_a[0], ring_a[i + 1], ring_a[i], tint * Color(1.08, 1.0, 0.9))
			tri(mat, ring_b[0], ring_b[i], ring_b[i + 1], tint * Color(1.08, 1.0, 0.9))

func cone(mat: String, base: Vector3, r: float, h: float, sides := 8, tint := Color.WHITE, yaw_deg := 0.0) -> void:
	var apex := base + Vector3(0, h, 0)
	var off := deg_to_rad(yaw_deg)
	for i in sides:
		var t0 := off + TAU * i / sides
		var t1 := off + TAU * (i + 1) / sides
		tri(mat, base + Vector3(cos(t0), 0, sin(t0)) * r, apex, base + Vector3(cos(t1), 0, sin(t1)) * r, tint)

func extrude(mat: String, profile: PackedVector2Array, z0: float, z1: float, tint := Color.WHITE, caps := true) -> void:
	## Extrudes an XY polygon (counter-clockwise) along Z from z0 to z1.
	var n := profile.size()
	for i in n:
		var a := profile[i]
		var b := profile[(i + 1) % n]
		quad(mat, Vector3(a.x, a.y, z1), Vector3(a.x, a.y, z0), Vector3(b.x, b.y, z0), Vector3(b.x, b.y, z1), tint)
	if caps:
		var idx := Geometry2D.triangulate_polygon(profile)
		for i in range(0, idx.size(), 3):
			var p0 := profile[idx[i]]
			var p1 := profile[idx[i + 1]]
			var p2 := profile[idx[i + 2]]
			tri(mat, Vector3(p0.x, p0.y, z1), Vector3(p1.x, p1.y, z1), Vector3(p2.x, p2.y, z1), tint)
			tri(mat, Vector3(p0.x, p0.y, z0), Vector3(p2.x, p2.y, z0), Vector3(p1.x, p1.y, z0), tint)

# ---------------------------------------------------------------- roofs
func shingle_slope(mat: String, eave_l: Vector3, eave_r: Vector3, ridge_l: Vector3, ridge_r: Vector3, row := 0.3, shingle := 0.34, thick := 0.055, tint := Color.WHITE) -> void:
	## Overlapping shingle courses on the quad eave->ridge. Rows may taper (hips).
	var slope_len := (ridge_l - eave_l).length()
	var rows := maxi(2, ceili(slope_len / row))
	var across := (eave_r - eave_l).normalized()
	var normal := (eave_r - eave_l).cross(ridge_l - eave_l).normalized()
	if normal.y < 0:
		normal = -normal
	for r in rows:
		var t0 := float(r) / rows
		var t1 := minf(1.0, float(r + 1) / rows + 0.35 / rows)
		var l0 := eave_l.lerp(ridge_l, t0)
		var r0 := eave_r.lerp(ridge_r, t0)
		var l1 := eave_l.lerp(ridge_l, t1)
		var r1 := eave_r.lerp(ridge_r, t1)
		var width := (r0 - l0).length()
		var count := maxi(1, roundi(width / shingle))
		var stagger := 0.5 if r % 2 == 1 else 0.0
		var lift := normal * (thick * (0.6 + 0.4 * float(r % 2)))
		for s in count + 1:
			var a0 := clampf((s - stagger) / count, 0.0, 1.0)
			var a1 := clampf((s + 1 - stagger) / count, 0.0, 1.0)
			if a1 - a0 < 0.02:
				continue
			var p00 := l0.lerp(r0, a0)
			var p10 := l0.lerp(r0, a1)
			var p01 := l1.lerp(r1, a0)
			var p11 := l1.lerp(r1, a1)
			var gap := across * 0.012
			var tn := tint * jitter(0.11)
			var drop := normal * -thick * 0.9
			# top face (raised, slightly tilted so each course reads as a step)
			quad(mat, p00 + gap + lift, p10 - gap + lift, p11 - gap + lift * 0.35, p01 + gap + lift * 0.35, tn)
			# visible butt edge
			quad(mat, p00 + gap + drop, p10 - gap + drop, p10 - gap + lift, p00 + gap + lift, tn * Color(0.72, 0.72, 0.72))
			quad(mat, p00 + gap + drop, p00 + gap + lift, p01 + gap + lift * 0.35, p01 + gap, tn * Color(0.8, 0.8, 0.8))
			quad(mat, p10 - gap + drop, p11 - gap, p11 - gap + lift * 0.35, p10 - gap + lift, tn * Color(0.8, 0.8, 0.8))
	# underside board so the roof never shows holes from below
	quad(mat, eave_l, ridge_l, ridge_r, eave_r, tint * Color(0.55, 0.55, 0.55))

func gable_roof(mat: String, c: Vector3, length: float, depth: float, rise: float, overhang := 0.35, gable_mat := "", ridge_mat := "dark_oak", tint := Color.WHITE) -> void:
	## Ridge along local X. c = centre at eave height.
	var hx := length * 0.5 + overhang
	var hz := depth * 0.5 + overhang
	var drop := rise * overhang / (depth * 0.5)
	var e := c.y - drop
	var ry := c.y + rise
	shingle_slope(mat, Vector3(c.x - hx, e, c.z + hz), Vector3(c.x + hx, e, c.z + hz), Vector3(c.x - hx, ry, c.z), Vector3(c.x + hx, ry, c.z), 0.3, 0.34, 0.055, tint)
	shingle_slope(mat, Vector3(c.x + hx, e, c.z - hz), Vector3(c.x - hx, e, c.z - hz), Vector3(c.x + hx, ry, c.z), Vector3(c.x - hx, ry, c.z), 0.3, 0.34, 0.055, tint)
	beam(ridge_mat, Vector3(c.x - hx - 0.05, ry + 0.06, c.z), Vector3(c.x + hx + 0.05, ry + 0.06, c.z), 0.16, 0.14)
	# barge boards
	for sx in [-1.0, 1.0]:
		var x: float = c.x + sx * (hx + 0.02)
		beam(ridge_mat, Vector3(x, e - 0.04, c.z + hz), Vector3(x, ry + 0.04, c.z), 0.07, 0.2)
		beam(ridge_mat, Vector3(x, e - 0.04, c.z - hz), Vector3(x, ry + 0.04, c.z), 0.07, 0.2)
	if gable_mat != "":
		for sx in [-1.0, 1.0]:
			var x: float = c.x + sx * length * 0.5
			var a := Vector3(x, c.y, c.z - depth * 0.5)
			var b := Vector3(x, c.y, c.z + depth * 0.5)
			var top := Vector3(x, ry - 0.05, c.z)
			if sx > 0:
				tri(gable_mat, a, top, b)
			else:
				tri(gable_mat, b, top, a)

func gable_frame(c: Vector3, length: float, depth: float, rise: float, mat := "dark_oak") -> void:
	## Decorative timber on both gable triangles (king post + braces).
	for sx in [-1.0, 1.0]:
		var x: float = c.x + sx * (length * 0.5 + 0.035)
		var top := Vector3(x, c.y + rise - 0.08, c.z)
		beam(mat, Vector3(x, c.y + 0.05, c.z - depth * 0.5), Vector3(x, c.y + 0.05, c.z + depth * 0.5), 0.09, 0.14)
		beam(mat, Vector3(x, c.y, c.z), top, 0.13, 0.09)
		beam(mat, Vector3(x, c.y + 0.05, c.z - depth * 0.3), Vector3(x, c.y + rise * 0.55, c.z), 0.09, 0.09)
		beam(mat, Vector3(x, c.y + 0.05, c.z + depth * 0.3), Vector3(x, c.y + rise * 0.55, c.z), 0.09, 0.09)

func hip_roof(mat: String, c: Vector3, lx: float, lz: float, rise: float, overhang := 0.3, tint := Color.WHITE, ridge_mat := "dark_oak") -> void:
	var hx := lx * 0.5 + overhang
	var hz := lz * 0.5 + overhang
	var drop := rise * overhang / (minf(lx, lz) * 0.5)
	var e := c.y - drop
	var ry := c.y + rise
	var rl := maxf(0.0, (lx - lz) * 0.5)
	var rw := maxf(0.0, (lz - lx) * 0.5)
	var A := Vector3(c.x - hx, e, c.z + hz)
	var B := Vector3(c.x + hx, e, c.z + hz)
	var C := Vector3(c.x + hx, e, c.z - hz)
	var D := Vector3(c.x - hx, e, c.z - hz)
	var R1 := Vector3(c.x - rl, ry, c.z - rw)
	var R2 := Vector3(c.x + rl, ry, c.z + rw)
	# front (+z) and back
	shingle_slope(mat, A, B, Vector3(R1.x, ry, R2.z), Vector3(R2.x, ry, R2.z), 0.3, 0.34, 0.055, tint)
	shingle_slope(mat, C, D, Vector3(R2.x, ry, R1.z), Vector3(R1.x, ry, R1.z), 0.3, 0.34, 0.055, tint)
	shingle_slope(mat, B, C, Vector3(R2.x, ry, R2.z), Vector3(R2.x, ry, R1.z), 0.3, 0.34, 0.055, tint)
	shingle_slope(mat, D, A, Vector3(R1.x, ry, R1.z), Vector3(R1.x, ry, R2.z), 0.3, 0.34, 0.055, tint)
	for p in [A, B, C, D]:
		var q: Vector3 = Vector3(R1.x if p.x < c.x else R2.x, ry, R1.z if p.z < c.z else R2.z)
		beam(ridge_mat, p + Vector3(0, 0.05, 0), q + Vector3(0, 0.07, 0), 0.1, 0.1)
	if rl > 0.01 or rw > 0.01:
		beam(ridge_mat, R1 + Vector3(0, 0.07, 0), R2 + Vector3(0, 0.07, 0), 0.14, 0.12)

func pyramid_roof(mat: String, c: Vector3, size: float, rise: float, overhang := 0.25, finial := true, tint := Color.WHITE) -> void:
	hip_roof(mat, c, size, size, rise, overhang, tint)
	if finial:
		cyl("dark_oak", c + Vector3(0, rise, 0), c + Vector3(0, rise + 0.35, 0), 0.07, 6)
		box("dark_oak", c + Vector3(0, rise + 0.4, 0), Vector3(0.16, 0.16, 0.16), 45)

# ---------------------------------------------------------------- walls
func timber_wall(a: Vector3, b: Vector3, h: float, openings: Array = [], infill := "plaster", frame := "oak", thick := 0.22, bay := 1.25, braces := true) -> void:
	## Wall from a to b (y = base). Face normal points to the right of a->b (outside).
	## openings: [{"at": metres from a, "w": width, "y0": sill, "y1": head, "kind": "door"/"window"/"open"}]
	var d := b - a
	var length := Vector2(d.x, d.z).length()
	var dir := Vector3(d.x, 0, d.z).normalized()
	var out := Vector3(-dir.z, 0, dir.x)
	var cuts := []
	for o in openings:
		cuts.append(Vector2(float(o.at) - float(o.w) * 0.5, float(o.at) + float(o.w) * 0.5))
	# infill panels as vertical strips split around openings
	var xs := [0.0, length]
	for o in openings:
		xs.append(float(o.at) - float(o.w) * 0.5)
		xs.append(float(o.at) + float(o.w) * 0.5)
	xs.sort()
	for i in xs.size() - 1:
		var x0: float = xs[i]
		var x1: float = xs[i + 1]
		if x1 - x0 < 0.01:
			continue
		var mid := (x0 + x1) * 0.5
		var spans := [Vector2(0, h)]
		for o in openings:
			if mid > float(o.at) - float(o.w) * 0.5 and mid < float(o.at) + float(o.w) * 0.5:
				spans = [Vector2(0, float(o.y0)), Vector2(float(o.y1), h)]
		for s in spans:
			if s.y - s.x < 0.01:
				continue
			var c := a + dir * mid + Vector3(0, (s.x + s.y) * 0.5, 0)
			box(infill, c, Vector3(x1 - x0, s.y - s.x, thick), rad_to_deg(atan2(-dir.z, dir.x)))
	# frame on the outside face
	var f := out * (thick * 0.5 + 0.03)
	var posts := maxi(1, roundi(length / bay))
	for i in posts + 1:
		var x := length * i / posts
		var blocked := false
		for cu in cuts:
			if x > cu.x - 0.05 and x < cu.y + 0.05:
				blocked = true
		if not blocked:
			beam(frame, a + dir * x + f, a + dir * x + f + Vector3(0, h, 0), 0.17, 0.1)
	beam(frame, a + f + Vector3(0, 0.08, 0), b + f + Vector3(0, 0.08, 0), 0.1, 0.17)
	beam(frame, a + f + Vector3(0, h - 0.08, 0), b + f + Vector3(0, h - 0.08, 0), 0.1, 0.17)
	if h > 2.2:
		# mid rail between openings
		var ry := minf(1.05, h * 0.45)
		var xs2 := [0.0]
		for cu in cuts:
			xs2.append(cu.x)
			xs2.append(cu.y)
		xs2.append(length)
		for i in range(0, xs2.size() - 1, 2):
			if float(xs2[i + 1]) - float(xs2[i]) > 0.2:
				beam(frame, a + dir * float(xs2[i]) + f + Vector3(0, ry, 0), a + dir * float(xs2[i + 1]) + f + Vector3(0, ry, 0), 0.09, 0.12)
	if braces:
		for i in posts:
			var x0 := length * i / posts
			var x1 := length * (i + 1) / posts
			var free := true
			for cu in cuts:
				if x1 > cu.x - 0.05 and x0 < cu.y + 0.05:
					free = false
			if free and x1 - x0 > 0.6:
				if i % 2 == 0:
					beam(frame, a + dir * x0 + f + Vector3(0, 0.15, 0), a + dir * x1 + f + Vector3(0, h - 0.15, 0), 0.1, 0.09)
				else:
					beam(frame, a + dir * x1 + f + Vector3(0, 0.15, 0), a + dir * x0 + f + Vector3(0, h - 0.15, 0), 0.1, 0.09)
	for o in openings:
		var at: float = float(o.at)
		var w: float = float(o.w)
		var y0: float = float(o.y0)
		var y1: float = float(o.y1)
		var cc := a + dir * at
		var yaw := rad_to_deg(atan2(-dir.z, dir.x))
		# jambs and lintel
		beam(frame, cc - dir * (w * 0.5 + 0.06) + f + Vector3(0, y0, 0), cc - dir * (w * 0.5 + 0.06) + f + Vector3(0, y1 + 0.1, 0), 0.13, 0.12)
		beam(frame, cc + dir * (w * 0.5 + 0.06) + f + Vector3(0, y0, 0), cc + dir * (w * 0.5 + 0.06) + f + Vector3(0, y1 + 0.1, 0), 0.13, 0.12)
		beam(frame, cc - dir * (w * 0.5 + 0.14) + f + Vector3(0, y1 + 0.08, 0), cc + dir * (w * 0.5 + 0.14) + f + Vector3(0, y1 + 0.08, 0), 0.12, 0.16)
		match String(o.get("kind", "window")):
			"door":
				door(cc + out * (thick * 0.1), w, y1 - y0, yaw, y0)
			"window":
				window(cc + out * (thick * 0.5), w, y0, y1, yaw)
			"double":
				door(cc - dir * w * 0.25 + out * (thick * 0.1), w * 0.5, y1 - y0, yaw, y0)
				door(cc + dir * w * 0.25 + out * (thick * 0.1), w * 0.5, y1 - y0, yaw, y0)

func door(c: Vector3, w: float, h: float, yaw: float, y0 := 0.0) -> void:
	var dir := Vector3(cos(deg_to_rad(yaw)), 0, -sin(deg_to_rad(yaw)))
	var planks := maxi(3, roundi(w / 0.16))
	for i in planks:
		var x := -w * 0.5 + w * (i + 0.5) / planks
		box("dark_oak", c + dir * x + Vector3(0, y0 + h * 0.5, 0), Vector3(w / planks - 0.012, h, 0.07), yaw, jitter(0.12))
	for yy in [0.22, 0.78]:
		box("iron", c + Vector3(0, y0 + h * yy, 0) + Vector3(dir.z, 0, -dir.x) * -0.045, Vector3(w * 0.86, 0.06, 0.025), yaw)
	box("iron", c + dir * (w * 0.32) + Vector3(0, y0 + h * 0.5, 0) + Vector3(dir.z, 0, -dir.x) * -0.06, Vector3(0.05, 0.12, 0.05), yaw)

func window(c: Vector3, w: float, y0: float, y1: float, yaw: float, shutters := true) -> void:
	var dir := Vector3(cos(deg_to_rad(yaw)), 0, -sin(deg_to_rad(yaw)))
	var out := Vector3(dir.z, 0, -dir.x) * -1.0
	var h := y1 - y0
	box("glass", c + Vector3(0, y0 + h * 0.5, 0) - out * 0.06, Vector3(w, h, 0.04), yaw)
	box("dark_oak", c + Vector3(0, y0 + h * 0.5, 0) - out * 0.03, Vector3(0.05, h, 0.05), yaw)
	box("dark_oak", c + Vector3(0, y0 + h * 0.55, 0) - out * 0.03, Vector3(w, 0.05, 0.05), yaw)
	box("oak", c + Vector3(0, y0 - 0.04, 0) + out * 0.04, Vector3(w + 0.2, 0.08, 0.16), yaw)
	if shutters:
		for s in [-1.0, 1.0]:
			box("shutter", c + dir * s * (w * 0.5 + w * 0.26) + Vector3(0, y0 + h * 0.5, 0) + out * 0.03, Vector3(w * 0.48, h * 0.98, 0.05), yaw, jitter(0.05))

func stone_wall(a: Vector3, b: Vector3, h: float, thick := 0.6, mat := "stone", openings: Array = [], quoins := true, plinth := true) -> void:
	var d := b - a
	var length := Vector2(d.x, d.z).length()
	var dir := Vector3(d.x, 0, d.z).normalized()
	var yaw := rad_to_deg(atan2(-dir.z, dir.x))
	var xs := [0.0, length]
	for o in openings:
		xs.append(float(o.at) - float(o.w) * 0.5)
		xs.append(float(o.at) + float(o.w) * 0.5)
	xs.sort()
	for i in xs.size() - 1:
		var x0: float = xs[i]
		var x1: float = xs[i + 1]
		if x1 - x0 < 0.01:
			continue
		var mid := (x0 + x1) * 0.5
		var spans := [Vector2(0, h)]
		for o in openings:
			if mid > float(o.at) - float(o.w) * 0.5 and mid < float(o.at) + float(o.w) * 0.5:
				spans = [Vector2(0, float(o.y0)), Vector2(float(o.y1), h)]
		for s in spans:
			if s.y - s.x < 0.01:
				continue
			box(mat, a + dir * mid + Vector3(0, (s.x + s.y) * 0.5, 0), Vector3(x1 - x0, s.y - s.x, thick), yaw, Color(0.62, 0.6, 0.57))
			_ashlar(mat, a, dir, x0, x1, s.x, s.y, thick, yaw)
	var out := Vector3(-dir.z, 0, dir.x)
	if plinth:
		var cuts := [0.0 - 0.06]
		for o in openings:
			if String(o.get("kind", "")) == "door":
				cuts.append(float(o.at) - float(o.w) * 0.5)
				cuts.append(float(o.at) + float(o.w) * 0.5)
		cuts.append(length + 0.06)
		for i in range(0, cuts.size() - 1, 2):
			var p0: float = cuts[i]
			var p1: float = cuts[i + 1]
			if p1 - p0 > 0.05:
				box(mat, a + dir * ((p0 + p1) * 0.5) + Vector3(0, 0.18, 0), Vector3(p1 - p0, 0.36, thick + 0.14), yaw, Color(0.86, 0.86, 0.84))
	box(mat, a + dir * length * 0.5 + Vector3(0, h + 0.06, 0), Vector3(length + 0.08, 0.12, thick + 0.1), yaw, Color(1.06, 1.05, 1.02))
	if quoins:
		for end in [0.0, length]:
			var y := 0.0
			var k := 0
			while y < h - 0.1:
				var bh := minf(0.32, h - y)
				var bw := 0.5 if k % 2 == 0 else 0.34
				var along := (bw * 0.5 - 0.02) * (1.0 if end == 0.0 else -1.0)
				box(mat, a + dir * (end + along) + Vector3(0, y + bh * 0.5, 0), Vector3(bw, bh - 0.025, thick + 0.07), yaw, Color(1.04, 1.02, 0.98) * jitter(0.05))
				y += bh
				k += 1
	for o in openings:
		var kind := String(o.get("kind", "window"))
		var cc := a + dir * float(o.at)
		if kind == "slit":
			box("glass", cc + out * (thick * 0.5 - 0.02) + Vector3(0, (float(o.y0) + float(o.y1)) * 0.5, 0), Vector3(float(o.w), float(o.y1) - float(o.y0), 0.05), yaw)
		elif kind == "window":
			window(cc + out * (thick * 0.5), float(o.w), float(o.y0), float(o.y1), yaw, false)
			box(mat, cc + out * (thick * 0.5) + Vector3(0, float(o.y1) + 0.1, 0), Vector3(float(o.w) + 0.3, 0.2, 0.12), yaw, Color(1.12, 1.1, 1.05))
		elif kind == "door":
			door(cc + out * (thick * 0.3), float(o.w), float(o.y1) - float(o.y0), yaw, float(o.y0))

func _ashlar(mat: String, a: Vector3, dir: Vector3, x0: float, x1: float, y0: float, y1: float, thick: float, yaw: float) -> void:
	## Coursed stone facing (both faces) over a darker mortar core.
	var out := Vector3(-dir.z, 0, dir.x)
	var course := 0.34
	var rows := maxi(1, roundi((y1 - y0) / course))
	var rh := (y1 - y0) / rows
	for r in rows:
		var y := y0 + rh * (r + 0.5)
		var x := x0
		var first := true
		while x < x1 - 0.02:
			var w := rng.randf_range(0.42, 0.78)
			if first and r % 2 == 1:
				w *= 0.5
			first = false
			var xe := minf(x1, x + w)
			if x1 - xe < 0.18:
				xe = x1
			var tn := jitter(0.09)
			for side: float in [-1.0, 1.0]:
				var c := a + dir * ((x + xe) * 0.5) + Vector3(0, y, 0) + out * side * (thick * 0.5 + 0.012)
				box(mat, c, Vector3(xe - x - 0.03, rh - 0.03, 0.05), yaw, tn)
			x = xe

func crenellations(a: Vector3, b: Vector3, y: float, thick := 0.5, mat := "stone", merlon := 0.45, gap := 0.35, height := 0.45) -> void:
	var d := b - a
	var length := Vector2(d.x, d.z).length()
	var dir := Vector3(d.x, 0, d.z).normalized()
	var yaw := rad_to_deg(atan2(-dir.z, dir.x))
	var n := maxi(1, floori((length + gap) / (merlon + gap)))
	var used := n * merlon + (n - 1) * gap
	var start := (length - used) * 0.5
	for i in n:
		var x := start + i * (merlon + gap) + merlon * 0.5
		box(mat, a + dir * x + Vector3(0, y + height * 0.5, 0), Vector3(merlon, height, thick), yaw, jitter(0.05))

func arch_wall(c: Vector3, width: float, thick: float, spring: float, wall_w: float, wall_h: float, mat := "stone", voussoir_mat := "stone_light") -> void:
	## Wall in the local XY plane centred at c.x, facing +Z, with a round-headed opening.
	## Opening: |x| < width/2, y < spring + width/2. Nothing is built inside the opening.
	var r := width * 0.5
	var top := spring + r
	# piers
	box(mat, c + Vector3(-(r + (wall_w * 0.5 - r) * 0.5), wall_h * 0.5, 0), Vector3(wall_w * 0.5 - r, wall_h, thick), 0, jitter(0.03))
	box(mat, c + Vector3(r + (wall_w * 0.5 - r) * 0.5, wall_h * 0.5, 0), Vector3(wall_w * 0.5 - r, wall_h, thick), 0, jitter(0.03))
	# spandrel above the arch, built as vertical strips that follow the curve
	var strips := 12
	for i in strips:
		var x0 := -r + width * i / strips
		var x1 := -r + width * (i + 1) / strips
		var xm := (x0 + x1) * 0.5
		var xin := minf(absf(x0), absf(x1)) if x0 * x1 > 0.0 else 0.0
		var yc := spring + sqrt(maxf(0.0, r * r - xin * xin))
		if wall_h - yc > 0.01:
			box(mat, c + Vector3(xm, (yc + wall_h) * 0.5, 0), Vector3(x1 - x0 + 0.005, wall_h - yc, thick), 0)
	# voussoirs (slightly proud of both faces)
	var count := 13
	for i in count:
		var t0 := PI * i / count
		var t1 := PI * (i + 1) / count
		var tm := (t0 + t1) * 0.5
		var mid := Vector3(cos(tm) * (r + 0.17), spring + sin(tm) * (r + 0.17), 0)
		var tint := Color(1.0, 1.0, 1.0) * jitter(0.06)
		var ang := rad_to_deg(tm) - 90.0
		box(voussoir_mat, c + mid, Vector3(PI * (r + 0.17) / count - 0.025, 0.36, thick + 0.1), 0, tint, 0, ang)
	box(voussoir_mat, c + Vector3(0, top + 0.2, 0), Vector3(0.34, 0.46, thick + 0.16), 0, Color(1.1, 1.08, 1.0))
	# impost blocks
	for s in [-1.0, 1.0]:
		box(voussoir_mat, c + Vector3(s * (r + 0.12), spring - 0.08, 0), Vector3(0.36, 0.18, thick + 0.14), 0, Color(1.05, 1.03, 1.0))

# ---------------------------------------------------------------- circulation
func stairs(base_center: Vector3, width: float, steps: int, rise: float, run: float, yaw := 0.0, mat := "stone", cheeks := true) -> void:
	## Ascends towards local -Z from base_center (first step front edge at base_center).
	push_at(base_center, yaw)
	for i in steps:
		var y := rise * (i + 1)
		var z := -run * i
		box(mat, Vector3(0, y * 0.5, z - run * 0.5), Vector3(width, y, run + 0.01), 0, jitter(0.05))
	if cheeks:
		for s in [-1.0, 1.0]:
			var pr := PackedVector2Array([Vector2(0, 0), Vector2(0, rise + 0.1), Vector2(-run * steps, rise * steps + 0.1), Vector2(-run * steps, 0)])
			push(Transform3D(Basis(Vector3.UP, -PI * 0.5), Vector3(s * (width * 0.5 + 0.1), 0, 0)))
			extrude(mat, pr, -0.1, 0.1, Color(0.92, 0.92, 0.9))
			pop()
	pop()

func ramp(from: Vector3, to: Vector3, width: float, mat := "oak", curbs := true, planks := true, curb_h := 0.12) -> void:
	## Continuous inclined deck from 'from' (low end on the ground) to 'to'. No steps.
	var d := to - from
	var flat := Vector3(d.x, 0, d.z)
	var length := flat.length()
	var dir := flat.normalized()
	var side := Vector3(dir.z, 0, -dir.x)
	var yaw := rad_to_deg(atan2(-dir.z, dir.x))
	# support wedge under the deck down to grade
	var pr := PackedVector2Array([Vector2(0.3, -0.02), Vector2(length, -0.02), Vector2(length, d.y - 0.06), Vector2(0.3, d.y * 0.3 / length - 0.06)])
	push(Transform3D(Basis(Vector3.UP, deg_to_rad(yaw)), from))
	extrude("dark_oak", pr, -width * 0.5 + 0.08, width * 0.5 - 0.08, Color(0.7, 0.7, 0.7))
	pop()
	# boards: walking surface lies exactly on the from->to line (flush with grade and deck)
	var n := maxi(2, roundi(length / 0.3)) if planks else 1
	var hw := side * width * 0.5
	for i in n:
		var t0 := float(i) / n
		var t1 := float(i + 1) / n
		var p0 := from.lerp(to, t0)
		var p1 := from.lerp(to, t1)
		var tn := jitter(0.12)
		var gap := (p1 - p0).normalized() * 0.01
		var dn := Vector3(0, -0.05, 0)
		quad(mat, p0 + hw + gap, p0 - hw + gap, p1 - hw - gap, p1 + hw - gap, tn)
		quad(mat, p0 + hw + gap + dn, p0 - hw + gap + dn, p0 - hw + gap, p0 + hw + gap, tn * Color(0.75, 0.75, 0.75))
		quad(mat, p0 + hw + gap + dn, p0 + hw + gap, p1 + hw - gap, p1 + hw - gap + dn, tn * Color(0.8, 0.8, 0.8))
		quad(mat, p0 - hw + gap, p0 - hw + gap + dn, p1 - hw - gap + dn, p1 - hw - gap, tn * Color(0.8, 0.8, 0.8))
	if curbs:
		# kerbs start part-way up so they never stick out where the foot meets uneven grade
		var k0 := from.lerp(to, 0.3)
		for s in [-1.0, 1.0]:
			beam("dark_oak", k0 + side * s * (width * 0.5 + 0.06) + Vector3(0, curb_h * 0.5 + 0.03, 0), to + side * s * (width * 0.5 + 0.06) + Vector3(0, curb_h * 0.5 + 0.03, 0), 0.1, curb_h)
			box("dark_oak", k0 + side * s * (width * 0.5 + 0.06) + Vector3(0, 0.08, 0), Vector3(0.14, 0.2, 0.14), rad_to_deg(atan2(-dir.z, dir.x)))

func deck(from: Vector3, to: Vector3, y: float, mat := "oak", posts := true, joists := true, along_x := true, post_mat := "dark_oak") -> void:
	## Plank platform covering the XZ rectangle from..to at height y (top surface).
	var lo := Vector3(minf(from.x, to.x), 0, minf(from.z, to.z))
	var hi := Vector3(maxf(from.x, to.x), 0, maxf(from.z, to.z))
	var span := (hi.z - lo.z) if along_x else (hi.x - lo.x)
	var n := maxi(1, roundi(span / 0.24))
	for i in n:
		var t0 := float(i) / n
		var t1 := float(i + 1) / n
		if along_x:
			box(mat, Vector3((lo.x + hi.x) * 0.5, y - 0.03, lerpf(lo.z, hi.z, (t0 + t1) * 0.5)), Vector3(hi.x - lo.x, 0.06, span / n - 0.018), 0, jitter(0.13))
		else:
			box(mat, Vector3(lerpf(lo.x, hi.x, (t0 + t1) * 0.5), y - 0.03, (lo.z + hi.z) * 0.5), Vector3(span / n - 0.018, 0.06, hi.z - lo.z), 0, jitter(0.13))
	if y > 0.15:
		if joists:
			for k in range(0, 3):
				var t := k / 2.0
				if along_x:
					box("dark_oak", Vector3((lo.x + hi.x) * 0.5, y - 0.12, lerpf(lo.z + 0.1, hi.z - 0.1, t)), Vector3(hi.x - lo.x, 0.12, 0.12))
				else:
					box("dark_oak", Vector3(lerpf(lo.x + 0.1, hi.x - 0.1, t), y - 0.12, (lo.z + hi.z) * 0.5), Vector3(0.12, 0.12, hi.z - lo.z))
		# fascia
		box("dark_oak", Vector3((lo.x + hi.x) * 0.5, y - 0.1, hi.z), Vector3(hi.x - lo.x, 0.16, 0.06))
		box("dark_oak", Vector3((lo.x + hi.x) * 0.5, y - 0.1, lo.z), Vector3(hi.x - lo.x, 0.16, 0.06))
		box("dark_oak", Vector3(lo.x, y - 0.1, (lo.z + hi.z) * 0.5), Vector3(0.06, 0.16, hi.z - lo.z))
		box("dark_oak", Vector3(hi.x, y - 0.1, (lo.z + hi.z) * 0.5), Vector3(0.06, 0.16, hi.z - lo.z))
		if posts:
			var nx := maxi(1, ceili((hi.x - lo.x) / 1.6))
			var nz := maxi(1, ceili((hi.z - lo.z) / 1.6))
			for i in nx + 1:
				for k in nz + 1:
					if i != 0 and i != nx and k != 0 and k != nz:
						continue
					var p := Vector3(lerpf(lo.x + 0.08, hi.x - 0.08, float(i) / nx), 0, lerpf(lo.z + 0.08, hi.z - 0.08, float(k) / nz))
					cyl(post_mat, p + Vector3(0, -0.6, 0), p + Vector3(0, y - 0.05, 0), 0.08, 7)

func railing(a: Vector3, b: Vector3, h := 0.9, mat := "oak", spacing := 0.5, balusters := true) -> void:
	var d := b - a
	var n := maxi(1, roundi(d.length() / spacing))
	for i in n + 1:
		var p := a.lerp(b, float(i) / n)
		if i == 0 or i == n or i % 3 == 0:
			beam(mat, p, p + Vector3(0, h + 0.05, 0), 0.1, 0.1)
		elif balusters:
			beam(mat, p, p + Vector3(0, h, 0), 0.05, 0.05)
	beam(mat, a + Vector3(0, h, 0), b + Vector3(0, h, 0), 0.08, 0.1)
	beam(mat, a + Vector3(0, h * 0.45, 0), b + Vector3(0, h * 0.45, 0), 0.05, 0.07)

func fence(a: Vector3, b: Vector3, h := 0.85, mat := "oak", post_every := 1.4) -> void:
	var d := b - a
	var n := maxi(1, roundi(d.length() / post_every))
	for i in n + 1:
		var p := a.lerp(b, float(i) / n)
		cyl(mat, p + Vector3(0, -0.1, 0), p + Vector3(0, h + 0.06, 0), 0.06, 6)
	for y in [h * 0.38, h * 0.8]:
		beam(mat, a + Vector3(0, y, 0), b + Vector3(0, y, 0), 0.05, 0.1, jitter(0.1))

func palisade(a: Vector3, b: Vector3, h := 2.0, r := 0.12, mat := "oak") -> void:
	var d := b - a
	var n := maxi(2, roundi(d.length() / (r * 2.05)))
	for i in n:
		var p := a.lerp(b, (i + 0.5) / n)
		var hh := h * rng.randf_range(0.94, 1.04)
		var tn := jitter(0.1)
		cyl(mat, p + Vector3(0, -0.1, 0), p + Vector3(0, hh, 0), r, 7, false, tn)
		cone(mat, p + Vector3(0, hh, 0), r, r * 2.4, 7, tn * Color(1.1, 1.05, 0.95))
	var side := Vector3(d.z, 0, -d.x).normalized()
	for y in [h * 0.3, h * 0.72]:
		beam("dark_oak", a + Vector3(0, y, 0) - side * (r + 0.05), b + Vector3(0, y, 0) - side * (r + 0.05), 0.08, 0.14)

func ground(from: Vector3, to: Vector3, mat := "earth", y := 0.03, tint := Color.WHITE) -> void:
	## Flat surfacing slab that also skirts down below grade (terrain is not perfectly level).
	box(mat, Vector3((from.x + to.x) * 0.5, y - 0.2, (from.z + to.z) * 0.5), Vector3(absf(to.x - from.x), 0.4, absf(to.z - from.z)), 0, tint)

func paving(from: Vector3, to: Vector3, y := 0.05, size := 0.55, mat := "stone_light") -> void:
	## Individually set flagstones (reads as paving at gameplay zoom).
	ground(from, to, "earth", y - 0.025, Color(0.8, 0.78, 0.75))
	var lo := Vector3(minf(from.x, to.x), 0, minf(from.z, to.z))
	var hi := Vector3(maxf(from.x, to.x), 0, maxf(from.z, to.z))
	var nz := maxi(1, roundi((hi.z - lo.z) / size))
	for k in nz:
		var z0 := lerpf(lo.z, hi.z, float(k) / nz)
		var z1 := lerpf(lo.z, hi.z, float(k + 1) / nz)
		var nx := maxi(1, roundi((hi.x - lo.x) / (size * rng.randf_range(0.9, 1.3))))
		var off := 0.5 if k % 2 == 1 else 0.0
		for i in nx + 1:
			var x0 := clampf(lerpf(lo.x, hi.x, (i - off) / nx), lo.x, hi.x)
			var x1 := clampf(lerpf(lo.x, hi.x, (i + 1 - off) / nx), lo.x, hi.x)
			if x1 - x0 < 0.05:
				continue
			box(mat, Vector3((x0 + x1) * 0.5, y - 0.02, (z0 + z1) * 0.5), Vector3(x1 - x0 - 0.035, 0.05, z1 - z0 - 0.035), 0, jitter(0.09))

# ---------------------------------------------------------------- props
func crate(c: Vector3, s := 0.55, yaw := 0.0) -> void:
	box("oak", c + Vector3(0, s * 0.5, 0), Vector3(s, s, s), yaw, jitter(0.1))
	push_at(c, yaw)
	for z in [-1.0, 1.0]:
		beam("dark_oak", Vector3(-s * 0.5, 0.04, z * s * 0.51), Vector3(s * 0.5, s - 0.04, z * s * 0.51), 0.06, 0.02)
	box("dark_oak", Vector3(0, s - 0.03, 0), Vector3(s + 0.02, 0.05, s + 0.02))
	pop()

func barrel(c: Vector3, h := 0.75, r := 0.27) -> void:
	cyl("oak", c, c + Vector3(0, h * 0.5, 0), r * 0.86, 10, false, jitter(0.1), r)
	cyl("oak", c + Vector3(0, h * 0.5, 0), c + Vector3(0, h, 0), r, 10, true, jitter(0.1), r * 0.86)
	for y in [0.12, 0.5, 0.88]:
		cyl("iron", c + Vector3(0, h * y - 0.025, 0), c + Vector3(0, h * y + 0.025, 0), r * (0.9 if y != 0.5 else 1.01) + 0.012, 10, false)

func sack(c: Vector3, yaw := 0.0) -> void:
	box("canvas", c + Vector3(0, 0.2, 0), Vector3(0.42, 0.4, 0.3), yaw, jitter(0.08))
	box("canvas", c + Vector3(0, 0.44, 0), Vector3(0.2, 0.1, 0.16), yaw)

func log_pile(c: Vector3, length := 2.6, rows := 3, r := 0.2, yaw := 0.0, mat := "log") -> void:
	## Pyramid stack of round logs (end grain visible).
	push_at(c, yaw)
	for row in rows:
		var n := rows - row + 1
		for i in n:
			var x := (i - (n - 1) * 0.5) * r * 2.05
			var y := r + row * r * 1.75
			var zj := rng.randf_range(-0.12, 0.12)
			cyl(mat, Vector3(x, y, -length * 0.5 + zj), Vector3(x, y, length * 0.5 + zj), r * rng.randf_range(0.9, 1.05), 9, true, jitter(0.1))
	# chocks
	for s in [-1.0, 1.0]:
		box("dark_oak", Vector3(s * (r * (rows + 1) * 1.05 + 0.08), 0.18, 0), Vector3(0.12, 0.36, 0.16))
	pop()

func plank_stack(c: Vector3, length := 2.2, w := 0.9, layers := 6, yaw := 0.0) -> void:
	push_at(c, yaw)
	for y in layers:
		var n := 4
		for i in n:
			box("plank", Vector3(-w * 0.5 + w * (i + 0.5) / n, 0.1 + y * 0.07 + 0.035, 0), Vector3(w / n - 0.02, 0.06, length * rng.randf_range(0.96, 1.0)), 0, jitter(0.07))
		if y % 3 == 0:
			for z in [-length * 0.38, 0.0, length * 0.38]:
				box("dark_oak", Vector3(0, 0.1 + y * 0.07, z), Vector3(w + 0.06, 0.03, 0.06))
	box("dark_oak", Vector3(0, 0.05, 0), Vector3(w + 0.1, 0.1, length * 0.9))
	pop()

func stone_block(c: Vector3, size: Vector3, yaw := 0.0, rough := false) -> void:
	box("stone_rough" if rough else "stone_light", c + Vector3(0, size.y * 0.5, 0), size, yaw, jitter(0.07))

func table(c: Vector3, lx := 1.4, lz := 0.75, h := 0.8, yaw := 0.0, top_mat := "oak") -> void:
	push_at(c, yaw)
	box(top_mat, Vector3(0, h - 0.04, 0), Vector3(lx, 0.08, lz), 0, jitter(0.06))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			beam("dark_oak", Vector3(sx * (lx * 0.5 - 0.1), 0, sz * (lz * 0.5 - 0.08)), Vector3(sx * (lx * 0.5 - 0.1), h - 0.08, sz * (lz * 0.5 - 0.08)), 0.08, 0.08)
	beam("dark_oak", Vector3(-(lx * 0.5 - 0.1), 0.25, 0), Vector3(lx * 0.5 - 0.1, 0.25, 0), 0.05, 0.06)
	pop()

func map_table(c: Vector3, lx := 2.0, lz := 1.3, yaw := 0.0) -> void:
	## Large pale table with a campaign map (parchment, routes and unit markers).
	table(c, lx, lz, 0.85, yaw, "oak_light")
	push_at(c, yaw)
	box("parchment", Vector3(0, 0.86, 0), Vector3(lx * 0.86, 0.015, lz * 0.82), 0)
	# terrain patches and routes on the map
	box("map_green", Vector3(-lx * 0.18, 0.871, -lz * 0.1), Vector3(lx * 0.3, 0.006, lz * 0.34), 12)
	box("map_blue", Vector3(lx * 0.12, 0.871, lz * 0.05), Vector3(lx * 0.06, 0.006, lz * 0.7), -20)
	box("cloth_red", Vector3(lx * 0.0, 0.873, -lz * 0.22), Vector3(lx * 0.5, 0.006, 0.025), 8)
	for p in [Vector3(-0.3, 0, 0.12), Vector3(0.25, 0, -0.2), Vector3(0.4, 0, 0.22), Vector3(-0.1, 0, -0.25)]:
		cyl("cloth_red" if p.x > 0 else "cloth_blue", Vector3(p.x * lx * 0.8, 0.87, p.z * lz * 1.2), Vector3(p.x * lx * 0.8, 0.95, p.z * lz * 1.2), 0.035, 6)
	pop()

func bench(c: Vector3, l := 1.4, yaw := 0.0) -> void:
	push_at(c, yaw)
	box("oak", Vector3(0, 0.44, 0), Vector3(l, 0.07, 0.32), 0, jitter(0.08))
	for s in [-1.0, 1.0]:
		box("dark_oak", Vector3(s * (l * 0.5 - 0.12), 0.21, 0), Vector3(0.08, 0.42, 0.28))
	pop()

func workbench(c: Vector3, l := 1.8, yaw := 0.0, tools := true) -> void:
	push_at(c, yaw)
	box("oak", Vector3(0, 0.84, 0), Vector3(l, 0.12, 0.7), 0, jitter(0.06))
	box("dark_oak", Vector3(0, 0.25, 0), Vector3(l - 0.15, 0.06, 0.55))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			box("dark_oak", Vector3(sx * (l * 0.5 - 0.1), 0.39, sz * 0.27), Vector3(0.12, 0.78, 0.12))
	if tools:
		box("iron", Vector3(-l * 0.25, 0.93, 0.05), Vector3(0.35, 0.05, 0.08), 20)
		box("dark_oak", Vector3(l * 0.2, 0.93, -0.1), Vector3(0.5, 0.04, 0.06), -10)
		box("plank", Vector3(l * 0.05, 0.94, 0.12), Vector3(0.7, 0.06, 0.2), 4)
	pop()

func sawhorse(c: Vector3, yaw := 0.0) -> void:
	push_at(c, yaw)
	for s in [-1.0, 1.0]:
		beam("oak", Vector3(s * 0.45, 0, -0.25), Vector3(s * 0.45, 0.7, 0.0), 0.07, 0.07)
		beam("oak", Vector3(s * 0.45, 0, 0.25), Vector3(s * 0.45, 0.7, 0.0), 0.07, 0.07)
	beam("oak", Vector3(-0.6, 0.7, 0), Vector3(0.6, 0.7, 0), 0.1, 0.1)
	pop()

func weapon_rack(c: Vector3, l := 1.6, yaw := 0.0) -> void:
	push_at(c, yaw)
	for s in [-1.0, 1.0]:
		beam("dark_oak", Vector3(s * l * 0.5, 0, 0), Vector3(s * l * 0.5, 1.5, 0), 0.09, 0.09)
	beam("dark_oak", Vector3(-l * 0.5, 1.35, 0), Vector3(l * 0.5, 1.35, 0), 0.07, 0.07)
	beam("dark_oak", Vector3(-l * 0.5, 0.3, 0.08), Vector3(l * 0.5, 0.3, 0.08), 0.06, 0.06)
	var n := roundi(l / 0.22)
	for i in n:
		var x := -l * 0.5 + 0.12 + (l - 0.24) * i / maxf(1, n - 1)
		beam("oak_light", Vector3(x, 0.25, 0.1), Vector3(x + 0.05, 1.75, -0.02), 0.04, 0.04)
		cone("iron", Vector3(x + 0.05, 1.75, -0.02), 0.04, 0.18, 4)
	pop()

func dummy(c: Vector3, yaw := 0.0) -> void:
	push_at(c, yaw)
	cyl("dark_oak", Vector3(0, 0, 0), Vector3(0, 1.75, 0), 0.06, 6)
	cyl("canvas", Vector3(0, 0.75, 0), Vector3(0, 1.4, 0), 0.2, 8, true, Color(0.92, 0.85, 0.7))
	cyl("canvas", Vector3(0, 1.42, 0), Vector3(0, 1.66, 0), 0.12, 8, true, Color(0.95, 0.88, 0.72))
	beam("dark_oak", Vector3(-0.42, 1.28, 0), Vector3(0.42, 1.28, 0), 0.06, 0.06)
	box("dark_oak", Vector3(0, 0.03, 0), Vector3(0.5, 0.06, 0.5))
	pop()

func banner(c: Vector3, w := 0.6, h := 1.0, mat := "cloth_red", yaw := 0.0, emblem := true) -> void:
	push_at(c, yaw)
	beam("dark_oak", Vector3(-w * 0.6, 0, 0.04), Vector3(w * 0.6, 0, 0.04), 0.05, 0.05)
	var pr := PackedVector2Array([Vector2(-w * 0.5, 0), Vector2(-w * 0.5, -h), Vector2(0, -h - w * 0.3), Vector2(w * 0.5, -h), Vector2(w * 0.5, 0)])
	pr.reverse()
	extrude(mat, pr, 0.0, 0.025)
	if emblem:
		box("brass", Vector3(0, -h * 0.45, 0.03), Vector3(w * 0.36, w * 0.36, 0.01), 0, Color.WHITE, 0, 45)
	pop()

func flag_pole(c: Vector3, h := 4.0, mat := "cloth_red") -> void:
	cyl("dark_oak", c, c + Vector3(0, h, 0), 0.06, 6)
	var pr := PackedVector2Array([Vector2(0, h - 0.05), Vector2(0, h - 0.65), Vector2(0.9, h - 0.45), Vector2(0.75, h - 0.35), Vector2(0.95, h - 0.2)])
	push_at(c)
	extrude(mat, pr, -0.012, 0.012)
	pop()

func lantern(c: Vector3) -> void:
	box("iron", c + Vector3(0, 0.12, 0), Vector3(0.16, 0.04, 0.16))
	box("glow", c, Vector3(0.12, 0.2, 0.12))
	box("iron", c + Vector3(0, -0.12, 0), Vector3(0.14, 0.03, 0.14))

func chimney(base: Vector3, h: float, w := 0.6) -> void:
	box("stone", base + Vector3(0, h * 0.5, 0), Vector3(w, h, w), 0, jitter(0.04))
	box("stone", base + Vector3(0, h + 0.07, 0), Vector3(w + 0.14, 0.14, w + 0.14), 0, Color(1.1, 1.08, 1.04))
	box("soot", base + Vector3(0, h + 0.15, 0), Vector3(w - 0.2, 0.04, w - 0.2))

func wheel(c: Vector3, r := 0.55, axis := Vector3.RIGHT, mat := "dark_oak") -> void:
	var u := axis.cross(Vector3.UP if absf(axis.dot(Vector3.UP)) < 0.9 else Vector3.FORWARD).normalized()
	var v := axis.cross(u).normalized()
	var seg := 14
	for i in seg:
		var a0 := TAU * i / seg
		var a1 := TAU * (i + 1) / seg
		beam(mat, c + (u * cos(a0) + v * sin(a0)) * r, c + (u * cos(a1) + v * sin(a1)) * r, 0.08, 0.1)
	for i in 6:
		var a := TAU * i / 6
		beam(mat, c, c + (u * cos(a) + v * sin(a)) * r, 0.05, 0.05)
	cyl("iron", c - axis * 0.08, c + axis * 0.08, 0.09, 8)

func hook_hoist(top: Vector3, drop: float) -> void:
	## Rope, pulley block and iron hook hanging from 'top'.
	cyl("iron", top + Vector3(0, -0.05, -0.1), top + Vector3(0, -0.05, 0.1), 0.14, 10)
	cyl("rope", top + Vector3(0, -0.15, 0), top + Vector3(0, -drop, 0), 0.025, 5, false)
	box("iron", top + Vector3(0, -drop - 0.08, 0), Vector3(0.12, 0.16, 0.08))
	var hk := top + Vector3(0, -drop - 0.16, 0)
	beam("iron", hk, hk + Vector3(0, -0.2, 0), 0.04, 0.04)
	beam("iron", hk + Vector3(0, -0.2, 0), hk + Vector3(0.14, -0.12, 0), 0.04, 0.04)

func cart(c: Vector3, yaw := 0.0, load := "") -> void:
	push_at(c, yaw)
	box("oak", Vector3(0, 0.62, 0), Vector3(1.0, 0.08, 1.6), 0, jitter(0.06))
	for s in [-1.0, 1.0]:
		box("oak", Vector3(s * 0.5, 0.82, 0), Vector3(0.06, 0.35, 1.6))
		wheel(Vector3(s * 0.62, 0.45, 0), 0.45, Vector3.RIGHT)
	box("oak", Vector3(0, 0.82, 0.8), Vector3(1.0, 0.35, 0.06))
	beam("dark_oak", Vector3(-0.3, 0.55, 0.8), Vector3(-0.3, 0.35, 2.0), 0.07, 0.07)
	beam("dark_oak", Vector3(0.3, 0.55, 0.8), Vector3(0.3, 0.35, 2.0), 0.07, 0.07)
	if load == "logs":
		for i in 3:
			cyl("log", Vector3(-0.28 + i * 0.28, 0.82, -0.9), Vector3(-0.28 + i * 0.28, 0.82, 0.9), 0.13, 8)
	elif load == "stone":
		stone_block(Vector3(-0.2, 0.66, 0.1), Vector3(0.45, 0.35, 0.5), 8)
		stone_block(Vector3(0.22, 0.66, -0.3), Vector3(0.4, 0.3, 0.45), -6)
	elif load == "ore":
		box("ore", Vector3(0, 0.8, 0), Vector3(0.85, 0.3, 1.4), 0, jitter(0.1))
	pop()

func anvil(c: Vector3, yaw := 0.0, scale_value := 1.0) -> void:
	push_at(c, yaw, scale_value)
	cyl("log", Vector3(0, 0, 0), Vector3(0, 0.5, 0), 0.26, 9)
	box("iron", Vector3(0, 0.58, 0), Vector3(0.28, 0.16, 0.22))
	box("iron", Vector3(0, 0.72, 0), Vector3(0.62, 0.14, 0.24))
	extrude("iron", PackedVector2Array([Vector2(0.31, 0.65), Vector2(0.55, 0.76), Vector2(0.31, 0.79)]), -0.06, 0.06)
	pop()

func forge(c: Vector3, w := 1.6, d := 1.2, yaw := 0.0) -> void:
	push_at(c, yaw)
	box("stone", Vector3(0, 0.45, 0), Vector3(w, 0.9, d), 0, jitter(0.04))
	box("ember", Vector3(0, 0.92, 0.05), Vector3(w * 0.6, 0.06, d * 0.55))
	box("stone_light", Vector3(0, 0.93, 0), Vector3(w + 0.1, 0.06, d + 0.1))
	# hood
	var pr := PackedVector2Array([Vector2(-w * 0.55, 1.6), Vector2(w * 0.55, 1.6), Vector2(w * 0.2, 2.4), Vector2(-w * 0.2, 2.4)])
	extrude("stone", pr, -d * 0.45, d * 0.25)
	pop()

func bed(c: Vector3, yaw := 0.0) -> void:
	push_at(c, yaw)
	box("dark_oak", Vector3(0, 0.3, 0), Vector3(0.85, 0.12, 1.9))
	box("linen", Vector3(0, 0.42, 0.05), Vector3(0.78, 0.12, 1.75), 0, Color(1, 1, 1))
	box("linen", Vector3(0, 0.5, -0.7), Vector3(0.6, 0.1, 0.32), 0, Color(1.05, 1.05, 1.05))
	box("cloth_red", Vector3(0, 0.49, 0.35), Vector3(0.8, 0.03, 0.9))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			box("dark_oak", Vector3(sx * 0.38, 0.15, sz * 0.88), Vector3(0.07, 0.3, 0.07))
	pop()

func stretcher(c: Vector3, yaw := 0.0) -> void:
	push_at(c, yaw)
	for s in [-1.0, 1.0]:
		beam("oak", Vector3(s * 0.3, 0.42, -1.1), Vector3(s * 0.3, 0.42, 1.1), 0.05, 0.05)
		for z in [-0.75, 0.75]:
			beam("dark_oak", Vector3(s * 0.3, 0, z), Vector3(s * 0.3, 0.42, z), 0.05, 0.05)
	box("canvas", Vector3(0, 0.45, 0), Vector3(0.6, 0.02, 1.6), 0, Color(1.1, 1.08, 1.0))
	pop()

func bush(c: Vector3, r := 0.45, mat := "leaves") -> void:
	for i in 4:
		var o := Vector3(rng.randf_range(-r, r) * 0.5, r * rng.randf_range(0.6, 0.9), rng.randf_range(-r, r) * 0.5)
		box(mat, c + o, Vector3.ONE * r * rng.randf_range(0.8, 1.15), rng.randf_range(0, 90), jitter(0.12), rng.randf_range(-20, 20))

func garden_bed(from: Vector3, to: Vector3, plant := "leaves", rows := 3, frame := true) -> void:
	var lo := Vector3(minf(from.x, to.x), 0, minf(from.z, to.z))
	var hi := Vector3(maxf(from.x, to.x), 0, maxf(from.z, to.z))
	if frame:
		box("oak", Vector3((lo.x + hi.x) * 0.5, 0.12, lo.z), Vector3(hi.x - lo.x, 0.24, 0.07))
		box("oak", Vector3((lo.x + hi.x) * 0.5, 0.12, hi.z), Vector3(hi.x - lo.x, 0.24, 0.07))
		box("oak", Vector3(lo.x, 0.12, (lo.z + hi.z) * 0.5), Vector3(0.07, 0.24, hi.z - lo.z))
		box("oak", Vector3(hi.x, 0.12, (lo.z + hi.z) * 0.5), Vector3(0.07, 0.24, hi.z - lo.z))
	box("soil", Vector3((lo.x + hi.x) * 0.5, 0.1, (lo.z + hi.z) * 0.5), Vector3(hi.x - lo.x - 0.06, 0.2, hi.z - lo.z - 0.06))
	for r in rows:
		var z := lerpf(lo.z + 0.2, hi.z - 0.2, (r + 0.5) / rows)
		var n := maxi(2, roundi((hi.x - lo.x) / 0.32))
		for i in n:
			var x := lerpf(lo.x + 0.18, hi.x - 0.18, (i + 0.5) / n)
			var s := rng.randf_range(0.16, 0.26)
			box(plant, Vector3(x, 0.2 + s * 0.5, z), Vector3(s, s, s), rng.randf_range(0, 90), jitter(0.15))

func crane(base: Vector3, mast_h: float, jib: Vector3, drop: float) -> void:
	## Timber hoisting crane: mast with braces, jib arm to 'jib' (relative), hook.
	beam("oak", base, base + Vector3(0, mast_h, 0), 0.24, 0.24)
	for s in [Vector3(0.7, 0, 0), Vector3(-0.7, 0, 0), Vector3(0, 0, 0.7), Vector3(0, 0, -0.7)]:
		beam("oak", base + s, base + Vector3(0, mast_h * 0.45, 0), 0.12, 0.12)
	var tip := base + Vector3(0, mast_h, 0) + jib
	beam("oak", base + Vector3(0, mast_h - 0.2, 0), tip, 0.2, 0.2)
	beam("dark_oak", base + Vector3(0, mast_h * 0.6, 0), base + Vector3(0, mast_h, 0) + jib * 0.55, 0.1, 0.1)
	hook_hoist(tip + Vector3(0, -0.1, 0), drop)

# ---------------------------------------------------------------- composite buildings
func timber_house(c: Vector3, lx: float, lz: float, h: float, rise: float, front: Array = [], back: Array = [], left: Array = [], right: Array = [], roof := "shingle", infill := "plaster", plinth_h := 0.45, stone_lower := 0.0) -> void:
	## Rectangular timber-framed volume; walls start on a stone plinth.
	var x0 := c.x - lx * 0.5
	var x1 := c.x + lx * 0.5
	var z0 := c.z - lz * 0.5
	var z1 := c.z + lz * 0.5
	var y := c.y
	box("stone", Vector3(c.x, y + plinth_h * 0.5 - 0.15, c.z), Vector3(lx + 0.2, plinth_h + 0.3, lz + 0.2), 0, jitter(0.04))
	var wy := y + plinth_h
	var wh := h - plinth_h
	if stone_lower > 0.0:
		stone_wall(Vector3(x0, wy, z1), Vector3(x1, wy, z1), stone_lower, 0.26, "stone", [], true, false)
		stone_wall(Vector3(x1, wy, z0), Vector3(x0, wy, z0), stone_lower, 0.26, "stone", [], true, false)
		stone_wall(Vector3(x0, wy, z0), Vector3(x0, wy, z1), stone_lower, 0.26, "stone", [], true, false)
		stone_wall(Vector3(x1, wy, z1), Vector3(x1, wy, z0), stone_lower, 0.26, "stone", [], true, false)
	timber_wall(Vector3(x0, wy, z1), Vector3(x1, wy, z1), wh, front, infill)
	timber_wall(Vector3(x1, wy, z0), Vector3(x0, wy, z0), wh, back, infill)
	timber_wall(Vector3(x0, wy, z0), Vector3(x0, wy, z1), wh, left, infill)
	timber_wall(Vector3(x1, wy, z1), Vector3(x1, wy, z0), wh, right, infill)
	gable_roof(roof, Vector3(c.x, y + h, c.z), lx, lz, rise, 0.4, infill)
	gable_frame(Vector3(c.x, y + h, c.z), lx, lz, rise)

func open_shed(c: Vector3, lx: float, lz: float, h: float, rise: float, roof := "shingle", posts_x := 3, posts_z := 2, ridge_x := true, braces := true) -> void:
	## Posts + beams + gable roof, open on all sides (work bays, pavilions).
	for i in posts_x:
		for k in posts_z:
			if i != 0 and i != posts_x - 1 and k != 0 and k != posts_z - 1:
				continue
			var p := Vector3(c.x - lx * 0.5 + lx * i / maxf(1, posts_x - 1), c.y, c.z - lz * 0.5 + lz * k / maxf(1, posts_z - 1))
			box("stone", p + Vector3(0, 0.1, 0), Vector3(0.36, 0.2, 0.36))
			beam("oak", p + Vector3(0, 0.2, 0), p + Vector3(0, h, 0), 0.22, 0.22)
	for k in [0, posts_z - 1]:
		var z: float = c.z - lz * 0.5 + lz * k / maxf(1, posts_z - 1)
		beam("oak", Vector3(c.x - lx * 0.5 - 0.15, c.y + h, z), Vector3(c.x + lx * 0.5 + 0.15, c.y + h, z), 0.2, 0.24)
		if braces:
			for i in posts_x:
				var x := c.x - lx * 0.5 + lx * i / maxf(1, posts_x - 1)
				if i > 0:
					beam("oak", Vector3(x, c.y + h - 0.7, z), Vector3(x - 0.6, c.y + h - 0.05, z), 0.1, 0.1)
				if i < posts_x - 1:
					beam("oak", Vector3(x, c.y + h - 0.7, z), Vector3(x + 0.6, c.y + h - 0.05, z), 0.1, 0.1)
	for i in [0, posts_x - 1]:
		var x: float = c.x - lx * 0.5 + lx * i / maxf(1, posts_x - 1)
		beam("oak", Vector3(x, c.y + h, c.z - lz * 0.5), Vector3(x, c.y + h, c.z + lz * 0.5), 0.18, 0.2)
	if ridge_x:
		gable_roof(roof, Vector3(c.x, c.y + h + 0.12, c.z), lx, lz, rise, 0.4)
		gable_frame(Vector3(c.x, c.y + h + 0.12, c.z), lx, lz, rise)
	else:
		push_at(Vector3(c.x, 0, c.z), 90)
		gable_roof(roof, Vector3(0, c.y + h + 0.12, 0), lz, lx, rise, 0.4)
		gable_frame(Vector3(0, c.y + h + 0.12, 0), lz, lx, rise)
		pop()

func lean_to(c: Vector3, lx: float, lz: float, h_low: float, h_high: float, roof := "shingle", posts := 3) -> void:
	## Mono-pitch roof on posts: high side at -Z, low side at +Z.
	var count := posts if posts > 0 else maxi(2, roundi(lx / 1.6) + 1)
	for i in count:
		var x := c.x - lx * 0.5 + lx * i / maxf(1, count - 1)
		if posts > 0:
			beam("oak", Vector3(x, c.y, c.z + lz * 0.5), Vector3(x, c.y + h_low, c.z + lz * 0.5), 0.18, 0.18)
		beam("oak", Vector3(x, c.y, c.z - lz * 0.5), Vector3(x, c.y + h_high, c.z - lz * 0.5), 0.18, 0.18)
		beam("oak", Vector3(x, c.y + h_low, c.z + lz * 0.5 + 0.2), Vector3(x, c.y + h_high, c.z - lz * 0.5 - 0.1), 0.12, 0.16)
	beam("oak", Vector3(c.x - lx * 0.5 - 0.2, c.y + h_high, c.z - lz * 0.5), Vector3(c.x + lx * 0.5 + 0.2, c.y + h_high, c.z - lz * 0.5), 0.16, 0.2)
	beam("oak", Vector3(c.x - lx * 0.5 - 0.2, c.y + h_low, c.z + lz * 0.5), Vector3(c.x + lx * 0.5 + 0.2, c.y + h_low, c.z + lz * 0.5), 0.16, 0.2)
	var o := 0.35
	var drop := (h_high - h_low) * o / lz
	shingle_slope(roof, Vector3(c.x - lx * 0.5 - o, c.y + h_low + 0.1 - drop, c.z + lz * 0.5 + o), Vector3(c.x + lx * 0.5 + o, c.y + h_low + 0.1 - drop, c.z + lz * 0.5 + o), Vector3(c.x - lx * 0.5 - o, c.y + h_high + 0.1, c.z - lz * 0.5), Vector3(c.x + lx * 0.5 + o, c.y + h_high + 0.1, c.z - lz * 0.5))

func ground_poly(points: PackedVector2Array, mat := "path", y := 0.02, tint := Color.WHITE) -> void:
	## Irregular flat surfacing (x, z points, counter-clockwise seen from above) skirting below grade.
	var pr := PackedVector2Array()
	for p in points:
		pr.append(Vector2(p.x, -p.y))
	push(Transform3D(Basis(Vector3.RIGHT, -PI * 0.5), Vector3(0, y, 0)))
	extrude(mat, pr, -0.3, 0.0, tint)
	pop()

func road(from: Vector3, to: Vector3, width: float, mat := "path", y := 0.02, flare := 0.6) -> void:
	## Wobbly-edged track from 'from' to 'to'; ends flare out and fade into the grass.
	var d := Vector3(to.x - from.x, 0, to.z - from.z)
	var dir := d.normalized()
	var side := Vector3(dir.z, 0, -dir.x)
	var n := maxi(4, roundi(d.length() / 0.8))
	var left := PackedVector2Array()
	var right := PackedVector2Array()
	for i in n + 1:
		var t := float(i) / n
		var p := from.lerp(to, t)
		var w := width * 0.5 + flare * pow(absf(t - 0.5) * 2.0, 3.0) + rng.randf_range(-0.12, 0.12)
		var a := p + side * w
		var b := p - side * (w + rng.randf_range(-0.1, 0.1))
		left.append(Vector2(a.x, a.z))
		right.append(Vector2(b.x, b.z))
	right.reverse()
	var poly := left + right
	if Geometry2D.is_polygon_clockwise(poly):
		poly.reverse()
	ground_poly(poly, mat, y)

func base_ground(radius := 6.0, mat := "earth") -> void:
	## Irregular packed-earth apron so the level reads as one composed lot.
	var pts := PackedVector2Array()
	var n := 18
	for i in n:
		var a := TAU * i / n
		var rr := radius * rng.randf_range(0.9, 1.0)
		pts.append(Vector2(cos(a) * rr, -sin(a) * rr))
	push(Transform3D(Basis(Vector3.RIGHT, -PI * 0.5), Vector3(0, 0.0, 0)))
	extrude(mat, pts, -0.02, 0.025, Color(1, 1, 1))
	pop()

# ---------------------------------------------------------------- bake
func bake() -> ArrayMesh:
	var mesh := ArrayMesh.new()
	var names := groups.keys()
	names.sort()
	for mat_name in names:
		var g: Dictionary = groups[mat_name]
		if g.v.is_empty():
			continue
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = g.v
		arrays[Mesh.ARRAY_NORMAL] = g.n
		arrays[Mesh.ARRAY_COLOR] = g.c
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var idx := mesh.get_surface_count() - 1
		mesh.surface_set_name(idx, mat_name)
		mesh.surface_set_material(idx, load(MAT_DIR + mat_name + ".tres"))
	return mesh

func triangle_count() -> int:
	var t := 0
	for k in groups:
		t += groups[k].v.size() / 3
	return t
