extends RefCounted
## DRENOVAR-V6-C1.0: capital architecture VI–XI. Uses the original architecture-v2
## masonry, shingle courses, PBR surfaces and fittings without modifying them.
## A level is a new composed mesh, not a scaled copy. Metres, +Z = street entrance.

const VERSION := "DRENOVAR-V6-C1.0-ART1"
const ENTRIES := [
	{"id":"B01", "type":"ECO-05", "name":"Town Hall", "fn":"town_hall"},
	{"id":"B02", "type":"ECO-04", "name":"House", "fn":"house"},
	{"id":"B03", "type":"ECO-01", "name":"Warehouse", "fn":"warehouse"},
	{"id":"B04", "type":"ECO-02", "name":"Granary", "fn":"granary"},
	{"id":"B05", "type":"ECO-03", "name":"Marketplace", "fn":"market"},
	{"id":"B06", "type":"RES-01", "name":"Lumber Camp", "fn":"lumber"},
	{"id":"B07", "type":"RES-02", "name":"Stone Quarry", "fn":"quarry"},
	{"id":"B08", "type":"RES-03", "name":"Iron Mine", "fn":"mine"},
	{"id":"B09", "type":"RES-04", "name":"Farm", "fn":"farm"},
	{"id":"B10", "type":"RES-05", "name":"Hunting Camp", "fn":"hunting_camp"},
	{"id":"B11", "type":"MIL-01", "name":"Infantry Barracks", "fn":"barracks"},
	{"id":"B12", "type":"MIL-02", "name":"Archery Range", "fn":"archery"},
	{"id":"B13", "type":"MIL-03", "name":"Stables", "fn":"stables"},
	{"id":"B14", "type":"MIL-04", "name":"Blacksmith", "fn":"smith"},
	{"id":"B15", "type":"MIL-05", "name":"Military Academy", "fn":"academy"},
	{"id":"B16", "type":"SUP-01", "name":"Infirmary", "fn":"infirmary"},
	{"id":"B17", "type":"SUP-02", "name":"Siege Workshop", "fn":"siege"},
	{"id":"B18", "type":"SUP-03", "name":"Walls and Gate", "fn":"gate"},
	{"id":"B19", "type":"SUP-04", "name":"Watchtower", "fn":"watchtower"},
	{"id":"B20", "type":"SUP-05", "name":"Well", "fn":"well"},
	{"id":"B21", "type":"ALT-02", "name":"Sawmill", "fn":"sawmill"},
	{"id":"B22", "type":"ALT-05", "name":"Wheat Farm", "fn":"wheat"},
	{"id":"B23", "type":"ALT-06", "name":"Hunting Lodge", "fn":"lodge"},
	{"id":"B24", "type":"ALT-07", "name":"Fishing Hut", "fn":"fishing"},
	{"id":"B25", "type":"ALT-08", "name":"Herbal Garden", "fn":"herbal"},
	{"id":"B26", "type":"ALT-09", "name":"Stone Workshop", "fn":"stonework"},
	{"id":"B27", "type":"ALT-10", "name":"Smelter", "fn":"smelter"},
]

const STAGES := {
	6: "Stone load-bearing buildings; natural fields and functional wood retained",
	7: "Slate roofing, iron ties and metal joints",
	8: "Functional annexes and arcaded sections",
	9: "Strengthened supports and organised yard logistics",
	10: "Heavy masonry, metal joints and complete working infrastructure",
	11: "Finished silhouette and final fittings; no unfinished XII reserve",
}

static func roof(L: int) -> String:
	return "slate_roof" if L >= 7 else "clay_roof"

static func block(k, center: Vector3, size: Vector3, yaw := 0.0, rough := false) -> void:
	# Recipe coordinates describe centres; the shared kit's stone_block expects a base.
	k.stone_block(center - Vector3(0, size.y * 0.5, 0), size, yaw, rough)

static func rock_outcrop(k, base: Vector3, size: Vector3) -> void:
	# Irregular natural outcrop, with sloping fractured sides and a broken crest.
	# It is neither a scaled generic model nor a floating placeholder cuboid.
	var rings := []
	for r in 3:
		var ring := PackedVector3Array()
		for i in 9:
			var angle := TAU * i / 9.0
			var radius: float = k.rng.randf_range(0.86, 1.04) * (1.0 if r < 2 else 0.72)
			var y: float = -0.08 if r == 0 else size.y * (0.48 if r == 1 else k.rng.randf_range(0.82, 1.03))
			ring.append(base + Vector3(cos(angle) * size.x * 0.5 * radius, y, sin(angle) * size.z * 0.5 * radius))
		rings.append(ring)
	for r in 2:
		for i in 9:
			var next := (i + 1) % 9
			k.quad("stone_rough", rings[r][i], rings[r + 1][i], rings[r + 1][next], rings[r][next], k.jitter(0.08))
	for i in 9:
		k.tri("stone_rough", rings[2][i], base + Vector3(0, size.y * 0.93, 0), rings[2][(i + 1) % 9], k.jitter(0.06))

static func create(k, entry: Dictionary, L: int) -> Dictionary:
	assert(L >= 6 and L <= 11)
	# Type-stable seed keeps common construction geometry consistent between levels.
	Callable(load("res://../art/buildings-v6/recipes.gd"), entry.fn).call(k, L)
	return {"worker":Vector3(0, 0, 5.9), "site":{"radius":6.1},
		"stage":STAGES[L], "source":"13_BUILDING_PASSPORTS_RU.md#%s" % entry.id,
		"natural":entry.id in ["B09", "B22", "B25"]}

static func yard(k, L: int, natural := false) -> void:
	k.base_ground(6.15, "earth")
	k.road(Vector3(0, 0, 6.3), Vector3(0, 0, 1.9), 1.5, "path", 0.026, 0.18)
	if L >= 9 and not natural:
		k.paving(Vector3(-1.15, 0, 1.7), Vector3(1.15, 0, 5.4), 0.035, 0.48)
	if L >= 10:
		for x in [-5.8, 5.8]:
			block(k, Vector3(x, 0.3, 4.7), Vector3(0.45, 0.6, 0.45))
			k.box("iron", Vector3(x, 0.51, 4.7), Vector3(0.47, 0.1, 0.47))

