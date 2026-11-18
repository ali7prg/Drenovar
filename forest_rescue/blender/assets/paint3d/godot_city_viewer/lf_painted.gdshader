// QA viewer override for the v2 painted kit: the textures already carry the painted light, so the
// engine light is mixed in only partially:  ALBEDO_OUT = albedo * mix(1, lambert, painted_light_mix)
// (lambert = max(dot(N, L), 0) with the scene sun). Wind from COLOR_0 (R sway, G flutter, B phase),
// A = AO multiplied softly. Unshaded so no second lighting pass is added on top.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform bool alpha_test = true;
uniform float alpha_cutoff : hint_range(0.0, 1.0) = 0.5;
uniform float painted_light_mix : hint_range(0.0, 1.0) = 0.4;
uniform vec3 light_dir_world = vec3(-0.45, 0.70, 0.55);   // direction TO the light (Godot Y up)
uniform bool use_ao = true;
uniform vec2 edge_fade = vec2(0.10, 0.30);
uniform float wind_strength = 1.0;
uniform float loop_seconds = 8.0;
uniform vec3 wind_dir = vec3(1.0, 0.0, 0.35);
varying float v_ao;
varying vec3 v_wn;

void vertex() {
	float t = TIME * 6.2831853 / loop_seconds;
	float sway = COLOR.r;
	float flutter = COLOR.g;
	float phase = COLOR.b * 6.2831853;
	vec3 o = MODEL_MATRIX[3].xyz;
	float inst = fract(sin(dot(o.xz, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
	vec3 ldir = normalize((vec4(normalize(vec3(wind_dir.x, 0.0, wind_dir.z)), 0.0) * MODEL_MATRIX).xyz);
	float trunk = sway * sway * 0.05 * (sin(t + inst) + 0.35 * sin(2.0 * t + inst * 1.3));
	float branch = sway * 0.14 * (0.6 * sin(2.0 * t + phase + inst) + 0.4 * sin(3.0 * t + phase * 1.7 + inst));
	float leaf = flutter * 0.04 * sin(11.0 * t + phase * 3.1 + dot(VERTEX, vec3(3.1, 2.3, 2.9)));
	VERTEX += ldir * (trunk + branch) * wind_strength;
	VERTEX += NORMAL * leaf * wind_strength;
	v_ao = use_ao ? mix(0.42, 1.0, COLOR.a * COLOR.a) : 1.0;
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec4 c = texture(albedo_tex, UV) * albedo_color;
	if (alpha_test) {
		// cards seen edge-on fade out (face normal from screen derivatives)
		vec3 fn = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
		float ndv = abs(dot(fn, normalize(-VERTEX)));
		ALPHA = c.a * smoothstep(edge_fade.x, edge_fade.y, ndv);
		ALPHA_SCISSOR_THRESHOLD = alpha_cutoff;
	}
	float lambert = max(dot(normalize(v_wn), normalize(light_dir_world)), 0.0);
	ALBEDO = c.rgb * mix(1.0, lambert, painted_light_mix) * v_ao;
}
