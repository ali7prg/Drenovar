shader_type spatial;
render_mode cull_disabled;

// Depth-tinted water with moving ripples and shore foam.
// Depth is approximated from the distance to the shore (no screen depth copy, which
// is costly on the mobile renderer); the city river strip uses its distance to the banks (UV2.x).

uniform vec4 water_color : source_color = vec4(0.19, 0.43, 0.46, 1.0);
uniform vec4 deep_color : source_color = vec4(0.07, 0.15, 0.19, 1.0);
uniform vec4 shallow_color : source_color = vec4(0.2, 0.29, 0.26, 1.0);
uniform vec4 foam_color : source_color = vec4(0.82, 0.86, 0.84, 1.0);
// World map: metres from the nearest shore (precomputed, 0..12.75 m in 8 bits).
uniform sampler2D shore_map : filter_linear, repeat_disable;
uniform bool use_shore_map = false;
uniform vec2 height_origin = vec2(-150.0, -120.0);
uniform vec2 height_extent = vec2(300.0, 240.0);
uniform float strip_depth = 2.4;
varying vec2 water_position;

float hash2(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash2(i), hash2(i + vec2(1.0, 0.0)), u.x), mix(hash2(i + vec2(0.0, 1.0)), hash2(i + vec2(1.0, 1.0)), u.x), u.y);
}

void vertex() {
	water_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
	vec2 p = water_position;
	float depth;
	if (use_shore_map) {
		float shore = texture(shore_map, (p - height_origin) / height_extent).r * 12.75;
		depth = max(0.0, shore - 0.5) * 0.95;
	} else {
		depth = (1.0 - abs(UV2.x * 2.0 - 1.0)) * strip_depth;
	}
	// Four directional waves: cheap analytic slopes, no normal texture fetch.
	float t = TIME;
	vec2 slope = vec2(0.0);
	vec2 d1 = vec2(0.42, 0.23); float w1 = dot(p, d1) * 1.0 + t * 0.9;
	vec2 d2 = vec2(-0.61, 0.89); float w2 = dot(p, d2) * 0.8 - t * 1.2;
	vec2 d3 = vec2(0.93, -0.37); float w3 = dot(p, d3) * 2.3 + t * 1.7;
	vec2 d4 = vec2(-0.27, -0.96); float w4 = dot(p, d4) * 3.1 + t * 2.1;
	slope += d1 * cos(w1) * 0.06 + d2 * cos(w2) * 0.05 + d3 * cos(w3) * 0.035 + d4 * cos(w4) * 0.025;
	vec3 ripple = mat3(VIEW_MATRIX) * vec3(-slope.x, 0.0, -slope.y);
	NORMAL = normalize(NORMAL + ripple);
	float shallow = 1.0 - smoothstep(0.0, 2.6, depth);
	vec3 body = mix(deep_color.rgb, shallow_color.rgb, shallow * shallow);
	// Keep a little of the per-scene tint so city and world waters stay distinct.
	body = mix(body, water_color.rgb * 0.55, 0.18);
	// Broken foam line along the shore, drifting slowly.
	float foam_noise = value_noise(p * 1.7 + vec2(t * 0.25, -t * 0.18)) * 0.6 + value_noise(p * 4.3 - t * 0.4) * 0.4;
	float foam_band = 1.0 - smoothstep(0.0, 0.32, depth);
	float foam = smoothstep(0.45, 0.75, foam_noise + foam_band * 0.55) * foam_band;
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = mix(body, foam_color.rgb, foam * 0.55);
	ROUGHNESS = mix(0.12, 0.6, foam);
	SPECULAR = 0.5;
	EMISSION = vec3(0.05, 0.07, 0.08) * fresnel * (1.0 - foam);
}
