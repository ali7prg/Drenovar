"""lf_orc_warden — captor of a forest cage (drains strength from the caged through the bars).

No reference art exists for this character: every number below is authored (metres, Blender world:
X = character's left, -Y = forward, Z up; feet on Z = 0).  The build reuses the v2 human pipeline
(shared `human_shared` skeleton, hv2 SDF fields / hands / drape sheets / pose solver / clip writer)
and replaces reference projection by a hand-authored painted texture (orc_tex.py).

Read by build_lf_orc_warden.py, orc_geo.py, orc_tex.py, orc_clips.py.
"""
import math

ID = "lf_orc_warden"
GROUP = "humans"
HEIGHT = 2.20                       # crown of the head (topknot excluded), hunched rest stance
BUDGET = (16000, 8000, 3000)        # LOD0 / LOD1 / LOD2 triangles (all mesh objects of a LOD)
TEX = 2048
VOXEL = 0.0032                      # body SDF voxel
PAINTED_LIGHT_MIX = 0.40
LIGHT = (-0.45, -0.55, 0.70)        # painted key light (to the light): upper-left of the front view

# --------------------------------------------------------------------------- skeleton joints
# spine with a forward hunch (neck/head ahead of the hips, rounded upper back)
SPINE = dict(Hips=(0.0, 0.030, 1.060), Spine=(0.0, 0.048, 1.240), Chest=(0.0, 0.056, 1.420),
             UpperChest=(0.0, 0.036, 1.600), Neck=(0.0, -0.010, 1.780), Head=(0.0, -0.070, 1.925),
             HeadTop=(0.0, -0.095, 2.170))
# left side (+X); the right side is mirrored
ARM = dict(Shoulder=(0.050, 0.012, 1.725), UpperArm=(0.285, 0.010, 1.705), LowerArm=(0.402, 0.045, 1.282),
           Hand=(0.468, -0.006, 0.908))
LEG = dict(UpperLeg=(0.150, 0.022, 1.040), LowerLeg=(0.176, -0.028, 0.585), Foot=(0.196, 0.048, 0.118))
FOOT = dict(length=0.345, width=0.150, toe_out_deg=11.0, heel_back=0.078)
HAND = dict(scale=1.42, palm_len=0.092, curl=(12.0, 22.0, 12.0))   # palm_len is scaled by `scale` (hv2_hand)

# head frame: origin at eye level on the mid-plane; parts authored in metres in this frame
HEAD = dict(origin=(0.0, -0.112, 2.010), scale=0.93)

# --------------------------------------------------------------------------- body volumes
# torso rows: z, half-width (x), front depth (-Y), back depth (+Y), centre y, superellipse exponent
TORSO = [
    (0.900, 0.212, 0.135, 0.150, 0.035, 2.3),
    (0.975, 0.244, 0.158, 0.176, 0.035, 2.3),    # glutes
    (1.060, 0.262, 0.176, 0.172, 0.036, 2.3),
    (1.160, 0.270, 0.204, 0.152, 0.040, 2.2),    # gut
    (1.280, 0.284, 0.214, 0.150, 0.046, 2.2),
    (1.400, 0.306, 0.204, 0.166, 0.050, 2.3),
    (1.520, 0.328, 0.190, 0.188, 0.045, 2.4),    # chest / lats
    (1.620, 0.336, 0.172, 0.204, 0.030, 2.5),    # upper chest, upper-back hump
    (1.700, 0.298, 0.148, 0.202, 0.014, 2.4),
    (1.770, 0.226, 0.120, 0.172, -0.006, 2.2),   # trapezius
    (1.830, 0.152, 0.100, 0.132, -0.030, 2.1),
    (1.885, 0.118, 0.090, 0.104, -0.052, 2.1),
]
# limb half-widths along the bone (s = 0 at the proximal joint): (s, radius_in_plane, radius_depth)
UPPER_ARM = [(0.0, 0.104, 0.104), (0.30, 0.090, 0.094), (0.70, 0.080, 0.082), (1.0, 0.068, 0.066)]
FOREARM = [(0.0, 0.064, 0.060), (0.25, 0.068, 0.061), (0.70, 0.055, 0.047), (1.0, 0.045, 0.036)]
THIGH = [(0.0, 0.136, 0.142), (0.30, 0.126, 0.134), (0.70, 0.106, 0.110), (1.0, 0.090, 0.092)]
SHIN = [(0.0, 0.082, 0.084), (0.28, 0.090, 0.096), (0.62, 0.075, 0.078), (1.0, 0.064, 0.066)]

