#!/usr/bin/env python3
"""Build 1024: the game event -> sound -> file table (godot/runtime-audit-1024/audio/events.md).

  python3 -I godot/tools/audio/event_table.py
The event column documents the hooks in the code (src/audio/sound.gd, src/combat_audio.gd, src/main.gd,
src/city_works.gd, src/landscape.gd, src/forest_rescue/game/*); the files come from audio_manifest.json.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.abspath(os.path.join(HERE, "..", "..", "project", "assets", "audio"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "runtime-audit-1024", "audio", "events.md"))

# (area, event, sound, bus, where in the code)
EVENTS = [
    ("UI", "any button press (every BaseButton, hooked on node_added)", "ui/press", "UI", "sound.gd _on_button_pressed"),
    ("UI", "switch / check button", "ui/toggle", "UI", "sound.gd (toggle_mode)"),
    ("UI", "rail tab, medal tab", "ui/tab", "UI", "ui_kit.gd rail_button / rail_medal meta sfx=tab"),
    ("UI", "window opens", "ui/open", "UI", "main.gd open_modal"),
    ("UI", "window closes, × button", "ui/close", "UI", "main.gd close_modal, ui_kit.gd close_button"),
    ("UI", "refused order, server error", "ui/error", "UI", "main.gd show_error, command"),
    ("UI", "market trade", "ui/purchase", "UI", "sound.gd order_cue trade"),
    ("UI", "collect resources", "ui/collect", "UI", "order_cue v6collect / collect"),
    ("UI", "starter reward, forest cage opened, large forest reward", "ui/reward", "UI", "order_cue starter71, adventure_audio"),
    ("UI", "construction / upgrade / move ordered", "ui/build_start", "UI", "order_cue construction, kingdom upgrade…"),
    ("UI", "training, siege, healing ordered", "ui/train", "UI", "order_cue train/siege/heal"),
    ("UI", "speed-up", "ui/speedup", "UI", "order_cue speedup"),
    ("UI", "march / deploy ordered", "ui/march + combat/horn", "UI, SFX", "order_cue deploy/worldMarch/march"),
    ("UI", "building tapped (ring opens)", "ui/building_tap", "UI", "main.gd open_building_ring, walls"),
    ("UI", "volume slider moved (every 10 %)", "ui/slider", "UI", "v6_menu.gd sound_row"),
    ("Forest", "puzzle step right / wrong", "ui/puzzle_right / ui/puzzle_wrong", "UI", "mechanism_ui.gd on_progress"),
    ("Forest", "every adventure button, card tap, rune input (button_pressed)", "ui/press (one per gesture)", "UI", "adventure_audio.gd setup, adventure_hud.gd"),
    ("City", "builder's hammer hits (3D, per builder)", "city/hammer", "SFX", "city_works.gd present_builders"),
    ("City", "lumberjack's axe strikes (3D)", "city/axe", "SFX", "city_works.gd present_lumberjack"),
    ("City", "tree falls (creak, crash on landing)", "city/tree_fall", "SFX", "city_works.gd topple_tree"),
    ("City", "construction / level finished", "city/build_done + stinger construction_done", "SFX, Music", "city_works.gd celebrate"),
    ("Combat", "longbow release", "combat/bow", "SFX", "combat_audio.gd consume (release ENG-03)"),
    ("Combat", "crossbow release", "combat/crossbow", "SFX", "consume (release ENG-04)"),
    ("Combat", "arrow / bolt lands on the creature", "combat/arrow_hit", "SFX", "consume (contact ENG-03/04)"),
    ("Combat", "sword and knight strikes", "combat/clash, combat/flesh", "SFX", "consume (soldier_attack)"),
    ("Combat", "spear strike", "combat/flesh", "SFX", "consume (ENG-01)"),
    ("Combat", "creature hurt (every few hits)", "combat/creature_hurt", "SFX", "consume"),
    ("Combat", "creature killed", "combat/creature_death + combat/fall", "SFX", "consume (creatureHP <= 0)"),
    ("Combat", "creature strikes a shield / armour / soldier", "combat/shield / combat/armor / combat/wood, combat/flesh", "SFX", "consume (creature_attack)"),
    ("Combat", "soldier hurt / killed", "voice/soldier_hurt / voice/soldier_death + combat/fall", "Voice, SFX", "consume"),
    ("Combat", "army reaches the creature (it roars, the men cry)", "combat/creature_roar + voice/war_cry", "SFX, Voice", "landscape.gd fight_started -> combat_audio.fight_begins"),
    ("Combat", "footsteps, hooves (animation contacts)", "combat/foot, combat/hoof", "SFX", "foot_contacts.gd"),
    ("Combat", "javelin", "combat/javelin", "SFX", "combat_audio family javelin"),
    ("Forest", "horse hoof contacts", "combat/hoof", "SFX", "adventure_audio.gd hoof"),
    ("Forest", "horse sets off / joins", "forest/horse_snort, forest/horse_neigh", "SFX", "adventure_audio.gd hoof, forest_game horse_joined"),
    ("Forest", "horse afraid of Teneris", "forest/horse_fear", "SFX", "horse_feared signal"),
    ("Forest", "Teneris / boss roar (lair, boss start)", "forest/roar", "SFX", "creature_roared signal, boss_started"),
    ("Forest", "Teneris attack warning in the fight", "forest/growl", "SFX", "creature_roared during a fight"),
    ("Forest", "fight: squad hits / guardian hits", "combat/clash, combat/flesh, combat/creature_hurt / combat/shield, combat/flesh, voice/soldier_hurt", "SFX, Voice", "fight_hit signal"),
    ("Forest", "fight: death", "combat/creature_death or voice/soldier_death + combat/fall", "SFX, Voice", "fight_hit death"),
    ("Forest", "cage opened", "ui/reward (+ fr_gate_creak, fr_cage_latch)", "UI, SFX", "cage_opened signal"),
    ("Forest", "people rescued, large reward, campaign won", "stinger reward + ui/reward / forest/horse_neigh (+ fr_* cue)", "Music, UI, SFX", "adventure_audio.gd play_cue"),
    ("Forest", "artifact found", "ui/reward (+ fr_artifact_discovery)", "UI, SFX", "adventure_audio.gd play_cue"),
    ("Forest", "fog draws back", "forest/fog_reveal", "SFX", "forest_game.gd on_events fog_revealed"),
    ("Forest", "night animals (every 28–65 s over the forest)", "forest/howl, forest/owl", "SFX", "sound.gd _process"),
    ("Music", "city", "city_irelands_coast <-> city_woodland_fantasy", "Music", "sound.gd wanted_theme"),
    ("Music", "world map", "world_heroic_demise", "Music", "sound.gd"),
    ("Music", "over the forest adventure", "forest_mystery_forest", "Music", "forest_game.gd music_mood"),
    ("Music", "a fight on screen (city, world, forest)", "battle_defying_commodus + ambient battle_din", "Music, Ambient", "battle_fx.last_battle_msec, music_mood battle"),
    ("Music", "battle report: victory / defeat", "stinger victory / defeat", "Music", "main.gd show_report (announced)"),
    ("Ambient", "city", "city_birds + city_market", "Ambient", "sound.gd AMBIENCE"),
    ("Ambient", "world map", "world_wind + city_birds (low)", "Ambient", "sound.gd AMBIENCE"),
    ("Ambient", "forest", "forest_birds + world_wind (low)", "Ambient", "sound.gd AMBIENCE"),
]


def main():
    manifest = json.load(open(os.path.join(AUDIO, "audio_manifest.json")))
    files = {}
    for key in manifest:
        if key.startswith("sfx/"):
            stem = key[4:-4].rsplit("_", 1)[0]
            files.setdefault(stem, []).append(key)
    lines = ["# Build 1024: game events and their sounds", "", "Generated by `godot/tools/audio/event_table.py`.", "",
             "| Area | Event | Sound | Bus | Hook |", "|---|---|---|---|---|"]
    for area, event, sound, bus, hook in EVENTS:
        lines.append("| %s | %s | %s | %s | %s |" % (area, event, sound, bus, hook))
    lines += ["", "## Sound -> files (variations picked at random, never the same twice in a row; pitch ±4 %, level ±1.2 dB)", "",
              "| Sound | Files |", "|---|---|"]
    for stem in sorted(files):
        lines.append("| %s | %s |" % (stem, ", ".join("`%s`" % f for f in sorted(files[stem]))))
    lines.append("")
    lines.append("Music: " + ", ".join("`%s`" % k for k in sorted(manifest) if k.startswith("music/")) + ".")
    lines.append("Stingers: " + ", ".join("`%s`" % k for k in sorted(manifest) if k.startswith("stingers/")) + ".")
    lines.append("Ambient: " + ", ".join("`%s`" % k for k in sorted(manifest) if k.startswith("ambient/")) + ".")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(lines) + "\n")
    print(OUT, len(EVENTS), "events", len(files), "sounds")


if __name__ == "__main__":
    main()
