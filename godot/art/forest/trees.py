"""Procedural forest trees for DRENOVAR (pure Python + numpy, writes .glb).

Each tree is a bark trunk plus alpha-tested foliage cards that sample the shared
atlas (foliage_atlas.py). Foliage normals are "volume" normals (pointing away from
the crown centre) so a crown is lit like one soft mass instead of flat cards, and
every card is emitted as two single-sided faces with the same normal, so the back
of a card is never lit inside-out. Vertex colour carries a cheap ambient occlusion
(darker low and inside the crown).

Variants keep the 0.5.9 city tree slots, sizes and LOD names:
  0 Scots pine, 1 Norway spruce, 2 tall pine, 3 oak, 4 birch, 5 lime/maple
LOD near / mid / far are written as tree{v}-v60.glb, tree{v}mid-v60.glb, tree{v}far-v60.glb.

    python3 trees.py OUT_DIR ATLAS_URI                       # city variants
    python3 trees.py world GAME_JSON OUT_DIR ATLAS_URI       # world-map species
"""
import json
import math
import random
import struct
import sys
from pathlib import Path

import numpy as np

ATLAS_COLS, ATLAS_ROWS = 4, 2
ALPHA_MODE = "MASK"
SPRUCE, PINE, OAK, BIRCH, CAP, BARK_CONIFER, BARK_BROAD = range(7)


def tile_uv(tile, u, v):
    """u, v in 0..1 inside the tile (v=0 at the tile's bottom edge) -> atlas UV (glTF, top-left origin)."""
    col, row = tile % ATLAS_COLS, tile // ATLAS_COLS
    inset = 0.004
    u = inset + u * (1 - 2 * inset)
    v = inset + v * (1 - 2 * inset)
    return ((col + u) / ATLAS_COLS, (row + (1 - v)) / ATLAS_ROWS)


class Mesh:
    def __init__(self):
        self.p, self.n, self.c, self.uv, self.idx = [], [], [], [], []

    def vert(self, p, n, c, uv):
        self.p.append(p); self.n.append(n); self.c.append(c); self.uv.append(uv)
        return len(self.p) - 1

    def quad(self, a, b, c, d, two_sided):
        self.idx += [a, b, c, a, c, d]
        if two_sided:
            self.idx += [a, c, b, a, d, c]

    def tris(self):
        return len(self.idx) // 3


def norm(v):
    v = np.asarray(v, float)
    length = np.linalg.norm(v)
    return v / length if length > 1e-9 else np.array([0.0, 1.0, 0.0])


def card(mesh, base, along, side, length, width, tile, centre, ao, rng, tint):
    """A foliage card from `base` along `along`; the sprig stem sits at `base`."""
    along, side = norm(along), norm(side)
    corners = [
        (base - side * width * 0.5, 0.0, 0.0),
        (base + side * width * 0.5, 1.0, 0.0),
        (base + side * width * 0.5 + along * length, 1.0, 1.0),
        (base - side * width * 0.5 + along * length, 0.0, 1.0),
    ]
    ids = []
    for pos, u, v in corners:
        # Volume normal: away from the crown centre, biased upward (sky light).
        normal = norm(norm(pos - centre) * 0.8 + np.array([0.0, 0.55, 0.0]))
        shade = ao(pos)
        colour = (shade * tint[0], shade * tint[1], shade * tint[2], 1.0)
        ids.append(mesh.vert(pos, normal, colour, tile_uv(tile, u, v)))
    mesh.quad(*ids, two_sided=True)


def trunk(mesh, base, top, r0, r1, sides, tile, rings=4, bend=None):
    bend = bend if bend is not None else np.zeros(3)
    rows = []
    for k in range(rings + 1):
        t = k / rings
        centre = base + (top - base) * t + bend * math.sin(t * math.pi)
        radius = r0 + (r1 - r0) * t
        row = []
        for s in range(sides + 1):
            a = 2 * math.pi * s / sides
            offset = np.array([math.cos(a), 0.0, math.sin(a)])
            pos = centre + offset * radius
            shade = 0.55 + 0.45 * min(1.0, t * 1.4)
            row.append(mesh.vert(pos, norm(offset), (shade, shade, shade, 1.0), tile_uv(tile, s / sides, t * 0.98)))
        rows.append(row)
    for k in range(rings):
        for s in range(sides):
            a, b = rows[k][s], rows[k][s + 1]
            c, d = rows[k + 1][s + 1], rows[k + 1][s]
            mesh.quad(a, d, c, b, two_sided=False)


