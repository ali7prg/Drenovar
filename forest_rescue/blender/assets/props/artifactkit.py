"""Artifact families (stone_rune, bronze_seal, amber_crystal, bone_key) and matching sockets.

Artifact frame (key_slot frame): origin = centre of the back face / insertion point, front face
toward -Y, up +Z.  Bone key: shaft along +Y (into the lock), bow toward -Y, bit plane YZ with the
teeth pointing -Z.  Socket frame: origin = recess floor centre (= key_slot), plate front at
y = -recess_depth, plate normal -Y.

Variant mapping (see site_props.json): readable without colour by outline + relief.
  stone_rune   v1 single spiral, chipped round rim        (lf_key_10)
               v2 triskele, three V-notches in the rim     (lf_key_02)
               v3 fir-sprig in a ring, 8-lobed scalloped rim (lf_key_04)
  bronze_seal  v1 three-leaf sprig, plain hexagon          (lf_key_11)
               v2 bell, hexagon with notched corners       (lf_key_03)
               v3 flame, hexagon with raised central boss  (lf_key_06)
  amber_crystal v1 single faceted crystal, 4 bronze caps   (lf_key_05)
               v2 two crystals split by a bronze bar        (lf_key_08)
               v3 three-step terraced crystal              (lf_key_09)
  bone_key     v1 round bow, one-notch bit                 (lf_key_01)
               v2 trefoil bow, two-notch bit               (lf_key_07)
               v3 square bow with cross, stepped bit       (lf_key_12)
"""
import math

import numpy as np

import motifs as mo
import propkit as pk
from propkit import Rx, Ry, Rz, M4

FRONT = Rx(math.pi / 2)          # local XY outline, local +Z toward the viewer -> world -Y
EMERALD = pk.srgb((74, 142, 92))

DIMS = {
    "stone_rune": dict(R=0.060, t=0.032, recess=("circle", 0.0635), recess_d=0.024),
    "bronze_seal": dict(R=0.050, t=0.022, recess=("hex", 0.0525), recess_d=0.016),
    "amber_crystal": dict(H=0.110, W=0.090, t=0.022, recess=("diamond", 0.116, 0.096), recess_d=0.018),
    "bone_key": dict(L=0.153, recess=("keyhole",), recess_d=0.030),
}


def _M(M, R=None, t=(0, 0, 0)):
    return np.asarray(M, float) @ M4(R, t)


# =============================================================================== stone rune

SCALE = {"stone_rune": 1.33, "bronze_seal": 1.30, "amber_crystal": 1.30, "bone_key": 1.25}   # sized to the cage-sheet sockets


def S4(fam):
    return M4(None, (0, 0, 0), SCALE[fam])


TRACE = {}   # filled by the build script from the reference masks: {family: dict(outline=(k,2) m, t=m, ...)}


def polar_resample(outline, n):
    """Resample a star-shaped outline by angle -> radii r(theta) (n samples)."""
    o = np.asarray(outline, float)
    ang = np.arctan2(o[:, 1], o[:, 0])
    rad = np.linalg.norm(o, axis=1)
    order = np.argsort(ang)
    ang, rad = ang[order], rad[order]
    ang = np.concatenate([ang - 2 * math.pi, ang, ang + 2 * math.pi])
    rad = np.concatenate([rad, rad, rad])
    th = np.linspace(-math.pi, math.pi, n, endpoint=False)
    return th, np.interp(th, ang, rad)


def rune_outline(v, n):
    R = DIMS["stone_rune"]["R"]
    tr = TRACE.get("stone_rune")
    if tr is not None:
        th, r = polar_resample(tr["outline"], n)
    else:
        th = np.linspace(-math.pi, math.pi, n, endpoint=False)
        r = np.full(n, R)
    if v == 2:
        r = r * 0.985
        for a in (math.pi / 2, math.pi / 2 + 2.094, math.pi / 2 + 4.189):
            dd = np.angle(np.exp(1j * (th - a)))
            r -= 0.0085 * np.clip(1 - np.abs(dd) / 0.17, 0, 1)
    elif v == 3:
        r = r * (0.99 - 0.035 * (0.5 + 0.5 * np.cos(8 * th)))
    return np.stack([r * np.cos(th), r * np.sin(th)], 1)


