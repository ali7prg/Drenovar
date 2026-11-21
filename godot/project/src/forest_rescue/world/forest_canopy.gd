extends Node3D
## Chunked, LOD'ed MultiMesh forest.
##
## Streaming unit: the atlas chunk (56 m, `lf_chunk_X_Z`), subdivided into 14 m culling cells.
## Every instance lives in exactly one cell; per (asset-variant, cell) we keep a prebuilt
## transform buffer. On camera changes each cell gets a class from select_chunks()
## (full / proxy / fogOnly / unloaded) and a LOD from zoom + distance to the camera focus,
## then per (asset-variant, LOD) one MultiMesh is refilled from the selected, frustum-visible
## cells only when that selection changed (no per-frame uploads, few draw calls).

const ForestMasks = preload("res://src/forest_rescue/world/forest_masks.gd")

const CELL := 14.0
const EXTENT := 140.0
const CELLS := 20                     # (2 * EXTENT) / CELL
const KIND_TREE := 0
const KIND_UNDER := 1
const KIND_STUMP := 2
const KIND_ROCK := 3                  # large understory that stays in proxy chunks

var meshes: Array = []                # [{key, lods:[Mesh×3], tris:[int×3], kind, radius, height}]
var mesh_index_by_key: Dictionary = {}
var cell_buffers: Dictionary = {}     # cell -> {mesh_index -> PackedFloat32Array}
var cell_low: Dictionary = {}         # cell -> Vector3
var cell_high: Dictionary = {}
var nodes: Dictionary = {}            # Vector2i(mesh, lod) -> MultiMeshInstance3D
var selection: Dictionary = {}        # Vector2i(mesh, lod) -> PackedInt32Array (cells)
var capacity: Dictionary = {}
var chunk_class: Dictionary = {}      # chunk id -> "full|proxy|fogOnly|unloaded"
var last_stats: Dictionary = {}
var uploads := 0
var uploaded_bytes := 0
var shadow_trees := true
var lod_bias := 1.0
var impostors: Node = null              # ForestImpostors (null/unavailable → 3D LOD2 meshes)
var cell_impostor: Dictionary = {}      # cell -> PackedFloat32Array (STRIDE floats per tree)
const IMPOSTOR_KEY := Vector2i(-1, 2)
## Fog cull (world layer): instances standing in unexplored ground deeper than the fog's blend
## band are removed from the GPU buffers entirely (under fog nothing renders but the fog).
## Recomputed only when the fog projection changes (set_cull), never per frame.
var cull_fn: Callable                   # (x, z) -> bool keep; invalid = keep everything
var shown_buffers: Dictionary = {}      # cell -> {mesh_index -> PackedFloat32Array} (kept subset)
var shown_impostor: Dictionary = {}     # cell -> PackedFloat32Array
var culled := 0


func clear_instances() -> void:
	cell_buffers.clear()
	cell_impostor.clear()
	shown_buffers.clear()
	shown_impostor.clear()
	cell_low.clear()
	cell_high.clear()
	for key in selection.keys():
		selection[key] = PackedInt32Array([-1])


func register_mesh(key: String, lods: Array, tris: Array, kind: int, radius: float, height: float) -> int:
	if mesh_index_by_key.has(key):
		return mesh_index_by_key[key]
	var index := meshes.size()
	meshes.append({"key": key, "lods": lods, "tris": tris, "kind": kind, "radius": radius, "height": height})
	mesh_index_by_key[key] = index
	return index


static func cell_of(x: float, z: float) -> int:
	var i := clampi(floori((x + EXTENT) / CELL), 0, CELLS - 1)
	var j := clampi(floori((z + EXTENT) / CELL), 0, CELLS - 1)
	return j * CELLS + i


static func cell_center(cell: int) -> Vector2:
	return Vector2(-EXTENT + (cell % CELLS + 0.5) * CELL, -EXTENT + (cell / CELLS + 0.5) * CELL)


const STRIDE := 16                    # 12 transform floats + 4 INSTANCE_CUSTOM floats


