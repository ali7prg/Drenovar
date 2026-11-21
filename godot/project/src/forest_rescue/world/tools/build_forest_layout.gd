extends SceneTree
## Offline, deterministic builder of the natural forest layout v2 + resource-tree remap.
##   godot --headless --path godot/project -s res://src/forest_rescue/world/tools/build_forest_layout.gd
## Output: res://data/forest_rescue/world/forest_layout_v2.json (see forest_layout_rules.gd).
##
## Composition follows the art/01 masterplan (atlas v2, user zones) in the CITY CAMERA's screen
## space (the painting is drawn from that view: river vertical right of the town). Screen angle φ
## around the town (CCW from screen-right; screen-up = world (-X,-Z)), ForestAtlas.REGION_SECTORS:
## big golden oaks with sunny meadows top / top-left (hollow oak at its mark, birches round glade
## 01), golden + green oaks on the left, the limestone quarry lower-left (mine + glade 05), dark
## pines with mossy ground at the bottom, willows / green deciduous on the east bank, pines in the
## arena gorge top-right, reeds and willows round the river, the lake, the waterfall pond and the
## marsh pools, a meadow belt round the walls. Zones blend over ~10 m with a warped angle.
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
## Camera clearance (all steps): no crown may sit between the fixed city camera (38°, from +X+Z)
## and a unit on a trail, in a glade, in the arena or at the horse spot (Rules.crown_capsule vs
## the unit zones). Ambient trees that would are made young (low crown) or not planted; resource
## trees take another slot inside their displacement limit or the young look; the few left are
## listed in `cameraOccluders` and faded whole at runtime (forest_occluders.gd).

