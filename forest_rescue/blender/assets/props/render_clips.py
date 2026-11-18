"""Render every node-animation clip of built prop assets to MP4 (from the saved .blend masters).

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/render_clips.py <asset_id> [<asset_id> ...]
Camera: the fitted drawing camera stored in qa/compare/props_cams/*.json (closed/main view), EEVEE.
Also writes a contact sheet per clip (qa/video/<asset>/<clip>_sheet.png).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import numpy as np

import propkit as pk
from frlib import paths, render

CAMS = {"lf_cage_wood": ("cage_cams.json", "closed"), "lf_cage_iron": ("cage_cams.json", "closed"),
        "lf_cage_root": ("cage_cams.json", "closed"), "lf_mechanism_rune_lock": ("mech_cams.json", "closed"),
        "lf_mechanism_winch_sequence": ("mech_cams.json", "main"), "lf_mechanism_paired_latch": ("mech_cams.json", "unpressed"),
        "lf_mechanism_trail_cache": ("mech_cams.json", "main"), "lf_props_supplies": ("supplies_cams.json", "chest")}
CROPS = {"lf_cage_wood": (392, 322), "lf_cage_iron": (374, 336), "lf_cage_root": (428, 326),
         "lf_mechanism_rune_lock": (322, 326), "lf_mechanism_winch_sequence": (528, 370), "lf_mechanism_paired_latch": (567, 247),
         "lf_mechanism_trail_cache": (760, 322), "lf_props_supplies": (380, 292)}
ONLY = {"lf_mechanism_rune_lock": ["lf_rune_ring1_mountain", "lf_rune_ring2_river", "lf_rune_ring3_leaf", "lf_lock_mechanism"]}


class Lite:
    pass


def load_asset(asset_id):
    bpy.ops.wm.open_mainfile(filepath=paths.source(pk.GROUP, f"{asset_id}.blend"))
    A = Lite()
    A.id = asset_id
    A.pivots, A.actions, A.clips = {}, {}, {}
    for o in bpy.data.objects:
        if o.animation_data and o.animation_data.nla_tracks:
            A.pivots[o.name] = o
            for tr in o.animation_data.nla_tracks:
                for st in tr.strips:
                    act = st.action
                    A.actions.setdefault(tr.name, {})[o.name] = act
                    A.clips[tr.name] = {"frames": int(round(act.frame_range[1])), "markers": {}}
    return A


def main():
    args = [a for a in sys.argv[1:] if a.startswith("lf_")]
    for asset_id in args:
        A = load_asset(asset_id)
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.hide_render = not o.name.endswith("_LOD0")
        for nm in ("socket_keyhole_pivot",):
            if nm in bpy.data.objects:
                for c in bpy.data.objects[nm].children_recursive:
                    c.hide_render = True
        fn, view = CAMS[asset_id]
        cams = json.load(open(os.path.join(paths.QA_COMPARE, "props_cams", fn)))
        x = cams[f"{asset_id}:{view}"]
        W, H = CROPS[asset_id]
        cam = pk.cam_from_params(np.array(x), W, H)
        pk.studio(engine="BLENDER_EEVEE", samples=16)
        bpy.context.scene.render.film_transparent = False
        bpy.context.scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.52, 0.46, 1)
        co = pk.blender_camera(cam)
        for clip in A.clips:
            if asset_id in ONLY and clip not in ONLY[asset_id]:
                continue
            out = paths.video(asset_id, f"{clip}.mp4")
            pk.render_clip_frames(A, clip, out, cam_obj=co, res=(int(W * 2) // 2 * 2, int(H * 2) // 2 * 2),
                                  engine="BLENDER_EEVEE", samples=16, hold=8)
            render.contact_sheet_from_video(out, out[:-4] + "_sheet.png", frames=8, width=1600)
            print("[clip]", out)


if __name__ == "__main__":
    main()
