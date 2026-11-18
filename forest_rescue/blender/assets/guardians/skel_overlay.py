"""Debug: draw the (posed) skeleton over reference panels.  python skel_overlay.py <spec> <out_dir>"""
import importlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import cv2
from frlib import core

def draw(pan, sk, pose, path, scale=2):
    img = (pan.view.image * 255).astype(np.uint8).copy()
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    for n in sk.names:
        if n == "root": continue
        h = pose[n][:3, 3]; t = h + pose[n][:3, 1] * sk.length[n]
        u0, v0, d0 = pan.view.project(h[None]); u1, v1, d1 = pan.view.project(t[None])
        near = (pan.view.d @ ((h + t) / 2)) < 0  # closer to camera
        col = (255, 255, 0) if n.endswith("_L") else ((0, 255, 255) if n.endswith("_R") else (255, 60, 60))
        cv2.line(img, (int(u0[0]*scale), int(v0[0]*scale)), (int(u1[0]*scale), int(v1[0]*scale)), col, 2)
        cv2.circle(img, (int(u0[0]*scale), int(v0[0]*scale)), 4, col, -1)
    cv2.imwrite(path, img[..., ::-1])

def main():
    spec = importlib.import_module(sys.argv[1]); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    pans = spec.panels(); sk = spec.skeleton()
    bind = sk.fk()
    for name, pan in pans.items():
        pose = spec.side_stance(sk) if (name == "side" and hasattr(spec, "side_stance")) else bind
        draw(pan, sk, pose, os.path.join(out, f"skel_{name}.png"))
main()
