"""Surface patterns evaluated in rest-pose 3D space (metres, Z up, front = -Y).

Every pattern returns (rgb (N,3) in sRGB 0..1, height (N,), roughness (N,)).
"""
import numpy as np

from texbake import fbm, hash_noise

RED = np.array([0.50, 0.09, 0.07])
LINEN = np.array([0.63, 0.57, 0.47])


def srgb(*values):
    return np.array(values, dtype=np.float64)


def _weave(p, scale=700.0):
    u = np.sin(p[:, 0] * scale + p[:, 1] * scale * 0.7)
    v = np.sin(p[:, 2] * scale)
    return 0.5 + 0.25 * u * np.sign(v)


def _grime(p, start=0.6, amount=0.55, seed=3):
    low = np.clip((start - p[:, 2]) / max(start, 1e-3), 0, 1)
    mottle = fbm(p * 7.0, 4, seed)
    return np.clip(mottle * 0.7 + low * amount - 0.3, 0, 1)


def patterns_dirt():
    return np.array([0.45, 0.36, 0.25])


def _apply_grime(rgb, p, start=0.6, amount=0.55, color=srgb(0.27, 0.21, 0.15), seed=3):
    g = _grime(p, start, amount, seed)[:, None]
    return rgb * (1 - g * 0.75) + color * g * 0.75


def skin(landmarks, tone=srgb(0.62, 0.43, 0.33), beard=srgb(0.22, 0.16, 0.12), stubble=0.6, seed=1):
    mouth = landmarks["mouth"]
    eye_l, eye_r = landmarks["eye_l"], landmarks["eye_r"]
    chin_z = landmarks["chin_z"]

    def pattern(p):
        n = fbm(p * 30.0, 3, seed)
        rgb = np.tile(tone, (len(p), 1)) * (0.92 + 0.12 * n[:, None])
        # Warm cheeks and nose, cooler jaw.
        front = np.clip((-p[:, 1] - 0.09) / 0.05, 0, 1)
        cheek = np.exp(-(((np.abs(p[:, 0]) - 0.045) / 0.025) ** 2 + ((p[:, 2] - (eye_l[2] - 0.035)) / 0.025) ** 2)) * front
        rgb = rgb * (1 - 0.18 * cheek[:, None]) + srgb(0.78, 0.38, 0.33) * 0.18 * cheek[:, None]
        # Lips.
        lip = np.exp(-((p[:, 0] / 0.022) ** 2 + ((p[:, 2] - mouth[2]) / 0.008) ** 2)) * front
        rgb = rgb * (1 - 0.45 * lip[:, None]) + srgb(0.55, 0.28, 0.25) * 0.45 * lip[:, None]
        # Stubble / short beard over jaw, chin and upper lip.
        jaw = (p[:, 2] < mouth[2] + 0.018) & (p[:, 2] > chin_z - 0.035) & (p[:, 1] < -0.05)
        upper_lip = (np.abs(p[:, 2] - (mouth[2] + 0.013)) < 0.008) & (np.abs(p[:, 0]) < 0.026)
        not_lip = lip < 0.35
        hair_noise = hash_noise(p * 900.0, seed + 7)
        beard_mask = ((jaw | upper_lip) & not_lip).astype(float) * stubble * (0.55 + 0.45 * hair_noise)
        rgb = rgb * (1 - beard_mask[:, None]) + beard * beard_mask[:, None]
        # Eyebrows.
        brow = np.zeros(len(p))
        for eye in (eye_l, eye_r):
            d = np.exp(-(((p[:, 0] - eye[0] * 1.08) / 0.024) ** 2 + ((p[:, 2] - eye[2] - 0.028) / 0.006) ** 2))
            brow = np.maximum(brow, d * front)
        rgb = rgb * (1 - 0.8 * brow[:, None]) + beard * 0.8 * brow[:, None]
        # Eye sockets and the shadow under the brow give the face depth at game distance.
        socket = np.zeros(len(p))
        for eye in (eye_l, eye_r):
            d = np.sqrt((p[:, 0] - eye[0]) ** 2 + ((p[:, 2] - eye[2]) * 1.3) ** 2)
            socket = np.maximum(socket, np.exp(-((d - 0.02) / 0.009) ** 2) * front)
        rgb = rgb * (1 - 0.22 * socket[:, None])
        nose_side = np.exp(-(((np.abs(p[:, 0]) - 0.018) / 0.008) ** 2 + ((p[:, 2] - (mouth[2] + 0.04)) / 0.02) ** 2)) * front
        rgb = rgb * (1 - 0.12 * nose_side[:, None])
        # Scalp hair (mostly under hoods and helmets).
        scalp = np.clip((p[:, 2] - (eye_l[2] + 0.045)) / 0.02, 0, 1) * np.clip((p[:, 1] + 0.12) / 0.03, 0, 1)
        rgb = rgb * (1 - scalp[:, None]) + beard * 1.15 * scalp[:, None]
        height = n * 0.15 + beard_mask * 0.3 * hair_noise
        rough = 0.62 - 0.08 * front + beard_mask * 0.3
        return np.clip(rgb, 0, 1), height, rough
    return pattern


