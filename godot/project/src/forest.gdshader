shader_type spatial;
render_mode cull_back, depth_draw_opaque;

// Forest cards and impostors (godot/art/forest). Same look as the imported
// material (atlas x vertex colour, alpha tested), plus a dithered clearing:
// trees near an active fight fade out so the battle under the canopy is visible.

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform float cutoff = 0.42;
global uniform vec4 battle_focus;   // xyz centre, w radius; w = 0 when no fight is shown
varying vec3 tree_origin;

void vertex() {
	tree_origin = MODEL_MATRIX[3].xyz;
}

void fragment() {
	vec4 texel = texture(albedo_tex, UV);
	ALBEDO = texel.rgb * COLOR.rgb;
	float alpha = texel.a;
	if (battle_focus.w > 0.0) {
		float distance_xz = length(tree_origin.xz - battle_focus.xz);
		float keep = smoothstep(battle_focus.w * 0.55, battle_focus.w, distance_xz);
		// Ordered dither keeps it opaque (no blending, no sorting) while it fades.
		float pattern = fract(dot(floor(FRAGCOORD.xy), vec2(0.7548777, 0.5698403)));
		if (keep < 0.999 && keep <= pattern) {
			discard;
		}
	}
	ALPHA = alpha;
	ALPHA_SCISSOR_THRESHOLD = cutoff;
	ROUGHNESS = 0.9;
	SPECULAR = 0.3;
}
