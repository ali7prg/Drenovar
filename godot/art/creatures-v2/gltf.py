"""Minimal, exact glTF 2.0 binary (GLB) writer for skinned, animated creatures.

Only core glTF 2.0 plus KHR_materials_emissive_strength (when an emissive
strength above 1 is used). No Draco/Meshopt/KTX2: the file opens in the stock
Three.js GLTFLoader and in the Godot 4.6 importer without decoders.
"""
import json
import struct

import numpy as np

FLOAT, UINT, USHORT, UBYTE = 5126, 5125, 5123, 5121
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963


class GLB:
    def __init__(self, generator="DRENOVAR creatures-v2 pipeline"):
        self.j = {"asset": {"version": "2.0", "generator": generator}, "scenes": [{"nodes": []}], "scene": 0,
                  "nodes": [], "meshes": [], "accessors": [], "bufferViews": [], "buffers": []}
        self.bin = bytearray()
        self.used_ext = set()

    # ---- raw data -------------------------------------------------------------------
    def _view(self, data, target=None, align=4):
        while len(self.bin) % align:
            self.bin += b"\x00"
        off = len(self.bin)
        self.bin += data
        view = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            view["target"] = target
        self.j["bufferViews"].append(view)
        return len(self.j["bufferViews"]) - 1

    def accessor(self, arr, ctype, atype, target=None, minmax=False, normalized=False):
        arr = np.ascontiguousarray(arr)
        view = self._view(arr.tobytes(), target)
        count = arr.shape[0]
        acc = {"bufferView": view, "componentType": ctype, "count": int(count), "type": atype}
        if normalized:
            acc["normalized"] = True
        if minmax:
            flat = arr.reshape(count, -1)
            acc["min"] = [float(x) for x in flat.min(0)]
            acc["max"] = [float(x) for x in flat.max(0)]
        self.j["accessors"].append(acc)
        return len(self.j["accessors"]) - 1

    def image(self, data, mime, name):
        if getattr(self, "external_images", None) is not None:
            ext = ".jpg" if mime == "image/jpeg" else ".png"
            uri = f"{self.texture_dir}/{name}{ext}" if self.texture_dir else f"{name}{ext}"
            self.external_images.append((uri, data))
            self.j.setdefault("images", []).append({"uri": uri, "name": name})
            return len(self.j["images"]) - 1
        view = self._view(data)
        self.j.setdefault("images", []).append({"bufferView": view, "mimeType": mime, "name": name})
        return len(self.j["images"]) - 1

    def external(self, texture_dir="textures"):
        """Switch to .gltf output: images become files next to the .gltf (no copy inside a GLB)."""
        self.external_images = []
        self.texture_dir = texture_dir
        return self

    def save_gltf(self, path):
        """Writes <path>.gltf + <name>.bin + images (returns total bytes written)."""
        import os
        base = os.path.splitext(path)[0]
        folder = os.path.dirname(path)
        if self.used_ext:
            self.j["extensionsUsed"] = sorted(self.used_ext)
        while len(self.bin) % 4:
            self.bin += b"\x00"
        bin_name = os.path.basename(base) + ".bin"
        self.j["buffers"] = [{"byteLength": len(self.bin), "uri": bin_name}]
        total = 0
        with open(os.path.join(folder, bin_name), "wb") as f:
            f.write(self.bin)
            total += len(self.bin)
        for uri, data in self.external_images:
            full = os.path.join(folder, uri)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(data)
            total += len(data)
        js = json.dumps(self.j, indent=1).encode("utf-8")
        with open(base + ".gltf", "wb") as f:
            f.write(js)
        return total + len(js)

    def texture(self, image_index, sampler=None):
        if "samplers" not in self.j:
            self.j["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}]
        self.j.setdefault("textures", []).append({"source": image_index, "sampler": 0 if sampler is None else sampler})
        return len(self.j["textures"]) - 1

    # ---- scene ----------------------------------------------------------------------
    def node(self, name, parent=None, translation=None, rotation=None, scale=None, **extra):
        n = {"name": name}
        if translation is not None and np.any(np.abs(translation) > 0):
            n["translation"] = [float(x) for x in translation]
        if rotation is not None and not np.allclose(rotation, [0, 0, 0, 1]):
            n["rotation"] = [float(x) for x in rotation]
        if scale is not None and not np.allclose(scale, 1):
            n["scale"] = [float(x) for x in scale]
        n.update(extra)
        self.j["nodes"].append(n)
        idx = len(self.j["nodes"]) - 1
        if parent is None:
            self.j["scenes"][0]["nodes"].append(idx)
        else:
            self.j["nodes"][parent].setdefault("children", []).append(idx)
        return idx

    def material(self, name, base_tex=None, normal_tex=None, orm_tex=None, emissive_tex=None, emissive=(0, 0, 0),
                 emissive_strength=1.0, roughness=1.0, metallic=0.0, base_color=(1, 1, 1, 1), extras=None,
                 normal_scale=1.0, double_sided=False):
        m = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": [float(x) for x in base_color],
                                                     "metallicFactor": float(metallic), "roughnessFactor": float(roughness)}}
        if base_tex is not None:
            m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": base_tex}
        if orm_tex is not None:
            m["pbrMetallicRoughness"]["metallicRoughnessTexture"] = {"index": orm_tex}
            m["occlusionTexture"] = {"index": orm_tex, "strength": 1.0}
        if normal_tex is not None:
            m["normalTexture"] = {"index": normal_tex, "scale": float(normal_scale)}
        if emissive_tex is not None:
            m["emissiveTexture"] = {"index": emissive_tex}
        if any(emissive):
            m["emissiveFactor"] = [float(x) for x in emissive]
        if emissive_strength != 1.0:
            m.setdefault("extensions", {})["KHR_materials_emissive_strength"] = {"emissiveStrength": float(emissive_strength)}
            self.used_ext.add("KHR_materials_emissive_strength")
        if double_sided:
            m["doubleSided"] = True
        if extras:
            m["extras"] = extras
        self.j.setdefault("materials", []).append(m)
        return len(self.j["materials"]) - 1

    def mesh(self, name, primitives, extras=None):
        """primitives: list of dicts with keys pos, nrm, tan(opt, Nx4), uv(opt), joints(opt Nx4), weights(opt), idx, material."""
        prims = []
        for p in primitives:
            attrs = {"POSITION": self.accessor(p["pos"].astype(np.float32), FLOAT, "VEC3", ARRAY_BUFFER, minmax=True),
                     "NORMAL": self.accessor(p["nrm"].astype(np.float32), FLOAT, "VEC3", ARRAY_BUFFER)}
            if p.get("tan") is not None:
                attrs["TANGENT"] = self.accessor(p["tan"].astype(np.float32), FLOAT, "VEC4", ARRAY_BUFFER)
            if p.get("uv") is not None:
                attrs["TEXCOORD_0"] = self.accessor(p["uv"].astype(np.float32), FLOAT, "VEC2", ARRAY_BUFFER)
            if p.get("joints") is not None:
                j = p["joints"]
                ct = UBYTE if j.max() < 256 else USHORT
                attrs["JOINTS_0"] = self.accessor(j.astype(np.uint8 if ct == UBYTE else np.uint16), ct, "VEC4", ARRAY_BUFFER)
                attrs["WEIGHTS_0"] = self.accessor(p["weights"].astype(np.float32), FLOAT, "VEC4", ARRAY_BUFFER)
            idx = p["idx"].astype(np.uint32).ravel()
            ict = UINT if len(p["pos"]) > 65535 else USHORT
            ia = self.accessor(idx.astype(np.uint32 if ict == UINT else np.uint16), ict, "SCALAR", ELEMENT_ARRAY_BUFFER)
            prim = {"attributes": attrs, "indices": ia, "mode": 4}
            if p.get("material") is not None:
                prim["material"] = p["material"]
            prims.append(prim)
        m = {"name": name, "primitives": prims}
        if extras:
            m["extras"] = extras
        self.j["meshes"].append(m)
        return len(self.j["meshes"]) - 1

    def skin(self, name, joints, inverse_binds, skeleton=None):
        acc = self.accessor(inverse_binds.astype(np.float32).reshape(-1, 16), FLOAT, "MAT4")
        s = {"name": name, "joints": list(map(int, joints)), "inverseBindMatrices": acc}
        if skeleton is not None:
            s["skeleton"] = int(skeleton)
        self.j.setdefault("skins", []).append(s)
        return len(self.j["skins"]) - 1

    def animation(self, name, channels, extras=None):
        """channels: list of (node, path, times(N,), values(N,k))."""
        samplers, chans = [], []
        cache = {}
        for node, path, times, values in channels:
            tkey = (len(times), float(times[-1]))
            if tkey not in cache:
                cache[tkey] = self.accessor(np.asarray(times, np.float32), FLOAT, "SCALAR", minmax=True)
            atype = {3: "VEC3", 4: "VEC4"}[values.shape[1]]
            out = self.accessor(np.asarray(values, np.float32), FLOAT, atype)
            samplers.append({"input": cache[tkey], "output": out, "interpolation": "LINEAR"})
            chans.append({"sampler": len(samplers) - 1, "target": {"node": int(node), "path": path}})
        a = {"name": name, "samplers": samplers, "channels": chans}
        if extras:
            a["extras"] = extras
        self.j.setdefault("animations", []).append(a)
        return len(self.j["animations"]) - 1

    def save(self, path):
        if self.used_ext:
            self.j["extensionsUsed"] = sorted(self.used_ext)
        while len(self.bin) % 4:
            self.bin += b"\x00"
        self.j["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.j, separators=(",", ":")).encode("utf-8")
        while len(js) % 4:
            js += b" "
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total))
            f.write(struct.pack("<II", len(js), 0x4E4F534A))
            f.write(js)
            f.write(struct.pack("<II", len(self.bin), 0x004E4942))
            f.write(self.bin)
        return total
