extends SceneTree
## Offline, deterministic builder of the natural forest layout v2 + resource-tree remap.
##   godot --headless --path godot/project -s res://src/forest_rescue/world/tools/build_forest_layout.gd
## Output: res://data/forest_rescue/world/forest_layout_v2.json (see forest_layout_rules.gd).
##
## Composition follows the art/01 masterplan in the CITY CAMERA's screen space (the painting is
## drawn from that view: river vertical right of the town). Screen angle φ around the town
## (CCW from screen-right; screen-up = world (-X,-Z)): golden-oak grove upper-left with the hero
## cave oak, quarry lower-left (glade 08), dark spruce forest at the bottom, willows/reeds along
## the river, arena pines upper-right, mixed broadleaf/birch transitions and a mixed belt
## around the protected town. Zones blend over ~10 m with a warped angle (no straight borders).
##
## 1. Hero cave oak + landmark spots are reserved (trunk-free discs).
## 2. Outer resource trees (|x|>56 or |z|>56): every id is moved off its old sunflower-spiral
##    point to a natural spot ≤ 4 m away (clump-biased, ≥ 2.3 m from other trunks, outside
##    route/glade/arena/bridge/landmark clearances). Trees whose old point lies inside a
##    clearance are pushed out (≤ 6.5 m keeps the stump inside its ±6.7 m prepared-site plot).
## 3. Inner resource trees (±56, the player's base) are jittered ≤ 3.5 m to break the spiral
##    rows, staying on the same side of every plot square and ≥ 1.8 m off the town roads.
## 4. Ambient trees fill each zone to its art/01 density with the zone's species mix.
## 5. Understory by zone (ferns, brambles, rocks, logs, branches, quarry boulders, reeds).
## Resource-tree look (kit variant + absolute scale) is chosen per zone so that the zone's
## dominant species reads as in art/01 even though resource species are fixed by id.

const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")
const ForestAtlas = preload("res://src/forest_rescue/world/forest_atlas.gd")
const ForestTerrain = preload("res://src/forest_rescue/world/forest_terrain.gd")
const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")
const ForestLandmarks = preload("res://src/forest_rescue/world/forest_landmarks.gd")

const EXTENT := 140.0
const CORE := 56.0
const HASH := 2.0
const SQRT2 := 1.41421356

