extends Node3D
## Atlas v2 still water and the waterfall (art/01 signature features; client visuals only, the
## atlas wet bounds stay the movement truth for the server):
##   * the reedy lake: the river widening south of the bridge (atlas river.features.lake), at
##     river level, gentle marshy banks, seamless with the river channel (same depth field);
##   * the waterfall: a limestone outcrop (kit moss rock v1, stacked) on the east plateau below the
##     arena, next to the waterfall junction (lf_junction_waterfall), whose face looks at the city
##     camera; the fall drops ~5 m into a perched lily pond. (The atlas pond mark (15,-70) lies in
##     the river gorge under the arena floor patch, where a fall is edge-on or hidden for the fixed
##     camera; the visual pond sits on the plateau rim 8 m east of it, inside the junction's reveal.)
##   * marsh pools with lily pads among the south pines below glade 07 (art/01 S-G).
## The terrain carves every body (ForestTerrain.water_bodies, see bodies()); the layout builder
## keeps trunks out and rings the shores with reeds.

const ForestTerrain = preload("res://src/forest_rescue/world/forest_terrain.gd")
const WATER_SHADER = preload("res://src/forest_rescue/world/forest_water.gdshader")
const FALLS_SHADER = preload("res://src/forest_rescue/world/forest_waterfall.gdshader")

const POND_CENTER := Vector2(22.6, -64.7)
const POND_RADIUS := 2.5
## Outcrop rocks [x, z, yaw°, scale]: kit lf_env_moss_rock v1 (limestone, 9.3 × 6.5 × 5.8 m).
const OUTCROP := [
	[19.5, -67.9, 228.0, Vector3(0.5, 0.95, 0.46)],
	[17.6, -65.4, 132.0, Vector3(0.34, 0.6, 0.33)],
	[21.9, -69.6, 32.0, Vector3(0.3, 0.52, 0.3)],
	[24.6, -62.1, 300.0, Vector3(0.16, 0.2, 0.16)],
]
const ROCK_HEIGHT := 5.76               # moss rock v1 LOD0 top (model space)
## The fall: lip on the outcrop's south-east face, facing the camera (+X +Z).
const FALLS_LIP := Vector2(20.55, -66.75)
const FALLS_FACING := Vector2(0.7071, 0.7071)
const FALLS_WIDTH := 2.3
const MARSH_POOLS := [[Vector2(68.0, 104.0), 3.0], [Vector2(73.5, 102.0), 2.0], [Vector2(64.5, 99.0), 1.8]]

var atlas: RefCounted
var items: Array = []        # [{node: MeshInstance3D, center: Vector2, radius}]
var falls_top := 0.0


## Water bodies for the terrain carve, the layout builder and the meshes.
## {id, kind, center: Vector2, radius, level, depth, bank (rise per m beyond the shore), noise,
##  seed, perched (dam the rim where the ground lies lower), lily, murk, river}
static func bodies(forest_atlas: RefCounted) -> Array:
	var out: Array = []
	for feature in forest_atlas.water_features:
		if feature.id == "lake":
			out.append({"id": "lake", "kind": "lake", "center": feature.center, "radius": feature.radius,
				"level": forest_atlas.WATER_LEVEL, "depth": 1.1, "bank": 0.42, "noise": 0.09, "seed": 1.7,
				"perched": false, "lily": 0.0, "murk": 0.22, "river": 1.0})
	out.append({"id": "pond", "kind": "pond", "center": POND_CENTER, "radius": POND_RADIUS,
		"level": ForestTerrain.base_height(POND_CENTER.x, POND_CENTER.y) - 0.42, "depth": 0.7, "bank": 1.1,
		"noise": 0.12, "seed": 4.1, "perched": true, "lily": 0.3, "murk": 0.12, "river": 0.0})
	for i in MARSH_POOLS.size():
		var c: Vector2 = MARSH_POOLS[i][0]
		out.append({"id": "marsh_%d" % i, "kind": "marsh", "center": c, "radius": float(MARSH_POOLS[i][1]),
			"level": ForestTerrain.base_height(c.x, c.y) - 0.24, "depth": 0.4, "bank": 0.5, "noise": 0.16,
			"seed": 2.3 + i, "perched": true, "lily": 0.2, "murk": 0.7, "river": 0.0})
	return out


static func shore_radius(body: Dictionary, angle: float) -> float:
	var s: float = body.seed
	return float(body.radius) * (1.0 + float(body.noise) * (0.6 * sin(3.0 * angle + s) + 0.4 * sin(5.0 * angle + 2.1 * s)))


## Signed distance (m) to a body's shoreline: < 0 in the water.
static func shore_distance(body: Dictionary, x: float, z: float) -> float:
	var d := Vector2(x, z) - Vector2(body.center)
	return d.length() - shore_radius(body, atan2(d.y, d.x))


func build(forest_atlas: RefCounted, height_fn: Callable, noise: Texture2D) -> void:
	atlas = forest_atlas
	for child in get_children():
		child.free()
	items.clear()
	for body in bodies(atlas):
		_build_body(body, noise)
	_build_falls(height_fn, noise)


