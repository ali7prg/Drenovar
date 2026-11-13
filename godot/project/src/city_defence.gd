extends RefCounted

# What the wall and the watchtower give the settlement when another player attacks
# it from the world map. The same table as the server patch city-defence-v1
# (gameplay37/server/city-defence.mjs); the server reports it in cityFeatures as
# "cityDefence". Server v92 without the patch counts only the garrison.
#  - the wall stands from town hall II or once "walls and gate" is built;
#  - garrison defence: +4% per town hall level above I (wall standing) and +5% per
#    level of "walls and gate"; the watchtower adds +3% per level;
#  - archers on the wall towers: (4 + 2·hall) towers × (2 + wall level), the
#    watchtower adds 4 + 2·level; each archer adds 18 + 6·wall level power;
#  - garrison losses are lower by half the defence bonus (at most 30%).

const FEATURE := "cityDefence"

static func stats(hall_level: int, wall_level: int, watch_level: int) -> Dictionary:
	var hall := clampi(hall_level, 1, 5)
	var wall := clampi(wall_level, 0, 5)
	var watch := clampi(watch_level, 0, 5)
	var standing := hall >= 2 or wall > 0
	var towers := 4 + 2 * hall if standing else 0
	var archers := towers * (2 + wall) + (4 + 2 * watch if watch > 0 else 0)
	var archer_power := 18 + 6 * wall
	var defence_pct := (4 * (hall - 1) + 5 * wall if standing else 0) + 3 * watch
	return {"standing": standing, "towers": towers, "archers": archers, "archer_power": archer_power,
		"fort_power": archers * archer_power, "defence_pct": defence_pct, "loss_cut_pct": mini(30, roundi(defence_pct / 2.0))}

static func wall_rows(s: Dictionary) -> Array:
	return [
		["Защита гарнизона", "+%d%%" % s.defence_pct],
		["Мощь укреплений", str(s.fort_power)],
		["Лучники на стенах", str(s.archers)],
		["Сила лучника", str(s.archer_power)],
		["Потери гарнизона", "−%d%%" % s.loss_cut_pct],
	]

# The watchtower's own part: what it adds over the wall alone.
static func watchtower_rows(hall_level: int, wall_level: int, watch_level: int) -> Array:
	var with_tower := stats(hall_level, wall_level, watch_level)
	var without := stats(hall_level, wall_level, 0)
	return [
		["Защита гарнизона", "+%d%%" % (with_tower.defence_pct - without.defence_pct)],
		["Лучники на башне", str(with_tower.archers - without.archers)],
		["Мощь укреплений", "+%d" % (with_tower.fort_power - without.fort_power)],
	]
