"""Armature layout of «Искра» (lf_horse_origin): 52 deform bones + non-deform root.

Pure data (numpy); `build_lf_horse_origin.py` turns it into a Blender armature.
Every bone's local X axis is aligned with the horse's lateral axis (+X = left) where
possible, so leg flexion/extension is a rotation about local X.
"""
import numpy as np

import horse_body as HB

V = lambda *a: np.array(a, float)  # noqa: E731

# LOD bone subsets (deform bones that may carry weights) and remap of the dropped ones
LOD1_DROP = {
    "belly": "spine_02", "forelock": "head",
    "mane_L_01": "neck_01", "mane_L_02": "neck_02", "mane_L_03": "neck_03", "mane_L_04": "neck_03",
    "mane_R_01": "neck_01", "mane_R_02": "neck_02", "mane_R_03": "neck_03", "mane_R_04": "neck_03",
    "ribbon_02": "ribbon_01", "ribbon_03": "ribbon_01", "tail_05": "tail_04", "tail_06": "tail_04",
}
LOD2_DROP = dict(LOD1_DROP)
LOD2_DROP.update({
    "jaw": "head", "ear_L": "head", "ear_R": "head", "ribbon_01": "head",
    "tail_02": "tail_01", "tail_04": "tail_03", "neck_02": "neck_01",
    "scapula_L": "spine_03", "scapula_R": "spine_03", "hoof_F_L": "pastern_F_L",
    "hoof_F_R": "pastern_F_R", "hoof_H_L": "pastern_H_L", "hoof_H_R": "pastern_H_R",
    "spine_01": "spine_02",
})


def resolve(name, drop):
    seen = set()
    while name in drop and name not in seen:
        seen.add(name)
        name = drop[name]
    return name


def mane_roots():
    """Crest points (poll -> withers) used both by mane cards and the mane bones."""
    return [V(0, -1.06, 1.88), V(0, -0.93, 1.835), V(0, -0.78, 1.75), V(0, -0.60, 1.63),
            V(0, -0.44, 1.535)]


def tail_points():
    """Tail chain along the solid tail mass (horse_hairvol.TAIL_SPLINE): dock arches back
    from the croup, hair falls to just above the fetlock line."""
    return [V(0, 0.60, 1.425), V(0, 0.73, 1.425), V(0, 0.815, 1.27), V(0, 0.855, 1.02),
            V(0, 0.870, 0.76), V(0, 0.866, 0.50), V(0, 0.845, 0.20)]


def ribbon_points():
    ring = throat_ring()
    return [ring + V(0.004, 0.0, -0.012), ring + V(0.008, 0.002, -0.08),
            ring + V(0.010, 0.004, -0.15), ring + V(0.011, 0.006, -0.225)]


def throat_ring():
    return V(0.072, -1.092, 1.505)


