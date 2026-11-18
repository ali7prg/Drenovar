"""Assembly of one human character from its spec: skeleton, body field (+hair), garments,
accessories, beard -> Pieces in the drawing pose.  Texturing/rigging/export live in other modules."""
import importlib
import time

import numpy as np

from frlib import sdf as fsdf

import humans_body as HB
import humans_geo as G
import humans_refs as R
import humans_sdf as H
import humans_skel as SK

TORSO_NAMES = ("torso", "thigh", "shin", "boot", "sole", "shaft", "neck", "skull", "own", "drape")


def log(*a):
    print("[humans]", *a, flush=True)


def load_spec(asset):
    return importlib.import_module("spec_" + asset)


def assemble(asset, voxel=0.0035, with_garments=True):
    t0 = time.time()
    spec = load_spec(asset)
    L = spec.L
    J = SK.joints_from_landmarks(L)
    B, fingers = SK.build_bones(J, L, getattr(spec, "BONE_GARMENTS", None))
    vf = R.make_view(asset, "front")
    vb = R.make_view(asset, "back")
    views = [vf, vb]
    hull_fn = G.hull_xz_fn(views)
    parts, subs, lm = HB.generic_parts(J, L, fingers, spec.FACE, neck_r=getattr(spec, "NECK_R", (0.060, 0.052)))
    parts += spec.body_parts(J, L)
    ctx = G.Ctx(asset=asset, spec=spec, L=L, J=J, B=B, fingers=fingers, views=views, hull_fn=hull_fn, lm=lm,
                center=np.array(getattr(spec, "CENTER", (0.0, 0.012))), parts=parts)
    # head-only fine field for hair/beard/headwear shells
    hp = [p for p in parts if getattr(p, "bone", None) in ("Head", "Jaw") and getattr(p, "cls", None) in
          ("skin", "lip", "eye", None)]
    O = lm["origin"]
    hlo = O + np.array([-0.15, -0.10, -0.20])
    hhi = O + np.array([0.15, 0.25, 0.16])
    Fh = fsdf.Field(hlo, hhi, 0.0025)
    for p in hp:
        Fh.apply(p, op=getattr(p, "op", "union"), k=p.k)
    ctx.head_fn = G.FieldFn(Fh)
    extras = spec.head_extras(ctx) if hasattr(spec, "head_extras") else []
    parts_all = parts + extras
    ctx.parts = parts_all
    lo, hi = HB.field_bounds(L)
    F = HB.build_field(parts_all, subs, lo, hi, voxel, views=views, hull_k=getattr(spec, "HULL_K", 0.010))
    ctx.body_field = F
    ctx.body_fn = G.FieldFn(F)
    Ft = G.parts_field(parts_all, lo, hi, 0.006, names=TORSO_NAMES + tuple(getattr(spec, "DRAPE_EXTRA", ())))
    ctx.torso_fn = G.FieldFn(Ft)
    log(asset, "fields %.1fs" % (time.time() - t0))
    v, f = F.mesh()
    body = G.Piece("body", v, f.tolist(), [[(0, 0)] * 3 for _ in range(len(f))], "body", {"type": "body"},
                   meta={"sdf": True})
    pieces = [body]
    if with_garments and hasattr(spec, "garments"):
        pieces += spec.garments(ctx)
    if with_garments and hasattr(spec, "beard"):
        b = spec.beard(ctx)
        if b is not None:
            b.meta["optional"] = "beard"
            pieces.append(b)
    if with_garments and hasattr(spec, "optional_parts"):
        for p in spec.optional_parts(ctx):
            pieces.append(p)
    ctx.pieces = pieces
    log(asset, "assembled %d pieces, body %d tris, %.1fs" % (len(pieces), len(f), time.time() - t0))
    return ctx