const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")
const ForestAtlas = preload("res://src/forest_rescue/world/forest_atlas.gd")
const ForestTerrain = preload("res://src/forest_rescue/world/forest_terrain.gd")
const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")
const ForestLandmarks = preload("res://src/forest_rescue/world/forest_landmarks.gd")
const ForestWater = preload("res://src/forest_rescue/world/forest_water.gd")

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
## Atlas v2 regions (ForestAtlas.REGION_SECTORS / REGION_NAMES, art/01 user zones): Z_TOP is the
## west mixed golden + green oaks, Z_EAST the green deciduous + willows of the east bank, Z_SPRUCE
## the dark south / south-east pines; belt, river (+ lake, pond, marsh) and quarry are spatial.
const ZONE_NAMES := ["golden_grove", "west_mixed", "arena_rock", "east_willows", "river_willows", "south_pines", "sw_quarry", "town_belt"]
## Ambient species mix per zone (resource trees keep their species).
const ZONE_MIX := [
	{Rules.OAK: 0.90, Rules.BIRCH: 0.06, Rules.PINE: 0.04},                 # golden grove (few big oaks, meadows)
	{Rules.OAK: 0.62, Rules.BIRCH: 0.20, Rules.PINE: 0.18},                 # west: golden + green oaks
	{Rules.PINE: 0.80, Rules.OAK: 0.12, Rules.BIRCH: 0.08},                 # arena rock: pines in the gorge
	{Rules.OAK: 0.46, Rules.WILLOW: 0.26, Rules.BIRCH: 0.16, Rules.PINE: 0.12},  # east: green deciduous + willows
	{Rules.WILLOW: 0.58, Rules.OAK: 0.18, Rules.BIRCH: 0.12, Rules.PINE: 0.12},  # river / lake willows
	{Rules.PINE: 0.93, Rules.BIRCH: 0.04, Rules.OAK: 0.03},                 # south pines (dark, dense)
	{Rules.BIRCH: 0.42, Rules.PINE: 0.43, Rules.OAK: 0.15},                 # quarry (sparse)
	{Rules.OAK: 0.50, Rules.BIRCH: 0.25, Rules.PINE: 0.25},                 # town belt (green broadleaf, meadows)
]
## Ambient spacing (m) per zone: target trunk spacing incl. resource trees.
const ZONE_SPACING := [15.0, 5.4, 3.9, 4.4, 4.8, 2.6, 9.0, 6.0]
## Grove hero oaks (owner: "big bright golden oaks 1.5–2×, fewer larger trees, clumps and
## open meadows"): every ambient grove oak at this absolute scale range (kit oak at 1.0 ≈ 13.6 m).
const GROVE_OAK_SCALE := [1.35, 1.8]
## Site 01 keeps birches around its glade (its text: white trunks): ambient trees within this
## distance of its centre are birches.
const BIRCH_RING := 17.0
## Absolute scale ranges per [zone][species] for AMBIENT trees (inside kit recommendedScale).
const AMBIENT_SCALE := {
	Rules.OAK: [[0.94, 1.10], [0.70, 0.88], [0.66, 0.80], [0.66, 0.82], [0.66, 0.80], [0.66, 0.78], [0.66, 0.78], [0.66, 0.82]],
	Rules.PINE: [[0.78, 0.98], [0.80, 1.00], [0.90, 1.16], [0.84, 1.06], [0.80, 1.00], [0.92, 1.20], [0.80, 1.00], [0.78, 0.96]],
	Rules.BIRCH: [[0.80, 0.95], [0.86, 1.08], [0.80, 0.96], [0.86, 1.10], [0.84, 1.04], [0.80, 0.95], [0.84, 1.00], [0.82, 1.00]],
	Rules.WILLOW: [[0.82, 0.98], [0.82, 1.0], [0.82, 1.0], [0.86, 1.06], [0.88, 1.12], [0.82, 1.0], [0.82, 1.0], [0.84, 1.0]],
}
## Resource-tree absolute scale ranges per zone [oak, pine] (zone decides which one dominates).
const RESOURCE_SCALE_OUTER := [
	[[0.34, 0.46], [0.44, 0.56]],   # grove: young oaks/pines between sparse old oaks
	[[0.38, 0.50], [0.62, 0.80]],
	[[0.34, 0.42], [0.92, 1.12]],   # arena pines
	[[0.36, 0.46], [0.82, 1.02]],
	[[0.36, 0.46], [0.76, 0.94]],
	[[0.32, 0.40], [0.96, 1.20]],   # spruce: young oaks under tall spruces
	[[0.36, 0.46], [0.70, 0.86]],
	[[0.42, 0.54], [0.70, 0.86]],
]
## Inner base (±56): the town stays readable (legacy-like 8–10 m crowns).
const RESOURCE_SCALE_INNER := [[0.46, 0.58], [0.60, 0.74]]
## Kit variant palettes per zone & species (art/01: v2+; v1 = art/02 hero accents).
const ZONE_VARIANTS := {
	Rules.OAK: [[2, 3, 4, 1], [2, 3, 4, 1], [2, 3], [2, 3, 4], [2, 3, 4], [2, 3], [2, 3, 4], [2, 3, 4]],
	Rules.PINE: [[1, 1, 2], [2, 3, 4], [2, 3, 4], [2, 3, 4], [2, 3], [2, 3, 4], [1, 2, 3], [2, 3, 4]],
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
## (atlas v2: the hollow oak stands just beyond the end of the spur lf_trail_site_01__mark_hollow_oak_giant)
const HERO_MARK := "lf_mark_hollow_oak_giant"
const HERO_BACK := 5.4
var hero_preferred := Vector2(-104.0, 24.0)
const HERO_CLEAR := 9.5
const QUARRY_PIT := 12.0          # art/01: open pale pit in front of the mine (no trunks)
const ARENA_RIM_TREE := 26.0      # no kit trunk inside the arena GLB's own rim forest
const ARENA_RIM_UNDER := 22.5     # no kit understory inside its cliff ring / rim shrubs
const ARENA_VIEW_RADIUS := 19.5   # camera clearance: arena floor + cliff ring + entrance rocks
var quarry_axis := 0.0            # direction (rad) from the pit centre to the cliff arc
var water: Array = []             # ForestWater.bodies(atlas): lake, waterfall pond, marsh pools
var glade_clearings: Array = []   # [[Vector2, radius]] visual glade clearings (pass 2)
const GLADE_CLEARING := 11.5

## Layout pass 3 (art/01: big individual crowns standing in groves on sunny meadows). Canopy cover
## of the zone's forest land (crown discs, art/01 crops at zoom 68), trunk spacing inside a grove,
## and the sunny strip kept open on the camera side of every trail (art/01 trails run along the
## grove edges, the walkers in front of the crowns).
const GROVES := true
const ZONE_COVER := [0.46, 0.58, 0.62, 0.62, 0.46, 0.80, 0.30, 0.46]
const ZONE_SLOT := [9.0, 7.6, 4.6, 7.2, 7.0, 3.6, 7.2, 7.6]   # canopy trunks: big crowns, a little overlap
const SUB_SLOT := 2.6                                            # young trees between the canopy trunks
const SUB_SCALE := [[0.42, 0.58], [0.5, 0.7]]                    # [oak, pine] young look inside a grove
const GROVE_BAND_NEAR := 7.0
const GROVE_BAND_FAR := 3.0
const GROVE_STEP := 2.0
const GROVE_CELL := 8.0
## pass 3 absolute scales [zone] -> [oak range, pine range] (crowns: oak 14 m, pine 6 m at 1.0;
## art/01 oak crowns 10–17 m, pines 5–7 m)
const GROVE_SCALE := [
	[[0.95, 1.25], [0.8, 1.0]],    # golden grove: big golden oaks
	[[0.8, 1.1], [0.9, 1.1]],      # west mixed
	[[0.7, 0.9], [0.95, 1.2]],     # arena rock: pines
	[[0.8, 1.05], [0.9, 1.1]],     # east bank
	[[0.8, 1.0], [0.9, 1.1]],      # river / lake
	[[0.5, 0.7], [0.95, 1.2]],     # south pines (oaks are accents under the pines)
	[[0.7, 0.9], [0.85, 1.05]],    # quarry
	[[0.7, 0.95], [0.85, 1.05]],   # town belt
]
var grove_noise := FastNoiseLite.new()
var grove_slots: Array = []        # [Vector2, zone, taken]
var grove_grid := {}               # Vector2i -> PackedInt32Array
var grove_stats := {}

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
## Unit zones for the camera clearance: [a: Vector2, b: Vector2, half width] (discs: a == b).
var unit_zones: Array = []
var unit_zone_grid := {}
const UNIT_ZONE_CELL := 8.0
const TRAIL_UNIT_HALF := 1.6         # squad column / escort file half width on a trail
const HORSE_ZONE := 4.0
const HOME_ZONE := 3.0
var camera_occluders: Array = []     # resource ids still hiding a unit zone (runtime fade)


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


var _zone_cache := {}
var _open_cache := {}


## Memoised on a 1 m lattice (the builder queries these hundreds of thousands of times).
func zone_weights(x: float, z: float) -> PackedFloat32Array:
	var key := Vector2i(floori(x), floori(z))
	if _zone_cache.has(key):
		return _zone_cache[key]
	var w := _zone_weights_raw(floori(x) + 0.5, floori(z) + 0.5)
	_zone_cache[key] = w
	return w


func _zone_weights_raw(x: float, z: float) -> PackedFloat32Array:
	var w: PackedFloat32Array = atlas.region_sector_weights(x, z, warp.get_noise_2d(x, z) * 16.0, 11.0)
	# Quarry: around the SW quarry centre (mine / glade 05), ragged edge.
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
	for body in water:
		river = maxf(river, (1.0 - smoothstep(2.0, 11.0, ForestTerrain.shore_distance(body, x, z))) * (1.0 if body.kind != "marsh" else 0.35))
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
# Camera clearance (unit zones vs crowns seen from the fixed city camera)

func _build_unit_zones() -> void:
	unit_zones.clear()
	unit_zone_grid.clear()
	for route in atlas.routes:
		if route.get("decor", false):
			continue                   # decorative trails: nobody walks there
		var points: PackedVector3Array = route.points
		for i in range(points.size() - 1):
			_add_unit_zone(Vector2(points[i].x, points[i].z), Vector2(points[i + 1].x, points[i + 1].z), TRAIL_UNIT_HALF, true)
	for site in atlas.sites:
		var c := Vector2(site.center.x, site.center.z)
		_add_unit_zone(c, c, float(site.radius))
	# the arena floor AND its cliff ring / entrance rocks (≤ 19.5 m) stay visible from the camera
	var arena := Vector2(atlas.arena_center.x, atlas.arena_center.z)
	for extra in atlas.extra_glades:
		var e := Vector2(extra.center.x, extra.center.z)
		_add_unit_zone(e, e, float(extra.radius))
	# signature features stay visible for the city camera like the units (art/01): the waterfall and
	# its pond, the marsh pools, the landmark spots (crowns in front of them are planted young/away)
	_add_unit_zone(ForestWater.POND_CENTER, ForestWater.POND_CENTER, ForestWater.POND_RADIUS + 0.8)
	_add_unit_zone(ForestWater.FALLS_LIP, ForestWater.FALLS_LIP, 2.0)
	for body in water:
		if body.kind == "marsh":
			_add_unit_zone(body.center, body.center, float(body.radius))
	for disc in landmark_discs:
		_add_unit_zone(disc[0], disc[0], minf(3.5, float(disc[1]) * 0.6))
	_add_unit_zone(arena, arena, ARENA_VIEW_RADIUS)
	var deck_rect: Rect2 = atlas.bridge_deck_rect()
	for end_x in [deck_rect.position.x, deck_rect.end.x]:
		var tower := Vector2(end_x, atlas.BRIDGE_CENTER.z)
		_add_unit_zone(tower, tower, 4.5)
	var horse := Vector2(atlas.horse_origin.x, atlas.horse_origin.z)
	_add_unit_zone(horse, horse, HORSE_ZONE)
	_add_unit_zone(ForestAtlas.HOME_RECEPTION, ForestAtlas.HOME_RECEPTION, HOME_ZONE)


func _add_unit_zone(a: Vector2, b: Vector2, half: float, trail := false) -> void:
	var index := unit_zones.size()
	unit_zones.append([a, b, half, trail])
	var lo := a.min(b) - Vector2.ONE * half
	var hi := a.max(b) + Vector2.ONE * half
	for gz in range(floori(lo.y / UNIT_ZONE_CELL), floori(hi.y / UNIT_ZONE_CELL) + 1):
		for gx in range(floori(lo.x / UNIT_ZONE_CELL), floori(hi.x / UNIT_ZONE_CELL) + 1):
			var key := Vector2i(gx, gz)
			if not unit_zone_grid.has(key):
				unit_zone_grid[key] = PackedInt32Array()
			unit_zone_grid[key].append(index)


## True when a crown capsule (Rules.crown_capsule) covers any unit zone.
func capsule_hits_units(capsule: Array, strict_only := false) -> bool:
	var a: Vector2 = capsule[0]
	var b: Vector2 = capsule[1]
	var r: float = capsule[2] + Rules.UNIT_RADIUS + 0.1     # + snapping margin (layout stores 0.01 m / 0.001)
	var lo := a.min(b) - Vector2.ONE * r
	var hi := a.max(b) + Vector2.ONE * r
	var seen := {}
	for gz in range(floori(lo.y / UNIT_ZONE_CELL), floori(hi.y / UNIT_ZONE_CELL) + 1):
		for gx in range(floori(lo.x / UNIT_ZONE_CELL), floori(hi.x / UNIT_ZONE_CELL) + 1):
			for index in unit_zone_grid.get(Vector2i(gx, gz), PackedInt32Array()):
				if seen.has(index):
					continue
				seen[index] = true
				var zone: Array = unit_zones[index]
				if strict_only and bool(zone[3]):
					continue
				if Rules.segment_segment_distance(a, b, zone[0], zone[1]) < r + float(zone[2]):
					return true
	return false


func tree_hides_units(x: float, z: float, species: int, variant: int, scale: float, yaw: float, strict_only := false) -> bool:
	return capsule_hits_units(Rules.crown_capsule(x, z, species, variant, scale, yaw), strict_only)


## Pass 2 (art/01 south): the dark pine forest stays dense — a pine there may stand in front of a
## trail (the walkers behind it are faded whole at runtime by ForestOccluders), never in front of a
## glade, the arena, the horse spot, a landmark, the water features or the bridge towers.
func dense_pine_ok(zone: int, species: int) -> bool:
	return zone == Z_SPRUCE and species == Rules.PINE


# ---------------------------------------------------------------------------------------------
# Clearances

## crown: crown radius (m) of the tree that would stand here; up to ~45 % of it may overhang a
## path or glade (art/01: trails stay readable between the crowns).
## dense: a south pine (pass 2, art/01 dark dense pine forest) — trunks stand FAR_SIDE_TRUNK_CLEAR
## off a trail centre on both sides and the crowns may overhang it (narrow trails between pines).
func blocked_exact(x: float, z: float, tree: bool, margin_scale := 1.0, crown := 0.0, dense := false) -> bool:
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
						if tree:
							var a := Vector2(float(mask.a.x), float(mask.a.z))
							var b := Vector2(float(mask.b.x), float(mask.b.z))
							var ab := b - a
							var t := clampf((Vector2(x, z) - a).dot(ab) / maxf(ab.length_squared(), 0.0001), 0.0, 1.0)
							if dense or Rules.far_side(Vector2(x, z) - (a + ab * t)):
								margin = Rules.FAR_SIDE_TRUNK_CLEAR - float(mask.radius)
					"glade":
						margin = (Rules.GLADE_TRUNK_MARGIN + crown * 0.4) * margin_scale if tree else 0.3
					"arena":
						margin = (2.0 + crown * 0.4) * margin_scale if tree else 0.5
					"bridge":
						margin = 0.8
					"reserve":
						if tree:
							continue
					"core":
						continue
				if ForestMasks.inside_mask(x, z, mask, margin):
					return true
	# Boss arena (art/08): the arena GLB carries its own cliff ring (rocks 15–19 m), rim shrubs
	# (~20 m) and rim pines (22–25 m); kit trees and rocks never intersect them or the entrance.
	var arena_d := Vector2(x, z).distance_to(Vector2(atlas.arena_center.x, atlas.arena_center.z))
	if arena_d < (ARENA_RIM_TREE + crown * 0.35 if tree else ARENA_RIM_UNDER):
		return true
	for disc in landmark_discs:
		if Vector2(x, z).distance_to(disc[0]) < float(disc[1]) * (1.0 if tree else 0.75):
			return true
	for disc in glade_clearings:
		if Vector2(x, z).distance_to(disc[0]) < (float(disc[1]) + crown * 0.3 if tree else float(disc[1]) * 0.66):
			return true
	if hero != Vector2.INF and Vector2(x, z).distance_to(hero) < (HERO_CLEAR if tree else 5.5):
		return true
	if tree and quarry_center != Vector2.INF:
		var dq := Vector2(x, z).distance_to(quarry_center)
		if dq < QUARRY_PIT + crown * 0.4:
			return true
		# the cliff/ledge arc behind the mine stays free of trunks (art/01: bare grey cliffs)
		if dq < 24.0 + crown * 0.3:
			var a := atan2(z - quarry_center.y, x - quarry_center.x)
			if absf(angle_difference(a, quarry_axis)) < deg_to_rad(110.0):
				return true
	return false


func ground_ok(x: float, z: float, tree: bool) -> bool:
	var h: float = terrain.ground_height(x, z)
	if h < -0.35:
		return false
	if atlas.river_bank_distance(x, z) < (1.2 if tree else 0.4):
		return false
	for body in water:
		if ForestTerrain.shore_distance(body, x, z) < (1.6 if tree else 0.5):
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
	var threshold := 0.3 if zone == Z_GROVE else (0.2 if zone == Z_BELT else (0.15 if zone in [Z_TOP, Z_EAST, Z_QUARRY] else (0.02 if zone == Z_SPRUCE else 0.07)))
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
	terrain.quarry_center = landmarks.quarry_center()
	water = ForestWater.bodies(atlas)
	terrain.water_bodies = water
	terrain.bake()
	for disc in landmarks.clearances():
		landmark_discs.append(disc)
	for placement in landmarks.placements:
		if placement.id == "lf_env_quarry_mine":
			var mine_p := Vector2(placement.position.x, placement.position.z)
			var glade_p := Vector2(atlas.site_by_id.lf_site_05.center.x, atlas.site_by_id.lf_site_05.center.z)
			quarry_center = mine_p.lerp(glade_p, 0.45)
			var axis := ((mine_p - glade_p).normalized() * 0.6 + Vector2(-0.7071, -0.7071) * 0.4).normalized()
			quarry_axis = atan2(axis.y, axis.x)
	var hero_mark: Vector2 = landmarks._node_xz(HERO_MARK)
	if hero_mark != Vector2.INF:
		hero_preferred = hero_mark + landmarks._away_from_trails(HERO_MARK, hero_mark) * HERO_BACK
	if landmarks.dead_tree_spot != Vector2.INF:
		landmark_discs.append([landmarks.dead_tree_spot, 3.2])
	# waterfall outcrop + pond (ForestWater): no trunks on the rocks, round the pond or between the
	# pond and the camera (resource trees are pushed out ≤ 6.5 m like from any clearance)
	landmark_discs.append([Vector2(19.8, -67.3), 5.2])
	landmark_discs.append([ForestWater.POND_CENTER, ForestWater.POND_RADIUS + 3.5])
	landmark_discs.append([ForestWater.POND_CENTER + Vector2(3.5, 3.5), 4.5])
	# art/01 (pass 2): every glade sits in an open sunny clearing of ~11.5 m radius (camp, fire,
	# cage, props) — no trunk inside and crowns overhang it only a little (the gameplay pad stays 7 m)
	for site in atlas.sites:
		glade_clearings.append([Vector2(site.center.x, site.center.z), GLADE_CLEARING])
	for extra in atlas.extra_glades:
		glade_clearings.append([Vector2(extra.center.x, extra.center.z), GLADE_CLEARING])
	# (f) the bridge ends: towers and red banners read (no trunk within 9 m of either deck end)
	var deck: Rect2 = atlas.bridge_deck_rect()
	for end_x in [deck.position.x, deck.end.x]:
		landmark_discs.append([Vector2(end_x, atlas.BRIDGE_CENTER.z), 9.0])
	landmarks.free()
	_build_unit_zones()
	print("LAYOUT terrain+masks ready ms=", Time.get_ticks_msec() - started, " quarry=", quarry_center, " unit zones=", unit_zones.size())

	# 1. Hero cave oak ------------------------------------------------------------------------
	hero = _find_hero_spot()
	print("LAYOUT hero cave oak at ", hero)

	if GROVES:
		var counts := PackedInt32Array()
		counts.resize(8)
		for tree in data.woods:
			var tp: Array = tree.p
			if maxf(absf(float(tp[0])), absf(float(tp[2]))) > CORE:
				counts[dominant_zone(float(tp[0]), float(tp[2]))] += 1
		_plan_groves(counts)

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
		if GROVES:
			# pass 3: the tree moves to the nearest free grove slot of its own zone (same id / species)
			var home_zone := dominant_zone(tx, tz)
			var slot := _take_grove_slot(tree, species, home_zone, tx, tz)
			if slot != Vector2.INF:
				insert(trunk_grid, trunks, [slot.x, slot.y, gap])
				var glook := _grove_look(tree, species, slot.x, slot.y, home_zone, _last_sub)
				if tree_hides_units(slot.x, slot.y, species, int(glook[0]) % Rules.GREEN_VARIANT_BASE, float(glook[1]), float(tree.angle)):
					camera_occluders.append(String(tree.id))          # walkers behind it: runtime whole-tree fade
				remap[tree.id] = [snappedf(slot.x, 0.01), snappedf(slot.y, 0.01), 0, glook[0], glook[1]]
				reasons["slot"] += 1
				displacements.append(Vector2(tx - slot.x, tz - slot.y).length())
				continue
		var crown := _resource_crown(tree, species, tx, tz)
		var in_mask := blocked_exact(tx, tz, true, 1.0, crown) or not ground_ok(tx, tz, true) or is_glade(tx, tz)
		var found := Vector2.INF
		var reason := 0
		# Camera clearance first (a slot whose crown — natural or young look — hides no unit zone),
		# then the plain v2 rules (the tree is then faded whole at runtime when it hides an actor).
		_cam_tree = tree
		_cam_species = species
		if not in_mask:
			found = _best_spot(tx, tz, 1.0, Rules.MAX_SLOT_DISPLACEMENT, gap, 60, crown)
		if found == Vector2.INF:
			found = _nearest_free(tx, tz, 6.5, gap, crown, true)
			if found != Vector2.INF and Vector2(tx, tz).distance_to(found) > Rules.MAX_SLOT_DISPLACEMENT:
				reason = 1 if in_mask else 2
		_cam_tree = {}
		if found == Vector2.INF and not in_mask:
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
			found = _nearest_free(tx, tz, 30.0, 1.2)
		if found == Vector2.INF:
			# last resort: nearest spot outside every clearance mask, ignoring slope/trunk gaps
			var radius := 0.5
			while radius <= 30.0 and found == Vector2.INF:
				for k in 24:
					var angle := TAU * k / 24.0
					var q := Vector2(tx + cos(angle) * radius, tz + sin(angle) * radius)
					if not blocked_exact(q.x, q.y, true) and atlas.river_bank_distance(q.x, q.y) > 0.5:
						found = q
						break
				radius += 0.5
		if found == Vector2.INF:
			found = Vector2(tx, tz)
		insert(trunk_grid, trunks, [found.x, found.y, gap])
		var look := _camera_look(tree, species, found.x, found.y, false)
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
	var horse := Vector2(atlas.horse_origin.x, atlas.horse_origin.z)
	var entry_route := PackedVector3Array()
	for route in atlas.routes:
		if route.from == "lf_horse_origin" or route.to == "lf_horse_origin":
			entry_route.append_array(route.points)
	for t in inner_order:
		var tree: Dictionary = inner[t]
		var o := Vector2(float(tree.p[0]), float(tree.p[2]))
		var membership := _rect_membership(o, plot_rects)
		var species: int = Rules.RESOURCE_SPECIES.get(String(tree.name), Rules.PINE)
		var best := o
		var best_score := -INF
		# The hall-III entrance (art/18): the horse spot and the entry trail stay trunk-free.
		var on_entrance := o.distance_to(horse) < HORSE_CLEAR or _entry_distance(o, entry_route) < ENTRY_CLEAR
		var reach := Rules.MAX_INNER_JITTER if on_entrance else 3.5
		# inner trees whose crown could hide the mare / squad at the entrance prefer clear slots
		var near_units := o.distance_to(horse) < 40.0
		for k in (60 if on_entrance else 28):
			var angle := rng.randf() * TAU
			var dist := lerpf(1.0, reach, sqrt(rng.randf()))
			var q := o + Vector2(cos(angle), sin(angle)) * dist
			if maxf(absf(q.x), absf(q.y)) > CORE - 0.4 or _rect_membership(q, plot_rects) != membership:
				continue
			if _near_road(q, 1.8) or terrain.ground_height(q.x, q.y) < -0.3:
				continue
			if q.distance_to(horse) < HORSE_CLEAR or _entry_distance(q, entry_route) < ENTRY_CLEAR:
				continue
			var ok := true
			for other in near_points(q.x, q.y, 3.0, placed_inner_grid, placed_inner):
				if q.distance_to(Vector2(other[0], other[1])) < 2.2:
					ok = false
					break
			if not ok:
				continue
			var score := (clump.get_noise_2d(q.x, q.y) + 1.0) * 0.6 + rng.randf() * 0.5
			if near_units:
				score += 2.0 * _cam_state_for(tree, species, q.x, q.y, true)
			if score > best_score:
				best_score = score
				best = q
		insert(placed_inner_grid, placed_inner, [best.x, best.y, 0.0])
		var look := _camera_look(tree, species, best.x, best.y, true)
		inner_remap[tree.id] = [snappedf(best.x, 0.01), snappedf(best.y, 0.01), 0 if best != o else 3, look[0], look[1]]
		inner_moved.append(best.distance_to(o))
	inner_moved.sort()
	print("LAYOUT inner jitter median=", inner_moved[inner_moved.size() / 2], " max=", inner_moved[-1])

	# 4. Ambient trees --------------------------------------------------------------------------
	var trees: Array = []
	var species_count := {}
	if hero != Vector2.INF:
		# yaw 45°: the walk-through hollow (model +Z) faces the city camera (+X+Z), as in art/01.
		trees.append([snappedf(hero.x, 0.01), snappedf(hero.y, 0.01), Rules.HOLLOW_OAK, 2, 45.0, Rules.HERO_SCALE, Z_GROVE])
		species_count[Rules.SPECIES[Rules.HOLLOW_OAK]] = 1
	var cells: Array = []
	var span := int(EXTENT * 2.0)
	for j in span:
		for i in span:
			cells.append(Vector2i(i, j))
	_shuffle(cells)
	if GROVES:
		_fill_groves(trees, species_count)
	for pass_index in 2:
		for cell: Vector2i in cells:
			var x := -EXTENT + cell.x + rng.randf()
			var z := -EXTENT + cell.y + rng.randf()
			if maxf(absf(x), absf(z)) < CORE + 0.8:
				continue
			var dense_spot := dominant_zone(x, z) == Z_SPRUCE
			if GROVES and not dense_spot:
				continue          # pass 3: groves everywhere else; the south stays the dense dark pine forest
			if blocked_exact(x, z, true, 1.0, 0.0, dense_spot) or not ground_ok(x, z, true) or is_glade(x, z):
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
			if dense_spot and species != Rules.PINE:
				# only the pines of the dense south forest may crowd a trail
				if blocked_exact(x, z, true):
					continue
			var dense_pine := dense_spot and zone == Z_SPRUCE and species == Rules.PINE
			var site01: Dictionary = atlas.site_by_id.get("lf_site_01", {})
			if not site01.is_empty() and Vector2(x, z).distance_to(Vector2(site01.center.x, site01.center.z)) < BIRCH_RING:
				species = Rules.BIRCH if rng.randf() < 0.85 else species
				spacing = minf(spacing, 5.0)
			var gap := spacing if species != Rules.PINE else spacing * 0.86
			if not free_of_trunks(x, z, gap):
				continue
			var scale_range: Array = GROVE_OAK_SCALE if (zone == Z_GROVE and species == Rules.OAK) else AMBIENT_SCALE[species][zone]
			var scale := lerpf(scale_range[0], scale_range[1], rng.randf())
			scale = lerpf(scale, lerpf(0.34, 0.52, rng.randf()), openness(x, z) * (0.0 if zone == Z_GROVE and species == Rules.OAK else 0.85))
			if blocked_exact(x, z, true, 1.0, Rules.CROWN_RADIUS[species] * scale, dense_pine):
				continue
			var variants: Array = ZONE_VARIANTS[species][zone]
			var variant: int = variants[rng.randi() % variants.size()]
			var drawn := species
			if species == Rules.OAK and zone != Z_GROVE and not oak_is_golden(x, z, rng.randf()):
				drawn = Rules.OAK_GREEN
				variant = clampi(variant, 2, 4)
			var yaw_deg := snappedf(rng.randf() * 360.0, 0.1)
			# Camera clearance: a crown that would hide a unit on a trail / in a glade is made
			# young (low crown, units seen past it) or the spot stays open (understory only).
			if tree_hides_units(x, z, drawn, variant, scale, deg_to_rad(yaw_deg)):
				if dense_pine and not tree_hides_units(x, z, drawn, variant, scale, deg_to_rad(yaw_deg), true):
					pass                     # dense south pines: trail walkers are faded through at runtime
				else:
					var young := lerpf(0.34, 0.46, rng.randf())
					if young >= scale or tree_hides_units(x, z, drawn, variant, young, deg_to_rad(yaw_deg)):
						continue
					scale = young
			insert(trunk_grid, trunks, [x, z, minf(gap, 3.0 if species != Rules.OAK or zone != Z_GROVE else 6.0)])
			trees.append([snappedf(x, 0.01), snappedf(z, 0.01), drawn, variant,
				yaw_deg, snappedf(scale, 0.001), zone])
			species_count[Rules.SPECIES[drawn]] = species_count.get(Rules.SPECIES[drawn], 0) + 1
	print("LAYOUT ambient trees=", trees.size(), " ", species_count)

	# 5. Understory -----------------------------------------------------------------------------
	var under: Array = []
	var under_grid := {}
	var logs: Array = []
	var log_grid := {}
	var kinds_count := {}
	_bank_dressing(trees, under, under_grid, logs, log_grid, kinds_count, species_count)
	_water_dressing(trees, under, under_grid, logs, log_grid, kinds_count, species_count)
	_quarry_cliffs(under, under_grid, logs, log_grid, kinds_count)
	_shuffle(cells)
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
			scale = lerpf(0.3, 0.52, rng.randf())       # moss rock v1 is 9 × 6 m at 1.0
		elif kind_name == "quarry_rock":
			scale = lerpf(0.7, 1.25, rng.randf())
		elif kind_name == "trunk":
			scale = lerpf(0.8, 1.05, rng.randf())
		insert(under_grid, under, [snappedf(x, 0.01), snappedf(z, 0.01), r, kind, variant,
			snappedf(rng.randf() * 360.0, 0.1), snappedf(scale, 0.001)])
		kinds_count[kind_name] = kinds_count.get(kind_name, 0) + 1
	var understory: Array = []
	for item in under:
		var row := [item[0], item[1], item[3], item[4], item[5], item[6]]
		if item.size() > 7 and float(item[7]) != 0.0:
			row.append(item[7])          # height offset (stacked quarry ledges)
		understory.append(row)
	print("LAYOUT understory=", understory.size(), " ", kinds_count)

	# 5b. Trail edges (art/07): small stones, roots (fallen branches), grass tufts and ferns on
	#     both sides of every trail, just outside its walking width; low, never in front of units.
	var dressing := _trail_dressing()
	print("LAYOUT trail dressing=", dressing.size())

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
			"understory": "[x, z, kindIndex, variant(1-based in Rules.UNDERSTORY_KIT), yawDeg, absoluteScale, (heightOffset)]",
			"trailDressing": "same as understory; stones/roots/grass/ferns at the trail edges (≥ walking width)"},
		"cameraClearance": {"unitHeight": Rules.UNIT_HEIGHT, "trailHalf": TRAIL_UNIT_HALF, "viewShift": Rules.VIEW_SHIFT,
			"rule": "no crown between the city camera and a unit on a trail / in a glade / arena / horse spot (Rules.crown_capsule)"},
		"cameraOccluders": camera_occluders,
		"trailDressing": dressing,
		"trees": trees, "resourceRemap": remap, "innerRemap": inner_remap, "understory": understory, "innerUnderstory": inner_under}
	var file := FileAccess.open(Rules.LAYOUT_PATH, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "", false))
	file.close()
	print("LAYOUT camera occluders (resource ids, runtime fade)=", camera_occluders.size())
	for arg in OS.get_cmdline_user_args():
		if String(arg).begins_with("--probe="):
			var v := String(arg).trim_prefix("--probe=").split_floats(",")
			_probe_region(v[0], v[1], v[2])
	print("LAYOUT_DONE trees=", trees.size(), " remap=", remap.size(), " inner=", inner_remap.size(), " understory=", understory.size(),
		" innerUnder=", inner_under.size(), " ms=", Time.get_ticks_msec() - started)
	quit()


