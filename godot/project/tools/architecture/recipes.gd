extends RefCounted
## Level recipes for the 40 positions listed in DRENOVAR CHANGES.md (20 series) and the
## 19 levels reworked after the 0.6.0 test 5 QA (VIS-01..03, build 53).
## Every function returns a spec; geometry goes into the kit (k).
## Main entrance faces +Z on every level; footprint stays inside the 14 x 14 m plot.

const ENTRIES := [
	{"series": "B03_Warehouse", "type": "ECO-01", "level": 1, "fn": "b03_warehouse"},
	{"series": "B03_Warehouse", "type": "ECO-01", "level": 2, "fn": "b03_warehouse"},
	{"series": "B03_Warehouse", "type": "ECO-01", "level": 3, "fn": "b03_warehouse"},
	{"series": "B03_Warehouse", "type": "ECO-01", "level": 4, "fn": "b03_warehouse"},
	{"series": "B03_Warehouse", "type": "ECO-01", "level": 5, "fn": "b03_warehouse"},
	{"series": "B04_Granary", "type": "ECO-02", "level": 1, "fn": "b04_granary"},
	{"series": "B04_Granary", "type": "ECO-02", "level": 2, "fn": "b04_granary"},
	{"series": "B04_Granary", "type": "ECO-02", "level": 3, "fn": "b04_granary"},
	{"series": "B04_Granary", "type": "ECO-02", "level": 4, "fn": "b04_granary"},
	{"series": "B04_Granary", "type": "ECO-02", "level": 5, "fn": "b04_granary"},
	{"series": "B05_Marketplace", "type": "ECO-03", "level": 1, "fn": "b05_market"},
	{"series": "B05_Marketplace", "type": "ECO-03", "level": 2, "fn": "b05_market"},
	{"series": "B05_Marketplace", "type": "ECO-03", "level": 3, "fn": "b05_market"},
	{"series": "B05_Marketplace", "type": "ECO-03", "level": 4, "fn": "b05_market"},
	{"series": "B05_Marketplace", "type": "ECO-03", "level": 5, "fn": "b05_market"},
	{"series": "B07_StoneQuarry", "type": "RES-02", "level": 1, "fn": "b07_quarry"},
	{"series": "B07_StoneQuarry", "type": "RES-02", "level": 2, "fn": "b07_quarry"},
	{"series": "B07_StoneQuarry", "type": "RES-02", "level": 3, "fn": "b07_quarry"},
	{"series": "B07_StoneQuarry", "type": "RES-02", "level": 4, "fn": "b07_quarry"},
	{"series": "B07_StoneQuarry", "type": "RES-02", "level": 5, "fn": "b07_quarry"},
	{"series": "B08_IronMine", "type": "RES-03", "level": 1, "fn": "b08_mine"},
	{"series": "B08_IronMine", "type": "RES-03", "level": 2, "fn": "b08_mine"},
	{"series": "B08_IronMine", "type": "RES-03", "level": 3, "fn": "b08_mine"},
	{"series": "B08_IronMine", "type": "RES-03", "level": 4, "fn": "b08_mine"},
	{"series": "B08_IronMine", "type": "RES-03", "level": 5, "fn": "b08_mine"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 1, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 2, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 3, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 4, "fn": "b18_gate"},
	{"series": "B18_WallsAndGate", "type": "SUP-03", "level": 5, "fn": "b18_gate"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 1, "fn": "b01_hall54"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 2, "fn": "b01_hall54"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 3, "fn": "b01_hall54"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 4, "fn": "b01_hall54"},
	{"series": "B01_TownHall", "type": "ECO-05", "level": 5, "fn": "b01_hall54"},
	{"series": "B02_House", "type": "ECO-04", "level": 1, "fn": "b02_house54"},
	{"series": "B02_House", "type": "ECO-04", "level": 2, "fn": "b02_house54"},
	{"series": "B02_House", "type": "ECO-04", "level": 3, "fn": "b02_house54"},
	{"series": "B02_House", "type": "ECO-04", "level": 4, "fn": "b02_house54"},
	{"series": "B02_House", "type": "ECO-04", "level": 5, "fn": "b02_house54"},
	{"series": "B06_LumberCamp", "type": "RES-01", "level": 1, "fn": "b06_lumber54"},
	{"series": "B06_LumberCamp", "type": "RES-01", "level": 2, "fn": "b06_lumber54"},
	{"series": "B06_LumberCamp", "type": "RES-01", "level": 3, "fn": "b06_lumber54"},
	{"series": "B06_LumberCamp", "type": "RES-01", "level": 4, "fn": "b06_lumber54"},
	{"series": "B06_LumberCamp", "type": "RES-01", "level": 5, "fn": "b06_lumber54"},
	{"series": "B09_Farm", "type": "RES-04", "level": 1, "fn": "b09_farm54"},
	{"series": "B09_Farm", "type": "RES-04", "level": 2, "fn": "b09_farm54"},
	{"series": "B09_Farm", "type": "RES-04", "level": 3, "fn": "b09_farm54"},
	{"series": "B09_Farm", "type": "RES-04", "level": 4, "fn": "b09_farm54"},
	{"series": "B09_Farm", "type": "RES-04", "level": 5, "fn": "b09_farm54"},
	{"series": "B10_HuntingCamp", "type": "RES-05", "level": 1, "fn": "b10_hunt54"},
	{"series": "B10_HuntingCamp", "type": "RES-05", "level": 2, "fn": "b10_hunt54"},
	{"series": "B10_HuntingCamp", "type": "RES-05", "level": 3, "fn": "b10_hunt54"},
	{"series": "B10_HuntingCamp", "type": "RES-05", "level": 4, "fn": "b10_hunt54"},
	{"series": "B10_HuntingCamp", "type": "RES-05", "level": 5, "fn": "b10_hunt54"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 1, "fn": "b11_barracks54"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 2, "fn": "b11_barracks54"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 3, "fn": "b11_barracks54"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 4, "fn": "b11_barracks54"},
	{"series": "B11_InfantryBarracks", "type": "MIL-01", "level": 5, "fn": "b11_barracks54"},
	{"series": "B12_ArcheryRange", "type": "MIL-02", "level": 1, "fn": "b12_range54"},
	{"series": "B12_ArcheryRange", "type": "MIL-02", "level": 2, "fn": "b12_range54"},
	{"series": "B12_ArcheryRange", "type": "MIL-02", "level": 3, "fn": "b12_range54"},
	{"series": "B12_ArcheryRange", "type": "MIL-02", "level": 4, "fn": "b12_range54"},
	{"series": "B12_ArcheryRange", "type": "MIL-02", "level": 5, "fn": "b12_range54"},
	{"series": "B13_Stables", "type": "MIL-03", "level": 1, "fn": "b13_stables54"},
	{"series": "B13_Stables", "type": "MIL-03", "level": 2, "fn": "b13_stables54"},
	{"series": "B13_Stables", "type": "MIL-03", "level": 3, "fn": "b13_stables54"},
	{"series": "B13_Stables", "type": "MIL-03", "level": 4, "fn": "b13_stables54"},
	{"series": "B13_Stables", "type": "MIL-03", "level": 5, "fn": "b13_stables54"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 1, "fn": "b14_smith54"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 2, "fn": "b14_smith54"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 3, "fn": "b14_smith54"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 4, "fn": "b14_smith54"},
	{"series": "B14_Blacksmith", "type": "MIL-04", "level": 5, "fn": "b14_smith54"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 1, "fn": "b15_academy54"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 2, "fn": "b15_academy54"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 3, "fn": "b15_academy54"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 4, "fn": "b15_academy54"},
	{"series": "B15_MilitaryAcademy", "type": "MIL-05", "level": 5, "fn": "b15_academy54"},
	{"series": "B16_Infirmary", "type": "SUP-01", "level": 1, "fn": "b16_infirmary54"},
	{"series": "B16_Infirmary", "type": "SUP-01", "level": 2, "fn": "b16_infirmary54"},
	{"series": "B16_Infirmary", "type": "SUP-01", "level": 3, "fn": "b16_infirmary54"},
	{"series": "B16_Infirmary", "type": "SUP-01", "level": 4, "fn": "b16_infirmary54"},
	{"series": "B16_Infirmary", "type": "SUP-01", "level": 5, "fn": "b16_infirmary54"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 1, "fn": "b17_siege54"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 2, "fn": "b17_siege54"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 3, "fn": "b17_siege54"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 4, "fn": "b17_siege54"},
	{"series": "B17_SiegeWorkshop", "type": "SUP-02", "level": 5, "fn": "b17_siege54"},
	{"series": "B19_Watchtower", "type": "SUP-04", "level": 1, "fn": "b19_tower54"},
	{"series": "B19_Watchtower", "type": "SUP-04", "level": 2, "fn": "b19_tower54"},
	{"series": "B19_Watchtower", "type": "SUP-04", "level": 3, "fn": "b19_tower54"},
	{"series": "B19_Watchtower", "type": "SUP-04", "level": 4, "fn": "b19_tower54"},
	{"series": "B19_Watchtower", "type": "SUP-04", "level": 5, "fn": "b19_tower54"},
	{"series": "B20_Well", "type": "SUP-05", "level": 1, "fn": "b20_well54"},
	{"series": "B20_Well", "type": "SUP-05", "level": 2, "fn": "b20_well54"},
	{"series": "B20_Well", "type": "SUP-05", "level": 3, "fn": "b20_well54"},
	{"series": "B20_Well", "type": "SUP-05", "level": 4, "fn": "b20_well54"},
	{"series": "B20_Well", "type": "SUP-05", "level": 5, "fn": "b20_well54"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 1, "fn": "b21_sawmill54"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 2, "fn": "b21_sawmill54"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 3, "fn": "b21_sawmill54"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 4, "fn": "b21_sawmill54"},
	{"series": "B21_Sawmill", "type": "ALT-02", "level": 5, "fn": "b21_sawmill54"},
	{"series": "B22_WheatFarm", "type": "ALT-05", "level": 1, "fn": "b22_wheat54"},
	{"series": "B22_WheatFarm", "type": "ALT-05", "level": 2, "fn": "b22_wheat54"},
	{"series": "B22_WheatFarm", "type": "ALT-05", "level": 3, "fn": "b22_wheat54"},
	{"series": "B22_WheatFarm", "type": "ALT-05", "level": 4, "fn": "b22_wheat54"},
	{"series": "B22_WheatFarm", "type": "ALT-05", "level": 5, "fn": "b22_wheat54"},
	{"series": "B23_HuntingLodge", "type": "ALT-06", "level": 1, "fn": "b23_lodge54"},
	{"series": "B23_HuntingLodge", "type": "ALT-06", "level": 2, "fn": "b23_lodge54"},
	{"series": "B23_HuntingLodge", "type": "ALT-06", "level": 3, "fn": "b23_lodge54"},
	{"series": "B23_HuntingLodge", "type": "ALT-06", "level": 4, "fn": "b23_lodge54"},
	{"series": "B23_HuntingLodge", "type": "ALT-06", "level": 5, "fn": "b23_lodge54"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 1, "fn": "b24_fishing54"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 2, "fn": "b24_fishing54"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 3, "fn": "b24_fishing54"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 4, "fn": "b24_fishing54"},
	{"series": "B24_FishingHut", "type": "ALT-07", "level": 5, "fn": "b24_fishing54"},
	{"series": "B25_HerbalGarden", "type": "ALT-08", "level": 1, "fn": "b25_herbal54"},
	{"series": "B25_HerbalGarden", "type": "ALT-08", "level": 2, "fn": "b25_herbal54"},
	{"series": "B25_HerbalGarden", "type": "ALT-08", "level": 3, "fn": "b25_herbal54"},
	{"series": "B25_HerbalGarden", "type": "ALT-08", "level": 4, "fn": "b25_herbal54"},
	{"series": "B25_HerbalGarden", "type": "ALT-08", "level": 5, "fn": "b25_herbal54"},
	{"series": "B26_StoneWorkshop", "type": "ALT-09", "level": 1, "fn": "b26_stonework54"},
	{"series": "B26_StoneWorkshop", "type": "ALT-09", "level": 2, "fn": "b26_stonework54"},
	{"series": "B26_StoneWorkshop", "type": "ALT-09", "level": 3, "fn": "b26_stonework54"},
	{"series": "B26_StoneWorkshop", "type": "ALT-09", "level": 4, "fn": "b26_stonework54"},
	{"series": "B26_StoneWorkshop", "type": "ALT-09", "level": 5, "fn": "b26_stonework54"},
	{"series": "B27_Smelter", "type": "ALT-10", "level": 1, "fn": "b27_smelter54"},
	{"series": "B27_Smelter", "type": "ALT-10", "level": 2, "fn": "b27_smelter54"},
	{"series": "B27_Smelter", "type": "ALT-10", "level": 3, "fn": "b27_smelter54"},
	{"series": "B27_Smelter", "type": "ALT-10", "level": 4, "fn": "b27_smelter54"},
	{"series": "B27_Smelter", "type": "ALT-10", "level": 5, "fn": "b27_smelter54"},
]

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
# ============================================================== B06 Lumber Camp (RES-01)
# ============================================================== B09 Farm (RES-04)
# ============================================================== B11 Infantry Barracks (MIL-01)
# ============================================================== B13 Stables (MIL-03)
# ============================================================== B14 Blacksmith (MIL-04)
# ============================================================== B15 Military Academy (MIL-05)
# ============================================================== B16 Infirmary (SUP-01)
# ============================================================== B17 Siege Workshop (SUP-02)
# ============================================================== B19 Watchtower (SUP-04)
# ============================================================== B21 Sawmill (ALT-02)
# ============================================================== B23 Hunting Lodge (ALT-06)
# ============================================================== B24 Fishing Hut (ALT-07)
# ============================================================== B25 Herbal Garden (ALT-08)
# ============================================================== B26 Stone Workshop (ALT-09)
# ============================================================== shared helpers (build 53)
static func _quad2(k, mat: String, a: Vector3, b: Vector3, c: Vector3, d: Vector3, tint := Color.WHITE) -> void:
	## Double-sided quad (free-standing surfaces: tents, gallery roofs, mounds).
	k.quad(mat, a, b, c, d, tint)
	k.quad(mat, a, d, c, b, tint)

static func _tri2(k, mat: String, a: Vector3, b: Vector3, c: Vector3, tint := Color.WHITE) -> void:
	k.tri(mat, a, b, c, tint)
	k.tri(mat, a, c, b, tint)

static func _louvre(k, c: Vector3, w: float, h: float, yaw: float) -> void:
	## Ventilation louvre on a wall face (local +Z out of the wall): dark slot + slanted slats.
	k.push_at(c, yaw)
	k.box("soot", Vector3(0, 0, 0.0), Vector3(w, h, 0.04))
	var n = maxi(2, roundi(h / 0.16))
	for i in n:
		var y = -h * 0.5 + h * (i + 0.5) / n
		k.box("oak_light", Vector3(0, y, 0.05), Vector3(w - 0.04, 0.035, 0.16), 0, Color.WHITE, 35)
	k.beam("dark_oak", Vector3(-w * 0.5 - 0.05, -h * 0.5 - 0.05, 0.06), Vector3(w * 0.5 + 0.05, -h * 0.5 - 0.05, 0.06), 0.08, 0.08)
	k.beam("dark_oak", Vector3(-w * 0.5 - 0.05, h * 0.5 + 0.05, 0.06), Vector3(w * 0.5 + 0.05, h * 0.5 + 0.05, 0.06), 0.08, 0.08)
	for s in [-1.0, 1.0]:
		k.beam("dark_oak", Vector3(s * (w * 0.5 + 0.05), -h * 0.5 - 0.05, 0.06), Vector3(s * (w * 0.5 + 0.05), h * 0.5 + 0.05, 0.06), 0.08, 0.08)
	k.pop()

static func _vent_cupola(k, p: Vector3, s: float, roof := "shingle") -> void:
	## Louvred ridge ventilator: the granary's roof signature.
	k.box("plank", p + Vector3(0, 0.15 * s, 0), Vector3(0.95 * s, 0.5 * s, 0.95 * s))
	var hy = 0.4 * s
	var lh = 0.6 * s
	for yaw in [0.0, 90.0, 180.0, 270.0]:
		var dir = Vector3(sin(deg_to_rad(yaw)), 0, cos(deg_to_rad(yaw)))
		_louvre(k, p + Vector3(0, hy + lh * 0.5, 0) + dir * 0.42 * s, 0.62 * s, lh * 0.8, yaw)
	for cx in [-1.0, 1.0]:
		for cz in [-1.0, 1.0]:
			k.beam("oak", p + Vector3(cx * 0.42 * s, hy - 0.05, cz * 0.42 * s), p + Vector3(cx * 0.42 * s, hy + lh, cz * 0.42 * s), 0.1 * s, 0.1 * s)
	k.box("plank", p + Vector3(0, hy + lh * 0.5, 0), Vector3(0.7 * s, lh, 0.7 * s), 0, Color(0.6, 0.55, 0.5))
	k.pyramid_roof(roof, p + Vector3(0, hy + lh + 0.05, 0), 0.95 * s, 0.6 * s, 0.14)

static func _sliding_gate(k, cx: float, front: float, floor_y: float, w: float, h: float, slide: Array, depth := 0.12) -> void:
	## Wide goods gate: dark opening, iron track above, plank leaves slid aside (slide: -1/1 per leaf).
	k.box("soot", Vector3(cx, floor_y + h * 0.5, front - 0.32), Vector3(w + 0.1, h, 0.1))
	k.box("plank", Vector3(cx, floor_y + 0.02, front - 0.2), Vector3(w, 0.04, 0.5))
	k.beam("iron", Vector3(cx - w, floor_y + h + 0.18, front + 0.16), Vector3(cx + w, floor_y + h + 0.18, front + 0.16), 0.07, 0.07)
	var lw = w * 0.5
	var i = 0
	for s in slide:
		var lc = Vector3(cx + float(s) * (w * 0.5 + lw * 0.5) * (1.0 if i == 0 or slide.size() == 1 else 1.0), floor_y + h * 0.5 + 0.04, front + depth + 0.04 * i)
		if slide.size() == 2:
			lc.x = cx + float(s) * (w * 0.5 + lw * 0.5)
		var planks = 5
		for p in planks:
			k.box("oak", lc + Vector3(-lw * 0.5 + lw * (p + 0.5) / planks, 0, 0), Vector3(lw / planks - 0.015, h, 0.08), 0, k.jitter(0.12))
		k.beam("dark_oak", lc + Vector3(-lw * 0.42, -h * 0.42, 0.06), lc + Vector3(lw * 0.42, h * 0.42, 0.06), 0.09, 0.05)
		for yy in [-h * 0.42, h * 0.42]:
			k.box("dark_oak", lc + Vector3(0, yy, 0.06), Vector3(lw - 0.04, 0.12, 0.04))
		k.box("iron", lc + Vector3(0, h * 0.5 + 0.08, 0.0), Vector3(lw * 0.8, 0.06, 0.05))
		i += 1

# ============================================================== B03 Warehouse (ECO-01)
## Low, long goods house with the ridge along the facade: wide sliding goods gates at
## cart height behind a stone-faced loading dock with a ramp (I), side goods shed (II),
## two gates and a loft hoist dormer (III), jib crane over the dock (IV), separate
## storeroom and paved receiving yard (V).
static func b03_warehouse(k, L: int) -> Dictionary:
	## Drawings B03 I-V: long plank-walled store with the ridge along the street, a
	## front gable over broad double freight doors with stone steps, window with red
	## shutters on the left, open loading canopy with a deck on the right. II stone
	## base and full loading deck with a ramp, III left wing, ridge vents and a fenced
	## paved yard, IV loft storey with a gallery and a jib crane on the right gable,
	## V closed storerooms left and right with the hoist lane kept clear.
	var lx = 8.0
	var lz = 4.8
	var c = Vector3(-0.3, 0, -2.0)
	var plinth: float = 0.6
	var wall = 2.9
	var rise = 2.1
	var front = c.z + lz * 0.5
	var dx = -1.6                       # centre of the freight doors
	var ey = plinth + wall
	# main body (vertical boards on a stone plinth)
	k.timber_house(c, lx, lz, ey, rise,
		[{"at": dx - (c.x - lx * 0.5), "w": 2.5, "y0": 0.0, "y1": 2.35, "kind": "double"},
		 {"at": 0.9, "w": 0.75, "y0": 1.0, "y1": 1.7, "kind": "window"}],
		[], [], [{"at": lz * 0.5, "w": 0.7, "y0": 1.1, "y1": 1.7, "kind": "window"}], "shingle", "plank", plinth, 0.0)
	# iron strap hinges on the doors
	for s in [-1.0, 1.0]:
		for y in [0.6, 1.8]:
			k.box("iron", Vector3(dx + s * 0.62, plinth + y, front + 0.16), Vector3(0.95, 0.07, 0.03))
	# front gable over the doors (cross gable) with the red banner
	var gw = 3.4
	k.box("plank", Vector3(dx, ey - 0.1, front + 0.25), Vector3(gw, 0.25, 0.5))
	for s in [-1.0, 1.0]:
		k.box("stone", Vector3(dx + s * (gw * 0.5 - 0.1), plinth * 0.5, front + 0.45), Vector3(0.4, plinth, 0.4))
		k.beam("oak", Vector3(dx + s * (gw * 0.5 - 0.1), plinth, front + 0.45), Vector3(dx + s * (gw * 0.5 - 0.1), ey, front + 0.45), 0.24, 0.24)
		k.beam("oak", Vector3(dx + s * (gw * 0.5 - 0.1), ey - 0.7, front + 0.45), Vector3(dx + s * 0.9, ey - 0.05, front + 0.45), 0.12, 0.12)
	k.push_at(Vector3(dx, 0, front - 0.4), 90)
	k.gable_roof("shingle", Vector3(0, ey, 0), 1.9, gw, 1.5, 0.3, "plank")
	k.gable_frame(Vector3(0, ey, 0), 1.9, gw, 1.5)
	k.pop()
	k.banner(Vector3(dx, ey + 1.0, front + 0.6), 0.5, 0.75, "cloth_red")
	# stone steps up to the doors
	var steps = 2 if L == 1 else 3
	k.stairs(Vector3(dx, 0, front + 0.65 + steps * 0.34), 3.0, steps, plinth / steps, 0.34, 0, "stone_light")
	# loading canopy and deck on the right of the doors
	var cx0 = dx + gw * 0.5 + 0.1
	var cx1: float = [c.x + lx * 0.5 + 0.4, c.x + lx * 0.5 + 0.6, c.x + lx * 0.5 + 0.6, c.x + lx * 0.5 - 0.4, c.x + lx * 0.5 - 0.4][L - 1]
	var cd: float = 2.2 if L == 1 else 2.7
	var deck_y = plinth
	k.box("stone", Vector3((cx0 + cx1) * 0.5, deck_y * 0.5 - 0.05, front + cd * 0.5), Vector3(cx1 - cx0, deck_y + 0.1, cd), 0, k.jitter(0.04))
	k.deck(Vector3(cx0, 0, front), Vector3(cx1, 0, front + cd), deck_y + 0.02, "plank", false, false, false)
	k.push_at(Vector3((cx0 + cx1) * 0.5, deck_y, front + cd * 0.5))
	k.lean_to(Vector3.ZERO, cx1 - cx0, cd, 2.25, wall - 0.15, "shingle", 3 if L == 1 else 4)
	k.pop()
	k.crate(Vector3(cx0 + 0.6, deck_y, front + 0.5)); k.crate(Vector3(cx0 + 1.2, deck_y, front + 0.6), 0.5, 15)
	k.crate(Vector3(cx0 + 0.85, deck_y + 0.55, front + 0.55), 0.45, -8)
	k.barrel(Vector3(cx1 - 0.6, deck_y, front + 0.5)); k.barrel(Vector3(cx1 - 0.5, deck_y, front + cd - 0.6))
	k.barrel(Vector3(cx0 + 2.0, deck_y, front + 0.4))
	if L >= 2:
		# railing along the deck edge and a broad ramp down to the yard
		k.railing(Vector3(cx1, deck_y, front + 0.2), Vector3(cx1, deck_y, front + cd), 0.8)
		var rx = (cx0 + cx1) * 0.5 - 0.3
		k.ramp(Vector3(rx, 0, front + cd + 3.6), Vector3(rx, deck_y + 0.02, front + cd), 1.9, "plank")
		k.lane(Vector3(rx, 0, front + cd + 3.5), Vector3(rx, deck_y * 0.2, front + cd + 2.8), 1.2, 1.9, "cart")
		for i in 2:
			k.lantern(Vector3(cx0 + 0.2 + i * (cx1 - cx0 - 0.4), deck_y + 1.9, front + cd - 0.1))
	if L >= 3:
		# left wing with its own lower roof and shuttered windows
		var wc = Vector3(c.x - lx * 0.5 - 1.0, 0, c.z + 0.2)
		k.timber_house(wc, 2.0, 4.0, plinth + 2.3, 1.2, [{"at": 1.25, "w": 0.7, "y0": 0.9, "y1": 1.55, "kind": "window"}], [], [], [], "shingle", "plank", plinth)
		# ridge ventilators
		for x in [c.x - 2.2, c.x + 2.0]:
			k.box("plank", Vector3(x, ey + rise + 0.25, c.z), Vector3(0.7, 0.6, 0.7))
			_louvre(k, Vector3(x, ey + rise + 0.3, c.z + 0.37), 0.5, 0.4, 0)
			k.pyramid_roof("shingle", Vector3(x, ey + rise + 0.58, c.z), 0.8, 0.35, 0.1)
		# paved, fenced receiving yard (stone piers and rails) with a gap at the ramp
		k.paving(Vector3(-6.3, 0, front + 0.9), Vector3(5.6, 0, 6.6), 0.05, 0.55)
		var gap0 = (cx0 + cx1) * 0.5 - 1.6
		var gap1 = (cx0 + cx1) * 0.5 + 1.0
		var xs = [-6.3, -4.3, gap0, gap1, 5.6]
		for x in xs:
			k.box("stone", Vector3(x, 0.4, 6.6), Vector3(0.42, 0.8, 0.42), 0, k.jitter(0.05))
		for i in xs.size() - 1:
			if xs[i] == gap0:
				continue
			k.fence(Vector3(xs[i] + 0.2, 0, 6.6), Vector3(xs[i + 1] - 0.2, 0, 6.6), 0.7)
		k.fence(Vector3(5.6, 0, 6.4), Vector3(5.6, 0, front + 1.0), 0.7)
		k.lantern(Vector3(gap0, 1.0, 6.6)); k.lantern(Vector3(gap1, 1.0, 6.6))
		k.cart(Vector3(4.3, 0, front + cd + 1.6), 100, "")
		for i in 3:
			k.crate(Vector3(-5.6 + i * 0.6, 0.05, 5.8), 0.5, i * 10.0)
		k.barrel(Vector3(4.6, 0.05, 6.0)); k.barrel(Vector3(4.0, 0.05, 6.1))
	if L >= 4:
		# loft storey over the right half with a front gable, gallery and winch
		var lx0 = cx0 - 0.2
		var lx1 = c.x + lx * 0.5
		var lz0 = c.z - lz * 0.5 + 0.6
		var lzf = front
		var ly = ey
		var lh = 2.0
		k.timber_wall(Vector3(lx0, ly, lzf), Vector3(lx1, ly, lzf), lh, [{"at": 0.9, "w": 0.6, "y0": 0.7, "y1": 1.3, "kind": "window"}, {"at": 2.0, "w": 0.6, "y0": 0.7, "y1": 1.3, "kind": "window"}], "plank")
		k.timber_wall(Vector3(lx1, ly, lzf), Vector3(lx1, ly, lz0), lh, [], "plank")
		k.timber_wall(Vector3(lx0, ly, lz0), Vector3(lx0, ly, lzf), lh, [], "plank")
		k.push_at(Vector3((lx0 + lx1) * 0.5, 0, (lz0 + lzf) * 0.5), 90)
		k.gable_roof("shingle", Vector3(0, ly + lh, 0), lzf - lz0, lx1 - lx0, 1.5, 0.35, "plank")
		k.gable_frame(Vector3(0, ly + lh, 0), lzf - lz0, lx1 - lx0, 1.5)
		k.pop()
		k.deck(Vector3(lx0, 0, lzf), Vector3(lx1 - 0.3, 0, lzf + 1.0), ly + 0.02, "plank", false, true, true)
		for x in [lx0 + 0.1, lx1 - 0.4]:
			k.beam("oak", Vector3(x, ly - 0.9, lzf + 0.1), Vector3(x, ly - 0.05, lzf + 0.9), 0.12, 0.12)
		k.railing(Vector3(lx0, ly, lzf + 1.0), Vector3(lx1 - 0.3, ly, lzf + 1.0), 0.8)
		k.crate(Vector3(lx0 + 0.6, ly, lzf + 0.5), 0.55); k.sack(Vector3(lx0 + 1.2, ly, lzf + 0.5)); k.sack(Vector3(lx0 + 1.5, ly, lzf + 0.55), 20)
		k.wheel(Vector3(lx1 - 0.7, ly + 1.1, lzf + 0.18), 0.4, Vector3.FORWARD)
		# jib crane on the right gable; the hook drops to a clear lane beside the canopy
		var cb = Vector3(lx1 + 0.05, ly + lh + 0.6, (lz0 + lzf) * 0.5 + 0.6)
		k.beam("oak", cb, cb + Vector3(1.6, 0, 0), 0.22, 0.24)
		k.beam("oak", cb + Vector3(0, -1.2, 0), cb + Vector3(1.0, -0.05, 0), 0.12, 0.12)
		k.hook_hoist(cb + Vector3(1.5, -0.1, 0), ly + lh - 0.4)
		k.paving(Vector3(lx1 - 0.2, 0, cb.z - 0.8), Vector3(lx1 + 2.2, 0, front + cd), 0.05, 0.5)
	if L == 5:
		# closed storerooms: left in front of the wing, right beside the hoist lane
		var sl = Vector3(c.x - lx * 0.5 - 1.1, 0, front + 1.3)
		k.push_at(sl, 0)
		k.timber_house(Vector3.ZERO, 2.4, 2.2, plinth + 2.1, 1.0, [{"at": 1.2, "w": 0.9, "y0": 0.0, "y1": 1.85, "kind": "door"}], [], [], [], "shingle", "plank", plinth)
		k.pop()
		var sr = Vector3(c.x + lx * 0.5 + 1.6, 0, front + 1.6)
		k.timber_house(sr, 1.5, 2.0, 2.4, 0.9, [{"at": 0.75, "w": 0.8, "y0": 0.0, "y1": 1.8, "kind": "door"}], [], [], [], "shingle", "plank", 0.3)
		for i in 4:
			k.sack(Vector3(-4.6 + (i % 2) * 0.45, 0.05, 5.0 + (i / 2) * 0.4), i * 30.0)
		k.crate(Vector3(-3.6, 0.05, 5.2), 0.55); k.crate(Vector3(-3.6, 0.6, 5.2), 0.5, 20)
	return {"worker": Vector3(-3.6, 0.0, 4.0) if L >= 3 else Vector3(-4.4, 0.0, 3.6)}

