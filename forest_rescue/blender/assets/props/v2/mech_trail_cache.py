"""lf_mechanism_trail_cache from art/10_artifact_mechanisms.png (upper left): fallen log made of split oak staves
(hollow), a cache recess on top holding bronze tree tokens, a sliding plank lid with an iron strap + bronze ring
(slides along the log), iron latch block at the near end, white-moss boulder behind, split birch stump (landmark
'split_birch'), bracket fungi, forest-floor patch. The three trail landmarks are separate nodes so the game can
highlight them (mark_landmark_a = split birch, mark_landmark_b = white-moss rock, cache_lid = fallen trunk).
"""
import math

import numpy as np

import cagegeo as CG
import pv2

ID = "lf_mechanism_trail_cache"
ATLAS = 2048
SHEET = "10_artifact_mechanisms.png"
LIGHT = (-0.55, -0.45, 0.70)
BOX = (8, 70, 762, 390)
OPEN = 0.55
GROUND_FROM_PAINTING = False   # tried (iter 14): the convex back-projected outline over-covers -> IoU 0.73
JOINT = True      # the painting's log-end / rock points are not mutually consistent with one rigid layout:
                   # camera from the hatch (5 pts, planar PnP), every other size by back-projection

PARAMS = dict(R=0.42, L=3.6, lx0=-0.15, lx1=0.75, lw=0.36, ax0=-0.9, ax1=-0.2, ay=0.25, sx_=-2.9, sy_=1.1, sr=0.48,
              sh=1.15, rx=-1.3, ry=1.5, rh=1.35)
FREE = ["L", "lx0", "lx1", "lw", "ax0", "ax1", "ay", "sx_", "sy_", "sr", "sh", "rx", "ry", "rh"]


def points(p):
    R, L = p["R"], p["L"]
    zt = 2 * R + 0.07
    return {
        "lid_bl": (p["lx0"] + OPEN, p["lw"], zt), "lid_br": (p["lx1"] + OPEN, p["lw"], zt),
        "lid_fr": (p["lx1"] + OPEN, -p["lw"], zt), "lid_fl": (p["lx0"] + OPEN, -p["lw"], zt),
        "ring": (p["lx1"] + OPEN - 0.18, -0.2, zt + 0.06),
        "arrow_l": (p["ax0"], p["ay"], 2 * R), "arrow_r": (p["ax1"], p["ay"], 2 * R),
        "far_c": (L / 2, 0.0, R), "near_top": (-L / 2, 0.0, 2 * R), "near_bot": (-L / 2, -R * 0.7, 0.1),
        "stump_tl": (p["sx_"] - p["sr"], p["sy_"], p["sh"]), "stump_tr": (p["sx_"] + p["sr"], p["sy_"], p["sh"]),
        "stump_bf": (p["sx_"], p["sy_"] - p["sr"], 0.0), "rock_top": (p["rx"], p["ry"], abs(p["rh"])),
    }


def views():
    v = pv2.ViewSpec(
        "main", SHEET, BOX,
        {"lid_bl": (460, 201.7), "lid_br": (593.3, 168.3), "lid_fr": (628.3, 216.7), "lid_fl": (495, 261.7),
         "ring": (583.3, 220), "arrow_l": (440, 186.7), "arrow_r": (525, 166.7), "far_c": (737, 180),
         "near_top": (232, 245), "near_bot": (285, 368), "stump_tl": (50, 113.3), "stump_tr": (183.3, 105),
         "stump_bf": (100, 313), "rock_top": (300, 75)},
        pose={"cache_lid": {"loc": (OPEN, 0, 0)}},
        light=LIGHT, thresh=0.085, fill_holes=True, shadow=None, solve_opts={"fov_prior": 20.0},
        title="TRAIL CACHE main view (lid slid open)")
    return [v]


