"""Rig `new_dinosaur_boss` for the Ancient Maw v2: bone table, skin weights, LOD bone merging (numpy).

70 deform bones (LOD0 <= 80): root, pelvis, spine_01-03, breath, neck_01-03, head, jaw, tongue_01-03,
eye_L/R, lid_up/lo_L/R, tail_01-12, per leg thigh/shin/foot/toe2a-b/toe3a-b/toe4a-b/hallux,
per arm upperarm/forearm/hand/finger1a-b/finger2a-b/finger3a-b.
LOD1 (<= 50) and LOD2 (<= 28) merge small bones into their parents (MERGE_LOD1 / MERGE_LOD2).
"""
import math

import numpy as np

import mv2_body as B

J = B.J


def tail_centreline(n=13):
    prof = B.trunk_profile()
    Y, zc = prof["Y"], prof["zc"]
    ys = np.linspace(0.30, Y[-1] - 0.02, 500)
    z = np.interp(ys, Y, zc)
    pts = np.stack([np.zeros_like(ys), ys, z], 1)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    seg = np.linspace(1.35, 0.65, n - 1)
    seg = seg / seg.sum()
    targets = np.concatenate([[0], np.cumsum(seg)]) * d[-1]
    return np.stack([np.interp(targets, d, pts[:, k]) for k in range(3)], 1)


