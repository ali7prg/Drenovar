extends Node3D

## Wall guards (build 1024): longbowmen (ENG-03) and crossbowmen (ENG-04) keeping watch on the
## city wall (src/city_walls.gd), so the town reads as guarded and alive.
##
## * Who: a visible share of the archers of src/city_defence.gd (that table counts
##   towers x (2 + wall) archers, 16-112): guards_wanted() = 8 at wall I up to 20 at wall V with
##   hall V. About 2/3 longbowmen, 1/3 crossbowmen, each +-3 % in size, the surcoat and hood in
##   one of three cloth shades.
## * Where (only on what the wall really draws, CityWalls.walkway() and CityWalls.towers):
##   - patrols walk the walkway (wall II+) between two towers, on the middle of its free band
##     (between the posts / merlons / gallery boards and the rail), stopping TOWER_BERTH before a
##     tower's body (its corner posts and watch room included) and before the main gate scene.
##     At each end: stop, turn to the parapet, look out, look along the wall, now and then draw
##     the bow / reload the crossbow (one dwell in four at most), turn back, walk back.
##     PATROL_SHARE of the guards off the gate (as many as there are stretches): the walkway is
##     where the game's camera sees them (wall V's covered gallery hides most of it but by the
##     towers), the towers' roofs hide the decks from wall III up;
##   - sentries stand on tower decks (wall I has no walkway: only there), on the deck's side
##     towards the camera, mostly still, facing out, turning their gaze slowly, and now and then
##     taking a few steps along the deck's edge;
##   - a pair stands on the inner side of the main gate, beside the passage (clear of the gate
##     scene: the SUP-03 spans of assets/city/town_solids.json).
##   No wall, no guards on it.
## * Motion: the whole day is a function of the clock (like src/townsfolk.gd): seeded cycles, so
##   no two guards move in step; walks ease in and out (RAMP), the walk clip plays at ground
##   speed / stride (GaitTable, no sliding), standing turns are eased (<= 1.6 rad/s) and the shown
##   heading never turns faster than TURN_RATE.
## * Feet: on the walkway's top (which follows the slope from wall sample to wall sample) or the
##   deck's top, exactly: the route's heights are the surfaces' own (qa_wall_guards.gd checks them
##   against the drawn boxes).
## * Cost: the models (the troop field model, and the preview model's meshes close up) are loaded
##   on a worker through the landscape's loader and instanced one per frame; off screen a guard
##   is hidden and its AnimationPlayer stopped (only the clock runs); zoomed out the clips are
##   posed ANIM_FAR_HZ times a second on each guard's own beat; standing guards are not evaluated
##   until something changes. Contact shadows: one multimesh; sun shadows only close up.
## * Plan: on a change of the wall (level, ring, gates) the route on it is worked out over a few
##   frames (step_plan(): segment frames, the points a third of the ring a frame, berths and
##   stretches, the gate pair, the posts; ~1-2 ms a frame), the guards hidden meanwhile; when only
##   the town changed, the posts are planned again in one frame from the route kept. Guards keep
##   their models across plans (the same post first, then their kind, then the spare rigs).

const WarriorVisual = preload("res://src/warrior_visual.gd")
const GaitTable = preload("res://src/gait_table.gd")
const CityWalls = preload("res://src/city_walls.gd")

const UNITS: Array[String] = ["ENG-03", "ENG-04"]
const C_IDLE := 0
const C_WALK := 1
const C_ACT := 2
const CLIPS := {"ENG-03": [&"Idle", &"Walk", &"Bow_Draw"], "ENG-04": [&"Idle", &"Walk", &"Crossbow_Reload"]}
## Bow_Draw and Crossbow_Reload are 2.0 s long.
const ACT_SECONDS := 2.0
const K_WALK := 0
const K_STAND := 1
const TURN_RATE := 5.0
const RAMP := 0.55
const BLEND := 0.3
const LOD_NEAR_ZOOM := 40.0
const SHADOW_ZOOM := 50.0
const ANIM_FAR_ZOOM := 50.0
const ANIM_FAR_HZ := 20.0
const FAR_STRIDE := 3
## Calm patrol pace (m/s; the walk clip at ~0.75 of its speed), and a sentry's few steps.
const PATROL_PACE := 1.0
const SENTRY_PACE := 0.85
## A tower's body grown by its corner posts and the level IV watch room (m), and the berth a
## guard's centre keeps from that.
const TOWER_GROW := 0.3
const TOWER_BERTH := 0.65
## The share of the guards (off the gate pair) walking the walkway where there is one.
const PATROL_SHARE := 0.65
## Shortest walkway stretch walked (m) and the longest beat of one patrol.
const MIN_STRETCH := 6.0
## A body's half width, the headroom a guard needs and the highest step between two segments'
## boards a patrol walks over (m).
const BODY := 0.28
const HEADROOM := 1.95
const MAX_STEP := 0.12
const MAX_PATROL := 26.0
## Half the main gate scene's width (local units, SUP-03 spans in town_solids.json: 48-52 cells
## of 0.25) by wall level; the patrols stop GATE_BERTH m before it.
const GATE_HALF_LOCAL: Array[float] = [6.0, 6.0, 6.0, 6.25, 6.5]
const GATE_BERTH := 0.9
## Cloth shades (surcoat, skirt, scarf, hood): as authored, a warmer and a cooler dye.
const TINTS: Array[Color] = [Color(1.0, 1.0, 1.0), Color(1.08, 0.98, 0.86), Color(0.86, 0.9, 1.0)]
const CLOTH := ["surcoat", "linen_skirt", "scarf", "hood"]
## Parts a few pixels or less zoomed out (a 1.7 m guard is ~12 px tall at zoom 70): not drawn
## there, four to five draw calls less per guard.
const FAR_HIDDEN := ["Eyes", "Pouch", "Belt", "Baldric", "Bracers"]

class Guard extends RefCounted:
	var key := ""
	var unit := "ENG-03"
	var role := ""
	var seed := 0
	var scale := 1.0
	var tint := 0
	var idle_rate := 1.0
	var cycle := 1.0
	var phase := 0.0
	var stride := 1.31
	# Timeline.
	var kinds := PackedInt32Array()
	var starts := PackedFloat32Array()
	var lengths := PackedFloat32Array()
	var at_a := PackedVector3Array()
	var yaw_from := PackedFloat32Array()
	var yaw_to := PackedFloat32Array()
	var turn_len := PackedFloat32Array()
	var act_at := PackedFloat32Array()
	var leg := PackedInt32Array()
	var speed := PackedFloat32Array()
	var lines: Array[PackedVector3Array] = []
	var cums: Array[PackedFloat32Array] = []
	## QA / debug: the posts this guard stands at and the beat it walks.
	var beat := PackedVector3Array()
	# Runtime.
	var node: Node3D = null
	var player: AnimationPlayer = null
	var meshes: Array[MeshInstance3D] = []
	var ready := false
	var shown := false
	var heading := 0.0
	var clip_now := -1
	var lod := -1
	## The LOD whose meshes are on the model (LOD1 only once the preview meshes are in).
	var lod_mesh := 2
	var anim_acc := 0.0
	var eval_t := -1.0
	var pose_t := -1.0
	var steady_until := -1.0
	var blob_hidden := false
	var placed := Vector3.INF
	var placed_yaw := INF
	# Evaluated.
	var pos := Vector3.ZERO
	var want_yaw := 0.0
	var v := 0.0
	var walked := 0.0
	var walking := false
	var turning := false
	var clip_want := C_IDLE
	var clip_offset := 0.0
	var index := 0
	var local := 0.0

	func adopt(old: Guard) -> void:
		node = old.node
		player = old.player
		meshes = old.meshes
		ready = old.ready
		shown = old.shown
		heading = old.heading
		clip_now = old.clip_now
		lod = old.lod
		lod_mesh = old.lod_mesh
		blob_hidden = old.blob_hidden
		old.node = null