def bones(J=None):
    """[{name, head, tail, parent, deform, lateral(bool)}] in armature (= world rest) space."""
    J = J or HB.skeleton()
    B = []

    def add(name, head, tail, parent=None, deform=True):
        B.append(dict(name=name, head=np.asarray(head, float), tail=np.asarray(tail, float),
                      parent=parent, deform=deform))

    add("root", V(0, 0, 0), V(0, 0.35, 0), None, deform=False)
    add("spine_02", V(0, -0.10, 1.36), V(0, -0.45, 1.38), "root")
    add("spine_03", V(0, -0.45, 1.38), V(0, -0.66, 1.40), "spine_02")
    add("spine_01", V(0, -0.10, 1.36), V(0, 0.22, 1.40), "spine_02")
    add("pelvis", V(0, 0.22, 1.40), V(0, 0.62, 1.42), "spine_01")
    add("belly", V(0, -0.14, 1.08), V(0, -0.14, 0.86), "spine_02")
    add("neck_01", V(0, -0.66, 1.40), V(0, -0.84, 1.575), "spine_03")
    add("neck_02", V(0, -0.84, 1.575), V(0, -0.965, 1.735), "neck_01")
    add("neck_03", V(0, -0.965, 1.735), J["head"], "neck_02")
    add("head", J["head"], V(0, -1.47, 1.47), "neck_03")
    add("jaw", J["jaw"], J["jaw_tip"], "head")
    for s, sx in (("L", 1), ("R", -1)):
        add(f"ear_{s}", J[f"ear_{s}"], J[f"ear_tip_{s}"], "head")
    add("forelock", V(0, -1.20, 1.955), V(0, -1.30, 1.80), "head")
    roots = mane_roots()
    for s, sx in (("L", 1), ("R", -1)):
        for i in range(4):
            a = 0.5 * (roots[i] + roots[i + 1])
            # pointing outward-down from the crest on its side
            t = a + V(0.13 * sx, 0.0, -0.17)
            parent = ["neck_03", "neck_03", "neck_02", "neck_01"][i]
            add(f"mane_{s}_{4 - i:02d}", a, t, parent)
    rp = ribbon_points()
    add("ribbon_01", rp[0], rp[1], "head")
    add("ribbon_02", rp[1], rp[2], "ribbon_01")
    add("ribbon_03", rp[2], rp[3], "ribbon_02")
    tp = tail_points()
    parent = "pelvis"
    for i in range(6):
        add(f"tail_{i + 1:02d}", tp[i], tp[i + 1], parent)
        parent = f"tail_{i + 1:02d}"
    for s in ("L", "R"):
        add(f"scapula_{s}", J[f"scap_top_{s}"], J[f"shoulder_{s}"], "spine_03")
        add(f"humerus_{s}", J[f"shoulder_{s}"], J[f"elbow_{s}"], f"scapula_{s}")
        add(f"forearm_{s}", J[f"elbow_{s}"], J[f"knee_{s}"], f"humerus_{s}")
        add(f"cannon_F_{s}", J[f"knee_{s}"], J[f"fetlock_F_{s}"], f"forearm_{s}")
        add(f"pastern_F_{s}", J[f"fetlock_F_{s}"], J[f"coffin_F_{s}"], f"cannon_F_{s}")
        add(f"hoof_F_{s}", J[f"coffin_F_{s}"], hoof_tip(J, "F", s), f"pastern_F_{s}")
        add(f"femur_{s}", J[f"hip_{s}"], J[f"stifle_{s}"], "pelvis")
        add(f"tibia_{s}", J[f"stifle_{s}"], J[f"hock_{s}"], f"femur_{s}")
        add(f"cannon_H_{s}", J[f"hock_{s}"], J[f"fetlock_H_{s}"], f"tibia_{s}")
        add(f"pastern_H_{s}", J[f"fetlock_H_{s}"], J[f"coffin_H_{s}"], f"cannon_H_{s}")
        add(f"hoof_H_{s}", J[f"coffin_H_{s}"], hoof_tip(J, "H", s), f"pastern_H_{s}")
    return B


def hoof_tip(J, fh, s):
    """Hoof bone tail: ground contact centre (sole) — keeps the hoof frame meaningful."""
    return 0.5 * (J[f"toe_{fh}_{s}"] + J[f"heel_{fh}_{s}"]) + V(0, -0.01, 0.0)


def deform_names(J=None):
    return [b["name"] for b in bones(J) if b["deform"]]


def lod_bones(level, J=None):
    names = deform_names(J)
    drop = {0: {}, 1: LOD1_DROP, 2: LOD2_DROP}[level]
    return sorted({resolve(n, drop) for n in names})


def roll_vector(head, tail, lateral=V(1, 0, 0)):
    """Z-axis target for EditBone.align_roll so that the bone's local X ~ +lateral."""
    d = tail - head
    d = d / np.linalg.norm(d)
    x = lateral - (lateral @ d) * d
    if np.linalg.norm(x) < 1e-6:
        x = V(0, 0, 1) - (V(0, 0, 1) @ d) * d
    x /= np.linalg.norm(x)
    z = np.cross(x, d)
    return z
