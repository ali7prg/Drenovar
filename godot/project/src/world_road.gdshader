shader_type spatial;

// The world map's roads (src/landscape.gd, build_world_roads): the «path» surface (albedo, normal
// and roughness maps) cut out below 0.05 alpha, both faces, lit like the StandardMaterial3D it
// replaces (Burley diffuse, Schlick-GGX specular 0.5, metallic 0, roughness from the map's red
// channel).
//
// 1023: the StandardMaterial3D drew the roads as black lines in the mobile renderer on the software
// Vulkan driver of the QA stills (lavapipe), while Forward+ and Compatibility drew them as light
// paths; this hand-written equivalent draws them as Forward+ does there.

render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_map : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_map : hint_roughness_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D roughness_map : hint_roughness_r, filter_linear_mipmap_anisotropic, repeat_enable;

void fragment() {
	vec4 colour = texture(albedo_map, UV);
	ALBEDO = colour.rgb;
	METALLIC = 0.0;
	SPECULAR = 0.5;
	ROUGHNESS = texture(roughness_map, UV).r;
	NORMAL_MAP = texture(normal_map, UV).rgb;
	NORMAL_MAP_DEPTH = 1.0;
	ALPHA = colour.a;
	ALPHA_SCISSOR_THRESHOLD = 0.05;
}
