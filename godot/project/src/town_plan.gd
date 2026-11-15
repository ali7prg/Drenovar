extends RefCounted

# Town plan (build 52): every building stands on its own yard and every yard is
# reached by straight streets, wherever the player put the buildings.
#
#  - A yard is the building's ground footprint (largest of its five levels, so the yard
#    never jumps on an upgrade) with a margin and a forecourt in front (+z, the side every
#    model faces). Yards that would overlap are split halfway; split edges get no kerb.
#  - Streets are axis-aligned. The avenue runs from the town square in front of the town
#    hall to the main gate, gate streets join the other gates, and every yard is joined
#    by a lane to the nearest point of the network (nearest yard first). Each link is
#    the cheapest of a few L and Z shapes along the gaps between plot rows/columns;
#    shapes that cross another yard, the troop ground, water or the wall are penalised.
#  - The result is painted into a mask the town ground draws (R earth, G paving, B yard),
#    so crossings and corners merge without seams.
# Visual only: the server's plots, routes and rules are unchanged.

const CELL := 0.25
const HALF := 64.0
const SIZE := 512
const COARSE := 2.0
const COARSE_SIZE := 64
const SIDE := 0.8
const FRONT := 2.4
const LANE := 1.8
const STREET := 2.6
const AVENUE := 3.2
const DOOR_GAP := 2.8
const BODY_COST := 120.0
const YARD_COST := 6.0

var lots: Array = []
var segments: Array = []
var plaza := Rect2()
var mask: Image
var coarse := PackedByteArray()
var x_corridors: Array = []
var z_corridors: Array = []
var blocked: Array = []
var ground_ok := Callable()
var attach: Array = []
var layout_key := ""
var grids := {}
var link_grid := {}
var link_half := 0.9
var link_own := -1
var link_body := PackedInt32Array()
var link_yard := PackedInt32Array()
var ground_cells := PackedByteArray()
var ground_cache := {}
var sample_bound := INF

# Inside the rectangle shrunk by `margin` (false when nothing is left of it).
static func inside(r: Rect2, margin: float, p: Vector2) -> bool:
	return p.x > r.position.x + margin and p.x < r.end.x - margin and p.y > r.position.y + margin and p.y < r.end.y - margin

static func level_of(table: Dictionary, type: String, level: int) -> Array:
	var levels: Variant = table.get(type)
	if not levels is Dictionary:
		return [-4.0, -4.0, 4.0, 4.0, 6.0]
	var entry: Variant = levels.get(str(clampi(level, 1, 5)))
	return entry if entry is Array else [-4.0, -4.0, 4.0, 4.0, 6.0]

static func union_of(table: Dictionary, type: String) -> Array:
	var u := level_of(table, type, 1).duplicate()
	for level in range(2, 6):
		var b := level_of(table, type, level)
		u = [minf(u[0], b[0]), minf(u[1], b[1]), maxf(u[2], b[2]), maxf(u[3], b[3]), maxf(u[4], b[4])]
	return u

# Streets run in the gaps between plot rows and columns.
static func corridors(values: Array) -> Array:
	var sorted := values.duplicate()
	sorted.sort()
	var out: Array = []
	for i in range(1, sorted.size()):
		if float(sorted[i]) - float(sorted[i - 1]) > 6.0:
			out.append((float(sorted[i]) + float(sorted[i - 1])) * 0.5)
	return out

