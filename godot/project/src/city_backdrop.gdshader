shader_type canvas_item;
render_mode unshaded;

// Grade of the blurred city behind the construction strip (src/city_backdrop.gd): a little
// less colour, darker (the cards and the rail must read on it), a warm cast, a vignette that
// deepens toward the edges and under the cards. One texture read per pixel.

uniform bool plain = false;
uniform float dim = 0.6;
uniform float saturation = 0.8;
uniform vec3 warm = vec3(1.06, 0.96, 0.84);

void fragment() {
	vec3 colour = plain ? mix(vec3(0.16, 0.12, 0.09), vec3(0.08, 0.06, 0.05), UV.y) : texture(TEXTURE, UV).rgb;
	float luma = dot(colour, vec3(0.299, 0.587, 0.114));
	colour = mix(vec3(luma), colour, saturation) * warm * dim;
	vec2 centred = (UV - vec2(0.56, 0.42)) * vec2(1.0, 1.25);
	float vignette = smoothstep(0.95, 0.25, length(centred));
	float floor_shade = mix(1.0, 0.72, smoothstep(0.55, 1.0, UV.y));
	colour *= mix(0.62, 1.0, vignette) * floor_shade;
	COLOR = vec4(colour, 1.0);
}
