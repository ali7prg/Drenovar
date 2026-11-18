"""propkit — procedural hard-surface prop pipeline for «Лес потерянных» props.

Used by build_lf_cage_*.py, build_lf_artifacts.py, build_lf_props_supplies.py and
build_lf_mechanism_*.py (forest_rescue/blender/assets/props).

Model
-----
* Geometry is generated in numpy as `Piece`s (vertices, polygons, *parametric* UVs in metres,
  per-face island / smooth / flag).  Parametric UVs are LOD independent (fractions of an ideal
  length/perimeter), so LOD1/LOD2 are produced by re-running the same builder with a coarser
  tessellation and mapping their parametric UVs into the LOD0 atlas through the per-island
  affine transform recovered from LOD0 (`transfer_atlas_uv`).  Organic SDF parts are decimated
  instead (UVs preserved by Blender's collapse decimator).
* A build function returns {node_name: [Part, ...]}; nodes are static (`root`) or animated
  pivots (empties placed exactly on the real rotation axis; LOD meshes are children).
* All LOD0 meshes of one asset share one UV atlas packed by Blender.  Colour / roughness /
  metallic / height are synthesised per texel from class shaders (wood, stone, iron, bronze,
  ...) evaluated in parametric space, height -> tangent normal map, Cycles AO multiplied in.
* Export: one material per asset (baseColor JPEG, ORM JPEG (G rough, B metal), normal PNG),
  node animations as NLA tracks named exactly like the clip ids (exported with
  export_animation_mode=NLA_TRACKS so one glTF animation drives several nodes).

Axes: Blender Z up, metres; the "front" of every prop (cage door, mechanism operator side)
faces -Y, which becomes glTF +Z.
"""
import json
import math
import os
import subprocess
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

from frlib import core, paths, texproj

GROUP = "props"
FPS = 30


# =============================================================================== math helpers

def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def Rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def rot_from_to(a, b):
    """Rotation matrix taking unit vector a to unit vector b."""
    a, b = unit(a), unit(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.999999:
        p = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        ax = unit(np.cross(a, p))
        return 2 * np.outer(ax, ax) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


def axis_angle(axis, ang):
    ax = unit(axis)
    x, y, z = ax
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def M4(R=None, t=(0, 0, 0), s=1.0):
    M = np.eye(4)
    R = np.eye(3) if R is None else np.asarray(R, float)
    M[:3, :3] = R * (np.asarray(s, float) if np.ndim(s) else s)
    M[:3, 3] = t
    return M


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_in_out(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x < 0.5, 4 * x ** 3, 1 - (-2 * x + 2) ** 3 / 2)


def ease_out_back(x, s=1.4):
    x = np.clip(x, 0.0, 1.0)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


# =============================================================================== polygons 2D

def poly_area(p):
    p = np.asarray(p, float)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def ccw(p):
    p = np.asarray(p, float)
    return p if poly_area(p) > 0 else p[::-1].copy()


def offset_poly(p, d):
    """Miter offset of a CCW polygon (d>0 grows outward)."""
    p = np.asarray(p, float)
    n = len(p)
    e = np.roll(p, -1, axis=0) - p
    en = unit(np.stack([e[:, 1], -e[:, 0]], 1))  # outward normals for CCW
    prev = np.roll(en, 1, axis=0)
    bis = prev + en
    dot = np.clip((prev * en).sum(1), -0.95, 1.0)
    return p + bis * (d / (1.0 + dot))[:, None]


def ear_clip(poly):
    """Triangulate a simple CCW polygon -> list of index triples."""
    poly = np.asarray(poly, float)
    idx = list(range(len(poly)))
    tris = []

    def is_convex(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 1e-12

    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (neg and pos)

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        found = False
        m = len(idx)
        for k in range(m):
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if not is_convex(a, b, c):
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                if inside(poly[j], a, b, c) and not (np.allclose(poly[j], a) or np.allclose(poly[j], b)
                                                     or np.allclose(poly[j], c)):
                    ok = False
                    break
            if ok:
                tris.append((i0, i1, i2))
                idx.pop(k)
                found = True
                break
        if not found:  # degenerate: fan the rest
            for k in range(1, len(idx) - 1):
                tris.append((idx[0], idx[k], idx[k + 1]))
            idx = idx[:2]
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def bridge_hole(outer, hole):
    """Merge a CW hole into a CCW outer polygon with a slit -> (polygon, index map)."""
    outer = ccw(outer)
    hole = ccw(hole)[::-1]  # CW
    hi = int(np.argmax(hole[:, 0]))
    hp = hole[hi]
    # nearest outer vertex visible to the right
    d = np.linalg.norm(outer - hp, axis=1) + np.where(outer[:, 0] >= hp[0], 0, 10)
    oi = int(np.argmin(d))
    poly = list(outer[:oi + 1]) + list(np.roll(hole, -hi, axis=0)) + [hole[hi]] + list(outer[oi:])
    return np.array(poly)


def circle(r, n, a0=0.0):
    a = a0 + np.arange(n) * 2 * math.pi / n
    return np.stack([r * np.cos(a), r * np.sin(a)], 1)


def ngon(r, n, a0=None):
    return circle(r, n, (math.pi / 2 if a0 is None else a0))


def rect(w, h, chamfer=0.0):
    x, y = w / 2, h / 2
    c = min(chamfer, x * 0.45, y * 0.45)
    if c <= 0:
        return np.array([[x, -y], [x, y], [-x, y], [-x, -y]], float)
    return np.array([[x, -y + c], [x, y - c], [x - c, y], [-x + c, y], [-x, y - c], [-x, -y + c],
                     [-x + c, -y], [x - c, -y]], float)


def rounded_rect(w, h, r, seg=3):
    x, y = w / 2 - r, h / 2 - r
    pts = []
    for cx, cy, a0 in ((x, y, 0), (-x, y, 90), (-x, -y, 180), (x, -y, 270)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts)


def resample_closed(p, n):
    """Resample a closed polyline to n points evenly by arc length."""
    p = np.asarray(p, float)
    q = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n, endpoint=False)
    return np.stack([np.interp(t, s, q[:, k]) for k in range(q.shape[1])], 1)


# =============================================================================== Piece

class Piece:
    """Polygon soup with per-corner parametric UVs (metres) and per-face attributes."""

    def __init__(self, V=None):
        self.V = np.zeros((0, 3)) if V is None else np.asarray(V, float)
        self.F = []      # tuples of vertex indices
        self.UV = []     # per face: list of (u, v)
        self.isl = []    # per face island id (0..)
        self.smooth = []
        self.flag = []   # 1 = chamfer/edge band, 2 = end grain / cap, 0 = main surface
        self.uv_mode = "param"

    def add_face(self, idx, uv, isl=0, smooth=False, flag=0):
        self.F.append(tuple(int(i) for i in idx))
        self.UV.append([(float(a), float(b)) for a, b in uv])
        self.isl.append(int(isl))
        self.smooth.append(bool(smooth))
        self.flag.append(int(flag))

    def append_verts(self, V):
        base = len(self.V)
        self.V = np.vstack([self.V, np.asarray(V, float).reshape(-1, 3)])
        return base

    def transformed(self, M):
        p = Piece()
        M = np.asarray(M, float)
        p.V = self.V @ M[:3, :3].T + M[:3, 3]
        if np.linalg.det(M[:3, :3]) < 0:
            p.F = [tuple(reversed(f)) for f in self.F]
            p.UV = [list(reversed(u)) for u in self.UV]
        else:
            p.F = list(self.F)
            p.UV = [list(u) for u in self.UV]
        p.isl, p.smooth, p.flag, p.uv_mode = list(self.isl), list(self.smooth), list(self.flag), self.uv_mode
        return p

    def tri_count(self):
        return sum(len(f) - 2 for f in self.F)

    @staticmethod
    def merge(pieces):
        out = Piece()
        Vs = []
        base = 0
        for p in pieces:
            Vs.append(p.V)
            out.F += [tuple(i + base for i in f) for f in p.F]
            out.UV += p.UV
            out.isl += p.isl
            out.smooth += p.smooth
            out.flag += p.flag
            base += len(p.V)
        out.V = np.vstack(Vs) if Vs else np.zeros((0, 3))
        return out


def _orient_faces_outward(piece, faces_range, centre_fn):
    """Flip faces whose normal points towards centre_fn(face_centroid)."""
    V = piece.V
    for fi in faces_range:
        f = piece.F[fi]
        pts = V[list(f)]
        c = pts.mean(0)
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        if np.dot(n, c - centre_fn(c, fi)) < 0:
            piece.F[fi] = tuple(reversed(f))
            piece.UV[fi] = list(reversed(piece.UV[fi]))


# =============================================================================== primitives

def _frames(path, closed, up):
    n = len(path)
    if closed:
        T = path[(np.arange(n) + 1) % n] - path[(np.arange(n) - 1) % n]
    else:
        T = np.gradient(path, axis=0) if n > 2 else np.repeat((path[1:2] - path[:1]), n, axis=0)
    T = unit(T)
    up = unit(np.asarray(up, float))
    N = np.zeros_like(T)
    n0 = up - np.dot(up, T[0]) * T[0]
    if np.linalg.norm(n0) < 1e-6:
        alt = np.array([1.0, 0, 0]) if abs(T[0][0]) < 0.9 else np.array([0, 1.0, 0])
        n0 = alt - np.dot(alt, T[0]) * T[0]
    N[0] = unit(n0)
    for i in range(1, n):
        R = rot_from_to(T[i - 1], T[i])
        v = R @ N[i - 1]
        v = v - np.dot(v, T[i]) * T[i]
        N[i] = unit(v)
    if closed:
        # distribute the holonomy so the frame closes
        R = rot_from_to(T[-1], T[0])
        nend = R @ N[-1]
        ang = math.atan2(np.dot(np.cross(nend, N[0]), T[0]), np.dot(nend, N[0]))
        for i in range(n):
            N[i] = axis_angle(T[i], ang * i / n) @ N[i]
    B = np.cross(T, N)
    return T, N, B


def sweep(path, profile, closed_path=False, scale=None, up=(0, 0, 1), caps=True, smooth=True,
          edge_flags=None, ref_len=None, ref_perim=None, twist=None, cap_flag=2):
    """Sweep a closed 2-D profile (k,2; x->N, y->B) along a 3-D polyline path (n,3).

    UV: u = path fraction * ref_len, v = profile perimeter fraction * ref_perim (metres).
    smooth: bool or per-profile-edge bools; edge_flags: per-profile-edge face flags.
    """
    path = np.asarray(path, float)
    prof = ccw(np.asarray(profile, float))
    n, k = len(path), len(prof)
    T, N, B = _frames(path, closed_path, up)
    if scale is None:
        sc = np.ones((n, 2))
    else:
        sc = np.asarray(scale, float)
        sc = np.repeat(sc[:, None], 2, axis=1) if sc.ndim == 1 else sc
    if twist is not None:
        tw = np.asarray(twist, float)
        Nn = np.cos(tw)[:, None] * N + np.sin(tw)[:, None] * B
        Bn = -np.sin(tw)[:, None] * N + np.cos(tw)[:, None] * B
        N, B = Nn, Bn
    seglen = np.linalg.norm(np.diff(np.vstack([path, path[:1]]) if closed_path else path, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seglen)])
    L = cum[-1]
    tfrac = cum / max(L, 1e-9)
    ref_len = L if ref_len is None else ref_len
    pe = np.linalg.norm(np.roll(prof, -1, axis=0) - prof, axis=1)
    pc = np.concatenate([[0], np.cumsum(pe)])
    P = pc[-1]
    sfrac = pc / max(P, 1e-9)
    ref_perim = P * float(np.mean(sc)) if ref_perim is None else ref_perim
    if isinstance(smooth, (bool, np.bool_)):
        smooth = [bool(smooth)] * k
    if edge_flags is None:
        edge_flags = [0] * k
    piece = Piece()
    ring = path[:, None, :] + sc[:, None, 0:1] * prof[None, :, 0:1] * N[:, None, :] \
        + sc[:, None, 1:2] * prof[None, :, 1:2] * B[:, None, :]
    base = piece.append_verts(ring.reshape(-1, 3))
    nrings = n
    segs = n if closed_path else n - 1
    for i in range(segs):
        i1 = (i + 1) % n
        u0 = tfrac[i] * ref_len
        u1 = tfrac[i + 1] * ref_len
        for j in range(k):
            j1 = (j + 1) % k
            v0 = sfrac[j] * ref_perim
            v1 = sfrac[j + 1] * ref_perim
            idx = (base + i * k + j, base + i * k + j1, base + i1 * k + j1, base + i1 * k + j)
            piece.add_face(idx, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)], 0, smooth[j], edge_flags[j])
    first_side = 0
    nside = len(piece.F)

    def centre(c, fi):
        # nearest path point
        d = np.linalg.norm(path - c, axis=1)
        return path[int(np.argmin(d))]
    # CCW profile in the right-handed (N, B, T) frame -> side quads already face outward (also for concave
    # profiles such as troughs), so no centroid-based flipping here.
    if caps and not closed_path:
        for which, ri, isl in ((0, 0, 1), (1, n - 1, 2)):
            cb = piece.append_verts(ring[ri])
            tris = ear_clip(prof)
            for t in tris:
                uvs = [tuple(prof[a] * sc[ri]) for a in t]
                piece.add_face((cb + t[0], cb + t[1], cb + t[2]), uvs, isl, False, cap_flag)
            outward = -T[0] if which == 0 else T[-1]
            for fi in range(len(piece.F) - len(tris), len(piece.F)):
                f = piece.F[fi]
                pts = piece.V[list(f)]
                nn = np.cross(pts[1] - pts[0], pts[2] - pts[0])
                if np.dot(nn, outward) < 0:
                    piece.F[fi] = tuple(reversed(f))
                    piece.UV[fi] = list(reversed(piece.UV[fi]))
    return piece


