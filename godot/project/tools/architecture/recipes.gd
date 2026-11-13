extends RefCounted
## Level recipes for the 40 positions listed in DRENOVAR CHANGES.md (20 series).
## Every function returns a spec; geometry goes into the kit (k).
## Main entrance faces +Z on every level; footprint stays inside the 14 x 14 m plot.

const ENTRIES := [
	{"series": "B01_TownHall", "type": "ECO-05", "level": 1, "fn": "b01_hall"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 2, "fn": "b01_hall"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 5, "fn": "b01_hall"},
	{"series": "B03_Warehouse", "type": "ECO-01", "level": 5, "fn": "b03_warehouse"},
	{"series": "B05_Marketplace", "type": "ECO-03", "level": 5, "fn": "b05_market"},
	{"series": "B06_LumberCamp", "type": "RES-01", "level": 5, "fn": "b06_lumber"},
	{"series": "B07_StoneQuarry", "type": "RES-02", "level": 5, "fn": "b07_quarry"},
	{"series": "B08_IronMine", "type": "RES-03", "level": 5, "fn": "b08_mine"},
	{"series": "B09_Farm", "type": "RES-04", "level": 3, "fn": "b09_farm"},
	{"series": "B09_Farm", "type": "RES-04", "level": 5, "fn": "b09_farm"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 4, "fn": "b11_barracks"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 5, "fn": "b11_barracks"},
	{"series": "B13_Stables", "type": "MIL-03", "level": 3, "fn": "b13_stables"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 3, "fn": "b14_smith"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 4, "fn": "b14_smith"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 5, "fn": "b14_smith"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 1, "fn": "b15_academy"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 2, "fn": "b15_academy"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 3, "fn": "b15_academy"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 4, "fn": "b15_academy"},
	{"series": "B16_Infirmary", "type": "SUP-01", "level": 5, "fn": "b16_infirmary"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 1, "fn": "b17_workshop"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 4, "fn": "b17_workshop"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 5, "fn": "b17_workshop"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 1, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 2, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 3, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 4, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 5, "fn": "b18_gate"},
	{"series": "B19_Watchtower", "type": "SUP-04", "level": 5, "fn": "b19_watchtower"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 1, "fn": "b21_sawmill"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 4, "fn": "b21_sawmill"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 5, "fn": "b21_sawmill"},
	{"series": "B23_HuntingLodge", "type": "ALT-06", "level": 5, "fn": "b23_lodge"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 2, "fn": "b24_fishing"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 3, "fn": "b24_fishing"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 4, "fn": "b24_fishing"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 5, "fn": "b24_fishing"},
	{"series": "B25_HerbalGarden", "type": "ALT-08", "level": 5, "fn": "b25_herbal"},
	{"series": "B26_StoneWorkshop", "type": "ALT-09", "level": 1, "fn": "b26_stoneworks"},
]

static func base(id: String, masks: Array = []) -> Dictionary:
	return {"base": {"id": id, "masks": masks}}

static func box_mask(from: Vector3, to: Vector3) -> AABB:
	return AABB(Vector3(minf(from.x, to.x), minf(from.y, to.y), minf(from.z, to.z)), (to - from).abs())

# ============================================================== B18 Walls and Gate (SUP-03)
const GATE_HALF := 1.5      # clear opening half-width (3.0 m carriageway)
const GATE_CLEAR := 3.2     # clear height under any lintel / floor

static func b18_gate(k, L: int) -> Dictionary:
	var wall_end := 5.6
	# packed earth road through the gate, flush with grade (no threshold or kerb)
	k.road(Vector3(0, 0, 6.4), Vector3(0, 0, -6.4), GATE_HALF * 2.0 + 0.5, "path", 0.02, 0.9)
	var jamb := GATE_HALF + (0.2 if L == 1 else 0.32)
	# ------------------------------------------------ side walls
	if L <= 2:
		for s in [-1.0, 1.0]:
			var a := Vector3(s * (jamb + 0.25), 0, 0)
			var b := Vector3(s * wall_end, 0, 0)
			k.box("stone", (a + b) * 0.5 + Vector3(0, 0.22, 0), Vector3(absf(b.x - a.x), 0.44, 0.62), 0, k.jitter(0.04))
			k.push_at(Vector3(0, 0.38, 0))
			k.palisade(a if s > 0 else b, b if s > 0 else a, 2.0 if L == 1 else 2.2, 0.13 if L == 1 else 0.15)
			k.pop()
			if L == 2:
				# braced counter-posts every 1.6 m behind the stakes
				var n := 3
				for i in n:
					var x: float = lerpf(a.x, b.x, (i + 0.5) / n)
					k.beam("dark_oak", Vector3(x, 0.4, -0.25), Vector3(x, 2.1, -0.18), 0.14, 0.14)
					k.beam("dark_oak", Vector3(x, 0.4, -1.0), Vector3(x, 1.7, -0.22), 0.1, 0.1)
	elif L == 3:
		for s in [-1.0, 1.0]:
			var x0: float = s * (jamb + 0.3)
			var x1: float = s * wall_end
			_b18_timber_curtain(k, x0, x1, 0.0, 2.7, s)
	else:
		for s in [-1.0, 1.0]:
			var x0: float = s * (jamb + (0.35 if L == 4 else 0.9))
			var x1: float = s * (wall_end - (0.0 if L == 4 else 0.95))
			var a := Vector3(minf(x0, x1), 0, 0)
			var b := Vector3(maxf(x0, x1), 0, 0)
			k.stone_wall(Vector3(a.x, 0, 0.0), Vector3(b.x, 0, 0.0), 2.3, 1.0, "stone",
				[{"at": (b.x - a.x) * 0.3, "w": 0.14, "y0": 1.0, "y1": 1.6, "kind": "slit"},
				 {"at": (b.x - a.x) * 0.7, "w": 0.14, "y0": 1.0, "y1": 1.6, "kind": "slit"}])
			# timber wall-walk gallery on top of the masonry
			_b18_gallery(k, a.x, b.x, 2.4, L == 5)
		if L == 4:
			# corbelled timber bartizans at both wall ends
			for s in [-1.0, 1.0]:
				_b18_bartizan(k, Vector3(s * (wall_end - 0.35), 2.4, 0.15))
		else:
			for s in [-1.0, 1.0]:
				_b18_tower(k, Vector3(s * (wall_end - 0.45), 0, 0.0))
	# ------------------------------------------------ gate structure
	if L == 1:
		for s in [-1.0, 1.0]:
			var p := Vector3(s * jamb, 0, 0)
			k.box("stone", p + Vector3(0, 0.25, 0), Vector3(0.6, 0.5, 0.6), 0, k.jitter(0.04))
			k.beam("oak", p + Vector3(0, 0.5, 0), p + Vector3(0, 3.75, 0), 0.34, 0.34)
			k.cone("oak", p + Vector3(0, 3.75, 0), 0.27, 0.38, 4, Color(1.05, 1, 0.95), 45)
			k.beam("oak", p + Vector3(-s * 0.05, 2.95, 0), p + Vector3(-s * 0.6, 3.36, 0), 0.14, 0.14)
		k.beam("oak", Vector3(-jamb - 0.3, 3.45, 0), Vector3(jamb + 0.3, 3.45, 0), 0.26, 0.3)
	elif L == 2:
		for s in [-1.0, 1.0]:
			var p := Vector3(s * jamb, 0, 0)
			k.box("stone", p + Vector3(0, 0.35, 0), Vector3(0.85, 0.7, 0.85), 0, k.jitter(0.04))
			k.box("stone_light", p + Vector3(0, 0.74, 0), Vector3(0.9, 0.08, 0.9))
			k.beam("oak", p + Vector3(0, 0.7, 0), p + Vector3(0, 4.3, 0), 0.5, 0.5)
			k.box("oak", p + Vector3(0, 4.45, 0), Vector3(0.62, 0.3, 0.62))
			k.cone("oak", p + Vector3(0, 4.6, 0), 0.4, 0.45, 4, Color(1.05, 1, 0.95), 45)
			for z in [-0.5, 0.5]:
				k.beam("oak", p + Vector3(-s * 0.1, 2.9, z * 0.6), p + Vector3(-s * 0.8, 3.55, z * 0.6), 0.14, 0.14)
		# horizontal timber deck on two beams (fighting platform)
		for z in [-0.55, 0.55]:
			k.beam("oak", Vector3(-jamb - 0.45, 3.62, z), Vector3(jamb + 0.45, 3.62, z), 0.26, 0.3)
		k.deck(Vector3(-jamb - 0.2, 0, -0.85), Vector3(jamb + 0.2, 0, 0.85), 3.95, "plank", false, false, false)
		for i in 7:
			var x: float = lerpf(-jamb, jamb, i / 6.0)
			k.box("dark_oak", Vector3(x, 3.85, 0), Vector3(0.12, 0.1, 2.0))
		k.railing(Vector3(-jamb - 0.2, 3.95, 0.85), Vector3(jamb + 0.2, 3.95, 0.85), 0.7, "oak", 0.42)
		k.railing(Vector3(-jamb - 0.2, 3.95, -0.85), Vector3(jamb + 0.2, 3.95, -0.85), 0.7, "oak", 0.42)
	elif L >= 3 and L <= 4:
		for s in [-1.0, 1.0]:
			var p := Vector3(s * (jamb + 0.05), 0, 0)
			if L == 4:
				k.box("stone", p + Vector3(0, 0.6, 0), Vector3(0.8, 1.2, 1.5), 0, k.jitter(0.04))
			for z in [-0.6, 0.6]:
				k.box("stone", p + Vector3(0, 0.25, z), Vector3(0.6, 0.5, 0.6))
				k.beam("oak", p + Vector3(0, 0.5, z), p + Vector3(0, GATE_CLEAR + 0.25, z), 0.42, 0.42)
				k.beam("oak", p + Vector3(-s * 0.1, 2.75, z), p + Vector3(-s * 0.7, GATE_CLEAR + 0.2, z), 0.16, 0.16)
		_b18_gatehouse(k, jamb + 0.5, 1.4, GATE_CLEAR + 0.3, L)
	else:
		# L5: masonry gate with a round arch; carriageway stays level under it
		k.push_at(Vector3(0, 0, 0.55))
		k.arch_wall(Vector3.ZERO, GATE_HALF * 2.0 + 0.1, 0.75, 2.45, 4.6, 4.45)
		k.pop()
		k.push_at(Vector3(0, 0, -0.35))
		k.arch_wall(Vector3.ZERO, GATE_HALF * 2.0 + 0.1, 0.6, 2.45, 4.6, 4.45, "stone", "stone")
		k.pop()
		# battered buttresses at the arch
		for s in [-1.0, 1.0]:
			var pr := PackedVector2Array([Vector2(0, 0), Vector2(0.45, 0), Vector2(0.12, 2.6), Vector2(0, 2.6)])
			k.push(Transform3D(Basis(Vector3.UP, -PI * 0.5), Vector3(s * 2.05, 0, 0.92)))
			k.extrude("stone", pr, -0.22, 0.22, Color(0.97, 0.95, 0.9))
			k.pop()
		k.box("brass", Vector3(0, 4.62, 0.97), Vector3(0.36, 0.42, 0.06))
		_b18_gatehouse(k, 2.55, 0.95, 4.5, L)
	# ------------------------------------------------ leaves, swung open inwards against the jambs
	var leaf_w := GATE_HALF - 0.02
	var leaf_h := 2.9 if L <= 2 else (3.0 if L < 5 else 2.95)
	for s in [-1.0, 1.0]:
		var hinge := Vector3(s * (GATE_HALF + 0.07), 0.06, -0.25 if L < 5 else -0.85)
		var yaw: float = -s * 88.0  # leaf swung fully back against the reveal, outside the carriageway
		k.push_at(hinge, yaw)
		var planks := 7
		for i in planks:
			var x: float = -s * (leaf_w * (i + 0.5) / planks)
			k.box("oak" if L < 4 else "dark_oak", Vector3(x, leaf_h * 0.5, 0), Vector3(leaf_w / planks - 0.015, leaf_h, 0.09), 0, k.jitter(0.12))
		for y in [0.45, leaf_h - 0.5]:
			k.box("iron", Vector3(-s * leaf_w * 0.42, y, 0.06), Vector3(leaf_w * 0.82, 0.09, 0.03))
		k.beam("dark_oak", Vector3(-s * 0.1, 0.5, -0.07), Vector3(-s * (leaf_w - 0.1), leaf_h - 0.5, -0.07), 0.12, 0.05)
		k.cyl("iron", Vector3(-s * leaf_w * 0.82, leaf_h * 0.48, 0.1), Vector3(-s * leaf_w * 0.82, leaf_h * 0.48, 0.14), 0.09, 8)
		k.pop()
	# passage for units, carts and wagons (QA sweeps these)
	var clear := GATE_CLEAR if L < 5 else 3.25
	k.lane(Vector3(0, 0, 6.2), Vector3(0, 0, -6.2), 2.6, clear - 0.1, "cart")
	return {}

