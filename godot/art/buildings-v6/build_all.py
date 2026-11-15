#!/usr/bin/env python3
"""Self-contained CI entry point for the native and web V6 building asset pack.

Run from any directory: python3 godot/art/buildings-v6/build_all.py --bootstrap
Godot 4.6.3 must be installed; DRENOVAR_GODOT_BIN may name its executable.
--check-reproducible performs a second complete generation and compares all assets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROJECT = ROOT / "godot/project"
ASSETS = PROJECT / "assets/city/architecture-v6"


def command(args: list[str], cwd: Path = ROOT) -> None:
    print("ART_COMMAND " + " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def fingerprints(native_only: bool) -> dict[str, str]:
    directories = ["levels", "transitions", "units"] + ([] if native_only else ["web", "materials"])
    return {str(p.relative_to(ASSETS)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in directories for p in sorted((ASSETS / folder).rglob("*"))
            if p.is_file() and not p.name.startswith(".")}


def archive(destination: Path, files: list[Path]) -> None:
    # Stable zip timestamps; delivery archives carry the exact verified bytes.
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for file in sorted(files):
            info = zipfile.ZipInfo(str(file.relative_to(ASSETS)), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            output.writestr(info, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true", help="Install pinned Python/Node tools into ignored local directories")
    parser.add_argument("--native-only", action="store_true", help="Native iOS packaging job; skips all Node/web outputs")
    parser.add_argument("--check-reproducible", action="store_true")
    parser.add_argument("--package-dir", type=Path, help="Write separate native-assets.zip and web-assets.zip")
    args = parser.parse_args()
    godot = os.environ.get("DRENOVAR_GODOT_BIN", "godot")
    engine = subprocess.check_output([godot, "--version"], text=True).strip()
    if not engine.startswith("4.6.3."):
        raise SystemExit("This asset version is pinned to Godot 4.6.3, found " + engine)
    venv = HERE / ".venv"
    python = str(venv / "bin/python") if (venv / "bin/python").exists() and not args.native_only else sys.executable
    node_version = None
    pillow_version = None
    if not args.native_only:
        node_version = subprocess.check_output(["node", "--version"], text=True).strip()
        if not node_version.startswith("v24."):
            raise SystemExit("Node 24 is required, found " + node_version)
        if args.bootstrap:
            if not (venv / "bin/python").exists():
                command([sys.executable, "-m", "venv", str(venv)])
            python = str(venv / "bin/python")
            command([python, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(HERE / "requirements.txt")])
            command(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], HERE)
        pillow_version = subprocess.check_output([python, "-c", "import PIL;print(PIL.__version__)"], text=True).strip()
        if pillow_version != "13.0.0":
            raise SystemExit("Pillow 13.0.0 is required; rerun with --bootstrap")

    def godot_script(name: str, *extra: str) -> None:
        command([godot, "--headless", "--path", str(PROJECT), "-s", str(HERE / name), *extra])

    def build_once() -> None:
        godot_script("build.gd", *( ["--", "--skip-web"] if args.native_only else [] ))
        godot_script("build_transitions.gd")
        godot_script("verify.gd")
        command([python, str(HERE / "verify_preservation.py")])
        if not args.native_only:
            command([python, str(HERE / "pack_web.py")])
            command(["node", str(HERE / "verify_web.mjs")])
            command(["node", str(HERE / "validate_gltf.mjs")])

    # A fresh checkout has no .godot/imported cache. This is required for the
    # original JPEG/PNG textures referenced by the unchanged PBR resources.
    command([godot,"--headless","--path",str(PROJECT),"--editor","--import","--quit"])
    build_once()
    hashes = fingerprints(args.native_only)
    repeated = False
    if args.check_reproducible:
        build_once()
        second = fingerprints(args.native_only)
        differences = sorted(key for key in set(hashes) | set(second) if hashes.get(key) != second.get(key))
        (ASSETS / "reproducibility.json").write_text(json.dumps({"status":"passed" if not differences else "error",
            "generation_passes":2,"files":len(hashes),"different_files":differences,
            "platform":platform.platform(),"scope":"Two clean generator executions; same pinned toolchain and machine"}, indent=2) + "\n")
        if differences:
            raise SystemExit("Non-deterministic assets: " + repr(differences))
        repeated = True
    (ASSETS / "artifact-sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    (ASSETS / "toolchain.json").write_text(json.dumps({"godot":engine,"node":node_version,
        "python":platform.python_version(),"pillow":pillow_version,"meshoptimizer":"1.3.0",
        "gltf_validator":"2.0.0-dev.3.10","platform":platform.platform(),
        "native_only":args.native_only,"reproducibility_checked":repeated,
        "scratch_dependencies":[],"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()}, indent=2) + "\n")
    if args.package_dir:
        destination = args.package_dir.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        native = [p for directory in ["levels","transitions","units"] for p in (ASSETS / directory).rglob("*") if p.is_file()]
        native += [ASSETS / "manifest.json",ASSETS / "artifact-sha256.json"]
        archive(destination / "native-assets.zip",native)
        if not args.native_only:
            web = [p for directory in ["web","materials"] for p in (ASSETS / directory).rglob("*") if p.is_file() and not p.name.startswith(".")]
            web += [ASSETS / "manifest.json",ASSETS / "artifact-sha256.json"]
            archive(destination / "web-assets.zip",web)
    print(f"ART_BUILD passed files={len(hashes)} reproducible={repeated}",flush=True)


if __name__ == "__main__":
    main()
