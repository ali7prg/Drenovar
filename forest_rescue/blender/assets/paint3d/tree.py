"""Painted-tree reconstruction from the art/02 front view (orthographic, slightly elevated).

Pipeline (all numpy): crop -> fg / wood / foliage masks -> camera (human scale + ground-ellipse
elevation) -> trunk axis + medial-axis limbs -> clump patches (watershed) -> RGBA tiles ->
front cards fitted to the painting + fill cards on a revolved crown volume + rotated limb copies
-> bark texture projected from the painting (+ swatch fill) -> LOD0/1/2 Mesh objects.
"""
import os

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

import analysis
import p3atlas as atl
import geom
import seg
import skel
from geom import Mesh, nrm
from frlib import refs, texproj

SHEET = "02_forest_modular_kit.png"
PPM_TOP = 29.8
ELEV_TOP = 3.5
MAT_BARK, MAT_LEAF = 0, 1


def _smooth1d(a, s):
    return ndi.gaussian_filter1d(np.asarray(a, float), s, mode="nearest") if s else np.asarray(a, float)


class TreeRef:
    """Masks, camera and structure of one painted tree."""

    def __init__(self, cfg, outdir=None):
        self.cfg = cfg
        S = seg.sheet(SHEET)
        self.bg = seg.bg_colour(S)
        x0, y0, x1, y1 = cfg["box"]
        self.box = cfg["box"]
        self.img = S[y0:y1, x0:x1].copy()
        H, W = self.img.shape[:2]
        self.H, self.W = H, W
        excl = [(a - x0, b - y0, c - x0, d - y0) for (a, b, c, d) in cfg.get("exclude", [])]
        fg, _ = seg.fg_mask(self.img, self.bg, thresh=cfg.get("fg_thresh", 10.0), exclude=excl,
                            min_area=cfg.get("fg_min_area", 200), hole_area=cfg.get("hole_area", 0))
        if cfg.get("keep_x"):
            kx0, kx1 = cfg["keep_x"]
            fg[:, :max(0, kx0 - x0)] = False
            fg[:, max(0, kx1 - x0):] = False
        lab_, n = ndi.label(fg)
        if n:
            sizes = ndi.sum(fg, lab_, np.arange(1, n + 1))
            big = int(np.argmax(sizes)) + 1
            # keep the main component and close satellites (leaf clusters detached by a gap)
            near = ndi.binary_dilation(lab_ == big, iterations=cfg.get("satellite_px", 6))
            ids = np.unique(lab_[near & fg])
            fg = np.isin(lab_, ids[ids > 0])
        self.fg_full = fg.copy()
        self.clip = cfg["clip_row"] - y0
        fg[self.clip:] = False
        self.fg = fg
        self.ground = cfg["ground_row"] - y0
        self.ppm = cfg.get("ppm", PPM_TOP)
        self.elev = cfg.get("elev", ELEV_TOP)
        self.wood_raw = analysis.wood_mask(self.img, fg, **cfg.get("wood", {}))
        self._trunk()
        self.view = refs.View(name=cfg["name"], image=self.img, mask=self.fg, d=geom.elevated_dir(self.elev),
                              ppm=self.ppm, ax=float(self.axis_x[-1]), ay=float(self.ground))
        self._limbs()
        self._crown()

    # ------------------------------------------------------------------ trunk
    def _trunk(self):
        cfg = self.cfg
        w = self.wood_raw.copy()
        cr = cfg.get("trunk_close", 4)
        if cr:
            w = ndi.binary_closing(w, structure=morphology.disk(cr)) & self.fg
            w = ndi.binary_fill_holes(w) & self.fg
        clip = self.clip
        ext = np.vstack([w[:clip], np.repeat(w[clip - 1:clip], 80, 0)])
        dt = ndi.distance_transform_edt(ext)[:clip]
        fork = cfg["fork_row"] - self.box[1]
        rows = np.arange(fork, clip)
        x = cfg.get("trunk_x", None)
        x = (x - self.box[0]) if x is not None else None
        ax, rad = [], []
        for v in rows[::-1]:
            run = np.nonzero(w[v] | (dt[v] > 0))[0]
            if not len(run):
                ax.append(ax[-1] if ax else self.W / 2)
                rad.append(rad[-1] if rad else 4)
                continue
            if x is None:
                x = float(np.median(run))
            # contiguous run around x
            lab_, n = ndi.label(dt[v] > 0)
            xi = int(np.clip(round(x), 0, self.W - 1))
            k = lab_[xi]
            if k == 0:
                cand = np.nonzero(lab_)[0]
                k = lab_[cand[np.argmin(np.abs(cand - x))]] if len(cand) else 0
            seg_ = np.nonzero(lab_ == k)[0] if k else np.array([xi])
            j = seg_[np.argmax(dt[v, seg_])]
            ax.append(float(j))
            rad.append(float(dt[v, j]))
            x = 0.7 * x + 0.3 * j
        ax = np.array(ax[::-1])
        rad = np.array(rad[::-1])
        rz = cfg.get("root_zone", 0)
        if rz:
            fgc = ndi.binary_closing(self.fg, structure=morphology.disk(2))
            for i, v in enumerate(rows):
                if v < clip - rz:
                    continue
                lab_, n = ndi.label(fgc[v])
                xi = int(np.clip(round(ax[i]), 0, self.W - 1))
                k = lab_[xi]
                if k:
                    run = np.nonzero(lab_ == k)[0]
                    hw = 0.5 * (run.max() - run.min()) * cfg.get("root_k", 0.85)
                    f = (v - (clip - rz)) / rz
                    rad[i] = max(rad[i], (1 - f) * rad[i] + f * hw)
                    ax[i] = (1 - 0.5 * f) * ax[i] + 0.5 * f * 0.5 * (run.max() + run.min())
        self.trunk_rows = rows
        self.axis_x = _smooth1d(ax, cfg.get("trunk_smooth", 4))
        r = _smooth1d(rad, 2)
        # root flare: widen the lowest rows towards the painted half-width
        self.trunk_r = r * cfg.get("trunk_r_scale", 1.0)
        band = np.zeros_like(self.wood_raw)
        xx = np.arange(self.W)
        for i, v in enumerate(rows):
            band[v] = np.abs(xx - self.axis_x[i]) <= self.trunk_r[i] + 1
        self.trunk_band = band & self.fg_full

    def axis_at(self, v):
        v = float(v)
        if v < self.trunk_rows[0] - 6:
            return None
        i = int(np.clip(round(v - self.trunk_rows[0]), 0, len(self.trunk_rows) - 1))
        return float(self.axis_x[i])

    # ------------------------------------------------------------------ limbs
    def _limbs(self):
        cfg = self.cfg
        wl = self.wood_raw & ~ndi.binary_dilation(self.trunk_band, iterations=1)
        segs, jc, sk, dist = skel.segments(wl)
        limbs = skel.limb_tree(segs, jc, self.trunk_band, self.axis_at, min_r=cfg.get("limb_min_r", 1.3),
                               float_min_r=cfg.get("float_min_r", 1.8), float_min_len=cfg.get("float_min_len", 10))
        rz = cfg.get("root_zone", 0)
        if rz:
            keep = [i for i, l in enumerate(limbs) if np.mean(l["P"][:, 1]) < self.clip - rz * 0.8]
            remap = {o: n for n, o in enumerate(keep)}
            new = []
            for o in keep:
                l = dict(limbs[o])
                if l["parent"] >= 0:
                    l["parent"] = remap.get(l["parent"], -2)
                new.append(l)
            limbs = new
        self.limbs = limbs
        self.skel = sk
        # 2-D coverage of the modelled wood (trunk band + limb disks)
        cov = self.trunk_band.copy().astype(np.uint8)
        for l in limbs:
            P, r = l["P"], l["r"]
            for (x, y), rr in zip(P, r):
                cv2.circle(cov, (int(round(x)), int(round(y))), int(max(1, round(rr))), 1, -1)
        self.wood_cov = cov.astype(bool) & self.fg

    # ------------------------------------------------------------------ crown volume (camera space)
    def _crown(self):
        cfg = self.cfg
        crown = self.fg & ~self.trunk_band
        rows = np.nonzero(crown.any(1))[0]
        v0, v1 = rows.min(), rows.max()
        xl = np.full(self.H, np.nan)
        xr = np.full(self.H, np.nan)
        for v in range(v0, v1 + 1):
            c = np.nonzero(crown[v])[0]
            if len(c) > 2:
                xl[v], xr[v] = c.min(), c.max()
        vv = np.arange(self.H)
        ok = ~np.isnan(xl)
        xl = np.interp(vv, vv[ok], xl[ok])
        xr = np.interp(vv, vv[ok], xr[ok])
        R = _smooth1d((xr - xl) / 2, 5)
        xc = _smooth1d((xl + xr) / 2, 8)
        self.crown_rows = (int(v0), int(v1))
        self.R = np.maximum(R, 2.0)
        self.xc = xc
        self.kd = cfg.get("crown_kd", 0.9)
        # crown radial centre (camera px) for smoothed normals
        self.crown_mid_v = (v0 + v1) / 2

    def depth_px(self, u, v):
        """Half-depth of the crown volume at pixel (u, v), pixels."""
        v = np.clip(np.asarray(v, int), 0, self.H - 1)
        R = self.R[v]
        q = np.clip(R ** 2 - (np.asarray(u, float) - self.xc[v]) ** 2, 0, None)
        return self.kd * np.sqrt(q)

    def normal_cam(self, u, v, t_px):
        """Outward normal of the revolved crown at camera point (u px, v px, t px) -> camera (right, up, depth)."""
        v = np.clip(np.asarray(v, int), 0, self.H - 1)
        R = self.R[v]
        dR = np.gradient(self.R)[v]
        x = np.asarray(u, float) - self.xc[v]
        n = np.stack([x, R * dR, np.asarray(t_px, float) / self.kd ** 2], -1)
        return nrm(n)

    def cam_to_world(self, u, v, t_px):
        return geom.pix_to_world(self.view, u, v, np.asarray(t_px, float) / self.ppm)

    def world_dir(self, n_cam):
        return geom.cam_to_world_dir(self.view, n_cam)

    def masks_preview(self, path):
        ov = seg.overlay(self.img, [(self.fg & ~self.wood_raw, (0.1, 0.8, 0.1)), (self.wood_raw, (0.8, 0.1, 0.8)),
                                    (self.trunk_band, (0.9, 0.5, 0.1)), (~self.fg_full, (0.1, 0.1, 0.5))], 0.5)
        sk = ov.copy()
        sk[self.skel] = (1, 1, 0)
        cov = seg.overlay(self.img, [(self.wood_cov, (0.9, 0.2, 0.2))], 0.6)
        for l in self.limbs:
            pts = np.round(l["P"]).astype(int)
            col = (0, 0, 1) if l["parent"] == -2 else ((0, 1, 1) if l["parent"] == -1 else (1, 1, 1))
            for (x, y) in pts:
                if 0 <= y < self.H and 0 <= x < self.W:
                    cov[y, x] = col
        seg.save(path, np.concatenate([ov, sk, cov], 1))


