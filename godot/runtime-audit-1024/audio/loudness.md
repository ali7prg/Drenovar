# Build 1024 audio: loudness and size

Measured by `godot/tools/audio/loudness_report.py` (ffmpeg ebur128, true peak).

| Group | Files | MB | Integrated LUFS (min..max) | Max true peak dBTP | Max lead ms |
|---|---|---|---|---|---|
| ambient | 5 | 1.86 | -21.0..-20.1 | -1.4 | 0.0 |
| music | 5 | 13.31 | -16.2..-16.0 | -1.2 | 8.4 |
| sfx | 119 | 1.25 | -32.0..-11.5 | -1.7 | 2.0 |
| stingers | 4 | 0.43 | -16.3..-15.9 | -4.3 | 4.8 |

Total: 16.85 MB in 133 files (limit 25 MB). Failures: 0.

| File | LUFS | LRA | True peak | Lead ms | KB |
|---|---|---|---|---|---|
| ambient/battle_din.ogg | -20.2 | 5.0 | -5.4 | 0.0 | 190 |
| ambient/city_birds.ogg | -20.2 | 4.0 | -5.8 | 0.0 | 560 |
| ambient/city_market.ogg | -20.1 | 2.0 | -5.0 | 0.0 | 117 |
| ambient/forest_birds.ogg | -21.0 | 10.8 | -1.4 | 0.0 | 634 |
| ambient/world_wind.ogg | -20.2 | 8.2 | -4.0 | 0.0 | 401 |
| music/battle_defying_commodus.ogg | -16.0 | 2.6 | -4.0 | 8.4 | 1344 |
| music/city_irelands_coast.ogg | -16.0 | 4.6 | -1.2 | 2.1 | 3795 |
| music/city_woodland_fantasy.ogg | -16.1 | 5.7 | -1.3 | 1.8 | 2465 |
| music/forest_mystery_forest.ogg | -16.2 | 8.1 | -1.4 | 1.9 | 1977 |
| music/world_heroic_demise.ogg | -16.0 | 5.2 | -1.6 | 2.1 | 4050 |
| stingers/construction_done.ogg | -16.1 | 1.8 | -5.0 | 2.1 | 127 |
| stingers/defeat.ogg | -15.9 | 4.7 | -6.9 | 0.1 | 116 |
| stingers/reward.ogg | -16.3 | 20.1 | -6.1 | 2.9 | 59 |
| stingers/victory.ogg | -16.1 | 9.9 | -4.3 | 4.8 | 136 |
