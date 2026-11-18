"""Compact review sheet of an iteration: python qa_sheet.py <asset_id> <tag> <out.png> [views...]"""
import sys, os
from PIL import Image
aid, tag, out = sys.argv[1:4]
views = sys.argv[4:] or ["side", "front", "rear"]
d = f"/home/user/Drenovar/forest_rescue/qa/compare/{aid}"
rows = []
for v in views:
    p = os.path.join(d, f"{tag}_{v}.png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("RGB")
    im = im.crop((0, 26, im.width, im.height))
    rows.append(im)
W = max(r.width for r in rows)
sc = 1600 / W
rows = [r.resize((int(r.width * sc), int(r.height * sc))) for r in rows]
H = sum(r.height for r in rows)
s = Image.new("RGB", (max(r.width for r in rows), H), (30, 30, 30))
y = 0
for r in rows:
    s.paste(r, (0, y)); y += r.height
s.save(out)
print(s.size)
