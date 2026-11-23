extends Node3D

## Townsfolk (build 1024): the people of the town, replacing the rigid ambient workers
## (Worker_* boxes whose merged clips flailed in place beside their building).
##
## * Models: the skinned civilians of «Лес потерянных» (assets/forest_rescue/humans/
##   lf_civilian_*.glb, one shared rig) loaded through ActorRig (threaded, one load at a time,
##   painted look, look variation through the variant mask, Bag accessory hidden for some).
##   LOD2 (2.1k triangles) at the city zooms, LOD1 (5.9k) when zoomed in below LOD_NEAR_ZOOM.
## * Walking: only on the town plan (src/town_plan.gd): the street centre lines split at every
##   crossing, the town square as an open area, and one path per yard from its street exit to
##   the building's door. Every edge is checked once per layout against building bodies, gate
##   posts, standing trees (>= 1.05 m), water, the wall, the troop ground, the parade, building
##   sites and unpainted ground; the free band of each edge decides how far from the centre line
##   people may walk. People keep to the right of the street (each at its own distance), corners
##   are rounded, so walkers that meet pass each other instead of walking through each other.
## * Routines: every person belongs to a building and has a loop (lumberjack: camp -> store with
##   a log; farmer: farm -> granary with a sack; carrier: store -> market with a crate; smith,
##   quarryman, herbalist, messenger, the hall's steward, strollers between the square and the
##   houses). Walk -> stop at a door or on the square -> stand, look around or gesture -> next
##   leg; at home they go in (fade at the doorway) and come out later. Seeded per person (look,
##   +-4 % height, +-10 % pace, phase), so the town never moves in step.
## * The whole day is a function of the clock: an off-screen person advances on the clock and
##   costs only the evaluation (no AnimationPlayer, no transforms); on screen the walk clip is
##   played at ground speed / stride speed (no sliding), clips cross-fade (BLEND), the heading
##   turns at most TURN_RATE. A walker that catches up with another one walking the same way
##   holds back (its clock is delayed and catches up later while standing or inside).
## * Ground: the feet stand on the drawn town ground (the same 1 m height grid, triangle split
##   and lift as src/town_ground.gd). Visual only: no server request or rule is involved.

const ActorRig = preload("res://src/forest_rescue/game/actor_rig.gd")
const TownPlan = preload("res://src/town_plan.gd")
const TownGround = preload("res://src/town_ground.gd")
## Ground each building level really takes (tools/measure_town_solids.gd).
const SOLIDS := "res://assets/city/town_solids.json"

const HUMAN := "res://assets/forest_rescue/humans/lf_civilian_%s.glb"
const CLIP_NAMES: Array[StringName] = [&"lf_civilian_wait", &"lf_civilian_follow", &"lf_civilian_follow_tired",
	&"lf_civilian_look_back", &"lf_civilian_thank", &"lf_civilian_react"]
enum { C_IDLE, C_WALK, C_LOADED, C_LOOK, C_THANK, C_REACT }
## Length of the one-shot clips (s, playback 1).
const GESTURE_SECONDS: Array[float] = [0.0, 0.0, 0.0, 1.6, 2.3, 1.4]
## Ground speed of the walk clips at scale 1 and playback 1 (m/s): the speed of the planted
## foot measured over the flat stance (lf_civilian_follow 1.193, _tired 0.944; qa_townsfolk).
const STRIDE_SPEED: Array[float] = [0.0, 1.193, 0.944, 0.0, 0.0, 0.0]
const BLEND := 0.25
const TURN_RATE := 5.0
const RAMP := 0.45
const TURN_WINDOW := 0.9
const STEP_IN := 0.65
const STEP_SECONDS := 0.7
const LOD_NEAR_ZOOM := 40.0
## Free space kept to a gate post and a tree trunk (m); buildings: town_solids.json.
const POST_CLEAR := 0.6
const TREE_CLEAR := 1.1
## A street edge keeps this much of its half width free at the kerb.
const EDGE_MARGIN := 0.35
const SQUARE_BAND := 0.45
const DOOR_BAND := 0.45
const SAMPLE_STEP := 0.5
const MAX_DELAY := 40.0
enum { K_WALK, K_DWELL, K_ENTER, K_INSIDE, K_LEAVE }

# Building roles by base type.
const STORE := ["ECO-01", "ECO-02", "ALT-12", "ALT-15"]
const MARKET := ["ECO-03", "ALT-11"]
const FARM := ["RES-04", "ALT-05"]
const LUMBER := ["RES-01", "ALT-01", "ALT-02"]
const QUARRY := ["RES-02", "ALT-03", "ALT-09", "RES-03", "ALT-04"]
const SMITH := ["MIL-04", "ALT-10"]
const HERBAL := ["ALT-08"]
const HOSPITAL := ["SUP-01"]
const HOUSE := ["ECO-04", "ALT-14", "ALT-13"]
const WELL := ["SUP-05", "ALT-16"]
const MILITARY := ["MIL-01", "MIL-02", "MIL-03", "MIL-05", "SUP-02", "SUP-04", "RES-05", "ALT-06", "ALT-07"]

## Look variation (the captives' palette): [cloth, hair].
const TINTS := [[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]], [[1.12, 0.9, 0.8], [1.32, 0.88, 0.7]],
	[[0.86, 0.8, 0.72], [1.18, 0.96, 0.82]], [[0.78, 0.78, 0.78], [0.62, 0.6, 0.6]],
	[[0.84, 1.0, 0.88], [1.55, 1.32, 1.02]], [[1.08, 0.98, 0.78], [1.18, 0.96, 0.82]],
	[[1.06, 1.06, 1.04], [0.62, 0.6, 0.6]], [[0.9, 0.9, 0.98], [1.32, 0.88, 0.7]],
	[[1.0, 1.0, 1.0], [1.2, 1.18, 1.16]], [[0.72, 1.0, 0.78], [0.62, 0.6, 0.6]]]

class Person extends RefCounted:
	var key := ""
	var role := ""
	var visual := ""
	var home := -1
	var seed := 0
	var scale := 1.0
	var pace := 1.0
	var side := 0.8
	var phase := 0.0
	var cycle := 1.0
	var idle_rate := 1.0
	var prop_kind := ""
	var variant: Dictionary = {}
	# Timeline (one entry per phase).
	var kinds := PackedInt32Array()
	var starts := PackedFloat32Array()
	var lengths := PackedFloat32Array()
	var leg := PackedInt32Array()
	var speed := PackedFloat32Array()
	var clip := PackedInt32Array()
	var gesture_at := PackedFloat32Array()
	var carry := PackedInt32Array()
	var spot_a := PackedVector2Array()
	var spot_b := PackedVector2Array()
	var face := PackedFloat32Array()
	var turn_to := PackedFloat32Array()
	var paths: Array[PackedVector2Array] = []
	var lines: Array[PackedVector3Array] = []
	var cums: Array[PackedFloat32Array] = []
	# Runtime.
	var rig: Node3D = null
	var prop: Node3D = null
	var meshes: Array[GeometryInstance3D] = []
	var ready := false
	var shown := false
	var heading := 0.0
	var clip_now := -1
	var alpha_now := 1.0
	var prop_shown := false
	var delay := 0.0
	var hold := 0.0
	var lod := -1
	var blob_hidden := false
	var pos := Vector2.ZERO
	var walked := 0.0
	var ground_at := Vector2.INF
	var placed := Vector3.INF
	var placed_yaw := INF
	# Evaluated every frame.
	var at := Vector2.ZERO
	var y := 0.0
	var want_yaw := 0.0
	var v := 0.0
	var clip_want := 0
	var clip_offset := 0.0
	var alpha := 1.0
	var carrying := false
	var walking := false
	var turning := false
	var index := 0
	var local := 0.0

	## Carries the model, its state and the pose over from the same person of an older plan.
	func adopt(old: Person) -> void:
		rig = old.rig
		prop = old.prop
		meshes = old.meshes
		ready = old.ready
		shown = old.shown
		heading = old.heading
		clip_now = old.clip_now
		alpha_now = old.alpha_now
		prop_shown = old.prop_shown
		lod = old.lod
		blob_hidden = old.blob_hidden
		old.rig = null

var stage: Node3D
var plan: TownPlan
var people: Array[Person] = []
var hall_level := 1
## QA: evaluate and pose every person as if on screen.
var simulate_all := false
## QA: hold-back of walkers that catch up with another (on by default).
var follow := true
var last_time := -1.0
var update_usec := 0
var update_samples := PackedInt32Array()
## QA: microseconds spent in [evaluate, hold back, posing], summed since the last reset.
var section_usec := PackedInt64Array([0, 0, 0])
var rebuilds := 0
var dropped_legs := 0
var lod_level := 2
var blobs: MultiMeshInstance3D
## Sun shadows of the people: only on the closer zooms, where a 1.7 m figure's shadow reads
## (at the default zoom it is 2-4 px, and each person would be one more skinned draw in the
## shadow pass). The contact blob grounds them at every zoom (one draw for all).
const SHADOW_ZOOM := 50.0
var cast_real_shadows := false

# Graph of the walkable town.
var g_nodes := PackedVector2Array()
var g_edges: Array[PackedInt32Array] = []
var e_a := PackedInt32Array()
var e_b := PackedInt32Array()
var e_lat := PackedFloat32Array()
var e_live := PackedByteArray()
var e_kind := PackedByteArray()
var e_shift := PackedFloat32Array()
var component := PackedInt32Array()
var edge_keys := {}
var node_cells := {}
var door_node := {}
var door_stop := {}
var door_lot := {}
var door_in := {}
## Room in front of each door (m of straight path before it): a door without room for a lead
## point is a place for one person at a time.
var door_room := {}
var street_segs: Array = []
var spot_nodes := PackedInt32Array()
## Places in the forecourts beside the door paths, where a passer-by stops to look (node -> yaw).
var yard_spots := {}
var square_nodes := {}
var stop_users := {}
var route_cache := {}
# Obstacles of the current layout.
var bodies: Array[Rect2] = []
var posts := PackedVector2Array()
var blocked_rects: Array[Rect2] = []
var extra_trees := {}
var heights := PackedFloat32Array()
var solid_lots: Array = []
## The wall's main gate scene (rotated, scaled): [inverse transform, x0, z0, w, h, bits].
var solid_gate: Array = []
static var solid_table: Dictionary = {}
var terrain_tiles: Array = []
var terrain_last := 0
var seen := {}
var lot_base: Array[String] = []
var district: Variant = null

func setup(owner_stage: Node3D) -> void:
	stage = owner_stage
	name = "Townsfolk"
	heights.resize(129 * 129)
	heights.fill(NAN)

# ------------------------------------------------------------------ ground

func grid_height(ix: int, iz: int) -> float:
	var i := (iz + 64) * 129 + ix + 64
	var h := heights[i]
	if is_nan(h):
		h = float(stage.static_height(float(ix), float(iz)))
		heights[i] = h
	return h

## Height of the drawn ground under a walker: the town ground (src/town_ground.gd: 1 m cells
## of static_height, split along the (1,0)-(0,1) diagonal, lifted by LIFT), or the terrain where
## its coarser grid rises above it (concave spots such as the edge of a flattened plot).
func ground_y(x: float, z: float) -> float:
	return maxf(town_y(x, z), terrain_y(x, z))

func town_y(x: float, z: float) -> float:
	if absf(x) >= 63.0 or absf(z) >= 63.0:
		return float(stage.ground_point(Vector3(x, 0.0, z)).y)
	var x0 := floorf(x)
	var z0 := floorf(z)
	var fx := x - x0
	var fz := z - z0
	var ix := int(x0)
	var iz := int(z0)
	var h := 0.0
	if fx + fz <= 1.0:
		var h00 := grid_height(ix, iz)
		h = h00 + (grid_height(ix + 1, iz) - h00) * fx + (grid_height(ix, iz + 1) - h00) * fz
	else:
		var h11 := grid_height(ix + 1, iz + 1)
		h = h11 + (grid_height(ix, iz + 1) - h11) * (1.0 - fx) + (grid_height(ix + 1, iz) - h11) * (1.0 - fz)
	return h + TownGround.LIFT

