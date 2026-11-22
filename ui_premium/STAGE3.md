# DRENOVAR premium UI — stage 3: construction and upgrade

Stage 3 rebuilds the construction flow of the V6 settlement:
- the construction window (`v6_panels.catalog()`, the HUD «Строить» and a tap on an empty plot);
- the building window with its upgrade;
- the quote window before any work;
- the placement of a new building on a plot.

The look follows `ART_DIRECTION.md`: carved oak and bronze, linen, enamel, gold. The reference game
was studied for composition only. Nothing from it is in the repository: no frames, crops, traces or
sheets. The side-by-side sheets stay in the session scratchpad.

## What the player sees

### Construction strip

The window keeps the player's own city behind it. The city is blurred, dimmed and warmed, so the
strip reads as a layer over the town rather than as a separate screen.

- **Top left.** A carved plate «Строительство», and under it «Свободно строителей X из Y · Занято
  участков N из M». These are the town hall's builders and plots.
- **Top right.** The player's resources and the close medallion.
- **Left rail.** Four bronze medallions with painted emblems (new in this stage: `kit_emb_town`,
  `kit_emb_craft`, `kit_emb_wall`; the troop emblem is from stage 2). Each has a green badge with
  the number of cards that can be built now. The categories are Хозяйство, Промыслы, Войско and
  Оборона. Every catalogue type is in exactly one category; `qa_build_strip` checks this against
  the live catalogue (27 types).
- **Cards.** A horizontal strip of tall carved cards (236×470):
  - the building's diorama, which rises above the top edge of the card;
  - the name on an oak band;
  - one line on what the building gives;
  - the cost with icons, in rows of three (red where the stock is short), and the time with the
    construction bonus;
  - a foot «Построено 0/1».
- **Card order.** Cards that can be built come first, then short of resources, under
  construction, locked, no plot, and last the ones built to their limit.
- **Card states:**
  - *Can be built.* A bright card with a warm gold glow.
  - *Short of resources.* The same bright card; the missing amounts are red. A tap still starts the
    placement, and the quote says what is missing.
  - *Under construction.* «Строится» with the time left and a gold progress bar. A tap opens the
    queues.
  - *Locked.* The art is darkened under a padlock, with a line «Нужно: Ратуша VI и ещё 1» in warning
    colour.
  - *No plot.* «Все участки заняты: улучшите ратушу», or «Нет свободного участка: опушка».
  - *Built to the limit.* The whole card is greyscale and darker, with no glow (see below).
- **Motion.** The strip follows the finger. A flick glides on, and the strip comes to rest with a
  card on its left edge. At the ends it gives like rubber. A shade gathers at an edge while cards lie
  past it, so a card slides into shadow instead of being cut by a hard line. A bronze indicator
  under the cards shows the position.

### Types built to their limit

In the V6 catalogue every type has `instance_limit` 1, so a type that stands in the settlement is
built to its limit. Two other states draw the same way:
- the shared food estate (`exclusive_group` FOOD_ESTATE, B22 and B24): one of the two can stand;
- the buildings given at founding (`free_start`: B01, B06, B09, B11).

These cards are drawn as follows:
- **Grey.** A greyscale shader on the whole card: 94 % desaturated and dimmed to 60 %. No glow,
  and no cost or time.
- **Stamp.** A dark enamel plate that is not greyed: «Больше строить нельзя». The food estate reads
  «Пищевой участок уже занят»; a founding building reads «Даётся только при основании».
- **Badge and foot.** The building's level in a kokoshnik badge at the top left, and the foot
  «Построено 1/1».

There is no build action. A tap opens the existing building's window, where it can be upgraded.

### Placement

A tap on a card that can be built starts the placement:
1. The strip slides down and fades (0.2 s). The blurred snapshot fades out over the live city
   (0.22 s), so the city sharpens under the finger.
2. Every free plot of the building's terrain glows: a gold ring with a soft halo, breathing
   slowly. The rings are drawn over trees and roofs, so a plot in the forest still shows.
3. The camera moves to the free plot nearest the town hall.
4. A carved banner at the top names the building: «Коснитесь светящегося участка · подходит N».
   It has «Списком», which opens the building window with its plot list (the old flow, still one
   tap away), and «Отмена».
5. A tap on a glowing plot (the nearest within 64 px) puts the building's level-I model on it as a
   gold ghost, and the ring burns brighter.
