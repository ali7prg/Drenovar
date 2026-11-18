"""Reference projection + relief for props (one-to-one colour/carving from the drawings).

* `TexelSet`  : atlas rasterisation of an asset's LOD0 meshes (texel -> triangle/barycentrics/owner).
* `ViewSpec`  : one reference view: orthographic (frlib.refs.View) or perspective (propkit camera dict),
                the reference crop + mask, which objects it paints, and an optional pose callback
                (e.g. lay a token flat like the table-top hero drawing).
* `project_views` : visibility-tested, facing-weighted blend of all views per texel (+ partial
                de-lighting of the painted key light) -> colour, weight, painted-relief height.
* `relief_bake`   : subdivide + displace a copy of each LOD0 mesh with the atlas height map
                (real high-res relief), then Cycles-bake tangent normals and AO onto the game mesh.
* outline/thickness tracing from the reference masks (`mask_outline`, `mask_extent`).
"""
import math
import os

import bpy
import cv2
import numpy as np
from scipy import ndimage as ndi

import propkit as pk
from frlib import core, refs, texproj


# =============================================================================== texels

class TexelSet:
    def __init__(self, asset, size):
        self.asset = asset
        self.objs = asset.lod0_objects()
        tri = pk.gather_triangles(self.objs)
        nt = len(tri["P"])
        verts = tri["P"].reshape(-1, 3)
        T = texproj.rasterize_uv(verts, np.arange(nt * 3).reshape(nt, 3), tri["UA"], size, tri["N"].reshape(-1, 3))
        self.size = T.size
        self.valid = T.valid
        self.yy, self.xx = np.nonzero(T.valid)
        self.t = T.tri[self.yy, self.xx]
        self.bary = T.bary[self.yy, self.xx]
        self.owner = tri["owner"][self.t]
        self.part = tri["part"][self.t]
        self.isl = tri["isl"][self.t]
        self.flag = tri["flag"][self.t]
        self.UV = (tri["UP"][self.t] * self.bary[..., None]).sum(1)
        self.tri_rest = tri
        self.n = len(self.yy)

    def positions(self):
        """Texel world positions/normals in the CURRENT pose of the objects."""
        tri = pk.gather_triangles(self.objs)
        P = (tri["P"][self.t] * self.bary[..., None]).sum(1)
        N = pk.unit((tri["N"][self.t] * self.bary[..., None]).sum(1))
        return P, N

    def owner_mask(self, objs):
        idx = [self.objs.index(o) for o in objs]
        return np.isin(self.owner, idx)

    def to_img(self, vals, fill=0.0):
        W, H = self.size
        v = np.asarray(vals, float)
        ch = 1 if v.ndim == 1 else v.shape[1]
        im = np.full((H, W, ch), fill, float)
        im[self.yy, self.xx] = v.reshape(self.n, ch)
        return im[..., 0] if ch == 1 else im


# =============================================================================== views

class ViewSpec:
    def __init__(self, name, image, mask, objects, kind="ortho", view=None, cam=None, pose=None, unpose=None,
                 weight=1.0, light=(-0.55, 0.6, 0.55), delight=0.35, height=True, power=2.0, min_facing=0.12,
                 erode=2, depth_eps=None):
        self.name, self.image, self.mask, self.objects = name, image, mask, objects
        self.kind, self.view, self.cam = kind, view, cam
        self.pose, self.unpose = pose, unpose
        self.weight, self.light, self.delight, self.height = weight, light, delight, height
        self.power, self.min_facing, self.erode, self.depth_eps = power, min_facing, erode, depth_eps

    # image-space mapping ---------------------------------------------------------
    def project(self, P):
        if self.kind == "ortho":
            u, v, d = self.view.project(P)
            return u, v, d
        uv, z = pk.project_points(P, self.cam)
        return uv[:, 0], uv[:, 1], z

    def to_camera_dir(self, P):
        """Unit vectors from points toward the camera (for facing weights)."""
        if self.kind == "ortho":
            return np.repeat(-self.view.d[None], len(P), 0)
        return pk.unit(self.cam["C"][None] - P)

    def light_world(self):
        """Painted key light: image left/up/toward-viewer components -> world direction."""
        lx, ly, lz = self.light
        if self.kind == "ortho":
            right, up, fwd = self.view.right, self.view.up, self.view.d
        else:
            R = self.cam["R"]
            right, up, fwd = R[0], -R[1], R[2]
        return pk.unit(lx * right + ly * up - lz * fwd)


