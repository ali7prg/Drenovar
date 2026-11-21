extends RefCounted
## Outer-ground earthworks for «Лес потерянных».
##
## The city ground is 64 GLB tiles; the inner 6×6 tiles form one regular 187×187 vertex grid
## over [-135.625, 135.625]² (step 45.2083/31 m). We read that grid from the real tile meshes,
## keep each tile's own vertex order + index buffer (topology unchanged) and only rewrite
## POSITION.y / NORMAL / COLOR / UV2 outside the protected core (±56). height_at() uses the
## same per-cell triangle diagonal as the rendered mesh, so actors stand exactly on it.
##
## Earthworks (all outside the core, never inside the wet river channel):
##   * glade pads: flatten r=7 at the authored site height, blend 2 m;
##   * arena bowl: shallow dish r=15 at the authored height, blend to 19 m;
##   * road profiles: atlas targetRoadY (12° limited), half-width 1.4, side blend 3 m,
##     tied into pads (6 m) and lifted to the bridge deck with 10 m ramps;
##   * bridge: deck top 1.1 over x∈[76.98, 103.98], z∈[18, 22] (height_at only, terrain untouched);
##   * atlas v2 water (ForestWater.bodies): basins for the reedy lake (river level, marshy banks),
##     the perched lily pond under the waterfall and the south marsh pools — carved after the
##     river protection, never under a trail's walking band or a glade pad.

const GRID_N := 187
const GRID_MIN := -135.625
const GRID_STEP := 45.20833206176758 / 31.0
const CORE := 56.0
const CORE_BLEND := 2.0
const ROAD_HALF_WIDTH := 2.9    # full-weight band ≥ grid diagonal so triangles under the path follow the profile
const ROAD_BLEND := 3.0
const RAMP_LENGTH := 10.0
const PAD_TIE := 6.0
const ARENA_BLEND_OUTER := 19.0
const ARENA_DISH := 0.3
const GLADE_PAD_BLEND := 2.0
const PAD_EXTRA_GRADE_DEG := 4.0      # grade a trail may gain on top of its atlas profile to meet its ends
const TERRAIN_VERSION := 18

## Atlas v2 region ground tints (ForestAtlas.REGION_NAMES order, art/01 crops at zoom 68):
## sunny warm meadow under the golden grove, olive mixed oaks, dry grey-olive arena rock, fresh
## green willow banks, cool riverside, dark mossy blue-green floor under the south pines, pale
## limestone quarry, lush meadow belt round the walls. FLOOR_SHADE = darkest canopy-floor factor.
const REGION_TINTS := [
	Color(1.07, 1.03, 0.82),   # golden_grove
	Color(1.00, 1.01, 0.86),   # west_mixed
	Color(0.96, 0.95, 0.88),   # arena_rock
	Color(0.93, 1.05, 0.88),   # east_willows
	Color(0.90, 1.01, 0.92),   # river
	Color(0.70, 0.81, 0.73),   # south_pines
	Color(1.03, 1.00, 0.92),   # sw_quarry
	Color(0.98, 1.06, 0.86),   # town_belt
]
const FLOOR_SHADE := [0.9, 0.84, 0.82, 0.84, 0.86, 0.68, 0.9, 0.88]
const WET_TINT := Color(0.80, 0.93, 0.86)

var atlas: RefCounted
var heights0 := PackedFloat32Array()     # original mesh heights (grid order)
var heights := PackedFloat32Array()      # final heights incl. earthworks
var diag := PackedByteArray()            # 0: (i,j)-(i+1,j+1) diagonal, 1: (i+1,j)-(i,j+1)
var earth := PackedFloat32Array()        # extra UV2.x (dirt) weight
var rock := PackedFloat32Array()         # extra UV2.y (stone) weight
var tint := PackedColorArray()           # COLOR multiplier
var road_profiles: Array = []            # per route: PackedFloat32Array final road heights
var road_on_deck: Array = []             # per route: PackedByteArray
var grid_ready := false
var stats := {}
var extra_pads: Array = []               # [[Vector2 centre, radius, height]] landmark/camp pads
var quarry_center := Vector2.INF         # SW quarry pit: grey stone/gravel ground (art/01)
var pad_heights: Dictionary = {}         # site id -> reconciled pad height (centre + route ends)
var water_bodies: Array = []             # ForestWater.bodies(atlas): lake / pond / marsh pools
var junction_pads: Array = []            # [[Vector2 centre, height]]: small flat landings at trail junctions


func _init(forest_atlas: RefCounted = null) -> void:
	atlas = forest_atlas


