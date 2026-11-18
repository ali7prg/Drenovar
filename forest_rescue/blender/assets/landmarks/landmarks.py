"""Landmark builders (art/06).  Each returns dict(lods={0,1,2: Kit}, colliders=[...], info={...}, extra={...}).

Blender axes: Z up, metres.  Bridge: origin = bridge centre on the world datum (y=0 in game units),
long axis +X, deck top exactly Z=1.1, deck 27.0 x 4.0 m (x in [-13.5, 13.5], y in [-2, 2]).
"""
import math
import numpy as np

from lmkit import Kit, rotm, STONE, WOOD, MISC, ROOF, GLOW
import lm_textures as lmt

DECK_TOP = 1.1
HALF_L = 13.5
HALF_W = 2.0
WET = 6.3          # wet banks at ±6.3 m (atlas: 84.165 / 96.769 around centre 90.482)
WATER_Z = -1.35    # atlas waterLevel (world datum)


def bank_z(x):
    """Real terrain profile across the bridge section (route lf_route_10_11 samples, local x)."""
    xs = np.array([-16.5, -13.5, -9.5, -8.5, -7.5, -6.5, -5.5, -4.0, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 13.5, 16.5])
    zs = np.array([0.56, 0.55, 0.50, 0.26, -0.38, -1.21, -2.03, -2.83, -2.83, -2.61, -1.99, -1.15, -0.31, 0.32, 0.53,
                   0.50, 0.50])
    return float(np.interp(x, xs, zs))


# ============================================================================ bridge