var stage: Node3D
var guards: Array[Guard] = []
var signature := ""
var replans := 0
var last_plan_usec := 0
## QA: microseconds of the last plan's steps.
var plan_profile := {}
var last_time := -1.0
var frame_count := 0
var lod_level := 2
var cast_real_shadows := false
var anim_manual := false
var blobs: MultiMeshInstance3D
## QA: evaluate and pose every guard as if on screen.
var simulate_all := false
## QA: microseconds of the guards' own update per frame, and of the AnimationPlayers advanced in
## manual mode (measured apart), and of instancing models.
var update_usec := 0
var update_samples := PackedInt32Array()
var anim_samples := PackedInt32Array()
var instance_samples := PackedInt32Array()
## Rigs instanced but not in the plan (a smaller plan); reused before instancing anew.
var spare := {"ENG-03": [], "ENG-04": []}
## Meshes of each LOD by unit and mesh name: {unit: {name: [mesh, skin] per LOD 1..2}}.
var lod_meshes := {}
var lod1_state := ""
var tinted := {}
## QA / debug: the walkway stretches of the last plan and where each guard stands.
var stretches: Array = []
var gate_spots: Array = []
var walk: Dictionary = {}

func setup(owner_stage: Node3D) -> void:
	stage = owner_stage
	name = "WallGuards"

# ------------------------------------------------------------------ plan

## How many guards are drawn on the wall: 8 at wall I up to 20 at wall V with hall V (the defence
## table's archers are 16-112; each guard on screen costs a skeleton and ~18.6k source
## triangles, see qa_wall_guards.gd).
static func guards_wanted(hall: int, wall: int) -> int:
	return clampi(2 + 3 * clampi(wall, 1, 5) + clampi(hall, 1, 5), 8, 20)

## What the route on the wall depends on: the ring, its level and gates, the wall's build.
func wall_key() -> String:
	var walls = stage.walls
	if not walls.visible:
		return "none"
	return "%s|%d" % [walls.signature, walls.builds]

func layout_key() -> String:
	var walls = stage.walls
	if not walls.visible:
		return "none"
	var gate: Variant = stage.get("gate_node")
	# (The pair at the main gate keeps off the townsfolk's ways: planned again with them.)
	var tf: Variant = stage.get("townsfolk")
	var town := -1
	if tf != null and is_instance_valid(tf):
		town = int(tf.rebuilds) * 2 + (1 if tf.building else 0)
	return "%s|%d|%d" % [wall_key(), gate.get_instance_id() if gate is Node3D and is_instance_valid(gate) else 0, town]

## The plan at once (tools; present() spreads it over frames with step_plan()).
func replan() -> void:
	var started := Time.get_ticks_usec()
	var key := layout_key()
	plan_profile.clear()
	if not plan_walkway():
		stretches.clear()
		route_key = wall_key()
	elif wall_key() != route_key:
		find_stretches(clampi(stage.walls.wall_level, 1, 5))
		route_key = wall_key()
	apply_plan(key, plan_specs())
	last_plan_usec = Time.get_ticks_usec() - started
	plan_frames = 1
	plan_slice_worst = last_plan_usec

## A plan worked out over a few frames, no frame carrying much of it: {key, wall, step, next,
## hide, usec, frames}. While the wall's route is worked out anew (the wall itself changed) the
## guards are hidden: the old posts are not on the new wall.
var job := {}
## The wall (wall_key()) whose route (route_*, stretches) is worked out.
var route_key := ""
## Wall segments' route points worked out a frame.
const ROUTE_CHUNK := 48
## QA: frames the last plan took, and its dearest frame (microseconds).
var plan_frames := 0
var plan_slice_worst := 0

func start_plan(key: String) -> void:
	job = {"key": key, "wall": wall_key(), "step": 0, "next": 0, "usec": 0, "frames": 0}
	job.hide = job.wall != route_key and not guards.is_empty()
	plan_profile.clear()

## The walkway of the wall as it stands (false: no wall, or no walkway on it).
func plan_walkway() -> bool:
	var walls = stage.walls
	walk = {}
	if not walls.visible or walls.radii.size() != CityWalls.SAMPLES:
		return false
	walk = CityWalls.walkway(clampi(walls.wall_level, 1, 5))
	return not walk.is_empty()

## One step of the plan in progress: the route (segment frames, the points a chunk of the ring at a
## time, the berths and stretches) when the wall changed, then the guards and their posts.
func step_plan() -> void:
	var started := Time.get_ticks_usec()
	var level: int = clampi(stage.walls.wall_level, 1, 5)
	var step := int(job.step)
	if step == 0:
		if plan_walkway() and job.wall != route_key:
			route_begin(level)
			job.step = 1
		else:
			if walk.is_empty():
				stretches.clear()
				route_key = job.wall
			job.step = 3
	elif step == 1:
		var lo := int(job.next)
		var hi := mini(lo + ROUTE_CHUNK, CityWalls.SAMPLES)
		route_points(lo, hi)
		job.next = hi
		if hi >= CityWalls.SAMPLES:
			job.step = 2
	elif step == 2:
		route_finish(level)
		route_key = job.wall
		job.step = 3
	var spent := Time.get_ticks_usec() - started
	if step <= 2:
		plan_profile["route"] = int(plan_profile.get("route", 0)) + spent
		var tag := "step%d" % step
		plan_profile[tag] = maxi(int(plan_profile.get(tag, 0)), spent)
	if int(job.step) == 3 and step <= 2 and (step != 0 or spent > 1500):
		# (The gate pair in a frame of its own after a route step.)
		job.usec = int(job.usec) + spent
		job.frames = int(job.frames) + 1
		plan_slice_worst = maxi(plan_slice_worst, spent)
		return
	if int(job.step) == 3:
		var before := Time.get_ticks_usec()
		job.gate = main_gate_spots(level) if stage.walls.visible else []
		plan_profile["gate"] = Time.get_ticks_usec() - before
		job.step = 4
		spent = Time.get_ticks_usec() - started
		if spent > 1500:
			# (The posts in the next frame.)
			job.usec = int(job.usec) + spent
			job.frames = int(job.frames) + 1
			plan_slice_worst = maxi(plan_slice_worst, spent)
			return
	if int(job.step) == 4:
		var before := Time.get_ticks_usec()
		apply_plan(job.key, plan_specs(job.gate))
		plan_profile["posts"] = Time.get_ticks_usec() - before
		spent = Time.get_ticks_usec() - started
		last_plan_usec = int(job.usec) + spent
		plan_frames = int(job.frames) + 1
		plan_slice_worst = maxi(plan_slice_worst, spent)
		job = {}
		return
	job.usec = int(job.usec) + spent
	job.frames = int(job.frames) + 1
	plan_slice_worst = maxi(plan_slice_worst, spent)

## The guards of a new plan take their models from the old one: the same post first, then any of
## their kind, then the spare rigs.
func apply_plan(key: String, specs: Array) -> void:
	signature = key
	replans += 1
	var fresh: Array[Guard] = []
	for spec: Guard in specs:
		fresh.append(spec)
	# Each guard keeps a model of its kind from the previous plan (the same post first).
	var previous: Array[Guard] = guards.duplicate()
	for g in fresh:
		for old in previous:
			if old.key == g.key and old.unit == g.unit and old.node != null:
				g.adopt(old)
				break
	for g in fresh:
		if g.node != null:
			continue
		for old in previous:
			if old.unit == g.unit and old.node != null:
				g.adopt(old)
				break
	for old in previous:
		if old.node != null and is_instance_valid(old.node):
			old.node.visible = false
			old.node.process_mode = Node.PROCESS_MODE_DISABLED
			spare[old.unit].append(old.node)
		old.node = null
	for g in fresh:
		g.steady_until = -1.0
		g.eval_t = -1.0
		g.placed = Vector3.INF
		g.walked = 0.0
		if g.node == null and not spare[g.unit].is_empty():
			bind(g, spare[g.unit].pop_back())
	guards = fresh
	ensure_blobs()

