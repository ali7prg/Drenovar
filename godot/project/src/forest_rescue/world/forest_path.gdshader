shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;

// Dirt path ribbons along the 13 atlas routes. Same surface maps as the city streets
// (surfaces07/path-*), world-space UV, soft broken edges (COLOR.a = 1 centre … 0 fringe).

uniform sampler2D path_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D path_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D path_roughness : filter_linear_mipmap, repeat_enable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
// art/01 trails: light-tan dirt (#caa270 mean, #b89261..#dcb37f) with soft grassy edges.
uniform vec3 tint : source_color = vec3(1.17, 1.05, 0.90);
uniform vec3 grass_edge : source_color = vec3(0.55, 0.58, 0.33);
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
	// Centre worn lighter, edges grow over with grass tufts (noise-broken), then fade out.
	float grassy = 1.0 - smoothstep(0.35, 0.85, edge + (n.r - 0.5) * 0.35);
	vec3 dirt = base * (0.92 + 0.22 * worn) * COLOR.rgb;
	ALBEDO = mix(dirt, grass_edge * (0.85 + 0.3 * n.b), grassy * 0.75);
	NORMAL_MAP = texture(path_normal, uv).rgb;
	ROUGHNESS = texture(path_roughness, uv).r;
	ALPHA = smoothstep(0.12, 0.5, edge) * 0.97;
}
