# DRENOVAR premium UI — stage 2: recruitment

Stage 2 rebuilds the training flow of the V6 buildings (barracks B11, range B12, stables B13,
siege workshop B17) around one full-screen recruitment window with a live 3D unit, and adds two
global fixes: the player's resources on full-screen windows and a more prominent window title.
The look follows `ART_DIRECTION.md` (carved oak and bronze, linen, enamel, kokoshnik badges). The
reference game was studied for composition only; nothing from it is in the repository.

## What the player sees

The ring of a training building offers «Обучение» (the hospital and academy keep «Работы здания»).

- **Header.** Full-screen windows use a tall two-board oak band (`kit_header_tall`, 92 px):
  - upper board: the section line on the left (`ОБУЧЕНИЕ ВОЙСК · УРОВЕНЬ II`), the resources on the right;
  - lower board: the title in Ruslan Display 40 (was 32) between the flourishes, and the close medallion.
- **Left rail.** One round bronze medallion per training building the settlement has.
  - Each medallion shows the bust of its first unit, with a caption (Пехота, Стрелки, Конница, Осада).
  - The selected building glows gold.
  - A small hourglass on the rim marks a building that is training.
  - A tap switches the window in place: the same window, the same 3D stage.
- **Hero stage.**
  - The live 3D unit plays its idle animation (the knight plays his showcase loop) on a carved dais.
  - The dais has a stone slab, an oak drum with notch carving and two bronze rings, and a wider
    stone plinth.
  - It stands over an ink wash in the tier colour, with a soft contact shadow, drifting embers and
    the warm key, cool fill and rim lights.
  - Dragging turns the dais slowly (a full turn is about three stage widths). It coasts, then
    turns back to face the viewer after 3.5 s.
  - The name plate carries the kokoshnik tier badge and an «i» chip that opens the details.
- **Tier cards.**
  - One card per unit of the building, with the baked portrait, the tier enamel and numeral, and
    the owned count.
  - A locked card is veiled with a bronze padlock and says what opens it («Нужен ур. III»).
- **Summary.** Name, class · tier · count in the army, role, four figures (attack, defence, health,
  power; wall damage and army places for the ram), and «Подробнее».
  - «Подробнее» (or the «i» chip) swaps the order panel for the stat sheet: what the figures row
    does not already show (speed, army places, upkeep, time for one; strike period and troop
    damage for the ram), then strengths, weaknesses, special and requirements. «Назад» swaps it
    back.
- **Order panel.**
  - Quantity slider, number field and «Макс».
    - «Макс» is the largest batch that fits now: `min(batch limit, free army places / places per
      unit, each stock / unit cost)`.
  - The cost strip shows the exact server values; an amount turns red when the stock is short.
  - Time with the hourglass, using the server rule: `ceil(seconds × n × 10000 / (10000 + speed_bp))`.
  - A gilded «Обучить» («В очередь» while an order runs).
  - A one-line hint with the batch limit and army use, or the reason the order cannot go.
- **Locked unit.**
  - The padlock and each requirement: building level and town-hall level, ticked or red.
  - «Улучшить здание» opens the inspector of the building that is short.
  - The single-unit cost and time at the current level.
- **Running orders.** A card per order of the building:
  - the unit bust with ×quantity;
  - the name and a ticking countdown;
  - a gold bar that fills smoothly to the end time (a tween, no per-frame script);
  - «Ускорить», which opens the speed-up items for this order and returns to the window after a
    use or with «Вернуться к обучению»;
  - «Отменить», which takes two taps («Точно отменить?» within 4 s).
  
  Free queue places show as one muted row («Свободно мест в очереди: 4 из 5 · …»).
- **Completion.** When an order finishes while the window is open:
  - a gold banner slides in over the stage («Обучено: Копейщик × 30»);
  - sparks rise from the dais and the unit's card pulses;
  - all of it is gone after 2.4 s and never blocks a tap.

## Decisions