# ============================================================== B04 Granary (ECO-02)
static func b04_granary(k, L: int) -> Dictionary:
	## Drawings B04 I-V: tall plank granary with the gable to the street on stone
	## piers (slatted skirt between them), centre door with iron straps, straight stair
	## down to the street, louvres in the gable and along the side, wheat banner, a
	## slatted hopper on legs at the right. II porch roof over the door and a lean-to
	## over the hopper, III longer body with a louvred ridge monitor and wall hoppers,
	## IV hoist gantry with a sack on the rope and a loading ramp, V gabled side wing.
	var lx = 4.4
	var lz: float = 4.8 if L <= 2 else 6.4
	var fl = 1.15
	var wall = 3.1
	var rise = 2.4
	var c = Vector3(-1.2, 0, 0.4 - lz * 0.5)
	var x0 = c.x - lx * 0.5
	var x1 = c.x + lx * 0.5
	var z0 = c.z - lz * 0.5
	var z1 = c.z + lz * 0.5
	# stone piers with a slatted skirt between them
	var nz = 3 if L <= 2 else 4
	var pw: float = 0.7
	for i in 2:
		for j in nz:
			var p = Vector3(x0 + 0.2 if i == 0 else x1 - 0.2, 0, lerpf(z1 - 0.25, z0 + 0.25, j / float(nz - 1)))
			k.box("stone", p + Vector3(0, fl * 0.5, 0), Vector3(pw, fl, pw), 0, k.jitter(0.05))
			k.box("stone_light", p + Vector3(0, fl - 0.04, 0), Vector3(pw + 0.1, 0.08, pw + 0.1))
	for s in [[Vector3(x0 + 0.2, 0, z1 - 0.25), Vector3(x1 - 0.2, 0, z1 - 0.25)], [Vector3(x1 - 0.2, 0, z1 - 0.25), Vector3(x1 - 0.2, 0, z0 + 0.25)]]:
		var a: Vector3 = s[0]
		var b: Vector3 = s[1]
		var n = int(a.distance_to(b) / 0.2)
		for i in n:
			var p = a.lerp(b, (i + 0.5) / n)
			k.box("oak", p + Vector3(0, fl * 0.45, 0), Vector3(0.06, fl * 0.8, 0.06))
	k.box("dark_oak", Vector3(c.x, fl + 0.02, c.z), Vector3(lx + 0.15, 0.16, lz + 0.15))
	var wy = fl + 0.1
	k.timber_wall(Vector3(x0, wy, z1), Vector3(x1, wy, z1), wall, [{"at": lx * 0.5, "w": 1.0, "y0": 0.0, "y1": 2.0, "kind": "door"}], "plank", "oak", 0.2, 1.1)
	k.timber_wall(Vector3(x1, wy, z0), Vector3(x0, wy, z0), wall, [], "plank", "oak", 0.2, 1.1)
	k.timber_wall(Vector3(x0, wy, z0), Vector3(x0, wy, z1), wall, [], "plank", "oak", 0.2, 1.1)
	k.timber_wall(Vector3(x1, wy, z1), Vector3(x1, wy, z0), wall, [], "plank", "oak", 0.2, 1.1)
	for s in [-1.0, 1.0]:
		_louvre(k, Vector3(c.x + s * 1.35, wy + 1.3, z1 + 0.12), 0.6, 0.55, 0)
	for y in [0.6, 1.5]:
		k.box("iron", Vector3(c.x + 0.05, wy + y, z1 + 0.13), Vector3(0.7, 0.06, 0.03))
	# side louvres in every bay
	var bays = int(lz / 1.2)
	for i in bays:
		var zz = lerpf(z1 - 0.7, z0 + 0.7, (i + 0.5) / bays)
		_louvre(k, Vector3(x1 + 0.12, wy + wall - 0.7, zz), 0.75, 0.55, 90)
		if L >= 3:
			# wall hoppers below the upper louvres
			k.push_at(Vector3(x1 + 0.3, wy + wall * 0.45, zz), 90)
			k.extrude("plank", PackedVector2Array([Vector2(-0.35, 0.3), Vector2(0.35, 0.3), Vector2(0.12, -0.3), Vector2(-0.12, -0.3)]), -0.2, 0.2)
			k.pop()
	# steep roof, gable to the street
	var ey = wy + wall
	k.push_at(Vector3(c.x, 0, c.z), 90)
	k.gable_roof("shingle", Vector3(0, ey, 0), lz, lx, rise, 0.4, "plank")
	k.gable_frame(Vector3(0, ey, 0), lz, lx, rise)
	k.pop()
	for s in [-1.0, 1.0]:
		_louvre(k, Vector3(c.x + s * 0.75, ey + 0.65, z1 + 0.06), 0.55, 0.5, 0)
	k.banner(Vector3(c.x, ey + 1.35, z1 + 0.14), 0.55, 0.85, "cloth_red")
	k.box("dark_oak", Vector3(c.x, ey + rise + 0.15, z1 + 0.35), Vector3(0.26, 0.4, 0.26))
	# straight stair down to the street
	var steps = 5
	var run = 0.32
	k.stairs(Vector3(c.x, 0, z1 + 0.15 + steps * run), 1.15, steps, wy / steps, run, 0, "oak", false)
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(c.x + s * 0.62, 0.0, z1 + 0.2 + steps * run), Vector3(c.x + s * 0.62, wy, z1 + 0.15), 0.12, 0.16)
		k.beam("oak", Vector3(c.x + s * 0.62, 0.0, z1 + 0.15 + steps * run), Vector3(c.x + s * 0.62, 0.9, z1 + 0.15 + steps * run), 0.1, 0.1)
	for p in [Vector3(c.x + 1.0, 0, z1 + 0.6), Vector3(c.x + 1.45, 0, z1 + 0.9), Vector3(c.x + 1.25, 0, z1 + 1.25)]:
		k.sack(p, p.x * 40.0)
	# slatted hopper on legs at the right front
	var hp = Vector3(x1 + 0.9, 0, z1 - 0.6 - (0.0 if L <= 2 else 0.0))
	if L <= 3:
		for sx in [-0.45, 0.45]:
			for sz in [-0.35, 0.35]:
				k.beam("oak", hp + Vector3(sx, 0, sz), hp + Vector3(sx, 0.95, sz), 0.1, 0.1)
		k.push_at(hp + Vector3(0, 1.0, 0), 90)
		k.extrude("plank", PackedVector2Array([Vector2(-0.6, 0.45), Vector2(0.6, 0.45), Vector2(0.25, -0.1), Vector2(-0.25, -0.1)]), -0.5, 0.5)
		k.pop()
		for i in 5:
			k.box("dark_oak", hp + Vector3(-0.4 + i * 0.2, 1.47, 0), Vector3(0.05, 0.04, 1.0))
	if L >= 2:
		# porch roof over the door with a lantern
		k.push_at(Vector3(c.x, 0, z1 + 0.5), 90)
		k.gable_roof("shingle", Vector3(0, wy + 2.25, 0), 0.9, 1.7, 0.6, 0.15, "plank")
		k.gable_frame(Vector3(0, wy + 2.25, 0), 0.9, 1.7, 0.6)
		k.pop()
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(c.x + s * 0.8, wy, z1 + 0.85), Vector3(c.x + s * 0.8, wy + 2.25, z1 + 0.85), 0.12, 0.12)
		k.lantern(Vector3(c.x, wy + 2.05, z1 + 0.35))
		if L <= 3:
			# lean-to over the hopper with a chain
			k.push_at(Vector3(x1 + 0.95, wy + 0.6, z1 - 0.7), 90)
			k.lean_to(Vector3.ZERO, 2.0, 1.6, 1.4, 1.8, "shingle", 2)
			k.pop()
			k.cyl("iron", Vector3(x1 + 1.7, wy + 1.9, z1 + 0.2), Vector3(x1 + 1.7, 0.2, z1 + 0.2), 0.03, 4, false)
			k.barrel(Vector3(x1 + 0.4, 0, z1 + 0.25))
	if L >= 3:
		# louvred ridge monitor along the roof
		var my = ey + rise - 1.25
		var ml = lz - 0.9
		var mh = 2.2
		for s in [-1.0, 1.0]:
			k.box("plank", Vector3(c.x + s * 1.15, my + mh * 0.5, c.z), Vector3(0.12, mh, ml))
			for i in int(ml / 0.75):
				_louvre(k, Vector3(c.x + s * 1.23, my + mh - 0.55, c.z - ml * 0.5 + 0.4 + i * 0.75), 0.55, 0.45, 90.0 * s)
		k.box("plank", Vector3(c.x, my + mh * 0.5, c.z + ml * 0.5), Vector3(2.42, mh, 0.12))
		_louvre(k, Vector3(c.x, my + mh - 0.45, c.z + ml * 0.5 + 0.08), 0.7, 0.45, 0)
		k.push_at(Vector3(c.x, 0, c.z), 90)
		k.gable_roof("shingle", Vector3(0, my + mh, 0), ml, 2.3, 1.0, 0.3, "plank")
		k.gable_frame(Vector3(0, my + mh, 0), ml, 2.3, 1.0)
		k.pop()
	if L >= 4:
		# hoist gantry beside the body with a sack on the rope, lean-to bay and ramp
		var gx = x1 + 1.0
		var gz = z1 - 0.9
		for zz in [gz - 0.9, gz + 0.9]:
			k.box("stone", Vector3(gx, 0.15, zz), Vector3(0.4, 0.3, 0.4))
			k.beam("oak", Vector3(gx, 0.3, zz), Vector3(gx, 3.6, zz), 0.28, 0.28)
		k.beam("oak", Vector3(gx, 3.6, gz - 1.1), Vector3(gx, 3.6, gz + 1.1), 0.26, 0.3)
		k.hook_hoist(Vector3(gx, 3.45, gz), 2.2)
		k.sack(Vector3(gx, 0.85, gz))
		k.push_at(Vector3(gx + 1.3, 0, gz), 90)
		k.lean_to(Vector3.ZERO, 2.4, 1.8, 2.4, 3.0, "shingle", 2)
		k.pop()
		k.ramp(Vector3(gx + 1.3, 0, gz + 3.0), Vector3(gx + 1.3, 0.55, gz + 0.9), 1.1, "plank")
		k.box("plank", Vector3(gx + 1.3, 0.28, gz - 0.2), Vector3(1.3, 0.56, 1.6))
		for i in 3:
			k.sack(Vector3(gx + 2.2, 0, gz - 1.0 + i * 0.45), i * 25.0)
		# upper floor band over the lean-to
		k.box("shingle", Vector3(x1 + 0.6, wy + wall * 0.62, c.z + 0.3), Vector3(1.2, 0.08, lz - 2.2), 0, Color.WHITE, 0, -20)
	if L == 5:
		# gabled side wing at the back right
		var wc = Vector3(x1 + 1.7, 0, z0 + 1.7)
		k.timber_house(wc, 3.2, 3.2, fl + wall - 0.3, 1.7, [{"at": 1.6, "w": 0.8, "y0": 1.2, "y1": 1.8, "kind": "window"}], [], [], [], "shingle", "plank", fl)
		for i in 2:
			_louvre(k, Vector3(wc.x + 1.67, fl + 1.6, wc.z - 0.7 + i * 1.4), 0.6, 0.5, 90)
	return {"worker": Vector3(-3.6, 0.0, 3.0)}

# ============================================================== B05 Marketplace (ECO-03)
## Build 59 (pilot of the drawing-exact rework): drawings B05 III-V measured on their own
## camera (front, about 33 degrees down). A ROUND paved square centred on the fountain
## spot, ringed by an X-braced fence on stone-footed posts with planters outside; the
## entrance gate on the front axis (+Z) with the approach path to the plot edge; the
## pavilion on the axis at the back, its stair coming down towards the centre; straight
## gallery sections closing the back corners; two big stalls either side of the centre.
##   III  pavilion on a low base with one tent, open stall rows on the gallery lines.
##   IV   pavilion on a stone podium (arched niches, wide stair), covered galleries on both
##        sides, gate roof with finials, grass beds and a path ring round a produce table.
##   V    two tiers: skirt roof, band, railed upper storey and a markedly raised upper roof
##        with an open lantern cupola; the left gallery is joined to the pavilion by a lower
##        roofed connector on timber posts; the right gallery keeps its front section (free
##        walk behind the pavilion); fountain in the centre with a free ring round it;
##        the square paved in rings.
## Upgrade IV -> V on the plot (upgrade clock 0..1; k.when / k.leave, see _at):
##   0.13-0.34  site works: table and grass beds cleared, ring kerbs laid round the centre,
##              old tent and the back right gallery section taken down, posts of the upper
##              storey and of the connector set up
##   0.36-0.68  gallery and canvas: connector beams and roof, skirt roof panel by panel,
##              band, upper floor and railing, upper roof panel by panel, cupola, lanterns
##   0.70-0.94  fountain: basin, rim, pedestal, bowl, spouts and water, planters; the rings
##              of setts round it finish the paving
const MK_C := Vector3(0, 0, 1.75)       # centre of the round square (fountain spot)
const MK_R := 4.9                      # fence ring
const MK_P := Vector3(0, 0, -3.85)     # pavilion centre
const MK_POD := 2.65                   # podium corner radius (flat face to the front)
const MK_POST := 2.15                  # lower tier posts
const MK_GATE_X := 1.25                # gate posts (2.2 m clear)
# Gallery lines on the left (inner edge, plaza side); the right side mirrors them.
const MK_GAL := [Vector2(-4.6, -0.1), Vector2(-4.3, -3.3), Vector2(-3.6, -4.6)]
const MK_GAL_D := 1.45

static func _at(k, x: Variant) -> void:
	## Appear time of what follows on the upgrade INTO this level (upgrade clock 0..1).
	k.when(null if x == null else (float(x) - 0.12) / 0.83)

static func _mkp(theta: float, r: float, c := MK_C, y := 0.0) -> Vector3:
	var t = deg_to_rad(theta)
	return Vector3(c.x + cos(t) * r, y, c.z + sin(t) * r)

static func _yaw_to(from: Vector3, to: Vector3) -> float:
	## yaw that turns local +Z from 'from' towards 'to'
	return rad_to_deg(atan2(to.x - from.x, to.z - from.z))

static func _circle(c: Vector3, r: float, n := 40, rot := 0.0) -> PackedVector2Array:
	var pts = PackedVector2Array()
	for i in n:
		var a = deg_to_rad(rot) + TAU * i / n
		pts.append(Vector2(c.x + cos(a) * r, c.z + sin(a) * r))
	return pts

static func _ellipse(c: Vector3, rx: float, rz: float, yaw: float, n := 20) -> PackedVector2Array:
	var pts = PackedVector2Array()
	var y = deg_to_rad(yaw)
	for i in n:
		var a = TAU * i / n
		var p = Vector2(cos(a) * rx, sin(a) * rz).rotated(y)
		pts.append(Vector2(c.x + p.x, c.z + p.y))
	return pts

static func _prism(k, mat: String, c: Vector3, r: float, y0: float, y1: float, n := 8, rot := 22.5, tint := Color.WHITE, r_top := -1.0, cap := true) -> void:
	## Upright n-sided prism (flat face to the front with rot 22.5 for n = 8).
	k.next_piece()
	var rt = r if r_top < 0.0 else r_top
	var ct = Vector3(c.x, y1, c.z)
	for i in n:
		var t0 = deg_to_rad(rot + 360.0 * i / n)
		var t1 = deg_to_rad(rot + 360.0 * (i + 1) / n)
		var b0 = Vector3(c.x + cos(t0) * r, y0, c.z + sin(t0) * r)
		var b1 = Vector3(c.x + cos(t1) * r, y0, c.z + sin(t1) * r)
		var u0 = Vector3(c.x + cos(t0) * rt, y1, c.z + sin(t0) * rt)
		var u1 = Vector3(c.x + cos(t1) * rt, y1, c.z + sin(t1) * rt)
		k.quad(mat, b1, b0, u0, u1, tint)
		if cap:
			k.tri(mat, ct, u1, u0, tint * Color(1.06, 1.03, 0.98))

static func _ring(k, mat: String, c: Vector3, r0: float, r1: float, y: float, n := 36, from_t: Variant = null, to_t: Variant = null, gap := 0.0, alt := "") -> void:
	## Flat ring band (kerb, paving course) laid segment by segment from the front round.
	for i in n:
		if from_t != null:
			_at(k, lerpf(float(from_t), float(to_t), float(i) / maxf(1.0, n - 1.0)))
		else:
			k.next_piece()
		var g = gap / maxf(r1, 0.1) * 0.5
		var a0 = deg_to_rad(90.0 + 360.0 * i / n) + g
		var a1 = deg_to_rad(90.0 + 360.0 * (i + 1) / n) - g
		var i0 = Vector3(c.x + cos(a0) * r0, y, c.z + sin(a0) * r0)
		var i1 = Vector3(c.x + cos(a1) * r0, y, c.z + sin(a1) * r0)
		var o0 = Vector3(c.x + cos(a0) * r1, y, c.z + sin(a0) * r1)
		var o1 = Vector3(c.x + cos(a1) * r1, y, c.z + sin(a1) * r1)
		var m: String = mat if alt == "" or i % 2 == 0 else alt
		var tn = k.jitter(0.07)
		k.quad(m, i0, i1, o1, o0, tn)
		k.quad(m, o0, o1, o1 - Vector3(0, 0.07, 0), o0 - Vector3(0, 0.07, 0), tn * Color(0.8, 0.8, 0.8))

static func _tent(k, c: Vector3, r0: float, y0: float, r1: float, y1: float, times: Array = [], valance := true, ribs := true) -> void:
	## Octagonal striped canvas roof of the drawings, from radius r0 at y0 up to r1 at y1
	## (r1 = 0: pointed), flat face to the front: cream panels with a coloured middle
	## stripe (wine and teal by turns), oak ribs on the hips, eave boards, scalloped
	## valance. times: optional [from, to] upgrade clock over the eight panels.
	for i in 8:
		if times.size() == 2:
			_at(k, lerpf(times[0], times[1], i / 7.0))
		var t0 = deg_to_rad(22.5 + 45.0 * i)
		var t1 = deg_to_rad(22.5 + 45.0 * (i + 1))
		var b0 = Vector3(c.x + cos(t0) * r0, y0, c.z + sin(t0) * r0)
		var b1 = Vector3(c.x + cos(t1) * r0, y0, c.z + sin(t1) * r0)
		var u0 = Vector3(c.x + cos(t0) * r1, y1, c.z + sin(t0) * r1)
		var u1 = Vector3(c.x + cos(t1) * r1, y1, c.z + sin(t1) * r1)
		var stripe: String = "awning_wine" if i % 2 == 0 else "awning_teal"
		var cuts = [0.0, 0.3, 0.7, 1.0]
		for s in 3:
			k.next_piece()
			_quad2(k, stripe if s == 1 else "awning", b0.lerp(b1, cuts[s]), b0.lerp(b1, cuts[s + 1]), u0.lerp(u1, cuts[s + 1]), u0.lerp(u1, cuts[s]))
		if ribs:
			k.beam("oak", b0 + Vector3(0, 0.06, 0), u0 + Vector3(0, 0.06, 0), 0.11, 0.1)
		k.beam("oak", b0 - Vector3(0, 0.04, 0), b1 - Vector3(0, 0.04, 0), 0.08, 0.14)
		if valance:
			for v in 4:
				var q0 = b0.lerp(b1, v / 4.0) - Vector3(0, 0.1, 0)
				var q1 = b0.lerp(b1, (v + 1) / 4.0) - Vector3(0, 0.1, 0)
				_tri2(k, stripe if v % 2 == 0 else "awning", q0, q1, (q0 + q1) * 0.5 + Vector3(0, -0.24, 0))

static func _finial(k, p: Vector3, h := 0.55) -> void:
	k.cyl("oak", p, p + Vector3(0, 0.3, 0), 0.07, 6)
	k.cyl("brass", p + Vector3(0, 0.28, 0), p + Vector3(0, 0.36, 0), 0.13, 8)
	k.cone("brass", p + Vector3(0, 0.36, 0), 0.11, h, 8)

static func _gallery_run(k, a: Vector2, b: Vector2, leave_t: Variant = null) -> void:
	## One straight section of the covered trading gallery (drawings IV-V): low posts on
	## stone footings with arched knee braces on the plaza side, tall posts and a closed
	## plank back on the outer side (open rail where the back faces the city camera),
	## striped canvas falling to the plaza with a scalloped valance, lanterns, counters.
	## leave_t: taken down on the next upgrade (roof first, then frame, posts last).
	var d = (b - a)
	var length = d.length()
	var dir = d / length
	var out = Vector2(-dir.y, dir.x)
	if out.dot((a + b) * 0.5 - Vector2(0, -1.5)) < 0.0:
		out = -out
	var n = maxi(1, ceili(length / 1.7))
	var lo = 2.5
	var hi = 3.05
	var A = Vector3(a.x, 0, a.y)
	var B = Vector3(b.x, 0, b.y)
	var O = Vector3(out.x, 0, out.y) * MK_GAL_D
	var yaw = rad_to_deg(atan2(-dir.y, dir.x))
	var seen = Vector2(out.x, out.y).dot(Vector2(0.707, 0.707)) > 0.2
	var lv = func(dt: float) -> void:
		k.leave(null if leave_t == null else float(leave_t) + dt)
	# floor of flags
	lv.call(0.06)
	k.ground_poly(PackedVector2Array([a, b, b + out * MK_GAL_D, a + out * MK_GAL_D]) if out.cross(dir) < 0.0 else PackedVector2Array([a, a + out * MK_GAL_D, b + out * MK_GAL_D, b]), "stone", 0.055)
	for i in n + 1:
		var pin = A.lerp(B, float(i) / n)
		var pout = pin + O
		lv.call(0.07)
		k.box("stone", pin + Vector3(0, 0.12, 0), Vector3(0.34, 0.24, 0.34), yaw, k.jitter(0.05))
		k.box("stone", pout + Vector3(0, 0.12, 0), Vector3(0.34, 0.24, 0.34), yaw, k.jitter(0.05))
		k.beam("oak", pin + Vector3(0, 0.24, 0), pin + Vector3(0, lo, 0), 0.2, 0.2)
		k.beam("oak", pout + Vector3(0, 0.24, 0), pout + Vector3(0, hi, 0), 0.2, 0.2)
		lv.call(0.04)
		k.beam("oak", pin + Vector3(0, lo - 0.05, 0), pout + Vector3(0, hi - 0.05, 0), 0.12, 0.16)
		# arched knee braces either side of the post along the eave
		for s in [-1.0, 1.0]:
			if (i == 0 and s < 0) or (i == n and s > 0):
				continue
			var e = pin + Vector3(dir.x, 0, dir.y) * s * 0.55
			k.beam("oak", pin + Vector3(0, lo - 0.62, 0), e + Vector3(0, lo - 0.12, 0), 0.1, 0.12)
		lv.call(-0.02)
		k.lantern(pin + Vector3(0, lo - 0.42, 0) - O.normalized() * 0.2)
	lv.call(0.04)
	k.beam("oak", A + Vector3(0, lo, 0), B + Vector3(0, lo, 0), 0.14, 0.2)
	k.beam("oak", A + O + Vector3(0, hi, 0), B + O + Vector3(0, hi, 0), 0.14, 0.2)
	# back: closed planks, or a low rail where the camera looks in
	lv.call(0.02)
	var mid = (A + B) * 0.5 + O
	if seen:
		k.box("plank", mid + Vector3(0, 0.55, 0), Vector3(length, 0.7, 0.08), yaw, k.jitter(0.08))
	else:
		k.box("plank", mid + Vector3(0, (hi + 0.24) * 0.5, 0), Vector3(length, hi - 0.24, 0.08), yaw, k.jitter(0.08))
	# counters along the back, goods facing the plaza
	lv.call(-0.03)
	for i in n:
		var cm = A.lerp(B, (i + 0.5) / n) + O * 0.68
		k.box("oak", cm + Vector3(0, 0.42, 0), Vector3(length / n * 0.78, 0.84, 0.48), yaw, k.jitter(0.08))
		var goods = [["cloth_red", "hay"], ["herb", "parchment"], ["hay", "awning_teal"], ["ore", "flower"]]
		var g = goods[(i + roundi(a.x * 3.0)) % goods.size()]
		k.box(g[0], cm + Vector3(0, 0.93, 0) + Vector3(dir.x, 0, dir.y) * -0.3, Vector3(0.5, 0.18, 0.34), yaw, k.jitter(0.1))
		k.box(g[1], cm + Vector3(0, 0.93, 0) + Vector3(dir.x, 0, dir.y) * 0.3, Vector3(0.5, 0.18, 0.34), yaw, k.jitter(0.1))
		k.barrel(cm + O.normalized() * -0.75 + Vector3(dir.x, 0, dir.y) * (length / n * 0.38))
	# canvas falling to the square: strips down the slope, cream with a wine and a teal
	# stripe per bay, scalloped valance on the low edge
	lv.call(0.0)
	var on = O.normalized()
	var ri = A - on * 0.4 + Vector3(0, lo + 0.12, 0)
	var rj = B - on * 0.4 + Vector3(0, lo + 0.12, 0)
	var ro = A + O + on * 0.25 + Vector3(0, hi + 0.16, 0)
	var rp = B + O + on * 0.25 + Vector3(0, hi + 0.16, 0)
	var strips = n * 5
	for s in strips:
		var u0 = float(s) / strips
		var u1 = float(s + 1) / strips
		var m: String = ["awning", "awning_wine", "awning", "awning_teal", "awning"][s % 5]
		k.next_piece()
		_quad2(k, m, ri.lerp(rj, u0), ri.lerp(rj, u1), ro.lerp(rp, u1), ro.lerp(rp, u0))
	for s in strips * 2:
		var q0 = ri.lerp(rj, float(s) / (strips * 2)) - Vector3(0, 0.06, 0)
		var q1 = ri.lerp(rj, float(s + 1) / (strips * 2)) - Vector3(0, 0.06, 0)
		_tri2(k, "awning_wine" if s % 2 == 0 else "awning", q0, q1, (q0 + q1) * 0.5 + Vector3(0, -0.22, 0))
	k.leave(null)

static func _mk_ground(k) -> void:
	## Round square, the apron round the pavilion and the approach through the gate.
	k.ground_poly(_circle(MK_C, MK_R + 0.12, 48), "stone", 0.04, Color(0.95, 0.85, 0.74))
	k.ground_poly(_circle(MK_P, 3.35, 8, 22.5), "stone", 0.035, Color(0.95, 0.85, 0.74))
	var gz = MK_C.z + sqrt(MK_R * MK_R - MK_GATE_X * MK_GATE_X)
	k.ground_poly(PackedVector2Array([Vector2(-1.15, gz - 0.6), Vector2(-1.25, 7.1), Vector2(1.25, 7.1), Vector2(1.15, gz - 0.6)]), "stone_light", 0.045)
	# light kerb lines either side of the approach
	for s in [-1.0, 1.0]:
		k.box("stone", Vector3(s * 1.2, 0.05, (gz + 7.1) * 0.5), Vector3(0.14, 0.06, 7.1 - gz + 0.2))

static func _mk_fence(k) -> void:
	## X-braced timber fence on stone-footed posts round the front of the square, from the
	## front end of each gallery to the gate; lavender planters outside it.
	var gate_th = rad_to_deg(asin(MK_GATE_X / MK_R))
	for side in [-1.0, 1.0]:
		var a0: float = 90.0 - side * gate_th    # the gate post on this side
		var front: Vector2 = Vector2(-MK_GAL[0].x, MK_GAL[0].y) if side > 0 else MK_GAL[0]
		var g = Vector2(front.x, front.y) - Vector2(MK_C.x, MK_C.z)
		var a1: float = rad_to_deg(atan2(g.y, g.x))
		if side < 0 and a1 < 0.0:
			a1 += 360.0
		var span = absf(a1 - a0)
		var n = maxi(2, ceili(span / 17.0))
		var prev = Vector3.ZERO
		for i in n + 1:
			var th = lerpf(a0, a1, float(i) / n)
			var p = _mkp(th, MK_R)
			k.box("stone", p + Vector3(0, 0.16, 0), Vector3(0.36, 0.32, 0.36), -th, k.jitter(0.05))
			k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, 1.12, 0), 0.18, 0.18)
			k.box("stone_light", p + Vector3(0, 1.17, 0), Vector3(0.26, 0.1, 0.26), -th)
			if i > 0:
				k.beam("oak", prev + Vector3(0, 0.95, 0), p + Vector3(0, 0.95, 0), 0.1, 0.12)
				k.beam("oak", prev + Vector3(0, 0.38, 0), p + Vector3(0, 0.38, 0), 0.08, 0.1)
				k.beam("oak", prev + Vector3(0, 0.4, 0), p + Vector3(0, 0.93, 0), 0.06, 0.07)
				k.beam("oak", prev + Vector3(0, 0.93, 0), p + Vector3(0, 0.4, 0), 0.06, 0.07)
				var pth = lerpf(a0, a1, (i - 0.5) / n)
				if i % 2 == 1 and absf(pth - 90.0) > 32.0:
					var pm = _mkp(pth, MK_R + 0.42)
					var yaw = _yaw_to(pm, MK_C) + 90.0
					k.box("plank", pm + Vector3(0, 0.2, 0), Vector3(1.0, 0.4, 0.38), yaw, k.jitter(0.08))
					k.bush(pm + Vector3(0, 0.32, 0) + (pm - MK_C).normalized().cross(Vector3.UP) * 0.22, 0.22, "lavender")
					k.bush(pm + Vector3(0, 0.3, 0) - (pm - MK_C).normalized().cross(Vector3.UP) * 0.22, 0.2, "flower")
			prev = p

static func _mk_gate(k, L: int) -> void:
	## Entrance of the drawings: two square oak posts on two-course stone plinths, an arch
	## of curved braces, the gable turned to the street with a diamond lattice, bunting
	## and lanterns; IV-V a striped canvas roof on the gable and brass finials.
	var gz = MK_C.z + sqrt(MK_R * MK_R - MK_GATE_X * MK_GATE_X)
	var eave = 2.75
	var apex = 3.42
	var hw = MK_GATE_X + 0.38
	for s in [-1.0, 1.0]:
		var x = s * MK_GATE_X
		k.box("stone", Vector3(x, 0.24, gz), Vector3(0.72, 0.48, 0.72), 0, k.jitter(0.04))
		k.box("stone", Vector3(x, 0.66, gz), Vector3(0.62, 0.36, 0.62), 0, k.jitter(0.04))
		k.box("stone_light", Vector3(x, 0.87, gz), Vector3(0.68, 0.07, 0.68))
		k.beam("oak", Vector3(x, 0.9, gz), Vector3(x, eave + 0.1, gz), 0.36, 0.36)
		k.box("oak", Vector3(x, eave + 0.16, gz), Vector3(0.46, 0.12, 0.46))
		# lantern on a bracket on the street face
		k.beam("iron", Vector3(x, 1.95, gz + 0.18), Vector3(x, 1.95, gz + 0.46), 0.04, 0.04)
		k.lantern(Vector3(x, 1.75, gz + 0.46))
		# curved braces from the post to the beam: the arch
		for j in 3:
			var t0 = j / 3.0
			var t1 = (j + 1) / 3.0
			var p0 = Vector3(x - s * (0.18 + 0.62 * (1.0 - cos(t0 * PI * 0.5))), 1.95 + 0.62 * sin(t0 * PI * 0.5), gz)
			var p1 = Vector3(x - s * (0.18 + 0.62 * (1.0 - cos(t1 * PI * 0.5))), 1.95 + 0.62 * sin(t1 * PI * 0.5), gz)
			k.beam("oak", p0, p1, 0.18, 0.22)
	k.beam("oak", Vector3(-MK_GATE_X - 0.18, 2.6, gz), Vector3(MK_GATE_X + 0.18, 2.6, gz), 0.16, 0.2)
	k.beam("oak", Vector3(-hw, eave, gz), Vector3(hw, eave, gz), 0.2, 0.22)
	for i in 5:
		var x = -0.8 + i * 0.4
		var y = 2.58 - absf(x) * 0.06
		_tri2(k, "awning_wine" if i % 2 == 0 else "awning_teal", Vector3(x - 0.15, y, gz + 0.03), Vector3(x + 0.15, y, gz + 0.03), Vector3(x, y - 0.3, gz + 0.03))
	# gable to the street: rafters and a diamond lattice
	for zz in [gz - 0.5, gz + 0.5]:
		k.beam("oak", Vector3(-hw, eave + 0.02, zz), Vector3(0, apex, zz), 0.12, 0.16)
		k.beam("oak", Vector3(hw, eave + 0.02, zz), Vector3(0, apex, zz), 0.12, 0.16)
	for i in 4:
		var x0 = -hw * 0.75 + i * hw * 0.5
		var y0 = eave + 0.06
		k.beam("oak", Vector3(x0 - hw * 0.25, y0, gz + 0.5), Vector3(x0 + hw * 0.25, y0 + minf(0.5, apex - eave - 0.1 - absf(x0) * 0.4), gz + 0.5), 0.05, 0.06)
		k.beam("oak", Vector3(x0 + hw * 0.25, y0, gz + 0.5), Vector3(x0 - hw * 0.25, y0 + minf(0.5, apex - eave - 0.1 - absf(x0) * 0.4), gz + 0.5), 0.05, 0.06)
	k.beam("oak", Vector3(0, apex, gz - 0.62), Vector3(0, apex, gz + 0.62), 0.14, 0.14)
	if L >= 4:
		for sx in [-1.0, 1.0]:
			var e0 = Vector3(sx * (hw + 0.1), eave - 0.05, gz - 0.62)
			var e1 = Vector3(sx * (hw + 0.1), eave - 0.05, gz + 0.62)
			var r0 = Vector3(0, apex + 0.05, gz - 0.62)
			var r1 = Vector3(0, apex + 0.05, gz + 0.62)
			var cuts = [0.0, 0.26, 0.36, 1.0]
			for i in 3:
				k.next_piece()
				_quad2(k, "awning_wine" if i == 0 else ("awning_teal" if i == 1 else "awning"), e0.lerp(r0, cuts[i]), e1.lerp(r1, cuts[i]), e1.lerp(r1, cuts[i + 1]), e0.lerp(r0, cuts[i + 1]))
			_finial(k, Vector3(sx * MK_GATE_X, eave + 0.22, gz), 0.5)
		_finial(k, Vector3(0, apex + 0.08, gz + 0.62), 0.55)

