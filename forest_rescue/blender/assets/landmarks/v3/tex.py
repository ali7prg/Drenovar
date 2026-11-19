"""Landmarks v3 texturing (numpy): perspective projection of the painting onto texels (z-buffered, angle
weighted, material-consistent), swatch-based tri-planar fill for hidden texels, colour matching, normal maps.
"""
import math

import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from frlib import texproj

DEBUG = True
PAINT_K = 0.35          # paintedLightMix used for de-lighting (same value the game/QA shader uses)


# ----------------------------------------------------------------------------- colour helpers
def to_lab(rgb):
    a = np.clip(np.asarray(rgb, np.float32), 0, 1)
    sh = a.shape
    lab = cv2.cvtColor(a.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(sh)
    return lab


def from_lab(lab):
    a = np.asarray(lab, np.float32)
    sh = a.shape
    return np.clip(cv2.cvtColor(a.reshape(-1, 1, 3), cv2.COLOR_LAB2RGB).reshape(sh), 0, 1)


class Classes:
    """Nearest-Gaussian (Lab) classifier of painting pixels into material classes, trained on crops."""

    def __init__(self):
        self.stats = {}

    def train(self, name, pixels, inflate=1.0):
        lab = to_lab(np.asarray(pixels).reshape(-1, 3)).astype(np.float64)
        mu = lab.mean(0)
        cov = np.cov(lab.T) * inflate + np.diag([4.0, 2.0, 2.0])
        self.stats[name] = (mu, np.linalg.inv(cov), math.log(np.linalg.det(cov)))

    def classify(self, img):
        lab = to_lab(img.reshape(-1, 3)).astype(np.float64)
        names = list(self.stats)
        D = []
        for n in names:
            mu, icov, ld = self.stats[n]
            d = lab - mu
            D.append(np.einsum("ij,jk,ik->i", d, icov, d) + ld)
        D = np.stack(D, 1)
        idx = D.argmin(1)
        return np.array(names, dtype=object)[idx].reshape(img.shape[:2]), D.min(1).reshape(img.shape[:2])


# ----------------------------------------------------------------------------- tileable swatches
def make_tileable(img, blend=0.25):
    """Seamless version of a swatch: cross-fade with its half-offset copy near the borders."""
    img = np.asarray(img, np.float64)
    H, W = img.shape[:2]
    rolled = np.roll(np.roll(img, H // 2, 0), W // 2, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    dx = np.minimum(xx, W - 1 - xx) / (W * blend)
    dy = np.minimum(yy, H - 1 - yy) / (H * blend)
    w = np.clip(np.minimum(dx, dy), 0, 1)[..., None]
    w = w * w * (3 - 2 * w)
    return img * w + rolled * (1 - w)


class Swatch:
    """Tileable texture covering `metres` x `metres`, sampled tri-planarly by world position."""

    def __init__(self, img, metres, name="", rotate=False):
        img = np.asarray(img, np.float64)
        if rotate:
            img = np.ascontiguousarray(np.rot90(img))
        self.img = make_tileable(img).astype(np.float32)
        self.m = float(metres)
        self.name = name
        lab = to_lab(self.img.reshape(-1, 3))
        self.mu = lab.mean(0)
        self.sd = lab.std(0) + 1e-3

    def sample(self, P, N, offset=(0.0, 0.0, 0.0)):
        H, W = self.img.shape[:2]
        P = np.asarray(P, float) + np.asarray(offset, float)
        A = np.abs(N)
        ax = A.argmax(1)
        uv = np.where(ax[:, None] == 0, P[:, [1, 2]], np.where(ax[:, None] == 1, P[:, [0, 2]], P[:, [0, 1]]))
        u = (uv[:, 0] / self.m % 1.0) * W
        v = (1.0 - (uv[:, 1] / self.m % 1.0)) * H
        return remap_wrap(self.img, u, v)


def remap_wrap(img, u, v):
    n = len(u)
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:n] = u
    my[:n] = v
    out = cv2.remap(img.astype(np.float32), mx.reshape(rows, cols), my.reshape(rows, cols),
                    interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    return out.reshape(rows * cols, -1)[:n]


def bilinear(img, u, v):
    n = len(u)
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:n] = u
    my[:n] = v
    out = cv2.remap(img.astype(np.float32), mx.reshape(rows, cols), my.reshape(rows, cols),
                    interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out.reshape(rows * cols, -1)[:n]


# ----------------------------------------------------------------------------- z-buffer (painting camera)
class CamView:
    def __init__(self, cam, W, H):
        self.cam, self.W, self.H = cam, W, H

    @property
    def size(self):
        return self.W, self.H

    def project(self, P):
        return self.cam.project(P)


def zbuffer(cam, W, H, V, T):
    return texproj.zbuffer(V, T, CamView(cam, W, H), pad=0)


def id_buffer(cam, W, H, V, T, ids):
    """Per painting pixel: id of the nearest triangle's label (ids per triangle), -1 = empty."""
    u, v, dep = cam.project(V)
    zb = np.full((H, W), np.inf)
    lab = np.full((H, W), -1, np.int32)
    U, Vv, D = u[T], v[T], dep[T]
    x0 = np.clip(np.floor(U.min(1)).astype(int), 0, W)
    x1 = np.clip(np.ceil(U.max(1)).astype(int) + 1, 0, W)
    y0 = np.clip(np.floor(Vv.min(1)).astype(int), 0, H)
    y1 = np.clip(np.ceil(Vv.max(1)).astype(int) + 1, 0, H)
    for t in np.nonzero((x1 > x0) & (y1 > y0) & (D.min(1) > 0))[0]:
        xs = np.arange(x0[t], x1[t]) + 0.5
        ys = np.arange(y0[t], y1[t]) + 0.5
        X, Y = np.meshgrid(xs, ys)
        (ax_, bx_, cx_), (ay_, by_, cy_) = U[t], Vv[t]
        den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
        if abs(den) < 1e-12:
            continue
        l1 = ((by_ - cy_) * (X - cx_) + (cx_ - bx_) * (Y - cy_)) / den
        l2 = ((cy_ - ay_) * (X - cx_) + (ax_ - cx_) * (Y - cy_)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not inside.any():
            continue
        z = l1 * D[t, 0] + l2 * D[t, 1] + l3 * D[t, 2]
        sub = zb[y0[t]:y1[t], x0[t]:x1[t]]
        lsub = lab[y0[t]:y1[t], x0[t]:x1[t]]
        upd = inside & (z < sub)
        sub[upd] = z[upd]
        lsub[upd] = ids[t]
    return lab, zb


# ----------------------------------------------------------------------------- projection
def lambert_shade(N, light, k=PAINT_K):
    L = np.asarray(light, float)
    L = L / np.linalg.norm(L)
    return (1 - k) + k * np.clip(N @ L, 0, 1)


def project_painting(P, N, cam, img, zb, W, H, accept=None, power=1.0, depth_eps=0.06, min_facing=0.5,
                     max_mag=2.0):
    """Colour + weight for texel positions P/normals N from the painting seen by cam.
    accept: optional bool (H,W) image of painting pixels allowed for these texels."""
    u, v, dep = cam.project(P)
    ui = np.floor(u).astype(int)
    vi = np.floor(v).astype(int)
    ok = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H) & (dep > 0)
    zval = np.full(len(P), -np.inf)
    zval[ok] = zb[vi[ok], ui[ok]]
    vis = ok & (dep <= zval + depth_eps * np.maximum(1.0, dep / 20.0))
    C = cam.centre
    vd = P - C
    vd /= np.maximum(np.linalg.norm(vd, axis=1, keepdims=True), 1e-9)
    facing = np.clip(-(N * vd).sum(1), 0, 1)
    if accept is not None:
        acc = np.zeros(len(P), bool)
        acc[ok] = accept[vi[ok], ui[ok]]
        vis &= acc
    # footprint rule: project only where the painting sees the face well (|n.v| >= min_facing, stretch
    # 1/|n.v| <= 2) and a painting pixel is not magnified more than max_mag x the asset's typical footprint
    dist = np.linalg.norm(P - C, axis=1)
    foot = dist / cam.f / np.maximum(facing, 1e-3)
    # near-horizontal faces (seen from above by the game camera): strict rule; steep faces: the painting is the
    # best texture we have -> |n.v| >= 0.3 and magnification <= 3x
    horiz = N[:, 2] > 0.7
    mf = np.where(horiz, min_facing, min(min_facing, 0.3))
    mm = np.where(horiz, max_mag, max(max_mag, 3.0) if max_mag < 1e8 else max_mag)
    good_f = vis & (facing >= mf)
    ref = np.median((dist / cam.f)[good_f]) if good_f.any() else 1.0
    w = np.where(good_f & (foot <= mm * ref), facing, 0.0)
    if DEBUG:
        print(f"   project: n={len(P)} inframe={ok.mean():.3f} vis={vis.mean():.3f} facing>0.4={(facing > 0.4).mean():.3f} w>0.17={(w > 0.17).mean():.3f}", flush=True)
    col = bilinear(img, u, v)[:, :3]
    return col, w, facing


def colour_match(fill, target_lab_mu, target_lab_sd, src_mu, src_sd, strength=1.0):
    lab = to_lab(fill)
    m = (lab - src_mu) / src_sd * (src_sd + (target_lab_sd - src_sd) * strength) + src_mu + (target_lab_mu - src_mu) * strength
    return from_lab(m)


def height_from_albedo(alb, valid, sigma=6.0):
    g = alb @ np.array([0.3, 0.55, 0.15])
    g = texproj.fill(g[..., None], valid)[..., 0]
    hp = g - ndi.gaussian_filter(g, sigma)
    return hp


def normal_map(height, valid, strength=3.0):
    return texproj.height_to_normal(height, valid, strength=strength)


def dilate(img, valid, px=6):
    return texproj.dilate_margin(img, valid, px)
