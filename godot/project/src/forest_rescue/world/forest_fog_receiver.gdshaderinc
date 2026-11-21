// Fog awareness for everything standing in the forest (painted kit trees, landmarks, impostors).
// Mirrors forest_fog.gdshader's volume (same state/heightmap/noise textures and billow field):
// fog_cover(world) = how deep this fragment sits inside the fog volume (0 clear .. 1 buried),
// fog_tint(world)  = how much a fragment above the cloud top should read as a dark silhouette.
// Trees under fog fade smoothly into the mist colour below the billowing cloud top and take a
// soft light-mist tint above it (no erosion, no dither: a tree always keeps its whole crown);
// the alpha-blended fog shell drawn over them does the actual covering, and instances deeper
// than the blend band are culled on the CPU. Revealed cells receive nothing (the soft edge lies
// entirely on the fog side of the explored boundary, see fog_edge_offset).
// ForestFog pushes these uniforms (fog_enabled false = no fog, e.g. legacy/tests).

uniform bool fog_enabled = false;
uniform sampler2D fog_state_tex : filter_linear, repeat_disable;
uniform sampler2D fog_height_tex : filter_linear, repeat_disable;
uniform sampler2D fog_noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec4 fog_domain = vec4(-140.0, -140.0, 280.0, 280.0);
uniform float fog_height_range = 30.0;
uniform float fog_height_lo = -4.0;
uniform float fog_height_span = 40.0;
uniform float fog_sdf_range = 64.0;
// iPhone hot path: the reveal / dim / sight values are project-wide global uniforms (project.godot
// [shader_globals]) set once per change by ForestFog, not on every receiver material each frame
global uniform float fog_reveal_t;
uniform float fog_drift_speed = 0.6;
uniform vec2 fog_wind = vec2(0.83, 0.56);
uniform sampler2D fog_dome_tex : filter_linear_mipmap, repeat_enable;
uniform float fog_dome_tile = 84.0;
uniform vec3 fog_silhouette : source_color = vec3(0.370, 0.418, 0.449);   // light mist (fog haze)

vec2 fog_uv(vec2 p) {
	return (p - fog_domain.xy) / fog_domain.zw;
}

vec4 fog_cubic_weights(float v) {
	vec4 n = vec4(1.0, 2.0, 3.0, 4.0) - v;
	vec4 s = n * n * n;
	float x = s.x;
	float y = s.y - 4.0 * s.x;
	float z = s.z - 4.0 * s.y + 6.0 * s.x;
	float w = 6.0 - x - y - z;
	return vec4(x, y, z, w) * (1.0 / 6.0);
}

// Same B-spline state filter as forest_fog.gdshader (state_smooth).
vec4 fog_state_smooth(vec2 p) {
	vec2 size = vec2(textureSize(fog_state_tex, 0));
	vec2 px = fog_uv(p) * size - 0.5;
	vec2 f = fract(px);
	px -= f;
	vec4 xc = fog_cubic_weights(f.x);
	vec4 yc = fog_cubic_weights(f.y);
	vec4 c = px.xxyy + vec2(-0.5, 1.5).xyxy;
	vec4 sw = vec4(xc.xz + xc.yw, yc.xz + yc.yw);
	vec4 offset = (c + vec4(xc.yw, yc.yw) / sw) / size.xxyy;
	vec4 s0 = texture(fog_state_tex, offset.xz);
	vec4 s1 = texture(fog_state_tex, offset.yz);
	vec4 s2 = texture(fog_state_tex, offset.xw);
	vec4 s3 = texture(fog_state_tex, offset.yw);
	float sx = sw.x / (sw.x + sw.y);
	float sy = sw.z / (sw.z + sw.w);
	return mix(mix(s3, s2, sx), mix(s1, s0, sx), sy);
}

float fog_billow(vec2 p, vec2 drift) {
	float big = texture(fog_noise_tex, (p + drift) / 92.0).r;
	float mid = texture(fog_noise_tex, (p - drift * 1.6) / 33.0 + vec2(0.37, 0.11)).g;
	return big * 0.66 + mid * 0.34;
}

uniform float fog_deep_top = 17.0;
global uniform float fog_reveal_curl;
global uniform float fog_dim_strength;
global uniform vec4 fog_sight_0;
global uniform vec4 fog_sight_1;
global uniform vec4 fog_sight_2;
global uniform vec4 fog_sight_3;
global uniform vec4 fog_sight_4;
global uniform vec4 fog_sight_5;
global uniform vec4 fog_sight_6;
global uniform vec4 fog_sight_7;
global uniform int fog_sight_count;
uniform vec3 fog_veil_color : source_color = vec3(0.246, 0.300, 0.335);