func add_instance(mesh_index: int, transform: Transform3D, custom := Color(0, 1, 1, 0)) -> void:
	var cell := cell_of(transform.origin.x, transform.origin.z)
	if not cell_buffers.has(cell):
		cell_buffers[cell] = {}
		cell_low[cell] = Vector3(INF, INF, INF)
		cell_high[cell] = Vector3(-INF, -INF, -INF)
	var buffers: Dictionary = cell_buffers[cell]
	if not buffers.has(mesh_index):
		buffers[mesh_index] = PackedFloat32Array()
	var b := transform.basis
	var o := transform.origin
	var buffer: PackedFloat32Array = buffers[mesh_index]
	buffer.append_array(PackedFloat32Array([b.x.x, b.y.x, b.z.x, o.x, b.x.y, b.y.y, b.z.y, o.y, b.x.z, b.y.z, b.z.z, o.z,
		custom.r, custom.g, custom.b, custom.a]))
	buffers[mesh_index] = buffer
	var spec: Dictionary = meshes[mesh_index]
	var s := b.x.length()
	var r: float = spec.radius * s + 1.0
	cell_low[cell] = cell_low[cell].min(o - Vector3(r, 1.0, r))
	cell_high[cell] = cell_high[cell].max(o + Vector3(r, spec.height * s + 1.0, r))


func add_impostor(transform: Transform3D, custom: Color) -> void:
	var cell := cell_of(transform.origin.x, transform.origin.z)
	var b := transform.basis
	var o := transform.origin
	if not cell_impostor.has(cell):
		cell_impostor[cell] = PackedFloat32Array()
	var buffer: PackedFloat32Array = cell_impostor[cell]
	buffer.append_array(PackedFloat32Array([b.x.x, b.y.x, b.z.x, o.x, b.x.y, b.y.y, b.z.y, o.y, b.x.z, b.y.z, b.z.z, o.z,
		custom.r, custom.g, custom.b, custom.a]))
	cell_impostor[cell] = buffer


## Re-filters every cell with keep(x, z) (cell-level shortcut via cell_state(cell) when given:
## 1 = whole cell kept, -1 = whole cell culled, 0 = test each instance). Forces re-upload.
var _cull_cache := {}      # cell -> [fog key, kept buffers, kept impostors, culled count, source buffers]


func set_cull(keep: Callable, cell_state: Callable = Callable(), cell_key: Callable = Callable()) -> void:
	cull_fn = keep
	shown_buffers.clear()
	shown_impostor.clear()
	culled = 0
	for cell in cell_buffers:
		var state := 1 if not keep.is_valid() else (int(cell_state.call(cell)) if cell_state.is_valid() else 0)
		var buffers: Dictionary = cell_buffers[cell]
		# mixed cell whose fog samples did not change since the last cull: reuse its filtered buffers
		var key: int = int(cell_key.call(cell)) if state == 0 and cell_key.is_valid() else 0
		if state == 0 and cell_key.is_valid() and _cull_cache.has(cell) and _cull_cache[cell][0] == key and is_same(_cull_cache[cell][4], buffers):
			var cached: Array = _cull_cache[cell]
			if not (cached[1] as Dictionary).is_empty():
				shown_buffers[cell] = cached[1]
			if not (cached[2] as PackedFloat32Array).is_empty():
				shown_impostor[cell] = cached[2]
			culled += int(cached[3])
			continue
		if state == 1:
			shown_buffers[cell] = buffers
			if cell_impostor.has(cell):
				shown_impostor[cell] = cell_impostor[cell]
			continue
		if state == -1:
			for buffer: PackedFloat32Array in buffers.values():
				culled += buffer.size() / STRIDE
			continue
		var culled_before := culled
		var kept := {}
		for mesh_index in buffers:
			var filtered := _filter(buffers[mesh_index], keep)
			if not filtered.is_empty():
				kept[mesh_index] = filtered
		if not kept.is_empty():
			shown_buffers[cell] = kept
		var filtered_i := PackedFloat32Array()
		if cell_impostor.has(cell):
			filtered_i = _filter(cell_impostor[cell], keep, true)
			if not filtered_i.is_empty():
				shown_impostor[cell] = filtered_i
		if cell_key.is_valid():
			_cull_cache[cell] = [key, kept, filtered_i, culled - culled_before, buffers]
	for key in selection.keys():
		selection[key] = PackedInt32Array([-1])


func _filter(buffer: PackedFloat32Array, keep: Callable, impostor := false) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	var count := buffer.size() / STRIDE
	for i in count:
		var o := i * STRIDE
		# impostor quads stand at the crown centre; their custom r/g carry the tree base x/z
		var x := buffer[o + 12] if impostor else buffer[o + 3]
		var z := buffer[o + 13] if impostor else buffer[o + 11]
		if keep.call(x, z):
			out.append_array(buffer.slice(o, o + STRIDE))
		elif not impostor:
			culled += 1
	return out


func _buffers(cell: int) -> Dictionary:
	return shown_buffers.get(cell, {}) if cull_fn.is_valid() else cell_buffers[cell]


## Instances of a cell that survive the fog cull ({} for an empty cell).
func visible_buffers(cell: int) -> Dictionary:
	if not cell_buffers.has(cell):
		return {}
	return _buffers(cell)


