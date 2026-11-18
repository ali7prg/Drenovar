"""Per-species configuration (art/02 crops, segmentation, LOD/variant recipes) + kit export + QA patch."""
import math
import os

import bpy
import numpy as np

import pblend
from frlib import core, paths, render as frr

RT = os.path.join(paths.RUNTIME, "forest")

LODS_MASS_OAK = {
    0: dict(trunk_step_m=0.35, trunk_sides=12, limb_step_m=0.3, limb_sides=5, limb_min_r_px=1.5, limb_budget=600,
            copies=True, copy_min_r_px=2.5, front_frac=1.0, front_scale=1.0, n_masses=14, clumps_per=52,
            fill_size=1.55, front_extra=0.6, max_cards=1350, core_cards=16),
    1: dict(trunk_step_m=0.7, trunk_sides=8, limb_step_m=0.6, limb_sides=4, limb_min_r_px=3.0, limb_budget=220,
            copies=True, copy_min_r_px=4.0, front_frac=0.55, front_scale=1.15, n_masses=12, clumps_per=22,
            fill_size=1.95, front_extra=0.3, max_cards=480, core_cards=6),
    2: dict(trunk_step_m=1.6, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.16, front_scale=1.5, n_masses=9, clumps_per=10, fill_size=2.5,
            front_extra=0.0, max_cards=110, core_cards=2),
}

LODS_MASS = {
    0: dict(trunk_step_m=0.35, trunk_sides=12, limb_step_m=0.3, limb_sides=5, limb_min_r_px=1.5, limb_budget=560,
            copies=True, copy_min_r_px=3.0, front_frac=1.0, front_scale=1.0, n_masses=13, clumps_per=26,
            fill_size=1.35, front_extra=0.6, max_cards=1250, core_cards=40),
    1: dict(trunk_step_m=0.7, trunk_sides=8, limb_step_m=0.6, limb_sides=4, limb_min_r_px=3.0, limb_budget=200,
            copies=True, copy_min_r_px=4.5, front_frac=0.55, front_scale=1.15, n_masses=11, clumps_per=12,
            fill_size=1.7, front_extra=0.3, max_cards=480, core_cards=14),
    2: dict(trunk_step_m=1.6, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.16, front_scale=1.5, n_masses=9, clumps_per=4, fill_size=2.2,
            front_extra=0.0, max_cards=104, core_cards=4),
}

LODS_VOLUME = {
    0: dict(trunk_step_m=0.35, trunk_sides=12, limb_step_m=0.3, limb_sides=5, limb_min_r_px=1.5, limb_budget=560,
            copies=True, copy_min_r_px=3.0, front_frac=1.0, front_scale=1.0, n_clumps=260, fill_size=1.45,
            front_extra=0.6, min_dist_k=0.6, max_cards=1250),
    1: dict(trunk_step_m=0.7, trunk_sides=8, limb_step_m=0.6, limb_sides=4, limb_min_r_px=3.0, limb_budget=200,
            copies=True, copy_min_r_px=4.5, front_frac=0.55, front_scale=1.15, n_clumps=120, fill_size=1.6,
            front_extra=0.35, min_dist_k=0.75, max_cards=500),
    2: dict(trunk_step_m=1.6, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.16, front_scale=1.5, n_clumps=34, fill_size=2.1, front_extra=0.0,
            min_dist_k=0.8, max_cards=104),
}

LODS_TREE = {
    0: dict(trunk_step_m=0.3, trunk_sides=12, limb_step_m=0.25, limb_sides=6, limb_min_r_px=1.3, limb_budget=820,
            copies=True, front_frac=1.0, front_scale=1.0, n_fill=390, fill_size=1.6, n_inner=40, min_dist_k=0.5),
    1: dict(trunk_step_m=0.6, trunk_sides=8, limb_step_m=0.5, limb_sides=4, limb_min_r_px=3.0, limb_budget=260,
            copies=True, front_frac=0.6, front_scale=1.12, n_fill=170, fill_size=1.75, n_inner=12, min_dist_k=0.6),
    2: dict(trunk_step_m=1.6, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.18, front_scale=1.5, n_fill=96, fill_size=1.9, n_inner=0, min_dist_k=0.6),
}

