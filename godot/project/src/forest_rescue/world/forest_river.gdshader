shader_type spatial;
render_mode unshaded, cull_disabled;

// «Лес потерянных» river (world layer override of the city water strip, flag ON only).
// art/01 east river: deep blue-teal channel, lighter shallows along the banks, subtle flow
// streaks along the current and foam where the water meets the bank rocks. Painted (unshaded,
// like the kit) so the colours read as the painting after the city's FILMIC tonemap.
// Bank geometry is analytic (same river as landscape.gd / ForestAtlas.river_center_analytic).

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 deep_color : source_color = vec3(0.16, 0.29, 0.34);
uniform vec3 mid_color : source_color = vec3(0.24, 0.40, 0.45);
uniform vec3 shallow_color : source_color = vec3(0.39, 0.55, 0.57);
uniform vec3 foam_color : source_color = vec3(0.86, 0.90, 0.88);
uniform vec3 light_dir_world = vec3(0.45, 0.74, 0.5);
uniform vec4 bridge_rect = vec4(76.982, 18.0, 27.0, 4.0);   // shade under the deck (x, z, w, d)
uniform float flow_speed = 1.1;

varying vec3 world;

float river_center(float z) {
	float k = (z + 25.0) / 15.0;          // (GLSL pow() is undefined for a negative base)
	return z + 66.0 + 8.0 * sin(z * 0.068) + 3.5 * cos(z * 0.127 + 0.3) + 9.0 * exp(-k * k);
}

float half_width(float z) {
	return 4.3 + 0.65 * sin(z * 0.093 + 1.4) + 0.9;
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world.xz;
	float c = river_center(p.y);
	// river tangent (dx/dz) -> flow direction in xz
	float dc = (river_center(p.y + 0.5) - river_center(p.y - 0.5));
	vec2 flow = normalize(vec2(dc, 1.0));
	vec2 across = vec2(flow.y, -flow.x);
	float hw = half_width(p.y);
	float u = clamp(abs(p.x - c) / hw, 0.0, 1.6);            // 0 centre .. 1 wet edge
	vec2 q = vec2(dot(p, across), dot(p, flow));
	float t = TIME * flow_speed;
	float streak = texture(noise_tex, vec2(q.x / 3.5, (q.y - t) / 21.0)).r;
	float ripple = texture(noise_tex, vec2(q.x / 7.0 + 0.3, (q.y - t * 1.4) / 9.0)).g;
	float depth = 1.0 - smoothstep(0.25, 0.95, u + (ripple - 0.5) * 0.18);
	vec3 col = mix(shallow_color, mix(mid_color, deep_color, smoothstep(0.35, 1.0, depth)), smoothstep(0.0, 0.45, depth));
	col *= 0.93 + 0.14 * streak;
	// sun glints on ripple crests (sparse, soft)
	col += vec3(0.10, 0.12, 0.12) * smoothstep(0.74, 0.92, ripple * 0.6 + streak * 0.4) * depth;
	// foam where the water meets the bank / bank rocks, broken and drifting
	float foam_n = texture(noise_tex, vec2(q.x / 2.2, (q.y - t * 0.6) / 4.0)).b;
	float foam_patch = texture(noise_tex, vec2(p.x / 19.0, p.y / 23.0)).r;   // rocky stretches
	float foam = smoothstep(0.82, 0.97, u) * smoothstep(0.55, 0.85, foam_n) * smoothstep(0.42, 0.62, foam_patch);
	col = mix(col, foam_color, clamp(foam, 0.0, 0.7));
	// wet dark rim where the water laps the bank
	col *= 1.0 - 0.18 * smoothstep(0.9, 1.0, u);
	// shade under the bridge deck (soft)
	vec2 b0 = bridge_rect.xy;
	vec2 b1 = bridge_rect.xy + bridge_rect.zw;
	// (smoothstep needs edge0 < edge1 in GLSL: equal edges are undefined)
	vec2 inside = smoothstep(b0 - vec2(0.5, 1.5), b0 + vec2(0.5, 0.5), p) * (1.0 - smoothstep(b1 - vec2(0.5, 0.5), b1 + vec2(0.5, 1.5), p));
	col *= 1.0 - 0.35 * inside.x * inside.y;
	ALBEDO = col;
}
