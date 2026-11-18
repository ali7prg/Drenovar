extends RefCounted
## Presentation-only interpolation of server move objects (CONTRACT §5):
## move = {path:[{x,y,z}], departAt, arriveAt, targetId, speed}. Position(t) follows the
## authoritative path at constant speed between departAt and arriveAt.

static func point(value: Variant) -> Vector3:
	if value is Vector3:
		return value
	if value is Dictionary:
		return Vector3(float(value.get("x", 0)), float(value.get("y", 0)), float(value.get("z", 0)))
	if value is Array and value.size() >= 3:
		return Vector3(float(value[0]), float(value[1]), float(value[2]))
	return Vector3.ZERO

static func build(path: Array) -> Dictionary:
	var points := PackedVector3Array()
	var distances := PackedFloat32Array()
	for entry in path:
		var next := point(entry)
		var total := 0.0
		if not points.is_empty():
			var previous := points[-1]
			total = distances[-1] + Vector2(next.x - previous.x, next.z - previous.z).length()
		points.append(next)
		distances.append(total)
	return {"points":points, "distances":distances, "total":distances[-1] if not distances.is_empty() else 0.0}

static func sample(route: Dictionary, distance: float) -> Dictionary:
	var points: PackedVector3Array = route.get("points", PackedVector3Array())
	var distances: PackedFloat32Array = route.get("distances", PackedFloat32Array())
	if points.is_empty():
		return {"position":Vector3.ZERO, "tangent":Vector3.FORWARD}
	if points.size() == 1:
		return {"position":points[0], "tangent":Vector3.FORWARD}
	var travelled := clampf(distance, 0.0, distances[-1])
	var index := clampi(distances.bsearch(travelled), 1, distances.size() - 1)
	var length := distances[index] - distances[index - 1]
	var weight := (travelled - distances[index - 1]) / length if length > 0.0001 else 0.0
	var a := points[index - 1]
	var b := points[index]
	var tangent := Vector3(b.x - a.x, 0, b.z - a.z)
	if tangent.length_squared() < 0.000001:
		tangent = Vector3.FORWARD
	return {"position":a.lerp(b, weight), "tangent":tangent.normalized()}

## Distance travelled along the move at server time now_ms (clamped to the path).
static func travelled(move: Dictionary, route: Dictionary, now_ms: float) -> float:
	var depart := float(move.get("departAt", now_ms))
	var arrive := float(move.get("arriveAt", depart))
	var total := float(route.get("total", 0.0))
	if arrive <= depart:
		return total if now_ms >= arrive else 0.0
	return total * clampf((now_ms - depart) / (arrive - depart), 0.0, 1.0)

static func speed(move: Dictionary, route: Dictionary) -> float:
	var seconds := (float(move.get("arriveAt", 0)) - float(move.get("departAt", 0))) / 1000.0
	if seconds <= 0.01:
		return float(move.get("speed", 0.0))
	return float(route.get("total", 0.0)) / seconds

static func yaw_of(direction: Vector3) -> float:
	return atan2(direction.x, direction.z)

## Smooth heading change without snapping 180° (presentation only).
static func turn_towards(current: float, wanted: float, rate: float, delta: float) -> float:
	return lerp_angle(current, wanted, 1.0 - exp(-rate * delta))
