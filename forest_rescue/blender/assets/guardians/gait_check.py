"""Pure-python gait check: stance IK reach error and lowest detail point per locomotion clip."""
import sys, importlib
import numpy as np
sys.path.insert(0, "/home/user/Drenovar/forest_rescue/blender/assets/guardians")
import ganim, gclips
for name in sys.argv[1:]:
    sp = importlib.import_module(f"spec_{name}")
    sk = sp.skeleton(); C = ganim.Composer(sk, sp.LEGS, sp.PIVOT)
    D = sp.details(sk) if sp.details.__code__.co_argcount < 4 else sp.details(sk)
    for kind in ("walk", "run"):
        if kind not in sp.ANIM:
            continue
        fr, m = gclips.locomotion(C, sp.ANIM, kind)
        worst, low = 0.0, 9.0
        for f in fr:
            p = C.compose(f)
            for leg, ch in sp.LEGS.items():
                if f["feet"][leg]["stance"]:
                    worst = max(worst, np.linalg.norm(p[ch[4]][:3, 3] - f["feet"][leg]["pos"]))
            for d in D:
                b = d["bone"]; T = p[b] @ np.linalg.inv(sk.rest[b]); v = d["mesh"][0]
                low = min(low, float((v @ T[:3, :3].T + T[:3, 3])[:, 2].min()))
        print(name, kind, "stance reach err cm", round(worst * 100, 2), "lowest detail z", round(low, 3),
              "stride", m["strideLength_m"])