static func base_height(x: float, z: float) -> float:
	# Exact copy of landscape.gd sample_city() without the inner lot pads (core only).
	var west := -x + 0.16 * z + 2.6 * sin(z * 0.095)
	var north := -z + 0.13 * x + 2.8 * sin(x * 0.078)
	var shelf := 3.8 * smoothstep(25, 31, west) + 2.1 * smoothstep(43, 49, west) + 4.5 * smoothstep(25, 33, north) \
		+ 1.7 * smoothstep(43, 50, north) + 2.6 * smoothstep(35, 43, z + sin(x * 0.08) * 3)
	var land := 0.45 + shelf * smoothstep(31.5, 38, maxf(absf(x), absf(z))) + 0.12 * sin(x * 0.17) * cos(z * 0.14) + 0.16 * sin((x + z) * 0.08)
	land += 2.0 * (1.0 - smoothstep(5.5, 15, Vector2(x + 25, z + 7).length()))
	land += 2.5 * (1.0 - smoothstep(5.5, 15, Vector2(x + 7, z + 27).length()))
	land += 1.1 * (1.0 - smoothstep(5.5, 15, Vector2(x - 28, z).length()))
	var center := z + 66 + 8 * sin(z * 0.068) + 3.5 * cos(z * 0.127 + 0.3) + 9 * exp(-pow((z + 25) / 15, 2))
	var distance := absf(x - center) - 4.3 - 0.65 * sin(z * 0.093 + 1.4)
	return lerpf(-2.85 + 0.15 * sin(z * 0.15), land, smoothstep(-0.6, 5.2, distance))


static func grid_x(i: int) -> float:
	return GRID_MIN + i * GRID_STEP


static func core_weight(x: float, z: float) -> float:
	return smoothstep(0.0, CORE_BLEND, maxf(absf(x), absf(z)) - CORE)


# --------------------------------------------------------------------------------------------
# Grid construction from the real tile meshes

## Reads the original vertex heights + triangle diagonals from the ground tile meshes.
func read_tiles(tile_meshes: Array) -> void:
	heights0.resize(GRID_N * GRID_N)
	heights0.fill(NAN)
	diag.resize((GRID_N - 1) * (GRID_N - 1))
	diag.fill(0)
	for mesh: Mesh in tile_meshes:
		var arrays := mesh.surface_get_arrays(0)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		var cells := PackedInt32Array()
		cells.resize(vertices.size())
		var inside := true
		for k in vertices.size():
			var v := vertices[k]
			var i := roundi((v.x - GRID_MIN) / GRID_STEP)
			var j := roundi((v.z - GRID_MIN) / GRID_STEP)
			if i < 0 or j < 0 or i >= GRID_N or j >= GRID_N or absf(grid_x(i) - v.x) > 0.02 or absf(grid_x(j) - v.z) > 0.02:
				inside = false
				cells[k] = -1
				continue
			cells[k] = j * GRID_N + i
			heights0[j * GRID_N + i] = v.y
		if not inside:
			continue
		for t in range(0, indices.size(), 3):
			var a := cells[indices[t]]
			var b := cells[indices[t + 1]]
			var c := cells[indices[t + 2]]
			# Find the diagonal edge (|di| == 1 and |dj| == 1).
			for pair in [[a, b], [b, c], [c, a]]:
				var p: int = pair[0]
				var q: int = pair[1]
				var di: int = (q % GRID_N) - (p % GRID_N)
				var dj: int = (q / GRID_N) - (p / GRID_N)
				if absi(di) == 1 and absi(dj) == 1:
					var ci := mini(p % GRID_N, q % GRID_N)
					var cj := mini(p / GRID_N, q / GRID_N)
					diag[cj * (GRID_N - 1) + ci] = 0 if di == dj else 1
	# Any vertex not covered (should not happen) falls back to the analytic terrain.
	var missing := 0
	for j in GRID_N:
		for i in GRID_N:
			if is_nan(heights0[j * GRID_N + i]):
				heights0[j * GRID_N + i] = base_height(grid_x(i), grid_x(j))
				missing += 1
	stats.grid_missing = missing


## Builds a grid from the analytic terrain only (offline tools / headless tests without meshes).
func read_analytic() -> void:
	heights0.resize(GRID_N * GRID_N)
	diag.resize((GRID_N - 1) * (GRID_N - 1))
	diag.fill(0)
	for j in GRID_N:
		for i in GRID_N:
			heights0[j * GRID_N + i] = base_height(grid_x(i), grid_x(j))


# --------------------------------------------------------------------------------------------
# Road profiles

