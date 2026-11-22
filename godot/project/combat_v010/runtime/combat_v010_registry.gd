extends RefCounted

# Combat v0.1.0 resource map. Exact library paths and clip names come from the
# delivered manifests (animations/*/manifest.json); there is no substring lookup.
# Libraries are loaded once through ResourceLoader and shared read-only by every
# instance; each AnimationPlayer keeps its own playback state.

const NAMESPACE := &"combat_v010"
const ROOT := "res://combat_v010/animations"

static var _troops: Dictionary = {}   # "ENG-01" -> manifest row
static var _animals: Dictionary = {}  # "TENERYS_L1_RIGGED_ANIMATED" -> manifest row

static func troop_library_path(unit_id: String) -> String:
	return "%s/troops/%s.res" % [ROOT, unit_id]

static func library_path_for_model(model_path: String) -> String:
	return "%s/animals/%s.res" % [ROOT, model_path.get_file().get_basename()]

static func _load_manifests() -> void:
	if not _troops.is_empty():
		return
	var troops: Variant = JSON.parse_string(FileAccess.get_file_as_string(ROOT + "/troops/manifest.json"))
	if troops is Dictionary:
		for row in troops.get("models", []):
			_troops[str(row.id)] = row
	var animals: Variant = JSON.parse_string(FileAccess.get_file_as_string(ROOT + "/animals/manifest.json"))
	if animals is Dictionary:
		for row in animals.get("models", []):
			_animals[str(row.model).get_file().get_basename()] = row

static func troop(unit_id: String) -> Dictionary:
	_load_manifests()
	return _troops.get(unit_id, {})

static func animal(model_path: String) -> Dictionary:
	_load_manifests()
	return _animals.get(model_path.get_file().get_basename(), {})

# Seconds into attack_a/attack_b where the authored contact (melee) or release
# (ranged) pose is. Server event.at is the contact moment.
static func troop_event_s(unit_id: String) -> float:
	return float(troop(unit_id).get("contact_or_release_s", 0.64))

static func troop_attack_length_s(unit_id: String) -> float:
	return float(troop(unit_id).get("length_s", 1.7))

static func animal_clip(model_path: String, clip: String) -> Dictionary:
	return animal(model_path).get("clips", {}).get(clip, {})
