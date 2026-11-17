"""Stage 3: skin weights, glTF materials and GLB export (+ clip manifest)."""
import io
import json
import os

import numpy as np
from PIL import Image

from gltf import GLB


def mesh_adjacency(idx, n):
    from scipy.sparse import coo_matrix
    rows = np.concatenate([idx[:, 0], idx[:, 1], idx[:, 2], idx[:, 1], idx[:, 2], idx[:, 0]])
    cols = np.concatenate([idx[:, 1], idx[:, 2], idx[:, 0], idx[:, 0], idx[:, 1], idx[:, 2]])
    A = coo_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel()
    return A, deg


def weld_groups(mesh):
    """Render vertices split at UV seams share a source vertex: average their weights so seams never tear."""
    return mesh["src"], mesh["part"]


def skin_weights(sp, mesh, joints, tau=0.045, smooth=3):
    """(V,4) joint indices and weights. Skinned parts: softmin ownership of the sculpt primitives by bone,
    smoothed over the surface; rigid parts: one bone."""
    sk, parts = sp.build_cached()
    jidx = {n: i for i, n in enumerate(joints)}
    V = len(mesh["pos"])
    Wfull = np.zeros((V, len(joints)), np.float32)
    for part in parts:
        sel = np.nonzero(mesh["part"] == part["index"])[0]
        if len(sel) == 0:
            continue
        if part["rigid"] is not None:
            Wfull[sel, jidx[part["rigid"]]] = 1.0
            continue
        P = mesh["pos"][sel]
        _d, D = part["part"].eval(P, keep=True, displace=False)
        prims = part["part"].prims
        valid = np.array([not p.neg for p in prims])
        D = np.where(valid[None, :], D, 1e3)
        dmin = D.min(1, keepdims=True)
        infl = np.exp(-(D - dmin) / tau)
        for j, p in enumerate(prims):
            if p.neg:
                continue
            Wfull[sel, jidx[p.bone]] += infl[:, j]
        Wfull[sel] /= np.maximum(Wfull[sel].sum(1, keepdims=True), 1e-9)
        # smooth over the surface (render vertices at the same source position share weights)
        A, deg = mesh_adjacency(mesh["idx"], V)
        sub = Wfull.copy()
        rigid_mask = np.zeros(V, bool)
        for p2 in parts:
            if p2["rigid"] is not None:
                rigid_mask |= mesh["part"] == p2["index"]
        for _ in range(smooth):
            avg = (A @ sub) / np.maximum(deg, 1)[:, None]
            sub = np.where(rigid_mask[:, None], sub, 0.5 * sub + 0.5 * avg)
        Wfull[sel] = sub[sel]
    # merge split copies of a source vertex (UV seams) so both sides move identically
    key = mesh["part"].astype(np.int64) * 10_000_000 + mesh["src"].astype(np.int64)
    _u, inv = np.unique(key, return_inverse=True)
    acc = np.zeros((len(_u), len(joints)), np.float32)
    np.add.at(acc, inv, Wfull)
    cnt = np.bincount(inv).astype(np.float32)
    Wfull = acc[inv] / cnt[inv][:, None]
    order = np.argsort(-Wfull, axis=1)[:, :4]
    w4 = np.take_along_axis(Wfull, order, 1)
    w4[w4 < 0.01] = 0.0
    w4 /= np.maximum(w4.sum(1, keepdims=True), 1e-9)
    order = np.where(w4 > 0, order, 0)
    return order.astype(np.uint8 if len(joints) < 256 else np.uint16), w4.astype(np.float32)


def png_bytes(path, max_size=None, mode=None, fmt="PNG", quality=92):
    im = Image.open(path)
    if mode:
        im = im.convert(mode)
    if max_size and im.size[0] > max_size:
        im = im.resize((max_size, max_size), Image.LANCZOS)
    b = io.BytesIO()
    if fmt == "JPEG":
        im.convert("RGB").save(b, "JPEG", quality=quality, optimize=True, progressive=False, subsampling=0)
        return b.getvalue(), "image/jpeg"
    im.save(b, "PNG", optimize=True)
    return b.getvalue(), "image/png"