func _prepare_profiles() -> void:
	road_profiles.clear()
	road_on_deck.clear()
	var deck: Rect2 = atlas.bridge_deck_rect()
	# Pads: start from the sampled site centres (+ arena), then relax heights so that every road
	# between two pads needs ≤ ~8° of extra grade on top of the authored 12° profile.
	pad_heights.clear()
	var centers := {}
	var radii := {}
	for site in atlas.sites:
		pad_heights[site.id] = float(site.center.y)
		centers[site.id] = Vector2(site.center.x, site.center.z)
		radii[site.id] = float(site.radius)
	for glade in atlas.extra_glades:
		pad_heights[glade.id] = float(glade.center.y)
		centers[glade.id] = Vector2(glade.center.x, glade.center.z)
		radii[glade.id] = float(glade.radius)
	pad_heights["lf_boss_arena"] = float(atlas.arena_center.y)
	centers["lf_boss_arena"] = Vector2(atlas.arena_center.x, atlas.arena_center.z)
	radii["lf_boss_arena"] = atlas.ARENA_RADIUS
	# Atlas v2 network: every other trail node (junctions, landmark spots, the horse origin, the
	# bridge ends at deck height) is a fixed tie point, so all trails meeting there meet at one
	# height (the per-trail atlas profiles may end up to 3 m apart at a shared junction).
	var fixed := {}
	for route in atlas.routes:
		for node_id in [String(route.from), String(route.to)]:
			if node_id.is_empty() or centers.has(node_id) or not atlas.landmark_by_id.has(node_id):
				continue
			var node: Dictionary = atlas.landmark_by_id[node_id]
			var deck_end: bool = node_id == "lf_bridge_west" or node_id == "lf_bridge_east"
			pad_heights[node_id] = atlas.BRIDGE_DECK_Y if deck_end else float(node.center.y)
			centers[node_id] = Vector2(float(node.center.x), float(node.center.z))
			radii[node_id] = 0.6
			fixed[node_id] = true
	junction_pads.clear()
	for node_id in fixed:
		if node_id != "lf_bridge_west" and node_id != "lf_bridge_east":
			junction_pads.append([centers[node_id], float(pad_heights[node_id])])
	var links: Array = []      # [route index, from pad, to pad, i0, i1, length]
	for r in atlas.routes.size():
		var route: Dictionary = atlas.routes[r]
		var pts: PackedVector3Array = route.points
		var from_id: String = route.from if centers.has(route.from) else ""
		var to_id: String = route.to if centers.has(route.to) else ""
		var along := PackedFloat32Array([0.0])
		for i in range(1, pts.size()):
			along.append(along[i - 1] + Vector2(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z).length())
		var i0 := 0
		var i1 := pts.size() - 1
		if not from_id.is_empty():
			while i0 < pts.size() - 1 and Vector2(pts[i0].x, pts[i0].z).distance_to(centers[from_id]) < radii[from_id]:
				i0 += 1
		if not to_id.is_empty():
			while i1 > i0 and Vector2(pts[i1].x, pts[i1].z).distance_to(centers[to_id]) < radii[to_id]:
				i1 -= 1
		links.append([r, from_id, to_id, i0, i1, maxf(1.0, along[i1] - along[i0]), along])
	for _iteration in 16:
		for link in links:
			if link[1].is_empty() or link[2].is_empty():
				continue
			var pts: PackedVector3Array = atlas.routes[link[0]].points
			var c0: float = pad_heights[link[1]] - pts[link[3]].y
			var c1: float = pad_heights[link[2]] - pts[link[4]].y
			var limit: float = tan(deg_to_rad(PAD_EXTRA_GRADE_DEG)) * link[5]
			var excess := absf(c1 - c0) - limit
			if excess > 0.0:
				var fix0: bool = fixed.has(link[1])
				var fix1: bool = fixed.has(link[2])
				if fix0 and fix1:
					continue
				var shift := excess * signf(c1 - c0) * (0.5 if not (fix0 or fix1) else 1.0)
				if not fix1:
					pad_heights[link[2]] -= shift
				if not fix0:
					pad_heights[link[1]] += shift
	for route in atlas.routes:
		var points: PackedVector3Array = route.points
		var n := points.size()
		var profile := PackedFloat32Array()
		var on_deck := PackedByteArray()
		profile.resize(n)
		on_deck.resize(n)
		var along := PackedFloat32Array()
		along.resize(n)
		for i in n:
			# decorative trails (no server way) lie on the natural ground
			profile[i] = base_height(points[i].x, points[i].z) if route.get("decor", false) else points[i].y
			along[i] = 0.0 if i == 0 else along[i - 1] + Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length()
			var on: bool = route.bridge and absf(points[i].z - atlas.BRIDGE_CENTER.z) < 0.6 \
				and points[i].x >= deck.position.x - 0.05 and points[i].x <= deck.end.x + 0.05
			on_deck[i] = 1 if on else 0
			if on:
				profile[i] = atlas.BRIDGE_DECK_Y
		# Tie into the pads: flat inside each glade, linear arc-length correction between edges.
		var link: Array = links[road_profiles.size()]
		var c_from: float = (pad_heights[link[1]] - profile[link[3]]) if not link[1].is_empty() else 0.0
		var c_to: float = (pad_heights[link[2]] - profile[link[4]]) if not link[2].is_empty() else 0.0
		for i in n:
			if on_deck[i] == 1:
				continue
			if i < link[3] and not link[1].is_empty():
				profile[i] = pad_heights[link[1]]
			elif i > link[4] and not link[2].is_empty():
				profile[i] = pad_heights[link[2]]
			elif link[4] > link[3]:
				var t := clampf((along[i] - along[link[3]]) / (along[link[4]] - along[link[3]]), 0.0, 1.0)
				profile[i] += lerpf(c_from, c_to, t)
		# Ramps: along-route distance to the nearest deck sample.
		if route.bridge:
			var deck_along: Array = []
			for i in n:
				if on_deck[i] == 1 and ((i > 0 and on_deck[i - 1] == 0) or (i < n - 1 and on_deck[i + 1] == 0)):
					deck_along.append(along[i])
			for i in n:
				if on_deck[i] == 1:
					continue
				var s := INF
				for value: float in deck_along:
					s = minf(s, absf(along[i] - value))
				if s < RAMP_LENGTH:
					profile[i] = lerpf(profile[i], atlas.BRIDGE_DECK_Y, 1.0 - smoothstep(0.0, RAMP_LENGTH, s))
		# A trail that passes close by a glade it does not end at runs level with that glade's pad
		# while it skirts it (the glade blend ring would otherwise cut a step into the trail); the
		# correction is spread along the trail so the added grade stays ≤ 7°.
		var corr := PackedFloat32Array()
		corr.resize(n)
		corr.fill(0.0)
		var any := false
		for pad_id in centers:
			if pad_id == route.from or pad_id == route.to or fixed.has(pad_id) or pad_id == "lf_boss_arena":
				continue
			var c: Vector2 = centers[pad_id]
			var pr: float = radii[pad_id]
			for i in n:
				var dd := Vector2(points[i].x, points[i].z).distance_to(c)
				if dd < pr + 4.0 and on_deck[i] == 0:
					var w := 1.0 - smoothstep(pr + 1.5, pr + 4.0, dd)
					var want: float = (float(pad_heights[pad_id]) - profile[i]) * w
					if absf(want) > absf(corr[i]):
						corr[i] = want
						any = true
		if any:
			# grade-limited spread of the correction (forward + backward passes)
			var g := tan(deg_to_rad(7.0))
			var spread := corr.duplicate()
			for i in range(1, n):
				var ds := along[i] - along[i - 1]
				var carried := spread[i - 1] - signf(spread[i - 1]) * minf(absf(spread[i - 1]), g * ds)
				if absf(carried) > absf(spread[i]):
					spread[i] = carried
			for i in range(n - 2, -1, -1):
				var ds := along[i + 1] - along[i]
				var carried := spread[i + 1] - signf(spread[i + 1]) * minf(absf(spread[i + 1]), g * ds)
				if absf(carried) > absf(spread[i]):
					spread[i] = carried
			for i in n:
				if on_deck[i] == 0 and not ((i < link[3] and not link[1].is_empty()) or (i > link[4] and not link[2].is_empty())):
					profile[i] += spread[i]
		# Two light smoothing passes (deck samples stay fixed).
		for _pass in 2:
			var copy := profile.duplicate()
			for i in range(1, n - 1):
				if on_deck[i] == 1:
					continue
				copy[i] = profile[i - 1] * 0.25 + profile[i] * 0.5 + profile[i + 1] * 0.25
			profile = copy
		road_profiles.append(profile)
		road_on_deck.append(on_deck)


