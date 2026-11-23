#!/usr/bin/env python3
"""Build 1024 audio bank: writes assets/audio/CREDITS.md and src/audio/sound_bank.gd
from assets/audio/audio_manifest.json (made by audio_master.py) and the licence table below.

Run:  python3 -I godot/tools/audio/make_bank.py
Only CC0 and CC-BY 3.0/4.0 sources are allowed; the script stops on anything else.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio_master  # noqa: E402  (the recipe table, for the "changes" column)

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "project"))
AUDIO = os.path.join(PROJECT, "assets", "audio")

CC0 = "CC0 1.0"
BY3 = "CC-BY 3.0"
BY4 = "CC-BY 4.0"
ALLOWED = {CC0, BY3, BY4}
LICENCE_URL = {CC0: "https://creativecommons.org/publicdomain/zero/1.0/",
               BY3: "https://creativecommons.org/licenses/by/3.0/",
               BY4: "https://creativecommons.org/licenses/by/4.0/"}
OGA = "https://opengameart.org/content/"
MP = "Matthew Pablo (www.matthewpablo.com)"

# key -> (title, author, url, licence)
SOURCES = {
    "mp_ireland_live": ("Ireland's Coast (Game Edition - LIVE PLAYERS)", MP, OGA + "irelands-coast-game-edition-live-players", BY3),
    "mp_woodland": ("Woodland Fantasy", MP, OGA + "woodland-fantasy", BY3),
    "mp_heroic_demise": ("Heroic Demise [Updated Version]", MP, OGA + "heroic-demise-updated-version", BY3),
    "az_mystery_forest": ("Mystery Forest", "Alexandr Zhelanov (https://soundcloud.com/alexandr-zhelanov)", OGA + "mystery-forest", BY3),
    "mp_commodus": ("Defying Commodus", MP, OGA + "defying-commodus", BY3),
    "mp_lively_meadow": ("Lively Meadow (Victory Fanfare and Song)", MP, OGA + "lively-meadow-victory-fanfare-and-song", BY3),
    "mp_brother_live": ("You Were My Brother (Live Orchestra)", MP, OGA + "you-were-my-brother-live-orchestra", BY3),
    "kenney_rpg": ("50 RPG sound effects (RPG Audio)", "Kenney (www.kenney.nl)", OGA + "50-rpg-sound-effects", CC0),
    "kenney_interface": ("Interface Sounds", "Kenney (www.kenney.nl)", OGA + "interface-sounds", CC0),
    "rd_rpg": ("80 CC0 RPG SFX", "rubberduck", OGA + "80-cc0-rpg-sfx", CC0),
    "rd_metalwood": ("100 CC0 metal and wood SFX", "rubberduck", OGA + "100-cc0-metal-and-wood-sfx", CC0),
    "rd_creature": ("80 CC0 creature SFX", "rubberduck", OGA + "80-cc0-creature-sfx", CC0),
    "sn_clash": ("20 Sword Sound Effects (Attacks and Clashes)", "StarNinjas", OGA + "20-sword-sound-effects-attacks-and-clashes", CC0),
    "sn_sword": ("20 Sword Sound Effects (Attacks and Clashes)", "StarNinjas", OGA + "20-sword-sound-effects-attacks-and-clashes", CC0),
    "sn_shield": ("10 Impact/Shield Blocks", "StarNinjas", OGA + "10-impactshield-blocks", CC0),
    "ms_impacts": ("Medieval sound effects - Weapon impacts", "MedicineStorm", OGA + "medieval-sound-effects-weapon-impacts", CC0),
    "ms_textures": ("Medieval sound effects - Weapon Textures", "MedicineStorm", OGA + "medieval-sound-effects-weapon-textures", CC0),
    "ad_swishes": ("Swishes Sound Pack", "artisticdude", OGA + "swishes-sound-pack", CC0),
    "cb_gallop": ("Horse gallop on different surfaces (ground, grass, muffled)",
                  "congusbongus; derived from D4XX, StephenSaldanha and MrFizzywig (freesound 564628, 165532, 581834)",
                  OGA + "horse-gallop-on-different-surfaces", CC0),
    "dar_troll": ("Big scary troll sounds", "Darsycho", OGA + "big-scary-troll-sounds", CC0),
    "dar_snarls": ("Monster snarls", "Darsycho", OGA + "monster-snarls", CC0),
    "antum_bear": ("Bear Growls", "AntumDeluge", OGA + "bear-growls", CC0),
    "trazzz_roar": ("CC0 Deep Monster Roar", "trazzz123", OGA + "cc0-deep-monster-roar", CC0),
    "bard_grunts": ("grunts of male death and pain", "thebardofblasphemy", OGA + "grunts-male-death-and-pain", CC0),
}

# Freesound (all CC0 1.0, checked on each sound's page): id -> (title, author)
FREESOUND = {
    "117611": ("wind_howl2_stereo.wav", "swiftoid"), "149024": ("Horse_Whinny.wav", "foxen10"),
    "163453": ("Crossbow Shot", "LeMudCrab"), "204946": ("Hammering_Wood.wav", "CapsLok"),
    "205938": ("Arrow Impact", "Twisted_Euphoria"), "259542": ("stabs.wav", "nicktermer"),
    "274175": ("Park ambience - mostly birds", "Mafon2"), "338260": ("Money Bag", "PhilSavlem"),
    "350428": ("Trumpet Fanfare", "bevibeldesign"), "380156": ("Howl_Echo.wav", "taure"),
    "385280": ("sfx_amb_forest_spring_afternoon-01.wav", "bajko"), "392180": ("Battle_horn_1.wav", "kirmm"),
    "394179": ("Longbow Release 2.wav", "saturdaysoundguy"), "397548": ("Page Turn 01", "LilMati"),
    "398430": ("Wolf howl", "NaturesTemper"), "402753": ("medieval horn by kris klavenes", "klavo1985"),
    "403003": ("magical rising wind or sea", "martian"), "419928": ("Chopping wood.wav", "14FPanskaSilovsky_Petr"),
    "421928": ("Chopping wood 01", "micahlg"), "421929": ("Chopping wood 02", "micahlg"),
    "424790": ("Crowded street at medieval market", "bolkmar"), "437110": ("G38-15-Perfect Horse Whinny.wav", "craigsmith"),
    "437111": ("G38-16-Four Horse Snorts.wav", "craigsmith"), "465697": ("Owl Hoot", "Breviceps"),
    "479674": ("R13-02-Scared Neighs.wav", "craigsmith"), "494071": ("Big Tree Fall in Forest", "Kinoton"),
    "521552": ("Arrow Impact", "omerbhatti34"), "521830": ("Middle Ages War Cry.wav", "joelcarrsound"),
    "521831": ("Middle Ages War Cry 3.wav", "joelcarrsound"), "521832": ("Middle Ages War Cry 2.wav", "joelcarrsound"),
    "538697": ("horse snort.wav", "bruno.auzet"), "539956": ("war horn.wav", "adharca"),
    "540139": ("Hitting nails with Hammer.wav", "aidansamuel"), "547209": ("Voice_AdultMale_PainGrunts_09.wav", "MrFossy"),
    "563011": ("People screaming in agony when charging into battle", "florianreichelt"),
    "610703": ("Good answer harp glissando.wav", "oggraphics"), "610998": ("Medium Male Pain Grunts", "unfa"),
    "708223": ("Arrow_Hit_1", "Mythmazter"), "715784": ("Magic Whoosh", "DustyWind"),
    "734841": ("dyingBeast", "QuantumFellow"), "85568": ("DRAGON_ROAR.wav", "JoelAudio"),
}
for fid, (title, author) in FREESOUND.items():
    SOURCES["fs_" + fid] = (title, author, "https://freesound.org/s/%s/" % fid, CC0)

THEME_OF = {"city_irelands_coast": "city", "city_woodland_fantasy": "city", "world_heroic_demise": "world",
            "forest_mystery_forest": "forest", "battle_defying_commodus": "battle"}


def recipe_changes(key, entry):
    kind = entry["kind"]
    if kind == "music":
        return ("cut to a seamless loop (loop start %.2f s, %.0f s file, equal-power seam), fade-in, "
                "loudness -16 LUFS, true peak <= -1 dBTP, OGG Vorbis q5 stereo" % (entry["loop_offset"], entry["duration"]))
    if kind == "stinger":
        return "excerpt %.1f s with a fade-out, loudness about -16 LUFS, true peak <= -1 dBTP, OGG q5" % entry["duration"]
    if kind == "ambient":
        return "loop excerpt %.0f s with a crossfaded seam, -20 LUFS, OGG q3" % entry["duration"]
    stem, index = key[4:-4].rsplit("_", 1)
    v = audio_master.SFX[stem][int(index)]
    parts = []
    if "seg" in v:
        parts.append("segment %.1f-%.1f s" % v["seg"])
    elif "pick" in v:
        parts.append("one take (rank %d) cut from a multi-take file" % v["pick"])
    else:
        parts.append("trimmed")
    if v.get("semitones"):
        parts.append("pitch %+d semitones" % v["semitones"])
    for layer in v.get("layers", []):
        parts.append("layered with %s (%s, %+d dB)" % (os.path.basename(layer["src"]), layer["lic"], layer.get("gain", 0)))
    parts.append("fades, peak-normalized, %s OGG q4" % ("stereo" if entry.get("channels") == 2 else "mono"))
    return ", ".join(parts)


def main():
    manifest = json.load(open(os.path.join(AUDIO, "audio_manifest.json")))
    for key in manifest:
        if not os.path.exists(os.path.join(AUDIO, key)):
            sys.exit("missing file " + key)
    uses = {}
    for key, entry in manifest.items():
        for lic in entry.get("lic_all", [entry["lic"]]):
            if lic not in SOURCES:
                sys.exit("no licence record for %s (%s)" % (lic, key))
            if SOURCES[lic][3] not in ALLOWED:
                sys.exit("licence not allowed: %s" % lic)
            uses.setdefault(lic, []).append(key)

    lines = ["# DRENOVAR audio credits (build 1024)", "",
             "Every file in `assets/audio/` is listed here. Only CC0 1.0 and CC-BY 3.0/4.0 sources are used;",
             "no NC, SA, personal-use or ripped material. Generated by `godot/tools/audio/make_bank.py` from",
             "`audio_manifest.json`; the processing itself is `godot/tools/audio/audio_master.py`.", "",
             "Older project-original sounds (not listed per file): `assets/forest_rescue/audio/fr_*.ogg` are procedural",
             "synthesis made for the project (see `src/forest_rescue/delivery/docs/AUDIO_RU.md`).", "",
             "## Attribution (CC-BY)", ""]
    for lic in sorted(uses):
        title, author, url, licence = SOURCES[lic]
        if licence != CC0:
            lines.append("- \"%s\" by %s, %s, licensed %s (%s). Edited: looped/excerpted and mastered." % (title, author, url, licence, LICENCE_URL[licence]))
    lines += ["", "## Sources", "", "| Key | Title | Author | Source | Licence | Files |", "|---|---|---|---|---|---|"]
    for lic in sorted(uses):
        title, author, url, licence = SOURCES[lic]
        files = ", ".join("`%s`" % k for k in sorted(uses[lic]))
        lines.append("| %s | %s | %s | %s | %s | %s |" % (lic, title.replace("|", "/"), author, url, licence, files))
    lines += ["", "## Files and changes", "", "| File | Sources | Licence | Changes |", "|---|---|---|---|"]
    for key in sorted(manifest):
        entry = manifest[key]
        lics = entry.get("lic_all", [entry["lic"]])
        licences = sorted({SOURCES[l][3] for l in lics})
        lines.append("| `%s` | %s | %s | %s |" % (key, ", ".join(lics), ", ".join(licences), recipe_changes(key, entry)))
    open(os.path.join(AUDIO, "CREDITS.md"), "w").write("\n".join(lines) + "\n")

    variants = {}
    for key, entry in manifest.items():
        if entry["kind"] == "sfx":
            stem = key[4:-4].rsplit("_", 1)[0]
            variants[stem] = variants.get(stem, 0) + 1
    music = {}
    for key, entry in manifest.items():
        if entry["kind"] == "music":
            name = os.path.basename(key)[:-4]
            music[name] = {"path": "res://assets/audio/" + key, "theme": THEME_OF[name], "loop_offset": entry["loop_offset"],
                           "duration": entry["duration"]}
    credits = []
    for lic in sorted(uses, key=lambda l: (SOURCES[l][3] == CC0, l)):
        title, author, url, licence = SOURCES[lic]
        credits.append([title, author, licence, url])
    allowed_by_file = {key: sorted({SOURCES[l][3] for l in e.get("lic_all", [e["lic"]])}) for key, e in manifest.items()}
    gd = ["## Generated by godot/tools/audio/make_bank.py from assets/audio/audio_manifest.json. Do not edit.",
          "extends RefCounted", "",
          "const ROOT := \"res://assets/audio/\"",
          "## sfx stem -> number of variants (files sfx/<stem>_<i>.ogg)",
          "const VARIANTS := " + json.dumps(dict(sorted(variants.items()))),
          "## music file -> theme, loop start and length (seconds)",
          "const MUSIC := " + json.dumps(dict(sorted(music.items()))),
          "## credits shown in the settings window: [title, author, licence, url]",
          "const CREDITS := " + json.dumps(credits, ensure_ascii=False),
          "## every audio file -> its licences (checked by qa_audio_1024)",
          "const LICENCES := " + json.dumps(dict(sorted(allowed_by_file.items()))), ""]
    os.makedirs(os.path.join(PROJECT, "src", "audio"), exist_ok=True)
    open(os.path.join(PROJECT, "src", "audio", "sound_bank.gd"), "w").write("\n".join(gd))
    print("sources", len(uses), "files", len(manifest), "stems", len(variants))


if __name__ == "__main__":
    main()
