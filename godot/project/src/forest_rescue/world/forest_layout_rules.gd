extends RefCounted
## Authoring rules shared by the offline layout builder and the runtime (species ids,
## per-biome mixes, spacing). Changing anything here requires bumping LAYOUT_VERSION and
## re-running tools/build_forest_layout.gd (the remap of resource-tree ids is versioned).

const LAYOUT_VERSION := 1
const LAYOUT_ID := "lf_forest_layout_v1"
const LAYOUT_PATH := "res://data/forest_rescue/world/forest_layout_v1.json"
const SEED := 1701

## Tree species (index used in the layout file).
const SPECIES := ["lf_env_golden_oak", "lf_env_dark_pine", "lf_env_birch", "lf_env_willow", "lf_env_hollow_oak"]
const OAK := 0
const PINE := 1
const BIRCH := 2
const WILLOW := 3
const HOLLOW_OAK := 4

## Understory kinds (index used in the layout file) → kit asset id.
const UNDERSTORY := ["fern", "reed", "bramble", "rock", "trunk", "stump"]
const UNDERSTORY_ASSET := {
	"fern": "lf_env_reed_fern", "reed": "lf_env_reed_fern", "bramble": "lf_env_bramble",
	"rock": "lf_env_moss_rock", "trunk": "lf_env_fallen_trunk", "stump": "lf_env_fallen_trunk"}

## Resource-tree species by the tree's in-game name (data.woods[].name).
const RESOURCE_SPECIES := {"Дуб": OAK, "Сосна": PINE}

## Per-biome (atlas zones lf_biome_1..8, in atlas order) minimum tree spacing (m) and
## weighted species mix for *ambient* slots. Resource trees keep their own species.
const BIOME_SPACING := [4.1, 5.0, 3.6, 4.7, 5.0, 4.1, 4.5, 4.6]
const BIOME_MIX := [
	{OAK: 0.22, PINE: 0.23, BIRCH: 0.55},                 # Берёзовый дозор
	{PINE: 0.72, BIRCH: 0.13, OAK: 0.15},                  # Ломаный известняк
	{PINE: 0.92, BIRCH: 0.08},                             # Тёмная хвоя
	{BIRCH: 0.58, PINE: 0.22, OAK: 0.20},                  # Угольное возрождение
	{BIRCH: 0.42, OAK: 0.38, WILLOW: 0.20},                # Ольховые луга
	{PINE: 0.55, OAK: 0.30, BIRCH: 0.15},                  # Папоротниковый кряж
	{WILLOW: 0.40, BIRCH: 0.30, OAK: 0.30},                # Речные террасы
	{OAK: 0.38, PINE: 0.47, HOLLOW_OAK: 0.04, BIRCH: 0.11},  # Древняя роща
]
## Per-biome understory weights (fern, reed, bramble, rock, trunk, stump) and density scale.
const BIOME_UNDERSTORY := [
	[0.40, 0.00, 0.30, 0.18, 0.07, 0.05],
	[0.18, 0.00, 0.16, 0.52, 0.09, 0.05],
	[0.55, 0.00, 0.16, 0.14, 0.12, 0.03],
	[0.26, 0.00, 0.24, 0.12, 0.13, 0.25],
	[0.42, 0.06, 0.34, 0.10, 0.06, 0.02],
	[0.66, 0.00, 0.14, 0.12, 0.06, 0.02],
	[0.36, 0.20, 0.24, 0.14, 0.04, 0.02],
	[0.28, 0.00, 0.16, 0.40, 0.12, 0.04],
]
const BIOME_UNDERSTORY_DENSITY := [1.0, 0.9, 1.15, 0.95, 1.1, 1.3, 1.0, 0.95]

## Base scale per species (kit assets are authored in real metres; legacy stand-ins differ).
const SPECIES_SCALE := [[0.85, 1.15], [0.85, 1.2], [0.85, 1.15], [0.9, 1.1], [1.0, 1.15]]

## Remap limits.
const MAX_SLOT_DISPLACEMENT := 4.0
const MIN_TREE_GAP := 2.3


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


## Legacy variant (0..5) → kit variant 1..3 (pines 0..2, oaks 3..5).
static func kit_variant_for_legacy(variant: int) -> int:
	return (variant % 3) + 1