## Final road height at a nearest-route hit (see ForestAtlas.nearest_route).
func road_height(hit: Dictionary) -> float:
	var profile: PackedFloat32Array = road_profiles[hit.route]
	return lerpf(profile[hit.segment], profile[hit.segment + 1], hit.t)


func road_hit_on_deck(hit: Dictionary) -> bool:
	var on_deck: PackedByteArray = road_on_deck[hit.route]
	return on_deck[hit.segment] == 1 and on_deck[hit.segment + 1] == 1


# --------------------------------------------------------------------------------------------
# Earthworks evaluation

## Height after earthworks at an arbitrary point (analytic base). Used for vertices and for
## points outside the mesh grid. Returns Vector4(height, earth, rock, road_distance).
func evaluate(x: float, z: float, h0: float) -> Vector4:
	var core := core_weight(x, z)
	if core <= 0.0:
		return Vector4(h0, 0.0, 0.0, INF)
	var h := h0
	var dirt := 0.0
	var stone := 0.0
	var road_distance := INF
	# Landmark/camp pads first; roads and glades then take precedence.
	for pad in extra_pads:
		var pd: float = Vector2(x, z).distance_to(pad[0])
		var pr: float = pad[1]
		if pd < pr + 3.0:
			h = lerpf(h, pad[2], 1.0 - smoothstep(pr * 0.75, pr + 3.0, pd))
			dirt = maxf(dirt, 0.35 * (1.0 - smoothstep(pr * 0.5, pr + 1.0, pd)))
	var hit: Dictionary = atlas.nearest_route(x, z)
	if not hit.is_empty():
		var decor: bool = atlas.routes[hit.route].get("decor", false)
		road_distance = hit.distance
		# Deck segments also shape the banks under the deck ends (abutments); the river
		# protection below keeps the wet channel itself untouched. Decorative trails only
		# colour the ground (worn dirt), they never reshape it.
		if not decor and hit.distance < ROAD_HALF_WIDTH + ROAD_BLEND:
			var w := 1.0 - smoothstep(ROAD_HALF_WIDTH, ROAD_HALF_WIDTH + ROAD_BLEND, hit.distance)
			h = lerpf(h, road_height(hit) - 0.03, w)
		# art/07: a narrow worn dirt band (the path ribbon draws the trail itself)
		dirt = maxf(dirt, (0.45 if decor else 0.52) * (1.0 - smoothstep(0.15, 0.9, hit.distance)))
	# trail junctions: a small flat landing at the node height (every trail meets it there), so
	# the ground never creases where the nearest trail switches
	for pad in junction_pads:
		var jd: float = Vector2(x, z).distance_to(pad[0])
		if jd < 4.5:
			h = lerpf(h, float(pad[1]) - 0.03, 1.0 - smoothstep(1.8, 4.5, jd))
	# outside a clearing, a trail passing by (not ending there) keeps its walking band: its profile
	# already meets the pad height at the closest approach (_prepare_profiles)
	var road_w := 0.0
	var road_route: Dictionary = {}
	if not hit.is_empty() and not atlas.routes[hit.route].get("decor", false):
		road_w = 1.0 - smoothstep(ROAD_HALF_WIDTH - 1.0, ROAD_HALF_WIDTH + 1.0, hit.distance)
		road_route = atlas.routes[hit.route]
	for site in atlas.sites:   # glade pads last: always flat inside the clearing radius
		var d := Vector2(x - site.center.x, z - site.center.z).length()
		var r: float = site.radius
		if d < r + site.blend:
			var w := 1.0 - smoothstep(r, r + site.blend, d)
			if road_w > 0.0 and road_route.from != site.id and road_route.to != site.id:
				w *= 1.0 - road_w * smoothstep(r - 0.5, r + 0.5, d)
			h = lerpf(h, float(pad_heights.get(site.id, site.center.y)), w)
		if d < r + 1.0:
			dirt = maxf(dirt, 0.55 * (1.0 - smoothstep(2.5, r + 0.5, d)))
	for glade in atlas.extra_glades:   # atlas v2: glades without a site (E-L camp)
		var d := Vector2(x - glade.center.x, z - glade.center.z).length()
		var r: float = glade.radius
		if d < r + GLADE_PAD_BLEND:
			var w := 1.0 - smoothstep(r, r + GLADE_PAD_BLEND, d)
			if road_w > 0.0 and road_route.from != glade.id and road_route.to != glade.id:
				w *= 1.0 - road_w * smoothstep(r - 0.5, r + 0.5, d)
			h = lerpf(h, float(pad_heights.get(glade.id, glade.center.y)), w)
		if d < r + 1.0:
			dirt = maxf(dirt, 0.5 * (1.0 - smoothstep(2.5, r + 0.5, d)))
	var ad := Vector2(x - atlas.arena_center.x, z - atlas.arena_center.z).length()
	if ad < ARENA_BLEND_OUTER:
		var floor_y: float = float(pad_heights.get("lf_boss_arena", atlas.arena_center.y)) - ARENA_DISH * (1.0 - pow(minf(ad, 15.0) / 15.0, 2.0))
		h = lerpf(h, floor_y, 1.0 - smoothstep(atlas.ARENA_RADIUS, ARENA_BLEND_OUTER, ad))
		dirt = maxf(dirt, 0.95 * (1.0 - smoothstep(12.5, 16.0, ad)))
		stone = maxf(stone, 0.45 * smoothstep(12.0, 15.0, ad) * (1.0 - smoothstep(16.5, 19.5, ad)))
	if quarry_center != Vector2.INF:
		var dq := Vector2(x, z).distance_to(quarry_center)
		if dq < 24.0:
			var n := 0.5 + 0.5 * sin(x * 0.61 + z * 0.37) * cos(x * 0.29 - z * 0.53)
			stone = maxf(stone, 0.85 * (1.0 - smoothstep(10.0 + 4.0 * n, 21.0, dq)))
			dirt = maxf(dirt, 0.45 * (1.0 - smoothstep(14.0, 23.0, dq)))
	# Never touch the wet river channel; blend back over 2 m outside the wet edge.
	var bank: float = atlas.river_bank_distance(x, z)
	var keep := smoothstep(0.0, 2.0, bank) * core
	var out := lerpf(h0, h, keep)
	# Atlas v2 water basins (after the river protection: the lake widens the channel itself).
	for body in water_bodies:
		var shaped := _water_shape(body, x, z, out, road_distance)
		out = shaped.x
		dirt = maxf(dirt, shaped.y * 0.5)
	return Vector4(out, dirt * core, stone * core, road_distance)


