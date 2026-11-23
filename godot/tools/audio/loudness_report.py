#!/usr/bin/env python3
"""Build 1024: offline loudness and size report of every file in godot/project/assets/audio.

  python3 -I godot/tools/audio/loudness_report.py [out_dir]   (default godot/runtime-audit-1024/audio)

Measures each OGG with ffmpeg (ebur128 integrated loudness, loudness range, true peak) and its leading
silence (first sample above -50 dBFS), and writes loudness.tsv, loudness.md and loudness.log (ffmpeg's
raw summaries). Targets: music -16 LUFS (±1), true peak <= -1 dBTP everywhere, leading silence
<= 10 ms (music and ambient beds may open with a fade-in), total <= 25 MB.
qa_audio_1024.gd reads loudness.tsv and checks it against the files on disk.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.abspath(os.path.join(HERE, "..", "..", "project", "assets", "audio"))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..", "runtime-audit-1024", "audio"))
SR = 44100


def measure(path):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True)
    text = proc.stderr
    summary = text[text.rfind("Summary:"):]
    def grab(label):
        m = re.search(label + r":\s+(-?[0-9.]+|-inf)", summary)
        return float(m.group(1)) if m and m.group(1) != "-inf" else -99.0
    return {"lufs": grab("I"), "lra": grab("LRA"), "true_peak": grab("Peak")}, summary.strip()


def lead_ms(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", "2", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    if x.size == 0:
        return -1.0
    above = np.nonzero(np.abs(x) > 10 ** (-50 / 20))[0]
    return round(1000.0 * above[0] / SR, 2) if above.size else 2000.0


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, logs = [], []
    for base, _dirs, files in sorted(os.walk(AUDIO)):
        for name in sorted(files):
            if not name.endswith(".ogg"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, AUDIO)
            m, summary = measure(path)
            kind = rel.split("/")[0]
            row = {"file": rel, "kind": kind, "lufs": m["lufs"], "lra": m["lra"], "true_peak": m["true_peak"],
                   "lead_ms": lead_ms(path), "bytes": os.path.getsize(path)}
            ok = row["true_peak"] <= -1.0
            if kind == "music":
                ok = ok and abs(row["lufs"] + 16.0) <= 1.0
            if kind == "sfx":
                ok = ok and row["lead_ms"] <= 10.0
            row["ok"] = ok
            rows.append(row)
            logs.append("== %s\n%s" % (rel, summary))
    with open(os.path.join(OUT, "loudness.tsv"), "w") as f:
        f.write("file\tkind\tlufs\tlra\ttrue_peak_dbtp\tlead_ms\tbytes\tok\n")
        for r in rows:
            f.write("%s\t%s\t%.1f\t%.1f\t%.1f\t%.2f\t%d\t%s\n" % (r["file"], r["kind"], r["lufs"], r["lra"], r["true_peak"], r["lead_ms"], r["bytes"], "ok" if r["ok"] else "FAIL"))
    open(os.path.join(OUT, "loudness.log"), "w").write("\n\n".join(logs) + "\n")
    total = sum(r["bytes"] for r in rows)
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    lines = ["# Build 1024 audio: loudness and size", "", "Measured by `godot/tools/audio/loudness_report.py` (ffmpeg ebur128, true peak).", "",
             "| Group | Files | MB | Integrated LUFS (min..max) | Max true peak dBTP | Max lead ms |", "|---|---|---|---|---|---|"]
    for kind, items in sorted(by_kind.items()):
        lu = [r["lufs"] for r in items if r["lufs"] > -70]
        lines.append("| %s | %d | %.2f | %s | %.1f | %.1f |" % (kind, len(items), sum(r["bytes"] for r in items) / 1048576.0,
                     ("%.1f..%.1f" % (min(lu), max(lu))) if lu else "n/a (shorter than 0.4 s)", max(r["true_peak"] for r in items),
                     max(r["lead_ms"] for r in items)))
    lines += ["", "Total: %.2f MB in %d files (limit 25 MB). Failures: %d." % (total / 1048576.0, len(rows), sum(1 for r in rows if not r["ok"])), "",
              "| File | LUFS | LRA | True peak | Lead ms | KB |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["kind"] != "sfx":
            lines.append("| %s | %.1f | %.1f | %.1f | %.1f | %d |" % (r["file"], r["lufs"], r["lra"], r["true_peak"], r["lead_ms"], r["bytes"] // 1024))
    open(os.path.join(OUT, "loudness.md"), "w").write("\n".join(lines) + "\n")
    print(json.dumps({"files": len(rows), "total_mb": round(total / 1048576.0, 2), "failures": [r["file"] for r in rows if not r["ok"]]}))


if __name__ == "__main__":
    main()
