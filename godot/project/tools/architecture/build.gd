extends SceneTree
## Builds native Godot level scenes for DRENOVAR architecture-v2.
## godot --headless --path project -s tools/architecture/build.gd -- [only=SUP-03-1,SUP-03-2]
## Output: res://assets/city/architecture-v2/levels/<TYPE>-<L>.tscn (+ .res meshes) and
## the "levelModels" table in res://assets/game.json.

const Kit = preload("res://tools/architecture/arch_kit.gd")
const Materials = preload("res://tools/architecture/materials.gd")
const Recipes = preload("res://tools/architecture/recipes.gd")
const OUT := "res://assets/city/architecture-v2/levels/"

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var only := []
	for a in OS.get_cmdline_user_args():
		if a.begins_with("only="):
			only = a.trim_prefix("only=").split(",")
	Materials.build()
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var table: Dictionary = {}
	var report := []
	for entry in Recipes.ENTRIES:
		var key := "%s-%d" % [entry.type, entry.level]
		var row := {"path": OUT + key + ".tscn", "scale": 1.0, "series": entry.series}
		if entry.get("carry", false):
			row["carried"] = true
		table.get_or_add(entry.type, {})[str(entry.level)] = row
		if not only.is_empty() and not key in only:
			continue
		# Seeded by type, so parts shared by neighbouring levels come out identical and
		# the upgrade animation can tell what stays from what is new.
		var kit = Kit.new(hash(entry.type))
		var spec: Dictionary = Callable(Recipes, entry.fn).call(kit, int(entry.level))
		if spec.has("worker"):
			row["worker"] = [spec.worker.x, spec.worker.y, spec.worker.z]
		var root := Node3D.new()
		root.name = key.replace("-", "_")
		root.set_meta("series", entry.series)
		root.set_meta("lanes", kit.lanes)
		if spec.has("worker"):
			root.set_meta("worker_offset", spec.worker)
		var tris := 0
		if spec.has("base"):
			tris += add_base(root, data, spec.base, int(entry.level), key)
		if spec.has("overlay"):
			# The original overlay GLB is referenced read-only; its mesh is placed exactly as
			# landscape.add_city_detail() does (identity transform, scenery material).
			var src: Node3D = load(spec.overlay).instantiate()
			for m: MeshInstance3D in src.find_children("*", "MeshInstance3D", true, false):
				var copy := MeshInstance3D.new()
				copy.name = "Overlay"
				copy.mesh = m.mesh if spec.get("overlay_masks", []).is_empty() else masked_mesh(m.mesh, m.transform, spec.overlay_masks)
				copy.transform = m.transform
				copy.material_override = load("res://assets/city/architecture-v2/materials/scenery.tres")
				root.add_child(copy)
				copy.owner = root
			src.free()
		var mesh: ArrayMesh = kit.bake()
		ResourceSaver.save(mesh, OUT + key + ".res", ResourceSaver.FLAG_COMPRESS)
		var arch := MeshInstance3D.new()
		arch.name = "Architecture"
		arch.mesh = load(OUT + key + ".res")
		root.add_child(arch)
		arch.owner = root
		tris += kit.triangle_count()
		var packed := PackedScene.new()
		packed.pack(root)
		var err := ResourceSaver.save(packed, OUT + key + ".tscn")
		report.append("%s %s tris=%d lanes=%d err=%d" % [key, entry.series, tris, kit.lanes.size(), err])
		root.free()
	link_upgrades(table)
	# levelModels table is written in a stable order so diffs stay small.
	data["levelModels"] = table
	var text := FileAccess.get_file_as_string("res://assets/game.json")
	var marker := "\"levelModels\""
	var encoded := JSON.stringify(table, "", true)
	if text.contains(marker):
		var start := text.find(marker)
		var depth := 0
		var i := text.find("{", start)
		var end := i
		while end < text.length():
			var ch := text[end]
			if ch == "{":
				depth += 1
			elif ch == "}":
				depth -= 1
				if depth == 0:
					break
			end += 1
		text = text.substr(0, i) + encoded + text.substr(end + 1)
	else:
		var close := text.rfind("}")
		text = text.substr(0, close).strip_edges(false, true) + ", " + marker + ": " + encoded + "}"
	var f := FileAccess.open("res://assets/game.json", FileAccess.WRITE)
	f.store_string(text)
	f.close()
	for line in report:
		print("BUILT ", line)
	quit(0)