def build_bridge(lod):
    k = Kit(seed=11 + lod, bevel=(lod == 0))
    plank_t = 0.08
    z_plank_bot = DECK_TOP - plank_t
    str_h, str_w = 0.34, 0.24
    z_str_top = z_plank_bot
    z_str_bot = z_str_top - str_h
    piers = [-7.25, 7.25]             # inner faces at ±6.6 > wet banks ±6.3: main channel stays clear
    sills = [-10.4, 10.4]
    # ---------------- deck
    if lod == 0:
        x = -HALF_L
        while x < HALF_L - 1e-6:
            w = min(0.30, HALF_L - x)
            k.box((x + w / 2, 0, DECK_TOP - plank_t / 2), (w - 0.02, 2 * HALF_W, plank_t), rotm(0, 0, k.rng.normal(0, 0.004)),
                  WOOD, tile=1.2, skip=("-z",))
            x += w
    else:
        k.box((0, 0, DECK_TOP - plank_t / 2), (2 * HALF_L, 2 * HALF_W, plank_t), None, WOOD, tile=1.2)
    # stringers + edge beams
    ys = [-1.5, -0.5, 0.5, 1.5] if lod == 0 else [-1.5, 1.5]
    for y in ys:
        k.beam((-HALF_L, y, z_str_bot + str_h / 2), (HALF_L, y, z_str_bot + str_h / 2), str_w, str_h)
    for s in (-1, 1):
        k.beam((-HALF_L - 0.1, s * (HALF_W + 0.07), DECK_TOP - 0.22), (HALF_L + 0.1, s * (HALF_W + 0.07), DECK_TOP - 0.22),
               0.14, 0.42)
    # ---------------- stone piers (bank edges, outside the channel)
    z_pier_top = z_str_bot - 0.62            # stone pier on the bank; timber trestle bent on top (art/06 timber piers)
    for px in piers:
        zb = min(bank_z(px - 0.6), bank_z(px + 0.6)) - 0.6
        if lod == 0:
            for yy in (-1.6, 0.0, 1.6):
                k.block_wall(px - 0.62, px + 0.62, zb, z_pier_top - zb, 1.15, course=0.44, block=(0.5, 0.7), y=yy, gap=0.03)
            k.bblock((px, 0, z_pier_top + 0.08), (1.45, 4.8, 0.16), None, STONE, tile=1.6, chamfer=0.04)
        else:
            k.box((px, 0, (zb + z_pier_top) / 2), (1.25, 4.6, z_pier_top - zb), None, STONE, tile=1.6)
        trestle(k, px, z_pier_top + 0.16, z_str_bot, lod)
        k.collider("box", (px, 0, (zb + z_str_bot) / 2), (1.3, 4.7, z_str_bot - zb))
    # ---------------- timber trestle bents on low stone footings under the side spans
    for sx in sills:
        zf = bank_z(sx) - 0.1
        if lod < 2:
            for yy in (-1.5, 0.0, 1.5):
                (k.bblock if lod == 0 else k.box)((sx, yy, zf + 0.12), (0.6, 0.6, 0.34), None, STONE, tile=1.6)
            trestle(k, sx, zf + 0.29, z_str_bot, lod)
    for sx in ():
        zb = 0
        if lod < 2:
            for y in (-1.5, 0.0, 1.5):
                k.box((sx, y, (zb + z_str_bot) / 2), (0.7, 1.35, z_str_bot - zb), rotm(0, 0, k.rng.normal(0, 0.03)), STONE,
                      tile=1.6)
    # ---------------- abutments at the deck ends
    for s in (-1, 1):
        ax = s * (HALF_L - 0.35)
        zb = bank_z(ax) - 0.4
        if lod == 0:
            for y in (-2.0, 2.0):
                k.block_wall(ax - 0.7, ax + 0.7, zb, DECK_TOP - 0.05 - zb, 0.8, course=0.38, block=(0.45, 0.7), y=y * 1.12)
            k.block_wall(ax - 0.45, ax + 0.45, zb, z_str_bot - zb, 4.2, course=0.38, block=(0.4, 0.5), y=0.0)
        else:
            k.box((ax, 0, (zb + DECK_TOP - 0.05) / 2), (1.4, 4.9, DECK_TOP - 0.05 - zb), None, STONE, tile=1.6)
    # ---------------- central span: timber arch ribs + spandrel posts (clear over the channel)
    if lod < 2:
        nseg = 10 if lod == 0 else 6
        x_sp = 6.62
        z_sp = 0.05
        z_crown = z_str_bot - 0.05
        for y in ((-1.5, 1.5) if lod == 0 else (-1.5, 1.5)):
            pts = []
            for i in range(nseg + 1):
                t = i / nseg
                x = -x_sp + 2 * x_sp * t
                z = z_sp + (z_crown - z_sp) * (1 - (2 * t - 1) ** 2) ** 0.85
                pts.append((x, y, z))
            for a, b in zip(pts[:-1], pts[1:]):
                k.beam(a, b, 0.24, 0.3, up=(0, 0, 1))
            if lod == 0:
                for i in range(1, nseg, 2):
                    x, _, z = pts[i]
                    if z_str_bot - z > 0.12:
                        k.beam((x, y, z), (x, y, z_str_bot), 0.16, 0.16)
            # knee braces from the piers to the side-span stringers (reference style)
            for s in (-1, 1):
                px = s * 7.25
                k.beam((px + s * 0.65, y, z_str_bot - 0.55), (px + s * 1.9, y, z_str_bot), 0.16, 0.16)
    # ---------------- railings
    post_dx = 27.0 / 12
    for s in (-1, 1):
        yv = s * (HALF_W + 0.2)
        posts = [-HALF_L + i * post_dx for i in range(13)]
        for x in posts:
            if lod == 0 or abs(x) > HALF_L - 0.1 or lod == 1 and (round((x + HALF_L) / post_dx) % 2 == 0):
                k.box((x, yv, DECK_TOP + 0.33), (0.2, 0.2, 1.45), None, WOOD, tile=1.2)
                if lod == 0:
                    k.beam((x, yv, DECK_TOP - 0.38), (x + 0.0, yv + s * 0.0, DECK_TOP - 0.38), 0.01, 0.01) if False else None
        k.beam((-HALF_L - 0.1, yv, DECK_TOP + 0.98), (HALF_L + 0.1, yv, DECK_TOP + 0.98), 0.16, 0.13)
        if lod < 2:
            k.beam((-HALF_L, yv, DECK_TOP + 0.52), (HALF_L, yv, DECK_TOP + 0.52), 0.12, 0.1)
        if lod == 0:
            for x in posts[:-1]:
                k.beam((x + 0.12, yv, DECK_TOP + 0.08), (x + post_dx * 0.45, yv, DECK_TOP + 0.5), 0.08, 0.08)
        k.collider("box", (0, yv, DECK_TOP + 0.55), (27.2, 0.22, 1.1))
    # ---------------- ramps to the banks (≈11.5°), timber on a stone-edged earth fill
    ramp_len = 3.2
    for s in (-1, 1):
        x0 = s * HALF_L
        x1 = s * (HALF_L + ramp_len)
        z0, z1 = DECK_TOP, bank_z(x1) - 0.08
        ang = math.atan2(z0 - z1, ramp_len)
        n = 10 if lod == 0 else 1
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            xa, xb = x0 + (x1 - x0) * t0, x0 + (x1 - x0) * t1
            za, zb_ = z0 + (z1 - z0) * t0, z0 + (z1 - z0) * t1
            c = ((xa + xb) / 2, 0, (za + zb_) / 2 - plank_t / 2)
            L = math.hypot(xb - xa, zb_ - za)
            k.box(c, (L - (0.02 if lod == 0 else 0), 2 * HALF_W, plank_t), rotm(0, s * ang, 0), WOOD, tile=1.2,
                  skip=("-z",) if lod == 0 else ())
        # fill wedge under the ramp
        zb = min(bank_z(x0), bank_z(x1)) - 0.3
        V = np.array([[x0, -HALF_W, zb], [x1, -HALF_W, zb], [x1, -HALF_W, z1 - plank_t], [x0, -HALF_W, z0 - plank_t],
                      [x0, HALF_W, zb], [x1, HALF_W, zb], [x1, HALF_W, z1 - plank_t], [x0, HALF_W, z0 - plank_t]])
        faces = [(0, 1, 2, 3), (5, 4, 7, 6), (3, 2, 6, 7), (0, 3, 7, 4), (1, 5, 6, 2)]
        if s > 0:
            faces = [tuple(reversed(f)) for f in faces]
        uv = [[(0, 0), (ramp_len / 1.6, 0), (ramp_len / 1.6, 0.8), (0, 0.8)]] * len(faces)
        k.md.add(V, faces, uv, STONE, np.ones((8, 4)))
        if lod < 2:
            for yy in (-1, 1):
                k.beam((x0, yy * (HALF_W + 0.1), z0 + 0.05), (x1, yy * (HALF_W + 0.1), z1 + 0.05), 0.18, 0.16)
        k.collider("ramp", ((x0 + x1) / 2, 0, (z0 + z1) / 2), (ramp_len, 2 * HALF_W, 0.1), yaw=0.0)
    k.collider("box", (0, 0, DECK_TOP - 0.05), (27.0, 4.0, 0.1))
    # ---------------- art/01: stone tower piers with red banners on the banks (beside the deck at the bank piers)
    for px in piers:
        for s in (-1, 1):
            ty = s * (HALF_W + 0.55)
            zb = bank_z(px) - 0.3
            ht = DECK_TOP + 3.1
            if lod == 0:
                k.block_wall(px - 0.55, px + 0.55, zb, ht - zb, 1.1, course=0.45, block=(0.5, 0.7), y=ty, gap=0.03)
                k.bblock((px, ty, ht + 0.1), (1.3, 1.3, 0.2), None, STONE, tile=1.6, chamfer=0.04)
            else:
                k.box((px, ty, (zb + ht) / 2), (1.1, 1.1, ht - zb), None, STONE, tile=1.6)
            # pyramidal cap
            cz = ht + (0.2 if lod == 0 else 0.0)
            a, b, c_, d = ((px - 0.62, ty - 0.62, cz), (px + 0.62, ty - 0.62, cz), (px + 0.62, ty + 0.62, cz),
                           (px - 0.62, ty + 0.62, cz))
            apex = (px, ty, cz + 0.9)
            for p0, p1 in ((a, b), (b, c_), (c_, d), (d, a)):
                k.quad([p0, p1, apex, apex], [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9), (0.5, 0.9)], STONE)
        # red banner on a pole beside the downstream tower (art/01)
        pole_x = px + (0.95 if px > 0 else -0.95)
        pole_y = -(HALF_W + 0.55)
        k.cyl((pole_x, pole_y, bank_z(pole_x) - 0.2), (pole_x, pole_y, DECK_TOP + 4.4), 0.07, segs=6 if lod == 0 else 4)
        k.beam((pole_x - 0.45, pole_y, DECK_TOP + 4.2), (pole_x + 0.45, pole_y, DECK_TOP + 4.2), 0.07, 0.07)
        bu0, bv0, bu1, bv1 = lmt.uv("cloth_dark")
        top, bot = DECK_TOP + 4.15, DECK_TOP + 2.0
        k.quad([(pole_x - 0.42, pole_y - 0.02, bot), (pole_x + 0.42, pole_y - 0.02, bot),
                (pole_x + 0.42, pole_y - 0.02, top), (pole_x - 0.42, pole_y - 0.02, top)],
               [(bu0, bv0), (bu1, bv0), (bu1, bv1), (bu0, bv1)], MISC)
        k.collider("box", (px, -(HALF_W + 0.55), (DECK_TOP + 3.1) / 2), (1.1, 1.1, DECK_TOP + 3.4))
        k.collider("box", (px, HALF_W + 0.55, (DECK_TOP + 3.1) / 2), (1.1, 1.1, DECK_TOP + 3.4))
    return k


# ============================================================================ hunter shelter

