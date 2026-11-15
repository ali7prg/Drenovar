shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

// Impact flash: a hot core and radial rays that expand and fade. Camera-facing.
uniform vec4 tint : source_color = vec4(1.0, 0.7, 0.3, 1.0);
uniform float progress = 0.0;
uniform float size = 1.4;
uniform float seed = 0.0;

void vertex() {
	VERTEX.xy *= size * (0.6 + progress * 0.8);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float a = atan(p.y, p.x);
	float rays = pow(abs(sin(a * 4.0 + seed * 6.28)), 18.0) + pow(abs(sin(a * 7.0 + seed * 3.1)), 30.0) * 0.6;
	float reach = mix(0.25, 1.0, progress);
	float ray = rays * (1.0 - smoothstep(reach * 0.4, reach, r)) * smoothstep(0.02, 0.1, r);
	float core = exp(-r * r * 30.0) * (1.0 - progress);
	float fade = 1.0 - progress;
	ALBEDO = (tint.rgb * ray * 1.4 + vec3(1.0, 0.95, 0.85) * core * 2.0) * fade;
}
