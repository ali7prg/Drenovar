extends Node
## Bounded, pooled, non-blocking reward effects: gold sparkles in the world on discovery and
## award, a sparkle burst on the reward strip, icons flying to the wallet after a claim,
## soft glows over revealed artifacts. Nothing here waits for the network or gates input.

const WORLD_POOL := 6
const HUD_POOL := 3
const FLYER_POOL := 20
const MAX_GLOWS := 4

var game: Node
var world_pool: Array[CPUParticles3D] = []
var world_next := 0
var hud_pool: Array[CPUParticles2D] = []
var hud_next := 0
var flyers: Array[TextureRect] = []
var glows: Dictionary = {}
var spark_texture: Texture2D
var spark_material: StandardMaterial3D
var hud_layer: Control
var world_parent: Node3D

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "RewardFx"
	var gradient := Gradient.new()
	gradient.set_color(0, Color(1, 0.95, 0.75, 1))
	gradient.set_color(1, Color(1, 0.7, 0.2, 0))
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(0.5, 0.0)
	texture.width = 32
	texture.height = 32
	spark_texture = texture
	spark_material = StandardMaterial3D.new()
	spark_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spark_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	spark_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	spark_material.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	spark_material.vertex_color_use_as_albedo = true
	spark_material.albedo_texture = spark_texture
	hud_layer = Control.new()
	hud_layer.name = "RewardFxLayer"
	hud_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	game.hud.add_child(hud_layer)
	for i in HUD_POOL:
		var burst := CPUParticles2D.new()
		burst.emitting = false
		burst.one_shot = true
		burst.amount = 28
		burst.lifetime = 0.9
		burst.explosiveness = 0.85
		burst.texture = spark_texture
		burst.direction = Vector2(0, -1)
		burst.spread = 180.0
		burst.initial_velocity_min = 60.0
		burst.initial_velocity_max = 170.0
		burst.gravity = Vector2(0, 120)
		burst.scale_amount_min = 0.35
		burst.scale_amount_max = 0.8
		burst.color = Color(1.0, 0.85, 0.45)
		hud_layer.add_child(burst)
		hud_pool.append(burst)
	for i in FLYER_POOL:
		var icon := TextureRect.new()
		icon.custom_minimum_size = Vector2(26, 26)
		icon.size = Vector2(26, 26)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon.hide()
		hud_layer.add_child(icon)
		flyers.append(icon)

func ensure_world() -> bool:
	var parent: Node3D = game.actors_root()
	if parent == null:
		return false
	if parent != world_parent or world_pool.is_empty() or not is_instance_valid(world_pool[0]):
		world_parent = parent
		world_pool.clear()
		glows.clear()
		for i in WORLD_POOL:
			var burst := CPUParticles3D.new()
			burst.name = "RewardSpark%d" % i
			burst.emitting = false
			burst.one_shot = true
			burst.amount = 36
			burst.lifetime = 1.1
			burst.explosiveness = 0.8
			burst.direction = Vector3.UP
			burst.spread = 55.0
			burst.initial_velocity_min = 2.0
			burst.initial_velocity_max = 5.5
			burst.gravity = Vector3(0, -4.0, 0)
			burst.scale_amount_min = 0.25
			burst.scale_amount_max = 0.6
			burst.color = Color(1.0, 0.86, 0.45)
			var quad := QuadMesh.new()
			quad.size = Vector2(0.6, 0.6)
			quad.material = spark_material
			burst.mesh = quad
			burst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			parent.add_child(burst)
			world_pool.append(burst)
	return true

func burst_world(p: Vector3, kind := "award") -> void:
	if p == Vector3.INF or not ensure_world():
		return
	var burst := world_pool[world_next % WORLD_POOL]
	world_next += 1
	burst.position = p + Vector3.UP * 0.8
	burst.color = {"award":Color(1.0, 0.86, 0.45), "discovery":Color(0.75, 1.0, 0.6), "socket":Color(1.0, 0.95, 0.7), "hit":Color(1.0, 0.6, 0.4)}.get(kind, Color(1, 0.86, 0.45))
	burst.amount = 14 if kind == "hit" else 36
	burst.restart()
	burst.emitting = true

func glow_world(id: String, p: Vector3) -> void:
	if not ensure_world():
		return
	var glow: Node3D = glows.get(id)
	if p == Vector3.INF:
		if glow != null and is_instance_valid(glow):
			glow.hide()
		return
	if glow == null or not is_instance_valid(glow):
		if glows.size() >= MAX_GLOWS:
			for key in glows.keys():
				if not is_instance_valid(glows[key]) or not glows[key].visible:
					if is_instance_valid(glows[key]):
						glows[key].queue_free()
					glows.erase(key)
					break
		if glows.size() >= MAX_GLOWS:
			return
		var sprite := MeshInstance3D.new()
		var quad := QuadMesh.new()
		quad.size = Vector2(2.4, 2.4)
		var material := spark_material.duplicate() as StandardMaterial3D
		material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		material.albedo_color = Color(1.0, 0.85, 0.45, 0.8)
		quad.material = material
		sprite.mesh = quad
		sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		world_parent.add_child(sprite)
		glows[id] = sprite
		glow = sprite
	glow.show()
	glow.position = p
	var pulse := 0.85 + 0.25 * sin(Time.get_ticks_msec() / 230.0)
	# Sized for the overview zoom; shrinks up close so the artifact itself stays readable.
	var zoom := float(game.stage.camera_zoom) if is_instance_valid(game.stage) else 40.0
	glow.scale = Vector3.ONE * pulse * clampf(zoom / 42.0, 0.3, 1.2)

## Task reward entered the reserve: sparkles at the squad and on the reward strip.
func award(_resources: Dictionary, world_position: Vector3) -> void:
	burst_world(world_position, "award")
	burst_hud(game.hud.strip_center())

func burst_hud(at: Vector2) -> void:
	if at == Vector2.ZERO:
		return
	var burst := hud_pool[hud_next % HUD_POOL]
	hud_next += 1
	burst.position = at
	burst.restart()
	burst.emitting = true

## Claimed resources fly from the reward strip to the real wallet counters.
func fly_to_wallet(resources: Dictionary) -> void:
	var origin: Vector2 = game.hud.strip_center()
	if origin == Vector2.ZERO or not game.hud.bar.visible:
		origin = hud_layer.get_viewport_rect().size * Vector2(0.3, 0.55)
	var used := 0
	for key in ["food", "wood", "stone", "iron", "coins"]:
		if int(resources.get(key, 0)) <= 0:
			continue
		var target_button: Control = game.main.resource_buttons.get(key)
		if target_button == null:
			continue
		var destination := target_button.get_global_rect().get_center() - Vector2(13, 13)
		for i in 4:
			if used >= FLYER_POOL:
				return
			var icon := flyers[used]
			used += 1
			icon.texture = game.main.resource_icons.get(key)
			icon.position = origin + Vector2(randf_range(-40, 40), randf_range(-12, 12))
			icon.modulate.a = 1.0
			icon.show()
			var tween := create_tween()
			var delay := 0.06 * i
			tween.tween_interval(delay)
			tween.tween_property(icon, "position", destination, 0.75).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
			tween.parallel().tween_property(icon, "modulate:a", 0.2, 0.75).set_delay(delay + 0.4)
			tween.tween_callback(icon.hide)
	burst_hud(origin)