def zbuffer(tris_world, spec, W, H):
    """Nearest depth per reference pixel for triangles (n,3,3) under the view mapping."""
    P = tris_world.reshape(-1, 3)
    u, v, d = spec.project(P)
    U, V, D = u.reshape(-1, 3), v.reshape(-1, 3), d.reshape(-1, 3)
    zb = np.full((H, W), np.inf)
    x0 = np.clip(np.floor(U.min(1)).astype(int), 0, W)
    x1 = np.clip(np.ceil(U.max(1)).astype(int) + 1, 0, W)
    y0 = np.clip(np.floor(V.min(1)).astype(int), 0, H)
    y1 = np.clip(np.ceil(V.max(1)).astype(int) + 1, 0, H)
    for t in np.nonzero((x1 > x0) & (y1 > y0))[0]:
        xs = np.arange(x0[t], x1[t])
        ys = np.arange(y0[t], y1[t])
        X, Y = np.meshgrid(xs, ys)
        ax, bx, cx = U[t]
        ay, by, cy = V[t]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
        l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        if not inside.any():
            continue
        z = l1 * D[t, 0] + l2 * D[t, 1] + l3 * D[t, 2]
        sub = zb[y0[t]:y1[t], x0[t]:x1[t]]
        np.minimum(sub, np.where(inside, z, np.inf), out=sub)
    return ndi.minimum_filter(zb, size=3)


def bandpass_height(img, mask, small_px=0.8, large_px=6.0, gain=1.0):
    """Relief proxy from painted luminance (bright ridges / dark grooves), zero mean inside mask."""
    L = img @ np.array([0.299, 0.587, 0.114])
    a = ndi.gaussian_filter(L, small_px)
    b = ndi.gaussian_filter(L, large_px)
    h = (a - b) * gain
    if mask is not None and mask.any():
        h = h - h[mask].mean()
    return h


def _bilinear(img, u, v, border=cv2.BORDER_REPLICATE):
    n = len(u)
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:n] = u
    my[:n] = v
    im = img.astype(np.float32)
    if im.ndim == 2:
        im = im[..., None]
    out = cv2.remap(im, mx.reshape(rows, cols), my.reshape(rows, cols), interpolation=cv2.INTER_LINEAR,
                    borderMode=border)
    return out.reshape(rows * cols, -1)[:n].astype(np.float64)