# ---------------------------------------------------------------------------------------------
# Pass 3 groves

func _grove_value(x: float, z: float) -> float:
	return (grove_noise.get_noise_2d(x, z) + 1.0) * 0.5


## Camera-side strip of a trail (sunny meadow in front of the walkers) and a narrow far-side strip.
func _in_trail_band(x: float, z: float, zone: int) -> bool:
	if zone == Z_SPRUCE:
		return false          # the dense south pines crowd the trails (pass 2 rule)
	var reach := GROVE_BAND_NEAR + 4.0
	for gz in range(floori((z - reach) / masks.cell), floori((z + reach) / masks.cell) + 1):
		for gx in range(floori((x - reach) / masks.cell), floori((x + reach) / masks.cell) + 1):
			for index in masks.grid.get(Vector2i(gx, gz), PackedInt32Array()):
				var mask: Dictionary = masks.masks[index]
				if String(mask.get("kind", "")) != "route":
					continue
				var a := Vector2(float(mask.a.x), float(mask.a.z))
				var b := Vector2(float(mask.b.x), float(mask.b.z))
				var ab := b - a
				var t := clampf((Vector2(x, z) - a).dot(ab) / maxf(ab.length_squared(), 0.0001), 0.0, 1.0)
				var off := Vector2(x, z) - (a + ab * t)
				var limit := GROVE_BAND_FAR if Rules.far_side(off) else GROVE_BAND_NEAR
				if off.length() < limit:
					return true
	return false