# buildings: [{id, type, level, x, z, hall}] already on their plots (no wall gate).
# gates: [[inner: Vector2, outer: Vector2], ...], main gate first (may be empty).
# all_plots: every plot position (Vector2), for the corridors.
func plan(buildings: Array, table: Dictionary, gates: Array, all_plots: Array, obstacles: Array, ok: Callable) -> void:
	# Streets depend only on where buildings stand: an upgrade only restyles the yards.
	var key := JSON.stringify([buildings.map(func(b): return [b.id, b.type, b.x, b.z, b.get("hall", false)]),
		gates.map(func(g): return [g[0].x, g[0].y, g[1].x, g[1].y]), obstacles.map(func(r: Rect2): return [r.position.x, r.position.y, r.size.x, r.size.y]),
		all_plots.size(), table.size()])
	if key == layout_key and lots.size() == buildings.size():
		for i in buildings.size():
			var b: Dictionary = buildings[i]
			var now := level_of(table, b.type, int(b.level))
			lots[i].level = int(b.level)
			lots[i].body = Rect2(lots[i].at.x + now[0], lots[i].at.y + now[1], now[2] - now[0], now[3] - now[1])
		paint()
		return
	layout_key = key
	ground_cache.clear()
	grids.clear()
	ground_cells.resize((GRID_SIZE >> 1) * (GRID_SIZE >> 1))
	ground_cells.fill(0)
	lots.clear()
	segments.clear()
	attach.clear()
	plaza = Rect2()
	blocked = obstacles
	ground_ok = ok
	x_corridors = corridors(all_plots.map(func(p: Vector2): return p.x))
	z_corridors = corridors(all_plots.map(func(p: Vector2): return p.y))
	for b: Dictionary in buildings:
		var u := union_of(table, b.type)
		var now := level_of(table, b.type, int(b.level))
		var at := Vector2(float(b.x), float(b.z))
		var rect := Rect2(at.x + u[0] - SIDE, at.y + u[1] - SIDE, u[2] - u[0] + SIDE * 2.0, u[3] - u[1] + SIDE + FRONT)
		lots.append({"id": b.id, "type": b.type, "level": int(b.level), "at": at, "rect": rect,
			"body": Rect2(at.x + now[0], at.y + now[1], now[2] - now[0], now[3] - now[1]),
			"reach": Rect2(at.x + u[0], at.y + u[1], u[2] - u[0], u[3] - u[1]),
			"hall": b.get("hall", false), "door_x": at.x + (u[0] + u[2]) * 0.5,
			"open": [true, true, true, true]})
	split_lots()
	var root := Vector2.ZERO
	var hall: Dictionary = {}
	for lot: Dictionary in lots:
		if lot.hall:
			hall = lot
	if not hall.is_empty():
		var r: Rect2 = hall.rect
		var front: float = hall.body.end.y
		plaza = Rect2(r.position.x, front - 0.3, r.size.x, maxf(1.5, r.end.y - front + 0.3))
		# The square stops at the buildings around it (the cut that keeps most of it).
		for lot: Dictionary in lots:
			if lot == hall or not lot.reach.intersects(plaza):
				continue
			var cut: Rect2 = lot.reach.intersection(plaza)
			var options: Array = [
				Rect2(plaza.position, Vector2(plaza.size.x, maxf(0.0, cut.position.y - plaza.position.y))),
				Rect2(Vector2(plaza.position.x, cut.end.y), Vector2(plaza.size.x, maxf(0.0, plaza.end.y - cut.end.y))),
				Rect2(plaza.position, Vector2(maxf(0.0, cut.position.x - plaza.position.x), plaza.size.y)),
				Rect2(Vector2(cut.end.x, plaza.position.y), Vector2(maxf(0.0, plaza.end.x - cut.end.x), plaza.size.y)),
			]
			options.sort_custom(func(x: Rect2, y: Rect2): return x.get_area() > y.get_area())
			plaza = options[0]
		root = Vector2(hall.door_x, r.end.y)
		if plaza.size.x > 1.0 and plaza.size.y > 0.6:
			for edge in plaza_edges():
				attach.append(edge)
		else:
			# A building stands right in front of the hall: the town is joined at the
			# first open side of the hall's yard.
			plaza = Rect2()
			var grid := grid_for(LANE * 0.5)
			var own := lots.find(hall) + 1
			for exit: Vector2 in [root, Vector2(r.position.x, r.end.y - 0.6), Vector2(r.end.x, r.end.y - 0.6), Vector2(float(hall.door_x), r.position.y)]:
				if body_at(grid, exit) in [0, own]:
					root = exit
					break
			attach.append([root, root])
	elif not lots.is_empty():
		root = door_of(lots[0])
	# Gate roads, then the avenue and the gate streets.
	for i in gates.size():
		segments.append({"a": gates[i][0], "b": gates[i][1], "w": AVENUE if i == 0 else STREET, "paved": true, "gate": true})
	# A gate road is joined at its inner end only (never along the road outside the wall).
	if not gates.is_empty() and (not hall.is_empty() or not lots.is_empty()):
		if attach.is_empty():
			attach.append([root, root])
		link_to_network(gates[0][0], AVENUE, true, null)
		attach.append([gates[0][0], gates[0][0]])
		for i in range(1, gates.size()):
			link_to_network(gates[i][0], STREET, true, null)
			attach.append([gates[i][0], gates[i][0]])
	# Lanes: the nearest unconnected yard first.
	var waiting: Array = lots.filter(func(lot): return not lot.hall)
	if hall.is_empty() and not lots.is_empty() and gates.is_empty():
		waiting.erase(lots[0])
		attach.append([root, root + Vector2(0, 0.01)])
	while not waiting.is_empty():
		var best: Dictionary = waiting[0]
		var best_d := INF
		for lot: Dictionary in waiting:
			var d := door_of(lot).distance_to(nearest_on_network(door_of(lot)))
			if d < best_d:
				best_d = d
				best = lot
		waiting.erase(best)
		link_lot(best)
	paint()

