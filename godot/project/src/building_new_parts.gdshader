shader_type spatial;
render_mode blend_add, unshaded, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

// Overlay of the «После» view in the upgrade window (src/building_stage.gd): the parts that
// the next level adds glow warm gold. The level scenes of the architecture kit mark them
// with UV2.x > 0 (the time they appear while upgrading into this level); parts already
// standing on the previous level have UV2.x = 0 (tools/architecture/build.gd link_upgrades,
// godot/art/buildings-v6/build.gd). A soft pulse and a rim make them read at a glance.

uniform vec4 glow : source_color = vec4(1.0, 0.74, 0.32, 1.0);
uniform float strength = 0.55;
uniform float pulse_speed = 1.6;

varying float fresh;

void vertex() {
	fresh = UV2.x > 0.0001 ? 1.0 : 0.0;
}

void fragment() {
	if (fresh < 0.5) {
		discard;
	}
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.0);
	float pulse = 0.62 + 0.38 * sin(TIME * pulse_speed);
	ALBEDO = glow.rgb * strength * pulse * (0.38 + 0.9 * rim);
}
