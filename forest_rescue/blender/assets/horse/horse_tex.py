"""Body texture of «Искра»: multi-view projection of the turnaround sheet (per-view de-lit,
mane/tail/halter/ribbon pixels excluded) + procedural coat detail, white forehead star,
eyes, muzzle, hooves.  Pure numpy/cv2; the Blender bake (normals/AO) lives in the build.
"""
import math

import cv2
import numpy as np
from scipy import ndimage as ndi

from frlib import texproj

import horse_body as HB


def _px_world(view):
    """World coordinates (along right, up) of every crop pixel centre."""
    H, W = view.mask.shape
    u = np.arange(W)
    v = np.arange(H)
    return (u - view.ax) / view.ppm, (view.ay - v) / view.ppm


# The painted views disagree on where the head sits: the right profile draws the whole head
# 0.068 m further forward than the left profile (eye, cheek ring and noseband ring all shift
# by 0.063-0.072 m) and the front view draws it 0.026 m toward the horse's right.  Texture
# projection samples those views with the head region re-registered to the (left-profile)
# geometry, so painted eyes/rings land on the modelled eye/rings instead of beside them.
HEAD_SHIFT_M = {"right": 0.068, "front": -0.0257}


def head_offset_m(view_name, P):
    """Offset (metres along view.right) added when sampling `view_name` at world points P."""
    sh = HEAD_SHIFT_M.get(view_name, 0.0)
    if not sh:
        return np.zeros(len(P))
    w = np.clip((-0.92 - P[:, 1]) / 0.14, 0.0, 1.0)
    return sh * w


def eye_region_weight(P, view_name, radius=0.075):
    """0 near an eye for every view except the profile on that eye's side (no ghost eyes)."""
    out = np.ones(len(P))
    for s, (C, r, n) in HB.eye_geometry().items():
        near = np.linalg.norm(P - C, axis=1) < radius
        own = "left" if s == "L" else "right"
        if view_name != own:
            out[near] = 0.0
    return out


def exclusion_masks(views, tack_verts=None, tack_tris=None, dilate_px=3):
    """Per view: pixels showing mane/tail/forelock hair, halter or ribbon (not coat)."""
    out = {}
    for name, v in views.items():
        img = v.image
        H, W = v.mask.shape
        luma = img @ np.array([0.299, 0.587, 0.114])
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        green = (g > r * 1.02) & (g > b * 1.05) & v.mask
        rr, uu = _px_world(v)
        RR, UU = np.meshgrid(rr, uu)
        dark = luma < 0.25
        ex = green.copy()
        if name in ("left", "right"):
            Y = RR if name == "left" else -RR
            # mane zone: above a line from the throat to the withers
            mane_line = np.interp(Y, [-1.25, -1.05, -0.70, -0.30, -0.20],
                                  [1.98, 1.66, 1.52, 1.44, 1.60])
            ex |= dark & (UU > mane_line) & (Y > -1.32) & (Y < -0.22)
            # forelock between the ears
            ex |= dark & (UU > 1.86) & (Y < -1.12)
            # tail behind the buttocks
            ex |= (luma < 0.30) & (Y > 0.70) & (UU > 0.25)
        else:
            X = RR if name == "front" else -RR
            ex |= dark & (UU > 1.47) & ((np.abs(X) > 0.085) | (UU > 1.86))
            if name == "rear":
                ex |= (luma < 0.30) & (np.abs(X) < 0.12) & (UU > 0.18) & (UU < 1.46)
        if name in ("left", "right"):
            # the white star seen edge-on in the profiles: painted procedurally, never projected
            sat = img.max(2) - img.min(2)
            Yh = RR if name == "left" else -RR
            ex |= (luma > 0.58) & (sat < 0.20) & (Yh < -1.05) & (UU > 1.55) & v.mask
        if tack_verts is not None:
            u, vv, _ = v.project(tack_verts)
            u = u + head_offset_m(name, tack_verts) * v.ppm
            poly = np.stack([u, vv], -1)[tack_tris]
            tm = np.zeros((H, W), np.uint8)
            for t in poly:
                cv2.fillConvexPoly(tm, np.round(t * 4).astype(np.int32), 1, lineType=cv2.LINE_8,
                                   shift=2)
            ex |= tm.astype(bool)
        ex = ndi.binary_dilation(ex, iterations=dilate_px) & v.mask
        out[name] = ex
    return out


def light_dir_for(view):
    """Painted key light: upper-left of each turnaround image, slightly toward the viewer."""
    L = -0.55 * view.right + 0.75 * view.up - 0.35 * view.d
    return L / np.linalg.norm(L)