func door_of(lot: Dictionary) -> Vector2:
	return Vector2(float(lot.door_x), lot.rect.end.y)

func plaza_edges() -> Array:
	var p := plaza
	return [[p.position, Vector2(p.end.x, p.position.y)], [Vector2(p.position.x, p.end.y), p.end],
		[p.position, Vector2(p.position.x, p.end.y)], [Vector2(p.end.x, p.position.y), p.end]]

# Split overlapping yards halfway along the axis of the smaller overlap.
func split_lots() -> void:
	for i in lots.size():
		for j in range(i + 1, lots.size()):
			var a: Rect2 = lots[i].rect
			var b: Rect2 = lots[j].rect
			if not a.intersects(b):
				continue
			var cut := a.intersection(b)
			if cut.size.x <= cut.size.y:
				var mid := cut.position.x + cut.size.x * 0.5
				var left: int = i if a.get_center().x <= b.get_center().x else j
				var right: int = j if left == i else i
				var l: Rect2 = lots[left].rect
				var r: Rect2 = lots[right].rect
				lots[left].rect = Rect2(l.position, Vector2(mid - l.position.x, l.size.y))
				lots[right].rect = Rect2(Vector2(mid, r.position.y), Vector2(r.end.x - mid, r.size.y))
				lots[left].open[1] = false
				lots[right].open[0] = false
			else:
				var mid := cut.position.y + cut.size.y * 0.5
				var top: int = i if a.get_center().y <= b.get_center().y else j
				var bottom: int = j if top == i else i
				var t: Rect2 = lots[top].rect
				var o: Rect2 = lots[bottom].rect
				lots[top].rect = Rect2(t.position, Vector2(t.size.x, mid - t.position.y))
				lots[bottom].rect = Rect2(Vector2(o.position.x, mid), Vector2(o.size.x, o.end.y - mid))
				lots[top].open[3] = false
				lots[bottom].open[2] = false
	for lot: Dictionary in lots:
		for obstacle: Rect2 in blocked:
			if lot.rect.intersects(obstacle):
				var r: Rect2 = lot.rect
				var cut := r.intersection(obstacle)
				if cut.size.x <= cut.size.y:
					if obstacle.get_center().x > r.get_center().x:
						lot.rect = Rect2(r.position, Vector2(cut.position.x - r.position.x, r.size.y))
						lot.open[1] = false
					else:
						lot.rect = Rect2(Vector2(cut.end.x, r.position.y), Vector2(r.end.x - cut.end.x, r.size.y))
						lot.open[0] = false
				elif obstacle.get_center().y > r.get_center().y:
					lot.rect = Rect2(r.position, Vector2(r.size.x, cut.position.y - r.position.y))
					lot.open[3] = false
				else:
					lot.rect = Rect2(Vector2(r.position.x, cut.end.y), Vector2(r.size.x, r.end.y - cut.end.y))
					lot.open[2] = false

