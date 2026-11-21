#!/usr/bin/env python3
"""Static audit of the existing ENG warrior GLB files (no external deps beyond numpy).

usage: python3 glb_audit.py <assets_dir> <out.json>
Reads every ENG-*-lod1/lod2 GLB, reports geometry, materials, textures, skin, clips and
per-mesh bone binding (which joints carry the weights of every mesh part).
"""
import json, os, struct, sys, glob, hashlib
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path):
    b = open(path, "rb").read()
    assert b[:4] == b"glTF"
    jl = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jl])
    off = 20 + jl
    binc = b""
    if off < len(b):
        bl = struct.unpack("<I", b[off:off + 4])[0]
        binc = b[off + 8:off + 8 + bl]
    return j, binc, len(b), jl


def accessor(j, binc, idx):
    a = j["accessors"][idx]
    bv = j["bufferViews"][a["bufferView"]]
    dt = CT[a["componentType"]]
    n = NC[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0)
    itemsize = np.dtype(dt).itemsize * n
    if stride and stride != itemsize:
        raw = np.frombuffer(binc, dtype=np.uint8, count=stride * (a["count"] - 1) + itemsize, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(a["count"], itemsize), strides=(stride, 1))
        arr = np.frombuffer(rows.copy().tobytes(), dtype=dt).reshape(a["count"], n)
    else:
        arr = np.frombuffer(binc, dtype=dt, count=a["count"] * n, offset=start).reshape(a["count"], n)
    if a.get("normalized"):
        if dt == np.uint8:
            arr = arr.astype(np.float32) / 255.0
        elif dt == np.uint16:
            arr = arr.astype(np.float32) / 65535.0
    return arr


def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", w, h
            if m == 0xD8 or m == 0x01 or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
        return "jpeg", None, None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", None, None
    return "unknown", None, None