## LOD the trees of `cell` are drawn with right now (2 = impostor / far mesh).
func tree_lod_at(cell: int) -> int:
	var cls: String = chunk_class.get(chunk_for_cell(cell), "fogOnly")
	var distance := Vector2(_last_target.x, _last_target.z).distance_to(cell_center(cell)) - CELL * 0.7
	return maxi(0, lod_for(KIND_TREE, cls, _last_zoom, maxf(distance, 0.0)))


## Hides (or shows again) one tree — its kit instance and its impostor — found by its base
## position: the occluder-fade copy draws it meanwhile (forest_occluders.gd). Flags live in
## INSTANCE_CUSTOM (kit: r = 1 hidden; impostor: b = 0 hidden); the batches holding the cell are
## re-uploaded on the next update_view().
func set_instance_hidden(cell: int, mesh_index: int, origin: Vector2, hidden: bool) -> void:
	var dicts: Array = [cell_buffers.get(cell, {})]
	if shown_buffers.has(cell) and not is_same(shown_buffers[cell], cell_buffers.get(cell)):
		dicts.append(shown_buffers[cell])
	for buffers: Dictionary in dicts:
		if buffers.has(mesh_index):
			buffers[mesh_index] = _flag(buffers[mesh_index], origin, 3, 11, 12, 1.0 if hidden else 0.0)
	if cell_impostor.has(cell):
		cell_impostor[cell] = _flag(cell_impostor[cell], origin, 12, 13, 14, 0.0 if hidden else 1.0)
	if shown_impostor.has(cell):
		shown_impostor[cell] = _flag(shown_impostor[cell], origin, 12, 13, 14, 0.0 if hidden else 1.0)
	for key in selection.keys():
		if (selection[key] as PackedInt32Array).has(cell):
			selection[key] = PackedInt32Array([-1])


static func _flag(buffer: PackedFloat32Array, origin: Vector2, x_at: int, z_at: int, flag_at: int, value: float) -> PackedFloat32Array:
	for n in buffer.size() / STRIDE:
		var o := n * STRIDE
		if absf(buffer[o + x_at] - origin.x) < 0.006 and absf(buffer[o + z_at] - origin.y) < 0.006:
			buffer[o + flag_at] = value
	return buffer


func _impostor_buffer(cell: int) -> PackedFloat32Array:
	return shown_impostor.get(cell, PackedFloat32Array()) if cull_fn.is_valid() else cell_impostor.get(cell, PackedFloat32Array())


func instance_count() -> int:
	var total := 0
	for cell in cell_buffers:
		for buffer: PackedFloat32Array in cell_buffers[cell].values():
			total += buffer.size() / STRIDE
	return total


## Chooses LOD per cell (-1 = hidden) for a mesh kind. Trees: LOD 2 means "impostor when baked"
## (identical silhouette from the fixed city camera, 2 triangles), 3D LOD1/LOD0 only near the
## camera focus at close zoom. Budget target: ≤ 110k visible environment triangles at zoom 40/68/120.
func lod_for(kind: int, cls: String, zoom: float, distance: float) -> int:
	var z := zoom * lod_bias
	match cls:
		"full":
			# distance = focus to the 14 m cell centre minus 9.8 m (≈ nearest cell edge).
			if kind == KIND_TREE or kind == KIND_STUMP:
				if z <= 30.0 and distance <= 2.0:
					return 0
				return 1 if z <= 48.0 and distance <= 6.0 else 2
			if kind == KIND_ROCK:
				if z <= 34.0 and distance <= 16.0:
					return 1
				return 2 if z <= 100.0 else -1
			if z > 78.0 or (z > 50.0 and distance > 36.0) or distance > 52.0:
				return -1
			return 0 if z <= 30.0 and distance <= 12.0 else (1 if z <= 46.0 and distance <= 24.0 else 2)
		"proxy":
			if kind == KIND_TREE or kind == KIND_STUMP:
				return 2
			if kind == KIND_ROCK:
				return 2 if z <= 70.0 else -1
			return -1
		"fogOnly", "far":
			return 2 if kind == KIND_TREE else -1
	return -1


func chunk_for_cell(cell: int) -> String:
	var c := cell_center(cell)
	var id := ForestMasks.chunk_id_at(c.x, c.y)
	return id if not id.is_empty() else "edge"


var _last_target := Vector3.ZERO
var _last_zoom := 68.0


