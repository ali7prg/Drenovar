"""GLB post-processing (pure python): read/write, node visibility, animation extras, stats."""
import json
import struct

import numpy as np


def read(path):
    b = open(path, "rb").read()
    off = 12
    js, binc = None, b""
    while off < len(b):
        clen, ctype = struct.unpack("<I4s", b[off:off + 8])
        chunk = b[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(chunk)
        elif ctype == b"BIN\x00":
            binc = chunk
        off += 8 + clen
    return js, binc


def write(path, js, binc):
    j = json.dumps(js, separators=(",", ":")).encode("utf-8")
    j += b" " * ((4 - len(j) % 4) % 4)
    binc = binc + b"\x00" * ((4 - len(binc) % 4) % 4)
    total = 12 + 8 + len(j) + (8 + len(binc) if binc else 0)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(j), b"JSON"))
        f.write(j)
        if binc:
            f.write(struct.pack("<I4s", len(binc), b"BIN\x00"))
            f.write(binc)


def postprocess(path, hidden_nodes=(), anim_extras=None, scene_extras=None):
    js, binc = read(path)
    used = set(js.get("extensionsUsed", []))
    for n in js.get("nodes", []):
        if n.get("name") in hidden_nodes:
            n.setdefault("extensions", {})["KHR_node_visibility"] = {"visible": False}
            used.add("KHR_node_visibility")
    if used:
        js["extensionsUsed"] = sorted(used)
    for a in js.get("animations", []):
        if anim_extras and a.get("name") in anim_extras:
            a["extras"] = anim_extras[a["name"]]
    if scene_extras:
        js.setdefault("scenes", [{}])[0].setdefault("extras", {}).update(scene_extras)
    write(path, js, binc)
    return js


CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def accessor(js, binc, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    dt = CT[a["componentType"]]
    nc = NC[a["type"]]
    n = a["count"]
    stride = bv.get("byteStride", 0)
    isz = np.dtype(dt).itemsize * nc
    if stride and stride != isz:
        raw = np.frombuffer(binc, np.uint8, count=stride * n, offset=off).reshape(n, stride)[:, :isz]
        return np.frombuffer(raw.tobytes(), dt).reshape(n, nc)
    return np.frombuffer(binc, dt, count=n * nc, offset=off).reshape(n, nc)


def stats(path):
    """Per-mesh triangle counts, joints used, max influences, animation lengths (verification)."""
    js, binc = read(path)
    out = {"meshes": {}, "animations": {}, "skins": [len(s["joints"]) for s in js.get("skins", [])],
           "images": [(im.get("name"), im.get("mimeType")) for im in js.get("images", [])],
           "extensionsUsed": js.get("extensionsUsed", [])}
    node_of_mesh = {n["mesh"]: n for n in js.get("nodes", []) if "mesh" in n}
    for mi, m in enumerate(js.get("meshes", [])):
        tris = 0
        joints = set()
        maxinf = 0
        for pr in m["primitives"]:
            tris += js["accessors"][pr["indices"]]["count"] // 3
            if "JOINTS_0" in pr["attributes"]:
                J = accessor(js, binc, pr["attributes"]["JOINTS_0"])
                W = accessor(js, binc, pr["attributes"]["WEIGHTS_0"]).astype(float)
                if W.dtype != np.float32 and W.max() > 1.5:
                    W = W / 255.0 if W.max() <= 255 else W / 65535.0
                joints |= set(np.unique(J[W > 1e-4]).tolist())
                maxinf = max(maxinf, int((W > 1e-4).sum(1).max()))
        nd = node_of_mesh.get(mi, {})
        out["meshes"][nd.get("name", m.get("name"))] = {"tris": tris, "joints_used": len(joints),
                                                         "max_influences": maxinf,
                                                         "hidden": "KHR_node_visibility" in nd.get("extensions", {})}
    for a in js.get("animations", []):
        tmax = 0.0
        for s in a["samplers"]:
            tmax = max(tmax, float(accessor(js, binc, s["input"]).max()))
        out["animations"][a["name"]] = round(tmax, 4)
    return out
