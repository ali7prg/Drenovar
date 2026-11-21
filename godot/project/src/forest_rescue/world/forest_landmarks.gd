extends Node3D
## Landmarks + boss arena dressing (landmarks v3 / arena modules). Nothing is invented here:
## every visual is a delivered GLB, picked up automatically (re-checked on every city build).
##
## Landmark GLBs: <id>.glb = LOD0 (+ <id>_cloth_LOD0 morph clip lf_banner_wind, + <id>_base
## painted ground patch), <id>_LOD1.glb / <id>_LOD2.glb (same origin). In the world the `_base`
## nodes are OFF (the terrain/paths provide the ground), cloth clips loop, every surface uses the
## painted kit material with k = 0.35 (meta paintedLightMix), LODs switch by the city zoom.
##
## Atlas v2 (art/01 masterplan, masterplan_inventory.json): every delivered landmark stands at
## its atlas mark (lf_mark_*), set back from the trail end that leads there (the mark node stays
## walkable) and facing it; validated against trails, glades, arena, bridge, core and the wet
## river channel (spiral search ≤ 24 m if blocked):
##   lf_env_bridge27m        (90.482, 0, 20) exactly, yaw 0 (long axis X, deck top local 1.1)
##   lf_env_ruined_watchpost lf_mark_ruined_arch (grove west, where three trails meet)
##   lf_env_standing_stones  lf_mark_standing_stones (the stone row the mare leads past)
##   lf_env_quarry_mine      lf_mark_quarry_mine (mine mouth at the end of the quarry spur)
##   lf_env_hunter_shelter   lf_mark_hunter_shelter (marsh / lake shore, two trails meet)
##   dead-tree set           lf_mark_dead_tree: arena pillar a/b + bones modules (the bare white
##                           tree itself is built by ForestWorld from kit pieces)
##   camps                   one per glade (12 sites + lf_glade_el), styled per glade (CAMP_STYLES)
##   arena (assembled)       centred on the atlas arena, yaw = atlas entranceYawDeg (gap toward
##                           the arena trail); whole LOD files by zoom (<=34 / <=85 / beyond)

const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const LANDMARK_DIR := "res://assets/forest_rescue/landmarks/"
const ARENA_DIR := "res://assets/forest_rescue/arena/"
const PROPS_DIR := "res://assets/forest_rescue/props/"
const LIGHT_MIX := 0.35

const MARK_LANDMARKS := [
	{"id": "lf_env_ruined_watchpost", "mark": "lf_mark_ruined_arch", "back": 6.5, "footprint": 5.0},
	{"id": "lf_env_standing_stones", "mark": "lf_mark_standing_stones", "back": 0.0, "footprint": 4.4, "face_node": "lf_junction_stones"},
	{"id": "lf_env_quarry_mine", "mark": "lf_mark_quarry_mine", "back": 6.0, "footprint": 6.0},
	{"id": "lf_env_hunter_shelter", "mark": "lf_mark_hunter_shelter", "back": 5.2, "footprint": 4.6},
]
## Dead-tree set around lf_mark_dead_tree (offsets in the frame facing the trail end: +Z toward it).
const DEAD_TREE_BACK := 3.0
const DEAD_TREE_SET := [
	{"id": "lf_arena_pillar_a", "offset": Vector2(-3.6, 0.8), "yaw": 20.0, "scale": 0.72, "footprint": 1.4},
	{"id": "lf_arena_pillar_b", "offset": Vector2(3.4, -1.2), "yaw": -35.0, "scale": 0.66, "footprint": 1.4},
	{"id": "lf_arena_bones", "offset": Vector2(1.2, 2.6), "yaw": 64.0, "scale": 0.8, "footprint": 1.8},
]
const CAMP := {"id": "lf_env_camp_props", "footprint": 3.4, "distance": 10.2}
## art/01 camps (masterplan_inventory.json per-cage notes; no two neighbouring glades alike).
## main: camp = lf_env_camp_props (red tarp, fire ring, crates, lantern), frame = the same without
## its tarp (bare drying poles), fire / fire_bench = the fire ring (+ the log bench) cut out of it.
## extras [kind, offset (m, camp frame: +Z toward the glade centre), yaw°]: supplies:<items>
## (lf_props_supplies nodes), lantern, rope, signpost, wall (stone wall), fence (split rails),
## hide_rack, drying_frame, lean_to; an extra that would touch a trail, a gameplay anchor or the
## water is mirrored, else dropped.
const CAMP_STYLES := {
	"lf_site_01": {"main": "camp", "mirror": false, "yaw": 0.0, "extras": [["supplies:crate_open,sacks", Vector2(4.3, 0.4), 20.0], ["lantern", Vector2(-3.9, 1.8), 0.0]]},
	"lf_site_02": {"main": "camp", "mirror": true, "yaw": 18.0, "extras": [["wall", Vector2(-4.4, -0.6), 72.0], ["rope", Vector2(3.9, 1.6), 0.0]]},
	"lf_site_03": {"main": "camp", "mirror": false, "yaw": -22.0, "extras": [["fence", Vector2(4.6, -0.8), 95.0], ["supplies:chest,blankets", Vector2(-4.4, 0.8), -15.0]]},
	"lf_site_04": {"main": "fire_bench", "mirror": false, "yaw": 0.0, "extras": [["fence", Vector2(-3.4, -1.6), 70.0], ["signpost", Vector2(2.8, -1.2), 30.0], ["supplies:crate_closed", Vector2(2.4, 1.4), 10.0]]},
	"lf_site_05": {"main": "camp", "mirror": true, "yaw": 12.0, "extras": [["supplies:crate_closed,crate_open,arrows", Vector2(-4.4, 0.6), 35.0], ["rope", Vector2(4.0, 0.9), 0.0], ["lantern", Vector2(3.6, -1.9), 0.0]]},
	"lf_site_06": {"main": "frame", "mirror": false, "yaw": -30.0, "extras": [["fence", Vector2(-4.5, 0.0), 100.0], ["supplies:sacks,bread", Vector2(4.2, 0.9), -20.0]]},
	"lf_site_07": {"main": "fire", "mirror": false, "yaw": 0.0, "extras": [["hide_rack", Vector2(2.6, -0.8), -25.0], ["rope", Vector2(-2.2, 0.6), 0.0]]},
	"lf_site_08": {"main": "fire_bench", "mirror": true, "yaw": 25.0, "extras": [["hide_rack", Vector2(-1.8, -2.4), 40.0], ["supplies:sacks", Vector2(2.6, 0.6), 0.0]]},
	"lf_site_09": {"main": "fire", "mirror": false, "yaw": 0.0, "extras": [["supplies:crate_closed,blankets", Vector2(-2.6, -0.4), 15.0], ["lantern", Vector2(1.9, -1.4), 0.0]]},
	"lf_site_10": {"main": "frame", "mirror": true, "yaw": 15.0, "extras": [["drying_frame", Vector2(-4.6, 0.4), 80.0], ["supplies:arrows", Vector2(4.1, 1.0), 0.0]]},
	"lf_site_11": {"main": "fire_bench", "mirror": false, "yaw": -12.0, "extras": [["drying_frame", Vector2(2.9, -1.6), -40.0], ["rope", Vector2(-2.6, -1.2), 0.0]]},
	"lf_glade_el": {"main": "fire", "mirror": false, "yaw": 0.0, "extras": [["lean_to", Vector2(0.4, -2.9), 0.0], ["supplies:chest", Vector2(2.7, 0.2), -30.0]]},
	"lf_site_12": {"main": "fire_bench", "mirror": true, "yaw": 8.0, "extras": [["lean_to", Vector2(-0.6, -3.1), 10.0], ["lantern", Vector2(2.3, -0.9), 0.0], ["signpost", Vector2(-3.4, 0.9), -20.0]]},
}
const PIECE_FOOTPRINT := {"camp": 3.4, "frame": 3.4, "fire": 1.3, "fire_bench": 2.1, "supplies": 1.6, "lantern": 0.4,
	"rope": 0.6, "signpost": 0.7, "wall": 1.8, "fence": 2.4, "hide_rack": 1.3, "drying_frame": 1.4, "lean_to": 1.8}
