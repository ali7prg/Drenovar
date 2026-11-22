shader_type canvas_item;

// Cards of building types built to their limit (src/build_card.gd): the whole card, art and
// text alike, desaturated and darker. One material shared by every such card.

uniform float amount = 0.94;
uniform float dim = 0.6;

void fragment() {
	float luma = dot(COLOR.rgb, vec3(0.299, 0.587, 0.114));
	COLOR.rgb = mix(COLOR.rgb, vec3(luma) * vec3(1.02, 1.0, 0.96), amount) * dim;
}