## The guards of the wall as it stands now (no nodes).
func plan_specs(gate_pair: Variant = null) -> Array:
	gate_spots.clear()
	var walls = stage.walls
	if not walls.visible or walls.radii.size() != CityWalls.SAMPLES:
		return []
	var level: int = clampi(walls.wall_level, 1, 5)
	var hall: int = clampi(walls.hall_level, 1, 5)
	var budget := guards_wanted(hall, level)
	walk = CityWalls.walkway(level)
	var specs: Array = []
	var count := 0
	var mark := Time.get_ticks_usec()
	if gate_pair == null:
		gate_pair = main_gate_spots(level)
		plan_profile["gate"] = Time.get_ticks_usec() - mark
	mark = Time.get_ticks_usec()
	# The pair at the main gate.
	for spot in gate_pair:
		var g := new_guard("gate%d" % count, count)
		g.role = "gate"
		var p: Vector3 = spot[0]
		var face: float = spot[1]
		sentry_timeline(g, [p], face, 0.55, false)
		specs.append(g)
		gate_spots.append(p)
		count += 1
	for stretch: Dictionary in stretches:
		stretch.patrolled = false
	var towers: Array = walls.towers
	var rest := budget - count
	var patrols := 0
	if not stretches.is_empty():
		# (Most of them on the walkway: from the game's camera the towers' roofs hide the decks
		# but at wall I-II, see deck_places().)
		patrols = mini(stretches.size(), roundi(rest * PATROL_SHARE))
		if towers.is_empty():
			patrols = mini(stretches.size(), rest)
	var sentries := mini(rest - patrols, towers.size() * 2)
	# Patrols: the stretches beside the main gate first (the front of the town), then the longest.
	var order: Array = range(stretches.size())
	order.sort_custom(func(a: int, b: int) -> bool:
		var sa: Dictionary = stretches[a]
		var sb: Dictionary = stretches[b]
		var ka: float = sa.length + (100.0 if sa.by_gate else 0.0)
		var kb: float = sb.length + (100.0 if sb.by_gate else 0.0)
		return ka > kb)
	for k in patrols:
		var stretch: Dictionary = stretches[order[k]]
		var g := new_guard("patrol%d" % k, count)
		g.role = "patrol"
		patrol_timeline(g, stretch)
		stretch.patrolled = true
		specs.append(g)
		count += 1
	# Sentries: gate towers first (a gatehouse deck), then spread evenly round the ring.
	var picks: Array = []
	var gate_towers: Array = []
	var plain: Array = []
	for t in towers.size():
		if int(towers[t].gate) >= 0:
			gate_towers.append(t)
		else:
			plain.append(t)
	var ring: Array = []
	if not plain.is_empty():
		var n := plain.size()
		var want := mini(n, maxi(0, sentries - gate_towers.size()))
		for k in want:
			ring.append(plain[int(floor((k + 0.5) * n / float(want)))])
	for t in gate_towers + ring:
		if picks.size() < sentries:
			picks.append(t)
	var second := 0
	# (A second sentry only on plain towers: on a gate tower the bridge's roof over the opening
	# leaves room for one, on the side away from the gate.)
	while picks.size() < sentries and second < plain.size():
		picks.append(plain[second])
		second += 1
	var on_tower := {}
	for t: int in picks:
		on_tower[t] = int(on_tower.get(t, 0)) + 1
	var seen := {}
	for t: int in picks:
		var slot := int(seen.get(t, 0))
		seen[t] = slot + 1
		var g := new_guard("tower%d-%d" % [int(towers[t].index), slot], count)
		g.role = "tower"
		tower_timeline(g, towers[t], level, slot, int(on_tower[t]))
		specs.append(g)
		count += 1
	plan_profile["timelines"] = Time.get_ticks_usec() - mark
	return specs

func new_guard(key: String, ordinal: int) -> Guard:
	var g := Guard.new()
	g.key = key
	g.seed = hash(key)
	var rng := seeded(key)
	# Two longbowmen to a crossbowman.
	g.unit = UNITS[1] if ordinal % 3 == 1 else UNITS[0]
	g.scale = rng.randf_range(0.97, 1.03)
	g.tint = rng.randi_range(0, TINTS.size() - 1)
	g.idle_rate = rng.randf_range(0.85, 1.1)
	g.stride = float(GaitTable.STANCE_SPEED[g.unit].walk) * g.scale
	return g

static func seeded(text: String) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(text) & 0x7fffffff
	return rng

## The walkway's centre line round the ring, cut where there is no walkway (gate openings), no
## room (a sharp bend), at the towers and at the main gate scene: the stretches a patrol may walk,
## each {line, length, by_gate}. Each wall segment's piece runs from joint to joint (each joint
## pushed in by the mean of its two segments' inward directions) with a point in its middle and
## one at every place the boards under it change: where a neighbour segment's boards begin or end
## (or its parapet / rail comes within a body's width) and where two segments' boards cross in
## height. In between, the boards' top is linear: the route's height is the drawn one everywhere.
## (find_stretches() at once; a re-plan spreads route_points() over frames, see step_plan().)
func find_stretches(level: int) -> void:
	route_begin(level)
	route_points(0, CityWalls.SAMPLES)
	route_finish(level)

## The route's points of the last plan (1 free; 0 no walkway (a gate opening) or no room (off
## the boards, or posts / rails / merlons / the gallery roof within a body's width); 2 a tower's
## berth; 3 the main gate scene) and the wall segment of each.
var route_pts := PackedVector3Array()
var route_free := PackedByteArray()
var route_seg := PackedInt32Array()
var route_joints := PackedVector3Array()

func route_begin(level: int) -> void:
	stretches.clear()
	var n: int = CityWalls.SAMPLES
	var offset: float = walk.offset
	frame_segments(level)
	route_joints.resize(n)
	for i in n:
		route_joints[i] = seg_a[i] + (seg_in[i] + seg_in[posmod(i - 1, n)]).normalized() * offset
	route_pts.resize(0)
	route_free.resize(0)
	route_seg.resize(0)

## The route's points on wall segments lo .. hi - 1.
func route_points(lo: int, hi: int) -> void:
	var n: int = CityWalls.SAMPLES
	var joints := route_joints
	var ts := PackedFloat32Array()
	for i in range(lo, hi):
		var j0 := joints[i]
		var j1 := joints[(i + 1) % n]
		ts.resize(0)
		ts.append(0.0)
		ts.append(0.5)
		if not seg_gate[i]:
			for k in 3:
				var j := posmod(i + k - 1, n)
				if seg_gate[j]:
					continue
				var s0 := seg_s(j, j0)
				var s1 := seg_s(j, j1)
				var d := s1 - s0
				if absf(d) < 0.0001:
					continue
				# Where its boards end (a point a centimetre either side: the boards of two
				# segments meet with a step at a steep bend) and where its parapet comes in reach.
				var ext := seg_ext(j)
				var step := 0.01 / maxf(absf(d), 0.01)
				for edge: float in [-ext, seg_len[j] + ext]:
					var t := (edge - s0) / d
					for e: float in [t - step, t + step]:
						if e > 0.005 and e < 0.995:
							ts.append(e)
				for edge: float in [-BODY, seg_len[j] + BODY]:
					var t := (edge - s0) / d
					if t > 0.005 and t < 0.995:
						ts.append(t)
				if j != i:
					# Where this neighbour's boards and segment i's cross in height.
					var h0 := seg_a[j].y + seg_rise[j] * s0 - (seg_a[i].y + seg_rise[i] * seg_s(i, j0))
					var h1 := seg_a[j].y + seg_rise[j] * s1 - (seg_a[i].y + seg_rise[i] * seg_s(i, j1))
					if (h0 < 0.0) != (h1 < 0.0) and absf(h1 - h0) > 0.00001:
						var t := h0 / (h0 - h1)
						if t > 0.005 and t < 0.995:
							ts.append(t)
			ts.sort()
		var last := -1.0
		for t in ts:
			if t - last < 0.002:
				continue
			last = t
			var p := j0.lerp(j1, t)
			var gate_gap: bool = seg_gate[i] or (t == 0.0 and seg_gate[posmod(i - 1, n)])
			var y := NAN if gate_gap else walk_height(p, i)
			p.y = y if not is_nan(y) else seg_a[i].y + float(walk.top)
			# (Two segments' boards meeting with a step a body cannot take in a stride: no way.)
			var blocked := is_nan(y)
			var count := route_pts.size()
			if count > 0 and not blocked:
				var q := route_pts[count - 1]
				if Vector2(p.x - q.x, p.z - q.z).length() < 0.05 and absf(p.y - q.y) > MAX_STEP:
					blocked = true
					route_free[count - 1] = 0
			route_pts.append(p)
			route_seg.append(i)
			route_free.append(0 if blocked else 1)