6. A compact floating confirm opens over the plot, with a pointer to it. It shows «Участок N», the
   cost with icons, the time and «Построить». «Построить» shows «Расчёт…» until the server has
   quoted the build on that plot, then sends it with the quoted time. The city then shows the
   scaffolding and says «Строительство началось: …».
7. If the quote fails, the reason shows in red under the buttons.

A tap on an empty plot opens the strip on the category with the most cards for that plot. Picking
one of them then selects that plot at once.

### Building window: «Сейчас» ➜ «После»

The hero (half the window) shows the building twice, live in 3D, on diorama tiles:
- «Сейчас · ур. V», a gold double chevron, then «После · ур. VI».
- The models are the scenes the city itself draws for those levels. `BuildingStage.level_visual`
  uses the same rule as `Landscape.level_visual`, and `qa_build_strip` compares the two for all
  27 types × 11 levels.
- **When a new model family begins.** For most types, levels I–V are the wooden scenes and
  levels VI–XI the stone ones. Here the whole «После» building is new, so a red enamel ribbon
  «Новый облик» stands over its caption, and nothing is lit.
- **Within a family.** The parts the next level adds (tagged in the scene's UV2) glow a soft
  pulsing gold, so the difference is visible at a glance.
- **Framing.** Both buildings share one scale and turn together: the finger turns them, and a slow
  sway keeps the view alive. If a scene's yard reaches past its tile, the view widens until
  nothing is cut off.
- **Other levels.** An unbuilt type shows «Будет построено · ур. I». Level XI shows «Окончательный
  уровень · ур. XI».

Below the hero:
- The effects as ruled rows. A value the next level raises carries a green delta («+50», «+10%»,
  «+300/ч»).
- «Улучшение до ур. VI»: the cost strip with icons (red where short).
- One row with the time pill (with the bonus) and the main action:
  - «Улучшить» opens the quote;
  - «Построить», for an unbuilt type, starts the placement;
  - «Сначала: Ратуша VI», when a requirement is missing, opens that building.
- **Requirements as chips.** Each chip shows the building's diorama in a bronze circle, the name
  and level, and a green ✓ or a red ✗. A missing chip opens that building's window.
- For an unbuilt type, the plot list «Участок v1-4 …» (each opens the quote for that plot).

### Quote window

- The eyebrow names the work: «УЛУЧШЕНИЕ ДО УР. VI», or «СТРОИТЕЛЬСТВО · УР. I · УЧАСТОК v1-4».
- The hero is the «После» building alone, live.
- «Что даст работа»: the server's effects before and after, with green deltas.
- The cost against the stock, and the time.
- The base time and the bonus.
- The builders and the workers the work takes.
- The reserve note.
- One footer button «Начать».

## Decisions

1. **The blur is made once, not per frame.**
   - On open, a SubViewport at one sixth of the device resolution renders the city once, from a
     copy of the city camera.
   - A second SubViewport of the same size holds the first and renders it once through a 7×7
     Gaussian. Nested viewports render first, so both are ready in the same frame.
   - On screen the result is one quad with a grade: less saturation, 60 % brightness, a warm cast
     and a vignette.
   - Once it has faded in, the root viewport's 3D pass is switched off (`main.cover_city`, as for
     the full windows of stage 2). While the strip is up the city costs nothing; see the
     measurements.
   - A live blur (a back-buffer copy and a blur over the full screen every frame) was rejected: it
     costs a full-screen read and blur per frame on a phone, for a background that does not move.
2. **The swipe goes through TouchScroll.**
   - The strip registers in a "panel_swipe" group. A touch inside it is handed to the strip;
     nothing is pressed while the finger may still drag.
   - Past the 16 px slop, a mostly horizontal move (|x| ≥ 0.75 |y|) drags the strip.
   - A release that never travelled taps the card where the finger landed.
   - A touch on a gliding strip only catches it.
   - After a drag, card taps are ignored for 60 ms, so the card under the lifted finger does not
     act.
   - The mouse (editor, desktop) follows the same rules.
3. **Glide and snap are one motion.**
   - The release velocity (over the last 90 ms) is projected 0.26 s ahead, and the nearest card
     edge to that point is the target.
   - A closed-form critically damped spring (ω 12.5) runs from the current offset and velocity to
     the target. It has no bounce, and there is no jump between the glide and the snap.
   - A deliberate flick always moves on at least one card.
   - Cards outside the view (with 40 px of margin) are hidden, so a long category costs no more
     than a short one.
