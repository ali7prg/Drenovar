"""godot/project/assets/forest_rescue/humans/captive_variants.json for the v2 civilians.

36 campaign captives -> 6 civilian visuals by role and gender (Russian role / name gender), each with
a look variation the game applies per actor (actor_rig.apply_look):
  tint.cloth  multiplies the albedo of the tintable garment material (*_cloth: apron, cloak, hood,
              capelet, vest, cap) - hue shifts kept inside the sheet palette (oak / limestone /
              russet / bronze / muted emerald); the emerald rescue band is on *_gear and never tinted
  tint.hair   multiplies the hair/beard material (*_hair)
  hide        ["Bag"] collapses the accessory on the Bag bone (pouch / satchel / rope coil / hammer)
  scale       uniform height variation (0.96 .. 1.04)
No two captives of one cage share visual+variant.

    python3 forest_rescue/blender/assets/humans/v2/make_captive_variants_v2.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CAMPAIGN = os.path.join(REPO, "forest_rescue", "delivery", "data", "campaign.json")
OUT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans", "captive_variants.json")

# role (and name gender) -> visual
VISUAL = {
    "lf_captive_01_a": "courier",        # Лада, возница (carter, travels)
    "lf_captive_01_b": "ferryman",       # Тим, помощник конюха
    "lf_captive_01_c": "miller",         # Сава, пекарь (flour apron)
    "lf_captive_02_a": "quarry_worker",  # Орина, резчица
    "lf_captive_02_b": "cooper",         # Бран, каменщик (leather apron, hammer)
    "lf_captive_02_c": "herbalist",      # Мила, собирательница трав
    "lf_captive_03_a": "herbalist",      # Энна, ткачиха (long dress)
    "lf_captive_03_b": "ferryman",       # Радек, кровельщик
    "lf_captive_03_c": "miller",         # Ивар, ученик писаря (apron)
    "lf_captive_04_a": "courier",        # Верна, следопыт
    "lf_captive_04_b": "miller",         # Олек, носильщик
    "lf_captive_04_c": "quarry_worker",  # Нела, гончар
    "lf_captive_05_a": "quarry_worker",  # Дарна, смолокур
    "lf_captive_05_b": "ferryman",       # Егор, лодочник
    "lf_captive_05_c": "herbalist",      # Рута, портниха
    "lf_captive_06_a": "miller",         # Федор, углежог (dark apron)
    "lf_captive_06_b": "courier",        # Ася, сборщица ягод
    "lf_captive_06_c": "cooper",         # Марен, ремесленник
    "lf_captive_07_a": "quarry_worker",  # Лина, рыбачка
    "lf_captive_07_b": "cooper",         # Торен, плотник
    "lf_captive_07_c": "herbalist",      # Сима, лекарка
    "lf_captive_08_a": "herbalist",      # Ярина, певчая
    "lf_captive_08_b": "ferryman",       # Век, пастух
    "lf_captive_08_c": "quarry_worker",  # Дина, садовница
    "lf_captive_09_a": "ferryman",       # Мирен, картограф
    "lf_captive_09_b": "courier",        # Бела, сборщица коры
    "lf_captive_09_c": "cooper",         # Стас, ученик кузнеца
    "lf_captive_10_a": "quarry_worker",  # Грета, каменотёс
    "lf_captive_10_b": "cooper",         # Леван, обозный мастер
    "lf_captive_10_c": "herbalist",      # Ника, пекарь (dress, apron-less)
    "lf_captive_11_a": "courier",        # Марта, перевозчица
    "lf_captive_11_b": "ferryman",       # Рен, травник
    "lf_captive_11_c": "herbalist",      # Алва, швея
    "lf_captive_12_a": "quarry_worker",  # Тала, хранительница записей
    "lf_captive_12_b": "ferryman",       # Мирко, охотник
    "lf_captive_12_c": "quarry_worker",  # Эда, мельничная работница
}

# cloth multipliers (on the painted garment colour) - inside the sheet palette
CLOTH = {
    "as_painted": [1.0, 1.0, 1.0],
    "weathered_oak": [0.86, 0.80, 0.72],
    "russet": [1.12, 0.90, 0.80],
    "limestone": [1.06, 1.06, 1.04],
    "aged_bronze": [1.08, 0.98, 0.78],
    "muted_emerald": [0.84, 1.00, 0.88],
    "dusk": [0.90, 0.90, 0.98],
    "smoke": [0.78, 0.78, 0.78],
}
HAIR = {
    "as_painted": [1.0, 1.0, 1.0],
    "black": [0.62, 0.60, 0.60],
    "chestnut": [1.18, 0.96, 0.82],
    "auburn": [1.32, 0.88, 0.70],
    "dark_blond": [1.55, 1.32, 1.02],
    "ash": [1.20, 1.18, 1.16],
    "salt_pepper": [1.35, 1.33, 1.30],
}
PRESETS = {   # per visual: (cloth, hair, hide accessory, scale) - taken in campaign order
    "miller": [("as_painted", "as_painted", False, 1.00), ("smoke", "black", True, 0.98),
               ("aged_bronze", "chestnut", False, 1.03), ("weathered_oak", "auburn", True, 0.97)],
    "ferryman": [("as_painted", "as_painted", False, 1.00), ("weathered_oak", "chestnut", True, 0.97),
                 ("dusk", "black", False, 1.02), ("limestone", "dark_blond", True, 0.99),
                 ("russet", "auburn", False, 0.98), ("smoke", "salt_pepper", False, 1.01),
                 ("aged_bronze", "black", True, 1.03)],
    "cooper": [("as_painted", "as_painted", False, 1.00), ("weathered_oak", "ash", True, 0.98),
               ("russet", "salt_pepper", False, 1.02), ("dusk", "as_painted", True, 0.97),
               ("muted_emerald", "ash", False, 1.01)],
    "herbalist": [("as_painted", "as_painted", False, 1.00), ("russet", "auburn", True, 0.98),
                  ("dusk", "black", False, 1.01), ("aged_bronze", "chestnut", True, 0.97),
                  ("weathered_oak", "dark_blond", False, 1.02), ("limestone", "black", True, 0.99),
                  ("muted_emerald", "chestnut", False, 1.00), ("smoke", "auburn", True, 0.98)],
    "courier": [("as_painted", "as_painted", False, 1.00), ("muted_emerald", "dark_blond", True, 0.98),
                ("aged_bronze", "black", False, 1.02), ("dusk", "auburn", True, 0.97),
                ("weathered_oak", "chestnut", False, 1.01)],
    "quarry_worker": [("as_painted", "as_painted", False, 1.00), ("limestone", "chestnut", False, 0.98),
                      ("russet", "black", False, 1.02), ("dusk", "auburn", False, 0.97),
                      ("weathered_oak", "dark_blond", False, 1.01), ("aged_bronze", "black", False, 0.99),
                      ("muted_emerald", "chestnut", False, 1.03), ("smoke", "auburn", False, 0.98)],
}


def main():
    camp = json.load(open(CAMPAIGN, encoding="utf-8"))
    used = {v: 0 for v in PRESETS}
    out = {}
    for site in camp["sites"]:
        seen = set()
        for c in site["captives"]:
            vis = VISUAL[c["id"]]
            k = used[vis]
            used[vis] += 1
            cl, hr, hide, sc = PRESETS[vis][k % len(PRESETS[vis])]
            key = (vis, cl, hr, hide)
            assert key not in seen, (site["id"], key)
            seen.add(key)
            out[c["id"]] = {
                "visual": vis, "name": c["name"], "role": c["role"], "variant": k,
                "tint": {"cloth": CLOTH[cl], "hair": HAIR[hr]},
                "tintNames": {"cloth": cl, "hair": hr},
                "hide": ["Bag"] if hide else [], "scale": sc,
            }
    data = {
        "schemaVersion": 2,
        "note": ("captive id -> civilian visual (lf_civilian_<visual>.glb) + look variation. tint.<group> "
                 "multiplies the albedo of materials named *_<group> (cloth = tintable garments, hair = hair "
                 "and beard; the emerald rescue band is *_gear and never tinted); hide = bones scaled to 0 "
                 "(Bag carries the toggleable accessory); scale = uniform model scale. Applied by "
                 "actor_rig.apply_look via actor_director.captive_variant."),
        "visuals": sorted(PRESETS),
        "captives": out,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, {v: used[v] for v in used})


if __name__ == "__main__":
    main()
