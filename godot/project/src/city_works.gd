extends Node3D

# Visible work in the city:
# - tree felling: a lumberjack walks to the tree and swings the axe, chips fly;
#   when the tree is felled it topples, dust rises and "+N дерева" floats up;
# - construction and upgrades: scaffolding, two builders hammering with sparks
#   and dust; when the work finishes a golden burst and "Уровень N" appear.
# Everything is procedural on the existing low-poly worker models (their arm and
# leg nodes are rotated), so no new animation assets are needed.

var stage: Node3D
var data: Dictionary
var lumberjack: Node3D
var lumber_tree := ""
var lumber_from := Vector3.ZERO
var lumber_at := Vector3.ZERO
var lumber_face := 0.0
var lumber_ends := 0.0
var last_now := 0.0
var chips: CPUParticles3D
var builders: Array[Node3D] = []
var builder_site := ""
var sparks: CPUParticles3D
var dust: CPUParticles3D
var last_swing := {}
var known_felled := {}
var known_levels := {}
var primed := false
# Trees and buildings that had visible work this session: only these topple or
# celebrate, not changes that happened while the app was closed.
var seen_work := {}

const SWING_HZ := 1.25
const WALK_SECONDS := 1.4

func setup(owner_stage: Node3D, game_data: Dictionary) -> void:
	stage = owner_stage
	data = game_data
	name = "CityWorks"

static func box_mesh(size: Vector3, color: Color, unshaded := false) -> BoxMesh:
	var mesh := BoxMesh.new()
	mesh.size = size
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.vertex_color_use_as_albedo = true
	if unshaded:
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mesh.material = material
	return mesh

func make_burst(color_a: Color, color_b: Color, amount: int, size: float, speed: float, lifetime: float, gravity: float, unshaded := false) -> CPUParticles3D:
	var particles := CPUParticles3D.new()
	particles.emitting = false
	particles.one_shot = true
	particles.explosiveness = 0.9
	particles.amount = amount
	particles.lifetime = lifetime
	particles.mesh = box_mesh(Vector3.ONE * size, Color.WHITE, unshaded)
	particles.direction = Vector3.UP
	particles.spread = 70.0
	particles.initial_velocity_min = speed * 0.5
	particles.initial_velocity_max = speed
	particles.gravity = Vector3(0, -gravity, 0)
	particles.angular_velocity_min = -360.0
	particles.angular_velocity_max = 360.0
	particles.scale_amount_min = 0.6
	particles.scale_amount_max = 1.2
	var ramp := Gradient.new()
	ramp.colors = PackedColorArray([color_a, color_b])
	particles.color_initial_ramp = ramp
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(particles)
	return particles

func ensure_effects() -> void:
	if chips == null:
		chips = make_burst(Color("#c99a5b"), Color("#7a5530"), 10, 0.13, 3.2, 0.8, 9.0)
		sparks = make_burst(Color("#fff2b0"), Color("#ff9a3a"), 8, 0.06, 3.6, 0.45, 6.0, true)
		dust = make_dust()

# Soft dust: camera-facing round puffs that grow and fade (no hard cubes).
func make_dust() -> CPUParticles3D:
	var particles := CPUParticles3D.new()
	particles.emitting = false
	particles.one_shot = true
	particles.explosiveness = 0.75
	particles.amount = 12
	particles.lifetime = 1.6
	var quad := QuadMesh.new()
	quad.size = Vector2(1.4, 1.4)
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	material.vertex_color_use_as_albedo = true
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	gradient.colors = PackedColorArray([Color(1, 1, 1, 0.85), Color(1, 1, 1, 0.35), Color(1, 1, 1, 0.0)])
	var puff := GradientTexture2D.new()
	puff.gradient = gradient
	puff.fill = GradientTexture2D.FILL_RADIAL
	puff.fill_from = Vector2(0.5, 0.5)
	puff.fill_to = Vector2(1.0, 0.5)
	puff.width = 64
	puff.height = 64
	material.albedo_texture = puff
	quad.material = material
	particles.mesh = quad
	particles.direction = Vector3.UP
	particles.spread = 60.0
	particles.initial_velocity_min = 0.6
	particles.initial_velocity_max = 1.6
	particles.gravity = Vector3(0, 0.25, 0)
	particles.damping_min = 0.6
	particles.damping_max = 1.2
	particles.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	particles.emission_sphere_radius = 0.9
	var grow := Curve.new()
	grow.add_point(Vector2(0.0, 0.45))
	grow.add_point(Vector2(1.0, 1.6))
	particles.scale_amount_curve = grow
	var fade := Gradient.new()
	fade.colors = PackedColorArray([Color(0.86, 0.8, 0.68, 0.7), Color(0.78, 0.74, 0.66, 0.0)])
	particles.color_ramp = fade
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(particles)
	return particles