def conifer(variant, lod, rng):
    mesh = Mesh()
    pine = variant in (0, 2)
    height = {0: 8.3, 1: 8.7, 2: 9.1}[variant]
    radius = {0: 2.9, 1: 2.7, 2: 3.6}[variant]
    crown_start = {0: 0.42, 1: 0.12, 2: 0.5}[variant] * height
    whorls = {0: 14, 1: 22, 2: 14}[variant]
    per_whorl = {0: 7, 1: 9, 2: 8}[variant]
    keep = {"": 0.85, "mid": 0.4, "far": 0.28}[lod]
    tile = PINE if pine else SPRUCE
    sides = {"": 7, "mid": 5, "far": 4}[lod]
    trunk(mesh, np.array([0.0, -0.05, 0.0]), np.array([0.0, height * 0.97, 0.0]), 0.28 if pine else 0.24, 0.04,
          sides, BARK_CONIFER, rings=3 if lod == "far" else 5)
    centre = np.array([0.0, crown_start + (height - crown_start) * 0.42, 0.0])

    def ao(pos):
        rel = (pos[1] - crown_start) / max(0.1, height - crown_start)
        radial = math.hypot(pos[0], pos[2]) / radius
        return 0.42 + 0.58 * min(1.0, 0.35 + rel * 0.55 + radial * 0.45)

    for w in range(whorls):
        rel = w / (whorls - 1)
        y = crown_start + (height - crown_start - 0.6) * rel
        if pine:
            # Rounded, irregular crown: widest a third of the way up.
            profile = math.sin(min(1.0, rel * 1.25) * math.pi * 0.92) ** 0.8 * (1 - rel * 0.35)
        else:
            profile = (1 - rel) ** 0.95
        length = max(0.55, radius * profile * rng.uniform(0.85, 1.1))
        count = max(3, int(round(per_whorl * (0.6 + 0.4 * profile) * keep + rng.random() * 0.5)))
        phase = rng.uniform(0, 2 * math.pi)
        for k in range(count):
            a = phase + 2 * math.pi * k / count + rng.uniform(-0.25, 0.25)
            out = np.array([math.cos(a), 0.0, math.sin(a)])
            droop = (-0.32 if not pine else -0.12) + rng.uniform(-0.12, 0.12) + (0.25 * rel if not pine else 0.0)
            along = norm(out + np.array([0, droop, 0]))
            base = np.array([0.0, y, 0.0]) + out * 0.12
            tint = (rng.uniform(0.9, 1.05), rng.uniform(0.92, 1.06), rng.uniform(0.9, 1.0))
            # Flat branch card (seen from above) and a crossing vertical one (volume from the side).
            card(mesh, base, along, np.cross(along, [0, 1, 0]), length, length * (0.95 if not pine else 0.8), tile, centre, ao, rng, tint)
            if lod != "far":
                card(mesh, base, along, np.array([0.0, 1.0, 0.0]) - along * along[1], length * 0.9, length * 0.55, tile, centre, ao, rng, tint)
    # Leader at the top: two crossed upright sprigs.
    top = np.array([0.0, height - 1.4, 0.0])
    for a in (0.0, math.pi / 2):
        side = np.array([math.cos(a), 0.0, math.sin(a)])
        card(mesh, top, np.array([0.0, 1.0, 0.0]), side, 1.6, 1.1, tile, centre, ao, rng, (1.0, 1.0, 1.0))
    if pine:
        # A horizontal cap fills the crown seen from straight above.
        cap_y = height * (0.86 if not pine else 0.82)
        cap_r = radius * (0.35 if not pine else 0.75)
        ids = []
        for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
            pos = np.array([(u - 0.5) * 2 * cap_r, cap_y, (v - 0.5) * 2 * cap_r])
            ids.append(mesh.vert(pos, norm([pos[0] * 0.3, 1.0, pos[2] * 0.3]), (0.95, 0.95, 0.95, 1), tile_uv(CAP, u, v)))
        mesh.quad(*ids, two_sided=True)
    return mesh