def rune_motifs(v):
    bb = (-0.066, -0.066, 0.066, 0.066)
    g = mo.Canvas(bb, ppm=9000)
    inl = mo.Canvas(bb, ppm=9000)
    orn = mo.Canvas(bb, ppm=9000)
    if v == 1:
        pts = mo.spiral_pts((0, 0), 0.003, 0.041, 2.15, a0=1.0)
        g.line(pts, 0.0088)
        inl.line(pts[8:-6], 0.0052)
        g.ring((0, 0), 0.0475, 0.0022)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            mo.knot_triangle(orn, (0.0505 * math.cos(a), 0.0505 * math.sin(a)), 0.0085, 0.0016, rot=a - math.pi / 2)
    elif v == 2:
        for k in range(3):
            a0 = k * 2 * math.pi / 3 + 0.4
            t = np.linspace(0, 1, 120)
            r = 0.004 + 0.038 * t
            a = a0 + 3.4 * t
            pts = np.stack([r * np.cos(a), r * np.sin(a)], 1)
            g.line(pts, 0.0072)
            inl.line(pts[10:-8], 0.0042)
        g.ring((0, 0), 0.0035, 0.002)
        for k in range(3):
            a = math.pi / 2 + math.pi / 3 + k * 2 * math.pi / 3
            mo.knot_triangle(orn, (0.049 * math.cos(a), 0.049 * math.sin(a)), 0.0085, 0.0016, rot=a - math.pi / 2)
    else:
        g.ring((0, 0), 0.036, 0.0055)
        inl.ring((0, 0), 0.036, 0.0032)
        # fir sprig: stem + chevrons
        g.line(np.array([[0, -0.026], [0, 0.027]]), 0.0035)
        for k, y in enumerate(np.linspace(-0.014, 0.020, 5)):
            w = 0.017 * (1 - k * 0.15)
            g.line(np.array([[-w, y - 0.008], [0, y], [w, y - 0.008]]), 0.0026)
        for k in range(8):
            a = k * math.pi / 4 + math.pi / 8
            c = np.array([math.cos(a), math.sin(a)])
            nrm = np.array([-c[1], c[0]])
            p0 = c * 0.0445 + nrm * 0.004
            p1 = c * 0.0495
            p2 = c * 0.0445 - nrm * 0.004
            orn.line(np.array([p0, p1, p2]), 0.0016)
    gm = g.mask(0.0006)
    om = orn.mask(0.0004)
    cut = np.maximum(gm, om * 0.55)
    return [dict(mask=cut, bbox=bb, isl=(2,), depth=0.0042, mode="cut", colour=pk.srgb((92, 80, 66)), tint=0.6),
            dict(mask=inl.mask(0.0004), bbox=bb, isl=(2,), depth=0.0, mode="cut", colour=EMERALD, tint=0.92,
                 rough=0.35)]


def build_rune(B, node, v, M=np.eye(4), cls="rune_stone"):
    d = DIMS["stone_rune"]
    t = TRACE.get("stone_rune", {}).get("t", d["t"])
    n = B.seg(40, 28, 16)
    outline = rune_outline(v, n)
    R = float(np.linalg.norm(outline, axis=1).max())
    dome = (lambda P: 0.0025 * np.clip(1 - (np.linalg.norm(P, axis=1) / R) ** 2, 0, 1)) if B.lod < 2 else None
    body = pk.extrude_round(outline, t - 0.0025, r_front=0.0075, r_back=0.005, seg=(2 if B.lod == 0 else 1),
                            cap_spacing=(0.013 if B.lod == 0 else (0.022 if B.lod == 1 else None)), dome=dome)
    meta = {"motif": rune_motifs(v)} if v != 1 else {"painted": 1}
    B.add(node, f"{node}_body", cls, body.transformed(_M(M, FRONT) @ S4("stone_rune")), meta=meta)


# =============================================================================== bronze seal

def seal_outline(v, lod):
    R = DIMS["bronze_seal"]["R"]
    tr = TRACE.get("bronze_seal")
    hexo = pk.ngon(R, 6, 0.0)
    if tr is not None and v != 2:
        return pk.resample_closed(tr["outline"], {0: 42, 1: 24, 2: 12}[lod])
    if v == 2 and lod < 2:
        pts = []
        for i in range(6):
            a = hexo[i]
            b = hexo[(i + 1) % 6]
            prev = hexo[i - 1]
            # notch: replace corner by a small concave arc
            da = pk.unit(prev - a)
            db = pk.unit(b - a)
            r = 0.0065
            c = a
            n_arc = 4 if lod == 0 else 2
            p0 = a + da * r
            p1 = a + db * r
            for k in range(n_arc + 1):
                t = k / n_arc
                q = (1 - t) * p0 + t * p1
                q = q + (c - q) * 0.0 - pk.unit(a) * 0.0
                # pull toward the hexagon centre (concave notch)
                q = q - pk.unit(a) * (0.0035 * math.sin(math.pi * t))
                pts.append(q)
        return np.array(pts)
    return hexo