def project_body(T, verts, tris, views, excl, power=3.0, min_facing=0.12, delight=0.22,
                 ambient=0.55):
    """Blend de-lit reference colours onto texels; returns colour (H,W,3), weight (H,W)."""
    Wt, Ht = T.size
    acc = np.zeros((Ht, Wt, 3))
    wsum = np.zeros((Ht, Wt))
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    for name, view in views.items():
        zb = texproj.zbuffer(verts, tris, view)
        vw, vh = view.size
        u, v, dep = view.project(P)
        u = u + head_offset_m(name, P) * view.ppm
        ui = np.round(u).astype(int)
        vi = np.round(v).astype(int)
        ok = (ui >= 0) & (ui < vw) & (vi >= 0) & (vi < vh)
        zval = np.full(len(u), -np.inf)
        zval[ok] = zb[vi[ok], ui[ok]]
        vis = ok & (dep <= zval + 0.03)
        good = ndi.binary_erosion(view.mask, iterations=2) & ~excl[name]
        inm = np.zeros(len(u), bool)
        inm[ok] = good[vi[ok], ui[ok]]
        facing = np.clip(N @ (-view.d), 0.0, 1.0)
        w = np.where(vis & inm & (facing > min_facing), facing ** power * view.weight, 0.0)
        w = w * eye_region_weight(P, name)
        col = texproj._bilinear(view.image, u, v)[:, :3]
        L = light_dir_for(view)
        shade = ambient + (1 - ambient) * np.clip(N @ L, 0, 1)
        col = col / np.maximum(shade, 0.25)[:, None] ** delight
        acc[yy, xx] += w[:, None] * col
        wsum[yy, xx] += w
    out = acc / np.maximum(wsum, 1e-9)[..., None]
    # keep the painted mean brightness (de-lighting only evens out light/shadow sides)
    m = wsum > 0
    if m.any():
        raw = np.zeros_like(out)
        out_mean = out[m].mean(0)
        ref_mean = np.mean([v.image[ndi.binary_erosion(v.mask, iterations=3)].mean(0)
                            for v in views.values()], axis=0)
        out = out * (ref_mean / np.maximum(out_mean, 1e-4))[None, None, :]
    return np.clip(out, 0, 1), wsum


# --------------------------------------------------------------------------- procedural detail

def _star_mask(P, N, J):
    """White forehead star (4 points, long vertical points, feathered hair edge)."""
    c = np.array([0.0, -1.33, 1.815])
    rel = P - c
    x, z = rel[:, 0], rel[:, 2]
    front = (N @ np.array([0, -1.0, 0.25])) > 0.25
    near = (np.abs(rel[:, 1]) < 0.08) & front
    th = np.arctan2(z, x)
    r = np.sqrt(x * x + z * z)
    up = np.sin(th) > 0
    r_pt = np.where(np.abs(np.sin(th)) > np.abs(np.cos(th)), np.where(up, 0.044, 0.050), 0.038)
    k = np.abs(np.cos(2 * th)) ** 2.2
    R = 0.012 + (r_pt - 0.012) * k
    hair = texproj.fbm(P * np.array([1.0, 1.0, 0.25]), 160.0, 3, seed=31)
    edge = (R * (0.85 + 0.35 * hair) - r) / 0.006
    m = np.clip(edge, 0, 1) * near
    return m


def match_coat(T, col, views, excl):
    """Per-channel gain so the projected coat (body above the knees) matches the sheet's coat."""
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    sel = (P[:, 2] > 0.85) & (P[:, 1] > -0.85) & (P[:, 1] < 0.70) & (P[:, 2] < 1.45)
    tex_med = np.median(col[yy[sel], xx[sel]], 0)
    refs = []
    for name in ("left", "right"):
        v = views[name]
        rr, uu = _px_world(v)
        RR, UU = np.meshgrid(rr, uu)
        Y = RR if name == "left" else -RR
        m = v.mask & ~excl[name] & (UU > 0.85) & (UU < 1.45) & (Y > -0.85) & (Y < 0.70)
        refs.append(v.image[m])
    ref_med = np.median(np.concatenate(refs), 0)
    gain = np.clip(ref_med / np.maximum(tex_med, 1e-4), 0.8, 1.35)
    return np.clip(col * gain[None, None, :], 0, 1), gain, ref_med, tex_med


