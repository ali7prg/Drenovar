shader_type spatial;

// «Лес потерянных» ground (layout pass 4): the city ground shader (src/biome.gdshader, settlement branch)
// unchanged inside the base square — the code path is identical there, so the city ground renders the same —
// plus painted detail on the forest ring outside ±56: art/01 meadow colour with light / dark patches, grass
// strokes, moss and flower patches, scattered stones, a dark mossy floor with needles under the pines, and
// crisp warm-sand camp pads with a darker rim at every glade (pads[]). Set on the forest-touched ground
// tiles by ForestWorld only.

uniform sampler2D grass : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D earth : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D roughness_texture : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_roughness : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_roughness : filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool settlement = true;

uniform sampler2D detail_noise : filter_linear_mipmap, repeat_enable;   // RGBA tileable noise (ForestWorld)
uniform vec4 pads[16];               // camp pads: xz centre, radius, seed
uniform int pad_count = 0;
uniform vec3 meadow_mul = vec3(0.7, 0.45, 0.32);   // art/01 meadow (H≈49-58, S≈.5-.57, V≈.49-.56; pad_metrics / forest_metrics_v3)
uniform vec3 pad_color : source_color = vec3(0.66, 0.53, 0.37);   // renders ≈ warm sand (185, 150, 105) (pad_metrics.py)
uniform float detail_on = 1.0;

varying vec3 terrain_position;
varying vec3 terrain_normal;
varying vec3 world_pos;

