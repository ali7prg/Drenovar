shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_test_disabled, depth_draw_never, shadows_disabled;

// Health bar facing the camera: dark frame, fill (with the recent loss in pale red).
uniform float ratio = 1.0;
uniform float recent = 1.0;
uniform vec4 fill : source_color = vec4(0.82, 0.2, 0.16, 1.0);
uniform vec2 size = vec2(2.6, 0.26);

void vertex() {
	VERTEX.xy *= size;
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}

void fragment() {
	vec2 uv = UV;
	float border = step(uv.x, 0.02) + step(0.98, uv.x) + step(uv.y, 0.12) + step(0.88, uv.y);
	vec3 colour = vec3(0.06, 0.05, 0.04);
	if (border < 0.5) {
		if (uv.x < ratio) {
			colour = fill.rgb * (0.85 + 0.3 * (1.0 - uv.y));
		} else if (uv.x < recent) {
			colour = vec3(0.95, 0.75, 0.6);
		} else {
			colour = vec3(0.16, 0.13, 0.11);
		}
	} else {
		colour = vec3(0.93, 0.8, 0.52) * 0.8;
	}
	ALBEDO = colour;
	ALPHA = 0.95;
}