## Height of the drawn terrain (the city ground tiles: regular vertex grids with the same
## diagonal); read from the tile meshes the first time a tile is needed.
func terrain_y(x: float, z: float) -> float:
	if terrain_tiles.is_empty():
		for mesh in stage.city_ground_meshes:
			if not is_instance_valid(mesh) or mesh.mesh == null:
				continue
			var box: AABB = mesh.global_transform * mesh.get_aabb()
			terrain_tiles.append({"rect": Rect2(box.position.x, box.position.z, box.size.x, box.size.z), "mesh": mesh, "h": PackedFloat32Array()})
		if terrain_tiles.is_empty():
			terrain_tiles.append({"rect": Rect2(), "mesh": null, "h": PackedFloat32Array()})
	var tile: Dictionary = terrain_tiles[terrain_last]
	if not (tile.rect as Rect2).grow(0.001).has_point(Vector2(x, z)):
		tile = {}
		for k in terrain_tiles.size():
			if (terrain_tiles[k].rect as Rect2).grow(0.001).has_point(Vector2(x, z)):
				terrain_last = k
				tile = terrain_tiles[k]
				break
		if tile.is_empty():
			return float(stage.sample_city(x, z))
	if (tile.h as PackedFloat32Array).is_empty():
		read_tile(tile)
	var n: int = tile.n
	var step: float = tile.step
	var fx := clampf((x - float(tile.x0)) / step, 0.0, n - 1.001)
	var fz := clampf((z - float(tile.z0)) / step, 0.0, n - 1.001)
	var i := int(fx)
	var j := int(fz)
	fx -= i
	fz -= j
	var h: PackedFloat32Array = tile.h
	if fx + fz <= 1.0:
		var h00 := h[j * n + i]
		return h00 + (h[j * n + i + 1] - h00) * fx + (h[(j + 1) * n + i] - h00) * fz
	var h11 := h[(j + 1) * n + i + 1]
	return h11 + (h[(j + 1) * n + i] - h11) * (1.0 - fx) + (h[j * n + i + 1] - h11) * (1.0 - fz)

func read_tile(tile: Dictionary) -> void:
	var mesh: MeshInstance3D = tile.mesh
	var vertices: PackedVector3Array = mesh.global_transform * (mesh.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array)
	var n := roundi(sqrt(float(vertices.size())))
	var rect: Rect2 = tile.rect
	var step := rect.size.x / maxf(1.0, n - 1)
	var h := PackedFloat32Array()
	h.resize(n * n)
	for v in vertices:
		var i := clampi(roundi((v.x - rect.position.x) / step), 0, n - 1)
		var j := clampi(roundi((v.z - rect.position.y) / step), 0, n - 1)
		h[j * n + i] = v.y
	tile.n = n
	tile.step = step
	tile.x0 = rect.position.x
	tile.z0 = rect.position.y
	tile.h = h

## Coverage of the town ground mask at (x, z) as its shader samples it (linear filter); the
## town ground is drawn where it is >= 0.5.
func cover(x: float, z: float) -> float:
	var town: TownPlan = stage.town_plan if stage != null else null
	if town == null or town.mask == null:
		return 0.0
	var u := (x + TownPlan.HALF) / TownPlan.CELL - 0.5
	var v := (z + TownPlan.HALF) / TownPlan.CELL - 0.5
	var i := floori(u)
	var j := floori(v)
	if i < 0 or j < 0 or i >= TownPlan.SIZE - 1 or j >= TownPlan.SIZE - 1:
		return 0.0
	var fu := u - i
	var fv := v - j
	var c00 := town.mask.get_pixel(i, j)
	var c10 := town.mask.get_pixel(i + 1, j)
	var c01 := town.mask.get_pixel(i, j + 1)
	var c11 := town.mask.get_pixel(i + 1, j + 1)
	return lerpf(lerpf(maxf(c00.r, c00.g), maxf(c10.r, c10.g), fu), lerpf(maxf(c01.r, c01.g), maxf(c11.r, c11.g), fu), fv)

## Ground a building really takes (walls, fences, stairs, beds, grown by a body width).
func solid_at(p: Vector2) -> bool:
	if not solid_gate.is_empty():
		var local: Vector3 = (solid_gate[0] as Transform3D) * Vector3(p.x, 0.0, p.y)
		var cx := floori(local.x / 0.25) - int(solid_gate[1])
		var cz := floori(local.z / 0.25) - int(solid_gate[2])
		var gw: int = solid_gate[3]
		if cx >= 0 and cz >= 0 and cx < gw and cz < int(solid_gate[4]):
			var gi := cz * gw + cx
			var gate_bits: PackedByteArray = solid_gate[5]
			if gate_bits[gi >> 3] & (1 << (gi & 7)):
				return true
	var feet := NAN
	for entry: Array in solid_lots:
		if not (entry[0] as Rect2).has_point(p):
			continue
		# Feet below the building's base (a plot on a slope): its low parts count as well.
		if is_nan(feet):
			feet = town_y(p.x, p.y)
		var mask: Array = entry[2] if feet < float(entry[1]) - 0.07 else entry[3]
		if mask.is_empty() or not (mask[0] as Rect2).has_point(p):
			continue
		var w: int = mask[3]
		var i: int = floori((p.y - float(mask[2])) / 0.25) * w + floori((p.x - float(mask[1])) / 0.25)
		var bits: PackedByteArray = mask[5]
		if bits[i >> 3] & (1 << (i & 7)):
			return true
	return false

func solid_entry(type: String, level: int) -> Dictionary:
	var entry: Variant = solid_table.get(type, {}).get(str(clampi(level, 1, 5)))
	if not entry is Dictionary or int(entry.w) == 0:
		return {}
	if not entry.has("raw"):
		entry.raw = Marshalls.base64_to_raw(str(entry.bits))
	return entry

func collect_solids() -> void:
	solid_lots.clear()
	solid_gate.clear()
	if solid_table.is_empty() and FileAccess.file_exists(SOLIDS):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SOLIDS))
		solid_table = parsed.get("types", {}) if parsed is Dictionary else {}
	var gate: Variant = stage.get("gate_node")
	if gate is Node3D and is_instance_valid(gate) and stage.walls.visible:
		var level := int(str(gate.scene_file_path).get_file().get_basename().get_slice("-", 2))
		var entry := solid_entry("SUP-03", level)
		if not entry.is_empty():
			solid_gate = [(gate as Node3D).global_transform.affine_inverse(), int(entry.x0), int(entry.z0), int(entry.w), int(entry.h), entry.raw]
	for lot: Dictionary in plan.lots:
		var entry := solid_entry(str(lot.type), int(lot.level))
		if entry.is_empty():
			continue
		var at: Vector2 = lot.at
		var solid := placed_mask(entry, at)
		var base: Array = placed_mask(entry.base, at) if entry.get("base") is Dictionary and int(entry.base.w) > 0 else solid
		var reach: Rect2 = solid[0]
		reach = reach.merge(base[0])
		# [both masks' rect, the plot's ground height, base mask, solid mask]
		solid_lots.append([reach, float(stage.sample_city(at.x, at.y)), base, solid])

## A mask of the table placed round a plot centre: [rect, x0, z0, w, h, bits].
static func placed_mask(entry: Dictionary, at: Vector2) -> Array:
	if not entry.has("raw"):
		entry.raw = Marshalls.base64_to_raw(str(entry.bits))
	var ox := at.x + int(entry.x0) * 0.25
	var oz := at.y + int(entry.z0) * 0.25
	return [Rect2(ox, oz, int(entry.w) * 0.25 - 0.0001, int(entry.h) * 0.25 - 0.0001), ox, oz, int(entry.w), int(entry.h), entry.raw]

## True where the town ground is drawn (streets, yards, square; not discarded by its shader).
var mask_bytes := PackedByteArray()
var mask_of: Image = null

func painted(x: float, z: float) -> bool:
	var town: TownPlan = stage.town_plan if stage != null else null
	if town == null or town.mask == null:
		return false
	if mask_of != town.mask:
		mask_of = town.mask
		mask_bytes = town.mask.get_data()
	var px := int(floor((x + TownPlan.HALF) / TownPlan.CELL))
	var pz := int(floor((z + TownPlan.HALF) / TownPlan.CELL))
	if px < 1 or pz < 1 or px >= TownPlan.SIZE - 1 or pz >= TownPlan.SIZE - 1:
		return false
	# The shader frays earth edges by up to a cell: the pixel and its four neighbours
	# (R earth or G paving of RGBA8).
	var i := (pz * TownPlan.SIZE + px) * 4
	var row := TownPlan.SIZE * 4
	for k: int in [i, i + 4, i - 4, i + row, i - row]:
		if maxi(mask_bytes[k], mask_bytes[k + 1]) < 230:
			return false
	return true

# ------------------------------------------------------------------ layout

## Called by the landscape at the end of each city update. Only notes the hall and the troop
## ground: the plan (and the model loads) start from the next present(), which main.gd calls
## once the scene is up, so nothing of this runs under the launch screen.
func sync(level: int, troop_ground: Variant) -> void:
	if level != hall_level or str(troop_ground) != str(district):
		seen.erase("town")
	hall_level = level
	district = troop_ground.duplicate() if troop_ground is Dictionary else null

func layout_changed() -> bool:
	if stage == null:
		return false
	var works = stage.works
	var works2 = stage.works2
	return seen.get("town", -1) != stage.town_rebuilds or seen.get("vegetation", -1) != stage.vegetation_rebuilds \
		or seen.get("forest", "") != stage.forest_attach_state or seen.get("hall", -1) != hall_level \
		or seen.get("site1", "") != works.builder_site or seen.get("site2", "") != works2.builder_site \
		or seen.get("parade", -1) != stage.parade_slots.size()

func remember_layout() -> void:
	seen = {"town": stage.town_rebuilds, "vegetation": stage.vegetation_rebuilds, "forest": stage.forest_attach_state,
		"hall": hall_level, "site1": stage.works.builder_site, "site2": stage.works2.builder_site,
		"parade": stage.parade_slots.size()}

## Plans the town anew (a building placed or upgraded, a site opened or closed, the wall, the
## parade, the forest). Runs in the background in slices of SLICE_USEC per frame: the people of
## the old plan keep walking until the new one is ready, then each carries its model over.
## sync_build (tools, QA) plans in one go.
const SLICE_USEC := 2500
var sync_build := false
var building := false
var build_serial := 0
var slice_start := 0
var crowded := 0
## QA: who was left out of the last plan and why.
var left_out: Array = []
var last_build_usec := 0
var last_build_frames := 0
## QA: microseconds of the last plan's steps (graph, people, timelines; frames between included).
var build_profile := {}

func rebuild() -> void:
	remember_layout()
	build_serial += 1
	var serial := build_serial
	building = true
	var started := Time.get_ticks_usec()
	slice_start = started
	last_build_frames = 1
	plan = stage.town_plan
	rebuilds += 1
	route_cache.clear()
	stop_users.clear()
	terrain_tiles.clear()
	terrain_last = 0
	collect_obstacles()
	collect_solids()
	memo.resize(MEMO_SIZE * MEMO_SIZE)
	memo.fill(0)
	build_profile.clear()
	var mark := Time.get_ticks_usec()
	if not await build_graph(serial):
		return
	build_profile["graph"] = Time.get_ticks_usec() - mark
	mark = Time.get_ticks_usec()
	var specs := plan_people()
	# The first person of each building has the first place at its own door.
	for spec: Dictionary in specs:
		var home: int = spec.home
		if home >= 0 and door_node.has(home):
			var users: Array = stop_users.get(door_node[home], [])
			if users.is_empty():
				users.append(spec.key)
				stop_users[door_node[home]] = users
	build_profile["plan"] = Time.get_ticks_usec() - mark
	mark = Time.get_ticks_usec()
	var wanted := clampi(4 + 2 * hall_level, 6, 14)
	var fresh: Array[Person] = []
	crowded = 0
	left_out.clear()
	for spec: Dictionary in specs:
		if fresh.size() >= wanted:
			break
		var person := Person.new()
		person.key = spec.key
		person.role = spec.role
		person.visual = spec.visual
		person.home = spec.home
		person.seed = spec.seed
		person.prop_kind = spec.prop
		if await build_timeline(person, spec.visits, serial):
			fresh.append(person)
		if not await next_slice(serial):
			return
	build_profile["timelines"] = Time.get_ticks_usec() - mark
	# The new plan takes over: each person keeps its model, look and pose.
	var previous := {}
	for person in people:
		previous[person.key] = person
	for person in fresh:
		var old: Person = previous.get(person.key)
		if old != null and old.visual == person.visual and old.rig != null and is_instance_valid(old.rig):
			person.adopt(old)
			previous.erase(person.key)
	for key in previous:
		var old: Person = previous[key]
		if old.rig != null and is_instance_valid(old.rig):
			old.rig.queue_free()
		old.rig = null
	people = fresh
	for person in people:
		ensure_rig(person)
	ensure_blobs()
	building = false
	last_build_usec = Time.get_ticks_usec() - started

