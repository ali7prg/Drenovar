"""Builds one DRENOVAR English soldier: body, outfit, weapons, textures, rig,
animations and LOD exports.

Usage (Blender 5.3 as a Python module, `pip install bpy==5.3.0`):
    python -I build.py --unit ENG-01 --out <dir> [--blend <dir>] [--textures <dir>]
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import gear  # noqa: E402
import layers as L  # noqa: E402
import materials  # noqa: E402
import mh_base  # noqa: E402
import patterns  # noqa: E402
import texbake  # noqa: E402
from patterns import srgb  # noqa: E402


class Kit:
    """Holds the soldier being built and shared resources."""

    def __init__(self, unit, textures, body_args):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.unit = unit
        self.textures = textures
        self.tiles = materials.tile_set(os.path.join(textures, "..", "tiles"))
        self.rig, self.body, self.joints = mh_base.build_body(unit.replace("-", ""), **body_args)
        self.eyes = mh_base.add_eyes(self.rig, self.joints, unit.replace("-", ""))
        self.parts = []
        self.hide_rules = []
        self.landmarks = self._landmarks()
        self.mats = {}
        self.grips = {}

    def _landmarks(self):
        j = self.joints
        to = mh_base.to_blender
        return {"mouth": np.array(to(j["oris01____head"])), "eye_l": np.array(to(j["eye.L____head"])),
                "eye_r": np.array(to(j["eye.R____head"])), "chin_z": to(j["jaw____tail"]).z}

    def tile(self, key, name, color=(1, 1, 1), roughness=0.8, metallic=0.0):
        mat_key = (key, name, tuple(color))
        if mat_key not in self.mats:
            suffix = "" if tuple(color) == (1, 1, 1) else "_" + "".join(f"{int(c * 99):02d}" for c in color)
            self.mats[mat_key] = materials.material(f"{self.unit}_{name}{suffix}", self.tiles[key]["albedo"],
                                                    self.tiles[key]["normal"], color, roughness, metallic)
        return self.mats[mat_key]

    def baked(self, obj, name, pattern, size=1024, roughness=0.85, metallic=0.0, strength=6.0, uv=None):
        paths = texbake.bake(obj, pattern, size, self.textures, f"{self.unit}_{name}", strength, uv)
        mat = materials.material(f"{self.unit}_{name}", paths["albedo"], paths["normal"], (1, 1, 1), roughness, metallic)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        return mat

    def add(self, obj):
        self.parts.append(obj)
        return obj

    def rule(self, bones, minimum=0.5, zmin=-1e9, zmax=1e9, extra=None):
        return gear.region_rule(self.body, bones, minimum, zmin, zmax, extra)

    # --- helpers used by layers ------------------------------------------------
    def cover(self, bones, minimum=0.5, zmin=-1e9, zmax=1e9):
        self.hide_rules.append(self.rule(bones, minimum, zmin, zmax))

    def near_wrist(self, index, distance):
        v = self.body.data.vertices[index].co
        return any((v - self.rig.data.bones[f"wrist.{s}"].head_local).length < distance for s in "LR")

    def strap_shield(self, shield, side, drop=0.16, standoff=0.055):
        return strap_shield(shield, self.rig, side, drop, standoff)

    def finish(self, tone=None, stubble=0.6):
        args = {} if tone is None else {"tone": tone}
        self.baked(self.body, "skin_head", patterns.skin(self.landmarks, stubble=stubble, **args), 1024, 0.6, strength=3.0)
        eye_tex = os.path.join(mh_base.MH_DATA, "eyes", "materials", "brown_eye.png")
        self.eyes.data.materials.clear()
        self.eyes.data.materials.append(materials.material(f"{self.unit}_eyeReal", eye_tex, None, (1, 1, 1), 0.15))
        if self.hide_rules:
            hide_covered_body(self, self.hide_rules)


def hide_covered_body(kit, rules):
    """Removes body faces fully hidden under opaque garments (saves triangles, avoids poke-through)."""
    body = kit.body
    count = len(body.data.vertices)
    covered = np.zeros(count, dtype=bool)
    for rule in rules:
        covered |= np.array([rule(i) for i in range(count)])
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    doomed = [f for f in bm.faces if all(covered[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(body.data)
    bm.free()


def hold_weapon(kit, key, obj, side, extra=None):
    """Weapon authored along +Z with the grip centre at the origin: the shaft leaves the
    fist on the thumb side (grip frame -Z) and the knuckles face the weapon's -Y."""
    local = Matrix.Rotation(math.pi, 4, "X") @ (extra or Matrix.Identity(4))
    kit.grips[key] = (side, gear.hand_grip(kit.rig, side) @ local)
    return kit.add(gear.place_on_grip(obj, kit.rig, side, local))