def beam(p0, p1, w, h, chamfer=0.0, up=None, caps=True, segs=1, bend=None, force_up=False):
    """Rectangular timber/iron bar from p0 to p1.

    Automatic section frame: vertical members -> w along world X, h along world Y;
    other members -> w = horizontal width (perpendicular to the bar), h = vertical height.
    (`up` is ignored unless force_up=True.)
    """
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    T = unit(p1 - p0)
    if not force_up or up is None:
        if abs(T[2]) > 0.9:
            up = (1.0, 0.0, 0.0)
        else:
            up = tuple(unit(np.cross([0.0, 0.0, 1.0], T)))
    t = np.linspace(0, 1, segs + 1)
    path = p0[None] + (p1 - p0)[None] * t[:, None]
    if bend is not None:
        path = path + np.asarray(bend, float)[None] * np.sin(np.pi * t)[:, None]
    prof = rect(w, h, chamfer)
    flags = [0] * len(prof)
    if chamfer > 0:
        flags = [0, 1] * 4  # rect() alternates main/chamfer edges starting with +x side
    return sweep(path, prof, up=up, caps=caps, smooth=False, edge_flags=flags)


def rect_face_v(w, h, c, face):
    """Parametric v (perimeter metres) of a face centre of a rect(w, h, c) sweep profile.
    faces: '+N', '+B', '-N', '-B' (beam(): +N = +X for vertical members, Z x T for others; B ~ up)."""
    a, b, d = h - 2 * c, w - 2 * c, c * math.sqrt(2)
    start = {"+N": 0.0, "+B": a + d, "-N": a + b + 2 * d, "-B": 2 * a + b + 3 * d}[face]
    return start + (a / 2 if face in ("+N", "-N") else b / 2)


def rod(p0, p1, r, sides=6, caps=True, up=(0, 0, 1), r1=None, segs=1):
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    t = np.linspace(0, 1, segs + 1)
    path = p0[None] + (p1 - p0)[None] * t[:, None]
    scale = None if r1 is None else np.interp(t, [0, 1], [1.0, r1 / r])
    return sweep(path, circle(r, sides, math.pi / sides), up=up, caps=caps, smooth=True, scale=scale,
                 ref_perim=2 * math.pi * r)


def tube(path, r, sides=6, closed_path=False, caps=True, up=(0, 0, 1), scale=None, twist=None):
    return sweep(path, circle(r, sides, math.pi / sides), closed_path=closed_path, up=up, caps=caps,
                 smooth=True, scale=scale, twist=twist, ref_perim=2 * math.pi * r)


def extrude(outline, depth, chamfer=0.0, smooth_sides=False, hole=None, cap_isl=(1, 2),
            side_flag=0, bottom=True, top=True):
    """Prism of a 2-D outline (CCW, XY) from z=0 to z=depth with optional chamfer bands.

    Caps get planar UVs (x, y); sides u = perimeter fraction * P, v = z.
    hole: optional inner outline cut through (with inner walls).
    """
    outline = ccw(np.asarray(outline, float))
    k = len(outline)
    pe = np.linalg.norm(np.roll(outline, -1, axis=0) - outline, axis=1)
    pc = np.concatenate([[0], np.cumsum(pe)])
    P = pc[-1]
    c = min(chamfer, depth * 0.45)
    if c > 0:
        inset = offset_poly(outline, -c)
        layers = [(inset, 0.0), (outline, c), (outline, depth - c), (inset, depth)]
        flags = [1, side_flag, 1]
    else:
        layers = [(outline, 0.0), (outline, depth)]
        flags = [side_flag]
    piece = Piece()
    rings = []
    for pts, z in layers:
        rings.append(piece.append_verts(np.c_[pts, np.full(k, z)]))
    for li in range(len(layers) - 1):
        r0, r1 = rings[li], rings[li + 1]
        z0, z1 = layers[li][1], layers[li + 1][1]
        for j in range(k):
            j1 = (j + 1) % k
            u0 = pc[j]
            u1 = pc[j + 1]
            piece.add_face((r0 + j, r0 + j1, r1 + j1, r1 + j), [(u0, z0), (u1, z0), (u1, z1), (u0, z1)], 0,
                           smooth_sides, flags[li])
    cap_poly = layers[0][0]
    top_poly = layers[-1][0]
    if hole is not None:
        hole = ccw(np.asarray(hole, float))
        kh = len(hole)
        hb0 = piece.append_verts(np.c_[hole, np.zeros(kh)])
        hb1 = piece.append_verts(np.c_[hole, np.full(kh, depth)])
        hpe = np.linalg.norm(np.roll(hole, -1, axis=0) - hole, axis=1)
        hpc = np.concatenate([[0], np.cumsum(hpe)])
        for j in range(kh):
            j1 = (j + 1) % kh
            piece.add_face((hb0 + j1, hb0 + j, hb1 + j, hb1 + j1),
                           [(hpc[j + 1], 0), (hpc[j], 0), (hpc[j], depth), (hpc[j + 1], depth)], 3, smooth_sides, 1)
        cap_poly = bridge_hole(cap_poly, hole)
        top_poly = bridge_hole(top_poly, hole)
    for poly, z, isl, up in ((cap_poly, 0.0, cap_isl[0], False), (top_poly, depth, cap_isl[1], True)):
        if (z == 0.0 and not bottom) or (z == depth and not top):
            continue
        cb = piece.append_verts(np.c_[poly, np.full(len(poly), z)])
        for t in ear_clip(poly):
            tt = t if up else (t[0], t[2], t[1])
            piece.add_face(tuple(cb + i for i in tt), [tuple(poly[i]) for i in tt], isl, False, 2 if False else 0)
    return piece


