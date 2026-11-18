# ForestWorld API (world layer → gameplay layer)

Owner of implementation: world-layer agent (`src/forest_rescue/world/*`, hooks in `src/landscape.gd`).
Consumer: gameplay agent (`src/forest_rescue/game/*`, hooks in `src/main.gd`).
Only additive changes; record them at the bottom.

Access: in the city scene `stage.forest_world` (Node3D, script `res://src/forest_rescue/world/forest_world.gd`).
It is `null` in the world-map scene.

```gdscript
signal world_ready                                  # chunks/terrain/fog prepared for first frame
signal fog_reveal_finished(revision: int)

func apply_adventure(adv: Dictionary) -> void       # state.adventure (CONTRACT §3) or {} if absent
func is_locked() -> bool                            # true when access.unlocked == false or no adventure
func height_at(x: float, z: float) -> float         # final ground height incl. earthworks/bridge deck
func ground_point(x: float, z: float) -> Vector3
func site_anchor(site_id: String) -> Dictionary     # {center, cage, guardian, artifact, approach,
                                                    #  plate_left, plate_right, landmarks:{symbol:Vector3}, cage_yaw}
func poi_position(target_id: String) -> Vector3     # CONTRACT targetIds incl. lf_home_reception
func route_points(route_id: String) -> PackedVector3Array
func actors_root() -> Node3D                        # parent for adventure actors (fog-aware culling)
func props_root() -> Node3D                         # parent for site props (cages, mechanisms)
func fog_cleared_at(x: float, z: float) -> bool     # projection says visible (for hiding POIs/actors)
func play_entrance_reveal(duration_ms: int) -> void # hall III unlock corridor (instant if reduced motion)
func set_reduced_motion(on: bool) -> void
func pin_area(id: String, center: Vector3, radius: float) -> void   # keep chunks full-detail
func unpin_area(id: String) -> void
func focus_bounds() -> Rect2                        # camera-allowed XZ rect (city ±56 + forest ±112)
func set_boss_arena_state(state: String) -> void    # locked|available|active|defeated (dressing)
func set_site_post_state(site_id: String, step: int) -> void  # after-rescue dressing (open door, ribbons…)
func perf_snapshot() -> Dictionary                  # {full_chunks, proxy_chunks, instances, tris_est}
```

Coordinates: game XZ = atlas XZ (`delivery/data/world-atlas.json`), +Y up, north = -Z.

## Changelog
* v1 (2026-11-18) initial.
