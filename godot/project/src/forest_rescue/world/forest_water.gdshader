shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled;

// «Лес потерянных» still water (atlas v2, art/01): the reedy lake where the river widens south of
// the bridge, the lily pond under the waterfall and the marsh pools in the south pines. Same
// painted palette as forest_river.gdshader; where a body overlaps the river channel both shaders
// compute the same depth (max of the river profile and the body bowl), so there is no seam.
// COLOR.a = 1 inside the body … 0 at its irregular shoreline (mesh built by ForestWater).

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 deep_color : source_color = vec3(0.16, 0.29, 0.34);
uniform vec3 mid_color : source_color = vec3(0.24, 0.40, 0.45);
uniform vec3 shallow_color : source_color = vec3(0.39, 0.55, 0.57);
uniform vec3 murky_color : source_color = vec3(0.30, 0.38, 0.30);     // reedy / marsh shallows
uniform vec3 pad_color : source_color = vec3(0.36, 0.52, 0.22);
uniform vec3 pad_light : source_color = vec3(0.55, 0.68, 0.30);
uniform vec3 flower_color : source_color = vec3(0.98, 0.86, 0.90);
uniform vec3 foam_color : source_color = vec3(0.90, 0.93, 0.92);
uniform float murk = 0.0;            // 0 clear lake .. 1 marsh
uniform float lily_density = 0.0;    // 0 none .. 1 dense lily pads
uniform float river_blend = 0.0;     // 1: the body touches the river channel (lake)
uniform vec4 falls_point = vec4(0.0, 0.0, 0.0, 0.0);   // xz of the fall's foot, radius, strength

varying vec3 world;

float river_center(float z) {
	float k = (z + 25.0) / 15.0;
	return z + 66.0 + 8.0 * sin(z * 0.068) + 3.5 * cos(z * 0.127 + 0.3) + 9.0 * exp(-k * k);
}

float river_depth(vec2 p) {
	float hw = 4.3 + 0.65 * sin(p.y * 0.093 + 1.4) + 0.9;
	float u = abs(p.x - river_center(p.y)) / hw;
	return 1.0 - smoothstep(0.25, 0.95, u);
}

vec2 hash2(vec2 p) {
	p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
	return fract(sin(p) * 43758.5453);
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world.xz;
	float inner = COLOR.a;                          // 1 deep inside .. 0 shore
	float ripple = texture(noise_tex, p / 6.0 + vec2(TIME * 0.015, TIME * 0.01)).g;
	float depth = smoothstep(0.0, 1.0, inner + (ripple - 0.5) * 0.12);
	depth = max(depth, river_depth(p) * river_blend);
	vec3 col = mix(shallow_color, mix(mid_color, deep_color, smoothstep(0.35, 1.0, depth)), smoothstep(0.0, 0.45, depth));
	col = mix(col, murky_color * (0.9 + 0.2 * ripple), murk * (1.0 - depth * 0.5));
	// soft painted sky glints on the still surface
	float glint = texture(noise_tex, p / 3.1 + vec2(TIME * 0.02, -TIME * 0.013)).b;
	col += vec3(0.07, 0.08, 0.08) * smoothstep(0.78, 0.95, glint * 0.7 + ripple * 0.3) * depth;
	// lily pads: one jittered pad per 1.1 m cell (notched discs), a few with a pale flower
	if (lily_density > 0.0) {
		vec2 cell = floor(p / 1.1);
		float pad = 0.0;
		float flower = 0.0;
		float shade = 0.0;
		for (int j = -1; j <= 1; j++) {
			for (int i = -1; i <= 1; i++) {
				vec2 c = cell + vec2(float(i), float(j));
				vec2 h = hash2(c);
				if (h.x > lily_density) continue;
				vec2 centre = (c + 0.2 + 0.6 * hash2(c + 7.1)) * 1.1;
				vec2 d = p - centre;
				float r = 0.22 + 0.2 * h.y;
				float ang = mod(atan(d.y, d.x) - h.x * 6.28318 + 3.14159, 6.28318) - 3.14159;
				float notch = step(abs(ang), 0.32);
				float disc = (1.0 - smoothstep(r - 0.03, r, length(d))) * (1.0 - notch);
				if (disc > pad) {
					pad = disc;
					shade = h.y;
					flower = step(0.82, fract(h.x * 13.7)) * (1.0 - smoothstep(0.05, 0.09, length(d)));
				}
			}
		}
		pad *= smoothstep(0.15, 0.45, inner);
		col = mix(col, mix(pad_color, pad_light, shade), pad);
		col = mix(col, flower_color, flower * pad);
	}
	// foam where the waterfall hits the pond
	if (falls_point.w > 0.0) {
		float fd = length(p - falls_point.xy) / max(falls_point.z, 0.01);
		float fn = texture(noise_tex, p / 1.3 + vec2(0.0, -TIME * 0.35)).r;
		float foam = (1.0 - smoothstep(0.35, 1.0, fd + (fn - 0.5) * 0.5)) * falls_point.w;
		col = mix(col, foam_color, clamp(foam, 0.0, 0.85));
	}
	// darker wet rim right at the shore
	col *= 1.0 - 0.16 * (1.0 - smoothstep(0.0, 0.35, inner));
	ALBEDO = col;
	ALPHA = smoothstep(0.0, 0.16, inner);
}