def lathe(profile, segments, a0=0.0, a1=2 * math.pi, smooth=True, ref_R=None, cap_flag=0, flags=None, v_values=None):
    """Surface of revolution around +Z of profile (k,2) = (r, z) listed bottom -> top.

    Ends with r==0 collapse to poles. UV: u = angle fraction * 2*pi*R_ref, v = arc fraction * L.
    """
    prof = np.asarray(profile, float)
    k = len(prof)
    full = abs((a1 - a0) - 2 * math.pi) < 1e-6
    ns = segments if full else segments + 1
    ang = a0 + (a1 - a0) * np.arange(ns) / segments
    pe = np.linalg.norm(np.diff(prof, axis=0), axis=1)
    pc = np.concatenate([[0], np.cumsum(pe)]) if v_values is None else np.asarray(v_values, float)
    Lp = pc[-1]
    R = ref_R if ref_R is not None else float(prof[:, 0].max())
    piece = Piece()
    if isinstance(smooth, (bool, np.bool_)):
        smooth = [bool(smooth)] * (k - 1)
    if flags is None:
        flags = [0] * (k - 1)
    rows = []
    for i in range(k):
        r, z = prof[i]
        if r < 1e-9:
            rows.append(("pole", piece.append_verts([[0, 0, z]])))
        else:
            pts = np.stack([r * np.cos(ang), r * np.sin(ang), np.full(ns, z)], 1)
            rows.append(("ring", piece.append_verts(pts)))
    U = (np.arange(segments + 1) / segments) * (a1 - a0) * R
    for i in range(k - 1):
        (ta, ba), (tb, bb) = rows[i], rows[i + 1]
        v0, v1 = pc[i], pc[i + 1]
        for s in range(segments):
            s1 = (s + 1) % ns if full else s + 1
            if ta == "ring" and tb == "ring":
                idx = (ba + s, ba + s1, bb + s1, bb + s)
                uv = [(U[s], v0), (U[s + 1], v0), (U[s + 1], v1), (U[s], v1)]
            elif ta == "pole" and tb == "ring":
                idx = (ba, bb + s1, bb + s)
                uv = [((U[s] + U[s + 1]) / 2, v0), (U[s + 1], v1), (U[s], v1)]
            elif ta == "ring" and tb == "pole":
                idx = (ba + s, ba + s1, bb)
                uv = [(U[s], v0), (U[s + 1], v0), ((U[s] + U[s + 1]) / 2, v1)]
            else:
                continue
            piece.add_face(idx, uv, 0, smooth[i], flags[i])
    return piece


def disc(r, n, z=0.0, up=True, isl=1):
    """Flat n-gon cap with planar UVs."""
    piece = Piece()
    pts = circle(r, n)
    c = piece.append_verts(np.c_[pts, np.full(n, z)])
    for t in ear_clip(pts):
        tt = t if up else (t[0], t[2], t[1])
        piece.add_face(tuple(c + i for i in tt), [tuple(pts[i]) for i in tt], isl, False, 0)
    return piece


def grid(fn, nu, nv, Lu=1.0, Lv=1.0, wrap_u=False, smooth=True, isl=0):
    """Parametric surface fn(u, v) -> (..., 3) over u, v in [0, 1]."""
    us = np.linspace(0, 1, nu + 1)
    vs = np.linspace(0, 1, nv + 1)
    UU, VV = np.meshgrid(us, vs, indexing="ij")
    P = fn(UU, VV)
    piece = Piece()
    cols = nu if wrap_u else nu + 1
    base = piece.append_verts(P[:cols].reshape(-1, 3))
    for i in range(nu):
        i1 = (i + 1) % nu if wrap_u else i + 1
        for j in range(nv):
            idx = (base + i * (nv + 1) + j, base + i1 * (nv + 1) + j, base + i1 * (nv + 1) + j + 1,
                   base + i * (nv + 1) + j + 1)
            uv = [(us[i] * Lu, vs[j] * Lv), (us[i + 1] * Lu, vs[j] * Lv), (us[i + 1] * Lu, vs[j + 1] * Lv),
                  (us[i] * Lu, vs[j + 1] * Lv)]
            piece.add_face(idx, uv, isl, smooth, 0)
    return piece


def ellipsoid(c, radii, nu=12, nv=8, deform=None):
    c = np.asarray(c, float)
    r = np.asarray(radii, float)

    def fn(u, v):
        th = u * 2 * math.pi
        ph = (v - 0.5) * math.pi
        x = np.cos(ph) * np.cos(th)
        y = np.cos(ph) * np.sin(th)
        z = np.sin(ph)
        P = np.stack([x * r[0], y * r[1], z * r[2]], -1)
        if deform is not None:
            P = deform(P, u, v)
        return P + c
    return grid(fn, nu, nv, Lu=2 * math.pi * r[:2].mean(), Lv=math.pi * r.mean(), wrap_u=True)


def orient_toward(piece, direction):
    """Flip faces whose normal points against `direction` (e.g. ground discs -> +Z)."""
    d = np.asarray(direction, float)
    for fi, f in enumerate(piece.F):
        pts = piece.V[list(f)]
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        if np.dot(n, d) < 0:
            piece.F[fi] = tuple(reversed(f))
            piece.UV[fi] = list(reversed(piece.UV[fi]))
    return piece


def mesh_piece(V, F, smooth=True):
    """Piece from an arbitrary triangle/quad mesh; UVs are assigned later with smart project."""
    p = Piece(V)
    for f in F:
        p.add_face(f, [(0.0, 0.0)] * len(f), 0, smooth, 0)
    p.uv_mode = "smart"
    return p


# =============================================================================== Parts / nodes

class Part:
    __slots__ = ("name", "cls", "piece", "meta", "density")

    def __init__(self, name, cls, piece, meta=None, density=1.0):
        self.name, self.cls, self.piece, self.meta, self.density = name, cls, piece, (meta or {}), density


class Builder:
    """Collects parts per node for one LOD level: B.add('door', 'stile_l', 'oak', piece)."""

    def __init__(self, lod):
        self.lod = lod
        self.nodes = {}

    def add(self, node, name, cls, piece, meta=None, density=1.0, M=None, max_lod=2):
        if self.lod > max_lod or piece is None:
            return
        if M is not None:
            piece = piece.transformed(M)
        key = name
        lst = self.nodes.setdefault(node, [])
        # parts may be added in several pieces under the same name
        for p in lst:
            if p.name == key:
                p.piece = Piece.merge([p.piece, piece])
                return
        lst.append(Part(key, cls, piece, meta, density))

    def seg(self, n0, n1=None, n2=None):
        """Tessellation helper: choose count by LOD."""
        opts = [n0, n1 if n1 is not None else max(2, int(round(n0 * 0.6))),
                n2 if n2 is not None else max(2, int(round(n0 * 0.35)))]
        return opts[self.lod]


# =============================================================================== Blender mesh creation

def build_object(name, parts, part_ids, cls_ids, pivot=(0, 0, 0), col=None):
    """Create a mesh object from parts (vertices in world space, stored relative to pivot)."""
    pieces = []
    face_part, face_cls = [], []
    for p in parts:
        pieces.append(p.piece)
        nf = len(p.piece.F)
        face_part += [part_ids[p.name]] * nf
        face_cls += [cls_ids[p.cls]] * nf
    P = Piece.merge(pieces)
    V = P.V - np.asarray(pivot, float)[None]
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], [list(f) for f in P.F])
    nl = len(me.loops)
    uv = np.array([c for f in P.UV for c in f], dtype=np.float32).reshape(-1, 2)
    assert len(uv) == nl, (len(uv), nl, name)
    lp = me.uv_layers.new(name="UVParam")
    lp.data.foreach_set("uv", uv.ravel())
    la = me.uv_layers.new(name="UVMap")
    la.data.foreach_set("uv", uv.ravel())
    me.uv_layers.active = la
    la.active_render = True
    me.polygons.foreach_set("use_smooth", np.array(P.smooth, bool))
    for nm, vals in (("fr_part", face_part), ("fr_cls", face_cls), ("fr_isl", P.isl), ("fr_flag", P.flag)):
        at = me.attributes.new(nm, "INT", "FACE")
        at.data.foreach_set("value", np.array(vals, np.int32))
    me.validate(clean_customdata=False)
    me.update()
    obj = bpy.data.objects.new(name, me)
    core.link(obj, col)
    obj["fr_uv_modes"] = json.dumps(sorted(set(p.piece.uv_mode for p in parts)))
    return obj


def face_attr(me, nm):
    a = np.empty(len(me.polygons), np.int32)
    me.attributes[nm].data.foreach_get("value", a)
    return a


def uv_array(me, layer):
    a = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[layer].data.foreach_get("uv", a)
    return a.reshape(-1, 2)


def set_uv_array(me, layer, arr):
    me.uv_layers[layer].data.foreach_set("uv", np.asarray(arr, np.float32).ravel())


