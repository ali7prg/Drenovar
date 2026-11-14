shader_type spatial;
render_mode cull_back, depth_draw_opaque;

// Town ground of the town plan (src/town_plan.gd): R earth (lanes, yards), G paving
// (streets, town square, forecourts), B yard. Read from a 0.25 m mask in world space, so
// crossings merge without seams; edges are worn darker and earth edges are ragged.

uniform sampler2D mask : filter_linear, repeat_disable;
uniform vec4 area = vec4(-64.0, -64.0, 128.0, 128.0);
uniform sampler2D earth_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;

varying vec3 world;

float hash2(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash2(i), hash2(i + vec2(1.0, 0.0)), u.x), mix(hash2(i + vec2(0.0, 1.0)), hash2(i + vec2(1.0, 1.0)), u.x), u.y);
}

float cover(vec2 uv) {
	vec4 m = texture(mask, uv);
	return max(m.r, m.g);
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = (world.xz - area.xy) / area.zw;
	vec4 m = texture(mask, uv);
	float c = max(m.r, m.g);
	float paved = smoothstep(0.3, 0.7, m.g / max(c, 0.001));
	// Earth edges fray into the grass; paving keeps a clean line.
	float fray = (value_noise(world.xz * 2.3) - 0.5) * 0.5 * (1.0 - paved);
	if (c < 0.5 + fray) {
		discard;
	}
	vec2 o = vec2(0.45) / area.zw;
	float inner = min(min(cover(uv + vec2(o.x, 0.0)), cover(uv - vec2(o.x, 0.0))),
		min(cover(uv + vec2(0.0, o.y)), cover(uv - vec2(0.0, o.y))));
	float edge = smoothstep(0.3, 1.0, inner);

	float patches = value_noise(world.xz * 0.45);
	// Trodden brown earth, a little darker where it is damp.
	// Two scales of the soil texture, so its tile never repeats visibly.
	vec3 soil = mix(texture(earth_tex, world.xz * 0.23).rgb, texture(earth_tex, world.xz * 0.071 + 0.37).rgb, 0.45);
	vec3 earth = soil * mix(vec3(0.66, 0.57, 0.45), vec3(0.8, 0.7, 0.55), patches);
	// Sparse grass in the yards, thicker towards their edges.
	float tuft = value_noise(world.xz * 3.1 + 11.0);
	float grassy = smoothstep(0.62, 0.8, tuft) * mix(0.35, 0.8, 1.0 - edge) * m.b;
	earth = mix(earth, vec3(0.26, 0.33, 0.16), grassy);

	// Setts in running bond.
	vec2 size = vec2(0.6, 0.4);
	vec2 s = world.xz / size;
	float row = floor(s.y);
	s.x += mod(row, 2.0) * 0.5;
	vec2 cell = floor(s);
	vec2 f = fract(s);
	vec2 gap = min(f, 1.0 - f) * size;
	float joint = smoothstep(0.012, 0.045, min(gap.x, gap.y));
	float shade = hash2(cell + vec2(row * 0.37, 1.7));
	vec3 stone = texture(stone_tex, world.xz * 0.45).rgb * mix(0.8, 1.1, shade) * vec3(1.02, 0.98, 0.9);
	// Gently domed stones: lighter centres.
	float dome = smoothstep(0.0, 0.16, min(gap.x, gap.y));
	vec3 setts = mix(stone * 0.42, stone * mix(0.92, 1.04, dome), joint);

	vec3 color = mix(earth, setts, paved);
	color *= mix(0.66, 1.0, edge);
	ALBEDO = color;
	ROUGHNESS = mix(0.96, 0.82, paved * joint);
	SPECULAR = 0.25;
}
