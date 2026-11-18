"""Proportion warp: one smooth space deformation applied to a whole built creature - every sculpt primitive, the
skeleton (heads, tails, sockets) and the fur-card regions - so a species can be re-proportioned to a new reference
sheet without rewriting each coordinate.

A warp is a list of operations applied in order, each blended by a weight field over space:
  ("scale", pivot, (sx, sy, sz), weight)      scale about `pivot`
  ("move", (dx, dy, dz), weight)              translate
  ("rotate", pivot, axis, angle_rad, weight)  rotate about `pivot`
weight: None (everywhere) or ("x"|"y"|"z", e0, e1) - a smoothstep from 0 at e0 to 1 at e1 along that axis
(e0 > e1 gives the falling ramp), or a product of several such ramps (list).

Shapes follow the local Jacobian: ellipsoids and boxes get the exact linear image (SVD), cones and capsules keep
their end points and scale their radii by the cross-section scale; rigid parts (claws, teeth, eyes, antlers,
plates) only move and scale uniformly, so they are never sheared.
"""
import numpy as np


def _ramp(spec, P):
    if spec is None:
        return np.ones(len(P))
    if isinstance(spec, list):
        w = np.ones(len(P))
        for s in spec:
            w = w * _ramp(s, P)
        return w
    ax, e0, e1 = spec
    i = "xyz".index(ax)
    t = np.clip((P[:, i] - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _rot(axis, ang):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = np.cos(ang), np.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def apply_points(ops, P):
    """Warped positions of points P (N,3). Bone filters are ignored here (see ops_for)."""
    ops = [_strip(op) for op in (ops or [])]
    P = np.array(P, float, copy=True)
    single = P.ndim == 1
    if single:
        P = P[None, :]
    for op in ops or []:
        kind = op[0]
        if kind == "scale":
            _k, pivot, s, wspec = op
            w = _ramp(wspec, P)[:, None]
            pv = np.asarray(pivot, float)
            target = pv + (P - pv) * np.asarray(s, float)
            P = P + (target - P) * w
        elif kind == "move":
            _k, d, wspec = op
            w = _ramp(wspec, P)[:, None]
            P = P + np.asarray(d, float) * w
        elif kind == "rotate":
            _k, pivot, axis, ang, wspec = op
            th = (_ramp(wspec, P) * ang)[:, None]
            pv = np.asarray(pivot, float)
            k = np.asarray(axis, float)
            k = k / np.linalg.norm(k)
            v = P - pv
            P = pv + v * np.cos(th) + np.cross(k, v) * np.sin(th) + k * (v @ k)[:, None] * (1 - np.cos(th))
        else:
            raise ValueError(kind)
    return P[0] if single else P


def jacobian(ops, p, eps=1e-3):
    ops = [_strip(op) for op in (ops or [])]
    J = np.zeros((3, 3))
    for a in range(3):
        d = np.zeros(3)
        d[a] = eps
        J[:, a] = (apply_points(ops, p + d) - apply_points(ops, p - d)) / (2 * eps)
    return J


def _similar(J):
    """Rotation and uniform scale closest to J (polar decomposition)."""
    U, S, Vt = np.linalg.svd(J)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    return R, float(np.cbrt(max(np.prod(S), 1e-12)))


def _frame_of(M):
    """M = R diag(r) Vt -> (R with det +1, r)."""
    U, S, _Vt = np.linalg.svd(M)
    if np.linalg.det(U) < 0:
        U[:, -1] *= -1
    return U, S


def warp_prim(ops, pr, rigid=False):
    p = pr.p
    if pr.kind in ("sphere", "ellipsoid", "box"):
        c = np.asarray(p["c"], float)
        J = jacobian(ops, c)
        if rigid:
            Rj, sc = _similar(J)
            J = Rj * sc
        mean = float(np.cbrt(abs(np.linalg.det(J))))
        p["c"] = apply_points(ops, c).astype(np.float32)
        if pr.kind == "sphere":
            U, S = _frame_of(J)
            if S.max() / max(S.min(), 1e-9) < 1.03:
                p["r"] = float(p["r"]) * mean
            else:
                r = float(p["r"])
                pr.kind = "ellipsoid"
                p["r"] = (S * r).astype(np.float32)
                p["R"] = U.astype(np.float32)
        else:
            key = "r" if pr.kind == "ellipsoid" else "h"
            R = np.asarray(p["R"], float) if "R" in p else np.eye(3)
            M = J @ R @ np.diag(np.asarray(p[key], float))
            U, S = _frame_of(M)
            p[key] = S.astype(np.float32)
            p["R"] = U.astype(np.float32)
            if pr.kind == "box" and "round" in p:
                p["round"] = float(p["round"]) * mean
    elif pr.kind in ("capsule", "cone"):
        a, b = np.asarray(p["a"], float), np.asarray(p["b"], float)
        m = (a + b) / 2
        J = jacobian(ops, m)
        if rigid:
            Rj, sc = _similar(J)
            J = Rj * sc
        d = b - a
        d = d / max(np.linalg.norm(d), 1e-9)
        n1 = np.cross(d, [0, 0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0, 0])
        n1 /= np.linalg.norm(n1)
        n2 = np.cross(d, n1)
        sr = float(np.sqrt(np.linalg.norm(J @ n1) * np.linalg.norm(J @ n2)))
        mean = float(np.cbrt(abs(np.linalg.det(J))))
        if rigid:
            # rigid: the end points follow the similarity at the middle (no shear along the piece)
            mw = apply_points(ops, m)
            p["a"] = (mw + J @ (a - m)).astype(np.float32)
            p["b"] = (mw + J @ (b - m)).astype(np.float32)
        else:
            p["a"] = apply_points(ops, a).astype(np.float32)
            p["b"] = apply_points(ops, b).astype(np.float32)
        if pr.kind == "capsule":
            p["r"] = float(p["r"]) * sr
        else:
            p["ra"] = float(p["ra"]) * sr
            p["rb"] = float(p["rb"]) * sr
    else:
        raise ValueError(pr.kind)
    pr.k = float(pr.k) * mean
    pr.bounds = pr._bounds()
    return pr


def _bone_ok(op, bone):
    """Ops may end with a filter dict {"bones": (prefix, ...)}: they then move only primitives, skeleton bones and
    sockets on those bones (e.g. a tail warp that must not drag the hind feet that stand under it)."""
    f = op[-1] if isinstance(op[-1], dict) else None
    if f is None or "bones" not in f:
        return True
    return bone is not None and any(str(bone).startswith(p) for p in f["bones"])


def _strip(op):
    return op[:-1] if isinstance(op[-1], dict) else op


def ops_for(ops, bone):
    return [_strip(op) for op in (ops or []) if _bone_ok(op, bone)]


def apply(ops, sk, parts):
    """Warps a built creature in place: skeleton and every part (rigid parts without shear)."""
    if not ops:
        return sk, parts
    for b in sk.bones:
        ob = ops_for(ops, b.name)
        b.head = apply_points(ob, b.head)
        if b.tail is not None:
            b.tail = apply_points(ob, b.tail)
    sk.sockets = [(n, bone, apply_points(ops_for(ops, bone), pos)) for n, bone, pos in sk.sockets]
    seen = set()
    for part in parts:
        if part.get("warp") is False:      # authored directly in the target proportions (e.g. a new antler crown)
            continue
        P = part["part"]
        rigid = part["rigid"] is not None or part.get("keep_shape", False)
        for pr in P.prims:
            if id(pr) in seen:
                continue
            seen.add(id(pr))
            warp_prim(ops_for(ops, pr.bone), pr, rigid=rigid)
    return sk, parts


def cards(ops, regions):
    """Fur-card regions follow the warp (centre, radii, lock length and width). A bone-filtered op moves a region
    when the region is tagged with one of its bones ("bone": name) - untagged regions get the unfiltered ops."""
    if not ops:
        return regions
    out = []
    for reg in regions:
        r = dict(reg)
        o = ops_for(ops, reg.get("bone"))
        c = np.asarray(reg["centre"], float)
        J = jacobian(o, c)
        r["centre"] = tuple(apply_points(o, c))
        r["radii"] = tuple(np.abs(J) @ np.asarray(reg["radii"], float))
        mean = float(np.cbrt(abs(np.linalg.det(J))))
        r["length"] = reg["length"] * mean
        r["width"] = reg["width"] * mean
        out.append(r)
    return out


def inverse_points(ops, P, iters=12):
    """Approximate inverse of a smooth warp (fixed point: p = q - d(p), d = warp - identity). Bone filters are
    ignored here (texel positions carry no bone): close to a filtered region this is off by the filtered move."""
    ops = [_strip(op) for op in (ops or [])]
    if not ops:
        return P
    Q = np.asarray(P, float)
    X = Q.copy()
    for _ in range(iters):
        X = Q - (apply_points(ops, X) - X)
    return X.astype(np.asarray(P).dtype)


def unwarped_shade(ops, shade_fn):
    """Species shading functions were written in the sculpt's original coordinates (colour bands by height,
    the rune or the eye positions): they get the texel positions mapped back through the warp."""
    if not ops:
        return shade_fn

    def shade(group, ctx):
        ctx.P = inverse_points(ops, ctx.P).astype(np.float32)
        return shade_fn(group, ctx)
    return shade
