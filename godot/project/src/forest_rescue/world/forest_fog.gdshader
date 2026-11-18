shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

// «Лес потерянных» exploration fog (lf_vfx_fog). Terrain-following shells, no particles,
// no raymarch. State texture (56×56, 4 m cells over [-112,112)²):
//   R = previous clear mask, G = target clear mask (server projection), B/A = previous/target
//   depth into the fog (distance to the nearest clear cell, 0..24 m → 0..1): banks are thin
//   and low next to clear ground (town stays readable) and rise above the canopy deeper in. The reveal (lf_fog_reveal, ~2 s) blends R→G per pixel with a
//   noise delay so cleared fog rolls away in billows; the edge is warped by drifting noise
//   (wisps). Outside the atlas the forest is always fogged.

uniform sampler2D state_tex : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D depth_tex : hint_depth_texture, filter_linear_mipmap;
uniform vec4 domain = vec4(-112.0, -112.0, 224.0, 224.0);
uniform float layer = 0.0;               // 0 haze, 1 bank, 2 crest
uniform float layer_alpha = 0.9;
uniform float layer_threshold = 0.0;     // higher layers need deeper fog
uniform float layer_height = 12.0;       // shell height above ground in deep fog
uniform float drift_speed = 0.6;
uniform vec2 wind = vec2(0.83, 0.56);
uniform float reveal_t = 1.0;
uniform float reveal_curl = 0.0;
uniform float dim_strength = 0.0;        // explored but not in current sight
uniform vec4 sights[8];
uniform int sight_count = 0;
uniform vec3 light_dir = vec3(0.45, 0.74, 0.5);
uniform vec3 lit_color : source_color = vec3(0.788, 0.824, 0.839);    // #c9d2d6 highlights
uniform vec3 shade_color : source_color = vec3(0.373, 0.435, 0.478);  // #5f6f7a valleys
uniform vec3 haze_color : source_color = vec3(0.561, 0.627, 0.671);   // #8fa0ab body
uniform vec3 warm_rim : source_color = vec3(0.90, 0.87, 0.80);
uniform float edge_softness = 0.16;
uniform bool soft_depth = true;
uniform float soft_distance = 2.5;
uniform float time_offset = 0.0;

varying vec3 world;
varying float vertex_fog;

vec4 cubic_weights(float v) {
	vec4 n = vec4(1.0, 2.0, 3.0, 4.0) - v;
	vec4 s = n * n * n;
	float x = s.x;
	float y = s.y - 4.0 * s.x;
	float z = s.z - 4.0 * s.y + 6.0 * s.x;
	float w = 6.0 - x - y - z;
	return vec4(x, y, z, w) * (1.0 / 6.0);
}

// Cubic B-spline filtered state (4 bilinear taps): rounded, blob-like cell shapes.
vec4 state_bicubic(vec2 uv) {
	vec2 size = vec2(56.0);
	vec2 px = uv * size - 0.5;
	vec2 f = fract(px);
	px -= f;
	vec4 xc = cubic_weights(f.x);
	vec4 yc = cubic_weights(f.y);
	vec4 c = px.xxyy + vec2(-0.5, 1.5).xyxy;
	vec4 s = vec4(xc.xz + xc.yw, yc.xz + yc.yw);
	vec4 offset = c + vec4(xc.yw, yc.yw) / s;
	offset /= size.xxyy;
	vec4 s0 = texture(state_tex, offset.xz);
	vec4 s1 = texture(state_tex, offset.yz);
	vec4 s2 = texture(state_tex, offset.xw);
	vec4 s3 = texture(state_tex, offset.yw);
	float sx = s.x / (s.x + s.y);
	float sy = s.z / (s.z + s.w);
	return mix(mix(s3, s2, sx), mix(s1, s0, sx), sy);
}

float inside_domain(vec2 p) {
	vec2 q = (p - domain.xy) / domain.zw;
	vec2 edge = smoothstep(vec2(0.0), vec2(0.012), q) * (1.0 - smoothstep(vec2(0.988), vec2(1.0), q));
	return edge.x * edge.y;
}

// Clear amount (0 = fog, 1 = open) incl. the reveal blend at time reveal_t.
float clear_at(vec2 p, float delay_noise) {
	vec4 s = state_bicubic((p - domain.xy) / domain.zw);
	float local_t = smoothstep(delay_noise * 0.55, delay_noise * 0.55 + 0.45, reveal_t);
	return mix(s.r, s.g, local_t) * inside_domain(p);
}