func _plan_groves(resource_counts: PackedInt32Array) -> void:
	var t0 := Time.get_ticks_msec()
	grove_noise.seed = Rules.SEED + 51
	grove_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	grove_noise.frequency = 1.0 / 26.0
	grove_noise.fractal_octaves = 2
	var land := PackedInt32Array()
	land.resize(8)
	var values: Array = []
	for i in 8:
		values.append(PackedFloat32Array())
	var cand: Array = []
	var x := -EXTENT + 1.0
	while x < EXTENT:
		var z := -EXTENT + 1.0
		while z < EXTENT:
			if maxf(absf(x), absf(z)) >= CORE + 1.0 and not blocked_exact(x, z, true) and ground_ok(x, z, true):
				var zone := dominant_zone(x, z)
				land[zone] += 1
				if not _in_trail_band(x, z, zone):
					var v := _grove_value(x, z)
					cand.append([x, z, zone, v])
					values[zone].append(v)
			z += GROVE_STEP
		x += GROVE_STEP
	# trunk area share per zone so that crowns (trunk area grown by ~0.6 crown radius) give ZONE_COVER
	var cut := PackedFloat32Array()
	cut.resize(8)
	for zone in 8:
		var vals: PackedFloat32Array = values[zone]
		if vals.is_empty():
			cut[zone] = 2.0
			continue
		vals.sort()
		# grove (trunk) area: the art/01 canopy share of the zone's land (crowns reach past the outer trunks)
		var want := clampf(ZONE_COVER[zone] * 0.78 * float(land[zone]) / float(vals.size()), 0.0, 0.97)
		cut[zone] = vals[clampi(int((1.0 - want) * vals.size()), 0, vals.size() - 1)]
	_shuffle(cand)
	var grid := {}
	for c in cand:
		var zone: int = c[2]
		if float(c[3]) < cut[zone]:
			continue
		var p := Vector2(float(c[0]) + rng.randf_range(-0.9, 0.9), float(c[1]) + rng.randf_range(-0.9, 0.9))
		var sp: float = ZONE_SLOT[zone] * rng.randf_range(0.85, 1.1)
		var key := Vector2i(floori(p.x / GROVE_CELL), floori(p.y / GROVE_CELL))
		var ok := true
		for gz in range(key.y - 1, key.y + 2):
			for gx in range(key.x - 1, key.x + 2):
				for idx in grid.get(Vector2i(gx, gz), PackedInt32Array()):
					var o: Vector2 = grove_slots[idx][0]
					if o.distance_squared_to(p) < sp * sp:
						ok = false
						break
				if not ok:
					break
			if not ok:
				break
		if not ok:
			continue
		if hero != Vector2.INF and p.distance_to(hero) < HERO_CLEAR + 2.0:
			continue
		if not grid.has(key):
			grid[key] = PackedInt32Array()
		grid[key].append(grove_slots.size())
		grove_slots.append([p, zone, false, 0])
	# young-tree slots tucked behind / under each canopy crown (camera-far side, inside the crown):
	# from the city camera the big crown covers them, so the grove reads as big individual crowns
	var canopy_count := grove_slots.size()
	for ci in canopy_count:
		var cp: Vector2 = grove_slots[ci][0]
		var zone: int = grove_slots[ci][1]
		var reach: float = ZONE_SLOT[zone] * 0.55
		for k in 3:
			var ang := deg_to_rad(225.0 + rng.randf_range(-70.0, 70.0))
			var p := cp + Vector2(cos(ang), sin(ang)) * rng.randf_range(SUB_SLOT, maxf(SUB_SLOT + 0.4, reach))
			if maxf(absf(p.x), absf(p.y)) < CORE + 1.0 or blocked_exact(p.x, p.y, true) or not ground_ok(p.x, p.y, true):
				continue
			var key := Vector2i(floori(p.x / GROVE_CELL), floori(p.y / GROVE_CELL))
			var ok := true
			for gz in range(key.y - 1, key.y + 2):
				for gx in range(key.x - 1, key.x + 2):
					for idx in grid.get(Vector2i(gx, gz), PackedInt32Array()):
						var o: Vector2 = grove_slots[idx][0]
						if o.distance_squared_to(p) < SUB_SLOT * SUB_SLOT:
							ok = false
							break
					if not ok:
						break
				if not ok:
					break
			if not ok or (hero != Vector2.INF and p.distance_to(hero) < HERO_CLEAR + 2.0):
				continue
			if not grid.has(key):
				grid[key] = PackedInt32Array()
			grid[key].append(grove_slots.size())
			grove_slots.append([p, zone, false, 1])
	grove_grid = grid
	var per_zone := {}
	for slot in grove_slots:
		var nm: String = ZONE_NAMES[int(slot[1])] + ("" if int(slot[3]) == 0 else "_sub")
		per_zone[nm] = per_zone.get(nm, 0) + 1
	grove_stats = {"slots": per_zone, "land_cells": land, "cut": cut, "resource": resource_counts}
	print("LAYOUT groves: slots ", per_zone, " resource ", resource_counts, " land(4m2) ", land, " band-free ",
		values.map(func(v): return v.size()), " ms=", Time.get_ticks_msec() - t0)


