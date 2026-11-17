"""Stage 2: PBR maps from the baked geometry.

For every texel the rasteriser gives the rest-pose position, smooth normal and
MikkTSpace tangent frame of the exported low poly. Species shading functions
turn those (plus per-texel material weights from the sculpt) into BaseColor,
roughness, metallic, emissive, a detail height field and level masks. The
Cycles tangent-space normal (sculpt -> low poly) is combined with the detail
normal by reoriented normal mapping; AO = Cycles AO x detail cavity.

Outputs (per LOD, per material atlas), all PNG:
  <mat>_basecolor.png  sRGB          <mat>_normal.png  linear, OpenGL (+Y) convention
  <mat>_orm.png        R=AO G=rough B=metal (linear)   <mat>_emissive.png sRGB
  <mat>_variant.png    RGBA level masks (Godot shader; baked into per-level web files)
"""
import os
import time

import numpy as np
from PIL import Image

import raster


def srgb_to_linear(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hexcol(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def prim_axis(p, P):
    """Direction a primitive's surface detail flows along (cone/capsule axis, ellipsoid major axis)."""
    if p.kind in ("cone", "capsule"):
        ax = p.p["b"] - p.p["a"]
    elif p.kind in ("ellipsoid", "box") and "R" in p.p:
        r = p.p.get("r", p.p.get("h"))
        ax = p.p["R"][:, int(np.argmax(r))]
    else:
        return None
    ax = np.asarray(ax, np.float32)
    return np.broadcast_to(ax / max(np.linalg.norm(ax), 1e-9), P.shape)


def material_weights(sp, group, mesh, tau=0.025):
    """Per-vertex weights of every surface class from the sculpt primitives that own the vertex,
    plus a per-vertex flow direction (owning primitives' axes, species default where none)."""
    sk, parts = sp.build_cached()
    classes = sp.CLASSES[group]
    W = np.zeros((len(mesh["pos"]), len(classes)), np.float32)
    FL = np.zeros((len(mesh["pos"]), 3), np.float32)
    RAD = np.zeros(len(mesh["pos"]), np.float32)
    for k, part in enumerate(parts):
        sel = np.nonzero(mesh["part"] == part["index"])[0]
        if len(sel) == 0:
            continue
        P = mesh["pos"][sel]
        _d, D = part["part"].eval(P, keep=True, displace=False)
        prims = part["part"].prims
        valid = np.array([not p.neg for p in prims])
        D = np.where(valid[None, :], D, 1e3)
        dmin = D.min(1, keepdims=True)
        infl = np.exp(-(D - dmin) / tau)
        default = sp.default_flow(P, part["name"])
        flow = np.zeros_like(P)
        rad = np.zeros(len(P), np.float32)
        tot = np.zeros(len(P), np.float32)
        for j, p in enumerate(prims):
            if p.neg:
                continue
            c = sp.CLASS_OF.get(p.mat, p.mat)
            if c not in classes:
                c = classes[0]
            W[sel, classes.index(c)] += infl[:, j]
            ax = prim_axis(p, P) if p.name.startswith(sp.AXIS_PRIMS) else None
            if ax is None:
                ax = default
            elif p.kind in ("cone", "capsule"):
                # orient along the default flow so neighbouring cones agree
                ax = np.where(np.sum(ax * default, 1, keepdims=True) < 0, -ax, ax)
            flow += ax * infl[:, j:j + 1]
            if p.kind == "cone":
                ba = p.p["b"] - p.p["a"]
                h = np.clip(((P - p.p["a"]) @ ba) / float(ba @ ba), 0, 1)
                rad += (p.p["ra"] + (p.p["rb"] - p.p["ra"]) * h) * infl[:, j]
            else:
                rad += 0.2 * infl[:, j]
            tot += infl[:, j]
        FL[sel] = flow / np.maximum(np.linalg.norm(flow, axis=1, keepdims=True), 1e-9)
        RAD[sel] = rad / np.maximum(tot, 1e-9)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    return W, FL, RAD


def rnm(base, detail):
    """Reoriented normal mapping of two tangent-space normals (-1..1)."""
    t = base + np.array([0, 0, 1], np.float32)
    u = detail * np.array([-1, -1, 1], np.float32)
    r = t * (np.sum(t * u, -1, keepdims=True) / t[..., 2:3]) - u
    return r / np.maximum(np.linalg.norm(r, axis=-1, keepdims=True), 1e-9)


class Ctx:
    """Everything a shading function needs, flattened to the covered texels."""

    def __init__(self, mesh, W, size, lod, flow=None, rad=None):
        self.size, self.lod = size, lod
        idx = mesh["idx"]
        self.tri, bary = raster.rasterize(mesh["uv"], idx, size)
        self.mask = self.tri >= 0
        m = self.mask
        self.P = raster.interpolate(mesh["pos"], idx, self.tri, bary)[m]
        N = raster.interpolate(mesh["nrm"], idx, self.tri, bary)[m]
        self.N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        T4 = raster.interpolate(mesh["tan"], idx, self.tri, bary)[m]
        T = T4[:, :3] - np.sum(T4[:, :3] * self.N, 1, keepdims=True) * self.N
        self.T = T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        sign = np.where(T4[:, 3] < 0, -1.0, 1.0).astype(np.float32)
        self.B = np.cross(self.N, self.T) * sign[:, None]
        self.W = raster.interpolate(W, idx, self.tri, bary)[m]
        if flow is not None:
            fl = raster.interpolate(flow, idx, self.tri, bary)[m]
            fl = fl - np.sum(fl * self.N, 1, keepdims=True) * self.N
            self.flow = fl / np.maximum(np.linalg.norm(fl, axis=1, keepdims=True), 1e-9)
        if rad is not None:
            self.rad = raster.interpolate(rad[:, None], idx, self.tri, bary)[m][:, 0]
        part = mesh["part"].astype(np.float32)[:, None]
        self.part = np.rint(raster.interpolate(part, idx, self.tri, bary)[m][:, 0]).astype(np.int32)
        self.n = len(self.P)

    def full(self, flat, fill=0.0):
        shape = (self.size, self.size) + flat.shape[1:]
        out = np.full(shape, fill, np.float32)
        out[self.mask] = flat
        return out


def detail_normal(ctx, height_fn, eps):
    """Tangent-space normal of a 3D height field h(P) sampled along the texel tangent frame."""
    P, T, B = ctx.P, ctx.T, ctx.B
    hu = (height_fn(P + T * eps) - height_fn(P - T * eps)) / (2 * eps)
    hv = (height_fn(P + B * eps) - height_fn(P - B * eps)) / (2 * eps)
    n = np.stack([-hu, -hv, np.ones_like(hu)], 1)
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def save_rgb(path, arr):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(path, optimize=True)


def save_rgba(path, arr):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path, optimize=True)


def resize(arr, size):
    if arr.shape[0] == size:
        return arr
    chans = arr.shape[2] if arr.ndim == 3 else 1
    out = []
    a = arr if arr.ndim == 3 else arr[..., None]
    for c in range(chans):
        im = Image.fromarray(a[..., c].astype(np.float32), "F").resize((size, size), Image.BOX if size < arr.shape[0]
                                                                         else Image.BICUBIC)
        out.append(np.asarray(im))
    out = np.stack(out, -1)
    return out if arr.ndim == 3 else out[..., 0]


def run(sp, work, lod, sizes, log=print):
    d = os.path.join(work, f"lod{lod}")
    size_c, size_o = sizes
    for group in sp.CLASSES:
        mpath = os.path.join(d, f"{group}_mesh.npz")
        if not os.path.exists(mpath):
            continue
        t = time.time()
        mesh = dict(np.load(mpath))
        W, FL, RAD = material_weights(sp, group, mesh)
        np.save(os.path.join(d, f"{group}_matw.npy"), W)
        ctx = Ctx(mesh, W, size_c, lod, FL, RAD)
        ctx.group = group
        out = sp.shade(group, ctx)  # dict with flat arrays
        # normals: Cycles base (0..1 -> -1..1) + detail
        base = np.load(os.path.join(d, f"{group}_normal.npy")).astype(np.float32)
        base = base * 2.0 - 1.0
        base_flat = base[ctx.mask]
        base_flat /= np.maximum(np.linalg.norm(base_flat, axis=1, keepdims=True), 1e-9)
        if "height" in out:
            det = detail_normal(ctx, out["height"], out.get("height_eps", 0.004))
            nrm = rnm(base_flat, det)
        else:
            nrm = base_flat
        nrm_img = raster.dilate(ctx.full(nrm * 0.5 + 0.5, 0.5), ctx.mask, 12)
        save_rgb(os.path.join(d, f"{group}_normal.png"), nrm_img)
        albedo = raster.dilate(ctx.full(linear_to_srgb(out["albedo"])), ctx.mask, 12)
        save_rgb(os.path.join(d, f"{group}_basecolor.png"), albedo)
        ao_c = np.load(os.path.join(d, f"{group}_ao.npy")).astype(np.float32)
        ao_c = resize(ao_c, size_c)[ctx.mask]
        ao = np.clip((0.35 + 0.65 * ao_c) * out.get("cavity", 1.0), 0, 1)
        orm = np.stack([ao, out["roughness"], out.get("metallic", np.zeros(ctx.n, np.float32))], 1)
        orm_img = raster.dilate(ctx.full(orm), ctx.mask, 12)
        save_rgb(os.path.join(d, f"{group}_orm.png"), resize(orm_img, size_o))
        em = out.get("emissive")
        if em is not None:
            em_img = raster.dilate(ctx.full(linear_to_srgb(em)), ctx.mask, 12)
            save_rgb(os.path.join(d, f"{group}_emissive.png"), resize(em_img, size_o))
        var = out.get("variant")
        if var is not None:
            var_img = raster.dilate(ctx.full(var), ctx.mask, 12)
            save_rgba(os.path.join(d, f"{group}_variant.png"), resize(var_img, max(256, size_o // 2)))
        log(f"  textures L{lod} {group} {size_c}: {time.time() - t:.1f}s")
