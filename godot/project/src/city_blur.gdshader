shader_type canvas_item;
render_mode unshaded;

// One-time blur of the city snapshot behind the construction strip (src/city_backdrop.gd):
// a 7x7 Gaussian (sigma 1.6 texels) at one sixth of the device resolution, rendered once per
// open. Stretched to the screen with bilinear filtering it reads as a deep, smooth blur.

uniform vec2 texel = vec2(0.005, 0.01);

void fragment() {
	vec3 sum = vec3(0.0);
	float total = 0.0;
	for (int y = -3; y <= 3; y++) {
		for (int x = -3; x <= 3; x++) {
			float w = exp(-float(x * x + y * y) / (2.0 * 1.6 * 1.6));
			sum += texture(TEXTURE, UV + vec2(float(x), float(y)) * texel).rgb * w;
			total += w;
		}
	}
	COLOR = vec4(sum / total, 1.0);
}