## Irregular shoreline radius of a water body at a polar angle around its centre.
static func shore_radius(body: Dictionary, angle: float) -> float:
	var s: float = body.seed
	return float(body.radius) * (1.0 + float(body.noise) * (0.6 * sin(3.0 * angle + s) + 0.4 * sin(5.0 * angle + 2.1 * s)))


## Signed distance (m) to a body's shoreline: < 0 in the water.
static func shore_distance(body: Dictionary, x: float, z: float) -> float:
	var d := Vector2(x, z) - Vector2(body.center)
	return d.length() - shore_radius(body, atan2(d.y, d.x))


## Basin of one water body: a bowl below the water inside the shore, a 0.7 m muddy margin just
## under the water line (the water mesh's own soft edge draws the shoreline), then a bank rising
## `bank` m per m; perched bodies get a low dam where the natural ground lies below the water.
## Trails (walking band + 2 m) and glade pads are never cut. Returns (height, mud weight).
func _water_shape(body: Dictionary, x: float, z: float, h: float, road_distance: float) -> Vector2:
	var c: Vector2 = body.center
	var reach: float = float(body.radius) * 1.3 + 14.0
	if absf(x - c.x) > reach or absf(z - c.y) > reach:
		return Vector2(h, 0.0)
	var sd := shore_distance(body, x, z)
	var level: float = body.level
	var target: float
	if sd < 0.0:
		var depth_t := clampf(-sd / maxf(1.0, float(body.radius) * 0.6), 0.0, 1.0)
		target = level - 0.25 - float(body.depth) * smoothstep(0.0, 1.0, depth_t)
	elif sd < 0.7:
		target = level - 0.25
	else:
		target = level - 0.25 + float(body.bank) * (sd - 0.7)
	var carved := minf(h, target)
	if body.perched and sd >= 0.0:
		var rim_w := 1.0 - smoothstep(0.9, 2.2, sd)
		carved = maxf(carved, level + 0.16 - (1.0 - rim_w) * 50.0)
	var guard := smoothstep(ROAD_HALF_WIDTH - 1.2, ROAD_HALF_WIDTH + 1.0, road_distance)
	for site in atlas.sites:
		var gd := Vector2(x - site.center.x, z - site.center.z).length()
		guard = minf(guard, smoothstep(float(site.radius) + 0.4, float(site.radius) + 2.6, gd))
	for glade in atlas.extra_glades:
		var gd := Vector2(x - glade.center.x, z - glade.center.z).length()
		guard = minf(guard, smoothstep(float(glade.radius) + 0.4, float(glade.radius) + 2.6, gd))
	var mud := (1.0 - smoothstep(0.4, 2.2, sd)) * guard
	return Vector2(lerpf(h, carved, guard), mud)