def audit(path):
    j, binc, size, jl = read_glb(path)
    d = os.path.dirname(path)
    nodes = j.get("nodes", [])
    out = {"file": os.path.basename(path), "bytes": size, "json_bytes": jl, "bin_bytes": len(binc),
           "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
           "generator": j.get("asset", {}).get("generator"), "extras": j.get("extras"),
           "extensionsUsed": j.get("extensionsUsed", []), "node_count": len(nodes)}
    scene = j["scenes"][j.get("scene", 0)]
    out["scene_roots"] = [nodes[i].get("name") for i in scene["nodes"]]
    # skins
    skins = []
    for s in j.get("skins", []):
        names = [nodes[i].get("name") for i in s["joints"]]
        skins.append({"name": s.get("name"), "joint_count": len(names), "joints": names,
                      "skeleton_root": nodes[s["skeleton"]].get("name") if "skeleton" in s else None})
    out["skins"] = skins
    # parents
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    # rest positions of joints (global) assuming rest = node TRS
    def local(i):
        n = nodes[i]
        m = np.eye(4)
        if "matrix" in n:
            return np.array(n["matrix"]).reshape(4, 4).T
        t = n.get("translation", [0, 0, 0]); r = n.get("rotation", [0, 0, 0, 1]); s = n.get("scale", [1, 1, 1])
        x, y, z, w = r
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        m[:3, :3] = R * np.array(s)
        m[:3, 3] = t
        return m
    gcache = {}
    def glob_m(i):
        if i in gcache:
            return gcache[i]
        m = local(i)
        if i in parent:
            m = glob_m(parent[i]) @ m
        gcache[i] = m
        return m
    rest = {}
    for i, n in enumerate(nodes):
        if "mesh" not in n:
            rest[n.get("name")] = [round(float(v), 4) for v in glob_m(i)[:3, 3]]
    out["rest_node_positions"] = rest
    # materials
    mats = []
    for m in j.get("materials", []):
        pbr = m.get("pbrMetallicRoughness", {})
        tex = {}
        for key, src in (("baseColor", pbr.get("baseColorTexture")), ("metallicRoughness", pbr.get("metallicRoughnessTexture")),
                         ("normal", m.get("normalTexture")), ("occlusion", m.get("occlusionTexture")), ("emissive", m.get("emissiveTexture"))):
            if src is not None:
                tex[key] = j["textures"][src["index"]]["source"]
        mats.append({"name": m.get("name"), "alphaMode": m.get("alphaMode", "OPAQUE"), "doubleSided": m.get("doubleSided", False),
                     "metallic": pbr.get("metallicFactor", 1), "roughness": pbr.get("roughnessFactor", 1),
                     "baseColorFactor": pbr.get("baseColorFactor"), "textures": tex,
                     "normal_scale": (m.get("normalTexture") or {}).get("scale"), "extensions": list(m.get("extensions", {}).keys())})
    out["materials"] = mats
    # images
    imgs = []
    for k, im in enumerate(j.get("images", [])):
        if "uri" in im and not im["uri"].startswith("data:"):
            p = os.path.join(d, im["uri"])
            data = open(p, "rb").read() if os.path.exists(p) else b""
            kind, w, h = image_size(data)
            imgs.append({"index": k, "storage": "external", "uri": im["uri"], "exists": os.path.exists(p), "bytes": len(data), "format": kind, "width": w, "height": h})
        else:
            bv = j["bufferViews"][im["bufferView"]]
            data = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
            kind, w, h = image_size(data)
            imgs.append({"index": k, "storage": "embedded", "name": im.get("name"), "mimeType": im.get("mimeType"), "bytes": len(data), "format": kind, "width": w, "height": h})
    out["images"] = imgs
    # meshes
    mesh_rows = []
    tv = tt = 0
    used_mats = set()
    for i, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        mesh = j["meshes"][n["mesh"]]
        skin = j["skins"][n["skin"]] if "skin" in n else None
        joint_names = [nodes[x].get("name") for x in skin["joints"]] if skin else []
        row = {"node": n.get("name"), "mesh": mesh.get("name"), "skinned": skin is not None, "primitives": []}
        for p in mesh["primitives"]:
            attrs = p["attributes"]
            vc = j["accessors"][attrs["POSITION"]]["count"]
            if "indices" in p:
                ic = j["accessors"][p["indices"]]["count"]
            else:
                ic = vc
            mode = p.get("mode", 4)
            tris = ic // 3 if mode == 4 else 0
            tv += vc; tt += tris
            used_mats.add(p.get("material"))
            prim = {"material": j["materials"][p["material"]]["name"] if "material" in p else None, "vertices": vc,
                    "triangles": tris, "attributes": sorted(attrs.keys()), "targets": len(p.get("targets", []))}
            pos = accessor(j, binc, attrs["POSITION"])
            prim["bbox_min"] = [round(float(x), 4) for x in pos.min(0)]
            prim["bbox_max"] = [round(float(x), 4) for x in pos.max(0)]
            if skin is not None and "JOINTS_0" in attrs:
                jo = accessor(j, binc, attrs["JOINTS_0"]).astype(int)
                we = accessor(j, binc, attrs["WEIGHTS_0"]).astype(np.float64)
                infl = (we > 1e-4).sum(1)
                prim["max_influences"] = int(infl.max())
                acc = {}
                for k2 in range(4):
                    for jj, ww in zip(jo[:, k2], we[:, k2]):
                        if ww > 1e-4:
                            acc[jj] = acc.get(jj, 0.0) + ww
                tot = sum(acc.values())
                prim["bone_weight_share"] = {joint_names[k3]: round(v / tot, 4) for k3, v in sorted(acc.items(), key=lambda kv: -kv[1]) if v / tot >= 0.005}
                # rigid check: vertices whose dominant weight >= 0.999
                prim["rigid_vertex_share"] = round(float((we.max(1) >= 0.999).mean()), 4)
            row["primitives"].append(prim)
        mesh_rows.append(row)
    out["meshes"] = mesh_rows
    out["mesh_nodes"] = len(mesh_rows)
    out["primitive_count"] = sum(len(r["primitives"]) for r in mesh_rows)
    out["vertices"] = tv
    out["triangles"] = tt
    out["materials_used"] = len([m for m in used_mats if m is not None])
    # animations
    anims = []
    for a in j.get("animations", []):
        tmax = 0.0; keys = 0; interp = set(); paths = {}
        hips_t = None
        for c in a["channels"]:
            smp = a["samplers"][c["sampler"]]
            inp = accessor(j, binc, smp["input"])
            tmax = max(tmax, float(inp.max()))
            keys = max(keys, len(inp))
            interp.add(smp.get("interpolation", "LINEAR"))
            tgt = nodes[c["target"]["node"]].get("name")
            paths.setdefault(c["target"]["path"], []).append(tgt)
            if c["target"]["path"] == "translation" and tgt in ("Hips", "HorseRoot"):
                outp = accessor(j, binc, smp["output"])
                hips_t = hips_t or {}
                hips_t[tgt] = {"min": [round(float(x), 4) for x in outp.min(0)], "max": [round(float(x), 4) for x in outp.max(0)],
                               "first": [round(float(x), 4) for x in outp[0]], "last": [round(float(x), 4) for x in outp[-1]]}
        anims.append({"name": a.get("name"), "duration": round(tmax, 4), "keys": keys, "channels": len(a["channels"]),
                      "interpolation": sorted(interp), "translation_targets": sorted(set(paths.get("translation", []))),
                      "scale_targets": sorted(set(paths.get("scale", []))), "root_translation": hips_t})
    out["animations"] = anims
    return out


def main():
    src = sys.argv[1]
    files = sorted(glob.glob(os.path.join(src, "ENG-*-lod[12].glb")))
    res = [audit(f) for f in files]
    json.dump(res, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
    for r in res:
        print(f'{r["file"]:42s} {r["bytes"]/1e6:6.2f}MB v={r["vertices"]:6d} t={r["triangles"]:6d} meshes={r["mesh_nodes"]:2d} prims={r["primitive_count"]:2d} mats={len(r["materials"]):2d}/{r["materials_used"]:2d} imgs={len(r["images"]):2d} joints={[s["joint_count"] for s in r["skins"]]} clips={[a["name"]+":"+str(a["duration"]) for a in r["animations"]]}')


if __name__ == "__main__":
    main()