def unit_frames(nrm, tan):
    """Unit normals; unit tangents orthogonal to them (degenerate UV corners get a stable fallback)."""
    n = nrm.astype(np.float64)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    bad_n = ~np.isfinite(n).all(1) | (np.linalg.norm(n, axis=1) < 0.5)
    n[bad_n] = (0.0, 1.0, 0.0)
    t = tan[:, :3].astype(np.float64)
    t = t - np.sum(t * n, 1, keepdims=True) * n
    ln = np.linalg.norm(t, axis=1)
    fallback = np.cross(n, np.where(np.abs(n[:, 0:1]) < 0.9, [[1.0, 0, 0]], [[0, 0, 1.0]]))
    t = np.where((ln < 1e-6)[:, None], fallback, t)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    w = np.where(tan[:, 3] < 0, -1.0, 1.0)
    return n.astype(np.float32), np.concatenate([t, w[:, None]], 1).astype(np.float32)


def skeleton_nodes(g, sk, root_name="CreatureRoot"):
    root = g.node(root_name)
    node_of = {}
    for b in sk.bones:
        parent = node_of[b.parent] if b.parent else root
        node_of[b.name] = g.node(b.name, parent, translation=sk.rest_offset(b.name))
    for name, bone, pos in sk.sockets:
        g.node(name, node_of[bone], translation=pos - sk.bone(bone).head, extras={"socket": True})
    return root, node_of


def extras_level_overlays(extras):
    return bool(extras and extras.get("web_canonical"))


