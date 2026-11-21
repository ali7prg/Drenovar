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

const POND_CENTER := Vector2(23.0, -64.3)
const POND_RADIUS := 3.4
## Outcrop rocks [x, z, yaw°, scale]: kit lf_env_moss_rock v1 (limestone, 9.3 × 6.5 × 5.8 m).
const OUTCROP := [
	[19.3, -68.1, 228.0, Vector3(0.64, 1.12, 0.52)],
	[17.2, -65.2, 132.0, Vector3(0.4, 0.7, 0.38)],
	[22.2, -70.0, 32.0, Vector3(0.36, 0.62, 0.34)],
	[25.4, -61.6, 300.0, Vector3(0.18, 0.22, 0.18)],
	[20.0, -61.4, 75.0, Vector3(0.16, 0.2, 0.17)],
]
const ROCK_HEIGHT := 5.76               # moss rock v1 LOD0 top (model space)
## The fall: lip on the outcrop's south-east face, facing the camera (+X +Z).
const FALLS_LIP := Vector2(20.7, -66.6)
const FALLS_FACING := Vector2(0.7071, 0.7071)
const FALLS_WIDTH := 3.8
## Pass 2 (art/01 at zoom 68: a wide white cascade, not a stripe): the fall breaks on a ledge at
## FALLS_LEDGE of its height and drops on in a wider lower sheet into a foaming pond.
const FALLS_LEDGE := 0.5
const FALLS_LOWER_WIDTH := 5.0
## [offset across the lip, width, lip height offset, offset out from the rock, noise seed]
const FALLS_STREAMS := [[-1.45, 1.05, -0.35, 0.15, 0.13], [0.15, 1.55, 0.15, 0.0, 0.47], [1.65, 0.85, -0.9, 0.25, 0.81]]
## Pass 2: the marsh pools sit right below glade 07's clearing (art/01 S-G), in the camera's view.
const MARSH_POOLS := [[Vector2(70.5, 101.8), 4.0], [Vector2(64.6, 99.3), 3.0], [Vector2(63.0, 105.0), 2.5], [Vector2(76.4, 99.6), 2.1]]

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
				"minor": float(feature.get("minor", feature.radius)), "rot": float(feature.get("rot", 0.0)),
				"level": forest_atlas.WATER_LEVEL, "depth": 1.1, "bank": 0.42, "noise": 0.13, "seed": 1.7,
				"perched": false, "lily": 0.22, "murk": 0.06, "river": 1.0, "depth_gain": 2.4, "edge_soft": 0.18})
	out.append({"id": "pond", "kind": "pond", "center": POND_CENTER, "radius": POND_RADIUS,
		"level": ForestTerrain.base_height(POND_CENTER.x, POND_CENTER.y) - 0.42, "depth": 0.7, "bank": 1.1,
		"noise": 0.12, "seed": 4.1, "perched": true, "lily": 0.42, "murk": 0.12, "river": 0.0})
	for i in MARSH_POOLS.size():
		var c: Vector2 = MARSH_POOLS[i][0]
		out.append({"id": "marsh_%d" % i, "kind": "marsh", "center": c, "radius": float(MARSH_POOLS[i][1]),
			"level": ForestTerrain.base_height(c.x, c.y) - 0.24, "depth": 0.4, "bank": 0.5, "noise": 0.16,
			"seed": 2.3 + i, "perched": true, "lily": 0.2, "murk": 0.85, "river": 0.0, "depth_gain": 1.3, "edge_soft": 0.6,
			"murky_color": Color(0.15, 0.21, 0.17)})
	return out


static func shore_radius(body: Dictionary, angle: float) -> float:
	return ForestTerrain.shore_radius(body, angle)


