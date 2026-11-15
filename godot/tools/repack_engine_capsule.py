#!/usr/bin/env python3
"""Build an unsigned test IPA from the explicitly reduced, verified engine capsule.
Not a replacement for compatibility review, native compilation or device testing.
Usage: python3 repack_engine_capsule.py BASE.zip NEW.pck OUTPUT.ipa \
  --version 0.6.0 --build 21 --expect-capsule-sha256 <SHA256>
"""
from pathlib import Path, PurePosixPath
import argparse, copy, hashlib, json, os, plistlib, struct, tempfile, zipfile

PREFIX = 'Payload/DRENOVAR.app/'
EXPECTED_EXECUTABLE = 'd9816f67f540bbebccfdb2a5ecf9460feda71c05247e4e80601caf44973bfaae'
ORIGINAL_IPA = '987a47b049eda4c9bc1c522e48b95c80beb5dfbebec7e340156d0400b3b18ec3'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def require(ok, message):
    if not ok:
        raise ValueError(message)

def build(args):
    require(args.destination.suffix.lower() == '.ipa', 'Output must end with .ipa')
    require(not args.destination.exists(), 'Output already exists; use a new path')
    require(args.source.resolve() != args.destination.resolve(), 'Source must not be overwritten')
    require(args.version and args.build, 'Version and build are required')
    require(sha(args.source.read_bytes()) == args.expect_capsule_sha256.lower(), 'Capsule checksum mismatch')
    pack = args.pack.read_bytes()
    require(len(pack) >= 20 and pack[:4] == b'GDPC', 'Invalid Godot PCK header')
    require(struct.unpack_from('<3I', pack, 8) == (4, 6, 3), 'Godot PCK engine version must be 4.6.3')
    with zipfile.ZipFile(args.source) as base:
        require(base.testzip() is None, 'Capsule ZIP integrity error')
        names = base.namelist()
        require(len(names) == len(set(names)), 'Duplicate ZIP entries')
        manifest = json.loads(base.read('ENGINE_CAPSULE_MANIFEST.json'))
        require(manifest['source_ipa_sha256'] == ORIGINAL_IPA, 'Unexpected source provenance')
        require(manifest['omitted_path'] == PREFIX+'DRENOVAR.pck', 'Unexpected omitted file')
        expected = {item['path']: item for item in manifest['retained_files']}
        actual_payload = {e.filename for e in base.infolist() if e.filename.startswith('Payload/') and not e.is_dir()}
        require(actual_payload == set(expected), 'Missing or extra payload files')
        for name, record in expected.items():
            require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, 'Unsafe ZIP path')
            data=base.read(name)
            require(len(data) == record['bytes'] and sha(data) == record['sha256'], 'Payload hash mismatch: '+name)
        info=plistlib.loads(base.read(PREFIX+'Info.plist'))
        require(info['CFBundleIdentifier'] == 'com.drenovar.game', 'Wrong Bundle ID')
        binary_name=PREFIX+info['CFBundleExecutable']
        binary=base.read(binary_name)
        require(sha(binary) == EXPECTED_EXECUTABLE, 'Executable differs from original recorded engine')
        require(binary[:4] == bytes.fromhex('cffaedfe') and struct.unpack_from('<I',binary,4)[0] == 0x0100000C, 'Expected arm64 Mach-O')
        info['CFBundleShortVersionString']=args.version
        info['CFBundleVersion']=args.build
        args.destination.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix=args.destination.name+'.',suffix='.tmp',dir=args.destination.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
                for entry in base.infolist():
                    if not entry.filename.startswith('Payload/'):
                        continue
                    if '/_CodeSignature/' in entry.filename or entry.filename.endswith('embedded.mobileprovision'):
                        continue
                    data=plistlib.dumps(info,fmt=plistlib.FMT_BINARY) if entry.filename == PREFIX+'Info.plist' else base.read(entry.filename)
                    out.writestr(copy.copy(entry),data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
                pck_entry=zipfile.ZipInfo(PREFIX+'DRENOVAR.pck')
                pck_entry.external_attr=(0o100644 << 16)
                out.writestr(pck_entry,pack,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
            with zipfile.ZipFile(temp) as result:
                require(result.testzip() is None,'Output ZIP integrity error')
                require(sha(result.read(binary_name)) == EXPECTED_EXECUTABLE,'Engine changed during packaging')
                require(result.read(PREFIX+'DRENOVAR.pck') == pack,'PCK differs from supplied pack')
                written=plistlib.loads(result.read(PREFIX+'Info.plist'))
                require(written['CFBundleIdentifier']=='com.drenovar.game','Output Bundle ID changed')
                require(written['CFBundleShortVersionString']==args.version and written['CFBundleVersion']==args.build,'Output version mismatch')
                for name in expected:
                    if name != PREFIX+'Info.plist':
                        require(result.read(name)==base.read(name),'Retained file changed: '+name)
            os.replace(temp,args.destination)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    print(json.dumps({'output':str(args.destination),'bytes':args.destination.stat().st_size,'sha256':sha(args.destination.read_bytes()),'engine_sha256':EXPECTED_EXECUTABLE,'pck_sha256':sha(pack),'version':args.version,'build':args.build,'signed':False,'device_tested':False},indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('pack',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--version',required=True)
    parser.add_argument('--build',required=True)
    parser.add_argument('--expect-capsule-sha256',required=True)
    args=parser.parse_args()
    try:
        build(args)
    except (ValueError,OSError,KeyError,zipfile.BadZipFile,struct.error) as exc:
        parser.exit(1,f'ERROR: {exc}\n')

if __name__=='__main__':
    main()