// Same edge field as forest_fog.gdshader (edge_offset): lobes + wind-elongated tendrils. The offset
// is ≥ 0, so the fog never reaches into explored ground: fogness = 0 for sdf ≥ 0 and the lobes
// only push the soft edge further out into the fog cells (fog_edge_fogness).
float fog_edge_offset(vec2 p, vec2 drift, float b) {
	vec2 wn = normalize(fog_wind);
	vec2 along = vec2(dot(p, wn), dot(p, vec2(-wn.y, wn.x)));
	float t1 = texture(fog_noise_tex, vec2(along.x / 38.0, along.y / 9.0) - vec2(drift.x * 0.03, 0.0) + vec2(0.13, 0.57)).r;
	float t2 = texture(fog_noise_tex, vec2(along.x / 17.0, along.y / 5.0) - vec2(drift.x * 0.05, 0.0) + vec2(0.61, 0.21)).g;
	return 1.0 * clamp(b * 0.35 + t1 * 0.45 + t2 * 0.2, 0.0, 1.0) + fog_reveal_curl * 1.0 * t2;
}

// 0 on explored ground (sdf ≥ 0) → 1 inside the fog: a 2.5 m blend band (+ ≤ 1 m lobes) on the
// fog side of the boundary (delivery spec: opaque soft fog with a 2–3 m blend band).
float fog_edge_fogness(float sdf, float offset) {
	return 1.0 - smoothstep(-2.5, 0.0, sdf + offset);
}

// Same cloud-top relief as forest_fog.gdshader (domes / cloud_height).
float fog_domes(vec2 p, vec2 drift) {
	float a = textureLod(fog_dome_tex, (p + drift * 0.5) / fog_dome_tile, 1.5).r;
	float b = textureLod(fog_dome_tex, (p - drift * 0.35) / (fog_dome_tile / 2.3) + vec2(0.31, 0.67), 1.0).g;
	float swell = texture(fog_noise_tex, (p + drift * 0.2) / 170.0 + vec2(0.55, 0.15)).r;
	return clamp(a * 0.55 + b * 0.2 + swell * 0.4 - 0.08, 0.0, 1.0);
}

// x = cover (fade into the mist colour), y = silhouette tint, z = explored dim (0..≈0.09): known
// forest away from the squad and the mare stays visible slightly darker (a plain darkening, no
// haze colour); within the sight circles (reveal radius around squad / mare) it is exactly clean.
vec3 fog_receive(vec3 p, float time) {
	if (!fog_enabled) {
		return vec3(0.0);
	}
	vec4 s = texture(fog_state_tex, fog_uv(p.xz));
	float delay = texture(fog_noise_tex, p.xz / 41.0).a;
	float local_t = smoothstep(delay * 0.5, delay * 0.5 + 0.5, fog_reveal_t);
	float sdf = (mix(s.g, s.r, local_t) - 0.5) * fog_sdf_range;
	float y = p.y - (fog_height_lo + texture(fog_height_tex, fog_uv(p.xz)).r * fog_height_span);
	float veil = 0.0;
	if (fog_dim_strength > 0.0 && sdf > 0.0) {
		float sight = 0.0;
		vec4 fog_sights[8] = vec4[8](fog_sight_0, fog_sight_1, fog_sight_2, fog_sight_3, fog_sight_4, fog_sight_5, fog_sight_6, fog_sight_7);
		for (int i = 0; i < 8; i++) {
			if (i >= fog_sight_count) break;
			vec4 c = fog_sights[i];
			sight = max(sight, (1.0 - smoothstep(c.z, c.z * 1.4, distance(c.xy, p.xz))) * c.w);
		}
		float outside = smoothstep(56.0, 66.0, max(abs(p.x), abs(p.z)));
		veil = fog_dim_strength * smoothstep(0.0, 3.0, sdf) * outside * (1.0 - sight) * smoothstep(0.6, 1.6, y);
	}
	if (sdf >= 0.0) {
		return vec3(0.0, 0.0, veil);
	}
	vec2 drift = fog_wind * time * fog_drift_speed;
	float b = fog_billow(p.xz, drift);
	float fogness = fog_edge_fogness(sdf, fog_edge_offset(p.xz, drift, b));
	vec4 sm = fog_state_smooth(p.xz);
	float top = mix(sm.a, sm.b, local_t) * fog_height_range;
	float cloud = top * (0.86 + 0.28 * fog_domes(p.xz, drift));
	float buried = 1.0 - smoothstep(cloud - 1.5, cloud + 2.5, y);
	// Deep fog hides whole trees (no tops poking through the cloud sea), e.g. while a reveal runs.
	float deep = smoothstep(fog_deep_top * 0.45, fog_deep_top * 0.8, top);
	// Edge trees get a soft light-mist tint (stronger inside the fog band, subtle on revealed ground),
	// never a dark band.
	float tint = 1.0 - smoothstep(cloud + 1.0, cloud + 9.0, y);
	float side = mix(0.25, 1.0, 1.0 - smoothstep(-1.0, 1.0, sdf));
	return vec3(fogness * max(buried, deep), fogness * side * mix(0.3, 0.6, tint), veil);
}
