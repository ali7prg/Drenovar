#!/usr/bin/env python3
"""Verify independent ZIPs, then extract without conflicting paths. Python stdlib only."""
import argparse, hashlib, json, pathlib, sys, zipfile

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('packages', type=pathlib.Path, help='folder containing all ZIPs and DELIVERY_INDEX.json')
    ap.add_argument('--extract', type=pathlib.Path, help='new empty extraction folder')
    args = ap.parse_args()
    index = json.loads((args.packages / 'DELIVERY_INDEX.json').read_text())
    names, entries, archives = set(), {}, []
    for item in index['packages']:
        name = item['filename']
        if pathlib.PurePosixPath(name).name != name or name in names:
            raise ValueError('Invalid/duplicate archive name')
        names.add(name)
        path = args.packages / name
        blob = path.read_bytes()
        if len(blob) != item['bytes'] or len(blob) > 30_000_000 or sha(blob) != item['sha256']:
            raise ValueError('Archive integrity failure: '+name)
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None: raise ValueError('ZIP CRC failure: '+name)
            for info in z.infolist():
                p = pathlib.PurePosixPath(info.filename)
                if info.is_dir() or p.is_absolute() or '..' in p.parts or '\\' in str(p) or ':' in str(p):
                    raise ValueError('Unsafe path: '+str(p))
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Symlink not permitted')
                if str(p) in entries: raise ValueError('Conflicting path: '+str(p))
                data = z.read(info)
                entries[str(p)] = {'bytes':len(data), 'sha256':sha(data)}
            archives.append(path)
    for item in index['packages']:
        if not set(item['depends_on']).issubset(names): raise ValueError('Missing package dependency')
    manifest_path = 'DRENOVAR_Forest_Rescue/PACKAGE_MANIFEST.json'
    start = next(p for p in archives if '_00_Start' in p.name)
    with zipfile.ZipFile(start) as z:
        manifest = json.loads(z.read(manifest_path))
    expected = {i['path']: {'bytes':i['bytes'],'sha256':i['sha256']} for i in manifest['files']}
    actual = {k:v for k,v in entries.items() if k != manifest_path}
    if expected != actual: raise ValueError('Payload manifest mismatch')
    if args.extract:
        if args.extract.exists() and any(args.extract.iterdir()): raise ValueError('Extraction target must be empty')
        args.extract.mkdir(parents=True, exist_ok=True)
        for path in archives:
            with zipfile.ZipFile(path) as z: z.extractall(args.extract)
        for name,meta in entries.items():
            blob=(args.extract/name).read_bytes()
            if len(blob)!=meta['bytes'] or sha(blob)!=meta['sha256']: raise ValueError('Readback mismatch: '+name)
    print(json.dumps({'ok':True,'archives':len(archives),'files':len(entries),'exact_sizes':True,'sha256':True,'zip_crc':True,'unique_safe_paths':True,'extracted':bool(args.extract)},indent=2))

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('FAIL: '+str(e),file=sys.stderr); sys.exit(1)
