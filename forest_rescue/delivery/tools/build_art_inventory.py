from pathlib import Path
from PIL import Image
import json,hashlib
r=Path(__file__).resolve().parents[1]
rows=[]
for p in sorted((r/'art').glob('*.png')):
 with Image.open(p) as im: im.verify()
 with Image.open(p) as im: size=list(im.size)
 b=p.read_bytes();assert len(b)<=30000000
 rows.append({'path':str(p.relative_to(r)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'pixel_dimensions':size,'status':'visual_reference','preserved_native_png':True})
(r/'qa/ART_INVENTORY.json').write_text(json.dumps({'images':rows,'count':len(rows),'new_delivered_3d_models':0,'new_delivered_animation_clips':0},ensure_ascii=False,indent=2)+'\n')
plan=[]
def add(id,desc,refs,out='GLB+editable source+PBR+LOD',mode='new'):
 for f in refs:assert(r/'art'/f).is_file(),f
 plan.append({'id':id,'purpose':desc,'reference_images':['art/'+f for f in refs],'status':'requires_further_development','expected_output':out,'production_mode':mode,'animation_spec':'data/animation_manifest.json'})
for id,desc in [('golden_oak','дуб'),('dark_pine','сосна'),('birch','берёза'),('hollow_oak','полый дуб'),('willow','ива'),('fallen_trunk','поваленный ствол'),('moss_rock','скалы'),('bramble','кусты'),('reed_fern','камыш и папоротники')]:add('lf_env_'+id,desc,['02_forest_modular_kit.png'])
for id in ['bridge27m','hunter_shelter','quarry_mine','ruined_watchpost','standing_stones','camp_props']:add('lf_env_'+id,id,['06_environment_landmarks.png'])
for id in ['wood','iron','root']:add('lf_cage_'+id,'модуль клетки, дверь, замок, гнездо',['cage_variants_gate_sockets.png'])
for id in ['trail_cache','rune_lock','winch_sequence','paired_latch']:add('lf_mechanism_'+id,id,['10_artifact_mechanisms.png'])
for id in ['stone_rune','bronze_seal','amber_crystal','bone_key']:add('lf_artifact_'+id,'семейство, три различимых варианта для12ключей',['loot_artifact_families.png'])
add('lf_horse_origin','гнедая Искра, без седла/всадника',['horse_guide_turnaround_motion.png'],'riggedGLB+source+clips+PBR+LOD')
for id in ['captain','scout','shield_guard']:add('lf_squad_'+id,id,['04_expedition_squad_turnaround.png'],'riggedGLB+source+clips+PBR+LOD','adapt_existing_units_without_gameplay_changes')
for id in ['miller','herbalist','ferryman','courier','cooper','quarry_worker']:add('lf_civilian_'+id,'основа для36индивидуальных NPC',['civilian_survivors_turnaround_expressions.png','12_civilian_rescue_motion.png'],'riggedGLB+source+clips+PBR+LOD')
add('lf_guardian_tenerys','сверить оригинал; предлагаемый upgrade',['09_tenerys_guardian_direction.png'],'validated original or upgraded riggedGLB+source+clips+PBR+LOD','compare_original_before_redesign')
for id in ['velkor','kamneklyk','dragor']:add('lf_guardian_'+id,'сверить оригинал; предлагаемый upgrade',['11_other_guardians_direction.png'],'validated original or upgraded riggedGLB+source+clips+PBR+LOD','compare_original_before_redesign')
add('lf_boss_ancient_maw','новый огромный двуногий Пращур',['03_boss_ancient_maw_turnaround.png','05_boss_motion_keyposes.png'],'riggedGLB+source+all boss clips+PBR+LOD')
add('lf_boss_arena','арена, модули стены, ископаемая скала, укрытие',['08_final_boss_arena.png'])
add('lf_vfx_fog','постоянное исследование+мягкая визуальная маска',['07_fog_exploration_interface.png','18_hall3_unlock_intro.png'],'shader+mask renderer+state adapter+hall3 intro presentation')
add('lf_vfx_rewards','частицы находки и награды',['loot_artifact_families.png','07_fog_exploration_interface.png'],'bounded pooledVFX+accessibleUI')
(r/'data/asset-production-plan.json').write_text(json.dumps({'schemaVersion':1,'campaignId':'forest_rescue_v1','actual_models_in_this_delivery':0,'production_owner':'Claude Code per final user instruction','items':plan},ensure_ascii=False,indent=2)+'\n')
print('images',len(rows),'production groups',len(plan))
