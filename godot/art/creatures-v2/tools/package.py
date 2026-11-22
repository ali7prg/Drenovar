"""Delivery packaging: per-species independent ZIPs (each <= 28 000 000 bytes) plus a manifest with
relative paths, sizes and SHA-256 of every file and every archive.
Usage: python3 -I package.py <work-root> <media-root> <dcc-root> <reports-dir> <source-dir> <out-dir>
"""
import hashlib
import json
import os
import sys
import zipfile

LIMIT = 28_000_000
work, media, dcc, reports, source, out = sys.argv[1:7]
os.makedirs(out, exist_ok=True)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


manifest = {"package": "DRENOVAR creatures-v2", "limit_bytes_per_archive": LIMIT, "archives": [], "files": []}


def pack(name, entries):
    """entries: list of (source path, path inside zip). Splits into parts when needed."""
    parts, cur, size = [], [], 0
    for src, arc in entries:
        s = os.path.getsize(src)
        if s > LIMIT:
            raise SystemExit(f"{src} alone exceeds the limit ({s} bytes)")
        if cur and size + s > LIMIT - 200_000:
            parts.append(cur)
            cur, size = [], 0
        cur.append((src, arc))
        size += s
    if cur:
        parts.append(cur)
    for k, part in enumerate(parts):
        zname = f"{name}.zip" if len(parts) == 1 else f"{name}_part{k + 1}.zip"
        zpath = os.path.join(out, zname)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for src, arc in part:
                z.write(src, arc)
                manifest["files"].append({"archive": zname, "path": arc, "bytes": os.path.getsize(src), "sha256": sha(src)})
        b = os.path.getsize(zpath)
        assert b <= LIMIT, (zname, b)
        manifest["archives"].append({"archive": zname, "bytes": b, "sha256": sha(zpath), "files": len(part)})
        print(f"{zname}: {b / 1e6:.2f} MB, {len(part)} files")


def files_in(folder, prefix, pred=lambda f: True):
    out_list = []
    for root, _d, fs in os.walk(folder):
        for f in sorted(fs):
            if pred(f):
                full = os.path.join(root, f)
                out_list.append((full, os.path.join(prefix, os.path.relpath(full, folder))))
    return out_list


for sid in ("velkor", "tenerys", "kamneklyk", "dragor"):
    o = os.path.join(work, sid, "out")
    pack(f"{sid}_1_model_lod0", [(os.path.join(o, f"{sid}_lod0.glb"), f"{sid}/model/{sid}_lod0.glb")])
    pack(f"{sid}_2_model_lod1_lod2", [(os.path.join(o, f"{sid}_lod1.glb"), f"{sid}/model/{sid}_lod1.glb"),
                                      (os.path.join(o, f"{sid}_lod2.glb"), f"{sid}/model/{sid}_lod2.glb"),
                                      (os.path.join(o, "clip_manifest.json"), f"{sid}/animations/clip_manifest.json"),
                                      (os.path.join(o, "metadata.json"), f"{sid}/metadata/metadata.json")])
    pack(f"{sid}_3_web_levels", [(os.path.join(o, f"{sid.upper()}_L{l}_RIGGED_ANIMATED.glb"),
                                  f"{sid}/model/web/{sid.upper()}_L{l}_RIGGED_ANIMATED.glb") for l in (1, 2, 3)])
    # editable source: .blend + .fbx with their LOD0 PBR maps (BaseColor/Normal/ORM/Emissive, 2K masters),
    # plus the level variant masks of every LOD (LOD1/LOD2 maps ship in the game repository)
    src = files_in(os.path.join(dcc, sid), f"{sid}/source")
    for lod in (0, 1, 2):
        src += files_in(os.path.join(work, sid, f"lod{lod}"), f"{sid}/textures/lod{lod}",
                        lambda f: f.endswith("_variant.png"))
    pack(f"{sid}_4_source_blend_fbx_textures", src)
# previews of all four in one archive: turntables, clip videos and sheets, level portraits, in-game hunts
previews = []
for sid in ("velkor", "tenerys", "kamneklyk", "dragor"):
    previews += files_in(os.path.join(media, sid), f"previews/{sid}",
                         lambda f: f.endswith((".mp4", ".webp", ".jpg")) and not f.startswith(("turn_", "clip_", "portrait_")))
previews += files_in(os.path.join(media, "ingame"), "previews/ingame", lambda f: f.endswith((".mp4", ".jpg")))
pack("creatures-v2_previews", previews)
pack("creatures-v2_pipeline_source", files_in(source, "pipeline", lambda f: not f.endswith(".pyc")))
pack("creatures-v2_reports", files_in(reports, "reports"))
with open(os.path.join(out, "MANIFEST.json"), "w") as f:
    json.dump(manifest, f, indent=1, ensure_ascii=False)
print("archives", len(manifest["archives"]), "files", len(manifest["files"]))
