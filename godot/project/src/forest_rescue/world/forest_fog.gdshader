shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_default, cull_back, shadows_disabled, fog_disabled;

// «Лес потерянных» exploration fog (lf_vfx_fog), v3 "luminous cumulus": ONE shell, no depth reads
// (the Mobile renderer gives transparent passes no depth texture), overdraw 1, no particles.
//
// Model. Inside unknown cells the fog is a height-limited volume that fills the forest up to a
// billowing cloud top (art/07, art/18, art/01 map edge). The shell IS that cloud top (vertex-
// displaced by the shared billow field), so it occludes correctly against trees by depth.
//  * Colour: the cloud-top surface is lit like cumulus — a normal from the cloud-top height field
//    (state top × billow) plus a world-space 3D-noise bump (vertically squashed puffs, slowly
//    evolving) gives sunlit tops toward the sun, soft blue-grey shaded undersides, and darker
//    valleys between billows (ambient occlusion from the billow height).
//  * Density: the fragment marches the city camera's (fixed, orthographic) view ray from the
//    cloud top down to the ground (heightmap); density detail is 3D noise in world space, so
//    steep faces get puffs, never vertical streaks of a projected 2D texture.
//  * Edge: signed distance to the explored edge + bounded noise (≤ 2.6 m into explored ground,
//    never reveals). Over the explored edge band the shell rises into a thin sheet at ~13 m that
//    only draws soft light wisps drifting with the wind (art/07 panel 3) — no veil there.
//  * Reveal (~2 s): previous→target blend per pixel with a noise delay; revealing fog thins out
//    and brightens (luminous wisps dissolving), the top sinks.
// Colours are sRGB inputs chosen through the inverse of the city FILMIC tonemap so that on
// screen: valleys L*≈34, body L*≈47, lit tops L*≈60, C*≈10, h≈244° (art/07 / art/18 measures).
//
// State texture (70×70, 4 m cells over [-140,140)², atlas ±112 + an always-fogged ring):
//   R/G = target/previous signed distance (0.5 + d/64, + inside explored ground),
//   B/A = target/previous fog-top height (/height_range), capped on the camera-near side.
// Heightmap: fog floor (6 m-neighbourhood max of the ground) on a 2 m grid over [-140,140].

uniform sampler2D state_tex : filter_linear, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform sampler3D noise3d : filter_linear, repeat_enable;
// Painted mist (tools/build_fog_texture.py: quilted from art/07 + art/18 fog, pre-inverted through
// the FILMIC tonemap) and cauliflower domes (inverted Worley F1, two octaves; ForestFog.make_dome).
uniform sampler2D paint_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dome_tex : filter_linear_mipmap, repeat_enable;
uniform float paint_tile_a = 62.0;       // m per tile, layer A
uniform float paint_tile_b = 41.0;       // m per tile, layer B (rotated, other drift)
uniform float dome_tile = 84.0;          // m per dome tile (~13 m domes) + small domes at /2.3
uniform vec4 domain = vec4(-140.0, -140.0, 280.0, 280.0);
uniform float height_range = 30.0;
uniform float height_lo = -4.0;
uniform float height_span = 40.0;
uniform float sdf_range = 64.0;
uniform float reveal_t = 1.0;
uniform float reveal_curl = 0.0;
uniform float drift_speed = 0.45;        // m/s of the main billows (wind is unit length)
uniform vec2 wind = vec2(0.83, 0.56);
uniform float density = 0.40;            // extinction per metre inside deep fog (opaque)
uniform float fog_top_abs = 17.0;
uniform float dim_strength = 0.0;        // explored but not in current sight
uniform vec4 sights[8];
uniform int sight_count = 0;
uniform vec3 light_dir = vec3(0.45, 0.74, 0.5);
uniform vec3 view_dir = vec3(-0.5414, -0.5991, -0.5414);   // city camera: normalize(-(75, 83, 75))
uniform float wisp_height = 13.0;        // wisp sheet over the explored edge band (m)
uniform float wisp_alpha = 0.34;
// sRGB inputs (see header): on screen ≈ #3a4d58 / #5a6d79 / #81939f / #98a5ac.
uniform vec3 valley_color : source_color = vec3(0.180, 0.231, 0.262);
uniform vec3 body_color : source_color = vec3(0.268, 0.322, 0.357);
uniform vec3 lit_color : source_color = vec3(0.395, 0.452, 0.489);
uniform vec3 sun_color : source_color = vec3(0.485, 0.515, 0.530);
uniform vec3 haze_color : source_color = vec3(0.370, 0.418, 0.449);
uniform vec3 veil_color : source_color = vec3(0.246, 0.300, 0.335);
uniform float time_offset = 0.0;
const int STEPS = 8;