## The berths of the towers and the gate scene, and the runs of free points: the stretches.
func route_finish(level: int) -> void:
	var walls = stage.walls
	var pts := route_pts
	var free := route_free
	var seg_of := route_seg
	var total := pts.size()
	plan_profile["points"] = total
	var gate_half: float = GATE_HALF_LOCAL[level - 1] * stage.gate_scene_scale(level) + GATE_BERTH
	var gate_at: Vector3 = walls.main_gate
	var gate_out: Vector3 = walls.main_gate_outward
	var gate_along := gate_out.cross(Vector3.UP).normalized()
	var near_gate := PackedByteArray()
	near_gate.resize(total)
	for k in total:
		var p := pts[k]
		if free[k] == 0:
			continue
		if not tower_clear(p, seg_of[k]):
			free[k] = 2
		elif walls.custom_main_gate:
			var d := p - gate_at
			if absf(d.dot(gate_along)) < gate_half and absf(d.dot(gate_out)) < 8.0:
				free[k] = 3
				near_gate[k] = 1
			# (Next to the gate opening of the ring itself.)
			elif Vector2(d.x, d.z).length() < gate_half + 1.5:
				near_gate[k] = 1
	# Runs of free points, round the ring from a blocked one.
	var first := -1
	for k in total:
		if free[k] != 1:
			first = k
			break
	if first < 0:
		return
	var k := 0
	while k < total:
		var at := (first + k) % total
		if free[at] != 1:
			k += 1
			continue
		var line := PackedVector3Array()
		var before := posmod(at - 1, total)
		var by_gate := near_gate[before] == 1
		# The ends reach as far towards a tower or the gate scene as the berth allows.
		if free[before] >= 2:
			line.append(reach_end(pts[at], pts[before], seg_of[before], free[before] == 3))
		while k < total and free[(first + k) % total] == 1:
			line.append(pts[(first + k) % total])
			k += 1
		var after := (first + k) % total
		by_gate = by_gate or near_gate[after] == 1
		if free[after] >= 2:
			line.append(reach_end(line[line.size() - 1], pts[after], seg_of[posmod(after - 1, total)], free[after] == 3))
		var length := 0.0
		for j in range(1, line.size()):
			length += line[j].distance_to(line[j - 1])
		if length >= MIN_STRETCH:
			stretches.append({"line": line, "length": length, "by_gate": by_gate, "patrolled": false})

## The boards of a wall segment reach this far past its ends along the slope (span(..., extra
## 0.06) in city_walls.gd): at a bend outward of the wall line they close the wedge between two
## segments.
const EXT := 0.03
## Per wall segment j (from wall sample j to j + 1) of the last plan: its start on the ground, its
## flat direction and length, inward direction, rise per metre, whether it is a gate opening, the
## gallery roof's inverse transform (wall V), and the towers within reach of it.
var seg_a := PackedVector3Array()
var seg_along := PackedVector3Array()
var seg_in := PackedVector3Array()
var seg_len := PackedFloat32Array()
var seg_rise := PackedFloat32Array()
var seg_gate := PackedByteArray()
var seg_roof: Array[Transform3D] = []
var seg_towers: Array = []

func frame_segments(level: int) -> void:
	var walls = stage.walls
	var n: int = CityWalls.SAMPLES
	seg_a.resize(n)
	for i in n:
		var w: Vector2 = walls.wall_point(i)
		seg_a[i] = Vector3(w.x, float(walls.height_at.call(w.x, w.y)), w.y)
	seg_along.resize(n)
	seg_in.resize(n)
	seg_len.resize(n)
	seg_rise.resize(n)
	seg_gate.resize(n)
	seg_roof.clear()
	seg_towers.clear()
	seg_towers.resize(n)
	for i in n:
		var a := seg_a[i]
		var b := seg_a[(i + 1) % n]
		var flat := Vector3(b.x - a.x, 0.0, b.z - a.z)
		var length := flat.length()
		seg_len[i] = length
		seg_along[i] = flat / maxf(length, 0.0001)
		seg_rise[i] = (b.y - a.y) / maxf(length, 0.0001)
		seg_in[i] = walls.inward_of(a, b)
		seg_gate[i] = 1 if walls.is_gate_segment(i) else 0
	if walk.get("roof", false):
		seg_roof.resize(n)
		for i in n:
			seg_roof[i] = walls.gallery_roof(seg_a[i], seg_a[(i + 1) % n], level).affine_inverse()
	# A tower stands on a wall sample; its body and berth reach at most ~4 m (under 5 samples
	# even round the smallest yard).
	for t in walls.towers.size():
		var at := int(walls.towers[t].index)
		for i in range(at - 5, at + 5):
			var slot := posmod(i, n)
			if seg_towers[slot] == null:
				seg_towers[slot] = [t]
			else:
				seg_towers[slot].append(t)

## How far (flat metres) the boards of segment j reach past its ends.
func seg_ext(j: int) -> float:
	return EXT / sqrt(1.0 + seg_rise[j] * seg_rise[j])

## How far along wall segment j (flat metres from its start) p is.
func seg_s(j: int, p: Vector3) -> float:
	var a := seg_a[j]
	var al := seg_along[j]
	return (p.x - a.x) * al.x + (p.z - a.z) * al.z

## Height of the walkway's boards at p (on wall segment i's piece of the route), NAN where a guard
## does not fit: no boards under the feet (0.2 m in from their edge), something of the parapet,
## posts or rails within BODY m of the body, the gallery roof lower than HEADROOM above the feet.
func walk_height(p: Vector3, i: int) -> float:
	var n := seg_a.size()
	var y := NAN
	var offset: float = walk.offset
	var band: float = float(walk.half) - BODY + 0.001
	var deck: float = walk.deck
	var deck_lim: float = float(walk.deck_half) - 0.2
	var top: float = walk.top
	for k in 3:
		var j := i + k - 1
		if j < 0:
			j += n
		elif j >= n:
			j -= n
		if seg_gate[j]:
			continue
		var a := seg_a[j]
		var dx := p.x - a.x
		var dz := p.z - a.z
		var al := seg_along[j]
		var s := dx * al.x + dz * al.z
		var length := seg_len[j]
		if s < -BODY or s > length + BODY:
			continue
		var inw := seg_in[j]
		var lateral := dx * inw.x + dz * inw.z
		# Within reach of this segment's parapet and rails: inside the free band.
		if absf(lateral - offset) > band:
			return NAN
		var ext := EXT / sqrt(1.0 + seg_rise[j] * seg_rise[j])
		if s >= -ext and s <= length + ext and absf(lateral - deck) <= deck_lim:
			var h := a.y + seg_rise[j] * s + top
			y = h if is_nan(y) else maxf(y, h)
	if is_nan(y) or seg_roof.is_empty():
		return y
	for k in 3:
		var inverse: Transform3D = seg_roof[posmod(i + k - 1, n)]
		var low := inverse * Vector3(p.x, y, p.z)
		var high := inverse * Vector3(p.x, y + 1.0, p.z)
		var rise := high.y - low.y
		if absf(rise) < 0.0001:
			continue
		# The height above the feet where the slab's underside (local y -0.5) is.
		var under := (-0.5 - low.y) / rise
		var at := low.lerp(high, under)
		if absf(at.x) <= 0.5 + BODY and absf(at.z) <= 0.5 + BODY and under < HEADROOM:
			return NAN
	return y

## Clear of every tower's berth near wall segment i.
func tower_clear(p: Vector3, i: int) -> bool:
	var near: Variant = seg_towers[i]
	if near == null:
		return true
	for t: int in near:
		if tower_distance(stage.walls.towers[t], p) < TOWER_BERTH:
			return false
	return true

## The last point from `inside` (clear) towards `blocked` that keeps the berth of every tower
## (or of the main gate scene), on the straight line between them (consecutive route points on
## wall segment i's piece), at the boards' height there.
func reach_end(inside: Vector3, blocked: Vector3, i: int, gate: bool) -> Vector3:
	var lo := 0.0
	var hi := 1.0
	for step in 12:
		var mid := (lo + hi) * 0.5
		var p := inside.lerp(blocked, mid)
		if end_clear(p, i, gate) and not is_nan(walk_height(p, i)):
			lo = mid
		else:
			hi = mid
	var p := inside.lerp(blocked, lo)
	var y := walk_height(p, i)
	if not is_nan(y):
		p.y = y
	return p

func end_clear(p: Vector3, i: int, gate: bool) -> bool:
	var walls = stage.walls
	if gate:
		var level: int = clampi(walls.wall_level, 1, 5)
		var gate_half: float = GATE_HALF_LOCAL[level - 1] * stage.gate_scene_scale(level) + GATE_BERTH
		var out: Vector3 = walls.main_gate_outward
		var d: Vector3 = p - walls.main_gate
		return absf(d.dot(out.cross(Vector3.UP).normalized())) >= gate_half or absf(d.dot(out)) >= 8.0
	return tower_clear(p, i)

## Horizontal distance from p to a tower's body grown by TOWER_GROW (0 inside).
static func tower_distance(tower: Dictionary, p: Vector3) -> float:
	var c: Vector3 = tower.p
	var out: Vector3 = tower.out
	var side := out.cross(Vector3.UP).normalized()
	var half: float = float(tower.size) * 0.5 + TOWER_GROW
	var d := Vector3(p.x - c.x, 0.0, p.z - c.z)
	var dx := maxf(absf(d.dot(side)) - half, 0.0)
	var dz := maxf(absf(d.dot(out)) - half, 0.0)
	return Vector2(dx, dz).length()