# grove oaks (art/01 look): broad, flat, lifted crown of yellow lobes, trunk + limbs visible below
GROVE_CFG = dict(placement="umbrella", umb_n=8, umb_rk=1.0, umb_base=0.5, umb_lobe_r=0.3, mass_r=0.25, mass_zscale=0.58, ao_under=0.68, ao_side=0.84, side_mode="shade", p_hires=0.6,
                 limbs_connected_only=True, limb_keep_r=2.2, anchor_min_r=2.2, anchor_min_z=7.6, mass_min_dist=2.7,
                 trunk_r_k=(1.06, 0.9), lobe_zf_min=-0.25, anchor_radial_k=1.25, anchor_step_m=1.2, lobe_limbs=True,
                 lobe_limb_r0=0.5, limb_min_top_z=6.5)
GROVE_LODS = {0: dict(n_masses=9, clumps_per=62, core_cards=0, max_cards=1250, copy_min_r_px=2.6),
              1: dict(n_masses=8, clumps_per=28, core_cards=0, max_cards=470, lobe_limb_pts=4),
              2: dict(n_masses=7, clumps_per=11, core_cards=0, max_cards=110, lobe_limb_pts=2)}

TREES = {
    "golden_oak": dict(
        cfg=dict(name="golden_oak", box=(0, 0, 430, 445), exclude=[(284, 360, 320, 432)], clip_row=410, ground_row=421,
                 fork_row=245, wood=dict(ratio=0.85, Lmax=64, hue_rng=(61, 95)), float_min_r=2.2, keep_x=(0, 428),
                 crown_kd=0.9, front_bias=0.45, trunk_kd=0.9, seed=7, root_zone=34, root_k=0.8, n_lobes=13, top_weight=1.6, lum_pref=2.6, mass_up=0.55, front_tilt_max=30, top_part=0.6, obl_part=0.75, vol_material=True,
                 mass_eta_min=0.04, mass_eta_max=0.45, core_eta_max=0.42, front_extra_eta=0.5, ao_under=0.8,
                 mass_zscale=0.55, p_hires=0.75, top_scale=1.0),
        n_patches=110, min_px=50, region="golden_oak", bark="oak", swatch=(20, 798, 318, 984), paintedLightMix=0.3,
        height_hint=13.3, crown_hint=7.2, lods=LODS_MASS_OAK, crown_mode="mass", mass_r=0.42,
        paintedLightMixByMaterial={"lf_foliage_vol": 0.5},
        hires=dict(region="oak_top", sheet="07_fog_exploration_interface.png", box=(518, 100, 800, 530), rosette_px=800,
                   m_per_px=1 / 50.0, l_shift=5.0, n_composite=16, keep_original=True),
        palettes=[dict(name="grove", region="oak_grove", lab=dict(dh=12.0, dl=2.0, kc=0.78))],
        single_refs="oak",
        tint_note="art/02 palette (orange-gold); for art/07 / art/01 look tint foliage toward warm yellow: "
                  "hue +0.02..+0.035, saturation x1.10, value x1.08 (INSTANCE_CUSTOM r,g,b)",
        variants={1: dict(seed=5, copies=[(125, 0.92), (-125, 0.9)]),
                  2: dict(seed=6, mirror=True, copies=[(90, 0.95), (180, 0.9), (-90, 0.95)], scale=(1.08, 1.2), palette="grove",
                          no_front=True, cfg=GROVE_CFG, lods=GROVE_LODS),
                  3: dict(seed=8, copies=[(100, 0.95), (200, 0.9), (-80, 0.95)], scale=(1.02, 1.24), palette="grove",
                          no_front=True, cfg=GROVE_CFG, lods=GROVE_LODS),
                  4: dict(seed=9, mirror=True, copies=[(120, 0.9), (-120, 0.9)], scale=(1.14, 1.16), palette="grove",
                          no_front=True, cfg=GROVE_CFG, lods=GROVE_LODS)},
        patch=dict(refs=[("07_fog_exploration_interface.png", (518, 110, 1020, 720), "art/07 panel 2"),
                         ("01_world_masterplan.png", (0, 0, 560, 330), "art/01 NW golden-oak grove")],
                   ground=(0.42, 0.44, 0.24), n=30, area=78.0, spacing=12.0),
    ),
}


