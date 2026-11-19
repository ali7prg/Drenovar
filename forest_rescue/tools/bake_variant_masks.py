#!/usr/bin/env python3
"""Bake <id>_variant_mask.png for the six v2 civilians (captive look variation).

The v2 human GLBs carry ONE merged body material, so the per-captive tints of
humans/captive_variants.json (tint.cloth, tint.hair) need a mask to know which texels are which:
  R = cloth (tintable garments: shirt, vest, apron, cloak, hood/cap, skirt, trousers)
  G = hair  (hair mass, beard)
  B = keep  (skin, the emerald rescue band, boots, belts/metal, bag/props)

Per texel the label comes from the body part that owns it (dominant skin weight of the LOD0
triangle rasterised in UV space: head / hands / feet / props / cloth bones) refined by the
painted colour (skin tones and the emerald band are never tinted, dark hair-coloured texels on
the head are hair). Islands are dilated by 6 px so mip levels do not bleed. Output is 1024 px.

    python3 forest_rescue/tools/bake_variant_masks.py
"""
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HUMANS = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans")
SIZE = 1024
VISUALS = ["cooper", "courier", "ferryman", "herbalist", "miller", "quarry_worker"]

HEAD = {"Head", "Neck"}
HAIRY = {"Head"}
SKIN = {"LeftHand", "RightHand"} | {f"{s}{f}{n}" for s in ("Left", "Right") for f in ("Thumb", "Index", "Middle", "Ring", "Pinky") for n in ("1", "2")}
KEEP = {"LeftFoot", "RightFoot", "LeftToes", "RightToes", "Bag", "PropR", "PropL"}
CLOTH_BONES = {"Hood", "Cloak1", "Cloak2", "SkirtFront1", "SkirtFront2", "SkirtBack1", "SkirtBack2", "SkirtLeft", "SkirtRight"}
ARMS = {"LeftLowerArm", "RightLowerArm", "LeftUpperArm", "RightUpperArm"}

COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}


def read_glb(path):
    data = open(path, "rb").read()
    clen = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + clen])
    off = 20 + clen
    blen = struct.unpack("<I", data[off:off + 4])[0]
    binary = data[off + 8:off + 8 + blen]
    return js, binary


def accessor(js, binary, index):
    acc = js["accessors"][index]
    view = js["bufferViews"][acc["bufferView"]]
    count = acc["count"]
    comps = COMPONENTS[acc["type"]]
    dtype = DTYPES[acc["componentType"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 0)
    item = np.dtype(dtype).itemsize * comps
    if stride and stride != item:
        raw = np.frombuffer(binary, dtype=np.uint8, count=stride * (count - 1) + item, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(count, item), strides=(stride, 1))
        arr = np.frombuffer(rows.tobytes(), dtype=dtype).reshape(count, comps)
    else:
        arr = np.frombuffer(binary, dtype=dtype, count=count * comps, offset=start).reshape(count, comps)
    if acc.get("normalized"):
        arr = arr.astype(np.float32) / float(np.iinfo(dtype).max)
    return arr


def body_texture(js, binary, material_index):
    tex = js["materials"][material_index]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    image = js["images"][js["textures"][tex]["source"]]
    view = js["bufferViews"][image["bufferView"]]
    blob = binary[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
    return Image.open(io.BytesIO(blob)).convert("RGB")


def rasterize(uv_tris, labels, size):
    """Per-texel label of the triangle covering it (UV space, v down), -1 = empty."""
    out = np.full((size, size), -1, dtype=np.int16)
    for tri, label in zip(uv_tris, labels):
        p = tri * size
        x0, y0 = np.floor(p.min(axis=0)).astype(int)
        x1, y1 = np.ceil(p.max(axis=0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
        block = out[y0:y1 + 1, x0:x1 + 1]
        block[inside] = label
    return out


def hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    s = np.where(mx > 1e-6, d / (mx + 1e-6), 0)
    return h, s, mx


def bake(visual):
    path = os.path.join(HUMANS, f"lf_civilian_{visual}.glb")
    js, binary = read_glb(path)
    joints = [js["nodes"][j]["name"] for j in js["skins"][0]["joints"]]
    mesh = next(m for m in js["meshes"] if m["name"].endswith("_LOD0"))
    prim = next(p for p in mesh["primitives"] if js["materials"][p["material"]]["name"].endswith("_body"))
    attrs = prim["attributes"]
    uv = accessor(js, binary, attrs["TEXCOORD_0"]).astype(np.float32)
    pos = accessor(js, binary, attrs["POSITION"]).astype(np.float32)
    jidx = accessor(js, binary, attrs["JOINTS_0"]).astype(np.int32)
    wts = accessor(js, binary, attrs["WEIGHTS_0"]).astype(np.float32)
    idx = accessor(js, binary, prim["indices"]).reshape(-1, 3)
    dominant = jidx[np.arange(len(jidx)), wts.argmax(axis=1)]
    names = [joints[d] for d in dominant]
    head_top = pos[:, 1].max()
    # Triangle label: 0 cloth, 1 head (hair or skin by colour), 2 skin, 3 keep, 4 arm (sleeve or
    # bare skin by colour). Garments may be tan/brown like skin: colour only decides on head/arms.
    labels = []
    for tri in idx:
        votes = [names[v] for v in tri]
        name = max(set(votes), key=votes.count)
        y = pos[tri, 1].mean()
        if name in SKIN:
            labels.append(2)
        elif name in KEEP:
            labels.append(3)
        elif name in HEAD and name not in CLOTH_BONES:
            labels.append(1 if y > head_top - 0.42 else 0)
        elif name in ARMS:
            labels.append(4)
        else:
            labels.append(0)
    tris_uv = uv[idx]
    region = rasterize(tris_uv, labels, SIZE)
    tex = np.asarray(body_texture(js, binary, prim["material"]).resize((SIZE, SIZE), Image.LANCZOS), dtype=np.float32) / 255.0
    h, s, v = hsv(tex)
    skin_like = (h >= 8) & (h <= 38) & (s >= 0.18) & (s <= 0.62) & (v >= 0.45)
    emerald = (h >= 85) & (h <= 175) & (s >= 0.22) & (v >= 0.18)
    dark_leather = (v < 0.16)
    hairish = ~skin_like & (s < 0.75)
    mask = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    cloth = ((region == 0) & ~emerald & ~dark_leather) | ((region == 4) & ~skin_like & ~emerald & ~dark_leather)
    head_hair = (region == 1) & hairish & ~emerald
    mask[..., 0] = cloth
    mask[..., 1] = head_hair
    mask[..., 2] = (region >= 0) & ~cloth & ~head_hair
    img = Image.fromarray((mask * 255).astype(np.uint8), "RGB")
    # Soften the class edges a little and dilate islands into the UV gutter (mip safety).
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    filled = np.asarray(img).copy()
    empty = region < 0
    for _ in range(6):
        grown = np.asarray(Image.fromarray(filled).filter(ImageFilter.MaxFilter(3)))
        filled[empty] = grown[empty]
    out = os.path.join(HUMANS, f"lf_civilian_{visual}_variant_mask.png")
    Image.fromarray(filled).save(out, optimize=True)
    stats = {k: float(m.mean()) for k, m in (("cloth", cloth), ("hair", head_hair))}
    print(f"{visual}: {out} cloth {stats['cloth']:.3f} hair {stats['hair']:.3f}")


if __name__ == "__main__":
    for visual in (sys.argv[1:] or VISUALS):
        bake(visual)