varying vec3 world;
varying float wisp_lift;

vec2 state_uv(vec2 p) {
	return (p - domain.xy) / domain.zw;
}

float ground(vec2 p) {
	return height_lo + texture(height_tex, state_uv(p)).r * height_span;
}

vec4 cubic_weights(float v) {
	vec4 n = vec4(1.0, 2.0, 3.0, 4.0) - v;
	vec4 s = n * n * n;
	float x = s.x;
	float y = s.y - 4.0 * s.x;
	float z = s.z - 4.0 * s.y + 6.0 * s.x;
	float w = 6.0 - x - y - z;
	return vec4(x, y, z, w) * (1.0 / 6.0);
}

// Cubic B-spline filtered state (4 bilinear taps): rounded domes instead of planar facets.
vec4 state_smooth(vec2 p) {
	vec2 size = vec2(textureSize(state_tex, 0));
	vec2 px = state_uv(p) * size - 0.5;
	vec2 f = fract(px);
	px -= f;
	vec4 xc = cubic_weights(f.x);
	vec4 yc = cubic_weights(f.y);
	vec4 c = px.xxyy + vec2(-0.5, 1.5).xyxy;
	vec4 sw = vec4(xc.xz + xc.yw, yc.xz + yc.yw);
	vec4 offset = (c + vec4(xc.yw, yc.yw) / sw) / size.xxyy;
	vec4 s0 = texture(state_tex, offset.xz);
	vec4 s1 = texture(state_tex, offset.yz);
	vec4 s2 = texture(state_tex, offset.xw);
	vec4 s3 = texture(state_tex, offset.yw);
	float sx = sw.x / (sw.x + sw.y);
	float sy = sw.z / (sw.z + sw.w);
	return mix(mix(s3, s2, sx), mix(s1, s0, sx), sy);
}

vec2 drift_of(float time) {
	return wind * (time * drift_speed + time_offset);
}

// Billow field 0..1 (large banks + mid lumps): defines the cloud-top height. Shared with
// forest_fog_receiver.gdshaderinc (fog_billow) — keep both identical.
float billow(vec2 p, vec2 drift) {
	float big = texture(noise_tex, (p + drift) / 92.0).r;
	float mid = texture(noise_tex, (p - drift * 1.6) / 33.0 + vec2(0.37, 0.11)).g;
	return big * 0.66 + mid * 0.34;
}

// World-space 3D puffs (vertically squashed), slowly evolving; 0..1. The 3D texture repeats every
// 56 m horizontally / 14 m vertically with ~4 features per repeat: puffs ≈ 14 m wide, 7 m tall.
float puffs(vec3 p, vec2 drift, float time) {
	vec3 q = vec3((p.x + drift.x * 0.8) / 56.0, p.y / 14.0 + time * 0.004, (p.z + drift.y * 0.8) / 56.0);
	float a = texture(noise3d, q).r;
	float b = texture(noise3d, q * 2.03 + vec3(0.31, 0.17, 0.59)).r;
	return a * 0.8 + b * 0.2;
}

