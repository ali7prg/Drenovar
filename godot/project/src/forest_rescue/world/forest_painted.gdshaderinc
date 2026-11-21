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
// Pass 2 colour grade of the forest materials only (kit vegetation, rocks, logs, landmarks; never the
// city): saturation and luminance contrast around a mid pivot, tuned per zone against art/01.
uniform bool grade_regions = false;      // ForestKit sets it on forest materials only
uniform float grade_pivot = 0.32;
// Pass 2 (art/01 quarry, art/08 arena cliffs): pale grey-beige limestone look for the kit moss
// rock (its cracks and shading kept, the golden moss washed out); 0 = painted texture as is.
uniform float limestone : hint_range(0.0, 1.0) = 0.0;
// Pass 2 (art/08 fossil wall): luminance contrast of the albedo around its mean (pale ribs and
// skull against the darker rock); 1 = as painted.
uniform float albedo_contrast = 1.0;
uniform float albedo_gain = 1.0;
// Pass 3 (art/01 waterfall): dark wet stone (desaturated, darkened, a cool sheen); 0 = as painted.
uniform float wet : hint_range(0.0, 1.0) = 0.0;
// Pass 4 (art/01 crown colour, set per species by ForestWorld): hue rotation (deg) and saturation of the
// albedo (pines toward blue-green teal, oaks toward golden olive), the AO floor of the vertex AO (lifts the
// shaded inner crown) and a half-wrapped painted light (no black backs; ForestKit for kit bark/foliage/rock).
uniform float hue_shift = 0.0;
uniform float albedo_sat = 1.0;
uniform float ao_floor = 0.42;
uniform bool wrap_light = false;
// Pass 4 (arena ring): world height of the ground under the limestone (strata / foot shadow); <-50 = off
uniform float limestone_base_y = -100.0;

float grade_sector(float phi, float a, float b, float blend) {
	float best = 0.0;
	for (int k = -1; k <= 1; k++) {
		float q = phi + 360.0 * float(k);
		best = max(best, smoothstep(a - blend, a + blend, q) * (1.0 - smoothstep(b - blend, b + blend, q)));
	}
	return best;
}

float grade_river_center(float z) {
	float k = (z + 25.0) / 15.0;
	return z + 66.0 + 8.0 * sin(z * 0.068) + 3.5 * cos(z * 0.127 + 0.3) + 9.0 * exp(-k * k);
}