def project_views(ts, specs, relief_px=(0.8, 6.0), log=print):
    """Blend all reference views onto texels -> (colour (n,3), weight (n,), height_px (n,), hweight (n,))."""
    acc = np.zeros((ts.n, 3))
    wsum = np.zeros(ts.n)
    hacc = np.zeros(ts.n)
    hw = np.zeros(ts.n)
    for sp in specs:
        if sp.pose:
            sp.pose()
        bpy.context.view_layer.update()
        P, N = ts.positions()
        sel = ts.owner_mask(sp.objects)
        H, W = sp.mask.shape
        tris = pk.world_triangles(sp.objects)
        zb = zbuffer(tris, sp, W, H)
        u, v, d = sp.project(P[sel])
        ui = np.round(u).astype(int)
        vi = np.round(v).astype(int)
        ok = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
        zv = np.full(len(u), -np.inf)
        zv[ok] = zb[vi[ok], ui[ok]]
        span = np.ptp(tris.reshape(-1, 3), axis=0).max()
        eps = sp.depth_eps if sp.depth_eps is not None else 0.012 * span
        vis = ok & (d <= zv + eps)
        m = ndi.binary_erosion(sp.mask, iterations=sp.erode) if sp.erode else sp.mask
        inm = np.zeros(len(u), bool)
        inm[ok] = m[vi[ok], ui[ok]]
        tocam = sp.to_camera_dir(P[sel])
        facing = np.clip((N[sel] * tocam).sum(1), 0, 1)
        w = np.where(vis & inm & (facing > sp.min_facing), facing ** sp.power * sp.weight, 0.0)
        col = _bilinear(sp.image, u, v)[:, :3]
        if sp.delight > 0:
            L = sp.light_world()
            shade = 0.45 + 0.55 * np.clip(N[sel] @ L, 0, 1)
            corr = shade ** sp.delight
            col = col / np.maximum(corr, 0.3)[:, None]
            good = w > 0
            if good.any():
                col *= (_bilinear(sp.image, u[good], v[good])[:, :3].mean() / max(col[good].mean(), 1e-6))
        idx = np.nonzero(sel)[0]
        acc[idx] += w[:, None] * col
        wsum[idx] += w
        if sp.height:
            hb = bandpass_height(sp.image, sp.mask, relief_px[0], relief_px[1])
            hv = _bilinear(hb, u, v)[:, 0]
            hacc[idx] += w * hv
            hw[idx] += w
        log(f"[proj] {sp.name}: {int((w > 0).sum())} texels painted")
        if sp.unpose:
            sp.unpose()
        bpy.context.view_layer.update()
    col = acc / np.maximum(wsum, 1e-9)[:, None]
    hgt = hacc / np.maximum(hw, 1e-9)
    return col, wsum, hgt, hw


# =============================================================================== mask tracing

def mask_outline(mask, n=None, eps_px=0.6):
    """Largest outer contour of a mask as (k,2) pixel coords (x, y), CCW in image space flipped to y-up later."""
    m = mask.astype(np.uint8)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)[:, 0, :].astype(float)
    c = ndi.gaussian_filter1d(c, 1.2, axis=0, mode="wrap")
    if n:
        c = pk.resample_closed(c, n)
    return c


def outline_metres(contour_px, centre_px, ppm):
    """Pixel contour -> metric XY (x right, y up) about a pixel centre."""
    x = (contour_px[:, 0] - centre_px[0]) / ppm
    y = (centre_px[1] - contour_px[:, 1]) / ppm
    return pk.ccw(np.stack([x, y], 1))


def mask_extent(mask):
    x0, y0, x1, y1 = refs.bbox(mask)
    return x0, y0, x1, y1, x1 - x0, y1 - y0


def ortho_view_for(name, image, mask, direction, objs, real_width=None, real_height=None):
    """refs.View scaled from a real dimension and centred on the projected model bbox (pose = current)."""
    view = refs.fit_view(name, image, mask, direction, real_width=real_width, real_height=real_height)
    tris = pk.world_triangles(objs)
    u, v, _ = view.project(tris.reshape(-1, 3))
    x0, y0, x1, y1 = refs.bbox(mask)
    view.ax += (x0 + x1) / 2 - (u.min() + u.max()) / 2
    view.ay += (y0 + y1) / 2 - (v.min() + v.max()) / 2
    return view


# =============================================================================== relief bake (Cycles)

def edge_fade(valid, texel_m, fade_m):
    """0 at UV island borders -> 1 inside (keeps displaced islands closed at their seams)."""
    dist = ndi.distance_transform_edt(valid)
    return np.clip(dist * texel_m / max(fade_m, 1e-9), 0, 1)