def seal_motif(v):
    R = DIMS["bronze_seal"]["R"]
    bb = (-0.054, -0.054, 0.054, 0.054)
    rim = mo.Canvas(bb, ppm=10000)
    rim.poly(pk.ngon(R + 0.002, 6, 0.0))
    rim.poly(pk.ngon(R - 0.0075, 6, 0.0), fill=0)
    band = mo.Canvas(bb, ppm=10000)
    hp = pk.ngon(R - 0.0118, 6, 0.0)
    mo.celtic_band(band, np.vstack([hp, hp[:1]]), 0.0062, period=0.009)
    em = mo.Canvas(bb, ppm=10000)
    if v == 1:
        mo.sprig3(em, (0.0, -0.001), 0.060, 0.0022)
    elif v == 2:
        mo.glyph(em, "bell", (0.0, 0.002), 0.056, 0.003)
        em.line(np.array([[-0.02, -0.024], [0.02, -0.024]]), 0.0022)
    else:
        mo.glyph(em, "flame", (0.0, 0.0), 0.058, 0.003)
    m = np.maximum.reduce([rim.mask(0.0005), band.mask(0.0003) * 0.7, em.mask(0.0006)])
    return [dict(mask=m, bbox=bb, isl=(2,), depth=0.0022, mode="raise", field_cavity=1.0)]


def build_seal(B, node, v, M=np.eye(4), cls="bronze"):
    d = DIMS["bronze_seal"]
    t = TRACE.get("bronze_seal", {}).get("t", d["t"])
    outline = seal_outline(v, B.lod)
    sp = 0.011 if B.lod == 0 else (0.02 if B.lod == 1 else None)
    meta = {"motif": seal_motif(v)} if v != 1 else {"painted": 1}
    if v == 3:
        body = pk.extrude_round(outline, t - 0.0045, r_front=0.002, r_back=0.002, seg=1, cap_spacing=sp)
        boss = pk.extrude_round(pk.ngon(d["R"] * 0.72, 6, 0.0), 0.0045, r_front=0.0015, r_back=0.0005, seg=1,
                                cap_spacing=sp)
        boss = boss.transformed(M4(None, (0, 0, t - 0.0047)))
        B.add(node, f"{node}_body", cls, Piece_merge(body, boss).transformed(_M(M, FRONT) @ S4("bronze_seal")), meta=meta)
    else:
        body = pk.extrude_round(outline, t, r_front=0.0028, r_back=0.002, seg=(2 if B.lod == 0 else 1), cap_spacing=sp)
        B.add(node, f"{node}_body", cls, body.transformed(_M(M, FRONT) @ S4("bronze_seal")), meta=meta)


def Piece_merge(*ps):
    return pk.Piece.merge(list(ps))


# =============================================================================== amber crystal

def diamond(H, W):
    return np.array([[0, H / 2], [-W / 2, 0], [0, -H / 2], [W / 2, 0]], float)


def amber_frame_motif():
    d = DIMS["amber_crystal"]
    H, W = d["H"], d["W"]
    bb = (-W / 2 - 0.004, -H / 2 - 0.004, W / 2 + 0.004, H / 2 + 0.004)
    cv = mo.Canvas(bb, ppm=10000)
    outer = diamond(H, W)
    inner = pk.offset_poly(pk.ccw(outer), -0.0165)
    mid = pk.offset_poly(pk.ccw(outer), -0.0082)
    for i in range(4):
        a, b = mid[i], mid[(i + 1) % 4]
        t = np.linspace(0.2, 0.8, 2)
        seg = np.array([a + (b - a) * 0.2, a + (b - a) * 0.8])
        mo.celtic_band(cv, seg, 0.0105, period=0.012)
    return [dict(mask=cv.mask(0.0004), bbox=bb, isl=(2,), depth=0.0013, mode="cut", colour=pk.srgb((70, 50, 34)),
                 tint=0.7)]