1. **One window, four buildings.** The rail switches buildings in place
   (`V6Recruit.open` → `set_modal_heading`, `stage.show_unit`, `render`). The modal generation
   stays the same, so a switch neither closes the window nor rebuilds the 3D world. Only the
   right panel is rebuilt.
2. **One tap to train, and the server decides.** The stage-1 flow went: works window → confirm
   window → «Начать» → queues window. The new flow stays in one window:
   - «Обучить» asks for the authoritative quote (`v6quote`).
   - It then sends that exact intent with `expected_duration_seconds`, so a changed rule returns
     `QUOTE_CHANGED` instead of a different order.
   - The window keeps showing what it computed with the server's own rules, and
     `qa_recruitment.gd` checks that the order the server records has the same unit, quantity,
     duration and escrow.
   - A failed quote shows the server's reason in the hint, for example «Недостаточно ресурсов:
     Еда — нужно …, есть …».
3. **Only options V6 really has.** There is no instant or paid training: V6 has no paid currency,
   so the reference's gem button has no counterpart. The secondary paths are «В очередь» (orders
   of a building run one after another), «Ускорить» with the legacy speed-up items
   (`training-1..8`), and «Отменить», which returns the escrow.
4. **The ram.** The siege workshop is in the same window. It shows its wall damage per strike
   and its army places instead of combat stats. Damaged rams at home get a «Ремонт тарана» row
   that uses the existing confirm flow.
5. **Portraits are baked from our models, not painted.**
   - `tools/bake_unit_portraits.gd` renders each preview model in a SubViewport. It uses the same
     camera direction, lens, framing rules and three-point light as the live stage, on a
     transparent background with 4× MSAA.
     - Full figures are rendered at 576×704, busts at 384×384.
     - Framing uses posed bone positions, because skinned meshes report T-pose bounds and spears
       would shrink the figure.
   - `godot/art/ui/units/finish_portraits.py` downsizes them with premultiplied Lanczos into lossy
     WebP q90 with an exact alpha plane: full figures 288×352, busts 128×128.
   - They are imported lossy with mipmaps.
   - Portraits are used on:
     - the tier cards, the stage placeholder, the queue cards and the rail medallions;
     - the new «Войска в городе» tiles of the army window;
     - the formation slots and the legacy recruitment, garrison and hospital art (`main.unit_portrait` /
       `unit_art`), with a fallback to the old painted panel art for units without a portrait.
   - Rebuild:
     ```
     VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1280x1024x24" \
       godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
       -s res://tools/bake_unit_portraits.gd -- --out=/tmp/unit_portraits
     python3 godot/art/ui/units/finish_portraits.py /tmp/unit_portraits godot/project/assets/ui/units
     ```
6. **The live stage costs nothing until it can be seen** (`src/unit_stage.gd`).
   - **First frame.** The window's first frame has only 2D: the ink wash, the shadow, the embers,
     the name plate and the baked portrait in the figure's place.
   - **World build.** The 3D world is built after that frame (`frame_post_draw`):
     - a SubViewport with its own world, transparent background and 4× MSAA;
     - `UPDATE_WHEN_VISIBLE`, at device resolution (canvas size × content scale), so the unit is as
       sharp as the UI on the phone;
     - the lights, the camera and the dais.
   - **Model load.**
     - The model comes from `ResourceLoader.load_threaded_request`, started when the ring or
       inspector of a training building opens (`V6Panels.warm_recruitment`), or at the latest when
       the stage is created.
     - The live view fades in over the portrait (0.28 s); the portrait matches it in pose and framing.
     - Switching units shows the new portrait at once and the model when its scene is ready.
       While the window is open, the last three scenes stay cached.
   - **On close.** The SubViewport, world, lights and model are children of the stage, and the
     window frees the stage when it closes or changes. The cached scenes are dropped too, so
     nothing 3D outlives the window.
   - **No quality cut.** The stage uses the same preview meshes (`unitModels.preview`) and
     materials as the old recruitment preview, at full texture resolution.