def hair_strands(P, N, flow, pal, seed=61):
    """Opaque hair-volume shading: anisotropic strand noise streaked along `flow`.

    Returns colour (n,3), roughness (n,), height (n,) for texels on the mane/tail/forelock.
    """
    d = flow / np.maximum(np.linalg.norm(flow, axis=1, keepdims=True), 1e-9)
    e1 = np.cross(d, N)
    e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-9)
    e2 = np.cross(d, e1)
    a = (P * e1).sum(1)
    b = (P * d).sum(1)
    c = (P * e2).sum(1)
    Q = np.stack([a * 230.0, b * 7.0, c * 230.0], 1)
    fine = texproj.fbm(Q, 1.0, 3, seed=seed)
    Q2 = np.stack([a * 38.0, b * 2.5, c * 38.0], 1)
    clump = texproj.fbm(Q2, 1.0, 3, seed=seed + 7)
    dark, mid, high = (np.asarray(x, float) for x in pal)
    v = np.clip(0.55 * fine + 0.45 * clump, 0, 1)
    col = dark[None] + (mid - dark)[None] * (v ** 1.2)[:, None] * 1.25
    hl = np.clip((fine - 0.62) * 4.0, 0, 1) * np.clip((clump - 0.45) * 3, 0, 1)
    col = col * (1 - 0.6 * hl[:, None]) + high[None] * 0.6 * hl[:, None]
    rough = 0.50 + 0.12 * (1 - fine)
    height = 0.9 * fine + 0.5 * clump
    return np.clip(col, 0, 1), rough, height


def details(T, col, J=None, seed=41, hair_mask=None, hair_flow=None, hair_pal=None,
            hoof_col=None):
    """Procedural coat detail + painted features.  Returns colour, roughness, height maps."""
    J = J or HB.skeleton()
    Wt, Ht = T.size
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    c = col[yy, xx].copy()
    rough = np.full(len(P), 0.72)
    height = np.zeros(len(P))
    # fine hair strokes: noise stretched along the (down/back) hair flow
    flow_scale = np.array([1.0, 0.35, 0.18])
    hair = texproj.fbm(P / flow_scale, 90.0, 4, seed=seed)
    big = texproj.fbm(P, 3.0, 4, seed=seed + 3)
    c *= (0.90 + 0.20 * hair)[:, None] * (0.94 + 0.12 * big)[:, None]
    height += 0.35 * hair
    # subtle dapples on the barrel/hindquarters (bay sheen)
    f1, f2 = texproj.voronoi(P, 9.0, seed=seed + 7)
    dap = np.clip((f2 - f1) * 9.0, 0, 1)
    body = (P[:, 2] > 0.85) & (P[:, 1] > -0.9)
    c[body] *= (0.97 + 0.06 * dap[body])[:, None]
    # darker points: legs below knee/hock get dark brown (blend with projection)
    knee_z = 0.50
    leg = (P[:, 2] < knee_z + 0.05) & (np.abs(P[:, 1]) > 0.25)
    t = np.clip((knee_z + 0.05 - P[:, 2]) / 0.12, 0, 1) * leg
    dark_pt = np.array([0.17, 0.11, 0.08]) * (0.85 + 0.3 * hair)[:, None]
    c = c * (1 - 0.55 * t[:, None]) + dark_pt * 0.55 * t[:, None]
    # hooves: horn colour with vertical growth lines, darker coronet band
    hz = P[:, 2]
    hoofm = hz < 0.072
    growth = texproj.fbm(P * np.array([1.0, 1.0, 0.08]), 140.0, 3, seed=seed + 9)
    horn_base = np.array([0.42, 0.32, 0.24]) if hoof_col is None else np.asarray(hoof_col, float)
    horn = horn_base * (0.78 + 0.4 * growth)[:, None]
    c[hoofm] = horn[hoofm] * np.clip((hz[hoofm] / 0.072) * 0.4 + 0.75, 0, 1)[:, None]
    rough[hoofm] = 0.58
    height[hoofm] += 0.5 * growth[hoofm]
    cor = (hz >= 0.072) & (hz < 0.095)
    c[cor] *= 0.6
    # muzzle: greyish dark brown around nostrils/lips
    muz = (P[:, 1] < -1.39) & (P[:, 2] < 1.54)
    mt = np.clip((-1.39 - P[:, 1]) / 0.06, 0, 1) * np.clip((1.54 - P[:, 2]) / 0.05, 0, 1)
    muz_c = np.array([0.24, 0.17, 0.135]) * (0.85 + 0.3 * hair)[:, None]
    c = c * (1 - 0.6 * mt[:, None]) + muz_c * 0.6 * mt[:, None]
    rough[muz] = 0.55
    for sx in (1, -1):
        nc = np.array([0.046 * sx, -1.54, 1.485])
        dn = np.linalg.norm((P - nc) / np.array([0.016, 0.03, 0.028]), axis=1)
        nm = np.clip(1.4 - dn, 0, 1)
        c *= (1 - 0.8 * nm)[:, None]
        rough = np.where(nm > 0.3, 0.7, rough)
    # eyes: exactly one per side — the modelled eyeball is painted dark and glossy, the lid rims
    # around it darkened (lashes); the surround comes from that side's profile only
    for s, (C, r, n) in HB.eye_geometry(J).items():
        dist = np.linalg.norm(P - C, axis=1)
        eye = np.clip((r + 0.0035 - dist) / 0.002, 0, 1)
        rim = np.clip((r + 0.011 - dist) / 0.004, 0, 1) * (1 - eye) * ((P - C) @ n > 0)
        iris = np.array([0.05, 0.035, 0.028])
        # warm brown iris toward the front of the eye, near-black pupil band in the middle
        front = np.clip(((P - C) @ np.array([0.0, -1.0, 0.0])) / r, -1, 1)
        eyec = iris[None] * (1.0 + 0.6 * np.clip(front, 0, 1))[:, None]
        c = c * (1 - eye[:, None]) + eyec * eye[:, None]
        c *= (1 - 0.45 * rim)[:, None]
        rough = np.where(eye > 0.5, 0.05, rough)
        height -= 0.4 * rim
    # inner ears darker
    for s, sx in (("L", 1), ("R", -1)):
        b, tip = J[f"ear_{s}"], J[f"ear_tip_{s}"]
        ax = tip - b
        L2 = ax @ ax
        tt = np.clip((P - b) @ ax / L2, 0, 1)
        dist = np.linalg.norm(P - (b + ax[None] * tt[:, None]), axis=1)
        inner = (dist < 0.05) & ((N @ np.array([0.3 * sx, -1.0, 0.0])) > 0.2) & (tt > 0.05)
        c[inner] *= 0.55
    # dark hair roots under the mane (crest band) and on the dock, so card gaps never show coat
    import horse_rig as HRig
    crest = np.array(HRig.mane_roots())
    cz = np.interp(P[:, 1], crest[::-1, 1], crest[::-1, 2])
    band = (P[:, 1] > -1.13) & (P[:, 1] < -0.36) & (P[:, 2] > cz - 0.10)
    t = np.clip((P[:, 2] - (cz - 0.10)) / 0.05, 0, 1) * band
    roots = np.array([0.13, 0.09, 0.065]) * (0.85 + 0.3 * hair)[:, None]
    c = c * (1 - 0.85 * t[:, None]) + roots * 0.85 * t[:, None]
    # white forehead star
    sm = _star_mask(P, N, J)
    white = np.array([0.93, 0.90, 0.84]) * (0.92 + 0.1 * hair)[:, None]
    c = c * (1 - sm[:, None]) + white * sm[:, None]
    if hair_mask is not None and hair_mask.any():
        hm = hair_mask[yy, xx]
        hc, hr, hh = hair_strands(P[hm], N[hm], hair_flow[yy[hm], xx[hm]], hair_pal)
        c[hm] = hc
        rough[hm] = hr
        height[hm] = hh
    out = col.copy()
    out[yy, xx] = np.clip(c, 0, 1)
    R = np.full((Ht, Wt), 0.72)
    R[yy, xx] = rough
    Hh = np.zeros((Ht, Wt))
    Hh[yy, xx] = height
    return out, R, Hh