## Candidate places of the gate pair, nearest the gate first.
var gate_order := PackedVector2Array()
## The pair's last places and the gate they were for.
var gate_last: Array = []
var gate_last_key := ""

## Places of the pair at the main gate: on the ground inside the yard, beside the passage, clear
## of the gate scene (its SUP-03 spans, or the plain table when it has none); [position, yaw].
func main_gate_spots(level: int) -> Array:
	var walls = stage.walls
	var gate: Variant = stage.get("gate_node")
	if not walls.custom_main_gate or not gate is Node3D or not is_instance_valid(gate):
		return []
	# While the townsfolk work out their ways the pair keeps its last places at the same gate (a
	# plan follows when they are done).
	var tf: Variant = stage.get("townsfolk")
	var gate_key := "%d|%d|%s" % [(gate as Node3D).get_instance_id(), level, str(walls.main_gate)]
	if tf == null or not is_instance_valid(tf) or tf.building:
		return gate_last.duplicate() if gate_key == gate_last_key else []
	var scale: float = stage.gate_scene_scale(level)
	var spans := gate_spans(level)
	var out: Vector3 = walls.main_gate_outward
	var along := out.cross(Vector3.UP).normalized()
	var centre: Vector3 = walls.main_gate
	var result: Array = []
	town_edges = edges_near(Vector2(centre.x, centre.z), 16.0)
	var inverse := (gate as Node3D).global_transform.affine_inverse()
	if gate_order.is_empty():
		# Candidates (depth in from the gate, lateral from the passage's middle), nearest first.
		var keyed := PackedFloat64Array()
		var depth := 1.5
		while depth <= 8.0:
			var lateral := 3.0
			while lateral <= 8.0:
				keyed.append(floorf((depth + lateral * 0.8) * 64.0) * 4096.0 + gate_order.size())
				gate_order.append(Vector2(depth, lateral))
				lateral += 0.25
			depth += 0.25
		keyed.sort()
		var sorted := PackedVector2Array()
		for key in keyed:
			sorted.append(gate_order[int(key) % 4096])
		gate_order = sorted
	var tests := 0
	var town_tests := 0
	for side: float in [-1.0, 1.0]:
		var best := Vector3.INF
		for c in gate_order:
			var p: Vector3 = centre - out * c.x + along * side * c.y
			tests += 1
			if walls.inside(p.x, p.z, 1.2) and spot_clear(spans, inverse, scale, p):
				town_tests += 1
				if clear_of_town(Vector2(p.x, p.z)):
					best = p
					break
		if best == Vector3.INF:
			continue
		best = stage.walk_ground(best)
		# Facing the passage, a little outward.
		var look := (-along * side + -out * 0.25).normalized()
		result.append([best, atan2(look.x, look.z)])
	plan_profile["gate_tests"] = tests
	plan_profile["gate_town_tests"] = town_tests
	gate_last = result
	gate_last_key = gate_key
	return result

## Off the townsfolk's ways (every edge of their walk graph and its free band, with a berth),
## clear of building solids, trees and water: nobody walks through a gate sentry.
var town_edges: Array = []

## The townsfolk's walk graph edges within `reach` m of p: [a, b, berth].
func edges_near(p: Vector2, reach: float) -> Array:
	var found: Array = []
	var tf: Variant = stage.get("townsfolk")
	if tf == null or not is_instance_valid(tf) or tf.building:
		return found
	var nodes: PackedVector2Array = tf.g_nodes
	var ea: PackedInt32Array = tf.e_a
	var eb: PackedInt32Array = tf.e_b
	var live: PackedByteArray = tf.e_live
	var lateral: PackedFloat32Array = tf.e_lat
	for e in ea.size():
		if not live[e]:
			continue
		var a := nodes[ea[e]]
		var b := nodes[eb[e]]
		if p.distance_squared_to(Geometry2D.get_closest_point_to_segment(p, a, b)) < reach * reach:
			found.append([a, b, lateral[e] + 0.95])
	return found

func clear_of_town(p: Vector2) -> bool:
	var tf: Variant = stage.get("townsfolk")
	if tf == null or not is_instance_valid(tf) or tf.building:
		return false
	for edge: Array in town_edges:
		var q := Geometry2D.get_closest_point_to_segment(p, edge[0], edge[1])
		var berth: float = edge[2]
		if p.distance_squared_to(q) < berth * berth:
			return false
	if stage.near_standing_tree(p, 1.21):
		return false
	var reason: String = tf.blocked_reason(p)
	return reason.is_empty() or reason == "unpainted"

## The SUP-03 spans of the gate scene (town_solids.json through the townsfolk table), or {}.
func gate_spans(level: int) -> Dictionary:
	var tf: Variant = stage.get("townsfolk")
	if tf == null or not is_instance_valid(tf):
		return {}
	var entry: Dictionary = tf.solid_entry("SUP-03", level)
	var spans: Variant = entry.get("spans")
	if not spans is Dictionary or int(spans.w) == 0:
		return {}
	if not spans.has("raw"):
		spans.raw = Marshalls.base64_to_raw(str(spans.bytes))
	return spans

## Clear of the gate scene within 0.55 m (any part of it from the ground up to 2.2 m; its paving
## is the road, which a guard keeps off as well).
func spot_clear(spans: Dictionary, inverse: Transform3D, scale: float, p: Vector3) -> bool:
	if spans.is_empty():
		return false
	var reach := 0.55 / scale
	var raw: PackedByteArray = spans.raw
	var w := int(spans.w)
	var h := int(spans.h)
	var local := inverse * Vector3(p.x, p.y, p.z)
	var x := -reach
	while x <= reach + 0.001:
		var z := -reach
		while z <= reach + 0.001:
			var cx := floori((local.x + x) / 0.25) - int(spans.x0)
			var cz := floori((local.z + z) / 0.25) - int(spans.z0)
			if cx >= 0 and cz >= 0 and cx < w and cz < h:
				var i := cz * w + cx
				if raw[i * 2] <= raw[i * 2 + 1]:
					return false
			z += 0.25
		x += 0.25
	return true

# ------------------------------------------------------------------ timelines

## Seconds to walk `distance` easing in and out over RAMP.
static func walk_time(distance: float, cruise: float) -> float:
	if distance >= cruise * RAMP:
		return distance / cruise + RAMP
	return 2.0 * sqrt(distance * RAMP / cruise)

func add_stand(g: Guard, at: Vector3, from: float, to: float, turn: float, hold: float, act := -1.0) -> void:
	g.kinds.append(K_STAND)
	g.starts.append(g.cycle)
	var length := turn + hold
	g.lengths.append(length)
	g.at_a.append(at)
	g.yaw_from.append(from)
	g.yaw_to.append(to)
	g.turn_len.append(turn)
	g.act_at.append(act)
	g.leg.append(-1)
	g.speed.append(0.0)
	g.cycle += length

func add_walk(g: Guard, line: PackedVector3Array, cruise: float) -> void:
	var cum := PackedFloat32Array([0.0])
	for j in range(1, line.size()):
		cum.append(cum[j - 1] + line[j].distance_to(line[j - 1]))
	g.lines.append(line)
	g.cums.append(cum)
	var length := walk_time(cum[cum.size() - 1], cruise)
	g.kinds.append(K_WALK)
	g.starts.append(g.cycle)
	g.lengths.append(length)
	g.at_a.append(line[0])
	g.yaw_from.append(0.0)
	g.yaw_to.append(0.0)
	g.turn_len.append(0.0)
	g.act_at.append(-1.0)
	g.leg.append(g.lines.size() - 1)
	g.speed.append(cruise)
	g.cycle += length

static func heading_of(a: Vector3, b: Vector3) -> float:
	return atan2(b.x - a.x, b.z - a.z)

## A turn of `delta` rad standing, eased: about 1.1 rad/s at its quickest (never above 1.6).
static func turn_time(delta: float) -> float:
	return clampf(absf(delta) * 1.35, 0.6, 2.6)

