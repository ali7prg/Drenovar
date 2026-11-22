# DRENOVAR premium UI — art direction

## One line

A carved-oak and bronze frame around warm, embroidered linen. Think of an old-Rus terem: a chest
with brass fittings, holding a rushnyk towel. Everything is painted in code: no third-party art,
no traced shapes.

## Pillars

1. **Materials, not panels.** Each surface is a material with its own job:
   - **Oak**: window header, cost strip, timer, toasts.
   - **Linen**: window body, cards.
   - **Bronze**: rims, knobs, medallions.
   - **Enamel**: button faces, tier colours.

   Flat colour fills are only for hairlines and progress tracks.
2. **Slavic ornament, used sparingly.**
   - Section headers carry a rushnyk cross-stitch band with rosettes.
   - Lozenge (rhombus) motifs cap the buttons and mark the bronze trim. They are Slavic protective
     motifs, not runes.
   - Tier badges are kokoshnik-shaped.
   - Ornament frames content and never sits behind text.
3. **Warm light.** The light comes from the upper left. Bronze has a hot rim highlight and a dark
   lower lip. Linen has a soft vignette toward the frame. Heroes sit in an ink-wash pool with a
   ground shadow, and embers drift up through the art.
4. **Readable first.**
   - Ink text on linen (#2b2016, muted #6a5843).
   - Gold or ivory on oak.
   - Green (#2e7a32) for gains, red (#b02a25 / #ff7a66 on oak) for shortfalls.
   - Minimum 15 px body and 17 px labels at the 1366×630 canvas. That is 28–32 device px on iPhone 12.
5. **Instant.**
   - Buttons react on touch-down: scale 0.965 + tint, in the same frame.
   - Windows open in one frame, with a 120 ms settle (fade 0.75→1, scale 0.985→1) that never blocks
     input.
   - Rows, tiles, section headers and heroes are single drawn nodes. Their text is shaped once per
     session.

## Typography

| Role | Face | Size (canvas px) | Notes |
|---|---|---|---|
| Window title | Ruslan Display (OFL) | 32 full / 26 centred / 23 docked | Old-Rus display capitals, gold on oak; level steps use it too (its I reads as a numeral) |
| Eyebrow | Noto Serif | 13, letter-spaced caps | Above the title, dim gold |
| Labels, buttons, values | Philosopher Bold (OFL) | 17–21 | Cyrillic humanist with calligraphic terminals |
| Body | Noto Serif | 15–19 | Long text, notes |

The fonts have no arrows, ticks or hourglass glyphs. The kit draws them (`UiKit.mark`, the painted
hourglass), so labels never fall back to a system font.

## Palette

| Token | Hex | Use |
|---|---|---|
| INK | #2b2016 | Text on linen |
| INK_MUTED | #6a5843 | Secondary text |
| BRONZE | #8d5f22 | Accents, stock counts |
| GOLD | #f3d28a | Text on oak, timers |
| IVORY | #fbf1dc | Toast text |
| GOOD | #2e7a32 | Gains, «Построить», ready |
| BAD | #b02a25 | Shortfalls, warnings on linen |
| WARN | #9c4f10 | Cautions, stopped production |
| Tiers I–V | #7d8288, #3f8a4b, #2f6aa8, #7b45a8, #d39a2c | Unit and item tiers |

Button enamels:

| Kind | Enamel | Use |
|---|---|---|
| Primary | Gilded gold | The one main action |
| Secondary | Lapis blue | Alternative actions such as «Использовать» or «Продать» |
| Green | Forest enamel | Gain actions such as «Купить» or claim |
| Danger | Cranberry | Cancel or disband |
| Tertiary | Linen plate | Lists and links |
| Disabled | Iron | Unavailable actions |

## Components (src/ui_kit.gd)

- **Full-screen frame**:
  - Oak header band (56 px plank, bronze lozenge trim, shadow), eyebrow + title, flourishes, close medallion
  - Linen body
  - Optional hero column (40 %): ink-wash splash, ground shadow, rising embers
  - Centred 900 px content column when there is no hero
  - Footer for the call to action
- **Docked and centred windows**: the same header and body, with a bronze rim and corner brackets.
- **Section header**: rushnyk stitch band, rosettes, bronze title.
- **Buttons**: primary, secondary, green, danger, tertiary, disabled. Each is a nine-patch with a
  pressed texture (content shifts 2 px), hover brightening and touch-down scale.
- **Other controls**:
  - Rail medallion and «i» chip
  - Cost strip on oak (amount turns red above stock)
  - Timer pill with hourglass
  - Gold / green progress bar
  - Gold-lozenge slider knob with a typed field
  - Tier card with a kokoshnik badge
  - List row, stat line, resource line, icon tile, toast
- **Textures**: 36 nine-patches painted procedurally at 2 texels per canvas unit, about 0.28 MB baked.
  They stay crisp at the iPhone 12 canvas scale of 1.86 (`godot/art/ui/premium/paint_kit.py`
  → `tools/bake_ui_kit.gd`).

## What we do differently from (or better than) the reference

| | Reference (Viking Rise) | DRENOVAR |
|---|---|---|
| Mood | Cold grey stone, runic Norse | Warm oak, bronze and embroidered linen of an old-Rus terem |
| Display type | Runic capitals | Ruslan Display (Old-Rus ustav capitals), OFL |
| Section ornament | Plain rules | Rushnyk cross-stitch bands with rosettes |
| Buttons | Hexagonal chevron plates | Chamfered enamel plates with bronze lozenge caps; five enamels with clear roles |
| Close | Plain X | Bronze medallion |
| Tier badge | Shield | Kokoshnik |
| Hero art | Static illustration in a fog splash | Ink-wash pool + ground shadow + drifting embers (alive, cheap: 14 CPU particles) |
| Unit preview | Static render on a rock | Live 3D unit on a stone pedestal (legacy recruitment today; V6 works in stage 2) |
| Press feedback | On release | On touch-down, same frame (scale + tint) |
| Window cost | — | V6 windows open in ~1–5 ms of main-thread time, 26 % less than before the redesign |
| Icons in text | Font glyphs | Vector marks: crisp at any scale, no system font fallback |

## Rules for later stages

- One primary (gold) action per window, placed in the footer when the body can scroll.
- Show a gain as the current value, a drawn green arrow and the next value. Never use text arrows.
- Costs always go in the oak cost strip, timers always in the timer pill.
- Never put ornament behind text, and never trim a title.
- New art is procedural or original, painted at 2x with `size_override`. Never trace or copy the
  reference.
- Keep the HUD resource counters plate-less. This is the owner's decision, protected by
  `qa_camera_hud`.