4. **Built to the limit is a whole-card grey.**
   - The card is drawn normally, and one canvas shader turns it grey. The stamp and the badge are a
     child control without the shader, so they stay legible.
   - No second copy of the art or the frame is needed.
5. **The rail counts what can be built now.** The badge shows only cards in the «can be built»
   state. «Short of resources» is not counted: the player sees at a glance where a builder can
   start today.
6. **Card art is baked from our own models** (commit c79a0d0, `tools/bake_building_art.gd`):
   - the level-I scene the city draws, on the diorama tile (turf, soil band, stones, soft contact
     shadow), lit by the warm key, cool fill and rim of the live view;
   - an orthographic three-quarter camera, transparent background, 4× MSAA;
   - rendered at 1040 px and reduced to 448 px (Lanczos on premultiplied alpha) for a 232 px card
     slot. That is 1.9× the canvas size, and about one image pixel per device pixel on the iPhone 12
     (canvas scale 1.85).
   - The live view starts on exactly this art and cross-fades to the 3D once the scenes are loaded.
7. **Live 3D only where it pays.**
   - The strip uses baked art: up to 11 cards are visible at once, and they must move at 60 fps.
   - The building window and the quote use live 3D: one subject, a turntable, and the level
     difference has to be seen.
   - The 3D world is built one frame after the window opens, so the open itself does no 3D work.
   - The scenes load on worker threads.
8. **A new model family gets a ribbon, not a glow.** The first version lit the parts new against
   the previous level. At level VI that is every part (a new family), and the building came out
   solid gold. Now:
   - a family change (`architecture-v2` → `architecture-v6`) puts the ribbon on the caption;
   - within a family only the new parts glow, at a softer strength (0.34, mostly on the rims).
9. **Placement stays in the city.**
   - The floating confirm replaces the old jump to a separate quote window, so the player sees the
     plot while deciding.
   - The server's quote is still required before «Построить» works, and the order carries the
     quoted time, exactly as before.
   - The plot list stays reachable through «Списком», and in the building window of an unbuilt
     type.
10. **One main action.** The building window has one call to action in the time row. The old
    «Проверить улучшение» is now «Улучшить», as the owner asked. `qa_building_actions` and
    `qa_building_services` look for the new label; nothing else in them changed.
11. **The legacy build sheet keeps its stage-1 look.**
    - It only serves the pre-V6 server, and its cards are built from a different data model
      (`data.buildings`, hall-level locks, the clear-site flow).
    - Restyling it as the strip would mean a second card model and touching the `qa_build_menu` and
      `qa_legacy_build` flows.
    - That is not cheap, so it is left for the stage that retires the legacy realm.

## Files

- `godot/project/src/v6_build.gd` (new) — the construction controller:
  - read-only rules: free plots, plot and builder use, the time rule, card states;
  - the strip window;
  - the placement flow: rings, camera, banner, floating confirm, quote, order.
- `godot/project/src/build_strip.gd` (new) — the strip window: heading, category rail, Swipe
  (touch and mouse, glide and snap, culling, edge shade, indicator).
- `godot/project/src/build_card.gd` (new) — a card drawn in one `_draw`: cached style boxes and
  text, the grey material, and the Stamp child.
- `godot/project/src/build_card_grey.gdshader` (new) — the greyscale of a card built to its limit.
- `godot/project/src/build_place.gd` (new) — the placement banner and the floating confirm.
- `godot/project/src/city_backdrop.gd`, `city_backdrop.gdshader`, `city_blur.gdshader` (new) — the
  one-off blurred city.
- `godot/project/src/plot_glow.gdshader` (new) — the plot rings.
- `godot/project/src/building_stage.gd` — the live «Сейчас/После» pair, appended to the card-art
  helpers from c79a0d0. Includes the family test and the framing on the models' own extents.
- `godot/project/src/building_new_parts.gdshader` — softer glow of new parts.
- `godot/project/src/v6_panels.gd` — `catalog` opens the strip; new `inspect` and a richer
  `confirm`.
- `godot/project/src/main.gd`:
  - the "strip" modal layout and the city backdrop;
  - the placement hooks (city tap, touch blocking, cancel);
  - `building_hero`;
  - the card art warm-up after launch.
