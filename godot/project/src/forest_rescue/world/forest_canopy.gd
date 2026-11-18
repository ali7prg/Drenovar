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


func clear_instances() -> void:
	cell_buffers.clear()
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


func add_instance(mesh_index: int, transform: Transform3D) -> void:
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
	buffer.append_array(PackedFloat32Array([b.x.x, b.y.x, b.z.x, o.x, b.x.y, b.y.y, b.z.y, o.y, b.x.z, b.y.z, b.z.z, o.z]))
	buffers[mesh_index] = buffer
	var spec: Dictionary = meshes[mesh_index]
	var s := b.x.length()
	var r: float = spec.radius * s + 1.0
	cell_low[cell] = cell_low[cell].min(o - Vector3(r, 1.0, r))
	cell_high[cell] = cell_high[cell].max(o + Vector3(r, spec.height * s + 1.0, r))


func instance_count() -> int:
	var total := 0
	for cell in cell_buffers:
		for buffer: PackedFloat32Array in cell_buffers[cell].values():
			total += buffer.size() / 12
	return total


## Chooses LOD per cell (-1 = hidden) for a mesh kind.
func lod_for(kind: int, cls: String, zoom: float, distance: float) -> int:
	var z := zoom * lod_bias
	match cls:
		"full":
			if kind == KIND_TREE or kind == KIND_STUMP:
				if z <= 46.0 and distance <= 36.0:
					return 0
				return 1 if z <= 96.0 else 2
			if kind == KIND_ROCK:
				return 0 if z <= 46.0 else (1 if z <= 100.0 else -1)
			return (0 if z <= 40.0 else 1) if z <= 78.0 else -1
		"proxy":
			if kind == KIND_TREE or kind == KIND_STUMP:
				return 1 if z <= 52.0 else 2
			if kind == KIND_ROCK:
				return 1 if z <= 70.0 else -1
			return -1
		"fogOnly":
			return 2 if kind == KIND_TREE else -1
	return -1


func chunk_for_cell(cell: int) -> String:
	var c := cell_center(cell)
	var id := ForestMasks.chunk_id_at(c.x, c.y)
	return id if not id.is_empty() else "edge"


func update_view(camera: Camera3D, target: Vector3, zoom: float) -> void:
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
		var buffers: Dictionary = cell_buffers[cell]
		for mesh_index in buffers:
			var spec: Dictionary = meshes[mesh_index]
			var lod := lod_for(spec.kind, cls, zoom, maxf(distance, 0.0))
			if lod < 0:
				continue
			var key := Vector2i(mesh_index, lod)
			if not wanted.has(key):
				wanted[key] = PackedInt32Array()
			wanted[key].append(cell)
			var count: int = buffers[mesh_index].size() / 12
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
		transforms.append_array(cell_buffers[cell][key.x])
		low = low.min(cell_low[cell])
		high = high.max(cell_high[cell])
	var count := transforms.size() / 12
	var multi := node.multimesh
	var cap: int = capacity.get(key, 0)
	if count > cap:
		cap = maxi(16, cap)
		while cap < count:
			cap *= 2
		capacity[key] = cap
		multi.instance_count = cap
	transforms.resize(cap * 12)
	multi.buffer = transforms
	multi.visible_instance_count = count
	multi.custom_aabb = AABB(low, high - low)
	node.visible = true
	uploads += 1
	uploaded_bytes += count * 48


func _make_node(key: Vector2i) -> MultiMeshInstance3D:
	var spec: Dictionary = meshes[key.x]
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.mesh = spec.lods[key.y]
	multi.instance_count = 0
	var node := MultiMeshInstance3D.new()
	node.name = "%s_LOD%d" % [String(spec.key).replace(":", "_"), key.y]
	node.multimesh = multi
	var casts: bool = shadow_trees and (spec.kind == KIND_TREE or spec.kind == KIND_STUMP)
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
