"""Garment and accessory geometry (numpy -> quad meshes with UVs; thickness via Solidify).

drape()     cloth sheets parametrised by angle around a vertical axis (theta=0 at the front,
            +theta toward the character's left/+X) and arc length down a profile that rests on
            the outermost body surface (ray casting into a reference SDF) and hangs vertically
            below support points (no clinging into concavities), with flare, folds, ragged
            hems, region masks (openings, armholes) and optional silhouette fitting.
band()      straps/belts/sashes along a polyline (ribbon offset along the surface normal)
tube()      ropes, cords, strings, rolled cuffs, coils
rbox()      rounded boxes (pouches, satchels, buckles, blocks)
lathe()     revolved profiles (helmet dome, shield boss, pommels, quivers)
"""
import math

import numpy as np

TAU = 2.0 * math.pi


def _unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


class Mesh:
    """Simple quad/tri mesh accumulator with per-loop UVs and per-face part ids."""

    def __init__(self):
        self.v = []
        self.f = []
        self.uv = []      # per face: list of (u, v)
        self.part = []    # per face: part name

    def add(self, verts, faces, uvs, part):
        base = sum(len(x) for x in self.v)
        self.v.append(np.asarray(verts, float))
        for fc, fu in zip(faces, uvs):
            self.f.append([base + int(i) for i in fc])
            self.uv.append([tuple(map(float, u)) for u in fu])
            self.part.append(part)
        return self

    def arrays(self):
        V = np.concatenate(self.v) if self.v else np.zeros((0, 3))
        return V, self.f, self.uv, self.part


def grid_faces(nu, nv, valid=None, wrap_u=False):
    """Quads of an (nv, nu) vertex grid; valid: (nv, nu) bool -> face kept if all 4 corners ok."""
    faces, uvidx = [], []
    cols = nu if wrap_u else nu - 1
    for j in range(nv - 1):
        for i in range(cols):
            i1 = (i + 1) % nu
            q = [(j, i), (j + 1, i), (j + 1, i1), (j, i1)]
            if valid is not None and not all(valid[a, b] for a, b in q):
                continue
            faces.append([a * nu + b for a, b in q])
            uvidx.append([(j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1)])
    return faces, uvidx


# --------------------------------------------------------------------------- ray casting

def ray_radius(sdf_fn, center_xy, theta, z, rmax=0.65, step=0.004, clearance=0.0):
    """Outermost radius (from the vertical axis through center_xy) at which sdf < clearance.

    theta, z: arrays of equal shape.  Returns r (np.nan where nothing is hit)."""
    th = np.asarray(theta, float)
    zz = np.asarray(z, float)
    shape = th.shape
    th = th.ravel()
    zz = zz.ravel()
    rs = np.arange(rmax, 0.0, -step)
    dx = np.sin(th)
    dy = -np.cos(th)
    hit = np.full(th.shape, np.nan)
    remaining = np.ones(th.shape, bool)
    prev = None
    for r in rs:
        idx = np.nonzero(remaining)[0]
        if len(idx) == 0:
            break
        P = np.stack([center_xy[0] + r * dx[idx], center_xy[1] + r * dy[idx], zz[idx]], -1)
        d = sdf_fn(P) - clearance
        inside = d < 0
        if inside.any():
            ii = idx[inside]
            # refine linearly between r and r+step using the distance value
            hit[ii] = r + np.clip(-d[inside], 0, step)
            remaining[ii] = False
    return hit.reshape(shape)


# --------------------------------------------------------------------------- drape