# ====================================================================== patches & tiles

class Patches:
    def __init__(self, ref, n_target, min_px=40, max_px=None, margin=3, scale=2, region_key=None, extra_masks=()):
        self.ref = ref
        card_region = ref.fg & ~ndi.binary_erosion(ref.wood_cov, iterations=1)
        lbl = seg.clump_patches(ref.img, card_region, n_target=n_target, min_px=min_px)
        if max_px:
            lbl = seg.split_large(lbl, ref.img, max_px)
        self.lbl = lbl
        self.n = int(lbl.max())
        self.tiles, self.rects, self.info = [], [], []
        Lab = seg.lab(ref.img)
        v0, v1 = ref.crown_rows
        for i in range(1, self.n + 1):
            m = lbl == i
            tile, rect = seg.make_tile(ref.img, ref.fg, m, margin=margin, scale=scale, bg=ref.bg)
            ys, xs = np.nonzero(m)
            cu, cv = float(xs.mean()), float(ys.mean())
            vi = int(np.clip(round(cv), 0, ref.H - 1))
            rho = (cu - ref.xc[vi]) / max(ref.R[vi], 1)
            eta = (cv - v0) / max(v1 - v0, 1)
            edge = bool((~ndi.binary_dilation(ref.fg, iterations=2))[max(0, rect[1]):rect[3], max(0, rect[0]):rect[2]].any())
            self.tiles.append(tile)
            self.rects.append(rect)
            self.info.append(dict(c=(cu, cv), area=int(m.sum()), rho=float(rho), eta=float(eta),
                                  lum=float(Lab[..., 0][m].mean()), edge=edge,
                                  w_m=(rect[2] - rect[0]) / ref.ppm, h_m=(rect[3] - rect[1]) / ref.ppm))
        self.extra = []

    def pack(self, key):
        region = atl.REGIONS[key]
        sizes = [(t.shape[1], t.shape[0]) for t in self.tiles]
        pos, s = seg.pack_rects(sizes, (0, 0, region[2], region[3]), pad=3)
        img = np.zeros((region[3], region[2], 4), np.float32)
        self.uv = []
        for t, p in zip(self.tiles, pos):
            if s < 0.999:
                t = cv2.resize(t, (max(1, int(np.ceil(t.shape[1] * s))), max(1, int(np.ceil(t.shape[0] * s)))),
                               interpolation=cv2.INTER_AREA)
            h, w = t.shape[:2]
            img[p[1]:p[1] + h, p[0]:p[0] + w] = t
            ax0, ay0 = region[0] + p[0], region[1] + p[1]
            # half-texel inset to avoid bleeding
            self.uv.append(atl.uv_rect((ax0 + 0.5, ay0 + 0.5, ax0 + w - 0.5, ay0 + h - 0.5)))
        self.atlas_scale = s
        self.region_img = img
        return img, s

    def preview(self, path):
        seg.save(path, seg.label_preview(self.lbl, self.ref.img, 0.45))


