extends RefCounted
## Shared PBR materials for architecture-v2 levels. They reuse the project's own surfaces07
## textures (read-only) with triplanar mapping, so new geometry needs no UV unwrap.

const OUT := "res://assets/city/architecture-v2/materials/"
const SURF := "res://assets/city/premium/surfaces07/"

static func textured(tex: String, tint: Color, scale_value: float, rough := 1.0, normal_strength := 0.6) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(SURF + tex + "-albedo." + ("webp" if tex in ["soil", "path", "drill20", "grass20"] else "jpg"))
	m.albedo_color = tint
	m.normal_enabled = true
	m.normal_texture = load(SURF + tex + "-normal.png")
	m.normal_scale = normal_strength
	m.roughness = rough
	m.roughness_texture = load(SURF + tex + "-roughness.png")
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.uv1_triplanar = true
	m.uv1_triplanar_sharpness = 4.0
	m.uv1_scale = Vector3.ONE * scale_value
	m.vertex_color_use_as_albedo = true
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m

static func flat(color: Color, rough := 0.9, metal := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	m.vertex_color_use_as_albedo = true
	return m

static func glow(color: Color, energy: float) -> StandardMaterial3D:
	var m := flat(color, 0.6)
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = energy
	return m

static func build() -> Dictionary:
	var mats := {
		"oak": textured("oak", Color(0.86, 0.76, 0.68), 0.75),
		"oak_light": textured("oak", Color(1.12, 1.02, 0.9), 0.75),
		"dark_oak": textured("dark_oak", Color(0.82, 0.78, 0.76), 0.75),
		"plank": textured("oak", Color(1.06, 0.95, 0.82), 1.1),
		"log": textured("dark_oak", Color(1.3, 1.12, 0.92), 0.9, 1.0, 0.9),
		"shingle": textured("oak", Color(0.8, 0.74, 0.74), 1.4, 1.0, 0.8),
		"shingle_light": textured("oak", Color(0.98, 0.88, 0.8), 1.4, 1.0, 0.8),
		"slate_roof": textured("slate", Color(0.58, 0.63, 0.68), 1.2, 1.0, 0.8),
		"clay_roof": textured("clay", Color(0.7, 0.58, 0.54), 1.2),
		"plaster": textured("plaster", Color(0.76, 0.71, 0.62), 0.6, 1.0, 0.35),
		"stone": textured("stone", Color(0.78, 0.74, 0.67), 0.55, 1.0, 0.9),
		"stone_light": textured("stone", Color(0.84, 0.79, 0.7), 0.8, 1.0, 0.7),
		"stone_rough": textured("stone", Color(0.84, 0.8, 0.74), 0.35, 1.0, 1.0),
		"earth": textured("soil", Color(0.92, 0.84, 0.72), 0.22, 1.0, 0.5),
		"path": textured("path", Color(0.92, 0.85, 0.74), 0.3, 1.0, 0.5),
		"drill": textured("drill20", Color(1.12, 1.02, 0.86), 0.25, 1.0, 0.5),
		"soil": textured("soil", Color(0.62, 0.48, 0.36), 0.5, 1.0, 0.6),
		"iron": flat(Color(0.16, 0.17, 0.18), 0.5, 0.75),
		"brass": flat(Color(0.62, 0.44, 0.16), 0.45, 0.7),
		"glass": flat(Color(0.07, 0.1, 0.11), 0.25, 0.1),
		"shutter": textured("oak", Color(0.36, 0.5, 0.5), 0.9),
		"canvas": flat(Color(0.84, 0.76, 0.58), 0.95),
		"linen": flat(Color(0.88, 0.86, 0.8), 0.95),
		"cloth_red": flat(Color(0.56, 0.1, 0.08), 0.92),
		"cloth_blue": flat(Color(0.12, 0.24, 0.42), 0.92),
		"rope": flat(Color(0.52, 0.4, 0.24), 0.95),
		"parchment": flat(Color(0.86, 0.78, 0.58), 0.95),
		"map_green": flat(Color(0.42, 0.52, 0.3), 0.95),
		"map_blue": flat(Color(0.3, 0.46, 0.58), 0.9),
		"glow": glow(Color(1.0, 0.72, 0.35), 1.3),
		"ember": glow(Color(0.9, 0.3, 0.06), 1.1),
		"soot": flat(Color(0.06, 0.05, 0.05), 1.0),
		"leaves": flat(Color(0.25, 0.38, 0.14), 0.9),
		"herb": flat(Color(0.32, 0.46, 0.2), 0.9),
		"lavender": flat(Color(0.48, 0.38, 0.62), 0.9),
		"hay": flat(Color(0.74, 0.6, 0.3), 0.95),
		"ore": flat(Color(0.26, 0.22, 0.2), 0.8, 0.3),
		"water": flat(Color(0.18, 0.34, 0.38), 0.15, 0.0),
		"greenglass": flat(Color(0.2, 0.3, 0.29), 0.08, 0.45),
		"sand": textured("soil", Color(1.08, 0.97, 0.78), 0.3, 1.0, 0.4),
		"flower": flat(Color(0.86, 0.82, 0.7), 0.9),
	}
	for key in mats:
		ResourceSaver.save(mats[key], OUT + key + ".tres")
	return mats