def smart_param_uv(obj, angle=60.0):
    """For 'smart' parts: smart-project then rescale UVParam/UVMap to metres (UV area = 3D area)."""
    me = obj.data
    core.select_only([obj])
    me.uv_layers.active = me.uv_layers["UVMap"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = uv_array(me, "UVMap").astype(np.float64)
    a3, auv = 0.0, 0.0
    me.calc_loop_triangles()
    co = np.array([v.co[:] for v in me.vertices])
    for lt in me.loop_triangles:
        a, b, c = (co[i] for i in lt.vertices)
        a3 += 0.5 * np.linalg.norm(np.cross(b - a, c - a))
        ua, ub, uc = (uv[i] for i in lt.loops)
        auv += 0.5 * abs((ub[0] - ua[0]) * (uc[1] - ua[1]) - (ub[1] - ua[1]) * (uc[0] - ua[0]))
    s = math.sqrt(a3 / max(auv, 1e-12))
    uv *= s
    set_uv_array(me, "UVMap", uv)
    set_uv_array(me, "UVParam", uv)


def decimate_obj(obj, ratio):
    if ratio >= 0.999:
        return obj
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    core.select_only([obj])
    bpy.ops.object.modifier_apply(modifier="dec")
    return obj


def organic_piece(V, F, target_tris, lod_ratios=(1.0, 0.5, 0.22), smooth=True, name="org"):
    """Marching-cubes style mesh -> decimated Pieces for 3 LODs with smart UVs in metres.

    Returns [piece_lod0, piece_lod1, piece_lod2] with consistent UVParam (decimation keeps UVs).
    """
    p = mesh_piece(V, F, smooth)
    tmp_parts = [Part("org", "org", p)]
    obj = build_object(f"__tmp_{name}", tmp_parts, {"org": 0}, {"org": 0})
    cur = core.tri_count(obj)
    decimate_obj(obj, min(1.0, target_tris / max(cur, 1)))
    smart_param_uv(obj)
    out = []
    for r in lod_ratios:
        o2 = obj.copy()
        o2.data = obj.data.copy()
        core.link(o2)
        decimate_obj(o2, r)
        out.append(piece_from_object(o2, smooth))
        bpy.data.objects.remove(o2, do_unlink=True)
    bpy.data.objects.remove(obj, do_unlink=True)
    for q in out:
        q.uv_mode = "organic"
    return out


def piece_from_object(obj, smooth=True):
    me = obj.data
    V = np.array([v.co[:] for v in me.vertices])
    uv = uv_array(me, "UVParam")
    p = Piece(V)
    for poly in me.polygons:
        li = list(poly.loop_indices)
        p.add_face(tuple(poly.vertices), [tuple(uv[i]) for i in li], 0, smooth, 0)
    return p


# =============================================================================== asset compile

class Asset:
    """Holds the Blender objects of one asset: pivots, LOD meshes, markers, actions."""

    def __init__(self, asset_id, node_spec, col=None):
        """node_spec: {node: {"parent": None|node, "pivot": (x,y,z), "export_name": str}}"""
        self.id = asset_id
        self.spec = node_spec
        self.col = col
        self.pivots = {}
        self.meshes = {0: {}, 1: {}, 2: {}}
        self.markers = {}
        self.part_ids = {}
        self.part_meta = {}
        self.part_cls = {}
        self.cls_ids = {}
        self.actions = {}   # clip -> {pivot_name: action}
        self.clips = {}     # clip -> {"frames": n, "markers": {...}, "loop": bool}

    def pivot(self, node):
        return self.pivots.get(node)

    def world_pivot(self, node):
        return np.asarray(self.spec[node].get("pivot", (0, 0, 0)), float)

    def make_pivots(self):
        for node, sp in self.spec.items():
            if node == "root":
                continue
            e = bpy.data.objects.new(sp.get("export_name", node), None)
            e.empty_display_size = 0.15
            e.empty_display_type = "ARROWS"
            core.link(e, self.col)
            self.pivots[node] = e
        for node, sp in self.spec.items():
            if node == "root":
                continue
            e = self.pivots[node]
            par = sp.get("parent")
            wp = self.world_pivot(node)
            if par and par != "root":
                e.parent = self.pivots[par]
                e.location = tuple(wp - self.world_pivot(par))
            else:
                e.location = tuple(wp)
            e.rotation_mode = "XYZ"

    def mesh_name(self, node, lod):
        if node == "root":
            return f"{self.id}_LOD{lod}"
        ex = self.spec[node].get("export_name", node)
        return f"{ex}_LOD{lod}" if ex.startswith(self.id) else f"{self.id}_{ex}_LOD{lod}"

    def compile(self, build_fn):
        """build_fn(lod) -> Builder. Creates LOD0..2 objects; LOD1/2 UVs transferred from LOD0."""
        self.make_pivots()
        builders = [build_fn(l) for l in (0, 1, 2)]
        # ids from LOD0
        for node, parts in builders[0].nodes.items():
            for p in parts:
                if p.name not in self.part_ids:
                    self.part_ids[p.name] = len(self.part_ids)
                    self.part_meta[p.name] = p.meta
                    self.part_cls[p.name] = p.cls
                if p.cls not in self.cls_ids:
                    self.cls_ids[p.cls] = len(self.cls_ids)
        for lod, B in enumerate(builders):
            for node, parts in B.nodes.items():
                for p in parts:
                    if p.name not in self.part_ids:
                        raise KeyError(f"part {p.name} exists in LOD{lod} but not LOD0")
                obj = build_object(self.mesh_name(node, lod), parts, self.part_ids, self.cls_ids,
                                   self.world_pivot(node) if node != "root" else (0, 0, 0), self.col)
                if node != "root":
                    obj.parent = self.pivots[node]
                self.meshes[lod][node] = obj
                # density multipliers applied to the atlas UVs before packing (LOD0)
                if lod == 0:
                    me = obj.data
                    dens = {self.part_ids[p.name]: p.density for p in parts}
                    fp = face_attr(me, "fr_part")
                    uv = uv_array(me, "UVMap").astype(np.float64)
                    for poly in me.polygons:
                        d = dens.get(int(fp[poly.index]), 1.0)
                        if d != 1.0:
                            li = list(poly.loop_indices)
                            uv[li] *= d
                    set_uv_array(me, "UVMap", uv)
        return builders

    def lod0_objects(self):
        return [o for o in self.meshes[0].values()]

    def all_meshes(self):
        return [o for l in (0, 1, 2) for o in self.meshes[l].values()]


def pack_atlas(objs, margin=0.004, rotate=True, shape="CONCAVE"):
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    core.select_only(objs, objs[0])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=rotate, rotate_method="ANY", scale=True,
                            merge_overlap=False, margin_method="FRACTION", margin=margin, shape_method=shape)
    bpy.ops.object.mode_set(mode="OBJECT")


def island_affines(obj):
    """Least-squares affine param->atlas per (part, island) from a packed LOD0 object."""
    me = obj.data
    fp = face_attr(me, "fr_part")
    fi = face_attr(me, "fr_isl")
    up = uv_array(me, "UVParam").astype(np.float64)
    ua = uv_array(me, "UVMap").astype(np.float64)
    groups = {}
    for poly in me.polygons:
        key = (int(fp[poly.index]), int(fi[poly.index]))
        groups.setdefault(key, []).extend(poly.loop_indices)
    aff = {}
    for key, li in groups.items():
        li = np.array(sorted(set(li)))
        A = np.c_[up[li], np.ones(len(li))]
        X, *_ = np.linalg.lstsq(A, ua[li], rcond=None)
        aff[key] = X  # (3,2)
    return aff


def transfer_atlas_uv(asset):
    """Map LOD1/LOD2 parametric UVs into the LOD0 atlas (per part/island affine)."""
    aff = {}
    for o in asset.meshes[0].values():
        aff.update(island_affines(o))
    worst = 0.0
    for lod in (1, 2):
        for node, obj in asset.meshes[lod].items():
            me = obj.data
            fp = face_attr(me, "fr_part")
            fi = face_attr(me, "fr_isl")
            up = uv_array(me, "UVParam").astype(np.float64)
            ua = np.zeros_like(up)
            for poly in me.polygons:
                key = (int(fp[poly.index]), int(fi[poly.index]))
                X = aff.get(key)
                if X is None:  # island missing in LOD0: use any island of the same part
                    cands = [v for k, v in aff.items() if k[0] == key[0]]
                    X = cands[0] if cands else np.array([[0, 0], [0, 0], [0.999, 0.999]])
                li = list(poly.loop_indices)
                ua[li] = np.c_[up[li], np.ones(len(li))] @ X
            worst = max(worst, float(np.abs(np.clip(ua, 0, 1) - ua).max()) if len(ua) else 0.0)
            set_uv_array(me, "UVMap", np.clip(ua, 0.0005, 0.9995))
    return worst


# =============================================================================== texel sampling

class Texels:
    pass


def gather_triangles(objs):
    """Concatenate loop triangles of objects (world rest pose) with attributes."""
    P, N, UA, UP, part, cls, isl, flag, owner = [], [], [], [], [], [], [], [], []
    for oi, obj in enumerate(objs):
        me = obj.data
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if nt == 0:
            continue
        loops = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get("loops", loops)
        vidx = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", vidx)
        pidx = np.empty(nt, np.int64)
        me.loop_triangles.foreach_get("polygon_index", pidx)
        sn = np.empty(nt * 9, np.float64)
        me.loop_triangles.foreach_get("split_normals", sn)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(obj.matrix_world)
        pw = co[vidx] @ M[:3, :3].T + M[:3, 3]
        nw = sn.reshape(-1, 3) @ np.linalg.inv(M[:3, :3])
        nw = unit(nw)
        P.append(pw.reshape(nt, 3, 3))
        N.append(nw.reshape(nt, 3, 3))
        UA.append(uv_array(me, "UVMap")[loops].reshape(nt, 3, 2))
        UP.append(uv_array(me, "UVParam")[loops].reshape(nt, 3, 2))
        for nm, dst in (("fr_part", part), ("fr_cls", cls), ("fr_isl", isl), ("fr_flag", flag)):
            dst.append(face_attr(me, nm)[pidx])
        owner.append(np.full(nt, oi))
    cat = lambda L: np.concatenate(L, 0)
    return dict(P=cat(P), N=cat(N), UA=cat(UA), UP=cat(UP), part=cat(part), cls=cat(cls), isl=cat(isl),
                flag=cat(flag), owner=cat(owner))


