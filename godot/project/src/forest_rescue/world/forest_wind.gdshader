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

varying float ao;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
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
}

void fragment() {
	vec4 base = albedo_color;
	if (use_albedo_texture) {
		base *= texture(albedo_texture, UV);
	}
	ALBEDO = base.rgb * tint * mix(0.62, 1.0, ao);
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