## Next slice of a background plan; false when a newer plan has started or the town is gone.
func next_slice(serial: int) -> bool:
	if sync_build or Time.get_ticks_usec() - slice_start < SLICE_USEC:
		return serial == build_serial
	if not is_inside_tree():
		return false
	await get_tree().process_frame
	if not is_instance_valid(self) or not is_inside_tree():
		return false
	slice_start = Time.get_ticks_usec()
	last_build_frames += 1
	return serial == build_serial

func _exit_tree() -> void:
	# A plan still running stops at its next slice; the town is planned again when back.
	if building:
		seen.clear()
	build_serial += 1
	building = false

func lot_type(lot: Dictionary) -> String:
	return str(stage.city_base_type(str(lot.get("type", ""))))

func collect_obstacles() -> void:
	bodies.clear()
	posts.clear()
	blocked_rects.clear()
	extra_trees.clear()
	lot_base.clear()
	for lot: Dictionary in plan.lots:
		bodies.append((lot.body as Rect2))
		lot_base.append(lot_type(lot))
		# Gate posts of the yard (as src/town_ground.gd draws them).
		var level := int(lot.level)
		if TownPlan.own_square(lot) or level < (3 if lot.hall else 4):
			continue
		var r: Rect2 = lot.rect
		var z := r.end.y - 0.3
		for side: float in [-1.0, 1.0]:
			var p := Vector2(float(lot.door_x) + side * (TownPlan.DOOR_GAP * 0.5 + TownGround.POST * 0.5), z)
			if not TownPlan.inside(r, 0.1, p):
				continue
			if not lot.hall and stage.town.on_street(plan, p, 0.3):
				continue
			if lot.hall and stage.town.on_street(plan, p, 0.2) and not plan.plaza.has_point(p):
				continue
			posts.append(p)
	if district is Dictionary:
		blocked_rects.append(Rect2(float(district.x) - 16.3, float(district.z) - 13.3, 32.6, 26.6))
	if not stage.parade_slots.is_empty():
		var low := Vector2(INF, INF)
		var high := Vector2(-INF, -INF)
		for slot: Dictionary in stage.parade_slots:
			var p: Vector3 = slot.get("position", Vector3.ZERO)
			low = low.min(Vector2(p.x, p.z))
			high = high.max(Vector2(p.x, p.z))
		blocked_rects.append(Rect2(low, high - low).grow(1.6))
	for works in [stage.works, stage.works2]:
		if str(works.builder_site).is_empty() or not is_instance_valid(works.site_node):
			continue
		var c: Vector3 = works.site_node.position
		var box: AABB = works.site_box
		var reach := maxf(maxf(absf(box.position.x), absf(box.end.x)), maxf(absf(box.position.z), absf(box.end.z)))
		var hx := clampf(reach, 3.0, 7.5)
		blocked_rects.append(Rect2(c.x - hx - 2.6, c.z - hx - 1.0, hx * 2.0 + 4.2, hx * 2.0 + 5.4))
	# 1022 world layer: its natural trees are not in standing_tree_cells.
	var world: Variant = stage.forest_world
	if world != null and is_instance_valid(world):
		var layout: Variant = world.get("layout")
		if layout is Dictionary:
			for item in layout.get("trees", []):
				var p := Vector2(float(item[0]), float(item[1]))
				if absf(p.x) > 66.0 or absf(p.y) > 66.0:
					continue
				var cell := Vector2i(floori(p.x / 4.0), floori(p.y / 4.0))
				if not extra_trees.has(cell):
					extra_trees[cell] = []
				extra_trees[cell].append(p)

func near_tree(p: Vector2) -> bool:
	if stage.near_standing_tree(p, TREE_CLEAR * TREE_CLEAR):
		return true
	if extra_trees.is_empty():
		return false
	var cell := Vector2i(floori(p.x / 4.0), floori(p.y / 4.0))
	for z in range(-1, 2):
		for x in range(-1, 2):
			for tree: Vector2 in extra_trees.get(cell + Vector2i(x, z), []):
				if p.distance_squared_to(tree) < TREE_CLEAR * TREE_CLEAR:
					return true
	return false

## Walkability memo of the current plan: 25 cm cells (0 unknown, 1 clear, 2 blocked), each
## the test at the cell centre (TREE_CLEAR keeps >= 0.92 m with the half diagonal).
const MEMO_CELL := 0.25
const MEMO_SIZE := 512
var memo := PackedByteArray()

func walkable(p: Vector2) -> bool:
	var i := floori((p.x + 64.0) / MEMO_CELL)
	var j := floori((p.y + 64.0) / MEMO_CELL)
	if i < 0 or j < 0 or i >= MEMO_SIZE or j >= MEMO_SIZE or memo.is_empty():
		return false
	var k := j * MEMO_SIZE + i
	var known := memo[k]
	if known == 0:
		var centre := Vector2((i + 0.5) * MEMO_CELL - 64.0, (j + 0.5) * MEMO_CELL - 64.0)
		known = 1 if clear_at(centre, bodies, posts) else 2
		memo[k] = known
	return known == 1

## One walkable point: on drawn town ground, dry, inside the wall, clear of bodies, posts,
## trees, the troop ground, the parade and building sites.
func clear_at(p: Vector2, near_bodies: Array, near_posts: PackedVector2Array) -> bool:
	if absf(p.x) > 62.0 or absf(p.y) > 62.0 or not painted(p.x, p.y):
		return false
	if ground_y(p.x, p.y) - TownGround.LIFT < -0.2:
		return false
	var walls = stage.walls
	if walls.visible and not walls.inside(p.x, p.y, 1.4):
		return false
	for rect: Rect2 in blocked_rects:
		if rect.has_point(p):
			return false
	if solid_at(p):
		return false
	for rect: Rect2 in near_bodies:
		if rect.has_point(p):
			# A footprint is the box round the whole model (yard fences, drill grounds): where
			# the town plan lays a street through an empty corner of it, the street is walked.
			if not on_street_band(p):
				return false
			break
	for post in near_posts:
		if p.distance_squared_to(post) < POST_CLEAR * POST_CLEAR:
			return false
	return not near_tree(p)

## CityWorks: a lumberjack's walk from `far` to `near` metres out from a trunk along `dir`:
## clear of other trunks (1 m), buildings, posts, water, the wall, the troop ground and sites.
func approach_clear(trunk: Vector2, dir: Vector2, near: float, far: float) -> bool:
	var walls = stage.walls
	var steps := ceili((far - near) / 0.3)
	for k in range(steps + 1):
		var p := trunk + dir * lerpf(near, far, float(k) / steps)
		if solid_at(p) or stage.sample_city(p.x, p.y) < -0.2:
			return false
		if walls.visible and absf(p.distance_to(walls.center) - walls.radius_at(p.x, p.y)) < 1.8:
			return false
		for rect: Rect2 in blocked_rects:
			if rect.has_point(p):
				return false
		for lot: Dictionary in plan.lots if plan != null else []:
			if (lot.body as Rect2).has_point(p):
				return false
		for post in posts:
			if p.distance_squared_to(post) < POST_CLEAR * POST_CLEAR:
				return false
		var cell := Vector2i(floori(p.x / 4.0), floori(p.y / 4.0))
		for z in range(-1, 2):
			for x in range(-1, 2):
				for tree: Vector2 in stage.standing_tree_cells.get(cell + Vector2i(x, z), []):
					if tree.distance_squared_to(trunk) > 0.01 and p.distance_squared_to(tree) < 1.0:
						return false
				for tree: Vector2 in extra_trees.get(cell + Vector2i(x, z), []):
					if tree.distance_squared_to(trunk) > 0.01 and p.distance_squared_to(tree) < 1.0:
						return false
	return true

## On the paved band of a street (not a gate road).
func on_street_band(p: Vector2) -> bool:
	for s: Array in street_segs:
		var q := Geometry2D.get_closest_point_to_segment(p, s[0], s[1])
		if p.distance_squared_to(q) <= float(s[2]) * float(s[2]):
			return true
	return false

## QA: why a point is not walkable ("" when it is).
func blocked_reason(p: Vector2) -> String:
	if absf(p.x) > 62.0 or absf(p.y) > 62.0:
		return "outside"
	if not painted(p.x, p.y):
		return "unpainted"
	if ground_y(p.x, p.y) - TownGround.LIFT < -0.2:
		return "water"
	if stage.walls.visible and not stage.walls.inside(p.x, p.y, 1.4):
		return "wall"
	for rect: Rect2 in blocked_rects:
		if rect.has_point(p):
			return "blocked_rect"
	if solid_at(p):
		return "solid"
	for i in bodies.size():
		if bodies[i].has_point(p) and not on_street_band(p):
			return "body:%d" % i
	for post in posts:
		if p.distance_squared_to(post) < POST_CLEAR * POST_CLEAR:
			return "post"
	if near_tree(p):
		return "tree"
	return ""

func nearby(a: Vector2, b: Vector2, reach: float) -> Array:
	var box := Rect2(a, Vector2.ZERO).expand(b).grow(reach + 1.0)
	var near_bodies: Array = []
	for rect in bodies:
		if rect.intersects(box):
			near_bodies.append(rect)
	var near_posts := PackedVector2Array()
	for post in posts:
		if box.grow(POST_CLEAR).has_point(post):
			near_posts.append(post)
	return [near_bodies, near_posts]

## The segment a-b walked anywhere within +-lateral of its line.
func band_clear(a: Vector2, b: Vector2, lateral: float, avoid := PackedVector2Array(), berth := 0.9) -> bool:
	var length := a.distance_to(b)
	if length < 0.01:
		return true
	var dir := (b - a) / length
	var right := Vector2(-dir.y, dir.x)
	var steps := maxi(1, ceili(length / SAMPLE_STEP))
	var offsets := [0.0] if lateral < 0.02 else [0.0, -lateral, lateral]
	for k in range(steps + 1):
		var c := a + dir * (length * k / steps)
		for o: float in offsets:
			var p: Vector2 = c + right * o
			if not walkable(p):
				return false
			for q in avoid:
				if p.distance_squared_to(q) < berth * berth:
					return false
	return true

func add_node(p: Vector2) -> int:
	var cell := Vector2i(roundi(p.x / 0.2), roundi(p.y / 0.2))
	for dz in range(-1, 2):
		for dx in range(-1, 2):
			for n: int in node_cells.get(cell + Vector2i(dx, dz), []):
				if g_nodes[n].distance_squared_to(p) < 0.0064:
					return n
	g_nodes.append(p)
	if not node_cells.has(cell):
		node_cells[cell] = []
	node_cells[cell].append(g_nodes.size() - 1)
	return g_nodes.size() - 1

## kind: 0 street (its band is the plan's), 1 yard path to a door, 2 across the square.
func add_edge(a: int, b: int, lateral: float, kind := 0) -> int:
	if a == b:
		return -1
	var key := mini(a, b) * 100000 + maxi(a, b)
	if edge_keys.has(key):
		var e: int = edge_keys[key]
		e_lat[e] = maxf(e_lat[e], lateral)
		e_kind[e] = mini(e_kind[e], kind)
		return e
	e_a.append(a)
	e_b.append(b)
	e_lat.append(lateral)
	e_live.append(1)
	e_kind.append(kind)
	e_shift.append(0.0)
	edge_keys[key] = e_a.size() - 1
	return e_a.size() - 1

