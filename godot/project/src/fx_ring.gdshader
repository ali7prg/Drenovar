shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled;

// Battle area on the ground: soft translucent disc, bright rim and a slow pulse.
uniform vec4 tint : source_color = vec4(0.36, 0.9, 0.45, 1.0);
uniform float strength = 1.0;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float rim = smoothstep(0.86, 0.95, r) * (1.0 - smoothstep(0.95, 1.0, r));
	float fill = (1.0 - smoothstep(0.7, 1.0, r)) * 0.16;
	float pulse = 0.75 + 0.25 * sin(TIME * 3.0 - r * 6.0);
	ALBEDO = tint.rgb;
	ALPHA = clamp((rim * 0.85 + fill) * pulse * strength, 0.0, 1.0);
}
