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
## The gate's height spans in the table (tools/measure_town_solids.gd).
const SPAN_BASE := -3.2
const SPAN_STEP := 0.025

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
## Two people meeting stand this far either side of the middle (m), facing each other.
const MEET_HALF := 0.7
## How long two people who meet stand together (s).
const MEET_DWELL := 5.5
## Where people stand at a door with room in front: the middle, then a step either side.
const DOOR_PLACES: Array[float] = [0.0, -0.95, 0.95, -1.9, 1.9]
## A detour round what cuts a street keeps within this distance beyond the street's band (m),
## and joins parts of the network at most BRIDGE_MAX apart.
const BRIDGE_REACH := 1.6
const BRIDGE_MAX := 30.0
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
	## The phase where this person meets its partner (-1: no partner).
	var meet_phase := -1
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
	## Zoomed out: animation time not yet given to the AnimationPlayer (manual mode).
	var anim_acc := 0.0
	## Clock of the last evaluate() and of the last pose (zoomed out each person is placed
	## every other frame).
	var eval_t := -1.0
	var pose_t := -1.0
	## Standing or inside: nothing about this person changes before this clock time.
	var steady_until := -1.0
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
## Zoomed out (people a few pixels tall) the clips are posed ANIM_FAR_HZ times a second, each
## person on its own beat: the AnimationPlayers run in manual mode, advanced from present().
const ANIM_FAR_ZOOM := 50.0
const ANIM_FAR_HZ := 20.0
const FAR_STRIDE := 3
var anim_manual := false
## QA: microseconds per frame spent advancing the AnimationPlayers in manual mode.
var anim_samples := PackedInt32Array()
var frame_count := 0
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
## Places to stop that are not doors (node -> the yaw a person there faces): the forecourts
## beside the door paths, work places round the buildings, the gates, the meeting places.
var yard_spots := {}
## What each such place is ("yard", "work", "gate", "meet", "square") and whose yard (-1: none).
var place_kind := {}
var place_lot := {}
## The nodes of each yard's path from its street exit to the door.
var lot_nodes := {}
## Two places facing each other, 1.4 m apart, where two people meet: [node a, node b, lot or -1].
var meet_pairs: Array = []
## QA: detours laid round what cuts a street (a fence end, a gate's plinth): [from, to, metres].
var bridges: Array = []
## Nodes of the street centre lines (the ends detours join).
var street_nodes := {}
var corridor_memo := PackedByteArray()
var tried_islands := {}
## The street node each door path leaves from.
var lot_entry := {}
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
## Squares a building draws itself (the market from level III): [rect, x0, z0, w, h, bytes,
## plot height, lot] with the top of the floor per 25 cm cell (tools/measure_town_solids.gd).
var floors: Array = []
var green_yards: Array[Rect2] = []
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
	var y := NAN
	if not green_yards.is_empty() and in_green_yard(Vector2(x, z)) and mask_cover(x, z) < 0.5:
		# The grass round a market's own square: the town ground is not drawn there.
		y = terrain_y(x, z)
	else:
		y = maxf(town_y(x, z), terrain_y(x, z))
	if not floors.is_empty():
		var f := floor_at(Vector2(x, z))
		if not is_nan(f):
			y = maxf(y, f)
	return y

## Inside the lot of a market that draws its own square (its fence and counters are solid).
func in_green_yard(p: Vector2) -> bool:
	for rect: Rect2 in green_yards:
		if rect.has_point(p):
			return true
	return false

## The floor of a square a building draws itself at p (NAN: none).
func floor_at(p: Vector2) -> float:
	for entry: Array in floors:
		if not (entry[0] as Rect2).has_point(p):
			continue
		var w: int = entry[3]
		var i: int = floori((p.y - float(entry[2])) / 0.25) * w + floori((p.x - float(entry[1])) / 0.25)
		var b: int = (entry[5] as PackedByteArray)[i]
		if b > 0:
			return float(entry[6]) + SPAN_BASE + b * SPAN_STEP
	return NAN

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
		var inverse: Transform3D = solid_gate[0]
		var local: Vector3 = inverse * Vector3(p.x, 0.0, p.y)
		var cx := floori(local.x / 0.25) - int(solid_gate[1])
		var cz := floori(local.z / 0.25) - int(solid_gate[2])
		var gw: int = solid_gate[3]
		if cx >= 0 and cz >= 0 and cx < gw and cz < int(solid_gate[4]):
			var gi := cz * gw + cx
			var gate_bytes: PackedByteArray = solid_gate[5]
			if solid_gate[6]:
				# What of the gate stands here, against the knees and the head of a walker on
				# the ground here (its paving at street level is walked).
				var low := gate_bytes[gi * 2]
				var high := gate_bytes[gi * 2 + 1]
				if low <= high:
					var g := ground_y(p.x, p.y)
					var knee := (inverse * Vector3(p.x, g + 0.15, p.y)).y
					var head := (inverse * Vector3(p.x, g + 2.0, p.y)).y
					if SPAN_BASE + high * SPAN_STEP > knee and SPAN_BASE + low * SPAN_STEP < head:
						return true
			elif gate_bytes[gi >> 3] & (1 << (gi & 7)):
				return true
	var feet := NAN
	for entry: Array in solid_lots:
		if not (entry[0] as Rect2).has_point(p):
			continue
		# Feet below the building's base (a plot on a slope): its low parts count as well.
		if is_nan(feet):
			feet = town_y(p.x, p.y)
			if not floors.is_empty():
				var f := floor_at(p)
				if not is_nan(f):
					feet = f
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
	floors.clear()
	green_yards.clear()
	# A market that draws its own square leaves its yard green round it (src/town_plan.gd):
	# walked to and from its gate like any yard (its fence and stalls are in the solids table).
	for lot: Dictionary in plan.lots:
		if TownPlan.own_square(lot):
			green_yards.append((lot.rect as Rect2).grow(-0.15))
	if solid_table.is_empty() and FileAccess.file_exists(SOLIDS):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SOLIDS))
		solid_table = parsed.get("types", {}) if parsed is Dictionary else {}
	var gate: Variant = stage.get("gate_node")
	if gate is Node3D and is_instance_valid(gate) and stage.walls.visible:
		var level := int(str(gate.scene_file_path).get_file().get_basename().get_slice("-", 2))
		var entry := solid_entry("SUP-03", level)
		var spans: Variant = entry.get("spans")
		if spans is Dictionary and int(spans.w) > 0:
			if not spans.has("raw"):
				spans.raw = Marshalls.base64_to_raw(str(spans.bytes))
			solid_gate = [(gate as Node3D).global_transform.affine_inverse(), int(spans.x0), int(spans.z0), int(spans.w), int(spans.h), spans.raw, true]
		elif not entry.is_empty():
			solid_gate = [(gate as Node3D).global_transform.affine_inverse(), int(entry.x0), int(entry.z0), int(entry.w), int(entry.h), entry.raw, false]
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
		var floor_entry: Variant = entry.get("floor")
		if TownPlan.own_square(lot) and floor_entry is Dictionary and int(floor_entry.w) > 0:
			if not floor_entry.has("raw"):
				floor_entry.raw = Marshalls.base64_to_raw(str(floor_entry.bytes))
			var ox := at.x + int(floor_entry.x0) * 0.25
			var oz := at.y + int(floor_entry.z0) * 0.25
			floors.append([Rect2(ox, oz, int(floor_entry.w) * 0.25 - 0.0001, int(floor_entry.h) * 0.25 - 0.0001), ox, oz, int(floor_entry.w), int(floor_entry.h),
				floor_entry.raw, float(stage.sample_city(at.x, at.y)), plan.lots.find(lot)])

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
	if not floors.is_empty() and not is_nan(floor_at(Vector2(x, z))):
		return true
	if in_green_yard(Vector2(x, z)):
		return true
	return mask_painted(x, z)

## The town ground's mask at (x, z) filtered as its shader samples it (it draws >= 0.5).
func mask_cover(x: float, z: float) -> float:
	var town: TownPlan = stage.town_plan if stage != null else null
	if town == null or town.mask == null:
		return 0.0
	if mask_of != town.mask:
		mask_of = town.mask
		mask_bytes = town.mask.get_data()
	var u := (x + TownPlan.HALF) / TownPlan.CELL - 0.5
	var v := (z + TownPlan.HALF) / TownPlan.CELL - 0.5
	var i := floori(u)
	var j := floori(v)
	if i < 0 or j < 0 or i >= TownPlan.SIZE - 1 or j >= TownPlan.SIZE - 1:
		return 0.0
	var at := func(a: int, b: int) -> float:
		var k := (b * TownPlan.SIZE + a) * 4
		return maxi(mask_bytes[k], mask_bytes[k + 1]) / 255.0
	var fu := u - i
	var fv := v - j
	return lerpf(lerpf(at.call(i, j), at.call(i + 1, j), fu), lerpf(at.call(i, j + 1), at.call(i + 1, j + 1), fu), fv)

## The town ground's own mask: drawn here (earth or paving).
func mask_painted(x: float, z: float) -> bool:
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
	mark_kerbs()
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
	var wanted := people_wanted(hall_level)
	var fresh: Array[Person] = []
	var partner := {}
	crowded = 0
	left_out.clear()
	for spec: Dictionary in specs:
		if fresh.size() >= wanted:
			break
		var pair: String = spec.get("pair", "")
		# Both who meet, or neither.
		if not pair.is_empty() and not partner.has(pair) and fresh.size() + 2 > wanted:
			continue
		if not pair.is_empty() and partner.has(pair) and partner[pair] == null:
			partner.erase(pair)
			continue
		var person := Person.new()
		person.key = spec.key
		person.role = spec.role
		person.visual = spec.visual
		person.home = spec.home
		person.seed = spec.seed
		person.prop_kind = spec.prop
		if await build_timeline(person, spec.visits, serial):
			if pair.is_empty():
				fresh.append(person)
			elif partner.has(pair):
				align_pair(partner[pair], person)
				fresh.append(partner[pair])
				fresh.append(person)
				partner.erase(pair)
			else:
				partner[pair] = person
		elif not pair.is_empty():
			if partner.has(pair):
				partner.erase(pair)
			else:
				partner[pair] = null
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

## How many people walk the town at each level of the hall: 8 at I, 14 at III, 20 at V (each
## costs ~10 us of script a frame on screen, see qa_townsfolk.gd).
static func people_wanted(level: int) -> int:
	return clampi(5 + 3 * level, 8, 20)

