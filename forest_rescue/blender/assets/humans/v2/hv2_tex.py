"""Painted textures for v2 humans.

* front/back paintings projected onto the texels that face them (z-buffered, |n.v| >= 0.35 with a
  soft ramp to 0.55) - nothing is projected at grazing angles, so there are no streaks;
* the expression portrait is solved as a scaled-orthographic camera from eye/eye/mouth(/nose/chin)
  landmarks and projected onto the face at its own (3.5x higher) resolution, tone-matched to the
  full-body painting;
* texels no view sees well are synthesised from the SAME character's painted cloth: low frequency
  from a 3-D neighbourhood average of seen texels (no UV bleeding), high frequency transferred
  from the painting next to the nearest seen texel by unfolding the surface around the vertical
  axis (mirrored continuation, never a stretched streak).
"""
import math

import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from frlib import texproj


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class AffineCam:
    """Scaled orthographic camera: [u, v] = s * [r1; r2] @ P + t, depth along d."""

    def __init__(self, name, image, mask, rows, t, d, weight=1.0):
        self.name, self.image, self.mask = name, image, mask
        self.rows = np.asarray(rows, float)      # 2x3 (already scaled)
        self.t = np.asarray(t, float)
        self.d = np.asarray(d, float) / np.linalg.norm(d)
        self.weight = weight

    @property
    def size(self):
        return self.image.shape[1], self.image.shape[0]

    def project(self, P):
        P = np.asarray(P, float)
        uv = P @ self.rows.T + self.t
        return uv[..., 0], uv[..., 1], P @ self.d


def rotm(yaw, pitch, roll):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1.0]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
    return Rz @ Rx @ Ry


def solve_portrait(X3, x2, img, weight=6.0):
    """X3: (n,3) world landmarks; x2: (n,2) pixel landmarks.  Camera looks along +Y (front)."""
    from scipy.optimize import least_squares
    X3 = np.asarray(X3, float)
    x2 = np.asarray(x2, float)
    c3 = X3.mean(0)
    c2 = x2.mean(0)
    s0 = np.linalg.norm(x2 - c2, axis=1).mean() / max(np.linalg.norm((X3 - c3)[:, [0, 2]], axis=1).mean(), 1e-6)

    def cam(p):
        yaw, pitch, roll, s, tx, ty = p
        Rm = rotm(yaw, pitch, roll)
        # base front camera: image right = +X, image down = -Z
        r1 = Rm @ np.array([1.0, 0, 0])
        r2 = Rm @ np.array([0, 0, -1.0])
        return s * np.stack([r1, r2]), np.array([tx, ty])

    def res(p):
        A, t = cam(p)
        pr = (X3 - c3) @ A.T + t
        r = (pr - (x2 - c2)).ravel()
        return np.concatenate([r, [p[0] * 3, p[1] * 3, p[2] * 3]])   # mild prior toward frontal
    p0 = np.array([0, 0, 0, s0, 0, 0], float)
    sol = least_squares(res, p0)
    A, t = cam(sol.x)
    tt = c2 + t - c3 @ A.T
    d = np.cross(A[0], A[1])
    d /= np.linalg.norm(d)
    # camera looks INTO the face: from -Y toward +Y
    if d[1] < 0:
        d = -d
    err = float(np.abs(res(sol.x)[:-3]).max())
    mask = np.ones(img.shape[:2], bool)
    mask[:3] = mask[-3:] = False
    mask[:, :3] = mask[:, -3:] = False
    return AffineCam("portrait", img, mask, A, tt, d, weight=weight), sol.x, err


def zbuf(verts, tris, cam):
    return texproj.zbuffer(verts, tris, cam, pad=1)


