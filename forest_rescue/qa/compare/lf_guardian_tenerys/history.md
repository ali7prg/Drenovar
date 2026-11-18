## Original vs new direction

The original `TENERYS_L1..L3_RIGGED_ANIMATED.glb` (creature-assets37) are identical grey procedural prototypes
(45.8k tris in 27 rigid section meshes, 13-joint "rigid-section-skinned" rig, clips Idle 3.2 / Walk 1.0 /
Run 0.62 / Alert 1.25 / Attack 1.0 / Hit 0.62 / Death 1.6 / Roar 1.6 s; levels differ only by material
names; the game scales them by 1.02+0.16*level).  They face **+X** in glTF although `landscape.gd`
orients creatures with `atan2(dx, dz)` (i.e. expects **+Z** forward) — the new GLB faces +Z.  Visually:
a grey wolf-boar with a tall spiked ruff, no stripes, no lynx ears, no horn nubs (see `original/L1/*.png`,
`old_vs_new.png`).  The new model follows art/09: lean striped lynx-wolf, dark swept mane ridge, lynx
ears with tufts, bony horn nubs, amber eyes, whiskers, light cheek ruff, bushy striped tail, big paws
with pale claws.  Species id, 3 levels, clip names and the ~5 m footprint are kept (new: 5.0 m nose to
tail tip vs 5.26 m).

## Compare → fix iterations (every image kept in this folder)

| iter | IoU side/front/rear | what differed (from the diff images and per-row run analysis) | what was changed |
|---|---|---|---|
| 00test | 0.730/0.772/0.769 | mane = sparse isolated spikes; legs too thin in front/rear; fangs & whiskers too prominent; weak ruff/ears; rear sheet painted its hanging tail onto the rump; render darker than the sheet | dark mane-ridge volume + denser finer spikes; light cheek/throat ruff volume; bigger ears; fangs tucked; almond eyes; wider/outset legs and paws; bushier tail; per-view projection trust filters; albedo calibration vs sheet |
| 01 | 0.777/0.817/0.817 | (+ orchestrator review) body too low, legs stumpy, mane too tall/vertical at the shoulders, head small/open-mouthed, thin tail, small paws; runs: head/ruff 0.1 m too narrow per side, crest missing above 1.85 m, fore-legs narrow inside | belly/chest raised, longer femur/tibia (clear hock angle), slender sagittal legs, closed mouth + whisker pads, mane angles lowered on the back, thicker tail core, wider head/ruff, ears moved out |
| 02 | 0.794/0.866/0.796 | mane spikes fitted only to the side poked out sideways in front/rear; hind legs wide inside; elbow end of the forearm too wide; side: lower legs 0.16–0.21 m vs sheet 0.27–0.33 m, paws 0.29–0.37 m long vs 0.43–0.50 m, mouth slit notched the profile | two-cone forearm (narrow elbow, wide wrist), thicker lower legs, longer paws/digits, mane fitted to slightly dilated front/rear masks, slit kept inside the lips |
| 03 | 0.821/0.882/0.821 | front and rear sheets are mutually inconsistent (leg union [0.17,0.51] m vs [0.24,0.48] m — impossible for one 3-D model); crest still short; mane-ridge rear too high; hind legs ~20 px too far back | leg width compromise ~[0.20,0.50]; dedicated midline crest group; lower ridge end; hind stance moved forward |
| 04 | 0.833/0.882/0.849 | extended hind leg carried the whole haunch backwards (gap under the tail filled); elbows closed the chest gaps; tail underside short; back mane low; ear base too far back | haunch moved onto the pelvis bone (lower thigh only follows the femur); smaller triceps; longer tail clumps; mane angles; ears forward |
| 05 | 0.851/0.875/0.850 | (visual) mane started on the forehead and hid the ears; white bar along the mouth; tail/mane clumps read as shingles; dark chest-tuft spikes in profile; per-channel gain pushed legs pink | mane starts behind the ears; finer & more clumps (body budget 7.6k); teeth inside; narrow chest tuft; luminance-only gain |
| 06 | 0.847/0.872/0.843 | a whisker ran back along the mouth line; mouth-interior paint reached the lips (red spot) | thinner, outward whiskers; interior colour only deep inside the slit; thinner slit; exact joint connections (no hidden bone translations) |
| 07 | 0.847/0.871/0.847 | full pipeline (rig, 8 clips, export, Godot) — see below | – |

Remaining honest deviations: the rear sheet draws the tail hanging to the ground while the side sheet
curves it up at ~0.54 m (the model follows the side sheet: ~6 % of the rear silhouette stays red); the
sheet's far hind leg is anatomically longer than any rig consistent with the near legs (knee ~40 px off in
the side stance); front/rear leg widths are a compromise between the two inconsistent sheets.
