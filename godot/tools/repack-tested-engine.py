#!/usr/bin/env python3
"""Replace a matching Godot 4.6.3 iOS package's game data; signing remains external.

python3 tools/repack-tested-engine.py previous.ipa new.pck output.ipa
The engine executable and frameworks are reused byte-for-byte. This is not an
Xcode compilation and does not create a signed App Store/TestFlight release.
"""
import hashlib
import plistlib
import sys
import zipfile
from pathlib import Path

source, pack, destination = map(Path, sys.argv[1:])
if source.resolve() == destination.resolve():
    raise SystemExit("Source and output must be different")
prefix = "Payload/DRENOVAR.app/"
with zipfile.ZipFile(source) as old:
    original_info = plistlib.loads(old.read(prefix + "Info.plist"))
    binary_name = prefix + original_info["CFBundleExecutable"]
    executable_hash = hashlib.sha256(old.read(binary_name)).hexdigest()
    assert old.read(binary_name)[:4] == bytes.fromhex("cffaedfe"), "Expected native Mach-O arm64 executable"
    assert prefix + "DRENOVAR.pck" in old.namelist()
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as new:
        for entry in old.infolist():
            if "/_CodeSignature/" in entry.filename or entry.filename.endswith("embedded.mobileprovision"):
                continue
            if entry.filename == prefix + "DRENOVAR.pck":
                contents = pack.read_bytes()
            elif entry.filename == prefix + "Info.plist":
                original_info["CFBundleShortVersionString"] = "0.5.9"
                original_info["CFBundleVersion"] = "19"
                contents = plistlib.dumps(original_info, fmt=plistlib.FMT_BINARY)
            else:
                contents = old.read(entry.filename)
            new.writestr(entry, contents)
with zipfile.ZipFile(destination) as result:
    assert result.testzip() is None
    assert hashlib.sha256(result.read(binary_name)).hexdigest() == executable_hash
    assert hashlib.sha256(result.read(prefix + "DRENOVAR.pck")).digest() == hashlib.sha256(pack.read_bytes()).digest()
print("Verified package CRC, unchanged native engine, exact new PCK. Requires signing for installation.")