func build(forest_atlas: RefCounted, height_fn: Callable, noise: Texture2D) -> void:
	atlas = forest_atlas
	for child in get_children():
		child.free()
	items.clear()
	for body in bodies(atlas):
		_build_body(body, noise)
	_build_falls(height_fn, noise)
	_build_mist(noise)


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
	material.set_shader_parameter("depth_gain", float(body.get("depth_gain", 1.0)))
	material.set_shader_parameter("edge_soft", float(body.get("edge_soft", 0.16)))
	if body.has("murky_color"):
		material.set_shader_parameter("murky_color", body.murky_color)
	if body.kind == "pond":
		var foot := FALLS_LIP + FALLS_FACING * 1.6
		material.set_shader_parameter("falls_point", Vector4(foot.x, foot.y, 3.4, 1.0))
	var node := MeshInstance3D.new()
	node.name = "Water_" + String(body.id)
	node.mesh = mesh
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	items.append({"node": node, "center": c, "radius": float(body.radius) * 1.2})


## The cascade (pass 2: readable at zoom 68): a wide main curtain from the outcrop lip down to the
## pond, a narrower second sheet stepping off a ledge beside it, and a soft foam / spray plume
## where they hit the water (additive billboard). Curtains bulge slightly out from the rock.
func _build_falls(height_fn: Callable, noise: Texture2D) -> void:
	var main: Array = OUTCROP[0]
	var base_y: float = height_fn.call(float(main[0]), float(main[1])) - 0.2
	falls_top = base_y + ROCK_HEIGHT * (main[3] as Vector3).y * 0.88
	var pond_level: float = ForestTerrain.base_height(POND_CENTER.x, POND_CENTER.y) - 0.42
	var bottom := pond_level + 0.02
	var across := Vector2(-FALLS_FACING.y, FALLS_FACING.x)
	# pass 4 (art/01: water over a dark rock lip, not a white sheet): three streams of different widths and
	# lip heights with dark wet rock between them, each a translucent streaked curtain
	for spec in FALLS_STREAMS:
		var lip: Vector2 = FALLS_LIP + across * float(spec[0]) + FALLS_FACING * float(spec[3])
		_add_curtain("Waterfall%d" % FALLS_STREAMS.find(spec), lip, falls_top + float(spec[2]), bottom, float(spec[1]), 0.1,
			noise, 0.4, float(spec[4]))
	# foam and spray at the foot
	var plume := MeshInstance3D.new()
	plume.name = "WaterfallSpray"
	var quad := QuadMesh.new()
	quad.size = Vector2(FALLS_LOWER_WIDTH * 1.35, 2.8)
	plume.mesh = quad
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, shadows_disabled, cull_disabled;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float n = texture(noise_tex, UV * vec2(1.5, 1.0) + vec2(TIME * 0.05, -TIME * 0.35)).r;
	float n2 = texture(noise_tex, UV * vec2(3.0, 2.0) + vec2(-TIME * 0.08, -TIME * 0.6)).g;
	float body = (1.0 - smoothstep(0.35, 1.0, length(p * vec2(1.0, 1.35)))) * smoothstep(-1.0, -0.2, -p.y * 0.6 - 0.1);
	ALBEDO = vec3(0.93, 0.96, 0.96);
	ALPHA = clamp(body * (0.35 + 0.4 * n) * (0.7 + 0.3 * n2), 0.0, 0.62);
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	material.render_priority = 3
	material.set_shader_parameter("noise_tex", noise)
	plume.material_override = material
	plume.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var foot := FALLS_LIP + FALLS_FACING * 1.9
	plume.position = Vector3(foot.x, bottom + 0.9, foot.y)
	add_child(plume)
	items.append({"node": plume, "center": foot, "radius": 3.0})