func update_view(camera: Camera3D, target: Vector3, zoom: float) -> void:
	_last_target = target
	_last_zoom = zoom
	var planes := camera.get_frustum()
	var wanted: Dictionary = {}
	var tris := 0
	var instances := [0, 0, 0]
	for cell in cell_buffers:
		var chunk := chunk_for_cell(cell)
		var cls: String = chunk_class.get(chunk, "fogOnly")
		if cls == "unloaded":
			continue
		var low: Vector3 = cell_low[cell]
		var high: Vector3 = cell_high[cell]
		if not _box_visible(planes, low, high):
			continue
		var center := cell_center(cell)
		var distance := Vector2(target.x, target.z).distance_to(center) - CELL * 0.7
		var buffers: Dictionary = _buffers(cell)
		var tree_lod := lod_for(KIND_TREE, cls, zoom, maxf(distance, 0.0))
		var use_impostor: bool = tree_lod == 2 and impostors != null and impostors.available and cell_impostor.has(cell)
		if use_impostor and not _impostor_buffer(cell).is_empty():
			if not wanted.has(IMPOSTOR_KEY):
				wanted[IMPOSTOR_KEY] = PackedInt32Array()
			wanted[IMPOSTOR_KEY].append(cell)
			var count_i: int = _impostor_buffer(cell).size() / STRIDE
			instances[2] += count_i
			tris += count_i * 2
		for mesh_index in buffers:
			var spec: Dictionary = meshes[mesh_index]
			var lod := lod_for(spec.kind, cls, zoom, maxf(distance, 0.0))
			if lod < 0 or (use_impostor and spec.kind == KIND_TREE):
				continue
			var key := Vector2i(mesh_index, lod)
			if not wanted.has(key):
				wanted[key] = PackedInt32Array()
			wanted[key].append(cell)
			var count: int = buffers[mesh_index].size() / STRIDE
			instances[lod] += count
			tris += count * int(spec.tris[lod])
	for key in nodes.keys():
		if not wanted.has(key):
			_apply(key, PackedInt32Array())
	for key in wanted:
		var cells: PackedInt32Array = wanted[key]
		cells.sort()
		_apply(key, cells)
	last_stats = {"instances": instances[0] + instances[1] + instances[2], "lod0": instances[0], "lod1": instances[1],
		"lod2": instances[2], "tris_est": tris, "batches": _visible_batches()}


func _visible_batches() -> int:
	var count := 0
	for key in nodes:
		if nodes[key].visible:
			count += 1
	return count


func _apply(key: Vector2i, cells: PackedInt32Array) -> void:
	if selection.get(key, PackedInt32Array()) == cells:
		return
	selection[key] = cells
	var node: MultiMeshInstance3D = nodes.get(key)
	if cells.is_empty():
		if node != null:
			node.visible = false
			node.multimesh.visible_instance_count = 0
		return
	if node == null:
		node = _make_node(key)
	var transforms := PackedFloat32Array()
	var low := Vector3(INF, INF, INF)
	var high := Vector3(-INF, -INF, -INF)
	for cell in cells:
		transforms.append_array(_impostor_buffer(cell) if key == IMPOSTOR_KEY else _buffers(cell).get(key.x, PackedFloat32Array()))
		low = low.min(cell_low[cell])
		high = high.max(cell_high[cell])
	var count := transforms.size() / STRIDE
	var multi := node.multimesh
	var cap: int = capacity.get(key, 0)
	if count > cap:
		cap = maxi(16, cap)
		while cap < count:
			cap *= 2
		capacity[key] = cap
		multi.instance_count = cap
	transforms.resize(cap * STRIDE)
	multi.buffer = transforms
	multi.visible_instance_count = count
	multi.custom_aabb = AABB(low, high - low)
	node.visible = true
	uploads += 1
	uploaded_bytes += count * 48


func _make_node(key: Vector2i) -> MultiMeshInstance3D:
	var impostor := key == IMPOSTOR_KEY
	var spec: Dictionary = {"key": "impostors", "kind": -1} if impostor else meshes[key.x]
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_custom_data = true
	multi.mesh = impostors.quad if impostor else spec.lods[key.y]
	multi.instance_count = 0
	var node := MultiMeshInstance3D.new()
	node.name = "%s_LOD%d" % [String(spec.key).replace(":", "_"), key.y]
	node.multimesh = multi
	var casts: bool = shadow_trees and (impostor or spec.kind == KIND_TREE or spec.kind == KIND_STUMP or spec.kind == KIND_ROCK)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if casts else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	nodes[key] = node
	capacity[key] = 0
	return node


func _box_visible(planes: Array[Plane], low: Vector3, high: Vector3) -> bool:
	var extent := high - low
	for plane in planes:
		var n := plane.normal
		var nearest := low + Vector3(extent.x if n.x < 0 else 0.0, extent.y if n.y < 0 else 0.0, extent.z if n.z < 0 else 0.0)
		if n.dot(nearest) > plane.d + 0.0001:
			return false
	return true