func _build_body(body: Dictionary, noise: Texture2D) -> void:
	var rings := [0.0, 0.3, 0.55, 0.75, 0.88, 0.96, 1.0, 1.05]
	var steps := 56 if body.kind == "lake" else 28
	var vertices := PackedVector3Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	var y: float = float(body.level) - (0.012 if body.kind == "lake" else 0.0)
	var c: Vector2 = body.center
	vertices.append(Vector3(c.x, y, c.y))
	colors.append(Color(1, 1, 1, 1))
	for ring in range(1, rings.size()):
		for k in steps:
			var angle := TAU * k / steps
			var r := shore_radius(body, angle) * float(rings[ring])
			vertices.append(Vector3(c.x + cos(angle) * r, y, c.y + sin(angle) * r))
			var f: float = rings[ring]
			colors.append(Color(1, 1, 1, pow(clampf((1.0 - f) / 0.55, 0.0, 1.0), 0.8)))
	for k in steps:
		indices.append_array(PackedInt32Array([0, 1 + (k + 1) % steps, 1 + k]))
	for ring in range(1, rings.size() - 1):
		var a0 := 1 + (ring - 1) * steps
		var b0 := 1 + ring * steps
		for k in steps:
			var k1 := (k + 1) % steps
			indices.append_array(PackedInt32Array([a0 + k, a0 + k1, b0 + k, a0 + k1, b0 + k1, b0 + k]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	var normals := PackedVector3Array()
	normals.resize(vertices.size())
	normals.fill(Vector3.UP)
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var material := ShaderMaterial.new()
	material.shader = WATER_SHADER
	material.render_priority = -3
	material.set_shader_parameter("noise_tex", noise)
	material.set_shader_parameter("murk", float(body.murk))
	material.set_shader_parameter("lily_density", float(body.lily))
	material.set_shader_parameter("river_blend", float(body.river))
	if body.kind == "pond":
		var foot := FALLS_LIP + FALLS_FACING * 0.75
		material.set_shader_parameter("falls_point", Vector4(foot.x, foot.y, 1.25, 1.0))
	var node := MeshInstance3D.new()
	node.name = "Water_" + String(body.id)
	node.mesh = mesh
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	items.append({"node": node, "center": c, "radius": float(body.radius) * 1.2})


## Curtain from the outcrop lip (top of the main rock) down to the pond, bulging slightly out.
func _build_falls(height_fn: Callable, noise: Texture2D) -> void:
	var main: Array = OUTCROP[0]
	var base_y: float = height_fn.call(float(main[0]), float(main[1])) - 0.2
	falls_top = base_y + ROCK_HEIGHT * (main[3] as Vector3).y * 0.9
	var pond_level: float = ForestTerrain.base_height(POND_CENTER.x, POND_CENTER.y) - 0.42
	var bottom := pond_level + 0.02
	var across := Vector2(-FALLS_FACING.y, FALLS_FACING.x)
	var rows := 10
	var cols := 6
	var vertices := PackedVector3Array()
	var uvs := PackedVector2Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	for j in rows + 1:
		var v := float(j) / rows
		var out := 0.12 + 0.75 * pow(v, 1.5)
		var y := lerpf(falls_top, bottom, v) + 0.25 * sin(v * PI) * 0.3
		var width := FALLS_WIDTH * (0.82 + 0.3 * v)
		for i in cols + 1:
			var u := float(i) / cols
			var p := FALLS_LIP + FALLS_FACING * out + across * (u - 0.5) * width
			vertices.append(Vector3(p.x, y, p.y))
			uvs.append(Vector2(u, v))
			colors.append(Color(1, 1, 1, 1.0 - pow(absf(u * 2.0 - 1.0), 3.0)))
	for j in rows:
		for i in cols:
			var a := j * (cols + 1) + i
			var b := a + cols + 1
			indices.append_array(PackedInt32Array([a, a + 1, b, a + 1, b + 1, b]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	var normals := PackedVector3Array()
	normals.resize(vertices.size())
	normals.fill(Vector3(FALLS_FACING.x, 0.0, FALLS_FACING.y))
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var material := ShaderMaterial.new()
	material.shader = FALLS_SHADER
	material.render_priority = 2
	material.set_shader_parameter("noise_tex", noise)
	material.set_shader_parameter("width_m", FALLS_WIDTH)
	material.set_shader_parameter("height_m", maxf(1.0, falls_top - bottom))
	var node := MeshInstance3D.new()
	node.name = "Waterfall"
	node.mesh = mesh
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	items.append({"node": node, "center": FALLS_LIP, "radius": 3.0})


## Outcrop rock instances for the canopy: [[x, z, yaw (rad), scale Vector3]].
static func outcrop_rocks() -> Array:
	var out: Array = []
	for rock in OUTCROP:
		out.append([float(rock[0]), float(rock[1]), deg_to_rad(float(rock[2])), rock[3]])
	return out


## Hidden under unexplored fog like every other forest visual (visible_fn: x, z, radius -> bool).
func update_view(visible_fn: Callable) -> void:
	for item in items:
		item.node.visible = visible_fn.call(item.center.x, item.center.y, item.radius) if visible_fn.is_valid() else true