def write(path, sp, sk, lod_sets, clips, level=1, generator="DRENOVAR creatures-v2", texture_format="PNG",
          include_overlays=True, extras=None, gltf_external=False):
    """lod_sets: list of (lod, {group: dict(mesh=..., tex=dir, joints/weights)}). Writes a GLB, or with
    gltf_external a .gltf + .bin + textures/ (BaseColor and ORM as JPEG, Normal/Emissive as PNG)."""
    g = GLB(generator)
    if gltf_external:
        g.external(f"{sp.ID}_textures")
        texture_format = "JPEG"
    root, node_of = skeleton_nodes(g, sk)
    joints = [b.name for b in sk.bones]
    inv = np.zeros((len(joints), 4, 4), np.float32)
    for i, b in enumerate(sk.bones):
        m = np.eye(4, dtype=np.float32)
        m[:3, 3] = -b.head
        inv[i] = m.T  # glTF matrices are column-major
    skin = g.skin("CreatureSkin", [node_of[n] for n in joints], inv, skeleton=node_of[joints[0]])
    for lod, groups in lod_sets:
        for group, data in groups.items():
            mesh = data["mesh"]
            tex = data["tex"]
            # textures (level-baked base colour / emissive when the file is a per-level export)
            base_path = data.get("base_override") or os.path.join(tex, f"{group}_basecolor.png")
            b_bytes, b_mime = png_bytes(base_path, fmt=texture_format if texture_format == "JPEG" else "PNG")
            ti_base = g.texture(g.image(b_bytes, b_mime, f"{sp.ID}_LOD{lod}_{group}_BaseColor"))
            n_bytes, n_mime = png_bytes(os.path.join(tex, f"{group}_normal.png"))
            ti_n = g.texture(g.image(n_bytes, n_mime, f"{sp.ID}_LOD{lod}_{group}_Normal"))
            o_bytes, o_mime = png_bytes(os.path.join(tex, f"{group}_orm.png"), fmt="JPEG" if gltf_external else "PNG",
                                        quality=94)
            ti_o = g.texture(g.image(o_bytes, o_mime, f"{sp.ID}_LOD{lod}_{group}_ORM"))
            ti_e = None
            em_path = data.get("emissive_override") or os.path.join(tex, f"{group}_emissive.png")
            if os.path.exists(em_path):
                e_bytes, e_mime = png_bytes(em_path)
                ti_e = g.texture(g.image(e_bytes, e_mime, f"{sp.ID}_LOD{lod}_{group}_Emissive"))
            mat_name = f"M_{sp.ID.capitalize()}_{sp.MATERIAL_NAMES[group]}_LOD{lod}"
            strength = level_params(sp, level, group).get("emission_strength", 1.0)
            mi = g.material(mat_name, base_tex=ti_base, normal_tex=ti_n, orm_tex=ti_o, emissive_tex=ti_e,
                            emissive=(1, 1, 1) if ti_e is not None else (0, 0, 0), emissive_strength=strength,
                            extras={"species": sp.ID, "group": group, "lod": lod, "level": level,
                                    "variant_mask": f"{group}_variant.png", "material_version": "creatures-v2"})
            # split by visibility tier: base / level II+ / level III overlays
            vis = data.get("tier")
            tiers = sorted(set(vis.tolist())) if vis is not None else [1]
            for tier in tiers:
                if tier > level and not include_overlays:
                    continue
                if tier > 1 and not include_overlays and not extras_level_overlays(extras):
                    continue
                if vis is not None:
                    fsel = np.all(vis[mesh["idx"]] == tier, axis=1)
                else:
                    fsel = np.ones(len(mesh["idx"]), bool)
                if not fsel.any():
                    continue
                faces = mesh["idx"][fsel]
                used = np.unique(faces)
                remap = -np.ones(len(mesh["pos"]), np.int64)
                remap[used] = np.arange(len(used))
                nrm, tan = unit_frames(mesh["nrm"][used], mesh["tan"][used])
                prim = {"pos": mesh["pos"][used], "nrm": nrm, "tan": tan,
                        "uv": mesh["uv"][used], "joints": data["joints"][used], "weights": data["weights"][used],
                        "idx": remap[faces], "material": mi}
                suffix = "" if tier == 1 else ("_VARIANT_L2" if tier == 2 else "_VARIANT_L3")
                name = f"{sp.ID.upper()}_{sp.MATERIAL_NAMES[group]}_LOD{lod}{suffix}"
                mx = g.mesh(name, [prim], extras={"lod": lod, "tier": int(tier)})
                # skinned meshes are scene roots (their node transform is ignored by glTF skinning)
                g.node(name, None, mesh=mx, skin=skin, extras={"lod": lod, "min_level": int(tier)})
    for clip in clips:
        chans = []
        for bone, target, times, values in clip["channels"]:
            chans.append((node_of[bone], target, times, values))
        g.animation(clip["name"], chans, extras={k: v for k, v in clip.items() if k not in ("channels",)})
    g.j["scenes"][0]["extras"] = dict(extras or {}, species=sp.ID, level=level, units="m", up="+Y",
                                      forward="+X", pipeline="godot/art/creatures-v2")
    return g.save_gltf(path) if gltf_external else g.save(path)


# ------------------------------------------------------------------ orchestration
def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def level_params(sp, level, group):
    """LEVELS[level] with that level's per-group overrides ("groups": {group: {...}}) applied."""
    prm = {k: v for k, v in sp.LEVELS[level].items() if k != "groups"}
    prm.update(sp.LEVELS[level].get("groups", {}).get(group, {}))
    return prm