LODS_PINE = {
    0: dict(trunk_step_m=0.4, trunk_sides=10, limb_step_m=0.3, limb_sides=4, limb_min_r_px=1.4, limb_budget=200,
            copies=False, front_frac=1.0, front_scale=1.0, n_masses=0, clumps_per=11, fill_size=1.25,
            front_extra=0.55, max_cards=1300, core_cards=10),
    1: dict(trunk_step_m=0.9, trunk_sides=6, limb_step_m=0.6, limb_sides=3, limb_min_r_px=3.0, limb_budget=0,
            copies=False, front_frac=0.55, front_scale=1.15, n_masses=0, clumps_per=5, fill_size=1.7,
            front_extra=0.25, max_cards=520, core_cards=4),
    2: dict(trunk_step_m=2.5, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.18, front_scale=1.5, n_masses=0, clumps_per=2, fill_size=2.3,
            front_extra=0.0, max_cards=105, core_cards=0),
}

LODS_WHORL = {
    0: dict(trunk_step_m=0.4, trunk_sides=10, limb_step_m=0.3, limb_sides=4, limb_min_r_px=1.4, limb_budget=160,
            copies=False, front_frac=1.0, front_scale=1.0, density=1.0, width_k=1.0, keep_every=1, max_cards=None,
            inner=True),
    1: dict(trunk_step_m=0.9, trunk_sides=6, limb_step_m=0.6, limb_sides=3, limb_min_r_px=3.0, limb_budget=0,
            copies=False, front_frac=0.5, front_scale=1.15, density=0.6, width_k=1.35, keep_every=1, max_cards=None,
            inner=True),
    2: dict(trunk_step_m=2.5, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.24, front_scale=1.6, density=0.42, width_k=1.6, keep_every=1, max_cards=44,
            inner=False, segs=2),
}

LODS_BIRCH = {
    0: dict(trunk_step_m=0.35, trunk_sides=10, limb_step_m=0.25, limb_sides=5, limb_min_r_px=1.2, limb_budget=900,
            copies=True, copy_min_r_px=1.8, front_frac=1.0, front_scale=1.0, n_masses=34, clumps_per=20,
            fill_size=1.1, front_extra=0.5, max_cards=1100, core_cards=8),
    1: dict(trunk_step_m=0.7, trunk_sides=6, limb_step_m=0.5, limb_sides=4, limb_min_r_px=2.6, limb_budget=260,
            copies=True, copy_min_r_px=3.5, front_frac=0.55, front_scale=1.15, n_masses=18, clumps_per=10,
            fill_size=1.5, front_extra=0.25, max_cards=450, core_cards=3),
    2: dict(trunk_step_m=2.0, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.18, front_scale=1.5, n_masses=10, clumps_per=5, fill_size=2.2,
            front_extra=0.0, max_cards=100, core_cards=0),
}