## Fire ring (+ log bench) inside lf_env_camp_props (model space): kept triangles by centroid.
const FIRE_CENTER := Vector2(-0.5, 1.05)
const FIRE_RADIUS := 1.05
const BENCH_RECT := Rect2(-2.8, 0.75, 1.4, 0.9)

var atlas: RefCounted
var placements: Array = []        # [{id, position: Vector3, yaw, footprint, kind, pad, ...}]
var missing: Dictionary = {}
var loaded: Dictionary = {}
var arena_state := "locked"
var arena_root: Node3D
var site_states: Dictionary = {}
var items: Array = []             # [{node, lods: [Node3D×3], players: [[AnimationPlayer]×3], center: Vector2, radius, lod}]
var arena_parts: Array = []       # [MeshInstance3D, Mesh LOD0, Mesh LOD1]
var arena_lod := -1
var tris_by_lod := {}             # placement id -> [tris LOD0, LOD1, LOD2]
var dead_tree_spot := Vector2.INF # where ForestWorld plants the bare white tree
var _cut_cache: Dictionary = {}   # "fire|bench:lod" -> [[Mesh, Transform3D, material overrides]]


## Computes all placements (static, deterministic). height_fn: Callable(x, z) -> float.
func plan(forest_atlas: RefCounted, masks: RefCounted, height_fn: Callable) -> void:
	atlas = forest_atlas
	placements.clear()
	placements.append({"id": "lf_env_bridge27m", "position": Vector3(atlas.BRIDGE_CENTER.x, 0.0, atlas.BRIDGE_CENTER.z),
		"yaw": 0.0, "footprint": 0.0, "kind": "bridge", "pad": false})
	for spec in MARK_LANDMARKS:
		var mark: Vector2 = _node_xz(spec.mark)
		if mark == Vector2.INF:
			continue
		var away := _away_from_trails(spec.mark, mark)
		var preferred: Vector2 = mark + away * float(spec.back)
		var face: Vector2 = _node_xz(spec.face_node) if spec.has("face_node") else mark
		var spot := find_spot(preferred, float(spec.footprint), masks)
		var dir: Vector2 = face - spot
		if dir.length() < 0.5:
			dir = -away
		placements.append({"id": spec.id, "position": Vector3(spot.x, 0.0, spot.y), "yaw": atan2(dir.x, dir.y),
			"footprint": spec.footprint, "kind": "landmark", "pad": true, "mark": spec.mark})
	# Dead-tree set: the tree stands DEAD_TREE_BACK beyond the end of the trail from glade 07.
	var dead: Vector2 = _node_xz("lf_mark_dead_tree")
	if dead != Vector2.INF:
		var away := _away_from_trails("lf_mark_dead_tree", dead)
		dead_tree_spot = dead + away * DEAD_TREE_BACK
		var basis_z := -away
		var basis_x := Vector2(basis_z.y, -basis_z.x)
		for spec in DEAD_TREE_SET:
			var p: Vector2 = dead_tree_spot + basis_x * spec.offset.x + basis_z * spec.offset.y
			if not valid_spot(p, float(spec.footprint), masks, true):
				continue
			placements.append({"id": spec.id, "position": Vector3(p.x, 0.0, p.y), "yaw": atan2(basis_z.x, basis_z.y) + deg_to_rad(spec.yaw),
				"footprint": spec.footprint, "kind": "landmark", "pad": false, "dir": ARENA_DIR, "scale": float(spec.scale)})
	# art/01: every glade has a camp next to its cage (+ the E-L glade without a cage), styled per
	# glade. The main piece stands at the clearing edge, as far as possible from the gameplay
	# anchors (cage, guardian, artifact, escort approach) and the trails (camera-far side preferred).
	var glades: Array = []
	for site in atlas.sites:
		glades.append(site)
	for glade in atlas.extra_glades:
		glades.append({"id": glade.id, "center": glade.center, "radius": glade.radius, "cage": Vector2.ZERO,
			"guardian": Vector2.ZERO, "artifact": Vector2.ZERO, "approach": Vector2.ZERO, "anchorless": true})
	for site in glades:
		var style: Dictionary = CAMP_STYLES.get(site.id, {"main": "camp", "mirror": false, "yaw": 0.0, "extras": []})
		var main_kind: String = style.main
		var main_fp: float = PIECE_FOOTPRINT[main_kind]
		var center := Vector2(site.center.x, site.center.z)
		var anchors: Array = [] if site.get("anchorless", false) else [site.cage, site.guardian, site.artifact, site.approach]
		var best := Vector2.INF
		var best_score := -INF
		var rings: Array = [2.5, 3.5, 4.5] if anchors.is_empty() else ([4.6, 5.6, 6.6] if main_fp < 2.5 else [6.2, 7.4, 8.8])
		for ring in rings:
			for k in 36:
				var angle := TAU * k / 36.0
				var p: Vector2 = center + Vector2(cos(angle), sin(angle)) * float(ring)
				if not camp_spot_ok(p, main_fp, site):
					continue
				var clearance := 6.0
				for anchor: Vector2 in anchors:
					clearance = minf(clearance, p.distance_to(center + anchor))
				var hit: Dictionary = atlas.nearest_route(p.x, p.y, false)
				var trail: float = minf(hit.get("distance", 12.0), 12.0)
				var score: float = minf(clearance, 6.0) * 1.6 + trail - float(ring) * 0.4
				score += 1.5 * Vector2(cos(angle), sin(angle)).dot(Vector2(-0.7071, -0.7071))
				if clearance < main_fp + 0.4:
					score -= 50.0
				if score > best_score:
					best_score = score
					best = p
		if best == Vector2.INF:
			continue
		var yaw := atan2(center.x - best.x, center.y - best.y) + deg_to_rad(float(style.get("yaw", 0.0)))
		var mirror: bool = style.get("mirror", false)
		placements.append({"id": CAMP.id, "position": Vector3(best.x, 0.0, best.y), "yaw": yaw, "footprint": main_fp,
			"kind": "camp", "site": site.id, "pad": main_fp >= 3.0, "piece": main_kind, "mirror": mirror})
		var fz := Vector2(sin(yaw), cos(yaw))          # camp frame +Z (model +Z) in world xz
		var fx := Vector2(fz.y, -fz.x)                 # camp frame +X
		for extra in style.get("extras", []):
			var kind: String = String(extra[0]).get_slice(":", 0)
			var fp: float = PIECE_FOOTPRINT.get(kind, 1.0)
			var offset: Vector2 = extra[1]
			if mirror:
				offset.x = -offset.x
			var placed := false
			for attempt in 2:
				var o := offset if attempt == 0 else Vector2(-offset.x, offset.y)
				var p: Vector2 = best + fx * o.x + fz * o.y
				if not _extra_ok(p, fp, site, anchors):
					continue
				var extra_yaw := yaw + deg_to_rad(float(extra[2])) * (-1.0 if mirror != (attempt == 1) else 1.0)
				placements.append({"id": _piece_asset(kind), "position": Vector3(p.x, 0.0, p.y), "yaw": extra_yaw,
					"footprint": fp, "kind": "camp_piece", "site": site.id, "pad": false, "piece": kind,
					"items": String(extra[0]).get_slice(":", 1) if String(extra[0]).contains(":") else ""})
				placed = true
				break
			if not placed:
				print("ForestLandmarks: camp extra %s dropped at %s" % [extra[0], site.id])
	for placement in placements:
		var p: Vector3 = placement.position
		if placement.kind != "bridge":
			placement.position.y = height_fn.call(p.x, p.z)