- `godot/project/src/landscape.gd` — `show_plot_glow`, `highlight_plot_glow`, the ghost and plate.
- `godot/project/src/touch_scroll.gd` — the "panel_swipe" protocol.
- `godot/project/src/ui_kit.gd` — category emblems, `need_chip`, and delta rows in `stat_row`.
- `godot/art/ui/premium/paint_kit.py` — `category_emblems`.
- `godot/project/assets/ui/premium/kit_emb_town.res`, `kit_emb_craft.res`, `kit_emb_wall.res`
  (new).
- `godot/tools/qa_build_strip.gd` (new test).
- `godot/project/qa_build_strip_shots.gd` (stills and open timings).
- `godot/tools/qa_building_actions.gd`, `godot/tools/qa_building_services.gd` — the renamed button.

## Stills and polish passes

Stills are in `ui_premium/shots/stage3/` (JPEG q85, 1366×630 unless noted).

The "before" stills come from the code at b4f9de0. The window code of the working tree matched
b4f9de0 when they were taken (stage 3 had only added assets). A separate worktree of the 7 GB
project did not fit on the disk.

| still | what it shows |
|---|---|
| `before_build.jpg` | The old catalogue: a three-column grid of tiles in a full window. |
| `after_build_economy.jpg`, `after_build_craft.jpg`, `after_build_army.jpg`, `after_build_defence.jpg` | The strip on each category, over the blurred city. |
| `after_build_maxed.jpg` | The economy category scrolled to its built-out cards: grey, with the stamp, the level badge and «1/1». |
| `after_build_swipe.jpg` | The craft strip caught mid-glide after a flick: the edge shade and the indicator. |
| `before_place.jpg` | The old way to a plot: the window of an unbuilt type with its plot buttons. |
| `after_place.jpg` | Placement: the free plots glow, the banner with «Списком» and «Отмена». |
| `after_place_confirm.jpg` | A plot chosen: the ghost on it and the floating confirm with the server's quote. |
| `before_upgrade_B11.jpg`, `after_upgrade_B11.jpg` | Barracks V: the old step and grid, then the live «Сейчас · ур. V» ➜ «После · ур. VI» pair, where the stone model of level VI begins («Новый облик»). |
| `before_confirm_B11.jpg`, `after_confirm_B11.jpg` | The quote for barracks VI. |
| `before_big_build.jpg`, `after_big_build_economy.jpg` | The construction window in a 2532×1170 window (the iPhone 12 screen). The project keeps its 1366×630 aspect, so the game draws 2532×1167 and the other three rows are letterbox; the stills hold the drawn area. |

The stills were rendered and compared with the reference frames after every round. The
side-by-side sheets are in the session scratchpad only.

**Pass 1** (first full render):
- The hero was solid gold at level VI. Every part of a new model family counts as new, so the
  family change now gets the «Новый облик» ribbon instead (decision 8), and the new-parts glow is
  softer.
- The plot rings were hidden under trees: they are now drawn without the depth test, and the ghost
  gets a gold overlay drawn the same way.
- The placement banner overlapped the resources: it moved under the top row.
- The floating confirm had no pointer: it now has one, toward the plot.
- The camera went to the centre of the town: it now goes to the free plot nearest the town hall.
- The glow of the buildable cards was too strong and was toned down.
- The «Больше строить нельзя» stamp covered the blurb: it moved down to where the cost would be.

**Pass 2:**
- The pointer under the floating confirm never showed: its placement read a property that
  controls do not have. Fixed.
- The upgrade hero cut off the level-V barracks at the left edge, because the scene's yard reaches
  past its tile. The live pair now measures both placed scenes and widens the view to fit them, at
  one shared scale.
- Cards were cut by a hard vertical line at the rail: a soft shade now gathers at each edge while
  cards lie past it.
- The city behind the strip was too dark to read. It is now brightened to 60 % (was 50 %), with
  saturation 0.8 (was 0.72) and a lighter vignette.
- The plot rings read as heavy gold blobs. The ring is now thinner, the halo smaller and the fill
  faint; the chosen plot fills brighter.
- The diorama is now drawn over the card frame and lifted 16 px, so tall roofs rise past the top
  edge of the card.

**Pass 3:**
- The edge shade ended in a hard horizontal line under the cards: it now covers only the card
  bodies.
