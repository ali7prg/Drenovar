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
			levels[str(level)] = entry
		table[type] = levels
		print(type, " ", JSON.stringify(levels.keys().map(func(k): return [levels[k].w, levels[k].h])))
	print("measured in %d ms" % (Time.get_ticks_msec() - started))
	var text := JSON.stringify({"schema": 1, "cell": CELL, "low": SOLID_LOW, "high": SOLID_HIGH, "grow": GROW,
		"base_low": BASE_LOW, "gate_low": GATE_LOW,
		"note": "solid ground of each building level around the plot centre: cells x0..x0+w-1, z0..z0+h-1 (of `cell` m), row-major bits (base64); `base`: the same from base_low; tools/measure_town_solids.gd",
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