## Walk the beat, stop, turn to the parapet, look out and along the wall, (now and then) draw or
## reload, turn back; the same at the other end. Two round trips per cycle, each dwell its own.
func patrol_timeline(g: Guard, stretch: Dictionary) -> void:
	var rng := seeded(g.key + "|beat")
	var full: PackedVector3Array = stretch.line
	var line := full
	var length: float = stretch.length
	if length > MAX_PATROL:
		# A beat of 18-26 m at one end of a long stretch (the end by a tower, or by the gate).
		var beat := rng.randf_range(18.0, MAX_PATROL)
		line = cut(full, 0.0, beat) if rng.randf() < 0.5 else cut(full, length - beat, length)
	var back := line.duplicate()
	back.reverse()
	var cruise := PATROL_PACE * rng.randf_range(0.92, 1.08) * g.scale
	g.beat = line
	var ends: Array = [line[line.size() - 1], line[0]]
	var arrive: Array = [heading_of(line[line.size() - 2], line[line.size() - 1]), heading_of(back[back.size() - 2], back[back.size() - 1])]
	var leave: Array = [heading_of(back[0], back[1]), heading_of(line[0], line[1])]
	var outward: Array = [outward_yaw(line, line.size() - 1), outward_yaw(line, 0)]
	# One dwell in four draws the bow / reloads (and some guards never do in a cycle).
	var act_dwell := rng.randi_range(0, 5)
	g.cycle = 0.0
	for trip in 2:
		for end in 2:
			add_walk(g, line if end == 0 else back, cruise)
			var dwell := trip * 2 + end
			var at: Vector3 = ends[end]
			var out: float = outward[end]
			var came: float = arrive[end]
			var go: float = leave[end]
			# Turn to the parapet and look out.
			add_stand(g, at, came, out, turn_time(angle_difference(came, out)), rng.randf_range(1.8, 3.5))
			# Look along the wall (outward and to one side), then the other way.
			var sweep := rng.randf_range(0.45, 0.7) * (1.0 if rng.randf() < 0.5 else -1.0)
			add_stand(g, at, out, out + sweep, turn_time(sweep), rng.randf_range(1.2, 2.6))
			var act := -1.0
			var hold := rng.randf_range(1.0, 2.4)
			if dwell == act_dwell:
				act = turn_time(sweep * 1.8) + 0.4
				hold = 0.4 + ACT_SECONDS + rng.randf_range(0.6, 1.2)
			add_stand(g, at, out + sweep, out - sweep * 0.7, turn_time(sweep * 1.7), hold, act)
			# Back to face the walk back.
			add_stand(g, at, out - sweep * 0.7, go, turn_time(angle_difference(out - sweep * 0.7, go)), rng.randf_range(0.2, 0.6))
	g.phase = rng.randf() * g.cycle

## The yaw looking out over the parapet at point k of a walkway line.
func outward_yaw(line: PackedVector3Array, k: int) -> float:
	var walls = stage.walls
	var p := line[k]
	var d := Vector3(p.x - walls.center.x, 0.0, p.z - walls.center.y)
	return atan2(d.x, d.z)

## A piece of a line from s0 to s1 metres along it.
static func cut(line: PackedVector3Array, s0: float, s1: float) -> PackedVector3Array:
	var result := PackedVector3Array()
	var s := 0.0
	for j in range(1, line.size()):
		var a := line[j - 1]
		var b := line[j]
		var piece := a.distance_to(b)
		if s + piece >= s0 and s <= s1:
			var t0 := clampf((s0 - s) / maxf(piece, 0.0001), 0.0, 1.0)
			var t1 := clampf((s1 - s) / maxf(piece, 0.0001), 0.0, 1.0)
			if result.is_empty():
				result.append(a.lerp(b, t0))
			result.append(a.lerp(b, t1))
		s += piece
	return result

## A sentry on a tower deck: two places on the deck (its own when two share it), facing out, the
## gaze turning slowly, now and then crossing to the other place.
func tower_timeline(g: Guard, tower: Dictionary, level: int, slot: int, sharing: int) -> void:
	var out: Vector3 = tower.out
	var places := deck_places(tower, level, [])
	if slot > 0 and sharing > 1:
		places = deck_places(tower, level, places)
	sentry_timeline(g, places, atan2(out.x, out.z), 0.6, true)

## The city camera looks from target + (75, 83, 75) (landscape.apply_camera_pose()): the deck's
## side towards it is what shows under the tower's roof.
const CAMERA_FLAT := Vector3(0.70710678, 0.0, 0.70710678)

## Two places on a tower's deck, as near the deck's edge towards the city camera as the body
## allows (the pyramid roof reaches far over the deck: only there does a sentry's head and
## shoulders show under it, on wall I-II; higher, the roofs hide the decks whatever the place),
## clear of the corner pillars, of the level V merlons and, on a gate tower, of the covered
## bridge over the opening (the side away from the gate), 1-1.6 m apart; and none within 1.2 m of
## `taken` (another sentry's places on the deck).
func deck_places(tower: Dictionary, level: int, taken: Array) -> Array:
	var size: float = tower.size
	var out: Vector3 = tower.out
	var side := out.cross(Vector3.UP).normalized()
	var p: Vector3 = tower.p
	var deck_y: float = p.y + float(tower.deck)
	# The deck reaches size / 2 + 0.45; at level V merlons stand on it from size / 2 - 0.2.
	var edge := size * 0.5 - 0.5 if level >= 5 else size * 0.5 + 0.1
	var pillar := size * 0.5 + 0.25
	var away := 0.0
	var gate := int(tower.gate)
	if gate >= 0:
		var opening: Vector2 = stage.walls.wall_point(stage.walls.gates[gate])
		away = -1.0 if (Vector3(opening.x, 0.0, opening.y) - p).dot(side) > 0.0 else 1.0
	var cs := CAMERA_FLAT.dot(side)
	var co := CAMERA_FLAT.dot(out)
	var spots: Array = []
	var steps := ceili(edge / 0.4)
	for a in range(-steps, steps + 1):
		var u := edge * a / steps
		for b in range(-steps, steps + 1):
			var v := edge * b / steps
			var clear := Vector2(absf(u) - pillar, absf(v) - pillar).length() >= 0.5
			if clear and away != 0.0 and u * away < 1.0:
				clear = false
			if clear:
				var at := p + side * u + out * v
				at.y = deck_y
				for q: Vector3 in taken:
					if at.distance_to(q) < 1.2:
						clear = false
				if clear:
					spots.append([u * cs + v * co, at])
	if spots.is_empty():
		var centre := p
		centre.y = deck_y
		return [centre]
	spots.sort_custom(func(x: Array, y: Array) -> bool: return x[0] > y[0])
	var first: Vector3 = spots[0][1]
	for spot: Array in spots:
		var d := first.distance_to(spot[1])
		if d >= 1.0 and d <= 1.6:
			return [first, spot[1]]
	return [first]

## A sentry's cycle: at each place (one or two) face `face`, look to one side and the other, and
## with two places walk to the other one; now and then draw / reload (seeded).
func sentry_timeline(g: Guard, places: Array, face: float, sweep_max: float, shift: bool) -> void:
	var rng := seeded(g.key + "|post")
	g.cycle = 0.0
	g.beat = PackedVector3Array(places)
	var act_round := rng.randi_range(0, 2 * places.size())
	var yaw := face
	for k in places.size():
		var at: Vector3 = places[k]
		var nxt: Vector3 = places[(k + 1) % places.size()]
		var rounds := rng.randi_range(1, 2)
		for r in rounds:
			var hold := rng.randf_range(4.0, 9.0)
			add_stand(g, at, yaw, face, turn_time(angle_difference(yaw, face)), hold)
			var sweep := rng.randf_range(0.35, sweep_max) * (1.0 if rng.randf() < 0.5 else -1.0)
			add_stand(g, at, face, face + sweep, turn_time(sweep) * 1.4, rng.randf_range(2.5, 6.0))
			var act := -1.0
			var rest := rng.randf_range(2.5, 6.0)
			if k * 2 + r == act_round:
				act = turn_time(sweep * 1.6) * 1.4 + 0.5
				rest = 0.5 + ACT_SECONDS + rng.randf_range(1.0, 2.5)
			add_stand(g, at, face + sweep, face - sweep * 0.8, turn_time(sweep * 1.8) * 1.4, rest, act)
			yaw = face - sweep * 0.8
		if shift and places.size() > 1:
			var go := heading_of(at, nxt)
			add_stand(g, at, yaw, go, turn_time(angle_difference(yaw, go)), 0.3)
			add_walk(g, PackedVector3Array([at, nxt]), SENTRY_PACE * g.scale)
			yaw = go
	# Back to the first heading at the cycle's end (it starts there again).
	if absf(angle_difference(yaw, face)) > 0.01:
		add_stand(g, places[0], yaw, face, turn_time(angle_difference(yaw, face)), 0.5)
	g.phase = rng.randf() * g.cycle