func build_graph(serial := -1) -> bool:
	g_nodes = PackedVector2Array()
	e_a = PackedInt32Array()
	e_b = PackedInt32Array()
	e_lat = PackedFloat32Array()
	e_live = PackedByteArray()
	e_kind = PackedByteArray()
	e_shift = PackedFloat32Array()
	edge_keys.clear()
	node_cells.clear()
	door_node.clear()
	door_stop.clear()
	door_lot.clear()
	door_in.clear()
	door_room.clear()
	spot_nodes = PackedInt32Array()
	yard_spots.clear()
	square_nodes.clear()
	var g_mark := Time.get_ticks_usec()
	# Streets: centre lines split at every crossing and junction (gate roads run outside the wall).
	var segs: Array = []
	for s: Dictionary in plan.segments:
		if s.gate or (s.a as Vector2).distance_to(s.b) < 0.05:
			continue
		segs.append([s.a, s.b, float(s.w) * 0.5])
	street_segs = segs
	for s in segs:
		add_node(s[0])
		add_node(s[1])
	for i in segs.size():
		for j in range(i + 1, segs.size()):
			var hit: Variant = Geometry2D.segment_intersects_segment(segs[i][0], segs[i][1], segs[j][0], segs[j][1])
			if hit is Vector2:
				add_node(hit)
	for s in segs:
		var a: Vector2 = s[0]
		var d: Vector2 = s[1] - a
		var box := Rect2(a, Vector2.ZERO).expand(s[1]).grow(0.1)
		var along: Array = []
		for n in g_nodes.size():
			var q := g_nodes[n]
			if not box.has_point(q):
				continue
			var t := clampf((q - a).dot(d) / d.length_squared(), 0.0, 1.0)
			if (a + d * t).distance_squared_to(q) < 0.0064:
				along.append([t, n])
		along.sort_custom(func(x, y): return x[0] < y[0])
		for k in range(1, along.size()):
			add_edge(along[k - 1][1], along[k][1], maxf(0.0, float(s[2]) - EDGE_MARGIN))
	build_profile["g_streets"] = Time.get_ticks_usec() - g_mark
	g_mark = Time.get_ticks_usec()
	# Doors: from the yard's street exit to a stop in front of the building.
	var square: Rect2 = plan.plaza
	var on_square: Array = []
	for li in plan.lots.size():
		var lot: Dictionary = plan.lots[li]
		var body: Rect2 = lot.body
		var r: Rect2 = lot.rect
		var stop := Vector2(float(lot.door_x), body.end.y + (0.75 if lot.hall else 0.55))
		var exit: Vector2 = lot.get("exit", plan.door_of(lot))
		var back: bool = not lot.hall and absf(exit.y - r.position.y) < 0.15
		if back:
			# The lane leaves from the back of the yard: the back door.
			stop = Vector2(exit.x, body.position.y - 0.5)
		if not TownPlan.inside(r.grow(0.05), 0.2, stop) and not (lot.hall and square.has_point(stop)):
			continue
		door_in[li] = Vector2(0.0, 1.0) if back else Vector2(0.0, -1.0)
		if lot.hall and square.has_area() and square.grow(-0.3).has_point(stop):
			# The hall's door opens on the square: people come up to it from straight in front.
			var n := add_node(stop)
			var front := stop + Vector2(0.0, 1.4)
			if square.grow(-0.2).has_point(front):
				var approach := add_node(front)
				add_edge(approach, n, DOOR_BAND, 1)
				on_square.append(approach)
			else:
				on_square.append(n)
			door_node[li] = n
			door_stop[li] = stop
			door_lot[n] = li
			continue
		var entry := -1
		for n in g_nodes.size():
			if g_nodes[n].distance_to(exit) < 0.3:
				entry = n
				break
		if entry < 0:
			continue
		# The last stretch to a door is straight and long enough for a lead point.
		var mid_z := clampf(stop.y + 1.15, (body.end.y + r.end.y) * 0.5, r.end.y - 0.75) if not back else stop.y
		var way: Array = [exit]
		if back:
			pass
		elif absf(exit.y - r.end.y) < 0.15:
			if absf(exit.x - stop.x) > 0.05:
				way.append(Vector2(exit.x, mid_z))
				way.append(Vector2(stop.x, mid_z))
		else:
			# A side exit: straight across the forecourt when it is clear, else round its edge.
			var inward := 0.6 if exit.x < r.get_center().x else -0.6
			var across := Vector2(stop.x, mid_z)
			if band_clear(exit, across, 0.2):
				way.append(across)
			else:
				way.append(Vector2(exit.x + inward, exit.y))
				way.append(Vector2(exit.x + inward, mid_z))
				way.append(across)
		way.append(stop)
		var previous := entry
		for k in range(1, way.size()):
			var n := add_node(way[k])
			add_edge(previous, n, DOOR_BAND, 1)
			previous = n
		door_node[li] = previous
		door_stop[li] = stop
		door_lot[previous] = li
		door_room[li] = (way[way.size() - 1] as Vector2).distance_to(way[way.size() - 2])
		# Beside the door path, in the forecourt: places to stop and look at the building.
		if not back:
			var look_z := (body.end.y + r.end.y) * 0.5
			for side: float in [-1.0, 1.0]:
				for step: float in [2.6, 3.4]:
					var q := Vector2(stop.x + side * step, look_z)
					if not TownPlan.inside(r, 0.6, q) or not walkable(q):
						continue
					var far := true
					for post in posts:
						if post.distance_to(q) < 1.2:
							far = false
					if not far:
						continue
					var joined_to := -1
					for w in range(way.size() - 1, -1, -1):
						var at: Vector2 = way[w]
						if at.distance_to(stop) > 0.6 and band_clear(at, q, 0.0):
							joined_to = add_node(at)
							break
					if joined_to < 0:
						continue
					var n := add_node(q)
					add_edge(joined_to, n, 0.0, 1)
					yard_spots[n] = atan2(door_in[li].x, door_in[li].y)
					break
	build_profile["g_doors"] = Time.get_ticks_usec() - g_mark
	g_mark = Time.get_ticks_usec()
	# The town square: open ground, every point on it joins every other in a straight line.
	if square.has_area():
		var hall_stop: Variant = null
		for li in door_lot.values():
			if plan.lots[li].hall:
				hall_stop = door_stop[li]
		var rng := RandomNumberGenerator.new()
		rng.seed = hash(str(square))
		var wanted := clampi(int(square.get_area() / 12.0), 1, 5)
		var tries := 0
		while spot_nodes.size() < wanted and tries < 60:
			tries += 1
			var p := Vector2(rng.randf_range(square.position.x + 1.2, square.end.x - 1.2), rng.randf_range(square.position.y + 1.4, square.end.y - 1.0))
			if hall_stop is Vector2 and p.distance_to(hall_stop) < 2.6:
				continue
			var far := true
			for n in spot_nodes:
				if g_nodes[n].distance_to(p) < 2.4:
					far = false
			var near: Array = nearby(p, p, 1.0)
			if not far or not clear_at(p, near[0], near[1]):
				continue
			spot_nodes.append(add_node(p))
		for n in g_nodes.size():
			# Door stops are reached by their own path (the hall's from straight in front).
			if square.grow(0.2).has_point(g_nodes[n]) and not on_square.has(n) and not door_lot.has(n):
				on_square.append(n)
		for n in on_square:
			square_nodes[n] = true
		# Each point of the square is joined straight to its nearest few (enough to cross it
		# in any direction without checking every pair).
		for n: int in on_square:
			var others: Array = on_square.filter(func(m): return m != n)
			others.sort_custom(func(x, y): return g_nodes[x].distance_squared_to(g_nodes[n]) < g_nodes[y].distance_squared_to(g_nodes[n]))
			for m: int in others.slice(0, 6):
				add_edge(n, m, SQUARE_BAND, 2)
	build_profile["g_square"] = Time.get_ticks_usec() - g_mark
	g_mark = Time.get_ticks_usec()
	var g_slept := 0
	# Keep only edges whose band is clear (narrowing the band where needed).
	var spots := PackedVector2Array()
	for n in spot_nodes:
		spots.append(g_nodes[n])
	# ... and the places in front of the hall's door where people wait.
	var hall_front := PackedVector2Array()
	for li in door_lot.values():
		if plan.lots[li].hall:
			for k in range(-2, 3):
				hall_front.append(door_stop[li] + Vector2(0.95 * k, 0.0))
			# ... and the way up to it (its front point).
			hall_front.append(door_stop[li] + Vector2(0.0, 1.1))
	for e in e_a.size():
		var before := Time.get_ticks_usec()
		if serial >= 0 and not await next_slice(serial):
			return false
		g_slept += Time.get_ticks_usec() - before
		var a := g_nodes[e_a[e]]
		var b := g_nodes[e_b[e]]
		var avoid := PackedVector2Array()
		var avoid_far := PackedVector2Array()
		if square_nodes.has(e_a[e]) and square_nodes.has(e_b[e]):
			for q in spots:
				if q.distance_to(a) > 0.1 and q.distance_to(b) > 0.1:
					avoid.append(q)
					avoid_far.append(q)
			for q in hall_front:
				if q.distance_to(a) > 1.0 and q.distance_to(b) > 1.0:
					avoid.append(q)
		var lateral := e_lat[e]
		var found := -1.0
		for k: float in [1.0, 0.6, 0.3, 0.0]:
			# People standing on a spot of the square are passed at a good step.
			if band_clear(a, b, lateral * k, avoid) and (avoid_far.is_empty() or band_clear(a, b, 0.0, avoid_far, 1.15 + lateral * k)):
				found = lateral * k
				break
		if found < 0.0 and lateral > 0.2:
			# One side of the street is taken (a fence, a corner of a building): walk the other.
			var right := Vector2(-(b - a).y, (b - a).x).normalized()
			for shift: float in [lateral * 0.5, -lateral * 0.5, lateral, -lateral]:
				if band_clear(a + right * shift, b + right * shift, 0.0, avoid) \
						and band_clear(a, a + right * shift, 0.0, avoid) and band_clear(b, b + right * shift, 0.0, avoid):
					e_shift[e] = shift
					found = 0.0
					break
		if found < 0.0:
			e_live[e] = 0
		else:
			e_lat[e] = found
	build_profile["g_validate"] = Time.get_ticks_usec() - g_mark - g_slept
	build_profile["g_edges"] = e_a.size()
	g_edges.clear()
	for n in g_nodes.size():
		g_edges.append(PackedInt32Array())
	for e in e_a.size():
		if e_live[e] == 1:
			g_edges[e_a[e]].append(e)
			g_edges[e_b[e]].append(e)
	# Parts of the network that reach each other (a street laid through a fence cuts the town).
	component = PackedInt32Array()
	component.resize(g_nodes.size())
	component.fill(-1)
	var part := 0
	for n in g_nodes.size():
		if component[n] >= 0:
			continue
		var stack := PackedInt32Array([n])
		component[n] = part
		while not stack.is_empty():
			var m := stack[stack.size() - 1]
			stack.resize(stack.size() - 1)
			for e in g_edges[m]:
				var o := e_b[e] if e_a[e] == m else e_a[e]
				if component[o] < 0:
					component[o] = part
					stack.append(o)
		part += 1
	return true

