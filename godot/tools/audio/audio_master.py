#!/usr/bin/env python3
"""DRENOVAR build 1024 — audio mastering pipeline (music, stingers, SFX, ambience).

Reads the licensed source downloads (see godot/project/assets/audio/CREDITS.md for every
source URL and licence) from SOURCES (a directory with one sub-directory per download, the
layout the sourcing step left in the scratchpad), and writes the game's OGG Vorbis files
into godot/project/assets/audio/ together with audio_manifest.json (per file: source,
licence key, loop offset, duration, loudness).

  python3 -I godot/tools/audio/audio_master.py SOURCES [--only PREFIX]

Mastering rules (task 1024):
- music: seamless loop (loopfind.py), -16 LUFS integrated, true peak <= -1 dBTP,
  44.1 kHz stereo, Vorbis q5; the game loops it from `loop_offset`.
- stingers: -16 LUFS, <= -1 dBTP, stereo q5, short fade-out.
- SFX: mono (spatial) unless marked stereo, leading silence cut to <= 2 ms, tail fade,
  sample peak -3 dBFS (true peak checked <= -1 dBTP after encoding), Vorbis q4.
- ambience beds: seamless crossfaded loop, -20 LUFS, Vorbis q3 (stereo).
Only ffmpeg and numpy are used; nothing from the downloads is executed.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loopfind  # noqa: E402

SR = 44100
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "project", "assets", "audio"))

# ----------------------------------------------------------------------------- recipes
# src paths are relative to SOURCES. "lic" is a key of LICENSES in credits.py.
MUSIC = [
    # City / base: calm-heroic. Two pieces alternate (the director rotates after one loop).
    {"out": "music/city_irelands_coast.ogg", "src": "ireland_live/Ireland%27s%20Coast%20%28Video%20Game%20Soundtrack%20-Live%29_0.mp3",
     "lic": "mp_ireland_live", "start": (95, 125), "end": (180, 200), "len": (70, 95)},
    {"out": "music/city_woodland_fantasy.ogg", "src": "woodland_fantasy/Woodland%20Fantasy_0.mp3",
     "lic": "mp_woodland", "start": (20, 45), "end": (105, 140), "len": (80, 110)},
    # World map: heroic, adventurous (choir and strings; the main section repeats almost exactly).
    {"out": "music/world_heroic_demise.ogg", "src": "heroic_demise/Heroic%20Demise%20%28New%29_0.mp3",
     "lic": "mp_heroic_demise", "start": (45, 75), "end": (190, 230), "len": (140, 170)},
    # Forest adventure: mysterious, tense.
    {"out": "music/forest_mystery_forest.ogg", "src": "mystery_forest/Mystery%20Forest.ogg",
     "lic": "az_mystery_forest", "start": (30, 60), "end": (90, 125), "len": (55, 75)},
    # Battle / fight: epic, driving (the action section of a film cue; the quiet opening is cut).
    {"out": "music/battle_defying_commodus.ogg", "src": "defying_commodus/Defying%20Commodus_0.mp3",
     "lic": "mp_commodus", "trim": 15.0, "start": (20, 75), "end": (60, 124), "len": (40, 56)},
]

STINGERS = [
    {"out": "stingers/victory.ogg", "src": "lively_meadow/x/Lively Meadow Collection/Lively Meadow Victory Fanfare.wav", "lic": "mp_lively_meadow",
     "seg": (0.0, 7.5), "fade": 0.6},
    {"out": "stingers/defeat.ogg", "src": "brother_live/Tropic%20Strike%20-%201M2%20-%20_You%20Were%20My%20Brother__0.mp3",
     "lic": "mp_brother_live", "seg": (2.0, 7.0), "fade": 2.5},
    {"out": "stingers/construction_done.ogg", "src": "fs_350428/350428_4557960-hq.ogg", "lic": "fs_350428",
     "seg": (0.0, 6.6), "fade": 1.0},
    {"out": "stingers/reward.ogg", "src": "fs_610703/610703_7772719-hq.ogg", "lic": "fs_610703",
     "seg": (0.0, 3.2), "fade": 1.0},
]

AMBIENT = [
    {"out": "ambient/city_birds.ogg", "src": "fs_274175/274175_1196472-hq.ogg", "lic": "fs_274175", "seg": (2.0, 46.0)},
    {"out": "ambient/city_market.ogg", "src": "fs_424790/424790_2927958-hq.ogg", "lic": "fs_424790", "seg": (0.0, 8.6), "xfade": 1.0},
    {"out": "ambient/world_wind.ogg", "src": "fs_117611/117611_854782-hq.ogg", "lic": "fs_117611", "seg": (1.0, 33.0)},
    {"out": "ambient/forest_birds.ogg", "src": "fs_385280/385280_2341984-hq.ogg", "lic": "fs_385280", "seg": (10.0, 58.0)},
    {"out": "ambient/battle_din.ogg", "src": "fs_563011/563011_6253486-hq.ogg", "lic": "fs_563011", "seg": (1.0, 16.0),
     "af": "highpass=f=120,lowpass=f=5200", "xfade": 1.5},
]


def S(src, lic, **kw):
    d = {"src": src, "lic": lic}
    d.update(kw)
    return d


K_INT = "k_interface/x/Audio/"
K_RPG = "k_rpg/x/OGG/"
RD_RPG = "rd_rpg/x/"
RD_MW = "rd_metalwood/x/"
RD_CR = "rd_creature/x/"
RD_BR = "rd_break/x/"
MS_I = "ms_impacts/x/"
MS_I2 = "ms_impacts2/x/"
MS_T = "ms_textures/x/"

# event file stem -> list of variants. A variant is one source (optionally a segment, an
# automatic pick among the hits of a multi-take file, a pitch shift) and optional layers.
SFX = {
    # ---------------------------------------------------------------- UI (bus UI, 2D)
    "ui/press": [S(K_RPG + "bookPlace1.ogg", "kenney_rpg", layers=[S(K_INT + "click_003.ogg", "kenney_interface", gain=-14)], maxlen=0.22),
                 S(K_RPG + "bookPlace2.ogg", "kenney_rpg", layers=[S(K_INT + "click_002.ogg", "kenney_interface", gain=-14)], maxlen=0.22),
                 S(K_RPG + "bookPlace3.ogg", "kenney_rpg", layers=[S(K_INT + "click_003.ogg", "kenney_interface", gain=-14)], maxlen=0.22)],
    "ui/toggle": [S(K_RPG + "metalLatch.ogg", "kenney_rpg", maxlen=0.25), S(RD_RPG + "lock_02.ogg", "rd_rpg", maxlen=0.25)],
    "ui/tab": [S("fs_397548/397548_6142149-hq.ogg", "fs_397548", maxlen=0.45), S(K_RPG + "bookFlip2.ogg", "kenney_rpg", maxlen=0.4),
               S(K_RPG + "bookFlip3.ogg", "kenney_rpg", maxlen=0.3)],
    "ui/open": [S(RD_RPG + "book_01.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.5, fade=0.15), S(RD_RPG + "book_03.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.5, fade=0.15)],
    "ui/close": [S(K_RPG + "bookClose.ogg", "kenney_rpg", maxlen=0.3)],
    "ui/error": [S(RD_RPG + "wood_03.ogg", "rd_rpg", maxlen=0.3, semitones=-3, layers=[S(K_INT + "error_008.ogg", "kenney_interface", gain=-9)]),
                 S(K_RPG + "dropLeather.ogg", "kenney_rpg", maxlen=0.3, layers=[S(K_INT + "error_008.ogg", "kenney_interface", gain=-9)])],
    "ui/purchase": [S(K_RPG + "handleCoins.ogg", "kenney_rpg", keep=True, soft=True, maxlen=0.8), S(K_RPG + "handleCoins2.ogg", "kenney_rpg", keep=True, soft=True, maxlen=0.5),
                    S(RD_RPG + "item_coins_01.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.5)],
    "ui/collect": [S(RD_RPG + "item_coins_02.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.7), S(RD_RPG + "item_coins_03.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.6),
                   S("fs_338260/338260_4136102-hq.ogg", "fs_338260", keep=True, soft=True, maxlen=1.2)],
    "ui/reward": [S(RD_RPG + "item_gem_04.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.7), S(RD_RPG + "item_gem_01.ogg", "rd_rpg", keep=True, soft=True, maxlen=0.4)],
    "ui/slider": [S(K_INT + "tick_002.ogg", "kenney_interface", maxlen=0.06)],
    "ui/puzzle_right": [S(RD_RPG + "item_gem_01.ogg", "rd_rpg", maxlen=0.4, layers=[S(K_RPG + "metalLatch.ogg", "kenney_rpg", gain=-8)])],
    "ui/puzzle_wrong": [S(RD_RPG + "wood_03.ogg", "rd_rpg", maxlen=0.35, semitones=-5, layers=[S(K_RPG + "creak3.ogg", "kenney_rpg", gain=-8)])],
    "ui/train": [S(K_RPG + "drawKnife3.ogg", "kenney_rpg", maxlen=0.45), S(K_RPG + "drawKnife2.ogg", "kenney_rpg", maxlen=0.45)],
    "ui/speedup": [S("swishes/x/swishes/swish-7.wav", "ad_swishes", maxlen=0.5), S("swishes/x/swishes/swish-9.wav", "ad_swishes", maxlen=0.5)],
    "ui/build_start": [S(RD_MW + "wood_hammer_01.ogg", "rd_metalwood", keep=True, soft=True, maxlen=0.9), S(RD_MW + "wood_hammer_02.ogg", "rd_metalwood", keep=True, soft=True, maxlen=0.9)],
    "ui/building_tap": [S(RD_RPG + "wood_03.ogg", "rd_rpg", maxlen=0.25), S(RD_RPG + "wood_05.ogg", "rd_rpg", maxlen=0.25)],
    "ui/march": [S("fs_392180/392180_4478330-hq.ogg", "fs_392180", keep=True, soft=True, maxlen=3.6, fade=0.9, stereo=True),
                 S("fs_402753/402753_4701691-hq.ogg", "fs_402753", keep=True, soft=True, maxlen=3.6, fade=0.9, stereo=True)],
    # ---------------------------------------------------------------- city works (spatial)
    "city/hammer": [S("fs_204946/204946_850742-hq.ogg", "fs_204946", pick=0, maxlen=0.45),
                    S("fs_204946/204946_850742-hq.ogg", "fs_204946", pick=1, maxlen=0.45),
                    S("fs_540139/540139_10965608-hq.ogg", "fs_540139", pick=0, maxlen=0.45),
                    S(RD_MW + "hammer_02.ogg", "rd_metalwood", maxlen=0.45)],
    "city/axe": [S("fs_421928/421928_8090574-hq.ogg", "fs_421928", maxlen=0.5), S("fs_421929/421929_8090574-hq.ogg", "fs_421929", maxlen=0.5),
                 S("fs_419928/419928_8373708-hq.ogg", "fs_419928", pick=0, maxlen=0.6)],
    "city/tree_fall": [S("fs_494071/494071_2247456-hq.ogg", "fs_494071", keep=True, soft=True, seg=(3.3, 3.6), fade=0.8)],
    "city/build_done": [S(RD_RPG + "item_gem_04.ogg", "rd_rpg", maxlen=0.7, layers=[S(RD_MW + "wood_slam_01.ogg", "rd_metalwood", gain=-6)])],
    # ---------------------------------------------------------------- combat (spatial)
    "combat/clash": [S("sn_clash/x/sword_clash.%d.ogg" % i, "sn_clash", maxlen=0.7) for i in (1, 3, 5, 7)]
                    + [S(MS_I + "Sabre Norse Sword Blade on Blade.wav", "ms_impacts", pick=0, maxlen=0.8),
                       S(MS_I2 + "Spear Norse Sword Blade on Blade.wav", "ms_impacts", pick=1, maxlen=0.8)],
    "combat/swing": [S("sn_sword/x/sword - StarNinjas/sword.%d.ogg" % i, "sn_sword", maxlen=0.5) for i in (1, 4, 7)],
    "combat/shield": [S("sn_shield/x/impact.%d.ogg" % i, "sn_shield", maxlen=0.6) for i in (1, 4, 8)],
    "combat/flesh": [S("fs_259542/259542_2316086-hq.ogg", "fs_259542", pick=i, maxlen=0.45) for i in (0, 1, 2)]
                    + [S(K_RPG + "knifeSlice2.ogg", "kenney_rpg", maxlen=0.4)],
    "combat/armor": [S(MS_I + "Mace Norse Sword Blade.wav", "ms_impacts", pick=0, maxlen=0.7),
                     S(MS_I + "Mace Sabre Blade.wav", "ms_impacts", pick=0, maxlen=0.7),
                     S(RD_MW + "metal_hit_02.ogg", "rd_metalwood", maxlen=0.6)],
    "combat/wood": [S("sn_shield/x/impact.%d.ogg" % i, "sn_shield", maxlen=0.6) for i in (2, 6)]
                   + [S(MS_I + "Axe Spear Haft on Haft.wav", "ms_impacts", pick=0, maxlen=0.6)],
    "combat/bow": [S("fs_394179/394179_7280678-hq.ogg", "fs_394179", maxlen=0.6), S(MS_T + "English Longbow Shoot.wav", "ms_textures", pick=0, maxlen=0.7),
                   S(MS_T + "Scythian Recurve Shoot.wav", "ms_textures", pick=0, maxlen=0.7)],
    "combat/crossbow": [S(MS_T + "Crossbow Shoot.wav", "ms_textures", pick=0, maxlen=0.8), S("fs_163453/163453_2263027-hq.ogg", "fs_163453", maxlen=0.5)],
    "combat/arrow_hit": [S("fs_205938/205938_3842302-hq.ogg", "fs_205938", maxlen=0.5), S("fs_521552/521552_11543986-hq.ogg", "fs_521552", maxlen=0.4),
                         S("fs_708223/708223_14777969-hq.ogg", "fs_708223", maxlen=0.7)],
    "combat/javelin": [S("swishes/x/swishes/swish-%d.wav" % i, "ad_swishes", maxlen=0.45) for i in (3, 5)],
    "combat/foot": [S(K_RPG + "footstep0%d.ogg" % i, "kenney_rpg", maxlen=0.25) for i in (1, 4, 7)],
    "combat/hoof": [S("horse_gallop_cb/x/ground.mp3", "cb_gallop", maxlen=0.35), S("horse_gallop_cb/x/grass.mp3", "cb_gallop", maxlen=0.35),
                    S("horse_gallop_cb/x/muffled.mp3", "cb_gallop", maxlen=0.35)],
    "combat/fall": [S(K_RPG + "dropLeather.ogg", "kenney_rpg", maxlen=0.6, keep=True, layers=[S(RD_MW + "metal_falling_01.ogg", "rd_metalwood", gain=-9, keep=True)]),
                    S(K_RPG + "dropLeather.ogg", "kenney_rpg", maxlen=0.6, semitones=-2, keep=True, layers=[S(K_RPG + "beltHandle1.ogg", "kenney_rpg", gain=-10)])],
    "combat/creature_hurt": [S(RD_CR + "hurt_0%d.ogg" % i, "rd_creature", soft=True, maxlen=0.9) for i in (1, 3, 5)],
    "combat/creature_roar": [S("troll/troll-roars_0.ogg", "dar_troll", pick=0, soft=True, maxlen=2.4, fade=0.4),
                             S("bear/x/ogg/bear_01.ogg", "antum_bear", soft=True, maxlen=1.2), S("troll/troll-roars_0.ogg", "dar_troll", pick=1, soft=True, maxlen=2.4, fade=0.4)],
    "combat/creature_death": [S("fs_734841/734841_14713973-hq.ogg", "fs_734841", soft=True, maxlen=3.0, fade=0.8), S(RD_CR + "scream_02.ogg", "rd_creature", soft=True, maxlen=1.6, fade=0.4)],
    "combat/horn": [S("fs_539956/539956_4366671-hq.ogg", "fs_539956", keep=True, soft=True, maxlen=4.0, fade=1.0)],
    # ---------------------------------------------------------------- voices (bus Voice, spatial)
    "voice/war_cry": [S("fs_521830/521830_3718141-hq.ogg", "fs_521830", keep=True, soft=True, maxlen=1.9), S("fs_521831/521831_3718141-hq.ogg", "fs_521831", keep=True, soft=True, maxlen=2.7),
                      S("fs_521832/521832_3718141-hq.ogg", "fs_521832", keep=True, soft=True, maxlen=1.2)],
    "voice/soldier_death": [S("grunts/death%20pain%20grunts.wav", "bard_grunts", pick=i, soft=True, maxlen=1.2, fade=0.25) for i in (0, 2, 4)],
    "voice/soldier_hurt": [S("fs_610998/610998_1038806-hq.ogg", "fs_610998", pick=i, soft=True, maxlen=0.8, fade=0.15) for i in (0, 3)]
                          + [S("fs_547209/547209_129727-hq.ogg", "fs_547209", soft=True, maxlen=0.4)],
    # ---------------------------------------------------------------- forest adventure
    "forest/horse_neigh": [S("fs_149024/149024_2581089-hq.ogg", "fs_149024", soft=True, maxlen=2.4, fade=0.5),
                           S("fs_437110/437110_2524442-hq.ogg", "fs_437110", pick=0, soft=True, maxlen=2.4, fade=0.5)],
    "forest/horse_snort": [S("fs_437111/437111_2524442-hq.ogg", "fs_437111", pick=i, soft=True, maxlen=1.0, fade=0.2) for i in (0, 1, 2)]
                          + [S("fs_538697/538697_11519060-hq.ogg", "fs_538697", pick=0, soft=True, maxlen=1.0, fade=0.2)],
    "forest/horse_fear": [S("fs_479674/479674_2524442-hq.ogg", "fs_479674", pick=i, soft=True, maxlen=2.2, fade=0.4) for i in (0, 1)],
    "forest/roar": [S("fs_85568/85568_1206321-hq.ogg", "fs_85568", soft=True, maxlen=2.4, fade=0.5),
                    S("deep_roar/monster_roar.wav", "trazzz_roar", soft=True, maxlen=4.0, fade=0.8)],
    "forest/growl": [S("snarls/monster-snarls_0.ogg", "dar_snarls", pick=i, soft=True, maxlen=1.8, fade=0.35) for i in (0, 1)]
                    + [S("snarls/monster-snarl-attack.ogg", "dar_snarls", pick=0, soft=True, maxlen=1.6, fade=0.3)],
    "forest/fog_reveal": [S("fs_715784/715784_7943867-hq.ogg", "fs_715784", keep=True, soft=True, maxlen=0.9, fade=0.3),
                          S("fs_403003/403003_84709-hq.ogg", "fs_403003", keep=True, soft=True, seg=(1.5, 3.0), fade=1.0)],
    "forest/howl": [S("fs_398430/398430_3862281-hq.ogg", "fs_398430", keep=True, soft=True, maxlen=6.5, fade=1.2), S("fs_380156/380156_2940947-hq.ogg", "fs_380156", keep=True, soft=True, seg=(2.4, 7.0), fade=2.0)],
    "forest/owl": [S("fs_465697/465697_9159316-hq.ogg", "fs_465697", keep=True, soft=True, maxlen=2.5, fade=0.6)],
}


# ----------------------------------------------------------------------------- helpers
def decode(path, stereo=False, af=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "2" if stereo else "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    return x.reshape(-1, 2) if stereo else x


def to_mono(x):
    return x if x.ndim == 1 else x.mean(1)


def envelope(x, win=0.005):
    m = np.abs(to_mono(x))
    n = max(1, int(win * SR))
    k = np.ones(n) / n
    return np.convolve(m, k, mode="same")


def onsets(x, min_gap=0.25, rel_db=-24.0):
    """Start samples of the distinct hits of a multi-take file (loudest first by peak)."""
    env = envelope(x, 0.004)
    peak = env.max() + 1e-12
    thr = peak * 10 ** (rel_db / 20)
    floor = peak * 10 ** ((rel_db - 14) / 20)
    hits = []
    i = 0
    gap = int(min_gap * SR)
    n = len(env)
    while i < n:
        if env[i] > thr:
            start = i
            while start > 0 and env[start - 1] > floor and i - start < int(0.05 * SR):
                start -= 1
            seg_end = min(n, i + gap)
            local_peak = env[i:seg_end].max()
            hits.append((start, float(local_peak)))
            j = seg_end
            while j < n and env[j] > floor:
                j += 1
            i = max(j, seg_end)
        else:
            i += 1
    return hits


def trim(x, rel_db_head=-45.0, rel_db_tail=-60.0, pre=0.002):
    m = np.abs(to_mono(x))
    peak = m.max() + 1e-12
    on = np.where(m > peak * 10 ** (rel_db_head / 20))[0]
    tail = np.where(m > peak * 10 ** (rel_db_tail / 20))[0]
    if len(on) == 0:
        return x
    a = max(0, on[0] - int(pre * SR))
    b = tail[-1] + 1
    return x[a:b]


def fades(x, fin=0.001, fout=0.015):
    x = x.copy()
    n_in = max(1, int(fin * SR))
    n_out = min(len(x) - 1, max(1, int(fout * SR)))
    shape_in = np.linspace(0, 1, n_in, dtype=np.float32)
    shape_out = np.cos(np.linspace(0, np.pi / 2, n_out, dtype=np.float32)) ** 2
    if x.ndim == 2:
        shape_in, shape_out = shape_in[:, None], shape_out[:, None]
    x[:n_in] *= shape_in
    x[-n_out:] *= shape_out
    return x


def pitch(x, semitones):
    if not semitones:
        return x
    ratio = 2 ** (semitones / 12)
    idx = np.arange(0, len(x) - 1, ratio)
    lo = np.floor(idx).astype(int)
    frac = (idx - lo).astype(np.float32)
    if x.ndim == 2:
        frac = frac[:, None]
    return x[lo] * (1 - frac) + x[lo + 1] * frac


def peak_normalize(x, target_db=-3.0):
    pk = np.abs(x).max() + 1e-12
    return x * (10 ** (target_db / 20) / pk)


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    s = r[r.rfind("Summary:"):]
    def g(k):
        m = re.search(k + r":\s+(-?[\d.]+|-inf)", s)
        return float(m.group(1).replace("-inf", "-120")) if m else None
    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak")}


def write_ogg(x, out, quality):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stereo = x.ndim == 2
    raw = np.ascontiguousarray(np.clip(x, -1, 1).astype(np.float32)).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2" if stereo else "1", "-i", "-",
                    "-c:a", "libvorbis", "-q:a", str(quality), "-map_metadata", "-1", out], input=raw, check=True)


def encode_checked(y, out, quality, ceiling=-1.0):
    """Encode, then re-limit until the decoded true peak is under the ceiling (Vorbis can
    overshoot the PCM peak by a few tenths of a dB)."""
    guard = -1.6
    for _ in range(4):
        write_ogg(y, out, quality)
        m = lufs(out)
        if m["TP"] is None or m["TP"] <= ceiling - 0.05:
            return y, m
        pk_db = 20 * np.log10(np.abs(y).max() + 1e-12)
        guard = min(guard, pk_db) - (m["TP"] - ceiling) - 0.25
        y = true_peak_guard(y, guard)
    return y, m


def loudness_gain(x, target):
    tmp = "/tmp/_dren_lufs.wav"
    raw = np.ascontiguousarray(np.clip(x, -1, 1).astype(np.float32)).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2" if x.ndim == 2 else "1", "-i", "-", tmp],
                   input=raw, check=True)
    m = lufs(tmp)
    os.remove(tmp)
    return 10 ** ((target - m["I"]) / 20)


def true_peak_guard(x, ceiling_db=-1.6):
    """Gentle soft-knee peak control: samples above the ceiling are compressed with a smooth
    gain envelope (5 ms attack, 80 ms release) rather than clipped."""
    ceiling = 10 ** (ceiling_db / 20)
    level = np.abs(x).max(1) if x.ndim == 2 else np.abs(x)
    if level.max() <= ceiling:
        return x
    need = np.minimum(1.0, ceiling / np.maximum(level, 1e-9))
    rel = np.exp(-1 / (0.08 * SR))
    g = np.empty_like(need)
    cur = 1.0
    # backward pass gives look-ahead (attack), forward pass gives release
    for i in range(len(need) - 1, -1, -1):
        cur = min(need[i], cur * rel + (1 - rel))
        g[i] = cur
    cur = 1.0
    for i in range(len(g)):
        cur = min(g[i], cur * rel + (1 - rel))
        g[i] = cur
    return x * (g[:, None] if x.ndim == 2 else g)


# ----------------------------------------------------------------------------- builders
def build_music(src_root, r, manifest):
    x = decode(os.path.join(src_root, r["src"]), stereo=True)
    if r.get("trim"):
        x = x[int(r["trim"] * SR):]
    a, b, score = loopfind.find_loop(x, r["start"], r["end"], r["len"][0], r["len"][1])
    y = loopfind.render_loop(x, a, b)
    # No silence before the first note (the director may start the file from 0 in a crossfade).
    mono = np.abs(to_mono(y))
    lead = int(np.argmax(mono > mono.max() * 10 ** (-45 / 20)))
    cut = max(0, lead - int(0.002 * SR))
    y, a, b = y[cut:], a - cut, b - cut
    n_in = int((0.25 if r.get("trim") else 0.004) * SR)
    y[:n_in] *= np.linspace(0, 1, n_in, dtype=np.float32)[:, None]
    y = y * loudness_gain(y, -16.0)
    y = true_peak_guard(y, -1.6)
    out = os.path.join(ROOT, r["out"])
    y, m = encode_checked(y, out, 5)
    rep = loopfind.seam_report(y, a)
    manifest[r["out"]] = {"kind": "music", "lic": r["lic"], "loop_offset": round(a / SR, 4), "loop_end": round(b / SR, 4),
                          "duration": round(len(y) / SR, 3), "loop_score": round(score, 3), "seam": {k: round(v, 4) for k, v in rep.items()},
                          "lufs": m["I"], "lra": m["LRA"], "true_peak": m["TP"], "bytes": os.path.getsize(out),
                          "source_trim_s": round(r.get("trim", 0.0) + cut / SR, 4)}
    print("music", r["out"], manifest[r["out"]])


def build_stinger(src_root, r, manifest):
    x = decode(os.path.join(src_root, r["src"]), stereo=True)
    s0, dur = r["seg"]
    y = x[int(s0 * SR):int((s0 + dur) * SR)]
    y = trim(y, -50, -70)
    y = fades(y, fin=0.003, fout=r.get("fade", 0.5))
    y = y * loudness_gain(y, -16.0)
    y = true_peak_guard(y, -1.6)
    out = os.path.join(ROOT, r["out"])
    y, m = encode_checked(y, out, 5)
    manifest[r["out"]] = {"kind": "stinger", "lic": r["lic"], "duration": round(len(y) / SR, 3), "lufs": m["I"], "true_peak": m["TP"],
                          "bytes": os.path.getsize(out), "lead_ms": lead_ms(y)}
    print("stinger", r["out"], manifest[r["out"]])


def build_ambient(src_root, r, manifest):
    x = decode(os.path.join(src_root, r["src"]), stereo=True, af=r.get("af"))
    s0, s1 = r["seg"]
    xf = r.get("xfade", 3.0)
    seg = x[int(s0 * SR):int((s1 + xf) * SR)]
    n = int((s1 - s0) * SR)
    k = len(seg) - n
    out_y = seg[:n].copy()
    t = np.linspace(0, np.pi / 2, k, dtype=np.float32)[:, None]
    out_y[:k] = seg[:k] * np.sin(t) + seg[n:n + k] * np.cos(t)
    out_y = out_y * loudness_gain(out_y, -20.0)
    out_y = true_peak_guard(out_y, -1.6)
    out = os.path.join(ROOT, r["out"])
    out_y, m = encode_checked(out_y, out, 3)
    manifest[r["out"]] = {"kind": "ambient", "lic": r["lic"], "loop_offset": 0.0, "duration": round(len(out_y) / SR, 3),
                          "lufs": m["I"], "true_peak": m["TP"], "bytes": os.path.getsize(out)}
    print("ambient", r["out"], manifest[r["out"]])


def lead_ms(y):
    m = np.abs(to_mono(y))
    on = np.where(m > m.max() * 10 ** (-40 / 20))[0]
    return round(1000.0 * on[0] / SR, 2) if len(on) else 0.0


def cut_at_next_hit(x, min_gap=0.09, rel=0.35):
    """Ends a one-shot before the next take of a multi-take source begins."""
    hits = onsets(x, min_gap=min_gap)
    if len(hits) < 2:
        return x
    first = hits[0][1]
    for start, pk in hits[1:]:
        if start > int(min_gap * SR) and pk > first * rel:
            end = max(int(min_gap * SR), start - int(0.004 * SR))
            return fades(x[:end], fin=0.0, fout=min(0.03, end / SR * 0.2))
    return x


def variant_audio(src_root, v):
    stereo = bool(v.get("stereo"))
    x = decode(os.path.join(src_root, v["src"]), stereo=stereo, af=v.get("af"))
    if "seg" in v:
        x = x[int(v["seg"][0] * SR):int((v["seg"][0] + v["seg"][1]) * SR)]
    head = -40.0 if v.get("soft") else -24.0
    if "pick" in v:
        # pick = rank by loudness (0 = the strongest take of the file)
        hits = sorted(onsets(x), key=lambda h: -h[1])
        start = hits[min(v["pick"], len(hits) - 1)][0]
        x = x[start:]
    x = trim(x, head, -60)
    if not v.get("keep"):
        x = cut_at_next_hit(x)
    if v.get("maxlen"):
        x = x[:int(v["maxlen"] * SR)]
    x = pitch(x, v.get("semitones", 0))
    for layer in v.get("layers", []):
        lx = variant_audio(src_root, dict(layer, stereo=stereo))
        lx = peak_normalize(lx, -3.0 + layer.get("gain", 0.0))
        x = peak_normalize(x, -3.0)
        if len(lx) > len(x):
            lx = lx[:len(x)]
        x = x.copy()
        x[:len(lx)] += lx
    return x


def build_sfx(src_root, stem, variants, manifest):
    for i, v in enumerate(variants):
        x = variant_audio(src_root, v)
        x = trim(x, -40.0 if v.get("soft") else -30.0, -52.0 if v.get("soft") else -46.0)
        x = fades(x, fin=0.0015, fout=v.get("fade", 0.02))
        x = peak_normalize(x, -3.0)
        out = os.path.join(ROOT, "sfx", "%s_%d.ogg" % (stem, i))
        x, m = encode_checked(x, out, 4)
        key = "sfx/%s_%d.ogg" % (stem, i)
        licences = [v["lic"]] + [layer["lic"] for layer in v.get("layers", [])]
        manifest[key] = {"kind": "sfx", "lic": licences[0], "lic_all": sorted(set(licences)), "src": v["src"],
                         "duration": round(len(x) / SR, 3), "lead_ms": lead_ms(x), "true_peak": m["TP"], "lufs": m["I"],
                         "bytes": os.path.getsize(out), "channels": 2 if x.ndim == 2 else 1}
        print("sfx", key, manifest[key]["duration"], manifest[key]["true_peak"])


def main():
    src_root = sys.argv[1]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    mpath = os.path.join(ROOT, "audio_manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for r in MUSIC:
        if r["out"].startswith(only) or (only and only in r["out"]):
            build_music(src_root, r, manifest)
    for r in STINGERS:
        if r["out"].startswith(only) or (only and only in r["out"]):
            build_stinger(src_root, r, manifest)
    for r in AMBIENT:
        if r["out"].startswith(only) or (only and only in r["out"]):
            build_ambient(src_root, r, manifest)
    for stem, variants in SFX.items():
        if ("sfx/" + stem).startswith(only) or (only and only in stem):
            build_sfx(src_root, stem, variants, manifest)
    json.dump(dict(sorted(manifest.items())), open(mpath, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
