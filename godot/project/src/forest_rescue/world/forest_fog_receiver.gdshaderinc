// Fog awareness for everything standing in the forest (painted kit trees, landmarks, impostors).
// Mirrors forest_fog.gdshader's volume (same state/heightmap/noise textures and billow field):
// fog_cover(world) = how deep this fragment sits inside the fog volume (0 clear .. 1 buried),
// fog_tint(world)  = how much a fragment above the cloud top should read as a dark silhouette.
// Trees under fog are therefore either hidden (eroded/dithered away below the billowing cloud top)
// or soft dark silhouettes fading into the mist above it — never hard-cut slices by the shell.
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
uniform float fog_reveal_t = 1.0;
uniform float fog_drift_speed = 0.6;
uniform vec2 fog_wind = vec2(0.83, 0.56);
uniform vec3 fog_silhouette : source_color = vec3(0.27, 0.34, 0.40);

vec2 fog_uv(vec2 p) {
	return (p - fog_domain.xy) / fog_domain.zw;
}

float fog_billow(vec2 p, vec2 drift) {
	float big = texture(fog_noise_tex, (p + drift) / 92.0).r;
	float mid = texture(fog_noise_tex, (p - drift * 1.6) / 33.0 + vec2(0.37, 0.11)).g;
	return big * 0.66 + mid * 0.34;
}

uniform float fog_deep_top = 17.0;
uniform float fog_reveal_curl = 0.0;
uniform float fog_dim_strength = 0.0;
uniform vec4 fog_sights[8];
uniform int fog_sight_count = 0;
uniform vec3 fog_veil_color : source_color = vec3(0.26, 0.33, 0.39);

// Same edge field as forest_fog.gdshader (edge_offset): lobes + wind-elongated tendrils.
float fog_edge_offset(vec2 p, vec2 drift, float b) {
	vec2 wn = normalize(fog_wind);
	vec2 along = vec2(dot(p, wn), dot(p, vec2(-wn.y, wn.x)));
	float t1 = texture(fog_noise_tex, vec2(along.x / 38.0, along.y / 9.0) - vec2(drift.x * 0.03, 0.0) + vec2(0.13, 0.57)).r;
	float t2 = texture(fog_noise_tex, vec2(along.x / 17.0, along.y / 5.0) - vec2(drift.x * 0.05, 0.0) + vec2(0.61, 0.21)).g;
	return -2.6 + 3.0 * (b * 0.35 + t1 * 0.45 + t2 * 0.2) - fog_reveal_curl * 2.0 * t2;
}

// x = cover (hide: dithered/eroded away), y = silhouette tint, z = explored-veil dim (0..1)
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
		for (int i = 0; i < 8; i++) {
			if (i >= fog_sight_count) break;
			vec4 c = fog_sights[i];
			sight = max(sight, (1.0 - smoothstep(c.z * 0.75, c.z, distance(c.xy, p.xz))) * c.w);
		}
		float outside = smoothstep(56.0, 66.0, max(abs(p.x), abs(p.z)));
		veil = fog_dim_strength * smoothstep(0.0, 3.0, sdf) * outside * (1.0 - sight) * smoothstep(0.6, 1.6, y);
	}
	if (sdf > 3.0) {
		return vec3(0.0, 0.0, veil);
	}
	vec2 drift = fog_wind * time * fog_drift_speed;
	float b = fog_billow(p.xz, drift);
	float fogness = 1.0 - smoothstep(-1.5, 1.5, sdf + fog_edge_offset(p.xz, drift, b));
	float top = mix(s.a, s.b, local_t) * fog_height_range;
	float cloud = top * (0.6 + 0.8 * b);
	float buried = 1.0 - smoothstep(cloud - 1.5, cloud + 2.5, y);
	// Deep fog hides whole trees (no tops poking through the cloud sea), e.g. while a reveal runs.
	float deep = smoothstep(fog_deep_top * 0.45, fog_deep_top * 0.8, top);
	float tint = 1.0 - smoothstep(cloud + 1.0, cloud + 8.0, y);
	return vec3(fogness * max(buried, deep), fogness * mix(0.45, 0.8, tint), veil);
}
