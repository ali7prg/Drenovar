extends RefCounted
## GDScript port of forest_rescue/delivery/code/world-layout.mjs (mask + chunk helpers)
## plus a spatial-hash MaskSet for fast per-instance queries.
## Pure functions: no scene access, no player-state mutation.

const CHUNK_SIZE := 56.0
const MIN := -112.0
const MAX := 112.0
const CORE := 56.0


static func chunk_id_at(x: float, z: float) -> String:
	if is_nan(x) or is_nan(z) or is_inf(x) or is_inf(z) or x < MIN or z < MIN or x >= MAX or z >= MAX:
		return ""
	return "lf_chunk_%d_%d" % [floori((x - MIN) / CHUNK_SIZE), floori((z - MIN) / CHUNK_SIZE)]


## Chunk coordinate (cx, cz) for any point; -1 outside the atlas.
static func chunk_coord(x: float, z: float) -> Vector2i:
	if x < MIN or z < MIN or x >= MAX or z >= MAX:
		return Vector2i(-1, -1)
	return Vector2i(floori((x - MIN) / CHUNK_SIZE), floori((z - MIN) / CHUNK_SIZE))


static func all_chunks() -> Array:
	var result: Array = []
	for i in 16:
		var cx := i % 4
		var cz := i / 4
		result.append({"id": "lf_chunk_%d_%d" % [cx, cz], "cx": cx, "cz": cz,
			"minX": MIN + cx * CHUNK_SIZE, "maxX": MIN + (cx + 1) * CHUNK_SIZE,
			"minZ": MIN + cz * CHUNK_SIZE, "maxZ": MIN + (cz + 1) * CHUNK_SIZE})
	return result


static func segment_distance(p: Vector2, a: Vector2, b: Vector2) -> float:
	var d := b - a
	var length_squared := d.length_squared()
	var t := 0.0 if length_squared == 0.0 else clampf((p - a).dot(d) / length_squared, 0.0, 1.0)
	return p.distance_to(a + d * t)


static func valid_mask(m: Variant) -> bool:
	if not m is Dictionary:
		return false
	match String(m.get("type", "")):
		"box":
			return m.has_all(["minX", "maxX", "minZ", "maxZ"]) and float(m.minX) <= float(m.maxX) and float(m.minZ) <= float(m.maxZ)
		"circle":
			return m.has_all(["x", "z", "radius"]) and float(m.radius) > 0.0
		"capsule":
			return m.get("a") is Dictionary and m.get("b") is Dictionary and float(m.get("radius", 0.0)) > 0.0
	return false


## Port of insideMask(p, mask, margin). Unsupported masks raise (fail closed).
static func inside_mask(x: float, z: float, mask: Dictionary, margin := 0.0) -> bool:
	match String(mask.get("type", "")):
		"circle":
			return Vector2(x - float(mask.x), z - float(mask.z)).length() <= float(mask.radius) + margin
		"box":
			return x >= float(mask.minX) - margin and x <= float(mask.maxX) + margin \
				and z >= float(mask.minZ) - margin and z <= float(mask.maxZ) + margin
		"capsule":
			var a := Vector2(float(mask.a.x), float(mask.a.z))
			var b := Vector2(float(mask.b.x), float(mask.b.z))
			return segment_distance(Vector2(x, z), a, b) <= float(mask.radius) + margin
	push_error("ForestMasks: UNSUPPORTED_MASK " + str(mask))
	return true


static func mask_bounds(mask: Dictionary, margin := 0.0) -> Rect2:
	match String(mask.get("type", "")):
		"circle":
			var r := float(mask.radius) + margin
			return Rect2(float(mask.x) - r, float(mask.z) - r, 2.0 * r, 2.0 * r)
		"box":
			return Rect2(float(mask.minX) - margin, float(mask.minZ) - margin,
				float(mask.maxX) - float(mask.minX) + 2.0 * margin, float(mask.maxZ) - float(mask.minZ) + 2.0 * margin)
		"capsule":
			var r := float(mask.radius) + margin
			var lo := Vector2(minf(float(mask.a.x), float(mask.b.x)), minf(float(mask.a.z), float(mask.b.z)))
			var hi := Vector2(maxf(float(mask.a.x), float(mask.b.x)), maxf(float(mask.a.z), float(mask.b.z)))
			return Rect2(lo - Vector2(r, r), hi - lo + Vector2(2.0 * r, 2.0 * r))
	return Rect2(-1.0e6, -1.0e6, 2.0e6, 2.0e6)


