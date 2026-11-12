class_name BattleFx
extends Node3D

# Battle presentation layer: weapon/claw sweeps, impact flashes, floating damage
# numbers, the battle area ring and the creature's health plate.
#
# Stateless per frame: the landscape re-requests every effect from the server's
# battle timeline each frame (begin() ... requests ... finish()), so effects stay in
# step with the authoritative events, survive scene switches and never accumulate.
# Nodes come from fixed pools created once; unused ones are hidden. No particles,
# no per-frame allocation, one small shader per effect type.

const SLASH := preload("res://src/fx_slash.gdshader")
const SPARK := preload("res://src/fx_spark.gdshader")
const RING := preload("res://src/fx_ring.gdshader")
const BAR := preload("res://src/fx_bar.gdshader")
const POOL := {"slash": 14, "spark": 10, "number": 10, "ring": 3, "bar": 3, "plate": 3}

var pools := {}
var used := {}

func _ready() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	for kind in POOL:
		var items: Array = []
		for index in POOL[kind]:
			items.append(make(kind, quad))
		pools[kind] = items
		used[kind] = 0

func make(kind: String, quad: QuadMesh) -> Node3D:
	var node: Node3D
	if kind in ["number", "plate"]:
		var label := Label3D.new()
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.shaded = false
		label.double_sided = true
		label.render_priority = 3
		label.outline_render_priority = 2
		# Constant on-screen size, readable at any zoom.
		label.fixed_size = true
		label.font_size = 64 if kind == "number" else 40
		label.outline_size = 16 if kind == "number" else 12
		label.pixel_size = 0.00042 if kind == "number" else 0.00036
		label.outline_modulate = Color(0.06, 0.04, 0.03, 0.9)
		node = label
	else:
		var mesh := MeshInstance3D.new()
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var material := ShaderMaterial.new()
		material.shader = {"slash": SLASH, "spark": SPARK, "ring": RING, "bar": BAR}[kind]
		material.render_priority = 2 if kind != "ring" else 0
		if kind == "ring":
			var plane := PlaneMesh.new()
			plane.size = Vector2(2, 2)
			mesh.mesh = plane
		else:
			mesh.mesh = quad
		mesh.material_override = material
		node = mesh
	node.visible = false
	add_child(node)
	return node

func take(kind: String) -> Node3D:
	var index: int = used[kind]
	var items: Array = pools[kind]
	if index >= items.size():
		return null
	used[kind] = index + 1
	var node: Node3D = items[index]
	node.visible = true
	return node

func begin() -> void:
	for kind in used:
		used[kind] = 0

func finish() -> void:
	for kind in pools:
		var items: Array = pools[kind]
		for index in range(used[kind], items.size()):
			items[index].visible = false

# Sweep from an attacker toward a target. progress 0..1 over the swing.
func slash(at: Vector3, toward: Vector3, progress: float, tint: Color, size := 1.6) -> void:
	if progress < 0.0 or progress > 1.0:
		return
	var node := take("slash") as MeshInstance3D
	if node == null:
		return
	node.position = at.lerp(toward, 0.35) + Vector3.UP * 1.0
	var material: ShaderMaterial = node.material_override
	material.set_shader_parameter("progress", progress)
	material.set_shader_parameter("tint", tint)
	material.set_shader_parameter("size", size)
	# Screen-space angle: sweep across the attack direction, alternating per strike.
	material.set_shader_parameter("angle", atan2(toward.z - at.z, toward.x - at.x) * 0.5 + 0.6)

func spark(at: Vector3, progress: float, tint: Color, size := 1.3, seed := 0.0) -> void:
	if progress < 0.0 or progress > 1.0:
		return
	var node := take("spark") as MeshInstance3D
	if node == null:
		return
	node.position = at + Vector3.UP * 1.1
	var material: ShaderMaterial = node.material_override
	material.set_shader_parameter("progress", progress)
	material.set_shader_parameter("tint", tint)
	material.set_shader_parameter("size", size)
	material.set_shader_parameter("seed", seed)

# Damage number that pops, rises and fades over ~0.9 s.
func number(at: Vector3, text: String, progress: float, tint: Color, big := false) -> void:
	if progress < 0.0 or progress > 1.0:
		return
	var label := take("number") as Label3D
	if label == null:
		return
	var pop := 1.0 + 0.45 * (1.0 - smoothstep(0.0, 0.18, progress))
	label.text = text
	label.position = at + Vector3.UP * (1.2 + progress * 1.3)
	label.modulate = Color(tint, 1.0 - smoothstep(0.6, 1.0, progress))
	label.outline_modulate.a = label.modulate.a * 0.9
	label.pixel_size = (0.00056 if big else 0.00042) * pop

func ring(centre: Vector3, radius: float, tint: Color) -> void:
	var node := take("ring") as MeshInstance3D
	if node == null:
		return
	node.position = centre + Vector3.UP * 0.12
	node.scale = Vector3(radius, 1.0, radius)
	(node.material_override as ShaderMaterial).set_shader_parameter("tint", tint)

# Health plate above a creature: name line and bar (ratio, recently lost part).
func health(at: Vector3, title: String, ratio: float, recent: float, tint: Color, scale := 1.0) -> void:
	var bar := take("bar") as MeshInstance3D
	var plate := take("plate") as Label3D
	if bar == null or plate == null:
		return
	bar.position = at + Vector3.UP * 0.2
	var material: ShaderMaterial = bar.material_override
	material.set_shader_parameter("ratio", clampf(ratio, 0.0, 1.0))
	material.set_shader_parameter("recent", clampf(maxf(ratio, recent), 0.0, 1.0))
	material.set_shader_parameter("fill", tint)
	material.set_shader_parameter("size", Vector2(2.6, 0.28) * scale)
	plate.text = title
	plate.position = at + Vector3.UP * 0.55 * scale
	plate.modulate = Color("#ffd9b0")
