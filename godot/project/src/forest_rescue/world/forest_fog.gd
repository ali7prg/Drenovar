extends Node3D
## Fog layer manager (v2): ONE terrain-following shell whose shader raymarches a height-limited
## fog volume (forest_fog.gdshader), a 70×70 state texture (the 56×56 server grid + an always
## fogged 7-cell ring, updated only when the projection changes), a ground heightmap and a
## tiling noise texture. All animation is uniforms only (drift, reveal progress): no per-frame
## texture uploads, no particles, alpha overdraw = 1 layer.
##
## Per cell the CPU bakes the fog-top height: it rises from the floor at the explored edge to
## canopy height FOG_TOP over TOP_RAMP metres, and on the camera-near side of explored ground it
## is capped so a bank never hides ground behind it (the city camera is fixed: a bank H metres
## high hides H·cot(38°) of ground in the view direction, which is the (-1,-1) cell diagonal).

signal reveal_finished

const SHADER := preload("res://src/forest_rescue/world/forest_fog.gdshader")
const COLUMNS := 56
const ROWS := 56
const CELL := 4.0
const ORIGIN := -112.0
const BYTES := 392
const REVEAL_SECONDS := 2.0
const GRID := 70                  # state grid incl. the ring outside the atlas
const GRID_OFFSET := 7
const GRID_ORIGIN := -140.0
const FOG_TOP := 17.5             # deep fog top above the ground (m); billows ±28 %
const TOP_RAMP := 16.0            # top rises over this distance from the explored edge
const HEIGHT_RANGE := 30.0        # B/A channel scale (m)
const VIEW_SLOPE := 1.28          # cot(38°)
const HEIGHT_LO := -4.0
const HEIGHT_SPAN := 40.0
const LAYERS := [{"name": "FogVolume", "drift": 0.6}]

static var _noise_texture: ImageTexture
static var _shell_mesh: ArrayMesh
static var _shell_key := ""
static var _height_texture: ImageTexture

var state_image := Image.create(GRID, GRID, false, Image.FORMAT_RGBA8)
var state_texture: ImageTexture
var target_bits := PackedByteArray()
var anchor_bits := PackedByteArray()
var materials: Array[ShaderMaterial] = []
var shells: Array[MeshInstance3D] = []
var reveal_t := 1.0
var reveal_seconds := REVEAL_SECONDS
var reduced_motion := false
var revealing := false
var dim_strength := 0.0
var soft_depth := true


func _ready() -> void:
	set_process(false)


func build(height_fn: Callable, light_dir: Vector3) -> void:
	state_image.fill(Color(0, 0, 0, FOG_TOP / HEIGHT_RANGE))
	for row in GRID:
		for column in GRID:
			state_image.set_pixel(column, row, Color(0, 0, FOG_TOP / HEIGHT_RANGE, FOG_TOP / HEIGHT_RANGE))
	state_texture = ImageTexture.create_from_image(state_image)
	if _noise_texture == null:
		_noise_texture = ImageTexture.create_from_image(make_noise_image(256))
	var key := "shell_v3"
	if _shell_mesh == null or _shell_key != key:
		_shell_mesh = make_shell_mesh(height_fn)
		_height_texture = make_height_texture(height_fn)
		_shell_key = key
	var material := ShaderMaterial.new()
	material.shader = SHADER
	material.render_priority = 10
	material.set_shader_parameter("state_tex", state_texture)
	material.set_shader_parameter("height_tex", _height_texture)
	material.set_shader_parameter("noise_tex", _noise_texture)
	material.set_shader_parameter("domain", Vector4(GRID_ORIGIN, GRID_ORIGIN, GRID * CELL, GRID * CELL))
	material.set_shader_parameter("height_range", HEIGHT_RANGE)
	material.set_shader_parameter("height_lo", HEIGHT_LO)
	material.set_shader_parameter("height_span", HEIGHT_SPAN)
	material.set_shader_parameter("drift_speed", LAYERS[0].drift)
	material.set_shader_parameter("light_dir", light_dir.normalized())
	var shell := MeshInstance3D.new()
	shell.name = LAYERS[0].name
	shell.mesh = _shell_mesh
	shell.material_override = material
	shell.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	shell.extra_cull_margin = 40.0
	add_child(shell)
	shells.append(shell)
	materials.append(material)