def colour_balance(col, valid, target_mean=None):
    """Optional global gain so the coat mean matches a target sRGB mean."""
    if target_mean is None:
        return col
    m = col[valid].mean(0)
    gain = np.asarray(target_mean) / np.maximum(m, 1e-4)
    return np.clip(col * gain, 0, 1)


def sheet_palette(views):
    """Mane / tail / hoof colours sampled from the turnaround sheet (side views).

    Returns {name: (dark p20, median, highlight p90)} as sRGB float triples.
    """
    pix = {"mane": [], "tail": [], "hoof": []}
    for name in ("left", "right"):
        v = views[name]
        rr, uu = _px_world(v)
        RR, UU = np.meshgrid(rr, uu)
        Y = RR if name == "left" else -RR
        img = v.image
        luma = img @ np.array([0.299, 0.587, 0.114])
        m = ndi.binary_erosion(v.mask, iterations=2)
        mane_line = np.interp(Y, [-1.10, -0.95, -0.80, -0.62, -0.45], [1.86, 1.67, 1.555, 1.495, 1.50])
        mane = m & (UU > mane_line + 0.03) & (Y > -1.05) & (Y < -0.45) & (luma < 0.42)
        tail = m & (Y > 0.86) & (UU > 0.30) & (UU < 1.25) & (luma < 0.42)
        hoof = m & (UU > 0.008) & (UU < 0.055)
        pix["mane"].append(img[mane])
        pix["tail"].append(img[tail])
        pix["hoof"].append(img[hoof])
    out = {}
    for k, lst in pix.items():
        a = np.concatenate(lst)
        out[k] = (np.percentile(a, 20, 0), np.median(a, 0), np.percentile(a, 90, 0), len(a))
    return out
