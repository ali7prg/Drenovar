"""End-to-end build of one human character: model -> textures -> compare -> rig -> clips -> GLB.

Usage (from a build_<asset>.py):  humans_make.make("lf_civilian_miller", tag="iter05")
"""
import json
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector

from frlib import core, paths, render

import humans_anim as A
import humans_build as HBLD
import humans_clips as CL
import humans_pipeline as PL
import humans_qa as Q
import humans_refs as R
import humans_rig as RG
import humans_skel as SK
import humans_tex as T

log = HBLD.log
GROUP_BUDGET = {"civilian": (12000, 6000, 2200), "soldier": (14000, 7000, 2500)}


def compare_dir(asset):
    return paths.ensure(paths.QA_COMPARE, asset)


def face_closeup(ctx, out_png, tag):
    """Render the head front + 3/4 next to the portrait inset (or front panel face)."""
    lm = ctx.lm
    c = lm["origin"] + np.array([0, 0.02, -0.03]) * lm["scale"]
    imgs = []
    for nm, off in (("front", (0, -0.95, 0.0)), ("q", (0.62, -0.72, 0.03))):
        render.perspective_camera(tuple(c + np.array(off)), tuple(c), lens=85, res=(420, 480))
        bpy.context.scene.render.film_transparent = True
        im = render.render_rgba()
        imgs.append(im[..., :3] * im[..., 3:] + 0.85 * (1 - im[..., 3:]))
    p = R.PANELS[ctx.asset]
    labels = ["model front", "model 3/4"]
    if p.get("inset"):
        ref = R.refs.crop(R.sheet(p["sheet"]), p["inset"])
        imgs = [ref] + imgs
        labels = ["reference portrait"] + labels
    v = ctx.views[0]
    # face crop of the full-body front panel too
    u, vv, _ = v.project(lm["origin"][None])
    s = v.ppm * 0.16
    x0, y0 = int(u[0] - s), int(vv[0] - s * 1.0)
    fc = v.image[max(y0, 0):int(vv[0] + s * 1.2), max(x0, 0):int(u[0] + s)]
    imgs = [fc] + imgs
    labels = ["front panel face"] + labels
    render.side_by_side(imgs, labels, out_png, height=420)


def reference_compare(ctx, tag, lod0, extra_objs=()):
    out = compare_dir(ctx.asset)
    render.studio(engine="BLENDER_EEVEE", samples=32)
    m = Q.render_compares(ctx.views, out, tag, f"{ctx.asset} {tag}")
    Q.render_views(os.path.join(out, f"{tag}_views.png"))
    face_closeup(ctx, os.path.join(out, f"{tag}_face.png"), tag)
    return {k: v["iou"] for k, v in m.items()}, {k: v["mean_abs_colour_error"] for k, v in m.items()}


# --------------------------------------------------------------------------- clips

def thigh_flex(M, side):
    hips = M["Hips"][:3, :3]
    d = M[f"{side}LowerLeg"][:3, 3] - M[f"{side}UpperLeg"][:3, 3]
    d = d / np.linalg.norm(d)
    down = -hips[:, 1] if False else -np.array(hips @ np.array([0, 0, 1.0]))
    fwd = hips @ np.array([0, -1.0, 0])
    lat = hips @ np.array([1.0, 0, 0])
    flex = math.degrees(math.atan2(np.dot(d, fwd), np.dot(d, down)))
    abd = math.degrees(math.atan2(np.dot(d, lat) * (1 if side == "Left" else -1), np.dot(d, down)))
    return flex, abd


