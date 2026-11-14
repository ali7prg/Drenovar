shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, depth_test_disabled, shadows_disabled;

// March route on the ground: light arrow chevrons flowing toward the destination,
// drawn only over the part of the route still ahead of the army. UV.x is metres
// along the route, UV.y runs 0..1 across the ribbon.
uniform vec4 tint : source_color = vec4(0.97, 0.95, 0.88, 0.92);
uniform float from_m = 0.0;
uniform float to_m = 100000.0;
uniform float spacing = 1.7;
uniform float flow = 1.5;

void fragment() {
	float d = UV.x;
	if (d < from_m || d > to_m) {
		discard;
	}
	float across = abs(UV.y * 2.0 - 1.0);
	float cell = fract((d - TIME * flow) / spacing);
	// A ">" pointing along the route: the centre runs ahead of the edges.
	float chevron = cell + across * 0.36;
	float body = smoothstep(0.30, 0.35, chevron) * (1.0 - smoothstep(0.55, 0.60, chevron));
	float edge = 1.0 - smoothstep(0.82, 1.0, across);
	float ends = smoothstep(from_m, from_m + 1.5, d) * (1.0 - smoothstep(to_m - 1.0, to_m, d));
	ALBEDO = tint.rgb;
	ALPHA = body * edge * ends * tint.a;
}