- On the dark city the chosen category barely stood out. The other medallions now step back
  (74 %), and the chosen one has a warm pool of light behind it and a gold notch pointing at the
  cards.
- Starting a placement cost about 15 ms on the tap. A timed copy of the function located the
  cost: new plate and ghost materials on every placement, whose shared shader had been freed with
  the previous placement's materials. The three placement materials now live as long as the city
  and are created while the strip is open. The ghost's scene loads on a worker thread.
- The first strip open of a session paid about 12 ms once, for its first card and the blurred
  city's viewports. Both are now prepared a few frames after launch, not in the first tap on
  «Строить».

## Measurements

All numbers come from Linux and Godot 4.6.3, at 1366×630, on Vulkan through lavapipe (a
software rasteriser) under xvfb, against the synthetic localhost fixture.
- Main-thread times are real CPU times.
- GPU times are lavapipe's CPU emulation. They show relative cost only and are not phone numbers.
- No device was measured.

The "before" column is the code at b4f9de0, run by the same probe. Its two window scripts were
loaded from git-ignored copies taken with `git show`.

**Window open** (main thread, the call until it returns; median of 5 / the first open of the
session):

| action | before (b4f9de0) | after |
|---|---|---|
| HUD «Строить»: the old catalogue grid / the strip | 4.63 / 5.91 ms | 2.58 / 4.52 ms |
| category switch | — | 0.92 / 1.05 ms |
| tap a card: the strip slides away, the plots glow, the banner shows | — (there was no such step) | 1.55 / 2.36 ms |
| tap a plot: the floating confirm (the quote follows) | — | 2.24 / 2.74 ms |
| building window, unbuilt type | 7.13 / 10.58 ms | 6.25 / 9.18 ms |
| building window, barracks V | 6.11 / 8.71 ms | 6.47 / 5.80 ms |
| quote window, barracks VI | 2.98 / 2.91 ms | 2.93 / 8.29 ms (the first one builds the live hero) |

For reference, stage 1 measured the build window at about 5.3–5.6 ms and the inspector at about
5–6 ms. Two figures were fixed in the third polish pass:
- the card tap went from 15.2 ms to 1.55 ms (median);
- the first strip open went from 14.9 ms to 4.5 ms.

The live 3D of the building window is built one frame after the open, so it is not in these
numbers. Its scenes load on worker threads.

**Per frame while open** (median of 90 frames after 20 frames of warm-up; draw calls are the
whole frame, all viewports):

| | draw calls | root CPU | root GPU* | frame (wall) |
|---|---|---|---|---|
| city, no window — before | 620 | 0.98 ms | 1071 ms | 1084 ms |
| city, no window — after | 621 | 1.03 ms | 1127 ms | 1142 ms |
| old catalogue (full window, city skipped) — before | 149 | 0.15 ms | 15 ms | 23 ms |
| strip at rest (city skipped, blurred snapshot) | 237 | 0.33 ms | 28 ms | 36 ms |
| strip while swiping all the time | 264 | 0.33 ms | 27 ms | 36 ms |
| strip with the city still drawn under it (not shipped; for comparison) | 717 | 1.10 ms | 1087 ms | 1099 ms |
| placement (the city, 22 rings, banner, floating confirm) | 671 | 1.11 ms | 1103 ms | 1114 ms |
| building window — before (static art) | 155 | 0.17 ms | 16 ms | 23 ms |
| building window — after (live «Сейчас/После» pair) | 212 | 0.30 ms | 18 ms | 441 ms |

\* lavapipe CPU emulation.

What the table shows:
- **The strip.** It costs about a thirtieth of the city frame on this renderer, because the city's
  3D pass stops once the snapshot is up. Swiping costs no more than resting: a swipe moves one
  track control and hides the cards out of view; nothing is laid out again.
- **Placement.** It costs what the city costs, plus the rings.
- **The building window.** Its wall time is the live pair's own viewport: two full level scenes
  with shadows, at device resolution with 4× MSAA, rasterised in software. The stage-2
  recruitment stage measured 146 ms the same way. No phone was measured.

**Launch** (`qa_instant_start`, headless, the baseline and the current code run alternately,
three each): baseline 1341, 1365 and 1598 ms; after 1226, 1306 and 1526 ms. Launch is not longer.
- The warm-up after launch grew: the dioramas, then the card class, the styles and the
  backdrop's viewports.