def bake_clip(rig, name, dur, loop, specs, role, props_fn=None, cloth=True):
    """Solve specs -> frames with secondary cloth/hood/bag dynamics; returns frames list."""
    n = len(specs)
    poses = [CL.solve(rig, sp) for sp in specs]
    if props_fn:
        for i, P in enumerate(poses):
            props_fn(P, i / A.FPS)
    if cloth:
        fl, fr, al, ar, lean, yaw, hy, vel = [], [], [], [], [], [], [], []
        for i, P in enumerate(poses):
            M = rig.S.world(P)
            a, b = thigh_flex(M, "Left")
            c, d = thigh_flex(M, "Right")
            fl.append(a)
            fr.append(c)
            al.append(b)
            ar.append(d)
            up = M["UpperChest"][:3, :3] @ np.array([0, 1.0, 0])
            lean.append(math.degrees(math.atan2(-up[1], up[2])))
            hy.append(M["Hips"][2, 3])
        fl, fr, al, ar, lean, hy = map(np.array, (fl, fr, al, ar, lean, hy))
        spring = A.Spring(k=70.0, d=10.0)
        front = np.maximum(np.maximum(fl, fr), 0) * 0.92 + 2.0
        front2 = np.maximum(np.maximum(fl, fr) - 25.0, 0) * 0.5
        back = np.maximum(np.maximum(-fl, -fr), 0) * 0.85
        bob = np.gradient(np.gradient(hy)) * A.FPS * A.FPS          # vertical accel
        tgt = {
            "SkirtFront1": spring.run(front, loop=loop) + 0.0,
            "SkirtFront2": spring.run(front2 + 0.004 * bob, loop=loop),
            "SkirtBack1": spring.run(back, loop=loop),
            "SkirtBack2": spring.run(back * 0.25 - 0.004 * bob, loop=loop),
            "SkirtLeft": spring.run(np.maximum(al, -2) * 0.8, loop=loop),
            "SkirtRight": spring.run(np.maximum(ar, -2) * 0.8, loop=loop),
            "Cape1": A.Spring(k=40, d=7).run(np.maximum(lean, -5) * 0.85 + 2.0, loop=loop),
            "Cape2": A.Spring(k=30, d=6).run(np.maximum(lean, -5) * 0.15 + 0.003 * bob, loop=loop),
            "Bag": A.Spring(k=35, d=5).run(0.006 * bob + (fl - fr) * 0.05, loop=loop),
        }
        if loop:
            for k in tgt:
                tgt[k] = A.make_loop(tgt[k], blend=4)
        for i, P in enumerate(poses):
            for b in ("SkirtFront1", "SkirtFront2", "SkirtBack1", "SkirtBack2", "Cape1", "Cape2", "Bag"):
                P[b] = ("local", A.rot_xyz(x=float(tgt[b][i])))
            P["SkirtLeft"] = ("local", A.rot_xyz(x=0.0, z=0.0, y=0.0) @ A.axis_angle((1, 0, 0), float(tgt["SkirtLeft"][i])))
            P["SkirtRight"] = ("local", A.axis_angle((1, 0, 0), float(tgt["SkirtRight"][i])))
            P["Hood"] = ("local", A.rot_xyz(x=0.0))
    frames = [rig.S.solve(P) for P in poses]
    if loop:
        frames[-1] = frames[0]
    bake_clip.last_slide = foot_slide(rig, poses, getattr(bake_clip, "speed", 0.0))
    return frames


def foot_slide(rig, poses, speed):
    """Max drift (cm) of the stance-foot contact point vs the ground (which moves backward at
    `speed` in in-place clips), over every stance interval; heel/ball/toe pivots tracked."""
    worst = 0.0
    for S_ in ("Left", "Right"):
        prev = None
        for i, P in enumerate(poses):
            M = rig.S.world(P)
            Mf, Mt = M[f"{S_}Foot"], M[f"{S_}Toes"]
            heel = (Mf @ np.array([0.0, -0.07, -0.075, 1.0]))[:3]
            ball = Mt[:3, 3]
            tip = (Mt @ np.array([0.0, rig.S.length[f"{S_}Toes"], 0.0, 1.0]))[:3]
            pts = {"heel": heel, "ball": ball, "tip": tip}
            k = min(pts, key=lambda q: pts[q][2])
            p = pts[k]
            if p[2] > 0.035:
                prev = None
                continue
            t = i / A.FPS
            if prev is None or prev[0] != k:
                prev = (k, p.copy(), t)
                continue
            exp = prev[1] + np.array([0.0, speed * (t - prev[2]), 0.0])
            worst = max(worst, float(np.linalg.norm((p - exp)[:2])))
    return round(worst * 100.0, 2)


