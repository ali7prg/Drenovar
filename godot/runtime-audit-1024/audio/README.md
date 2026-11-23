# Build 1024, stage 4: sound and music — evidence

All runs on the Linux QA container (Godot 4.6.3, Dummy audio driver headless; OpenGL under Xvfb for the
pictures, because Vulkan on lavapipe deadlocked after the forest world build). Nobody listened to the mix
on a device here: the numbers below are measurements, not a listening test.

| File | What |
|---|---|
| `loudness.md`, `loudness.tsv`, `loudness.log` | ffmpeg ebur128 of every file (`tools/audio/loudness_report.py`): music −16.0…−16.2 LUFS, all true peaks ≤ −1.2 dBTP, SFX lead ≤ 2 ms, 16.85 MB total |
| `events.md` | game event → sound → files (`tools/audio/event_table.py`) |
| `loops/` | each music loop point as heard (8 s before the end + 8 s after the loop start), spectrograms, `loops.md` seam numbers |
| `soundscapes/` | 30 s of the Master bus per scene (city, world, forest, battle), recorded with AudioEffectRecord at default settings: −20.6, −21.1, −20.6, −19.7 LUFS integrated |
| `sound_settings.png`, `sound_credits.png` | the «Звук и музыка» window and the credits |
| `qa_audio_1024_report.json` | full report of `qa_audio_1024.gd` (296 checks, 0 failures) |
| `suites.tsv` | the re-run suites |

Mix at default settings (master 100 %, music 85 %, effects 100 %, buttons 85 %, ambience 80 %, voices 90 %):
the music bus sits at −3.4 dB over −16 LUFS files, so effects and voices stand 6–10 dB above the theme;
the master compressor (−12 dB, 2:1) and the −1 dB limiter catch stacked hits.
