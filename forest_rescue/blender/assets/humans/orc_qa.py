"""Blender QA renders for lf_orc_warden: turnarounds (painted look = the game's albedo x mix(1, lambert,
paintedLightMix) model, and clay), face close-ups, staff / hand close-up, pose sheets."""
import math

import bpy
import numpy as np

import hv2_blender as HBL
import spec_lf_orc_warden as SP
from frlib import core, paths

BG = np.array([0.80, 0.78, 0.74])


def qa_path(name):
    return paths.compare(SP.ID, name)


def tile(loc, target, ortho, res, bg=BG):
    HBL.look_at_cam(loc, target, ortho_scale=ortho, res=res)
    rgba = HBL.render_rgba()
    return np.clip(rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4]), 0, 1)


def labelled(img, text):
    return HBL._label((np.clip(img, 0, 1) * 255).astype(np.uint8), text)


def sheet(tiles, labels, out_png, title=None):
    row = np.concatenate([labelled(t, l) for t, l in zip(tiles, labels)], 1)
    if title:
        top = HBL._label(np.full((24, row.shape[1], 3), 28, np.uint8), title)
        row = np.concatenate([top, row], 0)
    core.save_rgba(out_png, row / 255.0)
    return out_png


VIEWS = ((0, "front"), (35, "3/4 left"), (90, "side (left)"), (180, "back"), (-35, "3/4 right"))


def turnaround(out_png, title, zc=1.13, ortho=2.62, res=(560, 1040), views=VIEWS, samples=10):
    HBL.qa_scene(samples=samples)
    tiles, labels = [], []
    for yaw, lab in views:
        a = math.radians(yaw)
        tiles.append(tile((math.sin(a) * 8.0, -math.cos(a) * 8.0, zc + 0.55), (0, 0, zc), ortho, res))
        labels.append(lab)
    return sheet(tiles, labels, out_png, title)


def face(out_png, title, head_c, samples=16):
    HBL.qa_scene(samples=samples)
    tiles, labels = [], []
    for yaw, lab in ((0, "front"), (-35, "3/4 right"), (-90, "profile right"), (40, "3/4 left, low")):
        a = math.radians(yaw)
        dz = -0.35 if lab.endswith("low") else 0.10
        loc = (head_c[0] + math.sin(a) * 3.0, head_c[1] - math.cos(a) * 3.0, head_c[2] + dz)
        tiles.append(tile(loc, tuple(head_c), 0.46, (520, 560)))
        labels.append(lab)
    return sheet(tiles, labels, out_png, title)


def detail(out_png, title, center, ortho=0.55, views=((0, "front"), (-60, "3/4 right"), (60, "3/4 left")),
           res=(520, 560), up=0.25, samples=12):
    HBL.qa_scene(samples=samples)
    tiles, labels = [], []
    for yaw, lab in views:
        a = math.radians(yaw)
        loc = (center[0] + math.sin(a) * 3.0, center[1] - math.cos(a) * 3.0, center[2] + up)
        tiles.append(tile(loc, tuple(center), ortho, res))
        labels.append(lab)
    return sheet(tiles, labels, out_png, title)


def game_view(out_png, title, target=(0, 0, 1.0), ortho=3.4, res=(900, 900), samples=12):
    """Game camera direction (offset (75, 83, 75) in Godot = Blender (75, -75, 83)): yaw 45, pitch ~38."""
    HBL.qa_scene(samples=samples)
    off = np.array([75.0, -75.0, 83.0])
    off = off / np.linalg.norm(off) * 20.0
    t = np.array(target, float)
    img = tile(tuple(t + off), tuple(t), ortho, res)
    core.save_rgba(out_png, labelled(img, title) / 255.0)
    return out_png


def with_material(objs, mat, fn):
    """Temporarily put `mat` in every slot (in place: Mesh.materials.clear() would reset material indices)."""
    saved = {o.name: list(o.data.materials) for o in objs}
    for o in objs:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = mat
    try:
        return fn()
    finally:
        for o in objs:
            for i, m in enumerate(saved[o.name]):
                o.data.materials[i] = m