func nearest_on_network(p: Vector2) -> Vector2:
	var best := p
	var best_d := INF
	for s: Dictionary in segments:
		if s.gate:
			continue
		var q := Geometry2D.get_closest_point_to_segment(p, s.a, s.b)
		var d := p.distance_squared_to(q)
		if d < best_d:
			best_d = d
			best = q
	for edge: Array in attach:
		var q := Geometry2D.get_closest_point_to_segment(p, edge[0], edge[1])
		var d := p.distance_squared_to(q)
		if d < best_d:
			best_d = d
			best = q
	return best

func network_targets(from: Vector2) -> Array:
	# The nearest point of each of the three nearest streets.
	var targets: Array = []
	for s: Dictionary in segments:
		if s.gate:
			continue
		var q := Geometry2D.get_closest_point_to_segment(from, s.a, s.b)
		targets.append([from.distance_squared_to(q), q])
	for edge: Array in attach:
		var q := Geometry2D.get_closest_point_to_segment(from, edge[0], edge[1])
		targets.append([from.distance_squared_to(q), q])
	# Joints too: a street end is often the open way in.
	for s: Dictionary in segments:
		if not s.gate:
			targets.append([from.distance_squared_to(s.a), s.a])
	targets.sort_custom(func(x, y): return x[0] < y[0])
	return targets.map(func(t): return t[1])

# A yard is left by its front door; when a neighbour stands right in front of it, by a
# side or the back (costed higher, so the front is used whenever it is open).
func link_lot(lot: Dictionary) -> void:
	var r: Rect2 = lot.rect
	var exits := [[door_of(lot), 0.0], [Vector2(r.position.x, r.end.y - 0.6), 6.0],
		[Vector2(r.end.x, r.end.y - 0.6), 6.0], [Vector2(float(lot.door_x), r.position.y), 12.0]]
	# An exit that opens right onto another building is no way out (unless all do).
	var grid := grid_for(LANE * 0.5)
	var open_exits := exits.filter(func(e): return body_at(grid, e[0]) in [0, lots.find(lot) + 1])
	if open_exits.is_empty():
		open_exits = exits
	var pairs: Array = []
	for exit: Array in open_exits:
		for target: Vector2 in network_targets(exit[0]):
			pairs.append([exit[0], target, float(exit[1])])
	var best := cheapest(pairs, LANE, lots.find(lot))
	lot.exit = best[0][0] if not best.is_empty() else door_of(lot)
	if not best.is_empty():
		add_shape(best[0], LANE, true)

func link_to_network(from: Vector2, width: float, paved: bool, _own: Variant) -> void:
	if segments.is_empty() and attach.is_empty():
		return
	var pairs: Array = network_targets(from).map(func(t): return [from, t, 0.0])
	var best := cheapest(pairs, width, -1)
	if not best.is_empty():
		add_shape(best[0], width, paved)

func link(a: Vector2, b: Vector2, width: float, paved: bool, _own: Variant = null) -> void:
	if a.distance_to(b) < 0.05:
		return
	var best := cheapest([[a, b, 0.0]], width, -1)
	if not best.is_empty():
		add_shape(best[0], width, paved)

func add_shape(shape: Array, width: float, paved: bool) -> void:
	for i in range(shape.size() - 1):
		if shape[i].distance_to(shape[i + 1]) > 0.05:
			segments.append({"a": shape[i], "b": shape[i + 1], "w": width, "paved": paved, "gate": false})