def clip_specs(rig, role, name, dur):
    """Specs for a clip id; returns (specs, extra dict with groundSpeed/stride/markers/root)."""
    n = int(round(dur * A.FPS)) + 1
    ts = [i / A.FPS for i in range(n)]
    extra = {}
    if name in ("lf_civilian_follow", "lf_civilian_follow_tired"):
        tired = name.endswith("tired")
        G = A.Gait(rig, dur, 0.85 if tired else 1.20, duty=0.64 if tired else 0.62, lift=0.075 if tired else 0.095,
                   heel_ang=9.0 if tired else 14.0, toe_ang=18.0 if tired else 26.0)
        specs = CL.locomotion_specs(rig, G, CL.STYLES["civ_tired" if tired else "civ_walk"], n, dur)
        extra = dict(groundSpeed_mps=G.v, strideLength_m=round(G.stride, 3),
                     markers={"contact_l": 0.0, "contact_r": round(dur / 2, 3)})
        return specs, extra
    if name.startswith("lf_soldier"):
        specs, G = CL.soldier_clip_specs(rig, role, name, dur)
        if isinstance(G, A.Gait):
            extra = dict(groundSpeed_mps=G.v, strideLength_m=round(G.stride, 3),
                         markers={"contact_l": 0.0, "contact_r": round(dur / 2, 3)})
        if name in CL.MARKERS:
            extra["markers"] = dict(CL.MARKERS[name])
        return specs, extra
    fn = {"lf_civilian_cage_sit": CL.clip_cage_sit, "lf_civilian_cage_stand": CL.clip_cage_stand,
          "lf_civilian_cage_wait": CL.clip_cage_wait, "lf_civilian_react": CL.clip_react,
          "lf_civilian_stand_up": CL.clip_stand_up, "lf_civilian_look_back": CL.clip_look_back,
          "lf_civilian_thank": CL.clip_thank, "lf_civilian_wait": CL.clip_wait}.get(name)
    if fn is not None:
        return [fn(rig, t, dur) for t in ts], extra
    if name == "lf_civilian_exit":
        specs, pl = CL.clip_exit_specs(rig, dur)
    elif name == "lf_civilian_arrive":
        specs, pl = CL.clip_arrive_specs(rig, dur)
    else:
        raise KeyError(name)
    dist = -float(pl.root[-1])
    extra = dict(rootDistance_m=round(dist, 3), groundSpeed_mps=round(dist / dur, 3),
                 rootPath_m=[round(-float(v), 4) for v in pl.root[::3]])
    return specs, extra


# --------------------------------------------------------------------------- main

