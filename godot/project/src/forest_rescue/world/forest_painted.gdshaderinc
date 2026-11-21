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

#ifdef FADE
render_mode unshaded, cull_disabled, depth_draw_always, fog_disabled;
#else
render_mode unshaded, cull_disabled, depth_draw_opaque;
#endif

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform bool use_albedo_texture = true;
// glTF baseColorTexture.texCoord == 1 (props whose painting projection lives in TEXCOORD_1:
// rune lock, winch, artifacts); set by actor_rig from the GLB header. Default: UV (TEXCOORD_0).
uniform bool albedo_uv2 = false;
// Captive look variation (humans/captive_variants.json) through <id>_variant_mask.png
// (R = cloth, G = hair, B = keep): albedo *= mix(1, tint_cloth, R) * mix(1, tint_hair, G).
uniform bool use_variant_mask = false;
uniform sampler2D variant_mask : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform vec3 tint_cloth = vec3(1.0);
uniform vec3 tint_hair = vec3(1.0);
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
// Whole-tree occluder fade (ForestOccluders): a tree that would hide an adventure actor from the
// fixed city camera is drawn by a separate copy with the FADE variant (forest_wind_fade*.gdshader)
// that composites it over the opaque scene behind it (screen copy) at `tree_opacity` (≥ 0.35) —
// a smooth single-layer fade of the WHOLE tree, never a dither or a crown cut. Its canopy
// instance is hidden meanwhile (INSTANCE_CUSTOM.r > 0.5 collapses the instance; plain meshes
// have INSTANCE_CUSTOM = 0).
#ifdef FADE
instance uniform float tree_opacity : hint_range(0.0, 1.0) = 1.0;
#endif

#include "res://src/forest_rescue/world/forest_fog_receiver.gdshaderinc"

varying float v_ao;
varying vec3 v_wn;
varying vec3 world_pos;
const vec3 VIEW_DIR = vec3(-0.5414, -0.5991, -0.5414);   // normalize(-(75, 83, 75)), city camera
#ifdef FADE
uniform sampler2D behind_tex : hint_screen_texture, filter_linear, repeat_disable;
#endif

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
	if (INSTANCE_CUSTOM.r > 0.5) {
		VERTEX = vec3(0.0);       // canopy instance drawn by its occluder-fade copy right now
	}
}

void fragment() {
	vec4 c = albedo_color;
	if (use_albedo_texture) {
		c *= texture(albedo_texture, albedo_uv2 ? UV2 : UV);
	}
	if (use_variant_mask) {
		vec3 m = texture(variant_mask, UV).rgb;
		c.rgb *= mix(vec3(1.0), tint_cloth, m.r) * mix(vec3(1.0), tint_hair, m.g);
	}
	// Under the fog: parts below the billowing cloud top fade smoothly into the mist colour, parts
	// above it take a soft mist tint (the shell drawn over them does the covering). No erosion.
	vec3 fog = fog_receive(world_pos, TIME);
#ifdef CUTOUT
	// Face normal from screen derivatives; orthographic views look along -Z in view space.
	vec3 fn = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	vec3 view_dir = PROJECTION_MATRIX[3][3] != 0.0 ? vec3(0.0, 0.0, 1.0) : normalize(-VERTEX);
	float ndv = abs(dot(fn, view_dir));
	float cut = c.a * smoothstep(edge_fade.x, edge_fade.y, ndv);
#ifdef FADE
	if (cut < alpha_cut) {
		discard;
	}
#else
	ALPHA = cut;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
#endif
#endif
	float lambert = max(dot(normalize(v_wn), normalize(light_dir_world)), 0.0);
	vec3 lit = c.rgb * mix(1.0, lambert, painted_light_mix) * v_ao;
	vec3 col = mix(lit * (1.0 - fog.z), fog_silhouette, max(fog.y, fog.x));
#ifdef FADE
	// Composite over the opaque scene (screen copy, this tree is not in it): every fragment that
	// survives the depth test replaces the pixel with the same blend, so overlapping cards of the
	// tree never double up — a uniform single-layer fade down to tree_opacity.
	vec3 behind = textureLod(behind_tex, SCREEN_UV, 0.0).rgb;
	ALBEDO = mix(behind, col, tree_opacity);
	ALPHA = 1.0;
#else
	ALBEDO = col;
#endif
}