static func _mk_pavilion_base(k, L: int) -> float:
	## Podium, stair, lower tier of posts with arched braces, railing and the round counter.
	## Returns the eave height of the lower tier.
	var p = MK_P
	var base_h: float = 0.35 if L == 3 else 0.95
	var top: float = base_h + 2.5
	var ap = MK_POD * cos(PI / 8.0)
	_prism(k, "stone", p, MK_POD, -0.1, base_h - 0.08, 8, 22.5, k.jitter(0.03))
	_prism(k, "stone_light", p, MK_POD + 0.08, base_h - 0.08, base_h + 0.01, 8, 22.5)
	var steps = 2 if L == 3 else 4
	var run = 0.32 if L == 3 else 0.26
	k.stairs(Vector3(p.x, 0, p.z + ap + steps * run), 2.3, steps, base_h / steps, run, 0, "stone_light")
	if L >= 4:
		# arched niches with a lantern either side of the stair, pots and lantern posts
		for th in [45.0, 135.0, 0.0, 180.0]:
			var nrm = Vector3(cos(deg_to_rad(th)), 0, sin(deg_to_rad(th)))
			var c = p + nrm * (ap + 0.01) + Vector3(0, 0.42, 0)
			var yaw = rad_to_deg(atan2(nrm.x, nrm.z))
			k.box("soot", c, Vector3(0.5, 0.5, 0.04), yaw)
			k.box("soot", c + Vector3(0, 0.25, 0), Vector3(0.36, 0.14, 0.04), yaw)
			k.box("stone_light", c + Vector3(0, 0.36, 0) + nrm * 0.02, Vector3(0.7, 0.1, 0.05), yaw)
			k.box("glow", c + Vector3(0, -0.02, 0) + nrm * 0.02, Vector3(0.12, 0.18, 0.04), yaw)
		for s in [-1.0, 1.0]:
			var pp = Vector3(s * 1.45, 0, p.z + ap - 0.1)
			k.box("stone_light", pp + Vector3(0, base_h + 0.15, 0), Vector3(0.45, 0.3, 0.45))
			k.cyl("plank", pp + Vector3(0, base_h + 0.3, 0), pp + Vector3(0, base_h + 0.55, 0), 0.2, 8, true, Color(0.9, 0.75, 0.62), 0.25)
			k.bush(pp + Vector3(0, base_h + 0.5, 0), 0.22, "lavender")
			var lp = Vector3(s * 1.5, 0, p.z + ap + steps * run - 0.15)
			k.box("stone", lp + Vector3(0, 0.15, 0), Vector3(0.3, 0.3, 0.3))
			k.beam("dark_oak", lp + Vector3(0, 0.3, 0), lp + Vector3(0, 1.45, 0), 0.08, 0.08)
			k.lantern(lp + Vector3(0, 1.55, 0))
	var posts = []
	for i in 8:
		var a = deg_to_rad(22.5 + 45.0 * i)
		var q = p + Vector3(cos(a) * MK_POST, 0, sin(a) * MK_POST)
		posts.append(q)
		k.box("stone", q + Vector3(0, base_h + 0.12, 0), Vector3(0.34, 0.24, 0.34), 22.5 + 45.0 * i)
		k.beam("oak", q + Vector3(0, base_h + 0.24, 0), q + Vector3(0, top, 0), 0.24, 0.24)
	for i in 8:
		var q0: Vector3 = posts[i]
		var q1: Vector3 = posts[(i + 1) % 8]
		k.beam("oak", q0 + Vector3(0, top, 0), q1 + Vector3(0, top, 0), 0.18, 0.24)
		# arched braces under every beam
		k.beam("oak", q0 + Vector3(0, top - 0.75, 0), q0.lerp(q1, 0.3) + Vector3(0, top - 0.12, 0), 0.11, 0.13)
		k.beam("oak", q1 + Vector3(0, top - 0.75, 0), q0.lerp(q1, 0.7) + Vector3(0, top - 0.12, 0), 0.11, 0.13)
		# X-braced railing on every face but the front (the stair)
		var face = 22.5 + 45.0 * (i + 0.5)
		if absf(face - 90.0) < 1.0:
			continue
		k.beam("oak", q0 + Vector3(0, base_h + 0.85, 0), q1 + Vector3(0, base_h + 0.85, 0), 0.09, 0.11)
		k.beam("oak", q0 + Vector3(0, base_h + 0.25, 0), q1 + Vector3(0, base_h + 0.25, 0), 0.07, 0.09)
		k.beam("oak", q0.lerp(q1, 0.08) + Vector3(0, base_h + 0.27, 0), q0.lerp(q1, 0.92) + Vector3(0, base_h + 0.83, 0), 0.05, 0.06)
		k.beam("oak", q0.lerp(q1, 0.08) + Vector3(0, base_h + 0.83, 0), q0.lerp(q1, 0.92) + Vector3(0, base_h + 0.27, 0), 0.05, 0.06)
		# pennants under the eave beam
		for j in 3:
			var pm = q0.lerp(q1, 0.25 + j * 0.25) + Vector3(0, top - 0.14, 0)
			var tg = (q1 - q0).normalized() * 0.13
			_tri2(k, "awning_wine" if (i + j) % 2 == 0 else "awning_teal", pm - tg, pm + tg, pm + Vector3(0, -0.32, 0))
	# round counter with cheese wheels, crocks and sacks; lanterns from the beams
	_prism(k, "plank", p + Vector3(0, 0, 0.15), 1.05, base_h, base_h + 0.85, 8, 22.5, Color(1.0, 0.92, 0.82))
	_prism(k, "oak", p + Vector3(0, 0, 0.15), 1.15, base_h + 0.85, base_h + 0.93, 8, 22.5)
	for i in 6:
		var a = deg_to_rad(40.0 + i * 20.0)
		var g = p + Vector3(0, 0, 0.15) + Vector3(cos(a) * 0.75, base_h + 0.93, sin(a) * 0.75)
		if i % 2 == 0:
			k.cyl("hay", g, g + Vector3(0, 0.14, 0), 0.17, 10, true, Color(1.25, 1.12, 0.7))
		else:
			k.cyl("plank", g, g + Vector3(0, 0.26, 0), 0.12, 8, true, Color(0.75, 0.6, 0.45), 0.09)
	k.box("awning_wine", p + Vector3(0, base_h + 0.55, 1.22), Vector3(0.5, 0.5, 0.02))
	for i in 4:
		var a = deg_to_rad(67.5 + 90.0 * i)
		k.lantern(p + Vector3(cos(a) * 1.75, top - 0.45, sin(a) * 1.75))
	return top

static func _striped_stall(k, p: Vector3, yaw: float, stripe: String, w := 2.0, goods := 0, big := true, cream := "canvas") -> void:
	## Market stall of the drawings: corner posts, plank counter with a cloth runner,
	## cream awning with two coloured stripes sloping to the customers.
	k.push_at(p, yaw)
	var d = 1.3 if big else 1.0
	var hb = 2.5 if big else 2.2
	var hf = 2.05 if big else 1.8
	k.box("plank", Vector3(0, 0.45, 0.25), Vector3(w, 0.9, 0.5), 0, k.jitter(0.08))
	for sx in [-1.0, 1.0]:
		k.beam("dark_oak", Vector3(sx * w * 0.32, 0.1, 0.51), Vector3(-sx * w * 0.02, 0.8, 0.51), 0.06, 0.04)
	k.box("plank", Vector3(0, 0.92, 0.28), Vector3(w + 0.12, 0.06, 0.62))
	k.box(stripe, Vector3(0, 0.75, 0.6), Vector3(0.6, 0.35, 0.02))
	for sx in [-1.0, 1.0]:
		k.box("stone", Vector3(sx * w * 0.5, 0.12, -d * 0.5), Vector3(0.3, 0.24, 0.3))
		k.beam("oak", Vector3(sx * w * 0.5, 0.0, -d * 0.5), Vector3(sx * w * 0.5, hb + 0.35, -d * 0.5), 0.2, 0.2)
		k.beam("oak", Vector3(sx * w * 0.5, 0.0, d * 0.5), Vector3(sx * w * 0.5, hf, d * 0.5), 0.18, 0.18)
		k.box("oak", Vector3(sx * w * 0.5, hb + 0.45, -d * 0.5), Vector3(0.26, 0.15, 0.26))
	k.beam("oak", Vector3(-w * 0.5, hb, -d * 0.5), Vector3(w * 0.5, hb, -d * 0.5), 0.14, 0.18)
	k.box("plank", Vector3(0, 1.4, -d * 0.5 - 0.05), Vector3(w - 0.1, 1.2, 0.06))
	# awning: cream with two stripes, from the back beam down over the counter
	var slope = rad_to_deg(atan2(hb - hf, d + 0.4))
	var strips = 7
	for i in strips:
		var x = -w * 0.5 - 0.15 + (w + 0.3) * (i + 0.5) / strips
		var m: String = stripe if i == 1 or i == strips - 2 else cream
		k.box(m, Vector3(x, (hb + hf) * 0.5 + 0.08, 0.1), Vector3((w + 0.3) / strips + 0.01, 0.04, d + 0.55), 0, Color.WHITE, slope)
	# scalloped valance
	for i in 6:
		k.box(stripe if i % 2 == 0 else cream, Vector3(-w * 0.5 + w * (i + 0.5) / 6.0, hf - 0.08, d * 0.5 + 0.32), Vector3(w / 6.0 - 0.02, 0.22, 0.02))
	var goods_mats = ["hay", "herb", "cloth_red", "ore", "parchment", "flower"]
	for i in 3:
		k.box(goods_mats[(goods + i) % goods_mats.size()], Vector3(-w * 0.3 + i * w * 0.3, 1.02, 0.3), Vector3(w * 0.22, 0.16, 0.4), 0, k.jitter(0.1))
	k.box("oak", Vector3(-w * 0.25, 1.15, -0.2), Vector3(0.5, 0.3, 0.35))
	k.pop()

static func b05_market(k, L: int) -> Dictionary:
	## Drawings B05 I-V. I two stalls (teal and wine stripes) with bunting between
	## them on trodden earth, II plus a central produce table. III-V: see the section notes.
	if L <= 2:
		k.ground_poly(PackedVector2Array([Vector2(-4.6, -2.6), Vector2(4.6, -2.6), Vector2(5.0, 3.4), Vector2(-4.8, 3.6)]), "earth", 0.025)
		_striped_stall(k, Vector3(-2.1, 0, -0.6), 0.0, "cloth_teal", 2.2, 0)
		_striped_stall(k, Vector3(2.1, 0, -0.6), 0.0, "cloth_wine", 2.2, 3)
		for i in 5:
			var x = -1.0 + i * 0.5
			k.box("cloth_wine" if i % 2 == 0 else "cloth_teal", Vector3(x, 2.65 - absf(i - 2) * -0.04, -1.1), Vector3(0.32, 0.4, 0.02), 0, Color.WHITE, 0, 180)
		k.beam("rope", Vector3(-1.1, 2.9, -1.1), Vector3(1.1, 2.9, -1.1), 0.03, 0.03)
		k.barrel(Vector3(-3.6, 0, 0.6)); k.sack(Vector3(-3.2, 0, 1.0)); k.barrel(Vector3(3.6, 0, 0.6))
		if L == 2:
			k.table(Vector3(0, 0, 1.4), 1.8, 0.9, 0.85, 0, "plank")
			for i in 4:
				k.box(["hay", "herb", "flower", "parchment"][i], Vector3(-0.6 + i * 0.4, 0.92, 1.4), Vector3(0.3, 0.14, 0.4), 0, k.jitter(0.1))
			k.crate(Vector3(-0.8, 0, 2.4), 0.5); k.barrel(Vector3(0.9, 0, 2.3))
		return {"worker": Vector3(-0.2, 0.0, 3.2)}
	var leaving: bool = L == 4      # IV parts that the upgrade to V takes down carry times
	# ---- shared by III-V, emitted first and in the same order on every level, so the
	# parts that stay match exactly and the upgrade keeps them standing
	_mk_ground(k)
	_mk_fence(k)
	_mk_gate(k, mini(L, 4))
	for side in [-1.0, 1.0]:
		var sp = _mkp(190.0 if side < 0 else -10.0, 3.65)
		var yaw = 20.0 if side < 0 else -20.0
		_striped_stall(k, sp, yaw, "awning_teal" if side < 0 else "awning_wine", 2.4, 2 if side < 0 else 4, true, "awning")
		var back = sp + Vector3(sin(deg_to_rad(yaw)), 0, cos(deg_to_rad(yaw))) * -1.0
		k.barrel(back + Vector3(side * 0.9, 0, 0.9))
		k.crate(sp + Vector3(side * 0.9, 0, 1.3), 0.42, yaw)
		k.lantern(sp + Vector3(sin(deg_to_rad(yaw)), 0, cos(deg_to_rad(yaw))) * 0.66 + Vector3(cos(deg_to_rad(yaw)), 0, -sin(deg_to_rad(yaw))) * 1.32 + Vector3(0, 1.75, 0))
	var top = _mk_pavilion_base(k, L)
	k.lane(Vector3(0, 0, 7.0), Vector3(0, 0, MK_C.z + 2.1), 1.2, 2.2, "unit")
	var right: Array = MK_GAL.map(func(v: Vector2): return Vector2(-v.x, v.y))
	if L == 3:
		# open stall rows on the gallery lines
		for line in [MK_GAL, right]:
			for j in 2:
				var a: Vector2 = line[j]
				var b: Vector2 = line[j + 1]
				var m = (a + b) * 0.5
				var c3 = Vector3(m.x, 0, m.y)
				var yaw3 = _yaw_to(c3, Vector3(0, 0, -0.5))
				_striped_stall(k, c3 + (c3 - Vector3(0, 0, -1.5)).normalized() * 0.55, yaw3, "awning_teal" if j == 0 else "awning_wine", 1.8 if j == 0 else 1.4, j, false, "awning")
	else:
		_gallery_run(k, MK_GAL[0], MK_GAL[1])
		_gallery_run(k, MK_GAL[1], MK_GAL[2])
		_gallery_run(k, right[0], right[1])
	# ---- level-specific parts
	if L <= 4:
		if leaving:
			# the back right gallery section makes room for the walk behind the pavilion
			_gallery_run(k, right[1], right[2], 0.22)
			k.leave(0.14)
		# square of IV: grass beds either side of the approach, a path ring round a table
		k.ground_poly(_ellipse(Vector3(-1.95, 0, 4.15), 0.95, 0.6, -35.0), "herb", 0.06)
		k.ground_poly(_ellipse(Vector3(1.95, 0, 4.15), 0.95, 0.6, 35.0), "herb", 0.06)
		_ring(k, "path", MK_C, 2.45, 2.7, 0.058, 36)
		for s in [-1.0, 1.0]:
			k.bush(Vector3(s * 1.95, 0.05, 4.15), 0.3, "flower")
		if leaving:
			k.leave(0.13)
		k.table(MK_C + Vector3(0, 0.04, 0), 1.7, 0.85, 0.85, 0, "plank")
		for i in 4:
			k.box(["hay", "flower", "herb", "parchment"][i], MK_C + Vector3(-0.58 + i * 0.39, 0.97, 0), Vector3(0.3, 0.14, 0.4), 0, k.jitter(0.1))
		k.crate(MK_C + Vector3(-0.5, 0, 0.75), 0.42); k.sack(MK_C + Vector3(0.45, 0, 0.7))
		# tent roof with its lantern cupola (one tier)
		if leaving:
			k.leave(0.2)
		var rise = 1.6 if L == 3 else 2.0
		_tent(k, MK_P, 2.95, top, 0.55, top + rise)
		if leaving:
			k.leave(0.17)
		for i in 8:
			var a = deg_to_rad(22.5 + 45.0 * i)
			var q = MK_P + Vector3(cos(a) * 0.5, top + rise - 0.1, sin(a) * 0.5)
			k.beam("oak", q, q + Vector3(0, 0.6, 0), 0.08, 0.08)
		_prism(k, "oak", MK_P, 0.6, top + rise + 0.5, top + rise + 0.6, 8)
		_tent(k, MK_P, 0.8, top + rise + 0.6, 0.0, top + rise + 1.2, [], false, true)
		_finial(k, MK_P + Vector3(0, top + rise + 1.18, 0), 0.5)
		k.leave(null)
		return {"worker": Vector3(-1.6, 0.0, 5.3)}
	# ---- V
	# 1. site works: ring kerbs round the centre, posts of the upper storey and connector
	_ring(k, "stone_light", MK_C, 2.0, 2.3, 0.062, 28, 0.13, 0.2)
	_ring(k, "stone_light", MK_C, 4.15, 4.45, 0.062, 40, 0.15, 0.24)
	_ring(k, "stone", MK_C, 2.3, 4.15, 0.05, 40, 0.16, 0.26, 0.03)
	_at(k, 0.2)
	_ring(k, "stone_light", MK_C, 3.15, 3.3, 0.064, 40, 0.2, 0.27)
	var ur = 1.55
	var uy = top + 1.0          # floor of the upper storey
	var uh = uy + 1.7           # its eave (the tier is raised, the roof stays low)
	for i in 8:
		_at(k, 0.27 + i * 0.008)
		var a = deg_to_rad(22.5 + 45.0 * i)
		var q = MK_P + Vector3(cos(a) * ur, 0, sin(a) * ur)
		k.beam("oak", q + Vector3(0, top - 0.25, 0), q + Vector3(0, uh, 0), 0.2, 0.2)
	var gb_in: Vector2 = MK_GAL[2]
	var gb_out: Vector2 = gb_in + (Vector2(-0.881, -0.474)) * MK_GAL_D
	var pv1 = Vector2(MK_P.x + cos(deg_to_rad(190.0)) * 2.3, MK_P.z + sin(deg_to_rad(190.0)) * 2.3)
	var pv2 = Vector2(MK_P.x + cos(deg_to_rad(225.0)) * 2.3, MK_P.z + sin(deg_to_rad(225.0)) * 2.3)
	var cp = [gb_in.lerp(pv1, 0.25), gb_in.lerp(pv1, 0.68), gb_out.lerp(pv2, 0.5)]
	_at(k, 0.3)
	for q2 in cp:
		var q3 = Vector3(q2.x, 0, q2.y)
		k.box("stone", q3 + Vector3(0, 0.12, 0), Vector3(0.32, 0.24, 0.32))
		k.beam("oak", q3 + Vector3(0, 0.24, 0), q3 + Vector3(0, 2.62, 0), 0.22, 0.22)
	_at(k, 0.33)
	for j in 2:
		var q3 = Vector3(cp[j].x, 0, cp[j].y)
		for s in [-1.0, 1.0]:
			var e = q3 + Vector3(pv1.x - gb_in.x, 0, pv1.y - gb_in.y).normalized() * s * 0.5
			k.beam("oak", q3 + Vector3(0, 1.95, 0), e + Vector3(0, 2.5, 0), 0.1, 0.12)
	# 2. gallery and canvas: connector, skirt roof, band, upper storey and roof, cupola
	_at(k, 0.37)
	var f0 = Vector3(gb_in.x, 2.5, gb_in.y)
	var f1 = Vector3(pv1.x, 2.62, pv1.y)
	var b0 = Vector3(gb_out.x, 2.8, gb_out.y)
	var b1 = Vector3(pv2.x, 2.9, pv2.y)
	k.beam("oak", f0, f1, 0.16, 0.2)
	k.beam("oak", b0, b1, 0.16, 0.2)
	k.beam("oak", f0, b0, 0.12, 0.16)
	k.beam("oak", f1, b1, 0.12, 0.16)
	for i in 5:
		_at(k, 0.41 + i * 0.012)
		var u0 = i / 5.0
		var u1 = (i + 1) / 5.0
		var lift = Vector3(0, 0.12, 0)
		_quad2(k, ["awning", "awning_teal", "awning", "awning_wine", "awning"][i], f0.lerp(f1, u0) + lift, f0.lerp(f1, u1) + lift, b0.lerp(b1, u1) + lift, b0.lerp(b1, u0) + lift)
	for i in 6:
		var q0 = f0.lerp(f1, i / 6.0) + Vector3(0, 0.04, 0)
		var q1 = f0.lerp(f1, (i + 1) / 6.0) + Vector3(0, 0.04, 0)
		_tri2(k, "awning_wine" if i % 2 == 0 else "awning", q0, q1, (q0 + q1) * 0.5 + Vector3(0, -0.22, 0))
	k.lantern(f0.lerp(f1, 0.5) + Vector3(0, -0.45, 0))
	_at(k, 0.4)
	for i in 8:
		var a0 = deg_to_rad(22.5 + 45.0 * i)
		var a1 = deg_to_rad(22.5 + 45.0 * (i + 1))
		var q0 = MK_P + Vector3(cos(a0) * ur, uh, sin(a0) * ur)
		var q1 = MK_P + Vector3(cos(a1) * ur, uh, sin(a1) * ur)
		k.beam("oak", q0, q1, 0.16, 0.2)
		k.beam("oak", MK_P + Vector3(cos(a0) * ur, uy - 0.05, sin(a0) * ur), MK_P + Vector3(cos(a1) * ur, uy - 0.05, sin(a1) * ur), 0.14, 0.18)
	_tent(k, MK_P, 3.05, top, 1.72, top + 0.72, [0.44, 0.5])
	_at(k, 0.52)
	# the band that separates the two roofs
	_prism(k, "oak", MK_P, 1.78, top + 0.66, uy, 8, 22.5, Color(0.92, 0.85, 0.8), -1.0, false)
	_prism(k, "awning_wine", MK_P, 1.8, top + 0.74, top + 0.86, 8, 22.5, Color.WHITE, -1.0, false)
	_prism(k, "plank", MK_P, 1.74, uy - 0.06, uy, 8, 22.5)
	for i in 8:
		_at(k, 0.54 + i * 0.003)
		var a0 = deg_to_rad(22.5 + 45.0 * i)
		var a1 = deg_to_rad(22.5 + 45.0 * (i + 1))
		var q0 = MK_P + Vector3(cos(a0) * ur, uy, sin(a0) * ur)
		var q1 = MK_P + Vector3(cos(a1) * ur, uy, sin(a1) * ur)
		k.beam("oak", q0 + Vector3(0, 0.75, 0), q1 + Vector3(0, 0.75, 0), 0.08, 0.1)
		k.beam("oak", q0 + Vector3(0, 0.12, 0), q1 + Vector3(0, 0.12, 0), 0.07, 0.08)
		k.beam("oak", q0.lerp(q1, 0.1) + Vector3(0, 0.14, 0), q0.lerp(q1, 0.9) + Vector3(0, 0.73, 0), 0.05, 0.06)
		k.beam("oak", q0.lerp(q1, 0.1) + Vector3(0, 0.73, 0), q0.lerp(q1, 0.9) + Vector3(0, 0.14, 0), 0.05, 0.06)
		k.beam("oak", q0 + Vector3(0, 1.0, 0), q0.lerp(q1, 0.3) + Vector3(0, 1.45, 0), 0.08, 0.09)
		k.beam("oak", q1 + Vector3(0, 1.0, 0), q0.lerp(q1, 0.7) + Vector3(0, 1.45, 0), 0.08, 0.09)
	_tent(k, MK_P, 2.3, uh, 0.42, uh + 0.95, [0.57, 0.63])
	_at(k, 0.63)
	for i in 8:
		var a = deg_to_rad(22.5 + 45.0 * i)
		var q = MK_P + Vector3(cos(a) * 0.4, uh + 0.85, sin(a) * 0.4)
		k.beam("oak", q, q + Vector3(0, 0.6, 0), 0.08, 0.08)
	_prism(k, "oak", MK_P, 0.5, uh + 1.41, uh + 1.49, 8)
	_at(k, 0.65)
	_tent(k, MK_P, 0.7, uh + 1.49, 0.0, uh + 2.0, [], false, true)
	_at(k, 0.66)
	_finial(k, MK_P + Vector3(0, uh + 1.98, 0), 0.55)
	_at(k, 0.67)
	for i in 4:
		var a = deg_to_rad(67.5 + 90.0 * i)
		k.lantern(MK_P + Vector3(cos(a) * 1.15, uh - 0.35, sin(a) * 1.15))
	k.lantern(MK_P + Vector3(0, uh + 1.1, 0))
	# 3. fountain and the last of the paving
	var f = MK_C
	_at(k, 0.7)
	_prism(k, "stone_light", f, 1.32, -0.05, 0.14, 8, 22.5, Color(1.05, 1.02, 0.98))
	_prism(k, "stone_light", f, 0.95, 0.1, 0.5, 8, 22.5, k.jitter(0.03))
	_at(k, 0.73)
	_prism(k, "stone", f, 1.02, 0.5, 0.6, 8, 22.5, Color(1.08, 1.05, 1.0))
	_prism(k, "water", f, 0.8, 0.6, 0.62, 8, 22.5)
	_at(k, 0.76)
	_prism(k, "stone", f, 0.27, 0.6, 1.3, 8, 22.5, k.jitter(0.03))
	_prism(k, "stone_light", f, 0.36, 1.3, 1.42, 8, 22.5)
	_at(k, 0.79)
	_prism(k, "stone_light", f, 0.5, 1.42, 1.52, 8, 22.5, Color.WHITE, 0.56)
	_prism(k, "water", f, 0.44, 1.52, 1.54, 8, 22.5)
	_prism(k, "stone", f, 0.15, 1.52, 1.85, 8, 22.5)
	k.cone("stone_light", f + Vector3(0, 1.85, 0), 0.17, 0.32, 8)
	k.box("brass", f + Vector3(0, 2.2, 0), Vector3(0.1, 0.1, 0.1), 45)
	_at(k, 0.81)
	for i in 4:
		var a = deg_to_rad(45.0 + 90.0 * i)
		var dv = Vector3(cos(a), 0, sin(a))
		k.cyl("brass", f + dv * 0.22 + Vector3(0, 1.05, 0), f + dv * 0.42 + Vector3(0, 1.05, 0), 0.04, 6)
	_at(k, 0.84)
	for i in 4:
		var a = deg_to_rad(45.0 + 90.0 * i)
		var dv = Vector3(cos(a), 0, sin(a))
		k.beam("water", f + dv * 0.44 + Vector3(0, 1.05, 0), f + dv * 0.62 + Vector3(0, 0.62, 0), 0.06, 0.05)
	for i in 8:
		var a = deg_to_rad(22.5 + 45.0 * i)
		k.beam("water", f + Vector3(cos(a) * 0.48, 1.52, sin(a) * 0.48), f + Vector3(cos(a) * 0.62, 0.66, sin(a) * 0.62), 0.05, 0.04)
	for i in 2:
		_at(k, 0.86 + i * 0.02)
		var a = 0.0 if i == 0 else 180.0
		var pp = _mkp(a, 1.12)
		k.box("plank", pp + Vector3(0, 0.3, 0), Vector3(0.36, 0.34, 0.8), 0, Color(0.95, 0.85, 0.75))
		k.bush(pp + Vector3(0, 0.42, -0.2), 0.22, "lavender")
		k.bush(pp + Vector3(0, 0.42, 0.2), 0.2, "flower")
	_ring(k, "stone_light", MK_C, 0.95, 1.45, 0.066, 24, 0.88, 0.91, 0.05, "stone")
	_ring(k, "stone", MK_C, 1.45, 2.0, 0.066, 28, 0.91, 0.94, 0.05, "stone_light")
	_at(k, null)
	k.lane(MK_C, Vector3(1.7, 0, 1.7), 0.6, 1.8, "ring")
	k.lane(Vector3(3.45, 0, -0.6), Vector3(3.45, 0, -6.2), 0.8, 2.0, "unit")
	return {"worker": Vector3(-1.6, 0.0, 5.3),
		"site": {"scaffold": [0.0, MK_P.z, 3.35, 3.0, 8.6], "front_mid": false,
			"piles": [[-2.8, 4.9], [2.8, 4.9]], "hoist": [3.0, -0.3],
			"builders": [[-2.3, -0.45], [2.25, -0.4]], "carrier": [[-2.5, 4.4], [-1.6, -0.55]]}}

# ============================================================== B07 Stone Quarry (RES-02)
## Open pit face cut in pale stone, stepping down in benches towards the street (front)
## and the right, so the fresh cut faces turn to the city camera; sand work floor with
## cut blocks. II tripod derrick and ladder, III fourth bench and crane on the top,
## IV block slide and second shed, V upper post on the top bench and paved yard.
const QY_TH := 1.15

static func _bench_extent(j: int, L: int) -> Array:
	## [front z, left x] of bench j (0 = lowest); benches climb to the back.
	return [-0.2 - j * 1.15, -1.0 + j * 0.35]

static func _open_shed_z(k, c: Vector3, w: float, d: float, h: float, banner := "") -> void:
	## Open work shed of the drawings: gable to the street (ridge front-to-back),
	## heavy posts on stone pads with knee braces, tools on the back wall.
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 0.0, 1.0]:
			var p = c + Vector3(sx * w * 0.5, 0, sz * d * 0.5)
			k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 0.4), 0, k.jitter(0.05))
			k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, h, 0), 0.24, 0.24)
		k.beam("oak", c + Vector3(sx * w * 0.5, h, -d * 0.5 - 0.2), c + Vector3(sx * w * 0.5, h, d * 0.5 + 0.2), 0.2, 0.24)
		for sz in [-1.0, 1.0]:
			k.beam("oak", c + Vector3(sx * w * 0.5, h - 0.7, sz * d * 0.5), c + Vector3(sx * w * 0.5 - sx * 0.6, h - 0.05, sz * d * 0.5), 0.12, 0.12)
	k.beam("oak", c + Vector3(-w * 0.5 - 0.2, h, d * 0.5), c + Vector3(w * 0.5 + 0.2, h, d * 0.5), 0.2, 0.24)
	k.box("plank", c + Vector3(0, h * 0.5 + 0.2, -d * 0.5 + 0.05), Vector3(w, h - 0.4, 0.1))
	k.push_at(c, 90)
	k.gable_roof("shingle", Vector3(0, h + 0.1, 0), d + 0.2, w, 1.3, 0.4)
	k.gable_frame(Vector3(0, h + 0.1, 0), d + 0.2, w, 1.3)
	k.pop()
	if banner != "":
		k.banner(c + Vector3(-w * 0.5 + 0.05, h - 0.3, d * 0.5 + 0.15), 0.6, 1.0, banner)

static func b07_quarry(k, L: int) -> Dictionary:
	## Drawings B07 I-V: open work shed with a red banner at the front left, a pale
	## rock face cut in benches behind it and to the right, cut blocks on pallets on
	## the gravel floor. II treadwheel derrick on a stone plinth lifting a block, III
	## stair up the right flank to a roofed upper post with a railed gallery, IV more
	## benches, a rail track with carts on the right, V the upper post rebuilt in stone.
	var n: int = [2, 3, 4, 5, 5][L - 1]
	var back = -6.0
	var right = 5.5
	k.ground_poly(PackedVector2Array([Vector2(-6.0, -2.6), Vector2(5.8, -0.4), Vector2(5.8, 6.2), Vector2(-6.0, 6.2)]), "sand", 0.03)
	for jj in n:
		var e = _bench_extent(jj, L)
		var zf: float = e[0]
		var xl: float = e[1]
		var top = (jj + 1) * QY_TH
		k.box("stone_light", Vector3((xl + right) * 0.5, top * 0.5, (back + zf) * 0.5), Vector3(right - xl, top, zf - back), 0, Color(1.04, 1.02, 0.98) * k.jitter(0.03))
		# cut-block joints on the fresh faces
		for i in int((right - xl) / 0.8):
			k.box("stone", Vector3(xl + 0.4 + i * 0.8, top - QY_TH * 0.5, zf + 0.01), Vector3(0.05, QY_TH * 0.9, 0.03), 0, Color(0.72, 0.7, 0.66))
		k.box("stone", Vector3((xl + right) * 0.5, top - QY_TH * 0.5, zf + 0.01), Vector3(right - xl, 0.04, 0.03), 0, Color(0.72, 0.7, 0.66))
		if jj < n - 1:
			var en = _bench_extent(jj + 1, L)
			k.box("sand", Vector3((xl + right) * 0.5, top + 0.02, (en[0] + zf) * 0.5), Vector3(right - xl, 0.04, zf - en[0]), 0, Color(0.9, 0.86, 0.8))
			k.stone_block(Vector3(xl + 1.2 + jj * 0.9, top, zf - 0.45), Vector3(0.8, 0.5, 0.6), 4)
			if jj >= 1:
				k.stone_block(Vector3(right - 1.6, top, zf - 0.4), Vector3(0.7, 0.45, 0.55), -6)
	# rough natural rock round the cut: right flank and crown, with turf
	var tt = n * QY_TH
	var rim = []
	for i in 6:
		rim.append(Vector3(right - 0.4, 0, lerpf(1.0, back + 0.6, i / 5.0)))
	for i in 5:
		rim.append(Vector3(lerpf(right - 1.2, -0.6, i / 4.0), 0, back + 0.4))
	for p in rim:
		var hb = 0.0
		for jj in n:
			var e2 = _bench_extent(jj, L)
			if p.x >= e2[1] and p.z <= e2[0]:
				hb = (jj + 1) * QY_TH
		var hr = maxf(hb, 0.5) + k.rng.randf_range(0.35, 0.9)
		k.box("stone_rough", Vector3(p.x, hr * 0.5, p.z), Vector3(k.rng.randf_range(1.0, 1.4), hr, k.rng.randf_range(1.0, 1.4)), k.rng.randf_range(-20, 20), Color(0.8, 0.77, 0.7) * k.jitter(0.05), k.rng.randf_range(-6, 6), k.rng.randf_range(-6, 6))
		if k.rng.randf() < 0.6:
			k.bush(Vector3(p.x, hr - 0.1, p.z), 0.35)
	# open work shed with tools and a banner at the front left
	var sc = Vector3(-3.9, 0, -0.4)
	_open_shed_z(k, sc, 3.0, 3.4, 2.6, "cloth_red")
	k.workbench(sc + Vector3(0.1, 0, -1.2), 2.0, 0)
	k.barrel(sc + Vector3(-1.2, 0, 1.3))
	for i in 4:
		k.beam("iron", sc + Vector3(-0.9 + i * 0.5, 1.4, -1.68), sc + Vector3(-0.9 + i * 0.5, 2.0, -1.68), 0.05, 0.04)
	# blocks on pallets on the floor
	var pallets: int = [2, 4, 5, 6, 6][L - 1]
	for i in pallets:
		var pp = Vector3(-1.0 + (i % 3) * 1.6, 0, 3.0 + (i / 3) * 1.4)
		k.box("dark_oak", pp + Vector3(0, 0.07, 0), Vector3(1.3, 0.14, 0.95))
		for b in (2 if L <= 2 else 4):
			k.stone_block(pp + Vector3(-0.32 + (b % 2) * 0.64, 0.14 + (b / 2) * 0.48, 0), Vector3(0.58, 0.46, 0.8), k.rng.randf_range(-3, 3))
	k.road(Vector3(-4.0, 0, 6.8), Vector3(-2.5, 0, 2.5), 1.6, "path", 0.035, 0.3)
	if L >= 2:
		# treadwheel derrick on a stepped stone plinth, a block on the hook
		var dc = Vector3(1.6, 0, 0.6)
		k.box("stone", dc + Vector3(0, 0.2, 0), Vector3(2.6, 0.4, 2.2), 0, k.jitter(0.04))
		k.box("stone", dc + Vector3(0, 0.5, -0.1), Vector3(2.0, 0.3, 1.7), 0, k.jitter(0.04))
		var b0 = dc + Vector3(0, 0.65, 0)
		for sx in [-0.7, 0.7]:
			k.beam("oak", b0 + Vector3(sx, 0, 0.6), b0 + Vector3(0, 3.6, 0), 0.24, 0.24)
			k.beam("oak", b0 + Vector3(sx, 0, -0.6), b0 + Vector3(0, 3.6, 0), 0.24, 0.24)
		k.beam("oak", b0 + Vector3(0, 3.4, 0.2), b0 + Vector3(0.4, 4.4, 2.2), 0.24, 0.24)
		k.wheel(b0 + Vector3(-0.9, 0.8, 0), 0.75, Vector3.RIGHT)
		k.cyl("oak", b0 + Vector3(-0.9, 0.8, -0.3), b0 + Vector3(0.6, 0.8, -0.3), 0.15, 8)
		k.hook_hoist(b0 + Vector3(0.4, 4.3, 2.2), 2.2)
		k.stone_block(b0 + Vector3(0.4, 1.4, 2.2), Vector3(0.6, 0.45, 0.5))
	if L >= 3:
		# stair up the right flank to the top gallery and the upper post
		var steps = int(tt / 0.3)
		k.stairs(Vector3(right - 0.9, 0, 1.2 + 0.0), 0.9, steps, tt / steps, 0.32, 0, "oak", false)
		k.railing(Vector3(right - 0.4, 0.3, 1.2), Vector3(right - 0.4, tt, 1.2 - steps * 0.32), 0.85)
		var gz = _bench_extent(n - 1, L)[0]
		k.deck(Vector3(-0.6, 0, back + 0.4), Vector3(right - 0.4, 0, gz - 0.2), tt + 0.06, "plank", false, false, true)
		k.railing(Vector3(-0.6, tt + 0.06, gz - 0.2), Vector3(right - 1.4, tt + 0.06, gz - 0.2), 0.85)
		var up = Vector3(0.6, tt + 0.06, back + 1.6)
		if L <= 4:
			for sx in [-1.1, 1.1]:
				for sz in [-0.8, 0.8]:
					k.beam("oak", up + Vector3(sx, 0, sz), up + Vector3(sx, 2.0, sz), 0.18, 0.18)
			k.box("plank", up + Vector3(0, 0.9, -0.85), Vector3(2.2, 1.8, 0.08))
			k.gable_roof("shingle", up + Vector3(0, 2.05, 0), 2.6, 1.8, 0.7, 0.3)
			k.lantern(up + Vector3(-1.2, 1.7, 0.95))
		else:
			k.stone_wall(up + Vector3(-1.3, 0, -0.9), up + Vector3(1.3, 0, -0.9), 2.2, 0.35, "stone")
			for sx in [-1.2, 1.2]:
				k.box("stone", up + Vector3(sx, 1.1, 0.35), Vector3(0.4, 2.2, 0.4), 0, k.jitter(0.04))
			k.arch_wall(up + Vector3(0, 0, 0.75), 1.6, 0.35, 1.2, 2.8, 2.3, "stone", "stone_light")
			k.gable_roof("shingle", up + Vector3(0, 2.4, 0), 3.0, 2.2, 0.8, 0.3, "stone")
			k.lantern(up + Vector3(-1.4, 1.8, 1.0))
		k.table(up, 1.1, 0.6, 0.8)
		# small jib on the top edge
		k.crane(Vector3(right - 1.6, tt + 0.06, gz - 0.6), 2.2, Vector3(0.2, 0, 1.2), 1.8)
	if L >= 4:
		# rail track with block carts along the right front
		for zz in [2.0, 6.4]:
			pass
		for sx in [-0.4, 0.4]:
			k.box("iron", Vector3(4.2 + sx, 0.12, 4.0), Vector3(0.06, 0.07, 4.2))
		for i in 8:
			k.box("dark_oak", Vector3(4.2, 0.06, 2.0 + i * 0.55), Vector3(1.1, 0.07, 0.18))
		for zz in [3.0, 5.0]:
			k.box("dark_oak", Vector3(4.2, 0.55, zz), Vector3(1.0, 0.5, 1.5))
			k.stone_block(Vector3(4.2, 0.8, zz), Vector3(0.8, 0.35, 1.2))
		k.fence(Vector3(5.2, 0, 1.9), Vector3(5.2, 0, 6.0), 0.8)
		k.cart(Vector3(2.6, 0, 5.8), 60, "stone")
	return {"worker": Vector3(-2.2, 0.0, 4.6)}