static func building(k, c: Vector3, size: Vector2, height: float, L: int, door_w := 1.25, front_windows := true, hip := false) -> void:
	## Entire bearing shell and gables are coursed stone. No timber-frame substitution.
	var x0 := c.x - size.x * 0.5
	var x1 := c.x + size.x * 0.5
	var z0 := c.z - size.y * 0.5
	var z1 := c.z + size.y * 0.5
	var front := [{"at":size.x * 0.5, "w":door_w, "y0":0.0, "y1":minf(2.7, height - 0.4), "kind":"door"}]
	if front_windows and size.x > 4.0:
		for at in [0.85, size.x - 0.85]:
			front.append({"at":at, "w":0.6, "y0":1.2, "y1":2.1, "kind":"window"})
	var side := []
	for at in range(1, int(size.y)):
		if at % 2 == 1:
			side.append({"at":float(at), "w":0.55, "y0":1.2, "y1":2.1, "kind":"window"})
	k.stone_wall(Vector3(x0, c.y, z1), Vector3(x1, c.y, z1), height, 0.4, "stone", front)
	k.stone_wall(Vector3(x1, c.y, z0), Vector3(x0, c.y, z0), height, 0.4, "stone", side)
	k.stone_wall(Vector3(x0, c.y, z0), Vector3(x0, c.y, z1), height, 0.4, "stone", side)
	k.stone_wall(Vector3(x1, c.y, z1), Vector3(x1, c.y, z0), height, 0.4, "stone", side)
	if hip:
		k.hip_roof(roof(L), c + Vector3(0, height + 0.1, 0), size.x, size.y, 1.25)
	else:
		k.gable_roof(roof(L), c + Vector3(0, height + 0.1, 0), size.x, size.y, 1.5, 0.32, "stone_light", "iron" if L >= 7 else "dark_oak")
	if L >= 7:
		for x in [x0 + 0.35, x1 - 0.35]:
			k.box("iron", Vector3(x, c.y + height - 0.4, z1 + 0.25), Vector3(0.6, 0.12, 0.07), 0, Color.WHITE, 0, 45)
			k.box("iron", Vector3(x, c.y + height - 0.4, z1 + 0.25), Vector3(0.6, 0.12, 0.07), 0, Color.WHITE, 0, -45)
	if L >= 9:
		for x in [x0, x1]:
			buttress(k, Vector3(x, c.y, z1 + 0.34), height * 0.78, L)
	if L >= 10:
		k.box("stone_light", Vector3(c.x, c.y + height - 0.2, z1 + 0.25), Vector3(size.x + 0.25, 0.2, 0.16))
		k.box("iron", Vector3(c.x, c.y + height - 0.48, z1 + 0.25), Vector3(size.x - 0.45, 0.07, 0.08))

static func buttress(k, c: Vector3, h: float, L: int) -> void:
	block(k, c + Vector3(0, h * 0.22, 0.1), Vector3(0.7, h * 0.44, 0.8))
	block(k, c + Vector3(0, h * 0.65, 0), Vector3(0.46, h * 0.42, 0.5))
	k.box("stone_light", c + Vector3(0, h * 0.88, 0), Vector3(0.52, 0.12, 0.56))
	if L >= 10:
		k.box("iron", c + Vector3(0, h * 0.41, 0.1), Vector3(0.73, 0.1, 0.83))

static func pavilion(k, c: Vector3, size: Vector2, h: float, L: int, arches := false) -> void:
	## Open working pavilion on stone piers. Timber belongs only to roof equipment.
	var count := maxi(2, ceili(size.x / 2.0) + 1)
	for z in [-size.y * 0.5, size.y * 0.5]:
		for i in count:
			var x: float = -size.x * 0.5 + size.x * i / (count - 1)
			k.stone_wall(c + Vector3(x - 0.18, 0, z), c + Vector3(x + 0.18, 0, z), h, 0.38, "stone_light")
		k.box("stone", c + Vector3(0, h, z), Vector3(size.x + 0.45, 0.26, 0.43))
		if arches:
			for i in count - 1:
				var x: float = -size.x * 0.5 + size.x * (i + 0.5) / (count - 1)
				k.push_at(c + Vector3(x, 0, z))
				k.arch_wall(Vector3.ZERO, size.x / (count - 1) - 0.3, 0.35, h * 0.55, size.x / (count - 1), h)
				k.pop()
	k.gable_roof(roof(L), c + Vector3(0, h + 0.2, 0), size.x, size.y, 0.95, 0.28, "", "iron" if L >= 7 else "dark_oak")
	if L >= 7:
		for x in [-size.x * 0.5, size.x * 0.5]:
			k.box("iron", c + Vector3(x, h * 0.75, size.y * 0.5), Vector3(0.44, 0.1, 0.46))

static func tower(k, c: Vector3, side: float, h: float, L: int, covered := true, civil := false) -> void:
	var r := side * 0.5
	var openings := [{"at":r, "w":0.35 if not civil else 0.65, "y0":h - 2.0, "y1":h - 0.9, "kind":"slit" if not civil else "window"}]
	for a in [0, 90, 180, 270]:
		k.push_at(c, a)
		k.stone_wall(Vector3(-r, 0, r), Vector3(r, 0, r), h, 0.45, "stone", openings)
		if not covered:
			k.crenellations(Vector3(-r, 0, r), Vector3(r, 0, r), h + 0.12, 0.45)
		if L >= 9:
			buttress(k, Vector3(-r + 0.12, 0, r + 0.22), h * 0.52, L)
		if L >= 10:
			k.box("iron", Vector3(0, h * 0.52, r + 0.26), Vector3(side + 0.1, 0.12, 0.08))
		k.pop()
	if covered:
		k.pyramid_roof(roof(L), c + Vector3(0, h + 0.12, 0), side + 0.18, 1.6, 0.27, L == 11)
	else:
		k.box("stone_light", c + Vector3(0, h - 0.05, 0), Vector3(side - 0.3, 0.16, side - 0.3))
	if L >= 7:
		for x in [-r, r]:
			k.box("iron", c + Vector3(x, h - 0.5, r + 0.25), Vector3(0.45, 0.08, 0.06))

static func annex(k, c: Vector3, size: Vector2, L: int, open := false) -> void:
	if L >= 8:
		if open:
			pavilion(k, c, size, 2.5, L, true)
		else:
			building(k, c, size, 2.7, L, 1.0, false)

static func service_gate(k, L: int, z := 4.8, width := 2.5) -> void:
	if L >= 9:
		k.arch_wall(Vector3(0, 0, z), width, 0.5, 2.2, width + 1.4, 3.9)
		for x in [-width * 0.5 - 0.55, width * 0.5 + 0.55]:
			k.box("stone_light", Vector3(x, 3.95, z), Vector3(0.8, 0.16, 0.7))
	if L >= 10:
		for x in [-width * 0.5 - 0.2, width * 0.5 + 0.2]:
			k.box("iron", Vector3(x, 1.6, z + 0.3), Vector3(0.12, 2.3, 0.08))
	if L == 11:
		k.banner(Vector3(width * 0.5 + 0.5, 3.0, z + 0.35), 0.6, 1.2, "cloth_blue")

