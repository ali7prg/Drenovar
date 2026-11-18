#!/usr/bin/env python3
"""Decode and inspect delivered assets; no subjective/engine/device claims."""
from pathlib import Path
import argparse,hashlib,json,subprocess
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);a=p.parse_args();root=a.root
meta=json.loads((root/'assets/audio/audio_metadata.json').read_text());rows=[]
for asset in meta['assets']:
    for kind in ('master','game_aac','game_loop_pcm'):
        rel=asset.get(kind)
        if not rel:continue
        path=root/rel;data=path.read_bytes();assert len(data)<=30_000_000,(rel,'file limit')
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams'][0]
        assert int(info['sample_rate'])==48000 and info['channels']==2
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-acodec','pcm_f32le','-'])
        y=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
        assert len(y)>0 and np.all(np.isfinite(y)) and np.max(np.abs(y))<1
        expected=asset['samples_per_channel'];padding=len(y)-expected
        assert abs(padding)<=2048
        if kind!='game_aac':assert padding==0
        row=dict(id=asset['id'],kind=kind,path=rel,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),decoded_samples_per_channel=len(y),decoder_padding_samples=padding,peak_dbfs=float(20*np.log10(np.max(np.abs(y)))),clipped_samples=int(np.count_nonzero(np.abs(y)>=1)))
        if asset['loop'] and kind=='game_loop_pcm':
            row.update(loop_boundary_step=float(np.max(np.abs(y[0]-y[-1]))),largest_internal_step=float(np.max(np.abs(np.diff(y,axis=0)))))
            assert row['loop_boundary_step']<row['largest_internal_step']
        rows.append(row)
report=dict(passed=True,campaign_id=meta['campaign_id'],files_checked=len(rows),checks=['all files decoded with ffmpeg','48kHz stereo','finite PCM','no clipping','exact PCM sample counts','AAC padding <=2048 samples','loop boundary <= max internal step','exact file sizes <=30000000 bytes'],not_checked=['human listening','engine playback','visual sync','Safari decoding','iPhone 12'],assets=rows)
(root/'assets/audio/audio_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,files=len(rows),audio_file_bytes=sum(x['bytes'] for x in rows),largest_file_bytes=max(x['bytes'] for x in rows)),indent=2))