## Zones (index in the layout file, "zone" field of tree items).
const Z_GROVE := 0
const Z_TOP := 1
const Z_ARENA := 2
const Z_EAST := 3
const Z_RIVER := 4
const Z_SPRUCE := 5
const Z_QUARRY := 6
const Z_BELT := 7
const ZONE_NAMES := ["golden_grove", "top_birch_oak", "arena_pines", "east_mixed", "river_willows", "south_spruce", "sw_quarry", "town_belt"]
## Screen-angle sectors [from°, to°] (CCW from screen-right). Belt/river/quarry are spatial.
const SECTORS := {Z_ARENA: [12.0, 58.0], Z_TOP: [58.0, 104.0], Z_GROVE: [104.0, 212.0], Z_SPRUCE: [226.0, 306.0], Z_EAST: [306.0, 372.0]}
## Ambient species mix per zone (resource trees keep their species).
const ZONE_MIX := [
	{Rules.OAK: 0.92, Rules.PINE: 0.04, Rules.BIRCH: 0.04},                 # golden grove (big oaks)
	{Rules.BIRCH: 0.45, Rules.OAK: 0.35, Rules.PINE: 0.20},                 # top: birch + oak
	{Rules.PINE: 0.80, Rules.OAK: 0.12, Rules.BIRCH: 0.08},                 # arena pines
	{Rules.BIRCH: 0.40, Rules.WILLOW: 0.22, Rules.PINE: 0.28, Rules.OAK: 0.10},  # east mixed
	{Rules.WILLOW: 0.62, Rules.BIRCH: 0.22, Rules.PINE: 0.16},              # river willows
	{Rules.PINE: 0.92, Rules.BIRCH: 0.05, Rules.OAK: 0.03},                 # south spruce
	{Rules.BIRCH: 0.45, Rules.PINE: 0.45, Rules.OAK: 0.10},                 # quarry (sparse)
	{Rules.BIRCH: 0.45, Rules.PINE: 0.30, Rules.OAK: 0.25},                 # town belt
]
## Ambient spacing (m) per zone: target trunk spacing incl. resource trees.
const ZONE_SPACING := [13.0, 5.2, 3.7, 4.3, 4.8, 3.3, 9.0, 5.2]
## Absolute scale ranges per [zone][species] for AMBIENT trees (inside kit recommendedScale).
const AMBIENT_SCALE := {
	Rules.OAK: [[0.94, 1.10], [0.70, 0.88], [0.66, 0.80], [0.66, 0.82], [0.66, 0.80], [0.66, 0.78], [0.66, 0.78], [0.66, 0.82]],
	Rules.PINE: [[0.78, 0.98], [0.80, 1.00], [0.90, 1.16], [0.84, 1.06], [0.80, 1.00], [0.92, 1.20], [0.80, 1.00], [0.78, 0.96]],
	Rules.BIRCH: [[0.80, 0.95], [0.86, 1.08], [0.80, 0.96], [0.86, 1.10], [0.84, 1.04], [0.80, 0.95], [0.84, 1.00], [0.82, 1.00]],
	Rules.WILLOW: [[0.82, 0.98], [0.82, 1.0], [0.82, 1.0], [0.86, 1.06], [0.88, 1.12], [0.82, 1.0], [0.82, 1.0], [0.84, 1.0]],
}
## Resource-tree absolute scale ranges per zone [oak, pine] (zone decides which one dominates).
const RESOURCE_SCALE_OUTER := [
	[[0.46, 0.58], [0.56, 0.68]],   # grove: young oaks/pines under sparse big oaks
	[[0.44, 0.56], [0.68, 0.84]],
	[[0.40, 0.48], [0.92, 1.12]],   # arena pines
	[[0.42, 0.52], [0.82, 1.02]],
	[[0.42, 0.52], [0.76, 0.94]],
	[[0.38, 0.46], [0.96, 1.20]],   # spruce: young oaks under tall spruces
	[[0.42, 0.52], [0.74, 0.88]],
	[[0.44, 0.56], [0.72, 0.88]],
]
## Inner base (±56): the town stays readable (legacy-like 8–10 m crowns).
const RESOURCE_SCALE_INNER := [[0.46, 0.58], [0.60, 0.74]]
## Kit variant palettes per zone & species (art/01: v2+; v1 = art/02 hero accents).
const ZONE_VARIANTS := {
	Rules.OAK: [[2, 3, 4], [2, 3, 4, 1], [1, 2, 3], [2, 3, 4, 1], [2, 3, 4], [1, 2, 3], [2, 3, 4], [2, 3, 4, 1]],
	Rules.PINE: [[2, 3, 4], [2, 3, 4], [2, 3, 4], [2, 3, 4], [2, 3], [2, 3, 4], [2, 3, 4], [2, 3, 4]],
	Rules.BIRCH: [[2, 3], [2, 3, 1], [2, 3], [2, 3], [2, 3], [2, 3], [2, 3, 1], [2, 3]],
	Rules.WILLOW: [[2, 3], [2, 3], [2, 3], [2, 3], [2, 3], [2, 3], [2, 3], [2, 3]],
}
## Understory weights per zone over Rules.UNDERSTORY
## (fern, reed, bramble, rock, trunk, branches, quarry_rock, grass, mushrooms) and spacing (m).
const ZONE_UNDERSTORY := [
	[0.30, 0.0, 0.14, 0.10, 0.06, 0.08, 0.00, 0.26, 0.06],
	[0.30, 0.0, 0.16, 0.08, 0.05, 0.08, 0.00, 0.27, 0.06],
	[0.36, 0.0, 0.10, 0.18, 0.08, 0.10, 0.06, 0.08, 0.04],
	[0.34, 0.0, 0.18, 0.10, 0.05, 0.08, 0.00, 0.20, 0.05],
	[0.20, 0.30, 0.10, 0.20, 0.04, 0.04, 0.00, 0.12, 0.00],
	[0.44, 0.0, 0.10, 0.10, 0.10, 0.12, 0.00, 0.06, 0.08],
	[0.06, 0.0, 0.06, 0.18, 0.04, 0.06, 0.50, 0.10, 0.00],
	[0.30, 0.0, 0.20, 0.06, 0.04, 0.08, 0.00, 0.30, 0.02],
]
const ZONE_UNDER_SPACING := [3.4, 3.2, 3.6, 3.3, 3.0, 3.1, 3.6, 3.5]
## Hero cave oak (art/01 top-left corner of the grove): screen φ≈149°, near the overview edge.
const HERO_PREFERRED := Vector2(-104.0, 24.0)
const HERO_CLEAR := 9.5

var atlas
var terrain
var masks
var rng := RandomNumberGenerator.new()
var warp := FastNoiseLite.new()
var clump := FastNoiseLite.new()
var glade := FastNoiseLite.new()
var landmark_discs: Array = []      # [[Vector2, radius]]
var hero := Vector2.INF
var quarry_center := Vector2.INF
var trunks: Array = []               # [x, z, gap] all placed trunks (resource + ambient)
var trunk_grid := {}
var data: Dictionary


func _initialize() -> void:
	call_deferred("run")


func cell_key(x: float, z: float) -> Vector2i:
	return Vector2i(floori(x / HASH), floori(z / HASH))


