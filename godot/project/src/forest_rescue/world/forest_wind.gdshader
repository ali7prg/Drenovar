shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

// «Лес потерянных» forest kit material with shader-only wind (clip lf_forest_wind, 8 s loop).
// Vertex colour COLOR_0 from the kit: R branch sway weight, G leaf flutter, B phase, A ambient occlusion.
// Instances get an extra phase from their world origin; all harmonics are integer multiples of
// the 8 s base frequency, so the motion loops exactly every 8 seconds.

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform bool use_albedo_texture = true;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool use_normal = false;
uniform sampler2D roughness_texture : filter_linear_mipmap, repeat_enable;
uniform bool use_roughness_texture = false;
uniform float roughness_value = 0.9;
uniform bool foliage = false;
uniform float alpha_cut = 0.0;
uniform bool vertex_wind = true;
uniform float wind_strength = 1.0;
uniform float sway_amplitude = 0.32;
uniform float flutter_amplitude = 0.055;
uniform vec2 wind_direction = vec2(0.83, 0.56);
uniform float loop_seconds = 8.0;
uniform vec3 tint = vec3(1.0);
// Dithered canopy fade around actors / pinned areas: (x, ground y, z, radius). Fragments whose
// view ray reaches the ground inside a circle are dithered away above 1.2 m (crowns), so actors
// under trees stay visible from the fixed city camera.
uniform vec4 fade_circles[8];
uniform int fade_count = 0;
varying vec3 world_pos;
const vec3 VIEW_DIR = vec3(-0.5414, -0.5991, -0.5414);

float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[x + y * 4] + 0.5) / 16.0;
}

varying float ao;
varying vec4 tone;      // INSTANCE_CUSTOM: hue shift, saturation scale, value scale, unused

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	tone = INSTANCE_CUSTOM;
	float instance_phase = fract(dot(origin.xz, vec2(0.0713, 0.1131)));
	float sway_weight;
	float flutter_weight;
	float phase;
	if (vertex_wind) {
		sway_weight = COLOR.r;
		flutter_weight = COLOR.g;
		phase = COLOR.b;
		ao = COLOR.a;
	} else {
		float h = clamp(VERTEX.y / 9.0, 0.0, 1.0);
		sway_weight = h * h * 0.6;
		flutter_weight = 0.0;
		phase = 0.0;
		ao = 1.0;
	}
	float a = 6.28318530718 * (TIME / loop_seconds + instance_phase + phase);
	float gust = 0.62 * sin(a) + 0.28 * sin(2.0 * a + 1.3) + 0.10 * sin(3.0 * a + 0.4);
	float flutter = sin(7.0 * a + VERTEX.x * 2.1 + VERTEX.z * 1.7) * 0.6 + sin(11.0 * a + VERTEX.y * 3.3) * 0.4;
	// Model-space wind direction (instances may be rotated; keep the world wind coherent).
	vec3 world_wind = vec3(wind_direction.x, 0.0, wind_direction.y);
	vec3 local_wind = normalize((inverse(MODEL_MATRIX) * vec4(world_wind, 0.0)).xyz + vec3(1e-5));
	float scale = length(MODEL_MATRIX[0].xyz);
	VERTEX += local_wind * (gust * 0.55 + 0.45) * sway_weight * sway_amplitude * wind_strength / max(scale, 0.01);
	VERTEX += NORMAL * flutter * flutter_weight * flutter_amplitude * wind_strength;
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 base = albedo_color;
	if (use_albedo_texture) {
		base *= texture(albedo_texture, UV);
	}
	for (int i = 0; i < 8; i++) {
		if (i >= fade_count) break;
		vec4 f = fade_circles[i];
		float t = (world_pos.y - f.y) / -VIEW_DIR.y;
		vec2 ground = world_pos.xz + VIEW_DIR.xz * t;
		float k = 1.0 - smoothstep(f.w * 0.55, f.w, distance(ground, f.xz));
		if (world_pos.y > f.y + 1.2 && k * 0.92 > bayer4(FRAGCOORD.xy)) {
			discard;
		}
	}
	vec3 color = base.rgb;
	if (foliage && tone.b > 0.0 && (tone.r != 0.0 || tone.g != 1.0 || tone.b != 1.0)) {
		// rgb -> hsv, shift, back (per-instance seasonal variety of the shared foliage atlas)
		vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
		vec4 p = mix(vec4(color.bg, K.wz), vec4(color.gb, K.xy), step(color.b, color.g));
		vec4 q = mix(vec4(p.xyw, color.r), vec4(color.r, p.yzx), step(p.x, color.r));
		float d = q.x - min(q.w, q.y);
		vec3 hsv = vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
		hsv.x = fract(hsv.x + tone.r);
		hsv.y = clamp(hsv.y * tone.g, 0.0, 1.0);
		hsv.z = clamp(hsv.z * tone.b, 0.0, 1.0);
		vec3 rgb = clamp(abs(mod(hsv.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
		color = hsv.z * mix(vec3(1.0), rgb, hsv.y);
	}
	ALBEDO = color * tint * mix(0.42, 1.0, ao * ao);
	if (use_roughness_texture) {
		ROUGHNESS = texture(roughness_texture, UV).g;
	} else {
		ROUGHNESS = roughness_value;
	}
	if (use_normal) {
		NORMAL_MAP = texture(normal_texture, UV).rgb;
	}
	if (foliage) {
		ALPHA = base.a;
		ALPHA_SCISSOR_THRESHOLD = max(alpha_cut, 0.35);
		BACKLIGHT = base.rgb * 0.35;
		SPECULAR = 0.2;
	} else {
		SPECULAR = 0.3;
	}
}