7. **Drag on touch.** `TouchScroll` owns every touch while a window is open. It now forwards drags
   to nodes in the group `panel_drag` (`drag_begin`, `drag_by(dx)`, `drag_end`) when no button is
   under the finger. The mouse path is the stage's own `_gui_input`.
8. **Cheap to open.** The window builds about 60 controls where the old works window built about
   12. To keep that in one frame:
   - Tier cards and rail medallions are single drawn nodes on `TextureButton`, so they need no
     theme overrides. Each costs one node and no style work.
   - The figures row and the name plate are drawn too.
   - Catalogue rows are indexed (`V6Panels.row_for`, used dozens of times per open).
   - The hint is one line, so no wrapping pass runs.
   - Portraits decode on worker threads at launch (`UnitStage.warm_portraits`).
9. **The resources on full windows.** The kit plates show live values from `refresh_hud`, in the
   same format as the city HUD (`short_amount`), with the exact amount in the tooltip. They sit
   on the upper board, clear of the close medallion. Only full-screen windows have the tall band.
   Centred and docked windows keep the 62 px band, so nothing changes there.
10. **The title.** Ruslan Display 40 on full windows (34 would also fit; 40 matches the larger band).
    The ornament flourishes stay. The section line moves to the upper board, so the title has the
    lower board to itself.

11. **The city is not drawn under a full-screen window.** A full window covers the whole
    screen, so once its 120 ms settle animation ends the root viewport skips its 3D pass
    (`main.cover_city`, `Viewport.disable_3d`). The pass comes back when the window closes or
    turns into a docked or centred one. The recruitment stage is a separate SubViewport, so it
    keeps rendering. This applies to every full-screen window, not only recruitment.
12. **Badge shadow.** The kokoshnik badge's painted drop shadow wrapped around to the top edge of
    the texture (`np.roll`), which drew a grey hairline above the stage name plate on light
    linen. `paint_kit.py` now shifts that shadow without wrapping, and only `kit_badge` was
    rebaked.

## Files

- New:
  - `godot/project/src/v6_recruit.gd`: controller (data rules, rail, right panel, actions).
  - `godot/project/src/unit_stage.gd`: hero stage (3D world, dais, framing, light rig, portraits
    cache, drag, completion feedback).
  - `godot/project/tools/bake_unit_portraits.gd` and `godot/art/ui/units/finish_portraits.py`:
    the portrait pipeline.
  - `godot/project/assets/ui/units/*.webp`: 12 portraits, 117 KiB.
  - `godot/project/assets/ui/premium/kit_header_tall.res` (43 KB), `kit_dais.res` (58 KB) and
    `kit_dais_n.res` (6 KB). They are painted by `godot/art/ui/premium/paint_kit.py` and baked by
    `tools/bake_ui_kit.gd --only=…`.
  - `godot/tools/qa_recruitment.gd`: the recruitment flow test.
  - `godot/project/qa_recruit_shots.gd`: the stills.
- Changed:
  - `src/ui_kit.gd`: tier card (closed state, TITLE_FONT numeral, drawn), rail medallion,
    padlock, figures row, tall header style, preload list.
  - `src/v6_panels.gd`: training buildings open the recruitment window; ring and inspector warm-up;
    `speedups(order, back)`; army unit tiles; row index; test hooks `recruit_pick` and
    `recruit_details`.
  - `src/main.gd`: tall header, resources and title; `modal_hero_share`; `set_modal_heading`;
    the state hook for the open window; portrait warm-up; baked portraits for legacy unit art;
    the city's 3D pass skipped under full-screen windows (`cover_city`).
  - `src/touch_scroll.gd`: drag areas.
  - `godot/art/ui/premium/paint_kit.py` and `assets/ui/premium/kit_badge.res`: the badge shadow
    no longer wraps.

## Stills and polish passes

