"""In-engine check of the exported prop GLBs (Godot 4.6 Mobile viewer) side by side with the drawings.

Usage: python3 forest_rescue/blender/assets/props/godot_check.py <asset_id> <iter> [anim] [yaw] [pitch]
Writes forest_rescue/qa/compare/<asset>/iterNN_godot_shots/*.png, iterNN_godot_vs_drawing.png and
forest_rescue/qa/video/<asset>/godot_<anim>.mp4 (front-left 3/4 camera like the drawings).
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.dirname(FR)
TOOL = os.path.join(FR, "tools", "godot_view.sh")
RUNTIME = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "props")
ART = os.path.join(FR, "delivery", "art")
DRAW = {
    "lf_cage_wood": ("cage_variants_gate_sockets.png", (100, 110, 492, 432)),
    "lf_cage_iron": ("cage_variants_gate_sockets.png", (598, 110, 972, 446)),
    "lf_cage_root": ("cage_variants_gate_sockets.png", (1062, 100, 1490, 426)),
    "lf_artifact_stone_rune": ("loot_artifact_families.png", (20, 130, 390, 680)),
    "lf_artifact_bronze_seal": ("loot_artifact_families.png", (400, 130, 770, 680)),
    "lf_artifact_amber_crystal": ("loot_artifact_families.png", (780, 130, 1150, 680)),
    "lf_artifact_bone_key": ("loot_artifact_families.png", (1160, 130, 1530, 680)),
    "lf_props_supplies": ("loot_artifact_families.png", (0, 690, 1536, 1024)),
    "lf_mechanism_trail_cache": ("10_artifact_mechanisms.png", (0, 60, 760, 500)),
    "lf_mechanism_rune_lock": ("10_artifact_mechanisms.png", (770, 50, 1536, 500)),
    "lf_mechanism_winch_sequence": ("10_artifact_mechanisms.png", (0, 500, 740, 1024)),
    "lf_mechanism_paired_latch": ("10_artifact_mechanisms.png", (740, 500, 1536, 1024)),
}


def frames(mp4, times, fps=30):
    import cv2
    cap = cv2.VideoCapture(mp4)
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        if ok:
            out.append(fr[..., ::-1])
    cap.release()
    return out


def main():
    asset = sys.argv[1]
    it = int(sys.argv[2])
    anim = sys.argv[3] if len(sys.argv) > 3 else "all"
    yaw = sys.argv[4] if len(sys.argv) > 4 else "-40"
    pitch = sys.argv[5] if len(sys.argv) > 5 else "24"
    glb = os.path.join(RUNTIME, f"{asset}.glb")
    if asset.startswith("lf_artifact"):
        q = os.path.join(FR, "qa", "compare", asset, f"{asset}_layout_qa.glb")
        glb = q if os.path.exists(q) else glb
    cdir = os.path.join(FR, "qa", "compare", asset)
    shots = os.path.join(cdir, f"iter{it:02d}_godot_shots")
    os.makedirs(shots, exist_ok=True)
    r = subprocess.run(["bash", TOOL, glb, "shots", shots, "all", "6", "--pitch=" + pitch], capture_output=True, text=True)
    print(r.stdout[-600:])
    vdir = os.path.join(FR, "qa", "video", asset)
    os.makedirs(vdir, exist_ok=True)
    mp4 = os.path.join(vdir, f"godot_{anim}.mp4")
    secs = "8" if anim == "all" else "4"
    r = subprocess.run(["bash", TOOL, glb, "clip", mp4, anim, secs, "--yaw=" + yaw, "--pitch=" + pitch, "--dist=1.05"],
                       capture_output=True, text=True)
    print(r.stdout[-400:])
    img, box = DRAW[asset]
    ref = Image.open(os.path.join(ART, img)).convert("RGB").crop(box)
    tiles = [np.asarray(ref)]
    labels = ["drawing"]
    fr = frames(mp4, [0.05, 1.9]) if os.path.exists(mp4) else []
    for k, f in enumerate(fr):
        tiles.append(f)
        labels.append(f"Godot {anim} t={[0.05, 1.9][k]}s")
    for nm in ("shot_yaw000.png", "shot_yaw045.png"):
        p = os.path.join(shots, nm)
        if os.path.exists(p):
            tiles.append(np.asarray(Image.open(p).convert("RGB")))
            labels.append("Godot " + nm[5:-4])
    H = 360
    row = []
    from PIL import ImageDraw
    for t, l in zip(tiles, labels):
        im = Image.fromarray(t).resize((max(1, int(t.shape[1] * H / t.shape[0])), H))
        d = ImageDraw.Draw(im)
        d.rectangle([4, 4, 12 + 7 * len(l), 22], fill=(20, 20, 20))
        d.text((8, 7), l, fill=(255, 240, 200))
        row.append(np.asarray(im))
    sheet = np.concatenate(row, 1)
    Image.fromarray(sheet).save(os.path.join(cdir, f"iter{it:02d}_godot_vs_drawing.png"))
    print("sheet", os.path.join(cdir, f"iter{it:02d}_godot_vs_drawing.png"))


if __name__ == "__main__":
    main()
