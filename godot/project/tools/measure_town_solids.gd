extends SceneTree

# Where a person cannot stand around each building (build 1024, src/townsfolk.gd): every
# building type at levels I-V, as the city draws it (base model x level scale, or the reworked
# level scene), rasterised on a 0.25 m grid around the plot centre. A cell is solid where any
# triangle of the building lies between SOLID_LOW and SOLID_HIGH above the plot ground (walls,
# fences, posts, stairs, beds, stalls; not flat paving, not eaves above head height), then grown
# by one cell (the walker's body). The footprint table (tools/measure_footprints.gd) is the box
# round the whole model; this is the ground the model really takes.
#   godot --headless --path . -s tools/measure_town_solids.gd            # print
#   godot --headless --path . -s tools/measure_town_solids.gd -- --write  # update the table
#   godot --headless --path . -s tools/measure_town_solids.gd -- --check  # exit 1 if stale

const TABLE := "res://assets/city/town_solids.json"
const MeasureFootprints = preload("res://tools/measure_footprints.gd")
const CELL := 0.25
const SOLID_LOW := 0.15
const SOLID_HIGH := 2.0
const GROW := 1
## «Walls and gate» is only drawn as the wall's main gate, which stands on the wall line at its
## own height (often above the avenue inside): its foundations and ramps below the scene's
## origin are solid too.
const GATE_LOW := -3.0
## Where a plot stands on a slope, a street beside it can be lower than the building's base:
## there its low parts (plinths, steps, paving) stand at shin height. The "base" mask counts
## everything from BASE_LOW up; the townsfolk use it where their feet are below the plot.
const BASE_LOW := -0.6
## The gate also gets the height of what stands in each cell ("spans": lowest and highest point
## of its geometry from GATE_LOW to SPAN_HIGH, scene units, grown by GROW cells): the town knows
## the ground height where the gate is placed, so its flat paving at street level is walked and
## only what stands between the knees and the head of a walker there blocks (build 1024 rework).
const SPAN_HIGH := 2.4
## A building that draws its own square (the market from level III, TownPlan.OWN_SQUARE) is
## walked on that square: "floor" holds, per cell, the top of its upward-facing surfaces from
## FLOOR_LOW to FLOOR_HIGH above the plot (bytes as the spans; 0: no floor).
const FLOOR_LOW := -0.6
const FLOOR_HIGH := 0.25
const TownPlan = preload("res://src/town_plan.gd")
const SPAN_BASE := -3.2
const SPAN_STEP := 0.025

func _initialize() -> void:
	call_deferred("run")

func collect(node: Node3D, parent: Transform3D, out: Array) -> void:
	var here := parent * node.transform
	if node is MeshInstance3D and node.mesh != null and node.visible:
		out.append([node.mesh, here])
	for child in node.get_children():
		if child is Node3D:
			collect(child, here, out)

static func clip(poly: PackedVector3Array, level: float, keep_above: bool) -> PackedVector3Array:
	var out := PackedVector3Array()
	var count := poly.size()
	for i in count:
		var a := poly[i]
		var b := poly[(i + 1) % count]
		var a_in := a.y >= level if keep_above else a.y <= level
		var b_in := b.y >= level if keep_above else b.y <= level
		if a_in:
			out.append(a)
		if a_in != b_in:
			var t := (level - a.y) / (b.y - a.y)
			out.append(a.lerp(b, t))
	return out