static func limbs(actor: Node3D, part: String) -> Array[Node3D]:
	var found: Array[Node3D] = []
	for node in actor.find_children("*" + part + "*", "Node3D", true, false):
		found.append(node as Node3D)
	return found

func make_worker(model: String) -> Node3D:
	var asset: Dictionary = data.models[model]
	var actor: Node3D = stage.add_model(self, asset.path, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * 1.55), Vector3.ZERO))
	for player: AnimationPlayer in actor.find_children("*", "AnimationPlayer", true, false):
		player.stop()
		player.process_mode = Node.PROCESS_MODE_DISABLED
	var arms := limbs(actor, "arm")
	var legs := limbs(actor, "leg")
	actor.set_meta("arms", arms)
	actor.set_meta("legs", legs)
	actor.set_meta("arm_rest", arms.map(func(n): return n.rotation))
	actor.set_meta("leg_rest", legs.map(func(n): return n.rotation))
	return actor

func pose(actor: Node3D, arm_angle: float, leg_angle: float) -> void:
	var arms: Array = actor.get_meta("arms", [])
	var rest: Array = actor.get_meta("arm_rest", [])
	for index in arms.size():
		var sign := 1.0 if index % 2 == 0 else 0.6
		arms[index].rotation = rest[index] + Vector3(arm_angle * sign, 0, 0)
	var legs: Array = actor.get_meta("legs", [])
	var leg_rest: Array = actor.get_meta("leg_rest", [])
	for index in legs.size():
		legs[index].rotation = leg_rest[index] + Vector3(leg_angle * (1.0 if index % 2 == 0 else -1.0), 0, 0)

func tree_by_id(id: String) -> Dictionary:
	for tree in stage.selectable_trees:
		if tree.id == id:
			return tree
	return {}

# Called every frame in the city. job: {"tree": id, "started": ms, "ends": ms} or {}.
# site: {"position": Vector3, "started": ms, "ends": ms, "key": String} or {}.
func present(job: Dictionary, site: Dictionary, now_ms: float, delta: float) -> void:
	ensure_effects()
	last_now = now_ms
	present_lumberjack(job, now_ms)
	present_builders(site, now_ms)

