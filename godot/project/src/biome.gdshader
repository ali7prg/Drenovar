shader_type spatial;

uniform sampler2D grass : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D earth : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D roughness_texture : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_roughness : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_roughness : filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool settlement = false;
varying vec3 terrain_position;
varying vec3 terrain_normal;

float hash2(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash2(i), hash2(i + vec2(1.0, 0.0)), u.x), mix(hash2(i + vec2(0.0, 1.0)), hash2(i + vec2(1.0, 1.0)), u.x), u.y);
}

// Breaks the uniformly tiled lawn into lusher and drier patches (world space, so it never
// repeats with the texture) and takes the edge off the saturation. Two cheap noise taps.
vec3 meadow_variation(vec3 grass_color, vec2 world) {
	float n = value_noise(world * 0.035) * 0.65 + value_noise(world * 0.12 + 17.0) * 0.35;
	vec3 lush = vec3(0.84, 0.94, 0.80);
	vec3 dry = vec3(1.10, 1.01, 0.76);
	vec3 varied = grass_color * mix(lush, dry, smoothstep(0.3, 0.75, n));
	float luma = dot(varied, vec3(0.3, 0.59, 0.11));
	return mix(vec3(luma), varied, 0.78) * 0.94;
}

void vertex() {
	terrain_position = VERTEX;
	terrain_normal = NORMAL;
}

void fragment() {
	vec3 land = meadow_variation(texture(grass, UV).rgb, terrain_position.xz);
	if (settlement) {
		land = mix(land, texture(earth, UV).rgb, UV2.x);
		land = mix(land, texture(rock, UV).rgb, UV2.y);
	} else {
		vec3 axis = pow(abs(normalize(terrain_normal)), vec3(4.0));
		axis /= max(0.001, axis.x + axis.y + axis.z);
		vec3 stone = texture(rock, terrain_position.yz / 5.0).rgb * axis.x
			+ texture(rock, terrain_position.xz / 5.0).rgb * axis.y
			+ texture(rock, terrain_position.xy / 5.0).rgb * axis.z;
		vec3 tint = vec3(0.96 + 0.045 * sin(terrain_position.x * 0.19 + sin(terrain_position.z * 0.11)), 0.985, 0.96);
		land = mix(land * tint, texture(earth, UV * 0.85).rgb, UV2.x * 0.8);
		land = mix(land, stone, UV2.y);
		land = mix(land, vec3(0.79, 0.82, 0.8), clamp((terrain_position.y - 25.0) / 4.0, 0.0, 1.0));
	}
	ALBEDO = land * COLOR.rgb;
	NORMAL_MAP = texture(normal_texture, UV).rgb;
	NORMAL_MAP_DEPTH = settlement ? 0.51 : 0.24;
	ROUGHNESS = texture(roughness_texture, UV).r;
	if (settlement) {
		vec3 detail = mix(NORMAL_MAP * 2.0 - 1.0, texture(soil_normal, UV).rgb * 2.0 - 1.0, UV2.x);
		detail = mix(detail, texture(stone_normal, UV).rgb * 2.0 - 1.0, UV2.y);
		NORMAL_MAP = normalize(detail) * 0.5 + 0.5;
		ROUGHNESS = mix(ROUGHNESS, texture(soil_roughness, UV).r, UV2.x);
		ROUGHNESS = mix(ROUGHNESS, texture(stone_roughness, UV).r, UV2.y);
	}
}
