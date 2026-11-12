# DRENOVAR Godot — complete native source import

**Status: COMPLETE** (12 November 2026). The earlier partial-API-transfer warning is obsolete.

- Repository: `ali7prg/Drenovar`, branch `main`.
- Original snapshot: `DRENOVAR-iOS-v0.5.9-source.zip`, Godot 4.6.3, iOS build 19.
- Verified source Git bundle: `drenovar-godot-0.5.9.git.bundle`.
- Original source Git commit: `5ae4bc3ec323d78212df7a4d2c17f44a8c0b54a8`.
- Bundle SHA-256: `9888e56de53cd2bc4936e5e19768a54de690afd30767869d0db429369c773366`.
- Original Git handoff count: **1,617 tracked files**.
- Verified in GitHub: **732 / 732** inventoried original asset files, **0** missing, **0** mismatched.
- **447 / 447** GLB models.
- **281** images (PNG/JPG/WebP/SVG).
- **729 / 729** Godot `.import` source companion files.
- All handoff documentation under `docs/` is retained; GitHub-specific instructions and reports are additional files.

## Opening and building

The Godot project root is `godot/project/`. Open
`godot/project/project.godot` in Godot 4.6.3. Main scene:
`godot/project/main.tscn`. The game client depends on the separate
version-92 authoritative backend for online gameplay.

Typical headless validation, on a workstation equipped with Godot 4.6.3:

```bash
godot --headless --path godot/project --editor --quit
godot --headless --path godot/project --script res://qa_runtime.gd
```

Actual execution status of these commands in a new environment must be
reported by the developer; a successful repository import is not a
runtime test.

## Handoff verification

```bash
python3 godot/tools/verify_drenovar_asset_snapshot.py --require-complete
find godot/project/assets -type f -name '*.glb' | wc -l
find godot/project/assets -type f -name '*.import' | wc -l
```

Read `docs/GITHUB_IMPORT_COMPLETED.md`, `docs/02_FILE_MANIFEST.json`,
`docs/04_ASSET_INVENTORY.json`, `docs/05_SERVER_FILE_MANIFEST.json`,
`docs/06_TROOP_CATALOG.json`, and `docs/07_COMPLETENESS.txt`.

## Scope of completion

This is the **native source handoff for snapshot 0.5.9** — not a newly
optimized build, not a claim of full iPhone 12 acceptance testing and
not proof that all gameplay functionality requested since that snapshot
is implemented. Server v92 source, signed IPA distribution, Apple
credentials, player saves and editable Blender/FBX/PSD project files
remain separate from this native source repository.

The repository is public; verify rights for its assets.
