shader_type spatial;
render_mode blend_add, unshaded, depth_draw_never, depth_test_disabled, cull_disabled, shadows_disabled, fog_disabled;

// Free plots while a new building is placed (premium UI stage 3, Landscape.show_plot_glow):
// a warm gold ring with a soft halo and a faint disc inside, breathing slowly. The chosen
// plot burns brighter. Drawn additively on a quad just above the ground, over trees and roofs,
// so a plot in the forest still shows.

uniform vec4 colour : source_color = vec4(1.0, 0.76, 0.34, 1.0);
uniform float strength = 0.78;
uniform float chosen = 0.0;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float pulse = 0.72 + 0.28 * sin(TIME * 2.6);
	float ring = exp(-pow((r - 0.74) / 0.045, 2.0));
	float halo = exp(-pow((r - 0.74) / 0.16, 2.0)) * 0.3;
	// The chosen plot's ghost stands inside the ring: its disc stays faint so the ghost reads.
	float disc = (1.0 - smoothstep(0.0, 0.78, r)) * (0.07 - 0.04 * chosen);
	float glow = (ring + halo) * mix(pulse, 1.0, chosen) + disc;
	glow *= 1.0 - smoothstep(0.92, 1.0, r);
	ALBEDO = colour.rgb * glow * strength * (1.0 + chosen * 0.9);
}
