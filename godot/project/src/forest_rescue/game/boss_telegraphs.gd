extends Node3D
## Ground telegraphs for «Пращур» (campaign.json boss.attacks), synced to the server battle
## timeline: frontal sector (jaw_arc), rear/side arc (tail_sweep), fixed lane (lane_charge,
## committed at the end of its telegraph) and two rings with explicit gaps (stomp_waves).
## Shapes are authored for the boss at scale 1.0 and scaled with it (scale_factor = meta
## recommendedScale 1.52). Look (art/08): thin glowing orange arcs over a faint warm fill;
## the arcs sweep outward while the telegraph fills, flare white-hot in the active window and
## fade during recovery. Presentation only: the server decides hits; the decal shows where/when.

const SHAPES := {
	"jaw_arc":{"kind":"sector", "inner":1.6, "outer":9.5, "from":-42.0, "to":42.0, "color":Color("#ff6a1a")},
	"tail_sweep":{"kind":"sector", "inner":2.6, "outer":11.5, "from":70.0, "to":290.0, "color":Color("#ff8a1e")},
	"lane_charge":{"kind":"lane", "width":4.4, "start":2.0, "length":22.0, "color":Color("#ff5a1a")},
	"stomp_waves":{"kind":"rings", "radii":[6.0, 11.0], "band":1.5, "color":Color("#ff9424")}
}
const KIND_ID := {"sector":0, "lane":1, "rings":2}
const FALLBACK_TIMING := {
	"jaw_arc":{"telegraphSeconds":2.4, "activeSeconds":0.45, "recoverySeconds":1.4},
	"tail_sweep":{"telegraphSeconds":3.0, "activeSeconds":0.65, "recoverySeconds":1.8},
	"lane_charge":{"telegraphSeconds":2.8, "activeSeconds":1.1, "recoverySeconds":2.0},
	"stomp_waves":{"telegraphSeconds":3.2, "waveActiveSeconds":0.4, "waveCount":2, "waveStartIntervalSeconds":0.9, "recoverySeconds":2.4}
}

var game: Node
var shader: Shader
var decals: Dictionary = {}
var schedule: Array = []
var schedule_key := ""
var warning := ""
var locked_dirs: Dictionary = {}
## Boss model scale (actor_director sets it from the boss meta recommendedScale).
var scale_factor := 1.0

func setup(owner_game: Node) -> void:
	game = owner_game
	name = "BossTelegraphs"
	shader = Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled, fog_disabled;
