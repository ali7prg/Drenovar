"""Validate authored animation specification; does not claim GLB/rig validation."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'data/animation_manifest.json').read_text())
assert data['campaignId'] == 'forest_rescue_v1'
ids = set()
clips = 0
for group in data['groups']:
    assert len(group['maximumDeformBonesByLOD']) == 3
    for clip in group['clips']:
        assert clip['id'] not in ids, clip['id']
        ids.add(clip['id'])
        clips += 1
        assert clip['durationSeconds'] > 0
        assert isinstance(clip['loop'], bool)
        assert clip['productionStatus'] == 'requires_model_rig_animation_production'
        marker_times = [m['timeSeconds'] for m in clip['markers']]
        assert marker_times == sorted(marker_times), clip['id']
        assert all(0 <= t <= clip['durationSeconds'] for t in marker_times), clip['id']
        assert all(m['authority'] == 'presentation_only' for m in clip['markers'])
assert clips == 60
campaign = json.loads((root / 'data/campaign.json').read_text())
boss = campaign['boss']
assert [(p['id'], p['hpAboveFraction'], p['attacks']) for p in data['bossPhases']] == [(p['id'], p['hpAboveFraction'], p['attacks']) for p in boss['phases']]
boss_clips = {c['id']: c for g in data['groups'] if g['id'] == 'boss_dinosaur' for c in g['clips']}
for attack_id, attack in boss['attacks'].items():
    if attack_id == 'stomp_waves':
        total = attack['telegraphSeconds'] + (attack['waveCount'] - 1) * attack['waveStartIntervalSeconds'] + attack['waveActiveSeconds'] + attack['recoverySeconds']
    else:
        total = attack['telegraphSeconds'] + attack['activeSeconds'] + attack['recoverySeconds']
    assert abs(boss_clips['lf_boss_' + attack_id]['durationSeconds'] - total) < 1e-8, attack_id
print(json.dumps({'ok': True, 'groups': len(data['groups']), 'authored_clip_specs': clips, 'delivered_animation_files': 0, 'validation': 'specification consistency only'}))