static func _piece_asset(kind: String) -> String:
	match kind:
		"supplies":
			return "lf_props_supplies"
		"lantern":
			return "lf_env_lantern"
		"rope":
			return "lf_env_rope_coil"
		"signpost":
			return "lf_env_signpost"
		"wall":
			return "lf_env_stone_wall"
		"lean_to":
			return "lf_env_platform"
	return "proc_" + kind


func _node_xz(id: String) -> Vector2:
	var node: Variant = atlas.landmark_by_id.get(id)
	if node is Dictionary:
		return Vector2(float(node.center.x), float(node.center.z))
	if atlas.site_by_id.has(id):
		var site: Dictionary = atlas.site_by_id[id]
		return Vector2(site.center.x, site.center.z)
	return Vector2.INF


## Unit direction pointing away from the trails that end at a node (mean of their arrival
## directions, measured ~6 m out along each trail).
func _away_from_trails(node_id: String, at: Vector2) -> Vector2:
	var sum := Vector2.ZERO
	for route in atlas.routes:
		var pts: PackedVector3Array = route.server_points
		if pts.size() < 2 or not (route.from == node_id or route.to == node_id):
			continue
		var start := 0 if route.from == node_id else pts.size() - 1
		var step := 1 if start == 0 else -1
		var i := start
		while i + step >= 0 and i + step < pts.size() and Vector2(pts[i].x, pts[i].z).distance_to(at) < 6.0:
			i += step
		var dir := Vector2(pts[i].x, pts[i].z) - at
		if dir.length() > 0.1:
			sum += dir.normalized()
	if sum.length() < 0.05:
		return Vector2(-0.7071, -0.7071)        # camera-far side
	return -sum.normalized()


