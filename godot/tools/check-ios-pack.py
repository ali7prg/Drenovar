#!/usr/bin/env python3
"""Check that an exported DRENOVAR resource pack carries every runtime data file.

python3 godot/tools/check-ios-pack.py path/to/DRENOVAR.pck

The adventure reads its JSON data with FileAccess at runtime. Such files are not
Godot resources, so the export only packs them through the preset's include filter.
This check fails when any tracked JSON under project/data or project/assets is
missing from the pack, so a build cannot silently ship without the forest data.
"""
import struct
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent / "project"


def pack_names(path: Path) -> set:
    with path.open("rb") as pack:
        if pack.read(4) != b"GDPC":
            raise SystemExit(f"{path} is not a Godot resource pack")
        version, major, minor, patch = struct.unpack("<4I", pack.read(16))
        flags, = struct.unpack("<I", pack.read(4))
        pack.read(8)  # file base
        if version >= 3:
            directory, = struct.unpack("<Q", pack.read(8))
            pack.seek(directory)
        else:
            pack.read(16 * 4)
        if flags & 1:
            raise SystemExit("The pack directory is encrypted; cannot check it")
        count, = struct.unpack("<I", pack.read(4))
        names = set()
        for _ in range(count):
            length, = struct.unpack("<I", pack.read(4))
            name = pack.read(length).rstrip(b"\0").decode()
            pack.read(8 + 8 + 16 + 4)
            names.add(name.removeprefix("res://"))
        print(f"Pack format {version}, Godot {major}.{minor}.{patch}, {count} files, "
              f"{path.stat().st_size / 1e6:.1f} MB")
        return names


def main() -> None:
    names = pack_names(Path(sys.argv[1]))
    required = []
    for folder in ("data", "assets"):
        for item in sorted((PROJECT / folder).rglob("*.json")):
            required.append(item.relative_to(PROJECT).as_posix())
    missing = [item for item in required if item not in names]
    for item in missing:
        print(f"MISSING {item}")
    if not required:
        raise SystemExit("No runtime JSON found next to the project; wrong checkout?")
    if missing:
        raise SystemExit(f"{len(missing)} of {len(required)} runtime JSON files are not in the pack")
    print(f"All {len(required)} runtime JSON files are in the pack")


if __name__ == "__main__":
    main()