def trestle(k, x, z0, z1, lod):
    """Timber trestle bent: 3 posts, cap beam, X braces (in the YZ plane at x)."""
    ys = (-1.6, 0.0, 1.6)
    for yy in ys:
        k.box((x, yy, (z0 + z1) / 2 - 0.08), (0.24, 0.24, max(0.1, z1 - z0 - 0.16)), None, WOOD, tile=1.2)
    k.beam((x, -2.1, z1 - 0.1), (x, 2.1, z1 - 0.1), 0.3, 0.2)
    if lod == 0 and z1 - z0 > 0.35:
        k.beam((x + 0.14, -1.6, z0 + 0.05), (x + 0.14, 0.0, z1 - 0.2), 0.08, 0.12)
        k.beam((x + 0.14, 1.6, z0 + 0.05), (x + 0.14, 0.0, z1 - 0.2), 0.08, 0.12)
        k.beam((x - 0.14, -1.6, z1 - 0.2), (x - 0.14, 0.0, z0 + 0.05), 0.08, 0.12)
        k.beam((x - 0.14, 1.6, z1 - 0.2), (x - 0.14, 0.0, z0 + 0.05), 0.08, 0.12)


def build_shelter(lod):
    k = Kit(seed=21 + lod, bevel=(lod == 0))
    W, D = 5.2, 3.6                 # along X (front), depth along Y (back = +Y)
    zf, zb = 3.0, 2.0               # eave heights front/back (shed roof falling to the back)
    posts = [(-W / 2, -D / 2, zf), (0.0, -D / 2, zf), (W / 2, -D / 2, zf), (-W / 2, D / 2, zb), (W / 2, D / 2, zb)]
    for x, y, h in posts:
        k.box((x, y, h / 2), (0.24, 0.24, h), rotm(0, 0, k.rng.normal(0, 0.02)), WOOD, tile=1.2)
        k.box((x, y, 0.12), (0.5, 0.5, 0.24), None, STONE, tile=1.6) if lod == 0 else None
    k.beam((-W / 2 - 0.3, -D / 2, zf), (W / 2 + 0.3, -D / 2, zf), 0.24, 0.28)
    k.beam((-W / 2 - 0.3, D / 2, zb), (W / 2 + 0.3, D / 2, zb), 0.22, 0.24)
    nr = 6 if lod == 0 else 3
    for i in range(nr):
        x = -W / 2 + W * i / (nr - 1)
        k.beam((x, -D / 2 - 0.6, zf + 0.25), (x, D / 2 + 0.5, zb + 0.05), 0.12, 0.16)
    if lod == 0:
        for x in (-W / 2, W / 2):
            k.beam((x, -D / 2 + 0.1, zf - 0.9), (x, -D / 2 + 1.0, zf), 0.12, 0.12)
            k.beam((x, D / 2 - 0.1, 0.4), (x, -D / 2 + 0.1, zf - 0.2), 0.1, 0.1)
    # roof slab (tiles) following the rafters
    ang = math.atan2(zf - zb, D)
    L = math.hypot(D + 1.1, zf - zb + 0.2)
    rows = 8 if lod == 0 else 1
    for r in range(rows):
        t0 = r / rows
        y0 = -D / 2 - 0.6 + (D + 1.1) * t0
        yc = y0 + (D + 1.1) / rows * 0.55
        zc = zf + 0.42 - (zf - zb) * ((yc + D / 2 + 0.6) / (D + 1.1)) + (0.0 if lod else 0.04)
        thick = 0.3 if lod else 0.12
        k.box((0, yc, zc), (W + 1.1 + (0.06 * (r % 2)), (D + 1.1) / rows * 1.18 if lod == 0 else L, thick),
              rotm(-ang - (0.07 if lod == 0 else 0), 0, 0), ROOF, tile=2.2)
    if lod == 0:                                       # moss cushions on the tiles
        mu0, mv0, mu1, mv1 = lmt.uv("moss")
        for i in range(9):
            xm = k.rng.uniform(-W / 2, W / 2)
            ym = k.rng.uniform(-D / 2 - 0.4, D / 2 + 0.3)
            zm = zf + 0.42 - (zf - zb) * ((ym + D / 2 + 0.6) / (D + 1.1)) + 0.09
            s = k.rng.uniform(0.35, 0.7)
            Rr = rotm(-ang, 0, 0)
            pts = [np.array([xm, ym, zm]) + Rr @ np.array([dx * s, dy * s * 0.7, 0]) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            k.quad(pts, [(mu0, mv0), (mu1, mv0), (mu1, mv1), (mu0, mv1)], MISC)
    # ridge/edge beams
    k.beam((-W / 2 - 0.5, -D / 2 - 0.62, zf + 0.42), (W / 2 + 0.5, -D / 2 - 0.62, zf + 0.42), 0.12, 0.14)
    # back + side plank walls
    nb = 14 if lod == 0 else 1
    for i in range(nb):
        x0 = -W / 2 + W * i / nb
        w = W / nb
        k.box((x0 + w / 2, D / 2 + 0.05, zb / 2), (w - (0.02 if lod == 0 else 0), 0.06, zb), None, WOOD, tile=1.2)
    for s in (-1, 1):
        n = 7 if lod == 0 else 1
        for i in range(n):
            y0 = -D / 2 + 0.6 + (D - 0.6) * i / n
            h = zb + (zf - zb) * (1 - (y0 + D / 2) / D) - 0.15
            if lod == 0 and s < 0 and i < 2:
                continue        # open gap at the left front (as in the reference)
            k.box((s * (W / 2 + 0.03), y0 + (D - 0.6) / n / 2, h / 2), (0.06, (D - 0.6) / n - 0.02, h), None, WOOD, tile=1.2)
    # chimney (stone) at the back right
    cx, cy = W / 2 - 0.5, D / 2 + 0.35
    if lod == 0:
        for i in range(10):
            k.bblock((cx + k.rng.normal(0, 0.02), cy, 0.22 + i * 0.42), (0.75, 0.7, 0.4), rotm(0, 0, k.rng.normal(0, 0.05)),
                     STONE, tile=1.6, chamfer=0.05)
        k.box((cx, cy, 4.35), (0.85, 0.8, 0.14), None, STONE, tile=1.6)
    else:
        k.box((cx, cy, 2.2), (0.75, 0.7, 4.4), None, STONE, tile=1.6)
    k.collider("box", (cx, cy, 2.2), (0.8, 0.8, 4.4))
    # interior: workbench, stool, log pile, net
    k.box((-0.6, D / 2 - 0.55, 0.85), (2.6, 0.75, 0.1), None, WOOD, tile=1.2)
    if lod < 2:
        for x in (-1.7, 0.5):
            for y in (D / 2 - 0.85, D / 2 - 0.25):
                k.box((x, y, 0.4), (0.1, 0.1, 0.8), None, WOOD, tile=1.2)
        k.cyl((0.6, -0.6, 0.0), (0.6, -0.6, 0.5), 0.26, 8 if lod == 0 else 5, WOOD)
        # log pile (right front)
        for r in range(3):
            for c in range(4 - r):
                y = -D / 2 + 0.45 + c * 0.32 + r * 0.16
                z = 0.17 + r * 0.29
                k.cyl((W / 2 - 1.2, y, z), (W / 2 - 0.25, y, z), 0.15, 7 if lod == 0 else 5, WOOD,
                      cap_rect=lmt.uv("charcoal") if False else None)
    if lod == 0:
        u0, v0, u1, v1 = lmt.uv("net")
        k.quad([(-1.9, -D / 2 + 0.05, 0.9), (-1.0, -D / 2 + 0.05, 1.1), (-1.0, -D / 2 + 0.05, zf - 0.1),
                (-1.9, -D / 2 + 0.05, zf - 0.1)], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], MISC)
        for i in range(8):
            a = k.rng.uniform(0, 6.28)
            r = k.rng.uniform(2.6, 3.6)
            k.rock((math.cos(a) * r, math.sin(a) * r * 0.8, 0.1), k.rng.uniform(0.35, 0.8, 3) * np.array([1, 1, 0.6]))
    k.collider("box", (0, 0, 1.4), (W + 0.4, D + 0.4, 2.8))
    return k


