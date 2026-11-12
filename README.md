# DRENOVAR — native Godot mobile client

**Source snapshot:** DRENOVAR 0.5.9, iOS build 19, Godot 4.6.3 (Godot Mobile renderer).

## Source transfer

**COMPLETE — VERIFIED 12 November 2026.** The original Git handoff bundle
`drenovar-godot-0.5.9.git.bundle` was uploaded to the
[`godot-handoff-v0.5.9` release](https://github.com/ali7prg/Drenovar/releases/tag/godot-handoff-v0.5.9)
and its SHA-256 verified. The native source tree, 447 GLB models,
281 images, 729 Godot asset import metadata files and all
732 inventoried source assets have been imported and checked without hash mismatches.

The original source snapshot contains 1,617 tracked files. This GitHub
repository also includes supplementary import reports and automation,
so the repository's current file count is not required to equal 1,617.

## Open the native project

Open `godot/project/project.godot` in Godot 4.6.3. The main
scene is `godot/project/main.tscn`. Source scripts and shaders are under
`godot/project/src/`; original 3D models and textures are in
`godot/project/assets/`.

Build and platform instructions are under `godot/tools/`,
`godot/.github/workflows/` and `godot/project/export_presets.cfg`.
Review `docs/GITHUB_IMPORT_COMPLETED.md` and
`docs/COMPLETE_IMPORT.md` before development.

## Important boundaries

- **Native client only:** the authoritative online server source **v92 is separate** and not imported here. Full multiplayer features require the server.
- **Not a new app build:** no physical iPhone 12 validation or fresh iOS signing / distribution is implied by the successful source import.
- **Not all editable art originals:** `.blend`, `.fbx`, and `.psd` project files were not part of the handoff. Existing runtime GLB models and textures are present.
- **No signing secrets or personal data:** Apple signing keys, certificates and live player saves are not included.
- **Review rights:** this repository is public. Check third-party art licenses and distribution rights before redistribution.

The previous Unity migration experiment remains separate in
`ali7prg/drenovar-unity`.