static func _b18_timber_curtain(k, x0: float, x1: float, z: float, h: float, s: float) -> void:
	var a := Vector3(minf(x0, x1), 0, z)
	var b := Vector3(maxf(x0, x1), 0, z)
	k.box("stone", (a + b) * 0.5 + Vector3(0, 0.25, 0), Vector3(b.x - a.x, 0.5, 0.7), 0, k.jitter(0.04))
	var n := maxi(2, roundi((b.x - a.x) / 0.26))
	for i in n:
		var x: float = lerpf(a.x, b.x, (i + 0.5) / n)
		k.box("oak", Vector3(x, 0.5 + h * 0.5, z + 0.12), Vector3((b.x - a.x) / n - 0.02, h, 0.12), 0, k.jitter(0.12))
	for y in [0.9, 2.0]:
		k.beam("dark_oak", Vector3(a.x, y, z + 0.22), Vector3(b.x, y, z + 0.22), 0.1, 0.16)
	for i in 3:
		var x: float = lerpf(a.x + 0.1, b.x - 0.1, i / 2.0)
		k.beam("oak", Vector3(x, 0.5, z - 0.05), Vector3(x, 0.5 + h + 0.65, z - 0.05), 0.2, 0.2)
	# wall walk behind, with boarded parapet and crenels
	k.deck(Vector3(a.x, 0, z - 1.0), Vector3(b.x, 0, z - 0.05), 0.5 + h - 0.15, "plank", true, true, true)
	var m := maxi(2, roundi((b.x - a.x) / 0.7))
	for i in m:
		var x: float = lerpf(a.x, b.x, (i + 0.5) / m)
		k.box("oak", Vector3(x, 0.5 + h + 0.35, z + 0.12), Vector3((b.x - a.x) / m * 0.62, 0.7, 0.12), 0, k.jitter(0.1))
	k.beam("dark_oak", Vector3(a.x, 0.5 + h + 0.02, z + 0.12), Vector3(b.x, 0.5 + h + 0.02, z + 0.12), 0.16, 0.08)

static func _b18_gallery(k, x0: float, x1: float, y: float, roofed: bool) -> void:
	var a := minf(x0, x1)
	var b := maxf(x0, x1)
	k.deck(Vector3(a, 0, -0.75), Vector3(b, 0, 0.85), y + 0.1, "plank", false, true, true)
	# corbel brackets
	var n := maxi(2, roundi((b - a) / 0.8))
	for i in n + 1:
		var x: float = lerpf(a + 0.1, b - 0.1, float(i) / n)
		k.beam("oak", Vector3(x, y - 0.55, 0.45), Vector3(x, y + 0.02, 0.85), 0.12, 0.12)
	# timber breastwork with loopholes
	var m := maxi(2, roundi((b - a) / 0.5))
	for i in m:
		var x: float = lerpf(a, b, (i + 0.5) / m)
		var hh := 1.0 if i % 2 == 0 else 0.7
		k.box("oak", Vector3(x, y + 0.1 + hh * 0.5, 0.82), Vector3((b - a) / m - 0.03, hh, 0.1), 0, k.jitter(0.1))
	k.beam("dark_oak", Vector3(a, y + 0.15, 0.88), Vector3(b, y + 0.15, 0.88), 0.08, 0.14)
	if roofed:
		for i in n + 1:
			var x: float = lerpf(a + 0.1, b - 0.1, float(i) / n)
			k.beam("oak", Vector3(x, y + 0.1, 0.8), Vector3(x, y + 1.55, 0.8), 0.14, 0.14)
		k.beam("oak", Vector3(a, y + 1.55, 0.8), Vector3(b, y + 1.55, 0.8), 0.14, 0.18)
		k.lean_to(Vector3((a + b) * 0.5, y + 0.1, 0.05), b - a, 1.5, 1.55, 2.1, "shingle", 0)

static func _b18_bartizan(k, c: Vector3) -> void:
	for i in 3:
		k.beam("oak", c + Vector3(-0.45 + i * 0.45, -0.7, 0.4), c + Vector3(-0.45 + i * 0.45, 0.05, 0.95), 0.14, 0.14)
	k.deck(c + Vector3(-0.7, 0, -0.6), c + Vector3(0.7, 0, 1.0), c.y + 0.12, "plank", false, false, true)
	k.push_at(Vector3(0, c.y + 0.1, 0))
	k.timber_wall(Vector3(c.x - 0.7, 0, c.z + 1.0), Vector3(c.x + 0.7, 0, c.z + 1.0), 1.25, [{"at": 0.7, "w": 0.3, "y0": 0.55, "y1": 0.95, "kind": "window"}], "oak", "dark_oak", 0.1, 0.7, false)
	k.timber_wall(Vector3(c.x + 0.7, 0, c.z + 1.0), Vector3(c.x + 0.7, 0, c.z - 0.6), 1.25, [], "oak", "dark_oak", 0.1, 0.8, false)
	k.timber_wall(Vector3(c.x - 0.7, 0, c.z - 0.6), Vector3(c.x - 0.7, 0, c.z + 1.0), 1.25, [], "oak", "dark_oak", 0.1, 0.8, false)
	k.hip_roof("shingle", Vector3(c.x, 1.3, c.z + 0.2), 1.4, 1.6, 0.6, 0.18)
	k.pop()

static func _b18_tower(k, c: Vector3) -> void:
	# square masonry tower with timber lantern storey and spire roof
	k.stone_wall(c + Vector3(-0.85, 0, 0.85), c + Vector3(0.85, 0, 0.85), 3.3, 0.3, "stone", [{"at": 0.85, "w": 0.14, "y0": 1.4, "y1": 2.1, "kind": "slit"}])
	k.stone_wall(c + Vector3(0.85, 0, -0.85), c + Vector3(-0.85, 0, -0.85), 3.3, 0.3, "stone")
	k.stone_wall(c + Vector3(-0.85, 0, -0.85), c + Vector3(-0.85, 0, 0.85), 3.3, 0.3, "stone", [{"at": 0.85, "w": 0.14, "y0": 1.4, "y1": 2.1, "kind": "slit"}])
	k.stone_wall(c + Vector3(0.85, 0, 0.85), c + Vector3(0.85, 0, -0.85), 3.3, 0.3, "stone", [{"at": 0.85, "w": 0.14, "y0": 1.4, "y1": 2.1, "kind": "slit"}])
	k.box("stone", c + Vector3(0, 1.6, 0), Vector3(1.4, 3.2, 1.4))
	k.deck(c + Vector3(-1.05, 0, -1.05), c + Vector3(1.05, 0, 1.05), 3.45, "plank", false, false, true)
	k.push_at(Vector3(0, 3.45, 0))
	for corner in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(1, 0, 1), Vector3(-1, 0, 1)]:
		k.beam("oak", c + corner * 0.95, c + corner * 0.95 + Vector3(0, 1.3, 0), 0.16, 0.16)
	for i in 4:
		var a: Vector3 = [Vector3(-1, 0, 1), Vector3(1, 0, 1), Vector3(1, 0, -1), Vector3(-1, 0, -1)][i] * 0.95
		var b: Vector3 = [Vector3(1, 0, 1), Vector3(1, 0, -1), Vector3(-1, 0, -1), Vector3(-1, 0, 1)][i] * 0.95
		k.box("oak", c + (a + b) * 0.5 + Vector3(0, 0.4, 0), Vector3(absf(b.x - a.x) + 0.12, 0.8, absf(b.z - a.z) + 0.12), 0, k.jitter(0.08))
		k.beam("dark_oak", c + a + Vector3(0, 1.3, 0), c + b + Vector3(0, 1.3, 0), 0.14, 0.16)
	k.pyramid_roof("shingle", c + Vector3(0, 1.38, 0), 2.0, 1.35, 0.25)
	k.pop()

static func _b18_gatehouse(k, half_w: float, half_d: float, floor_y: float, L: int) -> void:
	## Timber room over the carriageway: floor beams sit above the clear height.
	var fy := floor_y
	for z in [-half_d + 0.15, 0.0, half_d - 0.15]:
		k.beam("oak", Vector3(-half_w - 0.35, fy + 0.15, z), Vector3(half_w + 0.35, fy + 0.15, z), 0.26, 0.3)
	# jettied floor joists
	for i in 9:
		var x: float = lerpf(-half_w + 0.1, half_w - 0.1, i / 8.0)
		k.box("dark_oak", Vector3(x, fy + 0.38, 0), Vector3(0.12, 0.14, half_d * 2 + 0.5))
	k.deck(Vector3(-half_w - 0.1, 0, -half_d - 0.15), Vector3(half_w + 0.1, 0, half_d + 0.15), fy + 0.5, "plank", false, false, true)
	var wy := fy + 0.5
	var wh := 1.9
	var wins := [{"at": half_w * 0.5, "w": 0.42, "y0": 0.7, "y1": 1.35, "kind": "window"},
		{"at": half_w, "w": 0.42, "y0": 0.7, "y1": 1.35, "kind": "window"},
		{"at": half_w * 1.5, "w": 0.42, "y0": 0.7, "y1": 1.35, "kind": "window"}]
	k.timber_wall(Vector3(-half_w, wy, half_d), Vector3(half_w, wy, half_d), wh, wins, "oak", "dark_oak", 0.16, 0.9, true)
	k.timber_wall(Vector3(half_w, wy, -half_d), Vector3(-half_w, wy, -half_d), wh, wins, "oak", "dark_oak", 0.16, 0.9, true)
	k.timber_wall(Vector3(-half_w, wy, -half_d), Vector3(-half_w, wy, half_d), wh, [], "oak", "dark_oak", 0.16, 0.9, true)
	k.timber_wall(Vector3(half_w, wy, half_d), Vector3(half_w, wy, -half_d), wh, [], "oak", "dark_oak", 0.16, 0.9, true)
	var ry := wy + wh
	k.gable_roof("shingle", Vector3(0, ry, 0), half_w * 2, half_d * 2, 1.05, 0.38, "oak")
	# corner posts with pyramid caps (silhouette of the gatehouse)
	for sx in [-1.0, 1.0]:
		var p := Vector3(sx * (half_w + 0.1), 0, half_d + 0.05)
		k.beam("oak", Vector3(p.x, fy + 0.2, p.z), Vector3(p.x, ry + 1.25, p.z), 0.36, 0.36)
		k.box("oak", Vector3(p.x, ry + 1.3, p.z), Vector3(0.5, 0.22, 0.5))
		k.cone("oak", Vector3(p.x, ry + 1.41, p.z), 0.33, 0.42, 4, Color(1.05, 1, 0.95), 45)
	if L >= 4:
		k.banner(Vector3(0, wy + 1.75, half_d + 0.14), 0.55, 0.9, "cloth_red")