def cloth(base, seed=5, grime_start=0.6, grime=0.5, fray=0.0):
    def pattern(p):
        w = _weave(p)
        n = fbm(p * 12.0, 4, seed)
        rgb = np.tile(base, (len(p), 1)) * (0.78 + 0.3 * n[:, None]) * (0.88 + 0.16 * w[:, None])
        rgb = _apply_grime(rgb, p, grime_start, grime, seed=seed)
        return np.clip(rgb, 0, 1), w * 0.4 + n * 0.3, 0.92 + 0.0 * n
    return pattern


def tabard(cross=True, base=LINEN, red=RED, chest_z=1.31, bar=0.047, seed=8, hem_z=0.55):
    def pattern(p):
        w = _weave(p)
        n = fbm(p * 10.0, 4, seed)
        rgb = np.tile(base, (len(p), 1))
        if cross:
            vertical = np.abs(p[:, 0]) < bar
            horizontal = (np.abs(p[:, 2] - chest_z) < bar) & (np.abs(p[:, 0]) < 0.2)
            mask = (vertical | horizontal).astype(float)
            # Hand-stitched edge: slight wobble.
            edge = fbm(p * 60.0, 2, seed + 1) * 0.008
            mask = np.maximum(mask, ((np.abs(p[:, 0]) < bar + edge) & vertical).astype(float))
            fade = 0.85 + 0.15 * fbm(p * 20.0, 3, seed + 2)
            rgb = rgb * (1 - mask[:, None]) + red * fade[:, None] * mask[:, None]
        rgb = rgb * (0.8 + 0.26 * n[:, None]) * (0.9 + 0.14 * w[:, None])
        stains = np.clip((fbm(p * 5.0, 4, seed + 3) - 0.55) * 3, 0, 1)
        rgb = rgb * (1 - 0.3 * stains[:, None]) + patterns_dirt() * 0.3 * stains[:, None]
        rgb = _apply_grime(rgb, p, hem_z + 0.45, 0.9, seed=seed)
        return np.clip(rgb, 0, 1), w * 0.45 + n * 0.3, np.full(len(p), 0.93)
    return pattern


def quilted(base, spacing=0.035, diamond=True, seed=9):
    def pattern(p):
        if diamond:
            a = np.abs(((p[:, 0] + p[:, 2]) / spacing) % 1 - 0.5)
            b = np.abs(((p[:, 0] - p[:, 2]) / spacing) % 1 - 0.5)
            groove = np.minimum(a, b)
        else:
            groove = np.abs((p[:, 2] / spacing) % 1 - 0.5)
        puff = np.clip(groove * 4, 0, 1) ** 0.6
        n = fbm(p * 14.0, 3, seed)
        rgb = np.tile(base, (len(p), 1)) * (0.74 + 0.26 * puff[:, None]) * (0.84 + 0.22 * n[:, None])
        rgb = _apply_grime(rgb, p, 0.9, 0.3, seed=seed)
        return np.clip(rgb, 0, 1), puff * 0.9 + n * 0.1, np.full(len(p), 0.95)
    return pattern


