"""QA renders: reference compares (IoU), preview views, side-by-sides, contact sheets."""
import os

import bpy
import numpy as np

from frlib import core, render

PREVIEW_COL = {"skin": (0.80, 0.62, 0.52), "lip": (0.7, 0.42, 0.40), "eye": (0.9, 0.9, 0.88),
               "hair": (0.20, 0.14, 0.10), "beard": (0.22, 0.15, 0.10), "shirt": (0.55, 0.25, 0.18),
               "apron": (0.82, 0.77, 0.68), "canvas": (0.70, 0.62, 0.50), "trousers": (0.33, 0.26, 0.20),
               "boot": (0.30, 0.20, 0.13), "sole": (0.12, 0.10, 0.08), "armband": (0.20, 0.42, 0.25),
               "body": (0.6, 0.6, 0.6)}


def piece_object(p, name=None, col=None):
    V = p.verts
    obj = core.mesh_object(name or p.name, V, p.faces, smooth=True)
    return obj


def preview_scene(pieces, body_cls=None):
    """Objects for preview; body faces coloured by class via per-face material index."""
    objs = []
    mats = {}

    def mat(cls):
        if cls not in mats:
            c = PREVIEW_COL.get(cls, (0.6, 0.6, 0.6))
            mats[cls] = core.material("pv_" + cls, base=(*c, 1.0), rough=0.7)
        return mats[cls]

    for p in pieces:
        obj = piece_object(p)
        if p.name == "body" and body_cls is not None:
            classes = sorted(set(body_cls))
            for c in classes:
                obj.data.materials.append(mat(c))
            idx = np.array([classes.index(c) for c in body_cls], np.int32)
            obj.data.polygons.foreach_set("material_index", idx)
        else:
            core.assign(obj, mat(p.cls))
        objs.append(obj)
    return objs


def render_compares(views, out_dir, prefix, title, engine="BLENDER_WORKBENCH", extra=None):
    sc = bpy.context.scene
    res = {}
    for view in views:
        render.camera_for_view(view)
        sc.render.film_transparent = True
        rgba = render.render_rgba(os.path.join(out_dir, f"_{prefix}_{view.name}_raw.png"))
        m = render.compare(view, rgba, os.path.join(out_dir, f"{prefix}_{view.name}.png"),
                           title=f"{title} {view.name}", extra=extra)
        os.remove(os.path.join(out_dir, f"_{prefix}_{view.name}_raw.png"))
        res[view.name] = m
    return res


def render_views(out_png, target=(0, 0, 0.9), dist=3.6, height=1.0, lens=55, res=(420, 640),
                 yaws=(-35, 35, 145, 90), bg=0.82):
    imgs = []
    import math
    for yw in yaws:
        a = math.radians(yw)
        loc = (target[0] + dist * math.sin(a), target[1] - dist * math.cos(a), height + target[2] * 0.3)
        render.perspective_camera(loc, target, lens=lens, res=res)
        bpy.context.scene.render.film_transparent = True
        im = render.render_rgba()
        rgb = im[..., :3] * im[..., 3:] + bg * (1 - im[..., 3:])
        imgs.append(rgb)
    core.save_rgba(out_png, np.concatenate(imgs, 1))
    return out_png


def workbench(color_type="MATERIAL"):
    render.studio(engine="BLENDER_WORKBENCH")
    sc = bpy.context.scene
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = color_type
    sc.display.shading.show_cavity = False
    return sc
