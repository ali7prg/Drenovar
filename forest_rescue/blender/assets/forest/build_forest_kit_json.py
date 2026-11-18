"""Write godot/project/assets/forest_rescue/forest/forest_kit.json from the per-asset meta files.

Run: python3 forest_rescue/blender/assets/forest/build_forest_kit_json.py   (plain python, no Blender)
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "forest")
DATA = os.path.join(REPO, "forest_rescue", "delivery", "data")

# gameplay base footprint (trunk + root flare collision radius) and recommended scale range per asset
INFO = {
    "lf_env_golden_oak": dict(footprint=1.6, scale=(0.65, 1.1), role="resource tree «Дуб» + ambient oak"),
    "lf_env_dark_pine": dict(footprint=0.7, scale=(0.75, 1.3), role="resource tree «Сосна» + ambient pine/spruce/fir"),
    "lf_env_birch": dict(footprint=0.9, scale=(0.8, 1.35), role="ambient birch (lf_tree_birch)"),
    "lf_env_willow": dict(footprint=1.2, scale=(0.8, 1.2), role="riverbank willow"),
    "lf_env_hollow_oak": dict(footprint=4.6, scale=(0.9, 1.05), role="hero landmark tree (walk-through hollow)"),
    "lf_env_fallen_trunk": dict(footprint=5.2, scale=(0.8, 1.2), role="feature: fallen trunk / log bridge"),
    "lf_env_moss_rock": dict(footprint=None, scale=(0.7, 1.3), role="limestone outcrop / boulders"),
    "lf_env_bramble": dict(footprint=None, scale=(0.8, 1.3), role="thorn bramble with berries"),
    "lf_env_reed_fern": dict(footprint=None, scale=(0.8, 1.45), role="reeds (wet banks) and fern clusters"),
    "lf_env_grass_tuft": dict(footprint=0.3, scale=(0.8, 1.5), role="near-chunk grass scatter"),
    "lf_env_fallen_branches": dict(footprint=1.2, scale=(0.8, 1.3), role="near-chunk deadwood scatter"),
    "lf_env_mushrooms": dict(footprint=0.3, scale=(0.8, 1.6), role="near-chunk mushroom scatter"),
}


def load_meta(asset):
    p = os.path.join(RT, f"{asset}.meta.json")
    return json.load(open(p)) if os.path.exists(p) else None


def candidates():
    a = json.load(open(os.path.join(DATA, "ambient-candidates.json")))
    cnt = collections.Counter()
    sc = collections.defaultdict(list)
    for ch in a["chunks"]:
        for i in ch["instances"]:
            cnt[i["assetId"]] += 1
            sc[i["assetId"]].append(i["scale"])
    return {k: dict(count=v, scale=[round(min(sc[k]), 3), round(max(sc[k]), 3)]) for k, v in cnt.items()}


def entry(asset, variants=None):
    m = load_meta(asset)
    if m is None:
        return dict(glb=f"{asset}.glb", status="missing")
    vs = m["variants"]
    names = variants or list(vs)
    out = dict(glb=f"{asset}.glb", meta=f"{asset}.meta.json", role=INFO[asset]["role"],
               variants={}, recommendedScale=list(INFO[asset]["scale"]))
    for vn in names:
        v = vs[vn]
        canopy = v.get("crown_radius_m", v.get("footprint_radius_m"))
        fp = INFO[asset]["footprint"] if INFO[asset]["footprint"] is not None else v.get("footprint_radius_m", canopy)
        out["variants"][vn] = dict(nodes=v["nodes"], tris=v["tris"], height_m=v.get("height_m"),
                                   canopyRadius_m=canopy, footprintRadius_m=round(min(fp, canopy or fp), 2),
                                   materials=v.get("materials"))
    return out


def main():
    cands = candidates()
    kit = {
        "schema": 1,
        "group": "forest",
        "note": "Mesh resources per variant/LOD; node translations in the GLBs are preview offsets only. "
                "Instance with deterministic transforms (seeded yaw 0..2pi, scale inside recommendedScale).",
        "sharedTextures": {"foliageAtlas": "lf_foliage_atlas.png (2048, RGBA, alpha cutoff 0.5)",
                           "bark": "lf_bark_{oak,pine,birch,hollow,willow}_{c.jpg,n.png,r.png} (1024)",
                           "rock": "lf_rock_limestone_{c.jpg,n.png,r.png} (1024)"},
        "wind": {"clip": "lf_forest_wind", "seconds": 8.0, "shader": "lf_forest_wind.gdshader",
                 "COLOR_0": "R sway (0 trunk base -> 1 tips), G leaf flutter, B per-branch phase, A crown AO"},
        "lodPolicy": {"LOD0": "near (bark + foliage surfaces)", "LOD1": "mid, single foliage-atlas surface (≈40%)",
                      "LOD2": "far card-cloud, single surface (≤300 tris)",
                      "suggestedVisibilityRange_m": {"LOD0": [0, 45], "LOD1": [40, 110], "LOD2": [100, 400]}},
        "ambientCandidates": {},
        "resourceTrees": {"oak «Дуб»": entry("lf_env_golden_oak"), "pine «Сосна»": entry("lf_env_dark_pine")},
        "biomeTreeMix": {
            "birch": {"asset": "lf_env_birch", "variants": ["v1", "v2", "v3"]},
            "pine": {"asset": "lf_env_dark_pine", "variants": ["v1", "v2", "v3", "v4"]},
            "fir": {"asset": "lf_env_dark_pine", "variants": ["v1", "v3"], "note": "spruce/fir silhouettes"},
            "ancient_pine": {"asset": "lf_env_dark_pine", "variants": ["v4", "v2"], "scale": [1.1, 1.35]},
            "alder": {"asset": "lf_env_birch", "variants": ["v2", "v3"], "note": "no dedicated alder: slender birch stand-in"},
            "willow": {"asset": "lf_env_willow", "variants": ["v1", "v2", "v3"]},
            "fern": {"asset": "lf_env_reed_fern", "variants": ["fern_v1", "fern_v2"]},
            "deadwood": {"asset": "lf_env_fallen_trunk", "variants": ["v2"], "extra": ["lf_env_fallen_branches",
                                                                                       "lf_env_hollow_oak v3 (snag)"]},
            "charcoal_stump": {"asset": None, "note": "not in this kit (no reference); use lf_env_fallen_branches + "
                                                       "lf_env_hollow_oak v3 tinted, or request a stump asset"},
            "bone_rock": {"asset": "lf_env_moss_rock", "variants": ["v1", "v2", "v3"]},
            "reed_bank_palette": {"asset": "lf_env_reed_fern", "variants": ["reed_v1", "reed_v2", "mixed_v1"]},
        },
        "assets": {},
    }
    mapping = {"lf_tree_pine": ("lf_env_dark_pine", None), "lf_tree_birch": ("lf_env_birch", None),
               "lf_fern_cluster": ("lf_env_reed_fern", ["fern_v1", "fern_v2"])}
    for cid, info in cands.items():
        asset, vs = mapping.get(cid, (None, None))
        e = entry(asset, vs) if asset else {"status": "unmapped"}
        e["candidateCount"] = info["count"]
        e["candidateScaleRange"] = info["scale"]
        kit["ambientCandidates"][cid] = e
    for asset in INFO:
        kit["assets"][asset] = entry(asset)
    with open(os.path.join(RT, "forest_kit.json"), "w", encoding="utf-8") as f:
        json.dump(kit, f, ensure_ascii=False, indent=1)
    print("wrote forest_kit.json", {k: v.get("status", "ok") for k, v in kit["assets"].items()})


if __name__ == "__main__":
    main()
