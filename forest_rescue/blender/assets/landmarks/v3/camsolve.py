"""Camera solve for painted 3/4 views (pure numpy/scipy/cv2; no bpy).

Pinhole + optional radial distortion (k1, k2) in OpenCV convention (x right, y down, camera looks +Z).
World = Blender (Z up, metres). solve(): cv2.solvePnP initialisation over a focal-length scan, then joint
least-squares refinement of f, principal point (optional), k1 (optional), rvec, tvec.
"""
import json
import math

import cv2
import numpy as np
from scipy.optimize import least_squares


class Cam:
    def __init__(self, f, cx, cy, rvec, tvec, k1=0.0, k2=0.0, size=(0, 0)):
        self.f, self.cx, self.cy = float(f), float(cx), float(cy)
        self.rvec = np.asarray(rvec, float).reshape(3)
        self.tvec = np.asarray(tvec, float).reshape(3)
        self.k1, self.k2 = float(k1), float(k2)
        self.size = tuple(int(v) for v in size)

    # ---------------------------------------------------------------- basics
    @property
    def R(self):
        return cv2.Rodrigues(self.rvec)[0]

    @property
    def centre(self):
        return -self.R.T @ self.tvec

    def K(self):
        return np.array([[self.f, 0, self.cx], [0, self.f, self.cy], [0, 0, 1.0]])

    def to_cam(self, P):
        return np.asarray(P, float) @ self.R.T + self.tvec

    def distort(self, xn, yn):
        r2 = xn * xn + yn * yn
        s = 1.0 + self.k1 * r2 + self.k2 * r2 * r2
        return xn * s, yn * s

    def undistort(self, xd, yd, iters=8):
        xn, yn = xd.copy(), yd.copy()
        for _ in range(iters):
            r2 = xn * xn + yn * yn
            s = 1.0 + self.k1 * r2 + self.k2 * r2 * r2
            xn, yn = xd / s, yd / s
        return xn, yn

    def project(self, P):
        """World points -> (u, v, depth) in painting pixels (distorted)."""
        Pc = self.to_cam(P)
        z = Pc[..., 2]
        zs = np.where(np.abs(z) < 1e-9, 1e-9, z)
        xn, yn = Pc[..., 0] / zs, Pc[..., 1] / zs
        xd, yd = self.distort(xn, yn)
        return self.f * xd + self.cx, self.f * yd + self.cy, z

    def ray(self, u, v):
        """Pixel(s) -> (origin, unit direction) in world."""
        u = np.asarray(u, float)
        v = np.asarray(v, float)
        xd, yd = (u - self.cx) / self.f, (v - self.cy) / self.f
        xn, yn = self.undistort(xd, yd)
        d = np.stack([xn, yn, np.ones_like(xn)], -1) @ self.R   # R^T applied on the right
        d /= np.linalg.norm(d, axis=-1, keepdims=True)
        return self.centre, d

    def on_plane_z(self, u, v, z):
        o, d = self.ray(u, v)
        t = (z - o[2]) / d[..., 2]
        return o + d * t[..., None]

    def on_plane(self, u, v, p0, n):
        o, d = self.ray(u, v)
        n = np.asarray(n, float)
        t = ((np.asarray(p0, float) - o) @ n) / (d @ n)
        return o + d * t[..., None]

    def on_surface(self, u, v, height_fn, z0=0.0, iters=12):
        """Intersect pixel rays with z = height_fn(x, y) (fixed-point iteration)."""
        o, d = self.ray(u, v)
        z = np.full(np.shape(u), float(z0))
        for _ in range(iters):
            t = (z - o[2]) / d[..., 2]
            P = o + d * t[..., None]
            z = height_fn(P[..., 0], P[..., 1])
        t = (z - o[2]) / d[..., 2]
        return o + d * t[..., None]

    # ---------------------------------------------------------------- Blender camera
    def blender(self, W, H):
        """Parameters for a Blender perspective camera rendering the UNDISTORTED image of size (W,H).

        Returns dict(location, rotation_matrix (3x3 world), lens_mm, sensor_mm, shift_x, shift_y)."""
        sensor = 36.0
        lens = self.f * sensor / max(W, H)
        # OpenCV cam axes (x right, y down, z fwd) -> Blender cam axes (x right, y up, z back)
        Rcv = self.R
        Rbl = np.diag([1, -1, -1]) @ Rcv            # world -> blender cam
        cam_to_world = Rbl.T
        shift_x = (W / 2.0 - self.cx) / max(W, H) * -1.0
        shift_y = (self.cy - H / 2.0) / max(W, H) * 1.0
        return dict(location=self.centre.tolist(), rot=cam_to_world.tolist(), lens=lens, sensor=sensor,
                    shift_x=shift_x, shift_y=shift_y, W=W, H=H)

    def undistort_maps(self, W, H):
        """For each painting pixel (distorted) the pixel in an undistorted pinhole render of the same K."""
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float64)
        xd, yd = (xs - self.cx) / self.f, (ys - self.cy) / self.f
        xn, yn = self.undistort(xd, yd)
        return (xn * self.f + self.cx).astype(np.float32), (yn * self.f + self.cy).astype(np.float32)

    def to_json(self):
        return dict(f=self.f, cx=self.cx, cy=self.cy, rvec=self.rvec.tolist(), tvec=self.tvec.tolist(),
                    k1=self.k1, k2=self.k2, size=list(self.size), centre=self.centre.tolist())

    @staticmethod
    def from_json(d):
        return Cam(d["f"], d["cx"], d["cy"], d["rvec"], d["tvec"], d.get("k1", 0.0), d.get("k2", 0.0),
                   d.get("size", (0, 0)))