func bake() -> void:
	if heights0.is_empty():
		read_analytic()
	_prepare_profiles()
	heights = heights0.duplicate()
	earth.resize(GRID_N * GRID_N)
	earth.fill(0.0)
	rock.resize(GRID_N * GRID_N)
	rock.fill(0.0)
	tint.resize(GRID_N * GRID_N)
	tint.fill(Color(1, 1, 1))
	var changed := 0
	for j in GRID_N:
		var z := grid_x(j)
		for i in GRID_N:
			var x := grid_x(i)
			var k := j * GRID_N + i
			if maxf(absf(x), absf(z)) <= CORE:
				continue
			var result := evaluate(x, z, heights0[k])
			if absf(result.x - heights0[k]) > 0.0005:
				changed += 1
			heights[k] = result.x
			earth[k] = result.y
			rock[k] = result.z
	# Slope rock (limestone biome & steep banks) and biome tint after heights are final.
	for j in range(1, GRID_N - 1):
		var z := grid_x(j)
		for i in range(1, GRID_N - 1):
			var x := grid_x(i)
			var k := j * GRID_N + i
			var core := core_weight(x, z)
			if core <= 0.0:
				continue
			var gx := (heights[k + 1] - heights[k - 1]) / (2.0 * GRID_STEP)
			var gz := (heights[k + GRID_N] - heights[k - GRID_N]) / (2.0 * GRID_STEP)
			var slope := rad_to_deg(atan(sqrt(gx * gx + gz * gz)))
			var weights := region_weights(x, z)
			var color := Color(0, 0, 0)
			var shade_min := 0.0
			for b in weights.size():
				color += REGION_TINTS[b] * weights[b]
				shade_min += float(FLOOR_SHADE[b]) * weights[b]
			var bank: float = atlas.river_bank_distance(x, z)
			var wet := 1.0 - smoothstep(0.0, 5.0, bank)
			for body in water_bodies:
				wet = maxf(wet, 1.0 - smoothstep(0.0, 3.5, shore_distance(body, x, z)))
			color = color.lerp(WET_TINT, wet * 0.8)
			var limestone := weights[6] + 0.5 * weights[2]
			rock[k] = maxf(rock[k], smoothstep(16.0, 30.0, slope) * (0.45 + 0.5 * limestone) * core)
			earth[k] = maxf(earth[k], limestone * 0.18 * core)
			# Shaded forest floor (darker under the canopy, light on paths/glades), as in art/01:
			# mossy and dark under the south pines, sunny under the golden grove.
			var floor_shade := lerpf(shade_min, 1.0, clampf(earth[k] * 1.4, 0.0, 1.0))
			color = Color(color.r * floor_shade, color.g * floor_shade, color.b * floor_shade)
			tint[k] = Color(1, 1, 1).lerp(color, core)
	stats.changed_vertices = changed
	grid_ready = true