func measure(path: String, scale: float, bottom := SOLID_LOW) -> Dictionary:
	var scene: Node3D = load(path).instantiate()
	scene.scale = Vector3.ONE * scale
	var meshes: Array = []
	collect(scene, Transform3D.IDENTITY, meshes)
	var cells := {}
	for entry: Array in meshes:
		var mesh: Mesh = entry[0]
		var xf: Transform3D = entry[1]
		var faces: PackedVector3Array = xf * mesh.get_faces()
		for f in range(0, faces.size(), 3):
			var a := faces[f]
			var b := faces[f + 1]
			var c := faces[f + 2]
			if maxf(a.y, maxf(b.y, c.y)) < bottom or minf(a.y, minf(b.y, c.y)) > SOLID_HIGH:
				continue
			var poly := clip(clip(PackedVector3Array([a, b, c]), bottom, true), SOLID_HIGH, false)
			if poly.size() < 2:
				continue
			var flat := PackedVector2Array()
			var low := Vector2(INF, INF)
			var high := Vector2(-INF, -INF)
			for v in poly:
				var q := Vector2(v.x, v.z)
				flat.append(q)
				low = low.min(q)
				high = high.max(q)
			var x0 := floori(low.x / CELL)
			var x1 := floori(high.x / CELL)
			var z0 := floori(low.y / CELL)
			var z1 := floori(high.y / CELL)
			var area := 0.0
			for i in flat.size():
				area += flat[i].cross(flat[(i + 1) % flat.size()])
			for cz in range(z0, z1 + 1):
				for cx in range(x0, x1 + 1):
					var key := Vector2i(cx, cz)
					if cells.has(key):
						continue
					var centre := Vector2((cx + 0.5) * CELL, (cz + 0.5) * CELL)
					var hit := absf(area) > 0.0001 and Geometry2D.is_point_in_polygon(centre, flat)
					if not hit:
						for i in flat.size():
							var q := Geometry2D.get_closest_point_to_segment(centre, flat[i], flat[(i + 1) % flat.size()])
							if absf(q.x - centre.x) <= CELL * 0.5 and absf(q.y - centre.y) <= CELL * 0.5:
								hit = true
								break
					if hit:
						cells[key] = true
	scene.free()
	if cells.is_empty():
		return {"x0": 0, "z0": 0, "w": 0, "h": 0, "bits": ""}
	var grown := {}
	for key: Vector2i in cells:
		for dz in range(-GROW, GROW + 1):
			for dx in range(-GROW, GROW + 1):
				grown[key + Vector2i(dx, dz)] = true
	var lo := Vector2i(1 << 20, 1 << 20)
	var hi := Vector2i(-(1 << 20), -(1 << 20))
	for key: Vector2i in grown:
		lo = lo.min(key)
		hi = hi.max(key)
	var w := hi.x - lo.x + 1
	var h := hi.y - lo.y + 1
	var bits := PackedByteArray()
	bits.resize((w * h + 7) >> 3)
	bits.fill(0)
	for key: Vector2i in grown:
		var i := (key.y - lo.y) * w + key.x - lo.x
		bits[i >> 3] = bits[i >> 3] | (1 << (i & 7))
	return {"x0": lo.x, "z0": lo.y, "w": w, "h": h, "bits": Marshalls.raw_to_base64(bits)}