## Port of selectChunks(). camera: Vector2 (XZ). pinned_points: Array[Vector2].
## is_chunk_explored: Callable(id: String) -> bool (default: everything explored).
static func select_chunks(camera: Vector2, view_radius := 65.0, pinned_points: Array = [],
		is_chunk_explored := Callable(), full_budget := 4, proxy_budget := 8) -> Dictionary:
	if is_nan(camera.x) or is_nan(camera.y) or view_radius < 0.0 or full_budget < 1 or full_budget > 16 \
			or proxy_budget < 0 or proxy_budget > 16:
		push_error("ForestMasks: INVALID_STREAM_INPUT")
		return {}
	var pinned := {}
	for point: Vector2 in pinned_points:
		var id := chunk_id_at(point.x, point.y)
		if id.is_empty():
			push_error("ForestMasks: INVALID_PIN " + str(point))
			return {}
		pinned[id] = true
	var chunks := all_chunks()
	for chunk: Dictionary in chunks:
		var nearest := Vector2(clampf(camera.x, chunk.minX, chunk.maxX), clampf(camera.y, chunk.minZ, chunk.maxZ))
		chunk.distance = camera.distance_to(nearest)
		chunk.pinned = pinned.has(chunk.id)
		chunk.explored = true if not is_chunk_explored.is_valid() else is_chunk_explored.call(chunk.id) == true
	chunks.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a.pinned != b.pinned:
			return a.pinned
		if a.distance != b.distance:
			return a.distance < b.distance
		return String(a.id) < String(b.id))
	var full: Array = []
	var proxy: Array = []
	var fog_only: Array = []
	var unloaded: Array = []
	for chunk: Dictionary in chunks:
		if chunk.pinned:
			full.append(chunk.id)
			continue
		if chunk.distance > view_radius + 20.0:
			unloaded.append(chunk.id)
			continue
		if not chunk.explored:
			fog_only.append(chunk.id)
			continue
		if chunk.distance <= view_radius and full.size() < full_budget:
			full.append(chunk.id)
		elif proxy.size() < proxy_budget:
			proxy.append(chunk.id)
		else:
			unloaded.append(chunk.id)
	return {"full": full, "proxy": proxy, "fogOnly": fog_only, "unloaded": unloaded,
		"overflow": maxi(0, full.size() - full_budget),
		"policy": "Pinned authoritative actors stay loaded; overflow requires measured quality reduction, never gameplay pause."}


## Spatial hash of masks for fast point queries. Masks are dictionaries in the
## world-layout.mjs format plus an optional "kind" tag (route, glade, arena, ...).
class MaskSet:
	extends RefCounted
	var cell := 8.0
	var masks: Array = []
	var grid: Dictionary = {}

	func _init(cell_size := 8.0) -> void:
		cell = cell_size

	func add(mask: Dictionary) -> void:
		var index := masks.size()
		masks.append(mask)
		var bounds := ForestMasksStatic.bounds_of(mask)
		for gz in range(floori(bounds.position.y / cell), floori(bounds.end.y / cell) + 1):
			for gx in range(floori(bounds.position.x / cell), floori(bounds.end.x / cell) + 1):
				var key := Vector2i(gx, gz)
				if not grid.has(key):
					grid[key] = PackedInt32Array()
				grid[key].append(index)

	## First matching mask (with margin) or {}. Margins larger than `cell` need query_radius.
	func hit(x: float, z: float, margin := 0.0, kinds: Array = []) -> Dictionary:
		var keys: Array = [Vector2i(floori(x / cell), floori(z / cell))]
		if margin > 0.0:
			keys.clear()
			for gz in range(floori((z - margin) / cell), floori((z + margin) / cell) + 1):
				for gx in range(floori((x - margin) / cell), floori((x + margin) / cell) + 1):
					keys.append(Vector2i(gx, gz))
		for key in keys:
			for index in grid.get(key, PackedInt32Array()):
				var mask: Dictionary = masks[index]
				if not kinds.is_empty() and not kinds.has(mask.get("kind", "")):
					continue
				if ForestMasksStatic.inside(x, z, mask, margin):
					return mask
		return {}

	func inside_any(x: float, z: float, margin := 0.0, kinds: Array = []) -> bool:
		return not hit(x, z, margin, kinds).is_empty()


## Static helpers reachable from the inner class (inner classes cannot call outer statics
## through the script name without a class_name).
class ForestMasksStatic:
	static func bounds_of(mask: Dictionary) -> Rect2:
		match String(mask.get("type", "")):
			"circle":
				var r := float(mask.radius)
				return Rect2(float(mask.x) - r, float(mask.z) - r, 2.0 * r, 2.0 * r)
			"box":
				return Rect2(float(mask.minX), float(mask.minZ), float(mask.maxX) - float(mask.minX), float(mask.maxZ) - float(mask.minZ))
			"capsule":
				var r := float(mask.radius)
				var lo := Vector2(minf(float(mask.a.x), float(mask.b.x)), minf(float(mask.a.z), float(mask.b.z)))
				var hi := Vector2(maxf(float(mask.a.x), float(mask.b.x)), maxf(float(mask.a.z), float(mask.b.z)))
				return Rect2(lo - Vector2(r, r), hi - lo + Vector2(2.0 * r, 2.0 * r))
		return Rect2(-1.0e6, -1.0e6, 2.0e6, 2.0e6)

	static func inside(x: float, z: float, mask: Dictionary, margin: float) -> bool:
		match String(mask.get("type", "")):
			"circle":
				var dx := x - float(mask.x)
				var dz := z - float(mask.z)
				var r := float(mask.radius) + margin
				return dx * dx + dz * dz <= r * r
			"box":
				return x >= float(mask.minX) - margin and x <= float(mask.maxX) + margin \
					and z >= float(mask.minZ) - margin and z <= float(mask.maxZ) + margin
			"capsule":
				var a := Vector2(float(mask.a.x), float(mask.a.z))
				var d := Vector2(float(mask.b.x), float(mask.b.z)) - a
				var p := Vector2(x, z) - a
				var length_squared := d.length_squared()
				var t := 0.0 if length_squared == 0.0 else clampf(p.dot(d) / length_squared, 0.0, 1.0)
				return p.distance_to(d * t) <= float(mask.radius) + margin
		return true
