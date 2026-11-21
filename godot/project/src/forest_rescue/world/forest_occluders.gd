extends Node3D
## Whole-tree occluder fade (replaces the old dithered crown cut-away).
##
## The layout keeps trails, glades, the arena and the horse spot clear for the fixed city camera
## (tools/build_forest_layout.gd, Rules.crown_capsule). For the few trees left that can still hide
## an adventure actor or a site prop (resource trees that cannot move, actors off the trail), this
## node checks every UPDATE_SECONDS which tree crowns sit between the camera and a target, and
## draws each of them — at most MAX_FADED, nearest first — with a per-tree copy that composites
## the WHOLE tree over the scene at MIN_OPACITY (forest_wind_fade*.gdshader: screen-copy blend,
## no dither, the crown is never cut). The tree's canopy / impostor instance is hidden meanwhile
## (ForestCanopy.set_instance_hidden), a shadow-only copy keeps its shadow on the ground.

const Rules = preload("res://src/forest_rescue/world/forest_layout_rules.gd")
const ForestCanopy = preload("res://src/forest_rescue/world/forest_canopy.gd")
const ForestKit = preload("res://src/forest_rescue/world/forest_kit.gd")
const FADE_SHADER := preload("res://src/forest_rescue/world/forest_wind_fade.gdshader")
const FADE_CUTOUT_SHADER := preload("res://src/forest_rescue/world/forest_wind_cutout_fade.gdshader")

const MIN_OPACITY := 0.35
const MAX_FADED := 8
const FADE_IN_SECONDS := 0.3
const FADE_OUT_SECONDS := 0.45
const HOLD_SECONDS := 0.6          # a tree stays faded this long after it stops hiding anyone
const UPDATE_SECONDS := 0.2
const BEHIND := 10.0               # m: trunks this far beyond a target (away from the camera)
const REACH := 34.0                # m: trunks this far toward the camera from a target

var canopy: Node3D
var world: Node3D
var faded: Dictionary = {}         # "cell:mesh:x:z" -> {node, shadow, opacity, hold, cell, mesh, origin}
var last_query := {"targets": 0, "candidates": 0, "hiding": 0, "ms": 0.0}
var _shapes: Dictionary = {}       # mesh index -> [species, variant] ([] = not a tree)
var _timer := 0.0
static var _fade_materials: Dictionary = {}   # source material id -> fade ShaderMaterial


func _init(owner_world: Node3D, forest_canopy: Node3D) -> void:
	name = "OccluderFade"
	world = owner_world
	canopy = forest_canopy


func _process(delta: float) -> void:
	var changed := false
	for key in faded.keys():
		var entry: Dictionary = faded[key]
		entry.hold -= delta
		var target := MIN_OPACITY if entry.hold > 0.0 else 1.0
		var rate := (1.0 - MIN_OPACITY) / (FADE_IN_SECONDS if target < entry.opacity else FADE_OUT_SECONDS)
		entry.opacity = move_toward(entry.opacity, target, rate * delta)
		(entry.node as GeometryInstance3D).set_instance_shader_parameter("tree_opacity", entry.opacity)
		if entry.hold <= 0.0 and entry.opacity >= 1.0:
			_release(key)
			changed = true
	if changed:
		_refresh_canopy()


## targets: [[Vector3 feet, float height], …] (visible adventure actors and site props).
func update_targets(targets: Array, delta: float) -> void:
	_timer -= delta
	if _timer > 0.0:
		return
	_timer = UPDATE_SECONDS
	var started := Time.get_ticks_usec()
	var hits := query(targets)
	var ranked: Array = hits.keys()
	ranked.sort_custom(func(a, b): return hits[a].score > hits[b].score)
	var changed := false
	for i in mini(ranked.size(), MAX_FADED + faded.size()):
		var key: String = ranked[i]
		if faded.has(key):
			faded[key].hold = HOLD_SECONDS
		elif _active_count() < MAX_FADED:
			_begin(key, hits[key])
			changed = true
	if changed:
		_refresh_canopy()
	last_query.ms = (Time.get_ticks_usec() - started) / 1000.0


