shader_type spatial;

// The scenery atlas material (src/landscape.gd): city details and understory (ferns, berry and
// round bushes, fallen branches, mossy rocks, reeds), the world map's scenery and the props of the
// building previews. The atlas colour times the vertex colour, cut out below 0.36 alpha, lit like
// the StandardMaterial3D it replaces: Burley diffuse, Schlick-GGX specular 0.5, roughness 0.95,
// metallic 0, both faces.
//
// 1023: the StandardMaterial3D drew these as black shapes in the mobile renderer on the software
// Vulkan driver of the QA stills (lavapipe), while Forward+ and Compatibility drew them right; a
// hand-written equivalent with the same lighting draws the same picture as Forward+ there. It also
// samples one texture instead of three (the StandardMaterial3D samples its unused metallic and
// roughness maps too).

render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D atlas : source_color, filter_linear_mipmap_anisotropic, repeat_enable;

void fragment() {
	vec4 colour = texture(atlas, UV) * COLOR;
	ALBEDO = colour.rgb;
	METALLIC = 0.0;
	SPECULAR = 0.5;
	ROUGHNESS = 0.95;
	ALPHA = colour.a;
	ALPHA_SCISSOR_THRESHOLD = 0.36;
}
