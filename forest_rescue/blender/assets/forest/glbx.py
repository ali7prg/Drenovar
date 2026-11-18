"""Minimal GLB reader/writer: replace embedded images by external relative URIs (shared textures)."""
import json, struct, sys
def read_glb(path):
    b = open(path,'rb').read()
    assert b[:4] == b'glTF'
    off = 12; js = None; bin_ = b''
    while off < len(b):
        ln, typ = struct.unpack('<II', b[off:off+8]); data = b[off+8:off+8+ln]
        if typ == 0x4E4F534A: js = json.loads(data)
        elif typ == 0x004E4942: bin_ = data
        off += 8 + ln
    return js, bin_
def write_glb(path, js, bin_):
    jb = json.dumps(js, separators=(',',':')).encode()
    jb += b' ' * ((4 - len(jb) % 4) % 4)
    bin_ += b'\0' * ((4 - len(bin_) % 4) % 4)
    total = 12 + 8 + len(jb) + (8 + len(bin_) if bin_ else 0)
    out = struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<II', len(jb), 0x4E4F534A) + jb
    if bin_: out += struct.pack('<II', len(bin_), 0x004E4942) + bin_
    open(path,'wb').write(out)
def externalize(path, mapping):
    """mapping: image name -> relative uri. Removes the embedded bufferViews and compacts BIN."""
    js, bin_ = read_glb(path)
    drop = set()
    for im in js.get('images', []):
        if im.get('name') in mapping:
            drop.add(im.pop('bufferView')); im.pop('mimeType', None); im['uri'] = mapping[im['name']]
    if not drop: return 0
    bvs = js['bufferViews']; remap = {}; newbvs = []; newbin = bytearray()
    for i, bv in enumerate(bvs):
        if i in drop: continue
        data = bin_[bv.get('byteOffset',0): bv.get('byteOffset',0) + bv['byteLength']]
        while len(newbin) % 4: newbin.append(0)
        nbv = dict(bv); nbv['byteOffset'] = len(newbin); newbin += data
        remap[i] = len(newbvs); newbvs.append(nbv)
    js['bufferViews'] = newbvs
    for acc in js.get('accessors', []):
        if 'bufferView' in acc: acc['bufferView'] = remap[acc['bufferView']]
        sp = acc.get('sparse')
        if sp:
            sp['indices']['bufferView'] = remap[sp['indices']['bufferView']]; sp['values']['bufferView'] = remap[sp['values']['bufferView']]
    for im in js.get('images', []):
        if 'bufferView' in im: im['bufferView'] = remap[im['bufferView']]
    js['buffers'][0]['byteLength'] = len(newbin)
    write_glb(path, js, bytes(newbin))
    return len(drop)
if __name__ == '__main__':
    print(externalize(sys.argv[1], {sys.argv[2]: sys.argv[3]}))


def info(path):
    """Summary: images (uri / embedded), materials, meshes with triangle counts per primitive."""
    js, bin_ = read_glb(path)
    out = {"images": [], "materials": [m.get("name") for m in js.get("materials", [])], "meshes": {}}
    for im in js.get("images", []):
        out["images"].append(im.get("uri") or f"<embedded {im.get('mimeType')}>")
    for m in js.get("meshes", []):
        tris = 0
        for p in m["primitives"]:
            acc = js["accessors"][p["indices"]]
            tris += acc["count"] // 3
        out["meshes"][m["name"]] = tris
    return out