TREES["dark_pine"] = dict(
    cfg=dict(name="dark_pine", box=(428, 0, 640, 445), exclude=[(580, 362, 612, 430)], clip_row=410, ground_row=423,
             fork_row=40, wood=dict(mode="hue", hue_max=73, Lmax=60), keep_x=(430, 634), trunk_close=3, float_min_r=2.0,
             crown_kd=0.95, front_bias=0.45, trunk_kd=0.95, seed=11, root_zone=22, root_k=0.75, trunk_taper=0.1,
             lum_pref=3.5, front_tilt_max=30, top_part=0.65, obl_part=0.8, vol_material=True, n_tiers=10,
             tier_mass_px=24, mass_zscale=0.32, ao_under=0.8, front_extra_eta=0.95, core_eta_max=0.9),
    n_patches=130, min_px=40, region="dark_pine", bark="pine", swatch=(356, 798, 612, 984), paintedLightMix=0.3,
    paintedLightMixByMaterial={"lf_foliage_vol": 0.5},
    height_hint=14.0, crown_hint=3.4, lods=LODS_WHORL, crown_mode="whorls",
    tint_note="art/02 palette (dark blue-green spruce); world tint as forest_world.gd conifers is fine",
    palettes=[dict(name="dark", region="pine_dark", lab=dict(dh=58.0, dl=-5.0, kc=0.55))],
    variants={1: dict(seed=5, copies=[]),
              2: dict(seed=6, mirror=True, copies=[], palette="dark"),
              3: dict(seed=8, copies=[], scale=(0.74, 1.08), palette="dark"),
              4: dict(seed=9, mirror=True, copies=[], scale=(0.66, 1.14), palette="dark")},
    patch=dict(refs=[("01_world_masterplan.png", (430, 640, 960, 1000), "art/01 south pine forest"),
                     ("07_fog_exploration_interface.png", (900, 110, 1020, 330), "art/07 p2 conifers")],
               ground=(0.30, 0.33, 0.16)),
)

TREES["birch"] = dict(
    cfg=dict(name="birch", box=(628, 28, 880, 445), exclude=[(805, 355, 845, 432)], clip_row=410, ground_row=427,
             fork_row=250, wood=dict(mode="hue", hue_max=80, Lmax=95, white=(62, 26)), keep_x=(630, 866), trunk_close=2,
             float_min_r=1.6, crown_kd=0.85, front_bias=0.45, trunk_kd=0.95, seed=13, root_zone=0, ground_limbs=True,
             ground_limb_min_r=2.5,
             lum_pref=3.0, front_tilt_max=30, top_part=0.65, obl_part=0.8, vol_material=True, mass_zscale=0.7,
             ao_under=0.82, front_extra_eta=0.6, core_eta_max=0.5, top_by_chroma=True),
    n_patches=140, min_px=35, region="birch", bark="birch", swatch=(650, 798, 844, 984), paintedLightMix=0.3,
    swatch_m=0.45, tile_grade=dict(dh=5.0, dl=0.0, kc=1.05), bark_whiten=(40.0, 58.0, 86.0),
    paintedLightMixByMaterial={"lf_foliage_vol": 0.5},
    height_hint=13.0, crown_hint=4.4, lods=LODS_BIRCH, crown_mode="mass", placement="anchors", mass_r=0.15,
    anchor_min_r=1.3, anchor_step_m=0.9, anchor_min_z=3.5,
    tint_note="art/02 palette (yellow-green); world birch tint deepens green",
    variants={1: dict(seed=5, copies=[(120, 0.95), (-120, 0.9)]),
              2: dict(seed=6, mirror=True, copies=[(72, 0.95), (144, 0.9), (-72, 0.95), (-144, 0.9)], no_front=True,
                      cfg=dict(anchor_min_z=5.2, mass_min_dist=2.0, ao_under=0.88, anchor_source="patches", mass_r=0.105),
                      lods={0: dict(n_masses=24, clumps_per=12, max_cards=930, core_cards=0, copy_min_r_px=2.6,
                                    limb_budget=700),
                            1: dict(n_masses=24, clumps_per=10, core_cards=0), 2: dict(n_masses=12, clumps_per=6)}),
              3: dict(seed=8, copies=[(60, 0.9), (130, 0.95), (-60, 0.95), (-130, 0.9)], scale=(0.92, 1.05),
                      no_front=True, cfg=dict(anchor_min_z=5.5, mass_min_dist=2.0, ao_under=0.88, anchor_source="patches",
                                              mass_r=0.105),
                      lods={0: dict(n_masses=22, clumps_per=12, max_cards=1000, core_cards=0, copy_min_r_px=2.6,
                                    limb_budget=700),
                            1: dict(n_masses=22, clumps_per=10, core_cards=0), 2: dict(n_masses=12, clumps_per=6)})},
    patch=dict(refs=[("02_forest_modular_kit.png", (620, 28, 886, 445), "art/02 birch"),
                     ("01_world_masterplan.png", (150, 360, 520, 600), "art/01 mixed broadleaf")],
               ground=(0.33, 0.36, 0.17)),
)


