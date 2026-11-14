shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled;

// Dust puff at the feet: a soft, lumpy cloud that swells and thins. Camera-facing.
uniform vec4 tint : source_color = vec4(0.72, 0.62, 0.46, 0.55);
uniform float progress = 0.0;
uniform float size = 1.4;
uniform float seed = 0.0;

void vertex() {
	VERTEX.xy *= size * vec2(1.6, 0.9);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float a = atan(p.y, p.x);
	// Lumpy outline: a few lobes turned by the seed.
	float lobes = 0.82 + 0.12 * sin(a * 3.0 + seed * 6.28) + 0.08 * sin(a * 5.0 - seed * 4.1);
	float r = length(p) / lobes;
	float cloud = 1.0 - smoothstep(0.35, 1.0, r);
	float thin = (1.0 - progress) * smoothstep(0.0, 0.15, progress);
	ALBEDO = tint.rgb * (0.85 + 0.15 * (1.0 - r));
	ALPHA = tint.a * cloud * thin;
}
