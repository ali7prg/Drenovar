# Build 1024: music loop points

Each `<name>_seam.ogg` plays the last 8 s of the file and then the 8 s after the loop start
(the wrap-around the player hears). The spectrogram shows the joint in the middle.

| Track | Loop start s | File s | Loop length s | Match score | Seam flux | Flux median | Flux p95 | Sample jump |
|---|---|---|---|---|---|---|---|---|
| battle_defying_commodus | 27.85 | 71.8 | 43.9 | 0.722 | 0.609 | 0.671 | 1.309 | 0.0004 |
| city_irelands_coast | 112.06 | 192.7 | 80.7 | 0.856 | 0.519 | 0.767 | 1.635 | 0.0036 |
| city_woodland_fantasy | 36.16 | 122.9 | 86.7 | 0.801 | 0.621 | 0.573 | 1.388 | 0.0021 |
| forest_mystery_forest | 48.43 | 109.9 | 61.4 | 0.731 | 0.566 | 0.658 | 2.107 | 0.0150 |
| world_heroic_demise | 55.58 | 210.4 | 154.8 | 0.972 | 0.426 | 0.671 | 1.480 | 0.0139 |

Seam flux below the median spectral flux of the track means the joint changes the sound less than an
ordinary moment of the music does; the sample jump is the waveform step at the joint (0.0 = continuous).