func near_points(x: float, z: float, reach: float, grid: Dictionary, store: Array) -> Array:
	var result: Array = []
	for gz in range(floori((z - reach) / HASH), floori((z + reach) / HASH) + 1):
		for gx in range(floori((x - reach) / HASH), floori((x + reach) / HASH) + 1):
			for index in grid.get(Vector2i(gx, gz), PackedInt32Array()):
				result.append(store[index])
	return result


func insert(grid: Dictionary, store: Array, entry: Array) -> int:
	var index := store.size()
	store.append(entry)
	var key := cell_key(entry[0], entry[1])
	if not grid.has(key):
		grid[key] = PackedInt32Array()
	grid[key].append(index)
	return index


# ---------------------------------------------------------------------------------------------
# Zoning (screen space of the city camera)

static func screen_angle(x: float, z: float) -> float:
	var sx := (x - z) / SQRT2
	var up := (-x - z) / SQRT2
	return fposmod(rad_to_deg(atan2(up, sx)), 360.0)


func _sector_weight(phi: float, a: float, b: float, blend: float) -> float:
	# Smooth bump over [a, b] (degrees, may wrap past 360).
	var best := 0.0
	for shift in [-360.0, 0.0, 360.0]:
		var p: float = phi + float(shift)
		best = maxf(best, smoothstep(a - blend, a + blend, p) * (1.0 - smoothstep(b - blend, b + blend, p)))
	return best


func zone_weights(x: float, z: float) -> PackedFloat32Array:
	var w := PackedFloat32Array()
	w.resize(8)
	var phi := screen_angle(x, z) + warp.get_noise_2d(x, z) * 16.0
	for zone in SECTORS:
		var s: Array = SECTORS[zone]
		w[zone] = _sector_weight(phi, s[0], s[1], 11.0)
	# Quarry: around the SW quarry centre (glade 08 / mine), ragged edge.
	if quarry_center != Vector2.INF:
		var dq := Vector2(x, z).distance_to(quarry_center) + warp.get_noise_2d(x * 1.7, z * 1.7) * 6.0
		var q := 1.0 - smoothstep(18.0, 32.0, dq)
		for i in w.size():
			w[i] *= (1.0 - q)
		w[Z_QUARRY] = maxf(w[Z_QUARRY], q * 1.2)
	# Mixed belt around the protected town (art/01 green belt outside the walls).
	var from_core := maxf(absf(x), absf(z)) - CORE
	var belt := 1.0 - smoothstep(5.0, 17.0, from_core + warp.get_noise_2d(z, x) * 5.0)
	for i in w.size():
		w[i] *= (1.0 - belt * 0.85)
	w[Z_BELT] += belt
	# River banks: willows and reeds (wet channel itself has no trees).
	var bank: float = atlas.river_bank_distance(x, z)
	var river := 1.0 - smoothstep(5.0, 13.0, bank + warp.get_noise_2d(x * 2.3, z * 2.3) * 3.0)
	for i in w.size():
		w[i] *= (1.0 - river * 0.8)
	w[Z_RIVER] += river
	var total := 0.0
	for v in w:
		total += v
	if total <= 0.0001:
		w[Z_EAST] = 1.0
		return w
	for i in w.size():
		w[i] /= total
	return w


func dominant_zone(x: float, z: float) -> int:
	var w := zone_weights(x, z)
	var best := 0
	for i in w.size():
		if w[i] > w[best]:
			best = i
	return best


func pick_zone(x: float, z: float) -> int:
	return Rules.pick_index(Array(zone_weights(x, z)), rng.randf())


# ---------------------------------------------------------------------------------------------
# Clearances

## crown: crown radius (m) of the tree that would stand here; up to ~45 % of it may overhang a
## path or glade (art/01: trails stay readable between the crowns).
func blocked_exact(x: float, z: float, tree: bool, margin_scale := 1.0, crown := 0.0) -> bool:
	if maxf(absf(x), absf(z)) < CORE + (0.8 if tree else 0.3):
		return true
	var reach := 6.0 + crown * 0.55
	for gz in range(floori((z - reach) / masks.cell), floori((z + reach) / masks.cell) + 1):
		for gx in range(floori((x - reach) / masks.cell), floori((x + reach) / masks.cell) + 1):
			for index in masks.grid.get(Vector2i(gx, gz), PackedInt32Array()):
				var mask: Dictionary = masks.masks[index]
				var margin := 0.0
				match String(mask.get("kind", "")):
					"route":
						margin = (Rules.ROUTE_TRUNK_MARGIN + crown * 0.45) * margin_scale if tree else 0.0
					"glade":
						margin = (Rules.GLADE_TRUNK_MARGIN + crown * 0.4) * margin_scale if tree else 0.3
					"arena":
						margin = (2.0 + crown * 0.4) * margin_scale if tree else 0.5
					"bridge":
						margin = 0.8
					"core", "reserve":
						continue
				if ForestMasks.inside_mask(x, z, mask, margin):
					return true
	for disc in landmark_discs:
		if Vector2(x, z).distance_to(disc[0]) < float(disc[1]) * (1.0 if tree else 0.75):
			return true
	if hero != Vector2.INF and Vector2(x, z).distance_to(hero) < (HERO_CLEAR if tree else 5.5):
		return true
	return false


