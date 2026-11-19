"""Perspective cameras for the painted 3/4 views of art/03 (rear three-quarter, head close-up).

PerspCam has the same projection interface as frlib.refs.View (project -> u, v, depth) so the
texture projector and the silhouette checker can use ortho and perspective views alike.
Solve: cv2.solvePnP on hand-picked landmarks (focal length scanned, best reprojection error), then
refined on the silhouette IoU (Powell) for the rear view.  Pixel coords are crop-local.
"""
import json
import math
import os
import sys

import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_refs as R  # noqa: E402


class PerspCam:
    def __init__(self, name, image, mask, K, rvec, tvec, weight=1.0):
        self.name = name
        self.image = image
        self.mask = mask
        self.K = np.asarray(K, float)
        self.rvec = np.asarray(rvec, float).reshape(3)
        self.tvec = np.asarray(tvec, float).reshape(3)
        self.weight = weight
        self.R = cv2.Rodrigues(self.rvec)[0]
        self.C = -self.R.T @ self.tvec            # camera centre (world)
        self.d = self.R.T @ np.array([0, 0, 1.0])  # optical axis (world)

    @property
    def size(self):
        return self.image.shape[1], self.image.shape[0]

    def project(self, P):
        P = np.asarray(P, float)
        Xc = P @ self.R.T + self.tvec
        z = np.maximum(Xc[..., 2], 1e-6)
        u = self.K[0, 0] * Xc[..., 0] / z + self.K[0, 2]
        v = self.K[1, 1] * Xc[..., 1] / z + self.K[1, 2]
        return u, v, Xc[..., 2]

    def view_dirs(self, P):
        """Unit vectors from the camera towards points P (for facing tests)."""
        D = np.asarray(P, float) - self.C
        return D / np.maximum(np.linalg.norm(D, axis=-1, keepdims=True), 1e-9)

    def px_per_m_at(self, P):
        Xc = np.asarray(P, float) @ self.R.T + self.tvec
        return self.K[0, 0] / max(Xc[2], 1e-6)

    def to_json(self):
        return {"name": self.name, "K": self.K.tolist(), "rvec": self.rvec.tolist(), "tvec": self.tvec.tolist(),
                "centre_world": self.C.tolist(), "axis_world": self.d.tolist()}


def K_of(f, W, H, cx=None, cy=None):
    return np.array([[f, 0, W / 2.0 if cx is None else cx], [0, f, H / 2.0 if cy is None else cy], [0, 0, 1.0]])