static func civic_detail(k, c: Vector3, L: int, color := "cloth_blue") -> void:
	if L >= 7:
		k.banner(c + Vector3(-1.3, 2.6, 0), 0.6, 1.15, color)
	if L >= 10:
		k.lantern(c + Vector3(1.1, 2.3, 0.2))
	if L == 11:
		k.banner(c + Vector3(1.3, 2.6, 0), 0.6, 1.15, color)
		k.box("stone_light", c + Vector3(0, 3.1, 0), Vector3(1.1, 0.4, 0.16))
		k.box("brass", c + Vector3(0, 3.1, 0.1), Vector3(0.45, 0.28, 0.06))

static func town_hall(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -1.5), Vector2(7.0, 4.8), 4.6, L, 1.8)
	tower(k, Vector3(-3.9, 0, -2.0), 2.25, 7.2, L, true, true)
	k.paving(Vector3(-3.4, 0, 1.2), Vector3(3.4, 0, 4.9), 0.025)
	civic_detail(k, Vector3(0, 0, 1.17), L)
	annex(k, Vector3(4.25, 0, -1.7), Vector2(2.2, 4.0), L, true)
	if L >= 9:
		for x in [-2.8, 2.8]:
			block(k, Vector3(x, 0.4, 3.8), Vector3(0.8, 0.8, 0.8))
			k.flag_pole(Vector3(x, 0.8, 3.8), 3.6, "cloth_blue")
	if L >= 10:
		pavilion(k, Vector3(0, 0, 2.0), Vector2(3.4, 1.4), 3.1, L, true)
	if L == 11:
		tower(k, Vector3(3.65, 3.2, -2.1), 1.6, 3.6, L, true, true)
		k.flag_pole(Vector3(-3.9, 8.8, -2.0), 1.3, "cloth_blue")

static func house(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-2.3, 0, -1.8), Vector2(3.6, 5.2), 3.5, L)
	building(k, Vector3(2.3, 0, -2.5), Vector2(3.6, 3.8), 3.1, L)
	for x in [-2.3, 2.3]:
		k.chimney(Vector3(x - 0.7, 3.3, -3.1), 2.4, 0.5)
		k.bench(Vector3(x, 0, 2.5), 1.7)
	k.table(Vector3(2.5, 0, 2.6), 1.5, 1.1)
	annex(k, Vector3(2.5, 0, 1.0), Vector2(3.4, 2.4), L)
	if L >= 9:
		service_gate(k, L, 4.8, 1.9)
	if L >= 10:
		k.garden_bed(Vector3(-5.0, 0, 2.1), Vector3(-3.6, 0, 4.6), "leaves", 3)
	if L == 11:
		building(k, Vector3(-2.3, 3.5, -2.8), Vector2(2.8, 2.3), 2.5, L, 0.8, false)
		k.box("cloth_teal", Vector3(2.3, 2.0, 2.46), Vector3(1.0, 0.28, 0.04))

static func warehouse(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -2.4), Vector2(7.8, 4.5), 4.0, L, 2.4)
	pavilion(k, Vector3(-3.9, 0, 1.9), Vector2(2.5, 2.8), 2.9, L)
	for z in [-0.2, 1.0, 2.2]:
		k.crate(Vector3(-4.2, 0, z), 0.8)
	k.cart(Vector3(3.7, 0, 2.7), -10, "crates")
	annex(k, Vector3(4.6, 0, -2.2), Vector2(1.8, 4.0), L)
	if L >= 9:
		service_gate(k, L)
		k.crane(Vector3(-2.8, 0, 3.6), 3.0, Vector3(1.7, 0.4, 0), 1.6)
	if L >= 10:
		for x in [-2.5, 2.5]:
			k.plank_stack(Vector3(x, 0, -5.1), 1.8, 0.65, 6)
	if L == 11:
		tower(k, Vector3(-3.4, 2.4, -3.4), 1.8, 3.2, L, true, true)

static func granary(k, L: int) -> void:
	yard(k, L)
	# Raised stone grain cells with open ventilation below; distinct from warehouse.
	for x in [-2.6, 2.6]:
		for z in [-3.8, -1.4]:
			block(k, Vector3(x, 0.45, z), Vector3(1.3, 0.9, 1.0))
		building(k, Vector3(x, 0.8, -2.6), Vector2(3.2, 4.0), 3.4, L, 1.1, false, true)
		k.ramp(Vector3(x, 0, 2.6), Vector3(x, 0.8, -0.5), 1.2, "stone_light", true, false)
		for z in [0.5, 1.3]:
			k.sack(Vector3(x + 1.0, 0, z))
	# The connection is forward of the bins so VIII reads from the city camera.
	annex(k, Vector3(0, 0, -0.2), Vector2(1.7, 2.4), L, true)
	if L >= 9:
		pavilion(k, Vector3(0, 0, 3.8), Vector2(3.0, 1.7), 2.6, L, true)
	if L >= 10:
		for x in [-4.6, 4.6]:
			k.barrel(Vector3(x, 0, -0.6))
	if L == 11:
		for x in [-2.6, 2.6]:
			pavilion(k, Vector3(x, 4.4, -2.6), Vector2(1.1, 1.6), 0.9, L)

static func market(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -3.8), Vector2(6.0, 2.8), 3.0, L, 1.5)
	for x in [-3.9, 3.9]:
		k.push_at(Vector3(x, 0, 0), 90)
		pavilion(k, Vector3.ZERO, Vector2(5.6, 2.0), 2.6, L, L >= 8)
		for dx in [-1.7, 0.0, 1.7]:
			k.table(Vector3(dx, 0, 0), 1.4, 0.8)
			k.crate(Vector3(dx, 0.83, 0), 0.35)
		k.pop()
	k.table(Vector3(0, 0, -1.3), 1.4, 0.8)
	# The weighbridge is equipment, never another gameplay currency or object.
	k.beam("iron", Vector3(0, 0.8, -1.3), Vector3(0, 1.7, -1.3), 0.08)
	k.beam("brass", Vector3(-0.6, 1.65, -1.3), Vector3(0.6, 1.65, -1.3), 0.06)
	for x in [-0.5, 0.5]:
		k.cyl("brass", Vector3(x, 1.2, -1.3), Vector3(x, 1.25, -1.3), 0.25, 10)
	if L >= 8:
		pavilion(k, Vector3(0, 0, 3.5), Vector2(5.5, 1.4), 2.9, L, true)
	if L >= 9:
		k.cart(Vector3(-4.6, 0, 4.5), 90, "crates")
	if L >= 10:
		civic_detail(k, Vector3(0, 0, -2.2), L, "cloth_wine")
	if L == 11:
		tower(k, Vector3(0, 3.0, -3.8), 1.9, 2.8, L, true, true)

