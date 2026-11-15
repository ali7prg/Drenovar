extends Node3D

# Visible work in the city:
# - tree felling: a lumberjack walks to the tree and swings the axe, chips fly;
#   when the tree is felled it topples, dust rises and "+N дерева" floats up;
# - construction and upgrades: a small building site (delivery, scaffolding, the
#   parts of the new level appearing in build order, a hoist with the building's
#   load, builders hammering with sparks and dust, scaffolding taken down); when
#   the work finishes a golden burst and "Уровень N" appear.
# Everything is procedural on the existing low-poly worker models (their arm and
# leg nodes are rotated), so no new animation assets are needed.

const BuildReveal = preload("res://src/build_reveal.gd")

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
# Build 54: the rising level scene(s) and their build clocks.
var site_from: Node3D
var site_to: Node3D
var reveal_from: Array = []
var reveal_to: Array = []
var site_signature := ""
var site_scaffold: Node3D
var site_props: Node3D
var site_piles: Array[Node3D] = []
var site_hoist: Node3D
var site_load: Node3D
var site_hook: Node3D
var site_carrier: Node3D
var site_box := AABB(Vector3(-4, 0, -4), Vector3(8, 6, 8))
var hidden_building: Node3D

# Share of the order: delivery and scaffolding, building, scaffolding taken down.
const DELIVERY_END := 0.08
const STRIP_START := 0.9

static func build_clock(progress: float) -> float:
	## Building clock of the level scene (0..1) inside the order's progress.
	return clampf((progress - DELIVERY_END) / (STRIP_START - DELIVERY_END), 0.0, 1.0)

# Construction site as a small scene (build 54):
# - delivery: a carrier brings materials, piles fill, scaffolding goes up;
# - building: the parts of the new level appear in build order (foundations, frame
#   and walls course by course, roof from the eaves, then fittings), each one lowered
#   into place; a hoist lifts the load of the building type; an upgrade first takes
#   down what the new level replaces, keeps the rest and adds the new parts;
# - finish: the scaffolding is taken down and the finished level stands.
# Everything follows the order's own clock, so after leaving and coming back the
# site shows the stage the order has reached.
func present_builders(site: Dictionary, now_ms: float) -> void:
	var key: String = site.get("key", "")
	if key.is_empty():
		for builder in builders:
			builder.visible = false
		if is_instance_valid(site_node):
			site_node.visible = false
		if is_instance_valid(site_carrier):
			site_carrier.visible = false
		restore_building()
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
	if builder_site != key or site_signature != site_key(site):
		builder_site = key
		build_site(site)
		var offsets := [Vector3(site_box.position.x - 0.9, 0, site_box.end.z + 0.9), Vector3(site_box.end.x + 0.9, 0, site_box.end.z + 0.4)]
		var spots: Array = site.get("layout", {}).get("builders", [])
		if spots.size() >= 2 and not site.has("frame"):
			offsets = [Vector3(float(spots[0][0]), 0, float(spots[0][1])), Vector3(float(spots[1][0]), 0, float(spots[1][1]))]
		if site.has("frame"):
			offsets = [Vector3(-4.6, 0, 4.2), Vector3(4.8, 0, 3.6)]
		for index in builders.size():
			var p: Vector3 = stage.ground_point(centre + offsets[index])
			builders[index].position = p
			builders[index].rotation.y = atan2(centre.x - p.x, centre.z - p.z)
	site_node.visible = true
	site_node.position = centre
	# The walls-and-gate upgrade wraps the main gate: frame stretched along the wall.
	var frame: Vector3 = site.get("frame", Vector3.ONE)
	site_node.basis = Basis(Vector3.UP, float(site.get("yaw", 0.0))) * Basis.from_scale(frame)
	animate_site(site, progress, now_ms)
	var seconds := now_ms / 1000.0
	var working := progress > DELIVERY_END * 0.5 and progress < 1.0
	for index in builders.size():
		var builder := builders[index]
		builder.visible = true
		if not working:
			pose(builder, 0.0, 0.0)
			continue
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
	if working and last_swing.get("dust", -1) != puff:
		last_swing.dust = puff
		dust.global_position = centre + Vector3(randf_range(-3.0, 3.0), 0.6, randf_range(-3.0, 3.0))
		dust.restart()

