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

// x = cover (hide), y = silhouette tint
vec2 fog_receive(vec3 p, float time) {
	if (!fog_enabled) {
		return vec2(0.0);
	}
	vec4 s = texture(fog_state_tex, fog_uv(p.xz));
	float sdf = (mix(s.g, s.r, fog_reveal_t) - 0.5) * fog_sdf_range;
	if (sdf > 3.0) {
		return vec2(0.0);
	}
	vec2 drift = fog_wind * time * fog_drift_speed;
	float b = fog_billow(p.xz, drift);
	float fogness = 1.0 - smoothstep(-2.2, 1.8, sdf - 3.0 + 4.0 * b);
	float top = mix(s.a, s.b, fog_reveal_t) * fog_height_range;
	float cloud = top * (0.45 + 1.0 * b);
	float y = p.y - (fog_height_lo + texture(fog_height_tex, fog_uv(p.xz)).r * fog_height_span);
	float buried = 1.0 - smoothstep(cloud - 1.5, cloud + 3.5, y);
	float tint = 1.0 - smoothstep(cloud + 2.0, cloud + 12.0, y);
	return vec2(fogness * buried, fogness * mix(0.55, 0.85, tint));
}
