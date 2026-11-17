"""Original dry contact cues, deterministic offline synthesis, no sampled library.
PCM is generated once, not on the audio/render thread. Listening acceptance on
the target speaker/headphones is separate from waveform/marker verification.
"""
from pathlib import Path
import argparse, json, wave
import numpy as np
from scipy.signal import butter, sosfilt

SPECS = {
    'foot': (.16, 110, .18), 'hoof': (.19, 175, .30),
    'bow': (.14, 270, .34), 'crossbow': (.12, 380, .40),
    'javelin': (.20, 100, .10), 'flesh': (.18, 85, .27),
    'armor': (.26, 440, .40), 'wood': (.20, 225, .38),
    'fall': (.42, 65, .35),
}

def generate(destination):
    destination.mkdir(parents=True, exist_ok=True); report=[]
    for family, (seconds, hz, resonance) in SPECS.items():
        for variant in range(3):
            rng=np.random.default_rng(711+variant+list(SPECS).index(family)*13)
            rate=48000;t=np.arange(round(seconds*rate))/rate
            noise=sosfilt(butter(2,[80,1900 if family!='javelin' else 1100],fs=rate,btype='band',output='sos'),rng.normal(0,1,len(t)))
            decay=seconds/(6 if family not in ['fall','javelin'] else 4)
            envelope=(1-np.exp(-t/0.0015))*np.exp(-t/decay)
            tone=np.sin(2*np.pi*hz*(1+variant*.03)*t)*np.exp(-t/(decay*.9))
            if family=='armor':
                for ratio in [1.67,2.43,3.19]:tone+=np.sin(2*np.pi*hz*ratio*t)*np.exp(-t/(decay*ratio))*.32
            if family=='hoof':noise+=np.roll(noise,round(.022*rate))*.35
            sound=(noise*.55+tone*resonance)*envelope
            sound-=sound.mean();sound*=.45/max(.01,abs(sound).max())
            sound*=np.minimum(1,np.maximum(0,(seconds-t)/.015))
            path=destination/f'{family}-{variant}.wav'
            with wave.open(str(path),'wb') as out:
                out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes((sound*32767).astype('<i2').tobytes())
            report.append({'file':path.name,'duration_ms':len(t)*1000/rate,'peak_dbfs':float(20*np.log10(abs(sound).max())),'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(sound**2))))})
    (destination/'manifest.json').write_text(json.dumps({'source':'Original deterministic procedural contact cues; no third-party recordings','rate':48000,'channels':1,'voices':8,'voice_gain_db':-14,'listening_acceptance':'OPEN on iPhone 12','files':report},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);generate(p.parse_args().destination)