# The cheapest shape over [from, to, extra cost] pairs: L and Z shapes first; only when
# they all cross a yard or a building, shapes that go round it (for the nearest pairs).
func cheapest(pairs: Array, width: float, own: int) -> Array:
	pairs.sort_custom(func(x, y): return absf(x[1].x - x[0].x) + absf(x[1].y - x[0].y) + x[2] < absf(y[1].x - y[0].x) + absf(y[1].y - y[0].y) + y[2])
	pairs = pairs.slice(0, 6)
	link_half = width * 0.5
	link_own = own
	link_grid = grid_for(link_half)
	link_body = link_grid.body
	link_yard = link_grid.yard
	var best: Array = []
	var best_cost := INF
	var best_clean := INF
	var blockers: Array = []
	for detour in [false, true]:
		if detour and (best.is_empty() or best_cost - best_clean < 0.5):
			break
		if detour:
			blockers = lots_hit(best[0])
		# Round a building: every pair; round a yard edge: the three nearest.
		for pair: Array in (pairs if not detour or best_cost - best_clean >= BODY_COST * 0.5 else pairs.slice(0, 3)):
			var a: Vector2 = pair[0]
			var b: Vector2 = pair[1]
			if absf(b.x - a.x) + absf(b.y - a.y) + pair[2] >= best_cost:
				continue
			# Shortest first: once a shape is no shorter than the best cost, none after it wins.
			var ranked: Array = shapes_for(a, b, detour, blockers).map(func(sh): return [clean_cost(sh), sh])
			ranked.sort_custom(func(x, y): return x[0] < y[0])
			ranked = ranked.slice(0, 160 if detour else 32)
			for entry: Array in ranked:
				if float(entry[0]) + pair[2] >= best_cost:
					break
				var shape: Array = entry[1]
				sample_bound = best_cost - pair[2]
				var found := shape_cost(shape)
				if found[0] + pair[2] < best_cost:
					best_cost = found[0] + pair[2]
					best_clean = found[1] + pair[2]
					best = [shape]
	return best

# The lots a shape crosses (body or yard, not where it may cross).
func lots_hit(shape: Array) -> Array:
	var hit := {}
	for i in range(shape.size() - 1):
		var p: Vector2 = shape[i]
		var q: Vector2 = shape[i + 1]
		var steps := maxi(1, ceili(p.distance_to(q) / 0.5))
		for k in range(steps + 1):
			var at := p.lerp(q, float(k) / steps)
			var cx := int(floor((at.x + HALF) / GRID))
			var cz := int(floor((at.y + HALF) / GRID))
			if cx < 0 or cz < 0 or cx >= GRID_SIZE or cz >= GRID_SIZE:
				continue
			for lot: int in [link_body[cz * GRID_SIZE + cx], link_yard[cz * GRID_SIZE + cx]]:
				if lot > 0 and not exempt(lot, at, shape[0]):
					hit[lot - 1] = true
	return hit.keys()

