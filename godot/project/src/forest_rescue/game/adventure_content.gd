extends RefCounted
## Read-only authored content for «Лес потерянных».
## The JSON files in res://data/forest_rescue/game/ are verbatim copies of
## forest_rescue/delivery/data (see SOURCE_SHA256SUMS.txt). Every user-facing string
## comes from ui.ru.json / unlock-intro.json / dialogue.ru.json / campaign.json;
## client.ru.json only adds HUD chrome captions that the delivery files do not contain.

const DATA_DIR := "res://data/forest_rescue/game/"
const RESOURCES := ["food", "wood", "stone", "iron", "coins"]
const TASKS := ["discover", "recover_artifact", "defeat_guardian", "unlock_cage", "escort_home"]

var campaign: Dictionary = {}
var economy: Dictionary = {}
var intro: Dictionary = {}
var manifest: Dictionary = {}
var strings: Dictionary = {}
var intro_strings: Dictionary = {}
var client_strings: Dictionary = {}
var dialogue: Dictionary = {}
var sites: Dictionary = {}
var site_order: Array[String] = []
var captives: Dictionary = {}
var clip_specs: Dictionary = {}
var loaded := false
var missing: Array[String] = []

static func read_json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed

func load_all() -> bool:
	campaign = _load("campaign.json")
	economy = _load("economy.json")
	intro = _load("unlock-intro.json")
	manifest = _load("animation_manifest.json")
	strings = _load("ui.ru.json").get("strings", {})
	intro_strings = intro.get("texts", {})
	client_strings = _load("client.ru.json").get("strings", {})
	var talk: Dictionary = _load("dialogue.ru.json")
	for entry in talk.get("entries", []):
		dialogue[String(entry.get("id", ""))] = entry
	for site in campaign.get("sites", []):
		var id := String(site.id)
		sites[id] = site
		site_order.append(id)
		for person in site.get("captives", []):
			var record: Dictionary = person.duplicate()
			record.siteId = id
			captives[String(person.id)] = record
	for group in manifest.get("groups", []):
		for clip in group.get("clips", []):
			clip_specs[String(clip.id)] = clip
	loaded = missing.is_empty()
	return loaded

func _load(file: String) -> Dictionary:
	var value: Variant = read_json(DATA_DIR + file)
	if value is Dictionary:
		return value
	missing.append(file)
	push_warning("Forest rescue content missing: " + file)
	return {}

## Looks a key up in ui.ru.json, then unlock-intro.json texts, then client chrome captions.
func text(key: String, args: Dictionary = {}) -> String:
	var value: String = strings.get(key, intro_strings.get(key, client_strings.get(key, "")))
	if value.is_empty():
		push_warning("Forest rescue string missing: " + key)
		return ""
	for name in args:
		value = value.replace("{" + String(name) + "}", str(args[name]))
	return value

func has_text(key: String) -> bool:
	return strings.has(key) or intro_strings.has(key) or client_strings.has(key)

func site(id: String) -> Dictionary:
	return sites.get(id, {})

func site_number(id: String) -> int:
	return int(site(id).get("number", 0))

func task(site_id: String, task_id: String) -> Dictionary:
	for entry in site(site_id).get("tasks", []):
		if entry.id == task_id:
			return entry
	return {}

func task_reward(site_id: String, task_id: String) -> Dictionary:
	return task(site_id, task_id).get("reward", {})

func prologue_reward() -> Dictionary:
	return campaign.get("prologue", {}).get("reward", economy.get("prologue", {}))

func final_reward() -> Dictionary:
	return campaign.get("boss", {}).get("reward", economy.get("final", {}))

func symbol_label(symbol: String) -> String:
	return text("symbol." + symbol) if has_text("symbol." + symbol) else symbol

func species_name(species: String) -> String:
	if species == "ancient_maw":
		return String(campaign.get("boss", {}).get("displayName", "Пращур"))
	return text("species." + species) if has_text("species." + species) else species

func captive(id: String) -> Dictionary:
	return captives.get(id, {})

func released_line(captive_id: String) -> String:
	return String(dialogue.get(captive_id + "_released", {}).get("text", ""))

func testimony(site_id: String) -> Dictionary:
	return dialogue.get(site_id + "_testimony", {})

func line(id: String) -> Dictionary:
	return dialogue.get(id, {})

func clip_seconds(clip_id: String, fallback := 1.0) -> float:
	return float(clip_specs.get(clip_id, {}).get("durationSeconds", fallback))

func boss_attack(attack: String) -> Dictionary:
	return campaign.get("boss", {}).get("attacks", {}).get(attack, {})

func intro_shots() -> Array:
	return intro.get("presentation", {}).get("shots", [])

func intro_seconds() -> float:
	return float(intro.get("presentation", {}).get("durationSeconds", 12))

static func format_amount(value: int) -> String:
	var digits := str(absi(value))
	var groups: PackedStringArray = []
	while digits.length() > 3:
		groups.insert(0, digits.right(3))
		digits = digits.left(digits.length() - 3)
	groups.insert(0, digits)
	return ("-" if value < 0 else "") + " ".join(groups)