func ground_ok(x: float, z: float, tree: bool) -> bool:
	var h: float = terrain.ground_height(x, z)
	if h < -0.35:
		return false
	if atlas.river_bank_distance(x, z) < (1.2 if tree else 0.4):
		return false
	return terrain.slope_degrees(x, z) <= (28.0 if tree else 36.0)


func free_of_trunks(x: float, z: float, gap: float) -> bool:
	for other in near_points(x, z, gap + 3.0, trunk_grid, trunks):
		var limit := maxf(gap, float(other[2]))
		if Vector2(x - other[0], z - other[1]).length_squared() < limit * limit:
			return false
	return true


func is_glade(x: float, z: float) -> bool:
	# Art glades: low-frequency noise holes (open grassy clearings between clumps, art/01 grove).
	var zone := dominant_zone(x, z)
	var threshold := 0.22 if zone == Z_GROVE else (0.15 if zone in [Z_TOP, Z_EAST, Z_BELT, Z_QUARRY] else 0.07)
	return (glade.get_noise_2d(x, z) + 1.0) * 0.5 < threshold


# ---------------------------------------------------------------------------------------------

func run() -> void:
	var started := Time.get_ticks_msec()
	rng.seed = Rules.SEED
	warp.seed = Rules.SEED + 11
	warp.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	warp.frequency = 1.0 / 46.0
	warp.fractal_octaves = 3
	clump.seed = Rules.SEED + 23
	clump.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	clump.frequency = 1.0 / 17.0
	clump.fractal_octaves = 2
	glade.seed = Rules.SEED + 37
	glade.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	glade.frequency = 1.0 / 30.0
	glade.fractal_octaves = 2
	atlas = ForestAtlas.load_default()
	terrain = ForestTerrain.new(atlas)
	terrain.read_analytic()
	masks = ForestMasks.MaskSet.new(8.0)
	for mask in atlas.static_masks():
		masks.add(mask)
	data = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	# Landmark spots (same deterministic plan as the runtime) → trunk-free discs + terrain pads.
	var landmarks = ForestLandmarks.new()
	landmarks.plan(atlas, masks, func(x: float, z: float) -> float: return ForestTerrain.base_height(x, z))
	terrain.extra_pads = landmarks.pads()
	terrain.bake()
	for disc in landmarks.clearances():
		landmark_discs.append(disc)
	for placement in landmarks.placements:
		if placement.id == "lf_env_quarry_mine":
			quarry_center = Vector2(placement.position.x, placement.position.z).lerp(
				Vector2(atlas.site_by_id.lf_site_08.center.x, atlas.site_by_id.lf_site_08.center.z), 0.45)
	landmarks.free()
	print("LAYOUT terrain+masks ready ms=", Time.get_ticks_msec() - started, " quarry=", quarry_center)

	# 1. Hero cave oak ------------------------------------------------------------------------
	hero = _find_hero_spot()
	print("LAYOUT hero cave oak at ", hero)

	# 2. Outer resource remap -------------------------------------------------------------------
	var outer: Array = []
	var inner: Array = []
	for tree in data.woods:
		var p: Array = tree.p
		if maxf(absf(float(p[0])), absf(float(p[2]))) > CORE:
			outer.append(tree)
		else:
			inner.append(tree)
	outer.sort_custom(func(a, b): return String(a.id).naturalnocasecmp_to(String(b.id)) < 0)
	inner.sort_custom(func(a, b): return String(a.id).naturalnocasecmp_to(String(b.id)) < 0)
	var order := range(outer.size())
	_shuffle(order)
	var remap := {}
	var reasons := {"slot": 0, "mask_push": 0, "jitter": 0, "kept": 0}
	var displacements := PackedFloat32Array()
	for t in order:
		var tree: Dictionary = outer[t]
		var tx := float(tree.p[0])
		var tz := float(tree.p[2])
		var species: int = Rules.RESOURCE_SPECIES.get(String(tree.name), Rules.PINE)
		var gap := Rules.MIN_TREE_GAP if species == Rules.PINE else 2.6
		var crown := _resource_crown(tree, species, dominant_zone(tx, tz))
		var in_mask := blocked_exact(tx, tz, true, 1.0, crown) or not ground_ok(tx, tz, true) or is_glade(tx, tz)
		var found := Vector2.INF
		var reason := 0
		if not in_mask:
			found = _best_spot(tx, tz, 1.0, Rules.MAX_SLOT_DISPLACEMENT, gap, 40, crown)
		if found == Vector2.INF:
			reason = 1 if in_mask else 2
			found = _nearest_free(tx, tz, 6.5, gap, crown, true)
		if found == Vector2.INF:
			found = _nearest_free(tx, tz, 6.5, gap, 0.0, false)
		if found == Vector2.INF:
			reason = 3
			found = _nearest_free(tx, tz, 14.0, 1.6)
		if found == Vector2.INF:
			var angle := rng.randf() * TAU
			found = Vector2(tx + cos(angle) * 1.2, tz + sin(angle) * 1.2)
		insert(trunk_grid, trunks, [found.x, found.y, gap])
		var zone := dominant_zone(found.x, found.y)
		var look := _resource_look(tree, species, zone, false)
		remap[tree.id] = [snappedf(found.x, 0.01), snappedf(found.y, 0.01), reason, look[0], look[1]]
		reasons[["slot", "mask_push", "jitter", "kept"][reason]] += 1
		displacements.append(Vector2(tx - found.x, tz - found.y).length())
	print("LAYOUT remap ", reasons, " ms=", Time.get_ticks_msec() - started)

	# 3. Inner resource jitter (player's base) --------------------------------------------------
	var inner_remap := {}
	var inner_moved := PackedFloat32Array()
	var plot_rects: Array = []
	for plot in data.plots + data.legacyPlots:
		plot_rects.append(Rect2(float(plot.x) - 6.7, float(plot.z) - 6.7, 13.4, 13.4))
	for grove in data.clearings:
		var half := float(grove.size) * 0.5
		plot_rects.append(Rect2(float(grove.x) - half, float(grove.z) - half, float(grove.size), float(grove.size)))
	var inner_trunks: Array = []
	var inner_grid := {}
	for tree in inner:
		insert(inner_grid, inner_trunks, [float(tree.p[0]), float(tree.p[2]), 0.0])
	var inner_order := range(inner.size())
	_shuffle(inner_order)
	var placed_inner: Array = []
	var placed_inner_grid := {}
	for t in inner_order:
		var tree: Dictionary = inner[t]
		var o := Vector2(float(tree.p[0]), float(tree.p[2]))
		var membership := _rect_membership(o, plot_rects)
		var species: int = Rules.RESOURCE_SPECIES.get(String(tree.name), Rules.PINE)
		var best := o
		var best_score := -INF
		for k in 28:
			var angle := rng.randf() * TAU
			var dist := lerpf(1.0, Rules.MAX_INNER_JITTER, sqrt(rng.randf()))
			var q := o + Vector2(cos(angle), sin(angle)) * dist
			if maxf(absf(q.x), absf(q.y)) > CORE - 0.4 or _rect_membership(q, plot_rects) != membership:
				continue
			if _near_road(q, 1.8) or terrain.ground_height(q.x, q.y) < -0.3:
				continue
			var ok := true
			for other in near_points(q.x, q.y, 3.0, placed_inner_grid, placed_inner):
				if q.distance_to(Vector2(other[0], other[1])) < 2.2:
					ok = false
					break
			if not ok:
				continue
			var score := (clump.get_noise_2d(q.x, q.y) + 1.0) * 0.6 + rng.randf() * 0.5
			if score > best_score:
				best_score = score
				best = q
		insert(placed_inner_grid, placed_inner, [best.x, best.y, 0.0])
		var look := _resource_look(tree, species, Z_BELT, true)
		inner_remap[tree.id] = [snappedf(best.x, 0.01), snappedf(best.y, 0.01), 0 if best != o else 3, look[0], look[1]]
		inner_moved.append(best.distance_to(o))
	inner_moved.sort()
	print("LAYOUT inner jitter median=", inner_moved[inner_moved.size() / 2], " max=", inner_moved[-1])

	# 4. Ambient trees --------------------------------------------------------------------------
	var trees: Array = []
	var species_count := {}
	if hero != Vector2.INF:
		trees.append([snappedf(hero.x, 0.01), snappedf(hero.y, 0.01), Rules.HOLLOW_OAK, 2, 225.0, Rules.HERO_SCALE, Z_GROVE])
		species_count[Rules.SPECIES[Rules.HOLLOW_OAK]] = 1
	var cells: Array = []
	var span := int(EXTENT * 2.0)
	for j in span:
		for i in span:
			cells.append(Vector2i(i, j))
	_shuffle(cells)
	for pass_index in 2:
		for cell: Vector2i in cells:
			var x := -EXTENT + cell.x + rng.randf()
			var z := -EXTENT + cell.y + rng.randf()
			if maxf(absf(x), absf(z)) < CORE + 0.8:
				continue
			if blocked_exact(x, z, true) or not ground_ok(x, z, true) or is_glade(x, z):
				continue
			var w := zone_weights(x, z)
			var spacing := 0.0
			for i in w.size():
				spacing += ZONE_SPACING[i] * w[i]
			var c := (clump.get_noise_2d(x, z) + 1.0) * 0.5
			spacing *= lerpf(1.35, 0.8, smoothstep(0.25, 0.75, c))
			if pass_index == 1:
				spacing *= 0.92
			var zone := Rules.pick_index(Array(w), rng.randf())
			var species := Rules.pick_weighted(ZONE_MIX[zone], rng.randf())
			var gap := spacing if species != Rules.PINE else spacing * 0.86
			if not free_of_trunks(x, z, gap):
				continue
			var scale_range: Array = AMBIENT_SCALE[species][zone]
			var scale := lerpf(scale_range[0], scale_range[1], rng.randf())
			if blocked_exact(x, z, true, 1.0, Rules.CROWN_RADIUS[species] * scale):
				continue
			insert(trunk_grid, trunks, [x, z, minf(gap, 3.0 if species != Rules.OAK or zone != Z_GROVE else 6.0)])
			var variants: Array = ZONE_VARIANTS[species][zone]
			var variant: int = variants[rng.randi() % variants.size()]
			trees.append([snappedf(x, 0.01), snappedf(z, 0.01), species, variant,
				snappedf(rng.randf() * 360.0, 0.1), snappedf(scale, 0.001), zone])
			species_count[Rules.SPECIES[species]] = species_count.get(Rules.SPECIES[species], 0) + 1
	print("LAYOUT ambient trees=", trees.size(), " ", species_count)

	# 5. Understory -----------------------------------------------------------------------------
	var under: Array = []
	var under_grid := {}
	var logs: Array = []
	var log_grid := {}
	_shuffle(cells)
	var kinds_count := {}
	for cell: Vector2i in cells:
		var x := -EXTENT + cell.x + rng.randf()
		var z := -EXTENT + cell.y + rng.randf()
		if maxf(absf(x), absf(z)) < CORE + 0.3:
			continue
		var zone := pick_zone(x, z)
		var h: float = terrain.ground_height(x, z)
		var slope: float = terrain.slope_degrees(x, z)
		var bank: float = atlas.river_bank_distance(x, z)
		var kind := Rules.pick_index(ZONE_UNDERSTORY[zone], rng.randf())
		var kind_name: String = Rules.UNDERSTORY[kind]
		# The river runs in a gorge: reeds on the wet margin, boulders on the steep walls.
		var reed_zone := bank > -0.4 and bank < 1.2 and h > -1.3 and h < 0.8
		var wall_zone := bank >= 1.2 and bank < 4.5 and slope > 30.0
		if reed_zone:
			kind_name = "reed" if rng.randf() < 0.8 else "rock"
		elif wall_zone:
			if rng.randf() > 0.35:
				continue
			kind_name = "rock"
		elif h < -0.3 or slope > 34.0:
			continue
		elif kind_name == "reed":
			kind_name = "fern"
		kind = Rules.UNDERSTORY.find(kind_name)
		var r: float = ZONE_UNDER_SPACING[zone]
		if is_glade(x, z):
			r *= 1.5
			if kind_name in ["fern", "trunk", "quarry_rock"] and rng.randf() < 0.6:
				kind_name = "grass"
				kind = Rules.UNDERSTORY.find(kind_name)
		if kind_name == "quarry_rock":
			r = 4.2
		elif kind_name == "reed":
			r = 2.2
		if blocked_exact(x, z, false):
			continue
		var ok := true
		for other in near_points(x, z, r + 1.0, under_grid, under):
			if Vector2(x - other[0], z - other[1]).length() < r:
				ok = false
				break
		if not ok:
			continue
		var trunk_gap := 1.1 if not kind_name in ["trunk", "rock", "quarry_rock"] else 2.8
		if not free_of_trunks(x, z, trunk_gap):
			continue
		if kind_name in ["trunk", "rock", "quarry_rock"]:
			var spacing := 10.0 if kind_name == "trunk" else (6.0 if kind_name == "quarry_rock" else 8.0)
			for other in near_points(x, z, spacing, log_grid, logs):
				if Vector2(x - other[0], z - other[1]).length() < spacing:
					ok = false
					break
			if not ok:
				kind_name = "fern" if zone != Z_QUARRY else "grass"
				kind = Rules.UNDERSTORY.find(kind_name)
			else:
				insert(log_grid, logs, [x, z, 0.0])
		var spec: Array = Rules.UNDERSTORY_KIT[kind_name]
		var variant := 1 + rng.randi() % (spec[1] as Array).size()
		var scale := lerpf(0.8, 1.2, rng.randf())
		if kind_name == "rock":
			scale = lerpf(0.55, 0.95, rng.randf())
		elif kind_name == "quarry_rock":
			scale = lerpf(0.7, 1.25, rng.randf())
		elif kind_name == "trunk":
			scale = lerpf(0.8, 1.05, rng.randf())
		insert(under_grid, under, [snappedf(x, 0.01), snappedf(z, 0.01), r, kind, variant,
			snappedf(rng.randf() * 360.0, 0.1), snappedf(scale, 0.001)])
		kinds_count[kind_name] = kinds_count.get(kind_name, 0) + 1
	var understory: Array = []
	for item in under:
		understory.append([item[0], item[1], item[3], item[4], item[5], item[6]])
	print("LAYOUT understory=", understory.size(), " ", kinds_count)

	# 6. Inner understory near inner trees (runtime filters plots/roads/buildings again) --------
	var reserve_rects: Array = []
	for mask in atlas.reserve_masks:
		if String(mask.get("type", "")) == "box" and String(mask.get("id", "")) != "preserve_existing_core":
			reserve_rects.append(Rect2(float(mask.minX), float(mask.minZ), float(mask.maxX) - float(mask.minX), float(mask.maxZ) - float(mask.minZ)))
	for plot in data.legacyPlots:
		reserve_rects.append(Rect2(float(plot.x) - 6.7, float(plot.z) - 6.7, 13.4, 13.4))
	var inner_under: Array = []
	var inner_under_grid := {}
	for entry in placed_inner:
		var count := rng.randi() % 3
		for k in count:
			var angle := rng.randf() * TAU
			var distance := lerpf(1.7, 3.6, rng.randf())
			var x: float = entry[0] + cos(angle) * distance
			var z: float = entry[1] + sin(angle) * distance
			if maxf(absf(x), absf(z)) > CORE - 0.5:
				continue
			var blocked := false
			for rect: Rect2 in reserve_rects:
				if rect.grow(0.6).has_point(Vector2(x, z)):
					blocked = true
					break
			if blocked or _near_road(Vector2(x, z), 1.8) or terrain.ground_height(x, z) < -0.3 or terrain.slope_degrees(x, z) > 30.0:
				continue
			var ok := true
			for other in near_points(x, z, 3.0, placed_inner_grid, placed_inner):
				if Vector2(x - other[0], z - other[1]).length() < 1.2:
					ok = false
					break
			for other in near_points(x, z, 3.0, inner_under_grid, inner_under):
				if Vector2(x - other[0], z - other[1]).length() < 2.2:
					ok = false
					break
			if not ok:
				continue
			var kind := Rules.pick_index([0.45, 0.0, 0.25, 0.0, 0.0, 0.05, 0.0, 0.25, 0.0], rng.randf())
			var names: Array = Rules.UNDERSTORY_KIT[Rules.UNDERSTORY[kind]][1]
			insert(inner_under_grid, inner_under, [snappedf(x, 0.01), snappedf(z, 0.01), kind, 1 + rng.randi() % names.size(),
				snappedf(rng.randf() * 360.0, 0.1), snappedf(lerpf(0.75, 1.05, rng.randf()), 0.001)])
	print("LAYOUT inner understory=", inner_under.size())

	displacements.sort()
	var result := {
		"schemaVersion": 2, "layoutId": Rules.LAYOUT_ID, "layoutVersion": Rules.LAYOUT_VERSION,
		"previousLayoutId": Rules.PREVIOUS_LAYOUT_ID,
		"atlasId": atlas.atlas_id, "seed": Rules.SEED, "terrainVersion": ForestTerrain.TERRAIN_VERSION,
		"generator": "res://src/forest_rescue/world/tools/build_forest_layout.gd",
		"composition": "art/01 masterplan in city-camera screen space (see tool header)",
		"zones": ZONE_NAMES, "heroCaveOak": [hero.x, hero.y],
		"woodsCount": data.woods.size(), "outerResourceTrees": outer.size(), "innerResourceTrees": inner.size(),
		"species": Rules.SPECIES, "understoryKinds": Rules.UNDERSTORY,
		"remapReasonCodes": ["slot", "mask_push", "jitter", "kept_offset"],
		"remapStats": {"reasons": reasons, "displacementMedian": displacements[displacements.size() / 2],
			"displacementP95": displacements[int(displacements.size() * 0.95)], "displacementMax": displacements[-1],
			"maxSlotDisplacement": Rules.MAX_SLOT_DISPLACEMENT,
			"innerJitterMedian": inner_moved[inner_moved.size() / 2], "innerJitterMax": inner_moved[-1]},
		"format": {"trees": "[x, z, speciesIndex, kitVariant(1..4), yawDeg, absoluteScale, zoneIndex]",
			"resourceRemap": "{id: [x, z, reasonCode, kitVariant, absoluteScale]} for every outer resource tree",
			"innerRemap": "{id: [x, z, reasonCode(0 jittered / 3 kept), kitVariant, absoluteScale]} for every inner (±56) resource tree",
			"understory": "[x, z, kindIndex, variant(1-based in Rules.UNDERSTORY_KIT), yawDeg, absoluteScale]"},
		"trees": trees, "resourceRemap": remap, "innerRemap": inner_remap, "understory": understory, "innerUnderstory": inner_under}
	var file := FileAccess.open(Rules.LAYOUT_PATH, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "", false))
	file.close()
	print("LAYOUT_DONE trees=", trees.size(), " remap=", remap.size(), " inner=", inner_remap.size(), " understory=", understory.size(),
		" innerUnder=", inner_under.size(), " ms=", Time.get_ticks_msec() - started)
	quit()