def outfit_eng01(kit):
    """ENG-01 Spearman (concept 1): kettle hat over a linen hood, quilted aketon with red
    sleeves, St George surcoat, belts and pouch, wrapped boots, spear and kite shield."""
    L.trousers(kit)
    L.boots(kit)
    L.aketon(kit, srgb(0.40, 0.085, 0.07))
    L.surcoat(kit)
    L.hood(kit, srgb(0.6, 0.55, 0.45))
    L.bracers(kit)
    L.kettle_hat(kit)
    L.belt(kit)
    L.baldric(kit)
    L.pouch(kit)
    L.sheathed_sword(kit, "L")
    wood = kit.tile("wood", "wood_spear", (0.72, 0.62, 0.52), 0.7)
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    hold_weapon(kit, "main", gear.spear(wood, steel, 2.3, 1.05), "R")
    L.kite_shield(kit)
    kit.finish()
    return {"drill": "Spear_Drill", "style": "spear_shield", "grip_from_butt": 1.05}


def outfit_eng02(kit):
    """ENG-02 Swordsman (concept 7): nasal helm, mail hauberk with coif, red gambeson
    sleeves under, sleeveless St George surcoat, arming sword and kite shield."""
    L.trousers(kit, srgb(0.3, 0.29, 0.28))
    L.boots(kit, srgb(0.32, 0.2, 0.12), top=0.42)
    L.aketon(kit, srgb(0.42, 0.09, 0.07), offset=0.012)
    L.mail(kit, sleeves="long", skirt_to=0.62)
    L.mail_coif(kit)
    L.surcoat(kit, offset=0.04, hem=0.52)
    L.bracers(kit, length=0.1, offset=0.034)
    L.nasal_helm(kit)
    L.belt(kit, push=0.055)
    L.baldric(kit, lift=0.05)
    L.pouch(kit, push=0.11)
    steel = kit.tile("steel", "steel_weapon", (0.72, 0.72, 0.74), 0.3, 0.55)
    leather = kit.tile("leather", "leather_grip", (0.5, 0.38, 0.32), 0.6)
    hold_weapon(kit, "main", gear.sword(steel, leather, 0.8), "R")
    L.kite_shield(kit, seed=14)
    kit.finish()
    return {"drill": "Sword_Drill", "style": "sword_shield"}


def outfit_eng03(kit):
    """ENG-03 Longbowman (concept 5): nasal helm, red hood/scarf, mail sleeves under a
    St George surcoat, leather bracers, quiver on the hip, yew longbow."""
    L.trousers(kit, srgb(0.3, 0.28, 0.26))
    L.boots(kit, srgb(0.36, 0.22, 0.12), top=0.43)
    L.aketon(kit, srgb(0.44, 0.1, 0.08), offset=0.012)
    L.mail(kit, sleeves="long", skirt_to=0.66, offset=0.02)
    L.surcoat(kit, offset=0.036, hem=0.55)
    L.scarf(kit)
    L.bracers(kit, length=0.14, offset=0.032)
    L.nasal_helm(kit)
    L.belt(kit, push=0.05)
    L.pouch(kit, x=0.16, push=0.11)
    L.quiver_on_hip(kit, "R", 9)
    wood = kit.tile("wood", "wood_bow", (0.85, 0.62, 0.4), 0.6)
    string = kit.tile("rope", "cloth_string", (1, 1, 1), 0.9)
    hold_weapon(kit, "main", gear.longbow(wood, string), "L")
    kit.finish()
    return {"drill": "Bow_Draw", "style": "longbow"}


def outfit_eng04(kit):
    """ENG-04 Crossbowman (concept 8): kettle hat, red hood, quilted jack, short St George
    surcoat, bolt case on the hip, crossbow carried in both hands."""
    L.trousers(kit, srgb(0.32, 0.29, 0.26))
    L.boots(kit, srgb(0.33, 0.2, 0.11))
    L.aketon(kit, srgb(0.5, 0.44, 0.34), spacing=0.03, diamond=True)
    L.surcoat(kit, hem=0.6, red=srgb(0.48, 0.09, 0.07))
    L.hood(kit, srgb(0.42, 0.09, 0.07), name="wool_hood_red")
    L.bracers(kit, length=0.12)
    L.kettle_hat(kit)
    L.belt(kit)
    L.baldric(kit, left_hip=False)
    L.pouch(kit, x=-0.17)
    L.quiver_on_hip(kit, "R", 8, kind="bolt")
    wood = kit.tile("wood", "wood_stock", (0.7, 0.52, 0.36), 0.6)
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    string = kit.tile("rope", "cloth_string", (1, 1, 1), 0.9)
    hold_weapon(kit, "main", gear.crossbow(wood, steel, string), "R", Matrix.Rotation(math.radians(90), 4, "X"))
    kit.finish()
    return {"drill": "Crossbow_Reload", "style": "crossbow"}


