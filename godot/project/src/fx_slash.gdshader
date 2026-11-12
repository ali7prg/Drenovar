shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

// Weapon / claw sweep: a crescent whose bright head travels along the arc and
// leaves a fading trail. Camera-facing quad; `angle` turns it in screen space.
uniform vec4 tint : source_color = vec4(1.0, 0.85, 0.55, 1.0);
uniform float progress = 0.0;
uniform float angle = 0.0;
uniform float size = 2.0;

void vertex() {
	vec2 local = VERTEX.xy * size;
	float c = cos(angle);
	float s = sin(angle);
	VERTEX.xy = vec2(c * local.x - s * local.y, s * local.x + c * local.y);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float a = atan(p.y, p.x);            // -PI..PI
	float sweep = mix(-2.6, 2.2, progress);
	float behind = sweep - a;              // >0 where the head has passed
	float trail = smoothstep(0.0, 0.05, behind) * exp(-behind * 2.2);
	float width = mix(0.06, 0.24, clamp(1.0 - behind * 0.5, 0.0, 1.0));
	float band = 1.0 - smoothstep(width * 0.5, width, abs(r - 0.78));
	float core = 1.0 - smoothstep(0.0, width * 0.45, abs(r - 0.78));
	float fade = 1.0 - smoothstep(0.65, 1.0, progress);
	float alpha = band * trail * fade;
	ALBEDO = mix(tint.rgb, vec3(1.0), core * 0.7) * alpha * 2.6;
}
