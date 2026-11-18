shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;

// Dirt path ribbons along the 13 atlas routes. Same surface maps as the city streets
// (surfaces07/path-*), world-space UV, soft broken edges (COLOR.a = 1 centre … 0 fringe).

uniform sampler2D path_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D path_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D path_roughness : filter_linear_mipmap, repeat_enable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 tint : source_color = vec3(1.04, 0.97, 0.86);
uniform float uv_scale = 0.35;

varying vec3 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = world.xz * uv_scale;
	vec3 base = texture(path_albedo, uv).rgb * tint;
	vec4 n = texture(noise_tex, world.xz / 5.5);
	float edge = COLOR.a + (n.g - 0.5) * 0.55 + (n.b - 0.5) * 0.25;
	float worn = texture(noise_tex, world.xz / 2.3).r;
	ALBEDO = base * (0.9 + 0.2 * worn) * COLOR.rgb;
	NORMAL_MAP = texture(path_normal, uv).rgb;
	ROUGHNESS = texture(path_roughness, uv).r;
	ALPHA = smoothstep(0.18, 0.62, edge) * 0.97;
}