static func lumber(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-2.4, 0, -2.6), Vector2(4.4, 4.0), 2.9, L)
	pavilion(k, Vector3(3.4, 0, -2.3), Vector2(3.4, 4.2), 2.8, L)
	for z in [0.7, 2.2, 3.7]:
		k.log_pile(Vector3(-3.6, 0, z), 2.3, 3, 0.2)
	k.workbench(Vector3(3.4, 0, 2.5), 2.0)
	k.sawhorse(Vector3(2.3, 0, 3.8))
	annex(k, Vector3(3.6, 0, 0.8), Vector2(2.8, 1.8), L, true)
	if L >= 9:
		k.crane(Vector3(-1.5, 0, 1.2), 3.6, Vector3(-2.5, 0.4, 0), 2.0)
	if L >= 10:
		k.cart(Vector3(3.7, 0, 4.5), 90, "logs")
	if L == 11:
		building(k, Vector3(-2.6, 3.0, -3.1), Vector2(2.7, 2.0), 2.3, L, 0.8, false)
		k.weapon_rack(Vector3(4.6, 0, 0.4), 1.4, 90)

static func quarry(k, L: int) -> void:
	yard(k, L)
	# Rock terraces remain natural quarry faces, not additional functional buildings.
	for i in 4:
		block(k, Vector3(-2.7, 0.32 + i * 0.31, -4.4 + i * 0.7), Vector3(5.8 - i * 0.55, 0.7 + i * 0.6, 1.6), i * 2.0, true)
	building(k, Vector3(3.5, 0, -3.0), Vector2(3.0, 3.0), 2.7, L)
	pavilion(k, Vector3(-2.5, 0, 0.6), Vector2(4.5, 2.5), 3.7, L)
	k.crane(Vector3(-2.6, 0, -0.3), 4.8, Vector3(1.8, 0.1, 1.0), 2.8)
	for x in [-4.0, -2.6, 2.8, 4.0]:
		block(k, Vector3(x, 0.4, 3.5), Vector3(0.9, 0.8, 0.8), x * 3)
	annex(k, Vector3(3.3, 0, 0.8), Vector2(2.7, 2.0), L, true)
	if L >= 9:
		service_gate(k, L, 4.6, 2.6)
	if L >= 10:
		k.crane(Vector3(3.9, 0, 1.4), 3.5, Vector3(-1.5, 0.2, 0), 2.0)
	if L == 11:
		tower(k, Vector3(3.5, 2.7, -3), 1.7, 2.8, L, true, true)

static func mine(k, L: int) -> void:
	yard(k, L)
	for x in [-3.8, 3.8]:
		rock_outcrop(k, Vector3(x, 0, -3.3), Vector3(3.5, 3.6, 4.5))
	k.arch_wall(Vector3(0, 0, -1.8), 2.6, 1.2, 2.4, 5.3, 4.4)
	k.box("soot", Vector3(0, 1.4, -3), Vector3(2.8, 2.8, 0.1))
	tower(k, Vector3(3.8, 2.7, -3.7), 1.7, 3.3, L, true)
	for x in [-0.65, 0.65]:
		k.beam("iron", Vector3(x, 0.07, -2.9), Vector3(x, 0.07, 3.7), 0.06, 0.07)
	for z in range(-2, 4):
		k.box("dark_oak", Vector3(0, 0.035, z), Vector3(1.7, 0.07, 0.17))
	k.cart(Vector3(0, 0.12, 1.7), 0, "stone")
	annex(k, Vector3(-4, 0, 1.4), Vector2(2.5, 3.2), L)
	if L >= 9:
		pavilion(k, Vector3(3.8, 0, 2.3), Vector2(2.2, 3.5), 3.0, L, true)
	if L >= 10:
		for x in [-2.1, 2.1]:
			buttress(k, Vector3(x, 0, -1.0), 3.5, L)
	if L == 11:
		k.pyramid_roof(roof(L), Vector3(0, 4.5, -1.8), 3.2, 1.3, 0.15)
		k.wheel(Vector3(3.8, 5.4, -2.6), 0.75, Vector3.FORWARD, "iron")

static func crop_rows(k, a: Vector3, b: Vector3, wheat_crop := false) -> void:
	k.garden_bed(a, b, "hay" if wheat_crop else "leaves", 4, false)
	if wheat_crop:
		var nx := maxi(2, int((b.x - a.x) / 0.28))
		var nz := maxi(2, int((b.z - a.z) / 0.38))
		for ix in nx:
			for iz in nz:
				var p := Vector3(lerpf(a.x + 0.15, b.x - 0.15, float(ix) / (nx - 1)), 0.05, lerpf(a.z + 0.1, b.z - 0.1, float(iz) / (nz - 1)))
				var h: float = 0.6 + k.rng.randf_range(-0.1, 0.15)
				k.beam("hay", p, p + Vector3(0.04, h, 0), 0.025)
				k.cyl("hay", p + Vector3(0.04, h, 0), p + Vector3(0.04, h + 0.17, 0), 0.045, 5)

static func farm(k, L: int) -> void:
	yard(k, L, true)
	building(k, Vector3(-3.1, 0, -3), Vector2(4.0, 3.2), 2.8, L)
	for x in [-4.8, 1.5]:
		crop_rows(k, Vector3(x, 0, -0.7), Vector3(x + 2.8, 0, 3.6), x > 0)
	k.fence(Vector3(-5.7, 0, 4.4), Vector3(-1.6, 0, 4.4), 0.7)
	k.fence(Vector3(1.4, 0, 4.4), Vector3(5.5, 0, 4.4), 0.7)
	annex(k, Vector3(3.5, 0, -3.1), Vector2(3.2, 2.8), L, true)
	if L >= 9:
		channel(k, Vector3(-0.85, 0, -4.8), Vector3(-0.85, 0, 4.1))
		k.cart(Vector3(0.6, 0, -2.6), 0, "sacks")
	if L >= 10:
		k.stone_wall(Vector3(-5.5, 0, -5.0), Vector3(5.5, 0, -5.0), 1.0, 0.3)
	if L == 11:
		pavilion(k, Vector3(-3.1, 2.9, -3), Vector2(1.4, 1.6), 1.0, L)
		k.sack(Vector3(4.5, 0, -2.2))