def make(asset, tag="iter", clips=True, export=True, compare=True, voxel=0.0032, tex_size=2048, only_clips=None,
         out_glb=None):
    t0 = time.time()
    ctx = HBLD.assemble(asset, voxel=voxel)
    spec = ctx.spec
    group = spec.GROUP
    role = getattr(spec, "ROLE", "civilian")
    budgets = GROUP_BUDGET[group]
    core.reset()
    budget = dict(getattr(spec, "BUDGET", {"head": 2500}))
    budget["total"] = budgets[0]
    lod0, classes = PL.build_lod0(ctx, budget)
    hi = [PL.obj_from_piece(p, "hi_" + p.name) for p in ctx.pieces if p.meta.get("sdf") and p.name in ("body", "head")]
    tex = PL.texture_lod0(ctx, lod0, classes, size=tex_size, hi_objs=hi)
    tp = PL.save_textures(asset, tex)
    mats, imgs = PL.make_materials(asset, lod0, classes, spec, tp, tex["factors"])
    main, optional = split_optional(ctx, lod0)
    aux = split_optional.aux
    for o in aux:
        o.hide_render = True
    res = {"asset": asset, "tag": tag}
    if compare:
        for o in optional:
            o.hide_render = (not o.get("default_on", False)) or o.get("no_compare", False)
        iou, cerr = reference_compare(ctx, tag, main)
        res.update(iou=iou, colour_error=cerr)
        log(asset, "IOU", iou, "colour", cerr)
        for o in optional:
            o.hide_render = False
    if not export:
        return res
    # ---------------- rig
    if aux:
        for o in aux:
            o.hide_render = False
        main = core.join([main] + aux, asset + "_LOD0")
    prop_to_hand(ctx, main)
    arm = SK.create_armature(asset + "_rig", ctx.B, ctx.J)
    rest_old = {b.name: np.array(b.matrix_local) for b in arm.data.bones}
    W = RG.compute_weights(ctx, main, main["pieces"].split(","))
    RG.bind(main, arm, W)
    body_ref = RG.compute_weights.last_body
    for o in optional:
        Wo = RG.compute_weights(ctx, o, o["pieces"].split(","), body_ref=body_ref)
        RG.bind(o, arm, Wo)
    RG.rerest_canonical(arm, [main] + optional, ctx.B)
    main.name = asset + "_LOD0"
    lods = [main]
    tri0 = core.tri_count(main)
    for li, keep in ((1, SK.LOD1_KEEP), (2, SK.LOD2_KEEP)):
        target = budgets[li] * 0.96
        r = target / max(tri0, 1)
        lod, Wl = RG.make_lod(main, f"{asset}_LOD{li}", r * 0.95, r * 1.05, keep, main["pieces"].split(","))
        RG.bind(lod, arm, Wl)
        lods.append(lod)
    opt_lods = []
    for o in optional:
        nm = o.name
        o.name = nm + "_LOD0"
        opt_lods.append(o)
        for li, keep in ((1, SK.LOD1_KEEP), (2, SK.LOD2_KEEP)):
            r = (0.55, 0.25)[li - 1]
            lod, Wl = RG.make_lod(o, f"{nm}_LOD{li}", r, r, keep, o["pieces"].split(","))
            RG.bind(lod, arm, Wl)
            opt_lods.append(lod)
    # ---------------- clips
    clip_meta = {}
    if clips:
        solver = A.Solver(arm)
        rig = A.Rig(solver)
        clist = CL.CIVILIAN if group == "civilian" else CL.SOLDIER
        props_fn = getattr(spec, "props_pose", None)
        for name, dur, loop in clist:
            if only_clips and name not in only_clips:
                continue
            tc = time.time()
            specs, extra = clip_specs(rig, role, name, dur)
            pf = (lambda P, t, nm=name: props_fn(rig, P, t, nm)) if props_fn else None
            bake_clip.speed = float(extra.get("groundSpeed_mps", 0.0)) if loop else 0.0
            pf = carry_override(ctx, rig, rest_old, name) or pf
            frames = bake_clip(rig, name, dur, loop, specs, role, props_fn=pf)
            act = write_action(arm, name, frames, loop)
            clip_meta[name] = dict(seconds=dur, loop=loop, frames=len(frames), **extra)
            if loop or name.startswith("lf_soldier_") or name in ("lf_civilian_react", "lf_civilian_thank",
                                                                   "lf_civilian_look_back"):
                clip_meta[name]["footSlide_cm"] = bake_clip.last_slide
            log(asset, "clip", name, len(frames), "%.1fs" % (time.time() - tc))
        arm.animation_data.action = None
        RG_rest(arm)
    # ---------------- export
    out = export_all(asset, ctx, arm, lods, opt_lods, mats, tex, tp, clip_meta, classes, group, out_glb=out_glb)
    res.update(out)
    res["build_seconds"] = round(time.time() - t0, 1)
    log(asset, "done", json.dumps({k: v for k, v in res.items() if k != "clips"})[:400])
    return res


def carry_override(ctx, rig, rest_old, clip):
    """Per-frame override that keeps a carried prop on its carry bone (scabbard on the hips,
    bow on the back) in clips where it is not held."""
    props = [p.meta["prop"] for p in ctx.pieces if p.meta.get("prop")]
    props = [pr for pr in props if clip not in pr["held"]]
    if not props:
        return None

    def fn(P, t):
        M = rig.S.world(P)
        for pr in props:
            b, cb = pr["bone"], pr["carry_bone"]
            S_local = np.linalg.inv(rest_old[b]) @ pr["hand_place"]
            Mc = M[cb] @ np.linalg.inv(rig.S.rest[cb]) @ pr["carry_place"]
            Mb = Mc @ np.linalg.inv(S_local)
            P[b] = Mb[:3, :3] / np.linalg.norm(Mb[:3, :3], axis=0, keepdims=True)
            P[b + "_pos"] = Mb[:3, 3]
    return fn


def RG_rest(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()


def _extract(lod0, sel, name):
    import bmesh
    o = lod0.copy()
    o.data = lod0.data.copy()
    core.link(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f, k in zip(bm.faces, sel) if not k], context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    o.name = name
    o["pieces"] = lod0["pieces"]
    o["classes"] = lod0["classes"]
    return o


def split_optional(ctx, lod0):
    """Separate variant parts (optional) and compare-hidden parts (weapons) into own objects."""
    import bmesh
    names = lod0["pieces"].split(",")
    fpiece = PL.get_face_attr(lod0, "piece")
    keep_main = np.ones(len(fpiece), bool)
    opt, aux = [], []
    for p in ctx.pieces:
        if not (p.meta.get("optional") or p.meta.get("no_compare")) or p.name not in names:
            continue
        sel = fpiece == names.index(p.name)
        if not sel.any():
            continue
        if p.meta.get("optional"):
            o = _extract(lod0, sel, f"{ctx.asset}_opt_{p.meta['optional']}")
            o["default_on"] = bool(p.meta.get("default_on", True))
            o["no_compare"] = bool(p.meta.get("no_compare", False))
            opt.append(o)
        else:
            o = _extract(lod0, sel, f"aux_{p.name}")
            o["prop"] = p.name
            aux.append(o)
        keep_main &= ~sel
    bm = bmesh.new()
    bm.from_mesh(lod0.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f, k in zip(bm.faces, keep_main) if not k], context="FACES")
    bm.to_mesh(lod0.data)
    bm.free()
    split_optional.aux = aux
    return lod0, opt


