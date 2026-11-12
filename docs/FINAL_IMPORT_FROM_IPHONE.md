# Finalize the complete DRENOVAR import from iPhone

The complete source Git bundle is retained in the founder's ChatGPT Library as
`drenovar-godot-0.5.9.git.bundle` (98,354,805 bytes).

The native source has 1,617 Git-tracked files including 447 GLBs, 732 original
asset files and 729 Godot import metadata files.

## One-time release upload

GitHub Actions cannot read an archive in a private ChatGPT file library.
To transfer the exact binaries without a computer or Git CLI:

1. Download `drenovar-godot-0.5.9.git.bundle` from the ChatGPT conversation
   or the ChatGPT Library to your iPhone Files app.
2. Open https://github.com/ali7prg/Drenovar/releases/new
3. Set tag `godot-handoff-v0.5.9`. Add a release title.
4. Attach the exact `drenovar-godot-0.5.9.git.bundle` as a **binary asset**,
   not inside a ZIP, then publish the release.
5. GitHub automatically runs
   `.github/workflows/complete-drenovar-import.yml`, checks SHA256 and
   imports the *entire exact source tree*. It never accepts a different bundle.
6. Confirm green Actions run and read `docs/GITHUB_IMPORT_COMPLETED.md`.

Release asset checksum:
`9888e56de53cd2bc4936e5e19768a54de690afd30767869d0db429369c773366`.

The workflow uses a normal Git commit; it never force-pushes or rewrites existing
history. This applies to the native Godot code, not the separate server v92.
The server archive, API secrets, Apple signing data and live player saves are not
included. Do not claim a playable online build until backend and runtime QA pass.

This repository is public. Confirm art distribution rights or make it private
before publishing the full asset set.