static func site_key(site: Dictionary) -> String:
	return "%s|%s|%s|%s" % [site.get("key", ""), site.get("model", ""), site.get("from_model", ""), site.get("to_model", "")]

# The building the city draws on the plot is hidden while its upgrade is rebuilt here.
func hide_building(centre: Vector3) -> void:
	restore_building()
	for child in stage.buildings.get_children():
		var p: Vector3 = (child as Node3D).global_position
		if Vector2(p.x - centre.x, p.z - centre.z).length() < 0.6 and child.visible:
			hidden_building = child
			child.visible = false
			return

func restore_building() -> void:
	if is_instance_valid(hidden_building):
		hidden_building.visible = true
	hidden_building = null

func build_site(site: Dictionary) -> void:
	if not is_instance_valid(site_node):
		site_node = Node3D.new()
		site_node.name = "ConstructionSite"
		add_child(site_node)
	site_signature = site_key(site)
	for node in [site_model, site_from, site_to, site_scaffold, site_props]:
		if is_instance_valid(node):
			node.queue_free()
	site_model = null
	site_from = null
	site_to = null
	reveal_from = []
	reveal_to = []
	site_piles.clear()
	site_frames.clear()
	restore_building()
	site_node.position = site.position
	site_node.basis = Basis.IDENTITY
	var legacy := site.has("frame")
	if not legacy and site.get("upgrade", false) and site.has("to_model"):
		site_from = stage.add_model(site_node, site.from_model, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(site.from_scale)), Vector3.ZERO))
		site_to = stage.add_model(site_node, site.to_model, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(site.to_scale)), Vector3.ZERO))
		reveal_from = BuildReveal.dress(site_from, BuildReveal.LEAVE, BuildReveal.TAKE_DOWN)
		reveal_to = BuildReveal.dress(site_to, BuildReveal.ARRIVE, BuildReveal.RISE)
		hide_building(site.position)
		site_box = model_box(site_to).merge(model_box(site_from))
	elif not legacy and not str(site.get("model", "")).is_empty():
		site_model_path = site.model
		site_model = stage.add_model(site_node, site.model, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(site.get("scale", 1.0))), Vector3.ZERO))
		reveal_to = BuildReveal.dress(site_model, BuildReveal.SCRATCH, BuildReveal.RISE)
		site_box = model_box(site_model)
	else:
		var half := 5.6 if site.get("upgrade", false) else 4.6
		site_box = AABB(Vector3(-half, 0, -half), Vector3(half * 2, 7.4 if site.get("upgrade", false) else 6.4, half * 2))
	# scaffolding hugs the building that rises (not the whole plot)
	var hx := clampf(maxf(absf(site_box.position.x), absf(site_box.end.x)) * 0.82, 2.4, 6.4)
	var hz := clampf(maxf(absf(site_box.position.z), absf(site_box.end.z)) * 0.82, 2.4, 6.4)
	var height := clampf(site_box.end.y * 0.85, 3.2, 9.5)
	if legacy:
		hx = site_box.end.x
		hz = site_box.end.z
		height = site_box.end.y
	# Build 59: the level's own site layout (e.g. the market: scaffolding round the
	# pavilion only, materials on the square clear of the walks).
	var layout: Dictionary = site.get("layout", {}) if not legacy else {}
	var at := Vector3.ZERO
	if layout.has("scaffold"):
		var sc: Array = layout.scaffold
		at = Vector3(float(sc[0]), 0, float(sc[1]))
		hx = float(sc[2])
		hz = float(sc[3])
		height = float(sc[4])
	site_scaffold = build_scaffold(hx, height, hz, bool(layout.get("front_mid", true)))
	site_scaffold.position = at
	site_node.add_child(site_scaffold)
	site_frames.append(site_scaffold as Node3D)
	site_props = Node3D.new()
	site_props.name = "SiteProps"
	site_node.add_child(site_props)
	if not legacy:
		build_props(str(site.get("type", "")), hx, hz, height, layout, at)

