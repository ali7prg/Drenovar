extends RefCounted
## Authoring rules shared by the offline layout builder and the runtime (species ids,
## per-zone mixes, spacing). Changing anything here requires bumping LAYOUT_VERSION and
## re-running tools/build_forest_layout.gd (the remap of resource-tree ids is versioned).
##
## v2 (kit v2): zoning follows the art/01 masterplan as seen from the city camera (screen
## space: golden-oak grove upper-left with the hero cave oak, quarry lower-left, dark spruce
## forest at the bottom, river willows/reeds on the right, arena pines upper-right, mixed
## broadleaf/birch transitions). Trees keep their authored real-metre size (meta heightM);
## `scale` in the layout is the absolute instance scale (inside the kit recommendedScale).

const LAYOUT_VERSION := 2
const LAYOUT_ID := "lf_forest_layout_v2"
const LAYOUT_PATH := "res://data/forest_rescue/world/forest_layout_v2.json"
const PREVIOUS_LAYOUT_ID := "lf_forest_layout_v1"
const SEED := 2207

## Tree species (index used in the layout file).
## OAK_GREEN = the golden-oak meshes with the baked green-broadleaf atlas (art/01: deep-green
## round broadleaf everywhere outside the golden grove); a resource «Дуб» may use either.
const SPECIES := ["lf_env_golden_oak", "lf_env_dark_pine", "lf_env_birch", "lf_env_willow", "lf_env_hollow_oak", "lf_env_golden_oak_green"]
const OAK := 0
const PINE := 1
const BIRCH := 2
const WILLOW := 3
const HOLLOW_OAK := 4
const OAK_GREEN := 5
## Resource look variant >= GREEN_VARIANT_BASE means "green copy of oak variant (v - base)".
const GREEN_VARIANT_BASE := 10
## Kit variants per species (1-based, forest_kit.json biomeTreeMix): v1 = art/02 hero palette,
## v2+ = art/01 palettes (grove oak golden-ochre, dark blue-green spruce, east-river willow).
const SPECIES_VARIANTS := [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3], [1, 2, 3], [1, 2, 3], [2, 3, 4]]
## Kit recommendedScale per species (meta), and the hero cave oak heroScale.
const SPECIES_SCALE := [[0.65, 1.1], [0.75, 1.3], [0.8, 1.35], [0.8, 1.2], [1.7, 2.0], [0.65, 1.1]]
const HERO_SCALE := 1.8
## Nominal crown radius (m, at scale 1) for clearance rules; real value comes from meta footprintM.
const CROWN_RADIUS := [7.0, 3.0, 3.8, 5.4, 6.4, 7.0]
const TRUNK_RADIUS := [1.0, 0.5, 0.5, 0.8, 2.6, 1.0]

## Crown shape per species / kit variant at scale 1, measured from the kit LOD0 foliage cards
## (leaf height p3 … p99.5, radius p85 around the crown centre, centre offset in model space):
## [crown base h0, crown top h1, radius, centre x, centre z] (m). OAK_GREEN uses the oak row.
const CROWN_SHAPE := [
	[[3.08, 13.41, 5.77, 1.52, 0.48], [8.88, 16.05, 7.24, -1.61, 1.63], [9.19, 16.57, 6.67, 1.73, 0.23], [8.28, 15.54, 6.93, -2.02, 0.96]],
	[[2.38, 13.22, 2.71, -0.19, 0.03], [2.31, 13.22, 2.73, 0.22, -0.02], [2.57, 14.27, 1.99, -0.14, 0.01], [2.64, 15.07, 1.83, 0.17, -0.02]],
	[[1.0, 12.51, 2.43, 1.25, 0.06], [4.98, 12.45, 3.38, -1.55, 0.2], [4.89, 12.87, 2.93, 1.09, -0.09]],
	[[1.08, 11.43, 4.91, 3.27, 0.36], [1.11, 11.31, 4.78, -2.73, 0.0], [1.18, 12.12, 4.59, 2.72, 0.38]],
	[[2.6, 13.95, 5.16, 0.42, 0.62], [4.31, 13.76, 5.46, -1.33, 0.19], [3.61, 13.22, 5.21, 1.08, 0.19]],
]
## Fixed city camera (target + (75, 83, 75), 38°): a point h metres up is drawn over the ground
## point shifted by -VIEW_SHIFT·h·(1, 1).
const VIEW_SHIFT := 0.9037
## Adventure units (soldiers, captives, the mare) for the camera clearance of trails and glades.
const UNIT_HEIGHT := 2.2
const UNIT_RADIUS := 0.4


static func crown_shape(species: int, variant: int) -> Array:
	var table: Array = CROWN_SHAPE[OAK if species == OAK_GREEN else clampi(species, 0, CROWN_SHAPE.size() - 1)]
	return table[clampi(variant - 1, 0, table.size() - 1)]


