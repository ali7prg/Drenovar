shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, skip_vertex_transform;

// Fixed-view tree impostor (the city camera never rotates). INSTANCE_CUSTOM: r/g = tree base x/z,
// b = shown (0 while the tree's occluder-fade copy draws it: the quad collapses), a = atlas cell.
// The atlas is baked from the painted kit material with a linear tonemap, so the city's FILMIC
// tonemap is applied exactly once. In any other view (the sun's shadow pass) the quad turns to
// face that view, so far trees still cast a crown-shaped shadow for 2 triangles.
// Fog like forest_painted.gdshaderinc: smooth mist fade, never erosion or dither.

uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform float grid = 8.0;
uniform float sway = 0.06;
uniform float alpha_cut = 0.5;
uniform bool grade_on = true;      // QA toggle (ForestImpostors.set_grade_enabled)

#include "res://src/forest_rescue/world/forest_fog_receiver.gdshaderinc"

varying flat float cell;
varying vec3 world;

const vec3 VIEW_DIR = vec3(-0.5414, -0.5991, -0.5414);   // normalize(-(75, 83, 75))

void vertex() {
	cell = INSTANCE_CUSTOM.a;
	vec3 origin = MODEL_MATRIX[3].xyz;
	float w = length(MODEL_MATRIX[0].xyz);
	float h = length(MODEL_MATRIX[1].xyz);
	vec3 right = MODEL_MATRIX[0].xyz / max(w, 1e-4);
	vec3 up = MODEL_MATRIX[1].xyz / max(h, 1e-4);
	vec3 forward = -INV_VIEW_MATRIX[2].xyz;
	if (dot(forward, VIEW_DIR) < 0.999) {
		right = INV_VIEW_MATRIX[0].xyz;
		up = INV_VIEW_MATRIX[1].xyz;
	}
	float phase = fract(dot(origin.xz, vec2(0.0713, 0.1131)));
	float a = 6.28318530718 * (TIME / 8.0 + phase);
	// Gentle top sway, base fixed (loops every 8 s like lf_forest_wind).
	float x = VERTEX.x + (UV.y < 0.5 ? 1.0 : 0.0) * sway * (0.62 * sin(a) + 0.28 * sin(2.0 * a + 1.3));
	world = origin + right * x * w + up * VERTEX.y * h;
	if (INSTANCE_CUSTOM.b < 0.5) {
		world = origin;           // hidden: drawn by its occluder-fade copy right now
	}
	VERTEX = (VIEW_MATRIX * vec4(world, 1.0)).xyz;
	NORMAL = normalize((VIEW_MATRIX * vec4(cross(right, up), 0.0)).xyz);
}

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

// Same art/01 region grade as forest_painted.gdshaderinc (impostors are always forest).
const vec3 GRADE_GROVE = vec3(1.52, 1.12, 1.0);
const vec3 GRADE_SOUTH = vec3(1.0, 1.0, 0.9);        // pass 4: blue-green pines, lifted shadows (crown_hsv.py)
const vec3 GRADE_EAST = vec3(0.88, 1.2, 0.86);
const vec3 GRADE_REST = vec3(1.1, 1.6, 1.0);
const vec3 GRADE_ARENA = vec3(1.18, 1.0, 1.0);     // arena rock sector (gorge, waterfall, arena)
const vec3 GRADE_LAKE = vec3(1.0, 0.95, 0.9);      // the reedy lake's shores (pass 4: no dark pines)
const vec2 GRADE_LAKE_CENTER = vec2(97.2, 32.4);
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

void fragment() {
	vec2 cell_xy = vec2(mod(cell, grid), floor(cell / grid));
	vec4 c = texture(atlas, (cell_xy + clamp(UV, vec2(0.004), vec2(0.996))) / grid, -0.6);   // crisp crowns at zoom 68-120
	if (c.a < alpha_cut) {
		discard;
	}
	// The quad stands at the crown centre: sample the fog where this texel's ray meets the tree
	// (approximation: the quad point itself) — buried parts fade into the mist colour, parts above
	// the cloud top take the soft mist tint. The whole tree always keeps its crown.
	vec3 fog = fog_receive(world, TIME);
	if (grade_on) {
		vec3 gf = grade_factors(world);
		float lum = max(dot(c.rgb, vec3(0.299, 0.587, 0.114)), 1e-4);
		c.rgb = max(mix(vec3(lum), c.rgb, gf.x), vec3(0.0));
		c.rgb *= max((lum - 0.32) * gf.y + 0.32, 0.0) * gf.z / lum;
	}
	c.rgb = mix(c.rgb * (1.0 - fog.z), fog_silhouette, max(fog.y, fog.x));
	ALBEDO = c.rgb;
}