## Best clump-biased spot within [min_d, max_d] of (tx, tz) (outside art glades).
func _best_spot(tx: float, tz: float, min_d: float, max_d: float, gap: float, tries: int, crown := 0.0) -> Vector2:
	var best := Vector2.INF
	var best_score := -INF
	for k in tries:
		var angle := rng.randf() * TAU
		var dist := lerpf(min_d, max_d, sqrt(rng.randf()))
		var x := tx + cos(angle) * dist
		var z := tz + sin(angle) * dist
		if blocked_exact(x, z, true, 1.0, crown) or not ground_ok(x, z, true) or not free_of_trunks(x, z, gap) or is_glade(x, z):
			continue
		var score := (clump.get_noise_2d(x, z) + 1.0) * 0.7 + rng.randf() * 0.45
		if score > best_score:
			best_score = score
			best = Vector2(x, z)
	return best


## Nearest valid spot (rings of 0.5 m) up to max_r.
func _nearest_free(tx: float, tz: float, max_r: float, gap: float, crown := 0.0, avoid_glades := false) -> Vector2:
	var radius := 0.5
	var angle0 := rng.randf() * TAU
	while radius <= max_r:
		var steps := maxi(12, int(radius * 6.0))
		for k in steps:
			var angle := angle0 + TAU * k / steps
			var x := tx + cos(angle) * radius
			var z := tz + sin(angle) * radius
			if blocked_exact(x, z, true, 1.0, crown) or not ground_ok(x, z, true) or not free_of_trunks(x, z, gap):
				continue
			if avoid_glades and is_glade(x, z):
				continue
			return Vector2(x, z)
		radius += 0.5
	return Vector2.INF


