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
const DUST := preload("res://src/fx_dust.gdshader")
const RING := preload("res://src/fx_ring.gdshader")
const BAR := preload("res://src/fx_bar.gdshader")
const POOL := {"slash": 16, "spark": 14, "dust": 12, "number": 10, "ring": 3, "bar": 3, "plate": 3}

var pools := {}
# For the device report: when a battle was last drawn and with how many events.
var last_battle_msec := -1
var last_battle_events := 0
var used := {}
var number_requests: Array = []
var number_rects: Array[Rect2] = []
var number_evidence: Array = []

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
	if kind == "number":
		node = Node3D.new()
		var label := Label.new()
		label.name = "Text"
		label.visible = false
		label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		label.add_theme_color_override("font_outline_color", Color("#16110c"))
		label.add_theme_constant_override("outline_size", 4)
		node.add_child(label)
	elif kind == "plate":
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
		label.pixel_size = 0.0007 if kind == "number" else 0.00055
		label.outline_modulate = Color(0.06, 0.04, 0.03, 0.9)
		node = label
	else:
		var mesh := MeshInstance3D.new()
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var material := ShaderMaterial.new()
		material.shader = {"slash": SLASH, "spark": SPARK, "dust": DUST, "ring": RING, "bar": BAR}[kind]
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
	if kind == "number": node.get_node("Text").show()
	return node

func begin() -> void:
	number_requests.clear()
	number_rects.clear()
	number_evidence.clear()
	for kind in used:
		used[kind] = 0

func finish() -> void:
	place_numbers()
	for kind in pools:
		var items: Array = pools[kind]
		for index in range(used[kind], items.size()):
			items[index].visible = false
			if kind == "number": items[index].get_node("Text").hide()

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

# Dust kicked up at the feet (a charge, a creature's lunge): a low, wide, soft puff.
func dust(at: Vector3, progress: float, size := 1.5, seed := 0.0) -> void:
	if progress < 0.0 or progress > 1.0:
		return
	var node := take("dust") as MeshInstance3D
	if node == null:
		return
	node.position = at + Vector3.UP * (0.35 + progress * 0.45)
	var material: ShaderMaterial = node.material_override
	material.set_shader_parameter("progress", progress)
	material.set_shader_parameter("tint", Color(0.72, 0.62, 0.46, 0.55))
	material.set_shader_parameter("size", size * (0.8 + progress * 0.7))
	material.set_shader_parameter("seed", seed)

# Damage number that pops, rises and fades over ~0.9 s.
func number(at: Vector3, text: String, progress: float, tint: Color, big := false, ids: Array = [], target := "", final := false) -> void:
	if progress < 0.0 or progress > 1.0:
		return
	number_requests.append({"at":at,"text":text,"progress":progress,"tint":tint,"big":big,"ids":ids,"target":target,"final":final})

func place_numbers() -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null: return
	# Canvas-items stretch uses a 1366px design width. Express legibility and
	# exclusion zones in actual viewport pixels, then convert to canvas units.
	var pixel := 1.0 / maxf(0.01,get_viewport().get_stretch_transform().get_scale().x)
	var viewport := get_viewport().get_visible_rect().grow(-8.0*pixel)
	var protected: Array[Rect2] = []
	for request in number_requests:
		var contact := camera.unproject_position(request.at + Vector3.UP * 1.1)
		protected.append(Rect2(contact-Vector2(38,30)*pixel,Vector2(76,60)*pixel))
	number_requests.sort_custom(func(a,b): return a.final and not b.final)
	for request in number_requests:
		if int(used.number) >= POOL.number: break
		if camera.is_position_behind(request.at): continue
		var item: Node3D = pools.number[int(used.number)]
		var label := item.get_node("Text") as Label
		label.text = request.text
		label.add_theme_font_size_override("font_size",roundi((20 if request.final else 18)*pixel))
		label.add_theme_constant_override("outline_size",roundi(2.0*pixel))
		label.reset_size()
		var size := label.get_minimum_size() + Vector2(8,4)*pixel
		var contact := camera.unproject_position(request.at + Vector3.UP * 1.1)
		var placed := false
		for row in 6:
			for side in [1.0,-1.0]:
				var centre := contact + Vector2(side*(52.0*pixel+size.x*0.5), -48.0*pixel-row*(size.y+4.0*pixel)+request.progress*8.0*pixel)
				var rect := Rect2(centre-size*0.5,size)
				if not viewport.encloses(rect) or protected.any(func(r):return r.intersects(rect)) or number_rects.any(func(r):return r.intersects(rect)):
					continue
				take("number")
				label.position = rect.position+Vector2(4,2)*pixel
				label.modulate = Color(request.tint,1.0-smoothstep(0.6,1.0,request.progress))
				number_rects.append(rect)
				number_evidence.append({"rect":rect,"event_ids":request.ids,"target":request.target,"text":request.text,"final":request.final})
				placed = true
				break
			if placed: break

# First-use preparation. Every effect kind is drawn once, transparent or at a
# negligible size, just in front of the camera when a scene opens, so its render
# pipelines are compiled then and not on the frame of the first blow. Measured on
# the Mobile renderer: the first fight compiled 3-6 surface/specialization
# pipelines exactly when its effects first appeared. Nothing visible is drawn.
func warm(camera: Camera3D) -> void:
	var at := camera.global_position - camera.global_transform.basis.z * (camera.near + 2.0)
	var side := camera.global_transform.basis.x * 0.01
	slash(at, at + side, 0.999, Color(1, 1, 1, 0.0), 0.001)
	spark(at, 0.999, Color(1, 1, 1, 0.0), 0.001)
	dust(at, 0.999, 0.001)
	ring(at, 0.001, Color(1, 1, 1, 0.0))
	health(at, "·", 0.5, 0.6, Color(1, 1, 1, 0.0), 0.001)
	var plate := pools.plate[maxi(0, int(used.plate) - 1)] as Label3D
	plate.modulate = Color(1, 1, 1, 0.0)
	plate.outline_modulate = Color(0, 0, 0, 0.0)
	var label := take("number").get_node("Text") as Label
	label.text = "-0123456789 ×"
	label.modulate = Color(1, 1, 1, 0.0)

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
	material.set_shader_parameter("size", Vector2(4.2, 0.45) * scale)
	plate.text = title
	plate.position = at + Vector3.UP * 0.8 * scale
	plate.modulate = Color("#ffd9b0")
	plate.outline_modulate = Color(0.06, 0.04, 0.03, 0.9)
