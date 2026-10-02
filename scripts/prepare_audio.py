"""Prepare licensed source recordings for low-latency browser playback. Not a test."""
from pathlib import Path
import subprocess
import wave
import numpy as np

ROOT=Path('/root/deadzone-source-audio')
OUT=Path('/app/frontend/public/audio');OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'firearms'/'Prepared SFX Library'

def decode(path):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','1','-ar','44100','pipe:1'])
    return np.frombuffer(raw,dtype=np.float32).copy()

def save(name,samples):
    peak=max(float(np.max(np.abs(samples))),.0001);samples=samples/peak*.88
    fade=min(3500,len(samples)//10);samples[-fade:]*=np.linspace(1,0,fade)
    path=OUT/(name+'.wav')
    with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes((samples*32767).astype(np.int16).tobytes())
    print(name,len(samples)/44100,path.stat().st_size)

for name,source,seconds in [('ak47','AK-47/C_28P.wav',1.05),('ak117','AK-47/C_31P.wav',.85),('ak107','AK-47/C_28P.wav',.95),('m4','AR-15/D_32P.wav',.9),('shotgun','Nova/O_21P.wav',1.3)]:
    a=decode(LIB/source); indices=np.where(np.abs(a)>.25*np.max(np.abs(a)))[0];start=max(0,int(indices[0])-180)
    a=a[start:start+int(seconds*44100)]
    if name=='ak117':a=np.interp(np.arange(0,len(a),1.10),np.arange(len(a)),a).astype(np.float32)
    if name=='ak107':a=np.interp(np.arange(0,len(a),.93),np.arange(len(a)),a).astype(np.float32)
    save(name,a)

a=decode(ROOT/'minigun.mp3');window=44100
energies=[float(np.mean(a[i:i+window]**2)) for i in range(0,len(a)-window,4410)]
start=int(np.argmax(energies))*4410;save('minigun',a[start:start+window])
for name,source in [('rocket','rlauncher.ogg'),('explosion','explosion.ogg'),('reload','weapswitch.ogg'),('lava','glauncher3.ogg')]:
    save(name,decode(ROOT/'q009'/'q009'/source))
if (ROOT/'torch.mp3').exists():
    a=decode(ROOT/'torch.mp3');start=10*44100;save('flamethrower',a[start:start+44100*2])