Stills are in `ui_premium/shots/stage2/`:
- **Before** (stage-1 build `c336a6c`, rendered from a separate worktree): `before_recruit_B11`,
  `before_recruit_B12`, `before_recruit_B13`, `before_recruit_B17`, `before_recruit_progress`,
  `before_recruit_speedups`, `before_big_recruit_B11`.
- **After**: `after_recruit_B11` (idle), `after_recruit_locked`, `after_recruit_details`,
  `after_recruit_B12`, `after_recruit_B13`, `after_recruit_B17`, `after_recruit_progress`,
  `after_recruit_speedups`, `after_big_recruit_B11` (2532×1167, with orders running).

Render them with:
```
xvfb-run … godot … -s qa_recruit_shots.gd -- --server=http://127.0.0.1:8792 --shots=<dir> [--size=WxH --only=B11 --prefix=…]
```
The side-by-side sheets with the reference stayed outside the repository.

- **Pass 1** (after the first full render):
  - The name plate became one drawn node, because its crest covered the name.
  - The five «free queue place» rows at XI became one summary row.
  - The «Мест в армии» caption no longer clips: figure columns fit their caption.
  - The ram got its own framing (it filled the stage) and the dais is wider.
  - Train and cancel no longer close the window.
  - A stale number field no longer doubles the quantity.
- **Pass 2**:
  - The figure fills more of the stage (66 % of its height, centred at 43 %), the wash is deeper,
    and a faint carved ring sits behind the figure.
  - The details sheet no longer repeats the figures row.
  - The badge-shadow hairline is gone.
  - The model cache is dropped on close.
  - The city's 3D pass is skipped under full-screen windows.

## Measurements

All numbers come from Linux and Godot 4.6.3, at 1366×630, on Vulkan through lavapipe (a
software rasteriser) under xvfb, against the synthetic localhost fixture.
- Main-thread times are real CPU times.
- GPU times are lavapipe's CPU emulation. They show relative cost only and are not phone numbers.
- No device was measured.

**Window open** (main thread, `V6Panels.services(type)` call until it returns):

| | recruitment window (stage 2) | works window (stage 1) |
|---|---|---|
| warm open, median of 5 | B11 4.9 ms, B12 8.5 ms (an earlier run: 5.3 and 7.7) | ≈1.6–1.8 ms |
| first open of each building in a session | B11 6.6, B12 7.5, B13 5.1, B17 6.0 ms (a second run: 7.8, 5.8, 5.9, 8.6) | B11 7.3, B12 2.8, B13 1.8, B17 2.0 ms |
| first open at 2532×1170 | 10.5 ms | — |
| first open ever, headless (`qa_recruitment`, cold glyphs and textures) | 14.8–16 ms | — |
| 3D world build, one frame later (`frame_post_draw`) | 1.9–2.5 ms | — |

The window builds about five times as many controls as the old one. It costs about three times as
much on the main thread, and still fits one 60 Hz frame (16.7 ms). The first open of a session is
the closest to that limit. The model loads on a worker thread and does not add to these numbers.

**Per frame while open** (median of 90 frames after 20 frames of warm-up; draw calls are the
whole frame, all viewports):

| | draw calls | objects | root CPU | stage CPU | root GPU* | stage GPU* | frame (wall) |
|---|---|---|---|---|---|---|---|
| city, no window | 900 | 1539 | 1.28 ms | — | 867 ms | — | 909 ms |
| recruitment, city still drawn underneath (before decision 11) | 788 | 1411 | 1.14 ms | 0.45 ms | 1061 ms | 339 ms | 1419 ms |
| recruitment, city skipped (final) | 250 | 873 | 0.36 ms | 0.30 ms | 19 ms | 118 ms | 146 ms |
| building inspector (full window), final | 123 | 605 | 0.21 ms | — | 15 ms | — | 23 ms |

\* lavapipe CPU emulation.

The live stage renders at device resolution with 4× MSAA. With the city skipped under a full
window, the open recruitment window costs about a sixth of the city frame on this renderer.