func shapes_for(a: Vector2, b: Vector2, detour: bool, blockers: Array = []) -> Array:
	if a.distance_to(b) < 0.05:
		return [[a, b]]
	var half := link_half
	var rows: Array = z_corridors.duplicate()
	var cols: Array = x_corridors.duplicate()
	rows.append(a.y + half + 0.4)
	var span := Rect2(a, Vector2.ZERO).expand(b).grow(8.0)
	for lot: Dictionary in lots:
		var r: Rect2 = lot.rect
		if span.intersects(r):
			rows.append_array([r.position.y - half - 0.05, r.end.y + half + 0.05])
			cols.append_array([r.position.x - half - 0.05, r.end.x + half + 0.05])
	rows = dedupe(rows)
	cols = dedupe(cols)
	var shapes: Array = []
	if not detour:
		shapes.append([a, Vector2(a.x, b.y), b])
		shapes.append([a, Vector2(b.x, a.y), b])
		for m in rows:
			shapes.append([a, Vector2(a.x, m), Vector2(b.x, m), b])
		for n in cols:
			shapes.append([a, Vector2(n, a.y), Vector2(n, b.y), b])
		return shapes
	# Round a building: out, along, past it and in, along the edges of what was in the way.
	var round_rows: Array = rows.filter(func(m): return m >= span.position.y and m <= span.end.y)
	var round_cols: Array = cols.filter(func(n): return n >= span.position.x and n <= span.end.x)
	for i: int in blockers:
		for r: Rect2 in [lots[i].rect, lots[i].reach]:
			round_rows.append_array([r.position.y - half - 0.05, r.end.y + half + 0.05])
			round_cols.append_array([r.position.x - half - 0.05, r.end.x + half + 0.05])
	for m in dedupe(round_rows):
		for n in dedupe(round_cols):
			shapes.append([a, Vector2(a.x, m), Vector2(n, m), Vector2(n, b.y), b])
			shapes.append([a, Vector2(n, a.y), Vector2(n, m), Vector2(b.x, m), b])
	return shapes

static func dedupe(values: Array) -> Array:
	var seen := {}
	var out: Array = []
	for v in values:
		var key := roundi(float(v) * 10.0)
		if not seen.has(key):
			seen[key] = true
			out.append(v)
	return out

func clean_cost(shape: Array) -> float:
	var cost := 0.0
	for i in range(shape.size() - 1):
		var d: float = absf(shape[i].x - shape[i + 1].x) + absf(shape[i].y - shape[i + 1].y)
		if d >= 0.05:
			cost += d + 3.0
	return cost

# [cost, cost without penalties]; INF once over sample_bound.
func shape_cost(shape: Array) -> Array:
	var length := 0.0
	var turns := 0
	for i in range(shape.size() - 1):
		var d: float = shape[i].distance_to(shape[i + 1])
		if d < 0.05:
			continue
		length += d
		turns += 1
	var clean := length + turns * 3.0
	var cost := clean
	if cost >= sample_bound:
		return [INF, INF]
	var start: Vector2 = shape[0]
	for i in range(shape.size() - 1):
		var p: Vector2 = shape[i]
		var q: Vector2 = shape[i + 1]
		var d := p.distance_to(q)
		if d < 0.05:
			continue
		var steps := maxi(1, ceili(d / 0.7))
		for k in range(steps + 1):
			cost += penalty_at(p.lerp(q, float(k) / steps), start) * d / steps
			if cost >= sample_bound:
				return [INF, INF]
	return [cost, clean]

# Body and yard of every lot, grown by a street half width, as 0.5 m cells holding the
# lot index + 1 (-1 where several bodies meet or the troop ground is). Built once per
# plan and width.
const GRID := 0.5
const GRID_SIZE := 256

func grid_for(half: float) -> Dictionary:
	var key := snappedf(half, 0.01)
	if grids.has(key):
		return grids[key]
	var body := PackedInt32Array()
	var yard := PackedInt32Array()
	body.resize(GRID_SIZE * GRID_SIZE)
	yard.resize(GRID_SIZE * GRID_SIZE)
	for i in lots.size():
		raster(body, lots[i].reach.grow(half - 0.1), i + 1)
		raster(yard, lots[i].rect.grow(half - 0.35), i + 1)
	for obstacle: Rect2 in blocked:
		raster(body, obstacle.grow(half), -1)
	grids[key] = {"body": body, "yard": yard}
	return grids[key]

func raster(cells: PackedInt32Array, r: Rect2, value: int) -> void:
	var x0 := clampi(ceili((r.position.x + HALF) / GRID - 0.5), 0, GRID_SIZE)
	var x1 := clampi(floori((r.end.x + HALF) / GRID - 0.5), -1, GRID_SIZE - 1)
	var z0 := clampi(ceili((r.position.y + HALF) / GRID - 0.5), 0, GRID_SIZE)
	var z1 := clampi(floori((r.end.y + HALF) / GRID - 0.5), -1, GRID_SIZE - 1)
	for z in range(z0, z1 + 1):
		for x in range(x0, x1 + 1):
			var i := z * GRID_SIZE + x
			cells[i] = value if cells[i] == 0 or cells[i] == value else -1