- The dioramas are decoded only once the server is known to be V6, four at a time. When they
  were all requested at once, the legacy build sheet, opened right after launch, took 177–222 ms
  instead of 41–58 ms (CPU contention).

**Assets:**
- Card dioramas (commit c79a0d0): 28 WebP images at 448×448 (27 types and the empty tile), 529 KiB
  in all.
- Three new rail emblems: `kit_emb_town` 6.5 KiB, `kit_emb_craft` 9.5 KiB, `kit_emb_wall`
  3.2 KiB (19.2 KiB).
- Five shaders: 4.0 KiB in all.
- No new models or fonts. The live views use the city's own level scenes.
- At run time, the blurred city is two viewports at a sixth of the device resolution (228×105 at
  1366×630; 422×195 on the iPhone 12): about 0.3 MB with the small one's 3D buffers.
- The stills in `ui_premium/shots/stage3/` (not part of the game) take 2.7 MB.

## Tests

All runs are on Linux with Godot 4.6.3, headless unless noted, against the synthetic localhost
fixtures. No real account was used.

| test | result |
|---|---|
| `qa_build_strip` (new) | 467 checks, 11 cases (categories, maxed, drag, catch, tap, placement, list, cancel, requirement chip, models 297 = 27 types × 11 levels, pair) |
| `qa_building_actions` | 297 states, 4469 checks (label «Проверить улучшение» → «Улучшить»; nothing else changed) |
| `qa_building_services` | 42 checks (same label change) |
| `qa_v6_panel_feedback` | 12 checks |
| `qa_recruitment` | 56 checks, 9 cases |
| `qa_legacy_build` | 22 checks |
| `qa_web_panels` | 37 checks |
| `qa_build_menu` | 20 checks. Open 48–60 ms (baseline 41–58 ms). The first version of the diorama warm-up made it 177–222 ms, over the test's 120 ms limit; fixed (see Measurements) |
| `qa_panel_latency` | 26 panels, 26 checks |
| `qa_button_responsiveness` | 50 checks |
| `qa_touch_buttons` | 11 checks |
| `qa_instant_start` | 12 checks; launch as in Measurements |
| `qa_net_1022` | 48 checks |
| `qa_forest_v6` | 43 checks; passed 5 of 6 runs. The one failure, «guardian drawn with the creatures v2 model», is the intermittent check also seen in stage 2 |
| `qa_move_building` | 14 of 16 on the in-memory v92 test realm. The 2 failures are the city-defence server patch, which that realm lacks; identical on the baseline code |
| `qa_building_looks` | 5 failures «4 of 5 buildings have a marker», identical on the baseline code (not from this stage) |
| `qa_market_upgrade` | not run: it records a real-time upgrade in two rendered phases on a patched realm |

The new test drives the strip through the real touch path (`root.push_input`, screen touches
and drags spread over frames, as a finger sends them).

## Still below the reference

- **Card art.** The reference cards carry large, finely detailed building renders that break
  far out of the card. Ours are rendered from the game's own city models; at level I these are
  modest (a well, two market stalls). The roofs only just rise past the frame.
- **The city behind the strip.** The reference keeps its cards in the lower half and lets much
  more of the blurred town show. Ours fill the height, to carry the blurb, the cost in two rows
  and the time. The backdrop is also a still snapshot: anything that moves in the city stops
  while the strip is open.
- **Greyed cards.** The reference greys to a light silver. Ours is darker, which reads well as
  "done" but is heavier on the eye in a category that is mostly built.
- **Upgrade models.** For some types the level-VI stone scene looks smaller or plainer than the
  wooden level V (barracks: the level-V scene has a yard and towers that VI lacks). The window
  shows exactly what the city will draw, so the «После» can look like a step down. That is a
  modelling issue, not a window one.
- **Placement.** It is tap-only. There is no dragging of the ghost between plots, no footprint
  grid and no rotation. The ghost is a gold overlay of the level-I model.
- **Live 3D cost on the software renderer.** The live «Сейчас/После» pair renders every frame
  (sway and turn) at device resolution with 4× MSAA. On lavapipe that dominates the frame of the
  building window. No phone was measured.
- **The legacy build sheet** (pre-V6 server) keeps its stage-1 look (decision 11).
- **No device numbers.** All timings are from Linux with a software rasteriser.