func model_box(model: Node3D) -> AABB:
	var box := AABB()
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		var b := (BuildReveal.local_xf(site_node, part)) * part.get_aabb()
		box = b if not box.has_volume() else box.merge(b)
	return box if box.has_volume() else AABB(Vector3(-4, 0, -4), Vector3(8, 6, 8))

# What the hoist lifts: the load that tells which building rises.
static func load_kind(type: String) -> String:
	var base := type
	if type in ["ECO-01", "ECO-02", "ALT-05"]:
		return "crate" if type == "ECO-01" else "sack"
	if type in ["RES-02", "ALT-09", "SUP-03", "SUP-04", "ECO-05"]:
		return "stone"
	if type in ["ECO-03"]:
		return "canvas"
	if type in ["RES-01", "ALT-02"]:
		return "log"
	if type in ["RES-03", "ALT-10", "MIL-04"]:
		return "ore"
	return "planks"

static func prop_material(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.9
	return m

func load_mesh(kind: String) -> Node3D:
	var root := Node3D.new()
	var part := MeshInstance3D.new()
	match kind:
		"crate":
			var b := BoxMesh.new(); b.size = Vector3(0.7, 0.6, 0.7); part.mesh = b
			part.material_override = prop_material(Color("#9a6b3c"))
		"sack":
			var b := CapsuleMesh.new(); b.radius = 0.28; b.height = 0.8; part.mesh = b
			part.material_override = prop_material(Color("#cdb88a"))
		"stone":
			var b := BoxMesh.new(); b.size = Vector3(0.9, 0.55, 0.65); part.mesh = b
			part.material_override = prop_material(Color("#cfc6b4"))
		"canvas":
			var b := BoxMesh.new(); b.size = Vector3(1.8, 0.05, 1.2); part.mesh = b
			part.material_override = prop_material(Color("#e6dcc2"))
			var stripe := MeshInstance3D.new()
			var sb := BoxMesh.new(); sb.size = Vector3(0.36, 0.06, 1.22); stripe.mesh = sb
			stripe.material_override = prop_material(Color("#8c2a2a"))
			for x in [-0.6, 0.0, 0.6]:
				var s2 := stripe.duplicate() as MeshInstance3D
				s2.position.x = x
				root.add_child(s2)
			stripe.free()
		"log":
			var b := CylinderMesh.new(); b.top_radius = 0.18; b.bottom_radius = 0.18; b.height = 2.4; part.mesh = b
			part.rotation.z = PI * 0.5
			part.material_override = prop_material(Color("#7a5634"))
		"ore":
			var b := CylinderMesh.new(); b.top_radius = 0.34; b.bottom_radius = 0.26; b.height = 0.5; part.mesh = b
			part.material_override = prop_material(Color("#5a4632"))
			var heap := MeshInstance3D.new()
			var hb := SphereMesh.new(); hb.radius = 0.3; hb.height = 0.3; heap.mesh = hb
			heap.position.y = 0.25
			heap.material_override = prop_material(Color("#3a3230"))
			root.add_child(heap)
		_:
			var b := BoxMesh.new(); b.size = Vector3(1.6, 0.24, 0.5); part.mesh = b
			part.material_override = prop_material(Color("#b08654"))
	root.add_child(part)
	return root

# Material piles, a hoist with the type's load and a carrier: built once per site.
func build_props(type: String, hx: float, hz: float, height: float, layout: Dictionary = {}, at := Vector3.ZERO) -> void:
	var kind := load_kind(type)
	var front := hz + 1.4
	var pile_at := [Vector3(-hx - 1.4, 0, front - 0.6), Vector3(-hx + 0.4, 0, front + 0.6)]
	if layout.has("piles"):
		pile_at = layout.piles.map(func(p: Array): return Vector3(float(p[0]), 0, float(p[1])))
	for i in 2:
		var pile := Node3D.new()
		pile.position = pile_at[i]
		for k in 3:
			var piece := load_mesh(kind if i == 0 else "planks")
			piece.position = Vector3((k % 2) * 0.5 - 0.25, 0.3 + k * 0.45, (k / 2) * 0.3)
			piece.rotation.y = k * 0.4
			pile.add_child(piece)
		site_props.add_child(pile)
		site_piles.append(pile)
	# hoist: mast at the front-right corner, jib over the scaffolding
	site_hoist = Node3D.new()
	site_hoist.position = at + Vector3(hx + 0.6, 0, hz + 0.6)
	if layout.has("hoist"):
		site_hoist.position = Vector3(float(layout.hoist[0]), 0, float(layout.hoist[1]))
	var mast := MeshInstance3D.new()
	var mm := BoxMesh.new(); mm.size = Vector3(0.22, height + 1.6, 0.22); mast.mesh = mm
	mast.position.y = (height + 1.6) * 0.5
	mast.material_override = timber()
	site_hoist.add_child(mast)
	var jib := MeshInstance3D.new()
	var jm := BoxMesh.new(); jm.size = Vector3(0.18, 0.18, 2.6); jib.mesh = jm
	jib.position = Vector3(0, height + 1.5, -1.1)
	jib.material_override = timber()
	site_hoist.add_child(jib)
	site_hook = MeshInstance3D.new()
	var rope := CylinderMesh.new(); rope.top_radius = 0.025; rope.bottom_radius = 0.025; rope.height = 1.0
	(site_hook as MeshInstance3D).mesh = rope
	(site_hook as MeshInstance3D).material_override = prop_material(Color("#8a6a40"))
	site_hoist.add_child(site_hook)
	site_load = load_mesh(kind)
	site_hoist.add_child(site_load)
	site_hoist.set_meta("top", height + 1.4)
	site_props.add_child(site_hoist)
	if not is_instance_valid(site_carrier):
		site_carrier = make_worker("Worker_Carrier")
	site_carrier.set_meta("from", Vector3(-hx - 1.0, 0, front + 1.6))
	site_carrier.set_meta("to", Vector3(-hx * 0.4, 0, hz + 0.9))
	if layout.has("carrier"):
		var walk: Array = layout.carrier
		site_carrier.set_meta("from", Vector3(float(walk[0][0]), 0, float(walk[0][1])))
		site_carrier.set_meta("to", Vector3(float(walk[1][0]), 0, float(walk[1][1])))

func animate_site(site: Dictionary, progress: float, now_ms: float) -> void:
	var clock := build_clock(progress)
	BuildReveal.set_time(reveal_to, clock)
	BuildReveal.set_time(reveal_from, clock)
	# scaffolding goes up during delivery and comes down at the end
	if is_instance_valid(site_scaffold):
		var up := clampf(progress / DELIVERY_END, 0.0, 1.0)
		var down := clampf((1.0 - progress) / (1.0 - STRIP_START), 0.0, 1.0)
		var h := minf(up, down) if not site.has("frame") else 1.0
		site_scaffold.scale = Vector3(1, maxf(h, 0.001), 1)
		site_scaffold.visible = h > 0.01
	# piles fill during delivery, then are used up as the parts go in
	for pile in site_piles:
		var fill := clampf(progress / (DELIVERY_END * 0.8), 0.0, 1.0) * (1.0 - clock * 0.85)
		pile.scale = Vector3.ONE * maxf(fill, 0.001)
		pile.visible = fill > 0.02
	var seconds := now_ms / 1000.0
	if is_instance_valid(site_hoist):
		var busy := progress > DELIVERY_END and progress < STRIP_START
		site_hoist.visible = progress > DELIVERY_END * 0.5 and progress < 0.97
		var top: float = site_hoist.get_meta("top", 6.0)
		var cycle := fposmod(seconds / 4.2, 1.0) if busy else 0.0
		# hook at the pile, lift, swing over the scaffolding, set down, return
		var lift := smoothstep(0.08, 0.45, cycle) * (1.0 - smoothstep(0.75, 0.95, cycle))
		var reach := -0.3 - 2.0 * smoothstep(0.45, 0.6, cycle) * (1.0 - smoothstep(0.85, 0.98, cycle))
		var y := lerpf(0.35, top - 1.2, lift)
		site_load.position = Vector3(0, y, reach)
		site_load.visible = busy and cycle < 0.72
		site_load.rotation.y = sin(seconds * 0.9) * 0.25
		var rope_len := maxf(top + 0.1 - y - 0.3, 0.1)
		site_hook.position = Vector3(0, y + 0.3 + rope_len * 0.5, reach)
		site_hook.scale = Vector3(1, rope_len, 1)
	if is_instance_valid(site_carrier):
		# the carrier walks between the material pile and the scaffolding
		var carry := progress < STRIP_START + 0.06 and not site.has("frame")
		site_carrier.visible = carry
		if carry:
			var from: Vector3 = site_node.to_global(site_carrier.get_meta("from", Vector3.ZERO))
			var to: Vector3 = site_node.to_global(site_carrier.get_meta("to", Vector3.ZERO))
			var walk := fposmod(seconds / 7.0, 1.0)
			var leg := walk * 2.0 if walk < 0.5 else (1.0 - walk) * 2.0
			var at := from.lerp(to, smoothstep(0.0, 1.0, leg))
			site_carrier.position = stage.ground_point(at)
			var dir := (to - from) if walk < 0.5 else (from - to)
			site_carrier.rotation.y = atan2(dir.x, dir.z)
			var stride := sin(seconds * 9.0)
			pose(site_carrier, -1.2 if walk < 0.5 else stride * 0.4, stride * 0.5)

static func timber() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("#6b4f31")
	material.roughness = 0.92
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material

# Timber scaffolding around a square plot: corner and middle poles, rails on three
# levels, plank decks and a cross brace per side. One mesh (SurfaceTool), so it
# costs a single draw call.
static func build_scaffold(half: float, height: float, half_z := -1.0, front_mid := true) -> MeshInstance3D:
	if half_z < 0.0:
		half_z = half
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
			# a stair or a door in the middle of the front keeps its way clear
			if sx == 0.0 and sz == 1.0 and not front_mid:
				continue
			beam.call(Vector3(sx * half, 0.0, sz * half_z), Vector3(sx * half, height, sz * half_z), 0.18)
	# sides as [corner a, corner b, inward]
	var sides := [[Vector3(-half, 0, half_z), Vector3(half, 0, half_z), Vector3(0, 0, -0.55)],
		[Vector3(half, 0, half_z), Vector3(half, 0, -half_z), Vector3(-0.55, 0, 0)],
		[Vector3(half, 0, -half_z), Vector3(-half, 0, -half_z), Vector3(0, 0, 0.55)],
		[Vector3(-half, 0, -half_z), Vector3(-half, 0, half_z), Vector3(0.55, 0, 0)]]
	# decks and rails on the back and left only: the camera side stays open, so the
	# rising building is seen through the poles
	for level in levels:
		for side in [sides[2], sides[3]]:
			var a: Vector3 = side[0] + Vector3.UP * level
			var b: Vector3 = side[1] + Vector3.UP * level
			beam.call(a, b, 0.17)
			# Plank deck just inside the rail.
			beam.call(a + side[2] - Vector3.UP * 0.12, b + side[2] - Vector3.UP * 0.12, 0.5)
	for level in [levels[2]]:
		for side in [sides[0], sides[1]]:
			beam.call(side[0] + Vector3.UP * level, side[1] + Vector3.UP * level, 0.14)
	for side in sides:
		var a: Vector3 = side[0]
		var b: Vector3 = side[1]
		var out: Vector3 = -side[2].normalized() * 0.05
		beam.call(a + Vector3.UP * 0.2 + out, (a + b) * 0.5 + Vector3.UP * levels[1] + out, 0.14)
		beam.call(b + Vector3.UP * 0.2 + out, (a + b) * 0.5 + Vector3.UP * levels[1] + out, 0.14)
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