func body_at(grid: Dictionary, p: Vector2) -> int:
	var cx := int(floor((p.x + HALF) / GRID))
	var cz := int(floor((p.y + HALF) / GRID))
	if cx < 0 or cz < 0 or cx >= GRID_SIZE or cz >= GRID_SIZE:
		return 0
	return grid.body[cz * GRID_SIZE + cx]

func penalty_at(p: Vector2, start: Vector2) -> float:
	var cx := int(floor((p.x + HALF) / GRID))
	var cz := int(floor((p.y + HALF) / GRID))
	if cx < 0 or cz < 0 or cx >= GRID_SIZE or cz >= GRID_SIZE:
		return BODY_COST
	var i := cz * GRID_SIZE + cx
	var total := 0.0
	var lot := link_body[i]
	if lot != 0 and not exempt(lot, p, start):
		total += BODY_COST
	lot = link_yard[i]
	if lot != 0 and not exempt(lot, p, start):
		total += YARD_COST
	if ground_ok.is_valid():
		# Dry ground inside the wall, cached in 1 m cells (0 unknown, 1 good, 2 bad).
		var g := (cz >> 1) * (GRID_SIZE >> 1) + (cx >> 1)
		if ground_cells[g] == 0:
			ground_cells[g] = 1 if ground_ok.call((cx >> 1) - HALF + 0.5, (cz >> 1) - HALF + 0.5) else 2
		if ground_cells[g] == 2:
			total += BODY_COST
	return total

# The lane may leave its own yard through the front; streets cross the town square.
func exempt(lot: int, p: Vector2, start: Vector2) -> bool:
	if lot - 1 == link_own and p.distance_to(start) < link_half + 0.6:
		return true
	return lot > 0 and lots[lot - 1].hall and inside(plaza, 0.2, p)

# --------------------------------------------------------------- mask

func pixel(v: float) -> int:
	return clampi(int(floor((v + HALF) / CELL)), 0, SIZE)

func fill(rect: Rect2, color: Color) -> void:
	var x0 := pixel(rect.position.x)
	var y0 := pixel(rect.position.y)
	var x1 := pixel(rect.end.x)
	var y1 := pixel(rect.end.y)
	if x1 <= x0 or y1 <= y0:
		return
	mask.fill_rect(Rect2i(x0, y0, x1 - x0, y1 - y0), color)
	mark(rect)

func mark(rect: Rect2) -> void:
	var g := rect.grow(1.0)
	for cz in range(clampi(int(floor((g.position.y + HALF) / COARSE)), 0, COARSE_SIZE - 1), clampi(int(floor((g.end.y + HALF) / COARSE)), 0, COARSE_SIZE - 1) + 1):
		for cx in range(clampi(int(floor((g.position.x + HALF) / COARSE)), 0, COARSE_SIZE - 1), clampi(int(floor((g.end.x + HALF) / COARSE)), 0, COARSE_SIZE - 1) + 1):
			coarse[cz * COARSE_SIZE + cx] = 1

func street_rect(s: Dictionary) -> Rect2:
	var a: Vector2 = s.a
	var b: Vector2 = s.b
	var h: float = float(s.w) * 0.5
	return Rect2(minf(a.x, b.x) - h, minf(a.y, b.y) - h, absf(a.x - b.x) + h * 2.0, absf(a.y - b.y) + h * 2.0)