# ============================================================== B01 Town Hall (ECO-05)
static func b01_hall(k, L: int) -> Dictionary:
	if L == 1:
		# starter hall + oval forecourt and a broad approach that reads from the city camera
		var pts := PackedVector2Array()
		for i in 22:
			var a := TAU * i / 22.0
			pts.append(Vector2(0.4 + cos(a) * 3.3, 5.0 + sin(a) * 1.75))
		k.ground_poly(pts, "path", 0.025)
		k.road(Vector3(0.4, 0, 6.2), Vector3(0.4, 0, 6.95), 2.6, "path", 0.02, 0.3)
		for s in [-1.0, 1.0]:
			k.bench(Vector3(0.4 + s * 2.4, 0, 5.2), 1.3, 90.0 * s)
			k.lantern(Vector3(0.4 + s * 2.9, 1.6, 4.0))
			k.cyl("dark_oak", Vector3(0.4 + s * 2.9, 0, 4.0), Vector3(0.4 + s * 2.9, 1.5, 4.0), 0.05, 6)
		for i in 9:
			var a := PI * (0.15 + 0.7 * i / 8.0)
			k.stone_block(Vector3(0.4 + cos(a) * 3.45, 0, 5.0 + sin(a) * 1.9), Vector3(0.4, 0.16, 0.3), rad_to_deg(-a))
		return base("starterHall")
	if L == 2:
		# keep the plaza; replace the flat canopy by a gabled covered portal with a broad stair
		var pts := PackedVector2Array()
		for i in 22:
			var a := TAU * i / 22.0
			pts.append(Vector2(0.0 + cos(a) * 3.6, 6.0 + sin(a) * 1.1))
		k.ground_poly(pts, "path", 0.025)
		k.paving(Vector3(-2.0, 0, 4.4), Vector3(2.0, 0, 6.8), 0.06, 0.5)
		k.stairs(Vector3(0, 0, 6.75), 3.4, 3, 0.16, 0.42, 0, "stone_light")
		var fy := 0.48
		k.deck(Vector3(-2.0, 0, 4.3), Vector3(2.0, 0, 5.5), fy, "stone_light", false, false, true)
		for sx in [-1.0, 1.0]:
			k.box("stone", Vector3(sx * 1.75, fy + 0.15, 5.4), Vector3(0.45, 0.3, 0.45))
			k.beam("oak", Vector3(sx * 1.75, fy + 0.3, 5.4), Vector3(sx * 1.75, fy + 3.0, 5.4), 0.3, 0.3)
			k.beam("oak", Vector3(sx * 1.75, fy + 2.3, 5.4), Vector3(sx * 1.1, fy + 2.95, 5.4), 0.13, 0.13)
		k.beam("oak", Vector3(-2.0, fy + 3.05, 5.4), Vector3(2.0, fy + 3.05, 5.4), 0.24, 0.28)
		k.push_at(Vector3(0, 0, 4.85), 90)
		k.gable_roof("slate_roof", Vector3(0, fy + 3.2, 0), 1.6, 3.9, 1.3, 0.3, "plaster")
		k.gable_frame(Vector3(0, fy + 3.2, 0), 1.6, 3.9, 1.3)
		k.pop()
		k.banner(Vector3(0, fy + 3.95, 5.62), 0.55, 0.8, "cloth_blue")
		var spec := base("hall", [box_mask(Vector3(-2.7, 2.2, 4.2), Vector3(2.7, 4.6, 6.4))])
		spec["worker"] = Vector3(-4.6, 0.0, 6.2)
		return spec
	# L5: bell tower whose stone piers run from the belfry down to the plinth; paved square with side galleries
	k.paving(Vector3(-6.8, 0, 5.2), Vector3(6.8, 0, 7.0), 0.06, 0.55)
	k.paving(Vector3(-6.8, 0, -1.0), Vector3(-4.9, 0, 5.2), 0.06, 0.55)
	k.paving(Vector3(4.9, 0, -1.0), Vector3(6.8, 0, 5.2), 0.06, 0.55)
	k.stairs(Vector3(0, 0, 7.0), 4.0, 2, 0.15, 0.4, 0, "stone_light")
	var front := 5.15
	for sx in [-1.0, 1.0]:
		# full-height masonry piers flanking the portal
		k.stone_wall(Vector3(sx * 2.35 - 0.45, 0, front), Vector3(sx * 2.35 + 0.45, 0, front), 9.6, 0.7, "stone_light", [], true, true)
	k.stone_wall(Vector3(-1.9, 7.2, front), Vector3(1.9, 7.2, front), 2.4, 0.5, "stone_light", [{"at": 1.9, "w": 0.9, "y0": 0.6, "y1": 1.8, "kind": "window"}], false, false)
	k.box("stone", Vector3(0, 9.75, front - 0.6), Vector3(3.2, 0.3, 2.2))
	# belfry
	var by := 9.9
	for cx in [-1.25, 1.25]:
		for cz in [-1.6, 0.4]:
			k.box("stone_light", Vector3(cx, by + 1.0, front + cz - 0.1), Vector3(0.5, 2.0, 0.5), 0, k.jitter(0.05))
	k.box("stone_light", Vector3(0, by + 2.1, front - 0.7), Vector3(3.1, 0.3, 2.6))
	k.cyl("brass", Vector3(0, by + 0.9, front - 0.7), Vector3(0, by + 1.5, front - 0.7), 0.42, 10, true, Color.WHITE, 0.22)
	k.beam("dark_oak", Vector3(-1.2, by + 1.6, front - 0.7), Vector3(1.2, by + 1.6, front - 0.7), 0.14, 0.14)
	k.pyramid_roof("slate_roof", Vector3(0, by + 2.25, front - 0.7), 2.9, 2.7, 0.3)
	k.flag_pole(Vector3(0, by + 4.9, front - 0.7), 1.4, "cloth_blue")
	k.box("brass", Vector3(0, 6.2, front + 0.38), Vector3(0.7, 0.7, 0.05), 0, Color.WHITE, 0, 45)
	# side galleries (arcades) along the square
	for sx in [-1.0, 1.0]:
		var x: float = sx * 5.85
		for i in 4:
			var z := -0.6 + i * 1.85
			k.box("stone", Vector3(x + sx * 0.55, 0.12, z), Vector3(0.36, 0.24, 0.36))
			k.beam("oak", Vector3(x + sx * 0.55, 0.24, z), Vector3(x + sx * 0.55, 2.6, z), 0.24, 0.24)
			if i < 3:
				k.beam("oak", Vector3(x + sx * 0.55, 2.0, z + 0.1), Vector3(x + sx * 0.55, 2.55, z + 0.65), 0.1, 0.1)
				k.beam("oak", Vector3(x + sx * 0.55, 2.0, z + 1.75), Vector3(x + sx * 0.55, 2.55, z + 1.2), 0.1, 0.1)
		k.beam("oak", Vector3(x + sx * 0.55, 2.62, -0.8), Vector3(x + sx * 0.55, 2.62, 5.0), 0.2, 0.22)
		k.push_at(Vector3(x, 0, 2.2), 90.0 * sx)
		k.lean_to(Vector3(0, 0, 0), 6.0, 1.6, 2.65, 3.3, "slate_roof", 0)
		k.pop()
		k.lantern(Vector3(x + sx * 0.4, 2.2, 4.9))
	var spec := base("hall", [box_mask(Vector3(-2.9, 2.6, 5.0), Vector3(2.9, 4.8, 7.2))])
	spec["worker"] = Vector3(-4.6, 0.0, 6.15)
	return spec

# ============================================================== B03 Warehouse (ECO-01)
static func b03_warehouse(k, L: int) -> Dictionary:
	# free paved receiving yard in front, separated from storage
	k.paving(Vector3(-6.6, 0, 5.7), Vector3(6.6, 0, 7.0), 0.05, 0.55)
	k.paving(Vector3(3.9, 0, 3.6), Vector3(6.6, 0, 5.7), 0.05, 0.55)
	# self-contained storeroom with its own roof and door
	k.timber_house(Vector3(5.25, 0, -1.6), 2.6, 3.6, 2.9, 1.2,
		[], [], [], [], "slate_roof", "plaster", 0.35)
	k.door(Vector3(5.25, 0, 0.27), 1.2, 1.95, 0, 0.35)
	k.box("stone", Vector3(5.25, 0.17, 0.55), Vector3(1.5, 0.34, 0.6))
	k.lantern(Vector3(4.45, 2.2, 0.32))
	# storage stays next to the store, out of the yard
	k.crate(Vector3(4.4, 0, 1.0)); k.crate(Vector3(4.4, 0.55, 1.0), 0.5, 15); k.barrel(Vector3(6.2, 0, 1.1))
	# jib crane: hook hangs over an empty strip of the yard
	k.box("stone", Vector3(6.5, 0.2, 4.0), Vector3(0.6, 0.4, 0.6))
	k.beam("oak", Vector3(6.5, 0.4, 4.0), Vector3(6.5, 4.6, 4.0), 0.28, 0.28)
	k.beam("oak", Vector3(6.5, 4.5, 4.0), Vector3(4.6, 4.5, 4.9), 0.2, 0.2)
	k.beam("oak", Vector3(6.5, 3.2, 4.0), Vector3(5.4, 4.45, 4.5), 0.12, 0.12)
	k.hook_hoist(Vector3(4.75, 4.35, 4.85), 2.0)
	k.lane(Vector3(4.75, 0, 6.9), Vector3(4.75, 0, 4.1), 1.2, 1.9, "unit")
	for i in 5:
		k.fence(Vector3(-6.6 + i * 1.5, 0, 7.05), Vector3(-5.4 + i * 1.5, 0, 7.05), 0.7)
	return base("warehouse", [box_mask(Vector3(1.0, -0.5, 6.4), Vector3(3.8, 3.0, 7.6)), box_mask(Vector3(3.6, -0.5, 1.2), Vector3(5.3, 3.0, 3.5))])

# ============================================================== B05 Marketplace (ECO-03)
static func b05_market(k, L: int) -> Dictionary:
	# fountain with a free walk-around ring
	var ring := PackedVector2Array()
	for i in 24:
		var a := TAU * i / 24.0
		ring.append(Vector2(0.2 + cos(a) * 2.1, 0.35 + sin(a) * 1.15))
	k.ground_poly(ring, "path", 0.03)
	k.cyl("stone_light", Vector3(0.2, 0, 0.35), Vector3(0.2, 0.45, 0.35), 0.5, 14)
	k.cyl("water", Vector3(0.2, 0.44, 0.35), Vector3(0.2, 0.47, 0.35), 0.4, 14)
	k.cyl("stone", Vector3(0.2, 0.45, 0.35), Vector3(0.2, 1.15, 0.35), 0.16, 8)
	k.cyl("stone_light", Vector3(0.2, 1.15, 0.35), Vector3(0.2, 1.3, 0.35), 0.38, 10)
	k.lane(Vector3(0.2, 0, 0.35), Vector3(1.5, 0, 0.8), 0.4, 1.8, "ring")
	# two-tier central pavilion at the back with a tall upper belt
	var c := Vector3(0.3, 0, -4.9)
	k.paving(c + Vector3(-2.1, 0, -1.4), c + Vector3(2.1, 0, 1.6), 0.06, 0.5)
	for i in 8:
		var a := TAU * i / 8.0 + PI / 8.0
		var p := c + Vector3(cos(a) * 1.75, 0, sin(a) * 1.3)
		k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.36, 0.3, 0.36))
		k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, 4.6, 0), 0.22, 0.22)
	k.deck(c + Vector3(-1.95, 0, -1.5), c + Vector3(1.95, 0, 1.5), 2.6, "plank", false, true, true)
	for z in [-1.5, 1.5]:
		k.railing(c + Vector3(-1.95, 2.6, z), c + Vector3(1.95, 2.6, z), 0.85, "oak", 0.35)
	k.hip_roof("shingle_light", c + Vector3(0, 2.5, 0), 4.0, 3.0, 0.6, 0.35)
	k.hip_roof("shingle", c + Vector3(0, 4.65, 0), 3.0, 2.3, 1.5, 0.35)
	for i in 6:
		k.box("cloth_red" if i % 2 == 0 else "canvas", c + Vector3(-1.6 + i * 0.64, 2.25, 1.62), Vector3(0.5, 0.35, 0.03), 0, Color.WHITE, 0, 0)
	# elevated walkway to the left stalls; posts carry it so the passage below stays open
	var w0 := c + Vector3(-1.95, 2.6, 0.3)
	var w1 := Vector3(-3.3, 2.6, -2.2)
	k.deck(Vector3(w1.x, 0, w1.z - 0.6), Vector3(w0.x, 0, w1.z + 0.6), 2.6, "plank", false, true, true)
	k.deck(Vector3(w0.x - 0.2, 0, w1.z), Vector3(w0.x + 0.4, 0, w0.z), 2.6, "plank", false, true, false)
	for p in [Vector3(w1.x + 0.15, 0, w1.z - 0.5), Vector3(w1.x + 0.15, 0, w1.z + 0.5), Vector3(w0.x - 0.2, 0, w1.z - 0.5), Vector3(w0.x - 0.2, 0, w1.z + 0.5)]:
		k.box("stone", p + Vector3(0, 0.12, 0), Vector3(0.3, 0.24, 0.3))
		k.beam("oak", p + Vector3(0, 0.24, 0), p + Vector3(0, 2.5, 0), 0.2, 0.2)
	k.railing(Vector3(w1.x, 2.6, w1.z + 0.6), Vector3(w0.x - 0.2, 2.6, w1.z + 0.6), 0.85, "oak", 0.35)
	k.railing(Vector3(w1.x, 2.6, w1.z - 0.6), Vector3(w0.x - 0.2, 2.6, w1.z - 0.6), 0.85, "oak", 0.35)
	k.stairs(Vector3(-4.6, 0, -0.8), 1.0, 9, 0.29, 0.28, 0, "oak", false)
	# bunting across the square
	for i in 8:
		k.box("cloth_red" if i % 2 == 0 else "cloth_blue", Vector3(-3.6 + i * 1.0, 2.9 - absf(i - 3.5) * -0.05, 0.9), Vector3(0.3, 0.32, 0.02), 25)
	return base("market27")

