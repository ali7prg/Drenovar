shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_default, cull_back, shadows_disabled, fog_disabled;

// «Лес потерянных» exploration fog (lf_vfx_fog), v2: ONE shell, volumetric look.
// The fog is a height-limited volume above the ground: inside unknown cells it fills the forest
// up to a billowing top at about canopy height (blue-grey cloud banks, art/07 / art/18); near the
// edge of explored ground the top sinks to the floor over ~14 m, so tree tops poke out and
// dissolve into it. The shell is the volume's upper surface; its fragment marches the view ray
// down to the opaque surface (depth buffer) in STEPS samples, so tall crowns above the fog stay
// crisp (they occlude the shell) and anything inside is fogged by the thickness it sits in.
// One alpha-blended layer (overdraw 1), no particles, uniforms-only animation.
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
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform vec4 domain = vec4(-140.0, -140.0, 280.0, 280.0);
uniform float height_range = 30.0;
uniform float height_lo = -4.0;
uniform float height_span = 40.0;
uniform float reveal_t = 1.0;
uniform float reveal_curl = 0.0;
uniform float drift_speed = 0.6;
uniform vec2 wind = vec2(0.83, 0.56);
uniform float density = 0.34;            // extinction per metre inside deep fog
uniform float fog_top_abs = 13.0;         // deep fog top (m) for the colour gradient
uniform float sdf_range = 64.0;
uniform float dim_strength = 0.0;        // explored but not in current sight
uniform float veil_height = 19.0;
uniform vec4 sights[8];
uniform int sight_count = 0;
uniform vec3 light_dir = vec3(0.45, 0.74, 0.5);
// Blue-grey palette (art/07, art/18), sRGB before the city's FILMIC tonemap.
uniform vec3 lit_color : source_color = vec3(0.66, 0.71, 0.76);
uniform vec3 body_color : source_color = vec3(0.47, 0.53, 0.59);
uniform vec3 deep_color : source_color = vec3(0.31, 0.36, 0.42);
uniform vec3 haze_color : source_color = vec3(0.60, 0.65, 0.70);
uniform vec3 rim_color : source_color = vec3(0.86, 0.84, 0.78);
uniform float time_offset = 0.0;
const int STEPS = 8;

varying vec3 world;

vec2 state_uv(vec2 p) {
	return (p - domain.xy) / domain.zw;
}

float ground(vec2 p) {
	return height_lo + texture(height_tex, state_uv(p)).r * height_span;
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec4 s = texture(state_tex, state_uv(world.xz));
	float h = max(s.a, s.b) * height_range;
	float explored = step(0.0, max(s.r, s.g) - 0.5);
	float town = step(max(abs(world.x), abs(world.z)), 56.0);
	float veil = dim_strength > 0.0 ? explored * (1.0 - town) * veil_height : 0.0;
	world.y += max(h * 1.42 + 1.2, veil);
	VERTEX = (inverse(MODEL_MATRIX) * vec4(world, 1.0)).xyz;
}

