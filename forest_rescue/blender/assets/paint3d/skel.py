"""Wood skeleton: medial axis -> branch segments (ordered pixel polylines with radii) -> limb tree."""
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def segments(mask, smooth=0):
    m = ndi.binary_opening(mask, iterations=smooth) if smooth else mask
    sk, dist = morphology.medial_axis(m, return_distance=True)
    k = ndi.convolve(sk.astype(np.int32), np.ones((3, 3), np.int32), mode="constant") - 1
    nb = np.where(sk, k, 0)
    junc = sk & (nb >= 3)
    jd = ndi.binary_dilation(junc, structure=np.ones((3, 3))) & sk
    jl, jn = ndi.label(jd, structure=np.ones((3, 3)))
    jcent = np.array(ndi.center_of_mass(jd, jl, np.arange(1, jn + 1))) if jn else np.zeros((0, 2))
    segpix = sk & ~jd
    sl, sn = ndi.label(segpix, structure=np.ones((3, 3)))
    objs = ndi.find_objects(sl)
    out = []
    H, W = mask.shape
    for i in range(1, sn + 1):
        sly, slx = objs[i - 1]
        sub = sl[sly, slx] == i
        ys, xs = np.nonzero(sub)
        ys = ys + sly.start
        xs = xs + slx.start
        pts = set(zip(ys.tolist(), xs.tolist()))
        # endpoints: pixels with <=1 neighbour inside the segment
        def nbrs(p):
            return [(p[0] + dy, p[1] + dx) for dy, dx in N8 if (p[0] + dy, p[1] + dx) in pts]
        ends = [p for p in pts if len(nbrs(p)) <= 1]
        start = ends[0] if ends else next(iter(pts))
        order = [start]
        seen = {start}
        cur = start
        while True:
            nx = [q for q in nbrs(cur) if q not in seen]
            if not nx:
                break
            # prefer 4-neighbours first for a clean walk
            nx.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            cur = nx[0]
            seen.add(cur)
            order.append(cur)
        P = np.array(order, float)[:, ::-1]           # (x, y)
        r = dist[P[:, 1].astype(int), P[:, 0].astype(int)]
        # junctions touching each end
        jt = []
        for end in (order[0], order[-1]):
            hit = None
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    y, x = end[0] + dy, end[1] + dx
                    if 0 <= y < H and 0 <= x < W and jl[y, x] > 0:
                        hit = int(jl[y, x]) - 1
            jt.append(hit)
        out.append(dict(P=P, r=r, j=jt, n=len(P)))
    return out, jcent, sk, dist


def limb_tree(segs, jcent, root_xy, root_radius=6.0, min_len=6, min_r=1.2, spur_k=1.6):
    """Orient segments away from root_xy (BFS through junctions), prune spurs/thin bits.

    Returns list of limbs: dict(P (k,2) pixel x,y from base to tip, r (k,), parent index or -1, depth level)."""
    root_xy = np.asarray(root_xy, float)
    # adjacency: junction -> segments
    adj = {}
    for si, s in enumerate(segs):
        for j in s["j"]:
            if j is not None:
                adj.setdefault(j, []).append(si)
    # pick start segments: those with an end within root_radius*3 of root or touching junction near root
    def d_end(s):
        return min(np.linalg.norm(s["P"][0] - root_xy), np.linalg.norm(s["P"][-1] - root_xy))
    order = sorted(range(len(segs)), key=lambda i: d_end(segs[i]))
    visited = set()
    limbs = []
    queue = []
    for si in order:
        if d_end(segs[si]) <= root_radius * 2.5 + 4:
            queue.append((si, None, -1, 0))
    if not queue and order:
        queue.append((order[0], None, -1, 0))
    jvisited = set()
    while queue:
        si, from_j, parent, lvl = queue.pop(0)
        if si in visited:
            continue
        visited.add(si)
        s = segs[si]
        P, r, j0, j1 = s["P"], s["r"], s["j"][0], s["j"][1]
        if from_j is not None:
            if j1 == from_j and j0 != from_j:
                P, r, j0, j1 = P[::-1], r[::-1], j1, j0
        else:
            if np.linalg.norm(P[-1] - root_xy) < np.linalg.norm(P[0] - root_xy):
                P, r, j0, j1 = P[::-1], r[::-1], j1, j0
        if from_j is not None and from_j < len(jcent):
            jc = jcent[from_j][::-1]
            P = np.vstack([jc[None], P])
            r = np.r_[r[0], r]
        elif parent == -1:
            P = np.vstack([root_xy[None], P])
            r = np.r_[r[0], r]
        idx = len(limbs)
        limbs.append(dict(P=P, r=r, parent=parent, level=lvl, end_j=j1, seg=si))
        if j1 is not None and j1 not in jvisited:
            jvisited.add(j1)
            for sj in adj.get(j1, []):
                if sj not in visited:
                    queue.append((sj, j1, idx, lvl + 1))
    # prune: thin limbs and short terminal spurs
    children = {i: [] for i in range(len(limbs))}
    for i, l in enumerate(limbs):
        if l["parent"] >= 0:
            children[l["parent"]].append(i)
    keep = [True] * len(limbs)
    for i, l in enumerate(limbs):
        L = np.linalg.norm(np.diff(l["P"], axis=0), axis=1).sum()
        rm = float(np.median(l["r"]))
        if rm < min_r:
            keep[i] = False
        if not children[i] and L < max(min_len, spur_k * rm * 2):
            keep[i] = False
    # drop descendants of dropped limbs
    for i, l in enumerate(limbs):
        p = l["parent"]
        while p >= 0:
            if not keep[p]:
                keep[i] = False
                break
            p = limbs[p]["parent"]
    remap = {}
    out = []
    for i, l in enumerate(limbs):
        if keep[i]:
            remap[i] = len(out)
            l = dict(l)
            l["parent"] = remap.get(l["parent"], -1)
            out.append(l)
    return out
