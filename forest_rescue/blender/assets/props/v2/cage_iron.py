"""lf_cage_iron (IRON) from art/cage_variants_gate_sockets.png (middle column): riveted wrought-iron square cage on
an oak skid platform; riveted box posts with spire finials, riveted top frame (crown) with gothic tracery, middle and
bottom riveted bands, bars with collars and fleur tips, big riveted arch band over the door, enamel tree emblem,
iron barred door with bronze strap hinges (LEFT jamb seen from outside) and the hexagonal bronze seal socket.
"""
import math

import numpy as np

import cagegeo as CG
import cage_common as CC
import pv2

ID = "lf_cage_iron"
ATLAS = 2048
NATIVE = "bronze_seal"
SHEET = "cage_variants_gate_sockets.png"
LIGHT = (-0.55, -0.55, 0.62)
BOXES = {"closed34": (592, 108, 958, 444), "open34": (592, 440, 985, 732)}

PARAMS = dict(c=1.80, cy=1.60, s=0.34, zd=0.42, zt=3.05, zs=3.50, zc=3.45, kx=0.0, ky=0.0, pe=0.14, pf=0.55, hx=-1.10, dx1=1.30, sz=1.30,
              sx=1.06, zda=2.45, dz0=0.44)
FREE = ["cy", "zd", "zt", "zc", "kx", "ky", "pe", "pf", "hx", "dx1", "sz", "sx", "zda", "dz0"]


def points(p):
    c, cy, s = p["c"], p["cy"], p["s"]
    yf = -cy - 0.03
    return {
        "top_n": (-c, -cy, p["zt"] + 0.08), "top_l": (-c, cy, p["zt"] + 0.08), "top_r": (c, -cy, p["zt"] + 0.08),
        "crown": (p["kx"], p["ky"], p["zc"]),
        "plat_bl": (-c - p["pe"], cy + p["pe"], p["zd"]), "plat_n": (-c - p["pe"], -cy - p["pf"], p["zd"]),
        "plat_r": (c + p["pe"], -cy - p["pf"], p["zd"]),
        "post_n_top": (-c - s / 2, -cy - s / 2, p["zt"]),
        "door_bl": (p["hx"] + 0.11, yf, p["dz0"]), "door_br": (p["dx1"], yf, p["dz0"]),
        "door_ap": ((p["hx"] + 0.11 + p["dx1"]) / 2, yf, p["zda"]), "sock": (p["sx"], yf - 0.05, p["sz"]),
        "postb_foot": (c - s / 2, cy + s / 2, p["zd"]),
        "postn_foot": (-c + s / 2, -cy - s / 2, p["zd"]),
    }


def views():
    closed = pv2.ViewSpec(
        "closed34", SHEET, BOXES["closed34"],
        {"top_n": (722.3, 141.7), "top_l": (614.3, 173.3), "top_r": (918.3, 160.0), "crown": (778.3, 141.7),
         "plat_bl": (593.3, 376.7), "plat_r": (948.3, 381.7), "postn_foot": (745, 387),
         "door_bl": (790, 396.7), "door_br": (910, 388.3), "door_ap": (850, 216.7), "sock": (878.3, 316.7)},
        light=LIGHT, thresh=0.11, fill_holes=30, shadow=0.10, title="IRON closed 3/4")
    opened = pv2.ViewSpec(
        "open34", SHEET, BOXES["open34"],
        {"top_n": (714.5, 465.0), "top_l": (614.5, 491.0), "top_r": (895, 481.0), "crown": (768.3, 463.0),
         "plat_bl": (595, 683.3), "plat_n": (726.7, 705), "postb_foot": (780, 670)},
        light=LIGHT, thresh=0.11, fill_holes=30, shadow=0.10, hide_parts=("door_pivot",), tex_weight=0.75,
        render_pose={"door_pivot": {"rot": (0, 0, -math.radians(95))}}, ignore_boxes=[(872, 530, 985, 732)],
        iou_ignore=("door_pivot",),
        title="IRON open 3/4 (painted door on the RIGHT jamb = drawing inconsistency; production rule LEFT jamb -> "
              "door region ignored)")
    return [closed, opened]


