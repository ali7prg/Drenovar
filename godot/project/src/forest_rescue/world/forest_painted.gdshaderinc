// «Лес потерянных» kit v2 painted material (forest + landmarks), shared by forest_wind.gdshader
// (opaque: bark, rock, wood, stone) and forest_wind_cutout.gdshader (alpha-tested cards).
// Port of forest_rescue/blender/assets/paint3d/godot_city_viewer/lf_painted.gdshader (forest_kit.json
// "shading"): the textures carry the painted light, so the sun is mixed in only partially
//   ALBEDO = albedo * mix(1, lambert(sun), painted_light_mix) * mix(0.42, 1, COLOR_0.a^2)
// painted_light_mix: meta paintedLightMix (trees 0.3, props/landmarks 0.35), lf_foliage_vol 0.5.
// Cards seen edge-on fade out: alpha *= smoothstep(0.10, 0.30, |dot(face normal, view dir)|).
// Wind from COLOR_0 (R sway 0 trunk base -> 1 tips, G leaf flutter, B per-branch phase), 8 s
// loop (all harmonics integer multiples of the base frequency), per-instance phase.
// Unshaded (no second lighting pass); still casts shadows and takes the city depth fog.

render_mode unshaded, cull_disabled, depth_draw_opaque;

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform bool use_albedo_texture = true;
uniform float alpha_cut = 0.5;
uniform float painted_light_mix : hint_range(0.0, 1.0) = 0.3;
uniform vec3 light_dir_world = vec3(0.45, 0.74, 0.5);   // direction TO the sun
uniform bool use_ao = true;
uniform vec2 edge_fade = vec2(0.10, 0.30);
uniform bool vertex_wind = true;
uniform float wind_strength = 1.0;
uniform float loop_seconds = 8.0;
uniform vec3 wind_dir = vec3(0.83, 0.0, 0.56);
uniform float trunk_amp = 0.05;
uniform float branch_amp = 0.14;
uniform float leaf_amp = 0.04;
// Dithered canopy fade around actors / pinned areas: (x, ground y, z, radius). Fragments whose
// view ray reaches the ground inside a circle are dithered away above 1.2 m (crowns), so actors
// under trees stay visible from the fixed city camera.
uniform vec4 fade_circles[8];
uniform int fade_count = 0;

#include "res://src/forest_rescue/world/forest_fog_receiver.gdshaderinc"

varying float v_ao;
varying vec3 v_wn;
varying vec3 world_pos;
const vec3 VIEW_DIR = vec3(-0.5414, -0.5991, -0.5414);   // normalize(-(75, 83, 75)), city camera

float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[x + y * 4] + 0.5) / 16.0;
}

void vertex() {
	vec3 o = MODEL_MATRIX[3].xyz;
	if (vertex_wind) {
		float t = TIME * 6.2831853 / loop_seconds;
		float sway = COLOR.r;
		float flutter = COLOR.g;
		float phase = COLOR.b * 6.2831853;
		float inst = fract(sin(dot(o.xz, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
		vec3 ldir = normalize((vec4(normalize(vec3(wind_dir.x, 0.0, wind_dir.z)), 0.0) * MODEL_MATRIX).xyz);
		float trunk = sway * sway * trunk_amp * (sin(t + inst) + 0.35 * sin(2.0 * t + inst * 1.3));
		float branch = sway * branch_amp * (0.6 * sin(2.0 * t + phase + inst) + 0.4 * sin(3.0 * t + phase * 1.7 + inst));
		float leaf = flutter * leaf_amp * sin(11.0 * t + phase * 3.1 + dot(VERTEX, vec3(3.1, 2.3, 2.9)));
		VERTEX += ldir * (trunk + branch) * wind_strength;
		VERTEX += NORMAL * leaf * wind_strength;
	}
	v_ao = use_ao ? mix(0.42, 1.0, COLOR.a * COLOR.a) : 1.0;
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 c = albedo_color;
	if (use_albedo_texture) {
		c *= texture(albedo_texture, UV);
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
	// Under the fog: buried parts erode away, parts above the cloud top darken into silhouettes.
	vec2 fog = fog_receive(world_pos, TIME);
#ifdef CUTOUT
	// Face normal from screen derivatives; orthographic views look along -Z in view space.
	vec3 fn = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	vec3 view_dir = PROJECTION_MATRIX[3][3] != 0.0 ? vec3(0.0, 0.0, 1.0) : normalize(-VERTEX);
	float ndv = abs(dot(fn, view_dir));
	ALPHA = c.a * smoothstep(edge_fade.x, edge_fade.y, ndv) * (1.0 - fog.x);
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
#else
	if (fog.x > 0.001 && fog.x * 1.05 > bayer4(FRAGCOORD.xy)) {
		discard;
	}
#endif
	float lambert = max(dot(normalize(v_wn), normalize(light_dir_world)), 0.0);
	ALBEDO = mix(c.rgb * mix(1.0, lambert, painted_light_mix) * v_ao, fog_silhouette, fog.y);
}