# ============================================================================ quarry mine + crane

def crane(k, lod, cx=4.4, cy=-1.9):
    """Timber jib crane + winch (art/06 crane inset): braced mast, long jib rising to the left with a stay,
    hanging stone block, winch drum with crank handles on a sled frame.  Pivot = mast base."""
    rng = k.rng
    # sled base frame
    k.beam((cx - 1.0, cy - 0.7, 0.12), (cx + 2.0, cy - 0.7, 0.12), 0.24, 0.24)
    k.beam((cx - 1.0, cy + 0.7, 0.12), (cx + 2.0, cy + 0.7, 0.12), 0.24, 0.24)
    for x in (cx - 0.9, cx + 0.1, cx + 1.9):
        k.beam((x, cy - 0.9, 0.3), (x, cy + 0.9, 0.3), 0.2, 0.2)
    # A-frame mast (two legs + braces)
    k.beam((cx - 0.15, cy - 0.65, 0.3), (cx, cy, 4.6), 0.26, 0.26)
    k.beam((cx - 0.15, cy + 0.65, 0.3), (cx, cy, 4.6), 0.26, 0.26)
    k.beam((cx + 1.6, cy, 0.3), (cx + 0.05, cy, 3.6), 0.2, 0.2)            # back strut
    if lod == 0:
        k.beam((cx - 0.1, cy - 0.45, 1.6), (cx - 0.1, cy + 0.45, 1.6), 0.12, 0.12)
        k.beam((cx - 0.05, cy - 0.3, 2.9), (cx - 0.05, cy + 0.3, 2.9), 0.12, 0.12)
    # jib: from the mast foot area rising to the left, stay rope from the mast top
    k.beam((cx - 0.1, cy, 1.2), (cx - 3.4, cy, 5.2), 0.26, 0.3)
    k.cyl((cx, cy, 4.6), (cx - 3.2, cy, 5.1), 0.03, 4, MISC, rect=lmt.uv("rope"), caps=False)
    # winch: frame + drum (rope) + crank handles
    wx = cx + 1.25
    for y in (cy - 0.55, cy + 0.55):
        k.box((wx, y, 0.75), (0.9, 0.14, 0.9), None, WOOD, tile=1.2)
    k.cyl((wx, cy - 0.5, 0.95), (wx, cy + 0.5, 0.95), 0.3, 12 if lod == 0 else 6, MISC, rect=lmt.uv("rope"),
          cap_rect=lmt.uv("sign"))
    if lod == 0:
        for s in (-1, 1):
            k.cyl((wx, cy + s * 0.62, 0.95), (wx, cy + s * 0.9, 0.95), 0.04, 5, MISC, rect=lmt.uv("iron"))
            k.beam((wx, cy + s * 0.92, 0.95), (wx + 0.35, cy + s * 0.92, 1.25), 0.06, 0.06)
    # rope from the winch over the jib tip down to the hanging block
    tip = np.array([cx - 3.3, cy, 5.15])
    blk = np.array([cx - 3.3, cy, 1.9])
    k.cyl((wx, cy, 1.2), tip, 0.022, 4, MISC, rect=lmt.uv("rope"), caps=False)
    k.cyl(tip, blk + np.array([0, 0, 0.55]), 0.025, 4, MISC, rect=lmt.uv("rope"), caps=False)
    (k.bblock if k.bevel else k.box)(blk, (1.0, 0.85, 0.8), rotm(0, 0, 0.1), STONE, tile=1.6)
    if lod == 0:
        for s in (-1, 1):
            k.beam(blk + np.array([s * 0.5, 0, 0.42]), blk + np.array([0, 0, 0.9]), 0.03, 0.03, mat=MISC,
                   rect=lmt.uv("rope"))
    return cx, cy, wx


def build_quarry(lod):
    k = Kit(seed=31 + lod, bevel=(lod == 0))
    # rock mound of rough blocks around the portal (portal faces -Y, the camera side)
    rng = k.rng
    rows = [(0.0, 9.0, 1.15), (1.1, 8.4, 1.1), (2.2, 7.6, 1.05), (3.2, 6.6, 1.0), (4.1, 5.0, 0.95)]
    for zb, width, h in rows:
        x = -width / 2
        while x < width / 2:
            L = rng.uniform(0.9, 1.5)
            xc = x + L / 2
            if not (abs(xc - 0.0) < 1.55 and zb < 2.8):
                depth = rng.uniform(2.0, 3.4) if lod == 0 else 3.2
                if lod == 0:
                    k.bblock((xc, 0.4 + rng.normal(0, 0.15), zb + h / 2), (L - 0.06, depth, h - 0.05),
                             rotm(rng.normal(0, 0.06), rng.normal(0, 0.06), rng.normal(0, 0.1)), STONE, tile=1.6,
                             chamfer=0.12, jitter=0.05)
                elif rng.random() < 0.6:
                    k.box((xc, 0.4 + rng.normal(0, 0.15), zb + h / 2), (L - 0.05, depth, h - 0.04),
                          rotm(rng.normal(0, 0.05), rng.normal(0, 0.05), rng.normal(0, 0.08)), STONE, tile=1.6)
            x += L
    if lod == 2:
        k.box((0, 0.6, 2.2), (8.0, 3.2, 4.4), None, STONE, tile=1.6)
    k.box((0, 2.2, 2.2), (9.0, 1.6, 4.4), None, STONE, tile=1.6) if lod < 2 else None
    # tunnel interior (dark) + portal timbers
    k.box((0, 1.6, 1.3), (2.6, 3.0, 2.6), None, MISC, rect=lmt.uv("charcoal"))
    for x in (-1.15, 1.15):
        k.box((x, -0.95, 1.35), (0.3, 0.3, 2.7), None, WOOD, tile=1.2)
        k.box((x, 0.3, 1.35), (0.26, 0.26, 2.7), None, WOOD, tile=1.2) if lod == 0 else None
    k.beam((-1.6, -0.95, 2.85), (1.6, -0.95, 2.85), 0.32, 0.32)
    if lod == 0:
        k.beam((-1.6, -0.75, 3.18), (1.6, -0.75, 3.18), 0.26, 0.26)
        for x in np.linspace(-1.4, 1.4, 6):
            k.beam((x, -1.1, 3.4), (x, 0.8, 3.4), 0.18, 0.16)
        for s in (-1, 1):
            k.beam((s * 1.15, -0.95, 1.9), (s * 0.45, -0.95, 2.72), 0.16, 0.16)
    # rail track out of the mine toward -Y
    nsl = 9 if lod == 0 else 3
    for i in range(nsl):
        y = -0.6 - i * 0.6
        k.box((0.1 * i * 0.2, y, 0.06), (1.3, 0.18, 0.1), rotm(0, 0, 0.04 * i), WOOD, tile=1.2)
    for s in (-1, 1):
        k.beam((s * 0.45, 0.8, 0.15), (s * 0.45 + 0.35, -5.6, 0.15), 0.07, 0.08, rect=lmt.uv("rail"), mat=MISC)
    cx, cy, wx = crane(k, lod)
    blk = np.array([cx - 3.3, cy, 1.9])
    if lod == 0:
        k.box((2.0, -3.3, 0.35), (0.8, 0.7, 0.7), None, WOOD, tile=1.2)
        for i in range(12):
            k.rock((rng.uniform(-4.6, 4.8), rng.uniform(-4.5, -1.2), 0.15), rng.uniform(0.35, 1.0, 3) * np.array([1, 1, 0.7]),
                   detail=0)
    k.collider("box", (0, 0.8, 2.2), (9.0, 3.6, 4.4))
    k.collider("box", (cx, cy, 2.3), (0.4, 0.4, 4.6))
    k.collider("box", (wx, cy, 0.6), (1.0, 1.3, 1.2))
    return k


