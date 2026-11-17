"""PBR materials and tiling textures shared by all soldiers.

Material names carry the keywords warrior_visual.gd uses to tune the runtime
response (skin, cloth, wool, linen, leather, steel, mail, wood, ...).
"""
import os

import bpy
import numpy as np

import texbake

TILE = 512


def _grid(size):
    y, x = np.mgrid[0:size, 0:size] / size
    return x, y


def _periodic_noise(size, freq, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((freq, freq))
    x, y = _grid(size)
    fx, fy = x * freq, y * freq
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a = g[iy % freq, ix % freq]
    b = g[iy % freq, (ix + 1) % freq]
    c = g[(iy + 1) % freq, ix % freq]
    d = g[(iy + 1) % freq, (ix + 1) % freq]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def _fbm2(size, base, octaves, seed):
    total, amp, norm = 0, 1.0, 0
    for o in range(octaves):
        total = total + amp * _periodic_noise(size, base * 2 ** o, seed + o)
        norm += amp
        amp *= 0.5
    return total / norm


def tile_set(directory):
    """Writes the tiling textures once; returns {name: {albedo, normal}}."""
    os.makedirs(directory, exist_ok=True)
    out = {}
    x, y = _grid(TILE)

    def write(name, albedo, height, strength):
        normal = texbake.height_to_normal(height, strength)
        paths = {"albedo": os.path.join(directory, f"tile_{name}_albedo.png"),
                 "normal": os.path.join(directory, f"tile_{name}_normal.png")}
        if not os.path.exists(paths["albedo"]):
            texbake.save_png(paths["albedo"], albedo)
            texbake.save_png(paths["normal"], normal)
        out[name] = paths

    # Forged steel: brushed streaks, hammer dents, rust specks.
    streak = _fbm2(TILE, 4, 3, 11) * 0.3 + np.sin(y * 2 * np.pi * 180 + _fbm2(TILE, 8, 2, 12) * 6) * 0.04
    dents = _fbm2(TILE, 16, 3, 13)
    rust = np.clip((_fbm2(TILE, 12, 4, 14) - 0.7) * 4, 0, 1) * 0.6
    base = 0.62 + streak * 0.35 - dents * 0.08
    steel = np.dstack([base, base * 0.99, base * 0.97])
    steel = steel * (1 - rust[..., None]) + np.array([0.42, 0.24, 0.12]) * rust[..., None]
    write("steel", np.clip(steel, 0, 1), dents * 0.6 + streak * 0.2 + rust * 0.3, 3.0)

    # Wood: oak grain along V.
    grain = np.sin((x * 40 + _fbm2(TILE, 4, 3, 21) * 6) * np.pi) * 0.5 + 0.5
    fine = _fbm2(TILE, 64, 2, 22)
    wood = np.dstack([0.45 + grain * 0.12 + fine * 0.06, 0.29 + grain * 0.08 + fine * 0.04, 0.16 + grain * 0.05])
    write("wood", np.clip(wood, 0, 1), grain * 0.5 + fine * 0.5, 2.5)

    # Leather: pebbled grain, darker creases.
    pebble = _fbm2(TILE, 48, 3, 31)
    crease = np.clip(1 - np.abs(_fbm2(TILE, 6, 3, 32) - 0.5) * 6, 0, 1)
    leather = np.dstack([0.36 + pebble * 0.1 - crease * 0.08, 0.21 + pebble * 0.06 - crease * 0.05, 0.11 + pebble * 0.03 - crease * 0.03])
    write("leather", np.clip(leather, 0, 1), pebble * 0.7 - crease * 0.4, 3.0)

    # Rope / bowstring / fletching.
    twist = np.sin((x * 60 + y * 60) * np.pi) * 0.5 + 0.5
    rope = np.dstack([0.66 + twist * 0.1, 0.58 + twist * 0.08, 0.42 + twist * 0.06])
    write("rope", rope, twist, 2.0)
    feather = np.dstack([0.86 + 0.08 * _fbm2(TILE, 32, 2, 41)] * 3) * np.array([1.0, 0.97, 0.9])
    write("feather", np.clip(feather, 0, 1), np.sin(y * 300) * 0.3, 1.0)
    return out


def material(name, albedo=None, normal=None, color=(1, 1, 1), roughness=0.8, metallic=0.0, double_sided=False):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = not double_sided
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    if albedo:
        if tuple(color) != (1, 1, 1):
            albedo = tinted(albedo, color)
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(albedo, check_existing=True)
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if normal:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(normal, check_existing=True)
        tex.image.colorspace_settings.name = "Non-Color"
        nmap = nodes.new("ShaderNodeNormalMap")
        links.new(tex.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def tinted(path, color):
    """Writes a colour-multiplied copy of a texture (glTF has no reliable tint node path)."""
    key = "_".join(f"{c:.3f}" for c in color)
    target = path.replace("_albedo.png", f"_{key}_albedo.png")
    if not os.path.exists(target):
        image = bpy.data.images.load(path, check_existing=True)
        w, h = image.size
        px = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)
        rgb = np.flipud(px[..., :3]) * np.array(color)
        texbake.save_png(target, np.clip(rgb, 0, 1))
    return target