func paint() -> void:
	mask = Image.create(SIZE, SIZE, false, Image.FORMAT_RGBA8)
	mask.fill(Color(0, 0, 0, 0))
	coarse.resize(COARSE_SIZE * COARSE_SIZE)
	coarse.fill(0)
	# Yards: earth; fully paved at level V and for the town square.
	for lot: Dictionary in lots:
		var paved: bool = lot.hall or int(lot.level) >= 5
		fill(lot.rect, Color(0, 1, 1, 1) if paved else Color(1, 0, 1, 1))
	# Paved forecourts from level III: from the building to the yard front, door wide.
	for lot: Dictionary in lots:
		if int(lot.level) >= 3 and not lot.hall:
			var front: float = lot.body.end.y - 0.2
			var apron := Rect2(float(lot.door_x) - DOOR_GAP * 0.5, front, DOOR_GAP, lot.rect.end.y - front + 0.1)
			fill(apron, Color(0, 1, 1, 1))
	if plaza.has_area():
		fill(plaza, Color(0, 1, 1, 1))
	# Every street is paved: lanes, gate streets and the avenue.
	for s: Dictionary in segments:
		if not s.gate:
			fill_keep(street_rect(s), Color(0, 1, 0, 1))
	for s: Dictionary in segments:
		if s.gate:
			var a: Vector2 = s.a
			var b: Vector2 = s.b
			var steps := maxi(1, ceili(a.distance_to(b) / 0.25))
			var h: float = float(s.w) * 0.5
			for k in range(steps + 1):
				var p := a.lerp(b, float(k) / steps)
				fill_keep(Rect2(p.x - h * 0.75, p.y - h * 0.75, h * 1.5, h * 1.5), Color(0, 1, 0, 1))

# Fills without lowering what is there: paving wins over earth, a yard keeps its flag.
func fill_keep(rect: Rect2, color: Color) -> void:
	var x0 := pixel(rect.position.x)
	var y0 := pixel(rect.position.y)
	var x1 := pixel(rect.end.x)
	var y1 := pixel(rect.end.y)
	if x1 <= x0 or y1 <= y0:
		return
	if color.g > 0.5:
		# Paving: overwrite earth, keep the yard flag where there is one.
		var region := mask.get_region(Rect2i(x0, y0, x1 - x0, y1 - y0))
		var paved := Image.create(x1 - x0, y1 - y0, false, Image.FORMAT_RGBA8)
		paved.fill(Color(0, 1, 0, 1))
		mask.blit_rect(paved, Rect2i(0, 0, x1 - x0, y1 - y0), Vector2i(x0, y0))
		# Restore yard flags (B) inside the region.
		var flags := region.get_data()
		var data := mask.get_region(Rect2i(x0, y0, x1 - x0, y1 - y0)).get_data()
		for i in range(2, data.size(), 4):
			data[i] = flags[i]
		mask.blit_rect(Image.create_from_data(x1 - x0, y1 - y0, false, Image.FORMAT_RGBA8, data), Rect2i(0, 0, x1 - x0, y1 - y0), Vector2i(x0, y0))
	else:
		# Earth: only where nothing is drawn yet.
		var data := mask.get_region(Rect2i(x0, y0, x1 - x0, y1 - y0)).get_data()
		for i in range(0, data.size(), 4):
			if data[i + 3] == 0:
				data[i] = 255
				data[i + 3] = 255
		mask.blit_rect(Image.create_from_data(x1 - x0, y1 - y0, false, Image.FORMAT_RGBA8, data), Rect2i(0, 0, x1 - x0, y1 - y0), Vector2i(x0, y0))
	mark(rect)

func covered(x: float, z: float) -> bool:
	if mask == null:
		return false
	var px := pixel(x)
	var py := pixel(z)
	if px >= SIZE or py >= SIZE or px <= 0 or py <= 0:
		return false
	return mask.get_pixel(px, py).a > 0.5

func coarse_cell(cx: int, cz: int) -> bool:
	return coarse[cz * COARSE_SIZE + cx] == 1

# Every street as [a, b, half width] for the vegetation tests.
func street_lines() -> Array:
	var out: Array = []
	for s: Dictionary in segments:
		out.append([s.a, s.b, float(s.w) * 0.5])
	return out