static func drying_rack(k, c: Vector3, fishing_net := false) -> void:
	for x in [-0.9, 0.9]:
		k.beam("dark_oak", c + Vector3(x, 0, 0), c + Vector3(x, 2.3, 0), 0.14)
	k.beam("oak", c + Vector3(-1, 2.2, 0), c + Vector3(1, 2.2, 0), 0.12)
	for i in 8:
		var x := -0.8 + i * 0.23
		k.beam("rope", c + Vector3(x, 2.1, 0), c + Vector3(x, 0.8, 0), 0.018)
	if fishing_net:
		for i in 7:
			k.beam("rope", c + Vector3(-0.8, 0.8 + i * 0.2, 0), c + Vector3(0.8, 0.8 + i * 0.2, 0), 0.018)
	else:
		for x in [-0.5, 0, 0.5]:
			k.box("canvas", c + Vector3(x, 1.45, 0), Vector3(0.38, 0.8, 0.06), x * 10)

static func hunting_camp(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-2.8, 0, -2.8), Vector2(4.2, 3.7), 2.7, L)
	pavilion(k, Vector3(3.1, 0, -2.1), Vector2(3.5, 4.2), 2.8, L)
	drying_rack(k, Vector3(3.1, 0, -1.2))
	drying_rack(k, Vector3(-3.3, 0, 2.0))
	k.workbench(Vector3(3.3, 0, 2.6), 2.0)
	k.barrel(Vector3(4.7, 0, 3.4))
	annex(k, Vector3(-3.0, 0, 0.2), Vector2(3.5, 1.8), L, true)
	if L >= 9:
		service_gate(k, L, 4.8, 2.0)
	if L >= 10:
		k.stone_wall(Vector3(-5.4, 0, -4.9), Vector3(5.4, 0, -4.9), 1.4, 0.3)
		k.cart(Vector3(3.6, 0, 4.2), 90)
	if L == 11:
		tower(k, Vector3(-3.2, 2.7, -3.2), 1.5, 2.6, L, true, true)

static func barracks(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -3.7), Vector2(8.5, 2.8), 3.4, L, 1.7)
	building(k, Vector3(-4.1, 0, -0.5), Vector2(2.6, 3.0), 2.8, L)
	k.ground(Vector3(-2.0, 0, -1.3), Vector3(4.4, 0, 3.9), "drill", 0.03)
	for x in [-1.3, 0.5, 2.3]:
		k.dummy(Vector3(x, 0, 0.0))
	k.weapon_rack(Vector3(-3.7, 0, 2.4), 2.0)
	civic_detail(k, Vector3(0, 0, -2.1), L, "cloth_red")
	annex(k, Vector3(4.2, 0, -0.4), Vector2(2.4, 3.0), L)
	if L >= 9:
		service_gate(k, L, 4.8)
	if L >= 10:
		k.palisade(Vector3(-5.5, 0, 1.4), Vector3(-5.5, 0, 4.4), 1.4, 0.09)
	if L == 11:
		tower(k, Vector3(-4.0, 2.8, -3.8), 1.9, 3.2, L, false)

static func target(k, c: Vector3) -> void:
	k.beam("oak", c, c + Vector3(0, 1.5, 0), 0.1)
	for r in [0.55, 0.38, 0.17]:
		k.cyl("cloth_red" if r == 0.38 else "linen", c + Vector3(0, 1.55, 0.08 - r * 0.03), c + Vector3(0, 1.55, 0.16 - r * 0.03), r, 20)

static func archery(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-4.1, 0, -2.4), Vector2(2.5, 4.7), 2.8, L)
	k.stone_wall(Vector3(-2.2, 0, -4.7), Vector3(4.9, 0, -4.7), 2.9, 0.45)
	for x in [-1.2, 1.1, 3.4]:
		target(k, Vector3(x, 0, -3.9))
		k.ground(Vector3(x - 0.65, 0, -3.1), Vector3(x + 0.65, 0, 2.1), "drill", 0.03)
	pavilion(k, Vector3(1.1, 0, 2.6), Vector2(6.6, 1.8), 2.8, L)
	annex(k, Vector3(-4.2, 0, 1.9), Vector2(2.2, 2.8), L)
	if L >= 9:
		for x in [-2.2, 4.9]:
			buttress(k, Vector3(x, 0, -4.4), 2.6, L)
	if L >= 10:
		k.weapon_rack(Vector3(-4.1, 0, 4.2), 2.0)
		k.stone_wall(Vector3(5.2, 0, -4.7), Vector3(5.2, 0, 3.4), 1.25, 0.3)
	if L == 11:
		tower(k, Vector3(-4.1, 2.8, -3.4), 1.6, 2.8, L, true)
		k.banner(Vector3(3.5, 2.6, 3.7), 0.6, 1.1, "cloth_red")

static func stables(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -3.4), Vector2(8.5, 3.2), 3.1, L, 2.2)
	for x in [-3.0, -1.5, 1.5, 3.0]:
		k.door(Vector3(x, 0, -1.56), 0.9, 1.7, 0)
		k.box("hay", Vector3(x, 0.5, -1.25), Vector3(0.7, 0.5, 0.35))
	for x in [-4.4, 4.4]:
		k.fence(Vector3(x, 0, -0.8), Vector3(x, 0, 4.1), 1.2)
		k.fence(Vector3(x, 0, 4.1), Vector3(signf(x) * 1.5, 0, 4.1), 1.2)
	k.ground(Vector3(-3.8, 0, -0.7), Vector3(3.8, 0, 3.7), "drill", 0.026)
	annex(k, Vector3(-4.7, 0, 0.7), Vector2(1.6, 2.5), L, true)
	if L >= 9:
		service_gate(k, L, 4.7, 2.7)
	if L >= 10:
		pavilion(k, Vector3(4.7, 0, 0.7), Vector2(1.6, 2.5), 2.5, L, true)
		k.barrel(Vector3(3.6, 0, 2.4))
	if L == 11:
		pavilion(k, Vector3(0, 4.0, -3.4), Vector2(1.8, 1.5), 1.2, L)

static func smith(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-2, 0, -2.8), Vector2(5.8, 3.7), 3.0, L, 1.8)
	pavilion(k, Vector3(3.4, 0, -1.7), Vector2(3.1, 3.8), 3.1, L)
	k.forge(Vector3(3.1, 0, -2.6), 1.6, 1.3)
	k.chimney(Vector3(-3.6, 0, -3.4), 6.2, 0.95)
	k.anvil(Vector3(3.1, 0, 0.5), 15)
	k.weapon_rack(Vector3(-3.3, 0, 1.4), 2.2)
	k.workbench(Vector3(-3.1, 0, 3.5), 2.5)
	annex(k, Vector3(3.5, 0, 2.4), Vector2(3.0, 2.4), L, true)
	if L >= 9:
		service_gate(k, L, 4.9, 2.0)
	if L >= 10:
		k.forge(Vector3(3.5, 0, 2.7), 1.3, 1.0)
		k.box("iron", Vector3(-3.6, 4.7, -3.4), Vector3(1.0, 0.15, 1.0))
	if L == 11:
		k.chimney(Vector3(-1.6, 1.8, -3.5), 5.0, 0.7)
		k.anvil(Vector3(-1.3, 0, 2.9), -10, 0.8)