## Pass 3 look of a tree in a grove: kit variant (+green copy) and the feature-tree scale.
func _grove_look(tree: Dictionary, species: int, x: float, z: float, zone: int, sub := false) -> Array:
	var look := _resource_look(tree, species, x, z, false)
	var u := clampf((float(tree.scale) - 0.45) / 0.85, 0.0, 1.0)
	var r: Array = SUB_SCALE[0 if species == Rules.OAK else 1] if sub else GROVE_SCALE[zone][0 if species == Rules.OAK else 1]
	var scale := lerpf(r[0], r[1], fposmod(u * 0.6 + Rules.id_hash(String(tree.id)) * 0.4, 1.0))
	# glade / landmark edges keep a smaller tree (art/01: young trees at the clearing rims)
	scale = lerpf(scale, scale * 0.7, clampf(openness(x, z) - 0.5, 0.0, 0.5) * 2.0)
	return [look[0], snappedf(scale, 0.001)]


## Nearest free grove slot of `zone` for a resource tree; the crown must clear the strict unit
## zones (glades, arena, horse spot, landmarks, water features); trails get the runtime fade.
func _take_grove_slot(tree: Dictionary, species: int, zone: int, tx: float, tz: float) -> Vector2:
	var p := _take_slot_kind(tree, species, zone, tx, tz, 0, 4)
	_last_sub = p == Vector2.INF
	if p == Vector2.INF:
		p = _take_slot_kind(tree, species, zone, tx, tz, 1, 14)
	return p


var _last_sub := false


func _take_slot_kind(tree: Dictionary, species: int, zone: int, tx: float, tz: float, kind: int, rings: int) -> Vector2:
	var key := Vector2i(floori(tx / GROVE_CELL), floori(tz / GROVE_CELL))
	for ring in rings:
		var best := -1
		var best_d := INF
		for gz in range(key.y - ring, key.y + ring + 1):
			for gx in range(key.x - ring, key.x + ring + 1):
				if ring > 0 and absi(gx - key.x) != ring and absi(gz - key.y) != ring:
					continue
				for idx in grove_grid.get(Vector2i(gx, gz), PackedInt32Array()):
					var slot: Array = grove_slots[idx]
					if bool(slot[2]) or int(slot[1]) != zone or int(slot[3]) != kind:
						continue
					var d := (slot[0] as Vector2).distance_squared_to(Vector2(tx, tz))
					if d < best_d:
						best_d = d
						best = idx
		if best >= 0:
			var p: Vector2 = grove_slots[best][0]
			var look := _grove_look(tree, species, p.x, p.y, zone, kind == 1)
			var crown: float = Rules.CROWN_RADIUS[species] * float(look[1])
			grove_slots[best][2] = true
			if blocked_exact(p.x, p.y, true, 1.0, crown, dense_pine_ok(zone, species)) or not free_of_trunks(p.x, p.y, 2.3) \
					or tree_hides_units(p.x, p.y, species, int(look[0]) % Rules.GREEN_VARIANT_BASE, float(look[1]), float(tree.angle), true):
				continue          # slot unusable for this crown: try the next ring (slot stays consumed)
			return p
	return Vector2.INF