func add_base(root: Node3D, data: Dictionary, base: Dictionary, level: int, key: String) -> int:
	var model: Dictionary = data.models[base.id]
	var s := float(model.scale) * (1.0 + 0.055 * (level - 1)) * float(base.get("scale", 1.0))
	var t := Transform3D(Basis(Vector3.UP, deg_to_rad(float(base.get("yaw", 0.0)))).scaled(Vector3.ONE * s), base.get("offset", Vector3.ZERO))
	var masks: Array = base.get("masks", [])
	var scene: PackedScene = load(model.path)
	if masks.is_empty():
		var inst := scene.instantiate()
		inst.name = "Base"
		inst.transform = t
		root.add_child(inst)
		inst.owner = root
		return 0
	# Copy the shared model and drop triangles inside the mask volumes (level space).
	# The original GLB stays untouched, so other levels and types are not affected.
	var src := scene.instantiate()
	var merged := ArrayMesh.new()
	var removed := 0
	for mi: MeshInstance3D in src.find_children("*", "MeshInstance3D", true, false):
		var local := t * _node_xf(mi, src)
		for si in mi.mesh.get_surface_count():
			var arrays := mi.mesh.surface_get_arrays(si)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array(range(verts.size()))
			var kept := PackedInt32Array()
			for i in range(0, idx.size(), 3):
				var cpos := (local * verts[idx[i]] + local * verts[idx[i + 1]] + local * verts[idx[i + 2]]) / 3.0
				var drop := false
				for m in masks:
					if (m as AABB).has_point(cpos):
						drop = true
						break
				if drop:
					removed += 1
				else:
					kept.append(idx[i]); kept.append(idx[i + 1]); kept.append(idx[i + 2])
			if kept.is_empty():
				continue
			# bake node transform into vertices so the copy lives in level space
			var nv := PackedVector3Array()
			nv.resize(verts.size())
			for v in verts.size():
				nv[v] = local * verts[v]
			arrays[Mesh.ARRAY_VERTEX] = nv
			if arrays[Mesh.ARRAY_NORMAL] != null:
				var nn: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
				var nb := local.basis.inverse().transposed()
				for v in nn.size():
					nn[v] = (nb * nn[v]).normalized()
				arrays[Mesh.ARRAY_NORMAL] = nn
			arrays[Mesh.ARRAY_TANGENT] = null
			arrays[Mesh.ARRAY_INDEX] = kept
			merged.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			merged.surface_set_material(merged.get_surface_count() - 1, mi.get_active_material(si))
	src.free()
	merged.regen_normal_maps()
	ResourceSaver.save(merged, OUT + key + "-base.res", ResourceSaver.FLAG_COMPRESS)
	var inst := MeshInstance3D.new()
	inst.name = "Base"
	inst.mesh = load(OUT + key + "-base.res")
	root.add_child(inst)
	inst.owner = root
	print("MASKED ", key, " removed triangles: ", removed)
	return 0

func masked_mesh(mesh: Mesh, xf: Transform3D, masks: Array) -> ArrayMesh:
	var out := ArrayMesh.new()
	for si in mesh.get_surface_count():
		var arrays := mesh.surface_get_arrays(si)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array(range(verts.size()))
		var kept := PackedInt32Array()
		for i in range(0, idx.size(), 3):
			var c := (xf * verts[idx[i]] + xf * verts[idx[i + 1]] + xf * verts[idx[i + 2]]) / 3.0
			if not masks.any(func(m: AABB): return m.has_point(c)):
				kept.append(idx[i]); kept.append(idx[i + 1]); kept.append(idx[i + 2])
		if kept.is_empty():
			continue
		arrays[Mesh.ARRAY_INDEX] = kept
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return out