def rasterize(tri, size):
    """Rasterise atlas triangles -> Texels with world pos/normal/param-uv/attributes per texel."""
    nt = len(tri["P"])
    verts = tri["P"].reshape(-1, 3)
    tris = np.arange(nt * 3).reshape(nt, 3)
    T = texproj.rasterize_uv(verts, tris, tri["UA"], size, tri["N"].reshape(-1, 3))
    tx = Texels()
    tx.size = T.size
    tx.valid = T.valid
    yy, xx = np.nonzero(T.valid)
    tx.yy, tx.xx = yy, xx
    t = T.tri[yy, xx]
    b = T.bary[yy, xx]
    tx.t = t
    tx.P = T.pos[yy, xx]
    tx.N = T.nrm[yy, xx]
    tx.UV = (tri["UP"][t] * b[..., None]).sum(1)
    for k in ("part", "cls", "isl", "flag", "owner"):
        setattr(tx, k, tri[k][t])
    return tx


# =============================================================================== noise helpers

def fbm2(x, y, freq=1.0, octaves=4, seed=0):
    P = np.stack([x, y, np.full_like(x, 0.37 * seed + 1.3)], -1)
    return texproj.fbm(P, freq, octaves, seed=seed)


def fbm3(P, freq=1.0, octaves=4, seed=0):
    return texproj.fbm(P, freq, octaves, seed=seed)


def hash1(i, seed=0):
    i = np.asarray(i, np.int64)
    return texproj._hash3(i, i * 7 + 3, i * 13 + 5, seed)


def srgb(c):
    return np.asarray(c, float) / (255.0 if np.max(c) > 1.5 else 1.0)


def mix(a, b, t):
    t = np.asarray(t, float)
    if t.ndim == 1 and np.ndim(a) and np.asarray(a).ndim == 2:
        t = t[:, None]
    return a * (1 - t) + b * t


# =============================================================================== texture synthesis

def synthesize(asset, shaders, size=2048, part_overrides=None, log=print):
    """Evaluate class shaders on every texel of the LOD0 atlas.

    shaders: {cls_name: fn(ctx) -> dict(albedo (n,3), rough (n), metal (n), height (n) metres)}
    Returns dict of full-size images (H,W,...) and the texel object.
    """
    t0 = time.time()
    objs = asset.lod0_objects()
    tri = gather_triangles(objs)
    tx = rasterize(tri, size)
    W, H = tx.size
    n = len(tx.yy)
    albedo = np.zeros((n, 3))
    rough = np.full(n, 0.8)
    metal = np.zeros(n)
    height = np.zeros(n)
    inv_cls = {v: k for k, v in asset.cls_ids.items()}
    inv_part = {v: k for k, v in asset.part_ids.items()}
    for cid in np.unique(tx.cls):
        name = inv_cls[int(cid)]
        sel = tx.cls == cid
        ctx = Ctx(tx, sel, asset, inv_part)
        res = shaders[name](ctx)
        albedo[sel] = res["albedo"]
        rough[sel] = res.get("rough", 0.8)
        metal[sel] = res.get("metal", 0.0)
        height[sel] = res.get("height", 0.0)
    img = lambda vals, ch: _to_img(tx, vals, W, H, ch)
    out = {"albedo": img(albedo, 3), "rough": img(rough, 1)[..., 0], "metal": img(metal, 1)[..., 0],
           "height": img(height, 1)[..., 0], "valid": tx.valid}
    # metres per texel (uniform atlas density)
    a3 = 0.0
    auv = 0.0
    Pt, Ut = tri["P"], tri["UA"]
    a3 = 0.5 * np.linalg.norm(np.cross(Pt[:, 1] - Pt[:, 0], Pt[:, 2] - Pt[:, 0]), axis=1).sum()
    auv = 0.5 * np.abs((Ut[:, 1, 0] - Ut[:, 0, 0]) * (Ut[:, 2, 1] - Ut[:, 0, 1])
                       - (Ut[:, 1, 1] - Ut[:, 0, 1]) * (Ut[:, 2, 0] - Ut[:, 0, 0])).sum()
    out["texel_m"] = math.sqrt(a3 / max(auv, 1e-12)) / W
    log(f"[propkit] synthesized {n} texels ({W}x{H}) in {time.time() - t0:.1f}s, texel {out['texel_m'] * 1000:.2f} mm")
    return out, tx


def _to_img(tx, vals, W, H, ch):
    im = np.zeros((H, W, ch))
    v = np.asarray(vals, float).reshape(len(tx.yy), -1)
    im[tx.yy, tx.xx] = v
    return im


class Ctx:
    """Texel subset for one material class."""

    def __init__(self, tx, sel, asset, inv_part):
        self.sel = sel
        self.P = tx.P[sel]
        self.N = tx.N[sel]
        self.UV = tx.UV[sel]
        self.u = self.UV[:, 0]
        self.v = self.UV[:, 1]
        self.part = tx.part[sel]
        self.isl = tx.isl[sel]
        self.flag = tx.flag[sel]
        self.n = int(sel.sum())
        self.asset = asset
        self.inv_part = inv_part
        self.seed = hash1(self.part, 11)
        self.seed2 = hash1(self.part, 23)

    def part_names(self):
        return [self.inv_part[int(p)] for p in self.part]

    def meta_mask(self, key):
        """Boolean mask of texels whose part meta has key truthy."""
        ids = [pid for name, pid in self.asset.part_ids.items() if self.asset.part_meta.get(name, {}).get(key)]
        return np.isin(self.part, ids)

    def meta_value(self, key, default=0.0):
        out = np.full(self.n, default, dtype=float)
        for name, pid in self.asset.part_ids.items():
            v = self.asset.part_meta.get(name, {}).get(key)
            if v is not None and not callable(v):
                out[self.part == pid] = v
        return out

    def by_part(self, key):
        """Yield (mask, meta_value) for parts that define meta[key]."""
        for name, pid in self.asset.part_ids.items():
            v = self.asset.part_meta.get(name, {}).get(key)
            if v is not None:
                m = self.part == pid
                if m.any():
                    yield m, v


def cavity_from_height(h, valid, texel_m, radius_m, depth_m):
    from scipy import ndimage as ndi
    hp = texproj.fill(h[..., None], valid)[..., 0]
    r_px = max(1.0, radius_m / texel_m)
    blur = ndi.gaussian_filter(hp, r_px)
    return 1.0 - np.clip((blur - hp) / depth_m, 0, 1)


def finalize_textures(asset, tex, ao=None, ao_strength=0.7, out_dir=None, sizes=None, log=print, cavity=None,
                      normal_strength=1.0):
    """Pad, add AO (+ cavity from the height map), build normal map; write masters + runtime images.

    cavity: (radius_m, depth_m, strength) darkens engraved recesses in the albedo (mobile has no SSAO).
    """
    sizes = sizes or {"base": 2048, "orm": 1024, "normal": 1024}
    valid = tex["valid"]
    H, W = valid.shape
    alb = tex["albedo"].copy()
    if ao is not None:
        a = ao if ao.shape[:2] == (H, W) else _resize(ao, W, H)
        alb = alb * (1 - ao_strength + ao_strength * a[..., None])
    if cavity is not None:
        cv_ = cavity_from_height(tex["height"], valid, tex["texel_m"], cavity[0], cavity[1])
        alb = alb * (1 - cavity[2] + cavity[2] * cv_[..., None])
        tex["cavity"] = cv_
    alb = texproj.dilate_margin(alb, valid, 12)
    rough = texproj.dilate_margin(tex["rough"][..., None], valid, 12)[..., 0]
    metal = texproj.dilate_margin(tex["metal"][..., None], valid, 12)[..., 0]
    h = tex["height"]
    nrm = texproj.height_to_normal(h, valid, strength=normal_strength, texel_m=tex["texel_m"])
    nrm = texproj.dilate_margin(nrm, valid, 12)
    # fill empty atlas space with neutral values
    far = ~valid & ~(np.abs(nrm - 0.5).sum(2) > 0)
    nrm[far] = (0.5, 0.5, 1.0)
    orm = np.stack([np.ones_like(rough), rough, metal], -1)
    out_dir = out_dir or paths.ensure(paths.TEXTURE_SOURCES, GROUP)
    core.save_rgba(os.path.join(out_dir, f"{asset.id}_base_master.png"), np.clip(alb, 0, 1))
    core.save_rgba(os.path.join(out_dir, f"{asset.id}_orm_master.png"), np.clip(orm, 0, 1))
    core.save_rgba(os.path.join(out_dir, f"{asset.id}_normal_master.png"), np.clip(nrm, 0, 1))
    if ao is not None:
        core.save_rgba(os.path.join(out_dir, f"{asset.id}_ao_master.png"),
                       np.repeat(np.clip(ao, 0, 1)[..., None], 3, 2))
    rt = paths.ensure(paths.SOURCES, GROUP, "tex")
    from PIL import Image
    files = {}
    for key, arr, fmt, cs in (("base", alb, "JPEG", "sRGB"), ("orm", orm, "JPEG", "Non-Color"),
                              ("normal", nrm, "PNG", "Non-Color")):
        s = sizes[key]
        a = _resize(arr, s, s) if arr.shape[0] != s else arr
        u8 = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
        ext = "jpg" if fmt == "JPEG" else "png"
        fp = os.path.join(rt, f"{asset.id}_{key}.{ext}")
        im = Image.fromarray(u8, "RGB")
        if fmt == "JPEG":
            im.save(fp, quality=90, optimize=True)
        else:
            im.save(fp, optimize=True)
        img = bpy.data.images.load(fp, check_existing=False)
        img.name = f"{asset.id}_{key}"
        img.colorspace_settings.name = cs
        files[key] = img
    log(f"[propkit] textures written ({sizes})")
    return files


