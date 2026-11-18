shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

// Fixed-view tree impostor (city camera never rotates). INSTANCE_CUSTOM: rgb = foliage tone
// (hue shift, saturation, value), a = atlas cell. Shares the canopy fade with forest_wind.

uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform float grid = 8.0;
uniform vec4 fade_circles[8];
uniform int fade_count = 0;
uniform float sway = 0.06;

varying vec4 tone;
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
	tone = INSTANCE_CUSTOM;
	vec3 origin = MODEL_MATRIX[3].xyz;
	float phase = fract(dot(origin.xz, vec2(0.0713, 0.1131)));
	float a = 6.28318530718 * (TIME / 8.0 + phase);
	// Gentle top sway, base fixed (loops every 8 s like lf_forest_wind).
	VERTEX.x += (UV.y < 0.5 ? 1.0 : 0.0) * sway * (0.62 * sin(a) + 0.28 * sin(2.0 * a + 1.3));
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float cell = tone.a;
	vec2 cell_xy = vec2(mod(cell, grid), floor(cell / grid));
	vec4 c = texture(atlas, (cell_xy + clamp(UV, vec2(0.004), vec2(0.996))) / grid);
	if (c.a < 0.5) {
		discard;
	}
	vec3 color = c.rgb;
	if (tone.b > 0.0 && (tone.r != 0.0 || tone.g != 1.0 || tone.b != 1.0)) {
		vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
		vec4 p = mix(vec4(color.bg, K.wz), vec4(color.gb, K.xy), step(color.b, color.g));
		vec4 q = mix(vec4(p.xyw, color.r), vec4(color.r, p.yzx), step(p.x, color.r));
		float d = q.x - min(q.w, q.y);
		vec3 hsv = vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
		// Only shift foliage-like texels (keep bark and deep shade).
		float leafy = smoothstep(0.18, 0.4, hsv.y) * smoothstep(0.08, 0.25, hsv.z);
		hsv.x = fract(hsv.x + tone.r * leafy);
		hsv.y = clamp(hsv.y * mix(1.0, tone.g, leafy), 0.0, 1.0);
		hsv.z = clamp(hsv.z * mix(1.0, tone.b, leafy), 0.0, 1.0);
		vec3 rgb = clamp(abs(mod(hsv.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
		color = hsv.z * mix(vec3(1.0), rgb, hsv.y);
	}
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
	ALBEDO = color;
}