def pine(variant, lod, rng):
    """Scots pine: tall bare reddish trunk, crown of needle tufts in the upper part."""
    mesh = Mesh()
    height = {0: 8.3, 2: 9.1}[variant]
    radius = {0: 2.9, 2: 3.6}[variant]
    keep = {"": 1.0, "mid": 0.45, "far": 0.3}[lod]
    sides = {"": 7, "mid": 5, "far": 4}[lod]
    lean = np.array([rng.uniform(-0.35, 0.35), 0.0, rng.uniform(-0.35, 0.35)])
    top = np.array([0.0, height * 0.9, 0.0]) + lean
    trunk(mesh, np.array([0.0, -0.05, 0.0]), top, 0.27, 0.07, sides, BARK_CONIFER, rings=3 if lod == "far" else 5,
          bend=lean * 0.4)
    crown_centre = np.array([0.0, height * 0.74, 0.0]) + lean * 0.8
    clumps = []
    count = {0: 7, 2: 8}[variant]
    for k in range(count):
        a = 2 * math.pi * k / count + rng.uniform(-0.35, 0.35)
        rel = rng.uniform(0.0, 1.0)
        y = height * (0.6 + 0.3 * rel)
        r = radius * (0.62 - 0.35 * rel) * rng.uniform(0.75, 1.0)
        clumps.append((np.array([math.cos(a) * r, y, math.sin(a) * r]) + lean * (y / height), radius * rng.uniform(0.34, 0.44)))
        if lod != "far":
            base = np.array([0.0, y - 0.5, 0.0]) + lean * (y / height)
            trunk(mesh, base, clumps[-1][0], 0.07, 0.03, 4, BARK_CONIFER, rings=1)
    clumps.append((top + np.array([0, 0.2, 0]), radius * 0.36))

    def ao(pos):
        inner = np.linalg.norm(pos - crown_centre) / radius
        return 0.45 + 0.55 * min(1.0, 0.3 + inner * 0.6)

    per_clump = int(round(16 * keep)) + 2
    for centre, size in clumps:
        for k in range(per_clump):
            d = norm([rng.gauss(0, 1), abs(rng.gauss(0, 1)) * 0.7 + 0.25, rng.gauss(0, 1)])
            base = centre + d * size * rng.uniform(0.1, 0.4)
            along = norm(d + np.array([0, 0.2, 0]))
            side = norm(np.cross(along, norm([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)])))
            length = size * rng.uniform(1.0, 1.35)
            tint = (rng.uniform(0.8, 0.92), rng.uniform(0.84, 0.95), rng.uniform(0.8, 0.9))
            card(mesh, base, along, side, length, length * 0.9, PINE, crown_centre, ao, rng, tint)
    return mesh


def broadleaf(variant, lod, rng):
    mesh = Mesh()
    height = {3: 7.8, 4: 8.2, 5: 8.7}[variant]
    radius = {3: 4.3, 4: 3.4, 5: 4.2}[variant]
    tile = OAK if variant in (3, 5) else BIRCH
    bark = BARK_BROAD
    keep = {"": 1.0, "mid": 0.4, "far": 0.24}[lod]
    sides = {"": 7, "mid": 5, "far": 4}[lod]
    trunk_top = np.array([rng.uniform(-0.3, 0.3), height * 0.55, rng.uniform(-0.3, 0.3)])
    trunk(mesh, np.array([0.0, -0.05, 0.0]), trunk_top, 0.34 if variant == 3 else 0.22, 0.16, sides, bark,
          rings=3 if lod == "far" else 4, bend=np.array([0.2, 0, -0.1]))
    # Crown made of overlapping clumps on main limbs.
    clump_count = {3: 6, 4: 5, 5: 6}[variant]
    clumps = []
    for k in range(clump_count):
        a = 2 * math.pi * k / clump_count + rng.uniform(-0.3, 0.3)
        r = radius * rng.uniform(0.35, 0.62)
        y = height * rng.uniform(0.62, 0.84)
        centre = np.array([math.cos(a) * r, y, math.sin(a) * r])
        clumps.append((centre, radius * rng.uniform(0.42, 0.55)))
        if lod != "far":
            trunk(mesh, trunk_top, centre * np.array([0.7, 1.0, 0.7]) - np.array([0, 0.4, 0]), 0.13, 0.05, 4, bark, rings=2)
    clumps.append((np.array([0.0, height * 0.86, 0.0]), radius * 0.55))
    crown_centre = np.array([0.0, height * 0.72, 0.0])

    def ao(pos):
        inner = np.linalg.norm((pos - crown_centre) * np.array([1.0, 1.4, 1.0])) / radius
        rel = (pos[1] - height * 0.45) / (height * 0.55)
        return 0.4 + 0.6 * min(1.0, 0.3 + inner * 0.55 + rel * 0.35)

    per_clump = int(round({3: 22, 4: 22, 5: 24}[variant] * keep)) + 2
    # Species tone: deep oak green, cooler birch, warmer lime/maple.
    hue = {3: (0.46, 0.55, 0.44), 4: (0.5, 0.6, 0.52), 5: (0.58, 0.58, 0.42)}[variant]
    for centre, size in clumps:
        for k in range(per_clump):
            # Cards on the clump surface, facing out, stem toward the clump centre.
            d = norm([rng.gauss(0, 1), abs(rng.gauss(0, 1)) * 0.9 + 0.1, rng.gauss(0, 1)])
            base = centre + d * size * rng.uniform(0.15, 0.55)
            along = norm(d + np.array([rng.uniform(-0.4, 0.4), 0.3, rng.uniform(-0.4, 0.4)]))
            side = norm(np.cross(along, norm([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)])))
            length = size * rng.uniform(0.9, 1.25)
            tint = tuple(c * rng.uniform(0.92, 1.06) for c in hue)
            card(mesh, base, along, side, length, length * 0.95, tile, crown_centre, ao, rng, tint)
    return mesh