## Shortest node path (Dijkstra, binary heap), [] when unreachable.
func route(from: int, to: int) -> PackedInt32Array:
	var key := from * 100000 + to
	if route_cache.has(key):
		return route_cache[key]
	var count := g_nodes.size()
	var dist := PackedFloat32Array()
	dist.resize(count)
	dist.fill(INF)
	var prev := PackedInt32Array()
	prev.resize(count)
	prev.fill(-1)
	var heap_d := PackedFloat32Array()
	var heap_n := PackedInt32Array()
	dist[from] = 0.0
	heap_push(heap_d, heap_n, 0.0, from)
	while not heap_n.is_empty():
		var d := heap_d[0]
		var n := heap_pop(heap_d, heap_n)
		if d > dist[n]:
			continue
		if n == to:
			break
		for e in g_edges[n]:
			var m := e_b[e] if e_a[e] == n else e_a[e]
			var nd := d + g_nodes[n].distance_to(g_nodes[m]) + (0.6 if square_nodes.has(m) and square_nodes.has(n) else 0.0)
			if nd < dist[m]:
				dist[m] = nd
				prev[m] = n
				heap_push(heap_d, heap_n, nd, m)
	var out := PackedInt32Array()
	if from != to and prev[to] < 0:
		route_cache[key] = out
		return out
	var n := to
	while n >= 0:
		out.append(n)
		if n == from:
			break
		n = prev[n]
	out.reverse()
	route_cache[key] = out
	return out

static func heap_push(keys: PackedFloat32Array, values: PackedInt32Array, k: float, v: int) -> void:
	keys.append(k)
	values.append(v)
	var i := keys.size() - 1
	while i > 0:
		var parent := (i - 1) >> 1
		if keys[parent] <= keys[i]:
			break
		var tk := keys[parent]
		keys[parent] = keys[i]
		keys[i] = tk
		var tv := values[parent]
		values[parent] = values[i]
		values[i] = tv
		i = parent

static func heap_pop(keys: PackedFloat32Array, values: PackedInt32Array) -> int:
	var top := values[0]
	var last := keys.size() - 1
	keys[0] = keys[last]
	values[0] = values[last]
	keys.resize(last)
	values.resize(last)
	var i := 0
	while true:
		var l := i * 2 + 1
		var r := l + 1
		var smallest := i
		if l < last and keys[l] < keys[smallest]:
			smallest = l
		if r < last and keys[r] < keys[smallest]:
			smallest = r
		if smallest == i:
			break
		var tk := keys[smallest]
		keys[smallest] = keys[i]
		keys[i] = tk
		var tv := values[smallest]
		values[smallest] = values[i]
		values[i] = tv
		i = smallest
	return top

func route_length(a: int, b: int) -> float:
	var nodes := route(a, b)
	if nodes.is_empty():
		return INF
	var total := 0.0
	for i in range(1, nodes.size()):
		total += g_nodes[nodes[i - 1]].distance_to(g_nodes[nodes[i]])
	return total

func edge_between(a: int, b: int) -> int:
	return edge_keys.get(mini(a, b) * 100000 + maxi(a, b), -1)

## The walked line of a node route: offset to the right of the walking direction by this
## person's share of each edge's free band, corners rounded; starts and ends on the stops.
func walk_line(nodes: PackedInt32Array, side: float, start: Vector2, finish: Vector2, round_corners := true,
		start_lead := Vector2.INF, finish_lead := Vector2.INF, radius := 0.8) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var count := nodes.size()
	if count < 2:
		pts.append(start)
		if start_lead != Vector2.INF:
			pts.append(start_lead)
		if finish_lead != Vector2.INF and finish_lead != start_lead:
			pts.append(finish_lead)
		pts.append(finish)
		return pts
	var dirs: Array[Vector2] = []
	var offs := PackedFloat32Array()
	for i in range(count - 1):
		var a := g_nodes[nodes[i]]
		var b := g_nodes[nodes[i + 1]]
		dirs.append((b - a).normalized() if a.distance_to(b) > 0.001 else Vector2.ZERO)
		var e := edge_between(nodes[i], nodes[i + 1])
		var shift := 0.0
		if e >= 0:
			shift = e_shift[e] if e_a[e] == nodes[i] else -e_shift[e]
		offs.append(e_lat[e] * side + shift if e >= 0 else 0.0)
	# A lead point never goes past the first (last) street node, or the line would double back.
	var first_edge := g_nodes[nodes[0]].distance_to(g_nodes[nodes[1]])
	var last_edge := g_nodes[nodes[count - 1]].distance_to(g_nodes[nodes[count - 2]])
	if start_lead != Vector2.INF:
		var reach := minf(start.distance_to(start_lead), first_edge - 0.25)
		start_lead = start + (start_lead - start).normalized() * reach if reach >= 0.4 else Vector2.INF
	if finish_lead != Vector2.INF:
		var reach := minf(finish.distance_to(finish_lead), last_edge - 0.25)
		finish_lead = finish + (finish_lead - finish).normalized() * reach if reach >= 0.4 else Vector2.INF
	var raw := PackedVector2Array()
	raw.append(start)
	if start_lead != Vector2.INF:
		raw.append(start_lead)
	for i in range(1, count - 1):
		var n := g_nodes[nodes[i]]
		var d1: Vector2 = dirs[i - 1]
		var d2: Vector2 = dirs[i]
		var r1 := Vector2(-d1.y, d1.x)
		var r2 := Vector2(-d2.y, d2.x)
		var cross := d1.cross(d2)
		if absf(cross) < 0.25:
			raw.append(n + r1 * offs[i - 1])
			if absf(offs[i] - offs[i - 1]) > 0.02 or d1.dot(d2) < 0.0:
				raw.append(n + r2 * offs[i])
			continue
		# Corner: where the two offset lines meet.
		var p1 := n + r1 * offs[i - 1]
		var p2 := n + r2 * offs[i]
		var t := (p2 - p1).cross(d2) / cross
		var corner := p1 + d1 * t
		raw.append(corner if corner.distance_to(n) < 2.5 else n)
	if finish_lead != Vector2.INF:
		raw.append(finish_lead)
	raw.append(finish)
	# Offsets on short connector edges can fold the line back on itself: such a vertex goes
	# (the lead points lie on the route, so only offset corners can fold).
	var folded := true
	while folded and raw.size() > 2:
		folded = false
		for i in range(1, raw.size() - 1):
			var d1 := raw[i] - raw[i - 1]
			var d2 := raw[i + 1] - raw[i]
			if d1.length_squared() > 0.000001 and d2.length_squared() > 0.000001 and absf(d1.angle_to(d2)) > 2.0:
				raw.remove_at(i)
				folded = true
				break
	if not round_corners:
		return raw
	# Short pieces (connectors between a yard and a street, jogs between offsets) merge into
	# one point, so the corners round over real lengths instead of zigzagging.
	var merged := true
	while merged and raw.size() > 2:
		merged = false
		for i in range(1, raw.size() - 1):
			var last := i == raw.size() - 2
			if raw[i].distance_to(raw[i + 1]) < 0.35 and not last:
				raw[i] = (raw[i] + raw[i + 1]) * 0.5
				raw.remove_at(i + 1)
				merged = true
				break
			if raw[i].distance_to(raw[i - 1]) < 0.2 or (last and raw[i].distance_to(raw[i + 1]) < 0.2):
				raw.remove_at(i)
				merged = true
				break
	pts.append(raw[0])
	for i in range(1, raw.size() - 1):
		var a := raw[i - 1]
		var c := raw[i]
		var b := raw[i + 1]
		var la := a.distance_to(c)
		var lb := c.distance_to(b)
		if la < 0.01 or lb < 0.01:
			continue
		var din := (c - a) / la
		var dout := (b - c) / lb
		if din.dot(dout) > 0.97:
			pts.append(c)
			continue
		var r := minf(radius, minf(la, lb) * 0.45)
		var p0 := c - din * r
		var p2 := c + dout * r
		for k in range(6):
			var t := float(k) / 5.0
			pts.append(p0.lerp(c, t).lerp(c.lerp(p2, t), t))
	pts.append(raw[raw.size() - 1])
	return pts

## No corner of a rounded line turns sharply (offsets that folded the line back).
static func smooth(pts: PackedVector2Array) -> bool:
	for i in range(1, pts.size() - 1):
		var d1 := pts[i] - pts[i - 1]
		var d2 := pts[i + 1] - pts[i]
		if d1.length_squared() > 0.000001 and d2.length_squared() > 0.000001 and absf(d1.angle_to(d2)) > 0.9:
			return false
	return true

func line_clear(pts: PackedVector2Array) -> bool:
	for i in range(pts.size() - 1):
		if not band_clear(pts[i], pts[i + 1], 0.0):
			return false
	return true

# ------------------------------------------------------------------ people and routines

static func seeded(text: String) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(text)
	return rng

func doors_of(types: Array) -> Array:
	var out: Array = []
	for li in door_node:
		if lot_base[li] in types:
			out.append(li)
	out.sort()
	return out

func hall_lot() -> int:
	for li in door_node:
		if plan.lots[li].hall:
			return li
	return -1

## A door with room in front for more than the one person who lives there.
func roomy(li: int) -> bool:
	return plan.lots[li].hall or float(door_room.get(li, 9.0)) >= 0.65

## Both stops on the same part of the street network.
func joined(a: int, b: int) -> bool:
	return a >= 0 and b >= 0 and component[door_node[a]] == component[door_node[b]]

## The first door of the first group that `home` can walk to (any door when home < 0), the
## nearest one first.
var door_load := {}

func first_door(groups: Array, home := -1) -> int:
	for types in groups:
		var best := -1
		var best_d := INF
		for li in doors_of(types):
			if li == home or (home >= 0 and not joined(home, li)) or not roomy(li):
				continue
			# The nearest, a busy door counting as 25 m further per visitor already sent there.
			var d := g_nodes[door_node[li]].distance_to(g_nodes[door_node[home]]) if home >= 0 else float(li)
			d += 25.0 * int(door_load.get(li, 0))
			if d < best_d:
				best_d = d
				best = li
		if best >= 0:
			door_load[best] = int(door_load.get(best, 0)) + 1
			return best
	return -1

## Where a producer takes its goods: the first group it can reach, else the hall, else any door.
func delivery(home: int, groups: Array) -> int:
	var to := first_door(groups, home)
	if to < 0 and joined(home, hall_lot()) and home != hall_lot():
		to = hall_lot()
		door_load[to] = int(door_load.get(to, 0)) + 1
	if to < 0:
		to = first_door([STORE, MARKET, HOUSE, WELL, SMITH, MILITARY, FARM, LUMBER, QUARRY, HERBAL, HOSPITAL], home)
	return to

## A visit: a stop (graph node), what is done there and what is carried away from it.
func visit_door(li: int, action: int, enter: bool, carry_out: bool, drop := false) -> Dictionary:
	return {"node": door_node[li], "lot": li, "action": action, "enter": enter, "carry_out": carry_out, "drop": drop}

func visit_spot(n: int, action: int) -> Dictionary:
	return {"node": n, "lot": -1, "action": action, "enter": false, "carry_out": false, "drop": false}

