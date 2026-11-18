extends SceneTree
## Offline, deterministic builder of the natural forest layout + resource-tree remap.
##   godot --headless --path godot/project -s res://src/forest_rescue/world/tools/build_forest_layout.gd
## Output: res://data/forest_rescue/world/forest_layout_v1.json (versioned; see forest_layout_rules.gd).
##
## 1. Blue-noise tree slots (dart throwing in a shuffled 1 m lattice, variable radius by biome,
##    low-frequency clearing noise) over [-140,140]² outside the protected core, never inside
##    route clearances, glades, arena, bridge corridor, wet river channel or steep gorge walls.
## 2. Every OUTER resource tree (|x|>56 or |z|>56) is matched to the nearest free slot within
##    4 m (global greedy by ascending distance, ties by id/slot index). Trees whose old spot lies
##    inside a route/glade/arena/bridge mask are pushed just outside; trees without a slot in
##    reach are jittered 1–3 m off their old spiral position. Inner trees keep their position.
## 3. Unclaimed slots become ambient trees with the biome species mix.
## 4. Understory (ferns, reeds, brambles, moss rocks, fallen trunks, stumps) by biome.

const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")
const ForestAtlas = preload("res://src/forest_rescue/world/forest_atlas.gd")
const ForestTerrain = preload("res://src/forest_rescue/world/forest_terrain.gd")
const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")

const EXTENT := 140.0
const CORE := 56.0
const HASH := 2.0

var atlas
var terrain
var masks
var rng := RandomNumberGenerator.new()
var clearing := FastNoiseLite.new()
var hash_grid := {}
var points: Array = []      # [x, z, r]


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


func blocked_exact(x: float, z: float, tree: bool) -> bool:
	if maxf(absf(x), absf(z)) < CORE + (0.8 if tree else 0.3):
		return true
	for gz in range(floori((z - 5.0) / masks.cell), floori((z + 5.0) / masks.cell) + 1):
		for gx in range(floori((x - 5.0) / masks.cell), floori((x + 5.0) / masks.cell) + 1):
			for index in masks.grid.get(Vector2i(gx, gz), PackedInt32Array()):
				var mask: Dictionary = masks.masks[index]
				var margin := 0.0
				match String(mask.get("kind", "")):
					"route":
						margin = 4.4 if tree else 0.0
					"glade":
						margin = 4.4 if tree else 0.3
					"arena":
						margin = 4.4 if tree else 0.5
					"bridge":
						margin = 0.5
				if ForestMasks.inside_mask(x, z, mask, margin):
					return true
	return false


func ground_ok(x: float, z: float, tree: bool) -> bool:
	var h: float = terrain.ground_height(x, z)
	if h < -0.35:
		return false
	return terrain.slope_degrees(x, z) <= (26.0 if tree else 34.0)


func spacing_at(x: float, z: float) -> float:
	var weights: PackedFloat32Array = atlas.biome_weights(x, z)
	var r := 0.0
	for b in weights.size():
		r += Rules.BIOME_SPACING[b] * weights[b]
	var c := (clearing.get_noise_2d(x, z) + 1.0) * 0.5
	if c > 0.70:
		r *= 0.88
	elif c < 0.34:
		r *= 1.45
	# Wet-bank fringe: looser groups of willows/birches.
	if atlas.river_bank_distance(x, z) < 9.0:
		r *= 1.1
	return r


func is_clearing(x: float, z: float) -> bool:
	return (clearing.get_noise_2d(x, z) + 1.0) * 0.5 < 0.17


