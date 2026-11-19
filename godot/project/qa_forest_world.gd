extends SceneTree
## Headless QA for the «Лес потерянных» world layer.
##   godot --headless --path godot/project -s qa_forest_world.gd
## Builds the city Landscape directly (flag ON and OFF), then checks resource-id preservation,
## masks, layout/remap invariants, chunk selection + pinning, fog bit layout (fog.mjs), locked
## projection, heights continuity and the WORLD_API surface.

const ForestFlags = preload("res://src/forest_rescue/world/forest_flags.gd")
const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")
const ForestFog = preload("res://src/forest_rescue/world/forest_fog.gd")
const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")

var failures: Array[String] = []
var checks := 0
var notes: Dictionary = {}


func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error("QA_FOREST_WORLD FAIL: " + detail)


func _initialize() -> void:
	call_deferred("run")


func build_city(data: Dictionary, flag_on: bool) -> Node3D:
	ForestFlags.set_override(1 if flag_on else 0)
	var stage: Node3D = load("res://src/landscape.gd").new()
	root.add_child(stage)
	await stage.setup(data, data.demo, "city", {})
	return stage


func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	# ---- Rollback: flag OFF builds the legacy forest and no world layer -----------------------
	var legacy: Node3D = await build_city(data, false)
	check(legacy.forest_world == null, "flag OFF must not create forest_world")
	var legacy_ids := {}
	for tree in legacy.selectable_trees:
		legacy_ids[tree.id] = tree
	var legacy_batches: int = legacy.render_batches.size()
	legacy.free()
	# ---- Flag ON -----------------------------------------------------------------------------
	var stage: Node3D = await build_city(data, true)
	var world: Node3D = stage.forest_world
	check(world != null, "flag ON must create stage.forest_world")
	if world == null:
		finish()
		return
	# WORLD_API surface (exact names).
	for method in ["apply_adventure", "is_locked", "height_at", "ground_point", "site_anchor", "poi_position",
			"route_points", "actors_root", "props_root", "fog_cleared_at", "play_entrance_reveal", "set_reduced_motion",
			"pin_area", "unpin_area", "focus_bounds", "set_boss_arena_state", "set_site_post_state", "perf_snapshot"]:
		check(world.has_method(method), "WORLD_API method missing: " + method)
	check(world.has_signal("world_ready") and world.has_signal("fog_reveal_finished"), "WORLD_API signals missing")
	# ---- Resource trees: every id kept, same felled/pickable set, remapped outer positions ----
	var ids := {}
	for tree in stage.selectable_trees:
		ids[tree.id] = tree
	check(ids.size() == legacy_ids.size(), "pickable resource ids changed: %d vs legacy %d" % [ids.size(), legacy_ids.size()])
	var missing := 0
	var changed_fields := 0
	var inner_moved := 0
	var outer_displacements := PackedFloat32Array()
	var inner_jitter := PackedFloat32Array()
	var on_old_point := 0
	for id in legacy_ids:
		if not ids.has(id):
			missing += 1
			continue
		var a: Dictionary = legacy_ids[id]
		var b: Dictionary = ids[id]
		for field in ["name", "wood", "xp", "durationMs", "level", "variant", "village"]:
			if a.get(field) != b.get(field):
				changed_fields += 1
		var old := Vector2(float(a.p[0]), float(a.p[2]))
		var now := Vector2(float(b.p[0]), float(b.p[2]))
		if maxf(absf(old.x), absf(old.y)) <= 56.0:
			# layout v2: inner (±56) trees are jittered off the spiral rows by ≤ 3.5 m, same id
			inner_jitter.append(old.distance_to(now))
			if old.distance_to(now) > Rules.MAX_INNER_JITTER + 0.01:
				inner_moved += 1
		else:
			outer_displacements.append(old.distance_to(now))
			if old.distance_to(now) < 0.5:
				on_old_point += 1
		var visual: Vector3 = world.resource_tree_position(id)
		check(Vector2(visual.x, visual.z).distance_to(now) < 0.01, "pick position != rendered position for " + id)
	check(missing == 0, "resource ids missing after remap: %d" % missing)
	check(changed_fields == 0, "resource tree fields changed: %d" % changed_fields)
	check(inner_moved == 0, "inner (±56) resource trees moved more than %.1f m: %d" % [Rules.MAX_INNER_JITTER, inner_moved])
	inner_jitter.sort()
	notes.inner_jitter = {"count": inner_jitter.size(), "median_m": inner_jitter[inner_jitter.size() / 2] if not inner_jitter.is_empty() else 0.0,
		"max_m": inner_jitter[-1] if not inner_jitter.is_empty() else 0.0}
	outer_displacements.sort()
	var n := outer_displacements.size()
	check(n > 1000, "too few outer resource trees checked: %d" % n)
	var off_rows := 1.0 - float(on_old_point) / maxf(1.0, n)
	check(off_rows >= 0.9, "old spiral rows: only %.1f%% of outer trees moved ≥0.5 m" % (off_rows * 100.0))
	notes.remap = {"outer": n, "median_m": outer_displacements[n / 2], "p95_m": outer_displacements[int(n * 0.95)],
		"max_m": outer_displacements[n - 1], "moved_ge_0_5m_pct": off_rows * 100.0}
	# Spiral-row metric: nearest-neighbour regularity of outer instances vs. the legacy layout.
	var layout: Dictionary = world.layout
	check(layout.get("layoutId", "") == Rules.LAYOUT_ID and int(layout.get("layoutVersion", 0)) == Rules.LAYOUT_VERSION, "layout id/version mismatch")
	check(layout.resourceRemap.size() == n, "remap table must cover every outer resource id (%d vs %d)" % [layout.resourceRemap.size(), n])
	# ---- Felled → stump at the remapped position, still pickable -----------------------------
	var some_outer := ""
	for id in layout.resourceRemap:
		if ids.has(id):
			some_outer = id
			break
	var city: Dictionary = data.demo.city.duplicate(true)
	city.progress.felled = [some_outer]
	stage.build_forest(city, [])
	var still := false
	for tree in stage.selectable_trees:
		if tree.id == some_outer:
			still = true
			check(Vector2(float(tree.p[0]), float(tree.p[2])).distance_to(world.remap[some_outer]) < 0.01, "felled tree pick position not remapped")
	check(still, "felled tree no longer pickable (needs 'Подготовить участок')")
	var standing := 0
	for cell in stage.standing_tree_cells:
		standing += stage.standing_tree_cells[cell].size()
	check(standing == stage.selectable_trees.size() - 1, "standing_tree_cells must exclude exactly the felled tree")
	stage.build_forest(data.demo.city, [])
	# ---- Masks: no ambient trees/understory inside reserves, routes (crown), glades, arena ----
	var masks = world.masks
	var bad_trees := 0
	for item in layout.trees:
		var x := float(item[0])
		var z := float(item[1])
		if maxf(absf(x), absf(z)) <= 56.0:
			bad_trees += 1
			continue
		var hit: Dictionary = world.atlas.nearest_route(x, z)
		# v2 rule: trunk ≥ route clearance + 1.4 m + 45 % of the crown (crowns may overhang a bit)
		var crown: float = world.TREE_CROWN[int(item[2])] * float(item[5])
		if not hit.is_empty() and hit.distance < 3.8 + Rules.ROUTE_TRUNK_MARGIN + crown * 0.45 - 0.05:
			bad_trees += 1
		for site in world.atlas.sites:
			if Vector2(x, z).distance_to(Vector2(site.center.x, site.center.z)) < site.radius + Rules.GLADE_TRUNK_MARGIN + crown * 0.4 - 0.05:
				bad_trees += 1
		if Vector2(x, z).distance_to(Vector2(world.atlas.arena_center.x, world.atlas.arena_center.z)) < 17.0:
			bad_trees += 1
		if world.atlas.river_bank_distance(x, z) < -0.5:
			bad_trees += 1
	check(bad_trees == 0, "ambient trees inside reserve/route-crown/glade/arena/river masks: %d" % bad_trees)
	var bad_under := 0
	for item in layout.understory:
		var x := float(item[0])
		var z := float(item[1])
		var mask: Dictionary = masks.hit(x, z, 0.0, ["core", "route", "glade", "arena", "bridge", "reserve"])
		if not mask.is_empty():
			bad_under += 1
	check(bad_under == 0, "understory inside masks: %d" % bad_under)
	var remap_in_mask := 0
	for id in layout.resourceRemap:
		var e: Array = layout.resourceRemap[id]
		var mask: Dictionary = masks.hit(float(e[0]), float(e[1]), 0.0, ["route", "glade", "arena", "bridge"])
		if not mask.is_empty():
			remap_in_mask += 1
	check(remap_in_mask == 0, "remapped resource trees still inside route/glade/arena/bridge masks: %d" % remap_in_mask)
	# ---- Chunk selection + pinning (port of selectChunks) ------------------------------------
	var all := ForestMasks.all_chunks()
	check(all.size() == 16 and all[0].id == "lf_chunk_0_0" and all[15].id == "lf_chunk_3_3", "16 chunks lf_chunk_X_Z")
	check(ForestMasks.chunk_id_at(-112, -112) == "lf_chunk_0_0" and ForestMasks.chunk_id_at(111.9, 111.9) == "lf_chunk_3_3" \
		and ForestMasks.chunk_id_at(112, 0) == "", "chunk_id_at bounds")
	var sel := ForestMasks.select_chunks(Vector2(0, 0), 65.0)
	check(sel.full.size() == 4 and sel.proxy.size() <= 8 and sel.overflow == 0, "budget 4 full / ≤8 proxy")
	var pins := [Vector2(-100, -100), Vector2(100, -100), Vector2(-100, 100), Vector2(100, 100), Vector2(0, 0)]
	sel = ForestMasks.select_chunks(Vector2(0, 0), 65.0, pins)
	for p in pins:
		check(sel.full.has(ForestMasks.chunk_id_at(p.x, p.y)), "pinned chunk evicted " + str(p))
	check(sel.overflow == sel.full.size() - 4 and sel.overflow > 0, "pin overflow reported, not evicted")
	sel = ForestMasks.select_chunks(Vector2(0, 0), 65.0, [], func(id): return id == "lf_chunk_1_1")
	check(sel.fogOnly.size() > 0 and not sel.full.has("lf_chunk_0_0"), "unexplored chunks are fogOnly")
	world.pin_area("qa", Vector3(-95, 0, 95), 6.0)
	check(world.perf_snapshot().full_chunks >= 1 and world.last_cull.select.full.has("lf_chunk_0_3"), "pin_area keeps its chunk full")
	world.unpin_area("qa")
	# ---- Fog bit layout (fog.mjs): bit i = row*56+col, LSB first, 392 bytes / 524 chars -------
	var town := ForestFog.default_town_bits()
	check(town.size() == 392 and ForestFog.count_bits(town) == 28 * 28, "createFogState: 28×28 town cells")
	check(Marshalls.raw_to_base64(town).length() == 524, "base64 length 524")
	var probe := PackedByteArray()
	probe.resize(392)
	ForestFog.set_bit(probe, 3, 2)          # index 2*56+3 = 115 → byte 14, bit 3
	check(probe[14] == 8 and ForestFog.count_bits(probe) == 1, "bit layout row*56+col LSB-first")
	var cell := ForestFog.cell_of(-112 + 3 * 4 + 1, -112 + 2 * 4 + 1)
	check(cell == Vector2i(3, 2), "cellAt(x,z) = floor((x+112)/4)")
	check(ForestFog.decode_base64(Marshalls.raw_to_base64(probe)) == probe, "decode round trip")
	check(ForestFog.decode_base64("AAAA").is_empty() and ForestFog.decode_base64("not base64!").is_empty(), "invalid fog encodings rejected")
	var corridor := ForestFog.corridor_bits(Vector2(-8, -55), Vector2(-12, -60), 3.0)
	var outside := 0
	for row in 56:
		for column in 56:
			if ForestFog.bit(corridor, column, row) and not ForestFog.bit(town, column, row):
				outside += 1
	check(outside >= 1 and outside <= 4, "entrance corridor opens only a few cells beyond the town (%d)" % outside)
	# ---- Locked projection hides POIs; unlocking never clears the forest by itself ------------
	world.apply_adventure({})
	check(world.is_locked(), "no adventure → locked")
	for site in world.atlas.sites:
		check(not world.fog_cleared_at(site.center.x, site.center.z), "locked: site visible " + site.id)
	check(world.fog_cleared_at(0, 0) and world.fog_cleared_at(-50, 50), "town must stay clear while locked")
	var locked_adv := {"access": {"unlocked": false, "hallLevel": 2}, "fog": {"visibleBase64": Marshalls.raw_to_base64(town), "revision": 3},
		"intro": {"status": "pending"}, "pois": []}
	world.apply_adventure(locked_adv)
	check(world.is_locked() and not world.fog_cleared_at(-20, -65), "hall 2 → locked")
	var unlocked_bits := town.duplicate()
	for i in 392:
		unlocked_bits[i] = unlocked_bits[i] | corridor[i]
	var unlocked := {"access": {"unlocked": true, "hallLevel": 3}, "fog": {"visibleBase64": Marshalls.raw_to_base64(unlocked_bits), "revision": 4},
		"intro": {"status": "playing"}}
	world.set_reduced_motion(true)
	world.apply_adventure(unlocked)
	check(not world.is_locked(), "hall 3 → unlocked")
	check(not world.fog_cleared_at(-12, -60), "entrance corridor held until play_entrance_reveal")
	world.play_entrance_reveal(1200)
	check(world.fog_cleared_at(-12, -60), "entrance reveal opens the corridor")
	check(not world.fog_cleared_at(-43, -67), "unlock must not clear other forest cells")
	world.apply_adventure({"access": {"unlocked": true}, "fog": {"visibleBase64": "garbage", "revision": 5}})
	check(not world.fog_cleared_at(-12, -60) and world.fog_cleared_at(0, 0), "invalid projection fails closed to the town default")
	# ---- Heights: continuous along routes, flat pads, bridge deck --------------------------
	var worst_step := 0.0
	var worst_route := ""
	for route in world.atlas.routes:
		var pts: PackedVector3Array = world.route_points(route.id)
		for i in range(1, pts.size()):
			var a := pts[i - 1]
			var b := pts[i]
			for k in 5:
				var t0 := k / 5.0
				var t1 := (k + 1) / 5.0
				var p0 := a.lerp(b, t0)
				var p1 := a.lerp(b, t1)
				var step := absf(world.height_at(p1.x, p1.z) - world.height_at(p0.x, p0.z)) / maxf(0.01, Vector2(p1.x - p0.x, p1.z - p0.z).length())
				if step > worst_step:
					worst_step = step
					worst_route = route.id + " at " + str(p0)
	notes.max_route_slope = rad_to_deg(atan(worst_step))
	check(rad_to_deg(atan(worst_step)) < 25.0, "route height discontinuity/slope %.1f° on %s" % [rad_to_deg(atan(worst_step)), worst_route])
	for site in world.atlas.sites:
		var c: Vector3 = site.center
		var spread := 0.0
		var pad_y: float = world.height_at(c.x, c.z)
		for angle in 12:
			var q := Vector2(c.x, c.z) + Vector2(cos(angle * TAU / 12.0), sin(angle * TAU / 12.0)) * 6.0
			spread = maxf(spread, absf(world.height_at(q.x, q.y) - pad_y))
		check(spread < 0.15, "glade pad not flat: %s spread %.2f" % [site.id, spread])
	check(is_equal_approx(world.height_at(90.48, 20.0), 1.1), "bridge deck height 1.1")
	check(absf(world.terrain.ground_height(90.48, 20.0) - world.terrain.original_height(90.48, 20.0)) < 0.001, "river under the bridge untouched")
	var jumps := 0
	for i in 2000:
		var x := -110.0 + fmod(i * 7.31, 220.0)
		var z := -110.0 + fmod(i * 3.17, 220.0)
		var natural := absf(world.terrain.original_height(x + 0.2, z) - world.terrain.original_height(x, z))
		if absf(world.height_at(x + 0.2, z) - world.height_at(x, z)) > maxf(0.6, natural + 0.15) and not world.terrain.on_bridge_deck(x + 0.2, z):
			jumps += 1
			print("QA jump at ", x, ",", z, " h0=", world.height_at(x, z), " h1=", world.height_at(x + 0.2, z), " orig=", world.terrain.original_height(x, z), "/", world.terrain.original_height(x + 0.2, z))
	check(jumps == 0, "earthwork-induced height jumps > 0.6 m over 0.2 m: %d" % jumps)
	var anchor: Dictionary = world.site_anchor("lf_site_01")
	check(anchor.has_all(["center", "cage", "guardian", "artifact", "approach", "plate_left", "plate_right", "landmarks", "cage_yaw"]), "site_anchor keys")
	check(world.poi_position("lf_home_reception").distance_to(Vector3(-7, 0, -51)) < 10.0, "lf_home_reception position")
	check(world.poi_position("lf_site_03:cage") != Vector3.INF and world.poi_position("lf_key_05") != Vector3.INF, "poi target ids")
	check(world.focus_bounds() == Rect2(-112, -112, 224, 224), "focus_bounds")
	notes.perf = world.perf_snapshot()
	notes.legacy_batches = legacy_batches
	notes.kit = world.kit_status()
	stage.free()
	finish()


func finish() -> void:
	ForestFlags.set_override(-1)
	print("QA_FOREST_WORLD_NOTES ", JSON.stringify(notes))
	print("QA_FOREST_WORLD checks=", checks, " failures=", failures.size())
	for f in failures:
		print("  FAIL ", f)
	quit(0 if failures.is_empty() else 1)