// Cloud-top relief 0..1: cauliflower domes (two Worley octaves) + low-frequency swell. Shared with
// forest_fog_receiver.gdshaderinc (fog_domes) — keep both identical.
float domes(vec2 p, vec2 drift) {
	float a = texture(dome_tex, (p + drift * 0.5) / dome_tile).r;
	float b = texture(dome_tex, (p - drift * 0.35) / (dome_tile / 2.3) + vec2(0.31, 0.67)).g;
	float swell = texture(noise_tex, (p + drift * 0.2) / 170.0 + vec2(0.55, 0.15)).r;
	return clamp(a * 0.62 + b * 0.23 + swell * 0.3 - 0.08, 0.0, 1.0);
}

float cloud_height(float top, vec2 p, vec2 drift) {
	return top * (0.8 + 0.4 * domes(p, drift));
}

vec3 painted(vec2 p, float time) {
	vec2 da = wind * time * drift_speed * 0.8;
	vec2 db = vec2(-wind.y, wind.x) * time * drift_speed * 0.35 + wind * time * drift_speed * 0.5;
	vec3 a = texture(paint_tex, (p - da) / paint_tile_a).rgb;
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	vec3 b = texture(paint_tex, (rot * p - db) / paint_tile_b + vec2(0.37, 0.71)).rgb;
	vec3 m = a * 0.6 + b * 0.4;
	// restore the contrast lost by averaging two independent layers; slightly desaturate
	vec3 mean = vec3(0.30, 0.355, 0.40);
	m = max(mean + (m - mean) * 1.5, vec3(0.0));
	float lum = dot(m, vec3(0.3, 0.55, 0.15));
	return mix(vec3(lum), m, 0.8);
}

float wisp_band(float sdf) {
	// only over explored ground (the bank itself stays the cloud top): rises right after the edge,
	// plateau over the first ~5 m of revealed forest, descends gently further inside
	return smoothstep(1.0, 3.0, sdf) * (1.0 - smoothstep(7.0, 17.0, sdf));
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec4 s = texture(state_tex, state_uv(world.xz));
	vec4 sm = state_smooth(world.xz);
	float top = mix(sm.a, sm.b, reveal_t) * height_range;
	float cloud = cloud_height(top, world.xz, drift_of(TIME));
	float sdf = (mix(s.g, s.r, reveal_t) - 0.5) * sdf_range;
	wisp_lift = wisp_band(sdf);
	world.y += max(max(cloud, wisp_height * wisp_lift), 0.3);
	VERTEX = (inverse(MODEL_MATRIX) * vec4(world, 1.0)).xyz;
}

