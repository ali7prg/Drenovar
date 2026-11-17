"""Copies built creatures into the Godot project and writes assets/creatures-v2/registry.json.
Usage: python3 -I publish.py <work-root> <godot/project> [species ...]
"""
import json
import os
import shutil
import sys
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Display adapter: model metres -> the existing in-game size of each species (battle places and
# camera were laid out for these bodies; 02_CREATURES.txt sizes stay the authored truth).
# Old CREATURE_BODY half lengths (landscape.gd) / new authored half lengths.
OLD_HALF_LENGTH = {"velkor": 2.51, "tenerys": 2.63, "kamneklyk": 2.62, "dragor": 3.15}
DESCRIPTIONS = {
    "velkor": "Лесной хранитель. Опускает рога и бьёт широким взмахом; каждым третьим ударом идёт на таран.",
    "tenerys": "Сумрачный хищник. Кусает и бьёт лапой; каждым третьим ударом прыгает на выбранную цель.",
    "kamneklyk": "Бронированный вепрь. Подхватывает клыками; каждым третьим ударом цепляет до трёх бойцов.",
    "dragor": "Горный исполин. Бьёт тяжёлой лапой; каждым третьим ударом поднимается и обрушивает землю.",
}


def measure(work, species):
    import numpy as np
    d = os.path.join(work, species, "lod1")
    sp = importlib.import_module("species." + species)
    sk, parts = sp.build_cached()
    body_idx = [p["index"] for p in parts if p["rigid"] is None]
    xs, zs, ys = [], [], []
    for group in sp.CLASSES:
        path = os.path.join(d, f"{group}_mesh.npz")
        if not os.path.exists(path):
            continue
        z = np.load(path)
        pos, part = z["pos"], z["part"]
        sel = np.isin(part, body_idx)
        xs.append(pos[:, 0])
        ys.append(pos[:, 1])
        zs.append(pos[sel, 2])
    x = np.concatenate(xs)
    zz = np.concatenate(zs)
    y = np.concatenate(ys)
    return float(x.min()), float(x.max()), float(np.abs(zz).max()), float(y.max())


def main():
    work, project = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or ["velkor", "tenerys", "kamneklyk", "dragor"]
    out_root = os.path.join(project, "assets", "creatures-v2")
    os.makedirs(out_root, exist_ok=True)
    reg_path = os.path.join(out_root, "registry.json")
    reg = json.load(open(reg_path)) if os.path.exists(reg_path) else {"version": 1, "species": {}}
    for sid in names:
        sp = importlib.import_module("species." + sid)
        src = os.path.join(work, sid, "out")
        dst = os.path.join(out_root, sid)
        os.makedirs(dst, exist_ok=True)
        # runtime asset: .gltf + .bin + <sid>_textures/ (Godot imports the textures once, no copy in a GLB)
        for old in os.listdir(dst):
            if old.startswith(f"{sid}_runtime.glb") or old.startswith(f"{sid}_runtime_"):
                os.remove(os.path.join(dst, old))
        g = os.path.join(src, "godot")
        shutil.copyfile(os.path.join(g, f"{sid}_runtime.gltf"), os.path.join(dst, f"{sid}_runtime.gltf"))
        shutil.copyfile(os.path.join(g, f"{sid}_runtime.bin"), os.path.join(dst, f"{sid}_runtime.bin"))
        tdst = os.path.join(dst, f"{sid}_textures")
        os.makedirs(tdst, exist_ok=True)
        keep = set(os.listdir(os.path.join(g, f"{sid}_textures")))
        for old in os.listdir(tdst):
            if old not in keep and not (old.endswith(".import") and old[:-7] in keep):
                os.remove(os.path.join(tdst, old))
        for name in keep:
            shutil.copyfile(os.path.join(g, f"{sid}_textures", name), os.path.join(tdst, name))
        shutil.copyfile(os.path.join(src, "clip_manifest.json"), os.path.join(dst, "clip_manifest.json"))
        masks = {}
        for group in sp.CLASSES:
            masks[group] = {}
            for lod in (1, 2):
                m = os.path.join(work, sid, f"lod{lod}", f"{group}_variant.png")
                if os.path.exists(m):
                    name = f"{sid}_{group}_lod{lod}_variant.png"
                    shutil.copyfile(m, os.path.join(dst, name))
                    masks[group][str(lod)] = f"res://assets/creatures-v2/{sid}/{name}"
        x0, x1, half_w, top = measure(work, sid)
        half_len = (x1 - x0) / 2.0
        scale = round(OLD_HALF_LENGTH[sid] / half_len, 3)
        levels = {str(k): {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
                  for k, v in sp.LEVELS.items()}
        reg["species"][sid] = {
            "name": sp.NAME, "model": f"res://assets/creatures-v2/{sid}/{sid}_runtime.gltf",
            "manifest": f"res://assets/creatures-v2/{sid}/clip_manifest.json",
            "display_scale": scale, "body": [round(half_len * scale, 3), round(half_w * scale, 3)],
            "authored_bounds_m": {"x": [round(x0, 3), round(x1, 3)], "half_width": round(half_w, 3), "top": round(top, 3)},
            "lod_switch_m": round(9.0 * top, 1), "groups": sp.MATERIAL_NAMES, "variant_masks": masks,
            "emission_color": sp.EMISSION_COLOR, "levels": levels, "description": DESCRIPTIONS[sid],
            "portraits": [f"res://assets/creatures-v2/{sid}/{sid}_portrait_{lv}.webp" for lv in (1, 2, 3)],
        }
        print(sid, "display_scale", scale, "body", reg["species"][sid]["body"])
    with open(reg_path, "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