## Ambient feature trees on the free grove slots + a few solitary trees on the meadows.
func _fill_groves(trees: Array, species_count: Dictionary) -> void:
	var order := range(grove_slots.size())
	_shuffle(order)
	var placed := 0
	for idx in order:
		var slot: Array = grove_slots[idx]
		if bool(slot[2]) or int(slot[3]) != 0:
			continue
		slot[2] = true
		var p: Vector2 = slot[0]
		var zone: int = slot[1]
		var species := Rules.pick_weighted(ZONE_MIX[zone], rng.randf())
		var site01: Dictionary = atlas.site_by_id.get("lf_site_01", {})
		if not site01.is_empty() and p.distance_to(Vector2(site01.center.x, site01.center.z)) < BIRCH_RING:
			species = Rules.BIRCH if rng.randf() < 0.85 else species
		var r: Array = GROVE_SCALE[zone][0 if species == Rules.OAK else 1] if species in [Rules.OAK, Rules.PINE] else AMBIENT_SCALE[species][zone]
		var scale := lerpf(r[0], r[1], rng.randf())
		if zone == Z_GROVE and species == Rules.OAK:
			scale = lerpf(GROVE_OAK_SCALE[0], GROVE_OAK_SCALE[1], rng.randf()) * 0.82
		scale = lerpf(scale, scale * 0.7, clampf(openness(p.x, p.y) - 0.5, 0.0, 0.5) * 2.0)
		var crown: float = Rules.CROWN_RADIUS[species] * scale
		if blocked_exact(p.x, p.y, true, 1.0, crown, dense_pine_ok(zone, species)) or not ground_ok(p.x, p.y, true) \
				or not free_of_trunks(p.x, p.y, 2.3):
			continue
		var variants: Array = ZONE_VARIANTS[species][zone]
		var variant: int = variants[rng.randi() % variants.size()]
		var drawn := species
		if species == Rules.OAK and zone != Z_GROVE and not oak_is_golden(p.x, p.y, rng.randf()):
			drawn = Rules.OAK_GREEN
			variant = clampi(variant, 2, 4)
		var yaw_deg := snappedf(rng.randf() * 360.0, 0.1)
		if tree_hides_units(p.x, p.y, drawn, variant, scale, deg_to_rad(yaw_deg), true):
			continue          # never in front of a glade, the arena, the horse spot or a landmark
		insert(trunk_grid, trunks, [p.x, p.y, 3.0])
		trees.append([snappedf(p.x, 0.01), snappedf(p.y, 0.01), drawn, variant, yaw_deg, snappedf(scale, 0.001), zone])
		species_count[Rules.SPECIES[drawn]] = species_count.get(Rules.SPECIES[drawn], 0) + 1
		placed += 1
	# solitary big trees on the meadows (art/01: single oaks / pines between the groves)
	var solitary := 0
	var tries := 0
	while solitary < 70 and tries < 4000:
		tries += 1
		var x := rng.randf_range(-EXTENT + 4.0, EXTENT - 4.0)
		var z := rng.randf_range(-EXTENT + 4.0, EXTENT - 4.0)
		if maxf(absf(x), absf(z)) < CORE + 4.0:
			continue
		var zone := dominant_zone(x, z)
		if zone == Z_SPRUCE or _grove_value(x, z) > 0.5:
			continue
		var species := Rules.OAK if zone in [Z_GROVE, Z_TOP, Z_EAST, Z_BELT] else Rules.pick_weighted(ZONE_MIX[zone], rng.randf())
		var r2: Array = GROVE_SCALE[zone][0 if species == Rules.OAK else 1] if species in [Rules.OAK, Rules.PINE] else AMBIENT_SCALE[species][zone]
		var scale := lerpf(r2[0], r2[1], rng.randf())
		var crown: float = Rules.CROWN_RADIUS[species] * scale
		if blocked_exact(x, z, true, 1.0, crown) or not ground_ok(x, z, true) or not free_of_trunks(x, z, 14.0) or is_glade(x, z):
			continue
		var drawn := species
		var variants: Array = ZONE_VARIANTS[species][zone]
		var variant: int = variants[rng.randi() % variants.size()]
		if species == Rules.OAK and zone != Z_GROVE and not oak_is_golden(x, z, rng.randf()):
			drawn = Rules.OAK_GREEN
			variant = clampi(variant, 2, 4)
		var yaw_deg := snappedf(rng.randf() * 360.0, 0.1)
		if tree_hides_units(x, z, drawn, variant, scale, deg_to_rad(yaw_deg)):
			continue
		insert(trunk_grid, trunks, [x, z, 3.0])
		trees.append([snappedf(x, 0.01), snappedf(z, 0.01), drawn, variant, yaw_deg, snappedf(scale, 0.001), zone])
		species_count[Rules.SPECIES[drawn]] = species_count.get(Rules.SPECIES[drawn], 0) + 1
		solitary += 1
	print("LAYOUT groves: ambient on slots=", placed, " solitary=", solitary)


## Debug (--probe=cx,cz,r): why no ambient pine stands on each 2 m cell of a region (ASCII map,
## screen-agnostic world grid; x → columns, z → rows).
func _probe_region(cx: float, cz: float, r: float) -> void:
	var counts := {}
	var lines: Array = []
	var z := cz - r
	while z <= cz + r:
		var line := ""
		var x := cx - r
		while x <= cx + r:
			var code := "."
			var scale := 1.06
			var crown: float = Rules.CROWN_RADIUS[Rules.PINE] * scale
			if blocked_exact(x, z, true):
				code = "B"
			elif not ground_ok(x, z, true):
				code = "g"
			elif is_glade(x, z):
				code = "o"
			elif not free_of_trunks(x, z, 2.2):
				code = "t"
			elif blocked_exact(x, z, true, 1.0, crown):
				code = "c"
			elif tree_hides_units(x, z, Rules.PINE, 2, scale, 0.0, true):
				code = "S"
			elif tree_hides_units(x, z, Rules.PINE, 2, scale, 0.0):
				code = "T"
			code = code if dominant_zone(x, z) == Z_SPRUCE or code != "." else "z"
			counts[code] = counts.get(code, 0) + 1
			line += code
			x += 2.0
		lines.append(line)
		z += 2.0
	print("PROBE ", cx, ",", cz, " r=", r, " counts=", counts)
	for line in lines:
		print("PROBE| ", line)


## Trail-edge dressing (art/07 panels 1–3): along every visual trail (atlas.routes incl. the
## decorative network), alternating sides every 1.4–3 m, an item 1.25–2.3 m from the centre line
## (decorative trails 1.0–1.8 m): grass tufts, small mossy stones, roots (fallen branches laid
## along the trail), ferns, a few mushrooms. Kept off glades, the base, the bridge, the arena and
## the wet river channel.
func _trail_dressing() -> Array:
	var out: Array = []
	var grid := {}
	var store: Array = []
	var kinds := ["grass", "rock", "branches", "fern", "mushrooms"]
	var weights := [0.42, 0.26, 0.16, 0.11, 0.05]
	for route in atlas.routes:
		var decor: bool = route.get("decor", false)
		var points: PackedVector3Array = route.points
		var along := 0.0
		var next := rng.randf_range(0.5, 2.0)
		for i in range(1, points.size()):
			var a := Vector2(points[i - 1].x, points[i - 1].z)
			var b := Vector2(points[i].x, points[i].z)
			along += a.distance_to(b)
			if along < next:
				continue
			next = along + rng.randf_range(1.4, 3.0)
			var tangent := (b - a).normalized()
			var normal := Vector2(-tangent.y, tangent.x)
			var side := -1.0 if rng.randf() < 0.5 else 1.0
			var lateral := rng.randf_range(1.0, 1.8) if decor else rng.randf_range(1.25, 2.3)
			var q := b + normal * side * lateral
			if maxf(absf(q.x), absf(q.y)) < CORE + 0.5 or maxf(absf(q.x), absf(q.y)) > EXTENT - 1.0:
				continue
			var hit: Dictionary = atlas.nearest_route(q.x, q.y)
			if not hit.is_empty() and float(hit.distance) < (0.95 if decor else 1.15):
				continue
			if atlas.river_bank_distance(q.x, q.y) < 0.5 or atlas.bridge_deck_rect().grow(3.0).has_point(q):
				continue
			if q.distance_to(Vector2(atlas.arena_center.x, atlas.arena_center.z)) < ARENA_RIM_UNDER:
				continue
			var in_glade := false
			for site in atlas.sites:
				if q.distance_to(Vector2(site.center.x, site.center.z)) < float(site.radius) + 0.5:
					in_glade = true
			for extra in atlas.extra_glades:
				if q.distance_to(Vector2(extra.center.x, extra.center.z)) < float(extra.radius) + 0.5:
					in_glade = true
			for body in water:
				if ForestTerrain.shore_distance(body, q.x, q.y) < 0.6:
					in_glade = true
			if in_glade or terrain.slope_degrees(q.x, q.y) > 34.0:
				continue
			var crowded := false
			for other in near_points(q.x, q.y, 1.6, grid, store):
				if q.distance_to(Vector2(other[0], other[1])) < 1.1:
					crowded = true
					break
			if crowded:
				continue
			insert(grid, store, [q.x, q.y, 0.0])
			var kind_name: String = kinds[Rules.pick_index(weights, rng.randf())]
			var spec: Array = Rules.UNDERSTORY_KIT[kind_name]
			var variant := 1 + rng.randi() % (spec[1] as Array).size()
			var yaw := rng.randf() * 360.0
			var scale := rng.randf_range(0.8, 1.15)
			match kind_name:
				"rock":
					scale = rng.randf_range(0.16, 0.32)
				"branches":
					scale = rng.randf_range(0.5, 0.75)
					yaw = rad_to_deg(atan2(tangent.x, tangent.y)) + rng.randf_range(-25.0, 25.0)
				"fern":
					scale = rng.randf_range(0.6, 0.85)
				"mushrooms":
					scale = rng.randf_range(0.8, 1.1)
			out.append([snappedf(q.x, 0.01), snappedf(q.y, 0.01), Rules.UNDERSTORY.find(kind_name), variant,
				snappedf(yaw, 0.1), snappedf(scale, 0.001)])
	return out