# ============================================================== B06 Lumber Camp (RES-01)
static func b06_lumber(k, L: int) -> Dictionary:
	# round-log stacks in front (instead of packed bundles) – the camp's signature
	k.log_pile(Vector3(-2.2, 0, 5.6), 3.2, 3, 0.23, 90)
	k.log_pile(Vector3(1.6, 0, 6.0), 2.6, 2, 0.2, 90)
	k.road(Vector3(0.4, 0, 7.0), Vector3(0.4, 0, 4.4), 1.6, "earth", 0.02, 0.3)
	# covered log store on the left
	k.open_shed(Vector3(-5.5, 0, 2.6), 2.2, 4.2, 2.4, 1.0, "slate_roof", 2, 3, false)
	k.log_pile(Vector3(-5.5, 0, 2.6), 3.6, 3, 0.18, 0, "log")
	# developed loading deck on the right with a hoist; deck under the hook is left empty
	k.deck(Vector3(4.0, 0, -3.2), Vector3(6.7, 0, 3.6), 0.55, "plank", true, true, false)
	k.ramp(Vector3(5.4, 0, 6.95), Vector3(5.4, 0.55, 3.6), 2.0, "plank")
	k.crane(Vector3(6.35, 0.55, -2.8), 4.2, Vector3(-1.2, 0, 3.6), 1.5)
	k.box("dark_oak", Vector3(5.15, 0.565, 0.8), Vector3(1.6, 0.012, 1.6), 0, Color(0.7, 0.6, 0.5))
	k.lane(Vector3(5.4, 0, 6.9), Vector3(5.4, 0.55, -0.4), 1.6, 1.9, "cart")
	k.plank_stack(Vector3(4.6, 0.55, -2.2), 1.6, 0.8, 4, 0)
	return base("lumber", [box_mask(Vector3(3.6, -0.5, 0.2), Vector3(5.6, 3.0, 2.8)), box_mask(Vector3(-6.0, -0.5, 0.0), Vector3(-3.8, 3.0, 4.8))])

# ============================================================== B07 Stone Quarry (RES-02)
static func b07_quarry(k, L: int) -> Dictionary:
	var top := 4.55
	# upper post: open masonry bay with a table on a timber platform
	k.deck(Vector3(-3.0, 0, -3.4), Vector3(0.2, 0, -1.2), top, "plank", true, true, true)
	for sx in [-2.7, -0.1]:
		k.box("stone", Vector3(sx, top + 1.1, -3.1), Vector3(0.5, 2.2, 0.5), 0, k.jitter(0.05))
		k.box("stone", Vector3(sx, top + 1.1, -1.5), Vector3(0.5, 2.2, 0.5), 0, k.jitter(0.05))
	k.box("stone_light", Vector3(-1.4, top + 2.3, -2.3), Vector3(3.1, 0.25, 2.1))
	k.gable_roof("shingle", Vector3(-1.4, top + 2.4, -2.3), 2.9, 1.9, 0.8, 0.3, "stone")
	k.table(Vector3(-1.4, top, -2.3), 1.4, 0.7, 0.8)
	k.box("parchment", Vector3(-1.4, top + 0.81, -2.3), Vector3(0.8, 0.01, 0.5))
	# separate platform for the upper hoist
	k.deck(Vector3(0.6, 0, -1.8), Vector3(2.6, 0, 0.2), 3.0, "plank", true, true, true)
	k.crane(Vector3(1.0, 3.0, -1.4), 2.4, Vector3(1.6, 0, 1.6), 2.8)
	k.railing(Vector3(0.6, 3.0, -1.8), Vector3(2.6, 3.0, -1.8), 0.9)
	# stair from the yard comes out freely onto that platform
	k.stairs(Vector3(3.3, 0, 3.6), 1.0, 10, 0.3, 0.38, 0, "oak", false)
	k.railing(Vector3(3.85, 0, 3.6), Vector3(3.85, 3.0, -0.2), 0.9)
	k.deck(Vector3(2.6, 0, -0.4), Vector3(3.8, 0, 0.2), 3.0, "plank", false, false, true)
	k.lane(Vector3(3.3, 0, 3.8), Vector3(3.3, 3.0, -0.2), 0.9, 2.0, "stair")
	# developed receiving yard
	k.paving(Vector3(-4.6, 0, 1.6), Vector3(2.4, 0, 5.4), 0.05, 0.6)
	for i in 3:
		var x := -3.8 + i * 1.6
		k.box("dark_oak", Vector3(x, 0.08, 4.6), Vector3(1.2, 0.12, 0.9))
		k.stone_block(Vector3(x - 0.25, 0.14, 4.6), Vector3(0.55, 0.42, 0.75), 0)
		k.stone_block(Vector3(x + 0.3, 0.14, 4.6), Vector3(0.5, 0.42, 0.7), 4)
	k.cart(Vector3(-2.7, 0, 3.0), 90, "stone")
	k.fence(Vector3(-1.3, 0, 3.85), Vector3(2.55, 0, 3.85), 0.85)
	return base("quarry27", [box_mask(Vector3(-1.6, -0.5, 3.4), Vector3(4.3, 2.0, 4.3))])

# ============================================================== B08 Iron Mine (RES-03)
static func b08_mine(k, L: int) -> Dictionary:
	# open sorting bay on the right with two large ore cells
	k.open_shed(Vector3(4.6, 0, -0.4), 3.4, 4.2, 2.6, 1.1, "shingle", 3, 2, false)
	k.ground(Vector3(2.9, 0, -2.5), Vector3(6.3, 0, 1.7), "earth", 0.02)
	for i in 2:
		var z := -1.5 + i * 2.0
		var c := Vector3(5.0, 0, z)
		k.box("stone", c + Vector3(0, 0.35, -0.85), Vector3(2.4, 0.7, 0.2))
		k.box("stone", c + Vector3(1.15, 0.35, 0), Vector3(0.2, 0.7, 1.7))
		k.box("dark_oak", c + Vector3(0, 0.35, 0.85), Vector3(2.4, 0.7, 0.12))
		k.box("ore", c + Vector3(0.05, 0.25, 0), Vector3(2.1, 0.5 - i * 0.12, 1.5), 0, k.jitter(0.1))
	k.workbench(Vector3(3.6, 0, 1.3), 1.4, 0)
	# upper hoisting volume: timber headframe with sheave wheel above the adit
	var h := Vector3(0.4, 0, 0.4)
	for s in [Vector3(-0.9, 0, -0.5), Vector3(0.9, 0, -0.5)]:
		k.beam("oak", h + s + Vector3(0, 2.6, 0), h + Vector3(s.x * 0.5, 6.6, 0.3), 0.24, 0.24)
	for s in [Vector3(-0.9, 0, 2.6), Vector3(0.9, 0, 2.6)]:
		k.box("stone", h + s + Vector3(0, 0.15, 0), Vector3(0.45, 0.3, 0.45))
		k.beam("oak", h + s + Vector3(0, 0.3, 0), h + Vector3(s.x * 0.5, 6.6, 0.3), 0.22, 0.22)
	k.beam("oak", h + Vector3(-0.6, 6.6, 0.3), h + Vector3(0.6, 6.6, 0.3), 0.26, 0.26)
	k.wheel(h + Vector3(0, 7.15, 0.3), 0.75, Vector3.RIGHT)
	k.box("shingle", h + Vector3(0, 7.8, 0.3), Vector3(1.8, 0.1, 1.6), 0, Color.WHITE, 0, 0)
	k.gable_roof("shingle", h + Vector3(0, 7.95, 0.3), 1.8, 1.4, 0.6, 0.2)
	# bucket hangs over a clear spot beside the rails
	k.beam("oak", h + Vector3(0, 6.6, 0.3), Vector3(2.1, 6.4, 3.0), 0.2, 0.2)
	k.cyl("rope", Vector3(2.1, 6.3, 3.0), Vector3(2.1, 2.3, 3.0), 0.025, 5, false)
	k.cyl("iron", Vector3(2.1, 1.6, 3.0), Vector3(2.1, 2.3, 3.0), 0.32, 10, true, Color.WHITE, 0.4)
	k.lane(Vector3(0.5, 0, 6.6), Vector3(0.5, 0, 1.2), 1.0, 2.0, "rail")
	k.lane(Vector3(2.1, 0, 2.6), Vector3(2.1, 0, 3.4), 0.6, 1.5, "unit")
	k.cart(Vector3(-1.6, 0, 4.6), 20, "ore")
	return base("ironmine27", [box_mask(Vector3(2.0, -0.5, 1.8), Vector3(3.2, 2.5, 3.6))])

# ============================================================== B09 Farm (RES-04)
static func b09_farm(k, L: int) -> Dictionary:
	var s := 1.0 if L == 5 else 0.945
	# dormer on the front roof slope
	var roof_y := 3.6 * s
	k.push_at(Vector3(-0.9 * s, roof_y, 2.0 * s))
	k.box("plaster", Vector3(0, 0.55, 0), Vector3(1.2, 1.1, 1.4))
	k.window(Vector3(0, 0, 0.72), 0.55, 0.25, 0.85, 0)
	k.push_at(Vector3(0, 1.1, 0.0), 90)
	k.gable_roof("clay_roof", Vector3(0, 0, 0), 1.6, 1.3, 0.55, 0.15, "plaster")
	k.pop()
	k.pop()
	# right utility corner: barn with an open entrance and a free path into the yard
	k.timber_house(Vector3(4.6, 0, -4.2), 2.4, 3.0, 2.6, 1.1, [{"at": 1.2, "w": 1.5, "y0": 0.0, "y1": 1.95, "kind": "open"}], [], [], [], "clay_roof", "plaster", 0.3)
	k.box("plank", Vector3(4.6, 0.16, -4.2), Vector3(2.2, 0.02, 2.8))
	k.door(Vector3(3.72, 0, -2.0), 0.7, 1.95, -85, 0.0)
	k.road(Vector3(4.6, 0, -2.6), Vector3(4.6, 0, 4.3), 1.2, "path", 0.025, 0.2)
	k.lane(Vector3(4.6, 0, -2.4), Vector3(4.6, 0, 3.5), 0.8, 1.9, "unit")
	k.barrel(Vector3(6.2, 0, -2.4))
	if L == 5:
		# wide right work bay: washing tub and a large table; water tank on a stand
		k.open_shed(Vector3(5.95, 0, 1.4), 1.4, 4.0, 2.4, 0.8, "clay_roof", 2, 3, false)
		k.ground(Vector3(5.2, 0, -0.6), Vector3(6.7, 0, 3.4), "stone_light", 0.04)
		k.cyl("oak", Vector3(6.0, 0, 0.2), Vector3(6.0, 0.55, 0.2), 0.42, 12, true, k.jitter(0.1), 0.48)
		k.cyl("water", Vector3(6.0, 0.55, 0.2), Vector3(6.0, 0.57, 0.2), 0.41, 12)
		k.table(Vector3(6.0, 0, 2.2), 1.6, 0.8, 0.85, 90)
		for i in 3:
			k.box("herb", Vector3(5.85 + i * 0.12, 0.9, 1.8 + i * 0.35), Vector3(0.25, 0.12, 0.25))
		var t := Vector3(-5.6, 0, -3.4)
		for sx in [-0.55, 0.55]:
			for sz in [-0.55, 0.55]:
				k.beam("dark_oak", t + Vector3(sx, 0, sz), t + Vector3(sx * 0.8, 2.2, sz * 0.8), 0.14, 0.14)
		k.cyl("oak", t + Vector3(0, 2.2, 0), t + Vector3(0, 3.3, 0), 0.75, 12, true, k.jitter(0.08))
		for y in [2.35, 2.75, 3.15]:
			k.cyl("iron", t + Vector3(0, y, 0), t + Vector3(0, y + 0.05, 0), 0.77, 12, false)
		k.cone("shingle", t + Vector3(0, 3.3, 0), 0.95, 0.6, 10)
		k.beam("dark_oak", t + Vector3(0.6, 2.3, 0.4), Vector3(-4.6, 1.0, -2.0), 0.08, 0.08)
	return base("farm", [box_mask(Vector3(3.6, -0.5, -2.2), Vector3(5.6, 2.0, 3.6))])

