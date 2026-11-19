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
// sRGB inputs (see header): on screen #3f535e / #5f727e / #81939f / #98a5ac.
uniform vec3 valley_color : source_color = vec3(0.204, 0.259, 0.292);
uniform vec3 body_color : source_color = vec3(0.293, 0.350, 0.386);
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

// World-space 3D puffs (vertically squashed), slowly evolving; 0..1.
float puffs(vec3 p, vec2 drift, float time) {
	vec3 q = vec3((p.x + drift.x * 0.8) / 11.0, p.y / 5.5 + time * 0.012, (p.z + drift.y * 0.8) / 11.0);
	float a = texture(noise3d, q).r;
	float b = texture(noise3d, q * 2.03 + vec3(0.31, 0.17, 0.59)).r;
	return a * 0.82 + b * 0.18;
}

float wisp_band(float sdf) {
	// only over explored ground (the bank itself stays the cloud top): rises right after the edge,
	// plateau over the first ~5 m of revealed forest, descends gently further inside
	return smoothstep(1.0, 3.0, sdf) * (1.0 - smoothstep(7.0, 17.0, sdf));
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec4 s = texture(state_tex, state_uv(world.xz));
	float top = mix(s.a, s.b, reveal_t) * height_range;
	float cloud = top * (0.6 + 0.8 * billow(world.xz, drift_of(TIME)));
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

	// ---- cumulus surface shading at the cloud top (entry) --------------------------------
	float top_e = mix(s_in.a, s_in.b, reveal_t) * height_range;
	float e = 3.0;
	vec4 s_x = texture(state_tex, state_uv(entry.xz + vec2(e, 0.0)));
	vec4 s_z = texture(state_tex, state_uv(entry.xz + vec2(0.0, e)));
	float b0 = billow(entry.xz, drift);
	float pf = puffs(entry, drift, time);
	float pfx = puffs(entry + vec3(e, 0.0, 0.0), drift, time);
	float pfz = puffs(entry + vec3(0.0, 0.0, e), drift, time);
	// combined cloud-top height field: banks (state top × billow) + world-space puffs
	float h0 = top_e * (0.6 + 0.8 * b0) + 4.0 * pf;
	float hx = mix(s_x.a, s_x.b, reveal_t) * height_range * (0.6 + 0.8 * billow(entry.xz + vec2(e, 0.0), drift)) + 4.0 * pfx;
	float hz = mix(s_z.a, s_z.b, reveal_t) * height_range * (0.6 + 0.8 * billow(entry.xz + vec2(0.0, e), drift)) + 4.0 * pfz;
	vec3 n = normalize(vec3((h0 - hx) / e * 2.2, 1.0, (h0 - hz) / e * 2.2));
	float lambert = clamp(dot(n, normalize(light_dir)), 0.0, 1.0);
	// 0 = valley between billows .. 1 = domed billow top
	float cum = smoothstep(0.37, 0.69, b0 * 0.55 + pf * 0.45);
	cum = 1.0 - (1.0 - cum) * (1.0 - cum);
	vec3 shade = mix(valley_color, body_color, smoothstep(0.0, 0.5, cum));
	shade = mix(shade, lit_color, smoothstep(0.42, 0.95, cum) * (0.4 + 0.6 * lambert));
	shade = mix(shade, sun_color, smoothstep(0.72, 1.0, cum) * smoothstep(0.55, 0.95, lambert) * 0.9);
	shade *= mix(0.9, 1.06, lambert);

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
		float top = mix(s.a, s.b, local_t) * height_range;
		float cloud_top = top * (0.6 + 0.8 * b);
		float y = max(0.0, p.y - ground(p.xz));
		float body = 1.0 - smoothstep(cloud_top - 3.0, cloud_top + 0.6, y);
		float detail = 0.55 + 0.45 * smoothstep(0.25, 0.75, puffs(p, drift, time));
		// revealing fog thins out and brightens (luminous dissolve)
		float revealing = clamp((s.r - s.g) * sdf_range / 10.0, 0.0, 1.0) * reveal_curl;
		float d = density * fogness * body * detail * (1.0 - 0.6 * revealing);
		if (d <= 0.0005) {
			continue;
		}
		float a = 1.0 - exp(-d * step_len);
		// the visible colour is the cumulus surface shade, a touch darker deeper inside
		float near_top = smoothstep(cloud_top - 7.0, cloud_top - 0.5, y);
		vec3 col = shade * mix(0.86, 1.0, near_top);
		float thin = 1.0 - smoothstep(0.15, 0.7, fogness * body);
		col = mix(col, haze_color, thin * 0.8);
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
		vec3 wq = vec3(along.x / 26.0 - time * drift_speed * 0.045, entry.y / 9.0 + time * 0.01, along.y / 8.0);
		float w1 = texture(noise3d, wq).r;
		float w2 = texture(noise3d, wq * 2.1 + vec3(0.43, 0.11, 0.27)).r;
		float wisp = smoothstep(0.50, 0.78, w1 * 0.7 + w2 * 0.3) * smoothstep(0.6, 1.0, band);
		float a_w = wisp_alpha * wisp * (1.0 - 0.5 * reveal_curl);
		vec3 wc = mix(haze_color, sun_color, 0.35 + 0.4 * w2);
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