func valid_spot(p: Vector2, footprint: float, masks: RefCounted, camp := false) -> bool:
	if maxf(absf(p.x), absf(p.y)) < 56.0 + footprint or maxf(absf(p.x), absf(p.y)) > 110.0 - footprint * 0.5:
		return false
	if atlas.river_bank_distance(p.x, p.y) < footprint + 2.0:
		return false
	var hit: Dictionary = atlas.nearest_route(p.x, p.y, false)
	if not hit.is_empty() and hit.distance < footprint + 1.8:
		return false
	for site in atlas.sites:
		var limit: float = site.radius + (0.8 if camp else 2.0) + footprint
		if p.distance_to(Vector2(site.center.x, site.center.z)) < limit:
			return false
	for glade in atlas.extra_glades:
		if p.distance_to(Vector2(glade.center.x, glade.center.z)) < glade.radius + 1.0 + footprint:
			return false
	if p.distance_to(Vector2(atlas.arena_center.x, atlas.arena_center.z)) < atlas.ARENA_CLEAR_RADIUS + footprint + 2.0:
		return false
	if atlas.bridge_deck_rect().grow(footprint + 4.0).has_point(p):
		return false
	for placement in placements:
		if placement.kind != "bridge" and Vector2(placement.position.x, placement.position.z).distance_to(p) < float(placement.footprint) + footprint + 1.0:
			return false
	return true


## Camp spot test: inside or at the edge of its own clearing, off trails, other glades, river.
func camp_spot_ok(p: Vector2, footprint: float, own_site: Dictionary) -> bool:
	if maxf(absf(p.x), absf(p.y)) < 56.0 + footprint or maxf(absf(p.x), absf(p.y)) > 110.0 - footprint * 0.5:
		return false
	if atlas.river_bank_distance(p.x, p.y) < footprint + 1.5:
		return false
	var hit: Dictionary = atlas.nearest_route(p.x, p.y)
	if not hit.is_empty() and hit.distance < footprint + 1.6:
		return false
	for site in atlas.sites:
		if site.id != own_site.id and p.distance_to(Vector2(site.center.x, site.center.z)) < site.radius + footprint + 1.0:
			return false
	for placement in placements:
		if placement.kind != "bridge" and Vector2(placement.position.x, placement.position.z).distance_to(p) < float(placement.footprint) + footprint + 1.0:
			return false
	return true


## Camp extra test: off the walking band of every trail, ≥ 1.8 m (+ footprint) from the glade's
## gameplay anchors, near its own clearing, dry, and not on another placement.
func _extra_ok(p: Vector2, footprint: float, site: Dictionary, anchors: Array) -> bool:
	var center := Vector2(site.center.x, site.center.z)
	if p.distance_to(center) > float(site.radius) + 3.5 or maxf(absf(p.x), absf(p.y)) < 56.5 + footprint:
		return false
	if atlas.river_bank_distance(p.x, p.y) < footprint + 1.2:
		return false
	var hit: Dictionary = atlas.nearest_route(p.x, p.y)
	if not hit.is_empty() and hit.distance < footprint + 1.5:
		return false
	for anchor: Vector2 in anchors:
		if p.distance_to(center + anchor) < footprint + 1.8:
			return false
	for placement in placements:
		if placement.kind != "bridge" and Vector2(placement.position.x, placement.position.z).distance_to(p) < float(placement.footprint) + footprint + 0.3:
			return false
	return true


func find_spot(preferred: Vector2, footprint: float, masks: RefCounted) -> Vector2:
	if valid_spot(preferred, footprint, masks):
		return preferred
	var radius := 1.0
	while radius <= 24.0:
		for k in 24:
			var angle := TAU * k / 24.0
			var p := preferred + Vector2(cos(angle), sin(angle)) * radius
			if valid_spot(p, footprint, masks):
				return p
		radius += 1.0
	return preferred


## Centre of the SW quarry pit (art/01 SW-E): between the mine portal and glade 05 (shared with
## the layout builder). Vector2.INF when the mine has no placement.
func quarry_center() -> Vector2:
	for placement in placements:
		if placement.id == "lf_env_quarry_mine":
			var site: Dictionary = atlas.site_by_id.get("lf_site_05", {})
			if site.is_empty():
				return Vector2(placement.position.x, placement.position.z)
			return Vector2(placement.position.x, placement.position.z).lerp(Vector2(site.center.x, site.center.z), 0.45)
	return Vector2.INF


## Flatten pads for terrain baking: [[Vector2 center, radius, height]].
func pads() -> Array:
	var result: Array = []
	for placement in placements:
		if placement.get("pad", false):
			result.append([Vector2(placement.position.x, placement.position.z), float(placement.footprint), placement.position.y])
	return result