# ============================================================== B11 Infantry Barracks (MIL-01)
static func b11_barracks(k, L: int) -> Dictionary:
	# open rectangular drill square: the barracks' signature from the city camera
	var lo := Vector3(-4.6, 0, 1.6)
	var hi := Vector3(4.2, 0, 6.6)
	k.ground(lo, hi, "drill", 0.035)
	for p in [[lo, Vector3(hi.x, 0, lo.z)], [Vector3(lo.x, 0, hi.z), hi], [lo, Vector3(lo.x, 0, hi.z)], [Vector3(hi.x, 0, lo.z), hi]]:
		var a: Vector3 = p[0]
		var b: Vector3 = p[1]
		k.box("stone_light", (a + b) * 0.5 + Vector3(0, 0.06, 0), Vector3(absf(b.x - a.x) + 0.2, 0.12, absf(b.z - a.z) + 0.2) if absf(b.x - a.x) > 0.1 else Vector3(0.2, 0.12, absf(b.z - a.z) + 0.2))
	for corner in [lo, Vector3(hi.x, 0, lo.z), Vector3(lo.x, 0, hi.z), hi]:
		k.cyl("dark_oak", corner, corner + Vector3(0, 1.1, 0), 0.08, 6)
		k.box("cloth_red", corner + Vector3(0, 1.0, 0.1), Vector3(0.3, 0.4, 0.02))
	k.lane(Vector3(-3.6, 0, 4.1), Vector3(3.2, 0, 4.1), 2.6, 2.0, "drill")
	# rows of weapon stands along the long sides, centre stays open
	for i in 3:
		k.weapon_rack(Vector3(-3.4 + i * 1.9, 0, 6.15), 1.4, 0)
	k.box("dark_oak", Vector3(-0.2, 0.01, 4.1), Vector3(0.12, 0.02, 1.2), 45, Color(0.6, 0.6, 0.6))
	k.box("dark_oak", Vector3(-0.2, 0.01, 4.1), Vector3(0.12, 0.02, 1.2), -45, Color(0.6, 0.6, 0.6))
	# developed left wing (barrack block)
	k.timber_house(Vector3(-4.6, 0, -2.2), 2.6, 4.0, 2.8, 1.2, [], [], [], [{"at": 2.0, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}, {"at": 0.8, "w": 0.45, "y0": 0.9, "y1": 1.5, "kind": "window"}, {"at": 3.2, "w": 0.45, "y0": 0.9, "y1": 1.5, "kind": "window"}], "clay_roof", "plaster", 0.35)
	var masks := [box_mask(Vector3(-5.0, -0.5, 1.2), Vector3(5.0, 3.5, 6.0))]
	if L == 5:
		# enlarged stone entrance on the main block
		k.push_at(Vector3(-0.6, 0, 1.25))
		k.arch_wall(Vector3.ZERO, 1.2, 0.5, 1.5, 2.4, 2.9, "stone", "stone_light")
		k.crenellations(Vector3(-1.2, 0, 0), Vector3(1.2, 0, 0), 2.9, 0.5)
		k.pop()
		k.door(Vector3(-0.6, 0, 1.0), 1.1, 2.0, 0, 0.0)
		k.banner(Vector3(-0.6, 2.8, 1.55), 0.5, 0.75, "cloth_red")
		# long covered gallery along the right side of the square, racks beneath it
		var gx := 4.75
		for i in 5:
			var z := 0.6 + i * 1.45
			k.box("stone", Vector3(gx, 0.12, z), Vector3(0.34, 0.24, 0.34))
			k.beam("oak", Vector3(gx, 0.24, z), Vector3(gx, 2.4, z), 0.22, 0.22)
		k.beam("oak", Vector3(gx, 2.45, 0.4), Vector3(gx, 2.45, 6.6), 0.2, 0.22)
		k.push_at(Vector3(5.55, 0, 3.5), -90)
		k.lean_to(Vector3(0, 0, 0), 6.3, 1.6, 2.45, 3.1, "clay_roof", 0)
		k.pop()
		for i in 3:
			k.weapon_rack(Vector3(5.7, 0, 1.4 + i * 1.9), 1.3, 90)
		for i in 4:
			k.lantern(Vector3(gx - 0.15, 2.15, 1.3 + i * 1.45))
	return base("barracks26", masks)

# ============================================================== B13 Stables (MIL-03)
static func b13_stables(k, L: int) -> Dictionary:
	# lattice stall doors restored on the front
	for i in 4:
		var x := -2.25 + i * 1.5
		var c := Vector3(x, 0, 0.12)
		k.box("dark_oak", c + Vector3(0, 0.55, 0), Vector3(1.1, 1.1, 0.06), 0, k.jitter(0.1))
		for j in 6:
			k.beam("oak", c + Vector3(-0.5 + j * 0.2, 1.1, 0.02), c + Vector3(-0.5 + j * 0.2, 1.75, 0.02), 0.04, 0.04)
		k.beam("oak", c + Vector3(-0.55, 1.75, 0.02), c + Vector3(0.55, 1.75, 0.02), 0.06, 0.08)
		k.beam("oak", c + Vector3(-0.5, 0.1, 0.05), c + Vector3(0.5, 1.0, 0.05), 0.06, 0.04)
	# light sanded paddock strip
	k.ground(Vector3(-3.8, 0, 1.2), Vector3(3.8, 0, 4.6), "sand", 0.03)
	k.fence(Vector3(-3.9, 0, 4.7), Vector3(3.9, 0, 4.7), 0.95)
	k.fence(Vector3(-3.9, 0, 1.1), Vector3(-3.9, 0, 4.7), 0.95)
	k.fence(Vector3(3.9, 0, 1.1), Vector3(3.9, 0, 4.7), 0.95)
	k.barrel(Vector3(3.5, 0, 1.4))
	k.box("water", Vector3(-3.3, 0.45, 2.6), Vector3(0.5, 0.04, 1.4))
	k.box("dark_oak", Vector3(-3.3, 0.22, 2.6), Vector3(0.6, 0.44, 1.5))
	# open saddlery (tack room) on the right
	k.open_shed(Vector3(5.3, 0, -1.6), 2.2, 3.0, 2.3, 0.9, "slate_roof", 2, 2, false)
	k.ground(Vector3(4.2, 0, -3.1), Vector3(6.4, 0, -0.1), "plank", 0.06)
	for i in 3:
		var z := -2.6 + i * 1.0
		k.beam("dark_oak", Vector3(5.9, 1.0, z), Vector3(6.3, 1.0, z), 0.1, 0.1)
		k.box("cloth_red" if i == 1 else "dark_oak", Vector3(5.85, 1.12, z), Vector3(0.5, 0.25, 0.42), 0, k.jitter(0.1))
		k.box("rope", Vector3(5.95, 1.5, z + 0.3), Vector3(0.05, 0.6, 0.05))
	k.weapon_rack(Vector3(4.6, 0, -2.9), 1.0, 0)
	return base("stables26", [box_mask(Vector3(-4.2, -0.5, 1.0), Vector3(4.2, 3.0, 5.0)), box_mask(Vector3(3.0, -0.5, -2.8), Vector3(4.2, 3.0, 0.6))])

# ============================================================== B14 Blacksmith (MIL-04)
static func b14_smith(k, L: int) -> Dictionary:
	var f := 1.0 if L == 5 else (0.955 if L == 4 else 0.91)
	var xr := 4.4 * f
	# stone forge core on the right with a new tall chimney
	k.box("stone", Vector3(xr + 0.85, 1.1, -2.2), Vector3(1.7, 2.2, 1.9), 0, k.jitter(0.04))
	k.box("stone_light", Vector3(xr + 0.85, 2.25, -2.2), Vector3(1.85, 0.12, 2.05))
	k.chimney(Vector3(xr + 0.85, 2.3, -2.4), 6.4, 0.95)
	k.box("ember", Vector3(xr + 0.85, 0.95, -1.22), Vector3(0.8, 0.5, 0.04))
	k.box("soot", Vector3(xr + 0.85, 0.95, -1.24), Vector3(1.0, 0.7, 0.02))
	k.box("stone", Vector3(xr + 0.85, 0.45, -0.95), Vector3(1.4, 0.9, 0.6))
	k.box("ember", Vector3(xr + 0.85, 0.92, -0.95), Vector3(0.7, 0.04, 0.35))
	# open anvil right in front of the forge
	k.anvil(Vector3(xr + 1.3, 0, 0.3), 90, 1.0 if L < 5 else 1.25)
	k.barrel(Vector3(xr + 2.05, 0, -0.2), 0.6, 0.3)
	k.lane(Vector3(xr + 0.72, 0, 4.2), Vector3(xr + 0.72, 0, 0.2), 0.5, 1.8, "unit")
	var masks := [box_mask(Vector3(xr - 0.2, -0.5, 0.5 * f), Vector3(xr + 1.8, 3.0, 3.4 * f))]
	if L >= 4:
		# finishing post with grindstone under a covered work row
		k.lean_to(Vector3(xr + 1.05, 0, 2.4), 2.0, 2.6, 2.2, 2.9, "clay_roof", 2)
		k.wheel(Vector3(xr + 1.7, 0.65, 1.8), 0.48, Vector3.FORWARD, "stone_light")
		k.box("dark_oak", Vector3(xr + 1.7, 0.3, 1.8), Vector3(0.7, 0.6, 0.35))
		k.workbench(Vector3(xr + 1.85, 0, 3.0), 1.3, 90)
	if L == 5:
		# lantern on the ridge, stone-faced front and a separate armour bay
		k.box("plaster", Vector3(0, 7.2, 0), Vector3(1.6, 0.9, 3.4))
		for z in [-1.2, -0.4, 0.4, 1.2]:
			k.box("glow", Vector3(0.81, 7.2, z), Vector3(0.02, 0.45, 0.4))
			k.box("glow", Vector3(-0.81, 7.2, z), Vector3(0.02, 0.45, 0.4))
		k.push_at(Vector3(0, 7.65, 0), 90)
		k.gable_roof("clay_roof", Vector3.ZERO, 3.6, 1.8, 0.6, 0.2)
		k.pop()
		k.stone_wall(Vector3(-4.4, 0, 4.05), Vector3(-1.6, 0, 4.05), 1.6, 0.3, "stone", [], true, true)
		k.stone_wall(Vector3(1.6, 0, 4.05), Vector3(4.4, 0, 4.05), 1.6, 0.3, "stone", [], true, true)
		var ab := Vector3(-5.6, 0, 1.6)
		k.open_shed(ab, 1.8, 3.0, 2.2, 0.8, "clay_roof", 2, 2, false)
		for i in 3:
			var p := ab + Vector3(0, 0, -1.0 + i * 1.0)
			k.cyl("dark_oak", p, p + Vector3(0, 1.35, 0), 0.04, 6)
			k.box("iron", p + Vector3(0, 1.15, 0), Vector3(0.45, 0.55, 0.28), 0, k.jitter(0.1))
			k.cyl("iron", p + Vector3(0, 1.45, 0), p + Vector3(0, 1.7, 0), 0.13, 8)
	return base("smith", masks)

