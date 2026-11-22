"""Shared builders for quadruped skeletons, fur strands and plates."""
import numpy as np

from sdf import Prim, Part, smin
from rig import Skeleton

SIDES = (("L", -1.0), ("R", 1.0))  # +Z is the creature's right side (+X forward, +Y up)


def leg_bones(sk, kind, parent, girdle, joints, side_name, extra_toes=None):
    """kind 'Front'/'Hind'; joints = [girdle, upper, lower, foot, toe, tip] world positions."""
    g = ("Shoulder" if kind == "Front" else "Hip") + "_" + side_name
    sk.add(g, parent, joints[0])
    sk.add(f"UpperLeg_{kind}_{side_name}", g, joints[1])
    sk.add(f"LowerLeg_{kind}_{side_name}", f"UpperLeg_{kind}_{side_name}", joints[2])
    sk.add(f"Foot_{kind}_{side_name}", f"LowerLeg_{kind}_{side_name}", joints[3])
    sk.add(f"Toe_{kind}_{side_name}", f"Foot_{kind}_{side_name}", joints[4], tail=joints[5])
    return g


def surface_points(part, seeds, steps=6):
    """Projects seed points onto the part surface (gradient steps). Returns points and normals."""
    p = np.asarray(seeds, np.float32).copy()
    for _ in range(steps):
        d = part.eval(p, displace=False, cull=False)
        g = part.gradient(p, 0.004, displace=False, cull=False)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        p = p - d[:, None] * g
    g = part.gradient(p, 0.004, displace=False, cull=False)
    g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
    return p, g


def strands(part, seeds, flow, length, r0, r1, bone_of, mat="fur_long", k=0.03, sink=0.035, gravity=0.0,
            lift=0.25, rng=None, curl=0.0):
    """Fur locks: round cones rooted in the surface, laid along `flow(p, n)` (+ gravity)."""
    rng = rng or np.random.default_rng(0)
    pts, nrm = surface_points(part, seeds)
    out = []
    for i, (p, n) in enumerate(zip(pts, nrm)):
        f = np.asarray(flow(p, n), float)
        f = f - np.dot(f, n) * n
        f = f / max(np.linalg.norm(f), 1e-6)
        d = f + n * lift + np.array([0, -gravity, 0])
        d = d / np.linalg.norm(d)
        L = length(p) if callable(length) else length
        L *= 0.8 + 0.4 * rng.random()
        root = p - n * sink
        mid = root + d * L * 0.55 + n * (0.02 + curl * L)
        tip = root + d * L + np.array([0, -gravity * L * 0.4, 0])
        ra = (r0(p) if callable(r0) else r0) * (0.85 + 0.3 * rng.random())
        b = bone_of(p)
        out.append(Prim("cone", b, k=k, mat=mat, name=f"strand{i}a", a=root, b=mid, ra=ra, rb=ra * 0.62))
        out.append(Prim("cone", b, k=k * 0.5, mat=mat, name=f"strand{i}b", a=mid, b=tip, ra=ra * 0.62, rb=r1))
    return out


def scatter_on(part, centre, radii, count, rng, normal_filter=None):
    """Random seeds inside an ellipsoid region (later projected to the surface)."""
    pts = []
    tries = 0
    while len(pts) < count and tries < count * 200:
        tries += 1
        q = rng.uniform(-1, 1, 3)
        if np.dot(q, q) > 1:
            continue
        pts.append(np.asarray(centre) + q * np.asarray(radii))
    return np.array(pts, np.float32)


def plate_frame(n, forward):
    """Orthonormal frame for a surface plate: x along `forward` projected on the tangent plane, y = normal."""
    n = n / np.linalg.norm(n)
    f = forward - np.dot(forward, n) * n
    if np.linalg.norm(f) < 1e-4:
        f = np.cross(n, (0, 0, 1))
    f = f / np.linalg.norm(f)
    s = np.cross(f, n)
    return np.stack([f, n, s], 1)  # columns: local x, y, z


def _frame(d, n):
    d = d / np.linalg.norm(d)
    n2 = n - np.dot(n, d) * d
    if np.linalg.norm(n2) < 1e-5:
        n2 = np.cross(d, (0, 0, 1))
    n2 = n2 / np.linalg.norm(n2)
    s = np.cross(d, n2)
    return np.stack([d, n2, s], 1)


def locks(part, seeds, flow, length, width, bone_of, mat="fur_long", thick=0.35, lift=0.25, gravity=0.0,
          sink=0.04, k=0.05, rng=None, droop=0.0):
    """Flattened fur locks (two tapered ellipsoids each) laid along the coat flow."""
    rng = rng or np.random.default_rng(0)
    pts, nrm = surface_points(part, seeds)
    out = []
    for i, (p, n) in enumerate(zip(pts, nrm)):
        f = np.asarray(flow(p, n), float)
        f = f - np.dot(f, n) * n
        if np.linalg.norm(f) < 1e-5:
            f = np.array([-1.0, 0, 0]) - np.dot([-1.0, 0, 0], n) * n
        f /= np.linalg.norm(f)
        d = f + n * lift + np.array([0, -gravity, 0])
        d /= np.linalg.norm(d)
        L = (length(p) if callable(length) else length) * (0.75 + 0.5 * rng.random())
        w = (width(p) if callable(width) else width) * (0.8 + 0.4 * rng.random())
        t = w * thick
        root = p - n * sink
        b = bone_of(p)
        R1 = _frame(d, n)
        c1 = root + d * L * 0.34
        d2 = d + np.array([0, -droop, 0])
        d2 /= np.linalg.norm(d2)
        R2 = _frame(d2, n)
        c2 = root + d * L * 0.58 + d2 * L * 0.18
        out.append(Prim("ellipsoid", b, k=k, mat=mat, name=f"lock{i}a", c=c1, r=(L * 0.36, t, w * 0.5), R=R1))
        out.append(Prim("ellipsoid", b, k=k * 0.6, mat=mat, name=f"lock{i}b", c=c2, r=(L * 0.30, t * 0.7, w * 0.36),
                        R=R2))
    return out


def scale_plate(centre, n, back, length, width, thick, bone, mat, tilt=0.22, yaw=0.0, point=0.35, name="plate"):
    """A leaf/shingle plate lying on the surface; its rear edge lifts by `tilt` and ends in a point."""
    from sdf import rot_y, rot_z
    Rf = plate_frame(n, back)  # local x = toward the rear (back), y = normal, z = side
    R = Rf @ rot_y(yaw) @ rot_z(tilt)
    xa, ya, za = R[:, 0], R[:, 1], R[:, 2]
    c = np.asarray(centre, float)
    out = [Prim("ellipsoid", bone, k=0.0, mat=mat, name=name + "a", c=c, r=(length * 0.5, thick, width * 0.5), R=R)]
    tip = c + xa * length * 0.62 + ya * thick * 0.4
    out.append(Prim("cone", bone, k=0.05, mat=mat, name=name + "b", a=c + xa * length * 0.15,
                    b=tip, ra=min(width * 0.33, length * 0.3), rb=thick * 0.5))
    return out
