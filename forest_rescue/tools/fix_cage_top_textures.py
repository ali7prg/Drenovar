#!/usr/bin/env python3
"""Re-texture the faces the high city camera looks straight down at, on the cage atlases.

The props v2 cages are textured by projecting the painting (art/cage_variants_gate_sockets.png);
faces the painting sees only at grazing angles (cage floor, plinth / pallet tops, the root cage's
roots seen from above) got the synthesised fill, which reads as diagonal stripes (iron), a blotchy
"cauliflower" (root floor) and camouflage (roots) from the game camera. This tool rewrites only
those texels of the existing atlases (LOD0/1/2) -- geometry, UVs, nodes, sockets and clips of the
GLBs are untouched (the textures are external files next to the GLB):

* top-facing faces (glTF normal y > 0.7) below the floor/plinth height: a floor texture quilted
  (Efros-Freeman, min-error cuts) from the painted floor pixels of the OPEN view, rectified to a
  top view, laid in cage space (x, z) at one texel density, planks parallel to the front face;
* root cage roots (main + roof meshes above the floor): bark quilted from the painted root bark
  (closed view), mapped per triangle along the local tube axis (smallest-eigenvalue direction of
  the neighbouring normals) so the grain follows the root;
* the painted low-frequency light of the old texels is kept as a gentle luminance modulation.

    /opt/tools/blender-venv/bin/python forest_rescue/tools/fix_cage_top_textures.py [iron root oak]
"""
import json
import os
import struct
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROPS = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "props")
ART = os.path.join(REPO, "forest_rescue", "delivery", "art", "cage_variants_gate_sockets.png")
BACKUP = os.path.join(REPO, "forest_rescue", "blender", "textures", "props", "v2", "pre_top_fix")

# Painted floor (top surface) of each OPEN view, as a quad (x, y) in art pixels: back-left,
# back-right, front-right, front-left; rectified to a top view of the given size in metres.
FLOORS = {
    "iron": {"quad": [(742, 680), (870, 677), (878, 699), (742, 700)], "metres": (3.3, 1.2), "ppm": 72},
    "root": {"quad": [(1252, 685), (1333, 683), (1346, 707), (1243, 707)], "metres": (2.6, 1.0), "ppm": 64},
    "oak": {"quad": [(208, 690), (372, 690), (392, 718), (190, 718)], "metres": (3.3, 1.3), "ppm": 70},
}
BARK_STRIPS = [(1210, 285, 1236, 345), (1207, 352, 1248, 398), (1095, 296, 1112, 356)]
CAGES = {
    "iron": {"id": "lf_cage_iron", "floor_max": 0.62},
    "root": {"id": "lf_cage_root", "floor_max": 0.34, "bark": True},
    "oak": {"id": "lf_cage_wood", "floor_max": 0.30},
}
COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}


def read_glb(path):
    data = open(path, "rb").read()
    clen = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + clen])
    off = 20 + clen
    blen = struct.unpack("<I", data[off:off + 4])[0]
    return js, data[off + 8:off + 8 + blen]