func present_lumberjack(job: Dictionary, now_ms: float) -> void:
	var tree_id: String = job.get("tree", "")
	var tree := tree_by_id(tree_id) if not tree_id.is_empty() else {}
	if tree.is_empty():
		if is_instance_valid(lumberjack):
			lumberjack.visible = false
		lumber_tree = ""
		return
	if not is_instance_valid(lumberjack):
		lumberjack = make_worker("Worker_Lumberjack")
	seen_work[tree_id] = true
	if lumber_tree != tree_id:
		lumber_tree = tree_id
		var trunk: Vector3 = stage.array_point(tree.p)
		# Stand on the side facing the camera so the swing is visible.
		var side: Vector3 = stage.camera.global_position - trunk
		side.y = 0.0
		side = side.normalized() if side.length_squared() > 0.01 else Vector3.BACK
		side = side.rotated(Vector3.UP, 0.6)
		lumber_at = stage.ground_point(trunk + side * 1.55)
		lumber_from = stage.ground_point(trunk + side * 7.0)
		lumber_face = atan2(trunk.x - lumber_at.x, trunk.z - lumber_at.z)
	lumberjack.visible = true
	lumber_ends = float(job.get("ends", 0.0))
	var started := float(job.get("started", now_ms))
	var walking := clampf((now_ms - started) / (WALK_SECONDS * 1000.0), 0.0, 1.0)
	var seconds := (now_ms - started) / 1000.0
	if walking < 1.0:
		lumberjack.position = lumber_from.lerp(lumber_at, walking)
		lumberjack.rotation.y = lumber_face
		var stride := sin(seconds * 11.0)
		pose(lumberjack, stride * 0.5, stride * 0.55)
		return
	lumberjack.position = lumber_at
	lumberjack.rotation.y = lumber_face
	if now_ms >= lumber_ends and lumber_ends > 0.0:
		# Work time is over: the axe rests until the tree falls.
		pose(lumberjack, 0.0, 0.0)
		return
	# Raise slowly, strike fast: the axe hits at the bottom of each cycle.
	var cycle := fposmod((seconds - WALK_SECONDS) * SWING_HZ, 1.0)
	var arm := -2.3 * (cycle / 0.7) if cycle < 0.7 else -2.3 + 2.6 * ((cycle - 0.7) / 0.3)
	pose(lumberjack, arm, 0.0)
	lumberjack.rotation.x = 0.0
	var strike := int(floor((seconds - WALK_SECONDS) * SWING_HZ))
	if cycle > 0.97 or (cycle < 0.05 and strike > 0):
		if last_swing.get("lumber", -1) != strike:
			last_swing.lumber = strike
			var trunk: Vector3 = stage.array_point(tree.p)
			chips.global_position = trunk.lerp(lumber_at, 0.35) + Vector3.UP * 1.0
			chips.restart()

var site_node: Node3D
var site_model: Node3D
var site_model_path := ""
var site_frames: Array[Node3D] = []

# Construction site: scaffolding around the plot, a new building rising inside it
# with the timer (from foundations to full height), builders hammering with
# sparks, dust now and then. For an upgrade the building stays as it is and the
# scaffolding stands around it.
func present_builders(site: Dictionary, now_ms: float) -> void:
	var key: String = site.get("key", "")
	if key.is_empty():
		for builder in builders:
			builder.visible = false
		if is_instance_valid(site_node):
			site_node.visible = false
		builder_site = ""
		return
	if builders.is_empty():
		builders.append(make_worker("Worker_Smith"))
		builders.append(make_worker("Worker_Carrier"))
	var centre: Vector3 = site.position
	seen_work[key] = true
	var started := float(site.get("started", now_ms))
	var ends := float(site.get("ends", now_ms + 1.0))
	var progress := clampf((now_ms - started) / maxf(ends - started, 1.0), 0.0, 1.0)
	if builder_site != key:
		builder_site = key
		var offsets := [Vector3(-4.6, 0, 4.2), Vector3(4.8, 0, 3.6)]
		for index in builders.size():
			var p: Vector3 = stage.ground_point(centre + offsets[index])
			builders[index].position = p
			builders[index].rotation.y = atan2(centre.x - p.x, centre.z - p.z)
		build_site(site)
	site_node.visible = true
	site_node.position = centre
	# The walls-and-gate upgrade wraps the main gate: frame stretched along the wall.
	var frame: Vector3 = site.get("frame", Vector3.ONE)
	site_node.basis = Basis(Vector3.UP, float(site.get("yaw", 0.0))) * Basis.from_scale(frame)
	if is_instance_valid(site_model):
		# Rises from 12 % (foundations) to full height as the timer runs.
		var height := lerpf(0.12, 1.0, progress)
		site_model.scale = Vector3(float(site.get("scale", 1.0)), float(site.get("scale", 1.0)) * height, float(site.get("scale", 1.0)))
	var seconds := now_ms / 1000.0
	for index in builders.size():
		var builder := builders[index]
		builder.visible = true
		var cycle := fposmod(seconds * (1.6 + index * 0.25) + index * 0.37, 1.0)
		var arm := -1.9 * (cycle / 0.75) if cycle < 0.75 else -1.9 + 2.2 * ((cycle - 0.75) / 0.25)
		pose(builder, arm, 0.0)
		var hit := int(floor(seconds * (1.6 + index * 0.25) + index * 0.37))
		if cycle > 0.96 and last_swing.get("builder%d" % index, -1) != hit:
			last_swing["builder%d" % index] = hit
			var forward := Vector3(sin(builder.rotation.y), 0, cos(builder.rotation.y))
			sparks.global_position = builder.position + forward * 1.0 + Vector3.UP * 1.1
			sparks.restart()
	var puff := int(floor(seconds / 2.6))
	if last_swing.get("dust", -1) != puff:
		last_swing.dust = puff
		dust.global_position = centre + Vector3(randf_range(-3.0, 3.0), 0.6, randf_range(-3.0, 3.0))
		dust.restart()