void fragment() {
	float time = TIME;
	vec2 drift = drift_of(time);
	vec3 entry = world;
	vec4 s_in = texture(state_tex, state_uv(entry.xz));
	// Where the view ray from this point meets the fog floor (2 refinements).
	float t_hit = max(0.0, (entry.y - ground(entry.xz)) / -view_dir.y);
	for (int k = 0; k < 2; k++) {
		vec3 q = entry + view_dir * t_hit;
		t_hit = max(0.0, (entry.y - ground(q.xz)) / -view_dir.y);
	}
	t_hit = min(t_hit, 60.0);
	vec3 surface = entry + view_dir * t_hit;
	vec4 s_out = texture(state_tex, state_uv(surface.xz));
	float sdf_entry = (mix(s_in.g, s_in.r, reveal_t) - 0.5) * sdf_range;
	float sdf_min = (min(min(s_in.r, s_in.g), min(s_out.r, s_out.g)) - 0.5) * sdf_range;
	float band = wisp_band(sdf_entry);
	if (dim_strength <= 0.0 && sdf_min > 2.5 && band < 0.01) {
		discard;
	}

	// ---- soft painted shading at the cloud top (entry) --------------------------------------
	vec4 sm_in = state_smooth(entry.xz);
	float top_e = mix(sm_in.a, sm_in.b, reveal_t) * height_range;
	float e = 3.0;
	vec4 s_x = state_smooth(entry.xz + vec2(e, 0.0));
	vec4 s_z = state_smooth(entry.xz + vec2(0.0, e));
	float h0 = cloud_height(top_e, entry.xz, drift);
	float hx = cloud_height(mix(s_x.a, s_x.b, reveal_t) * height_range, entry.xz + vec2(e, 0.0), drift);
	float hz = cloud_height(mix(s_z.a, s_z.b, reveal_t) * height_range, entry.xz + vec2(0.0, e), drift);
	vec2 slope = vec2(h0 - hx, h0 - hz) / e;
	slope *= min(1.0, 0.75 / max(length(slope), 1e-4));        // ≤ ~37° tilt: no hard terminators
	vec3 n = normalize(vec3(slope.x, 1.0, slope.y));
	vec3 l = normalize(light_dir);
	float half_lambert = dot(n, l) * 0.5 + 0.5;                   // wrap lighting
	float ndv = abs(dot(n, -view_dir));
	vec3 albedo = painted(entry.xz, time);
	// gentle form from the domes: lit dome tops, soft shaded flanks (wrap lighting, never black)
	vec3 shade = albedo * mix(0.74, 1.14, half_lambert * half_lambert);
	// silver lining: thin / grazing parts of the billows catch the light
	float rim = (1.0 - smoothstep(0.35, 0.85, ndv)) * smoothstep(0.45, 0.9, half_lambert);
	shade = mix(shade, sun_color, rim * 0.35);
	// grazing angles and silhouettes melt into the haze (no outlines)
	shade = mix(shade, haze_color, (1.0 - smoothstep(0.25, 0.7, ndv)) * 0.55);

	// ---- volume march: density (3D puffs), thin fog reads as light haze --------------------
	float trans = 1.0;
	vec3 acc = vec3(0.0);
	float step_len = t_hit / float(STEPS);
	// No march from lifted/explored entries: without a depth buffer it would paint far banks over
	// the revealed trees in front (wisps only there).
	int steps = (sdf_entry > 2.0 || band > 0.02) ? 0 : STEPS;
	for (int i = 0; i < steps; i++) {
		vec3 p = entry + view_dir * (t_hit * (float(i) + 0.5) / float(STEPS));
		vec4 s = texture(state_tex, state_uv(p.xz));
		float delay = texture(noise_tex, p.xz / 41.0).a;
		float local_t = smoothstep(delay * 0.5, delay * 0.5 + 0.5, reveal_t);
		float sdf = (mix(s.g, s.r, local_t) - 0.5) * sdf_range;
		float b = billow(p.xz, drift);
		vec2 wn = normalize(wind);
		vec2 along = vec2(dot(p.xz, wn), dot(p.xz, vec2(-wn.y, wn.x)));
		float t1 = texture(noise_tex, vec2(along.x / 38.0, along.y / 9.0) - vec2(drift.x * 0.03, 0.0) + vec2(0.13, 0.57)).r;
		float t2 = texture(noise_tex, vec2(along.x / 17.0, along.y / 5.0) - vec2(drift.x * 0.05, 0.0) + vec2(0.61, 0.21)).g;
		float offset = -2.6 + 3.0 * (b * 0.35 + t1 * 0.45 + t2 * 0.2) - reveal_curl * 2.0 * t2;
		float fogness = 1.0 - smoothstep(-1.5, 1.5, sdf + offset);
		if (fogness < 0.004) {
			continue;
		}
		vec4 smp = state_smooth(p.xz);
		float top = mix(smp.a, smp.b, local_t) * height_range;
		float g = ground(p.xz);
		// the faceted shell may sit slightly above the analytic cloud top: count the first metres
		// below the entry as inside the cloud (no facet creases in density/haze)
		float cloud_top = max(cloud_height(top, p.xz, drift), (entry.y - g) * step(0.5, top) - 0.4);
		float y = max(0.0, p.y - g);
		float body = 1.0 - smoothstep(cloud_top - 3.0, cloud_top + 0.6, y);
		float detail = 0.75 + 0.25 * smoothstep(0.25, 0.75, puffs(p, drift, time));
		// revealing fog thins out and brightens (luminous dissolve)
		float revealing = clamp((s.r - s.g) * sdf_range / 10.0, 0.0, 1.0) * reveal_curl;
		float d = density * fogness * body * detail * (1.0 - 0.6 * revealing);
		if (d <= 0.0005) {
			continue;
		}
		float a = 1.0 - exp(-d * step_len);
		// the visible colour is the cumulus surface shade, a touch darker deeper inside
		float near_top = smoothstep(cloud_top - 7.0, cloud_top - 0.5, y);
		vec3 col = shade * mix(0.95, 1.0, near_top);
		// the first metres of fog at the edge are translucent light mist
		float thin = 1.0 - smoothstep(0.15, 0.7, fogness * body);
		col = mix(col, mix(haze_color, sun_color, 0.35), thin * 0.85);
		col = mix(col, sun_color, revealing * 0.55);
		acc += trans * a * col;
		trans *= 1.0 - a;
		if (trans < 0.02) {
			break;
		}
	}
	float alpha = 1.0 - trans;
	vec3 color = alpha > 0.0001 ? acc / alpha : shade;

	// ---- wisps over the explored edge band (thin light mist drifting over the edge trees) ----
	if (band > 0.01) {
		vec2 wn = normalize(wind);
		vec2 along = vec2(dot(entry.xz, wn), dot(entry.xz, vec2(-wn.y, wn.x)));
		vec3 wq = vec3((along.x - time * drift_speed * 1.2) / 120.0, entry.y / 30.0 + time * 0.003, along.y / 36.0);
		float w1 = texture(noise3d, wq).r;
		vec3 pw = painted(vec2(along.x * 0.6, along.y * 1.6), time);
		float lum = dot(pw, vec3(0.3, 0.55, 0.15));
		float wisp = smoothstep(0.46, 0.74, w1 * 0.6 + smoothstep(0.30, 0.42, lum) * 0.4) * smoothstep(0.6, 1.0, band);
		// soft haze bank rising over the first metres of revealed forest (art/07 panel 3)
		float sdf_e2 = (mix(s_in.g, s_in.r, reveal_t) - 0.5) * sdf_range;
		float bank = 0.16 * (1.0 - smoothstep(1.5, 7.0, sdf_e2));
		float a_w = (wisp_alpha * wisp + bank) * (1.0 - 0.5 * reveal_curl);
		vec3 wc = mix(haze_color, sun_color, 0.3 + 0.5 * smoothstep(0.3, 0.45, lum));
		color = (color * alpha + (1.0 - alpha) * a_w * wc) / max(1.0 - (1.0 - alpha) * (1.0 - a_w), 1e-4);
		alpha = 1.0 - (1.0 - alpha) * (1.0 - a_w);
	}

	// ---- explored but not currently watched: a light ground-level veil (never the town) -----
	// (faded out under the wisp sheet so the revealed edge trees never get a dark band)
	if (dim_strength > 0.0) {
		vec4 s = texture(state_tex, state_uv(surface.xz));
		float sight = 0.0;
		for (int i = 0; i < 8; i++) {
			if (i >= sight_count) break;
			vec4 c = sights[i];
			sight = max(sight, (1.0 - smoothstep(c.z * 0.75, c.z, distance(c.xy, surface.xz))) * c.w);
		}
		float outside = smoothstep(56.0, 66.0, max(abs(surface.x), abs(surface.z)));
		float explored = smoothstep(0.0, 3.0, (mix(s.g, s.r, reveal_t) - 0.5) * sdf_range);
		float veil = dim_strength * explored * outside * (1.0 - sight) * (1.0 - band);
		float total = 1.0 - (1.0 - alpha) * (1.0 - veil);
		color = (color * alpha + (1.0 - alpha) * veil * veil_color) / max(total, 1e-4);
		alpha = total;
	}
	if (alpha < 0.003) {
		discard;
	}
	ALBEDO = color;
	ALPHA = clamp(alpha, 0.0, 1.0);
}
