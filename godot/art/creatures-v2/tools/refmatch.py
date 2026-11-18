"""Reference matching for creatures-v2: silhouettes of the FRONT / LEFT SIDE / REAR views on the kit concept
sheets against orthographic silhouettes of the sculpt, with the best uniform scale and offset.

  python -I refmatch.py refs <sheet dir> <out dir>            # cut + segment the sheet views (GrabCut)
  python -I refmatch.py model <species> <out dir> [voxel_m]    # coarse sculpt -> silhouettes -> IoU vs refs
  python -I refmatch.py compare <species> <views dir> <out dir> # game renders (media.gd --what=views, use the
                                                                # Mobile renderer) vs the sheet: <id>_compare.jpg

The sheet views have a slight perspective (REFERENCE_NOTES.txt); IoU is a guide, the overlay images show
where the shape differs (red: only the reference, cyan: only the model).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# sheet pixel boxes of each view and rectangles to ignore (scale bars, human figure, labels)
VIEWS = {
    "velkor": {"sheet": "velkor_reference.png",
               "front": ((794, 135, 1013, 505), [(794, 225, 806, 505), (1003, 300, 1013, 505)]),
               "side": ((1052, 135, 1490, 505), [(1058, 330, 1125, 505)]),
               "rear": ((1492, 135, 1735, 505), [])},
    "kamneklyk": {"sheet": "kamneklyk_reference.png",
                  "front": ((768, 115, 1000, 448), []),
                  "side": ((1008, 115, 1512, 448), []),
                  "rear": ((1518, 115, 1765, 448), [])},
    "tenerys": {"sheet": "tenerys_reference.png",
                "front": ((800, 112, 965, 442), []),
                "side": ((982, 125, 1495, 442), []),
                "rear": ((1497, 112, 1665, 442), [])},
    "dragor": {"sheet": "dragor_reference.png",
               "front": ((775, 160, 1012, 450), []),
               "side": ((1015, 165, 1552, 450), []),
               "rear": ((1552, 160, 1768, 455), [])},
}


def segment(img, ignore):
    """GrabCut from a rectangle, then the soft ground shadow under the feet is removed."""
    import cv2
    a = np.asarray(img.convert("RGB"))
    h, w = a.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
    m = 4
    mask[:m, :] = mask[-m:, :] = mask[:, :m] = mask[:, -m:] = cv2.GC_BGD
    # background colour model from the border
    border = np.concatenate([a[:m].reshape(-1, 3), a[-m:].reshape(-1, 3), a[:, :m].reshape(-1, 3), a[:, -m:].reshape(-1, 3)])
    bg = np.median(border, 0)
    diff = np.abs(a.astype(np.float32) - bg).sum(2)
    mask[diff < 18] = cv2.GC_PR_BGD
    mask[diff < 8] = cv2.GC_BGD
    # light, saturated parts (ivory antlers, moss, tusks) differ from the neutral background by hue, not by value
    hsv0 = cv2.cvtColor(a[:, :, ::-1].copy(), cv2.COLOR_BGR2HSV)
    sat = hsv0[:, :, 1].astype(np.float32)
    bg_sat = float(np.median(np.concatenate([hsv0[:m, :, 1].ravel(), hsv0[-m:, :, 1].ravel()])))
    mask[(sat > bg_sat + 38) & (diff > 12)] = cv2.GC_PR_FGD
    mask[(sat > bg_sat + 70) & (diff > 25)] = cv2.GC_FGD
    for (x0, y0, x1, y1) in ignore:
        mask[max(0, y0):y1, max(0, x0):x1] = cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(a[:, :, ::-1].copy(), mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    # soft shadow: neutral, only a little darker than the background, in the lowest part of the figure
    ys = np.where(fg.any(1))[0]
    if len(ys):
        y_lo = ys.max()
        hsv = cv2.cvtColor(a[:, :, ::-1].copy(), cv2.COLOR_BGR2HSV).astype(np.float32)
        lum = a.astype(np.float32).mean(2)
        bgl = float(bg.mean())
        shadow = (hsv[:, :, 1] < 40) & (lum > bgl - 70) & (lum < bgl - 3)
        band = np.zeros_like(fg, bool)
        band[int(y_lo - (y_lo - ys.min()) * 0.10):, :] = True
        fg[shadow & band] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        keep = np.zeros(n, bool)
        big = stats[1:, cv2.CC_STAT_AREA].max()
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] > big * 0.004
        fg = keep[lab].astype(np.uint8)
    return fg.astype(bool)


def cmd_refs(sheet_dir, out):
    os.makedirs(out, exist_ok=True)
    info = {}
    for sp, v in VIEWS.items():
        im = Image.open(os.path.join(sheet_dir, v["sheet"])).convert("RGB")
        info[sp] = {}
        for view in ("front", "side", "rear"):
            box, ign = v[view]
            crop = im.crop(box)
            ignore = [(x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1]) for x0, y0, x1, y1 in ign]
            fg = segment(crop, ignore)
            Image.fromarray((fg * 255).astype(np.uint8)).save(os.path.join(out, f"{sp}_{view}_mask.png"))
            rgba = np.dstack([np.asarray(crop), (fg * 255).astype(np.uint8)])
            Image.fromarray(rgba, "RGBA").save(os.path.join(out, f"{sp}_{view}_cut.png"))
            ys, xs = np.where(fg)
            info[sp][view] = {"box": box, "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                              "area": int(fg.sum())}
            print(sp, view, info[sp][view])
    json.dump(info, open(os.path.join(out, "refs.json"), "w"), indent=1)


# ------------------------------------------------------------------ model side
def coarse_meshes(species, voxel):
    import importlib
    from sdf import extract
    sp = importlib.import_module("species." + species)
    sk, parts = sp.build()
    meshes = []
    for part in parts:
        h = voxel if part["rigid"] is None else min(voxel, max(0.006, part.get("voxel", 0.008) * 2))
        v, f = extract(part["part"], h)
        if len(f):
            meshes.append((part["name"], v, f, part.get("level", 1)))
    return meshes


def project(v, view):
    """Model metres -> (u right, w up) for the sheet views. +X forward, +Y up, left side is -Z.
    LEFT SIDE view: the head points left on the sheet; FRONT: viewer in front; REAR: viewer behind."""
    if view == "side":
        return np.stack([-v[:, 0], v[:, 1]], 1)
    if view == "front":
        return np.stack([-v[:, 2], v[:, 1]], 1)   # the creature's right (+Z) appears on the viewer's left
    return np.stack([v[:, 2], v[:, 1]], 1)


def raster(meshes, view, px_per_m, level=1):
    pts = np.concatenate([project(v, view) for _n, v, _f, lv in meshes if lv <= level])
    lo, hi = pts.min(0) - 0.05, pts.max(0) + 0.05
    W, H = [int(np.ceil((hi[i] - lo[i]) * px_per_m)) + 1 for i in (0, 1)]
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    for _n, v, f, lv in meshes:
        if lv > level:
            continue
        p = project(v, view)
        q = np.stack([(p[:, 0] - lo[0]) * px_per_m, (hi[1] - p[:, 1]) * px_per_m], 1)
        for tri in q[f]:
            d.polygon([tuple(tri[0]), tuple(tri[1]), tuple(tri[2])], fill=255)
    return np.asarray(img) > 0, lo, hi


def fit(ref, model):
    """Best uniform scale + offset of the model silhouette onto the reference (IoU), coarse-to-fine:
    feet on the reference ground line, centred, scale searched."""
    rys, rxs = np.where(ref)
    ref_h = rys.max() - rys.min() + 1
    best = (0, None)
    mys, mxs = np.where(model)
    m_h = mys.max() - mys.min() + 1
    for s in np.linspace(0.80, 1.20, 41) * ref_h / m_h:
        mh, mw = int(model.shape[0] * s), int(model.shape[1] * s)
        if mh < 4 or mw < 4:
            continue
        mm = np.asarray(Image.fromarray(model.astype(np.uint8) * 255).resize((mw, mh), Image.BILINEAR)) > 127
        ys, xs = np.where(mm)
        for dx in range(-12, 13, 3):
            canvas = np.zeros_like(ref)
            oy = rys.max() - ys.max()            # feet on the reference ground line
            ox = int((rxs.min() + rxs.max()) / 2 - (xs.min() + xs.max()) / 2) + dx
            y0, x0 = max(0, oy), max(0, ox)
            y1, x1 = min(ref.shape[0], oy + mh), min(ref.shape[1], ox + mw)
            if y1 <= y0 or x1 <= x0:
                continue
            canvas[y0:y1, x0:x1] = mm[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
            inter = (canvas & ref).sum()
            iou = inter / max(1, (canvas | ref).sum())
            if iou > best[0]:
                best = (iou, canvas.copy(), s, dx)
    return best


def overlay(ref, fitted, cut):
    base = np.asarray(cut.convert("RGB")).astype(np.float32) * 0.35 + 255 * 0.65
    out = base.copy()
    out[ref & ~fitted] = (230, 40, 40)
    out[fitted & ~ref] = (40, 190, 230)
    out[ref & fitted] = out[ref & fitted] * 0.55 + np.array([90, 90, 90]) * 0.45
    return Image.fromarray(out.astype(np.uint8))


def grid_view(species, out, view, px_per_m, ground_px=None, anchor=None, meshes=None, level=1):
    """Reference cut on a metric grid in model coordinates (side: x forward to the left, y up; front/rear: z),
    with the model silhouette outline, so landmark positions can be read off in metres."""
    import cv2
    cut = Image.open(os.path.join(out, f"{species}_{view}_cut.png")).convert("RGBA")
    ref = np.asarray(Image.open(os.path.join(out, f"{species}_{view}_mask.png"))) > 127
    ys, xs = np.where(ref)
    g = ys.max() if ground_px is None else ground_px
    # anchor: model coordinate of the reference bbox centre (side: x, front/rear: z) -> default 0
    cx = (xs.min() + xs.max()) / 2.0
    a0 = 0.0 if anchor is None else anchor
    scale = 3
    W, H = cut.size
    big = Image.new("RGB", (W * scale, H * scale), (255, 255, 255))
    bg = Image.new("RGBA", cut.size, (250, 250, 250, 255))
    bg.alpha_composite(cut)
    big.paste(bg.convert("RGB").resize((W * scale, H * scale), Image.LANCZOS))
    d = ImageDraw.Draw(big)

    def to_px(u_m, y_m):  # u_m: screen-right metres relative to anchor
        return ((cx + u_m * px_per_m) * scale, (g - y_m * px_per_m) * scale)
    for k in range(-30, 31):
        u = k * 0.25
        x0, _ = to_px(u, 0)
        if 0 <= x0 < W * scale:
            d.line([(x0, 0), (x0, H * scale)], fill=(170, 200, 255) if k % 4 else (90, 140, 255), width=1)
            if k % 2 == 0:
                val = -(u) + a0 if view == "side" else (-(u) + a0 if view == "front" else u + a0)
                d.text((x0 + 2, 2), f"{val:.1f}", fill=(0, 0, 160))
    for k in range(0, 30):
        y = k * 0.25
        _, y0 = to_px(0, y)
        if 0 <= y0 < H * scale:
            d.line([(0, y0), (W * scale, y0)], fill=(255, 200, 170) if k % 4 else (255, 120, 60), width=1)
            if k % 2 == 0:
                d.text((2, y0 - 12), f"{y:.1f}", fill=(160, 40, 0))
    if meshes is not None:
        sil, lo, hi = raster(meshes, view, px_per_m * scale, level)
        # model u axis: projected first coordinate; side projection u = -x, so u - (-a0) relative to anchor
        off_u = lo[0] - (-a0 if view in ("side", "front") else a0)
        ox = cx * scale + off_u * px_per_m * scale
        oy = g * scale - hi[1] * px_per_m * scale
        cnt, _h = cv2.findContours(sil.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for c in cnt:
            pts = [(float(p[0][0] + ox), float(p[0][1] + oy)) for p in c[::2]]
            if len(pts) > 2:
                d.line(pts + [pts[0]], fill=(0, 170, 0), width=2)
    big.save(os.path.join(out, f"{species}_{view}_grid.png"))


def cmd_model(species, out, voxel=0.03, level=1):
    refs = json.load(open(os.path.join(out, "refs.json")))[species]
    meshes = coarse_meshes(species, voxel)
    res = {}
    tiles = []
    for view in ("front", "side", "rear"):
        ref = np.asarray(Image.open(os.path.join(out, f"{species}_{view}_mask.png"))) > 127
        sil, lo, hi = raster(meshes, view, 120.0, level)
        iou, fitted, s, dx = fit(ref, sil)
        res[view] = round(float(iou), 3)
        cut = Image.open(os.path.join(out, f"{species}_{view}_cut.png"))
        tiles.append(overlay(ref, fitted, cut))
    w = sum(t.size[0] for t in tiles) + 20
    h = max(t.size[1] for t in tiles)
    sheet = Image.new("RGB", (w, h), (255, 255, 255))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.size[0] + 10
    sheet.save(os.path.join(out, f"{species}_match.png"))
    print("IOU", species, json.dumps(res))
    return res


def _crop_alpha(im):
    a = np.asarray(im.convert("RGBA"))
    ys, xs = np.where(a[:, :, 3] > 40)
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def cmd_compare(species, views_dir, out, height=330):
    """Sheet view | game model render (same orthographic view, idle pose) | silhouette overlay, for front, side and
    rear. Both are cropped to their silhouettes and scaled to the same height; the overlay uses the best uniform
    scale and offset (IoU printed)."""
    from PIL import ImageFont
    rows, res = [], {}
    for view in ("front", "side", "rear"):
        ref = _crop_alpha(Image.open(os.path.join(out, f"{species}_{view}_cut.png")).convert("RGBA"))
        mdl = _crop_alpha(Image.open(os.path.join(views_dir, species, f"view_{view}.png")).convert("RGBA"))
        r2 = ref.resize((max(1, int(ref.size[0] * height / ref.size[1])), height), Image.LANCZOS)
        m2 = mdl.resize((max(1, int(mdl.size[0] * height / mdl.size[1])), height), Image.LANCZOS)
        rm = np.asarray(r2)[:, :, 3] > 127
        mm = np.asarray(m2)[:, :, 3] > 127
        W = max(rm.shape[1], mm.shape[1]) + 60
        refc = np.zeros((height + 40, W), bool)
        ox = (W - rm.shape[1]) // 2
        refc[20:20 + height, ox:ox + rm.shape[1]] = rm
        iou, fitted, _s, _dx = fit(refc, mm)
        res[view] = round(float(iou), 3)
        ov = np.full((height + 40, W, 3), 245, np.uint8)
        ov[refc & ~fitted] = (230, 60, 60)
        ov[fitted & ~refc] = (40, 180, 230)
        ov[refc & fitted] = (120, 120, 120)
        tiles = []
        for t in (r2, m2):
            bg = Image.new("RGBA", (t.size[0] + 40, height + 40), (238, 234, 228, 255))
            bg.alpha_composite(t, (20, 20))
            tiles.append(bg.convert("RGB"))
        tiles.append(Image.fromarray(ov))
        w = sum(t.size[0] for t in tiles) + 20
        row = Image.new("RGB", (w, height + 40), (255, 255, 255))
        x = 0
        for t in tiles:
            row.paste(t, (x, 0))
            x += t.size[0] + 10
        d = ImageDraw.Draw(row)
        d.text((8, 4), f"{view.upper()}  sheet | game model | overlay  IoU {iou:.2f}", fill=(20, 20, 20))
        rows.append(row)
    W = max(r.size[0] for r in rows)
    H = sum(r.size[1] for r in rows) + 10 * len(rows)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.size[1] + 10
    sheet.save(os.path.join(out, f"{species}_compare.jpg"), quality=90)
    print("COMPARE", species, json.dumps(res))
    return res


if __name__ == "__main__":
    if sys.argv[1] == "compare":
        cmd_compare(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0)
    if sys.argv[1] == "refs":
        cmd_refs(sys.argv[2], sys.argv[3])
    else:
        cmd_model(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.03)