# ------------------------------------------------------------------ per frame

## Place, heading and clip of a guard at clock time t (seconds). No allocations.
func evaluate(g: Guard, t: float) -> void:
	var u := fposmod(t + g.phase, g.cycle)
	var i := clampi(g.starts.bsearch(u, false) - 1, 0, g.kinds.size() - 1)
	var local := u - g.starts[i]
	g.index = i
	g.local = local
	g.v = 0.0
	g.walking = false
	g.turning = false
	g.clip_offset = 0.0
	g.steady_until = -1.0
	if g.kinds[i] == K_WALK:
		var line: PackedVector3Array = g.lines[g.leg[i]]
		var cum: PackedFloat32Array = g.cums[g.leg[i]]
		var total := cum[cum.size() - 1]
		var cruise := g.speed[i]
		var duration := g.lengths[i]
		var s := 0.0
		var accel := cruise / RAMP
		if total >= cruise * RAMP:
			if local < RAMP:
				s = 0.5 * accel * local * local
				g.v = accel * local
			elif local < duration - RAMP:
				s = 0.5 * cruise * RAMP + cruise * (local - RAMP)
				g.v = cruise
			else:
				var rest := maxf(duration - local, 0.0)
				s = total - 0.5 * accel * rest * rest
				g.v = accel * rest
		else:
			var half := duration * 0.5
			if local < half:
				s = 0.5 * accel * local * local
				g.v = accel * local
			else:
				var rest := maxf(duration - local, 0.0)
				s = total - 0.5 * accel * rest * rest
				g.v = accel * rest
		s = clampf(s, 0.0, total)
		g.walked = s
		var j := clampi(cum.bsearch(s, false) - 1, 0, line.size() - 2)
		var piece := cum[j + 1] - cum[j]
		var a := line[j]
		var b := line[j + 1]
		g.pos = a.lerp(b, (s - cum[j]) / piece if piece > 0.0001 else 0.0)
		if piece > 0.001:
			g.want_yaw = atan2(b.x - a.x, b.z - a.z)
		g.walking = true
		g.clip_want = C_WALK if g.v > 0.12 else C_IDLE
		return
	g.pos = g.at_a[i]
	var turn := g.turn_len[i]
	if local < turn:
		var k := local / turn
		g.want_yaw = g.yaw_from[i] + angle_difference(g.yaw_from[i], g.yaw_to[i]) * k * k * (3.0 - 2.0 * k)
		g.turning = true
	else:
		g.want_yaw = g.yaw_to[i]
	g.clip_want = C_IDLE
	var act := g.act_at[i]
	var next := g.lengths[i]
	if act >= 0.0:
		if local >= act and local < act + ACT_SECONDS:
			g.clip_want = C_ACT
			g.clip_offset = local - act
			next = act + ACT_SECONDS
		elif local < act:
			next = act
	if not g.turning:
		g.steady_until = t + (next - local) - 0.002

## QA: microseconds of the last present() as a whole (re-plan and instancing included).
var frame_usec := 0

func present(t: float) -> void:
	var started := Time.get_ticks_usec()
	if stage == null:
		return
	var key := layout_key()
	if key != signature and (job.is_empty() or job.key != key):
		start_plan(key)
	if not job.is_empty():
		step_plan()
	var planned := Time.get_ticks_usec() - started
	if not job.is_empty() and job.hide:
		# The wall changed under the guards: hidden till their new posts are worked out.
		for i in guards.size():
			var g := guards[i]
			if g.node != null and g.shown:
				g.shown = false
				g.node.visible = false
				g.node.process_mode = Node.PROCESS_MODE_DISABLED
			if blobs != null and not g.blob_hidden and i < blobs.multimesh.instance_count:
				g.blob_hidden = true
				blobs.multimesh.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), Vector3.ZERO))
		frame_usec = Time.get_ticks_usec() - started
		return
	var dt := clampf(t - last_time, 0.0, 0.25) if last_time >= 0.0 else 0.0
	var jumped := last_time < 0.0 or absf(t - last_time) > 1.0
	last_time = t
	frame_count += 1
	var camera: Camera3D = stage.camera
	var zoom: float = stage.camera_zoom
	if lod_level == 2 and zoom < LOD_NEAR_ZOOM - 3.0:
		lod_level = 1
	elif lod_level == 1 and zoom > LOD_NEAR_ZOOM + 3.0:
		lod_level = 2
	var shadows := zoom < SHADOW_ZOOM - 3.0 or (cast_real_shadows and zoom < SHADOW_ZOOM + 3.0)
	if shadows != cast_real_shadows:
		cast_real_shadows = shadows
		for g in guards:
			for mesh in g.meshes:
				mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var manual := zoom > ANIM_FAR_ZOOM + 3.0 or (anim_manual and zoom > ANIM_FAR_ZOOM - 3.0)
	if manual != anim_manual:
		anim_manual = manual
		for g in guards:
			if g.ready:
				set_manual(g)
	var instanced := make_rigs()
	var halved := anim_manual and not jumped and not simulate_all
	var count := guards.size()
	var swaps := 0
	var anim_spent := 0
	for i in count:
		var g := guards[i]
		if g.node == null:
			continue
		# Off screen only the clock runs: worked out every sixth frame (to see it come into view).
		if not g.shown and not jumped and not simulate_all and (frame_count + i) % 6 != 0:
			continue
		var beat := (frame_count + i) % FAR_STRIDE == 0
		if halved and g.shown and not beat and g.heading == g.want_yaw:
			continue
		if (g.steady_until <= t or jumped or simulate_all) and (not halved or not g.shown or beat):
			var was_index := g.index
			var was_walked := g.walked
			var was_walking := g.walking
			var since := t - g.eval_t
			g.eval_t = t
			evaluate(g, t)
			# The feet keep pace with the distance walked since the last evaluation.
			if g.walking and was_walking and g.index == was_index and since > 0.0 and since < 0.3 and g.shown:
				g.v = maxf(0.0, g.walked - was_walked) / since
		var on_screen := simulate_all or camera.is_position_in_frustum(g.pos + Vector3.UP * 0.9)
		var pdt := clampf(t - g.pose_t, 0.0, 0.25) if g.pose_t >= 0.0 else dt
		g.pose_t = t
		if not on_screen or not g.ready:
			if g.shown:
				g.shown = false
				g.node.visible = false
				g.node.process_mode = Node.PROCESS_MODE_DISABLED
			if blobs != null and not g.blob_hidden:
				g.blob_hidden = true
				blobs.multimesh.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), Vector3.ZERO))
			continue
		var snap := not g.shown or jumped
		if not g.shown:
			g.shown = true
			g.node.visible = true
			g.node.process_mode = Node.PROCESS_MODE_INHERIT
		if g.lod != lod_level and (swaps < 4 or snap or simulate_all):
			# (Four guards a frame change their meshes; the first sight at once.)
			set_lod(g, lod_level)
			swaps += 1
		if snap:
			g.heading = g.want_yaw
		else:
			var turn := angle_difference(g.heading, g.want_yaw)
			var limit := TURN_RATE * pdt
			g.heading = wrapf(g.heading + clampf(turn, -limit, limit), -PI, PI)
		if snap or g.pos != g.placed or g.heading != g.placed_yaw:
			g.placed = g.pos
			g.placed_yaw = g.heading
			g.node.transform = Transform3D(Basis(Vector3.UP, g.heading).scaled(Vector3.ONE * g.scale), g.pos)
			if blobs != null:
				g.blob_hidden = false
				var size := 0.95 * g.scale
				blobs.multimesh.set_instance_transform(i, Transform3D(Basis().scaled(Vector3(size, 1.0, size)), g.pos + Vector3.UP * 0.03))
		animate(g, snap)
		if anim_manual and g.player != null:
			g.anim_acc += pdt
			if snap or g.anim_acc >= 1.0 / ANIM_FAR_HZ:
				var before := Time.get_ticks_usec()
				g.player.advance(g.anim_acc)
				g.anim_acc = 0.0
				anim_spent += Time.get_ticks_usec() - before
	frame_usec = Time.get_ticks_usec() - started
	update_usec = frame_usec - anim_spent - instanced - planned
	if update_samples.size() < 4096:
		update_samples.append(update_usec)
	if anim_samples.size() < 4096:
		anim_samples.append(anim_spent)