## Two people who meet: one cycle as long as the other's (the time inside, or the longest wait,
## grows) and clocks set so both stand at the meeting places at the same time.
func align_pair(a: Person, b: Person) -> void:
	var c := maxf(a.cycle, b.cycle)
	pad(a, c - a.cycle)
	pad(b, c - b.cycle)
	a.phase = fposmod(a.phase, c)
	if a.meet_phase >= 0 and b.meet_phase >= 0:
		b.phase = fposmod(a.phase + b.starts[b.meet_phase] - a.starts[a.meet_phase], c)

func pad(p: Person, extra: float) -> void:
	if extra <= 0.001:
		return
	var k := -1
	for i in p.kinds.size():
		if p.kinds[i] == K_INSIDE:
			k = i
			break
	if k < 0:
		for i in p.kinds.size():
			if p.kinds[i] == K_DWELL and i != p.meet_phase and (k < 0 or p.lengths[i] > p.lengths[k]):
				k = i
	if k < 0:
		return
	p.lengths[k] += extra
	for i in range(k + 1, p.kinds.size()):
		p.starts[i] += extra
	p.cycle += extra

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
		# (A cell is walked anywhere in it: one whose centre is within half a cell of a
		# footprint counts as in it.)
		if rect.grow(MEMO_CELL * 0.5 + 0.01).has_point(p):
			# A footprint is the box round the whole model (yard fences, drill grounds): where
			# the town plan lays a street through an empty corner of it, the street is walked;
			# so is the square a market draws itself.
			# (A cell is walked anywhere in it: its centre well inside the street's band.)
			if not on_street_band(p, 0.15) and (floors.is_empty() or is_nan(floor_at(p))) and not in_green_yard(p):
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
func on_street_band(p: Vector2, inset := 0.0) -> bool:
	for s: Array in street_segs:
		var q := Geometry2D.get_closest_point_to_segment(p, s[0], s[1])
		var half := float(s[2]) - inset
		if p.distance_squared_to(q) <= half * half:
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
		if bodies[i].has_point(p) and not on_street_band(p, 0.15) and (floors.is_empty() or is_nan(floor_at(p))) and not in_green_yard(p):
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
	place_kind.clear()
	place_lot.clear()
	lot_nodes.clear()
	lot_entry.clear()
	meet_pairs.clear()
	bridges.clear()
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
	street_nodes.clear()
	for e in e_a.size():
		street_nodes[e_a[e]] = true
		street_nodes[e_b[e]] = true
	corridor_memo.resize(MEMO_SIZE * MEMO_SIZE)
	corridor_memo.fill(0)
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
		if not lot.hall and not walkable(stop):
			# Steps or a porch reach past the plan's footprint: the stop moves out in front of them.
			for k in range(1, 6):
				var q := stop - (door_in[li] as Vector2) * (0.25 * k)
				if walkable(q):
					stop = q
					break
		if lot.hall and square.has_area() and square.grow(-0.3).has_point(stop):
			# The hall's door opens on the square: people come up to it from straight in front.
			var n := add_node(stop)
			# Straight in front, well inside the square (its edge is not painted).
			var front := stop + Vector2(0.0, minf(1.4, square.end.y - 0.6 - stop.y))
			lot_nodes[li] = [n]
			if front.y - stop.y >= 0.7 and square.grow(-0.2).has_point(front):
				var approach := add_node(front)
				add_edge(approach, n, DOOR_BAND, 1)
				on_square.append(approach)
				lot_nodes[li].append(approach)
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
		var path_nodes: Array = []
		for k in range(1, way.size()):
			var n := add_node(way[k])
			add_edge(previous, n, DOOR_BAND, 1)
			previous = n
			path_nodes.append(n)
		lot_nodes[li] = path_nodes
		lot_entry[li] = entry
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
					# Joined to the point of the door path that leads out soonest (the walk to
					# it and on does not run past it to the door and back).
					var joined_to := -1
					var best_cost := INF
					var from_exit := 0.0
					for w in way.size():
						var at: Vector2 = way[w]
						if w > 0:
							from_exit += at.distance_to(way[w - 1])
						var cost := from_exit + at.distance_to(q)
						if cost < best_cost and at.distance_to(stop) > 0.6 and band_clear(at, q, 0.0):
							best_cost = cost
							joined_to = add_node(at)
					if joined_to < 0:
						continue
					var n := add_node(q)
					add_edge(joined_to, n, 0.0, 1)
					yard_spots[n] = atan2(door_in[li].x, door_in[li].y)
					place_kind[n] = "yard"
					place_lot[n] = li
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
		# A square no deeper in front of the hall's door than a street is one: people walk along
		# it (a line of points down its middle) and wait at the hall's door, no one stands about.
		var narrow: bool = hall_stop is Vector2 and square.end.y - (hall_stop as Vector2).y < 3.0
		if narrow:
			# The line nearest the door that is open along most of the square (lamps and
			# benches stand along its front edge).
			var stop_at: Vector2 = hall_stop
			var row_z := stop_at.y + 0.6
			var best_open := -1
			for k in range(5, 12):
				var z := stop_at.y + 0.1 * k
				var open := 0
				var x := square.position.x + 0.5
				while x <= square.end.x - 0.5:
					if walkable(Vector2(x, z)):
						open += 1
					x += 0.25
				if open > best_open:
					best_open = open
					row_z = z
			var first := stop_at.x - 2.4 * floorf((stop_at.x - square.position.x - 0.9) / 2.4)
			var x := first
			while x <= square.end.x - 0.9:
				var q := Vector2(x, row_z)
				if walkable(q):
					on_square.append(add_node(q))
				x += 2.4
			# Two people meet at the square's quiet end, past the row's last point where no one
			# walks through, facing each other: side on to the city camera (looking along x = z)
			# where there is room, so neither hides the other; else across the square.
			var row_lo := INF
			var row_hi := -INF
			for n in on_square:
				row_lo = minf(row_lo, g_nodes[n].x)
				row_hi = maxf(row_hi, g_nodes[n].x)
			var quiet: Array = []
			var qx := square.position.x + 0.9
			while qx <= square.end.x - 0.9:
				if qx >= row_hi + 1.0 or qx <= row_lo - 1.0:
					var qz := square.position.y + 0.8
					while qz <= square.end.y - 0.8:
						quiet.append(Vector2(qx, qz))
						qz += 0.1
				qx += 0.25
			quiet.sort_custom(func(x, y): return x.distance_squared_to(hall_stop) < y.distance_squared_to(hall_stop))
			for axis: Vector2 in [Vector2(0.7071, -0.7071), Vector2(0.0, 1.0), Vector2(0.6, 0.8), Vector2(-0.6, 0.8)]:
				for m: Vector2 in quiet:
					if not meet_pairs.is_empty():
						break
					if m.distance_to(hall_stop) < 3.0:
						continue
					var a := m - axis * MEET_HALF
					var b := m + axis * MEET_HALF
					if not walkable(a) or not walkable(b) or not walkable(m) \
							or not walkable(a - axis * 0.3) or not walkable(b + axis * 0.3):
						continue
					var busy := false
					for n in g_nodes.size():
						if g_nodes[n].distance_to(a) < 1.6 or g_nodes[n].distance_to(b) < 1.6:
							busy = true
							break
					if busy:
						continue
					var na := add_node(a)
					var nb := add_node(b)
					meet_pairs.append([na, nb, -1])
					for pair_node: int in [na, nb]:
						place_kind[pair_node] = "meet"
						place_lot[pair_node] = -1
					yard_spots[na] = atan2(axis.x, axis.y)
					yard_spots[nb] = atan2(-axis.x, -axis.y)
					break
		# Where two people meet on the square: two places facing each other (along the square's
		# long side), clear of the hall's door and of each other.
		var long_axis := Vector2.RIGHT if square.size.x >= square.size.y else Vector2.DOWN
		var centres: Array = []
		var gx := square.position.x + 1.4
		while gx <= square.end.x - 1.4:
			var gz := square.position.y + 0.9
			while gz <= square.end.y - 0.9:
				centres.append(Vector2(gx, gz))
				gz += 0.5
			gx += 0.5
		# Farthest from the hall's door first.
		if hall_stop is Vector2:
			centres.sort_custom(func(x, y): return x.distance_squared_to(hall_stop) > y.distance_squared_to(hall_stop))
		for m: Vector2 in centres:
			if meet_pairs.size() >= 2 or narrow:
				break
			var a := m - long_axis * MEET_HALF
			var b := m + long_axis * MEET_HALF
			if hall_stop is Vector2 and m.distance_to(hall_stop) < 3.0:
				continue
			var far := true
			for pair: Array in meet_pairs:
				if g_nodes[pair[0]].lerp(g_nodes[pair[1]], 0.5).distance_to(m) < 3.6:
					far = false
			# (Not where a street comes onto the square: the way in would run between them.)
			for n: int in street_nodes:
				if g_nodes[n].distance_to(a) < 2.6 or g_nodes[n].distance_to(b) < 2.6:
					far = false
					break
			if not far or not walkable(a) or not walkable(b) or not walkable(m):
				continue
			var na := add_node(a)
			var nb := add_node(b)
			meet_pairs.append([na, nb, -1])
			for pair_node: int in [na, nb]:
				place_kind[pair_node] = "meet"
				place_lot[pair_node] = -1
			yard_spots[na] = atan2(long_axis.x, long_axis.y)
			yard_spots[nb] = atan2(-long_axis.x, -long_axis.y)
		var wanted := clampi(int(square.get_area() / 6.0), 2, 8)
		var tries := 0
		while spot_nodes.size() < wanted and tries < 120 and not narrow:
			tries += 1
			var p := Vector2(rng.randf_range(square.position.x + 1.0, square.end.x - 1.0), rng.randf_range(square.position.y + 0.9, square.end.y - 0.8))
			if hall_stop is Vector2 and p.distance_to(hall_stop) < 2.6:
				continue
			var far := true
			for n in spot_nodes:
				if g_nodes[n].distance_to(p) < 2.2:
					far = false
			for pair: Array in meet_pairs:
				if g_nodes[pair[0]].distance_to(p) < 2.0 or g_nodes[pair[1]].distance_to(p) < 2.0:
					far = false
			var near: Array = nearby(p, p, 1.0)
			if not far or not clear_at(p, near[0], near[1]):
				continue
			var sn := add_node(p)
			spot_nodes.append(sn)
			place_kind[sn] = "square"
			place_lot[sn] = -1
			yard_spots[sn] = rng.randf_range(-PI, PI)
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
	for pair: Array in meet_pairs:
		spots.append(g_nodes[pair[0]])
		spots.append(g_nodes[pair[1]])
	# ... and the places in front of the hall's door where people wait.
	var hall_front := PackedVector2Array()
	for li in door_lot.values():
		# (On a square no deeper than a street people pass those at the door closer.)
		if plan.lots[li].hall and not (square.has_area() and square.end.y - door_stop[li].y < 3.0):
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
	link()
	g_mark = Time.get_ticks_usec()
	if not await bridge(serial):
		return false
	tried_islands.clear()
	if not await bridge_islands(serial):
		return false
	build_profile["g_bridge"] = Time.get_ticks_usec() - g_mark
	g_mark = Time.get_ticks_usec()
	if not await add_places(serial):
		return false
	build_profile["g_places"] = Time.get_ticks_usec() - g_mark
	link()
	return true