func build_site(site: Dictionary) -> void:
	if not is_instance_valid(site_node):
		site_node = Node3D.new()
		site_node.name = "ConstructionSite"
		add_child(site_node)
	var wanted: String = site.get("model", "")
	if wanted != site_model_path or not is_instance_valid(site_model):
		if is_instance_valid(site_model):
			site_model.queue_free()
		site_model = null
		site_model_path = wanted
		if not wanted.is_empty():
			site_model = stage.add_model(site_node, wanted, Transform3D.IDENTITY)
	var half := 5.6 if site.get("upgrade", false) else 4.6
	if site_frames.is_empty() or not is_equal_approx(float(site_node.get_meta("half", 0.0)), half):
		for frame in site_frames:
			frame.queue_free()
		site_frames.clear()
		var scaffold := build_scaffold(half, 7.4 if site.get("upgrade", false) else 6.4)
		site_node.add_child(scaffold)
		site_frames.append(scaffold)
		site_node.set_meta("half", half)

static func timber() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("#6b4f31")
	material.roughness = 0.92
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material

# Timber scaffolding around a square plot: corner and middle poles, rails on three
# levels, plank decks and a cross brace per side. One mesh (SurfaceTool), so it
# costs a single draw call.
static func build_scaffold(half: float, height: float) -> MeshInstance3D:
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	var beam := func(a: Vector3, b: Vector3, thickness: float) -> void:
		var axis := b - a
		var length := axis.length()
		if length < 0.01:
			return
		var forward := axis / length
		var side := forward.cross(Vector3.UP if absf(forward.y) < 0.9 else Vector3.RIGHT).normalized() * thickness * 0.5
		var up := side.cross(forward).normalized() * thickness * 0.5
		var corners := [a - side - up, a + side - up, a + side + up, a - side + up,
			b - side - up, b + side - up, b + side + up, b - side + up]
		for face in [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7], [4, 5, 1, 0]]:
			var p0: Vector3 = corners[face[0]]
			var p1: Vector3 = corners[face[1]]
			var p2: Vector3 = corners[face[2]]
			var p3: Vector3 = corners[face[3]]
			var normal := (p1 - p0).cross(p2 - p0).normalized()
			for vertex in [p0, p2, p1, p0, p3, p2]:
				tool.set_normal(-normal)
				tool.add_vertex(vertex)
	var levels := [height * 0.32, height * 0.64, height * 0.96]
	for sx in [-1.0, 0.0, 1.0]:
		for sz in [-1.0, 0.0, 1.0]:
			if sx == 0.0 and sz == 0.0:
				continue
			beam.call(Vector3(sx * half, 0.0, sz * half), Vector3(sx * half, height, sz * half), 0.24)
	for level in levels:
		for side in 4:
			var angle := side * PI * 0.5
			var a := Vector3(-half, level, half).rotated(Vector3.UP, angle)
			var b := Vector3(half, level, half).rotated(Vector3.UP, angle)
			beam.call(a, b, 0.17)
			# Plank deck just inside the rail.
			var inward := Vector3(0, 0, -0.55).rotated(Vector3.UP, angle)
			beam.call(a + inward - Vector3.UP * 0.12, b + inward - Vector3.UP * 0.12, 0.5)
	for side in 4:
		var angle := side * PI * 0.5
		beam.call(Vector3(-half, 0.2, half + 0.05).rotated(Vector3.UP, angle),
			Vector3(0.0, levels[1], half + 0.05).rotated(Vector3.UP, angle), 0.14)
		beam.call(Vector3(half, 0.2, half + 0.05).rotated(Vector3.UP, angle),
			Vector3(0.0, levels[1], half + 0.05).rotated(Vector3.UP, angle), 0.14)
	var mesh := MeshInstance3D.new()
	mesh.name = "Scaffold"
	mesh.mesh = tool.commit()
	mesh.material_override = timber()
	return mesh