def level_textures(sp, tex_dir, group, level, out_dir):
    """Bakes the level look (same formula as the Godot creature shader) into BaseColor/Emissive PNGs."""
    from texturing import srgb_to_linear, linear_to_srgb, hexcol
    prm = level_params(sp, level, group)
    base = np.asarray(Image.open(os.path.join(tex_dir, f"{group}_basecolor.png")).convert("RGB"), np.float32) / 255
    vpath = os.path.join(tex_dir, f"{group}_variant.png")
    if not os.path.exists(vpath):
        return None, None
    var = Image.open(vpath).convert("RGBA").resize(base.shape[1::-1], Image.BILINEAR)
    var = np.asarray(var, np.float32) / 255
    lin = srgb_to_linear(base)
    for ch, key in ((0, "tint_r"), (1, "tint_g"), (2, "tint_b")):
        t = prm.get(key)
        if t is None or t[3] <= 0:
            continue
        tint = srgb_to_linear(np.array(t[:3], np.float32))
        target = tint * np.clip(luma(lin) / 0.18, 0.35, 1.6)[..., None]
        lin = lin + (target - lin) * (var[..., ch] * t[3])[..., None]
    os.makedirs(out_dir, exist_ok=True)
    bpath = os.path.join(out_dir, f"{group}_basecolor_L{level}.png")
    Image.fromarray((linear_to_srgb(lin) * 255 + 0.5).astype(np.uint8)).save(bpath, optimize=True)
    epath = None
    em_src = os.path.join(tex_dir, f"{group}_emissive.png")
    if os.path.exists(em_src):
        em = srgb_to_linear(np.asarray(Image.open(em_src).convert("RGB"), np.float32) / 255)
        var_e = np.asarray(Image.open(vpath).convert("RGBA").resize(em.shape[1::-1], Image.BILINEAR), np.float32) / 255
        col = srgb_to_linear(hexcol(sp.EMISSION_COLOR))
        # glTF multiplies the whole emissive texture by emissiveStrength; the shader adds the mask glow after the
        # strength, so the mask term is divided by it here: tex * s == emissive * s + colour * masks (as in Godot).
        s = max(prm.get("emission_strength", 1.0), 1e-6)
        em = em + col * (var_e[..., 0] * prm.get("emit_r", 0.0) + var_e[..., 1] * prm.get("emit_g", 0.0) +
                         var_e[..., 2] * prm.get("emit_b", 0.0))[..., None] / s
        epath = os.path.join(out_dir, f"{group}_emissive_L{level}.png")
        Image.fromarray((linear_to_srgb(np.clip(em, 0, 1)) * 255 + 0.5).astype(np.uint8)).save(epath, optimize=True)
    return bpath, epath


def load_lod(sp, work, lod, joints):
    d = os.path.join(work, f"lod{lod}")
    sk, parts = sp.build_cached()
    tier_of = {p["index"]: p.get("level", 1) for p in parts}
    groups = {}
    for group in sp.CLASSES:
        mp = os.path.join(d, f"{group}_mesh.npz")
        if not os.path.exists(mp):
            continue
        mesh = dict(np.load(mp))
        cache = os.path.join(d, f"{group}_skin.npz")
        if os.path.exists(cache):
            z = np.load(cache)
            jw, ww = z["j"], z["w"]
        else:
            jw, ww = skin_weights(sp, mesh, joints)
            np.savez_compressed(cache, j=jw, w=ww)
        tier = np.array([tier_of[int(p)] for p in mesh["part"]], np.int32)
        groups[group] = {"mesh": mesh, "tex": d, "joints": jw, "weights": ww, "tier": tier}
    return groups


def clip_manifest(sp, clips):
    rows = {}
    for c in clips:
        short = c["name"].split("__", 1)[1]
        row = {"name": c["name"], "frames": c["frames"], "fps": c["fps"], "length_s": round(c["length"], 4),
               "loop": c["loop"], "events": c["events"]}
        for k in ("windows", "motion", "speed_mps"):
            if k in c:
                row[k] = c[k]
        if "windows" in c:
            w = c["windows"]
            row["contact_s"] = round(w["impact"] / c["fps"], 4)
            row["normalized"] = {"windup": [0, round(w["windup"][1] / c["frames"], 3)],
                                 "active": [round(w["active"][0] / c["frames"], 3),
                                            round(w["active"][1] / c["frames"], 3)],
                                 "recovery": [round(w["recovery"][0] / c["frames"], 3), 1.0],
                                 "impact": round(w["impact"] / c["frames"], 3)}
        rows[short] = row
    return {"species": sp.ID, "clip_count": len(clips), "naming": "<species>__<name>", "fps": 30,
            "semantic_states": sp.SEMANTIC, "server_events": sp.SERVER_EVENTS, "clips": rows}