def lab_transform(dh=0.0, dl=0.0, kc=1.0, kl=1.0):
    """Lab colour grade: hue rotation (deg), lightness offset/scale, chroma scale (painted structure kept)."""
    def fn(lab):
        L = lab[..., 0] * kl + dl
        a, b = lab[..., 1], lab[..., 2]
        C = np.hypot(a, b) * kc
        h = np.arctan2(b, a) + np.radians(dh)
        out = np.stack([np.clip(L, 0, 100), C * np.cos(h), C * np.sin(h)], -1)
        return out
    return fn


LODS_WILLOW = {
    0: dict(trunk_step_m=0.35, trunk_sides=10, limb_step_m=0.3, limb_sides=5, limb_min_r_px=1.4, limb_budget=520,
            copies=True, copy_min_r_px=2.0, front_frac=1.0, front_scale=1.0, n_masses=12, clumps_per=26,
            fill_size=1.15, front_extra=0.45, max_cards=1300, core_cards=14, curtains=230),
    1: dict(trunk_step_m=0.7, trunk_sides=6, limb_step_m=0.6, limb_sides=4, limb_min_r_px=2.6, limb_budget=160,
            copies=True, copy_min_r_px=3.5, front_frac=0.55, front_scale=1.15, n_masses=9, clumps_per=12,
            fill_size=1.5, front_extra=0.2, max_cards=480, core_cards=4, curtains=70),
    2: dict(trunk_step_m=2.0, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.2, front_scale=1.5, n_masses=7, clumps_per=5, fill_size=2.2,
            front_extra=0.0, max_cards=110, core_cards=0, curtains=24),
}

TREES["willow"] = dict(
    cfg=dict(name="willow", box=(1196, 80, 1536, 445), exclude=[(1375, 355, 1420, 430)], clip_row=410, ground_row=423,
             fork_row=230, wood=dict(mode="hue", hue_max=84, Lmax=52, min_area=260), keep_x=(1198, 1536), trunk_close=3,
             foot=0.96,
             float_min_r=1.8, crown_kd=0.9, front_bias=0.45, trunk_kd=0.95, seed=17, root_zone=18, root_k=0.75,
             lum_pref=3.0, front_tilt_max=30, top_part=1.0, obl_part=1.0, vol_material=True, mass_zscale=0.55,
             ao_under=0.9, ao_side=0.95, front_extra_eta=0.5, core_eta_max=0.45, curtain_eta=(0.25, 0.9),
             mass_eta_min=0.03, mass_eta_max=0.45, grove_k=(0.5, 0.85), limbs_connected_only=True, limb_keep_r=2.0),
    n_patches=150, min_px=30, region="willow", bark="willow", swatch=(1260, 798, 1516, 984), paintedLightMix=0.3,
    paintedLightMixByMaterial={"lf_foliage_vol": 0.5}, patch_mode="strips", strip_w=11, strip_h=80,
    height_hint=11.5, crown_hint=6.0, lods=LODS_WILLOW, crown_mode="mass", placement="dome", mass_r=0.3,
    tint_note="art/02 palette (olive-green weeping willow)",
    variants={1: dict(seed=5, copies=[(115, 0.92), (-120, 0.9)]),
              2: dict(seed=6, mirror=True, copies=[(100, 0.9), (-140, 0.95)]),
              3: dict(seed=8, copies=[(140, 0.9), (-100, 0.95)], scale=(0.9, 1.06))},
    patch=dict(refs=[("01_world_masterplan.png", (1000, 280, 1536, 700), "art/01 east river")], ground=(0.33, 0.36, 0.17)),
)


