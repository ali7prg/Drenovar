shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_default, cull_back, shadows_disabled, fog_disabled;

// «Лес потерянных» exploration fog (lf_vfx_fog), v2: ONE shell, volumetric look, no depth reads
// (the Mobile renderer gives transparent passes no depth texture).
// The fog is a height-limited volume above the ground: inside unknown cells it fills the forest
// up to a billowing cloud top at about canopy height (blue-grey banks, art/07 / art/18); near the
// edge of explored ground the top sinks to the floor over ~14 m. The shell IS that cloud top
// (vertex-displaced by the same billow noise), so crowns taller than the local top are in front
// of it and stay crisp (conifer tops poke out of the cloud sea), anything below is fogged.
// The fragment marches the city camera's (fixed, orthographic) view ray from the cloud top down
// to the ground (heightmap) in STEPS samples, so the explored edge, wisps and thin margins are
// integrated correctly. One alpha-blended layer (overdraw 1), no particles, uniforms-only motion.
//
// State texture (70×70, 4 m cells over [-140,140)², the atlas ±112 plus an always-fogged ring):
//   R/G = target/previous signed distance to the explored edge (+ inside explored ground,
//   0.5 + d/64), B/A = target/previous fog-top height (/height_range), already capped on the
//   camera-near side so a bank never hides explored ground behind it (fixed city camera).
//   The edge is the SDF zero line + bounded noise (−3…+1 m: fog may curl a little into explored
//   ground, it never reveals more than ~3 m past the server cells). The reveal (~2 s) blends the
//   SDF and the top previous→target with a per-pixel noise delay: the bank sinks and rolls back.
// Heightmap texture: smoothed ground height on a 2 m grid over [-140,140].

uniform sampler2D state_tex : filter_linear, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec4 domain = vec4(-140.0, -140.0, 280.0, 280.0);
uniform float height_range = 30.0;
uniform float height_lo = -4.0;
uniform float height_span = 40.0;
uniform float sdf_range = 64.0;
uniform float reveal_t = 1.0;
uniform float reveal_curl = 0.0;
uniform float drift_speed = 0.6;
uniform vec2 wind = vec2(0.83, 0.56);
uniform float density = 0.42;            // extinction per metre inside deep fog (opaque)
uniform float fog_top_abs = 13.0;        // deep fog top (m) for the colour gradient
uniform float dim_strength = 0.0;        // explored but not in current sight
uniform vec4 sights[8];
uniform int sight_count = 0;
uniform vec3 light_dir = vec3(0.45, 0.74, 0.5);
uniform vec3 view_dir = vec3(-0.5414, -0.5991, -0.5414);   // city camera: normalize(-(75, 83, 75))
// Blue-grey palette sampled from art/18 panel 1 / art/07 panel 1 (median #53697a, tops #738ca0,
// valleys #374956), sRGB before the city's FILMIC tonemap (near identity in this range).
uniform vec3 lit_color : source_color = vec3(0.50, 0.59, 0.66);
uniform vec3 body_color : source_color = vec3(0.35, 0.43, 0.50);
uniform vec3 deep_color : source_color = vec3(0.22, 0.29, 0.34);
uniform vec3 haze_color : source_color = vec3(0.45, 0.53, 0.59);
uniform vec3 rim_color : source_color = vec3(0.74, 0.71, 0.63);
uniform float time_offset = 0.0;
uniform int debug_mode = 0;
const int STEPS = 8;

varying vec3 world;
varying float shell_top;

vec2 state_uv(vec2 p) {
	return (p - domain.xy) / domain.zw;
}

float ground(vec2 p) {
	return height_lo + texture(height_tex, state_uv(p)).r * height_span;
}

vec2 drift_of(float time) {
	return wind * (time * drift_speed + time_offset);
}

// Billow field 0..1 (large banks + mid lumps), shared by the shell and the march.
float billow(vec2 p, vec2 drift) {
	float big = texture(noise_tex, (p + drift) / 92.0).r;
	float mid = texture(noise_tex, (p - drift * 1.6) / 33.0 + vec2(0.37, 0.11)).g;
	return big * 0.66 + mid * 0.34;
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec4 s = texture(state_tex, state_uv(world.xz));
	float top = mix(s.a, s.b, reveal_t) * height_range;
	// The shell is the cloud top; over explored ground it lies on the ground (veil only), so
	// there are no lifted walls over the revealed forest.
	shell_top = top * (0.6 + 0.8 * billow(world.xz, drift_of(TIME)));
	world.y += max(shell_top, 0.3);
	VERTEX = (inverse(MODEL_MATRIX) * vec4(world, 1.0)).xyz;
}

// Edge offset (m) added to the signed distance: drifting lobes + wind-elongated tendrils
// (art/07 panel 3). Range −2.6…+0.4: fog may curl ≤ 2.6 m into explored ground, never reveals.
float edge_offset(vec2 p, vec2 drift, float b) {
	vec2 wn = normalize(wind);
	vec2 along = vec2(dot(p, wn), dot(p, vec2(-wn.y, wn.x)));
	float t1 = texture(noise_tex, vec2(along.x / 38.0, along.y / 9.0) - vec2(drift.x * 0.03, 0.0) + vec2(0.13, 0.57)).r;
	float t2 = texture(noise_tex, vec2(along.x / 17.0, along.y / 5.0) - vec2(drift.x * 0.05, 0.0) + vec2(0.61, 0.21)).g;
	return -2.6 + 3.0 * (b * 0.35 + t1 * 0.45 + t2 * 0.2) - reveal_curl * 2.0 * t2;
}

