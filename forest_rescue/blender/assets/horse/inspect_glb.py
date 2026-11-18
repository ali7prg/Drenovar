"""Summarise a GLB (no Blender needed): meshes/tris, skins, materials, images, animation lengths.

    python3 inspect_glb.py godot/project/assets/forest_rescue/horse/lf_horse_origin.glb [--json out.json]
"""
import json
import struct
import sys


def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF", "not a GLB"
    off = 12
    js, binchunk = None, None
    while off < length:
        clen, ctype = struct.unpack_from("<I4s", data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(chunk)
        elif ctype == b"BIN\x00":
            binchunk = chunk
        off += 8 + clen
    return js, binchunk


def accessor_minmax(js, idx):
    a = js["accessors"][idx]
    return a.get("min"), a.get("max"), a["count"]


def main():
    path = sys.argv[1]
    js, _ = read_glb(path)
    out = {"file": path}
    meshes = []
    for m in js.get("meshes", []):
        tris = 0
        for p in m["primitives"]:
            if "indices" in p:
                tris += js["accessors"][p["indices"]]["count"] // 3
        meshes.append({"name": m["name"], "primitives": len(m["primitives"]), "tris": tris})
    out["meshes"] = meshes
    out["nodes_with_skin"] = [n["name"] for n in js.get("nodes", []) if "skin" in n]
    out["skins"] = [{"joints": len(s["joints"])} for s in js.get("skins", [])]
    out["materials"] = [{"name": m.get("name"), "alphaMode": m.get("alphaMode", "OPAQUE"),
                         "alphaCutoff": m.get("alphaCutoff"), "doubleSided": m.get("doubleSided", False),
                         "extensions": sorted(m.get("extensions", {}).keys())}
                        for m in js.get("materials", [])]
    out["images"] = [{"name": i.get("name"), "mimeType": i.get("mimeType")} for i in js.get("images", [])]
    anims = []
    for a in js.get("animations", []):
        tmax = 0.0
        tmin = 1e9
        n_keys = 0
        for s in a["samplers"]:
            mn, mx, cnt = accessor_minmax(js, s["input"])
            tmax = max(tmax, mx[0])
            tmin = min(tmin, mn[0])
            n_keys = max(n_keys, cnt)
        interp = sorted({s.get("interpolation", "LINEAR") for s in a["samplers"]})
        anims.append({"name": a["name"], "start": round(tmin, 4), "duration": round(tmax, 4),
                      "channels": len(a["channels"]), "keys": n_keys, "interpolation": interp})
    out["animations"] = anims
    txt = json.dumps(out, indent=1, ensure_ascii=False)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            f.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