def export_kit(asset, built, sp, info, kind, k, args):
    from frlib import paths as P
    import fbuild  # noqa: F401 (forest helpers path)
    import glbx
    root = bpy.data.objects.new(asset, None)
    core.link(root)
    spacing = 0.0
    for v, objs in built.items():
        lo, hi = core.bounds([objs[0]])
        spacing = max(spacing, hi[0] - lo[0], hi[1] - lo[1])
    spacing += 2.0
    export_objs = [root]
    meta_vars = {}
    for i, v in enumerate(sorted(built)):
        objs = built[v]
        ve = bpy.data.objects.new(f"{asset}_v{v}", None)
        core.link(ve)
        ve.parent = root
        ve.location = (i * spacing, 0, 0)
        export_objs.append(ve)
        for o in objs:
            o.parent = ve
            o.location = (0, 0, 0)
            export_objs.append(o)
        bpy.context.view_layer.update()
        lo, hi = core.bounds([objs[0]])
        lo = lo - np.array([i * spacing, 0, 0])
        hi = hi - np.array([i * spacing, 0, 0])
        meta_vars[f"v{v}"] = {
            "nodes": [o.name for o in objs],
            "tris": {f"LOD{l}": core.tri_count(objs[l]) for l in range(3)},
            "materials": {f"LOD{l}": [m.name for m in objs[l].data.materials] for l in range(3)},
            "height_m": round(float(hi[2]), 2),
            "crown_radius_m": round(float(max(-lo[0], hi[0], -lo[1], hi[1])), 2),
            "bounds_m_blender": [np.round(lo, 2).tolist(), np.round(hi, 2).tolist()],
            "display_offset_gltf": [round(i * spacing, 3), 0.0, 0.0],
            "recipe": {kk: vv for kk, vv in sp["variants"][v].items() if kk != "seed"},
        }
    bpy.context.view_layer.update()
    out = os.path.join(RT, f"{asset}.glb")
    ext = {"lf_foliage_atlas": "lf_foliage_atlas.png", f"lf_bark_{kind}_c": f"lf_bark_{kind}_c.jpg",
           f"lf_bark_{kind}_n": f"lf_bark_{kind}_n.png", f"lf_bark_{kind}_r": f"lf_bark_{kind}_r.png"}
    core.select_only(export_objs, export_objs[0])
    core.export_glb(out, export_objs, animations=False,
                    extra=dict(export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                               export_active_vertex_color_when_no_material=False, export_image_format="AUTO"))
    glbx.externalize(out, ext)
    gi = glbx.info(out)
    meta = {
        "id": asset,
        "generation": "v2 image-based reconstruction from art/02 (painted cards + projected bark)",
        "variants": meta_vars,
        "tris": {f"LOD{l}": max(mv["tris"][f"LOD{l}"] for mv in meta_vars.values()) for l in range(3)},
        "bones": 0,
        "materials": sorted(set(gi["materials"])),
        "textures": {"lf_foliage_atlas.png": 2048, f"lf_bark_{kind}_c.jpg": 1024, f"lf_bark_{kind}_n.png": 1024,
                     f"lf_bark_{kind}_r.png": 1024},
        "texture_mode": "external shared files next to the GLB (relative URIs); one foliage atlas for the whole kit",
        "alpha": {"lf_foliage": {"mode": "MASK", "cutoff": 0.5, "double_sided": True}},
        "paintedLightMix": k,
        "paintedLightNote": "Textures carry the painted light. Shade as albedo * mix(1, lambert, paintedLightMix) "
                            "(lambert = max(dot(N, L), 0)); foliage normals are smoothed crown normals.",
        "edgeFade": {"what": "alpha *= smoothstep(0.10, 0.30, |dot(face_normal, view_dir)|) on foliage (alpha-tested) "
                             "surfaces; face normal from screen derivatives (cross(dFdx(VERTEX), dFdy(VERTEX))) so "
                             "cards seen edge-on vanish instead of streaking", "range": [0.10, 0.30]},
        "aoFormula": "albedo *= mix(0.42, 1.0, COLOR_0.a^2) (same as forest_wind.gdshader)",
        "recommendedTint": sp.get("tint_note"),
        "wind": {"attribute": "COLOR_0 (RGBA float, linear)",
                 "R": "sway weight 0 at the trunk base -> 1 at crown tips", "G": "leaf flutter (cards 0.45..1, bark 0)",
                 "B": "per-branch / crown-sector phase 0..1", "A": "ambient occlusion (1 outer front/top cards, "
                 "0.9 fill, 0.78 inner, bark 1)"},
        "clips": {"lf_forest_wind": {"seconds": 8.0, "loop": True, "type": "shader (vertex colour driven)"}},
        "layout_note": "Variants laid out along +X (display_offset_gltf); the three LODs of a variant share its origin "
                       "(trunk base on the ground).",
        "scale_note": "Real scale from the 1.8 m figure on art/02 (29.8 px/m).",
        "glb_images": gi["images"],
        "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_tree.py "
                 f"{asset.replace('lf_env_', '')}",
    }
    core.write_json(os.path.join(RT, f"{asset}.meta.json"), meta)
    core.save_blend(paths.source("forest", f"{asset}.blend"))
    return out


