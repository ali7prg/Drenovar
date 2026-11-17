shader_type spatial;
render_mode cull_back, depth_draw_opaque;

// Forest cards and impostors (godot/art/forest). Same look as the imported
// material (atlas x vertex colour, alpha tested), plus a dithered clearing:
// trees near an active fight fade out so the battle under the canopy is visible.

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform float cutoff = 0.42;
global uniform vec4 battle_focus;   // xyz centre, w radius; w = 0 when no fight is shown
// The ground the fighting crowd stands on (xyz creature, w radius; 0 = none): trees
// there are gone for the fight, so the battle places can use it (combat_slots.gd).
global uniform vec4 battle_focus_core;
// Trees beside a marching column fade the same way (build 1021): the soldiers walking
// between them stay in sight and never stand in a trunk. On the world map also the
// trees around a creature (it is about as tall as they are). A small mask around the
// camera (landscape.update_march_clearing): r = 1 where a soldier walks.
global uniform sampler2D march_clear : filter_linear, repeat_disable;
global uniform vec4 march_clear_area; // x0, z0, size (m); w > 0 when the mask is in use
varying vec3 tree_origin;

void vertex() {
	tree_origin = MODEL_MATRIX[3].xyz;
}

void fragment() {
	vec4 texel = texture(albedo_tex, UV);
	ALBEDO = texel.rgb * COLOR.rgb;
	float alpha = texel.a;
	float keep = 1.0;
	if (battle_focus.w > 0.0) {
		float distance_xz = length(tree_origin.xz - battle_focus.xz);
		keep = smoothstep(battle_focus.w * 0.55, battle_focus.w, distance_xz);
		if (battle_focus_core.w > 0.0) {
			float core_xz = length(tree_origin.xz - battle_focus_core.xz);
			keep = min(keep, smoothstep(battle_focus_core.w, battle_focus_core.w * 1.3, core_xz));
		}
	}
	if (march_clear_area.w > 0.0) {
		vec2 uv = (tree_origin.xz - march_clear_area.xy) / march_clear_area.z;
		if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) {
			keep = min(keep, 1.0 - texture(march_clear, uv).r);
		}
	}
	// Ordered dither keeps it opaque (no blending, no sorting) while it fades.
	float pattern = fract(dot(floor(FRAGCOORD.xy), vec2(0.7548777, 0.5698403)));
	if (keep < 0.999 && keep <= pattern) {
		discard;
	}
	ALPHA = alpha;
	ALPHA_SCISSOR_THRESHOLD = cutoff;
	ROUGHNESS = 0.9;
	SPECULAR = 0.3;
}
