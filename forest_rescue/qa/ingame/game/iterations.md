# «Лес потерянных» — gameplay layer: in-game vs reference iterations

All in-game images are rendered by `godot/project/qa_forest_flow_capture.gd` (Vulkan, llvmpipe under
Xvfb, 1366×630 landscape) from the **existing DRENOVAR orthographic city camera** (only target/zoom are
moved). States are fixtures recorded from the local realm (`data/forest_rescue/game/fixtures`).
Side-by-side sheets: `iterNN_compare_<shot>.png` (left: reference panel, right: in-game), made with
`compose_compare.py iterNN`. Fog, terrain and trees belong to the world layer (`src/forest_rescue/world`);
this log covers the gameplay layer (HUD, cards, intro, actors, mechanisms, telegraphs).

## iter01

| Shot | Differs from reference | Change for iter02 |
|---|---|---|
| hud_forest (art/07 row) | Task title clipped to «Добыть: Берестяная» (2nd line lost); «За спасение:» caption hidden (compact mode); «Маршрут» / «Продолжить» captions overflow the buttons; the row ran into the DRENOVAR navigation on narrower widths | Row re-proportioned for the space left of the existing navigation (task card 200, five 46 px reward cells, buttons 76/76/100), 15 px title on two lines, 14 px captions, 13 px «За спасение:» kept visible |
| intro_horse (art/18 right) | Iskra not visible: start point inside dense canopy, actor hidden by the fog check while the corridor opens | Walk-out starts on the entrance corridor line (−13.6, −62 → −8, −55); intro horse ignores the fog check during the 1200 ms reveal |
| intro_prompt / intro_horse | Visible horizontal banding in the bottom shade (24 stacked rects) | Smooth `GradientTexture2D` shade |
| intro_banner (art/18 centre) | Network toast drawn over the banner; ribbon tails detached from the plate; no visible hall glow | Toasts move below the banner while it is shown; ribbon tails drawn in the plate's own space; additive halo over the town hall (0–2 s) |
| locked_card (art/18 left) | Close to the reference (medallion, title, body, red «К ратуше»); body not italic (only NotoSerif Regular ships with the game); fog is the world layer's | kept |

## iter02

| Shot | Differs from reference | Change for iter03 |
|---|---|---|
| intro_horse (art/18 right) | Bottom shade now smooth (fixed). Iskra is placed on the corridor and visible to the renderer, but the world layer's canopy covers the whole entrance corridor and the site glade from the top camera, so she cannot be seen | Reported to the world layer (routes ≥ 3.8 m and glades ≥ 7 m free of crowns / canopy fade around actors); gameplay side adds 2D name plates («Искра», «Отряд», site names with n/5) drawn above everything, and faint golden route-preview dots to the next target |
| intro_banner | Toast no longer overlaps; ribbons attached to the plate | kept |
| hud_forest (art/07 row) | Row now matches the reference order and look (banner card with dots and «1 / 3», chest strip with five resources «+20 000 … +1 400», «Маршрут» «Отряд» «Продолжить»). Remaining: «За спасение:» still hidden in the space left of the DRENOVAR navigation, «Продолжить» caption clipped by 2 px; actors hidden under the world canopy | Caption always visible (stacked under a smaller chest when the row is narrow), «Продолжить» button 108 px |
| mech_rune / mech_paired / boss_telegraph_* / guardian_battle | DRENOVAR's own battle-result popup («Победа», ordinary loot) for reports already present in the recorded fixture covered the shots; widgets were flat diagrams, far from the bronze rune drum, stone plates on springs, winch frame of art/10 | Capture clears stale result notices before each shot. In play the gameplay layer no longer opens its own result panel when the report is in `state.reports` (DRENOVAR's popup shows outcome, losses and the separate ordinary loot; a toast names the campaign step). Mechanism widgets redrawn: bronze discs with engraved glyphs on a stone ring + green key gem, stone platform with springs, levers and the tree latch, winch A-frame with rope drum, pawl gear, crank and chest over a stone well, trail map with bronze landmark medallions and the hollow log |

## iter03

| Shot | Differs from reference | Change for iter04 |
|---|---|---|
| mech_rune (art/10 rune lock) | Bronze rings with engraved mountain/river/leaf glyphs on a stone ring now read like the bronze drum; the delivered `lf_mechanism_rune_lock.glb` stands in the glade with the gold target ring. Rings are concentric (top-down UI) where the art stacks three bands on a dome | kept (three concentric rings = the three bands seen from above) |
| mech_trail (art/10 trail cache) | Map widget with bronze medallions and the hollow log matches the beat; in 3D the landmark name plates crowd each other and the site name at zoom 30 | Trail camera zoom 24, site plate hidden while the trail is open, plates placed at the landmarks and nudged up/down to avoid overlaps, plates never drawn under the HUD row or the mechanism panel |
| guardian_battle (storyboard 3) | Header «Страж: Тенерис, уровень 1» and retreat button fine, but HP 0 and «0:00»: the capture clock ran past `endsAt` while llvmpipe rendered | Capture freezes the presentation clock at the fixture's server time (movie runs advance it per frame) |
| cage_unlock_key (storyboard 4) | Delivered cage GLB visible in the glade; live toasts («Страж побеждён…», «Гнедая кобыла принадлежит Ладе…») from `recentEvents`; name plates were drawn over the toasts; the three captives are missing (human GLBs not delivered yet) | Plates/arrow layer moved under toasts and cards |
| boss_telegraph_* (art/08) | Fog and arena from the world layer now resemble the reference; Пращур GLB not delivered; progress dots showed site steps «0 / 5» | Boss row shows the three authored phases (hunt / fury / last stand) as «n / 3»; telegraph decal verified in-engine (lane_charge, 4.4 × 22 m at the arena) |
| intro movie | Camera stayed on the town: the presentation captured its return pose before the city stage was tracked | Camera pose taken from `main.stage`; glide verified: town → entrance (2–4.6 s) → hold → back at 12 s |
| hud row | «За спасение:» shown (stacked under the chest in the narrow row); «Продолжить» fits | kept |