def relief_bake(asset, height_img, texel_m, objs=None, levels=3, samples=12, ao_distance=0.02, size=None,
                isolate=True, extrusion=None, log=print):
    """Real relief: subdivided + displaced copies of the LOD0 meshes (displacement = atlas height, metres)
    -> Cycles selected-to-active tangent NORMAL + AO bake into the shared atlas. Returns (normal, ao)."""
    import time
    t0 = time.time()
    objs = objs or asset.lod0_objects()
    H, W = height_img.shape
    size = size or W
    hmin, hmax = float(height_img.min()), float(height_img.max())
    rng = max(hmax - hmin, 1e-6)
    himg = bpy.data.images.new("__relief_h", W, H, alpha=False, float_buffer=True)
    himg.colorspace_settings.name = "Non-Color"
    norm = (height_img - hmin) / rng
    core.numpy_to_image(himg, np.repeat(norm[..., None], 3, 2))
    tex = bpy.data.textures.new("__relief_tex", "IMAGE")
    tex.image = himg
    tex.extension = "EXTEND"
    tex.use_interpolation = True
    tex.filter_type = "BOX"
    nimg = bpy.data.images.new("__relief_n", size, size, alpha=False, float_buffer=True)
    nimg.colorspace_settings.name = "Non-Color"
    aimg = bpy.data.images.new("__relief_ao", size, size, alpha=False, float_buffer=True)
    aimg.colorspace_settings.name = "Non-Color"
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bake_world")
    sc.world.light_settings.distance = ao_distance
    ext = extrusion if extrusion is not None else max(abs(hmin), abs(hmax)) * 1.5 + 0.0005
    hp_objs = {}
    for o in objs:
        hp = o.copy()
        hp.data = o.data.copy()
        hp.name = "__hp_" + o.name
        for c in o.users_collection:
            c.objects.link(hp)
        hp.parent = o.parent
        hp.matrix_world = o.matrix_world.copy()
        sub = hp.modifiers.new("sub", "SUBSURF")
        sub.subdivision_type = "SIMPLE"
        sub.levels = levels
        sub.render_levels = levels
        dsp = hp.modifiers.new("dsp", "DISPLACE")
        dsp.texture = tex
        dsp.texture_coords = "UV"
        dsp.uv_layer = "UVMap"
        dsp.direction = "NORMAL"
        dsp.strength = rng
        dsp.mid_level = -hmin / rng
        hp_objs[o.name] = hp
    tmat = bpy.data.materials.new("__relief_mat")
    tmat.use_nodes = True
    node = tmat.node_tree.nodes.new("ShaderNodeTexImage")
    tmat.node_tree.nodes.active = node
    saved = {o.name: list(o.data.materials) for o in objs}
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(tmat)
    allm = [x for x in bpy.data.objects if x.type == "MESH"]
    vis0 = {x.name: x.hide_render for x in allm}
    for kind, img in (("NORMAL", nimg), ("AO", aimg)):
        node.image = img
        first = True
        for o in objs:
            hp = hp_objs[o.name]
            for x in allm + list(hp_objs.values()):
                x.hide_render = True
            o.hide_render = False
            hp.hide_render = False
            if not isolate:
                for x in objs:
                    hp_objs[x.name].hide_render = False
            core.select_only([hp, o], o)
            o.data.uv_layers.active = o.data.uv_layers["UVMap"]
            sc.render.bake.use_selected_to_active = True
            sc.render.bake.cage_extrusion = ext
            sc.render.bake.max_ray_distance = ext * 2.5
            sc.render.bake.normal_space = "TANGENT"
            sc.render.bake.margin = 8
            sc.render.bake.use_clear = first
            bpy.ops.object.bake(type=kind, use_selected_to_active=True, cage_extrusion=ext,
                                max_ray_distance=ext * 2.5, normal_space="TANGENT", margin=8, use_clear=first)
            first = False
    for x in allm:
        if x.name in vis0:
            x.hide_render = vis0[x.name]
    for o in objs:
        o.data.materials.clear()
        for m in saved[o.name]:
            o.data.materials.append(m)
    nrm = core.image_to_numpy(nimg)[..., :3].astype(np.float64)
    ao = core.image_to_numpy(aimg)[..., 0].astype(np.float64)
    for hp in hp_objs.values():
        bpy.data.objects.remove(hp, do_unlink=True)
    bpy.data.materials.remove(tmat)
    log(f"[relief] baked normal+AO {size}px from displaced x{4 ** levels} subdivided copies in {time.time() - t0:.1f}s "
        f"(height range {hmin * 1000:.1f}..{hmax * 1000:.1f} mm)")
    return nrm, ao