## The people this town could have, in priority order (rebuild takes as many as the hall
## allows: 6 at I .. 14 at V). Every destination is one the person can walk to from home.
func plan_people() -> Array:
	door_load.clear()
	var specs: Array = []
	var extra: Array = []
	var hall := hall_lot()
	var visuals_used := {}
	var add := func(list: Array, role: String, home: int, visuals: Array, prop: String, visits: Array) -> void:
		if visits.size() < 2:
			return
		var key := "%s|%s" % [role, str(plan.lots[home].id) if home >= 0 else "town"]
		var n := 0
		while specs.any(func(s): return s.key == key + "#%d" % n) or extra.any(func(s): return s.key == key + "#%d" % n):
			n += 1
		key += "#%d" % n
		var rng := seeded(key)
		var visual: String = visuals[rng.randi() % visuals.size()]
		if visuals_used.get(visual, 0) > 2:
			for alternative in visuals:
				if visuals_used.get(alternative, 0) < visuals_used.get(visual, 0):
					visual = alternative
		visuals_used[visual] = visuals_used.get(visual, 0) + 1
		list.append({"key": key, "role": role, "home": home, "visual": visual, "prop": prop, "visits": visits, "seed": hash(key)})
	var deliver := func(list: Array, role: String, home: int, visuals: Array, prop: String, groups: Array, action: int) -> void:
		var to := delivery(home, groups)
		if to >= 0:
			add.call(list, role, home, visuals, prop, [visit_door(home, C_IDLE, true, true), visit_door(to, action, false, false, true)])
	# Producers take their goods to the store (or the market, or the hall).
	for li in doors_of(LUMBER):
		deliver.call(specs, "lumberjack", li, ["quarry_worker", "ferryman"], "log", [STORE, MARKET], C_THANK)
	for li in doors_of(FARM):
		deliver.call(specs, "farmer", li, ["miller"], "sack", [["ECO-02"], STORE, MARKET], C_THANK)
	for li in doors_of(QUARRY):
		deliver.call(specs, "quarryman", li, ["quarry_worker", "cooper"], "stone", [SMITH, STORE], C_REACT)
	for li in doors_of(HERBAL):
		deliver.call(specs, "herbalist", li, ["herbalist"], "basket", [HOSPITAL, MARKET], C_THANK)
	for li in doors_of(STORE):
		deliver.call(specs, "carrier", li, ["cooper", "courier"], "crate", [MARKET], C_THANK)
		break
	# The smith fetches ore or iron and goes back to the forge.
	for li in doors_of(SMITH):
		var from := delivery(li, [QUARRY, STORE])
		if from >= 0:
			add.call(specs, "smith", li, ["cooper"], "ore", [visit_door(li, C_IDLE, true, false), visit_door(from, C_LOOK, false, true)])
	# The hall's steward walks round the town and back; a messenger runs from the barracks.
	if hall >= 0:
		var rounds: Array = [visit_door(hall, C_IDLE, true, false)]
		var others: Array = door_node.keys().filter(func(li): return li != hall and not lot_base[li] in HOUSE and joined(hall, li) and roomy(li))
		others.sort()
		var rng := seeded("steward")
		for k in mini(2, others.size()):
			var pick: int = others[rng.randi() % others.size()]
			others.erase(pick)
			rounds.append(visit_door(pick, C_LOOK if k == 0 else C_THANK, false, false))
		add.call(specs, "steward", hall, ["courier", "miller"], "", rounds)
	for li in doors_of(MILITARY):
		# To the hall, unless its door is already busy with deliveries.
		var to := hall if joined(li, hall) and int(door_load.get(hall, 0)) < 2 else first_door([STORE, SMITH, MARKET, HOUSE, FARM, LUMBER], li)
		if to >= 0:
			add.call(specs, "messenger", li, ["courier", "ferryman"], "", [visit_door(li, C_IDLE, true, false), visit_door(to, C_REACT, false, false)])
		break
	# Strollers: the square, the houses, the market and the well (one part of town each, the
	# biggest part first).
	var parts := {}
	var spots_all: Array = Array(spot_nodes) + yard_spots.keys()
	for n in spots_all:
		if g_edges[n].is_empty():
			continue
		var c: int = component[n]
		if not parts.has(c):
			parts[c] = []
		parts[c].append(visit_spot(n, C_LOOK if n % 3 != 0 else C_IDLE))
	var spots_taken := {}
	var ranked: Array = parts.keys().filter(func(c): return parts[c].size() >= 2)
	ranked.sort_custom(func(a, b): return parts[a].size() > parts[b].size())
	if ranked.is_empty():
		for li in door_node:
			var c: int = component[door_node[li]]
			if not parts.has(c):
				parts[c] = []
			parts[c].append(visit_door(li, C_LOOK, false, false))
		ranked = parts.keys().filter(func(c): return parts[c].size() >= 2)
	for k in 6:
		if ranked.is_empty():
			break
		var places: Array = parts[ranked[k % ranked.size()]]
		var rng := seeded("stroller%d" % k)
		var route_visits: Array = []
		var pool := places.duplicate()
		# A walk round the neighbourhood: each next place among the two nearest left.
		# Spots on the square already taken by another stroller are left to them.
		var own: Array = pool.filter(func(v): return v.lot >= 0 or not spots_taken.has(v.node))
		if own.size() >= 2:
			pool = own
		var here: Dictionary = pool[rng.randi() % pool.size()]
		for step in mini(3, pool.size()):
			pool.erase(here)
			route_visits.append(here)
			if pool.is_empty():
				break
			var from_node: int = here.node
			pool.sort_custom(func(a, b): return route_length(from_node, a.node) < route_length(from_node, b.node))
			here = pool[rng.randi() % mini(2, pool.size())]
		for v in route_visits:
			if v.lot < 0:
				spots_taken[v.node] = true
		add.call(extra if k >= 2 else specs, "stroller", -1, ["herbalist", "ferryman", "courier", "miller"], "", route_visits)
	# Second hands at the bigger workplaces, and the households.
	for li in doors_of(LUMBER) + doors_of(FARM) + doors_of(STORE):
		if int(plan.lots[li].level) >= 3:
			var groups: Array = [MARKET] if lot_base[li] in STORE else [STORE, MARKET]
			var prop := "log" if lot_base[li] in LUMBER else ("sack" if lot_base[li] in FARM else "crate")
			deliver.call(extra, "helper", li, ["ferryman", "quarry_worker", "cooper", "miller"], prop, groups, C_THANK)
	# More errands: a visitor from the hall to the market, the healer, the water carrier.
	var market := first_door([MARKET], hall)
	if hall >= 0 and market >= 0:
		add.call(extra, "visitor", hall, ["courier", "herbalist", "ferryman"], "basket",
			[visit_door(hall, C_IDLE, true, false), visit_door(market, C_THANK, false, true)])
	for li in doors_of(HOSPITAL):
		var to := first_door([HERBAL, MARKET, STORE], li)
		if to >= 0:
			add.call(extra, "healer", li, ["herbalist"], "basket", [visit_door(li, C_IDLE, true, false), visit_door(to, C_LOOK, false, true)])
	for li in doors_of(WELL):
		var to := first_door([HOUSE, MARKET], li)
		if to < 0 and joined(li, hall):
			to = hall
		if to >= 0:
			add.call(extra, "water carrier", li, ["miller", "ferryman"], "sack", [visit_door(li, C_REACT, false, true), visit_door(to, C_IDLE, false, false, true)])
	for li in doors_of(HOUSE):
		var well := first_door([WELL], li)
		var to := well if well >= 0 else delivery(li, [MARKET])
		if to >= 0:
			add.call(extra, "resident", li, ["herbalist", "miller", "ferryman"], "basket" if well >= 0 else "",
				[visit_door(li, C_IDLE, true, false), visit_door(to, C_LOOK, false, well >= 0)])
	specs.append_array(extra)
	return specs

## Turns a list of visits into this person's day: walks, stops, the door and the time inside.
func build_timeline(p: Person, visits: Array, serial := -1) -> bool:
	var rng := seeded(p.key)
	p.scale = rng.randf_range(0.96, 1.04)
	p.pace = rng.randf_range(0.9, 1.1)
	p.side = rng.randf_range(0.7, 1.0)
	p.idle_rate = rng.randf_range(0.9, 1.1)
	var tint: Array = TINTS[rng.randi() % TINTS.size()]
	p.variant = {"tint": {"cloth": tint[0], "hair": tint[1]}, "hide": ["Bag"] if rng.randf() < 0.4 else []}
	p.kinds = PackedInt32Array()
	p.starts = PackedFloat32Array()
	p.lengths = PackedFloat32Array()
	p.leg = PackedInt32Array()
	p.speed = PackedFloat32Array()
	p.clip = PackedInt32Array()
	p.gesture_at = PackedFloat32Array()
	p.carry = PackedInt32Array()
	p.spot_a = PackedVector2Array()
	p.spot_b = PackedVector2Array()
	p.face = PackedFloat32Array()
	p.turn_to = PackedFloat32Array()
	p.paths.clear()
	p.lines.clear()
	p.cums.clear()
	# Where each visit is stood: a slot beside the others who use the same stop, reached
	# straight from a lead point in front of it (so nobody brushes past someone waiting there).
	var spots: Array[Vector2] = []
	var leads: Array[Vector2] = []
	var claims := PackedInt32Array()
	for visit: Dictionary in visits:
		var node: int = visit.node
		# Places are claimed only once the whole day works out (see the end).
		var users: Array = stop_users.get(node, [])
		var slot := users.find(p.key)
		if slot < 0:
			slot = users.size() + int(claims.count(node))
			claims.append(node)
		var base := g_nodes[node]
		# Each user of a door has a place of its own: the middle, then a step either side (three
		# at most; one where the door has no room in front). Everybody comes and goes through the
		# door's front point on its straight approach, so the way to one place keeps a good step
		# from the others. A spot on the square is one person's.
		var spot := Vector2.INF
		var lead := Vector2.INF
		if visit.lot >= 0:
			var outward := -(door_in.get(visit.lot, Vector2(0.0, -1.0)) as Vector2)
			var room := float(door_room.get(visit.lot, 1.4))
			var places := 3 if room >= 0.65 else 1
			if room >= 0.65:
				lead = base + outward * minf(1.1, room - 0.25)
			var free := 0
			for k in places:
				var place := base + Vector2([0.0, -0.95, 0.95][k], 0.0)
				if walkable(place) and (lead == Vector2.INF or k == 0 or band_clear(lead, place, 0.0)):
					if free == slot:
						spot = place
						break
					free += 1
		elif slot == 0:
			spot = base
		if spot == Vector2.INF:
			# Nowhere left to stand at this stop: someone else takes this place in the town.
			crowded += 1
			left_out.append("%s at %s (slot %d, room %.2f)" % [p.key, lot_base[visit.lot] if visit.lot >= 0 else "square", slot, float(door_room.get(visit.lot, -1.0))])
			return false
		spots.append(spot)
		leads.append(lead)
	# Legs: from each visit to the next (cyclic); the person's own side of the street first,
	# then nearer the middle, then the centre line, corners rounded; sharp only as a last resort.
	var count := visits.size()
	var lines: Array[PackedVector2Array] = []
	for i in count:
		var from: Dictionary = visits[i]
		var to: Dictionary = visits[(i + 1) % count]
		var k := (i + 1) % count
		var nodes := route(from.node, to.node)
		if nodes.is_empty() and from.node != to.node:
			dropped_legs += 1
			return false
		var line := PackedVector2Array()
		var found := false
		# [share of the band, corner radius (0 = sharp), with lead points]
		for attempt: Array in [[p.side, 0.8, true], [p.side * 0.5, 0.8, true], [0.0, 0.8, true], [p.side, 0.3, true],
				[0.0, 0.3, true], [0.0, 0.12, true], [0.0, 0.3, false], [0.0, 0.12, false], [0.0, 0.0, true], [0.0, 0.0, false]]:
			var leading: bool = attempt[2]
			line = walk_line(nodes, attempt[0], spots[i], spots[k], attempt[1] > 0.0,
				leads[i] if leading else Vector2.INF, leads[k] if leading else Vector2.INF, attempt[1])
			if (attempt[1] <= 0.12 or smooth(line)) and line_clear(line):
				found = true
				break
		if not found:
			dropped_legs += 1
			left_out.append("%s: no clear line %s -> %s" % [p.key, str(g_nodes[from.node]), str(g_nodes[to.node])])
			return false
		lines.append(line)
		if serial >= 0 and not await next_slice(serial):
			return false
	var dense_mark := Time.get_ticks_usec()
	# Each walked line sampled every 0.35 m with the drawn ground under it: walking is a binary
	# search and a lerp per frame.
	for i in count:
		var line: PackedVector2Array = lines[i]
		var dense := PackedVector3Array()
		for k in range(line.size() - 1):
			var a := line[k]
			var b := line[k + 1]
			var pieces := maxi(1, ceili(a.distance_to(b) / 0.35))
			for m in pieces:
				var q := a.lerp(b, float(m) / pieces)
				dense.append(Vector3(q.x, ground_y(q.x, q.y), q.y))
		var last := line[line.size() - 1]
		dense.append(Vector3(last.x, ground_y(last.x, last.y), last.y))
		var cum := PackedFloat32Array()
		cum.append(0.0)
		for k in range(1, dense.size()):
			var a3 := dense[k - 1]
			var b3 := dense[k]
			cum.append(cum[k - 1] + Vector2(a3.x, a3.z).distance_to(Vector2(b3.x, b3.z)))
		p.paths.append(line)
		p.lines.append(dense)
		p.cums.append(cum)
	build_profile["t_dense"] = build_profile.get("t_dense", 0) + Time.get_ticks_usec() - dense_mark
	var t := 0.0
	for i in count:
		var visit: Dictionary = visits[(i + 1) % count]
		var leaving: Dictionary = visits[i]
		var line: PackedVector2Array = p.paths[i]
		var cum: PackedFloat32Array = p.cums[i]
		var distance := cum[cum.size() - 1]
		var loaded: bool = leaving.carry_out and not p.prop_kind.is_empty() and p.prop_kind in ["log", "stone", "crate", "sack", "ore"]
		var cruise: float = (0.95 if loaded else (0.88 if p.role == "stroller" else 1.12)) * p.pace * p.scale
		var clip_id := C_LOADED if loaded else C_WALK
		var duration := walk_time(distance, cruise)
		var arrive_dir := (line[line.size() - 1] - line[maxi(0, line.size() - 2)]).normalized()
		if distance > 0.05:
			t = add_phase(p, K_WALK, t, duration, i, cruise, clip_id, -1.0, 1 if leaving.carry_out else 0, Vector2.ZERO, Vector2.ZERO, 0.0, 0.0)
		var spot: Vector2 = spots[(i + 1) % count]
		var next_line: PackedVector2Array = p.paths[(i + 1) % count]
		var next_dir := (next_line[mini(1, next_line.size() - 1)] - next_line[0]).normalized()
		var next_yaw := atan2(next_dir.x, next_dir.y) if next_dir != Vector2.ZERO else 0.0
		var inward: Vector2 = door_in.get(visit.lot, Vector2(0.0, -1.0))
		var in_yaw := atan2(inward.x, inward.y)
		var out_yaw := atan2(-inward.x, -inward.y)
		var facing := in_yaw if visit.lot >= 0 else rng.randf_range(-PI, PI)
		var carried_in: bool = leaving.carry_out
		if visit.enter:
			var doorway := spot + inward * STEP_IN
			t = add_phase(p, K_DWELL, t, 0.5, -1, 0.0, C_IDLE, -1.0, 1 if carried_in else 0, spot, spot, in_yaw, in_yaw)
			t = add_phase(p, K_ENTER, t, STEP_SECONDS, -1, 0.0, C_WALK, -1.0, 1 if carried_in else 0, spot, doorway, in_yaw, in_yaw)
			t = add_phase(p, K_INSIDE, t, rng.randf_range(4.0, 10.0), -1, 0.0, C_IDLE, -1.0, 0, doorway, doorway, in_yaw, in_yaw)
			t = add_phase(p, K_LEAVE, t, STEP_SECONDS, -1, 0.0, C_WALK, -1.0, 1 if visit.carry_out else 0, spot, doorway, out_yaw, out_yaw)
			t = add_phase(p, K_DWELL, t, TURN_WINDOW + rng.randf_range(0.3, 1.2), -1, 0.0, C_IDLE, -1.0, 1 if visit.carry_out else 0, spot, spot, out_yaw, next_yaw)
		else:
			var action: int = visit.action
			var dwell := rng.randf_range(2.0, 6.0)
			var gesture := -1.0
			if action != C_IDLE:
				dwell = maxf(dwell, GESTURE_SECONDS[action] + TURN_WINDOW + 0.9)
				gesture = rng.randf_range(0.35, dwell - TURN_WINDOW - GESTURE_SECONDS[action] - 0.2)
			var carry_mode := 0
			if carried_in and visit.drop:
				carry_mode = 2
			elif carried_in or visit.carry_out:
				carry_mode = 1 if carried_in else 3
			if yard_spots.has(visit.node):
				facing = float(yard_spots[visit.node]) + rng.randf_range(-0.5, 0.5)
			elif visit.lot < 0 and arrive_dir != Vector2.ZERO:
				facing = atan2(arrive_dir.x, arrive_dir.y) + rng.randf_range(-1.2, 1.2)
			t = add_phase(p, K_DWELL, t, dwell, -1, 0.0, action, gesture, carry_mode, spot, spot, facing, next_yaw)
	p.cycle = maxf(t, 1.0)
	p.phase = rng.randf() * p.cycle
	for node in claims:
		var users: Array = stop_users.get(node, [])
		if not users.has(p.key):
			users.append(p.key)
		stop_users[node] = users
	return true

