"""Print ref/render mask runs (metres) per row from a compare PNG diff panel.
python diff_runs.py <png> <ppm> <center_col_in_crop> <ground_row_in_crop> [axis=row|col] [step_px]"""
import sys
import numpy as np
from PIL import Image
p, ppm, cc, gr = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
axis = sys.argv[5] if len(sys.argv) > 5 else "row"
step = int(sys.argv[6]) if len(sys.argv) > 6 else 15
a = np.asarray(Image.open(p).convert("RGB")).astype(int)[26:]
w = a.shape[1] // 3
d = a[:, 2 * w:3 * w]
red = (d[..., 0] > 190) & (d[..., 1] < 70) & (d[..., 2] < 70)
blue = (d[..., 2] > 190) & (d[..., 0] < 70)
green = (d[..., 1] > d[..., 0] + 25) & (d[..., 1] > d[..., 2] + 25)
ref = red | green
ren = blue | green
def runs(r):
    xs = np.nonzero(r)[0]
    if len(xs) == 0:
        return []
    out = []; s = xs[0]; pv = xs[0]
    for x in xs[1:]:
        if x != pv + 1:
            out.append((s, pv)); s = x
        pv = x
    out.append((s, pv))
    return out
fmt = lambda rr, c: " ".join(f"[{(a - c) / ppm:+.2f},{(b - c) / ppm:+.2f}]" for a, b in rr if b - a > 1)
if axis == "row":
    for y in range(5, ref.shape[0], step):
        print(f"z={(gr - y) / ppm:5.2f}  ref {fmt(runs(ref[y]), cc):40s} | ren {fmt(runs(ren[y]), cc)}")
else:
    for x in range(5, ref.shape[1], step):
        R = runs(ref[:, x]); N = runs(ren[:, x])
        f2 = lambda rr: " ".join(f"[{(gr - b) / ppm:.2f},{(gr - a) / ppm:.2f}]" for a, b in rr if b - a > 1)
        print(f"y={(x - cc) / ppm:+5.2f}  ref {f2(R):38s} | ren {f2(N)}")