# ============================================================================ ruined watchpost

def build_watchpost(lod):
    k = Kit(seed=41 + lod, bevel=(lod == 0))
    PW, PD, PH = 5.6, 4.4, 1.3          # raised platform
    if lod == 0:
        for y, axis_y in ((-PD / 2, -PD / 2), (PD / 2, PD / 2)):
            k.block_wall(-PW / 2, PW / 2, 0.0, PH, 0.55, course=0.43, y=axis_y)
        for x in (-PW / 2, PW / 2):
            k.block_wall(-PD / 2 + 0.3, PD / 2 - 0.3, 0.0, PH, 0.55, course=0.43, y=x, axis="y")
        k.box((0, 0, PH - 0.12), (PW - 0.2, PD - 0.2, 0.24), None, STONE, tile=1.6)
    else:
        k.box((0, 0, PH / 2), (PW, PD, PH), None, STONE, tile=1.6)
    # back wall with arch (along X at y = +PD/2 - 0.4), broken stepped top
    wy = PD / 2 - 0.45
    prof = lambda t: PH + (3.4 if t < 0.2 else 4.2 if t < 0.75 else 2.0 - (t - 0.75) * 4)
    arch_x, arch_w, arch_sp = 0.4, 1.7, PH + 1.6
    hole = lambda x, z: abs(x - arch_x) < arch_w / 2 and z < arch_sp + 0.5
    if lod == 0:
        k.block_wall(-PW / 2 + 0.2, PW / 2 - 0.2, PH, 4.3, 0.7, course=0.42, y=wy,
                     profile=lambda t: prof(t) - 0.0, skip_fn=lambda x, z: hole(x, z) or (abs(x - arch_x) < arch_w / 2 + 0.55
                                                                                        and z > arch_sp - 0.2 and z < arch_sp + 1.3))
        k.arch(arch_x, arch_sp, arch_w, 0.42, 0.72, n=9, y=wy)
        # side walls (left tall corner, right low), stepped ruins
        k.block_wall(-PD / 2 + 0.2, PD / 2 - 0.9, PH, 3.2, 0.6, course=0.42, y=-PW / 2 + 0.35, axis="y",
                     profile=lambda t: PH + 0.6 + 2.6 * t)
        k.block_wall(-PD / 2 + 0.2, PD / 2 - 0.9, PH, 1.6, 0.6, course=0.42, y=PW / 2 - 0.35, axis="y",
                     profile=lambda t: PH + 1.4 * t)
    else:
        k.box((-PW / 2 + 0.6, wy, PH + 2.1), (1.4, 0.7, 4.2), None, STONE, tile=1.6)
        k.box((arch_x + 1.6, wy, PH + 1.7), (1.6, 0.7, 3.4), None, STONE, tile=1.6)
        k.box((arch_x, wy, arch_sp + 1.25), (arch_w + 0.4, 0.7, 0.6), None, STONE, tile=1.6)
    # stairs up to the platform (right side, toward -Y/front)
    nst = 6
    rise = PH / nst
    for i in range(nst if lod < 2 else 1):
        x = PW / 2 + 0.35 + (nst - 1 - i) * 0.42
        if lod == 2:
            k.box((PW / 2 + 1.4, -0.6, PH / 2), (2.4, 1.6, PH), None, STONE, tile=1.6)
            break
        h = rise * (i + 1)
        k.box((x, -0.6, h / 2), (0.44, 1.7, h), rotm(0, 0, k.rng.normal(0, 0.03)), STONE, tile=1.6)
    if lod == 0:
        for i in range(14):
            a = k.rng.uniform(0, 6.28)
            r = k.rng.uniform(3.3, 4.8)
            k.box((math.cos(a) * r, math.sin(a) * r * 0.8, 0.2), (0.6, 0.45, 0.4), rotm(k.rng.normal(0, 0.2), k.rng.normal(0, 0.2),
                  k.rng.uniform(0, 3)), STONE, tile=1.6)
    if lod < 2:                                       # ivy curtains hanging from the wall tops (art/06)
        iu0, iv0, iu1, iv1 = lmt.uv("leaves")
        for i in range(12 if lod == 0 else 5):
            xw = k.rng.uniform(-PW / 2 + 0.4, PW / 2 - 0.5)
            ztop = prof((xw + PW / 2) / PW) - 0.15
            if abs(xw - arch_x) < arch_w / 2 + 0.1:
                continue
            wv, hv = k.rng.uniform(0.7, 1.3), min(ztop - PH * 0.6, k.rng.uniform(1.3, 2.6))
            yv = wy - 0.37
            k.quad([(xw - wv / 2, yv, ztop - hv), (xw + wv / 2, yv, ztop - hv), (xw + wv / 2, yv, ztop),
                    (xw - wv / 2, yv, ztop)], [(iu0, iv0), (iu1, iv0), (iu1, iv1), (iu0, iv1)], MISC)
        mu0, mv0, mu1, mv1 = lmt.uv("moss")
        for i in range(10 if lod == 0 else 4):         # moss cushions on the platform edge and steps
            xm, ym = k.rng.uniform(-PW / 2, PW / 2), k.rng.uniform(-PD / 2, PD / 2)
            s = k.rng.uniform(0.5, 1.0)
            k.quad([(xm - s, ym - s * 0.6, PH + 0.005), (xm + s, ym - s * 0.6, PH + 0.005), (xm + s, ym + s * 0.6, PH + 0.005),
                    (xm - s, ym + s * 0.6, PH + 0.005)], [(mu0, mv0), (mu1, mv0), (mu1, mv1), (mu0, mv1)], MISC)
    k.collider("box", (0, 0, PH / 2), (PW, PD, PH))
    k.collider("box", (0, wy, PH + 2.0), (PW, 0.8, 4.0))
    k.collider("ramp", (PW / 2 + 1.4, -0.6, PH / 2), (2.5, 1.7, PH))
    return k


