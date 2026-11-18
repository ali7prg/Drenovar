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
MAT_BARK, MAT_LEAF, MAT_LEAF_VOL = 0, 1, 2


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
        if cfg.get("trunk_taper"):
            rb = float(np.median(r[-12:]))
            f = (rows - rows[0]) / max(rows[-1] - rows[0], 1)
            r = np.minimum(r, rb * (cfg["trunk_taper"] + (1 - cfg["trunk_taper"]) * f))
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
    def __init__(self, ref, n_target, min_px=40, max_px=None, margin=3, scale=2, region_key=None, extra_masks=(),
                 mode="clumps", strip_w=12, strip_h=90):
        self.ref = ref
        card_region = ref.fg & ~ndi.binary_erosion(ref.wood_cov, iterations=1)
        if mode == "strips":
            lbl = seg.strip_patches(ref.img, card_region, width=strip_w, max_h=strip_h, min_px=min_px)
        else:
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
            ytop = ys.min() + (ys.max() - ys.min()) / 3.0
            top_px = m & (np.arange(ref.H)[:, None] <= ytop)
            top_lum = float(Lab[..., 0][top_px].mean()) if top_px.any() else float(Lab[..., 0][m].mean())
            chroma = float(np.hypot(Lab[..., 1][m], Lab[..., 2][m]).mean())
            self.info.append(dict(c=(cu, cv), area=int(m.sum()), rho=float(rho), eta=float(eta),
                                  lum=float(Lab[..., 0][m].mean()), top_lum=top_lum, edge=edge, chroma=chroma,
                                  w_m=(rect[2] - rect[0]) / ref.ppm, h_m=(rect[3] - rect[1]) / ref.ppm))
        self.extra = []

    def grade(self, dh=0.0, dl=0.0, kc=1.0):
        from skimage import color as skc
        for i, t_ in enumerate(self.tiles):
            lab_ = seg.lab(t_[..., :3])
            C = np.hypot(lab_[..., 1], lab_[..., 2]) * kc
            h = np.arctan2(lab_[..., 2], lab_[..., 1]) + np.radians(dh)
            lab_ = np.stack([np.clip(lab_[..., 0] + dl, 0, 100), C * np.cos(h), C * np.sin(h)], -1)
            self.tiles[i] = np.concatenate([np.clip(skc.lab2rgb(lab_), 0, 1).astype(np.float32), t_[..., 3:4]], 2)

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

    def add_fronds(self, max_tiers=12, min_gap_m=0.45, scale=2):
        """Side-view tier fronds cut from the painted conifer: band between consecutive tier tips, from the trunk
        axis to the silhouette edge, per side. Appended as extra tiles (kind 'frond')."""
        ref = self.ref
        fg = ref.fg & ~ref.trunk_band
        v0, v1 = ref.crown_rows
        fr = []
        for side in (-1, 1):
            Rs = np.zeros(ref.H)
            for v in range(v0, v1 + 1):
                ax = ref.axis_at(v)
                ax = ref.axis_x[0] if ax is None else ax
                cols = np.nonzero(ref.fg[v])[0]
                c = cols[cols > ax] - ax if side > 0 else ax - cols[cols < ax]
                Rs[v] = c.max() if len(c) else 0
            Rsm = ndi.gaussian_filter1d(Rs, 2.0)
            from scipy.signal import find_peaks
            pk, _ = find_peaks(Rsm[v0:v1 + 1], distance=max(3, int(min_gap_m * ref.ppm)), prominence=1.5)
            pk = pk + v0
            prev = v0
            for vt in pk:
                b0, b1 = int(prev), int(min(ref.clip - 1, vt + 4))
                if b1 - b0 < 6:
                    prev = vt
                    continue
                ax = ref.axis_at(vt)
                ax = ref.axis_x[0] if ax is None else ax
                m = np.zeros_like(fg)
                m[b0:b1] = fg[b0:b1]
                xx = np.arange(ref.W)
                m &= (xx[None, :] > ax - 2) if side > 0 else (xx[None, :] < ax + 2)
                if m.sum() < 60:
                    prev = vt
                    continue
                fr.append(dict(mask=m, side=side, v_tip=float(vt), R_px=float(Rs[int(vt)]), band=(b0, b1), ax=float(ax)))
                prev = vt - int(0.25 * (vt - prev))
        self.fronds = []
        fr = [f for f in fr if (f["v_tip"] - v0) / max(v1 - v0, 1) < self.ref.cfg.get("frond_eta_max", 0.93)]
        for f in fr:
            tile, rect = seg.make_tile(ref.img, ref.fg, f["mask"], margin=1, scale=scale, bg=ref.bg,
                                       bg_thresh=self.ref.cfg.get("frond_bg_thresh", 22.0))
            x0, y0, x1, y1 = rect
            eta = (f["v_tip"] - v0) / max(v1 - v0, 1)
            self.tiles.append(tile)
            self.rects.append(rect)
            self.info.append(dict(c=((x0 + x1) / 2, (y0 + y1) / 2), area=int(f["mask"].sum()), rho=float(f["side"]),
                                  eta=float(eta), lum=60.0, top_lum=60.0, edge=True, w_m=(x1 - x0) / ref.ppm,
                                  h_m=(y1 - y0) / ref.ppm, frond=True, side=f["side"], R_m=f["R_px"] / ref.ppm,
                                  ax_frac=float(np.clip((f["ax"] - x0) / max(x1 - x0, 1), 0, 1))))
            self.fronds.append(len(self.tiles) - 1)
        return len(self.fronds)

    def add_palette_copy(self, key, name, lab_fn, scale=None):
        """Recoloured copies of all current tiles (Lab transform lab_fn(lab)->lab) packed into region `key`.
        Copies get info['palette'] = name and keep the geometry metadata; self.pal[name] = index offset map."""
        import p3atlas
        from skimage import color as skc
        region = p3atlas.REGIONS[key]
        src_ids = list(range(len(self.tiles)))
        tiles = []
        for i in src_ids:
            t_ = self.tiles[i]
            lab = seg.lab(t_[..., :3])
            lab = lab_fn(lab)
            rgb = np.clip(skc.lab2rgb(np.clip(lab, [0, -128, -128], [100, 127, 127])), 0, 1).astype(np.float32)
            tiles.append(np.concatenate([rgb, t_[..., 3:4]], 2))
        sizes = [(t_.shape[1], t_.shape[0]) for t_ in tiles]
        pos, s = seg.pack_rects(sizes, (0, 0, region[2], region[3]), pad=3)
        img = np.zeros((region[3], region[2], 4), np.float32)
        mp = {}
        for i, t_, p_ in zip(src_ids, tiles, pos):
            if s < 0.999:
                t_ = cv2.resize(t_, (max(1, int(np.ceil(t_.shape[1] * s))), max(1, int(np.ceil(t_.shape[0] * s)))),
                                interpolation=cv2.INTER_AREA)
            h, w = t_.shape[:2]
            img[p_[1]:p_[1] + h, p_[0]:p_[0] + w] = t_
            ax0, ay0 = region[0] + p_[0], region[1] + p_[1]
            inf = dict(self.info[i])
            inf["palette"] = name
            lab0 = seg.lab(t_[..., :3])
            al = t_[..., 3] > 0.5
            if al.any():
                inf["lum"] = float(lab0[..., 0][al].mean())
                inf["top_lum"] = inf["lum"] + (self.info[i]["top_lum"] - self.info[i]["lum"])
            self.info.append(inf)
            self.uv.append(p3atlas.uv_rect((ax0 + 0.5, ay0 + 0.5, ax0 + w - 0.5, ay0 + h - 0.5)))
            self.tiles.append(t_)
            mp[i] = len(self.info) - 1
        p3atlas.save_region(key, img, {"palette": name, "tiles": len(tiles), "scale": s})
        if not hasattr(self, "pal"):
            self.pal = {}
        self.pal[name] = mp
        return s

    def add_hires(self, key, sheet, box, target_mask=None, rosette_px=800, m_per_px=None, l_shift=4.0, hue=(70, 100),
                  n_composite=14, keep_original=False):
        """Append colour-matched hi-res clump tiles from another painting (top/oblique card sources)."""
        import hires
        import p3atlas
        tiles = hires.extract(sheet, box, rosette_px=rosette_px, hue=hue)
        Lab = seg.lab(self.ref.img)
        C = np.hypot(Lab[..., 1], Lab[..., 2])
        sel = (C > 35) & (Lab[..., 0] > 52) & self.ref.fg if target_mask is None else target_mask
        orig = [dict(t_) for t_ in tiles]
        tiles = hires.match_palette(tiles, Lab[sel], l_shift=l_shift)
        tiles = hires.composite(tiles, n=n_composite) + tiles
        pal_tiles = []
        if keep_original:
            # the same rosettes/composites in their original art/07 colours (grove palette), chroma x0.85
            from skimage import color as skc
            for o in orig:
                lab_ = seg.lab(o["rgba"][..., :3])
                lab_[..., 1:] *= 0.85
                o["rgba"] = np.concatenate([np.clip(skc.lab2rgb(lab_), 0, 1).astype(np.float32), o["rgba"][..., 3:4]], 2)
            pal_tiles = hires.composite(orig, n=n_composite) + orig
        allt = tiles + pal_tiles
        img, uvs, s = hires.pack(allt, key)
        p3atlas.save_region(key, img, {"source": sheet, "box": box, "tiles": len(allt)})
        mpp = m_per_px or (1.0 / self.ref.ppm)
        for j, (tl, uv) in enumerate(zip(allt, uvs)):
            h, w = tl["rgba"].shape[:2]
            inf = dict(c=(0, 0), area=tl["area"], rho=0.0, eta=0.0, lum=tl["lum"] + l_shift,
                       top_lum=tl["lum"] + l_shift + 6, edge=False, w_m=w * mpp, h_m=h * mpp, hires=True)
            if j >= len(tiles):
                inf["palette"] = "grove"
            self.info.append(inf)
            self.uv.append(uv)
        self.n_hires = len(allt)
        if keep_original:
            if not hasattr(self, "pal"):
                self.pal = {}
            mp = self.pal.setdefault("grove", {})
            base0 = len(self.info) - len(allt)
            for j in range(len(tiles)):
                mp[base0 + j] = base0 + len(tiles) + j
        return len(allt)


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
            for zz in (0.45 * bottom[2], -0.3):
                q = bottom.copy()
                q[2] = zz
                ext.append(q)
        Pw = np.vstack([Pw, ext]) if ext else Pw
        fl = cfg.get("flare", 1.0)
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
            if cfg.get("ground_limbs") and Ps[0, 1] >= ref.clip - 8 and rs[0] >= cfg.get("ground_limb_min_r", 3.0):
                # a stem (e.g. birch side trunk) cut by the clip row: continue it vertically into the ground
                q = Pw[0].copy()
                q[2] = -0.3
                Pw = np.vstack([q[None], Pw])
                rr = np.r_[rr[0] * 1.05, rr]
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
            lim = -np.cos(np.radians(self.cfg.get("front_tilt_max", 50)))
            for _ in range(6):              # keep the tilt from the reference axis <= front_tilt_max
                if n_cam[2] <= lim:
                    break
                n_cam = nrm(n_cam + np.array([0, 0, -0.25]))
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

    def card_footprint_ok(self, V, fg, thresh, front_dm=None, margin_m=0.15):
        u, v, tq = self.ref.view.project(V)
        if front_dm is not None:
            H, W = fg.shape
            for uu, vv, t_ in zip(u, v, tq):
                ui, vi = int(round(uu)), int(round(vv))
                if 0 <= ui < W and 0 <= vi < H and np.isfinite(front_dm[vi, ui]) and \
                        t_ * self.ref.ppm < front_dm[vi, ui] + margin_m * self.ref.ppm:
                    return 0.0
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

    def lobe_cards(self, n_cards, front_dm, size_k=1.0, seed=5, n_lobes=12, lobe_r=0.32, min_dist_k=0.45,
                   foot=0.86, up_bias=0.45, inset=0.74, n_inner=0):
        """Foliage masses: cards clustered on hemispherical caps around lobe centres on the crown dome
        (gaps between masses show the limbs, as in the painted top views)."""
        ref, p = self.ref, self.p
        rng = np.random.default_rng(seed)
        v0, v1 = ref.crown_rows
        info = p.info
        areas = np.array([q["area"] for q in info], float)
        etas = np.array([q["eta"] for q in info])
        rhos = np.array([q["rho"] for q in info])
        lums = np.array([q["lum"] for q in info])
        edges = np.array([q["edge"] for q in info])
        lum_med = np.median(lums)
        Rmax = float(ref.R[v0:v1 + 1].max())
        rl_px = lobe_r * Rmax
        # lobe centres (camera px): apex lobe + ring(s)
        lobes = [(-np.pi / 2 + rng.normal(0, 0.3), 0.06)]
        ring = []
        for i in range(n_lobes - 1):
            ph = -np.pi / 2 + (i + 0.5) * 2 * np.pi / (n_lobes - 1) + rng.normal(0, 0.18)
            eta = rng.uniform(0.18, 0.62)
            ring.append((ph, eta))
        lobes += ring
        L = []
        for ph, eta in lobes:
            v = v0 + eta * (v1 - v0)
            vi = int(np.clip(round(v), 0, ref.H - 1))
            k = inset * rng.uniform(0.92, 1.05)
            u = ref.xc[vi] + ref.R[vi] * k * np.cos(ph)
            tt = ref.kd * ref.R[vi] * k * np.sin(ph)
            if eta < 0.1:
                v = v0 + rl_px * 0.9
                u = ref.xc[int(v)] + rng.normal(0, 0.1) * ref.R[int(v)]
                tt = rng.normal(0, 0.15) * ref.R[int(v)]
            c = ref.cam_to_world(np.array([u]), np.array([v]), np.array([tt]))[0]
            ax = ref.world_dir(ref.normal_cam(u, v, tt))
            ax = nrm(ax + np.array([0, 0, 0.5]))
            L.append((c, ax, eta))
        typ = np.median([q["w_m"] for q in info if q["area"] > np.median(areas)]) * size_k
        rmin = typ * min_dist_k
        per = max(4, n_cards // max(1, len(L)))
        cards = []
        placed_pts = []
        for li, (c, ax, eta) in enumerate(L):
            got = 0
            tries = 0
            rl = rl_px / ref.ppm * rng.uniform(0.85, 1.15)
            while got < per and tries < per * 25:
                tries += 1
                # direction in the cap around the lobe axis (polar angle up to ~105 deg)
                d = nrm(rng.normal(0, 1, 3))
                if np.dot(d, ax) < -0.25:
                    d = d - 1.6 * np.dot(d, ax) * ax
                    d = nrm(d)
                P3 = c + d * rl * rng.uniform(0.75, 1.05)
                if any(np.sum((P3 - q) ** 2) < rmin * rmin for q in placed_pts[-400:]):
                    continue
                u, v, tdep = ref.view.project(P3[None])
                u, v, tdep = float(u[0]), float(v[0]), float(tdep[0]) * ref.ppm
                ui, vi = int(round(u)), int(round(v))
                if not (0 <= ui < ref.W and 0 <= vi < ref.H) or not ref.fg[vi, ui]:
                    continue
                if tdep < front_dm[vi, ui] + 0.3 * ref.ppm:
                    continue
                uw = self.cfg.get("mass_up", 0.55)
                n_w = nrm(d * (1 - uw) + uw * np.array([0, 0, 1.0]) + rng.normal(0, 0.08, 3))
                wgt = np.sqrt(areas) * np.exp(-((etas - eta) / 0.35) ** 2)
                wgt *= np.exp(np.clip((lums - lum_med) / self.cfg.get("lum_pref", 5.0) * (0.6 + 0.6 * max(n_w[2], 0)), -4, 4))
                side = abs(np.dot(d, ref.view.right))
                if side > 0.6:
                    wgt *= np.where(edges, 2.0, 0.8)
                wgt /= wgt.sum()
                ti = int(rng.choice(len(info), p=wgt))
                size = rng.uniform(0.9, 1.15) * size_k
                roll = rng.normal(0, 0.25) + (np.pi if n_w[2] > self.cfg.get("flip_top_nz", 0.4) else 0.0)
                ok = False
                for attempt in range(3):
                    Vc = self._fill_quad(P3, n_w, ti, size, roll)
                    if self.card_footprint_ok(Vc, ref.fg, foot, front_dm) >= foot:
                        ok = True
                        break
                    P3 = c + (P3 - c) * 0.8
                    size *= 0.8
                if not ok:
                    continue
                flip = bool(rng.random() < 0.5)
                cards.append(dict(kind="fill", P=P3, n=n_w, tile=ti, flip=flip, size=size, roll=roll, c=(u, v),
                                  t_px=tdep))
                placed_pts.append(P3)
                got += 1
        return cards

    def volume_cards(self, n_clumps, front_cards, front_dm, size_k=1.0, seed=5, min_dist_k=0.7, foot=0.86,
                     front_extra_frac=0.65, extra_size=1.0, shell_pow=1.4, top_boost=1.2, max_cards=None):
        """Crown as a filled volume: every clump = crossed cards (top-facing + oblique + outward side).

        * front clumps (projectively fitted cards) get a top and an oblique card behind them (same painted patch);
        * clump centres fill the revolved crown volume at several depths (shell / mid / core);
        * top cards use the brightest-topped painted clumps, interior clumps darker patches + AO.
        All cards stay behind the painted front layer and inside the silhouette in the art/02 view."""
        ref, p = self.ref, self.p
        rng = np.random.default_rng(seed)
        info = p.info
        areas = np.array([q["area"] for q in info], float)
        etas = np.array([q["eta"] for q in info])
        lums = np.array([q["lum"] for q in info])
        tlums = np.array([q["top_lum"] for q in info])
        edges = np.array([q["edge"] for q in info])
        lum_med = np.median(lums)
        lp = self.cfg.get("lum_pref", 4.0)
        v0, v1 = ref.crown_rows
        Z = np.array([0, 0, 1.0])
        cards = []

        def add(P3, n, ti, size, roll, ao, kind="fill", flip=None, top_part=False):
            ok = False
            tp = self.cfg.get("top_part", 0.6) if top_part else 1.0
            for attempt in range(3):
                Vc = self._fill_quad(P3, n, ti, size, roll, hfrac=tp)
                if self.card_footprint_ok(Vc, ref.fg, foot, front_dm) >= foot:
                    ok = True
                    break
                size *= 0.8
            if not ok:
                return False
            cards.append(dict(kind=kind, P=P3, n=n, tile=ti, flip=bool(rng.random() < 0.5) if flip is None else flip,
                              size=size, roll=roll, ao=ao, hfrac=tp))
            return True

        def pick(eta, mode, depth_k):
            w = np.sqrt(areas) * np.exp(-((etas - eta) / 0.3) ** 2)
            if mode == "top":
                w *= np.exp(np.clip((tlums - np.median(tlums)) / (lp * 0.8), -5, 5))
            elif mode == "side":
                w *= np.where(edges, 1.8, 1.0) * np.exp(np.clip((lums - lum_med) / (lp * 1.5), -4, 4))
            else:
                w *= np.exp(np.clip((lums - lum_med) / (lp * 1.2), -4, 4))
            if depth_k < 0.55:    # interior: darker leaves
                w *= np.exp(np.clip(-(lums - lum_med) / 6.0, -4, 4))
            w /= w.sum()
            return int(rng.choice(len(info), p=w))

        # 1) crossed cards behind the painted front clumps
        if front_extra_frac > 0:
            order = np.argsort([-info[c["tile"]]["area"] for c in front_cards])
            for j in order[: int(len(order) * front_extra_frac)]:
                c = front_cards[j]
                ti = c["tile"]
                cu, cv = c["c"]
                C = ref.cam_to_world(np.array([cu]), np.array([cv]), np.array([c["t_px"]]))[0]
                hs = max(info[ti]["w_m"], info[ti]["h_m"]) * extra_size
                eta = (cv - v0) / max(v1 - v0, 1)
                # top-facing card, pushed behind the front card
                Pt = C + ref.view.d * (0.5 * hs + 0.2) + Z * 0.15 * hs
                add(Pt, nrm(Z + rng.normal(0, 0.12, 3)), pick(eta, "top", 1.0), hs / max(info[ti]["w_m"], 1e-3) * 1.1,
                    rng.uniform(-np.pi, np.pi), 1.0, top_part=True)
                # oblique card (45 deg, outward + up)
                out = c["n"] - np.dot(c["n"], Z) * Z
                out = nrm(out) if np.linalg.norm(out) > 1e-3 else -ref.view.d
                Po = C + ref.view.d * (0.4 * hs + 0.2)
                add(Po, nrm(out + Z * 1.0 + rng.normal(0, 0.1, 3)), ti, 1.0 * extra_size, rng.normal(0, 0.2), 1.0)
        # 2) clump centres through the crown volume
        typ = np.median([q["w_m"] for q in info if q["area"] > np.median(areas)]) * size_k
        rmin = typ * min_dist_k
        vs = np.arange(v0, v1 + 1)
        w_row = ref.R[vs] ** 2
        eta_r = (vs - v0) / max(v1 - v0, 1)
        w_row = w_row * (1.0 + top_boost * np.clip(1 - eta_r / 0.55, 0, 1))
        w_row /= w_row.sum()
        M = n_clumps * 30
        vv = rng.choice(vs, size=M, p=w_row) + rng.uniform(-0.5, 0.5, M)
        ph = rng.uniform(-np.pi, np.pi, M)
        kk = rng.random(M) ** (1.0 / (1.0 + shell_pow))          # radial fraction, denser near the shell
        kk = np.clip(kk, 0.12, 0.98)
        vi = np.clip(np.round(vv).astype(int), 0, ref.H - 1)
        uu = ref.xc[vi] + ref.R[vi] * kk * np.cos(ph)
        tt = ref.kd * ref.R[vi] * kk * np.sin(ph)
        ui = np.clip(np.round(uu).astype(int), 0, ref.W - 1)
        ok = ref.fg[vi, ui] & (tt > front_dm[vi, ui] + 0.25 * ref.ppm)
        eta_all = (vv - v0) / max(v1 - v0, 1)
        low = eta_all > self.cfg.get("low_eta", 0.58)
        lobe_az = rng.uniform(-np.pi, np.pi, self.cfg.get("low_lobes", 5))
        dphi = np.min(np.abs((ph[:, None] - lobe_az[None, :] + np.pi) % (2 * np.pi) - np.pi), axis=1)
        ok &= ~low | ((dphi < 0.45) & (kk > 0.6))
        cand = np.nonzero(ok)[0]
        centres = []
        grid = {}
        n_ok = 0
        for c in cand:
            P3 = ref.cam_to_world(np.array([uu[c]]), np.array([vv[c]]), np.array([tt[c]]))[0]
            key = tuple((P3 // rmin).astype(int))
            bad = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for o in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), []):
                            if np.sum((o - P3) ** 2) < rmin * rmin:
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
            grid.setdefault(key, []).append(P3)
            eta = (vv[c] - v0) / max(v1 - v0, 1)
            k = kk[c]
            n_out = ref.world_dir(ref.normal_cam(uu[c], vv[c], tt[c]))
            horiz = n_out - np.dot(n_out, Z) * Z
            horiz = nrm(horiz) if np.linalg.norm(horiz) > 1e-3 else nrm(rng.normal(0, 1, 3) * [1, 1, 0])
            ao = 1.0 if k > 0.72 else (0.93 if k > 0.45 else 0.82)
            size = typ * rng.uniform(0.95, 1.2) * (1.0 if k > 0.55 else 0.9)
            # three crossed cards
            n_top = nrm(Z + rng.normal(0, 0.15, 3))
            n_obl = nrm(horiz + Z + rng.normal(0, 0.12, 3))
            n_side = nrm(horiz + rng.normal(0, 0.15, 3) + Z * 0.15)
            for n, mode, roll in ((n_top, "top", rng.uniform(-np.pi, np.pi)), (n_obl, "obl", rng.normal(0, 0.2)),
                                  (n_side, "side", rng.normal(0, 0.15))):
                ti = pick(eta, mode, k)
                sz = size / max(info[ti]["w_m"], 1e-3)
                if mode == "top":
                    sz *= self.cfg.get("top_scale", 1.25)
                add(P3 + rng.normal(0, 0.12 * typ, 3), n, ti, sz, roll, ao, top_part=(mode == "top"))
            n_ok += 1
            if n_ok >= n_clumps or (max_cards and len(cards) >= max_cards):
                break
        return cards

    def mass_cards(self, front_cards, front_dm, size_k=1.0, seed=5, n_masses=12, mass_r=0.34, clumps_per=26,
                   foot=0.86, front_extra_frac=0.6, max_cards=None, core_cards=40, placement="dome", anchors=None,
                   curtains=0):
        """Cumulus crown: big flattened masses (ellipsoids) of crossed clump cards. Card normals radiate from
        each mass centre (painted-light shading -> bright top, darker underside), AO falls toward the
        underside, gaps between masses show the limbs / dark core."""
        ref, p = self.ref, self.p
        cfg = self.cfg
        rng = np.random.default_rng(seed)
        info = p.info
        areas = np.array([q["area"] for q in info], float)
        etas = np.array([q["eta"] for q in info])
        lums = np.array([q["lum"] for q in info])
        tlums = np.array([q["top_lum"] for q in info])
        lum_med = np.median(lums)
        lp = cfg.get("lum_pref", 4.0)
        v0, v1 = ref.crown_rows
        Z = np.array([0, 0, 1.0])
        cards = []

        base_m = np.array([not q.get("palette") for q in info])
        hires_m = np.array([bool(q.get("hires")) for q in info]) & base_m
        chs_all = np.array([q.get("chroma", 40.0) for q in info])
        p_hi = cfg.get("p_hires", 0.75)

        def pick(eta, mode):
            if mode in ("top", "obl") and hires_m.any() and rng.random() < p_hi:
                w = np.where(hires_m, areas, 0.0)          # prefer the big rosette clusters
                w = w * np.exp(np.clip((lums - np.median(lums[hires_m])) / 6.0, -3, 3))
                w /= w.sum()
                return int(rng.choice(len(info), p=w))
            w = np.where(hires_m | ~base_m, 0.0, np.sqrt(areas) * np.exp(-((etas - eta) / 0.35) ** 2))
            if mode == "top" and cfg.get("top_by_chroma"):
                ref_c = np.percentile(chs_all[base_m & ~hires_m], 65)
                w *= np.exp(np.clip((chs_all - ref_c) / 5.0, -6, 4)) * np.exp(-((lums - np.percentile(lums[base_m], 60)) / 12.0) ** 2)
            elif mode == "top":
                # brightest-topped painted clumps (top quartile)
                w *= np.exp(np.clip((tlums - np.percentile(tlums[~hires_m & base_m], 70)) / (lp * 0.6), -6, 4))
            elif mode == "shade":
                w *= np.exp(-((lums - np.percentile(lums[base_m & ~hires_m], 35)) / 6.0) ** 2)
            elif mode == "under":
                chs = np.array([q.get("chroma", 40.0) for q in info])
                w *= np.exp(-((lums - np.percentile(lums[~hires_m], 30)) / 5.0) ** 2)
                w *= (chs > np.median(chs[~hires_m]) * 0.9)
            else:
                w *= np.exp(np.clip((lums - lum_med) / (lp * 1.3), -4, 4))
            w /= w.sum()
            return int(rng.choice(len(info), p=w))

        foot = cfg.get("foot", foot)

        def add(P3, n, ti, size, roll, ao, nshade, hfrac=1.0):
            for attempt in range(3):
                Vc = self._fill_quad(P3, n, ti, size, roll, hfrac=hfrac)
                if self.card_footprint_ok(Vc, ref.fg, foot, front_dm) >= foot:
                    cards.append(dict(kind="fill", P=P3, n=n, tile=ti, flip=bool(rng.random() < 0.5), size=size,
                                      roll=roll, ao=ao, hfrac=hfrac, nshade=nshade))
                    return True
                size *= 0.82
            return False

        # front clumps: crossed top + oblique cards behind them (same painted area)
        order = np.argsort([-info[c["tile"]]["area"] for c in front_cards])
        for j in order[: int(len(order) * front_extra_frac)]:
            c = front_cards[j]
            ti = c["tile"]
            cu, cv = c["c"]
            C = ref.cam_to_world(np.array([cu]), np.array([cv]), np.array([c["t_px"]]))[0]
            hs = max(info[ti]["w_m"], info[ti]["h_m"])
            eta = (cv - v0) / max(v1 - v0, 1)
            if eta > cfg.get("front_extra_eta", 0.55):
                continue
            Pt = C + ref.view.d * (0.5 * hs + 0.2) + Z * 0.15 * hs
            tt = pick(eta, "top")
            add(Pt, nrm(Z + rng.normal(0, 0.12, 3)), tt, hs / max(info[tt]["w_m"], 1e-3) * 1.1,
                rng.uniform(-np.pi, np.pi), 1.0, None, hfrac=cfg.get("top_part", 0.6))
            out = c["n"] - np.dot(c["n"], Z) * Z
            out = nrm(out) if np.linalg.norm(out) > 1e-3 else -ref.view.d
            add(C + ref.view.d * (0.4 * hs + 0.2), nrm(out + Z + rng.normal(0, 0.1, 3)), ti, 1.0,
                rng.normal(0, 0.2), 1.0, None)
        # mass centres on the upper / outer crown
        Rmax = float(ref.R[v0:v1 + 1].max())
        masses = []
        zsq = cfg.get("mass_zscale", 0.68)
        if placement == "tiers":
            # conifer: flat whorl tiers on the cone surface (seen from above as stacked layers)
            n_t = cfg.get("n_tiers", 9)
            for ti_ in range(n_t):
                eta = 0.06 + 0.9 * (ti_ + 0.5) / n_t
                v = v0 + eta * (v1 - v0)
                vi = int(np.clip(round(v), 0, ref.H - 1))
                Rv = ref.R[vi]
                m = max(3, int(round(2 * np.pi * 0.7 * Rv / (cfg.get("tier_mass_px", 26)))))
                off = rng.uniform(0, 2 * np.pi)
                for j in range(m):
                    ph = off + 2 * np.pi * j / m
                    u = ref.xc[vi] + Rv * 0.72 * np.cos(ph)
                    tq = ref.kd * Rv * 0.72 * np.sin(ph)
                    C = ref.cam_to_world(np.array([u]), np.array([v]), np.array([tq]))[0]
                    masses.append((C, max(0.35 * Rv / ref.ppm, 0.45), eta))
            n_masses = 0
        elif placement == "umbrella":
            # art/01 grove oak: 7-9 distinct domed lobes on a broad, lifted crown (top lobe + ring at varied heights)
            axis_top = geom.world_at_y(ref.view, np.array([ref.axis_x[0]]), np.array([float(ref.trunk_rows[0])]),
                                       np.array([0.0]))[0]
            Rc = float(ref.R[v0:v1 + 1].max()) / ref.ppm * cfg.get("umb_rk", 1.0)
            Htot = (ref.ground - v0) / ref.ppm
            zb, zt = cfg.get("umb_base", 0.55) * Htot, 0.97 * Htot
            n_l = cfg.get("umb_n", 8)
            r_l = cfg.get("umb_lobe_r", 0.3) * Rc
            rz_ = r_l * zsq
            a0 = rng.uniform(0, 2 * np.pi)
            masses.append((np.array([axis_top[0], axis_top[1], zt - rz_ * 0.9]), r_l * 0.95, 0.05))
            for i in range(n_l - 1):
                ang = a0 + 2 * np.pi * i / (n_l - 1) + rng.normal(0, 0.18)
                rho = Rc * rng.uniform(0.5, 0.82)
                hi = (i % 2 == 0)
                z = zb + rz_ + (zt - zb - 2.2 * rz_) * (rng.uniform(0.55, 0.95) if hi else rng.uniform(0.05, 0.45))
                C = np.array([axis_top[0] + rho * np.cos(ang), axis_top[1] + rho * np.sin(ang), z])
                masses.append((C, r_l * rng.uniform(0.85, 1.1), float(np.clip(1 - (z - zb) / max(zt - zb, 1e-3), 0, 1))))
            n_masses = 0
        elif placement == "anchors" and anchors is not None and len(anchors):
            A = np.asarray(anchors)
            md = cfg.get("mass_min_dist", 0.0)
            if md > 0:      # separated clusters: Poisson-disk selection of anchors
                order_ = rng.permutation(len(A))
                sel = []
                for i in order_:
                    if all(np.linalg.norm(A[i] - A[j]) >= md for j in sel):
                        sel.append(i)
                    if len(sel) >= n_masses:
                        break
            else:
                sel = rng.choice(len(A), size=min(n_masses, len(A)), replace=False)
            for i in sel:
                C = A[i].copy()
                r_m = mass_r * Rmax / ref.ppm * rng.uniform(0.8, 1.2)
                u, v, tq = ref.view.project(C[None])
                ui = int(np.clip(round(u[0]), 0, ref.W - 1))
                vi = int(np.clip(round(v[0]), 0, ref.H - 1))
                # masses in front of the painted front layer are pushed back behind it (front stays exact)
                need = front_dm[vi, ui] / ref.ppm + 0.15 + 0.6 * r_m if np.isfinite(front_dm[vi, ui]) else -1e9
                if tq[0] < need:
                    C = C + ref.view.d * (need - tq[0])
                eta = float(np.clip((v[0] - v0) / max(v1 - v0, 1), 0, 1))
                masses.append((C, r_m, eta))
            n_masses = 0
        n_top = max(1, n_masses // 5)
        for i in range(n_masses):
            if i < n_top:
                eta = rng.uniform(0.04, 0.2)
                ph = rng.uniform(-np.pi, np.pi)
                k = rng.uniform(0.0, 0.45)
            else:
                eta = rng.uniform(cfg.get("mass_eta_min", 0.18), cfg.get("mass_eta_max", 0.62))
                ph = -np.pi / 2 + (i - n_top + 0.5) * 2 * np.pi / (n_masses - n_top) + rng.normal(0, 0.2)
                k = rng.uniform(*cfg.get("grove_k", (0.5, 0.78)))
            v = v0 + eta * (v1 - v0)
            vi = int(np.clip(round(v), 0, ref.H - 1))
            u = ref.xc[vi] + ref.R[vi] * k * np.cos(ph)
            tq = ref.kd * ref.R[vi] * k * np.sin(ph)
            C = ref.cam_to_world(np.array([u]), np.array([v]), np.array([tq]))[0]
            r = mass_r * Rmax / ref.ppm * rng.uniform(0.85, 1.2)
            masses.append((C, r, eta))
        typ = np.median([q["w_m"] for q in info if q["area"] > np.median(areas)]) * size_k
        edges_m = np.array([q["edge"] for q in info])
        self.last_masses = list(masses)
        for (C, r, eta) in masses:
            rz = r * zsq
            # cumulus cap: Fibonacci points on the lobe ellipsoid, ordered top -> rim -> underside
            n_c = clumps_per
            gold = np.pi * (3 - np.sqrt(5))
            for j in range(n_c):
                zf = 1 - (j + 0.5) / n_c * (1.0 - cfg.get("lobe_zf_min", -0.55))   # 1 (top) .. zf_min (underside)
                rr = np.sqrt(max(0.0, 1 - zf * zf))
                a = j * gold + rng.uniform(-0.25, 0.25)
                dvec = np.array([rr * np.cos(a), rr * np.sin(a), zf])
                P3 = C + dvec * np.array([r, r, rz]) * rng.uniform(0.85, 1.0)
                nshade = nrm(dvec / np.array([r, r, rz]))
                if zf > 0.35:
                    mode, hf, ao = "top", cfg.get("top_part", 0.6), 1.0
                    n = nrm(nshade + Z * 0.6)
                elif zf > -0.15:
                    mode, hf, ao = cfg.get("side_mode", "side"), 1.0, cfg.get("ao_side", 0.95)
                    n = nrm(nshade + Z * 0.35)
                else:
                    mode, hf, ao = "under", 1.0, cfg.get("ao_under", 0.8)
                    n = nrm(nshade * np.array([1, 1, 0.3]) + rng.normal(0, 0.1, 3))
                ti = pick(eta, mode)
                if mode == "side" and not info[ti].get("hires"):
                    pass
                size = typ * rng.uniform(0.95, 1.2) * (cfg.get("top_scale", 1.0) if mode == "top" else 0.95)
                sz = size / max(info[ti]["w_m"], 1e-3)
                roll = rng.uniform(-np.pi, np.pi) if mode == "top" else rng.normal(0, 0.15)
                add(P3, n, ti, sz, roll, ao, nshade, hfrac=hf if not info[ti].get("hires") else 1.0)
                if max_cards and len(cards) >= max_cards:
                    break
            if max_cards and len(cards) >= max_cards:
                break
        # hanging curtains around the rim (willow): outward-facing cards, strand patches of the lower crown
        if curtains:
            edges = np.array([q["edge"] for q in info])
            for i in range(curtains):
                eta = rng.uniform(cfg.get("curtain_eta", (0.3, 0.85))[0], cfg.get("curtain_eta", (0.3, 0.85))[1])
                v = v0 + eta * (v1 - v0)
                vi = int(np.clip(round(v), 0, ref.H - 1))
                ph = rng.uniform(-np.pi, np.pi)
                k = rng.uniform(0.82, 0.98)
                u = ref.xc[vi] + ref.R[vi] * k * np.cos(ph)
                tq = ref.kd * ref.R[vi] * k * np.sin(ph)
                P3 = ref.cam_to_world(np.array([u]), np.array([v]), np.array([tq]))[0]
                n_out = ref.world_dir(ref.normal_cam(u, v, tq))
                horiz = n_out - np.dot(n_out, Z) * Z
                horiz = nrm(horiz) if np.linalg.norm(horiz) > 1e-3 else nrm(rng.normal(0, 1, 3) * [1, 1, 0])
                w = np.sqrt(areas) * np.exp(-((etas - eta) / 0.25) ** 2) * np.where(edges, 2.0, 1.0)
                w /= w.sum()
                ti = int(rng.choice(len(info), p=w))
                add(P3, nrm(horiz + Z * 0.25 + rng.normal(0, 0.08, 3)), ti, rng.uniform(1.0, 1.25) * size_k,
                    rng.normal(0, 0.08), 0.95, None)
        # dark core (gaps between masses show leaves, not the ground)
        for i in range(core_cards):
            vq = rng.uniform(v0 + 0.15 * (v1 - v0), v0 + cfg.get("core_eta_max", 0.6) * (v1 - v0))
            vi = int(vq)
            a = rng.uniform(-np.pi, np.pi)
            k = rng.uniform(0.0, 0.45)
            u = ref.xc[vi] + ref.R[vi] * k * np.cos(a)
            tq = ref.kd * ref.R[vi] * k * np.sin(a)
            P3 = ref.cam_to_world(np.array([u]), np.array([vq]), np.array([tq]))[0]
            ti = pick((vq - v0) / max(v1 - v0, 1), "side")
            add(P3, nrm(Z * 0.6 + rng.normal(0, 0.45, 3)), ti, rng.uniform(0.8, 1.0) * size_k, rng.uniform(-np.pi, np.pi),
                0.85, None)
        return cards

    def whorl_cards(self, front_dm, seed=5, density=1.0, droop=(4, 14), keep_every=1, max_cards=None, inner=True,
                    foot=0.86, width_k=1.0, len_k=1.0, segs=3):
        """Conifer: drooping radial frond cards per whorl (tier), textured with painted side-view tier fronds.
        Frond cards facing the reference camera are shortened so the painted front layer stays in front."""
        ref, p = self.ref, self.p
        rng = np.random.default_rng(seed)
        cfg = self.cfg
        info = p.info
        fronds = [i for i, q in enumerate(info) if q.get("frond") and not q.get("palette")]
        if not fronds:
            return []
        Z = np.array([0, 0, 1.0])
        tips = sorted(set(round(info[i]["eta"], 2) for i in fronds))
        cards = []
        v0, v1 = ref.crown_rows
        etas = np.array([info[i]["eta"] for i in fronds])
        # whorls: every painted tier tip (both sides merged) + an extra interleaved whorl between tips
        wh = sorted(set([float(e) for e in etas]))
        merged = []
        for e in wh:
            if not merged or e - merged[-1] > 0.035:
                merged.append(e)
        extra = [(a + b) / 2 for a, b in zip(merged[:-1], merged[1:])] if cfg.get("interleave", True) else []
        whorls = sorted(merged + extra)[::keep_every]
        for wi, eta in enumerate(whorls):
            v = v0 + eta * (v1 - v0)
            vi = int(np.clip(round(v), 0, ref.H - 1))
            ax = ref.axis_at(v)
            ax = ref.axis_x[0] if ax is None else ax
            Rpx = float(ref.R[vi])
            # trunk point of this whorl (world, on the axis plane y=0) and frond length
            base = geom.world_at_y(ref.view, np.array([ax]), np.array([v - 0.35 * Rpx * np.tan(np.radians(22))]),
                                   np.array([0.0]))[0]
            j = fronds[int(np.argmin(np.abs(etas - eta)))]
            L = max(0.35, info[j]["R_m"] if abs(info[j]["eta"] - eta) < 0.06 else Rpx / ref.ppm) * len_k
            Hm = info[j]["h_m"]
            m = int(np.clip(round(2 * np.pi * 0.75 * L / max(0.55 * Hm * width_k, 0.3) * density), 4, 18))
            off = rng.uniform(0, 2 * np.pi)
            for k in range(m):
                phi = off + 2 * np.pi * k / m + rng.normal(0, 0.12)
                dirr = np.array([np.cos(phi), np.sin(phi), 0.0])
                toward_cam = -np.dot(dirr, ref.view.d) / np.linalg.norm(ref.view.d[:2])
                Lk = L * rng.uniform(0.88, 1.05) * (0.72 if toward_cam > 0.55 else 1.0)
                cand = [i for i in fronds if abs(info[i]["eta"] - eta) < 0.09] or [j]
                ti = int(rng.choice(cand))
                dr = np.radians(rng.uniform(*droop))
                s = np.linspace(0, 1, segs + 1)
                P = base[None] + (Lk * s)[:, None] * dirr[None] - Z[None] * (Lk * np.tan(dr) * s ** 1.6)[:, None]
                P[:, 2] += rng.normal(0, 0.05)
                tang = nrm(np.gradient(P, axis=0))
                sidev = nrm(np.cross(Z, dirr))
                nn = nrm(np.cross(tang, sidev))
                nn[nn[:, 2] < 0] *= -1
                wk = info[ti]["h_m"] * width_k * rng.uniform(0.9, 1.1)
                widths = wk * np.interp(s, [0, 0.33, 0.66, 1.0], [0.55, 0.85, 1.0, 0.9])
                # footprint / depth test on the card outline
                Lv = P - sidev * widths[:, None] / 2
                Rv = P + sidev * widths[:, None] / 2
                quad = np.vstack([Lv[0], Lv[-1], Rv[-1], Rv[0]])
                if self.card_footprint_ok(quad, ref.fg, foot, front_dm, margin_m=0.1) < foot:
                    Lk *= 0.8
                    P = base[None] + (Lk * s)[:, None] * dirr[None] - Z[None] * (Lk * np.tan(dr) * s ** 1.6)[:, None]
                    Lv = P - sidev * widths[:, None] / 2
                    Rv = P + sidev * widths[:, None] / 2
                    quad = np.vstack([Lv[0], Lv[-1], Rv[-1], Rv[0]])
                    if self.card_footprint_ok(quad, ref.fg, foot, front_dm, margin_m=0.1) < foot:
                        continue
                ao = 1.0 if eta < 0.5 else 0.94
                cards.append(dict(kind="frond", P=P, widths=widths, n=nn, side=sidev, tile=ti, ao=ao,
                                  flipv=bool(rng.random() < 0.5)))
                if max_cards and len(cards) >= max_cards:
                    return cards
            # inner dark disk (blocks see-through between fronds): 2 crossed horizontal cards of an under tile
            if inner and L > 0.8:
                under = [i for i, q in enumerate(info) if not q.get("frond") and not q.get("hires") and not q.get("palette")]
                lums = np.array([info[i]["lum"] for i in under])
                ti = under[int(np.argmin(np.abs(lums - np.percentile(lums, 25))))]
                for a in (0.0, np.pi / 2):
                    c0 = base - Z * 0.25 * L * np.tan(np.radians(22))
                    n0 = nrm(Z + rng.normal(0, 0.05, 3))
                    sz = 1.1 * L / max(info[ti]["w_m"], 1e-3)
                    Vq = self._fill_quad(c0, n0, ti, sz, a)
                    if self.card_footprint_ok(Vq, ref.fg, foot, front_dm, margin_m=0.1) >= foot:
                        cards.append(dict(kind="fill", P=c0, n=n0, tile=ti, flip=False, size=sz, roll=a, ao=0.8))
        return cards

    def _fill_quad(self, P3, n, ti, size, roll, hfrac=1.0):
        w = self.p.info[ti]["w_m"] * size
        h = self.p.info[ti]["h_m"] * size * hfrac
        up = np.array([0, 0, 1.0])
        rt = nrm(np.cross(up, n)) if abs(np.dot(up, n)) < 0.97 else nrm(np.cross([1.0, 0, 0], n))
        upv = nrm(np.cross(n, rt))
        upv = upv * np.cos(roll) + rt * np.sin(roll)
        V, _, _, _, _ = geom.free_card(P3, n, upv, w, h, (0, 0, 1, 1), np.zeros(4))
        return V

    # -------------------------------------------------------------- mesh assembly
    def assemble(self, paths, cards, bark_uv, sides_trunk=14, sides_limb=6, min_limb_r_px=0.0, copies=None,
                 tree_h=None, crown_r=None, seed=3, copy_min_r_px=0.0):
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
                if path["kind"] != "limb" or path.get("r_px", 0) < max(min_limb_r_px, copy_min_r_px):
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
            if c["kind"] == "frond":
                P_, wv, nn, sv = c["P"], c["widths"], c["n"], c["side"]
                kq = len(P_)
                Vf = np.empty((2 * kq, 3))
                Vf[0::2] = P_ - sv * wv[:, None] / 2
                Vf[1::2] = P_ + sv * wv[:, None] / 2
                u0_, v0_, u1_, v1_ = uvr
                inf = p.info[ti]
                axf = inf.get("ax_frac", 0.0)
                s_ = np.linspace(0, 1, kq)
                # along the frond = tile x from the trunk axis to the tip (mirrored for left-side tiles)
                if inf.get("side", 1) > 0:
                    us = u0_ + (u1_ - u0_) * (axf + (1 - axf) * s_)
                else:
                    us = u1_ - (u1_ - u0_) * ((1 - axf) + axf * s_ - (1 - axf)) if False else \
                        u0_ + (u1_ - u0_) * (axf - axf * s_)
                va, vb = (v0_, v1_) if not c.get("flipv") else (v1_, v0_)
                UVf = np.empty((2 * kq, 2))
                UVf[0::2, 0] = us
                UVf[1::2, 0] = us
                UVf[0::2, 1] = va
                UVf[1::2, 1] = vb
                Tf = []
                for i in range(kq - 1):
                    a_, b_, c_, d_ = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
                    Tf += [[a_, b_, c_], [a_, c_, d_]]
                Nf = np.repeat(nn, 2, axis=0)
                Nf = nrm(Nf * 0.7 + nrm(Vf - crown_c) * 0.3)
                rr_ = np.linalg.norm(Vf[:, :2] - Vf[:1, :2], axis=1)
                fl = 0.3 + 0.7 * rr_ / max(rr_.max(), 1e-6)
                sector = (np.arctan2(P_[-1, 1], P_[-1, 0]) / (2 * np.pi) + 0.5)
                ph = (np.floor(sector * 7) / 7 + 0.37 * np.floor(P_[0, 2] / 2.5)) % 1.0
                Cf = wind_rgba(Vf, H, Rc, "leaf", ph, c.get("ao", 1.0), flutter=fl)
                leaf.add(Vf, np.array(Tf), UVf, Cf, Nf, MAT_LEAF_VOL if self.cfg.get("vol_material") else MAT_LEAF)
                continue
            if c["kind"] == "front":
                V, T, UV, _, N = geom.front_card(ref.view, c["rect"], c["c"], c["t_px"] / ref.ppm, c["n"], uvr,
                                                 np.zeros(4), flip=False)
                ao = 1.0
            else:
                hf = c.get("hfrac", 1.0)
                w = p.info[ti]["w_m"] * c["size"]
                h = p.info[ti]["h_m"] * c["size"] * hf
                if hf < 1.0:          # upper (bright) part of the tile only
                    u0_, v0_, u1_, v1_ = uvr
                    uvr = (u0_, v1_ - (v1_ - v0_) * hf, u1_, v1_)
                up = np.array([0, 0, 1.0])
                n = c["n"]
                rt = nrm(np.cross(up, n)) if abs(np.dot(up, n)) < 0.97 else nrm(np.cross([1.0, 0, 0], n))
                upv = nrm(np.cross(n, rt))
                upv = upv * np.cos(c["roll"]) + rt * np.sin(c["roll"])
                V, T, UV, _, N = geom.free_card(c["P"], n, upv, w, h, uvr, np.zeros(4), flip=c["flip"])
                ao = c.get("ao", 0.9 if c["kind"] == "fill" else 0.78)
            # smoothed crown normals (ellipsoid around the crown centre), blended with the card normal;
            # mass cards use their mass normal (cumulus shading)
            sn = nrm((V - crown_c) / crown_ax ** 2)
            if c.get("nshade") is not None:
                sn = nrm(sn * 0.35 + np.asarray(c["nshade"]) * 0.65)
            Nn = nrm(sn * 0.75 + N * 0.25)
            cen = V.mean(0)
            fl = 0.45 + 0.55 * np.linalg.norm(V - cen, axis=1) / max(np.linalg.norm(V[0] - cen), 1e-6)
            sector = (np.arctan2(cen[1], cen[0]) / (2 * np.pi) + 0.5)
            ph = (np.floor(sector * 7) / 7 + 0.37 * np.floor(cen[2] / 2.5)) % 1.0
            C = wind_rgba(V, H, Rc, "leaf", ph, ao, flutter=fl)
            leaf.add(V, T, UV, C, Nn, MAT_LEAF if (c["kind"] == "front" or not self.cfg.get("vol_material")) else MAT_LEAF_VOL)
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


def bark_texture(ref, bark_mesh_orig, path_ids, size=1024, swatch_box=None, wood_mask=None, delight_floor=18.0,
                 swatch_px_per_m=None, swatch_m=0.6):
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
    facing = np.abs(Tx.nrm[yy, xx] @ ref.view.d)
    ok &= facing > 0.38          # grazing texels would smear the painted outline -> fill instead
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
        if swatch_px_per_m and swatch_m:
            s_ = swatch_px_per_m * swatch_m / sw.shape[1]
            sw = cv2.resize(sw, (max(8, int(sw.shape[1] * s_)), max(8, int(sw.shape[0] * s_))),
                            interpolation=cv2.INTER_AREA if s_ < 1 else cv2.INTER_LANCZOS4)
        sh, sw_w = sw.shape[:2]
        reps_y = int(np.ceil(size / sh)) + 1
        reps_x = int(np.ceil(size / sw_w)) + 1
        # mirrored tiling (seamless) of the painted swatch
        tile2 = np.concatenate([np.concatenate([sw, sw[:, ::-1]], 1), np.concatenate([sw[::-1], sw[::-1, ::-1]], 1)], 0)
        tiled = np.tile(tile2, (reps_y // 2 + 1, reps_x // 2 + 1, 1))[:size, :size]
        unknown = Tx.valid & ~known
        if known.any():
            # colour-match the swatch to the projected painted bark of this tree (mean/std per channel)
            kp = col[known]
            m_s, s_s = tiled.reshape(-1, 3).mean(0), tiled.reshape(-1, 3).std(0) + 1e-4
            m_k, s_k = kp.mean(0), kp.std(0) + 1e-4
            k_ = np.clip(s_k / s_s, 0.6, 1.4)
            tiled = np.clip((tiled - m_s) * k_ + m_k, 0, 1)
        soft = cv2.GaussianBlur(unknown.astype(np.float32), (0, 0), 3.0)
        soft = np.where(unknown, np.maximum(soft, 0.65), soft * 0.5)
        out = out * (1 - soft[..., None]) + tiled * soft[..., None]
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