# --------------------------------------------------------------------------- garments / gear
MANTLE = dict(hem=[(0, 1.715), (40, 1.675), (70, 1.610), (95, 1.585), (130, 1.500), (180, 1.405)],
              top=[(0, 1.790), (60, 1.820), (110, 1.900), (180, 1.985)],
              thick=0.062, ragged=0.055, voxel=0.0048, tris=2300, neck_open=0.118)
KILT = dict(z_top=1.120, under_hem=0.680,
            flaps=[dict(name="flap_front", phi=0.0, half=24.0, hem=0.500, cls="cloth_red", offset=0.030),
                   dict(name="flap_back", phi=180.0, half=26.0, hem=0.540, cls="cloth_red", offset=0.030)],
            tassets=[dict(name=f"tasset_{i}", phi=p, half=17.0, hem=h, cls="leather", offset=0.024)
                     for i, (p, h) in enumerate([(52.0, 0.640), (-52.0, 0.640), (92.0, 0.660), (-92.0, 0.660),
                                                 (132.0, 0.630), (-132.0, 0.630)])])
BELT = dict(z=1.120, height=0.105, offset=0.016)
HARNESS = dict(width=0.062, z_top=1.735, x_top=0.150, z_bot=1.150, x_bot=0.215, ring_z=1.462)
PAULDRON = dict(side="l", radius=0.182, spikes=3, spike_len=0.085)
STAFF = dict(length=1.90, grip_from_bottom=1.12, radius=0.0215, cage_h=0.27, cage_r=0.064, crystal_h=0.150,
             crystal_r=0.034)
AMULET = dict(len=0.085, r=0.024)

# --------------------------------------------------------------------------- painted palette (sRGB 0..1)
PALETTE = {
    "skin": (0.395, 0.415, 0.318),          # grey-green olive
    "skin_warm": (0.455, 0.405, 0.318),     # knuckles, elbows, brow, ears
    "skin_dark": (0.230, 0.245, 0.190),     # creases, under the brow
    "lip": (0.290, 0.250, 0.210),
    "eye": (0.780, 0.600, 0.200),           # amber iris
    "tusk": (0.800, 0.740, 0.600),
    "hair": (0.105, 0.092, 0.078),
    "fur": (0.215, 0.180, 0.135),
    "fur_tip": (0.395, 0.345, 0.270),
    "leather": (0.250, 0.170, 0.110),
    "leather_worn": (0.390, 0.280, 0.180),
    "boot": (0.215, 0.150, 0.100),
    "cloth_dark": (0.270, 0.245, 0.200),    # under-kilt
    "cloth_red": (0.380, 0.170, 0.125),     # flaps
    "linen": (0.470, 0.420, 0.330),         # forearm / shin wraps
    "iron": (0.265, 0.275, 0.285),
    "rust": (0.400, 0.245, 0.140),
    "bone": (0.770, 0.715, 0.600),
    "staff_bone": (0.700, 0.640, 0.520),
    "crystal": (0.640, 0.930, 0.700),
}
GLOW = dict(color=(0.42, 1.0, 0.56), strength=0.85)   # resting glow; the director pulses it (ActorRig.set_glow)

# glTF material per texture class (one shared 2048 atlas; *_glow keeps emission in the game)
MATERIAL_OF = {
    "skin": "body", "eye": "body", "tusk": "body",
    "hair": "hair", "fur": "hair",
    "cloth_dark": "cloth", "cloth_red": "cloth", "linen": "cloth",
    "leather": "gear", "boot": "gear", "iron": "gear", "bone": "gear",
    "staff_bone": "prop", "staff_iron": "prop", "staff_leather": "prop",
    "crystal": "glow",
}
MATERIALS = ["body", "hair", "cloth", "gear", "prop", "glow"]
ROUGH = {"body": 0.88, "hair": 1.0, "cloth": 0.95, "gear": 0.72, "prop": 0.78, "glow": 0.25}

# --------------------------------------------------------------------------- clips (30 fps, in place)
CLIPS = [
    # id, seconds, loop
    ("lf_orc_idle", 3.2, True),
    ("lf_orc_walk", 1.05, True),
    ("lf_orc_turn_left", 1.0, False),
    ("lf_orc_turn_right", 1.0, False),
    ("lf_orc_order_point", 2.6, False),
    ("lf_orc_order_point_left", 2.6, False),
    ("lf_orc_talk", 3.0, True),
    ("lf_orc_drain", 3.2, False),
    ("lf_orc_roar", 2.0, False),
    ("lf_orc_look", 2.4, False),
]
WALK_SPEED = 1.10
POINT_DEG = 60.0          # pointing direction, degrees to the side of forward


def deg(a):
    return math.radians(a)