# ============================================================== B08 Iron Mine (RES-03)
## Drawings B08 I-V: open lean-to shed with ore baskets at the left, a grey rocky
## hill with the adit to its right, rails into the dark tunnel. I timber portal sets,
## II rails out to the yard, a drainage channel and ore bins on the right, III a
## stone-faced arch portal with a winch frame above and a jib with a bucket, a
## closed store on the right, IV/V a timbered head house over the portal.
static func _mound(k, c: Vector3, rx: float, rz: float, h: float) -> void:
	var seg = 22
	var rings = 6
	var noise = []
	for i in seg:
		noise.append(k.rng.randf_range(0.9, 1.06))
	var prev = []
	for r in rings + 1:
		var t = float(r) / rings
		var y = h * sin(t * PI * 0.5)
		var f = pow(cos(t * PI * 0.5), 0.55)
		var cur = []
		for i in seg:
			var a = TAU * i / seg
			var nn: float = lerpf(float(noise[i]), 1.0, t)
			cur.append(c + Vector3(cos(a) * rx * f * nn, y, sin(a) * rz * f * nn))
		if r > 0:
			var mat = "stone_rough"
			var tint = Color(0.62, 0.6, 0.58) if r <= 2 else Color(0.72, 0.7, 0.66)
			for i in seg:
				var j = (i + 1) % seg
				_quad2(k, mat, prev[i], prev[j], cur[j], cur[i], tint * k.jitter(0.06))
		prev = cur
	for i in 4:
		var a2 = TAU * i / 4.0 + 1.1
		k.bush(c + Vector3(cos(a2) * rx * 0.45, h * 0.86, sin(a2) * rz * 0.45), 0.45, "herb")
	# rock outcrops on the skirts
	for i in 5:
		var a = TAU * (i + 0.3) / 5.0 + 0.4
		k.box("stone_rough", c + Vector3(cos(a) * rx * 0.9, 0.35, sin(a) * rz * 0.9), Vector3(0.9, 0.7, 0.7), rad_to_deg(a), Color(0.62, 0.6, 0.58), 8.0, 6.0)

static func b08_mine(k, L: int) -> Dictionary:
	var hc = Vector3(1.0, 0, -3.4)
	_mound(k, hc, 4.5, 3.2, [3.6, 3.8, 4.0, 4.2, 4.2][L - 1])
	var px = 1.3
	var pz = 0.0
	k.ground_poly(PackedVector2Array([Vector2(-6.6, -1.8), Vector2(6.4, -1.4), Vector2(6.4, 6.6), Vector2(-6.6, 6.6)]), "path", 0.03)
	# tunnel mouth
	k.box("soot", Vector3(px, 1.25, pz - 0.8), Vector3(2.0, 2.5, 1.5))
	if L <= 2:
		for zz in [pz + 0.4, pz - 0.3]:
			for s in [-1.0, 1.0]:
				k.box("stone", Vector3(px + s * 1.2, 0.15, zz), Vector3(0.5, 0.3, 0.5))
				k.beam("oak", Vector3(px + s * 1.2, 0.3, zz), Vector3(px + s * 1.1, 2.75, zz), 0.36, 0.36)
				k.beam("oak", Vector3(px + s * 1.15, 2.1, zz), Vector3(px + s * 0.6, 2.75, zz), 0.14, 0.14)
			k.beam("oak", Vector3(px - 1.6, 2.85, zz), Vector3(px + 1.6, 2.85, zz), 0.38, 0.42)
		for s in [-1.0, 1.0]:
			k.box("iron", Vector3(px + s * 1.2, 1.4, pz + 0.6), Vector3(0.4, 0.08, 0.04))
	else:
		k.push_at(Vector3(px, 0, pz + 0.3))
		k.arch_wall(Vector3.ZERO, 2.0, 0.6, 1.55, 4.0, 3.2, "stone", "stone_light")
		k.pop()
		k.box("stone_light", Vector3(px, 3.3, pz + 0.3), Vector3(4.2, 0.2, 0.8))
	k.lantern(Vector3(px + 1.45, 2.2, pz + 0.75))
	if L >= 3:
		k.lantern(Vector3(px - 1.45, 2.2, pz + 0.75))
	# rails into the tunnel and out to the yard
	var r1: float = 2.0 if L == 1 else 6.6
	for i in int((r1 - pz + 0.6) / 0.55):
		k.box("dark_oak", Vector3(px, 0.07, pz - 0.5 + i * 0.55), Vector3(1.3, 0.08, 0.2), 0, k.jitter(0.1))
	for s in [-1.0, 1.0]:
		k.box("iron", Vector3(px + s * 0.42, 0.15, (pz - 0.6 + r1) * 0.5), Vector3(0.07, 0.08, r1 - pz + 0.6))
	k.lane(Vector3(px, 0, 2.6), Vector3(px, 0, pz + 0.7), 1.0, 2.0, "rail")
	# open lean-to shed with ore baskets at the left
	var sc = Vector3(-3.6, 0, -0.4)
	var sw = 3.6
	var sd = 3.4
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			var p = sc + Vector3(sx * sw * 0.5, 0, sz * sd * 0.5)
			k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 0.4))
			k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, 2.6, 0), 0.24, 0.24)
	for sz in [-1.0, 1.0]:
		k.beam("oak", sc + Vector3(-sw * 0.5 - 0.2, 2.6, sz * sd * 0.5), sc + Vector3(sw * 0.5 + 0.2, 2.6, sz * sd * 0.5), 0.2, 0.24)
	k.push_at(sc, 90)
	k.gable_roof("shingle", Vector3(0, 2.7, 0), sd + 0.3, sw, 1.3, 0.4)
	k.gable_frame(Vector3(0, 2.7, 0), sd + 0.3, sw, 1.3)
	k.pop()
	for i in (3 if L == 1 else 4):
		var bp = sc + Vector3(-1.0 + (i % 2) * 0.75, 0, 0.6 - (i / 2) * 0.8)
		k.cyl("hay", bp, bp + Vector3(0, 0.55, 0), 0.3, 10, true, k.jitter(0.1), 0.36)
		k.cone("ore", bp + Vector3(0, 0.5, 0), 0.32, 0.25, 8)
	k.crate(sc + Vector3(1.1, 0, 0.9), 0.55)
	k.beam("dark_oak", sc + Vector3(1.4, 0, 0.3), sc + Vector3(1.2, 1.1, 0.1), 0.05, 0.05)
	if L >= 2:
		# ore bins along the right edge and a drainage channel
		for i in 3:
			var bc = Vector3(5.2, 0, 1.6 + i * 1.5)
			k.box("plank", bc + Vector3(0, 0.35, 0), Vector3(1.3, 0.7, 1.3), 0, k.jitter(0.06))
			k.box("ore", bc + Vector3(0, 0.66, 0), Vector3(1.1, 0.12, 1.1), 0, k.jitter(0.1))
		k.box("stone", Vector3(px + 1.2, 0.04, 3.6), Vector3(0.4, 0.1, 6.0))
		k.box("water", Vector3(px + 1.2, 0.08, 3.6), Vector3(0.22, 0.02, 6.0))
		k.barrel(Vector3(px + 1.9, 0, 3.4))
	if L >= 3:
		# winch frame above the portal, jib with a bucket, closed store on the right
		var wy = 3.4
		k.deck(Vector3(px - 2.0, 0, pz - 0.9), Vector3(px + 2.0, 0, pz + 0.5), wy, "plank", false, true, true)
		k.railing(Vector3(px - 2.0, wy, pz + 0.5), Vector3(px + 2.0, wy, pz + 0.5), 0.85)
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(px + s * 0.8, wy, pz - 0.4), Vector3(px + s * 0.8, wy + 1.4, pz - 0.4), 0.2, 0.2)
		k.cyl("oak", Vector3(px - 0.7, wy + 1.0, pz - 0.4), Vector3(px + 0.7, wy + 1.0, pz - 0.4), 0.32, 10)
		k.wheel(Vector3(px + 0.95, wy + 1.0, pz - 0.4), 0.55, Vector3.RIGHT)
		var jb = Vector3(px + 0.3, wy + 1.4, pz - 0.6)
		k.beam("oak", jb, jb + Vector3(0, 1.4, 0), 0.26, 0.26)
		k.beam("oak", jb + Vector3(0, 1.3, 0), jb + Vector3(2.2, 2.0, 2.4), 0.26, 0.28)
		k.cyl("iron", jb + Vector3(2.2, 1.9, 2.3), jb + Vector3(2.2, 1.9, 2.5), 0.25, 10)
		k.cyl("rope", jb + Vector3(2.2, 1.7, 2.4), Vector3(jb.x + 2.2, 1.3, jb.z + 2.4), 0.025, 5, false)
		k.cyl("dark_oak", Vector3(jb.x + 2.2, 0.85, jb.z + 2.4), Vector3(jb.x + 2.2, 1.3, jb.z + 2.4), 0.32, 10, true, k.jitter(0.08), 0.26)
		k.cone("ore", Vector3(jb.x + 2.2, 1.28, jb.z + 2.4), 0.3, 0.2, 8)
		var st = Vector3(px + 3.1, 0, pz - 0.6)
		k.timber_house(st, 1.8, 2.0, 2.4, 0.9, [{"at": 0.9, "w": 0.8, "y0": 0.0, "y1": 1.8, "kind": "door"}], [], [], [], "shingle", "plank", 0.25)
	if L >= 4:
		# timbered head house over the portal with the winch inside
		var hy = 3.4
		var hz0 = pz - 1.0
		k.timber_wall(Vector3(px - 1.9, hy, pz + 0.45), Vector3(px + 1.9, hy, pz + 0.45), 2.0, [{"at": 1.9, "w": 1.4, "y0": 0.4, "y1": 1.6, "kind": "open"}], "plank")
		k.timber_wall(Vector3(px + 1.9, hy, pz + 0.45), Vector3(px + 1.9, hy, hz0 - 0.8), 2.0, [], "plank")
		k.timber_wall(Vector3(px - 1.9, hy, hz0 - 0.8), Vector3(px - 1.9, hy, pz + 0.45), 2.0, [], "plank")
		k.push_at(Vector3(px, 0, (pz + 0.45 + hz0 - 0.8) * 0.5), 90)
		k.gable_roof("shingle", Vector3(0, hy + 2.0, 0), pz + 0.45 - hz0 + 0.8, 3.8, 1.5, 0.35, "plank")
		k.gable_frame(Vector3(0, hy + 2.0, 0), pz + 0.45 - hz0 + 0.8, 3.8, 1.5)
		k.pop()
		# open ore shed on the right
		k.open_shed(Vector3(5.0, 0, -0.9), 2.4, 2.8, 2.4, 0.9, "shingle", 2, 2, false)
	if L == 5:
		k.paving(Vector3(-1.0, 0, 1.0), Vector3(4.2, 0, 6.6), 0.05, 0.5)
		k.lantern(Vector3(-1.6, 2.3, 1.2))
		for i in 2:
			k.box("dark_oak", Vector3(-1.6 + i * 0.9, 0.45, 2.6), Vector3(0.8, 0.5, 1.1))
			k.box("ore", Vector3(-1.6 + i * 0.9, 0.75, 2.6), Vector3(0.7, 0.12, 0.9))
	return {"worker": Vector3(-1.4, 0.0, 3.6)}

# ============================================================== build 54: drawings B01-B27
## Recipes below follow the approved drawings level by level (DRENOVAR-B01..B27, test 8
## visual match). Each keeps the main body of the previous level where the drawings do,
## so an upgrade adds the new parts instead of rebuilding the whole building.

static func _gable_house(k, c: Vector3, lx: float, lz: float, wall: float, rise: float,
		front: Array = [], right: Array = [], roof := "shingle", infill := "plank", plinth := 0.35, left: Array = [], back: Array = []) -> void:
	## Rectangular house with the gable to the street (ridge front-to-back) on a plinth.
	var x0 = c.x - lx * 0.5
	var x1 = c.x + lx * 0.5
	var z0 = c.z - lz * 0.5
	var z1 = c.z + lz * 0.5
	k.box("stone", Vector3(c.x, c.y + plinth * 0.5 - 0.15, c.z), Vector3(lx + 0.2, plinth + 0.3, lz + 0.2), 0, k.jitter(0.04))
	var wy = c.y + plinth
	k.timber_wall(Vector3(x0, wy, z1), Vector3(x1, wy, z1), wall, front, infill)
	k.timber_wall(Vector3(x1, wy, z0), Vector3(x0, wy, z0), wall, back, infill)
	k.timber_wall(Vector3(x0, wy, z0), Vector3(x0, wy, z1), wall, left, infill)
	k.timber_wall(Vector3(x1, wy, z1), Vector3(x1, wy, z0), wall, right, infill)
	k.push_at(Vector3(c.x, 0, c.z), 90)
	k.gable_roof(roof, Vector3(0, wy + wall, 0), lz, lx, rise, 0.4, infill, "dark_oak", Color.WHITE)
	k.gable_frame(Vector3(0, wy + wall, 0), lz, lx, rise)
	k.pop()

static func _oval(cx: float, cz: float, rx: float, rz: float, n := 24) -> PackedVector2Array:
	var pts = PackedVector2Array()
	for i in n:
		var a = TAU * i / n
		pts.append(Vector2(cx + cos(a) * rx, cz + sin(a) * rz))
	return pts

# ---------------------------------------------------------------- B01 Town Hall (ECO-05)
static func b01_hall54(k, L: int) -> Dictionary:
	## I long timber hall, central double door, shuttered windows, oval earth forecourt
	## with a stone border. II central gabled porch with stone steps. III stone ground
	## storey, slate roof, side lean-to wings, roof vents. IV two storeys, tall central
	## gable with arched windows over a stone arch portal, cupola on the ridge. V stone
	## bell tower over the portal, open side arcades, paved square.
	var lx = 8.4
	var lz = 5.0
	var c = Vector3(0, 0, -1.6)
	var front = c.z + lz * 0.5
	var plinth = 0.4
	var wall = 2.8 if L <= 3 else 4.6
	var rise = 2.2 if L <= 3 else 2.4
	var roof = "shingle" if L <= 2 else "slate_roof"
	var win = []
	for x in [0.9, 2.0, lx - 2.0, lx - 0.9]:
		win.append({"at": x, "w": 0.65, "y0": 1.0, "y1": 1.85, "kind": "window"})
	if L >= 4:
		for x in [0.9, 2.0, lx - 2.0, lx - 0.9]:
			win.append({"at": x, "w": 0.6, "y0": 2.9, "y1": 3.9, "kind": "window"})
	win.append({"at": lx * 0.5, "w": 1.8, "y0": 0.0, "y1": 2.3, "kind": "double"})
	k.timber_house(c, lx, lz, plinth + wall, rise, win, [], [{"at": lz * 0.5, "w": 0.6, "y0": 1.0, "y1": 1.8, "kind": "window"}],
		[{"at": lz * 0.5, "w": 0.6, "y0": 1.0, "y1": 1.8, "kind": "window"}], roof, "plank", plinth, 1.7 if L >= 3 else 0.0)
	var ey = plinth + wall
	if L <= 2:
		k.ground_poly(_oval(0, front + 2.0, 3.6, 1.7), "path", 0.03)
		for i in 18:
			var a = TAU * i / 18.0
			if sin(a) < -0.6:
				continue
			k.stone_block(Vector3(cos(a) * 3.7, 0, front + 2.0 + sin(a) * 1.8), Vector3(0.36, 0.14, 0.26), rad_to_deg(-a))
	if L == 1:
		k.box("plank", Vector3(0, plinth * 0.5, front + 0.35), Vector3(2.2, plinth, 0.7))
	if L >= 2:
		# central gabled porch (II-III timber, IV-V stone arch portal) with steps
		var pw = 3.0 if L <= 3 else 3.4
		var ph = 2.9 if L <= 3 else 3.3
		if L <= 3:
			for s in [-1.0, 1.0]:
				k.box("stone", Vector3(s * pw * 0.5, plinth * 0.5 + 0.1, front + 0.9), Vector3(0.5, plinth + 0.2, 0.5))
				k.beam("oak", Vector3(s * pw * 0.5, plinth + 0.2, front + 0.9), Vector3(s * pw * 0.5, plinth + ph, front + 0.9), 0.28, 0.28)
				k.beam("oak", Vector3(s * pw * 0.5, plinth + ph - 0.7, front + 0.9), Vector3(s * pw * 0.25, plinth + ph - 0.05, front + 0.9), 0.12, 0.12)
			k.push_at(Vector3(0, 0, front + 0.5), 90)
			k.gable_roof(roof, Vector3(0, plinth + ph, 0), 1.3, pw + 0.4, 1.2, 0.3, "plank")
			k.gable_frame(Vector3(0, plinth + ph, 0), 1.3, pw + 0.4, 1.2)
			k.pop()
		else:
			k.push_at(Vector3(0, 0, front + 0.35))
			k.arch_wall(Vector3.ZERO, 1.9, 0.6, plinth + 1.6, pw, plinth + ph, "stone_light", "stone_light")
			k.pop()
			k.box("stone_light", Vector3(0, plinth + ph + 0.35, front + 0.35), Vector3(pw - 0.6, 0.7, 0.6))
			k.box("brass", Vector3(0, plinth + ph + 0.35, front + 0.67), Vector3(0.5, 0.5, 0.04), 0, Color.WHITE, 0, 45)
			for s in [-1.0, 1.0]:
				k.lantern(Vector3(s * 2.0, plinth + 1.9, front + 0.2))
		var n = 3 if L <= 3 else 4
		k.stairs(Vector3(0, 0, front + 1.15 + n * 0.32), 2.6, n, plinth / n + 0.02, 0.32, 0, "stone_light")
	if L >= 3:
		# side lean-to wings
		for s in [-1.0, 1.0]:
			var wc = Vector3(s * (lx * 0.5 + 1.0), 0, c.z + 0.2)
			k.box("stone", Vector3(wc.x, 1.0, wc.z), Vector3(2.0, 2.0, 3.6), 0, k.jitter(0.04))
			k.push_at(wc, 90.0 * s)
			k.lean_to(Vector3(0, 0, 0), 3.8, 2.0, 2.1, 2.8, roof, 0)
			k.pop()
			k.window(Vector3(wc.x, 0, wc.z + 1.82), 0.55, 0.9, 1.6, 0)
		if L == 3:
			for x in [-3.0, 3.0]:
				k.box("plank", Vector3(x, ey + 0.6, front - 0.6), Vector3(0.9, 0.6, 0.5))
				_louvre(k, Vector3(x, ey + 0.6, front - 0.33), 0.6, 0.35, 0)
		else:
			# tall central gable with arched windows
			k.push_at(Vector3(0, 0, front - 0.6), 90)
			k.gable_roof(roof, Vector3(0, ey, 0), 2.2, 4.0, 2.0, 0.3, "plank")
			k.gable_frame(Vector3(0, ey, 0), 2.2, 4.0, 2.0)
			k.pop()
			k.box("plank", Vector3(0, ey - 0.8, front + 0.32), Vector3(3.9, 1.6, 0.2))
			for x in [-0.8, 0.0, 0.8]:
				k.box("glass", Vector3(x, ey - 0.7, front + 0.44), Vector3(0.42, 1.1, 0.04))
				k.cyl("glass", Vector3(x, ey - 0.15, front + 0.42), Vector3(x, ey - 0.15, front + 0.46), 0.21, 8)
	if L == 4:
		var cy = ey + rise
		k.box("plank", Vector3(0, cy + 0.35, c.z), Vector3(1.0, 1.0, 1.0))
		for yaw in [0.0, 90.0]:
			_louvre(k, Vector3(0, cy + 0.45, c.z) + Vector3(sin(deg_to_rad(yaw)), 0, cos(deg_to_rad(yaw))) * 0.52, 0.6, 0.6, yaw)
		k.pyramid_roof("slate_roof", Vector3(0, cy + 0.85, c.z), 1.3, 0.9, 0.15)
	if L == 5:
		# stone bell tower over the portal, open arcades on both sides, paved square
		var tz = front - 0.4
		k.box("stone_light", Vector3(0, ey + 1.5, tz), Vector3(2.4, 3.0 + 0.5, 2.2), 0, k.jitter(0.03))
		for s in [-1.0, 1.0]:
			k.box("stone", Vector3(s * 1.05, ey + 4.0, tz), Vector3(0.35, 2.0, 2.0))
		k.box("stone", Vector3(0, ey + 4.0, tz - 0.95), Vector3(2.4, 2.0, 0.3))
		k.box("brass", Vector3(0, ey + 4.0, tz), Vector3(0.6, 0.7, 0.6))
		k.box("stone_light", Vector3(0, ey + 5.1, tz), Vector3(2.6, 0.25, 2.4))
		k.pyramid_roof("slate_roof", Vector3(0, ey + 5.2, tz), 2.6, 2.0, 0.2)
		k.box("glass", Vector3(0, ey + 2.2, tz + 1.12), Vector3(0.6, 1.0, 0.04))
		for s in [-1.0, 1.0]:
			var ax = s * (lx * 0.5 + 1.0)
			for i in 3:
				var p = Vector3(ax + s * 0.9, 0, c.z + 1.6 - i * 1.4)
				k.beam("oak", p, p + Vector3(0, 2.1, 0), 0.2, 0.2)
			k.railing(Vector3(ax + s * 0.9, 0.2, c.z + 1.8), Vector3(ax + s * 0.9, 0.2, c.z - 1.2), 0.7)
		k.paving(Vector3(-5.4, 0, front + 0.2), Vector3(5.4, 0, 6.6), 0.05, 0.6)
		k.paving(Vector3(-1.4, 0, 2.6), Vector3(1.4, 0, 6.6), 0.06, 0.4, "stone")
	return {"worker": Vector3(-4.6, 0.0, 4.6)}

# ---------------------------------------------------------------- B02 House (ECO-04)
static func b02_house54(k, L: int) -> Dictionary:
	## I small plank house, gable to the street under a steep thatch, door on the left,
	## leaded window, lantern. II stone plinth, shutters, woodshed lean-to with logs and
	## a wattle fence on the right. III half-timbered plaster walls, red tile roof,
	## chimney, dormer. IV two storeys with a gabled porch, rain barrel, garden beds.
	## V an oriel bay over the door, flower boxes, garden gate.
	var lx = 4.2
	var lz = 4.6
	var c = Vector3(-0.8, 0, -1.4)
	var front = c.z + lz * 0.5
	var plinth = 0.45
	var wall = 2.5 if L <= 3 else 4.2
	var infill = "plank" if L <= 2 else "plaster"
	var roof = "thatch" if L <= 2 else "clay_roof"
	var fr = [{"at": 1.1, "w": 0.9, "y0": 0.0, "y1": 1.95, "kind": "door"}, {"at": 3.0, "w": 0.8, "y0": 0.95, "y1": 1.75, "kind": "window"}]
	if L >= 4:
		fr.append({"at": 1.1, "w": 0.7, "y0": 2.8, "y1": 3.6, "kind": "window"})
		fr.append({"at": 3.0, "w": 0.7, "y0": 2.8, "y1": 3.6, "kind": "window"})
	_gable_house(k, c, lx, lz, wall, 2.6, fr, [{"at": 2.3, "w": 0.7, "y0": 0.95, "y1": 1.7, "kind": "window"}], roof, infill, plinth)
	var ey = plinth + wall
	k.lantern(Vector3(c.x - lx * 0.5 + 0.35, plinth + 2.0, front + 0.2))
	var n = 1 if L == 1 else 2
	k.stairs(Vector3(c.x - lx * 0.5 + 1.1, 0, front + 0.15 + n * 0.3), 1.2, n, plinth / n, 0.3, 0, "stone" if L >= 2 else "oak")
	if L >= 2:
		# woodshed lean-to on the right with split logs, wattle fence
		k.push_at(Vector3(c.x + lx * 0.5 + 0.8, 0, front - 1.0), 90)
		k.lean_to(Vector3.ZERO, 2.0, 1.6, 1.9, 2.4, "shingle", 2)
		k.pop()
		k.log_pile(Vector3(c.x + lx * 0.5 + 0.9, 0, front - 1.0), 1.6, 3, 0.11, 0)
		k.barrel(Vector3(c.x + lx * 0.5 + 0.5, 0, front + 0.4))
		k.stone_block(Vector3(c.x + lx * 0.5 + 1.0, 0, front + 0.8), Vector3(0.4, 0.4, 0.4), 0, true)
		k.palisade(Vector3(c.x + lx * 0.5 + 1.9, 0, front + 1.6), Vector3(c.x + lx * 0.5 + 1.9, 0, front - 2.6), 0.9, 0.05)
		k.palisade(Vector3(c.x + 0.6, 0, front + 1.8), Vector3(c.x + lx * 0.5 + 1.9, 0, front + 1.6), 0.9, 0.05)
	if L >= 3:
		k.chimney(Vector3(c.x + 0.9, ey + 0.8, c.z - 1.3), 2.6, 0.7)
		# dormer on the right roof slope
		k.push_at(Vector3(c.x + 1.0, ey + 0.6, c.z + 0.3))
		k.box(infill, Vector3(0, 0.5, 0), Vector3(1.0, 1.0, 1.0))
		k.window(Vector3(0.52, 0, 0), 0.5, 0.25, 0.8, 90)
		k.gable_roof(roof, Vector3(0, 1.0, 0), 1.2, 1.2, 0.5, 0.15, infill)
		k.pop()
	if L >= 4:
		# gabled porch over the door, rain barrel, garden beds, stepping stones
		var px = c.x - lx * 0.5 + 1.1
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(px + s * 0.7, plinth, front + 0.9), Vector3(px + s * 0.7, plinth + 2.2, front + 0.9), 0.14, 0.14)
		k.push_at(Vector3(px, 0, front + 0.5), 90)
		k.gable_roof(roof, Vector3(0, plinth + 2.25, 0), 1.0, 1.7, 0.6, 0.15, infill)
		k.pop()
		k.barrel(Vector3(c.x + lx * 0.5 - 0.3, 0, front + 0.35), 0.85, 0.3)
		k.garden_bed(Vector3(c.x + lx * 0.5 + 0.4, 0, front + 0.9), Vector3(c.x + lx * 0.5 + 1.7, 0, front + 1.5), "herb", 2)
		for i in 4:
			k.box("stone_light", Vector3(c.x + 1.2 + i * 0.35, 0.03, front + 1.0 + i * 0.45), Vector3(0.35, 0.06, 0.3), i * 20.0)
	if L == 5:
		# oriel bay over the porch, flower boxes, garden gate
		var ox = c.x + 0.9
		k.box(infill, Vector3(ox, plinth + 3.3, front + 0.35), Vector3(1.3, 1.1, 0.7))
		k.box("glass", Vector3(ox, plinth + 3.35, front + 0.71), Vector3(1.0, 0.7, 0.04))
		k.pyramid_roof("shingle", Vector3(ox, plinth + 3.85, front + 0.35), 1.4, 0.5, 0.1, false)
		for x in [c.x + 1.0, c.x - 0.8]:
			k.box("plank", Vector3(x, plinth + 0.9, front + 0.2), Vector3(0.8, 0.18, 0.2))
			k.bush(Vector3(x, plinth + 0.95, front + 0.2), 0.18, "flower")
		k.box("oak", Vector3(c.x + 0.9, 0.45, front + 1.8), Vector3(0.9, 0.9, 0.06))
	return {"worker": Vector3(-3.6, 0.0, 3.0)}