def stave_ring(g, x0, x1, R, angles, w, t, lod, tag="stave", skip_range=None, gap=None):
    for k, a in enumerate(angles):
        c = np.array([0.0, R * math.cos(a), R + R * math.sin(a)])
        Rm = np.stack([np.array([1.0, 0, 0]), np.array([0, -math.sin(a), math.cos(a)]),
                       np.array([0, math.cos(a), math.sin(a)])], 1)
        segs = [(x0, x1)]
        if gap is not None and skip_range is not None and skip_range[0] <= a <= skip_range[1]:
            segs = [(x0, gap[0]), (gap[1], x1)]
        for (a0, a1) in segs:
            if a1 - a0 < 0.05:
                continue
            g.box(c + ((a0 + a1) / 2, 0, 0), (a1 - a0 - 0.01, w, t), R=Rm, mat="wood", tag=tag,
                  chamfer=0.03 if lod == 0 else 0.0)


def build(A, p, lod):
    R, L = p["R"], p["L"]
    g = A.g("root", lod)
    # ground patch (forest floor): the painted ground outline back-projected onto z = 0 through the solved camera
    # (lower silhouette boundary only), joined with the footprints of the log, stump and rock -> convex outline
    poly = None
    v = p.get("_view") if GROUND_FROM_PAINTING else None
    if v is not None and v.cam is not None:
        from scipy.spatial import ConvexHull
        m, _ = v.mask()
        H_, W_ = m.shape
        pts = []
        for x in range(0, W_, 4):
            ys = np.nonzero(m[:, x])[0]
            if len(ys):
                pts.append((x + 0.5, ys.max() + 0.5))
        uv = np.array(pts)
        G = v.cam.on_plane_z(uv[:, 0], uv[:, 1], 0.0)
        foot = [(-L / 2, -R, 0), (L / 2, -R, 0), (L / 2, R, 0), (-L / 2, R, 0),
                (p["sx_"] - p["sr"], p["sy_"], 0), (p["sx_"], p["sy_"] + p["sr"], 0)]
        allp = np.concatenate([G[:, :2], np.array(foot)[:, :2]])
        ok = np.all(np.isfinite(allp), 1) & (np.abs(allp) < 12).all(1)
        allp = allp[ok]
        hull = ConvexHull(allp)
        poly = allp[hull.vertices]
        if lod > 0:
            poly = poly[:: (2 if lod == 1 else 3)]
    if poly is None:
        n = 20 if lod == 0 else 10
        poly = np.array([((L / 2 + 0.9) * math.cos(a) - 0.4, 1.35 * math.sin(a) + 0.35) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)])
    g.prism(np.asarray(poly, float), 0.0, 0.03, "ground", "ground", caps=(False, True))
    # hollow log of split staves; cache opening between lx0-0.4 and lx1 on the top staves
    nst = 9 if lod == 0 else 6
    angles = [math.radians(a) for a in np.linspace(-90 - 140, -90 + 140, nst)]
    gap = (p["lx0"] - 0.45, p["lx1"] + 0.02)
    stave_ring(g, -L / 2, L / 2, R * 0.93, angles, 2 * math.pi * R / nst * 1.05, 0.16, lod, skip_range=(math.radians(20), math.radians(160)), gap=gap)
    # end caps (cut ends, rings come from the painting)
    for xe in (-L / 2 + 0.03, L / 2 - 0.03):
        g.cyl((xe - 0.03, 0, R), (xe + 0.03, 0, R), R * 0.86, n=12 if lod == 0 else 8, mat="wood", tag="log_end",
              up=(0, 0, 1))
    # cache recess (dark box) + bronze tokens
    g.box(((gap[0] + gap[1]) / 2, 0, 2 * R - 0.25), (gap[1] - gap[0], 0.62, 0.36), mat="wood", tag="cache_box")
    if lod < 2:
        for k, (dx, dy, tilt) in enumerate(((-0.25, -0.05, 0.25), (-0.02, 0.08, -0.15), (0.2, -0.04, 0.35))):
            c = np.array([p["lx0"] - 0.2 + dx, dy, 2 * R - 0.02])
            Rm = CG.frame((math.cos(tilt), 0, math.sin(tilt) * 0.3), (0, -math.sin(0.5), math.cos(0.5)))
            g.cyl(c - Rm[:, 2] * 0.025, c + Rm[:, 2] * 0.025, 0.12, n=14 if lod == 0 else 8, mat="bronze", tag="token",
                  up=(1, 0, 0))
    # iron latch block at the near end of the opening
    g.box((gap[0] - 0.12, -0.05, 2 * R + 0.03), (0.22, 0.26, 0.14), mat="iron", tag="latch_block")
    # sliding lid (node): planks + iron strap + bronze ring; rest = closed over the opening
    lid = A.part("cache_lid", None, ((p["lx0"] + p["lx1"]) / 2, 0, 2 * R))
    lg = lid.geo[lod]
    for k in range(3):
        y = -p["lw"] + (k + 0.5) * (2 * p["lw"] / 3)
        lg.box(((p["lx0"] + p["lx1"]) / 2, y, 2 * R + 0.035), (p["lx1"] - p["lx0"], 2 * p["lw"] / 3 - 0.01, 0.07),
               mat="wood", tag="lid_plank")
    lg.box((p["lx1"] - 0.18, -0.02, 2 * R + 0.075), (0.06, 0.32, 0.012), mat="iron", tag="lid_strap")
    ring = [np.array([p["lx1"] - 0.18 + 0.075 * math.cos(a), -0.2, 2 * R + 0.1 + 0.075 * math.sin(a)]) for a in np.linspace(0, 2 * math.pi, 11)[:-1]]
    lg.tube(np.array(ring + [ring[0]]), 0.014, n=5, mat="bronze", tag="lid_ring")
    # white-moss boulder (landmark b)
    rk = A.part("mark_landmark_b", None, (p["rx"], p["ry"], 0))
    rh = max(0.9, abs(p["rh"]))
    rk.geo[lod].rock((p["rx"], p["ry"], rh * 0.5), (rh * 0.85, rh * 0.62, rh * 0.62), seed=4, sub=2 if lod == 0 else 1,
                     mat="stone", tag="rock")
    # split birch stump (landmark a): two half trunks with a split gap
    st = A.part("mark_landmark_a", None, (p["sx_"], p["sy_"], 0))
    sg = st.geo[lod]
    nh = 10 if lod == 0 else 6
    for side in (-1, 1):
        half = [(0.36 * math.cos(a), side * 0.04 + side * 0.36 * abs(math.sin(a))) for a in np.linspace(-math.pi / 2, math.pi / 2, nh)]
        half = np.array([(x, y) for x, y in half])
        if side < 0:
            half = half[::-1]
        poly = np.array([(p["sx_"] + 0, 0) for _ in range(0)])
        pts = np.array([(y, x) for x, y in half])
        pts = pts if side > 0 else pts
        g2 = np.array([(px_, py_) for px_, py_ in pts])
        # D-shaped prism (flat face at the split)
        ang = np.linspace(-math.pi / 2, math.pi / 2, nh)
        D = np.array([(p["sr"] * math.sin(a), side * (0.035 + p["sr"] * math.cos(a))) for a in ang])
        if side > 0:
            D = D[::-1]
        sg.prism(D, 0.0, p["sh"] + (0.06 if side > 0 else 0.0), "birch", "stump", t=(p["sx_"], p["sy_"], 0))
    # bracket fungi on the far end
    if lod < 2:
        for k, (dz, dx) in enumerate(((0.62, 0.0), (0.42, 0.1))):
            c = np.array([L / 2 - 0.25 + dx, -R * 0.75, dz + 0.4])
            g.cyl(c, c + (0, 0, 0.05), 0.18 - 0.03 * k, n=10 if lod == 0 else 6, mat="fungus", tag="fungus")
    if lod == 0:
        A.marker("artifact_spot", ((p["lx0"] + p["lx1"]) / 2 - 0.2, 0, 2 * R - 0.05))
    return A