# ====================================================================== geometry assembly

def wind_rgba(P, H, Rc, kind, phase, ao, flutter=0.0, base_z=0.0):
    """R sway 0 base -> 1 tips, G flutter, B phase, A AO."""
    z = np.clip((P[:, 2] - base_z) / max(H, 1e-3), 0, 1)
    r = np.linalg.norm(P[:, :2], axis=1) / max(Rc, 1e-3)
    if kind == "trunk":
        sway = 0.25 * z ** 2
    elif kind == "limb":
        sway = np.clip(0.2 + 0.55 * z ** 1.2 + 0.3 * r, 0, 1)
    else:
        sway = np.clip(0.35 + 0.45 * z + 0.35 * r, 0, 1)
    C = np.zeros((len(P), 4))
    C[:, 0] = sway
    C[:, 1] = flutter
    C[:, 2] = phase
    C[:, 3] = ao
    return C


class TreeBuilder:
    def __init__(self, ref, patches, cfg, bark_uv=None):
        self.ref = ref
        self.p = patches
        self.cfg = cfg

    # -------------------------------------------------------------- wood
    def wood_paths(self):
        """World polylines for trunk and limbs (v1 layout). Returns list of dict(P, r, kind, id, parent)."""
        ref = self.ref
        cfg = self.cfg
        rng = np.random.default_rng(cfg.get("seed", 7))
        paths = []
        # trunk: from below ground to the fork, axis points at world y=0
        step = cfg.get("trunk_step", 6)
        rows = ref.trunk_rows
        idx = np.r_[np.arange(0, len(rows), step), len(rows) - 1]
        idx = np.unique(idx)
        u = ref.axis_x[idx]
        v = rows[idx].astype(float)
        r_px = ref.trunk_r[idx]
        Pw = geom.world_at_y(ref.view, u, v, np.zeros(len(u)))
        # extend down to the ground (z=0) and below
        bottom = Pw[-1].copy()
        rb = r_px[-1]
        ext = []
        if bottom[2] > -0.25:
            for zz in (0.5 * bottom[2] - 0.05, -0.4):
                q = bottom.copy()
                q[2] = zz
                ext.append(q)
        Pw = np.vstack([Pw, ext]) if ext else Pw
        fl = cfg.get("flare", 1.12)
        r_px = np.r_[r_px, [rb * fl, rb * fl * 1.08][:len(ext)]]
        Pw = Pw[::-1]
        r_m = r_px[::-1] / ref.ppm
        paths.append(dict(P=Pw, r=r_m, kind="trunk", id=0, parent=-1, depth_scale=cfg.get("trunk_kd", 0.9)))
        # limbs: assign depth (world y) along each limb
        ypos = {}
        slopes = {}
        for li, l in enumerate(ref.limbs):
            P = l["P"].astype(float)
            r = l["r"].astype(float)
            Ps, s = geom.resample_polyline(P, max(cfg.get("limb_step", 5.0), 1.0))
            rs = np.interp(s, np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))], r)
            rs = _smooth1d(rs, 1.0)
            par = l["parent"]
            if par >= 0 and par in ypos:
                y0 = ypos[par][1]
                slope = slopes[par] + rng.uniform(-0.45, 0.45)
            elif par == -1:
                y0 = 0.0
                slope = rng.uniform(-0.8, 0.8)
            else:   # floating limb: pick a depth inside the crown, toward the front half
                u0, v0 = Ps[0]
                D = ref.depth_px(u0, v0) / ref.ppm
                y0 = rng.uniform(-0.55, 0.35) * D
                slope = rng.uniform(-0.6, 0.6)
            sl = s / ref.ppm
            y = y0 + slope * sl
            D = ref.depth_px(Ps[:, 0], Ps[:, 1]) / ref.ppm
            lim = np.maximum(0.55 * D, 0.15)
            y = np.clip(y, -lim, lim)
            Pw = geom.world_at_y(ref.view, Ps[:, 0], Ps[:, 1], y)
            # taper: radius never grows toward the tip
            rr = np.minimum.accumulate(np.maximum(rs, 0.8)) / ref.ppm
            ypos[li] = (y0, float(y[-1]))
            slopes[li] = slope
            paths.append(dict(P=Pw, r=rr, kind="limb", id=li + 1, parent=par, level=l["level"],
                              r_px=float(np.median(rs))))
        return paths

    # -------------------------------------------------------------- foliage cards
    def front_cards(self, scale=1.0, keep=None, seed=11):
        ref, p = self.ref, self.p
        rng = np.random.default_rng(seed)
        cards = []
        for i in range(p.n):
            if keep is not None and i not in keep:
                continue
            x0, y0, x1, y1 = p.rects[i]
            cu, cv = p.info[i]["c"]
            if scale != 1.0:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                x0, x1 = cx + (x0 - cx) * scale, cx + (x1 - cx) * scale
                y0, y1 = cy + (y0 - cy) * scale, cy + (y1 - cy) * scale
            D = float(ref.depth_px(cu, cv))
            t = -D * rng.uniform(0.82, 1.0)
            n_cam = ref.normal_cam(cu, cv, t)
            n_cam = nrm(n_cam + np.array([0, 0, -1.0]) * self.cfg.get("front_bias", 0.8))
            if n_cam[2] > -0.42:            # keep <= ~65 deg from the reference axis
                n_cam = nrm(n_cam + np.array([0, 0, -1.0]) * (0.42 + n_cam[2] + 0.05))
            n_w = ref.world_dir(n_cam)
            cards.append(dict(kind="front", rect=(x0, y0, x1, y1), c=(cu, cv), t_px=t, n=n_w, tile=i,
                              flip=False))
        return cards

    def front_depth_map(self, cards):
        """Camera depth (px) of the visible front layer per pixel (inf where nothing)."""
        ref = self.ref
        dm = np.full((ref.H, ref.W), np.inf)
        for c in cards:
            m = self.p.lbl == (c["tile"] + 1)
            dm[m] = np.minimum(dm[m], c["t_px"])
        # wood: trunk front ~ -r * kd, limbs ~ their depth (approx: crown depth * 0.3)
        tb = ref.trunk_band
        for i, v in enumerate(ref.trunk_rows):
            row = tb[v]
            if row.any():
                dm[v, row] = np.minimum(dm[v, row], -ref.trunk_r[i] * 0.9)
        wl = ref.wood_cov & ~tb
        dm[wl] = np.minimum(dm[wl], -0.2 * ref.depth_px(np.nonzero(wl)[1], np.nonzero(wl)[0]))
        return dm

    def lobes(self, seed, n=None):
        """Big clump lobes on the crown dome: (phi, eta, amplitude, sigma_phi, sigma_eta)."""
        rng = np.random.default_rng(seed)
        n = n or self.cfg.get("n_lobes", 14)
        L = []
        for i in range(n):
            L.append((rng.uniform(-np.pi, np.pi), rng.uniform(0.05, 0.8), rng.uniform(0.10, 0.2),
                      rng.uniform(0.35, 0.55), rng.uniform(0.10, 0.16)))
        return L

    @staticmethod
    def lobe_field(lobes, ph, eta):
        b = np.zeros(np.shape(ph))
        g = np.zeros(np.shape(ph) + (2,))
        for (p0, e0, A, sp, se) in lobes:
            dp = (np.asarray(ph) - p0 + np.pi) % (2 * np.pi) - np.pi
            de = np.asarray(eta) - e0
            w = A * np.exp(-(dp / sp) ** 2 - (de / se) ** 2)
            b += w
            g[..., 0] += w * dp / sp
            g[..., 1] += w * de / se
        return b, g

    def card_footprint_ok(self, V, fg, thresh):
        u, v, _ = self.ref.view.project(V)
        pts = np.stack([u, v], 1)
        x0, y0 = np.floor(pts.min(0)).astype(int) - 1
        x1, y1 = np.ceil(pts.max(0)).astype(int) + 2
        H, W = fg.shape
        if x1 <= 0 or y1 <= 0 or x0 >= W or y0 >= H:
            return 0.0
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillConvexPoly(m, np.round(pts - [x0, y0]).astype(np.int32), 1)
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x1), min(H, y1)
        inside = m[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0].astype(bool) & fg[cy0:cy1, cx0:cx1]
        tot = m.sum()
        return float(inside.sum()) / max(1, tot)

    def fill_cards(self, n_fill, front_dm, size_k=1.0, seed=5, n_inner=0, min_dist_k=0.55, choose=None,
                   up_bias=0.35, foot=0.86):
        ref, p = self.ref, self.p
        cfg = self.cfg
        rng = np.random.default_rng(seed)
        v0, v1 = ref.crown_rows
        fg_e = ref.fg
        lobes = self.lobes(seed + 101)
        vs = np.arange(v0, v1 + 1)
        R = ref.R[vs]
        dR = np.gradient(ref.R)[vs]
        w_row = R * np.sqrt(1 + dR ** 2)
        eta_r = (vs - v0) / max(v1 - v0, 1)
        w_row = w_row * (1.0 + self.cfg.get("top_weight", 1.6) * np.clip(1 - eta_r / 0.6, 0, 1))
        w_row = w_row / w_row.sum()
        M = n_fill * 14
        vv = rng.choice(vs, size=M, p=w_row) + rng.uniform(-0.5, 0.5, M)
        ph = rng.uniform(-np.pi, np.pi, M)
        vi = np.clip(np.round(vv).astype(int), 0, ref.H - 1)
        eta = (vv - v0) / max(v1 - v0, 1)
        bump, grad = self.lobe_field(lobes, ph, eta)
        kr = 0.86 + bump * 0.9 + rng.uniform(-0.04, 0.04, M)
        side = np.abs(np.cos(ph)) > 0.75
        kr = np.where(side, np.minimum(kr, 0.98), kr)
        x = ref.xc[vi] + ref.R[vi] * kr * np.cos(ph)
        t = ref.kd * ref.R[vi] * kr * np.sin(ph)
        # clumpier: keep candidates with probability rising on lobes
        keep_p = np.clip(0.3 + bump / 0.2, 0, 1)
        ok = rng.random(M) < keep_p
        xi = np.clip(np.round(x).astype(int), 0, ref.W - 1)
        ok &= fg_e[vi, xi]
        ok &= t > front_dm[vi, xi] + 0.3 * ref.ppm
        cand = np.nonzero(ok)[0]
        rng.shuffle(cand)
        info = p.info
        areas = np.array([q["area"] for q in info], float)
        typ = np.median([q["w_m"] for q in info if q["area"] > np.median(areas)]) * ref.ppm * size_k
        rmin = typ * min_dist_k
        etas = np.array([q["eta"] for q in info])
        rhos = np.array([q["rho"] for q in info])
        lums = np.array([q["lum"] for q in info])
        edges = np.array([q["edge"] for q in info])
        lum_med = np.median(lums)
        grid = {}
        cards = []
        for c in cand:
            q = np.array([x[c], vv[c], t[c]])
            key = tuple((q // rmin).astype(int))
            bad = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for o in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), []):
                            if np.sum((o - q) ** 2) < rmin * rmin:
                                bad = True
                                break
                        if bad:
                            break
                    if bad:
                        break
                if bad:
                    break
            if bad:
                continue
            u, v, tt = q
            n_cam = ref.normal_cam(u, v, tt)
            n_w = ref.world_dir(n_cam)
            # lobe shading: tilt away from the lobe centre (tops of clumps face up/out)
            tang_up = ref.world_dir(np.array([0.0, 1.0, 0.0]))
            tang_ph = ref.world_dir(np.array([-np.sin(ph[c]), 0.0, np.cos(ph[c]) * ref.kd]))
            n_w = nrm(n_w + 2.2 * (grad[c, 1] * -tang_up + grad[c, 0] * tang_ph))
            if n_w[2] > -0.25:
                n_w = nrm(n_w + up_bias * np.array([0, 0, 1.0]))
            n_w = nrm(n_w + rng.normal(0, 0.12, 3))
            wgt = np.exp(-((etas - eta[c]) / 0.2) ** 2) * np.sqrt(areas)
            sd = np.cos(ph[c])
            if abs(sd) > 0.55:
                wgt *= np.where(edges & (np.abs(rhos) > 0.45), 3.0, 0.6)
            if n_w[2] > -0.3:
                wgt *= np.exp(np.clip((lums - lum_med) / self.cfg.get("lum_pref", 5.0), -4, 4))
            if choose is not None:
                wgt *= choose
            wgt = wgt / wgt.sum()
            ti = int(rng.choice(len(info), p=wgt))
            flip = bool(np.sign(rhos[ti]) != np.sign(sd)) if abs(sd) > 0.4 else bool(rng.random() < 0.5)
            P3 = ref.cam_to_world(np.array([u]), np.array([v]), np.array([tt]))[0]
            size = rng.uniform(0.95, 1.18) * size_k
            roll = rng.normal(0, 0.22)
            if n_w[2] > self.cfg.get("flip_top_nz", 0.4):
                # upper slopes are seen from above: tuck the painted clump shadow under the card above
                roll += np.pi
            placed = None
            for attempt in range(3):
                Vc = self._fill_quad(P3, n_w, ti, size, roll)
                if self.card_footprint_ok(Vc, fg_e, foot) >= foot:
                    placed = (P3, size)
                    break
                # shrink and pull toward the crown axis
                ax_w = ref.cam_to_world(np.array([ref.xc[int(v)]]), np.array([v]), np.array([0.0]))[0]
                P3 = ax_w + (P3 - ax_w) * 0.85
                size *= 0.78
            if placed is None:
                continue
            grid.setdefault(key, []).append(q)
            cards.append(dict(kind="fill", P=placed[0], n=n_w, tile=ti, flip=flip, size=placed[1], roll=roll,
                              c=(u, v), t_px=tt))
            if len(cards) >= n_fill:
                break
        # inner cards (block see-through from above; darker patches)
        tries = 0
        n_in = 0
        while n_in < n_inner and tries < n_inner * 20:
            tries += 1
            vq = rng.uniform(v0 + 0.08 * (v1 - v0), v1 - 0.15 * (v1 - v0))
            vi_ = int(vq)
            a = rng.uniform(-np.pi, np.pi)
            kk = rng.uniform(0.35, 0.72)
            u = ref.xc[vi_] + ref.R[vi_] * kk * np.cos(a)
            tt = ref.kd * ref.R[vi_] * kk * np.sin(a)
            ui = int(np.clip(u, 0, ref.W - 1))
            if not fg_e[vi_, ui] or tt < front_dm[vi_, ui] + 0.3 * ref.ppm:
                continue
            wgt = np.exp(-((etas - (vq - v0) / max(v1 - v0, 1)) / 0.25) ** 2) * np.sqrt(areas)
            wgt *= np.exp(-((lums - lum_med) / 10.0) ** 2)
            wgt /= wgt.sum()
            ti = int(rng.choice(len(info), p=wgt))
            n_w = ref.world_dir(ref.normal_cam(u, vq, tt))
            n_w = nrm(n_w + rng.normal(0, 0.3, 3) + np.array([0, 0, 0.4]))
            P3 = ref.cam_to_world(np.array([u]), np.array([vq]), np.array([tt]))[0]
            size = rng.uniform(1.0, 1.25) * size_k
            roll = rng.normal(0, 0.4)
            Vc = self._fill_quad(P3, n_w, ti, size, roll)
            if self.card_footprint_ok(Vc, fg_e, foot) < foot:
                continue
            cards.append(dict(kind="inner", P=P3, n=n_w, tile=ti, flip=bool(rng.random() < 0.5), size=size,
                              roll=roll, c=(u, vq), t_px=tt))
            n_in += 1
        return cards

    def _fill_quad(self, P3, n, ti, size, roll):
        w = self.p.info[ti]["w_m"] * size
        h = self.p.info[ti]["h_m"] * size
        up = np.array([0, 0, 1.0])
        rt = nrm(np.cross(up, n)) if abs(np.dot(up, n)) < 0.97 else nrm(np.cross([1.0, 0, 0], n))
        upv = nrm(np.cross(n, rt))
        upv = upv * np.cos(roll) + rt * np.sin(roll)
        V, _, _, _, _ = geom.free_card(P3, n, upv, w, h, (0, 0, 1, 1), np.zeros(4))
        return V

    # -------------------------------------------------------------- mesh assembly
    def assemble(self, paths, cards, bark_uv, sides_trunk=14, sides_limb=6, min_limb_r_px=0.0, copies=None,
                 tree_h=None, crown_r=None, seed=3):
        ref, p = self.ref, self.p
        rng = np.random.default_rng(seed)
        bark = Mesh()
        leaf = Mesh()
        H = tree_h or 10.0
        Rc = crown_r or 5.0
        phase_of = {}
        for path in paths:
            if path["kind"] == "limb" and path.get("r_px", 9) < min_limb_r_px:
                continue
            pid = path["id"]
            par = path.get("parent", -1)
            ph = phase_of.get(par, rng.random()) if par >= 0 else rng.random()
            phase_of[pid] = (ph + rng.uniform(-0.06, 0.06)) % 1.0 if par >= 0 else ph
            sides = sides_trunk if path["kind"] == "trunk" else (sides_limb if path.get("r_px", 9) >= 2.5 else max(4, sides_limb - 2))
            uvr = bark_uv[pid]
            V, T, UV, C, N = geom.tube(path["P"], path["r"], sides, uvr, np.zeros(4),
                                       depth_scale=path.get("depth_scale"), ref_side=ref.view.d)
            C = wind_rgba(V, H, Rc, path["kind"], 0.0 if path["kind"] == "trunk" else phase_of[pid], 1.0)
            bark.add(V, T, UV, C, N, MAT_BARK)
        for (Rm, tvec, mirror, sc) in (copies or []):
            for path in paths:
                if path["kind"] != "limb" or path.get("r_px", 0) < min_limb_r_px:
                    continue
                if path.get("parent", -1) == -2 and path.get("r_px", 0) < 3.0:
                    continue
                P = path["P"] - tvec
                P = P * sc
                P = P @ Rm.T + tvec
                sides = sides_limb if path.get("r_px", 9) >= 2.5 else max(4, sides_limb - 2)
                V, T, UV, C, N = geom.tube(P, path["r"] * sc, sides, bark_uv[path["id"]], np.zeros(4),
                                           ref_side=ref.view.d)
                C = wind_rgba(V, H, Rc, "limb", rng.random(), 1.0)
                bark.add(V, T, UV, C, N, MAT_BARK)
        crown_c = ref.cam_to_world(np.array([ref.xc[int(ref.crown_mid_v)]]), np.array([ref.crown_mid_v]),
                                   np.array([0.0]))[0]
        crown_ax = np.array([ref.R[int(ref.crown_mid_v)], ref.R[int(ref.crown_mid_v)] * ref.kd,
                             (ref.crown_rows[1] - ref.crown_rows[0]) / 2]) / ref.ppm
        for c in cards:
            ti = c["tile"]
            uvr = p.uv[ti]
            if c["kind"] == "front":
                V, T, UV, _, N = geom.front_card(ref.view, c["rect"], c["c"], c["t_px"] / ref.ppm, c["n"], uvr,
                                                 np.zeros(4), flip=False)
                ao = 1.0
            else:
                w = p.info[ti]["w_m"] * c["size"]
                h = p.info[ti]["h_m"] * c["size"]
                up = np.array([0, 0, 1.0])
                n = c["n"]
                rt = nrm(np.cross(up, n)) if abs(np.dot(up, n)) < 0.97 else nrm(np.cross([1.0, 0, 0], n))
                upv = nrm(np.cross(n, rt))
                upv = upv * np.cos(c["roll"]) + rt * np.sin(c["roll"])
                V, T, UV, _, N = geom.free_card(c["P"], n, upv, w, h, uvr, np.zeros(4), flip=c["flip"])
                ao = 0.9 if c["kind"] == "fill" else 0.78
            # smoothed crown normals (ellipsoid around the crown centre), blended with the card normal
            sn = nrm((V - crown_c) / crown_ax ** 2)
            Nn = nrm(sn * 0.75 + N * 0.25)
            cen = V.mean(0)
            fl = 0.45 + 0.55 * np.linalg.norm(V - cen, axis=1) / max(np.linalg.norm(V[0] - cen), 1e-6)
            sector = (np.arctan2(cen[1], cen[0]) / (2 * np.pi) + 0.5)
            ph = (np.floor(sector * 7) / 7 + 0.37 * np.floor(cen[2] / 2.5)) % 1.0
            C = wind_rgba(V, H, Rc, "leaf", ph, ao, flutter=fl)
            leaf.add(V, T, UV, C, Nn, MAT_LEAF)
        return bark, leaf


