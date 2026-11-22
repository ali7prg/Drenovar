shader_type canvas_item;

// Cards of building types built to their limit (src/build_card.gd): the whole card, art and
// text alike, in a light silver greyscale (the greys are lifted, not darkened, so the card
// reads as finished rather than switched off). One material shared by every such card.

uniform float lift = 0.2;
uniform float range = 0.74;

void fragment() {
	float luma = dot(COLOR.rgb, vec3(0.299, 0.587, 0.114));
	float silver = lift + range * pow(luma, 0.9);
	COLOR.rgb = vec3(silver) * vec3(0.965, 0.975, 1.0);
}