void fragment() {
	float t = TIME * drift_speed + time_offset;
	vec2 drift = wind * t;
	// Opaque surface behind this pixel (ground, trunk, crown, building).
	float depth = texture(depth_tex, SCREEN_UV).r;
	vec4 view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
	view.xyz /= view.w;
	vec3 surface = (INV_VIEW_MATRIX * vec4(view.xyz, 1.0)).xyz;
	vec3 entry = world;
	// Cheap reject: entry and surface columns both well inside explored ground and no veil.
	vec4 s_in = texture(state_tex, state_uv(entry.xz));
	vec4 s_out = texture(state_tex, state_uv(surface.xz));
	float sdf_min = (min(min(s_in.r, s_in.g), min(s_out.r, s_out.g)) - 0.5) * sdf_range;
	if (dim_strength <= 0.0 && sdf_min > 4.5) {
		discard;
	}
	vec3 ray = surface - entry;
	float len = length(ray);
	if (len > 60.0) {
		ray *= 60.0 / len;
		len = 60.0;
	}
	float trans = 1.0;
	vec3 acc = vec3(0.0);
	float step_len = len / float(STEPS);
	float lit = 0.0;
	for (int i = 0; i < STEPS; i++) {
		vec3 p = entry + ray * ((float(i) + 0.5) / float(STEPS));
		vec4 s = texture(state_tex, state_uv(p.xz));
		vec4 n = texture(noise_tex, (p.xz + drift) / 66.0);
		vec4 m = texture(noise_tex, (p.xz - drift * 1.7) / 21.0 + vec2(0.37, 0.11));
		float delay = n.a;
		float local_t = smoothstep(delay * 0.5, delay * 0.5 + 0.5, reveal_t);
		float sdf = (mix(s.g, s.r, local_t) - 0.5) * sdf_range;
		// Organic edge: −3…+1 m of drifting noise, plus a curl while the bank rolls back.
		float offset = -3.0 + 4.0 * (n.g * 0.6 + m.r * 0.4) - reveal_curl * 2.0 * m.b;
		float fogness = 1.0 - smoothstep(-2.0, 1.6, sdf + offset);
		if (fogness < 0.004) {
			continue;
		}
		float top = mix(s.a, s.b, local_t) * height_range;
		float billow = n.r * 0.62 + m.g * 0.38;
		float cloud_top = top * (0.52 + 0.9 * billow);
		float y = max(0.0, p.y - ground(p.xz));
		float body = 1.0 - smoothstep(cloud_top - 3.0, cloud_top + 0.6, y);
		float wisps = 0.6 + 0.4 * smoothstep(0.2, 0.8, m.b);
		float d = density * fogness * body * wisps;
		if (d <= 0.0005) {
			continue;
		}
		float a = 1.0 - exp(-d * step_len);
		// Colour by absolute height: valleys between banks darker, billow tops lit by the sun.
		float hy = clamp(y / fog_top_abs, 0.0, 1.3);
		vec3 col = mix(deep_color, body_color, smoothstep(0.05, 0.6, hy));
		vec4 n2 = texture(noise_tex, (p.xz + drift + normalize(light_dir.xz) * 5.0) / 66.0);
		float facing = clamp(0.5 + (n.r - n2.r) * 7.0, 0.0, 1.0);
		col = mix(col, lit_color, smoothstep(0.55, 1.15, hy) * (0.35 + 0.65 * facing));
		// Thin fog (edges, wisps) reads as light haze, not as a dark film.
		col = mix(col, haze_color, (1.0 - smoothstep(0.15, 0.7, fogness * body)) * 0.7);
		col = mix(col, rim_color, (1.0 - fogness) * 0.10 * facing);
		acc += trans * a * col;
		trans *= 1.0 - a;
		if (trans < 0.02) {
			break;
		}
	}
	float alpha = 1.0 - trans;
	vec3 color = alpha > 0.0001 ? acc / alpha : body_color;
	// Explored but not currently watched: a light veil over the known forest (never the town).
	if (dim_strength > 0.0) {
		vec4 s = texture(state_tex, state_uv(surface.xz));
		float sight = 0.0;
		for (int i = 0; i < 8; i++) {
			if (i >= sight_count) break;
			vec4 c = sights[i];
			sight = max(sight, (1.0 - smoothstep(c.z * 0.7, c.z, distance(surface.xz, c.xy))) * c.w);
		}
		float town = 1.0 - step(56.0, max(abs(surface.x), abs(surface.z)));
		float explored = smoothstep(0.0, 3.0, (mix(s.g, s.r, reveal_t) - 0.5) * sdf_range);
		float veil = dim_strength * explored * (1.0 - town) * (1.0 - sight);
		// surface -> veil -> fog (back to front)
		float total = 1.0 - (1.0 - alpha) * (1.0 - veil);
		color = (color * alpha + (1.0 - alpha) * veil * body_color) / max(total, 1e-4);
		alpha = total;
	}
	if (alpha < 0.003) {
		discard;
	}
	ALBEDO = color;
	ALPHA = clamp(alpha, 0.0, 1.0);
}