static func academy(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -2.9), Vector2(7.8, 3.6), 4.2, L, 1.7, true, true)
	building(k, Vector3(-4, 0, 0.1), Vector2(2.7, 2.5), 3.3, L)
	k.map_table(Vector3(2.7, 0, 1.8), 2.4, 1.6)
	civic_detail(k, Vector3(0, 0, -0.9), L)
	annex(k, Vector3(4.0, 0, 0.1), Vector2(2.7, 2.5), L)
	if L >= 9:
		pavilion(k, Vector3(0, 0, 2.6), Vector2(3.4, 1.8), 3.0, L, true)
	if L >= 10:
		for x in [-4, 4]:
			k.bench(Vector3(x, 0, 3.0), 1.8)
	if L == 11:
		tower(k, Vector3(0, 3.6, -3.0), 2.2, 3.1, L, true, true)

static func infirmary(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-3, 0, -1.7), Vector2(3.5, 5.8), 3.1, L, 1.5)
	building(k, Vector3(2.9, 0, -2.8), Vector2(3.7, 3.6), 3.1, L, 1.5)
	k.stretcher(Vector3(2.8, 0, 1.6))
	k.bed(Vector3(3.8, 0, 3.5), 90)
	k.garden_bed(Vector3(-4.6, 0, 2.3), Vector3(-2, 0, 4.1), "herb", 3)
	annex(k, Vector3(2.9, 0, 0.6), Vector2(3.6, 2.4), L, true)
	if L >= 9:
		pavilion(k, Vector3(0, 0, -3.1), Vector2(1.9, 2.5), 2.9, L, true)
	if L >= 10:
		service_gate(k, L, 4.8, 2.3)
	if L == 11:
		pavilion(k, Vector3(-3, 3.3, -2.1), Vector2(1.5, 2.0), 1.1, L)
		k.banner(Vector3(1.5, 2.6, 4.9), 0.55, 1.05, "linen")

static func ram_display(k, c: Vector3) -> void:
	## Workshop equipment only. Its visible presence grants no free army unit.
	for x in [-0.85, 0.85]:
		for z in [-1.0, 1.0]:
			k.wheel(c + Vector3(x, 0.45, z), 0.43)
		k.beam("oak", c + Vector3(x, 0.55, -1.3), c + Vector3(x, 0.55, 1.3), 0.18)
		for z in [-0.9, 0.9]:
			k.beam("dark_oak", c + Vector3(x, 0.6, z), c + Vector3(0, 2.2, z), 0.2)
	k.cyl("log", c + Vector3(0, 1.1, -1.6), c + Vector3(0, 1.1, 1.8), 0.23, 10)
	k.box("iron", c + Vector3(0, 1.1, 1.8), Vector3(0.5, 0.5, 0.3))
	k.gable_roof("shingle", c + Vector3(0, 2.25, 0), 1.8, 2.7, 0.6, 0.1)

static func siege(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-3.5, 0, -3.2), Vector2(3.1, 3.6), 3.3, L)
	pavilion(k, Vector3(1.4, 0, -2.1), Vector2(5.8, 5.0), 4.1, L)
	ram_display(k, Vector3(1.4, 0, -1.4))
	k.crane(Vector3(3.8, 0, -2.6), 3.7, Vector3(-2.8, 0.0, 0), 1.5)
	for z in [1.3, 2.4, 3.5]:
		k.wheel(Vector3(-4, 0.65, z), 0.65)
	annex(k, Vector3(-3.6, 0, 1.2), Vector2(2.9, 2.3), L, true)
	if L >= 9:
		service_gate(k, L, 4.9, 3.2)
	if L >= 10:
		k.plank_stack(Vector3(4.1, 0, 3.0), 2.4, 0.9, 7, 90)
		k.anvil(Vector3(-3.5, 0, 1.4), 0, 0.8)
	if L == 11:
		pavilion(k, Vector3(1.4, 5.4, -2.1), Vector2(1.7, 2.5), 1.0, L)

static func gate(k, L: int) -> void:
	yard(k, L)
	# Central carriageway stays open; towers are one visual part of one wall node.
	k.arch_wall(Vector3(0, 0, 0), 3.4, 1.6, 3.3, 6.8, 5.6)
	for x in [-4.1, 4.1]:
		tower(k, Vector3(x, 0, 0), 2.5, 6.0, L, L >= 7)
		k.stone_wall(Vector3(signf(x) * 5.3, 0, -0.1), Vector3(signf(x) * 6.0, 0, -0.1), 3.8, 1.0)
		k.crenellations(Vector3(signf(x) * 5.3, 0, -0.1), Vector3(signf(x) * 6.0, 0, -0.1), 3.9, 0.8)
	k.crenellations(Vector3(-2.8, 0, 0.8), Vector3(2.8, 0, 0.8), 5.7, 0.5)
	k.lane(Vector3(0, 0, 5.7), Vector3(0, 0, -5.6), 2.7, 3.1, "cart")
	if L >= 8:
		for x in [-4.1, 4.1]:
			k.stone_wall(Vector3(x, 0, -1.4), Vector3(x, 0, -3.8), 3.8, 0.7)
			k.crenellations(Vector3(x, 0, -1.4), Vector3(x, 0, -3.8), 3.9, 0.65)
	if L >= 9:
		for x in [-2.7, 2.7]:
			buttress(k, Vector3(x, 0, 1.1), 4.4, L)
	if L >= 10:
		for x in [-1.8, 1.8]:
			k.box("iron", Vector3(x, 1.8, 0.91), Vector3(0.12, 3.6, 0.15))
		k.box("iron", Vector3(0, 4.9, 0.91), Vector3(3.8, 0.18, 0.14))
	if L == 11:
		tower(k, Vector3(0, 5.6, 0), 2.0, 2.3, L, true)
		for x in [-4.1, 4.1]:
			k.banner(Vector3(x, 4.7, 1.6), 0.8, 1.5, "cloth_red")

