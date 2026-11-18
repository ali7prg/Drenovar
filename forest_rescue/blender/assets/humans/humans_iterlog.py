"""Iteration log helper: qa/compare/<asset>/iterations.json  [{tag, iou, colour, differences, changes}]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QA = os.path.abspath(os.path.join(HERE, "..", "..", "..", "qa", "compare"))


def path(asset):
    os.makedirs(os.path.join(QA, asset), exist_ok=True)
    return os.path.join(QA, asset, "iterations.json")


def load(asset):
    p = path(asset)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def note(asset, tag, differences, changes):
    log = load(asset)
    m = {}
    for v in ("front", "back"):
        f = os.path.join(QA, asset, f"{tag}_{v}.json")
        if not os.path.exists(f):
            f = os.path.join(QA, asset, f"{tag}_geo_{v}.json")
        if os.path.exists(f):
            d = json.load(open(f))
            m[v] = {"iou": d["iou"], "colour_error": d["mean_abs_colour_error"]}
    log = [e for e in log if e["tag"] != tag]
    log.append({"tag": tag, "metrics": m, "differences": differences, "changes_for_next": changes})
    log.sort(key=lambda e: e["tag"])
    json.dump(log, open(path(asset), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    a, t = sys.argv[1], sys.argv[2]
    note(a, t, sys.argv[3].split(" | "), sys.argv[4].split(" | "))
