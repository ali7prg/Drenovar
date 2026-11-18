import sys, numpy as np
from PIL import Image
p = sys.argv[1]; off = int(sys.argv[2]); rows = [int(x) for x in sys.argv[3].split(',')]
a = np.asarray(Image.open(p).convert('RGB')).astype(int)[26:]
w = a.shape[1]//3; d = a[:, 2*w:3*w]
red = (d[...,0]>190)&(d[...,1]<70)&(d[...,2]<70); blue=(d[...,2]>190)&(d[...,0]<70); green=(d[...,1]>d[...,0]+25)&(d[...,1]>d[...,2]+25)
ref = red|green; ren = blue|green
def runs(r):
    xs=np.nonzero(r)[0]; out=[]
    if len(xs)==0: return out
    s=xs[0]; pv=xs[0]
    for x in xs[1:]:
        if x!=pv+1: out.append((s+off,pv+off)); s=x
        pv=x
    out.append((s+off,pv+off)); return [f"{o[0]}-{o[1]}" for o in out if o[1]-o[0]>2]
print("red px", red.sum(), "blue px", blue.sum())
for y in rows:
    print(f"y={y} ref {' '.join(runs(ref[y]))}\n      ren {' '.join(runs(ren[y]))}")
