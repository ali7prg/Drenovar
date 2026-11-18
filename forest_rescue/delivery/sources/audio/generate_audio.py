#!/usr/bin/env python3
"""forest_rescue_v1: original procedural sound assets, no external samples.
Python 3.10+, NumPy/SciPy, ffmpeg. Masters PCM24 48k stereo; AAC-LC delivery;
PCM16 forest loop for sample-accurate WebAudio looping.
"""
from pathlib import Path
import argparse, json, math, subprocess, wave
import numpy as np
from scipy import signal
SR=48000
SEED=171126

def clock(duration): return np.arange(round(duration*SR),dtype=np.float64)/SR

def noise(rng,n,low,high):
    y=signal.sosfilt(signal.butter(3,[low,high],btype='bandpass',fs=SR,output='sos'),rng.normal(0,1,n))
    return y/(np.std(y)+1e-12)

def edge(y,attack=.008,release=.1):
    env=np.ones(len(y));a=min(round(attack*SR),len(y)//2);r=min(round(release*SR),len(y)//2)
    if a:env[:a]=np.sin(np.linspace(0,np.pi/2,a))**2
    if r:env[-r:]=np.cos(np.linspace(0,np.pi/2,r))**2
    return y*env[:,None] if y.ndim==2 else y*env

def stereo(y,width=.08):
    if y.ndim==2:return y
    return np.stack([y+width*np.roll(y,41),y-width*np.roll(y,59)],axis=1)

def level(y,peak_db):
    y=y-np.mean(y,axis=0)
    return y*(10**(peak_db/20))/max(np.max(np.abs(y)),1e-12)

def forest(rng):
    # Both noise and gust envelope are periodic across exactly 12 seconds.
    t=clock(12);n=len(t);f=np.fft.rfftfreq(n,1/SR)
    def field(low,high):
        v=(rng.normal(size=len(f))+1j*rng.normal(size=len(f)))
        v*=np.exp(-(f/high)**2)*(1-np.exp(-(f/low)**2));v[0]=0
        y=np.fft.irfft(v,n=n);return y/(np.std(y)+1e-12)
    wind=field(100,1350)*(.6+.17*np.cos(2*np.pi*t/12)+.08*np.cos(2*np.pi*3*t/12))
    leaves=field(1100,6500)*(.15+.12*(.5+.5*np.sin(2*np.pi*5*t/12))**2)
    y=wind+leaves
    return np.stack([y+.16*np.roll(leaves,163),np.roll(wind,73)+leaves-.12*np.roll(leaves,127)],axis=1)

def rumble(rng):
    t=clock(2);n=len(t)
    envelope=np.sin(np.pi*t/2)**1.4
    # Designed warning texture; no creature/animal voice modelling.
    sub=.45*np.sin(2*np.pi*(61*t-4*t*t))+.19*np.sin(2*np.pi*94*t)
    grit=noise(rng,n,80,550)*(.16+.09*np.sin(2*np.pi*7.5*t)**2)
    y=(sub+grit)*envelope
    y=signal.sosfilt(signal.butter(2,700,fs=SR,output='sos'),y)
    return edge(stereo(y,.04),attack=.06,release=.35)

def hoof(rng):
    t=clock(.45);n=len(t)
    impact=(.9*np.sin(2*np.pi*112*t)+.38*np.sin(2*np.pi*233*t))*np.exp(-t/.037)*(1-np.exp(-t/.001))
    earth=noise(rng,n,130,2400)*.21*np.exp(-t/.022)*(1-np.exp(-t/.0008))
    # Quiet leather recovery follows the strike; no neigh or hoof-gait sequence.
    s=np.maximum(t-.035,0); leather=.034*noise(rng,n,260,920)*np.exp(-s/.08)*(1-np.exp(-s/.01))*(t>=.035)
    return edge(stereo(impact+earth+leather,.015),attack=.001,release=.08)

def bell(duration,frequency,at,decay=.65):
    t=clock(duration);s=np.maximum(t-at,0);y=np.zeros(len(t))
    for ratio,amp,rel in [(1,1,1),(2.01,.28,.72),(2.76,.13,.45),(4.11,.06,.24)]:
        y+=amp*np.sin(2*np.pi*frequency*ratio*s)*np.exp(-s/(decay*rel))
    return y*(1-np.exp(-s/.006))**2*(t>=at)

def artifact(rng):
    y=bell(1.5,329.63,0,.62)+.33*bell(1.5,493.88,.10,.45)
    return edge(stereo(y,.13),release=.25)

def latch(rng):
    t=clock(1);y=np.zeros(len(t))
    for at,amp,freq in [(.025,.45,380),(.21,.24,277),(.57,.72,310)]:
        s=np.maximum(t-at,0);mask=t>=at
        hit=(np.sin(2*np.pi*freq*s)+.31*np.sin(2*np.pi*freq*2.37*s))*np.exp(-s/.055)*(1-np.exp(-s/.001))
        y+=amp*hit*mask
        y+=amp*.08*noise(rng,len(t),1200,5500)*np.exp(-s/.009)*mask
    scrape=noise(rng,len(t),450,2100)*.06*np.sin(np.pi*np.clip((t-.25)/.28,0,1))**2
    return edge(stereo(y+scrape,.05),release=.12)

def gate(rng):
    t=clock(2);n=len(t)
    travel=np.sin(np.pi*np.clip(t/1.76,0,1))**1.1
    phase=2*np.pi*(135*t+11*t*t+2*np.sin(2*np.pi*1.4*t))
    friction=(np.sin(phase)+.28*np.sin(2.1*phase)+.09*np.sin(4.6*phase))
    friction*=travel*(.25+.13*np.sin(2*np.pi*5.3*t)**2)
    grain=noise(rng,n,230,2000)*travel*.055
    s=np.maximum(t-1.73,0);stop=(t>=1.73)*np.sin(2*np.pi*98*s)*np.exp(-s/.06)*(1-np.exp(-s/.003))*.44
    return edge(stereo(friction+grain+stop,.065),attack=.05,release=.1)

def relief(rng):
    # Instrumental resolution, intentionally no human sigh or crowd sample.
    y=bell(1.5,261.63,0,.5)*.6+bell(1.5,329.63,.09,.45)*.35+bell(1.5,392,.17,.4)*.25
    return edge(stereo(y,.18),attack=.015,release=.3)

def reward(rng):
    y=bell(2,196,0,.9)*.7+bell(2,293.665,.13,.8)*.55+bell(2,392,.27,.75)*.4+bell(2,493.88,.41,.62)*.22
    return edge(stereo(y,.2),attack=.01,release=.32)

def write_wav(path,y,bits):
    with wave.open(str(path),'wb') as w:
        w.setnchannels(2);w.setsampwidth(bits//8);w.setframerate(SR)
        if bits==16:payload=np.round(y*32767).astype('<i2').tobytes()
        else:
            q=np.round(y*(2**23-1)).astype(np.int32).ravel();v=np.empty((q.size,3),np.uint8)
            v[:,0]=q&255;v[:,1]=(q>>8)&255;v[:,2]=(q>>16)&255;payload=v.tobytes()
        w.writeframes(payload)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);a=p.parse_args();root=a.root
    game=root/'assets/audio';masters=root/'sources/audio/masters';game.mkdir(parents=True,exist_ok=True);masters.mkdir(parents=True,exist_ok=True)
    designs=[
      ('fr_forest_wind',forest,-16,'Периодический лесной ветер и листва',True),
      ('fr_distant_rumble',rumble,-12,'Условный низкий гул угрозы; не голос существа',False),
      ('fr_horse_hoof',hoof,-9,'Один синтетический удар копыта по земле со сбруей',False),
      ('fr_artifact_discovery',artifact,-7,'Бронзовый отклик найденного артефакта',False),
      ('fr_cage_latch',latch,-9,'Металлическая защёлка клетки',False),
      ('fr_gate_creak',gate,-11,'Скрип ворот и мягкий упор',False),
      ('fr_people_rescued',relief,-8,'Инструментальное облегчение после спасения; без голосов',False),
      ('fr_large_reward',reward,-7,'Расширенное подтверждение большой награды',False),
    ]
    assets=[]
    for i,(name,fn,db,description,is_loop) in enumerate(designs):
        y=level(fn(np.random.default_rng(SEED+i)),db);wav=masters/f'{name}.wav';write_wav(wav,y,24)
        aac=game/f'{name}.m4a'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-map_metadata','-1','-c:a','aac','-b:a','128k','-movflags','+faststart',str(aac)],check=True)
        pcm=None
        if is_loop:
            pcm=game/f'{name}.wav';write_wav(pcm,y,16)
        assets.append(dict(id=name,campaign_id='forest_rescue_v1',description_ru=description,status='requires_engine_setup',origin='original_procedural_synthesis_no_external_samples',master=str(wav.relative_to(root)),game_aac=str(aac.relative_to(root)),game_loop_pcm=str(pcm.relative_to(root)) if pcm else None,sample_rate_hz=SR,channels=2,master_pcm_bits=24,samples_per_channel=len(y),duration_seconds=len(y)/SR,peak_dbfs=round(float(20*np.log10(np.max(np.abs(y)))),4),rms_dbfs=round(float(20*np.log10(np.sqrt(np.mean(y*y)))),4),loop=is_loop,loop_start_sample=0 if is_loop else None,loop_end_sample=len(y) if is_loop else None))
    metadata=dict(schema_version=1,campaign_id='forest_rescue_v1',seed=SEED,assets=assets,verification=dict(generated=True,encoded=True,human_listening=False,engine_playback=False,iphone12=False),production_missing=['recorded human relief/dialogue','natural boss/creature vocalisation','natural horse vocalisation','recorded material Foley if required by art review'])
    (game/'audio_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'generated_cues':len(assets),'runtime_decoded_bytes_all_cues':sum(x['samples_per_channel']*2*4 for x in assets),'max_duration_seconds':max(x['duration_seconds'] for x in assets)},indent=2))
if __name__=='__main__':main()
