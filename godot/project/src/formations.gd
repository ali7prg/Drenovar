extends RefCounted

const GROUPS := ["INF-01", "CAV-01", "RNG-01", "SIEGE"]
const FIELD_LIMIT := 24

# Match representedMembers60, including the original server indices used by combat events.
static func field_slots(bag: Dictionary, roster: Array) -> Array[Dictionary]:
	var assigned: Array[Dictionary] = []
	var total := 0
	for id in bag:
		var count := int(bag[id])
		if count > 0:
			assigned.append({"id":id, "total":count, "count":1, "fraction":0.0, "order":assigned.size()})
			total += count
	if total > FIELD_LIMIT:
		var remaining := FIELD_LIMIT - assigned.size()
		var spare := total - assigned.size()
		for entry in assigned:
			var quota := float(remaining * (entry.total - 1)) / spare
			entry.count += floori(quota)
			entry.fraction = quota - floori(quota)
		remaining = FIELD_LIMIT
		for entry in assigned:
			remaining -= int(entry.count)
		var sorted := assigned.duplicate()
		sorted.sort_custom(func(a, b): return a.order < b.order if a.fraction == b.fraction else a.fraction > b.fraction)
		for entry in sorted:
			if remaining > 0 and entry.count < entry.total:
				entry.count += 1
				remaining -= 1
	else:
		for entry in assigned:
			entry.count = entry.total
	var roles := {}
	for unit in roster:
		roles[unit.id] = unit.training_building
	var groups := {"INF-01":[], "CAV-01":[], "RNG-01":[], "SIEGE":[]}
	for entry in assigned:
		var role: String = roles.get(entry.id, "INF-01")
		for index in range(int(entry.count)):
			groups[role].append({"id":entry.id,"index":index})
	var slots: Array[Dictionary] = []
	var depth := 0.0
	for role in GROUPS:
		var members: Array = groups[role]
		var mounted: bool = role in ["CAV-01", "SIEGE"]
		var width := 4 if mounted else 5
		var spacing := 2.4 if mounted else 1.45
		var row_depth := 3.7 if mounted else 1.7
		for i in range(members.size()):
			var row := floori(float(i) / width)
			var count := mini(width, members.size() - row * width)
			var member: Dictionary = members[i]
			member.side = (i % width - (count - 1) * 0.5) * spacing
			member.rear = depth + row * row_depth
			member.ranged = role == "RNG-01"
			member.mounted = mounted
			slots.append(member)
		if not members.is_empty():
			depth += ceilf(float(members.size()) / width) * row_depth + (0.8 if mounted else 0.45)
	return slots

static func parade_slots(bag: Dictionary, roster: Array) -> Array[Dictionary]:
	var groups := {"INF-01":[], "CAV-01":[], "RNG-01":[], "SIEGE":[]}
	var remaining := bag.duplicate()
	for role in GROUPS:
		var members: Array = groups[role]
		var limit := 4 if role == "CAV-01" else 24
		while members.size() < limit:
			var size_before := members.size()
			for unit in roster:
				if unit.training_building == role and int(remaining.get(unit.id, 0)) > 0:
					members.append(unit.id)
					remaining[unit.id] = int(remaining[unit.id]) - 1
					if members.size() == limit:
						break
			if size_before == members.size():
				break
	var cavalry: Array = groups["CAV-01"]
	var foot_limit := 24 - ceili(cavalry.size() / 2.0)
	var slots: Array[Dictionary] = []
	for role in ["INF-01", "RNG-01"]:
		var members: Array = groups[role]
		var side := -1.0 if role == "INF-01" else 1.0
		for i in range(mini(foot_limit, members.size())):
			var x := side * (4.1 + floori(i / 12.0) * 4.5) + (i % 3 - 1) * 1.05
			slots.append({"id":members[i], "offset":Vector2(x, -6 + floori((i % 12) / 3.0) * 1.45), "mounted":false})
	for i in range(cavalry.size()):
		slots.append({"id":cavalry[i], "offset":Vector2(1.2 if i % 2 else -1.2, -5 + floori(i / 2.0) * 4), "mounted":true})
	for i in range(mini(4, int(bag.get("SIEGE-RAM-01", 0)))):
		slots.append({"id":"SIEGE-RAM-01", "offset":Vector2((i - 1.5) * 3.1, 5.5), "mounted":true})
	return slots

# A returning formation has new positions, never new identities. Older city
# responses carry the full death history; the paired V6 projection also supplies
# surviving members for reconnects and for world armies with compact events.
static func returning_slots(army: Dictionary, roster: Array) -> Array[Dictionary]:
	var presentation: Dictionary = army.get("presentation", {})
	var survivors := {}
	var explicit: Variant = presentation.get("returnMembers")
	if explicit is Array:
		for member in explicit:
			var id := str(member.unitId)
			if not survivors.has(id):
				survivors[id] = []
			survivors[id].append(int(member.index))
	else:
		var dead := {}
		var events: Array = army.get("battle", {}).get("events", []) if army.get("battle") is Dictionary else army.get("events", [])
		for e in events:
			if e is Dictionary and e.get("kind") != "soldier_attack" and e.get("hp", -1) == 0:
				dead["%s:%d" % [e.unitId, int(e.index)]] = true
			elif e is Array and e[1] != "soldier_attack" and e[4] == 0:
				dead["%s:%d" % [e[2], int(e[3])]] = true
		for member in army.get("fallen", []):
			dead["%s:%d" % [member[0], int(member[1])]] = true
		var original: Dictionary = presentation.get("originalUnits", army.units)
		for id in original:
			survivors[id] = []
			for index in int(original[id]):
				if not dead.has("%s:%d" % [id,index]):
					survivors[id].append(index)
	var slots := field_slots(army.get("returnUnits", army.units), roster)
	var result: Array[Dictionary] = []
	for slot in slots:
		var indices: Array = survivors.get(slot.id, [])
		if int(slot.index) < indices.size():
			slot.index = indices[int(slot.index)]
			result.append(slot)
	return result
