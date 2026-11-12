extends RefCounted

static var contact_material: StandardMaterial3D

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