// (saturation, luminance contrast, luminance) per art/01 region, tuned against the art/01 crops at
// zoom 68 (forest_rescue/qa/ingame/integration/grade_metrics.py: vegetation saturation and luminance
// contrast within ~10 % per zone). Contrast acts on luminance only (hue and saturation kept).
const vec3 GRADE_GROVE = vec3(1.52, 1.12, 1.0);
const vec3 GRADE_SOUTH = vec3(1.0, 1.0, 0.9);        // pass 4: blue-green pines, lifted shadows (crown_hsv.py)
const vec3 GRADE_EAST = vec3(0.88, 1.2, 0.86);
const vec3 GRADE_REST = vec3(1.1, 1.6, 1.0);
const vec3 GRADE_ARENA = vec3(1.18, 1.0, 1.0);     // arena rock sector (gorge, waterfall, arena)
const vec3 GRADE_LAKE = vec3(1.0, 0.95, 0.9);      // the reedy lake's shores (pass 4: no dark pines)
const vec2 GRADE_LAKE_CENTER = vec2(97.2, 32.4);
// (saturation, contrast, luminance) multipliers by art/01 region (city camera screen angle around the
// town, river side): saturated sunny golden grove / west oaks, dark misty south pines and east bank.
vec3 grade_factors(vec3 p) {
	float u = (p.x - p.z) * 0.70710678;
	float w = (p.x + p.z) * 0.70710678;
	float phi = degrees(atan(-w, u));
	phi = phi < 0.0 ? phi + 360.0 : phi;
	float outer = smoothstep(56.0, 66.0, max(abs(p.x), abs(p.z)));
	float east_raw = smoothstep(-4.0, 6.0, p.x - grade_river_center(p.z));
	float lake = 1.0 - smoothstep(18.0, 30.0, length(p.xz - GRADE_LAKE_CENTER));
	float arena = grade_sector(phi, -8.0, 62.0, 10.0) * (1.0 - lake);
	float east = east_raw * (1.0 - arena) * (1.0 - lake);
	float grove = grade_sector(phi, 58.0, 214.0, 12.0) * (1.0 - east_raw) * (1.0 - arena);
	float south = grade_sector(phi, 232.0, 345.0, 12.0) * (1.0 - east_raw) * (1.0 - lake);
	float rest = clamp(1.0 - grove - south - east - arena - lake, 0.0, 1.0);
	vec3 k = GRADE_GROVE * grove + GRADE_SOUTH * south + GRADE_EAST * east + GRADE_REST * rest
		+ GRADE_ARENA * arena + GRADE_LAKE * lake;
	return mix(vec3(1.0), k, outer);
}
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
	v_ao = use_ao ? mix(ao_floor, 1.0, COLOR.a * COLOR.a) : 1.0;
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
	if (hue_shift != 0.0 || albedo_sat != 1.0) {
		float ha = radians(hue_shift);
		vec3 k = vec3(0.57735027);
		vec3 rc = c.rgb * cos(ha) + cross(k, c.rgb) * sin(ha) + k * dot(k, c.rgb) * (1.0 - cos(ha));
		float lr = dot(rc, vec3(0.299, 0.587, 0.114));
		c.rgb = max(mix(vec3(lr), rc, albedo_sat), vec3(0.0));
	}
	if (limestone > 0.0) {
		float l = dot(c.rgb, vec3(0.299, 0.587, 0.114));
		// pass 4: warm beige limestone (art/01, art/08), the texture's noise strongly compressed (cracks kept),
		// horizontal strata bands and a darker foot (cast shadow / AO) over limestone_base_y
		float lc = 0.46 + (l - 0.42) * 0.42;
		vec3 pale = vec3(lc) * vec3(1.13, 0.99, 0.78);
		float band = sin(world_pos.y * 3.1 + 1.3 * sin(world_pos.x * 0.31 + world_pos.z * 0.23));
		pale *= 0.93 + 0.07 * smoothstep(-0.2, 0.6, band);
		if (limestone_base_y > -50.0) {
			pale *= mix(0.72, 1.0, smoothstep(0.0, 2.6, world_pos.y - limestone_base_y));
		}
		c.rgb = mix(c.rgb, clamp(pale, 0.0, 1.0), limestone);
	}
	if (wet > 0.0) {
		float l = dot(c.rgb, vec3(0.299, 0.587, 0.114));
		c.rgb = mix(c.rgb, vec3(l) * vec3(0.5, 0.56, 0.6) + vec3(0.02, 0.03, 0.04), wet);
	}
	if (albedo_contrast != 1.0 || albedo_gain != 1.0) {
		float l = dot(c.rgb, vec3(0.299, 0.587, 0.114));
		c.rgb = max(c.rgb + vec3((l - 0.36) * (albedo_contrast - 1.0)), vec3(0.0)) * albedo_gain;
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
	float ndl = dot(normalize(v_wn), normalize(light_dir_world));
	float lambert = wrap_light ? clamp(ndl * 0.6 + 0.4, 0.0, 1.0) : max(ndl, 0.0);
	vec3 lit = c.rgb * mix(1.0, lambert, painted_light_mix) * v_ao;
	if (grade_regions) {
		vec3 gf = grade_factors(world_pos);
		float lum = max(dot(lit, vec3(0.299, 0.587, 0.114)), 1e-4);
		lit = max(mix(vec3(lum), lit, gf.x), vec3(0.0));
		lit *= max((lum - grade_pivot) * gf.y + grade_pivot, 0.0) * gf.z / lum;
	}
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