# ---------------------------------------------------------------- B06 Lumber Camp (RES-01)
static func b06_lumber54(k, L: int) -> Dictionary:
	## I open gabled work shed (workbench, tools, firewood) with a sawhorse in front and a
	## log stack at the right. II the left half closed into a cabin with a door and a
	## window, the open shed continues on the right. III raised loading deck with a ramp
	## at the front right. IV gantry hoist on the deck lifting a log bundle, longer
	## lean-to. V dormer and chimney on the cabin, long open log store at the right.
	var c = Vector3(-1.0, 0, -1.8)
	var lx = 6.4
	var lz = 3.8
	var front = c.z + lz * 0.5
	var h = 2.6
	# posts and gable roof (ridge along the street)
	for i in 4:
		var x = c.x - lx * 0.5 + lx * i / 3.0
		for z in [c.z - lz * 0.5, front]:
			k.box("stone", Vector3(x, 0.15, z), Vector3(0.42, 0.3, 0.42))
			k.beam("oak", Vector3(x, 0.3, z), Vector3(x, h, z), 0.26, 0.26)
			if i < 3:
				k.beam("oak", Vector3(x, h - 0.6, z), Vector3(x + 0.6, h - 0.02, z), 0.12, 0.12)
			if i > 0:
				k.beam("oak", Vector3(x, h - 0.6, z), Vector3(x - 0.6, h - 0.02, z), 0.12, 0.12)
	for z in [c.z - lz * 0.5, front]:
		k.beam("oak", Vector3(c.x - lx * 0.5 - 0.2, h, z), Vector3(c.x + lx * 0.5 + 0.2, h, z), 0.22, 0.26)
	k.gable_roof("shingle", Vector3(c.x, h + 0.1, c.z), lx, lz, 1.5, 0.4)
	k.gable_frame(Vector3(c.x, h + 0.1, c.z), lx, lz, 1.5)
	k.box("plank", Vector3(c.x, 1.3, c.z - lz * 0.5 + 0.05), Vector3(lx, 2.6, 0.1))
	var wx = c.x + (0.6 if L == 1 else 1.4)
	k.workbench(Vector3(wx, 0, c.z - 0.9), 1.8, 0)
	for i in 3:
		k.beam("iron", Vector3(wx - 0.6 + i * 0.6, 1.5, c.z - lz * 0.5 + 0.12), Vector3(wx - 0.6 + i * 0.6, 2.0, c.z - lz * 0.5 + 0.12), 0.05, 0.04)
	k.log_pile(Vector3(c.x + lx * 0.5 - 0.6, 0, c.z - 0.6), 1.2, 3, 0.1, 0)
	k.barrel(Vector3(wx + 1.3, 0, c.z - 0.4))
	k.sawhorse(Vector3(-4.6, 0, 2.6), 20)
	k.log_pile(Vector3(3.6, 0, 3.0), 3.0, 3 if L == 1 else 4, 0.22, 90)
	if L >= 2:
		# the left half closed into a cabin
		var x0 = c.x - lx * 0.5
		var xm = c.x - lx * 0.5 + lx / 3.0 * 1.0 + 0.6
		k.box("stone", Vector3((x0 + xm) * 0.5, 0.2, c.z), Vector3(xm - x0, 0.4, lz), 0, k.jitter(0.04))
		k.timber_wall(Vector3(x0, 0.4, front), Vector3(xm, 0.4, front), h - 0.4, [{"at": 0.8, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}, {"at": 2.1, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}], "plank")
		k.timber_wall(Vector3(xm, 0.4, front), Vector3(xm, 0.4, c.z - lz * 0.5), h - 0.4, [], "plank")
		k.timber_wall(Vector3(x0, 0.4, c.z - lz * 0.5), Vector3(x0, 0.4, front), h - 0.4, [], "plank")
		k.lantern(Vector3(x0 + 0.2, 2.0, front + 0.2))
		# lean-to continuing the open shed on the right
		k.push_at(Vector3(c.x + lx * 0.5 + 0.9, 0, c.z), 90)
		k.lean_to(Vector3.ZERO, lz, 1.8, 2.0, h - 0.1, "shingle", 2)
		k.pop()
		k.log_pile(Vector3(c.x + lx * 0.5 + 0.9, 0, c.z), 2.4, 2, 0.14, 0)
	if L >= 3:
		# raised loading deck with a ramp at the front right
		var dy = 0.6
		k.deck(Vector3(0.4, 0, front + 0.2), Vector3(4.6, 0, front + 2.6), dy, "plank", true, true, true)
		for x in [0.5, 4.5]:
			k.box("stone", Vector3(x, 0.35, front + 2.5), Vector3(0.4, 0.7, 0.4))
		k.ramp(Vector3(-0.8, 0, front + 3.4), Vector3(0.4, dy, front + 1.8), 1.4, "plank")
		k.cart(Vector3(2.4, dy, front + 1.4), 90, "logs")
	if L >= 4:
		# gantry hoist on the deck with a log bundle on the rope
		var gx = 2.6
		var gz = front + 1.0
		for x in [gx - 1.2, gx + 1.2]:
			k.beam("oak", Vector3(x, 0.6, gz), Vector3(x, 4.6, gz), 0.26, 0.26)
		k.beam("oak", Vector3(gx - 1.5, 4.6, gz), Vector3(gx + 1.5, 4.6, gz), 0.26, 0.3)
		k.hook_hoist(Vector3(gx - 0.3, 4.45, gz), 2.2)
		for i in 3:
			k.cyl("log", Vector3(gx - 1.0, 1.8 + i * 0.22, gz - 0.2 + i * 0.1), Vector3(gx + 0.4, 1.8 + i * 0.22, gz - 0.2 + i * 0.1), 0.12, 8)
		k.wheel(Vector3(gx + 1.2, 1.5, gz + 0.15), 0.5, Vector3.FORWARD)
	if L == 5:
		k.chimney(Vector3(c.x - lx * 0.5 + 1.2, h + 0.5, c.z - 0.6), 2.0, 0.55)
		k.push_at(Vector3(c.x - lx * 0.5 + 1.0, h + 0.3, c.z + 0.8))
		k.box("plank", Vector3(0, 0.45, 0), Vector3(1.1, 0.9, 1.0))
		k.window(Vector3(0, 0, 0.52), 0.5, 0.2, 0.7, 0)
		k.push_at(Vector3(0, 0.9, 0), 90)
		k.gable_roof("shingle", Vector3.ZERO, 1.2, 1.3, 0.5, 0.15, "plank")
		k.pop()
		k.pop()
		# long open log store at the right
		k.open_shed(Vector3(5.2, 0, -1.4), 2.2, 5.0, 2.6, 0.8, "shingle", 2, 4, false)
		for i in 3:
			k.log_pile(Vector3(5.2, 0, -3.0 + i * 1.5), 1.6, 3, 0.13, 90)
		k.deck(Vector3(4.6, 0, front + 0.2), Vector3(6.4, 0, front + 2.6), 0.6, "plank", true, true, true)
	return {"worker": Vector3(-4.0, 0.0, 4.2)}

static func _fence_ring(k, cx: float, cz: float, rx: float, rz: float, gate_deg: float, gap_deg: float, stone := false, h := 0.85) -> void:
	## Oval rail fence round a yard with a gate gap at gate_deg (90 = front).
	var n = 22
	for i in n:
		var a0 = 360.0 * i / n
		var a1 = 360.0 * (i + 1) / n
		var mid = (a0 + a1) * 0.5
		if absf(angle_difference(deg_to_rad(mid), deg_to_rad(gate_deg))) < deg_to_rad(gap_deg):
			continue
		var p0 = Vector3(cx + cos(deg_to_rad(a0)) * rx, 0, cz + sin(deg_to_rad(a0)) * rz)
		var p1 = Vector3(cx + cos(deg_to_rad(a1)) * rx, 0, cz + sin(deg_to_rad(a1)) * rz)
		k.fence(p0, p1, h)
		if stone and i % 3 == 0:
			k.box("stone", p0 + Vector3(0, h * 0.55, 0), Vector3(0.36, h * 1.1, 0.36), 0, k.jitter(0.05))

static func _gate(k, p: Vector3, w: float, yaw := 0.0, open := 0.0) -> void:
	k.push_at(p, yaw)
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(s * w * 0.5, 0, 0), Vector3(s * w * 0.5, 1.15, 0), 0.14, 0.14)
	k.push_at(Vector3(-w * 0.5, 0, 0), -open)
	for y in [0.3, 0.75]:
		k.box("oak", Vector3(w * 0.5, y, 0), Vector3(w, 0.08, 0.05))
	k.beam("oak", Vector3(0.05, 0.25, 0), Vector3(w - 0.05, 0.8, 0), 0.06, 0.05)
	k.pop()
	k.pop()

# ---------------------------------------------------------------- B09 Farm (RES-04)
static func b09_farm54(k, L: int) -> Dictionary:
	## I plank cabin at the back, fenced kitchen garden with bean poles at the front
	## left, hand cart, oval rail fence with a gate. II half-timbered house with a front
	## cross gable and chimney, thatched open shed at the left. III dormer with flower
	## box, chicken coop at the front right. IV timbered work bay instead of the thatched
	## shed, root cellar with a low roof at the front right, stone fence piers. V water
	## tower on the right and an open produce stall.
	var c = Vector3(0.6, 0, -2.6)
	var lx = 5.2
	var lz = 3.6
	var front = c.z + lz * 0.5
	var plinth = 0.5
	var infill = "plank" if L == 1 else "plaster"
	k.ground_poly(_oval(0, 0.4, 6.2, 5.6), "earth", 0.025)
	k.timber_house(c, lx, lz, plinth + 2.6, 1.8, [{"at": 1.0, "w": 0.65, "y0": 0.9, "y1": 1.6, "kind": "window"},
		{"at": 3.0, "w": 0.9, "y0": 0.0, "y1": 1.95, "kind": "door"}, {"at": 4.3, "w": 0.65, "y0": 0.9, "y1": 1.6, "kind": "window"}],
		[], [], [{"at": 1.8, "w": 0.6, "y0": 0.9, "y1": 1.6, "kind": "window"}], "shingle", infill, plinth)
	var ey = plinth + 2.6
	k.stairs(Vector3(c.x - lx * 0.5 + 3.0, 0, front + 0.15 + 2 * 0.3), 1.2, 2, plinth / 2.0, 0.3, 0, "stone")
	# kitchen garden with bean poles
	k.garden_bed(Vector3(-5.0, 0, 1.2), Vector3(-2.6, 0, 2.6), "leaves", 3)
	k.garden_bed(Vector3(-2.2, 0, 1.2), Vector3(-0.4, 0, 2.6), "herb", 3)
	k.garden_bed(Vector3(-5.0, 0, 3.0), Vector3(-2.6, 0, 4.2), "flower", 2)
	for i in 3:
		var bp = Vector3(-5.4 + i * 0.5, 0, 0.6)
		k.beam("oak", bp, bp + Vector3(0.2, 1.8, 0.0), 0.05, 0.05)
		k.bush(bp + Vector3(0.1, 0.6, 0), 0.25)
	k.road(Vector3(0.0, 0, 6.4), Vector3(0.2, 0, front + 0.6), 1.3, "path", 0.03, 0.2)
	_fence_ring(k, 0, 0.6, 6.4, 5.8, 90.0, 9.0, L >= 4)
	_gate(k, Vector3(0, 0, 6.4), 1.3, 0, 25.0)
	k.cart(Vector3(3.4, 0, front + 1.2), 120, "")
	if L >= 2:
		k.chimney(Vector3(c.x + 1.6, ey + 0.6, c.z - 0.6), 2.0, 0.6)
		# front cross gable on the right half with the farm banner
		k.push_at(Vector3(c.x + 1.2, 0, front - 0.2), 90)
		k.gable_roof("shingle", Vector3(0, ey, 0), 1.4, 2.6, 1.4, 0.3, infill)
		k.gable_frame(Vector3(0, ey, 0), 1.4, 2.6, 1.4)
		k.pop()
		k.box(infill, Vector3(c.x + 1.2, ey - 0.6, front + 0.35), Vector3(2.5, 1.2, 0.3))
		k.banner(Vector3(c.x + 1.2, ey + 0.8, front + 0.55), 0.45, 0.6, "cloth_red")
		if L <= 3:
			# thatched open shed at the left with tools and barrels
			var sc = Vector3(c.x - lx * 0.5 - 1.3, 0, c.z + 0.2)
			k.open_shed(sc, 2.2, 3.0, 2.2, 0.9, "thatch", 2, 2, false)
			k.barrel(sc + Vector3(-0.5, 0, 0.3)); k.workbench(sc + Vector3(0.2, 0, -0.9), 1.4, 0)
	if L >= 3:
		k.push_at(Vector3(c.x - 1.0, ey + 0.4, c.z + 0.6))
		k.box(infill, Vector3(0, 0.45, 0), Vector3(1.1, 0.9, 1.0))
		k.window(Vector3(0, 0, 0.52), 0.55, 0.2, 0.75, 0)
		k.box("plank", Vector3(0, 0.12, 0.62), Vector3(0.8, 0.14, 0.2))
		k.bush(Vector3(0, 0.2, 0.62), 0.18, "flower")
		k.push_at(Vector3(0, 0.9, 0), 90)
		k.gable_roof("shingle", Vector3.ZERO, 1.2, 1.3, 0.5, 0.15, infill)
		k.pop()
		k.pop()
		# chicken coop at the front right
		var cc = Vector3(3.6, 0, 2.6)
		k.box("plank", cc + Vector3(0, 0.55, 0), Vector3(1.2, 0.7, 0.9))
		k.gable_roof("shingle", cc + Vector3(0, 0.9, 0), 1.3, 1.0, 0.4, 0.1)
		k.fence(cc + Vector3(-0.6, 0, 0.5), cc + Vector3(-0.6, 0, 1.6), 0.6)
		k.fence(cc + Vector3(-0.6, 0, 1.6), cc + Vector3(0.6, 0, 1.6), 0.6)
		k.barrel(Vector3(c.x + 2.6, 0, front + 0.4))
	if L >= 4:
		# timbered work bay at the left (gable to the street), root cellar at the right
		var sc = Vector3(c.x - lx * 0.5 - 1.5, 0, c.z + 0.3)
		_open_shed_z(k, sc, 2.8, 3.2, 2.4)
		k.cart(sc + Vector3(0, 0, 0.4), 0, "")
		k.box("stone", Vector3(c.x + lx * 0.5 + 0.8, 0.6, c.z), Vector3(1.4, 1.2, 2.4), 0, k.jitter(0.04))
		k.push_at(Vector3(c.x + lx * 0.5 + 0.8, 0, c.z), 90)
		k.gable_roof("shingle", Vector3(0, 1.4, 0), 2.6, 1.6, 0.8, 0.2)
		k.pop()
		var rc = Vector3(3.0, 0, 3.4)
		k.push_at(rc, -20)
		k.box("stone", Vector3(0, 0.25, 0), Vector3(2.4, 0.5, 1.4), 0, k.jitter(0.04))
		k.lean_to(Vector3(0, 0, 0), 2.4, 1.4, 0.7, 1.2, "shingle", 2)
		k.door(Vector3(0, 0, 0.72), 0.8, 0.7, 0, 0.0)
		k.pop()
	if L == 5:
		# water tower and an open produce stall on the right
		var t = Vector3(5.2, 0, -1.6)
		for sx in [-0.5, 0.5]:
			for sz in [-0.5, 0.5]:
				k.beam("dark_oak", t + Vector3(sx, 0, sz), t + Vector3(sx * 0.8, 2.2, sz * 0.8), 0.14, 0.14)
		k.cyl("oak", t + Vector3(0, 2.2, 0), t + Vector3(0, 3.6, 0), 0.75, 12, true, k.jitter(0.08))
		k.cone("shingle", t + Vector3(0, 3.6, 0), 0.95, 0.7, 10)
		k.open_shed(Vector3(4.6, 0, 1.0), 2.0, 2.0, 2.2, 0.7, "shingle", 2, 2, true)
		k.table(Vector3(4.6, 0, 1.0), 1.4, 0.7, 0.85)
		for i in 3:
			k.box(["hay", "herb", "flower"][i], Vector3(4.2 + i * 0.4, 0.92, 1.0), Vector3(0.3, 0.14, 0.4))
	return {"worker": Vector3(-1.6, 0.0, 4.6)}

# ---------------------------------------------------------------- B10 Hunting Camp (RES-05)
static func _tent_a(k, c: Vector3, w: float, d: float, h: float, yaw := 0.0) -> void:
	## A-frame canvas tent with a teal hem, door flap facing local +Z.
	k.push_at(c, yaw)
	for z in [-d * 0.5, d * 0.5]:
		k.beam("oak", Vector3(-w * 0.5 - 0.1, 0, z), Vector3(0, h + 0.25, z), 0.07, 0.07)
		k.beam("oak", Vector3(w * 0.5 + 0.1, 0, z), Vector3(0, h + 0.25, z), 0.07, 0.07)
	for s in [-1.0, 1.0]:
		k.next_piece()
		_quad2(k, "canvas", Vector3(s * w * 0.5, 0.05, -d * 0.5), Vector3(s * w * 0.5, 0.05, d * 0.5), Vector3(0, h, d * 0.5), Vector3(0, h, -d * 0.5))
		k.box("cloth_teal", Vector3(s * w * 0.46, 0.2, 0), Vector3(0.04, 0.1, d), 0, Color.WHITE, 0, -s * rad_to_deg(atan2(h, w * 0.5)) * 0.0)
	k.next_piece()
	_tri2(k, "canvas", Vector3(-w * 0.5, 0.05, -d * 0.5), Vector3(w * 0.5, 0.05, -d * 0.5), Vector3(0, h, -d * 0.5))
	_tri2(k, "canvas", Vector3(-w * 0.5, 0.05, d * 0.5), Vector3(-w * 0.1, 0.05, d * 0.5), Vector3(0, h, d * 0.5))
	_tri2(k, "canvas", Vector3(w * 0.5, 0.05, d * 0.5), Vector3(w * 0.25, 0.05, d * 0.75), Vector3(0, h, d * 0.5))
	k.pop()

static func _drying_rack(k, c: Vector3, w := 1.6, yaw := 0.0, hides := false) -> void:
	k.push_at(c, yaw)
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(s * w * 0.5 - 0.3, 0, 0.3), Vector3(s * w * 0.5, 1.5, 0), 0.08, 0.08)
		k.beam("oak", Vector3(s * w * 0.5 + 0.3 * s * 0.0, 0, -0.3), Vector3(s * w * 0.5, 1.5, 0), 0.08, 0.08)
	k.beam("oak", Vector3(-w * 0.5 - 0.1, 1.45, 0), Vector3(w * 0.5 + 0.1, 1.45, 0), 0.08, 0.08)
	for i in 3:
		var x = -w * 0.3 + i * w * 0.3
		if hides:
			k.box("parchment", Vector3(x, 1.0, 0), Vector3(0.4, 0.8, 0.03), 0, Color(0.8, 0.62, 0.42))
		else:
			k.box("cloth_red", Vector3(x, 1.15, 0), Vector3(0.14, 0.5, 0.06), 0, Color(0.9, 0.6, 0.6))
	k.pop()

static func b10_hunt54(k, L: int) -> Dictionary:
	## I open gabled shed with a table and an antler banner at the left, canvas tent at
	## the right, drying racks with meat and hides in front. II a log cabin at the back
	## right and a lean-to beside the shed. III a pointed palisade round the camp with a
	## gate and lanterns. IV a second workshop shed and a covered rack inside the yard.
	## V a larger cabin with a porch and a store shed at the right.
	k.ground_poly(_oval(0, 0, 6.3, 5.8), "earth", 0.025)
	var sc = Vector3(-3.4, 0, -1.6)
	_open_shed_z(k, sc, 3.2, 3.2, 2.5, "cloth_wine")
	k.table(sc + Vector3(0, 0, 0.2), 1.6, 0.8, 0.85)
	k.bench(sc + Vector3(0, 0, 1.0), 1.4, 0)
	k.lantern(sc + Vector3(0.6, 1.0, 0.2))
	k.barrel(sc + Vector3(1.2, 0, -1.0))
	_tent_a(k, Vector3(0.6, 0, -1.4), 2.2, 2.6, 2.0, -15.0)
	_drying_rack(k, Vector3(-1.4, 0, 2.6), 1.6, 0, true)
	_drying_rack(k, Vector3(1.2, 0, 3.0), 1.6, -10, false)
	if L >= 2:
		var cab = Vector3(3.6, 0, -3.4)
		_gable_house(k, cab, 2.6, 2.6, 2.2, 1.6, [{"at": 1.3, "w": 0.8, "y0": 0.0, "y1": 1.8, "kind": "door"}],
			[{"at": 1.3, "w": 0.5, "y0": 0.9, "y1": 1.4, "kind": "window"}], "shingle", "plank", 0.45)
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(cab.x + s * 0.2, 0.45 + 2.2 + 1.6 - 0.1, cab.z + 1.5), Vector3(cab.x - s * 0.5, 0.45 + 2.2 + 2.3, cab.z + 1.5), 0.08, 0.08)
		k.log_pile(Vector3(cab.x + 1.8, 0, cab.z), 1.4, 2, 0.12, 0)
		k.push_at(Vector3(sc.x + 2.6, 0, sc.z - 0.2), 0)
		k.lean_to(Vector3.ZERO, 2.0, 2.0, 2.0, 2.4, "shingle", 2)
		k.pop()
		k.box("parchment", Vector3(sc.x + 2.6, 1.2, sc.z - 1.15), Vector3(0.9, 0.9, 0.03), 0, Color(0.8, 0.62, 0.42))
	if L >= 3:
		# pointed palisade round the camp with a gate
		var n = 26
		for i in n:
			var a0 = TAU * i / n
			var a1 = TAU * (i + 1) / n
			var mid = (a0 + a1) * 0.5
			if absf(angle_difference(mid, PI * 0.5)) < 0.16:
				continue
			k.palisade(Vector3(cos(a0) * 6.2, 0, sin(a0) * 5.7), Vector3(cos(a1) * 6.2, 0, sin(a1) * 5.7), 1.4, 0.09)
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(s * 0.85, 0, 5.75), Vector3(s * 0.85, 2.1, 5.75), 0.22, 0.22)
			k.lantern(Vector3(s * 0.85, 1.8, 5.95))
		k.beam("oak", Vector3(-1.0, 2.0, 5.75), Vector3(1.0, 2.0, 5.75), 0.18, 0.2)
		k.door(Vector3(0.4, 0, 5.75), 0.8, 1.5, 0, 0.0)
	if L >= 4:
		var ws = Vector3(2.0, 0, 1.4)
		k.open_shed(ws, 2.0, 1.8, 2.1, 0.7, "shingle", 2, 2, true)
		k.workbench(ws + Vector3(0, 0, -0.3), 1.4, 0)
		_drying_rack(k, Vector3(-3.6, 0, 3.4), 1.4, 15, true)
	if L == 5:
		var cab = Vector3(3.6, 0, -3.4)
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(cab.x + s * 1.0, 0.45, cab.z + 1.9), Vector3(cab.x + s * 1.0, 2.4, cab.z + 1.9), 0.14, 0.14)
		k.push_at(Vector3(cab.x, 0, cab.z + 1.55), 90)
		k.gable_roof("shingle", Vector3(0, 2.45, 0), 0.9, 2.4, 0.6, 0.15)
		k.pop()
		k.open_shed(Vector3(5.0, 0, 0.0), 1.6, 2.4, 2.0, 0.6, "shingle", 2, 2, false)
		k.crate(Vector3(5.0, 0, -0.4)); k.barrel(Vector3(5.0, 0, 0.6))
	return {"worker": Vector3(-0.4, 0.0, 4.6)}

# ---------------------------------------------------------------- B11 Infantry Barracks (MIL-01)
static func _dummy_row(k, from: Vector3, to: Vector3, n: int) -> void:
	for i in n:
		k.dummy(from.lerp(to, (i + 0.5) / n), 0)

static func b11_barracks54(k, L: int) -> Dictionary:
	## I long timber barracks (ridge along the street) with a front gable at the left
	## over a double door and crossed-swords banner, shuttered windows, weapon racks and a
	## fenced training yard with dummies at the front right. II stone plinth, a lean-to
	## armoury at the right end. III two storeys with a stone ground floor. IV an L-shaped
	## wing round the back and right of a larger paved yard with a dummy line. V corner
	## turrets at the front, an arcade on the wing, red-hung yard.
	var c = Vector3(-1.2, 0, -3.0)
	var lx = 8.4
	var lz = 4.0
	var front = c.z + lz * 0.5
	var plinth = 0.55
	var wall = 2.8 if L <= 2 else 4.6
	var ops = [{"at": 1.6, "w": 1.6, "y0": 0.0, "y1": 2.2, "kind": "double"}]
	for x in [3.4, 4.6, 5.9, 7.2]:
		ops.append({"at": x, "w": 0.6, "y0": 1.0, "y1": 1.7, "kind": "window"})
	if L >= 3:
		for x in [1.6, 3.4, 4.6, 5.9, 7.2]:
			ops.append({"at": x, "w": 0.6, "y0": 2.9, "y1": 3.7, "kind": "window"})
	k.timber_house(c, lx, lz, plinth + wall, 2.0, ops, [], [], [{"at": 2.0, "w": 0.6, "y0": 1.0, "y1": 1.7, "kind": "window"}],
		"shingle", "plank", plinth, 1.8 if L >= 3 else 0.0)
	var ey = plinth + wall
	var gx = c.x - lx * 0.5 + 1.6
	k.push_at(Vector3(gx, 0, front - 0.3), 90)
	k.gable_roof("shingle", Vector3(0, ey, 0), 1.6, 3.0, 1.6, 0.3, "plank")
	k.gable_frame(Vector3(0, ey, 0), 1.6, 3.0, 1.6)
	k.pop()
	k.box("plank", Vector3(gx, ey - 0.5, front + 0.3), Vector3(2.9, 1.0, 0.3))
	k.banner(Vector3(gx, ey + 1.0, front + 0.6), 0.55, 0.85, "cloth_wine")
	k.stairs(Vector3(gx, 0, front + 0.15 + 3 * 0.3), 2.0, 3, plinth / 3.0, 0.3, 0, "stone")
	k.weapon_rack(Vector3(gx + 1.8, 0, front + 0.5), 1.4, 0)
	# training yard
	var yx0 = c.x - lx * 0.5 + 3.2
	var yx1 = 6.2 if L <= 3 else 6.4
	var yz0 = front + 0.4
	var yz1 = 6.4
	if L >= 4:
		yx0 = c.x - lx * 0.5 + 3.0
	k.ground(Vector3(yx0, 0, yz0), Vector3(yx1, 0, yz1), "sand", 0.03)
	if L <= 4:
		k.fence(Vector3(yx0, 0, yz1), Vector3(yx1, 0, yz1), 0.85)
		k.fence(Vector3(yx1, 0, yz1), Vector3(yx1, 0, yz0 if L <= 3 else -1.0), 0.85)
		k.fence(Vector3(yx0, 0, yz0 + 1.0), Vector3(yx0, 0, yz1), 0.85)
	_dummy_row(k, Vector3(yx0 + 1.0, 0, 2.6), Vector3(yx1 - 0.6, 0, 2.6), 2 if L <= 2 else (3 if L == 3 else 6))
	if L <= 2:
		k.beam("oak", Vector3(yx1 - 0.8, 0, 4.4), Vector3(yx1 - 0.8, 2.0, 4.4), 0.12, 0.12)
		k.beam("oak", Vector3(yx1 - 0.8, 2.0, 4.4), Vector3(yx1 - 0.2, 2.0, 4.4), 0.1, 0.1)
		k.hook_hoist(Vector3(yx1 - 0.3, 1.95, 4.4), 0.6)
	if L >= 3:
		for i in 3:
			k.beam("oak", Vector3(yx0 + 1.0 + i * 1.3, 0.4, 4.8), Vector3(yx0 + 1.6 + i * 1.3, 0.4, 4.8), 0.08, 0.08)
	if L >= 2 and L <= 3:
		k.push_at(Vector3(c.x + lx * 0.5 + 0.9, 0, c.z + 0.3), 90)
		k.lean_to(Vector3.ZERO, lz - 0.6, 1.8, 2.2, 2.8, "shingle", 2)
		k.pop()
		k.weapon_rack(Vector3(c.x + lx * 0.5 + 0.9, 0, c.z + 0.3), 1.4, 90)
	if L >= 4:
		# L-shaped wing round the right of the yard, galleries facing it
		var wc = Vector3(5.3, 0, -0.2)
		k.timber_house(wc, 2.4, 5.6, plinth + 2.8, 1.5, [], [], [], [], "shingle", "plank", plinth, 1.2)
		k.push_at(Vector3(wc.x - 1.6, 0, wc.z), -90)
		k.lean_to(Vector3.ZERO, 5.6, 1.4, 2.4, 3.2, "shingle", 4 if L == 4 else 6)
		k.pop()
		k.paving(Vector3(yx0, 0, yz0), Vector3(3.2, 0, yz1), 0.05, 0.6, "stone_light")
		for i in 4:
			k.box("cloth_red", Vector3(-3.0 + i * 1.8, 0.4, yz1 - 0.05), Vector3(0.18, 0.5, 0.02))
		k.fence(Vector3(yx0, 0, yz1), Vector3(3.5, 0, yz1), 0.85)
	if L == 5:
		for x in [c.x - lx * 0.5 - 0.2, c.x - lx * 0.5 + 3.0]:
			var tp = Vector3(x, 0, front + 0.6)
			k.cyl("stone", tp, tp + Vector3(0, 5.2, 0), 0.75, 8, true, k.jitter(0.04))
			k.cone("slate_roof", tp + Vector3(0, 5.2, 0), 0.95, 1.6, 8)
			k.flag_pole(tp + Vector3(0, 6.6, 0), 1.2, "cloth_wine")
	return {"worker": Vector3(-5.0, 0.0, 3.0)}

static func _target(k, p: Vector3, r := 0.5, yaw := 0.0) -> void:
	k.push_at(p, yaw)
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(s * 0.35, 0, -0.25), Vector3(s * 0.25, r * 2.2, 0.0), 0.07, 0.07)
	var rings = [["hay", r], ["cloth_red", r * 0.8], ["cloth_teal", r * 0.55], ["cloth_wine", r * 0.3], ["brass", r * 0.12]]
	for i in rings.size():
		k.cyl(rings[i][0], Vector3(0, r * 1.3, 0.04 + i * 0.012), Vector3(0, r * 1.3, 0.05 + i * 0.012), rings[i][1], 16)
	k.pop()

static func _mound_berm(k, x0: float, x1: float, z0: float, z1: float, h: float) -> void:
	## Turfed earth berm along X between z0 (back) and z1 (front), sloping to the front.
	k.push(Transform3D(Basis(Vector3.UP, PI * 0.5), Vector3.ZERO))
	k.extrude("leaves", PackedVector2Array([Vector2(-z1, 0), Vector2(-z0, 0), Vector2(-z0 - 0.6, h), Vector2(-z1 + 1.4, h)]), x0, x1, Color(0.85, 0.95, 0.7))
	k.pop()

# ---------------------------------------------------------------- B12 Archery Range (MIL-02)
static func b12_range54(k, L: int) -> Dictionary:
	## I gabled bow shed with a banner at the front left, a turfed earth berm at the back
	## with three targets, a rail fence round the range. II a covered shooting line with
	## posts and stools along the front. III a timber backstop on the berm and a small
	## hut on the berm top with steps. IV the shooting line under three gables, more
	## targets. V a larger lodge with a chimney on the berm.
	var sc = Vector3(-4.8, 0, 0.6)
	_gable_house(k, sc, 2.0, 2.6, 2.1, 1.4, [{"at": 1.0, "w": 1.2, "y0": 0.0, "y1": 1.9, "kind": "open"}], [], "shingle", "plank", 0.3)
	k.box("soot", sc + Vector3(0, 1.2, 1.1), Vector3(1.1, 1.8, 0.1))
	k.weapon_rack(sc + Vector3(0, 0.3, 0.6), 1.2, 0)
	k.banner(sc + Vector3(1.15, 2.2, 0.9), 0.4, 0.8, "cloth_wine", 90)
	k.barrel(sc + Vector3(0.6, 0, 1.7))
	var bh = 1.5 if L <= 2 else 2.6
	_mound_berm(k, -3.6, 6.2, -6.4, -2.0, bh)
	var tz = -2.2
	var nt = 3 if L <= 3 else 4
	for i in nt:
		_target(k, Vector3(-2.0 + i * (7.0 / nt), 0, tz), 0.5)
	k.ground(Vector3(-3.6, 0, -2.0), Vector3(6.2, 0, 6.4), "earth", 0.025, Color(0.9, 0.95, 0.8))
	for i in nt:
		k.box("sand", Vector3(-2.0 + i * (7.0 / nt), 0.04, 1.6), Vector3(0.12, 0.02, 6.6))
	k.fence(Vector3(-3.6, 0, 6.4), Vector3(6.2, 0, 6.4), 0.8)
	k.fence(Vector3(6.2, 0, 6.4), Vector3(6.2, 0, -2.0), 0.8)
	if L >= 3:
		# timber backstop on the berm
		for i in 9:
			k.cyl("log", Vector3(-3.4, 0.4 + i * 0.28, -2.6), Vector3(6.0, 0.4 + i * 0.28, -2.6), 0.15, 8)
		for x in [-3.2, -0.6, 2.0, 4.6]:
			k.beam("dark_oak", Vector3(x, 0, -2.4), Vector3(x, 3.2, -2.4), 0.22, 0.22)
		var hp = Vector3(3.6, bh, -4.8) if L <= 4 else Vector3(2.6, bh, -4.9)
		if L <= 4:
			_gable_house(k, hp, 2.2, 2.0, 2.0, 1.3, [{"at": 1.1, "w": 0.8, "y0": 0.0, "y1": 1.8, "kind": "door"}], [], "shingle", "plank", 0.2)
			k.open_shed(hp + Vector3(1.8, 0, 0), 1.2, 1.8, 1.8, 0.5, "shingle", 2, 2, true)
		else:
			_gable_house(k, hp, 4.6, 2.6, 2.4, 1.6, [{"at": 1.0, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}, {"at": 2.3, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}, {"at": 3.6, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}], [], "shingle", "plank", 0.3)
			k.chimney(hp + Vector3(1.4, 2.7, -0.6), 2.4, 0.55)
		k.stairs(Vector3(hp.x, 0, -2.2), 1.0, int(bh / 0.25), 0.25, 0.3, 0, "stone", false)
		k.fence(Vector3(-3.4, bh, -3.4), Vector3(6.0, bh, -3.4), 0.8)
	if L >= 2:
		# covered shooting line along the front
		var sz = 4.6
		var x0 = -3.2
		var x1 = 5.8
		var n = 6
		for i in n + 1:
			var x = lerpf(x0, x1, float(i) / n)
			k.box("stone", Vector3(x, 0.12, sz), Vector3(0.32, 0.24, 0.32))
			k.beam("oak", Vector3(x, 0.24, sz + 0.6), Vector3(x, 2.3, sz + 0.6), 0.18, 0.18)
			k.beam("oak", Vector3(x, 0.24, sz - 0.6), Vector3(x, 2.3, sz - 0.6), 0.18, 0.18)
			if i < n:
				k.bench(Vector3(x + 0.75, 0, sz), 0.4, 90)
		if L <= 3:
			k.gable_roof("shingle", Vector3((x0 + x1) * 0.5, 2.35, sz), x1 - x0 + 0.2, 1.4, 0.6, 0.3)
		else:
			for i in 3:
				var cx = lerpf(x0, x1, (i + 0.5) / 3.0)
				k.push_at(Vector3(cx, 0, sz), 90)
				k.gable_roof("shingle", Vector3(0, 2.35, 0), 1.6, (x1 - x0) / 3.0, 0.8, 0.2)
				k.pop()
			k.box("stone", Vector3((x0 + x1) * 0.5, 0.15, sz + 0.75), Vector3(x1 - x0, 0.3, 0.2))
		for i in 3:
			k.lantern(Vector3(lerpf(x0, x1, (i + 0.5) / 3.0), 2.0, sz + 0.62))
	return {"worker": Vector3(-4.6, 0.0, 3.8)}