def outfit_eng07(kit):
    """ENG-07 Man-at-arms (concept 6): open helm with cheek plates, mail with plate
    pauldrons, couters, knee cops and greaves, surcoat, sword and kite shield."""
    L.trousers(kit, srgb(0.27, 0.26, 0.25))
    L.boots(kit, srgb(0.3, 0.19, 0.11), top=0.3)
    L.aketon(kit, srgb(0.44, 0.1, 0.08), offset=0.012)
    L.mail(kit, sleeves="long", skirt_to=0.56)
    L.mail_coif(kit)
    L.surcoat(kit, offset=0.04, hem=0.5)
    L.scarf(kit)
    L.bracers(kit, length=0.15, offset=0.036, metal=True)
    L.greaves(kit)
    L.pauldrons(kit)
    L.knee_cops(kit)
    L.elbow_cops(kit)
    L.nasal_helm(kit, cheeks=True, scale=1.05)
    L.belt(kit, push=0.058)
    L.baldric(kit, lift=0.052)
    steel = kit.tile("steel", "steel_weapon", (0.74, 0.74, 0.76), 0.3, 0.55)
    leather = kit.tile("leather", "leather_grip", (0.5, 0.38, 0.32), 0.6)
    hold_weapon(kit, "main", gear.sword(steel, leather, 0.85), "R")
    L.kite_shield(kit, height=0.96, width=0.52, seed=15)
    kit.finish()
    return {"drill": "Sword_Drill", "style": "sword_shield"}


def outfit_eng08(kit):
    """ENG-08 Town militia: inexpensive kit of a settlement defender - iron skullcap over a
    hood, brown padded jack, short plain tabard with a small red cross, falchion and a
    town-painted heater shield."""
    L.trousers(kit, srgb(0.36, 0.32, 0.27))
    L.boots(kit, srgb(0.34, 0.24, 0.15), top=0.36, straps=0.0)
    L.aketon(kit, srgb(0.42, 0.32, 0.21), spacing=0.03, diamond=True)
    L.surcoat(kit, hem=0.66, base=srgb(0.6, 0.55, 0.44), seed=31, slit=0.0)
    L.hood(kit, srgb(0.38, 0.33, 0.25), name="wool_hood")
    L.nasal_helm(kit, scale=0.98)
    L.belt(kit)
    L.pouch(kit, x=0.17)
    steel = kit.tile("steel", "steel_weapon", (0.62, 0.62, 0.64), 0.4, 0.55)
    leather = kit.tile("leather", "leather_grip", (0.5, 0.38, 0.32), 0.6)
    hold_weapon(kit, "main", gear.sword(steel, leather, 0.62), "R")
    L.kite_shield(kit, height=0.66, width=0.46, seed=16)
    kit.finish()
    return {"drill": "Sword_Drill", "style": "sword_shield"}


def outfit_eng09(kit):
    """ENG-09 Foot recruit: young soldier in plain undyed quilted aketon (no surcoat), linen
    arming cap, red cross armband-style patch, short sword and a small round shield."""
    L.trousers(kit, srgb(0.4, 0.37, 0.32))
    L.boots(kit, srgb(0.38, 0.27, 0.17), top=0.3, straps=0.0)
    L.aketon(kit, srgb(0.66, 0.6, 0.48), spacing=0.026, diamond=False, bottom=0.7)
    L.arming_cap(kit)
    L.belt(kit, push=0.03)
    L.pouch(kit, x=0.17, push=0.07)
    steel = kit.tile("steel", "steel_weapon", (0.66, 0.66, 0.68), 0.4, 0.55)
    leather = kit.tile("leather", "leather_grip", (0.5, 0.38, 0.32), 0.6)
    hold_weapon(kit, "main", gear.sword(steel, leather, 0.55), "R")
    L.round_shield(kit, radius=0.24, design=L.round_design(0.24, 17, rim_red=True))
    kit.finish(stubble=0.25)
    return {"drill": "Sword_Drill", "style": "sword_shield"}


