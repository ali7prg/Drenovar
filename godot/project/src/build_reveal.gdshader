shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

// Construction / upgrade reveal for building level scenes (build 54).
// Same look as the architecture-v2 StandardMaterial3D (triplanar maps, vertex colour)
// or as a UV-mapped model material, plus a build clock:
//   mode 0  built from scratch: a part appears when build_t reaches COLOR.a
//   mode 1  upgrade, new level: parts with UV2.x > 0 appear at UV2.x (UV2.x = 0: already there)
//   mode 2  upgrade, old level: a part leaves at UV2.y (2 = stays until the swap)
//   mode 3  models without build data: rise course by course with the height
//   mode 4  models without build data, old level: taken down from the top
// A part that just appeared is lowered into place from above.

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D tex_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool use_albedo_tex = false;
uniform sampler2D tex_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform bool use_normal = false;
uniform float normal_scale = 1.0;
uniform sampler2D tex_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform bool use_rough = false;
uniform float roughness = 1.0;
uniform float metallic = 0.0;
uniform bool triplanar = true;
uniform bool use_vertex_color = true;
uniform vec3 uv_scale = vec3(1.0);
uniform vec3 emission_color : source_color = vec3(0.0);
uniform float emission_energy = 0.0;
uniform float alpha_cut = -1.0;

uniform float build_t = 1.0;
uniform int build_mode = 0;
uniform float build_top = 6.0;
uniform float drop = 0.9;

varying vec3 tri_pos;
varying vec3 tri_w;
varying float shown;

void vertex() {
	float key;
	bool leaving = build_mode == 2 || build_mode == 4;
	if (build_mode == 0) {
		key = COLOR.a;
	} else if (build_mode == 1) {
		key = UV2.x <= 0.0001 ? 9.0 : UV2.x;
	} else if (build_mode == 2) {
		key = UV2.y;
	} else if (build_mode == 3) {
		key = 0.06 + 0.86 * clamp(VERTEX.y / build_top, 0.0, 1.0);
	} else {
		key = 0.04 + 0.26 * (1.0 - clamp(VERTEX.y / build_top, 0.0, 1.0));
	}
	if (leaving) {
		shown = build_t < key ? 1.0 : 0.0;
	} else {
		shown = build_t >= key ? 1.0 : 0.0;
		float since = build_t - key;
		if (since >= 0.0 && since < 0.03) {
			float s = 1.0 - since / 0.03;
			VERTEX.y += drop * s * s;
		}
	}
	tri_w = pow(abs(NORMAL), vec3(4.0));
	tri_w /= max(dot(tri_w, vec3(1.0)), 0.0001);
	tri_pos = VERTEX * uv_scale * vec3(1.0, -1.0, 1.0);
}

vec4 sample_albedo(vec2 uv) {
	if (!triplanar) {
		return texture(tex_albedo, uv);
	}
	return texture(tex_albedo, tri_pos.xy) * tri_w.z + texture(tex_albedo, tri_pos.xz) * tri_w.y
		+ texture(tex_albedo, tri_pos.zy * vec2(-1.0, 1.0)) * tri_w.x;
}

vec4 sample_normal(vec2 uv) {
	if (!triplanar) {
		return texture(tex_normal, uv);
	}
	return texture(tex_normal, tri_pos.xy) * tri_w.z + texture(tex_normal, tri_pos.xz) * tri_w.y
		+ texture(tex_normal, tri_pos.zy * vec2(-1.0, 1.0)) * tri_w.x;
}

vec4 sample_rough(vec2 uv) {
	if (!triplanar) {
		return texture(tex_rough, uv);
	}
	return texture(tex_rough, tri_pos.xy) * tri_w.z + texture(tex_rough, tri_pos.xz) * tri_w.y
		+ texture(tex_rough, tri_pos.zy * vec2(-1.0, 1.0)) * tri_w.x;
}

void fragment() {
	if (shown < 0.5) {
		discard;
	}
	vec3 base = albedo.rgb;
	if (use_albedo_tex) {
		vec4 t = sample_albedo(UV);
		if (alpha_cut > 0.0 && t.a * albedo.a < alpha_cut) {
			discard;
		}
		base *= t.rgb;
	}
	if (use_vertex_color) {
		base *= COLOR.rgb;
	}
	ALBEDO = base;
	METALLIC = metallic;
	ROUGHNESS = use_rough ? roughness * sample_rough(UV).g : roughness;
	if (use_normal) {
		NORMAL_MAP = sample_normal(UV).rgb;
		NORMAL_MAP_DEPTH = normal_scale;
	}
	EMISSION = emission_color * emission_energy;
}
