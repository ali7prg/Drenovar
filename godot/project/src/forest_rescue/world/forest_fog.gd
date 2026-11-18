extends Node3D
## Fog layer manager: three terrain-following shells sharing one mesh, one 56×56 state texture
## (updated only when the projection changes) and a tiling noise texture. All animation is
## uniforms only (drift, reveal progress) — no per-frame texture uploads, no particles.

signal reveal_finished

const SHADER := preload("res://src/forest_rescue/world/forest_fog.gdshader")
const COLUMNS := 56
const ROWS := 56
const CELL := 4.0
const ORIGIN := -112.0
const BYTES := 392
const REVEAL_SECONDS := 2.0
const LAYERS := [
	# lift (m), alpha, threshold, drift, edge softness
	# height = shell top above ground in deep fog (canopy ≈ 9–10.5 m); banks rise with depth.
	{"name": "FogHaze", "height": 9.0, "lift": 0.0, "alpha": 0.80, "threshold": 0.00, "drift": 0.45, "soft": 0.26},
	{"name": "FogBank", "height": 13.0, "lift": 0.0, "alpha": 0.84, "threshold": 0.10, "drift": 0.65, "soft": 0.26},
	{"name": "FogCrest", "height": 16.5, "lift": 0.0, "alpha": 0.90, "threshold": 0.22, "drift": 0.95, "soft": 0.30},
]

static var _noise_texture: ImageTexture
static var _shell_mesh: ArrayMesh
static var _shell_key := ""

var state_image := Image.create(COLUMNS, ROWS, false, Image.FORMAT_RGBA8)
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
	state_image.fill(Color(0, 0, 0, 0))
	state_texture = ImageTexture.create_from_image(state_image)
	if _noise_texture == null:
		_noise_texture = ImageTexture.create_from_image(make_noise_image(256))
	var key := "shell_v2"
	if _shell_mesh == null or _shell_key != key:
		_shell_mesh = make_shell_mesh(height_fn)
		_shell_key = key
	for i in LAYERS.size():
		var spec: Dictionary = LAYERS[i]
		var material := ShaderMaterial.new()
		material.shader = SHADER
		material.render_priority = 10 + i
		material.set_shader_parameter("state_tex", state_texture)
		material.set_shader_parameter("noise_tex", _noise_texture)
		material.set_shader_parameter("layer", float(i))
		material.set_shader_parameter("layer_alpha", spec.alpha)
		material.set_shader_parameter("layer_threshold", spec.threshold)
		material.set_shader_parameter("layer_height", spec.height)
		material.set_shader_parameter("drift_speed", spec.drift)
		material.set_shader_parameter("edge_softness", spec.soft)
		material.set_shader_parameter("light_dir", light_dir.normalized())
		material.set_shader_parameter("time_offset", 37.0 * i)
		material.set_shader_parameter("soft_depth", soft_depth)
		var shell := MeshInstance3D.new()
		shell.name = spec.name
		shell.mesh = _shell_mesh
		shell.position.y = 0.0
		shell.material_override = material
		shell.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		shell.extra_cull_margin = 16.0
		add_child(shell)
		shells.append(shell)
		materials.append(material)


## Terrain-following grid: 4 m inside ±124, 8 m out to ±220, hole over the always-clear town.
static func make_shell_mesh(height_fn: Callable) -> ArrayMesh:
	var coords := PackedFloat32Array()
	var c := -220.0
	while c <= 220.0001:
		coords.append(c)
		c += 4.0 if absf(c) < 124.0 else 8.0
	var n := coords.size()
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	vertices.resize(n * n)
	normals.resize(n * n)
	for j in n:
		for i in n:
			var x := coords[i]
			var z := coords[j]
			var h := -1.35
			# Smooth the ground under the shell (max of 5 taps) so banks do not clip ridges.
			for o in [Vector2.ZERO, Vector2(2.5, 0), Vector2(-2.5, 0), Vector2(0, 2.5), Vector2(0, -2.5)]:
				h = maxf(h, float(height_fn.call(x + o.x, z + o.y)))
			vertices[j * n + i] = Vector3(x, h, z)
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


## RGBA tiling noise: R large billows, G mid, B fine, A reveal delay.
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


## Depth into the fog per cell: chamfer distance (cells) to the nearest clear cell, /6 → 0..1.
static func fog_depth(bits: PackedByteArray) -> PackedFloat32Array:
	var d := PackedFloat32Array()
	d.resize(COLUMNS * ROWS)
	for row in ROWS:
		for column in COLUMNS:
			d[row * COLUMNS + column] = 0.0 if bit(bits, column, row) else 99.0
	for pass_index in 2:
		var rows := range(ROWS) if pass_index == 0 else range(ROWS - 1, -1, -1)
		var columns := range(COLUMNS) if pass_index == 0 else range(COLUMNS - 1, -1, -1)
		var step := -1 if pass_index == 0 else 1
		for row in rows:
			for column in columns:
				var k: int = row * COLUMNS + column
				var best := d[k]
				for o in [Vector2i(step, 0), Vector2i(0, step), Vector2i(step, step), Vector2i(-step, step)]:
					var c: int = column + o.x
					var r: int = row + o.y
					if c >= 0 and r >= 0 and c < COLUMNS and r < ROWS:
						best = minf(best, d[r * COLUMNS + c] + (1.4142 if o.x != 0 and o.y != 0 else 1.0))
				d[k] = best
	for k in d.size():
		d[k] = clampf(d[k] / 6.0, 0.0, 1.0)
	return d


## Sets the displayed target. animate=false snaps (reduced motion / first frame).
## State texel: R previous clear, G target clear, B previous depth, A target depth.
func set_target(bits: PackedByteArray, anchors: PackedByteArray, animate: bool, seconds := REVEAL_SECONDS) -> void:
	if bits.size() != BYTES:
		return
	var previous := target_bits
	target_bits = bits
	anchor_bits = anchors if anchors.size() == BYTES else PackedByteArray()
	var depth := fog_depth(bits)
	var grows := false
	for row in ROWS:
		for column in COLUMNS:
			var before := bit(previous, column, row) if previous.size() == BYTES else false
			var after := bit(bits, column, row)
			if after and not before:
				grows = true
			# During an unfinished reveal, continue from what is shown now.
			var shown := state_image.get_pixel(column, row)
			var start := lerpf(shown.r, shown.g, smoothstep(0.0, 1.0, reveal_t)) if revealing else (1.0 if before else 0.0)
			var start_depth := lerpf(shown.b, shown.a, smoothstep(0.0, 1.0, reveal_t)) if revealing else shown.a
			var target_depth := depth[row * COLUMNS + column]
			if previous.size() != BYTES:
				start_depth = target_depth
			state_image.set_pixel(column, row, Color(start if animate else (1.0 if after else 0.0), 1.0 if after else 0.0,
				start_depth if animate else target_depth, target_depth))
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
	for row in ROWS:
		for column in COLUMNS:
			var p := state_image.get_pixel(column, row)
			state_image.set_pixel(column, row, Color(p.g, p.g, p.a, p.a))
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
		material.set_shader_parameter("drift_speed", 0.0 if on else LAYERS[materials.find(material)].drift)


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
	for material in materials:
		material.set_shader_parameter("soft_depth", on)


## Displayed clear amount (0..1) at a point, CPU mirror of the shader's bilinear target.
func displayed_clear(x: float, z: float) -> float:
	var cell := cell_of(x, z)
	if cell.x < 0:
		return 0.0
	var p := state_image.get_pixel(cell.x, cell.y)
	return lerpf(p.r, p.g, reveal_t)