def outfit_eng10(kit):
    """ENG-10 Javelinman (concept 4): kettle hat, red scalloped hood, quilted red sleeves,
    St George surcoat, javelin case on the hip, round shield, javelin in hand."""
    L.trousers(kit, srgb(0.3, 0.28, 0.26))
    L.boots(kit, srgb(0.34, 0.21, 0.12))
    L.aketon(kit, srgb(0.42, 0.09, 0.07))
    L.surcoat(kit, hem=0.56)
    L.hood(kit, srgb(0.44, 0.09, 0.07), name="wool_hood_red")
    L.bracers(kit)
    L.kettle_hat(kit)
    L.belt(kit)
    L.baldric(kit)
    L.pouch(kit, x=0.17)
    wood = kit.tile("wood", "wood_javelin", (0.75, 0.62, 0.5), 0.7)
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    L.javelin_case(kit, wood, steel)
    hold_weapon(kit, "main", gear.javelin(wood, steel), "R")
    L.round_shield(kit, radius=0.3)
    kit.finish()
    return {"drill": "Javelin_Drill", "style": "javelin"}


# Field-model triangle counts of the 0.5.9 soldiers (docs/QA_EVIDENCE/v0.6.0/troop_audit.jsonl).
FIELD_BUDGET = {"ENG-01": 21898, "ENG-02": 21401, "ENG-03": 20275, "ENG-04": 21989, "ENG-05": 29114,
                "ENG-06": 34754, "ENG-07": 17591, "ENG-08": 22548, "ENG-09": 22360, "ENG-10": 21316}
OLD_ASSETS = os.path.normpath(os.path.join(HERE, "..", "..", "project", "assets", "army", "assets"))


def outfit_eng05(kit):
    """ENG-05 Mounted scout (concept 3): nasal helm, red scarf, quilted brown sleeves,
    St George surcoat, riding boots, spear, small kite shield; rides the project's grey horse."""
    L.trousers(kit, srgb(0.27, 0.25, 0.23))
    L.boots(kit, srgb(0.33, 0.21, 0.12), top=0.5, straps=0.0)
    L.aketon(kit, srgb(0.36, 0.27, 0.18), spacing=0.026, diamond=True)
    L.surcoat(kit, hem=0.62, slit=0.35)
    L.scarf(kit)
    L.bracers(kit)
    L.nasal_helm(kit)
    L.belt(kit)
    L.sheathed_sword(kit, "L")
    wood = kit.tile("wood", "wood_spear", (0.72, 0.62, 0.52), 0.7)
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    hold_weapon(kit, "main", gear.spear(wood, steel, 2.4, 1.0), "R")
    L.kite_shield(kit, height=0.72, width=0.42, seed=18)
    kit.finish()
    return {"drill": "Mounted_Drill", "mounted": os.path.join(OLD_ASSETS, "ENG-05-scout-lod1.glb")}


def outfit_eng06(kit):
    """ENG-06 Mounted knight (concept 2): nasal helm with cheek plates, mail with plate
    pauldrons and cops, St George surcoat, lance with pennant, kite shield; caparisoned horse."""
    L.trousers(kit, srgb(0.26, 0.25, 0.24))
    L.boots(kit, srgb(0.3, 0.19, 0.11), top=0.3)
    L.aketon(kit, srgb(0.44, 0.1, 0.08), offset=0.012)
    L.mail(kit, sleeves="long", skirt_to=0.62)
    L.mail_coif(kit)
    L.surcoat(kit, offset=0.04, hem=0.56, slit=0.35)
    L.greaves(kit)
    L.pauldrons(kit)
    L.knee_cops(kit)
    L.elbow_cops(kit)
    L.bracers(kit, length=0.15, offset=0.036, metal=True)
    L.nasal_helm(kit, cheeks=True, scale=1.05)
    L.belt(kit, push=0.058)
    wood = kit.tile("wood", "wood_lance", (0.75, 0.62, 0.5), 0.7)
    steel = kit.tile("steel", "steel_weapon", (0.74, 0.74, 0.76), 0.3, 0.55)
    lance = gear.spear(wood, steel, 3.0, 1.1)
    hold_weapon(kit, "main", gear.join([lance, L.pennant(kit, 3.0 - 1.1 - 0.5)], "Lance"), "R")
    L.kite_shield(kit, height=0.8, width=0.46, seed=19)
    kit.finish()
    return {"drill": "Mounted_Drill", "mounted": os.path.join(OLD_ASSETS, "ENG-06-knight-lod1.glb")}