## Spots the forest layout keeps free of trunks: [[Vector2 center, radius]].
func clearances() -> Array:
	var result: Array = []
	for placement in placements:
		if placement.kind != "bridge":
			result.append([Vector2(placement.position.x, placement.position.z), float(placement.footprint) + (1.5 if placement.kind != "camp_piece" else 0.8)])
	if dead_tree_spot != Vector2.INF:
		result.append([dead_tree_spot, 3.0])
	return result


## Instantiates every delivered asset; logs missing ones. Safe to call again (picks up new files).
func populate() -> void:
	for child in get_children():
		child.free()
	items.clear()
	arena_parts.clear()
	arena_lod = -1
	missing.clear()
	loaded.clear()
	_cut_cache.clear()
	for placement in placements:
		var proc: bool = String(placement.id).begins_with("proc_")
		var paths := [] if proc else lod_paths(placement.id, placement.get("dir", ""))
		if not proc and paths[0].is_empty():
			missing[placement.id] = "not delivered (expected %s%s.glb)" % [placement.get("dir", LANDMARK_DIR), placement.id]
			continue
		var holder := Node3D.new()
		holder.name = "%s_%s" % [placement.id, placement.get("site", str(placements.find(placement)))]
		holder.position = placement.position
		holder.rotation.y = placement.yaw
		var scale: float = placement.get("scale", 1.0)
		holder.scale = Vector3(-scale if placement.get("mirror", false) else scale, scale, scale)
		add_child(holder)
		var lods: Array = []
		var players: Array = []
		var tris: Array = []
		for lod in 3:
			var node: Node3D = _proc_piece(String(placement.piece), lod) if proc else null
			if not proc:
				var path: String = ""
				for level in range(lod, -1, -1):
					if not paths[level].is_empty():
						path = paths[level]
						break
				var scene: Variant = load(path)
				if not scene is PackedScene:
					missing[placement.id] = "found but not imported yet: " + path
					lods.append(null)
					players.append([])
					tris.append(0)
					continue
				node = scene.instantiate()
				_prepare(node)
				_dress(node, placement, lod)
			node.name = "LOD%d" % lod
			holder.add_child(node)
			lods.append(node)
			players.append(node.find_children("*", "AnimationPlayer", true, false))
			tris.append(_count_tris(node))
		tris_by_lod[placement.id] = tris
		items.append({"node": holder, "lods": lods, "players": players, "center": Vector2(placement.position.x, placement.position.z),
			"radius": maxf(4.0, float(placement.footprint)) if placement.kind != "bridge" else 17.0, "lod": -1, "id": placement.id,
			"site": placement.get("site", ""), "tris": tris})
		loaded[placement.id] = paths[0] if not proc else "procedural (kit wood)"
		_set_lod(items[-1], 1)
	_populate_arena()


## [LOD0, LOD1, LOD2] files of a landmark id ("" when missing). dir: asset folder override
## (arena modules, props); props files carry their LODs inside one GLB.
func lod_paths(id: String, dir := "") -> Array:
	var result := []
	var folder: String = dir if not dir.is_empty() else (PROPS_DIR if id.begins_with("lf_props_") else LANDMARK_DIR)
	for suffix in ["", "_LOD1", "_LOD2"]:
		var path: String = folder + id + suffix + ".glb"
		result.append(path if ResourceLoader.exists(path) else "")
	return result


## Per-placement dressing of an instantiated landmark LOD: camp pieces cut out of the camp GLB,
## the supply items picked for this camp, the lean-to (platform tilted onto two posts).
func _dress(node: Node3D, placement: Dictionary, lod: int) -> void:
	var piece: String = placement.get("piece", "")
	if placement.id == CAMP.id and piece in ["frame", "fire", "fire_bench"]:
		for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
			if String(part.name).contains("cloth"):
				part.visible = false          # the red tarp (morph cloth node)
			elif piece != "frame" and not String(part.name).contains("_base"):
				part.mesh = _cut_mesh(part.mesh, piece, lod)
	elif placement.id == "lf_props_supplies":
		var wanted: PackedStringArray = String(placement.get("items", "")).split(",", false)
		for part in node.find_children("*", "Node3D", true, false):
			var n := String(part.name)
			if n.begins_with("lf_props_supplies_supply_"):
				var item := n.trim_prefix("lf_props_supplies_supply_").get_slice("_LOD", 0)
				(part as Node3D).visible = wanted.has(item) and n.ends_with("_LOD%d" % lod)
	elif placement.get("piece", "") == "lean_to":
		# platform planks leaning at 62° on a cross pole held by two posts (art/01 lean-to)
		var planks := Node3D.new()
		for child in node.get_children():
			node.remove_child(child)
			planks.add_child(child)
		planks.rotation.x = deg_to_rad(-62.0)
		planks.position = Vector3(0.0, 0.05, -0.5)
		node.add_child(planks)
		var frame := MeshInstance3D.new()
		frame.mesh = _proc_mesh("lean_to_frame")
		node.add_child(frame)