func _add_curtain(node_name: String, lip: Vector2, top: float, bottom: float, width: float, out0: float, noise: Texture2D, spread := 0.35, seed := 0.0) -> void:
	var across := Vector2(-FALLS_FACING.y, FALLS_FACING.x)
	var rows := 12
	var cols := 8
	var vertices := PackedVector3Array()
	var uvs := PackedVector2Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	for j in rows + 1:
		var v := float(j) / rows
		var out := out0 + 0.95 * pow(v, 1.5)
		var y := lerpf(top, bottom, v)
		var w := width * (0.85 + spread * v)
		for i in cols + 1:
			var u := float(i) / cols
			var bulge := 0.18 * sin(u * PI) * (1.0 - v)
			var p := lip + FALLS_FACING * (out + bulge) + across * (u - 0.5) * w
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
	material.set_shader_parameter("width_m", width)
	material.set_shader_parameter("height_m", maxf(1.0, top - bottom))
	material.set_shader_parameter("seed", seed)
	var node := MeshInstance3D.new()
	node.name = node_name
	node.mesh = mesh
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	items.append({"node": node, "center": lip, "radius": 3.0 + width * 0.5})


## Pass 4 (art/01: thin blue ground mist over the marsh pools, the lake and along the river): low drifting
## wisps (alpha <= 0.22) lying just above the water, kept off the trails and the bridge, so they never
## veil a trail, a camp or a unit; distinct from the opaque fog of war (thin, translucent, at water level).
const MIST_ALPHA := 0.1
static var _mist_material: ShaderMaterial


func _build_mist(noise: Texture2D) -> void:
	if _mist_material == null:
		_mist_material = ShaderMaterial.new()
		var shader := Shader.new()
		shader.code = """
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, shadows_disabled, cull_disabled, fog_disabled;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform float max_alpha = 0.22;
varying vec3 wpos;
void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float body = 1.0 - smoothstep(0.35, 1.0, length(p * vec2(1.0, 1.25)));
	float n = texture(noise_tex, wpos.xz / 17.0 + vec2(TIME * 0.012, TIME * 0.007)).r;
	float n2 = texture(noise_tex, wpos.xz / 6.5 + vec2(-TIME * 0.02, TIME * 0.015)).a;
	ALBEDO = vec3(0.62, 0.72, 0.8);
	ALPHA = clamp(body * smoothstep(0.35, 0.75, n * 0.7 + n2 * 0.45), 0.0, 1.0) * max_alpha;
}
"""
		_mist_material.shader = shader
		_mist_material.render_priority = 4
		_mist_material.set_shader_parameter("noise_tex", noise)
		_mist_material.set_shader_parameter("max_alpha", MIST_ALPHA)
	var spots: Array = []          # [centre Vector2, y, size Vector2, yaw]
	for body in bodies(atlas):
		if body.kind == "marsh":
			spots.append([body.center, float(body.level) + 0.55, Vector2(body.radius * 2.6, body.radius * 1.9), 0.3])
		elif body.kind == "lake":
			var rot := float(body.get("rot", 0.0))
			spots.append([body.center, float(body.level) + 0.7, Vector2(body.radius * 1.6, float(body.get("minor", body.radius)) * 1.4), -rot])
	var z := -98.0
	while z <= 104.0:
		var r: Vector3 = atlas.river_at(z)
		var c := Vector2(r.x, z)
		var deck: Rect2 = atlas.bridge_deck_rect()
		var hit: Dictionary = atlas.nearest_route(c.x, c.y, false)
		if not deck.grow(10.0).has_point(c) and float(hit.get("distance", 99.0)) > 5.0:
			var ahead: Vector3 = atlas.river_at(z + 4.0)
			var yaw := atan2(ahead.x - r.x, 4.0)
			spots.append([c, atlas.WATER_LEVEL + 0.75, Vector2(5.5, 13.0), yaw])
		z += 13.0
	for spot in spots:
		var node := MeshInstance3D.new()
		node.name = "Mist"
		var quad := QuadMesh.new()
		quad.size = spot[2]
		quad.orientation = PlaneMesh.FACE_Y
		node.mesh = quad
		node.material_override = _mist_material
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.position = Vector3(spot[0].x, float(spot[1]), spot[0].y)
		node.rotation.y = float(spot[3])
		add_child(node)
		items.append({"node": node, "center": spot[0], "radius": maxf(spot[2].x, spot[2].y) * 0.5})


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
