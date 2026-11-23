#!/usr/bin/env python3
"""Build 1024: listening demos of each music loop point.

  python3 -I godot/tools/audio/loop_demos.py [out_dir]   (default godot/runtime-audit-1024/audio/loops)

For every music file writes <name>_seam.ogg: the last 8 s before the end of the file followed directly by
the 8 s after its loop start — exactly what a player hears when the theme wraps around — plus a spectrogram
of the joint (seam at the middle), and loops.md with the seam numbers from audio_manifest.json.
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.abspath(os.path.join(HERE, "..", "..", "project", "assets", "audio"))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..", "runtime-audit-1024", "audio", "loops"))
SR = 44100
SPAN = 8.0


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = json.load(open(os.path.join(AUDIO, "audio_manifest.json")))
    lines = ["# Build 1024: music loop points", "", "Each `<name>_seam.ogg` plays the last %d s of the file and then the %d s after the loop start" % (SPAN, SPAN),
             "(the wrap-around the player hears). The spectrogram shows the joint in the middle.", "",
             "| Track | Loop start s | File s | Loop length s | Match score | Seam flux | Flux median | Flux p95 | Sample jump |", "|---|---|---|---|---|---|---|---|---|"]
    for key, entry in sorted(manifest.items()):
        if entry["kind"] != "music":
            continue
        name = os.path.basename(key)[:-4]
        x = decode(os.path.join(AUDIO, key))
        a = int(round(entry["loop_offset"] * SR))
        n = int(SPAN * SR)
        joint = np.concatenate([x[-n:], x[a:a + n]])
        wav = os.path.join(OUT, name + "_seam.wav")
        ogg = os.path.join(OUT, name + "_seam.ogg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libvorbis", "-q:a", "4", ogg],
                       input=joint.astype(np.float32).tobytes(), check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ogg, "-lavfi", "showspectrumpic=s=800x240:legend=0:scale=log", os.path.join(OUT, name + "_seam.png")], check=True)
        if os.path.exists(wav):
            os.remove(wav)
        seam = entry.get("seam", {})
        lines.append("| %s | %.2f | %.1f | %.1f | %.3f | %.3f | %.3f | %.3f | %.4f |" % (name, entry["loop_offset"], entry["duration"], entry["duration"] - entry["loop_offset"],
                     entry.get("loop_score", 0), seam.get("seam_flux", 0), seam.get("flux_p50", 0), seam.get("flux_p95", 0), seam.get("sample_jump", 0)))
    lines += ["", "Seam flux below the median spectral flux of the track means the joint changes the sound less than an",
              "ordinary moment of the music does; the sample jump is the waveform step at the joint (0.0 = continuous)."]
    open(os.path.join(OUT, "loops.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
