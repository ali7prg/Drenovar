"""Write godot/project/assets/forest_rescue/props/site_props.json: which cage / socket / artifact variant /
mechanism each of the 12 sites uses (proposal by site variation, biome and key name), plus the per-site
mechanism symbol targets copied from the mechanism meta files.

Run (plain python, no Blender needed): python3 forest_rescue/blender/assets/props/write_site_props.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.dirname(FR)
DATA = os.path.join(FR, "delivery", "data")
OUT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "props")

# cage per site: oak = built clearings / stone ground, iron = chapel/charcoal/river (forged, portable),
# root = resin lowland / grass labyrinth / fern ledge / ancient grove (living forest)
CAGE = {"lf_site_01": "oak", "lf_site_02": "oak", "lf_site_04": "oak", "lf_site_10": "oak",
        "lf_site_03": "iron", "lf_site_06": "iron", "lf_site_07": "iron", "lf_site_11": "iron",
        "lf_site_05": "root", "lf_site_08": "root", "lf_site_09": "root", "lf_site_12": "root"}
# artifact family + variant per key (3 per family); bone keys go into the keyhole plate of any cage
ARTIFACT = {"lf_key_01": ("stone_rune", 1), "lf_key_02": ("stone_rune", 2), "lf_key_04": ("stone_rune", 3),
            "lf_key_11": ("bronze_seal", 1), "lf_key_03": ("bronze_seal", 2), "lf_key_06": ("bronze_seal", 3),
            "lf_key_05": ("amber_crystal", 1), "lf_key_08": ("amber_crystal", 2), "lf_key_09": ("amber_crystal", 3),
            "lf_key_10": ("bone_key", 1), "lf_key_07": ("bone_key", 2), "lf_key_12": ("bone_key", 3)}
WHY = {
    "lf_key_01": "«Берестяная печать» - first site, oak cage: the drawn spiral stone medallion in the cage's native round socket (vertical slice)",
    "lf_key_02": "«Печать трёх граней» - three facets -> triskele with three rim notches",
    "lf_key_04": "«Печать елового круга» - spruce circle -> fir sprig in a ring, scalloped rim",
    "lf_key_11": "«Печать дальнего берега» - the drawn three-leaf sprig seal",
    "lf_key_03": "«Печать тихого колокола» - bells are bronze -> bell emblem, notched corners",
    "lf_key_06": "«Печать возвращённого огня» - charcoal/forge site -> flame emblem, raised boss",
    "lf_key_05": "«Янтарная печать» in «Смоляная низина» - the drawn amber crystal",
    "lf_key_08": "«Печать двух троп» - two crystals split by a bronze bar",
    "lf_key_09": "«Печать трёх уступов» - three-step terraced crystal",
    "lf_key_10": "«Печать каменного дыхания» (late act 4, oak cage) - bone key with round bow in the keyhole plate",
    "lf_key_07": "«Печать мелкой воды» - trefoil bow, two-notch bit",
    "lf_key_12": "«Печать последней двери» in «Роща старых костей» - bone key, square bow with cross",
}
CAGE_ASSET = {"oak": "lf_cage_wood", "iron": "lf_cage_iron", "root": "lf_cage_root"}
NATIVE = {"oak": ("circle", "stone_rune"), "iron": ("hex", "bronze_seal"), "root": ("diamond", "amber_crystal")}
MECH = {"trail_cache": "lf_mechanism_trail_cache", "rune_lock": "lf_mechanism_rune_lock",
        "winch_sequence": "lf_mechanism_winch_sequence", "paired_latch": "lf_mechanism_paired_latch"}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    camp = load(os.path.join(DATA, "campaign.json"))
    atlas = load(os.path.join(DATA, "world-atlas.json"))
    asites = {s["id"]: s for s in atlas["sites"]}
    out = {"schemaVersion": 1, "campaignId": camp["id"],
           "status": "proposal by the props production pass (art-side mapping; server ids unchanged)",
           "rules": {"cage_by": "site biome / story (see cage_reason)",
                     "socket": "native socket of the cage matches its artifact family (oak=circle/stone_rune, "
                               "iron=hex/bronze_seal, root=diamond/amber_crystal); bone keys use the keyhole plate "
                               "(socket_keyhole_pivot, scale 0 by default) of whichever cage the site has",
                     "door": "hinge on the left jamb seen from outside, opens outward 95 deg; door side faces the "
                             "atlas escapeApproachOffset (+Z)",
                     "families_balanced": "4 families x 3 variants = 12 keys; each cage type hosts 3 native + 1 bone key"},
           "cage_reason": {"oak": "built clearings near paths / stone ground (birch watch, stone pocket, fir hollow, broken terrace)",
                           "iron": "forged, portable cages for chapel/charcoal/ford/river-terrace sites",
                           "root": "living-forest sites (resin lowland, grass labyrinth, fern ledge, ancient grove)"},
           "sites": {}}
    metas = {}
    for k, a in MECH.items():
        p = os.path.join(OUT, f"{a}.meta.json")
        if os.path.exists(p):
            metas[k] = load(p)
    for s in camp["sites"]:
        sid = s["id"]
        key = s["artifact"]["id"]
        fam, var = ARTIFACT[key]
        cage = CAGE[sid]
        native_shape, native_fam = NATIVE[cage]
        socket = "keyhole" if fam == "bone_key" else native_shape
        assert fam == "bone_key" or fam == native_fam, (sid, fam, cage)
        mech = {"kind": s["variation"], "glb": f"{MECH[s['variation']]}.glb",
                "solution": s["artifact"]["puzzle"]["solution"]}
        mm = metas.get(s["variation"], {}).get("symbol_targets")
        if mm:
            if s["variation"] == "rune_lock":
                mech["targets"] = mm["sites"].get(sid)
            elif s["variation"] == "trail_cache":
                mech["targets"] = {sym: mm["landmarks"][mm["sites"][sid][sym]] for sym in mech["solution"]}
            else:
                mech["targets"] = {sym: mm[sym] for sym in mech["solution"] if sym in mm}
        a = asites.get(sid, {})
        out["sites"][sid] = {
            "name": s["name"], "act": s["act"], "variation": s["variation"], "biome": a.get("zoneId"),
            "cage": {"type": cage, "glb": f"{CAGE_ASSET[cage]}.glb", "socket_shape": socket,
                     "socket_node": "socket_keyhole_pivot" if socket == "keyhole" else "socket_pivot",
                     "key_slot_node": "key_slot_keyhole" if socket == "keyhole" else "key_slot",
                     "placement": {"cageOffset": a.get("cageOffset"), "escapeApproachOffset": a.get("escapeApproachOffset"),
                                   "door_faces": "+Z (glTF) = toward escapeApproachOffset"}},
            "artifact": {"key": key, "name": s["artifact"]["name"], "family": fam, "variant": var,
                         "glb": f"lf_artifact_{fam}.glb", "node": f"lf_artifact_{fam}_v{var}", "why": WHY[key]},
            "mechanism": mech,
        }
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "site_props.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote", p)


if __name__ == "__main__":
    main()