# ---------------------------------------------------------------- B13 Stables (MIL-03)
static func _stall_bay(k, x: float, z: float, w: float, h: float, arched: bool) -> void:
	## Front of one open horse stall: half door, hay rack, (arched) opening.
	k.box("plank", Vector3(x, 0.55, z + 0.05), Vector3(w - 0.3, 1.1, 0.08), 0, k.jitter(0.08))
	k.beam("dark_oak", Vector3(x - w * 0.4, 0.2, z + 0.1), Vector3(x + w * 0.4, 0.95, z + 0.1), 0.08, 0.05)
	k.box("soot", Vector3(x, 1.5, z - 0.3), Vector3(w - 0.4, 0.9, 0.05))
	k.box("hay", Vector3(x, 1.3, z - 0.25), Vector3(w * 0.6, 0.3, 0.3))
	if arched:
		k.cyl("dark_oak", Vector3(x, h - 0.6, z + 0.06), Vector3(x, h - 0.6, z + 0.1), (w - 0.3) * 0.5, 12)

static func b13_stables54(k, L: int) -> Dictionary:
	## I long stable (ridge along the street): tack room with a door and a window at the
	## left, two open stalls with half doors, paddock fence at the right. II three stalls
	## with arched heads, two cupolas on the ridge, lean-to tack shed. III a front gable
	## over the tack shed doorway. IV a tall central gable over a drive-through aisle,
	## stalls on both sides. V a hayloft gable with a hoist and a weather-vane cupola.
	var c = Vector3(-0.8, 0, -2.4)
	var lx = 8.4
	var lz = 3.8
	var front = c.z + lz * 0.5
	var h = 2.8
	k.timber_house(c, lx, lz, h, 1.9, [{"at": 0.9, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}, {"at": 1.9, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}],
		[], [], [], "shingle", "plank", 0.3)
	var bays = 2 if L == 1 else 3
	var bx0 = c.x - lx * 0.5 + 2.8
	var bw = 1.5
	for i in bays:
		_stall_bay(k, bx0 + bw * (i + 0.5), front, bw, h, L >= 2)
	k.box("soot", Vector3(bx0 + bw * bays * 0.5, 1.0, front - 0.2), Vector3(bw * bays, 1.9, 0.05))
	k.lantern(Vector3(c.x - lx * 0.5 + 2.6, 2.1, front + 0.15))
	k.sack(Vector3(c.x - lx * 0.5 + 2.4, 0, front + 0.4)); k.barrel(Vector3(c.x - lx * 0.5 + 2.9, 0, front + 0.45))
	# paddock at the right
	var px0 = c.x + lx * 0.5 + 0.1
	k.ground(Vector3(px0, 0, c.z - 1.4), Vector3(6.4, 0, front + 3.4), "sand", 0.03)
	k.fence(Vector3(px0, 0, front + 3.4), Vector3(6.4, 0, front + 3.4), 1.0)
	k.fence(Vector3(6.4, 0, front + 3.4), Vector3(6.4, 0, c.z - 1.4), 1.0)
	_gate(k, Vector3(px0 + 0.8, 0, front + 3.4), 1.2, 0, 0.0)
	k.box("plank", Vector3(5.6, 0.3, c.z), Vector3(0.5, 0.35, 1.6))
	if L >= 2:
		for x in [c.x - 1.6, c.x + 1.6]:
			_vent_cupola(k, Vector3(x, h + 1.9 - 0.25, c.z), 0.8)
		k.push_at(Vector3(c.x + lx * 0.5 + 0.9, 0, c.z + 0.4), 90)
		k.lean_to(Vector3.ZERO, lz - 0.4, 1.7, 2.1, 2.6, "shingle", 2)
		k.pop()
		k.box("parchment", Vector3(c.x + lx * 0.5 + 0.6, 1.1, c.z + 0.4), Vector3(0.6, 0.4, 0.5), 0, Color(0.6, 0.38, 0.2))
	if L >= 3:
		k.push_at(Vector3(c.x + lx * 0.5 - 1.2, 0, front - 0.2), 90)
		k.gable_roof("shingle", Vector3(0, h, 0), 1.4, 2.2, 1.2, 0.3, "plank")
		k.gable_frame(Vector3(0, h, 0), 1.4, 2.2, 1.2)
		k.pop()
		k.door(Vector3(c.x + lx * 0.5 - 1.2, 0, front + 0.12), 1.0, 2.0, 0, 0.0)
	if L >= 4:
		# tall central gable over a drive-through aisle
		var ax = c.x + 0.5
		k.box("soot", Vector3(ax, 1.3, front - 0.1), Vector3(2.0, 2.6, 0.1))
		k.push_at(Vector3(ax, 0, front - 0.4), 90)
		k.gable_roof("shingle", Vector3(0, h + 0.5, 0), 2.0, 3.0, 1.7, 0.3, "plank")
		k.gable_frame(Vector3(0, h + 0.5, 0), 2.0, 3.0, 1.7)
		k.pop()
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(ax + s * 1.4, 0, front + 0.4), Vector3(ax + s * 1.4, h + 0.5, front + 0.4), 0.26, 0.26)
			k.beam("oak", Vector3(ax + s * 1.4, h - 0.3, front + 0.4), Vector3(ax + s * 0.7, h + 0.45, front + 0.4), 0.12, 0.12)
		k.lantern(Vector3(ax, h - 0.1, front + 0.5))
	if L == 5:
		var ax = c.x + 0.5
		k.box("plank", Vector3(ax, h + 1.2, front + 0.3), Vector3(2.6, 1.6, 0.3))
		k.box("soot", Vector3(ax, h + 1.1, front + 0.46), Vector3(1.0, 1.0, 0.04))
		k.box("hay", Vector3(ax, h + 0.8, front + 0.5), Vector3(0.8, 0.4, 0.3))
		k.beam("oak", Vector3(ax, h + 2.3, front - 0.2), Vector3(ax, h + 2.3, front + 1.3), 0.14, 0.16)
		k.hook_hoist(Vector3(ax, h + 2.2, front + 1.2), 1.2)
		_vent_cupola(k, Vector3(ax, h + 0.5 + 1.7 - 0.2, front - 0.4), 0.9)
		k.cyl("iron", Vector3(ax, h + 3.3, front - 0.4), Vector3(ax, h + 3.9, front - 0.4), 0.03, 4)
		k.box("iron", Vector3(ax + 0.1, h + 3.85, front - 0.4), Vector3(0.5, 0.2, 0.03))
	return {"worker": Vector3(-4.0, 0.0, 2.2)}

# ---------------------------------------------------------------- B14 Blacksmith (MIL-04)
static func _forge_hood(k, p: Vector3, w := 1.6, tall := false) -> void:
	k.box("stone", p + Vector3(0, 0.45, 0), Vector3(w, 0.9, 1.2), 0, k.jitter(0.04))
	k.box("ember", p + Vector3(0, 0.92, 0.1), Vector3(w * 0.55, 0.06, 0.6))
	k.box("glow", p + Vector3(0, 1.15, -0.2), Vector3(w * 0.4, 0.3, 0.1))
	var pr = PackedVector2Array([Vector2(-w * 0.55, 1.5), Vector2(w * 0.55, 1.5), Vector2(w * 0.25, 2.4), Vector2(-w * 0.25, 2.4)])
	k.push_at(p)
	k.extrude("stone", pr, -0.6, 0.35)
	k.pop()
	k.box("stone", p + Vector3(0, 1.2, -0.45), Vector3(w, 0.6, 0.3))

static func b14_smith54(k, L: int) -> Dictionary:
	## I open timber smithy, gable to the street with the anvil banner, stone forge with
	## a hood at the back, anvil on a stump, quench tub, small chimney, open lean-to at
	## the right. II the left bay closed with plaster walls, a door and a shuttered window,
	## the forge open on the right. III a tall stone chimney over the forge, tool rack.
	## IV a weapon-rack lean-to at the right. V stone walls and a louvred roof monitor.
	var c = Vector3(-2.2, 0, -1.6)
	var lx = 3.6
	var lz = 4.0
	var front = c.z + lz * 0.5
	var h = 2.7
	var infill = "plaster" if L <= 4 else "stone"
	if L == 1:
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				var p = Vector3(c.x + sx * lx * 0.5, 0, c.z + sz * lz * 0.5)
				k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 0.4))
				k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, h, 0), 0.24, 0.24)
		for sz in [-1.0, 1.0]:
			k.beam("oak", Vector3(c.x - lx * 0.5, h, c.z + sz * lz * 0.5), Vector3(c.x + lx * 0.5, h, c.z + sz * lz * 0.5), 0.2, 0.24)
		k.push_at(Vector3(c.x, 0, c.z), 90)
		k.gable_roof("shingle", Vector3(0, h, 0), lz, lx, 1.6, 0.4, "plank")
		k.gable_frame(Vector3(0, h, 0), lz, lx, 1.6)
		k.pop()
		k.box("stone", Vector3(c.x, 0.15, c.z), Vector3(lx, 0.3, lz))
	else:
		_gable_house(k, c, lx, lz, h - 0.3, 1.6, [{"at": 1.2, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}, {"at": 2.7, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}],
			[], "shingle", infill, 0.3)
	k.banner(Vector3(c.x, h + 0.7, front + 0.45), 0.5, 0.75, "cloth_wine")
	# open forge bay at the right
	var fx = c.x + lx * 0.5 + 1.8
	var fw = 3.6
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			var p = Vector3(fx + sx * fw * 0.5, 0, c.z + sz * lz * 0.5)
			k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 0.4))
			k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, h - 0.2, 0), 0.24, 0.24)
	k.push_at(Vector3(fx, 0, c.z), 0)
	k.lean_to(Vector3.ZERO, fw + 0.2, lz, h - 0.6, h + 0.3, "shingle", 0)
	k.pop()
	k.box("stone", Vector3(fx, 0.08, c.z), Vector3(fw, 0.16, lz))
	_forge_hood(k, Vector3(fx - 0.6, 0.16, c.z - 1.2), 1.6)
	k.anvil(Vector3(fx - 0.4, 0.16, c.z + 0.6), 20)
	k.cyl("oak", Vector3(fx + 0.8, 0.16, c.z + 1.2), Vector3(fx + 0.8, 0.7, c.z + 1.2), 0.35, 10, true, k.jitter(0.1))
	k.cyl("water", Vector3(fx + 0.8, 0.69, c.z + 1.2), Vector3(fx + 0.8, 0.71, c.z + 1.2), 0.33, 10)
	k.box("plank", Vector3(fx + 1.2, 1.3, c.z - 1.85), Vector3(1.4, 1.4, 0.08))
	for i in 4:
		k.beam("iron", Vector3(fx + 0.7 + i * 0.3, 1.0, c.z - 1.78), Vector3(fx + 0.7 + i * 0.3, 1.6, c.z - 1.78), 0.04, 0.04)
	k.box("ore", Vector3(fx - 1.5, 0.35, c.z + 1.4), Vector3(0.6, 0.4, 0.6))
	if L <= 2:
		k.chimney(Vector3(fx - 0.6, h + 0.4, c.z - 1.3), 1.2, 0.6)
	else:
		# tall stone chimney over the forge
		k.box("stone", Vector3(fx - 0.6, h + 1.4, c.z - 1.3), Vector3(1.1, 3.2, 1.1), 0, k.jitter(0.04))
		k.box("stone_light", Vector3(fx - 0.6, h + 3.05, c.z - 1.3), Vector3(1.3, 0.2, 1.3))
		k.box("soot", Vector3(fx - 0.6, h + 3.16, c.z - 1.3), Vector3(0.7, 0.04, 0.7))
		k.workbench(Vector3(fx + 1.0, 0.16, c.z - 0.5), 1.2, 90)
	if L >= 4:
		# weapon-rack lean-to on the right
		var rx = fx + fw * 0.5 + 0.9
		k.push_at(Vector3(rx, 0, c.z + 0.2), 90)
		k.lean_to(Vector3.ZERO, lz - 0.4, 1.6, 2.0, 2.5, "shingle", 2)
		k.pop()
		k.weapon_rack(Vector3(rx, 0, c.z - 0.4), 1.2, 90)
		k.box("iron", Vector3(rx - 0.3, 1.0, c.z + 1.0), Vector3(0.1, 0.8, 0.6))
		k.fence(Vector3(rx + 0.8, 0, front + 0.2), Vector3(rx + 0.8, 0, c.z - 1.6), 1.2)
	if L == 5:
		var mx = fx + 0.6
		k.box("plank", Vector3(mx, h + 0.75, c.z), Vector3(2.4, 0.9, 1.2))
		for i in 3:
			k.box("glow", Vector3(mx - 0.7 + i * 0.7, h + 0.8, c.z + 0.62), Vector3(0.45, 0.35, 0.04))
		k.gable_roof("shingle", Vector3(mx, h + 1.2, c.z), 2.6, 1.4, 0.5, 0.2)
	return {"worker": Vector3(-1.0, 0.0, 3.4)}

# ---------------------------------------------------------------- B15 Military Academy (MIL-05)
static func b15_academy54(k, L: int) -> Dictionary:
	## I gable-fronted hall with a stone ground floor, an arched double door up stone
	## steps, plaster upper floor and banners; an open pavilion with a red awning over a
	## map table at the right; a sand training yard with a rope fence, post dummy and a
	## weapon rack in front. II dormers and a roofed pavilion. III the pavilion with its
	## own front gable. IV a two-storey wing round the back of a garden court behind the
	## pavilion. V a central cupola with a flag.
	var c = Vector3(-3.4, 0, -1.4)
	var lx = 4.2
	var lz = 5.2
	var front = c.z + lz * 0.5
	_gable_house(k, c, lx, lz, 4.2, 2.6, [{"at": 1.0, "w": 0.5, "y0": 2.6, "y1": 3.3, "kind": "window"}, {"at": 2.1, "w": 0.6, "y0": 2.6, "y1": 3.4, "kind": "window"}, {"at": 3.2, "w": 0.5, "y0": 2.6, "y1": 3.3, "kind": "window"}],
		[{"at": 1.4, "w": 0.6, "y0": 1.0, "y1": 1.7, "kind": "window"}, {"at": 2.8, "w": 0.6, "y0": 1.0, "y1": 1.7, "kind": "window"}, {"at": 4.0, "w": 0.6, "y0": 1.0, "y1": 1.7, "kind": "window"}], "shingle", "plaster", 0.6)
	k.box("stone", Vector3(c.x, 1.55, front + 0.05), Vector3(lx + 0.1, 2.0, 0.3), 0, k.jitter(0.03))
	k.push_at(Vector3(c.x, 0, front + 0.25))
	k.arch_wall(Vector3.ZERO, 1.6, 0.35, 1.8, 2.4, 2.7, "stone", "stone_light")
	k.pop()
	k.door(Vector3(c.x - 0.4, 0.6, front + 0.15), 0.8, 2.0, 0, 0.0)
	k.door(Vector3(c.x + 0.4, 0.6, front + 0.15), 0.8, 2.0, 0, 0.0)
	for s in [-1.0, 1.0]:
		k.banner(Vector3(c.x + s * 1.55, 2.3, front + 0.45), 0.35, 0.9, "cloth_wine")
		k.lantern(Vector3(c.x + s * 1.3, 2.7, front + 0.5))
	k.stairs(Vector3(c.x, 0, front + 0.4 + 4 * 0.3), 1.8, 4, 0.15, 0.3, 0, "stone")
	# open pavilion at the right with the map table
	var pv = Vector3(c.x + lx * 0.5 + 1.9, 0, c.z + 0.6)
	var pw = 3.2
	var pd = 2.8
	k.box("stone", pv + Vector3(0, 0.12, 0), Vector3(pw, 0.24, pd))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			k.beam("oak", pv + Vector3(sx * pw * 0.45, 0.24, sz * pd * 0.45), pv + Vector3(sx * pw * 0.45, 2.5, sz * pd * 0.45), 0.2, 0.2)
	k.map_table(pv + Vector3(0, 0.24, 0), 1.8, 1.1)
	k.lantern(pv + Vector3(pw * 0.45, 2.1, pd * 0.45 + 0.15))
	if L == 1:
		k.box("cloth_wine", pv + Vector3(0, 2.6, 0.2), Vector3(pw + 0.3, 0.05, pd + 0.4), 0, Color.WHITE, 8)
		for i in 6:
			k.box("cloth_wine", pv + Vector3(-pw * 0.5 + pw * (i + 0.5) / 6.0, 2.42, pd * 0.5 + 0.38), Vector3(pw / 6.0 - 0.02, 0.22, 0.02))
	elif L == 2:
		k.gable_roof("shingle", pv + Vector3(0, 2.55, 0), pw, pd, 1.0, 0.3)
	else:
		k.push_at(pv, 90)
		k.gable_roof("shingle", Vector3(0, 2.55, 0), pd, pw, 1.3, 0.3, "plank")
		k.gable_frame(Vector3(0, 2.55, 0), pd, pw, 1.3)
		k.pop()
		k.banner(pv + Vector3(0, 3.3, pd * 0.5 + 0.35), 0.4, 0.6, "cloth_wine")
	# training yard
	var yx0 = -2.4
	var yx1 = 5.8
	var yz0 = 1.8
	var yz1 = 6.2
	k.ground(Vector3(yx0, 0, yz0), Vector3(yx1, 0, yz1), "sand", 0.03)
	for p in [Vector3(yx0, 0, yz0), Vector3(yx1, 0, yz0), Vector3(yx1, 0, yz1), Vector3(yx0, 0, yz1)]:
		k.beam("oak", p, p + Vector3(0, 0.6, 0), 0.14, 0.14)
	for e in [[Vector3(yx0, 0.5, yz1), Vector3(yx1, 0.5, yz1)], [Vector3(yx1, 0.5, yz0), Vector3(yx1, 0.5, yz1)]]:
		k.cyl("rope", e[0], e[1], 0.025, 4, false)
	k.cyl("log", Vector3(0.6, 0, 3.8), Vector3(0.6, 1.8, 3.8), 0.2, 8)
	k.weapon_rack(Vector3(3.6, 0, 3.6), 1.4, 0)
	k.box("cloth_wine", Vector3(-1.2, 0.3, 4.8), Vector3(1.0, 0.3, 0.6))
	if L >= 2:
		for x in [c.x - 0.9, c.x + 0.9]:
			k.push_at(Vector3(c.x + lx * 0.5 - 0.6, 4.8, c.z + (x - c.x) * 1.4))
			k.box("plaster", Vector3(0, 0.4, 0), Vector3(1.0, 0.8, 0.9))
			k.window(Vector3(0.48, 0, 0), 0.4, 0.2, 0.65, 90)
			k.gable_roof("shingle", Vector3(0, 0.8, 0), 1.2, 1.0, 0.45, 0.12, "plaster")
			k.pop()
		k.paving(Vector3(-6.4, 0, front + 0.5), Vector3(-2.6, 0, 6.4), 0.05, 0.5)
	if L >= 4:
		# two-storey wing round a garden court behind the pavilion
		var wz = -4.6
		k.timber_house(Vector3(2.4, 0, wz), 7.6, 2.6, 4.0, 1.8, [{"at": 1.6, "w": 0.5, "y0": 2.4, "y1": 3.1, "kind": "window"}, {"at": 3.2, "w": 0.5, "y0": 2.4, "y1": 3.1, "kind": "window"}, {"at": 4.8, "w": 0.5, "y0": 2.4, "y1": 3.1, "kind": "window"}, {"at": 6.4, "w": 0.5, "y0": 2.4, "y1": 3.1, "kind": "window"}], [], [], [], "shingle", "plaster", 0.4, 1.4)
		k.timber_house(Vector3(5.4, 0, -1.8), 2.0, 3.4, 3.4, 1.4, [], [], [], [], "shingle", "plaster", 0.4, 1.2)
		k.push_at(Vector3(1.9, 0, wz + 1.9), 0)
		k.lean_to(Vector3.ZERO, 6.0, 1.1, 2.2, 2.7, "shingle", 5)
		k.pop()
		k.box("cloth_wine", Vector3(1.9, 2.15, wz + 2.5), Vector3(6.0, 0.25, 0.04))
		k.garden_bed(Vector3(0.0, 0, -2.6), Vector3(1.6, 0, -1.6), "herb", 2)
		k.cyl("stone_light", Vector3(2.8, 0, -2.2), Vector3(2.8, 0.5, -2.2), 0.45, 10)
	if L == 5:
		_vent_cupola(k, Vector3(2.4, 0.4 + 4.0 + 1.6, -4.6), 1.1)
		k.flag_pole(Vector3(2.4, 0.4 + 4.0 + 2.9, -4.6), 1.4, "cloth_wine")
	return {"worker": Vector3(-0.6, 0.0, 5.4)}

# ---------------------------------------------------------------- B16 Infirmary (SUP-01)
static func _canvas_roof(k, c: Vector3, lz: float, lx: float, h: float, rise: float) -> void:
	## Cream canvas gable roof on a timber frame, ridge front-to-back, red hem.
	for s in [-1.0, 1.0]:
		k.next_piece()
		_quad2(k, "canvas", Vector3(c.x + s * (lx * 0.5 + 0.25), h - 0.15, c.z - lz * 0.5 - 0.2), Vector3(c.x + s * (lx * 0.5 + 0.25), h - 0.15, c.z + lz * 0.5 + 0.2),
			Vector3(c.x, h + rise, c.z + lz * 0.5 + 0.2), Vector3(c.x, h + rise, c.z - lz * 0.5 - 0.2), Color(1.0, 0.98, 0.92))
		k.box("cloth_red", Vector3(c.x + s * (lx * 0.5 + 0.22), h - 0.12, c.z), Vector3(0.04, 0.12, lz + 0.4))
	for z in [c.z - lz * 0.5, c.z + lz * 0.5]:
		k.beam("oak", Vector3(c.x - lx * 0.5 - 0.1, h - 0.2, z), Vector3(c.x, h + rise + 0.15, z), 0.16, 0.16)
		k.beam("oak", Vector3(c.x + lx * 0.5 + 0.1, h - 0.2, z), Vector3(c.x, h + rise + 0.15, z), 0.16, 0.16)
	k.beam("oak", Vector3(c.x, h + rise + 0.1, c.z - lz * 0.5 - 0.2), Vector3(c.x, h + rise + 0.1, c.z + lz * 0.5 + 0.2), 0.14, 0.14)

static func b16_infirmary54(k, L: int) -> Dictionary:
	## I canvas ward on a timber deck: framed gable, curtained entrance, cots inside, a
	## stretcher on the deck, a lean-to with a remedy table at the left, steps. II a boarded
	## front gable round the curtained arch and a closed store at the right. III stone
	## plinth, plaster gable with a red cross, wider steps, balustrade with flower boxes.
	## IV a walled garden court with a fountain behind, a long back wing. V chimney,
	## paved approach.
	var c = Vector3(0.0, 0, -0.8)
	var lx = 4.0
	var lz = 4.6
	var fy = 0.45 if L <= 2 else 0.75
	var front = c.z + lz * 0.5
	if L <= 2:
		k.deck(Vector3(c.x - lx * 0.5 - 2.2, 0, c.z - lz * 0.5), Vector3(c.x + lx * 0.5 + 1.0, 0, front + 1.6), fy, "plank", true, true, true)
	else:
		k.box("stone", Vector3(c.x - 0.6, fy * 0.5, c.z + 0.4), Vector3(lx + 3.4, fy, lz + 2.4), 0, k.jitter(0.04))
		k.deck(Vector3(c.x - lx * 0.5 - 2.2, 0, c.z - lz * 0.5), Vector3(c.x + lx * 0.5 + 1.0, 0, front + 1.6), fy + 0.02, "plank", false, false, true)
	var h = fy + 2.4
	for sx in [-1.0, 1.0]:
		for z in [c.z - lz * 0.5, c.z, front]:
			k.beam("oak", Vector3(c.x + sx * lx * 0.5, fy, z), Vector3(c.x + sx * lx * 0.5, h, z), 0.18, 0.18)
	_canvas_roof(k, c, lz, lx, h, 1.8)
	for sx in [-1.0, 1.0]:
		k.next_piece()
		_quad2(k, "canvas", Vector3(c.x + sx * lx * 0.5, fy, c.z - lz * 0.5), Vector3(c.x + sx * lx * 0.5, fy, front), Vector3(c.x + sx * lx * 0.5, h, front), Vector3(c.x + sx * lx * 0.5, h, c.z - lz * 0.5))
	# front gable: canvas (I) / boards (II) / plaster with a red cross (III+)
	var gm = "canvas" if L == 1 else ("plank" if L == 2 else "plaster")
	for sx in [-1.0, 1.0]:
		k.box(gm, Vector3(c.x + sx * (lx * 0.5 - 0.6), (fy + h) * 0.5, front), Vector3(1.2, h - fy, 0.1))
	k.next_piece()
	_tri2(k, gm, Vector3(c.x - lx * 0.5, h, front + 0.02), Vector3(c.x + lx * 0.5, h, front + 0.02), Vector3(c.x, h + 1.8, front + 0.02))
	for sx in [-1.0, 1.0]:
		k.box("linen", Vector3(c.x + sx * 0.75, fy + 1.1, front + 0.1), Vector3(0.35, 2.1, 0.05))
		k.box("cloth_red", Vector3(c.x + sx * 0.75, fy + 0.15, front + 0.13), Vector3(0.36, 0.2, 0.02))
	if L >= 3:
		k.box("linen", Vector3(c.x, h + 0.7, front + 0.08), Vector3(0.6, 0.6, 0.02))
		k.box("cloth_red", Vector3(c.x, h + 0.7, front + 0.1), Vector3(0.45, 0.13, 0.02))
		k.box("cloth_red", Vector3(c.x, h + 0.7, front + 0.1), Vector3(0.13, 0.45, 0.02))
	for i in 2:
		k.bed(Vector3(c.x - 0.9 + i * 1.8, fy, c.z - 0.6), 0)
	k.stretcher(Vector3(c.x + 1.6, fy, front + 0.8), 90)
	# remedy lean-to at the left
	k.push_at(Vector3(c.x - lx * 0.5 - 1.1, fy, c.z + 0.6), -90)
	k.lean_to(Vector3.ZERO, lz - 0.4, 2.0, 1.9, 2.4, "shingle", 2)
	k.pop()
	k.table(Vector3(c.x - lx * 0.5 - 1.2, fy, c.z + 0.6), 1.2, 0.6, 0.85)
	k.box("greenglass", Vector3(c.x - lx * 0.5 - 1.2, fy + 0.95, c.z + 0.6), Vector3(0.5, 0.15, 0.3))
	k.lantern(Vector3(c.x - lx * 0.5 - 2.0, fy + 1.9, c.z + 1.8))
	var n = 2 if L <= 2 else 4
	k.stairs(Vector3(c.x, 0, front + 1.6 + n * 0.3), 1.6 if L <= 2 else 2.4, n, fy / n, 0.3, 0, "stone")
	if L >= 2:
		var st = Vector3(c.x + lx * 0.5 + 1.0, fy, c.z - 0.2)
		_gable_house(k, st, 1.8, 2.6, 2.1, 1.1, [{"at": 0.9, "w": 0.8, "y0": 0.0, "y1": 1.8, "kind": "door"}], [], "shingle", gm if L >= 3 else "plank", 0.1)
		k.lantern(st + Vector3(1.0, 1.9, 1.4))
	if L >= 3:
		k.railing(Vector3(c.x - lx * 0.5 - 2.2, fy, front + 1.6), Vector3(c.x - 1.2, fy, front + 1.6), 0.8)
		for x in [c.x - 4.0, c.x - 2.8]:
			k.box("plank", Vector3(x, fy + 0.85, front + 1.65), Vector3(0.8, 0.2, 0.25))
			k.bush(Vector3(x, fy + 0.9, front + 1.65), 0.2, "flower")
	if L >= 4:
		# walled garden court with a fountain behind, long back wing
		k.stone_wall(Vector3(-6.4, 0, -5.6), Vector3(-6.4, 0, -1.0), 1.6, 0.4, "plaster")
		k.stone_wall(Vector3(-6.4, 0, -5.6), Vector3(0.0, 0, -5.6), 1.6, 0.4, "plaster")
		k.timber_house(Vector3(3.4, 0, -5.0), 5.6, 2.6, 3.0, 1.6, [], [], [], [{"at": 1.3, "w": 0.6, "y0": 1.0, "y1": 1.7, "kind": "window"}], "clay_roof", "plaster", 0.4)
		k.ground(Vector3(-6.0, 0, -5.2), Vector3(0.4, 0, -3.2), "path", 0.03)
		k.cyl("stone_light", Vector3(-3.2, 0, -4.2), Vector3(-3.2, 0.5, -4.2), 0.6, 10)
		k.cyl("water", Vector3(-3.2, 0.49, -4.2), Vector3(-3.2, 0.52, -4.2), 0.5, 10)
		for x in [-5.4, -1.0]:
			k.bush(Vector3(x, 0, -4.4), 0.45, "flower")
			k.bush(Vector3(x, 0, -3.4), 0.35)
		k.bench(Vector3(-4.6, 0, -5.1), 1.2, 0)
	if L == 5:
		k.chimney(Vector3(4.6, 3.4, -5.4), 1.8, 0.5)
		k.ground_poly(PackedVector2Array([Vector2(-1.2, 4.8), Vector2(1.2, 4.8), Vector2(2.6, 6.6), Vector2(-0.4, 6.6)]), "stone_light", 0.04)
	return {"worker": Vector3(3.2, 0.0, 3.8)}

# ---------------------------------------------------------------- B17 Siege Workshop (SUP-02)
static func b17_siege54(k, L: int) -> Dictionary:
	## I half-timbered workshop, gable to the street, broad doors with a catapult banner
	## up stone steps; an open deck at the right with trestles, a wheel and a beam frame,
	## a ladder down. II an open-sided roofed bay over the deck with parts racks and a
	## hoist. III a louvred monitor and cupola on the bay. IV a tall arched assembly hall
	## with an inner jib crane. V a long ramp out of the hall and a gallery inside.
	var c = Vector3(-3.0, 0, -1.0)
	var lx = 3.8
	var lz = 4.4
	var front = c.z + lz * 0.5
	_gable_house(k, c, lx, lz, 3.0, 2.4, [{"at": 1.9, "w": 1.8, "y0": 0.0, "y1": 2.3, "kind": "double"}, {"at": 0.5, "w": 0.4, "y0": 1.0, "y1": 1.6, "kind": "window"}, {"at": 3.3, "w": 0.4, "y0": 1.0, "y1": 1.6, "kind": "window"}],
		[], "shingle", "plaster", 0.5)
	k.banner(Vector3(c.x, 3.9, front + 0.45), 0.6, 0.85, "cloth_wine")
	k.stairs(Vector3(c.x, 0, front + 0.2 + 2 * 0.32), 2.2, 2, 0.25, 0.32, 0, "stone")
	# work deck at the right
	var dx0 = c.x + lx * 0.5 + 0.1
	var dx1 = 6.4
	var dz0 = c.z - lz * 0.5 + 0.3
	var dz1 = front + 1.2
	var dy = 0.55
	k.deck(Vector3(dx0, 0, dz0), Vector3(dx1, 0, dz1), dy, "plank", true, true, true)
	k.stairs(Vector3(dx1 - 1.2, 0, dz1 + 0.6), 0.8, 3, dy / 3.0, 0.2, 0, "oak", false)
	k.sawhorse(Vector3(dx0 + 0.9, dy, front), 0); k.sawhorse(Vector3(dx0 + 2.0, dy, front + 0.2), 10)
	k.wheel(Vector3(dx0 + 3.2, dy + 0.6, dz0 + 0.8), 0.6, Vector3.FORWARD)
	for s in [-0.5, 0.5]:
		k.beam("oak", Vector3(dx0 + 2.2, dy + 0.1, dz0 + 1.0 + s), Vector3(dx0 + 4.2, dy + 0.1, dz0 + 1.0 + s), 0.18, 0.18)
	k.beam("oak", Vector3(dx0 + 2.6, dy, dz0 + 1.0), Vector3(dx0 + 3.0, dy + 1.4, dz0 + 1.0), 0.14, 0.14)
	if L >= 2:
		var bx = (dx0 + dx1) * 0.5
		var bz = (dz0 + dz1) * 0.5 - 0.4
		var bw = dx1 - dx0 - 0.3
		var bd = dz1 - dz0 - 1.0
		var bh = 3.4 if L <= 3 else 4.6
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				k.beam("oak", Vector3(bx + sx * bw * 0.5, dy, bz + sz * bd * 0.5), Vector3(bx + sx * bw * 0.5, dy + bh, bz + sz * bd * 0.5), 0.26, 0.26)
		k.box("plank", Vector3(bx, dy + bh * 0.5, bz - bd * 0.5), Vector3(bw, bh, 0.1))
		if L <= 3:
			k.gable_roof("shingle", Vector3(bx, dy + bh, bz), bw + 0.2, bd + 0.2, 1.3, 0.35)
		else:
			# tall arched assembly hall
			for z in [bz - bd * 0.5, bz + bd * 0.5]:
				var prev = Vector3.ZERO
				for i in 9:
					var t = PI * i / 8.0
					var p = Vector3(bx - cos(t) * bw * 0.5, dy + bh + sin(t) * 1.6, z)
					if i > 0:
						k.beam("oak", prev, p, 0.22, 0.26)
					prev = p
			k.gable_roof("shingle", Vector3(bx, dy + bh + 0.1, bz), bw + 0.4, bd + 0.4, 1.8, 0.3)
		k.box("plank", Vector3(bx + bw * 0.3, dy + 1.4, bz - bd * 0.5 + 0.2), Vector3(1.4, 1.6, 0.4))
		for i in 3:
			k.wheel(Vector3(bx + bw * 0.1 + i * 0.5, dy + 1.5, bz - bd * 0.5 + 0.45), 0.25, Vector3.FORWARD)
		k.hook_hoist(Vector3(bx, dy + bh - 0.1, bz), 1.8)
		if L >= 3:
			var ry = dy + bh + (1.3 if L == 3 else 1.8)
			k.box("plank", Vector3(bx, ry + 0.3, bz), Vector3(bw * 0.7, 0.7, 1.0))
			for i in 4:
				k.box("glow", Vector3(bx - bw * 0.25 + i * bw * 0.17, ry + 0.3, bz + 0.52), Vector3(0.35, 0.3, 0.03))
			k.gable_roof("shingle", Vector3(bx, ry + 0.65, bz), bw * 0.75, 1.2, 0.4, 0.15)
			_vent_cupola(k, Vector3(bx, ry + 0.85, bz), 0.6)
		if L >= 4:
			var jb = Vector3(bx - 0.6, dy, bz + 0.4)
			k.crane(jb, bh - 0.4, Vector3(1.4, 0, 0.4), 1.6)
			k.wheel(jb + Vector3(0.6, 0.8, 0.3), 0.5, Vector3.RIGHT)
	if L == 5:
		k.ramp(Vector3(4.2, 0, 6.6), Vector3(4.2, dy + 0.02, dz1), 2.4, "plank")
		k.deck(Vector3(dx0, 0, dz0), Vector3(dx0 + 1.4, 0, dz0 + 1.8), dy + 2.4, "plank", true, true, true)
		k.railing(Vector3(dx0, dy + 2.4, dz0 + 1.8), Vector3(dx0 + 1.4, dy + 2.4, dz0 + 1.8), 0.8)
	return {"worker": Vector3(-1.2, 0.0, 4.4)}

