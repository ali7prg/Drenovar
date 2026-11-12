shader_type spatial;
render_mode cull_disabled;

uniform vec4 water_color : source_color = vec4(0.19, 0.43, 0.46, 1.0);
varying vec2 water_position;

void vertex() {
	water_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
	vec2 p = water_position;
	float broad = sin(dot(p, vec2(0.42, 0.23)) + TIME * 0.7);
	float fine = sin(dot(p, vec2(-0.61, 0.89)) - TIME * 1.15 + broad * 0.55);
	vec3 ripple = mat3(VIEW_MATRIX) * vec3(0.075 * broad, 0.0, 0.06 * fine);
	NORMAL = normalize(NORMAL + ripple);
	float edge = pow(1.0 - clamp(abs(dot(NORMAL, VIEW)), 0.0, 1.0), 3.0);
	ALBEDO = mix(water_color.rgb * (0.95 + fine * 0.04), vec3(0.22, 0.35, 0.37), edge * 0.36);
	ROUGHNESS = 0.29 + 0.04 * broad;
	SPECULAR = 0.52;
}