# ============================================================== B15 Military Academy (MIL-05)
static func b15_academy(k, L: int) -> Dictionary:
	var f := 1.0 + 0.055 * (L - 1)
	var bx := 1.6 * f       # right wall of the main block
	var masks := []
	# map pavilion: the academy's reading cue is a big pale table with a campaign map
	var pc := Vector3(4.1, 0, 0.6)
	if L <= 3:
		k.ground(pc + Vector3(-1.6, 0, -1.4), pc + Vector3(1.6, 0, 1.4), "plank" if L == 1 else "stone_light", 0.06)
		k.open_shed(pc, 2.8 if L < 3 else 3.4, 2.4, 2.4, 0.85, "clay_roof", 2, 2, true)
		k.box("cloth_red", pc + Vector3(0, 2.42, 1.27), Vector3(3.0 if L < 3 else 3.4, 0.28, 0.03))
		k.map_table(pc + Vector3(0, 0.06, 0.05), 2.0 if L < 3 else 2.4, 1.25, 0)
	else:
		# L4: separate hipped pavilion for the map
		k.paving(pc + Vector3(-1.8, 0, -1.6), pc + Vector3(1.8, 0, 1.6), 0.06, 0.5)
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				var p := pc + Vector3(sx * 1.45, 0, sz * 1.25)
				k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 0.4))
				k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, 2.5, 0), 0.24, 0.24)
		k.beam("oak", pc + Vector3(-1.6, 2.55, 1.25), pc + Vector3(1.6, 2.55, 1.25), 0.2, 0.24)
		k.beam("oak", pc + Vector3(-1.6, 2.55, -1.25), pc + Vector3(1.6, 2.55, -1.25), 0.2, 0.24)
		k.hip_roof("clay_roof", pc + Vector3(0, 2.65, 0), 3.2, 2.8, 1.2, 0.35)
		k.map_table(pc + Vector3(0, 0.06, 0), 2.3, 1.4, 0)
	k.lane(pc + Vector3(0, 0, 2.6), pc + Vector3(0, 0, 0.95), 0.9, 1.9, "unit")
	if L >= 2:
		# permanent covered gallery joining the block to the map area
		var g0 := Vector3(bx, 0, -1.2)
		var g1 := Vector3(pc.x - 1.4, 0, -1.2)
		for i in 3:
			var p := g0.lerp(g1, i / 2.0) + Vector3(0, 0, 0.55)
			k.beam("oak", p, p + Vector3(0, 2.3, 0), 0.18, 0.18)
		k.beam("oak", g0 + Vector3(0, 2.35, 0.55), g1 + Vector3(0, 2.35, 0.55), 0.16, 0.2)
		k.lean_to((g0 + g1) * 0.5 + Vector3(0, 0, 0), g1.x - g0.x + 0.2, 1.1, 2.35, 2.8, "slate_roof", 0)
		k.ground(g0 + Vector3(0, 0, -0.5), g1 + Vector3(0, 0, 0.6), "stone_light", 0.05)
		# two dormers on the front slope of the main roof
		for dx in [-0.75, 0.75]:
			k.push_at(Vector3(dx * f - 0.2, 3.25 * f, -0.2 * f))
			k.box("plaster", Vector3(0, 0.4, 0), Vector3(0.8, 0.8, 1.2))
			k.window(Vector3(0, 0, 0.61), 0.38, 0.18, 0.62, 0, false)
			k.push_at(Vector3(0, 0.8, 0), 90)
			k.gable_roof("slate_roof", Vector3.ZERO, 1.3, 0.95, 0.45, 0.12, "plaster")
			k.pop()
			k.pop()
	if L >= 3:
		# new right gable wing behind the map bay
		k.timber_house(Vector3(4.3, 0, -3.3), 3.0, 2.4, 2.9, 1.2, [{"at": 1.5, "w": 0.45, "y0": 0.9, "y1": 1.5, "kind": "window"}], [], [], [{"at": 1.2, "w": 0.45, "y0": 0.9, "y1": 1.5, "kind": "window"}], "slate_roof", "plaster", 0.35)
	if L == 4:
		# gallery wrapping the training court on the left
		var gx := -4.9
		for i in 5:
			var z := -2.6 + i * 1.5
			k.beam("oak", Vector3(gx + 0.55, 0, z), Vector3(gx + 0.55, 2.3, z), 0.18, 0.18)
		k.beam("oak", Vector3(gx + 0.55, 2.35, -2.8), Vector3(gx + 0.55, 2.35, 3.4), 0.16, 0.2)
		k.push_at(Vector3(gx, 0, 0.3), 90)
		k.lean_to(Vector3.ZERO, 6.4, 1.2, 2.35, 2.9, "slate_roof", 0)
		k.pop()
		k.ground(Vector3(gx - 0.5, 0, -2.8), Vector3(gx + 0.7, 0, 3.4), "stone_light", 0.05)
		masks.append(box_mask(Vector3(-5.6, -0.5, -0.5), Vector3(-4.0, 3.0, 2.0)))
	return base("academy27", masks)

# ============================================================== B16 Infirmary (SUP-01)
static func b16_infirmary(k, L: int) -> Dictionary:
	# covered reception on the right; reached from grade by one continuous gentle ramp
	var fy := 0.42
	var lo := Vector3(3.7, 0, -2.4)
	var hi := Vector3(6.5, 0, 2.2)
	k.box("stone", Vector3((lo.x + hi.x) * 0.5, fy * 0.5 - 0.1, (lo.z + hi.z) * 0.5), Vector3(hi.x - lo.x + 0.1, fy + 0.2, hi.z - lo.z + 0.1), 0, k.jitter(0.03))
	k.paving(lo, hi, fy + 0.04, 0.45)
	for sx in [lo.x + 0.15, hi.x - 0.15]:
		for sz in [lo.z + 0.15, 0.0, hi.z - 0.15]:
			k.beam("oak", Vector3(sx, fy, sz), Vector3(sx, fy + 2.5, sz), 0.22, 0.22)
	k.beam("oak", Vector3(lo.x, fy + 2.55, hi.z - 0.15), Vector3(hi.x, fy + 2.55, hi.z - 0.15), 0.2, 0.24)
	k.beam("oak", Vector3(lo.x, fy + 2.55, lo.z + 0.15), Vector3(hi.x, fy + 2.55, lo.z + 0.15), 0.2, 0.24)
	k.push_at(Vector3((lo.x + hi.x) * 0.5, 0, (lo.z + hi.z) * 0.5), 90)
	k.gable_roof("slate_roof", Vector3(0, fy + 2.62, 0), hi.z - lo.z, hi.x - lo.x, 1.0, 0.35, "plaster")
	k.gable_frame(Vector3(0, fy + 2.62, 0), hi.z - lo.z, hi.x - lo.x, 1.0)
	k.pop()
	k.timber_wall(Vector3(hi.x, fy, lo.z), Vector3(lo.x, fy, lo.z), 2.5, [], "plaster")
	k.stretcher(Vector3(5.0, fy, -0.3), 90)
	k.bed(Vector3(5.3, fy, -1.55), 90)
	for i in 3:
		k.box("oak", Vector3(4.6 + i * 0.7, fy + 0.9 + 0.0, -2.2), Vector3(0.6, 0.05, 0.3))
		k.cyl("clay_roof", Vector3(4.5 + i * 0.7, fy + 0.93, -2.2), Vector3(4.5 + i * 0.7, fy + 1.15, -2.2), 0.07, 8)
	k.box("cloth_red", Vector3(5.1, fy + 1.9, -2.27), Vector3(0.4, 0.12, 0.02))
	k.box("cloth_red", Vector3(5.1, fy + 1.9, -2.27), Vector3(0.12, 0.4, 0.02))
	k.lantern(Vector3(lo.x + 0.15, fy + 2.2, hi.z - 0.05))
	# ramp: grade -> floor over 4.4 m (about 1:10), wide enough for a stretcher pair
	k.ramp(Vector3(5.1, 0, 6.6), Vector3(5.1, fy, 2.2), 2.2, "stone_light", true, true, 0.14)
	k.paving(Vector3(3.9, 0, 6.6), Vector3(6.3, 0, 7.0), 0.03, 0.45)
	k.lane(Vector3(5.1, 0, 7.0), Vector3(5.1, fy, 0.6), 1.4, 2.1, "stretcher")
	return base("hospital27", [box_mask(Vector3(3.2, -0.5, -1.8), Vector3(4.2, 1.5, 1.5))])

# ============================================================== B17 Siege Workshop (SUP-02)
static func b17_workshop(k, L: int) -> Dictionary:
	if L == 1:
		# open platform: big joinery frame and separate wheels
		var lo := Vector3(0.7, 0, 0.3)
		var hi := Vector3(3.9, 0, 3.3)
		k.deck(lo, hi, 0.32, "plank", true, true, true)
		k.stairs(Vector3(2.9, 0, 3.75), 0.9, 2, 0.16, 0.22, 0, "oak", false)
		var c := Vector3(2.2, 0.32, 1.6)
		for s in [-1.0, 1.0]:
			k.beam("oak", c + Vector3(-1.0, 0, s * 0.55), c + Vector3(1.0, 0, s * 0.55), 0.2, 0.2)
			k.beam("oak", c + Vector3(-0.8, 0.1, s * 0.55), c + Vector3(-0.2, 1.7, s * 0.2), 0.16, 0.16)
			k.beam("oak", c + Vector3(0.8, 0.1, s * 0.55), c + Vector3(0.2, 1.7, s * 0.2), 0.16, 0.16)
		k.beam("oak", c + Vector3(0, 1.72, -0.35), c + Vector3(0, 1.72, 0.35), 0.18, 0.18)
		k.beam("oak", c + Vector3(-0.95, 0.5, 0), c + Vector3(0.95, 0.5, 0), 0.14, 0.14)
		k.wheel(Vector3(3.55, 0.85, 0.6), 0.55, Vector3(0.94, 0, 0.34))
		k.wheel(Vector3(3.6, 0.85, 1.4), 0.55, Vector3(0.94, 0, -0.34))
		k.workbench(Vector3(1.3, 0.32, 2.8), 1.4, 0)
		k.sawhorse(Vector3(3.2, 0.32, 2.7), 90)
		return base("workshop27", [box_mask(Vector3(0.5, 0.25, -0.2), Vector3(4.2, 4.0, 3.7))])
	# L4/L5: tall lifting hall on the right with a roof lantern
	var x0 := 0.9
	var x1 := 6.3
	var z0 := -3.0
	var z1 := 2.9
	var fy := 0.38
	k.deck(Vector3(x0, 0, z0), Vector3(x1, 0, z1), fy, "plank", true, true, false)
	for x in [x0 + 0.15, (x0 + x1) * 0.5, x1 - 0.15]:
		for z in [z0 + 0.15, z1 - 0.15]:
			k.box("stone", Vector3(x, fy + 0.15, z), Vector3(0.42, 0.3, 0.42))
			k.beam("oak", Vector3(x, fy + 0.3, z), Vector3(x, fy + 3.8, z), 0.28, 0.28)
			k.beam("oak", Vector3(x, fy + 3.0, z), Vector3(x + (0.7 if x < x1 - 0.5 else -0.7), fy + 3.75, z), 0.14, 0.14)
	for z in [z0 + 0.15, z1 - 0.15]:
		k.beam("oak", Vector3(x0 - 0.2, fy + 3.85, z), Vector3(x1 + 0.2, fy + 3.85, z), 0.24, 0.3)
	k.timber_wall(Vector3(x1, fy, z0), Vector3(x0, fy, z0), 3.8, [], "plaster")
	k.push_at(Vector3((x0 + x1) * 0.5, 0, (z0 + z1) * 0.5), 90)
	k.gable_roof("clay_roof", Vector3(0, fy + 4.0, 0), z1 - z0, x1 - x0, 1.9, 0.35, "plaster")
	k.gable_frame(Vector3(0, fy + 4.0, 0), z1 - z0, x1 - x0, 1.9)
	# ridge lantern (clerestory) running along the hall
	k.box("plaster", Vector3(0, fy + 6.05, 0), Vector3(3.2, 0.55, 0.9))
	for i in 5:
		k.box("glow", Vector3(-1.2 + i * 0.6, fy + 6.05, 0.46), Vector3(0.35, 0.28, 0.02))
	k.gable_roof("clay_roof", Vector3(0, fy + 6.35, 0), 3.2, 0.9, 0.3, 0.15)
	k.cyl("dark_oak", Vector3(0, fy + 6.6, 0), Vector3(0, fy + 7.0, 0), 0.25, 6)
	k.cone("clay_roof", Vector3(0, fy + 7.0, 0), 0.38, 0.4, 6)
	k.pop()
	# hoist beam and hook over its own marked bay (left), clear of the drive-in strip (right)
	var hook := Vector3(2.4, fy, -0.4)
	k.box("plank", hook + Vector3(0, 0.005, 0), Vector3(1.5, 0.01, 1.5), 0, Color(0.75, 0.62, 0.48))
	k.beam("oak", Vector3(hook.x, fy + 3.85, z0 + 0.15), Vector3(hook.x, fy + 3.85, z1 - 0.15), 0.22, 0.26)
	k.hook_hoist(Vector3(hook.x, fy + 3.7, hook.z), 1.9)
	k.wheel(Vector3(1.5, fy + 0.65, -2.4), 0.55, Vector3.FORWARD)
	# workbenches pushed to the left wall, away from the lane
	k.workbench(Vector3(1.35, fy, 1.2), 1.4, 90)
	k.workbench(Vector3(3.0, fy, -2.5), 1.6, 0)
	k.weapon_rack(Vector3(5.6, fy, -2.75), 1.2, 0)
	if L == 4:
		k.stairs(Vector3(4.7, 0, z1 + 0.62), 1.1, 2, 0.19, 0.3, 0, "oak", false)
		k.lane(Vector3(4.7, 0, 4.0), Vector3(4.7, fy, -1.5), 0.9, 2.6, "stair")
		return base("workshop27", [box_mask(Vector3(0.5, 0.2, -1.4), Vector3(4.4, 4.0, 3.9))])
	# L5: wide ramp straight onto the working floor + inner gallery with stair
	k.ramp(Vector3(4.8, 0, 6.8), Vector3(4.8, fy, z1), 2.2, "plank", true, true, 0.16)
	k.lane(Vector3(4.75, 0, 6.9), Vector3(4.75, fy, -1.5), 1.6, 3.0, "cart")
	k.deck(Vector3(3.5, 0, z0 + 0.2), Vector3(x1 - 0.2, 0, z0 + 1.1), fy + 2.3, "plank", true, true, true)
	k.railing(Vector3(3.5, fy + 2.3, z0 + 1.1), Vector3(x1 - 0.9, fy + 2.3, z0 + 1.1), 0.85)
	k.stairs(Vector3(x1 - 0.32, fy, z0 + 3.05), 0.5, 7, 0.33, 0.27, 0, "oak", false)
	for i in 3:
		k.crate(Vector3(4.0 + i * 0.6, fy + 2.3, z0 + 0.6), 0.45)
	return base("workshop27", [box_mask(Vector3(0.5, 0.2, -1.4), Vector3(4.4, 4.0, 3.9))])