## The live edges of every node and the parts of the network that reach each other.
func link() -> void:
	g_edges.clear()
	for n in g_nodes.size():
		g_edges.append(PackedInt32Array())
	for e in e_a.size():
		if e_live[e] == 1:
			g_edges[e_a[e]].append(e)
			g_edges[e_b[e]].append(e)
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
	route_cache.clear()

# ------------------------------------------------------------------ kerbs, detours, places

## Yard kerbs (src/town_ground.gd lays them along the open edges of every yard from level II,
## broken at the door, at streets and where another yard is): never stepped over.
func mark_kerbs() -> void:
	var town = stage.town
	for lot: Dictionary in plan.lots:
		var level := int(lot.level)
		if level < 2 or lot.hall or TownPlan.own_square(lot):
			continue
		var r: Rect2 = lot.rect
		var width := 0.3 if level >= 4 else 0.2
		var inset := width * 0.5 + 0.08
		var open: Array = lot.open
		var edges := [
			[Vector2(r.position.x + inset, r.position.y + inset), Vector2(r.position.x + inset, r.end.y - inset), open[0], false],
			[Vector2(r.end.x - inset, r.position.y + inset), Vector2(r.end.x - inset, r.end.y - inset), open[1], false],
			[Vector2(r.position.x + inset, r.position.y + inset), Vector2(r.end.x - inset, r.position.y + inset), open[2], false],
			[Vector2(r.position.x + inset, r.end.y - inset), Vector2(r.end.x - inset, r.end.y - inset), open[3], true],
		]
		var near_segments: Array = plan.segments.filter(func(sg): return plan.street_rect(sg).grow(0.6).intersects(r.grow(0.6)))
		var near_lots: Array = plan.lots.filter(func(other): return other != lot and other.rect.grow(0.2).intersects(r.grow(0.2)))
		for edge: Array in edges:
			if not edge[2]:
				continue
			var a: Vector2 = edge[0]
			var b: Vector2 = edge[1]
			var steps := maxi(1, ceili(a.distance_to(b) / 0.2))
			for k in range(steps + 1):
				var p := a.lerp(b, float(k) / steps)
				if not near_segments.is_empty() and town.on_street(plan, p, 0.15, near_segments):
					continue
				if edge[3] and absf(p.x - float(lot.door_x)) < TownPlan.DOOR_GAP * 0.5:
					continue
				var other_yard := false
				for other: Dictionary in near_lots:
					if (other.rect as Rect2).grow(0.05).has_point(p):
						other_yard = true
						break
				if not other_yard:
					block_memo(p, width * 0.5 + 0.22)

## Marks the walkability memo blocked round p.
func block_memo(p: Vector2, radius: float) -> void:
	var i0 := floori((p.x - radius + 64.0) / MEMO_CELL)
	var i1 := floori((p.x + radius + 64.0) / MEMO_CELL)
	var j0 := floori((p.y - radius + 64.0) / MEMO_CELL)
	var j1 := floori((p.y + radius + 64.0) / MEMO_CELL)
	for j in range(maxi(j0, 0), mini(j1, MEMO_SIZE - 1) + 1):
		for i in range(maxi(i0, 0), mini(i1, MEMO_SIZE - 1) + 1):
			var centre := Vector2((i + 0.5) * MEMO_CELL - 64.0, (j + 0.5) * MEMO_CELL - 64.0)
			if centre.distance_squared_to(p) <= (radius + MEMO_CELL * 0.5) * (radius + MEMO_CELL * 0.5):
				memo[j * MEMO_SIZE + i] = 2

## Within reach of the town's streets (their band and BRIDGE_REACH beyond it) or the square:
## where a detour may run (not across a yard).
func corridor(p: Vector2) -> bool:
	var i := floori((p.x + 64.0) / MEMO_CELL)
	var j := floori((p.y + 64.0) / MEMO_CELL)
	if i < 0 or j < 0 or i >= MEMO_SIZE or j >= MEMO_SIZE or corridor_memo.is_empty():
		return false
	var k := j * MEMO_SIZE + i
	if corridor_memo[k] == 0:
		var centre := Vector2((i + 0.5) * MEMO_CELL - 64.0, (j + 0.5) * MEMO_CELL - 64.0)
		var inside := plan.plaza.has_area() and plan.plaza.grow(0.3).has_point(centre)
		if not inside:
			for sg: Dictionary in plan.segments:
				var reach := float(sg.w) * 0.5 + BRIDGE_REACH
				if centre.distance_squared_to(Geometry2D.get_closest_point_to_segment(centre, sg.a, sg.b)) <= reach * reach:
					inside = true
					break
		corridor_memo[k] = 1 if inside else 2
	return corridor_memo[k] == 1

## A straight line walked (every 25 cm cell it passes through) and within the corridor.
func fine_clear(a: Vector2, b: Vector2, in_corridor := false) -> bool:
	var i := floori((a.x + 64.0) / MEMO_CELL)
	var j := floori((a.y + 64.0) / MEMO_CELL)
	var i1 := floori((b.x + 64.0) / MEMO_CELL)
	var j1 := floori((b.y + 64.0) / MEMO_CELL)
	var d := b - a
	var step_i := 1 if d.x > 0.0 else -1
	var step_j := 1 if d.y > 0.0 else -1
	var next_x := ((i + (1 if step_i > 0 else 0)) * MEMO_CELL - 64.0)
	var next_z := ((j + (1 if step_j > 0 else 0)) * MEMO_CELL - 64.0)
	var t_x := (next_x - a.x) / d.x if absf(d.x) > 0.000001 else INF
	var t_z := (next_z - a.y) / d.y if absf(d.y) > 0.000001 else INF
	var dt_x := MEMO_CELL / absf(d.x) if absf(d.x) > 0.000001 else INF
	var dt_z := MEMO_CELL / absf(d.y) if absf(d.y) > 0.000001 else INF
	for guard in 4096:
		var centre := Vector2((i + 0.5) * MEMO_CELL - 64.0, (j + 0.5) * MEMO_CELL - 64.0)
		if not walkable(centre) or (in_corridor and not corridor(centre)):
			return false
		if i == i1 and j == j1:
			return true
		if t_x < t_z:
			i += step_i
			t_x += dt_x
		else:
			j += step_j
			t_z += dt_z
	return true

## Shortest walk on the 25 cm walkability grid from a to b, within the corridor and at most
## `limit` m long ([] when there is none), straightened (string pulling).
func grid_path(a: Vector2, b: Vector2, limit: float, anywhere := false) -> PackedVector2Array:
	var box := Rect2(a, Vector2.ZERO).expand(b).grow(5.0)
	var x0 := floori((box.position.x + 64.0) / MEMO_CELL)
	var z0 := floori((box.position.y + 64.0) / MEMO_CELL)
	var w := ceili(box.size.x / MEMO_CELL) + 1
	var h := ceili(box.size.y / MEMO_CELL) + 1
	var count := w * h
	var cost := PackedFloat32Array()
	cost.resize(count)
	cost.fill(INF)
	var parent := PackedInt32Array()
	parent.resize(count)
	parent.fill(-1)
	var state := PackedByteArray()
	state.resize(count)
	state.fill(0)
	var centre := func(c: int) -> Vector2:
		return Vector2((x0 + c % w + 0.5) * MEMO_CELL - 64.0, (z0 + c / w + 0.5) * MEMO_CELL - 64.0)
	var cell_of := func(p: Vector2) -> int:
		var cx := floori((p.x + 64.0) / MEMO_CELL) - x0
		var cz := floori((p.y + 64.0) / MEMO_CELL) - z0
		return cz * w + cx if cx >= 0 and cz >= 0 and cx < w and cz < h else -1
	var start: int = cell_of.call(a)
	var goal: int = cell_of.call(b)
	if start < 0 or goal < 0:
		return PackedVector2Array()
	var passable := func(c: int) -> bool:
		if state[c] == 0:
			var q: Vector2 = centre.call(c)
			state[c] = 1 if walkable(q) and (anywhere or corridor(q)) else 2
		return state[c] == 1
	state[start] = 1
	state[goal] = 1
	var heap_d := PackedFloat32Array()
	var heap_n := PackedInt32Array()
	cost[start] = 0.0
	heap_push(heap_d, heap_n, 0.0, start)
	var steps_limit := limit / MEMO_CELL
	var found := false
	var gx := goal % w
	var gz := goal / w
	while not heap_n.is_empty():
		var c := heap_pop(heap_d, heap_n)
		if c == goal:
			found = true
			break
		var cx := c % w
		var cz := c / w
		for dz in range(-1, 2):
			for dx in range(-1, 2):
				if dx == 0 and dz == 0:
					continue
				var nx := cx + dx
				var nz := cz + dz
				if nx < 0 or nz < 0 or nx >= w or nz >= h:
					continue
				var n := nz * w + nx
				if not passable.call(n):
					continue
				if dx != 0 and dz != 0 and (not passable.call(cz * w + nx) or not passable.call(nz * w + cx)):
					continue
				var g := cost[c] + (1.4142 if dx != 0 and dz != 0 else 1.0)
				if g > steps_limit or g >= cost[n]:
					continue
				cost[n] = g
				parent[n] = c
				heap_push(heap_d, heap_n, g + Vector2(nx - gx, nz - gz).length(), n)
	if not found:
		return PackedVector2Array()
	var cells := PackedVector2Array()
	var c := goal
	while c >= 0:
		cells.append(centre.call(c))
		if c == start:
			break
		c = parent[c]
	cells.reverse()
	cells[0] = a
	cells[cells.size() - 1] = b
	var out := PackedVector2Array([a])
	var i := 0
	while i < cells.size() - 1:
		var j := cells.size() - 1
		while j > i + 1 and not fine_clear(cells[i], cells[j], not anywhere):
			j -= 1
		out.append(cells[j])
		i = j
	return out

