"""Procedural texture baking for DRENOVAR soldiers.

A texture is produced by rasterising a mesh's UV triangles and evaluating a
pattern function at the interpolated rest-pose 3D position of each texel.
Patterns return (albedo RGB, height, roughness). Normal maps are derived from
the baked height. Everything is deterministic (seeded) and needs only numpy.
"""
import os

import numpy as np

try:
    import bpy
except ImportError:  # texbake can be imported without Blender for previews
    bpy = None


def hash_noise(p, seed=0):
    """Smooth value noise in 3D (p: (N,3) array), output in [0,1]."""
    p = np.asarray(p, dtype=np.float64)
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = f * f * (3 - 2 * f)

    def h(ix, iy, iz):
        n = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
        n = (n ^ (n >> 13)) * 1274126177
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0

    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                out = out + w * h(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    return out


def fbm(p, octaves=4, seed=0):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * hash_noise(p * (2 ** o), seed + o)
        norm += amp
        amp *= 0.5
    return total / norm


def mesh_triangles(obj, uv_name=None):
    """Rest-pose triangles: positions (T,3,3) and UVs (T,3,2)."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers[uv_name] if uv_name else mesh.uv_layers.active
    co = np.array([v.co[:] for v in mesh.vertices])
    tris = mesh.loop_triangles
    verts = np.array([t.vertices[:] for t in tris])
    loops = np.array([t.loops[:] for t in tris])
    uvs = np.array([d.uv[:] for d in uv.data])
    world = np.array(obj.matrix_world)
    pos = co @ world[:3, :3].T + world[:3, 3]
    return pos[verts], uvs[loops]


def rasterize(positions, uvs, size):
    """Returns per-texel 3D positions (size,size,3) and a coverage mask."""
    out = np.zeros((size, size, 3), dtype=np.float64)
    mask = np.zeros((size, size), dtype=bool)
    px = uvs * size
    for t in range(len(px)):
        a, b, c = px[t]
        lo = np.floor(np.minimum(np.minimum(a, b), c)).astype(int) - 1
        hi = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int) + 1
        lo = np.clip(lo, 0, size - 1)
        hi = np.clip(hi, 0, size - 1)
        if hi[0] < lo[0] or hi[1] < lo[1]:
            continue
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1) + 0.5, np.arange(lo[1], hi[1] + 1) + 0.5)
        v0, v1 = b - a, c - a
        den = v0[0] * v1[1] - v1[0] * v0[1]
        if abs(den) < 1e-12:
            continue
        dx, dy = xs - a[0], ys - a[1]
        w1 = (dx * v1[1] - v1[0] * dy) / den
        w2 = (v0[0] * dy - dx * v0[1]) / den
        w0 = 1 - w1 - w2
        # Small conservative margin avoids cracks along UV seams.
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any():
            continue
        p3 = positions[t]
        pts = w0[..., None] * p3[0] + w1[..., None] * p3[1] + w2[..., None] * p3[2]
        iy = (ys[inside] - 0.5).astype(int)
        ix = (xs[inside] - 0.5).astype(int)
        out[size - 1 - iy, ix] = pts[inside]
        mask[size - 1 - iy, ix] = True
    return out, mask


def dilate(image, mask, passes=6):
    """Bleed colours outward so mip levels do not pull in background at seams."""
    image = image.copy()
    mask = mask.copy()
    for _ in range(passes):
        grown = image.copy()
        filled = mask.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(np.roll(image, dy, 0), dx, 1)
            smask = np.roll(np.roll(mask, dy, 0), dx, 1)
            take = smask & ~filled
            grown[take] = shifted[take]
            filled |= take
        image, mask = grown, filled
    return image


def height_to_normal(height, strength):
    gy, gx = np.gradient(height)
    n = np.dstack((-gx * strength, gy * strength, np.ones_like(height)))
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def bake(obj, pattern, size, directory, name, normal_strength=6.0, uv_name=None):
    """pattern(points (N,3)) -> (rgb (N,3), height (N,), roughness (N,))."""
    positions, uvs = mesh_triangles(obj, uv_name)
    points, mask = rasterize(positions, uvs, size)
    flat = points[mask]
    rgb, height, rough = pattern(flat)
    albedo = np.zeros((size, size, 3))
    hmap = np.zeros((size, size))
    rmap = np.full((size, size), 0.85)
    albedo[mask] = np.clip(rgb, 0, 1)
    hmap[mask] = height
    rmap[mask] = np.clip(rough, 0.05, 1)
    albedo = dilate(albedo, mask)
    hmap = dilate(hmap[..., None], mask)[..., 0]
    rmap = dilate(rmap[..., None], mask)[..., 0]
    normal = height_to_normal(hmap, normal_strength)
    os.makedirs(directory, exist_ok=True)
    paths = {}
    for key, data in (("albedo", albedo), ("normal", normal), ("roughness", np.repeat(rmap[..., None], 3, 2))):
        path = os.path.join(directory, f"{name}_{key}.png")
        save_png(path, data)
        paths[key] = path
    return paths


def save_png(path, rgb):
    """Writes an sRGB/linear 8-bit PNG through Blender's image API."""
    size_y, size_x = rgb.shape[:2]
    image = bpy.data.images.new(os.path.basename(path), size_x, size_y, alpha=False)
    rgba = np.ones((size_y, size_x, 4), dtype=np.float32)
    rgba[..., :3] = np.flipud(rgb)
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


# ---------------------------------------------------------------- patterns

def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) == 1 else t
    return a * (1 - t) + b * t


def color(hex_value):
    hex_value = hex_value.lstrip("#")
    return np.array([int(hex_value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]) ** 2.2 ** 0  # sRGB stored


def weave(p, scale=520.0):
    """Plain-weave cloth relief from rest-pose coordinates."""
    u = np.sin(p[:, 0] * scale + np.sin(p[:, 2] * scale) * 0.6)
    v = np.sin(p[:, 2] * scale + np.sin(p[:, 1] * scale) * 0.6)
    return 0.5 + 0.25 * (u * np.sign(v))


def grime(p, ground_fade=0.55, seed=3):
    """Dirt and wear: stronger near the ground, mottled."""
    low = np.clip((ground_fade - p[:, 2]) / ground_fade, 0, 1)
    return np.clip(fbm(p * 9.0, 4, seed) * 0.6 + low * 0.55 - 0.25, 0, 1)
