"""Species builders: golden oak, dark pine (spruce), birch, willow -> LOD0/1/2 MeshData per variant.

Material slots: LOD0 = [bark, foliage]; LOD1/LOD2 = [foliage] only (bark mapped to the atlas bark
strip so far LODs are a single draw call).  All units metres, Z up, trunk base at the origin.
"""
import math
import numpy as np

import atlas
import treegen as tg
from scipy.spatial import cKDTree
from scipy.cluster.vq import kmeans2
from treegen import MeshData, normalize


# ============================================================================ common broadleaf finishing

def _subdiv(pts, step=0.6):
    pts = [np.asarray(p, float) for p in pts]
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return out


def _bezier(p0, p1, p2, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * np.asarray(p0) + 2 * t * (1 - t) * np.asarray(p1) + t ** 2 * np.asarray(p2)


class Result:
    def __init__(self):
        self.lods = {}
        self.info = {}


def _pick(rng, items):
    w = np.array([i[0] for i in items], float)
    return items[rng.choice(len(items), p=w / w.sum())][1]


def finish_broadleaf(sk, env, spec, rng):
    """Skeleton + envelope -> LOD0/1/2 MeshData following `spec` (see oak specs below)."""
    P, parent, fixed, can = sk.arrays()
    P = tg.smooth_skeleton(P, parent, fixed, iters=spec.get("smooth", 3))
    order = tg.topo_order(parent)
    R = tg.pipe_radii(parent, r_tip=0.01, gamma=spec.get("gamma", 2.3), order=order[::-1])
    root = order[0]
    # remap radii: trunk base radius fixed, power curve keeps limbs chunky
    Rb = R[root]
    # automatic exponent: branch tips -> r_tip, trunk base -> r_base (limbs stay chunky)
    r_tip = spec.get("r_tip", 0.014)
    alpha = math.log(r_tip / spec["r_base"]) / math.log(0.01 / Rb) if Rb > 0.011 else 1.0
    alpha = float(np.clip(alpha * spec.get("alpha_k", 1.0), 0.7, 3.5))
    R = spec["r_base"] * (R / Rb) ** alpha
    res_alpha = alpha
    # authored trunk nodes only: enforce the specified taper
    for i in spec.get("trunk_ids", []):
        if "trunk_r" in spec:
            R[i] = max(R[i], spec["trunk_r"](P[i]))
    for ids_l, r0, r1 in spec.get("limbs", []):           # thick gnarled main limbs
        for j, i in enumerate(ids_l):
            R[i] = max(R[i], r0 + (r1 - r0) * j / max(len(ids_l) - 1, 1))
    chains, cpar, corder = tg.build_chains(P, parent, R)
    L = tg.path_lengths(P, parent)
    Lmax = L.max()
    sway = np.clip((L - 0.4) / max(Lmax - 0.4, 1e-3), 0, 1) ** 1.35
    ph_chain = tg.branch_phases(chains, cpar, rng)
    node_chain = np.zeros(len(P), int)
    for ci, ch in enumerate(chains):
        for k, n in enumerate(ch):
            if k == 0 and cpar[ci] >= 0:
                continue
            node_chain[n] = ci
    ao = tg.crown_ao(P, env=env, floor=0.38)
    ch_list = tg.children_lists(parent)
    # distance (path) to nearest tip below each node
    tipd = np.full(len(P), 1e9)
    for i in order[::-1]:
        if not ch_list[i]:
            tipd[i] = 0.0
        else:
            tipd[i] = min(tipd[c] + np.linalg.norm(P[c] - P[i]) for c in ch_list[i])
    crown_c = env.centre.copy()
    crown_c[2] = env.pmin[2] + (env.pmax[2] - env.pmin[2]) * spec.get("crown_c_h", 0.45)
    res = Result()
    res.skel = dict(P=P, parent=parent, R=R)
    res.info["radius_alpha"] = round(res_alpha, 3)
    res.info["nodes"] = int(len(P))

    def bark(md, lod, cull_k=1.0):
        cull = spec["cull"][lod] * cull_k
        segtab = [tg.SEG_LOD0, tg.SEG_LOD1, tg.SEG_LOD2][lod]
        mat = 0
        uvmode = "tile" if lod == 0 else "atlas"
        rect = atlas.uv_rect("bark_" + spec["bark"]) if lod > 0 else None
        maxorder = spec.get("max_order", [9, 3, 1])[lod]
        for ci, ch in enumerate(chains):
            if corder[ci] > maxorder:
                continue
            nodes = list(ch)
            if spec.get("skip_order0") and (corder[ci] == 0 or (corder[ci] == 1 and corder[cpar[ci]] == 0
                                                                 and nodes[0] == chains[cpar[ci]][0])):
                nodes = nodes[1:]
                if len(nodes) < 2:
                    continue
            if cpar[ci] >= 0 and len(nodes) > 1:
                r0 = R[nodes[1]]
            else:
                r0 = R[nodes[0]]
            if r0 < cull and corder[ci] > 0:
                continue
            keep = [nodes[0]]
            for n in nodes[1:]:
                if R[n] < cull * 0.55 and corder[ci] > 0:
                    break
                keep.append(n)
            if len(keep) < 2:
                continue
            pts = P[keep].copy()
            rad = R[keep].copy()
            if cpar[ci] >= 0:
                rad[0] = rad[1] * 1.05
                # start slightly inside the parent so the joint is hidden
                pts[0] = pts[0] + normalize(pts[1] - pts[0]) * min(0.15, rad[0])
            step = (lambda r: np.clip(r * [10, 14, 20][lod], [0.35, 0.7, 1.2][lod], [1.6, 2.6, 4.0][lod]))
            pts2, rad2, kidx = tg.resample_chain(pts, rad, step, min_angle_deg=[9, 15, 25][lod])
            if lod == 2:
                pts2, rad2 = pts2[: max(2, min(len(pts2), 3 if corder[ci] else 4))], rad2[: max(2, min(len(rad2), 3 if corder[ci] else 4))]
                kidx = kidx[:len(pts2)]
            ids = [keep[k] for k in kidx]
            aw = ao[ids].copy()
            if spec.get("junction_dark") and cpar[ci] >= 0 and len(aw) > 1:
                aw[0] = min(aw[0], 0.3)
                aw[1] = min(aw[1], 0.55)
            if spec.get("base_dark"):
                bh, bv = spec["base_dark"]
                aw = np.minimum(aw, bv + (1 - bv) * np.clip(pts2[:len(ids), 2] / bh, 0, 1))
            wind = np.stack([sway[ids], np.zeros(len(ids)), np.full(len(ids), ph_chain[ci]), aw], -1)
            segs = tg.seg_count(rad2[0], segtab)
            flare = None
            if corder[ci] == 0 and spec.get("flare") and not spec.get("skip_order0"):
                fa, fh, lobes, la = spec["flare"]
                th0 = rng.uniform(0, 6.28)
                zs = pts2[:, 2]

                def flare(i, th, zs=zs, fa=fa, fh=fh, lobes=lobes, la=la, th0=th0):
                    e = math.exp(-max(zs[i], 0) / fh)
                    lob = max(0.0, math.cos(lobes * (th - th0))) ** 2
                    return 1 + fa * e * (1 + la * lob)
                # add extra flare rings near the ground for LOD0/1
                if lod < 2 and len(pts2) > 1:
                    z0 = pts2[0, 2]
                    extra = [z for z in (0.25, 0.6, 1.1) if z > z0 + 0.05 and z < pts2[1, 2] - 0.1]
                    if extra:
                        a, b = pts2[0], pts2[1]
                        ins = [a + (b - a) * ((z - a[2]) / (b[2] - a[2])) for z in extra]
                        rins = [rad2[0] + (rad2[1] - rad2[0]) * ((z - a[2]) / (b[2] - a[2])) for z in extra]
                        pts2 = np.vstack([pts2[:1], ins, pts2[1:]])
                        rad2 = np.concatenate([rad2[:1], rins, rad2[1:]])
                        wind = np.vstack([wind[:1], np.repeat(wind[:1], len(extra), 0), wind[1:]])
                        zs = pts2[:, 2]

                        def flare(i, th, zs=zs, fa=fa, fh=fh, lobes=lobes, la=la, th0=th0):
                            e = math.exp(-max(zs[i], 0) / fh)
                            lob = max(0.0, math.cos(lobes * (th - th0))) ** 2
                            return 1 + fa * e * (1 + la * lob)
            tg.tube(md, pts2, rad2, segs, mat, wind, uvmode, tile=spec.get("bark_tile", (1.4, 1.4)), flare=flare,
                    cap_tip=True, atlas_rect=rect)
        # surface roots
        if spec.get("roots") and lod < 2:
            nroot, rlen, rr = spec["roots"]
            rng2 = np.random.default_rng(spec.get("seed", 0) + 99)
            for k in range(nroot):
                th = 2 * np.pi * k / nroot + rng2.normal(0, 0.25)
                d = np.array([math.cos(th), math.sin(th), 0])
                ln = rlen * rng2.uniform(0.6, 1.2)
                p0 = np.array([0, 0, 1.0]) + d * spec["r_base"] * 0.7
                pts = _bezier(p0, p0 + d * ln * 0.45 + np.array([0, 0, -0.85]), p0 + d * ln + np.array([0, 0, -1.25]),
                              5 if lod == 0 else 3)
                rad = rr * np.linspace(1.0, 0.3, len(pts)) ** 0.8
                wind = np.zeros((len(pts), 4))
                wind[:, 3] = 0.8
                tg.tube(md, pts, rad, 6 if lod == 0 else 4, 0, wind, uvmode, tile=spec.get("bark_tile", (1.4, 1.4)),
                        atlas_rect=rect, cap_tip=False)

    # ---------------- leaf sites
    leafy = np.nonzero((tipd <= spec.get("leaf_tip_dist", 1.4)) & (R <= spec.get("leaf_r_max", 0.07)))[0]
    leafy = leafy[P[leafy, 2] > spec.get("leaf_z_min", 1.0)]
    rng.shuffle(leafy)
    from scipy.spatial import cKDTree
    acc = []
    dmin = spec.get("site_spacing", 0.45)
    if len(leafy):
        tree_pts = []
        for i in leafy:
            if tree_pts:
                if cKDTree(np.array(tree_pts)).query(P[i])[0] < dmin:
                    continue
            tree_pts.append(P[i])
            acc.append(i)
    acc = np.array(acc, int)
    res.info["leaf_sites"] = int(len(acc))

    puffs = spec.get("puffs")
    if puffs is not None and len(puffs):
        from scipy.spatial import cKDTree as _KD
        leafn = np.nonzero(R <= spec.get("leaf_r_max", 0.07) * 1.5)[0]
        kd = _KD(P[leafn])

    def make_puff_cards(n_target):
        cards = []
        pr = np.asarray(spec.get("puff_r", (1.3, 2.0)))
        radii = rng.uniform(pr[0], pr[1], len(puffs))
        share = radii ** 2 / (radii ** 2).sum()
        moods = spec["moods"]
        for pi, (pc, rc) in enumerate(zip(puffs, radii)):
            k = max(3, int(round(n_target * share[pi])))
            dd0, _ = kd.query(pc)
            if dd0 > spec.get("puff_max_gap", 1.7):
                continue
            tiles = _pick(rng, moods)
            for j in range(k):
                d = rng.normal(0, 1, 3)
                d[2] = abs(d[2]) * 0.9 + 0.15 if rng.random() < 0.8 else d[2]
                d = normalize(d)
                p = pc + d * rc * rng.uniform(0.3, 0.85)
                for _k in range(4):
                    if env.inside_depth(p[None])[0] > 0:
                        break
                    p = pc + (p - pc) * 0.6
                dd, ni = kd.query(p)
                node = leafn[ni]
                n = normalize(d * 0.85 + np.array([0, 0, 0.3]) + rng.normal(0, 0.18, 3))
                tile = tiles[rng.integers(len(tiles))]
                dense = rng.random() < spec.get("dense_frac", 0.0)
                if dense:
                    tile = spec["dense_map"].get(tile, tile)
                att = atlas.LAYOUT[tile]["attach"]
                upv = normalize(np.cross(n, rng.normal(0, 1, 3)))
                if att == "top":
                    upv = normalize(upv * 0.3 + np.array([0, 0, -1.0]))
                s = rng.uniform(*spec["card_size"]) * (spec.get("dense_scale", 1.25) if dense else 1.0)
                cw, chh = s * spec.get("card_w", 1.0), s * spec.get("card_h", 1.0)
                if att == "top":
                    c = p + np.array([0, 0, chh * 0.35])
                else:
                    c = p - upv * chh * 0.5
                ph = ph_chain[node_chain[node]]
                cards.append(dict(c=c, n=n, up=upv, w=cw, h=chh, tile=tile,
                                  wind=np.array([min(1.0, sway[node] + 0.08), 0, ph]),
                                  ao=float(np.clip(tg.crown_ao(p[None], env=env, floor=0.38)[0] * (0.72 + 0.28 * (d[2] + 1) / 2), 0.36, 1)),
                                  attach=att, flutter=(0.3, 1.0)))
        return cards

    def make_cards(n_target):
        cards = []
        if puffs is not None and len(puffs):
            nf = int(n_target * spec.get("puff_frac", 0.8))
            cards = make_puff_cards(nf)
            n_target = n_target - len(cards)
            if n_target <= 0:
                return cards[: max(1, nf)]
        if len(acc) == 0:
            return cards
        reps = int(math.ceil(n_target / len(acc)))
        sel = np.concatenate([rng.permutation(acc) for _ in range(reps)])[:n_target]
        moods = spec["moods"]
        chain_mood = {}
        for i in sel:
            ci = node_chain[i]
            # first-order ancestor chain -> colour mood (clumped colour variation)
            c0 = ci
            while cpar[c0] >= 0 and cpar[cpar[c0]] >= 0:
                c0 = cpar[c0]
            if c0 not in chain_mood:
                chain_mood[c0] = _pick(rng, moods)
            tiles = chain_mood[c0]
            tile = tiles[rng.integers(len(tiles))]
            p = P[i]
            par = parent[i] if parent[i] >= 0 else i
            bdir = normalize(P[i] - P[par]) if par != i else np.array([0, 0, 1.0])
            out = normalize(p - crown_c)
            side = rng.random() < spec.get("side_frac", 0.45)
            if side:
                n = normalize(out * 0.85 + np.array([0, 0, 0.35]) + rng.normal(0, 0.2, 3))
            else:
                n = normalize(out * 0.6 + np.array([0, 0, 0.65]) + rng.normal(0, 0.2, 3))
            att = atlas.LAYOUT[tile]["attach"]
            if att == "top":
                up = normalize(out * 0.5 + np.array([0, 0, -1.0]) * spec.get("hang", 0.8) + bdir * 0.2)
            else:
                up = normalize(bdir * 0.55 + out * 0.45 + np.array([0, 0, 0.25]))
            s = rng.uniform(*spec["card_size"])
            c = p - up * s * spec.get("card_back", 0.12)
            ph = ph_chain[node_chain[i]]
            cards.append(dict(c=c, n=n, up=up, w=s * spec.get("card_w", 1.0), h=s * spec.get("card_h", 1.0), tile=tile,
                              wind=np.array([min(1.0, sway[i] + 0.05), 0, ph]),
                              ao=float(ao[i]), attach=att, flutter=(0.3, 1.0)))
        return cards[:max(1, n_target + len(cards) - len(cards))] if False else cards

    budgets = spec["budget"]
    out = {}
    bark_frac = spec.get("bark_frac", (0.36, 0.3, 0.16))
    for lod in range(3):
        k = 1.0
        for _ in range(14):
            md = MeshData()
            bark(md, lod, k)
            bt = md.tris()
            if bt <= budgets[lod] * bark_frac[lod]:
                break
            k *= 1.22
        res.info[f"cull_k{lod}"] = round(k, 2)
        n_cards = max(8, (budgets[lod] - bt) // 2)
        if spec.get("foliage") == "none":
            out[lod] = md
            res.info[f"LOD{lod}"] = dict(tris=md.tris(), bark_tris=bt, cards=0)
            continue
        if spec.get("n_pads"):
            if lod == 0:
                PC, PR, PY, PN = pick_pads(P, R, tipd, env, spec, rng)
                acc_p = rng.random(len(PC)) < spec.get("accent_frac", 0.05)
                zr = (env.pmin[2], env.pmax[2])
                hull_c = (env.pmin + env.pmax) / 2
                hull_r = np.maximum((env.pmax - env.pmin) / 2, 0.5)
                res.pads = dict(C=PC, R=PR)
            if lod == 2 and len(PC) > spec.get("lod2_max_clumps", 24):
                kk = spec.get("lod2_max_clumps", 24)
                cent, lab = kmeans2(PC, kk, minit="++", seed=int(rng.integers(1 << 30)))
                C2, R2, Y2, N2, A2 = [], [], [], [], []
                for q in range(kk):
                    idq = np.nonzero(lab == q)[0]
                    if len(idq) == 0:
                        continue
                    c = PC[idq].mean(0)
                    ext = np.abs(PC[idq] - c).max(0)
                    rr = np.maximum(PR[idq].max(0), ext + PR[idq].mean(0) * 0.7)
                    C2.append(c); R2.append(rr); Y2.append(PY[idq[0]]); N2.append(PN[idq[0]]); A2.append(False)
                cards = pad_cards(np.array(C2), np.array(R2), np.array(Y2), np.array(N2), n_cards, lod, spec, rng, sway,
                                  ph_chain, node_chain, zr, np.array(A2))
            else:
                cards = pad_cards(PC, PR, PY, PN, n_cards, lod, spec, rng, sway, ph_chain, node_chain, zr, acc_p)
            emit_pad_cards(md, cards, hull_c, hull_r, 1 if lod == 0 else 0, zr, spec.get("k_clump", 0.7))
            out[lod] = md
            res.info[f"LOD{lod}"] = dict(tris=md.tris(), bark_tris=bt, cards=len(cards))
            continue
        if spec.get("n_clumps"):
            if lod == 0:
                CL, RL, NL = pick_clumps(P, R, tipd, env, spec, rng)
                acc_fl = rng.random(len(CL)) < spec.get("accent_frac", 0.1)
                zr = (env.pmin[2], env.pmax[2])
                hull_c = (env.pmin + env.pmax) / 2
                hull_r = np.maximum((env.pmax - env.pmin) / 2, 0.5)
                res.clumps = dict(C=CL, R=RL)
            if lod == 2 and len(CL) > spec.get("lod2_max_clumps", 24):
                kk = spec.get("lod2_max_clumps", 24)
                cent, lab = kmeans2(CL, kk, minit="++", seed=int(rng.integers(1 << 30)))
                C2, R2, N2, A2 = [], [], [], []
                for q in range(kk):
                    idq = np.nonzero(lab == q)[0]
                    if len(idq) == 0:
                        continue
                    c = CL[idq].mean(0)
                    r = max(np.max(np.linalg.norm(CL[idq] - c, axis=1) + RL[idq] * 0.8), RL[idq].max())
                    C2.append(c)
                    R2.append(r)
                    N2.append(NL[idq[0]])
                    A2.append(bool(acc_fl[idq].any()) and len(idq) == 1)
                cards = clump_cards(np.array(C2), np.array(R2), np.array(N2), n_cards, lod, spec, rng, sway, ph_chain,
                                    node_chain, zr, np.array(A2))
            else:
                cards = clump_cards(CL, RL, NL, n_cards, lod, spec, rng, sway, ph_chain, node_chain, zr, acc_fl)
            emit_clump_cards(md, cards, hull_c, hull_r, 1 if lod == 0 else 0, zr, spec.get("k_clump", 0.7))
        else:
            if lod == 0:
                cards0 = make_cards(n_cards)
                cards = cards0
            else:
                cards = tg.merge_cards(cards0, n_cards, spec["dense_map"], rng, size_gain=spec.get("merge_gain", 0.9),
                                       min_size=spec["card_size"][1] * (1.1 if lod == 1 else 1.6),
                                       max_size=spec["card_size"][1] * (2.6 if lod == 1 else 4.0))
            tg.emit_cards(md, cards, crown_c, mat=1 if lod == 0 else 0, sph=spec.get("sph", 0.65),
                          up_bias=spec.get("up_bias", 0.25))
        out[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris(), bark_tris=bt, cards=len(cards))
    res.lods = out
    res.crown_c = crown_c
    return res



# ============================================================================ clump crowns (spherified normals)

CLUMP_TILES = {
    "oak": {"light": ["oak_clump_light_a", "oak_clump_light_b"], "gold": ["oak_clump_gold_a", "oak_clump_gold_b"],
            "ochre": ["oak_clump_ochre_a", "oak_clump_ochre_b"], "dark": ["oak_clump_dark_a"], "red": ["oak_clump_red_a"]},
    "birch": {"light": ["birch_clump_light", "birch_clump_gold"], "gold": ["birch_clump_mid", "birch_clump_gold"],
              "ochre": ["birch_clump_mid"], "dark": ["birch_clump_dark"], "red": ["birch_clump_gold"]},
    "hollow": {"light": ["oak_clump_gold_b", "oak_clump_ochre_a"], "gold": ["oak_clump_ochre_a", "oak_clump_ochre_b"],
               "ochre": ["oak_clump_ochre_b", "oak_clump_red_a"], "dark": ["oak_clump_dark_a"], "red": ["oak_clump_red_a"]},
}
SUN = normalize(np.array([-0.45, -0.55, 0.0]))     # sun side (key light from front-left like the sheets)


def pick_clumps(P, R, tipd, env, spec, rng):
    """Clump centres at branch ends (FPS), radius per clump; returns (centres, radii, node ids)."""
    n = spec["n_clumps"]
    rlo, rhi = spec["clump_r"]
    if spec.get("clump_fill", True):
        # fill the crown shell evenly (overlapping cumulus), attach each clump to its nearest twig node
        dlo, dhi = spec.get("clump_depth", (0.45, 1.7))
        idx = np.argwhere(env.occ & (env.depth >= dlo) & (env.depth <= dhi))
        pts = env.lo + idx * env.voxel
        pts = pts[pts[:, 2] > spec.get("leaf_z_min", 1.0) + 0.3]
        if len(pts) > 8000:
            pts = pts[rng.choice(len(pts), 8000, replace=False)]
        sel = [int(np.argmax(pts[:, 2]))]
        dmin = np.linalg.norm(pts - pts[sel[0]], axis=1)
        for _ in range(n - 1):
            k = int(np.argmax(dmin))
            sel.append(k)
            dmin = np.minimum(dmin, np.linalg.norm(pts - pts[k], axis=1))
        C = pts[sel] + rng.uniform(-0.5, 0.5, (len(sel), 3)) * env.voxel
        twig = np.nonzero(R <= spec.get("leaf_r_max", 0.09) * 1.6)[0]
        _, nn = cKDTree(P[twig]).query(C)
        return C, rng.uniform(rlo, rhi, len(C)), twig[nn]
    depth = env.inside_depth(P)
    ok = (tipd <= spec.get("clump_tip", 1.8)) & (R <= spec.get("leaf_r_max", 0.09) * 1.6) & (depth > 0.3)
    ok &= P[:, 2] > spec.get("leaf_z_min", 1.0)
    ids = np.nonzero(ok)[0]
    if len(ids) < n:
        ids = np.nonzero((depth > 0.1) & (P[:, 2] > spec.get("leaf_z_min", 1.0)))[0]
    # prefer the outer shell: weight by closeness of depth to the target (~0.6 * mean radius)
    target = 0.6 * (rlo + rhi) / 2
    w = np.exp(-((depth[ids] - target) / max(target, 0.3)) ** 2)
    sel = [ids[int(np.argmax(w))]]
    dmin = np.linalg.norm(P[ids] - P[sel[0]], axis=1)
    for _ in range(n - 1):
        score = dmin * (0.35 + w)
        k = int(np.argmax(score))
        sel.append(ids[k])
        dmin = np.minimum(dmin, np.linalg.norm(P[ids] - P[ids[k]], axis=1))
    C = P[sel].copy()
    rad = rng.uniform(rlo, rhi, len(sel))
    # push centres so the clump surface meets the envelope surface (silhouette), never outside
    cc = env.centre.copy()
    for i in range(len(C)):
        d = C[i] - cc
        d[2] *= 0.6
        d = normalize(d)
        for _ in range(6):
            dep = env.inside_depth(C[i][None])[0]
            if dep > rad[i] * 0.75:
                C[i] = C[i] + d * 0.25
            elif dep < rad[i] * 0.45:
                C[i] = C[i] - d * 0.25
            else:
                break
    return C, rad, np.array(sel)


def clump_cards(C, rad, nodes, n_target, lod, spec, rng, sway, ph_chain, node_chain, zr, accent):
    """Cards on each clump ball; tile by position (light top/sun side -> dark underside); LODs share clumps."""
    tiles = CLUMP_TILES[spec.get("clump_kind", "oak")]
    area = rad ** 2
    share = area / area.sum()
    cards = []
    size_k = [1.0, 1.35, 2.0][lod]
    for k in range(len(C)):
        m = spec.get("lod2_cards", 4) if lod == 2 else max([5, 3][lod], int(round(n_target * share[k])))
        if lod == 2:
            a0 = rng.uniform(0, 2 * np.pi)
            nv = spec.get("lod2_cards", 4) - 1
            dirs = [np.array([0, 0, 1.0])] + [normalize(np.array([math.cos(a0 + j * 2 * np.pi / nv),
                                                                  math.sin(a0 + j * 2 * np.pi / nv), 0.3]))
                                               for j in range(nv)]
            dirs = [normalize(dd + rng.normal(0, 0.1, 3)) for dd in dirs]
        else:
            g = (1 + 5 ** 0.5) / 2
            rot = rng.uniform(0, 2 * np.pi)
            dirs = []
            i = 0
            while len(dirs) < m and i < 4 * m:
                z = 1 - 2 * (i + 0.5) / (1.35 * m)
                i += 1
                if z < -1:
                    break
                rr = math.sqrt(max(0, 1 - z * z))
                a = 2 * np.pi * i / g + rot
                dirs.append(normalize(np.array([rr * math.cos(a), rr * math.sin(a), z]) + rng.normal(0, 0.12, 3)))
        hk = (C[k][2] - zr[0]) / max(zr[1] - zr[0], 1e-3)
        node = nodes[k]
        for d in dirs:
            if accent[k]:
                cat = "red" if d[2] > 0.2 else "ochre" if d[2] > -0.3 else "dark"
            else:
                s = 0.6 * d[2] + 0.5 * (hk - 0.5) + 0.25 * float(np.dot(d, SUN)) + rng.normal(0, 0.12)
                cat = "light" if s > 0.30 else "gold" if s > -0.12 else "ochre" if s > -0.45 else "dark"
            tl = tiles[cat]
            tile = tl[rng.integers(len(tl))]
            sz = rad[k] * rng.uniform(1.0, 1.3) * size_k * spec.get("clump_card_k", 1.0)
            if lod < 2 and d[2] < -0.45 and rng.random() < 0.55:
                continue                                   # flatter cumulus underside, saves cards
            sq = np.array([1.0, 1.0, spec.get("clump_flat", 0.72)])
            if lod == 2:
                c = C[k] + d * sq * rad[k] * 0.15
            else:
                c = C[k] + d * sq * rad[k] * rng.uniform(0.35, 0.6)
            nrm = normalize(d + rng.normal(0, 0.18, 3)) if lod < 2 else d
            upv = normalize(np.cross(nrm, rng.normal(0, 1, 3)))
            cards.append(dict(c=c, n=nrm, up=upv, w=sz, h=sz, tile=tile, C=C[k], rad=rad[k], flat=sq[2],
                              wind=np.array([min(1.0, sway[node] + 0.06), 0, ph_chain[node_chain[node]]]),
                              hk=hk, attach="center"))
    return cards


def emit_clump_cards(md, cards, hull_c, hull_r, mat, zr, k_clump=0.7):
    """Quads with per-vertex spherified normals: 70% from the clump centre, 30% from the crown hull."""
    for cc in cards:
        n = normalize(cc["n"])
        t = normalize(cc["up"] - n * np.dot(cc["up"], n))
        b = normalize(np.cross(t, n))
        c = cc["c"]
        w, h = cc["w"], cc["h"]
        corners = np.array([c - b * w / 2 - t * h / 2, c + b * w / 2 - t * h / 2, c + b * w / 2 + t * h / 2,
                            c - b * w / 2 + t * h / 2])
        u0, v0, u1, v1 = atlas.uv_rect(cc["tile"])
        uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        nc = normalize((corners - cc["C"]) / np.array([1.0, 1.0, cc.get("flat", 1.0) ** 2]))
        nh = normalize((corners - hull_c) / (hull_r ** 2))
        nn = normalize(k_clump * nc + (1 - k_clump) * nh)
        col = np.zeros((4, 4))
        col[:, 0] = cc["wind"][0]
        dist = np.linalg.norm(corners - cc["C"], axis=1) / max(cc["rad"], 1e-3)
        col[:, 1] = np.clip(0.25 + 0.6 * dist, 0.25, 1.0)
        col[:, 2] = cc["wind"][2]
        hz = np.clip((corners[:, 2] - zr[0]) / max(zr[1] - zr[0], 1e-3), 0, 1)
        col[:, 3] = np.clip(0.58 + 0.27 * (0.5 + 0.5 * nn[:, 2]) + 0.15 * hz, 0.58, 1.0)
        md.add(corners, [(0, 1, 2, 3)], [uv], mat, col, normals=nn)

# ============================================================================ golden oak

OAK_MOODS_GOLD = [(6, ["oak_gold_a", "oak_gold_b", "oak_gold_a", "oak_amber_a"]),
                  (3, ["oak_amber_a", "oak_amber_b", "oak_gold_b"]),
                  (1.5, ["oak_orange_a", "oak_amber_b", "oak_orange_b"]),
                  (0.4, ["oak_green_a", "oak_gold_a", "oak_gold_b"])]
OAK_DENSE = {"oak_gold_a": "oak_dense_gold", "oak_gold_b": "oak_dense_gold", "oak_amber_a": "oak_dense_amber",
             "oak_amber_b": "oak_dense_amber", "oak_orange_a": "oak_dense_orange", "oak_orange_b": "oak_dense_orange",
             "oak_rust_a": "oak_dense_rust", "oak_rust_b": "oak_dense_rust", "oak_green_a": "oak_dense_gold"}


def oak_spec(seed, budget=(2950, 1150, 290), r_base=0.85, **kw):
    s = dict(bark="oak", r_base=r_base, alpha=1.0, gamma=2.25, cull=(0.045, 0.16, 0.35), max_order=[9, 2, 1],
             flare=(1.3, 1.1, 5, 1.0), roots=(6, 2.6, 0.55), card_size=(1.1, 1.5), moods=OAK_MOODS_GOLD,
             dense_frac=0.55, dense_scale=1.1, bark_frac=(0.42, 0.3, 0.16),
             n_clumps=46, clump_r=(1.35, 2.1), clump_kind="oak", accent_frac=0.05, clump_tip=1.8, clump_depth=(0.8, 2.1),
             dense_map=OAK_DENSE, budget=budget, leaf_tip_dist=1.6, leaf_r_max=0.09, site_spacing=0.42,
             side_frac=0.45, sph=0.62, up_bias=0.22, seed=seed, bark_tile=(1.5, 1.5), leaf_z_min=2.0)
    s.update(kw)
    return s


def build_golden_oak(variant, view=None):
    """v1: reference broad oak (hull of art/02 silhouette); v2: tall ovoid; v3: wind-swept two-leader;
    v4: young compact oak."""
    seed = {1: 101, 2: 202, 3: 303, 4: 404}[variant]
    rng = np.random.default_rng(seed)
    sk = tg.Skeleton()
    if variant == 1:
        env = tg.envelope_from_mask(view.mask, view.ppm, view.ay, view.ax, z_min=2.4, depth_scale=0.92, voxel=0.25)
        trunk = _subdiv([(0, 0, -0.3), (0.0, 0, 1.6), (0.08, 0.05, 3.2), (0.15, 0.0, 4.3)], 0.7)
        tid = sk.add_polyline(trunk, can_grow_from_z=3.6)
        limbs = [((-2.4, 0.4, 5.0), (-5.2, 0.5, 6.2)), ((-1.3, -0.6, 6.6), (-3.0, -1.2, 9.4)),
                 ((0.2, 0.3, 7.4), (0.3, 0.6, 11.4)), ((1.6, -0.3, 6.6), (3.6, -0.4, 9.6)),
                 ((2.6, 0.5, 5.2), (5.6, 0.8, 6.6)), ((0.3, 2.1, 6.0), (0.4, 4.6, 7.8)),
                 ((-0.5, -2.2, 5.8), (-0.8, -4.6, 7.4))]
        top = trunk[-1]
        for mid, end in limbs:
            pts = _bezier(top, mid, end, 7)
            sk.add_polyline(list(pts[1:]), parent=tid[-1], can_grow_from_z=4.0)
        puffs = env.sample_even(46, rng, dmin=0.9, dmax=1.9)
        att = env.sample(1700, rng, shell=2.3, inner_weight=0.12, clumps=puffs, clump_r=1.9)
        spec = oak_spec(seed, puffs=puffs, r_base=0.95, trunk_r=lambda p: 0.95 * (1.0 - 0.2 * min(p[2], 4.4) / 4.4), trunk_ids=tid)
        tg.space_colonize(sk, att, D=0.38, di=3.2, dk=0.85, iters=160, tropism=(0, 0, 1), trop_w=0.12, rng=rng)
    elif variant == 2:
        # tall ovoid crown, straight bole, crown base 3.5 m, 15 m tall
        env = tg.envelope_ellipsoid((0, 0, 9.3), (4.4, 4.2, 5.9), voxel=0.25,
                                    noise=lambda X, Y, Z: 0.10 * np.sin(1.3 * X + 0.7 * Z) * np.cos(1.1 * Y))
        trunk = _subdiv([(0, 0, -0.3), (0, 0, 2.5), (-0.1, 0.05, 5.0), (-0.15, 0, 6.2)], 0.7)
        tid = sk.add_polyline(trunk, can_grow_from_z=4.0)
        top = trunk[-1]
        for mid, end in [((-1.2, 0.3, 7.8), (-2.6, 0.5, 10.5)), ((1.0, -0.4, 8.0), (2.4, -0.6, 11.0)),
                         ((0.1, 0.2, 9.0), (0.0, 0.3, 13.6)), ((0.6, 1.3, 7.6), (1.0, 3.0, 9.6)),
                         ((-0.4, -1.4, 7.4), (-0.6, -3.0, 9.4))]:
            pts = _bezier(top, mid, end, 7)
            sk.add_polyline(list(pts[1:]), parent=tid[-1], can_grow_from_z=4.0)
        puffs = env.sample_even(30, rng, dmin=0.7, dmax=1.8)
        att = env.sample(1500, rng, shell=2.0, inner_weight=0.12, clumps=puffs, clump_r=1.7)
        spec = oak_spec(seed, puffs=puffs, r_base=0.62, trunk_r=lambda p: 0.62 * (1.0 - 0.2 * min(p[2], 6) / 6), roots=(5, 1.8, 0.3), trunk_ids=tid,
                        n_clumps=36, clump_r=(1.25, 1.95),
                        flare=(0.45, 0.8, 5, 0.5), crown_c_h=0.5)
        tg.space_colonize(sk, att, D=0.38, di=3.0, dk=0.85, iters=160, tropism=(0, 0, 1), trop_w=0.18, rng=rng)
    elif variant == 3:
        # wind-swept, two leaders, crown pushed to +X, low wide skirt on one side
        env1 = tg.envelope_ellipsoid((2.0, 0.3, 7.6), (5.6, 4.0, 3.6), voxel=0.25,
                                     noise=lambda X, Y, Z: 0.15 * np.sin(0.9 * X + 1.7 * Y) * np.cos(0.8 * Z))
        env2 = tg.envelope_ellipsoid((-2.6, -0.4, 9.6), (3.0, 3.0, 2.6), voxel=0.25)
        env = _union_env(env1, env2)
        trunk = _subdiv([(0, 0, -0.3), (0.1, 0, 1.8), (0.4, 0.05, 3.0)], 0.7)
        tid = sk.add_polyline(trunk, can_grow_from_z=2.6)
        top = trunk[-1]
        for mid, end in [((1.6, 0.2, 4.6), (4.5, 0.4, 6.4)), ((0.9, -0.2, 6.0), (2.6, -0.6, 9.8)),
                         ((-0.6, 0.0, 6.2), (-2.6, -0.4, 10.6)), ((0.4, 1.6, 5.2), (1.2, 3.6, 7.0)),
                         ((3.0, -0.8, 5.4), (6.8, -1.0, 6.4))]:
            pts = _bezier(top, mid, end, 8)
            sk.add_polyline(list(pts[1:]), parent=tid[-1], can_grow_from_z=3.0)
        puffs = env.sample_even(32, rng, dmin=0.7, dmax=1.8)
        att = env.sample(1600, rng, shell=2.2, inner_weight=0.12, clumps=puffs, clump_r=1.8)
        spec = oak_spec(seed, puffs=puffs, r_base=0.78, trunk_r=lambda p: 0.78 * (1 - 0.15 * min(p[2], 3) / 3), crown_c_h=0.4, trunk_ids=tid,
                        n_clumps=40, clump_r=(1.3, 2.0))
        tg.space_colonize(sk, att, D=0.38, di=3.2, dk=0.85, iters=160, tropism=(0.25, 0, 1), trop_w=0.12, rng=rng)
    else:
        # young compact oak, 8 m, round crown
        env = tg.envelope_ellipsoid((0, 0, 5.2), (3.4, 3.2, 2.9), voxel=0.2,
                                    noise=lambda X, Y, Z: 0.12 * np.sin(1.7 * X) * np.cos(1.9 * Y + Z))
        trunk = _subdiv([(0, 0, -0.2), (0.05, 0, 1.5), (0.1, 0.05, 2.6)], 0.6)
        tid = sk.add_polyline(trunk, can_grow_from_z=2.2)
        top = trunk[-1]
        for mid, end in [((-1.0, 0.2, 3.6), (-2.3, 0.4, 4.8)), ((0.9, -0.3, 3.8), (2.2, -0.5, 5.4)),
                         ((0.1, 0.1, 4.4), (0.2, 0.2, 7.2)), ((0.2, 1.1, 3.6), (0.4, 2.3, 5.0))]:
            pts = _bezier(top, mid, end, 6)
            sk.add_polyline(list(pts[1:]), parent=tid[-1], can_grow_from_z=2.4)
        puffs = env.sample_even(20, rng, dmin=0.7, dmax=1.8)
        att = env.sample(1000, rng, shell=1.6, inner_weight=0.15, clumps=puffs, clump_r=1.3)
        spec = oak_spec(seed, puffs=puffs, r_base=0.36, trunk_r=lambda p: 0.36 * (1 - 0.2 * min(p[2], 2.6) / 2.6), trunk_ids=tid,
                        roots=(5, 1.0, 0.14), flare=(0.4, 0.6, 5, 0.4), card_size=(1.0, 1.4),
                        cull=(0.03, 0.10, 0.2), budget=(2400, 950, 240), crown_c_h=0.45, leaf_z_min=1.6,
                        n_clumps=22, clump_r=(0.95, 1.4))
        tg.space_colonize(sk, att, D=0.3, di=2.4, dk=0.65, iters=150, tropism=(0, 0, 1), trop_w=0.12, rng=rng)
    res = finish_broadleaf(sk, env, spec, rng)
    res.env = env
    return res


def _union_env(e1, e2):
    lo = np.minimum(e1.lo, e2.lo)
    hi = np.maximum(e1.lo + np.array(e1.occ.shape) * e1.voxel, e2.lo + np.array(e2.occ.shape) * e2.voxel)
    vox = e1.voxel
    n = np.ceil((hi - lo) / vox).astype(int) + 1
    occ = np.zeros(n, bool)
    for e in (e1, e2):
        o = np.round((e.lo - lo) / vox).astype(int)
        s = e.occ.shape
        occ[o[0]:o[0] + s[0], o[1]:o[1] + s[1], o[2]:o[2] + s[2]] |= e.occ
    return tg.Envelope(occ, lo, vox)


# ============================================================================ conifer (spruce / pine)

def build_conifer(spec, rng):
    """Whorled conifer. spec: H, crown_base, r_base, profile(z)->branch length, droop, whorl_dz,
    per_whorl, budget, tiles, top_tiles, card sizes, missing (fraction of skipped branches)."""
    H = spec["H"]
    res = Result()
    trunk_pts = [np.array([0, 0, -0.3])]
    lean = np.asarray(spec.get("lean", (0, 0)), float)
    zs = np.linspace(0, H, int(H / 0.9) + 2)
    wob = spec.get("wobble", 0.05)
    ph1, ph2 = rng.uniform(0, 6.28, 2)
    for z in zs:
        f = min(1.0, z / 2.0)          # smooth low-frequency bends (no zig-zag)
        trunk_pts.append(np.array([lean[0] * z / H + wob * 2.2 * f * math.sin(z * 0.45 + ph1),
                                   lean[1] * z / H + wob * 2.2 * f * math.sin(z * 0.38 + ph2), z]))
    trunk_pts = np.array(trunk_pts)
    trunk_pts[-1, :2] = trunk_pts[-2, :2]
    rb = spec["r_base"]
    trunk_r = np.array([rb * max(0.02 / rb, (1 - max(p[2], 0) / H) ** 1.15) for p in trunk_pts])
    trunk_sway = np.clip(trunk_pts[:, 2] / H, 0, 1) ** 2.0 * spec.get("trunk_sway", 0.5)
    # whorls
    z = spec["crown_base"]
    whorls = []
    k = 0
    golden = 2.39996
    while z < H - 0.35:
        n = spec["per_whorl"] + rng.integers(-1, 2)
        frac = (z - spec["crown_base"]) / max(H - spec["crown_base"], 1e-3)
        whorl = []
        for j in range(n):
            if rng.random() < spec.get("missing", 0.0) * (1 - frac * 0.5):
                continue
            az = k * golden + j * 2 * np.pi / n + rng.normal(0, 0.25)
            Lb = spec["profile"](z, az) * rng.uniform(0.85, 1.12)
            if Lb < 0.25:
                continue
            whorl.append((az, Lb))
        whorls.append((z, frac, whorl))
        z += spec["whorl_dz"](frac) * rng.uniform(0.85, 1.15)
        k += 1
    branches = []
    for (z, frac, whorl) in whorls:
        ti = np.searchsorted(trunk_pts[:, 2], z)
        ti = min(max(ti, 1), len(trunk_pts) - 1)
        tz0, tz1 = trunk_pts[ti - 1, 2], trunk_pts[ti, 2]
        f = (z - tz0) / max(tz1 - tz0, 1e-6)
        base = trunk_pts[ti - 1] * (1 - f) + trunk_pts[ti] * f
        for az, Lb in whorl:
            d = np.array([math.cos(az), math.sin(az), 0])
            pitch = spec["pitch"](frac) + rng.normal(0, 0.06)
            droop = spec["droop"](frac)
            nseg = 4
            pts = []
            for s in range(nseg + 1):
                t = s / nseg
                horiz = d * Lb * t
                vert = Lb * (math.sin(pitch) * t - droop * t * t + spec.get("tip_up", 0.12) * max(0, t - 0.75) * 4 * t)
                pts.append(base + horiz + np.array([0, 0, vert]))
            pts = np.array(pts)
            rr = (0.018 + 0.05 * Lb / max(spec["Lmax"], 1e-3)) * spec.get("branch_r", 1.0)
            branches.append(dict(pts=pts, r=rr, L=Lb, z=z, frac=frac, az=az, phase=rng.random()))
    res.info["branches"] = len(branches)
    crown_c = np.array([0, 0, spec["crown_base"] + (H - spec["crown_base"]) * 0.4])
    crown_r = np.array([spec["Lmax"], spec["Lmax"], (H - spec["crown_base"]) * 0.6])

    def aof(p):
        return tg.crown_ao(np.atleast_2d(p), centre=crown_c, radii=crown_r,
                           zrange=(spec["crown_base"], H), floor=0.5)

    def bark(md, lod, stem_k=1.0):
        rect = atlas.uv_rect("bark_" + spec["bark"]) if lod > 0 else None
        mode = "tile" if lod == 0 else "atlas"
        segs = [9, 6, 5][lod]
        stride = [1, 2, 3][lod]
        tp = trunk_pts[::stride]
        if not np.allclose(tp[-1], trunk_pts[-1]):
            tp = np.vstack([tp, trunk_pts[-1]])
        tr = np.interp(tp[:, 2], trunk_pts[:, 2], trunk_r)
        ts = np.interp(tp[:, 2], trunk_pts[:, 2], trunk_sway)
        wind = np.stack([ts, np.zeros(len(tp)), np.zeros(len(tp)), aof(tp)], -1)
        fa = spec.get("flare", (0.5, 0.7, 6, 0.5))
        th0 = rng.uniform(0, 6)
        zz = tp[:, 2]

        def flare(i, th):
            e = math.exp(-max(zz[i], 0) / fa[1])
            return 1 + fa[0] * e * (1 + fa[3] * max(0, math.cos(fa[2] * (th - th0))) ** 2)
        if lod < 2:
            # extra rings near the base for the flare
            ins_z = [0.2, 0.5]
            pts2, r2, w2 = [tp[0]], [tr[0]], [wind[0]]
            for zz_ in ins_z:
                if zz_ < tp[1, 2]:
                    pts2.append(np.array([tp[0, 0], tp[0, 1], zz_]))
                    r2.append(np.interp(zz_, tp[:, 2], tr))
                    w2.append(wind[0])
            tp = np.vstack([pts2, tp[1:]])
            tr = np.concatenate([r2, tr[1:]])
            wind = np.vstack([w2, wind[1:]])
            zz = tp[:, 2]
        tg.tube(md, tp, tr, segs, 0, wind, mode, tile=spec.get("bark_tile", (1.0, 1.0)), flare=flare, atlas_rect=rect)
        # branch stems: only longer, lower branches get geometry
        lmin = spec.get("stem_min_L", [1.4, 2.4, 99][lod]) * stem_k
        for b in branches:
            if b["L"] < lmin or b["frac"] > [0.8, 0.6, 0][lod]:
                continue
            pts = b["pts"][::2]
            r = np.linspace(b["r"], b["r"] * 0.3, len(pts))
            sw = np.interp(pts[:, 2], trunk_pts[:, 2], trunk_sway) + np.linspace(0.15, 0.85, len(pts)) * 0.7
            w = np.stack([np.clip(sw, 0, 1), np.zeros(len(pts)), np.full(len(pts), b["phase"]), aof(pts)], -1)
            tg.tube(md, pts, r, 3 if lod == 0 else 3, 0, w, mode, tile=(0.6, 0.6), atlas_rect=rect, cap_tip=False)

    def spray_cards(n_target):
        """Needle sprays laid along branches + leader cards."""
        cards = []
        tiles = spec["tiles"]
        per = []
        for b in branches:
            L = b["L"]
            cnt = max(1, int(round(L / spec.get("spray_spacing", 0.75))))
            per.append(cnt)
        total = sum(per) + spec.get("leader_cards", 4)
        scale = n_target / max(total, 1)
        for b, cnt in zip(branches, per):
            pts = b["pts"]
            seglen = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            cum = np.concatenate([[0], np.cumsum(seglen)])
            m = max(1, int(round(cnt * scale)))
            for j in range(m):
                t = (j + 0.5) / m * 0.92 + 0.08 * rng.random() if m > 1 else 0.6
                s = t * cum[-1]
                i = min(np.searchsorted(cum, s) - 1, len(seglen) - 1)
                i = max(i, 0)
                f = (s - cum[i]) / max(seglen[i], 1e-6)
                p = pts[i] + (pts[i + 1] - pts[i]) * f
                bd = normalize(pts[i + 1] - pts[i])
                side = normalize(np.cross(bd, np.array([0, 0, 1.0])))
                roll = rng.normal(0, 0.35)
                n = normalize(np.array([0, 0, 1.0]) * math.cos(roll) + side * math.sin(roll) - bd * 0.15)
                w = rng.uniform(*spec["spray_w"]) * (0.65 + 0.35 * min(1, b["L"] / spec["Lmax"] * 1.5))
                h = w * rng.uniform(1.0, 1.25)
                c = p - bd * h * 0.35
                sw = float(np.interp(p[2], trunk_pts[:, 2], trunk_sway)) + 0.25 + 0.6 * t
                cards.append(dict(c=c, n=n, up=bd, w=w, h=h, tile=tiles[rng.integers(len(tiles))],
                                  wind=np.array([min(1, sw), 0, b["phase"]]), ao=float(aof(p)[0]), attach="bottom",
                                  flutter=(0.25, 0.8)))
                # vertical side spray for volume when seen from the side
                if rng.random() < spec.get("side_spray", 0.45):
                    n2 = normalize(side * (1 if rng.random() < 0.5 else -1) + np.array([0, 0, 0.2]))
                    cards.append(dict(c=c, n=n2, up=normalize(bd + np.array([0, 0, -0.55])), w=w * 0.85, h=h * 0.95,
                                      tile=tiles[rng.integers(len(tiles))], wind=np.array([min(1, sw), 0, b["phase"]]),
                                      ao=float(aof(p)[0]) * 0.95, attach="bottom", flutter=(0.25, 0.8)))
        # leader: crossed vertical sprays around the top
        ntop = spec.get("leader_cards", 4)
        for j in range(ntop):
            az = j * np.pi / ntop * 2 + rng.normal(0, 0.2)
            n = np.array([math.cos(az), math.sin(az), 0.15])
            hz = spec.get("leader_h", 1.6)
            c = np.array([trunk_pts[-1, 0], trunk_pts[-1, 1], H - hz])
            cards.append(dict(c=c, n=normalize(n), up=np.array([0, 0, 1.0]), w=hz * 0.55, h=hz, tile=spec["top_tile"],
                              wind=np.array([trunk_sway[-1], 0, 0.0]), ao=1.0, attach="bottom", flutter=(0.2, 0.6)))
        return cards

    out = {}
    budgets = spec["budget"]
    for lod in range(3):
        k = 1.0
        for _ in range(12):
            md = MeshData()
            bark(md, lod, k)
            bt = md.tris()
            if bt <= budgets[lod] * spec.get("bark_frac", (0.3, 0.25, 0.2))[lod]:
                break
            k *= 1.18
        n_cards = max(8, (budgets[lod] - bt) // 2)
        if lod == 0:
            cards0 = spray_cards(n_cards)
            if len(cards0) > n_cards:
                idx = rng.permutation(len(cards0))[:n_cards]
                cards0 = [cards0[i] for i in sorted(idx)]
            cards = cards0
        else:
            cards = tg.merge_cards(cards0, n_cards, spec["dense_map"], rng, size_gain=0.95,
                                   min_size=spec["spray_w"][1] * (1.2 if lod == 1 else 1.8),
                                   max_size=spec["spray_w"][1] * (2.4 if lod == 1 else 3.6))
            # merged conifer cards: alternate flat tiers (top camera) and outward-facing vertical cards (side)
            for j, c in enumerate(cards):
                if j % 2 == 0:
                    c["n"] = normalize(c["n"] * 0.5 + np.array([0, 0, 1.0]) * 0.5)
                else:
                    radial = c["c"] - np.array([trunk_pts[-1, 0], trunk_pts[-1, 1], c["c"][2]])
                    radial[2] = 0
                    c["n"] = normalize(normalize(radial) + np.array([0, 0, 0.25]))
                    c["up"] = np.array([0, 0, 1.0])
        tg.emit_cards(md, cards, crown_c, mat=1 if lod == 0 else 0, sph=spec.get("sph", 0.45), up_bias=0.3)
        out[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris(), bark_tris=bt, cards=len(cards))
    res.lods = out
    res.crown_c = crown_c
    return res


PINE_DENSE = {"pine_spray_a": "pine_dense_a", "pine_spray_b": "pine_dense_b", "pine_spray_c": "pine_dense_a",
              "pine_spray_d": "pine_dense_b", "pine_spray_e": "pine_dense_a", "pine_top": "pine_dense_a"}


def pine_profile_from_view(view, H):
    """Branch length per height from the reference silhouette half-widths (avg of both sides)."""
    m = view.mask
    rows = np.nonzero(m.any(axis=1))[0]
    zs, left, right = [], [], []
    for r in rows:
        cols = np.nonzero(m[r])[0]
        z = (view.ay - r) / view.ppm
        left.append(max(view.ax - cols.min(), 0) / view.ppm)
        right.append(max(cols.max() - view.ax, 0) / view.ppm)
        zs.append(z)
    zs = np.array(zs)
    o = np.argsort(zs)
    zs = zs[o]
    from scipy.ndimage import uniform_filter1d
    left = uniform_filter1d(np.array(left)[o], 7)
    right = uniform_filter1d(np.array(right)[o], 7)
    scale = H / zs.max()

    def prof(z, az):
        # +X (right in the front view) uses the right half-width, -X the left; depth (Y) the mean
        c = math.cos(az)
        wl = float(np.interp(z / scale, zs, left))
        wr = float(np.interp(z / scale, zs, right))
        wm = 0.5 * (wl + wr)
        return (wr * max(c, 0) + wl * max(-c, 0) + wm * (1 - abs(c))) * 0.95
    return prof


def build_dark_pine(variant, view=None):
    """v1: reference spruce (art/02 silhouette); v2: tall Scots-pine-like with high open crown;
    v3: young broad spruce with skirts to the ground; v4: old irregular pine, broken whorls, lean."""
    seed = {1: 111, 2: 222, 3: 333, 4: 444}[variant]
    rng = np.random.default_rng(seed)
    base = dict(bark="pine", tiles=["pine_spray_a", "pine_spray_b", "pine_spray_c", "pine_spray_d", "pine_spray_e"],
                top_tile="pine_spray_c", dense_map=PINE_DENSE, budget=(2900, 1150, 290), spray_w=(0.85, 1.15),
                bark_tile=(1.0, 1.0))
    if variant == 1:
        H = 14.0
        prof = pine_profile_from_view(view, H)
        spec = dict(base, H=H, crown_base=2.9, r_base=0.30, profile=prof, Lmax=3.6,
                    whorl_dz=lambda f: 0.62 - 0.30 * f, per_whorl=5,
                    pitch=lambda f: -0.22 + 0.85 * f ** 1.5, droop=lambda f: 0.20 * (1 - f) + 0.05,
                    tip_up=0.10, missing=0.05, flare=(0.55, 0.6, 6, 0.5), side_spray=0.6)
    elif variant == 2:
        H = 16.5
        def prof(z, az, H=H):
            f = (z - 7.0) / (H - 7.0)
            return max(0.0, 2.9 * math.sin(np.pi * min(max(f, 0), 1) ** 0.75) ** 0.8 + 0.5 * math.sin(3 * az + z)) \
                * (1.0 if f > 0 else 0)
        spec = dict(base, H=H, crown_base=7.0, r_base=0.27, profile=prof, Lmax=3.4,
                    whorl_dz=lambda f: 0.75 - 0.25 * f, per_whorl=4,
                    pitch=lambda f: 0.10 + 0.5 * f, droop=lambda f: 0.10, tip_up=0.25, missing=0.25,
                    spray_w=(0.95, 1.3), leader_cards=3, leader_h=1.2, top_tile="pine_spray_a", wobble=0.12)
    elif variant == 3:
        H = 8.5
        def prof(z, az, H=H):
            f = z / H
            return 3.1 * (1 - f) ** 0.95 + 0.15
        spec = dict(base, H=H, crown_base=0.35, r_base=0.19, profile=prof, Lmax=3.2,
                    whorl_dz=lambda f: 0.42 - 0.15 * f, per_whorl=6,
                    pitch=lambda f: -0.15 + 0.7 * f ** 1.4, droop=lambda f: 0.22 * (1 - f) + 0.03, tip_up=0.15,
                    missing=0.02, budget=(2600, 1050, 280), spray_w=(0.8, 1.05), flare=(0.3, 0.5, 6, 0.3))
    else:
        H = 13.0
        def prof(z, az, H=H):
            f = (z - 3.5) / (H - 3.5)
            if f < 0:
                return 0.0
            side = 1.0 + 0.45 * math.cos(az - 0.6)          # one-sided (wind-pruned)
            return (2.8 * (1 - f) ** 0.8 + 0.3) * side * (0.75 + 0.25 * math.sin(7 * z))
        spec = dict(base, H=H, crown_base=3.5, r_base=0.36, profile=prof, Lmax=3.8,
                    whorl_dz=lambda f: 0.7 - 0.2 * f, per_whorl=5, lean=(0.9, 0.3),
                    pitch=lambda f: -0.25 + 0.75 * f, droop=lambda f: 0.25 * (1 - f) + 0.05, tip_up=0.1,
                    missing=0.32, wobble=0.1, spray_w=(0.9, 1.2), flare=(0.45, 0.6, 5, 0.5))
    res = build_conifer(spec, rng)
    res.spec = spec
    return res


# ============================================================================ birch

BIRCH_MOODS = [(5, ["birch_a", "birch_b", "birch_a"]), (2, ["birch_yellow", "birch_a"]),
               (2, ["birch_c", "birch_green", "birch_b"])]
BIRCH_DENSE = {"birch_a": "birch_dense", "birch_b": "birch_dense", "birch_c": "birch_dense",
               "birch_yellow": "birch_dense", "birch_green": "birch_dense"}


def build_birch(variant, view=None):
    """v1: three-trunk cluster (art/02); v2: single slender birch; v3: two trunks in a V."""
    seed = {1: 121, 2: 232, 3: 343}[variant]
    rng = np.random.default_rng(seed)
    sk = tg.Skeleton()
    root = sk.add(np.array([0, 0, -0.3]), -1, fixed=True, can_grow=False)
    if variant == 1:
        env = tg.envelope_from_mask(view.mask, view.ppm, view.ay, view.ax, z_min=3.3, depth_scale=0.9, voxel=0.22)
        trunks = [[(0, 0, 0.0), (0.05, 0.0, 3.0), (0.15, 0.1, 6.0), (0.2, 0.1, 9.0), (0.25, 0.1, 11.5)],
                  [(-0.4, 0.15, 0.0), (-1.0, 0.25, 3.0), (-1.7, 0.35, 6.0), (-2.2, 0.4, 8.5)],
                  [(0.45, -0.15, 0.0), (1.2, -0.25, 3.0), (1.9, -0.3, 6.0), (2.4, -0.4, 8.6)]]
        spec_r = 0.20
    elif variant == 2:
        env = tg.envelope_ellipsoid((0.2, 0, 8.6), (2.6, 2.5, 4.4), voxel=0.22,
                                    noise=lambda X, Y, Z: 0.12 * np.sin(1.5 * X + Z) * np.cos(1.3 * Y))
        trunks = [[(0, 0, 0.0), (0.1, 0, 3.0), (0.25, 0.05, 6.5), (0.3, 0.05, 10.0), (0.35, 0.0, 12.8)]]
        spec_r = 0.19
    else:
        env1 = tg.envelope_ellipsoid((-2.1, 0.2, 8.0), (2.3, 2.2, 3.4), voxel=0.22)
        env2 = tg.envelope_ellipsoid((2.0, -0.2, 7.4), (2.2, 2.2, 3.2), voxel=0.22)
        env = _union_env(env1, env2)
        trunks = [[(-0.2, 0, 0.0), (-0.8, 0.05, 3.0), (-1.7, 0.1, 6.0), (-2.4, 0.2, 9.5)],
                  [(0.2, 0, 0.0), (0.9, -0.05, 3.0), (1.7, -0.1, 6.0), (2.3, -0.2, 9.0)]]
        spec_r = 0.18
    trunk_ids = [root]
    for tpts in trunks:
        pts = _subdiv(tpts, 0.6)
        trunk_ids += sk.add_polyline(pts, parent=root, can_grow_from_z=3.2 if variant != 2 else 4.0)
    puffs = env.sample_even(26, rng, dmin=0.7, dmax=1.8)
    att = env.sample(1300, rng, shell=1.6, inner_weight=0.18, clumps=puffs, clump_r=1.4)
    tg.space_colonize(sk, att, D=0.32, di=3.4, dk=0.6, iters=170, tropism=(0, 0, -1), trop_w=0.05, rng=rng)
    spec = dict(puffs=puffs, puff_r=(0.8, 1.3), puff_frac=0.45, bark="birch", n_clumps=0, junction_dark=True,
                clump_r=(0.7, 1.1), clump_kind="birch", accent_frac=0.15, clump_tip=1.4, lod2_cards=3, k_clump=0.55,
                clump_flat=0.62, clump_card_k=1.15,
                lod2_max_clumps=26,
                base_dark=(1.5, 0.2), r_base=spec_r * (1.6 if variant == 1 else 1.0), alpha=1.0, gamma=2.3,
                cull=(0.03, 0.08, 0.15), max_order=[9, 2, 1], flare=(0.25, 0.4, 4, 0.3), roots=None,
                card_size=(0.7, 1.0), moods=BIRCH_MOODS, dense_map=BIRCH_DENSE, budget=(3200, 1250, 290),
                leaf_tip_dist=1.6, leaf_r_max=0.05, site_spacing=0.3, side_frac=0.55, sph=0.6, up_bias=0.2,
                seed=seed, bark_tile=(1.5, 1.5), hang=1.0, leaf_z_min=3.5, bark_frac=(0.5, 0.36, 0.18),
                trunk_r=lambda p: spec_r * (1.0 - 0.55 * min(max(p[2], 0), 12) / 12), trunk_ids=trunk_ids)
    res = finish_broadleaf(sk, env, spec, rng)
    if variant == 1:   # small orange autumn shrub at the foot of the cluster (art/02)
        srng = np.random.default_rng(seed + 5)
        for lod, nc in ((0, 14), (1, 6), (2, 2)):
            cards = []
            for (cx, cy, cr) in ((-0.9, -0.5, 0.55), (0.5, -0.8, 0.45)):
                C = np.array([cx, cy, cr * 0.7])
                for j in range(nc // 2):
                    d = normalize(srng.normal(0, 1, 3) * np.array([1, 1, 0.6]) + np.array([0, 0, 0.5]))
                    sz = cr * srng.uniform(1.4, 1.8) * (1.0 if lod == 0 else 1.4)
                    nrm = normalize(d + srng.normal(0, 0.2, 3))
                    cards.append(dict(c=C + d * cr * 0.4, n=nrm, up=normalize(np.cross(nrm, srng.normal(0, 1, 3))), w=sz, h=sz,
                                      tile="shrub_orange", C=C, rad=cr, flat=0.8, wind=np.array([0.15, 0, srng.random()]),
                                      attach="center"))
            emit_clump_cards(res.lods[lod], cards, np.array([0, 0, 0.5]), np.array([1.0, 1.0, 0.6]),
                             1 if lod == 0 else 0, (0.0, 1.2))
            res.info[f"LOD{lod}"]["tris"] = res.lods[lod].tris()
    res.env = env
    return res


# ============================================================================ willow

def build_willow(variant, view=None):
    """Bent leaning trunk, arching limbs, dome of hanging foliage + long curtain strips.
    v1: art/02 reference (lean to +X); v2: mirrored, broader & lower; v3: young upright willow."""
    seed = {1: 131, 2: 242, 3: 353}[variant]
    rng = np.random.default_rng(seed)
    sk = tg.Skeleton()
    mir = -1.0 if variant == 2 else 1.0
    if variant == 1:
        env = tg.envelope_from_mask(view.mask, view.ppm, view.ay, view.ax, z_min=4.0, depth_scale=0.9, voxel=0.25,
                                    row_lo=int(view.ay - 6.0 * view.ppm))
        trunk = [(-0.4, 0, -0.3), (-0.35, 0, 1.0), (0.1, 0.0, 2.2), (0.9, 0.05, 3.3), (1.5, 0.1, 4.4), (1.8, 0.1, 5.4)]
        hem = 1.8
        rb = 0.62
        limbs = [((0.6, 0.2, 6.6), (-1.2, 0.4, 8.6)), ((2.4, -0.3, 6.8), (2.8, -0.6, 9.8)),
                 ((2.8, 0.3, 6.0), (4.6, 0.6, 7.6)), ((1.2, 1.4, 6.2), (1.4, 3.0, 7.8)),
                 ((1.4, -1.5, 6.4), (1.6, -3.2, 8.2)), ((0.0, 0.4, 6.4), (-3.6, 0.6, 7.6)),
                 ((0.2, -0.8, 6.2), (-3.0, -2.2, 7.2)), ((-0.4, 0.6, 7.4), (-4.4, 1.0, 8.2))]
    elif variant == 2:
        env = tg.envelope_ellipsoid((-1.2, 0, 6.0), (5.6, 4.6, 2.9), voxel=0.25,
                                    noise=lambda X, Y, Z: 0.12 * np.sin(1.1 * X + 0.6 * Y) * np.cos(0.9 * Z))
        trunk = [(0.3, 0, -0.3), (0.25, 0, 1.0), (-0.3, 0.0, 2.0), (-0.9, 0.05, 3.0), (-1.3, 0.1, 3.8)]
        hem = 1.8
        rb = 0.70
        limbs = [((-2.6, 0.2, 5.0), (-5.0, 0.4, 6.4)), ((0.6, -0.2, 5.4), (2.8, -0.5, 7.0)),
                 ((-1.4, 0.1, 6.0), (-1.2, 0.2, 8.4)), ((-1.0, 1.8, 5.0), (-1.2, 3.6, 6.4)),
                 ((-1.0, -1.8, 5.0), (-1.2, -3.6, 6.2))]
    else:
        env = tg.envelope_ellipsoid((0.2, 0, 6.2), (3.2, 3.0, 2.8), voxel=0.22)
        trunk = [(0, 0, -0.3), (0.05, 0, 1.5), (0.2, 0.0, 3.0), (0.3, 0.05, 4.0)]
        hem = 1.8
        rb = 0.36
        limbs = [((-0.8, 0.2, 5.2), (-2.0, 0.3, 6.6)), ((1.2, -0.2, 5.4), (2.4, -0.4, 6.8)),
                 ((0.3, 0.1, 5.8), (0.4, 0.2, 8.4)), ((0.4, 1.2, 5.0), (0.5, 2.4, 6.4))]
    trunk = _subdiv(trunk, 0.6)
    tid = sk.add_polyline(trunk, can_grow_from_z=3.6 if variant != 3 else 3.0)
    top = trunk[-1]
    for mid, end in limbs:
        pts = _bezier(top, mid, end, 7)
        sk.add_polyline(list(pts[1:]), parent=tid[-1], can_grow_from_z=3.5)
    puffs = env.sample_even(26, rng, dmin=0.7, dmax=1.8)
    att = env.sample(1300, rng, shell=1.6, inner_weight=0.1, clumps=puffs, clump_r=1.5)
    tg.space_colonize(sk, att, D=0.36, di=3.6, dk=0.8, iters=150, tropism=(0, 0, 1), trop_w=0.1, rng=rng)
    W_TILES = [f"willow_strand_{k}" for k in range(6)]
    spec = dict(puffs=puffs, puff_r=(1.2, 1.8), puff_frac=0.75, bark="willow", r_base=rb, alpha=1.0, gamma=2.3, cull=(0.04, 0.12, 0.28), max_order=[9, 2, 1],
                flare=(0.45, 0.7, 4, 0.6), roots=(5, 1.6, rb * 0.35), card_size=(1.2, 1.6),
                moods=[(1, W_TILES)], dense_map={**{f"willow_strand_{k}": "willow_dense" for k in range(6)},
                                                 "willow_top_a": "willow_dense"}, budget=(3300, 1300, 295),
                card_w=0.42, card_h=1.9,
                leaf_tip_dist=1.2, leaf_r_max=0.06, site_spacing=0.55, side_frac=0.3, sph=0.6, up_bias=0.2,
                seed=seed, bark_tile=(1.3, 1.3), hang=0.6, leaf_z_min=3.0,
                trunk_r=lambda p: rb * (1 - 0.25 * min(max(p[2], 0), 5) / 5), trunk_ids=tid)
    # bark only from finish_broadleaf; foliage = weeping curtains along arching branch curves (below)
    spec["foliage"] = "none"
    spec["bark_frac"] = (0.24, 0.2, 0.12)
    res = finish_broadleaf(sk, env, spec, rng)
    res.env = env
    P, parent, R = res.skel["P"], res.skel["parent"], res.skel["R"]
    ch = tg.children_lists(parent)
    L = tg.path_lengths(P, parent)
    sway = np.clip((L - 0.4) / max(L.max() - 0.4, 1e-3), 0, 1) ** 1.35
    rng2 = np.random.default_rng(seed + 7)
    trunk_top = np.array(trunk[-1], float)
    zr = (env.pmin[2], env.pmax[2])
    dome_c = np.array([(env.pmin[0] + env.pmax[0]) / 2, (env.pmin[1] + env.pmax[1]) / 2, hem + 0.45 * (env.pmax[2] - hem)])
    # arc start nodes: outer upper skeleton nodes (FPS)
    rad_xy = np.linalg.norm(P[:, :2] - trunk_top[:2], axis=1)
    cand = np.nonzero((P[:, 2] > hem + 2.0) & (rad_xy > 0.6) & (R < 0.08))[0]
    n_arcs = {1: 52, 2: 52, 3: 34}[variant]
    sel = [cand[int(np.argmax(P[cand, 2]))]]
    dmin = np.linalg.norm(P[cand] - P[sel[0]], axis=1)
    for _ in range(min(n_arcs, len(cand)) - 1):
        k = int(np.argmax(dmin))
        sel.append(cand[k])
        dmin = np.minimum(dmin, np.linalg.norm(P[cand] - P[cand[k]], axis=1))
    arcs = []
    for i in sel:
        S = P[i]
        o = S - dome_c
        o[2] = 0
        o = normalize(o + rng2.normal(0, 0.25, 3) * np.array([1, 1, 0]))
        ln = rng2.uniform(1.6, 2.6)
        A = S + o * ln * 0.35 + np.array([0, 0, 0.45])
        E = S + o * ln + np.array([0, 0, -0.5])
        arcs.append((_bezier(S, A, E, 9), i, rng2.random()))
    W_STR = [f"willow_strand_{k}" for k in range(6)]

    def strand(md, top, out, width, nseg, node, ph, mat):
        hz = hem * rng2.uniform(0.35, 0.75)
        length = max(0.8, top[2] - hz)
        u0, v0, u1, v1 = atlas.uv_rect(W_STR[rng2.integers(6)])
        side = normalize(np.cross(out, np.array([0, 0, 1.0])))
        verts, uvs, cols, nrms = [], [], [], []
        for k in range(nseg + 1):
            tt = k / nseg
            c = top + out * 0.18 * math.sin(np.pi * tt * 0.7) + np.array([0, 0, -length * tt])
            for sgn in (-1, 1):
                v = c + side * sgn * width * 0.5
                verts.append(v)
                uvs.append((u0 if sgn < 0 else u1, v1 - (v1 - v0) * tt))
                nrm = normalize(0.7 * normalize(v - dome_c) + 0.3 * normalize(out + np.array([0, 0, 0.2])))
                nrms.append(nrm)
                hzf = np.clip((v[2] - hz) / max(zr[1] - hz, 1e-3), 0, 1)
                cols.append([min(1, sway[node] + 0.15 + 0.35 * tt), 0.25 + 0.75 * tt, ph,
                             float(np.clip(0.45 + 0.35 * hzf + 0.2 * (0.5 + 0.5 * np.dot(nrm, SUN)), 0.45, 1))])
        faces, fuv = [], []
        for k in range(nseg):
            a = 2 * k
            faces.append((a, a + 1, a + 3, a + 2))
            fuv.append([uvs[a], uvs[a + 1], uvs[a + 3], uvs[a + 2]])
        md.add(np.array(verts), faces, fuv, mat, np.array(cols), normals=np.array(nrms))

    for lod in range(3):
        md = res.lods[lod]
        mat = 1 if lod == 0 else 0
        step = [0.34, 0.6, 1.9][lod]
        nseg = [3, 2, 1][lod]
        wk = [1.0, 1.5, 2.6][lod]
        cards = []
        for arc, node, ph in arcs:
            seg = np.linalg.norm(np.diff(arc, axis=0), axis=1)
            cum = np.concatenate([[0], np.cumsum(seg)])
            s = rng2.uniform(0, step)
            while s < cum[-1]:
                j = min(np.searchsorted(cum, s) - 1, len(seg) - 1)
                j = max(j, 0)
                p = arc[j] + (arc[j + 1] - arc[j]) * (s - cum[j]) / max(seg[j], 1e-6)
                out = p - dome_c
                out[2] = 0
                strand(md, p, normalize(out), rng2.uniform(0.40, 0.55) * wk, nseg, node, ph, mat)
                s += step * rng2.uniform(0.8, 1.2)
            # drape cards over the arch (read from the top camera)
            nd = [5, 3, 1][lod]
            for q in range(nd):
                tt = (q + 0.5) / nd * 0.75
                j = int(tt * (len(arc) - 1))
                p = arc[j]
                tang = normalize(arc[min(j + 1, len(arc) - 1)] - arc[max(j - 1, 0)])
                out = p - dome_c
                nrm = normalize(np.cross(tang, normalize(np.cross(np.array([0, 0, 1.0]), tang))) + normalize(out) * 0.3)
                if nrm[2] < 0:
                    nrm = -nrm
                sz = rng2.uniform(0.9, 1.25) * [1.0, 1.35, 2.0][lod]
                cards.append(dict(c=p - tang * sz * 0.1, n=nrm, up=tang, w=sz * 0.8, h=sz, tile="willow_top_a", C=dome_c,
                                  rad=float(np.linalg.norm(p - dome_c)), flat=1.0,
                                  wind=np.array([min(1, sway[node] + 0.1), 0, ph]), attach="center"))
        emit_clump_cards(md, cards, dome_c, np.maximum((env.pmax - env.pmin) / 2, 0.5), mat, zr, 0.5)
        res.info[f"LOD{lod}"]["tris"] = md.tris()
        res.info[f"LOD{lod}"]["arcs"] = len(arcs)
    return res


# ============================================================================ conifer v2: regular drooping fan tiers

def build_conifer2(spec, rng):
    """Straight trunk, regular whorls of drooping branch FANS (needle cards along each branch, widening to the
    tip, plus a hanging tip skirt); spherified normals (70% fan centre below the branch, 30% cone hull);
    LOD1 = one fan + skirt per branch, LOD2 = tier petals (6 drooping cards per tier) -> same tiles/colours."""
    H, cb = spec["H"], spec["crown_base"]
    res = Result()
    lean = np.asarray(spec.get("lean", (0.0, 0.0)), float)
    zs = np.concatenate([[-0.3, 0.2, 0.5], np.linspace(1.0, H, int(H / 0.8) + 1)])
    trunk_pts = np.array([[lean[0] * max(z, 0) / H, lean[1] * max(z, 0) / H, z] for z in zs])
    rb = spec["r_base"]
    trunk_r = rb * np.maximum(0.04, 1 - np.clip(zs, 0, None) / H) ** 1.1
    trunk_sway = np.clip(zs / H, 0, 1) ** 2 * 0.5
    axis_at = lambda z: np.array([lean[0] * z / H, lean[1] * z / H, z])
    Wmax = spec["Lmax"]
    branches = []
    z, k = cb, 0
    while z < H - 0.45:
        f = (z - cb) / max(H - cb, 1e-3)
        n = spec["per_whorl"]
        for j in range(n):
            if rng.random() < spec.get("missing", 0.02):
                continue
            az = k * 2.39996 + j * 2 * np.pi / n + rng.normal(0, 0.12)
            Lb = spec["profile"](z, az) * rng.uniform(0.92, 1.08)
            if Lb < 0.3:
                continue
            d = np.array([math.cos(az), math.sin(az), 0.0])
            pitch = spec["pitch"](f)
            droop = spec["droop"](f) * (0.6 + 0.4 * Lb / Wmax)
            pts = []
            for s in range(6):
                t = s / 5
                pts.append(axis_at(z) + d * Lb * t + np.array([0, 0, Lb * (math.sin(pitch) * t - droop * t * t)]))
            branches.append(dict(pts=np.array(pts), L=Lb, z=z, f=f, az=az, phase=rng.random(), d=d))
        z += spec["whorl_dz"](f) * rng.uniform(0.93, 1.07)
        k += 1
    res.info["branches"] = len(branches)
    tiles = spec["tiles"]
    cone_k = Wmax / max(H - cb, 1.0)

    def hull_n(v):
        ax = axis_at(v[2])
        rad = v - ax
        rad[2] = 0
        return normalize(normalize(rad) + np.array([0, 0, cone_k + 0.25]))

    def emit(md, cards, mat):
        for c in cards:
            n = normalize(c["n"])
            t = normalize(c["up"] - n * np.dot(c["up"], n))
            b = normalize(np.cross(t, n))
            p0 = c["c"]
            w, h = c["w"], c["h"]
            corners = np.array([p0 - b * w / 2, p0 + b * w / 2, p0 + b * w / 2 + t * h, p0 - b * w / 2 + t * h])
            if c.get("fold"):
                corners[2:] += np.array([0, 0, -c["fold"] * h])
            u0, v0, u1, v1 = atlas.uv_rect(c["tile"])
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            nn = np.array([normalize(0.7 * normalize(q - c["fc"]) + 0.3 * hull_n(q)) for q in corners])
            col = np.zeros((4, 4))
            col[:, 0] = [c["sw0"], c["sw0"], c["sw1"], c["sw1"]]
            col[:, 1] = [0.2, 0.2, 0.85, 0.85]
            col[:, 2] = c["phase"]
            hz = np.clip((corners[:, 2] - cb) / max(H - cb, 1e-3), 0, 1)
            col[:, 3] = np.clip(0.42 + 0.22 * np.array([c["t0"], c["t0"], c["t1"], c["t1"]]) + 0.36 * hz, 0.42, 1.0)
            md.add(corners, [(0, 1, 2, 3)], [uv], mat, col, normals=nn)

    def fan_cards(lod, layers):
        cards = []
        for b in branches:
            pts, L = b["pts"], b["L"]
            sw_base = float(np.interp(b["z"], zs, trunk_sway))
            side = normalize(np.cross(b["d"], np.array([0, 0, 1.0])))
            m = 1 if lod == 1 else max(1, min(4, int(round(L / 0.85))))
            for lay in range(layers):
                roll = (lay - (layers - 1) / 2) * 0.35 + rng.normal(0, 0.08)
                for j in range(m):
                    t0 = j / m * 0.85
                    t1 = min(1.0, (j + 1) / m + 0.12)
                    i0 = t0 * 5
                    pa = pts[int(i0)] + (pts[min(int(i0) + 1, 5)] - pts[int(i0)]) * (i0 - int(i0))
                    i1 = t1 * 5
                    pb = pts[min(int(i1), 5)] + (pts[min(int(i1) + 1, 5)] - pts[min(int(i1), 5)]) * (i1 - int(i1))
                    tang = normalize(pb - pa)
                    nrm = normalize(np.cross(side, tang))
                    nrm = normalize(nrm * math.cos(roll) + side * math.sin(roll))
                    if nrm[2] < 0:
                        nrm = -nrm
                    width = L * (0.32 + 0.45 * t1) * spec.get("fan_w", 1.0)
                    length = np.linalg.norm(pb - pa) * 1.15
                    fc = (pa + pb) / 2 - np.array([0, 0, 0.35 + 0.25 * L])
                    tile = tiles[rng.integers(len(tiles))]
                    cards.append(dict(c=pa, n=nrm, up=tang, w=max(0.45, width), h=max(0.5, length), tile=tile, fc=fc,
                                      sw0=min(1, sw_base + 0.15 + 0.6 * t0), sw1=min(1, sw_base + 0.15 + 0.6 * t1),
                                      phase=b["phase"], t0=t0, t1=t1, fold=0.12))
            if L > spec.get("skirt_min", 1.0):
                tip = pts[-1]
                down = normalize(b["d"] * 0.35 + np.array([0, 0, -1.0]))
                nrm = normalize(np.cross(side, down))
                if np.dot(nrm, b["d"]) < 0:
                    nrm = -nrm
                hh = min(1.2, 0.35 + 0.3 * L) * (1.3 if lod else 1.0)
                cards.append(dict(c=tip - down * 0.1, n=nrm, up=down, w=0.55 * hh + 0.25, h=hh,
                                  tile=tiles[rng.integers(len(tiles))], fc=tip - np.array([0, 0, 0.6]) - b["d"] * 0.4,
                                  sw0=min(1, sw_base + 0.8), sw1=min(1, sw_base + 0.95), phase=b["phase"], t0=0.9, t1=1.0))
        return cards

    def leader_cards(lod):
        cards = []
        hz = spec.get("leader_h", 1.8)
        top = axis_at(H)
        for j in range(4 if lod == 0 else 2):
            az = j * np.pi / (4 if lod == 0 else 2) + 0.3
            n = np.array([math.cos(az), math.sin(az), 0.1])
            cards.append(dict(c=top - np.array([0, 0, hz]), n=normalize(n), up=np.array([0, 0, 1.0]), w=hz * 0.42, h=hz + 0.25,
                              tile=tiles[j % len(tiles)], fc=top - np.array([0, 0, hz * 1.2]), sw0=0.5, sw1=0.6, phase=0.0,
                              t0=0.8, t1=1.0))
        return cards

    def tier_cards():
        cards = []
        zt = np.linspace(cb, H - 0.6, spec.get("lod2_tiers", 10))
        for i, z in enumerate(zt):
            L = spec["profile"](z, 0.0) * 1.02
            f = (z - cb) / max(H - cb, 1e-3)
            for j in range(8):
                az = j * np.pi / 4 + i * 0.4
                d = np.array([math.cos(az), math.sin(az), 0])
                tang = normalize(d + np.array([0, 0, -0.35 - 0.3 * (1 - f)]))
                side = normalize(np.cross(d, np.array([0, 0, 1.0])))
                nrm = normalize(np.cross(side, tang))
                if nrm[2] < 0:
                    nrm = -nrm
                base = axis_at(z + 0.25)
                cards.append(dict(c=base, n=nrm, up=tang, w=max(0.6, L * 0.85), h=max(0.6, L * 1.05),
                                  tile=spec.get("lod2_tile", "pine_dense_a"), fc=base + d * L * 0.5 - np.array([0, 0, 0.8]),
                                  sw0=float(np.interp(z, zs, trunk_sway)) + 0.1, sw1=0.9, phase=(i * 0.13) % 1, t0=0.2,
                                  t1=1.0, fold=0.08))
        return cards

    def bark(md, lod, stem_k=1.0):
        rect = atlas.uv_rect("bark_" + spec["bark"]) if lod > 0 else None
        mode = "tile" if lod == 0 else "atlas"
        segs = [9, 6, 5][lod]
        stride = [1, 2, 3][lod]
        tp = trunk_pts[::stride]
        if not np.allclose(tp[-1], trunk_pts[-1]):
            tp = np.vstack([tp, trunk_pts[-1]])
        tr = np.interp(tp[:, 2], trunk_pts[:, 2], trunk_r)
        ts = np.interp(tp[:, 2], trunk_pts[:, 2], trunk_sway)
        ao = np.clip(0.5 + 0.5 * np.clip(tp[:, 2] / H, 0, 1), 0.5, 1.0)
        wind = np.stack([ts, np.zeros(len(tp)), np.zeros(len(tp)), ao], -1)
        fa = spec.get("flare", (0.5, 0.6, 6, 0.5))
        th0 = rng.uniform(0, 6)
        zz = tp[:, 2]

        def flare(i, th):
            e = math.exp(-max(zz[i], 0) / fa[1])
            return 1 + fa[0] * e * (1 + fa[3] * max(0, math.cos(fa[2] * (th - th0))) ** 2)
        tg.tube(md, tp, tr, segs, 0, wind, mode, tile=spec.get("bark_tile", (1.0, 1.0)), flare=flare, atlas_rect=rect)
        if lod == 0:
            for b in branches:
                if b["L"] < spec.get("stem_min_L", 1.5) * stem_k:
                    continue
                pts = b["pts"][::2]
                r = np.linspace(0.02 + 0.03 * b["L"] / Wmax, 0.01, len(pts))
                w = np.stack([np.linspace(0.2, 0.9, len(pts)), np.zeros(len(pts)), np.full(len(pts), b["phase"]),
                              np.full(len(pts), 0.6)], -1)
                tg.tube(md, pts, r, 3, 0, w, mode, tile=(0.6, 0.6), atlas_rect=rect, cap_tip=False)

    budgets = spec["budget"]
    for lod in range(3):
        k_ = 1.0
        for _ in range(10):
            md = MeshData()
            bark(md, lod, k_)
            bt = md.tris()
            if bt <= budgets[lod] * 0.25:
                break
            k_ *= 1.25
        if lod == 2:
            cards = tier_cards()
        else:
            room = (budgets[lod] - bt) // 2
            layers = 1
            while len(fan_cards(lod, layers + 1)) <= room and layers < 3:
                layers += 1
            cards = fan_cards(lod, layers) + leader_cards(lod)
            if len(cards) > room:
                idx = np.sort(rng.permutation(len(cards))[:room])
                cards = [cards[i] for i in idx]
        emit(md, cards, 1 if lod == 0 else 0)
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris(), bark_tris=bt, cards=len(cards))
    res.crown_c = np.array([0, 0, cb + (H - cb) * 0.4])
    return res


def build_dark_pine2(variant, view=None):
    """v1: art/02 spruce spire (silhouette profile); v2: tall narrow spire; v3: young broad spruce to the ground;
    v4: old spruce, slight lean, a few broken whorls."""
    seed = {1: 111, 2: 222, 3: 333, 4: 444}[variant]
    rng = np.random.default_rng(seed)
    base = dict(bark="pine", tiles=["pine_spray_a", "pine_spray_b", "pine_spray_c", "pine_spray_d", "pine_spray_e"],
                budget=(2900, 1150, 290), bark_tile=(1.0, 1.0), per_whorl=6, missing=0.02)
    cone = lambda H, cb, W, p=1.0: (lambda z, az: max(0.0, W * ((H - z) / (H - cb)) ** p) if z >= cb else 0.0)
    if variant == 1:
        H = 14.0
        prof_ref = pine_profile_from_view(view, H)
        # silhouette widths are measured at the drooped tip height -> look the profile up ~0.6 m lower
        prof = lambda z, az: (0.75 * prof_ref(max(z - 0.6, 0.0), az) + 0.25 * cone(H, 2.6, 3.3, 0.95)(z, az)) * \
            (0.8 if z < 4.0 else 1.0)
        spec = dict(base, H=H, crown_base=3.3, r_base=0.32, profile=prof, Lmax=3.5, fan_w=0.85, leader_h=2.2,
                    whorl_dz=lambda f: 0.55 - 0.25 * f, pitch=lambda f: -0.02 + 0.5 * f ** 1.5,
                    droop=lambda f: 0.30 * (1 - f) + 0.10, flare=(0.55, 0.6, 6, 0.5))
    elif variant == 2:
        H = 16.5
        spec = dict(base, H=H, crown_base=3.4, r_base=0.30, profile=cone(H, 3.4, 3.0, 1.05), Lmax=3.0,
                    whorl_dz=lambda f: 0.6 - 0.25 * f, pitch=lambda f: -0.08 + 0.5 * f ** 1.5,
                    droop=lambda f: 0.5 * (1 - f) + 0.12, flare=(0.5, 0.6, 6, 0.5))
    elif variant == 3:
        H = 8.5
        spec = dict(base, H=H, crown_base=0.35, r_base=0.2, profile=cone(H, 0.35, 3.1, 0.95), Lmax=3.1,
                    whorl_dz=lambda f: 0.42 - 0.15 * f, pitch=lambda f: -0.02 + 0.45 * f ** 1.4,
                    droop=lambda f: 0.36 * (1 - f) + 0.1, flare=(0.3, 0.5, 6, 0.3), budget=(2600, 1050, 280))
    else:
        H = 13.0
        spec = dict(base, H=H, crown_base=3.0, r_base=0.36, profile=cone(H, 3.0, 3.6, 0.9), Lmax=3.6,
                    whorl_dz=lambda f: 0.62 - 0.25 * f, pitch=lambda f: -0.08 + 0.5 * f ** 1.5,
                    droop=lambda f: 0.45 * (1 - f) + 0.12, flare=(0.6, 0.7, 5, 0.6), lean=(0.35, 0.1), missing=0.12)
    res = build_conifer2(spec, rng)
    res.spec = spec
    return res


# ============================================================================ pads (flattened cumulus foliage at branch ends)

def pick_pads(P, R, tipd, env, spec, rng):
    """Pad centres on branch ends (FPS over twig tips), flattened ellipsoid radii (rx, ry, rz) and yaw."""
    n = spec["n_pads"]
    lo, hi = spec["pad_r"]
    depth = env.inside_depth(P)
    zmin = spec.get("leaf_z_min", 1.0)
    ok = (tipd <= spec.get("pad_tip", 0.7)) & (R <= spec.get("leaf_r_max", 0.09) * 1.3) & (P[:, 2] > zmin) & (depth > 0.05)
    ids = np.nonzero(ok)[0]
    if len(ids) < n:
        ids = np.nonzero((P[:, 2] > zmin) & (depth > 0.0))[0]
    w = np.exp(-((depth[ids] - spec.get("pad_depth", 0.9)) / 1.0) ** 2)
    sel = [ids[int(np.argmax(P[ids, 2]))]]
    dmin = np.linalg.norm((P[ids] - P[sel[0]]) * np.array([1, 1, 1.6]), axis=1)
    for _ in range(n - 1):
        k = int(np.argmax(dmin * (0.4 + w)))
        sel.append(ids[k])
        dmin = np.minimum(dmin, np.linalg.norm((P[ids] - P[ids[k]]) * np.array([1, 1, 1.6]), axis=1))
    sel = np.array(sel)
    rx = rng.uniform(lo, hi, len(sel))
    radii = np.stack([rx, rx * rng.uniform(0.75, 1.2, len(sel)), rx * rng.uniform(*spec.get("pad_flat", (0.38, 0.52)), len(sel))], 1)
    C = P[sel] + np.stack([np.zeros(len(sel)), np.zeros(len(sel)), radii[:, 2] * 0.35], 1)
    yaw = rng.uniform(0, np.pi, len(sel))
    return C, radii, yaw, sel


def _rotz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def pad_cards(C, radii, yaw, nodes, n_target, lod, spec, rng, sway, ph_chain, node_chain, zr, accent):
    """Cards on flattened pads: bumpy top, flat sparse bottom, fringe cards breaking the outline."""
    tiles = CLUMP_TILES[spec.get("clump_kind", "oak")]
    fringe_tiles = spec.get("fringe_tiles", ["oak_clump_gold_a", "oak_clump_ochre_a", "oak_clump_light_b"])
    area = radii[:, 0] * radii[:, 1]
    share = area / area.sum()
    cards = []
    for k in range(len(C)):
        Rk = _rotz(yaw[k])
        rad = radii[k]
        hk = (C[k][2] - zr[0]) / max(zr[1] - zr[0], 1e-3)
        node = nodes[k]
        wind = np.array([min(1.0, sway[node] + 0.06), 0, ph_chain[node_chain[node]]])
        if lod == 2:
            m = spec.get("lod2_cards", 3)
            dirs = [np.array([0, 0, 1.0])] + [normalize(np.array([math.cos(a), math.sin(a), 0.15]))
                                               for a in np.linspace(0, np.pi, m - 1, endpoint=False) + rng.uniform(0, 3)]
            nfr = 0
        else:
            m = max([6, 3][lod], int(round(n_target * share[k] * (1 - spec.get("fringe_frac", 0.25)))))
            nfr = max(1, int(round(n_target * share[k] * spec.get("fringe_frac", 0.25)))) if lod == 0 else \
                max(1, int(round(n_target * share[k] * 0.15)))
            g = (1 + 5 ** 0.5) / 2
            rot = rng.uniform(0, 2 * np.pi)
            dirs = []
            i = 0
            while len(dirs) < m and i < 6 * m:
                z = 1 - 2 * (i + 0.5) / (1.6 * m)
                i += 1
                if z < -1:
                    break
                if z < -0.3 and rng.random() < 0.7:
                    continue                                    # flat, sparse underside
                rr = math.sqrt(max(0, 1 - z * z))
                a = 2 * np.pi * i / g + rot
                dirs.append(normalize(np.array([rr * math.cos(a), rr * math.sin(a), z]) + rng.normal(0, 0.12, 3)))
        for d in dirs:
            if accent[k]:
                cat = "red" if d[2] > 0.2 else "ochre"
            else:
                s = 0.65 * d[2] + 0.45 * (hk - 0.5) + 0.25 * float(np.dot(d, SUN)) + rng.normal(0, 0.12)
                cat = "light" if s > 0.30 else "gold" if s > -0.12 else "ochre" if s > -0.45 else "dark"
            tl = tiles[cat]
            bump = 1.0 + 0.18 * math.sin(3 * math.atan2(d[1], d[0]) + k) * (d[2] > 0)
            p = C[k] + Rk @ (d * rad * (rng.uniform(0.45, 0.75) if lod < 2 else 0.1) * bump)
            nrm_local = normalize(d / rad)
            tilt = normalize(np.array([rng.normal(), rng.normal(), 0.0]))
            nrm = normalize(Rk @ nrm_local + 0.45 * tilt + rng.normal(0, 0.15, 3)) if lod < 2 else normalize(Rk @ d)
            sz = rad[0] * rng.uniform(0.85, 1.15) * [1.0, 1.35, 2.1][lod] * spec.get("pad_card_k", 1.0)
            upv = normalize(np.cross(nrm, rng.normal(0, 1, 3)))
            cards.append(dict(c=p, n=nrm, up=upv, w=sz, h=sz * rng.uniform(0.8, 1.0), tile=tl[rng.integers(len(tl))],
                              C=C[k], radii=rad, R=Rk, wind=wind, attach="center"))
        for j in range(nfr):                                       # fringe: small clusters sticking out of the rim
            a = rng.uniform(0, 2 * np.pi)
            d = np.array([math.cos(a), math.sin(a), rng.uniform(-0.25, 0.45)])
            p = C[k] + Rk @ (d * rad * np.array([rng.uniform(0.95, 1.2), rng.uniform(0.95, 1.2), 1.0]))
            nrm = normalize(Rk @ normalize(d / rad) + np.array([0, 0, 0.35]) + rng.normal(0, 0.2, 3))
            sz = rad[0] * rng.uniform(0.38, 0.55) * [1.0, 1.4][lod]
            upv = normalize(Rk @ np.array([math.cos(a), math.sin(a), 0.2]))
            cards.append(dict(c=p, n=nrm, up=upv, w=sz, h=sz, tile=fringe_tiles[rng.integers(len(fringe_tiles))],
                              C=C[k], radii=rad, R=Rk, wind=wind, attach="center"))
    return cards


def emit_pad_cards(md, cards, hull_c, hull_r, mat, zr, k_pad=0.7):
    """Quads; per-vertex normals 70% from the flattened pad ellipsoid gradient, 30% from the crown hull."""
    for cc in cards:
        n = normalize(cc["n"])
        t = normalize(cc["up"] - n * np.dot(cc["up"], n))
        b = normalize(np.cross(t, n))
        c = cc["c"]
        w, h = cc["w"], cc["h"]
        corners = np.array([c - b * w / 2 - t * h / 2, c + b * w / 2 - t * h / 2, c + b * w / 2 + t * h / 2,
                            c - b * w / 2 + t * h / 2])
        u0, v0, u1, v1 = atlas.uv_rect(cc["tile"])
        uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        local = (corners - cc["C"]) @ cc["R"]
        ne = normalize((local / (cc["radii"] ** 2)) @ cc["R"].T)
        nh = normalize((corners - hull_c) / (hull_r ** 2))
        nn = normalize(k_pad * ne + (1 - k_pad) * nh)
        col = np.zeros((4, 4))
        col[:, 0] = cc["wind"][0]
        dist = np.linalg.norm(local / cc["radii"], axis=1)
        col[:, 1] = np.clip(0.25 + 0.6 * dist, 0.25, 1.0)
        col[:, 2] = cc["wind"][2]
        hz = np.clip((corners[:, 2] - zr[0]) / max(zr[1] - zr[0], 1e-3), 0, 1)
        col[:, 3] = np.clip(0.55 + 0.30 * (0.5 + 0.5 * nn[:, 2]) + 0.15 * hz, 0.5, 1.0)
        md.add(corners, [(0, 1, 2, 3)], [uv], mat, col, normals=nn)


def gnarled_limb(base, mid, end, n, rng, kink=0.35):
    """Bezier limb with random perpendicular kinks (gnarled)."""
    pts = _bezier(base, mid, end, n)
    d = normalize(np.asarray(end, float) - np.asarray(base, float))
    side = perp(d)
    up = np.cross(d, side)
    for i in range(1, n - 1):
        t = i / (n - 1)
        amp = kink * math.sin(np.pi * t)
        pts[i] = pts[i] + side * amp * rng.normal(0, 0.6) + up * amp * rng.normal(0, 0.4)
    return pts


def perp(v):
    v = normalize(v)
    a = np.array([1.0, 0, 0]) if abs(v[0]) < 0.9 else np.array([0, 1.0, 0])
    return normalize(np.cross(v, a))


# ============================================================================ golden oak v2: branchy tree + flattened pads

def build_golden_oak2(variant, view=None):
    """Short massive trunk splitting low into 3-5 thick gnarled limbs; secondary/tertiary branches by space
    colonisation; foliage = irregular flattened pads at the branch ends (+ fringe cards), broad dome."""
    seed = {1: 1101, 2: 1202, 3: 1303, 4: 1404}[variant]
    rng = np.random.default_rng(seed)
    sk = tg.Skeleton()
    if variant == 1:
        env = tg.envelope_from_mask(view.mask, view.ppm, view.ay, view.ax, z_min=3.0, depth_scale=0.9, voxel=0.25)
        top_z, rb = 3.4, 0.95
        limb_defs = [((-1.8, 0.3, 5.0), (-5.2, 0.5, 7.0), 0.52), ((-0.6, -1.4, 5.6), (-2.4, -3.8, 9.6), 0.46),
                     ((0.4, 0.5, 6.0), (0.6, 1.0, 11.2), 0.5), ((1.6, -0.6, 5.4), (4.2, -1.2, 9.4), 0.48),
                     ((1.9, 1.0, 4.8), (5.6, 2.2, 6.8), 0.44)]
        n_pads, pad_r = 50, (1.3, 2.1)
    elif variant == 2:
        env = tg.envelope_ellipsoid((0, 0, 9.0), (5.0, 4.6, 5.0), voxel=0.25,
                                    noise=lambda X, Y, Z: 0.12 * np.sin(1.2 * X + 0.6 * Z) * np.cos(1.1 * Y))
        top_z, rb = 4.2, 0.72
        limb_defs = [((-1.0, 0.3, 6.4), (-3.4, 0.6, 10.2), 0.4), ((1.0, -0.4, 6.6), (3.2, -0.9, 10.6), 0.4),
                     ((0.2, 0.2, 7.0), (0.3, 0.4, 13.2), 0.42), ((0.4, 1.3, 6.2), (1.2, 3.6, 9.4), 0.34)]
        n_pads, pad_r = 34, (1.15, 1.85)
    elif variant == 3:
        env1 = tg.envelope_ellipsoid((2.0, 0.3, 7.4), (5.8, 4.2, 3.4), voxel=0.25,
                                     noise=lambda X, Y, Z: 0.15 * np.sin(0.9 * X + 1.7 * Y) * np.cos(0.8 * Z))
        env2 = tg.envelope_ellipsoid((-2.6, -0.4, 9.2), (3.0, 3.0, 2.4), voxel=0.25)
        env = _union_env(env1, env2)
        top_z, rb = 3.0, 0.82
        limb_defs = [((1.8, 0.2, 4.4), (5.6, 0.4, 6.4), 0.46), ((1.0, -0.3, 5.6), (3.0, -0.8, 9.4), 0.42),
                     ((-0.8, 0.0, 5.8), (-2.8, -0.4, 10.2), 0.44), ((0.6, 1.6, 4.8), (1.6, 3.8, 6.8), 0.34)]
        n_pads, pad_r = 36, (1.2, 1.9)
    else:
        env = tg.envelope_ellipsoid((0, 0, 5.2), (3.6, 3.4, 2.7), voxel=0.2,
                                    noise=lambda X, Y, Z: 0.12 * np.sin(1.7 * X) * np.cos(1.9 * Y + Z))
        top_z, rb = 2.3, 0.4
        limb_defs = [((-0.9, 0.2, 3.4), (-2.6, 0.5, 4.8), 0.22), ((0.9, -0.4, 3.6), (2.5, -0.8, 5.2), 0.22),
                     ((0.1, 0.9, 3.8), (0.3, 2.0, 6.6), 0.22)]
        n_pads, pad_r = 20, (0.9, 1.45)
    trunk = _subdiv([(0, 0, -0.3), (0.05, 0, top_z * 0.5), (0.12, 0.04, top_z)], 0.6)
    tid = sk.add_polyline(trunk, can_grow_from_z=top_z + 0.4)
    top = np.array(trunk[-1])
    limbs = []
    for mid, end, r0 in limb_defs:
        pts = gnarled_limb(top, np.array(mid), np.array(end), 9, rng, kink=0.45)
        ids = sk.add_polyline(list(pts[1:]), parent=tid[-1], can_grow_from_z=top_z + 0.8)
        limbs.append((ids, r0, r0 * 0.3))
    att = env.sample(1600 if variant != 4 else 900, rng, shell=2.2, inner_weight=0.15)
    tg.space_colonize(sk, att, D=0.4 if variant != 4 else 0.32, di=3.0, dk=0.85, iters=150, tropism=(0, 0, 1),
                      trop_w=0.1, rng=rng, jitter=0.16)
    spec = oak_spec(seed, r_base=rb, trunk_r=lambda p: rb * (1.0 - 0.25 * min(max(p[2], 0), top_z) / top_z),
                    trunk_ids=tid, limbs=limbs, n_pads=n_pads, pad_r=pad_r, n_clumps=0, clump_kind="oak",
                    accent_frac=0.05, bark_frac=(0.46, 0.32, 0.16), pad_tip=0.8, pad_depth=0.9, leaf_z_min=top_z - 0.3,
                    fringe_frac=0.25, lod2_cards=3, lod2_max_clumps=22, pad_flat=(0.5, 0.66),
                    roots=(6, 2.6 if variant != 4 else 1.2, rb * 0.55), flare=(1.2, 1.1, 5, 1.0),
                    budget=(2950, 1150, 290) if variant != 4 else (2400, 950, 240))
    res = finish_broadleaf(sk, env, spec, rng)
    res.env = env
    return res