def forest_patch(asset, built, out_png, sp):
    """~30 mixed instances (variants, yaw, scale) on a ground plane at 55 deg, next to art/07 + art/01 crops."""
    from frlib import refs
    cfg = sp["patch"]
    rng = np.random.default_rng(3)
    insts = []
    area = cfg["area"]
    pts = []
    tries = 0
    while len(pts) < cfg["n"] and tries < 5000:
        tries += 1
        p = rng.uniform(-area / 2, area / 2, 2)
        if all(np.linalg.norm(p - q) > cfg.get("spacing", 7.0) for q in pts):
            pts.append(p)
    vs = sorted(built)
    for i, p in enumerate(pts):
        src = built[vs[i % len(vs)]][0]
        o = src.copy()
        o.name = f"patch_{i}"
        core.link(o)
        o.location = (p[0], p[1], 0)
        o.rotation_euler = (0, 0, rng.uniform(0, 2 * math.pi))
        s = rng.uniform(0.8, 1.1)
        o.scale = (s, s, s)
        insts.append(o)
    bpy.ops.mesh.primitive_plane_add(size=area * 1.6, location=(0, 0, 0))
    g = bpy.context.active_object
    m = bpy.data.materials.new("patch_ground")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*cfg["ground"], 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    g.data.materials.append(m)
    bpy.context.view_layer.update()
    pblend.only(insts + [g])
    # perspective camera at 55 deg pitch (game-like), framing the patch centre
    d = area * 0.95
    loc = (0.0, -d * math.cos(math.radians(55)), d * math.sin(math.radians(55)))
    cam = frr.perspective_camera(loc, (0, 0, 2.0), lens=35, res=(1100, 900))
    rgba = frr.render_rgba()
    img = rgba[..., :3] * rgba[..., 3:4] + np.array(cfg["ground"]) * (1 - rgba[..., 3:4])
    ims, labs = [], []
    for sheet, box, lab in cfg["refs"]:
        ims.append(refs.crop(refs.load(sheet), box))
        labs.append(lab)
    ims.append(img)
    labs.append(f"{asset} x{len(insts)} instances, 55deg, painted-light")
    frr.side_by_side(ims, labs, out_png, height=640)
    for o in insts:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.objects.remove(g, do_unlink=True)


# ------------------------------------------------------------------ matched-scale crops + Godot patch

SINGLE_REFS = {
    "oak": [("07_fog_exploration_interface.png", (768, 455, 962, 705), "art/07 p2 oak"),
            ("01_world_masterplan.png", (438, 126, 588, 228), "art/01 grove oak")],
}


