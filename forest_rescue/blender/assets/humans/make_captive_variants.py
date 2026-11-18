"""Generate godot/project/assets/forest_rescue/humans/captive_variants.json.

Each of the 36 campaign captives (lf_captive_NN_a/b/c) maps to one of the six civilian base GLBs
plus a variant = material tint factors (garment / skin / hair baseColorFactor, the albedo atlas of
these groups is luminance-normalised) and optional-part toggles (hood up/down, cap on/off).
Plain python (no bpy):  python3 forest_rescue/blender/assets/humans/make_captive_variants.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CAMPAIGN = os.path.join(REPO, "forest_rescue", "delivery", "data", "campaign.json")
OUT_DIR = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans")

# role/gender -> base (16 men over 3 male bases, 20 women over 3 female bases)
BASE_OF = {
    "lf_captive_01_a": "courier", "lf_captive_01_b": "ferryman", "lf_captive_01_c": "miller",
    "lf_captive_02_a": "quarry_worker", "lf_captive_02_b": "cooper", "lf_captive_02_c": "herbalist",
    "lf_captive_03_a": "herbalist", "lf_captive_03_b": "ferryman", "lf_captive_03_c": "miller",
    "lf_captive_04_a": "courier", "lf_captive_04_b": "ferryman", "lf_captive_04_c": "quarry_worker",
    "lf_captive_05_a": "quarry_worker", "lf_captive_05_b": "ferryman", "lf_captive_05_c": "herbalist",
    "lf_captive_06_a": "miller", "lf_captive_06_b": "courier", "lf_captive_06_c": "cooper",
    "lf_captive_07_a": "courier", "lf_captive_07_b": "cooper", "lf_captive_07_c": "herbalist",
    "lf_captive_08_a": "herbalist", "lf_captive_08_b": "ferryman", "lf_captive_08_c": "quarry_worker",
    "lf_captive_09_a": "miller", "lf_captive_09_b": "courier", "lf_captive_09_c": "cooper",
    "lf_captive_10_a": "quarry_worker", "lf_captive_10_b": "cooper", "lf_captive_10_c": "quarry_worker",
    "lf_captive_11_a": "courier", "lf_captive_11_b": "miller", "lf_captive_11_c": "herbalist",
    "lf_captive_12_a": "herbalist", "lf_captive_12_b": "ferryman", "lf_captive_12_c": "quarry_worker",
}

GARMENT = {  # target median colour of the tintable garment group (sRGB-ish linear factors)
    "russet": (0.50, 0.25, 0.17), "madder": (0.56, 0.20, 0.15), "woad": (0.24, 0.31, 0.42),
    "moss": (0.29, 0.34, 0.21), "ochre": (0.58, 0.45, 0.23), "undyed": (0.60, 0.55, 0.45),
    "slate": (0.34, 0.36, 0.38), "walnut": (0.36, 0.26, 0.18), "emerald": (0.20, 0.33, 0.22),
    "heather": (0.42, 0.33, 0.40),
}
SKIN = {"fair": (1.06, 1.05, 1.04), "base": (1.0, 1.0, 1.0), "olive": (0.94, 0.92, 0.84),
        "tan": (0.90, 0.82, 0.74), "deep": (0.70, 0.58, 0.50)}
HAIR = {"black": (0.07, 0.06, 0.055), "dark_brown": (0.17, 0.11, 0.075), "chestnut": (0.30, 0.17, 0.09),
        "auburn": (0.40, 0.17, 0.08), "dark_blond": (0.50, 0.38, 0.22), "grey": (0.50, 0.49, 0.47),
        "white": (0.78, 0.76, 0.72), "salt_pepper": (0.32, 0.30, 0.28)}

# per base: ordered list of variant presets; captives of a base take them in campaign order
PRESETS = {
    "miller": [("russet", "base", "dark_brown", {}), ("woad", "tan", "black", {}), ("ochre", "fair", "chestnut", {}),
               ("slate", "olive", "salt_pepper", {}), ("madder", "deep", "black", {}), ("undyed", "base", "auburn", {})],
    "ferryman": [("slate", "base", "dark_brown", {}), ("walnut", "fair", "dark_blond", {}), ("moss", "tan", "black", {}),
                 ("woad", "olive", "chestnut", {}), ("undyed", "deep", "black", {}), ("russet", "base", "auburn", {}),
                 ("heather", "fair", "dark_brown", {})],
    "cooper": [("undyed", "base", "grey", {"cap": True}), ("ochre", "tan", "dark_brown", {"cap": False}),
               ("slate", "fair", "salt_pepper", {"cap": True}), ("walnut", "olive", "chestnut", {"cap": False}),
               ("woad", "deep", "white", {"cap": True}), ("russet", "base", "black", {"cap": False})],
    "herbalist": [("emerald", "base", "dark_brown", {"hood_up": True, "hood_down": False}),
                  ("heather", "fair", "auburn", {"hood_up": False, "hood_down": True}),
                  ("ochre", "olive", "black", {"hood_up": True, "hood_down": False}),
                  ("woad", "tan", "chestnut", {"hood_up": False, "hood_down": True}),
                  ("madder", "fair", "dark_blond", {"hood_up": True, "hood_down": False}),
                  ("slate", "deep", "black", {"hood_up": False, "hood_down": True}),
                  ("moss", "base", "grey", {"hood_up": True, "hood_down": False})],
    "courier": [("russet", "base", "dark_brown", {}), ("woad", "fair", "dark_blond", {}), ("moss", "olive", "black", {}),
                ("madder", "tan", "chestnut", {}), ("ochre", "deep", "black", {}), ("heather", "base", "auburn", {})],
    "quarry_worker": [("slate", "base", "dark_brown", {}), ("undyed", "tan", "black", {}),
                      ("walnut", "fair", "auburn", {}), ("woad", "olive", "chestnut", {}),
                      ("moss", "deep", "black", {}), ("ochre", "base", "grey", {}), ("heather", "fair", "dark_blond", {})],
}


def mul(a, b):
    return [round(x * y, 4) for x, y in zip(a, b)]


def main():
    camp = json.load(open(CAMPAIGN, encoding="utf-8"))
    captives = [(c, s["id"]) for s in camp["sites"] for c in s["captives"]]
    metas = {}
    for base in PRESETS:
        p = os.path.join(OUT_DIR, f"lf_civilian_{base}.meta.json")
        metas[base] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    counters = {b: 0 for b in PRESETS}
    out = {"schemaVersion": 1, "campaignId": camp["id"],
           "notes": ("Each captive keeps its campaign id/name/role. 'materials' are glTF baseColorFactor "
                     "overrides (RGB, linear multipliers of the luminance-normalised atlas) for the base GLB's "
                     "materials <base>_garment / _skin / _hair; 'parts' toggles optional meshes "
                     "<base>_opt_<part>_LOD0/1/2 (visible=true). No new rigs: all use rig human_shared and the "
                     "civilian clip set inside the base GLB."),
           "bases": {}, "captives": {}}
    for base, meta in metas.items():
        out["bases"][base] = {"glb": f"res://assets/forest_rescue/humans/lf_civilian_{base}.glb",
                              "asset_id": f"lf_civilian_{base}",
                              "default_factors": (meta or {}).get("materialTint", {}),
                              "group_median": (meta or {}).get("materialMedian", {}),
                              "optional_parts": (meta or {}).get("optionalParts", [])}
    for cap, site in captives:
        base = BASE_OF[cap["id"]]
        k = counters[base]
        counters[base] += 1
        g, sk, hr, parts = PRESETS[base][k % len(PRESETS[base])]
        meta = metas[base] or {}
        tint = meta.get("materialTint", {})
        med = meta.get("materialMedian", {})
        mats = {}
        # garment: absolute target colour -> factor = default_factor * target / original median
        if "garment" in tint and "garment" in med:
            mats[f"lf_civilian_{base}_garment"] = mul(tint["garment"], [t / max(m, 1e-3) for t, m in
                                                                        zip(GARMENT[g], med["garment"])])
        if "skin" in tint:
            mats[f"lf_civilian_{base}_skin"] = mul(tint["skin"], SKIN[sk])
        if "hair" in tint and "hair" in med:
            mats[f"lf_civilian_{base}_hair"] = mul(tint["hair"], [t / max(m, 1e-3) for t, m in zip(HAIR[hr], med["hair"])])
        out["captives"][cap["id"]] = {
            "name": cap["name"], "role": cap["role"], "site": site, "base": base,
            "base_glb": f"res://assets/forest_rescue/humans/lf_civilian_{base}.glb",
            "variant": f"{base}_v{k + 1:02d}", "garment_tint": g, "skin_tone": sk, "hair": hr,
            "headwear": {kk: v for kk, v in parts.items()}, "materials": mats,
            "parts": {kk: v for kk, v in parts.items()},
            "height_scale": round(1.0 + 0.012 * ((sum(map(ord, cap["id"])) % 5) - 2), 3),
        }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "captive_variants.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(path, {b: counters[b] for b in counters})


if __name__ == "__main__":
    main()