## Lanes the town plan lays through a fence, a yard's corner or a gate's plinth cut the street
## network in parts. Each part is joined to the nearest other one by the shortest walk round
## what is in the way, within reach of the streets (BRIDGE_REACH beyond their band), when there
## is one no longer than twice the gap and 8 m.
func bridge(serial: int) -> bool:
	var tried := {}
	var attempts := 0
	for round in 12:
		var groups := {}
		for n: int in street_nodes:
			if g_edges[n].is_empty() or not walkable(g_nodes[n]):
				continue
			var c: int = component[n]
			if not groups.has(c):
				groups[c] = PackedInt32Array()
			groups[c].append(n)
		var keys: Array = groups.keys()
		var best: Array = []
		for i in keys.size():
			for j in range(i + 1, keys.size()):
				# The three nearest pairs of street nodes of the two parts.
				var pairs: Array = []
				for a: int in groups[keys[i]]:
					for b: int in groups[keys[j]]:
						var d := g_nodes[a].distance_to(g_nodes[b])
						if d <= BRIDGE_MAX and not tried.has("%d|%d" % [mini(a, b), maxi(a, b)]):
							pairs.append([d, a, b])
				pairs.sort_custom(func(x, y): return x[0] < y[0])
				for pair: Array in pairs.slice(0, 3):
					best.append(pair)
		if best.is_empty():
			return true
		best.sort_custom(func(x, y): return x[0] < y[0])
		var joined := false
		for candidate: Array in best:
			if attempts >= 24:
				return true
			attempts += 1
			tried["%d|%d" % [mini(candidate[1], candidate[2]), maxi(candidate[1], candidate[2])]] = true
			if serial >= 0 and not await next_slice(serial):
				return false
			var a := g_nodes[candidate[1]]
			var b := g_nodes[candidate[2]]
			var path := grid_path(a, b, float(candidate[0]) * 2.0 + 8.0)
			if path.size() < 2:
				continue
			lay_detour(candidate[1], candidate[2], path)
			joined = true
			break
		if not joined:
			return true
		link()
	return true

## A part of the network with doors on it that no detour along the streets reaches (the plan's
## lane to it runs under a building that grew over it, or the last stretch of a door path is
## built over): joined to the town by the shortest walk across the ground in between.
func bridge_islands(serial: int) -> bool:
	for round in 6:
		var counts := {}
		for n: int in street_nodes:
			if not g_edges[n].is_empty():
				counts[component[n]] = counts.get(component[n], 0) + 1
		var main := -1
		for c: int in counts:
			if main < 0 or counts[c] > counts[main]:
				main = c
		if main < 0:
			return true
		var islands := {}
		for li: int in door_node:
			var c: int = component[door_node[li]]
			if c != main and not tried_islands.has(c):
				islands[c] = true
		if islands.is_empty():
			return true
		var targets := PackedInt32Array()
		for n in g_nodes.size():
			if component[n] == main and n < g_edges.size() and not g_edges[n].is_empty() and not yard_spots.has(n) and walkable(g_nodes[n]):
				targets.append(n)
		var joined := false
		for c: int in islands:
			tried_islands[c] = true
			# For each node of the town, the nearest of the island; tried in order of distance,
			# at most six, each 5 m from those before (different ways out).
			var from := PackedInt32Array()
			for a in g_nodes.size():
				if component[a] == c and not yard_spots.has(a) and walkable(g_nodes[a]):
					from.append(a)
			var pairs: Array = []
			for b: int in targets:
				var best := -1
				var best_d := BRIDGE_MAX
				for a: int in from:
					var d := g_nodes[a].distance_to(g_nodes[b])
					if d < best_d:
						best_d = d
						best = a
				if best >= 0:
					pairs.append([best_d, best, b])
			pairs.sort_custom(func(x, y): return x[0] < y[0])
			var chosen: Array = []
			for pair: Array in pairs:
				if chosen.size() >= 6:
					break
				var spread := true
				for other: Array in chosen:
					if g_nodes[other[2]].distance_to(g_nodes[pair[2]]) < 5.0:
						spread = false
						break
				if spread:
					chosen.append(pair)
			for pair: Array in chosen:
				if serial >= 0 and not await next_slice(serial):
					return false
				var path := grid_path(g_nodes[pair[1]], g_nodes[pair[2]], float(pair[0]) * 1.8 + 6.0, true)
				if path.size() < 2:
					continue
				lay_detour(pair[1], pair[2], path)
				joined = true
				break
			if joined:
				break
		if not joined:
			return true
		link()
		tried_islands.clear()
	return true

## Lays a detour found on the grid as edges (kind 3) from node a to node b; each corner also
## joins the network nodes it sees close by, so no way through it runs on to a node and back.
func lay_detour(a: int, b: int, path: PackedVector2Array) -> void:
	var previous := a
	var length := 0.0
	var made: Array = []
	for k in range(1, path.size()):
		var n: int = b if k == path.size() - 1 else add_node(path[k])
		add_edge(previous, n, 0.0, 3)
		length += g_nodes[previous].distance_to(g_nodes[n])
		previous = n
		if k < path.size() - 1:
			made.append(n)
	for n: int in made:
		var joins := 0
		for m in g_nodes.size():
			if joins >= 3 or m == n or m >= g_edges.size() or g_edges[m].is_empty() or yard_spots.has(m):
				continue
			if g_nodes[m].distance_to(g_nodes[n]) < 3.0 and fine_clear(g_nodes[m], g_nodes[n], true):
				add_edge(m, n, 0.0, 3)
				joins += 1
	bridges.append([g_nodes[a], g_nodes[b], length])

