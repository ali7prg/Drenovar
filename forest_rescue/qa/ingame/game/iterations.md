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