def project_views(T, verts, tris, views, lo=0.35, hi=0.55, erode=2, region=None):
    """Angle-limited, z-buffered projection.  Returns colour, weight sum, per-view weights."""
    W, H = T.size
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    acc = np.zeros((len(P), 3))
    ws = np.zeros(len(P))
    per = {}
    for v in views:
        vw, vh = v.size
        zb = zbuf(verts, tris, v)
        u, vv, dep = v.project(P)
        ui = np.round(u).astype(int)
        vi = np.round(vv).astype(int)
        ok = (ui >= 0) & (ui < vw) & (vi >= 0) & (vi < vh)
        zval = np.full(len(P), -np.inf)
        zval[ok] = zb[vi[ok], ui[ok]]
        vis = ok & (dep <= zval + 0.012)
        m = ndi.binary_erosion(v.mask, iterations=erode) if erode else v.mask
        inm = np.zeros(len(P), bool)
        inm[ok] = m[vi[ok], ui[ok]]
        facing = N @ (-v.d)
        w = smoothstep(lo, hi, facing) * vis * inm * v.weight
        if region is not None and v.name in region:
            w = w * region[v.name](P)
        col = texproj._bilinear(v.image, u, vv)[:, :3]
        acc += w[:, None] * col
        ws += w
        per[v.name] = (w, u, vv)
    col = acc / np.maximum(ws, 1e-9)[:, None]
    return (yy, xx, P, N), col, ws, per


def synthesize(T, data, col, ws, per, views, seen_thr=0.25, k=14, detail=0.9, axis_x=0.0):
    """Fill weakly seen texels from the same character's painted cloth (see module doc)."""
    yy, xx, P, N = data
    seen = ws >= seen_thr
    out = col.copy()
    if seen.all():
        return out, seen
    Ps, Cs = P[seen], col[seen]
    sub = np.arange(len(Ps))
    if len(sub) > 250000:
        sub = np.random.default_rng(0).choice(len(Ps), 250000, replace=False)
    lam = 0.04
    tree = cKDTree(np.concatenate([Ps[sub], lam * N[seen][sub]], 1))
    q = np.nonzero(~seen)[0]
    dist, idx = tree.query(np.concatenate([P[q], lam * N[q]], 1), k=k)
    wq = 1.0 / np.maximum(dist, 2e-3) ** 2
    low = (Cs[sub][idx] * wq[..., None]).sum(1) / wq.sum(1)[:, None]
    # high-frequency transfer: unfold around the vertical axis from the nearest seen texel
    near = sub[idx[:, 0]]
    seen_idx = np.nonzero(seen)[0][near]
    det = np.zeros((len(q), 3))
    best_w = np.zeros(len(q))
    for v in views:
        if v.name not in per:
            continue
        w, u, vv = per[v.name]
        hp_img = v.image[..., :3] - cv2.GaussianBlur(v.image[..., :3].astype(np.float32), (0, 0), 2.2)
        wv = w[seen_idx]
        use = wv > best_w
        if not use.any():
            continue
        Q = P[seen_idx]
        dlt = P[q] - Q
        h = np.sqrt(dlt[:, 0] ** 2 + dlt[:, 1] ** 2)
        ppm = getattr(v, "ppm", None)
        if ppm is None:
            continue
        side = np.sign((Q - np.array([axis_x, 0, 0])) @ v.right)
        us = u[seen_idx] - side * h * ppm
        vs = vv[seen_idx] - dlt[:, 2] * ppm
        hv = texproj._bilinear(hp_img, us, vs)[:, :3]
        mk = texproj._bilinear(ndi.binary_erosion(v.mask, iterations=3).astype(np.float32)[..., None], us, vs)[:, 0]
        fade = np.exp(-h / 0.05) * np.clip(mk, 0, 1)
        det[use] = (hv * fade[:, None])[use]
        best_w[use] = wv[use]
    out[q] = np.clip(low + detail * det, 0, 1)
    # blend the seam between projected and synthesised texels by weight
    t = smoothstep(0.05, seen_thr * 2.0, ws)[:, None]
    mixed = out.copy()
    partial = (ws > 0.05) & (ws < seen_thr * 2.0)
    if partial.any():
        pidx = np.nonzero(partial)[0]
        d2, i2 = tree.query(np.concatenate([P[pidx], lam * N[pidx]], 1), k=k)
        w2 = 1.0 / np.maximum(d2, 2e-3) ** 2
        low2 = (Cs[sub][i2] * w2[..., None]).sum(1) / w2.sum(1)[:, None]
        mixed[pidx] = col[pidx] * t[pidx] + low2 * (1 - t[pidx])
    return mixed, seen


def to_image(T, data, colors, fill_bg=True):
    W, H = T.size
    yy, xx = data[0], data[1]
    img = np.zeros((H, W, 3))
    img[yy, xx] = colors
    if fill_bg:
        img = texproj.dilate_margin(img, T.valid, 6)
    return img