func add_phase(p: Person, kind: int, t: float, length: float, leg: int, cruise: float, clip_id: int, gesture: float,
		carry: int, a: Vector2, b: Vector2, face: float, turn: float) -> float:
	p.kinds.append(kind)
	p.starts.append(t)
	p.lengths.append(length)
	p.leg.append(leg)
	p.speed.append(cruise)
	p.clip.append(clip_id)
	p.gesture_at.append(gesture)
	p.carry.append(carry)
	p.spot_a.append(a)
	p.spot_b.append(b)
	p.face.append(face)
	p.turn_to.append(turn)
	return t + length

## Seconds to walk `distance` with RAMP seconds to speed up and to slow down.
static func walk_time(distance: float, cruise: float) -> float:
	if distance >= cruise * RAMP:
		return distance / cruise + RAMP
	return 2.0 * sqrt(distance * RAMP / cruise)

# ------------------------------------------------------------------ per frame

## The person's place, heading, clip and look at clock time t (seconds). No allocations.
func evaluate(p: Person, t: float) -> void:
	var u := fposmod(t + p.phase - p.delay, p.cycle)
	var i := clampi(p.starts.bsearch(u, false) - 1, 0, p.kinds.size() - 1)
	var local := u - p.starts[i]
	p.index = i
	p.local = local
	p.alpha = 1.0
	p.v = 0.0
	p.walking = false
	p.turning = false
	p.clip_offset = 0.0
	match p.kinds[i]:
		K_WALK:
			var line: PackedVector3Array = p.lines[p.leg[i]]
			var cum: PackedFloat32Array = p.cums[p.leg[i]]
			var total := cum[cum.size() - 1]
			var cruise := p.speed[i]
			var duration := p.lengths[i]
			var s := 0.0
			if total >= cruise * RAMP:
				var accel := cruise / RAMP
				if local < RAMP:
					s = 0.5 * accel * local * local
					p.v = accel * local
				elif local < duration - RAMP:
					s = 0.5 * cruise * RAMP + cruise * (local - RAMP)
					p.v = cruise
				else:
					var rest := maxf(duration - local, 0.0)
					s = total - 0.5 * accel * rest * rest
					p.v = accel * rest
			else:
				var accel := cruise / RAMP
				var half := duration * 0.5
				if local < half:
					s = 0.5 * accel * local * local
					p.v = accel * local
				else:
					var rest := maxf(duration - local, 0.0)
					s = total - 0.5 * accel * rest * rest
					p.v = accel * rest
			s = clampf(s, 0.0, total)
			p.walked = s
			# Held back behind someone: the clock (and so the walk) runs slower.
			p.v *= 1.0 - p.hold
			var j := clampi(cum.bsearch(s, false) - 1, 0, line.size() - 2)
			var piece := cum[j + 1] - cum[j]
			var a := line[j]
			var b := line[j + 1]
			var here := a.lerp(b, (s - cum[j]) / piece if piece > 0.0001 else 0.0)
			p.at = Vector2(here.x, here.z)
			p.y = here.y
			p.ground_at = p.at
			if piece > 0.001:
				p.want_yaw = atan2(b.x - a.x, b.z - a.z)
			p.walking = true
			p.clip_want = p.clip[i] if p.v > 0.12 else C_IDLE
			p.carrying = p.carry[i] != 0
		K_DWELL:
			p.at = p.spot_a[i]
			var turn_at := p.lengths[i] - TURN_WINDOW
			p.want_yaw = p.face[i] if local < turn_at else p.turn_to[i]
			p.turning = local >= turn_at
			var gesture := p.gesture_at[i]
			var action := p.clip[i]
			p.clip_want = C_IDLE
			if gesture >= 0.0 and local >= gesture and local < gesture + GESTURE_SECONDS[action]:
				p.clip_want = action
				p.clip_offset = local - gesture
			match p.carry[i]:
				0: p.carrying = false
				1: p.carrying = true
				2: p.carrying = gesture < 0.0 or local < gesture + 0.5
				3: p.carrying = gesture >= 0.0 and local >= gesture + 0.5
		K_ENTER:
			var k := local / p.lengths[i]
			p.at = p.spot_a[i].lerp(p.spot_b[i], k)
			p.alpha = clampf(1.0 - k * 1.15, 0.0, 1.0)
			p.want_yaw = p.face[i]
			p.v = STEP_IN / STEP_SECONDS
			p.clip_want = C_WALK
			p.carrying = p.carry[i] != 0
		K_INSIDE:
			p.at = p.spot_a[i]
			p.alpha = 0.0
			p.clip_want = C_IDLE
			p.carrying = false
		K_LEAVE:
			var k := local / p.lengths[i]
			p.at = p.spot_b[i].lerp(p.spot_a[i], k)
			p.alpha = clampf(k * 1.15 - 0.15, 0.0, 1.0)
			p.want_yaw = p.face[i]
			p.v = STEP_IN / STEP_SECONDS
			p.clip_want = C_WALK
			p.carrying = p.carry[i] != 0
	if p.at != p.ground_at:
		p.ground_at = p.at
		p.y = ground_y(p.at.x, p.at.y)

## Walkers meeting on the street: someone right behind another one going the same way slows
## to the other's pace (its clock runs slower, so the walk clip slows with it); the time is
## made up while standing idle, inside or off screen. Walkers coming towards each other keep
## to their right (walk_line); people waiting at a stop stand in slots of their own, reached
## straight from in front.
var walkers := PackedInt32Array()
var hold_dt := 0.0

func hold_back(dt: float) -> void:
	var count := people.size()
	walkers.resize(0)
	for i in count:
		if people[i].walking and people[i].alpha >= 0.5:
			walkers.append(i)
	for i in count:
		var p := people[i]
		if not p.walking or p.v < 0.05:
			p.hold = 0.0
			if p.delay > 0.0 and (p.kinds[p.index] == K_INSIDE or not p.shown or (p.kinds[p.index] == K_DWELL and p.clip_want == C_IDLE \
					and not p.turning and p.local + dt * 2.0 < p.lengths[p.index] - TURN_WINDOW \
					and (p.gesture_at[p.index] < 0.0 or p.local > p.gesture_at[p.index] + GESTURE_SECONDS[p.clip[p.index]]))):
				p.delay = maxf(0.0, p.delay - dt)
			continue
		var fx := sin(p.want_yaw)
		var fz := cos(p.want_yaw)
		var target := 0.0
		var own := p.v / maxf(0.05, 1.0 - p.hold)
		for j in walkers:
			if j == i:
				continue
			var q := people[j]
			# Nobody waits for someone who is already waiting (the earlier one goes on).
			if j > i and q.hold > 0.6:
				continue
			var dx := q.at.x - p.at.x
			var dz := q.at.y - p.at.y
			if absf(dx) > 1.7 or absf(dz) > 1.7:
				continue
			var ahead := dx * fx + dz * fz
			var lateral := absf(dz * fx - dx * fz)
			var same := cos(q.want_yaw - p.want_yaw)
			if same >= 0.5 and ahead >= 0.2 and ahead <= 1.6 and lateral <= 0.5:
				# Right behind someone going the same way: keep a good step behind them.
				var keep := clampf((ahead - 0.95) / 0.5, 0.0, 1.0)
				target = maxf(target, clampf(1.0 - q.v / maxf(own, 0.05) * keep, 0.0, 0.95))
			elif j < i and same >= 0.5 and absf(ahead) < 0.35 and lateral < 0.6 \
					and -(dx * sin(q.want_yaw) + dz * cos(q.want_yaw)) < 0.2:
				# Side by side: the later one falls in behind (unless the other one already follows).
				target = maxf(target, 0.7)
			elif p.walked < 1.2 and same < 0.5 and (q.walked >= 1.2 or j < i) and ahead > -0.3 and ahead < 1.3 and lateral < 0.9:
				# Just setting off: let someone crossing in front or coming this way go first.
				target = maxf(target, 0.95)
		p.hold = move_toward(p.hold, target, dt * 5.0)
		if p.hold > 0.0:
			# The clock is held back by what is left under the cap (the walk slows by as much).
			var added := minf(dt * p.hold, MAX_DELAY - p.delay)
			p.delay += added
			p.hold = added / dt