def strap_shield(shield, rig, side, drop=0.16, standoff=0.055):
    """Shield strapped to the forearm: the forearm lies along the back of the shield,
    the face looks the way the back of the hand looks, the point hangs below the arm
    when the forearm is held across the body."""
    bones = rig.data.bones
    head = lambda name: bones[name].head_local.copy()
    elbow = head(f"lowerarm01.{side}")
    wrist = head(f"wrist.{side}")
    along = (wrist - elbow).normalized()
    palm, _, _ = gear.palm_normal(head, side)
    dorsal = -(palm - along * palm.dot(along)).normalized()
    up = along.cross(dorsal).normalized()
    if side == "R":
        up = -up
    across = up.cross(-dorsal).normalized()
    # Shield local axes: x = across, -y = face normal (dorsal), z = up.
    m = Matrix((across, -dorsal, up)).transposed().to_4x4()
    m.translation = elbow.lerp(wrist, 0.55) + dorsal * standoff - up * drop
    shield.matrix_world = m
    bpy.context.view_layer.objects.active = shield
    bpy.ops.object.select_all(action="DESELECT")
    shield.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return gear.rigid(shield, rig, f"lowerarm02.{side}")


OUTFITS = {
    "ENG-01": (outfit_eng01, {"muscle": 0.62, "weight": 0.5, "height": 0.5}),
    "ENG-02": (outfit_eng02, {"muscle": 0.68, "weight": 0.52, "height": 0.52}),
    "ENG-03": (outfit_eng03, {"muscle": 0.66, "weight": 0.45, "height": 0.55}),
    "ENG-04": (outfit_eng04, {"muscle": 0.6, "weight": 0.55, "height": 0.48}),
    "ENG-05": (outfit_eng05, {"muscle": 0.6, "weight": 0.45, "height": 0.5}),
    "ENG-06": (outfit_eng06, {"muscle": 0.75, "weight": 0.55, "height": 0.55}),
    "ENG-07": (outfit_eng07, {"muscle": 0.8, "weight": 0.58, "height": 0.56}),
    "ENG-08": (outfit_eng08, {"muscle": 0.52, "weight": 0.6, "height": 0.45}),
    "ENG-09": (outfit_eng09, {"muscle": 0.45, "weight": 0.4, "height": 0.47}),
    "ENG-10": (outfit_eng10, {"muscle": 0.6, "weight": 0.45, "height": 0.5}),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--textures", default=None)
    parser.add_argument("--blend", default=None)
    parser.add_argument("--static", action="store_true", help="skip animations")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    textures = args.textures or os.path.join(args.out, "textures", args.unit)
    builder, body_args = OUTFITS[args.unit]
    kit = Kit(args.unit, textures, body_args)
    info = builder(kit)
    if info.get("mounted"):
        import mounted
        mounted.mount(kit, info["mounted"], info)
    elif not args.static:
        import anim
        anim.build_all(kit, info)
    export(kit, args.out, args.blend)


def export(kit, out, blend_dir):
    os.makedirs(out, exist_ok=True)
    stem = kit.unit
    for obj in bpy.data.objects:
        if obj.type == "MESH" and not obj.data.materials:
            obj.data.materials.append(materials.material(f"{stem}_fallback", None, None, (0.5, 0.5, 0.5)))
    if blend_dir:
        os.makedirs(blend_dir, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(blend_dir, f"{stem}.blend"), compress=True)
    common = dict(export_format="GLTF_SEPARATE", export_texture_dir=f"{stem}-textures", export_skins=True, export_animations=True, export_yup=True,
                  export_apply=True, export_animation_mode="ACTIONS", export_force_sampling=True,
                  export_image_format="AUTO", export_texcoords=True, export_normals=True,
                  export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True,
                  export_optimize_animation_keep_anim_object=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(out, f"{stem}-lod1.gltf"), **common)
    # Field LOD: never heavier than the 0.5.9 field model it replaces (armies draw many).
    budget = FIELD_BUDGET.get(stem, 22000)
    small, large = 0, 0
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.data.calc_loop_triangles()
            count = len(obj.data.loop_triangles)
            if len(obj.data.polygons) > 200:
                large += count
            else:
                small += count
    ratio = max(0.08, min(0.42, (budget * 0.97 - small) / max(1, large)))
    print(f"LOD2 ratio {ratio:.3f} for budget {budget} (large {large}, small {small})")
    for obj in bpy.data.objects:
        if obj.type == "MESH" and len(obj.data.polygons) > 200:
            mod = obj.modifiers.new("LOD", "DECIMATE")
            mod.ratio = ratio
            mod.use_collapse_triangulate = True
    bpy.ops.export_scene.gltf(filepath=os.path.join(out, f"{stem}-lod2.gltf"), **common)


if __name__ == "__main__":
    main()