# ============================================================== B19 Watchtower (SUP-04)
static func b19_watchtower(k, L: int) -> Dictionary:
	var dy := 4.15
	# wider wrap-around deck on corbels braced back into the tower shaft
	k.deck(Vector3(-3.1, 0, -2.9), Vector3(1.4, 0, 2.9), dy, "plank", false, true, true)
	for x in [-2.9, -1.2, 0.6]:
		for z in [-2.7, 2.7]:
			var corbel_root := Vector3(clampf(x, -1.6, 1.6), dy - 1.5, signf(z) * 1.6)
			k.beam("oak", corbel_root, Vector3(x, dy - 0.12, z), 0.16, 0.16)
	for z in [-2.7, -0.9, 0.9, 2.7]:
		k.beam("oak", Vector3(-1.6, dy - 1.5, z * 0.6), Vector3(-2.9, dy - 0.12, z), 0.16, 0.16)
	k.railing(Vector3(-3.1, dy, 2.9), Vector3(1.0, dy, 2.9), 1.0)
	k.railing(Vector3(-3.1, dy, -2.9), Vector3(1.4, dy, -2.9), 1.0)
	k.railing(Vector3(-3.1, dy, -2.9), Vector3(-3.1, dy, 2.9), 1.0)
	# separate gabled watch bay on the right
	var c := Vector3(2.5, dy, -1.0)
	k.deck(Vector3(1.4, 0, -2.3), Vector3(3.7, 0, 0.3), dy, "plank", false, true, true)
	for sx in [1.5, 3.55]:
		for sz in [-2.15, 0.15]:
			k.beam("oak", Vector3(sx, dy, sz), Vector3(sx, dy + 2.0, sz), 0.18, 0.18)
			k.beam("oak", Vector3(sx, dy - 1.3, sz * 0.7), Vector3(sx, dy - 0.1, sz), 0.14, 0.14)
	k.railing(Vector3(3.7, dy, -2.3), Vector3(3.7, dy, 0.3), 1.0)
	k.gable_roof("slate_roof", Vector3(2.55, dy + 2.05, -1.0), 2.4, 2.6, 1.0, 0.3, "oak")
	k.gable_frame(Vector3(2.55, dy + 2.05, -1.0), 2.4, 2.6, 1.0)
	k.banner(Vector3(3.83, dy + 1.8, -1.0), 0.45, 0.7, "cloth_blue", 90)
	# stair lands on a clear part of the deck
	k.lane(Vector3(2.65, dy, 0.1), Vector3(2.65, dy, -1.6), 0.6, 1.85, "unit")
	k.lane(Vector3(-2.65, dy, 2.5), Vector3(-2.65, dy, -2.5), 0.55, 1.85, "unit")
	return base("watchtower27")

# ============================================================== B21 Sawmill (ALT-02)
static func b21_sawmill(k, L: int) -> Dictionary:
	if L == 1:
		# open pavilion over a saw pit: log on trestles and a big two-man pit saw
		k.ground(Vector3(-3.6, 0, -2.6), Vector3(3.6, 0, 3.0), "earth", 0.02)
		k.open_shed(Vector3(0, 0, 0), 6.0, 4.2, 2.7, 1.5, "shingle", 3, 2, true)
		k.box("soil", Vector3(0.4, -0.02, 0.2), Vector3(4.0, 0.06, 1.1), 0, Color(0.55, 0.5, 0.45))
		for s in [-1.0, 1.0]:
			k.box("dark_oak", Vector3(0.4, 0.1, 0.2 + s * 0.62), Vector3(4.2, 0.2, 0.18))
		k.cyl("log", Vector3(-1.8, 0.62, 0.2), Vector3(2.6, 0.62, 0.2), 0.3, 10)
		k.sawhorse(Vector3(-1.2, 0, 0.2), 0)
		k.sawhorse(Vector3(2.0, 0, 0.2), 0)
		k.box("iron", Vector3(0.6, 0.85, 0.2), Vector3(0.04, 1.9, 0.32))
		k.beam("dark_oak", Vector3(0.6, 1.85, 0.0), Vector3(0.6, 1.85, 0.4), 0.06, 0.06)
		k.beam("dark_oak", Vector3(0.6, -0.1, 0.0), Vector3(0.6, -0.1, 0.4), 0.06, 0.06)
		k.workbench(Vector3(-2.3, 0, -1.5), 1.4, 0)
		k.plank_stack(Vector3(2.3, 0, -1.5), 1.6, 0.8, 4, 90)
		k.road(Vector3(0.4, 0, 6.6), Vector3(0.4, 0, 2.2), 1.6, "earth", 0.02, 0.3)
		return {}
	# L4/L5: lumber block + open saw bay fed with round logs from the front
	var bay_lo := Vector3(3.9, 0, -3.2)
	var bay_hi := Vector3(6.7, 0, 2.6)
	var fy := 0.55
	k.deck(bay_lo, bay_hi, fy, "plank", true, true, false)
	var h := 3.0 if L == 4 else 4.2
	for x in [bay_lo.x + 0.15, bay_hi.x - 0.15]:
		for z in [bay_lo.z + 0.15, -0.3, bay_hi.z - 0.15]:
			k.beam("oak", Vector3(x, fy, z), Vector3(x, fy + h, z), 0.24, 0.24)
	for x in [bay_lo.x + 0.15, bay_hi.x - 0.15]:
		k.beam("oak", Vector3(x, fy + h, bay_lo.z), Vector3(x, fy + h, bay_hi.z), 0.2, 0.26)
	k.push_at(Vector3((bay_lo.x + bay_hi.x) * 0.5, 0, (bay_lo.z + bay_hi.z) * 0.5))
	k.push_at(Vector3.ZERO, 90)
	k.gable_roof("slate_roof", Vector3(0, fy + h + 0.1, 0), bay_hi.z - bay_lo.z, bay_hi.x - bay_lo.x, 1.2, 0.35, "plaster")
	k.gable_frame(Vector3(0, fy + h + 0.1, 0), bay_hi.z - bay_lo.z, bay_hi.x - bay_lo.x, 1.2)
	k.pop()
	k.pop()
	# log carriage: rails from the front edge to the vertical saw frame
	var fx := 5.3
	for s in [-0.45, 0.45]:
		k.beam("iron", Vector3(fx + s, fy + 0.05, 4.8), Vector3(fx + s, fy + 0.05, -2.2), 0.06, 0.06)
	k.deck(Vector3(4.4, 0, 2.6), Vector3(6.2, 0, 5.2), fy, "plank", true, true, false)
	k.cyl("log", Vector3(fx, fy + 0.4, 3.3), Vector3(fx, fy + 0.4, 0.2), 0.3, 10)
	for z in [2.9, 0.8]:
		k.box("dark_oak", Vector3(fx, fy + 0.12, z), Vector3(1.1, 0.14, 0.3))
	var sf := Vector3(fx, fy, -0.9)
	for s in [-0.75, 0.75]:
		k.beam("oak", sf + Vector3(s, 0, 0), sf + Vector3(s, 2.6, 0), 0.22, 0.22)
	k.beam("oak", sf + Vector3(-0.85, 2.6, 0), sf + Vector3(0.85, 2.6, 0), 0.22, 0.22)
	k.beam("dark_oak", sf + Vector3(-0.6, 1.5, 0), sf + Vector3(0.6, 1.5, 0), 0.16, 0.16)
	for i in 4:
		k.box("iron", sf + Vector3(-0.3 + i * 0.2, 1.0, 0), Vector3(0.025, 1.1, 0.12))
	k.wheel(sf + Vector3(1.0, 1.3, 0.5), 0.75, Vector3.RIGHT)
	k.cyl("log", sf + Vector3(0, 0.4, 0.2), sf + Vector3(0, 0.4, -1.6), 0.3, 10)
	# overhead grab; the deck below it stays free
	k.beam("oak", Vector3(4.4, fy + h - 0.3, 4.3), Vector3(6.2, fy + h - 0.3, 4.3), 0.2, 0.22)
	for x in [4.45, 6.15]:
		k.beam("oak", Vector3(x, fy, 4.3), Vector3(x, fy + h - 0.2, 4.3), 0.2, 0.2)
	k.hook_hoist(Vector3(5.3, fy + h - 0.45, 4.3), 0.1)
	k.lane(Vector3(fx, fy, 5.1), Vector3(fx, fy, 3.7), 1.0, 1.75, "unit")
	k.log_pile(Vector3(2.4, 0, 5.6), 2.4, 2, 0.24, 90)
	var masks := [box_mask(Vector3(3.6, -0.5, 0.2), Vector3(5.6, 3.0, 2.8))]
	if L == 5:
		# separate covered board delivery (flat planks) on the right side
		k.lean_to(Vector3(5.5, 0, -4.6), 2.4, 1.6, 2.2, 2.8, "slate_roof", 2)
		k.plank_stack(Vector3(5.5, 0, -4.6), 2.0, 1.0, 7, 90)
		k.ramp(Vector3(6.6, 0, -5.5), Vector3(6.6, fy, -3.2), 0.8, "plank", false)
		k.box("plaster", Vector3(5.3, fy + h + 1.6, -0.3), Vector3(1.0, 0.7, 4.8))
		for z in [-2.0, -0.9, 0.2, 1.3]:
			k.box("glow", Vector3(5.8, fy + h + 1.6, z), Vector3(0.02, 0.35, 0.5))
		k.push_at(Vector3(5.3, 0, -0.3), 90)
		k.gable_roof("slate_roof", Vector3(0, fy + h + 1.95, 0), 4.8, 1.2, 0.45, 0.15)
		k.pop()
	return base("lumber", masks)

# ============================================================== B23 Hunting Lodge (ALT-06)
static func b23_lodge(k, L: int) -> Dictionary:
	# long covered terrace across the front
	k.deck(Vector3(-3.0, 0, 0.7), Vector3(2.3, 0, 2.5), 0.38, "plank", true, true, true)
	for i in 5:
		var x := -2.85 + i * 1.25
		k.beam("oak", Vector3(x, 0.38, 2.35), Vector3(x, 2.55, 2.35), 0.2, 0.2)
		k.beam("oak", Vector3(x, 2.0, 2.35), Vector3(x + (0.45 if i < 4 else -0.45), 2.5, 2.35), 0.1, 0.1)
	k.beam("oak", Vector3(-3.1, 2.58, 2.35), Vector3(2.4, 2.58, 2.35), 0.18, 0.22)
	k.lean_to(Vector3(-0.35, 0, 1.55), 5.5, 1.8, 2.6, 3.05, "slate_roof", 0)
	k.railing(Vector3(-3.0, 0.38, 2.5), Vector3(-0.6, 0.38, 2.5), 0.8)
	k.railing(Vector3(0.9, 0.38, 2.5), Vector3(2.3, 0.38, 2.5), 0.8)
	k.railing(Vector3(2.3, 0.38, 0.7), Vector3(2.3, 0.38, 2.5), 0.8)
	k.stairs(Vector3(0.15, 0, 3.0), 1.3, 2, 0.19, 0.25, 0, "oak", false)
	k.bench(Vector3(1.4, 0.38, 1.0), 1.4, 0)
	k.table(Vector3(-1.9, 0.38, 1.5), 1.2, 0.7, 0.75)
	k.lantern(Vector3(-0.6, 2.25, 2.35))
	k.lantern(Vector3(1.9, 2.25, 2.35))
	# low stone storeroom with its own gable and a full-size door
	var c := Vector3(3.6, 0, -1.9)
	k.stone_wall(c + Vector3(-1.4, 0, 1.15), c + Vector3(1.4, 0, 1.15), 2.0, 0.4, "stone", [{"at": 1.4, "w": 1.0, "y0": 0.0, "y1": 1.8, "kind": "door"}])
	k.stone_wall(c + Vector3(1.4, 0, -1.15), c + Vector3(-1.4, 0, -1.15), 2.0, 0.4)
	k.stone_wall(c + Vector3(1.4, 0, 1.15), c + Vector3(1.4, 0, -1.15), 2.0, 0.4)
	k.stone_wall(c + Vector3(-1.4, 0, -1.15), c + Vector3(-1.4, 0, 1.15), 2.0, 0.4)
	k.push_at(c, 90)
	k.gable_roof("slate_roof", Vector3(0, 2.05, 0), 2.7, 3.2, 1.0, 0.3, "stone")
	k.pop()
	k.box("dark_oak", c + Vector3(0, 2.6, 1.42), Vector3(0.9, 0.05, 0.05))
	k.road(Vector3(3.6, 0, 4.2), Vector3(3.6, 0, -0.5), 1.2, "path", 0.02, 0.3)
	k.lane(Vector3(3.6, 0, 3.4), Vector3(3.6, 0, -0.45), 0.9, 1.75, "unit")
	return base("hunt27", [box_mask(Vector3(-3.4, -0.5, 1.8), Vector3(5.0, 3.0, 3.2)), box_mask(Vector3(2.4, -0.5, -3.2), Vector3(5.0, 3.0, 3.95))])

