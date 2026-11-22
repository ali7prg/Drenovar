extends RefCounted

static var contact_material: StandardMaterial3D
static var reflection_skies := {}

static func add_reflections(env: Environment, horizon: Color) -> void:
	"""Static procedural sky used only for specular reflections (background and ambient
	light stay as they were). Shared per horizon colour, so the radiance map is built once."""
	var key := horizon.to_html()
	if not reflection_skies.has(key):
		var material := ProceduralSkyMaterial.new()
		material.sky_top_color = Color("#6f8fae")
		material.sky_horizon_color = horizon.lightened(0.25)
		material.ground_horizon_color = horizon.darkened(0.15)
		material.ground_bottom_color = Color("#3b3a31")
		material.sun_angle_max = 30.0
		var sky := Sky.new()
		sky.sky_material = material
		sky.radiance_size = Sky.RADIANCE_SIZE_128
		sky.process_mode = Sky.PROCESS_MODE_QUALITY
		reflection_skies[key] = sky
	env.sky = reflection_skies[key]
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY

static func prepare(actor: Node3D) -> void:
	for part: MeshInstance3D in actor.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		for surface in part.mesh.get_surface_count():
			var material := part.get_active_material(surface) as BaseMaterial3D
			if material == null or material.has_meta("drenovar_warrior_surface"):
				continue
			material.set_meta("drenovar_warrior_surface", true)
			material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
			var name := material.resource_name.to_lower()
			if name.contains("eye"):
				material.metallic = 0.0
				material.metallic_specular = 0.44
			elif has_part(name, ["skin", "_head", "horsecoat", "horsehair", "beard"]):
				material.metallic_specular = 0.28
				material.roughness = maxf(material.roughness, 0.85)
				material.clearcoat_enabled = false
			elif has_part(name, ["cloth", "wool", "linen", "pants", "glove", "leather", "boot", "thread", "wood", "shieldpaint"]):
				material.metallic = 0.0
				material.metallic_specular = 0.32
				material.roughness = maxf(material.roughness, 0.9)
				material.clearcoat_enabled = false
			elif has_part(name, ["steel", "iron", "mail", "brass", "gold", "sword", "edge"]):
				material.metallic_specular = 0.52
				material.roughness = maxf(material.roughness, 0.63)

static func has_part(name: String, parts: Array[String]) -> bool:
	for part in parts:
		if part in name:
			return true
	return false

static func ground_shadow(parent: Node3D, bounds: AABB) -> void:
	if contact_material == null:
		var fade := Gradient.new()
		fade.colors = PackedColorArray([Color("#080c0ba1"), Color("#080c0b00")])
		var texture := GradientTexture2D.new()
		texture.gradient = fade
		texture.width = 64
		texture.height = 64
		texture.fill = GradientTexture2D.FILL_RADIAL
		texture.fill_from = Vector2(0.5, 0.5)
		texture.fill_to = Vector2(1.0, 0.5)
		contact_material = StandardMaterial3D.new()
		contact_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		contact_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		contact_material.albedo_texture = texture
	var plane := PlaneMesh.new()
	plane.size = Vector2(maxf(bounds.size.x * 0.9, 0.8), maxf(bounds.size.z * 1.05, 0.75))
	var shadow := MeshInstance3D.new()
	shadow.mesh = plane
	shadow.material_override = contact_material
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	shadow.position = Vector3(bounds.get_center().x, bounds.position.y - 0.01, bounds.get_center().z)
	parent.add_child(shadow)


# Stone display pedestal under a recruitment preview: a worn top slab on a wider
# plinth, stone-textured, top surface just under the unit's feet.
static func pedestal(parent: Node3D, bounds: AABB, stone: Texture2D) -> AABB:
	var radius := maxf(0.5, minf(bounds.size.x, bounds.size.z) * 0.95)
	var material := StandardMaterial3D.new()
	material.albedo_texture = stone
	material.albedo_color = Color("#857d70")
	material.roughness = 0.88
	material.uv1_triplanar = true
	material.uv1_scale = Vector3.ONE * 1.6
	var feet := bounds.position.y - 0.02
	var parts := [[radius, radius * 1.04, 0.16, feet - 0.08], [radius * 1.12, radius * 1.16, 0.12, feet - 0.22]]
	for part in parts:
		var cylinder := CylinderMesh.new()
		cylinder.top_radius = part[0]
		cylinder.bottom_radius = part[1]
		cylinder.height = part[2]
		cylinder.radial_segments = 40
		cylinder.rings = 1
		var slab := MeshInstance3D.new()
		slab.mesh = cylinder
		slab.material_override = material
		slab.position = Vector3(bounds.get_center().x, part[3], bounds.get_center().z)
		parent.add_child(slab)
	var grown := bounds
	grown.position.y = feet - 0.28
	grown.size.y += 0.28
	return grown