## Per cell [lowest, highest] point of the scene's geometry between GATE_LOW and SPAN_HIGH:
## {x0, z0, w, h, bytes}: two bytes a cell, row-major, (y - SPAN_BASE) / SPAN_STEP; 255, 0 where
## the cell is empty.
func measure_spans(path: String, scale: float) -> Dictionary:
	var scene: Node3D = load(path).instantiate()
	scene.scale = Vector3.ONE * scale
	var meshes: Array = []
	collect(scene, Transform3D.IDENTITY, meshes)
	var lo := {}
	var hi := {}
	for entry: Array in meshes:
		var mesh: Mesh = entry[0]
		var xf: Transform3D = entry[1]
		var faces: PackedVector3Array = xf * mesh.get_faces()
		for f in range(0, faces.size(), 3):
			var a := faces[f]
			var b := faces[f + 1]
			var c := faces[f + 2]
			if maxf(a.y, maxf(b.y, c.y)) < GATE_LOW or minf(a.y, minf(b.y, c.y)) > SPAN_HIGH:
				continue
			var poly := clip(clip(PackedVector3Array([a, b, c]), GATE_LOW, true), SPAN_HIGH, false)
			if poly.size() < 2:
				continue
			var normal := (b - a).cross(c - a)
			var sloped := normal.length_squared() > 1e-12 and absf(normal.normalized().y) > 0.2
			var flat := PackedVector2Array()
			var low := Vector2(INF, INF)
			var high := Vector2(-INF, -INF)
			var ylow := INF
			var yhigh := -INF
			for v in poly:
				var q := Vector2(v.x, v.z)
				flat.append(q)
				low = low.min(q)
				high = high.max(q)
				ylow = minf(ylow, v.y)
				yhigh = maxf(yhigh, v.y)
			var area := 0.0
			for i in flat.size():
				area += flat[i].cross(flat[(i + 1) % flat.size()])
			for cz in range(floori(low.y / CELL), floori(high.y / CELL) + 1):
				for cx in range(floori(low.x / CELL), floori(high.x / CELL) + 1):
					var centre := Vector2((cx + 0.5) * CELL, (cz + 0.5) * CELL)
					var hit := absf(area) > 0.0001 and Geometry2D.is_point_in_polygon(centre, flat)
					if not hit:
						for i in flat.size():
							var q := Geometry2D.get_closest_point_to_segment(centre, flat[i], flat[(i + 1) % flat.size()])
							if absf(q.x - centre.x) <= CELL * 0.5 and absf(q.y - centre.y) <= CELL * 0.5:
								hit = true
								break
					if not hit:
						continue
					var y0 := ylow
					var y1 := yhigh
					if sloped:
						# The plane over this cell (its corners), within the piece's own heights.
						var n := normal.normalized()
						y0 = INF
						y1 = -INF
						for corner: Vector2 in [Vector2(cx, cz), Vector2(cx + 1, cz), Vector2(cx, cz + 1), Vector2(cx + 1, cz + 1)]:
							var at := corner * CELL
							var y := a.y - (n.x * (at.x - a.x) + n.z * (at.y - a.z)) / n.y
							y0 = minf(y0, clampf(y, ylow, yhigh))
							y1 = maxf(y1, clampf(y, ylow, yhigh))
					var key := Vector2i(cx, cz)
					lo[key] = minf(float(lo.get(key, INF)), y0)
					hi[key] = maxf(float(hi.get(key, -INF)), y1)
	scene.free()
	if lo.is_empty():
		return {"x0": 0, "z0": 0, "w": 0, "h": 0, "bytes": ""}
	var glo := {}
	var ghi := {}
	for key: Vector2i in lo:
		for dz in range(-GROW, GROW + 1):
			for dx in range(-GROW, GROW + 1):
				var k := key + Vector2i(dx, dz)
				glo[k] = minf(float(glo.get(k, INF)), lo[key])
				ghi[k] = maxf(float(ghi.get(k, -INF)), hi[key])
	var low_cell := Vector2i(1 << 20, 1 << 20)
	var high_cell := Vector2i(-(1 << 20), -(1 << 20))
	for key: Vector2i in glo:
		low_cell = low_cell.min(key)
		high_cell = high_cell.max(key)
	var w := high_cell.x - low_cell.x + 1
	var h := high_cell.y - low_cell.y + 1
	var bytes := PackedByteArray()
	bytes.resize(w * h * 2)
	for i in w * h:
		bytes[i * 2] = 255
		bytes[i * 2 + 1] = 0
	for key: Vector2i in glo:
		var i := (key.y - low_cell.y) * w + key.x - low_cell.x
		bytes[i * 2] = clampi(floori((glo[key] - SPAN_BASE) / SPAN_STEP), 0, 254)
		bytes[i * 2 + 1] = clampi(ceili((ghi[key] - SPAN_BASE) / SPAN_STEP), 1, 255)
	return {"x0": low_cell.x, "z0": low_cell.y, "w": w, "h": h, "bytes": Marshalls.raw_to_base64(bytes)}