# ============================================================================ standing stones

def stone_slab(k, c, w, h, t, yaw, knot, lod):
    """Rounded-top monolith (extruded profile) + carved knotwork panel on the front face."""
    n = 7 if lod == 0 else 4
    prof = []
    for i in range(n + 1):
        a = math.pi * i / n
        prof.append((math.cos(a) * w / 2 * (0.9 + 0.1 * math.sin(a)), h - (1 - math.sin(a)) * h * 0.3 * (w / h + 0.3)))
    prof = [(w / 2 * 1.05, 0.0)] + prof + [(-w / 2 * 1.05, 0.0)]
    P = np.array(prof)
    R = rotm(k.rng.normal(0, 0.04), k.rng.normal(0, 0.04), yaw)
    c = np.asarray(c, float)
    verts = []
    for ty in (-t / 2, t / 2):
        sc = 1.0 if ty < 0 else 0.92
        for x, z in P:
            verts.append(R @ np.array([x * sc, ty, z]) + c + np.array([0, 0, -0.25]))
    m = len(P)
    faces, uvs = [], []
    faces.append(tuple(range(m - 1, -1, -1)))
    uvs.append([(P[i][0] / 1.6, P[i][1] / 1.6) for i in range(m - 1, -1, -1)])
    faces.append(tuple(range(m, 2 * m)))
    uvs.append([(P[i][0] / 1.6 + 0.3, P[i][1] / 1.6) for i in range(m)])
    for i in range(m - 1):
        faces.append((i, i + 1, m + i + 1, m + i))
        L = np.linalg.norm(P[i + 1] - P[i])
        uvs.append([(0, P[i][1] / 1.6), (L / 1.6, P[i + 1][1] / 1.6), (L / 1.6, P[i + 1][1] / 1.6 + t / 1.6),
                    (0, P[i][1] / 1.6 + t / 1.6)])
    k.md.add(np.array(verts), faces, uvs, STONE, np.ones((len(verts), 4)))
    if knot and lod < 2:
        u0, v0, u1, v1 = lmt.uv(knot)
        pw, ph = w * 0.5, h * 0.5
        z0 = h * 0.22
        quad = [R @ np.array([x, -t / 2 - 0.006, z]) + c + np.array([0, 0, -0.25]) for x, z in
                ((-pw / 2, z0), (pw / 2, z0), (pw / 2, z0 + ph), (-pw / 2, z0 + ph))]
        k.quad(quad, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], MISC)


_MENHIR_CACHE = {}


def menhir_hi(w, h, t, knot, seed):
    """High-res menhir mesh (superquadric slab, rounded top, chipped), knot panel carved on the -Y face,
    moss shell on top. Returns (V, T, bare_field, field)."""
    key = (w, h, t, knot, seed)
    if key in _MENHIR_CACHE:
        return _MENHIR_CACHE[key]
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "forest"))
    from frlib import sdf, texproj
    import groundcover2 as gc2
    import cv2
    rng = np.random.default_rng(seed)
    a, b, c = w / 2, t / 2, h
    vox = 0.03
    F = sdf.Field((-a - 0.25, -b - 0.25, -0.3), (a + 0.25, b + 0.25, h + 0.2), vox)
    P = np.stack(np.meshgrid(*F.axes, indexing="ij"), -1)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    taper = 1 - 0.16 * np.clip(z / h, 0, 1)
    q = np.sqrt((x / (a * taper)) ** 2 + (y / (b * taper)) ** 2)
    zz = np.clip(z, 0, None) / c
    S = (q ** 2.6 + zz ** 5) ** (1 / 2.6)
    d = (S - 1) * min(a, b) * 0.9
    d = np.maximum(d, -z - 0.25)
    d += 0.035 * (texproj.fbm(P, 2.2, 3, seed=seed) - 0.5) + 0.02 * (texproj.fbm(P, 6.0, 2, seed=seed + 1) - 0.5)
    # carved knot panel on the front (-Y) face
    km = lmt.knot_pattern(256, 256, 1 if knot == "knot_a" else 2)
    strand = (km > 0.3).astype(np.float32)
    edge = np.clip(cv2.dilate(strand, np.ones((7, 7))) - strand, 0, 1)
    pw, ph, z0 = w * 0.62, h * 0.55, h * 0.22
    u = (x + pw / 2) / pw
    v = 1 - (z - z0) / ph
    inside = (u >= 0) & (u < 1) & (v >= 0) & (v < 1) & (y < 0)
    ui = np.clip((u * 255).astype(int), 0, 255)
    vi = np.clip((v * 255).astype(int), 0, 255)
    carve = np.zeros_like(d)
    carve[inside] = 0.035 * edge[vi[inside], ui[inside]] + 0.012 * (1 - strand[vi[inside], ui[inside]])
    F.d = (d + carve).astype(np.float32)
    F.smooth(0.6)
    bare = gc2.moss_dilate(F, 0.05, seed=seed + 5, up_lo=0.2, cover=0.5, freq=1.2, streak=True)
    V, T = F.mesh()
    out = (V, T, bare, F)
    _MENHIR_CACHE[key] = out
    return out