def mail(seed=10, base=srgb(0.6, 0.6, 0.62)):
    def pattern(p):
        angle = np.arctan2(p[:, 0], -p[:, 1]) * 0.14
        u = (angle + p[:, 0] * 0.3) / 0.008
        v = p[:, 2] / 0.0065
        row = np.floor(v)
        u = u + (row % 2) * 0.5
        fu, fv = u % 1 - 0.5, v % 1 - 0.5
        r = np.sqrt(fu * fu + fv * fv)
        ring = np.clip(1 - np.abs(r - 0.32) * 7, 0, 1)
        n = fbm(p * 8.0, 3, seed)
        rust = np.clip((fbm(p * 15.0, 3, seed + 1) - 0.62) * 4, 0, 1)
        rgb = base * (0.45 + 0.65 * ring[:, None]) * (0.85 + 0.25 * n[:, None])
        rgb = rgb * (1 - rust[:, None] * 0.6) + srgb(0.4, 0.22, 0.1) * rust[:, None] * 0.6
        return np.clip(rgb, 0, 1), ring, 0.45 + 0.4 * (1 - ring) + rust * 0.3
    return pattern


def leather(base=srgb(0.36, 0.22, 0.12), seed=11, straps_every=0.0, grime_start=0.35):
    def pattern(p):
        pebble = fbm(p * 140.0, 2, seed)
        crease = np.clip(1 - np.abs(fbm(p * 9.0, 3, seed + 1) - 0.5) * 7, 0, 1)
        rgb = np.tile(base, (len(p), 1)) * (0.85 + 0.25 * pebble[:, None]) * (1 - 0.25 * crease[:, None])
        height = pebble * 0.5 - crease * 0.4
        if straps_every:
            band = np.abs(((p[:, 2] + 0.5 * np.abs(p[:, 0])) / straps_every) % 1 - 0.5) < 0.09
            rgb[band] *= 0.6
            height = height + band * 0.6
        scuff = np.clip((fbm(p * 20.0, 3, seed + 2) - 0.55) * 3, 0, 1)
        rgb = rgb * (1 - scuff[:, None] * 0.3) + srgb(0.55, 0.42, 0.3) * scuff[:, None] * 0.3
        rgb = _apply_grime(rgb, p, grime_start, 0.6, seed=seed)
        return np.clip(rgb, 0, 1), height, 0.55 + 0.3 * crease
    return pattern


def shield_cross(base=srgb(0.86, 0.82, 0.72), red=RED, cross_w=0.06, seed=12, height=0.98, chest=0.12):
    def pattern(p):
        n = fbm(p * 9.0, 4, seed)
        grain = np.sin((p[:, 0] * 50 + fbm(p * 4.0, 2, seed + 4) * 4) * np.pi) * 0.5 + 0.5
        vertical = np.abs(p[:, 0]) < cross_w
        horizontal = np.abs(p[:, 2] - chest) < cross_w
        mask = (vertical | horizontal).astype(float)
        rgb = np.tile(base, (len(p), 1)) * (1 - mask[:, None]) + red * mask[:, None]
        rgb = rgb * (0.82 + 0.25 * n[:, None])
        chips = np.clip((fbm(p * 25.0, 3, seed + 5) - 0.66) * 6, 0, 1)
        rgb = rgb * (1 - chips[:, None]) + srgb(0.42, 0.29, 0.17) * chips[:, None] * (0.8 + 0.2 * grain[:, None])
        scratches = np.clip(1 - np.abs(np.sin((p[:, 0] * 3 + p[:, 2] * 7) * 40)) * 30, 0, 1) * (fbm(p * 6, 2, seed + 6) > 0.6)
        rgb = rgb * (1 - 0.25 * scratches[:, None])
        return np.clip(rgb, 0, 1), chips * 0.6 + grain * 0.15 + n * 0.1, 0.7 + chips * 0.2
    return pattern