func measure_floor(path: String, scale: float) -> Dictionary:
	var scene: Node3D = load(path).instantiate()
	scene.scale = Vector3.ONE * scale
	var meshes: Array = []
	collect(scene, Transform3D.IDENTITY, meshes)
	var top := {}
	for entry: Array in meshes:
		var mesh: Mesh = entry[0]
		var xf: Transform3D = entry[1]
		var faces: PackedVector3Array = xf * mesh.get_faces()
		for f in range(0, faces.size(), 3):
			var a := faces[f]
			var b := faces[f + 1]
			var c := faces[f + 2]
			var normal := (b - a).cross(c - a)
			if normal.length_squared() < 1e-12:
				continue
			var n := normal.normalized()
			if absf(n.y) < 0.8 or maxf(a.y, maxf(b.y, c.y)) < FLOOR_LOW or minf(a.y, minf(b.y, c.y)) > FLOOR_HIGH:
				continue
			var flat := PackedVector2Array([Vector2(a.x, a.z), Vector2(b.x, b.z), Vector2(c.x, c.z)])
			var low := flat[0].min(flat[1]).min(flat[2])
			var high := flat[0].max(flat[1]).max(flat[2])
			for cz in range(floori(low.y / CELL), floori(high.y / CELL) + 1):
				for cx in range(floori(low.x / CELL), floori(high.x / CELL) + 1):
					var centre := Vector2((cx + 0.5) * CELL, (cz + 0.5) * CELL)
					if not Geometry2D.is_point_in_polygon(centre, flat):
						continue
					var y := a.y - (n.x * (centre.x - a.x) + n.z * (centre.y - a.z)) / n.y
					if y < FLOOR_LOW or y > FLOOR_HIGH:
						continue
					var key := Vector2i(cx, cz)
					top[key] = maxf(float(top.get(key, -INF)), y)
	scene.free()
	if top.is_empty():
		return {"x0": 0, "z0": 0, "w": 0, "h": 0, "bytes": ""}
	var low_cell := Vector2i(1 << 20, 1 << 20)
	var high_cell := Vector2i(-(1 << 20), -(1 << 20))
	for key: Vector2i in top:
		low_cell = low_cell.min(key)
		high_cell = high_cell.max(key)
	var w := high_cell.x - low_cell.x + 1
	var h := high_cell.y - low_cell.y + 1
	var bytes := PackedByteArray()
	bytes.resize(w * h)
	bytes.fill(0)
	for key: Vector2i in top:
		bytes[(key.y - low_cell.y) * w + key.x - low_cell.x] = clampi(roundi((top[key] - SPAN_BASE) / SPAN_STEP), 1, 255)
	return {"x0": low_cell.x, "z0": low_cell.y, "w": w, "h": h, "bytes": Marshalls.raw_to_base64(bytes)}

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var table := {}
	var types: Array = data.types.keys()
	types.sort()
	var started := Time.get_ticks_msec()
	for type: String in types:
		var levels := {}
		for level in range(1, 6):
			var parts := MeasureFootprints.level_parts(data, type, level)
			var entry := measure(parts[0], float(parts[1]), GATE_LOW if type == "SUP-03" else SOLID_LOW)
			entry.base = measure(parts[0], float(parts[1]), GATE_LOW if type == "SUP-03" else BASE_LOW)
			if type == "SUP-03":
				entry.spans = measure_spans(parts[0], float(parts[1]))
			if TownPlan.own_square({"type": type, "level": level}):
				entry.floor = measure_floor(parts[0], float(parts[1]))
			levels[str(level)] = entry
		table[type] = levels
		print(type, " ", JSON.stringify(levels.keys().map(func(k): return [levels[k].w, levels[k].h])))
	print("measured in %d ms" % (Time.get_ticks_msec() - started))
	var text := JSON.stringify({"schema": 1, "cell": CELL, "low": SOLID_LOW, "high": SOLID_HIGH, "grow": GROW,
		"base_low": BASE_LOW, "gate_low": GATE_LOW, "span_high": SPAN_HIGH, "span_base": SPAN_BASE, "span_step": SPAN_STEP,
		"floor_low": FLOOR_LOW, "floor_high": FLOOR_HIGH,
		"note": "solid ground of each building level around the plot centre: cells x0..x0+w-1, z0..z0+h-1 (of `cell` m), row-major bits (base64); `base`: the same from base_low; SUP-03 `spans`: per cell lowest and highest point (bytes, span_base + n * span_step); own-square levels `floor`: per cell top of the floor (byte, 0 none); tools/measure_town_solids.gd",
		"types": table}, "\t", true) + "\n"
	var args := OS.get_cmdline_user_args()
	if "--write" in args:
		var file := FileAccess.open(TABLE, FileAccess.WRITE)
		file.store_string(text)
		file.close()
		print("WROTE ", TABLE)
	elif "--check" in args:
		var current := FileAccess.get_file_as_string(TABLE) if FileAccess.file_exists(TABLE) else ""
		var same := current == text
		print("TOWN_SOLIDS ", "up to date" if same else "STALE")
		quit(0 if same else 1)
		return
	quit()
