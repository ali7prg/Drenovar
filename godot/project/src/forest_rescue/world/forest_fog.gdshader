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
// Target on screen (after the city's filmic tonemap): #c9d2d6 tops, #8fa0ab body, #5f6f7a valleys.
uniform vec3 lit_color : source_color = vec3(0.64, 0.69, 0.72);
uniform vec3 shade_color : source_color = vec3(0.24, 0.29, 0.33);
uniform vec3 haze_color : source_color = vec3(0.39, 0.45, 0.50);
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
	// Banks stand above the canopy right at the feathered edge (far side), but rise gently on the
	// camera-near side so they never hide the protected town by parallax.
	vec2 e = vec2(4.0, 0.0);
	vec2 uv = (world.xz - domain.xy) / domain.zw;
	float dx = mix(state_bicubic(uv + e.xy / domain.zw).b, state_bicubic(uv + e.xy / domain.zw).a, reveal_t)
		- mix(state_bicubic(uv - e.xy / domain.zw).b, state_bicubic(uv - e.xy / domain.zw).a, reveal_t);
	float dz = mix(state_bicubic(uv + e.yx / domain.zw).b, state_bicubic(uv + e.yx / domain.zw).a, reveal_t)
		- mix(state_bicubic(uv - e.yx / domain.zw).b, state_bicubic(uv - e.yx / domain.zw).a, reveal_t);
	vec2 to_clear = -vec2(dx, dz);
	float near_side = smoothstep(-0.05, 0.25, dot(to_clear, normalize(vec2(-1.0, -1.0))));
	float ramp = mix(0.75 + 0.25 * vertex_depth, smoothstep(0.0, 0.75, vertex_depth), near_side);
	float swell = smoothstep(0.0, 0.5, vertex_fog) * ramp;
	float billow = texture(noise_tex, world.xz / 47.0 + vec2(0.37 * layer, 0.11)).r;
	world.y += layer_height * swell * (0.85 + 0.3 * billow) + reveal_curl * (1.0 - swell) * 2.0;
	VERTEX = (inverse(MODEL_MATRIX) * vec4(world, 1.0)).xyz;
}

void fragment() {
	vec2 p = world.xz;
	float t = TIME + time_offset;
	vec2 drift = wind * t * drift_speed;
	vec2 offset = vec2(0.37 * layer, 0.11 + 0.23 * layer);
	// Cloud-scale noise: ~55 m lobes, ~40 m billows, ~17 m puffs, ~6 m wisps (no marbling).
	vec4 lobe = texture(noise_tex, (p + drift * 0.3) / 220.0 + vec2(0.21, 0.67));
	vec2 warp = (lobe.rg - 0.5) * (10.0 + reveal_curl * 16.0);
	float big = texture(noise_tex, (p + warp + drift) / 170.0 + offset).r;
	float mid = texture(noise_tex, (p - warp * 0.5 + drift * 1.5) / 70.0 + offset.yx).g;
	float fine = texture(noise_tex, (p + warp * 0.3 + drift * 2.2) / 26.0 + offset).r;
	float delay = texture(noise_tex, p / 33.0).a;
	vec2 edge_warp = (lobe.ba - 0.5) * 30.0 + (vec2(mid, big) - 0.5) * (7.0 + reveal_curl * 6.0);
	// Irregular bank edge: fog may curl up to ~10 m into explored ground, but the clear area may
	// grow at most ~3 m past the server cells (fog never reveals), and the town core stays clear.
	float true_clear = clear_at(p, delay);
	float clear = min(clear_at(p + edge_warp, delay), smoothstep(0.02, 0.22, true_clear));
	clear = max(clear, 1.0 - smoothstep(53.0, 55.5, max(abs(p.x), abs(p.y))));
	float fog = 1.0 - clear;
	float billow = big * 0.62 + mid * 0.28 + fine * 0.10;
	float body = fog * (0.62 + 0.62 * billow) * (0.55 + 0.45 * smoothstep(0.0, 0.5, vertex_depth)) - layer_threshold;
	float alpha = smoothstep(0.0, edge_softness, body) * layer_alpha * smoothstep(0.0, 0.55, fog);
	// Lighting from the billow height field (sun side bright, lee side blue-grey).
	float bx = texture(noise_tex, (p + vec2(3.0, 0.0) + warp + drift) / 170.0 + offset).r * 0.62
		+ texture(noise_tex, (p + vec2(3.0, 0.0) - warp * 0.5 + drift * 1.5) / 70.0 + offset.yx).g * 0.28;
	float bz = texture(noise_tex, (p + vec2(0.0, 3.0) + warp + drift) / 170.0 + offset).r * 0.62
		+ texture(noise_tex, (p + vec2(0.0, 3.0) - warp * 0.5 + drift * 1.5) / 70.0 + offset.yx).g * 0.28;
	float b0 = big * 0.62 + mid * 0.28;
	vec3 n = normalize(vec3(-(bx - b0) * 9.0, 1.0, -(bz - b0) * 9.0));
	float ndl = clamp(dot(n, normalize(light_dir)) * 0.5 + 0.5, 0.0, 1.0);
	float tops = smoothstep(0.3, 0.8, billow);
	float light = clamp(0.16 + tops * 0.46 + (ndl - 0.5) * 1.0 + 0.04 * layer, 0.0, 1.0);
	vec3 color = light < 0.5 ? mix(shade_color, haze_color, light * 2.0) : mix(haze_color, lit_color, light * 2.0 - 1.0);
	// Thin edges glow softly from the sun side (backlit wisps).
	float thin = 1.0 - smoothstep(0.0, edge_softness * 2.5, body);
	color = mix(color, warm_rim, thin * 0.18 * ndl);
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