## River banks (art/01 east river): boulders half in the water along both wet edges, reed beds
## in patches on the wet margin, willows leaning over the water where the bank allows.
func _bank_dressing(trees: Array, under: Array, under_grid: Dictionary, logs: Array, log_grid: Dictionary,
		kinds_count: Dictionary, species_count: Dictionary) -> void:
	var z := -EXTENT
	var willow_next := [-EXTENT, -EXTENT + 6.0]
	while z <= EXTENT:
		var r: Vector3 = atlas.river_at(z)
		for side in 2:
			var edge: float = r.y if side == 0 else r.z
			var out := -1.0 if side == 0 else 1.0
			var patch := (clump.get_noise_2d(edge * 0.7, z * 0.7) + 1.0) * 0.5
			# boulders right at the wet edge (partly submerged)
			if rng.randf() < 0.55:
				var x := edge + out * lerpf(-0.6, 0.8, rng.randf())
				var zz := z + rng.randf() * 1.5
				if _bank_ok(x, zz, 1.4):
					var big := rng.randf() < 0.3
					var kind := "quarry_rock" if not big else "rock"
					var variant := 1 if (big or rng.randf() < 0.6) else 2
					var scale := lerpf(0.26, 0.5, rng.randf()) if not big else lerpf(0.22, 0.36, rng.randf())
					insert(under_grid, under, [snappedf(x, 0.01), snappedf(zz, 0.01), 1.6, Rules.UNDERSTORY.find(kind), variant,
						snappedf(rng.randf() * 360.0, 0.1), snappedf(scale, 0.001)])
					insert(log_grid, logs, [x, zz, 0.0])
					kinds_count["bank_" + kind] = kinds_count.get("bank_" + kind, 0) + 1
			# reed beds in patches on the wet margin
			if patch > 0.45:
				for k in 2:
					var x := edge + out * lerpf(-1.2, 0.6, rng.randf())
					var zz := z + rng.randf() * 2.4
					if _bank_ok(x, zz, 1.0):
						insert(under_grid, under, [snappedf(x, 0.01), snappedf(zz, 0.01), 1.2, Rules.UNDERSTORY.find("reed"), 1 + rng.randi() % 3,
							snappedf(rng.randf() * 360.0, 0.1), snappedf(lerpf(0.75, 1.15, rng.randf()), 0.001)])
						kinds_count["bank_reed"] = kinds_count.get("bank_reed", 0) + 1
			# willows on the bank top, leaning over the water
			if z >= willow_next[side]:
				var x := edge + out * lerpf(1.4, 3.2, rng.randf())
				var scale := lerpf(0.82, 1.02, rng.randf())
				var variant := 2 + rng.randi() % 2
				var yaw_deg := snappedf(rad_to_deg(atan2(-out, 0.0)) + lerpf(-40.0, 40.0, rng.randf()), 0.1)
				if maxf(absf(x), absf(z)) > CORE + 1.0 and not blocked_exact(x, z, true, 1.0, 4.0) \
						and terrain.ground_height(x, z) > -0.4 and terrain.slope_degrees(x, z) < 38.0 and free_of_trunks(x, z, 3.2) \
						and not tree_hides_units(x, z, Rules.WILLOW, variant, scale, deg_to_rad(yaw_deg)):
					insert(trunk_grid, trunks, [x, z, 3.2])
					trees.append([snappedf(x, 0.01), snappedf(z, 0.01), Rules.WILLOW, variant,
						yaw_deg, snappedf(scale, 0.001), Z_RIVER])
					species_count[Rules.SPECIES[Rules.WILLOW]] = species_count.get(Rules.SPECIES[Rules.WILLOW], 0) + 1
					willow_next[side] = z + lerpf(9.0, 17.0, rng.randf())
				else:
					willow_next[side] = z + 2.0
		z += 2.4


## Atlas v2 water (art/01): reed beds ringing the lake, the waterfall pond and the marsh pools
## (shore band -0.8 .. +1.4 m, patchy), a few stones at the pond dam, willows leaning over the
## lake and the pond (never in front of a unit: camera clearance).
func _water_dressing(trees: Array, under: Array, under_grid: Dictionary, logs: Array, log_grid: Dictionary,
		kinds_count: Dictionary, species_count: Dictionary) -> void:
	var reed := Rules.UNDERSTORY.find("reed")
	for body in water:
		var c: Vector2 = body.center
		var r: float = body.radius
		var perimeter := TAU * r
		var steps := maxi(10, int(perimeter / 1.15))
		var willow_next := 0.0
		for k in steps:
			var angle := TAU * (k + rng.randf() * 0.6) / steps
			var shore := ForestTerrain.shore_radius(body, angle)
			var patch := (clump.get_noise_2d(c.x + cos(angle) * 9.0, c.y + sin(angle) * 9.0) + 1.0) * 0.5
			if patch > (0.32 if body.kind == "pond" else (0.27 if body.kind == "lake" else 0.18)):
				for j in (3 if body.kind == "lake" else (2 if body.kind == "marsh" else 1)):
					var dist := shore + rng.randf_range(-0.8, 1.4)
					var p := c + Vector2(cos(angle), sin(angle)) * dist
					if _bank_ok(p.x, p.y, 1.0):
						insert(under_grid, under, [snappedf(p.x, 0.01), snappedf(p.y, 0.01), 1.1, reed, 1 + rng.randi() % 3,
							snappedf(rng.randf() * 360.0, 0.1), snappedf(lerpf(0.7, 1.1, rng.randf()), 0.001)])
						kinds_count["water_reed"] = kinds_count.get("water_reed", 0) + 1
			elif (body.perched or body.kind == "lake") and rng.randf() < (0.35 if body.perched else 0.75):
				var p := c + Vector2(cos(angle), sin(angle)) * (shore + rng.randf_range(0.2, 0.9))
				if _bank_ok(p.x, p.y, 1.4):
					insert(under_grid, under, [snappedf(p.x, 0.01), snappedf(p.y, 0.01), 1.4, Rules.UNDERSTORY.find("quarry_rock"), 1,
						snappedf(rng.randf() * 360.0, 0.1), snappedf(rng.randf_range(0.16, 0.3) * (1.6 if body.kind == "lake" else 1.0), 0.001)])
					kinds_count["water_stone"] = kinds_count.get("water_stone", 0) + 1
			if body.kind == "marsh":
				continue
			var along := angle * shore
			if along >= willow_next:
				var dist := shore + rng.randf_range(2.6, 4.4)
				var p := c + Vector2(cos(angle), sin(angle)) * dist
				var scale := lerpf(0.8, 1.0, rng.randf())
				var variant := 2 + rng.randi() % 2
				var yaw_deg := snappedf(rad_to_deg(atan2(-cos(angle), -sin(angle))) + lerpf(-35.0, 35.0, rng.randf()), 0.1)
				# pass 3 (art/01): dark pines crowd the lake shore between the willows
				var sp := Rules.PINE if body.kind == "lake" and rng.randf() < 0.6 else Rules.WILLOW
				if sp == Rules.PINE:
					scale = lerpf(0.95, 1.2, rng.randf())
					variant = 2 + rng.randi() % 3
				if maxf(absf(p.x), absf(p.y)) > CORE + 1.0 and not blocked_exact(p.x, p.y, true, 1.0, 4.0) and ground_ok(p.x, p.y, true) \
						and terrain.slope_degrees(p.x, p.y) < 34.0 and free_of_trunks(p.x, p.y, 3.0 if sp == Rules.PINE else 3.4) \
						and not tree_hides_units(p.x, p.y, sp, variant, scale, deg_to_rad(yaw_deg), true):
					insert(trunk_grid, trunks, [p.x, p.y, 3.4])
					trees.append([snappedf(p.x, 0.01), snappedf(p.y, 0.01), sp, variant, yaw_deg, snappedf(scale, 0.001), Z_RIVER])
					species_count[Rules.SPECIES[sp]] = species_count.get(Rules.SPECIES[sp], 0) + 1
					willow_next = along + (lerpf(3.5, 6.0, rng.randf()) if sp == Rules.PINE else lerpf(7.0, 12.0, rng.randf()))


func _bank_ok(x: float, z: float, spacing: float) -> bool:
	if maxf(absf(x), absf(z)) < CORE + 0.5 or maxf(absf(x), absf(z)) > EXTENT - 1.0:
		return false
	if blocked_exact(x, z, false) or atlas.bridge_deck_rect().grow(3.0).has_point(Vector2(x, z)):
		return false
	for other in near_points(x, z, spacing + 1.0, _bank_grid, _bank_points):
		if Vector2(x - other[0], z - other[1]).length() < spacing:
			return false
	insert(_bank_grid, _bank_points, [x, z, 0.0])
	return true


var _bank_points: Array = []
var _bank_grid := {}