def ground_poly(p):
    c, cy = p["c"], p["cy"]
    return [(-c - p["pe"] - 0.05, -cy - p["pf"], 0), (c + p["pe"] + 0.05, -cy - p["pf"], 0),
            (c + p["pe"] + 0.05, cy + p["pe"], 0), (-c - p["pe"] - 0.05, cy + p["pe"], 0)]


def painted_ts(p, view, row, xs, origin, ex):
    cam = p.get("_cams", {}).get(view)
    if cam is None:
        return None
    x0, y0 = BOXES[view][:2]
    o = np.array([origin[0], origin[1], 0.0])
    e3 = np.array([ex[0], ex[1], 0.0])
    n = np.cross(e3, (0, 0, 1))
    P = cam.on_plane(np.array(xs, float) - x0, np.full(len(xs), row - y0, float), o, n)
    return sorted(float((q - o) @ e3) for q in P)


def rivets_line(g, a, b, nrm, step, lod, size=0.032, tag="rivet"):
    if lod > 0:
        return
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    L = np.linalg.norm(b - a)
    n = max(1, int(L / step))
    nrm = np.asarray(nrm, float)
    R = CG.frame(np.cross(nrm, (0, 0, 1)) if abs(nrm[2]) < 0.9 else (1, 0, 0), nrm)
    for k in range(n + 1):
        pnt = a + (b - a) * (k / max(n, 1))
        CG.pyramid(g, pnt, size, size * 0.45, mat="iron", tag=tag, R=R)


