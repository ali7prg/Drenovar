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
const SPECIES := ["lf_env_golden_oak", "lf_env_dark_pine", "lf_env_birch", "lf_env_willow", "lf_env_hollow_oak"]
const OAK := 0
const PINE := 1
const BIRCH := 2
const WILLOW := 3
const HOLLOW_OAK := 4
## Kit variants per species (1-based, forest_kit.json biomeTreeMix): v1 = art/02 hero palette,
## v2+ = art/01 palettes (grove oak golden-ochre, dark blue-green spruce, east-river willow).
const SPECIES_VARIANTS := [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3], [1, 2, 3], [1, 2, 3]]
## Kit recommendedScale per species (meta), and the hero cave oak heroScale.
const SPECIES_SCALE := [[0.65, 1.1], [0.75, 1.3], [0.8, 1.35], [0.8, 1.2], [1.7, 2.0]]
const HERO_SCALE := 1.8
## Nominal crown radius (m, at scale 1) for clearance rules; real value comes from meta footprintM.
const CROWN_RADIUS := [7.0, 3.0, 3.8, 5.4, 6.4]
const TRUNK_RADIUS := [1.0, 0.5, 0.5, 0.8, 2.6]

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
const MAX_INNER_JITTER := 3.5
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