## SW quarry (art/01): light-grey cliffs and ledges wrap the back of the mine and the far side of
## the quarry pit (moss rock v3 ledge slabs stacked in 2–3 terraces, quarry palette), v2 boulder
## piles in the pit. Kept off the mine, the route clearances and glade 08.
func _quarry_cliffs(under: Array, under_grid: Dictionary, logs: Array, log_grid: Dictionary, kinds_count: Dictionary) -> void:
	if quarry_center == Vector2.INF:
		return
	var mine := Vector2.INF
	for disc in landmark_discs:
		if Vector2(disc[0]).distance_to(quarry_center) < 14.0:
			mine = disc[0]
	var site: Dictionary = atlas.site_by_id.lf_site_05
	var glade_c := Vector2(site.center.x, site.center.z)
	var base_angle := quarry_axis
	var kind := Rules.UNDERSTORY.find("quarry_rock")
	var tiers := [[12.0, 0.0, 1.45], [15.5, 2.2, 1.6], [19.0, 4.4, 1.75], [22.5, 6.4, 1.85]]   # pass 3: terraces
	for tier in tiers.size():
		var radius: float = tiers[tier][0]
		var lift: float = tiers[tier][1]
		var scale: float = tiers[tier][2]
		var arc := deg_to_rad(210.0 - tier * 25.0)
		var steps := int(arc * radius / 5.0)
		for k in steps + 1:
			var a := base_angle - arc * 0.5 + arc * k / maxf(1.0, steps) + rng.randf_range(-0.05, 0.05)
			var c := quarry_center + Vector2(cos(a), sin(a)) * (radius + rng.randf_range(-0.8, 0.8))
			if mine != Vector2.INF and c.distance_to(mine) < 7.5:
				continue
			if c.distance_to(glade_c) < float(site.radius) + 2.5 or blocked_exact(c.x, c.y, false):
				continue
			if not ground_ok(c.x, c.y, false):
				continue
			# slab long axis tangent to the arc, face toward the pit
			var yaw := rad_to_deg(atan2(cos(a), -sin(a))) + rng.randf_range(-12.0, 12.0)
			insert(under_grid, under, [snappedf(c.x, 0.01), snappedf(c.y, 0.01), 4.0, kind, 2, snappedf(yaw, 0.1),
				snappedf(scale * rng.randf_range(0.92, 1.08), 0.001), snappedf(lift, 0.01)])
			insert(log_grid, logs, [c.x, c.y, 0.0])
			kinds_count["quarry_ledge"] = kinds_count.get("quarry_ledge", 0) + 1
	# boulder piles in the pit, between the glade and the cliffs
	for k in 26:
		var a := base_angle + rng.randf_range(-1.6, 1.6)
		var c := quarry_center + Vector2(cos(a), sin(a)) * rng.randf_range(4.0, 11.0)
		if mine != Vector2.INF and c.distance_to(mine) < 6.5:
			continue
		if c.distance_to(glade_c) < float(site.radius) + 0.5 or blocked_exact(c.x, c.y, false):
			continue
		insert(under_grid, under, [snappedf(c.x, 0.01), snappedf(c.y, 0.01), 2.0, kind, 1, snappedf(rng.randf() * 360.0, 0.1),
			snappedf(rng.randf_range(0.3, 0.6), 0.001)])
		kinds_count["quarry_boulder"] = kinds_count.get("quarry_boulder", 0) + 1


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
		if not _cam_tree.is_empty():
			var cam := _cam_state_for(_cam_tree, _cam_species, x, z, false)
			if cam == 0:
				continue
			score += 0.8 * (cam - 1)
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
			if not _cam_tree.is_empty() and _cam_state_for(_cam_tree, _cam_species, x, z, false) == 0:
				continue
			return Vector2(x, z)
		radius += 0.5
	return Vector2.INF


## Crown radius (m) the resource tree will have at (x, z).
func _resource_crown(tree: Dictionary, species: int, x: float, z: float) -> float:
	var look := _resource_look(tree, species, x, z, false)
	return Rules.CROWN_RADIUS[species] * float(look[1])


var _cam_tree: Dictionary = {}       # resource tree being placed (camera clearance active)
var _cam_species := 0


## Young look of a resource tree (low crown: the camera sees units past it).
func _young_scale(tree: Dictionary) -> float:
	var u := clampf((float(tree.scale) - 0.45) / 0.85, 0.0, 1.0)
	return snappedf(lerpf(0.30, 0.36, u), 0.001)


## Camera clearance of a resource tree at (x, z): 2 = natural look hides no unit zone,
## 1 = only the young look does not, 0 = both hide a unit zone.
func _cam_state_for(tree: Dictionary, species: int, x: float, z: float, inner: bool) -> int:
	var look := _resource_look(tree, species, x, z, inner)
	var variant: int = int(look[0]) % Rules.GREEN_VARIANT_BASE
	var yaw := float(tree.angle)
	if not tree_hides_units(x, z, species, variant, float(look[1]), yaw):
		return 2
	return 1 if not tree_hides_units(x, z, species, variant, _young_scale(tree), yaw) else 0


## Resource look at the final slot, made young when the natural crown would hide a unit zone;
## ids that still hide one (young as well) are listed — runtime whole-tree fade.
func _camera_look(tree: Dictionary, species: int, x: float, z: float, inner: bool) -> Array:
	var look := _resource_look(tree, species, x, z, inner)
	var state := _cam_state_for(tree, species, x, z, inner)
	if state < 2 and not inner and dense_pine_ok(dominant_zone(x, z), species):
		var variant: int = int(look[0]) % Rules.GREEN_VARIANT_BASE
		if not tree_hides_units(x, z, species, variant, float(look[1]), float(tree.angle), true):
			camera_occluders.append(String(tree.id))      # natural look; faded whole when it hides walkers
			return look
	if state < 2:
		# young look (low, small crown): clear for the camera, or at least the smallest occluder
		look[1] = minf(float(look[1]), _young_scale(tree))
	if state == 0:
		camera_occluders.append(String(tree.id))
	return look


## Openness 0..1 from art/01: 1 inside/at the edge of clearings, site camps, trails, art glades
## and landmark spots (young trees, saplings), 0 in forest cores (full-size trees).
func openness(x: float, z: float) -> float:
	var key := Vector2i(floori(x), floori(z))
	if _open_cache.has(key):
		return _open_cache[key]
	var value := _openness_raw(floori(x) + 0.5, floori(z) + 0.5)
	_open_cache[key] = value
	return value


func _openness_raw(x: float, z: float) -> float:
	# atlas v2: trails wind through mature forest (art/01), so only glades, the arena and the
	# landmark spots open the forest up (young trees, saplings) — trails do not.
	var d := 99.0
	for site in atlas.sites:
		d = minf(d, Vector2(x, z).distance_to(Vector2(site.center.x, site.center.z)) - float(site.radius))
	for extra in atlas.extra_glades:
		d = minf(d, Vector2(x, z).distance_to(Vector2(extra.center.x, extra.center.z)) - float(extra.radius))
	d = minf(d, Vector2(x, z).distance_to(Vector2(atlas.arena_center.x, atlas.arena_center.z)) - 17.0)
	for disc in landmark_discs:
		d = minf(d, Vector2(x, z).distance_to(disc[0]) - float(disc[1]))
	var g := (glade.get_noise_2d(x, z) + 1.0) * 0.5
	var zone := dominant_zone(x, z)
	var threshold := 0.3 if zone == Z_GROVE else (0.2 if zone == Z_BELT else (0.15 if zone in [Z_TOP, Z_EAST, Z_QUARRY] else (0.02 if zone == Z_SPRUCE else 0.07)))
	var open_glade := 1.0 - smoothstep(threshold, threshold + 0.12, g)
	return maxf(1.0 - smoothstep(2.0, 13.0, d), open_glade)


## art/01 palette zoning: oaks are golden inside the NW grove (and its border, ~12 % accents
## elsewhere, more near the grove), deep-green broadleaf (baked atlas copy) everywhere else.
func oak_is_golden(x: float, z: float, roll: float) -> bool:
	var w := zone_weights(x, z)
	var gold := clampf(w[Z_GROVE] * 1.25 + w[Z_TOP] * 0.55 + w[Z_ARENA] * 0.1, 0.0, 1.0)
	return roll < maxf(gold, 0.04)


## Resource look: [kit variant (+GREEN_VARIANT_BASE for the green oak copy), absolute scale].
## Openness decides the size: young trees/saplings (0.30–0.50) in openings, full size around the
## kit recommendedScale in forest cores; grove pines stay young (art/01: few spruces in the grove).
func _resource_look(tree: Dictionary, species: int, x: float, z: float, inner: bool) -> Array:
	var h := Rules.id_hash(String(tree.id))
	var u := clampf((float(tree.scale) - 0.45) / 0.85, 0.0, 1.0)
	var zone := Z_BELT if inner else dominant_zone(x, z)
	var variants: Array = ZONE_VARIANTS[species][zone]
	var variant: int = variants[int(h * 997.0) % variants.size()]
	var scale := 0.0
	if inner:
		var r: Array = RESOURCE_SCALE_INNER[0 if species == Rules.OAK else 1]
		scale = lerpf(r[0], r[1], u)
	else:
		var open := openness(x, z)
		var young := lerpf(0.30, 0.50, u) if not (zone == Z_SPRUCE and species == Rules.OAK) else lerpf(0.27, 0.34, u)
		var core: float
		if species == Rules.OAK:
			core = lerpf(0.62, 0.92, u) if zone != Z_SPRUCE else lerpf(0.30, 0.38, u)
		else:
			core = lerpf(0.82, 1.14, u) if zone != Z_GROVE else lerpf(0.40, 0.52, u)
		scale = lerpf(core, young, open)
	if species == Rules.OAK and variant > 1 and not (zone == Z_GROVE or oak_is_golden(x, z, fposmod(h * 7.31, 1.0))):
		variant += Rules.GREEN_VARIANT_BASE
	return [variant, snappedf(scale, 0.001)]


func _find_hero_spot() -> Vector2:
	var radius := 0.0
	while radius <= 22.0:
		for k in maxi(1, int(radius * 3.0)):
			var angle := TAU * k / maxf(1.0, radius * 3.0)
			var p: Vector2 = hero_preferred + Vector2(cos(angle), sin(angle)) * radius
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
	return hero_preferred


const HORSE_CLEAR := 3.9
const ENTRY_CLEAR := 3.0


func _entry_distance(p: Vector2, points: PackedVector3Array) -> float:
	var best := INF
	for i in range(points.size() - 1):
		best = minf(best, ForestMasks.segment_distance(p, Vector2(points[i].x, points[i].z), Vector2(points[i + 1].x, points[i + 1].z)))
	return best


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