varying float vertex_depth;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec4 s = state_bicubic((world.xz - domain.xy) / domain.zw);
	float inside = inside_domain(world.xz);
	float clear = mix(s.r, s.g, reveal_t) * inside;
	vertex_fog = 1.0 - clear;
	vertex_depth = mix(mix(s.b, s.a, reveal_t), 1.0, 1.0 - inside);
	// Banks hug the ground at the clear edge and rise above the canopy deeper in the fog.
	float swell = smoothstep(0.0, 0.85, vertex_fog) * (0.22 + 0.78 * smoothstep(0.0, 1.0, vertex_depth));
	float billow = texture(noise_tex, world.xz / 47.0 + vec2(0.37 * layer, 0.11)).r;
	world.y += layer_height * swell * (0.85 + 0.3 * billow) + reveal_curl * (1.0 - swell) * 2.0;
	VERTEX = (inverse(MODEL_MATRIX) * vec4(world, 1.0)).xyz;
}

void fragment() {
	vec2 p = world.xz;
	float t = TIME + time_offset;
	vec2 drift = wind * t * drift_speed;
	// Domain-warped drifting billows (large) + detail; wisps curl at the edge.
	vec4 w = texture(noise_tex, (p + drift * 0.6) / 61.0);
	vec2 warp = (w.rg - 0.5) * (9.0 + reveal_curl * 14.0);
	float big = texture(noise_tex, (p + warp + drift) / 47.0 + vec2(0.37 * layer, 0.11)).r;
	float mid = texture(noise_tex, (p - warp * 0.7 + drift * 1.6) / 19.0 + vec2(0.5, 0.23 * layer)).g;
	float fine = texture(noise_tex, (p + warp * 0.4 + drift * 2.3) / 7.5).b;
	float delay = texture(noise_tex, p / 33.0).a;
	vec2 edge_warp = (vec2(mid, big) - 0.5) * (7.0 + layer * 2.5 + reveal_curl * 6.0) + (w.ba - 0.5) * 4.0;
	float clear = clear_at(p + edge_warp, delay);
	float fog = 1.0 - clear;
	float billow = big * 0.66 + mid * 0.27 + fine * 0.07;
	float body = fog * (0.62 + 0.62 * billow) * (0.55 + 0.45 * smoothstep(0.0, 0.5, vertex_depth)) - layer_threshold;
	float alpha = smoothstep(0.0, edge_softness, body) * layer_alpha;
	// Lighting from the noise height field (cheap normal) + bank slope.
	float hx = texture(noise_tex, (p + vec2(1.2, 0.0) + warp + drift) / 47.0 + vec2(0.37 * layer, 0.11)).r - big;
	float hz = texture(noise_tex, (p + vec2(0.0, 1.2) + warp + drift) / 47.0 + vec2(0.37 * layer, 0.11)).r - big;
	vec3 n = normalize(vec3(-hx * 7.0, 1.0, -hz * 7.0));
	float ndl = clamp(dot(n, normalize(light_dir)) * 0.5 + 0.5, 0.0, 1.0);
	// Cauliflower shading: billow tops catch the sun, valleys stay blue-grey.
	float tops = pow(clamp(billow, 0.0, 1.0), 0.8);
	float light = clamp(tops * (0.55 + 0.18 * layer) + (ndl - 0.5) * 0.55 + 0.12 * layer, 0.0, 1.0);
	vec3 color = mix(shade_color, lit_color, light);
	// Thin edges glow softly from the sun side (backlit wisps).
	float thin = 1.0 - smoothstep(0.0, edge_softness * 2.5, body);
	color = mix(color, warm_rim, thin * 0.35 * ndl);
	color = mix(haze_color, color, 0.35 + 0.65 * smoothstep(0.0, 1.0, layer * 0.5 + billow * 0.5));
	// Explored but not currently watched: a light veil (haze layer only), never over the town.
	if (dim_strength > 0.0 && layer < 0.5) {
		vec4 s = state_bicubic((p - domain.xy) / domain.zw);
		float sight = 0.0;
		for (int i = 0; i < 8; i++) {
			if (i >= sight_count) break;
			vec4 q = sights[i];
			sight = max(sight, (1.0 - smoothstep(q.z * 0.75, q.z, distance(p, q.xy))) * q.w);
		}
		float town = step(max(abs(p.x), abs(p.y)), 56.0);
		float veil = dim_strength * clear * (1.0 - town) * (1.0 - sight) * (0.75 + 0.5 * billow);
		alpha = max(alpha, veil);
		color = mix(color, haze_color, veil);
	}
	if (soft_depth) {
		float depth = texture(depth_tex, SCREEN_UV).r;
		vec4 view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
		view.xyz /= view.w;
		float gap = (-view.z) - (-VERTEX.z);
		alpha *= clamp(gap / soft_distance, 0.0, 1.0);
	}
	ALBEDO = color;
	ALPHA = clamp(alpha, 0.0, 1.0);
}