func present(t: float) -> void:
	var started := Time.get_ticks_usec()
	if stage == null or stage.town_rebuilds == 0:
		return
	if layout_changed():
		rebuild()
	var dt := clampf(t - last_time, 0.0, 0.25) if last_time >= 0.0 else 0.0
	var jumped := last_time < 0.0 or absf(t - last_time) > 1.0
	last_time = t
	var camera: Camera3D = stage.camera
	var zoom: float = stage.camera_zoom
	if lod_level == 2 and zoom < LOD_NEAR_ZOOM - 3.0:
		lod_level = 1
	elif lod_level == 1 and zoom > LOD_NEAR_ZOOM + 3.0:
		lod_level = 2
	var shadows := zoom < SHADOW_ZOOM - 3.0 or (cast_real_shadows and zoom < SHADOW_ZOOM + 3.0)
	if shadows != cast_real_shadows:
		cast_real_shadows = shadows
		for p in people:
			for mesh in p.meshes:
				mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mark := Time.get_ticks_usec()
	for p in people:
		var was_index := p.index
		var was_walked := p.walked
		var was_walking := p.walking
		evaluate(p, t)
		p.pos = p.at
		# The feet keep pace with the distance actually walked since the last frame (held back
		# behind someone included).
		if p.walking and was_walking and p.index == was_index and dt > 0.0:
			p.v = maxf(0.0, p.walked - was_walked) / dt
	var mark2 := Time.get_ticks_usec()
	section_usec[0] += mark2 - mark
	# Holding back changes slowly: worked out at 30 Hz.
	hold_dt += dt
	if follow and hold_dt > 0.0 and (hold_dt >= 0.03 or simulate_all):
		hold_back(hold_dt)
		hold_dt = 0.0
	mark = Time.get_ticks_usec()
	section_usec[1] += mark - mark2
	var blob_index := 0
	for p in people:
		var yaw := p.want_yaw
		var on_screen := p.alpha > 0.01 and (simulate_all or camera.is_position_in_frustum(Vector3(p.pos.x, p.y + 0.9, p.pos.y)))
		if not p.ready:
			p.ready = p.rig != null and p.rig.is_ready()
			if p.ready:
				prepare(p)
		if not on_screen or not p.ready:
			if p.shown:
				p.shown = false
				p.rig.set_active(false)
			if blobs != null and not p.blob_hidden:
				p.blob_hidden = true
				blobs.multimesh.set_instance_transform(blob_index, Transform3D(Basis().scaled(Vector3.ZERO), Vector3.ZERO))
			blob_index += 1
			continue
		var snap := not p.shown or jumped
		if not p.shown:
			p.shown = true
			p.rig.set_active(true)
		if p.lod != lod_level:
			p.lod = lod_level
			p.rig.set_lod(lod_level)
		if snap:
			p.heading = yaw
		else:
			var turn := angle_difference(p.heading, yaw)
			var limit := TURN_RATE * dt
			p.heading = wrapf(p.heading + clampf(turn, -limit, limit), -PI, PI)
		var place := Vector3(p.pos.x, p.y, p.pos.y)
		if snap or place != p.placed or p.heading != p.placed_yaw:
			p.placed = place
			p.placed_yaw = p.heading
			p.rig.transform = Transform3D(Basis(Vector3.UP, p.heading), place)
			if blobs != null:
				p.blob_hidden = false
				var size := 0.95 * p.scale * (0.35 + 0.65 * p.alpha)
				blobs.multimesh.set_instance_transform(blob_index, Transform3D(Basis().scaled(Vector3(size, 1.0, size)), place + Vector3.UP * 0.025))
		animate(p, snap)
		if absf(p.alpha - p.alpha_now) > 0.001:
			p.alpha_now = p.alpha
			for mesh in p.meshes:
				mesh.transparency = 1.0 - p.alpha
		if p.prop != null and p.carrying != p.prop_shown:
			p.prop_shown = p.carrying
			p.prop.visible = p.carrying
		blob_index += 1
	var spent := Time.get_ticks_usec() - started
	section_usec[2] += Time.get_ticks_usec() - mark
	update_usec = spent
	if update_samples.size() < 4096:
		update_samples.append(spent)

func animate(p: Person, snap: bool) -> void:
	var player: AnimationPlayer = p.rig.player
	if player == null:
		return
	var want := p.clip_want
	if want != p.clip_now:
		p.clip_now = want
		player.play(CLIP_NAMES[want], 0.0 if snap else BLEND)
		if want >= C_LOOK:
			if p.clip_offset > 0.05:
				player.seek(p.clip_offset, true)
		elif snap or want == C_IDLE:
			player.seek(fposmod(float(p.seed % 1000) * 0.0131, 1.0) * player.current_animation_length, true)
	elif snap and want >= C_LOOK:
		player.seek(p.clip_offset, true)
	if want == C_WALK or want == C_LOADED:
		player.speed_scale = clampf(p.v / (STRIDE_SPEED[want] * p.scale), 0.05, 2.0)
	else:
		player.speed_scale = p.idle_rate if want == C_IDLE else 1.0

# ------------------------------------------------------------------ nodes

func ensure_rig(p: Person) -> void:
	if p.rig != null and is_instance_valid(p.rig):
		return
	var rig := ActorRig.new()
	rig.model_scale = p.scale
	rig.variant = p.variant
	rig.setup("Townsperson_%s" % p.key.validate_node_name(), HUMAN % p.visual)
	rig.visible = false
	add_child(rig)
	p.rig = rig
	p.ready = false
	p.shown = false
	p.clip_now = -1
	p.lod = -1
	p.prop = null
	p.prop_shown = false
	p.alpha_now = 1.0
	p.meshes.clear()

## Once the model is in: no marker dispatch, shadows, the carried prop on the chest bone.
func prepare(p: Person) -> void:
	var rig = p.rig
	rig.set_process(false)
	rig.set_lod(lod_level, true)
	p.lod = lod_level
	p.meshes.clear()
	for level in 3:
		for mesh in rig.lods[level]:
			if is_instance_valid(mesh):
				p.meshes.append(mesh)
				mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_real_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if rig.player != null:
		rig.player.playback_default_blend_time = BLEND
	if p.prop_kind.is_empty() or rig.model == null:
		return
	var skeleton: Skeleton3D = null
	for node in rig.model.find_children("*", "Skeleton3D", true, false):
		skeleton = node
	if skeleton == null:
		return
	var hand := p.prop_kind in ["basket"]
	var bone := skeleton.find_bone("LeftHand" if hand else "UpperChest")
	if bone < 0:
		return
	var attach := BoneAttachment3D.new()
	attach.bone_name = skeleton.get_bone_name(bone)
	skeleton.add_child(attach)
	var item := prop_node(p.prop_kind)
	attach.add_child(item)
	# Where the load sits on the model (model space, +Z forward, the right side is -X).
	var place := Transform3D.IDENTITY
	match p.prop_kind:
		"log":
			place = Transform3D(Basis(Vector3.RIGHT, PI * 0.5).rotated(Vector3.UP, 0.25), Vector3(-0.2, 1.56, -0.02))
		"crate":
			place = Transform3D(Basis(Vector3.UP, 0.2), Vector3(-0.12, 1.6, -0.08))
		"sack", "ore":
			place = Transform3D(Basis(Vector3.BACK, PI * 0.5).rotated(Vector3.UP, 0.3), Vector3(-0.14, 1.55, -0.1))
		"stone":
			place = Transform3D(Basis.IDENTITY, Vector3(-0.15, 1.58, -0.06))
		"basket":
			place = Transform3D(Basis.IDENTITY, Vector3(0.33, 0.66, 0.04))
	var rest := skeleton.get_bone_global_rest(bone)
	item.transform = rest.affine_inverse() * place
	item.visible = false
	p.prop = item
	p.prop_shown = false

static var prop_meshes := {}

static func prop_node(kind: String) -> MeshInstance3D:
	if not prop_meshes.has(kind):
		var mesh: Mesh
		var color := Color("#9a6b3c")
		match kind:
			"log":
				var c := CylinderMesh.new()
				c.top_radius = 0.085
				c.bottom_radius = 0.095
				c.height = 1.25
				c.radial_segments = 8
				c.rings = 1
				mesh = c
				color = Color("#7a5634")
			"crate":
				var b := BoxMesh.new()
				b.size = Vector3(0.44, 0.34, 0.38)
				mesh = b
			"sack", "ore":
				var s := CapsuleMesh.new()
				s.radius = 0.15
				s.height = 0.62
				s.radial_segments = 8
				s.rings = 2
				mesh = s
				color = Color("#cdb88a") if kind == "sack" else Color("#4a3c33")
			"stone":
				var b := BoxMesh.new()
				b.size = Vector3(0.4, 0.26, 0.3)
				mesh = b
				color = Color("#cfc6b4")
			_:
				var c := CylinderMesh.new()
				c.top_radius = 0.17
				c.bottom_radius = 0.12
				c.height = 0.2
				c.radial_segments = 8
				c.rings = 1
				mesh = c
				color = Color("#a88a52")
		var material := StandardMaterial3D.new()
		material.albedo_color = color
		material.roughness = 0.9
		(mesh as PrimitiveMesh).material = material
		prop_meshes[kind] = mesh
	var node := MeshInstance3D.new()
	node.name = "Load"
	node.mesh = prop_meshes[kind]
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node

## Soft contact shadows of all people: one multimesh, one draw call.
func ensure_blobs() -> void:
	if blobs == null:
		var fade := Gradient.new()
		fade.colors = PackedColorArray([Color(0.03, 0.045, 0.04, 0.55), Color(0.03, 0.045, 0.04, 0.0)])
		var texture := GradientTexture2D.new()
		texture.gradient = fade
		texture.width = 64
		texture.height = 64
		texture.fill = GradientTexture2D.FILL_RADIAL
		texture.fill_from = Vector2(0.5, 0.5)
		texture.fill_to = Vector2(1.0, 0.5)
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.albedo_texture = texture
		var plane := PlaneMesh.new()
		plane.size = Vector2.ONE
		plane.material = material
		blobs = MultiMeshInstance3D.new()
		blobs.name = "ContactShadows"
		blobs.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		blobs.multimesh = MultiMesh.new()
		blobs.multimesh.transform_format = MultiMesh.TRANSFORM_3D
		blobs.multimesh.mesh = plane
		add_child(blobs)
	if blobs.multimesh.instance_count != people.size():
		blobs.multimesh.instance_count = people.size()
	for i in people.size():
		blobs.multimesh.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), Vector3.ZERO))
		people[i].blob_hidden = true

# ------------------------------------------------------------------ QA / debug

## Every walked line, the graph and the obstacles (qa_townsfolk draws them from above).
func debug_dump() -> Dictionary:
	var edges: Array = []
	for e in e_a.size():
		edges.append([g_nodes[e_a[e]].x, g_nodes[e_a[e]].y, g_nodes[e_b[e]].x, g_nodes[e_b[e]].y, e_lat[e], e_live[e]])
	var persons: Array = []
	for p in people:
		var lines: Array = []
		for line in p.paths:
			lines.append(Array(line).map(func(v: Vector2): return [v.x, v.y]))
		persons.append({"key": p.key, "role": p.role, "visual": p.visual, "cycle": p.cycle, "lines": lines})
	return {"edges": edges, "people": persons, "posts": Array(posts).map(func(v: Vector2): return [v.x, v.y]),
		"blocked": blocked_rects.map(func(r: Rect2): return [r.position.x, r.position.y, r.size.x, r.size.y]),
		"spots": Array(spot_nodes).map(func(n: int): return [g_nodes[n].x, g_nodes[n].y]),
		"doors": door_stop.values().map(func(v: Vector2): return [v.x, v.y])}