def run(sp, work, lods, log=print, out_dir=None):
    import time
    from anim import Quad, SkinSampler
    sk, parts = sp.build_cached()
    joints = [b.name for b in sk.bones]
    out_dir = out_dir or os.path.join(work, "out")
    os.makedirs(out_dir, exist_ok=True)
    t = time.time()
    lod_data = {lod: load_lod(sp, work, lod, joints) for lod in lods}
    log(f"  weights: {time.time() - t:.1f}s")
    # rig + skinning sampler (LOD1 surface incl. rigid antlers/horns/plates) for ground contact
    ref = lod_data.get(1) or lod_data[lods[0]]
    pos = np.concatenate([g["mesh"]["pos"] for g in ref.values()])
    jj = np.concatenate([g["joints"] for g in ref.values()])
    ww = np.concatenate([g["weights"] for g in ref.values()])
    tier = np.concatenate([g["tier"] for g in ref.values()])
    keep = tier == 1
    rigid_parts = {p["index"] for p in parts if p["rigid"] is not None}
    part_ids = np.concatenate([g["mesh"]["part"] for g in ref.values()])
    rigid = np.isin(part_ids, list(rigid_parts))
    sampler = SkinSampler(sk, pos[keep], jj[keep], ww[keep], joints, count=6000, rigid=rigid[keep])
    rig = Quad(sk)
    t = time.time()
    clips = sp.clips(rig, sampler)
    log(f"  clips: {len(clips)} in {time.time() - t:.1f}s")
    for c in clips:
        c.pop("_baked", None)
    man = clip_manifest(sp, clips)
    with open(os.path.join(out_dir, "clip_manifest.json"), "w") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    sizes = {}
    # standalone LOD files (level I look, no overlays)
    for lod in lods:
        path = os.path.join(out_dir, f"{sp.ID}_lod{lod}.glb")
        sizes[os.path.basename(path)] = write(path, sp, sk, [(lod, lod_data[lod])], clips, level=1,
                                              include_overlays=False,
                                              extras={"lod": lod, "clip_manifest": "clip_manifest.json"})
    # runtime (Godot): LOD1 + LOD2 on one skeleton, overlays as VARIANT nodes, level I materials
    rt = [(l, lod_data[l]) for l in (1, 2) if l in lod_data]
    path = os.path.join(out_dir, f"{sp.ID}_runtime.glb")
    sizes[os.path.basename(path)] = write(path, sp, sk, rt, clips, level=1, include_overlays=True,
                                          extras={"lods": [l for l, _ in rt], "runtime": "godot"})
    # the same runtime asset as .gltf + .bin + textures/ for the Godot project (no image bytes stored twice)
    rt_dir = os.path.join(out_dir, "godot")
    os.makedirs(rt_dir, exist_ok=True)
    sizes[f"godot/{sp.ID}_runtime.gltf"] = write(os.path.join(rt_dir, f"{sp.ID}_runtime.gltf"), sp, sk, rt, clips,
                                                 level=1, include_overlays=True, gltf_external=True,
                                                 extras={"lods": [l for l, _ in rt], "runtime": "godot"})
    # web canonical per-level files from LOD1 with the level look baked in
    if 1 in lod_data:
        for level in (1, 2, 3):
            data = {}
            for group, g in lod_data[1].items():
                b, e = level_textures(sp, g["tex"], group, level, os.path.join(work, "levels"))
                gg = dict(g)
                if b:
                    gg["base_override"] = b
                if e:
                    gg["emissive_override"] = e
                data[group] = gg
            path = os.path.join(out_dir, f"{sp.ID.upper()}_L{level}_RIGGED_ANIMATED.glb")
            sizes[os.path.basename(path)] = write(path, sp, sk, [(1, data)], clips, level=level,
                                                  include_overlays=False, extras={"web_canonical": True})
    with open(os.path.join(out_dir, "sizes.json"), "w") as f:
        json.dump(sizes, f, indent=1)
    log("  wrote", ", ".join(f"{k} {v / 1e6:.2f} MB" for k, v in sizes.items()))
    return clips