def stone_menhir(k, c, w, h, t, yaw, knot, lod, seed):
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "forest"))
    import trees_hollow as th
    import groundcover2 as gc2
    V, T, bare, F = menhir_hi(w, h, t, knot, seed)
    v, tt, n = th.decimate_bpy(V, T, [1400, 420, 60][lod])
    moss = gc2.split_moss(v, tt, bare, F)
    R = rotm(0, 0, yaw)
    W = v @ R.T + np.asarray(c, float)
    mu0, mv0, mu1, mv1 = lmt.uv("moss")
    sf, su, mf, mu = [], [], [], []
    for f, m in zip(tt, moss):
        p = v[f]
        nn = np.cross(p[1] - p[0], p[2] - p[0])
        ax = int(np.argmax(np.abs(nn)))
        o = [i for i in range(3) if i != ax]
        if m and lod < 2:
            mf.append(tuple(int(i) for i in f))
            mu.append([(mu0 + (mu1 - mu0) * ((q[0] * 0.7) % 1.0), mv0 + (mv1 - mv0) * ((q[1] * 0.7 + q[2] * 0.3) % 1.0)) for q in p])
        else:
            sf.append(tuple(int(i) for i in f))
            su.append([(q[o[0]] / 1.6 + 0.3 * seed, q[o[1]] / 1.6) for q in p])
    col = np.ones((len(W), 4))
    k.md.add(W, sf, su, STONE, col)
    if mf:
        k.md.add(W, mf, mu, MISC, col)
    if knot and lod < 2:                                   # normal-mapped knot decal flush with the carved panel
        u0, v0, u1, v1 = lmt.uv(knot)
        pw, ph = w * 0.5, h * 0.5
        z0 = h * 0.22
        yb = -t / 2 * (1 - 0.16 * (z0 + ph / 2) / h) - 0.012
        quad = [R @ np.array([xq, yb, zq]) + np.asarray(c, float) for xq, zq in
                ((-pw / 2, z0), (pw / 2, z0), (pw / 2, z0 + ph), (-pw / 2, z0 + ph))]
        k.quad(quad, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], MISC)


def build_stones(lod):
    k = Kit(seed=51 + lod, bevel=(lod == 0))
    spec = [(-3.2, -1.2, 1.35, 2.2, "knot_a"), (-2.0, 1.9, 1.15, 2.0, "knot_b"), (0.4, 2.9, 1.55, 2.75, "knot_a"),
            (3.0, 1.6, 1.15, 2.1, "knot_b"), (2.6, -1.6, 1.25, 2.3, "knot_a")]
    for i, (x, y, w, h, knot) in enumerate(spec):
        yaw = math.atan2(-y, -x) - math.pi / 2         # carved face toward the circle centre
        stone_menhir(k, (x, y, 0), w, h, 0.62 * w, yaw + math.pi, knot, lod, seed=500 + i)
        k.collider("box", (x, y, h / 2), (w, 0.62 * w, h), yaw=yaw)
    if lod == 0:
        for i in range(10):
            a = k.rng.uniform(0, 6.28)
            r = k.rng.uniform(0.5, 2.6)
            k.rock((math.cos(a) * r, math.sin(a) * r, 0.03), k.rng.uniform(0.2, 0.5, 3) * np.array([1, 1, 0.4]), detail=0)
    return k


# ============================================================================ camp

