"""Adds the socket-insertion clip and an emissive glow pulse to the artifact GLBs (geometry/textures of the
families are kept): for every variant node <id>_vN a child glow shell <id>_vN_glow (LOD0 mesh, normals pushed out
1.5 mm, emissive material <id>_glow with KHR_materials_emissive_strength) and NLA clips:
  lf_artifact_insert (1.2 s): variant slides 0.22 m along +Z (glTF, out of the socket) into place, seats with a
      small press, then the glow shell pulses (scale 1.0 -> 1.10 -> 1.0); marker seated 0.75 s.
  lf_artifact_glow (2.0 s, loop): gentle glow pulse for the 'found / hovering' state.
python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/v2/artifact_glow.py
"""
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pv2  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core  # noqa: E402

FAM = {"stone_rune": (0.35, 0.95, 0.55), "bronze_seal": (1.0, 0.72, 0.30), "amber_crystal": (1.0, 0.62, 0.15),
       "bone_key": (1.0, 0.92, 0.70)}
STRENGTH = 3.0


def run(fam):
    aid = f"lf_artifact_{fam}"
    src = os.path.join(pv2.RT, f"{aid}.glb")
    bak = os.path.join(pv2.SRC, f"{aid}_pre_v2.glb")
    if not os.path.exists(bak):
        shutil.copy(src, bak)
    core.reset()
    bpy.ops.import_scene.gltf(filepath=bak)
    objs = list(bpy.context.scene.objects)
    for o in objs:
        if o.animation_data:
            o.animation_data_clear()
    col = FAM[fam]
    gm = core.material(f"{aid}_glow", base=(*col, 1.0), rough=0.4, emission=(*col, 1.0), emission_strength=STRENGTH)
    gm.blend_method = "BLEND" if hasattr(gm, "blend_method") else None
    variants = [o for o in objs if o.type == "EMPTY" and o.name.startswith(f"{aid}_v") and "_LOD" not in o.name]
    if not variants:   # variants exported as meshes without an empty parent
        variants = []
    glows = {}
    for v in variants:
        lod0 = [c for c in v.children if c.type == "MESH" and c.name.endswith("_LOD0")]
        if not lod0:
            continue
        m = lod0[0]
        me = m.data.copy()
        # push vertices out along normals (thin halo shell)
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get("co", co)
        nr = np.empty(n * 3)
        me.vertices.foreach_get("normal", nr)
        co = co.reshape(-1, 3) + nr.reshape(-1, 3) * 0.0015
        me.vertices.foreach_set("co", co.ravel())
        me.materials.clear()
        me.materials.append(gm)
        g = bpy.data.objects.new(f"{v.name}_glow", me)
        core.link(g)
        g.parent = v
        g.matrix_parent_inverse = m.matrix_parent_inverse.copy()
        g.matrix_basis = m.matrix_basis.copy()
        ge = bpy.data.objects.new(f"{v.name}_glow_pivot", None)
        core.link(ge)
        ge.parent = v
        ge.location = (0, 0, 0)
        g.parent = ge
        glows[v.name] = ge
    fps = 30
    clips = {}

    def key_clip(name, seconds, tracks, markers=None, loop=False):
        frames = int(round(seconds * fps))
        clips[name] = {"seconds": frames / fps, "loop": loop, "frames": frames, "markers": markers or {}}
        for obj, fn in tracks:
            rl = np.array(obj.location[:]) if "rest_loc" not in obj else np.array(obj["rest_loc"])
            obj["rest_loc"] = list(rl)
            obj.rotation_mode = "XYZ"
            if obj.animation_data is None:
                obj.animation_data_create()
            act = bpy.data.actions.new(f"{name}|{obj.name}")
            obj.animation_data.action = act
            for f in range(frames + 1):
                val = fn(f / fps)
                obj.location = tuple(rl + np.asarray(val.get("loc", (0, 0, 0)), float))
                obj.scale = tuple(val.get("scale", (1, 1, 1)))
                obj.keyframe_insert("location", frame=f)
                obj.keyframe_insert("scale", frame=f)
            obj.animation_data.action = None
            tr = obj.animation_data.nla_tracks.new()
            tr.name = name
            st = tr.strips.new(name, 0, act)
            st.extrapolation = "NOTHING"
            obj.location = tuple(rl)
            obj.scale = (1, 1, 1)

    def insert(t):
        # Blender -Y = glTF +Z (out of the socket toward the viewer)
        if t < 0.6:
            d = 0.22 * (1 - pv2.ease_io(t / 0.6))
        else:
            d = -0.006 * math.sin(math.pi * min(1.0, (t - 0.6) / 0.2))
        return {"loc": (0, -d, 0)}

    def pulse(t, t0, dur, amp):
        x = (t - t0) / dur
        s = 1.0 + amp * math.sin(math.pi * min(max(x, 0.0), 1.0))
        return {"scale": (s, s, s)}

    tr = []
    for v in variants:
        tr.append((v, insert))
        if v.name in glows:
            tr.append((glows[v.name], lambda t: pulse(t, 0.7, 0.5, 0.10)))
    key_clip("lf_artifact_insert", 1.2, tr, markers={"seated": 0.75, "glow_peak": 0.95})
    tr2 = [(glows[k], (lambda t: pulse(t, 0.0, 2.0, 0.06))) for k in glows]
    key_clip("lf_artifact_glow", 2.0, tr2, loop=True)
    # export (rest pose), then patch node rest TRS for the animated variant nodes / glow pivots
    for o in bpy.context.scene.objects:
        if o.animation_data:
            o.animation_data.action = None
            for t in o.animation_data.nla_tracks:
                t.mute = False
    out = os.path.join(pv2.RT, f"{aid}.glb")
    bpy.context.preferences.edit.use_negative_frames = True
    bpy.context.scene.frame_set(-10)
    core.export_glb(out, list(bpy.context.scene.objects), animations=True,
                    extra={"export_animation_mode": "NLA_TRACKS", "export_optimize_animation_size": False,
                           "export_def_bones": False, "export_skins": False, "export_current_frame": True,
                           "export_optimize_animation_keep_anim_object": True, "export_image_format": "AUTO"})
    import glbx
    js, bin_ = glbx.read_glb(out)
    rest = {o.name: np.array(o.get("rest_loc", list(o.location[:])), float) for o in bpy.context.scene.objects
            if o.get("rest_loc") is not None}
    for node in js["nodes"]:
        nm = node.get("name")
        if nm in rest:
            x, y, z = rest[nm]
            node["translation"] = [float(x), float(z), float(-y)]
            node.pop("scale", None)
    glbx.write_glb(out, js, bin_)
    # meta
    mp = os.path.join(pv2.RT, f"{aid}.meta.json")
    meta = json.load(open(mp))
    meta["clips"] = clips
    meta["glow"] = {"nodes": sorted(f"{k}_glow" for k in glows), "pivots": sorted(f"{k}_glow_pivot" for k in glows),
                    "material": f"{aid}_glow", "emissive_rgb": list(col), "emissive_strength": STRENGTH,
                    "parameter": "StandardMaterial3D.emission_energy_multiplier (glTF KHR_materials_emissive_strength); "
                                 "set 0 to switch the glow off, ~3 when seated, pulse via lf_artifact_glow",
                    "note": "the painted-light override (paintedLightMix) must skip materials ending in _glow"}
    meta["insert"] = {"clip": "lf_artifact_insert", "axis_gltf": [0, 0, 1], "travel_m": 0.22,
                      "parent_to": "cage key_slot node (identity transform), variant node per site"}
    nodes, anims = pv2.glb_nodes(out)
    meta["glb_nodes"] = nodes
    meta["glb_animations"] = anims
    core.write_json(mp, meta)
    bad, _ = pv2.godot_import_check(out)
    print(f"[{aid}] variants {len(variants)} glows {len(glows)} anims {anims} godot errors/warnings {len(bad)}", flush=True)
    for ln in bad[:6]:
        print("   GODOT>", ln, flush=True)


if __name__ == "__main__":
    for f in (sys.argv[1:] or list(FAM)):
        run(f)
