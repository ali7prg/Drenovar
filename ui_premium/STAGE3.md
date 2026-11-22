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
- **Cards.** A horizontal strip of carved cards (206×404) in the lower part of the screen, about
  60 % of its height. The blurred city stays readable above them. Each card has:
  - the building's diorama, close up on a transparent ground, breaking out above the top edge of
    the card;
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
  - *Locked.* The art is darkened under a padlock, with a line «Нужно: Ратуша III и ещё 1» in
    warning colour.
  - *No plot.* «Все участки заняты: улучшите ратушу» while the town hall can still be upgraded,
    otherwise «Все участки заняты»; or «Нет свободного участка: опушка».
  - *Soon.* Its level I needs a building past the open level (see «Levels stop at V»): «Откроется с
    новыми уровнями зданий», and no build action. No type is in this state with today's catalogue;
    the state is there for when the catalogue changes.
  - *Built to the limit.* The whole card is a light silver greyscale, with no glow (see below).
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
- **Silver.** A greyscale shader on the whole card that lifts the darks: the luminance is mapped to
  0.2–0.94 with a faint cool tint, so the card reads as light silver, not as a dark slab. No glow,
  and no cost or time.
- **Caption.** A plain dark caption where the cost would be: «Больше строить нельзя». It has no
  plate, frame or bevel, so it does not look like a button. The food estate reads «Пищевой участок
  уже занят»; a founding building reads «Даётся только при основании».
- **Badge and foot.** The building's level in a kokoshnik badge at the top left, and the foot
  «Построено 1/1». The badge is the level that stands. A building already past V (the test
  fixtures have them) shows its real level here; nothing on the strip offers a level past V.

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
   translucent ghost: the model's own colours and textures, about two-thirds opaque, with a warm
   rim and a soft key light, drawn over trees. The ring burns brighter.
6. A compact floating confirm opens beside the plot, never over it. The plot's footprint and the
   ghost's height are projected to the screen; the confirm tries the right, the left, above and
   below, and takes the first place that keeps clear of them. A pointer on that side points at the
   plot. It follows the plot while the camera settles.
7. The confirm shows the plot by a human name, «Участок 4 · на опушке» (the number and where it
   lies: в центре, у рудной жилы, у скал, у берега, на опушке, на краю поселения, у ратуши), the
   cost with icons, the time and «Построить». «Построить» shows «Расчёт…» until the server has
   quoted the build on that plot, then sends it with the quoted time. The city then shows the
   scaffolding and says «Строительство началось: …».
8. If the quote fails, the reason shows in red under the buttons.

A tap on an empty plot opens the strip on the category with the most cards for that plot. Picking
one of them then selects that plot at once.

### Building window: «Сейчас» ➜ «После»

The hero (half the window) shows the building twice, live in 3D, on diorama tiles:
- «Сейчас · ур. IV», a gold double chevron, then «После · ур. V».
- The models are the scenes the city itself draws for those levels. `BuildingStage.level_visual`
  uses the same rule as `Landscape.level_visual`, and `qa_build_strip` compares the two for all
  27 types × 11 levels.