# ---------------------------------------------------------------- B19 Watchtower (SUP-04)
static func b19_tower54(k, L: int) -> Dictionary:
	## I open lookout deck on four braced posts with a balustrade and a stair on the right,
	## stone pads. II the lower storey boarded with a door, a pyramid-gabled roof on posts
	## over the deck. III stone plinth course and a hood over the door, telescope on the deck.
	## IV a battered stone lower tower with slit windows. V a wider gallery on corbels with a
	## second roof wing and lanterns.
	var hw = 1.6
	var dy = 3.6 if L == 1 else 3.8
	var c = Vector3(-0.6, 0, -0.6)
	if L <= 3:
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				var p = c + Vector3(sx * hw, 0, sz * hw)
				k.box("stone", p + Vector3(0, 0.25, 0), Vector3(0.6, 0.5, 0.6), 0, k.jitter(0.05))
				k.beam("oak", p + Vector3(0, 0.5, 0), p + Vector3(0, dy, 0), 0.34, 0.34)
		for e in [[Vector3(-1, 0, 1), Vector3(1, 0, 1)], [Vector3(1, 0, 1), Vector3(1, 0, -1)], [Vector3(-1, 0, -1), Vector3(-1, 0, 1)]]:
			k.beam("oak", c + e[0] * hw + Vector3(0, 0.8, 0), c + e[1] * hw * 0.5 + Vector3(0, dy - 0.3, 0), 0.14, 0.14)
	else:
		# battered stone lower tower
		var pr = PackedVector2Array([Vector2(-hw - 0.5, 0), Vector2(hw + 0.5, 0), Vector2(hw + 0.1, dy), Vector2(-hw - 0.1, dy)])
		k.push_at(c)
		k.extrude("stone", pr, -hw - 0.5, hw + 0.5)
		k.pop()
		k.push(Transform3D(Basis(Vector3.UP, PI * 0.5), c))
		k.extrude("stone", pr, -hw - 0.3, hw + 0.3)
		k.pop()
		for x in [-0.8, 0.0, 0.8]:
			k.box("soot", c + Vector3(x, dy - 1.1, hw + 0.16), Vector3(0.18, 0.5, 0.05))
	if L >= 2 and L <= 3:
		for e in [[Vector3(-1, 0, 1), Vector3(1, 0, 1)], [Vector3(1, 0, 1), Vector3(1, 0, -1)]]:
			k.timber_wall(c + e[0] * hw + Vector3(0, 0.5, 0), c + e[1] * hw + Vector3(0, 0.5, 0), dy - 0.6, [{"at": hw, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}] if e[0].x < 0 else [], "plank", "oak", 0.15, 1.6)
	if L >= 3:
		var dz = c.z + hw + (0.15 if L == 3 else 0.6)
		k.door(Vector3(c.x - 0.4, 0, dz), 0.9, 1.9, 0, 0.0)
		k.push_at(Vector3(c.x - 0.4, 2.1, dz + 0.3))
		k.lean_to(Vector3.ZERO, 1.4, 0.6, 0.0, 0.3, "shingle", 0)
		k.pop()
		for s in [-1.0, 1.0]:
			k.lantern(Vector3(c.x - 0.4 + s * 0.8, 1.9, dz + 0.1))
		if L == 3:
			k.box("stone", c + Vector3(0, 0.5, 0), Vector3(hw * 2 + 0.6, 1.0, hw * 2 + 0.6), 0, k.jitter(0.04))
	# deck with a balustrade
	var gw = hw + (0.3 if L <= 4 else 0.9)
	k.deck(c + Vector3(-gw, 0, -gw), c + Vector3(gw, 0, gw), dy + 0.1, "plank", false, true, true)
	if L == 5:
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 0.0, 1.0]:
				k.beam("oak", c + Vector3(sx * (hw + 0.1), dy - 0.8, sz * hw), c + Vector3(sx * (gw - 0.1), dy, sz * hw), 0.16, 0.16)
	for e in [[Vector3(-1, 0, 1), Vector3(1, 0, 1)], [Vector3(1, 0, 1), Vector3(1, 0, -1)], [Vector3(-1, 0, -1), Vector3(-1, 0, 1)], [Vector3(1, 0, -1), Vector3(-1, 0, -1)]]:
		if L == 1:
			k.railing(c + e[0] * gw + Vector3(0, dy + 0.1, 0), c + e[1] * gw + Vector3(0, dy + 0.1, 0), 0.95, "oak", 0.35)
		else:
			var a = c + e[0] * gw + Vector3(0, dy + 0.1, 0)
			var b = c + e[1] * gw + Vector3(0, dy + 0.1, 0)
			var mid = (a + b) * 0.5
			k.box("plank", mid + Vector3(0, 0.45, 0), Vector3(absf(b.x - a.x) + 0.1, 0.9, absf(b.z - a.z) + 0.1), 0, k.jitter(0.06))
	if L >= 2:
		var rh = dy + 2.3
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				k.beam("oak", c + Vector3(sx * hw, dy + 0.1, sz * hw), c + Vector3(sx * hw, rh, sz * hw), 0.24, 0.24)
		k.push_at(c, 90)
		k.gable_roof("shingle", Vector3(0, rh, 0), hw * 2 + 0.4, hw * 2 + 0.4, 1.4, 0.45)
		k.gable_frame(Vector3(0, rh, 0), hw * 2 + 0.4, hw * 2 + 0.4, 1.4)
		k.pop()
		if L == 5:
			k.gable_roof("shingle", c + Vector3(hw + 0.6, rh - 0.2, 0), 1.4, hw * 2, 1.0, 0.3)
			for sz in [-1.0, 1.0]:
				k.beam("oak", c + Vector3(gw - 0.1, dy + 0.1, sz * hw), c + Vector3(gw - 0.1, rh - 0.2, sz * hw), 0.18, 0.18)
				k.lantern(c + Vector3(gw, dy + 1.6, sz * gw))
	if L >= 3:
		k.cyl("brass", c + Vector3(-0.5, dy + 1.3, 0.5), c + Vector3(0.2, dy + 1.5, 0.9), 0.08, 8)
		k.beam("dark_oak", c + Vector3(-0.2, dy + 0.1, 0.7), c + Vector3(-0.2, dy + 1.3, 0.7), 0.06, 0.06)
	# stair on the right up to the deck
	var steps = int(dy / 0.3)
	k.push_at(c + Vector3(gw + 0.55, 0, gw + steps * 0.24 - 0.2), 0)
	for i in steps:
		k.box("oak", Vector3(0, (i + 1) * dy / steps - 0.04, -i * 0.24), Vector3(0.8, 0.07, 0.26))
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(s * 0.45, 0, 0.1), Vector3(s * 0.45, dy + 0.1, -steps * 0.24), 0.08, 0.2)
		k.beam("oak", Vector3(s * 0.45, 0.9, 0.1), Vector3(s * 0.45, dy + 1.0, -steps * 0.24), 0.06, 0.06)
	k.pop()
	k.box("stone", c + Vector3(gw + 0.55, 0.12, gw + steps * 0.24 + 0.1), Vector3(1.0, 0.24, 0.5))
	return {"worker": Vector3(-3.2, 0.0, 2.8)}

# ---------------------------------------------------------------- B20 Well (SUP-05)
static func b20_well54(k, L: int) -> Dictionary:
	## I stone well ring with two posts, a crossbeam, rope and bucket. II gabled shingle
	## roof on braced posts and a windlass with a crank. III round paving, a rain gutter
	## and downpipe with a drain grate. IV a taller ring with a moulded cap, a gear box,
	## wider paving with a kerb. V steps up to the ring, a stone trough and a bucket stand.
	var c = Vector3(0, 0, 0)
	var rr = 1.1 if L <= 3 else 1.25
	var rh = 0.8 if L <= 3 else 1.0
	if L >= 3:
		k.ground_poly(_oval(0, 0.2, 3.4 if L == 3 else 3.8, 3.0 if L == 3 else 3.4, 28), "stone_light", 0.04)
	if L >= 4:
		var ring = _oval(0, 0.2, 3.9, 3.5, 28)
		for i in ring.size():
			var a = ring[i]
			var b = ring[(i + 1) % ring.size()]
			k.box("stone", Vector3((a.x + b.x) * 0.5, 0.08, (a.y + b.y) * 0.5), Vector3(Vector2(a - b).length() + 0.02, 0.16, 0.3), rad_to_deg(-atan2(b.y - a.y, b.x - a.x)))
	k.cyl("stone", c, c + Vector3(0, rh, 0), rr, 14, true, k.jitter(0.04))
	k.cyl("stone_light", c + Vector3(0, rh, 0), c + Vector3(0, rh + 0.12, 0), rr + 0.08, 14)
	k.cyl("water", c + Vector3(0, rh + 0.08, 0), c + Vector3(0, rh + 0.13, 0), rr - 0.25, 14)
	for s in [-1.0, 1.0]:
		k.box("stone", Vector3(s * (rr + 0.35), 0.25, 0), Vector3(0.5, 0.5, 0.5), 0, k.jitter(0.05))
		k.beam("oak", Vector3(s * (rr + 0.35), 0.5, 0), Vector3(s * (rr + 0.35), 2.6, 0), 0.26, 0.26)
		if L >= 2:
			k.beam("oak", Vector3(s * (rr + 0.35), 2.0, 0), Vector3(s * (rr - 0.1), 2.55, 0), 0.12, 0.12)
	var by = rh + 0.5
	if L == 1:
		k.beam("oak", Vector3(-rr - 0.6, 2.45, 0), Vector3(rr + 0.6, 2.45, 0), 0.24, 0.28)
		k.cyl("rope", Vector3(0, 2.4, -0.15), Vector3(0, 2.4, 0.15), 0.18, 10)
	else:
		k.cyl("oak", Vector3(-rr - 0.2, 2.0, 0), Vector3(rr + 0.2, 2.0, 0), 0.2, 10)
		k.cyl("rope", Vector3(-0.4, 2.0, 0), Vector3(0.4, 2.0, 0), 0.24, 10)
		k.beam("iron", Vector3(rr + 0.5, 2.0, 0), Vector3(rr + 0.65, 1.7, 0.1), 0.05, 0.05)
		k.cyl("oak", Vector3(rr + 0.65, 1.7, 0.1), Vector3(rr + 0.65, 1.7, 0.45), 0.05, 6)
		k.gable_roof("shingle", Vector3(0, 2.75, 0), (rr + 0.35) * 2 + 0.2, 1.4, 1.1, 0.45)
		k.gable_frame(Vector3(0, 2.75, 0), (rr + 0.35) * 2 + 0.2, 1.4, 1.1)
		k.beam("oak", Vector3(-rr - 0.6, 2.7, 0), Vector3(rr + 0.6, 2.7, 0), 0.2, 0.24)
	k.cyl("rope", Vector3(0, by + 0.35, 0), Vector3(0, 2.2, 0), 0.025, 5, false)
	k.cyl("oak", Vector3(0, by, 0), Vector3(0, by + 0.35, 0), 0.2, 10, true, k.jitter(0.1), 0.24)
	if L >= 3:
		# gutter, downpipe and drain grate
		k.box("iron", Vector3(0, 2.38, 1.15), Vector3((rr + 0.6) * 2, 0.08, 0.1))
		k.beam("iron", Vector3(rr + 0.75, 2.35, 1.15), Vector3(rr + 0.75, 0.15, 1.15), 0.08, 0.08)
		k.box("iron", Vector3(rr + 0.75, 0.06, 1.45), Vector3(0.4, 0.03, 0.4))
	if L >= 4:
		k.box("plank", Vector3(rr + 0.4, 2.0, 0), Vector3(0.3, 0.6, 0.6))
		k.wheel(Vector3(rr + 0.58, 2.0, 0), 0.25, Vector3.RIGHT, "iron")
	if L == 5:
		k.stairs(Vector3(0, 0, rr + 1.3), 1.6, 2, 0.15, 0.3, 0, "stone_light")
		k.box("stone", Vector3(2.2, 0.35, 0.8), Vector3(0.7, 0.7, 1.6), 0, k.jitter(0.04))
		k.box("water", Vector3(2.2, 0.66, 0.8), Vector3(0.5, 0.04, 1.4))
		k.box("stone", Vector3(-2.2, 0.3, 0.0), Vector3(0.8, 0.6, 0.8))
		k.cyl("oak", Vector3(-2.3, 0.6, 0.0), Vector3(-2.3, 0.95, 0.0), 0.2, 10)
		k.lantern(Vector3(rr + 0.4, 2.6, 0.3))
	return {"worker": Vector3(-2.6, 0.0, 2.2)}

# ---------------------------------------------------------------- B21 Sawmill (ALT-02)
static func _saw_frame(k, p: Vector3, big := false) -> void:
	## Water-driven frame saw: two posts, a crosshead with blades, a log on the carriage,
	## a gear wheel at the side.
	var h = 2.4 if not big else 2.8
	for s in [-1.0, 1.0]:
		k.beam("oak", p + Vector3(s * 0.7, 0, 0), p + Vector3(s * 0.7, h, 0), 0.22, 0.22)
	k.beam("oak", p + Vector3(-0.85, h, 0), p + Vector3(0.85, h, 0), 0.22, 0.24)
	k.beam("oak", p + Vector3(-0.7, h * 0.65, 0), p + Vector3(0.7, h * 0.65, 0), 0.14, 0.14)
	for i in (1 if not big else 4):
		k.box("iron", p + Vector3(-0.3 + i * 0.2, h * 0.45, 0), Vector3(0.03, h * 0.5, 0.12))
	k.beam("dark_oak", p + Vector3(0, 0.6, -1.6), p + Vector3(0, 0.6, 1.6), 0.5, 0.12)
	k.cyl("log", p + Vector3(0, 0.85, -1.4), p + Vector3(0, 0.85, 1.2), 0.24, 9)
	k.wheel(p + Vector3(-1.1, 1.0, 0.0), 0.75, Vector3.RIGHT)

static func b21_sawmill54(k, L: int) -> Dictionary:
	## I open cross-gabled shed over a saw pit with a log and a two-man saw, sawhorses,
	## a workbench and a sawn-board stack. II a cabin at the left (gable to the street,
	## chimney, door, window, banner), the frame saw with a gear wheel in the open bay at
	## the right. III a raised deck with steps in front of the saw bay. IV a log claw on
	## the deck and lanterns. V a larger saw hall with a multi-blade frame and an outer
	## lean-to with log stacks.
	if L == 1:
		var c = Vector3(0.4, 0, -0.8)
		for sx in [-1.0, 0.0, 1.0]:
			for sz in [-1.0, 1.0]:
				var p = c + Vector3(sx * 2.8, 0, sz * 2.0)
				k.box("stone", p + Vector3(0, 0.12, 0), Vector3(0.4, 0.24, 0.4))
				k.beam("oak", p + Vector3(0, 0.24, 0), p + Vector3(0, 2.6, 0), 0.26, 0.26)
		for sz in [-1.0, 1.0]:
			k.beam("oak", c + Vector3(-3.0, 2.6, sz * 2.0), c + Vector3(3.0, 2.6, sz * 2.0), 0.22, 0.26)
		k.gable_roof("shingle", c + Vector3(-1.4, 2.65, 0), 3.0, 4.0, 1.5, 0.4)
		k.push_at(c + Vector3(1.4, 0, 0), 90)
		k.gable_roof("shingle", Vector3(0, 2.65, 0), 4.0, 2.8, 1.9, 0.4)
		k.pop()
		k.box("soil", c + Vector3(1.4, 0.02, 0.6), Vector3(1.0, 0.06, 3.2))
		k.cyl("log", c + Vector3(1.4, 0.35, -0.8), c + Vector3(1.4, 0.35, 2.4), 0.3, 9)
		k.box("iron", c + Vector3(1.4, 0.9, 0.8), Vector3(0.03, 1.4, 0.1))
		k.sawhorse(c + Vector3(-0.4, 0, 2.6), 90); k.sawhorse(c + Vector3(-1.4, 0, 2.8), 70)
		k.workbench(c + Vector3(-2.2, 0, -0.8), 1.6, 0)
		k.plank_stack(Vector3(4.2, 0, 2.8), 1.8, 0.8, 5, 0)
		return {"worker": Vector3(-3.2, 0.0, 3.4)}
	# cabin at the left
	var cab = Vector3(-3.4, 0, -1.0)
	_gable_house(k, cab, 3.0, 4.4, 2.6, 2.2, [{"at": 0.8, "w": 0.6, "y0": 0.9, "y1": 1.6, "kind": "window"}, {"at": 2.1, "w": 0.9, "y0": 0.0, "y1": 1.95, "kind": "door"}], [], "shingle", "plank", 0.5)
	k.chimney(Vector3(cab.x - 0.9, 3.0, cab.z - 1.4), 2.2, 0.6)
	k.banner(Vector3(cab.x, 3.6, cab.z + 2.4), 0.4, 0.7, "cloth_red")
	k.stairs(Vector3(cab.x + 0.6, 0, cab.z + 2.2 + 2 * 0.3), 1.0, 2, 0.25, 0.3, 0, "stone")
	# open saw bay at the right
	var bx = 1.6 if L <= 4 else 2.0
	var bw = 4.4 if L <= 4 else 5.2
	var bz = -1.0
	var bd = 4.4
	var hh = 3.0 if L <= 4 else 3.6
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			var p = Vector3(bx + sx * bw * 0.5, 0, bz + sz * bd * 0.5)
			k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.42, 0.3, 0.42))
			k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, hh, 0), 0.28, 0.28)
	k.gable_roof("shingle", Vector3(bx, hh + 0.05, bz), bw + 0.4, bd + 0.2, 1.6, 0.4)
	k.gable_frame(Vector3(bx, hh + 0.05, bz), bw + 0.4, bd + 0.2, 1.6)
	k.box("plank", Vector3(bx, hh * 0.5, bz - bd * 0.5 + 0.05), Vector3(bw, hh, 0.1))
	_saw_frame(k, Vector3(bx - 0.2, 0.0 if L == 2 else 0.6, bz + 0.2), L == 5)
	k.plank_stack(Vector3(bx + 1.6, 0.0 if L == 2 else 0.6, bz - 1.2), 1.6, 0.8, 5, 90)
	k.lantern(Vector3(bx + bw * 0.5 + 0.15, 2.0, bz + bd * 0.5))
	if L == 2:
		k.stairs(Vector3(bx - 1.2, 0, bz + bd * 0.5 + 0.8), 1.0, 2, 0.15, 0.3, 0, "oak", false)
	if L >= 3:
		k.deck(Vector3(bx - bw * 0.5, 0, bz - bd * 0.5 + 0.2), Vector3(bx + bw * 0.5, 0, bz + bd * 0.5 + 1.8), 0.6, "plank", true, true, true)
		k.stairs(Vector3(bx - 1.4, 0, bz + bd * 0.5 + 1.8 + 3 * 0.3), 1.0, 3, 0.2, 0.3, 0, "oak", false)
		k.railing(Vector3(bx - 0.8, 0.6, bz + bd * 0.5 + 1.8), Vector3(bx + bw * 0.5, 0.6, bz + bd * 0.5 + 1.8), 0.8)
	if L >= 4:
		k.beam("oak", Vector3(bx + 0.8, hh - 0.2, bz - 0.4), Vector3(bx + 0.8, hh - 0.2, bz + bd * 0.5 + 0.8), 0.18, 0.2)
		k.hook_hoist(Vector3(bx + 0.8, hh - 0.3, bz + 1.6), 1.2)
		for s in [-1.0, 1.0]:
			k.beam("iron", Vector3(bx + 0.8, 1.55, bz + 1.6), Vector3(bx + 0.8 + s * 0.3, 1.2, bz + 1.6), 0.05, 0.05)
		k.lantern(Vector3(bx - bw * 0.5 - 0.15, 2.0, bz + bd * 0.5))
	if L == 5:
		k.push_at(Vector3(bx + bw * 0.5 + 1.0, 0, bz + 0.6), 90)
		k.lean_to(Vector3.ZERO, 3.6, 1.8, 2.2, 2.8, "shingle", 3)
		k.pop()
		for i in 2:
			k.log_pile(Vector3(bx + bw * 0.5 + 1.0, 0, bz - 0.4 + i * 1.8), 1.4, 3, 0.15, 0)
		k.log_pile(Vector3(bx + 1.6, 0, 4.6), 2.4, 3, 0.18, 90)
	return {"worker": Vector3(-3.4, 0.0, 3.6)}

static func _wheat_field(k, x0: float, x1: float, z0: float, z1: float) -> void:
	k.ground(Vector3(x0, 0, z0), Vector3(x1, 0, z1), "soil", 0.03)
	var rows = int((x1 - x0) / 0.55)
	for i in rows:
		var x = x0 + 0.3 + i * 0.55
		k.box("hay", Vector3(x, 0.38, (z0 + z1) * 0.5), Vector3(0.4, 0.7, z1 - z0 - 0.4), 0, Color(1.08, 0.92, 0.66) * k.jitter(0.06))
		k.box("hay", Vector3(x, 0.78, (z0 + z1) * 0.5), Vector3(0.28, 0.12, z1 - z0 - 0.5), 0, Color(1.15, 0.98, 0.7))

static func _sheaf(k, p: Vector3) -> void:
	k.cyl("hay", p, p + Vector3(0, 0.8, 0), 0.22, 8, true, Color(1.1, 0.95, 0.55), 0.14)
	k.cone("hay", p + Vector3(0, 0.75, 0), 0.24, 0.3, 8, Color(1.15, 1.0, 0.55))

# ---------------------------------------------------------------- B22 Wheat Farm (ALT-05)
static func b22_wheat54(k, L: int) -> Dictionary:
	## I small farmhouse (gable to the street, wheat banner) at the back left, a large
	## fenced wheat field filling the front, sheaves by the house. II chimney and an open
	## sheaf shed at the right. III dormer, a barn with doors and a hoist, a threshing
	## floor under a lean-to. IV the shed and barn become one long open granary hall.
	## V a louvred monitor on the hall and a side lean-to.
	var h = Vector3(-4.2, 0, -3.6)
	_gable_house(k, h, 2.8, 3.0, 2.4, 1.8, [{"at": 1.6, "w": 0.8, "y0": 0.0, "y1": 1.85, "kind": "door"}, {"at": 0.6, "w": 0.5, "y0": 0.9, "y1": 1.5, "kind": "window"}], [], "shingle", "plank", 0.4)
	k.banner(Vector3(h.x + 1.55, 2.3, h.z + 1.2), 0.35, 0.7, "cloth_wine", 90)
	k.stairs(Vector3(h.x + 0.2, 0, h.z + 1.5 + 2 * 0.28), 1.0, 2, 0.2, 0.28, 0, "stone")
	k.barrel(Vector3(h.x - 1.2, 0, h.z + 1.9)); k.sack(Vector3(h.x - 0.8, 0, h.z + 2.0))
	_wheat_field(k, -4.6, 6.2, -0.6, 6.2)
	k.fence(Vector3(-4.8, 0, 6.4), Vector3(6.4, 0, 6.4), 0.8)
	k.fence(Vector3(6.4, 0, 6.4), Vector3(6.4, 0, -0.8), 0.8)
	k.fence(Vector3(-4.8, 0, 6.4), Vector3(-4.8, 0, 1.0), 0.8)
	k.road(Vector3(-5.8, 0, 6.6), Vector3(h.x + 0.2, 0, h.z + 2.4), 1.0, "path", 0.035, 0.2)
	if L == 1:
		for i in 3:
			_sheaf(k, Vector3(-2.2 + i * 0.5, 0, -2.4))
		k.fence(Vector3(-2.6, 0, -1.8), Vector3(-0.8, 0, -1.8), 0.6)
	if L >= 2:
		k.chimney(Vector3(h.x - 0.8, 2.8, h.z - 0.8), 1.8, 0.5)
		if L <= 3:
			k.open_shed(Vector3(-0.8, 0, -3.4), 3.0, 2.4, 2.2, 0.9, "shingle", 3, 2, true)
			for i in 4:
				_sheaf(k, Vector3(-1.9 + i * 0.7, 0, -3.4))
	if L >= 3:
		k.push_at(Vector3(h.x + 0.9, 2.9, h.z + 0.2))
		k.box("plank", Vector3(0, 0.35, 0), Vector3(0.8, 0.7, 0.8))
		k.window(Vector3(0.42, 0, 0), 0.4, 0.15, 0.55, 90)
		k.gable_roof("shingle", Vector3(0, 0.7, 0), 1.0, 1.0, 0.4, 0.1)
		k.pop()
		if L == 3:
			var b = Vector3(2.6, 0, -3.6)
			_gable_house(k, b, 2.8, 3.0, 2.8, 1.8, [{"at": 1.4, "w": 1.5, "y0": 0.0, "y1": 2.1, "kind": "double"}], [], "shingle", "plank", 0.3)
			k.beam("oak", Vector3(b.x, 3.4, b.z + 0.8), Vector3(b.x, 3.4, b.z + 2.0), 0.14, 0.16)
			k.hook_hoist(Vector3(b.x, 3.3, b.z + 1.9), 1.2)
			k.push_at(Vector3(5.2, 0, -3.2), 0)
			k.lean_to(Vector3.ZERO, 2.0, 2.4, 2.0, 2.4, "shingle", 2)
			k.pop()
			k.box("hay", Vector3(5.2, 0.15, -3.0), Vector3(1.6, 0.3, 1.6), 0, Color(1.1, 0.95, 0.55))
	if L >= 4:
		# long open granary hall at the back right
		var gh = Vector3(2.4, 0, -3.6)
		var gw = 7.0
		var gd = 3.6
		k.box("stone", gh + Vector3(0, 0.15, 0), Vector3(gw, 0.3, gd))
		for i in 5:
			var x = gh.x - gw * 0.5 + gw * i / 4.0
			for z in [gh.z - gd * 0.5, gh.z + gd * 0.5]:
				k.beam("oak", Vector3(x, 0.3, z), Vector3(x, 3.0, z), 0.26, 0.26)
		k.box("plank", gh + Vector3(0, 1.6, -gd * 0.5 + 0.05), Vector3(gw, 2.6, 0.1))
		k.gable_roof("shingle", gh + Vector3(0, 3.05, 0), gw + 0.4, gd + 0.2, 1.7, 0.4)
		k.gable_frame(gh + Vector3(0, 3.05, 0), gw + 0.4, gd + 0.2, 1.7)
		for i in 5:
			_sheaf(k, gh + Vector3(-2.6 + i * 0.6, 0.3, -0.8))
		for i in 4:
			k.sack(gh + Vector3(1.2 + (i % 2) * 0.4, 0.3, 0.2 + (i / 2) * 0.4), i * 20.0)
		k.crate(gh + Vector3(2.6, 0.3, 0.6), 0.6)
		for x in [gh.x - 2.4, gh.x + 1.8]:
			k.lantern(Vector3(x, 2.4, gh.z + gd * 0.5 + 0.15))
	if L == 5:
		var gh = Vector3(2.4, 0, -3.6)
		k.box("plank", gh + Vector3(0, 5.0, 0), Vector3(3.0, 0.8, 1.2))
		for i in 4:
			_louvre(k, gh + Vector3(-1.1 + i * 0.73, 5.0, 0.62), 0.5, 0.5, 0)
		k.gable_roof("shingle", gh + Vector3(0, 5.4, 0), 3.2, 1.4, 0.5, 0.2)
		k.push_at(Vector3(h.x + 1.0, 0, h.z + 2.1), 0)
		k.lean_to(Vector3.ZERO, 1.6, 1.0, 1.9, 2.3, "shingle", 2)
		k.pop()
	return {"worker": Vector3(-5.6, 0.0, -0.6)}

# ---------------------------------------------------------------- B23 Hunting Lodge (ALT-06)
static func _log_walls(k, c: Vector3, lx: float, lz: float, h: float, door_x := 0.0, wins: Array = []) -> void:
	## Log-cabin walls: round logs with crossed corners, a door gap on the front.
	var n = int(h / 0.28)
	for i in n:
		var y = c.y + 0.14 + i * 0.28
		for z in [c.z - lz * 0.5, c.z + lz * 0.5]:
			if z > c.z and y < c.y + 1.95:
				for seg in [[c.x - lx * 0.5 - 0.25, c.x + door_x - 0.5], [c.x + door_x + 0.5, c.x + lx * 0.5 + 0.25]]:
					k.cyl("log", Vector3(seg[0], y, z), Vector3(seg[1], y, z), 0.15, 7, true, k.jitter(0.08))
			else:
				k.cyl("log", Vector3(c.x - lx * 0.5 - 0.25, y, z), Vector3(c.x + lx * 0.5 + 0.25, y, z), 0.15, 7, true, k.jitter(0.08))
		for x in [c.x - lx * 0.5, c.x + lx * 0.5]:
			k.cyl("log", Vector3(x, y + 0.14, c.z - lz * 0.5 - 0.25), Vector3(x, y + 0.14, c.z + lz * 0.5 + 0.25), 0.15, 7, true, k.jitter(0.08))
	k.box("soot", Vector3(c.x, c.y + h * 0.5, c.z), Vector3(lx - 0.1, h, lz - 0.1))
	k.door(Vector3(c.x + door_x, c.y, c.z + lz * 0.5), 0.95, 1.95, 0, 0.0)
	for w in wins:
		k.window(Vector3(c.x + w, c.y, c.z + lz * 0.5 + 0.12), 0.55, 0.9, 1.5, 0)