IMPOSTOR_SIDE = (256, 512)
IMPOSTOR_SIZE = (1536, 768)


def impostor_uv(variant, top, u, v):
    """UV in forest60-far.png: side views on the top row (256x512), top views below (256x256)."""
    w, h = IMPOSTOR_SIZE
    x0 = variant * IMPOSTOR_SIDE[0]
    if top:
        y0, th = IMPOSTOR_SIDE[1], 256
    else:
        y0, th = 0, IMPOSTOR_SIDE[1]
    inset = 1.5
    px = x0 + inset + u * (IMPOSTOR_SIDE[0] - 2 * inset)
    py = y0 + inset + (1 - v) * (th - 2 * inset)
    return (px / w, py / h)


def impostor(variant, sizes):
    """Far LOD: three crossed side views and one top view of the baked tree (16 triangles)."""
    mesh = Mesh()
    frame, half = sizes[str(variant)]
    crown_y = frame * 0.5 * (0.55 if variant == 1 else 0.7)
    centre = np.array([0.0, crown_y, 0.0])
    height_cap = frame

    def add_card(corners, top):
        ids = []
        for pos, u, v in corners:
            pos = np.asarray(pos, float)
            normal = norm(norm(pos - centre) * 0.6 + np.array([0.0, 0.8, 0.0]))
            # The bake already holds the crown's AO; slightly darker to match lit cards.
            shade = 0.8
            ids.append(mesh.vert(pos, normal, (shade, shade, shade, 1.0), impostor_uv(variant, top, u, v)))
        mesh.quad(*ids, two_sided=True)

    for k in range(3):
        a = math.pi * k / 3
        side = np.array([math.cos(a), 0.0, math.sin(a)]) * frame * 0.25
        up = np.array([0.0, height_cap, 0.0])
        add_card([(-side, 0, 0), (side, 1, 0), (side + up, 1, 1), (-side + up, 0, 1)], False)
    # Top view at crown height fills the canopy seen from the game camera.
    y = frame * (0.42 if variant == 1 else 0.62)
    if variant in (3, 4, 5):
        y = frame * 0.42
    add_card([((-half, y, half), 0, 0), ((half, y, half), 1, 0), ((half, y, -half), 1, 1), ((-half, y, -half), 0, 1)], True)
    return mesh