def _resize(a, w, h):
    import cv2
    return cv2.resize(np.asarray(a, np.float32), (w, h), interpolation=cv2.INTER_AREA)


def make_material(asset, imgs):
    mat = core.material(f"{asset.id}_mat", base_tex=imgs["base"], rough_tex=imgs["orm"], metal_tex=imgs["orm"],
                        normal_tex=imgs["normal"], normal_strength=1.0, uv_map="UVMap")
    for o in asset.all_meshes():
        core.assign(o, mat)
    return mat


# =============================================================================== AO bake (Cycles)

def bake_ao(asset, size=1024, samples=24, distance=0.35, hide_for_static=(), isolate=()):
    """Bake ambient occlusion of the LOD0 atlas. Static root is baked with `hide_for_static`
    nodes hidden (so an opened door leaves no phantom shadow)."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake_world")
    scene.world.light_settings.distance = distance
    img = bpy.data.images.new(f"{asset.id}_ao_bake", size, size, alpha=False, float_buffer=True)
    img.generated_color = (1, 1, 1, 1)
    lod0 = asset.lod0_objects()
    others = [o for l in (1, 2) for o in asset.meshes[l].values()]
    for o in others:
        o.hide_render = True
    tmpmat = bpy.data.materials.new("__ao_tmp")
    tmpmat.use_nodes = True
    nt = tmpmat.node_tree
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.nodes.active = node
    saved = {}
    for o in lod0:
        saved[o.name] = list(o.data.materials)
        o.data.materials.clear()
        o.data.materials.append(tmpmat)
    scene.render.bake.margin = 6
    scene.render.bake.margin_type = "EXTEND"
    first = True
    for node_name, o in asset.meshes[0].items():
        hidden = []
        if node_name in isolate or "*" in isolate:
            for n2, oo in asset.meshes[0].items():
                if oo is not o and not oo.hide_render:
                    oo.hide_render = True
                    hidden.append(oo)
        if node_name == "root":
            for hn in hide_for_static:
                for oo in [asset.meshes[0].get(hn)] + _descendant_meshes(asset, hn):
                    if oo is not None and not oo.hide_render:
                        oo.hide_render = True
                        hidden.append(oo)
        scene.render.bake.use_clear = first
        core.select_only([o], o)
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
        bpy.ops.object.bake(type="AO", margin=6, use_clear=first)
        first = False
        for oo in hidden:
            oo.hide_render = False
    for o in lod0:
        o.data.materials.clear()
        for m in saved[o.name]:
            o.data.materials.append(m)
    for o in others:
        o.hide_render = False
    bpy.data.materials.remove(tmpmat)
    ao = core.image_to_numpy(img)[..., 0].astype(np.float64)
    return np.clip(ao, 0, 1)


def _descendant_meshes(asset, node):
    out = []
    for n, sp in asset.spec.items():
        p = sp.get("parent")
        while p:
            if p == node:
                out.append(asset.meshes[0].get(n))
                break
            p = asset.spec.get(p, {}).get("parent")
    return [o for o in out if o is not None]


# =============================================================================== markers & animation

def marker(asset, name, world_pos, parent_node=None, size=0.06):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "SPHERE"
    e.empty_display_size = size
    core.link(e, asset.col)
    wp = np.asarray(world_pos, float)
    if parent_node and parent_node != "root":
        e.parent = asset.pivots[parent_node]
        e.location = tuple(wp - asset.world_pivot(parent_node))
    else:
        e.location = tuple(wp)
    asset.markers[name] = (e, parent_node, wp)
    return e


def add_clip(asset, clip, tracks, frames, markers=None, loop=False):
    """tracks: {node: fn(frame) -> dict(loc=(x,y,z) local offset from rest, rot=(rx,ry,rz) radians,
    scale=(sx,sy,sz))}; values are absolute local transforms relative to the pivot's rest location."""
    asset.clips[clip] = {"frames": frames, "markers": markers or {}, "loop": loop}
    asset.actions.setdefault(clip, {})
    for node, fn in tracks.items():
        obj = asset.pivots[node]
        rest_loc = np.array(obj.location[:]) if "rest_loc" not in obj else np.array(obj["rest_loc"])
        if "rest_loc" not in obj:
            obj["rest_loc"] = list(rest_loc)
        if obj.animation_data is None:
            obj.animation_data_create()
        act = bpy.data.actions.new(f"{clip}|{node}")
        act.use_fake_user = True
        obj.animation_data.action = act
        for f in range(frames + 1):
            v = fn(f)
            obj.location = tuple(rest_loc + np.asarray(v.get("loc", (0, 0, 0)), float))
            obj.rotation_euler = tuple(v.get("rot", (0, 0, 0)))
            obj.scale = tuple(v.get("scale", (1, 1, 1)))
            obj.keyframe_insert("location", frame=f)
            obj.keyframe_insert("rotation_euler", frame=f)
            obj.keyframe_insert("scale", frame=f)
        for fc in _fcurves(act):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        act.use_frame_range = True
        act.frame_start = 0
        act.frame_end = frames
        obj.animation_data.action = None
        tr = obj.animation_data.nla_tracks.new()
        tr.name = clip
        st = tr.strips.new(clip, 0, act)
        st.extrapolation = "NOTHING"      # no influence outside the clip -> rest pose exports as the node TRS
        tr.mute = False
        asset.actions[clip][node] = act
        obj.location = tuple(rest_loc)
        obj.rotation_euler = (0, 0, 0)
        obj.scale = (1, 1, 1)


def _fcurves(act):
    try:
        return list(act.fcurves)
    except AttributeError:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out += list(cb.fcurves)
        return out


def pose_clip(asset, clip, frame):
    """Evaluate clip at frame on the pivots (for preview renders; NLA tracks are muted)."""
    for node, obj in asset.pivots.items():
        if obj.animation_data:
            for tr in obj.animation_data.nla_tracks:
                tr.mute = True
            obj.animation_data.action = None
    for node, act in asset.actions.get(clip, {}).items():
        obj = asset.pivots[node]
        obj.animation_data.action = act
    bpy.context.scene.frame_set(int(frame))


def rest_pose(asset):
    for node, obj in asset.pivots.items():
        if obj.animation_data:
            obj.animation_data.action = None
            for tr in obj.animation_data.nla_tracks:
                tr.mute = False
        if "rest_loc" in obj:
            obj.location = tuple(obj["rest_loc"])
        obj.rotation_euler = tuple(obj.get("rest_rot", (0, 0, 0)))
        obj.scale = tuple(obj.get("rest_scale", (1, 1, 1)))
    bpy.context.scene.frame_set(0)


def set_static_pose(asset, poses):
    """poses: {node: dict(loc, rot, scale)} relative to rest (for comparison renders)."""
    for node, obj in asset.pivots.items():
        if obj.animation_data:
            obj.animation_data.action = None
            for tr in obj.animation_data.nla_tracks:
                tr.mute = True
    for node, v in poses.items():
        obj = asset.pivots[node]
        rl = np.array(obj["rest_loc"]) if "rest_loc" in obj else np.array(obj.location[:])
        if "rest_loc" not in obj:
            obj["rest_loc"] = list(rl)
        obj.location = tuple(rl + np.asarray(v.get("loc", (0, 0, 0)), float))
        obj.rotation_euler = tuple(v.get("rot", (0, 0, 0)))
        obj.scale = tuple(v.get("scale", (1, 1, 1)))
    bpy.context.view_layer.update()


# =============================================================================== export & meta

def b2g(p):
    """Blender (x, y, z) -> glTF/Godot (x, z, -y)."""
    p = np.asarray(p, float)
    return [round(float(p[0]), 4), round(float(p[2]), 4), round(float(-p[1]), 4)]


def export(asset, glb_path, extra_objects=()):
    rest_pose(asset)
    for node, obj in asset.pivots.items():
        if obj.animation_data:
            obj.animation_data.action = None
            for tr in obj.animation_data.nla_tracks:
                tr.mute = False
    objs = list(asset.pivots.values()) + asset.all_meshes() + [m[0] for m in asset.markers.values()] + list(extra_objects)
    # game GLB must carry the atlas UV as TEXCOORD_0 (Godot ignores texCoord 1): drop the parametric UV layer
    for o in asset.all_meshes():
        uvl = o.data.uv_layers
        if "UVParam" in uvl:
            uvl.remove(uvl["UVParam"])
        if "UVMap" in uvl:
            uvl.active = uvl["UVMap"]
            uvl["UVMap"].active_render = True
    bpy.context.preferences.edit.use_negative_frames = True
    bpy.context.scene.frame_set(-10)          # outside every NLA strip -> nodes evaluate at rest
    core.export_glb(glb_path, objs, extra={"export_animation_mode": "NLA_TRACKS", "export_optimize_animation_size": False,
                                           "export_def_bones": False, "export_skins": False,
                                           "export_current_frame": True, "export_optimize_animation_keep_anim_object": True})
    bpy.context.scene.frame_set(0)
    return glb_path


