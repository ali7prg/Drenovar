shader_type spatial;
render_mode blend_mix, depth_draw_always, cull_back, unshaded, shadows_disabled, fog_disabled;

// The ghost of a building being placed (premium UI stage 3, Landscape.attach_ghost): the
// building's own colours (its albedo map, sampled triplanar as the city's materials do, its
// colour and vertex colour), translucent, with a soft key light so the forms read and a warm
// rim. One shader; one material per surface of the level scene (uniforms only, so no
// shader is compiled when a plot is picked).

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float use_texture = 1.0;
uniform float triplanar = 1.0;
uniform float uv_scale = 0.75;
uniform float ghost_alpha = 0.66;
uniform vec4 rim_colour : source_color = vec4(1.0, 0.86, 0.55, 1.0);

varying vec3 tri_pos;
varying vec3 tri_weight;

void vertex() {
	tri_pos = VERTEX * uv_scale;
	vec3 w = pow(abs(NORMAL), vec3(4.0));
	tri_weight = w / max(dot(w, vec3(1.0)), 0.0001);
}

void fragment() {
	vec3 tex = texture(albedo_texture, tri_pos.zy * vec2(-1.0, -1.0)).rgb * tri_weight.x
		+ texture(albedo_texture, tri_pos.xz).rgb * tri_weight.y
		+ texture(albedo_texture, tri_pos.xy * vec2(1.0, -1.0)).rgb * tri_weight.z;
	vec3 flat_tex = texture(albedo_texture, UV).rgb;
	vec3 sampled = mix(flat_tex, tex, triplanar);
	vec3 base = mix(vec3(1.0), sampled, use_texture) * albedo_color.rgb * COLOR.rgb;
	vec3 n = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	float light = 0.62 + 0.5 * clamp(dot(n, normalize(vec3(-0.45, 0.8, 0.4))), 0.0, 1.0);
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.5);
	ALBEDO = base * light + rim_colour.rgb * rim * 0.4;
	ALPHA = clamp(ghost_alpha + rim * 0.22, 0.0, 1.0);
}