func _active_count() -> int:
	var count := 0
	for key in faded:
		if faded[key].hold > 0.0:
			count += 1
	return count


## Trees whose crown hides at least one target: key -> {score, cell, mesh, origin, transform}.
## Same geometry as the layout builder (Rules.crown_capsule), inlined: crown centre C, the crown
## part between heights max(h0 - target height, 0) and h1 projected along the camera view.
func query(targets: Array) -> Dictionary:
	var result := {}
	last_query.targets = targets.size()
	last_query.candidates = 0
	last_query.hiding = 0
	if targets.is_empty() or canopy == null:
		return result
	# A crown hides a target only from the camera side (+X+Z): per target, trunks inside
	# [g - BEHIND, g + REACH]; canopy cells touching those boxes.
	var cell_targets := {}
	for index in targets.size():
		var feet: Vector3 = targets[index][0]
		var c0 := _cell_xy(feet.x - BEHIND, feet.z - BEHIND)
		var c1 := _cell_xy(feet.x + REACH, feet.z + REACH)
		for j in range(c0.y, c1.y + 1):
			for i in range(c0.x, c1.x + 1):
				var cell := j * ForestCanopy.CELLS + i
				if not cell_targets.has(cell):
					cell_targets[cell] = PackedInt32Array()
				cell_targets[cell].append(index)
	var shift := Vector2.ONE * Rules.VIEW_SHIFT
	for cell in cell_targets:
		var near: PackedInt32Array = cell_targets[cell]
		var buffers: Dictionary = canopy.visible_buffers(cell)
		for mesh_index in buffers:
			var shape := _shape(mesh_index)
			if shape.is_empty():
				continue
			var dims: Array = Rules.crown_shape(shape[0], shape[1])
			var offset := Vector2(float(dims[3]), float(dims[4]))
			var buffer: PackedFloat32Array = buffers[mesh_index]
			for n in buffer.size() / ForestCanopy.STRIDE:
				var o := n * ForestCanopy.STRIDE
				var x := buffer[o + 3]
				var z := buffer[o + 11]
				var score := 0.0
				var tested := false
				var crown_c := Vector2.ZERO
				var h0 := 0.0
				var r := 0.0
				var a := Vector2.ZERO
				for index in near:
					var feet: Vector3 = targets[index][0]
					if x < feet.x - BEHIND or x > feet.x + REACH or z < feet.z - BEHIND or z > feet.z + REACH:
						continue
					if not tested:
						tested = true
						last_query.candidates += 1
						var axis := Vector3(buffer[o], buffer[o + 4], buffer[o + 8])
						var scale := axis.length()
						crown_c = Vector2(x, z) + offset.rotated(-atan2(-axis.z, axis.x)) * scale
						h0 = float(dims[0]) * scale
						r = float(dims[2]) * scale + Rules.UNIT_RADIUS
						a = crown_c - shift * (float(dims[1]) * scale)
					var g := Vector2(feet.x, feet.z)
					var b := crown_c - shift * maxf(0.0, h0 - float(targets[index][1]))
					if Geometry2D.get_closest_point_to_segment(g, a, b).distance_squared_to(g) < r * r:
						score += 10.0 - minf(9.0, Vector2(x, z).distance_to(g) * 0.25)
				if score > 0.0:
					var key := "%d:%d:%.2f:%.2f" % [cell, mesh_index, x, z]
					result[key] = {"score": score, "cell": cell, "mesh": mesh_index, "origin": Vector2(x, z),
						"transform": Transform3D(Basis(Vector3(buffer[o], buffer[o + 4], buffer[o + 8]),
							Vector3(buffer[o + 1], buffer[o + 5], buffer[o + 9]), Vector3(buffer[o + 2], buffer[o + 6], buffer[o + 10])),
							Vector3(x, buffer[o + 7], z))}
	last_query.hiding = result.size()
	return result