- **Within a family.** The parts the next level adds (tagged in the scene's UV2) glow a soft gold,
  so the difference is visible at a glance. A slow warm breath behind the pair keeps the window
  alive; it is a 2D glow, so it costs no 3D frame.
- **When a new model family begins.** For most types, levels I–V are the wooden scenes and
  levels VI–XI the stone ones. There the whole «После» building is new, so a red enamel ribbon
  «Новый облик» stands over its caption, and nothing is lit. With the game stopped at V this is not
  reached; it returns when the open level rises.
- **Framing and motion.** Both buildings share one scale and turn together. On opening they turn
  once by about 14° and settle (1.4 s), so the depth reads; then the view holds still. The finger
  turns them. If a scene's yard reaches past its tile, the view widens until nothing is cut off.
- **Other levels.** An unbuilt type shows «Будет построено · ур. I». At level V and above see
  «Levels stop at V». Level XI shows «Окончательный уровень · ур. XI».

Below the hero:
- The effects as ruled rows. A value the next level raises carries a green delta («+50», «+10%»,
  «+300/ч»).
- «Улучшение до ур. V»: the cost strip with icons (red where short).
- One row with the time pill (with the bonus) and the main action:
  - «Улучшить» opens the quote;
  - «Построить», for an unbuilt type, starts the placement;
  - «Сначала: Ратуша V», when a requirement is missing, opens that building.
- **Requirements as chips.** Each chip shows the building's diorama in a bronze circle, the name
  and level, and a green ✓ or a red ✗. A missing chip opens that building's window.
- For an unbuilt type, the plot list «Участок 4 · на опушке …» (each opens the quote for that
  plot).

### Quote window

- The eyebrow names the work: «УЛУЧШЕНИЕ ДО УР. V», or «СТРОИТЕЛЬСТВО · УР. I · УЧАСТОК 4».
- The hero is the «После» building alone, live.
- «Что даст работа»: the server's effects before and after, with green deltas.
- The cost against the stock, and the time.
- The base time and the bonus.
- The builders and the workers the work takes.
- The reserve note.
- One footer button «Начать».

### Levels stop at V

The models for building levels VI and above are not made yet, so the game stops at level V for now
(owner requirement). One client constant holds the open level: `MAX_OPEN_BUILDING_LEVEL := 5` in
`main.gd`. The server is unchanged.

- **The building window at level V and above.** «Сейчас» shows the building as it stands. The
  «После» slot shows no level-VI model: it is a veiled card (the empty diorama tile darkened under
  dark linen, a gold border, a faint sun) with a «Скоро» plate and «Новые уровни зданий скоро
  появятся». Its caption reads «После · скоро».
- **Below the hero.** The effects of the current level, without deltas. A section «Следующий уровень
  · скоро» holds the line «Новые уровни зданий скоро появятся.» and a disabled grey «Скоро» button.
  There is no cost strip, no time and no requirement chips for VI, and the server's VI quote is
  never asked for.
- **Levels I to IV** upgrade as before, up to V.
- **Buildings already past V** (fixtures) display as they stand, with their real level, and cannot
  be upgraded.
- **Every way in is closed:**
  - the action ring offers «Сведения» instead of «Улучшить»;
  - `confirm()` with kind construction and a target past V shows the line and returns before it
    opens anything;
  - `main.request()` refuses a quote, and `main.command()` an order, past V: a V6 construction
    intent, a kingdom «upgrade» from level V, and a legacy «level» order past V. These two are the
    only ways out to the server, so this guard holds for any path not listed here;
  - the legacy building window offers no upgrade from V and caps its level buttons at V;
  - the strip: a type whose level I needs a building past V would be «Soon» (above), and the
    placement refuses it;
  - the recruitment lock panel: a unit whose building needs a level past V reads «Откроется с
    новыми уровнями зданий», and its «Улучшить здание» becomes a disabled «Скоро».
- **Raising the cap** later is the one constant; the tests read it from `main.gd`.

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
   - The card is drawn normally, and one canvas shader turns it silver. The caption and the badge
     are a child control without the shader, so they stay legible.
   - No second copy of the art or the frame is needed.
5. **The rail counts what can be built now.** The badge shows only cards in the «can be built»
   state. «Short of resources» is not counted: the player sees at a glance where a builder can
   start today.
6. **Card art is baked from our own models** (commit c79a0d0, `tools/bake_building_art.gd`):
   - the level-I scene the city draws, on the diorama tile (turf, soil band, stones, soft contact
     shadow), lit by the warm key, cool fill and rim of the live view;
   - an orthographic three-quarter camera, transparent background, 4× MSAA;
   - rendered at 1040 px and reduced to 448 px (Lanczos on premultiplied alpha). That is about
     2.2× the 206 px card, and a little over one image pixel per device pixel on the iPhone 12
     (canvas scale 1.85);
   - since the fourth polish pass, a close framing per type: the tile is shrunk to the building's
     footprint, the camera is lower (about 23° above the ground instead of 30°), and the building and
     its tile fill the image with small margins. The building is the subject, not the tile.
   - The live view starts on exactly this art and cross-fades to the 3D once the scenes are loaded.
7. **Live 3D only where it pays.**
   - The strip uses baked art: up to 11 cards are visible at once, and they must move at 60 fps.
   - The building window and the quote use live 3D: one subject, a turntable, and the level
     difference has to be seen.
   - The 3D world is built one frame after the window opens, so the open itself does no 3D work.
   - The scenes load on worker threads.
   - The live pair renders on demand (decision 12).
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
12. **The live pair renders on demand.**
    - Its SubViewport is switched between `UPDATE_ALWAYS` and `UPDATE_DISABLED`. A disabled viewport
      keeps its last picture, so the window shows the full-quality pair (device resolution, 4×
      MSAA, shadows) at no 3D cost while nothing moves.
    - It renders while the opening turn runs, while the finger turns the pair, while a released
      turn glides back, and for two or three frames after a model is placed, the view is laid out or
      the size changes. Then it stops.
    - The slow sway was dropped, and the new parts no longer pulse: both would have needed a frame
      of 3D every frame. The life of the window is now the 2D breath behind the pair (an additive
      warm glow whose opacity loops over 1.9 s).
13. **One open level, checked where requests leave.**
    - `MAX_OPEN_BUILDING_LEVEL` is the only value. The windows ask `V6Panels.level_open(type,
      target)`, which also refuses a level whose requirements go past the open level, unless they
      already stand.
    - Every quote and order leaves through `main.request()` or `main.command()`, and both refuse
      anything past the open level before any network work. A path that was missed in the windows
      still sends nothing. `capped_requests` counts the refusals and `quotes_sent` the quotes that
      went out; the tests use both.

## Files

- `godot/project/src/v6_build.gd` (new) — the construction controller:
  - read-only rules: free plots, plot and builder use, the time rule, card states;
  - the strip window;
  - the placement flow: rings, camera, banner, floating confirm, quote, order.
- `godot/project/src/build_strip.gd` (new) — the strip window: heading, category rail, Swipe
  (touch and mouse, glide and snap, culling, edge shade, indicator).
- `godot/project/src/build_card.gd` (new) — a card drawn in one `_draw`: cached style boxes and
  text, the grey material, and the Stamp child.
- `godot/project/src/build_card_grey.gdshader` (new) — the silver greyscale of a card built to its
  limit.
- `godot/project/src/build_place.gd` (new) — the placement banner and the floating confirm, which
  keeps clear of the plot's projected footprint.
- `godot/project/src/placement_ghost.gdshader` (new) — the translucent ghost: the model's own
  textures (sampled as its material samples them, triplanar or by UV), a soft key light and a
  warm rim.
- `godot/project/src/city_backdrop.gd`, `city_backdrop.gdshader`, `city_blur.gdshader` (new) — the
  one-off blurred city.
- `godot/project/src/plot_glow.gdshader` (new) — the plot rings.
- `godot/project/src/building_stage.gd` — the live «Сейчас/После» pair, appended to the card-art
  helpers from c79a0d0. Includes the family test, the framing on the models' own extents, the
  rendering on demand, the breath and the veiled «Скоро» card.
- `godot/project/src/building_new_parts.gdshader` — a softer, steady glow of new parts.
- `godot/project/src/v6_panels.gd` — `catalog` opens the strip; new `inspect` and a richer
  `confirm`; `level_open` and the «Скоро» section.
- `godot/project/src/v6_recruit.gd` — the lock panel of a unit whose building needs a level past V.
- `godot/project/src/main.gd`:
  - the "strip" modal layout and the city backdrop;
  - the placement hooks (city tap, touch blocking, cancel);
  - `building_hero`;
  - the card art warm-up after launch;
  - `MAX_OPEN_BUILDING_LEVEL`, `SOON_LINE`, the guard in `request()` and `command()`, and the cap
    in the legacy building window.
- `godot/project/src/landscape.gd` — `show_plot_glow`, `highlight_plot_glow`, the ghost (with one
  ghost material per source material, cached) and the plate.
- `godot/project/src/touch_scroll.gd` — the "panel_swipe" protocol.
- `godot/project/src/ui_kit.gd` — category emblems, `need_chip`, and delta rows in `stat_row`.
- `godot/art/ui/premium/paint_kit.py` — `category_emblems`.
- `godot/project/assets/ui/premium/kit_emb_town.res`, `kit_emb_craft.res`, `kit_emb_wall.res`
  (new).
- `godot/tools/qa_build_strip.gd` (new test).
- `godot/project/qa_build_strip_shots.gd` (stills and open timings).
- `godot/project/tools/bake_building_art.gd`, `godot/art/ui/buildings/finish_art.py` — the close
  framing; the 28 images in `godot/project/assets/ui/buildings/v6/` were baked again.
- `godot/tools/qa_building_actions.gd`, `godot/tools/qa_building_services.gd` — the renamed button;
  `qa_building_actions` also checks the open level.
- `godot/tools/qa_v6_panel_feedback.gd` — its stand-in for `main.gd` now carries the open level
  (read from `main.gd`) and the refusal counter.

## Stills and polish passes

Stills are in `ui_premium/shots/stage3/` (JPEG q85, 1366×630 unless noted).

The "before" stills come from the code at b4f9de0. The window code of the working tree matched
b4f9de0 when they were taken (stage 3 had only added assets). A separate worktree of the 7 GB
project did not fit on the disk.

| still | what it shows |
|---|---|
| `before_build.jpg` | The old catalogue: a three-column grid of tiles in a full window. |
| `after_build_economy.jpg`, `after_build_craft.jpg`, `after_build_army.jpg`, `after_build_defence.jpg` | The strip on each category, over the blurred city. |
| `after_build_maxed.jpg` | The economy category scrolled to its built-out cards: light silver, with the plain caption, the level badge and «1/1». |
| `after_build_swipe.jpg` | The craft strip caught mid-glide after a flick: the edge shade and the indicator. |
| `before_place.jpg` | The old way to a plot: the window of an unbuilt type with its plot buttons. |
| `after_place.jpg` | Placement: the free plots glow, the banner with «Списком» and «Отмена». |
| `after_place_confirm.jpg` | A plot chosen: the translucent ghost of the market on it, and beside it the floating confirm «Участок 4 · на опушке» with the server's quote. |
| `before_upgrade_B11.jpg`, `after_upgrade_B11.jpg` | Barracks: the old step and grid at level V, then the live «Сейчас · ур. IV» ➜ «После · ур. V» pair (level V adds the gate towers and flags). The before still is older than the owner's level cap, so it shows level V. |
| `after_upgrade_B11_soon.jpg` | Barracks V: «После» is the veiled «Скоро» card, and the disabled «Скоро» button in «Следующий уровень · скоро». |
| `before_confirm_B11.jpg`, `after_confirm_B11.jpg` | The quote: barracks VI before the cap, barracks V after. |
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

**Pass 4** (after the coordinator's review of the economy strip, the barracks upgrade and the
placement confirm):
- **Strip height and city.** The cards are 206×404 instead of 236×470 and sit in the lower part
  of the screen (about 60 % of it), so the blurred city reads above them. The card art was baked
  again with a close framing (decision 6): the building fills more of the picture, the tile is
  smaller, and the roof breaks out above the card. The blurb, cost and time were re-spaced for the
  smaller card, and a long name steps down from 19 to 17 or 15 px instead of being cut. The 28
  images are 490 KiB (were 529).
- **Built-out cards.** Light silver instead of dark grey, and the «Больше строить нельзя» plate,
  which looked like a brown button, is now a plain caption.
- **Upgrade window cost.** The live pair renders on demand (decision 12). The idle 3D cost of the
  window is gone; see Measurements.
- **Placement.** Plot names instead of «Участок v1-4»; a translucent ghost with the building's own
  colours instead of a gold glow over it; the floating confirm keeps clear of the plot. The plate
  under the ghost and the disc of the chosen ring were made fainter, so the ghost is the subject.
- **Level cap** (owner requirement, «Levels stop at V»): the IV→V upgrade, and the «Скоро» window
  at V.

## Model step-downs, levels I–V

The window shows exactly the scene the city draws for each level, so a «После» that looks plainer
than «Сейчас» is a modelling matter. The models were not changed. All 27 types were surveyed for
levels I–V (the levels the game offers now): each level scene was measured (extent, height,
vertices, surfaces) and rendered from the same camera, and the suspect pairs were compared by eye.

No step is a clear downgrade. Mild ones:

| type | step | what is lost |
|---|---|---|
| B19 Сторожевая башня | III → IV | The wooden lookout box on top is gone; a stone base is added instead. 11 % fewer vertices, same height. The plainest step of the five levels. |
| B18 Стены и ворота | III → IV | The tall wooden gate tower becomes a lower, wider gatehouse. 4 % lower; more geometry overall. |
| B22 Пшеничная ферма | III → IV | The second gabled house becomes an open barn. 4 % fewer vertices, 3 % lower. |
| B16 Лазарет | II → III | 5 % lower and 4 % fewer vertices; a porch is added. Not visible at the window's size. |

Barracks IV → V is not a step-down: V adds the gate towers and flags (1 % fewer vertices).

Steps where almost nothing changes (under 0.2 % of the pixels differ at the same camera), so
«После» looks the same as «Сейчас»: B01 I→II, B02 IV→V, B05 I→II, B06 III→IV, B09 II→III, B10
IV→V, B13 II→III and IV→V, B14 IV→V, B19 II→III, B20 IV→V, B21 III→IV, B24 II→III, B26 III→IV,
B27 I→II.

The contact sheets (all 27 types at I–V, and the suspect pairs side by side) are in the session
scratchpad only: `ui_compare/stage3/model_steps_levels_I-V.jpg` and
`ui_compare/stage3/model_steps_suspect_pairs.jpg`.

## Measurements

All numbers come from Linux and Godot 4.6.3, at 1366×630, on Vulkan through lavapipe (a
software rasteriser) under xvfb, against the synthetic localhost fixture.
- Main-thread times are real CPU times.
- GPU times are lavapipe's CPU emulation. They show relative cost only and are not phone numbers.
- No device was measured.

The "before" column is the code at b4f9de0, run by the same probe. Its two window scripts were
loaded from git-ignored copies taken with `git show`.

**Window open, pass 3** (main thread, the call until it returns; median of 5 / the first open of
the session):

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

**Per frame while open, pass 3** (median of 90 frames after 20 frames of warm-up; draw calls are the
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

**Pass 4** (the final code, with the level cap; the same renderer and fixture). Window open, main
thread, median of 5 and the first of the run (the probe opens after 60 frames of warm-up, so this
"first" is not the first open after launch):

| action | median / first |
|---|---|
| HUD «Строить»: the strip | 3.92 / 3.92 ms |
| category switch | 1.04 / 0.66 ms |
| tap a card: placement begins | 1.58 / 2.13 ms |
| tap a plot: the floating confirm | 1.83 / 1.79 ms |
| building window, unbuilt type | 6.83 / 7.41 ms |
| building window, barracks IV («Сейчас · IV» ➜ «После · V») | 4.46 / 5.46 ms |
| building window, barracks V («Скоро») | 2.98 / 5.49 ms |
| quote window, barracks V | 2.72 / 4.30 ms |

Per frame while open (median; draw calls are the whole frame, all viewports):

| | draw calls | root CPU | root GPU* | frame (wall) |
|---|---|---|---|---|
| strip at rest (two runs) | 263 | 0.24–0.37 ms | 20–25 ms | 27–36 ms |
| strip while swiping all the time | 286 | 0.36 ms | 21 ms | 29 ms |
| placement (the city, rings, ghost, banner, floating confirm) | 668 | 1.07 ms | 968 ms | 982 ms |
| building window, pair at rest — pass 3 (rendered every frame) | 212 | 0.30 ms | 18 ms | 441 ms |
| **building window, pair at rest — pass 4 (held picture)** | **189** | **0.32 ms** | **19 ms** | **27 ms** |
| building window while the finger turns the pair | 211 | 0.29 ms | 17 ms | 451 ms |
| building window at V, «Скоро» | 137 | 0.28 ms | 18 ms | 28 ms |

\* lavapipe CPU emulation.

- **The upgrade window at rest** now costs what a flat window costs: its 3D viewport renders no
  frame (`qa_build_strip` checks that the count of rendered frames does not move while the window
  is idle), and the frame is the 2D window and the breath. That is 27 ms of wall time on this
  renderer instead of 441 ms. The quality while it renders is unchanged: device resolution, 4×
  MSAA, shadows.
- **While it moves** (the 1.4 s opening turn, a finger turn and its glide back) every frame is a
  full render, as before: 451 ms per frame here. A phone renders this scene on its GPU; it was not
  measured.
- The strip and placement numbers are in line with pass 3. The strip at rest varies between runs
  of this software renderer (27 and 36 ms).

**Launch** (`qa_instant_start`, headless, the baseline and the current code run alternately,
three each): baseline 1341, 1365 and 1598 ms; after 1226, 1306 and 1526 ms. Launch is not longer.
- The warm-up after launch grew: the dioramas, then the card class, the styles and the
  backdrop's viewports.
- The dioramas are decoded only once the server is known to be V6, four at a time. When they
  were all requested at once, the legacy build sheet, opened right after launch, took 177–222 ms
  instead of 41–58 ms (CPU contention).

**Assets:**
- Card dioramas: 28 WebP images at 448×448 (27 types and the empty tile), 490 KiB in all since the
  close framing of pass 4 (529 KiB in commit c79a0d0).
- Three new rail emblems: `kit_emb_town` 6.5 KiB, `kit_emb_craft` 9.5 KiB, `kit_emb_wall`
  3.2 KiB (19.2 KiB).
- Six shaders: 6.0 KiB in all (the placement ghost shader is new in pass 4).
- No new models or fonts. The live views use the city's own level scenes.
- At run time, the blurred city is two viewports at a sixth of the device resolution (228×105 at
  1366×630; 422×195 on the iPhone 12): about 0.3 MB with the small one's 3D buffers.
- The stills in `ui_premium/shots/stage3/` (not part of the game) take 2.8 MB.

## Tests

All runs are on Linux with Godot 4.6.3, headless unless noted, against the synthetic localhost
fixtures. No real account was used.

Pass 4 (with the level cap). These ran last, on the final code:

| test | result |
|---|---|
| `qa_build_strip` | 697 checks, 15 cases. Added since pass 3: the maxed caption is plain text; plot names (no «v1-»); the confirm never covers the chosen plot (40 frames while the camera settles); the ghost uses the translucent ghost shader; the plot list names the plots; barracks II, IV, V, VII and XI in the window (IV upgrades to V and sends one quote; V and VII show «Скоро», a disabled «Скоро» button, no cost, no time, no chips, and the ring has no «Улучшить»; at each, `confirm`, `request`, `command`, a kingdom upgrade and a legacy level order are all refused, 5 refusals, no quote sent, no order started); no strip note names a level past V; the idle window renders no 3D, the turning one does |
| `qa_building_actions` | 297 states, 2984 checks. Below the open level the full upgrade flow as before; the completion boundary (one millisecond early, then on time) is checked on the upgrades from III and IV (was III, V and X). At V and above (162 states: 27 types × V–X): the ring offers «Сведения», the window has the disabled «Скоро» and no cost or requirements, the «Скоро» button sends nothing, and `confirm`, `request` and `command` are refused (3 refusals per state, no quote sent, no order started) |
| `qa_building_services` | 42 checks, 6 states |
| `qa_v6_panel_feedback` | 12 checks (its stand-in for `main.gd` now carries the open level) |
| `qa_recruitment` | 56 checks, 9 cases; open 8.2 ms |
| `qa_build_menu` | 20 checks; open 38.9 ms |
| `qa_panel_latency` | 26 panels, 26 checks |
| `qa_button_responsiveness` | 50 checks |
| `qa_touch_buttons` | 11 checks |
| `qa_instant_start` | 12 checks; launch 2140, 1456 and 1478 ms (the first run right after the art was imported again) |
| `qa_legacy_build` | 22 checks |
| `qa_web_panels` | 37 checks |

Pass 3 (the first stage-3 runs; kept for the record):

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

- **Card art.** The dioramas are closer now and break out above the card, but they are rendered
  from the game's own city models, and at level I these are modest (a well, two market stalls).
  The reference cards carry larger, finely detailed renders that break much further out.
- **The city behind the strip.** It now reads above the cards, but it is a still snapshot:
  anything that moves in the city stops while the strip is open.
- **Upgrade models.** No step from I to V is a real downgrade, but four are mildly plainer (B19
  III→IV most of all) and fifteen steps barely change at all (see «Model step-downs»). The window
  shows exactly what the city draws, so this is for the modelling work, not the window.
- **The «Скоро» card** is a 2D veil over the empty tile, not a model or a painted teaser. The
  next-level section at V is a single line and a disabled button; it could later say what level VI
  will bring once that is designed.
- **Placement.** It is tap-only. There is no dragging of the ghost between plots, no footprint
  grid and no rotation. At the default city zoom a level-I ghost is small (the market's two stalls
  are about 60 px wide), so the ring still carries most of the signal.
- **Live 3D while turning.** The pair no longer costs anything at rest, but each frame of the
  opening turn or of a finger turn is a full render at device resolution with 4× MSAA and shadows
  (about 450 ms per frame on lavapipe). No phone was measured.
- **The first building window of a session** takes about 19 ms on the main thread in the headless
  `qa_panel_latency` run (the later ones 6–8 ms; before stage 3 about 2.5 ms). It is under the
  test's limit, but it is the slowest open of this stage.
- **The legacy build sheet** (pre-V6 server) keeps its stage-1 look (decision 11).
- **No device numbers.** All timings are from Linux with a software rasteriser.