def solve(P3, p2, size, f_range=(300, 20000), free_pp=False, free_k1=False, free_k2=False, weights=None,
          pp_prior=0.02, k_prior=0.5, f0=None, fix_f=False, f_prior=None, init_centre=None, init_target=None):
    """P3 (N,3) world points, p2 (N,2) painting pixels (crop coordinates). Returns (Cam, report)."""
    P3 = np.asarray(P3, float)
    p2 = np.asarray(p2, float)
    W, H = size
    w = np.ones(len(P3)) if weights is None else np.asarray(weights, float)
    best = None
    fs = [f0] if f0 else np.geomspace(f_range[0], f_range[1], 60)
    for f in fs:
        K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]])
        if init_centre is not None:
            C = np.asarray(init_centre, float)
            fwd = np.asarray(init_target, float) - C
            fwd /= np.linalg.norm(fwd)
            right = np.cross(fwd, [0, 0, 1.0])
            right /= np.linalg.norm(right)
            down = np.cross(fwd, right)
            Rg = np.stack([right, down, fwd])
            rv0 = cv2.Rodrigues(Rg)[0]
            tv0 = (-Rg @ C).reshape(3, 1)
            ok, rv, tv = cv2.solvePnP(P3, p2, K, None, rv0, tv0, useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
        else:
            ok, rv, tv = cv2.solvePnP(P3, p2, K, None, flags=cv2.SOLVEPNP_SQPNP)
        if not ok:
            continue
        rv, tv = cv2.solvePnPRefineLM(P3, p2, K, None, rv, tv)
        pr, _ = cv2.projectPoints(P3, rv, tv, K, None)
        err = np.sqrt((((pr[:, 0] - p2) ** 2).sum(1) * w).sum() / w.sum())
        if best is None or err < best[0]:
            best = (err, f, rv.ravel(), tv.ravel())
    err0, f, rv, tv = best
    cam = Cam(f, W / 2, H / 2, rv, tv, size=size)

    def pack(c):
        x = [math.log(c.f), *c.rvec, *c.tvec]
        if free_pp:
            x += [c.cx / W - 0.5, c.cy / H - 0.5]
        if free_k1:
            x += [c.k1]
        if free_k2:
            x += [c.k2]
        return np.array(x)

    def unpack(x):
        i = 7
        c = Cam(math.exp(x[0]), W / 2, H / 2, x[1:4], x[4:7], size=size)
        if free_pp:
            c.cx, c.cy = (x[i] + 0.5) * W, (x[i + 1] + 0.5) * H
            i += 2
        if free_k1:
            c.k1 = x[i]
            i += 1
        if free_k2:
            c.k2 = x[i]
        return c

    def resid(x):
        c = unpack(x)
        u, v, z = c.project(P3)
        r = np.concatenate([(u - p2[:, 0]) * np.sqrt(w), (v - p2[:, 1]) * np.sqrt(w)])
        extra = []
        if fix_f:
            extra += [(math.log(c.f) - math.log(f0)) * 400.0]
        elif f_prior:
            extra += [(math.log(c.f) - math.log(f_prior[0])) / f_prior[1]]
        if free_pp:
            extra += [(c.cx / W - 0.5) / pp_prior, (c.cy / H - 0.5) / pp_prior]
        if free_k1:
            extra += [c.k1 / k_prior]
        if free_k2:
            extra += [c.k2 / k_prior]
        return np.concatenate([r, np.array(extra)])

    x0 = pack(cam)
    sol = least_squares(resid, x0, method="lm" if len(P3) * 2 >= len(x0) + 2 else "trf", max_nfev=4000)
    cam = unpack(sol.x)
    u, v, z = cam.project(P3)
    e = np.hypot(u - p2[:, 0], v - p2[:, 1])
    rep = dict(rms_px=float(np.sqrt((e ** 2).mean())), max_px=float(e.max()), per_point_px=[round(float(a), 2) for a in e],
               init_rms_px=float(err0), f=cam.f, cx=cam.cx, cy=cam.cy, k1=cam.k1, k2=cam.k2,
               fov_deg=float(2 * math.degrees(math.atan(max(W, H) / 2 / cam.f))), n=len(P3),
               camera_centre=cam.centre.tolist(), depth_min=float(z.min()))
    return cam, rep
