"""Vectorised 3D noise for sculpt detail and texture baking (numpy, float32).

All functions take an (N, 3) array of points and return (N,) arrays. They are
deterministic (integer hashing, no global RNG state), so a rebuild reproduces
every map byte for byte.
"""
import numpy as np

_PRIMES = np.array([73856093, 19349663, 83492791], dtype=np.int64)


def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return h & 0x7FFFFFFF


def _rand(ix, iy, iz, seed, k=0):
    return (_hash3(ix, iy, iz, seed * 31 + k) % 1000003).astype(np.float32) / 1000003.0


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def value(p, seed=0):
    """Smooth value noise in [-1, 1]."""
    p = np.asarray(p, dtype=np.float32)
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = _fade(f)
    out = np.zeros(len(p), dtype=np.float32)
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1.0 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1.0 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1.0 - u[:, 2]
                out += wx * wy * wz * _rand(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out * 2.0 - 1.0


_GRAD = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1], [1, 1, 0], [-1, 1, 0], [0, -1, 1], [0, -1, -1]],
                 dtype=np.float32)


def perlin(p, seed=0):
    """Gradient noise, roughly in [-1, 1]."""
    p = np.asarray(p, dtype=np.float32)
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = _fade(f)
    out = np.zeros(len(p), dtype=np.float32)
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1.0 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1.0 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1.0 - u[:, 2]
                g = _GRAD[_hash3(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed) & 15]
                d = f - np.array([dx, dy, dz], dtype=np.float32)
                out += wx * wy * wz * np.einsum('ij,ij->i', g, d)
    return out * 1.6


def fbm(p, octaves=4, lacunarity=2.03, gain=0.5, seed=0, kind=perlin):
    p = np.asarray(p, dtype=np.float32)
    amp, total, norm = 1.0, np.zeros(len(p), dtype=np.float32), 0.0
    q = p.copy()
    for o in range(octaves):
        total += amp * kind(q, seed + o * 17)
        norm += amp
        amp *= gain
        q = q * lacunarity + np.float32(0.37 * (o + 1))
    return total / norm


def ridged(p, octaves=3, seed=0):
    """Ridged multifractal in [0, 1] (sharp creases at 1)."""
    p = np.asarray(p, dtype=np.float32)
    amp, total, norm = 1.0, np.zeros(len(p), dtype=np.float32), 0.0
    q = p.copy()
    for o in range(octaves):
        r = 1.0 - np.abs(perlin(q, seed + 5 * o))
        total += amp * r * r
        norm += amp
        amp *= 0.5
        q = q * 2.07 + 0.11
    return total / norm


def worley(p, seed=0, jitter=0.9, chunk=400000):
    """Cellular noise: returns F1, F2 (distances) and a per-cell random id in [0,1)."""
    p = np.asarray(p, dtype=np.float32)
    n = len(p)
    F1 = np.empty(n, np.float32)
    F2 = np.empty(n, np.float32)
    cid = np.empty(n, np.float32)
    for s in range(0, n, chunk):
        q = p[s:s + chunk]
        i = np.floor(q).astype(np.int64)
        f1 = np.full(len(q), 9.0, np.float32)
        f2 = np.full(len(q), 9.0, np.float32)
        best = np.zeros(len(q), np.float32)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    cx, cy, cz = i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz
                    fp = np.stack([_rand(cx, cy, cz, seed, 1), _rand(cx, cy, cz, seed, 2),
                                   _rand(cx, cy, cz, seed, 3)], 1) * jitter + (0.5 - jitter * 0.5)
                    d = np.linalg.norm(np.stack([cx, cy, cz], 1).astype(np.float32) + fp - q, axis=1)
                    closer = d < f1
                    f2 = np.where(closer, f1, np.minimum(f2, d))
                    best = np.where(closer, _rand(cx, cy, cz, seed, 4), best)
                    f1 = np.where(closer, d, f1)
        F1[s:s + chunk] = f1
        F2[s:s + chunk] = f2
        cid[s:s + chunk] = best
    return F1, F2, cid


def stretch_along(p, direction, factor):
    """Coordinates in which features become `factor` times longer along `direction`."""
    d = direction / np.maximum(np.linalg.norm(direction, axis=-1, keepdims=True), 1e-6)
    along = np.sum(p * d, axis=-1, keepdims=True)
    return p + (1.0 / factor - 1.0) * along * d