def prop_to_hand(ctx, obj):
    """Move carried props (sword in scabbard, slung bow) from their carry placement (as on the
    sheet) to their hand placement before rigid binding to the Prop bone."""
    for p in ctx.pieces:
        pr = p.meta.get("prop")
        if not pr:
            continue
        names = obj["pieces"].split(",")
        if p.name not in names:
            continue
        fpiece = PL.get_face_attr(obj, "piece")
        me = obj.data
        vs = set()
        for f, pi in zip(me.polygons, fpiece):
            if pi == names.index(p.name):
                vs.update(f.vertices)
        idx = np.array(sorted(vs))
        X = np.linalg.inv(pr["carry_place"])
        Mv = pr["hand_place"] @ X
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        co[idx] = co[idx] @ Mv[:3, :3].T + Mv[:3, 3]
        me.vertices.foreach_set("co", co.ravel())
        me.update()


def write_action(arm, name, frames, loop):
    from frlib import rig as frig
    keep = ("Hips", "LeftProp", "RightProp")
    act = frig.write_action(arm, name, frames, loop=loop, keep_location=keep)
    return act


def export_all(asset, ctx, arm, lods, opt_lods, mats, tex, tp, clip_meta, classes, group, out_glb=None):
    glb = out_glb or paths.runtime("humans", f"{asset}.glb")
    arm.name = asset + "_rig"
    objs = [arm] + lods + opt_lods
    for o in opt_lods:
        o.hide_render = False
    core.export_glb(glb, objs)
    tris = {f"LOD{i}": core.tri_count(l) for i, l in enumerate(lods)}
    used = {}
    for i, l in enumerate(lods):
        W = RG.read_weights(l)
        used[f"LOD{i}"] = int((W.max(0) > 0).sum())
    lo, hi = core.bounds(lods[:1])
    sockets = {}
    for b in ("LeftHand", "RightHand", "LeftProp", "RightProp", "Head", "Hips"):
        bb = arm.data.bones[b]
        h = bb.head_local
        sockets[b] = [round(h.x, 4), round(h.z, 4), round(-h.y, 4)]   # glTF (+Y up, +Z forward)
    meta = {
        "id": asset, "rig": "human_shared", "group": group,
        "tris": tris, "bones": len(arm.data.bones), "deformBonesUsedByLOD": used,
        "materials": [m.name for m in mats],
        "materialTint": {m.name.split("_")[-1]: [round(x, 4) for x in m.get("tint_factor", [1, 1, 1])] for m in mats},
        "materialMedian": {k: [round(x, 4) for x in v] for k, v in tex.get("medians", {}).items()},
        "textures": {"albedo": 1024, "orm": 1024, "normal": 1024},
        "bounds_m": {"min": [round(float(x), 3) for x in lo], "max": [round(float(x), 3) for x in hi]},
        "clips": clip_meta,
        "sockets": sockets,
        "seat_height_m": CL.SEAT_H,
        "optionalParts": sorted({o.name.split("_opt_")[1].rsplit("_LOD", 1)[0] for o in opt_lods}),
        "notes": "Clips in place; root path for exit/arrive in clips[*].rootPath_m (metres along +Z forward). "
                 "Seated clips assume a 0.45 m seat behind the root (cage bench/log). Tintable materials carry "
                 "colour in baseColorFactor (albedo atlas normalised) for captive variants.",
    }
    if out_glb:
        core.write_json(out_glb.replace(".glb", ".meta.json"), meta)
        return {"glb": glb, "tris": tris, "bones_used": used}
    core.write_json(paths.runtime("humans", f"{asset}.meta.json"), meta)
    blend = paths.source("humans", f"{asset}.blend")
    core.save_blend(blend)
    return {"glb": glb, "tris": tris, "bones_used": used, "blend": blend}