def tarp_mesh(nx=9, ny=7, lod=0):
    """Canvas tarp between 4 poles (sagging) as a grid; returns verts (grid), faces, uvs, pins mask."""
    if lod > 0:
        nx, ny = 4, 3
    else:
        nx, ny = 16, 12
    corners = np.array([[-2.2, -1.6, 2.15], [2.0, -1.8, 2.35], [2.2, 1.7, 2.75], [-2.0, 1.6, 2.6]])
    V, uv, pin = [], [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            p = (1 - u) * (1 - v) * corners[0] + u * (1 - v) * corners[1] + u * v * corners[2] + (1 - u) * v * corners[3]
            sag = 0.75 * math.sin(math.pi * u) * math.sin(math.pi * v) ** 0.8
            fold = 0.06 * math.sin(2 * math.pi * 3.5 * u + 1.3 * v) * math.sin(math.pi * v) + \
                0.03 * math.sin(2 * math.pi * 7 * v + u)
            p = p - np.array([0, 0, sag + fold])
            V.append(p)
            uv.append((u, v))
            pin.append(1.0 - math.sin(math.pi * u) * math.sin(math.pi * v))
    F = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            F.append((a, a + 1, a + nx + 2, a + nx + 1))
    return np.array(V), F, uv, np.array(pin), corners


def build_camp(lod):
    k = Kit(seed=61 + lod, bevel=(lod == 0))
    V, F, uvg, pin, corners = tarp_mesh(lod=lod)
    for c in corners:
        k.cyl((c[0], c[1], 0.0), (c[0], c[1], c[2] + 0.25), 0.09, 7 if lod == 0 else 5, WOOD)
        if lod == 0:                                  # rope lashing where the tarp is tied to the pole
            for dz in (-0.08, 0.0, 0.08):
                k.cyl((c[0], c[1], c[2] + dz - 0.03), (c[0], c[1], c[2] + dz + 0.03), 0.115, 7, MISC, rect=lmt.uv("rope"),
                      caps=False)
        k.collider("cylinder", (c[0], c[1], c[2] / 2), (0.2, 0.2, c[2]))
    if lod < 2:
        for c in corners[[0, 1]]:
            g = np.array([c[0] + np.sign(c[0]) * 1.2, c[1] - 0.8, 0.0])
            k.cyl(c + np.array([0, 0, 0.1]), g, 0.012, 3, MISC, rect=lmt.uv("rope"), caps=False)
    # lantern pole + lantern
    lp = np.array([3.0, -0.2, 0.0])
    k.cyl(lp, lp + np.array([0, 0, 2.9]), 0.08, 7 if lod == 0 else 5, WOOD)
    k.beam(lp + np.array([0, 0, 2.7]), lp + np.array([-0.6, 0, 2.7]), 0.08, 0.08)
    lan = lp + np.array([-0.55, 0, 2.2])
    lantern(k, lan, 0.42, lod)
    # campfire ring
    for i in range(11 if lod == 0 else 6):
        a = 2 * math.pi * i / (11 if lod == 0 else 6)
        k.rock((math.cos(a) * 0.75, -0.6 + math.sin(a) * 0.75, 0.12), (0.34, 0.3, 0.26), detail=1 if lod == 0 else 0)
    k.box((0, -0.6, 0.02), (1.1, 1.1, 0.04), None, MISC, rect=lmt.uv("ash"))
    if lod < 2:
        for a in (0.3, 1.4, 2.5):
            d = np.array([math.cos(a), math.sin(a), 0]) * 0.45
            k.cyl(np.array([0, -0.6, 0.08]) - d, np.array([0, -0.6, 0.18]) + d, 0.06, 5, WOOD)
        # tripod + pot
        top = np.array([0, -0.6, 1.5])
        for a in (0.2, 2.3, 4.4):
            k.cyl(top, np.array([math.cos(a) * 0.8, -0.6 + math.sin(a) * 0.8, 0]), 0.03, 4, MISC, rect=lmt.uv("iron"), caps=False)
        k.cyl(np.array([0, -0.6, 0.55]), np.array([0, -0.6, 0.85]), 0.2, 8, MISC, rect=lmt.uv("iron"), r2=0.17)
    # benches, stool, crates, barrel, bedroll
    for (x, y, L, yaw) in ((-1.4, -1.5, 1.8, 0.2), (-0.5, 1.2, 1.6, -0.1)):
        R = rotm(0, 0, yaw)
        k.box(np.array([x, y, 0.46]), (L, 0.38, 0.08), R, WOOD, tile=1.2)
        for s in (-1, 1):
            k.box(np.array([x, y, 0.21]) + R @ np.array([s * L * 0.38, 0, 0]), (0.12, 0.34, 0.42), R, WOOD, tile=1.2)
        k.collider("box", (x, y, 0.25), (L, 0.4, 0.5), yaw=yaw)
    k.box((1.0, -2.1, 0.45), (0.55, 0.45, 0.08), None, WOOD, tile=1.2)
    for s in (-1, 1):
        k.box((1.0 + s * 0.2, -2.1, 0.21), (0.08, 0.38, 0.42), None, WOOD, tile=1.2)
    for (x, y, z, sz) in ((2.0, 1.1, 0.35, (1.4, 0.8, 0.7)), (2.1, 1.15, 1.0, (1.0, 0.7, 0.6))):
        k.box((x, y, z), sz, rotm(0, 0, 0.1), WOOD, tile=1.2)
    k.box((2.05, 1.12, 1.33), (1.05, 0.75, 0.08), rotm(0, 0, 0.1), MISC, rect=lmt.uv("cloth_dark"))
    k.collider("box", (2.0, 1.1, 0.65), (1.5, 0.9, 1.3))
    k.cyl((3.2, 1.0, 0.0), (3.2, 1.0, 0.9), 0.32, 10 if lod == 0 else 6, WOOD, r2=0.3)
    k.collider("cylinder", (3.2, 1.0, 0.45), (0.64, 0.64, 0.9))
    if lod == 0:
        for z in (0.15, 0.75):
            k.cyl((3.2, 1.0, z - 0.03), (3.2, 1.0, z + 0.03), 0.335, 10, MISC, rect=lmt.uv("iron"), caps=False)
        k.cyl((-1.9, 0.2, 0.18), (-1.0, 0.25, 0.18), 0.18, 8, MISC, rect=lmt.uv("canvas"))
    return k, (V, F, uvg, pin)


def lantern(k, c, h, lod):
    """Hanging bronze lantern: frame + glowing glass; pivot = hook at the top."""
    c = np.asarray(c, float)
    w = h * 0.45
    k.box(c + np.array([0, 0, -h * 0.5]), (w * 0.9, w * 0.9, h * 0.62), None, GLOW, rect=lmt.uv("glass"))
    k.box(c + np.array([0, 0, -h * 0.9]), (w * 1.15, w * 1.15, h * 0.12), None, MISC, rect=lmt.uv("bronze"))
    k.box(c + np.array([0, 0, -h * 0.12]), (w * 1.1, w * 1.1, h * 0.12), None, MISC, rect=lmt.uv("bronze"))
    k.cyl(c + np.array([0, 0, -h * 0.06]), c + np.array([0, 0, h * 0.12]), w * 0.3, 6, MISC, rect=lmt.uv("bronze"), r2=0.02)
    if lod == 0:
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box(c + np.array([sx * w * 0.47, sy * w * 0.47, -h * 0.5]), (0.025, 0.025, h * 0.66), None, MISC,
                      rect=lmt.uv("bronze"))
        k.cyl(c + np.array([0, 0, h * 0.12]), c + np.array([0, 0, h * 0.28]), 0.03, 6, MISC, rect=lmt.uv("bronze"))


# ============================================================================ small props

def build_small(name, lod):
    k = Kit(seed=71 + lod + len(name), bevel=(lod == 0))
    if name == "stone_wall":
        for i in range(4):
            k.box((-1.2 + i * 0.8, 0, 0.3), (0.72 + k.rng.normal(0, 0.03), 0.6, 0.6), rotm(0, 0, k.rng.normal(0, 0.05)),
                  STONE, tile=1.6)
        if lod == 0:
            for i in range(3):
                k.box((-0.8 + i * 0.8, 0.0, 0.78), (0.7, 0.5, 0.36), rotm(0, 0, k.rng.normal(0, 0.06)), STONE, tile=1.6)
        k.collider("box", (0, 0, 0.45), (3.2, 0.62, 0.9))
    elif name == "signpost":
        k.box((0, 0, 1.1), (0.16, 0.16, 2.2), None, WOOD, tile=1.2)
        for (z, yaw, s) in ((1.75, 0.3, 1), (1.4, -0.2, -1)):
            R = rotm(0, 0, yaw)
            k.box(np.array([0, 0, z]) + R @ np.array([s * 0.45, 0, 0]), (0.8, 0.05, 0.2), R, MISC, rect=lmt.uv("sign"))
            if lod == 0:
                tip = np.array([0, 0, z]) + R @ np.array([s * 0.92, 0, 0])
                k.md.add(np.array([tip + R @ np.array([-s * 0.07, -0.025, 0.1]), tip + R @ np.array([-s * 0.07, -0.025, -0.1]),
                                   tip + R @ np.array([s * 0.06, -0.025, 0])]), [(0, 1, 2)] if s > 0 else [(1, 0, 2)],
                         [[(0.6, 0.2), (0.6, 0.3), (0.65, 0.25)]], MISC, np.ones((3, 4)))
        if lod == 0:
            for i in range(5):
                a = k.rng.uniform(0, 6.28)
                k.rock((math.cos(a) * 0.35, math.sin(a) * 0.35, 0.05), (0.25, 0.22, 0.15), detail=0)
        k.collider("cylinder", (0, 0, 1.1), (0.2, 0.2, 2.2))
    elif name == "rope_coil":
        n = 5 if lod == 0 else 3
        segs = 16 if lod == 0 else 8
        for j in range(n):
            r = 0.42 - j * 0.04
            z = 0.04 + j * 0.065
            pts = [np.array([math.cos(2 * math.pi * i / segs) * r, math.sin(2 * math.pi * i / segs) * r, z]) for i in range(segs + 1)]
            for a, b in zip(pts[:-1], pts[1:]):
                k.cyl(a, b, 0.035, 5 if lod == 0 else 3, MISC, rect=lmt.uv("rope"), caps=False)
        k.collider("cylinder", (0, 0, 0.15), (0.9, 0.9, 0.3))
    elif name == "lantern":
        lantern(k, (0, 0, 0.62), 0.5, lod)
        k.collider("box", (0, 0, 0.3), (0.3, 0.3, 0.6))
    elif name == "platform":
        for y in (-0.8, 0.0, 0.8):
            k.box((0, y, 0.12), (2.4, 0.22, 0.24), None, WOOD, tile=1.2)
        n = 8 if lod == 0 else 1
        for i in range(n):
            w = 2.4 / n
            k.box((-1.2 + w * (i + 0.5), 0, 0.29), (w - (0.03 if lod == 0 else 0), 2.0, 0.08), None, WOOD, tile=1.2,
                  grain_axis=None)
        k.collider("box", (0, 0, 0.17), (2.4, 2.0, 0.34))
    return k
