// creatures-v2: one material per species/level/LOD atlas. Levels share every texture; their look
// (tints in the variant-mask regions, rune/vein/seam emission) comes from these uniforms only.
// Same formula as godot/art/creatures-v2/export.py:level_textures (used for the per-level web files).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D emission_tex : source_color, hint_default_black, filter_linear_mipmap, repeat_disable;
uniform sampler2D variant_tex : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform vec4 tint_r = vec4(1.0, 1.0, 1.0, 0.0); // rgb (sRGB) + weight
uniform vec4 tint_g = vec4(1.0, 1.0, 1.0, 0.0);
uniform vec4 tint_b = vec4(1.0, 1.0, 1.0, 0.0);
uniform vec3 emission_color : source_color = vec3(0.33, 0.84, 0.46);
uniform float emission_strength = 1.0;
uniform vec3 emit_masks = vec3(0.0); // emission added in the R, G, B mask regions
uniform float normal_strength = 1.0;
// Per instance: 1 alive, fades to 0 over the death clip (runes, veins and seams go out).
instance uniform float life = 1.0;

vec3 to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void fragment() {
	vec3 base = texture(albedo_tex, UV).rgb;
	vec4 m = texture(variant_tex, UV);
	float l = clamp(dot(base, vec3(0.2126, 0.7152, 0.0722)) / 0.18, 0.35, 1.6);
	base = mix(base, to_linear(tint_r.rgb) * l, m.r * tint_r.a);
	base = mix(base, to_linear(tint_g.rgb) * l, m.g * tint_g.a);
	base = mix(base, to_linear(tint_b.rgb) * l, m.b * tint_b.a);
	ALBEDO = base;
	vec3 orm = texture(orm_tex, UV).rgb;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.65;
	ROUGHNESS = orm.g;
	METALLIC = orm.b;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	vec3 glow = texture(emission_tex, UV).rgb * emission_strength;
	glow += emission_color * (m.r * emit_masks.x + m.g * emit_masks.y + m.b * emit_masks.z);
	EMISSION = glow * life;
}
