shader_type spatial;
render_mode blend_add, unshaded, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

// Overlay of the «После» view in the upgrade window (src/building_stage.gd): the parts that
// the next level adds glow warm gold. The level scenes of the architecture kit mark them
// with UV2.x > 0 (the time they appear while upgrading into this level); parts already
// standing on the previous level have UV2.x = 0 (tools/architecture/build.gd link_upgrades,
// godot/art/buildings-v6/build.gd). A steady glow and a rim make them read at a glance; the
// window renders this view only while it moves, so the breathing is a 2D light over it.

uniform vec4 glow : source_color = vec4(1.0, 0.76, 0.36, 1.0);
uniform float strength = 0.3;

varying float fresh;
varying vec3 world;

void vertex() {
	fresh = UV2.x > 0.0001 ? 1.0 : 0.0;
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	if (fresh < 0.5) {
		discard;
	}
	// Premium UI stage 4b: the parts keep their own texture; only a thin gold rim on the
	// silhouette and a faint diagonal glint (it slides over them as the pair turns) mark them.
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float rim = pow(1.0 - facing, 3.2);
	float glint = smoothstep(0.93, 1.0, sin(dot(world, vec3(0.9, 1.5, 0.7)) * 1.1));
	ALBEDO = glow.rgb * strength * (0.05 + 1.15 * rim + 0.45 * glint * (0.35 + facing));
}