def band(g, a, b, w, h, nrm, lod, tag="band", rivet_step=0.22):
    """Riveted flat band between a and b (centre line), w across (horizontal, perpendicular to the run), h tall."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    g.beam(a, b, w, h, up=(0, 0, 1), mat="iron", tag=tag)
    off = np.asarray(nrm, float) * (w / 2 + 0.002)
    rivets_line(g, a + off, b + off, nrm, rivet_step, lod)


def fleur(g, top, ex, lod):
    """Spear tip with two side curls (fleur-de-lis-like) on top of a bar."""
    top = np.asarray(top, float)
    CG.lathe(g, [(0.035, 0.0), (0.012, 0.06), (0.0, 0.13)], top, n=4 if lod == 0 else 3, mat="iron", tag="fleur")
    if lod == 0:
        ex = np.asarray(ex, float)
        for sgn in (-1, 1):
            P = np.array([top + (0, 0, 0.01), top + ex * sgn * 0.045 + (0, 0, 0.05), top + ex * sgn * 0.035 + (0, 0, 0.09)])
            g.tube(P, 0.009, n=4, mat="iron", tag="fleur")


def iron_face(g, origin, ex, L, z_bot, z_mid, z_top, n_arch, ts, lod, tag, fleur_bars=True):
    o = np.array([origin[0], origin[1], 0.0])
    ex = np.array([ex[0], ex[1], 0.0])
    nrm = np.cross(ex, (0, 0, 1))
    if lod == 2:
        ts = ts[::2]
    w = L / n_arch
    rise = (z_top - 0.06) - (z_mid + 0.08)
    zsp = z_mid + 0.08
    for t in ts:
        k = min(int(t / w), n_arch - 1)
        local = (t - k * w)
        r = (w * w / 4 + rise * rise) / w
        dx = abs(local - w / 2)
        top = zsp + math.sqrt(max(r * r - (r - w / 2 + dx) ** 2, 0.0))
        p0 = o + ex * t + (0, 0, z_bot)
        g.cyl(p0, o + ex * t + (0, 0, min(top, z_top)), 0.026, n=6 if lod == 0 else 4, mat="iron", tag=tag + "_bar",
              caps=(False, False))
        if lod == 0:
            for zc in (z_mid - 0.62,):
                CG.lathe(g, [(0.02, -0.04), (0.04, 0.0), (0.02, 0.04)], o + ex * t + (0, 0, zc), n=6, mat="iron",
                         tag=tag + "_collar", cap_top=False, cap_bot=False)
        if fleur_bars and lod < 2:
            fleur(g, o + ex * t + (0, 0, z_mid + 0.02), ex, lod)
    R = CG.frame(ex)
    g.box(o + ex * (L / 2) + (0, 0, z_mid), (L, 0.05, 0.07), R=R, mat="iron", tag=tag + "_rail")
    g.box(o + ex * (L / 2) + (0, 0, z_bot + 0.06), (L, 0.05, 0.06), R=R, mat="iron", tag=tag + "_rail")
    if lod < 2:
        n = 8 if lod == 0 else 5
        for k in range(n_arch):
            Lp, Rp = CG.pointed_arch(k * w, (k + 1) * w, zsp, rise, n)
            for pts in (Lp, Rp):
                CG.sweep_rect(g, np.array([o + ex * s_ + (0, 0, z_) for s_, z_ in pts]), 0.065, 0.09, up=(0, 0, 1),
                              mat="iron", tag=tag + "_arch")
            if lod == 0:
                # two lancets + an oculus inside each arch
                sub = w / 2
                for j in range(2):
                    Lp2, Rp2 = CG.pointed_arch(k * w + j * sub, k * w + (j + 1) * sub, zsp, rise * 0.62, 6)
                    for pts in (Lp2, Rp2):
                        g.tube(np.array([o + ex * s_ + (0, 0, z_) for s_, z_ in pts]), 0.014, n=4, mat="iron",
                               tag=tag + "_lancet")
                cc = o + ex * ((k + 0.5) * w) + (0, 0, zsp + rise * 0.78)
                ring = [cc + ex * (0.075 * math.cos(a)) + np.array([0, 0, 0.075 * math.sin(a)])
                        for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
                g.tube(np.array(ring + [ring[0]]), 0.013, n=4, mat="iron", tag=tag + "_oculus")


def build(A, p, lod):
    c, cy, s = p["c"], p["cy"], p["s"]
    zd, zt = p["zd"], p["zt"]
    hx = p["hx"]
    g = A.g("root", lod)
    pe, pf = p["pe"], p["pf"]
    # ---------------- oak skid platform: deck + 3 skid runners (along X) + bolt heads
    x0p, x1p, y0p, y1p = -c - pe, c + pe, -cy - pf, cy + pe
    g.box(((x0p + x1p) / 2, (y0p + y1p) / 2, (zd + 0.16) / 2 + 0.0), (x1p - x0p, y1p - y0p, zd - 0.16), mat="wood",
          tag="deck")
    for yy in (y0p + 0.22, (y0p + y1p) / 2, y1p - 0.22):
        g.box((0, yy, 0.08), (x1p - x0p + 0.14, 0.30, 0.16), mat="wood", tag="skid", skip=("-z",))
    if lod == 0:
        for (x, y, nrm) in ((x0p, y0p + 0.3, (-1, 0, 0)), (x0p, y1p - 0.3, (-1, 0, 0)), (x0p + 0.5, y0p, (0, -1, 0)),
                            (0.0, y0p, (0, -1, 0)), (x1p - 0.4, y0p, (0, -1, 0))):
            pnt = np.array([x, y, (zd + 0.16) / 2]) + np.array(nrm) * 0.005
            g.cyl(pnt, pnt + np.array(nrm) * 0.03, 0.045, n=8, mat="iron", tag="bolt")
    # plank floor seams are painted; deck top = floor
    # ---------------- iron posts with rivets, spires
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            x, y = sx_ * c, sy_ * cy
            g.box((x, y, (zd + zt) / 2), (s, s, zt - zd), mat="iron", tag="post")
            g.box((x, y, zd + 0.07), (s + 0.05, s + 0.05, 0.14), mat="iron", tag="post_shoe", skip=("-z",))
            g.box((x, y, zt + 0.04), (s + 0.06, s + 0.06, 0.08), mat="iron", tag="post_cap")
            CG.lathe(g, [(0.075, 0.0), (0.075, 0.04), (0.045, 0.07), (0.07, 0.13), (0.05, 0.19), (0.03, 0.22), (0.0, 0.46)],
                     (x, y, zt + 0.08), n=8 if lod == 0 else (6 if lod == 1 else 4), mat="iron", tag="spire")
            for fn in ((0, -1, 0), (-1, 0, 0), (1, 0, 0), (0, 1, 0)):
                if (fn[0] and fn[0] == sx_) or (fn[1] and fn[1] == sy_):
                    off = np.array(fn) * (s / 2 + 0.002)
                    rivets_line(g, np.array([x, y, zd + 0.25]) + off, np.array([x, y, zt - 0.15]) + off, fn, 0.32, lod)
    # hinge post (left jamb)
    g.box((hx, -cy, (zd + zt) / 2), (0.16, 0.16, zt - zd), mat="iron", tag="hinge_post")
    rivets_line(g, (hx, -cy - 0.082, zd + 0.3), (hx, -cy - 0.082, zt - 0.4), (0, -1, 0), 0.26, lod)
    # ---------------- top frame (riveted bands) = the crown
    zb = zt - 0.09
    for (a, b, nrm) in (((-c, -cy, zb), (c, -cy, zb), (0, -1, 0)), ((-c, cy, zb), (c, cy, zb), (0, 1, 0)),
                        ((-c, -cy, zb), (-c, cy, zb), (-1, 0, 0)), ((c, -cy, zb), (c, cy, zb), (1, 0, 0))):
        band(g, a, b, 0.09, 0.24, nrm, lod, tag="topband")
    # crown: four riveted straps rising from the post caps to a central boss + spire
    zc = p["zc"]
    rg = A.part("roof", None, (0.0, 0.0, zt)).geo[lod]          # crown = separate node (fade / cut away)
    nseg = 7 if lod == 0 else (4 if lod == 1 else 2)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            a = np.array([sx_ * c, sy_ * cy, zt + 0.06])
            kc = np.array([p["kx"], p["ky"], 0.0])
            P = []
            for t in np.linspace(0, 1, nseg):
                q = a * (1 - t) + kc * t
                q[2] = zt + 0.06 + (zc - zt - 0.06) * math.sin(t * math.pi / 2)
                P.append(q)
            CG.sweep_rect(rg, np.array(P), 0.085, 0.09, up=(0, 0, 1), mat="iron", tag="crown_strap")
    rg.box((p["kx"], p["ky"], zc), (0.14, 0.14, 0.1), mat="iron", tag="crown_boss")
    CG.lathe(rg, [(0.06, 0.0), (0.06, 0.03), (0.035, 0.06), (0.055, 0.11), (0.03, 0.17), (0.0, 0.38)], (p["kx"], p["ky"], zc + 0.05),
             n=8 if lod == 0 else 5, mat="iron", tag="spire")
    # middle / bottom bands are per face (iron_face rails); front: riveted segmental arch band over the door
    z_mid = zd + 0.52 * (zt - zd)
    xs_ = np.linspace(-c + s / 2, c - s / 2, 11 if lod == 0 else 7)
    zarc_base = zt - 0.75
    zarc = zarc_base + 0.32 * np.sqrt(np.clip(1 - (xs_ / (c - s / 2)) ** 2, 0, 1))
    P = np.stack([xs_, np.full(len(xs_), -cy - 0.01), zarc], 1)
    CG.sweep_rect(g, P, 0.07, 0.15, up=(0, -1, 0), mat="iron", tag="arch_band")
    if lod == 0:
        for q in P[1:-1:2]:
            CG.pyramid(g, q + (0, -0.037, 0), 0.03, 0.014, mat="iron", tag="rivet",
                       R=np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float))
    # tracery in the spandrels above the arch band (rings) + emblem
    if lod < 2:
        for xx in (-c + 0.45, -c + 1.05, c - 1.05, c - 0.45):
            cc = np.array([xx, -cy, zt - 0.36])
            ring = [cc + np.array([0.11 * math.cos(a), 0, 0.11 * math.sin(a)]) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
            g.tube(np.array(ring + [ring[0]]), 0.015, n=4, mat="iron", tag="tracery")
    nr = 14 if lod == 0 else (9 if lod == 1 else 6)
    xc = (p["hx"] + 0.11 + p["dx1"]) / 2
    half = [(0.30 * math.cos(a), 0.30 * math.sin(a)) for a in np.linspace(0, math.pi, nr)]
    Rm = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)
    g.prism(np.array(half), 0.0, 0.04, "enamel", "emblem", R=Rm, t=(xc, -cy - 0.05, zarc_base + 0.30))
    if lod < 2:
        arc = np.array([(xc + 0.30 * math.cos(a), -cy - 0.09, zarc_base + 0.30 + 0.30 * math.sin(a))
                        for a in np.linspace(0, math.pi, nr)])
        g.tube(arc, 0.025, n=5, mat="bronze", tag="emblem_rim")
    # ---------------- bar faces
    spx, spy = 2 * c - s, 2 * cy - s
    tl = painted_ts(p, "closed34", 330, [637, 648, 660, 672, 689.5, 705.5], (-c, -cy + s / 2), (0, 1))
    iron_face(g, (-c, -cy + s / 2), (0, 1), spy, zd, z_mid, zb - 0.09, 2,
              tl if tl else list(np.linspace(0, spy, 9)[1:-1]), lod, "left")
    iron_face(g, (-c + s / 2, cy), (1, 0), spx, zd, z_mid, zb - 0.09, 2, list(np.linspace(0, spx, 12)[1:-1]), lod, "back")
    iron_face(g, (c, -cy + s / 2), (0, 1), spy, zd, z_mid, zb - 0.09, 2, list(np.linspace(0, spy, 10)[1:-1]), lod, "right")
    fb = (hx - 0.08) - (-c + s / 2)
    if fb > 0.12:
        iron_face(g, (-c + s / 2, -cy), (1, 0), fb, zd, z_mid, zarc_base, 1, [fb / 2], lod, "frontbay")
    # ---------------- door, sockets, latch
    cfg = door_cfg(p)
    piv = CC.add_door_and_sockets(A, cfg, lod, NATIVE)
    for zz in cfg["strap_z"]:
        g.box((hx + 0.02, -cy - 0.085, zz), (0.12, 0.012, 0.16), mat="bronze", tag="pintle")
    if lod == 0:
        CC.add_markers(A, cfg, piv)
    return A


def door_cfg(p):
    c, cy = p["c"], p["cy"]
    hx = p["hx"]
    return dict(hinge_x=hx + 0.09, y_face=-cy - 0.03, thick=0.06, x1=p["dx1"], z0=p["dz0"],
                z_top_side=p["zda"] - 0.22, z_apex=p["zda"], stile_w=0.09, rail_h=0.12, bars=6, bar_r=0.018,
                rails_z=(p["dz0"] + 0.55, p["dz0"] + 1.25), socket_x=p["sx"], socket_z=p["sz"],
                strap_z=(p["dz0"] + 0.42, p["dz0"] + 1.36), strap_len=0.48, strap_w=0.11, latch_z=p["sz"] + 0.3,
                floor_z=p["zd"], captive_slots_xz=[(-0.72, 0.1), (0.05, -0.45), (0.74, 0.18)],
                exit=[(hx + 0.6, -cy + 0.5, p["zd"]), (hx + 0.6, -cy - 0.3, p["zd"]), (hx + 0.6, -cy - 1.4, 0.0),
                      (hx + 0.6, -cy - 2.6, 0.0)],
                wood_mat="iron", socket_mat="bronze",
                bar_x=painted_ts(p, "closed34", 350, [810, 830, 850.5, 870, 886.5], (0.0, -cy - 0.0), (1, 0)))


SWATCHES = {
    "iron": dict(sheet=SHEET, box=(712, 250, 740, 278), metres=0.22),
    "wood": dict(sheet=SHEET, box=(640, 384, 700, 400), metres=0.5),
    "bronze": dict(sheet=SHEET, box=(800, 860, 840, 885), metres=0.06),
    "enamel": dict(sheet=SHEET, box=(812, 178, 830, 192), metres=0.1),
    "stone": dict(sheet=SHEET, box=(712, 250, 740, 278), metres=0.22),
}


def sym_specs(p):
    """Right side (+X) mirrored from the painted left side; back (+Y) rotated from the left side."""
    return [("mirror_x_closed", "closed34", pv2.mirror_x(), 0.55),
            ("back_from_left", "closed34", pv2.rot_back_to_left(p["c"], p["cy"]), 0.45)]


def clips(A, B):
    CC.add_clips(A, B)


def meta(A, p):
    cfg = door_cfg(p)
    piv = np.array([cfg["hinge_x"], cfg["y_face"] - 0.035, 0.0])
    return CC.cage_meta(A, cfg, piv, NATIVE, {"cage_type": "iron", "native_family": NATIVE, "roofNode": "roof",
                                              "roofNote": "crown straps + central boss + spire as one node (meshes "
                                                          "lf_cage_iron_roof_LOD0/1/2); fade or hide it when captives are "
                                                          "inside and the camera is above"})
