"""Aggregate the v2 human QA: per character best/latest turnaround metrics, portrait SSIM, tris and
bones per LOD, clips (duration, loop, foot slip) -> qa/compare/humans_v2_summary.json + a printable
table on stdout.   python3 forest_rescue/blender/assets/humans/v2/summary_v2.py"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
QA = os.path.join(REPO, "forest_rescue", "qa", "compare")
HUM = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans")
IDS = ["lf_civilian_miller", "lf_civilian_herbalist", "lf_civilian_ferryman", "lf_civilian_courier",
       "lf_civilian_cooper", "lf_civilian_quarry_worker", "lf_squad_captain", "lf_squad_scout",
       "lf_squad_shield_guard"]


def main():
    out = {}
    for aid in IDS:
        its = sorted(glob.glob(os.path.join(QA, aid, "v2_iter*_metrics.json")))
        hist = []
        for p in its:
            it = int(re.search(r"iter(\d+)", p).group(1))
            m = json.load(open(p))
            hist.append(dict(iter=it, front=m.get("front"), back=m.get("back"), portrait=m.get("portrait")))
        meta_p = os.path.join(HUM, f"{aid}.meta.json")
        meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
        out[aid] = dict(first=hist[0] if hist else None, latest=hist[-1] if hist else None,
                        tris=meta.get("tris"), bones=meta.get("bones", {}).get("weightedByLOD"),
                        deform=meta.get("bones", {}).get("deform"),
                        clips={k: dict(seconds=v["seconds"], loop=v["loop"], slip_mm=v.get("footSlip_mm"),
                                       speed=v.get("groundSpeed_mps"), markers=v.get("markers"))
                               for k, v in meta.get("clips", {}).items()})
    json.dump(out, open(os.path.join(QA, "humans_v2_summary.json"), "w"), indent=1, ensure_ascii=False)
    for aid, d in out.items():
        f, l = d["first"], d["latest"]
        if not l:
            print(aid, "no metrics")
            continue
        fm = lambda h, k: (h[k]["iou"], h[k]["colour_error"]) if h and h.get(k) else None  # noqa: E731
        print(aid, "first", f["iter"], fm(f, "front"), fm(f, "back"), "latest", l["iter"], fm(l, "front"), fm(l, "back"),
              "portrait", l.get("portrait"), "tris", d["tris"], "bones", d["bones"])


if __name__ == "__main__":
    main()