## Atlas v2 region weights for the ground tint (same regions as the layout builder's zones):
## warped screen sectors + the quarry pit, the meadow belt round the walls and the river banks.
func region_weights(x: float, z: float) -> PackedFloat32Array:
	var phi_offset := 9.0 * sin(x * 0.043 + z * 0.027) + 6.0 * sin(z * 0.061 - x * 0.019)
	var w: PackedFloat32Array = atlas.region_sector_weights(x, z, phi_offset)
	if quarry_center != Vector2.INF:
		var q := 1.0 - smoothstep(16.0, 30.0, Vector2(x, z).distance_to(quarry_center) + 3.0 * sin(x * 0.31 + z * 0.17))
		for i in w.size():
			w[i] *= 1.0 - q
		w[6] = maxf(w[6], q * 1.2)
	var belt := 1.0 - smoothstep(4.0, 16.0, maxf(absf(x), absf(z)) - CORE + 3.0 * sin(z * 0.09 + x * 0.05))
	for i in w.size():
		w[i] *= 1.0 - belt * 0.85
	w[7] += belt
	var river := 1.0 - smoothstep(4.0, 12.0, atlas.river_bank_distance(x, z))
	for i in w.size():
		w[i] *= 1.0 - river * 0.8
	w[4] += river
	var total := 0.0
	for v in w:
		total += v
	if total <= 0.0001:
		w[3] = 1.0
		return w
	for i in w.size():
		w[i] /= total
	return w


# --------------------------------------------------------------------------------------------
# Queries

func _cell_height(field: PackedFloat32Array, x: float, z: float) -> float:
	var fx := (x - GRID_MIN) / GRID_STEP
	var fz := (z - GRID_MIN) / GRID_STEP
	var i := clampi(floori(fx), 0, GRID_N - 2)
	var j := clampi(floori(fz), 0, GRID_N - 2)
	var u := clampf(fx - i, 0.0, 1.0)
	var v := clampf(fz - j, 0.0, 1.0)
	var h00 := field[j * GRID_N + i]
	var h10 := field[j * GRID_N + i + 1]
	var h01 := field[(j + 1) * GRID_N + i]
	var h11 := field[(j + 1) * GRID_N + i + 1]
	if diag[j * (GRID_N - 1) + i] == 0:
		# Diagonal (0,0)-(1,1)
		if u >= v:
			return h00 + (h10 - h00) * u + (h11 - h10) * v
		return h00 + (h01 - h00) * v + (h11 - h01) * u
	# Diagonal (1,0)-(0,1)
	if u + v <= 1.0:
		return h00 + (h10 - h00) * u + (h01 - h00) * v
	return h11 + (h01 - h11) * (1.0 - u) + (h10 - h11) * (1.0 - v)