def tri_stats(asset):
    out = {}
    for lod in (0, 1, 2):
        per = {}
        for node, obj in asset.meshes[lod].items():
            per[node] = core.tri_count(obj)
        out[f"LOD{lod}"] = {"total": int(sum(per.values())), "by_node": per}
    return out


def glb_summary(glb_path):
    import struct
    data = open(glb_path, "rb").read()
    ln = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + ln])
    nodes = [n.get("name") for n in js.get("nodes", [])]
    anims = {}
    for a in js.get("animations", []):
        chans = [(js["nodes"][c["target"]["node"]]["name"], c["target"]["path"]) for c in a["channels"]]
        mx = 0.0
        for s in a["samplers"]:
            acc = js["accessors"][s["input"]]
            mx = max(mx, float(acc.get("max", [0])[0]))
        anims[a["name"]] = {"seconds": round(mx, 4), "channels": chans}
    imgs = [(im.get("name"), im.get("mimeType")) for im in js.get("images", [])]
    return {"nodes": nodes, "animations": anims, "images": imgs, "bytes": len(data)}


# =============================================================================== camera fitting & silhouettes

def project_points(X, cam):
    """cam = dict(R (3x3 world->cam, OpenCV), t (3,), f, cx, cy)."""
    Xc = X @ cam["R"].T + cam["t"]
    z = np.maximum(Xc[:, 2], 1e-6)
    u = cam["f"] * Xc[:, 0] / z + cam["cx"]
    v = cam["f"] * Xc[:, 1] / z + cam["cy"]
    return np.stack([u, v], 1), Xc[:, 2]


def cam_from_params(x, W, H):
    """x = (yaw, pitch, roll, dist, f_scale, tx_px, ty_px, tgt_x, tgt_y, tgt_z)."""
    yaw, pitch, roll, dist, fs, sx, sy = x[:7]
    tgt = np.asarray(x[7:10], float)
    # camera position on a sphere around target; yaw 0 = camera at -Y looking +Y
    d = np.array([math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)])
    C = tgt + d * dist
    fwd = unit(tgt - C)
    right = unit(np.cross(fwd, [0, 0, 1]))
    up = np.cross(right, fwd)
    # roll around fwd
    cr, sr = math.cos(roll), math.sin(roll)
    right, up = cr * right + sr * up, -sr * right + cr * up
    R = np.stack([right, -up, fwd], 0)  # OpenCV: x right, y down, z forward
    t = -R @ C
    f = fs * max(W, H)
    return {"R": R, "t": t, "f": f, "cx": W / 2 + sx, "cy": H / 2 + sy, "C": C, "W": W, "H": H}


def silhouette_mask(tris_world, cam, W, H):
    import cv2
    pts, z = project_points(tris_world.reshape(-1, 3), cam)
    pts = pts.reshape(-1, 3, 2)
    m = np.zeros((H, W), np.uint8)
    poly = np.round(pts * 16).astype(np.int32)
    cv2.fillPoly(m, list(poly), 1, lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)


def world_triangles(objs):
    out = []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != "MESH" or o.hide_render:
            continue
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        vi = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", vi)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ev.matrix_world)
        out.append((co[vi] @ M[:3, :3].T + M[:3, 3]).reshape(nt, 3, 3))
        ev.to_mesh_clear()
    return np.concatenate(out, 0)


def fit_camera_points(P3, p2, W, H, x0, fixed=(2,), log=print):
    """Least-squares camera from 3-D landmarks (Blender) and their drawing pixels (crop coords)."""
    from scipy.optimize import least_squares
    P3 = np.asarray(P3, float)
    p2 = np.asarray(p2, float)
    x0 = np.asarray(x0, float)
    free = [i for i in range(len(x0)) if i not in fixed]

    def res(z):
        x = x0.copy()
        x[free] = z
        uv, _ = project_points(P3, cam_from_params(x, W, H))
        return (uv - p2).ravel()
    r = least_squares(res, x0[free], method="lm", max_nfev=4000)
    x = x0.copy()
    x[free] = r.x
    e = np.linalg.norm(res(r.x).reshape(-1, 2), axis=1)
    log(f"[propkit] landmark camera: mean err {e.mean():.1f}px max {e.max():.1f}px; per point {np.round(e, 1).tolist()}")
    return x, e


def landmark_errors(x, P3, p2, W, H):
    uv, _ = project_points(np.asarray(P3, float), cam_from_params(x, W, H))
    return uv - np.asarray(p2, float)


def fit_camera(tris, ref_mask, x0, fixed=(), bounds=None, fill=True, iters=2, log=print, landmarks=None, lam=0.0):
    """Optimise camera params to maximise silhouette IoU against a reference mask
    (optionally + lam * mean landmark reprojection error in pixels)."""
    from scipy import ndimage as ndi
    from scipy.optimize import minimize
    H, W = ref_mask.shape
    ref = ndi.binary_fill_holes(ref_mask) if fill else ref_mask
    x0 = np.asarray(x0, float)
    free = [i for i in range(len(x0)) if i not in fixed]
    d0 = x0[3]
    scales = np.array([0.02, 0.02, 0.01, 0.05 * d0, 0.02, 5, 5, 0.02 * d0, 0.02 * d0, 0.02 * d0])

    def score(xf):
        x = x0.copy()
        x[free] = xf
        cam = cam_from_params(x, W, H)
        m = silhouette_mask(tris, cam, W, H)
        if fill:
            m = ndi.binary_fill_holes(m)
        inter = np.logical_and(m, ref).sum()
        uni = np.logical_or(m, ref).sum()
        pen = 0.0
        if landmarks is not None and lam > 0:
            uv, _ = project_points(np.asarray(landmarks[0], float), cam)
            pen = lam * float(np.linalg.norm(uv - np.asarray(landmarks[1], float), axis=1).mean())
        return 1.0 - inter / max(uni, 1) + pen

    best = x0[free].copy()
    for it in range(iters):
        res = minimize(lambda z: score(best + z * scales[free]), np.zeros(len(free)), method="Powell",
                       options={"maxiter": 4000, "xtol": 1e-3, "ftol": 1e-5})
        best = best + res.x * scales[free]
    x = x0.copy()
    x[free] = best
    sc = score(best)
    if landmarks is not None and lam > 0:
        uv, _ = project_points(np.asarray(landmarks[0], float), cam_from_params(x, W, H))
        sc -= lam * float(np.linalg.norm(uv - np.asarray(landmarks[1], float), axis=1).mean())
    log(f"[propkit] camera fit IoU(filled)={1 - sc:.4f}")
    return x, 1 - sc


def blender_camera(cam, name="fr_cam", clip_end=200.0):
    """Create/update a Blender perspective camera equal to an OpenCV-style camera dict."""
    W, H = cam["W"], cam["H"]
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.type = "PERSP"
    cd.sensor_fit = "HORIZONTAL" if W >= H else "VERTICAL"
    cd.sensor_width = 36.0
    cd.sensor_height = 36.0
    ref = W if W >= H else H
    cd.lens = cam["f"] / ref * 36.0
    cd.shift_x = -(cam["cx"] - W / 2) / ref
    cd.shift_y = (cam["cy"] - H / 2) / ref
    cd.clip_start = 0.02
    cd.clip_end = clip_end
    obj = bpy.data.objects.get(name) or core.link(bpy.data.objects.new(name, cd))
    R = cam["R"]
    rot = np.stack([R[0], -R[1], -R[2]], 0).T  # columns: cam x, cam y(up), cam z(back)
    M = np.eye(4)
    M[:3, :3] = rot
    M[:3, 3] = cam["C"]
    obj.matrix_world = Matrix(M.tolist())
    sc = bpy.context.scene
    sc.camera = obj
    sc.render.resolution_x = int(W)
    sc.render.resolution_y = int(H)
    sc.render.resolution_percentage = 100
    return obj


def studio(engine="CYCLES", samples=32, key=3.0, fill=1.0, rim=1.4, ambient=0.6, bg=(0.86, 0.82, 0.74)):
    from frlib import render
    sc = render.studio(bg=bg, engine=engine, samples=samples, key_energy=key, fill_energy=fill,
                       rim_energy=rim, ambient=ambient, transparent=True)
    if engine == "BLENDER_EEVEE":
        try:
            sc.eevee.use_shadows = True
        except AttributeError:
            pass
    return sc


def render_rgba(path):
    from frlib import render
    return render.render_rgba(path)


def label(img_u8, text, xy=(8, 6), scale=1):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.fromarray(img_u8)
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13 * scale)
    except Exception:
        font = None
    x, y = xy
    tw = dr.textlength(text, font=font) if font else 7 * len(text)
    dr.rectangle([x - 4, y - 3, x + tw + 6, y + 16 * scale], fill=(20, 20, 20))
    dr.text((x, y), text, fill=(255, 240, 200), font=font)
    return np.asarray(im)


def iou(a, b):
    i = np.logical_and(a, b).sum()
    u = np.logical_or(a, b).sum()
    return float(i) / max(float(u), 1.0)