def crystal_piece(outline, z0, z1, apex_z, kind, lod):
    """Faceted crystal over a convex outline (CCW). kind: 'peak' | 'terrace'."""
    outline = pk.ccw(np.asarray(outline, float))
    k = len(outline)
    c = outline.mean(0)
    p = pk.Piece()
    # girdle walls
    b0 = p.append_verts(np.c_[outline, np.full(k, z0)])
    b1 = p.append_verts(np.c_[outline, np.full(k, z1)])
    per = np.concatenate([[0], np.cumsum(np.linalg.norm(np.roll(outline, -1, 0) - outline, axis=1))])
    for j in range(k):
        j1 = (j + 1) % k
        p.add_face((b0 + j, b0 + j1, b1 + j1, b1 + j), [(per[j], z0), (per[j + 1], z0), (per[j + 1], z1), (per[j], z1)], 0)
    if kind == "peak":
        mid = c + (outline - c) * 0.55
        zm = z1 + (apex_z - z1) * 0.7
        m0 = p.append_verts(np.c_[mid, np.full(k, zm)])
        ax = outline[0] - c
        ridge = np.array([c + ax * 0.16, c - ax * 0.16])
        r0 = p.append_verts(np.c_[ridge, np.full(2, apex_z)])
        for j in range(k):
            j1 = (j + 1) % k
            p.add_face((b1 + j, b1 + j1, m0 + j1, m0 + j), [tuple(outline[j]), tuple(outline[j1]), tuple(mid[j1]), tuple(mid[j])], 1)
        # top facets: connect mid ring to ridge (nearest ridge point)
        for j in range(k):
            j1 = (j + 1) % k
            ra = 0 if np.dot(mid[j] - c, ax) >= 0 else 1
            rb = 0 if np.dot(mid[j1] - c, ax) >= 0 else 1
            if ra == rb:
                p.add_face((m0 + j, m0 + j1, r0 + ra), [tuple(mid[j]), tuple(mid[j1]), tuple(ridge[ra])], 1)
            else:
                p.add_face((m0 + j, m0 + j1, r0 + rb, r0 + ra), [tuple(mid[j]), tuple(mid[j1]), tuple(ridge[rb]), tuple(ridge[ra])], 1)
    else:  # terrace: 3 steps
        prev, zp = b1, z1
        prev_pts = outline
        for s, (sc, zz) in enumerate(((0.74, z1 + (apex_z - z1) * 0.38), (0.48, z1 + (apex_z - z1) * 0.7),
                                      (0.24, apex_z))):
            pts = c + (outline - c) * sc
            ta = p.append_verts(np.c_[pts, np.full(k, zp)])     # terrace (flat) ring
            tb = p.append_verts(np.c_[pts, np.full(k, zz)])     # riser top
            for j in range(k):
                j1 = (j + 1) % k
                p.add_face((prev + j, prev + j1, ta + j1, ta + j), [tuple(prev_pts[j]), tuple(prev_pts[j1]), tuple(pts[j1]), tuple(pts[j])], 1)
                p.add_face((ta + j, ta + j1, tb + j1, tb + j), [(per[j], zp), (per[j + 1], zp), (per[j + 1], zz), (per[j], zz)], 0)
            prev, zp, prev_pts = tb, zz, pts
        cap = p.append_verts(np.c_[prev_pts, np.full(k, zp)])
        for t in pk.ear_clip(prev_pts):
            p.add_face(tuple(cap + i for i in t), [tuple(prev_pts[i]) for i in t], 1)
    return p


