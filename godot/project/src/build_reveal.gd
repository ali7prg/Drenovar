extends RefCounted

# Construction / upgrade reveal (build 54): dresses a building level scene in
# build_reveal.gdshader materials that follow one build clock (0..1, the order's
# progress). Level scenes from the architecture kit carry the order of their parts
# (vertex colour alpha: from scratch; UV2: upgrade in / out); other models rise or
# come down with their height.

const SHADER := preload("res://src/build_reveal.gdshader")
const SCRATCH := 0
const ARRIVE := 1
const LEAVE := 2
const RISE := 3
const TAKE_DOWN := 4

static func has_build_data(mesh: Mesh) -> bool:
	return mesh is ArrayMesh and mesh.get_surface_count() > 0 \
		and (mesh.surface_get_format(0) & Mesh.ARRAY_FORMAT_TEX_UV2) != 0 \
		and (mesh.surface_get_format(0) & Mesh.ARRAY_FORMAT_COLOR) != 0

static func reveal_material(source: Material, mode: int, top: float) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SHADER
	m.set_shader_parameter("build_mode", mode)
	m.set_shader_parameter("build_top", top)
	if source is BaseMaterial3D:
		var b := source as BaseMaterial3D
		m.set_shader_parameter("albedo", b.albedo_color)
		m.set_shader_parameter("use_albedo_tex", b.albedo_texture != null)
		if b.albedo_texture != null:
			m.set_shader_parameter("tex_albedo", b.albedo_texture)
		m.set_shader_parameter("use_normal", b.normal_enabled and b.normal_texture != null)
		if b.normal_texture != null:
			m.set_shader_parameter("tex_normal", b.normal_texture)
		m.set_shader_parameter("normal_scale", b.normal_scale)
		m.set_shader_parameter("use_rough", b.roughness_texture != null)
		if b.roughness_texture != null:
			m.set_shader_parameter("tex_rough", b.roughness_texture)
		m.set_shader_parameter("roughness", b.roughness)
		m.set_shader_parameter("metallic", b.metallic)
		m.set_shader_parameter("triplanar", b.uv1_triplanar)
		m.set_shader_parameter("uv_scale", b.uv1_scale)
		m.set_shader_parameter("use_vertex_color", b.vertex_color_use_as_albedo)
		if b.emission_enabled:
			m.set_shader_parameter("emission_color", b.emission)
			m.set_shader_parameter("emission_energy", b.emission_energy_multiplier)
		if b.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
			m.set_shader_parameter("alpha_cut", b.alpha_scissor_threshold)
	return m

static func local_xf(root: Node3D, part: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var n: Node = part
	while n != null and n != root:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t

static func scene_top(root: Node3D) -> float:
	var top := 1.0
	for part: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if part.mesh != null:
			top = maxf(top, (local_xf(root, part) * part.get_aabb()).end.y)
	return top

## Dresses every mesh of root; returns the materials to drive with set_time().
static func dress(root: Node3D, data_mode: int, plain_mode: int) -> Array:
	var materials: Array = []
	var top := scene_top(root)
	for part: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null:
			continue
		var mode := data_mode if has_build_data(part.mesh) else plain_mode
		# local height of this part in the scene, for the height-driven modes
		var part_top := top / maxf(local_xf(root, part).basis.get_scale().y, 0.001)
		for index in part.mesh.get_surface_count():
			var m := reveal_material(part.get_active_material(index), mode, part_top)
			part.set_surface_override_material(index, m)
			materials.append(m)
		part.material_override = null
		part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return materials

static func set_time(materials: Array, t: float) -> void:
	for m: ShaderMaterial in materials:
		m.set_shader_parameter("build_t", t)