static func b23_lodge54(k, L: int) -> Dictionary:
	## I log lodge (gable to the street) on a stone footing: door with a hood on posts,
	## shuttered windows, antlers and a banner on the gable, stone chimney at the left,
	## bow rack and chest by the door. II a lean-to workshop at the right. III a dormer and
	## a railed veranda with a table along the right. IV the veranda extends with a log
	## store, a drying rack and stepping stones. V a stone side store and a taller chimney.
	var c = Vector3(-1.6, 0.4, -1.4)
	var lx = 4.4
	var lz = 4.6
	var front = c.z + lz * 0.5
	k.box("stone", Vector3(c.x, 0.2, c.z), Vector3(lx + 0.6, 0.4, lz + 0.6), 0, k.jitter(0.04))
	_log_walls(k, c, lx, lz, 2.5, 0.0, [-1.4, 1.4])
	var ey = c.y + 2.5
	k.push_at(Vector3(c.x, 0, c.z), 90)
	k.gable_roof("shingle", Vector3(0, ey, 0), lz + 0.4, lx + 0.4, 2.0, 0.45, "log")
	k.gable_frame(Vector3(0, ey, 0), lz + 0.4, lx + 0.4, 2.0)
	k.pop()
	k.banner(Vector3(c.x, ey + 0.9, front + 0.45), 0.4, 0.6, "cloth_wine")
	for s in [-1.0, 1.0]:
		k.beam("dark_oak", Vector3(c.x, ey + 1.5, front + 0.45), Vector3(c.x + s * 0.5, ey + 1.9, front + 0.5), 0.05, 0.05)
		k.beam("dark_oak", Vector3(c.x + s * 0.35, ey + 1.75, front + 0.48), Vector3(c.x + s * 0.55, ey + 1.6, front + 0.5), 0.04, 0.04)
	k.chimney(Vector3(c.x - lx * 0.5 - 0.1, 0.4, c.z - 1.0), 5.2 if L < 5 else 5.8, 0.8)
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(c.x + s * 0.7, c.y, front + 0.8), Vector3(c.x + s * 0.7, c.y + 2.2, front + 0.8), 0.16, 0.16)
	k.push_at(Vector3(c.x, 0, front + 0.5), 90)
	k.gable_roof("shingle", Vector3(0, c.y + 2.25, 0), 0.8, 1.7, 0.6, 0.15)
	k.pop()
	k.stairs(Vector3(c.x, 0, front + 1.0 + 2 * 0.3), 1.6, 2, 0.2, 0.3, 0, "stone")
	k.weapon_rack(Vector3(c.x + 1.4, c.y, front + 0.4), 0.9, 0)
	k.box("oak", Vector3(c.x - 1.3, c.y + 0.25, front + 0.45), Vector3(0.8, 0.5, 0.45))
	k.lantern(Vector3(c.x + 0.9, c.y + 1.9, front + 0.2))
	if L >= 2 and L <= 2:
		k.push_at(Vector3(c.x + lx * 0.5 + 1.0, 0, c.z + 0.6), 90)
		k.lean_to(Vector3.ZERO, 2.6, 1.8, 2.0, 2.6, "shingle", 2)
		k.pop()
		k.workbench(Vector3(c.x + lx * 0.5 + 1.0, 0, c.z + 0.6), 1.2, 90)
		k.log_pile(Vector3(c.x + lx * 0.5 + 1.0, 0, c.z - 0.6), 1.0, 2, 0.12, 0)
	if L >= 3:
		k.push_at(Vector3(c.x + 1.0, ey + 0.7, c.z + 0.6))
		k.box("plank", Vector3(0, 0.4, 0), Vector3(1.0, 0.8, 1.0))
		k.window(Vector3(0.52, 0, 0), 0.45, 0.2, 0.65, 90)
		k.gable_roof("shingle", Vector3(0, 0.8, 0), 1.2, 1.1, 0.45, 0.12)
		k.pop()
		var vx0 = c.x + lx * 0.5
		var vx1 = vx0 + (2.6 if L == 3 else 4.2)
		k.deck(Vector3(vx0, 0, c.z - lz * 0.5 + 0.4), Vector3(vx1, 0, front + 0.6), 0.6, "plank", true, true, true)
		k.push_at(Vector3((vx0 + vx1) * 0.5, 0.6, (c.z - lz * 0.5 + 0.4 + front + 0.6) * 0.5), 90)
		k.lean_to(Vector3.ZERO, lz + 0.2, vx1 - vx0, 2.1, 2.7, "shingle", 3)
		k.pop()
		k.railing(Vector3(vx0, 0.6, front + 0.6), Vector3(vx1, 0.6, front + 0.6), 0.8)
		k.table(Vector3(vx0 + 1.2, 0.6, c.z + 0.6), 1.2, 0.7, 0.8)
		k.box("parchment", Vector3(vx0 + 1.2, 1.45, c.z + 0.6), Vector3(0.7, 0.04, 0.5), 0, Color(0.8, 0.62, 0.42))
		k.stairs(Vector3(vx0 + 0.6, 0, front + 0.6 + 2 * 0.3), 0.8, 2, 0.3, 0.3, 0, "oak", false)
		k.log_pile(Vector3((vx0 + vx1) * 0.5 + 0.3, 0, front + 0.35), vx1 - vx0 - 0.8, 2, 0.1, 90)
	if L >= 4:
		_drying_rack(k, Vector3(3.6, 0, 3.6), 1.4, 0, true)
		for i in 5:
			k.box("stone_light", Vector3(c.x + 0.4 + i * 0.6, 0.03, front + 2.0 + (i % 2) * 0.3), Vector3(0.45, 0.06, 0.38), i * 17.0)
		k.cyl("log", Vector3(1.8, 0, 4.6), Vector3(1.8, 0.5, 4.6), 0.3, 9)
	if L == 5:
		var st = Vector3(c.x + lx * 0.5 + 3.8, 0, c.z - 0.6)
		k.box("stone", st + Vector3(0, 1.1, 0), Vector3(1.8, 2.2, 2.4), 0, k.jitter(0.04))
		k.push_at(st, 90)
		k.gable_roof("shingle", Vector3(0, 2.2, 0), 2.6, 2.0, 0.9, 0.2)
		k.pop()
		k.door(Vector3(st.x, 0, st.z + 1.22), 0.8, 1.7, 0, 0.0)
	return {"worker": Vector3(-4.6, 0.0, 3.2)}

# ---------------------------------------------------------------- B24 Fishing Hut (ALT-07)
static func _net_frame(k, p: Vector3, w := 2.2, yaw := 0.0) -> void:
	k.push_at(p, yaw)
	for s in [-1.0, 1.0]:
		k.beam("oak", Vector3(s * w * 0.5, 0, 0), Vector3(s * w * 0.5, 2.6, 0), 0.12, 0.12)
	k.beam("oak", Vector3(-w * 0.5 - 0.1, 2.5, 0), Vector3(w * 0.5 + 0.1, 2.5, 0), 0.1, 0.1)
	k.next_piece()
	_quad2(k, "linen", Vector3(-w * 0.45, 2.45, 0), Vector3(w * 0.45, 2.45, 0), Vector3(w * 0.3, 1.0, 0.1), Vector3(-w * 0.3, 1.2, 0.1), Color(0.85, 0.82, 0.7))
	k.pop()

static func b24_fishing54(k, L: int) -> Dictionary:
	## I plank hut (gable to the street, chimney, lantern) on the shore with a short
	## landing stage into the water at the right, nets, baskets and pots. II a covered work
	## deck on piles over the water with racks and a net-drying frame. III a cleaning
	## table and a basin under the deck roof. IV a railed jetty with a raised post under its
	## own roof and a fish basket on a hoist. V a store hut at the end and a fish-drying rack.
	k.box("water", Vector3(3.4, -0.02, 0.4), Vector3(6.8, 0.06, 12.4))
	k.ground_poly(PackedVector2Array([Vector2(-6.6, -6.2), Vector2(0.4, -6.2), Vector2(0.9, -2.0), Vector2(0.2, 2.0), Vector2(0.8, 6.6), Vector2(-6.6, 6.6)]), "earth", 0.04)
	for i in 6:
		k.stone_block(Vector3(0.6 + (i % 2) * 0.3, -0.05, -4.0 + i * 1.6), Vector3(0.5, 0.3, 0.4), i * 30.0, true)
	var c = Vector3(-2.4, 0, -1.2)
	_gable_house(k, c, 3.4, 3.8, 2.4, 2.0, [{"at": 1.0, "w": 0.9, "y0": 0.0, "y1": 1.9, "kind": "door"}, {"at": 2.4, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}],
		[{"at": 1.9, "w": 0.6, "y0": 0.9, "y1": 1.5, "kind": "window"}], "shingle", "plank", 0.35)
	k.chimney(Vector3(c.x - 0.9, 2.6, c.z - 1.0), 1.8, 0.55)
	k.lantern(Vector3(c.x - 1.4, 2.0, c.z + 2.1))
	k.stairs(Vector3(c.x - 0.7, 0, c.z + 1.9 + 2 * 0.28), 1.0, 2, 0.18, 0.28, 0, "stone")
	for p in [Vector3(c.x + 0.4, 0, c.z + 2.6), Vector3(c.x + 0.9, 0, c.z + 2.8)]:
		k.cyl("hay", p, p + Vector3(0, 0.4, 0), 0.25, 9, true, k.jitter(0.1), 0.3)
	var dy = 0.45
	var dx1 = 2.6 if L == 1 else (4.4 if L <= 3 else 5.6)
	k.deck(Vector3(c.x + 1.7, 0, c.z - 0.4), Vector3(dx1, 0, c.z + 1.6), dy, "plank", true, true, true)
	if L == 1:
		k.box("linen", Vector3(c.x + 1.75, 1.4, c.z + 0.8), Vector3(0.05, 1.0, 1.2), 0, Color(0.85, 0.82, 0.7))
	if L >= 2:
		var rx = c.x + 2.9
		k.push_at(Vector3(rx, dy, c.z + 0.6), 90)
		k.lean_to(Vector3.ZERO, 2.2, 2.4, 2.0, 2.5, "shingle", 2)
		k.pop()
		k.box("plank", Vector3(rx, dy + 1.2, c.z - 0.3), Vector3(2.0, 1.4, 0.3))
		for i in 3:
			k.barrel(Vector3(rx - 0.6 + i * 0.5, dy, c.z - 0.2), 0.5, 0.2)
		_net_frame(k, Vector3(c.x + 4.6, 0, c.z - 1.6), 2.2, 0)
	if L >= 3:
		k.table(Vector3(c.x + 3.2, dy, c.z + 1.0), 1.2, 0.6, 0.85)
		k.cyl("water", Vector3(c.x + 3.6, dy + 0.85, c.z + 1.0), Vector3(c.x + 3.6, dy + 0.9, c.z + 1.0), 0.2, 8)
	if L >= 4:
		k.deck(Vector3(dx1 - 1.4, 0, c.z + 1.6), Vector3(dx1, 0, 5.6), dy, "plank", true, true, true)
		k.railing(Vector3(dx1, dy, c.z + 1.6), Vector3(dx1, dy, 5.6), 0.8)
		var pp = Vector3(dx1 - 0.7, dy, c.z - 1.6)
		k.deck(pp + Vector3(-0.9, -dy, -0.9), pp + Vector3(0.9, -dy, 0.9), dy + 1.4, "plank", true, true, true)
		k.gable_roof("shingle", pp + Vector3(0, 3.6, 0), 2.0, 2.0, 0.9, 0.3)
		for sx in [-0.85, 0.85]:
			for sz in [-0.85, 0.85]:
				k.beam("oak", pp + Vector3(sx, 1.4, sz), pp + Vector3(sx, 3.6, sz), 0.14, 0.14)
		k.beam("oak", Vector3(dx1 - 0.7, dy, 4.2), Vector3(dx1 - 0.7, dy + 2.6, 4.2), 0.18, 0.18)
		k.beam("oak", Vector3(dx1 - 0.7, dy + 2.5, 4.2), Vector3(dx1 + 0.6, dy + 2.5, 4.2), 0.14, 0.14)
		k.cyl("rope", Vector3(dx1 + 0.5, dy + 2.4, 4.2), Vector3(dx1 + 0.5, dy + 1.2, 4.2), 0.025, 5, false)
		k.cyl("hay", Vector3(dx1 + 0.5, dy + 0.7, 4.2), Vector3(dx1 + 0.5, dy + 1.2, 4.2), 0.3, 9, true, k.jitter(0.1), 0.2)
	if L == 5:
		var sh = Vector3(dx1 - 0.7, dy, 1.2)
		_gable_house(k, sh, 1.4, 1.6, 1.8, 0.8, [{"at": 0.7, "w": 0.7, "y0": 0.0, "y1": 1.6, "kind": "door"}], [], "shingle", "plank", 0.05)
		_drying_rack(k, Vector3(c.x + 3.6, dy, c.z + 1.4), 1.4, 0, false)
	return {"worker": Vector3(-4.4, 0.0, 3.2)}

# ---------------------------------------------------------------- B25 Herbal Garden (ALT-08)
static func _planter(k, p: Vector3, w := 1.4, d := 0.7, plant := "lavender") -> void:
	k.box("plank", p + Vector3(0, 0.15, 0), Vector3(w, 0.3, d), 0, k.jitter(0.06))
	for i in int(w / 0.35):
		k.bush(p + Vector3(-w * 0.5 + 0.2 + i * 0.35, 0.25, 0), 0.2, plant if i % 3 != 2 else "herb")

static func b25_herbal54(k, L: int) -> Dictionary:
	## I open stand with hanging herb bundles, pots and baskets at the back right, free
	## lavender and sage plantings round a trodden patch. II the stand closed at the side
	## with a door, shelves and a drying ladder, timber planters. III a half-timbered
	## cottage with a chimney, banner and dormer, a glazed lean-to and a herb drying rack
	## on the roof. IV a low stone garden wall with a gate, a two-level drying gallery.
	## V a full greenhouse along the right and a rose arbour.
	k.ground_poly(_oval(0, 0.4, 5.2, 4.8), "earth", 0.025)
	for p in [Vector3(-3.6, 0, 2.6), Vector3(-1.4, 0, 3.4), Vector3(1.4, 0, 3.6), Vector3(-3.0, 0, -0.6), Vector3(3.4, 0, 2.6)]:
		k.bush(p, 0.45, "lavender" if int(p.x) % 2 == 0 else "herb")
	if L <= 2:
		var st = Vector3(2.8, 0, -1.6)
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				k.beam("oak", st + Vector3(sx * 1.1, 0, sz * 0.8), st + Vector3(sx * 1.1, 2.3, sz * 0.8), 0.16, 0.16)
		k.push_at(st, 0)
		k.lean_to(Vector3.ZERO, 2.4, 1.8, 2.2, 2.5, "shingle", 0)
		k.pop()
		k.table(st, 1.8, 0.7, 0.85)
		for i in 5:
			k.box("herb", st + Vector3(-0.8 + i * 0.4, 1.8, 0.0), Vector3(0.12, 0.35, 0.12))
		for i in 3:
			k.cyl("clay_roof", st + Vector3(-0.6 + i * 0.5, 0.88, 0.1), st + Vector3(-0.6 + i * 0.5, 1.1, 0.1), 0.1, 8)
		k.cyl("hay", st + Vector3(1.4, 0, 0.9), st + Vector3(1.4, 0.35, 0.9), 0.25, 9)
		if L == 2:
			k.box("plank", st + Vector3(1.15, 1.15, 0), Vector3(0.1, 2.3, 1.6))
			k.door(st + Vector3(1.22, 0, 0.0), 0.7, 1.8, 90, 0.0)
			for s in [-0.4, 0.4]:
				k.beam("oak", st + Vector3(1.6 + s, 0, 1.4), st + Vector3(1.6 + s * 0.6, 1.8, 1.2), 0.06, 0.06)
			for y in [0.6, 1.1, 1.6]:
				k.beam("oak", st + Vector3(1.2, y, 1.3), st + Vector3(2.0, y, 1.3), 0.04, 0.04)
			k.lantern(st + Vector3(1.3, 1.9, 0.9))
			_planter(k, Vector3(-3.2, 0, 3.4)); _planter(k, Vector3(-0.4, 0, 3.6), 1.4, 0.7, "herb"); _planter(k, Vector3(2.0, 0, 3.6))
		return {"worker": Vector3(-1.0, 0.0, 1.8)}
	var c = Vector3(-1.8, 0, -1.8)
	_gable_house(k, c, 3.6, 3.6, 2.6, 2.2, [{"at": 1.8, "w": 0.9, "y0": 0.0, "y1": 2.0, "kind": "door"}, {"at": 0.6, "w": 0.5, "y0": 0.9, "y1": 1.5, "kind": "window"}, {"at": 3.0, "w": 0.5, "y0": 0.9, "y1": 1.5, "kind": "window"}],
		[], "shingle", "plaster", 0.5)
	k.chimney(Vector3(c.x - 1.4, 0.5, c.z - 0.6), 5.4, 0.7)
	k.banner(Vector3(c.x, 3.9, c.z + 2.25), 0.4, 0.7, "cloth_wine")
	k.stairs(Vector3(c.x, 0, c.z + 1.8 + 2 * 0.3), 1.2, 2, 0.25, 0.3, 0, "stone")
	k.push_at(Vector3(c.x + 1.0, 3.3, c.z + 0.2))
	k.box("plaster", Vector3(0, 0.35, 0), Vector3(0.8, 0.7, 0.8))
	k.window(Vector3(0.42, 0, 0), 0.4, 0.15, 0.55, 90)
	k.gable_roof("shingle", Vector3(0, 0.7, 0), 1.0, 1.0, 0.4, 0.1)
	k.pop()
	# glazed lean-to at the right of the cottage
	var g = Vector3(c.x + 3.0, 0, c.z + 0.2)
	var gl = 2.4 if L <= 4 else 4.6
	k.box("stone", g + Vector3(gl * 0.5 - 1.2, 0.25, 0), Vector3(gl, 0.5, 3.2), 0, k.jitter(0.04))
	for i in int(gl / 0.8) + 1:
		k.beam("oak", g + Vector3(-1.2 + i * 0.8, 0.5, 1.6), g + Vector3(-1.2 + i * 0.8, 2.2, 1.6), 0.08, 0.08)
	k.box("greenglass", g + Vector3(gl * 0.5 - 1.2, 1.35, 1.6), Vector3(gl, 1.7, 0.04))
	k.box("greenglass", g + Vector3(gl * 0.5 - 1.2, 2.55, 0.4), Vector3(gl, 0.04, 2.6), 0, Color.WHITE, -25)
	k.table(g + Vector3(0, 0.5, 0.4), 1.6, 0.6, 0.8)
	for i in 4:
		k.bush(g + Vector3(-0.6 + i * 0.4, 1.35, 0.4), 0.16, "herb")
	# herb drying rack on top of the lean-to
	var r = g + Vector3(0.0, 2.6, -0.8)
	for s in [-0.7, 0.7]:
		k.beam("oak", r + Vector3(s, 0, 0), r + Vector3(s, 1.3, 0), 0.08, 0.08)
	for y in [0.6, 1.2]:
		k.beam("oak", r + Vector3(-0.8, y, 0), r + Vector3(0.8, y, 0), 0.06, 0.06)
		for i in 4:
			k.box("lavender", r + Vector3(-0.5 + i * 0.33, y - 0.2, 0), Vector3(0.1, 0.3, 0.1))
	_planter(k, Vector3(-3.6, 0, 2.6)); _planter(k, Vector3(-1.2, 0, 3.2), 1.4, 0.7, "herb"); _planter(k, Vector3(1.4, 0, 3.0))
	k.barrel(Vector3(c.x - 1.0, 0, c.z + 2.4))
	if L >= 4:
		var n = 24
		for i in n:
			var a0 = TAU * i / n
			var a1 = TAU * (i + 1) / n
			if absf(angle_difference((a0 + a1) * 0.5, PI * 0.5)) < 0.2:
				continue
			if sin((a0 + a1) * 0.5) < -0.2:
				continue
			var p0 = Vector3(cos(a0) * 4.9, 0, 0.4 + sin(a0) * 4.6)
			var p1 = Vector3(cos(a1) * 4.9, 0, 0.4 + sin(a1) * 4.6)
			k.box("stone", (p0 + p1) * 0.5 + Vector3(0, 0.4, 0), Vector3(p0.distance_to(p1) + 0.05, 0.8, 0.45), rad_to_deg(-atan2(p1.z - p0.z, p1.x - p0.x)), k.jitter(0.05))
		_gate(k, Vector3(0, 0, 5.0), 1.0, 0, 0.0)
		k.deck(r + Vector3(-1.2, -2.6, -0.6), r + Vector3(1.2, -2.6, 0.5), 2.65, "plank", false, true, true)
		k.gable_roof("shingle", r + Vector3(0, 1.6, -0.1), 2.6, 1.4, 0.7, 0.2)
	if L == 5:
		var ar = Vector3(-4.0, 0, 1.2)
		for s in [-0.6, 0.6]:
			k.beam("oak", ar + Vector3(0, 0, s), ar + Vector3(0, 2.2, s), 0.1, 0.1)
		k.beam("oak", ar + Vector3(0, 2.2, -0.7), ar + Vector3(0, 2.2, 0.7), 0.1, 0.1)
		k.bush(ar + Vector3(0, 1.6, 0), 0.5, "flower")
		for i in 3:
			_planter(k, g + Vector3(0.4 + i * 1.1, 0.5, -0.6), 0.9, 0.6, "herb")
	return {"worker": Vector3(-1.0, 0.0, 4.2)}

# ---------------------------------------------------------------- B26 Stone Workshop (ALT-09)
static func b26_stonework54(k, L: int) -> Dictionary:
	## I open shed with a mason's bench, a tool board and roughly cut blocks, a squared
	## block in front. II a double open shed on a paved floor with stacked blocks, steps,
	## a drawing table. III a half-timbered cottage (gable to the street, chimney, arched
	## door, banner) at the left of the open workshop with a grinding wheel and shelves.
	## IV a gantry hoist with a hanging block inside the workshop. V a tall workshop hall
	## with block shelving, a louvred cupola and a delivery stair.
	var w0 = Vector3(1.0, 0, -1.2)
	var ww = 4.6 if L <= 2 else 4.2
	var wd = 3.8
	if L >= 2:
		k.paving(w0 + Vector3(-ww * 0.5 - (2.4 if L == 2 else 0.0), 0, -wd * 0.5), w0 + Vector3(ww * 0.5, 0, wd * 0.5 + 0.3), 0.18, 0.5)
		k.stairs(w0 + Vector3(0.8, 0, wd * 0.5 + 0.3 + 0.6), 1.4, 2, 0.09, 0.3, 0, "stone_light")
	var hh = 2.6 if L <= 4 else 3.4
	for sx in [-1.0, 0.0, 1.0]:
		for sz in [-1.0, 1.0]:
			var p = w0 + Vector3(sx * ww * 0.5, 0, sz * wd * 0.5)
			k.box("stone", p + Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 0.4))
			k.beam("oak", p + Vector3(0, 0.3, 0), p + Vector3(0, hh, 0), 0.24, 0.24)
	if L <= 4:
		k.gable_roof("shingle", w0 + Vector3(0, hh + 0.05, 0), ww + 0.2, wd + 0.2, 1.3, 0.35)
	else:
		k.gable_roof("shingle", w0 + Vector3(0, hh + 0.05, 0), ww + 0.2, wd + 0.2, 1.9, 0.35, "plank")
		_vent_cupola(k, w0 + Vector3(0, hh + 1.7, 0), 0.8)
		for i in 3:
			k.box("plank", w0 + Vector3(ww * 0.5 - 0.3, 0.6 + i * 0.8, 0), Vector3(0.6, 0.06, wd - 0.4))
			for j in 3:
				k.stone_block(w0 + Vector3(ww * 0.5 - 0.3, 0.64 + i * 0.8, -1.0 + j * 1.0), Vector3(0.45, 0.35, 0.6))
	k.box("plank", w0 + Vector3(0, hh * 0.5, -wd * 0.5 + 0.05), Vector3(ww, hh, 0.1))
	k.workbench(w0 + Vector3(-0.6, 0.0 if L == 1 else 0.18, -1.0), 1.8, 0)
	k.stone_block(w0 + Vector3(-0.4, 0.98 if L > 1 else 0.8, -1.0), Vector3(0.6, 0.35, 0.4))
	for i in 3:
		k.stone_block(w0 + Vector3(1.2 + (i % 2) * 0.6, 0.0 if L == 1 else 0.18, -0.6 + (i / 2) * 0.6), Vector3(0.55, 0.45, 0.5), i * 6.0, true)
	k.stone_block(w0 + Vector3(-0.6, 0, wd * 0.5 + 1.4), Vector3(1.0, 0.6, 0.8))
	if L == 2:
		var w1 = w0 + Vector3(-ww * 0.5 - 1.2, 0, 0)
		for sz in [-1.0, 1.0]:
			k.beam("oak", w1 + Vector3(-1.2, 0.18, sz * wd * 0.5), w1 + Vector3(-1.2, 2.2, sz * wd * 0.5), 0.22, 0.22)
		k.push_at(w1, -90)
		k.lean_to(Vector3.ZERO, wd, 2.4, 2.2, 2.6, "shingle", 0)
		k.pop()
		for i in 4:
			k.stone_block(w1 + Vector3(-0.4 + (i % 2) * 0.7, 0.18 + (i / 2) * 0.45, -0.6), Vector3(0.6, 0.42, 0.7))
		k.table(w1 + Vector3(0, 0.18, 1.0), 1.2, 0.7, 0.85)
		k.box("parchment", w1 + Vector3(0, 1.04, 1.0), Vector3(0.8, 0.01, 0.5))
	if L >= 3:
		var c = Vector3(w0.x - ww * 0.5 - 2.0, 0, -1.0)
		_gable_house(k, c, 3.6, 4.2, 2.6, 2.2, [{"at": 1.4, "w": 0.95, "y0": 0.0, "y1": 2.0, "kind": "door"}, {"at": 0.5, "w": 0.5, "y0": 0.9, "y1": 1.5, "kind": "window"}],
			[], "shingle", "plaster", 0.5)
		k.chimney(Vector3(c.x - 1.3, 0.5, c.z - 1.0), 5.0, 0.7)
		k.banner(Vector3(c.x + 1.82, 2.0, c.z + 1.6), 0.35, 0.7, "cloth_wine", 90)
		k.stairs(Vector3(c.x - 0.4, 0, c.z + 2.1 + 2 * 0.3), 1.2, 2, 0.25, 0.3, 0, "stone")
		k.wheel(w0 + Vector3(-0.2, 0.9, 0.6), 0.55, Vector3.RIGHT, "stone_light")
		k.box("oak", w0 + Vector3(-0.2, 0.5, 0.6), Vector3(0.3, 0.7, 0.9))
	if L >= 4:
		var gx = w0.x - 0.2
		for s in [-1.0, 1.0]:
			k.beam("oak", Vector3(gx + s * 1.0, 0.18, w0.z + 0.8), Vector3(gx + s * 1.0, hh - 0.2, w0.z + 0.8), 0.18, 0.18)
		k.beam("oak", Vector3(gx - 1.1, hh - 0.2, w0.z + 0.8), Vector3(gx + 1.1, hh - 0.2, w0.z + 0.8), 0.2, 0.22)
		k.hook_hoist(Vector3(gx, hh - 0.3, w0.z + 0.8), hh - 1.6)
		k.stone_block(Vector3(gx - 0.3, 1.1, w0.z + 0.8), Vector3(0.6, 0.4, 0.5))
	if L == 5:
		k.stairs(w0 + Vector3(ww * 0.5 - 0.6, 0, wd * 0.5 + 1.6), 1.0, 4, 0.18, 0.3, 0, "stone_light")
	return {"worker": Vector3(-1.6, 0.0, 3.8)}

# ---------------------------------------------------------------- B27 Smelter (ALT-10)
static func _furnace(k, p: Vector3, stone := false, tall := false) -> void:
	var mat = "stone" if stone else "clay_roof"
	var r = 1.0
	for i in 5:
		var t0 = float(i) / 5.0
		var t1 = float(i + 1) / 5.0
		k.cyl(mat, p + Vector3(0, t0 * 1.8, 0), p + Vector3(0, t1 * 1.8, 0), r * cos(t0 * 1.1), 14, i == 4, k.jitter(0.05), r * cos(t1 * 1.1))
	k.box("soot", p + Vector3(0, 0.45, r * 0.85), Vector3(0.6, 0.6, 0.2))
	k.box("ember", p + Vector3(0, 0.3, r * 0.9), Vector3(0.45, 0.25, 0.1))
	k.box("glow", p + Vector3(0, 0.45, r * 0.95), Vector3(0.35, 0.2, 0.04))
	if tall:
		k.box("stone", p + Vector3(0, 4.2, 0), Vector3(1.1, 5.2, 1.1), 0, k.jitter(0.04))
		k.box("stone_light", p + Vector3(0, 6.9, 0), Vector3(1.35, 0.2, 1.35))
		for s in [-1.0, 1.0]:
			k.box("stone", p + Vector3(s * 0.52, 7.15, 0), Vector3(0.22, 0.35, 1.1))
		k.pyramid_roof("shingle", p + Vector3(0, 7.35, 0), 1.3, 0.45, 0.1, false)

static func _bellows(k, p: Vector3) -> void:
	k.box("dark_oak", p + Vector3(0, 0.35, 0), Vector3(0.6, 0.7, 1.2))
	k.push_at(p + Vector3(0, 0.8, 0))
	k.extrude("cloth_wine", PackedVector2Array([Vector2(-0.4, -0.2), Vector2(0.9, 0.0), Vector2(0.9, 0.12), Vector2(-0.4, 0.35)]), -0.35, 0.35)
	k.pop()
	k.beam("oak", p + Vector3(-0.4, 1.0, 0), p + Vector3(-1.1, 1.5, 0), 0.08, 0.08)

static func b27_smelter54(k, L: int) -> Dictionary:
	## I open gabled smelting shed (ridge along the street) with a clay bloomery furnace on
	## the right, a bellows and ore and charcoal baskets on the left, flagstones in front.
	## II the furnace rebuilt in stone, a charcoal wood rack, ingots on a block. III a tall
	## stone chimney rising from the furnace through the roof. IV a lean-to at the right
	## with an ingot table and paving. V the shed closed with plank wings at both ends,
	## ingot shelving.
	var c = Vector3(0.0, 0, -1.0)
	var lx = 7.4
	var lz = 4.6
	var h = 2.7
	for i in 4:
		var x = c.x - lx * 0.5 + lx * i / 3.0
		for z in [c.z - lz * 0.5, c.z + lz * 0.5]:
			k.box("stone", Vector3(x, 0.18, z), Vector3(0.45, 0.36, 0.45))
			k.beam("oak", Vector3(x, 0.36, z), Vector3(x, h, z), 0.28, 0.28)
			if i < 3:
				k.beam("oak", Vector3(x, h - 0.7, z), Vector3(x + 0.7, h - 0.02, z), 0.12, 0.12)
			if i > 0:
				k.beam("oak", Vector3(x, h - 0.7, z), Vector3(x - 0.7, h - 0.02, z), 0.12, 0.12)
	for z in [c.z - lz * 0.5, c.z + lz * 0.5]:
		k.beam("oak", Vector3(c.x - lx * 0.5 - 0.2, h, z), Vector3(c.x + lx * 0.5 + 0.2, h, z), 0.24, 0.28)
	k.gable_roof("shingle", Vector3(c.x, h + 0.1, c.z), lx, lz, 1.8, 0.45)
	k.gable_frame(Vector3(c.x, h + 0.1, c.z), lx, lz, 1.8)
	var fp = Vector3(c.x + 1.4, 0, c.z - 0.2)
	_furnace(k, fp, L >= 2, L >= 3)
	_bellows(k, Vector3(c.x - 0.6, 0, c.z - 0.2))
	for i in 3:
		var bp = Vector3(c.x - 2.8 + (i % 2) * 0.7, 0, c.z + 0.8 - (i / 2) * 0.8)
		k.cyl("hay", bp, bp + Vector3(0, 0.5, 0), 0.3, 10, true, k.jitter(0.1), 0.36)
		k.cone("ore" if i != 1 else "soot", bp + Vector3(0, 0.45, 0), 0.32, 0.25, 8, Color(1.3, 1.0, 0.85) if i != 1 else Color.WHITE)
	for i in 3:
		k.box("stone_light", Vector3(c.x - 0.6 + i * 0.7, 0.03, c.z + lz * 0.5 + 0.7 + (i % 2) * 0.2), Vector3(0.6, 0.06, 0.45), i * 12.0)
	if L >= 2:
		k.box("plank", Vector3(c.x - 2.6, 0.9, c.z - lz * 0.5 + 0.5), Vector3(1.6, 1.8, 0.6))
		k.log_pile(Vector3(c.x - 2.6, 0, c.z - lz * 0.5 + 0.55), 1.4, 3, 0.1, 90)
		k.box("stone", Vector3(c.x + 3.0, 0.3, c.z + 1.4), Vector3(0.8, 0.6, 0.6))
		for i in 3:
			k.box("iron", Vector3(c.x + 2.8 + (i % 2) * 0.35, 0.66 + (i / 2) * 0.08, c.z + 1.4), Vector3(0.3, 0.08, 0.12))
	if L >= 4:
		k.push_at(Vector3(c.x + lx * 0.5 + 1.1, 0, c.z + 0.4), 90)
		k.lean_to(Vector3.ZERO, lz - 0.6, 2.0, 2.1, 2.6, "shingle", 2)
		k.pop()
		k.table(Vector3(c.x + lx * 0.5 + 1.1, 0, c.z + 0.6), 1.4, 0.7, 0.85)
		for i in 4:
			k.box("iron", Vector3(c.x + lx * 0.5 + 0.8 + i * 0.22, 0.9, c.z + 0.6), Vector3(0.18, 0.08, 0.5))
		k.paving(Vector3(c.x + lx * 0.5 - 0.2, 0, c.z + lz * 0.5), Vector3(6.4, 0, 5.4), 0.05, 0.5)
		k.lantern(Vector3(c.x + lx * 0.5 + 2.0, 2.0, c.z + 1.9))
	if L == 5:
		for s in [-1.0, 1.0]:
			var wx = c.x + s * (lx * 0.5 + (1.1 if s < 0 else 2.2))
			k.push_at(Vector3(wx, 0, c.z), 90.0 * s)
			k.lean_to(Vector3.ZERO, lz, 1.8, 2.2, 2.7, "shingle", 2)
			k.pop()
			k.box("plank", Vector3(wx + s * 0.85, 1.2, c.z), Vector3(0.1, 2.3, lz))
		for i in 3:
			k.box("plank", Vector3(c.x - lx * 0.5 - 1.0, 0.6 + i * 0.6, c.z), Vector3(0.6, 0.05, lz - 0.6))
			k.box("ore", Vector3(c.x - lx * 0.5 - 1.0, 0.7 + i * 0.6, c.z), Vector3(0.5, 0.15, lz - 1.0))
	return {"worker": Vector3(-2.6, 0.0, 3.6)}