## Crown radius (m) the resource tree will have in this zone.
func _resource_crown(tree: Dictionary, species: int, zone: int) -> float:
	var look := _resource_look(tree, species, zone, false)
	return Rules.CROWN_RADIUS[species] * float(look[1])


func _resource_look(tree: Dictionary, species: int, zone: int, inner: bool) -> Array:
	var h := Rules.id_hash(String(tree.id))
	var u := clampf((float(tree.scale) - 0.45) / 0.85, 0.0, 1.0)
	var r: Array = RESOURCE_SCALE_INNER[0 if species == Rules.OAK else 1] if inner else RESOURCE_SCALE_OUTER[zone][0 if species == Rules.OAK else 1]
	var variants: Array = ZONE_VARIANTS[species][zone]
	var variant: int = variants[int(h * 997.0) % variants.size()]
	return [variant, snappedf(lerpf(r[0], r[1], u), 0.001)]


func _find_hero_spot() -> Vector2:
	var radius := 0.0
	while radius <= 22.0:
		for k in maxi(1, int(radius * 3.0)):
			var angle := TAU * k / maxf(1.0, radius * 3.0)
			var p: Vector2 = HERO_PREFERRED + Vector2(cos(angle), sin(angle)) * radius
			var ok: bool = ground_ok(p.x, p.y, true) and float(terrain.slope_degrees(p.x, p.y)) < 14.0
			var saved := hero
			hero = Vector2.INF
			ok = ok and not blocked_exact(p.x, p.y, true, 1.0)
			# keep the whole hero footprint off routes/glades
			for o in [Vector2(6, 0), Vector2(-6, 0), Vector2(0, 6), Vector2(0, -6)]:
				ok = ok and not blocked_exact(p.x + o.x, p.y + o.y, true, 1.0)
			hero = saved
			if ok:
				return p
		radius += 1.0
	return HERO_PREFERRED


func _rect_membership(p: Vector2, rects: Array) -> int:
	var code := 0
	for i in rects.size():
		if (rects[i] as Rect2).has_point(p):
			code = code * 31 + i + 1
	return code


func _near_road(p: Vector2, width: float) -> bool:
	for road in data.cityRoads:
		var a := Vector2(float(road[0][0]), float(road[0][1]))
		var b := Vector2(float(road[1][0]), float(road[1][1]))
		if ForestMasks.segment_distance(p, a, b) < width:
			return true
	return false


func _shuffle(array: Array) -> void:
	for i in range(array.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var tmp = array[i]
		array[i] = array[j]
		array[j] = tmp
