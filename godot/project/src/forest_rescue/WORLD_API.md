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
func perf_snapshot() -> Dictionary                  # {full_chunks, proxy_chunks, instances, tris_est, …}
func focus_on(position: Vector3, zoom := -1.0) -> void      # v2: city-camera fly-to (no new camera mode)
func focus_site(site_id: String, zoom := 42.0) -> void
func focus_entrance(zoom := 46.0) -> void
func set_sight_points(points: Array) -> void          # v2: extra sight circles Vector4(x, z, radius, strength)
func resource_tree_position(id: String) -> Vector3    # rendered (= pick) position of a resource tree
func area_displayed(x: float, z: float, radius: float) -> bool   # v3: any displayed-clear fog cell near (x, z)
func kit_status() -> Dictionary
func layout_info() -> Dictionary                      # {layoutId, layoutVersion, seed, remapStats, apiVersion, flag…}
```

Coordinates: game XZ = atlas XZ (`delivery/data/world-atlas.json`), +Y up, north = -Z.

`perf_snapshot()` (v3) also reports `landmark_tris` (visible landmark/arena triangles at the chosen
LOD), `fog_culled` (instances removed because they stand deeper than 3 m inside fog) and
`fog_cull_ms` (CPU time of the last cull, run only when the fog projection changes).

## Changelog
* v1 (2026-11-18) initial.
* v2 (2026-11-18) additive: focus_on/focus_site/focus_entrance, set_sight_points, kit_status, layout_info.
* v3 (2026-11-19) world layer v2 (kit v2 + layout v2 + fog v2); API additive only:
  - `area_displayed(x, z, radius)`; `perf_snapshot().landmark_tris`; `API_VERSION` 3.
  - Layout `lf_forest_layout_v2` (`data/forest_rescue/world/forest_layout_v2.json`, builder
    `world/tools/build_forest_layout.gd`): every resource id kept; outer trees moved off the old
    spiral to natural spots (≤ 4 m, clearance pushes ≤ 6.5 m keep the stump inside its ±6.7 m
    prepared-site plot); inner (±56) trees jittered ≤ 3.5 m (≤ 4 m on the entrance) off the spiral rows (same side of every
    plot square, ≥ 1.8 m off town roads; if the player's property covers the jittered spot the tree
    is drawn at its original spot). `selectable_trees[].p` and `resource_tree_position()` are the
    rendered positions; the pickable set is decided on the original spot exactly as the legacy forest.
  - Fog v2: `fog_cleared_at()` / projection rules unchanged (server cells only, the camera never
    reveals, hall I–II = whole outer forest fogged, entrance corridor 1200 ms). Visual changes only.
  - Actors under `actors_root()` keep the canopy fade; trees/landmarks under fog now erode/darken
    by fog density (no gameplay effect).
  - Under fog nothing renders but the fog: every canopy instance (trees, impostors, understory)
    standing more than 3 m inside unexplored ground is removed from the GPU buffers when the
    projection changes; landmarks/arena hide unless displayed ground is within their radius + 3 m;
    props/actors keep the `fog_cleared_at()` rule. The pickable resource list is unaffected.
  - Inner (±56) trees on the hall-III entrance (horse spot r 3.9 m, entry trail ±3 m) may move up
    to 4.0 m (other inner trees ≤ 3.5 m). The entry trail ribbon starts at the horse origin.
  - The city river strip gets the world-layer river material (flag ON only; found by its shader,
    landscape.gd unchanged).
  - Fog look v3 (iter10–11, visual only): painted mist texture quilted from art/07 + art/18
    (`assets/forest_rescue/world/lf_fog_painted.png`, tools/build_fog_texture.py), soft cauliflower
    domes, wrap lighting / silver lining / haze at grazing angles, light wisps and a translucent haze
    bank over the revealed edge, drift 0.45 m/s (frozen with reduced motion).
* v3.1 (2026-11-19, integration pass — additive, API_VERSION unchanged):
  - Boss arena v2 LODs: `lf_boss_arena_assembled{,_lod1,_lod2}.glb` are switched as whole files by the
    city zoom (LOD0 ≤ 34, LOD1 ≤ 85, LOD2 beyond; LOD2 also when the arena is far from the camera
    target). The wanted file is loaded on a worker thread and swapped in; the previous instance is
    freed, so only one arena file is resident. Painted kit material (k 0.35) like the landmarks.
    `landmarks.finish_arena_load()` completes a pending swap synchronously (QA stills only).
  - Zero-through-fog for the arena: every arena part (rim pines, rocks, banners inside the arena
    GLB) follows the kit-instance rule (`area_displayed(part centre, part radius)`), and the arena's
    painted materials are registered as fog receivers. `perf_snapshot().landmark_tris` counts only
    the visible arena parts.
  - `clock_source: Callable` (optional property): the gameplay layer sets `client.server_now`, so
    the sight circles follow the presentation clock (fixed-fps movies); real time when unset.
  - Painted shader include (`forest_painted.gdshaderinc`, shared with actors/props): optional
    uniforms `albedo_uv2` (glTF baseColorTexture.texCoord 1), `use_variant_mask` / `variant_mask` /
    `tint_cloth` / `tint_hair` (captive look variation through `<civilian>_variant_mask.png`). Defaults
    leave the kit unchanged.