## Smoothed ground (max of 5 taps, so the volume floor never cuts ridges) on a 2 m grid.
static func smoothed_ground(height_fn: Callable, x: float, z: float) -> float:
	var h := -1.35
	for o in [Vector2.ZERO, Vector2(2.5, 0), Vector2(-2.5, 0), Vector2(0, 2.5), Vector2(0, -2.5)]:
		h = maxf(h, float(height_fn.call(x + o.x, z + o.y)))
	return h


static func make_height_texture(height_fn: Callable) -> ImageTexture:
	var n := 141
	var image := Image.create(n, n, false, Image.FORMAT_L8)
	for j in n:
		for i in n:
			var x := GRID_ORIGIN + i * 2.0
			var z := GRID_ORIGIN + j * 2.0
			var h := smoothed_ground(height_fn, x, z)
			var v := clampf((h - HEIGHT_LO) / HEIGHT_SPAN, 0.0, 1.0)
			image.set_pixel(i, j, Color(v, v, v, 1.0))
	return ImageTexture.create_from_image(image)


## Terrain-following grid: 4 m inside ±144, 8 m out to ±224, hole over the always-clear town.
static func make_shell_mesh(height_fn: Callable) -> ArrayMesh:
	var coords := PackedFloat32Array()
	var c := -224.0
	while c <= 224.0001:
		coords.append(c)
		c += 4.0 if absf(c) < 144.0 else 8.0
	var n := coords.size()
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	vertices.resize(n * n)
	normals.resize(n * n)
	for j in n:
		for i in n:
			var x := coords[i]
			var z := coords[j]
			vertices[j * n + i] = Vector3(x, smoothed_ground(height_fn, x, z), z)
			normals[j * n + i] = Vector3.UP
	var indices := PackedInt32Array()
	for j in n - 1:
		for i in n - 1:
			var x0 := coords[i]
			var x1 := coords[i + 1]
			var z0 := coords[j]
			var z1 := coords[j + 1]
			if maxf(absf(x0), absf(x1)) < 50.0 and maxf(absf(z0), absf(z1)) < 50.0:
				continue
			var a := j * n + i
			indices.append_array(PackedInt32Array([a, a + 1, a + n, a + 1, a + n + 1, a + n]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


## RGBA tiling noise: R large billows, G mid, B fine (cellular wisps), A reveal delay.
static func make_noise_image(size: int) -> Image:
	var image := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var layers: Array[Image] = []
	var specs := [[FastNoiseLite.TYPE_SIMPLEX_SMOOTH, 3, 4.0], [FastNoiseLite.TYPE_SIMPLEX_SMOOTH, 4, 6.0],
		[FastNoiseLite.TYPE_CELLULAR, 2, 10.0], [FastNoiseLite.TYPE_SIMPLEX_SMOOTH, 2, 5.0]]
	for k in 4:
		var noise := FastNoiseLite.new()
		noise.seed = 1701 + k * 97
		noise.noise_type = specs[k][0]
		noise.fractal_type = FastNoiseLite.FRACTAL_FBM
		noise.fractal_octaves = specs[k][1]
		noise.frequency = float(specs[k][2]) / size
		if k == 2:
			noise.cellular_return_type = FastNoiseLite.RETURN_DISTANCE
		var layer := noise.get_seamless_image(size, size, false, false, 0.1, true)
		layer.convert(Image.FORMAT_L8)
		layers.append(layer)
	for y in size:
		for x in size:
			image.set_pixel(x, y, Color(layers[0].get_pixel(x, y).r, layers[1].get_pixel(x, y).r,
				layers[2].get_pixel(x, y).r, layers[3].get_pixel(x, y).r))
	image.generate_mipmaps()
	return image


static func decode_base64(text: String) -> PackedByteArray:
	if text.is_empty():
		return PackedByteArray()
	var bytes := Marshalls.base64_to_raw(text)
	if bytes.size() != BYTES or Marshalls.raw_to_base64(bytes) != text:
		return PackedByteArray()
	return bytes


static func bit(bytes: PackedByteArray, column: int, row: int) -> bool:
	if column < 0 or row < 0 or column >= COLUMNS or row >= ROWS or bytes.size() != BYTES:
		return false
	var index := row * COLUMNS + column
	return (bytes[index >> 3] & (1 << (index & 7))) != 0


static func set_bit(bytes: PackedByteArray, column: int, row: int) -> void:
	if column < 0 or row < 0 or column >= COLUMNS or row >= ROWS:
		return
	var index := row * COLUMNS + column
	bytes[index >> 3] = bytes[index >> 3] | (1 << (index & 7))


static func cell_of(x: float, z: float) -> Vector2i:
	var column := floori((x - ORIGIN) / CELL)
	var row := floori((z - ORIGIN) / CELL)
	if column < 0 or row < 0 or column >= COLUMNS or row >= ROWS:
		return Vector2i(-1, -1)
	return Vector2i(column, row)


## createFogState(): the protected ±56 square (cell centres −54…54).
static func default_town_bits() -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(BYTES)
	var z := -54.0
	while z <= 54.0:
		var x := -54.0
		while x <= 54.0:
			var cell := cell_of(x, z)
			set_bit(bytes, cell.x, cell.y)
			x += 4.0
		z += 4.0
	return bytes


## fog.mjs disc(): marks cells whose centre lies within `radius` of p.
static func stamp_disc(bytes: PackedByteArray, p: Vector2, radius: float) -> void:
	var min_c := maxi(0, ceili((p.x - radius + 110.0) / 4.0))
	var max_c := mini(55, floori((p.x + radius + 110.0) / 4.0))
	var min_r := maxi(0, ceili((p.y - radius + 110.0) / 4.0))
	var max_r := mini(55, floori((p.y + radius + 110.0) / 4.0))
	for r in range(min_r, max_r + 1):
		for c in range(min_c, max_c + 1):
			var cx := -110.0 + c * 4.0
			var cz := -110.0 + r * 4.0
			if Vector2(cx - p.x, cz - p.y).length() <= radius:
				set_bit(bytes, c, r)


static func corridor_bits(from: Vector2, to: Vector2, radius: float) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(BYTES)
	for i in 9:
		stamp_disc(bytes, from.lerp(to, i / 8.0), radius)
	return bytes


static func count_bits(bytes: PackedByteArray) -> int:
	var total := 0
	for value in bytes:
		var v := int(value)
		while v:
			total += v & 1
			v >>= 1
	return total


## Fog-top heights (m) for the 70×70 state grid from a 56×56 clear mask: ramp from the explored
## edge (chamfer distance) and the camera-near cap (distance to clear ground along the view).
static func fog_tops(bits: PackedByteArray) -> PackedFloat32Array:
	var n := GRID
	var clear := PackedByteArray()
	clear.resize(n * n)
	for row in ROWS:
		for column in COLUMNS:
			if bit(bits, column, row):
				clear[(row + GRID_OFFSET) * n + column + GRID_OFFSET] = 1
	var d := PackedFloat32Array()
	d.resize(n * n)
	for k in n * n:
		d[k] = 0.0 if clear[k] == 1 else 999.0
	for pass_index in 2:
		var rows := range(n) if pass_index == 0 else range(n - 1, -1, -1)
		var columns := range(n) if pass_index == 0 else range(n - 1, -1, -1)
		var step := -1 if pass_index == 0 else 1
		for row in rows:
			for column in columns:
				var k: int = row * n + column
				var best := d[k]
				for o in [Vector2i(step, 0), Vector2i(0, step), Vector2i(step, step), Vector2i(-step, step)]:
					var c: int = column + o.x
					var r: int = row + o.y
					if c >= 0 and r >= 0 and c < n and r < n:
						best = minf(best, d[r * n + c] + (1.4142 if o.x != 0 and o.y != 0 else 1.0))
				d[k] = best
	var tops := PackedFloat32Array()
	tops.resize(n * n)
	for row in n:
		for column in n:
			var k := row * n + column
			if clear[k] == 1:
				tops[k] = 0.0
				continue
			var edge := maxf(0.0, d[k] * CELL - CELL * 0.5)
			var top := FOG_TOP * smoothstep(0.0, TOP_RAMP, edge + 2.0)
			# Camera-near cap: the view crosses the ground toward (-X, -Z) = cell diagonal (-1, -1).
			for s in range(1, 14):
				var c := column - s
				var r := row - s
				if c < 0 or r < 0:
					break
				if clear[r * n + c] == 1:
					var behind := s * CELL * 1.41421 - CELL * 0.7
					top = minf(top, maxf(0.0, (behind + 2.5) / (VIEW_SLOPE * 1.28)))
					break
			tops[k] = top
	return tops


## Sets the displayed target. animate=false snaps (reduced motion / first frame).
## State texel: R target clear, G previous clear, B target fog top, A previous fog top.
func set_target(bits: PackedByteArray, anchors: PackedByteArray, animate: bool, seconds := REVEAL_SECONDS) -> void:
	if bits.size() != BYTES:
		return
	var previous := target_bits
	target_bits = bits
	anchor_bits = anchors if anchors.size() == BYTES else PackedByteArray()
	var tops := fog_tops(bits)
	var grows := false
	var first := previous.size() != BYTES
	var shown_t := smoothstep(0.0, 1.0, reveal_t)
	for row in GRID:
		for column in GRID:
			var inner_c := column - GRID_OFFSET
			var inner_r := row - GRID_OFFSET
			var before := bit(previous, inner_c, inner_r) if not first else false
			var after := bit(bits, inner_c, inner_r)
			if after and not before:
				grows = true
			var px := state_image.get_pixel(column, row)
			# During an unfinished reveal, continue from what is shown now.
			var start := lerpf(px.g, px.r, shown_t) if revealing else px.r
			var start_top := lerpf(px.a, px.b, shown_t) if revealing else px.b
			var target_top := tops[row * GRID + column] / HEIGHT_RANGE
			if first or not animate:
				start = 1.0 if after else 0.0
				start_top = target_top
			state_image.set_pixel(column, row, Color(1.0 if after else 0.0, start, target_top, start_top))
	state_texture.update(state_image)
	if animate and grows and not reduced_motion:
		reveal_seconds = maxf(0.05, seconds)
		reveal_t = 0.0
		revealing = true
		set_process(true)
	else:
		reveal_t = 1.0
		revealing = false
		_settle()
	_push_reveal()


func _settle() -> void:
	for row in GRID:
		for column in GRID:
			var p := state_image.get_pixel(column, row)
			state_image.set_pixel(column, row, Color(p.r, p.r, p.b, p.b))
	state_texture.update(state_image)


func _process(delta: float) -> void:
	if not revealing:
		set_process(false)
		return
	reveal_t = minf(1.0, reveal_t + delta / reveal_seconds)
	_push_reveal()
	if reveal_t >= 1.0:
		revealing = false
		_settle()
		set_process(false)
		reveal_finished.emit()


func _push_reveal() -> void:
	var curl := sin(PI * clampf(reveal_t, 0.0, 1.0)) if revealing else 0.0
	for material in materials:
		material.set_shader_parameter("reveal_t", reveal_t)
		material.set_shader_parameter("reveal_curl", curl)


func finish_now() -> void:
	if revealing:
		reveal_t = 1.0
		_process(0.0)


func set_reduced_motion(on: bool) -> void:
	reduced_motion = on
	if on:
		finish_now()
	for material in materials:
		material.set_shader_parameter("drift_speed", 0.0 if on else LAYERS[0].drift)


func set_dim(strength: float) -> void:
	dim_strength = strength
	for material in materials:
		material.set_shader_parameter("dim_strength", strength)


func set_sights(points: Array) -> void:
	var packed: Array[Vector4] = []
	for p in points.slice(0, 8):
		packed.append(p)
	while packed.size() < 8:
		packed.append(Vector4.ZERO)
	for material in materials:
		material.set_shader_parameter("sights", packed)
		material.set_shader_parameter("sight_count", mini(points.size(), 8))


func set_soft_depth(on: bool) -> void:
	soft_depth = on


## Displayed clear amount (0..1) at a point, CPU mirror of the shader's state blend.
func displayed_clear(x: float, z: float) -> float:
	var cell := cell_of(x, z)
	if cell.x < 0:
		return 0.0
	var p := state_image.get_pixel(cell.x + GRID_OFFSET, cell.y + GRID_OFFSET)
	return lerpf(p.g, p.r, reveal_t)