def accessor(js, binary, index):
    acc = js["accessors"][index]
    view = js["bufferViews"][acc["bufferView"]]
    comps = COMPONENTS[acc["type"]]
    dtype = DTYPES[acc["componentType"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 0)
    item = np.dtype(dtype).itemsize * comps
    count = acc["count"]
    if stride and stride != item:
        raw = np.frombuffer(binary, dtype=np.uint8, count=stride * (count - 1) + item, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(count, item), strides=(stride, 1))
        return np.frombuffer(rows.tobytes(), dtype=dtype).reshape(count, comps)
    return np.frombuffer(binary, dtype=dtype, count=count * comps, offset=start).reshape(count, comps)


def node_matrix(node):
    m = np.eye(4)
    if "matrix" in node:
        return np.array(node["matrix"]).reshape(4, 4).T
    t = node.get("translation", [0, 0, 0])
    r = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    x, y, z, w = r
    rot = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m[:3, :3] = rot * np.array(s)
    m[:3, 3] = t
    return m


def world_matrices(js):
    out = {}

    def walk(i, parent):
        m = parent @ node_matrix(js["nodes"][i])
        out[i] = m
        for c in js["nodes"][i].get("children", []):
            walk(c, m)
    for r in js["scenes"][0]["nodes"]:
        walk(r, np.eye(4))
    return out


def rectified(art, quad, metres, ppm):
    w, h = int(metres[0] * ppm), int(metres[1] * ppm)
    dst = np.float32([(0, 0), (w, 0), (w, h), (0, h)])
    hmat = cv2.getPerspectiveTransform(np.float32(quad), dst)
    return cv2.warpPerspective(art, hmat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def quilt(sample, out_h, out_w, block, overlap, rng):
    """Efros-Freeman image quilting with minimum-error boundary cuts (vertical + horizontal)."""
    sample = sample.astype(np.float32)
    sh, sw = sample.shape[:2]
    block = min(block, sh - 1, sw - 1)
    overlap = min(overlap, block // 2)
    step = block - overlap
    rows = (out_h - overlap + step - 1) // step
    cols = (out_w - overlap + step - 1) // step
    out = np.zeros((rows * step + overlap, cols * step + overlap, 3), np.float32)
    candidates = [(y, x) for y in range(0, sh - block, 2) for x in range(0, sw - block, 2)] or [(0, 0)]
    for r in range(rows):
        for c in range(cols):
            y0, x0 = r * step, c * step
            errs = []
            for (sy, sx) in candidates:
                patch = sample[sy:sy + block, sx:sx + block]
                e = 0.0
                if c > 0:
                    e += np.sum((patch[:, :overlap] - out[y0:y0 + block, x0:x0 + overlap]) ** 2)
                if r > 0:
                    e += np.sum((patch[:overlap, :] - out[y0:y0 + overlap, x0:x0 + block]) ** 2)
                errs.append(e)
            errs = np.array(errs)
            good = np.nonzero(errs <= errs.min() * 1.1 + 1e-6)[0]
            sy, sx = candidates[int(rng.choice(good))]
            patch = sample[sy:sy + block, sx:sx + block].copy()
            mask = np.ones((block, block), bool)
            if c > 0:
                diff = np.sum((patch[:, :overlap] - out[y0:y0 + block, x0:x0 + overlap]) ** 2, axis=2)
                cut = min_cut(diff)
                for i in range(block):
                    mask[i, :cut[i]] = False
            if r > 0:
                diff = np.sum((patch[:overlap, :] - out[y0:y0 + overlap, x0:x0 + block]) ** 2, axis=2).T
                cut = min_cut(diff)
                for j in range(block):
                    mask[:cut[j], j] = False
            region = out[y0:y0 + block, x0:x0 + block]
            region[mask] = patch[mask]
    return np.clip(out[:out_h, :out_w], 0, 255).astype(np.uint8)


def min_cut(err):
    """Column index per row of the minimum-error vertical path through err (rows x overlap)."""
    h, w = err.shape
    cost = err.copy()
    for i in range(1, h):
        for j in range(w):
            lo, hi = max(0, j - 1), min(w, j + 2)
            cost[i, j] += cost[i - 1, lo:hi].min()
    path = np.zeros(h, int)
    path[-1] = int(np.argmin(cost[-1]))
    for i in range(h - 2, -1, -1):
        j = path[i + 1]
        lo, hi = max(0, j - 1), min(w, j + 2)
        path[i] = lo + int(np.argmin(cost[i, lo:hi]))
    return path


def tile_from(sample, h, w, y0, x0):
    """h x w block from `sample` starting at (y0, x0), mirrored-tiled so any size works."""
    sh, sw = sample.shape[:2]
    ys = np.abs(((np.arange(h) + y0) % (2 * sh)) - (np.arange(h) + y0) % (2 * sh) // sh * (2 * ((np.arange(h) + y0) % sh) + 1))
    ys = np.where(((np.arange(h) + y0) // sh) % 2 == 0, (np.arange(h) + y0) % sh, sh - 1 - (np.arange(h) + y0) % sh)
    xs = np.where(((np.arange(w) + x0) // sw) % 2 == 0, (np.arange(w) + x0) % sw, sw - 1 - (np.arange(w) + x0) % sw)
    return sample[ys][:, xs]


def plank_floor(sample, ppm, rng, metres=5.0, plank=0.3):
    """Plank deck quilted from the painted deck: every plank is a run of grain-aligned strips
    cut from the painting (grain along u = cage x), butt joints and seams darkened."""
    n = int(metres * ppm)
    w = max(6, int(plank * ppm))
    out = np.zeros((n, n, 3), np.float32)
    s = sample.astype(np.float32)
    if s.shape[0] < w + 2:
        s = cv2.resize(s, (s.shape[1], w + 2), interpolation=cv2.INTER_CUBIC)
    y = 0
    while y < n:
        x = -int(rng.integers(0, int(1.2 * ppm)))
        while x < n:
            length = min(int(rng.uniform(1.1, 2.2) * ppm), s.shape[1])
            sy = int(rng.integers(0, s.shape[0] - w + 1))
            sx = int(rng.integers(0, s.shape[1] - length + 1))
            block = s[sy:sy + w, sx:sx + length] * rng.uniform(0.9, 1.08)
            x0, x1 = max(x, 0), min(x + length, n)
            if x1 > x0:
                out[y:y + w, x0:x1] = block[:min(w, n - y), x0 - x:x1 - x]
                out[y:y + w, x0:min(x0 + 2, n)] *= 0.62           # butt joint
            x += length
        out[y:min(y + 2, n), :] *= 0.55                           # seam between planks
        y += w
    return np.clip(out, 0, 255).astype(np.uint8)


def slab_floor(sample, ppm, rng, metres=5.0):
    """Packed earth / flagstones quilted from the painted slab floor: irregular running-bond slabs,
    each filled with a patch of the painting, darker joints."""
    n = int(metres * ppm)
    out = np.zeros((n, n, 3), np.float32)
    s = sample.astype(np.float32)
    y = 0
    while y < n:
        h = int(rng.uniform(0.42, 0.7) * ppm)
        x = -int(rng.uniform(0.0, 0.5) * ppm)
        h = min(h, s.shape[0])
        while x < n:
            w = min(int(rng.uniform(0.45, 0.95) * ppm), s.shape[1])
            sy = int(rng.integers(0, s.shape[0] - h + 1))
            sx = int(rng.integers(0, s.shape[1] - w + 1))
            block = s[sy:sy + h, sx:sx + w] * rng.uniform(0.9, 1.08)
            x0, x1 = max(x, 0), min(x + w, n)
            y1 = min(y + h, n)
            if x1 > x0:
                out[y:y1, x0:x1] = block[:y1 - y, x0 - x:x1 - x]
                out[y:y1, x0:min(x0 + 3, n)] *= 0.6
            x += w
        out[y:min(y + 3, n), :] *= 0.6
        y += h
    return np.clip(cv2.GaussianBlur(out, (0, 0), 0.7), 0, 255).astype(np.uint8)


def floor_texture(art, kind, rng):
    spec = FLOORS[kind]
    top = rectified(art, spec["quad"], spec["metres"], spec["ppm"])
    # Keep the clean middle of the painted floor (no rail / posts / door frame / front edge).
    hh, ww = top.shape[:2]
    top = top[int(hh * 0.14):int(hh * 0.9), int(ww * 0.04):int(ww * 0.9)]
    if kind == "iron":
        return plank_floor(top, spec["ppm"], rng), spec["ppm"]
    return slab_floor(top, spec["ppm"], rng), spec["ppm"]


def bark_texture(art, rng, ppm=110):
    """Bark with the grain along v: vertical runs cut from the painted root trunks (closed view)."""
    strips = []
    for (x0, y0, x1, y1) in BARK_STRIPS:
        s = art[y0:y1, x0:x1].astype(np.float32)
        strips.append(cv2.resize(s, (int((x1 - x0) * 1.8), int((y1 - y0) * 1.8)), interpolation=cv2.INTER_CUBIC))
    width, height = 192, 384
    out = np.zeros((height, width, 3), np.float32)
    x = 0
    while x < width:
        src = strips[int(rng.integers(0, len(strips)))]
        w = min(src.shape[1] - 4, int(rng.integers(18, 34)))
        y = -int(rng.integers(0, 60))
        sx = int(rng.integers(2, max(3, src.shape[1] - w - 2)))
        while y < height:
            h = min(int(rng.integers(70, 150)), src.shape[0])
            sy = int(rng.integers(0, src.shape[0] - h + 1))
            block = src[sy:sy + h, sx:sx + w]
            y0, y1 = max(y, 0), min(y + h, height)
            if y1 > y0:
                out[y0:y1, x:min(x + w, width)] = block[y0 - y:y1 - y, :min(w, width - x)]
            y += h
        x += w
    out = cv2.GaussianBlur(out, (0, 0), 0.8)
    return np.clip(out, 0, 255).astype(np.uint8), ppm


def raster_triangles(uv, faces, size):
    """Yields (face index, ys, xs, barycentric (n x 3)) for texels covered by each UV triangle."""
    for f, tri in enumerate(faces):
        p = uv[tri] * size
        x0, y0 = np.floor(p.min(axis=0)).astype(int) - 1
        x1, y1 = np.ceil(p.max(axis=0)).astype(int) + 1
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        px, py = xs + 0.5, ys + 0.5
        (ax, ay), (bx, by), (cx, cy) = p
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
        w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any():
            continue
        yield f, ys[inside], xs[inside], np.stack([w0[inside], w1[inside], w2[inside]], axis=1)


def tube_axes(cent, normals, radius=0.14):
    """Per triangle: the direction normals vary least along (root tube axis)."""
    cell = radius
    keys = np.floor(cent / cell).astype(np.int64)
    buckets = {}
    for i, k in enumerate(map(tuple, keys)):
        buckets.setdefault(k, []).append(i)
    axes = np.zeros_like(normals)
    for i, k in enumerate(map(tuple, keys)):
        near = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    near.extend(buckets.get((k[0] + dx, k[1] + dy, k[2] + dz), ()))
        near = np.array(near)
        near = near[np.linalg.norm(cent[near] - cent[i], axis=1) <= radius]
        n = normals[near]
        cov = n.T @ n
        val, vec = np.linalg.eigh(cov)
        axes[i] = vec[:, 0]
    return axes


def fix(kind, art, rng):
    spec = CAGES[kind]
    aid = spec["id"]
    js, binary = read_glb(os.path.join(PROPS, aid + ".glb"))
    worlds = world_matrices(js)
    floor_tex, floor_ppm = floor_texture(art, kind, rng)
    cv2.imwrite(os.path.join(BACKUP, f"{aid}_floor_quilt.png"), cv2.cvtColor(floor_tex, cv2.COLOR_RGB2BGR))
    bark_tex, bark_ppm = (bark_texture(art, rng) if spec.get("bark") else (None, 0))
    bark_mean = cv2.GaussianBlur(bark_tex.astype(np.float32), (0, 0), 6.0) if bark_tex is not None else None
    if bark_tex is not None:
        cv2.imwrite(os.path.join(BACKUP, f"{aid}_bark_quilt.png"), cv2.cvtColor(bark_tex, cv2.COLOR_RGB2BGR))
    files = [f"{aid}_c.jpg", f"{aid}_lod1_c.jpg", f"{aid}_lod2_c.jpg"]
    stats = {}
    for lod, fname in enumerate(files):
        path = os.path.join(PROPS, fname)
        backup = os.path.join(BACKUP, fname)
        if not os.path.exists(backup):
            cv2.imwrite(backup, cv2.imread(path), [cv2.IMWRITE_JPEG_QUALITY, 100])
        atlas = cv2.cvtColor(cv2.imread(backup), cv2.COLOR_BGR2RGB)
        size = atlas.shape[0]
        lum = cv2.GaussianBlur(cv2.cvtColor(atlas, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), max(2.0, size / 256.0))
        low = cv2.GaussianBlur(atlas.astype(np.float32), (0, 0), max(1.5, size / 340.0))
        out = atlas.copy()
        written = np.zeros(atlas.shape[:2], bool)
        counts = {"floor": 0, "bark": 0}
        for ni, node in enumerate(js["nodes"]):
            name = node.get("name", "")
            if "mesh" not in node or not name.endswith(f"_LOD{lod}"):
                continue
            part = name[len(aid) + 1:-5]
            if part not in ("", "roof"):
                continue                      # door / latch / socket plates keep their painting
            mesh = js["meshes"][node["mesh"]]
            m = worlds[ni]
            for prim in mesh["primitives"]:
                pos = accessor(js, binary, prim["attributes"]["POSITION"]).astype(np.float64)
                uv = accessor(js, binary, prim["attributes"]["TEXCOORD_0"]).astype(np.float64)
                faces = accessor(js, binary, prim["indices"]).reshape(-1, 3).astype(np.int64)
                wp = pos @ m[:3, :3].T + m[:3, 3]
                a, b, c = wp[faces[:, 0]], wp[faces[:, 1]], wp[faces[:, 2]]
                nrm = np.cross(b - a, c - a)
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
                cent = (a + b + c) / 3.0
                is_floor = (nrm[:, 1] > 0.7) & (cent[:, 1] < spec["floor_max"])
                is_bark = np.zeros(len(faces), bool)
                axes = None
                if bark_tex is not None:
                    is_bark = ~is_floor & (cent[:, 1] > spec["floor_max"] - 0.05)
                    axes = tube_axes(cent, nrm)
                for f, ys, xs, bary in raster_triangles(uv, faces, size):
                    if not (is_floor[f] or is_bark[f]):
                        continue
                    p = bary @ wp[faces[f]]
                    if is_floor[f]:
                        u = np.mod((p[:, 0] + 2.5) * floor_ppm, floor_tex.shape[1] - 1).astype(int)
                        v = np.mod((p[:, 2] + 2.5) * floor_ppm, floor_tex.shape[0] - 1).astype(int)
                        col = floor_tex[v, u]
                        counts["floor"] += len(ys)
                    else:
                        ax = axes[f]
                        bx = np.cross(ax, nrm[f])
                        bx /= max(np.linalg.norm(bx), 1e-9)
                        s = p @ ax
                        t = p @ bx
                        u = np.mod(t * bark_ppm, bark_tex.shape[1] - 1).astype(int)
                        v = np.mod(s * bark_ppm, bark_tex.shape[0] - 1).astype(int)
                        col = bark_tex[v, u]
                        bark_mean_px = bark_mean[v, u]
                        counts["bark"] += len(ys)
                    if is_floor[f]:
                        # Keep the painted low-frequency light (contact shadow under bars / roots).
                        shade = np.clip(0.72 + 0.28 * lum[ys, xs] / max(float(np.mean(lum[ys, xs])), 1.0), 0.6, 1.2)
                        out[ys, xs] = np.clip(col.astype(np.float32) * shade[:, None], 0, 255).astype(np.uint8)
                    else:
                        # Roots: keep the painted colour / light of the projection (low-pass of the
                        # old texels) and replace only the fine detail by grain along the root axis.
                        detail = col.astype(np.float32) / np.maximum(bark_mean_px, 1.0)
                        detail = 1.0 + (detail - 1.0) * 0.75
                        out[ys, xs] = np.clip(low[ys, xs] * detail, 0, 255).astype(np.uint8)
                    written[ys, xs] = True
        # Bleed the rewritten texels 2 px into the UV gutter (mip safety), only onto old fill.
        grown = out.copy()
        mask = written.astype(np.uint8)
        for _ in range(2):
            dil = cv2.dilate(grown, np.ones((3, 3), np.uint8))
            mdil = cv2.dilate(mask, np.ones((3, 3), np.uint8))
            ring = (mdil > 0) & (mask == 0)
            grown[ring] = dil[ring]
            mask = mdil
        q = 90 if lod == 0 else 88
        cv2.imwrite(path, cv2.cvtColor(grown, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, q])
        stats[fname] = counts
    print(kind, stats)


if __name__ == "__main__":
    os.makedirs(BACKUP, exist_ok=True)
    art = cv2.cvtColor(cv2.imread(ART), cv2.COLOR_BGR2RGB)
    rng = np.random.default_rng(7)
    for kind in (sys.argv[1:] or ["iron", "root"]):
        fix(kind, art, rng)
