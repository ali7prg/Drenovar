"""Close-up renders of a built creature for appearance work (Blender 5.3 as a Python module, Cycles on the CPU):
the head from 3/4 front, the front and the side, and a front paw from 3/4, perspective cameras aimed at the
bones, the same studio light as tools/proof.py. One sheet per creature: <id>_closeups.jpg (+ the single PNGs).

  python -I closeup.py <species> <glb> <out dir> [clip:frame] [samples]
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import proof  # noqa: E402

# camera distance (m) to the head / to the paw, per creature (heads 0.4-1.2 m long)
DIST = {"tenerys": (1.55, 1.05), "velkor": (2.1, 1.15), "kamneklyk": (1.9, 1.15), "dragor": (3.2, 1.9)}
SHOTS = [("head 3/4", "head", 38, 8), ("head front", "head", 0, 4), ("head side", "head", 90, 2),
         ("front paw 3/4", "paw", 35, 22)]


def bone_world(arm, names):
    for n in names:
        pb = arm.pose.bones.get(n)
        if pb is not None:
            return np.array(arm.matrix_world @ pb.head)
    raise KeyError(names)


def main():
    import bpy
    from mathutils import Vector
    sid, glb, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pose = sys.argv[4] if len(sys.argv) > 4 else "idle:0"
    samples = int(sys.argv[5]) if len(sys.argv) > 5 else 48
    os.makedirs(out, exist_ok=True)
    sc = proof.scene_setup(samples)
    proof.import_glb(sc, glb)
    clip, fr = pose.split(":")
    proof.set_clip(sc, sid, clip, int(fr))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    head = bone_world(arm, ["Head"])
    nose = bone_world(arm, ["Nose", "Jaw", "Head"])
    # aim between the skull and the snout; the left side of the creature is +Y in Blender (glTF -Z)
    head_target = head * 0.45 + nose * 0.55 + np.array([0, 0, 0.04])
    paw = bone_world(arm, ["Toe_Front_L", "Foot_Front_L", "Hand_Front_L"])
    paw_target = paw + np.array([0.04, 0.0, 0.08])
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x = sc.render.resolution_y = 720
    sc.render.film_transparent = False
    tiles = []
    for title, what, az, el in SHOTS:
        target = head_target if what == "head" else paw_target
        dist = DIST.get(sid, (2.0, 1.2))[0 if what == "head" else 1]
        a, e = math.radians(az), math.radians(el)
        pos = target + dist * np.array([math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)])
        cam.location = Vector(pos.tolist())
        d = Vector((target - pos).tolist())
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        proof.light_rig(sc, cam)
        path = os.path.join(out, f"{sid}_closeup_{what}_{az}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        im = Image.open(path).convert("RGB")
        ImageDraw.Draw(im).text((8, 6), f"{sid} {title}", fill=(20, 20, 20))
        tiles.append(im)
    W = sum(t.size[0] for t in tiles) + 6 * (len(tiles) - 1)
    sheet = Image.new("RGB", (W, tiles[0].size[1]), (255, 255, 255))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.size[0] + 6
    p = os.path.join(out, f"{sid}_closeups.jpg")
    sheet.save(p, quality=88)
    print("CLOSEUPS", p, sheet.size)


if __name__ == "__main__":
    main()
