shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled;

// «Лес потерянных» waterfall (atlas v2, art/01: the fall from the limestone outcrop into the lily
// pond below the arena). A curtain mesh built by ForestWater: UV.x across (0..1), UV.y down the
// fall (0 lip .. 1 pool). Painted white-teal streaks racing down, a glassy lip, a foamy foot;
// soft broken side edges. COLOR.a fades the curtain at its sides.

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 water_color : source_color = vec3(0.24, 0.43, 0.48);
uniform vec3 streak_color : source_color = vec3(0.90, 0.95, 0.95);
uniform vec3 foam_color : source_color = vec3(0.96, 0.98, 0.97);
uniform float speed = 1.6;
uniform float width_m = 2.4;
uniform float height_m = 5.0;
uniform bool foam_only = false;     // the foam band on a ledge (a quad, no fall)

void fragment() {
	vec2 uv = UV;
	float t = TIME * speed;
	float across = uv.x * width_m;
	float down = uv.y * height_m;
	if (foam_only) {
		vec2 p = UV * 2.0 - 1.0;
		float fn0 = texture(noise_tex, vec2(across / 0.8 + t * 0.05, (down + t * 0.4) / 0.9)).b;
		float body = (1.0 - smoothstep(0.55, 1.0, abs(p.x))) * (1.0 - smoothstep(0.3, 1.0, abs(p.y)));
		ALBEDO = foam_color;
		ALPHA = clamp(body * (0.55 + 0.5 * fn0), 0.0, 0.92);
	} else {
	// vertical streaks (painted look): broad white ribbons with teal gaps, racing down
	float s1 = texture(noise_tex, vec2(across / 1.1, (down - t * 2.2) / 4.5)).r;
	float s2 = texture(noise_tex, vec2(across / 0.5 + 0.37, (down - t * 2.9) / 2.2)).g;
	float streak = smoothstep(0.42, 0.66, s1 * 0.6 + s2 * 0.5);
	vec3 col = mix(water_color, streak_color, 0.12 + 0.86 * streak);
	// glassy darker lip at the top, whiter and broken towards the foot
	col = mix(col * 0.86, col, smoothstep(0.0, 0.18, uv.y));
	float foot = smoothstep(0.62, 1.0, uv.y);
	float fn = texture(noise_tex, vec2(across / 0.7, (down - t * 1.2) / 1.1)).b;
	col = mix(col, foam_color, clamp(foot * (0.55 + 0.6 * fn), 0.0, 0.95));
	float side = COLOR.a;
	float edge_noise = texture(noise_tex, vec2(uv.x * 2.0, (down - t * 2.0) / 2.6)).r;
	float alpha = smoothstep(0.0, 0.35, side + (edge_noise - 0.5) * 0.35);
	alpha *= 0.78 + 0.2 * streak;
	alpha *= smoothstep(0.0, 0.04, uv.y) * 0.9 + 0.1;
	ALBEDO = col;
	ALPHA = clamp(alpha, 0.0, 0.96);
	}
}
