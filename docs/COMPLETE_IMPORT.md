# Complete DRENOVAR Godot source import

Status on 2026-11-12: This repository currently contains a **partial API transfer** of the verified Godot 0.5.9 source. It is NOT a complete build: the majority of GLB, PNG, JPG, WebP and TTF source assets are missing. Do not publish or test builds from the partial checkout.

## Exact full source

The verified local Git bundle contains the complete 1,617-file GitHub-ready handoff. Bundle file: `drenovar-godot-0.5.9.git.bundle`, original source commit `5ae4bc3ec323d78212df7a4d2c17f44a8c0b54a8`. Download it from the owner's ChatGPT conversation artifact. Its original source was `DRENOVAR-iOS-v0.5.9-source.zip` (Godot 4.6.3, iOS build 19).

GitHub cannot import a local bundle directly through the ChatGPT GitHub contents API: the complete binary files must be pushed by an environment with filesystem access and authenticated Git access.

## Complete import using Git

1. Download the Git bundle from the handoff chat onto a machine/cloud workspace with Git installed.
2. Clone this repository and enter it.
3. Fetch the bundle under a temporary reference.
4. Restore the verified contents of the bundle over the partial transfer, commit and push.

```bash
git clone https://github.com/ali7prg/Drenovar.git
cd Drenovar

git fetch /FULL/PATH/drenovar-godot-0.5.9.git.bundle refs/heads/main:refs/remotes/handoff/main
git cat-file -t 5ae4bc3ec323d78212df7a4d2c17f44a8c0b54a8

git restore --source=refs/remotes/handoff/main --staged --worktree -- .
git commit -m "Restore complete verified DRENOVAR Godot 0.5.9 source and assets"
git push origin main
```

Replace `/FULL/PATH/` with the actual local downloaded file path. For a fresh checkout containing only the initial API import, this method preserves this repository's Git history and commits the full file tree in a normal new commit.

## Verify the result

```bash
git ls-files | wc -l
git ls-files 'godot/project/assets/*.glb' 'godot/project/assets/**/*.glb' | wc -l
git ls-files | grep '^godot/project/assets/' | wc -l
```

The target complete handoff has **1,617 tracked files**. Its source snapshot contained 447 GLBs and 732 files inside `godot/project/assets/`, plus 729 Godot `.import` files. Verify actual paths and the file manifest in `docs/02_FILE_MANIFEST.json`; do not rely solely on file counts.

The native client requires the separate backend v92 for complete online gameplay. The signed production IPA, Apple keys and live player saves are not included. No confidential keys should be committed. This repository is currently public; make it private before publishing assets if their distribution rights are not established.
