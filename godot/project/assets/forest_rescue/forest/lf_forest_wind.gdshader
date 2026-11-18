// lf_forest_wind — reference wind shader for the «Лес потерянных» forest kit (Godot 4.6, Mobile).
// Seamless 8 s loop (clip lf_forest_wind): all motion uses integer harmonics of TIME*2pi/loop_seconds.
// Vertex colour COLOR_0 (from the GLBs):  R = branch sway weight (0 trunk base -> 1 tips)
//                                          G = leaf flutter weight, B = per-branch phase 0..1
//                                          A = crown ambient occlusion (1 = open)
// Per-instance phase from the instance position, so MultiMesh forests never move in lockstep.
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D rough_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform bool use_normal_map = false;
uniform bool use_rough_map = false;
uniform bool alpha_test = true;
uniform float alpha_cutoff : hint_range(0.0, 1.0) = 0.5;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.85;
uniform float ao_strength : hint_range(0.0, 1.0) = 0.85;
uniform vec3 wind_dir = vec3(1.0, 0.0, 0.35);
uniform float wind_strength = 1.0;
uniform float trunk_amp = 0.05;     // metres at R=1 (scaled by R^2)
uniform float branch_amp = 0.16;    // metres at R=1
uniform float leaf_amp = 0.05;      // metres along the normal at G=1
uniform float loop_seconds = 8.0;
varying float v_ao;

void vertex() {
	float t = TIME * 6.2831853 / loop_seconds;
	float sway = COLOR.r;
	float flutter = COLOR.g;
	float phase = COLOR.b * 6.2831853;
	vec3 o = MODEL_MATRIX[3].xyz;
	float inst = fract(sin(dot(o.xz, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
	vec3 ldir = normalize((vec4(normalize(vec3(wind_dir.x, 0.0, wind_dir.z)), 0.0) * MODEL_MATRIX).xyz);
	float trunk = sway * sway * trunk_amp * (sin(t + inst) + 0.35 * sin(2.0 * t + inst * 1.3));
	float branch = sway * branch_amp * (0.6 * sin(2.0 * t + phase + inst) + 0.4 * sin(3.0 * t + phase * 1.7 + inst));
	float leaf = flutter * leaf_amp * sin(11.0 * t + phase * 3.1 + dot(VERTEX, vec3(3.1, 2.3, 2.9)));
	VERTEX += ldir * (trunk + branch) * wind_strength;
	VERTEX.y -= abs(branch) * 0.12 * sway * wind_strength;
	VERTEX += NORMAL * leaf * wind_strength;
	v_ao = mix(1.0, COLOR.a, ao_strength);
}

void fragment() {
	vec4 c = texture(albedo_tex, UV);
	ALBEDO = c.rgb * v_ao;
	if (alpha_test) {
		ALPHA = c.a;
		ALPHA_SCISSOR_THRESHOLD = alpha_cutoff;
	}
	ROUGHNESS = use_rough_map ? texture(rough_tex, UV).g : roughness_value;
	if (use_normal_map) {
		NORMAL_MAP = texture(normal_tex, UV).rgb;
	}
	// keep the authored (spherized) foliage normals on both card faces
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}