## Places to stop beyond the doors: work places round each building in its yard (a field's
## edge, the lumber yard, the store's yard: beside the building, facing it), the inner side of
## the wall's gates (looking out), and at the well and the market two places facing each other
## where neighbours meet. Each is joined by one straight line checked clear (kerbs included).
func add_places(serial: int) -> bool:
	var taken := PackedVector2Array()
	for n in yard_spots:
		taken.append(g_nodes[n])
		if place_kind.get(n, "") == "yard":
			join_place(n)
	for li: int in door_node.keys():
		if serial >= 0 and not await next_slice(serial):
			return false
		var lot: Dictionary = plan.lots[li]
		if lot.hall or TownPlan.own_square(lot):
			continue
		var body: Rect2 = lot.body
		var inner := (lot.rect as Rect2).grow(-0.45)
		var anchors: Array = (lot_nodes.get(li, []) as Array).duplicate()
		for n in yard_spots:
			if place_lot.get(n, -1) == li:
				anchors.append(n)
		var stop: Vector2 = door_stop[li]
		var want := clampi(2 + int(lot.level) / 2, 2, 4)
		# How far each node of the door path is from its street node (along the path).
		var out_cost := {}
		var walked := 0.0
		var last: Vector2 = g_nodes[lot_entry[li]] if lot_entry.has(li) else stop
		if lot_entry.has(li):
			anchors.push_front(lot_entry[li])
			out_cost[lot_entry[li]] = 0.0
		for m: int in lot_nodes.get(li, []):
			walked += g_nodes[m].distance_to(last)
			last = g_nodes[m]
			out_cost[m] = walked
		var made := 0
		var candidates: Array = []
		# Along each side of the building, 0.8 m out from its footprint, facing it.
		for side: Array in [[body.position, Vector2.RIGHT, Vector2.UP, body.size.x], [Vector2(body.position.x, body.end.y), Vector2.RIGHT, Vector2.DOWN, body.size.x],
				[body.position, Vector2.DOWN, Vector2.LEFT, body.size.y], [Vector2(body.end.x, body.position.y), Vector2.DOWN, Vector2.RIGHT, body.size.y]]:
			var steps := maxi(2, floori(float(side[3]) / 1.4))
			for k in range(1, steps):
				var q: Vector2 = side[0] + side[1] * (float(side[3]) * k / steps) + side[2] * 0.8
				candidates.append([q, atan2(-side[2].x, -side[2].y)])
		var rng := seeded("work%d" % li)
		for k in range(candidates.size() - 1, 0, -1):
			var m := rng.randi() % (k + 1)
			var t: Array = candidates[k]
			candidates[k] = candidates[m]
			candidates[m] = t
		for candidate: Array in candidates:
			if made >= want:
				break
			var q: Vector2 = candidate[0]
			if not inner.has_point(q) or q.distance_to(stop) < 1.8 or not walkable(q):
				continue
			var crowded_here := false
			for other in taken:
				if other.distance_to(q) < 2.0:
					crowded_here = true
					break
			for post in posts:
				if post.distance_to(q) < 1.2:
					crowded_here = true
			if crowded_here:
				continue
			# Joined where the way out is soonest: along the door path from its street node
			# (the walk from the place on does not run past it to the door and back).
			var anchor := -1
			var anchor_cost := INF
			for m: int in anchors:
				var d := g_nodes[m].distance_to(q)
				var cost: float = d + float(out_cost.get(m, 3.0))
				if d < 10.0 and cost < anchor_cost and d > 1.2 and fine_clear(g_nodes[m], q):
					anchor_cost = cost
					anchor = m
			if anchor < 0:
				continue
			var by_door := false
			for x: float in DOOR_PLACES:
				if q.distance_to(stop + Vector2(x, 0.0)) < 1.0:
					by_door = true
			if by_door or on_a_way(q, 0.6):
				continue
			var n := add_node(q)
			add_edge(anchor, n, 0.0, 1)
			join_place(n)
			yard_spots[n] = candidate[1]
			place_kind[n] = "work"
			place_lot[n] = li
			anchors.append(n)
			taken.append(q)
			made += 1
		if made < 2 and (lot_base[li] in FARM or lot_base[li] in LUMBER or lot_base[li] in STORE):
			# The building fills its yard (a big farm's fields): places at the yard's edge, on
			# the street beside it (by its kerb, out of the walkers' way), facing the yard.
			var r: Rect2 = lot.rect
			var edge_spots: Array = []
			for side: Array in [[r.position, Vector2.RIGHT, Vector2.UP, r.size.x], [Vector2(r.position.x, r.end.y), Vector2.RIGHT, Vector2.DOWN, r.size.x],
					[r.position, Vector2.DOWN, Vector2.LEFT, r.size.y], [Vector2(r.end.x, r.position.y), Vector2.DOWN, Vector2.RIGHT, r.size.y]]:
				var steps := maxi(2, floori(float(side[3]) / 1.4))
				for k in range(1, steps):
					var q: Vector2 = side[0] + side[1] * (float(side[3]) * k / steps) + side[2] * 0.45
					for sg: Dictionary in plan.segments:
						if sg.gate or float(sg.w) < 2.5:
							continue
						var off := q.distance_to(Geometry2D.get_closest_point_to_segment(q, sg.a, sg.b))
						if off <= float(sg.w) * 0.5 and off >= float(sg.w) * 0.5 - 0.55:
							edge_spots.append([q, atan2(-side[2].x, -side[2].y)])
							break
			for candidate: Array in edge_spots:
				if made >= 2:
					break
				var q: Vector2 = candidate[0]
				if q.distance_to(stop) < 2.5 or not walkable(q) or on_a_way(q, 0.9):
					continue
				var crowded_here := false
				for other in taken:
					if other.distance_to(q) < 2.5:
						crowded_here = true
						break
				for post in posts:
					if post.distance_to(q) < 1.2:
						crowded_here = true
				if crowded_here:
					continue
				var anchor := nearest_joined(q, 2.5)
				if anchor < 0:
					anchor = split_street(q)
				if anchor < 0 or component[anchor] != component[door_node[li]] or not fine_clear(g_nodes[anchor], q):
					continue
				var n := add_node(q)
				add_edge(anchor, n, 0.0, 1)
				join_place(n)
				yard_spots[n] = candidate[1]
				place_kind[n] = "work"
				place_lot[n] = li
				taken.append(q)
				made += 1
	link()
	# The inner side of each gate of the wall: on its road, where it is walked, looking out.
	if stage.walls.visible:
		for road: Array in stage.walls.gate_roads:
			var inward: Vector2 = (road[0] - road[1]).normalized()
			var wall_at: Vector2 = road[0] - inward * 7.0
			for k: float in [3.5, 4.5, 5.5, 6.5, 8.0, 9.5, 11.0]:
				var q := wall_at + inward * k
				if not walkable(q) or not stage.walls.inside(q.x, q.y, 3.0) or not walkable(q + inward * 0.6):
					continue
				var anchor := nearest_joined(q, 9.0)
				if anchor < 0:
					continue
				var n := add_node(q)
				add_edge(anchor, n, 0.0, 1)
				join_place(n)
				yard_spots[n] = atan2(-inward.x, -inward.y)
				place_kind[n] = "gate"
				place_lot[n] = -1
				taken.append(q)
				break
	link()
	# A market that draws its own square: a way in through the gate of its fence to the middle
	# of the square, and stalls (beside a counter, facing it) where the merchant stands and
	# loads are left.
	var market_ways := {}
	for li: int in door_node.keys():
		var lot: Dictionary = plan.lots[li]
		if not TownPlan.own_square(lot) or floors.is_empty():
			continue
		if serial >= 0 and not await next_slice(serial):
			return false
		var body: Rect2 = lot.body
		var inward: Vector2 = door_in[li]
		var stop: Vector2 = door_stop[li]
		var cells := PackedVector2Array()
		var sum := Vector2.ZERO
		var z := body.position.y + 0.125
		while z < body.end.y:
			var x := body.position.x + 0.125
			while x < body.end.x:
				var q := Vector2(x, z)
				if not is_nan(floor_at(q)) and walkable(q):
					cells.append(q)
					sum += q
				x += 0.25
			z += 0.25
		if cells.size() < 24:
			continue
		var roomy_at := func(q: Vector2) -> bool:
			return walkable(q + Vector2(0.3, 0.0)) and walkable(q - Vector2(0.3, 0.0)) and walkable(q + Vector2(0.0, 0.3)) and walkable(q - Vector2(0.0, 0.3))
		var gate_in := Vector2.INF
		for k in range(1, 20):
			var q := stop + inward * (0.25 * k)
			if not is_nan(floor_at(q)) and walkable(q):
				var deeper := q + inward * 0.5
				gate_in = deeper if walkable(deeper) and not is_nan(floor_at(deeper)) else q
				break
		if gate_in == Vector2.INF or not fine_clear(stop, gate_in):
			continue
		var middle := sum / cells.size()
		var hub := Vector2.INF
		for q in cells:
			if q.distance_to(gate_in) > 1.5 and roomy_at.call(q) and fine_clear(gate_in, q) \
					and (hub == Vector2.INF or q.distance_squared_to(middle) < hub.distance_squared_to(middle)):
				hub = q
		var n_gate := add_node(gate_in)
		add_edge(door_node[li], n_gate, 0.0, 1)
		var ways: Array = [gate_in]
		if hub != Vector2.INF:
			add_edge(n_gate, add_node(hub), 0.0, 1)
			ways.append(hub)
		market_ways[li] = ways
		link()
		var order := Array(cells)
		order.sort_custom(func(a, b): return a.distance_squared_to(middle) < b.distance_squared_to(middle))
		var stalls := 0
		for q: Vector2 in order:
			if stalls >= 3:
				break
			if q.distance_to(gate_in) < 1.5 or (hub != Vector2.INF and q.distance_to(hub) < 1.2) or not roomy_at.call(q):
				continue
			var crowded_here := false
			for other in taken:
				if other.distance_to(q) < 2.2:
					crowded_here = true
					break
			if crowded_here:
				continue
			var facing := Vector2.ZERO
			for k in 8:
				var d := Vector2.from_angle(k * PI / 4.0)
				if solid_at(q + d * 0.6) and walkable(q + d * 0.2):
					facing = d
					break
			if facing == Vector2.ZERO or on_a_way(q, 0.7):
				continue
			var anchor := nearest_joined(q, 8.0)
			if anchor < 0 or component[anchor] != component[door_node[li]]:
				continue
			var n := add_node(q)
			add_edge(anchor, n, 0.0, 1)
			join_place(n)
			yard_spots[n] = atan2(facing.x, facing.y)
			place_kind[n] = "work"
			place_lot[n] = li
			taken.append(q)
			stalls += 1
			link()
	# Meeting places in front of the well and the market: the nearest clear pair of places in
	# front of the door, beside the way in (the door's own places and its lead point left free);
	# at a market with its own square, on the square.
	for li in doors_of(WELL) + doors_of(MARKET):
		if serial >= 0 and not await next_slice(serial):
			return false
		var outward := -(door_in.get(li, Vector2(0.0, -1.0)) as Vector2)
		var across := Vector2(-outward.y, outward.x)
		var stop: Vector2 = door_stop[li]
		var keep_free := PackedVector2Array([stop + outward * 1.1])
		for x: float in DOOR_PLACES:
			keep_free.append(stop + across * x)
		var centres: Array = []
		var on_floor := market_ways.has(li)
		if on_floor:
			var ways: Array = market_ways[li]
			var middle: Vector2 = ways[ways.size() - 1]
			across = Vector2.RIGHT
			for q: Vector2 in ways:
				keep_free.append(q)
			var body: Rect2 = plan.lots[li].body
			var z := body.position.y + 0.25
			while z < body.end.y:
				var x := body.position.x + 0.25
				while x < body.end.x:
					if not is_nan(floor_at(Vector2(x, z))):
						centres.append(Vector2(x, z))
					x += 0.25
				z += 0.25
			centres.sort_custom(func(x, y): return x.distance_squared_to(middle) < y.distance_squared_to(middle))
		else:
			for out_k in range(4, 13):
				for side_k in range(-8, 9):
					centres.append(stop + outward * (out_k * 0.3) + across * (side_k * 0.4))
			centres.sort_custom(func(x, y): return x.distance_squared_to(stop + outward * 2.4) < y.distance_squared_to(stop + outward * 2.4))
		for m: Vector2 in centres:
			var a := m - across * MEET_HALF
			var b := m + across * MEET_HALF
			var crowded_here := false
			for q in keep_free:
				if q.distance_to(a) < 1.3 or q.distance_to(b) < 1.3 or q.distance_to(m) < 1.3:
					crowded_here = true
					break
			for other in taken:
				if other.distance_to(a) < 1.5 or other.distance_to(b) < 1.5:
					crowded_here = true
					break
			if crowded_here or not walkable(a) or not walkable(b) or not walkable(m):
				continue
			if on_floor and (is_nan(floor_at(a)) or is_nan(floor_at(b)) or not walkable(a - across * 0.35) or not walkable(b + across * 0.35)):
				continue
			var anchor_a := nearest_joined(a, 6.0)
			var anchor_b := nearest_joined(b, 6.0)
			if anchor_a < 0 or anchor_b < 0 or component[anchor_a] != component[anchor_b] or component[anchor_a] != component[door_node[li]]:
				continue
			var na := add_node(a)
			var nb := add_node(b)
			add_edge(anchor_a, na, 0.0, 1)
			add_edge(anchor_b, nb, 0.0, 1)
			join_place(na)
			join_place(nb)
			yard_spots[na] = atan2(across.x, across.y)
			yard_spots[nb] = atan2(-across.x, -across.y)
			for pair_node: int in [na, nb]:
				place_kind[pair_node] = "meet"
				place_lot[pair_node] = li
			meet_pairs.append([na, nb, li])
			taken.append(a)
			taken.append(b)
			link()
			break
	return true

