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


def limb_tree(segs, jcent, root_mask, axis_fn, min_len=6, min_r=1.2, spur_k=1.6, touch_px=4,
              keep_floating=True, float_min_r=1.6, float_min_len=10):
    """Orient segments away from the trunk (root_mask), BFS through junctions, prune spurs/thin bits.

    axis_fn(y_pixel) -> x_pixel of the trunk axis at that row (start points get extended to it).
    Floating segments (not connected to the trunk) are kept as independent limbs (parent -2).
    Returns list of dict(P (k,2) x,y from base to tip, r (k,), parent idx (-1 trunk, -2 floating), level)."""
    H, W = root_mask.shape
    near_root = ndi.binary_dilation(root_mask, iterations=touch_px)
    adj = {}
    for si, s in enumerate(segs):
        for j in s["j"]:
            if j is not None:
                adj.setdefault(j, []).append(si)

    def touches(p):
        x, y = int(round(p[0])), int(round(p[1]))
        return 0 <= y < H and 0 <= x < W and near_root[y, x]

    visited, limbs, queue, jvisited = set(), [], [], set()
    for si, s in enumerate(segs):
        a, b = touches(s["P"][0]), touches(s["P"][-1])
        if a or b:
            queue.append((si, None, -1, 0, a))
    # junctions inside the root region count as visited roots
    for j, c in enumerate(jcent):
        y, x = int(round(c[0])), int(round(c[1]))
        if 0 <= y < H and 0 <= x < W and near_root[y, x]:
            jvisited.add(j)

    def run(queue):
        while queue:
            si, from_j, parent, lvl, start_first = queue.pop(0)
            if si in visited:
                continue
            visited.add(si)
            s = segs[si]
            P, r, j0, j1 = s["P"], s["r"], s["j"][0], s["j"][1]
            if from_j is not None:
                if j1 == from_j and j0 != from_j:
                    P, r, j0, j1 = P[::-1], r[::-1], j1, j0
            elif not start_first:
                P, r, j0, j1 = P[::-1], r[::-1], j1, j0
            if from_j is not None and from_j < len(jcent):
                jc = jcent[from_j][::-1]
                P = np.vstack([jc[None], P])
                r = np.r_[r[0], r]
            elif parent == -1:
                ax = axis_fn(P[0][1])
                if ax is not None:
                    P = np.vstack([[ax, P[0][1]], P])
                    r = np.r_[r[0], r]
            # drop pixels inside the trunk (keep the first one as anchor)
            idx = len(limbs)
            limbs.append(dict(P=P, r=r, parent=parent, level=lvl, end_j=j1, seg=si))
            if j1 is not None and j1 not in jvisited:
                jvisited.add(j1)
                for sj in adj.get(j1, []):
                    if sj not in visited:
                        queue.append((sj, j1, idx, lvl + 1, True))

    run(queue)
    if keep_floating:
        # remaining components: start from their lowest end (closest to the trunk axis)
        rest = [si for si in range(len(segs)) if si not in visited]
        rest.sort(key=lambda si: -np.median(segs[si]["r"]) * segs[si]["n"])
        for si in rest:
            if si in visited:
                continue
            s = segs[si]
            if np.median(s["r"]) < float_min_r or s["n"] < float_min_len:
                continue
            p0, p1 = s["P"][0], s["P"][-1]
            ax0 = axis_fn(p0[1])
            ax1 = axis_fn(p1[1])
            d0 = abs(p0[0] - (ax0 if ax0 is not None else p0[0])) + 0.3 * (H - p0[1])
            d1 = abs(p1[0] - (ax1 if ax1 is not None else p1[0])) + 0.3 * (H - p1[1])
            run([(si, None, -2, 1, d0 <= d1)])
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
    for i, l in enumerate(limbs):
        p = l["parent"]
        while p >= 0:
            if not keep[p]:
                keep[i] = False
                break
            p = limbs[p]["parent"]
    remap, out = {}, []
    for i, l in enumerate(limbs):
        if keep[i]:
            remap[i] = len(out)
            l = dict(l)
            if l["parent"] >= 0:
                l["parent"] = remap.get(l["parent"], -2)
            out.append(l)
    return out