STRICT_FACING = ("wood",)
SWATCHES = {
    "wood": dict(sheet=SHEET, box=(560, 250, 622, 268), metres=0.6),
    "stone": dict(sheet=SHEET, box=(240, 95, 290, 135), metres=0.8),
    "birch": dict(sheet=SHEET, box=(60, 140, 90, 200), metres=0.6),
    "bronze": dict(sheet=SHEET, box=(408, 252, 430, 268), metres=0.15),
    "iron": dict(sheet=SHEET, box=(316, 205, 340, 222), metres=0.15),
    "ground": dict(sheet=SHEET, box=(560, 325, 640, 360), metres=0.9),
    "fungus": dict(sheet=SHEET, box=(668, 172, 690, 186), metres=0.2),
}


def clips(A, B):
    pv2.add_clip(A, B, "lf_trail_mark_1", 1.0, {"mark_landmark_a": lambda t: {"loc": (0, 0, 0.03 * math.sin(math.pi * t))}},
                 note="landmark 1 (split birch) acknowledged: small settle bump")
    pv2.add_clip(A, B, "lf_trail_mark_2", 1.0, {"mark_landmark_b": lambda t: {"loc": (0, 0, 0.03 * math.sin(math.pi * t))}},
                 note="landmark 2 (white-moss rock) acknowledged")
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.4, {"cache_lid": lambda t: {"loc": (OPEN * pv2.ease_io((t - 0.15) / 1.1), 0, 0)}},
                 markers={"cache_open": 1.25}, note="log hatch slides open along the log (solved pose = last frame)")
    pv2.add_clip(A, B, "lf_trail_cache_close", 1.0, {"cache_lid": lambda t: {"loc": (OPEN * (1 - pv2.ease_io(t)), 0, 0)}},
                 note="hatch slides closed")