void vertex() {
	terrain_position = VERTEX;
	terrain_normal = NORMAL;
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

vec3 forest_detail(vec3 albedo, vec3 grass_tex, vec2 p, float ring, vec2 uv, vec2 uv2, vec3 tint) {
	float earth_w = uv2.x;
	float rock_w = uv2.y;
	float tint_l = dot(tint, vec3(0.299, 0.587, 0.114));
	float meadow = (1.0 - earth_w) * (1.0 - rock_w);
	// shaded floor under the pines (the ground bake darkens it): needles + moss, no flowers
	float pine_floor = smoothstep(0.62, 0.42, tint_l);
	vec4 n_lo = texture(detail_noise, p / 23.0);
	vec4 n_mid = texture(detail_noise, p / 7.3 + vec2(0.37, 0.11));
	vec4 n_hi = texture(detail_noise, p / 2.1 + vec2(0.71, 0.53));
	// --- meadow: art/01 warm yellow-green with light / dark patches and grass strokes
	vec3 m = grass_tex * tint * meadow_mul;
	float patch = (n_lo.r - 0.5) * 0.9 + (n_mid.g - 0.5) * 0.55;
	m *= 1.0 + 0.2 * patch;
	m = mix(m, m * vec3(1.06, 1.0, 0.82), smoothstep(0.1, 0.4, patch));          // sunlit patches: warmer
	m = mix(m, m * vec3(0.86, 0.95, 0.9), smoothstep(-0.1, -0.4, patch));        // shaded patches: cooler
	float ang = n_lo.b * 3.1416;
	vec2 sp = mat2(vec2(cos(ang), sin(ang)), vec2(-sin(ang), cos(ang))) * p;
	float stroke = texture(detail_noise, sp * vec2(2.4, 0.42)).a;
	m *= 1.0 + 0.14 * (smoothstep(0.58, 0.82, stroke) - smoothstep(0.42, 0.18, stroke));
	// moss patches (darker, greener)
	float moss = smoothstep(0.6, 0.74, n_mid.a) * (0.45 + 0.55 * pine_floor);
	m = mix(m, vec3(0.13, 0.19, 0.07) * (0.85 + 0.3 * n_hi.r), moss * 0.55);
	// flower patches: sparse specks in clusters (white, yellow, pale violet), sunny meadow only
	vec2 cell = floor(p / 0.62);
	vec2 jit = hash22(cell);
	float h = hash12(cell + 17.3);
	float cluster = smoothstep(0.56, 0.78, n_lo.g);
	float flower_d = length(p - (cell + 0.2 + 0.6 * jit) * 0.62);
	float flower = step(h, 0.22 * cluster) * (1.0 - smoothstep(0.06, 0.1, flower_d)) * (1.0 - pine_floor);
	float hc = hash12(cell + 3.1);
	vec3 fcol = hc < 0.42 ? vec3(0.92, 0.9, 0.8) : (hc < 0.78 ? vec3(0.95, 0.78, 0.22) : vec3(0.72, 0.6, 0.86));
	m = mix(m, fcol, flower * 0.9);
	// needles under the pines: fine reddish-brown strokes over a dark moss floor
	float needles = smoothstep(0.55, 0.8, texture(detail_noise, sp * vec2(5.5, 0.9)).r);
	vec3 floor_col = mix(tint * grass_tex * vec3(0.62, 0.7, 0.62), vec3(0.2, 0.13, 0.08), needles * 0.45);
	m = mix(m, floor_col, pine_floor * 0.75);
	// scattered stones (lit top-left, shaded bottom-right)
	vec2 sc = floor(p / 2.3);
	vec2 sj = hash22(sc + 5.7);
	float sh = hash12(sc + 9.2);
	vec2 sd = p - (sc + 0.25 + 0.5 * sj) * 2.3;
	float sr = 0.14 + 0.2 * hash12(sc + 1.9);
	float stone = step(sh, 0.07) * (1.0 - smoothstep(sr * 0.85, sr, length(sd * vec2(1.0, 1.35))));
	vec3 scol = vec3(0.6, 0.58, 0.52) * (0.85 + 0.3 * clamp(dot(normalize(sd + vec2(0.001)), vec2(-0.7, -0.7)), -1.0, 1.0));
	m = mix(m, scol, stone * meadow);
	vec3 out_col = mix(albedo, m, meadow);
	// --- camp pads: crisp warm sand with a darker rim (art/01: every camp a focal point)
	for (int i = 0; i < 16; i++) {
		if (i >= pad_count) {
			break;
		}
		vec4 pd = pads[i];
		vec2 d = p - pd.xy;
		float dist = length(d);
		if (dist > pd.z + 3.0) {
			continue;
		}
		float a = atan(d.y, d.x);
		float edge = pd.z + 0.75 * sin(a * 5.0 + pd.w) + 0.45 * sin(a * 9.0 + pd.w * 1.7) + (n_mid.r - 0.5) * 0.8;
		float pad = 1.0 - smoothstep(edge - 0.35, edge + 0.1, dist);
		float soil = dot(texture(earth, uv * 0.85).rgb, vec3(0.333));
		vec3 sand = pad_color * (0.82 + 0.4 * soil) * (0.94 + 0.12 * n_hi.g);
		sand = mix(sand, sand * vec3(0.78, 0.72, 0.66), smoothstep(0.62, 0.8, n_hi.b) * 0.5);   // trampled darker spots
		float rim = smoothstep(edge - 1.05, edge - 0.45, dist) * (1.0 - smoothstep(edge - 0.2, edge + 0.25, dist));
		out_col = mix(out_col, sand, pad);
		out_col *= 1.0 - 0.28 * rim;
	}
	return mix(albedo, out_col, ring * detail_on);
}

void fragment() {
	vec3 land = texture(grass, UV).rgb;
	vec3 grass_tex = land;
	if (settlement) {
		land = mix(land, texture(earth, UV).rgb, UV2.x);
		land = mix(land, texture(rock, UV).rgb, UV2.y);
	} else {
		vec3 axis = pow(abs(normalize(terrain_normal)), vec3(4.0));
		axis /= max(0.001, axis.x + axis.y + axis.z);
		vec3 stone = texture(rock, terrain_position.yz / 5.0).rgb * axis.x
			+ texture(rock, terrain_position.xz / 5.0).rgb * axis.y
			+ texture(rock, terrain_position.xy / 5.0).rgb * axis.z;
		vec3 tint = vec3(0.96 + 0.045 * sin(terrain_position.x * 0.19 + sin(terrain_position.z * 0.11)), 0.985, 0.96);
		land = mix(land * tint, texture(earth, UV * 0.85).rgb, UV2.x * 0.8);
		land = mix(land, stone, UV2.y);
		land = mix(land, vec3(0.79, 0.82, 0.8), clamp((terrain_position.y - 25.0) / 4.0, 0.0, 1.0));
	}
	vec3 albedo = land * COLOR.rgb;
	float ring = smoothstep(56.5, 59.0, max(abs(world_pos.x), abs(world_pos.z)));
	if (ring > 0.0) {
		albedo = forest_detail(albedo, grass_tex, world_pos.xz, ring, UV, UV2, COLOR.rgb);
	}
	ALBEDO = albedo;
	NORMAL_MAP = texture(normal_texture, UV).rgb;
	NORMAL_MAP_DEPTH = settlement ? 0.51 : 0.24;
	ROUGHNESS = texture(roughness_texture, UV).r;
	if (settlement) {
		vec3 detail = mix(NORMAL_MAP * 2.0 - 1.0, texture(soil_normal, UV).rgb * 2.0 - 1.0, UV2.x);
		detail = mix(detail, texture(stone_normal, UV).rgb * 2.0 - 1.0, UV2.y);
		NORMAL_MAP = normalize(detail) * 0.5 + 0.5;
		ROUGHNESS = mix(ROUGHNESS, texture(soil_roughness, UV).r, UV2.x);
		ROUGHNESS = mix(ROUGHNESS, texture(stone_roughness, UV).r, UV2.y);
	}
}
