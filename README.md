# DRENOVAR — Godot native client

**Source baseline:** Godot 4.6.3, GDScript, client 0.5.9 / iOS build 19. Backend baseline v92 (separate source).

## Migration status

**PARTIAL IMPORT IN PROGRESS — DO NOT BUILD OR DISTRIBUTE YET.** Complete 3D assets and textures are required. A verified source archive and Git bundle have been prepared for the full import. GitHub contents API upload does not automatically transfer those binary assets.

## Project

- `godot/project/project.godot` — main Godot configuration
- `godot/project/main.tscn` — entry scene
- `godot/project/src/` — gameplay, world, UI and session logic
- `godot/project/assets/` — models and textures (required; upload still pending)
- `docs/` — source inventory and handoff

This repo is currently public. Do not commit API tokens, player saves, certificates or signing keys. Keep the earlier `drenovar-unity` experiment separate.