def solve_pnp(P3, p2, W, H, focals, init=None):
    """Scan focal lengths; returns best (err_px, f, rvec, tvec, per-point errors)."""
    P3 = np.asarray(P3, np.float64)
    p2 = np.asarray(p2, np.float64)
    best = None
    for f in focals:
        K = K_of(f, W, H)
        if init is not None:
            ok, rv, tv = cv2.solvePnP(P3, p2, K, None, rvec=init[0].copy(), tvec=init[1].copy(),
                                      useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
        else:
            ok, rv, tv = cv2.solvePnP(P3, p2, K, None, flags=cv2.SOLVEPNP_SQPNP)
            if ok:
                ok, rv, tv = cv2.solvePnP(P3, p2, K, None, rvec=rv, tvec=tv, useExtrinsicGuess=True,
                                          flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            continue
        proj, _ = cv2.projectPoints(P3, rv, tv, K, None)
        e = np.linalg.norm(proj.reshape(-1, 2) - p2, axis=1)
        rms = float(np.sqrt((e ** 2).mean()))
        if best is None or rms < best[0]:
            best = (rms, f, rv.reshape(3), tv.reshape(3), e)
    return best


# ---------------------------------------------------------------- rear three-quarter landmarks
# crop-local pixel (REAR_BOX origin 1150,105) <- world point (rest pose, metres)
def rear_landmarks():
    x0, y0 = R.REAR_BOX[:2]
    pts = [
        ("tail_tip", (0.0, 5.30, 2.19), (1526, 361)),
        ("snout_tip", (0.0, -4.55, 2.93), (1164, 182)),
        ("heel_L", (0.70, 0.31, 0.76), (1291, 391)),
        ("heel_R", (-0.70, 0.31, 0.76), (1388, 387)),
        ("claw_toe4_L", (1.20, -0.67, 0.02), (1213, 463)),
        ("hand_claw_L", (0.45, -2.12, 1.13), (1208, 323)),
        ("knee_back_L", (0.80, -0.20, 1.40), (1288, 318)),
        ("tail_mid_top", (0.0, 2.60, 2.84), (1440, 255)),
    ]
    names = [p[0] for p in pts]
    P3 = np.array([p[1] for p in pts], float)
    p2 = np.array([(p[2][0] - x0, p[2][1] - y0) for p in pts], float)
    return names, P3, p2


def rear_cam(occ_points=None, refine=True, log=None):
    crop, mask = R.rear_mask()
    H, W = mask.shape
    names, P3, p2 = rear_landmarks()
    best = solve_pnp(P3, p2, W, H, focals=np.geomspace(300, 20000, 60))
    rms, f, rv, tv, e = best
    info = {"pnp_rms_px": rms, "pnp_focal_px": f, "pnp_errors": dict(zip(names, np.round(e, 2).tolist()))}
    cam = PerspCam("rear34", crop, mask, K_of(f, W, H), rv, tv)
    if refine and occ_points is not None:
        cam, iou = refine_silhouette(cam, occ_points, mask)
        proj = np.stack(cam.project(P3)[:2], 1)
        e2 = np.linalg.norm(proj - p2, axis=1)
        info.update({"refined_iou": iou, "refined_rms_px": float(np.sqrt((e2 ** 2).mean())),
                     "refined_errors": dict(zip(names, np.round(e2, 2).tolist())), "refined_focal_px": cam.K[0, 0]})
    info["camera"] = cam.to_json()
    if log:
        with open(log, "w") as fh:
            json.dump(info, fh, indent=2)
    return cam, info


def splat_mask(cam, pts, shape, radius_m=0.03):
    H, W = shape
    u, v, _ = cam.project(pts)
    m = np.zeros((H, W), bool)
    ui, vi = np.round(u).astype(int), np.round(v).astype(int)
    ok = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
    m[vi[ok], ui[ok]] = True
    r = max(1, int(round(cam.px_per_m_at(pts.mean(0)) * radius_m)))
    m = ndi.binary_closing(ndi.binary_dilation(m, iterations=r), iterations=2)
    return ndi.binary_fill_holes(m)


def refine_silhouette(cam, pts, mask, iters=400):
    """Powell over (rvec, tvec, log f) maximising silhouette IoU with the painted mask."""
    H, W = mask.shape
    sub = pts[:: max(1, len(pts) // 60000)]
    x0 = np.concatenate([cam.rvec, cam.tvec, [math.log(cam.K[0, 0])]])

    def make(x):
        return PerspCam(cam.name, cam.image, cam.mask, K_of(math.exp(x[6]), W, H), x[:3], x[3:6])

    def loss(x):
        c = make(x)
        m = splat_mask(c, sub, (H, W), 0.035)
        inter = (m & mask).sum()
        uni = (m | mask).sum()
        return 1.0 - inter / max(uni, 1)

    res = minimize(loss, x0, method="Powell", options={"maxiter": iters, "xtol": 1e-3, "ftol": 1e-4})
    c = make(res.x)
    return c, float(1.0 - res.fun)


# ---------------------------------------------------------------- head close-up landmarks
# crop-local (HEAD_BOX origin 0,528) <- world point in the rest pose; jaw landmarks are rotated by the
# solved jaw-open angle before solving.
HEAD_LANDMARKS_UPPER = [
    ("snout_tip", (0.0, -4.56, 2.95), (18, 726)),
    ("nostril_L", (0.235, -4.37, 3.115), (80, 676)),
    ("eye_L", (0.43, -3.63, 3.285), (274, 631)),
    ("scar_top", (0.335, -3.70, 3.52), (300, 568)),
    ("mouth_corner_L", (0.44, -3.40, 3.02), (380, 716)),
    ("upper_tooth_front_L", (0.17, -4.47, 2.84), (40, 760)),
    ("upper_tooth_mid_L", (0.40, -3.95, 2.83), (180, 766)),
    ("brow_front_L", (0.31, -3.86, 3.42), (215, 590)),
]
HEAD_LANDMARKS_JAW = [
    ("jaw_tip", (0.0, -4.50, 2.66), (76, 885)),
    ("lower_tooth_front_L", (0.16, -4.42, 2.80), (80, 845)),
    ("lower_tooth_mid_L", (0.38, -3.92, 2.80), (210, 822)),
]


def head_points(jaw_deg, hinge=(0.0, -3.22, 2.96)):
    names, P3, p2 = [], [], []
    x0, y0 = R.HEAD_BOX[:2]
    for n, p, q in HEAD_LANDMARKS_UPPER:
        names.append(n)
        P3.append(p)
        p2.append((q[0] - x0, q[1] - y0))
    a = math.radians(jaw_deg)
    h = np.array(hinge)
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    for n, p, q in HEAD_LANDMARKS_JAW:
        names.append(n)
        # opening the jaw rotates the mandible about +X (tip goes down): rotate by -a around X at the hinge
        P3.append(h + (Rx.T @ (np.array(p) - h)))
        p2.append((q[0] - x0, q[1] - y0))
    return names, np.array(P3, float), np.array(p2, float)


def head_cam(log=None):
    crop, mask = R.head_crop()
    H, W = mask.shape
    best_all = None
    for jaw in np.arange(10.0, 42.0, 1.0):
        names, P3, p2 = head_points(jaw)
        b = solve_pnp(P3, p2, W, H, focals=np.geomspace(400, 12000, 40))
        if b is not None and (best_all is None or b[0] < best_all[0][0]):
            best_all = (b, jaw, names)
    (rms, f, rv, tv, e), jaw, names = best_all
    cam = PerspCam("head_closeup", crop, mask, K_of(f, W, H), rv, tv)
    info = {"pnp_rms_px": rms, "focal_px": f, "jaw_open_deg": float(jaw),
            "errors_px": dict(zip(names, np.round(e, 2).tolist())), "camera": cam.to_json()}
    if log:
        with open(log, "w") as fh:
            json.dump(info, fh, indent=2)
    return cam, info, jaw