def build_amber(B, node, v, M=np.eye(4)):
    M = np.asarray(M, float) @ S4("amber_crystal")
    d = DIMS["amber_crystal"]
    tr = TRACE.get("amber_crystal", {})
    H, W, t = tr.get("H", d["H"]), tr.get("W", d["W"]), tr.get("t", d["t"])
    outer = pk.ccw(diamond(H, W))
    fw = 0.0175
    inner = pk.offset_poly(outer, -fw)
    traced = tr.get("outline")
    if traced is not None:
        fo = pk.resample_closed(traced, {0: 48, 1: 28, 2: 16}[B.lod])
        frame = pk.extrude(fo, t, chamfer=0.0022, hole=inner)
    else:
        frame = pk.extrude(outer, t, chamfer=0.0022, hole=inner)
    B.add(node, f"{node}_frame", "oak_fine", frame.transformed(_M(M, FRONT)),
          meta=({"motif": amber_frame_motif()} if v != 1 else {"painted": 1}))
    gem_out = pk.offset_poly(outer, -fw + 0.0025)
    if v == 1:
        B.add(node, f"{node}_crystal", "amber", crystal_piece(gem_out, 0.003, t - 0.001, t + 0.012, "peak", B.lod)
              .transformed(_M(M, FRONT)))
    elif v == 2:
        top = np.array([gem_out[0], [gem_out[1][0], 0.003], [gem_out[3][0], 0.003]])
        bot = np.array([[gem_out[1][0], -0.003], gem_out[2], [gem_out[3][0], -0.003]])
        B.add(node, f"{node}_crystal", "amber", crystal_piece(top, 0.003, t - 0.001, t + 0.009, "peak", B.lod)
              .transformed(_M(M, FRONT)))
        B.add(node, f"{node}_crystal", "amber", crystal_piece(bot, 0.003, t - 0.001, t + 0.009, "peak", B.lod)
              .transformed(_M(M, FRONT)))
        bar = pk.extrude(pk.rect(W - 0.02, 0.0075, 0.0015), t + 0.004, chamfer=0.0012)
        B.add(node, f"{node}_bar", "bronze", bar.transformed(_M(M, FRONT)))
    else:
        B.add(node, f"{node}_crystal", "amber", crystal_piece(gem_out, 0.003, t - 0.001, t + 0.011, "terrace", B.lod)
              .transformed(_M(M, FRONT)))
    # bronze corner caps with rivets
    c0 = outer.mean(0)
    for i in range(4):
        T = outer[i]
        e1 = pk.unit(outer[(i + 1) % 4] - T)
        e2 = pk.unit(outer[i - 1] - T)
        n1 = np.array([e1[1], -e1[0]])          # outward normal of edge T -> next (CCW)
        n2 = np.array([-e2[1], e2[0]])          # outward normal of edge prev -> T
        L, grow = 0.0175, 0.0016
        A = T + e1 * L
        Bp = T + e2 * L
        In = inner[i]
        poly = pk.ccw(np.array([T + pk.unit(T - c0) * grow * 1.4, A + n1 * grow, A - n1 * (fw + 0.0015),
                                In - pk.unit(T - c0) * 0.0015, Bp - n2 * (fw + 0.0015), Bp + n2 * grow]))
        cap = pk.extrude(poly, t + 0.003, chamfer=0.0009).transformed(M4(None, (0, 0, -0.0015)))
        B.add(node, f"{node}_caps", "bronze", cap.transformed(_M(M, FRONT)))
        cc = T + (In - T) * 0.40
        seg = B.seg(10, 6, 4)
        riv = pk.lathe(np.array([[0.0032, 0], [0.0029, 0.0012], [0.0018, 0.0022], [0, 0.0026]]), seg)
        riv = riv.transformed(M4(None, (cc[0], cc[1], t + 0.0014)))
        B.add(node, f"{node}_caps", "bronze", riv.transformed(_M(M, FRONT)), max_lod=1)


# =============================================================================== bone key

KEY_L = 0.152          # traced: bow outer dia = 0.353 L, shaft dia 0.12 L, bit 0.75..0.97 L (front view)


def key_profile(lod):
    """Lathe profile (r, x) of the shaft from the bow neck to the tip; x local (insertion point = 0 at 0.73 L)."""
    L = KEY_L
    X = lambda f: (f - 0.73) * L
    P = [(0.0, X(0.315)), (0.0080, X(0.318)), (0.0118, X(0.330)), (0.0128, X(0.338)), (0.0128, X(0.356)),
         (0.0098, X(0.362)), (0.0116, X(0.370)), (0.0116, X(0.402)), (0.0094, X(0.410)), (0.0093, X(0.418)),
         (0.0093, X(0.662)), (0.0096, X(0.670)), (0.0106, X(0.676)), (0.0106, X(0.722)), (0.0094, X(0.730)),
         (0.0091, X(0.740)), (0.0091, X(0.975)), (0.0080, X(0.990)), (0.0048, X(0.999)), (0.0, X(1.0))]
    P = np.array(P)
    pc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    if lod == 2:
        idx = [0, 1, 3, 4, 7, 9, 10, 13, 15, 16, 18, 19]
    elif lod == 1:
        idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19]
    else:
        idx = list(range(len(P)))
    return P[idx], pc[idx]


def key_motif():
    # knot band on the thick shaft section (lathe v = arc length along the profile)
    prof, pc = key_profile(0)
    # profile point indices 9..10 = knot section
    v0, v1 = pc[9], pc[10]
    prof = prof
    R = 0.0128
    U = 2 * math.pi * R
    bb = (0, v0 - 0.002, U, v1 + 0.002)
    cv = mo.Canvas(bb, ppm=12000)
    for k in range(2):
        uc = U * (0.25 + 0.5 * k)
        mo.celtic_band(cv, np.array([[uc, v0 + 0.0015], [uc, v1 - 0.0015]]), U * 0.36, period=0.0095)
    return [dict(mask=cv.mask(0.0003), bbox=bb, isl=(0,), depth=0.0011, mode="cut", colour=pk.srgb((140, 112, 80)),
                 tint=0.7)]