static func watchtower(k, L: int) -> void:
	yard(k, L)
	tower(k, Vector3(0, 0, -0.9), 3.1, 7.1, L, true)
	building(k, Vector3(-3.6, 0, -2.9), Vector2(2.7, 3.0), 2.6, L)
	k.stairs(Vector3(0, 0, 2.9), 1.3, 9, 0.15, 0.28, 0, "stone")
	annex(k, Vector3(3.7, 0, -2.7), Vector2(2.6, 3.0), L)
	if L >= 9:
		k.stone_wall(Vector3(-4.8, 0, 2.7), Vector3(-1.5, 0, 2.7), 1.6, 0.45)
		k.stone_wall(Vector3(1.5, 0, 2.7), Vector3(4.8, 0, 2.7), 1.6, 0.45)
	if L >= 10:
		k.flag_pole(Vector3(3.7, 3.0, -2.7), 3.5, "cloth_red")
	if L == 11:
		pavilion(k, Vector3(0, 8.0, -0.9), Vector2(1.6, 1.6), 1.4, L)
		k.cyl("brass", Vector3(0, 8.6, -0.9), Vector3(0.2, 8.5, 0.0), 0.12, 10)

static func channel(k, a: Vector3, b: Vector3) -> void:
	var d := (b - a).normalized()
	var side := Vector3(d.z, 0, -d.x) * 0.24
	k.beam("water", a + Vector3(0, 0.05, 0), b + Vector3(0, 0.05, 0), 0.33, 0.04)
	for s in [-1, 1]:
		k.beam("stone_light", a + side * s + Vector3(0, 0.12, 0), b + side * s + Vector3(0, 0.12, 0), 0.16, 0.24)

static func well(k, L: int) -> void:
	yard(k, L)
	# Hollow ring leaves visible water; functional windlass stays timber.
	for i in 16:
		var a := TAU * i / 16.0
		block(k, Vector3(cos(a) * 1.2, 0.6, sin(a) * 1.2), Vector3(0.48, 1.2, 0.5), -rad_to_deg(a))
	k.cyl("water", Vector3(0, 0.2, 0), Vector3(0, 0.22, 0), 1.1, 24)
	pavilion(k, Vector3.ZERO, Vector2(3.5, 3.1), 3.0, L)
	k.cyl("oak", Vector3(-1.8, 2.2, 0), Vector3(1.8, 2.2, 0), 0.12, 12)
	k.wheel(Vector3(2.0, 2.2, 0), 0.5)
	k.beam("rope", Vector3(0, 2.2, 0), Vector3(0, 0.8, 0), 0.035)
	channel(k, Vector3(-1.6, 0, 0), Vector3(-5.1, 0, 0))
	channel(k, Vector3(1.6, 0, 0), Vector3(5.1, 0, 0))
	annex(k, Vector3(-3.6, 0, -3.1), Vector2(2.8, 2.5), L)
	if L >= 9:
		channel(k, Vector3(4.7, 0, -3.8), Vector3(4.7, 0, 4.4))
		for x in [-3.0, 3.0]:
			k.barrel(Vector3(x, 0, 2.6))
	if L >= 10:
		pavilion(k, Vector3(3.4, 0, -3.1), Vector2(2.6, 2.3), 2.7, L, true)
	if L == 11:
		k.pyramid_roof(roof(L), Vector3(0, 4.0, 0), 1.3, 1.0, 0.14)
		k.box("brass", Vector3(0, 2.5, 1.8), Vector3(0.5, 0.4, 0.08))

static func sawmill(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-3.5, 0, -3.1), Vector2(3.2, 3.2), 3.0, L)
	pavilion(k, Vector3(1.6, 0, -1.7), Vector2(5.0, 5.4), 3.7, L)
	for z in [-3.3, -1.3]:
		k.workbench(Vector3(1.6, 0, z), 3.7, 90)
		k.cyl("iron", Vector3(1.6, 1.3, z - 0.05), Vector3(1.6, 1.3, z + 0.05), 0.65, 24)
	k.log_pile(Vector3(-3.4, 0, 1.1), 3.0, 3, 0.22, 90)
	k.plank_stack(Vector3(3.6, 0, 3.5), 3.0, 1.2, 7)
	annex(k, Vector3(-3.6, 0, 1.1), Vector2(2.5, 3.2), L, true)
	if L >= 9:
		k.crane(Vector3(1.5, 0, 3.1), 3.4, Vector3(-2.5, 0.3, 0), 2.1)
	if L >= 10:
		k.cart(Vector3(-3.7, 0, 4.0), 90, "logs")
	if L == 11:
		pavilion(k, Vector3(1.6, 4.6, -1.7), Vector2(1.7, 2.6), 1.2, L)
		k.wheel(Vector3(4.4, 1.2, -1.7), 0.9, Vector3.RIGHT, "iron")

static func wheat(k, L: int) -> void:
	yard(k, L, true)
	building(k, Vector3(-3.4, 0, -3.4), Vector2(3.6, 2.7), 2.9, L)
	crop_rows(k, Vector3(0.6, 0, -4.3), Vector3(5.1, 0, 3.8), true)
	crop_rows(k, Vector3(-5.1, 0, -0.9), Vector3(-1.3, 0, 3.8), true)
	k.table(Vector3(-2.9, 0, -0.7), 2.1, 0.7)
	for x in [-4.4, -2.6]:
		k.sack(Vector3(x, 0, -1.8))
	annex(k, Vector3(-3.2, 0, -0.7), Vector2(3.2, 1.6), L, true)
	if L >= 9:
		channel(k, Vector3(-0.7, 0, -4.6), Vector3(-0.7, 0, 4.2))
		k.stone_wall(Vector3(-5.4, 0, -5.0), Vector3(5.4, 0, -5.0), 0.8, 0.3)
	if L >= 10:
		k.cart(Vector3(-3.4, 0, 4.6), 90, "sacks")
	if L == 11:
		pavilion(k, Vector3(-3.4, 3.7, -3.4), Vector2(1.4, 1.4), 1.1, L)
		k.sack(Vector3(-4.8, 0, -1.8))

static func lodge(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -2.5), Vector2(6.0, 4.2), 3.5, L, 1.5)
	k.chimney(Vector3(-2.2, 2.0, -3.3), 4.1, 0.7)
	pavilion(k, Vector3(-4, 0, 1.3), Vector2(2.4, 3.2), 2.6, L)
	k.map_table(Vector3(-4, 0, 1.3), 1.7, 1.2)
	k.workbench(Vector3(3.8, 0, 1.5), 2.0, 90)
	annex(k, Vector3(4, 0, 1.0), Vector2(2.3, 3.1), L)
	if L >= 9:
		service_gate(k, L, 4.7, 2.0)
	if L >= 10:
		drying_rack(k, Vector3(-3.8, 0, 3.8))
		k.stone_wall(Vector3(-5.5, 0, -5.0), Vector3(5.5, 0, -5.0), 1.3, 0.35)
	if L == 11:
		tower(k, Vector3(2.2, 2.8, -3.1), 1.9, 3.1, L, true, true)
		k.banner(Vector3(0, 3.0, -0.1), 0.7, 1.1, "cloth_teal")

