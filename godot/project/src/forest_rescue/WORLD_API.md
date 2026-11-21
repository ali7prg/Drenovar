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
func trail_path(from_id: String, to_id: String) -> PackedVector3Array   # v3.3: shortest drawn trail between CONTRACT ids
func arena_entrance_yaw_deg() -> float               # v3.3: atlas entranceYawDeg of the boss arena
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
* v3.2 (2026-11-21, checkpoint-2 P0 — API additive, API_VERSION unchanged):
  - No screen-door dither anywhere: the Bayer canopy fade, the Bayer fog cover and the impostor fade are
    removed. Fog receivers (kit trees, landmarks, impostors, actors/props) now fade parts below the cloud top
    smoothly into the mist colour (`fog_receive().x`), never erode or discard them; leaf cards keep their
    alpha test only (a tree always keeps its whole crown). The alpha-blended fog shell does the covering.
  - Crown cut-away removed: `ForestKit.set_fade_circles` and the `fade_circles` uniforms are gone; actor metas
    `canopy_fade_radius` are replaced by `occluder_height` (m, default 2.0 actors / 2.6 props); the meta
    `no_canopy_fade` still excludes markers/decals.
  - Layout camera clearance (`forest_layout_v2.json`, rebuilt): no crown between the fixed city camera and a
    unit on a trail (±1.6 m), in a glade, the arena or at the horse spot/home reception
    (`Rules.crown_capsule`, measured crown shapes `Rules.CROWN_SHAPE`). Ambient trees that would hide one are
    planted young or not at all (understory instead); resource trees keep their ids and displacement limits
    (≤ 4 m / 6.5 m outer, ≤ 3.5–4 m inner), take a clear slot when one exists, otherwise the young look; the
    rest (`cameraOccluders`, 93 ids) are faded at runtime. Understory also stays out of reserve masks.
  - `occluders` (ForestOccluders, forest_occluders.gd): every 0.2 s the trees whose crown hides a visible
    actor/prop near the camera focus (zoom ≤ 80) are drawn — at most 8, nearest first — by a per-tree copy
    that composites the WHOLE tree over the scene at 0.35 opacity (forest_wind_fade*.gdshader, screen copy,
    `instance uniform tree_opacity`), fading in 0.3 s / out 0.45 s; the canopy/impostor instance is hidden
    meanwhile (`canopy.set_instance_hidden`, INSTANCE_CUSTOM r = 1 kit / b = 0 impostor) and a shadow-only
    copy keeps the shadow. `occluders.last_query` reports targets / candidates / hiding / ms.
  - Fog look (delivery spec WORLD_LAYOUT_AND_FOG_RU §79–95): the soft edge lies entirely on the fog side of
    the explored boundary (2.5 m blend band + ≤ 1 m wind lobes; revealed cells receive no fog), opaque past
    the band (density 0.9 /m, top rises to canopy height within ~10 m, camera-near cap unchanged); the wisp
    sheet and haze bank over revealed ground are removed. Known forest away from the squad and the mare
    (outside the sight circles: reveal radius 10 m, falling off to 14 m) stays visible dimmed by
    `DIM_EXPLORED` 0.09 as a plain darkening (no haze colour, never inside the town). Projection rules are
    unchanged: fog opens only from server cells (squad's confirmed checkpoints, entrance corridor).
  - Gameplay layer (forest_game.gd): while the squad or an escort is under way the client reads `/api/state`
    every 1.2 s of server time, so each committed checkpoint reveal dissolves on its own (~2 s per cell)
    instead of all at once on arrival.
* v3.3 (2026-11-21, atlas v2 — API additive, API_VERSION unchanged):
  - The world copy of the atlas is v2 (`data/forest_rescue/world/world-atlas.json` = `lost_forest_atlas_v2`,
    art/01 masterplan network; CONTRACT v1.3): 47 routes `lf_trail_<from>__<to>` + `lf_route_bridge`, junctions
    `lf_junction_*`, landmark spots `lf_mark_*`, glade `lf_glade_el`, arena (18, -92) with `entranceYawDeg` 72.9,
    river `features` lake (101, 38) r 11 / pond (15, -70) r 6.5. v1 route ids (`lf_route_entry`, `lf_route_NN_MM`,
    `lf_route_boss`) are gone; `route_points()` takes the v2 ids. The decorative (visual-only) trails are retired:
    every drawn trail is a server way.
  - `trail_path(from_id, to_id)`: the drawn trail (terrain-profile heights) of the shortest walk over the network
    between two CONTRACT ids (`lf_key_NN` / `lf_site_NN:*` → its glade, `lf_boss_ancient_maw` → the arena,
    `lf_home_reception` → the horse origin), never through another site's glade (the server rule); empty when
    unknown. The director's golden preview dots use it (was: consecutive v1 route ids).
  - `arena_entrance_yaw_deg()`: the arena gap's facing (atlas). The arena GLB, the boss framing and the mare's
    wait point follow it (was a 5.4° constant).
  - Atlas regions (`ForestAtlas.region_sector_weights`, REGION_NAMES): golden grove (top / top-left), west mixed
    oaks, arena rock (top-right gorge), east willows, river, south pines, sw quarry, town belt — used by the layout
    builder zones and the ground tint (sunny meadow under the grove, dark mossy floor under the south pines).
  - `forest_layout_v2.json` rebuilt on atlas v2 (same layout id/version; resource ids unchanged): grove oaks at
    1.35–1.8 absolute scale with open meadows, birches round glade 01, the hollow oak beyond the end of its spur,
    reeds/willows round the lake, the pond and the marsh pools, quarry ledges round the mine and glade 05.
  - Water (`ForestWater`, forest_water.gd/.gdshader, forest_waterfall.gdshader): the reedy lake (river level,
    seamless with the restyled river), a perched lily pond with a waterfall from a limestone outcrop next to
    `lf_junction_waterfall` (22.6, -64.7), three marsh pools below glade 07; terrain basins in ForestTerrain
    (`water_bodies`, TERRAIN_VERSION 12). Hidden under unexplored fog like every forest visual.
  - Landmarks at the atlas marks (watchpost, standing stones, quarry mine, hunter shelter), the dead-tree set
    (arena pillars + bones modules around a bare white tree built from kit bark), a camp at every glade (13)
    with per-glade styles (tent / bare frame / fire ring / fire + bench, supplies, lanterns, rope, signposts,
    stone wall, split-rail fences, hide racks, drying frames, lean-tos; mirrored/rotated, no two neighbours alike).