## A place also joins the network nodes it sees close by (not other places), so the way to it
## and on does not run past it to its anchor and back.
func join_place(n: int, reach := 4.0, most := 3) -> void:
	var near: Array = []
	for m in g_nodes.size():
		if m == n or m >= g_edges.size() or g_edges[m].is_empty() or yard_spots.has(m):
			continue
		var d := g_nodes[m].distance_to(g_nodes[n])
		if d < reach and d > 0.3:
			near.append([d, m])
	near.sort_custom(func(x, y): return x[0] < y[0])
	# Its own edges so far (to its anchor): a join only where it saves a detour of a metre.
	var own: Array = []
	for e in e_a.size():
		if e_live[e] == 1 and (e_a[e] == n or e_b[e] == n):
			own.append(e_b[e] if e_a[e] == n else e_a[e])
	var joins := 0
	for item: Array in near:
		if joins >= most:
			break
		var e := edge_between(n, item[1])
		if e >= 0 and e_live[e] == 1:
			continue
		var via := INF
		for m: int in own:
			via = minf(via, g_nodes[item[1]].distance_to(g_nodes[m]) + g_nodes[m].distance_to(g_nodes[n]))
		if float(item[0]) > via - 1.0:
			continue
		if fine_clear(g_nodes[item[1]], g_nodes[n]):
			e = add_edge(item[1], n, 0.0, 1)
			e_live[e] = 1
			e_lat[e] = 0.0
			e_shift[e] = 0.0
			joins += 1

## Someone standing at p would stand on a way walked (a live edge passes within `reach`).
func on_a_way(p: Vector2, reach := 0.8) -> bool:
	for e in e_a.size():
		if e_live[e] == 1 and p.distance_squared_to(Geometry2D.get_closest_point_to_segment(p, g_nodes[e_a[e]], g_nodes[e_b[e]])) < reach * reach:
			return true
	return false

## A node on the street edge nearest p (within 2 m of its line), the edge split there (-1: none).
func split_street(p: Vector2) -> int:
	var best := -1
	var best_d := 2.0
	var at := Vector2.ZERO
	for e in e_a.size():
		if e_live[e] == 0 or e_kind[e] != 0:
			continue
		var q := Geometry2D.get_closest_point_to_segment(p, g_nodes[e_a[e]], g_nodes[e_b[e]])
		var d := q.distance_to(p)
		if d < best_d and q.distance_to(g_nodes[e_a[e]]) > 0.5 and q.distance_to(g_nodes[e_b[e]]) > 0.5:
			best_d = d
			best = e
			at = q
	if best < 0:
		return -1
	var n := add_node(at)
	var a := e_a[best]
	var b := e_b[best]
	e_live[best] = 0
	for pair: Array in [[a, n], [n, b]]:
		var e := add_edge(pair[0], pair[1], e_lat[best], 0)
		e_live[e] = 1
		e_lat[e] = e_lat[best]
		e_shift[e] = e_shift[best]
	link()
	return n

## The nearest node of the network (one with live edges) joined to p by a clear straight line.
func nearest_joined(p: Vector2, reach: float) -> int:
	var best := -1
	var best_d := reach
	for n in g_nodes.size():
		if n >= g_edges.size() or g_edges[n].is_empty():
			continue
		var d := g_nodes[n].distance_to(p)
		if d < best_d and d > 0.5 and fine_clear(g_nodes[n], p):
			best_d = d
			best = n
	return best

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
			if n != from and yard_spots.has(n):
				# A place someone may stand on is walked through only when there is no other way
				# (where two people meet, not even then while a long way round exists).
				nd += 40.0 if place_kind.get(n, "") == "meet" else 4.0
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
	# when the line straight past it is clear (a detour's corner that is needed stays).
	var folded := true
	while folded and raw.size() > 2:
		folded = false
		for i in range(1, raw.size() - 1):
			var d1 := raw[i] - raw[i - 1]
			var d2 := raw[i + 1] - raw[i]
			if d1.length_squared() > 0.000001 and d2.length_squared() > 0.000001 and absf(d1.angle_to(d2)) > 2.0 \
					and band_clear(raw[i - 1], raw[i + 1], 0.0):
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
## Optional: "dwell" (seconds, Vector2 range), "acts" (clips played one after another while
## standing), "face" (yaw), "meet" (the stop where this person meets its partner).
func visit_door(li: int, action: int, enter: bool, carry_out: bool, drop := false) -> Dictionary:
	return {"node": door_node[li], "lot": li, "action": action, "enter": enter, "carry_out": carry_out, "drop": drop}

func visit_spot(n: int, action: int, carry_out := false, drop := false, dwell := Vector2(2.0, 6.0), acts: Array = []) -> Dictionary:
	return {"node": n, "lot": -1, "action": action, "enter": false, "carry_out": carry_out, "drop": drop, "dwell": dwell,
		"acts": acts if not acts.is_empty() else [action]}

## The places of a yard of the kinds asked (nearest the door first).
func places_of(li: int, kinds: Array) -> Array:
	var out: Array = []
	for n in yard_spots:
		if place_lot.get(n, -1) == li and place_kind.get(n, "") in kinds and n < g_edges.size() and not g_edges[n].is_empty():
			out.append(n)
	var stop: Vector2 = door_stop.get(li, Vector2.ZERO)
	out.sort_custom(func(a, b): return g_nodes[a].distance_squared_to(stop) < g_nodes[b].distance_squared_to(stop))
	return out

## The same part of the street network.
func same_part(a: int, b: int) -> bool:
	return a >= 0 and b >= 0 and component[a] == component[b]

## A place in a yard nobody else has, that `home` can walk to (-1: none).
func free_place(li: int, kinds: Array, home: int, claimed: Dictionary) -> int:
	for n in places_of(li, kinds):
		if not claimed.has(n) and (home < 0 or same_part(door_node[home], n)):
			claimed[n] = true
			return n
	return -1

## Where a stroller may stop: free places (the square, forecourts, work places nobody works at,
## the gates) and the doors with room in front, all in one part of the network.
func stroll_pool(claimed: Dictionary, part: int) -> Array:
	var pool: Array = []
	for n in yard_spots:
		var kind: String = place_kind.get(n, "")
		if claimed.has(n) or kind == "meet" or n >= g_edges.size() or g_edges[n].is_empty() or component[n] != part:
			continue
		pool.append(visit_spot(n, C_LOOK if n % 3 != 0 else C_IDLE, false, false, Vector2(2.5, 6.0)))
	for li in door_node:
		if roomy(li) and component[door_node[li]] == part and not lot_base[li] in HOUSE and int(door_users.get(li, 0)) < 3:
			pool.append(visit_door(li, C_LOOK, false, false))
	if pool.size() < 3:
		# A small town: the houses' doors too, and the busier doors once more.
		for li in door_node:
			if roomy(li) and component[door_node[li]] == part and (lot_base[li] in HOUSE or int(door_users.get(li, 0)) >= 3) \
					and int(door_users.get(li, 0)) < 5 and not plan.lots[li].hall:
				pool.append(visit_door(li, C_LOOK, false, false))
	return pool

## The part of the network with the most doors.
func main_part() -> int:
	var count := {}
	for li in door_node:
		var c: int = component[door_node[li]]
		count[c] = int(count.get(c, 0)) + 1
	var best := -1
	for c in count:
		if best < 0 or count[c] > count[best]:
			best = c
	return best

## The people this town could have, in priority order (rebuild takes as many as the hall
## allows: 8 at I, 14 at III, 20 at V). The workers' errands go where the goods belong, however
## far (camp -> store, farm -> granary, store <-> market, forge <-> store, water from the well);
## strollers cross the town; neighbours meet face to face at the square, the well or the market.
var door_users := {}