static func boat(k, c: Vector3) -> void:
	k.push_at(c)
	k.box("plank", Vector3(0, 0.1, 0), Vector3(1.0, 0.15, 2.8))
	for s in [-1, 1]:
		k.beam("oak", Vector3(s * 0.65, 0.4, -0.9), Vector3(s * 0.65, 0.4, 0.9), 0.14, 0.5)
		k.beam("oak", Vector3(s * 0.65, 0.4, 0.9), Vector3(0, 0.5, 1.7), 0.14, 0.5)
		k.beam("oak", Vector3(s * 0.65, 0.4, -0.9), Vector3(0, 0.5, -1.7), 0.14, 0.5)
	for z in [-0.65, 0.65]:
		k.box("plank", Vector3(0, 0.48, z), Vector3(1.25, 0.12, 0.38))
	k.beam("oak_light", Vector3(-0.8, 0.7, -0.5), Vector3(0.6, 0.6, 1.1), 0.07)
	k.pop()

static func fishing(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-2.5, 0, -2.8), Vector2(4.5, 3.8), 2.9, L)
	# Piled timber dock and nets are functional equipment, compatible with VI stone rule.
	k.deck(Vector3(1.2, 0, -4.6), Vector3(4.5, 0, 3.5), 0.4, "plank", true, true, true, "dark_oak")
	k.railing(Vector3(4.5, 0.4, -4.6), Vector3(4.5, 0.4, 1.0), 0.85)
	drying_rack(k, Vector3(-3.5, 0, 1.7), true)
	k.barrel(Vector3(2.6, 0.4, 2.5))
	boat(k, Vector3(5.4, 0.0, 1.3))
	annex(k, Vector3(-2.8, 0, 0.5), Vector2(3.6, 2.0), L, true)
	if L >= 9:
		k.crane(Vector3(2.7, 0.4, -2.9), 3.0, Vector3(1.5, 0.3, 0), 2.2)
		k.ramp(Vector3(0, 0, 4.2), Vector3(2.4, 0.4, 3.2), 1.1, "plank")
	if L >= 10:
		k.stone_wall(Vector3(0.7, 0, -4.7), Vector3(0.7, 0, 2.7), 0.5, 0.4)
		k.workbench(Vector3(-3.6, 0, 3.6), 2.0)
	if L == 11:
		tower(k, Vector3(-3.7, 2.8, -3.4), 1.6, 2.8, L, true, true)
		k.flag_pole(Vector3(4.3, 0.4, -4.2), 2.7, "cloth_teal")

static func herbal(k, L: int) -> void:
	yard(k, L, true)
	building(k, Vector3(0, 0, -3.5), Vector2(5.8, 2.8), 2.7, L, 1.2)
	for x in [-4.6, 1.4]:
		for z in [-0.8, 1.3]:
			k.garden_bed(Vector3(x, 0, z), Vector3(x + 3.0, 0, z + 1.6), "lavender" if z > 0 else "herb", 4)
	for x in [-5.3, 5.3]:
		k.stone_wall(Vector3(x, 0, -4.8), Vector3(x, 0, 3.7), 0.9, 0.3)
	k.workbench(Vector3(-3.8, 0, 4.3), 2.0)
	annex(k, Vector3(4.0, 0, -3.4), Vector2(2.1, 2.8), L, true)
	if L >= 9:
		service_gate(k, L, 4.8, 1.7)
		channel(k, Vector3(-0.8, 0, -1.9), Vector3(-0.8, 0, 3.5))
	if L >= 10:
		pavilion(k, Vector3(-4.0, 0, -3.4), Vector2(2.0, 2.8), 2.4, L, true)
	if L == 11:
		pavilion(k, Vector3(0, 3.1, -3.5), Vector2(1.8, 1.2), 1.0, L)
		k.barrel(Vector3(3.9, 0, 4.2), 0.6, 0.25)

static func stonework(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(-3.4, 0, -3.1), Vector2(3.4, 3.3), 3.0, L)
	pavilion(k, Vector3(1.7, 0, -2.0), Vector2(5.0, 4.6), 3.6, L)
	for x in [0.0, 2.8]:
		k.workbench(Vector3(x, 0, -1.9), 2.0)
		block(k, Vector3(x, 1.2, -1.9), Vector3(1.1, 0.6, 0.7))
	k.crane(Vector3(4.3, 0, -2.6), 3.9, Vector3(-2.0, 0.2, 0), 2.6)
	for x in [-4, -2.7, 2.7, 4]:
		block(k, Vector3(x, 0.4, 2.8), Vector3(0.9, 0.8, 1.1), x * 2)
	annex(k, Vector3(-3.5, 0, 0.7), Vector2(2.8, 2.1), L, true)
	if L >= 9:
		service_gate(k, L, 4.8, 2.6)
	if L >= 10:
		k.workbench(Vector3(-3.4, 0, 0.6), 2.0)
		k.cyl("stone_light", Vector3(4.4, 0, 0.4), Vector3(4.4, 2.4, 0.4), 0.28, 12)
	if L == 11:
		pavilion(k, Vector3(1.7, 4.5, -2), Vector2(2.0, 2.2), 1.1, L)
		k.arch_wall(Vector3(-3.5, 0, 3.7), 0.9, 0.3, 1.2, 1.6, 2.3)

static func smelter(k, L: int) -> void:
	yard(k, L)
	building(k, Vector3(0, 0, -3.0), Vector2(7.6, 3.6), 3.5, L, 2.2)
	for x in [-2.3, 2.3]:
		k.forge(Vector3(x, 0, -0.8), 2.0, 1.8)
		k.chimney(Vector3(x, 1.5, -2.9), 5.3, 1.1)
		k.box("iron", Vector3(x, 5.2, -2.9), Vector3(1.2, 0.16, 1.2))
		k.box("stone", Vector3(x, 0.15, 1.6), Vector3(0.6, 0.3, 2.6))
		k.box("soot", Vector3(x, 0.31, 1.6), Vector3(0.32, 0.04, 2.4))
	k.cart(Vector3(-3.9, 0, 3.5), 90, "stone")
	annex(k, Vector3(4.5, 0, 1.4), Vector2(1.8, 3.2), L, true)
	if L >= 9:
		pavilion(k, Vector3(-4.5, 0, 0.3), Vector2(1.8, 2.5), 3.0, L, true)
	if L >= 10:
		service_gate(k, L, 4.9, 2.4)
	if L == 11:
		k.chimney(Vector3(0, 1.0, -3.5), 7.5, 1.3)
		k.box("iron", Vector3(0, 6.8, -3.5), Vector3(1.4, 0.18, 1.4))