# ============================================================== B24 Fishing Hut (ALT-07)
static func b24_fishing(k, L: int) -> Dictionary:
	## Shore geometry stays exactly as level I: the L1 model is kept unchanged under every level
	## and the new decks/piers develop over its dock and inside the original plot.
	var dock_y := 0.36
	# II: covered deck and net racks; III widens it into a front-facing gable
	if L == 2:
		k.open_shed(Vector3(1.7, dock_y, 2.0), 2.0, 1.6, 2.1, 0.75, "slate_roof", 2, 2, true)
	else:
		k.open_shed(Vector3(1.5, dock_y, 2.2), 2.8, 2.2, 2.3, 1.1, "slate_roof", 2, 2, false)
		k.box("oak", Vector3(1.5, dock_y + 2.6, 3.35), Vector3(2.9, 0.18, 0.12))
	for i in 2:
		var x := 3.6 + i * 1.2
		k.cyl("dark_oak", Vector3(x, 0, -1.6), Vector3(x, 2.3, -1.6), 0.07, 6)
	k.beam("dark_oak", Vector3(3.5, 2.2, -1.6), Vector3(4.9, 2.2, -1.6), 0.07, 0.07)
	for i in 7:
		k.beam("rope", Vector3(3.62 + i * 0.19, 2.15, -1.6), Vector3(3.6 + i * 0.19 + 0.05, 0.95 - 0.05 * (i % 3), -1.6), 0.02, 0.02)
	for j in 5:
		k.beam("rope", Vector3(3.62, 2.0 - j * 0.24, -1.6), Vector3(4.78, 1.95 - j * 0.24, -1.6), 0.02, 0.02)
	for i in 3:
		k.barrel(Vector3(-2.0 + i * 0.6, dock_y, 3.9), 0.5, 0.2)
	if L >= 3:
		# raised processing deck with a guard rail, reached by a gentle ramp from the dock
		var py := 0.6
		k.deck(Vector3(3.0, 0, -0.1), Vector3(5.2, 0, 2.6), py, "oak", true, true, true)
		k.railing(Vector3(3.0, py, 2.6), Vector3(5.2, py, 2.6), 0.9)
		k.railing(Vector3(5.2, py, -0.1), Vector3(5.2, py, 2.6), 0.9)
		k.table(Vector3(4.3, py, 1.6), 1.4, 0.7, 0.8)
		for i in 4:
			k.box("map_blue", Vector3(3.9 + i * 0.25, py + 0.82, 1.6), Vector3(0.18, 0.04, 0.5), 10)
		k.ramp(Vector3(1.2, dock_y, 0.25), Vector3(3.0, py, 0.25), 0.9, "oak", false)
		k.lane(Vector3(1.3, dock_y, 0.25), Vector3(4.6, py, 0.25), 0.7, 1.8, "unit")
	if L >= 4:
		# long pier with a ladder and a separate far canopy
		k.deck(Vector3(2.9, 0, 3.0), Vector3(6.6, 0, 4.4), dock_y, "oak", true, true, true)
		k.deck(Vector3(5.4, 0, 4.4), Vector3(6.6, 0, 6.7), dock_y, "oak", true, true, false)
		for z in [3.2, 4.2, 5.5, 6.5]:
			k.cyl("dark_oak", Vector3(6.6, -0.4, z), Vector3(6.6, dock_y + 0.55, z), 0.1, 7)
		k.beam("dark_oak", Vector3(6.75, -0.3, 5.9), Vector3(6.75, dock_y + 0.4, 5.9), 0.05, 0.05)
		for y in [0.0, 0.25]:
			k.beam("dark_oak", Vector3(6.75, y, 5.75), Vector3(6.75, y, 6.05), 0.04, 0.04)
		k.lane(Vector3(3.2, dock_y, 3.7), Vector3(6.0, dock_y, 3.7), 1.0, 1.8, "unit")
		k.lane(Vector3(6.0, dock_y, 3.7), Vector3(6.0, dock_y, 6.5), 0.9, 1.8, "unit")
		if L == 4:
			k.open_shed(Vector3(5.6, 0, -2.4), 2.0, 1.8, 2.2, 0.8, "slate_roof", 2, 2, false)
			k.barrel(Vector3(5.2, 0, -2.6)); k.crate(Vector3(6.0, 0, -2.2))
	if L == 5:
		# enclosed far storehouse and a tall drying rack
		k.timber_house(Vector3(5.6, 0, -2.4), 2.0, 2.0, 2.4, 0.9, [{"at": 1.0, "w": 0.8, "y0": 0.0, "y1": 1.7, "kind": "door"}], [], [], [], "slate_roof", "oak", 0.3)
		var r := Vector3(1.5, 0, -2.9)
		for s in [-1.1, 1.1]:
			k.cyl("dark_oak", r + Vector3(s, 0, 0), r + Vector3(s, 3.4, 0), 0.08, 6)
		for y in [1.6, 2.3, 3.0]:
			k.beam("dark_oak", r + Vector3(-1.2, y, 0), r + Vector3(1.2, y, 0), 0.06, 0.06)
			for i in 6:
				k.box("map_blue", r + Vector3(-0.9 + i * 0.36, y - 0.25, 0), Vector3(0.1, 0.4, 0.04), 0, Color(0.9, 0.95, 1.0))
		k.crane(Vector3(4.95, 0.6, 2.3), 2.6, Vector3(0.9, 0, 1.3), 0.35)
	# the mooring post under the new pier is lifted out; the dock and shore stay as in level I
	return base("fishing27", [box_mask(Vector3(2.95, -0.6, 2.9), Vector3(3.95, 2.0, 3.9))])

# ============================================================== B25 Herbal Garden (ALT-08)
static func b25_herbal(k, L: int) -> Dictionary:
	# enlarged lower glazed zone filled with beds
	var lo := Vector3(0.6, 0, -3.4)
	var hi := Vector3(5.6, 0, 0.4)
	k.box("stone", Vector3((lo.x + hi.x) * 0.5, 0.2, (lo.z + hi.z) * 0.5), Vector3(hi.x - lo.x, 0.4, hi.z - lo.z), 0, k.jitter(0.03))
	var gh := 2.2
	for i in 5:
		var x := lerpf(lo.x, hi.x, i / 4.0)
		for z in [lo.z, hi.z]:
			k.beam("oak", Vector3(x, 0.4, z), Vector3(x, gh, z), 0.12, 0.12)
	for z in [lo.z, hi.z]:
		k.beam("oak", Vector3(lo.x, gh, z), Vector3(hi.x, gh, z), 0.12, 0.14)
		k.beam("oak", Vector3(lo.x, 1.2, z), Vector3(hi.x, 1.2, z), 0.06, 0.08)
	k.box("greenglass", Vector3((lo.x + hi.x) * 0.5, 1.3, hi.z), Vector3(hi.x - lo.x, 1.8, 0.03))
	k.box("greenglass", Vector3(hi.x, 1.3, (lo.z + hi.z) * 0.5), Vector3(0.03, 1.8, hi.z - lo.z))
	k.push_at(Vector3((lo.x + hi.x) * 0.5, 0, (lo.z + hi.z) * 0.5))
	k.shingle_slope("greenglass", Vector3(-2.6, gh, 2.0), Vector3(2.6, gh, 2.0), Vector3(-2.6, gh + 1.1, -0.2), Vector3(2.6, gh + 1.1, -0.2), 0.6, 0.9, 0.02)
	k.pop()
	for i in 3:
		var x := 1.2 + i * 1.5
		k.push_at(Vector3(0, 0.4, 0))
		k.garden_bed(Vector3(x, 0, -3.0), Vector3(x + 1.1, 0, 0.0), "herb" if i != 1 else "lavender", 3, true)
		k.pop()
	# separate upper drying loft; its posts continue the greenhouse frame
	var dl := Vector3(lo.x, 0, lo.z)
	for x in [lo.x, lo.x + 2.5]:
		k.beam("oak", Vector3(x, gh, lo.z), Vector3(x, gh + 2.0, lo.z), 0.14, 0.14)
		k.beam("oak", Vector3(x, gh, lo.z + 1.1), Vector3(x, gh + 2.0, lo.z + 1.1), 0.14, 0.14)
	k.deck(Vector3(lo.x - 0.1, 0, lo.z - 0.1), Vector3(lo.x + 2.6, 0, lo.z + 1.2), gh + 1.15, "plank", false, false, true)
	for y in [gh + 1.55, gh + 1.9]:
		k.beam("dark_oak", Vector3(lo.x, y, lo.z + 0.55), Vector3(lo.x + 2.5, y, lo.z + 0.55), 0.05, 0.05)
		for i in 7:
			k.box("lavender" if i % 2 == 0 else "herb", Vector3(lo.x + 0.2 + i * 0.35, y - 0.18, lo.z + 0.55), Vector3(0.12, 0.3, 0.12))
	k.gable_roof("slate_roof", Vector3(lo.x + 1.25, gh + 2.05, lo.z + 0.55), 2.7, 1.3, 0.6, 0.25)
	# tall chimney (level IV form)
	k.chimney(Vector3(-0.6, 2.0, -2.6), 3.6, 0.6)
	# low stone garden wall with a gate
	k.stone_wall(Vector3(-3.8, 0, 3.6), Vector3(-0.4, 0, 3.6), 0.6, 0.35, "stone", [], false, false)
	k.stone_wall(Vector3(0.8, 0, 3.6), Vector3(5.2, 0, 3.6), 0.6, 0.35, "stone", [], false, false)
	k.road(Vector3(0.2, 0, 6.2), Vector3(0.2, 0, 3.4), 1.1, "path", 0.02, 0.4)
	k.lane(Vector3(0.2, 0, 4.6), Vector3(0.2, 0, 3.3), 1.0, 1.8, "unit")
	return base("herbal27")

# ============================================================== B26 Stone Workshop (ALT-09)
static func b26_stoneworks(k, L: int) -> Dictionary:
	# open work shelter; approach open from the left
	k.ground(Vector3(-3.0, 0, -2.0), Vector3(2.8, 0, 2.4), "earth", 0.02)
	k.open_shed(Vector3(0.6, 0, -0.4), 3.6, 2.6, 2.5, 1.0, "shingle", 2, 2, true)
	k.workbench(Vector3(0.6, 0, -0.9), 1.9, 0)
	k.box("iron", Vector3(0.1, 0.93, -0.8), Vector3(0.28, 0.06, 0.06), 30)
	# dressed pale block and a rough blank in front of the bench
	k.stone_block(Vector3(0.2, 0, 0.6), Vector3(0.75, 0.55, 0.6), 8)
	k.stone_block(Vector3(1.5, 0, 1.0), Vector3(0.9, 0.7, 0.75), -12, true)
	k.box("dark_oak", Vector3(1.5, 0.05, 1.0), Vector3(1.1, 0.1, 0.9))
	for i in 3:
		k.stone_block(Vector3(2.4, 0, -1.4 + i * 0.55), Vector3(0.45, 0.3, 0.4), i * 7)
	k.road(Vector3(-6.4, 0, -0.4), Vector3(-1.2, 0, -0.4), 1.6, "path", 0.02, 0.6)
	k.lane(Vector3(-6.0, 0, -0.4), Vector3(-0.6, 0, -0.4), 1.0, 1.8, "unit")
	return {}
