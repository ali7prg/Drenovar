extends RefCounted

# What the defensive buildings give the settlement, by level. One table for the
# panels so every number shown comes from the same place.
#
# Server v92 resolves an attack on a city from the garrison alone (duel62): the
# wall and the watchtower do not change a battle yet. These values are what the
# client shows and what the proposed server patch city-defence-v1 is to apply;
# the panel says so and switches to "действует" when the server reports the
# feature in cityFeatures.

const FEATURE := "cityDefence"

# Walls: the palisade from town hall II; "walls and gate" (SUP-03) strengthens it.
static func wall_stats(hall_level: int, wall_level: int, towers: int) -> Dictionary:
	var hall := clampi(hall_level, 1, 5)
	var wall := clampi(wall_level, 0, 5)
	return {
		"durability": 2000 + 1500 * hall + 2500 * wall,
		"defence_pct": 4 * maxi(hall - 1, 0) + 5 * wall,
		"archers": towers * (2 + wall),
		"tower_damage": 18 + 6 * wall,
		"gate_hold_s": 20 + 10 * wall,
	}

# Watchtower (SUP-04): sight over the approaches and archers on the tower.
static func watchtower_stats(level: int) -> Dictionary:
	var l := clampi(level, 1, 5)
	return {
		"sight_m": 60 + 15 * l,
		"warning_s": 30 + 15 * l,
		"archer_attack_pct": 3 * l,
		"archers": 4 + 2 * l,
	}

static func rows_for_wall(stats: Dictionary) -> Array:
	return [
		["Прочность стен", str(stats.durability)],
		["Защита гарнизона", "+%d%%" % stats.defence_pct],
		["Лучники на башнях", str(stats.archers)],
		["Урон башни за залп", str(stats.tower_damage)],
		["Ворота держатся", "%d с" % stats.gate_hold_s],
	]

static func rows_for_watchtower(stats: Dictionary) -> Array:
	return [
		["Обзор подступов", "%d м" % stats.sight_m],
		["Предупреждение о нападении", "за %d с" % stats.warning_s],
		["Атака лучников при обороне", "+%d%%" % stats.archer_attack_pct],
		["Лучники на башне", str(stats.archers)],
	]