def build_key(B, node, v, M=np.eye(4)):
    # local presentation frame: shaft along +X, bit plane XZ, teeth -Z; then Rz(90): +X -> +Y
    Mk = np.asarray(M, float) @ S4("bone_key") @ M4(Rz(math.pi / 2))
    seg = B.seg(8, 6, 4)
    kp, kv = key_profile(B.lod)
    shaft = pk.lathe(kp, seg, smooth=True, v_values=kv, ref_R=0.0128)
    shaft = shaft.transformed(M4(Ry(math.pi / 2)))   # lathe axis Z -> X ; r=0 rows at x=-0.0805 and 0.0528
    shaft = _fix_lathe_x(shaft)
    B.add(node, f"{node}_shaft", "bone", shaft.transformed(Mk), meta={"motif": key_motif()})
    # bow
    bc = np.array([(0.172 - 0.73) * KEY_L, 0.0, 0.0])
    nseg = B.seg(22, 14, 10)
    sides = B.seg(6, 5, 4)
    bow_prof = lambda r: np.array([[r * math.cos(a), 1.45 * r * math.sin(a)] for a in
                                   np.linspace(0, 2 * math.pi, sides, endpoint=False) + math.pi / sides])
    if v == 1:
        th = np.linspace(0, 2 * math.pi, nseg, endpoint=False)
        R = 0.0206
        path = np.stack([bc[0] + R * np.cos(th), np.zeros(nseg), R * np.sin(th)], 1)
        bow = pk.sweep(path, bow_prof(0.0064), closed_path=True, up=(0, 1, 0), smooth=True, ref_perim=0.05)
    elif v == 2:
        th = np.linspace(0, 2 * math.pi, int(nseg * 1.2), endpoint=False)
        R = 0.0185 * (1 + 0.30 * np.cos(3 * th))
        path = np.stack([bc[0] - 0.002 + R * np.cos(th), np.zeros(len(th)), R * np.sin(th)], 1)
        bow = pk.sweep(path, bow_prof(0.0052), closed_path=True, up=(0, 1, 0), smooth=True, ref_perim=0.045)
    else:
        s = 0.0205
        sq = pk.rounded_rect(2 * s, 2 * s, 0.008, seg=max(2, nseg // 8))
        sq = pk.resample_closed(sq, nseg)
        path = np.stack([bc[0] + sq[:, 0], np.zeros(len(sq)), sq[:, 1]], 1)
        bow = pk.sweep(path, bow_prof(0.0054), closed_path=True, up=(0, 1, 0), smooth=True, ref_perim=0.046)
        B.add(node, f"{node}_bowx", "bone", pk.rod((bc[0] - s, 0, 0), (bc[0] + s, 0, 0), 0.0034, 4).transformed(Mk))
        B.add(node, f"{node}_bowx", "bone", pk.rod((bc[0], 0, -s), (bc[0], 0, s), 0.0034, 4).transformed(Mk))
    B.add(node, f"{node}_bow", "bone", bow.transformed(Mk))
    # bit (XZ outline, thickness along Y)
    if v == 1:
        bit = [(0.003, 0.004), (0.003, -0.0292), (0.0175, -0.0292), (0.0175, -0.0165), (0.0223, -0.0165),
               (0.0223, -0.0292), (0.0365, -0.0292), (0.0365, 0.004)]
    elif v == 2:
        bit = [(0.003, 0.004), (0.003, -0.0292), (0.0106, -0.0292), (0.0106, -0.017), (0.016, -0.017),
               (0.016, -0.0292), (0.0236, -0.0292), (0.0236, -0.017), (0.0289, -0.017), (0.0289, -0.0292),
               (0.0365, -0.0292), (0.0365, 0.004)]
    else:
        bit = [(0.0023, 0.004), (0.0023, -0.032), (0.0137, -0.032), (0.0137, -0.024), (0.0251, -0.024),
               (0.0251, -0.016), (0.0365, -0.016), (0.0365, 0.004)]
    bit = np.array(bit)
    bp = pk.extrude(bit, 0.0105, chamfer=0.0013)
    # extrude: outline XY (x, z), depth along local z -> map (x, y, z) -> (x, z_depth - t/2, y)
    Mb = np.array([[1, 0, 0, 0], [0, 0, 1, -0.00525], [0, 1, 0, 0], [0, 0, 0, 1]], float)
    bp = bp.transformed(Mb)
    B.add(node, f"{node}_bit", "bone", bp.transformed(Mk))


def _fix_lathe_x(p):
    return p


# =============================================================================== sockets

def recess_outline(kind, n=48):
    if kind == "circle":
        return pk.circle(DIMS["stone_rune"]["recess"][1], n)
    if kind == "hex":
        return pk.ngon(DIMS["bronze_seal"]["recess"][1], 6, 0.0)
    if kind == "diamond":
        _, H, W = DIMS["amber_crystal"]["recess"]
        return pk.ccw(diamond(H, W))
    if kind == "keyhole":
        c = pk.circle(0.0105, max(10, n // 3), math.pi / 2)
        c = c[(c[:, 1] > -0.0062)]
        pts = list(c) + [(-0.0062, -0.009), (-0.0095, -0.046), (0.0095, -0.046), (0.0062, -0.009)]
        pts = np.array(pts) + np.array([0, 0.016])
        return pk.ccw(pts)
    raise ValueError(kind)


def socket_plate_outline(kind, style=None):
    if style == "cage":      # cage-mounted plates as drawn on the cage sheet
        if kind == "circle":
            return pk.circle(0.122, 40)
        if kind == "hex":
            return pk.ngon(0.104, 6, 0.0)
        if kind == "diamond":
            return pk.ccw(diamond(0.250, 0.162))
        return pk.rect(0.165, 0.205, 0.028)
    if kind == "circle":
        return pk.rounded_rect(0.205, 0.205, 0.03, 3)
    if kind == "hex":
        return pk.ngon(0.112, 8, math.pi / 8)
    if kind == "diamond":
        return pk.ccw(diamond(0.210, 0.178))
    if kind == "keyhole":
        return pk.rect(0.150, 0.190, 0.026)
    raise ValueError(kind)


def socket_motif(kind, style=None):
    if style == "cage" and kind == "circle":   # segmented stone ring (oak cage drawing)
        bb = (-0.125, -0.125, 0.125, 0.125)
        cv = mo.Canvas(bb, ppm=3000)
        for k in range(14):
            a = 2 * math.pi * k / 14 + 0.1
            cv.line(np.array([[0.086 * math.cos(a), 0.086 * math.sin(a)], [0.125 * math.cos(a), 0.125 * math.sin(a)]]), 0.003)
        cv.ring((0, 0), 0.088, 0.004)
        return [dict(mask=cv.mask(0.0008), bbox=bb, isl=(2,), depth=0.004, mode="cut", colour=pk.srgb((80, 70, 58)), tint=0.6)]
    if style == "cage" and kind in ("hex", "diamond", "keyhole"):
        bb = (-0.12, -0.12, 0.12, 0.12)
        cv = mo.Canvas(bb, ppm=3000)
        out = socket_plate_outline(kind, "cage")
        inner = pk.offset_poly(pk.ccw(out), -0.016)
        cv.line(np.vstack([inner, inner[:1]]), 0.003)
        return [dict(mask=cv.mask(0.0006), bbox=bb, isl=(2,), depth=0.0015, mode="cut")]
    if kind == "circle":
        bb = (-0.105, -0.105, 0.105, 0.105)
        cv = mo.Canvas(bb, ppm=6000)
        mo.celtic_band(cv, np.vstack([pk.circle(0.077, 64), pk.circle(0.077, 64)[:1]]), 0.012, period=0.016)
        crk = mo.Canvas(bb, ppm=6000)
        for a in (0.3, 1.9, 3.5, 4.9):
            crk.line(np.array([[0.066 * math.cos(a), 0.066 * math.sin(a)], [0.11 * math.cos(a + 0.05), 0.11 * math.sin(a + 0.05)]]), 0.0012)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            mo.knot_triangle(cv, (0.088 * math.cos(a), 0.088 * math.sin(a)), 0.011, 0.002, rot=a - math.pi / 2)
    elif kind == "hex":
        bb = (-0.113, -0.113, 0.113, 0.113)
        cv = mo.Canvas(bb, ppm=6000)
        crk = mo.Canvas(bb, ppm=6000)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            mo.knot_triangle(cv, (0.082 * math.cos(a), 0.082 * math.sin(a)), 0.013, 0.0022, rot=a - math.pi / 2)
        hp = pk.ngon(0.064, 6, 0.0)
        cv.line(np.vstack([hp, hp[:1]]), 0.002)
        for a in (0.0, math.pi):
            crk.line(np.array([[0.055 * math.cos(a), 0], [0.11 * math.cos(a), 0.002]]), 0.0012)
    elif kind == "diamond":
        bb = (-0.092, -0.108, 0.092, 0.108)
        cv = mo.Canvas(bb, ppm=6000)
        crk = mo.Canvas(bb, ppm=6000)
        for sx in (-1, 1):
            mo.knot_triangle(cv, (sx * 0.058, 0.0), 0.014, 0.0022, rot=(math.pi / 2 if sx > 0 else -math.pi / 2) - math.pi / 2)
        dp = pk.offset_poly(pk.ccw(diamond(0.116, 0.096)), 0.006)
        cv.line(np.vstack([dp, dp[:1]]), 0.002)
    else:
        bb = (-0.077, -0.097, 0.077, 0.097)
        cv = mo.Canvas(bb, ppm=6000)
        crk = mo.Canvas(bb, ppm=6000)
        for sx in (-1, 1):
            c = np.array([sx * 0.046, -0.002])
            cv.line(np.array([c + (0, 0.032), c + (sx * 0.012, 0.0), c + (0, -0.032), c + (-sx * 0.012, 0.0), c + (0, 0.032)]), 0.0022)
            mo.triquetra(cv, c, 0.012, 0.0018, rot=0.3)
        crk.line(np.array([[0.0, 0.05], [0.004, 0.095]]), 0.0012)
    m = np.maximum(cv.mask(0.0004), crk.mask(0.0003))
    return [dict(mask=m, bbox=bb, isl=(2,), depth=0.0018, mode="cut", colour=pk.srgb((96, 84, 70)), tint=0.55)]


def build_socket(B, node, kind, M=np.eye(4), cls="limestone_fine", prefix=None, plate=True, floor_cls=None,
                 plate_t=0.036, style=None, density=1.0):
    """Socket plate with recess (frame: recess floor at origin, plate front at -Y = -recess_d)."""
    prefix = prefix or node
    key = {"circle": "stone_rune", "hex": "bronze_seal", "diamond": "amber_crystal", "keyhole": "bone_key"}[kind]
    Sf = SCALE[key]
    rd = DIMS[key]["recess_d"] * Sf
    n = B.seg(48, 28, 16) if style is None else B.seg(28, 20, 12)
    rec = recess_outline(kind, n) * Sf
    if style == "cage":
        plate_t = rd + 0.012
    if plate:
        out = socket_plate_outline(kind, style)
        if style is None:
            out = out * Sf
        if kind == "circle":
            out = pk.resample_closed(out, B.seg(40, 24, 16) if style is None else B.seg(28, 20, 12))
        p = pk.extrude(out, plate_t, chamfer=0.004 if style is None else 0.008, hole=rec)
        p = p.transformed(M4(None, (0, 0, rd - plate_t)))
        mot = socket_motif(kind, style)
        if style is None:
            mot = [dict(m_, bbox=tuple(np.asarray(m_["bbox"]) * Sf)) for m_ in mot]
        meta = {"motif": mot, "no_paint": 1 if style else 0}
        B.add(node, f"{prefix}_plate", cls, p.transformed(_M(M, FRONT)), meta=meta, density=density)
        if style == "cage" and kind in ("hex", "diamond"):     # corner rivet heads
            for q in socket_plate_outline(kind, "cage"):
                c = q * 0.88
                rv = pk.lathe(np.array([[0.011, 0], [0.01, 0.005], [0.006, 0.009], [0, 0.011]]), B.seg(8, 6, 4))
                B.add(node, f"{prefix}_rivets", cls, rv.transformed(_M(M, FRONT) @ M4(None, (c[0], c[1], rd))), max_lod=1,
                      meta={"no_paint": 1}, density=density)
        if style == "cage" and kind == "circle":               # square loop on the left of the ring (drawing)
            loop = pk.extrude(pk.rect(0.06, 0.07, 0.006), 0.03, chamfer=0.004, hole=pk.rect(0.03, 0.04))
            B.add(node, f"{prefix}_loop", cls, loop.transformed(_M(M, FRONT) @ M4(None, (-0.143, 0.0, rd - 0.03))),
                  meta={"no_paint": 1}, density=density)
    floor = pk.extrude(rec * 1.02, 0.004).transformed(M4(None, (0, 0, -0.004)))
    B.add(node, f"{prefix}_floor", floor_cls or cls, floor.transformed(_M(M, FRONT)), meta={"floor": 1, "no_paint": 1 if style else 0},
          density=density)
    return rd