def drape(sdf_fn, center_xy, theta_range, z_top, z_hem, nu=48, nv=40, clearance=0.012, slack=0.10,
          flare=0.0, flare_pow=1.5, folds=None, ragged=0.0, seed=0, region=None, closed=False,
          fit=None, rmin=0.03, top_r=None, part="cloth", u_scale=None, extra_r=None, z_samples=None):
    """Cloth sheet hanging around a vertical axis.

    theta_range: (t0, t1) radians (t0<t1; closed=True for a full tube).
    z_top(theta), z_hem(theta): callables (arrays) giving top edge and hem heights.
    slack: how fast (m per m of drop) the cloth may fall back toward the axis below a support.
    flare(z_frac) or constant: extra radius growth (m per m of drop from the top).
    folds: list of (count, amplitude, phase) radial sine folds (amplitude grows toward the hem).
    region(theta, z) -> bool mask of where cloth exists (armholes, front openings).
    fit: optional (hull_fn(x,z)->signed dist m, zlo, zhi, side_sign or 0): pull/push the extreme
         columns so the front-view outline follows the reference hull in [zlo, zhi].
    Returns dict(verts (nv,nu,3), valid (nv,nu), faces, uvs, theta, zrows).
    """
    rng = np.random.default_rng(seed)
    t0, t1 = theta_range
    if closed:
        th = np.linspace(t0, t0 + TAU, nu, endpoint=False)
    else:
        th = np.linspace(t0, t1, nu)
    zt = np.asarray(z_top(th), float) * np.ones(nu)
    zh = np.asarray(z_hem(th), float) * np.ones(nu)
    if ragged > 0:
        jag = rng.normal(0, ragged, nu)
        jag = np.convolve(np.concatenate([jag[-2:], jag, jag[:2]]), np.ones(3) / 3, mode="same")[2:-2]
        zh = zh + jag
    # fine vertical sampling per column
    nzf = z_samples or 220
    prof = []
    for i in range(nu):
        zs = np.linspace(zt[i], zh[i], nzf)
        r_hit = ray_radius(sdf_fn, center_xy, np.full(nzf, th[i]), zs, clearance=clearance)
        r = np.zeros(nzf)
        cur = None
        for j in range(nzf):
            h = r_hit[j]
            if cur is None:
                cur = h if np.isfinite(h) else (top_r if top_r is not None else rmin)
            else:
                dz = zs[j - 1] - zs[j]
                fall = cur - slack * dz
                cur = max(fall, h) if np.isfinite(h) else max(fall, rmin)
            r[j] = cur
        drop = zt[i] - zs
        span = max(zt[i] - zh[i], 1e-6)
        if callable(flare):
            r = r + flare(drop / span) * drop
        elif flare:
            r = r + flare * span * (drop / span) ** flare_pow
        if extra_r is not None:
            r = r + extra_r(th[i], zs)
        prof.append((zs, r))
    # arc-length resampling per column into nv rows
    V = np.zeros((nv, nu, 3))
    Zr = np.zeros((nv, nu))
    Ls = np.zeros(nu)
    for i in range(nu):
        zs, r = prof[i]
        seg = np.sqrt(np.diff(r) ** 2 + np.diff(zs) ** 2)
        acc = np.concatenate([[0], np.cumsum(seg)])
        Ls[i] = acc[-1]
        tgt = np.linspace(0, acc[-1], nv)
        rr = np.interp(tgt, acc, r)
        zz = np.interp(tgt, acc, zs)
        if folds:
            frac = np.linspace(0, 1, nv)
            add = 0.0
            for (cnt, amp, ph) in folds:
                add = add + amp * np.sin(cnt * th[i] + ph) * frac ** 0.8
            rr = rr + add
        V[:, i, 0] = center_xy[0] + rr * np.sin(th[i])
        V[:, i, 1] = center_xy[1] - rr * np.cos(th[i])
        V[:, i, 2] = zz
        Zr[:, i] = zz
    if fit is not None:
        V = fit_outline(V, *fit)
    valid = np.ones((nv, nu), bool)
    if region is not None:
        valid = region(np.broadcast_to(th[None, :], (nv, nu)), Zr)
    faces, uvidx = grid_faces(nu, nv, valid, wrap_u=closed)
    # UVs: u by arc length around (at the top row and hem average), v by arc length down
    circ = np.linalg.norm(np.diff(np.concatenate([V[nv // 2], V[nv // 2][:1]]) if closed else V[nv // 2], axis=0),
                          axis=1)
    ucum = np.concatenate([[0], np.cumsum(circ)])
    vlen = Ls.mean()
    uvs = []
    for q in uvidx:
        uvs.append([(ucum[min(i, len(ucum) - 1)] if i < len(ucum) else ucum[-1], -(j / (nv - 1)) * vlen) for j, i in q])
    return dict(verts=V, valid=valid, faces=faces, uvs=uvs, theta=th, nu=nu, nv=nv, part=part, closed=closed)


def fit_outline(V, hull_fn, zlo, zhi, side=0, max_scale=0.25, cx=0.0):
    """Scale each row's lateral offsets (per side) so its extreme x matches the hull edge."""
    nv, nu, _ = V.shape
    V = V.copy()
    for j in range(nv):
        z = V[j, 0, 2]
        if not (zlo <= V[j, :, 2].mean() <= zhi):
            continue
        for sgn in ((1, -1) if side == 0 else (side,)):
            xs = V[j, :, 0] - cx
            sel = xs * sgn > 0.01
            if not sel.any():
                continue
            ext = np.max(xs[sel] * sgn)
            zz = V[j, sel, 2].mean()
            # march along x to find hull boundary starting from the current extreme
            cand = np.linspace(max(ext * 0.6, 0.02), ext * 1.6 + 0.05, 160)
            d = hull_fn(np.full_like(cand, 0) + sgn * cand + cx, np.full_like(cand, zz))
            inside = d < 0
            if not inside.any():
                continue
            # last inside sample of the run that contains (or is nearest to) the current extreme
            k0 = int(np.argmin(np.abs(cand - ext)))
            if inside[k0]:
                k = k0
                while k + 1 < len(cand) and inside[k + 1]:
                    k += 1
            else:
                k = k0
                while k > 0 and not inside[k]:
                    k -= 1
            edge = cand[k]
            f = np.clip(edge / max(ext, 1e-6), 1 - max_scale, 1 + max_scale)
            V[j, sel, 0] = cx + xs[sel] * f
    # smooth the per-row change vertically to avoid zig-zags
    return V


def sheet_mesh(D):
    """Flatten a drape dict to (verts, faces, uvs) lists."""
    V = D["verts"].reshape(-1, 3)
    return V, D["faces"], D["uvs"]


# --------------------------------------------------------------------------- bands, tubes, boxes

def band(points, normals, width, part="band", twist_up=None, closed=False, segs_w=1):
    """Ribbon along polyline points (n,3) with surface normals (n,3): width across, flat."""
    P = np.asarray(points, float)
    N = _unit(np.asarray(normals, float))
    n = len(P)
    T = np.gradient(P, axis=0)
    if closed:
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    T = _unit(T)
    Bv = _unit(np.cross(T, N))
    verts = []
    for k in range(segs_w + 1):
        a = -0.5 + k / segs_w
        verts.append(P + Bv * (a * width))
    V = np.stack(verts, 0)  # (segs_w+1, n, 3)
    nu = n
    nv = segs_w + 1
    faces, uvidx = grid_faces(nu, nv, wrap_u=closed)
    seglen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    if closed:
        seglen = np.concatenate([seglen, [seglen[-1] + np.linalg.norm(P[0] - P[-1])]])
    uvs = [[(seglen[min(i, len(seglen) - 1)], j * width / segs_w) for j, i in q] for q in uvidx]
    return V.reshape(-1, 3), faces, uvs


def tube(points, radius, sides=8, closed=False, part="tube", caps=True, twist=0.0):
    """Round tube along a polyline; radius scalar or per-point array."""
    P = np.asarray(points, float)
    n = len(P)
    R = np.broadcast_to(np.asarray(radius, float), (n,)).copy()
    T = np.gradient(P, axis=0) if not closed else (np.roll(P, -1, 0) - np.roll(P, 1, 0))
    T = _unit(T)
    # parallel transport frame
    ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    Nv = _unit(np.cross(T[0], ref))
    frames = []
    for i in range(n):
        if i:
            Nv = Nv - np.dot(Nv, T[i]) * T[i]
            Nv = _unit(Nv)
        Bv = np.cross(T[i], Nv)
        frames.append((Nv, Bv))
    verts = np.zeros((n, sides, 3))
    for i in range(n):
        Nv, Bv = frames[i]
        for k in range(sides):
            a = TAU * k / sides + twist * i
            verts[i, k] = P[i] + R[i] * (math.cos(a) * Nv + math.sin(a) * Bv)
    faces, uvidx = grid_faces(sides, n, wrap_u=True)
    faces = [[f[0], f[3], f[2], f[1]] for f in faces]  # outward winding
    uvidx = [[q[0], q[3], q[2], q[1]] for q in uvidx]
    seglen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    circ = TAU * float(R.mean())
    uvs = [[(i / sides * circ, seglen[min(j, n - 1)]) for j, i in q] for q in uvidx]
    V = verts.reshape(-1, 3)
    if caps and not closed:
        extra = []
        for end, sign in ((0, -1), (n - 1, 1)):
            c = len(V) + len(extra)
            extra.append(P[end])
            ring = [end * sides + k for k in range(sides)]
            for k in range(sides):
                a, b = ring[k], ring[(k + 1) % sides]
                faces.append([a, b, c] if sign > 0 else [b, a, c])
                uvs.append([(0, 0), (0.01, 0), (0.005, 0.01)])
        V = np.concatenate([V, np.array(extra)])
    return V, faces, uvs


def rbox(center, size, rot=None, bevel=0.2, segs=2, part="box"):
    """Rounded box as a subdivided cube projected toward a superellipsoid (bevel 0..1)."""
    c = np.asarray(center, float)
    hx, hy, hz = np.asarray(size, float) / 2.0
    n = segs * 2 + 2
    lin = np.linspace(-1, 1, n)
    verts, faces, uvs = [], [], []

    def face_grid(axis, sign):
        base = len(verts)
        for j in range(n):
            for i in range(n):
                a, b = lin[i], lin[j]
                p = np.zeros(3)
                p[axis] = sign
                o = [k for k in range(3) if k != axis]
                p[o[0]] = a if sign > 0 else -a
                p[o[1]] = b
                verts.append(p)
        for j in range(n - 1):
            for i in range(n - 1):
                q = [base + j * n + i, base + j * n + i + 1, base + (j + 1) * n + i + 1, base + (j + 1) * n + i]
                faces.append(q)
                uvs.append([(i / (n - 1), j / (n - 1)), ((i + 1) / (n - 1), j / (n - 1)),
                            ((i + 1) / (n - 1), (j + 1) / (n - 1)), (i / (n - 1), (j + 1) / (n - 1))])

    for ax in range(3):
        for sg in (1, -1):
            face_grid(ax, sg)
    V = np.array(verts)
    # superellipsoid rounding
    e = 2.0 + 10.0 * (1 - np.clip(bevel, 0.01, 1))
    nrm = (np.abs(V) ** e).sum(1) ** (1 / e)
    V = V / nrm[:, None]
    V = V * np.array([hx, hy, hz])
    if rot is not None:
        V = V @ np.asarray(rot).T
    V = V + c
    # weld duplicate edge vertices
    key = np.round(V / 1e-5).astype(np.int64)
    _, inv, idx = np.unique(key, axis=0, return_inverse=True, return_index=True)[0:0] or (None, None, None)
    uniq, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.ravel()
    V2 = V[first]
    faces = [[int(inverse[i]) for i in f] for f in faces]
    # fix winding (outward)
    out_f = []
    for f in faces:
        a, b, c_ = V2[f[0]], V2[f[1]], V2[f[2]]
        nrm_ = np.cross(b - a, c_ - a)
        cen = V2[f].mean(0)
        if np.dot(nrm_, cen - c) < 0:
            f = f[::-1]
        out_f.append(f)
    uvs2 = []
    for f, u in zip(faces, uvs):
        uvs2.append(u)
    # reverse uvs where faces were flipped
    uvs_fixed = []
    for f0, f1, u in zip(faces, out_f, uvs):
        uvs_fixed.append(u if f0 == f1 else u[::-1])
    scale = np.array([hx, hy, hz]).max() * 2
    uvs_fixed = [[(a * scale, b * scale) for a, b in u] for u in uvs_fixed]
    return V2, out_f, uvs_fixed


def lathe(profile, axis_origin, axis_dir, sides=16, part="lathe", ref=None, closed_top=False):
    """Revolve profile [(radius, height) ...] around axis; returns verts, faces, uvs."""
    o = np.asarray(axis_origin, float)
    ax = _unit(axis_dir)
    if ref is None:
        ref = np.array([1.0, 0, 0]) if abs(ax[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = _unit(ref - np.dot(ref, ax) * ax)
    e2 = np.cross(ax, e1)
    prof = np.asarray(profile, float)
    m = len(prof)
    V = np.zeros((m, sides, 3))
    for j, (r, h) in enumerate(prof):
        for k in range(sides):
            a = TAU * k / sides
            V[j, k] = o + ax * h + r * (math.cos(a) * e1 + math.sin(a) * e2)
    faces, uvidx = grid_faces(sides, m, wrap_u=True)
    seg = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    circ = TAU * float(np.max(prof[:, 0]))
    uvs = [[(i / sides * circ, seg[j]) for j, i in q] for q in uvidx]
    return V.reshape(-1, 3), faces, uvs


# --------------------------------------------------------------------------- helpers on body SDF

def surface_point(sdf_fn, origin, direction, rmax=0.5, step=0.002, clearance=0.0):
    """Outermost point along a ray from `origin + direction*rmax` back toward origin."""
    d = _unit(direction)
    for r in np.arange(rmax, 0, -step):
        p = origin + d * r
        if sdf_fn(p[None])[0] < clearance:
            return p
    return origin


def ring_around(sdf_fn, center_xy, z, n=48, clearance=0.006, z_fn=None, theta0=0.0, theta1=TAU):
    """Closed ring hugging the body at height z (or z_fn(theta)); returns points, outward normals."""
    th = np.linspace(theta0, theta1, n, endpoint=False)
    zz = z_fn(th) if z_fn is not None else np.full(n, z)
    r = ray_radius(sdf_fn, center_xy, th, zz, clearance=clearance)
    r = np.where(np.isfinite(r), r, np.nanmean(r))
    P = np.stack([center_xy[0] + r * np.sin(th), center_xy[1] - r * np.cos(th), zz], -1)
    Nn = np.stack([np.sin(th), -np.cos(th), np.zeros(n)], -1)
    return P, Nn