## Triangles of a camp mesh whose centroid lies in the fire ring (+ the log bench), below 1.1 m.
func _cut_mesh(mesh: Mesh, piece: String, lod: int) -> Mesh:
	if mesh == null:
		return mesh
	var key := "%s:%d:%d" % [piece, lod, mesh.get_instance_id()]
	if _cut_cache.has(key):
		return _cut_cache[key]
	var out := ArrayMesh.new()
	for s in mesh.get_surface_count():
		var material := mesh.surface_get_material(s)
		var mname := String(material.resource_name).to_lower() if material != null else ""
		if mname.contains("rope") or mname.contains("cloth"):
			continue
		var arrays := mesh.surface_get_arrays(s)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array(range(verts.size()))
		var kept := PackedInt32Array()
		for t in range(0, index.size(), 3):
			var c := (verts[index[t]] + verts[index[t + 1]] + verts[index[t + 2]]) / 3.0
			if c.y > 1.1:
				continue
			var xz := Vector2(c.x, c.z)
			if xz.distance_to(FIRE_CENTER) <= FIRE_RADIUS or (piece == "fire_bench" and BENCH_RECT.has_point(xz)):
				kept.append_array(PackedInt32Array([index[t], index[t + 1], index[t + 2]]))
		if kept.is_empty():
			continue
		arrays[Mesh.ARRAY_INDEX] = kept
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		out.surface_set_material(out.get_surface_count() - 1, material)
	_cut_cache[key] = out
	return out


## Procedural camp pieces from the delivered landmark wood (lm_wood_c) with the painted kit
## material: split-rail fence, hide rack, drying frame. One node per LOD (same mesh).
func _proc_piece(kind: String, _lod: int) -> Node3D:
	var root := Node3D.new()
	var part := MeshInstance3D.new()
	part.mesh = _proc_mesh(kind)
	part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	root.add_child(part)
	return root


static var _proc_meshes: Dictionary = {}


func _proc_mesh(kind: String) -> Mesh:
	if _proc_meshes.has(kind) and is_instance_valid(_proc_meshes[kind]):
		return _proc_meshes[kind]
	var wood := SurfaceTool.new()
	wood.begin(Mesh.PRIMITIVE_TRIANGLES)
	var hide := SurfaceTool.new()
	hide.begin(Mesh.PRIMITIVE_TRIANGLES)
	var has_hide := false
	match kind:
		"fence":
			for i in 4:
				var x := -2.1 + i * 1.4
				_beam(wood, Vector3(x, -0.15, 0.03 * (i % 2)), Vector3(x + 0.03, 1.02 + 0.06 * sin(i * 2.3), 0.0), 0.12, 0.12)
			_beam(wood, Vector3(-2.25, 0.46, 0.06), Vector3(2.25, 0.41, 0.06), 0.08, 0.1)
			_beam(wood, Vector3(-2.25, 0.83, 0.06), Vector3(2.25, 0.88, 0.06), 0.08, 0.1)
		"hide_rack":
			_beam(wood, Vector3(-0.85, -0.1, 0.0), Vector3(-0.8, 1.95, 0.0), 0.1, 0.1)
			_beam(wood, Vector3(0.85, -0.1, 0.0), Vector3(0.8, 1.9, 0.0), 0.1, 0.1)
			_beam(wood, Vector3(-1.0, 1.82, 0.0), Vector3(1.0, 1.78, 0.0), 0.08, 0.08)
			_beam(wood, Vector3(-0.85, 0.42, 0.0), Vector3(0.85, 0.42, 0.0), 0.07, 0.07)
			_hide_quad(hide, Vector3(-0.7, 0.5, 0.04), Vector3(0.7, 1.74, 0.04))
			has_hide = true
		"drying_frame":
			for x in [-1.1, 1.1]:
				_beam(wood, Vector3(x, -0.1, -0.65), Vector3(x, 1.75, 0.0), 0.09, 0.09)
				_beam(wood, Vector3(x, -0.1, 0.65), Vector3(x, 1.75, 0.0), 0.09, 0.09)
			_beam(wood, Vector3(-1.35, 1.72, 0.0), Vector3(1.35, 1.72, 0.0), 0.08, 0.08)
			_beam(wood, Vector3(-1.2, 0.95, 0.33), Vector3(1.2, 0.95, 0.33), 0.06, 0.06)
			for i in 4:
				var x := -0.75 + i * 0.5
				_hide_quad(hide, Vector3(x - 0.13, 1.05 + 0.08 * (i % 2), 0.02), Vector3(x + 0.13, 1.68, 0.02))
			has_hide = true
		"lean_to_frame":
			_beam(wood, Vector3(-1.15, -0.1, 0.55), Vector3(-1.1, 1.55, 0.5), 0.11, 0.11)
			_beam(wood, Vector3(1.15, -0.1, 0.55), Vector3(1.1, 1.5, 0.5), 0.11, 0.11)
			_beam(wood, Vector3(-1.4, 1.5, 0.5), Vector3(1.4, 1.46, 0.5), 0.1, 0.1)
	var mesh := wood.commit()
	mesh.surface_set_material(0, _material("wood"))
	if has_hide:
		hide.commit(mesh)
		mesh.surface_set_material(1, _material("hide"))
	_proc_meshes[kind] = mesh
	return mesh


static var _proc_materials: Dictionary = {}


static func _material(kind: String) -> Material:
	if _proc_materials.has(kind) and is_instance_valid(_proc_materials[kind]):
		return _proc_materials[kind]
	var base := StandardMaterial3D.new()
	base.resource_name = "lf_proc_" + kind
	if kind == "wood":
		var texture: Variant = load(LANDMARK_DIR + "lm_wood_c.jpg") if ResourceLoader.exists(LANDMARK_DIR + "lm_wood_c.jpg") else null
		base.albedo_texture = texture
		base.albedo_color = Color(0.92, 0.86, 0.78) if texture != null else Color(0.42, 0.3, 0.2)
	else:
		base.albedo_color = Color(0.68, 0.52, 0.35)
	var material := ForestKit.painted_material(base, false, LIGHT_MIX, false)
	_proc_materials[kind] = material
	return material


