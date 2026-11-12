shader_type spatial;
render_mode cull_disabled;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float sway = sin(TIME * 1.7 + origin.x * 0.23 + origin.z * 0.37);
	VERTEX.x += sway * VERTEX.y * VERTEX.y * 0.2;
}

void fragment() {
	ALBEDO = COLOR.rgb;
	ROUGHNESS = 1.0;
}