func inside_grid(x: float, z: float) -> bool:
	var limit := GRID_MIN + (GRID_N - 1) * GRID_STEP
	return x >= GRID_MIN and z >= GRID_MIN and x <= limit and z <= limit


## Rendered ground height (earthworks applied, exact triangle interpolation).
func ground_height(x: float, z: float) -> float:
	if grid_ready and inside_grid(x, z):
		return _cell_height(heights, x, z)
	return base_height(x, z)


## Original (pre-earthworks) rendered height.
func original_height(x: float, z: float) -> float:
	if not heights0.is_empty() and inside_grid(x, z):
		return _cell_height(heights0, x, z)
	return base_height(x, z)


func on_bridge_deck(x: float, z: float) -> bool:
	return atlas.bridge_deck_rect().grow(0.02).has_point(Vector2(x, z))


## Walkable height: bridge deck where it spans, otherwise the rendered ground.
func height_at(x: float, z: float) -> float:
	var h := ground_height(x, z)
	var deck: Rect2 = atlas.bridge_deck_rect()
	var outside := Vector2(maxf(maxf(deck.position.x - x, x - deck.end.x), 0.0), maxf(maxf(deck.position.y - z, z - deck.end.y), 0.0)).length()
	if outside <= 0.0:
		return maxf(h, atlas.BRIDGE_DECK_Y)
	if outside < 1.5 and h < atlas.BRIDGE_DECK_Y:
		# Abutment apron: walkable height eases off the deck edge (bridge mesh covers the seam);
		# continuous in both distance and depth (fades out over water/gorge).
		var w := (1.0 - smoothstep(0.0, 1.5, outside)) * (1.0 - smoothstep(0.5, 1.0, atlas.BRIDGE_DECK_Y - h))
		return lerpf(h, atlas.BRIDGE_DECK_Y, w)
	return h


func slope_degrees(x: float, z: float) -> float:
	var e := 0.75
	var gx := (ground_height(x + e, z) - ground_height(x - e, z)) / (2.0 * e)
	var gz := (ground_height(x, z + e) - ground_height(x, z - e)) / (2.0 * e)
	return rad_to_deg(atan(sqrt(gx * gx + gz * gz)))


# --------------------------------------------------------------------------------------------
# Mesh rewrite

## Returns a new ArrayMesh for a tile (same vertex order and indices), or null if unchanged.
func rebuild_tile(mesh: Mesh) -> ArrayMesh:
	var arrays := mesh.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR] if arrays[Mesh.ARRAY_COLOR] != null else PackedColorArray()
	var uv2: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV2] if arrays[Mesh.ARRAY_TEX_UV2] != null else PackedVector2Array()
	var touched := false
	for k in vertices.size():
		var v := vertices[k]
		if maxf(absf(v.x), absf(v.z)) <= CORE:
			continue
		var i := roundi((v.x - GRID_MIN) / GRID_STEP)
		var j := roundi((v.z - GRID_MIN) / GRID_STEP)
		if i < 1 or j < 1 or i >= GRID_N - 1 or j >= GRID_N - 1:
			continue
		var g := j * GRID_N + i
		touched = true
		var delta := heights[g] - heights0[g]
		v.y = heights[g]
		vertices[k] = v
		if absf(delta) > 0.0005 or absf(heights[g - 1] - heights0[g - 1]) > 0.0005 or absf(heights[g + 1] - heights0[g + 1]) > 0.0005 \
				or absf(heights[g - GRID_N] - heights0[g - GRID_N]) > 0.0005 or absf(heights[g + GRID_N] - heights0[g + GRID_N]) > 0.0005:
			var gx := (heights[g + 1] - heights[g - 1]) / (2.0 * GRID_STEP)
			var gz := (heights[g + GRID_N] - heights[g - GRID_N]) / (2.0 * GRID_STEP)
			normals[k] = Vector3(-gx, 1.0, -gz).normalized()
		if not colors.is_empty():
			var c := colors[k]
			var t := tint[g]
			colors[k] = Color(c.r * t.r, c.g * t.g, c.b * t.b, c.a)
		if not uv2.is_empty():
			var w := uv2[k]
			uv2[k] = Vector2(maxf(w.x, earth[g]), maxf(w.y, rock[g]))
	if not touched:
		return null
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	if not colors.is_empty():
		arrays[Mesh.ARRAY_COLOR] = colors
	if not uv2.is_empty():
		arrays[Mesh.ARRAY_TEX_UV2] = uv2
	# Tangents are kept: terrain UV runs along +X, so the original tangent frame stays valid.
	var result := ArrayMesh.new()
	result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var material := mesh.surface_get_material(0)
	if material != null:
		result.surface_set_material(0, material)
	return result