func set_manual(g: Guard) -> void:
	if g.player == null:
		return
	g.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL if anim_manual else AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	g.anim_acc = fposmod(float(g.seed % 977) * 0.0131, 1.0 / ANIM_FAR_HZ)

func animate(g: Guard, snap: bool) -> void:
	var player := g.player
	if player == null:
		return
	var want := g.clip_want
	var names: Array = CLIPS[g.unit]
	if want != g.clip_now:
		g.clip_now = want
		player.play(names[want], 0.0 if snap else BLEND)
		if want == C_ACT:
			if g.clip_offset > 0.05:
				player.seek(g.clip_offset, true)
		elif snap or want == C_IDLE:
			player.seek(fposmod(float(g.seed % 1000) * 0.0131, 1.0) * player.current_animation_length, true)
	elif snap and want == C_ACT:
		player.seek(g.clip_offset, true)
	var rate := 1.0
	if want == C_WALK:
		rate = clampf(g.v / g.stride, 0.05, 2.0)
	elif want == C_IDLE:
		rate = g.idle_rate
	if rate != player.speed_scale:
		player.speed_scale = rate

# ------------------------------------------------------------------ models

## One model a frame for a guard without one (the troop field model, loaded on a worker by the
## landscape); then, all in, the preview meshes for close up. Microseconds spent.
func make_rigs() -> int:
	var started := Time.get_ticks_usec()
	for g in guards:
		if g.node != null:
			continue
		var path := field_path(g.unit)
		if path.is_empty() or not stage.model_ready(path):
			return Time.get_ticks_usec() - started
		var node: Node3D = stage.add_warrior(self, path, Transform3D.IDENTITY)
		node.name = "Guard_%s" % g.key.validate_node_name()
		bind(g, node)
		remember_lod(g.unit, 2, g.meshes)
		var spent := Time.get_ticks_usec() - started
		if instance_samples.size() < 256:
			instance_samples.append(spent)
		return spent
	if lod1_state != "ready" and lod1_state != "failed" and not guards.is_empty():
		load_lod1()
	return Time.get_ticks_usec() - started

func field_path(unit: String) -> String:
	var models: Dictionary = stage.data.get("unitModels", {})
	return str(models[unit].field) if models.has(unit) else ""

func preview_path(unit: String) -> String:
	var models: Dictionary = stage.data.get("unitModels", {})
	return str(models[unit].preview) if models.has(unit) else ""

## A model taken into a guard's service: clips looped, cloth shade, shadows, manual posing.
func bind(g: Guard, node: Node3D) -> void:
	g.node = node
	node.visible = false
	node.process_mode = Node.PROCESS_MODE_DISABLED
	g.meshes.clear()
	for mesh: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		g.meshes.append(mesh)
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_real_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var players := node.find_children("*", "AnimationPlayer", true, false)
	g.player = players[0] if not players.is_empty() else null
	if g.player != null:
		for clip: StringName in [&"Idle", &"Walk"]:
			if g.player.has_animation(clip):
				g.player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
		g.player.playback_default_blend_time = BLEND
		set_manual(g)
	g.lod = -1
	g.lod_mesh = 2
	# (A spare model may still wear the preview meshes.)
	var table: Dictionary = lod_meshes.get(g.unit, {})
	for mesh in g.meshes:
		var entry: Array = table.get(mesh.name, [])
		if entry.size() >= 4 and entry[0] != null and mesh.mesh == entry[0]:
			g.lod_mesh = 1
			break
	g.clip_now = -1
	g.shown = false
	g.ready = true
	g.blob_hidden = false
	shade(g)

func shade(g: Guard) -> void:
	for mesh in g.meshes:
		for s in mesh.mesh.get_surface_count():
			mesh.set_surface_override_material(s, cloth(mesh.mesh.surface_get_material(s), g.tint))

## The cloth materials in the guard's shade (shared per material and shade), else null.
func cloth(material: Material, tint: int) -> Material:
	if tint == 0 or not material is BaseMaterial3D:
		return null
	var lower := String(material.resource_name).to_lower()
	var dyed := false
	for part: String in CLOTH:
		if lower.contains(part):
			dyed = true
	if not dyed:
		return null
	var key := [material.get_instance_id(), tint]
	if not tinted.has(key):
		var copy := (material as BaseMaterial3D).duplicate() as BaseMaterial3D
		copy.albedo_color = copy.albedo_color * TINTS[tint]
		tinted[key] = copy
	return tinted[key]

func remember_lod(unit: String, level: int, meshes: Array) -> void:
	var table: Dictionary = lod_meshes.get(unit, {})
	for mesh: MeshInstance3D in meshes:
		var entry: Array = table.get(mesh.name, [null, null, null, null])
		if entry[(level - 1) * 2] == null:
			entry[(level - 1) * 2] = mesh.mesh
			entry[(level - 1) * 2 + 1] = mesh.skin
		table[mesh.name] = entry
	lod_meshes[unit] = table

## The preview (LOD1) models' meshes: loaded on a worker, instanced once (materials prepared as
## the troops' are), kept by mesh name; the template is freed.
func load_lod1() -> void:
	lod1_state = "loading"
	for unit in UNITS:
		var table: Dictionary = lod_meshes.get(unit, {})
		if table.is_empty():
			return
		var sample: Array = table.values()[0]
		if sample[0] != null:
			continue
		var path := preview_path(unit)
		if path.is_empty():
			lod1_state = "failed"
			return
		if not stage.model_ready(path):
			return
		var template: Node3D = stage.scene_resource(path).instantiate() as Node3D
		WarriorVisual.prepare(template)
		remember_lod(unit, 1, template.find_children("*", "MeshInstance3D", true, false))
		template.free()
		return
	lod1_state = "ready"
	# Guards already close up take the preview meshes now.
	for g in guards:
		g.lod = -1

## Close up the preview model's meshes (and skins), zoomed out the field model's.
func set_lod(g: Guard, level: int) -> void:
	g.lod = level
	for mesh in g.meshes:
		var small := false
		for part: String in FAR_HIDDEN:
			if String(mesh.name).contains(part):
				small = true
		mesh.visible = level == 1 or not small
	var table: Dictionary = lod_meshes.get(g.unit, {})
	var want := level
	if want == 1 and (table.is_empty() or (table.values()[0] as Array)[0] == null):
		want = 2
	if want == g.lod_mesh:
		return
	for mesh in g.meshes:
		var entry: Array = table.get(mesh.name, [])
		if entry.size() < 4 or entry[(want - 1) * 2] == null:
			continue
		mesh.mesh = entry[(want - 1) * 2]
		mesh.skin = entry[(want - 1) * 2 + 1]
	g.lod_mesh = want
	shade(g)

## Soft contact shadows of all guards: one multimesh, one draw call.
func ensure_blobs() -> void:
	if blobs == null:
		var fade := Gradient.new()
		fade.colors = PackedColorArray([Color(0.03, 0.045, 0.04, 0.6), Color(0.03, 0.045, 0.04, 0.0)])
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
	if blobs.multimesh.instance_count != guards.size():
		blobs.multimesh.instance_count = guards.size()
	for i in guards.size():
		blobs.multimesh.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), Vector3.ZERO))
		guards[i].blob_hidden = true

# ------------------------------------------------------------------ QA / debug

## The plan for the top-down map (qa_wall_guards.gd --dump): the wall, towers, stretches, beats.
func debug_dump() -> Dictionary:
	var walls = stage.walls
	var wall: Array = []
	if walls.visible:
		for i in CityWalls.SAMPLES:
			var w: Vector2 = walls.wall_point(i)
			wall.append([w.x, w.y, 1 if walls.is_gate_segment(i) else 0])
	return {"level": walls.wall_level, "hall": walls.hall_level, "wall": wall, "walk": walk,
		"towers": walls.towers.map(func(t: Dictionary): return {"x": t.p.x, "z": t.p.z, "size": t.size, "out": [t.out.x, t.out.z], "gate": t.gate}),
		"gate": [walls.main_gate.x, walls.main_gate.z, walls.main_gate_outward.x, walls.main_gate_outward.z],
		"stretches": stretches.map(func(s: Dictionary): return {"line": Array(s.line).map(func(p: Vector3): return [p.x, p.z]), "length": s.length, "patrolled": s.patrolled}),
		"guards": guards.map(func(g: Guard): return {"key": g.key, "unit": g.unit, "role": g.role, "cycle": g.cycle,
			"beat": Array(g.beat).map(func(p: Vector3): return [p.x, p.z])})}