def matched_scale(asset, obj, out_png, kind="oak", yaw=20):
    """Single painted reference trees vs the model at 55 deg rendered at the same crown width (px)."""
    import cv2
    from frlib import refs
    pblend.only([obj])
    pblend.ortho_frame([obj], 55, yaw, res=(520, 520), margin=1.02)
    rgba = frr.render_rgba()
    a = rgba[..., 3:4]
    ys, xs = np.nonzero(rgba[..., 3] > 0.5)
    crop = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    panels, labels = [], []
    for sheet, box, lab in SINGLE_REFS[kind]:
        ref = refs.crop(refs.load(sheet), box)
        w_ref = ref.shape[1]
        s = w_ref * 0.92 / crop.shape[1]
        r = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), max(1, int(crop.shape[0] * s))), interpolation=cv2.INTER_AREA)
        bg = np.median(ref[:6].reshape(-1, 3), 0)
        canvas = np.ones((max(ref.shape[0], r.shape[0]), w_ref, 3)) * bg
        oy = canvas.shape[0] - r.shape[0]
        ox = (w_ref - r.shape[1]) // 2
        sub = canvas[oy:oy + r.shape[0], ox:ox + r.shape[1]]
        canvas[oy:oy + r.shape[0], ox:ox + r.shape[1]] = r[..., :3] * r[..., 3:4] + sub * (1 - r[..., 3:4])
        panels += [ref, canvas]
        labels += [lab, f"{asset} 55deg same width"]
    frr.side_by_side(panels, labels, out_png, height=420)


def godot_patch(asset, built, sp, out_prefix, k, kind_files, n=30, spacing=11.0, area=70.0):
    """30 mixed instances exported as a temporary GLB and rendered in Godot with the painted override."""
    import shutil
    import subprocess
    import glbx
    from frlib import refs
    rng = np.random.default_rng(5)
    pts = []
    tries = 0
    while len(pts) < n and tries < 20000:
        tries += 1
        p = rng.uniform(-area / 2, area / 2, 2)
        if all(np.linalg.norm(p - q) > spacing for q in pts):
            pts.append(p)
    vs = sorted(built)
    objs = []
    for i, p in enumerate(pts):
        src = built[vs[i % len(vs)]][0]
        o = src.copy()
        o.parent = None
        o.name = f"patch_{i}"
        core.link(o)
        o.location = (p[0], p[1], 0)
        o.rotation_euler = (0, 0, rng.uniform(0, 2 * math.pi))
        s = rng.uniform(0.85, 1.1)
        o.scale = (s, s, s)
        objs.append(o)
    bpy.ops.mesh.primitive_plane_add(size=area + 30, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "patch_ground"
    gm = bpy.data.materials.new("patch_ground_mat")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.33, 0.13, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
    g.data.materials.append(gm)
    objs.append(g)
    tmp = os.path.join("/tmp", f"p3d_patch_{asset}")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    glb = os.path.join(tmp, f"{asset}_patch.glb")
    core.export_glb(glb, objs, animations=False,
                    extra=dict(export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                               export_active_vertex_color_when_no_material=False))
    glbx.externalize(glb, {os.path.splitext(f)[0]: f for f in kind_files})
    for f in kind_files:
        shutil.copy(os.path.join(RT, f), tmp)
    sh = os.path.join(os.path.dirname(os.path.abspath(__file__)), "godot_paint_view.sh")
    shots = {}
    for tag, dist in (("close", 0.42), ("far", 0.9)):
        od = out_prefix + f"_godot_{tag}"
        subprocess.run([sh, glb, od, f"--painted={k}", "--ground=0", "--yaws=25", "--pitches=55", f"--dist={dist}",
                        "--bg=0.55,0.6,0.62"], check=False, stdout=subprocess.DEVNULL)
        f = sorted(os.listdir(od))[0] if os.path.isdir(od) and os.listdir(od) else None
        if f:
            from PIL import Image
            shots[tag] = np.asarray(Image.open(os.path.join(od, f)).convert("RGB"), float) / 255.0
    ims, labs = [], []
    for sheet, box, lab in sp["patch"]["refs"]:
        ims.append(refs.crop(refs.load(sheet), box))
        labs.append(lab)
    for tag in ("close", "far"):
        if tag in shots:
            ims.append(shots[tag])
            labs.append(f"Godot painted k={k}: {len(pts)} instances, 55deg {tag}")
    frr.side_by_side(ims, labs, out_prefix + "_godot_patch.png", height=560)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return out_prefix + "_godot_patch.png"
