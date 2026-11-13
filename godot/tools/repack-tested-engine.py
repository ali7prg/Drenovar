#!/usr/bin/env python3
"""Replace a matching Godot 4.6.3 iOS package's game data; signing remains external.

python3 tools/repack-tested-engine.py previous.ipa new.pck output.ipa --version 0.6.0 --build 21 \
    [--expect-executable-sha256 HEX] [--expect-ipa-sha256 HEX]

The engine executable, frameworks, icons and launch storyboard of the previous,
device-tested IPA are reused byte-for-byte; only DRENOVAR.pck and the version
fields of Info.plist change. This is NOT an Xcode compilation. The output is an
unsigned IPA intended for re-signing by SideStore/AltStore (signatures and
provisioning profiles of the source are removed).
"""
import argparse
import hashlib
import plistlib
import struct
import zipfile
from pathlib import Path

PREFIX = "Payload/DRENOVAR.app/"
BUNDLE_ID = "com.drenovar.game"


def pck_engine_version(data: bytes):
    if data[:4] != b"GDPC":
        raise SystemExit("New PCK is not a Godot pack")
    _pack, major, minor, patch = struct.unpack("<4I", data[4:20])
    return major, minor, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("pack", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--expect-executable-sha256", default="")
    parser.add_argument("--expect-ipa-sha256", default="")
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        raise SystemExit("Source and output must be different")
    if args.expect_ipa_sha256:
        actual = hashlib.sha256(args.source.read_bytes()).hexdigest()
        if actual != args.expect_ipa_sha256:
            raise SystemExit(f"Source IPA SHA-256 {actual} does not match the recorded tested IPA")
    pack_bytes = args.pack.read_bytes()
    if pck_engine_version(pack_bytes) != (4, 6, 3):
        raise SystemExit(f"PCK was exported by Godot {pck_engine_version(pack_bytes)}, engine binary is 4.6.3")
    with zipfile.ZipFile(args.source) as old:
        info = plistlib.loads(old.read(PREFIX + "Info.plist"))
        if info.get("CFBundleIdentifier") != BUNDLE_ID:
            raise SystemExit(f"Unexpected bundle id {info.get('CFBundleIdentifier')}")
        binary_name = PREFIX + info["CFBundleExecutable"]
        binary = old.read(binary_name)
        if binary[:4] != bytes.fromhex("cffaedfe"):
            raise SystemExit("Expected a native Mach-O arm64 executable")
        executable_hash = hashlib.sha256(binary).hexdigest()
        if args.expect_executable_sha256 and executable_hash != args.expect_executable_sha256:
            raise SystemExit(f"Executable SHA-256 {executable_hash} differs from the tested engine")
        if PREFIX + "DRENOVAR.pck" not in old.namelist():
            raise SystemExit("Source IPA has no separate DRENOVAR.pck")
        info["CFBundleShortVersionString"] = args.version
        info["CFBundleVersion"] = args.build
        with zipfile.ZipFile(args.destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as new:
            for entry in old.infolist():
                if "/_CodeSignature/" in entry.filename or entry.filename.endswith("embedded.mobileprovision"):
                    continue
                if entry.filename == PREFIX + "DRENOVAR.pck":
                    contents = pack_bytes
                elif entry.filename == PREFIX + "Info.plist":
                    contents = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
                else:
                    contents = old.read(entry.filename)
                new.writestr(entry, contents)
    with zipfile.ZipFile(args.destination) as result:
        assert result.testzip() is None
        assert hashlib.sha256(result.read(binary_name)).hexdigest() == executable_hash
        assert result.read(PREFIX + "DRENOVAR.pck") == pack_bytes
        written = plistlib.loads(result.read(PREFIX + "Info.plist"))
        assert written["CFBundleIdentifier"] == BUNDLE_ID
        assert written["CFBundleShortVersionString"] == args.version and written["CFBundleVersion"] == args.build
    digest = hashlib.sha256(args.destination.read_bytes()).hexdigest()
    print(f"IPA {args.destination.name} {args.destination.stat().st_size} bytes sha256 {digest}")
    print(f"engine executable unchanged sha256 {executable_hash}; PCK sha256 {hashlib.sha256(pack_bytes).hexdigest()}")
    print("Unsigned: SideStore/AltStore re-sign it on install.")


if __name__ == "__main__":
    main()