## Ground footprint, along the fixed city camera's view, of the crown part that hides a unit of
## height `unit_h` standing on the ground: [a: Vector2, b: Vector2, radius]. A unit whose feet
## stand within `radius` (+ UNIT_RADIUS) of segment a–b is hidden by this crown (the crown sits
## between the camera and the unit). yaw: instance rotation about +Y (radians).
static func crown_capsule(x: float, z: float, species: int, variant: int, scale: float, yaw: float, unit_h := UNIT_HEIGHT) -> Array:
	var shape := crown_shape(species, variant)
	var c := Vector2(x, z) + Vector2(float(shape[3]), float(shape[4])).rotated(-yaw) * scale
	var v0 := maxf(0.0, float(shape[0]) * scale - unit_h)
	var v1 := float(shape[1]) * scale
	return [c - Vector2.ONE * (VIEW_SHIFT * v1), c - Vector2.ONE * (VIEW_SHIFT * v0), float(shape[2]) * scale]


## Distance between segments p0–p1 and q0–q1 (2D).
static func segment_segment_distance(p0: Vector2, p1: Vector2, q0: Vector2, q1: Vector2) -> float:
	var best := minf(Geometry2D.get_closest_point_to_segment(p0, q0, q1).distance_to(p0),
		Geometry2D.get_closest_point_to_segment(p1, q0, q1).distance_to(p1))
	best = minf(best, Geometry2D.get_closest_point_to_segment(q0, p0, p1).distance_to(q0))
	best = minf(best, Geometry2D.get_closest_point_to_segment(q1, p0, p1).distance_to(q1))
	if Geometry2D.segment_intersects_segment(p0, p1, q0, q1) != null:
		return 0.0
	return best


## Understory kinds (index used in the layout file) → [kit asset id, kit variant names].
const UNDERSTORY := ["fern", "reed", "bramble", "rock", "trunk", "branches", "quarry_rock", "grass", "mushrooms"]
const UNDERSTORY_KIT := {
	"fern": ["lf_env_reed_fern", ["fern_v1", "fern_v2"]],
	"reed": ["lf_env_reed_fern", ["reed_v1", "reed_v2", "mixed_v1"]],
	"bramble": ["lf_env_bramble", ["v1", "v2", "v3"]],
	"rock": ["lf_env_moss_rock", ["v1"]],
	"trunk": ["lf_env_fallen_trunk", ["v1", "v2"]],
	"branches": ["lf_env_fallen_branches", ["v1", "v2"]],
	"quarry_rock": ["lf_env_moss_rock", ["v2", "v3"]],
	"grass": ["lf_env_grass_tuft", ["v1", "v2", "v3"]],
	"mushrooms": ["lf_env_mushrooms", ["v1", "v2"]],
}
## Understory kinds drawn with the rock LOD policy (large, stay in proxy chunks).
const LARGE_UNDERSTORY := ["rock", "trunk", "quarry_rock"]

## Resource-tree species by the tree's in-game name (data.woods[].name).
const RESOURCE_SPECIES := {"Дуб": OAK, "Сосна": PINE}

## Remap limits (resource trees keep their ids; visual slot within this distance of the old
## spiral point, except trees pushed out of a route/glade/arena/bridge clearance).
const MAX_SLOT_DISPLACEMENT := 4.0
const MAX_INNER_JITTER := 4.0          # ≤ 3.5 m typical; ≤ 4.0 m to clear the hall-III entrance
const MIN_TREE_GAP := 2.3
## Trunk clearance from a route centre line (route.clear + this); crowns may overhang.
const ROUTE_TRUNK_MARGIN := 1.4
const GLADE_TRUNK_MARGIN := 1.6


static func pick_weighted(mix: Dictionary, roll: float) -> int:
	var total := 0.0
	for key in mix:
		total += float(mix[key])
	var acc := 0.0
	for key in mix:
		acc += float(mix[key]) / total
		if roll <= acc:
			return int(key)
	return int(mix.keys()[-1])


static func pick_index(weights: Array, roll: float) -> int:
	var total := 0.0
	for w in weights:
		total += float(w)
	var acc := 0.0
	for i in weights.size():
		acc += float(weights[i]) / total
		if roll <= acc:
			return i
	return weights.size() - 1


## Legacy variant (0..5: pines 0..2, oaks 3..5) → kit variant: the art/01 palettes v2..v4,
## with the art/02 hero v1 as an occasional warm accent for oaks (decided by the id hash).
static func kit_variant_for_legacy(variant: int, id_hash := 0.5, species := PINE) -> int:
	if species == OAK and id_hash < 0.12:
		return 1
	return (variant % 3) + 2


## Legacy resource scale (0.45..1.3) → absolute instance scale inside the kit recommendedScale.
static func resource_scale(species: int, legacy_scale: float) -> float:
	var u := clampf((legacy_scale - 0.45) / 0.85, 0.0, 1.0)
	var r: Array = SPECIES_SCALE[species]
	return lerpf(float(r[0]), float(r[1]), u)


static func id_hash(id: String) -> float:
	return float(hash(id) & 0xffff) / 65535.0