func plan_people() -> Array:
	door_load.clear()
	door_users.clear()
	var specs: Array = []
	var claimed := {}
	var keys_used := {}
	var hall := hall_lot()
	var visuals_used := {}
	var add := func(role: String, home: int, visuals: Array, prop: String, visits: Array, pair := "") -> void:
		if visits.size() < 2:
			return
		var key := "%s|%s" % [role, str(plan.lots[home].id) if home >= 0 else "town"]
		var n := 0
		while keys_used.has(key + "#%d" % n):
			n += 1
		key += "#%d" % n
		keys_used[key] = true
		var rng := seeded(key)
		var visual: String = visuals[rng.randi() % visuals.size()]
		if visuals_used.get(visual, 0) > 3:
			for alternative in visuals:
				if visuals_used.get(alternative, 0) < visuals_used.get(visual, 0):
					visual = alternative
		visuals_used[visual] = visuals_used.get(visual, 0) + 1
		for v: Dictionary in visits:
			if v.lot >= 0:
				door_users[v.lot] = int(door_users.get(v.lot, 0)) + 1
		specs.append({"key": key, "role": role, "home": home, "visual": visual, "prop": prop, "visits": visits, "seed": hash(key), "pair": pair})
	var part := main_part()
	# A worker's round: home (in through the door), the work in its yard (picking the load up),
	# the long walk to where the load goes (put down there).
	var worker := func(role: String, li: int, visuals: Array, prop: String, groups: Array, work_acts: Array) -> void:
		var to := delivery(li, groups)
		if to < 0:
			return
		var visits: Array = [visit_door(li, C_IDLE, true, false)]
		var work := free_place(li, ["work", "yard"], li, claimed)
		if work >= 0:
			visits.append(visit_spot(work, work_acts[0], true, false, Vector2(5.0, 9.0), work_acts))
		else:
			visits[0].carry_out = true
		# At a market the load goes to a stall when one is free.
		var stall := -1
		if lot_base[to] in MARKET:
			stall = free_place(to, ["work"], li, claimed)
			if stall < 0:
				stall = free_place(to, ["yard"], li, claimed)
		visits.append(visit_spot(stall, C_THANK, false, true, Vector2(3.0, 5.0)) if stall >= 0 else visit_door(to, C_THANK, false, false, true))
		add.call(role, li, visuals, prop, visits)
	var stroller := func(k: int) -> void:
		var pool := stroll_pool(claimed, part)
		if pool.size() < 3:
			return
		var rng := seeded("stroller%d" % k)
		var here: Dictionary = pool[rng.randi() % pool.size()]
		# Every other stroller sets out from the hall's square (from hall III; at I the square
		# has room to stand about and does not need them).
		if k % 2 == 0 and hall >= 0 and int(plan.lots[hall].level) >= 3:
			for v: Dictionary in pool:
				if v.lot == hall and hall >= 0:
					here = v
					break
		var visits: Array = [here]
		pool.erase(here)
		# Each next stop far across the town (one of the three farthest still free).
		for step in 3:
			var from_node: int = here.node
			var ranked: Array = pool.filter(func(v): return v.node != from_node)
			ranked.sort_custom(func(a, b): return route_length(from_node, a.node) > route_length(from_node, b.node))
			if ranked.is_empty() or route_length(from_node, ranked[0].node) < 8.0:
				break
			here = ranked[rng.randi() % mini(3, ranked.size())]
			pool.erase(here)
			visits.append(here)
		for v in visits:
			if v.lot < 0:
				claimed[v.node] = true
		add.call("stroller", -1, ["herbalist", "ferryman", "courier", "miller", "cooper"], "", visits)
	var meeting := func(k: int) -> void:
		# Two neighbours from two homes meet face to face, talk a while and part.
		# The square first, then the well, then the market.
		var pair: Array = []
		var best := -1
		for candidate: Array in meet_pairs:
			if not claimed.has(candidate[0]) and component[candidate[0]] == part and component[candidate[1]] == part:
				var on_square := int(candidate[2]) < 0
				var score := (2 if (k == 0) == on_square else 0) + (1 if not on_square and lot_base[candidate[2]] in WELL else 0)
				if score > best:
					best = score
					pair = candidate
		if pair.is_empty():
			return
		var homes: Array = doors_of(HOUSE) + doors_of(WELL) + doors_of(FARM) + doors_of(STORE) + doors_of(MILITARY) + doors_of(LUMBER) + [hall]
		homes = homes.filter(func(li): return li >= 0 and roomy(li) and component[door_node[li]] == part)
		if homes.size() < 2:
			return
		var rng := seeded("meet%d" % k)
		var first: int = homes[(k * 2) % homes.size()]
		var second: int = homes[(k * 2 + 1) % homes.size()]
		if first == second:
			second = homes[(k * 2 + 2) % homes.size()]
		claimed[pair[0]] = true
		claimed[pair[1]] = true
		var tag := "pair%d" % k
		var acts := [[C_THANK, C_LOOK], [C_REACT, C_THANK]]
		for side in 2:
			var home: int = first if side == 0 else second
			var meet := visit_spot(pair[side], acts[side][0], false, false, Vector2(MEET_DWELL, MEET_DWELL), [acts[side][rng.randi() % 2]])
			meet.face = yard_spots[pair[side]]
			meet.meet = true
			# (Then on somewhere else than home.)
			var pool: Array = stroll_pool(claimed, part).filter(func(v): return v.lot != home and v.node != door_node[home])
			var visits: Array = [visit_door(home, C_IDLE, true, false), meet]
			if not pool.is_empty():
				pool.sort_custom(func(a, b): return route_length(pair[side], a.node) > route_length(pair[side], b.node))
				var after: Dictionary = pool[rng.randi() % mini(3, pool.size())]
				if after.lot < 0:
					claimed[after.node] = true
				visits.append(after)
			add.call("neighbour", home, ["herbalist", "miller", "ferryman", "courier", "cooper"], "", visits, tag)
	var lumber := doors_of(LUMBER)
	var farms := doors_of(FARM)
	var stores := doors_of(STORE)
	var markets := doors_of(MARKET)
	# --- in priority order ---
	if not lumber.is_empty():
		worker.call("lumberjack", lumber[0], ["quarry_worker", "ferryman"], "log", [STORE, MARKET], [C_LOOK, C_REACT])
	if not farms.is_empty():
		worker.call("farmer", farms[0], ["miller"], "sack", [["ECO-02"], STORE, MARKET], [C_LOOK, C_IDLE])
	meeting.call(0)
	if hall >= 0:
		# The hall's steward walks to the two farthest doors and back.
		var rounds: Array = [visit_door(hall, C_IDLE, true, false)]
		var others: Array = door_node.keys().filter(func(li): return li != hall and not lot_base[li] in HOUSE and joined(hall, li) and roomy(li))
		others.sort_custom(func(a, b): return route_length(door_node[hall], door_node[a]) > route_length(door_node[hall], door_node[b]))
		for k in mini(2, others.size()):
			rounds.append(visit_door(others[k], C_LOOK if k == 0 else C_THANK, false, false))
		add.call("steward", hall, ["courier", "miller"], "", rounds)
	stroller.call(0)
	for li in doors_of(MILITARY):
		# The messenger runs from the barracks to the hall (or the farthest door) and on to a gate.
		var to := hall if joined(li, hall) and hall != li else first_door([STORE, SMITH, MARKET, FARM, LUMBER], li)
		if to < 0:
			break
		var visits: Array = [visit_door(li, C_IDLE, true, false), visit_door(to, C_REACT, false, false)]
		for n in yard_spots:
			if place_kind.get(n, "") == "gate" and not claimed.has(n) and same_part(door_node[li], n):
				claimed[n] = true
				visits.append(visit_spot(n, C_LOOK, false, false, Vector2(3.0, 6.0)))
				break
		add.call("messenger", li, ["courier", "ferryman"], "", visits)
		break
	if not stores.is_empty() and not markets.is_empty():
		worker.call("carrier", stores[0], ["cooper", "courier"], "crate", [MARKET], [C_LOOK, C_THANK])
	for li in markets:
		# The merchant keeps a stall: long waits there facing the street, now and then inside.
		# (Its stalls first: the counters of a market's own square, the work places round a
		# smaller one; its forecourt after.)
		var stall_a := free_place(li, ["work"], li, claimed)
		if stall_a < 0:
			stall_a = free_place(li, ["yard"], li, claimed)
		var stall_b := free_place(li, ["work"], li, claimed)
		if stall_b < 0:
			stall_b = free_place(li, ["yard"], li, claimed)
		if stall_a < 0:
			break
		var visits: Array = []
		for n in [stall_a, stall_b]:
			if n < 0:
				continue
			var v := visit_spot(n, C_IDLE, false, false, Vector2(12.0, 20.0), [C_IDLE, C_THANK, C_LOOK])
			v.face = wrapf(float(yard_spots[n]) + PI, -PI, PI)
			visits.append(v)
			# (A market with its own square is gone into through its gate: no door to go in.)
			if visits.size() == 1 and not TownPlan.own_square(plan.lots[li]):
				visits.append(visit_door(li, C_IDLE, true, false))
		if visits.size() == 1:
			visits.append(visit_door(li, C_LOOK, false, false))
		add.call("merchant", li, ["cooper", "miller", "herbalist"], "", visits)
		break
	for li in doors_of(SMITH):
		# The smith fetches iron from the store (or ore from the quarry) and back to the forge.
		var from := delivery(li, [STORE, QUARRY])
		if from >= 0:
			add.call("smith", li, ["cooper"], "ore", [visit_door(li, C_IDLE, true, false), visit_door(from, C_LOOK, false, true)])
		break
	for li in doors_of(WELL):
		# Water from the well: a rest there, then the walk to a house, the market or the hall.
		var to := first_door([HOUSE, MARKET], li)
		if to < 0 and joined(li, hall):
			to = hall
		if to >= 0:
			var rest := visit_door(li, C_IDLE, false, true)
			rest.dwell = Vector2(8.0, 14.0)
			rest.acts = [C_IDLE, C_LOOK]
			add.call("water carrier", li, ["miller", "ferryman"], "sack", [rest, visit_door(to, C_IDLE, false, false, true)])
		break
	# Petitioners: from home to the hall's door, a long wait there, a look round a yard or a gate
	# near the hall, and back to its door for another wait.
	if hall >= 0 and int(plan.lots[hall].level) >= 3:
		var petitioner_homes: Array = (doors_of(HOUSE) + doors_of(WELL) + doors_of(STORE) + doors_of(FARM)).filter(func(li): return joined(li, hall) and roomy(li))
		var hall_at: Vector2 = door_stop[hall]
		for k in mini(2, petitioner_homes.size()):
			var home: int = petitioner_homes[(k * 3) % petitioner_homes.size()]
			var nearest := -1
			for n in yard_spots:
				var kind: String = place_kind.get(n, "")
				if claimed.has(n) or not kind in ["yard", "gate", "work", "square"] or n >= g_edges.size() or g_edges[n].is_empty() \
						or not same_part(door_node[hall], n) or g_nodes[n].distance_to(hall_at) < 4.0:
					continue
				if nearest < 0 or g_nodes[n].distance_to(hall_at) < g_nodes[nearest].distance_to(hall_at):
					nearest = n
			var visits: Array = [visit_door(home, C_IDLE, true, false)]
			for w in 2:
				var wait := visit_door(hall, C_THANK, false, false)
				wait.dwell = Vector2(8.0, 14.0)
				wait.acts = [C_IDLE, C_THANK, C_LOOK] if (k + w) % 2 == 0 else [C_LOOK, C_IDLE, C_REACT]
				visits.append(wait)
				if w == 0:
					if nearest >= 0 and g_nodes[nearest].distance_to(hall_at) < 30.0:
						claimed[nearest] = true
						visits.append(visit_spot(nearest, C_LOOK, false, false, Vector2(4.0, 8.0), [C_LOOK, C_IDLE]))
					else:
						break
			add.call("petitioner", home, ["herbalist", "miller", "courier", "cooper"], "", visits)
	stroller.call(1)
	meeting.call(1)
	for li in doors_of(QUARRY):
		worker.call("quarryman", li, ["quarry_worker", "cooper"], "stone", [SMITH, STORE], [C_LOOK, C_REACT])
		break
	for li in doors_of(HERBAL):
		worker.call("herbalist", li, ["herbalist"], "basket", [HOSPITAL, MARKET], [C_LOOK, C_THANK])
		break
	stroller.call(2)
	# Second hands at the bigger workplaces.
	for li in lumber + farms + stores:
		if int(plan.lots[li].level) >= 3:
			var groups: Array = [MARKET] if lot_base[li] in STORE else [STORE, MARKET]
			var prop := "log" if lot_base[li] in LUMBER else ("sack" if lot_base[li] in FARM else "crate")
			worker.call("helper", li, ["ferryman", "quarry_worker", "cooper", "miller"], prop, groups, [C_REACT, C_LOOK])
	for li in doors_of(HOSPITAL):
		var to := first_door([HERBAL, MARKET, STORE], li)
		if to >= 0:
			add.call("healer", li, ["herbalist"], "basket", [visit_door(li, C_IDLE, true, false), visit_door(to, C_LOOK, false, true)])
		break
	for li in doors_of(HOUSE):
		var well := first_door([WELL], li)
		var to := well if well >= 0 else delivery(li, [MARKET, STORE])
		if to >= 0:
			add.call("resident", li, ["herbalist", "miller", "ferryman"], "basket" if well >= 0 else "",
				[visit_door(li, C_IDLE, true, false), visit_door(to, C_LOOK, false, well >= 0)])
	stroller.call(3)
	meeting.call(2)
	stroller.call(4)
	var market := first_door([MARKET], hall)
	if hall >= 0 and market >= 0:
		add.call("visitor", hall, ["courier", "herbalist", "ferryman"], "basket",
			[visit_door(hall, C_IDLE, true, false), visit_door(market, C_THANK, false, true)])
	for k in range(5, 9):
		stroller.call(k)
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
	var own_slot := {}
	for visit: Dictionary in visits:
		var node: int = visit.node
		# Places are claimed only once the whole day works out (see the end).
		var users: Array = stop_users.get(node, [])
		var slot := users.find(p.key)
		if slot < 0 and own_slot.has(node):
			# (The same stop twice in a day: the same place.)
			slot = own_slot[node]
		elif slot < 0:
			slot = users.size() + int(claims.count(node))
			claims.append(node)
			own_slot[node] = slot
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
			var places := DOOR_PLACES.size() if room >= 0.65 else 1
			if room >= 0.65:
				lead = base + outward * minf(1.1, room - 0.25)
			var free := 0
			for k in places:
				if TownPlan.own_square(plan.lots[visit.lot]) and absf(DOOR_PLACES[k]) > 1.0:
					# (A market's gate: its paved apron only, the grass round it is lower.)
					continue
				var place := base + Vector2(DOOR_PLACES[k], 0.0)
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
	# Each walked line sampled every 0.35 m with the drawn ground under it (every 4.4 cm across
	# a step, e.g. from the grass onto paving): walking is a binary search and a lerp per frame.
	for i in count:
		var line: PackedVector2Array = lines[i]
		var dense := PackedVector3Array()
		for k in range(line.size() - 1):
			var a := line[k]
			var b := line[k + 1]
			var pieces := maxi(1, ceili(a.distance_to(b) / 0.35))
			for m in pieces:
				var q := a.lerp(b, float(m) / pieces)
				var y := ground_y(q.x, q.y)
				if not dense.is_empty():
					var before := dense[dense.size() - 1]
					if absf(y - before.y) > 0.03:
						var from := Vector2(before.x, before.z)
						for f in range(1, 8):
							var r := from.lerp(q, f / 8.0)
							dense.append(Vector3(r.x, ground_y(r.x, r.y), r.y))
				dense.append(Vector3(q.x, y, q.y))
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
			var acts: Array = visit.get("acts", [visit.action])
			var span: Vector2 = visit.get("dwell", Vector2(2.0, 6.0))
			var carry_mode := 0
			if carried_in and visit.drop:
				carry_mode = 2
			elif carried_in or visit.carry_out:
				carry_mode = 1 if carried_in else 3
			# A load is put down or picked up with a gesture.
			if (carry_mode == 2 or carry_mode == 3) and int(acts[0]) == C_IDLE:
				acts = [C_THANK] + acts
			if yard_spots.has(visit.node):
				facing = float(yard_spots[visit.node]) + rng.randf_range(-0.35, 0.35)
			elif visit.lot < 0 and arrive_dir != Vector2.ZERO:
				facing = atan2(arrive_dir.x, arrive_dir.y) + rng.randf_range(-1.2, 1.2)
			if visit.has("face"):
				facing = float(visit.face)
			if visit.get("meet", false):
				p.meet_phase = p.kinds.size()
			# Standing here: one stretch per clip (a gesture somewhere in it), the turn to the
			# next leg at the end of the last.
			var each := rng.randf_range(span.x, span.y) / acts.size()
			for k in acts.size():
				var action: int = acts[k]
				var last := k == acts.size() - 1
				var tail := TURN_WINDOW if last else 0.0
				var length := maxf(each, tail + 0.6)
				var gesture := -1.0
				if action != C_IDLE:
					length = maxf(length, GESTURE_SECONDS[action] + tail + 0.9)
					gesture = rng.randf_range(0.35, length - tail - GESTURE_SECONDS[action] - 0.2)
				var mode := carry_mode
				if k > 0:
					mode = 1 if carry_mode == 1 or carry_mode == 3 else 0
				t = add_phase(p, K_DWELL, t, length, -1, 0.0, action, gesture, mode, spot, spot, facing, next_yaw if last else facing)
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
	p.steady_until = -1.0
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
			# The next change: the turn, the gesture's start and end, the load put down.
			var next := p.lengths[i]
			if local < turn_at:
				next = turn_at
			if gesture >= 0.0:
				if local < gesture:
					next = minf(next, gesture)
				elif local < gesture + GESTURE_SECONDS[action]:
					next = minf(next, gesture + GESTURE_SECONDS[action])
				if local < gesture + 0.5:
					next = minf(next, gesture + 0.5)
			# (A delay being made up runs this clock up to twice as fast.)
			p.steady_until = t + (next - local) * (0.5 if p.delay > 0.0 else 1.0) - 0.002
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
			p.steady_until = t + (p.lengths[i] - local) * (0.5 if p.delay > 0.0 else 1.0) - 0.002
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
	var manual := zoom > ANIM_FAR_ZOOM + 3.0 or (anim_manual and zoom > ANIM_FAR_ZOOM - 3.0)
	if manual != anim_manual:
		anim_manual = manual
		for p in people:
			if p.ready:
				set_manual(p)
	frame_count += 1
	var mark := Time.get_ticks_usec()
	var count := people.size()
	# Zoomed out (people a few pixels tall: 0.06 m, a 20th of a second's walk, is under a
	# pixel) each person on screen is placed every FAR_STRIDE-th frame, on its own beat (with
	# its pose, ANIM_FAR_HZ).
	var halved := anim_manual and not jumped and not simulate_all
	for i in count:
		var p := people[i]
		# Off screen only the clock runs: the place is worked out every sixth frame (for the
		# test whether the person comes into view, and for those walking behind).
		if not p.shown and not jumped and not simulate_all and (frame_count + i) % 6 != 0 and p.ready:
			continue
		if halved and p.shown and (frame_count + i) % FAR_STRIDE != 0:
			continue
		if p.steady_until > t and not jumped and not simulate_all:
			# Standing (or inside) with nothing changing yet.
			continue
		var was_index := p.index
		var was_walked := p.walked
		var was_walking := p.walking
		var since := t - p.eval_t
		p.eval_t = t
		evaluate(p, t)
		p.pos = p.at
		# The feet keep pace with the distance actually walked since the last frame (held back
		# behind someone included).
		if p.walking and was_walking and p.index == was_index and since > 0.0 and since < 0.3 and p.shown:
			p.v = maxf(0.0, p.walked - was_walked) / since
	var mark2 := Time.get_ticks_usec()
	section_usec[0] += mark2 - mark
	# Holding back changes slowly: worked out at 30 Hz (15 Hz zoomed out).
	hold_dt += dt
	if follow and hold_dt > 0.0 and (hold_dt >= (0.066 if anim_manual else 0.03) or simulate_all):
		hold_back(hold_dt)
		hold_dt = 0.0
	mark = Time.get_ticks_usec()
	section_usec[1] += mark - mark2
	var blob_index := 0
	var anim_spent := 0
	for i in count:
		var p := people[i]
		if halved and p.shown and (frame_count + i) % FAR_STRIDE != 0 and p.heading == p.want_yaw:
			# (Not its beat; still turning, it turns every frame.)
			blob_index += 1
			continue
		var on_screen := p.alpha > 0.01 and (simulate_all or camera.is_position_in_frustum(Vector3(p.pos.x, p.y + 0.9, p.pos.y)))
		if on_screen and not p.shown and not jumped and p.eval_t != t:
			# Coming into view: the place of this very frame.
			p.eval_t = t
			evaluate(p, t)
			p.pos = p.at
			on_screen = p.alpha > 0.01
		var pdt := clampf(t - p.pose_t, 0.0, 0.25) if p.pose_t >= 0.0 else dt
		p.pose_t = t
		var yaw := p.want_yaw
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
			var limit := TURN_RATE * pdt
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
		if anim_manual and p.rig.player != null:
			p.anim_acc += pdt
			if snap or p.anim_acc >= 1.0 / ANIM_FAR_HZ:
				var before := Time.get_ticks_usec()
				p.rig.player.advance(p.anim_acc)
				p.anim_acc = 0.0
				anim_spent += Time.get_ticks_usec() - before
		if absf(p.alpha - p.alpha_now) > 0.001:
			p.alpha_now = p.alpha
			for mesh in p.meshes:
				mesh.transparency = 1.0 - p.alpha
		if p.prop != null and p.carrying != p.prop_shown:
			p.prop_shown = p.carrying
			p.prop.visible = p.carrying
		blob_index += 1
	# The townsfolk's own update (the AnimationPlayers' work, done by the engine at full rate
	# close up, is measured apart).
	var spent := Time.get_ticks_usec() - started - anim_spent
	section_usec[2] += Time.get_ticks_usec() - mark - anim_spent
	update_usec = spent
	if update_samples.size() < 4096:
		update_samples.append(spent)
	if anim_samples.size() < 4096:
		anim_samples.append(anim_spent)

## Manual mode (zoomed out) or the engine's own (close up); each person on its own beat.
func set_manual(p: Person) -> void:
	var player: AnimationPlayer = p.rig.player
	if player == null:
		return
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL if anim_manual else AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	p.anim_acc = fposmod(float(p.seed % 977) * 0.0131, 1.0 / ANIM_FAR_HZ)

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
	var rate := 1.0
	if want == C_WALK or want == C_LOADED:
		rate = clampf(p.v / (STRIDE_SPEED[want] * p.scale), 0.05, 2.0)
	elif want == C_IDLE:
		rate = p.idle_rate
	if rate != player.speed_scale:
		player.speed_scale = rate

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
		set_manual(p)
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
		"doors": door_stop.values().map(func(v: Vector2): return [v.x, v.y]),
		"places": yard_spots.keys().map(func(n: int): return [g_nodes[n].x, g_nodes[n].y, place_kind.get(n, "")]),
		"meets": meet_pairs.map(func(m: Array): return [g_nodes[m[0]].x, g_nodes[m[0]].y, g_nodes[m[1]].x, g_nodes[m[1]].y]),
		"bridges": bridges.map(func(b: Array): return [b[0].x, b[0].y, b[1].x, b[1].y, b[2]])}