## A square beam from a to b (cross-section w × h), UV u along the beam.
static func _beam(st: SurfaceTool, a: Vector3, b: Vector3, w: float, h: float) -> void:
	var axis := (b - a).normalized()
	var side := axis.cross(Vector3.UP)
	if side.length() < 0.01:
		side = axis.cross(Vector3.RIGHT)
	side = side.normalized() * w * 0.5
	var up := side.cross(axis).normalized() * h * 0.5
	var length := a.distance_to(b)
	var corners := [side + up, -side + up, -side - up, side - up]
	for k in 4:
		var c0: Vector3 = corners[k]
		var c1: Vector3 = corners[(k + 1) % 4]
		var n := ((c0 + c1) * 0.5).normalized()
		var quad := [a + c0, a + c1, b + c1, b + c0]
		var uvs := [Vector2(0, k * 0.25), Vector2(0, (k + 1) * 0.25), Vector2(length, (k + 1) * 0.25), Vector2(length, k * 0.25)]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal(n)
			st.set_uv(uvs[i])
			st.add_vertex(quad[i])


## A slightly sagging hide (3 × 3 grid) between two corners in the local XY plane.
static func _hide_quad(st: SurfaceTool, lo: Vector3, hi: Vector3) -> void:
	var n := 3
	for j in n:
		for i in n:
			var q := []
			for c in [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]]:
				var u := float(c[0]) / n
				var v := float(c[1]) / n
				var sag := 0.05 * sin(u * PI) * sin(v * PI)
				q.append(Vector3(lerpf(lo.x, hi.x, u) + 0.03 * sin(v * 5.0), lerpf(lo.y, hi.y, v), lo.z + sag))
			for k in [0, 1, 2, 0, 2, 3]:
				st.set_normal(Vector3(0, 0, 1))
				st.set_uv(Vector2(float([i, i + 1, i + 1, i][k]) / n, float([j, j, j + 1, j + 1][k]) / n))
				st.add_vertex(q[k])


func _prepare(node: Node3D) -> void:
	for part in node.find_children("*", "Node3D", true, false):
		if String(part.name).contains("_base"):
			(part as Node3D).visible = false
	ForestKit.paint_scene(node, LIGHT_MIX)
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if String(part.name).contains("_base") else GeometryInstance3D.SHADOW_CASTING_SETTING_ON


static func _visible_tris(node: Node) -> int:
	if node == null or not is_instance_valid(node):
		return 0
	var total := 0
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if part.mesh != null and part.is_visible_in_tree():
			total += ForestKit.mesh_triangles(part.mesh)
	return total


static func _count_tris(node: Node) -> int:
	var total := 0
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null or not part.visible:
			continue
		total += ForestKit.mesh_triangles(part.mesh)
	return total


func _set_lod(item: Dictionary, lod: int) -> void:
	if item.lod == lod:
		return
	item.lod = lod
	for i in 3:
		var node: Node3D = item.lods[i]
		if node == null:
			continue
		var on := i == lod
		node.visible = on
		for player: AnimationPlayer in item.players[i]:
			if on and not player.get_animation_list().is_empty():
				var clip: String = player.get_animation_list()[0]
				player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
				if not player.is_playing():
					player.play(clip)
					player.seek(fposmod(item.center.x * 0.37 + item.center.y * 0.11, 4.5), true)
			elif not on and player.is_playing():
				player.stop()


## LOD by the city zoom and the distance to the camera focus; hidden while under opaque fog.
## visible_fn: Callable(x, z, radius) -> bool (fog-aware). Returns visible triangle estimate.
func update_view(target: Vector3, zoom: float, visible_fn: Callable) -> int:
	var tris := 0
	for item in items:
		var shown: bool = visible_fn.call(item.center.x, item.center.y, item.radius) if visible_fn.is_valid() else true
		item.node.visible = shown
		if not shown:
			continue
		var d: float = item.center.distance_to(Vector2(target.x, target.z))
		var lod := 2
		if zoom <= 50.0 and d <= 30.0:
			lod = 0
		elif zoom <= 96.0 and d <= 64.0:
			lod = 1
		_set_lod(item, lod)
		if d <= zoom * 1.25 + item.radius:      # roughly inside the ortho view
			tris += int(item.tris[lod])
	if arena_root != null:
		var center := Vector2(arena_root.position.x, arena_root.position.z)
		var shown: bool = visible_fn.call(center.x, center.y, 20.0) if visible_fn.is_valid() else true
		arena_root.visible = shown
		if shown:
			var d := center.distance_to(Vector2(target.x, target.z))
			var lod := 0 if zoom <= ARENA_LOD_ZOOM[0] else (1 if zoom <= ARENA_LOD_ZOOM[1] else 2)
			if d > zoom * 1.25 + 40.0:
				lod = 2
			_set_arena_lod(lod)
			arena_visible_fn = visible_fn
			_cull_arena()
			if d <= zoom * 1.25 + 24.0:
				tris += _visible_tris(arena_node)
	return tris


## Arena v2 (art/08 rebuild): three whole files with the same node names,
## lf_boss_arena_assembled{,_lod1,_lod2}.glb (54.8k / 21.2k / 10.1k tris, ~13-14 MB each with
## embedded kit textures). The file for the zoom (LOD0 <= 34, LOD1 <= 85, LOD2 beyond) is
## loaded on a worker thread and swapped in; the previous instance is freed, so only one
## arena file stays resident. Painted kit material like the landmarks.
const ARENA_FILES := ["lf_boss_arena_assembled.glb", "lf_boss_arena_assembled_lod1.glb", "lf_boss_arena_assembled_lod2.glb"]
const ARENA_LOD_ZOOM := [34.0, 85.0]
var arena_node: Node3D
var arena_cull: Array = []        # [[MeshInstance3D, Vector2 xz centre, radius]] of the shown file
var arena_visible_fn := Callable()
var arena_shown_lod := -1
var arena_wanted_lod := -1
var arena_loading := ""
var arena_tris := 0