def compare_panels(ref_rgb, rgba, ref_mask, out_png, title, bg=None, extra_text="", mask_fill=True):
    """[reference | render over reference bg | silhouette diff] + metrics json."""
    from scipy import ndimage as ndi
    H, W = ref_rgb.shape[:2]
    if rgba.shape[:2] != (H, W):
        rgba = _resize(rgba, W, H)
    bgc = np.median(ref_rgb[~ref_mask], axis=0) if bg is None else np.asarray(bg)
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + bgc[None, None] * (1 - a)
    rm = rgba[..., 3] > 0.5
    metrics = {"title": title}
    if ref_mask is not None:
        rf = ndi.binary_fill_holes(ref_mask) if mask_fill else ref_mask
        mf = ndi.binary_fill_holes(rm) if mask_fill else rm
        metrics["iou_filled"] = round(iou(rf, mf), 4)
        metrics["iou_raw"] = round(iou(ref_mask, rm), 4)
        both = ref_mask & rm
        metrics["mean_abs_colour_error"] = round(float(np.abs(comp[both] - ref_rgb[both]).mean()), 4) if both.any() else None
        if both.any():
            metrics["mean_rgb_ref"] = [round(float(x), 3) for x in ref_rgb[both].mean(0)]
            metrics["mean_rgb_render"] = [round(float(x), 3) for x in comp[both].mean(0)]
        diff = np.repeat(ref_rgb.mean(axis=2, keepdims=True) * 0.5 + 0.35, 3, axis=2)
        diff[rf & mf] = diff[rf & mf] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
        diff[rf & ~mf] = (0.85, 0.15, 0.15)
        diff[~rf & mf] = (0.15, 0.3, 0.9)
        panels = [(ref_rgb, "reference"), (comp, "render"), (diff, f"IoU filled {metrics['iou_filled']:.3f} raw {metrics['iou_raw']:.3f}")]
    else:
        panels = [(ref_rgb, "reference"), (comp, "render")]
    imgs = [label((np.clip(p, 0, 1) * 255).astype(np.uint8), t) for p, t in panels]
    sheet = np.concatenate(imgs, axis=1)
    top = np.full((28, sheet.shape[1], 3), 28, np.uint8)
    top = label(top, title + ("  " + extra_text if extra_text else ""))
    sheet = np.concatenate([top, sheet], 0)
    core.save_rgba(out_png, sheet / 255.0)
    core.write_json(out_png[:-4] + ".json", metrics)
    return metrics


def side_by_side(images, labels, out_png, height=480):
    import cv2
    panels = []
    for img, lab in zip(images, labels):
        img = np.asarray(img, float)
        if img.max() > 1.5:
            img = img / 255.0
        if img.ndim == 2:
            img = np.repeat(img[..., None], 3, 2)
        if img.shape[2] == 4:
            img = img[..., :3] * img[..., 3:4] + 0.86 * (1 - img[..., 3:4])
        s = height / img.shape[0]
        img = cv2.resize(img.astype(np.float32), (max(1, int(img.shape[1] * s)), height), interpolation=cv2.INTER_AREA)
        panels.append(label((np.clip(img, 0, 1) * 255).astype(np.uint8), lab))
    core.save_rgba(out_png, np.concatenate(panels, axis=1) / 255.0)
    return out_png


def ref_crop(image_name, box):
    from PIL import Image
    im = Image.open(paths.art(image_name)).convert("RGB")
    return np.asarray(im.crop(box), dtype=np.float64) / 255.0


def render_clip_frames(asset, clip, out_mp4, cam_obj=None, res=(960, 540), engine="BLENDER_EEVEE", samples=16,
                       hold=0):
    """Render a node-animation clip to MP4 (H.264, 30 fps)."""
    import shutil
    import tempfile
    sc = bpy.context.scene
    sc.render.engine = engine
    if engine == "BLENDER_EEVEE":
        sc.eevee.taa_render_samples = samples
    else:
        sc.cycles.samples = samples
    sc.render.film_transparent = False
    if cam_obj is not None:
        sc.camera = cam_obj
    sc.render.resolution_x, sc.render.resolution_y = res
    tmp = tempfile.mkdtemp()
    n = asset.clips[clip]["frames"]
    k = 0
    for f in list(range(n + 1)) + [n] * hold:
        pose_clip(asset, clip, f)
        sc.render.filepath = os.path.join(tmp, f"f{k:05d}.png")
        sc.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
        k += 1
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out_mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    rest_pose(asset)
    return out_mp4


def godot_shots(glb, out_dir, extra=()):
    tool = os.path.join(paths.FR_DIR, "tools", "godot_view.sh")
    cmd = ["bash", tool, glb, "shots", out_dir, "all", "6"] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout + r.stderr


def godot_clip(glb, out_mp4, anim="all", seconds=6, extra=()):
    tool = os.path.join(paths.FR_DIR, "tools", "godot_view.sh")
    cmd = ["bash", tool, glb, "clip", out_mp4, anim, str(seconds)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout + r.stderr


# =============================================================================== rounded extrusion with grid cap

def _point_in_poly(pts, poly):
    import cv2
    c = poly.astype(np.float32).reshape(-1, 1, 2)
    return np.array([cv2.pointPolygonTest(c, (float(x), float(y)), False) > 0 for x, y in pts])


def grid_cap(poly, spacing, z=0.0, up=True, dome=None, isl=2):
    """Planar cap of a CCW polygon with interior grid points (Delaunay) for displacement/doming."""
    from scipy.spatial import Delaunay
    poly = ccw(np.asarray(poly, float))
    lo, hi = poly.min(0), poly.max(0)
    gx = np.arange(lo[0] + spacing * 0.5, hi[0], spacing)
    gy = np.arange(lo[1] + spacing * 0.5, hi[1], spacing)
    G = np.array([(x, y + (0.5 * spacing if (i % 2) else 0)) for i, x in enumerate(gx) for y in gy]) if len(gx) and len(gy) else np.zeros((0, 2))
    if len(G):
        inside = _point_in_poly(G, offset_poly(poly, -spacing * 0.45))
        G = G[inside]
    pts = np.vstack([poly, G]) if len(G) else poly
    tri = Delaunay(pts).simplices
    cen = pts[tri].mean(1)
    keep = _point_in_poly(cen, poly)
    tri = tri[keep]
    zz = np.full(len(pts), z, float)
    if dome is not None:
        zz = zz + dome(pts)
    p = Piece()
    b = p.append_verts(np.c_[pts, zz])
    for t in tri:
        a, bb, c = pts[t[0]], pts[t[1]], pts[t[2]]
        cr = (bb[0] - a[0]) * (c[1] - a[1]) - (bb[1] - a[1]) * (c[0] - a[0])
        tt = list(t) if (cr > 0) == up else [t[0], t[2], t[1]]
        p.add_face(tuple(b + i for i in tt), [tuple(pts[i]) for i in tt], isl, False, 0)
    return p


def extrude_round(outline, depth, r_front=0.004, r_back=0.003, seg=3, cap_spacing=None, dome=None,
                  smooth=True):
    """Prism with quarter-round front/back rims (pillow tokens). Front cap at z=depth (+dome), back at z=0.

    Sides: u = perimeter, v = z (metres). Caps: planar (x, y), island 2 = front, 1 = back.
    """
    outline = ccw(np.asarray(outline, float))
    k = len(outline)
    pe = np.linalg.norm(np.roll(outline, -1, axis=0) - outline, axis=1)
    pc = np.concatenate([[0], np.cumsum(pe)])
    layers = []
    for j in range(seg + 1):                       # back rounding: inset r(1-sin)
        th = (math.pi / 2) * j / seg
        layers.append((r_back * (1 - math.sin(th)), r_back * (1 - math.cos(th))))
    for j in range(seg + 1):                       # front rounding
        th = (math.pi / 2) * j / seg
        layers.append((r_front * (1 - math.cos(th)), depth - r_front + r_front * math.sin(th)))
    rings = []
    piece = Piece()
    for inset, z in layers:
        pts = offset_poly(outline, -inset) if inset > 1e-7 else outline
        rings.append((piece.append_verts(np.c_[pts, np.full(k, z)]), z, pts))
    vacc = 0.0
    vs = [0.0]
    for i in range(1, len(layers)):
        d = math.hypot(layers[i][0] - layers[i - 1][0], layers[i][1] - layers[i - 1][1])
        vacc += d
        vs.append(vacc)
    for li in range(len(layers) - 1):
        r0, z0, _ = rings[li]
        r1, z1, _ = rings[li + 1]
        if abs(vs[li + 1] - vs[li]) < 1e-9:
            continue
        flag = 0 if (li == seg) else 1
        for j in range(k):
            j1 = (j + 1) % k
            piece.add_face((r0 + j, r0 + j1, r1 + j1, r1 + j),
                           [(pc[j], vs[li]), (pc[j + 1], vs[li]), (pc[j + 1], vs[li + 1]), (pc[j], vs[li + 1])],
                           0, smooth, flag)
    back = rings[0][2]
    front = rings[-1][2]
    if cap_spacing:
        fc = grid_cap(front, cap_spacing, z=depth, up=True, dome=dome, isl=2)
        bc = grid_cap(back, cap_spacing * 1.6, z=0.0, up=False, isl=1)
    else:
        fc = Piece()
        b = fc.append_verts(np.c_[front, np.full(k, depth)])
        for t in ear_clip(front):
            fc.add_face(tuple(b + i for i in t), [tuple(front[i]) for i in t], 2, False, 0)
        bc = Piece()
        b = bc.append_verts(np.c_[back, np.zeros(k)])
        for t in ear_clip(back):
            bc.add_face((b + t[0], b + t[2], b + t[1]), [tuple(back[t[0]]), tuple(back[t[2]]), tuple(back[t[1]])], 1, False, 0)
    return Piece.merge([piece, fc, bc])