def bone_table():
    """[{name, head, tail, parent, connect}] in rest pose (Blender world = armature space)."""
    T = []

    def add(name, h, t, parent, connect=False):
        T.append({"name": name, "head": tuple(map(float, h)), "tail": tuple(map(float, t)), "parent": parent,
                  "connect": connect})

    add("root", (0, 0, 0), (0, -0.6, 0), None)
    spine = [J["pelvis"], J["spine_01"], J["spine_02"], J["spine_03"], J["neck_01"], J["neck_02"], J["neck_03"],
             J["head"]]
    names = ["pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "neck_02", "neck_03"]
    for i, n in enumerate(names):
        add(n, spine[i], spine[i + 1], "root" if i == 0 else names[i - 1], connect=i > 0)
    add("head", J["head"], J["head_end"], "neck_03", connect=True)
    add("breath", (0, -1.30, 2.15), (0, -1.30, 1.75), "spine_02")
    add("jaw", J["jaw"], J["jaw_end"], "head")
    ty = [-3.42, -3.70, -3.96, -4.22]
    tz = [float(B.lip_z(y)) - 0.075 for y in ty]
    for i in range(3):
        add(f"tongue_{i + 1:02d}", (0, ty[i], tz[i]), (0, ty[i + 1], tz[i + 1]),
            "jaw" if i == 0 else f"tongue_{i:02d}", connect=i > 0)
    for sx, side in ((1, "L"), (-1, "R")):
        c = np.array([sx * 0.372, -3.63, 3.285])
        ax = np.array([sx * 0.80, -0.55, 0.22])
        ax /= np.linalg.norm(ax)
        add(f"eye_{side}", c, c + ax * 0.08, "head")
        add(f"lid_up_{side}", c, c + np.array([0, -0.08, 0.0]), "head")
        add(f"lid_lo_{side}", c, c + np.array([0, -0.08, 0.0]) + np.array([0, 0, -0.001]), "head")
    tc = tail_centreline(13)
    for i in range(12):
        add(f"tail_{i + 1:02d}", tc[i], tc[i + 1], "pelvis" if i == 0 else f"tail_{i:02d}", connect=i > 0)
    for sx, side in ((1, "L"), (-1, "R")):
        m = lambda p: np.asarray(p, float) * np.array([sx, 1, 1])  # noqa: E731
        add(f"thigh_{side}", m(J["hip_L"]), m(J["knee_L"]), "pelvis")
        add(f"shin_{side}", m(J["knee_L"]), m(J["ankle_L"]), f"thigh_{side}", connect=True)
        add(f"foot_{side}", m(J["ankle_L"]), m(J["ball_L"]), f"shin_{side}", connect=True)
        for toe, ch in B.TOES_L.items():
            add(f"{toe}a_{side}", m(ch[0]), m(ch[1]), f"foot_{side}")
            add(f"{toe}b_{side}", m(ch[1]), m(ch[2]), f"{toe}a_{side}", connect=True)
        add(f"hallux_{side}", m(B.HALLUX_L[0]), m(B.HALLUX_L[1]), f"foot_{side}")
        add(f"upperarm_{side}", m(J["shoulder_L"]), m(J["elbow_L"]), "spine_03")
        add(f"forearm_{side}", m(J["elbow_L"]), m(J["wrist_L"]), f"upperarm_{side}", connect=True)
        add(f"hand_{side}", m(J["wrist_L"]), m(J["hand_end_L"]), f"forearm_{side}", connect=True)
        for f, ch in B.FINGERS_L.items():
            add(f"{f}a_{side}", m(ch[0]), m(ch[1]), f"hand_{side}")
            add(f"{f}b_{side}", m(ch[1]), m(ch[2]), f"{f}a_{side}", connect=True)
    return T


def parents():
    return {b["name"]: b["parent"] for b in bone_table()}


# small bones folded into their parents per LOD (weights summed into the surviving ancestor)
MERGE_LOD1 = ["tongue_02", "tongue_03", "eye_L", "eye_R", "toe2b_L", "toe3b_L", "toe4b_L", "toe2b_R", "toe3b_R",
              "toe4b_R"] + [f"finger{i}{s}_{side}" for i in (1, 2, 3) for s in "ab" for side in "LR"]
MERGE_LOD2 = MERGE_LOD1 + ["tongue_01", "lid_up_L", "lid_lo_L", "lid_up_R", "lid_lo_R", "breath",
                           "toe2a_L", "toe3a_L", "toe4a_L", "hallux_L", "toe2a_R", "toe3a_R", "toe4a_R", "hallux_R",
                           "hand_L", "hand_R", "neck_02", "tail_02", "tail_04", "tail_06", "tail_08", "tail_10",
                           "tail_12", "spine_02"]


def surviving(name, merged):
    par = parents()
    while name in merged:
        name = par[name]
    return name


def merge_weights(W, names, merged):
    """W (N, B) -> W' with merged bones' weights moved to their surviving ancestors."""
    idx = {n: i for i, n in enumerate(names)}
    W2 = W.copy()
    for n in names:
        if n in merged:
            tgt = surviving(n, merged)
            W2[:, idx[tgt]] += W2[:, idx[n]]
            W2[:, idx[n]] = 0.0
    return W2


# ------------------------------------------------------------------------------------ skin weights
def _seg_dist(P, a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1), t


def chain_weights(P, chain, names, sharp=0.35):
    """Smooth weights along a bone chain: position s of the closest polyline point -> hat functions
    centred on bone mid-points (linear blend between neighbours)."""
    pts = [np.asarray(c, float) for c in chain]
    nseg = len(pts) - 1
    best = np.full(len(P), np.inf)
    s = np.zeros(len(P))
    lens = [np.linalg.norm(pts[i + 1] - pts[i]) for i in range(nseg)]
    cum = np.concatenate([[0], np.cumsum(lens)])
    for i in range(nseg):
        d, t = _seg_dist(P, pts[i], pts[i + 1])
        better = d < best
        best = np.where(better, d, best)
        s = np.where(better, cum[i] + t * lens[i], s)
    centres = (cum[:-1] + cum[1:]) * 0.5
    W = np.zeros((len(P), nseg))
    for i in range(nseg):
        left = centres[i - 1] if i > 0 else cum[0] - 1e3
        right = centres[i + 1] if i < nseg - 1 else cum[-1] + 1e3
        c = centres[i]
        w = np.where(s <= c, np.clip((s - left) / max(c - left, 1e-6), 0, 1),
                     np.clip((right - s) / max(right - c, 1e-6), 0, 1))
        W[:, i] = w
    W = W ** (1.0 + sharp)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    return {names[i]: W[:, i] for i in range(nseg)}, best


def compute_weights(V, names, parts, adjacency=None, smooth_iters=3):
    """Skin weights for body vertices V (N,3) from SDF part ownership + chain blending."""
    N = len(V)
    idx = {n: i for i, n in enumerate(names)}
    W = np.zeros((N, len(names)))
    tb = {b["name"]: b for b in bone_table()}
    # --- ownership by part groups (soft): distance of each group's union
    groups = {"trunk": [], "head": [], "jaw": [], "leg_L": [], "leg_R": [], "arm_L": [], "arm_R": [],
              "toes_L": [], "toes_R": [], "fingers_L": [], "fingers_R": []}
    for p in parts:
        b = p.bone or ""
        if p.name == "trunk":
            groups["trunk"].append(p)
        elif b in ("head",) or p.name in ("scar", "browknob"):
            groups["head"].append(p)
        elif b == "jaw":
            groups["jaw"].append(p)
        elif b.startswith(("thigh", "shin", "foot")):
            groups["leg_" + b[-1]].append(p)
        elif b.startswith(("toe", "hallux")):
            groups["toes_" + b[-1]].append(p)
        elif b.startswith(("upperarm", "forearm", "hand")):
            groups["arm_" + b[-1]].append(p)
        elif b.startswith("finger"):
            groups["fingers_" + b[-1]].append(p)
    gd = {}
    for g, ps in groups.items():
        if not ps:
            continue
        d = np.full(N, 10.0)
        for p in ps:
            d = np.minimum(d, p.fn(V))
        gd[g] = d
    keys = list(gd)
    D = np.stack([gd[k] for k in keys], 1)
    dmin = D.min(1, keepdims=True)
    falloff = 0.05
    O = np.exp(-(D - dmin) / falloff)
    O /= O.sum(1, keepdims=True)
    own = {k: O[:, i] for i, k in enumerate(keys)}

    def addw(bone, w):
        W[:, idx[bone]] += w

    # trunk: spine + neck + head + tail chain
    tc = [tb[f"tail_{i:02d}"]["tail"] for i in range(12, 0, -1)] + [tb["tail_01"]["head"]]
    chain = tc + [J["pelvis"], J["spine_01"], J["spine_02"], J["spine_03"], J["neck_01"], J["neck_02"],
                  J["neck_03"], J["head"], J["head_end"]]
    cnames = [f"tail_{i:02d}" for i in range(12, 0, -1)] + ["pelvis_tailjoin", "pelvis", "spine_01", "spine_02",
                                                             "spine_03", "neck_01", "neck_02", "neck_03", "head"]
    cw, _ = chain_weights(V, chain, cnames)
    cw["pelvis"] = cw["pelvis"] + cw.pop("pelvis_tailjoin")
    tr = own.get("trunk", 0)
    for n, w in cw.items():
        addw(n, w * tr)
    # breathing: ribcage/belly below the spine between the shoulders and the hips
    yb = V[:, 1]
    zs = np.interp(yb, [-2.3, -0.3], [2.85, 2.6])
    breath = np.clip((zs - V[:, 2]) / 0.6, 0, 1) * np.clip((yb + 2.1) / 0.4, 0, 1) * np.clip((-0.3 - yb) / 0.4, 0, 1)
    if "breath" in idx:
        moved = breath * 0.45 * tr
        for n in ("spine_01", "spine_02", "spine_03"):
            W[:, idx[n]] *= (1 - breath * 0.45 * tr)
        addw("breath", moved)
    # head / jaw split by the lip line (mouth region) and the mandible parts
    hd = own.get("head", 0) + own.get("jaw", 0)
    zl = np.interp(V[:, 1], B.head_profile()["Y"], B.head_profile()["zlip"])
    behind = np.clip((V[:, 1] - (-3.30)) / 0.18, 0, 1)        # 0 in front of the corner, 1 behind
    below = 1.0 / (1.0 + np.exp((V[:, 2] - (zl - 0.004)) / 0.012))
    jaw_w = np.clip(below * (1 - behind) + own.get("jaw", 0) * 0.85, 0, 1)
    jaw_w = np.where(V[:, 1] > -3.05, jaw_w * np.clip((-2.85 - V[:, 1]) / 0.2, 0, 1), jaw_w)
    head_chain = np.clip((V[:, 1] - (-3.25)) / 0.25, 0, 1)    # blend head -> neck_03 at the back of the skull
    addw("jaw", hd * jaw_w)
    addw("head", hd * (1 - jaw_w) * (1 - head_chain))
    addw("neck_03", hd * (1 - jaw_w) * head_chain)
    # eyelids
    for sx, side in ((1, "L"), (-1, "R")):
        c = np.array([sx * 0.372, -3.63, 3.285])
        r = np.linalg.norm(V - c, axis=1)
        ring = np.clip((0.115 - r) / 0.045, 0, 1) * (r > 0.045)
        up = V[:, 2] >= c[2] + 0.004
        lo = V[:, 2] < c[2] + 0.004
        w = ring * hd
        for n in ("head", "jaw"):
            W[:, idx[n]] *= (1 - w)
        addw(f"lid_up_{side}", w * up)
        addw(f"lid_lo_{side}", w * lo)
    # legs: thigh / shin / foot chain, toes and hallux by part ownership
    for side, sx in (("L", 1), ("R", -1)):
        m = lambda p: np.asarray(p, float) * np.array([sx, 1, 1])  # noqa: E731
        lw, _ = chain_weights(V, [m(J["hip_L"]) + np.array([0, 0, 0.35]), m(J["hip_L"]), m(J["knee_L"]),
                                  m(J["ankle_L"]), m(J["ball_L"])],
                              ["pelvis_leg", f"thigh_{side}", f"shin_{side}", f"foot_{side}"])
        g = own.get("leg_" + side, 0)
        addw("pelvis", lw.pop("pelvis_leg") * g)
        for n, w in lw.items():
            addw(n, w * g)
        gt = own.get("toes_" + side, 0)
        tparts = [p for p in groups["toes_" + side]]
        td = np.stack([p.fn(V) for p in tparts], 1)
        tb_names = [p.bone for p in tparts]
        tw = np.exp(-(td - td.min(1, keepdims=True)) / 0.02)
        tw /= tw.sum(1, keepdims=True)
        for j, n in enumerate(tb_names):
            addw(n, tw[:, j] * gt)
        # arms
        aw, _ = chain_weights(V, [m(J["shoulder_L"]) + np.array([0, 0, 0.25]), m(J["shoulder_L"]), m(J["elbow_L"]),
                                  m(J["wrist_L"]), m(J["hand_end_L"])],
                              ["chest_arm", f"upperarm_{side}", f"forearm_{side}", f"hand_{side}"])
        ga = own.get("arm_" + side, 0)
        addw("spine_03", aw.pop("chest_arm") * ga)
        for n, w in aw.items():
            addw(n, w * ga)
        gf = own.get("fingers_" + side, 0)
        fparts = groups["fingers_" + side]
        fd = np.stack([p.fn(V) for p in fparts], 1)
        fw = np.exp(-(fd - fd.min(1, keepdims=True)) / 0.015)
        fw /= fw.sum(1, keepdims=True)
        for j, p in enumerate(fparts):
            addw(p.bone, fw[:, j] * gf)
    # smooth over the surface, keep <= 4 influences
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-9)
    if adjacency is not None and smooth_iters:
        lids = [idx[n] for n in names if n.startswith("lid_")]
        keep = W[:, lids].copy() if lids else None
        for _ in range(smooth_iters):
            W = 0.5 * W + 0.5 * (adjacency @ W)
        if keep is not None:
            W[:, lids] = np.maximum(W[:, lids], keep * 0.8)
    return limit(W)


def limit(W, top=4, min_w=0.02):
    W = W.copy()
    if W.shape[1] > top:
        cut = np.argsort(-W, axis=1)[:, top:]
        np.put_along_axis(W, cut, 0.0, axis=1)
    W[W < min_w] = 0.0
    s = W.sum(1, keepdims=True)
    bad = s[:, 0] <= 0
    if np.any(bad):
        W[bad, 1] = 1.0
        s = W.sum(1, keepdims=True)
    return W / s