void fragment() {
	vec2 drift = drift_of(TIME);
	vec3 entry = world;
	// Where the view ray from this point of the cloud top meets the ground (2 refinements).
	float g0 = ground(entry.xz);
	float t_hit = max(0.0, (entry.y - g0) / -view_dir.y);
	for (int k = 0; k < 2; k++) {
		vec3 q = entry + view_dir * t_hit;
		t_hit = max(0.0, (entry.y - ground(q.xz)) / -view_dir.y);
	}
	t_hit = min(t_hit, 60.0);
	vec3 surface = entry + view_dir * t_hit;
	if (debug_mode == 1) {
		ALBEDO = vec3(fract(surface.y / 8.0), fract(t_hit / 40.0), 0.0);
		ALPHA = 1.0;
	} else {
	// Cheap reject: entry and ground columns both well inside explored ground and no veil.
	vec4 s_in = texture(state_tex, state_uv(entry.xz));
	vec4 s_out = texture(state_tex, state_uv(surface.xz));
	float sdf_min = (min(min(s_in.r, s_in.g), min(s_out.r, s_out.g)) - 0.5) * sdf_range;
	if (dim_strength <= 0.0 && sdf_min > 2.5) {
		discard;
	}
	float trans = 1.0;
	vec3 acc = vec3(0.0);
	float step_len = t_hit / float(STEPS);
	// Over explored ground the shell lies on the ground (veil only): the volume is integrated only
	// from entries on (or right at) the fog bank itself.
	float sdf_entry = (mix(s_in.g, s_in.r, reveal_t) - 0.5) * sdf_range;
	int steps = sdf_entry > 2.0 ? 0 : STEPS;
	for (int i = 0; i < steps; i++) {
		vec3 p = entry + view_dir * (t_hit * (float(i) + 0.5) / float(STEPS));
		vec4 s = texture(state_tex, state_uv(p.xz));
		vec4 w = texture(noise_tex, (p.xz - drift * 2.3) / 15.0 + vec2(0.71, 0.29));
		float delay = texture(noise_tex, p.xz / 41.0).a;
		float local_t = smoothstep(delay * 0.5, delay * 0.5 + 0.5, reveal_t);
		float sdf = (mix(s.g, s.r, local_t) - 0.5) * sdf_range;
		// Organic edge: 2–3 m blend band, drifting lobes and wind-elongated tendrils.
		float b = billow(p.xz, drift);
		float fogness = 1.0 - smoothstep(-1.5, 1.5, sdf + edge_offset(p.xz, drift, b));
		float y = max(0.0, p.y - ground(p.xz));
		if (fogness < 0.004) {
			continue;
		}
		float top = mix(s.a, s.b, local_t) * height_range;
		float cloud_top = top * (0.6 + 0.8 * b);
		float body = 1.0 - smoothstep(cloud_top - 3.2, cloud_top + 0.6, y);
		float wisps = 0.62 + 0.38 * smoothstep(0.2, 0.8, w.g);
		float d = density * fogness * body * wisps;
		if (d <= 0.0005) {
			continue;
		}
		float a = 1.0 - exp(-d * step_len);
		// Colour by absolute height: valleys between banks darker, billow tops lit by the sun.
		float hy = clamp(y / fog_top_abs, 0.0, 1.4);
		vec3 col = mix(deep_color, body_color, smoothstep(0.0, 0.6, hy));
		float facing = clamp(0.5 + (b - billow(p.xz + normalize(light_dir.xz) * 6.0, drift)) * 6.0, 0.0, 1.0);
		col = mix(col, lit_color, smoothstep(0.5, 1.2, hy) * (0.3 + 0.7 * facing));
		// Thin fog (edges, wisps) reads as light haze, not as a dark film.
		col = mix(col, haze_color, (1.0 - smoothstep(0.1, 0.65, fogness * body)) * 0.85);
		col = mix(col, rim_color, (1.0 - fogness) * 0.12 * facing);
		acc += trans * a * col;
		trans *= 1.0 - a;
		if (trans < 0.02) {
			break;
		}
	}
	float alpha = 1.0 - trans;
	vec3 color = alpha > 0.0001 ? acc / alpha : body_color;
	// Explored but not currently watched: a light ground-level veil over the known forest (never
	// the town); trees there are dimmed by forest_fog_receiver with the same rule.
	if (dim_strength > 0.0) {
		vec4 s = texture(state_tex, state_uv(surface.xz));
		// Round sight circle on the ground (where this pixel's view ray meets the ground).
		float sight = 0.0;
		for (int i = 0; i < 8; i++) {
			if (i >= sight_count) break;
			vec4 c = sights[i];
			sight = max(sight, (1.0 - smoothstep(c.z * 0.75, c.z, distance(c.xy, surface.xz))) * c.w);
		}
		// soft 10 m transition at the protected town (no hard line along the ±56 square)
		float outside = smoothstep(56.0, 66.0, max(abs(surface.x), abs(surface.z)));
		float explored = smoothstep(0.0, 3.0, (mix(s.g, s.r, reveal_t) - 0.5) * sdf_range);
		float veil = dim_strength * explored * outside * (1.0 - sight);
		// ground -> veil -> fog (back to front); the veil dims toward the deep fog colour
		float total = 1.0 - (1.0 - alpha) * (1.0 - veil);
		color = (color * alpha + (1.0 - alpha) * veil * mix(deep_color, body_color, 0.5)) / max(total, 1e-4);
		alpha = total;
	}
	if (alpha < 0.003) {
		discard;
	}
	ALBEDO = color;
	ALPHA = clamp(alpha, 0.0, 1.0);
	}
}
