"""Minimal GLB reader/patcher (no bpy): stats, exact clip durations, animation extras."""
import json
import struct

import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read(path):
    b = open(path, "rb").read()
    magic, ver, length = struct.unpack_from("<III", b, 0)
    assert magic == 0x46546C67
    off = 12
    js, binc = None, b""
    while off < len(b):
        clen, ctype = struct.unpack_from("<II", b, off)
        data = b[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            binc = bytearray(data)
        off += 8 + clen
    return js, binc


def write(path, js, binc):
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    bb = bytes(binc) + b"\0" * ((4 - len(binc) % 4) % 4)
    total = 12 + 8 + len(jb) + 8 + len(bb)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(jb), 0x4E4F534A))
        f.write(jb)
        f.write(struct.pack("<II", len(bb), 0x004E4942))
        f.write(bb)


def accessor(js, binc, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    n = a["count"] * NC[a["type"]]
    arr = np.frombuffer(bytes(binc[off: off + n * np.dtype(CT[a["componentType"]]).itemsize]),
                        dtype=CT[a["componentType"]]).copy()
    return arr, off


def set_accessor(js, binc, i, arr):
    a = js["accessors"][i]
    _, off = accessor(js, binc, i)
    raw = arr.astype(CT[a["componentType"]]).tobytes()
    binc[off: off + len(raw)] = raw
    if "min" in a:
        a["min"] = [float(arr.min())]
        a["max"] = [float(arr.max())]


def fix_durations(js, binc, durations, markers=None):
    """Scale each animation's time inputs so it lasts exactly durations[name]; add markers extras."""
    report = {}
    for anim in js.get("animations", []):
        name = anim["name"]
        inputs = sorted({s["input"] for s in anim["samplers"]})
        tmax = max(float(accessor(js, binc, i)[0].max()) for i in inputs)
        D = durations.get(name)
        if D is not None and tmax > 0 and abs(tmax - D) > 1e-4:
            for i in inputs:
                arr, _ = accessor(js, binc, i)
                set_accessor(js, binc, i, arr * (D / tmax))
        report[name] = {"before": round(tmax, 5), "after": D if D is not None else tmax}
        if markers and name in markers:
            anim.setdefault("extras", {})["markers"] = markers[name]
            anim["extras"]["duration_s"] = D
    return report


def stats(js, binc):
    out = {"meshes": {}, "animations": {}, "skins": [], "materials": [m.get("name") for m in js.get("materials", [])],
           "images": [(im.get("name"), im.get("mimeType")) for im in js.get("images", [])]}
    for n in js.get("nodes", []):
        if "mesh" in n:
            m = js["meshes"][n["mesh"]]
            tris = 0
            for p in m["primitives"]:
                if "indices" in p:
                    tris += js["accessors"][p["indices"]]["count"] // 3
            out["meshes"][n.get("name")] = tris
    for s in js.get("skins", []):
        out["skins"].append(len(s["joints"]))
    for a in js.get("animations", []):
        tmax = max(float(accessor(js, binc, s["input"])[0].max()) for s in a["samplers"])
        out["animations"][a["name"]] = round(tmax, 4)
    return out