**Assets**:
- 12 unit portraits: 117 KiB (WebP q90; full figures 288×352, busts 128×128).
- `kit_header_tall.res`: 43 KB.
- `kit_dais.res`: 58 KB.
- `kit_dais_n.res`: 6 KB.
- `kit_badge.res`: 2.6 KB (rebaked).
- Stills in `ui_premium/shots/stage2/` (JPEG q85): about 150 KB each at 1366×630, 350 KB at 2532×1170.

## Tests

| test | result |
|---|---|
| `qa_recruitment` (new) | 56 checks |
| `qa_building_actions` | 297 states, 4469 checks |
| `qa_building_services` | 42 checks (was 46) |
| `qa_v6_panel_feedback` | 12 checks |
| `qa_button_responsiveness` | 50 checks |
| `qa_build_menu` | 20 checks |
| `qa_panel_latency` | 26 panels |
| `qa_troops06` | 122 checks |
| `qa_touch_buttons` | 11 checks |
| `qa_web_panels` | 37 checks |
| `qa_instant_start` | 12 checks |
| `qa_net_1022` | 48 checks |
| `qa_forest_v6` | 43 checks |
| `qa_combat_1020` | 5500 checks |

- **New test.** `godot/tools/qa_recruitment.gd` runs against the synthetic buildings fixture and
  checks:
  - open, the locked unit, and a rail switch that keeps the window and the stage;
  - that quantity changes the cost and time by the server's own rules;
  - that «Обучить» sends `v6quote` and then exactly the shown order (unit, quantity, duration,
    escrow);
  - the in-progress card and the busy rail mark;
  - speed-ups and the way back, the two-tap cancel, and the details sheet;
  - the ram, the stage freed on close, and no legacy commands.
- **Changed test.** `qa_building_services` drops from 46 to 42 checks. The training buildings no
  longer open the works → confirm → queues chain. Each of B11, B12, B13 and B17 now uses 4 checks
  (available, accepted, shown in the window, cancelled) instead of 5. The removed check was for the
  confirm window, which these buildings no longer have. The hospital and academy keep the old path.
- **Test environment.**
  - `qa_net_1022` runs its fixture without `DRENOVAR_QA_ADVENTURE`; with adventures on, its town
    checks fail.
  - `qa_forest_v6` needs no locally built ram scene in the git-ignored
    `assets/city/architecture-v6/units/`. The CI build puts it there, and the forest guardian check
    then counts it. The local copy that was used for the stills was removed before the final run.
  - Neither of these is a stage-2 code change.

## Still below the reference

- **The model, not the frame.** The reference's hero units are high-detail sculpted models in
  dynamic poses, with rich materials and a rock plinth that merges into the ink wash. Ours are the
  game's own preview models (lower poly, simpler textures) in a calm idle on a carved dais.
  - The composition matches, but the figure is the weakest part of the window. Better unit art is
    an art-production task, not UI work.
  - The knight's lance runs under the header band; the reference keeps weapons inside the wash.
- **Few tiers per building.** The reference shows five to seven tier cards per building. The V6
  catalogue has one or two units per training building, so the card row looks sparse and the
  summary takes the room.
- **More words than icons.** The hint line, the free-queue row and the locked-unit requirements are
  text. The reference says the same with icons and one short line.
- **No atmosphere layer.** There is no animated border glow or vignette around the stage (the
  reference has a fire-lit frame). Embers and the halo are the only motion besides the unit.
- **The ram stands high.** Its dais sits higher than the troops' (the framing fits its length), so
  there is a gap between the dais and the name plate.
- **Untested on a phone.** No real-device frame time was measured. The lavapipe GPU numbers only
  give relative costs.
- **First open is close to a frame.** The first open of a session is close to one 60 Hz frame on
  the main thread (cold glyphs). Pre-shaping the window's fonts during warm-up would remove that.
- **The rail shows busts, not emblems.** This is deliberate (the unit you will train), but it is
  less instantly readable than the reference's branch emblems at small sizes.
