shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, skip_vertex_transform;

// Fixed-view tree impostor (the city camera never rotates). INSTANCE_CUSTOM.a = atlas cell.
// The atlas is baked from the painted kit material with a linear tonemap, so the city's FILMIC
// tonemap is applied exactly once. In any other view (the sun's shadow pass) the quad turns to
// face that view, so far trees still cast a crown-shaped shadow for 2 triangles.
// Shares the canopy fade with forest_painted.gdshaderinc.

uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform float grid = 8.0;
uniform vec4 fade_circles[8];
uniform int fade_count = 0;
uniform float sway = 0.06;
uniform float alpha_cut = 0.5;

#include "res://src/forest_rescue/world/forest_fog_receiver.gdshaderinc"

varying flat float cell;
varying vec3 world;

const vec3 VIEW_DIR = vec3(-0.5414, -0.5991, -0.5414);   // normalize(-(75, 83, 75))

float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	int index = x + y * 4;
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[index] + 0.5) / 16.0;
}

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
	VERTEX = (VIEW_MATRIX * vec4(world, 1.0)).xyz;
	NORMAL = normalize((VIEW_MATRIX * vec4(cross(right, up), 0.0)).xyz);
}

void fragment() {
	vec2 cell_xy = vec2(mod(cell, grid), floor(cell / grid));
	vec4 c = texture(atlas, (cell_xy + clamp(UV, vec2(0.004), vec2(0.996))) / grid);
	// The quad stands at the crown centre: sample the fog where this texel's ray meets the tree
	// (approximation: the quad point itself) — buried parts erode, tops darken into silhouettes.
	vec3 fog = fog_receive(world, TIME);
	if (c.a * (1.0 - fog.x) < alpha_cut) {
		discard;
	}
	c.rgb = mix(mix(c.rgb, fog_veil_color, fog.z), fog_silhouette, fog.y);
	for (int i = 0; i < 8; i++) {
		if (i >= fade_count) break;
		vec4 f = fade_circles[i];
		float t = (world.y - f.y) / -VIEW_DIR.y;
		vec2 ground = world.xz + VIEW_DIR.xz * t;
		float k = 1.0 - smoothstep(f.w * 0.55, f.w, distance(ground, f.xz));
		if (world.y > f.y + 1.2 && k * 0.92 > bayer4(FRAGCOORD.xy)) {
			discard;
		}
	}
	ALBEDO = c.rgb;
}
