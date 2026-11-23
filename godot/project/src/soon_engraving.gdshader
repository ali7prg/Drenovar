shader_type canvas_item;

// The «Скоро» card of the building window (src/building_stage.gd, 1023): the current level's card
// art as a warm gold engraving on the card's dark enamel. The next level stays veiled, the shape
// stays readable (a flat dark silhouette read as a black smudge on the enamel).

uniform vec3 shadow_tone : source_color = vec3(0.32, 0.22, 0.12);
uniform vec3 light_tone : source_color = vec3(1.0, 0.88, 0.62);
uniform float strength = 0.86;

void fragment() {
	float luma = dot(COLOR.rgb, vec3(0.299, 0.587, 0.114));
	COLOR.rgb = mix(shadow_tone, light_tone, smoothstep(0.04, 0.72, luma));
	COLOR.a *= strength;
}