uniform vec4 tint : source_color = vec4(1.0, 0.48, 0.1, 1.0);
uniform float fill = 0.0;      // telegraph progress 0..1
uniform float active = 0.0;    // 1 inside the hit window
uniform float fade = 1.0;      // recovery fade-out
uniform int kind = 0;          // 0 sector, 1 lane, 2 rings
float glow_line(float x, float at, float core, float halo) {
	float d = abs(x - at);
	return smoothstep(core, core * 0.25, d) + 0.5 * smoothstep(halo, 0.0, d);
}
void fragment() {
	vec2 uv = UV;
	float ends = smoothstep(0.0, 0.1, uv.x) * smoothstep(1.0, 0.9, uv.x);
	float light = 0.0;
	float wash = 0.0;
	if (kind == 0) {
		// Sector (art/08): three close concentric arcs near the rim + the rim itself; a wavefront
		// sweeps outwards with the fill, everything flares in the active window.
		for (int i = 0; i < 3; i++) {
			float at = 0.62 + 0.13 * float(i);
			light += glow_line(uv.y, at, 0.035, 0.11) * (0.45 + 0.55 * step(at, fill + 0.04));
		}
		light += glow_line(uv.y, 0.975, 0.03, 0.09);
		light += glow_line(uv.y, fill, 0.04, 0.16) * (1.0 - active) * 0.7;
		wash = (0.05 + 0.12 * step(uv.y, fill)) * smoothstep(0.0, 0.3, uv.y);
		light *= ends;
		wash *= ends;
	} else if (kind == 1) {
		// Lane: glowing side edges, chevrons running forward, warm fill growing along it.
		float side = min(uv.x, 1.0 - uv.x);
		light = glow_line(side, 0.03, 0.04, 0.14);
		float chevron = fract(uv.y * 6.0 - abs(uv.x - 0.5) * 1.4 - TIME * 1.3);
		light += smoothstep(0.09, 0.0, abs(chevron - 0.5)) * 0.7 * step(0.1, side) * step(uv.y, fill + 0.05);
		wash = 0.05 + 0.12 * step(uv.y, fill);
		float tip = smoothstep(1.0, 0.88, uv.y) * smoothstep(0.0, 0.05, uv.y);
		light *= tip;
		wash *= tip;
	} else {
		// Ring band: a hot line at the centre (two thin echoes); in the active window the wave runs out.
		float wave = mix(0.5, fract(TIME * 2.4), active);
		light = glow_line(uv.y, 0.5, 0.09, 0.3) + 0.6 * glow_line(uv.y, 0.22, 0.05, 0.12) + 0.6 * glow_line(uv.y, 0.78, 0.05, 0.12);
		light += glow_line(uv.y, wave, 0.07, 0.22) * active;
		wash = 0.05 + 0.08 * fill;
		light *= ends;
		wash *= ends;
	}
	// Painted glow (art/08): saturated orange lines with a lighter core, a soft warm halo;
	// HDR brightness lifts them above the floor, the active window turns them hot.
	vec3 hot = vec3(1.0, 0.82, 0.45);
	float core = clamp(light - 0.55, 0.0, 1.0);
	vec3 col = mix(tint.rgb, hot, clamp(core * 0.8 + active * 0.3, 0.0, 1.0)) * (1.25 + 0.55 * active + 0.35 * core);
	float alpha = clamp(light * 0.85 + wash * (1.0 + active), 0.0, 0.92) * (0.55 + 0.45 * fill);
	ALBEDO = col;
	ALPHA = alpha * fade;
}
"""

func clear() -> void:
	for key in decals:
		if is_instance_valid(decals[key]):
			decals[key].queue_free()
	decals.clear()
	warning = ""

func current_warning() -> String:
	return warning

func timing(attack: String) -> Dictionary:
	var authored: Dictionary = game.content.boss_attack(attack)
	return authored if not authored.is_empty() else FALLBACK_TIMING.get(attack, FALLBACK_TIMING.jaw_arc)

func total_seconds(attack: String) -> float:
	var spec := timing(attack)
	if attack == "stomp_waves":
		var waves := int(spec.get("waveCount", 2))
		return float(spec.get("telegraphSeconds", 3.2)) + float(spec.get("waveStartIntervalSeconds", 0.9)) * (waves - 1) + float(spec.get("waveActiveSeconds", 0.4)) + float(spec.get("recoverySeconds", 2.4))
	return float(spec.get("telegraphSeconds", 2.4)) + float(spec.get("activeSeconds", 0.45)) + float(spec.get("recoverySeconds", 1.4))

## Builds [{attack, start, event}] from telegraph events (or attack events minus telegraph).
func build_schedule(fight: Dictionary) -> void:
	var key := String(fight.get("reportId", "")) + ":" + str((fight.get("timeline", []) as Array).size())
	if key == schedule_key:
		return
	schedule_key = key
	schedule.clear()
	locked_dirs.clear()
	var telegraphed := {}
	for event in fight.get("timeline", []):
		if String(event.get("type", "")) == "telegraph" and SHAPES.has(String(event.get("attack", ""))):
			var attack := String(event.attack)
			schedule.append({"attack":attack, "start":float(event.get("t", 0.0)), "event":event})
			telegraphed[attack + ":" + str(snappedf(float(event.get("t", 0.0)) + float(timing(attack).get("telegraphSeconds", 2.4)), 0.1))] = true
	for event in fight.get("timeline", []):
		if String(event.get("type", "")) != "attack" or String(event.get("actor", "boss")) != "boss":
			continue
		var attack := String(event.get("attack", ""))
		if not SHAPES.has(attack):
			continue
		var start := float(event.get("t", 0.0)) - float(timing(attack).get("telegraphSeconds", 2.4))
		if telegraphed.has(attack + ":" + str(snappedf(float(event.get("t", 0.0)), 0.1))):
			continue
		var duplicate := false
		for entry in schedule:
			if entry.attack == attack and absf(float(entry.start) - start) < 0.3:
				duplicate = true
			# Later waves of one stomp share the telegraph of the first wave.
			if entry.attack == attack and start > float(entry.start) and start < float(entry.start) + total_seconds(attack):
				duplicate = true
		if not duplicate:
			schedule.append({"attack":attack, "start":maxf(0.0, start), "event":event})
	schedule.sort_custom(func(a, b): return float(a.start) < float(b.start))

## Updates decals for the server elapsed time; returns the attack the boss is performing.
func update_from_battle(fight: Dictionary, elapsed: float, boss_pos: Vector3, boss_yaw: float, squad_pos: Vector3) -> Dictionary:
	build_schedule(fight)
	var current := {}
	var live := {}
	warning = ""
	var death_at := INF
	for event in fight.get("timeline", []):
		if String(event.get("type", "")) == "death":
			death_at = minf(death_at, float(event.get("t", 0.0)))
	for index in schedule.size():
		var entry: Dictionary = schedule[index]
		var local := elapsed - float(entry.start)
		if local < 0.0 or local > total_seconds(String(entry.attack)) or elapsed >= death_at:
			continue
		var attack := String(entry.attack)
		var id := "%s_%d" % [attack, index]
		live[id] = true
		var spec := timing(attack)
		var telegraph := float(spec.get("telegraphSeconds", 2.4))
		var direction := boss_yaw
		if squad_pos != Vector3.INF:
			direction = atan2(squad_pos.x - boss_pos.x, squad_pos.z - boss_pos.z)
		var event: Dictionary = entry.event
		if event.has("angle"):
			direction = float(event.angle)
		elif event.get("dir") is Dictionary:
			direction = atan2(float(event.dir.get("x", 0)), float(event.dir.get("z", 1)))
		if attack == "lane_charge":
			if local >= telegraph and not locked_dirs.has(id):
				locked_dirs[id] = direction
			if locked_dirs.has(id):
				direction = float(locked_dirs[id])
		draw_decal(id, attack, boss_pos, direction, local, spec, event)
		if local < telegraph + 0.2:
			warning = game.content.text("boss.telegraph." + attack)
		if current.is_empty() or local < float(current.local):
			current = {"attack":attack, "local":local}
	for id in decals.keys():
		if not live.has(id):
			if is_instance_valid(decals[id]):
				decals[id].queue_free()
			decals.erase(id)
	return current

func draw_decal(id: String, attack: String, boss_pos: Vector3, direction: float, local: float, spec: Dictionary, event: Dictionary) -> void:
	var shape: Dictionary = SHAPES[attack]
	var node: MeshInstance3D = decals.get(id)
	var key := "%s|%.2f|%.1f|%.1f|%.2f" % [attack, direction, boss_pos.x, boss_pos.z, scale_factor]
	if node == null or not is_instance_valid(node):
		node = MeshInstance3D.new()
		node.name = id
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var material := ShaderMaterial.new()
		material.shader = shader
		material.set_shader_parameter("tint", shape.color)
		material.set_shader_parameter("kind", KIND_ID.get(String(shape.kind), 0))
		node.material_override = material
		add_child(node)
		decals[id] = node
	if node.get_meta("key", "") != key:
		node.set_meta("key", key)
		node.mesh = build_mesh(attack, shape, boss_pos, direction, event)
	var material: ShaderMaterial = node.material_override
	var telegraph := float(spec.get("telegraphSeconds", 2.4))
	var fill := clampf(local / telegraph, 0.0, 1.0)
	var active := 0.0
	var fade := 1.0
	if attack == "stomp_waves":
		var interval := float(spec.get("waveStartIntervalSeconds", 0.9))
		var span := float(spec.get("waveActiveSeconds", 0.4))
		for wave in int(spec.get("waveCount", 2)):
			var begin := telegraph + interval * wave
			if local >= begin and local <= begin + span:
				active = 1.0
		var end := telegraph + interval * (int(spec.get("waveCount", 2)) - 1) + span
		if local > end:
			fade = clampf(1.0 - (local - end) / float(spec.get("recoverySeconds", 2.4)), 0.0, 1.0) * 0.6
	else:
		var span := float(spec.get("activeSeconds", 0.45))
		if local >= telegraph and local <= telegraph + span:
			active = 1.0
		elif local > telegraph + span:
			fade = clampf(1.0 - (local - telegraph - span) / float(spec.get("recoverySeconds", 1.4)), 0.0, 1.0) * 0.6
	# Soft fade-in over the first 0.3 s of the telegraph.
	fade *= clampf(local / 0.3, 0.0, 1.0)
	material.set_shader_parameter("fill", fill)
	material.set_shader_parameter("active", active)
	material.set_shader_parameter("fade", fade)
	node.position = boss_pos

## Mesh in boss-local XZ, draped on the terrain (height_at) and lifted 0.3 m (above the arena floor).
func build_mesh(attack: String, shape: Dictionary, boss_pos: Vector3, direction: float, event: Dictionary) -> ArrayMesh:
	var k := scale_factor
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var basis := Basis(Vector3.UP, direction)
	match String(shape.kind):
		"sector":
			add_arc(surface, basis, boss_pos, float(shape.inner) * k, float(shape.outer) * k, deg_to_rad(float(shape.from)), deg_to_rad(float(shape.to)), 40)
		"lane":
			var w := float(shape.width) * 0.5 * k
			var start := float(shape.start) * k
			var length := float(shape.length) * k
			var steps := 16
			for i in steps:
				var a := start + length * float(i) / steps
				var b := start + length * float(i + 1) / steps
				var quad := [Vector3(-w, 0, a), Vector3(w, 0, a), Vector3(w, 0, b), Vector3(-w, 0, b)]
				var uvs := [Vector2(0, float(i) / steps), Vector2(1, float(i) / steps), Vector2(1, float(i + 1) / steps), Vector2(0, float(i + 1) / steps)]
				add_quad(surface, basis, boss_pos, quad, uvs)
		"rings":
			var gaps: Array = event.get("gaps", [])
			var radii: Array = shape.radii
			for ring in radii.size():
				var center_angles: Array = []
				if gaps.size() > ring and gaps[ring] is Array:
					for value in gaps[ring]:
						center_angles.append(deg_to_rad(float(value)))
				else:
					for g in 3:
						center_angles.append(deg_to_rad(40.0 + 120.0 * g + 60.0 * ring))
				var gap_half := deg_to_rad(15.0)
				var r := float(radii[ring]) * k
				var band := float(shape.band) * 0.5 * k
				var segments := 96
				var open := []
				for s in segments:
					var mid := TAU * (float(s) + 0.5) / segments
					var in_gap := false
					for c in center_angles:
						if absf(angle_difference(mid, float(c))) < gap_half:
							in_gap = true
					open.append(not in_gap)
				var first_gap := open.find(false)
				if first_gap < 0:
					add_arc(surface, Basis.IDENTITY, boss_pos, r - band, r + band, 0.0, TAU, segments)
					continue
				var run_start := -1
				for step in segments + 1:
					var s := (first_gap + step) % segments
					var is_open: bool = open[s] and step < segments
					if is_open and run_start < 0:
						run_start = step
					elif not is_open and run_start >= 0:
						var a0 := TAU * float(first_gap + run_start) / segments
						var a1 := TAU * float(first_gap + step) / segments
						add_arc(surface, Basis.IDENTITY, boss_pos, r - band, r + band, a0, a1, step - run_start)
						run_start = -1
	surface.generate_normals()
	return surface.commit()

func add_arc(surface: SurfaceTool, basis: Basis, origin: Vector3, inner: float, outer: float, from: float, to: float, segments: int) -> void:
	for s in segments:
		var a0 := lerpf(from, to, float(s) / segments)
		var a1 := lerpf(from, to, float(s + 1) / segments)
		var quad := [Vector3(sin(a0) * inner, 0, cos(a0) * inner), Vector3(sin(a0) * outer, 0, cos(a0) * outer),
			Vector3(sin(a1) * outer, 0, cos(a1) * outer), Vector3(sin(a1) * inner, 0, cos(a1) * inner)]
		var u0 := float(s) / segments
		var u1 := float(s + 1) / segments
		add_quad(surface, basis, origin, quad, [Vector2(u0, 0), Vector2(u0, 1), Vector2(u1, 1), Vector2(u1, 0)])

func add_quad(surface: SurfaceTool, basis: Basis, origin: Vector3, quad: Array, uvs: Array) -> void:
	var lifted := []
	for corner in quad:
		var world := origin + basis * (corner as Vector3)
		var ground: Vector3 = game.ground(world.x, world.z)
		lifted.append(basis * (corner as Vector3) + Vector3(0, ground.y - origin.y + 0.3, 0))
	for i in [0, 1, 2, 0, 2, 3]:
		surface.set_uv(uvs[i])
		surface.add_vertex(lifted[i])