func _node_xf(n: Node3D, top: Node) -> Transform3D:
	var t := n.transform
	var p := n.get_parent()
	while p != null and p != top and p is Node3D:
		t = (p as Node3D).transform * t
		p = p.get_parent()
	return t

# ---------------------------------------------------------------- upgrade order
static func tri_key(mat: String, a: Vector3, b: Vector3, c: Vector3) -> String:
	var m := (a + b + c) / 3.0
	var n := (b - a).cross(c - a).normalized()
	return "%s|%d|%d|%d|%d|%d|%d" % [mat, roundi(m.x * 33.0), roundi(m.y * 33.0), roundi(m.z * 33.0),
		roundi(n.x * 8.0), roundi(n.y * 8.0), roundi(n.z * 8.0)]

static func mesh_keys(mesh: ArrayMesh) -> Dictionary:
	var keys := {}
	for si in mesh.get_surface_count():
		var arr := mesh.surface_get_arrays(si)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var mat := mesh.surface_get_name(si)
		for t in range(0, v.size(), 3):
			keys[tri_key(mat, v[t], v[t + 1], v[t + 2])] = true
	return keys

func link_upgrades(table: Dictionary) -> void:
	## For each level L with a kit-built level L-1: parts already standing in L-1 get
	## UV2.x = 0 (not rebuilt); new parts keep their build time. In L-1, parts missing
	## from L get UV2.y = an early dismantle time (roof first), the rest UV2.y = 2.
	var linked := 0
	for type in table:
		for level in range(2, 6):
			var prev := OUT + "%s-%d.res" % [type, level - 1]
			var cur := OUT + "%s-%d.res" % [type, level]
			if not (table[type].has(str(level)) and table[type].has(str(level - 1))):
				continue
			if not (FileAccess.file_exists(prev) and FileAccess.file_exists(cur)):
				continue
			var pm: ArrayMesh = load(prev)
			var cm: ArrayMesh = load(cur)
			var pk := mesh_keys(pm)
			var ck := mesh_keys(cm)
			var top := 0.5
			for si in pm.get_surface_count():
				for v: Vector3 in pm.surface_get_arrays(si)[Mesh.ARRAY_VERTEX]:
					top = maxf(top, v.y)
			cm = relink(cm, func(key: String, uv: Vector2, a: Vector3, b: Vector3, c: Vector3) -> Vector2:
				return Vector2(0.0 if pk.has(key) else uv.x, uv.y))
			pm = relink(pm, func(key: String, uv: Vector2, a: Vector3, b: Vector3, c: Vector3) -> Vector2:
				var h := clampf(((a.y + b.y + c.y) / 3.0) / top, 0.0, 1.0)
				# replaced in place: a part is taken down just before the new parts at
				# its height go up (walls course by course, the old roof with the new frame)
				return Vector2(uv.x, 2.0 if ck.has(key) else 0.12 + 0.83 * (0.1 + 0.46 * pow(h, 0.85)) - 0.02))
			ResourceSaver.save(cm, cur, ResourceSaver.FLAG_COMPRESS)
			ResourceSaver.save(pm, prev, ResourceSaver.FLAG_COMPRESS)
			linked += 1
	print("UPGRADE_LINKS ", linked)

static func relink(mesh: ArrayMesh, fn: Callable) -> ArrayMesh:
	var out := ArrayMesh.new()
	for si in mesh.get_surface_count():
		var arr := mesh.surface_get_arrays(si)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var uv: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV2]
		var mat := mesh.surface_get_name(si)
		for t in range(0, v.size(), 3):
			var r: Vector2 = fn.call(tri_key(mat, v[t], v[t + 1], v[t + 2]), uv[t], v[t], v[t + 1], v[t + 2])
			uv[t] = r; uv[t + 1] = r; uv[t + 2] = r
		arr[Mesh.ARRAY_TEX_UV2] = uv
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		out.surface_set_name(si, mat)
		out.surface_set_material(si, mesh.surface_get_material(si))
	return out
