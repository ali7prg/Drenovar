"""Reference check against the creature-references kit (repository drenovar-server, branch creature-references:
creature-references/manifest.json, <id>/model.png turnaround views and four attack pose images per creature).

  python -I refcheck.py refs <creature-references dir> <out>        # segment the views and poses, metric scale
  python -I refcheck.py sculpt <species> <out> [voxel_m]             # coarse sculpt silhouettes vs the views
  python -I refcheck.py render <species> <glb> <out>                 # Cycles orthographic renders vs the views
                                                                     # (run with Blender 5.3 as a Python module)

Every comparison is made at the reference's own scale: the sheet is read at a fixed number of pixels per metre
(PX_PER_M, from the manifest dimensions), the model is projected at that scale with the ground on the sheet's
ground line, and only a horizontal shift is searched (no rescaling). Overlay colours: red - only on the
reference, cyan - only on the model, grey - both.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# manifest ids (art names) -> project ids
REF_ID = {"dragor": "dragar", "velkor": "velkor", "tenerys": "teneris", "kamneklyk": "kamneklyk"}
# view boxes on <id>/model.png (x0, y0, x1, y1) - every box holds one drawing of the creature
VIEWS = {
    "dragor": {"side": (18, 4, 1214, 414), "front": (1216, 4, 1724, 414), "rear": (88, 424, 592, 876),
               "top": (660, 446, 1768, 836)},
    "velkor": {"side": (18, 28, 934, 806), "front": (934, 66, 1368, 800), "rear": (1368, 66, 1770, 800)},
    "tenerys": {"side": (74, 4, 1012, 452), "front": (1020, 4, 1340, 452), "rear": (1402, 4, 1698, 452),
                "top": (54, 538, 978, 800), "three_quarter": (1024, 446, 1722, 852)},
    "kamneklyk": {"side": (40, 4, 1156, 700), "front": (1158, 4, 1650, 700), "rear": (1660, 4, 2168, 700)},
}
POSES = ("preparation", "launch", "contact", "recovery")
# pixels per metre of each turnaround sheet (side view), from the manifest dimensions - see refs.json "scale"
PX_PER_M = {}


def load_scale(out):
    p = os.path.join(out, "refs.json")
    if os.path.exists(p):
        for sp, row in json.load(open(p)).items():
            PX_PER_M[sp] = row["scale"]["px_per_m"]


# ------------------------------------------------------------------ segmentation
def background(a, order=3):
    """Smooth studio backdrop: a robust polynomial fit per channel (outliers - the figure, its shadow, effects -
    are dropped in a few reweighting rounds). Fit on a whole sheet, then cropped per view."""
    import cv2
    h, w = a.shape[:2]
    sh, sw = max(16, h // 8), max(16, w // 8)
    small = cv2.resize(a, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float64)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float64)
    xx = xx / sw * 2 - 1
    yy = yy / sh * 2 - 1
    terms = [np.ones_like(xx)]
    for i in range(1, order + 1):
        for j in range(i + 1):
            terms.append(xx ** (i - j) * yy ** j)
    basis = np.stack(terms, -1)
    sat = small.max(2) - small.min(2)
    use = sat < np.percentile(sat, 60) + 6
    lum = small.mean(2)
    use &= lum > np.percentile(lum, 35)
    bg = np.zeros_like(small)
    for _ in range(6):
        res = np.zeros(small.shape[:2])
        for c in range(3):
            coef, *_ = np.linalg.lstsq(basis[use], small[..., c][use], rcond=None)
            bg[..., c] = basis @ coef
            res += np.abs(small[..., c] - bg[..., c])
        thr = max(12.0, np.percentile(res[use], 80) * 1.5)
        use = res < thr
    full = cv2.resize(bg.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    return full


def segment(img, ground_band=0.16, keep_frac=0.02, effects=False, bg=None):
    """Figure mask: backdrop difference seeds GrabCut. Smooth neutral areas (the backdrop and the soft floor
    shadow: no texture, no hue) are background; the creature's scales, fur and plates are always textured.
    For the attack poses (`effects`) glow trails, dust haze and flying debris are removed as well."""
    import cv2
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w = a.shape[:2]
    bg = background(a) if bg is None else bg
    diff = np.abs(a - bg).sum(2)
    hsv = cv2.cvtColor(a.astype(np.uint8)[:, :, ::-1].copy(), cv2.COLOR_BGR2HSV).astype(np.float32)
    sat = hsv[:, :, 1]
    bg_hsv = cv2.cvtColor(np.clip(bg, 0, 255).astype(np.uint8)[:, :, ::-1].copy(), cv2.COLOR_BGR2HSV).astype(np.float32)
    dsat = sat - bg_hsv[:, :, 1]
    lum = a.mean(2)
    dl = lum - bg.mean(2)
    mu = cv2.blur(lum, (5, 5))
    tex = np.sqrt(np.maximum(cv2.blur(lum * lum, (5, 5)) - mu * mu, 0))
    smooth = cv2.blur(tex, (9, 9)) < 3.2
    neutral = np.abs(dsat) < 22
    shadow = smooth & neutral & (dl < 25) & (dl > -75)
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    mask[diff > 30] = cv2.GC_PR_FGD
    mask[((diff > 90) & ~shadow) | ((dsat > 40) & (diff > 40))] = cv2.GC_FGD
    mask[(diff < 12) | (shadow & (diff < 110))] = cv2.GC_BGD
    glow = np.zeros((h, w), bool)
    if effects:
        # saturated green / cyan-blue light trails (antler sweep, claw slash) are drawn effects, not the body
        hue = hsv[:, :, 0]
        glow = (sat > 70) & (hsv[:, :, 2] > 120) & (((hue > 35) & (hue < 85)) | ((hue > 85) & (hue < 125)))
        glow = cv2.dilate(glow.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        mask[glow] = cv2.GC_BGD
    m = 3
    mask[:m, :] = mask[-m:, :] = mask[:, :m] = mask[:, -m:] = cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(a.astype(np.uint8)[:, :, ::-1].copy(), mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    fg[shadow & (diff < 110)] = 0
    if effects:
        # dust: light, low-saturation haze close to the backdrop; the creature is darker and textured
        haze = neutral & (dl > -55) & (diff < 75) & (cv2.blur(tex, (9, 9)) < 9)
        fg[haze | glow] = 0
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # thin horizontal floor strips left under the feet (shadow contact lines) are cut off
    rows = fg.sum(1)
    ys = np.where(rows > 0)[0]
    if len(ys):
        y_lo = ys.max()
        band0 = int(y_lo - (y_lo - ys.min()) * ground_band)
        sub = fg[band0:].copy()
        opened = cv2.morphologyEx(sub, cv2.MORPH_OPEN, np.ones((7, 3), np.uint8))
        fg[band0:] = opened
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        big = stats[1:, cv2.CC_STAT_AREA].max()
        keep = np.zeros(n, bool)
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] > big * keep_frac
        fg = keep[lab].astype(np.uint8)
    # fill small holes (eyes, mouth interior seen against the backdrop stay figure)
    inv = (1 - fg).astype(np.uint8)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n2):
        x, y, ww, hh, area = st2[i]
        if area < 400 and x > 0 and y > 0 and x + ww < w and y + hh < h:
            fg[lab2 == i] = 1
    return fg.astype(bool)


def ground_row(mask, feet=False):
    """Ground line of a standing figure: the lowest rows of its feet (98th percentile of the lowest pixel per
    column, so a stray hair tip does not move it). feet=True (front / rear views): the row where most columns
    end - the flat soles - so a tail tip hanging nearer the camera (lower in a perspective drawing) is ignored."""
    cols = np.where(mask.any(0))[0]
    low = np.array([np.where(mask[:, c])[0].max() for c in cols])
    if not feet:
        return float(np.percentile(low, 98))
    ys = np.where(mask.any(1))[0]
    floor = ys.max() - (ys.max() - ys.min()) * 0.25
    cand = low[low >= floor]
    hist = np.bincount((cand // 4).astype(int))
    ok = np.where(hist >= hist.max() * 0.4)[0]
    b = ok.max()
    sel = cand[(cand // 4) == b]
    return float(np.percentile(sel, 90))


def cmd_refs(ref_dir, out):
    os.makedirs(out, exist_ok=True)
    man = json.load(open(os.path.join(ref_dir, "manifest.json")))
    by_ref = {c["id"]: c for c in man["creatures"]}
    info = {}
    for sp, views in VIEWS.items():
        c = by_ref[REF_ID[sp]]
        im = Image.open(os.path.join(ref_dir, c["model"])).convert("RGB")
        sheet_bg = background(np.asarray(im).astype(np.float32))
        info[sp] = {"model": c["model"], "views": {}, "dimensions": c.get("dimensions", {})}
        for view, box in views.items():
            crop = im.crop(box)
            fg = segment(crop, bg=sheet_bg[box[1]:box[3], box[0]:box[2]])
            Image.fromarray((fg * 255).astype(np.uint8)).save(os.path.join(out, f"{sp}_{view}_mask.png"))
            rgba = np.dstack([np.asarray(crop), (fg * 255).astype(np.uint8)])
            Image.fromarray(rgba, "RGBA").save(os.path.join(out, f"{sp}_{view}_cut.png"))
            crop.save(os.path.join(out, f"{sp}_{view}_ref.png"))
            ys, xs = np.where(fg)
            row = {"box": list(box), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                   "area": int(fg.sum())}
            if view not in ("top", "three_quarter"):
                row["ground"] = round(ground_row(fg, feet=view in ("front", "rear")), 1)
            info[sp]["views"][view] = row
        # attack poses, in the manifest's order
        info[sp]["poses"] = {}
        for p in c["attack"]["poses"]:
            pim = Image.open(os.path.join(ref_dir, p["file"])).convert("RGB")
            fg = segment(pim, effects=True)
            Image.fromarray((fg * 255).astype(np.uint8)).save(os.path.join(out, f"{sp}_pose_{p['phase']}_mask.png"))
            rgba = np.dstack([np.asarray(pim), (fg * 255).astype(np.uint8)])
            Image.fromarray(rgba, "RGBA").save(os.path.join(out, f"{sp}_pose_{p['phase']}_cut.png"))
            pim.save(os.path.join(out, f"{sp}_pose_{p['phase']}_ref.png"))
            ys, xs = np.where(fg)
            info[sp]["poses"][p["phase"]] = {"file": p["file"], "action": p["action"],
                                             "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}
        info[sp]["attack"] = c["attack"]["name"]
        info[sp]["materials"] = c.get("materials", {})
        info[sp]["scale"] = scale_of(sp, info[sp], out)
        view_scales(info[sp])
        print(sp, json.dumps(info[sp]["scale"]), {v: r["px_per_m"] for v, r in info[sp]["views"].items()})
    json.dump(info, open(os.path.join(out, "refs.json"), "w"), ensure_ascii=False, indent=1)


# metric scale of each turnaround sheet, read on its side view (pixels of the cropped side view)
SCALE_RULE = {
    # velkor: "shoulder_height 2.1, body_length 3.6" - 3.6 m from the nose tip to the end of the tail (as the
    # length bar of the kit sheet); check: the withers come out at 2.04 m
    "velkor": {"length_m": 3.6},
    # tenerys: "body_length_excluding_tail 2.8, tail_length 1.15": nose tip to tail tip 3.95 m; withers 1.55 m
    "tenerys": {"length_m": 3.95},
    # kamneklyk: "shoulder_height 1.65, body_length 3.0": snout disc (x 45) to the rump where the tail starts
    # (x 990) is 3.0 m; the slate crest then tops out at 2.02 m and the withers sit under it at 1.65 m
    "kamneklyk": {"span_px": (45, 990), "span_m": 3.0},
    # dragor: no numbers in the manifest (scale note: a 1.8 m man on the kit sheet, where the shoulders were
    # 3.1 m): the highest point - the dorsal scutes over the shoulders - stays at 3.1 m, so head, legs and claws
    # keep their size and the body takes the longer, lower proportions of this sheet
    "dragor": {"height_m": 3.10},
}


def scale_of(sp, row, out):
    v = row["views"]["side"]
    fg = np.asarray(Image.open(os.path.join(out, f"{sp}_side_mask.png"))) > 127
    x0, y0, x1, y1 = v["bbox"]
    g = v["ground"]
    rule = SCALE_RULE[sp]
    res = {"ground_px": g, "length_px": x1 - x0, "height_px": round(g - y0, 1)}
    if "length_m" in rule:
        res["px_per_m"] = round((x1 - x0) / rule["length_m"], 2)
    elif "height_m" in rule:
        res["px_per_m"] = round((g - y0) / rule["height_m"], 2)
    else:
        res["px_per_m"] = round((rule["span_px"][1] - rule["span_px"][0]) / rule["span_m"], 2)
    res["rule"] = {k: list(v) if isinstance(v, tuple) else v for k, v in rule.items()}
    res["extent_m"] = {"length": round((x1 - x0) / res["px_per_m"], 3), "height": round((g - y0) / res["px_per_m"], 3)}
    return res


def view_scales(row):
    """Pixels per metre of every view. The metric scale is read on the side view (scale_of); the sheet draws the
    other views with their own perspective and size (dragar: front +7 %, rear +12 %), so each is read at the
    scale where it agrees with the side view the way orthographic views must: the highest point of the creature at
    the same height (front, rear) and the same nose-to-tail length (top). Landmarks are measured on the masks."""
    side = row["views"]["side"]
    ppm = row["scale"]["px_per_m"]
    h_side = side["ground"] - side["bbox"][1]
    l_side = side["bbox"][2] - side["bbox"][0]
    for view, r in row["views"].items():
        if view == "side":
            r["px_per_m"] = ppm
        elif view in ("front", "rear"):
            r["px_per_m"] = round(ppm * (r["ground"] - r["bbox"][1]) / h_side, 2)
        elif view == "top":
            r["px_per_m"] = round(ppm * (r["bbox"][2] - r["bbox"][0]) / l_side, 2)
        else:
            r["px_per_m"] = ppm


# ------------------------------------------------------------------ model projection
def project(v, view):
    """Model metres (+X forward, +Y up, +Z right) -> sheet axes (u right, w up). Side: the LEFT side with the head
    to the left; front: the creature's right appears on the viewer's left; rear: the right on the right;
    top: from above, head to the left."""
    if view == "side":
        return np.stack([-v[:, 0], v[:, 1]], 1)
    if view == "front":
        return np.stack([-v[:, 2], v[:, 1]], 1)
    if view == "rear":
        return np.stack([v[:, 2], v[:, 1]], 1)
    if view == "top":
        return np.stack([-v[:, 0], -v[:, 2]], 1)
    raise ValueError(view)


def raster(meshes, view, ppm, W, H, ground_px, u_off=0.0, w_off=0.0):
    """Silhouette of `meshes` on a W x H canvas: model ground (y=0) on row `ground_px`, model u=0 on column
    W/2 + u_off (pixels). For the top view w_off places z=0."""
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    for v, f in meshes:
        p = project(v, view)
        if view == "top":
            q = np.stack([W / 2 + u_off + p[:, 0] * ppm, H / 2 + w_off - p[:, 1] * ppm], 1)
        else:
            q = np.stack([W / 2 + u_off + p[:, 0] * ppm, ground_px - p[:, 1] * ppm], 1)
        for tri in q[f]:
            d.polygon([tuple(tri[0]), tuple(tri[1]), tuple(tri[2])], fill=255)
    return np.asarray(img) > 0


def best_shift(ref, sil_fn, ranges):
    """Translation (pixels) with the best IoU; sil_fn(du, dw) -> mask. Coarse grid, then refine."""
    best = (-1, 0, 0, None)
    for du in ranges[0]:
        for dw in ranges[1]:
            m = sil_fn(du, dw)
            iou = (m & ref).sum() / max(1, (m | ref).sum())
            if iou > best[0]:
                best = (iou, du, dw, m)
    return best


def overlay(ref, mdl, cut):
    base = np.asarray(cut.convert("RGB")).astype(np.float32) * 0.30 + 255 * 0.70
    out = base.copy()
    out[ref & ~mdl] = (225, 45, 45)
    out[mdl & ~ref] = (35, 185, 230)
    out[ref & mdl] = out[ref & mdl] * 0.5 + np.array([95, 95, 95]) * 0.5
    return Image.fromarray(out.astype(np.uint8))


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 8 + 6 * len(text), 14], fill=(255, 255, 255))
    d.text((4, 2), text, fill=(15, 15, 15))
    return im


def coarse_meshes(species, voxel):
    import importlib
    from sdf import extract
    sp = importlib.import_module("species." + species)
    sk, parts = sp.build_cached()
    meshes = []
    for part in parts:
        if part.get("level", 1) > 1:
            continue
        h = voxel if part["rigid"] is None else min(voxel, max(0.006, part.get("voxel", 0.008) * 2))
        v, f = extract(part["part"], h)
        if len(f):
            meshes.append((v, f))
    return meshes


def fit_view(sp, view, ref, meshes, ppm, g):
    H, W = ref.shape
    ys, xs = np.where(ref)
    if view == "top":
        def fn(du, dw):
            return raster(meshes, view, ppm, W, H, g, du, dw)
        # centre the model bbox on the reference bbox first
        m0 = fn(0, 0)
        my, mx = np.where(m0)
        c_u = (xs.min() + xs.max()) / 2 - (mx.min() + mx.max()) / 2
        c_w = (ys.min() + ys.max()) / 2 - (my.min() + my.max()) / 2
        iou, du, dw, m = best_shift(ref, fn, (np.arange(c_u - 24, c_u + 25, 6), np.arange(c_w - 12, c_w + 13, 6)))
        iou, du, dw, m = best_shift(ref, fn, (np.arange(du - 5, du + 6, 1), np.arange(dw - 5, dw + 6, 1)))
        return iou, m, (du, dw)

    def fn(du, dw):
        return raster(meshes, view, ppm, W, H, g, du, 0)
    m0 = fn(0, 0)
    my, mx = np.where(m0)
    c_u = (xs.min() + xs.max()) / 2 - (mx.min() + mx.max()) / 2
    iou, du, dw, m = best_shift(ref, fn, (np.arange(c_u - 40, c_u + 41, 8), [0]))
    iou, du, dw, m = best_shift(ref, fn, (np.arange(du - 7, du + 8, 1), [0]))
    return iou, m, (du, 0)


def cmd_sculpt(species, out, voxel=0.03, tag="sculpt"):
    load_scale(out)
    refs = json.load(open(os.path.join(out, "refs.json")))[species]
    ppm = PX_PER_M[species]
    meshes = coarse_meshes(species, voxel)
    res, tiles = {}, []
    for view, row in refs["views"].items():
        if view == "three_quarter":
            continue
        ref = np.asarray(Image.open(os.path.join(out, f"{species}_{view}_mask.png"))) > 127
        g = row.get("ground", ref.shape[0] / 2)
        iou, m, shift = fit_view(species, view, ref, meshes, ppm, g)
        res[view] = round(float(iou), 3)
        cut = Image.open(os.path.join(out, f"{species}_{view}_cut.png"))
        tiles.append(label(overlay(ref, m, cut), f"{view} IoU {iou:.3f} (same scale {ppm} px/m)"))
    sheet = stack(tiles)
    sheet.save(os.path.join(out, f"{species}_{tag}.png"))
    print("IOU", species, tag, json.dumps(res))
    return res


def stack(tiles, cols=2, pad=8):
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    W = max(sum(t.size[0] for t in r) + pad * (len(r) - 1) for r in rows)
    H = sum(max(t.size[1] for t in r) for r in rows) + pad * (len(rows) - 1)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            sheet.paste(t, (x, y))
            x += t.size[0] + pad
        y += max(t.size[1] for t in r) + pad
    return sheet


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "refs":
        cmd_refs(sys.argv[2], sys.argv[3])
    elif cmd == "sculpt":
        cmd_sculpt(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.03,
                   sys.argv[5] if len(sys.argv) > 5 else "sculpt")
    else:
        raise SystemExit(__doc__)