static func _cell_xy(x: float, z: float) -> Vector2i:
	return Vector2i(clampi(floori((x + ForestCanopy.EXTENT) / ForestCanopy.CELL), 0, ForestCanopy.CELLS - 1),
		clampi(floori((z + ForestCanopy.EXTENT) / ForestCanopy.CELL), 0, ForestCanopy.CELLS - 1))


## [species, variant] for a canopy tree mesh ("tree:<asset>:v<n>"), [] for anything else.
func _shape(mesh_index: int) -> Array:
	if _shapes.has(mesh_index):
		return _shapes[mesh_index]
	var shape: Array = []
	var spec: Dictionary = canopy.meshes[mesh_index]
	if int(spec.kind) == ForestCanopy.KIND_TREE:
		var parts := String(spec.key).split(":")
		if parts.size() == 3:
			var species := Rules.SPECIES.find(parts[1])
			if species >= 0:
				shape = [species, int(parts[2].trim_prefix("v"))]
	_shapes[mesh_index] = shape
	return shape


func _begin(key: String, hit: Dictionary) -> void:
	var spec: Dictionary = canopy.meshes[hit.mesh]
	var lod := clampi(canopy.tree_lod_at(hit.cell), 0, 2)
	var mesh: Mesh = spec.lods[lod]
	var node := MeshInstance3D.new()
	node.name = "Faded_" + key.replace(":", "_").replace(".", "_")
	node.mesh = mesh
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var fresh := false
	for s in mesh.get_surface_count():
		var source := mesh.surface_get_material(s)
		var fade := _fade_material(source)
		fresh = fresh or not ForestKit.fog_receivers.has(fade)
		if fade is ShaderMaterial and not ForestKit.fog_receivers.has(fade):
			ForestKit.fog_receivers.append(fade)
		node.set_surface_override_material(s, fade)
	add_child(node)
	node.global_transform = hit.transform
	node.set_instance_shader_parameter("tree_opacity", 1.0)
	var shadow := MeshInstance3D.new()
	shadow.name = node.name + "_shadow"
	shadow.mesh = mesh
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	add_child(shadow)
	shadow.global_transform = hit.transform
	faded[key] = {"node": node, "shadow": shadow, "opacity": 1.0, "hold": HOLD_SECONDS, "cell": hit.cell,
		"mesh": hit.mesh, "origin": hit.origin}
	canopy.set_instance_hidden(hit.cell, hit.mesh, hit.origin, true)
	if fresh and world != null and world.has_method("_register_fog_receivers"):
		world.call("_register_fog_receivers")


func _release(key: String) -> void:
	var entry: Dictionary = faded[key]
	canopy.set_instance_hidden(entry.cell, entry.mesh, entry.origin, false)
	(entry.node as Node).queue_free()
	(entry.shadow as Node).queue_free()
	faded.erase(key)


## Drops every faded copy at once (canopy rebuilt, world torn down).
func clear() -> void:
	for key in faded.keys():
		var entry: Dictionary = faded[key]
		(entry.node as Node).queue_free()
		(entry.shadow as Node).queue_free()
	faded.clear()


func _refresh_canopy() -> void:
	if world != null and world.has_method("on_camera_changed"):
		world.call("on_camera_changed")


static func _fade_material(source: Material) -> Material:
	if not source is ShaderMaterial:
		return source
	var id := source.get_instance_id()
	if _fade_materials.has(id) and is_instance_valid(_fade_materials[id]):
		return _fade_materials[id]
	var fade: ShaderMaterial = source.duplicate()
	fade.shader = FADE_CUTOUT_SHADER if (source as ShaderMaterial).shader == ForestKit.CUTOUT_SHADER else FADE_SHADER
	fade.render_priority = 0
	_fade_materials[id] = fade
	return fade


static func clear_cache() -> void:
	_fade_materials.clear()


func _exit_tree() -> void:
	clear()