# ====================================================================== bark texture

def tri_id_buffer(V, T, tri_ids, view):
    """Nearest triangle id per reference pixel (-1 none) and its depth."""
    W, H = view.size
    u, v, dep = view.project(V)
    zb = np.full((H, W), np.inf)
    ib = np.full((H, W), -1, np.int64)
    U, Vv, D = u[T], v[T], dep[T]
    x0 = np.clip(np.floor(U.min(1)).astype(int), 0, W)
    x1 = np.clip(np.ceil(U.max(1)).astype(int) + 1, 0, W)
    y0 = np.clip(np.floor(Vv.min(1)).astype(int), 0, H)
    y1 = np.clip(np.ceil(Vv.max(1)).astype(int) + 1, 0, H)
    for t in np.nonzero((x1 > x0) & (y1 > y0))[0]:
        X, Y = np.meshgrid(np.arange(x0[t], x1[t]), np.arange(y0[t], y1[t]))
        ax_, bx_, cx_ = U[t]
        ay_, by_, cy_ = Vv[t]
        den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
        if abs(den) < 1e-12:
            continue
        l1 = ((by_ - cy_) * (X - cx_) + (cx_ - bx_) * (Y - cy_)) / den
        l2 = ((cy_ - ay_) * (X - cx_) + (ax_ - cx_) * (Y - cy_)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
        if not inside.any():
            continue
        z = l1 * D[t, 0] + l2 * D[t, 1] + l3 * D[t, 2]
        sub = zb[y0[t]:y1[t], x0[t]:x1[t]]
        isub = ib[y0[t]:y1[t], x0[t]:x1[t]]
        better = inside & (z < sub)
        sub[better] = z[better]
        isub[better] = tri_ids[t]
    return ib, zb


def swatch(box, size=None):
    S = seg.sheet(SHEET)
    x0, y0, x1, y1 = box
    sw = S[y0:y1, x0:x1].astype(np.float32)
    if size:
        sw = cv2.resize(sw, size, interpolation=cv2.INTER_LANCZOS4)
    return sw


def bark_texture(ref, bark_mesh_orig, path_ids, size=1024, swatch_box=None, wood_mask=None, delight_floor=18.0):
    """Project the painting onto the (original, non-copied) wood mesh; fill unseen texels from visible
    painted bark (pull-push) + high-pass detail of the art/02 bark swatch."""
    V, T, UV, C, N, M = bark_mesh_orig.arrays()
    uvc = UV[T]
    Tx = texproj.rasterize_uv(V, T, uvc, size, N)
    ib, zb = tri_id_buffer(V, T, path_ids, ref.view)
    yy, xx = np.nonzero(Tx.valid)
    P = Tx.pos[yy, xx]
    u, v, dep = ref.view.project(P)
    ui = np.clip(np.round(u).astype(int), 0, ref.W - 1)
    vi = np.clip(np.round(v).astype(int), 0, ref.H - 1)
    own = path_ids[Tx.tri[yy, xx]]
    wm = ref.wood_cov if wood_mask is None else wood_mask
    ok = wm[vi, ui]
    match = np.zeros(len(ui), bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            match |= ib[np.clip(vi + dy, 0, ref.H - 1), np.clip(ui + dx, 0, ref.W - 1)] == own
    ok &= match
    col = np.zeros((size, size, 3), np.float32)
    known = np.zeros((size, size), bool)
    img = ref.img.astype(np.float32)
    samp = texproj._bilinear(img, u, v)[:, :3]
    col[yy[ok], xx[ok]] = samp[ok]
    known[yy[ok], xx[ok]] = True
    # de-light only the extreme shadows (Lab L floor)
    lab = seg.lab(np.clip(col, 0, 1))
    Lc = lab[..., 0]
    lift = np.clip((delight_floor - Lc) / delight_floor, 0, 1) * known
    if lift.any():
        from skimage import color as skc
        lab[..., 0] = Lc + lift * (delight_floor - Lc) * 0.6
        col = np.where(known[..., None], skc.lab2rgb(lab).astype(np.float32), col)
    filled = texproj.fill(col.astype(np.float64), known).astype(np.float32)
    out = filled.copy()
    if swatch_box is not None:
        sw = swatch(swatch_box)
        sh, sw_w = sw.shape[:2]
        # tile the swatch over the texture (scale ~ painted bark density)
        reps_y = int(np.ceil(size / sh)) + 1
        reps_x = int(np.ceil(size / sw_w)) + 1
        tiled = np.tile(sw, (reps_y, reps_x, 1))[:size, :size]
        hp = tiled - cv2.GaussianBlur(tiled, (0, 0), 6)
        unknown = Tx.valid & ~known
        soft = cv2.GaussianBlur(unknown.astype(np.float32), (0, 0), 2.0)
        out = out + hp * soft[..., None] * 0.9
    out = np.clip(out, 0, 1)
    bl = cv2.GaussianBlur(out, (0, 0), 1.0)
    out = np.clip(out + 0.35 * (out - bl), 0, 1)
    out = texproj.dilate_margin(out.astype(np.float64), Tx.valid, px=6).astype(np.float32)
    return out, known, Tx


def bark_maps(col):
    g = cv2.cvtColor((np.clip(col, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    h = g - cv2.GaussianBlur(g, (0, 0), 8)
    valid = np.ones(g.shape, bool)
    n = texproj.height_to_normal(h, valid, strength=3.0)
    r = np.clip(0.82 + 0.15 * (0.5 - g), 0.6, 1.0)
    return n, r