def write_glb(mesh, path, atlas_uri, name, cutoff=0.42):
    pos = np.asarray(mesh.p, np.float32)
    nor = np.asarray([norm(n) for n in mesh.n], np.float32)
    col = np.clip(np.asarray(mesh.c, np.float32), 0, 1)
    uv = np.asarray(mesh.uv, np.float32)
    idx = np.asarray(mesh.idx, np.uint32 if len(pos) > 65535 else np.uint16)
    blobs, views, accessors = [], [], []
    offset = 0

    def add(array, target, component, kind, minmax=False):
        nonlocal offset
        data = array.tobytes()
        pad = (-len(data)) % 4
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        blobs.append(data + b"\0" * pad)
        offset += len(data) + pad
        acc = {"bufferView": len(views) - 1, "componentType": component, "count": len(array), "type": kind}
        if minmax:
            acc["min"] = array.min(axis=0).tolist()
            acc["max"] = array.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    a_pos = add(pos, 34962, 5126, "VEC3", True)
    a_nor = add(nor, 34962, 5126, "VEC3")
    a_col = add(col, 34962, 5126, "VEC4")
    a_uv = add(uv, 34962, 5126, "VEC2")
    a_idx = add(idx, 34963, 5125 if idx.dtype == np.uint32 else 5123, "SCALAR")
    doc = {
        "asset": {"version": "2.0", "generator": "DRENOVAR forest trees.py"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_nor, "COLOR_0": a_col,
                    "TEXCOORD_0": a_uv}, "indices": a_idx, "material": 0}]}],
        "materials": [{"name": "Drenovar_Forest60", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                       "metallicFactor": 0, "roughnessFactor": 0.9}, "alphaMode": ALPHA_MODE, "alphaCutoff": cutoff,
                       "doubleSided": False}],
        "textures": [{"source": 0, "sampler": 0}],
        "images": [{"uri": atlas_uri}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "buffers": [{"byteLength": offset}],
        "bufferViews": views, "accessors": accessors,
    }
    body = b"".join(blobs)
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * ((-len(js)) % 4)
    total = 12 + 8 + len(js) + 8 + len(body)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(body), 0x004E4942) + body)


def impostor_sizes(out):
    """Sizes written by bake_impostors.gd; None until the far atlas has been baked."""
    path = Path(out).resolve().parents[1] / "environment" / "forest60-far.json"
    return json.loads(path.read_text()) if path.exists() else None


FAR_URI = "../../environment/forest60-far.png"


def main(out_dir, atlas_uri):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    sizes = impostor_sizes(out)
    for variant in range(6):
        for lod in ("", "mid", "far"):
            rng = random.Random(600 + variant * 7 + {"": 0, "mid": 1, "far": 2}[lod])
            if lod == "far" and sizes:
                mesh = impostor(variant, sizes)
                name = f"tree{variant}far-v60"
                write_glb(mesh, out / f"{name}.glb", FAR_URI, name, cutoff=0.5)
                report[name] = mesh.tris()
                continue
            if variant == 1:
                mesh = conifer(variant, lod, rng)
            elif variant in (0, 2):
                mesh = pine(variant, lod, rng)
            else:
                mesh = broadleaf(variant, lod, rng)
            name = f"tree{variant}{lod}-v60"
            write_glb(mesh, out / f"{name}.glb", atlas_uri, name)
            report[name] = mesh.tris()
    print(json.dumps(report))


if __name__ == "__main__" and sys.argv[1] != "world":
    main(sys.argv[1], sys.argv[2])


def build_world(game_json, out_dir, atlas_uri):
    """World-map tree species reuse the city variants, scaled by each species' canopy scale."""
    data = json.loads(Path(game_json).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    sizes = impostor_sizes(out)
    for species, spec in data["environmentModels"].items():
        canopy = spec.get("canopy")
        if not spec.get("tree") or not isinstance(canopy, dict):
            continue
        variant, scale = int(canopy["variant"]), float(canopy["scale"])
        # World trees are small on screen: the near model is the light card crown, the far one the impostor.
        for lod, suffix in (("far", ""), ("impostor", "-far")):
            rng = random.Random(f"{species}{lod}")
            far_impostor = lod == "impostor" and sizes
            if far_impostor:
                mesh = impostor(variant, sizes)
            else:
                mesh = conifer(variant, lod, rng) if variant == 1 else pine(variant, lod, rng) if variant in (0, 2) else broadleaf(variant, lod, rng)
            mesh.p = [np.asarray(p) * scale for p in mesh.p]
            name = f"{species}{suffix}"
            write_glb(mesh, out / f"{name}.glb", FAR_URI if far_impostor else atlas_uri, name, cutoff=0.5 if far_impostor else 0.42)
            report[name] = mesh.tris()
    print(json.dumps(report))
    return report


if __name__ == "__main__" and len(sys.argv) > 3 and sys.argv[1] == "world":
    build_world(sys.argv[2], sys.argv[3], sys.argv[4])