def meta(A, p):
    g = pv2.b2g
    return {"mechanism": "trail_cache",
            "steps": {"split_birch": "lf_trail_mark_1 (node mark_landmark_a)",
                      "white_moss": "lf_trail_mark_2 (node mark_landmark_b)",
                      "fallen_trunk": "lf_lock_mechanism (node cache_lid slides +X 0.55 m)"},
            "solved_clip": "lf_lock_mechanism (hold last frame)",
            "sockets": {"artifact": g(((p["lx0"] + p["lx1"]) / 2 - 0.2, 0, 2 * p["R"] - 0.05))}}


def solve(views):
    """Two-stage solve: (1) camera from the hatch rectangle + ring + arrow plank (all on the log top) with an
    assumed hatch size and a 20 deg fov prior (planar PnP); (2) log ends, stump and rock back-projected through that
    camera for initial sizes; (3) joint least squares of camera + every blueprint size on all 14 points."""
    import cv2
    from scipy.optimize import least_squares
    import camsolve
    v = views[0]
    W, H = v.size
    p = dict(PARAMS)
    f0 = max(W, H) / (2 * math.tan(math.radians(10.0)))
    K = np.array([[f0, 0, W / 2], [0, f0, H / 2], [0, 0, 1.0]])
    k1 = ["lid_bl", "lid_br", "lid_fr", "lid_fl", "ring"]
    p["ax0"] = p["lx0"] + OPEN - 0.2
    p["ax1"] = p["ax0"] + 0.62
    p["ay"] = p["lw"] + 0.14
    P = points(p)
    # look-at initialisation (camera in front-left, above): avoids the planar-PnP two-fold ambiguity
    best = None
    for el in (25, 32, 38, 45, 52):
        for az in (-40, -30, -20, -10, 0, 10):
            tgt = np.array([0.3, 0.0, 0.9])
            d = f0 * 0.9 / 138.0
            e_, a_ = math.radians(el), math.radians(az)
            C = tgt + d * np.array([math.sin(a_) * math.cos(e_), -math.cos(a_) * math.cos(e_), math.sin(e_)])
            fwd = (tgt - C) / np.linalg.norm(tgt - C)
            right = np.cross(fwd, (0, 0, 1.0))
            right /= np.linalg.norm(right)
            down = np.cross(fwd, right)
            Rm = np.stack([right, down, fwd])
            rv0 = cv2.Rodrigues(Rm)[0]
            tv0 = (-Rm @ C).reshape(3, 1)
            ok, rv, tv = cv2.solvePnP(np.array([P[k] for k in k1], float), v.p2(k1), K, None, rv0, tv0,
                                      useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
            pr, _ = cv2.projectPoints(np.array([P[k] for k in k1], float), rv, tv, K, None)
            err = float(np.sqrt(((pr[:, 0] - v.p2(k1)) ** 2).sum(1).mean()))
            Rc = cv2.Rodrigues(rv)[0]
            Cc = -Rc.T @ tv.ravel()
            if Cc[2] < 1.0:          # camera must be above the ground
                continue
            if best is None or err < best[0]:
                best = (err, rv, tv, el, az)
    err, rv, tv, el, az = best
    print(f"  [main] stage-1 hatch PnP (5 pts) rms {err:.2f}px from look-at init el {el} az {az}", flush=True)
    cam = camsolve.Cam(f0, W / 2, H / 2, rv.ravel(), tv.ravel(), size=v.size)
    # back-projections for initial sizes
    def ray_plane(key, p0, n):
        q = v.p2([key])[0]
        return cam.on_plane(np.array([q[0]]), np.array([q[1]]), p0, n)[0]
    zt = 2 * p["R"]
    nt = ray_plane("near_top", (0, 0, 0), (0, 1, 0))
    fc = ray_plane("far_c", (0, 0, 0), (0, 1, 0))
    p["L"] = float(max(2.0, min(6.0, fc[0] - nt[0])))
    sb = ray_plane("stump_bf", (0, 0, 0), (0, 0, 1))
    p["sx_"], p["sy_"] = float(sb[0]), float(sb[1] + p["sr"])
    tl = ray_plane("stump_tl", (0, p["sy_"], 0), (0, 1, 0))
    tr = ray_plane("stump_tr", (0, p["sy_"], 0), (0, 1, 0))
    p["sr"] = float(max(0.25, min(0.8, abs(tr[0] - tl[0]) / 2)))
    p["sh"] = float(max(0.6, min(2.2, (tl[2] + tr[2]) / 2)))
    rt = ray_plane("rock_top", (0, p["ry"], 0), (0, 1, 0))
    p["rx"], p["rh"] = float(rt[0]), float(max(0.6, min(2.5, rt[2])))
    print("  [main] stage-1 planar PnP init:", {k: round(p[k], 3) for k in ("L", "sx_", "sy_", "sr", "sh", "rx", "rh")}, flush=True)
    free = FREE
    keys = list(v.points)
    p0 = np.array([p[k] for k in free])

    def unpack(x):
        c = camsolve.Cam(math.exp(x[0]), W / 2, H / 2, x[1:4], x[4:7], size=v.size)
        pp = dict(p)
        for j, k in enumerate(free):
            pp[k] = x[7 + j]
        return c, pp

    def resid(x):
        c, pp = unpack(x)
        PP = points(pp)
        u, w_, _ = c.project(np.array([PP[k] for k in keys]))
        q = v.p2(keys)
        r = list(u - q[:, 0]) + list(w_ - q[:, 1])
        r.append((x[0] - math.log(f0)) * 40.0)
        for j, k in enumerate(free):
            r.append((pp[k] - p0[j]) / (0.35 * max(abs(p0[j]), 0.2)) * 0.6)
        return np.array(r)

    x0 = np.array([math.log(f0), *cam.rvec, *cam.tvec, *p0])
    if JOINT:
        sol = least_squares(resid, x0, method="trf", max_nfev=8000, loss="soft_l1", f_scale=4.0)
        cam, pp = unpack(sol.x)
    else:
        cam, pp = unpack(x0)
    PP = points(pp)
    u, w_, _ = cam.project(np.array([PP[k] for k in keys]))
    q = v.p2(keys)
    e = np.hypot(u - q[:, 0], w_ - q[:, 1])
    v.cam = cam
    v.rep = dict(rms_px=float(np.sqrt((e ** 2).mean())), max_px=float(e.max()), n=len(keys),
                 per_point_px={k: round(float(a), 2) for k, a in zip(keys, e)}, f=cam.f,
                 fov_deg=float(2 * math.degrees(math.atan(max(v.size) / 2 / cam.f))),
                 camera_centre=[round(float(a), 3) for a in cam.centre],
                 method="look-at-initialised PnP on the hatch (5 pts) + joint robust (soft-L1) least squares of "
                        "camera and layout on 14 correspondences; log-end/rock points of the painting are not consistent "
                        "with one rigid layout (outliers)")
    print(f"  [main] joint solve rms {v.rep['rms_px']:.2f}px max {v.rep['max_px']:.2f}px n={len(keys)} fov {v.rep['fov_deg']:.1f}",
          flush=True)
    print("  solved:", {k: round(float(pp[k]), 3) for k in free}, flush=True)
    pp["_view"] = v
    return pp