# Called by the landscape after each authoritative city update.
func observe_city(city: Dictionary, plots: Dictionary) -> void:
	var felled := {}
	for id in city.get("progress", {}).get("felled", []):
		felled[id] = true
	var levels := {}
	for building in city.get("buildings", []):
		levels[building.id] = int(building.level)
	if primed:
		for id in felled:
			if not known_felled.has(id) and seen_work.has(id):
				topple_tree(id)
		for building in city.get("buildings", []):
			var before: int = known_levels.get(building.id, 0)
			var worked: bool = seen_work.has(str(building.id)) or seen_work.has(str(building.plotId))
			if before != int(building.level) and plots.has(building.plotId) and worked:
				celebrate(plots[building.plotId], "Построено!" if before == 0 else "Уровень %d" % int(building.level))
	known_felled = felled
	known_levels = levels
	primed = true

func topple_tree(id: String) -> void:
	# The server may mark the tree felled when the order is accepted: the tree then
	# stands (as a copy) until the axe work ends, and falls afterwards.
	var wait := maxf(0.0, (lumber_ends - last_now) / 1000.0) if lumber_tree == id else 0.0
	var tree := tree_by_id(id)
	if tree.is_empty():
		return
	var trunk: Vector3 = stage.array_point(tree.p)
	if not stage.camera.is_position_in_frustum(trunk + Vector3.UP * 2.0):
		return
	var model: String = "tree" + str(int(tree.variant))
	if not data.models.has(model):
		return
	var pivot := Node3D.new()
	add_child(pivot)
	pivot.position = trunk
	var away: Vector3 = trunk - (lumber_at if lumber_tree == id else stage.camera.global_position)
	away.y = 0.0
	away = away.normalized() if away.length_squared() > 0.01 else Vector3.RIGHT
	pivot.rotation.y = atan2(away.x, away.z)
	var copy: Node3D = stage.add_model(pivot, data.models[model].path,
		Transform3D(Basis(Vector3.UP, float(tree.angle) - pivot.rotation.y).scaled(Vector3.ONE * float(tree.scale)), Vector3.ZERO))
	copy.name = "Falling"
	var fall := create_tween()
	if wait > 0.0:
		fall.tween_interval(minf(wait, 30.0))
	fall.tween_property(pivot, "rotation:x", deg_to_rad(86.0), 1.15).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	var reward := "+%d дерева" % int(tree.get("wood", 0))
	fall.tween_callback(func():
		dust.global_position = trunk + away * 4.0 + Vector3.UP * 0.4
		dust.restart()
		float_text(trunk + Vector3.UP * 4.0, reward, Color("#ffd28a")))
	fall.tween_property(pivot, "scale", Vector3.ONE * 0.01, 0.7).set_delay(0.5)
	fall.tween_callback(pivot.queue_free)

func celebrate(at: Vector3, text: String) -> void:
	if not stage.camera.is_position_in_frustum(at + Vector3.UP * 3.0):
		return
	var burst := make_burst(Color("#fff3b8"), Color("#e8a93a"), 36, 0.12, 7.5, 1.3, 7.0, true)
	burst.global_position = at + Vector3.UP * 3.0
	burst.spread = 180.0
	burst.restart()
	get_tree().create_timer(1.6).timeout.connect(burst.queue_free)
	float_text(at + Vector3.UP * 7.0, text, Color("#ffe39a"))

func float_text(at: Vector3, text: String, color: Color) -> void:
	var label := Label3D.new()
	label.text = text
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.fixed_size = true
	label.pixel_size = 0.0016
	label.font_size = 34
	label.outline_size = 12
	label.modulate = color
	label.outline_modulate = Color(0.08, 0.06, 0.04, 0.9)
	label.position = at
	add_child(label)
	var rise := create_tween()
	rise.tween_property(label, "position", at + Vector3.UP * 3.0, 1.8).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	rise.parallel().tween_property(label, "modulate:a", 0.0, 0.6).set_delay(1.2)
	rise.tween_callback(label.queue_free)
