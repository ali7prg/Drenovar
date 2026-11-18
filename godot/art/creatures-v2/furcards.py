"""Fur cards: alpha-masked hair locks over the furry sculpts (kit 03_ANIMATIONS_AND_MATERIALS: alpha-mask strands
along the silhouette are allowed; the main volume stays opaque geometry).

Each card is a curved strip (3 segments) rooted on the outer body surface (sculpted locks included) and laid along
the coat flow; silhouette tufts (mane, ruff, tail) add a second strip crossed at right angles. Both faces are explicit
geometry with the same outward surface normal, so the single-sided material lights both sides like the coat under
them (a double-sided material flips the normal on back faces and turns half the locks black) - the same in Godot,
three.js and DCC tools.

Colour per vertex: root = body BaseColor at the root (darkened), tip = the region's tip colour (the light silver /
grey ends of the locks on the sheets), so each lock goes dark-to-light like the painted coats. The strand atlas has
pointed locks, split locks and wispy strands; regions marked "glow" use the fourth column, whose strands are also in
the emissive texture (the glowing strands on the Tenerys sheet). Skin weights are copied from the nearest body
vertex, so the cards follow the body exactly.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ATLAS_COLUMNS = 4
GLOW_COLUMN = 3
# per LOD: share of the cards kept, their width (fewer, wider cards keep the coverage far away) and strip
# segments - sized so the coat stays close to the triangle budgets of 03_ANIMATIONS_AND_MATERIALS
KEEP = {0: 0.55, 1: 0.34, 2: 0.10}
WIDEN = {0: 1.15, 1: 1.45, 2: 2.2}
SEGMENTS = {0: 3, 1: 2, 2: 2}


def _srgb_to_linear(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _hex(h):
    return np.array([int(h[k:k + 2], 16) / 255.0 for k in (1, 3, 5)], np.float32)


def _strands(rng, col_w, h, x0, n, tips, length, width, spread=0.05, wisp=False):
    """Strand polylines for one atlas column: roots spread over the column width, converging on `tips` (pointed
    locks) or running up with a little spread (wisps). Image y: root at the bottom row, tip toward the top."""
    out = []
    for _ in range(n):
        xr = x0 + col_w * (0.05 + 0.90 * rng.random())
        if wisp:
            xt = xr + rng.normal(0, col_w * 0.07)
        else:
            k = int(np.argmin([abs((xr - x0) / col_w - t) for t in tips]))
            xt = x0 + col_w * (tips[k] + rng.normal(0, spread))
        frac = length[0] + (length[1] - length[0]) * rng.random() ** 0.6
        top = (h - 1) * (1.0 - frac)
        wave = rng.normal(0, col_w * 0.025)
        ph = rng.random() * 6.28
        pts = []
        for k in range(14):
            t = k / 13.0
            y = (h - 1) - t * ((h - 1) - top)
            s = t if wisp else t ** 1.5
            x = xr + (xt - xr) * s + wave * np.sin(t * 3.0 + ph) * t
            pts.append((x, y))
        out.append((pts, width[0] + (width[1] - width[0]) * rng.random(), 0.60 + 0.40 * rng.random()))
    return out


def hair_atlas(out_dir, glow_rgb=None, w=512, h=1024, seed=0):
    """fur_basecolor.png (RGBA strands, grey: the vertex colour carries the hue) and, with glow_rgb, fur_emissive.png
    (the lit strands of the glow column)."""
    rng = np.random.default_rng(seed)
    col_w = w // ATLAS_COLUMNS
    alpha, lum, glow = (Image.new("L", (w, h), 0) for _ in range(3))
    da, dl, dg = ImageDraw.Draw(alpha), ImageDraw.Draw(lum), ImageDraw.Draw(glow)
    # tufts, not needles: many strands, wide at the root, tips spread over a third of the column
    specs = [dict(n=150, tips=[0.38, 0.62], length=(0.55, 1.0), width=(2.4, 4.4), spread=0.10),   # full lock
             dict(n=160, tips=[0.22, 0.5, 0.78], length=(0.5, 0.97), width=(2.4, 4.2), spread=0.09),  # split lock
             dict(n=170, tips=[0.5], length=(0.35, 1.0), width=(2.0, 3.4), wisp=True),            # wispy strands
             dict(n=120, tips=[0.5], length=(0.6, 1.0), width=(2.0, 3.6), spread=0.07)]           # glow lock
    for c, spec in enumerate(specs):
        for pts, wdt, shade in _strands(rng, col_w, h, c * col_w, **spec):
            lit = c == GLOW_COLUMN and rng.random() < 0.5
            for k in range(len(pts) - 1):
                t = k / (len(pts) - 1)
                wk = max(1, int(round(wdt * (1.0 - 0.7 * t))))
                da.line([pts[k], pts[k + 1]], fill=255, width=wk)
                dl.line([pts[k], pts[k + 1]], fill=int(255 * shade * (0.82 + 0.18 * t)), width=wk)
                if lit:
                    dg.line([pts[k], pts[k + 1]], fill=int(255 * min(1.0, 0.35 + 0.8 * t)), width=max(1, wk - 1))
    a_raw = np.asarray(alpha.filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    l_raw = np.asarray(lum.filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    shade = np.where(a_raw > 0.02, np.clip(l_raw / np.maximum(a_raw, 1e-3), 0.5, 1.0), 0.8)
    v = 1.0 - np.linspace(0, 1, h, dtype=np.float32)[:, None]          # 0 at the root row, 1 at the tip row
    a = np.clip(a_raw + np.clip((0.05 - v) / 0.05, 0, 1) * 0.9, 0, 1)   # dense root band hides the card base
    g = np.clip(np.stack([shade] * 3, 2) * 255, 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack([g, (a * 255).astype(np.uint8)]), "RGBA").save(
        os.path.join(out_dir, "fur_basecolor.png"), optimize=True)
    if glow_rgb is not None:
        gm = np.asarray(glow.filter(ImageFilter.GaussianBlur(0.8)), np.float32)[..., None] / 255.0
        em = np.clip(gm * np.asarray(glow_rgb, np.float32)[None, None, :] * 255, 0, 255).astype(np.uint8)
        Image.fromarray(em, "RGB").save(os.path.join(out_dir, "fur_emissive.png"), optimize=True)


def _frame(d, n):
    d = d / np.linalg.norm(d)
    s = np.cross(d, n)
    if np.linalg.norm(s) < 1e-5:
        s = np.cross(d, np.array([0.0, 0.0, 1.0]))
    s /= np.linalg.norm(s)
    up = np.cross(s, d)
    return d, up / np.linalg.norm(up), s


def cards(surface, regions, rng, keep=1.0, widen=1.0):
    """regions: dicts {centre, radii, count, length, width, flow(p, n), lift, gravity, droop, crossed, tip, tip_k,
    root, root_k, glow, segments, keep} (tip / root: sRGB hex overriding the body colour at the root; keep(p): a
    root position filter). Seeds are projected onto `surface` (the outer body: core + sculpted locks)."""
    from common import scatter_on, surface_points
    out = []
    for reg in regions:
        seeds = scatter_on(surface, reg["centre"], reg["radii"], reg["count"], rng)
        pts, nrm = surface_points(surface, seeds, steps=10)
        mask = reg.get("keep")      # optional keep(p) -> bool: no cards on eyes, nose leather, lips
        for p, n in zip(pts, nrm):
            if rng.random() > keep:
                continue
            if mask is not None and not mask(p):
                continue
            n = n / max(np.linalg.norm(n), 1e-6)
            f = np.asarray(reg["flow"](p, n), float)
            f = f - np.dot(f, n) * n
            if np.linalg.norm(f) < 1e-5:
                f = np.array([-1.0, 0, 0]) - np.dot([-1.0, 0, 0], n) * n
            f /= np.linalg.norm(f)
            d = f + n * reg.get("lift", 0.2) + np.array([0, -reg.get("gravity", 0.0), 0])
            d /= np.linalg.norm(d)
            out.append({"root": p - n * reg.get("sink", 0.012), "n": n, "d": d,
                        "L": reg["length"] * (0.75 + 0.5 * rng.random()),
                        "W": reg["width"] * (0.8 + 0.4 * rng.random()) * widen,
                        "droop": reg.get("droop", 0.15), "crossed": reg.get("crossed", False),
                        "col": GLOW_COLUMN if reg.get("glow") else int(rng.integers(0, GLOW_COLUMN)),
                        "tip": reg.get("tip"), "tip_k": reg.get("tip_k", 1.5), "root_k": reg.get("root_k", 0.8),
                        "root_hex": reg.get("root"),
                        "segs": reg.get("segments"),
                        "jitter": 0.9 + 0.2 * rng.random()})
    return out


def card_mesh(card_list, crossed_ok=True, segments=3, lod=None):
    """Curved strips (crossed pairs for silhouette tufts), each face emitted twice with opposite winding.
    Returns pos, nrm, uv, idx, card index per vertex and t (0 root .. 1 tip) per vertex. A card's region may set
    its own strip segments per LOD ("segments": {lod: n}) - short coat cards lie flat and need fewer."""
    P, N, UV, I, ROOT, T = [], [], [], [], [], []
    default_segments = segments
    for ci, c in enumerate(card_list):
        segments = default_segments
        if lod is not None and c.get("segs") and lod in c["segs"]:
            segments = c["segs"][lod]
        d, up, side = _frame(c["d"], c["n"])
        u0, u1 = c["col"] / ATLAS_COLUMNS, (c["col"] + 1) / ATLAS_COLUMNS
        for across in ([side, up] if crossed_ok and c["crossed"] else [side]):
            base = len(P)
            for k in range(segments + 1):
                t = k / float(segments)
                ctr = c["root"] + d * c["L"] * t + np.array([0, -c["droop"] * c["L"] * t * t, 0])
                wk = c["W"] * (1.0 - 0.55 * t)      # tufts narrow to the tip (strips read as paper)
                for sgn, u in ((-1, u0), (1, u1)):
                    P.append(ctr + across * sgn * wk * 0.5)
                    N.append(c["n"])
                    UV.append((u, 1.0 - t))       # glTF: v=1 bottom row of the atlas (roots), v=0 top (tips)
                    ROOT.append(ci)
                    T.append(t)
            for k in range(segments):
                a = base + 2 * k
                I += [(a, a + 1, a + 3), (a, a + 3, a + 2), (a, a + 3, a + 1), (a, a + 2, a + 3)]
    return (np.asarray(P, np.float32), np.asarray(N, np.float32), np.asarray(UV, np.float32),
            np.asarray(I, np.int64), np.asarray(ROOT, np.int64), np.asarray(T, np.float32))


def body_colours(roots, body_mesh, body_tex):
    """sRGB body BaseColor at the nearest body vertex of each root (glTF UVs: row = v * height)."""
    from scipy.spatial import cKDTree
    _d, nearest = cKDTree(body_mesh["pos"]).query(roots)
    img = np.asarray(Image.open(body_tex).convert("RGB")).astype(np.float32) / 255.0
    h, w = img.shape[:2]
    uv = body_mesh["uv"][nearest]
    x = np.clip((uv[:, 0] * w).astype(int), 0, w - 1)
    y = np.clip((uv[:, 1] * h).astype(int), 0, h - 1)
    return img[y, x], nearest


def vertex_colours(card_list, root_srgb, rootv, tv):
    """Linear RGBA per vertex: darkened root colour -> tip colour along the lock."""
    root = np.zeros((len(card_list), 3), np.float32)
    tip = np.zeros((len(card_list), 3), np.float32)
    for i, c in enumerate(card_list):
        base = (_hex(c["root_hex"]) if c["root_hex"] else root_srgb[i]) * c["jitter"]
        root[i] = np.clip(base * c["root_k"], 0, 1)
        tip[i] = np.clip(_hex(c["tip"]) * c["jitter"] if c["tip"] else base * c["tip_k"], 0, 1)
    s = (tv ** 1.3)[:, None]
    srgb = root[rootv] * (1 - s) + tip[rootv] * s
    lin = _srgb_to_linear(srgb)
    return np.concatenate([lin, np.ones((len(lin), 1), np.float32)], 1).astype(np.float32)


def outer_surface(sp):
    """The body part of the sculpt (core volumes plus sculpted locks) for rooting the cards."""
    _sk, parts = sp.build_cached()
    return next(p["part"] for p in parts if p["name"] == "body")


def build_group(sp, lod, work, body, out_dir, seed=21):
    """The 'fur' export group for one LOD: mesh dict, textures dir, joints and weights (from the body)."""
    if not getattr(sp, "FUR_CARDS", None):
        return None
    rng = np.random.default_rng(seed)
    clist = cards(outer_surface(sp), sp.FUR_CARDS, rng, getattr(sp, "FUR_KEEP", KEEP)[lod], WIDEN[lod])
    if not clist:
        return None
    pos, nrm, uv, idx, rootv, tv = card_mesh(clist, crossed_ok=lod < 2, segments=SEGMENTS[lod], lod=lod)
    roots = np.array([c["root"] for c in clist], np.float32)
    root_srgb, nearest = body_colours(roots, body["mesh"], os.path.join(body["tex"], "body_basecolor.png"))
    col = vertex_colours(clist, root_srgb, rootv, tv)
    os.makedirs(out_dir, exist_ok=True)
    glow = any(r.get("glow") for r in sp.FUR_CARDS)
    hair_atlas(out_dir, _hex(sp.EMISSION_COLOR) if glow else None)
    Image.new("RGB", (16, 16), (128, 128, 255)).save(os.path.join(out_dir, "fur_normal.png"))
    Image.new("RGB", (16, 16), (255, 222, 0)).save(os.path.join(out_dir, "fur_orm.png"))
    if not glow and os.path.exists(os.path.join(out_dir, "fur_emissive.png")):
        os.remove(os.path.join(out_dir, "fur_emissive.png"))
    tan = np.concatenate([np.cross(nrm, np.array([[0.0, 0.0, 1.0]])) + 1e-3, np.ones((len(nrm), 1))], 1)
    mesh = {"pos": pos, "nrm": nrm, "tan": tan.astype(np.float32), "uv": uv, "idx": idx,
            "part": np.zeros(len(pos), np.int32), "src": np.arange(len(pos)), "color": col}
    return {"mesh": mesh, "tex": out_dir, "joints": body["joints"][nearest][rootv],
            "weights": body["weights"][nearest][rootv], "tier": np.ones(len(pos), np.int32), "alpha": True}