func run() -> void:
	var started := Time.get_ticks_msec()
	rng.seed = Rules.SEED
	clearing.seed = Rules.SEED
	clearing.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	clearing.frequency = 1.0 / 38.0
	clearing.fractal_octaves = 2
	atlas = ForestAtlas.load_default()
	terrain = ForestTerrain.new(atlas)
	terrain.read_analytic()
	terrain.bake()
	masks = ForestMasks.MaskSet.new(8.0)
	for mask in atlas.static_masks():
		masks.add(mask)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	print("LAYOUT terrain+masks ready ms=", Time.get_ticks_msec() - started)

	# 1. Tree slots ------------------------------------------------------------------------
	var cells: Array = []
	var span := int(EXTENT * 2.0)
	for j in span:
		for i in span:
			cells.append(Vector2i(i, j))
	_shuffle(cells)
	var slots: Array = []            # [x, z, r]
	var slot_grid := {}
	for pass_index in 2:
		for cell: Vector2i in cells:
			var x := -EXTENT + cell.x + rng.randf()
			var z := -EXTENT + cell.y + rng.randf()
			if is_clearing(x, z) or blocked_exact(x, z, true) or not ground_ok(x, z, true):
				continue
			var r := spacing_at(x, z) * (1.0 if pass_index == 0 else 0.94)
			var ok := true
			for other in near_points(x, z, r + 1.0, slot_grid, slots):
				var limit: float = (r + float(other[2])) * 0.5
				if Vector2(x - other[0], z - other[1]).length_squared() < limit * limit:
					ok = false
					break
			if ok:
				insert(slot_grid, slots, [x, z, r])
	print("LAYOUT slots=", slots.size(), " ms=", Time.get_ticks_msec() - started)

	# 2. Resource remap --------------------------------------------------------------------
	var outer: Array = []
	for tree in data.woods:
		var p: Array = tree.p
		if maxf(absf(float(p[0])), absf(float(p[2]))) > CORE:
			outer.append(tree)
	outer.sort_custom(func(a, b): return String(a.id).naturalnocasecmp_to(String(b.id)) < 0)
	var pairs: Array = []
	for t in outer.size():
		var tx := float(outer[t].p[0])
		var tz := float(outer[t].p[2])
		for gz in range(floori((tz - Rules.MAX_SLOT_DISPLACEMENT) / HASH), floori((tz + Rules.MAX_SLOT_DISPLACEMENT) / HASH) + 1):
			for gx in range(floori((tx - Rules.MAX_SLOT_DISPLACEMENT) / HASH), floori((tx + Rules.MAX_SLOT_DISPLACEMENT) / HASH) + 1):
				for s in slot_grid.get(Vector2i(gx, gz), PackedInt32Array()):
					var d := Vector2(tx - slots[s][0], tz - slots[s][1]).length()
					if d <= Rules.MAX_SLOT_DISPLACEMENT:
						pairs.append([d, t, s])
	pairs.sort_custom(func(a, b):
		if a[0] != b[0]:
			return a[0] < b[0]
		if a[1] != b[1]:
			return a[1] < b[1]
		return a[2] < b[2])
	var tree_slot := {}
	var slot_owner := {}
	for pair in pairs:
		if tree_slot.has(pair[1]) or slot_owner.has(pair[2]):
			continue
		tree_slot[pair[1]] = pair[2]
		slot_owner[pair[2]] = pair[1]
	var remap := {}
	var placed: Array = []           # forced placements [x, z, r]
	var placed_grid := {}
	var reasons := {"slot": 0, "mask_push": 0, "jitter": 0, "kept": 0}
	var displacements := PackedFloat32Array()
	for t in outer.size():
		var tree: Dictionary = outer[t]
		var tx := float(tree.p[0])
		var tz := float(tree.p[2])
		if tree_slot.has(t):
			var s: int = tree_slot[t]
			remap[tree.id] = [snappedf(slots[s][0], 0.01), snappedf(slots[s][1], 0.01), 0]
			reasons.slot += 1
			displacements.append(Vector2(tx - slots[s][0], tz - slots[s][1]).length())
	for t in outer.size():
		if tree_slot.has(t):
			continue
		var tree: Dictionary = outer[t]
		var tx := float(tree.p[0])
		var tz := float(tree.p[2])
		var in_mask := blocked_exact(tx, tz, true) and maxf(absf(tx), absf(tz)) >= CORE + 0.8
		var start_radius := 0.5 if in_mask else 1.0
		var found := Vector2.INF
		var radius := start_radius
		var angle0 := rng.randf() * TAU
		while radius <= 14.0 and found == Vector2.INF:
			for k in 16:
				var angle := angle0 + TAU * k / 16.0
				var x := tx + cos(angle) * radius
				var z := tz + sin(angle) * radius
				if blocked_exact(x, z, true) or not ground_ok(x, z, true):
					continue
				var free := true
				for other in near_points(x, z, Rules.MIN_TREE_GAP + 1.0, slot_grid, slots) + near_points(x, z, Rules.MIN_TREE_GAP + 1.0, placed_grid, placed):
					if Vector2(x - other[0], z - other[1]).length() < Rules.MIN_TREE_GAP:
						free = false
						break
				if free:
					found = Vector2(x, z)
					break
			radius += 0.5
			if not in_mask and radius > 3.0:
				break
		var reason := 1 if in_mask else 2
		if found == Vector2.INF:
			# Keep near the old spot but always off the old spiral point.
			var angle := rng.randf() * TAU
			found = Vector2(tx + cos(angle) * 0.9, tz + sin(angle) * 0.9)
			reason = 3
		insert(placed_grid, placed, [found.x, found.y, Rules.MIN_TREE_GAP])
		remap[tree.id] = [snappedf(found.x, 0.01), snappedf(found.y, 0.01), reason]
		reasons[["slot", "mask_push", "jitter", "kept"][reason]] += 1
		displacements.append(Vector2(tx - found.x, tz - found.y).length())
	print("LAYOUT remap ", reasons, " ms=", Time.get_ticks_msec() - started)

	# 3. Ambient trees ---------------------------------------------------------------------
	var trees: Array = []
	var species_count := {}
	for s in slots.size():
		if slot_owner.has(s):
			continue
		var x: float = slots[s][0]
		var z: float = slots[s][1]
		var weights: PackedFloat32Array = atlas.biome_weights(x, z)
		var biome := Rules.pick_index(Array(weights), rng.randf())
		var species := Rules.pick_weighted(Rules.BIOME_MIX[biome], rng.randf())
		var bank: float = atlas.river_bank_distance(x, z)
		if bank < 7.0 and rng.randf() < 0.75:
			species = Rules.WILLOW if rng.randf() < 0.6 else Rules.BIRCH
		var scale_range: Array = Rules.SPECIES_SCALE[species]
		var scale := lerpf(scale_range[0], scale_range[1], rng.randf())
		if biome == 7 and species == Rules.PINE:
			scale *= 1.15
		trees.append([snappedf(x, 0.01), snappedf(z, 0.01), species, 1 + rng.randi() % 3,
			snappedf(rng.randf() * 360.0, 0.1), snappedf(scale, 0.001), biome])
		species_count[Rules.SPECIES[species]] = species_count.get(Rules.SPECIES[species], 0) + 1
	print("LAYOUT ambient trees=", trees.size(), " ", species_count)

	# 4. Understory ------------------------------------------------------------------------
	var all_trees: Array = []
	var all_tree_grid := {}
	for s in slots.size():
		insert(all_tree_grid, all_trees, [slots[s][0], slots[s][1], 1.0])
	for entry in placed:
		insert(all_tree_grid, all_trees, [entry[0], entry[1], 1.0])
	var under: Array = []
	var under_grid := {}
	var trunks: Array = []
	var trunk_grid := {}
	_shuffle(cells)
	var kinds_count := {}
	for cell: Vector2i in cells:
		var x := -EXTENT + cell.x + rng.randf()
		var z := -EXTENT + cell.y + rng.randf()
		if maxf(absf(x), absf(z)) < CORE + 0.3:
			continue
		var weights: PackedFloat32Array = atlas.biome_weights(x, z)
		var biome := Rules.pick_index(Array(weights), rng.randf())
		var h: float = terrain.ground_height(x, z)
		var slope: float = terrain.slope_degrees(x, z)
		var bank: float = atlas.river_bank_distance(x, z)
		var kind := Rules.pick_index(Rules.BIOME_UNDERSTORY[biome], rng.randf())
		var reed_zone := h > -1.25 and h < -0.05 and slope < 38.0
		if reed_zone:
			kind = 1 if rng.randf() < 0.85 else 3
		elif h < -0.3 or slope > 34.0:
			continue
		elif kind == 1:
			kind = 0
		if bank > 12.0 and kind == 1:
			kind = 0
		var r: float = 3.1 / float(Rules.BIOME_UNDERSTORY_DENSITY[biome])
		if is_clearing(x, z):
			r *= 1.6
		if blocked_exact(x, z, false):
			continue
		var ok := true
		for other in near_points(x, z, r + 1.0, under_grid, under):
			if Vector2(x - other[0], z - other[1]).length() < r:
				ok = false
				break
		if not ok:
			continue
		var trunk_gap := 1.0 if kind != 4 else 2.6
		for other in near_points(x, z, trunk_gap + 0.5, all_tree_grid, all_trees):
			if Vector2(x - other[0], z - other[1]).length() < trunk_gap:
				ok = false
				break
		if not ok:
			continue
		if kind == 4:
			for other in near_points(x, z, 9.0, trunk_grid, trunks):
				if Vector2(x - other[0], z - other[1]).length() < 9.0:
					ok = false
					break
			if not ok:
				kind = 0
			else:
				insert(trunk_grid, trunks, [x, z, 0.0])
		var scale := lerpf(0.8, 1.25, rng.randf())
		insert(under_grid, under, [snappedf(x, 0.01), snappedf(z, 0.01), r, kind, 1 + rng.randi() % 3,
			snappedf(rng.randf() * 360.0, 0.1), snappedf(scale, 0.001)])
		kinds_count[Rules.UNDERSTORY[kind]] = kinds_count.get(Rules.UNDERSTORY[kind], 0) + 1
	var understory: Array = []
	for item in under:
		understory.append([item[0], item[1], item[3], item[4], item[5], item[6]])
	print("LAYOUT understory=", understory.size(), " ", kinds_count)

	# 5. Inner understory near inner trees (runtime filters plots/roads/buildings again) ----
	var reserve_rects: Array = []
	for mask in atlas.reserve_masks:
		if String(mask.get("type", "")) == "box" and String(mask.get("id", "")) != "preserve_existing_core":
			reserve_rects.append(Rect2(float(mask.minX), float(mask.minZ), float(mask.maxX) - float(mask.minX), float(mask.maxZ) - float(mask.minZ)))
	for plot in data.legacyPlots:
		reserve_rects.append(Rect2(float(plot.x) - 6.7, float(plot.z) - 6.7, 13.4, 13.4))
	var inner_trees: Array = []
	var inner_grid := {}
	for tree in data.woods:
		var p: Array = tree.p
		if maxf(absf(float(p[0])), absf(float(p[2]))) <= CORE:
			insert(inner_grid, inner_trees, [float(p[0]), float(p[2]), 1.0])
	var inner_under: Array = []
	var inner_under_grid := {}
	for tree in inner_trees:
		var count := rng.randi() % 3
		for k in count:
			var angle := rng.randf() * TAU
			var distance := lerpf(1.7, 3.6, rng.randf())
			var x: float = tree[0] + cos(angle) * distance
			var z: float = tree[1] + sin(angle) * distance
			if maxf(absf(x), absf(z)) > CORE - 0.5:
				continue
			var blocked := false
			for rect: Rect2 in reserve_rects:
				if rect.grow(0.6).has_point(Vector2(x, z)):
					blocked = true
					break
			if blocked:
				continue
			for road in data.cityRoads:
				var a := Vector2(float(road[0][0]), float(road[0][1]))
				var b := Vector2(float(road[1][0]), float(road[1][1]))
				if ForestMasks.segment_distance(Vector2(x, z), a, b) < 1.8:
					blocked = true
					break
			if blocked or terrain.ground_height(x, z) < -0.3 or terrain.slope_degrees(x, z) > 30.0:
				continue
			var ok := true
			for other in near_points(x, z, 3.0, inner_grid, inner_trees):
				if Vector2(x - other[0], z - other[1]).length() < 1.2:
					ok = false
					break
			for other in near_points(x, z, 3.0, inner_under_grid, inner_under):
				if Vector2(x - other[0], z - other[1]).length() < 2.2:
					ok = false
					break
			if not ok:
				continue
			var kind := Rules.pick_index([0.55, 0.0, 0.33, 0.12, 0.0, 0.0], rng.randf())
			insert(inner_under_grid, inner_under, [snappedf(x, 0.01), snappedf(z, 0.01), kind, 1 + rng.randi() % 3,
				snappedf(rng.randf() * 360.0, 0.1), snappedf(lerpf(0.75, 1.1, rng.randf()), 0.001)])
	print("LAYOUT inner understory=", inner_under.size())

	displacements.sort()
	var result := {
		"schemaVersion": 1, "layoutId": Rules.LAYOUT_ID, "layoutVersion": Rules.LAYOUT_VERSION,
		"atlasId": atlas.atlas_id, "seed": Rules.SEED, "terrainVersion": ForestTerrain.TERRAIN_VERSION,
		"generator": "res://src/forest_rescue/world/tools/build_forest_layout.gd",
		"woodsCount": data.woods.size(), "outerResourceTrees": outer.size(),
		"species": Rules.SPECIES, "understoryKinds": Rules.UNDERSTORY,
		"remapReasonCodes": ["slot", "mask_push", "jitter", "kept_offset"],
		"remapStats": {"reasons": reasons, "displacementMedian": displacements[displacements.size() / 2],
			"displacementP95": displacements[int(displacements.size() * 0.95)], "displacementMax": displacements[-1],
			"maxSlotDisplacement": Rules.MAX_SLOT_DISPLACEMENT},
		"format": {"trees": "[x, z, speciesIndex, variant(1..3), yawDeg, scale, biomeIndex]",
			"resourceRemap": "{id: [x, z, reasonCode]} for every outer resource tree; inner trees keep data.woods[].p",
			"understory": "[x, z, kindIndex, variant, yawDeg, scale]"},
		"trees": trees, "resourceRemap": remap, "understory": understory, "innerUnderstory": inner_under}
	var file := FileAccess.open(Rules.LAYOUT_PATH, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "", false))
	file.close()
	print("LAYOUT_DONE trees=", trees.size(), " remap=", remap.size(), " understory=", understory.size(),
		" inner=", inner_under.size(), " ms=", Time.get_ticks_msec() - started)
	quit()


func _shuffle(array: Array) -> void:
	for i in range(array.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var tmp = array[i]
		array[i] = array[j]
		array[j] = tmp