func _populate_arena() -> void:
	arena_root = Node3D.new()
	arena_root.name = "BossArena"
	var center: Vector3 = atlas.arena_center
	arena_root.position = Vector3(center.x, center.y - 0.3, center.z)
	arena_root.rotation.y = deg_to_rad(atlas.arena_yaw_deg)
	add_child(arena_root)
	if not arena_loading.is_empty():
		ResourceLoader.load_threaded_get(arena_loading)   # drain a request of the previous build
	arena_node = null
	arena_shown_lod = -1
	arena_wanted_lod = -1
	arena_loading = ""
	if _arena_path(0).is_empty():
		missing["lf_boss_arena"] = "arena not delivered (expected %s%s)" % [ARENA_DIR, ARENA_FILES[0]]
		return
	loaded["lf_boss_arena"] = _arena_path(0)
	_request_arena_lod(1)


func _arena_path(lod: int) -> String:
	for level in range(lod, -1, -1):
		var path: String = ARENA_DIR + ARENA_FILES[level]
		if ResourceLoader.exists(path):
			return path
	return ""


func _request_arena_lod(lod: int) -> void:
	arena_wanted_lod = lod
	var path := _arena_path(lod)
	if path.is_empty() or (lod == arena_shown_lod and arena_node != null):
		return
	if arena_loading == path:
		return
	if not arena_loading.is_empty():
		# A different file is still on its way: let it land, the poll re-requests the wanted one.
		return
	if ResourceLoader.load_threaded_request(path, "PackedScene") != OK:
		_swap_arena(load(path), lod)
		return
	arena_loading = path


func _process(_delta: float) -> void:
	_poll_arena()


func _poll_arena(blocking := false) -> void:
	if arena_loading.is_empty():
		return
	var status := ResourceLoader.load_threaded_get_status(arena_loading)
	if blocking or status == ResourceLoader.THREAD_LOAD_LOADED:
		var scene: Variant = ResourceLoader.load_threaded_get(arena_loading)
		var lod := ARENA_FILES.find(arena_loading.get_file())
		arena_loading = ""
		_swap_arena(scene, lod)
	elif status == ResourceLoader.THREAD_LOAD_FAILED or status == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
		push_warning("ForestLandmarks: arena LOD failed to load: " + arena_loading)
		arena_loading = ""
	if arena_loading.is_empty() and arena_wanted_lod >= 0 and arena_wanted_lod != arena_shown_lod:
		_request_arena_lod(arena_wanted_lod)


## QA/capture: finish a pending arena load now (a still never shows the previous LOD).
func finish_arena_load() -> void:
	_poll_arena(true)


func _swap_arena(scene: Variant, lod: int) -> void:
	if not scene is PackedScene or arena_root == null:
		return
	var node: Node3D = (scene as PackedScene).instantiate()
	node.name = "LOD%d" % lod
	ForestKit.paint_scene(node, LIGHT_MIX)
	arena_root.add_child(node)
	for player: AnimationPlayer in node.find_children("*", "AnimationPlayer", true, false):
		if not player.get_animation_list().is_empty():
			var clip: String = player.get_animation_list()[0]
			player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
			player.play(clip)
	if arena_node != null and is_instance_valid(arena_node):
		arena_node.free()
	arena_node = node
	arena_shown_lod = lod
	arena_lod = lod
	arena_tris = _count_tris(node)
	# Zero-through-fog: the arena file carries kit trees / rocks on its rim; each part follows
	# the same rule as the kit instances (nothing renders deeper inside unexplored ground than
	# the 3 m blend band, here + the part's own radius), and its painted materials join the fog
	# receivers so the band erodes like the forest around it.
	arena_cull.clear()
	for part: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		var box: AABB = part.global_transform * part.get_aabb()
		var c := box.get_center()
		arena_cull.append([part, Vector2(c.x, c.z), maxf(box.size.x, box.size.z) * 0.5])
	var world := get_parent()
	if world != null and world.has_method("_register_fog_receivers"):
		world.call("_register_fog_receivers")
	_cull_arena()
	apply_arena_state(arena_state)


func _cull_arena() -> void:
	if not arena_visible_fn.is_valid():
		return
	for entry in arena_cull:
		var part: MeshInstance3D = entry[0]
		if is_instance_valid(part):
			part.visible = bool(arena_visible_fn.call(entry[1].x, entry[1].y, float(entry[2])))


func _set_arena_lod(lod: int) -> void:
	_request_arena_lod(lod)


## Visual dressing only. Nodes named state_<locked|available|active|defeated> (any depth) are
## shown for their state; everything else is untouched.
func apply_arena_state(state: String) -> void:
	arena_state = state
	if arena_root == null:
		return
	for node in arena_root.find_children("state_*", "Node3D", true, false):
		(node as Node3D).visible = String(node.name).trim_prefix("state_").begins_with(state)


func apply_site_state(site_id: String, step: int) -> void:
	site_states[site_id] = step
	for node in find_children("*_" + site_id, "Node3D", false, false):
		for part in node.find_children("post_*", "Node3D", true, false):
			(part as Node3D).visible = step >= 5
