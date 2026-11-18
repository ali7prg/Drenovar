"""Compare -> fix log for the Ancient Maw (used by maw_report.py to write REPORT.md)."""

ITERATIONS = [
    {"iter": "01", "build": "1.6 cm SDF, smart-UV 60 deg, 2048 dev textures",
     "diffs": [
         "albedo ~25 % darker and greyer than the painting (measured mean ratio ref/render R1.35 G1.27 B1.16 on the head)",
         "legs read almost black; strong AO + groove darkening stacked on the de-lit projection",
         "UV atlas only ~39 % used (many tiny knob islands) -> low texel density on the head",
         "front compare used the side-view stance (right leg stepped back) -> leg mismatch in the front view",
         "head close-up: head slender, small teeth, smooth skin, faint scar",
         "osteoderm rows small/dark; mouth slit visible as a black hole in the front view"],
     "fixes": [
         "colour calibration gain (1.24, 1.17, 1.08) after AO; AO 0.70+0.30*ao; groove darkening 0.86..1.02",
         "front compare in the symmetric drawn stance (each view gets the stance it is drawn in)",
         "bigger paramedian osteoderms (7-8.5 cm) + skull-roof knob rows; wider snout (+3-4 cm half width)",
         "mouth cavity dome/trough start 20 cm behind the lips (no see-through hole); jaw closed 2 deg",
         "far-leg/arm turnaround pose corrected to the drawn positions"]},
    {"iter": "02", "build": "same pipeline, smart-UV 78 deg",
     "diffs": [
         "colour now warm brown, but texture soft; painted scale detail lost (projection blur 0.9 px)",
         "UV still only ~36 % (huge concave islands)",
         "head close-up: jaw lobes too round/thin, teeth ~70 % of the drawn size",
         "near shin front edge 5-10 cm behind the drawing"],
     "fixes": [
         "region-seam UV unwrap (32 body-part islands, limb tubes cut on the inner/back side, head islands x1.7) "
         "-> 61 % texel use",
         "teeth x1.3 length / x1.22 radius; fuller jaw cross-sections (super-ellipse 2.5-3.2)",
         "tibialis volume on the shin front; projection blur 0.45 px; scale relief +40 %, darker head grooves"]},
    {"iter": "03", "build": "region-seam UVs (61 % texel use); renders lost in a container restart, all its changes "
                            "are part of iter04",
     "diffs": ["(no compare images: the QA job was killed by a container restart; front iter02 reviewed instead)",
               "front: premaxillary teeth read as 2 fangs per side instead of a small row across the snout",
               "front: hands hang too low; claws look like straight spikes; burnt-umber chest too dark",
               "review (coordinator): head/skin must follow the close-up — large rough olive-iron/charcoal scales, "
               "burnt-umber throat, bigger irregular ivory teeth, taller shorter snout with visible nostril, "
               "pronounced brow osteoderms, clearly visible pale scar over the LEFT eye"],
     "fixes": ["6 small premaxillary teeth per side across the snout front; all other teeth x1.5 longer with random "
               "length (0.8-1.25) and tilt, brighter ivory",
               "snout 5.6 cm shorter and up to 5 cm taller; large nostril pits (17x12 cm) with raised rims",
               "brow knobs x1.4, skull-roof osteoderm rows x1.3",
               "scar: raised ridge 2.2-2.8 cm radius from the skull roof over the LEFT eye to the cheek, pale pink "
               "(0.90,0.76,0.74), 7.5 cm wide mask with fibrous streaks",
               "per-scale olive-iron/charcoal alternation + bronze scale centres on head/neck/back; darker head "
               "grooves; burnt-umber (0.50,0.27,0.13) throat/chest band; hands raised for the front stance; "
               "projection mask erosion 3 px (no background bleed)"]},
]
